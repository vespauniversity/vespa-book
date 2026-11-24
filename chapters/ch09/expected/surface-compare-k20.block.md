| | success | queries per task, p50 / p95 | context bytes, mean | invalid queries per task |
|---|---|---|---|---|
| tool surface | 0.909 ± 0.019 | 2 / 3 | 4,470 | 0.001 |
| query surface | 0.900 ± 0.020 | 2 / 4 | 4,038 | 0.001 |
| difference | -0.009 [-0.019, +0.001], inside the noise | +0.05 [+0.01, +0.09], real (mean) | -432 [-540, -325], real (mean) | +0.000 [-0.003, +0.003], inside the noise (mean) |

n = 872. Difference = query surface minus tool surface, question by question, with a bootstrap interval; success is 1 or 0 per question, queries and bytes are per question. Invalid queries per task = statements or calls refused, over questions.

