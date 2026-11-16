| explore | agreement@100 | empty queries | p50 | p95 | algorithm |
|---|---|---|---|---|---|
| lexical | — | — | 3.5 ms | 5.0 ms | — |

Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher
Desktop), median of 3 warm passes, client-measured, validation split, 735
queries, rung `nike` (604 documents), retriever `lexical` (no ANN strategy) — a
reader's machine gives a different number.

