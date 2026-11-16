| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 1.000 | 0 / 735 | 11.7 ms | 14.3 ms | exact |
| +20 explored | 1.000 | 0 / 735 | 12.3 ms | 15.0 ms | exact |
| +100 explored | 1.000 | 0 / 735 | 12.1 ms | 14.8 ms | exact |
| +500 explored | 1.000 | 0 / 735 | 12.2 ms | 14.8 ms | exact |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `small_brand` (10 documents), strategy `default` — a reader's
machine gives a different number.

