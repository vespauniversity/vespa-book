| | |
|---|---|
| run | llm, k = 3, evidence supplied, shape `alternative` |
| questions | 872 |
| success | 0.905 ± 0.019 (widest for this n: ± 0.033) |
| hit@k | 0.947 |
| precision@k | 0.853 |
| context bytes, mean | 823 |
| tool statuses | malformed 3, ok 1500, over_constrained 42 |
| queries per task, p50 / p95 | 1 / 3 |
| surface | query |
| invalid queries per task | 0.003 |

n = 872. The interval is 1.96 * sqrt(p(1-p)/n); the widest case for this n is shown because the observed-rate interval collapses at 0 and 1.

