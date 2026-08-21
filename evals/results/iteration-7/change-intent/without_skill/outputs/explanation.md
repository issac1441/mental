我已讀完整個 orderflow 的程式。先講一個關鍵發現,它會主導整個設計:

**當訂單進到 dead-letter queue 時,它的 reservation 早就被釋放並刪除了,而 DLQ 記錄裡只留了 `{order_id, reason}`。** 所以 `force_redispatch` 本質上不是「重試上一次的 send」,而是「重新 reserve + 重新定價 + 重新 dispatch」。這個重新框架決定了下面所有考量。

看 `pipeline.py:59-67` 的 dead-letter 路徑:

```python
except DispatchExhausted as err:
    self.inventory.release(order.order_id)   # 退還庫存 + 刪除 reservation
    self.dead_letters.append(
        {"order_id": order.order_id, "reason": str(err.last_error)}  # 只留兩個欄位
    )
    return Receipt(..., status="dead_lettered", ...)
```

而 `release()`(`inventory.py:77-91`)會把庫存加回 catalog 再 `store.delete(key)`。

---

## 一、正確性 / 安全(必須解決,不解決會出事)

**1. At-most-once 出貨 —— 這是最大的風險。**
`send` 的簽章是 `Callable[[str, Order], None]`(`pipeline.py:41`),**沒有 idempotency key**。而 `CarrierTimeout` 是 *retryable*(`errors.py:36`),意思是:carrier 可能其實已經收單出貨了,只是回應逾時,訂單照樣被判 exhausted 而進 DLQ。此時 `force_redispatch` 會**重複實體出貨**。dead-lettered 的訂單恰恰是 carrier 狀態最曖昧的一批。要讓這個功能安全,前提幾乎是先把 idempotency key 一路帶進 `send`,否則手動重送 = 手動製造重複出貨。

**2. reservation 已經不存在了。**
redispatch 無法重用舊的 reservation(已被 `release()` 刪掉),必須重新取得一個。這帶出下面的 3、C 區。

**3. DLQ 記錄是有損的 —— 連 carrier 都算不出來。**
`dispatch()` / `choose_carrier()` 需要 `Order`(要 `order.region`)和 `Reservation`(要每行的 `weight_g`)。但:
- `region` **只存在於 `Order` 物件上**,reservation 和 DLQ 記錄都沒有它。`choose_carrier` 的 `if order.region == "offshore": return "air"`(`dispatch.py:38`)在重送時**無法還原**。
- DLQ 只有 `order_id` + `reason`。

所以 `force_redispatch(order_id)` 只拿 order_id 是**資訊不足**的。必須擇一:(a) 把 DLQ 記錄補上 `order`(或至少 region + lines);(b) 另建 order store;(c) 讓呼叫端重新提供 raw order。這是這個 API 簽章本身的根本張力。

**4. force_redispatch 自身的冪等性。**
`dead_letters` 是 `list[dict]`,同一個 order_id 可能有**重複條目**(同 id 被處理兩次都失敗)。要考慮:重複呼叫、order_id 根本不在 DLQ 上、以及成功後「要移除哪一筆」。需要一個 guard(確認確實在 DLQ、且處理中/成功後從 DLQ 移除)來避免二次出貨。

---

## 二、要保住的既有語意(對應你說的「不改變現有失敗語意」)

**5. 讓它是純加法。** 不要動 `process()` / `dispatch()` 的失敗路徑。現有的兩條失敗語意要原封不動:
- FatalError(validation / UnknownSku / InsufficientStock)→ 立即 `failed`,不重試、不進 DLQ。
- Retryable 耗盡 → `dead_lettered`(release + DLQ append + receipt)。

