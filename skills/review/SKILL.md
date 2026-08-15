---
name: review
description: Review a repository diff, branch, commit, or implementation against its canonical mental model and approved change brief. Use to find broken contracts, violated invariants, implicit decisions, incorrect failure behavior, model drift, missing evidence, or decision surprises. Remain read-only unless the user separately asks to apply fixes.
---

# Review

Review model impact before local style. Remain read-only.

## Workflow

1. Read `../../references/methodology.md`, `../../references/artifact-contract.md`, and `../../references/repository-workflow.md` relative to this skill.
2. Resolve the review target without mutating it. Read the relevant canonical artifacts, approved change brief, diff, tests, and runtime evidence.
3. Reconstruct the intended model delta. If no approved brief exists, label consequential implementation choices as potentially implicit decisions.
4. Trace one representative success path and one failure path through the changed behavior.
5. Compare predicted with observed behavior, including contracts, invariants, boundaries, ownership, prerequisites, and failure semantics.
6. Return actionable findings ordered by model impact:
   - broken contract or invariant;
   - unapproved or hidden decision;
   - incorrect failure behavior;
   - stale or contradictory model;
   - missing verification evidence;
   - local implementation quality.
7. Include `Model Delta`, `Decision Surprises`, `Evidence`, and `Open Questions` after findings. If there are no findings, say so and name residual evidence gaps.

Do not update artifacts, mastery, source files, code, or Git state. Suggest `$sync` when implementation evidence makes the canonical model stale.
