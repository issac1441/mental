# Repository workflow

## Canonical repository model

Build the smallest useful set:

- `model/map.md`: system boundary and relationships;
- `architecture.md`: structural view when multiple components matter;
- `concepts/`: capabilities or components worth naming;
- `contracts/`: externally visible behavior, invariants, and failure semantics;
- `scenarios/`: representative runtime paths;
- `decisions/`: rationale for consequential choices;
- `changes/`: explicitly recorded proposed or accepted model deltas.

Use code, tests, configuration, and runtime evidence as implementation truth. Use canonical artifacts as agreed conceptual truth.

## When to use change

The preferred order is `change → human decision → Plan Mode → implementation`. `change` establishes what the system should become; Plan Mode establishes how to perform the accepted work.

`change` also works after a plan exists. Treat the active plan, a session TODO list, or pending decision list as valid input when the user wants to understand an option or its tradeoffs. If analysis changes the decision, revise the plan afterward.

Detect one of three modes:

- **intent**: only a desired outcome exists; produce a proposed model delta and open decisions;
- **decision**: alternatives such as A/B exist; compare their actual effects on behavior, boundaries, ownership, contracts, failures, cost, and reversibility;
- **plan-interpretation**: a plan or TODO list exists; translate steps into conceptual changes and identify pending decisions or hidden coupling.

The user's natural-language question is primary input. A request such as “Tell me the actual effect of option A in the current plan” should constrain both the scope and the comparison.

## Change analysis

Use these sections in conversation or in a recorded brief:

1. `Mode and Question`
2. `Current Model`
3. `Prediction`
4. `Proposed Model Delta`
5. `Actual Effects and Tradeoffs`
6. `Decision Manifest`
7. `Contracts and Invariants`
8. `Representative Scenarios`
9. `Failure Behavior`
10. `Verification Evidence`
11. `Surprises and Conflicts`
12. `Human Decision`

Analysis is read-only by default. Create `mental/changes/<id>.md` only when the user explicitly asks to record it, including natural wording such as “save this change brief” or an explicit `record=true`. Before approval, `Human Decision` is `pending` and any recorded brief stays `draft`. Do not implement while the decision is pending.

## Model-aware review

Explain the actual change before presenting audit findings:

1. Reconstruct `Before → After` from the diff and evidence.
2. State the actual model delta and runtime consequences.
3. Name new or changed boundaries, contracts, invariants, ownership, failures, and operator predictions.
4. Compare the proposed delta with the actual delta and expose surprises.
5. Audit contracts, invariants, failure paths, hidden decisions, model drift, and missing evidence.
6. Report findings before local style observations.

Use finding severity based on model impact: broken contract/invariant, unapproved decision, incorrect failure behavior, stale model, missing verification evidence, then local implementation quality.
