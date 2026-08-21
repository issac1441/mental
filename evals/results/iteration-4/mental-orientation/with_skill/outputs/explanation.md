這是 `mental` 外掛本身的原始碼。我已讀完關鍵結構檔案,以下是它的整體架構。

---

**`mental` 是一個給 Claude Code 與 Codex 用的「agent-native」外掛,本身不是 CLI、也不是服務。** 它的用途是幫人替某個「目標 repo」或一批學習教材,建立、解釋、測驗、維護一份**有證據連結的心智模型(mental model)**。整個對外介面就是**九個 skill(技能)**——每個 skill 是一份 Markdown 指令檔,由 agent 讀進去照著執行;repo 裡的 Python 腳本只是這些 skill 私下呼叫的輔助工具,不是給使用者的 CLI(`README.md:5`、`scripts/validate_workspace.py:2` 都標明 internal)。

先講最容易誤會、也最關鍵的一點:**這個 repo 是「工具」,它產出的心智模型(`mental/` 資料夾)並不在這個 repo 裡,而是長在你拿去分析的那個目標 repo 裡。** 本 repo 唯一出現 `mental/` 樹的地方是 `tests/fixtures/` 底下的範例。你現在就在體驗它——你剛用 `/mental:understand` 呼叫的,正是九個 skill 之一。

## 架構分成七塊

| 位置 | 角色 | 做什麼 |
| --- | --- | --- |
| `skills/*/SKILL.md`(9 個) | **介面層(orchestration)** | 每個 skill 是一段給 agent 的「程式」。這就是產品本體。 |
| `references/*.md`(5 份) | **共用規則層(policy)** | 真正的方法論。所有 skill 第一步都來讀這裡。 |
| `scripts/*.py`(2 支) | **機械輔助層(mechanics)** | 無相依、determinstic 的雜活:建骨架、驗結構。 |
| `assets/templates/*` | **樣板** | scaffold 腳本蓋出來的種子檔。 |
| `mental/` 與 `.mental/` | **資料模型(產出物)** | 不在本 repo;在目標 repo 裡產生。 |
| `.claude-plugin/`、`.codex-plugin/` | **打包/發佈** | 讓兩個 host 找得到這些 skill。 |
| `tests/` | **契約測試(glue)** | 強制上面幾塊彼此保持一致。 |

(另有 `README.md`/`README.zh-TW.md` 與 `docs/` 設計說明,屬文件層。)

## 各部分細節

**1. skills/ — 九個 skill,就是全部功能。** 分兩條工作線(`README.md:97`):

- **repo 線**:`build`(建草稿模型)→ `understand`(解釋,你現在用的)→ `change`(在動手前比較選項/解讀計畫)→ `review`(改完後先講「實際改了什麼」再稽核)→ `sync`(原始碼漂移後同步模型)→ `doctor`(稽核結構與隱私)。
- **學習線**:`build`(從教材建模型)→ `learn`(先診斷 2–5 個知識缺口再教)→ `practice`(一次一題,逐步修最弱的關聯)→ `quiz`(10–20 題的完整測驗)。

每個 skill 資料夾還帶一支 `agents/openai.yaml`,只放 Codex 需要的介面 metadata(`skills/understand/agents/openai.yaml`)——這讓同一份 SKILL.md 在 Claude 與 Codex 兩個 host 上都能用。

**2. references/ — 五份共用規則,是真正的「大腦」。** skill 檔案本身很薄,把方法論全外包給這裡:

- `methodology.md`:核心方法 **Lens × Views × Detail**(視角 × 內容切片 × 深度)、三種真相(observed/inferred/agreed/conflict)、解釋的寫法。
- `artifact-contract.md`:`mental/` 的檔案格式、frontmatter 欄位、隱私邊界。
- `writing-profile.md`:寫作風格規範(STE-inspired)。
- `repository-workflow.md` 與 `learning-workflow.md`:兩條工作線各自的細節流程。

