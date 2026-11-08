| run | p50 | p95 |
|---|---|---|
| phased_h10 | 927.8 ms | 940.2 ms |
| ltr_global | 921.3 ms | 934.1 ms |
| ltr_global_t400 | 922.1 ms | 940.0 ms |

Warm readings. The whole query set was run once and discarded before any pass
was measured, so they describe a container whose index has already been
touched. A cold container answers its first queries more slowly; this book does
not measure by how much, or for how long.

