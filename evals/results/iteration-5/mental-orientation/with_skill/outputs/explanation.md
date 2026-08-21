這個 repo 就是 `mental` 這個外掛本身——一個給 **Claude Code 與 Codex** 用的 agent-native 外掛,對外只暴露 **9 個 skill**,用來為「別的目標程式庫」或「學習教材」建立、解釋、評測、維護「可驗證的心智模型」。它幾乎沒有 runtime 程式碼:真正的「邏輯」是一批 Markdown 指令檔(skills + 共用 references),由 LLM agent 逐步照著執行;`scripts/` 裡那兩支 Python 只是被 skill 呼叫的私有輔助工具。換句話說,**agent 本身就是 runtime**,這個 repo 交付的是「操控 agent 的說明書 + 一套資料契約」,而不是一個會自己跑起來的服務(`README.md:3-5`)。

## 組成的幾個部分,各自負責什麼

- **`skills/` — 對外介面(9 個 skill)。** 每個 skill 是一個資料夾,含 `SKILL.md`(帶 `name`/`description` frontmatter 的工作流程指令)加一個 `agents/openai.yaml`(Codex 端的介面文字)。host 會把 `SKILL.md` 變成 `/mental:understand`(Claude)或 `$mental:understand`(Codex)。9 個 skill 分兩個家族:
  - *程式庫/變更家族*:`build`(建草稿模型)、`understand`(解釋,唯讀)、`change`(在動手前講清楚選項與影響)、`review`(先說明實際 diff 再稽核)、`sync`(source→model 的差異提案)、`doctor`(稽核結構/證據/隱私)。
  - *學習家族*:`learn`(診斷 2–5 個知識缺口再教)、`practice`(一次修一個弱關係)、`quiz`(10–20 題的有界測驗)。`build`/`understand` 兩邊共用(`README.md:97-113`)。

- **`references/` — 共用「憲法」。** 五份 Markdown,是所有 skill 共享的規則來源:`methodology.md`(核心方法 Lens×Views×Detail、三種真理、解釋該長什麼樣)、`artifact-contract.md`(產物的目錄結構、frontmatter schema、來源標籤、升級關卡)、`writing-profile.md`(STE 風格的寫作規則)、外加 `repository-workflow.md` 與 `learning-workflow.md` 兩個模式專用流程。**關鍵:每個 `SKILL.md` 的第 1 步都是「先讀這幾份 references」**(見 `skills/understand/SKILL.md:20`、`skills/build/SKILL.md:12`)——所以共同行為集中在這裡,skill 本身很薄。

- **資料契約(產物模型)。** skill 不只是講話,它們讀寫「目標 repo」裡的兩個目錄:`mental/`(共用、git 追蹤的心智模型:`index.md`、`model/map.md`、`concepts/`、`scenarios/`…)與 `.mental/`(個人、gitignore 掉的學習狀態:`profile.md`、`mastery.json`)。這是 skill 之間傳遞的「共同狀態」。核心不變量是 **provenance 四標籤**(`[observed]`/`[inferred]`/`[agreed]`/`[conflict]`)與 **草稿→canonical 的升級關卡**:agent 可以寫草稿,但把「推論」升級成「共識」一定要人類拍板(`references/artifact-contract.md:90-110`)。

- **`scripts/` — 契約的機械化執行者。** 兩支零相依 Python:`scaffold_workspace.py`(`build` 呼叫它,依 `assets/templates/` 非破壞性地長出 `mental/` 骨架)與 `validate_workspace.py`(`doctor`/`sync` 呼叫它,檢查 frontmatter、ID 唯一性、壞連結、來源引用、`.mental/.gitignore` 隱私、`mastery.json` 形狀)。它們把 `artifact-contract.md` 的規則變成可執行檢查,**不是給使用者的 CLI**(`scripts/validate_workspace.py:1`)。

- **`assets/templates/` — 骨架範本。** scaffold 會做 `{{TODAY}}` 這類佔位符替換,產出 index/map/sources/glossary/concept/scenario/lens 及私有 profile/mastery 範本。

- **`.claude-plugin/` 與 `.codex-plugin/` — 雙 host 包裝。** 同一個 `skills/` 目錄,配兩份 `plugin.json`(各自 host 一份)加一份 `marketplace.json`(讓這個 repo 自己就是一個 Claude marketplace)。這是「一套原始碼同時服務兩個 host」的接點。

