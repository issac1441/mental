讀完 skill、三個 reference 與 orderflow 全部原始碼了。下面直接回答你的三個問題。目前這個 repo 還沒有 `mental/` canonical model,所以以下是我直接讀原始碼追出來的因果(若想把這套失敗行為固化成可維護的模型,之後可以用 `$build`)。

---

保留(reservation)會為一筆訂單**一次凍結兩樣東西**:要消耗的庫存,以及當下的單價快照。它以 `order_id` 為鍵、在存活期間是**冪等**的(重複處理同一張單會拿回同一筆保留),TTL 是 120 秒;過期後會用當前 catalog 重建,並標記 `reprice_required`。系統裡有**兩個各自獨立的重試迴圈**:一個在庫存層,只針對版本衝突重試最多 3 次;另一個在派送層,針對暫時性的 carrier 錯誤做指數退避、重試最多 3 次,耗盡後把訂單丟進 dead-letter。一筆訂單的終局只有三種明確狀態——`dispatched`(成功)、`failed`(遇到不可重試的錯誤,立即失敗、不派送)、`dead_lettered`(派送重試耗盡、庫存已釋放);另外還有一個較少見的第四種:某些暫時性錯誤沒被攔截時,`process()` 會直接丟例外,連 receipt 都不給你。

## 先分清楚兩種錯誤:這是整個失敗行為的骨幹

所有失敗行為都掛在 `orderflow/errors.py` 的一個分叉上:

- **`FatalError`**(`errors.py:12`)——不可恢復,**絕不重試**。三個子類:`ValidationError`(`:20`,payload 不合法)、`UnknownSku`(`:24`,SKU 不在 catalog)、`InsufficientStock`(`:28`,庫存不足)。
- **`RetryableError`**(`errors.py:16`)——暫時性,**可以退避重試**。三個子類:`VersionConflict`(`:32`,樂觀鎖寫入衝突)、`CarrierTimeout`(`:36`)、`CarrierUnavailable`(`:40`)。

記住這條線,後面每一個「會不會重試、會變成哪種 receipt」都由「這個例外是 Fatal 還是 Retryable」決定。

## 庫存保留:先全部驗證、再全部提交,外加一個版本衝突重試

`Inventory.reserve()`(`inventory.py:54`)的流程:

1. 先查 `reservation/{order_id}`。**存在且未過期** → 直接回傳舊的(這就是冪等性,`:66`)。
2. **存在但已過期** → 用當前 catalog 重建、設 `reprice_required=True`、寫回(`:68-71`)。
3. **不存在** → 全新建立(`:73-75`)。

過期判斷在 `expired()`(`:39-41`):`now - created_at > RESERVATION_TTL_SECONDS`(120 秒,`config.py:4`)。**調大 TTL** → 保留活得更久、重建與重新計價更少,但庫存被凍結的時間也更長。

真正扣庫存的是 `_build()`(`inventory.py:93`),它刻意分兩趟:

- **第一趟只驗證**:逐行查 catalog,找不到就丟 `UnknownSku`(`:100`),庫存不夠就丟 `InsufficientStock`(`:103`)。此時**還沒動任何庫存**。
- **第二趟才提交**:逐行扣庫存並寫回,同時把 `unit_price_cents`、`weight_g` 快照進 `ReservedLine`。

這個「先驗證完再提交」的設計(見 `:94-95` 的註解)保證了一個重要不變量:**一筆在保留階段失敗的訂單,不會留下扣了一半的庫存**。

這裡有第一個重試迴圈——`_put_with_retry()`(`inventory.py:127`):寫入若撞到 `VersionConflict`,就重新讀取拿到最新 version、再試,最多 `_PUT_ATTEMPTS = 3` 次(`:21`);第 3 次還衝突就**把 `VersionConflict` 原樣拋出**。底層的樂觀鎖規則在 `store.py:29-47`:寫入時你交出的 version 必須等於現存 version,否則衝突。

## 派送:指數退避重試,耗盡就 dead-letter

第二個重試迴圈在 `dispatch()`(`dispatch.py:52`),和庫存層那個**完全獨立**:

- 迴圈跑最多 `MAX_DISPATCH_ATTEMPTS = 3` 次(`config.py:6`)。
- 每次呼叫 `send(carrier, order)`;**只攔 `RetryableError`**(`:67`)。第一次不睡,之後每次先退避。
- 退避量 `backoff_ms()`(`:44`):`200ms × 2^(attempt-2)` + 每單固定 jitter(crc32 取模 0–99ms)。所以 attempt 2 ≈ 200ms、attempt 3 ≈ 400ms,加上該訂單的固定抖動。**調大 `BASE_RETRY_DELAY_MS`** → 每次等更久;**調大 `MAX_DISPATCH_ATTEMPTS`** → 放棄前多試幾次。
- 三次都是 retryable 失敗 → 拋 `DispatchExhausted`(帶最後一個錯誤,`:71`)。

注意兩個「3」長得一樣但是**兩個不同的旋鈕、放在不同檔案**:`_PUT_ATTEMPTS`(庫存寫入,`inventory.py:21`)管的是版本衝突;`MAX_DISPATCH_ATTEMPTS`(派送,`config.py:6`)管的是 carrier 暫時性故障。

