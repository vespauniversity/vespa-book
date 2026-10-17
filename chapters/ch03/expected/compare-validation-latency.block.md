| run | p50 | p95 |
|---|---|---|
| validation-default | 4.9 ms | 7.2 ms |
| validation-bm25_title | 4.7 ms | 6.6 ms |
| validation-bm25_all | 4.9 ms | 6.7 ms |
| validation-bm25_weighted | 4.8 ms | 6.5 ms |
| validation-bm25_tuned-k1only | 4.7 ms | 6.5 ms |
| validation-bm25_tuned | 4.7 ms | 6.5 ms |

Warm readings. The whole query set was run once and discarded before any pass
was measured, so they describe a container whose index has already been
touched. A cold container answers its first queries more slowly; this book does
not measure by how much, or for how long.

