| | |
|---|---|
| run | llm, k = 3, shape `brands` |
| questions | 872 |
| brand recall, mean | 0.637 |
| brand precision, mean | 0.907 |
| context bytes, mean | 1,305 |
| tool statuses | malformed 7, ok 2514, over_constrained 32, planner_error 2 |
| queries per task, p50 / p95 | 3 / 3 |
| surface | query |
| invalid queries per task | 0.008 |

n = 872. Recall: the share of the oracle's brands the table names; precision: the share of the table's brands the oracle names.

