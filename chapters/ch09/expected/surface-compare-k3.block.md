| | success | queries per task, p50 / p95 | context bytes, mean | invalid queries per task |
|---|---|---|---|---|
| tool surface | 0.909 ± 0.019 | 2 / 3 | 910 | 0.003 |
| query surface | 0.908 ± 0.019 | 2 / 3 | 846 | 0.000 |
| difference | -0.001 [-0.014, +0.010], inside the noise | -0.06 [-0.11, -0.02], real (mean) | -63 [-88, -41], real (mean) | -0.003 [-0.008, +0.000], inside the noise (mean) |

n = 872. Difference = query surface minus tool surface, question by question, with a bootstrap interval; success is 1 or 0 per question, queries and bytes are per question. Invalid queries per task = statements or calls refused, over questions.

