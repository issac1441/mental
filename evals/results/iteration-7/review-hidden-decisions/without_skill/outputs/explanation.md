我已比對 diff、CHANGE_BRIEF.md、error taxonomy（`errors.py`）與現有測試。以下是結論。

## 結論

這個 diff **確實有實作**核准的 2 秒 timeout —— 但同時夾帶了 **4 項 brief 明確列為 out of scope 的改動**。其中一項是真正的行為 regression 且不會被現有測試抓到，另一項會直接讓現有測試 fail。核准內容是「只加 timeout，其餘語意不變」，實際 diff 不符。

## 實際改了什麼

**符合核准範圍的部分（忠實實作）：**
- `config.py:13` 新增 `CARRIER_SEND_TIMEOUT_SECONDS = 2.0`。
- `dispatch.py:53-71` 新增 `_send_with_timeout()`，用 daemon thread + `join(timeout)` 實作等待，逾時丟 `CarrierTimeout`，否則把原始例外原樣 re-raise。
- `dispatch.py:87` 把 `send(...)` 換成 `_send_with_timeout(...)`。

這三項就足以滿足 brief。問題出在其餘改動。

## 跟核准內容的出入（皆為 out of scope）

**① 縮小 retry 的 except 型別 —— 真正的 regression（最嚴重）**
`dispatch.py:89` 把 `except RetryableError` 改成 `except CarrierTimeout`（連帶改了 import、`last_error` 型別、`DispatchExhausted.__init__` 型別）。

後果：`CarrierUnavailable`（`errors.py:40`，「carrier 回傳 transient 5xx」）和 `VersionConflict`（`errors.py:32`）都是 `RetryableError` 的 sibling、不是 `CarrierTimeout` 的 subclass。改動後它們**不再被 retry**，會直接從 `dispatch()` 往外拋成 unhandled exception，而不是走 retry / dead-letter。這違反 brief 的「不得改動哪些 error 型別可被 retry」，也違反 brief 自己寫的「follows the **existing** retry path」，以及 `dispatch.py` docstring「Only RetryableError is retried」。

關鍵：`CarrierTimeout` 本來就是 `RetryableError` 的 subclass（`errors.py:36`），所以正確做法是**維持 `except RetryableError` 完全不動**，新的 timeout 自然會被接住。這次的收窄既非必要、又有害。而且**現有測試沒有覆蓋 `CarrierUnavailable` 的 retry**，所以這是個 silent regression。

**② 改 retry 次數**
`config.py:7` `MAX_DISPATCH_ATTEMPTS` 3 → 2。brief 明列「不得改 retry counts」。

**③ 改 backoff timing —— 且會弄壞現有測試**
`config.py:10` `BASE_RETRY_DELAY_MS` 200 → 50。brief 明列「不得改 backoff timing」。此外 `tests/test_pipeline.py:65-69` 的 `test_backoff_doubles_with_stable_jitter` 是以 base=200 寫死的（`backoff_ms(2,...) - 200` 必須 ≥ 0）；改成 50 後該值變負，**這個測試會 fail**。

**④ 改 receipt**
`pipeline.py` 在 `Receipt` 新增 `attempts` 欄位並填入 `result.attempts`。brief 明列「不得改 receipts」。雖然是 additive、看似無害，但仍在 out-of-scope 清單內。

## 一個次要（在核准意圖內、但值得留意）的正確性隱憂

thread-based timeout 無法真正取消已送出的 send —— 逾時後 daemon thread 仍可能在背景完成該次 carrier send。若接著 retry，對非冪等的 carrier 就可能**重複送單**。這算是 brief 核准之「timeout→retry」路徑的固有代價，不是偏離，但既然 carrier send 通常不冪等，實作前值得先確認。

## 建議

若要讓 diff 回到「只做核准的事」：還原 ①②③④，只保留 `CARRIER_SEND_TIMEOUT_SECONDS`、`_send_with_timeout()` 與 `dispatch.py:87` 的接線，並讓 `except` 維持 `RetryableError`。要不要我直接把 diff 收斂成這個最小版本？