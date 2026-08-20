我已讀完 skill 與三份 reference，並直接追了 `orderflow/` 的實際程式碼。以下依「訂單在系統裡的執行路徑」來講。

---

一筆訂單走的是一條**固定四段的流水線**，全部由 `Pipeline.process()` 串起來(`orderflow/pipeline.py:44`):先把原始 dict 解析驗證成 `Order`,再向庫存**預留並凍結一份價格快照**,接著依快照計價,最後交給 carrier 出貨、失敗時做有限次重試。整條線對外只回傳一張 `Receipt`,結局固定三種——`dispatched`(成功)、`failed`(驗證/SKU/庫存等致命錯,不重試)、`dead_lettered`(出貨重試用盡,退還庫存後進死信佇列)。**一個錯誤要不要重試,完全由 `errors.py` 的 `FatalError` / `RetryableError` 分類決定**,這是理解整條線的關鍵樞紐。

整體地圖:

```
raw dict
  → parse_order         (進單驗證)        失敗 → Receipt(failed)
  → Inventory.reserve   (庫存 + 價格快照)  失敗 → Receipt(failed)
  → price               (計價)
  → dispatch            (出貨, 重試 ≤ 3)   用盡 → release + Receipt(dead_lettered)
  → Receipt(dispatched, carrier, total_cents)
```

### 第 1 段:進單與驗證 `parse_order`(ingest.py:25)

把原始 dict 轉成 `Order`,同時擋掉爛資料:`order_id` 必須是非空字串、`region` 只能是 `domestic` 或 `offshore`(預設 `domestic`,ingest.py:31)、至少要有一條 line、每條 line 要有字串 `sku` 和正整數 `quantity`。任何一項不過就丟 `ValidationError`(屬 `FatalError`),`process` 直接回 `Receipt(status="failed")`(pipeline.py:47-49)——**dispatch 這時完全不會執行**。

### 第 2 段:庫存預留 + 凍結價格快照 `Inventory.reserve`(inventory.py:54)

這一段做的不只是扣庫存,它同時把「這張單將被計價的單價」凍結下來。三個重點:

- **冪等**:同一 `order_id` 若已有未過期的預留,直接回傳原本那份(inventory.py:64-67)。重跑同一張單不會重複扣庫存,價格也維持當初快照。
- **兩段式建構**(`_build`, inventory.py:93):先把每條 line **全部驗證完**(找不到 SKU → `UnknownSku`;庫存不足 → `InsufficientStock`,兩者都是 `FatalError`),全數通過後才進第二圈真正扣庫存,並把 `unit_price_cents`、`weight_g` 從 catalog 抄進 `ReservedLine`。「先全驗證、再全提交」保證失敗時不會留下扣一半的庫存(見 inventory.py:94-95 的註解)。
- **過期重建**:TTL 由 `RESERVATION_TTL_SECONDS = 120` 秒控制(config.py:4、inventory.py:39-41)。過期的預留會用**當下** catalog 價格重建,並標記 `reprice_required = True`(inventory.py:68-70),因為凍結的單價可能已經變了。

這一段的致命錯同樣被 `process` 接住回 `failed`(pipeline.py:53-54)。

### 第 3 段:計價 `price`(pricing.py:48)

**從預留快照算,不是從原始訂單算**——計價基準是 reserve 當下凍結的那份單價。規則四條:

1. `subtotal = Σ quantity × unit_price_cents`(pricing.py:49)。
2. **折扣最多一個、不疊加**:取「達到門檻且 `priority` 最高」的那條(pricing.py:72-78)。規則表 `DISCOUNT_RULES`:`spring-30`(小計滿 5000.00 打七折,priority 20)、`loyalty-10`(無門檻打九折,priority 10)(pricing.py:32-35)。
3. **稅** = `round(折後貨款 × TAX_RATE)`,`TAX_RATE = 0.05`,只對折後貨款課,**運費不課稅**(pricing.py:55)。
4. **運費**:若**折扣前**的小計 ≥ `FREE_SHIPPING_THRESHOLD_CENTS = 8000.00` 就免運,否則收 `FLAT_SHIPPING_CENTS = 120.00`(pricing.py:57-60)。判斷用折扣前金額——這點很容易誤解,下面會單獨講。

(金額在程式內都是整數「分」,例如 `3000_00` = 300000 分 = 3000.00 元;以下沿用測試註解的 `.00` 寫法。)

### 第 4 段:出貨與重試 `dispatch`(dispatch.py:52)

- **選 carrier**(dispatch.py:36):`offshore` 一律走 `air`;`domestic` 看總重量,`≤ POST_MAX_WEIGHT_G = 2000` 克走 `post`,超過走 `freight`。
- **重試迴圈**最多 `MAX_DISPATCH_ATTEMPTS = 3` 次(config.py:5)。**只有 `RetryableError`(`CarrierTimeout` / `CarrierUnavailable`)會重試;`FatalError` 立刻往外拋**(dispatch.py:67)。
- 第 2 次起先 sleep 退避:`backoff = BASE_RETRY_DELAY_MS × 2^(attempt-2) + jitter`,`BASE = 200`ms,`jitter = crc32(order_id) % 100` 是**每張單固定**的 0–99ms(dispatch.py:44-49)。所以第 2 次 ≈ 200ms、第 3 次 ≈ 400ms(加同一 jitter)。
- 3 次都失敗 → `raise DispatchExhausted`(dispatch.py:70-71)。

