# Chapter 6 — Multi-Stage Ranking

This directory is the code for Chapter 6 of *Production AI Search with Vespa*. It turns Chapter 5's hybrid application into a three-stage ranking funnel over the same 101,341 products and the same judged queries. Chapter 5's first phase scores every candidate the hybrid request matches. A second phase adds a late-interaction score, MaxSim, to the best 25 on each content node. A global phase, after the results are merged, blends in a cross-encoder's score for the best ten. The chapter chooses each stage's weight and candidate count on validation, measures what each stage adds to NDCG@10 and to latency, logs 52 rank features for every judged product, and checks the result once on test.

The book explains what each step does and why. This page is the practical half: what to run, in the same order as the chapter, what you should see, and what to do when something goes wrong.

## What is in this directory

```
chapters/ch06/
├── app/                                the application package Vespa deploys
│   ├── services.xml                    adds two components: the late-interaction model
│   │                                   (colbert) and the cross-encoder's tokenizer
│   ├── models/
│   │   └── cross_encoder.onnx          the cross-encoder; downloaded by bootstrap.sh, not in git
│   ├── schemas/
│   │   ├── product.sd                  Chapter 5's schema, plus three fields (colbert,
│   │   │                               title_tokens, text_tokens) and the onnx-model cross
│   │   └── product/                    one file per rank profile
│   │       ├── phased.profile          new: the three-stage funnel
│   │       ├── phased_title.profile    new: the same funnel, cross-encoder reading the title only
│   │       ├── phased_replace.profile  new: each reranker replaces the earlier score
│   │       ├── features.profile        new: logs 52 rank features; does not change the ranking
│   │       └── …                       Chapters 3 to 5's profiles, unchanged
│   └── search/query-profiles/
│       └── default.xml                 request defaults, unchanged: bm25_tuned is still the default
├── chapter.toml                        what bootstrap.sh needs for this chapter
├── funnel.py                           the phased request shared by the chapter's tools
├── weight_sweep.py                     varies w_sim or w_cross
├── rerank_sweep.py                     varies the second-phase or global-phase count
├── funnel_budget.py                    what each stage adds over the stage before it
├── features_log.py                     the rank-feature log, one row per judged pair
├── wider_net.py                        where the pairs only one retrieval side found end up
├── scripts/bg_run.sh                   optional helper for running commands in the background
├── COMMANDS.md                         every command, as run for the book
└── expected/                           the book's reference output
```

The feeder, the query tool, the evaluation tool, the comparison tool and the memory tool are shared by every chapter and live in `shared/tools/`.

## What you need

The same as Chapter 5, plus this chapter's two models.

|  | Version used for the book | Notes |
| :---- | :---- | :---- |
| Docker | — | Give it **4 CPUs and 10 GB of memory**. Docker Desktop or Rancher Desktop both work. |
| Python | 3.11 (3.11.13) | Only needed to create the virtual environment. |
| Vespa CLI | 8.562.17 | macOS: `brew install vespa-cli`. Linux and Windows: the Vespa GitHub releases page. |
| Retrieval embedder | `BAAI/bge-small-en-v1.5`, commit `5c38ec7c` | The same model as Chapters 4 and 5. It is still the only model that retrieves anything. |
| Late-interaction model | `colbert-ir/colbertv2.0`, commit `c1e84128` | New. Downloaded by the container from Hugging Face when the application is deployed. |
| Cross-encoder | `cross-encoder/ms-marco-MiniLM-L6-v2`, commit `233902d2` | New. `bootstrap.sh` downloads the model file into `app/models/` and checks its sha256 before deploying; the container downloads its tokenizer. |
| Network | — | Access to Hugging Face, for the two new models, and for the dataset if it is not already cached. |

Every pinned version is listed in `docs/pins.md` at the repository root.

## Run it

From the repository root:

```
./bootstrap.sh ch06
```

If you are continuing from Chapter 5, this downloads the cross-encoder if it is not already there, deploys this chapter's application package (three new fields, two new components, four new rank profiles), and feeds the whole catalogue again. The three new fields are computed as each document is written, so every product has to be fed once more. The script checks this by sending one query under `phased` and reading its `max_sim` match-feature: zero means no product has a `colbert` field yet, and it feeds.

If you are starting with this chapter, add `--fresh`: it removes any earlier virtual environment and Vespa container and builds everything from the beginning.

