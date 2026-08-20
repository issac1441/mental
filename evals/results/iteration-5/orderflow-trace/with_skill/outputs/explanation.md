一筆訂單的完整生命週期都由 `Pipeline.process(raw)` 這一個進入點驅動(`orderflow/pipeline.py:44`),它固定跑四個階段:**解析 → 訂庫存 → 計價 → 出貨**(ingest → reserve → price → dispatch)。每筆訂單最後都會拿到一張 `Receipt`,狀態只有三種:`dispatched`(成功出貨)、`failed`(解析或訂庫存時遇到致命錯誤,當場失敗、不重試)、`dead_lettered`(出貨重試用盡,庫存已退回、進死信佇列)。階段順序是刻意的:計價一定排在訂庫存之後,因為「這筆訂單實際會被收多少錢」的單價快照是由 reservation 凍結的,不是來自原始訂單。

下面沿著執行路徑走一遍。

```
raw dict
  │  parse_order            ── ValidationError ─────────────► Receipt("failed")
  ▼
 Order
  │  inventory.reserve      ── UnknownSku / InsufficientStock ► Receipt("failed")
  ▼
 Reservation (凍結庫存 + 單價快照)
  │  price                  (純算術,不會丟例外)
  ▼
 Quote
  │  dispatch (retry ≤ 3)   ── DispatchExhausted ──► release 庫存 ► Receipt("dead_lettered")
  ▼
 Receipt("dispatched", carrier, total_cents)
```

## 第一站:解析與驗證(`ingest.py:25`)

`parse_order(raw)` 把外部 dict 轉成不可變的 `Order`(內含多個 `Line`)。它檢查四件事:`order_id` 必須是非空字串、`region` 只能是 `domestic` 或 `offshore`(預設 `domestic`)、`lines` 不可為空、每個 line 的 `sku` 是字串且 `quantity` 是正整數。任何一項不符就丟 `ValidationError`。

`ValidationError` 屬於 `FatalError`(`errors.py:20`),在 `process` 的第一個 `try` 被接住(`pipeline.py:47`),直接回 `Receipt(status="failed")`。此時還沒碰庫存,所以什麼都不用回滾。

## 第二站:訂庫存 + 價格快照(`inventory.py:54`)

`Inventory.reserve(order)` 是這條流程的重心,它一次凍結兩樣東西:**要扣的庫存**和**要計價用的單價**。機制有三個要點:

- **先驗證、後扣帳**(`_build`,`inventory.py:93`):第一個迴圈把每一行都查一遍——目錄裡沒有這個 SKU 就丟 `UnknownSku`,庫存不足就丟 `InsufficientStock`(兩者都是 `FatalError`)。**全部通過後**第二個迴圈才真的去扣 `stock` 並記下 `unit_price_cents` / `weight_g`。所以訂庫存失敗時,不會留下扣一半的庫存。
- **價格是在這裡定格的**:`ReservedLine` 存下當下目錄的 `price_cents`(`inventory.py:117`),之後計價只看這份快照,不再回頭看目錄或原始訂單。
- **對同一個 order_id 具冪等性**:若這個 order_id 已有 reservation 且未過期,直接回傳舊的、不重複扣庫存(`inventory.py:64`)。若已過期,就用**現在**的目錄價重建一份,並把 `reprice_required=True`(`inventory.py:68`)——因為單價可能變了。

同樣地,`reserve` 的 `FatalError` 在 `pipeline.py:53` 被接住 → `Receipt("failed")`。

## 第三站:計價(`pricing.py:48`)

`price(reservation)` 是純算術,不丟例外,規則有四條(`pricing.py` 檔頭寫得很清楚):

1. **商品小計** = Σ(訂購量 × 快照單價)。
2. **折扣最多一個、不疊加**:`_select_discount`(`pricing.py:72`)挑出所有「小計 ≥ 門檻」的規則,取 `priority` 最高的那個。目前有 `spring-30`(30%,門檻 5000_00,priority 20)和 `loyalty-10`(10%,門檻 0,priority 10)。
3. **稅只課在折扣後的商品金額上**,運費永遠不課稅(`TAX_RATE = 0.05`)。
4. **運費是定額,但免運看的是「折扣前」小計**:小計 ≥ `FREE_SHIPPING_THRESHOLD_CENTS`(8000_00)就免運,否則收 `FLAT_SHIPPING_CENTS`(120_00)。折扣不影響免運資格。

值得注意:`process` 其實**不去讀** `reprice_required` 這個旗標。因為計價「一律」從 reservation 快照算(`pipeline.py:57`),重建過的 reservation 已帶著新價,重新計價自然就發生了。旗標目前只是給外部/測試看的資訊(`tests/test_pipeline.py:86`),不改變 pipeline 自身的控制流。

## 第四站:出貨與重試(`dispatch.py:52`)

`dispatch` 先選承運商(`choose_carrier`,`dispatch.py:36`):`offshore` 一律走 `air`;`domestic` 則按總重量,`≤ POST_MAX_WEIGHT_G`(2000g)走 `post`,超過走 `freight`。重量用的是 reservation 裡凍結的 `weight_g`。

