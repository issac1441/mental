# Learning-transfer evaluation

評估目標：`mental` 的解釋型 skills（首先是 `understand`）產出的說明，是否真的讓人**由淺入深、快速**建立可預測系統行為的心智模型——而不是只把框架展示出來。基準線是**同一個模型、不掛 skill** 的裸回答，因為那正是使用者實際比較的對象。

## Method

每個 (case, arm) 跑三個階段，全部用同一個 model + effort（預設 `claude-opus-4-8` + `--effort max`），唯一變因是說明文件本身：

1. **Explain** — agent 在目標 repo 內回答案例問題。三個 arm：
   - `with_skill`：目前的 `skills/understand/SKILL.md`
   - `old_skill`：改版前的 snapshot
   - `without_skill`：裸模型（使用者的實際基準線）
2. **Learn** — 一個**看不到程式碼、禁用所有工具**的全新 agent，只讀說明文件，回答 5 題 probe。這直接度量「知識轉移」：說明沒教會的，讀者就答不出來。
3. **Grade** — 有 repo 存取權的評分 agent（對 arm 盲測）：
   - 逐題比對 probe 答案與 ground truth（答「說明中沒有提到」計為未通過）；
   - 依 rubric 評 1-5：`gist`（開頭即答案）、`coherence`（敘事連貫）、`overhead`（內容前無框架負擔）、`concreteness`（主張連到檔案/測試）；
   - 抽查最多 3 個檔案引用是否存在且支持主張。

### 為什麼 eval 目標不用知名開源專案

模型對知名專案（如 requests）有先備知識，learner 不看說明也答得出 probe，三個 arm 會被拉平。因此目標是：

- `fixtures/orderflow/` — 本 repo 自帶的合成訂單管線（保證不在訓練資料中），埋了可鑑別的機制：免運門檻看**折扣前**小計、只有 `RetryableError` 會重試、保留過期觸發重新計價、dead-letter 補償等；
- 這個 repo 本身（近期才存在，模型沒看過）——最接近「對自己的 branch 問問題」的真實情境。runner 會複製一份排除 `evals/` 的乾淨副本作為目標。

### Probe 設計原則

- 每案 5 題，混合：事實回憶、機制因果（為什麼 X 在 Y 之後）、**遷移/預測**（給新數字算結果）、失敗語意。
- Ground truth 逐條先與程式碼比對過（見各 `cases/*.json` 的 `Source:` 欄位）。
- Learner 被明確允許「答不出來就說沒提到」，避免用猜的稀釋訊號。

### 指標

- **transfer accuracy**：probe 通過率（主指標——「學得快不快」的操作化）。
- **rubric**：gist / coherence / overhead / concreteness（「好懂、由淺入深」的操作化）。
- **citations**：引用可驗證性（mental 的核心賣點，不能為了好懂而犧牲）。
- **效率**：timing.json 記錄說明字數與 explainer tokens/時間——同等傳達力下，較短者勝。

## Run

```sh
python3 evals/run_eval.py \
  --workspace /tmp/mental-eval \
  --iteration 2 \
  --arms with_skill,old_skill,without_skill \
  --old-skill-path /path/to/skill-snapshot/skills/understand/SKILL.md \
  --graders 2
```

v2 battery（[metrics-v2.md](metrics-v2.md) 的 standard 配置）：分層 probe（retention/near/counterfactual/diagnosis/repair/edges/scope/decision，含 trap 標記）、learner 信心收集（Brier）、前 25% 截斷閱讀（由淺入深曲線）、`nontech-pm` persona case（S1 可及性＋F5 內容高度）、埋藏邊界覆蓋勾稽、肯定斷言抽驗（false certainty）、逐段 extraneous 記帳、grader ensemble（`--graders 2`，保守 AND 合併並記錄一致率）、`null_floor` 控制組（無說明作答的先備知識地板，主指標改看 lift over floor；`--no-floor` 可關）。

- 需要已登入的 `claude` CLI。所有子代理固定 `--model claude-opus-4-8 --effort max`（可用 `--model/--effort` 覆蓋，但除非你要測的變因就是模型，否則不要改）。
- 可續跑：已存在的 stage 輸出會被跳過（`--force` 重跑）。
- 輸出為 skill-creator 相容格式（`grading.json`、`timing.json`、`outputs/`），可直接餵給其 `aggregate_benchmark` 與 `generate_review.py`。

## Roadmap

指標的深化設計（遷移深度分層、認知邊界、校準、關係圖回收、output style 與 ELI5 可及性、Lens fitness 與內容高度、Decision Surprise Rate、控制組與統計加固）見 [metrics-v2.md](metrics-v2.md)。

## Interpreting

- `without_skill` 是要打敗的線：使用者回饋裸 Opus 的說明比舊版 skill 好懂約 20%。
- 若 `with_skill` 在 transfer 與 rubric 上 ≥ `without_skill`，且 citations 更好，skill 才算提供淨價值。
- 單次運行每案樣本小（n=1/arm/case），把結果當方向訊號；重要決策前用多 iteration 或多 case 累積。