The deployment prints the same warning as in Chapter 5, about `document-summary 'context'`. That is expected. No other warning appears.

On the reference machine (Apple M4 Pro, container VM with 4 CPUs and 10 GB), continuing from Chapter 5 took 29 minutes 35 seconds, almost all of it the feed, at 58 documents per second. Chapter 4's feed ran at about 210 documents per second; the late-interaction model now runs on every title as well. A fresh run took 31 minutes 4 seconds, and a first run that also had to download the dataset took 44 minutes 2 seconds. Running `./bootstrap.sh ch06` again afterwards only redeploys, in about 13 seconds. Your timings will differ.

A successful run ends with this state:

```
== at the start of ch06
   build      builds/esci-us-hard-book-s42-kdd-v4
   image      vespaengine/vespa:8.751.13
   documents  101341
   embedders  embedder=BAAI/bge-small-en-v1.5@5c38ec7c colbert=colbert-ir/colbertv2.0@c1e84128
```

The last line now names both embedding components.

## The commands in this chapter

The steps below follow the chapter, section by section. Run them from the repository root after `bootstrap.sh` has finished.

Most commands save their result in `expected/`, replacing the book's copy of that file, so that `git diff chapters/ch06/expected/` shows how your run compares with the book's. To put the book's files back, run `git checkout chapters/ch06/expected/`.

**Budget your time.** Every request in this chapter returns 400 hits, and a request that reaches the cross-encoder takes about a second on the reference machine. The sweeps that run the cross-encoder take hours. They are marked below.

**Running long commands in the background.** The two long cross-encoder sweeps below also show an optional `bg_run` command. From the repository root, load the helper once in each terminal:

```bash
source chapters/ch06/scripts/bg_run.sh
```

To run any other command in the background, use `bg_run COMMAND [ARGUMENTS...]`. For commands with output redirection, use `bg_run bash -c 'COMMAND > output-file'` so the output is redirected inside the background job.

The helper prints a folder under `logs/` with the job's output, PID and status. Replace the folder below with the one it prints:

```bash
tail -f logs/bg-XXXXXXXX/output.log
cat logs/bg-XXXXXXXX/status.txt
```

`State: COMPLETED` with `Exit code: 0` means the command succeeded; `State: FAILED` means to check `output.log`. Wait for completion before rendering its table or starting the next measurement. Jobs survive a normal terminal or SSH disconnect; keep the host awake and Vespa running.

**Two options appear on almost every command.**

| Option | What it does |
| :---- | :---- |
| `--hits 400` | Returns 400 hits per query and asks the vector side for 400 nearest neighbors (`targetHits: 400`), so no reranking count in this chapter runs out of candidates. |
| `--reranker-input qt=colbert --reranker-input qt_cross=tokenizer` | Supplies the two query representations the later phases need: `query(qt)`, the query encoded by the late-interaction model, and `query(qt_cross)`, the query tokenized for the cross-encoder. Every `phased`-family request needs both, even when both rerank counts are zero. |

The chapter's own tools (`weight_sweep.py`, `rerank_sweep.py`, `funnel_budget.py`) build that request themselves.

Several tools take two steps: the first command measures and writes a JSON report, and a second command with `--from` and `--block` prints the table from that report without querying anything.

### Why one ranking function is rarely enough

Nothing to run. The two new components are in `app/services.xml`; the three new fields and the `onnx-model cross` declaration are in `app/schemas/product.sd`.

### First-phase scoring across all matches

The first stage on its own: `phased` with both rerank counts set to zero, so only Chapter 5's first phase orders the results. Validation, then test:

```
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking phased --hits 400 --param 'ranking.rerankCount=0' --param 'ranking.globalPhase.rerankCount=0' --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label first_stage --block headline --out chapters/ch06/expected/validation-first_stage.json > chapters/ch06/expected/validation-first_stage.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking phased --hits 400 --param 'ranking.rerankCount=0' --param 'ranking.globalPhase.rerankCount=0' --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label first_stage --block headline --out chapters/ch06/expected/test-first_stage.json > chapters/ch06/expected/test-first_stage.block.md
```

`ranking.rerankCount` overrides the second phase's count and `ranking.globalPhase.rerankCount` the global phase's; zero turns each phase off.

**What you should see:** NDCG@10 0.482 on validation and 0.489 on test. This is the floor every later stage is compared against.

