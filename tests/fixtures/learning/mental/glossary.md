---
id: glossary
kind: glossary
authority: conceptual
status: active
sources:
  - source-event-loop
prerequisites: []
updated_at: 2026-08-15
verification_basis:
  - source-event-loop defines task and queue usage
checked_predictions:
  - "success: the terms support prediction of queued task order"
  - "boundary: the terms do not define multi-thread scheduling"
known_gaps:
  - multi-thread terminology is outside scope
conflicts: []
---

# 詞彙

- **task**：event loop 一次取出並執行的工作單位。
- **queue**：等待執行的 tasks 順序。
