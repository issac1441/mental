# Learning-transfer benchmark

Generated: 2026-08-20T03:15:49+00:00

| configuration | pass rate (mean) | time s (mean) | tokens (mean) |
| --- | --- | --- | --- |
| with_skill | 0.967 | 278.6 | 422,535 |
| old_skill | 0.733 | 399.2 | 430,598 |
| without_skill | 0.833 | 151.7 | 147,170 |

## Per-run

| eval | configuration | passed/total | time s |
| --- | --- | --- | --- |
| mental-orientation | old_skill | 7/10 | 266.5 |
| mental-orientation | with_skill | 9/10 | 265.3 |
| mental-orientation | without_skill | 6/10 | 89.3 |
| orderflow-failure | old_skill | 7/10 | 324.2 |
| orderflow-failure | with_skill | 10/10 | 311.9 |
| orderflow-failure | without_skill | 9/10 | 204.7 |
| orderflow-trace | old_skill | 8/10 | 607.0 |
| orderflow-trace | with_skill | 10/10 | 258.5 |
| orderflow-trace | without_skill | 10/10 | 161.2 |

## Notes

- with_skill: transfer(probe) accuracy 93%, avg explanation 5,585 chars, rubric {'gist': 4.67, 'coherence': 5, 'overhead': 4, 'concreteness': 5}
- old_skill: transfer(probe) accuracy 93%, avg explanation 6,018 chars, rubric {'gist': 1.67, 'coherence': 3.67, 'overhead': 1.67, 'concreteness': 5}
- without_skill: transfer(probe) accuracy 87%, avg explanation 3,754 chars, rubric {'gist': 3.67, 'coherence': 5, 'overhead': 4, 'concreteness': 5}
