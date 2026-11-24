| | |
|---|---|
| run | llm, k = 3, shape `alternative` |
| questions | 872 |
| success | 0.919 ± 0.018 (widest for this n: ± 0.033) |
| hit@k | 0.970 |
| precision@k | 0.841 |
| context bytes, mean | 751 |
| tool statuses | filtered 51, malformed 3, ok 1685, over_constrained 31 |
| queries per task, p50 / p95 | 2 / 4 |
| surface | query |
| invalid queries per task | 0.003 |

n = 872. The interval is 1.96 * sqrt(p(1-p)/n); the widest case for this n is shown because the observed-rate interval collapses at 0 and 1.

