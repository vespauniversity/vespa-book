| | |
|---|---|
| run | llm, k = 20, shape `alternative` |
| questions | 872 |
| success, all of top-k | 0.327 ± 0.031 (widest for this n: ± 0.033) |
| success, answer only | 0.909 ± 0.019 |
| hit@k | 0.994 |
| precision@k | 0.791 |
| context bytes, mean | 4,470 |
| surface | tools |

n = 872. All of top-k: a task succeeds only when the answer is in the oracle set and so is every product the planner saw in its last search; answer only: the first definition, the answer alone. The interval is 1.96 * sqrt(p(1-p)/n).

