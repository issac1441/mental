我已完整讀過 orderflow 的原始碼與測試,也確認了證據邊界:`dead_letters` 目前只有 pipeline.py 寫入、test_pipeline.py 讀取筆數,沒有其他消費者;repo 內沒有既有的 redispatch 實作;也沒有任何 `mental/` canonical model。

因為沒有 canonical model,以下整份分析屬 **[inferred]**(我從程式碼綜合出來、尚未經你確認的模型),模式為 **intent**(只有期望結果,沒有既定方案)。我維持 read-only,沒有寫入任何檔案。

---

## 結論先講

你要的簽章 `force_redispatch(order_id)` **無法用「純新增」的方式做出來**,而且有兩個非顯而易見的重點:

1. **dead-letter 現在是一塊墓碑**。訂單一旦 dead-letter,`inventory.release()` 會把庫存還回目錄、**刪掉 reservation**,而 `dead_letters` 這筆只留下 `{order_id, reason}` [observed: `pipeline.py:61-67`]。原始 `Order`(region、lines)、raw payload、`Quote`、選到的 carrier **全都沒有留**。所以光憑 `order_id`,系統重建不出要重送的東西 —— 這個 change 一定會**回頭改到 dead-letter 這條路徑**要保存什麼。

2. **「不改變失敗語意」這個限制,本身就是複雜度的根源**。你想保留的失敗語意其中一條,就是「dead-letter 時釋放 reservation」(測試 `test_pipeline.py:51-63` 直接斷言庫存被還回)。正因為 reservation 被釋放刪除,redispatch **被迫要重新 reserve**,而重新 reserve 才把「重新定價」「庫存可能不夠」「重複出貨」這些問題全部拖進來。如果你願意 dead-letter 時**不**釋放,redispatch 幾乎是 trivial —— 但那就改了失敗語意。**限制與複雜度是同一枚硬幣的兩面。**

---

## 現在的模型:dead-letter 之後,訂單處於什麼狀態

pipeline 是 ingest → reserve → price → dispatch [observed: `pipeline.py:1-4`]。失敗語意目前是:

- **FatalError**(validation / UnknownSku / InsufficientStock):不重試,立即回 `status="failed"`。
- **RetryableError in dispatch**:退避重試到 `MAX_DISPATCH_ATTEMPTS`(=3),仍失敗就 dead-letter。

dead-letter 這條路徑一次做三件事 [observed: `pipeline.py:61-67`]:

| 動作 | 效果 |
|---|---|
| `inventory.release(order_id)` | 庫存還回目錄 **+ 刪除 reservation**(`inventory.py:77-91`) |
| `dead_letters.append(...)` | 只存 `{"order_id", "reason": str(last_error)}` |
| `return Receipt(...)` | `status="dead_lettered"` |

所以一筆 dead-lettered 訂單,在**持久狀態裡剩下的東西 = 一個 id + 一句失敗原因**。重送 dispatch 需要 `Order` 和 `Reservation`(見 `dispatch.py:52-58`、`choose_carrier` 要 region 與行重量),兩者都不在了。

---

## 你必須決定的事(這才是「需要考慮什麼」的主體)

我把決策點編號,方便你逐一拍板。標 ★ 的是「不決定就做不下去」的阻斷點。

**★ D1 — 重建來源:redispatch 拿什麼重建 Order/Reservation?**
- A. dead-letter 時**加大 `dead_letters` 這筆**,存下完整 `order`(視 D3 再決定要不要一併存 reservation 快照/原始 `Quote`)。→ 保住你要的簽章 `force_redispatch(order_id)`,代價是改了 dead-letter 記錄的資料形狀 + 記憶體。
- B. 改簽章成 `force_redispatch(order_id, raw)`,由呼叫端重新提供 payload。→ `dead_letters` 維持精簡,但**違反你要的簽章**,且假設呼叫端一定給同一張單。
- 建議 A,因為簽章要求如此;但要對你明講:這**動到了 dead-letter 路徑**(是資料契約變更,不是失敗行為變更)。

**★ D2 — 重新 reserve 與庫存**:因為要保留「釋放」語意,redispatch 一定得重新 reserve。dead-letter 與 redispatch 之間,還回去的庫存**可能被別的訂單吃掉** → 重新 reserve 會丟 `InsufficientStock`(FatalError)。要決定:此時 force_redispatch 回什麼?留在 dead_letters 還是轉 `failed`?(注意這條風險的**因**就是你的限制,見上面第 2 點。)

**D3 — 重新定價 vs 原始報價**:reservation 被刪後重建,走的是「全新建立」分支,會**抓當下目錄價**、而且 `reprice_required` 維持 `False`(`inventory.py:62-75`)。更進一步,`process()` **從來不讀** `reprice_required`,它一律用當下 snapshot 定價(`pipeline.py:56-57`)。所以 redispatch 會**靜默地用新價**、沒有任何旗標提示。要決定:redispatch 該沿用**原始報價**(那就得在 D1 時把 `Quote` 一起存)還是**收當下價**?「不改失敗語意」**不涵蓋**這一軸,別以為它自動有答案。

**D4 — 重複出貨 / 冪等**:`send()` 在單次 `process()` 內就可能被呼叫最多 3 次(重試,`dispatch.py:61-68`),所以「timeout 其實已出貨」的重複出貨風險**今天就潛在存在**。force_redispatch 再加一整個 dispatch 回合 → 把這個風險**放大成人為觸發**:操作員對一張「timeout 假失敗、實際已出」的單重送 = 出貨兩次。要決定:是否引入 idempotency key / 去重?最低限度也要寫清楚 force_redispatch 是 at-least-once,`send()` 若有非冪等副作用就不安全。

