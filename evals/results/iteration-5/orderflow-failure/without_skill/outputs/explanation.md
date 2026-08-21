讀完整條管線了。我把庫存保留、重試、還有失敗行為完整講一遍 —— 特別是最後幾個「失敗行為跟文件宣稱不一致」的地方，因為那正是你想搞懂的重點。

## 整條管線的順序

`ingest → reserve → price → dispatch`（`pipeline.py:44`）。錯誤被切成兩類（`errors.py`）：

- **`FatalError`**：`ValidationError`、`UnknownSku`、`InsufficientStock` —— 不重試，立刻失敗。
- **`RetryableError`**：`VersionConflict`、`CarrierTimeout`、`CarrierUnavailable` —— 可以退避重試。

## 1. 庫存保留怎麼運作（`inventory.py`）

`reserve(order)` 以 `reservation/{order_id}` 為 key，行為分三種（`inventory.py:54`）：

- **有保留、還沒過期** → 直接回傳舊的，不再扣庫存（idempotent，同一 order_id 重放安全）。
- **有保留、已過期**（超過 `RESERVATION_TTL_SECONDS=120s`）→ 用目前的 catalog **重建**，設 `reprice_required=True`（因為單價快照可能變了），管線之後會照重建的快照重新計價。
- **沒有保留** → 直接建一個新的。

建立時 `_build()` 是**兩階段**（`inventory.py:93`）：先把每一行都驗過（SKU 不存在 → `UnknownSku`；庫存不足 → `InsufficientStock`），**全部通過**才進第二個迴圈逐行扣庫存。註解說這樣「失敗的保留不會留下要回捲的半套庫存」。

## 2. 兩種重試

**(a) 儲存層** `_put_with_retry`（`inventory.py:127`）：寫入 `VersionedStore` 撞到 `VersionConflict`（樂觀鎖版本不符）時，重讀版本再試，最多 `_PUT_ATTEMPTS=3` 次，還是失敗就把 `VersionConflict` 拋出去。

**(b) 派送層** `dispatch`（`dispatch.py:52`）：只重試 `RetryableError`，最多 `MAX_DISPATCH_ATTEMPTS=3` 次，指數退避 `200ms → 400ms` 再加每單固定 jitter（`dispatch.py:44`）。三次都失敗 → 拋 `DispatchExhausted`。

## 3. 一筆訂單會「整個失敗」的情況 —— 設計上的三種終態

`process()` 回傳的 `Receipt.status` 有三種結局：

| 情況 | status | 發生什麼 |
|------|--------|---------|
| parse 或 reserve 拋 `FatalError`（欄位不合法／SKU 不存在／庫存不足） | `"failed"` | 立刻失敗，**dispatch 完全沒跑** |
| dispatch 三次重試耗盡（carrier 一直 timeout/unavailable） | `"dead_lettered"` | **釋放保留**、丟進 dead-letter queue、回 receipt（不丟例外） |
| 一路成功 | `"dispatched"` | 帶 carrier 與 total |

所以「乾淨的整個失敗」只有兩條：**fatal → `failed`**，或 **重試耗盡 → `dead_lettered`**。

---

## 4. ⚠️ 但有幾個失敗行為跟文件宣稱不一致

這是我覺得你最該知道的部分 —— 有三個地方，實際失敗行為跟 docstring 講的不一樣：

**B. 過期重建會「重複扣庫存」（庫存洩漏）**
`reserve()` 走過期分支時，直接呼叫 `_build()` 再扣一次庫存，**沒有先 `release()` 把舊保留的量還回去**（`inventory.py:68`）。同一張單過期後被重放，庫存就被扣兩次。

這在現有測試裡就看得到 —— `test_expired_reservation_is_rebuilt_and_flags_reprice`：WIDGET 起始庫存 10，第一次 reserve 扣到 9，過期重建又扣到 **8**，但那張單實際只該佔 1 個。測試只斷言 `reprice_required=True`，沒檢查庫存，所以照樣綠燈。庫存越扣越少，甚至可能讓後續重放誤觸 `InsufficientStock`。

**A. reserve 提交到一半撞 `VersionConflict` → 半套扣庫存 + 未被攔截的例外**
`_build` 第二個迴圈逐行寫入，如果第一行已提交、第二行 `_put_with_retry` 三次都失敗，會拋出 `VersionConflict`。但 `VersionConflict` 是 `RetryableError`，而 `pipeline.py:53` 的 reserve 只 `except FatalError` —— 於是這個例外**直接穿出 `process()`**（不是回 receipt）。而且此時保留記錄根本還沒寫入（`reserve()` 在 `_build` 回傳後才存 reservation key），第一行扣掉的庫存**沒有 key 可以 `release`**，永久漏掉。這正好違反 `_build` 註解宣稱的「不留半套庫存」—— 那個保證只對「驗證階段」的失敗成立，對「提交階段」的 `VersionConflict` 不成立。

**C. dispatch 期間的 `FatalError` → 保留沒釋放、也沒包成 receipt**
`dispatch` 只攔 `RetryableError`，`send()` 若拋 `FatalError` 會往上穿（`dispatch.py:67` 設計如此）。但 `pipeline.py:59` 只 `except DispatchExhausted`，所以這個 fatal 同樣**穿出 `process()`**，而且**保留沒被釋放**。對比其他所有 fatal 路徑都會回 `"failed"` receipt，這裡是不一致的破口（庫存留在保留狀態）。

---

**小結**：正常設計下，訂單失敗只會是 `failed`（fatal，dispatch 沒跑）或 `dead_lettered`（重試耗盡，有釋放庫存）兩種乾淨終態。但有三個邊界會讓「失敗」變成**未被攔截的例外 + 庫存洩漏**：過期重建重複扣（B）、reserve 提交半途版本衝突（A）、dispatch 期間的 fatal（C）。B 目前現有測試就能佐證。

要不要我幫你針對其中某一個寫個能重現的測試，或看看修法？