---
id: mental-index
kind: index
authority: conceptual
status: active
sources:
  - source-event-loop
prerequisites: []
updated_at: 2026-08-15
mode: learning
language: zh-TW
verification_basis:
  - source:source-event-loop
checked_predictions:
  - "success: the index leads to the queue and task relationship"
  - "boundary: the index does not claim multi-thread behavior"
known_gaps:
  - multi-thread behavior is outside the supplied source
conflicts: []
---

# Event loop 心智模型

Event loop 的核心預測問題是：下一個 task 何時能開始？

- [概念圖](model/map.md)
- [學習路徑](learning/path.md)
- [來源](sources.md)
- [詞彙](glossary.md)
