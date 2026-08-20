一筆訂單最後只會落在三種結局之一,而決定命運的是「錯誤的種類」,不是「在哪個階段出錯」。系統裡其實有**兩套各自獨立的重試**,很容易被當成同一套:一套是庫存寫入的樂觀鎖重試,一套是 dispatch 送出的重試。而你問的「整個失敗」最乾淨的定義,就是拿到 `failed` 這張收據——它只由三類致命錯誤造成:驗證失敗、未知 SKU、庫存不足,而且一律不重試。

下面照著訂單流過管線的路徑(`ingest → reserve → price → dispatch`,見 `orderflow/pipeline.py:4`)拆給你看。

## 一切的分水嶺:錯誤被分成兩類

`orderflow/errors.py` 把所有錯誤切成兩個家族,這是理解全部失敗行為的鑰匙:

- `FatalError`(`errors.py:12`)及其子類 `ValidationError`、`UnknownSku`、`InsufficientStock`——**不可重試,立即失敗**。
- `RetryableError`(`errors.py:16`)及其子類 `VersionConflict`、`CarrierTimeout`、`CarrierUnavailable`——**短暫性,可退避重試**。

`process()` 回傳的 `Receipt.status` 就三種值:`"dispatched" | "failed" | "dead_lettered"`(`pipeline.py:32`)。分類決定你落在哪一種。

## 庫存保留怎麼運作

`Inventory.reserve()`(`inventory.py:54`)做的事:先查有沒有既有保留(以 `order_id` 為 key),然後:

1. **有、且未過期** → 直接回傳既有保留(`inventory.py:66`)。這就是「同一筆訂單重複處理」的**冪等**保證。
2. **有、但已過期** → 用當前目錄重建一份,標記 `reprice_required=True`,覆寫舊記錄(`inventory.py:68-71`)。過期門檻是 `RESERVATION_TTL_SECONDS = 120` 秒(`config.py:4`,`inventory.py:39-41`)。
3. **沒有** → 直接建一份新的(`inventory.py:73-74`)。

建立保留的 `_build()`(`inventory.py:93`)刻意分成**兩階段**:先把每一行都驗證過(SKU 存在、庫存夠),全部通過後才進第二個迴圈真正扣庫存。這是為了「一筆失敗的保留不留下任何要回滾的半成品庫存」(`inventory.py:94-95`)——所以致命錯誤發生在扣庫存之前,catalog 不會被動到。

**第一套重試就藏在這裡。** store 是一個帶版本號的樂觀鎖存儲(optimistic concurrency,`store.py:1`):寫入時必須帶著你讀到的版本號,對不上就丟 `VersionConflict`(`store.py:42`)。`_put_with_retry()`(`inventory.py:127`)會重讀版本、最多重試 `_PUT_ATTEMPTS = 3` 次(`inventory.py:21`),**沒有退避、沒有 sleep**,純粹是為了對付並行寫入同一個 key 的碰撞。單執行緒下(例如測試裡)這條路幾乎永遠不會觸發。

## Dispatch 的重試與死信

**第二套重試在 `dispatch()`(`dispatch.py:52`)。** 它跑一個最多 `MAX_DISPATCH_ATTEMPTS = 3` 次的迴圈(`config.py:7`):

- **只有 `RetryableError` 被接住重試**(`dispatch.py:67`);其他任何例外都當場往外拋。
- 第 2 次起在送出前先退避:`backoff_ms = BASE_RETRY_DELAY_MS × 2^(attempt-2) + jitter`(`dispatch.py:44-49`)。以 `BASE_RETRY_DELAY_MS = 200`(`config.py:10`)算,第 2 次約等 200ms、第 3 次約 400ms,**指數成長**。jitter 是 `crc32(order_id) % 100` 毫秒,固定 0–99ms、且同一筆訂單永遠一樣(可預測、`test_pipeline.py:65` 驗證)。
- 三次都敗給可重試錯誤 → 拋 `DispatchExhausted`(`dispatch.py:71`)。

管線接住 `DispatchExhausted` 後做三件事(`pipeline.py:61-67`):**釋放保留(把庫存還回 catalog)** → 訂單推進死信佇列 `dead_letters` → 回傳 `dead_lettered` 收據**而非拋例外**。`test_pipeline.py:51` 驗證:ANVIL×2 遇到永遠 timeout 的 carrier,重試耗盡後庫存回到 2,拿到 `dead_lettered`。

## 什麼情況下一筆訂單會「整個失敗」

嚴格對應 `failed` 收據的,只有下面這些**致命錯誤**,它們都不重試、而且 dispatch 根本不會執行(`test_pipeline.py:49` 斷言 `calls == []`):

