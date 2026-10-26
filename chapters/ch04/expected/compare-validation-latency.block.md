| run | p50 | p95 |
|---|---|---|
| validation-bm25_tuned | 4.4 ms | 6.6 ms |
| validation-semantic | 12.9 ms | 15.5 ms |

Warm readings. The whole query set was run once and discarded before any pass
was measured, so they describe a container whose index has already been
touched. A cold container answers its first queries more slowly; this book does
not measure by how much, or for how long.

