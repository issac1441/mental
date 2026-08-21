我已取得精確的 before/after（透過 `git cat-file` 讀出 base 版本，再對照工作區現況），可以做逐行比對了。下面是完整 review。

---

這個 diff 確實把「2 秒 carrier send timeout」做出來了，而且 `config.py` 完全照核准內容——只新增 `CARRIER_SEND_TIMEOUT_SECONDS = 2.0`,其他常數（重試次數、backoff、jitter…）一個都沒動。**但 `dispatch.py` 夾帶了一項 change brief 明文排除的改動**:重試迴圈多了一個 `except Exception` 分支,把「任何」非 `RetryableError` 的例外(包含 `FatalError` 和程式 bug)都包成 `CarrierTimeout` 拿去重試。結論是——timeout 本體做對了,但同時偷偷擴大了「哪些錯誤可以重試」的範圍,這一項並未核准,也和現有契約矛盾。

---

## 實際變更的心智模型(Actual Change Mental Model)

**Before → After**,這個 diff 只動兩個檔、五處:

| # | 位置 | 改動 | 屬於核准範圍? |
|---|------|------|:---:|
| 1 | `config.py:12-13` | 新增 `CARRIER_SEND_TIMEOUT_SECONDS = 2.0` | ✅ 是 |
| 2 | `dispatch.py:11` | 新增 `import threading` | ✅ 是(timeout 實作所需) |
| 3 | `dispatch.py:18` | import 加入 `CarrierTimeout` | ✅ 是 |
| 4 | `dispatch.py:53-71` | 新增 `_send_with_timeout()`:把 `send` 丟到 daemon thread、`join(2.0)`,逾時就 raise `CarrierTimeout` | ✅ 是 |
| 5 | `dispatch.py:87` | 呼叫點 `send(carrier, order)` → `_send_with_timeout(send, carrier, order)` | ✅ 是 |
| 6 | `dispatch.py:91-92` | **新增** `except Exception as err: last_error = CarrierTimeout(str(err))` | ❌ **否——超出核准範圍** |

**實際 model delta:** 核准的意圖是「送出無回應 → 視為 `CarrierTimeout` → 走既有重試路徑」。既有重試路徑就是迴圈裡的 `except RetryableError`(`dispatch.py:89-90`)。而 `CarrierTimeout` 本來就是 `RetryableError` 的子類(`errors.py:36`),所以**真正的逾時,靠第一個 except 分支就會被正確攔下並重試**。第 6 項那個新的 `except Exception` 對「逾時功能」本身完全不需要——它存在的唯一效果,是把**原本不可重試的例外也變成可重試**。

**Runtime 後果 / operator 該更新的預測:**
- 之前:`send` 丟出 `FatalError`(或任何非 `RetryableError`)→ 立即往外拋、不重試(符合 `dispatch.py:1-7` docstring 與 `errors.py:12-13`)。
- 之後:同樣的 `FatalError` → 被吞掉、包成 `CarrierTimeout` → **重試 3 次**(呼叫 `send` 三次)→ `DispatchExhausted` → pipeline 走 dead-letter(`pipeline.py:59-67`),回 `dead_lettered` receipt。而且 dead-letter 的 reason 會是 `str(err)` 包成的 CarrierTimeout 訊息,**原始錯誤型別在觀測面上被抹掉**。

---

## 核准 vs 實際(Proposed vs Actual)

- **核准要做、也做到了:** carrier send 加 2 秒 timeout,逾時當 `CarrierTimeout` 走既有重試 →「Explicitly out of scope」清單裡的重試次數、backoff、jitter、可重試型別、receipts、dead-letter、pricing、inventory——`config.py` 端全數未動,✅。
- **核准沒說要做、卻做了:** `dispatch.py:91-92` 這個 `except Exception` 把「哪些錯誤型別可重試」改掉了。而 brief 的 out-of-scope 第一條正是:**「Any change to which error types are retryable.」** 這是直接踩線。

---

## 具體路徑追蹤(一成功、一失敗)

**代表性路徑 A — 真正逾時(符合核准):** `send` 卡住 >2s → `_send_with_timeout` 的 worker 仍存活 → raise `CarrierTimeout`(`dispatch.py:66-69`)→ 被 `except RetryableError` 攔下重試 → 三次都逾時 → `DispatchExhausted` → dead-letter、釋放庫存、回 `dead_lettered`。✅ 完全符合 brief。

**失敗路徑 B — `send` 丟 `FatalError`(偏離核准):** 例如某 carrier adapter 對無效地址丟 `ValidationError`。
- Before:不被攔 → 立即往外拋,不重試。
- After:`_send_with_timeout` 內層 `except Exception`(`dispatch.py:60`)存起來再 re-raise → 迴圈的**新** `except Exception`(`:91-92`)攔下 → 包成 `CarrierTimeout` → 重試 3 次 → dead-lettered。一個「應該立刻失敗」的訂單,變成打了三次、最後進死信佇列,理由還顯示成「carrier timeout」。

---

## 發現(Findings,依 model 影響排序)

