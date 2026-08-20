讀完整個 package 了。這是一個小而完整的訂單處理 pipeline，核心是 `orderflow/pipeline.py` 的 `Pipeline.process()`，它把一筆 raw dict 依序推過四個階段。我先給你整體圖像，再逐段拆解。

## 整體流程

進入點是 `pipeline.py:44` 的 `process(raw: dict) -> Receipt`。刻意的階段順序是 **ingest → reserve → price → dispatch**：

```
raw dict
  │
  ▼  parse_order        (ingest.py)    ──fail─▶ Receipt(status="failed")   ← ValidationError
  │   Order(order_id, region, lines)
  ▼  inventory.reserve  (inventory.py) ──fail─▶ Receipt(status="failed")   ← UnknownSku / InsufficientStock
  │   Reservation(庫存+單價快照)
  ▼  price              (pricing.py)   （沒有失敗分支）
  │   Quote(total_cents)
  ▼  dispatch           (dispatch.py)  ──retry耗盡─▶ 釋放庫存 + 進 dead_letters → Receipt(status="dead_lettered")
  │   DispatchResult(carrier)
  ▼
Receipt(status="dispatched", carrier, total_cents)
```

最後一律回傳一個 `Receipt`（`pipeline.py:29`），狀態只有三種：`dispatched` / `failed` / `dead_lettered`——**呼叫端永遠拿到收據，不會吃到例外**。

## 逐段拆解

**1. Ingest — 解析與驗證（`ingest.py:25`）**
把 raw dict 轉成 immutable 的 `Order`。檢查 `order_id`（必填、須為 str）、`region`（只允許 `domestic` / `offshore`，預設 domestic）、至少一個 line、每個 line 的 sku 與正整數 quantity。任何一項不過就丟 `ValidationError`（屬 Fatal），pipeline 立刻回 `failed`（`pipeline.py:47`）。

**2. Reserve — 預留庫存並凍結單價（`inventory.py:54`）**
這一段做兩件事：**扣住庫存**，同時**把當下的單價與重量快照進 `ReservedLine`**。幾個關鍵點：
- **Idempotent per order_id**：同一張單重跑，只要 reservation 還沒過期就回傳原本那筆（`inventory.py:64`）。
- **過期會重建**：超過 `RESERVATION_TTL_SECONDS`（120 秒）就用當前 catalog 重建，並標記 `reprice_required=True`（`inventory.py:68`），因為單價可能變了。
- **先驗證全部、再一次提交**（`_build`, `inventory.py:93`）：先掃過所有 line 確認 SKU 存在（否則 `UnknownSku`）、庫存夠（否則 `InsufficientStock`），全部通過才真的去扣庫存。這樣**失敗的預留不會留下扣一半的庫存**。
- 寫入走樂觀鎖，碰到 `VersionConflict` 會重讀重試最多 3 次（`_put_with_retry`, `inventory.py:127`）。

失敗（`UnknownSku` / `InsufficientStock`，都是 Fatal）→ pipeline 回 `failed`。

**3. Price — 從快照計價（`pricing.py:48`）**
**一律用 reservation 的快照計價，而不是 raw order**——這就是為什麼計價排在預留之後（`pipeline.py:56`）。規則：
1. 小計 = Σ(預留數量 × 快照單價)。
2. 折扣至多一條，取「門檻有達到、priority 最高」的那條，**不疊加**（`spring-30` 30%/門檻 5000 元/priority 20 勝過 `loyalty-10`）。
3. 稅金只對折後小計課，運費不課稅。
4. 免運看的是**折扣前**小計是否達 `FREE_SHIPPING_THRESHOLD`；折扣不影響免運資格。

（test 裡的 happy path 可驗證：3 × $3000 = $9000 → spring-30 折成 $6300 → 稅 $315 → 折扣前 $9000 已達免運 → 合計 $6615。）

**4. Dispatch — 選 carrier 並帶重試出貨（`dispatch.py:52`）**
- 選 carrier（`dispatch.py:36`）：offshore 一律 `air`；否則算總重，≤ 2000g 走 `post`，超過走 `freight`。
- 重試迴圈最多 `MAX_DISPATCH_ATTEMPTS`（3）次，第 2 次起先 sleep。退避是 `BASE * 2^(attempt-2)` 再加一個依 order_id crc32 算出的 0–99ms 抖動（`backoff_ms`, `dispatch.py:44`），所以同一張單的延遲是**確定性**的。
- **只重試 `RetryableError`**（如 `CarrierTimeout`）；Fatal 直接往上拋。三次都失敗就丟 `DispatchExhausted`。
- pipeline 接到 `DispatchExhausted` 後做補償（`pipeline.py:61`）：**把庫存釋放回 catalog**、把單丟進 `dead_letters`、回 `dead_lettered`。

## 貫穿全局的兩個底層概念

- **錯誤分類是整條 pipeline 的骨架（`errors.py`）**：`FatalError`（Validation / UnknownSku / InsufficientStock）= 立刻失敗、不重試；`RetryableError`（VersionConflict / CarrierTimeout / CarrierUnavailable）= 退避重試。哪裡重試、哪裡放棄，全看這個分類。
- **VersionedStore 樂觀併發（`store.py`）**：catalog 和 reservation 都存在同一個帶 version 的 store 裡；寫入要帶著讀到的 version，不符就丟 `VersionConflict`（可重試）。這是 reserve/release 能安全並發的基礎。

## 幾個幫助理解的細節

- **計價沒有失敗分支**——`price()` 一定會產出 `Quote`，所以計價階段不會讓訂單失敗。
- **`reprice_required` 這個旗標在目前 pipeline 其實沒被讀取**：因為 `process()` 無論如何都會重新 `price(reservation)`（`pipeline.py:57`），所以重建後重算是「自動」發生的，旗標比較像是留給其他呼叫端的訊號。
- **Idempotency 的邊界只到 reserve**：reserve 對同一 order_id 是冪等的，但 `dispatch` 的 `send()` 副作用不是——若在 reservation 還存活時重跑同一張單，會回傳同一筆預留、但 `send()` 會再被呼叫一次。這在追出貨相關問題時值得記著。

需要的話我可以幫你畫一張狀態機圖（三種 Receipt 狀態的所有轉移路徑），或針對某一段（例如樂觀鎖重試、或折扣/免運的邊界條件）再深入。