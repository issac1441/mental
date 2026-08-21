我已經完全讀懂相關程式碼路徑與測試所固化的契約。目前 workspace 沒有 `mental/` canonical model,所以以下分析屬於從程式碼直接推導(observed)加上我的綜合判斷(inferred),並在結尾建議是否要 `$build` 一份可留存的模型。

---

## 結論

A 和 B 其實在優化**兩個不同的指標**,不是互相替代的選項。

- **只有 A 會降低「死信率」本身**:3 次改 5 次,更多在 carrier 抖動下的訂單會在耗盡重試前就送出去。
- **B 完全不改變死信的數量**——重試次數還是 3,同樣多的訂單會掉進 `dead_lettered`——它想省的是死信「之後」人工重派的成本。
- 而且 B 照字面「不釋放庫存保留」的做法,和現有的 `RESERVATION_TTL_SECONDS = 120` 秒**直接衝突**:保留在 2 分鐘後就過期,遠短於任何人工重派的時間尺度(分鐘、小時級)。過期後重派不但拿不回原本的保留,反而會**重複扣一次庫存**,甚至因為自己被卡住的庫存而 `InsufficientStock` 失敗。所以 B 以「一行不釋放」的形式,對真實情境**達不到宣稱的目的**。

換句話說:你問的是「降死信率」,嚴格照這個指標,**A 對題、B 離題**。但 A 和 B 是**互補**的——A 減少流入 DLQ 的量,B 想降低已進 DLQ 者的復原成本。下面拆開講實際效果與代價。

---

## 現在發生什麼事(carrier 抖動時)

`dispatch()` 對 `RetryableError`(`CarrierTimeout`、`CarrierUnavailable`)重試,`FatalError` 不重試(`dispatch.py:61-71`)。重試排程由三個 lever 決定:

| Lever | 值 | 方向 |
|---|---|---|
| `MAX_DISPATCH_ATTEMPTS` | 3 | ↑ → 死信變少,但尾端延遲變長 |
| `BASE_RETRY_DELAY_MS` | 200(A/B 都不動) | ↑ → 每次退避變長 |
| `RESERVATION_TTL_SECONDS` | 120 | B 的隱藏耦合點 |

退避是 `200 * 2^(attempt-2) + jitter`(`dispatch.py:44-49`),第 2 次前睡 `200+j`、第 3 次前睡 `400+j`,`j = crc32(order_id) % 100`(0–99ms)。耗盡 3 次後 → `pipeline.py:61-67`:**釋放保留(退回庫存 + 刪除 reservation key)→ 記一筆 `{order_id, reason}` 到 dead_letters → 回 `dead_lettered` receipt**。注意 dead_letters 那筆**只有 order_id 和 reason,沒有原始訂單、也沒有 reservation**,所以人工重派必須重跑 `process()` → 再次 `reserve()`。

⚠️ 一個關鍵背景事實:這個 `jitter` 是**每筆訂單固定、且同一筆訂單三次重試都一樣**(只吃 order_id,不吃 attempt;`test_pipeline.py:65-69` 固化了這點)。所以在一次**共同的** carrier 抖動下,所有訂單幾乎踩同一條指數排程重試,沒有 per-attempt 隨機化去打散重試風暴。A 和 B 都**沒有**碰這個點。

---

## 選項 A:`MAX_DISPATCH_ATTEMPTS` 3 → 5(退避基準不變)

**實際效果**:多兩次機會、且重試視窗從約 **0.6–0.8 秒拉長到約 3.0–3.4 秒**(純 backoff:`600+2j` → `3000+4j` ms)。只要 carrier 在這個加長視窗內恢復,原本會死信的訂單就成功送出。

- 若各次失敗**獨立**、單次失敗率 p:死信率 `p³ → p⁵`。p=0.5 → 0.125→0.031(約 4× 少);p=0.3 → 0.027→0.0024(約 11× 少)。
- **但這是有邊界的**(要防的過度推論):A 只救「抖動長度介於約 0.8 秒到 3.4 秒之間」的訂單。比 0.8 秒短的本來就會成功;比 3.4 秒長的中斷,A 一樣死信。對「carrier 抖動」這種短暫 blip,A 正好對症;對長時間中斷無效。

**代價**:
1. **尾端延遲**:失敗訂單(以及要靠第 4、5 次才成功的訂單)掛在 worker 上的時間從約 0.6–0.8 秒 → 約 3.0–3.4 秒(純 backoff,約 4–5×),送出呼叫 3 → 5 次。`dead_lettered` receipt 也**晚約 2.4–2.6 秒**才回給呼叫端。
2. **抖動期間吞吐**:`process()` 是同步阻塞 sleep,單筆佔用 worker 拉長約 4–5 倍。大範圍 carrier 中斷時,受影響路徑吞吐下降、backlog 變深。這會**間接**把上游排隊訂單推向 `RESERVATION_TTL_SECONDS`(排太久 → 派送前保留過期 → reprice/rebuild)。單筆訂單自身不會踩到:3.4 秒 ≪ 120 秒,A 本身**不會**造成 reprice。
3. **重複送出風險**(視 `send` 是否冪等,程式碼看不到冪等鍵):`CarrierTimeout` = 「carrier 沒即時回應」,有可能它其實已收到。多兩次重試 = 多兩次重複派送曝險。此為既有風險,A 放大 ⅔。

