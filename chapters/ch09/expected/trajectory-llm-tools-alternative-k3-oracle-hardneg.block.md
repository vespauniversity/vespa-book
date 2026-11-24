| | |
|---|---|
| run | llm, k = 3, evidence supplied, shape `alternative` |
| questions | 470 |
| success | 0.838 ± 0.033 (widest for this n: ± 0.045) |
| hit@k | 0.934 |
| precision@k | 0.780 |
| context bytes, mean | 925 |
| tool statuses | malformed 1, ok 933, over_constrained 7 |
| queries per task, p50 / p95 | 2 / 3 |
| surface | tools |
| invalid queries per task | 0.002 |

n = 470. The interval is 1.96 * sqrt(p(1-p)/n); the widest case for this n is shown because the observed-rate interval collapses at 0 and 1. Hard-negative subset: the 470 questions, of 872, whose pool holds at least one product labelled irrelevant (I).