接著是一個最多 `MAX_DISPATCH_ATTEMPTS`(3)次的迴圈:呼叫注入進來的 `send(carrier, order)`,成功就回 `DispatchResult`。**只有 `RetryableError`(如 `CarrierTimeout`、`CarrierUnavailable`)會被重試**;重試前先 `sleep`,延遲由 `backoff_ms` 決定——`BASE_RETRY_DELAY_MS × 2^(attempt-2)` 再加上一個由 order_id 算出的 0–99ms 固定抖動(`dispatch.py:44`,指數退避)。三次都失敗就丟 `DispatchExhausted`。

`process` 在 `pipeline.py:61` 只接 `DispatchExhausted`:退回庫存(`inventory.release`,把 stock 加回目錄並刪掉 reservation)、把訂單推進 `dead_letters`、回傳 `Receipt("dead_lettered")`。**成功出貨則不退庫存**——貨賣掉了,扣掉的庫存就該留著(`pipeline.py:69`)。

## 一個具體例子(happy path,對照 `test_pipeline.py:22`)

訂單 `o-1`,3 × `WIDGET`(單價 3000_00、重 500g):

- 小計 = 9000_00 → 符合 `spring-30`(9000_00 ≥ 5000_00,priority 20 勝過 loyalty-10)→ 折 2700_00 → 折後 6300_00。
- 稅 = round(6300_00 × 0.05) = 315_00。
- 運費:**折扣前** 9000_00 ≥ 8000_00 → **免運**(0)——即使折後的 6300_00 低於門檻。
- 總計 = 6300_00 + 315_00 + 0 = **6615_00**。
- 承運商:domestic、總重 1500g ≤ 2000g → `post`。

## 三個容易誤解的地方(預測時最會踩到的)

- **免運看折扣前、不是折扣後**:上例折後只有 6300_00 卻仍免運,就是這條規則(`pricing.py:57`,`test_pipeline.py:32` 專門釘住它)。
- **冪等只保護「庫存」,不保護「出貨」**:重跑一個仍在有效期內的 order_id 不會重複扣庫存,但 `process` 之後照樣會再跑一次 `dispatch` → 對承運商**再送一次**(`pipeline.py:60` 無條件呼叫)。reservation 層不會重複下單,但 dispatch 會重送。
- **不是所有錯誤都會變成漂亮的 Receipt**。`process` 在 dispatch 那段只接 `DispatchExhausted`。若 `send` 丟出**非** retryable 的錯誤,它會穿過 dispatch、也穿過 `process`,變成未捕捉的例外往外拋。另外,`reserve` 內部的 `VersionConflict` 若重試 3 次仍失敗(`inventory.py:133`),因為它是 `RetryableError` 而非 `FatalError`,也**不會**被 `except FatalError` 接住而外拋——不過這在目前這個單執行緒、記憶體版 store 下實務上不會發生,得有並發寫入者才觸得到。

## 可調的旋鈕(都在 `config.py`,除折扣規則外)

- `RESERVATION_TTL_SECONDS`(120):reservation 存活/冪等的時間;調長 → 重建與重新計價變少。
- `MAX_DISPATCH_ATTEMPTS`(3)、`BASE_RETRY_DELAY_MS`(200):放棄前的重試次數與退避基準;調高 → 更晚才進死信。
- `FREE_SHIPPING_THRESHOLD_CENTS`、`FLAT_SHIPPING_CENTS`、`TAX_RATE`、`POST_MAX_WEIGHT_G`:免運門檻、運費、稅率、post/freight 分界。
- `DISCOUNT_RULES`(`pricing.py:32`):每條規則的 `priority` 決定誰勝出、`min_subtotal_cents` 決定何時觸發。

---

**Sources and gaps**
- 追蹤路徑:`orderflow/pipeline.py:44`(進入點與三種結局)、`ingest.py:25`(解析)、`inventory.py:54,93,127`(訂庫存/先驗後扣/樂觀鎖重試)、`pricing.py:48,72`(計價與選折扣)、`dispatch.py:36,44,52`(選承運商/退避/重試迴圈)、`config.py`、`errors.py`。
- 行為佐證:`tests/test_pipeline.py`(happy path 6615_00、免運看折扣前、缺貨不重試、死信退庫存、退避抖動、過期重建 reprice)。
- 我用**靜態閱讀**追出因果,未實際執行程式;上面帶數字的結局有測試背書,未被測試覆蓋的兩個外拋邊界(dispatch 非 retryable 例外、reserve 用盡的 `VersionConflict`)是讀碼推得,標為需並發才可達。
- 目前 workspace 沒有 `mental/` canonical model,以上皆直接讀 source。若想把這套流程固化成可重用、可累積的模型,可用 `$build`(我不會自行建檔)。

Context: engineer lens · map,mechanism,scenario,evidence · standard — 依 repository 追蹤請求選定;想更深挖某一站(例如把 `_put_with_retry` 的樂觀鎖或死信補償邏輯攤開),或換個視角(如 `operator` 看維運、`pm` 看功能),調整 `lens=` `views=` `detail=` 或直接說即可。