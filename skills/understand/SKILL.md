---
name: understand
description: Explain a repository, document set, or supplied topic through an evidence-linked mental model. Use for orientation, architecture walkthroughs, concept explanations, runtime tracing, or any question that should adapt to the current session, a selected role, requested views, and desired detail without changing files.
---

# Understand

Explain through a mental model while remaining strictly read-only. The goal is transfer: after reading, the person can predict what the system does and why. Lens, Views, and Detail decide what the answer contains; the subject itself decides how the answer reads. Optimize for the reader, never for displaying the framework.

## Input contract

Use natural language, optionally followed by:

`lens=<built-in-or-artifact-id> views=<anchor,map,mechanism,scenario,evidence> detail=<brief|standard|deep>`

Views are a comma-separated multi-selection. Manual values override inference. Built-in lenses are `general`, `engineer`, `architect`, `pm`, `operator`, `student`, and `researcher`; a project may add `mental/lenses/*.md`.

## Workflow

1. Resolve references relative to this `SKILL.md`. Read `../../references/methodology.md`, `../../references/artifact-contract.md`, and `../../references/writing-profile.md`.
2. Read the current request and relevant current session history, including active plans, TODOs, earlier corrections, and demonstrated goals. Read host memory only if the host exposes it; treat it as a weak signal, never as authoritative user state.
3. Locate the workspace root. Read `mental/index.md`, `mental/model/map.md`, relevant custom lens artifacts, the smallest relevant canonical artifacts, and their cited sources. Read `.mental/profile.md` and `.mental/mastery.json` only when they are relevant to the request.
4. If no canonical model exists, answer from supplied sources or the current repository. Read enough of the real code or source to explain causally — a correct answer grounded in the actual files beats a cautious summary of file names. Mention once that no canonical model exists and suggest `$build`; do not create files.
5. Select Lens, Views, and Detail using this precedence: manual override → explicit current goal → current session evidence → private profile or mastery → exposed host memory as a weak signal → scope default. Repository questions default to `engineer`; general learning questions default to `student`.
6. Do not infer ability from grammar, speed, identity, confidence, or protected traits. Never persist an inferred Lens, View, Detail, or preference unless the user explicitly asks.
7. Compose the explanation for transfer, following the explanation shape in `methodology.md`:
   - Open with the direct answer: two to four sentences that answer the question correctly on their own. A reader who stops there should leave with a true, if coarse, model.
   - Organize the body by the subject's own structure — follow the request through the system for a trace, group by component for architecture, follow the causal chain for a "why". Never use View names or framework vocabulary as section headers; the selected Views are a private completeness checklist, not an outline.
   - Order content shallow to deep so each section refines the previous one and the reader can stop at any point with a correct partial model.
   - Ground every abstraction: tie claims to exact paths such as `src/router.py:42`, tests, commands, or quoted source, and weave one concrete scenario into the narrative instead of appending it as ceremony.
   - Include a boundary, failure, or counterexample when it prevents overgeneralization.
   - Use the shortest text that supports prediction at the selected Detail; offer the next layer of depth instead of delivering everything.
8. Reserve `[inferred]` and `[conflict]` labels for claims whose evidence is genuinely uncertain or contradictory; routine observations need only their citation. Call out stale, inaccessible, or conflicting evidence.

## Response contract

Return, in the user's language:

- the direct answer first, then a body organized by the subject's own structure;
- the material boundary or failure, woven in or as a short closing note;
- a compact `Sources and gaps` footer listing the exact paths, sections, URLs, tests, or runtime evidence behind the answer, plus open uncertainties;
- one final `Context` line naming the Lens, selected Views, Detail, and the selection basis in one clause, so the reader can steer the next answer — for example `Context: engineer lens · map,mechanism,scenario · standard — from the current debugging goal; adjust with lens= views= detail=`.

Expand when requested or when a prediction reveals a missing relationship. Never edit shared artifacts, private state, source files, or Git state.
