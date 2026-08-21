我已讀完 SKILL.md、三份核心 reference，並實際查了 repo 的 manifest、兩支 Python、9 個 skill 與契約測試。以下是直接答案。

---

`mental` 是一個給 LLM agent 用的 **Claude Code / Codex 外掛（plugin）**,它的「產品」是 `skills/` 底下**九個 `SKILL.md`——用自然語言寫成的 agent 工作流程,而不是可執行程式**。這九個 skill 幫使用者對「**別的** repo 或學習教材」建立、解釋、決策、測驗、維護一份有證據連結的心智模型。真正會被電腦執行的程式只有 `scripts/` 裡兩支 Python(建骨架、驗檔案);其餘全是給 agent 讀的 Markdown 規格。各部分靠**磁碟上的 `mental/` 檔案**與**共享的 `references/` 規格**協作,skill 之間**不互相呼叫**。

## 先破除最容易踩的誤會

你剛接手時,看到 `scripts/*.py` + `tests/` 很容易以為「這是一支 Python CLI 工具」。**不是。** README 開宗明義:介面是九個 skill,Python 只是 skill 的**私有實作 helper**(`README.md:5`、`skills/build/SKILL.md:18` 稱其為 "internal helper")。同樣地,`SKILL.md` 本身很**薄**(20–44 行),真正的共享邏輯在 `references/`——每個 skill 的工作流第一步都是「去讀 references」。

還有一層:**這個 repo 不產生任何 `mental/` 模型檔**。模型是在你「想理解的那個目標 repo」裡才被建立;這裡只放「怎麼建立它們」的指令與工具。

## 組成的七個部分

**1. 封裝／進入層** — `.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`、`.codex-plugin/plugin.json`,加上每個 skill 的 `agents/openai.yaml`。作用是讓**同一個 `skills/` 資料夾**在兩個 host 都能被發現:Claude Code 用 `/mental:build`,Codex 用 `$mental:build`。兩個 manifest 都指向 `"skills": "./skills/"`,且刻意不含 `mcpServers`/`apps`/`hooks`(由 `tests/test_plugin_contract.py:44-46` 釘死)。`marketplace.json` 讓這個 repo 本身就是一個 marketplace,免另開倉庫。

**2. 九個 skill(介面與行為)** — 位於 `skills/*/SKILL.md`,每個是 frontmatter(`name`、`description`)+ 一段 Workflow。分兩群:
- **理解／維護 repo**:`build`(唯一會寫草稿)、`understand`(唯讀解釋)、`change`(唯讀決策)、`review`(唯讀稽核 diff)、`sync`(偵測漂移→草稿 delta)、`doctor`(稽核/驗證)
- **從教材學習**:`learn`、`practice`、`quiz`

README 的表格(`README.md:99-113`)是這九個角色最快的索引。

**3. 共享方法(`references/*.md`)——一致性的來源** — 這是「共享函式庫」。`methodology.md`(核心方法 Lens × Views × Detail、三種真實 observed/inferred/agreed、解釋的寫法)、`artifact-contract.md`(檔案佈局、frontmatter schema、provenance 標籤、promotion gate)、`writing-profile.md`(STE-inspired 寫作規範)、以及 `repository-workflow.md` / `learning-workflow.md`(兩種模式各自的程序)。九個薄 skill 之所以行為一致,就是因為它們**載入同一份規格**(例如 `skills/understand/SKILL.md:20`、`skills/build/SKILL.md:12`)。

**4. 可執行 helper(`scripts/*.py`)——唯一真的會跑的碼** — 兩支、零相依、純標準庫:
- `scaffold_workspace.py`:`build` 呼叫它,**非破壞地**建出 `mental/` + `.mental/` 骨架(`skills/build/SKILL.md:14-18`);已存在的檔案只會 `kept:` 不覆寫(`scripts/scaffold_workspace.py:22-28`)。
- `validate_workspace.py`:`doctor` 與 `sync` 呼叫它(`skills/doctor/SKILL.md:13`、`skills/sync/SKILL.md:17`),**機械式**檢查 frontmatter、id 唯一性、canonical 一定要有 sources、連結是否斷、以及隱私邊界。

**5. 範本(`assets/templates/*.md`)** — scaffold 的素材。`scaffold_workspace.py:15-19` 讀這些範本、做 `{{KEY}}` 字串替換,產出初始 artifact。

**6. 協作用的共享狀態(`mental/` + `.mental/`)——不在本 repo,在目標 repo** — 這是各 skill 溝通的**唯一媒介**:`mental/` 是共享、進 git、經人同意的模型;`.mental/` 是私人、被 gitignore、放個人學習進度。這條公私分界是核心不變量,由 validator 強制(`.mental/.gitignore` 必須剛好是 `*` 加 `!.gitignore`,見 `scripts/validate_workspace.py:200-206`)。