回到 `process` 收尾:成功就回 `Receipt(dispatched, carrier, total_cents)`(pipeline.py:69);若捕到 `DispatchExhausted`,則 `release` 把庫存還回 catalog、刪掉預留(inventory.py:77)、把這張單塞進 `dead_letters`,回 `Receipt(dead_lettered)`(pipeline.py:61-67)。**這是整條線唯一會退還庫存的路徑**——`failed` 不需要退,因為兩段式建構保證那時根本還沒扣。

### 一次完整走查(來自 test_pipeline.py:22,`o-1`、`WIDGET × 3`)

`WIDGET` 在 catalog 是 price 3000.00、stock 10、weight 500g。

1. **reserve**:10 ≥ 3,扣到剩 7,快照單價 3000.00。
2. **price**:小計 9000.00 → `spring-30` 命中(priority 較高)→ 折 2700.00 → 折後 6300.00;稅 `round(6300.00 × 0.05)` = 315.00;運費——**折前** 9000.00 ≥ 8000.00 → 免運;total = **6615.00**。
3. **carrier**:domestic,總重 1500g ≤ 2000 → `post`。
4. **send 成功** → `Receipt(o-1, dispatched, post, 6615_00)`。測試斷言的就是這個數。

### 可調的旋鈕(全在 config.py)

| 旋鈕 | 值 | 調大的效果 |
|---|---|---|
| `RESERVATION_TTL_SECONDS` | 120 | 預留更久有效、重跑更常拿到舊價快照;調小則更常過期重建並 reprice |
| `MAX_DISPATCH_ATTEMPTS` / `BASE_RETRY_DELAY_MS` | 3 / 200 | 更能容忍暫時性 carrier 故障,但單筆最壞延遲上升 |
| `TAX_RATE` / `FREE_SHIPPING_THRESHOLD_CENTS` / `FLAT_SHIPPING_CENTS` / `DISCOUNT_RULES` | 0.05 / 8000.00 / 120.00 / — | 直接改變 total 的組成 |
| `POST_MAX_WEIGHT_G` | 2000 | 提高 → 更多 domestic 單走 post 而非 freight |

### 邊界與最容易誤解的三件事

1. **免運看「折扣前」小計**。像 `o-1` 折後只剩 6300.00(低於 8000.00 門檻)卻**仍免運**,因為折前 9000.00 已達標(test_pipeline.py:32-39 專門在測這個)。這是最常見的直覺陷阱。
2. **對外只有三種 `Receipt`,但不是每種錯都會變成 Receipt**。`process` 只接住 reserve 的 `FatalError` 與 dispatch 的 `DispatchExhausted`(pipeline.py:51-67)。因此 [inferred] 若 `send` 丟出的是 `FatalError`、或 store 連續 3 次 `VersionConflict` 讓 reserve 冒出 `RetryableError`,這些例外會**直接往外拋、不會被包成 Receipt**。預測失敗行為時要記得這個缺口。
3. **`reprice_required` 目前是資訊性旗標**。inventory 會在重建時設它,但 pipeline **一律無條件** `price(reservation)`(見 pipeline.py:56 註解「Always price…」),並沒有讀這個旗標。所以它現在不影響行為,只標示「這份預留是重建來的」——別誤以為它會 gate 計價。

---

**Sources and gaps**
- 主幹:`orderflow/pipeline.py:44-74`(四段串接、三種 Receipt、release/dead-letter)。
- 各段:`ingest.py:25-49`(驗證)、`inventory.py:54-137`(冪等/兩段式/TTL重建/樂觀鎖重試)、`pricing.py:32-78`(折扣擇一、稅、折前免運)、`dispatch.py:36-71`(選 carrier、退避、耗盡)。
- 支援:`store.py`(in-memory versioned store + 樂觀鎖)、`config.py`(全部旋鈕)、`errors.py:8-40`(Fatal vs Retryable 分類)。
- 佐證:`tests/test_pipeline.py` 覆蓋 happy path 總額、折前免運、庫存不足不重試、死信退庫存、退避、過期重建。
- Gap:這是 `evals/fixtures/` 下的自足 fixture,store 為記憶體、carrier 靠注入的 `send` callable,沒有真正 DB 或外部 API;上述並發衝突路徑在單執行緒下實務上不會觸發。此 workspace **尚無 `mental/` 正典模型**,以上皆為直接讀現有程式碼得出;若想把它固化成可累積、可校對的模型,可用 `$build`(我不會自行建立檔案)。

Context: engineer lens · map,mechanism,scenario,evidence · standard — 依「理解 repository 整體流程」這個目標選定;要調整可加 `lens=` `views=` `detail=`(例如 `detail=deep` 深入樂觀鎖與退避的邊界,或 `lens=pm` 只看功能與結局)。