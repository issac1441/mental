---
id: request-success
kind: scenario
authority: mechanical
status: current
sources:
  - source-repo
prerequisites:
  - request-routing
updated_at: 2026-08-15
---

# Health request

Input `/health` returns `(200, "ok")`.

## Failure boundary

`/healthy` does not prefix-match and returns not found.
