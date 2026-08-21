I have a complete, evidence-grounded picture of the repo. Here's the walkthrough.

---

這個 repo 是 **`mental`** —— 一個給 Claude Code 與 Codex 用的「agent-native」外掛。它幾乎沒有傳統意義上的執行程式碼:整個產品就是 **9 個用自然語言寫成的 skill**(`skills/*/SKILL.md`),由 LLM agent 讀取後照著做。各部分不是靠函式呼叫互相協作,而是靠兩件事:**共讀同一疊 `references/` 契約文件**,以及**共同讀寫 `mental/` 與 `.mental/` 裡的模型檔案**。真正的「程式碼」只有兩支 Python 小工具,是 skill 的內部輔助,不是給人用的 CLI(`README.md:5`、`README.md:223`)。

它解決的問題:程式碼產出速度可能超過人重建正確心智模型的速度,所以 `mental` 幫你把 repo 或學習教材,變成**可審閱、可追溯證據**的心智模型(`references/methodology.md:5-8`)。

## 各個部分是做什麼的

**1. `skills/` —— 對外的唯一介面(9 個 skill)**
每個 skill 是一個資料夾,內含 `SKILL.md`(給 agent 的指令)加一份 `agents/openai.yaml`(只是 Codex 端的 UI 顯示名稱/預設提示,`skills/build/agents/openai.yaml`)。兩個 host 共用同一份 `SKILL.md` 語意。依角色分四組(`README.md:99-113`):

- **建立**:`build` —— 從 repo/檔案/URL 產生 *草稿* 模型;唯一預設會寫檔的 skill,但只寫草稿。
- **解釋**:`understand` —— 就是你現在觸發的這支,用 Lens×Views×Detail 解釋,唯讀。
- **改動決策**:`change`(講清楚一個改動的意圖/選項/效果,唯讀)→ `review`(改完後先還原「改了什麼」再稽核)。
- **學習評量**:`learn`(診斷 2–5 個弱點再教)、`practice`(一次一題適應性練習)、`quiz`(10–20 題有界測驗)。
- **維護**:`doctor`(稽核結構/證據/隱私,唯讀)、`sync`(來源與模型漂移時提出 delta)。

關鍵安全設計是**讀寫邊界**:多數 skill 預設唯讀,測試甚至強制每支唯讀 skill 要寫明界線 —— `understand` 要有「Never edit」、`review` 要有「Do not update artifacts」、`doctor` 要有「Do not edit by default」、`change` 要有「Remain read-only by default」(`tests/test_plugin_contract.py:101-109`)。

**2. `references/` —— 所有 skill 共用的「契約層」(協作的骨幹)**
5 份文件,是 9 個 skill 保持一致的原因。每支 skill 的第一步都是「讀這幾份 references」(例如 `skills/understand/SKILL.md:20`、`skills/build/SKILL.md:12`):
- `methodology.md`:核心方法 Lens×Views×Detail、三種真相(observed/inferred/agreed/conflict)、解釋的寫法。
- `artifact-contract.md`:檔案該放哪、frontmatter 欄位、`[observed]/[inferred]/[agreed]/[conflict]` 標記、草稿升級關卡。
- `writing-profile.md`:STE-inspired 的寫作規範(明確不宣稱 ASD-STE100 合規)。
- `repository-workflow.md` / `learning-workflow.md`:兩種模式各自的流程細節。

**3. `scripts/` —— 唯一的真實程式碼(2 支,零相依)**
- `scaffold_workspace.py`:`build` 用它建出空的 `mental/` 骨架,套用 `assets/templates/` 的樣板,**非破壞性**(已存在的檔不覆寫,`scaffold_workspace.py:22-28`)。
- `validate_workspace.py`:`doctor` 與 `sync` 用它檢查 frontmatter、`kind`/`status`、來源 ID、壞連結、隱私 gitignore、mastery.json(`validate_workspace.py:1`、`skills/build/SKILL.md:23`)。

**4. 產出物 `mental/` 與 `.mental/` —— 注意:不在這個 repo 裡**
這兩個資料夾是外掛在**目標 repo** 產生的東西,不是 `mental` 專案本身的一部分:
- `mental/`:共享、進 git 的心智模型(map、concepts、scenarios、lenses…)。
- `.mental/`:私人、被 gitignore(內容就是 `*` 加 `!.gitignore`,`scaffold_workspace.py:81`)的學習狀態(profile、mastery、sessions)。
你現在的 workspace 還沒有 canonical 的 `mental/` 模型 —— 想建立就跑 `$mental:build`。(這點我只提一次,不會一直推。)

