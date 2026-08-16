---
id: learning-path
kind: learning-path
authority: conceptual
status: active
sources:
  - source-event-loop
prerequisites:
  - event-loop
updated_at: 2026-08-15
---

# 學習路徑

這條路徑依序建立 anchor、prediction、transfer 與 boundary：

1. 用 queue 建立 anchor。
2. 預測長 task 對後續 task 的影響。
3. 將長 task 拆分後重新預測順序。
4. 指出模型不涵蓋多執行緒。

## Verification basis

- 每個活動都能由 `source-event-loop` 判定。
- 包含 success prediction、transfer 與 multi-thread boundary。
