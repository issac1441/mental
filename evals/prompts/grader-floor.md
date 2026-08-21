你是一位嚴謹的評分者。一位讀者在**完全沒有任何說明文件、也看不到程式碼**的情況下（floor 控制組），僅憑常識與先備知識回答了關於某系統的測驗題。請逐題比對讀者答案與標準答案：語意正確、涵蓋關鍵事實即通過。答「說明中沒有提到／看不懂／無法判斷」一律算不通過（floor 組要量測的是裸猜能對多少）。

測驗題與標準答案：
{{PROBES_WITH_GT}}

讀者作答：
{{LEARNER_ANSWERS}}

輸出格式：只輸出一個 JSON 物件（不要 code fence）：
{
  "expectations": [
    {"text": "probe 1: <題目摘要>", "passed": false, "evidence": "<一句話>"},
    ...
  ],
  "probe_results": [{"id": 1, "correct": false}, ...]
}
