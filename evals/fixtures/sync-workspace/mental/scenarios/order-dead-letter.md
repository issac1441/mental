---
id: order-dead-letter
kind: scenario
status: canonical
sources:
  - src-code
prerequisites: []
updated_at: 2026-08-05
---

# Scenario: order dead-lettered

[observed] A carrier outage makes every dispatch attempt fail with a retryable error. After the final attempt, dispatch raises DispatchExhausted (src/orderflow/dispatch.py).
[observed] The pipeline catches DispatchExhausted, releases the reservation — restoring the reserved quantities to catalog stock — and appends the order id and reason to the dead-letter queue (src/orderflow/pipeline.py).
[observed] The returned Receipt has status `dead_lettered`; the caller sees no exception (src/orderflow/pipeline.py).
