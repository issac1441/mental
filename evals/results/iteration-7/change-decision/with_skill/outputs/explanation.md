我已讀完 change skill、四份 reference、change 模板,以及 orderflow 全部原始碼與測試。目前 workspace 沒有 `mental/` canonical model,所以以下分析屬 **inferred**(以現有程式碼為證據),不建立任何檔案。若日後想要一份可持續維護的 dispatch/inventory 模型,建議之後跑 `$build`。

以下是 `change`(decision 模式)分析。**唯讀,不實作。**

---

## 直接結論

兩個選項**不在同一個座標軸上**,不是二選一的替代方案:

- **A(3→5 次)真的會降低死信率** —— 針對「carrier 抖動」這種短暫、attempt 之間互相獨立的失敗,多兩次嘗試直接減少 dead-letter 發生率。代價是 retry 路徑的尾端延遲增加約 **2.4 秒**,並在抖動高峰期佔用 worker 更久。
- **B(不釋放庫存)完全不會降低死信率** —— 它改的是 dead-letter *之後* 的復原成本,不是 dead-letter *是否發生*。而且照字面「只是不呼叫 release」實作,在目前 120 秒 TTL 下,超過 2 分鐘的人工重派會踩到**庫存重複扣減**的隱藏 bug,反而比現況更糟。

如果目標嚴格是「降低死信率」,只有 A 能達成。B 是「降低單次死信的善後成本」,是另一個問題。

---

## 現況模型與預測

Pipeline 階段固定為 `ingest → reserve → price → dispatch`(`pipeline.py`)。關鍵現況:

- `dispatch()` 只重試 `RetryableError`(含 `CarrierTimeout`/`CarrierUnavailable`),最多 `MAX_DISPATCH_ATTEMPTS = 3` 次(`config.py:7`、`dispatch.py:61`)。用盡後丟 `DispatchExhausted`。
- backoff 為 `BASE * 2^(attempt-2) + jitter(0–99ms)`,`BASE = 200ms`(`dispatch.py:44-49`、`config.py:10`)。sleep 是**同步** `time.sleep`(`dispatch.py:56,63`)。
- dead-letter 時,pipeline **會呼叫 `inventory.release()`**,把庫存還回 catalog 並刪掉 reservation,再回 `dead_lettered` receipt(`pipeline.py:61-67`)。
- reservation 的 idempotent 只在「仍存活」時成立:`reserve()` 遇到未過期的舊 reservation 直接回傳;**一旦超過 `RESERVATION_TTL_SECONDS = 120`,走 rebuild 分支,`_build()` 會再次扣 catalog 庫存**(`inventory.py:64-71,108-125`;`config.py:4`)。
- **沒有背景清掃器**:過期只在「同一個 order 下次再 `reserve()`」時才被評估;`release()` 是目前唯一把 dead-letter 庫存還回去的路徑(`store.py` 只有 `delete`,無 TTL sweep)。

---

## 選項 A:`MAX_DISPATCH_ATTEMPTS` 3 → 5(退避基準不變)

**實際效果**
backoff 序列(每次 +jitter 0–99ms):

| attempt | 2 | 3 | 4(新) | 5(新) |
|---|---|---|---|---|
| sleep | 200 | 400 | 800 | 1600 |

- 用盡前的總 sleep:現況 `200+400 = 600ms`;A 之後 `200+400+800+1600 = 3000ms`。**每個走到第 4–5 次的 order 多花約 2.4 秒**(+jitter)。
- 對死信率:若每次抖動失敗獨立、機率 `p`,死信率由 `p³` 降到 `p⁵`。`p=0.3` → 2.7% 降到 0.24%(約 1/11);`p=0.5` → 12.5% 降到 3.1%(約 1/4)。**〔inferred:此獨立性假設是關鍵〕** 「抖動」若是短脈衝,attempt 間隔(最長到 ~3s)通常能跨過脈衝,獨立性成立、A 有效;若是**持續性 outage**(脈衝比 3 秒長),五次都落在同一段壞掉的時間裡,A 幾乎沒用,只是晚 2.4 秒才 dead-letter。

**代價**
- 尾端延遲 +2.4s(僅落在「本來就會抖」的 order 上,不影響早期成功的 order)。
- 同步 sleep 佔用 worker 更久;抖動高峰=重試 order 最多的時候,並發被進一步壓縮,**吞吐下降**。
- TTL 無虞:3s ≪ 120s,不會引發過期/reprice。
- 血緣極小:只改一個常數;`DispatchExhausted` 訊息自動跟著更新(`dispatch.py:26`);沒有測試斷言「恰好 3 次」。唯一副作用是 `test_dead_letter_...`(真實 sleep)會從 ~0.6s 變 ~3s,拖慢測試。
- **可逆性高**:改回去就是改回一個常數。

---

## 選項 B:維持 3 次,dead-letter 後不釋放保留

改動點是拿掉 `pipeline.py:62` 的 `self.inventory.release(...)`。

**實際效果**
- 對死信率:**零改變**。仍是 3 次用盡就 dead-letter。它只影響善後。
- 宣稱的好處「人工重派不用重搶庫存」**只在 reservation 仍存活(< 120s)時成立**,因為 `reserve()` 的 idempotent 只在未過期分支回傳舊 reservation(`inventory.py:64-67`)。

