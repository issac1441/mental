# mental

`mental` 幫助你直接在 Claude Code 或 Codex 裡理解 repo 與指定的學習材料。你可以用它解釋系統、評估預定變更、review 已完成的實作、學習主題，或檢查自己是否真的理解。

[English README](README.md)

## Quickstart

### 1. 載入 plugin

Claude Code：

```sh
git clone https://github.com/issac1441/mental.git /absolute/path/to/mental
cd /path/to/你的-project
claude --plugin-dir /absolute/path/to/mental
```

Codex 請先從已設定的 plugin marketplace 安裝 `mental`，再開啟專案：

```sh
codex -C /path/to/你的-project
```

Claude Code 使用 `/mental:<skill>`；Codex 使用 `$mental:<skill>` 或 skill selector。

### 2. 直接理解一件事

```text
/mental:understand 一個 request 如何走過這個 repo？
$mental:understand 一個 request 如何走過這個 repo？
```

`understand` 可以直接使用，不需要先建立 `mental/` workspace。

### 3. 實作前理解變更

```text
/mental:change 加入 request timeout，但不要改變 failure behavior。
/mental:change 告訴我目前 plan 中 option A 的實際影響。
```

你可以回答 prediction question；如果只想直接看說明，輸入 `skip`。除非加上 `record=true`，否則這個 skill 不會寫檔。

### 4. Review 已完成的工作

```text
/mental:review Review 目前 diff。
/mental:quiz current-change items=12 feedback=end format=mixed
```

`review` 會說明 Before → After 行為並列出 findings；`quiz` 用來檢查你是否能重建這次變更。

### 5. 從指定材料學習

```text
/mental:learn 根據 docs/event-loop.md 教我 event loop。
/mental:practice event-loop
/mental:quiz event-loop items=15
```

`learn` 會先提出 2–5 題短診斷。使用 `practice` 進行自適應練習；使用 `quiz` 進行完整測驗。

### 6. 保存可重用模型（選用）

```text
/mental:build 保存這個 session 中可重用的模型。
```

建立 artifacts 後可以使用：

```text
/mental:sync
/mental:doctor
```

## Skill 參考

| Skill | 語法 | 用途 | 預設寫入 |
| --- | --- | --- | --- |
| `understand` | `<問題> [job=...] [lens=...]` | 解釋 repo、文件、session 或指定主題 | 無 |
| `change` | `<變更或問題> [job=decide\|predict] [lens=...] [record=true\|false]` | 比較預定變更、選項、plan 或 TODO list | 無 |
| `review` | `[diff-or-ref] [job=verify\|predict] [lens=...]` | 解釋並審查已完成的工作 | 無 |
| `learn` | `<目標或範圍> [lens=...]` | 診斷 prerequisite，並依指定來源教學 | 同意後才保存私人進度 |
| `practice` | `[範圍] [lens=...]` | 執行會隨回答調整的練習 | 同意後才保存私人進度 |
| `quiz` | `[範圍] [items=12] [feedback=end\|after-each] [format=mixed\|open\|mcq] [lens=...]` | 執行固定 10–20 題的完整測驗 | 同意後才保存私人結果 |
| `build` | `[來源或範圍] [mode=repository\|learning\|hybrid] [language=...]` | 建立或擴充可重用 artifacts | `mental/` 與 `.mental/` |
| `sync` | `[範圍]` | 來源改變後刷新既有 artifacts | `mental/` |
| `doctor` | `[範圍] [repair=true\|false]` | 檢查結構、link、證據、conflict 與 privacy | 除非 `repair=true`，否則無 |

## 共用參數

通常不需要手動指定這些值；skill 會從你的問題與目前 session 推論。

- `lens=` 控制預設角色與語彙：`general`、`engineer`、`architect`、`pm`、`operator`、`student`、`researcher` 或 custom lens ID。
- `job=` 控制目前任務：`orient`、`decide`、`predict`、`verify` 或 `repair`。

例如：

```text
/mental:understand lens=pm job=orient 說明 checkout service。
/mental:understand lens=architect job=predict 說明 failover 如何運作。
/mental:change job=decide 比較 option A 與 B。
```

<details>
<summary>進階 view override</summary>

熟悉 mental 詞彙的使用者可以指定一個或多個 `views=`：`anchor`、`map`、
`mechanism`、`scenario` 或 `evidence`。一般情況讓 skill 自動選擇即可。

</details>

## 常見流程

- 快速理解 repo：`understand`
- 預定實作：`understand → change → Plan Mode → implementation → review`
- 理解已完成 diff：`review → optional quiz`
- 引導式學習：`learn → practice → quiz`
- 可重用 workspace：`understand → optional build → 日後 sync 或 doctor`

## mental 會建立的檔案

- `mental/` 保存團隊可共享、可版控的 models、sources、scenarios、changes、decisions 與 conflicts。
- `.mental/` 保存私人 profile、答案、mastery state 與 session 紀錄。Scaffold 會設定 Git 忽略這個目錄。

`understand` 與 `review` 永遠不寫檔。學習 skills 只會在你於目前 session 同意後保存私人進度。

## 安裝與驗證

### Claude Code

```sh
claude --plugin-dir /absolute/path/to/mental
claude plugin validate /absolute/path/to/mental
```

需要長期安裝時，請將 repo 加入 Claude Code marketplace，再從 marketplace 安裝 `mental`。

### Codex

從已設定的 plugin marketplace 安裝 `mental`，接著用 `/skills` 或輸入 `$` 選擇 skill。非預設 local marketplace 可使用：

```sh
codex plugin marketplace add /absolute/path/to/marketplace
codex plugin add mental@marketplace-name
```

### OpenCode

OpenCode 目前只提供文件層級相容。將 `skills/`、`references/`、`scripts/`、`assets/` 一起複製或連結到同一個 `.agents/` 目錄，並保留相對路徑。Skills 會以 `understand`、`change` 等未加 namespace 的名稱出現。

## 開發驗證

```sh
python3 -m unittest discover -s tests -v
python3 scripts/scaffold_workspace.py /tmp/mental-demo --mode hybrid --language zh-TW
python3 scripts/validate_workspace.py /tmp/mental-demo
python3 scripts/run_conversation_evals.py --list
python3 scripts/run_conversation_evals.py --host claude --judge-host claude --case understand-without-workspace
```

Workspace scripts 是 skills 的內部 helper，不是公開 CLI。Conversation eval
會真的執行指定 host 與 rubric judge，原始結果寫入 gitignored 的
`eval-results/`。執行 Codex eval 前需先安裝 `mental` plugin。
`--capture-only` 只收集 host 輸出，會標示為 `UNJUDGED` 並以 exit code 2
結束；它不是通過的評測結果。

## 延伸文件

- [設計背景與研究架構](docs/design-background.zh-TW.md)
- [ASD-STE100 評估](docs/ste100-evaluation.zh-TW.md)

## 授權

[0BSD](LICENSE)。你可以自由使用、複製、修改與散布，不需要署名。
