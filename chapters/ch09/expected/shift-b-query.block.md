| profile | agent statements, ndcg@10: mean (p25 / p50 / p75) | human query in the pool | human query over the corpus | agent − human, in the pool | agent − human, over the corpus |
|---|---|---|---|---|---|
| bm25_tuned | 0.768 (0.661 / 0.804 / 0.915), n = 1,300 | 0.699 (0.592 / 0.742 / 0.855) | 0.445 (0.176 / 0.462 / 0.697) | +0.067 [+0.055, +0.080], real | +0.317 [+0.298, +0.335], real |
| semantic | 0.780 (0.682 / 0.810 / 0.916), n = 1,300 | 0.735 (0.622 / 0.775 / 0.875) | 0.457 (0.223 / 0.471 / 0.702) | +0.045 [+0.033, +0.057], real | +0.325 [+0.307, +0.343], real |
| hybrid_rrf | 0.783 (0.688 / 0.812 / 0.920), n = 1,300 | 0.730 (0.622 / 0.778 / 0.870) | 0.474 (0.237 / 0.496 / 0.714) | +0.053 [+0.042, +0.065], real | +0.303 [+0.285, +0.321], real |
| phased | 0.787 (0.691 / 0.816 / 0.924), n = 1,300 | 0.735 (0.637 / 0.782 / 0.871) | 0.501 (0.270 / 0.545 / 0.745) | +0.051 [+0.039, +0.062], real | +0.282 [+0.264, +0.300], real |

| profile | agent statements, recall@100: mean (p25 / p50 / p75) | human query in the pool | human query over the corpus | agent − human, in the pool | agent − human, over the corpus |
|---|---|---|---|---|---|
| bm25_tuned | 0.935 (0.943 / 1.000 / 1.000), n = 1,300 | 0.918 (0.933 / 1.000 / 1.000) | 0.638 (0.438 / 0.688 / 0.900) | +0.019 [+0.008, +0.032], real | +0.300 [+0.284, +0.317], real |
| semantic | 1.000 (1.000 / 1.000 / 1.000), n = 1,300 | 1.000 (1.000 / 1.000 / 1.000) | 0.690 (0.507 / 0.750 / 0.933) | +0.000 [+0.000, +0.000], inside the noise | +0.313 [+0.298, +0.329], real |
| hybrid_rrf | 1.000 (1.000 / 1.000 / 1.000), n = 1,300 | 1.000 (1.000 / 1.000 / 1.000) | 0.679 (0.500 / 0.750 / 0.933) | +0.000 [+0.000, +0.000], inside the noise | +0.325 [+0.310, +0.341], real |
| phased | 1.000 (1.000 / 1.000 / 1.000), n = 1,300 | 1.000 (1.000 / 1.000 / 1.000) | 0.679 (0.500 / 0.750 / 0.933) | +0.000 [+0.000, +0.000], inside the noise | +0.325 [+0.310, +0.341], real |

n = 1300 statements from 871 questions of the query surface, k = 3; left out: 0 refused by the engine when the agent sent them, 265 with no word to score in a `query` argument, a `query` parameter or an `embed(…)` (words written into the YQL itself, as `title contains …`, are not read), 0 grouping calls. Each statement's words, the agent's own conditions dropped, and its question's human query are sent as the book's request for each profile (100 hits) and scored against that question's human judgements: in the question's pool, the paired comparison (same candidates, same labels, only the wording differs), and the human query also over the whole corpus, as context. Mean, then p25 / p50 / p75; difference = agent minus the human query of the same question, per statement, with a bootstrap interval. Profile order by mean ndcg@10, read off the means with no profile-against-profile interval - agent: phased > hybrid_rrf > semantic > bm25_tuned; human in the pool: phased > semantic > hybrid_rrf > bm25_tuned; human over the corpus: phased > hybrid_rrf > semantic > bm25_tuned.

