---
id: event-loop
kind: concept
status: canonical
sources:
  - source-event-loop
prerequisites: []
updated_at: 2026-08-15
---

# Event loop

[agreed] 要預測下一個 task 的開始時間，先判斷目前 task 何時結束。

## Boundary

[observed] 來源只描述單一 event loop，不足以推論多執行緒行為。
