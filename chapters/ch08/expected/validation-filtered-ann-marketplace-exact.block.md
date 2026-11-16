| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 1.000 | 0 / 735 | 14.9 ms | 17.5 ms | exact |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `marketplace` (5,397 documents), strategy `exact` — a reader's
machine gives a different number.