The chapter compares the first stage with Chapter 5's profiles re-run at the same depth on this container. Those reference runs:

```
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking hybrid_linear --param 'input.query(alpha)=0.3' --hits 400 --label hybrid_linear --block headline --out chapters/ch06/expected/validation-hybrid_linear.json > chapters/ch06/expected/validation-hybrid_linear.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking hybrid_linear --param 'input.query(alpha)=0.3' --hits 400 --label hybrid_linear --block headline --out chapters/ch06/expected/test-hybrid_linear.json > chapters/ch06/expected/test-hybrid_linear.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking hybrid_rrf --hits 400 --label hybrid_rrf --block headline --out chapters/ch06/expected/validation-hybrid_rrf.json > chapters/ch06/expected/validation-hybrid_rrf.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking hybrid_rrf --hits 400 --label hybrid_rrf --block headline --out chapters/ch06/expected/test-hybrid_rrf.json > chapters/ch06/expected/test-hybrid_rrf.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever semantic --ranking semantic --hits 400 --label semantic --block headline --out chapters/ch06/expected/validation-semantic.json > chapters/ch06/expected/validation-semantic.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever semantic --ranking semantic --hits 400 --label semantic --block headline --out chapters/ch06/expected/test-semantic.json > chapters/ch06/expected/test-semantic.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever lexical --ranking bm25_tuned --hits 400 --label bm25_tuned --block headline --out chapters/ch06/expected/validation-bm25_tuned.json > chapters/ch06/expected/validation-bm25_tuned.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever lexical --ranking bm25_tuned --hits 400 --label bm25_tuned --block headline --out chapters/ch06/expected/test-bm25_tuned.json > chapters/ch06/expected/test-bm25_tuned.block.md
```

**What you should see:** `hybrid_linear` at 0.483 on validation and 0.488 on test, within noise of the first stage. Its Recall@100 is 0.691 on validation, against 0.669 in Chapter 5, because the deeper union gives the top 100 more to choose from.

### Second-phase reranking with late interaction

**Scoring every query token** and **Reading the MaxSim expression.** Nothing to run. The `colbert` field is in `app/schemas/product.sd`; the `max_sim` function and the second phase are in `app/schemas/product/phased.profile`.

**Replacing the score, or adding to it.** The chapter's table sets `phased_replace`'s curve beside `phased`'s. The `phased` curve comes from the count sweep below. The `phased_replace` curve is optional; the wall time of this sweep was not recorded:

```
.venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase second --profile phased_replace --out chapters/ch06/expected/validation-rerank-colbert-replace.json
.venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase second --profile phased_replace --from chapters/ch06/expected/validation-rerank-colbert-replace.json --block rerank-sweep > chapters/ch06/expected/validation-rerank-colbert-replace.block.md
```

**What you should see:** NDCG@10 of 0.482 at count 0, falling to 0.474 at 25 and 0.468 from 100 upward. From 100 upward the change against count 0 is −0.014 [−0.026, −0.002], which the tool labels **real**. Its latency column comes from its own run and reads lower than `phased`'s at the same counts, because each `phased_replace` hit carries a smaller cross-encoder input (`title_tokens`, 96 values, against `text_tokens`, 256). Compare its timings only with each other.

**A scale chosen by hand.** Sweep `w_sim`, the weight on MaxSim, with the second phase reranking 100 and the global phase off:

```
.venv/bin/python chapters/ch06/weight_sweep.py --split validation --input w_sim --values 0 0.002 0.005 0.01 0.02 0.05 --second 100 --global 0 --passes 1 --out chapters/ch06/expected/validation-weight-sim.json
.venv/bin/python chapters/ch06/weight_sweep.py --split validation --input w_sim --values 0 0.002 0.005 0.01 0.02 0.05 --from chapters/ch06/expected/validation-weight-sim.json --block weight-sweep > chapters/ch06/expected/validation-weight-sim.block.md
```

`--second` and `--global` hold each phase's count fixed while the weight varies. `--passes 1` runs each value once: a weight is chosen for quality, not for latency, so the weight tables print a p50 for reference and no p95 or p99. On the second command, `--split`, `--input` and `--values` are required by the tool but do not change what it prints; type them as shown.

**What you should see:** only `w_sim = 0.002` beats the first stage with an interval above zero, +0.013 [+0.007, +0.019]. 0.005 includes zero, and 0.01 and higher are no better than the first stage.

