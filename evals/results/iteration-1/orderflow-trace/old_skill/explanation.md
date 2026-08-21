我已讀完 `SKILL.md` 及其引用的三份 reference,並讀過整個 orderflow codebase(8 個模組 + 測試 + README)。以下依 understand skill 的 response contract 回答。

---

## Context

- **Lens**：`engineer`(儲存庫問題的 scope 預設)
- **Views**：`map, mechanism, scenario, evidence`(engineer 預設;正好對應「追蹤一條端到端流程」的需求)
- **Detail**：`standard`
- **選擇依據與不確定性**:這是對本 repo 執行流程的追蹤問題,沒有 manual override、沒有指定其他角色,故採 repo 預設 lens 與其預設 views。不確定你要的是「概念總覽」還是「能預測每個分支的深度」——若要,我可對任一 stage 展開成 `deep`。
- **目前 workspace 沒有 canonical mental model**(`mental/` 不存在)。以下內容全部直接讀自目前 repo:`[observed]` 表示程式碼/docstring 直接支持,`[inferred]` 是我的綜合、**尚未經你確認**。若要把它固化成可累積、可被 review 的模型,建議跑 `$build`(本次為唯讀,我沒有建立任何檔案)。

---

## Map — 元件與關係

整體是一條**線性四段 pipeline**,外加一條共用主幹(reservation)與一條橫切規則(error taxonomy)。

```
raw dict ──> parse_order ──> Inventory.reserve ──> price ──> dispatch ──> Receipt
             (ingest)        (庫存+價格快照)      (算錢)     (選 carrier+送出)
```

`[observed]` 入口是 `Pipeline.process(raw: dict) -> Receipt`(`pipeline.py:44`);stage 順序刻意固定,docstring 明講「ingest → reserve → price → dispatch」(`pipeline.py:3-14`)。

**主幹是 `Reservation`**,它同時凍結兩件事——扣下的 stock 與 unit-price 快照。下游都讀它:

| 元件 | 讀什麼 | 寫什麼 |
|---|---|---|
| `price` (`pricing.py:48`) | reservation 的**單價快照** | — |
| `dispatch` (`dispatch.py:52`) | reservation 的**重量**(選 carrier)| 透過注入的 `send` 送出 |
| `Inventory` (`inventory.py`) | `catalog/*` | `reservation/*`、扣/還 `catalog/*` 的 stock |

**橫切規則**:`errors.py` 把所有錯誤分成 `FatalError`(立即失敗、不重試)與 `RetryableError`(退避重試)兩支(`errors.py:8-41`)。這條分類決定了每一站失敗時的行為。

**底層**:`VersionedStore` 用 optimistic concurrency 存 catalog 與 reservation(`store.py`);`config.py` 是所有旋鈕(TTL、重試次數、稅率、免運門檻、運費、post 重量上限)。

---

## Mechanism — 因果鏈(逐段)

**1. Ingest — `parse_order`(`ingest.py:25`)**
raw dict → `Order`。檢查 order_id、region ∈ {domestic, offshore}(預設 domestic)、至少一條 line、每條 line 的 sku 與 quantity ≥ 1。任一違規丟 `ValidationError`(FatalError)。`process` 接住 → `Receipt(status="failed")`(`pipeline.py:45-49`);此時 id 用 `str(raw.get("order_id"))`,因為 Order 還沒建成。

**2. Reserve — `Inventory.reserve`(`inventory.py:54`)**,key = `reservation/{order_id}`
- `[observed]` **冪等**:同一 order_id 若已有且未過期 → 直接回舊 reservation,**不重扣庫存**(`inventory.py:64-67`)。
- 過期 → 用**當前** catalog 重建,並設 `reprice_required=True`(`inventory.py:68-71`)。
- `_build`(`inventory.py:93`)採「**先全部檢查、再全部提交**」:任一 SKU 不存在丟 `UnknownSku`、庫存不足丟 `InsufficientStock`(皆 FatalError)——所以失敗**不會留下半扣的庫存**。通過後才逐條扣 stock、把單價與重量收進 `ReservedLine`。
- 寫入走 `_put_with_retry`,對 `VersionConflict`(retryable)重試 3 次(`inventory.py:127-137`)。
- `process` 只接 FatalError → `Receipt(status="failed")`(`pipeline.py:51-54`)。

**3. Price — `price(reservation)`(`pricing.py:48`)**:一律用 reservation 快照,不看原始 order。
- subtotal = Σ(數量 × 快照單價)。
- `[observed]` 折扣**最多一個**,取符合門檻中 priority 最高者(spring-30:30%/門檻 $5000/prio20;loyalty-10:10%/門檻 $0/prio10),**不疊加**(`pricing.py:72-78`)。
- tax = round(折後貨款 × 0.05),**只課貨款、不課運費**。
- 運費:折扣**前** subtotal ≥ $8000 免運,否則 $120 平運;**折扣不影響免運資格**。
- `process` 未對 price 包 try/except——它被視為不會丟 domain error。

