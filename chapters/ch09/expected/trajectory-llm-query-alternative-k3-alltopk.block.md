| | |
|---|---|
| run | llm, k = 3, shape `alternative` |
| questions | 872 |
| success, all of top-k | 0.602 ± 0.032 (widest for this n: ± 0.033) |
| success, answer only | 0.908 ± 0.019 |
| hit@k | 0.948 |
| precision@k | 0.803 |
| context bytes, mean | 846 |
| surface | query |

n = 872. All of top-k: a task succeeds only when the answer is in the oracle set and so is every product the planner saw in its last search; answer only: the first definition, the answer alone. The interval is 1.96 * sqrt(p(1-p)/n).

