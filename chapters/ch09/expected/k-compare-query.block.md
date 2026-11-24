| | success | queries per task, p50 / p95 | context bytes, mean | invalid queries per task |
|---|---|---|---|---|
| k = 3 | 0.908 ± 0.019 | 2 / 3 | 846 | 0.000 |
| k = 20 | 0.900 ± 0.020 | 2 / 4 | 4,038 | 0.001 |
| difference | -0.008 [-0.022, +0.007], inside the noise | +0.10 [+0.05, +0.16], real (mean) | +3192 [+3048, +3344], real (mean) | +0.001 [+0.000, +0.003], inside the noise (mean) |

| | hit@k | precision@k |
|---|---|---|
| k = 3 | 0.948 | 0.803 |
| k = 20 | 0.984 | 0.809 |

n = 872. Difference = k = 20 minus k = 3, question by question, with a bootstrap interval; success is 1 or 0 per question, queries and bytes are per question. Invalid queries per task = statements or calls refused, over questions.

