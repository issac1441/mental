我已讀完 skill 引用的三個 reference,以及 `orderflow/` 全部原始碼、`README.md` 與測試。以下依 methodology 的「說明形狀」組織,把一筆訂單從進來到出貨的因果鏈追一遍。

---

一筆訂單由單一入口 `Pipeline.process(raw)`(`orderflow/pipeline.py:44`)驅動,固定走四個刻意排定的階段:**ingest(解析驗證)→ reserve(鎖庫存並凍結單價)→ price(依凍結快照算總價)→ dispatch(選承運商並帶重試出貨)**。每一筆訂單最終只會落到三種 `Receipt` 結果之一:`dispatched`(出貨成功)、`failed`(前段致命錯誤,不重試)、`dead_lettered`(出貨重試用盡,已退庫存並進死信佇列)。定價排在鎖庫存「之後」是設計重點——因為要收的單價快照是由 reservation 持有的,而不是即時目錄。

我用測試裡的 happy path 訂單 `o-1`(3 × `WIDGET`,單價 300000 分、庫存 10、重 500g)當作貫穿全程的例子。

## 第一關:ingest —— 把 raw dict 變成合法 `Order`

`parse_order(raw)`(`orderflow/ingest.py:25`)做純驗證,不碰任何狀態:

- `order_id` 必須是非空字串,否則 `ValidationError`。
- `region` 預設 `"domestic"`,只允許 `{"domestic", "offshore"}`。
- `lines` 不可為空;每行的 `sku` 要是字串、`quantity` 要是正整數。

任何一項不過就丟 `ValidationError`(屬於 `FatalError`)。`process` 在 `pipeline.py:47` 接住它,直接回傳 `status="failed"` 的收據——**這裡不會有任何副作用要回收**,因為還沒動到庫存。`o-1` 通過後得到 `Order(order_id="o-1", region="domestic", lines=(Line("WIDGET", 3),))`。

## 第二關:reserve —— 一次凍結「庫存」與「單價」兩件事

`Inventory.reserve(order)`(`orderflow/inventory.py:54`)是整個流程狀態變化的核心。它做三件事:

1. **先全檢、後提交**。`_build`(`inventory.py:93`)會先把每一行都查一遍:目錄查不到 SKU → `UnknownSku`;庫存不足 → `InsufficientStock`(兩者皆 `FatalError`)。**全部通過後**才真正逐行把 `stock` 扣掉。所以一筆多行訂單不會出現「扣了一半才失敗」的殘留庫存。`o-1`:庫存 10 ≥ 3,扣成 7,並把當下的 `price_cents`、`weight_g` 快照進 `ReservedLine`。
2. **同一 `order_id` 具冪等性**。若已存在且未逾時的 reservation,直接回傳舊的(`inventory.py:64`);重跑同一筆訂單不會重複扣庫存。
3. **逾時會重建並標記 `reprice_required`**。超過 `RESERVATION_TTL_SECONDS`(120 秒,`config.py:4`)後,reservation 會用「當前目錄價」重建,單價快照因此可能改變(`inventory.py:66-70`)。

底層存取都走 `VersionedStore`(`orderflow/store.py`):每筆記錄帶版本號,寫入要帶對版本,否則丟 `VersionConflict`(可重試)。`_put_with_retry`(`inventory.py:127`)就是為此對樂觀鎖做最多 3 次重讀重試。若 reserve 拋 `FatalError`,`process`(`pipeline.py:53`)一樣回 `status="failed"`。

## 第三關:price —— 只認 reservation 快照,不認即時目錄

`price(reservation)`(`orderflow/pricing.py:48`)在 `pipeline.py:57` 被**無條件**呼叫,且只吃 reservation 的凍結單價。規則有四條,`o-1` 正好踩到最容易誤會的兩條:

- **貨品小計** = Σ 數量 × 快照單價 = 3 × 300000 = 900000 分。
- **折扣至多一條、不疊加**:取「達到門檻且優先權最高」的一條(`pricing.py:72`)。`o-1` 兩條都符合,選 priority 較高的 `spring-30`(30%)。折扣 = 900000 × 30 // 100 = 270000,折後 630000 分。
- **稅只加在折後貨品上,不加在運費**:tax = round(630000 × 0.05) = 31500 分(`pricing.py:55`)。
- **免運看「折扣前」小計**:900000 ≥ `FREE_SHIPPING_THRESHOLD_CENTS`(800000,`config.py:16`)→ 免運。注意折後的 630000 其實低於門檻,但資格是用折扣前判定的(`pricing.py:57`,`test_free_shipping_uses_pre_discount_subtotal` 專門鎖這條)。

