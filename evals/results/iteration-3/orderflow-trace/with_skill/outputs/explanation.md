程式碼與關鍵的「否定型」宣稱都已驗證完畢。以下依實際執行路徑說明整個流程。

---

這個 codebase 的核心是一條**四段式訂單管線**,唯一入口是 `Pipeline.process(raw: dict)`(`pipeline.py:44`):一個原始 dict 進去,一張 `Receipt` 出來。四段按固定順序跑——**收單 ingest → 訂位扣庫存 reserve → 計價 price → 出貨 dispatch**(`pipeline.py:3`)——由 `Pipeline` 這個協調者串起,每段只做一件事。最後的 `Receipt.status` 只會是三種之一:`dispatched`(成功出貨)、`failed`(收單或庫存階段就被擋、不重試)、`dead_lettered`(出貨重試用盡後放棄並補償)。

資料沿路變形:`raw dict → Order → Reservation(+ Quote)→ DispatchResult → Receipt`。下面順著這條路走一遍,並用測試裡的 o-1 訂單(WIDGET × 3)當實例貫穿。

## 1. 收單 ingest — 把 dict 變成受檢的 Order

`parse_order(raw)`(`ingest.py:25`)做純驗證,通過就回傳 frozen 的 `Order(order_id, region, lines)`,失敗就丟 `ValidationError`。檢查項:`order_id` 必填且為字串、`region` 預設 `domestic` 且只能是 `{domestic, offshore}`、至少一條 line、每條 line 要有字串 `sku` 與正整數 `quantity`(`ingest.py:27-47`)。

`ValidationError` 屬於 `FatalError`(`errors.py:20`),所以 `process` 一攔到就直接回 `failed` 收據、**不進後面任何一段**(`pipeline.py:46-49`)。

## 2. 訂位扣庫存 reserve — 一次凍結「庫存」與「單價」

`Inventory.reserve(order)`(`inventory.py:54`)是整條線最有狀態的一段。它替訂單凍結兩樣東西:**要消耗的庫存**,以及**日後計價要用的單價快照**。三條分支:

- **已有且未過期** → 直接回傳舊的訂位(以 `order_id` 為 key 的冪等性,重送同一筆不會重覆扣庫存)(`inventory.py:64-67`)。
- **已有但過期** → 用目前 catalog 重建,並標記 `reprice_required=True`(`inventory.py:68-71`)。
- **全新** → 直接建立(`inventory.py:73-75`)。

實際建立在 `_build`(`inventory.py:93`),採**先全查、再提交**:先把每條 line 都查一遍,查不到 SKU 丟 `UnknownSku`、庫存不足丟 `InsufficientStock`(`inventory.py:96-106`);全部過關後才逐條把 catalog 庫存扣掉,並擷取當下的 `price_cents` 與 `weight_g` 存進 `ReservedLine`(`inventory.py:108-120`)。這樣設計是為了「失敗時不留半套已扣的庫存」。`UnknownSku`、`InsufficientStock` 都是 `FatalError`,同樣讓 `process` 回 `failed`、不重試(`pipeline.py:51-54`;對應 `test_insufficient_stock_fails_without_retry`)。

> o-1 實例:catalog 的 WIDGET 是 `price 3000_00 / stock 10 / weight 500`。訂位後庫存 10→7,擷取單價 3000_00。

底層存取都走 `VersionedStore`(`store.py`)——每筆紀錄帶版本號,寫入要附上讀到的版本,不符就丟 `VersionConflict`(可重試型);`_put_with_retry` 會重讀版本、最多試 3 次(`inventory.py:127-137`)。

## 3. 計價 price — 一律用訂位快照算,不看原始訂單

`process` 無條件呼叫 `price(reservation)`(`pipeline.py:56-57`)。計價**只吃訂位快照的單價**,不碰原始訂單價格,因為帳單金額以訂位當下凍結的價為準(`pricing.py:1-14`)。規則四步(`pricing.py:48-69`):

