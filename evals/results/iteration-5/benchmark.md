# Learning-transfer benchmark (v2)

Generated: 2026-08-20T08:57:05+00:00

| configuration | pass rate | probes | lift/floor | traps | prefix25 | Brier | boundaries | false-cert | extraneous | time s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| with_skill | 0.983 | 0.967 | — | 1.000 | 0.600 | 0.034 | 1.000 | 0 | 0.193 | 286.5 |
| without_skill | 0.859 | 0.867 | — | 1.000 | 0.567 | 0.077 | 0.917 | 1 | 0.169 | 215.2 |

## Tier accuracy

| configuration | counterfactual | decision | diagnosis | edges | near | repair | retention | scope |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| with_skill | 1.00 | 1.00 | 1.00 | 1.00 | 0.88 | 1.00 | 1.00 | 1.00 |
| without_skill | 0.50 | 1.00 | 1.00 | 1.00 | 0.88 | 1.00 | 0.91 | 1.00 |

## Notes

- with_skill: probes 0.967, traps 1.0, prefix25 0.6, Brier 0.034, boundaries 1.0, false-certainty 0, extraneous 0.193, impl-share 0.1
- without_skill: probes 0.867, traps 1.0, prefix25 0.567, Brier 0.077, boundaries 0.917, false-certainty 1, extraneous 0.169, impl-share 0.1