**6. 但「重新 reserve」會引進新的失敗模式,而這些模式的處理不能污染舊語意:**
- 重新 reserve 可能 `InsufficientStock` / `UnknownSku`(FatalError)—— 因為庫存已被退還、可能被別人吃掉,或 catalog 改了。
- 重新 reserve 可能讓 **`VersionConflict`(RetryableError)往外拋**:`reserve()` 在 `_put_with_retry` 三次後會 `raise`(`inventory.py:133`),而 `process()` 只在 reserve 外面接 `FatalError`、**沒接 RetryableError**(`pipeline.py:52-54`)。你的新路徑會踩到這個既有的尖角,要明確決定怎麼收斂。

**7. 重送又耗盡怎麼辦?** 要不要再 dead-letter 一次(=DLQ 又多一筆)?必須定義清楚,別變成靜默丟單或重複 append。

---

## 三、定價 / 庫存後果

**8. 重新 reserve 會用「當下的 catalog 價格」重抓,總額可能跟原本報價不同。** 而且有個陷阱:正常流程裡 TTL 過期重建才會設 `reprice_required=True`(`inventory.py:68-69`);但 redispatch 是**全新** reservation,`reprice_required` 會是 `False` —— 系統原本用來警示價格漂移的訊號**不會亮**。需決定:沿用原報價還是接受 reprice。(注意原始 `Quote` 也沒被保存,想沿用得先存起來。)

**9. 庫存可能已經不夠。** 退還的庫存可能被後續訂單消耗,重送時湊不齊。

---

## 四、API 形狀 / 回傳

- **10.** 放在哪:最自然是 `Pipeline` 的 method(需要 `self.inventory / self.send / self.dead_letters`)。
- **11.** 回傳型別:為了一致性回 `Receipt`。但要小心 —— 沿用現有三個 status 才不會打破依 status 分支的消費端;若加新 status 是相容性風險。且 `total_cents` 沒 reprice 就填不出來。
- **12.** 簽章矛盾:`force_redispatch(order_id)` 只有 id,卻需要 `Order`(見第 3 點)。這點要先拍板,其餘設計才站得住。

---

## 五、並行 / 維運

- **13.** store 是樂觀鎖,catalog 被並行改動時 `VersionConflict` 會冒出來(見第 6 點)。
- **14.** 若直接複用 `dispatch()`,你會繼承**真實會 sleep 的 3 次重試迴圈**(`dispatch.py:61-63`,預設 `time.sleep`)。手動維運動作要不要這樣阻塞?或改成單次嘗試 / 不同的 attempt 預算?
- **15.** 稽核:目前**完全沒有 log / 稽核軌跡**。手動重送死信是敏感維運操作(誰、何時、為何、結果),而且 `Receipt` 無法區分「原始出貨」與「強制重送」。至少該留一筆。

---

## 六、測試

新增:重送成功會從 DLQ 移除、重送時庫存不足、order_id 不在 DLQ、重複呼叫的冪等、重送又耗盡的行為;並且**證明既有的失敗語意測試(`test_insufficient_stock_fails_without_retry`、`test_dead_letter_after_exhausted_retries_releases_stock`)一字不改仍通過**。重複出貨風險(第 1 點)在沒有 carrier idempotency 前無法被測試涵蓋,要以文件標記。

---

## 我的建議

最小又安全的設計會是:

1. **先把 DLQ 記錄補成 additive 的**(加上 `order` 物件與最後的 `quote`,舊欄位不動)—— 解掉第 3、8、12 點。
2. **`force_redispatch` 做成 `Pipeline` method**,流程:確認在 DLQ → 重新 `reserve`(明確處理 InsufficientStock / VersionConflict,不進舊 DLQ 語意)→ 重新 `dispatch` → 成功才從 DLQ 移除、回 `Receipt`。
3. **在 `send` 加 idempotency key** 作為安全前提(否則就只能在文件與回傳上大聲標註重複出貨風險)。
4. `process()` / `dispatch()` / 現有測試**完全不動**。

要不要我針對其中一種拍板方向(例如「DLQ 存 order + 沿用原報價 + 單次嘗試 + 從 DLQ 移除」)寫出具體實作與測試?我也可以先只做第 1 步的 DLQ enrich,把地基鋪好再談重送。