讀完了整個 package。這是一條很清楚的訂單處理管線，進入點只有一個：`Pipeline.process(raw: dict) -> Receipt`（`orderflow/pipeline.py:44`）。整條線是**刻意排定的四個階段**，加上兩種失敗收場。

## 整體管線

```
raw dict（外部丟進來的訂單）
   │
   ▼
① parse_order ──ValidationError────────────► Receipt(failed)
   │  Order（immutable）
   ▼
② reserve ──UnknownSku / InsufficientStock──► Receipt(failed)
   │  Reservation（凍結庫存 + 單價快照 + 重量）
   ▼
③ price（只看 reservation 快照，不看原始訂單）
   │  Quote
   ▼
④ dispatch ──重試耗盡 DispatchExhausted──► 釋放庫存 + 進 dead-letter ─► Receipt(dead_lettered)
   │  DispatchResult
   ▼
Receipt(dispatched, carrier, total_cents)
```

管線的 docstring（`pipeline.py:1-15`）自己就把順序講明了：**ingest → reserve → price → dispatch**，而且順序不能換——因為單價快照歸 reservation 所有，所以一定要先 reserve 才能 price。

## 逐階段拆解

**① Ingest — `parse_order`（`ingest.py:25`）**
把 raw dict 驗證並轉成 immutable 的 `Order`（`order_id` / `region` / `lines`）。檢查項目：`order_id` 必填字串、`region` 只能是 `domestic`/`offshore`（預設 domestic）、至少要有一行、每行要有 `sku` 且 `quantity` 是 ≥1 的整數。任何一項不過就丟 `ValidationError`（屬於 FatalError）。

**② Reserve — `Inventory.reserve`（`inventory.py:54`）**
一次凍結兩樣東西：**要消耗的庫存**和**之後計價要用的單價**（外加重量）。幾個關鍵行為：
- **對 order_id 具 idempotent**：同一張單重跑，只要 reservation 還活著，就直接回傳原本那份（`inventory.py:64-67`）。
- **先全部檢查、再全部提交**：`_build`（`inventory.py:93`）先掃過每一行確認 SKU 存在、庫存足夠（不足就 `UnknownSku` / `InsufficientStock`），全部通過才真的去扣庫存——所以**失敗不會留下扣一半的爛帳**。
- **TTL 過期會重建**：預設 120 秒（`config.py:4`）。過期後用當前 catalog 重建，並打上 `reprice_required=True`，因為重抓的單價可能已經變了（`inventory.py:68-71`）。
- 寫入都走 `_put_with_retry`：撞到 `VersionConflict` 會重讀再試，最多 3 次（樂觀鎖）。

**③ Price — `price`（`pricing.py:48`）**
重點是**從 reservation 的單價快照算，不看原始訂單價**。規則（docstring `pricing.py:1-14` 有完整說明）：
- subtotal = Σ（數量 × 快照單價）
- **最多套一個折扣**：符合門檻的規則裡取 priority 最高的那個，折扣**不疊加**（`pricing.py:72`）。目前有 spring-30 和 loyalty-10 兩條。
- 稅 = round(折後金額 × 5%)，**運費不課稅**。
- 運費看的是**折扣前**的 subtotal 有沒有到免運門檻（8000_00）；到了就免運，否則平運 120_00。**折扣不影響免運資格**——這條有專門的測試守著（`tests/test_pipeline.py:32`）。

**④ Dispatch — `dispatch`（`dispatch.py:52`）**
- 先選 carrier（`dispatch.py:36`）：offshore 一律走 `air`；domestic 看總重，≤2000g 走 `post`，否則 `freight`。
- 呼叫注入進來的 `send(carrier, order)`，最多 `MAX_DISPATCH_ATTEMPTS`（3）次。
- **只重試 `RetryableError`**（CarrierTimeout / CarrierUnavailable），重試間隔是指數退避 + 依 order_id 算出的固定 jitter（`dispatch.py:44`，所以同一張單的退避時間是可重現的）。
- 全部試完還失敗 → 丟 `DispatchExhausted`（帶著 `last_error`），交回給 pipeline 去補償。

## 失敗模型（整個設計的核心）

錯誤分兩層（`errors.py`），對應到兩種收場：

| 錯誤類型 | 例子 | 結果 |
|---|---|---|
| **FatalError** | Validation / UnknownSku / InsufficientStock | 不重試，立刻回 `failed` receipt |
| **RetryableError** | VersionConflict / CarrierTimeout / CarrierUnavailable | 退避重試；dispatch 重試耗盡才 `dead_lettered` |

`dead_lettered` 這條路（`pipeline.py:61-67`）值得記住：dispatch 耗盡後，pipeline 會**把庫存釋放回 catalog**、把訂單丟進 `dead_letters` list、回一張 `dead_lettered` receipt——**而不是往外丟例外**。這條有測試驗證庫存確實還了回去（`tests/test_pipeline.py:51`）。

⚠️ 有一個縫隙值得知道：如果注入的 `send` 丟的是 **FatalError**（而非 Retryable），`dispatch` 不會接、`pipeline` 也只接 `DispatchExhausted`——所以它會變成**未處理例外往外噴**。這是「dispatch 階段的 fatal 當成程式錯誤看待」的隱含假設，不是走 receipt 那套。

## 底層 & 兩個容易誤會的點

- **VersionedStore（`store.py`）**：catalog 和 reservation 都住在同一個帶版本號的 in-memory store 上，用樂觀併發控制。這就是為什麼 inventory 裡到處是重試迴圈——寫入前要帶著讀到的版本號，對不上就 `VersionConflict`。
- **免運看折扣前金額**：直覺上會以為看實付金額，但這裡刻意看折扣前（`pricing.py:57`）。
- **`reprice_required` 目前沒有人 branch on 它**：pipeline 在 `pipeline.py:56-57` 是**一律**重新 price 的，所以這個 flag 現在比較像是「給人/給日後看的訊號」，實際流程並沒有靠它做分支判斷。如果你之後要改計價邏輯，這是個要留意的點。

要不要我再挑一條路徑（例如「過期重建 + 重新計價」或「dead-letter 補償」）跟著程式碼逐行走一遍？