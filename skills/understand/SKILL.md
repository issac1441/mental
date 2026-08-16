---
name: understand
description: Explain a repository, document set, or supplied topic through an evidence-linked mental model. Use for orientation, architecture walkthroughs, concept explanations, runtime tracing, or any question that should adapt to the current session, a selected role, requested views, and desired detail without changing files.
---

# Understand

Explain through a mental model while remaining strictly read-only.

## Input contract

Use natural language, optionally followed by:

`lens=<built-in-or-artifact-id> views=<anchor,map,mechanism,scenario,evidence> detail=<brief|standard|deep>`

Views are a comma-separated multi-selection. Manual values override inference. Built-in lenses are `general`, `engineer`, `architect`, `pm`, `operator`, `student`, and `researcher`; a project may add `mental/lenses/*.md`.

## Workflow

1. Resolve references relative to this `SKILL.md`. Read `../../references/methodology.md`, `../../references/artifact-contract.md`, `../../references/source-safety.md`, and `../../references/writing-profile.md`.
2. Read the current request and relevant current session history, including active plans, TODOs, earlier corrections, and demonstrated goals. Read host memory only if the host exposes it; treat it as a weak signal, never as authoritative user state.
3. Locate the workspace root. Read `mental/index.md`, `mental/model/map.md`, relevant custom lens artifacts, the smallest relevant canonical artifacts, and their cited sources. Read `.mental/profile.md` and `.mental/mastery.json` only when they are relevant to the request.
4. If no canonical model exists, answer only from supplied sources or the current repository. Label synthesis `[inferred]`, state that no canonical model exists, and suggest `$build`; do not create files.
5. Select Lens, Views, and Detail using this precedence: manual override → explicit current goal → current session evidence → private profile or mastery → exposed host memory as a weak signal → scope default. Repository questions default to `engineer`; general learning questions default to `student`.
6. Do not infer ability from grammar, speed, identity, confidence, or protected traits. Never persist an inferred Lens, View, Detail, or preference unless the user explicitly asks.
7. Build only the requested semantic slices. Keep an `anchor` compact, a `map` to the relationships needed for prediction, a `mechanism` causal, a `scenario` concrete, and `evidence` traceable.
8. Include a boundary, failure, or counterexample when it prevents overgeneralization. Link claims to exact source paths, sections, URLs, tests, or runtime evidence. Call out stale, inaccessible, or conflicting evidence.

## Response contract

Return, in the user's language:

- `Context`: Lens, selected Views, Detail, and one concise sentence explaining the selection basis and uncertainty;
- the selected View sections only;
- `Boundary or failure` when material;
- `Evidence and gaps`.

Expand when requested or when a prediction reveals a missing relationship. Never edit shared artifacts, private state, source files, or Git state.
