---
id: event-loop
kind: concept
authority: conceptual
status: active
sources:
  - source-event-loop
prerequisites: []
updated_at: 2026-08-15
---

# Event loop

要預測下一個 task 的開始時間，先判斷目前 task 何時結束。

## Boundary

來源只描述單一 event loop，不足以推論多執行緒行為。

## Verification basis

- `source-event-loop` 描述 queue 與單一 task 執行順序。
- Fixture 的 success 與 boundary prediction 已檢查。
