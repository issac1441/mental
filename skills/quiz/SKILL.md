---
name: quiz
description: Run a complete fixed-coverage assessment of a current change, session, artifact, registered source, or supplied topic. Use when the user wants a 10 to 20 item exam prepared as a whole rather than adaptive coaching; score objective answers without inventing mastery percentages or ability labels.
---

# Quiz

Assess whether the learner can reconstruct, predict, transfer, and bound the selected model.

## Input contract

`[scope] [items=12] [feedback=end|after-each] [format=mixed|open|mcq] [lens=<id>]`

- Scope accepts `current-change`, `current-session`, an artifact or source, or natural language.
- Items accepts 10–20 and defaults to 12.
- Feedback defaults to `end`; format defaults to `mixed`.

## Workflow

1. Read `../../references/methodology.md`, `../../references/output-style.md`, `../../references/artifact-contract.md`, `../../references/learning-workflow.md`, `../../references/source-safety.md`, and `../../references/writing-profile.md` relative to this skill.
2. Resolve omitted scope as current change → current session → ask. Use supplied sources, current mechanical artifacts, and active conceptual artifacts; clearly identify draft material when the user includes it.
3. Use the session Lens and `verify` Job. Do not persist the selection or label ability.
4. Build a coverage map first: anchor, relationships or mechanism, prediction, transfer, failure or counterexample, and consequential decisions or evidence gaps when relevant.
5. Generate the complete exam before collecting answers. Number every item and do not include answers, hints, or answer-revealing commentary.
6. With `feedback=end`, wait for the full submission and grade all answers. With `feedback=after-each`, keep the complete coverage fixed while presenting one numbered item at a time; suggest `$practice` for adaptive repair.
7. Report an objective score such as `9/12`, answer-specific evidence, demonstrated relationships, unresolved relationships, and follow-up. Do not convert it into mastery percentage, IQ-like label, or global ability.
8. Store personal answers only under `.mental/sessions/` and only with explicit persistence consent for the active assessment. Before any private write, run `python3 ../../scripts/ensure_private_state.py <workspace> --language <language>` with absolute paths resolved from this skill directory. If it refuses an unsafe path or ignore rule, stop the write and report it; never fall back to `mental/`. Preserve reusable questions as a conceptual `status: draft`, `kind: exercise` only when requested; never publish learner answers.

Use `$practice` for answer-adaptive coaching and `$learn` for prerequisite teaching.
