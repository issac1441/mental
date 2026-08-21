你的系統沒有 `mental/` canonical 模型,所以以下是我直接讀 `orderflow/` 的程式碼與 `tests/test_pipeline.py` 追出來的因果行為(read-only,沒有動任何檔案)。

---

一筆訂單走的是固定四階段:`ingest → reserve → price → dispatch`(`orderflow/pipeline.py:44`)。**庫存保留**會一次凍結兩樣東西——要扣的庫存,以及當下的單價快照——而且對同一個 `order_id` 是冪等的、有 120 秒 TTL。系統裡其實有**兩層完全不同的重試**,很容易被混為一談。而「整個失敗」也不是一種狀態,而是兩種:被擋下的 `"failed"`,和送不出去被丟進死信的 `"dead_lettered"`。

下面照著訂單流經系統的路徑講。

## 庫存保留怎麼運作(`orderflow/inventory.py`)

`Inventory.reserve(order)`(`inventory.py:54`)的行為分三種情況:

- **已有且未過期** → 直接回傳原本的 reservation(`inventory.py:66`)。這就是「冪等」:同一筆訂單重跑,不會重複扣庫存,拿到的是同一個保留。所以「重跑訂單」本身**不是**重試,是冪等回放。
- **已有但已過期** → 用當前 catalog 重建一份,並把 `reprice_required=True`(`inventory.py:68-71`)。過期判定看 `now - created_at > RESERVATION_TTL_SECONDS`(`inventory.py:39-41`)。重建的意義是:舊的單價快照可能已經不準,所以標記「必須重新計價」。
- **全新** → 直接建一份(`inventory.py:73-75`)。

真正建立保留的 `_build`(`inventory.py:93`)有個關鍵設計:**先全部驗證,再一次提交**。第一個迴圈把每一行都查一遍(SKU 存在嗎、庫存夠嗎),全部通過後,第二個迴圈才真的去扣庫存。這保證「一筆保留失敗時,不會留下扣一半的庫存要善後」(對應 `inventory.py:94-95` 的註解)。所以**保留階段失敗 = 一顆庫存都沒扣**,不需要 release。

`release(order_id)`(`inventory.py:77`)是反向操作:把每一行的數量加回 catalog、刪掉保留紀錄。這只在 dead-letter 時被呼叫,下面會講到。

**槓桿**:`RESERVATION_TTL_SECONDS = 120`(`config.py:4`)。調大 → 保留活更久、更不會過期重建、更少觸發 reprice;調小 → 更常重建、更常標記 `reprice_required`。

## 兩層不同的重試

這是最容易搞混的地方——請務必分開看:

**第一層:store 寫入的樂觀鎖重試**(`inventory.py:127` 的 `_put_with_retry`)。底層 `VersionedStore` 每筆紀錄有版本號,寫入時要帶對版本,不然丟 `VersionConflict`(`store.py:41-44`)。`_put_with_retry` 會重讀版本、重試,最多 `_PUT_ATTEMPTS = 3` 次(`inventory.py:21`),**沒有 backoff**,失敗到底就把 `VersionConflict` 拋出去。這是併發寫入用的,跟「訂單重試」是兩回事。

**第二層:dispatch 的送貨重試**(`orderflow/dispatch.py:52`)。這才是一般講的「訂單重試」。它最多試 `MAX_DISPATCH_ATTEMPTS = 3` 次(`config.py:6`),**只重試 `RetryableError`**(即 `CarrierTimeout`、`CarrierUnavailable`),每次之間用指數退避:`BASE_RETRY_DELAY_MS * 2^(attempt-2)` 再加一個依 `order_id` 決定的 0–99ms jitter(`dispatch.py:44-49`)。所以第 2 次前等 ~200ms、第 3 次前等 ~400ms,第 1 次不等。三次全失敗才拋 `DispatchExhausted`(`dispatch.py:71`)。

| | store 寫入重試 | dispatch 送貨重試 |
|---|---|---|
| 觸發 | `VersionConflict` | `CarrierTimeout` / `CarrierUnavailable` |
| 次數 | `_PUT_ATTEMPTS=3` | `MAX_DISPATCH_ATTEMPTS=3` |
| 退避 | 無 | 指數 + jitter |
| 用完之後 | 拋 `VersionConflict` | 拋 `DispatchExhausted` → 死信 |

**槓桿**:`MAX_DISPATCH_ATTEMPTS` 調大 → 更晚放棄、更晚 dead-letter;`BASE_RETRY_DELAY_MS` 調大 → 每次等更久。

## 一筆訂單什麼時候會「整個失敗」

沒被成功 `"dispatched"` 的訂單,會落到兩種終局 receipt 之一,兩者對庫存的處置完全不同:

**一、`"failed"`——被 `FatalError` 當場擋下,連 dispatch 都不會跑。** 觸發點有兩處:

