| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 0.011 | 701 / 735 | 16.4 ms | 19.2 ms | index top k |
| +20 explored | 0.011 | 701 / 735 | 16.4 ms | 19.4 ms | index top k |
| +100 explored | 0.011 | 702 / 735 | 16.5 ms | 19.4 ms | index top k |
| +500 explored | 0.011 | 702 / 735 | 16.7 ms | 19.6 ms | index top k |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `small_brand` (10 documents), strategy `post` — a reader's
machine gives a different number.

