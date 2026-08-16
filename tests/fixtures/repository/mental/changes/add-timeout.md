---
id: add-timeout
kind: change
authority: decision
status: pending
sources:
  - source-repo
prerequisites:
  - request-contract
updated_at: 2026-08-15
prediction_status: skipped
supersedes: []
superseded_by: []
status_history:
  - 2026-08-15:pending
---

# Add timeout

## Current Model

Routing is synchronous.

## Human Prediction and Model Gap

Skipped in this fixture. A timeout would introduce a new failure outcome.

## Proposed Model Delta

Add explicit timeout semantics to the request contract.

## Decision Manifest

Pending.

## Contracts and Invariants

Pending.

## Representative Scenarios

Pending.

## Failure Behavior

Pending.

## Verification Harness

None yet.

## Open Conflicts

[Timeout owner](../conflicts/timeout-owner.md) remains open.

## Human Decision

Pending. Do not implement.
