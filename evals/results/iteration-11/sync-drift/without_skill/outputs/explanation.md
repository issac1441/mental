分析完成。以下把 18 條 canonical 主張逐一比對現行程式碼，先給結論再展開。

---

## 結論（先講重點）

`mental/` 模型建於 **2026-08-05**，現在 src 已漂移。18 條主張中：

- **12 條 unchanged**（仍成立）
- **3 條 changed**（事實細節變了，機制還在）
- **2 條 contradicted**（程式碼現在做的與主張相反）← **最危險**
- **1 條 unverifiable**（佐證來源消失）

**最需要注意的**：兩條定價「保證」被程式碼反轉（稅的計算基準、免運判定時機），而且唯一能當仲裁依據的政策文件 `./docs/pricing-policy.md` **已從 workspace 消失**——所以現在無法只憑 repo 判斷這兩項是「刻意的政策調整」還是「regression」。這兩條不該盲目照 code 改成 canonical，必須先找回文件並跟 commerce team 對齊。

---

## 漂移總表

| # | 主張（出處） | 類別 | 一句話 |
|---|---|---|---|
| M1 | map: ingest→reserve→price→dispatch→Receipt | unchanged | pipeline.py 流程一致 |
| M2 | map/pricing: 由 reservation 快照計價，不用 raw order | unchanged（+新增佐證） | 仍成立；docstring 新增「重建的 reservation 會重抓現價」nuance |
| M3 | map: 耗盡重試→釋放 reservation+dead-letter | unchanged | pipeline.py 一致 |
| M4 | map: 狀態存於 VersionedStore（樂觀並行） | unchanged | store.py 一致 |
| D1 | dispatch: 最多 **3** 次，`MAX_DISPATCH_ATTEMPTS = 3` | **changed** | 現在是 **4**（config.py:7） |
| D2 | dispatch: 退避 `BASE*2^(n-2)` + CRC32 jitter | unchanged | dispatch.py:44-49 公式完全一致 |
| D3 | dispatch: 耗盡不會擱置庫存 | unchanged（+新增佐證） | 仍成立；docstring 明文「never silently drops an order」 |
| P1 | pricing: 折扣最多一條、不疊加 | unchanged | `_select_discount` 一致 |
| P2 | pricing: **先折扣再課稅**（對折後小計課稅） | **contradicted** | 程式碼對**折前**小計課稅 |
| P3 | pricing: 免運看**折扣前**小計、折扣不會害失去免運 | **contradicted** | 現在看**折扣後**小計，折扣**會**害失去免運 |
| P4 | pricing: 以 `doc-pricing-policy` 為仲裁依據 | **unverifiable** | 該文件已不存在 |
| R1 | reservation: TTL `RESERVATION_TTL_SECONDS = 120` | **changed** | 常數更名為 `RESERVATION_HOLD_SECONDS`（值仍 120） |
| R2 | reservation: reserve() 對 order_id 冪等 | unchanged | inventory.py:64-67 一致 |
| R3 | reservation: 過期重建並設 `reprice_required`，讓 pipeline 知道要重算 | **changed** | flag 有設但**無人讀取**；pipeline 改成**無條件**重算 |
| R4 | reservation: release() 還庫存+刪除、未知 id 為 no-op | unchanged | inventory.py:77-91 一致 |
| S1 | scenario: 全部失敗後 raise DispatchExhausted | unchanged | dispatch.py:70-71 一致 |
| S2 | scenario: pipeline 接住、釋放、進 dead-letter | unchanged | pipeline.py:61-65 一致 |
| S3 | scenario: Receipt 狀態 `dead_lettered`、呼叫端無例外 | unchanged | pipeline.py:66-67 一致 |

---

## 漂移細節與證據

### 🔴 Contradicted（程式碼與主張相反 — 高風險）

**P2 — 課稅基準反轉**（`pricing-totals.md:15`）
- 主張：「Tax is charged on the discounted goods subtotal — discount first, then tax.」
- 現況：`tax = round(subtotal * config.TAX_RATE)`（`pricing.py:56`），`subtotal` 是**折扣前**小計（:50），`discounted` 沒被用來算稅。`config.py:12` 註解也寫「before any discount」，docstring 規則 3 亦然。
- 影響：稅基變大 → 稅金變多。（「Shipping is never taxed」這半句仍成立，保留。）

**P3 — 免運判定時機反轉**（`pricing-totals.md:16`，且原為 `[agreed]`，2026-08-05 與 commerce team 確認過）
- 主張：「eligibility is decided on the goods subtotal **BEFORE** any discount; applying a discount can never cost an order its free shipping.」
- 現況：`if discounted >= config.FREE_SHIPPING_THRESHOLD_CENTS`（`pricing.py:58`）用的是**折扣後**小計；`config.py:15-16` 註解寫「after any discount」；`pricing.py` docstring 規則 4 甚至直接寫「**A large discount can therefore cost the order its free shipping**」——正好是主張的反面。
- 影響：折扣後跨不過門檻就要付運費，免運更難拿到。

> 觀察：P2 讓稅基變大、P3 讓免運變難，**兩者都朝「對營收有利／對客戶不利」的方向**。src 內部的 docstring 也同步改寫成新行為（表示在程式碼層是**刻意且自洽**的），但能證明商業意圖的 `doc-pricing-policy` 文件不見了 → 無法確認這是核准的政策改動還是 bug。見 P4。

### 🟠 Changed（機制仍在，事實細節變了）

**D1 — 重試上限 3 → 4**（`dispatch-retry.md:13`）
- `config.MAX_DISPATCH_ATTEMPTS = 4`（`config.py:7`）。主張寫死的「3」與「at most 3 total attempts」已錯。退避公式（D2）不受影響、仍正確。

