# Chapter 5 — Hybrid Search

This directory is the code for Chapter 5 of *Production AI Search with Vespa*. It combines Chapter 3's lexical lens and Chapter 4's semantic lens in one request and one rank profile, over the same 101,341 products and the same judged queries. It fuses the two scores in two ways, reciprocal rank fusion and a normalized, weighted blend. It then measures both against each single lens, tests how much the blend's weight matters, shows what a badly chosen first phase loses, and turns the fused results into compact, attributable context for a generative model.

The book explains what each step does and why. This page is the practical half: what to run, in the same order as the chapter, what you should see, and what to do when something goes wrong.

## What is in this directory

```
chapters/ch05/
├── app/                              the application package Vespa deploys
│   ├── services.xml                  unchanged from Chapter 4
│   ├── schemas/
│   │   ├── product.sd                Chapter 4's schema, plus the document summary `context`;
│   │   │                             no new fields
│   │   └── product/                  one file per rank profile
│   │       ├── hybrid_rrf.profile    new: bounded first phase, reciprocal rank fusion
│   │       ├── hybrid_linear.profile new: same first phase, normalized blend weighted by alpha
│   │       ├── hybrid_starved.profile new: raw-sum first phase, reciprocal rank fusion
│   │       └── …                     Chapters 3 and 4's profiles, unchanged
│   └── search/query-profiles/
│       └── default.xml               request defaults, unchanged: bm25_tuned is still the default
├── chapter.toml                      what bootstrap.sh needs for this chapter
├── alpha_sweep.py                    hybrid_linear at nine values of alpha
├── wider_net.py                      where the pairs only one lens reaches end up after fusion
├── context.py                        builds RAG context from the fused results, and measures it
├── COMMANDS.md                       every command, as run for the book
└── expected/                         the book's reference output
```

The feeder, the query tool, the evaluation tool and the comparison tool are shared by every chapter and live in `shared/tools/`.

## What you need

The same as Chapter 4. This chapter adds no model and no field.

|  | Version used for the book | Notes |
| :---- | :---- | :---- |
| Docker | — | Give it **4 CPUs and 10 GB of memory**. Docker Desktop or Rancher Desktop both work. |
| Python | 3.11 (3.11.13) | Only needed to create the virtual environment. |
| Vespa CLI | 8.562.17 | macOS: `brew install vespa-cli`. Linux and Windows: the Vespa GitHub releases page. |
| Embedding model | `BAAI/bge-small-en-v1.5`, commit `5c38ec7c` | The same model as Chapter 4. Already in place if you are continuing. |
| Network | — | Access to Hugging Face, only when starting fresh: for the model weights, and for the dataset if it is not already cached. |

Every pinned version is listed in `docs/pins.md` at the repository root.

## Run it

From the repository root:

```
./bootstrap.sh ch05
```

If you are continuing from Chapter 4, this deploys this chapter's application package to the running container. It adds three rank profiles and one document summary but no fields, so every product already has its `title_embedding` and nothing is fed. The script checks for vectors and prints `skip  101341 documents in the index, title_embedding present`.

If you are starting with this chapter, add `--fresh`: it removes any earlier virtual environment and Vespa container, builds everything from the beginning, and feeds the catalogue once, computing every vector as it is written, exactly as Chapter 4 did.

Either way, the deployment prints one new warning:

```
WARNING In document-summary 'context' in schema 'product': Fields [snippet] references non-attribute fields: Using this summary will cause disk accesses. Set 'from-disk' on this document-summary to silence this warning.
```

That is expected, and the chapter leaves it in place on purpose. *Compact, attributable context for generation* below explains it. No reindex warning appears, because no field changed.

On the reference machine (Apple M4 Pro, container VM with 4 CPUs and 10 GB), continuing from Chapter 4 took about 10 seconds. A fresh run with the dataset already cached took 9 minutes 2 seconds, most of it the feed; a first run that also had to download the dataset took 22 minutes 48 seconds. Your timings will differ.

