| candidates (N) | fetch p50 (ms) | fetch p95 (ms) | ship+score p50 (ms) | ship+score p95 (ms) | external total p50 (ms) | in-engine p50 (ms) | in-engine p95 (ms) | bytes/request p50 |
|---|---|---|---|---|---|---|---|---|
| 10 | 71.3 ms | 75.7 ms | 2.5 ms | 3.7 ms | 73.9 ms | 68.8 ms | 72.7 ms | 6270 |
| 25 | 72.0 ms | 76.3 ms | 2.7 ms | 4.0 ms | 74.9 ms | 69.7 ms | 73.6 ms | 15605 |
| 100 | 77.4 ms | 82.6 ms | 2.0 ms | 3.5 ms | 79.7 ms | 73.2 ms | 78.8 ms | 61264 |

Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher Desktop). The mock model service runs on the host, not inside the container VM.

