| | |
|---|---|
| run | llm, k = 3, query surface, shape `alternative` |
| boundary | two sellers per question: the anchor product's and the oracle seller with the most products in the oracle |
| questions | 872 |
| answerable: an oracle product inside the boundary | 872 of 872 (1.000) |
| oracle share inside the boundary, p25 / p50 / p75 | 0.143 / 0.214 / 0.333 |
| success | 0.919 ± 0.018 (widest for this n: ± 0.033) |
| tool statuses | filtered 51, malformed 3, ok 1685, over_constrained 31 |
| `filtered` statuses | 51 over 45 questions |
| after a `filtered`, the next step | final 23, query filtered 4, query ok 24 |
| questions with a `filtered` that went on to an ok search | 24 of 45 |
| recovered: met a `filtered`, answer in the oracle | 27 of 45 |
| no `filtered`, answer in the oracle | 774 of 827 |

n = 872. The boundary is the `tenant` each question ran under; the sellers of the oracle's products come from the build, so the answerable count is the ceiling of success under this boundary and needs no planner. The success interval is 1.96 * sqrt(p(1-p)/n).

