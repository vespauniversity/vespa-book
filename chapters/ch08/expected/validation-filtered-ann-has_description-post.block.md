| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| default | 0.860 | 0 / 735 | 14.0 ms | 16.7 ms | index top k |
| +20 explored | 0.865 | 0 / 735 | 14.1 ms | 16.7 ms | index top k |
| +100 explored | 0.880 | 0 / 735 | 14.4 ms | 16.8 ms | index top k |
| +500 explored | 0.898 | 0 / 735 | 15.4 ms | 18.3 ms | index top k |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `has_description` (51,995 documents), strategy `post` — a
reader's machine gives a different number.

