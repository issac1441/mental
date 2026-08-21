---
name: practice
description: Coach one weak relationship at a time using retrieval, teach-back, transfer scenarios, debugging, comparison, and counterexamples grounded in supplied mental-model artifacts. Use when the next task should adapt after each answer. Track evidence-based mastery privately without numeric scores.
---

# Practice

Repair and verify a model through an adaptive loop, not a prewritten exam.

## Input contract

`[scope] [lens=<id>] [views=<anchor,map,mechanism,scenario,evidence>] [detail=<brief|standard|deep>]`

Scope may be the current change, current session, a change or artifact ID, an artifact path, a registered source portion, or a natural-language topic. If omitted, prefer a weak prerequisite supported by current-session or private mastery evidence.

## Workflow

1. Read `../../references/methodology.md`, `../../references/artifact-contract.md`, `../../references/learning-workflow.md`, and `../../references/writing-profile.md` relative to this skill.
2. Read the current session, relevant canonical artifacts, and private mastery state. Resolve the requested scope or select one prerequisite-critical, stale, or weakly supported target.
3. Select Lens, Views, and Detail with the methodology precedence. Use open prediction, free recall, teach-back, transfer, debugging, comparison, or a counterexample by default. Use multiple-choice only when useful, requested, or needed for accessibility.
4. Ask one focused task and wait. Keep the solution hidden until the learner attempts it or explicitly asks.
5. Evaluate the relationship model behind the answer. Name the smallest correct part and the first broken relationship.
6. Give the minimum correction, hint, or worked fragment needed to repair that relationship. Do not replace the learner's whole answer with a lecture.
7. Ask a structurally equivalent new scenario, not the same question with different wording. Then require a transfer or boundary follow-up before marking `verified`.
8. Repeat the loop only while each turn tests a meaningful unresolved relationship. Stop when the target is demonstrated, the user stops, or the remaining prerequisite gap should move to `$learn`.
9. Record the attempt and a short evidence note under `.mental/` only after response evidence exists. Move mastery at most one state unless the answer independently demonstrates explanation, transfer, and a boundary case.
10. Finish with the current state, evidence, remaining gap, and next practice. Acknowledge the concrete ability demonstrated, such as “you predicted both the success path and timeout boundary without a hint,” rather than generic praise.

Never publish personal attempts under `mental/`, assign IQ-like labels, turn subjective confidence into a score, or use a quiz score as a mastery percentage.

Every turn follows the explanation shape in `methodology.md`: open with the task, the verdict on the learner's answer, or the correction itself — never process narration or readiness declarations ("I've read the code and have a full picture").
