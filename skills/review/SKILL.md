---
name: review
description: Explain and audit a repository diff, branch, commit, or completed implementation after the agent works. Use to reconstruct Before to After, reveal runtime effects and Decision Surprises, compare proposed versus actual choices, check contracts and failures, and assess the relevant Model × Harness × Task Class. Remains read-only.
---

# Review

Give the operator a model of what actually changed, then audit it.

## Input contract

`[target] [job=<verify|predict>] [lens=<id>]`

Target defaults to the current diff and may be a staged diff, commit, branch, ref, or named implementation. Accept advanced `views=` only when explicitly supplied.

## Workflow

1. Read `../../references/methodology.md`, `../../references/output-style.md`, `../../references/artifact-contract.md`, `../../references/repository-workflow.md`, `../../references/source-safety.md`, and `../../references/writing-profile.md` relative to this skill.
2. Resolve the target without mutation. Read relevant current mechanical artifacts, active conceptual artifacts, accepted decisions, open conflicts, change briefs, diff, tests, and runtime evidence.
3. Infer Lens and Job from the request and session unless the user supplied them. Use `verify` as the default Job and do not print routine selection metadata.
4. Reconstruct the `Actual Change Mental Model`: `Before → After`, runtime consequences, changed boundaries, ownership, contracts, invariants, failures, and operator predictions.
5. Compare proposed and actual decisions. Mark consequential choices first discovered after approval as `Decision Surprises`; do not hide them as implementation details.
6. Trace one representative success and failure path. Audit the relevant contracts, invariants, failure semantics, ownership, and verification harness.
7. State the bounded Task Class and assess Model × Harness coverage. Name the missing factor before recommending more autonomy.
8. When review coverage has a valid denominator, report Decision Surprise Rate as `post-approval consequential decisions / all consequential decisions discovered`. Otherwise report `N/A` with the missing coverage.
9. Offer one short prediction or teach-back prompt when it helps the operator absorb the change. Do not block the review or reveal its answer before an attempted response.
10. Return actionable findings ordered by model impact: broken contract or invariant; Decision Surprise; wrong failure behavior; open conflict; stale model; missing harness evidence; local implementation quality.

## Response contract

Return `Actual Change Mental Model`, `Proposed vs Actual`, `Findings`, `Decision Surprises`, `Trust Basis`, `Evidence`, and `Open Questions`. If there are no findings, say so and name residual evidence gaps.

Do not update artifacts, mastery, source files, code, or Git state. Suggest `$quiz` for bounded understanding assessment and advanced `$sync` for artifact refresh.
