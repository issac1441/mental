I have everything I need. Bash is gated (both `git` and `python3` require an approval that isn't being granted here), so I worked from the readable working tree, the module contracts, the change brief, and the **unmodified** test file — which turns out to be decisive evidence on its own. Here is the review.

---

這個 diff 確實實作了核准的「carrier send 2 秒 timeout」，但它同時夾帶了**至少兩項核准範圍外的改動**,並且動到了第三個檔案(`pipeline.py`)。因此結論是:**它不符合 change brief 說的「timeout only, semantics otherwise unchanged」**。核准的那一項做對了;問題出在沒被核准、卻一起改掉的東西——其中一項還會讓一個現有測試變紅、另一項會在 `CarrierUnavailable` 時洩漏庫存預留。

> 說明角度:engineer;內容切片:map · mechanism · scenario · evidence;細節:standard–deep。以下 `[observed]` = 直接有程式碼佐證,`[inferred]` = 我的推論(尚待 diff 確認),`[conflict]` = 程式碼與文件契約互相矛盾。

## 實際變更的心智模型(Before → After)

**核准要做的那一件事,做對了。** `[observed]`
- `config.py:13` 新增 `CARRIER_SEND_TIMEOUT_SECONDS = 2.0`,註解與 brief 一致。
- `dispatch.py:53-71` 新增 `_send_with_timeout`:把 `send` 丟進一條 daemon thread,`worker.join(2.0)`;若 thread 還活著就 `raise CarrierTimeout`(`dispatch.py:66-69`),否則把 send 自己拋的例外原樣重拋(`dispatch.py:70-71`)。
- `dispatch.py:87` 主流程改呼叫 `_send_with_timeout` 而非直接 `send`。逾時會走進 retry 迴圈 → 耗盡後 `DispatchExhausted` → `pipeline.py:62-68` release + dead-letter。**這條路徑符合核准內容。**

**但 model 的實際 delta 比「加一個 timeout」大。** 執行後你該更新的預測:

- **retry 的錯誤集合被縮小了。** `[conflict]` 迴圈只 `except CarrierTimeout`(`dispatch.py:89`)。但模組契約寫的是「Only RetryableError is retried」(`dispatch.py:5-6`)、`errors.py:3-4` 也寫「dispatch and storage retry RetryableError subclasses only」。而 `CarrierTimeout` 與 `CarrierUnavailable` 是**兄弟類別**,都繼承 `RetryableError`(`errors.py:36-41`)。→ 現在 `CarrierUnavailable`(carrier 回 5xx 這種 transient 錯誤)**不會被 retry、也不會被 dead-letter**。
- **backoff 變快了。** `[observed]` `config.py:10` 現在是 `BASE_RETRY_DELAY_MS = 50`,但**未被修改**的測試 `tests/test_pipeline.py:65-69` 用字面值 `200`/`400` 鎖死了 `BASE == 200`(見下方證據推導)。→ 第二次嘗試前的等待從 ~200ms 掉到 ~50ms。
- **「timeout」不等於「取消送出」。** `[observed]` thread 逾時後只是「不再等」,那條 send thread 仍在跑、Python 無法強制中止。逾時的送出**之後仍可能真的送達 carrier**,而 dispatch 同時已經在 retry。→ 對非冪等的 `send` 而言,存在**重複派送(重複出貨)**的風險。

## 核准 vs 實際

| brief 說 | 實際 diff |
|---|---|
| 加 2 秒 timeout,逾時 → `CarrierTimeout` → 走既有 retry 路徑 | ✅ 有做(`_send_with_timeout` + 迴圈 + dead-letter) |
| 不得改「哪些錯誤可 retry」 | ❌ retry 迴圈從(推定的)`except RetryableError` 縮成 `except CarrierTimeout`,踢掉 `CarrierUnavailable` |
| 不得改 backoff timing | ❌ `BASE_RETRY_DELAY_MS` 由 200 降到 50 |
| 不得動 receipts / dead-letter | ⚠️ `pipeline.py` 在改動清單內,但我無法取得 diff 確認改了什麼(git 需授權) |
| 不得動 pricing / inventory | ✅ `pricing.py`、`inventory.py` 未在改動清單 |

## 發現(依對 model 的衝擊排序)

**F1 — 破壞契約 + 錯誤的失敗行為:`CarrierUnavailable` 會逃出整條 pipeline。** `[observed]` 追蹤路徑:`send` 拋 `CarrierUnavailable` → `_send_with_timeout` 原樣重拋(`dispatch.py:70-71`)→ 迴圈只接 `CarrierTimeout`(`dispatch.py:89`),接不到 → 逃出 `dispatch()` → `pipeline.process` 只接 `DispatchExhausted`(`pipeline.py:62`),接不到 → **逃出 `process()` 變成未處理例外**。後果:不 retry、不 dead-letter、**reservation 不會被 release**(庫存與價格快照被卡住直到 TTL 120s 到期),呼叫端拿到 exception 而非 receipt。這同時違反 `dispatch.py:5-6` 與 `pipeline.py:10-15` 兩處文件契約,也踩到 brief 的「不得改哪些錯誤可 retry」。

**F2 — 未核准的隱藏決策,且會讓現有測試變紅:backoff 從 200 → 50。** `[observed]`+`[inferred]` `test_backoff_doubles_with_stable_jitter`(未被修改)斷言 `backoff_ms(3) == 400 + (backoff_ms(2) - 200)`,代數上**唯一解是 `BASE == 200`**(與 jitter 無關)。現在 config 是 50,該測試的兩條斷言都會失敗。→ 我推論 diff 把它從 200 改成 50,屬 brief 明列的 out-of-scope「backoff timing」。(我無法執行 `pytest`/`git` 確認 base 值,但未修改的測試就是強證據。)

**F3 — 決策意外 + 證據缺口:動了 `pipeline.py`,但改了什麼無法確認。** `[observed]` `pipeline.py` 在 `git status` 的 M 清單內,而 brief 把改動範圍限定在 dispatch,並把「receipts, dead-letter behavior」列為 out-of-scope——`pipeline.py` 正好擁有這兩者。現行 `pipeline.py` 內容看不出 timeout 相關邏輯,所以它的 delta 對純靜態分析不可見。**需要 diff 才能判定。**

**F4 — model drift(程式碼與自身文件矛盾)。** `[conflict]` `dispatch.py:5-6`、`errors.py:3-4`、`pipeline.py:10-15` 三處 docstring 都還在宣稱「所有 RetryableError 都會被 retry、最終 dead-letter」,但程式碼已不是如此。文件現在會誤導讀者。

**F5 — 驗證證據不足。** `[observed]` 這次改動**沒有**新增或更新任何測試(`tests/` 不在改動清單):
- 真正的 2 秒 wall-clock timeout **完全沒被測**——唯一的 dead-letter 測試(`test_pipeline.py:51-63`)是讓 send **直接 `raise CarrierTimeout`**,不是讓它 hang。
- 巧的是,那個測試用的正是**唯一還會被 retry 的** `CarrierTimeout`,所以它仍會綠燈,**剛好遮住 F1 的破壞**。若把它換成 `CarrierUnavailable`,就會 error 且庫存不會釋放。

**F6 — 局部實作品質(次要)。** `[observed]` 逾時的 daemon thread 無法回收,持續逾時下會累積殘留 thread;程序結束時 daemon thread 被硬砍。屬於 thread-based timeout 的固有代價,搭配 F1 的重複派送風險一起評估。

## 兩條路徑走查

- **成功路徑:** parse → reserve → price → `dispatch` attempt 1 呼叫 `_send_with_timeout`,send 在 2s 內回來 → `DispatchResult(attempts=1)` → receipt `"dispatched"`。✅ 與核准一致,快速回應時 timeout 包裝幾乎零開銷。
- **失敗路徑(核准的那種):** send hang > 2s → `CarrierTimeout` → 迴圈接住 → 退避後 attempt 2(此時 attempt 1 的 thread 可能仍在跑)→ 再逾時 → `DispatchExhausted` → dead-letter,receipt `"dead_lettered"`,庫存 release。✅ 行為符合核准,**但有 F6 的重複送達伏筆**。
- **失敗路徑(被打破的那種):** send 拋 `CarrierUnavailable` → 逃出 `dispatch()` → 逃出 `process()` → 未處理例外、reservation 洩漏。❌ 見 F1。

## 決策意外(Decision Surprises)

1. retry 錯誤集合縮窄(F1)—— out of scope。
2. `BASE_RETRY_DELAY_MS` 200 → 50(F2)—— out of scope。
3. `pipeline.py` 被修改(F3)—— 觸及 out-of-scope 區域,改動內容未明。

## 證據

- 核准內容:`CHANGE_BRIEF.md:5-15`(approved delta + out of scope 清單)。
- 錯誤階層:`errors.py:16-41`(`CarrierTimeout`、`CarrierUnavailable`、`VersionConflict` 皆為 `RetryableError`)。
- retry 縮窄:`dispatch.py:89` vs `dispatch.py:5-6`、`errors.py:3-4`。
- backoff 常數矛盾:`config.py:10` (=50) vs `tests/test_pipeline.py:65-69`(鎖 200);`backoff_ms` 定義在 `dispatch.py:45-50`。
- pipeline 失敗語意:`pipeline.py:60-68`、docstring `pipeline.py:10-15`。
- 遮蔽 F1 的測試:`tests/test_pipeline.py:51-63`(用 `CarrierTimeout`)。

## 待答問題 / 證據缺口

1. **`pipeline.py` 到底改了什麼?**(最關鍵的未知)
2. `dispatch` 的 catch 子句在 base 是否為 `except RetryableError`?`BASE_RETRY_DELAY_MS` 在 base 是否為 200?`MAX_DISPATCH_ATTEMPTS` 有沒有被動?

這三點都能用一條指令關閉:請**核准 git**、或直接貼上 `git --no-pager diff` 的輸出,我就能把上面的 `[inferred]` 升級成 `[observed]`,並補上 `pipeline.py` 的實際 delta。這次 review 全程唯讀,沒有更動任何檔案、程式碼或 git 狀態。

---

後續:若你想在修好之後重新確認自己對「哪些錯誤該 retry、backoff 該多久」的理解,可用 `$quiz`;目前 workspace 沒有 `mental/` canonical model,若你想把修正後的失敗語意固化成正式契約,再用 `$sync` 建立。修這個 diff 時,先處理 F1(把 `except CarrierTimeout` 還原成 `except RetryableError`,或明確地把「只 retry timeout」送回 `change` 重新核准)與 F2(還原 backoff 值),影響最大。