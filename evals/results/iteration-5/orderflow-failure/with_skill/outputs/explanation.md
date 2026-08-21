I have a complete picture of the codebase. Let me give you the answer.

---

這個 pipeline 的骨幹是四個依序執行的階段:**ingest → reserve → price → dispatch**(`orderflow/pipeline.py:1-15`)。你問的「保留、重試、失敗」其實牽涉**兩個彼此獨立的重試迴圈**,以及一個**不對稱的失敗處理**。一筆訂單正常只會拿到三種 `Receipt` 之一:`dispatched`(成功)、`failed`(遇到 `FatalError`,立即失敗、不重試)、`dead_lettered`(dispatch 重試用盡,先釋放庫存再進死信佇列)。但關鍵重點是:**只有 dispatch 階段的「可重試失敗」有安全網;保留/儲存階段若把可重試的 `VersionConflict` 重試用盡,它會直接以例外往外拋,連 `Receipt` 都不會產生。** 底下依執行路徑逐段說明。

## 保留(reservation)是怎麼運作的

保留這一步同時凍結兩件事:**要扣的庫存**與**要收的單價快照**(`inventory.py:1-9`)。它以 `reservation/{order_id}` 為 key,有三個行為:

- **同單冪等**:同一個 `order_id` 在保留還「活著」時重跑,直接回傳既有保留,不會重複扣庫存(`inventory.py:62-67`)。
- **TTL 過期就重建並重新定價**:`expired()` 用 `now - created_at > RESERVATION_TTL_SECONDS`(預設 120 秒)判斷(`inventory.py:39-41`、`config.py:4`)。過期後會依**當下**型錄重建保留,並把 `reprice_required=True`(`inventory.py:68-71`)。因為 pipeline 一律從保留快照定價(`pipeline.py:57`),重建後的保留自然就用新價;`reprice_required` 只是個訊號,`process()` 目前並沒有真的去讀它判斷分支——重新定價是「因為 `price()` 永遠讀最新快照」而自動發生的。所以**同一筆訂單跨過 TTL 後,總價可以合法地改變**。
- **先全驗證、再逐行扣庫存**(`_build`,`inventory.py:93-125`):第一個迴圈把每一行都查過(型錄查無 → `UnknownSku`;庫存不足 → `InsufficientStock`),第二個迴圈才真正扣庫存並擷取單價/重量。這個「先驗證」設計的用意,是讓**驗證失敗時完全不動到庫存**。

## 兩個獨立的重試迴圈

| 重試迴圈 | 位置 | 觸發的錯誤 | 次數上限 | 用盡後 |
|---|---|---|---|---|
| **儲存寫入重試** | `inventory._put_with_retry`(`inventory.py:127-136`) | `VersionConflict`(樂觀鎖版本不符,`store.py:29-47`) | `_PUT_ATTEMPTS = 3`(寫死在 `inventory.py:21`) | **重新拋出 `VersionConflict`** |
| **派送重試** | `dispatch()`(`dispatch.py:52-71`) | 只有 `RetryableError`(`CarrierTimeout`、`CarrierUnavailable`…) | `MAX_DISPATCH_ATTEMPTS = 3`(`config.py:7`) | 拋出 `DispatchExhausted` |

派送重試用的是指數退避:`backoff_ms = BASE_RETRY_DELAY_MS × 2^(attempt-2) + jitter`,jitter 是 `crc32(order_id) % 100`(每單固定、0–99ms)(`dispatch.py:44-49`)。所以在承運商全掛的情況下,第 2 次約等 200–299ms、第 3 次約等 400–499ms,大約 0.6–0.8 秒後才會進死信。派送前的承運商選擇是純規則:offshore 一律空運,國內則以總重跟 `POST_MAX_WEIGHT_G`(2000g)比,決定 post 或 freight(`dispatch.py:36-41`)。

**可調的槓桿與方向**:`RESERVATION_TTL_SECONDS` 調大 → 保留活得久、重建/重新定價變少,但庫存被綁住更久;`MAX_DISPATCH_ATTEMPTS` 調大 → 更晚放棄、進死信前延遲更長;`BASE_RETRY_DELAY_MS` 調大 → 每次派送間隔更長;`_PUT_ATTEMPTS` 調大 → 更能容忍並發寫入衝突,但這條路徑用盡後的例外沒人接(見下)。

## 一筆訂單會走到哪些結局

「整個失敗」= 訂單沒送出去。這會發生在下面幾種情況,而且**是以「整筆訂單」為單位、沒有部分出貨**:

| 結局 | 觸發條件 | 重試? | 庫存 |
|---|---|---|---|
| `failed`(有 Receipt) | ingest 的 `ValidationError`(缺 `order_id`、region 不合法、沒有 line、sku 空、數量非正整數;`ingest.py:25-49`),或 reserve 的 `UnknownSku` / `InsufficientStock`(`pipeline.py:46-54`) | 否,立即失敗 | 未動用(驗證在扣庫存之前) |
| `dead_lettered`(有 Receipt) | dispatch 連續 3 次都是 `RetryableError`,拋 `DispatchExhausted`(`pipeline.py:59-67`) | 是,退避重試 3 次 | **已釋放**(`release()` 把庫存加回型錄) |
| **未捕捉的例外(沒有 Receipt)** | reserve/release 階段 `VersionConflict` 重試用盡;或 `send` 拋出非 `RetryableError` 的例外 | 見下 | **可能外洩** |

