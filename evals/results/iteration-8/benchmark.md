# Learning-transfer benchmark (v2)

Generated: 2026-08-20T13:12:10+00:00

| configuration | pass rate | probes | lift/floor | traps | prefix25 | Brier | boundaries | false-cert | extraneous | time s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| with_skill | 0.954 | 1.000 | +0.542 | 1.000 | 0.870 | 0.019 | 1.000 | 0 | 0.251 | 342.5 |
| without_skill | 0.968 | 0.957 | +0.500 | 1.000 | 0.783 | 0.058 | 1.000 | 0 | 0.095 | 200.9 |
| null_floor | 0.458 | 0.478 | +0.000 | 0.667 | — | 0.210 | — | 0 | — | 0.0 |

## Tier accuracy

| configuration | counterfactual | decision | diagnosis | near | repair | retention | scope |
| --- | --- | --- | --- | --- | --- | --- | --- |
| with_skill | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| without_skill | 1.00 | 0.75 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| null_floor | 0.40 | 0.50 | 1.00 | 0.25 | 0.50 | 0.50 | 0.67 |

## Notes

- with_skill: probes 1.0, lift over floor +0.542, traps 1.0, prefix25 0.87, Brier 0.019, boundaries 1.0, false-certainty 0, extraneous 0.251
- without_skill: probes 0.957, lift over floor +0.500, traps 1.0, prefix25 0.783, Brier 0.058, boundaries 1.0, false-certainty 0, extraneous 0.095
- null_floor: probe accuracy 0.478 (prior-knowledge floor; lower = harder to guess)
