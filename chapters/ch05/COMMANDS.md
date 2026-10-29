# ch05 COMMANDS

One line per command exactly as run, one line per file it wrote.

```
./bootstrap.sh ch05
```
wrote nothing (state check only; `4/5 application` redeployed as expected, `5/5 documents` skipped — 101,341, `title_embedding` present; full output `chapters/ch05/review/bootstrap-step5-start.txt`)

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --retriever lexical --ranking bm25_tuned --label validation-bm25_tuned --out chapters/ch05/expected/validation-bm25_tuned.json > chapters/ch05/expected/validation-bm25_tuned.block.md
```
wrote `chapters/ch05/expected/validation-bm25_tuned.json`, `chapters/ch05/expected/validation-bm25_tuned.block.md` (ndcg@10 0.437, recall@10 0.297, recall@100 0.625, mrr 0.744; field check passed)

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --retriever semantic --ranking semantic --label validation-semantic --out chapters/ch05/expected/validation-semantic.json > chapters/ch05/expected/validation-semantic.block.md
```
wrote `chapters/ch05/expected/validation-semantic.json`, `chapters/ch05/expected/validation-semantic.block.md` (ndcg@10 0.451, recall@10 0.308, recall@100 0.679, mrr 0.747; field check passed)

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --retriever hybrid --ranking hybrid_rrf --label validation-hybrid_rrf --out chapters/ch05/expected/validation-hybrid_rrf.json > chapters/ch05/expected/validation-hybrid_rrf.block.md
```
wrote `chapters/ch05/expected/validation-hybrid_rrf.json`, `chapters/ch05/expected/validation-hybrid_rrf.block.md` (ndcg@10 0.467, recall@10 0.320, recall@100 0.669, mrr 0.760; field check passed)

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --retriever hybrid --ranking hybrid_starved --label validation-hybrid_starved --out chapters/ch05/expected/validation-hybrid_starved.json > chapters/ch05/expected/validation-hybrid_starved.block.md
```
wrote `chapters/ch05/expected/validation-hybrid_starved.json`, `chapters/ch05/expected/validation-hybrid_starved.block.md` (ndcg@10 0.464, recall@10 0.316, recall@100 0.632, mrr 0.758; field check passed)

```
.venv/bin/python chapters/ch05/alpha_sweep.py --split validation --out chapters/ch05/expected/validation-alpha-sweep.json > chapters/ch05/expected/validation-alpha-sweep.block.md
```
wrote `chapters/ch05/expected/validation-alpha-sweep.json`, `chapters/ch05/expected/validation-alpha-sweep.block.md` (default alphas 0.0–1.0 incl. both endpoints; baseline 0.3 first 0.481 / last 0.481, +0.000 inside the noise; largest row 0.482 at alpha 0.4, which the sweep cannot tell apart from 0.3 and 0.5 — no winner named; field check: `build`/`deployed_embedders`/`host` present, `latency_conditions`/`settled` absent — the sweep measures quality only, so there is no timing to condition)

```
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking hybrid_rrf --hits 5 --block features > chapters/ch05/expected/features-running-shoes-hybrid_rrf.block.md
```
wrote `chapters/ch05/expected/features-running-shoes-hybrid_rrf.block.md` (top hit "Nike Women's Running Shoes, Black/White, 5 us", lexical 12.249, vector 0.805; title and lexical/vector columns non-empty across all 5 rows)

