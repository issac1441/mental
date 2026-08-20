我已經把整個 pipeline 讀過一遍了。先講設計上「原本的意圖」，再指出實際行為跟文件描述不一致、而且直接影響失敗行為的幾個地方。

## 庫存保留（reservation）怎麼運作

核心在 `inventory.py` 的 `reserve()`（`inventory.py:54`）：

- **以 `order_id` 為單位做冪等（idempotent）**：先查 `reservation/{order_id}`。若已存在且未過期，直接回傳舊的保留，不重新扣庫存（`inventory.py:63-67`）。
- **`_build()` 是「先全驗證、再一次提交」的兩階段**（`inventory.py:93-125`）：
  - 第一階段把每一行都檢查過 —— SKU 不存在丟 `UnknownSku`、庫存不足丟 `InsufficientStock`（`inventory.py:96-106`）。
  - 全部通過後，第二階段才逐行把 `stock` 扣掉並「快照」當下的 `unit_price_cents` / `weight_g`（`inventory.py:108-120`）。
  - 好處：**單一筆保留失敗時不會留下扣了一半的庫存**，不需要回捲。這點設計是對的。
- **TTL 過期後會重建**：`RESERVATION_TTL_SECONDS = 120`（`config.py:4`）。過期後重新用「當下的目錄價」建一份新保留，並打上 `reprice_required=True`，讓 pipeline 知道總價要重算（`inventory.py:68-71`）。

## 重試（retry）有兩層，互相獨立

1. **儲存層** —— `_put_with_retry`（`inventory.py:127`）：只針對樂觀鎖衝突 `VersionConflict` 重試，最多 `_PUT_ATTEMPTS = 3` 次，每次重讀最新 version 再寫。
2. **派送層** —— `dispatch()`（`dispatch.py:52`）：只針對 `RetryableError`（`CarrierTimeout` / `CarrierUnavailable`）重試，最多 `MAX_DISPATCH_ATTEMPTS = 3` 次，指數退避 `BASE * 2^(attempt-2) + jitter`（`dispatch.py:44`）。`FatalError` 不重試、直接往上拋。

分界線就是 `errors.py` 的 taxonomy：`FatalError` 立即失敗、`RetryableError` 才重試。

## 一筆訂單「整個失敗」有哪幾種

看 `pipeline.py:44` 的 `process()`，**帳面上**只有兩種失敗 receipt：

| 狀態 | 觸發條件 | 行為 |
|------|----------|------|
| `failed` | `ValidationError`（格式/region/數量）、`UnknownSku`、`InsufficientStock` —— 都是 `FatalError` | 立即失敗、**完全不 dispatch**、不留殘餘庫存（`pipeline.py:47-54`） |
| `dead_lettered` | dispatch 三次都是 retryable 失敗 → `DispatchExhausted` | **釋放保留庫存** + 進 dead-letter queue + 回 receipt（`pipeline.py:61-67`） |

⚠️ 但實際上還有**第三種、文件沒寫的失敗**：**未被接住的例外直接讓 `process()` crash**。因為 reserve 那段只 `except FatalError`（`pipeline.py:53`），而下列都不是 `FatalError`：

- reserve 時 `VersionConflict` 重試 3 次耗盡 → `_put_with_retry` 把它往上拋（`inventory.py:133-134`），它是 `RetryableError`（`errors.py:32`），**不會被接住**，也不會變成 receipt，而是直接丟例外給呼叫端。
- `price()` 完全沒有 try（`pipeline.py:57`）。
- dispatch 拋出非 `DispatchExhausted` 的東西（例如 `send` 丟 `FatalError`）也不會被接住。

換句話說，`dispatch.py` 文件說「本模組絕不默默丟掉訂單」，但 **reserve 階段的儲存重試耗盡是可以默默把整個呼叫炸掉的**，這跟宣稱的失敗語意不一致。

## 兩個直接影響失敗行為、我認為是 bug 的點

**1. 過期保留重建時會「重複扣庫存」（庫存洩漏）** —— 這個最嚴重。

`reserve()` 在過期分支直接呼叫 `_build()` 再扣一次庫存，但**沒有先把舊保留的庫存還回去**（`inventory.py:68-71`）。對照 `release()`（`inventory.py:77-91`）才是唯一會把庫存加回目錄的地方，而它只在 dead-letter 路徑被呼叫。

實際跑一次（用測試目錄 `WIDGET stock=10`、數量 1）：
- 第一次保留：`stock 10 → 9`
- TTL 過期後再處理：`_build` 又扣一次 → `stock 9 → 8`

同一筆只會出貨一次的訂單，過期一次就吃掉兩份庫存。後果就是**目錄庫存被慢慢蝕空，導致後來其他本來該成功的訂單誤報 `InsufficientStock` → `failed`**。現有測試 `test_expired_reservation_is_rebuilt_and_flags_reprice` 只驗 `reprice_required`、沒驗庫存數字，所以抓不到。

**2. reserve 的 `VersionConflict` 耗盡會變成未捕捉例外**（同上第三種失敗），跟 pipeline 宣稱的「FatalError→failed、RetryableError→dead_lettered」不符。在目前單執行緒、記憶體內的用法下不容易觸發，但路徑確實存在。

另外附帶一提（跟你問的冪等有關）：保留的冪等只保護**庫存**，不保護**出貨**。同一個 `order_id` 在 TTL 內被重跑一次，reserve 會回傳舊保留、但 dispatch 會**再 `send` 一次**（`pipeline.py:57-60` 沒有「已出貨」的擋板），有重複出貨風險。

---

想我接著怎麼做？我可以：
- 寫一個會 fail 的測試把「過期重建重複扣庫存」釘死，然後修 `reserve()`（過期分支先 `release` 再 `_build`，或改成復用已扣的庫存）；
- 或把 reserve 的 `VersionConflict`／`price` 也納入 pipeline 的失敗語意，讓它回 receipt 而不是炸掉。

要哪個我就直接動手。