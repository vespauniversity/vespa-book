| | |
|---|---|
| run | llm, k = 3, the oracle's products supplied, shape `alternative` |
| questions | 872 |
| success | 0.991 ± 0.006 (widest for this n: ± 0.033) |
| hit@k | 0.872 |
| precision@k | 0.663 |
| context bytes, mean | 57 |
| tool statuses | ok 104, over_constrained 3 |
| queries per task, p50 / p95 | 0 / 1 |
| surface | tools |
| invalid queries per task | 0.000 |

n = 872. The interval is 1.96 * sqrt(p(1-p)/n); the widest case for this n is shown because the observed-rate interval collapses at 0 and 1.

