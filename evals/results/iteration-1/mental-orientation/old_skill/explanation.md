I now have enough evidence to answer. This repo is the **`mental` toolkit itself** — and notably, this very `/mental:understand` run is a live example of one of its own skills. Here's the model, built read-only from the source.

---

## Context

- **Lens**: `engineer` · **Views**: `anchor, map, mechanism, scenario, evidence` · **Detail**: `standard`
- **選擇依據**：這是「剛接手 repo、想理解整體架構」的定向問題，依 methodology 的 repository 預設用 `engineer`;你問的兩件事分別對應 **map**(各部分做什麼) 與 **mechanism/scenario**(彼此怎麼協作),再加一個精簡 **anchor** 幫你入門。若你想強調邊界/取捨/為何是這個形狀,改用 `lens=architect` 即可。
- **重要前提**:此 workspace **沒有 canonical `mental/` 模型**(我已確認結構)。所以以下整體架構是我**從原始碼與 README `[inferred]` 綜合**出來的,不是任何人 `[agreed]` 的模型。要把它固化成團隊可共享、可被驗證的模型,請用 `/mental:build`(Codex 用 `$mental:build`);`understand` 本身唯讀,不會建立任何檔案。

---

## Anchor(這是什麼)

`[observed README.md:3-6]` `mental` 是一個 **agent-native plugin**(給 Claude Code 與 Codex 兩個 host 用),**不是** CLI、也不是服務。它的**整個對外介面就是 9 個 skills**;bundled 的 Python 腳本是「skill 的私有實作 helper」,不是給人用的指令列工具。

它的目的:把一個 repo 或一份學習素材,變成**可驗證、有證據連結的心智模型**。方法核心是 **Lens × Views × Detail** `[observed README.md:81-87]`,配上一條貫穿全系統的鐵律 —— **證據真理與人類同意的模型要分開**,且**寫入前要人類批准**:產物先是 `draft`,人類在 gate 確認後才 `canonical`。

---

## Map(各部分是什麼、邊界在哪)

repo 可分成 **7 個群組**,由「介面層 → 共享規則 → 私有實作 → 產物」由外而內堆疊:

| 部分 | 位置 | 職責 |
|---|---|---|
| **1. Plugin 包裝** | `.claude-plugin/`, `.codex-plugin/` | 對兩個 host 宣告「這是一個 **skills-only** 外掛」,都指向 `./skills/`;Codex 版多帶 UI 文案。`.claude-plugin/marketplace.json` 讓 repo 自身即市集。 |
| **2. Skills(介面層)** | `skills/<name>/SKILL.md` ×9 | 唯一入口:`understand / build / sync / doctor / change / review / learn / practice / quiz`。每個 SKILL.md 很**薄**(20–44 行),是「指令與契約」,不是實作。每個 skill 另附 `agents/openai.yaml` 作 Codex 端 UI 綁定。 |
| **3. References(共享方法論)** | `references/` ×5 | 系統的「大腦」:`methodology`(Lens×Views×Detail、三種真理、選擇優先序)、`artifact-contract`(產物佈局/frontmatter/provenance 標籤/promotion gate)、`writing-profile`(STE-inspired 寫作規則)、`repository-workflow`、`learning-workflow`。**所有 skill 開頭都來讀這些。** |
| **4. Scripts(私有實作)** | `scripts/` ×2 | `scaffold_workspace.py`:非破壞性建立 workspace 骨架(build 用);`validate_workspace.py`:零依賴驗證 frontmatter/id/來源/連結/隱私(doctor、sync 用)。 |
| **5. Assets(模板)** | `assets/templates/*.md` + 2 個 private 模板 | scaffold 用 `{{KEY}}` 佔位替換來渲染出各種 artifact 初稿。 |
| **6. 產物(資料層,不在本 repo)** | 目標 repo 的 `mental/` 與 `.mental/` | 共享模型放 `mental/`(index、sources、glossary、model/map、concepts、scenarios、contracts、decisions、changes、lenses…);個人狀態放 **gitignored** 的 `.mental/`(profile、mastery.json、sessions)。 |
| **7. Docs + Tests** | `docs/`, `tests/` | 設計背景與 STE100 政策(含 zh-TW);測試把 README/SKILL 的承諾**編碼成斷言**,當契約守門員。 |

**關鍵邊界** `[observed]`:
- 介面 = skills;scripts 是「私有實作細節,不是 end-user CLI」`[README.md:5-6, 223]`。
- **本 repo 不含產物 `mental/`** —— 產物是在**使用者的目標 repo** 裡被建立的。這也是為什麼這次 `understand` 只能從原始碼推斷。
- 讀寫邊界分明:`understand/doctor/review/change` 預設唯讀;`build/sync` 只寫 draft;學習類只在有 learner evidence 後才寫 private state `[observed README.md:99-109]`。

---

## Mechanism(彼此怎麼協作)

協作的骨幹是 **「薄 skill + 厚共享 references + 人類批准 gate」**。因果鏈:

1. **host → skill**:Claude Code/Codex 讀 `plugin.json` → 載入 `skills/` → 你打 `/mental:<skill>`(或 `$…`)→ host 把該 `SKILL.md` 當指令注入 agent。`[observed plugin.json, README.md:31-45]`
2. **skill → references**:每個 SKILL.md 第一步都是「resolve references 相對於自己」,去讀 methodology / artifact-contract / writing-profile(+ 對應的 repository/learning-workflow)。`[observed skills/build/SKILL.md:12, skills/understand/SKILL.md:20]` **→ 這就是設計精髓:9 個薄 skill 共用同一套厚規則,行為才會一致。**
3. **build → scripts → assets**:要建骨架時,build 呼叫 `scaffold_workspace.py`,它用 `assets/templates` 渲染出 draft 的 `mental/` 與 private `.mental/`。`[observed skills/build/SKILL.md:14-18, scaffold_workspace.py:36-94]`
4. **doctor/sync → scripts**:用 `validate_workspace.py` 驗證產物的結構、id 唯一性、來源存在、連結不壞、`.mental` 有正確 gitignore、mastery.json 形狀。`[observed validate_workspace.py:110-239]`
5. **產物之間靠三樣東西串起來** `[observed artifact-contract.md:62-110]`:
   - **frontmatter**(`id/kind/status/sources/prerequisites`)給每個 artifact 身分與依賴;
   - **provenance 標籤**(`[observed]/[inferred]/[agreed]/[conflict]`)保住「證據 vs 同意」的分野;
   - **promotion gate**:build 產 draft → 人類批准 → 才升 `canonical`、把接受的宣稱標 `[agreed]`。
6. **tests = 契約守門員**:把承諾編碼成斷言 —— 例如「恰好這 9 個 skill」「`understand` 必含 `Never edit`」「`change` 必含 intent/decision/plan-interpretation」「兩個 manifest 不得有 mcpServers/apps/hooks」。`[observed test_plugin_contract.py:36-147]` 這防止**文件與行為漂移**。

**整體生命週期(vibe coding)** `[observed README.md:130-151]`:
`build → understand → change →(人類決定)→ host Plan Mode → implementation → review → quiz → sync`

---

## Scenario(一次具體走查 —— 正好包含「現在」)

情境:你剛進這個陌生 repo。

1. `/mental:build …` → build 讀 references,發現沒有 `mental/`,跑 `scaffold_workspace.py` 建 draft 骨架,登記 sources,寫 `model/map.md` 與少量 concepts,全部 `status: draft` 並標 `[observed]/[inferred]`,最後**停在 promotion gate 等你決定**。
2. 你接受其中幾個 → 下一輪 build 把它們升 `canonical`,把你接受的因果宣稱改標 `[agreed]`。
3. `/mental:understand …` → understand 讀你剛接受的 `mental/` 模型,依選定 Lens/Views/Detail 回答,**唯讀**。
   → **這就是你現在這一步。** 但因為此 repo 還沒有 `mental/`,understand 只能退回「從原始碼推斷」—— 所以本次回答全是 `[inferred]`,而非 `[agreed]`。
4. 你改了程式 → `/mental:review` 先重建 `Before → After`,再拿它跟 `[agreed]` 模型對照稽核。

---

## Boundary or failure

- **無 canonical 模型**:整份架構理解是 `[inferred]`。README 是作者敘述(可信但屬聲明);程式碼/測試才是**實作真理**。兩者若衝突,`mental` 的規矩是保留為 `[conflict]`、不得靜默抹平。
- **別把 scripts 當公開 CLI**:它們是 skill 的內部 helper。
- **要固化這份理解**:若你想讓它變成團隊共享、可被 `doctor` 驗證、可被 `review`/`sync` 引用的 canonical 模型,下一步用 `/mental:build`。我(understand)不會、也不應建立任何檔案。

---

## Evidence and gaps

**Evidence(可點開核對)**
- 介面/包裝:`README.md:3-6,97-109` · `.claude-plugin/plugin.json` · `.codex-plugin/plugin.json:11-25` · `.claude-plugin/marketplace.json`
- 薄 skill + 厚 references:`skills/build/SKILL.md:12` · `skills/understand/SKILL.md:20` · `references/methodology.md`
- 私有腳本:`scripts/scaffold_workspace.py:1,36-94` · `scripts/validate_workspace.py:1,110-239`
- 產物契約:`references/artifact-contract.md:6-25,62-110` · `README.md:153-176`
- 讀寫邊界 + 契約守門:`tests/test_plugin_contract.py:36-147`(尤其 `:101-109` 鎖唯讀措辭)

**Gaps / 不確定**
- 我**只逐字讀了 9 個 SKILL 中的 2 個**(`understand`、`build`)。其餘 7 個(sync/doctor/change/review/learn/practice/quiz)我目前只依 README 摘要 + 契約測試的斷言推斷;要它們的精確行為需再讀那些 `SKILL.md`。**要我補讀哪幾個?**
- 未讀:`test_workspace_scripts.py` 內文、`behavior_cases.json` 內容、`docs/` 全文、各 `assets/templates` 全文。
- **無 git 歷史**(環境顯示 not a git repo),故無演進/決策時序證據。

要我(a)把某幾個未讀 skill 補齊成完整的 mechanism,或(b)改用 `architect` lens 深談邊界與取捨,或(c)直接走 `/mental:build` 把這份理解固化成 draft 模型 —— 你挑一個方向即可。