- **驗證失敗 `ValidationError`**(`ingest.py`,被 `pipeline.py:47` 接住):`order_id` 缺失或非字串、`region` 不是 `domestic`/`offshore`、沒有任何行、某行缺 `sku`、或數量不是正整數(`ingest.py:27-46`)。
- **未知 SKU `UnknownSku`**:某行的 SKU 不在 catalog(`inventory.py:99`)。
- **庫存不足 `InsufficientStock`**:catalog 現有量小於要求量(`inventory.py:102-105`)。後兩者在 reserve 階段由 `pipeline.py:53` 接住。

## 幾個容易誤解的邊界

- **`dead_lettered` ≠ `failed`。** 死信不是失敗:它庫存有還、訂單有保留在佇列、呼叫端拿到收據不是例外。真正的 `failed` 才是「致命、立即放棄」。

- **還有第四條路:直接拋例外、根本沒有收據。** [observed] `process()` 在 reserve 外只接 `FatalError`(`pipeline.py:53`),在 dispatch 外只接 `DispatchExhausted`(`pipeline.py:61`)。所以:①並行寫入讓 `_put_with_retry` 三次都撞 `VersionConflict`(RetryableError)時,例外會**穿過** `except FatalError` 逃出 `process()`;②若 `send` 丟出的是 `FatalError` 或任何非 `RetryableError` 例外,`dispatch()` 不接(`dispatch.py:67` 只接 Retryable),它會一路逃出 `process()`。這兩條在 docstring 的「三種結局」裡都沒寫,是文件外的真實行為。所以「整個失敗」其實有兩種形狀:拿到 `failed` 收據,或 `process()` 直接拋例外。

- **過期重建會重複扣庫存(疑似 bug)。** [inferred] 過期分支(`inventory.py:68-71`)呼叫 `_build` 重新扣庫存,但**沒有先呼叫 `release()`** 把舊保留的庫存還回去(`release()` 只在死信路徑被呼叫,`pipeline.py:62`)。同一筆訂單在 TTL 過後被重跑一次,catalog 會被同一筆數量扣兩次。這會讓庫存慢慢流失,甚至讓後續訂單冒出**本不該發生的 `InsufficientStock` 失敗**——這點直接影響你要搞懂的失敗行為,值得驗證。

- **`reprice_required` 這個旗標,管線沒讀。** `process()` 一律 `price(reservation)`(`pipeline.py:57`),因為重建出來的保留本來就帶新價,所以功能上總是重新計價;但那個旗標在管線裡實際上沒有被分支使用。

**可調的旋鈕(改了會怎樣):** `RESERVATION_TTL_SECONDS`(↑ 保留活更久、越不會重建/重複計價)、`MAX_DISPATCH_ATTEMPTS`(↑ 更晚死信、更能撐過短暫故障)、`BASE_RETRY_DELAY_MS`(↑ 退避更久)、`_PUT_ATTEMPTS`(↑ 更能撐過寫入爭用才拋 `VersionConflict`)。

---

**Sources and gaps**
- 錯誤分類:`orderflow/errors.py:8-40`
- 管線與三種收據:`orderflow/pipeline.py:32,44-74`
- 保留/冪等/過期重建/兩階段/寫入重試:`orderflow/inventory.py:21,39-41,54-75,77-91,93-125,127-137`
- 樂觀鎖與 `VersionConflict`:`orderflow/store.py:29-47`
- Dispatch 重試/退避/死信:`orderflow/dispatch.py:22-27,44-49,52-71`
- 旋鈕:`orderflow/config.py:4,7,10`
- 行為佐證測試:`tests/test_pipeline.py:41-49`(致命不重試)、`51-63`(死信釋放庫存)、`65-69`(退避)、`71-86`(過期重建)
- **未驗證/待確認:**(1)過期重建的重複扣庫存我是從程式碼結構推斷,尚未實際跑出來;(2)兩條「拋例外而非回收據」的逃逸路徑需要並行寫入或會亂丟例外的 `send` 才會觸發,單執行緒測試碰不到。若要我用一段腳本重現這幾點,或改用 operator 視角談運維/復原,直接說。
- 此 workspace 目前沒有 canonical mental model(`mental/`);若想把上面這套失敗語意固化成可維護的模型,可用 `$build`。

Context: engineer lens · map,mechanism,scenario,evidence · standard→deep — 依你「搞懂失敗行為」的明確目標與這是 repository 問題而定;要換視角或深淺用 `lens= views= detail=` 或直接講。