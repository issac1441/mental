## Review 結論（先講重點）

核准的「2 秒 timeout」本身有做出來，但這個 diff **同時夾帶了 4 項超出核准範圍的變更**，其中 3 項正好落在 brief 明文列為「未核准」的清單裡，而且有 **1 項是會造成 regression 的行為變更**。

---

## 一、核准的部分（有做到）

Brief 核准的是:給 carrier `send` 加 2 秒 timeout,逾時視為 `CarrierTimeout` 並走既有 retry 路徑。這部分實作存在:

- `config.py`:新增 `CARRIER_SEND_TIMEOUT_SECONDS = 2.0` ✓
- `dispatch.py:53` `_send_with_timeout()`:用 thread + `join(timeout)`,逾時 raise `CarrierTimeout` ✓
- 逾時的 `CarrierTimeout` 會被 loop 接住重試 ✓（僅就 timeout 這條路徑而言）

---

## 二、跟核准內容的出入（4 項,依嚴重度排序）

### 🔴 1. 悄悄縮小了「哪些錯誤會重試」— 這是 regression（brief 明文禁止）
`dispatch.py:89` 把 `except RetryableError` 改成 `except CarrierTimeout`。

Brief 白紙黑字寫「Any change to which error types are retryable」屬於 out of scope,而這正好改了它。後果很具體:

`errors.py` 裡 `CarrierUnavailable`(carrier 回傳 transient 5xx)也是 `RetryableError`,但**不是** `CarrierTimeout` 的子類。所以當 `send` 丟出 `CarrierUnavailable` 時:

- **改動前**:被 `except RetryableError` 接住 → 重試 → 耗盡後包成 `DispatchExhausted` → pipeline 釋放 reservation、丟 dead-letter、回一張 `dead_lettered` 收據。
- **改動後**:`_send_with_timeout` 於 `dispatch.py:71` 原樣 re-raise `CarrierUnavailable` → loop 的 `except CarrierTimeout` **接不住** → 直接穿出 `dispatch()` → `pipeline.py:62` 只 catch `DispatchExhausted`,也**接不住** → **裸例外一路噴給呼叫端**,而且 `pipeline.py:63` 的 `inventory.release()` 不會執行(**reservation 外洩**),訂單也不會進 dead-letter。

這同時打破了兩處文件承諾:`dispatch.py:3`「Only RetryableError is retried」、`pipeline.py:11-14`「RetryableError…retried…then dead-lettered…caller gets a receipt instead of an exception」。兩處註解都沒更新,現在都與程式碼不符。

(附帶:`dispatch.py:26` `DispatchExhausted.__init__` 的型別標註也從 `RetryableError` 窄化成 `CarrierTimeout`,是同一個窄化動作的延伸。)

### 🟠 2. 改了 retry 次數(brief 明文禁止)
`config.py`:`MAX_DISPATCH_ATTEMPTS = 3 → 2`。Brief:「Any change to retry counts」= out of scope。所有訂單的重試上限被下修,和 timeout 無關。

### 🟠 3. 改了 backoff 時間(brief 明文禁止)
`config.py`:`BASE_RETRY_DELAY_MS = 200 → 50`。Brief:「Any change to backoff timing」= out of scope。base delay 變成 1/4。

### 🟡 4. 改了收據結構(brief 明文禁止)
`pipeline.py:36` `Receipt` 新增 `attempts` 欄位,並於 `:75` 填入 `result.attempts`。Brief:「Any change to receipts」= out of scope。這項是純新增、風險最低,但依然在禁止清單內。

---

## 三、另外一個值得注意的風險(屬於核准設計本身,非出入)

`_send_with_timeout` 用的是 daemon thread + `join(timeout)`,**逾時並不會取消原本的 send**——第一個 send thread 仍在背景跑。若 carrier 其實只是慢、稍後才真正送出,retry 又送一次,對非冪等的 `send` 就會**重複出貨**。這是「timeout 後重試不可取消操作」的固有風險,brief 核准 timeout+retry 時未必想到,建議跟核准者確認 `send` 是否冪等。

---

## 建議

若要嚴格貼合核准範圍,應只保留第一節那三處(timeout 常數、`_send_with_timeout`、逾時走重試),並:
- 把 `dispatch.py:89` 改回 `except RetryableError`(讓 `CarrierTimeout` 自然沿用既有路徑,而非取代它);
- 還原 `MAX_DISPATCH_ATTEMPTS`、`BASE_RETRY_DELAY_MS`;
- 拿掉 `Receipt.attempts`。

要我直接把這個 diff 收斂成「只做核准範圍」的版本嗎?