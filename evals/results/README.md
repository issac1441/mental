# Published evaluation evidence

The repository keeps concise, reviewable summaries here. Raw model transcripts, grader outputs, and per-iteration caches do not belong on the default branch.

## v0.3.0 evaluated line

- [Human-readable benchmark](v0.3.0/benchmark-final.md)
- [Machine-readable summary](v0.3.0/summary.json)
- [Evidence manifest and limitations](v0.3.0/manifest.json)
- [Later exploratory findings](exploratory-2026-08-20.md)

The historical raw captures remain auditable in the immutable source commit [`c8d8f8c`](https://github.com/issac1441/mental/tree/c8d8f8c44fb0e9dc4d6f07b991333e08037d65d4/evals/results). Iterations 1–6 supported the v0.3.0 study. Iterations 7–12 were later exploratory studies of other skills.

Those captures predate per-run provenance records. They may explain an earlier decision, but the current runner will not accept them as release-gate inputs.

## Publishing policy

Commit only:

- a compact aggregate with no local absolute paths or session identifiers;
- a manifest that pins the source commit and result-tree hash;
- limitations that distinguish measured evidence from exploratory observations.

Keep raw captures in a gitignored workspace. If a future release needs a full evidence bundle, publish a sanitized archive outside the default branch and record its immutable URL and SHA-256 in the manifest.
