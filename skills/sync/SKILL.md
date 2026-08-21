---
name: sync
description: Advanced maintenance skill that refreshes mechanical artifacts from registered sources and exposes drift in conceptual models, decisions, or conflicts. Use after source, code, test, or material changes when durable mental artifacts exist; mechanical refresh is automatic, while conceptual activation and human decisions retain their own gates.
---

# Sync

Refresh caches without choosing conceptual truth or human intent.

## Input contract

`[scope]`

Scope may be an artifact, registered source, or natural-language area. If omitted, use the durable artifacts implicated by the current session.

## Workflow

1. Read `../../references/methodology.md`, `../../references/output-style.md`, `../../references/artifact-contract.md`, `../../references/source-safety.md`, `../../references/writing-profile.md`, and the relevant mode workflow.
2. Re-read only registered sources. Classify material changes as unchanged, added, changed, removed, contradicted, or unverifiable.
3. Regenerate an affected `authority: mechanical` artifact only when its declared `refresh_basis` names registered sources at concrete revisions and its Evidence section makes stable regeneration possible. Update the basis and mark it `current` when complete. Otherwise leave content unchanged, mark it `stale`, expose a delta, and direct the user to `build` when the regeneration basis must be established or rebuilt. Never infer mechanical authority or a refresh basis from prose alone. Do not ask for human approval of mechanical facts.
4. Keep active conceptual artifacts byte-for-byte unchanged when new evidence would alter their model. Do not add a conflict link, known gap, timestamp, or status change to the active file before approval; record those proposed metadata changes in the draft delta and first-class open conflict instead. Apply them only if the human later accepts that conceptual update.
5. Preserve decision history. Never rewrite an accepted decision to match implementation drift; create a conflict or superseding decision proposal.
6. Use `mental/changes/sync-<date>-<scope>.md` only when a durable conceptual or decision delta needs a record. Pure mechanical refresh does not require a change brief.
7. Run `python3 ../../scripts/validate_workspace.py <workspace>` with absolute paths. Fix structural errors in newly created records or refreshed mechanical artifacts, including broken relative links, then run it again. Never make a protected conceptual or decision update merely to make validation pass. Report any remaining structural findings separately from semantic drift.
8. Report refreshed caches, stale artifacts, conceptual verification needed, decision gaps, and open conflicts. Ask only for decisions the human has standing to make.