A successful run ends with this state, the same as at the end of Chapter 4:

```
== at the start of ch05
   build      builds/esci-us-hard-book-s42-kdd-v4
   image      vespaengine/vespa:8.751.13
   documents  101341
   embedders  embedder=BAAI/bge-small-en-v1.5@5c38ec7c
```

## The commands in this chapter

The steps below follow the chapter, section by section. Run them from the repository root after `bootstrap.sh` has finished.

Most commands save their result in `expected/`, replacing the book's copy of that file, so that `git diff chapters/ch05/expected/` shows how your run compares with the book's. To put the book's files back, run `git checkout chapters/ch05/expected/`.

### One request, two lenses

Send one hybrid query:

```
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking hybrid_rrf --hits 5 --block features
```

`--retriever hybrid` makes the tool send the request the chapter shows: `userQuery()` and `nearestNeighbor` joined with `or`, carrying both the query text and the embedded query vector. `--block features` prints each hit's `lexical` and `vector` scores next to the score the profile ranked by.

**What you should see:** five running shoes, with the Nike Women's Running Shoes listing first at lexical 12.249 and vector 0.805, and the Haforever listing second at 11.918 and 0.819. These are the two products the chapter opens with.

**Narrowing the union with a filter.** Nothing to run. The chapter shows the shape of a filtered hybrid request and measures nothing about it; Chapter 8 does. If you try it yourself, keep the parentheses around the union, as the chapter explains:

```
select id, title from product
where (userQuery() or ({targetHits:100}nearestNeighbor(title_embedding, q)))
  and has_description = true
```

### Two scores on different scales

Nothing to run. The three hybrid profiles are in `app/schemas/product/`. `hybrid_rrf.profile` holds the `lexical` and `vector` functions, the bounded first phase `lexical / (1 + lexical) + vector`, and the global phase with `rerank-count: 100`. The other two profiles inherit from it and change one phase each.

### Two ways to fuse: rank fusion and a normalized blend

The same query under each of the three hybrid profiles, saved for the chapter's comparison of top fives:

```
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking hybrid_rrf --hits 5 --block features > chapters/ch05/expected/features-running-shoes-hybrid_rrf.block.md
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking hybrid_linear --param 'input.query(alpha)=0.3' --hits 5 --block features > chapters/ch05/expected/features-running-shoes-hybrid_linear.block.md
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking hybrid_starved --hits 5 --block features > chapters/ch05/expected/features-running-shoes-hybrid_starved.block.md
```

`--param` passes a query input to the profile; here it sets `hybrid_linear`'s alpha to 0.3, its default. `--hits 5` also sets the vector side's target to 5, so these single-query examples use a smaller vector target than the evaluations, which use 100. The lexical side still contributes its own candidates.

**What you should see:** under `hybrid_rrf`, Nike first and Haforever second. Under `hybrid_linear`, Haforever first and four different products after it. `hybrid_starved` is used later, in *A first phase that adds the raw scores*.

### Measuring hybrid search against each lens

Evaluate all five profiles on both query sets. The options are the same as in Chapters 3 and 4: `--retriever` chooses the request (`lexical`, `semantic` or `hybrid`), `--ranking` chooses the rank profile, and `--param` passes a query input.

