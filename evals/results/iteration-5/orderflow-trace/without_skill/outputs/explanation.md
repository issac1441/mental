我已經把整個 codebase 讀完了。這是一個小而結構清楚的訂單處理管線，核心入口只有一個：`Pipeline.process(raw: dict) -> Receipt`（`pipeline.py:44`）。一筆訂單會依序走過**四個階段**，任何一步出事都會轉成一張「收據」而不是拋例外給呼叫端。

## 整體流程

```
raw dict
   │
   ▼  ① 解析驗證   parse_order()      ingest.py
 Order ───(ValidationError)──────────► Receipt(failed)
   │
   ▼  ② 庫存預留   inventory.reserve() inventory.py
 Reservation ─(UnknownSku/InsufficientStock)─► Receipt(failed)
   │   （凍結「扣的庫存」＋「單價快照」）
   ▼  ③ 計價       price()            pricing.py
 Quote
   │
   ▼  ④ 出貨       dispatch()         dispatch.py
   ├─ 成功 ─────────────────────────► Receipt(dispatched, carrier, total)
   └─ 重試耗盡(DispatchExhausted) ──► 釋放庫存 + 進死信 ► Receipt(dead_lettered)
```

管線 docstring（`pipeline.py:1-15`）特別點明**階段順序是刻意的**：計價一定排在預留之後，因為「單價快照」是由預留這一步持有的。

## 逐階段拆解

**① 解析驗證 — `ingest.py:25`**
`parse_order()` 把外部傳進來的 dict 變成不可變的 `Order`。檢查 `order_id` 必填、`region` 只能是 `domestic`/`offshore`、至少一個 line、每個 line 要有 sku 且 quantity 是正整數。任何違規都丟 `ValidationError`（屬於 `FatalError`，不重試）。

**② 庫存預留 — `inventory.py:54`**
這是最關鍵的一步，它一次凍結兩件事：**要扣的庫存** 和 **要收費的單價**。幾個重點：
- **冪等**：同一個 `order_id` 重跑，只要預留還沒過期（TTL 120 秒，`config.py:4`），直接回傳原本那筆，不會重複扣庫存。
- **過期會重建**：TTL 過了就用「當下的目錄價」重建一筆，並把 `reprice_required` 設為 True——因為單價可能已經變了（`inventory.py:68-70`）。
- **先驗證再提交**（`_build`, `inventory.py:93`）：先把每一行都查過（庫存夠不夠、SKU 存不存在），全部通過才真正扣庫存，避免留下扣一半的殘局。SKU 不存在丟 `UnknownSku`、庫存不足丟 `InsufficientStock`，兩者都是 `FatalError`。

**③ 計價 — `pricing.py:48`**
從**預留快照**算錢（不是從原始訂單），規則有幾個容易踩雷的地方：
- 折扣**最多套一個**，取「符合門檻且優先權最高」的那條，不疊加（`_select_discount`, `pricing.py:72`）。
- 稅只加在「折後商品金額」上，運費不課稅。
- **免運判斷用的是「折扣前」的商品小計**（`pricing.py:57`）。這點有兩個測試專門在守（`test_pipeline.py:32`）：一筆折後 6300 元、低於免運門檻 8000 元的單，仍然免運，因為折扣前的 9000 元已經過門檻。

**④ 出貨 — `dispatch.py:52`**
- **選運送方式**：offshore 一律空運；domestic 依總重量，超過 2000g 走貨運（freight），否則郵寄（post）（`choose_carrier`, `dispatch.py:36`）。
- **只重試 `RetryableError`**（例如 `CarrierTimeout`），用指數退避 + 每單固定 jitter（`backoff_ms`, `dispatch.py:44`），最多 `MAX_DISPATCH_ATTEMPTS`=3 次。
- 三次都失敗就丟 `DispatchExhausted`，交回給管線做補償，這個模組保證「絕不默默吞掉訂單」。

## 三種結局（Receipt）

| 狀態 | 觸發時機 | 副作用 |
|------|----------|--------|
| `dispatched` | 成功送出 | 帶回 carrier 與 total_cents |
| `failed` | 解析或預留階段的 `FatalError` | 立即失敗，不重試 |
| `dead_lettered` | 出貨重試耗盡 | **釋放已預留庫存** + 丟進 `dead_letters` 佇列（`pipeline.py:61-67`）|

死信這條路會呼叫 `inventory.release()`（`inventory.py:77`）把庫存加回目錄——這是「已經扣了庫存但最終送不出去」的補償動作，`test_dead_letter...releases_stock`（`test_pipeline.py:51`）就在驗證這件事。

## 支撐用的基礎設施

- **`store.py` — VersionedStore**：一個記憶體版的鍵值儲存，帶**樂觀鎖**。每筆記錄有 version，寫入時要帶對版本，不對就丟 `VersionConflict`（可重試）。庫存的 `_put_with_retry`（`inventory.py:127`）就是靠重讀+重試來吸收這種衝突。
- **`errors.py` — 錯誤分類法**：整個設計的骨架就是這條分界線——`FatalError`（立即失敗）vs `RetryableError`（可退避重試）。管線和出貨模組都是靠這個型別分類來決定「該重試還是該放棄」。
- **`config.py`**：所有可調參數（TTL、重試次數、稅率、免運門檻、運費、重量分界），金額一律用整數「分」。

---

補充一個讀的時候容易困惑的點：預留過期重建時會設 `reprice_required`，但管線其實**無論如何都會重新計價**（`pipeline.py:56-57` 的註解 "Always price from the ... snapshot"），所以從管線角度看，這個 flag 並沒有被 `if` 判斷用到——它比較像是留給其他呼叫端的訊號。這不是 bug，只是初看會納悶它的用途。

要不要我針對某個階段再深入（例如樂觀鎖的重試細節、或退避時間的實際數字）？