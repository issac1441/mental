# Learning-transfer benchmark (v2)

Generated: 2026-08-20T08:57:06+00:00

| configuration | pass rate | probes | lift/floor | traps | prefix25 | Brier | boundaries | false-cert | extraneous | time s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| with_skill | 0.947 | 0.933 | — | 1.000 | 0.500 | 0.061 | 1.000 | 0 | 0.199 | 272.1 |
| without_skill | 0.914 | 0.900 | — | 1.000 | 0.367 | 0.063 | 1.000 | 0 | 0.170 | 198.2 |

## Tier accuracy

| configuration | counterfactual | decision | diagnosis | edges | near | repair | retention | scope |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| with_skill | 0.75 | 1.00 | 1.00 | 1.00 | 0.88 | 1.00 | 1.00 | 1.00 |
| without_skill | 0.75 | 1.00 | 1.00 | 1.00 | 0.75 | 1.00 | 1.00 | 1.00 |

## Notes

- with_skill: probes 0.933, traps 1.0, prefix25 0.5, Brier 0.061, boundaries 1.0, false-certainty 0, extraneous 0.199, impl-share 0.05
- without_skill: probes 0.9, traps 1.0, prefix25 0.367, Brier 0.063, boundaries 1.0, false-certainty 0, extraneous 0.17, impl-share 0.05
