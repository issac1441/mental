---
name: sync
description: Compare canonical mental-model artifacts with their current supplied sources and propose an evidence-linked model delta. Use after code, documentation, source revisions, or new evidence may have made `mental/` stale. This skill may write a draft delta but must not silently reconcile conflicts or update canonical claims without approval.
---

# Sync

Detect drift without choosing truth on the user's behalf.

## Workflow

1. Read `../../references/methodology.md`, `../../references/artifact-contract.md`, and the mode-specific workflow reference relative to this skill.
2. Read `mental/index.md`, every artifact in scope, and the source catalog. Re-read only registered sources; do not discover replacements for missing sources.
3. Compare each material claim and relationship. Classify results as `unchanged`, `added evidence`, `changed`, `removed`, `contradicted`, or `unverifiable`.
4. Keep canonical artifacts untouched. Write or update a draft `mental/changes/sync-<date>-<scope>.md` with:
   - current model;
   - source delta;
   - proposed model delta;
   - conflicts and surprises;
   - affected contracts, prerequisites, or scenarios;
   - verification evidence;
   - `Human Decision: pending`.
5. Mark an affected artifact `stale` only when the user explicitly asks to record detected drift before deciding the replacement. Never replace `[agreed]` with `[inferred]` silently.
6. Run `../../scripts/validate_workspace.py` and report structural findings separately from semantic drift.
7. Ask for a decision per coherent delta. After approval, update only accepted artifacts, preserve conflict history in the change record, and restore `canonical` only when evidence and agreement are both present.

Report unchanged areas briefly; focus attention on model changes and decision surprises.
