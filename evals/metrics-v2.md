# Evaluation metrics v2 — 從認知科學到可跑的指標

本文件把 [design-background](../docs/design-background.md) 的五個假設（H1–H5）、§6 evaluation plan、以及其引用的認知科學文獻，操作化成 harness 可執行的指標。目標：iteration-1 的指標偏「記住了沒」；v2 要測的是 **repo 真正的主張——模型能不能拿來預測、修正、做決策**。

## 0. 現況的不足（iteration-1 診斷）

| 不足 | 後果 |
| --- | --- |
| Probe 偏 retention/近遷移 | 三組都接近天花板（87–93%），鑑別力集中在 rubric |
| rubric 全靠單一 judge 主觀 1–5 分 | 噪音大、可被寫作風格騙 |
| 沒有 floor 控制組 | 無法排除 learner 先備知識/常識推理的貢獻 |
| n=1/arm/case | 單次抽樣，統計上只算方向訊號 |
| 完全沒測 Lens（角色職責）、校準（三種真值）、邊界（認知邊界）、決策（問題核心） | repo 的差異化主張全部沒被檢驗 |

## 1. 設計原則

1. **每個指標綁定一個可證偽的主張**（H1–H5 或 §6 條目），不做泛用「品質分」。
2. **行為證據優於評審印象**：能用 learner 的作答行為量測的，不用 judge 打分（呼應 H4：transfer 與反例 > 辨識與熟悉感）。
3. **有 floor / ceiling 控制組**：null-explanation arm 估先備知識地板；full-code-access arm 估天花板；報告 **lift over floor** 而非裸準確率。
4. **誠實標註「LLM 模擬測不到的」**：LLM learner 不是人類初學者。orientation 的真實時間、7 天延遲保留、真實認知負荷（如 NASA-TLX）只能靠人類研究；模擬結果是必要非充分訊號（呼應 §7 limitations）。

## 2. 指標族

### Family A — 遷移深度（H3、H4；Barnett & Ceci 2002 遷移距離分類）

把 probe 分層，報告**每層準確率的深度剖面**，而不是單一總分。遠遷移權重高於復述。

| Tier | 定義 | orderflow 範例 | 現況 |
| --- | --- | --- | --- |
| A1 retention | 說明中直接陳述的事實 | 「最多重試幾次？」 | 已有 |
| A2 near transfer | 把說明中的規則套到新數字 | 「小計 9,000、折 30%、門檻 8,000，要運費嗎？」 | 已有 1 題 |
| A3 **counterfactual intervention** | 預測一個說明**沒討論過**的改動的後果，需組合 ≥2 條關係 | 「把 `MAX_DISPATCH_ATTEMPTS` 改成 1，dead_letters 和收據會怎樣？」「若 `VersionConflict` 改繼承 `FatalError`，哪些行為改變？」 | 缺 |
| A4 **abductive diagnosis** | 從症狀反推原因鏈（operator 的真實工作） | 「同一筆訂單重跑後 total 變了，最可能的原因鏈？」 | 缺 |
| A5 **model repair**（§6 Model correction） | 給 learner 一句**刻意錯誤**的系統描述，必須拒絕並修正 | 「『免運門檻看折扣後金額』——對嗎？錯在哪？」 | 缺 |

> A5 同時測抗錨定：說明品質差時，learner 會順著權威敘述接受錯誤前提。

### Family B — 認知邊界（H4；misconception / negative knowledge）

| 指標 | 操作化 |
| --- | --- |
| B1 **trap resistance** | case 檔標注 `trap: true` 的 probe（表面直覺答案是錯的）。報告 trap 與非 trap 準確率的差距 |
| B2 **boundary coverage** | case 檔宣告 fixture 埋的邊界清單（如：`VersionConflict` 重試耗盡會以未攔截例外逃出 `process()`、免運看折扣前小計、jitter 由 order_id 決定）。grader 勾稽說明**主動揭露了幾個**。iteration-1 中新版 skill 自己挖出 escape path 就是這個指標的正例 |
| B3 **overgeneralization probe** | 生成式邊界題：「這個規則在什麼情況下不成立？」learner 必須自己說出至少一個邊界，不是選擇題 |
| B4 **scope honesty** | 1–2 題材料範圍外的問題，正確行為是答「說明中沒有提到」。誘答率 = 說明風格引發的幻覺率 |

### Family C — 校準與三種真值（H5；metacognitive calibration；Brier 1950）

repo 的差異化主張是 `[observed]/[inferred]/[agreed]/[conflict]`。如果這套機制真的做事，應該可以量測到：