1. **商品小計** = Σ(訂位數量 × 擷取單價)。
2. **折扣**:最多套一個、不疊加;在門檻達標的規則中挑 **priority 最高**(不是 percent 最高)的那個(`_select_discount`,`pricing.py:72-78`)。目前兩條規則:`spring-30`(30%、門檻 5000_00、priority 20)與 `loyalty-10`(10%、門檻 **0**、priority 10)(`pricing.py:32-35`)。因為 loyalty-10 門檻是 0,實務上**每筆訂單至少吃到 10% off**,`discount` 幾乎不會是 None。
3. **稅** = `round(折扣後小計 × TAX_RATE)`,只課在折扣後商品金額,**運費不課稅**(`pricing.py:55`)。
4. **運費**:折扣**前**小計 ≥ `FREE_SHIPPING_THRESHOLD_CENTS` 就免運,否則收統一 `FLAT_SHIPPING_CENTS`(`pricing.py:57-60`)。

> o-1 實例:小計 = 3 × 3000_00 = **9000_00**;≥ 5000_00 → 套 spring-30,扣 `9000_00 × 30 // 100 = 2700_00` → 折後 **6300_00**;稅 = `round(6300_00 × 0.05) = 315_00`;運費:折扣前 9000_00 ≥ 8000_00 → **免運 0**;總計 = 6300_00 + 315_00 + 0 = **6615_00**(正是 `test_pipeline.py:30` 斷言的值)。

## 4. 出貨 dispatch — 選物流、有上限地重試,失敗就退信

`dispatch(order, reservation, send)`(`dispatch.py:52`)先選物流商:離岸(offshore)一律 `air`;國內則看總重,`≤ POST_MAX_WEIGHT_G` 走 `post`、超過走 `freight`(`choose_carrier`,`dispatch.py:36-41`)。接著跑最多 `MAX_DISPATCH_ATTEMPTS` 次的迴圈呼叫外部 `send`:

- 成功 → 回 `DispatchResult(carrier, attempts)`。
- 丟 `RetryableError`(如 `CarrierTimeout`/`CarrierUnavailable`)→ 記下錯誤、重試;第 2 次起先退避 `backoff_ms/1000` 秒(`dispatch.py:61-68`)。
- **只重試 `RetryableError`**;其他例外(含 `FatalError`)直接往外拋(`dispatch.py:67`)。

退避是**指數式 + 每單固定抖動**:`BASE_RETRY_DELAY_MS × 2^(attempt-2) + (crc32(order_id) % 100)` 毫秒(`dispatch.py:44-49`)。抖動由 `order_id` 決定,所以同一筆訂單的延遲可重現(`test_backoff_doubles_with_stable_jitter`)。

重試用盡 → 丟 `DispatchExhausted`;`process` 攔到後做**補償**:`release` 訂位把庫存還回 catalog、把訂單記進 `dead_letters`、回 `dead_lettered` 收據(`pipeline.py:59-67`;對應 `test_dead_letter_after_exhausted_retries_releases_stock`)。全程走完成功則回 `dispatched` 收據,帶 `carrier` 與 `total_cents`(`pipeline.py:69-74`)。

> o-1 實例:國內、總重 3×500 = 1500g ≤ 2000 → `post`;`send` 首次成功 → `Receipt(o-1, dispatched, carrier=post, total_cents=6615_00)`。

## 可調的旋鈕(全在 `config.py`,金額都是整數分)

