_Candidate depth 400, second-phase count 25 (`ranking.rerankCount`), global-phase count 10 (`ranking.globalPhase.rerankCount`)_

| stage | ndcg@10 | ndcg@10 vs previous | recall@100 | p50 | p95 | Δp50 vs previous |
|---|---|---|---|---|---|---|
| first stage alone | 0.482 | — | 0.691 | 114.1 ms | 124.7 ms | — |
| + second phase | 0.494 | +0.012 [+0.006, +0.018], real | 0.691 | 114.2 ms | 125.0 ms | +0.1 ms |
| + global phase | 0.502 | +0.009 [+0.004, +0.013], real | 0.691 | 947.6 ms | 969.0 ms | +833.3 ms |