```
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking hybrid_linear --param 'input.query(alpha)=0.3' --hits 5 --block features > chapters/ch05/expected/features-running-shoes-hybrid_linear.block.md
```
wrote `chapters/ch05/expected/features-running-shoes-hybrid_linear.block.md` (top hit "Haforever Men's Running Shoes...", lexical 11.918, vector 0.819; alpha is `hybrid_linear`'s default alpha (0.3), which the sweep gave no reason to move — this is the worked-query example, not the test-split evaluation)

```
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking hybrid_starved --hits 5 --block features > chapters/ch05/expected/features-running-shoes-hybrid_starved.block.md
```
wrote `chapters/ch05/expected/features-running-shoes-hybrid_starved.block.md` (top hit "Nike Women's Running Shoes, Black/White, 5 us", lexical 12.249, vector 0.805; title and lexical/vector columns non-empty across all 5 rows)

<!-- from here on: `latency_conditions`/`settled` are required only of reports that carry timings; alpha = 0.3 for hybrid_linear everywhere; the generator context is built under hybrid_rrf -->

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --retriever hybrid --ranking hybrid_linear --param 'input.query(alpha)=0.3' --label validation-hybrid_linear --out chapters/ch05/expected/validation-hybrid_linear.json > chapters/ch05/expected/validation-hybrid_linear.block.md
```
wrote `chapters/ch05/expected/validation-hybrid_linear.json`, `chapters/ch05/expected/validation-hybrid_linear.block.md` (ndcg@10 0.481, recall@10 0.331, recall@100 0.669, mrr 0.779; field check passed)

```
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --retriever lexical --ranking bm25_tuned --label test-bm25_tuned --out chapters/ch05/expected/test-bm25_tuned.json > chapters/ch05/expected/test-bm25_tuned.block.md
```
wrote `chapters/ch05/expected/test-bm25_tuned.json`, `chapters/ch05/expected/test-bm25_tuned.block.md` (ndcg@10 0.443, recall@10 0.312, recall@100 0.644, mrr 0.756; field check passed)

```
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --retriever semantic --ranking semantic --label test-semantic --out chapters/ch05/expected/test-semantic.json > chapters/ch05/expected/test-semantic.block.md
```
wrote `chapters/ch05/expected/test-semantic.json`, `chapters/ch05/expected/test-semantic.block.md` (ndcg@10 0.454, recall@10 0.320, recall@100 0.687, mrr 0.748; field check passed)

```
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --retriever hybrid --ranking hybrid_rrf --label test-hybrid_rrf --out chapters/ch05/expected/test-hybrid_rrf.json > chapters/ch05/expected/test-hybrid_rrf.block.md
```
wrote `chapters/ch05/expected/test-hybrid_rrf.json`, `chapters/ch05/expected/test-hybrid_rrf.block.md` (ndcg@10 0.470, recall@10 0.335, recall@100 0.683, mrr 0.781; field check passed)

```
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --retriever hybrid --ranking hybrid_linear --param 'input.query(alpha)=0.3' --label test-hybrid_linear --out chapters/ch05/expected/test-hybrid_linear.json > chapters/ch05/expected/test-hybrid_linear.block.md
```
wrote `chapters/ch05/expected/test-hybrid_linear.json`, `chapters/ch05/expected/test-hybrid_linear.block.md` (ndcg@10 0.486, recall@10 0.344, recall@100 0.683, mrr 0.784; field check passed)

```
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --retriever hybrid --ranking hybrid_starved --label test-hybrid_starved --out chapters/ch05/expected/test-hybrid_starved.json > chapters/ch05/expected/test-hybrid_starved.block.md
```
wrote `chapters/ch05/expected/test-hybrid_starved.json`, `chapters/ch05/expected/test-hybrid_starved.block.md` (ndcg@10 0.470, recall@10 0.334, recall@100 0.650, mrr 0.779; field check passed)

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/validation-bm25_tuned.json chapters/ch05/expected/validation-hybrid_rrf.json chapters/ch05/expected/validation-hybrid_linear.json chapters/ch05/expected/validation-hybrid_starved.json chapters/ch05/expected/validation-semantic.json --baseline validation-bm25_tuned --block comparison --out chapters/ch05/expected/compare-validation-vs-tuned.json > chapters/ch05/expected/compare-validation-vs-tuned.block.md
```
wrote `chapters/ch05/expected/compare-validation-vs-tuned.json`, `chapters/ch05/expected/compare-validation-vs-tuned.block.md` (vs bm25_tuned: hybrid_linear ndcg@10 +0.044 real, hybrid_rrf +0.030 real, hybrid_starved +0.027 real, semantic +0.014 inside the noise; recall@100 real for hybrid_rrf/hybrid_linear/semantic, hybrid_starved +0.007 real but small)

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/validation-semantic.json chapters/ch05/expected/validation-hybrid_rrf.json chapters/ch05/expected/validation-hybrid_linear.json chapters/ch05/expected/validation-hybrid_starved.json --baseline validation-semantic --block comparison --out chapters/ch05/expected/compare-validation-vs-semantic.json > chapters/ch05/expected/compare-validation-vs-semantic.block.md
```
wrote `chapters/ch05/expected/compare-validation-vs-semantic.json`, `chapters/ch05/expected/compare-validation-vs-semantic.block.md` (vs semantic: hybrid_linear ndcg@10 +0.030 real, hybrid_rrf +0.016 real, hybrid_starved +0.013 real; recall@100 not real for hybrid_rrf/hybrid_linear, real loss for hybrid_starved -0.046)

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/validation-hybrid_linear.json chapters/ch05/expected/validation-hybrid_rrf.json --baseline validation-hybrid_linear --block comparison --out chapters/ch05/expected/compare-validation-rrf-vs-linear.json > chapters/ch05/expected/compare-validation-rrf-vs-linear.block.md
```
wrote `chapters/ch05/expected/compare-validation-rrf-vs-linear.json`, `chapters/ch05/expected/compare-validation-rrf-vs-linear.block.md` (hybrid_rrf vs hybrid_linear baseline: ndcg@10 -0.014 real (linear ahead), recall@100 +0.000 inside the noise — same union candidate set)

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/validation-hybrid_rrf.json chapters/ch05/expected/validation-hybrid_starved.json --baseline validation-hybrid_rrf --block comparison --out chapters/ch05/expected/compare-validation-starved-vs-rrf.json > chapters/ch05/expected/compare-validation-starved-vs-rrf.block.md
```
wrote `chapters/ch05/expected/compare-validation-starved-vs-rrf.json`, `chapters/ch05/expected/compare-validation-starved-vs-rrf.block.md` (hybrid_starved vs hybrid_rrf baseline: ndcg@10 -0.003 real, recall@100 -0.037 real — the starved first phase loses recall@100)

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/validation-bm25_tuned.json chapters/ch05/expected/validation-semantic.json chapters/ch05/expected/validation-hybrid_rrf.json chapters/ch05/expected/validation-hybrid_linear.json chapters/ch05/expected/validation-hybrid_starved.json --baseline validation-bm25_tuned --block evaluations > chapters/ch05/expected/compare-validation-evaluations.block.md
```
wrote `chapters/ch05/expected/compare-validation-evaluations.block.md` (five-row quality table, the same figures as the five validation reports above)

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/test-bm25_tuned.json chapters/ch05/expected/test-hybrid_rrf.json chapters/ch05/expected/test-hybrid_linear.json chapters/ch05/expected/test-hybrid_starved.json chapters/ch05/expected/test-semantic.json --baseline test-bm25_tuned --block comparison --out chapters/ch05/expected/compare-test-vs-tuned.json > chapters/ch05/expected/compare-test-vs-tuned.block.md
```
wrote `chapters/ch05/expected/compare-test-vs-tuned.json`, `chapters/ch05/expected/compare-test-vs-tuned.block.md` (vs bm25_tuned: hybrid_linear ndcg@10 +0.043 real, hybrid_starved +0.027 real, hybrid_rrf +0.027 real, semantic +0.012 inside the noise; recall@100 real for hybrid_rrf/hybrid_linear/semantic, hybrid_starved +0.006 real but small)

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/test-semantic.json chapters/ch05/expected/test-hybrid_rrf.json chapters/ch05/expected/test-hybrid_linear.json chapters/ch05/expected/test-hybrid_starved.json --baseline test-semantic --block comparison --out chapters/ch05/expected/compare-test-vs-semantic.json > chapters/ch05/expected/compare-test-vs-semantic.block.md
```
wrote `chapters/ch05/expected/compare-test-vs-semantic.json`, `chapters/ch05/expected/compare-test-vs-semantic.block.md` (vs semantic: hybrid_linear ndcg@10 +0.032 real, hybrid_starved +0.016 real, hybrid_rrf +0.016 real; recall@100 not real for hybrid_rrf/hybrid_linear, real loss for hybrid_starved -0.037)

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/test-hybrid_linear.json chapters/ch05/expected/test-hybrid_rrf.json --baseline test-hybrid_linear --block comparison --out chapters/ch05/expected/compare-test-rrf-vs-linear.json > chapters/ch05/expected/compare-test-rrf-vs-linear.block.md
```
wrote `chapters/ch05/expected/compare-test-rrf-vs-linear.json`, `chapters/ch05/expected/compare-test-rrf-vs-linear.block.md` (hybrid_rrf vs hybrid_linear baseline: ndcg@10 -0.016 real (linear ahead), recall@100 +0.000 inside the noise)

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/test-hybrid_rrf.json chapters/ch05/expected/test-hybrid_starved.json --baseline test-hybrid_rrf --block comparison --out chapters/ch05/expected/compare-test-starved-vs-rrf.json > chapters/ch05/expected/compare-test-starved-vs-rrf.block.md
```
wrote `chapters/ch05/expected/compare-test-starved-vs-rrf.json`, `chapters/ch05/expected/compare-test-starved-vs-rrf.block.md` (hybrid_starved vs hybrid_rrf baseline: ndcg@10 +0.000 inside the noise, recall@100 -0.033 real)

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/test-bm25_tuned.json chapters/ch05/expected/test-semantic.json chapters/ch05/expected/test-hybrid_rrf.json chapters/ch05/expected/test-hybrid_linear.json chapters/ch05/expected/test-hybrid_starved.json --baseline test-bm25_tuned --block evaluations > chapters/ch05/expected/compare-test-evaluations.block.md
```
wrote `chapters/ch05/expected/compare-test-evaluations.block.md` (five-row quality table, the same figures as the five test reports above)

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/validation-bm25_tuned.json chapters/ch05/expected/validation-semantic.json chapters/ch05/expected/validation-hybrid_rrf.json chapters/ch05/expected/validation-hybrid_linear.json chapters/ch05/expected/validation-hybrid_starved.json --baseline validation-bm25_tuned --block evaluations-latency > chapters/ch05/expected/compare-validation-latency.block.md
```
wrote `chapters/ch05/expected/compare-validation-latency.block.md` (p50/p95 ms: bm25_tuned 4.5/6.5, semantic 14.0/16.9, hybrid_rrf 14.7/18.4, hybrid_linear 14.6/18.1, hybrid_starved 14.6/18.1 — warm, Apple M4 Pro / Rancher Desktop VM 4 CPU 10 GB; candidate count union at targetHits 100, rerank-count 100)

```
.venv/bin/python chapters/ch05/wider_net.py --split validation --alpha 0.3 --out chapters/ch05/expected/validation-wider-net.json > chapters/ch05/expected/validation-wider-net.block.md
```
wrote `chapters/ch05/expected/validation-wider-net.json`, `chapters/ch05/expected/validation-wider-net.block.md` (vector-only relevant 1,617, keyword-only relevant 917; hybrid_rrf 36/625 vector-only in top10/top100, 52/755 keyword-only; hybrid_linear 105/625, 55/755; hybrid_starved 22/107, 61/897; semantic 315/1602, 18/52; vs ch04's validation-overlap 1,613/916 — both within a few units)

```
.venv/bin/python chapters/ch05/wider_net.py --split test --alpha 0.3 --out chapters/ch05/expected/test-wider-net.json > chapters/ch05/expected/test-wider-net.block.md
```
wrote `chapters/ch05/expected/test-wider-net.json`, `chapters/ch05/expected/test-wider-net.block.md` (vector-only relevant 2,158, keyword-only relevant 1,291; hybrid_rrf 24/797, 73/1091; hybrid_linear 112/797, 74/1091; hybrid_starved 15/136, 90/1258; semantic 420/2136, 27/52; vs ch04's test-overlap 2,153/1,313 — keyword-only differs by 22, the largest move of any cell)

```
.venv/bin/python chapters/ch05/context.py --split validation --depths 1 3 5 10 20 --ranking hybrid_rrf --out chapters/ch05/expected/validation-context.json > chapters/ch05/expected/validation-context.block.md
```
wrote `chapters/ch05/expected/validation-context.json`, `chapters/ch05/expected/validation-context.block.md` (depths 1/3/5/10/20: mean bytes 170/524/894/1826/3700, exact-match share 52.4%/71.4%/76.5%/83.1%/87.9%, dropped 0/18/33/62/115; all 735 queries have an exact match to find; field check passed)

```
.venv/bin/python chapters/ch05/context.py --query "running shoes" --ranking hybrid_rrf > chapters/ch05/expected/context-running-shoes.block.md
```
wrote `chapters/ch05/expected/context-running-shoes.block.md` (5 entries, every line carries a product id, e.g. `[B078JRKH6X] Nike Women's Running Shoes, Black/White, 5 us`)

