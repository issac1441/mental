# Final benchmark — repeats aggregate

Generated: 2026-08-20T08:56:25+00:00

| metric | with_skill | without_skill |
| --- | --- | --- |
| pass_rate | 0.954 ± 0.026 | 0.884 ± 0.028 |
| probe_accuracy | 0.944 ± 0.02 | 0.9 ± 0.033 |
| lift_over_floor | 0.406 ± 0.018 | 0.361 ± 0.037 |
| trap_accuracy | 1.0 ± 0.0 | 1.0 ± 0.0 |
| prefix25_accuracy | 0.567 ± 0.058 | 0.478 ± 0.102 |
| brier | 0.044 ± 0.015 | 0.063 ± 0.014 |
| boundary_coverage | 1.0 ± 0.0 | 0.972 ± 0.048 |
| false_certainty_total | 0 ± 0.0 | 0.667 ± 0.577 |
| extraneous_ratio | 0.189 ± 0.013 | 0.158 ± 0.021 |
| altitude_implementation_share | 0.082 ± 0.028 | 0.067 ± 0.029 |

## Paired deltas (with_skill − without_skill)

- probe accuracy: +0.045 (95% CI [0.01, 0.083], n=12 case×repeat pairs)
- prefix25: +0.087 (95% CI [0.003, 0.17])

## Release criteria

- ✅ transfer not worse than bare (paired CI overlaps or exceeds 0) — probe delta +0.045, 95% CI [0.01, 0.083]
- ✅ anytime validity better than bare (prefix25 delta > 0) — prefix25 delta +0.087, 95% CI [0.003, 0.17]
- ✅ reader calibration not worse (Brier) — Brier 0.044 vs 0.063
- ✅ zero fabricated flat assertions across repeats — false-certainty per repeat: [0, 0, 0]
- ✅ pm-case altitude within cap (<=0.10 mean) — implementation share 0.082
- ✅ boundary coverage stays complete — boundary coverage 1.0
- ✅ leaner than the pre-tune skill (extraneous) — extraneous 0.189 vs old 0.259

**Release: PASS**
