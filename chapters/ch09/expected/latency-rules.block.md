| | |
|---|---|
| run | rules, k = 3, shape `alternative` |
| tasks | 872 |
| queries per task, p50 / p95 (mean) | 2 / 2 (2.00) |
| latency per task, p50 / p95 | 36.7 ms / 49.9 ms |
| latency per task, max | 117.2 ms |
| latency per query, mean | 18.8 ms |

Retrieval time only: the sum of a task's tool calls as the loop timed them (every request a call made, re-runs included), model time excluded. One pass over the whole set after a warm-up pass over it, on an Apple M4 Pro with a 4 CPU / 10 GB container VM; a reader's machine will give other numbers.

