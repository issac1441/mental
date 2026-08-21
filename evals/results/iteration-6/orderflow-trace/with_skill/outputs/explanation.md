一筆訂單在 orderflow 裡是被一條管線推過四個固定階段，每個階段的失敗各自對應一種收據結果。進入點是 `Pipeline.process(raw: dict) -> Receipt`（`orderflow/pipeline.py:44`）：它拿一個原始 dict，依序跑 **ingest → reserve → price → dispatch**（順序是刻意的，見 `pipeline.py:3`），最後一定回傳一張 `Receipt`，狀態是三種之一 —— `dispatched`（出貨成功）、`failed`(前段擋下、不重試)、`dead_lettered`(派送重試用盡、已補償)。真正把包裹交給承運商的，是呼叫端注入的 `send` 函式；`Inventory` 同時扮演商品目錄與保留單的儲存。

下面按執行路徑走一遍。

## 1. Ingest — 把 dict 變成驗證過的 Order（`ingest.py:25`）

`parse_order` 檢查 order_id（必填、字串）、region（預設 `"domestic"`，只能是 `domestic`/`offshore`）、至少一筆 line，以及每筆 line 的 sku（必填字串）與 quantity（正整數）。任一項不合就丟 `ValidationError`。它屬於 `FatalError`，`process` 接住後直接回 `failed`、dispatch 完全不跑（`pipeline.py:47-49`）。

## 2. Reserve — 凍結庫存與單價（`inventory.py:54`）

`Inventory.reserve` 以 key `reservation/{order_id}` 同時鎖住兩件事：這張單要消耗的**庫存**，以及它將被計價的**單價快照**（`ReservedLine.unit_price_cents`）。三個關鍵性質：

- **冪等**：同一 order_id 若已有「未過期」的保留單，直接回傳原本那張，不會再扣一次庫存（`inventory.py:64-67`）。
- **過期重建**：TTL(`RESERVATION_TTL_SECONDS=120` 秒)一過，保留單用「當下目錄價」重建，並標記 `reprice_required=True`，因為單價可能已變（`inventory.py:68-71`）。
- **原子性**：`_build` 先驗證每一筆 line(找不到 SKU → `UnknownSku`；庫存不足 → `InsufficientStock`)，**全部通過才**逐筆扣庫存(`inventory.py:93-106`)——所以失敗的保留單不會留下「扣了一半」的庫存。

`UnknownSku`、`InsufficientStock` 也都是 `FatalError` → 回 `failed`。底層寫入走 `VersionedStore` 的樂觀鎖：每筆記錄帶 version，寫入要附上讀到的 version，否則丟可重試的 `VersionConflict`；`_put_with_retry` 會重讀 version、最多重試 3 次(`inventory.py:127`、`store.py:29`)。

## 3. Price — 一律用保留單快照算錢（`pricing.py:48`）

`process` **無條件**呼叫 `price(reservation)`（`pipeline.py:57`），計價基礎是保留單裡的單價，不是原始訂單。四條規則：

1. 商品小計 = Σ(數量 × 快照單價)。
2. 最多一個折扣：在門檻達標的規則中選 `priority` 最高者，**折扣不疊加**(`_select_discount`)。現有兩條：`spring-30`(30%、小計 ≥ 5000.00)、`loyalty-10`(10%、無門檻)。
3. 稅 = round(折後小計 × `TAX_RATE=0.05`)，**運費不課稅**。
4. 運費固定 `FLAT_SHIPPING_CENTS=120.00`，但當「**折扣前**」小計 ≥ `FREE_SHIPPING_THRESHOLD_CENTS=8000.00` 時免運；折扣不影響免運資格。

## 4. Dispatch — 選承運商、有限重試（`dispatch.py:52`）

先選承運商(`choose_carrier`)：offshore 一律 `"air"`；domestic 看總重，≤ `POST_MAX_WEIGHT_G=2000` 克走 `"post"`，否則 `"freight"`。接著最多試 `MAX_DISPATCH_ATTEMPTS=3` 次 `send(carrier, order)`：

- **成功** → 回 `DispatchResult`，`process` 回 `dispatched`(帶 carrier 與 total)。
- **丟 `RetryableError`**(如 `CarrierTimeout`/`CarrierUnavailable`) → 記下、退避後重試。退避 = `BASE_RETRY_DELAY_MS=200` × 2^(attempt-2) + 每單固定 jitter(0–99ms)(`backoff_ms`)；這個 `sleep` 是真的會阻塞的。
- **三次全敗** → 丟 `DispatchExhausted`。`process` 接住後做補償：`release` 保留單(庫存加回目錄、刪掉保留單)、記進 `dead_letters`、回 `dead_lettered`(`pipeline.py:60-67`)。

