我已讀完 skill 指示、三份 reference，並實際讀過這個 repo 的 manifests、9 個 skills、兩個 Python 腳本、references 與 tests。以下是接手導向的架構說明。

---

# mental 這個 repo 的整體架構

## 先給結論

這是一個給 **Claude Code 與 Codex** 用的 plugin，名叫 `mental`,對外介面就是 **9 個 skills**,用途是把「一個 repo 或一份學習教材」轉成**有證據連結、可審閱的心智模型**(mental model)。最關鍵、也最容易踩雷的一點:**這不是一般的可執行軟體,而是「指令即產品」**——真正的執行者是 LLM agent,每個 `skills/*/SKILL.md` 是寫給 agent 照做的工作流程;那兩支 Python 只是 skill 內部呼叫的小工具,不是給使用者跑的 CLI(`README.md:5`、`README.md:223`)。所以你接手要維護的主要是**提示詞(prompt)與規約(contract)**,不是傳統程式邏輯。

---

## 各部分是做什麼的

我按職責分層來講,從外到內:

### 1. Manifests — 註冊層(讓兩個 host 認得這個 plugin)
- `.claude-plugin/plugin.json`、`.codex-plugin/plugin.json`:分別向 Claude Code 與 Codex 註冊,兩者都把 `"skills": "./skills/"` 指到同一個 skills 目錄(`plugin.json:10`)。刻意「只有 skills」——沒有 MCP server、沒有 hooks、沒有 apps(這條由 `tests/test_plugin_contract.py:44-46` 強制)。
- `.claude-plugin/marketplace.json`:讓這個 repo **自己就是一個 Claude Code marketplace**,不用另開 marketplace repo 就能持久安裝(`README.md:189`)。
- Codex 端每個 skill 另有 `skills/*/agents/openai.yaml`,只放 UI 文案(`display_name`、`short_description`、以 `$skillname` 開頭的 default_prompt)。Claude 用 `/mental:xxx`、Codex 用 `$mental:xxx`,但**語意完全一致**(`README.md:207`)。

### 2. Skills — 對外介面(9 個,可分三組記)

| 組別 | Skill | 做什麼 | 預設會不會寫檔 |
| --- | --- | --- | --- |
| **理解/解釋** | `understand` | 用選定的 Lens/Views/Detail 解釋主題 | 不寫 |
| | `change` | 在動手前,把「打算怎麼改」講成模型 delta、攤開取捨 | 不寫(要求才存草稿) |
| | `review` | 改完後,先講「實際改了什麼」再稽核 | 不寫 |
| **建構/維護** | `build` | 從來源產生**草稿** artifacts、或自訂 lens | 只寫草稿 |
| | `sync` | 偵測「原始碼/教材 vs 模型」的漂移,提 delta | 只寫草稿 delta |
| | `doctor` | 稽核工作區結構、證據、隱私邊界 | 預設不寫 |
| **學習/評量** | `learn` | 先診斷 2–5 個缺口,再適性教學 | 只寫私有狀態 |
| | `practice` | 一次修一條「壞掉的關係」,逐題適應 | 只寫私有狀態 |
| | `quiz` | 一次給完整 10–20 題的有界測驗 | 不寫(要求才存私有結果) |

這 9 個名字是被鎖死的:`tests/test_plugin_contract.py:10` 的 `SKILL_NAMES` 和 `:64` 的測試會斷言「skills 目錄剛好就是這 9 個、且 frontmatter 只有 `name` 與 `description`」。

### 3. References — 共用的「腦」(真正的核心邏輯在這裡)
`references/` 下五份文件是所有 skill 共享的規約,也是最該優先讀的:
- `methodology.md`:**Lens × Views × Detail** 選擇法、三種真相(observed/inferred/agreed)、解釋該長什麼樣。
- `artifact-contract.md`:產出檔案的目錄佈局、frontmatter schema、證據標籤、晉升關卡(promotion gate)。
- `writing-profile.md`:STE-inspired 寫作規則(明確聲明**不宣稱** ASD-STE100 合規)。
- `repository-workflow.md` / `learning-workflow.md`:repo 模式與學習模式各自的細節。

重點:**每個 skill 的第一步都是「去讀這幾份 reference」**(例如 `skills/understand/SKILL.md:20`、`skills/build/SKILL.md:12`)。所以 skill 本身很薄,真正的一致性靠 references 這個「單一真相來源」。要改行為準則,是改 references,不是改各個 skill。

