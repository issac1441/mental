# Learning-transfer benchmark (v2)

Generated: 2026-08-20T06:26:48+00:00

| configuration | pass rate | probes | lift/floor | traps | prefix25 | Brier | boundaries | false-cert | extraneous | time s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| with_skill | 0.933 | 0.933 | +0.396 | 1.000 | 0.600 | 0.051 | 1.000 | 0 | 0.190 | 351.0 |
| old_skill | 0.931 | 0.967 | +0.427 | 1.000 | 0.500 | 0.043 | 1.000 | 0 | 0.259 | 286.9 |
| without_skill | 0.878 | 0.933 | +0.396 | 1.000 | 0.500 | 0.049 | 1.000 | 1 | 0.134 | 205.5 |
| null_floor | 0.542 | 0.533 | +0.000 | 0.600 | — | 0.199 | — | 0 | — | 0.0 |

## Tier accuracy

| configuration | counterfactual | decision | diagnosis | edges | near | repair | retention | scope |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| with_skill | 0.75 | 1.00 | 1.00 | 1.00 | 0.88 | 1.00 | 1.00 | 1.00 |
| old_skill | 0.75 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| without_skill | 0.75 | 1.00 | 1.00 | 1.00 | 0.88 | 1.00 | 1.00 | 1.00 |
| null_floor | 0.50 | 1.00 | 0.50 | 1.00 | 0.25 | 1.00 | 0.64 | 0.00 |

## Notes

- with_skill: probes 0.933, lift over floor +0.396, traps 1.0, prefix25 0.6, Brier 0.051, boundaries 1.0, false-certainty 0, extraneous 0.19, impl-share 0.025
- old_skill: probes 0.967, lift over floor +0.427, traps 1.0, prefix25 0.5, Brier 0.043, boundaries 1.0, false-certainty 0, extraneous 0.259, impl-share 0.14
- without_skill: probes 0.933, lift over floor +0.396, traps 1.0, prefix25 0.5, Brier 0.049, boundaries 1.0, false-certainty 1, extraneous 0.134, impl-share 0.05
- null_floor: probe accuracy 0.533 (prior-knowledge floor; lower = harder to guess)
