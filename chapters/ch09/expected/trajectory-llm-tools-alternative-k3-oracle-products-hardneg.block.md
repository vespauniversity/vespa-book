| | |
|---|---|
| run | llm, k = 3, the oracle's products supplied, shape `alternative` |
| questions | 470 |
| success | 0.983 ± 0.012 (widest for this n: ± 0.045) |
| hit@k | 0.833 |
| precision@k | 0.572 |
| context bytes, mean | 75 |
| tool statuses | ok 72, over_constrained 3 |
| queries per task, p50 / p95 | 0 / 1 |
| surface | tools |
| invalid queries per task | 0.000 |

n = 470. The interval is 1.96 * sqrt(p(1-p)/n); the widest case for this n is shown because the observed-rate interval collapses at 0 and 1. Hard-negative subset: the 470 questions, of 872, whose pool holds at least one product labelled irrelevant (I).