**5. 打包與測試**
`.claude-plugin/plugin.json` 與 `.codex-plugin/plugin.json` 是雙 host 的 manifest,兩者都只指向 `./skills/`、且刻意不含 mcpServers/apps/hooks(`tests/test_plugin_contract.py:44-46`);`.claude-plugin/marketplace.json` 讓 repo 自己就是一個 marketplace。`tests/` 用 stdlib `unittest` 把「契約」釘死(剛好這 9 個 skill、每支都載入 writing-profile、被引用的支援檔都存在…)。`docs/` 是雙語設計背景與 STE100 決策紀錄。

## 彼此怎麼協作(一次走完)

以「接手新 repo」為例,資料流是這樣:

1. Host(Claude Code/Codex)靠 manifest 載入 `./skills/`。
2. 你輸入 `/mental:build`(Codex 用 `$mental:build`)→ agent 讀 `skills/build/SKILL.md`。
3. SKILL.md 第一步叫它去讀 `references/` 那疊契約 → 這就是 skill 之間對齊的機制:**大家讀同一份規則**。
4. `mental/` 不存在時,build 呼叫 `scripts/scaffold_workspace.py` 用 `assets/templates/` 生出骨架。
5. build 把草稿寫進 `mental/`,每個新主張標上 `[observed]/[inferred]/[conflict]`,跑 `validate_workspace.py` 檢查,然後停在**升級關卡**等你決定(`skills/build/SKILL.md:22-25`)。
6. 你接受後,主張才變 `[agreed]`、狀態才從 `draft` 變 `canonical` —— 只有人能升級,agent 不會偷偷把推論當共識(`references/methodology.md:77-83`)。
7. 之後 `understand` 讀那些 canonical 檔來回答你;`change`→(host Plan Mode)→`review`→`quiz`→`sync` 串起改動生命週期(`README.md:138-151`)。

所以協作不是靠 API,而是**「共讀契約 + 共讀寫檔案 + 人工升級關卡」**這三件事扣在一起。要調節「答案給誰看、含哪些切片、多深」的旋鈕就是 **Lens × Views × Detail**,由 skill 依「手動指定 → 當前目標 → session 證據 → 私人 profile → host memory(弱訊號)→ 範疇預設」的順序挑選(`skills/understand/SKILL.md:24`)。

## 一個容易誤會的地方

你可能會以為「那兩支 Python 就是這個工具的本體、這是個 CLI」。**其實相反**:`README.md:5` 明講介面是那 9 個 skill,scripts 只是內部實作細節、明確「不是給 end-user 的 CLI」。真正的邏輯活在 Markdown skill 裡、由 agent 執行;Python 只負責建骨架與驗證這種機械工作。這是理解這個 repo 最關鍵的一次視角轉換 —— 它是「寫給 LLM 執行的 prompt 程式」,不是傳統應用程式。

---

**Sources and gaps**
- 完整讀過:`README.md`、三個 manifest(`.claude-plugin/plugin.json`+`marketplace.json`、`.codex-plugin/plugin.json`)、`references/methodology.md`、`references/artifact-contract.md`、`references/writing-profile.md`、`references/repository-workflow.md`、`references/learning-workflow.md`、`scripts/scaffold_workspace.py`、`scripts/validate_workspace.py`、`skills/understand/SKILL.md`、`skills/build/SKILL.md`、`skills/build/agents/openai.yaml`、`tests/test_plugin_contract.py`。
- 未逐字讀:其餘 7 支 `SKILL.md`(change/review/doctor/sync/learn/practice/quiz)—— 它們的職責是用 `README.md:99-113` 的表格與 `tests/test_plugin_contract.py:131-147` 的契約斷言交叉佐證的,可信但非逐行;要深入任一支我可以再展開。也未讀 `tests/test_workspace_scripts.py` 與 `tests/behavior_cases.json` 的細節、`docs/` 內文。
- 本 workspace 尚無 canonical `mental/` 模型,以上是我直接讀 `target-mental` 原始檔案得出的,不是既有心智模型。

Context:engineer lens · anchor,map,mechanism,scenario,evidence · standard —— 依你「接手 repo、想快速理解整體架構與協作」的當前目標,加上 repository 範疇預設而選定。想拉高到純架構取捨可用 `lens=architect`、想看產品面用 `lens=pm`;想深入某支 skill 就說,我會用 `detail=deep` 展開。