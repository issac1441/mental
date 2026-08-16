---
name: build
description: Advanced persistence skill that saves reusable, evidence-linked mental artifacts after an explanation or learning interaction proves worth preserving. Use when the user explicitly wants a durable repository or learning model, mechanical cache, custom lens, decision record, or conflict record; it is not required before understand or learn.
---

# Build

Persist only the model that has earned its maintenance cost.

## Input contract

`[source-or-scope] [mode=repository|learning|hybrid] [language=<BCP-47-tag>]`

The current repository is the default source when invoked from it. Otherwise use only supplied files, text, or URLs.

## Workflow

1. Read `../../references/methodology.md`, `../../references/output-style.md`, `../../references/artifact-contract.md`, `../../references/source-safety.md`, and `../../references/writing-profile.md`. Read the relevant repository or learning workflow.
2. Establish the source boundary. Fetch only user-supplied URLs and do not expand research scope.
3. If `mental/` is absent, run `python3 ../../scripts/scaffold_workspace.py <workspace> --mode <mode> --language <language>` using absolute paths resolved from this skill directory.
4. Inventory evidence and register stable source IDs with revision and access status.
5. Persist a source-derived map, concept, contract, or scenario as `authority: mechanical` only when it can be stably regenerated from registered evidence. Record `refresh_basis` as `<source-id>@<revision>` and an `Evidence` section. Use `status: current` only when both are concrete and complete; otherwise use `stale` and expose the missing basis.
6. Persist interpretive boundaries, teaching structures, custom lenses, or durable explanations as `authority: conceptual`, `status: draft`. Add empty activation fields from the template. Activate only after recording a non-placeholder verification basis, checked success and failure or boundary predictions, known gaps, and linked conflicts; user assent alone is not evidence.
7. Persist consequential choices only as `authority: decision` artifacts when recording is requested. Preserve options, owner, surfaced timing, reversibility, and history.
8. Create a first-class `kind: conflict`, `status: open` artifact for every unresolved material mismatch. Never bury it in prose or rewrite one side.
9. Build only artifacts that improve a future prediction, decision, repair, or source-navigation task. Do not target complete wiki coverage.
10. Run `python3 ../../scripts/validate_workspace.py <workspace>`. Fix structural errors without inventing evidence or resolving conflicts.
11. Present mechanical refresh results, conceptual drafts with verification requirements, recorded decisions, open conflicts, and maintenance cost. Stop without implementing repository code.

Use the conceptual activation gate from the methodology. Never overwrite decision history or downgrade an active artifact silently.