| 常數 | 值 | 改了會怎樣 |
|---|---|---|
| `RESERVATION_TTL_SECONDS` | 120 | 訂位存活秒數;過了就重建並標 `reprice_required` |
| `MAX_DISPATCH_ATTEMPTS` | 3 | 出貨總嘗試次數;用完就 dead-letter |
| `BASE_RETRY_DELAY_MS` | 200 | 第 2 次嘗試前的基礎退避,之後每次加倍 |
| `TAX_RATE` | 0.05 | 對折扣後商品小計課的稅率(運費不課) |
| `FREE_SHIPPING_THRESHOLD_CENTS` | 8000_00(80萬分) | 折扣**前**小計達此值免運 |
| `FLAT_SHIPPING_CENTS` | 120_00 | 未達免運門檻的統一運費 |
| `POST_MAX_WEIGHT_G` | 2000 | 國內包裹 ≤ 此重走 post,否則 freight |

## 幾個容易誤解的地方

- **免運看「折扣前」、課稅看「折扣後」——基準不同。** 折扣可能把折後金額壓到門檻以下,但只要折扣前 ≥ 8000_00 仍免運(`pricing.py:57`,有 `test_free_shipping_uses_pre_discount_subtotal` 專門守著)。別假設「我實付多少決定免不免運」。

- **別以為訂位過期就會自動把庫存還回去。**〔inferred〕過期重建路徑直接呼叫 `_build`(會再扣一次庫存)並覆寫紀錄,中間**沒有**歸還舊的保留量(`inventory.py:68-71`);全庫 `release` 只在 dead-letter 那條路徑被呼叫(`pipeline.py:62`),也沒有 TTL 掃描器。因此同一筆訂單過期後被重新處理,catalog 會被扣第二次而舊量未還——看起來像漏了補償。這是 in-memory fixture,無法確認是否刻意,先當作要注意的邊界。

- **`reprice_required` 有設定但沒人讀。**〔conflict〕docstring 說設這旗標是「讓 pipeline 知道要重算總額」(`inventory.py:59`),但 pipeline 其實是「不看旗標、每次都用訂位快照重算」(`pipeline.py:56-57`)。因為重建後的訂位本就帶最新價,永遠重算剛好也對,所以旗標目前只是資訊性的、沒有實際分支(全庫搜尋只有測試與 docstring 引用它)。是文件意圖與實作的落差,不是計價錯誤。

- **出貨時的非重試型錯誤會直接冒出、且不補償。** `dispatch` 只攔 `RetryableError`(`dispatch.py:67`),而 `process` 只攔 `DispatchExhausted`(`pipeline.py:59-61`)。若 `send` 丟出 `FatalError`,例外會穿過 `process` 拋給呼叫端,且**訂位不會被 release、庫存仍被佔著**。這在 dispatch 層是刻意的(`dispatch.py:4`),但 pipeline 沒為它補償。

---

**Sources and gaps**
- 進入點與編排:`orderflow/pipeline.py:44-74`(段序與失敗語意 `:1-15`)
- 收單:`orderflow/ingest.py:25-49`;錯誤分類:`orderflow/errors.py:8-40`
- 訂位/庫存:`orderflow/inventory.py:54-137`;儲存層:`orderflow/store.py:29-47`
- 計價:`orderflow/pricing.py:32-78`;可調常數:`orderflow/config.py`
- 出貨/重試:`orderflow/dispatch.py:36-71`
- 行為佐證:`tests/test_pipeline.py`(happy path、免運基準、庫存不足、dead-letter、退避、過期重建)
- 缺口:(1) 過期重建的重覆扣庫存與 (2) `send` 丟 `FatalError` 未補償,兩者是否刻意,現有程式與註解看不出來;(3) 這是 `evals/fixtures/` 下的示範用 codebase,無外部 I/O、store 為記憶體版,行為未必等同正式系統。
- 這個 workspace 尚無 `mental/` 正典模型;上述都是我當下讀碼得到的推論。若想把這套流程固化成可累積、可校正的模型,可用 `$build`(我不會自行建立檔案)。

*Context: engineer lens · map,mechanism,scenario,evidence · standard — 依 repository 預設與「理解整條流程」的目標選定;想更深入某一段、換視角或改深淺,直接說 `lens= views= detail=` 即可。*