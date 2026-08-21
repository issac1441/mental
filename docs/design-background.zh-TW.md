# 設計背景與研究架構

[English version](design-background.md)

## 摘要

`mental` 處理的是一個協作瓶頸：agent 產生或修改內容的速度，可能快過人類建立可靠模型的速度。因此，本 plugin 優化的不是文件產量，而是模型取得、預測、修正與人類決策。

方法由小型關係模型、Lens × Views × Detail、runtime／遷移情境、主張來源標記、draft-to-canonical promotion，以及以證據為基礎的練習組成。本文件記錄這些設計如何從原始對話發展而來、它們與認知科學研究的關係，以及哪些主張仍需要實驗驗證。

## 1. 問題定義

最初的設計對話從 coding agent 協作開始。大型 code diff 可能局部正確，但操作者仍無法回答：

- 系統模型到底改了什麼？
- 哪個邊界、契約或不變量現在最重要？
- runtime 實際上應該發生什麼？
- agent 代替操作者做了哪些決定？
- 這份解釋從哪裡開始失去預測力？

學習也有同樣的落差。學習者可以讀完流暢摘要，卻無法重建機制、預測結果或把概念遷移到新情境。接收內容不等於取得模型。

因此，核心設計問題是：

> Agent 要如何協助人類建立小而可追溯、能支持預測與修正的模型，同時不取代人類判斷？

## 2. 設計假說

以下是產品假說，不是 `mental` 已經證實的效果。

### H1 — 關係比清單更重要

由邊界、prerequisite、因果、契約與失敗路徑構成的小型關係圖，應該比完整檔案或事實清單更能支持有用預測。

### H2 — 適當視角能減少不必要資訊

先選擇符合角色的 Lens、必要的語意 Views 與適當 Detail，應該能在 orientation 時減少無關資訊。漸進式揭露先幫助人建立 schema，再進入實作證據。

### H3 — 預測能暴露模型缺口

在揭露答案或 implementation trace 前先要求預測，應該比詢問「有沒有聽懂」更容易找出缺少的關係。

### H4 — 遷移與反例比辨識更強

能用自己的話解釋關係、套用到新情境並指出邊界，比只認得熟悉措辭提供更強的理解證據。

### H5 — 概念真相必須由人類確認

Agent 可以整理證據並建立 draft；它不能自行決定推論出的邊界、因果或不變量已成為團隊共識。因此，promotion 至 `canonical` 必須經過明確的人類決定。

## 3. 與認知科學的連結

下列研究是設計動機，不是整個 plugin 的有效性證明。

### Mental model

Johnson-Laird 的早期論述把 mental model 視為認知與推理所使用的表徵。`mental` 借用「有用表徵應該支持推論」這個實務觀點。Repo 中的 Markdown graph 是外部協作 artifact，不代表它等同於人腦內部表徵。

### 認知負荷與 schema acquisition

Sweller 於 1988 年提出的實驗與模型指出，傳統 means-ends problem solving 可能占用原本可用於 schema acquisition 的處理容量。`mental` 因此採漸進式揭露、小型關係集合、worked scenario 與明確 prerequisite。目前 plugin 沒有量測認知負荷，所以不能宣稱已降低認知負荷。

### Self-explanation

Chi 等人的研究發現，較成功的學習者在閱讀 worked examples 時產生較多 self-explanation，並把解題步驟連回原理。這支持 teach-back、prediction 與「先修正第一個斷裂關係」的設計，但不代表每次口頭解釋都足以證明 mastery。

### Retrieval 與 transfer

Karpicke 與 Blunt 在科學文本實驗中發現，retrieval practice 的學習效果優於 elaborative concept mapping。這對本產品是一個重要限制：建立 map 本身不夠，`/mental:practice` 必須要求重建與遷移。

## 4. 方法推導

本方法刻意拆開大型架構文件常混在一起的問題：

- 結構視圖回答「有什麼」。
- 情境回答「發生什麼」。
- 決策紀錄回答「為什麼形成這個形狀」。
- 證據回答「觀察到什麼」。
- Canonical 狀態回答「人類同意用什麼概念模型理解它」。

Lens × Views × Detail 選擇回答策略；model map 命名最小必要關係；scenarios 測試關係能否預測行為；claim labels 分開觀察、推論、共識與衝突；promotion gate 防止流暢的 agent 內容意外成為已接受真相。

### 設計語彙的演化

最初設計使用 **Lens × Zoom**。當時 Lens 指 architect、debugger 等視角；以學歷分級的例子其實是在描述 audience assumption。現在把兩者合併：Lens 代表某個角色通常具備的知識、語彙、關注與決策方式。因此 `architect`、`student` 與 `pm` 都是 Lens；它只影響這次回答假設什麼、強調什麼，不表示使用者永久就是該角色。

舊 L0–L4 也混合了不同維度。「Runtime」和「evidence」並不是「system」的更詳細版本，而是不同語意切面，而且使用者常需要同時選取多個切面。現在的 operational model 改用可複選 Views（`anchor`、`map`、`mechanism`、`scenario`、`evidence`），並以獨立的 Detail（`brief`、`standard`、`deep`）控制密度。舊名稱只留在本背景文件記錄設計來源；skills 不接受舊名稱作為 alias。

情境選擇依序使用手動指定、目前明確目標、current session evidence、private profile／mastery、host 有提供時的弱 memory signal，最後才是 scope default。這讓 agent 能自適應，又不會把推論靜默變成永久 user profile。

