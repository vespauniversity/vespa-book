| | |
|---|---|
| run | llm, k = 20, shape `alternative` |
| questions | 872 |
| success | 0.900 ± 0.020 (widest for this n: ± 0.033) |
| hit@k | 0.984 |
| precision@k | 0.809 |
| context bytes, mean | 4,038 |
| tool statuses | malformed 1, ok 1563, over_constrained 77 |
| queries per task, p50 / p95 | 2 / 4 |
| surface | query |
| invalid queries per task | 0.001 |

n = 872. The interval is 1.96 * sqrt(p(1-p)/n); the widest case for this n is shown because the observed-rate interval collapses at 0 and 1.

