---
id: ticket-routing
kind: concept
status: canonical
sources:
  - src-code
prerequisites: []
updated_at: 2026-08-10
---

# Ticket routing

[inferred] Routing hashes the customer id to pick an agent pool.
[inferred] Collisions fall back to round-robin assignment.
[inferred] VIP customers always bypass triage.
