`/mental:sync` 完成。以下是漂移分析與模型修正草案（此環境無寫檔權限，草案直接寫在回覆中，未建立或修改任何檔案；`mental/` canonical 主張全部保持原狀）。

---

## 結論（先講重點）

比對 18 條主張後，**13 條 unchanged、5 條已漂移、另有 1 個意外與 1 批未建模行為**。漂移集中在兩個地方：`config.py` 的常數改了（`MAX_DISPATCH_ATTEMPTS` 3→4、`RESERVATION_TTL_SECONDS` 更名為 `RESERVATION_HOLD_SECONDS`），以及 **pricing 的兩條主張現在被程式碼直接推翻**——稅基與免運判定都改成「折扣後」計算，其中一條還是經 commerce team 簽核的 `[agreed]` 不變量。更麻煩的是，能仲裁這兩個衝突的政策文件 `doc-pricing-policy`（`./docs/pricing-policy.md`）已不存在，所以**目前無法從證據判定「程式是 bug」還是「政策改了」——這需要你決定，我不會替你選邊**。

結構驗證（`validate_workspace.py`）通過、零錯誤；漂移全是語意層，驗證器抓不到。

---

## 漂移分類總表

| # | Artifact / 主張 | 分類 | 證據 |
|---|---|---|---|
| 1 | map: ingest→reserve→price→dispatch 產生 Receipt | `unchanged` | `pipeline.py:44-74` |
| 2 | map: 以 reservation 快照定價、不用 raw order | `unchanged` | `pricing.py:50` |
| 3 | map: 耗盡重試→釋放預留+dead-letter | `unchanged` | `pipeline.py:61-67` |
| 4 | map: 狀態存於 VersionedStore、樂觀併發 | `unchanged` | `store.py`, `inventory.py:127-137` |
| 5 | dispatch: **最多 3 次嘗試，`MAX_DISPATCH_ATTEMPTS = 3`** | **`changed`** | `config.py:7` 現為 **`= 4`** |
| 6 | dispatch: backoff = `BASE*2^(n-2)` + CRC32 jitter | `unchanged`（公式）| `dispatch.py:44-49`（但因 #5 多一次重試，見下）|
| 7 | dispatch `[agreed]`: 耗盡→釋放預留、絕不擱置庫存 | `unchanged` | `dispatch.py:71`+`pipeline.py:61-67` |
| 8 | pricing: 至多一個折扣、取最高優先、不疊加 | `unchanged` | `pricing.py:73-79` |
| 9 | pricing: **稅課在折扣後小計（先折後稅）**；運費不課稅 | **`contradicted`**（前半）/ `unchanged`（運費不課稅）| `pricing.py:56` 對 `subtotal`（**折扣前**）課稅 |
| 10 | pricing `[agreed]`: **免運以折扣前小計判定、折扣絕不會害訂單失去免運** | **`contradicted`** | `pricing.py:58` 用 `discounted`（**折扣後**）判定 |
| 11 | pricing `[agreed]`: 規則實作 `doc-pricing-policy`、該文件為仲裁 | **`unverifiable`** | `./docs/pricing-policy.md` 不存在 |
| 12 | reservation: 生命週期由 **`RESERVATION_TTL_SECONDS = 120`** 控制 | **`changed`** | 已更名為 `RESERVATION_HOLD_SECONDS = 120`（值不變）`config.py:4` |
| 13 | reservation: `reserve()` 對 order_id 冪等、回傳既有預留 | `unchanged` | `inventory.py:63-67` |
| 14 | reservation: 過期→依現行 catalog 重建、標記 `reprice_required` | `unchanged`（機制）| `inventory.py:68-70`（但因果語句有意外，見下）|
| 15 | reservation: `release()` 還庫存+刪預留、未知 id 為 no-op | `unchanged` | `inventory.py:77-91` |
| 16 | scenario: 全數失敗→最終嘗試後 raise DispatchExhausted | `unchanged` | `dispatch.py:61-71`（「最終嘗試」序號因 #5 位移）|
| 17 | scenario: pipeline 釋放預留+dead-letter | `unchanged` | `pipeline.py:61-65` |
| 18 | scenario: Receipt 為 `dead_lettered`、呼叫端不見例外 | `unchanged` | `pipeline.py:66-67` |

`removed`：無。任何主張的主體都仍存在（`RESERVATION_TTL_SECONDS` 只是被更名，概念仍在，故歸 `changed` 而非 `removed`）。

---

## 重點衝突與意外

**衝突 A — 稅基（#9，`contradicted`，中高風險）。** Canonical 說「先折後稅」，但 `pricing.py:56` 是 `tax = round(subtotal * TAX_RATE)`，對**折扣前** `subtotal` 課稅（`config.py:12` 與 docstring 註解都寫「before any discount」）。**槓桿 `TAX_RATE=0.05`。方向：只要有折扣，實收稅額高於模型預測。** 具體：小計 $6000 命中 spring-30（−30%）→ 折後 $4200；模型預測稅 = 5%×4200 = $210，程式算稅 = 5%×6000 = $300，**客戶多付 $90 稅**。

