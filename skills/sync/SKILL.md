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
3. Regenerate affected `authority: mechanical` artifacts and mark them `current` when evidence is complete. Mark them `stale` when refresh cannot complete. Do not ask for human approval of mechanical facts.
4. Keep active conceptual artifacts unchanged when new evidence would alter their model. Create or update a conceptual draft delta and a first-class open conflict instead of silently reconciling them.
5. Preserve decision history. Never rewrite an accepted decision to match implementation drift; create a conflict or superseding decision proposal.
6. Use `mental/changes/sync-<date>-<scope>.md` only when a durable conceptual or decision delta needs a record. Pure mechanical refresh does not require a change brief.
7. Run `python3 ../../scripts/validate_workspace.py <workspace>` with absolute paths and report structural findings separately from semantic drift.
8. Report refreshed caches, stale artifacts, conceptual verification needed, decision gaps, and open conflicts. Ask only for decisions the human has standing to make.
