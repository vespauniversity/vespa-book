| | |
|---|---|
| run | llm, k = 3, shape `alternative` |
| questions | 872 |
| success | 0.908 ± 0.019 (widest for this n: ± 0.033) |
| hit@k | 0.948 |
| precision@k | 0.803 |
| context bytes, mean | 846 |
| tool statuses | ok 1565, over_constrained 33 |
| queries per task, p50 / p95 | 2 / 3 |
| surface | query |
| invalid queries per task | 0.000 |

n = 872. The interval is 1.96 * sqrt(p(1-p)/n); the widest case for this n is shown because the observed-rate interval collapses at 0 and 1.

