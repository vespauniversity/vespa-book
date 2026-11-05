| run | p50 | p95 |
|---|---|---|
| bm25_tuned | 15.3 ms | 21.1 ms |
| semantic | 23.6 ms | 30.1 ms |
| hybrid_rrf | 27.6 ms | 35.6 ms |
| hybrid_linear | 28.4 ms | 36.2 ms |
| first_stage | 114.5 ms | 125.0 ms |
| phased_title | 323.9 ms | 337.4 ms |
| phased | 947.9 ms | 969.0 ms |

Warm readings. The whole query set was run once and discarded before any pass
was measured, so they describe a container whose index has already been
touched. A cold container answers its first queries more slowly; this book does
not measure by how much, or for how long.

