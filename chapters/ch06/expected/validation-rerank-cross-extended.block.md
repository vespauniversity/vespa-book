_Profile `phased`, phase `global` (`ranking.globalPhase.rerankCount`), candidate depth 400, other phase (`ranking.rerankCount`) pinned at 0, reference count 10_

| rerank count | ndcg@10 | ndcg@10 vs floor (0) | ndcg@10 vs reference (10) | recall@10 | recall@100 | mrr | p50 | p95 | p99 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.482 | — | -0.014 [-0.019, -0.007], real | 0.332 | 0.691 | 0.778 | 112.9 ms | 123.1 ms | 131.1 ms |
| 5 | 0.489 | +0.007 [+0.002, +0.012], real | -0.007 [-0.009, -0.004], real | 0.332 | 0.691 | 0.798 | 515.6 ms | 526.5 ms | 535.9 ms |
| 10 | 0.495 | +0.014 [+0.007, +0.019], real | — | 0.332 | 0.691 | 0.804 | 943.3 ms | 957.5 ms | 972.7 ms |
| 25 | 0.511 | +0.030 [+0.020, +0.039], real | +0.016 [+0.009, +0.023], real | 0.343 | 0.691 | 0.806 | 2224.7 ms | 2245.3 ms | 2267.3 ms |