**R1 — 常數更名**（`reservation.md:13`）
- `RESERVATION_TTL_SECONDS` 已不存在，改名 `RESERVATION_HOLD_SECONDS`（`config.py:4`、`inventory.py:41`），**值仍為 120**。行為未變，但模型引用的識別字 grep 不到了。

**R3 — reprice 機制漂移，`reprice_required` 成 dead flag**（`reservation.md:15`）
- 主張：「flagged `reprice_required`, **so the pipeline knows** totals must be recomputed。」
- 現況：`reprice_required` 只在 `inventory.py:37`（定義）、`:69`（設值）出現，**全 repo 沒有任何地方讀它**。pipeline 改成**無條件**重算：`quote = price(reservation)`（`pipeline.py:57`，註解「Always price from the (possibly rebuilt) reservation snapshot」）。
- 結果（過期重建後 totals 一定重算）仍正確，但**機制不同**：不是靠 flag 驅動，而是每次都重算；flag 已是無用的 vestigial 欄位。

### 🟡 Unverifiable（佐證來源消失）

**P4 + doc-pricing-policy 來源**（`pricing-totals.md:17`、`sources.md:20-26`）
- `sources.md` 仍宣稱 `doc-pricing-policy` 位於 `./docs/pricing-policy.md`、`access: ok`，但 workspace **沒有 `docs/` 目錄、找不到該檔**。
- 後果：P4「以該文件為仲裁依據」無法執行；更關鍵的是——正因為它消失，**P2/P3 兩項衝突無法在 repo 內裁決**（不知道程式碼是照新政策改、還是違反政策）。

### 🟢 Unchanged（12 條，仍成立）

M1, M2, M3, M4, D2, D3, P1, R2, R4, S1, S2, S3 全部與程式碼一致。其中 **M2、D3** 現在還多了 module docstring 的明文佐證（例如 dispatch.py 的「never silently drops an order」、pipeline.py 對「reserve 擁有價格快照、重建會重抓現價」的說明）——屬 *added evidence*，建議把「重建的 reservation 會合法地改變報價」這個 nuance 補進 M2/R3。

---

## 模型修正草案

以下為建議取代文字（沿用模型的 `[observed]`/`[agreed]` 標記與 provenance 風格；所有異動檔的 frontmatter `updated_at` 建議改 `2026-08-20`）。

**`concepts/dispatch-retry.md`（第 13 行）**
```
[observed] Dispatch makes at most 4 total attempts per order; the cap is
`config.MAX_DISPATCH_ATTEMPTS = 4` (src/orderflow/config.py).
// drift 2026-08-20: was 3, raised to 4.
```

**`concepts/reservation.md`（第 13、15 行）**
```
[observed] A reservation freezes stock and unit prices; its lifetime is 120 s,
governed by `config.RESERVATION_HOLD_SECONDS` (renamed from
RESERVATION_TTL_SECONDS; value unchanged) (config.py, inventory.py).
...
[observed] An expired reservation is rebuilt from the current catalog. The
pipeline reprices UNCONDITIONALLY from the (possibly rebuilt) reservation
snapshot (pipeline.py:57 `price(reservation)`), so totals are always
recomputed. The rebuilt reservation still sets `reprice_required`, but no code
reads it — it is now a vestigial flag (inventory.py:69).
```

**`concepts/pricing-totals.md`（第 15–17 行）**
```
[observed] Tax is charged on the goods subtotal BEFORE any discount
(`tax = round(subtotal * TAX_RATE)`, pricing.py:56; config.py:12). Discounting
does not lower the tax. Shipping is still never taxed.
// DRIFT 2026-08-20: model previously said discount-first-then-tax.

[needs-reconfirm] Free-shipping eligibility is now decided on the goods
subtotal AFTER discount (`discounted >= FREE_SHIPPING_THRESHOLD_CENTS`,
pricing.py:58; config.py:15-16). A large discount CAN now cost an order its
free shipping — the OPPOSITE of the 2026-08-05 [agreed] guarantee. Do not
adopt as canonical until confirmed with commerce team; the confirming source
(doc-pricing-policy) is currently missing.

[unverifiable] `doc-pricing-policy` cannot serve as the tie-breaker: the file
./docs/pricing-policy.md is absent from the workspace as of 2026-08-20.
```

**`sources.md`（更新兩個來源的狀態）**
```
## src-code
- revision: 2026-08-05  // model baseline; src has since drifted — re-baseline needed
- access: ok

## doc-pricing-policy
- location: ./docs/pricing-policy.md
- revision: 2026-07-20
- access: MISSING  // file not found in workspace as of 2026-08-20
```

`model/map.md`、`concepts/dispatch-retry.md` 的 D2/D3、`index.md`、scenario 三條、reservation R2/R4、pricing P1 **無需修改**。

---

## 建議動作（按風險排序）

1. **可直接更新（純事實、零風險）**：D1（3→4）、R1（常數更名）。照上面草案改即可。
2. **先查證再定案（P2、P3）**：這是最關鍵的一步。**先找回／還原 `./docs/pricing-policy.md`，與 commerce team 對齊**，再決定——若是核准的政策調整，就把模型改成新行為並移除舊 `[agreed]` 保證；若違反政策，則應把程式碼視為 regression 回報，而**不是**改模型。在文件缺席前，這兩條維持 `needs-reconfirm`，不要標回 canonical。
3. **回報工程團隊**：`reprice_required` 已成 dead code（有設無讀），可清掉或補上讀取端；順帶確認 `sources.md` 為何仍標 `access: ok` 卻找不到 docs 文件。

（依指示，以上分析與修正草案僅寫在回覆中，未建立或修改任何檔案。）