| 指標 | 操作化 |
| --- | --- |
| C1 **learner confidence calibration** | learner 每題附 0–100 信心 → Brier score ＋ 分辨力（答對題與答錯題的信心分佈差）。好的說明產生「知道自己不知道」的讀者 |
| C2 **false-certainty rate** | grader 抽驗說明中 N 條斷言 vs 程式碼：以肯定語氣陳述但錯誤/無證據支持的比率（應趨近 0）；反向也罰過度避險（可驗證卻滿篇 hedging） |
| C3 **provenance fidelity**（僅 skill arms） | `[inferred]` 標籤的 precision/recall：標了的地方是否真的缺證據？有證據的地方是否被誤標？檢驗三種真值是**認識論工具還是裝飾** |
| C4 **gap disclosure coverage** | 說明自報的 gaps vs grader 實際找到的 gaps 的覆蓋率 |

### Family D — 關係結構回收（H1「relationships beat inventory」；Johnson-Laird 1980）

| 指標 | 操作化 |
| --- | --- |
| D1 **relationship-map F1** | case 檔內建 ground-truth 邊清單（8–12 條因果/依賴邊，如 `reservation → pricing`、`RetryableError → backoff retry`）。learner 被要求列出「A 直接影響 B」的所有關係 → 算 precision/recall/F1。直接檢驗讀者拿到的是**圖**還是**事實袋** |
| D2 **mechanism chain integrity** | 給打亂的步驟卡，learner 排出因果鏈；用編輯距離計分 |
| D3 **inventory contamination** | learner 自由回憶「這個系統最重要的 10 件事」；grader 標注其中多少是「對預測無用的檔案清單式細節」。反向指標：高＝說明浪費了讀者的注意力（H1 的反面）|

### Family E — 認知負荷與由淺入深（H2；Sweller 1988）

| 指標 | 操作化 |
| --- | --- |
| E1 **prefix validity curve**（取代 gist 主觀分） | 把說明截斷在 25% / 50% / 100%，各跑一次 learner → 準確率-閱讀量曲線的 AUC。行為化的「由淺入深」：隨時停下來，手上的模型都是對的 |
| E2 **deterministic load metrics**（腳本算，零 judge 噪音） | (a) 術語先用後定義的次數；(b) 前向引用數；(c) 進入第一個實質主張前的字元數；(d) 碎裂指數：同一機制被拆到幾個不相鄰段落 |
| E3 **extraneous-content ratio**（取代 overhead 主觀分） | grader 逐段標注 {回答問題 / 支撐預測 / meta / 框架 / 填充}，報告 extraneous 佔比。段落級記帳，比 1–5 分穩定 |

### Family S — Output style 與語言可及性（ELI5-ness；writing-profile 的操作化）

**先承認一個測量盲點**：目前的 learner 是預設模型——它是專家讀者，任何生澀術語都讀得懂，所以「人看不看得懂」在行為層測不到，只剩 judge 印象分。修法是把 learner 鎖進 persona，讓可及性失敗變成可觀察的行為。

| 指標 | 操作化 |
| --- | --- |
| S1 **persona-locked comprehension**（核心） | learner 的系統提示鎖定非技術 persona：「你是非工程背景的 PM。文中未解釋的技術術語對你是不可理解的雜訊；依賴這些術語的句子視為讀不懂，相關題答『看不懂』。」probe 改問功能/執行層問題（「出貨一直失敗，客戶最後會遇到什麼？」「這筆訂單為什麼變貴了？」）。用語生澀的說明會在這裡行為性地現形——這是 ELI5 的行為化，不是品味打分 |
| S2 **jargon density / first-use definition** | 每個 fixture 維護一張技術術語表（`optimistic concurrency`、`idempotent`、`TTL`、`dead-letter`…）。計數：出現在論述主幹、首次出現未被白話解釋的術語數/千字。code identifier 出現在**證據引用位置**（如文末 Sources、括號路徑）不罰；撐起論述卻無解釋才罰 |
| S3 **concrete-example coverage** | 每個抽象主張（規則、不變量、策略）±2 句內是否有具體落地（數字、情境、walkthrough）。coverage % —— writing-profile「Prefer concrete behavior to abstract claims」的直接檢驗 |
| S4 **analogy quality & boundary marking** | 出現比喻時：是否對應真實機制、是否標明失效點（writing-profile:「Mark where an analogy stops working」）。沒有比喻不罰——錯誤比喻比沒有比喻更糟 |
| S5 **sentence load**（純腳本、零成本） | zh：平均句長（字元）與逗號鏈深度；en：>25 words 句比率。跨迭代追蹤趨勢 |

### Family F — 角色職責 Lens fitness（H2 role-conditioning；design doc「Lens 合併 audience 與 perspective」）

