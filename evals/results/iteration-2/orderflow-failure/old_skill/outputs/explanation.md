I've now read the full `orderflow` codebase. Here's what the code actually does.

---

庫存保留是一個「**先全部驗證、再全部扣庫存**」的兩階段動作，它同時凍結「要消耗的庫存」和「要計價的單價」，並以 `order_id` 做冪等（idempotent）；保留有 120 秒 TTL，到期後會用當前型錄重建。系統其實有**兩套彼此獨立的重試**:一套是寫入 store 時的樂觀並發重試（`VersionConflict`,最多 3 次、無退避），另一套是 dispatch 出貨的重試（`RetryableError`,最多 3 次、指數退避＋抖動）。一筆訂單「整個失敗」有三種會回傳收據的乾淨結局,但還有**第四條不乾淨的路徑**——保留階段的並發衝突若把重試用光,會以未攔截的例外逃出 `Pipeline.process`,既不是 `failed` 也不是 `dead_lettered`。這條路徑正是文件與測試都沒寫到的地方,下面逐一拆解。

整條管線的順序是 `ingest → reserve → price → dispatch`（`orderflow/pipeline.py:44-74`),失敗行為完全由「哪一種例外、在哪一階段被丟出」決定,所以我先講清楚錯誤分類,再走保留、重試,最後收斂到失敗。

## 錯誤分成兩類,決定「會不會重試」

`orderflow/errors.py` 把所有例外分成兩支,這是理解失敗行為的根:

- **`FatalError`**（`errors.py:12`）— 不可恢復,**絕不重試**。子類:`ValidationError`(payload 不合法)、`UnknownSku`(型錄查無此 SKU)、`InsufficientStock`(庫存不足)。
- **`RetryableError`**（`errors.py:16`）— 暫時性,可重試。子類:`VersionConflict`(樂觀鎖衝突)、`CarrierTimeout`、`CarrierUnavailable`(出貨商暫時性錯誤)。

記住一個關鍵事實:**`VersionConflict` 屬於 `RetryableError`,不是 `FatalError`**（`errors.py:32`）。這一點稍後會決定第四種失敗路徑的走向。

## 庫存保留:兩階段的 validate → commit

`Inventory.reserve`（`inventory.py:54-75`）的核心委託給 `_build`（`inventory.py:93-125`），它刻意分成兩個迴圈:

1. **驗證階段**（`inventory.py:96-106`）:逐行讀 `catalog/{sku}`。查無 → 丟 `UnknownSku`;`stock < quantity` → 丟 `InsufficientStock`。**這一階段還沒有動任何庫存**。
2. **提交階段**（`inventory.py:108-120`）:逐行把 `entry["stock"] -= quantity` 寫回 store,並把當下的 `price_cents`、`weight_g` 快照進 `ReservedLine`。

這個「先驗證完再開始扣」的設計,目的（見 `inventory.py:94-95` 的註解）是讓驗證類的失敗「不留下要回滾的半套庫存」——因為 `UnknownSku` / `InsufficientStock` 都在還沒扣任何庫存前就丟出。

**冪等與 TTL**(`inventory.py:62-75`):

- 同一 `order_id` 再次進來,若既有保留還沒過期 → 直接回傳舊的(`inventory.py:64-67`),不重複扣庫存。
- 過期後(`created_at` 距今 > 120 秒,`inventory.py:39-41` + `config.py:4`)→ 用當前型錄**重建**,並標記 `reprice_required=True`,因為期間單價可能變了(`inventory.py:68-71`)。測試 `test_expired_reservation_is_rebuilt_and_flags_reprice`(`tests/test_pipeline.py:71-86`)覆蓋了這條。

`price()` 一律從(可能已重建的)保留快照計價,不從原始訂單(`pipeline.py:56-57`、`pricing.py:48-49`)——所以「凍結單價」是真的凍結在保留裡。

## 兩套獨立的重試機制

使用者問的「重試」其實有兩個,長得像但用途不同:

**(A) Store 寫入的樂觀並發重試** — `_put_with_retry`（`inventory.py:127-137`）

- 觸發:`VersionConflict`(別人搶先改了同一筆 record,`store.py:41-44`)。
- 次數:`_PUT_ATTEMPTS = 3`（`inventory.py:21`），**沒有退避 / sleep**,失敗就重讀版本再試(`inventory.py:135-136`)。
- 耗盡:第 3 次仍衝突 → **原封不動 `raise VersionConflict`**(`inventory.py:133`)。
- 範圍:保留過程中**每一次** store 寫入都走它——扣型錄庫存、寫保留 record 都是。

**(B) Dispatch 出貨重試** — `dispatch`（`dispatch.py:52-71`）

- 觸發:`send()` 丟出 `RetryableError`(如 `CarrierTimeout`),`dispatch.py:67-68` 只攔這一類。
- 次數:`MAX_DISPATCH_ATTEMPTS = 3`（`config.py:7`），總共試 3 次。
- 退避:第 2、3 次前會 sleep,`backoff_ms = 200 * 2^(attempt-2) + jitter`(`dispatch.py:44-49`)。也就是第 2 次前約 200–299ms、第 3 次前約 400–499ms;jitter 用 `crc32(order_id) % 100`,**每筆訂單固定、可重現**(測試 `test_backoff_doubles_with_stable_jitter`,`tests/test_pipeline.py:65-69`)。管線沒有注入假的 `sleep`,所以正式環境會真的睡(`pipeline.py:60`)——一筆最終死信的訂單會阻塞約 0.6–0.8 秒才放棄。
- 耗盡:3 次都失敗 → `raise DispatchExhausted(last_error)`(`dispatch.py:70-71`)。

