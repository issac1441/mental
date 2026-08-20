我已讀完 `SKILL.md` 及其引用的三份 reference（`methodology.md`、`artifact-contract.md`、`writing-profile.md`），也讀過 `orderflow` 的全部原始碼與測試。以下依 Response contract 回覆。

---

## Context

- **Lens**：`engineer`｜**Views**：`map, mechanism, scenario, evidence`｜**Detail**：`standard`
- **選擇依據**：這是 repository 內的機制與失敗行為問題，故用 engineer 預設視角;你要「搞懂失敗行為」，所以以 mechanism + scenario 為主、map 定位、evidence 溯源。
- **重要前提**：此 workspace **目前沒有 `mental/` canonical model**。以下全部由現有原始碼即時綜合，屬 `[inferred]` 綜合，並附 `[observed]` 逐行證據。若要把它固化成可複用、可校訂的模型，建議之後執行 **`$build`**。本次為唯讀,不會建立任何檔案。

---

## Map — 系統關係

管線階段是刻意排定的:`ingest → reserve → price → dispatch`(`orderflow/pipeline.py:5`)。

兩個關鍵的正交結構決定了失敗行為:

1. **錯誤分類法**(`orderflow/errors.py`):所有例外分兩支 —
   - `FatalError`(不可重試):`ValidationError`、`UnknownSku`、`InsufficientStock`
   - `RetryableError`(可重試):`VersionConflict`、`CarrierTimeout`、`CarrierUnavailable`
2. **兩個獨立的重試迴圈**(不是一個):
   - 儲存層 `_put_with_retry`(`orderflow/inventory.py:127`)— 只重試 `VersionConflict`
   - 派送層 `dispatch`(`orderflow/dispatch.py:52`)— 只重試 `RetryableError`

終局結果有三種 `Receipt.status`:`dispatched` | `failed` | `dead_lettered`(`orderflow/pipeline.py:30-35`)。

---

## Mechanism — 保留、重試、失敗路由

### 1. 庫存保留 reserve `[observed]`

`Inventory.reserve`(`orderflow/inventory.py:54-75`)的行為:

- **冪等(idempotent)**:同一 `order_id` 若已有「未過期」的保留,直接回傳既有保留,不重扣庫存(`inventory.py:64-66`)。
- **先全驗證、再一次性提交**:`_build`(`inventory.py:93-125`)先跑一輪驗證所有 line(缺 SKU 拋 `UnknownSku`、庫存不足拋 `InsufficientStock`,`inventory.py:97-106`),**全部通過後**才進第二輪扣庫存。註解明說用意是「失敗的保留不留下需回收的部分庫存」(`inventory.py:94-95`)。
- **TTL 與 reprice**:保留存活 `RESERVATION_TTL_SECONDS = 120` 秒(`config.py:4`)。過期後再 `reserve` 會用**當前型錄價**重建,並標記 `reprice_required=True`(`inventory.py:67-71`)。
- **釋放 release**(`inventory.py:77-91`):把保留的數量加回型錄庫存,再刪除保留紀錄。

### 2. 兩層重試 `[observed]`

| 重試層 | 觸發 | 次數 | 退避 | 耗盡後 |
|---|---|---|---|---|
| 儲存 `_put_with_retry` | `VersionConflict`(樂觀併發衝突) | 3(`_PUT_ATTEMPTS`) | 無 sleep,重讀新版本再套用 | **重新拋出** `VersionConflict`(`inventory.py:133`) |
| 派送 `dispatch` | `RetryableError`(如 `CarrierTimeout`) | 3(`MAX_DISPATCH_ATTEMPTS`) | 指數退避 + 抖動 | 拋出 `DispatchExhausted`(`dispatch.py:71`) |

派送退避 `backoff_ms`(`dispatch.py:44-49`):`200ms × 2^(attempt-2) + jitter`,jitter = `crc32(order_id) % 100`(0–99ms,**同一訂單固定**)。只在第 2、3 次前 sleep,故第 2 次前 ≈200ms、第 3 次前 ≈400ms(各加固定抖動)。

### 3. 失敗路由 —「誰接住例外」決定結局 `[observed]`

這張表是回答你問題的核心:

| 階段 | 拋出的例外 | 由誰處理 | 訂單結局 |
|---|---|---|---|
| `parse_order` | `FatalError`(`ValidationError`) | pipeline `try`(`pipeline.py:45-49`) | **`failed`**(立即) |
| `reserve` | `FatalError`(`UnknownSku` / `InsufficientStock`) | pipeline `try`(`pipeline.py:51-54`) | **`failed`**(立即) |
| `dispatch` | `RetryableError` 3 次耗盡 → `DispatchExhausted` | pipeline `try`(`pipeline.py:59-67`) | **`dead_lettered`**(釋放庫存 + 進死信佇列) |
| `reserve` / `release` 寫入 | `VersionConflict` 3 次耗盡 | **無人接住**(pipeline 只 catch `FatalError`) | `[inferred]` 未處理例外逸出 |
| `dispatch` | `FatalError`(`send` 拋 fatal) | **無人接住**(dispatch 只 catch `Retryable`,pipeline 只 catch `DispatchExhausted`) | `[inferred]` 未處理例外逸出,**且不釋放庫存** |
| `price` | (目前不拋) | 未包 `try`(`pipeline.py:57`) | `[inferred]` 若拋則逸出 |

