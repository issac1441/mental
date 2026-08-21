---
name: quiz
description: Run a complete bounded assessment of a current change, session, artifact, registered source, or supplied topic. Use when the user wants a 10 to 20 item exam delivered as a whole rather than adaptive coaching. Score objective answers without inventing mastery percentages or permanent ability labels.
---

# Quiz

Assess whether the learner can reconstruct, predict, transfer, and bound the selected mental model.

## Input contract

`[scope] [items=12] [feedback=end|after-each] [format=mixed|open|mcq]`

- `scope` accepts `current-change`, `current-session`, a change ID, artifact ID or path, a portion of a registered source, or a natural-language topic.
- `items` accepts 10–20 and defaults to 12.
- `feedback` defaults to `end`.
- `format` defaults to `mixed`; `open` avoids multiple-choice and `mcq` requests it.

Examples:

- `$quiz current-change items=12 feedback=end format=mixed`
- `$quiz mental/concepts/event-loop.md items=10 format=open`
- `$quiz Test whether I understand the timeout decisions in this session.`

## Workflow

1. Read `../../references/methodology.md`, `../../references/artifact-contract.md`, `../../references/learning-workflow.md`, and `../../references/writing-profile.md` relative to this skill.
2. Resolve omitted scope in this order: current change → current session → ask the user. Use only canonical artifacts and supplied or registered sources unless the user explicitly allows clearly labeled draft material.
3. Select Lens, Views, and Detail with the methodology precedence so wording and emphasis fit the current goal. Do not use this selection to label ability or persist a profile.
4. Build a coverage map before writing questions. Include the anchor, important relationships or mechanisms, at least one prediction, one transfer, one failure or counterexample, and consequential decisions or evidence gaps when relevant.
5. Generate the complete exam first. Number every item, state the requested format and scope, and do not include answers, hints, or answer-revealing commentary.
6. With `feedback=end`, wait for the full submission, then grade all answers. With `feedback=after-each`, still define the complete exam first, but present and evaluate one numbered item at a time without changing the remaining coverage merely to chase one mistake; suggest `$practice` if adaptive repair is needed.
7. Report an objective score such as `9/12`, answer-specific evidence, demonstrated relationships, unresolved relationships, and recommended follow-up. Do not convert the score into a mastery percentage, IQ-like label, or global ability claim.
8. Store personal answers and results only under `.mental/sessions/` and only when persistence is requested or already in scope. If the user asks to preserve reusable questions, write a `status: draft`, `kind: exercise` artifact under `mental/exercises/`; never publish the learner's answers there.

Use `$practice` when the user wants answer-by-answer adaptive coaching. Use `$learn` when the assessment exposes a prerequisite gap that needs teaching.
