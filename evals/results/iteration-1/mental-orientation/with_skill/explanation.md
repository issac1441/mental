I've now read the repo's manifests, all nine skills' contracts (spot-checked in depth), the shared references, both Python scripts, the templates, and the test suite. Here's the architecture.

---

## 直接答案

這個 repo 是 **`mental`** —— 一個給 Claude Code 和 Codex 用的 **plugin**（外掛），不是 CLI 工具、也不是線上服務。它的作用是幫人把一個 repository 或學習教材，整理成「可驗證、有證據連結的心智模型（mental model）」，並存成檔案。最關鍵的一點：它幾乎**沒有執行程式碼**——它的「邏輯」絕大部分是寫給 agent（LLM）看的 Markdown 指示（9 個 skill + 幾份共用 reference），真正的程式碼只有 2 支 Python 輔助腳本。換句話說，**runtime 就是 agent 本身，架構是「用文件（prompt）當程式」**。

---

## 各個部分是做什麼的

我把目錄按「角色」分成六層，由外而內：

**1. 註冊層 —— 讓兩個 host 認得這個 plugin**
- `.claude-plugin/plugin.json`、`.codex-plugin/plugin.json`：兩份 manifest，內容幾乎一樣，都指向 `"skills": "./skills/"`。一份給 Claude Code、一份給 Codex。
- `.claude-plugin/marketplace.json`：讓這個 repo「自己就是一個 marketplace」，所以使用者不必另建 marketplace repo 就能安裝（`README.md:189`）。

**2. 介面層 —— 9 個 skill（真正的使用者介面）**
- 位於 `skills/<name>/SKILL.md`，共 9 個：`understand`、`build`、`sync`、`doctor`、`change`、`review`、`learn`、`practice`、`quiz`（清單見 `README.md` 的 Skills 表格；被 `tests/test_plugin_contract.py:10` 鎖定）。
- 每個 skill 是一個資料夾，含一份 `SKILL.md`（給 agent 的自然語言指示，**這就是「程式碼」**）加一份 `agents/openai.yaml`（Codex 的 UI 名稱／描述）。
- 使用者在目標 repo 裡打 `/mental:understand ...`（Codex 用 `$mental:understand ...`），host 就載入對應的 `SKILL.md`。這正是你現在觸發的流程。

**3. 共用準則層 —— references（所有 skill 的「共同大腦」）**
- `references/methodology.md`：核心方法論 **Lens × Views × Detail**（用什麼角色視角、要哪些語意切片、多深），以及「四種真相」`[observed]/[inferred]/[agreed]/[conflict]`。
- `references/artifact-contract.md`：產出檔案的目錄結構與 frontmatter 規則。
- `references/writing-profile.md`：寫作風格（STE-inspired）。
- `references/repository-workflow.md` 與 `learning-workflow.md`：repo 模式／學習模式各自的流程。
- **關鍵協作模式**：每個 `SKILL.md` 第一步都是「先讀這幾份 reference」。所以 skill 本身很薄，共同規則集中在 references，避免重複——測試 `test_all_skills_load_the_shared_writing_profile` 就強制每個 skill 都要載入 writing-profile。

**4. 決定論骨幹 —— 唯一的真程式碼**
- `scripts/scaffold_workspace.py`：非破壞性地建立空的模型骨架（已存在的檔案會跳過，見 `write_new`）。
- `scripts/validate_workspace.py`：解析 frontmatter、檢查 id/kind/status/sources/連結，並檢查隱私邊界（`.mental/.gitignore` 是否只含 `*` 與 `!.gitignore`，`validate_workspace.py:200`）。可輸出文字或 `--json`。
- `assets/templates/*.md`：上面 scaffold 腳本要填入的樣板（用 `{{TODAY}}` 之類佔位符替換）。
- 兩支腳本都**零相依套件**，README 明講它們是「內部實作細節，不是給使用者的 CLI」。

**5. 產出的資料模型 —— 注意：這是「輸出」，不是原始碼**
- `mental/`：共用、要 commit 進 git 的模型（`index.md`、`sources.md`、`model/map.md`、`concepts/`、`scenarios/`、`contracts/`、`decisions/`、`changes/`、`lenses/` …）。
- `.mental/`：私人、**被 gitignore** 的狀態（`profile.md`、`mastery.json`、`sessions/`）——放個人學習進度與答案。
- 這條「共用 vs 私人」的隱私界線是整個系統的硬性不變量（invariant）。

**6. 支援層**
- `docs/`：設計背景與 STE100 評估（含 `.zh-TW` 版）。
- `tests/`：見下面「協作」——它其實是這套 prompt 系統的「編譯器」。

---

## 彼此怎麼協作

有兩條協作軸線：**單次呼叫的執行鏈**，以及**跨 skill 的生命週期**。

**（A）呼叫一個 skill 時的執行鏈**（以你此刻的 `understand` 為例）：

1. 你在目標 repo 打 `/mental:understand ...` → host 靠 manifest 找到 `skills/understand/SKILL.md`。
2. agent 讀 `SKILL.md`，照指示先載入共用 references（methodology／artifact-contract／writing-profile）。
3. 找 workspace root，讀 `mental/` 的既有模型與它引用的來源。
4. 依 **Lens×Views×Detail** 的優先序選好視角，組出解釋；`understand` **全程唯讀**，不寫任何檔案。

