看完整個 `orderflow` 套件（含測試），我把庫存保留、重試、以及失敗行為整理如下。先給你正確的心智模型，再點出幾個文件沒明講、但實際會咬人的地方。

## 整體流程

管線是固定四階段（`orderflow/pipeline.py:44`）：

```
parse_order → reserve → price → dispatch
```

`price` 刻意排在 `reserve` 之後，因為單價快照是由「保留」這一步凍結的，定價只認保留裡的快照，不看原始訂單。

## 庫存保留怎麼運作

核心在 `Inventory.reserve`（`orderflow/inventory.py:54`），有三個關鍵性質：

1. **同一 `order_id` 冪等**：`reservation/{order_id}` 已存在且未過期 → 直接回傳舊的保留，不重扣庫存（`inventory.py:64-67`）。
2. **TTL 過期會重建**：TTL 是 120 秒（`config.py:4`）。過期後 `reserve` 會用**當下的目錄**重新 `_build` 一份，並打上 `reprice_required=True`，讓定價知道總額要重算（`inventory.py:68-71`）。原因是舊快照的單價可能已經變了。
3. **先全驗證、再全提交**：`_build`（`inventory.py:93`）先跑一輪把每一行都查過（SKU 存在嗎？庫存夠嗎？），全部通過才進第二輪逐行扣庫存。這是為了「驗證階段失敗時不留下半套要回收的庫存」（`inventory.py:94-95`）。

扣庫存的實體動作 = 把 `catalog/{sku}` 的 `stock` 減掉；`release`（`inventory.py:77`）則是把數量加回去並刪掉保留記錄。

## 重試怎麼運作

系統裡其實有**兩套獨立的重試**，不要混在一起：

**① 儲存層寫入重試** — `_put_with_retry`（`inventory.py:127`）
針對 `VersionConflict`（樂觀鎖衝突）。版本化 store（`store.py`）每筆記錄帶 version，寫入要帶對版本，不對就丟 `VersionConflict`。這個 helper 最多試 `_PUT_ATTEMPTS = 3` 次，每次重讀版本再試；**三次還衝突就把 `VersionConflict` 往外拋**（`inventory.py:133-134`）。

**② 派送重試** — `dispatch`（`orderflow/dispatch.py:52`）
只針對 carrier 的 `RetryableError`（`CarrierTimeout` / `CarrierUnavailable`）。最多 `MAX_DISPATCH_ATTEMPTS = 3` 次，之間用指數退避 + 抖動：`BASE(200ms) × 2^(attempt-2) + jitter`，jitter 是 `crc32(order_id) % 100`（每筆訂單固定）。所以第 2 次等 ~200ms、第 3 次等 ~400ms。三次都失敗就丟 `DispatchExhausted`。

## 一筆訂單會怎麼失敗

文件宣稱失敗一律回一張「收據」（`pipeline.py:8-14`），但實際上 `process()` **只攔了三個地方的例外**，對應三種結果：

| 失敗點 | 觸發條件 | 結果 |
|---|---|---|
| `parse_order` 拋 `FatalError` | order_id 缺失、region 不合法、沒有 line、sku 缺失、quantity 非正整數（`ingest.py`） | `status="failed"`，立即，無重試 |
| `reserve` 拋 `FatalError` | `UnknownSku`（目錄查無此 SKU）或 `InsufficientStock`（庫存不足） | `status="failed"`，立即，無重試 |
| `dispatch` 拋 `DispatchExhausted` | carrier 連續 3 次 `RetryableError` | `status="dead_lettered"`：**釋放庫存** + 進死信佇列 + 回收據（`pipeline.py:59-67`） |

`test_insufficient_stock_fails_without_retry` 和 `test_dead_letter_after_exhausted_retries_releases_stock` 分別驗證了前後兩條。

## 文件沒明講、但實際會咬人的地方

你說想「搞懂失敗的行為」，這幾點才是重點——它們都是文件語氣（「一定會回收據」「不留半套庫存」）與實際程式碼不一致的地方：

**1. 保留階段的 `VersionConflict` 會直接炸出去，不是收據。**
`VersionConflict` 是 `RetryableError`，**不是** `FatalError`（`errors.py:32`）。但 `process()` 對 `reserve` 只 `except FatalError`（`pipeline.py:52-54`）。所以當 `_put_with_retry` 三次重試耗盡、把 `VersionConflict` 往外拋時，**沒人接**——它直接從 `process()` 逃出去變成未捕捉例外。這筆訂單既不是 `failed` 也不是 `dead_lettered`，而是讓呼叫端吃到 exception。這是文件完全沒提的第四種失敗模式。（同理，若 carrier 的 `send` 拋出非 retryable 的 `OrderError`，也會繞過 `DispatchExhausted` 的攔截逃出去。）

**2. 保留過期重建會「重複扣庫存」。**
過期分支只呼叫 `_build`，**沒有先 `release` 舊的保留**（`inventory.py:68-71`）。舊保留當初扣掉的庫存從沒還回去，重建又扣一次，同一筆訂單就被扣了兩份。`test_expired_reservation_is_rebuilt_and_flags_reprice` 只斷言 `reprice_required`、沒檢查 stock，所以這個洞是隱性的、測試抓不到。

**3. `_put_with_retry` 重試時會覆寫成過期的值 → 遺失更新（lost update）。**
衝突後它只更新 `expected_version`，卻用**同一個舊的 `value`** 重寫（`inventory.py:130-136`），不重讀、不重算。並發下若別人已改了庫存，這裡會把對方的更新蓋掉。等於樂觀鎖偵測到衝突，卻又把衝突的結果抹平了——違背了 store 存在的初衷。

**4. 「不留半套庫存」只在驗證階段成立。**
`_build` 第二輪是逐行 `_put_with_retry` 扣庫存（`inventory.py:108-112`）。若第 1 行已扣成功、第 2 行重試耗盡拋 `VersionConflict`，前面的扣減**不會回滾**，而且此時保留記錄還沒寫進 store（那步在 `_build` return 之後才做），所以 `release` 也救不回來（查無記錄）。結果：庫存被扣、沒有保留、例外往上拋——庫存憑空蒸發。

---

想我針對其中哪一項（例如 #1 的未捕捉例外，或 #2 的過期重複扣）深入到「怎麼修」的層級，還是先幫你補一個能重現的測試把洞釘住？