---
name: review
description: Explain and audit a repository diff, branch, commit, or implementation against its canonical mental model and approved change brief. Use after implementation to show Before to After, runtime consequences, proposed-versus-actual surprises, broken contracts, hidden decisions, failure behavior, model drift, and missing evidence. Remains read-only.
---

# Review

Give the operator a mental model of what actually changed, then audit whether it is correct. Remain read-only.

## Workflow

1. Read `../../references/methodology.md`, `../../references/artifact-contract.md`, `../../references/repository-workflow.md`, and `../../references/writing-profile.md` relative to this skill.
2. Resolve the review target without mutating it. Read the relevant canonical artifacts, approved change brief, diff, tests, and runtime evidence.
3. Reconstruct the `Actual Change Mental Model` first:
   - `Before → After`;
   - actual model delta;
   - runtime consequences;
   - new or changed boundaries, ownership, contracts, invariants, and failure behavior;
   - predictions the operator should now update.
4. Compare the proposed delta with the actual delta. Label omissions, additional behavior, and changed decisions as `Decision Surprises`; if no approved brief exists, label consequential implementation choices as potentially hidden decisions.
5. Trace one representative success path and one failure path through the changed behavior.
6. Audit the implementation against canonical contracts, invariants, failure semantics, ownership, prerequisites, model status, and verification evidence.
7. Return actionable findings ordered by model impact: broken contract or invariant; unapproved or hidden decision; incorrect failure behavior; stale or contradictory model; missing verification evidence; local implementation quality.

## Response contract

Open with two or three plain-language sentences stating what actually changed and whether it matches what was agreed — a reader who stops there should already have the verdict. Then return `Actual Change Mental Model`, `Proposed vs Actual`, `Findings`, `Decision Surprises`, `Evidence`, and `Open Questions`. If there are no findings, say so and name residual evidence gaps.

Do not update artifacts, mastery, source files, code, or Git state. Suggest `$quiz` when the operator wants to verify their own understanding and `$sync` when implementation evidence makes the canonical model stale.
