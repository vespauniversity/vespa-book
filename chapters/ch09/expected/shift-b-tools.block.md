| profile | agent statements, ndcg@10: mean (p25 / p50 / p75) | human query in the pool | human query over the corpus | agent − human, in the pool | agent − human, over the corpus |
|---|---|---|---|---|---|
| bm25_tuned | 0.761 (0.655 / 0.795 / 0.910), n = 1,622 | 0.699 (0.593 / 0.742 / 0.855) | 0.444 (0.174 / 0.462 / 0.698) | +0.062 [+0.051, +0.073], real | +0.324 [+0.307, +0.341], real |
| semantic | 0.773 (0.666 / 0.805 / 0.919), n = 1,622 | 0.735 (0.622 / 0.776 / 0.875) | 0.459 (0.223 / 0.473 / 0.702) | +0.042 [+0.032, +0.053], real | +0.331 [+0.315, +0.347], real |
| hybrid_rrf | 0.777 (0.678 / 0.807 / 0.922), n = 1,622 | 0.730 (0.622 / 0.779 / 0.870) | 0.474 (0.237 / 0.496 / 0.714) | +0.050 [+0.039, +0.060], real | +0.314 [+0.298, +0.329], real |
| phased | 0.777 (0.683 / 0.808 / 0.923), n = 1,622 | 0.735 (0.637 / 0.782 / 0.871) | 0.501 (0.270 / 0.545 / 0.745) | +0.046 [+0.036, +0.057], real | +0.288 [+0.272, +0.304], real |

| profile | agent statements, recall@100: mean (p25 / p50 / p75) | human query in the pool | human query over the corpus | agent − human, in the pool | agent − human, over the corpus |
|---|---|---|---|---|---|
| bm25_tuned | 0.926 (0.938 / 1.000 / 1.000), n = 1,622 | 0.919 (0.933 / 1.000 / 1.000) | 0.638 (0.438 / 0.688 / 0.900) | +0.013 [+0.003, +0.023], real | +0.314 [+0.298, +0.329], real |
| semantic | 1.000 (1.000 / 1.000 / 1.000), n = 1,622 | 1.000 (1.000 / 1.000 / 1.000) | 0.691 (0.533 / 0.769 / 0.933) | +0.000 [+0.000, +0.000], inside the noise | +0.339 [+0.325, +0.354], real |
| hybrid_rrf | 1.000 (1.000 / 1.000 / 1.000), n = 1,622 | 1.000 (1.000 / 1.000 / 1.000) | 0.680 (0.500 / 0.750 / 0.933) | +0.000 [+0.000, +0.000], inside the noise | +0.347 [+0.333, +0.362], real |
| phased | 1.000 (1.000 / 1.000 / 1.000), n = 1,622 | 1.000 (1.000 / 1.000 / 1.000) | 0.680 (0.500 / 0.750 / 0.933) | +0.000 [+0.000, +0.000], inside the noise | +0.347 [+0.333, +0.362], real |

n = 1622 statements from 871 questions of the tools surface, k = 3; left out: 3 refused by the engine when the agent sent them, 1 with no word to score in a `query` argument, a `query` parameter or an `embed(…)` (words written into the YQL itself, as `title contains …`, are not read), 0 grouping calls. Each statement's words, the agent's own conditions dropped, and its question's human query are sent as the book's request for each profile (100 hits) and scored against that question's human judgements: in the question's pool, the paired comparison (same candidates, same labels, only the wording differs), and the human query also over the whole corpus, as context. Mean, then p25 / p50 / p75; difference = agent minus the human query of the same question, per statement, with a bootstrap interval. Profile order by mean ndcg@10, read off the means with no profile-against-profile interval - agent: phased > hybrid_rrf > semantic > bm25_tuned; human in the pool: semantic > phased > hybrid_rrf > bm25_tuned; human over the corpus: phased > hybrid_rrf > semantic > bm25_tuned.

