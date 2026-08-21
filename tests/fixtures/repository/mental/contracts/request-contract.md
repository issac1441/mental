---
id: request-contract
kind: contract
status: canonical
sources:
  - source-repo
prerequisites:
  - request-routing
updated_at: 2026-08-15
---

# Request contract

[agreed] Routing always returns a two-item `(status, body)` pair.

[observed] Unknown paths return `(404, "not found")`.
