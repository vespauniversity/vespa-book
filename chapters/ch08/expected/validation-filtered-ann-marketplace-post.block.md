| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 0.342 | 22 / 735 | 16.9 ms | 19.9 ms | index top k |
| +20 explored | 0.342 | 22 / 735 | 16.9 ms | 19.9 ms | index top k |
| +100 explored | 0.342 | 22 / 735 | 16.7 ms | 19.9 ms | index top k |
| +500 explored | 0.344 | 22 / 735 | 17.4 ms | 20.4 ms | index top k |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `marketplace` (5,397 documents), strategy `post` — a reader's
machine gives a different number.