**代價與隱藏危害(這是重點)**
1. **超過 120s 後,重派會重複扣庫存,甚至扣不到。** 人工處理通常以分鐘/小時計,遠超 120s。此時 `reserve()` 走過期 rebuild 分支,`_build()` 對 catalog **再扣一次**(`inventory.py:68-71,108-125`),但上一份 reservation 的庫存從沒還回去。
   - 具體用測試 catalog 走一遍:`ANVIL` stock=2,order 訂 2 → dead-letter 後 catalog 仍是 0(因為不 release)。2 分鐘後人工重派 → `_build` 想扣 2、但只有 0 → **丟 `InsufficientStock`**(`inventory.py:101-105`)。**這張 order 因為自己上一份沒還的保留,把自己卡死了。**
   - 若庫存充足(如 `WIDGET` stock=10),則是**每次重派多漏 2 件**(10−2−2=6 給同一張 order 的兩份保留),庫存帳面被侵蝕。
2. **永久洩漏**:dead-letter 若被取消或永遠沒人重派,那份庫存**永遠回不來**(無 sweeper,release 是唯一回收路徑)。日積月累 → 假性缺貨 → 未來正常 order 誤報 `InsufficientStock`。
3. **計價語意**:若在存活期內重用舊 reservation,會**沿用舊的 unit price**(`reprice_required=False`);過期 rebuild 才 reprice,但同時踩上面的重複扣減。兩條路都有副作用。
4. **打破一條被測試釘住的不變式**:`test_dead_letter_after_exhausted_retries_releases_stock`(`tests/test_pipeline.py:51-63`)明確斷言 dead-letter 後庫存還原。B 會讓它失敗;這條測試的名字本身就是現行契約。

**要讓 B 真正做對,實際改動遠比「不 release」大**:得替 dead-letter 的 reservation 設計獨立、較長或不過期的生命週期;新增一條「重派時以 key 重用既有 reservation、繞過過期 rebuild」的入口;並補一條「取消/逾期未派 → 還庫存」的清掃/補償路徑。這是一個**歸屬權**問題(誰負責釋放 dead-letter 的庫存?),不是刪一行。

---

## 決策清單(Decision Manifest)

需要你拍板的,是這幾個明確選擇:

1. **我們到底在優化哪個指標?** dead-letter *發生率*(→ A)還是 dead-letter *善後成本*(→ B)?兩者不互相替代,可以同時做。
2. **A 的延遲/吞吐預算**:能接受抖動時尾端 +2.4s、並發下降嗎?
3. **若要 B**:願意連帶改 `RESERVATION_TTL_SECONDS` / 建立 dead-letter reservation 生命週期 + sweeper 嗎?還是只接受「120 秒內才有效、之後有重複扣減危害」的天真版?(天真版不建議上線。)
4. **歸屬**:B 之下,dead-letter 且被取消或無人重派的庫存,由誰、在何時釋放?

---

## 受影響的契約與不變式

- **A**:不破壞任何契約;`dispatch` 對外語意(只重試 retryable、用盡才 dead-letter、絕不靜默丟單)不變,只是把「用盡」的門檻抬高。
- **B**:直接改寫一條不變式——「dead-letter 會釋放庫存保留」(`pipeline.py` 失敗語意 docstring + `tests/test_pipeline.py:51`)。屬 **〔conflict〕**:提案與現有 agreed/tested 不變式衝突,必須顯式決策,不能默默改測試讓它過。

---

## 驗證指引(若之後採行)

- A:新增測試斷言 attempt 4/5 的 backoff = `800+jitter`/`1600+jitter`(比照 `test_backoff_doubles_with_stable_jitter`,`tests/test_pipeline.py:65`);dead-letter 測試改注入 5 次逾時。
- B:一定要加「dead-letter 後、超過 TTL 再 `reserve()`」的測試,把重複扣減/`InsufficientStock` 這個行為釘出來——否則它會靜默存在。

---

## 建議

若現在的痛點就是「死信率」,**先做 A**:一個常數、可逆、直接命中目標,代價(尾端 +2.4s、抖動時吞吐下降)有界且集中在本來就會失敗的 order 上——但先確認你的抖動比較接近「短脈衝、attempt 間獨立」而非「持續 outage」,否則 A 效益有限。

**B 不要照字面上線**。它不動死信率,而且在 120 秒外會製造庫存重複扣減與洩漏。若「重派要重搶庫存」確實很痛,把它當成一個獨立、較大的 reservation-lifecycle 設計來處理(可與 A 併行:A 降發生率,設計完整的 B 降殘餘死信的善後成本)。

---

**Human Decision: pending。** 在你就上面「決策清單」四點給出選擇前,我不會實作、也不會建立或提升任何 `mental/` artifact。你可以直接回覆選 A、選 B(天真版/完整版)、兩者併行,或要我把哪個選項展開成 `deep` 細節;若要我把這份比較存成 `mental/changes/…` 草稿,說一聲「存成 change brief」即可。

*(Lens: engineer;Views: map, mechanism, scenario, evidence;Detail: standard。依 repository 預設選定,無手動覆寫。)*