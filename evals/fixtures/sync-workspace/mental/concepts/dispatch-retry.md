---
id: dispatch-retry
kind: concept
status: canonical
sources:
  - src-code
prerequisites: []
updated_at: 2026-08-05
---

# Dispatch retry

[observed] Dispatch makes at most 3 total attempts per order; the cap is `config.MAX_DISPATCH_ATTEMPTS = 3` (src/orderflow/config.py).
[observed] The delay before attempt n (n ≥ 2) is `BASE_RETRY_DELAY_MS * 2^(n-2)` milliseconds plus a deterministic jitter derived from the CRC32 of the order id (src/orderflow/dispatch.py).
[agreed] When every attempt fails, dispatch raises DispatchExhausted; the pipeline then releases the reservation's stock and dead-letters the order — exhaustion never strands reserved stock (src/orderflow/pipeline.py).
