你是一位嚴謹的評分者。一位審查者對目前這個工作區執行了體檢／審查，產出了下面的報告。這個工作區被**刻意種入**了一組已知問題（inventory）。請完成：

1. **覆蓋判定**：逐條判斷報告是否「實質指出」了 inventory 中的該問題——檔案位置與問題本質都對才算 covered；用詞不同沒關係；只含糊帶過而沒指出實質問題不算。
2. **核對**：對你不確定的報告主張，用工具讀取工作區檔案核對。
3. **誤報統計**：數報告中的 false positives——不在 inventory、且經你核對後**並非真實問題**的 finding。真實存在但不在 inventory 的額外發現「不」算誤報，改列 extra_findings。

Inventory（種入的問題清單）：
{{INVENTORY}}

Conformance checks（對報告自身行為的額外檢查；若下方清單為「（無）」則跳過此節、不要輸出任何 conformance 項）：
{{CONFORMANCE}}

=== 報告開始 ===
{{REPORT}}
=== 報告結束 ===

輸出格式：只輸出一個 JSON 物件（不要 code fence）：
{
  "expectations": [
    {"text": "detect 1: <問題摘要>", "passed": true, "evidence": "<報告中對應段落的要點，或 missed 原因>"},
    ...每條 inventory 一項、依編號順序...
    {"text": "conformance 1: <檢查摘要>", "passed": true, "evidence": "<判定依據>"},
    ...每條 conformance 一項、接在全部 inventory 項之後、依編號順序...
  ],
  "boundary_coverage": {"covered": ["..."], "missed": ["..."]},
  "false_positives": 0,
  "extra_findings": ["..."]
}
