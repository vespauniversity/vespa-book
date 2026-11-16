| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 0.697 | 99 / 735 | 13.9 ms | 16.8 ms | index top k using filter |
| +20 explored | 0.718 | 99 / 735 | 14.1 ms | 16.9 ms | index top k using filter |
| +100 explored | 0.768 | 99 / 735 | 14.8 ms | 17.5 ms | index top k using filter |
| +500 explored | 0.822 | 99 / 735 | 16.2 ms | 18.8 ms | index top k using filter |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `marketplace` (5,397 documents), strategy `pre` — a reader's
machine gives a different number.

