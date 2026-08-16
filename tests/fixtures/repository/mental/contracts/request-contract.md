---
id: request-contract
kind: contract
authority: mechanical
status: current
sources:
  - source-repo
prerequisites:
  - request-routing
updated_at: 2026-08-15
---

# Request contract

Routing always returns a two-item `(status, body)` pair.

Unknown paths return `(404, "not found")`.
