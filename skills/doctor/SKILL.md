---
name: doctor
description: Advanced diagnostic skill that audits a mental workspace's structure, authority/state rules, evidence coverage, decision ledger, open conflicts, links, drift, and private-state isolation. Use when durable mental artifacts appear invalid, stale, inconsistent, or unsafe to commit; diagnose read-only by default and repair only when explicitly requested.
---

# Doctor

Separate deterministic schema failures from semantic model risks.

## Input contract

`[scope] [repair=<true|false>]`

Scope defaults to the current mental workspace. Repair defaults to false and never authorizes semantic changes.

## Workflow

1. Read `../../references/artifact-contract.md`, `../../references/methodology.md`, `../../references/output-style.md`, `../../references/source-safety.md`, and `../../references/writing-profile.md` relative to this skill.
2. Run `python3 ../../scripts/validate_workspace.py <workspace> --json` using absolute paths.
3. Independently inspect what the structural validator cannot decide:
   - whether each mechanical `refresh_basis` names the source revision that actually reproduces the artifact;
   - whether active conceptual artifacts have verification and checked predictions that actually support the represented model;
   - decisions missing rejected alternatives, owner, timing, or history;
   - deleted, reordered, or rewritten `status_history`, `supersedes`, or `superseded_by` entries compared with the Git baseline, when Git can supply one;
   - material mismatches that lack first-class open conflict artifacts;
   - resolved conflicts without evidence or a decision;
   - missing Model × Harness × Task Class coverage behind autonomy claims;
   - artifacts that do not improve a prediction, decision, repair, or navigation task;
   - personal answers or mastery outside `.mental/` and Git privacy checks the validator could not complete.
4. Report `error`, `warning`, and `advisory` findings with the smallest safe repair. Separate `Structure` from `Readiness`; drafts, stale artifacts, pending decisions, and open conflicts make readiness incomplete without making the structure invalid. Treat Git-history privacy findings as advisory because validation cannot remove copies from refs, forks, or remotes. If Git or a baseline is unavailable, label decision-history preservation unverified instead of claiming it passed. Include counts of open conflicts and post-approval consequential decisions when available.
5. Do not edit by default. With explicit repair, fix mechanical structure only; ask before changing meaning, authority, status, evidence, decision history, conflict resolution, or source boundary.

Never declare a model correct merely because validation succeeds.