**關鍵區分**:
- **`failed`** = 一開始就判定「此訂單本質上處理不了」,立即放棄、**不重試**、不派送。
- **`dead_lettered`** = 「已盡力重試仍送不出」的優雅降級 — **庫存已釋放**、進死信佇列、呼叫端拿到的是 `Receipt` 而非例外(`pipeline.py:60-67`;`dispatch.py:5-6` 註解稱此模組「絕不默默丟棄訂單」)。

---

## Scenario — 具體失敗走查

**A. 庫存不足 → `failed`(立即,不派送)** `[observed]`
訂 `ANVIL × 5` 但只有 2 件。`_build` 在驗證階段拋 `InsufficientStock`,`reserve` 直接把它往上丟,pipeline 回 `failed`,`dispatch` 完全沒跑。測試 `o-3` 明確驗證 `calls == []`(`tests/test_pipeline.py:41-49`)。因為「先全驗證再提交」,此時沒有任何庫存被扣。

**B. 承運商一直逾時 → 重試 3 次後 `dead_lettered`** `[observed]`
`send` 每次都拋 `CarrierTimeout`。`dispatch` 試 3 次(中間退避)後拋 `DispatchExhausted`;pipeline 呼叫 `inventory.release` 把庫存加回、記入 `dead_letters`、回 `dead_lettered`。測試 `o-4` 驗證庫存從扣掉後**回到 2**(`tests/test_pipeline.py:51-63`)。

---

## Boundary or failure — 失敗行為的邊界與不對稱

這些是「整個失敗」語意下最容易誤解、且**測試未涵蓋**的地方,依重要性排列:

- **`[inferred]` 派送遇到 Fatal 會「裸奔」逸出,且庫存卡住**:`dispatch` 只接 `RetryableError`(`dispatch.py:67`),若 `send` 拋出 `FatalError`,它直接穿過 `dispatch` 與 pipeline(pipeline 只接 `DispatchExhausted`),成為未處理例外 — 而且**不會呼叫 `release`**,保留的庫存就此卡住。這既不是 `failed` 也不是 `dead_lettered`。
- **`[inferred]` 保留階段的 `VersionConflict` 耗盡也會逸出**:`_put_with_retry` 3 次後重拋 `VersionConflict`(屬 `RetryableError`),但 pipeline 的 reserve 只 `except FatalError`(`pipeline.py:53`),接不住 → 未處理例外,同樣**不是 `failed`**。
- **`[inferred]`「不留部分庫存」的保證有前提**:該保證只涵蓋**驗證期**的失敗(`inventory.py:94-95`)。若在第二輪扣庫存迴圈中途發生 `VersionConflict` 耗盡,先前幾筆 line 的扣減已提交、但保留紀錄從未寫入 → 產生無主的庫存缺口。(在目前記憶體單執行緒 store 下幾乎不會觸發,屬潛在路徑。)
- **`[inferred]` 過期重建失敗會留下舊保留**:若既有保留已過期、重建時型錄庫存已下滑而拋 `InsufficientStock`,pipeline 回 `failed`,但**舊保留紀錄仍在、其舊扣減的庫存仍被佔用**(重建路徑未走到 `release`)。
- **`[observed]` `reprice_required` 是資訊性旗標**:pipeline 其實**無條件**重新計價(`pipeline.py:56-57`),並未依此旗標分支;此為設計冗餘,非失敗來源,但易被誤讀。

---

## Evidence and gaps

**Evidence(逐項)**
- 階段順序與失敗語意總述:`orderflow/pipeline.py:1-15`
- 失敗路由:`pipeline.py:44-67`｜錯誤分類:`orderflow/errors.py:8-40`
- 保留/驗證/TTL/釋放:`orderflow/inventory.py:54-137`｜TTL 值:`orderflow/config.py:4`
- 派送重試/退避/耗盡:`orderflow/dispatch.py:22-71`｜重試上限與基準延遲:`config.py:7,10`
- 樂觀併發與 `VersionConflict`:`orderflow/store.py:29-47`
- 已涵蓋行為的測試:`tests/test_pipeline.py:41-63,71-86`

**Gaps(已知不確定與缺口)**
- **無 canonical model**:以上為即時綜合;上述 `[inferred]` 邊界尚未經人工確認,建議 `$build` 後固化與校訂。
- **邊界無測試**:上節四個 `[inferred]` 逸出/庫存卡住路徑,現有測試皆未涵蓋。
- **併發與持久化未知**:`VersionedStore` 為記憶體、單執行緒(`store.py`),`VersionConflict` 在此環境實務上難觸發;真實併發或多程序下的行為無證據。
- **`price` 失敗未建模**:目前 `pricing.py` 為純算術不拋例外,但 pipeline 未防護,屬潛在破口。

---

需要的話,我可以:(1) 針對上述某條 `[inferred]` 邊界做 `detail=deep` 的深入走查與反例;或 (2) 你若想把這套失敗模型變成可複用工件,直接進 **`$build`**。