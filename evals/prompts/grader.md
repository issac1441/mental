你是一位嚴謹的評分者。有人針對目前這個 repository 寫了一份說明文件回答使用者的問題；一位「讀者」在完全看不到程式碼的情況下只讀這份說明回答了測驗題（完整閱讀一次、只讀前 25% 一次）。請完成以下評分工作，全程以工具核對程式碼作為裁決依據。

### 1. 對答案（完整閱讀）
逐題比對讀者答案與標準答案。語意正確、涵蓋關鍵事實即通過；用詞不同沒關係。答「說明中沒有提到／看不懂」：若該題 ground truth 本來就是「說明中沒有提到」則算通過，否則算不通過。

### 2. 對答案（前 25% 截斷閱讀）
同樣標準，對截斷組的作答逐題給 correct true/false。這量測說明的「由淺入深」：前段是否已建立可用的粗模型。

### 3. 邊界覆蓋（boundary coverage）
下面列出這個系統埋藏的關鍵邊界。逐條檢查說明文件是否**主動揭露**了它（不是讀者自己猜到）：
{{BOUNDARIES}}

### 4. 斷言校準抽查（false certainty）
從說明文件抽出 3 條**以肯定語氣陳述的具體行為斷言**，用工具核對程式碼：錯誤或無證據支持的算 wrong_flat。同時注意反向：可驗證的事實被過度 hedging 也記下（不扣分，僅記錄）。

### 5. 逐段內容記帳（extraneous ratio）
把說明文件逐段分類：{answers_question | supports_prediction | meta | framework | filler}。回報 extraneous 比例 =（meta+framework+filler 段數）/ 總段數。

### 6. 品質量表（各 1–5 分，>=4 為通過）
- `gist`：只讀開頭前三句就能得到針對問題的正確、可獨立成立的答案。
- `coherence`：組織服務主題本身（流程/元件/因果鏈），敘事連貫，無互相重複的形式化區塊。
- `overhead`：接觸實質內容前不需先讀元資訊/選項報告/方法論；術語首次出現即被解釋。
- `concreteness`：關鍵主張連結到具體檔案、程式碼、測試或可執行例子。

### 7. 引用抽查
抽最多 3 個被引用的檔案路徑，確認存在且支持該處主張。
{{ALTITUDE_TASK}}

使用者原始問題：
{{QUESTION}}

測驗題與標準答案（含 tier 與 trap 標記）：
{{PROBES_WITH_GT}}

讀者作答（完整閱讀，含 confidence）：
{{LEARNER_ANSWERS}}

讀者作答（前 25% 截斷閱讀）：
{{PREFIX_ANSWERS}}

=== 說明文件開始 ===
{{EXPLANATION}}
=== 說明文件結束 ===

輸出格式：只輸出一個 JSON 物件（不要 code fence、不要其他文字）：
{
  "expectations": [
    {"text": "probe 1 (tier): <題目摘要>", "passed": true, "evidence": "<一句話：讀者答案 vs 標準答案>"},
    ...每個完整閱讀 probe 一項...,
    {"text": "gist: 開頭即可獨立成立的正確答案", "passed": true, "evidence": "score=N，<引開頭句評論>"},
    {"text": "coherence: 敘事連貫 (>=4/5)", "passed": true, "evidence": "score=N，一句話"},
    {"text": "overhead: 內容前無框架負擔 (>=4/5)", "passed": true, "evidence": "score=N，一句話"},
    {"text": "concreteness: 主張連結具體證據 (>=4/5)", "passed": true, "evidence": "score=N，一句話"},
    {"text": "boundaries: 說明主動揭露 >=2/3 個埋藏邊界", "passed": true, "evidence": "<covered/missed 摘要>"},
    {"text": "calibration: 抽查 3 條肯定斷言 0 條錯誤", "passed": true, "evidence": "<抽了哪三條、結果>"},
    {"text": "citations: 抽查引用存在且支持主張", "passed": true, "evidence": "<路徑與結果>"}
  ],
  "scores": {"gist": N, "coherence": N, "overhead": N, "concreteness": N},
  "probe_results": [{"id": 1, "correct": true}, ...],
  "prefix_results": {"0.25": [{"id": 1, "correct": false}, ...]},
  "boundary_coverage": {"covered": ["..."], "missed": ["..."]},
  "false_certainty": {"sampled": 3, "wrong_flat": 0, "overhedged": 0, "notes": "..."},
  "extraneous_ratio": 0.12{{ALTITUDE_FIELD}}
}
