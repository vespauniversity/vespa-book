| | |
|---|---|
| run | llm, k = 3, evidence supplied, shape `alternative` |
| questions | 470 |
| success | 0.847 ± 0.033 (widest for this n: ± 0.045) |
| hit@k | 0.917 |
| precision@k | 0.768 |
| context bytes, mean | 823 |
| tool statuses | malformed 1, ok 830, over_constrained 26 |
| queries per task, p50 / p95 | 2 / 3 |
| surface | query |
| invalid queries per task | 0.002 |

n = 470. The interval is 1.96 * sqrt(p(1-p)/n); the widest case for this n is shown because the observed-rate interval collapses at 0 and 1. Hard-negative subset: the 470 questions, of 872, whose pool holds at least one product labelled irrelevant (I).