**衝突 B — 免運判定（#10，`contradicted`，最高風險）。** 這是經 commerce team 於 2026-08-05 簽核的 `[agreed]` 不變量：「折扣絕不會害訂單失去免運」。但 `pricing.py:58` 用**折扣後**的 `discounted` 跟門檻比，docstring 甚至明寫「A large discount can therefore cost the order its free shipping」——**與 agreed 主張正好相反**。**槓桿 `FREE_SHIPPING_THRESHOLD_CENTS=800000`、`FLAT_SHIPPING_CENTS=12000`。** 具體：小計 $8500（過門檻）命中 spring-30 → 折後 $5950（未達 $8000）→ 程式收運費 $120，模型預測 $0。

> 兩個衝突都讓訂單變貴、都可能是「刻意改政策」或「回歸性 bug」，而**唯一能仲裁的 `doc-pricing-policy` 已遺失**（衝突 C）。依 methodology「實作真相與概念真相衝突時，兩者都保留並標為 conflict」，我不替你判定哪個是對的。

**衝突 C — 來源遺失（#11，`unverifiable`）。** `doc-pricing-policy` 指向 `./docs/pricing-policy.md`，該檔與整個 `docs/` 目錄都不存在。依 source policy，**保留為 gap、不擅自尋找替代來源**。後果：衝突 A/B 無法用政策文件裁決。

**意外（#14，非漂移、無法定年）。** `reprice_required` 只在 `inventory.py:69` 被**設定**，全 repo 無任何地方**讀取**它（grep 確認）。pipeline 是**無條件** `price(reservation)`（`pipeline.py:57`，註解「Always price from the … snapshot」），重算靠的是重建預留已換入現價，不是靠這個旗標。故主張後半「so the pipeline knows totals must be recomputed」的因果描述不精確——旗標是 dead flag。這可能是既有狀況、非本次漂移，我無法定年（見下）。

**knock-on（#5 的連鎖）。** attempts 3→4 使 backoff 公式（#6）多套一次：新增第 4 次嘗試，延遲 `200*2^2=800ms`+jitter，dead-letter 前最壞多約 0.8s 延遲；scenario #16 的「最終嘗試」由第 3 次變第 4 次。公式本身未變。

**定年限制（誠實聲明）：** 此 fixture 的 `src/` 與 `mental/` 是**單一 commit**（`2c598c8`）匯入的靜態快照，git 無 `src/` 逐步變更史。因此我只能做「canonical vs 現行程式碼」比對，**無法斷定每項漂移發生的時間點**，也無法區分「碼選擇（#20 carrier）是 2026-08-05 後新增」或「一直都有、只是漏建模」。

---

## 來源異動（source delta）

| Source ID | 登記狀態 | 現況 | 處置 |
|---|---|---|---|
| `src-code` | `./src`, rev 2026-08-05, access ok | 現行程式碼，可重讀 | 已重讀；revision 應更新為本次比對日 |
| `doc-pricing-policy` | `./docs/pricing-policy.md`, rev 2026-07-20, access ok | **檔案不存在** | 標記為 gap（`access: missing`），**不替換**；請確認是移動、刪除還是改名 |

**未建模行為（`added evidence`，`[inferred]`，無法定年）：** `dispatch.choose_carrier`（`dispatch.py:36-41`：offshore→air、國內依 `POST_MAX_WEIGHT_G=2000g` 分 post/freight）完全未出現在模型；`TAX_RATE`、兩個 shipping 常數也未在 pricing 概念中「點名槓桿」。若你要，我可補一條 concept 或在 map 補一句，但需先確認這是新增能力還是既有缺漏。

---

## 結構驗證（與語意漂移分開報告）

```
python3 scripts/validate_workspace.py evals/fixtures/sync-workspace --json
→ { "ok": true, "files": 7, "errors": [], "warnings": [] }
```

結構層乾淨：frontmatter 欄位齊全、id 合法、內部連結可解析、status 合法。**注意驗證器不檢查來源檔是否真的存在、也不檢查被引用的程式碼符號是否還在**——所以 `doc-pricing-policy` 遺失與 `RESERVATION_TTL_SECONDS` 更名都不會被它抓到。全部漂移都在語意層。

---

## 模型修正草案

以下是**建議寫入** `mental/changes/sync-2026-08-20-orderflow.md` 的內容（尚未寫檔）。canonical artifacts 一律不動；`[agreed]` 不靜默改寫；每項待你逐一決定。

````markdown
---
id: sync-2026-08-20-orderflow
kind: change
status: draft
sources:
  - src-code
  - doc-pricing-policy
prerequisites: []
updated_at: 2026-08-20
---

# Sync 2026-08-20 — orderflow drift