前兩列就是「有禮貌」的失敗:呼叫端拿到的是 Receipt,不是例外。第三列才是最需要注意的部分。

**要先破除一個直覺**:你可能以為多行訂單裡「壞的那一行失敗、好的照樣出貨」——不是。`_build` 只要在任何一行踩到 `UnknownSku`/`InsufficientStock` 就整個拋出,**整筆訂單變成 `failed`**,是全有或全無(`inventory.py:96-106`;測試 `test_insufficient_stock_fails_without_retry`,`test_pipeline.py:41-49`)。

## 最容易誤判的邊界:失敗處理是不對稱的

dispatch 的 docstring 說它「never silently drops an order」(`dispatch.py:1-7`),很容易讓人以為整個 pipeline 對「可重試失敗」都有安全網。**實際上那個安全網只在 dispatch 這一段。** 保留/儲存階段沒有對應的保護:

- **`VersionConflict` 會逃出 pipeline**:`_put_with_retry` 重試 3 次後**重新拋出 `VersionConflict`**(`inventory.py:132-133`)。而 `VersionConflict` 是 `RetryableError`,**不是** `FatalError`(`errors.py:32`)。`pipeline.process` 在 reserve 外面只 `except FatalError`(`pipeline.py:53`),所以這個例外不會被接住,會直接往外拋——呼叫端拿到的是**例外,而不是 `failed` 或 `dead_lettered` 的 Receipt**。這需要有並發寫入者對同一個型錄/保留 key 造成版本衝突才會發生(單執行緒的測試路徑碰不到);此結論是我**逐路徑追出來的,沒有實際跑並發驗證**。

- **而且可能留下外洩的庫存**:`_build` 的註解說「先驗證所有行,失敗時不留下要回捲的部分庫存」(`inventory.py:94-95`)。這句話**只對「驗證失敗」成立**。在第二個「逐行扣庫存」迴圈裡(`inventory.py:108-120`),若第一行已扣成功並提交、第二行的 `_put_with_retry` 才用盡重試拋出 `VersionConflict`,此時第一行的庫存已經被扣掉、卻**沒有任何 `reservation/{order_id}` 記錄可供 `release()` 回補**——庫存就這樣漏掉。**這是程式碼與其自身註解之間的衝突**:註解宣稱的「不留部分庫存」不成立於並發下的提交階段。

- **兩個附帶點**:(1) 若注入的 `send` 拋出的是 `FatalError`(或任何非 `RetryableError`),dispatch 不會接(它只 catch `RetryableError`,`dispatch.py:67`),會一路逃出 `except DispatchExhausted`,同樣變成未捕捉例外。(2) 死信路徑呼叫的 `release()` 用的是**沒有重試的**直接 `put`(`inventory.py:90`),並發衝突時也會拋例外,連 `dead_lettered` 這條「優雅」路徑都可能在釋放庫存時中斷。

實務上的收斂結論:**「可重試失敗」只有在 dispatch 階段才會被轉成乾淨的 `dead_lettered` 結果;在保留/儲存階段,可重試失敗反而是最不優雅的——它會拋例外、可能漏庫存。** 如果你要強化失敗行為,第一個該補的洞就是讓 `reserve()` 的 `VersionConflict` 用盡後也能落到某種 Receipt(並在部分提交時回捲)。

---

**Sources and gaps**
- 流程與失敗語意:`orderflow/pipeline.py:1-15`(docstring)、`:44-74`(`process`,含 `except FatalError` 於 `:53`、`except DispatchExhausted` 於 `:61`)。
- 保留機制:`orderflow/inventory.py:39-41`(TTL)、`:54-75`(`reserve`/冪等/重建)、`:77-91`(`release`,注意 `:90` 無重試)、`:93-125`(`_build` 先驗證後扣庫存)、`:127-136`(`_put_with_retry`)、`:21`(`_PUT_ATTEMPTS`)。
- 重試/派送:`orderflow/dispatch.py:36-41`(選承運商)、`:44-49`(退避+jitter)、`:52-71`(重試迴圈)。
- 錯誤分類:`orderflow/errors.py:12`(`FatalError`)、`:16`(`RetryableError`)、`:32`(`VersionConflict` 屬 Retryable——不對稱的根因)。
- 樂觀鎖:`orderflow/store.py:29-47`。槓桿常數:`orderflow/config.py:4,7,10`。驗證規則:`orderflow/ingest.py:25-49`。定價一律讀保留快照:`orderflow/pricing.py:48`。
- 佐證測試:`tests/test_pipeline.py:41-49`(缺貨不重試)、`:51-63`(死信釋放庫存)、`:71-86`(過期重建+reprice)。
- **未驗證的缺口**:`VersionConflict` 逃逸與部分扣庫存外洩,是靜態追蹤而非實際並發執行所得;此 repo 目前沒有 `mental/` canonical 模型,以上屬我從程式碼推得的解讀。若要把這套失敗行為(尤其那個不對稱)固化成團隊共識模型,可用 `$build` 產出 canonical 版本;我不會自行建立檔案。

本次以**工程師視角**、聚焦**元件關係、因果機制、實際情境與程式碼佐證**、**標準深度**說明,依據是「這是 repository 內的失敗行為追蹤問題」;想更深入(例如把並發下的外洩情境展開)、或改用其他視角,直接說即可。