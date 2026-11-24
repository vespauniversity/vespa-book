| | |
|---|---|
| run | llm, k = 3, shape `alternative` |
| questions | 872 |
| success | 0.909 ± 0.019 (widest for this n: ± 0.033) |
| hit@k | 0.956 |
| precision@k | 0.813 |
| context bytes, mean | 910 |
| tool statuses | malformed 3, ok 1667, over_constrained 8 |
| queries per task, p50 / p95 | 2 / 3 |
| surface | tools |
| invalid queries per task | 0.003 |

n = 872. The interval is 1.96 * sqrt(p(1-p)/n); the widest case for this n is shown because the observed-rate interval collapses at 0 and 1.

