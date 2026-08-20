`force_redispatch(order_id)` 本質上不是 dispatch 層的改動,而是一條 **re-reserve → re-price → re-dispatch** 的復原流程——因為訂單被 dead-letter 的當下,reservation 已經被釋放、庫存已經還回 catalog(`pipeline.py:62` 呼叫 `inventory.release`),而 dead-letter 只留下 `{order_id, reason}`(`pipeline.py:63-65`),**沒有保留 Order 本體**。所以真正要決定的不是「怎麼重送」,而是兩件更前面的事:重建訂單所需的資料從哪來,以及如何避免重複出貨——現有程式**完全沒有任何 idempotency 標記**。而「不改變失敗語意」這個限制,只鎖住了既有的 Fatal/Retryable 分流,它並沒有回答 redispatch 自己失敗時該怎麼辦——那是一塊全新的、必須由你決定的語意。

---

## 現況:一張單被 dead-letter 之後,系統留下什麼

追蹤 `pipeline.process` 的 dispatch 耗盡路徑(`pipeline.py:59-67`):

1. `dispatch()` 對 `RetryableError` 重試到 `MAX_DISPATCH_ATTEMPTS`(=3,`config.py:7`),仍失敗就 raise `DispatchExhausted`。
2. pipeline 接住後,**先** `self.inventory.release(order.order_id)`——這會把庫存加回 catalog **並且 `delete` 掉 reservation record**(`inventory.py:77-91`)。
3. 再 append 一筆 `{"order_id", "reason"}` 到 `dead_letters`,回一張 `dead_lettered` receipt。

`test_dead_letter_after_exhausted_retries_releases_stock`(`test_pipeline.py:51-63`)證實了這個不變量:dead-letter 後 ANVIL 庫存回到 2,**reservation 已不存在**。

這條路徑決定了 redispatch 的全部難度:被 dead-letter 的訂單在系統裡**只剩一個字串 id 和一個原因**,既沒有 lines、region,也沒有它當初被 reserve/定價的快照。

## `force_redispatch` 實際上被迫要做的事

因為 reservation 沒了、庫存還回去了,重送不可能只是「再呼叫一次 `dispatch()`」——`dispatch()` 需要 `Order` **和** `Reservation` 兩個物件(`dispatch.py:52-57`),而這兩個現在都不存在。所以它實際上必須:

- 拿回 Order 本體(目前無處可取)→ **re-reserve**(可能失敗)→ **re-price**(價格可能變)→ 才輪到 dispatch。

一條正常 trace:`force_redispatch("o-4")` → 重建 Order → `inventory.reserve` 走「全新 key」分支(`inventory.py:73-75`)→ 用**當前** catalog 價格 build,且**不會**設 `reprice_required` → `price()` 依這份新快照算出可能不同的總額 → `dispatch()` 成功。
一條失敗 trace:同上,但 re-reserve 時庫存已被別單吃掉 → raise `InsufficientStock`(FatalError)→ 這張本來只是「暫時性失敗」的單,現在以 **Fatal 收場**。

## 必須決定的事(Decision Manifest)

**1. 訂單資料來源。** dead-letter 只存 `{order_id, reason}`。兩條路:(A) enrich dead-letter,把 parsed `Order`(或原始 raw)一起存進去——這**改變了「dead-letter entry 是什麼」**;(B) 改簽名成 `force_redispatch(order_id, raw)` 讓呼叫方重新提供 payload——這**動到你要的簽名**,而且有「重送的 payload 與原單不一致」的完整性風險。你要的 `force_redispatch(order_id)` 單參數簽名,實際上**逼你選 A**。

**2. 重複出貨的防護(最高風險,也最貼近「失敗語意」)。** `send` 沒有 idempotency 契約(`dispatch.py:52`);一個「已送達但 ack 逾時」的 send,與「從未送達」在程式裡**完全無法區分**(retry 迴圈只記 `last_error`,`dispatch.py:67-68`)。同時 `dead_letters` 是 append-only、**沒有 status 欄位**(`pipeline.py:42`)。若不加「已重送 / sent」標記,並在成功後移除或標記該 entry,同一張單可被反覆 `force_redispatch` → **重複出貨**。注意這裡的微妙點:你想保留的失敗語意確實沒被動到,但**成功路徑引入了一個原本不存在的雙送危險**。

