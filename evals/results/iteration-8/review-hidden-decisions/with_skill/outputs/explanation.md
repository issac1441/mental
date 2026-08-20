I have everything I need: the approved brief, the full diff, the error taxonomy, the surrounding code, and the tests. I traced the execution paths statically (the sandbox blocked running the suite, noted below). Here is the review.

---

這個 diff 確實實作了核准的「carrier send 2 秒 timeout」(新增 `CARRIER_SEND_TIMEOUT_SECONDS = 2.0` 與 `_send_with_timeout`),但它**同時夾帶了四項未核准的變更**,而且其中一項改壞了失敗語意:重試的 `except` 從 `RetryableError` 收窄成只抓 `CarrierTimeout`,導致 `CarrierUnavailable` 不再重試,會以未捕捉例外的形式直接衝出 pipeline。因此它**不符合** brief 明訂的「timeout only, semantics otherwise unchanged」。

## 實際變更的心智模型(Before → After)

**dispatch.py — 送件迴圈**
- Before:直接呼叫 `send(carrier, order)`;`except RetryableError` 攔截**所有**可重試錯誤(`CarrierTimeout`、`CarrierUnavailable`,乃至未來新增的 `RetryableError` 子類)。
- After:改呼叫 `_send_with_timeout(...)`,用一條 daemon thread 執行 send,`worker.join(2.0)` 等待;逾時就丟 `CarrierTimeout`。攔截子句收窄為 `except CarrierTimeout`(dispatch.py:89)。

**config.py — 旋鈕**
- `MAX_DISPATCH_ATTEMPTS` 3 → **2**(config.py:7)
- `BASE_RETRY_DELAY_MS` 200 → **50**(config.py:10)
- 新增 `CARRIER_SEND_TIMEOUT_SECONDS = 2.0`(config.py:13)← 唯一核准的那項

**pipeline.py — 收據**
- `Receipt` 新增 `attempts: int | None`(pipeline.py:36),並在 dispatched 收據填入 `result.attempts`(pipeline.py:75)。

**實際的模型 delta / runtime 後果:**
1. **可重試集合被收窄**。`CarrierTimeout` 本來就是 `RetryableError` 的子類(errors.py:34),所以要讓 timeout「走既有重試路徑」,`except` 子句**根本不需要動**。把它改成 `except CarrierTimeout` 反而把 `CarrierUnavailable`(errors.py:37,carrier 回傳暫時性 5xx)踢出了重試路徑。
2. **重試更少、更快**:每筆訂單從最多 3 次變 2 次;唯一那次重試前的退避從約 200–299ms 降到約 50–149ms。
3. **逾時不等於取消**:Python 無法強制中止 thread。逾時只是「不再等」,那條 send 仍在背景跑,可能稍後才真的把訂單送出去。
4. 收據多帶一個 `attempts` 欄位。

**操作者該更新的預測:**
- 「dispatch 對任何暫時性 carrier 故障都會重試、最後給收據」→ 現在**只有 timeout** 會;`CarrierUnavailable` 會讓 `process` 直接拋例外。
- 「重試是安全、冪等的」→ 現在逾時重試會與仍在飛的第一次 send 疊加,存在**重複送件**風險。

## 核准 vs 實際

| 項目 | Brief 說 | 實際 diff |
|---|---|---|
| 2 秒 timeout → `CarrierTimeout` → 既有重試路徑 | ✅ 核准 | ✅ 有做(但實作方式帶來下述副作用) |
| 重試次數 | 明訂**不得改** | ❌ 3 → 2 |
| 退避時間 / backoff | 明訂**不得改** | ❌ 200 → 50ms |
| 哪些錯誤可重試 | 明訂**不得改** | ❌ 全 `RetryableError` → 只剩 `CarrierTimeout` |
| receipts | 明訂**不得改** | ❌ 新增 `attempts` 欄位 |
| 「其餘語意不變」 | 核准前提 | ❌ 上述皆違反 |

## 發現(依模型衝擊排序)

**F1 — 破壞契約 + 錯誤失敗行為:`CarrierUnavailable` 不再重試,並以未捕捉例外衝出 pipeline。** [observed 程式路徑 / inferred 影響]
`except CarrierTimeout`(dispatch.py:89)只抓 timeout。當 `send` 丟出 `CarrierUnavailable`(一個 `RetryableError`),`_send_with_timeout` 會原樣 re-raise(dispatch.py:71),而 dispatch 不再攔它 → 直接離開 `dispatch`。`pipeline.process` 只 `except DispatchExhausted`(pipeline.py:62),所以這個裸的 `CarrierUnavailable` 會一路穿出 `process` 拋給呼叫端。這同時違反兩份文件契約:dispatch 的「Only RetryableError is retried」與 pipeline 的「retryable 失敗會被重試、耗盡後 dead-letter、呼叫端拿到收據而非例外」(pipeline.py:11–14)。修法通常是把 `except` 改回 `RetryableError`(因為 `CarrierTimeout` 已是其子類,timeout 一樣會被抓)。

