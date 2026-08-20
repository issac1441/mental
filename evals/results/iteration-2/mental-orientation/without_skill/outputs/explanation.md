讀完了。我把基礎設施、共用契約、方法論、測試，加上子代理回傳的 9 個 skill 逐項細節都彙整好了。以下是這個 repo 的整體架構。

---

## 一句話定位

`mental` 是一個 **agent-native 外掛**（同時給 Claude Code 和 Codex 用），把「幫人建立、解釋、評測、維護對一個 repo 或學習素材的**心智模型**」做成 **9 個 skill**。

最關鍵、也最容易誤會的一點：**這個 repo 幾乎沒有 runtime 程式碼**。它的「產品」是一組 Markdown 規格（給 agent 讀的 prompt spec）+ 一份共用契約 + 兩支 Python 輔助腳本。你接手時要用「讀規格」而不是「讀程式」的心態來看它。README 講得很直接:「The interface is nine skills. The bundled Python scripts are private implementation helpers.」

---

## 分層架構（各部分做什麼）

```
① 封裝/註冊層     .claude-plugin/  .codex-plugin/   ← 讓兩個 host 發現這些 skill
      │
② Skill 層        skills/<name>/SKILL.md            ← 每個 skill 的「行為規格」(真正內容)
      │           skills/<name>/agents/openai.yaml  ← Codex 端的 4 行介面殼
      │
③ 共用契約層      references/*.md                   ← 9 個 skill 全部載入的單一真相來源
      │
④ 工具層          scripts/*.py                      ← scaffold(建骨架) + validate(驗證)
      │           assets/templates/*                ← scaffold 用的樣板
      │
⑤ 產出物(執行期)  mental/(共用,進 git)  .mental/(私人,gitignore)
```

**① 封裝/註冊層** — 三個 JSON manifest 讓外掛被安裝、被發現：
- `.claude-plugin/plugin.json`(Claude)、`.codex-plugin/plugin.json`(Codex，多了 `interface` 區塊)、`.claude-plugin/marketplace.json`(讓 repo 自己當 marketplace，不需另開 repo)。
- 三者都只指向 `./skills/`，**刻意不含** `mcpServers`/`apps`/`hooks`(測試會強制檢查這點)。

**② Skill 層** — 9 個 skill，各是 `skills/<name>/` 下一個目錄：
| Skill | 做什麼 | 預設寫入 |
|---|---|---|
| `build` | 從來源產生**草稿**模型 + 可重用 lens | 寫 `mental/`(全 draft) |
| `understand` | 用選定的 Lens×Views×Detail 解釋 | **唯讀** |
| `sync` | 偵測來源與模型漂移，提 delta | 寫 draft delta |
| `doctor` | 稽核結構/證據/隱私外洩 | 唯讀(除非要求修) |
| `change` | 實作前把「要改什麼」講成模型 delta | 唯讀(除非 `record=true`) |
| `review` | 解釋實際 diff 再對照模型稽核 | **唯讀** |
| `learn` | 先診斷 2–5 題再適性教學 | 寫 `.mental/`(私人) |
| `practice` | 一次修一條最弱的關係 | 寫 `.mental/` |
| `quiz` | 一次出完 10–20 題的有界測驗 | 只把結果寫 `.mental/` |

　　每個 `SKILL.md` 是**規格本體**(含 `name`/`description` frontmatter 供 host 路由)；配套的 `agents/openai.yaml` 只是 Codex 端 4 行的**介面殼**(`display_name`/`short_description`/`default_prompt`)，不重複任何行為邏輯，只用 `$build` 這種形式指回 skill。

**③ 共用契約層 `references/`** — 這是把 9 個 skill 綁成同一套語言的核心。每個 SKILL.md 第一步都載入：
- `methodology.md` — **Lens × Views × Detail** 選擇法、三種真相、變更/學習兩條 workflow。
- `artifact-contract.md` — frontmatter 欄位、`kind`/`status` 列舉、draft→canonical 升級門、`mental/` vs `.mental/` 隱私切分。
- `writing-profile.md` — STE-inspired 的三種寫作 profile(程序/技術描述/學習)。
- 再依模式加載 `repository-workflow.md` 或 `learning-workflow.md`。

