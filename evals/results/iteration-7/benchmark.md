# Learning-transfer benchmark (v2)

Generated: 2026-08-20T12:27:25+00:00

| configuration | pass rate | probes | lift/floor | traps | prefix25 | Brier | boundaries | false-cert | extraneous | time s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| with_skill | 0.828 | 0.957 | +0.500 | 1.000 | 0.870 | 0.068 | 0.900 | 0 | 0.278 | 428.5 |
| without_skill | 0.969 | 0.913 | +0.458 | 1.000 | 0.696 | 0.050 | 1.000 | 0 | 0.114 | 222.3 |
| null_floor | 0.458 | 0.478 | +0.000 | 0.667 | — | 0.210 | — | 0 | — | 0.0 |

## Tier accuracy

| configuration | counterfactual | decision | diagnosis | near | repair | retention | scope |
| --- | --- | --- | --- | --- | --- | --- | --- |
| with_skill | 1.00 | 0.75 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| without_skill | 1.00 | 0.75 | 1.00 | 0.75 | 1.00 | 1.00 | 1.00 |
| null_floor | 0.40 | 0.50 | 1.00 | 0.25 | 0.50 | 0.50 | 0.67 |

## Notes

- with_skill: probes 0.957, lift over floor +0.500, traps 1.0, prefix25 0.87, Brier 0.068, boundaries 0.9, false-certainty 0, extraneous 0.278
- without_skill: probes 0.913, lift over floor +0.458, traps 1.0, prefix25 0.696, Brier 0.05, boundaries 1.0, false-certainty 0, extraneous 0.114
- null_floor: probe accuracy 0.478 (prior-knowledge floor; lower = harder to guess)
