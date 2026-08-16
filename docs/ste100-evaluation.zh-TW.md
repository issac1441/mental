# ASD-STE100 評估與寫作規範

[English version](ste100-evaluation.md)

## 決定

`mental` 採用 **STE-inspired clarity profile**，但不宣稱 plugin 或輸出內容符合 ASD-STE100。

ASD-STE100 Issue 9 是用於技術文件的 controlled English，由 writing rules 與 controlled dictionary 組成。官方 FAQ 說明它不是 general-purpose writing 規範，但短句、每句一個主題與 active voice 等原則可以應用到其他寫作情境。

這個界線很適合 `mental`：skill 中的程序指令非常適合 STE 原則；多語言教學與概念解釋則需要更寬廣的語言表達。

## 各類內容的適用度

| 內容 | 適用度 | 規範 |
| --- | --- | --- |
| `SKILL.md` workflow | 高 | 使用直接 imperative、明確 actor/object、每步一個主要動作，並先呈現必要條件。 |
| 安裝與驗證指令 | 高 | 使用短而有順序的步驟、穩定 command name，並分開 expected result。 |
| Artifact templates | 高 | 使用精確 headings 與 prompts，分開決策、證據與動作。 |
| Validator diagnostics | 中 | 指出物件、問題與最小修正；避免指涉不明的代名詞。 |
| Methodology 與設計論述 | 中 | 使用漸進式結構與穩定術語，但保留必要的限定與論證。 |
| Adaptive lessons | 選擇性 | 每個 chunk 聚焦一個關係，但保留類比、提問、範例與自然的學習者語言。 |
| 繁體中文內容 | 僅套用原則 | 採用清晰度與資訊順序原則；不套用英文 grammar、dictionary 或 word count。 |

## 採用的原則

實作規範採用以下想法：

- 在同一範圍內，一個概念使用一個穩定術語。
- Actor 已知時使用 active voice。
- 程序使用直接 imperative。
- 如果讀者執行前必須知道條件，先寫條件，再寫動作。
- 每個編號步驟只放一個主要動作。
- 可行時，每個敘述句或段落只處理一個主題。
- 從 anchor、relationships 到 detail，逐步提供資訊。
- 當 prose 會藏住 alternatives、conditions 或 results 時，改用 vertical list。
- 不省略 actor、object、evidence 或 decision state。
- 使用具體行為，避免「正確運作」之類的抽象主張。

對英文技術內容而言，官方的 procedural sentence 20 words、descriptive sentence 25 words 上限可以作為 review signal。`mental` 不把它們做成普遍硬限制，因為連結、code identifier、evidence marker 與教學情境會讓機械式計數產生誤導。

## 刻意不採用的要求

本專案不採用：

- 完整 controlled English dictionary；
- 英文 verb form 或 `-ing` form 限制；
- 航太專用 safety-instruction rules；
- 機械式 word-count validation；
- ASD-STE100 compliance 標籤。

完整合規必須把目前標準與 dictionary 全部套用到適用的英文技術內容。只採部分原則不能證明合規。官方標準受著作權保護，本 repo 只提供連結，不會內嵌該 PDF。

## 預期效益

這個 profile 應能讓 agent 更一致地解析指令，也讓人更容易掃讀程序。穩定 terminology 也能協助翻譯，並減少同一概念意外產生多個名稱。

如果它移除了有用類比、語氣、uncertainty 或 learner-specific phrasing，也可能傷害理解。因此，概念與學習內容把它當作 clarity constraint，不把它當作 controlled vocabulary。

## 驗證狀態

這是一項設計決定，不是實驗結果。Repo 會驗證每個 skill 都載入共用 writing profile，但不會用機械式檢查證明所有文件都符合 profile，也不能保證文件不會誤稱完整合規。Readability、task success、translation quality 與 learning outcome 仍需要 user study 或 controlled comparison。

## 官方來源

- [ASD-STE100 官方網站](https://www.asd-ste100.org/)：目前版本與適用範圍。
- [官方 FAQ](https://www.asd-ste100.org/STE_faq.html)：預期用途、原則、限制、翻譯與合規注意事項。
- [ASD-STE100 Issue 9](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf)：官方 writing rules 與 dictionary。本 repo 只連結，不重新散布 PDF。