**3. re-reserve 的新失敗模式。** 承 trace,re-reserve 可能 raise `InsufficientStock` 或 `UnknownSku`(SKU 下架)——**都是 FatalError**。這打破操作者的直覺「dead-lettered = 暫時性,重試就會過」。要決定:這種情況回什麼?維持 `dead_lettered`?轉成 `failed`?還是一個新狀態?

**4. 重新定價 / 換 carrier。** re-reserve 擷取當前 catalog 價格且不設 `reprice_required`,而 pipeline 本來就**不看**這個旗標、每次都重算(`pipeline.py:57`;grep 確認全專案只有 inventory 和測試碰它)。結果:重送出去的單,**總價可能與原單不同**;若 `weight_g` 變了,`choose_carrier` 甚至可能選到不同 carrier(`dispatch.py:36-41`)。要決定:這種「合法但靜默的改價」可接受,還是要凍結/回填原價?

**5. redispatch 自身失敗的語意(「不改變失敗語意」沒回答的部分)。** 若沿用 `dispatch()`,再次耗盡會 raise `DispatchExhausted`,你**必須明確接住**。選項:re-dead-letter(再 append 一筆、再 release 一次——會與第 2 點的 dedup 打架)、直接 raise 給呼叫方、或回一個新狀態。這是全新語意,不是「保留既有語意」能涵蓋的。

**6. 擁有者與並行。** 這三樣東西(`inventory`、`send`、`dead_letters`)都掛在 `Pipeline` 上,所以它是 `Pipeline` 的方法。store 是 in-memory、單進程、樂觀鎖;人工重送與正常處理並行時靠 `VersionConflict` 重試化解(`inventory.py:127-137`),但要確認實際呼叫情境是否真的單進程。

**7. 可稽核性。** 目前無法從系統狀態看出一張單「是否被人工重送過、被誰、何時」。因為這是人工介入既有失敗流,建議至少記錄操作者/時間/原因。

## 失敗語意:哪些被鎖住、哪些是新開的

「不改變失敗語意」明確鎖住的既有行為(都要保持不變):

- FatalError(validation / unknown SKU / 庫存不足)→ 立即 `failed`、不重試、不進 dead-letter(`pipeline.py:47-54`)。
- dispatch 的 RetryableError → 退避重試至 `MAX_DISPATCH_ATTEMPTS` → dead-letter(release + append + `dead_lettered`)。

它**沒有**鎖住、因此是你這次要新定義的:redispatch 成功後 dead-letter entry 的去向(第 2 點)、re-reserve 的 Fatal 結果(第 3 點)、redispatch 再次耗盡的處置(第 5 點)。這三塊是這個 change 真正的設計工作,dispatch 的「重送」本身反而是最簡單的部分。

---

*Lens = engineer;Views = map · mechanism · scenario · evidence;Detail = standard(失敗路徑處加深)——依 repository 情境預設與你「分析要考慮什麼」的請求選定。此工作區沒有 `mental/` canonical model,所以以上代碼事實為 implementation truth(已附檔案行號),模型 delta 與風險評估為 **inferred**,尚待你確認。若決定後想把「dead-letter / dispatch 失敗契約」固化成 canonical model,可再跑 `$build`;若要把這份分析存成 change brief,回我 `record=true`。*

**Human Decision: pending** — 需要你拍板的確切選擇:
1. 訂單資料來源:enrich dead-letter 存 Order(A),還是改簽名讓呼叫方重送 payload(B)?(第 1 點)
2. 雙送防護:是否加 `sent`/status 標記與成功後 entry 的移除規則?(第 2 點)
3. re-reserve 遇 Fatal(庫存/SKU)時回哪種狀態?(第 3 點)
4. 靜默改價/換 carrier 是否接受,還是要回填原價?(第 4 點)
5. redispatch 再次耗盡時:re-dead-letter、raise、還是新狀態?(第 5 點)

在你決定前我不會動任何程式碼。決定後可交給 Plan Mode 落地,實作完再走 `$review`。