## 第 1 則（導師）

讀完了，出題有依據了。範圍鎖在 `orderflow/dispatch.py`（搭配 `config.py`、`errors.py`）的重試機制。以下三題，你用自己的話回答就好，我再逐題對照程式碼幫你確認。

已知參數：`MAX_DISPATCH_ATTEMPTS = 3`、`BASE_RETRY_DELAY_MS = 200`。

**Q1 — 次數與節奏**
`send()` 每次都丟 `CarrierTimeout`（一種 `RetryableError`）的話：
- `send()` 總共會被呼叫幾次？
- 這些呼叫「之間」會 sleep 幾次、各約多久？（先忽略 0–99ms 的 jitter）
- 最後一次失敗之後，還會不會再 sleep 一次才結束？

**Q2 — 什麼會觸發重試**
如果第一次 `send()` 丟的不是 retryable，而是某個 `FatalError` 子類（例如 `ValidationError`），`dispatch()` 的行為會怎樣？跟 Q1 的情況差在哪？

**Q3 — 用盡之後**
三次都以 retryable 失敗收場時，`dispatch()` 最後做了什麼？另外——這三次嘗試打的是「同一家」carrier 還是每次重選？

回答時不必背程式碼細節，講清楚「機制怎麼運作」跟「為什麼」就好。三題答完後如果還想加碼，我可以再問一題關於 `backoff_ms` 裡 jitter 的性質。

## 第 2 則（學習者）

我的理解是：失敗後會指數退避重試。第一次失敗後（也就是第 2 次嘗試前）等 400ms，第二次失敗後等 800ms，因為公式是 200 乘以 2 的 (n-1) 次方。jitter 的部分我記得是加一個隨機亂數避免同時重試。

## 第 3 則（導師）

核心觀念對，但兩個地方要修：數字差了一倍，jitter 不是亂數。逐項看：

**✅ 對的部分**：失敗後做「指數退避重試」、退避時間會翻倍——這個骨架正確。

**❌ 要修一：退避的數字差了 2 倍**
你用的公式是 `200 × 2^(n-1)`，但 `backoff_ms` 裡是 `BASE × 2^(attempt-2)`（注意是 `attempt-2`，docstring 說的「2-based」就是這個意思）。

關鍵在 `attempt` 的起點：它從 **1** 開始數，而 `attempt=1` 是第一次嘗試、**不 sleep**；真正的重試是 `attempt=2、3`。所以指數是 `attempt-2`：

| 事件 | attempt | 退避 | 實際等待 |
|------|---------|------|----------|
| 第一次失敗後 → 第 2 次嘗試前 | 2 | `200 × 2^0` | **200** + jitter |
| 第二次失敗後 → 第 3 次嘗試前 | 3 | `200 × 2^1` | **400** + jitter |

所以是 **200 → 400**，不是你說的 400 → 800。你的每個值剛好都大了一倍——典型的「指數 off-by-one」。第一個重試等的是「一倍 BASE」，不是「兩倍」。

**❌ 要修二：jitter 是決定性的，不是亂數**
程式碼是 `zlib.crc32(order_id) % 100`——由 **order_id 算出來的 0–99ms**，同一張單每次都算出同一個值，不是 random。

你講的「避免大家同時重試」這個**目的**方向對：用 order_id 去 hash，正是為了讓**不同訂單**的退避錯開、不要撞在同一毫秒。但因為它是決定性的，有兩個你原本會忽略的後果：
1. **同一張單**的兩次重試 jitter 完全相同（它只跟 order_id 有關，跟 attempt 無關）——所以它不會打散「同一張單自己」的重試節奏。
2. 可重現、好測試（不像 random 那樣每跑一次不一樣）。

---

另外你這次只答了 Q1 的退避部分，還有幾個沒碰，順手收一下：
- **Q1 剩下**：`send()` 到底被呼叫**幾次**？最後一次失敗之後，還會不會再 sleep 一次才結束？
- **Q2**：第一次就丟 `ValidationError`（FatalError）時會怎樣？
- **Q3**：三次都 retryable 失敗後，`dispatch()` 最後做了什麼？三次打的是同一家 carrier 嗎？

要不要接著答這幾題？

## 第 4 則（學習者）

了解，所以第 3 次嘗試前的固定等待是 200×2^(3-2)=400ms 才對。那全部嘗試都失敗之後呢——我猜 process() 會把 DispatchExhausted 直接拋給呼叫端，讓上層自己 catch 處理？

