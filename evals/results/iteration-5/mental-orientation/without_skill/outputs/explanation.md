我已經把整個 repo 讀通了。以下用它自己的方法論風格(先給直接答案,再依主題結構展開)幫你建立心智模型。

---

## 先講結論

這**不是一般的應用程式 repo**,而是一個給 Claude Code / Codex 用的**外掛(plugin)**,名字叫 `mental`。它的「執行引擎」其實是 LLM agent 本身——真正的產品是**九個 skill 的指令檔(prompt)**加上一套**共用規範文件**。整個 repo 幾乎沒有傳統意義的程式邏輯:唯二的可執行碼是兩支零依賴的 Python 腳本。所以如果你抱著「找 main、找 API layer」的預期進來,會撲空——這裡的「原始碼」是散文(Markdown)。

它解決的問題:當實作速度超過人重建正確心智模型的速度時,幫人**建立、解釋、測驗、維護「有證據連結、可驗證」的心智模型**——對象可以是一個 repo,也可以是學習教材。

---

## 各部分是什麼

**1. 外掛清單 — 雙宿主入口**
- `.claude-plugin/plugin.json`、`.codex-plugin/plugin.json`:同一套 skill 分別對 Claude Code 與 Codex 宣告。兩者刻意保持一致(name/version/`skills: ./skills/`),Codex 版多一段 `interface` UI 描述。
- `.claude-plugin/marketplace.json`:讓這個 repo **本身就是自己的 marketplace**,所以安裝不需要另開一個 marketplace repo。
- 明確**不含** `mcpServers` / `apps` / `hooks`(測試會擋)——它是純 skill 外掛。

**2. `skills/` — 唯一的對外介面(九個)**
每個 skill 是一個 `SKILL.md`(給 agent 讀的指令)加一個 `agents/openai.yaml`(Codex 的 UI 標籤)。九個依行為分三群:

| 群組 | Skills | 是否寫檔 |
|---|---|---|
| 唯讀解釋/稽核 | `understand`、`review`、`doctor`、`change` | 否(`change` 僅在被要求時寫 draft brief) |
| 建模寫手(僅草稿,需人工批准) | `build`、`sync` | 只寫 `mental/` 的 draft |
| 學習迴圈 | `learn`、`practice`、`quiz` | 只寫私有 `.mental/`,且需有學習者證據後才寫 |

關鍵:**只有 `build` 和 `sync` 會動共用模型,而且永遠只產 draft**;其餘要嘛唯讀,要嘛只碰私有狀態。這是整個系統的安全邊界。

**3. `references/` — 共用規範(single source of truth)**
所有 skill 開頭都去讀這幾份,避免把規則複製進每個 skill:
- `methodology.md`:核心方法 **Lens × Views × Detail**、三種真實、解釋的呈現形狀。
- `artifact-contract.md`:產出物的目錄結構、frontmatter 欄位、provenance 標籤、promotion 閘門。
- `writing-profile.md`:STE-inspired 的寫作風格(注意:只是「啟發」,測試明文禁止宣稱 ASD-STE100 合規)。
- `repository-workflow.md` / `learning-workflow.md`:兩種模式各自的流程。

**4. `scripts/` — 唯二的可執行碼(零依賴 stdlib)**
- `scaffold_workspace.py`:`build` 用它非破壞性地生出 `mental/` + `.mental/` 骨架(套用 `assets/templates/`)。已存在的檔案一律跳過。
- `validate_workspace.py`:`doctor` / `sync` 用它做結構驗證——檢查 frontmatter 必填欄位、`kind`/`status` 列舉值、id 唯一性、source id 與 prerequisite 是否存在、本地連結有沒有斷、`.mental/.gitignore` 是否正確、`mastery.json` 結構。這支腳本等於把 `artifact-contract.md` 變成可執行的檢查器。

**5. `assets/templates/`**:scaffold 用的產出物骨架(`{{TODAY}}` 之類的變數替換)。

**6. 兩棵產出物樹(這是使用者實際生出來的東西,不在本 repo)**
- `mental/`:**共用、進 git**——map、concepts、scenarios、lenses、contracts、decisions… 團隊層級的「已同意的概念真實」。
- `.mental/`:**私有、被 gitignore**——個人的 profile、mastery.json、session 紀錄。`.gitignore` 規則是 `*` + `!.gitignore`(除了自己什麼都忽略)。這條隱私邊界是硬性的。

**7. `tests/`**:見下節——它是把這一堆散文綁在一起的「膠水」。

**8. `docs/`**:設計背景與 STE100 評估(含繁中版),是「為什麼這樣設計」的決策紀錄。

---

## 各部分怎麼協作

