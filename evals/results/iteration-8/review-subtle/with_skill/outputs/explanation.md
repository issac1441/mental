已看完 diff、`CHANGE_BRIEF.md`、`dispatch.py`／`errors.py`／`config.py` 全文，以及 skill 引用的四份 reference。以下是 review（read-only,我沒有改動任何檔案或 Git 狀態）。

---

這個 diff 有實作核准的 2 秒 carrier send 逾時——逾時會被判為 `CarrierTimeout` 並走既有重試路徑——但它同時夾帶了兩項**未核准、且會改變失敗語意**的行為，所以與核准內容有實質出入,不建議照現狀合併。第一,新增的 `except Exception` 讓**所有**例外(含 `FatalError`)都被重試,直接違反模組自載的「只重試 `RetryableError`、`FatalError` 立即上拋」契約,也正好命中 brief 明列的 out-of-scope。第二,逾時用**無法被取消**的 daemon thread 實作,逾時後底層 send 仍可能稍後才真的交運,對有副作用的 send 會造成同一訂單重複派送。

## 實際變更心智模型 (Actual Change Mental Model)

**Before → After**

- **Before**:`dispatch` 直接呼叫 `send(carrier, order)`,只 catch `RetryableError` 重試;`FatalError` 與任何其他例外在 attempt 1 就**立即往外拋**。沒有逾時概念——send 掛多久,dispatch 就等多久。
- **After**:`send` 包進 `_send_with_timeout`(`dispatch.py:53`),在 daemon thread 執行、`join(2.0s)`。逾時→`raise CarrierTimeout`;因為 `CarrierTimeout` 本來就是 `RetryableError`(`errors.py:36`),它會被既有的 `except RetryableError` 接住重試。**此外** dispatch 新增 `except Exception`(`dispatch.py:91`),把任何非 `RetryableError` 例外轉成 `CarrierTimeout(str(err))` 再重試。

**Runtime 後果**

1. 慢的 send 現在最多等 2s 就判逾時重試——這是核准的效果,有到位。
2. 但 thread 不能被中止:逾時後底層 send **仍在背景執行**,可能在重試之後才真的把訂單交給 carrier;每次逾時也留下一條 daemon thread。
3. Fatal 與非預期例外**不再立即上拋**,而是被重試 3 次(每次還多睡一段 backoff,約 200ms + 400ms),最後包成 `DispatchExhausted`,其 `.last_error` 是 `CarrierTimeout` 字串,**原始型別與原因遺失**。

**契約 / 失敗語意變動**

- `[conflict]` `dispatch.py:1-7` 與 `errors.py:1-5` 明載「Only RetryableError is retried. FatalError propagates immediately」——實作已打破。
- 逃逸例外型別從 `FatalError`(原型別)變成 `DispatchExhausted`。呼叫端若靠型別區分「致命 vs 重試耗盡」會誤判。
- `[inferred]` 隱含不變式「一次 dispatch 最多一次實際交運」在逾時路徑下不再成立。

**操作者要更新的預測**

- 「送一筆 fatal order(壞 payload / 未知 SKU / 缺庫存)會立刻炸」→ 現在會延遲、重試、變成 `DispatchExhausted`。
- 「dead-letter 的 `last_error` 反映真因」→ 現在 fatal 會被標成 `CarrierTimeout`。
- 「一次 dispatch 最多實際交運一次」→ 逾時後可能多次。

## 核准 vs 實際 (Proposed vs Actual)

| 項目 | 核准 brief | 實際 diff |
|---|---|---|
| 2s 逾時 → `CarrierTimeout` → 既有重試 | ✅ | ✅ 有實作(config 常數 + thread wrapper + raise) |
| 重試哪些錯誤型別 | 明列 **out of scope** | ❌ 被 `except Exception` 擴大到所有例外(見 Finding 1) |
| 逾時的實作機制 | brief 未指定 | daemon thread,不可取消(見 Finding 2) |
| retry 次數 / backoff / jitter | out of scope | ✅ 未動 |
| receipts / dead-letter / pricing / inventory | out of scope | ✅ 未動 |

## 發現 (Findings) — 依模型衝擊排序

