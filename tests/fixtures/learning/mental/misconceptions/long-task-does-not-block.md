---
id: long-task-does-not-block
kind: misconception
authority: conceptual
status: active
sources:
  - source-event-loop
prerequisites:
  - event-loop
updated_at: 2026-08-15
verification_basis:
  - source:source-event-loop
checked_predictions:
  - "success: a short task starts after the current task finishes"
  - "failure: a long current task delays later queued tasks"
known_gaps: []
conflicts: []
---

# 長 task 不會影響後續工作

這是錯誤模型；來源明確指出長 task 會延遲後續 tasks。
