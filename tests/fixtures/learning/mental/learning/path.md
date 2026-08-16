---
id: learning-path
kind: learning-path
status: canonical
sources:
  - source-event-loop
prerequisites:
  - event-loop
updated_at: 2026-08-15
---

# 學習路徑

[agreed] 這條路徑依序建立 anchor、prediction、transfer 與 boundary：

1. 用 queue 建立 anchor。
2. 預測長 task 對後續 task 的影響。
3. 將長 task 拆分後重新預測順序。
4. 指出模型不涵蓋多執行緒。
