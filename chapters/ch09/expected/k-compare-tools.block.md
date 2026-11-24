| | success | queries per task, p50 / p95 | context bytes, mean | invalid queries per task |
|---|---|---|---|---|
| k = 3 | 0.909 ± 0.019 | 2 / 3 | 910 | 0.003 |
| k = 20 | 0.909 ± 0.019 | 2 / 3 | 4,470 | 0.001 |
| difference | +0.000 [-0.014, +0.014], inside the noise | -0.01 [-0.06, +0.03], inside the noise (mean) | +3560 [+3400, +3724], real (mean) | -0.002 [-0.006, +0.000], inside the noise (mean) |

| | hit@k | precision@k |
|---|---|---|
| k = 3 | 0.956 | 0.813 |
| k = 20 | 0.994 | 0.791 |

n = 872. Difference = k = 20 minus k = 3, question by question, with a bootstrap interval; success is 1 or 0 per question, queries and bytes are per question. Invalid queries per task = statements or calls refused, over questions.