**3. scripts/ — 兩支 Python,刻意「笨但可靠」。**

- `scaffold_workspace.py`:在目標 repo 蓋出 `mental/` + `.mental/` 骨架。它**不覆蓋既有檔案**(`write_new` 見既有就跳過,`scripts/scaffold_workspace.py:22`),並依 `--mode` 決定蓋哪些資料夾——repository 模式多出 `contracts/decisions/changes/`,learning 模式多出 `learning/misconceptions/exercises/`(`scripts/scaffold_workspace.py:59`)。內容來自 `assets/templates/`,用 `{{KEY}}` 字串替換填入(`scripts/scaffold_workspace.py:15`)。
- `validate_workspace.py`:**只驗結構,不判斷語意**。檢查 frontmatter 必填欄位、`kind`/`status` 合法值、`kind: lens` 必須放在 `lenses/`、canonical 檔案必須有 sources、連結不能斷、`.mental/.gitignore` 必須是 `*` + `!.gitignore`(`scripts/validate_workspace.py:110` 起)。它無相依套件,`doctor` 與 `sync` 會呼叫它。

**4. tests/ — 把上面幾塊「焊」在一起的契約。** 這是理解協作的關鍵。測試強制:skill 集合剛好是這九個、每個 SKILL.md 只能有 `name`+`description` 兩個欄位、每個 skill 都必須載入 `writing-profile.md`、三份 manifest 版本都是 `0.2.0`、manifest 不准出現 `mcpServers`/`hooks`/`apps`(確保它是「純 skill」外掛)。更妙的是 `behavior_cases.json`:它替每個 skill 列出「必須出現的關鍵語句」,測試會斷言這些字串真的寫在對應 SKILL.md 裡(`tests/test_plugin_contract.py:93`)——例如 `understand` 必須含 "strictly read-only"、`build` 必須含 "promotion gate"。**規格被寫成可執行的測試,skill 的行為承諾不會偷偷跑掉。**

## 它們怎麼協作

**核心模式:skill 負責編排,references 負責規則,scripts 負責機械動作。** 每個 skill 的第一步都是「讀那三份 reference」(`skills/build/SKILL.md:12`、`skills/understand/SKILL.md:20`)。所以 skill 是很薄的入口,真正的判斷邏輯集中在共用 references——這也是為什麼九個 skill 行為能保持一致。

貫穿全系統的三條規則,決定了資料怎麼流動:

- **讀寫邊界**:只有 `build` 與 `sync` 會寫檔,而且**只寫草稿(draft)**;`understand`/`review`/`doctor`/`change` 預設唯讀(測試會檢查這些 SKILL.md 真的寫了 "Never edit" 之類的字,`tests/test_plugin_contract.py:101`)。
- **升級閘門(promotion gate)**:任何草稿要變成 `canonical`(正規、可信),一定要停下來讓**人**確認(`skills/build/SKILL.md:24`、`references/artifact-contract.md:102`)。agent 不能自己把「推測」升級成「已同意」。
- **兩種真相 + 隱私分流**:程式碼/測試是「材料真相」,`mental/` 裡人類同意過的模型是「概念真相」,兩者衝突時要標 `[conflict]` 保留、不准偷偷抹平。共享模型放 git 追蹤的 `mental/`,個人學習狀態(profile、mastery、答題紀錄)放**被 gitignore 的** `.mental/`(`scripts/scaffold_workspace.py:81`)。

整體生命週期(`README.md:138` 的流程圖):`build → understand → change →(人做決定)→ Plan Mode → 實作 → review → quiz → sync`。注意 `change` 排在 host 的 Plan Mode **之前**:`change` 決定「該變成什麼」,Plan Mode 才決定「怎麼實作」(`references/repository-workflow.md:18`)。

## 一個具體情境:跑 `/mental:build`

假設你在新的目標 repo 裡執行 `build`,協作鏈是這樣:

