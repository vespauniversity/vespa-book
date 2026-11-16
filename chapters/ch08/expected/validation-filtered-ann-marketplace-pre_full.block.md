| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 0.964 | 0 / 735 | 25.4 ms | 33.5 ms | index top k using filter |
| +20 explored | 0.974 | 0 / 735 | 26.5 ms | 35.0 ms | index top k using filter |
| +100 explored | 0.991 | 0 / 735 | 30.0 ms | 38.2 ms | index top k using filter |
| +500 explored | 0.999 | 0 / 735 | 38.5 ms | 45.2 ms | index top k using filter |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `marketplace` (5,397 documents), strategy `pre_full` — a reader's
machine gives a different number.

