我已看完 diff、`CHANGE_BRIEF.md`、`dispatch.py` 全文，以及 `errors.py` 的錯誤分類。以下是 review 結果。

## 實際改了什麼

**`config.py`**
- 新增常數 `CARRIER_SEND_TIMEOUT_SECONDS = 2.0`。✓ 符合核准內容。

**`dispatch.py`**
1. 新增 `_send_with_timeout()` helper：把 `send` 丟到 daemon thread 執行，`join()` 等 2 秒。thread 若還活著就丟 `CarrierTimeout`;否則把 worker 內捕捉到的原始例外重新丟出。✓
2. `dispatch()` 迴圈裡把 `send(carrier, order)` 換成 `_send_with_timeout(...)`。✓
3. **額外**在 retry 迴圈裡多加了一個 `except Exception` 分支,把所有非 `RetryableError` 的例外轉成 `CarrierTimeout` 並重試。

第 1、2 點正確實作了 brief 要的 timeout:逾時丟 `CarrierTimeout`,而 `CarrierTimeout` 本身是 `RetryableError`,會被既有的 `except RetryableError` 接住並走原本的 retry path。這部分沒問題。

## 與核准內容的出入(重點)

**問題出在第 3 點 —— 那個新增的 `except Exception` 分支超出核准範圍,而且違反這個模組的核心契約。**

```python
except RetryableError as err:
    last_error = err
except Exception as err:  # unexpected carrier failures behave like timeouts
    last_error = CarrierTimeout(str(err))
```

具體問題:

- **改變了「哪些錯誤會被重試」—— 這正是 brief 明列的 out of scope**(「Any change to which error types are retryable」)。原本只有 `RetryableError` 會重試;現在**任何**例外都會被轉成 `CarrierTimeout` 重試。

- **違反模組 docstring 的契約**:`dispatch.py` 開頭與 `errors.py` 都明講「FatalError propagates immediately / must not retry these」。改動後,若 `send` 丟出 `ValidationError`、`UnknownSku` 這類 `FatalError`(例如碰到寄件地址不合法這種重試也沒用的狀況),不會再立即往上拋,而是被吞掉、轉成 `CarrierTimeout`、重試 3 次,最後包成 `DispatchExhausted`。錯誤型別與行為都跑掉了。

- **會遮蔽程式 bug**:連 `TypeError`、`AttributeError` 這種真正「意外」的錯誤也會被當成 timeout 重試,最終以 `DispatchExhausted("gave up after 3 attempts")` 收場,`last_error` 還是個 `CarrierTimeout(str(原始錯誤))`,debug 時很難追。

- **關鍵:這個分支對 timeout 功能是多餘的。** timeout 已經由 `_send_with_timeout` 丟 `CarrierTimeout`(retryable)、走 `except RetryableError` 完成了。拿掉這個 `except Exception` 分支,brief 要的功能完全不受影響。

**建議:直接刪掉 `except Exception` 分支**,讓 fatal / 非預期例外維持原本「立即往上拋」的語義。這樣才符合「timeout only, semantics otherwise unchanged」的核准決定。

## 一個次要提醒(非 scope 出入,是實作取捨)

thread 版 timeout **無法真的取消**底下的 `send`。若某次 `send` 卡了 3 秒,會被判 timeout 而重試,但那個 daemon thread 可能稍後才跑完 —— 也就是訂單有可能被**重複送出**。模組原本標榜「never silently drops an order」,這裡反而多了「可能靜默重複」的風險。brief 沒要求取消語義,所以這不算違反核准,但如果 `send` 沒有自帶冪等/去重,值得評估。

---

**總結**:timeout 本身實作正確且符合 brief;唯一實質出入是那個超範圍的 `except Exception` 分支,它改動了重試語義、違反 FatalError 立即傳播的契約,且對功能而言是多餘的 —— 應移除。