The finer sweep around it:

```
.venv/bin/python chapters/ch06/weight_sweep.py --split validation --input w_sim --values 0 0.001 0.002 0.003 0.005 --second 100 --global 0 --passes 1 --out chapters/ch06/expected/validation-weight-sim-fine.json
.venv/bin/python chapters/ch06/weight_sweep.py --split validation --input w_sim --values 0 0.001 0.002 0.003 0.005 --from chapters/ch06/expected/validation-weight-sim-fine.json --block weight-sweep > chapters/ch06/expected/validation-weight-sim-fine.block.md
```

**What you should see:** 0.001, 0.002 and 0.003 all beat the first stage. 0.001 cannot be told apart from 0.002, and 0.003 is slightly worse, −0.003 [−0.005, −0.000]. The profile keeps 0.002 as its default.

**How many candidates the second phase reranks.** With `w_sim` at 0.002, vary the second-phase count from 0 to 400 with the global phase off:

```
.venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase second --param 'input.query(w_sim)=0.002' --out chapters/ch06/expected/validation-rerank-colbert.json
.venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase second --from chapters/ch06/expected/validation-rerank-colbert.json --block rerank-sweep > chapters/ch06/expected/validation-rerank-colbert.block.md
```

`--phase second` sends the count through `ranking.rerankCount`, sets `ranking.globalPhase.rerankCount` to zero, and prints both in the table caption. The table compares every count with count 0 and with count 100, its reference count.

**What you should see:** NDCG@10 0.482 at count 0, 0.485 at 5, and 0.494 from 25 to 400. No count from 25 upward can be told apart from 100. p50 rises only from 115.0 ms at 0 to 120.9 ms at 400. Recall@100 is 0.691 until 200, then 0.695 and 0.696. The profile keeps 25.

### Global-phase reranking with a cross-encoder

**Reading the query and the product together.** Nothing to run. The `title_tokens` and `text_tokens` fields and the `onnx-model cross` declaration are in `app/schemas/product.sd`; the token functions and the global phase are in `app/schemas/product/phased.profile`.

**Blending the logit with the carried score.** Sweep `w_cross`, the cross-encoder's share of the blend, with the second phase at 25 and the global phase at 10. This sweep took 2 hours 19 minutes on the reference machine:

```
.venv/bin/python chapters/ch06/weight_sweep.py --split validation --input w_cross --values 0 0.3 0.5 0.7 1.0 --second 25 --global 10 --passes 1 --param 'input.query(w_sim)=0.002' --out chapters/ch06/expected/validation-weight-cross.json
.venv/bin/python chapters/ch06/weight_sweep.py --split validation --input w_cross --values 0 0.3 0.5 0.7 1.0 --from chapters/ch06/expected/validation-weight-cross.json --block weight-sweep > chapters/ch06/expected/validation-weight-cross.block.md
```

Alternatively, run the measurement in the background after sourcing the helper above, then run the `--from` command once it completes:

```bash
bg_run .venv/bin/python chapters/ch06/weight_sweep.py \
  --split validation --input w_cross \
  --values 0 0.3 0.5 0.7 1.0 \
  --second 25 --global 10 --passes 1 \
  --param 'input.query(w_sim)=0.002' \
  --out chapters/ch06/expected/validation-weight-cross.json
```

**What you should see:** every non-zero weight beats 0.0, and 0.7 is the best row at 0.502. Against 0.7, the logit alone (1.0) changes NDCG@10 by −0.002 [−0.005, +0.001], an interval that includes zero. p50 stays between 944.6 and 947.0 ms for every weight, including 0.0: the cross-encoder still runs at `w_cross = 0`, so that row is not a baseline without the model.

**How many candidates the cross-encoder reads.** Vary the global-phase count with the second phase off. The core sweep measures 0, 5 and 10:

```
.venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase global --counts 0 5 10 --reference-count 10 --param 'input.query(w_sim)=0.002' --param 'input.query(w_cross)=0.7' --out chapters/ch06/expected/validation-rerank-cross.json
.venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase global --from chapters/ch06/expected/validation-rerank-cross.json --block rerank-sweep > chapters/ch06/expected/validation-rerank-cross.block.md
```

`--phase global` sends the count through `ranking.globalPhase.rerankCount` and sets `ranking.rerankCount` to zero. `--counts` lists the counts to measure, and `--reference-count` names the row the others are compared against.

