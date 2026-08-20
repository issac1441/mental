# Eval results — skill 版本與 iteration 對照

每個 iteration 目錄存放該輪的 `benchmark.{json,md}` 與各 run 的說明原文、learner 作答、合議評分。arm 名稱固定（`with_skill`=當輪被測版本、`old_skill`=對照版本、`without_skill`=裸模型、`null_floor`=無說明地板），但**指到的 skill 版本隨輪次移動**：

| skill 版本 | 內容 | 被測位置 |
| --- | --- | --- |
| v0 | 原版：Context 區塊開頭、View 名稱分節 | iteration-1 `old_skill` |
| v1 | 答案優先重構（Explanation shape） | iteration-1 `with_skill`；iteration-2/3/4 `old_skill` |
| v2 | + lens altitude、name-the-levers、trap 預防、校準語氣 | iteration-2 `with_skill` |
| v3 | + 負向保證需追全路徑、禁程序開場（第一版）、非技術 lens 白話 Context | iteration-3 `with_skill` |
| v3.1 | 開場規則強化：第一句就是主題事實、無任何 warm-up | iteration-4 `with_skill`（現行版） |

- Iteration-1 用 v1 battery（5 probes/案、單 grader）；iteration-2 起為 v2 battery（分層 probes、trap、信心/Brier、25% 截斷、persona、邊界覆蓋、斷言抽驗、extraneous、grader ensemble×2、null floor）。跨 battery 的 pass rate 不可直接比較；v2 內各輪可比。
- Iteration-3/4 只重跑 `with_skill`；`old_skill`/`without_skill`/`null_floor` 沿用 iteration-2 的產物與評分（相同輸入重評只增加評審噪音）。
- **Iteration-5/6 為 repeats 輪**：`with_skill`（v3.1）與 `without_skill` 兩 arm 全案重新取樣（explain→learn→grade 全管線）。定版統計取 v3.1 = {it-4, it-5, it-6}、裸模型 = {it-2, it-5, it-6} 各 3 個獨立樣本。
- **定版結果見 [final-v3.1/benchmark-final.md](final-v3.1/benchmark-final.md)**（`finalize.py` 產出）：逐案配對 delta —— probe +0.045（95% CI [0.01, 0.083]）、prefix25 +0.087（95% CI [0.003, 0.17]），七項 release criteria 全過，**v0.3.0 定版**。
- 已知非鑑別題：orderflow-failure probe 8（carrier 選擇）——三個說明 arm 都自然省略該內容，懲罰的是問題範圍外的涵蓋度；改版收錄於下一輪 battery 調整。

## change / review / doctor 迴圈（iteration-7 → 8）

- **Iteration-7**（首輪）：暴露 (a) review skill arm 的 git 呼叫被窄白名單擋下，只能盲審——dirty diff 4 個偷渡決策僅抓到 2 個（DSR 50%），裸模型 4/4；(b) change 內容滿分（probes 12/12）但輸在表達層（流程開場、$build 廣告、未白話的 [inferred]/Lens 頁尾）；(c) doctor 兩組皆 6/6（種毒太易，天花板），skill 組 0 誤報 vs 裸組 1。
- **Iteration-8**（修正驗證）：git 白名單放寬＋「發現只寫一次」＋ answer-first 移植後——review dirty 案 with_skill 13/13、**DSR 0%**、subtle 案 12/12 且 gist 反超裸模型（4 vs 2.5）；change probes 維持 12/12，gist 部分改善（2.5/3.5）仍低於裸模型（4/4.5），為下一輪殘留項。
- 種子沿用規則：floors、bare change、doctor 由 iteration-7 拷貝（輸入未變）。
- Floor 訊號：review 案 floor 2/6、0/5（高鑑別）；change 案 floor 4/6、5/6（部分可推理猜中，probe 需再 code-bound 化）。

## change 表達層收尾（iteration-9 → 10）

change skill 版本沿革：v1（檔尾一段 presentation 附註，it-8 被測）→ v2（Response contract 章節＋workflow 步驟內就地改寫 `$build`/選型報告的位置，it-9）→ v3（補禁「模式宣告」開場＋methodology 新增 side-effect 主張須 path-specific 規則，it-10）。

- **Iteration-9**（v2 驗證）：intent 案表達痊癒（gist 3.5→**5**、overhead 4→**5**）證明「規則進 workflow 動線」是對的機制；decision 案殘留三句英文 meta 開場（"This is a decision-mode comparison…"，模式宣告不在 v2 禁列）gist 3；另 calibration 抽驗抓到一條真實杜撰——宣稱 force 路徑 rebuild 會設 `reprice_required=True`，實際只有 TTL 過期分支會設（相鄰路徑混淆）。
- **Iteration-10**（v3 定案）：兩案 **13/13 全過**，gist **5/5**、overhead **5/5**、coherence 4/4、concreteness 5/5、杜撰 0、grader 一致率 1.0——全面追平或反超裸模型（4/4.5）。change 迴圈關閉。
- 種子沿用：兩輪的 bare 與 floor 均拷自 iteration-8/9（輸入未變，重評只加噪音）。
