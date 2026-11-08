| run | p50 | p95 |
|---|---|---|
| first_stage | 115.9 ms | 125.8 ms |
| ltr_second_tiny | 91.1 ms | 101.2 ms |
| ltr_second | 91.3 ms | 101.1 ms |
| ltr_second_offline | 92.0 ms | 102.7 ms |
| ltr_second_mid | 91.5 ms | 100.8 ms |
| ltr_second_large | 96.0 ms | 107.1 ms |
| ltr_second_onnx | 92.4 ms | 102.0 ms |
| phased | 947.3 ms | 970.2 ms |
| ltr_global | 913.5 ms | 922.1 ms |
| ltr_global_200 | 913.8 ms | 923.9 ms |
| ltr_global_onnx | 914.6 ms | 923.7 ms |
| ltr_global_g25 | 2179.5 ms | 2222.7 ms |

Warm readings. The whole query set was run once and discarded before any pass
was measured, so they describe a container whose index has already been
touched. A cold container answers its first queries more slowly; this book does
not measure by how much, or for how long.