The extended sweep adds 25. It is optional and took 3 hours 12 minutes on the reference machine:

```
.venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase global --counts 0 5 10 25 --reference-count 10 --param 'input.query(w_sim)=0.002' --param 'input.query(w_cross)=0.7' --out chapters/ch06/expected/validation-rerank-cross-extended.json
.venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase global --from chapters/ch06/expected/validation-rerank-cross-extended.json --block rerank-sweep > chapters/ch06/expected/validation-rerank-cross-extended.block.md
```

Alternatively, run this measurement in the background, then run the `--from` command once it completes:

```bash
bg_run .venv/bin/python chapters/ch06/rerank_sweep.py \
  --split validation --phase global \
  --counts 0 5 10 25 --reference-count 10 \
  --param 'input.query(w_sim)=0.002' \
  --param 'input.query(w_cross)=0.7' \
  --out chapters/ch06/expected/validation-rerank-cross-extended.json
```

**What you should see:** NDCG@10 0.482 at 0, 0.489 at 5, 0.495 at 10 and 0.511 at 25, each step a gain the interval confirms. p50 climbs from about 113 ms to 516 ms, 943 ms and 2,225 ms, roughly 81 to 85 ms for each added candidate. The 0, 5 and 10 rows of the two sweeps agree. The profile keeps 10, chosen for cost rather than at a plateau.

### Evaluating Ranking Pipeline: Choosing rerank counts with quality and latency

**Two curves, two reasons to stop.** Nothing new to run: the two curves are the second-phase and global-phase count sweeps above.

**The funnel's budget, stage by stage.** The whole funnel at the chosen values, each stage compared with the one before it:

```
.venv/bin/python chapters/ch06/funnel_budget.py --split validation --second 25 --global 10 --hits 400 --param 'input.query(w_sim)=0.002' --param 'input.query(w_cross)=0.7' --out chapters/ch06/expected/validation-funnel-budget.json
.venv/bin/python chapters/ch06/funnel_budget.py --split validation --from chapters/ch06/expected/validation-funnel-budget.json --block funnel-budget > chapters/ch06/expected/validation-funnel-budget.block.md
```

**What you should see:** NDCG@10 0.482 for the first stage alone, 0.494 with the second phase and 0.502 with the global phase. The second phase adds +0.1 ms at the median; the global phase adds +833.3 ms. Recall@100 is 0.691 at every stage.

**What the first stage already costs.** The latency tables, from the reports above:

```
.venv/bin/python shared/tools/compare.py --block evaluations-latency --out chapters/ch06/expected/compare-validation-latency.json chapters/ch06/expected/validation-bm25_tuned.json chapters/ch06/expected/validation-semantic.json chapters/ch06/expected/validation-hybrid_rrf.json chapters/ch06/expected/validation-hybrid_linear.json chapters/ch06/expected/validation-first_stage.json chapters/ch06/expected/validation-phased_title.json chapters/ch06/expected/validation-phased.json > chapters/ch06/expected/compare-validation-latency.block.md
.venv/bin/python shared/tools/compare.py --block evaluations-latency --out chapters/ch06/expected/compare-test-latency.json chapters/ch06/expected/test-bm25_tuned.json chapters/ch06/expected/test-semantic.json chapters/ch06/expected/test-hybrid_rrf.json chapters/ch06/expected/test-hybrid_linear.json chapters/ch06/expected/test-first_stage.json chapters/ch06/expected/test-phased_title.json chapters/ch06/expected/test-phased.json > chapters/ch06/expected/compare-test-latency.block.md
```

**What you should see:** on validation, p50 of 28.4 ms for `hybrid_linear`, 114.5 ms for the first stage, 323.9 ms for `phased_title` and 947.9 ms for `phased`. Test agrees within 2 ms at p50. Every row returns 400 hits; that is why `hybrid_linear` reads about twice Chapter 5's 14.6 ms.

**What the rerankers cost to hold.** The memory reading takes **at least twenty minutes, and up to thirty**. Run it on an idle container straight after a fresh bootstrap, before any other command, if you want a figure comparable with the book's:

```
.venv/bin/python shared/tools/memory.py --settle 600 --rounds 3 --tolerance 0.01 --out chapters/ch06/expected/memory.json
.venv/bin/python shared/tools/memory.py --from chapters/ch06/expected/memory.json > chapters/ch06/expected/memory.block.md
```

