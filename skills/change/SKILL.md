---
name: change
description: Help a person understand and decide a proposed repository change, option, plan, or TODO list before implementation. Use to expose model deltas, tradeoffs, hidden decisions, contracts, runtime effects, failure behavior, and reversibility; ask a useful human prediction when it can reveal a consequential model gap. Read-only unless recording is explicitly requested.
---

# Change

Help the human decide what the system should become before Plan Mode decides how to build it.

## Input contract

`<question-or-change-intent> [job=<decide|predict>] [lens=<id>] [record=<true|false>]`

Examples:

- `$change Add request timeouts without changing failure semantics.`
- `$change Tell me the actual effect of option A in the current plan.`
- `$change Help me predict who owns retry after this change. job=predict`

Accept advanced `views=` only when the user explicitly supplies it.

## Workflow

1. Read `../../references/methodology.md`, `../../references/output-style.md`, `../../references/artifact-contract.md`, `../../references/repository-workflow.md`, `../../references/source-safety.md`, and `../../references/writing-profile.md` relative to this skill.
2. Treat the request, current session, active plan, TODO list, current mechanical model, active conceptual model, open conflicts, and supplied evidence as inputs. Work directly from the repository when no model exists.
3. Select `intent`, `decision`, or `plan-interpretation` mode. Infer Job and Lens; do not print routine selection metadata.
4. Apply the repository workflow's semantic Decision Gate. Ignore diff size and implementation effort when deciding whether human approval matters.
5. If one human prediction can expose a consequential model gap and the user did not ask for a direct answer, ask it before revealing the evidence and stop for the response. Let the user answer or say `skip`. Never invent a human prediction.
6. After the response or skip, compare the human prediction with source or implementation evidence. Name and minimally repair the first model gap before asking for a decision.
7. Explain `Current Model → Proposed Model Delta`. Compare actual effects, ownership, contracts, invariants, state, failures, cost, and reversibility when material.
8. State the bounded Task Class and the available Model × Harness trust basis. Do not imply trust outside that task class.
9. Remain read-only by default. When recording is requested, write a `kind: change`, `authority: decision`, `status: pending` artifact from `../../assets/templates/change.md`. Create first-class conflict artifacts for unresolved mismatches.
10. End with the exact human choices and `Human Decision: pending`. Do not implement while pending.
11. After the human chooses `accepted` or `rejected`, update a recorded brief to the matching decision status and preserve alternatives. Create append-preserving decision-ledger entries from `../../assets/templates/decision.md` for consequential choices already in recording scope. Hand only an accepted delta to Plan Mode.

Keep the analysis smaller than the prospective diff. Use `$review` after implementation, optionally `$quiz`, then advanced `$sync` only when durable artifacts need refresh.
