| | |
|---|---|
| run | rules, k = 20, shape `alternative` |
| questions | 872 |
| success, all of top-k | 0.411 ± 0.033 (widest for this n: ± 0.033) |
| success, answer only | 0.870 ± 0.022 |
| hit@k | 0.995 |
| precision@k | 0.816 |
| context bytes, mean | 2,533 |
| surface | tools |

n = 872. All of top-k: a task succeeds only when the answer is in the oracle set and so is every product the planner saw in its last search; answer only: the first definition, the answer alone. The interval is 1.96 * sqrt(p(1-p)/n).

