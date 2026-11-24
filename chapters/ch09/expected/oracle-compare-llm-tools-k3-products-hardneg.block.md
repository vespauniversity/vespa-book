| evidence | success | queries per task, p50 |
|---|---|---|
| retrieved by the planner | 0.851 ± 0.032 | 2 |
| the oracle's products supplied | 0.983 ± 0.012 | 0 |
| difference | +0.132 [+0.104, +0.162], real | |

n = 470. Difference = the oracle's products supplied minus evidence retrieved, question by question, with a bootstrap interval. Supplied: every product of the question's oracle, with its title and brand, in the evidence before the first turn. Hard-negative subset: the 470 questions, of 872, whose pool holds at least one product labelled irrelevant (I).

