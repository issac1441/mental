# 設計背景與研究架構

[English version](design-background.md)

## 摘要

`mental` 處理的是一個協作瓶頸：agent 採取行動的速度，可能快過人類建立可靠模型的速度。因此，產品要縮短的是「agent 已執行」與「人類取得模型」之間的落差，並同時支援 agentic software work 與 source-bound learning。

目前方法強調先提供價值再建 artifacts、human-first prediction、decision accountability、自適應修正、三種 artifact authority 與 first-class conflicts。本文件記錄原始研究架構、後續設計修正，以及仍需要實驗驗證的主張。

## 1. 問題定義

大型 code change 可能局部正確，但操作者仍無法回答：

- 系統模型到底改了什麼？
- 哪個邊界、契約或不變量現在最重要？
- Runtime 應該發生什麼？
- Agent 代替操作者做了哪些重大選擇？
- 這份解釋從哪裡開始失去預測力？

學習也有相同落差。學習者可能讀完流暢摘要，卻無法重建機制、預測結果或遷移概念。交付內容與生成 artifacts 都不等於取得模型。

核心問題因此是：

> Agent 要如何幫助人建立並修正小而可追溯的模型，同時不代替人完成 prediction 或 decision？

## 2. 設計假說

以下是產品假說，不是已證實效果。

### H1 — 關係比清單重要

由邊界、prerequisite、因果、契約與失敗構成的小型關係圖，應該比完整 inventory 更能支援有用預測。

### H2 — Lens × Job 能減少無關說明

Session 角色（Lens）加上目前認知任務（Job），應該比 generic answer 或要求使用者預先設定大量旋鈕，更能選出有用的回答。

### H3 — Human-first prediction 能暴露 model gap

在重大情境中，先讓人預測再揭露證據，應該比詢問「有沒有聽懂」更容易發現缺少的關係。但互動必須允許直接回答或 `skip`；強制 Socratic friction 也可能降低價值。

### H4 — 遷移與反例比 recognition 強

獨立解釋、套用到結構相似的新案例，以及指出邊界或反例，比點頭或辨識熟悉文字提供更強的理解證據。

### H5 — Gate 必須符合人的判斷立足點

人可以正當決定期望行為、trade-off、ownership 與風險；剛進入陌生 repo 的人不能因為核准流暢 draft 就驗證陌生事實。因此 mechanical refresh、conceptual activation 與 human decision 必須使用不同 gate。

### H6 — 工作流程內的學習具有更高觸及率

把短 prediction 與 repair 放進 `change`、`review`，可能接觸到不會另外開始讀書 session 的操作者。`learn`、`practice`、`quiz` 仍服務明確的學習目標。

## 3. 與認知科學的連結

下列研究是設計動機，不是整個 plugin 的有效性證明。

### Mental model

Johnson-Laird 把 mental model 描述為認知與推理使用的表徵。`mental` 借用「有用表徵應支援推論」的實務判準。Markdown artifacts 是外部協作物，不代表人腦內部表徵。

### 認知負荷與 schema acquisition

Sweller 於 1988 年指出 means-ends problem solving 可能占用原本可用於 schema acquisition 的處理容量。漸進式揭露、小型關係集合、worked scenario 與明確 prerequisite 回應了這項顧慮。`mental` 沒有量測認知負荷，因此不能宣稱已降低它。

### Self-explanation 與 generation

Chi 等人發現較成功的學習者會產生更多 self-explanation，並把步驟連回原理。這支援 teach-back、human prediction 與修正第一個斷裂關係；由 agent 代寫 prediction 反而會破壞目的。

### Retrieval 與 transfer

Karpicke 與 Blunt 在科學文本實驗中發現 retrieval practice 優於 elaborative concept mapping。因此只有 map 不夠，學習者必須重建與遷移。Retrieval 也可能強化錯誤模型，所以來源證據、反例與 open conflicts 必須保持可見。

## 4. 方法演化

### 從 Lens × Zoom 到 Lens × Views × Detail

最初設計使用 Lens × Zoom。後續把 anchor、map、mechanism、scenario、evidence 等語意切面與回答密度分開，因為 evidence 並不是 system structure 的更深版本。

但這次修正仍把太多控制暴露在 input surface。Lens 到 default Views 的 mapping 沒增加多少資訊，而 Detail 也部分重複 View selection。

### 從 Lens × Views × Detail 到 Lens × Job

目前介面保留：

- **Lens**：低頻的 session assumption，描述角色知識、語彙、關注與決策方式；
- **Job**：每次任務的需求，包含 orient、decide、predict、verify、repair。

Views 留作 agent 內部 audit vocabulary。只有使用者手動指定、不是預設、存在不確定性，或揭露後可以採取行動時才會顯示。熟悉的使用者可以 override，第一次使用不必懂 taxonomy。

