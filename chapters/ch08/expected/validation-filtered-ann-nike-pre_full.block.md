| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 0.995 | 0 / 735 | 36.2 ms | 45.0 ms | index top k using filter |
| +20 explored | 0.997 | 0 / 735 | 36.9 ms | 45.0 ms | index top k using filter |
| +100 explored | 1.000 | 0 / 735 | 40.1 ms | 47.0 ms | index top k using filter |
| +500 explored | 1.000 | 0 / 735 | 47.8 ms | 51.1 ms | index top k using filter |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `nike` (604 documents), strategy `pre_full` — a reader's machine
gives a different number.