**D5 — 終態轉移與 `dead_letters` 帳務**:必須定義
- 守衛:`order_id` 不在 `dead_letters` 就拒絕(否則在重送一張不存在的單)。
- 成功後:**從 `dead_letters` 移除**(否則可被反覆重送 → 反覆出貨)。
- 再次耗盡重試:重新 dead-letter(這才是「失敗語意不變」最自然的讀法,見 D7)。
- 注意既有測試斷言 `len(dead_letters)==1`(`test_pipeline.py:61`),別讓加大欄位或重入破壞筆數語意。

**D7 — 新路徑自己的失敗契約**:把 force_redispatch 的結果對齊既有 status enum(`"dispatched"|"failed"|"dead_lettered"`,`pipeline.py:32`),**不要發明第四種狀態**(若真要 `"redispatched"`,那是 enum/契約變更,要單獨攤開)。最乾淨的做法:**直接重用 `dispatch()` 的重試→`DispatchExhausted` 機器**,讓「再次失敗」的行為與原本一字不差(同 `MAX_DISPATCH_ATTEMPTS`、同退避、同釋放)。這樣「不改失敗語意」= redispatch 只是同一台 dispatch 狀態機跑第二次,差別僅在**先重新 reserve、且讀一份保存下來的 order**。

**D6 / D8 —(可延後但要表態)並行與稽核**:`Pipeline` 沒有鎖,`dead_letters` 是普通 list(store 有樂觀並行 `VersionConflict`,list 沒有)。兩個 force_redispatch 併發、或 redispatch 撞上同 id 的新 `process()`,會 double-reserve/double-send 或弄亂 list。至少要講清楚假設(單執行緒操作員使用?)。稽核方面:手動重送是有金流副作用的操作,`dead_letters` 目前無 timestamp / 無嘗試次數 / 無操作者 —— 要不要留紀錄?

---

## 會被動到的 contract 與 invariant

- **`Receipt.status` enum**:維持三值,force_redispatch 要對映上去(D7)。
- **`dead_letters` 記錄形狀**:今天是 `{order_id, reason}`,D1 很可能加大它。目前唯一消費者是程式碼 + 一個測長度的測試,**波及面小,但仍是資料契約變更**,要標明。
- **「dispatch never silently drops an order」**(`dispatch.py:1-7`):redispatch 也不得靜默吞單。
- **「reserve 先驗證所有行才提交」**(`inventory.py:93-106`):重新 reserve 仍守住,失敗不留半截庫存 —— 這點對你有利。
- **庫存守恆**:release 已還、re-reserve 再扣,注意轉移過程不要出現雙還或雙扣。
- **既有邊界**:若 `send()` 丟 **FatalError**,現在會直接穿出 `process()`(`except DispatchExhausted` 不接它),reservation 不被釋放。redispatch 若重用 `dispatch()`,同樣邊界會被繼承 —— 要保留還是收斂,請一併表態。

---

## 代表性情境(拿 `test_pipeline.py` 的 o-4 當例子)

1. **順利重送**:o-4 因 carrier down 而 dead-letter,carrier 恢復,操作員 `force_redispatch("o-4")` → 重新 reserve ANVIL×2(庫存夠)→ 重送成功 → 從 `dead_letters` 移除,回 `dispatched`。**用什麼價?**(D3)
2. **庫存已被吃掉**:期間 ANVIL(還回成 2)被別單消耗 → 重新 reserve 丟 `InsufficientStock`。**回什麼?留在哪?**(D2/D5)
3. **又失敗**:carrier 仍掛 → 再次耗盡重試 → 重新 dead-letter + 再釋放,行為應與第一次**完全一致**(D7)。
4. **幻影成功**:原本 timeout 其實已出貨,操作員重送 → **出兩次**(D4)。

---

## 建議怎麼驗證(Plan Mode 後)

- 對「不在 `dead_letters`」的 id 呼叫 → 被拒。
- 成功重送 → 移除該筆 + 回 `dispatched`。
- 再次耗盡 → 重新 dead-letter + 再釋放(對映既有 dead-letter 測試)。
- 重新 reserve 遇 `InsufficientStock` 的路徑。
- 定價測試(把 D3 的決定釘死)。
- 保住既有測試:dead-letter 測試仍斷言釋放 + `len==1`,確認加大欄位不破壞它。

---

## Human Decision: pending

不實作。要往下走,請針對這幾點拍板:

1. **D1** — 重建來源(建議 A:加大 dead-letter 記錄),以及**連帶要不要存 reservation 快照 / 原始 Quote**。
2. **D3** — redispatch 收**當下價**還是沿用**原始報價**。
3. **D5 + D7** — 終態帳務(成功即移除、再失敗重新 dead-letter)與 redispatch 的結果契約(建議直接重用 `dispatch()` 機器、不新增狀態)。
4. **D2 / D4 / D6 / D8** — 庫存不足處置、重複出貨冪等、並行、稽核 —— 這些**本次做**還是**明確延後**。

決定之後,把接受的 delta 交給 host 的 Plan Mode;實作後走 `$review`(需要時 `$quiz`)再 `$sync`。

另外:目前 workspace **沒有 `mental/` canonical model**。這裡的「失敗語意 + dead-letter 生命週期」正是值得沉澱成 canonical 的東西 —— 若你想要一份可反覆對照、能防止之後偷偷改掉失敗語意的耐久模型,建議先跑 `$build`。

---

*Lens: engineer;Views: map, mechanism, scenario, evidence;Detail: standard。依 methodology 精度選定:repository 情境預設 engineer,你的請求「分析需要考慮什麼」把重心放在決策面,故加重 Decision Manifest。整份為 [inferred](無 canonical model)。*