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
- 已知非鑑別題：orderflow-failure probe 8（carrier 選擇）——三個說明 arm 都自然省略該內容，懲罰的是問題範圍外的涵蓋度；改版收錄於下一輪 battery 調整。
