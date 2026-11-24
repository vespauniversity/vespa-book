| | |
|---|---|
| run | rules, k = 3, tools surface, shape `alternative` |
| boundary | one seller per question, the anchor product's |
| questions | 872 |
| answerable: an oracle product inside the boundary | 0 of 872 (0.000) |
| oracle share inside the boundary, p25 / p50 / p75 | 0.000 / 0.000 / 0.000 |
| success | 0.000 ± 0.000 (widest for this n: ± 0.033) |
| tool statuses | filtered 867, ok 873, over_constrained 4 |
| `filtered` statuses | 867 over 867 questions |
| after a `filtered`, the next step | final 867 |
| questions with a `filtered` that went on to an ok search | 0 of 867 |
| recovered: met a `filtered`, answer in the oracle | 0 of 867 |
| no `filtered`, answer in the oracle | 0 of 5 |

n = 872. The boundary is the `tenant` each question ran under; the sellers of the oracle's products come from the build, so the answerable count is the ceiling of success under this boundary and needs no planner. The success interval is 1.96 * sqrt(p(1-p)/n).

