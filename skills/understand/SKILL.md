---
name: understand
description: Explain a repository, document set, current session, or supplied topic immediately through the smallest evidence-linked mental model. Use as mental's first entry point for orientation, mechanisms, architecture, runtime tracing, decisions, or confusion; it works before any mental artifacts exist and remains strictly read-only.
---

# Understand

Give useful understanding now. Do not require artifact setup first.

## Input contract

`<question-or-scope> [job=<orient|decide|predict|verify|repair>] [lens=<built-in-or-custom-id>]`

Infer Job and Lens from the request and session. Accept `views=<anchor,map,mechanism,scenario,evidence>` only as an advanced override; do not require it or advertise it as prerequisite knowledge.

## Workflow

1. Read `../../references/methodology.md`, `../../references/output-style.md`, `../../references/artifact-contract.md`, `../../references/source-safety.md`, and `../../references/writing-profile.md` relative to this skill.
2. Read the current request and relevant session history, including plans, TODOs, corrections, answers, and decisions. Use exposed host memory only as a weak signal.
3. Inspect the smallest relevant supplied source or current repository evidence. When present, also read current mechanical artifacts, active conceptual artifacts, open conflicts, and relevant private profile or mastery state.
4. If no mental workspace exists, answer directly from supplied evidence. Do not stop to request `$build` and do not create files.
5. Select Job and Lens with the methodology precedence. Choose internal Views and response density automatically. Do not print routine selection metadata or a closing selection recap. Disclose a selection only when the user chose it, or when uncertainty would materially change the answer and the user can correct it.
6. Lead with the changed prediction or answer. Build only the anchor, relationships, mechanism, scenario, evidence, or boundary needed by the Job.
7. Separate evidence from interpretation in plain language. Link exact source paths, sections, URLs, tests, or runtime observations. Surface open conflicts instead of reconciling them silently.
8. When the same model will likely matter again, offer `$build` as an optional way to persist the useful parts. Do not turn persistence into a prerequisite or write without consent.

## Response contract

Return the answer in the user's language, followed by evidence and gaps when material. Include one boundary, failure, or counterexample when it prevents overgeneralization. Never edit shared artifacts, private state, source files, or Git state.
