---
name: change
description: Explain a proposed repository change, option, plan, or TODO list as a mental-model delta before implementation. Use to reveal actual effects, tradeoffs, boundaries, decisions, contracts, runtime behavior, and failures before Plan Mode or to clarify an existing plan. Read-only by default and never implements the change.
---

# Change

Help the human decide what the system should become before the host decides how to implement it.

## Input contract

Use a natural-language question or change intent. Optional controls are:

`lens=<id> views=<anchor,map,mechanism,scenario,evidence> detail=<brief|standard|deep> record=<true|false>`

Examples:

- `$change Add request timeouts without changing failure semantics.`
- `$change Tell me the actual effect of option A in the current plan.`
- `$change Explain which decisions remain in this TODO list. lens=pm detail=brief`

## Workflow

1. Read `../../references/methodology.md`, `../../references/artifact-contract.md`, `../../references/repository-workflow.md`, and `../../references/writing-profile.md` relative to this skill.
2. Treat the current request, current session, active Plan Mode result, TODO list, canonical model, and supplied evidence as valid inputs. If no model exists, create no code; label the analysis inferred, and save any `$build` recommendation for the closing line — never the opening.
3. Select Lens, Views, and Detail with the methodology precedence. Manual values win. Report the selection basis only in the closing line; never persist inferred preferences.
4. Auto-detect one mode:
   - `intent`: only a desired outcome exists;
   - `decision`: alternatives or a named option exist;
   - `plan-interpretation`: a plan or TODO list exists and needs conceptual translation.
   Never announce the detected mode in the response; the shape of the verdict carries it.
5. Write the `Prediction` for current behavior before proposing or interpreting the change. Trace at least one normal and one failure scenario. This ordering governs the analysis, not the response — the response still opens with the verdict.
6. Explain `Current Model → Proposed Model Delta`. In decision mode, compare the actual effects and tradeoffs of each relevant option. In plan-interpretation mode, map implementation steps to conceptual changes and expose pending decisions, hidden coupling, and reversibility.
7. Make consequential choices explicit in the Decision Manifest. Include effects on boundaries, ownership, contracts, invariants, data, user behavior, operations, failure semantics, cost, and verification when material.
8. Remain read-only by default. Write `mental/changes/<stable-change-id>.md` from `../../assets/templates/change.md` only when the user explicitly asks to record it, including `record=true` or natural wording such as “save this brief.” A recorded brief remains `status: draft`.
9. End with `Human Decision: pending`, state the exact choices that need a decision, and stop. Do not implement code while the decision is pending.
10. After explicit approval, hand the accepted delta to the host's Plan Mode. If a later plan option is unclear, run this skill again before revising the plan. After implementation, use `$review`, optionally `$quiz`, then `$sync`.

Keep the analysis smaller than the prospective diff. Local code details belong only where they are evidence for a model decision.

## Response contract

Return, in the user's language, following the explanation shape in `methodology.md`:

- The verdict first: the very first sentence of the response states a fact about the change — in `decision` mode the comparison verdict, in `intent` mode what the change actually does to the system, in `plan-interpretation` mode the most consequential thing the plan changes or leaves undecided. No warm-up of any kind — not process narration ("I've read the brief…"), not readiness declarations ("I have enough to analyze…", "Here is the analysis"), not mode or framework announcements ("this is a decision-mode comparison"), not artifact-status notes ("no canonical model exists"), not tool suggestions. A reader who stops after the first two to four sentences already knows which way the decision leans and why.
- Then the body — `Prediction`, the delta, traced scenarios, and the Decision Manifest — in whatever order the subject makes clearest, shallow to deep, every claim tied to exact files, tests, or quoted evidence.
- One closing line carrying all the machinery: the Lens/Views/Detail basis, evidence-scope caveats (for example, the analysis is inferred because no canonical model exists), and any `$build` or record suggestion — in plain words when the audience does not assume this tool's vocabulary.
- Last, `Human Decision: pending` with the exact pending choices, each named in one line that points into the Decision Manifest without restating its analysis.