Built-in Lens 的名稱看似角色，是使用上的捷徑，不是 identity claim。同一個人可以在一次說明使用 `architect`，下一次改用 `student`。Job 決定認知任務；Lens 提供預設知識、語彙與顯著關注。`concerns` 不是白名單：PM Lens 在 Job 是 prediction 時仍然可以追蹤 mechanism。兩者看似衝突時，由 Job 優先、Lens 決定表達方式。這個區分仍需實證，因為 agent 若使用不慎，角色標籤仍可能誘發 identity-based inference。

### 從 artifact-first 到 value-first

早期 Quickstart 要求先 `build`。這延遲第一次價值，並要求 newcomer 核准自己還沒有能力判斷的 model。現在先使用唯讀 `understand` 或直接從來源開始 `learn`；互動證明具有重用價值後，才選擇 `build`。

### 從 agent prediction 到 human prediction

曾出貨的 change workflow 要求 agent 寫 Prediction，反而重現產品想阻止的認知外包。現在 `change` 只在能影響重大決策時詢問一個高資訊量 prediction，允許 `skip`，再用證據比較並修正最小 model gap。`skip` 只影響當次 invocation，不保存成 behavior profile。需要記錄時，只保存 prediction 是 attempted、skipped 或 not applicable；除非使用者要求，答案留在對話而不寫入 artifact。

### 從單一 promotion gate 到三種 gate

早期把 human assent 當作 draft 變 canonical 的路徑，混淆了 recognition、decision authority 與 factual verification。目前分為：

- 從已註冊證據刷新 mechanical artifacts；
- 具有明確 verification basis 才啟用 conceptual artifacts；
- 由人接受意圖與 trade-off。

`active` 表示目前 working model，不是絕對真理。

## 5. Authority、conflict 與 decision

來源檔案、code、tests 與 runtime observations 仍是材料／實作真相。團隊共用 artifacts 會宣告 maintenance authority：

- **mechanical** artifacts 是可重新生成的 cache；只有具備已記錄 source ID、具體 revision、refresh basis 與 Evidence section 時才可自動刷新；
- **conceptual** artifacts 是 durable explanation，啟用前需要證據與已檢查 prediction；
- **decision** artifacts 保存人或 agent 的選擇、被否決替代方案、浮現時機與可逆性。

Authority 與 volatility 是兩個正交軸。Authority 決定誰能更新 artifact；volatility 決定 agent 應多久檢查一次。V1 暫不增加 `volatility` 欄位，因為目前沒有通過驗證的 decay policy。已註冊 source revision 加上 `current|stale` 是較小的操作機制；未來應評估獨立 decay hint 是否能減少掃描，同時不增加另一個儀式性欄位。

Mechanical 不是「完全沒有推論」，而是 bounded agent pass 可以從註冊證據
穩定重建相同 representation，且不需要選擇期望行為或解決競爭的 conceptual
interpretation。因此，可同時作為 cache 或 explanation 的 kind 允許 mechanical
與 conceptual 兩種 authority。只有 artifact 記錄如何重建 mechanical reading
時才可自動 refresh；否則應標示 stale 並揭露 delta。

Conflicts 是具有穩定 ID、owner、雙方證據與 resolution 的 `open|resolved` artifacts，不再只是 inline confidence label。

Decision Surprise 描述 agentic coding 特有的失敗：重大選擇在核准或實作後才浮現。單次 review 的 Decision Surprise Rate 是「post-approval consequential decisions ÷ 該次 review 發現的全部 consequential decisions」。沒有有效分母時回報 `N/A`，不能把它變成 global trust score。

Trust 的單位是 `Model × Harness × Task Class`。沒有 task-relevant test 或 canary 的 model 不足以支持 autonomy；harness 也不能把信任擴張到未涵蓋的 task class。

## 6. Skill 與 output-style 層

Opt-in skill 無法單獨修正所有預設說明品質。因此 `mental` 定義共用 output policy：先說 outcome、提供最小可預測模型、漸進揭露證據、保留可採取行動的不確定性，且不重複 context header。

Portable plugin 能保證 mental skills 內使用此 policy。要讓 skill 外的所有回答也套用，取決於 host-level instruction mechanism，必須另外評估，不能假設跨 host 一致。

六個主要 skills 保留有意義的互動與寫入邊界：`understand`、`change`、`review`、`learn`、`practice`、`quiz`。`build`、`sync`、`doctor` 是進階 persistence 與 maintenance capabilities。這降低 cold-start 複雜度，又不會把唯讀說明、private learning writes 與 artifact maintenance 混進含糊指令。

## 7. 評估計畫

評估應針對明確 task class，比較 `mental` 與 host agent 的一般 workflow。可用指標包括：