- **`docs/` / `tests/` / `evals/`——設計與品質。** `docs/` 放設計背景與 STE100 寫作政策的決策紀錄;`tests/` 有契約測試(斷言兩份 manifest 版本/skill 集一致)、腳本測試、以及 `fixtures/` 裡的範例 `mental/` 工作區;`evals/`(只在 git worktree、不在這份 target 副本裡)是一套實驗檯,拿「有 skill vs 沒 skill」的解釋去給 grader 打分,用來證明 skill 的價值。

## 它們怎麼協作

有四條「接線」把這些部分綁在一起:

1. **共享行為靠 references。** 9 個 skill 都在第 1 步讀同一批 references——所以改 `methodology.md` 一個檔,9 個 skill 的行為同時改變。這是最高槓桿、也是最大 blast radius 的位置。
2. **共享狀態靠 `mental/` 產物。** `build` 產出草稿模型,`understand`/`change`/`review`/`quiz` 讀它,`sync`/`doctor` 維護它。skill 之間不直接呼叫彼此,而是透過這批檔案接力。
3. **共享生命週期。** README 的主流程是一個迴圈:`build → understand → change →(人類決策)→ host Plan Mode → 實作 → review → quiz → sync`(`README.md:132-151`)。每個 skill 是這個迴圈的一個階段。
4. **共享契約與包裝靠 scripts + 雙 manifest。** 產物形狀由 validator 把關,對外身分由兩份 plugin.json + marketplace.json 對齊。

## 一個具體流程(就是你現在這一次)

你剛剛打 `/mental:understand` 要我解釋架構,底層發生的事正好走了一遍上面的接線:host 載入 `skills/understand/SKILL.md` → 它第 1 步叫我讀那三份 references(拿到 Lens×Views×Detail 規則)→ 第 3 步要我找 workspace 根、讀 `mental/index.md`;但**這個 workspace 目前沒有 canonical 的 `mental/` 模型**,所以照 `SKILL.md:23` 的指示,我改成直接讀真實原始碼來回答,並在此提一次:若想把這份理解沉澱成可維護、可驗證的模型,可用 `$build` 建立草稿(我不會自動建檔)。最後這類回答一定附上「用了什麼 Lens/Views/Detail」的說明,方便你調整——也就是文末那行。

## 接手後最該記住的槓桿與邊界

- **要新增一個 skill**:加 `skills/<name>/SKILL.md`(+ `agents/openai.yaml`)、把名字加進 `tests/test_plugin_contract.py` 的 `SKILL_NAMES`、必要時同步兩份 manifest。host 顯示的是 frontmatter 的 `name`/`description`。
- **版本要一起動**:契約測試斷言兩份 `plugin.json` 的 `version` 都是 `0.2.0`(`tests/test_plugin_contract.py:41`),升版要同步 marketplace。
- **改資料 schema 就要改 validator**:產物欄位/種類的規則同時寫在 `artifact-contract.md`(給 agent 讀)與 `validate_workspace.py`(機械檢查),兩邊要一致。
- **最容易踩的誤解**:別把這當成「一個 Python 工具、腳本就是本體」。腳本只是約 380 行的可選輔助;真正的行為活在 Markdown 指令裡,由模型執行,沒有獨立 runtime。另一個誤解是「模型應該在這個 repo 裡」——不是,`mental/` 產物住在你用這個外掛去理解的**那個目標 repo**;這裡出的是機器,不是模型(`tests/fixtures/` 裡的 `mental/` 只是測試用範例)。

---

**Sources and gaps**
- 讀過:`README.md`、`.claude-plugin/{plugin,marketplace}.json`、`.codex-plugin/plugin.json`、`references/{methodology,artifact-contract,writing-profile}.md`、`skills/{understand,build}/SKILL.md`、`skills/understand/agents/openai.yaml`、`scripts/{scaffold,validate}_workspace.py`、`tests/test_plugin_contract.py`,並掃過完整檔案樹與 `evals/` 清單。
- 未逐字讀:`change/review/sync/doctor/learn/practice/quiz` 七個 `SKILL.md`(責任取自 `README.md` 的對照表,尚未核對其內文細節)、`references/{repository,learning}-workflow.md`、`docs/`、`evals/` 內的評測邏輯。
- 本 workspace **沒有** canonical `mental/` 模型;以上為讀真實檔案後的 `[inferred]` 架構理解,尚未經人類確認為 `[agreed]`。git 歷史因需授權未取得。

*Context:* architect lens · map,mechanism,scenario · standard —— 依你「理解整體架構、各部分職責與如何協作」的明確目標選定(而非 repository 預設的 engineer);想更深入某個 skill 或改用其他視角,直接說,或加 `lens= views= detail=` 即可。