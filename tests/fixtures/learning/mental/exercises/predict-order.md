---
id: predict-order
kind: exercise
authority: conceptual
status: active
sources:
  - source-event-loop
prerequisites:
  - event-loop
updated_at: 2026-08-15
verification_basis:
  - source-event-loop makes the requested prediction decidable
checked_predictions:
  - "success: a split task allows another queued task to run"
  - "failure: one long task delays the task behind it"
known_gaps: []
conflicts: []
---

# 預測順序

不用查筆記，說明為什麼一個長 task 會延遲排在它後面的短 task，再提出一種讓短 task 更早開始的方法。