**1. 〔破壞契約 + 未核准決策 + 錯誤的失敗行為〕`except Exception` 擴大了可重試範圍。** `dispatch.py:91-92`
`send` 拋出的**任何** `FatalError` 或非預期例外(`TypeError`、`KeyError` 等程式 bug),現在都被轉成 `CarrierTimeout` 重試 3 次後 dead-letter,而非立即失敗。這同時:(a) 違反 brief out-of-scope 第一條;(b) 與 `dispatch.py:1-7` docstring「Only RetryableError is retried. FatalError propagates immediately」矛盾;(c) 與 `errors.py:12-13` 契約矛盾;(d) 把程式 bug 偽裝成短暫性 carrier 逾時、悄悄吞進死信佇列,傷害可觀測性。**且此分支對核准的 timeout 功能並非必要**——真正逾時走的是第一個 `except RetryableError`。這是本次最需要處理的偏離。*建議方向:移除該分支;若團隊確實想要「未知例外也重試」,那要另外核准,並同步更新 docstring/errors 契約與測試。*

**2. 〔runtime 後果 / 隱藏設計決策〕timeout 用 daemon thread 但無法真正取消送出,可能重複派送。** `dispatch.py:63-69`
逾時只是主執行緒 raise `CarrierTimeout`,背景 worker thread 不會被中止,仍繼續送。若 `send` 需要 ~2.5s 但其實會成功:第 1 次在 2.0s 判逾時 → 重試;背景那次在 2.5s 仍把訂單送達 carrier。backoff 只有 200ms+jitter(<300ms),所以同一訂單最多會有 **3 個重疊的 in-flight send**,carrier 可能收到 2–3 次;最糟情況是**訂單已送達,卻同時被 dead-letter、庫存被釋放**。docstring 說「never silently drops an order」技術上成立,但它現在可能「silently **duplicate**」。程式碼裡沒有任何 idempotency/去重保護。brief 核准的是「逾時就重試」,重複風險算是這個決策的內在後果,故我列為**需要讓 operator 知道的後果**,而非直接判定違反核准——但 brief 沒點出它,值得你確認是否可接受。

**3. 〔model drift / 文件過期〕`dispatch.py` 模組 docstring 未更新。** `dispatch.py:1-7`
仍寫著「Only RetryableError is retried. FatalError propagates immediately」,在 Finding 1 之後已不成立。diff 沒改它,程式與文件矛盾。

**4. 〔次要〕跨執行緒共享 `outcome` dict 無同步。** `dispatch.py:54-71`
靠 `join()` 屏障 + CPython GIL,非逾時路徑實務上安全;逾時路徑主執行緒 raise 後不再讀 `outcome`,該 race 無害。優先度低,順帶一提。

---

## 決策意外(Decision Surprises)

- **未核准的隱藏決策:** 把「未知/致命例外也當逾時重試」(Finding 1)偷偷併進 timeout 改動。註解「unexpected carrier failures behave like timeouts」洩了底——這是一個刻意的語意選擇,不是 timeout 的附帶必需品。
- **未言明的後果:** 用「無法取消的執行緒」做 timeout 所帶來的重複派送風險(Finding 2),brief 與程式碼都沒說明。
- **好消息(沒有意外的地方):** `config.py` 沒有夾帶任何 out-of-scope 常數改動;重試次數、backoff、jitter 全部原封不動——這點與核准一致。

---

## 證據(Evidence)

- Before 版本:以 `git cat-file -p HEAD:orderflow/{dispatch,config}.py` 讀出(`git diff`/`git show` 在此環境需核准,`cat-file` 可用);After 版本:直接讀工作區檔案。兩者逐行比對得到上表六處改動。[observed]
- 契約來源:`dispatch.py:1-7`、`errors.py:12-13,36`、`pipeline.py:1-15,59-67`。[observed]
- `CarrierTimeout` 是 `RetryableError` 子類,故真逾時走第一個 except:`errors.py:36`。[observed]
- **驗證缺口:** 我**沒有執行測試**(`python3` 在此環境需核准)。而且 `tests/test_pipeline.py` 的 `always_timeout`(:52-55)是**同步**丟 `CarrierTimeout`,只測到第一個 except 分支與 dead-letter 流程——**沒有**任何測試覆蓋 (a) 真正的 thread `join` 逾時機制、(b) 新的 `except Exception` 對 `FatalError` 的行為、(c) 重複派送。本次兩個最高風險的新行為目前零測試覆蓋。

---

## 待澄清問題(Open Questions)

1. Finding 1 的 `except Exception` 是**有意**要「未知例外也重試」,還是只是想保險而不小心擴大了範圍?(brief 讀起來是後者不被允許。)
2. `send` 的合約上到底會不會丟 `FatalError`?若會,現在會被重試 3 次 + 錯誤地 dead-letter。
3. Finding 2 的重複派送對這條 pipeline 可接受嗎?carrier 端是否有 idempotency key 可依?

---

我維持 read-only,沒有改動任何檔案、程式或 Git 狀態。若要處理,最小修正是移除 `dispatch.py:91-92` 那個 `except Exception` 分支,讓 timeout 功能只透過既有 `except RetryableError` 生效(那樣就 100% 符合核准)。目前 workspace 沒有 `mental/` canonical model;等你決定如何處置後,若想把「逾時語意」正式寫進契約,可用 `$sync` 對齊文件與程式(現在 docstring 已與程式漂移);若你想自我檢驗對這次重試語意的理解,可用 `$quiz`。

*Lens=engineer · Views=map,mechanism,scenario,evidence · Detail=standard→deep。*