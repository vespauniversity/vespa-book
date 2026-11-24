| | success | queries per task, p50 / p95 | context bytes, mean | invalid queries per task |
|---|---|---|---|---|
| no boundary | 0.908 ± 0.019 | 2 / 3 | 846 | 0.000 |
| boundary of 2 sellers (pair) | 0.919 ± 0.018 | 2 / 4 | 751 | 0.003 |
| difference | +0.010 [-0.014, +0.034], inside the noise | +0.29 [+0.22, +0.36], real (mean) | -95 [-127, -63], real (mean) | +0.003 [+0.000, +0.009], inside the noise (mean) |

| | tool statuses |
|---|---|
| no boundary | ok 1565, over_constrained 33 |
| boundary of 2 sellers (pair) | filtered 51, malformed 3, ok 1685, over_constrained 31 |

n = 872. Difference = boundary of 2 sellers (pair) minus no boundary, question by question, with a bootstrap interval; success is 1 or 0 per question, queries and bytes are per question. Invalid queries per task = statements or calls refused, over questions.

