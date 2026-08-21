# Exploratory skill evaluations — 2026-08-20

Iterations 7–12 explored `change`, `review`, `doctor`, `sync`, `learn`, and `practice` after the v0.3.0 study. These are directional findings, not a release gate: the historical runner did not emit the provenance records now required for comparable aggregation.

## Change and review

- Iteration 7 exposed a restricted git-tool configuration that left `review` blind to part of the diff. The dirty-diff case found 2 of 4 consequential decisions, while the bare arm found all 4.
- Iteration 8 widened the read-only git allowance and removed repeated findings. The dirty-diff case then reached 13/13 with a 0% Decision Surprise Rate; the subtle case reached 12/12.
- Iterations 9–10 tightened answer-first presentation and path-specific evidence. The final exploratory change cases reached 13/13, with gist and overhead at 5/5 and no sampled fabricated assertion.

## Doctor and sync

- The doctor fixture saturated at 6/6 for both arms, so it was useful for conformance but not discriminative quality measurement.
- Iteration 11 reached 7/7 for both sync arms with no false positives. The skill arm found more real out-of-inventory drift and produced more disciplined pending decisions, but the case was recall-saturated.

## Learn and practice dialogue

- Iteration 12 validated the multi-turn protocol. `learn` reached 9/9 versus 8/9 for the bare arm; the differentiating behavior was diagnosing before teaching.
- `practice` reached 8/9 versus 9/9 for the bare arm. Review found that the failed criterion incorrectly combined two corrections even though the skill intentionally corrected one relationship at a time.
- Both post-tests saturated at 4/4. Future cases need transfer questions that require combining relationships not stated verbatim in the dialogue.

## Audit source

The full historical captures are available at commit [`c8d8f8c`](https://github.com/issac1441/mental/tree/c8d8f8c44fb0e9dc4d6f07b991333e08037d65d4/evals/results), result-tree `8ed687c736e94ab8afee584ff8e40d556f979d15`.
