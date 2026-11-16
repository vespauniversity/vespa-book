| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 0.910 | 0 / 735 | 13.2 ms | 15.9 ms | index top k using filter |
| +20 explored | 0.928 | 0 / 735 | 13.2 ms | 15.9 ms | index top k using filter |
| +100 explored | 0.960 | 0 / 735 | 13.5 ms | 16.1 ms | index top k using filter |
| +500 explored | 0.990 | 0 / 735 | 14.7 ms | 17.3 ms | index top k using filter |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `has_brand` (95,944 documents), strategy `default` — a reader's
machine gives a different number.

