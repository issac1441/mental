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

## learn / practice 多輪首跑（iteration-12，`run_dialogue_eval.py`）

- 協定驗證通過：`claude -p --resume` 多輪、腳本化迷思學習者、逐字稿契約檢核、獨立後測 learner、floor 全管線串通。
- **learn-pricing**：skill 組 **9/9**；裸組 8/9——唯一失分正是 learn 教義的核心鑑別項：裸導師第一輪直接倒滿整套課（模型＋對照表＋完整範例）再出題，無「診斷 2–5 題先停」。skill 組第一輪＝主題錨定＋明說「先不給答案」＋三題診斷＋停等。後測兩組 4/4（floor 2/4）。
- **practice-dispatch**：裸組 9/9；skill 組 8/9——失分經細讀屬**檢核項設計瑕疵**：檢核 2 把「backoff 最小修正」與「jitter 糾正」綁成一條，但 skill 按「一次修一個關係」教義刻意把 jitter 留待下輪（學習者其後自行修正、導師確認）；grader 註明最小修正部分對 dispatch.py:47 核實完美。下輪修正：拆開連言式檢核、將「延後但最終處理」計為合規。後測 4/4（floor 1/4，高鑑別）。
- 後測 probes 兩案皆兩組 4/4 飽和——只要對話涵蓋主題，後測就可從逐字稿推出；下輪需加「對話未明說、須組合推理」的 transfer 題。
- 觀察到未被檢核懲罰的不合規：practice 導師開場 readiness declaration（「我已經讀完 dispatch.py…完整掌握」）——已在 practice SKILL.md 補 per-turn answer-first 行（**預防性、本輪未經 eval 驗證**）；下輪 battery 將 no-warm-up 納入 dialogue_checks。

## sync 漂移偵測首跑（iteration-11）

- 5 個種子漂移＋2 個 conformance 檢查：**兩組全過 7/7、0 誤報**——recall 觸頂（同 doctor 教訓：對被明確指派的「主張對碼」任務，裸 opus-max 就是強審查者）。
- 鑑別訊號在**廣度**：skill 組 4 個 extra findings（`reprice_required` 死旗標、`choose_carrier` 未建模、pricing 槓桿未點名、attempts 3→4 對 backoff 序列的衍生效應）vs 裸組 1 個；以及收尾紀律（skill 以 D1–D6 逐項決策單收尾、`[agreed]` 改寫要求 commerce 重簽核、stale 標記遵守「明確要求才做」）。
- **Eval 抓到 fixture 裡未種的真實漂移**：工件裡「so the pipeline knows totals must be recomputed」的因果子句已死（旗標無人讀取）——兩組皆無提示發現；已補為 inventory #6 供未來輪次（本輪以 5 種子計分）。
- 觀察到未被指標懲罰的不合規：skill 報告開場為流程宣告（「`/mental:sync` 完成。…」）——detection 協定無 gist rubric。已在 sync SKILL.md 補 answer-first 行（**預防性修正，本輪未經 eval 驗證**——recall 飽和，重跑量不到差異）。
- 下輪 battery 改進：跨檔語意漂移（如 pipeline 呼叫順序變更）、分類精確度計分（changed/contradicted/removed/unverifiable 逐項對標，而非只看實質指出）。

## change 表達層收尾（iteration-9 → 10）

change skill 版本沿革：v1（檔尾一段 presentation 附註，it-8 被測）→ v2（Response contract 章節＋workflow 步驟內就地改寫 `$build`/選型報告的位置，it-9）→ v3（補禁「模式宣告」開場＋methodology 新增 side-effect 主張須 path-specific 規則，it-10）。

- **Iteration-9**（v2 驗證）：intent 案表達痊癒（gist 3.5→**5**、overhead 4→**5**）證明「規則進 workflow 動線」是對的機制；decision 案殘留三句英文 meta 開場（"This is a decision-mode comparison…"，模式宣告不在 v2 禁列）gist 3；另 calibration 抽驗抓到一條真實杜撰——宣稱 force 路徑 rebuild 會設 `reprice_required=True`，實際只有 TTL 過期分支會設（相鄰路徑混淆）。
- **Iteration-10**（v3 定案）：兩案 **13/13 全過**，gist **5/5**、overhead **5/5**、coherence 4/4、concreteness 5/5、杜撰 0、grader 一致率 1.0——全面追平或反超裸模型（4/4.5）。change 迴圈關閉。
- 種子沿用：兩輪的 bare 與 floor 均拷自 iteration-8/9（輸入未變，重評只加噪音）。