目前完全沒測。新增 lens 變因 case（同一問題 × `lens=pm` / `lens=operator` / 預設）：

| 指標 | 操作化 |
| --- | --- |
| F1 **role-decision usefulness** | 每個 lens 配「該角色必須做的決策」probe。pm：「接受 option A 要付什麼代價？」operator：「半夜 DLQ 警報，第一步查哪裡？」 |
| F2 **assumed-knowledge violation** | 依 methodology 中該 lens 的 `assumes` 清單，grader 數「未定義就使用、且該角色不能被假設已懂」的術語數。pm 說明裡裸奔的 `optimistic concurrency` = 1 次違規 |
| F3 **cross-lens consistency + divergence** | 同題不同 lens 的兩份說明：抽取事實主張，**矛盾率必須為 0**（lens 改變強調，不能改變真值）；同時測**內容分佈差異**——重疊率太高代表 lens 是裝飾品，矛盾代表 lens 是危險品 |
| F4 **default-lens appropriateness** | 自動選擇的 lens 是否符合問題隱含的角色（以 grader 判斷 + skill 自報的 Context 行核對）|
| F5 **abstraction-altitude fit**（認知邊界的內容面） | grader 逐段標注高度 {purpose / functional / operational / implementation}，與該 lens 的目標分佈比對。pm 目標：purpose+functional+operational ≥ 80%、implementation ≤ 10% 且只能以可選的證據指標形式出現（文末 Sources、括號引用）；違規 = 未標記為可選就往下潛的段落數。engineer 反向成立：只有 purpose 空談、無 mechanism 也算高度不足。這抓的是「詞彙都解釋了、但內容根本不該出現在這個高度」的失配——S2 數不到的那種 |

### Family G — 問題核心：決策與變更（§6；agent throughput > human model rebuild）

這族把 eval 從 `understand` 延伸到 `change`/`review`（你說 change 好用——這裡讓它可量化）：

| 指標 | 操作化 |
| --- | --- |
| G1 **Decision Surprise Rate**（design doc 自己定義的指標） | 準備一個 diff + change brief 的 case，fixture 裡埋 N 個 consequential decisions（改了失敗語意、隱藏的 contract 變更…）。跑 `review` 說明後問 learner「agent 替你做了哪些決定？」→ 事後才發現的決策數 ÷ 總決策數。越低越好 |
| G2 **predict-then-observe self-correction**（H3 直接檢驗） | 兩階段 learner：先根據說明預測 scenario 結果 → 再給實際 test output → 數自我修正次數與方向。檢驗「說明產生的是可行動的預測，還是被動的閱讀感」 |
| G3 **orientation efficiency** | 已有 time/tokens；補上「每千字說明的 lift-over-floor」＝單位閱讀成本的知識增量 |
| G4 **drift detection**（`sync`/`doctor`，後續） | 在 canonical artifact 裡埋一條與程式碼矛盾的過期主張；skill 是否找到、是否保持 `[conflict]` 可見而不悄悄改寫（H5 + §5 真值治理）|

## 2.5 各 skill 的迴圈協定現況

| skill | 協定 | 狀態 |
| --- | --- | --- |
| `understand` | learning-transfer（A–F 全族） | ✅ 已跑 4 輪，v3.1 定版 |
| `change` | learning-transfer 變體：learner 讀分析後答「決策 probe」（選項實際效果、隱藏耦合、待決策項、埋藏邊界） | ✅ cases: change-decision / change-intent |
| `review` | **Decision Surprise Rate**：git 佈置的真 diff＋埋入未核准決策清單；boundary coverage 即（1−surprise rate）；另計誤報 | ✅ cases: review-hidden-decisions / review-subtle |
| `doctor` | **detection 協定**（無 learner）：種毒 workspace（6 violations）→ 報告 vs inventory 的 recall＋false positives | ✅ case: doctor-detection |
| `sync` | detection 變體：canonical model＋漂移後的 source → 偵測 `changed/contradicted/removed`、且不得悄悄改寫 `[agreed]`（保持 `[conflict]` 可見）。fixture 需一組「model@t0 + source@t1」對 | 📐 設計完成，待建 fixture |
| `build` | 工件品質：build 產出 draft model → learner **只讀產出的 mental/ 工件**答 understand 同款 probes（模型可教性）＋ validate_workspace 通過率＋ promotion gate 是否完整呈現 | 📐 設計完成，需 write-enabled 沙盒跑法 |
| `learn` | 多輪協定：腳本化學習者 persona（帶預設迷思）與 skill 對話 N 輪；量測——診斷題是否 2–5 題且先停、第一輪教學是否只教最小斷裂關係、迷思是否被修正（後測 probe）、mastery 是否只在有證據後移動一格 | 📐 設計完成，需 `claude -p --resume` 多輪 harness |
| `practice` | 多輪協定：學習者按劇本答錯特定關係 → 量測 skill 是否找到「第一個斷裂關係」、給最小修正、出**結構等價新情境**（非改寫原題）、transfer+boundary 後才 `verified` | 📐 同上 |
| `quiz` | 單輪可測一半：出題品質（涵蓋圖 vs 稿定 coverage map、無答案洩漏、格式合規）；閱卷需第二輪（提交假答卷 → 評分準確性、不得產生假 mastery 百分比） | 📐 出題半段可直接沿用現 harness |