### 4. Scripts — 內部機械工具(由 skill 呼叫,不是給人用)
兩支零相依 Python(`README.md:215`「no runtime dependencies」):
- `scripts/scaffold_workspace.py`:`build` 用它產生 `mental/` + `.mental/` 骨架。**非破壞性**——`write_new` 會跳過已存在的檔案(`scaffold_workspace.py:22-28`),所以重跑不會蓋掉你的東西。
- `scripts/validate_workspace.py`:`doctor`、`sync`、以及 `build` 收尾(`skills/build/SKILL.md:23`)都會呼叫。它只做**確定性的結構檢查**:frontmatter 必填欄位、`id`/`kind`/`status` 合法值、source id 有沒有登錄、連結會不會斷、lens 欄位、`.mental/.gitignore`、`mastery.json` 形狀。它**不判斷語意對錯**——這條界線很重要,`doctor` 明講「validator 過了不代表模型語意正確」(`skills/doctor/SKILL.md:27`)。

### 5. Assets — 模板
`assets/templates/*` 是 scaffold 拿去渲染的樣板,用 `{{TODAY}}`、`{{MODE}}` 這類佔位符替換(`scaffold_workspace.py:15-19`)。`lens.md` 給 `build` 造自訂 lens 用;`change.md` 給 `change`/`sync` 記錄 brief 用。

### 6. 產出物(不在本 repo,除了當 fixtures)——貫穿全系統的隱私邊界
skill 跑起來會在**使用者的目標 repo** 產生兩個目錄:
- `mental/`:**共享、要 commit** 的心智模型(index、map、concepts、scenarios…)。
- `.mental/`:**私有、被 gitignore** 的個人狀態(profile、mastery、sessions)。
scaffold 會自動寫入 `.mental/.gitignore = *\n!.gitignore`(`scaffold_workspace.py:81`),validator 會反過來檢查它存在且正確(`validate_workspace.py:200-206`)。`tests/fixtures/{repository,learning}/` 就是兩個完整範例工作區,測試會斷言它們能通過驗證。

### 7. docs 與 tests
- `docs/`:設計背景 + STE100 評估(說明為何寫作規則是「inspired」而非「compliant」的決策紀錄)。
- `tests/`:見下一節,它是把上面所有部分綁在一起的「合約」。

---

## 它們彼此怎麼協作

### 執行期的一次呼叫(這是理解全局的鑰匙)
因為「執行者是 agent」,一次 `/mental:understand …` 的流程是這樣串起來的:

1. 你在目標 repo 裡輸入 `/mental:understand …`(Codex 是 `$…`)。
2. host 讀 `skills/understand/SKILL.md`,把它當指令注入給 agent。
3. skill 第一步叫 agent 去讀共享 references——這等於**用「讀檔」做依賴注入**,references 就是被共用的函式庫。
4. agent 依 references 的方法讀你的目標程式碼/教材來作答;**會寫檔的 skill** 則額外 shell out 去跑 `python3 ../../scripts/...`(scaffold 或 validate)。
5. 要寫的東西只會落在 `mental/`(草稿)或 `.mental/`(私有),而且**任何「草稿→canonical」都會停在人工關卡**等你拍板。

用一句話描述層次依賴:
```
Manifests(註冊) → Skills(薄的流程編排) → References(共用規約/真相來源)
                                        ↘ Scripts + Assets(確定性的機械工作:scaffold/validate/樣板)
                                                        ↘ 產出 mental/(共享) + .mental/(私有)
Tests ── 把上面每一層之間的合約鎖死 ──┘
```

### 一個具體場景:接手 repo 後的典型旅程
README 把它畫成 `build → understand → change →(人工決策)→ Plan Mode → review → quiz → sync`(`README.md:132`、`:138-149`)。落地成動作:
- `/mental:build`:scaffold 產生骨架 → agent 讀你的碼、登錄 sources、先寫 `model/map.md` 再補必要概念 → 全部標 `status: draft` → validate → **給你一個晉升關卡**列出邊界、關係、推論、成功/失敗情境、衝突與缺口,停下來等你選要接受哪些(`skills/build/SKILL.md:9-10`)。
- 你接受後,`/mental:understand`、`/mental:change`、`/mental:review` 就以那份 canonical 模型為底來解釋、比較、稽核。
- `sync` 在原始碼日後漂移時偵測差異;`doctor` 在檔案結構或隱私邊界可能壞掉時體檢。

### tests 如何綁住整體(維護時最該看的地方)
測試不是跑 LLM,而是**檢查 prompt 裡有沒有該有的字**,把「行為」變成確定性檢查:
- `tests/behavior_cases.json` 為每個 skill 列出 `required_phrases`,測試斷言這些字確實出現在對應 SKILL.md(`test_plugin_contract.py:93`)。**這是最實用的「行為規格」入口**——想知道某 skill 的不可退讓行為,先看它在這裡的必含片語。
- 其他斷言:唯讀類 skill 必須明寫寫入邊界(`:101-109`);`understand/change/learn/practice/quiz` 都要出現 Lens/Views/Detail 的共用選擇規約(`:111-120`);所有 skill 都要載入 `writing-profile.md`(`:149`);兩個 manifest 版本、授權要一致(`:36`);skill 引用的每個 support 檔案都要真的存在(`:84`)。
- `test_workspace_scripts.py` 則端到端跑 scaffold+validate:驗證非破壞性、gitignore 生效、壞狀態會失敗、自訂 lens 會過而未知 view 會被擋。

