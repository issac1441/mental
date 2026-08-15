# Repository workflow

## Canonical repository model

Build the smallest useful set:

- `model/map.md`: system boundary and relationships;
- `architecture.md`: structural view when multiple components matter;
- `concepts/`: capabilities or components worth naming;
- `contracts/`: externally visible behavior, invariants, and failure semantics;
- `scenarios/`: representative runtime paths;
- `decisions/`: rationale for consequential choices;
- `changes/`: proposed or accepted model deltas.

Use code, tests, configuration, and runtime evidence as implementation truth. Use canonical artifacts as agreed conceptual truth.

## Change brief

Write a change brief with these headings:

1. `Current Model`
2. `Prediction`
3. `Proposed Model Delta`
4. `Decision Manifest`
5. `Contracts and Invariants`
6. `Representative Scenarios`
7. `Failure Behavior`
8. `Verification Evidence`
9. `Surprises and Conflicts`
10. `Human Decision`

Before approval, `Human Decision` is `pending` and the brief stays `draft`. Do not implement the change while the decision is pending.

## Model-aware review

Review in this order:

1. Identify the intended model delta.
2. Compare changed behavior with canonical contracts and invariants.
3. Trace one normal and one failure scenario.
4. Check whether decisions were made implicitly.
5. Compare predicted and observed outcomes.
6. Report decision surprises and evidence gaps before stylistic findings.

Use finding severity based on model impact: broken contract/invariant, unapproved decision, incorrect failure behavior, stale model, then local implementation quality.