**7. 測試(`tests/`)——釘住跨檔案契約** — 對新維護者最重要。`test_plugin_contract.py` 斷言:剛好九個 skill、兩個 manifest 版本一致、每個被 SKILL.md 引用的 support 檔都存在、唯讀 skill 都寫明寫入邊界、不得出現舊詞彙 `zoom`/`L0–L4` 等。它測的是「檔案之間是否一致」,而不是 agent 行為。(docs/、README 為雙語設計說明,附帶但非核心。)

## 一次呼叫怎麼流動(以 build → understand 為例)

1. 你在目標 repo 下 `/mental:build …`。host 把 `skills/build/SKILL.md` 當指令餵給 agent。
2. agent 依 workflow **先讀 references**(共享規格),若 `mental/` 不存在就跑 `scaffold_workspace.py` 用範本鋪骨架。
3. agent 把**草稿** artifact 寫進 `mental/`,跑 `validate_workspace.py` 修結構錯,然後**停在 promotion gate 等你點頭**(`skills/build/SKILL.md:23-25`)——未經人確認不會變 canonical。
4. 之後你 `/mental:understand …`,那個 skill **唯讀地讀 `mental/` 裡的 artifact** 來支撐回答;`change`/`review`/`quiz` 也一樣讀同一批檔。

關鍵:**skill 從不直接呼叫彼此**。串接是由「人」(或 README:138-149 那張 workflow 圖)完成的;它們只透過磁碟上的 `mental/`、`.mental/` 檔案與共享 `references/` 交換狀態。這就是「怎麼協作」的答案。

## 你能調的槓桿(改這裡→可預測的後果)

- **要加/刪一個 skill**:光新增 `skills/<x>/` 不夠。`tests/test_plugin_contract.py:10-20` 的 `SKILL_NAMES` 硬編了這九個名字,`tests/behavior_cases.json` 也要對得上(`:93-99`)——三處要一起改,否則測試紅。
- **版本號**:`0.2.0` 必須在兩個 `plugin.json` 與 marketplace 條目**三處一致**(`test_plugin_contract.py:41,61`)。
- **改 artifact schema**:合法的 `kind`/`status`/`view` 同時寫在 `references/artifact-contract.md`(文件)**和** `scripts/validate_workspace.py:14-33`(常數)。這兩份**目前靠手動同步**,測試只抽查 lens 幾個欄位(`:160-168`),不保證整組枚舉對齊——這是真正的漂移風險點。
- **改 skill 的支援檔引用**:任何 `../../{references,scripts,assets}/…` 路徑都得真的存在,且每個 skill 都必須引用 `writing-profile.md`(`test_plugin_contract.py:84-91,149-152`)。

## 會咬人的邊界

- **這不是一般「跑得起來」的軟體。** `python3 -m unittest` 只驗**兩支 Python** + 「skill 文字是否含正確契約字串」;skill 的**實際行為**只有在 agent host 裡才會發生,無法用單元測試驗證。別期待 `tests/` 能抓到 prompt 語意變差。
- **在錯的目錄跑 validator 會說 not found。** `validate_workspace.py:112` 有雙 root 偵測:若你正站在 `mental/` 資料夾裡,它會往上一層找 `.mental/`;否則預期 `<workspace>/mental`。
- 這個工作區**目前沒有 `mental/` canonical 模型**,所以上面全是我直接讀原始碼與規格得到的 `[observed]` 事實,尚未被任何人固化成「已同意」的模型。若你想要一份可長期維護、可 promotion 的模型檔,可執行 `$mental:build`;依 `understand` 的規範我**不會擅自建立任何檔案**。

---

**Sources and gaps**
- 封裝:`.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`、`.codex-plugin/plugin.json`、`skills/understand/agents/openai.yaml`
- 介面:`skills/*/SKILL.md`(完整讀了 understand/build/doctor/sync;其餘 change/review/learn/practice/quiz 依 `README.md:99-113`、`references/repository-workflow.md`、`references/learning-workflow.md` 與 `tests/behavior_cases.json` 契約推得,尚未逐字讀正文——`[inferred]`,可再展開)
- 規格:`references/methodology.md`、`artifact-contract.md`、`writing-profile.md`、`repository-workflow.md`、`learning-workflow.md`
- 程式:`scripts/scaffold_workspace.py`、`scripts/validate_workspace.py`(皆完整讀過)
- 契約:`tests/test_plugin_contract.py`(完整);`tests/test_workspace_scripts.py` 只看了行數,內容未逐一讀——`[inferred]`
- 未讀:`docs/*`、`assets/templates/*` 個別內容、`README.zh-TW.md`。若要我深入某一塊(例如逐一走完九個 skill 的正文,或 validator 的每條規則),說一聲即可。

Context: engineer lens · map,mechanism,scenario,evidence · standard —— 依「新接手者要看整體架構與協作」的當前目標加 repo 預設而選;想更深、換成 architect 視角或縮成 brief,直接說 `lens= views= detail=`。