Validation:

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --retriever lexical --ranking bm25_tuned --label validation-bm25_tuned --out chapters/ch05/expected/validation-bm25_tuned.json > chapters/ch05/expected/validation-bm25_tuned.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --retriever semantic --ranking semantic --label validation-semantic --out chapters/ch05/expected/validation-semantic.json > chapters/ch05/expected/validation-semantic.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --retriever hybrid --ranking hybrid_rrf --label validation-hybrid_rrf --out chapters/ch05/expected/validation-hybrid_rrf.json > chapters/ch05/expected/validation-hybrid_rrf.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --retriever hybrid --ranking hybrid_linear --param 'input.query(alpha)=0.3' --label validation-hybrid_linear --out chapters/ch05/expected/validation-hybrid_linear.json > chapters/ch05/expected/validation-hybrid_linear.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --retriever hybrid --ranking hybrid_starved --label validation-hybrid_starved --out chapters/ch05/expected/validation-hybrid_starved.json > chapters/ch05/expected/validation-hybrid_starved.block.md
```

Test:

```
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --retriever lexical --ranking bm25_tuned --label test-bm25_tuned --out chapters/ch05/expected/test-bm25_tuned.json > chapters/ch05/expected/test-bm25_tuned.block.md
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --retriever semantic --ranking semantic --label test-semantic --out chapters/ch05/expected/test-semantic.json > chapters/ch05/expected/test-semantic.block.md
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --retriever hybrid --ranking hybrid_rrf --label test-hybrid_rrf --out chapters/ch05/expected/test-hybrid_rrf.json > chapters/ch05/expected/test-hybrid_rrf.block.md
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --retriever hybrid --ranking hybrid_linear --param 'input.query(alpha)=0.3' --label test-hybrid_linear --out chapters/ch05/expected/test-hybrid_linear.json > chapters/ch05/expected/test-hybrid_linear.block.md
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --retriever hybrid --ranking hybrid_starved --label test-hybrid_starved --out chapters/ch05/expected/test-hybrid_starved.json > chapters/ch05/expected/test-hybrid_starved.block.md
```

`bm25_tuned` is evaluated with `--retriever lexical`, not with the hybrid request. As the chapter explains, its profile does not declare the query vector input `query(q)` that the hybrid request carries, so Vespa refuses that request for it.

**What you should see:** ndcg@10 on validation of 0.437 for `bm25_tuned`, 0.451 for `semantic`, 0.467 for `hybrid_rrf`, 0.481 for `hybrid_linear` and 0.464 for `hybrid_starved`. On test: 0.443, 0.454, 0.470, 0.486 and 0.470.

The tables in this section are built from those ten reports by `shared/tools/compare.py`. It reads the saved reports and queries nothing; `--block` chooses the table, and `--baseline` names the run the others are compared against. First, the five-profile tables:

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/validation-bm25_tuned.json chapters/ch05/expected/validation-semantic.json chapters/ch05/expected/validation-hybrid_rrf.json chapters/ch05/expected/validation-hybrid_linear.json chapters/ch05/expected/validation-hybrid_starved.json --baseline validation-bm25_tuned --block evaluations > chapters/ch05/expected/compare-validation-evaluations.block.md
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/test-bm25_tuned.json chapters/ch05/expected/test-semantic.json chapters/ch05/expected/test-hybrid_rrf.json chapters/ch05/expected/test-hybrid_linear.json chapters/ch05/expected/test-hybrid_starved.json --baseline test-bm25_tuned --block evaluations > chapters/ch05/expected/compare-test-evaluations.block.md
```

Then each profile against `bm25_tuned`:

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/validation-bm25_tuned.json chapters/ch05/expected/validation-hybrid_rrf.json chapters/ch05/expected/validation-hybrid_linear.json chapters/ch05/expected/validation-hybrid_starved.json chapters/ch05/expected/validation-semantic.json --baseline validation-bm25_tuned --block comparison --out chapters/ch05/expected/compare-validation-vs-tuned.json > chapters/ch05/expected/compare-validation-vs-tuned.block.md
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/test-bm25_tuned.json chapters/ch05/expected/test-hybrid_rrf.json chapters/ch05/expected/test-hybrid_linear.json chapters/ch05/expected/test-hybrid_starved.json chapters/ch05/expected/test-semantic.json --baseline test-bm25_tuned --block comparison --out chapters/ch05/expected/compare-test-vs-tuned.json > chapters/ch05/expected/compare-test-vs-tuned.block.md
```

**What you should see:** against `bm25_tuned`, `hybrid_linear` changes ndcg@10 by +0.044 [+0.032, +0.056] on validation and +0.043 [+0.033, +0.054] on test; `hybrid_rrf` by +0.030 [+0.021, +0.040] and +0.027 [+0.019, +0.035]. Every one of those intervals lies above zero, and the tool labels them **real**. `semantic` alone, +0.014 [−0.001, +0.031] and +0.012 [−0.003, +0.026], still includes zero, and the tool labels it **inside the noise**, as in Chapter 4.

Then each hybrid profile against `semantic`:

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/validation-semantic.json chapters/ch05/expected/validation-hybrid_rrf.json chapters/ch05/expected/validation-hybrid_linear.json chapters/ch05/expected/validation-hybrid_starved.json --baseline validation-semantic --block comparison --out chapters/ch05/expected/compare-validation-vs-semantic.json > chapters/ch05/expected/compare-validation-vs-semantic.block.md
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/test-semantic.json chapters/ch05/expected/test-hybrid_rrf.json chapters/ch05/expected/test-hybrid_linear.json chapters/ch05/expected/test-hybrid_starved.json --baseline test-semantic --block comparison --out chapters/ch05/expected/compare-test-vs-semantic.json > chapters/ch05/expected/compare-test-vs-semantic.block.md
```

