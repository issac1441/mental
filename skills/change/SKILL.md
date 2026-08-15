---
name: change
description: Design a repository change as an explicit mental-model delta before implementation. Use for features, fixes, refactors, migrations, or architecture work where a human should review boundaries, decisions, contracts, invariants, runtime scenarios, failure behavior, and predictions before code changes. Do not use for general learning topics.
---

# Change

Make the human review the decision and model delta, not a future pile of code.

## Workflow

1. Read `../../references/methodology.md`, `../../references/artifact-contract.md`, and `../../references/repository-workflow.md` relative to this skill.
2. Orient to canonical artifacts and inspect the smallest implementation evidence needed to test them. If no model exists, create no code; recommend `$build` or explicitly frame the brief as inferred.
3. Write the `Prediction` for current behavior before designing the change. Trace at least one normal and one failure scenario.
4. Write a draft `mental/changes/<stable-change-id>.md` using `../../assets/templates/change.md` as the structure. Include the exact headings required by the repository workflow.
5. Make every consequential choice explicit in the Decision Manifest. Include alternatives when they materially affect boundaries, contracts, invariants, data ownership, or failure semantics.
6. End with `Human Decision: pending`, summarize the approval choices, and stop. Do not implement code while the decision is pending.
7. If the user explicitly approves in a later turn, hand the accepted brief to the host agent for implementation. During implementation, verify the predictions and record surprises rather than rewriting the brief to look prescient.
8. After verification, use `$sync` to reconcile accepted model changes. A passing test does not itself promote a conceptual claim to canonical.

Keep the brief smaller than the prospective diff. Omit local code details unless they are evidence for a model decision.