---

## 貫穿全系統的四條不變量(也就是「牽一髮動全身」的槓桿)

理解這四條,就能預測「改某處會發生什麼」:

1. **預設唯讀、寫入必經關卡**:多數 skill 完全不寫;會寫的只產生 `draft`,且晉升成 `canonical` 一定要人工同意(`references/artifact-contract.md:102-110`)。→ 想放寬/收緊,改的是各 skill 的 workflow 步驟與 `test_read_only_skills_have_explicit_write_boundaries`。
2. **證據 vs 共識分離**:`[observed]`/`[inferred]`/`[agreed]`/`[conflict]` 四種標籤;程式碼/測試是「材料真相」,canonical artifacts 是「人類同意的概念真相」,兩者衝突時**絕不默默調和**(`README.md:91-94`)。
3. **隱私邊界**:共享的 `mental/`(commit)對上私有的 `.mental/`(gitignore);個人答案、能力推斷、session 紀錄永遠不進 `mental/`(`references/artifact-contract.md:39`)。
4. **Lens × Views × Detail**:一套「怎麼選解釋角度」的規約只定義在 `methodology.md` 一次,所有解釋型 skill 共用——選擇優先序是 `手動 override → 當前目標 → 本次 session 證據 → 私有 profile → host memory(弱訊號)→ 範圍預設`,且**不得擅自把推斷偏好存起來**(`skills/understand/SKILL.md:24-25`)。

**新增一個 skill 要動哪些地方(槓桿實例)**:新增 `skills/<x>/SKILL.md`(frontmatter 只放 name+description)、`skills/<x>/agents/openai.yaml`、把 `<x>` 加進 `tests/test_plugin_contract.py:10` 的 `SKILL_NAMES`、在 `behavior_cases.json` 補一筆、SKILL.md 內要載入 `writing-profile.md`——少任何一項,測試就會紅。

---

## 最容易誤解的地方(接手時先擋掉)

- **別把 Python 腳本當成主體**。它們是 skill 的實作細節;真正的「邏輯」在 SKILL.md 與 references 的自然語言規約裡。
- **別以為 tests 在測 AI 的回答品質**。它們測的是「prompt 文本合約」——片語在不在、檔案在不在、manifest 一不一致,而**不是**模型輸出對不對。
- **scaffold/validate 不是使用者 CLI**(`README.md:223`),只是 skill 內部呼叫。
- validate 通過 ≠ 模型正確;結構檢查與語意品質是刻意分開的兩件事(`skills/doctor/SKILL.md:27`)。

最後,依 skill 規約提一次:**目前這個 workspace 沒有 canonical 的 `mental/` 心智模型**(只有 `tests/fixtures/` 底下的範例)。上面這份說明是我直接讀原始檔案得出的,尚未落成任何 artifact。若你想把它變成可審閱、可持續維護的模型,可以跑 `/mental:build`(我不會擅自建立檔案)。

---

**Sources and gaps**
- 定位與介面:`README.md:1-11`、`:97-129`;manifests `.claude-plugin/plugin.json:10`、`.codex-plugin/plugin.json`、`.claude-plugin/marketplace.json`。
- 9 個 skills 各自職責:`skills/{understand,build,sync,doctor,change,review,learn,practice,quiz}/SKILL.md`。
- 共用規約:`references/methodology.md`、`references/artifact-contract.md`(佈局 `:6-25`、frontmatter `:61-89`、晉升關卡 `:102-110`)、`references/writing-profile.md`、`references/{repository,learning}-workflow.md`。
- 腳本:`scripts/scaffold_workspace.py`(非破壞 `:22-28`、寫 gitignore `:81`)、`scripts/validate_workspace.py`(`:110-239`)。
- 合約鎖定:`tests/test_plugin_contract.py`、`tests/test_workspace_scripts.py`、`tests/behavior_cases.json`;範例工作區 `tests/fixtures/{repository,learning}/`。
- 缺口/未驗證:我**沒有實際執行** `python3 -m unittest` 或跑 scaffold/validate,所以「測試會通過」是依讀碼推斷,非執行證據;`docs/design-background.md`、`docs/ste100-evaluation.md` 我尚未細讀,設計動機的細節可能還有補充。

**Context**: engineer lens · map,mechanism,scenario,evidence · standard —— 依「你剛接手、要架構導向」這個當前目標與 repository 範圍預設而選;若想更偏邊界/取捨可用 `lens=architect`,想更快用 `detail=brief`,想深入某一塊(例如 build 的晉升流程或 validator 規則)用 `views=mechanism,evidence detail=deep`。