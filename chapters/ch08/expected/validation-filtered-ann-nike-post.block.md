| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 0.085 | 395 / 735 | 16.6 ms | 19.5 ms | index top k |
| +20 explored | 0.085 | 396 / 735 | 16.7 ms | 19.6 ms | index top k |
| +100 explored | 0.085 | 396 / 735 | 16.8 ms | 19.7 ms | index top k |
| +500 explored | 0.086 | 393 / 735 | 17.0 ms | 19.9 ms | index top k |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `nike` (604 documents), strategy `post` — a reader's machine
gives a different number.

