---
id: model-map
kind: map
status: canonical
sources:
  - source-event-loop
prerequisites: []
updated_at: 2026-08-15
---

# 概念圖

[agreed] [event-loop](../concepts/event-loop.md) 每次從 queue 取一個 task；目前 task 結束前，後續 task 無法開始。

常見誤解見[長任務不會阻塞](../misconceptions/long-task-does-not-block.md)。
