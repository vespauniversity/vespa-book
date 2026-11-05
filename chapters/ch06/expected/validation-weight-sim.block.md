_Profile `phased`, input `query(w_sim)`, second-phase count 100 (`ranking.rerankCount`), global-phase count 0 (`ranking.globalPhase.rerankCount`), candidate depth 400_

| w_sim | ndcg@10 | ndcg@10 vs floor (0.0) | ndcg@10 vs best (0.002) | recall@10 | recall@100 | mrr | p50 |
|---|---|---|---|---|---|---|---|
| 0.0 | 0.482 | — | -0.013 [-0.019, -0.007], real | 0.332 | 0.691 | 0.778 | 113.9 ms |
| 0.002 | 0.494 | +0.013 [+0.007, +0.019], real | — | 0.338 | 0.691 | 0.785 | 115.1 ms |
| 0.005 | 0.488 | +0.007 [-0.002, +0.015], inside the noise | -0.006 [-0.010, -0.001], real | 0.333 | 0.691 | 0.782 | 115.6 ms |
| 0.01 | 0.481 | -0.000 [-0.010, +0.010], inside the noise | -0.013 [-0.019, -0.007], real | 0.328 | 0.691 | 0.775 | 116.3 ms |
| 0.02 | 0.477 | -0.005 [-0.016, +0.006], inside the noise | -0.018 [-0.026, -0.010], real | 0.324 | 0.691 | 0.775 | 116.2 ms |
| 0.05 | 0.472 | -0.010 [-0.021, +0.002], inside the noise | -0.023 [-0.031, -0.014], real | 0.321 | 0.691 | 0.773 | 116.1 ms |

