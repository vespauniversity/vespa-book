| profile named | `llm-tools-alternative-k3` | `llm-query-alternative-k3` | `llm-tools-alternative-k20` | `llm-query-alternative-k20` | `llm-query-alternative-k3-allprofiles` |
|---|---|---|---|---|---|
| `hybrid_rrf` | 0 | 1,028 | 0 | 1,163 | 71 |
| `bm25_tuned` | 23 | 504 | 112 | 440 | 0 |
| `bm25_weighted` | 0 | 0 | 0 | 0 | 310 |
| `bm25_title` | 0 | 0 | 0 | 0 | 280 |
| `semantic` | 58 | 7 | 56 | 3 | 14 |
| `bm25_all` | 0 | 0 | 0 | 0 | 99 |
| no profile named | 1,545 | 26 | 1,427 | 9 | 992 |
| statements | 1,626 | 1,565 | 1,595 | 1,615 | 1,766 |
| questions | 872 | 872 | 872 | 872 | 872 |

Each column is one log: how many statements named each rank profile in their `ranking` argument - every `search` call on the tool surface, every `query` statement on the query surface, refused ones included. A statement that named none ran under `hybrid_rrf`, the default on both surfaces. Grouping calls on the tool surface take no profile and are not counted (1 in all). Counts from one model run per log; no interval.

