一筆訂單的處理全程由單一進入點 `Pipeline.process(raw)`（`orderflow/pipeline.py:44`）串起,依「刻意固定」的四個階段跑完:**解析驗證 → 保留庫存 → 計價 → 出貨**(ingest → reserve → price → dispatch),最後回傳一張 `Receipt`,狀態是 `dispatched`、`failed`、`dead_lettered` 三者之一。階段順序是設計決定:保留庫存必須在計價之前,因為「保留單」同時凍結了要扣的庫存**和**要計價的單價快照,計價一律以這份快照為準,而不是原始訂單。

```
raw dict
  └─ parse_order ──(ValidationError)──────────────► Receipt "failed"
       └─ inventory.reserve ──(UnknownSku/InsufficientStock)─► Receipt "failed"
            └─ price（永遠吃保留單快照）
                 └─ dispatch ──成功──────────────► Receipt "dispatched"
                      └─(重試用盡 DispatchExhausted)─► 釋放庫存+死信 ► Receipt "dead_lettered"
```

## 階段一:解析驗證 `parse_order`(`ingest.py:25`)

把 raw dict 轉成不可變的 `Order`(order_id、region、lines)。驗證規則:`order_id` 必填且為字串、`region` 預設 `"domestic"` 且只能是 `{"domestic","offshore"}`、至少一行、每行要有 `sku`(字串)與正整數 `quantity`。任何一項不過就丟 `ValidationError`(屬於 `FatalError`)。

管線在這裡若接到 `FatalError`,直接回 `Receipt(status="failed")`,而且用的是 `str(raw.get("order_id"))` ——因為此時 `Order` 物件還沒生出來(`pipeline.py:47-49`)。

## 階段二:保留庫存 `Inventory.reserve`(`inventory.py:54`)

這是最有機關的一段,它凍結兩樣東西:**要消耗的庫存**與**要計價的單價**。

- **冪等(idempotent)**:以 `reservation/{order_id}` 為鍵。同一訂單重跑時,若既有保留單還「活著」就直接回傳既有的(`inventory.py:64-67`),不會重複扣庫存。
- **TTL 過期會重建**:保留單活過 `RESERVATION_TTL_SECONDS`(120 秒)後,以「當前目錄價」重建一份,並標記 `reprice_required=True`(`inventory.py:68-71`),因為凍結的單價可能已經變了。
- **先全驗、再全扣**:`_build`(`inventory.py:93`)先把每一行都查一遍——目錄沒這個 SKU 就丟 `UnknownSku`、庫存不夠就丟 `InsufficientStock`——**全部通過後**才逐行扣庫存(`inventory.py:94-112`)。這保證失敗的保留不會留下「扣一半」的庫存要收拾。
- **底層是版本化儲存**:`VersionedStore`(`store.py`)是記憶體內的字典,每筆記錄帶版本號,寫入要帶對版本,否則丟 `VersionConflict`(可重試)。`_put_with_retry` 會重讀重試最多 3 次(`inventory.py:127-137`)。這套樂觀並行控制目前是為並發寫入預留的基礎設施。

`UnknownSku`、`InsufficientStock` 都是 `FatalError` → 回 `Receipt(status="failed")`,不重試、不派送。

## 階段三:計價 `price`(`pricing.py:48`)

一律從**保留單快照**算,不看原始訂單(`pipeline.py:56-57`)。四條規則:

1. 商品小計 = Σ(保留數量 × 凍結單價)。
2. **折扣不疊加**:只取「符合最低門檻、且優先度最高」的那一條(`_select_discount`, `pricing.py:72-78`)。`spring-30`(30%、門檻 $5000、優先度 20)勝過 `loyalty-10`(10%、門檻 $0、優先度 10)。
3. 稅 = round(**折後**小計 × `TAX_RATE`);運費從不課稅。
4. 運費:**折扣「前」**小計達 `FREE_SHIPPING_THRESHOLD_CENTS` 就免運,否則收固定 `FLAT_SHIPPING_CENTS`。

⚠️ 最容易誤會的地方:免運看的是**折扣前**小計。你可能以為「折後金額低於免運門檻就要收運費」,實際不會——資格在折扣前就判定完了(`pricing.py:57`;測試 `test_free_shipping_uses_pre_discount_subtotal`)。

## 階段四:出貨 `dispatch`(`dispatch.py:52`)

