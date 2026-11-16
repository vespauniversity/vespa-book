| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 0.242 | 557 / 735 | 12.3 ms | 15.2 ms | index top k using filter |
| +20 explored | 0.242 | 557 / 735 | 12.3 ms | 15.3 ms | index top k using filter |
| +100 explored | 0.242 | 557 / 735 | 12.3 ms | 15.4 ms | index top k using filter |
| +500 explored | 0.242 | 557 / 735 | 12.4 ms | 15.9 ms | index top k using filter |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `nike` (604 documents), strategy `pre` — a reader's machine gives
a different number.

