| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 0.919 | 0 / 735 | 13.8 ms | 16.6 ms | index top k using filter |
| +20 explored | 0.936 | 0 / 735 | 14.0 ms | 16.6 ms | index top k using filter |
| +100 explored | 0.966 | 0 / 735 | 14.4 ms | 17.0 ms | index top k using filter |
| +500 explored | 0.993 | 0 / 735 | 16.1 ms | 19.0 ms | index top k using filter |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `has_description` (51,995 documents), strategy `default` — a
reader's machine gives a different number.