**What you should see:** both fused profiles improve ndcg@10 over `semantic`, with intervals above zero on both query sets: `hybrid_linear` +0.030 and +0.032, `hybrid_rrf` +0.016 on both. Their recall@100 changes by −0.010 [−0.023, +0.003] on validation and −0.004 [−0.016, +0.007] on test; those intervals include zero.

**Which fusion method.** The two fused profiles directly, with `hybrid_linear` as the baseline:

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/validation-hybrid_linear.json chapters/ch05/expected/validation-hybrid_rrf.json --baseline validation-hybrid_linear --block comparison --out chapters/ch05/expected/compare-validation-rrf-vs-linear.json > chapters/ch05/expected/compare-validation-rrf-vs-linear.block.md
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/test-hybrid_linear.json chapters/ch05/expected/test-hybrid_rrf.json --baseline test-hybrid_linear --block comparison --out chapters/ch05/expected/compare-test-rrf-vs-linear.json > chapters/ch05/expected/compare-test-rrf-vs-linear.block.md
```

**What you should see:** `hybrid_rrf` at −0.014 [−0.021, −0.008] on validation and −0.016 [−0.021, −0.011] on test. recall@100 changes by +0.000 on both, because both profiles rerank the same 100 candidates.

### How much the weight matters, and what the first phase decides

**The weight has a plateau.** `hybrid_linear` on the validation queries at alpha 0.0, every tenth from 0.2 to 0.8, and 1.0:

```
.venv/bin/python chapters/ch05/alpha_sweep.py --split validation --out chapters/ch05/expected/validation-alpha-sweep.json > chapters/ch05/expected/validation-alpha-sweep.block.md
```

The script also runs the default, 0.3, first and last, as a check that nothing changed during the sweep. Its table has more columns than the chapter's: each row is compared with both ends of the sweep, for ndcg@10 and for recall@100. The tool's last column, *cannot be told apart from*, is the one the chapter calls *No detected difference from*: the settings whose interval against that row includes zero.

**What you should see:** ndcg@10 of 0.457 at alpha 0.0, rising to 0.481 at 0.3 and 0.482 at 0.4, and falling to 0.440 at 1.0. 0.3 cannot be told apart from 0.4, 0.5 and 0.6. recall@100 is 0.669 in every row. The two ends are not the same as `semantic` and `bm25_tuned`: they still use the hybrid request and the bounded first phase.

**A first phase that adds the raw scores.** `hybrid_starved` against `hybrid_rrf`:

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/validation-hybrid_rrf.json chapters/ch05/expected/validation-hybrid_starved.json --baseline validation-hybrid_rrf --block comparison --out chapters/ch05/expected/compare-validation-starved-vs-rrf.json > chapters/ch05/expected/compare-validation-starved-vs-rrf.block.md
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/test-hybrid_rrf.json chapters/ch05/expected/test-hybrid_starved.json --baseline test-hybrid_rrf --block comparison --out chapters/ch05/expected/compare-test-starved-vs-rrf.json > chapters/ch05/expected/compare-test-starved-vs-rrf.block.md
```