**1. `except Exception` 破壞重試契約,且落在明列的 out-of-scope 〔broken contract〕**
`dispatch.py:91-92` 的 `except Exception` 把 `FatalError`(→`OrderError`→`Exception`)也接住並重試。後果:`ValidationError`／`UnknownSku`／`InsufficientStock` 現在會被重試 3 次再包成 `DispatchExhausted`,原始型別遺失;連 send 內部的 `ValueError`／`KeyError` 這類程式 bug 也被偽裝成 `CarrierTimeout`,難以診斷。這正好命中 brief 的「Any change to which error types are retryable」。**關鍵**:逾時功能**不需要**這個 clause——`CarrierTimeout` 已是 `RetryableError`,逾時本來就走 `except RetryableError`。此 clause 非核准功能所必需。→ 建議移除,除非人類另外核准「擴大重試範圍」。

**2. 逾時用不可取消的 daemon thread → 重複派送 + thread 洩漏〔hidden decision / failure behavior〕**
`_send_with_timeout`(`dispatch.py:63-69`)判逾時後,底層 send 執行緒仍在跑;Python 無法中止它。若 send 有實際副作用,它可能在**重試之後**才真的交運,造成同一訂單被送 2~3 次;每次逾時也洩漏一條背景 thread。模組 docstring 自稱「never silently drops an order」,新碼卻可能「silently **duplicate**」。此風險存在於**核准的逾時路徑本身**,不只 Finding 1。`[inferred]` 嚴重度取決於 send 是否 idempotent——若非 idempotent,以真實成本論這可能是本 diff **最危險**的一項。→ 建議:確認 send 冪等性;若否,需 carrier 端 idempotency key/去重,或改用可真正取消的機制。

**3. 無驗證證據〔missing evidence〕**
`git diff` 只動 `config.py`、`dispatch.py`,**沒有任何測試變更**。核准的逾時路徑、以及被改掉的 fatal 路徑都無測試佐證;尤其沒有測試證明「`FatalError` 仍會立即上拋」——因為它現在其實不會(暴露 Finding 1)。逾時用真實 wall-clock + threading、不可注入,既有以 fake `sleep` 的測試也覆蓋不到。→ 建議補:逾時→重試→`DispatchExhausted`;fatal→立即上拋。

## 決策意外 (Decision Surprises)

兩項皆已在 Findings 述明:Finding 1(未核准地擴大重試範圍)與 Finding 2(未指定、且有重複派送副作用的 thread 機制)。共通點:兩者都**缺人類核准**,而 brief 的 `Human decision` 明寫「timeout only, semantics otherwise unchanged」。

## 證據 (Evidence)

- `config.py:12-13` — 新常數 `CARRIER_SEND_TIMEOUT_SECONDS = 2.0`(與 brief 一致)。
- `dispatch.py:53-71` — `_send_with_timeout`;`:87` 呼叫點;`:91-92` 新 `except Exception`。
- `errors.py:36-37` — `CarrierTimeout(RetryableError)`,證明逾時走既有路徑**不需** `except Exception`。
- `dispatch.py:1-7`、`errors.py:1-5` — 被違反的契約文字。
- `CHANGE_BRIEF.md` — out-of-scope 清單與 human decision。
- 測試:`git diff` 無測試檔變更。

## 待答問題 (Open Questions)

- send 是否有實際交運副作用、是否 idempotent?→ 決定 Finding 2 的真實嚴重度。
- `except Exception`「unexpected carrier failures behave like timeouts」是否有人類真的想要?brief 說沒有——需確認是刻意還是誤加。
- 逾時是否該在測試中可控(注入 timer/thread)?目前不可,影響 Finding 3 的可測性。

---

下一步建議:移除 Finding 1 的 `except Exception` clause 並補 Finding 3 的測試,即可讓 diff 回到「只加逾時」的核准範圍;Finding 2 需人類決策(冪等性/機制)。若你想自我檢核對這條 retry 契約的理解,可用 `$quiz`。`$sync` 目前不適用——workspace 沒有 `mental/` canonical model,而且這裡的衝突是「程式 vs 程式自己的 docstring」,該修的是程式,不是模型。