# mental

`mental` 是一套縮短「agent 已經做完」與「人類真正理解」之間落差的 Agent-native plugin。它讓使用者直接在 Claude Code 或 Codex 裡定位問題、預測、決策、review、學習與修正模型。

它不是獨立 CLI、託管服務或原始材料的替代品，也沒有後端、帳號、遙測、MCP server 或外部 LLM API。使用者介面是九個 skills；Python 腳本只供 skills 內部做確定性建檔與檢查。

[English README](README.md)

設計文件：[設計背景與研究架構](docs/design-background.zh-TW.md) · [STE100 評估](docs/ste100-evaluation.zh-TW.md)

## Quickstart

### 1. 載入 `mental`

Claude Code 開發環境：

```sh
git clone https://github.com/issac1441/mental.git /absolute/path/to/mental
cd /path/to/你想理解的-repo
claude --plugin-dir /absolute/path/to/mental
```

Codex 請先依照[安裝與驗證](#安裝與驗證)，從已設定的 plugin marketplace 安裝 `mental`，再開啟目標 repo：

```sh
codex -C /path/to/你想理解的-repo
```

### 2. 先問，不需要設定 artifacts

```text
/mental:understand 一個 request 如何走過這個 repo？
$mental:understand 一個 request 如何走過這個 repo？
```

`understand` 會讀取目前 session，以及最小必要的 repo 或指定來源證據。即使 `mental/` 不存在也能直接回答，而且不會寫檔。如果同一個模型以後還會使用，它才會提議 `build`；持久化不是入場費。

### 3. 在實作前預測並決策

```text
/mental:change 加入 request timeout，但不要改變 failure semantics。
/mental:change 告訴我目前 plan 中 option A 的實際影響。
```

如果 prediction 能揭露重要 model gap，`change` 會先問人，等待回答或 `skip`，再拿證據比較。明確要求直接回答時不會強迫小考。人類核准的是期望行為與 trade-off，不是沒有證據的事實。

### 4. 理解實際發生的變更

```text
/mental:review Review 目前 diff。
/mental:quiz current-change items=12 feedback=end format=mixed
```

`review` 會重建 Before → After，把核准後才浮現的選擇標成 Decision Surprise，並檢查有界的 `Model × Harness × Task Class` trust unit。

### 5. 有價值後才持久化

```text
/mental:build 保存剛才建立、以後還會重用的模型。
```

`build` 是進階 persistence skill。它保存可重建的 mechanical artifacts、附有驗證要求的 conceptual drafts、decision history 與 first-class conflicts；不會為了追求完整 coverage 建立巨型 wiki。

## 互動模型

`mental` 使用 **Lens × Job**：

- **Lens** 是塑造 session 回答的角色知識、語彙、關注與決策方式：`general`、`engineer`、`architect`、`pm`、`operator`、`student`、`researcher` 或 custom lens。
- **Job** 是使用者此刻要完成的認知工作：`orient`、`decide`、`predict`、`verify` 或 `repair`。

Agent 會從目前目標與 session 自動推論兩者；手動 `lens=` 與 `job=` 永遠優先。Anchor、map、mechanism、scenario、evidence 等 Views 保留為 agent 內部選擇語彙。熟悉它們的使用者仍可用 `views=` 進階 override，但第一次使用不需要先懂這套分類。

`mental` 不會每次重複印出 context header。只有使用者手動指定、選擇不是預設、存在不確定性，或揭露後可以採取行動時，才會說明 Lens、Job 或 Views。

## Skills

### 主要 skills

| Skill | 使用時機 | 預設寫入 |
| --- | --- | --- |
| `understand` | 需要立即解釋或 orientation | 無 |
| `change` | 實作前需要預測、比較或決策 | 無；要求記錄時才寫 |
| `review` | Agent 做完後，需要理解實際變更 | 無 |
| `learn` | 需要診斷與自適應的 source-bound 教學 | 有學習證據且明確同意保存後才寫 private state |
| `practice` | 需要跟著回答調整的修正與遷移練習 | 有學習證據且明確同意保存後才寫 private state |
| `quiz` | 需要完整、固定 coverage 的測驗 | 明確同意保存後才寫 private result |

### 進階 persistence 與維護

| Skill | 使用時機 |
| --- | --- |
| `build` | 有用模型、Lens、decision 或 conflict 值得保存 |
| `sync` | 已註冊來源改變，durable artifacts 需要刷新 |
| `doctor` | Durable workspace 的 authority、證據、decision、conflict、link 或 privacy 可能有問題 |

每個 skill 內的 Input contract 是正式參數定義。Host 介面可能顯示 description 或 default prompt，但 Claude Code 與 Codex 不保證都有列舉型參數 autocomplete。

## Artifact authority

每個 artifact 都會說明誰能更新它：

| Authority | 意義 | States |
| --- | --- | --- |
| `mechanical` | 可從已註冊證據重新生成 | `current`、`stale` |
| `conceptual` | 有驗證依據的 durable working explanation | `draft`、`active`、`stale` |
| `decision` | 人類意圖、trade-off 或已接受變更 | `pending`、`accepted`、`rejected`、`superseded` |

`active` 表示「具有明確驗證依據的目前 working model」，不是絕對真理。「看起來沒問題」或 recognition 不是 verification。Mechanical artifacts 不需要人類核准事實；人類 decision 也不能讓沒有證據的主張變真。

Conflicts 放在 `mental/conflicts/`，具有穩定 ID、`open|resolved`、雙方主張與證據、owner 和 resolution history。重大選擇放在 `mental/decisions/` 的 append-preserving decision ledger。

團隊共用 artifacts 放在 `mental/`；個人目標、答案、進度與 session 放在 gitignored `.mental/`。

## 代表性流程

**Vibe coding：**`understand → change → human prediction/decision → Plan Mode → implementation → review → optional quiz → advanced sync`

**快速提問：**只用 `understand`，不必建 artifacts。

**產品決策：**`understand lens=pm → change job=decide → human decision → Plan Mode → review`

**學習：**`learn 指定來源 → practice → quiz → optional build`

**Durable model：**`understand → 證明有重用價值 → build → 日後 sync/doctor`

## 安裝與驗證

### Claude Code

```sh
claude --plugin-dir /absolute/path/to/mental
claude plugin validate /absolute/path/to/mental
```

正式分發時，請將 repo 加入 Claude Code marketplace 後安裝 `mental`。

### Codex

從已設定的 plugin marketplace 安裝 `mental`，接著用 `/skills` 或 `$` 選擇 skill。非預設 local marketplace 可使用：

```sh
codex plugin marketplace add /absolute/path/to/marketplace
codex plugin add mental@marketplace-name
```

套件使用 `.codex-plugin/plugin.json` 與 `skills/*/SKILL.md`；Claude 與 Codex 共用相同技能語意。

### OpenCode 相容模式

目前僅提供文件層級相容，不承諾 native namespace parity。將 `skills/`、`references/`、`scripts/`、`assets/` 一起複製或連結到同一個 `.agents/` 目錄並保留相對路徑；OpenCode 會以 `understand`、`change` 等未加 namespace 的名稱發現它們。

## 開發驗證

本專案沒有 runtime dependencies：

```sh
python3 -m unittest discover -s tests -v
python3 scripts/scaffold_workspace.py /tmp/mental-demo --mode hybrid --language zh-TW
python3 scripts/validate_workspace.py /tmp/mental-demo
```

Python helpers 是 skill 內部實作細節，不是公開 CLI。

## 授權

[0BSD](LICENSE)。可以自由使用、複製、修改與散布；重新散布時不要求署名，也不要求保留著作權聲明。
