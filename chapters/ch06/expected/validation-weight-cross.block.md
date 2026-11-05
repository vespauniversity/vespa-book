_Profile `phased`, input `query(w_cross)`, second-phase count 25 (`ranking.rerankCount`), global-phase count 10 (`ranking.globalPhase.rerankCount`), candidate depth 400_

| w_cross | ndcg@10 | ndcg@10 vs floor (0.0) | ndcg@10 vs best (0.7) | recall@10 | recall@100 | mrr | p50 |
|---|---|---|---|---|---|---|---|
| 0.0 | 0.494 | — | -0.009 [-0.013, -0.004], real | 0.338 | 0.691 | 0.785 | 945.6 ms |
| 0.3 | 0.498 | +0.004 [+0.001, +0.006], real | -0.005 [-0.008, -0.001], real | 0.338 | 0.691 | 0.789 | 944.6 ms |
| 0.5 | 0.499 | +0.005 [+0.002, +0.009], real | -0.003 [-0.006, -0.001], real | 0.338 | 0.691 | 0.793 | 946.1 ms |
| 0.7 | 0.502 | +0.009 [+0.004, +0.013], real | — | 0.338 | 0.691 | 0.800 | 945.8 ms |
| 1.0 | 0.500 | +0.006 [+0.001, +0.013], real | -0.002 [-0.005, +0.001], inside the noise | 0.338 | 0.691 | 0.798 | 947.0 ms |

