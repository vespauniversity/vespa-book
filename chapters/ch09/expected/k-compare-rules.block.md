| | success | queries per task, p50 / p95 | context bytes, mean | invalid queries per task |
|---|---|---|---|---|
| k = 3 | 0.869 ± 0.022 | 2 / 2 | 635 | 0.000 |
| k = 20 | 0.870 ± 0.022 | 2 / 2 | 2,533 | 0.000 |
| difference | +0.001 [+0.000, +0.003], inside the noise | +0.00 [+0.00, +0.00], inside the noise (mean) | +1898 [+1843, +1955], real (mean) | +0.000 [+0.000, +0.000], inside the noise (mean) |

| | hit@k | precision@k |
|---|---|---|
| k = 3 | 0.969 | 0.868 |
| k = 20 | 0.995 | 0.816 |

n = 872. Difference = k = 20 minus k = 3, question by question, with a bootstrap interval; success is 1 or 0 per question, queries and bytes are per question. Invalid queries per task = statements or calls refused, over questions.

