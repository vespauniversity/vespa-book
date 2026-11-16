| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 1.000 | 0 / 735 | 12.8 ms | 15.4 ms | exact |
| +20 explored | 1.000 | 0 / 735 | 12.8 ms | 15.6 ms | exact |
| +100 explored | 1.000 | 0 / 735 | 12.8 ms | 15.5 ms | exact |
| +500 explored | 1.000 | 0 / 735 | 12.8 ms | 15.4 ms | exact |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `nike` (604 documents), strategy `default` — a reader's machine
gives a different number.