**What you should see:** about 1,430 MB on a container built with `./bootstrap.sh ch06 --fresh` and fed once. A container continued from Chapter 5, whose index has been fed by both chapters, reads higher; the book saw about 2,025 MB. Check that the report says `settled: true`.

### Evaluating the Ranking Pipeline on the Test Set

**Validation and Test Results”.**

```
.venv/bin/python shared/tools/compare.py --block evaluations --out chapters/ch06/expected/compare-validation-evaluations.json chapters/ch06/expected/validation-bm25_tuned.json chapters/ch06/expected/validation-semantic.json chapters/ch06/expected/validation-hybrid_rrf.json chapters/ch06/expected/validation-hybrid_linear.json chapters/ch06/expected/validation-first_stage.json chapters/ch06/expected/validation-phased_title.json chapters/ch06/expected/validation-phased.json > chapters/ch06/expected/compare-validation-evaluations.block.md
.venv/bin/python shared/tools/compare.py --block evaluations --out chapters/ch06/expected/compare-test-evaluations.json chapters/ch06/expected/test-bm25_tuned.json chapters/ch06/expected/test-semantic.json chapters/ch06/expected/test-hybrid_rrf.json chapters/ch06/expected/test-hybrid_linear.json chapters/ch06/expected/test-first_stage.json chapters/ch06/expected/test-phased_title.json chapters/ch06/expected/test-phased.json > chapters/ch06/expected/compare-test-evaluations.block.md
```

**What you should see:** `phased` at 0.502 on validation and 0.499 on test; the first stage at 0.482 and 0.489. The gain over the first stage, from the comparison blocks above, is +0.021 on validation and +0.010 on test.

**Which Retrieved Products Reach the Top Ten.** For each split, the relevant pairs only one retrieval side found in its top 100, and where each profile places them:

```
.venv/bin/python chapters/ch06/wider_net.py --split validation --profiles phased hybrid_linear hybrid_rrf semantic --alpha 0.3 --out chapters/ch06/expected/validation-wider-net.json
.venv/bin/python chapters/ch06/wider_net.py --from chapters/ch06/expected/validation-wider-net.json --block wider-net > chapters/ch06/expected/validation-wider-net.block.md
.venv/bin/python chapters/ch06/wider_net.py --split test --profiles phased hybrid_linear hybrid_rrf semantic --alpha 0.3 --out chapters/ch06/expected/test-wider-net.json
.venv/bin/python chapters/ch06/wider_net.py --from chapters/ch06/expected/test-wider-net.json --block wider-net > chapters/ch06/expected/test-wider-net.block.md
```

As in Chapter 5, the tool recomputes the two sets at depth 100 on your container and says *vector-only* and *keyword-only* where the chapter says *semantic-only* and *lexical-only*. `--alpha 0.3` applies only to `hybrid_linear`.

**What you should see** (test): 2,158 semantic-only and 1,303 lexical-only relevant pairs. In the top ten, `hybrid_rrf` places 25 and 79, `hybrid_linear` 112 and 80, and `phased` 75 and 138. All three place 799 and 1,098 in their top 100. On validation the sets are 1,623 and 908, and the top-ten counts are 36 and 41, 105 and 46, and 76 and 74.

### Three scores, one query: rank features and feature logging

**Logging rank features.** One feature log per split, then the summary table. This is the first time the book uses the training split:

```
.venv/bin/python chapters/ch06/features_log.py --split train --out chapters/ch06/expected/features-train.json
.venv/bin/python chapters/ch06/features_log.py --split validation --out chapters/ch06/expected/features-validation.json
.venv/bin/python chapters/ch06/features_log.py --split test --out chapters/ch06/expected/features-test.json
.venv/bin/python chapters/ch06/features_log.py --from chapters/ch06/expected/features-train.json chapters/ch06/expected/features-validation.json chapters/ch06/expected/features-test.json --block features-log > chapters/ch06/expected/features-log.block.md
```

Each run writes one CSV row per judged query and product under `builds/esci-us-hard-book-s42-kdd-v4/features/`, a build file that is not part of the repository, and a JSON report under `expected/`. The cross-encoder runs on every logged pair, so these runs are not quick.