**4. Dispatch — `dispatch`(`dispatch.py:52`)**
- `choose_carrier`:offshore → `air`;否則看總重,≤ 2000g → `post`,否則 → `freight`(`dispatch.py:36-41`)。
- 重試迴圈最多 `MAX_DISPATCH_ATTEMPTS=3`:**只重試 RetryableError**,FatalError 立即上拋;退避 200ms → 400ms(每次 ×2)加每單固定 jitter(`dispatch.py:44-49`)。
- 全數失敗 → `DispatchExhausted`。`process` 接住後**做補償**:釋放 reservation 把庫存還回、推進 `dead_letters`、回 `Receipt(status="dead_lettered")`(`pipeline.py:59-67`)。
- 成功 → `Receipt(status="dispatched", carrier, total_cents)`。

**三種終局(Receipt.status)**:

| status | 觸發點 | 補償動作 |
|---|---|---|
| `dispatched` | send 成功 | — |
| `failed` | ingest 或 reserve 丟 FatalError | 不需要(reserve 在提交前已驗證) |
| `dead_lettered` | dispatch 重試耗盡 | 釋放 reservation、入 dead-letter queue |

---

## Scenario — 具體走一遍

**Happy path(對應 `test_pipeline.py:22-30`)**:下單 `WIDGET × 3`。
reserve:catalog stock 10 → 7,凍結單價 $3000。price:subtotal $9000 → 命中 spring-30 → 折後 $6300;tax $315;**pre-discount $9000 ≥ $8000 → 免運**(即使折後 $6300 < $8000 仍免運);total **$6615**。carrier:domestic + 重 1500g ≤ 2000 → `post`。→ `Receipt(dispatched, post, 661500)`。

**Dead-letter path(對應 `test_pipeline.py:51-63`)**:`ANVIL × 2`,carrier 一直 timeout。
reserve:stock 2 → 0。dispatch 試 3 次(退避 ~200ms、~400ms)全 timeout → `DispatchExhausted` → release 把 stock **還原成 2** → `Receipt(dead_lettered)`,`dead_letters` 多一筆。

---

## Boundary or failure

- `[inferred]` **不是所有失敗都會變成乾淨的 Receipt。** 只有 ingest/reserve 的 FatalError 與 dispatch 的 `DispatchExhausted` 會轉成 receipt。其餘會**以例外逃出 `process`**:reserve 的 `VersionConflict` 連續 3 次失敗(store 高度競爭)會上拋;若注入的 `send` 丟 `FatalError`,dispatch 直接上拋、而 `process` 只接 `DispatchExhausted`(兩者是 `OrderError` 的**同層兄弟**,見 `errors.py` / `dispatch.py:22`),於是例外逃出 `process`,**且此時 reservation 已扣庫存卻不會被釋放**(庫存滯留)。這條界線防止你以為「任何失敗都會落成 receipt」。
- `[inferred]` **`reprice_required` 目前「設了但沒人讀」。** reserve 在過期重建時設此旗標(`inventory.py:69`),但 `process` 一律 `price(reservation)`(`pipeline.py:57`),而 `price()` 不看旗標。端到端行為上它目前**不改變任何結果**(重建後快照本就帶新價,總價自然反映)。是潛在接縫,不是 bug。
- `[observed]` **免運看折扣「前」的 subtotal**,是刻意設計並有測試釘住(`test_pipeline.py:32-39`)。

---

## Evidence and gaps

**Evidence(exact paths)**
- 編排與終局:`pipeline.py:44-74`;Receipt 型別:`pipeline.py:29-35`
- 驗證規則:`ingest.py:25-49`;region 白名單:`ingest.py:9`
- 冪等 / TTL 重建 / 兩段式提交 / 釋放:`inventory.py:54-75`、`93-125`、`77-91`
- 定價規則:`pricing.py:48-78`;旋鈕:`config.py:4-22`
- carrier 選擇 / 退避 / 重試上限:`dispatch.py:36-49`、`52-71`
- 錯誤分類:`errors.py:8-41`;樂觀鎖:`store.py:29-47`

**Gaps / 未覆蓋**
- `send` 是**注入的 callable**(`pipeline.py:40`),真實 carrier 整合不在 repo 內——成功/失敗完全由它決定。
- `VersionedStore` 是**純記憶體**(`store.py`),進程結束即失;無持久化、無跨進程並發的實測。
- reservation 過期用 `time.monotonic()`(`inventory.py:41`),`process()` 沒有注入 `now` 的路徑,**端到端幾乎觸發不到「過期重建」分支**(只有測試直接呼叫 `reserve` 才測到,`test_pipeline.py:71-86`)。
- `reprice_required` 與 `_put_with_retry` 耗盡分支,在 `process` 端到端測試中**未覆蓋**。
- **無 canonical model**:以上關係與界線是我讀碼綜合的 `[inferred]`,尚未經你確認。若要固化,`$build` 能把它變成可累積、可 review 的模型。

---

需要我把任一段(例如 reserve 的冪等/重建,或 dispatch 的退避/補償)展開成 `detail=deep`,或改用 `architect` lens 從邊界與 invariant 角度重講嗎?