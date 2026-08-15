# mental

`mental` 是一套住在 Claude Code 與 Codex 裡的 Agent-native skills。它把使用者指定的 repo、文件、文字或網址整理成可驗證、可版本化的 mental model，並透過 agent 協助理解、學習、練習與修正模型。

它不是另一個獨立 CLI，也沒有後端、帳號、遙測、MCP 或外部 LLM API。使用者面對的是 `/mental:*`／`$mental:*` skills；Python 腳本只供 skills 內部進行確定性的建檔與檢查。

[English README](README.md)

## 核心想法

Agent 產生實作的速度，可能遠高於人類重建正確 mental model 的速度。`mental` 因此不把巨大 diff 或長篇文件當成主要 review 單位，而是讓操作者確認：

- 這件事的 Anchor 與主要關係是什麼？
- 目前採用哪個 Lens、哪個 Zoom？
- 哪些是來源觀察、agent 推論、人類共識或尚未解決的衝突？
- 正常情境、失敗情境、契約與不變量是什麼？
- 新變更造成了什麼 Model Delta 與 Decision Surprise？

共享模型放在 `mental/` 並可進版控；個人目標、答案、程度與 session 紀錄放在 `.mental/`，預設不會被 Git 追蹤。

## Skills

### 共用

- `/mental:understand <問題>`：唯讀地以最小必要 Lens × Zoom 解釋；沒有 canonical model 時明確標記推論，不暗中建檔。
- `/mental:build <來源>`：從目前 repo 或指定材料建立 draft artifacts；經人類確認前不得 canonicalize。
- `/mental:sync [範圍]`：比較來源與 canonical model，先產生 draft delta；不會靜默消除衝突。
- `/mental:doctor`：檢查 schema、連結、證據、孤立概念、過期模型與私密資料外洩。

### Repo

- `/mental:change <意圖>`：在寫程式前整理 Current Model、Prediction、Model Delta、Decision Manifest、契約、不變量、情境與失敗行為，等待人類決定。
- `/mental:review [diff/ref]`：以模型影響為主審查變更，預設完全唯讀。

### 學習

- `/mental:learn <目標>`：先以 2–5 個高資訊量問題診斷概念缺口，再分小段教學。
- `/mental:practice [範圍]`：用回想、teach-back、遷移、除錯與反例驗證理解，而不是只做辨識型選擇題。

學習 mastery 只使用 `unknown`、`exposed`、`working`、`verified`。答錯代表模型中的關係仍有缺口，不是對人的能力標籤，也不會產生看似精準的數字分數。

## 安裝與測試

### Claude Code

開發時可直接載入 checkout：

```sh
claude --plugin-dir /absolute/path/to/mental
```

驗證 plugin：

```sh
claude plugin validate /absolute/path/to/mental
```

載入後可使用 `/mental:understand`、`/mental:build` 等指令。正式分發時，將 repo 加入 Claude Code marketplace 後安裝 `mental`。

### Codex

從已設定的 plugin marketplace 安裝 `mental`，接著用 `/skills` 或 `$` 選擇 `mental` skills。本機開發 marketplace 的基本流程為：

```sh
codex plugin marketplace add /absolute/path/to/marketplace
codex plugin add mental@marketplace-name
```

Codex 的實際顯示方式由當前介面決定；技能的語意與 Claude Code 版本相同。

### OpenCode 相容模式

V1 不提供 OpenCode 原生 namespace adapter。若要試用，將本 repo 的 `skills/`、`references/`、`scripts/`、`assets/` 一起複製或連結到同一個 `.agents/` 目錄，保留相對路徑。OpenCode 會以 `understand`、`build` 等未加 namespace 的名稱發現它們。

## Artifact 結構

```text
mental/
├── index.md
├── sources.md
├── glossary.md
├── model/map.md
├── concepts/
├── scenarios/
├── contracts/       # repo mode，按需
├── decisions/       # repo mode，按需
├── changes/         # repo mode，按需
├── learning/path.md # learning mode，按需
├── misconceptions/ # learning mode，按需
└── exercises/       # learning mode，按需

.mental/
├── .gitignore
├── profile.md
├── mastery.json
└── sessions/
```

每個共享 Markdown artifact 都必須有穩定英文 ID 與 frontmatter：`id`、`kind`、`status`、`sources`、`prerequisites`、`updated_at`。內容會跟隨使用者語言。

重要主張使用：

- `[observed]`：來源直接支持。
- `[inferred]`：agent 合成、尚待確認。
- `[agreed]`：人類明確接受的概念真相。
- `[conflict]`：來源／實作與 canonical model 不一致。

Canonical 不代表程式碼一定正確；它代表人類同意用這個概念模型理解系統。兩種真相不一致時，`mental` 必須保留並揭露差異。

## Build promotion gate

`build` 一律先產生 `draft`。轉成 `canonical` 前，操作者至少會看到並確認：

1. 模型邊界與核心關係；
2. agent 推論的因果、不變量或 prerequisite；
3. 一個代表性成功情境；
4. 一個失敗、邊界或反例；
5. 來源缺口與衝突。

只 promotion 明確接受的 artifacts；未決項目繼續保持 draft 或 stale。

## 開發驗證

本專案沒有 runtime dependencies：

```sh
python3 -m unittest discover -s tests -v
python3 scripts/scaffold_workspace.py /tmp/mental-demo --mode hybrid --language zh-TW
python3 scripts/validate_workspace.py /tmp/mental-demo
```

詳細 schema 請參考 [artifact contract](references/artifact-contract.md)。

## 授權

MIT