- **Ingest 驗證失敗**(`ingest.py:parse_order`,丟 `ValidationError`):缺 `order_id`、`region` 不是 `domestic`/`offshore`、沒有任何 line、line 缺 `sku`、`quantity` 不是正整數(`ingest.py:28-46`)。在 `pipeline.py:47-49` 被接住。
- **保留失敗**:SKU 不在 catalog(`UnknownSku`,`inventory.py:100`),或庫存不足(`InsufficientStock`,`inventory.py:102`)。在 `pipeline.py:53-54` 被接住。

因為 `FatalError` 依定義**不重試**(`errors.py:12`),這類訂單立刻失敗。又因為保留是「先驗證再提交」,**沒有任何庫存被扣**。實例:對 stock=2 的 `ANVIL` 下單 5 個,回傳 `status="failed"`,而且 dispatch 從沒被呼叫(`tests/test_pipeline.py:41-49` 驗證 `calls == []`)。

**二、`"dead_lettered"`——保留成功、送貨卻怎麼試都失敗。** dispatch 三次都吃到 `RetryableError`,拋出 `DispatchExhausted`,在 `pipeline.py:61-67` 被接住,接著做三件事:**release 把庫存還回去、把訂單推進 `dead_letters` 佇列、回傳 `"dead_lettered"` receipt**(注意是 receipt,不是例外)。實例:對 `ANVIL` 下單 2 個、carrier 每次都 timeout,最後 `status="dead_lettered"`、死信佇列 +1、而且 `ANVIL` 庫存從被扣的 0 還原回 2(`tests/test_pipeline.py:51-63`)。

所以要精準回答你的問題:「整個失敗」若指**被拒收**,是 `"failed"`(沒扣庫存);若指**收了卻送不出**,是 `"dead_lettered"`(扣了再還)。分辨兩者的關鍵,就是那條 `FatalError` vs `RetryableError` 的界線(`errors.py` 的整個分類就是為這件事存在)。

順帶一提:`price()`(`pricing.py:48`)是純算術、不會拋錯,所以計價**不是**失敗點——它只是照著保留當下的單價快照算總額。

## 邊界:並不是「每種失敗都會回成 receipt」

pipeline 的 docstring 說失敗都會變成 receipt,但這只在它描述的兩條路徑上成立。有幾條路會讓例外**直接逸出 `process()`**,而不是回傳 receipt——如果你要完整掌握失敗行為,這幾點最值得記:

- **[inferred] 保留提交階段的 `VersionConflict`**:`reserve` 那層 `try/except` 只接 `FatalError`(`pipeline.py:53`),但 `_put_with_retry` 用完 3 次會拋 `VersionConflict`(`RetryableError`,不是 `FatalError`)。它會穿過 pipeline 逸出。單執行緒、in-memory 的現況幾乎踩不到(版本永遠是剛讀的),但 store 本身是為併發樂觀鎖設計的(`store.py:1-6`),多寫入者共用時這條路就真實存在。`release()` 還庫存那筆寫入(`inventory.py:90`)是**直接 `put`、沒包重試**,同理在併發下也可能拋 `VersionConflict` 而逸出。
- **[inferred] `send` 丟出 `FatalError`**:dispatch 迴圈只接 `RetryableError`(`dispatch.py:67`),pipeline 只接 `DispatchExhausted`(`pipeline.py:61`)。carrier callback 若丟任何非 `RetryableError` 的例外,一樣直接逸出。
- **[inferred] 送貨是 at-least-once**:重試是重複呼叫 `send`(`dispatch.py:65`)。如果 carrier 已部分受理才回 timeout,重試可能讓同一筆訂單被送兩次——這裡保證的是「不會靜默丟單」,不是「不會重複送」。

換句話說:別假設 `process()` 一定回傳 `failed`/`dispatched`/`dead_lettered` 三者之一;絕大多數情況會,但上面幾條路會拋例外。

---

**Sources and gaps**
- 保留與重試主體:`orderflow/inventory.py:54-136`、`orderflow/store.py:29-47`、`orderflow/config.py:4`。
- dispatch 重試與退避:`orderflow/dispatch.py:44-71`、`orderflow/config.py:6-9`。
- 失敗分類與路徑:`orderflow/errors.py`、`orderflow/pipeline.py:44-74`、`orderflow/ingest.py:25-49`。
- 行為佐證:`tests/test_pipeline.py`(insufficient-stock 不重試、dead-letter 後還原庫存、backoff、過期重建 reprice)。
- 未實測執行,僅靜態追蹤:上述三條 `[inferred]` 逸出/at-least-once 路徑沒有測試覆蓋,是讀碼推得;若要確認,值得補一個「保留階段 `VersionConflict` 會怎樣」的測試。
- 此 workspace 尚無 `mental/` canonical 模型,以上皆為直接讀碼所得;若想把這套失敗語意固化成可重用模型,可用 `$build`。

Context: engineer lens · map,mechanism,scenario,evidence · standard —— 依「這是 repository 問題」的預設,加上你「想搞懂失敗行為」的目標,把重心放在機制與失敗情境;想深挖某一條路徑或改用其他視角,跟我說或用 `lens= views= detail=` 調整即可。