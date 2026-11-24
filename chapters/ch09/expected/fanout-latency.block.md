| loops at once | update stream | p50 | p95 | p99 | requests / s |
|---|---|---|---|---|---|
| 1 | no | 15.0 ms | 31.6 ms | 38.3 ms | 55.5 |
| 2 | no | 15.5 ms | 31.6 ms | 38.6 ms | 109.7 |
| 4 | no | 20.2 ms | 38.6 ms | 48.2 ms | 179.4 |
| 1 | yes | 14.1 ms | 30.9 ms | 37.4 ms | 58.1 |
| 2 | yes | 15.0 ms | 31.6 ms | 37.7 ms | 114.2 |
| 4 | yes | 19.2 ms | 37.9 ms | 48.1 ms | 186.8 |

Replay of the rules planner's requests (1,744 from `chapters/ch10/expected/trajectories/rules-alternative-k3.jsonl`: each search as the planner sent it, inside its question's pool, under `hybrid_rrf`) by N loops at once, each walking the questions in order, for a 60 s window after a 20 s warm-up; client-measured, over the requests that completed inside the window. The update stream is one process re-assigning each product its own `tenant_id` through the document API at a target of 200 updates/s (achieved 200, 200, 200 updates/s in the three cells), so the data does not change while the engine does every write. The model is not involved: this is the engine's side only. One pass per cell on an Apple M4 Pro with a 4 CPU / 10 GB container VM (Rancher Desktop); a reader's machine will give other numbers.