**④ 工具層 `scripts/`** — 唯二的可執行碼，零相依：
- `scaffold_workspace.py` — 用 `assets/templates/` 建工作區骨架，**非破壞性**(已存在就跳過)。
- `validate_workspace.py` — 驗證 artifact 契約:frontmatter 必填欄、id 唯一、來源/prerequisite/連結有效、`mastery.json` 形狀、`.mental/.gitignore` 有把私人狀態擋掉。`doctor`/`sync` 會呼叫它。

**⑤ 產出物** — skill 執行後產生的東西，也是隱私設計的重點:
- `mental/` = 共用、進 git、要有來源佐證的模型/lens/exercise。
- `.mental/` = 私人學習狀態(`profile.md`、`mastery.json`、`sessions/`)，被自身的 `.gitignore` 全部擋掉，永不進版控。

---

## 把它們綁在一起的共用詞彙（協作的基礎）

所有 skill 講同一套話，這套話定義在 `references/`，不在各 skill 內重複：

1. **Lens × Views × Detail** — 三個獨立控制軸。Lens=用哪個角色視角(engineer/architect/pm/student…)、Views=五個語意切片(`anchor,map,mechanism,scenario,evidence`)、Detail=密度(`brief/standard/deep`)。有一條共用的**選擇優先序**:手動 > 當前目標 > 本次 session 證據 > `.mental/` 檔案 > host memory(弱訊號) > 預設。
2. **三種真相 / 出處標籤** — `[observed]`(有來源)、`[inferred]`(agent 推論未確認)、`[agreed]`(人類確認)、`[conflict]`(模型與實作打架)。鐵律:**衝突不能為了讓驗證通過就刪掉**。
3. **draft → canonical 升級門** — agent 寫出來的東西一律 `draft`;要變 `canonical` 必須先把邊界/關係/推論/場景/缺口攤給人看、由人明確接受。這是「agent 產出不會意外變成團隊公認真相」的閘門。
4. **`mental/` vs `.mental/` 隱私切分** — 共用模型 vs 私人能力狀態,永不混。`doctor` 會專門稽核有沒有私人資料漏進 `mental/`。

---

## 兩條生命週期（彼此怎麼交接）

- **Bootstrap**:`build` 產草稿 → 升級門 → 人接受 → canonical。其他 skill 都消費 canonical,沒有就建議先 `$build`。
- **改 code 的流程**:`change`(講清要變什麼)→ 人決定 → host **Plan Mode**(講清怎麼做)→ 實作 → `review`(對照實際 diff 稽核)→ 選配 `quiz` → `sync`(把漂移收斂回 canonical)。
- **學習流程**:`learn`(先診斷再教)→ `practice`(適性、每答一題調整下一題) 或 `quiz`(固定考卷、交卷後評)。
- **`doctor`** 是正交的 QA,任何時候都能跑(例如 commit 前查隱私外洩)。

---

## 一個接手時該注意的邊界

這個 repo 用 **「規格即測試」(spec-as-tests)** 的方式維護 —— `tests/test_plugin_contract.py` 不測程式邏輯,而是斷言**規格文字本身**:9 個 skill 剛好存在、frontmatter 只有 `name`/`description`、每個 skill 都載入 writing-profile、唯讀 skill 必須寫明 "Never edit"、`behavior_cases.json` 列的關鍵詞必須出現在對應 SKILL.md 裡、舊詞彙(`zoom`/`L0–L4`)不准出現。

**含意**:你改一句 SKILL.md 的措辭,可能就會弄掉一個契約測試;反之,測試綠燈代表「規格結構」正確,**不代表 agent 行為正確**——`validate_workspace.py` 綠燈也只保證格式,不保證模型語意對(`doctor` 自己就這麼警告)。所以真正的「行為正確性」靠的是人工審規格 + 那份 `docs/design-background.md` 記錄的設計假設(H1–H5),不是 CI。

---

想深入哪一塊我可以再往下帶:比如挑一個 skill 逐行拆 `SKILL.md`、把 `validate_workspace.py` 的驗證規則講細、或畫一張正式的架構/流程圖(可做成可分享的視覺頁面)。