---
id: route-contract-decision
kind: decision
authority: decision
status: accepted
sources:
  - source-repo
prerequisites:
  - request-contract
updated_at: 2026-08-15
decision_owner: human
surfaced: pre-approval
consequential: true
reversibility: costly
---

# Preserve exact route matching

## Options considered

- Exact matching.
- Prefix matching.

## Decision

Keep exact matching so `/healthy` remains not found.

## Status history

- 2026-08-15: accepted by the fixture owner.