Repo 變更流程是：

1. Orient 至 current model。
2. 在改動前預測目前行為。
3. 提出 model delta。
4. 揭露 decisions、contracts、invariants 與 failure behavior。
5. 取得 human decision。
6. 實作已接受的變更。
7. 驗證原先預測。
8. 保留 surprise，並同步已接受的模型變更。

學習流程是：

1. 診斷少量 prerequisite 關係。
2. 提供一個 anchor 與小型關係集合。
3. 走過一個代表性情境。
4. 呈現一個邊界、失敗或 misconception。
5. 要求 retrieval、prediction 或 teach-back。
6. 修正第一個斷裂關係。
7. 以 transfer 檢核後，才記錄 verified mastery。

## 5. 真相與治理

`mental` 分開兩種真相：

- 來源、程式碼、測試與 runtime observation 描述材料／實作真相。
- Canonical artifacts 描述人類同意的概念真相。

兩者可能衝突。衝突是一項發現，不是靜默改寫任何一方的授權。因此 artifacts 使用 `[observed]`、`[inferred]`、`[agreed]` 與 `[conflict]`。

共享模型放在 `mental/`。個人目標、診斷答案、session note 與 mastery evidence 放在 gitignored `.mental/`。這個分離讓團隊能共享模型，又不會公開學習者 profile。

## 6. 評估計畫

評估應針對明確 task class，比較 `mental` 與 host agent 的一般工作方式。不要把不同任務合成單一 trust score。

可用指標包括：

- **Orientation time：**直到使用者能說明邊界並追蹤代表性情境所需的時間。
- **Prediction accuracy：**對未見 runtime 或 transfer case 的正確預測率。
- **Model correction：**找出並修正刻意放入的錯誤關係。
- **Decision Surprise Rate：**核准後才發現的重大決策數，除以該任務中檢視過的重大決策數。
- **Transfer performance：**把模型套用到結構相似新情境的能力。
- **Drift detection：**能否找出 source/model conflict，並在 human decision 前持續揭露。
- **Privacy containment：**個人學習資料是否留在版控 artifacts 之外。

可信的研究應記錄 prior knowledge、task class、source quality、model status、耗時與協助程度，也應包含 delayed retention。Prediction task 必須在模型建立後才揭露。

## 7. 威脅與限制

- 漂亮的 graph 仍可能是錯的。Evidence link 與 human confirmation 只能降低風險。
- Source-bound learning 也可能忠實保留原始材料的錯誤或缺漏。
- Lens × Views × Detail 是設計語彙，不是已驗證的認知分類法。
- 四種 mastery state 是 workflow state，不是心理計量結果。
- Agent 診斷可能反映 prompt 品質或 source coverage，而不是學習者能力。
- Artifacts 太多會增加維護成本。每一份 artifact 都必須改善一項預測或決策。
- 單一 repo、學習者、語言或主題的結果，不能證明廣泛有效。

## 8. 論文形狀的研究議程

未來的 paper 或 proposal 可以採用以下結構：

1. **Introduction：**agent throughput 與人類 model-acquisition bottleneck。
2. **Related work：**mental models、cognitive load、self-explanation、retrieval practice、architecture knowledge 與 human-agent oversight。
3. **Method：**Lens × Views × Detail、artifact contract、provenance、promotion gates 與 skill workflows。
4. **Research questions：**orientation、prediction、transfer、decision surprise、drift 與 privacy。
5. **Study design：**task classes、baselines、participants、source controls 與 delayed tests。
6. **Results：**behavioral outcomes 與 failure cases，而不只 satisfaction。
7. **Discussion：**externalized model 在哪裡有效、在哪裡增加摩擦，以及 agent error 如何傳播。
8. **Limitations and ethics：**learner profiling、source bias、over-trust、privacy 與 generalizability。

## 9. 來源與參考資料

初始問題、Living System Model、原始 Lens × Zoom、model-delta workflow、Decision Surprise Rate，以及 implementation truth／conceptual truth 的區分，來自[使用者提供的設計對話](https://chatgpt.com/share/6a7f588a-6aa8-83ee-a4d4-7ea7cdc7a38c)。後續討論把 audience 與 perspective 合併至 Lens、把舊尺度拆為 Views 與 Detail、釐清 `change` 和 Plan Mode 的先後、分開自適應 `practice` 與有界 `quiz`，並把 session context 納入正式選擇訊號。本文件同時記錄兩個階段；該對話是設計來源，不是 peer-reviewed evidence。

- P. N. Johnson-Laird, “Mental Models in Cognitive Science,” *Cognitive Science* 4(1), 1980. [DOI](https://doi.org/10.1207/s15516709cog0401_4)
- John Sweller, “Cognitive Load During Problem Solving: Effects on Learning,” *Cognitive Science* 12(2), 1988. [DOI](https://doi.org/10.1207/s15516709cog1202_4)
- Michelene T. H. Chi et al., “Self-Explanations: How Students Study and Use Examples in Learning to Solve Problems,” *Cognitive Science* 13(2), 1989. [DOI](https://doi.org/10.1207/s15516709cog1302_1)
- Jeffrey D. Karpicke and Janell R. Blunt, “Retrieval Practice Produces More Learning than Elaborative Studying with Concept Mapping,” *Science* 331(6018), 2011. [DOI](https://doi.org/10.1126/science.1199327)
