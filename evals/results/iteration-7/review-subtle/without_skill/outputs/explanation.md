Review 完成。核心結論:**2 秒 timeout 本身有正確實作,但 diff 夾帶了一個超出核准範圍的語義改動**,踩到 brief 明列的兩條「不在範圍」。

## 實際改了什麼

**`config.py`**
- 新增 `CARRIER_SEND_TIMEOUT_SECONDS = 2.0`(config.py:12-13)

**`dispatch.py`**
- import `threading`、`CarrierTimeout`(dispatch.py:11, 18)
- 新增 `_send_with_timeout()`(dispatch.py:53-71):把 `send` 丟到 daemon thread 跑,`join(2s)`;若 thread 還活著 → raise `CarrierTimeout`;否則把 thread 內抓到的例外重新 raise
- dispatch 迴圈把 `send(...)` 換成 `_send_with_timeout(...)`(dispatch.py:87)
- **新增 `except Exception` 分支**(dispatch.py:91-92):把任何「非 `RetryableError`」的例外包成 `CarrierTimeout` 存進 `last_error`

## 符合核准的部分 ✓

「2 秒沒回應 → 當成 `CarrierTimeout` → 走既有 retry path」這條實作正確:`CarrierTimeout` 是 `RetryableError`(errors.py:36),真正超時走的是 `except RetryableError`(dispatch.py:89)那條,行為符合 brief。

## 跟核准內容的出入 ⚠️

**1. `except Exception`(dispatch.py:91-92)超出範圍,同時踩到兩條「不在範圍」**

Brief 明列不得動:「哪些 error type 可重試」與「dead-letter 行為」。但這個分支兩條都動到了:

- 原本只有 `RetryableError` 會重試,`FatalError`(`ValidationError` / `UnknownSku` / `InsufficientStock`)與任何非 `OrderError` 例外都會**立即往外拋**(dispatch.py 開頭 docstring 就寫「FatalError propagates immediately」)。改完後這些全被接住、包成 `CarrierTimeout`、變成可重試。
- **具體後果**:若 `send` 丟出 `FatalError`,原本會直接往外傳(fail-fast);現在會重試 3 次後以 `DispatchExhausted` 拋出,`pipeline.py:61` 接到後會**釋放庫存 + 丟進 `dead_letters` + 回 `dead_lettered` 收據**。本來該 fail-fast 的訂單現在被 dead-letter 了——正是 brief 說不能動的 dead-letter 行為。
- **附帶壞處**:`send` 裡真正的程式 bug(`KeyError`/`TypeError` 等)會被吞掉、誤標成 `CarrierTimeout`,白白重試 3 次 + backoff,並遮蔽真正的錯誤,難除錯;operator 看到的錯誤型別也從原型別變成 `CarrierTimeout`。

dispatch.py:91 的註解「unexpected carrier failures behave like timeouts」正好說明作者是**刻意**這樣寫,但這不是 brief 核准的——brief 只核准「2 秒沒回應」當 timeout。

補充:**現有測試抓不到這個**。`test_pipeline.py` 只覆蓋 `send` 丟 `CarrierTimeout`(RetryableError)的情況(test_pipeline.py:52-53),沒覆蓋 `send` 丟 `FatalError`/其他例外,所以測試照過,問題被藏住。

**2.(次要,實作面風險)thread 無法取消 → 可能重複出貨**

超時後 raise `CarrierTimeout` 並重試,但原本那個 `send` 還在 daemon thread 裡繼續跑。若那個慢 `send` 其實成功送達,retry 又送一次 → 可能 **double dispatch**,最多 3 個背景 send 疊著跑。brief 沒提冪等性,但 carrier send 是有副作用的動作,值得確認 `send` 是否冪等 / 此風險可否接受。這是 Python 對 blocking call 做 timeout 的固有限制。

## 建議修法(若要嚴格貼齊 brief)

把 dispatch.py:91-92 的 `except Exception` 分支**移除**,讓 `_send_with_timeout` 只負責「超時 → `CarrierTimeout`」,其餘例外維持原傳遞語義(`RetryableError` 重試、其他往外拋)。這樣就完全等同 brief:**只加 timeout,其他語義不變**。

小事一件(無害):`outcome["ok"] = True`(dispatch.py:59)設了之後從沒被讀。

---

要我直接把 `except Exception` 那段拿掉、讓 diff 收斂回 brief 範圍嗎?