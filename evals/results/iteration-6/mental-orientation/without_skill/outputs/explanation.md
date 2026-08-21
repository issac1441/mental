我已經把整個 repo 摸清楚了。這是一份給接手者的架構總覽。

---

## 一句話總結

`mental` 是一個 **agent-native plugin**(給 Claude Code / Codex 用),**沒有 runtime、沒有 server、沒有給終端使用者的 CLI**。它的「產品」是 **9 個 skills**(用 Markdown 寫的 agent 指令)加上一套 **嚴格的產物合約(artifact contract)**;唯一會執行的程式碼是兩支零依賴的 Python 腳本。它的用途是:在 Claude Code/Codex 裡,把一個 repo 或學習素材,變成「可驗證、可追溯證據」的心智模型(mental model)。

真正的「邏輯」是寫在 `SKILL.md` 裡的散文式工作流程,不是傳統程式碼——這是理解這個 repo 最關鍵的心態轉換。

---

## 六個層次(依系統自身結構分)

**1. 打包 / 被發現層 — 讓 host 找到並載入 plugin**
- `.claude-plugin/plugin.json` — Claude Code 的 manifest,`skills` 指向 `./skills/`
- `.claude-plugin/marketplace.json` — 讓這個 repo **自己就是一個 marketplace**,不需另建 marketplace repo 就能持久安裝
- `.codex-plugin/plugin.json` — Codex 的 manifest,多了一個 `interface{}` 區塊(顯示名稱、預設 prompt)
- 兩邊都指向**同一個 `skills/`** → 所以 README 說「Claude 和 Codex 共用相同的 skill 語意」

**2. Skills 層 — 這就是「介面」,也是實際的「程式」**

9 個 skill,每個是一個資料夾,含 `SKILL.md`(frontmatter 的 `name`+`description` 決定何時被觸發;body 是編號的 Workflow + Output)與 `agents/openai.yaml`(Codex 專用的介面 metadata)。依職責分四組:

| 群組 | Skills | 作用 |
|---|---|---|
| 建模生命週期 | `build` / `sync` / `doctor` | 建立草稿模型 / 提出來源→模型的差異 / 稽核工作區 |
| 解釋 | `understand` | 用選定的 Lens×Views×Detail 解釋(唯讀) |
| 變更生命週期 | `change` / `review` | 實作**前**談意圖與取捨 / 實作**後**解釋並稽核 diff |
| 學習 | `learn` / `practice` / `quiz` | 適性教學 / 一次修一個弱關係 / 完整有界測驗 |

**3. 共享規則層 `references/` — 單一事實來源(DRY 核心)**

skills **不重複規則**,而是每支 Workflow 第一步就去讀這些檔(我確認過:9/9 skill 都引用):
- `methodology.md` — 核心方法 **Lens × Views × Detail**、三種真實(observed/inferred/agreed)、解釋的寫法、兩種工作流程
- `artifact-contract.md` — 產物的磁碟格式(frontmatter schema、證據標記、promotion gate、隱私邊界)
- `writing-profile.md` — 使用者可見文字的寫法
- `repository-workflow.md` / `learning-workflow.md` — 兩種模式的流程

**4. 產物 / 資料模型層 — skills 產出的東西**
- `mental/`(**共享、進 git**):`index`、`sources`、`glossary`、`model/map`、`concepts/`、`scenarios/`、`lenses/`,以及 repo 模式(`contracts/` `decisions/` `changes/` `architecture`)與學習模式(`learning/path` `misconceptions/` `exercises/`)的按需目錄
- `.mental/`(**私有、gitignore**):`profile.md`、`mastery.json`、`sessions/` — 個人目標、答題、進度
- `assets/templates/` — 每種產物的種子模板,scaffold 會把 `{{VAR}}` 填入
- **鐵律:共享的「概念真實」與私有的「個人狀態」永不混放**

**5. 執行 / 驗證層 `scripts/` — 唯一的可執行程式碼(零依賴 Python)**
- `scaffold_workspace.py` — 從模板**非破壞性**地建出 `mental/` + `.mental/` 骨架(被 `build` 呼叫)
- `validate_workspace.py` — 驗證產物合約:frontmatter、id、kind、status、來源引用、壞連結、隱私 gitignore、`mastery.json` 形狀(被 `build`、`doctor`、`sync` 呼叫)。**這支腳本是合約中「機器可檢查」的那一半。**

**6. docs 與 tests**
- `docs/` — `design-background`、`ste100-evaluation`(雙語,講「為什麼這樣設計」)
- `tests/` — `test_plugin_contract.py`(守 plugin 打包不變量)、`test_workspace_scripts.py`(守兩支腳本)、`behavior_cases.json` 與 `fixtures/`

---

## 它們怎麼協作

**一次 skill 呼叫的流程:**
```
host 依 manifest 載入 → 使用者呼叫 /mental:build(Codex 是 $mental:build)
  → agent 讀該 SKILL.md 的 Workflow
  → 第一步:讀 references/*(規則都在這,不在 SKILL 裡重複)
  → 依 artifact-contract 讀來源、讀寫 mental/ 與 .mental/
  → build 會 scaffold;build/doctor/sync 會 validate
```

**串起 9 個 skill 的生命週期**(來自 README 與 methodology):
- **Repo 工作流**:`build → understand → change →〔人做決定〕→ host Plan Mode → 實作 → review → quiz → sync`
- **學習工作流**:`build → learn → practice → quiz`

**貫穿全系統、把各部分綁在一起的三條紀律:**
1. 一切先是 `draft`,經過**人審核的 promotion gate** 才變 `canonical`——沒有 skill 能自己把草稿變定案
2. 每個宣稱都標記出處:`[observed]`(有來源)/ `[inferred]`(AI 綜合)/ `[agreed]`(人確認)/ `[conflict]`(來源與定案模型衝突,絕不悄悄和稀泥)
3. 共享概念真實(`mental/`) vs 私有個人狀態(`.mental/`)嚴格分離

---

## 給接手者的幾個要點(避免踩雷)

- **改「行為」是改 Markdown,不是改 code。** 想調整某個 skill 怎麼運作,去編輯它的 `SKILL.md`;`.py` 只負責 scaffold 與 validate。
- **規則要改就改 `references/`。** 那是 DRY 的單一來源,9 個 skill 都會繼承;別把規則複製進個別 `SKILL.md`。
- **`validate_workspace.py` 必須和 `artifact-contract.md` 同步。** 兩者是同一份合約的「機器版」與「文字版」。若要新增一種 artifact kind,得同時改:`artifact-contract.md`、validator 裡的 `ALLOWED_KINDS`、`assets/templates/`、以及 `scaffold_workspace.py`。
- **Claude 與 Codex 共用 `skills/`。** 動介面時,兩份 manifest 與各 skill 的 `agents/openai.yaml` 要一起維持一致;`tests/test_plugin_contract.py` 會守這些打包不變量。

要驗證環境沒問題,README 給的指令是:`python3 -m unittest discover -s tests -v`。

---

需要的話,我可以接著幫你:(1) 把上面這張架構圖做成一個可視化的 artifact 頁面方便你日後查閱;(2) 深入任一條工作流程(例如 `change → review → sync` 實際怎麼讀寫哪些檔);或 (3) 跑一次測試確認你接手的狀態是綠的。要哪個?