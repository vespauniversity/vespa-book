_Profile `phased`, phase `second` (`ranking.rerankCount`), candidate depth 400, other phase (`ranking.globalPhase.rerankCount`) pinned at 0, reference count 100_

| rerank count | ndcg@10 | ndcg@10 vs floor (0) | ndcg@10 vs reference (100) | recall@10 | recall@100 | mrr | p50 | p95 | p99 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.482 | — | -0.013 [-0.019, -0.007], real | 0.332 | 0.691 | 0.778 | 115.0 ms | 125.3 ms | 132.6 ms |
| 5 | 0.485 | +0.003 [-0.000, +0.007], inside the noise | -0.009 [-0.014, -0.005], real | 0.332 | 0.691 | 0.786 | 115.5 ms | 127.0 ms | 137.1 ms |
| 25 | 0.494 | +0.012 [+0.006, +0.018], real | -0.000 [-0.001, +0.001], inside the noise | 0.338 | 0.691 | 0.785 | 115.0 ms | 125.5 ms | 132.8 ms |
| 50 | 0.494 | +0.013 [+0.007, +0.019], real | +0.000 [-0.000, +0.000], inside the noise | 0.338 | 0.691 | 0.785 | 115.1 ms | 125.5 ms | 134.7 ms |
| 100 | 0.494 | +0.013 [+0.007, +0.019], real | — | 0.338 | 0.691 | 0.785 | 115.7 ms | 126.5 ms | 134.6 ms |
| 200 | 0.494 | +0.012 [+0.006, +0.019], real | -0.000 [-0.000, +0.000], inside the noise | 0.338 | 0.695 | 0.785 | 117.2 ms | 127.9 ms | 136.1 ms |
| 400 | 0.494 | +0.012 [+0.007, +0.019], real | -0.000 [-0.000, +0.000], inside the noise | 0.338 | 0.696 | 0.785 | 120.9 ms | 135.6 ms | 140.9 ms |

