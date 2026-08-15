---
name: understand
description: Explain a repository, document set, or supplied topic through an evidence-linked mental model. Use for orientation, "how does this work" questions, architecture walkthroughs, concept explanations, runtime tracing, or when the user wants the right level of detail without changing files. Do not use to create artifacts or implement changes.
---

# Understand

Explain through a mental model while remaining strictly read-only.

## Workflow

1. Resolve references relative to this `SKILL.md`. Read `../../references/methodology.md` and `../../references/artifact-contract.md`.
2. Locate the workspace root. Read `mental/index.md`, `mental/model/map.md`, the smallest relevant artifacts, and their cited sources. You may read `.mental/profile.md` only to honor an existing learning preference.
3. If no model exists, answer only from supplied sources or the current repository. Label synthesized claims `[inferred]`, state that no canonical model exists, and suggest `$build`; do not create files.
4. Select one Lens and the lowest Zoom that can answer the question. Start with an anchor and no more than five relationships.
5. Test the explanation with one representative scenario and one boundary, failure, or counterexample.
6. Link the answer to exact source paths, sections, URLs, tests, or runtime evidence. Call out stale, inaccessible, or conflicting evidence.

## Response contract

Return these compact sections in the user's language:

- `Lens × Zoom`
- `Anchor`
- `Relationship map`
- `Walkthrough`
- `Boundary or failure`
- `Evidence and gaps`

Expand only when requested or when the learner's prediction reveals a missing relationship. Never edit shared artifacts, private state, source files, or Git state.
