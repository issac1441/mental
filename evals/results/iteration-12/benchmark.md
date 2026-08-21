# Learning-transfer benchmark (v2)

Generated: 2026-08-20T15:12:52+00:00

| configuration | pass rate | probes | lift/floor | traps | prefix25 | Brier | boundaries | false-cert | extraneous | time s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| with_skill | 0.945 | 1.000 | +0.625 | 1.000 | — | — | — | 0 | — | 0.0 |
| without_skill | 0.945 | 1.000 | +0.625 | 1.000 | — | — | — | 0 | — | 0.0 |
| null_floor | 0.375 | 0.375 | +0.000 | 1.000 | — | — | — | 0 | — | 0.0 |

## Tier accuracy

| configuration | counterfactual | near | retention |
| --- | --- | --- | --- |
| with_skill | 1.00 | 1.00 | 1.00 |
| without_skill | 1.00 | 1.00 | 1.00 |
| null_floor | 0.00 | 0.50 | 0.40 |

## Notes

- with_skill: probes 1.0, lift over floor +0.625, traps 1.0, false-certainty 0
- without_skill: probes 1.0, lift over floor +0.625, traps 1.0, false-certainty 0
- null_floor: probe accuracy 0.375 (prior-knowledge floor; lower = harder to guess)
