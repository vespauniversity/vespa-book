| setting | p50 | p95 |
|---|---|---|
| exact | 14.9 ms | 17.4 ms |
| HNSW, default | 12.6 ms | 15.2 ms |
| HNSW, +20 explored | 12.7 ms | 15.3 ms |
| HNSW, +100 explored | 12.9 ms | 15.5 ms |
| HNSW, +500 explored | 14.0 ms | 16.5 ms |
| HNSW, default | 12.6 ms | 15.3 ms |

Median of 3 warm passes over 735 queries, after one warm-up pass over the whole
query set was discarded. Warm readings. The whole query set was run once and
discarded before any pass was measured, so they describe a container whose
index has already been touched. A cold container answers its first queries more
slowly; this book does not measure by how much, or for how long.

