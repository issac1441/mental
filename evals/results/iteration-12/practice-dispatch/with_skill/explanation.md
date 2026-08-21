## 第 1 則（導師）

好，我已經讀完 `dispatch.py`、`config.py`、`errors.py`,對這個重試機制有完整的掌握了。既然你要「確認理解對不對」,我們用 retrieval 的方式:我給情境,你憑理解推,先別翻程式碼。

先從最常見的路徑開始——**重試後成功**。

情境:一筆 `region == "offshore"` 的訂單進到 `dispatch()`。你注入的 `send()` 前兩次都丟 `CarrierTimeout`,第三次成功回傳。其餘參數都用預設(`MAX_DISPATCH_ATTEMPTS=3`、`BASE_RETRY_DELAY_MS=200`)。

請 trace 這一次執行,回答三件事:

1. `send()` 總共被呼叫幾次?
2. 過程中 `sleep()` 被呼叫幾次?每次大約睡多久?(可以用公式或帶入 config 常數表達,jitter 先擱著沒關係)
3. `dispatch()` 最後回傳什麼?(型別 + 各欄位的值)

答完我再依你的回答決定下一題——我們會慢慢逼近幾個容易搞錯的邊界。

—
Lens: engineer｜Views: mechanism, scenario｜Detail: standard(依你指定;scope 綁 `dispatch.py`)

## 第 2 則（學習者）

我的理解是：失敗後會指數退避重試。第一次失敗後（也就是第 2 次嘗試前）等 400ms，第二次失敗後等 800ms，因為公式是 200 乘以 2 的 (n-1) 次方。jitter 的部分我記得是加一個隨機亂數避免同時重試。

## 第 3 則（導師）

你抓到的骨架是對的:指數退避、base = 200、每次翻倍,而且「第一次失敗 ↔ 第 2 次嘗試前才開始等」這個對應也正確(第一次嘗試**前**不 sleep)。

**但延遲數字差了一倍。** 實際不是 400 → 800,而是 **200 → 400**。

問題出在指數的 offset。程式的公式是:

```python
base = BASE_RETRY_DELAY_MS * (2 ** (attempt - 2))
```

指數是 `attempt - 2`,不是你記的 `attempt - 1`。關鍵一句話:**第一次重試的指數從 0 算起**。

- 第 2 次嘗試前(第一次重試):`200 × 2^(2-2)` = `200 × 2^0` = **200ms**
- 第 3 次嘗試前(第二次重試):`200 × 2^(3-2)` = `200 × 2^1` = **400ms**

也就是「第一次重試只等一個 BASE(1 倍),之後才開始翻倍」。你的 `2^(n-1)` 會讓第一次重試就先乘 2,整條時間軸因此被推大一倍。

換一組數字驗證一下——這次讓它一路失敗到底:

> 假設 config 改成 `BASE_RETRY_DELAY_MS = 100`、`MAX_DISPATCH_ATTEMPTS = 4`。一筆訂單的 `send()` 這四次全丟 `CarrierTimeout`,沒有一次成功。

1. 過程中 `sleep()` 被呼叫幾次?每次的 base 各是多少 ms?(jitter 先不算)
2. 迴圈跑完後,`dispatch()` 會發生什麼事?丟出什麼、裡面帶著什麼資訊?

(你提到 jitter 是「隨機亂數」——這點先擱著,下一輪專門看,那裡有個小陷阱。)

## 第 4 則（學習者）

了解，所以第 3 次嘗試前的固定等待是 200×2^(3-2)=400ms 才對。那全部嘗試都失敗之後呢——我猜 process() 會把 DispatchExhausted 直接拋給呼叫端，讓上層自己 catch 處理？

## 第 5 則（導師）

先把上一題收尾:`BASE=100`、`MAX=4` 那組會 sleep **三次**,base 各是 100 / 200 / 400 ms——指數規則你已經接上了,這條線過關。

現在講你猜的那半條路。你有**一半是對的**:`dispatch()` 確實會 `raise DispatchExhausted`,而且它帶著 `last_error`(最後那次的 `CarrierTimeout`)。這個 exception 也的確是「給上層的訊號」。

**但它不會飛到 caller 手上。** `process()` 就地把它接住了:

```python
try:
    result = dispatch(order, reservation, self.send)
except DispatchExhausted as err:
    self.inventory.release(order.order_id)              # 1. 把庫存放回去
    self.dead_letters.append({...})                     # 2. 進 dead-letter queue
    return Receipt(order_id=..., status="dead_lettered",
                   reason=str(err.last_error))           # 3. 回傳 Receipt,不是丟例外
```

所以 caller 拿到的是一個 **`status="dead_lettered"` 的 `Receipt` 值**,不是 exception。`process()` 就是那道邊界:把 dispatch 內部的 exception,翻譯成「補償動作 + 一個正常回傳值」。這正是 `dispatch.py` docstring 說的 "so the pipeline can compensate / never silently drops an order"。

你「拋給呼叫端」的直覺不是全錯——只是搞錯對象:`DispatchExhausted` 是**被特別接住**的那一個。

轉個彎,確認你抓到「補償」這半段。同樣是「這筆訂單沒送出去」,比較兩條路:

- **A**:`reserve()` 因為 `InsufficientStock` 失敗
- **B**:`reserve()` 成功,但 `dispatch()` 三次全失敗、耗盡

問兩件事:
1. caller 在 A、B 各拿到什麼 `status`?
2. `inventory.release(...)` 這個動作,A、B 兩條**都會**執行嗎?為什麼?

## 第 6 則（學習者）

整理一下我現在的理解：總共最多 3 次嘗試；第 n 次嘗試前等 200×2^(n-2) 毫秒、外加由 order_id 的 CRC32 導出的固定 jitter；全部耗盡後呼叫端拿到的是 status 為 dead_lettered 的 Receipt、保留的庫存會被釋放、不會收到任何例外。沒問題的話，出一題新的變化題讓我驗證吧。

## 第 7 則（導師）

你的整理是準的。我特別記一下你自己修掉的兩個坑:指數 offset 從 `2^(n-1)` 改成 `2^(n-2)`,jitter 從「隨機」改成「由 `order_id` 的 CRC32 導出的固定值」——這兩個本來都是最容易錯的地方,你都翻對了。

其中「耗盡後呼叫端不會收到任何例外」這句,在我們追過的那條路(retryable 一路重試到耗盡)上**成立**。那就拿它的**邊界**當變化題——看看這個「不丟例外」的性質是不是永遠成立。

情境:一筆訂單,`reserve()` 成功。但這次你注入的 `send()` 在**第一次呼叫**就丟出一個 `FatalError`(就是 `errors.py` 裡跟 `RetryableError` 對照的那一支,例如視為 carrier 端不可重試的拒絕),而不是 `CarrierTimeout`。

預測三件事:

1. `dispatch()` 會進入重試嗎?會 sleep 嗎?總共 call 幾次 `send()`?
2. 這個 `FatalError`,會被 `dispatch()` 或 `process()` 其中哪一層接住嗎?
3. `process()` 的呼叫端最後拿到的是什麼——一個 `Receipt`,還是一個例外?

答完這題,你這套模型的成功路徑、耗盡路徑、跟「不可重試」邊界就三條都補齊了。