## 一個具體例子（測試 o-1）

WIDGET×3，目錄 price 3000.00 / stock 10 / weight 500g：

ingest 通過 → reserve 把 stock 扣到 7、記下單價 3000.00 → price：小計 **9000.00**，套 `spring-30` 折 2700.00 得 6300.00，稅 315.00，運費因「折扣前」9000.00 ≥ 8000.00 而**免運** → total **6615.00** → dispatch：總重 1500g ≤ 2000 走 `"post"`，送出成功 → `dispatched`。這正是 `test_happy_path_dispatches_with_totals` 鎖住的數字(`tests/test_pipeline.py:22`)。注意免運看的是折扣前的 9000.00，即使折後 6300.00 已低於門檻。（金額都是整數「分」，這裡用 X.XX 元呈現。）

## 三種結果與庫存下場

| Receipt 狀態 | 觸發點 | 庫存結果 |
|---|---|---|
| `dispatched` | send 成功 | 保留不釋放，庫存維持已扣（貨真的出去了） |
| `failed` | ingest 或 reserve 的 `FatalError` | 沒扣到庫存，無需釋放 |
| `dead_lettered` | dispatch 重試用盡 | `release` 把庫存加回目錄 |

## 可調的旋鈕（`config.py`）

- `RESERVATION_TTL_SECONDS` ↑ → 保留單活更久、越常命中冪等回舊單、越少重建重定價。
- `MAX_DISPATCH_ATTEMPTS` / `BASE_RETRY_DELAY_MS` ↑ → 更能撐過暫時性承運商故障，但失敗時要更久才 dead-letter。
- `POST_MAX_WEIGHT_G` → 決定 post/freight 的分界。
- `TAX_RATE` / `FREE_SHIPPING_THRESHOLD_CENTS` / `FLAT_SHIPPING_CENTS` / `DISCOUNT_RULES` → 直接改動金額結果。

## 容易誤解的邊界

- **`reprice_required` 目前沒有人讀**。pipeline 反正每次都重算 `price`，所以這個 flag 現在只是資訊性訊號，沒有任何 control flow 依賴它（只在 `inventory.py` 被設定、在測試被檢查）。你可能以為 pipeline 會依它決定是否重新計價；其實它無條件重算。
- **reserve 冪等，但 dispatch 不冪等**。同一張未過期的訂單再 `process` 一次，reserve 會回舊保留單(不重扣庫存)，但 `process` 仍會再跑一次 dispatch → `send` 被再呼叫一次。所以「保留層不會重複扣庫存」成立，但「不會重複出貨」**不成立**——重入會重送。
- **`send` 丟「非重試」錯誤會逃出 `process`**。dispatch 只接 `RetryableError`；若 `send` 丟 `FatalError` 或其他例外，會穿過 dispatch、也穿過 `process`(它只接 `DispatchExhausted`)拋給呼叫端，且此時保留單**不會**被 release、庫存卡住。所以 dispatch 註解說的「永不默默丟單」只在「重試用盡」這條路成立，不涵蓋 send 丟出致命錯誤的情況。

---

**Sources and gaps**
- 追蹤路徑：`pipeline.py:44`(orchestrator) → `ingest.py:25` → `inventory.py:54,93,127` + `store.py:29` → `pricing.py:48,72` → `dispatch.py:36,44,52`；錯誤分類 `errors.py`；旋鈕 `config.py`；行為以 `tests/test_pipeline.py` 佐證。
- 我是靜態閱讀＋以測試數字核對，未實際執行程式。並發／重入的推論（dispatch 重送、release 未走 `_put_with_retry`）是從單執行緒程式碼推得，真實並發下的競態未驗證。
- 這個 workspace 還沒有 canonical 的 `mental/` 模型；若想把上面這套理解固化成可查、可校正的模型，之後可用 `$build`（我不會自動建立任何檔案）。

Context: engineer lens · map,mechanism,scenario,evidence · standard — 依「理解整條出貨流程」這個 repo 追蹤目標而選；要更深(例如計價數學、退避、樂觀鎖競態)或換視角，直接說或加 `lens= views= detail=` 即可。