`o-1` 總價 = 630000 + 31500 + 0 = **661500 分**,和 `test_happy_path_dispatches_with_totals` 斷言的 `6615_00` 一致。

## 第四關:dispatch —— 選承運商 + 有界重試

`dispatch(order, reservation, send)`(`orderflow/dispatch.py:52`):

- **選承運商**(`choose_carrier`,`dispatch.py:36`):offshore 一律 `"air"`;否則算總重,≤ `POST_MAX_WEIGHT_G`(2000g)走 `"post"`,超過走 `"freight"`。`o-1` 為 domestic、總重 1500g → `"post"`。
- **重試迴圈**:最多 `MAX_DISPATCH_ATTEMPTS`(3)次呼叫 `send(carrier, order)`。**只有 `RetryableError`(如 `CarrierTimeout`)會重試**;重試前依 `backoff_ms` 退避——`BASE * 2^(attempt-2)` 加上用 `crc32(order_id)` 算出的 0–99ms 決定性抖動(`dispatch.py:44`)。
- 三次都失敗就丟 `DispatchExhausted`。`process`(`pipeline.py:60`)接住後做補償:`inventory.release()` 把庫存加回目錄、把訂單推進 `dead_letters`,回 `status="dead_lettered"`。`test_dead_letter_after_exhausted_retries_releases_stock` 驗證了退庫存(ANVIL 從 0 回到 2)。

`o-1` 的 `send` 不丟錯,第一次即成功,回 `Receipt(status="dispatched", carrier="post", total_cents=661500)`。

## 三種結局怎麼分,以及一個要小心的邊界

把上面收斂起來,`process` 只會回三種 `Receipt`:

| 結果 | 觸發 | 副作用回收 |
|---|---|---|
| `dispatched` | send 在 ≤3 次內成功 | — |
| `failed` | ingest 或 reserve 拋 `FatalError` | 不需要(尚未扣庫存 / 或全檢後才提交) |
| `dead_lettered` | dispatch 的 `RetryableError` 用盡 | `release()` 退回庫存 + 進死信佇列 |

**要避免的過度概括:`process` 並非「一定回傳 `Receipt`」。** 它只接住 `DispatchExhausted`(`pipeline.py:60`),而 `dispatch` 只重試 `RetryableError`(`dispatch.py:67`)。因此若 `send` 在出貨階段拋出 `FatalError` 或其他非 `RetryableError` 例外,它會一路穿過 `dispatch` 與 `process` 拋給呼叫端——而且此時 reservation 已扣了庫存卻不會被 `release()`。這是從控制流可直接推得的行為邊界,雖然現有測試裡的 `send` 不會這樣做。

另一個小提醒:`reprice_required` 這個旗標在 reserve 逾時重建時會被設上,但 `process` 是**無條件**呼叫 `price` 的(`pipeline.py:56` 註解也這麼說),整個 codebase 沒有任何地方讀取這個旗標。它目前是給尚未存在的外部消費者用的訊號,不影響本流程的分支。

---

想更深的話,我可以單獨深挖任一關——例如 `VersionedStore` 的樂觀併發與 `_put_with_retry` 的競態、`backoff_ms` 的抖動推導、或折扣/免運/稅的所有邊界值,給到含替代設計與逐行證據的 `deep` 版本。

目前這個 workspace 還**沒有** canonical 的 `mental/` 模型;若你想把這份理解固化成可維護、可被引用的模型,可以用 `$build` 建立(我不會自動建立任何檔案)。

---

**Sources and gaps**
- 入口與三種結局:`orderflow/pipeline.py:44-74`;錯誤分類:`orderflow/errors.py`
- 各關:`ingest.py:25`、`inventory.py:54`/`93`/`127`、`pricing.py:48`/`72`、`dispatch.py:36`/`44`/`52`
- 狀態底層:`store.py:29`(版本化寫入);參數:`config.py`
- 行為佐證:`tests/test_pipeline.py`(happy path 總價、免運用折扣前小計、缺貨不重試、死信退庫存、退避、逾時重建)
- Gaps:`send` 由呼叫端注入,真實承運商整合不在 repo 內;`reprice_required` 無消費端;儲存僅記憶體內、無持久化;時間走 `time.monotonic()`。

*Context: engineer lens · map,mechanism,scenario,evidence · standard —— 這是從本 repo 發問的流程追蹤題,engineer 為情境預設;要調整用 `lens=` `views=` `detail=`。*