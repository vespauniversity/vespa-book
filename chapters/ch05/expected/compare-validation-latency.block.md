| run | p50 | p95 |
|---|---|---|
| validation-bm25_tuned | 4.5 ms | 6.5 ms |
| validation-semantic | 14.0 ms | 16.9 ms |
| validation-hybrid_rrf | 14.7 ms | 18.4 ms |
| validation-hybrid_linear | 14.6 ms | 18.1 ms |
| validation-hybrid_starved | 14.6 ms | 18.1 ms |

Warm readings. The whole query set was run once and discarded before any pass
was measured, so they describe a container whose index has already been
touched. A cold container answers its first queries more slowly; this book does
not measure by how much, or for how long.