**What you should see:** 35,019 judged pairs for train, 14,926 for validation and 21,503 for test, 56 columns in every row: four identifying the pair, its grade and how it was retrieved, then 52 rank features. The `sha256` column is your file's checksum and will differ from the book's while every count matches.

## Comparing your run with the book's

`expected/` holds the output of every command above, exactly as it ran when the book was written. Four kinds of number are in there, and they behave differently:

- **Quality numbers** — NDCG@10, recall and MRR for every profile, sweep and funnel row. These should come back within a few thousandths. No interval's label should change, and every chosen weight and count should again be the best row or indistinguishable from it.
- **Counts** — the wider-net sets and their cells can move by a handful of pairs between runs, and by up to about a dozen against Chapter 5's run of its own tool. The feature-log counts are exact; the CSV checksums differ.
- **The worked query** — the BM25-based `lexical` values can move by a few hundredths with the container's feeding history, and the relevance columns that blend them in by up to about a hundredth. `max_sim`, `vector` and the rank order should not change.
- **Cost numbers** — bootstrap and feed timings, p50, p95 and p99 latency, and memory. These describe one machine on one day (an Apple M4 Pro, Docker with 4 CPUs / 10 GB), one query at a time, after a discarded warm-up pass. Yours will differ, and that is expected.

The `phased_replace` curve and the two cross-encoder sweeps (`w_cross`, and the extended count sweep) are reproduced only if you run them.

After a run, `git diff chapters/ch06/expected/` shows every difference.

## If something goes wrong

**The deploy fails because `models/cross_encoder.onnx` is missing** — the schema declares the cross-encoder by file, so the file must exist before deploying. Run `./bootstrap.sh ch06`, which downloads it and checks its sha256, rather than `vespa deploy` on its own.

**`max_sim` is zero, or the rerankers seem to do nothing** — the request may be missing `query(qt)` or `query(qt_cross)`. Use `--reranker-input qt=colbert --reranker-input qt_cross=tokenizer` with `evaluate.py`, or the two `--param 'input.query(...)=embed(...)'` lines with `query.py`. If the inputs are there and `max_sim` is still zero, the catalogue has not been fed with this chapter's fields; run `./bootstrap.sh ch06`.

**A hand-typed `curl` against `phased` returns `"Timed out"` and `"No time left to get summaries"`** — Vespa's default request timeout is too short for `phased`'s rerankers. `query.py` and `evaluate.py` send a 30-second timeout on every request. Add `&timeout=10s` (or more) to any raw request against `phased` or `phased_title`.

**A count sweep looks like the wrong reranker** — `ranking.rerankCount` sets the second phase's count and `ranking.globalPhase.rerankCount` the global phase's. Sending the wrong one is not an error: the request succeeds, and the phase you meant stays at its default. `rerank_sweep.py` sets the right one for `--phase` and prints both in the table caption; check the caption. The current Vespa documentation also names the second-phase setting `ranking.secondPhase.rerankCount`; this chapter uses `ranking.rerankCount` with its pinned Vespa version.

**Changing `w_sim` or `w_cross` changes nothing** — only profiles that declare those inputs read them. `hybrid_rrf` and `hybrid_linear` accept them silently and ignore them.

**A count sweep shows identical rows above some count** — the candidates ran out. Keep `--hits` at least as large as the largest count; every command here uses 400.

**The weight tables have no p95 or p99** — by design. `weight_sweep.py` runs one pass, because a weight is chosen for quality. The count sweeps print p95 and p99.

**The memory reading is higher than the book's** — the container has a longer feed history. Only a container built with `--fresh`, fed once, with nothing else run, reproduces the book's reading. If the report says `settled: false`, the readings never agreed; run it again when nothing else is querying the container.

**`HTTP 429` from Hugging Face** — rate limiting, not a broken build. Run the same command again.

**The deploy or feed fails, or Vespa stops responding partway** — check that Docker really has 4 CPUs and 10 GB. Every run behind the book used exactly that, so too little memory is the first thing to rule out.

**The container fails to start because a port is already allocated** — something else on your machine is using port 8080 or 19071. Stop it, or stop the other Vespa container, then rerun with `--fresh`.

## Next

When you are ready for Chapter 7:

```
./bootstrap.sh ch07
```

It adds no fields, so continuing from this chapter is a deploy with no feed. Chapter 7 uses the rank-feature log from this chapter to learn how to weigh the signals, instead of choosing two weights by hand.
