| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 1.000 | 0 / 735 | 47.2 ms | 49.8 ms | index top k using filter |
| +20 explored | 1.000 | 0 / 735 | 47.2 ms | 50.1 ms | index top k using filter |
| +100 explored | 1.000 | 0 / 735 | 47.1 ms | 49.8 ms | index top k using filter |
| +500 explored | 1.000 | 0 / 735 | 47.1 ms | 49.9 ms | index top k using filter |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `small_brand` (10 documents), strategy `pre_full` — a reader's
machine gives a different number.

