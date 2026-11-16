| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 0.017 | 720 / 735 | 11.7 ms | 14.3 ms | index top k using filter |
| +20 explored | 0.017 | 720 / 735 | 11.7 ms | 14.2 ms | index top k using filter |
| +100 explored | 0.017 | 720 / 735 | 11.7 ms | 14.4 ms | index top k using filter |
| +500 explored | 0.017 | 720 / 735 | 11.8 ms | 14.2 ms | index top k using filter |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `small_brand` (10 documents), strategy `pre` — a reader's machine
gives a different number.

