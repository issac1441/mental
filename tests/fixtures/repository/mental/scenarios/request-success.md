---
id: request-success
kind: scenario
status: canonical
sources:
  - source-repo
prerequisites:
  - request-routing
updated_at: 2026-08-15
---

# Health request

[observed] Input `/health` returns `(200, "ok")`.

## Failure boundary

[observed] `/healthy` does not prefix-match and returns not found.
