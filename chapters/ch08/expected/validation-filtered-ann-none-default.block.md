| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 0.908 | 0 / 735 | 13.8 ms | 16.3 ms | index top k |
| +20 explored | 0.928 | 0 / 735 | 13.9 ms | 16.4 ms | index top k |
| +100 explored | 0.960 | 0 / 735 | 14.1 ms | 16.7 ms | index top k |
| +500 explored | 0.990 | 0 / 735 | 15.2 ms | 18.0 ms | index top k |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `none` (101,341 documents), strategy `default` — a reader's
machine gives a different number.