**What you should see:** recall@100 changes by −0.037 [−0.044, −0.030] on validation and −0.033 [−0.039, −0.028] on test. ndcg@10 barely moves: −0.003 [−0.005, −0.000] on validation and +0.000 [−0.002, +0.003] on test.

**What the wider net delivers.** For each query, the relevant products only the semantic lens reaches in its top 100, and those only the lexical lens reaches, then how many of each land in each profile's top 10 and top 100:

```
.venv/bin/python chapters/ch05/wider_net.py --split validation --alpha 0.3 --out chapters/ch05/expected/validation-wider-net.json > chapters/ch05/expected/validation-wider-net.block.md
.venv/bin/python chapters/ch05/wider_net.py --split test --alpha 0.3 --out chapters/ch05/expected/test-wider-net.json > chapters/ch05/expected/test-wider-net.block.md
```

The script recomputes the two sets on your container with the same two single-lens requests Chapter 4 used, rather than reading Chapter 4's report. It then sends the **hybrid** request under each profile, including `semantic`. The `semantic` row is therefore the semantic profile ranking the union, not the semantic-only request that defined the sets, which is why it holds 2,136 of the 2,158 semantic-only pairs and 52 lexical-only ones rather than all 2,158 and none. `--alpha 0.3` applies only to `hybrid_linear`. The tool says *vector-only* and *keyword-only* where the chapter says *semantic-only* and *lexical-only*.

**What you should see** (test): 2,158 semantic-only and 1,291 lexical-only relevant pairs. `hybrid_rrf` places 24 semantic-only pairs in its top 10 and 797 in its top 100; `hybrid_linear` 112 and the same 797; `hybrid_starved` 15 and 136. On validation the same table reads 1,617 and 917 pairs, with `hybrid_rrf` at 36 / 625, `hybrid_linear` at 105 / 625 and `hybrid_starved` at 22 / 107.

### What fusion costs

The latency table, from the same five validation reports:

```
.venv/bin/python shared/tools/compare.py chapters/ch05/expected/validation-bm25_tuned.json chapters/ch05/expected/validation-semantic.json chapters/ch05/expected/validation-hybrid_rrf.json chapters/ch05/expected/validation-hybrid_linear.json chapters/ch05/expected/validation-hybrid_starved.json --baseline validation-bm25_tuned --block evaluations-latency > chapters/ch05/expected/compare-validation-latency.block.md
```

**What you should see:** p50 4.5 ms for `bm25_tuned`, 14.0 ms for `semantic`, and 14.6 to 14.7 ms for the three hybrid profiles, on the reference machine. Yours will differ. Vespa's own reported search time, which leaves out the query embedding, is in the `latency_ms_vespa_reported` field of each report.

### Compact, attributable context for generation

**A document summary for context.** Nothing to run. The `document-summary context` is in `app/schemas/product.sd`. It returns `id`, `title`, and a `snippet` cut from the description around the query's terms. The disk-access warning bootstrap printed comes from the snippet: it is cut from the stored description, which is read from the document store rather than from memory.

**Building and measuring the context.** One worked context, then the measurement over all 735 validation queries:

```
.venv/bin/python chapters/ch05/context.py --query "running shoes" --ranking hybrid_rrf > chapters/ch05/expected/context-running-shoes.block.md
.venv/bin/python chapters/ch05/context.py --split validation --depths 1 3 5 10 20 --ranking hybrid_rrf --out chapters/ch05/expected/validation-context.json > chapters/ch05/expected/validation-context.block.md
```

`context.py` asks for the `context` summary, removes Vespa's highlighting markup, drops any entry whose title repeats one already included, and writes one entry per product, identifier first. `--depths` lists how many products to retrieve for each row of the table. The context is built under `hybrid_rrf`; to build it under the blend instead, use `--ranking hybrid_linear --alpha 0.3`.

