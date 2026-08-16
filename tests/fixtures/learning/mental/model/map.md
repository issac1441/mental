---
id: model-map
kind: map
authority: mechanical
status: current
sources:
  - source-event-loop
prerequisites: []
updated_at: 2026-08-15
refresh_basis:
  - source-event-loop@2026-08-15
---

# 概念圖

[event-loop](../concepts/event-loop.md) 每次從 queue 取一個 task；目前 task 結束前，後續 task 無法開始。

常見誤解見[長任務不會阻塞](../misconceptions/long-task-does-not-block.md)。

## Evidence

- `source-event-loop`: `materials/event-loop.md`