**兩者最關鍵的差異在「耗盡之後」**:(B) 的耗盡是被管線**乾淨接住**的;(A) 的耗盡**沒有人接**。這正是失敗行為的分水嶺。

## 什麼情況下訂單會「整個失敗」

按結局分成三種收據 + 一種逃逸:

**① `status="failed"` — 立即失敗,不重試,不扣庫存**
由 `FatalError` 觸發,被 `pipeline.py:47` 或 `:53` 接住:
- parse 失敗(`ValidationError`):缺 `order_id`、region 不在 `{domestic, offshore}`、`lines` 空、sku 空、quantity 非正整數(`ingest.py:26-49`)。此時連保留都還沒開始。
- 保留驗證失敗:`UnknownSku` 或 `InsufficientStock`(`inventory.py:99, 102`)。因為在驗證階段丟出,**庫存沒被動過**。
- 測試 `test_insufficient_stock_fails_without_retry`(`tests/test_pipeline.py:41-49`)確認:回 `failed`、dispatch 完全沒被呼叫。

**② `status="dead_lettered"` — 重試耗盡後的可控失敗**
dispatch 三次都丟 `RetryableError` → `DispatchExhausted` → 管線在 `pipeline.py:61-67` 做補償:`inventory.release()` 把庫存還回型錄(`inventory.py:77-91`)、把訂單塞進 `dead_letters` 清單、回傳 `dead_lettered` 收據(**不丟例外**)。測試 `test_dead_letter_after_exhausted_retries_releases_stock`(`tests/test_pipeline.py:51-63`)確認 ANVIL 庫存從 2→0→補償回 2。

**③ `status="dispatched"` — 成功**,`pipeline.py:69-74`。

**④ 未攔截的例外 — 逃出管線的「不乾淨失敗」**  `[observed]`
若在**保留階段**發生持續的 `VersionConflict`,`_put_with_retry` 用完 3 次後 `raise VersionConflict`(`inventory.py:133`)。但 `pipeline.py:51-53` 的 reserve 只有 `except FatalError`——而 `VersionConflict` 是 `RetryableError`,**不是** `FatalError`(`errors.py:32`)。因此它**穿過整個 `Pipeline.process` 未被攔截**,呼叫端拿到的是例外,而不是任何收據。這條路徑在單執行緒下不會發生(沒有並發寫入者就不會衝突),但 store 的設計本意就是給並發用的(`store.py:1-6`),所以在正式部署裡它是真實存在的。管線 docstring 只列了 `failed` / `dead_lettered` 兩種失敗語義(`pipeline.py:8-15`),**沒有提到這一條**。

## 邊界:文件沒寫、測試沒蓋的更深失敗模式

既然你想「搞懂失敗的行為」,這兩個較深的坑值得知道(都未被測試覆蓋,標記為推論):

- **TTL 過期重建會重複扣庫存** `[inferred]`。過期分支(`inventory.py:68-71`)直接呼叫 `_build`(會再扣一次庫存),但**沒有先 `release` 舊保留的庫存**——舊的扣減只在 dead-letter 路徑才會被還回。結果:每次過期重建,舊保留的量就永久漏掉,型錄庫存被低估,甚至可能在重建時觸發一個本不該發生的 `InsufficientStock`。

- **提交階段中途失敗會留下半套庫存** `[conflict]`。`_build` 的 docstring 宣稱兩階段設計「不留下要回滾的半套庫存」(`inventory.py:94-95`),但這只對**驗證階段**成立。若提交迴圈(`inventory.py:108-120`)在扣完前幾行後,某一行的 `_put_with_retry` 因並發衝突耗盡而丟 `VersionConflict`,已扣的前幾行**不會回滾**,而且此時保留 record 還沒寫入(要等 `_build` 回傳後才寫,`inventory.py:74`),所以連 `release` 都沒得釋放。文件宣稱的不變式與實際並發行為在此**衝突**。

這兩點我還沒實測驗證,若你要我寫一個並發或過期情境的重現測試來確認,我可以接著做。

---

**Sources and gaps**
- 失敗分派與補償:`orderflow/pipeline.py:44-74`(尤其 `:47, :53, :61-67`)
- 保留兩階段、冪等、TTL 重建:`orderflow/inventory.py:54-75, 93-125`;store 重試 `:127-137`;釋放 `:77-91`
- 出貨重試與退避:`orderflow/dispatch.py:44-49, 52-71`;上限 `orderflow/config.py:4, 7, 10`
- 錯誤分類(決定重試與否的關鍵):`orderflow/errors.py:12-40`;樂觀鎖 `orderflow/store.py:29-47`
- 測試佐證:`tests/test_pipeline.py:41-49, 51-63, 71-86`
- 未覆蓋的缺口(僅程式碼推論、無測試):結局④ 的未攔截 `VersionConflict`、TTL 重建重複扣庫存、提交階段半套庫存
- 註:此 workspace 目前沒有 canonical 的 `mental/` 模型,以上皆直接讀原始碼得出;若要把這套失敗語義固化成可維護、可被後續 review/sync 追蹤的模型,可執行 `$build`。

*Context: engineer lens · map,mechanism,scenario,evidence · deep — 依你「想搞懂失敗行為」的明確目標選定,並在保留/重試機制上加重 mechanism 與 boundary;可用 `lens= views= detail=` 調整。*