**一次 skill 呼叫的生命週期**(以 `build` 為例,`skills/build/SKILL.md`):
1. 讀 `references/` 那幾份共用規範 →
2. 確立來源邊界(只用使用者提供的來源,不自行上網) →
3. 沒有 `mental/` 就跑 `scaffold_workspace.py` 生骨架 →
4. 先寫 `mental/model/map.md`,再補足夠支撐它的 concepts/scenarios →
5. 用 `[observed]`/`[inferred]`/`[conflict]` 標記每個主張,全部維持 `status: draft` →
6. 跑 `validate_workspace.py` 驗證 →
7. **停在「promotion gate」等人決定** → 之後才把被明確接受的東西改成 `canonical` / `[agreed]`。

**貫穿全系統的三個機制:**

- **三種真實的分離**:`observed`(來源直接支持)/ `inferred`(agent 推論,待確認)/ `agreed`(人類批准)。加上 `conflict`(實作真實 vs 概念真實衝突)。**規則是:絕不把推論偷偷升級成同意,衝突絕不為了通過驗證而抹掉。** 這是它「可驗證」的根基。

- **draft → canonical 閘門**:agent 只能生 draft,升為 canonical 一定要人工過閘。`build`/`sync` 產出,人決定,才落地。

- **Lens × Views × Detail**:回答的三個獨立旋鈕——Lens(用哪個角色的視角,repo 預設 `engineer`)、Views(anchor/map/mechanism/scenario/evidence 五種語意切片可組合)、Detail(brief/standard/deep)。有明確的優先序:手動指定 > 當前目標 > session 證據 > 私有 profile > host memory(弱訊號)> 預設。**未經明確要求絕不持久化推論出來的偏好。**

**change / review 如何包夾 host 的 Plan Mode**(這是最巧妙的設計):`mental` **刻意不寫實作程式碼**。它在宿主的實作前後各放一個唯讀 skill:
```
change(該改什麼、選項與取捨) → 人做決定 → 宿主 Plan Mode(怎麼實作) → 實作 → review(實際改了什麼 + 稽核)→ quiz/sync
```
`change` 先於 Plan Mode 界定「要改什麼」,`review` 事後重建「實際的 Before→After」再對照當初批准的 brief 找出 `Decision Surprises`。

---

## 維繫一致性的契約:測試

`tests/test_plugin_contract.py` 很值得先讀——它把散落在各處的散文用**可執行的不變式**綁在一起,例如:
- 兩份 manifest 必須描述同一組 skill、同版本、且不含 mcpServers/apps/hooks;
- skill 集合必須剛好是那九個,frontmatter 只能有 `name`/`description`;
- 唯讀 skill 必須含明確的 write 邊界字串(如 `understand` 要有 "Never edit");
- 每個 skill 引用的 `../../references|scripts|assets/...` 路徑都必須真的存在;
- 全 repo 禁止出現舊詞彙 `zoom` / `L0-L4`(防止文件回退到已淘汰的設計)。

所以**改動任何一份散文,測試會逼你同步其他份**——這是一個「散文即程式碼」的 repo 用來防漂移的手段。另有 `test_workspace_scripts.py` 測那兩支腳本,`tests/fixtures/` 放了 repository / learning 兩種模式的完整範例工作區(可當你理解產出物長相的活教材)。

---

## 一個要注意的邊界

別把這個 repo 當成會「跑起來」的服務。它沒有 runtime、沒有網路呼叫、沒有狀態機在跑;它的行為完全發生在「agent 讀了 SKILL.md 之後照著做」的當下。因此**修改行為 = 修改 prompt 文字**,而正確性靠三樣東西守住:`validate_workspace.py` 的結構驗證、`tests/` 的跨檔一致性、以及 draft→canonical 的人工閘門。README 也提醒:跨 Claude Code / Codex 的參數 autocomplete **不保證**一致,唯一權威是每個 skill 裡的 Input contract。

---

想深入的下一步,我建議挑一條:(1) 我可以帶你逐一走完另外六個 skill(`sync`/`doctor`/`change`/`learn`/`practice`/`quiz`)的差異契約;(2) 實際跑一次 scaffold + validate,看產出物長什麼樣;或(3) 需要的話我把上面這份整理成一頁可分享的架構圖 artifact。你想往哪走?

> 依據:`README.md`、`references/methodology.md`、`references/artifact-contract.md`、`scripts/*.py`、`skills/{build,understand,review}/SKILL.md`、`tests/test_plugin_contract.py`、兩份 `plugin.json` 與 `marketplace.json`。尚未逐字讀:`sync/doctor/change/learn/practice/quiz` 六個 SKILL、三份 workflow/writing references、`docs/` 設計文件。
> Context:engineer lens · map,mechanism,scenario · standard — 依「剛接手、要快速理解架構」的目標選定;要調整可用 lens= views= detail=。