`build` 的鏈多兩步：若 `mental/` 不存在，`SKILL.md` 會叫 agent 跑 `scaffold_workspace.py` 生骨架（把 `assets/templates/` 渲染出來），填完證據後再跑 `validate_workspace.py` 檢查，最後停在一個 **promotion gate（升級關卡）** 等人確認，才把 draft 變 `canonical`。這就是腳本、樣板、skill 三者接手的地方。

**（B）圍繞同一份 `mental/` 資料模型的生命週期**（各 skill 像圍著同一份文件分工）：

```
build  →  understand  →  change  →（人做決定）→ Plan Mode → 實作 → review → quiz → sync
建立草稿    唯讀解釋      提出變更 delta                              審核實際差異        對齊模型
```

- `build`：建 draft，會呼叫兩支腳本，停在 promotion gate（`skills/build/SKILL.md`）。
- `understand`：唯讀，讀模型回答問題（就是現在）。
- `change`：實作**前**先把「打算怎麼改」講成模型 delta，預設唯讀，只有你明講 `record=true` 才寫 `mental/changes/<id>.md`；結尾一定停在 `Human Decision: pending`（`skills/change/SKILL.md:35`）。
- `review`：實作**後**，先重建 `Before → After` 再對照 canonical 稽核，唯讀，並會建議接著用 `$quiz`／`$sync`（`skills/review/SKILL.md:29`）。
- `sync`：偵測「來源已變、模型過時」的 drift，寫 draft delta 但**不擅自把 `[agreed]` 改回 `[inferred]`**，會呼叫 validator（`skills/sync/SKILL.md:17`）。
- `doctor`：稽核整個 workspace，跑 `validate_workspace.py --json` 再加語意檢查（`skills/doctor/SKILL.md:13`）。
- `learn`／`practice`／`quiz`：教學與評量，只寫 `.mental/` 私人狀態。

貫穿全部的兩條**不變量**，就是各部分協作的「憲法」：**(1)** 區分四種真相、**沒有人確認前不把 `[inferred]` 悄悄升成 `[agreed]`**；**(2)** 共用模型放 `mental/`、私人狀態放被 gitignore 的 `.mental/`。`change`/`review`/`understand`/`doctor` 的「唯讀」宣告，和 validator 的隱私檢查，都是在守這兩條線。

**（C）測試是這套系統的「編譯器」**：因為邏輯是文件而非程式，`tests/test_plugin_contract.py` 檢查的是**文件之間是否一致**——兩份 manifest 是否鎖定同一組 skill、9 個 skill 是否都在、每個 skill 是否都載入 writing-profile、每個 skill 是否含 `behavior_cases.json` 規定的關鍵語句、唯讀邊界字句是否存在。`tests/fixtures/` 底下還有一份 repository 模式與 learning 模式的**完整範例 workspace**，同時當作 validator 的測試資料與參考範例。

---

## 一個會絆倒新接手者的邊界

不要用「一般程式專案」的直覺讀它：這裡**沒有 server、沒有進入點函式、沒有執行時邏輯**可追。你在 `skills/*.md` 看到的動詞（「read」「validate」「stop for human」）不是虛擬碼，而是**真的要由 agent 執行**的指令；真正會跑的程式只有 `scripts/` 那兩支。所以看架構要看的是「文件之間如何互相引用與互相約束」，而不是 call graph。

最後一點：**這個 repo 目前沒有屬於它自己的 canonical `mental/` 模型**（`mental/` 目錄不存在），所以上面這份說明是我**直接讀原始檔案**得出的 `[inferred]`，尚未經人確認。如果你想把它固化成可維護、可 review、可被 `understand` 反覆查詢的心智模型，可以跑 `$mental:build`（例如 `/mental:build Build a repository mental model for the current workspace.`）——它會建 draft 並停在 promotion gate 讓你逐項確認。我在這裡不會替你新增任何檔案。

---

**Sources and gaps**
- 定位與介面：`README.md`、`.claude-plugin/plugin.json`、`.codex-plugin/plugin.json`、`.claude-plugin/marketplace.json`
- Skill 契約：`skills/{understand,build,change,review,sync,doctor}/SKILL.md`、`skills/build/agents/openai.yaml`
- 共用準則：`references/{methodology,artifact-contract,writing-profile,repository-workflow,learning-workflow}.md`
- 決定論骨幹：`scripts/scaffold_workspace.py`、`scripts/validate_workspace.py`、`assets/templates/index.md`
- 契約測試：`tests/test_plugin_contract.py`、`tests/behavior_cases.json`、`tests/fixtures/`
- 未讀（gap）：`learn`/`practice`/`quiz` 三個 skill 的 `SKILL.md` 我只從 README 表格與測試斷言推得其職責，未逐行細讀；`docs/` 的設計背景、`tests/test_workspace_scripts.py` 未讀。若你要我深入教學／評量那條線，我可以再補。

**Context**: architect lens · map,mechanism,scenario · standard —— 依你「快速理解整體架構、各部分職責與協作」的明確目標選定（比 repo 預設的 engineer 更貼題）；要調整可加 `lens=engineer`、`views=...`、`detail=deep`（例如想逐一深看每個 skill）。