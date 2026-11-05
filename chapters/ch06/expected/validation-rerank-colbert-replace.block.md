_Profile `phased_replace`, phase `second` (`ranking.rerankCount`), candidate depth 400, other phase (`ranking.globalPhase.rerankCount`) pinned at 0, reference count 100_

| rerank count | ndcg@10 | ndcg@10 vs floor (0) | ndcg@10 vs reference (100) | recall@10 | recall@100 | mrr | p50 | p95 | p99 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.482 | — | +0.014 [+0.002, +0.026], real | 0.332 | 0.691 | 0.778 | 97.0 ms | 106.2 ms | 111.2 ms |
| 5 | 0.481 | -0.000 [-0.005, +0.005], inside the noise | +0.014 [+0.004, +0.024], real | 0.332 | 0.691 | 0.786 | 98.1 ms | 107.8 ms | 113.3 ms |
| 25 | 0.474 | -0.008 [-0.018, +0.003], inside the noise | +0.007 [+0.002, +0.011], real | 0.323 | 0.691 | 0.773 | 97.2 ms | 106.8 ms | 115.3 ms |
| 50 | 0.471 | -0.011 [-0.022, +0.001], inside the noise | +0.003 [+0.000, +0.006], real | 0.321 | 0.691 | 0.769 | 96.6 ms | 105.2 ms | 111.7 ms |
| 100 | 0.468 | -0.014 [-0.026, -0.002], real | — | 0.318 | 0.691 | 0.767 | 96.8 ms | 105.0 ms | 110.6 ms |
| 200 | 0.468 | -0.014 [-0.026, -0.002], real | +0.000 [-0.002, +0.002], inside the noise | 0.317 | 0.675 | 0.769 | 98.9 ms | 108.5 ms | 115.5 ms |
| 400 | 0.468 | -0.014 [-0.027, -0.002], real | -0.000 [-0.002, +0.002], inside the noise | 0.317 | 0.667 | 0.768 | 101.0 ms | 113.2 ms | 122.1 ms |

