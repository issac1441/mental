---
name: practice
description: Repair and verify one weak mental-model relationship at a time through retrieval, prediction, teach-back, transfer, debugging, and counterexamples. Use when each next task should adapt to the learner's last answer; persist evidence-based mastery privately only with explicit session consent.
---

# Practice

Run an adaptive repair loop, not a prewritten exam.

## Input contract

`[scope] [lens=<id>]`

Scope may be the current change, current session, an artifact or source, or a natural-language topic. If omitted, choose one prerequisite-critical gap supported by session or private mastery evidence.

## Workflow

1. Read `../../references/methodology.md`, `../../references/output-style.md`, `../../references/artifact-contract.md`, `../../references/learning-workflow.md`, `../../references/source-safety.md`, and `../../references/writing-profile.md` relative to this skill.
2. Read relevant sources, current mechanical or active conceptual artifacts, the current session, and private mastery state when relevant.
3. Use the session Lens and `repair` Job. Choose the task form automatically; prefer open prediction, recall, teach-back, transfer, debugging, comparison, or counterexample.
4. Ask one focused task and wait. Keep the solution hidden until the learner attempts it or asks.
5. Name the smallest correct part and first broken relationship in the response.
6. Give the minimum correction, hint, or worked fragment needed to repair that relationship.
7. Ask a structurally equivalent new scenario. Require independent explanation, transfer, and a boundary or counterexample before marking `verified`.
8. Stop when the target is demonstrated, the user stops, or a prerequisite gap should move to `$learn`.
9. Persist the attempt and short evidence under `.mental/` only after response evidence and explicit persistence consent for the active practice session.
10. Finish with demonstrated capability, remaining gap, and next practice. Do not use generic praise or numeric mastery percentages.

Never publish personal attempts under `mental/`, infer global ability, or use a quiz score as mastery.
