---
id: reservation
kind: concept
status: canonical
sources:
  - src-code
prerequisites: []
updated_at: 2026-08-05
---

# Reservation

[observed] A reservation freezes stock and unit prices for an order; its lifetime is governed by `config.RESERVATION_TTL_SECONDS = 120` (src/orderflow/config.py).
[observed] reserve() is idempotent per order_id: re-processing an order whose reservation is still live returns the existing reservation unchanged (src/orderflow/inventory.py).
[observed] An expired reservation is rebuilt from the current catalog and flagged `reprice_required`, so the pipeline knows totals must be recomputed (src/orderflow/inventory.py).
[observed] release() returns reserved stock to the catalog and deletes the reservation; releasing an unknown order id is a no-op (src/orderflow/inventory.py).