**可逆性 / 測試**:A 是**改一個常數**,零資料遷移,秒回退。`DispatchExhausted` 訊息用 `MAX_DISPATCH_ATTEMPTS` 自動更新。**不會弄壞任何現有測試**(dead-letter 測試用永久 timeout,只檢查狀態/釋放,不數次數)。

---

## 選項 B:維持 3 次,dead-letter 後「不釋放」保留

**你想要的效果**:庫存續留,人工重派時 `reserve()` 走冪等分支直接拿回原保留,不用重搶。

**實際會發生的事(這是最重要的隱藏耦合)**:保留的 `created_at` 不會因 dead-letter 而更新,`reserve()` 重用時也**不 refresh TTL**(`inventory.py:64-67`)。所以:

- **重派在 120 秒內**:`reserve()` 回傳既有保留,不重搶、不 reprice。✅ 你要的效果——**但人工在 2 分鐘內重派幾乎不可能**。
- **重派在 120 秒後(真實情境)**:保留已過期 → `reserve()` 走 `_build()`(`inventory.py:68-70, 93-125`),它會**對現在的 catalog 再扣一次庫存**。因為 B 從沒退回原本那筆,於是:
  - 若該品項庫存被自己卡到不足(例:ANVIL 原 stock 2、訂單要 2 → 扣後 0 → rebuild 再要 2 → **`InsufficientStock`**)→ 重派直接變 `failed`。**諷刺地,B 本想保證庫存還在,結果因自己卡住的庫存而重派失敗。**
  - 若庫存夠 → **重複扣減**(一筆訂單佔了 2 份庫存),外加 `reprice_required=True` → 金額可能變動。

**代價**:
1. **破壞已被測試固化的 invariant**:`test_pipeline.py:51-63`(`test_dead_letter_after_exhausted_retries_releases_stock`)明確斷言死信後 `stock == 2`。B 會讓它變 0 → **這個測試會紅**。這代表「死信退回庫存」是目前**有意、有測試**的契約,B 是在改契約。
2. **庫存永久洩漏**:`release()` 是唯一退回庫存的路徑,沒有背景清掃。任何 dead-letter **後來沒被人工重派**的訂單,其庫存**永久**被扣住、無法販售。現行做法則是死信當下立即退回。
3. **把死信正確性耦合到 `RESERVATION_TTL_SECONDS`**:要真的達成 B 的意圖,不是「拿掉一行 release」,而是要改保留生命週期——讓 dead-lettered 的保留**豁免 TTL 過期或延長/刷新 TTL**,並讓重派路徑**重用而非 rebuild**。這是**比 A 大得多**的改動,牽動庫存正確性。

**可逆性**:程式碼可回退,但 B 上線期間造成的**洩漏/重複扣減庫存需要人工對帳**才能清乾淨。

---

## 一個情境對照:carrier 中斷約 2 秒

| | 現況(3 次) | A(5 次) | B(3 次,不釋放) |
|---|---|---|---|
| 這筆訂單 | ~0.6s 內三次都撞在中斷內 → **死信** | 第 5 次落在 ~3s、中斷已恢復 → **送出** ✅ | 一樣 **死信**(不變) |
| 庫存 | 立即退回 | 立即退回 | 卡住不退 |
| 人工重派 | 需重搶(可能被別單搶走 → `InsufficientStock`) | 同左,但要重派的量已變少 | >120s 後重派 → **重複扣 / `InsufficientStock` / reprice** |

A 自動救回這筆;B 不救、且它的復原路徑對真實時間軸是壞的。B 想解的「別單把釋放的庫存搶走」問題確實存在,但用「不釋放」解會換來更糟的 TTL 衝突。

---

## 需要你拍板的決定(Decision Manifest)

1. **優化目標到底是哪個指標?** 死信「發生率」(→ A)還是死信「復原成本 / 最終不可送達數」(→ B 的意圖)。兩者互補,可只做 A、也可 A+一個**正確版**的 B。
2. **A 的取捨**:接受失敗訂單尾端延遲 +約 2.4–2.6 秒、worker 佔用約 4–5×、以及多兩次重複送出曝險,換取死信減少(僅對 < ~3.4 秒的中斷有效)。
3. **B 的取捨**:你是否願意改保留生命週期(TTL 豁免/刷新 + 重用而非 rebuild)、破壞現有「死信退回庫存」測試、並承擔被遺棄死信的庫存長期卡住?**照字面「一行不釋放」不要做——它是錯的。**
4. **要不要順手處理真正的病灶**:若死信主要來自同步重試風暴,`backoff_ms` 的**每筆固定、跨次相同**的 jitter 才是 leverage 點(改成 per-attempt 隨機退避),A/B 都沒碰到。

**Human Decision: pending。** 在你選定前我不會動任何程式碼。請告訴我:(a) 目標指標是「降發生率」還是「降復原成本」;(b) 選 A、正確版 B、還是兩者;(c) 是否要我把這份比較存成 `mental/changes/<id>.md` 留存(預設不存)。決定後再交給 Plan Mode 規劃實作。

---
*Lens=engineer;著重 mechanism/scenario/evidence + 決策對照;detail=standard–deep。目前沒有可留存的 `mental/` 模型——若這條出貨/庫存/死信路徑之後還會反覆討論,建議用 `$build` 建一份小的 canonical model(dispatch 契約 + reservation 生命週期),之後 change/review 都能對著它談。*