**F2 — 逾時無法取消,新增重複送件視窗與 thread 洩漏。** [inferred]
舊路徑只在 send **明確回報失敗(raise)** 後才重試;新路徑會在第一條 send **仍在執行、結果未知** 時就重試(dispatch.py:63–69)。若 send 慢但最終成功且非冪等,同一筆訂單可能被送給 carrier 兩次以上。此外每次逾時都留下一條 daemon thread,直到該 send 自行結束;carrier 持續變慢時 thread 會累積。brief 說「語意不變」,但這是新的失敗模式,值得讓操作者納入模型。

**F3 — 文件與程式碼互相矛盾(模型漂移)。** [conflict]
dispatch.py:4「Only RetryableError is retried」與 pipeline.py:11–14 的失敗語意,在 F1 之後皆已不成立,但註解未更新。讀這些 docstring 的人會得到錯誤的心智模型。

**F4 — 驗證證據缺失,且既有測試被改壞。** [observed]
- `test_backoff_doubles_with_stable_jitter`(test_pipeline.py:65–69)寫死了 `200`/`400`。改成 `BASE_RETRY_DELAY_MS = 50` 後,`backoff_ms(2,"o-5") = 50 + j`(j∈[0,99]),於是 `jitter = (50+j) − 200 = j − 150`,恆為負,`assertGreaterEqual(jitter, 0)` 必定失敗。此測試**現在會 fail**。
- **沒有任何測試覆蓋真正的 timeout 路徑**(會卡住的 send 觸發 `worker.join` 逾時)。`test_dead_letter_after_exhausted_retries_releases_stock` 用的是同步 `raise CarrierTimeout`,不是 hang。
- 沒有測試覆蓋 F1 的 `CarrierUnavailable` 逸出。
- 我嘗試實跑 `python3 -m unittest`,但此工作階段的權限層擋下了執行;以上為靜態追蹤(traced, not executed)。

## 決策落差(相對核准 brief 的範圍外變更)

brief 的「Explicitly out of scope」逐條被違反:

- **S1 retry counts:** `MAX_DISPATCH_ATTEMPTS` 3→2(config.py:7)——未核准。副作用:`DispatchExhausted` 訊息「gave up after 2 attempts」與 dead-letter 時機一併提前。
- **S2 backoff timing:** `BASE_RETRY_DELAY_MS` 200→50(config.py:10)——未核准;其測試破壞見 F4。
- **S3 which errors are retryable:** `except` 收窄(dispatch.py:89)——未核准;其正確性後果即 F1。
- **S4 receipts:** `Receipt.attempts`(pipeline.py:36,75)——未核准。純新增、風險低,但仍在明訂的範圍外。

這四項都可能是「順手」或誤留的改動(例如把退避調小、次數調少是為了讓測試跑快),但沒有任何一項在 brief 裡。

## 證據

- 核准範圍:CHANGE_BRIEF.md:7–15(timeout only;retry counts / backoff / retryable 類型 / receipts 皆 out of scope)。
- 錯誤階層:errors.py:30–38(`CarrierTimeout` 與 `CarrierUnavailable` 皆為 `RetryableError` 子類)。
- 收窄的攔截:dispatch.py:89;re-raise 原錯誤:dispatch.py:70–71;pipeline 只接 `DispatchExhausted`:pipeline.py:60–68。
- 逾時實作:dispatch.py:53–71(daemon thread + `join`,無取消)。
- config 旋鈕:config.py:7、10、13。
- 破壞的測試推導:test_pipeline.py:65–69 搭配 backoff 公式 dispatch.py:45–50。
- 說明:`CarrierUnavailable` 由實際 send 拋出屬 [inferred](依 errors.py:37–38 對它的定義);目前測試以 lambda 當 send,不會觸發。

## 待澄清問題

1. S1–S2、S4 是刻意的還是誤留?若非刻意,應從此 diff 移除以回到「timeout only」。
2. carrier `send` 是否冪等?若否,F2 的重複送件是實質風險,逾時重試需要冪等鍵或去重保護。
3. 是否**刻意**要把 `CarrierUnavailable` 變成不可重試?若否,`except` 應改回 `RetryableError`(F1)。
4. 有沒有比目前更新的驗證紀錄?就我所見,測試處於會失敗且未覆蓋新路徑的狀態。

---

本 workspace 沒有 `mental/` canonical model,所以我只能拿 diff 對照 brief 與程式碼自身的 docstring,無法對照已核准的概念模型——這是本次審查的殘留證據缺口。F3 的漂移目前僅存在於「程式碼 vs 自身註解」之間。若你想先確認自己對「收窄 `except` 為何會讓 `CarrierUnavailable` 逸出」的理解,可用 `$quiz`。

*Lens=engineer · Views=map,mechanism,scenario,evidence · Detail=deep — 依 repository 預設 engineer lens;此為 read-only 審查,未改動任何檔案、程式碼或 Git 狀態。*