## 第 5 則（導師）

backoff 你補對了：`200×2^(3-2)=400ms` ✅，這個接上了。

至於「用盡之後」——你的直覺一半對，但另一半要**翻過來**，關鍵是分兩層看：

**`dispatch()` 這層**：確實會 `raise DispatchExhausted(last_error)`。所以「有東西被拋出來」你沒說錯。

**`process()` 這層**（你猜的地方）：**剛好相反**——它不是往上拋，而是**自己把 `DispatchExhausted` 接住**，然後做三件事（`pipeline.py` 61–67 行）：
1. `self.inventory.release(order.order_id)` — 釋放先前保留的庫存。貨沒送成，就得把佔住的庫存還回去，這就是 dispatch docstring 說的 "compensate"。
2. append 到 `self.dead_letters` — 進死信佇列，訂單不會憑空消失。
3. `return Receipt(status="dead_lettered", ...)` — **回傳一個 receipt，不是丟例外**。

所以「讓上層自己 catch 處理」正好是這設計**要避免**的：pipeline 幫你接掉了，呼叫端不用 `try/except`，只要看 `receipt.status`。docstring 那句 *"the caller gets a 'dead_lettered' receipt instead of an exception"* 就是在講這件事。

三種結局擺一起看更清楚——`process()` 把「預期內的失敗」全轉成帶 status 的 receipt：

| 情況 | 結果 |
|------|------|
| parse / reserve 撞 FatalError | `status="failed"` |
| dispatch 重試用盡 | `status="dead_lettered"`（＋釋放庫存＋死信） |
| 成功 | `status="dispatched"` |

（小細節：死信和 receipt 的 `reason` 用的是 `err.last_error`，也就是**最後那個原始的 retryable 錯誤**，不是 `DispatchExhausted` 的包裝訊息——原始原因被保留了下來。）

---

還有兩題沒收：
- **Q1 剩下**：`send()` 總共被呼叫幾次？最後一次失敗後還會不會再 sleep 一次才結束？
- **Q2**：dispatch 過程中若丟的是 `FatalError`（例如 `ValidationError`）會怎樣？**提示**：拿它跟你剛答的「被 `process()` 接住」情況比一比——結果不一樣喔。

## 第 6 則（學習者）

整理一下我現在的理解：總共最多 3 次嘗試；第 n 次嘗試前等 200×2^(n-2) 毫秒、外加由 order_id 的 CRC32 導出的固定 jitter；全部耗盡後呼叫端拿到的是 status 為 dead_lettered 的 Receipt、保留的庫存會被釋放、不會收到任何例外。沒問題的話，出一題新的變化題讓我驗證吧。

## 第 7 則（導師）

整理得很準，六點我逐一對過都成立 ✅。只補一個讓它**更精確**的地方：

**退避只發生在 n≥2。** 你寫「第 n 次嘗試前等 `200×2^(n-2)`」——這對 n=2、3 成立，但迴圈裡有 `if attempt > 1` 這道守門，所以**第 1 次嘗試不等、直接送**。所以完整說法是：最多 3 次嘗試，但**最多只有 2 次**退避等待（200＋j、400＋j），而且**最後一次失敗後不會再等**就直接收尾。這也把你之前 Q1 沒明講的那半題補齊了。

至於「不會收到任何例外」——在**重試用盡**這條路上完全正確。那它是不是**永遠**成立？下面這題就來測這個邊界。

---

**變化題**

`send()` 依序這樣回應（同一張單、carrier 已選定）：
- 第 1 次：丟 `CarrierTimeout`
- 第 2 次：丟 `ValidationError`

請回答：
- **(a)** `send()` 總共被呼叫幾次？會有第 3 次嗎？
- **(b)** `dispatch()` 最後是 `return` 還是 `raise`？若是 raise，拋的是哪一個例外？
- **(c)** 呼叫 `process()` 的人拿到的是 **Receipt 還是例外**？是 Receipt 就說 status；是例外就說哪一個。
- **(d)** 這張單先前保留的庫存，**有沒有**被釋放？

**提示**：把 `errors.py` 的繼承關係，分別套進 `dispatch()` 的 `except RetryableError` 和 `process()` 的 `except DispatchExhausted` 這兩道關卡——看誰接得住、誰接不住。慢慢推，我再幫你對答案。