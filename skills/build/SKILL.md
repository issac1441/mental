---
name: build
description: Build draft, evidence-linked mental-model artifacts from a supplied repository, files, text, or URLs. Use to bootstrap mental artifacts, map an unfamiliar codebase or subject, create learning material, or define reusable role lenses. This skill may write drafts but must not make them canonical without explicit human confirmation.
---

# Build

Create the smallest model that improves prediction. Treat every new conceptual claim as a candidate until a human confirms it.

## Workflow

1. Resolve references relative to this `SKILL.md`. Read `../../references/methodology.md`, `../../references/artifact-contract.md`, and `../../references/writing-profile.md`. Read `../../references/repository-workflow.md` for repository mode or `../../references/learning-workflow.md` for learning mode.
2. Establish the source boundary. The current repository is supplied when invoked from it; otherwise require files, text, or URLs from the user. Fetch only URLs the user supplied. Do not expand into autonomous web research.
3. Choose `repository`, `learning`, or `hybrid` mode and follow the user's language. If `mental/` is absent, run the internal helper with an absolute workspace path:

   `python3 ../../scripts/scaffold_workspace.py <workspace> --mode <mode> --language <language>`

   Resolve the script path from this skill directory. It is non-destructive and keeps existing files.
4. Inventory evidence before modeling. Register stable source IDs in `mental/sources.md` with type, location, scope, revision, and access status.
5. Build `mental/model/map.md` first, then only the concepts and scenarios needed to support it. Add mode-specific artifacts only when evidence exists.
6. When the user asks for a reusable role-conditioned explanation, create a `kind: lens` draft under `mental/lenses/` from `../../assets/templates/lens.md`. Define `assumes`, `prioritizes`, `vocabulary`, and `default_views`; never encode identity or an inferred ability judgment.
7. Mark direct claims `[observed]`, synthesis `[inferred]`, and mismatches `[conflict]`. Every created or materially changed artifact remains `status: draft`.
8. Validate with `python3 ../../scripts/validate_workspace.py <workspace>`. Fix structural errors without hiding semantic conflicts.
9. Present a promotion gate containing boundaries, key relationships, causal claims or invariants, one success scenario, one failure/counterexample, and known gaps. Stop for the human decision.
10. On a later turn, promote only explicitly accepted artifacts to `canonical`, change accepted conceptual claims to `[agreed]`, preserve their evidence, and leave rejected or unresolved artifacts as draft or stale.

## Output

Summarize created or changed artifacts, source coverage, inferences needing a decision, conflicts, and the exact promotion choices. Do not implement repository code as part of this skill.
