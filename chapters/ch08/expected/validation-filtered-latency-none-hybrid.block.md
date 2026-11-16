| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| hybrid | — | — | 15.2 ms | 18.7 ms | — |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `none` (101,341 documents), retriever `hybrid` (no ANN strategy)
— a reader's machine gives a different number.