1. skill 讀完三份 reference,建立方法論脈絡;
2. 若沒有 `mental/`,它呼叫 `scaffold_workspace.py`,把 `assets/templates/` 的樣板蓋成 `mental/` + `.mental/` 骨架;
3. agent 讀你的真實程式碼,填 `model/map.md`,每個宣稱標上 `[observed]`(有原始碼佐證)或 `[inferred]`(推測);
4. 呼叫 `validate_workspace.py` 確認結構沒壞;
5. **停在升級閘門**,把邊界、關聯、一個成功情境、一個失敗情境、已知缺口攤給你看,等你逐一決定要不要升成 canonical。

一次流程就同時動用了樣板、兩支腳本、references 規則、`mental/` 產出物,以及**「人來拍板」這個硬性關卡**。

## 想改動時的槓桿與邊界

要預測「改某處會怎樣」,盯這幾個槓桿:

- **`--mode`(repository/learning/hybrid)** 決定 scaffold 蓋哪些資料夾與樣板。
- **`status`(draft/canonical/stale)** 是信任等級的開關;canonical 是那道人為閘門。
- **claim 標籤(`[observed]`/`[inferred]`/`[agreed]`/`[conflict]`)** 是真相追蹤機制。
- 若要**新增一個 skill**:得同時加 `skills/<name>/SKILL.md` + `agents/openai.yaml`、在 `behavior_cases.json` 補一筆、並讓 `SKILL_NAMES` 對得上——否則 `tests/test_plugin_contract.py:64` 會紅。這是刻意設計的護欄。

三個容易踩的誤解,先幫你擋掉:

- **別把 `mental/` 當成本 repo 的一部分。** 它是產出物,在目標 repo 裡;這裡只有 `tests/fixtures/` 的範例。
- **別把 `scripts/` 當成使用者 CLI。** 它們是 skill 的私有實作細節(`README.md:223`),你不會直接手跑(開發驗證時例外)。
- **別以為 repo 裡有「執行邏輯」在跑。** 除了兩支小 Python 與測試,幾乎全是 Markdown 指令。真正的「智慧」發生在——coding agent 讀這些 prose 並執行它們。這個 repo 的產品,本質上是**寫給 agent 讀的一套規範**。

---

**Sources and gaps**
- 介面與版本:`.claude-plugin/plugin.json`、`.codex-plugin/plugin.json`、`.claude-plugin/marketplace.json`(三者 version 0.2.0、skills 指向 `./skills/`)。
- skill 集合與職責:`README.md:97`(技能表)、`tests/test_plugin_contract.py:10`(九個 skill 白名單)、`tests/behavior_cases.json`(各 skill 行為契約)。
- 規則層:`references/methodology.md`、`artifact-contract.md`、`writing-profile.md`、`repository-workflow.md`、`learning-workflow.md`。
- 腳本行為:`scripts/scaffold_workspace.py`(非破壞式、依 mode 建目錄)、`scripts/validate_workspace.py`(結構驗證規則)。
- 唯讀/寫入邊界與升級閘門:`tests/test_plugin_contract.py:101`、`skills/build/SKILL.md:22`。
- 我讀完整的是 `understand`、`build` 兩個 SKILL.md;其餘七個 skill 的細節是由 README 技能表、`behavior_cases.json` 與測試推得,**未逐檔展開**。若要我深入某個特定 skill(例如 `review` 或 `sync` 的實際章節結構),再指定即可。
- **目前這個 workspace 還沒有 `mental/` 正規模型**,以上是我直接讀原始碼與文件得到的。若想把它固化成可複用、能被其他 skill 引用的模型,可以用 `$build`(或 `/mental:build`)建草稿——但那會寫檔,不在本次唯讀範圍內。

*Context: engineer 視角 · map,mechanism,scenario · standard —— 依你「剛接手 repo、要理解整體架構與協作」的當前目標推得;想更深、換視角或聚焦某個 skill,直接說,或用 `lens= views= detail=` 調整。*