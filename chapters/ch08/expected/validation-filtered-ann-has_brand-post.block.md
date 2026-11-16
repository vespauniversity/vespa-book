| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 0.874 | 0 / 735 | 13.6 ms | 16.2 ms | index top k |
| +20 explored | 0.891 | 0 / 735 | 13.7 ms | 16.3 ms | index top k |
| +100 explored | 0.917 | 0 / 735 | 14.1 ms | 16.7 ms | index top k |
| +500 explored | 0.937 | 0 / 735 | 15.0 ms | 17.6 ms | index top k |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `has_brand` (95,944 documents), strategy `post` — a reader's
machine gives a different number.

