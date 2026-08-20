---
id: map
kind: map
status: canonical
sources:
  - src-code
prerequisites: []
updated_at: 2026-08-05
---

# System map

[observed] An order flows ingest → inventory.reserve → pricing.price → dispatch.send, producing a Receipt (src/orderflow/pipeline.py).
[observed] The reservation is the pricing input: totals are computed from the captured unit-price snapshot, never from the raw order (src/orderflow/pricing.py).
[observed] When dispatch exhausts its retries, the pipeline releases the reservation and appends the order to the dead-letter queue (src/orderflow/pipeline.py).
[observed] All catalog and reservation state lives in a VersionedStore with optimistic concurrency (src/orderflow/store.py).

Related: [dispatch retry](../concepts/dispatch-retry.md), [pricing totals](../concepts/pricing-totals.md), [reservation](../concepts/reservation.md).