- **選載具** `choose_carrier`(`dispatch.py:36`):`offshore` 一律走 `air`;`domestic` 依總重(Σ 數量×`weight_g`)決定——不超過 `POST_MAX_WEIGHT_G`(2000g)走 `post`,否則 `freight`。
- **有界重試**:最多 `MAX_DISPATCH_ATTEMPTS`(3)次呼叫 `send(carrier, order)`。第一次不等待,之後每次先睡 `backoff_ms`:基礎延遲 `BASE_RETRY_DELAY_MS`(200ms)每次加倍,再加上依 `order_id` 算出的 0–99ms 固定 jitter(`dispatch.py:44-49`,同一訂單抖動量固定)。
- **只重試 `RetryableError`**(`CarrierTimeout`、`CarrierUnavailable`、`VersionConflict`)。三次都失敗就丟 `DispatchExhausted`。
- 管線接到 `DispatchExhausted` 後做**補償**(`pipeline.py:62-67`):`release()` 把庫存還回目錄、把訂單丟進 `dead_letters` 清單、回 `Receipt(status="dead_lettered")`,reason 是最後一次載具錯誤。

## 三種結局(`Receipt`)

| 狀態 | 何時發生 | 庫存後果 |
|------|----------|----------|
| `dispatched` | 全程成功 | 已扣(帶 `carrier`、`total_cents`) |
| `failed` | ingest/reserve 的 `FatalError` | 未扣(先全驗再全扣,失敗不留殘餘) |
| `dead_lettered` | dispatch 重試用盡 | 已 `release` 還回目錄 |

## 可調的旋鈕(`config.py`)

- `RESERVATION_TTL_SECONDS=120`:調大→舊快照沿用更久;調小→更常以現價重建並觸發 `reprice_required`。
- `MAX_DISPATCH_ATTEMPTS=3` / `BASE_RETRY_DELAY_MS=200`:撐過暫時性載具故障的能力 vs. 尾端延遲。
- `FREE_SHIPPING_THRESHOLD_CENTS`($8000)、`FLAT_SHIPPING_CENTS`($120)、`TAX_RATE=0.05`:直接改動帳單。
- `POST_MAX_WEIGHT_G=2000`:國內 `post`/`freight` 的分界。

## 走一遍具體例子(來自 `test_pipeline.py:22`)

下單 3 個 `WIDGET`(單價 $3000、庫存 10、每個 500g)、region 預設 domestic:

保留 → 庫存 10 扣成 7、凍結單價 $3000 → 小計 $9000 → 命中 `spring-30` 折 $2700 → 折後 $6300 → 稅 round($6300×0.05)=$315 → 運費**免**(折前 $9000 ≥ $8000 門檻)→ **total $6615**。總重 3×500=1500g ≤ 2000 → carrier `post`。得到 `Receipt("dispatched", carrier="post", total_cents=6615_00)`。

## 需要留意的邊界

- **冪等只在保留單存活期間成立**;過 TTL 後同一訂單會重建保留單並標記需重新計價。
- `reprice_required` 在管線內部其實是**資訊性旗標**:`price()` 只讀 `reservation.lines` 並無條件重算,從不檢查這個旗標(`pricing.py:48-49`、`pipeline.py:56-57`)。正確性來自「永遠以最新快照計價」,旗標是給呼叫端/測試看的訊號。
- **一個不對稱處** [observed]:若 `send` callback 丟出「非 `RetryableError`」的例外(任何 `FatalError` 或一般 `Exception`),`dispatch` 不攔(只 `except RetryableError`)、`process` 也只攔 `DispatchExhausted`,因此該例外會**直接往外拋出 `process`,不會變成 Receipt**。相對地,ingest/reserve 的 `FatalError` 會被轉成 `"failed"` 收據。`dispatch` 的 docstring 說「never silently drops an order」——它確實沒靜默吞掉,但這條路徑是以例外呈現,而非死信收據。

---

**Sources and gaps**
- 進入點與階段編排、補償:`orderflow/pipeline.py:44-74`。
- 各階段:`ingest.py:25`、`inventory.py:54/77/93/127`、`pricing.py:48/72`、`dispatch.py:36/44/52`;儲存 `store.py`;錯誤分類 `errors.py`;旋鈕 `config.py`。
- 行為佐證:`tests/test_pipeline.py`(happy path、免運看折前、缺貨不重試、死信釋放庫存、backoff、TTL 重建)。
- 未驗證/待確認:(1)`send` 丟非重試例外的實際上層處理未在 repo 內出現;(2)`VersionedStore` 為記憶體內、測試為單執行緒,樂觀鎖重試路徑未被實際觸發;(3)`reprice_required` 的下游消費者不在此 codebase 內;(4)`dispatch` 預設用真實 `time.sleep`,死信情境會實際等待。
- 此 workspace 目前沒有 `mental/` canonical model,以上是直接讀原始碼得出的模型;若想把它固化成可維護的共享模型,可用 `$build`(我不會自行建立檔案)。

*Context:engineer lens · map,mechanism,scenario,evidence · standard —— 依據:這是對現有 repository 的執行流程追蹤,套用預設 engineer 視角。想更淺(概念導向)、更深(逐行/並發語意),或換個視角,直接說或用 `lens= views= detail=` 調整。*