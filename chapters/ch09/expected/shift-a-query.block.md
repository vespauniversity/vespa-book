| | human | agent |
|---|---|---|
| queries | 1,050 | 1,300 |
| characters (median / mean / max) | 22 / 23.3 / 115 | 64 / 65.8 / 189 |
| words (median / mean / max) | 4 / 4.0 / 24 | 10 / 10.8 / 33 |
| vocabulary overlap | 0.960 | 0.998 |

Descriptive only. Human queries: every query of the test split (1050). Agent queries: every search and group query in the trajectory file (1300). Vocabulary overlap = the share of a query's words that occur in some product title of the corpus, averaged over queries. 265 `query` statements put no words in a `query` parameter or an `embed(…)` and are not described: their words, where they have any, are written into the YQL itself (`title contains …`), and the rest are field conditions only.