- **Time to first value：**從安裝到取得有用答案的時間。
- **Orientation time：**直到人能說明邊界並追蹤 scenario 的時間。
- **Prediction accuracy：**對未見 runtime 或 transfer case 的正確預測。
- **Model correction：**找出並修正刻意放入的錯誤關係。
- **Decision Surprise Rate：**有界的 post-approval consequential choices 比例。
- **Transfer performance：**把模型套用到結構相似新案例的能力。
- **Maintenance cost：**人類檢視 mechanical 與 conceptual drift 的時間。
- **Privacy containment：**個人學習資料是否留在版控 artifacts 之外。

可信研究應記錄 prior knowledge、task class、source quality、artifact authority、耗時、協助程度、harness coverage 與 delayed retention。Prediction task 必須在人先作答後才揭露。

實作保證使用兩個正交層。Deterministic tests 在 CI 中快速驗證 manifests、
schemas、paths、privacy 與 state transitions；conversation eval 則真的執行
Claude Code 或 Codex host，保留實際輸出與 workspace delta，再交給 rubric
judge 評分 conditional behavior。只檢查某句話是否存在，不算 conversation
eval。Host eval 較慢且具有雜訊，因此是 deterministic layer 的補充，不是替代。

Deterministic workspace snapshot 會記錄 fixture 內的一般檔案內容、directory
是否存在、symlink target 與 special-file type，因此能抓到執行結束時的淨變化，
包括 empty directory 與 symlink。但它不能證明 host 從未寫入後刪除，也看不到
fixture 外的寫入；read-only cases 因此也使用 host 的唯讀控制。Capture-only run
明確標成未評分，不能通過 evaluation gate。

## 8. 威脅與限制

- 漂亮的 model 仍可能是錯的，而且 practice 可能強化這個錯誤。
- Source-bound learning 可能保留原始材料的錯誤或缺漏。
- Human prediction 只有在問題具有資訊價值時才值得；過度使用會變成 ceremony。
- Lens × Job 是設計語彙，不是已驗證的認知 taxonomy。
- Mastery states 是 workflow states，不是心理計量結果。
- Agent diagnosis 可能反映 prompt 與 source quality，而不是 learner ability。
- Generated artifacts 可能形成維護負擔；persistence 必須先證明價值。
- Skill instructions 只能降低 prompt injection 風險，不是 security sandbox。
- 單一 repo、學習者、語言或主題不能證明普遍效果。

## 9. 論文形狀的研究議程

1. **Introduction：**agent throughput 與 human model-acquisition bottleneck。
2. **Related work：**mental models、cognitive load、self-explanation、generation、retrieval、architecture knowledge 與 human-agent oversight。
3. **Method：**Lens × Job、human-first prediction、authority-specific gates、decision ledger、conflicts 與 adaptive repair。
4. **Research questions：**time to value、prediction、transfer、Decision Surprise、maintenance cost 與 privacy。
5. **Study design：**task classes、baselines、participants、source controls、harnesses 與 delayed tests。
6. **Results：**behavioral outcomes 與 failure cases，不只 satisfaction。
7. **Discussion：**externalized model 在哪裡有幫助、在哪裡增加 friction，以及 agent error 如何傳播。
8. **Limitations and ethics：**learner profiling、source bias、over-trust、privacy 與 generalizability。

## 10. 來源與參考資料

初始問題、Living System Model、Lens × Zoom、model-delta workflow、Decision Surprise Rate、truth layering、trust unit 與 PREDICT interaction，來自[使用者提供的設計對話](https://chatgpt.com/share/6a7f588a-6aa8-83ee-a4d4-7ea7cdc7a38c)。後續討論把 audience 與 perspective 合併進 Lens、分開 adaptive practice 與 fixed quiz、加入 session context，接著修正 artifact-first onboarding、agent-authored prediction、單一 promotion gate 與過度暴露的 Views/Detail controls。本文件保留這段演化，不把目前版本包裝成唯一必然結果。

- P. N. Johnson-Laird, “Mental Models in Cognitive Science,” *Cognitive Science* 4(1), 1980. [DOI](https://doi.org/10.1207/s15516709cog0401_4)
- John Sweller, “Cognitive Load During Problem Solving: Effects on Learning,” *Cognitive Science* 12(2), 1988. [DOI](https://doi.org/10.1207/s15516709cog1202_4)
- Michelene T. H. Chi et al., “Self-Explanations: How Students Study and Use Examples in Learning to Solve Problems,” *Cognitive Science* 13(2), 1989. [DOI](https://doi.org/10.1207/s15516709cog1302_1)
- Jeffrey D. Karpicke and Janell R. Blunt, “Retrieval Practice Produces More Learning than Elaborative Studying with Concept Mapping,” *Science* 331(6018), 2011. [DOI](https://doi.org/10.1126/science.1199327)