**What you should see:** five entries for `running shoes`, each starting with its product identifier in brackets, such as `[B078JRKH6X] Nike Women's Running Shoes, Black/White, 5 us`. Two carry a snippet; the Soulsfeng snippet still contains HTML such as `<br>` and `<strong>`, which is part of ESCI's own description text. The table reads, at 1, 3, 5, 10 and 20 products: mean bytes 170, 524, 894, 1,826 and 3,700; contexts holding an Exact product 52.4%, 71.4%, 76.5%, 83.1% and 87.9%; entries dropped as duplicates 0, 18, 33, 62 and 115.

## Comparing your run with the book's

`expected/` holds the output of every command above, exactly as it ran when the book was written. Three kinds of number are in there, and they behave differently:

- **Lexical quality numbers** — `bm25_tuned`'s ndcg@10, recall and mrr. These should come back within 0.001, and match Chapter 4's within the same margin.
- **Semantic and hybrid quality numbers** — every figure from a `semantic` or hybrid run, the alpha sweep, the wider-net counts and the context table. HNSW builds a slightly different graph each time vectors are fed, so these can move by a few thousandths, and the counts by a handful of pairs. The direction of every comparison, and whether its interval includes zero, should not change, with one exception: `hybrid_starved` against `hybrid_rrf` on validation ndcg@10, −0.003, has an interval edge within 0.002 of zero, so a rerun can change its label.
- **Cost numbers** — bootstrap timings and p50 and p95 latency. These describe one machine on one day (an Apple M4 Pro, Docker with 4 CPUs / 10 GB). Latency is measured after a discarded warm-up pass. Chapter 4 measured `semantic` at 12.9 ms p50 on its own container, and this chapter 14.0 ms: that is the size of run-to-run movement to expect. Yours will differ.

After a run, `git diff chapters/ch05/expected/` shows every difference.

## If something goes wrong

**The deploy prints a warning about `document-summary 'context'`** — expected. It describes the cost of a query-dependent snippet, and the chapter leaves it in place.

**A hybrid request against `bm25_tuned` returns HTTP 400** — `bm25_tuned` does not declare `query(q)`, the query vector the hybrid request carries. Use `--retriever lexical` with `bm25_tuned`, as every command above does.

**Changing alpha changes nothing** — only `hybrid_linear` reads `query(alpha)`. Sending it to `hybrid_rrf` or `hybrid_starved` has no effect. `context.py` refuses `--alpha` unless `--ranking` is `hybrid_linear`, and `wider_net.py` refuses it unless `hybrid_linear` is among its profiles.

**A filter seems to let ineligible products through** — check the parentheses. Without them, `userQuery() or nearestNeighbor(...) and has_description = true` filters only the vector side.

**Your single-query results differ from the evaluation's top ten** — `query.py --hits 5` also sets the vector side's target to 5, so its union is narrower than the evaluations', which use 100.

**Hybrid or semantic queries return only lexical matches, or none** — the vectors are missing, usually because the container was rebuilt. Run `./bootstrap.sh ch05`: if no product has a vector, it feeds the catalogue again.

**Snippets contain HTML such as `<br>` or `<strong>`** — that markup is part of ESCI's description text. `context.py` removes Vespa's highlighting markup, not the dataset's own.

**`HTTP 429` from Hugging Face** — rate limiting, not a broken build. Run the same command again; it starts the dataset download from the first file.

**The deploy or feed fails, or Vespa stops responding partway** — check that Docker really has 4 CPUs and 10 GB. Every run behind the book used exactly that, so too little memory is the first thing to rule out.

**The container fails to start because a port is already allocated** — something else on your machine is using port 8080 or 19071. Stop it, or stop the other Vespa container, then rerun with `--fresh`.

## Next

When you are ready for Chapter 6:

```
./bootstrap.sh ch06
```

It adds the fields that late interaction and a cross-encoder need, so continuing from this chapter is a deploy followed by one full feed. Chapter 6 then decides how many of the fused candidates to examine, and how carefully.
