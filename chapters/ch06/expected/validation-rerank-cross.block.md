_Profile `phased`, phase `global` (`ranking.globalPhase.rerankCount`), candidate depth 400, other phase (`ranking.rerankCount`) pinned at 0, reference count 10_

| rerank count | ndcg@10 | ndcg@10 vs floor (0) | ndcg@10 vs reference (10) | recall@10 | recall@100 | mrr | p50 | p95 | p99 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.482 | — | -0.014 [-0.019, -0.007], real | 0.332 | 0.691 | 0.778 | 112.7 ms | 122.7 ms | 132.4 ms |
| 5 | 0.489 | +0.007 [+0.002, +0.012], real | -0.007 [-0.009, -0.004], real | 0.332 | 0.691 | 0.798 | 515.8 ms | 527.0 ms | 532.9 ms |
| 10 | 0.495 | +0.014 [+0.007, +0.019], real | — | 0.332 | 0.691 | 0.804 | 942.4 ms | 953.7 ms | 967.3 ms |