## Current Model
canonical 建於 2026-08-05，依 src-code(rev 2026-08-05)。本次以現行 ./src 比對，
18 條主張中 13 unchanged、2 changed、2 contradicted、1 unverifiable。

## Source Delta
- doc-pricing-policy: ./docs/pricing-policy.md 已不存在 → 標為 gap，未替換。
- src-code: 內容已於 2026-08-05 後變動，revision 待更新。

## Proposed Model Delta（逐項；除非核准，否則不套用）

### D1  concepts/dispatch-retry.md — [changed]，低風險、可機械更新
- 原: 「at most 3 total attempts … MAX_DISPATCH_ATTEMPTS = 3」
- 改: 「at most 4 total attempts … MAX_DISPATCH_ATTEMPTS = 4」(config.py:7)
- 連鎖: backoff 公式不變，但新增第 4 次嘗試(≈800ms+jitter)；scenario 的
        「final attempt」序號隨之位移。provenance 維持 [observed]。

### D2  concepts/reservation.md — [changed]，低風險、可機械更新
- 原: 「config.RESERVATION_TTL_SECONDS = 120」
- 改: 「config.RESERVATION_HOLD_SECONDS = 120」(config.py:4；值/行為不變，僅更名)
- provenance 維持 [observed]。

### D3  concepts/pricing-totals.md 稅基 — [contradicted]，不自動改寫
- canonical: 先折後稅（tax on discounted subtotal）。
- code: pricing.py:56 對折扣前 subtotal 課稅(TAX_RATE=0.05)。
- 建議標為 [conflict]，兩種真相並存，二選一由人決定：
  - 選項 A（code=回歸 bug）: 保留 canonical，改走 change→plan 修 code。
  - 選項 B（政策已改）: 復原/更新 doc-pricing-policy 後，改寫模型文字，
                       並以新日期重新確認為 [observed]/[agreed]。
- 未定案前不改 canonical 文字、不設 stale（除非你要求記錄漂移）。

### D4  concepts/pricing-totals.md 免運 — [contradicted]，最高風險，不自動改寫
- canonical [agreed]（commerce team 2026-08-05）: 免運以折扣前小計判定、
  折扣絕不會害訂單失去免運。
- code: pricing.py:58 以折扣後 discounted 判定；折扣可害訂單失去免運。
- 建議標為 [conflict]，保留 [agreed] 原文（絕不靜默降級為 [inferred]）。
  仲裁文件 doc-pricing-policy 已遺失 → 需人來源決定：
  - 選項 A: 這是回歸 → 保留 agreed、修 code。
  - 選項 B: 政策已改 → 需 commerce team 重新簽核 + 復原政策文件，
            方可改寫並重新標 [agreed]（新日期）。

### D5  sources.md — doc-pricing-policy
- 將 access: ok → access: missing（保留條目為 gap，不刪、不換來源）。

## Conflicts and Surprises
- 衝突 A(稅基)、B(免運) 皆使訂單變貴、皆無法用現有證據裁決(政策文件遺失)。
- 意外: reprice_required 被設定但全 repo 無讀取(dead flag)；pipeline 無條件重算。
        主張機制成立、因果語句「pipeline knows」不精確 → 建議修辭修正，待確認是否本次漂移。

## Affected Contracts / Prerequisites
- pricing 免運不變量(agreed)遭 code 違反 → 影響對外計費行為與客戶承諾。
- 無 prerequisite 鏈斷裂；map 對 pricing 的引用仍有效。

## Verification Evidence
- config.py:4,7；pricing.py:56,58；dispatch.py:44-49,61-71；inventory.py:41,68-70；
  grep: reprice_required 僅 set 未 read；docs/ 不存在；validate_workspace → ok/0 errors。

## Human Decision: pending
````

---

## 需要你決定（每個 delta 一項）

1. **D1 / D2（安全機械更新）**：是否核准把 `MAX_DISPATCH_ATTEMPTS 3→4`、常數更名同步進 canonical？（`[observed]` 值/名漂移，我建議核准。）
2. **D3 稅基衝突**：程式是 bug（走 change→修 code）還是政策已改（更新模型）？
3. **D4 免運 `[agreed]` 衝突**：同上二擇一；若選「政策已改」，需 commerce team 重新簽核才可改寫 agreed 主張。
4. **D5 來源**：`doc-pricing-policy` 是被刪、移動還是改名？要我標為 `missing` gap，還是你會提供新位置？
5. **是否記錄漂移**：要不要我把受影響 artifact（pricing-totals、dispatch-retry、reservation）標 `status: stale`？依 skill 規則，這只在你明確要求「先記錄漂移再決定替代」時才做——預設不動。
6. **未建模行為**：要不要為 `choose_carrier` 補一條 concept／在 map 點名 pricing 槓桿？

告訴我每項的決定，核准後我只更新你接受的 artifact、在 change record 保留衝突歷史，並僅在「證據＋人為同意」都齊備時才把狀態還原為 `canonical`。