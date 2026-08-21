# Learning-transfer benchmark (v2)

Generated: 2026-08-20T14:32:50+00:00

| configuration | pass rate | probes | lift/floor | traps | prefix25 | Brier | boundaries | false-cert | extraneous | time s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| with_skill | 1.000 | 1.000 | +0.250 | 1.000 | 0.750 | 0.018 | 1.000 | 0 | 0.158 | 308.1 |
| without_skill | 0.962 | 0.917 | +0.167 | 1.000 | 0.750 | 0.067 | 1.000 | 0 | 0.068 | 267.3 |
| null_floor | 0.750 | 0.750 | +0.000 | 1.000 | — | 0.330 | — | 0 | — | 0.0 |

## Tier accuracy

| configuration | counterfactual | decision | diagnosis | near | repair | retention | scope |
| --- | --- | --- | --- | --- | --- | --- | --- |
| with_skill | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| without_skill | 1.00 | 0.50 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| null_floor | 0.50 | 1.00 | 1.00 | 0.33 | 1.00 | 1.00 | 1.00 |

## Notes

- with_skill: probes 1.0, lift over floor +0.250, traps 1.0, prefix25 0.75, Brier 0.018, boundaries 1.0, false-certainty 0, extraneous 0.158
- without_skill: probes 0.917, lift over floor +0.167, traps 1.0, prefix25 0.75, Brier 0.067, boundaries 1.0, false-certainty 0, extraneous 0.068
- null_floor: probe accuracy 0.75 (prior-knowledge floor; lower = harder to guess)
