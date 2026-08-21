# Repository workflow

## Smallest useful repository state

Start by answering the user's question from the repository. Do not require artifacts first.

Persist only what will pay for future understanding or accountability:

- regenerable mechanical maps, contracts, and scenarios that shorten later inspection;
- active conceptual models with a recorded verification basis;
- consequential decisions and rejected alternatives;
- open conflicts that require evidence or a decision.

Do not build a complete repository wiki. `concepts/`, `scenarios/`, and `contracts/` are caches or focused models, not coverage targets.

## Decision gate

Put a change through the human decision gate when it materially affects any of these semantics:

- external behavior;
- responsibility or ownership boundary;
- contract semantics or invariant;
- state model;
- retry, idempotency, transaction, or concurrency behavior;
- security boundary;
- data ownership or lifecycle;
- failure semantics;
- cross-component dependency;
- costly or irreversible operational behavior.

Do not use lines changed, file count, or implementation effort as the gate criterion.

## Change modes

Detect one mode:

- **intent**: only an outcome exists; expose the proposed model delta and decisions.
- **decision**: alternatives exist; compare effects, failure behavior, and reversibility.
- **plan-interpretation**: a plan or TODO list exists; translate steps into model changes and hidden decisions.

The natural-language question constrains scope. A request such as “Tell me the actual effect of option A” asks for a direct explanation; do not force a prediction exercise before answering it.

## Human-first prediction

For a change that passes the Decision Gate, ask one high-information prediction before revealing the answer only when the response can change the decision or expose a model relationship that needs repair. Ask about an observable outcome, owner, invariant, or failure path. Let the user answer or say `skip`. When waiting, return only that prompt; do not also reveal the evidence, complete the model delta, or emit a pending-decision manifest.

After the response:

1. show implementation or source evidence;
2. compare the human prediction with the evidence;
3. name the smallest model gap;
4. repair that relationship before asking for a decision.

Do not fabricate a human prediction. If the user requests a direct answer, the change does not pass the Decision Gate, or the prediction would add ceremony without changing the decision or repair, answer directly.

When a change brief is already in recording scope, record only
`prediction_status: attempted|skipped|not-applicable` for the invocation. `skip`
applies only to the current prompt and is not a persistent preference. Keep the
answer in conversation unless the user explicitly asks to store it; showing the
evidence in the same turn would defeat the prediction gate.

## Change analysis

Use these sections when material:

1. `Mode and Question`
2. `Task Class and Trust Basis`
3. `Current Model`
4. `Human Prediction and Model Gap`
5. `Proposed Model Delta`
6. `Actual Effects and Tradeoffs`
7. `Decision Manifest`
8. `Contracts and Invariants`
9. `Representative Scenarios`
10. `Failure Behavior`
11. `Verification Harness`
12. `Open Conflicts`
13. `Human Decision`

Analysis is read-only by default. Record it only when requested. A recorded `kind: change` uses decision authority and starts `pending`. After a decision, update it to `accepted` or `rejected`, preserve alternatives, and create decision-ledger entries for consequential choices.
Append every decision-state transition to `status_history`. When one record
replaces another, link both directions with `supersedes` and `superseded_by`
instead of rewriting the older entry.

## Model-aware review

Explain the actual change before findings:

1. reconstruct `Before → After` from the diff and evidence;
2. state runtime effects and updated operator predictions;
3. compare proposed and actual decisions;
4. identify consequential choices surfaced only after approval as Decision Surprises;
5. trace one success and one failure path;
6. assess the relevant Model × Harness × Task Class unit;
7. report Decision Surprise Rate only when review coverage supplies a valid denominator.

Order findings by model impact: broken contract/invariant, Decision Surprise, wrong failure behavior, open conflict, stale model, missing harness evidence, then local implementation quality.