多輪 harness 的共同機制：`claude -p --resume <session>` 續同一 session，學習者側用固定劇本（腳本化錯誤與迷思），每輪之間由 runner 檢查停等契約（該停沒停即 fail）。

## 3. 控制組與統計加固

| 機制 | 說明 |
| --- | --- |
| **null-explanation floor** | learner 拿空說明作答 → 每 case 的先備知識地板。所有準確率改報 lift-over-floor。順帶當汙染哨兵：地板異常高 = fixture 可被常識推理攻破，需要換題 |
| **full-access ceiling**（選配） | learner 直接讀 code 作答 → 天花板，量測說明的「傳真率」 |
| repeats ≥3 | 每 (case, arm) 至少 3 次，報 mean±sd 與 paired delta 的 bootstrap CI |
| grader ensemble | 3 個獨立 grader 取中位數；報告一致性；分歧題目人工複核 |
| blinding hygiene | rubric 評分前剝除可辨識 arm 的 Context/footer 行（provenance 指標另行保留原文）|

## 4. 分級路線

- **v2（改 case schema + prompts 即可，不動架構）**：A3–A5、B1–B4、C1–C2、D1、E1–E3、S1–S3、S5、null floor、repeats、ensemble。
- **v3（需要新 case 類型/多輪協定）**：C3–C4、D2–D3、S4、F 全族（F5 可提前併入 v2 的 grader 附加任務）、G1–G2。
- **只能靠人類研究**（誠實邊界，呼應 §7）：真實 orientation time、7 天延遲保留、主觀認知負荷量表、真實團隊的 Decision Surprise Rate。LLM 模擬版本一律標注 `simulated`。

## 5. Case schema 擴充（v2）

```jsonc
{
  "probes": [
    {
      "id": 6,
      "tier": "counterfactual",        // retention|near|counterfactual|diagnosis|repair|boundary|scope
      "trap": true,                     // 表面直覺答案是錯的
      "question": "...",
      "ground_truth": "...",
      "confidence": true                // learner 需附 0-100 信心
    }
  ],
  "boundaries": [                       // B2 coverage 勾稽清單
    "VersionConflict retry exhaustion escapes process() uncaught",
    "free-shipping threshold uses pre-discount subtotal"
  ],
  "edges": [                            // D1 ground-truth 關係邊
    ["reservation", "captures unit-price snapshot", "pricing"],
    ["RetryableError", "triggers backoff retry", "dispatch"]
  ],
  "prefixes": [0.25, 0.5, 1.0],         // E1 截斷點
  "personas": ["nontech-pm"],           // S1 persona-locked learner
  "jargon_list": ["optimistic concurrency", "idempotent", "TTL", "dead-letter"],
  "altitude_target": {                  // F5 各 lens 的內容高度分佈
    "pm": {"implementation_max": 0.10}
  }
}
```

Persona 定義集中在 `evals/prompts/personas/*.md`，probe 可加 `"audience": "pm"` 指定只給某 persona 作答。

## 6. 成本估算（3 cases × 3 arms）

| 配置 | claude 呼叫數/迭代 | 相對 iteration-1 |
| --- | --- | --- |
| iteration-1（現況） | 27 | 1× |
| **v2 standard**：10 probes、repeats×2、prefix 2 點、null floor、ensemble×2、S1 persona×1 | ≈ 90 | ≈ 3.3× |
| v2 full：repeats×3、prefix 3 點、ensemble×3、ceiling、persona×2 | ≈ 170 | ≈ 6× |

建議日常迭代跑 standard，發版前跑 full。所有呼叫依 subagent 政策固定 `claude-opus-4-8 --effort max`。

## 參考

- Johnson-Laird (1980); Sweller (1988); Chi et al. (1989); Karpicke & Blunt (2011) — 已列於 design-background。
- Barnett, S. M., & Ceci, S. J. (2002). When and where do we apply what we learn? A taxonomy for far transfer. *Psychological Bulletin*, 128(4).
- Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. *Monthly Weather Review*, 78(1).
