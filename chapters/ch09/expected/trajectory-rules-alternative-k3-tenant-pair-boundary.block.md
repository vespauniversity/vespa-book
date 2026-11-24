| | |
|---|---|
| run | rules, k = 3, tools surface, shape `alternative` |
| boundary | two sellers per question: the anchor product's and the oracle seller with the most products in the oracle |
| questions | 872 |
| answerable: an oracle product inside the boundary | 872 of 872 (1.000) |
| oracle share inside the boundary, p25 / p50 / p75 | 0.143 / 0.214 / 0.333 |
| success | 0.952 ± 0.014 (widest for this n: ± 0.033) |
| tool statuses | filtered 11, ok 1729, over_constrained 4 |
| `filtered` statuses | 11 over 11 questions |
| after a `filtered`, the next step | final 11 |
| questions with a `filtered` that went on to an ok search | 0 of 11 |
| recovered: met a `filtered`, answer in the oracle | 0 of 11 |
| no `filtered`, answer in the oracle | 830 of 861 |

n = 872. The boundary is the `tenant` each question ran under; the sellers of the oracle's products come from the build, so the answerable count is the ceiling of success under this boundary and needs no planner. The success interval is 1.96 * sqrt(p(1-p)/n).