## 一筆訂單「整個失敗」的幾種情況(你最想搞懂的部分)

把 `pipeline.py:44` 的 `process()` 從頭走一遍,失敗其實分**三個嚴重度不同的層級**:

**① `failed`——立即失敗、不重試、不派送、不動庫存。** 觸發來源:
- `parse_order` 丟 `ValidationError`:`order_id` 缺、region 不是 `domestic`/`offshore`、沒有任何 line、line 缺 sku、quantity 不是正整數(`ingest.py:25-49`)。
- `reserve` 丟 `UnknownSku` 或 `InsufficientStock`(`inventory.py:100`、`:103`)。
- 這些都是 `FatalError`,由 `pipeline.py:47` 和 `:53` 攔下,回一張 `status="failed"` 的 receipt。派送**完全不會執行**(測試 `test_pipeline.py:41` 就是驗證 ANVIL 要 5、只有 2 → failed,且 `calls == []`)。

**② `dead_lettered`——重試耗盡後的「受控失敗」。** 派送三次都撞暫時性 carrier 錯誤 → `DispatchExhausted`(`dispatch.py:71`)→ `pipeline.py:61-67` 做三件事:呼叫 `inventory.release()` 把庫存還回 catalog、把訂單推進 `dead_letters` 清單、回一張 `status="dead_lettered"` 的 receipt。**這是唯一會做補償(釋放庫存)的失敗路徑**(測試 `test_pipeline.py:51`:carrier 一直 timeout,最後 ANVIL 庫存回到 2)。

**③ 未被攔截的例外——連 receipt 都沒有。** 這是最容易被忽略的一種「整個失敗」。`process()` **並不保證**每個輸入都回一張 receipt:
- `reserve` 若在 3 次寫入後仍拋 `VersionConflict`(`inventory.py:133`):它是 `RetryableError`,**不是** `FatalError`,所以 `pipeline.py:53` 的 `except FatalError` **攔不到**,例外直接往外拋。
- carrier 的 `send` 若丟出一個 `FatalError`:`dispatch()` 只攔 `RetryableError`(`:67`),而 pipeline 那層只攔 `DispatchExhausted`(`:61`),兩層都漏接 → 一樣往外拋。

所以嚴格回答「什麼情況下一筆訂單會整個失敗」:**驗證/SKU/庫存問題** → `failed`;**carrier 一直暫時性掛掉** → `dead_lettered`(有補償);**儲存層持續高度衝突,或 carrier 丟出非暫時性錯誤** → 直接例外、沒有 receipt、庫存也沒被釋放。

順帶一提:`reprice_required` 這個旗標雖然在過期重建時會被設起來,但 pipeline 並沒有針對它分支——`price()` 一律從(可能已重建的)保留快照重新計算(`pipeline.py:56-57`),所以重建後自然就是新價;這個旗標比較像是給其他消費端看的訊號。

## 一個容易誤判的邊界:過期重建會重複扣庫存 `[inferred]`

你可能會假設「同一張訂單的保留是冪等的,所以重複處理不會多扣庫存」——**在 TTL 內成立,過期後不成立**。看 `inventory.py:68-71`:保留過期時直接呼叫 `_build()` 重新扣當前 catalog 的庫存,**但沒有先把舊保留已凍結的那份庫存還回去**。後果:

- 同一張 order 過期後被重新處理,`_build` 第一趟驗證是拿「已經被自己扣過一次」的庫存去比對。若剩餘量不足,就會丟 `InsufficientStock`——**對著這張單自己正握著的庫存報「庫存不足」而整個失敗**。
- 唯一覆蓋重建路徑的測試(`test_pipeline.py:71`,WIDGET 庫存 10、只要 1)因為庫存遠大於需求而看不出問題;但重建後 catalog 其實從 9 又被扣到 8,證實了重複扣。

我標成 `[inferred]`,因為這是我讀程式碼推出的因果、目前沒有測試直接驗證,而非既有文件寫明的行為。若要處理它,那屬於 `change` 的範疇,不在這個唯讀的 `understand` 裡。

---

**Sources and gaps**
- 錯誤分類:`orderflow/errors.py:8-40`
- 保留與重試:`orderflow/inventory.py:39-41, 54-75, 93-125, 127-137`;TTL/常數 `config.py:4`、`inventory.py:21`
- 樂觀鎖:`orderflow/store.py:29-47`
- 派送與退避/dead-letter:`orderflow/dispatch.py:44-71`;常數 `config.py:6,9`
- 三種終局的控制流:`orderflow/pipeline.py:44-74`;釋放庫存 `inventory.py:77-91`
- 佐證測試:`tests/test_pipeline.py:41`(failed)、`:51`(dead_lettered + 釋放)、`:71`(過期重建)
- 缺口:並發下 `release()` 沒有重試(`inventory.py:90` 的 `put` 一旦版本衝突會直接拋);第 ③ 類未攔截例外與過期重建重複扣庫存皆為 `[inferred]`,無測試覆蓋;repo 目前無 `mental/` canonical model。

*Context: engineer lens · map,mechanism,scenario,evidence · standard —— 依「理解失敗行為」這個當前目標選定;可用 `lens= views= detail=` 調整,例如想更深入邊界條件可加 `detail=deep`。*