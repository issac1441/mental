---
id: model-map
kind: map
authority: mechanical
status: current
sources:
  - source-repo
prerequisites: []
updated_at: 2026-08-15
refresh_basis:
  - source-repo@2026-08-15
---

# Model map

A request path enters [request-routing](../concepts/request-routing.md), which returns exactly one response pair governed by the [request contract](../contracts/request-contract.md).

The [request-success scenario](../scenarios/request-success.md) demonstrates the health path.

## Evidence

- `source-repo`: `src/router.py`
