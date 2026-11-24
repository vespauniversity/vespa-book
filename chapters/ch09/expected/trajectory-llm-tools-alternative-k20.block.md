| | |
|---|---|
| run | llm, k = 20, shape `alternative` |
| questions | 872 |
| success | 0.909 ± 0.019 (widest for this n: ± 0.033) |
| hit@k | 0.994 |
| precision@k | 0.791 |
| context bytes, mean | 4,470 |
| tool statuses | malformed 1, ok 1651, over_constrained 11 |
| queries per task, p50 / p95 | 2 / 3 |
| surface | tools |
| invalid queries per task | 0.001 |

n = 872. The interval is 1.96 * sqrt(p(1-p)/n); the widest case for this n is shown because the observed-rate interval collapses at 0 and 1.

