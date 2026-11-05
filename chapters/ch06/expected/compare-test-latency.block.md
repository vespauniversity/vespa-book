| run | p50 | p95 |
|---|---|---|
| bm25_tuned | 15.1 ms | 21.1 ms |
| semantic | 24.9 ms | 31.6 ms |
| hybrid_rrf | 27.7 ms | 35.6 ms |
| hybrid_linear | 28.3 ms | 36.3 ms |
| first_stage | 114.4 ms | 125.0 ms |
| phased_title | 324.4 ms | 338.0 ms |
| phased | 949.8 ms | 973.9 ms |

Warm readings. The whole query set was run once and discarded before any pass
was measured, so they describe a container whose index has already been
touched. A cold container answers its first queries more slowly; this book does
not measure by how much, or for how long.

