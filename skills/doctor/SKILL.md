---
name: doctor
description: Audit a mental workspace for artifact structure, frontmatter, custom lenses, evidence coverage, broken links, stale or conflicting claims, orphan concepts, and private-state leakage. Use when mental-model artifacts seem incomplete, invalid, inconsistent, or unsafe to commit. Diagnose read-only by default and repair only when explicitly requested.
---

# Doctor

Separate deterministic format failures from semantic model-quality risks.

## Workflow

1. Read `../../references/artifact-contract.md`, `../../references/methodology.md`, and `../../references/writing-profile.md` relative to this skill.
2. Run `python3 ../../scripts/validate_workspace.py <workspace> --json` using an absolute script path resolved from this skill directory.
3. Independently inspect issues a structural script cannot decide:
   - important claims without `[observed]`, `[inferred]`, `[agreed]`, or `[conflict]` provenance;
   - canonical inferences that were never confirmed;
   - source revisions newer than artifacts;
   - relationship maps without representative scenarios;
   - concepts that cannot improve a prediction;
   - custom lenses whose assumptions or priorities are identity claims rather than role needs;
   - unresolved conflicts that disappeared from later artifacts;
   - personal answers or mastery data outside `.mental/`.
4. Report findings by `error`, `warning`, and `advisory`. Include file paths and the smallest safe repair.
5. Do not edit by default. If the user requests repair, fix mechanical structure only; ask before changing meaning, provenance, status, source boundaries, or lens semantics. Re-run validation after repairs.

Never declare the model semantically correct merely because the validator exits successfully.
