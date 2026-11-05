_Profile `phased`, input `query(w_sim)`, second-phase count 100 (`ranking.rerankCount`), global-phase count 0 (`ranking.globalPhase.rerankCount`), candidate depth 400_

| w_sim | ndcg@10 | ndcg@10 vs floor (0.0) | ndcg@10 vs best (0.002) | recall@10 | recall@100 | mrr | p50 |
|---|---|---|---|---|---|---|---|
| 0.0 | 0.482 | — | -0.013 [-0.019, -0.007], real | 0.332 | 0.691 | 0.778 | 115.9 ms |
| 0.001 | 0.491 | +0.010 [+0.005, +0.015], real | -0.003 [-0.006, +0.001], inside the noise | 0.337 | 0.691 | 0.783 | 114.7 ms |
| 0.002 | 0.494 | +0.013 [+0.007, +0.019], real | — | 0.338 | 0.691 | 0.785 | 118.5 ms |
| 0.003 | 0.491 | +0.010 [+0.003, +0.017], real | -0.003 [-0.005, -0.000], real | 0.336 | 0.691 | 0.782 | 115.5 ms |
| 0.005 | 0.488 | +0.007 [-0.002, +0.015], inside the noise | -0.006 [-0.010, -0.001], real | 0.333 | 0.691 | 0.782 | 114.2 ms |

