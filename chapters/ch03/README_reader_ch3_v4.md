# Chapter 3 — Text Search Foundations

This directory is the code for Chapter 3 of *Production AI Search with Vespa*. It loads the full catalogue of 101,341 products from Amazon's ESCI shopping dataset into the application Chapter 2 built, establishes a BM25 baseline against ESCI's human relevance judgements, tunes BM25, adds two more ranking signals, and measures the final profile on queries that were never used for tuning.

The book explains what each step does and why. This page is the practical half: what to run, in the same order as the chapter, what you should see, and what to do when something goes wrong.

## What is in this directory

```
chapters/ch03/
├── app/                              the application package Vespa deploys
│   ├── services.xml                  the container and content nodes, unchanged
│   ├── schemas/
│   │   ├── product.sd                Chapter 2's schema, plus enable-bm25 and title_grams
│   │   └── product/                  one file per rank profile
│   │       ├── random.profile        random order
│   │       ├── default.profile       Chapter 2's nativeRank, unchanged
│   │       ├── bm25_title.profile    BM25 on the title only
│   │       ├── bm25_all.profile      BM25 on four fields, added together
│   │       ├── bm25_weighted.profile BM25 on four fields, weighted
│   │       ├── bm25_k*_b*.profile    the fifteen k1 × b profiles
│   │       ├── bm25_tuned.profile    the chapter's final profile
│   │       └── explained.profile     returns rank features with each hit
│   └── search/query-profiles/
│       └── default.xml               request defaults: hits, rank profile, timing
├── chapter.toml                      what bootstrap.sh needs for this chapter
├── compare.py                        builds the chapter's tables from saved reports
├── vocabulary_mismatch.py            counts relevant products with no matching term
├── COMMANDS.md                       every command, as run for the book
└── expected/                         the book's reference output
```

The feeder, the query tool and the evaluation tool are shared by every chapter and live in `shared/tools/`.

## What you need

Nothing new since Chapter 2\.

|  | Version used for the book | Notes |
| :---- | :---- | :---- |
| Docker | — | Give it **4 CPUs and 10 GB of memory**. Docker Desktop or Rancher Desktop both work. |
| Python | 3.11 (3.11.13) | Only needed to create the virtual environment; nothing is installed globally. |
| Vespa CLI | 8.562.17 | macOS: `brew install vespa-cli`. Linux and Windows: the Vespa GitHub releases page. |
| Disk | about 3 GB | The same as Chapter 2: the Vespa image, the cached dataset and the corpus build. |
| Network | — | Access to Hugging Face, only if the dataset is not already cached. |

The CLI and the Vespa server image (`vespaengine/vespa:8.751.13`) have different version numbers on purpose. Every pinned version is listed in `docs/pins.md` at the repository root.

## Run it

From the repository root:

```
./bootstrap.sh ch03
```

If you are continuing from Chapter 2, this reuses the running application, deploys this chapter's application package, and feeds all 101,341 products. If you are starting with this chapter, add `--fresh`: it removes any earlier virtual environment and Vespa container and builds everything from the beginning.

When you continue from Chapter 2, the deployment prints this warning:

```
WARNING Change(s) between active and new application that may require re-index:
reindexing: Consider re-indexing document type 'product' in cluster 'content' because:
    1) Document type 'product': Non-document field 'title_grams' added; this may be populated by reindexing
```

That is expected. This chapter adds a new field, `title_grams`, and the feed that follows processes all 101,341 products again, including the 2,000 already in the application, under the updated schema. You do not need to reindex separately.

On the reference machine, continuing from Chapter 2 took 3 minutes 30 seconds, of which the feed took 200.5 seconds at 506 documents per second. A fresh run with the dataset already cached took 4 minutes 37 seconds. If the dataset still needs to be downloaded, add the time described in Chapter 2; the `[corpus] shard N/15` lines mean it is working, not stuck.

A successful run ends with this state:

```
== at the start of ch03
   build      builds/esci-us-hard-book-s42-kdd-v4
   image      vespaengine/vespa:8.751.13
   documents  101341
   embedders  none declared
```

`embedders none declared` is correct: this chapter uses only lexical retrieval.

## The commands in this chapter

The steps below follow the chapter, section by section. Run them from the repository root after `bootstrap.sh` has finished.

Most commands save their result in `expected/`, replacing the book's copy of that file, so that `git diff chapters/ch03/expected/` shows how your run compares with the book's. To put the book's files back, run `git checkout chapters/ch03/expected/`.

### Load the whole catalogue

Bootstrap has already done this. To repeat the steps by hand:

```
vespa deploy --wait 300 chapters/ch03/app
.venv/bin/python shared/tools/feed.py builds/esci-us-hard-book-s42-kdd-v4/products.jsonl --out chapters/ch03/expected/feed.json --label "ch03 full feed (re-feed onto the populated index)" > chapters/ch03/expected/feed.block.md
```

**What you should see:** `Success: Deployed 'chapters/ch03/app' …`, then `101,341 ok, 0 failed, 0 retried in …`. Repeating the feed replaces documents with the same IDs, so the count stays at 101,341. The book's re-feed took 234.2 seconds; yours will differ.

### From text to terms

Nothing to run. The settings this section describes are in `app/schemas/product.sd`: `match: text` and `index: enable-bm25` on the text fields, `match: word` on `id`, the `default` fieldset, and the `title_grams` field outside it.

### What a query asks for

Send the chapter's query:

```
.venv/bin/python shared/tools/query.py --query "running shoes" --hits 5
```

**What you should see:** `1,300 matched, showing 5`, then five titles, all of them running shoes. With weakAnd, 1,300 is not a count of every product containing either word; the chapter explains why.

Then try the four YQL examples with the Vespa CLI:

```
vespa query 'yql=select id, title from product where title contains "running"' 'hits=5'
vespa query 'yql=select id, title from product where title contains "running" and brand contains "nike"' 'hits=5'
vespa query 'yql=select id, title from product where title contains phrase("running", "shoes")' 'hits=5'
vespa query 'yql=select id, title from product where userQuery() and has_description = true' 'query=running shoes' 'hits=5'
```

These are for exploring the query language. The book does not measure them, and nothing in `expected/` corresponds to them.

### A test set you can trust

From here on, most commands run `evaluate.py`. It sends every query in one set of judged queries to Vespa, compares the results with ESCI's judgements, prints four scores (ndcg@10, recall@10, recall@100 and mrr), and saves a report. Every `evaluate.py` command is built from the same options:

| Option | What it does |
| :---- | :---- |
| `--split` | Which set of judged queries to run. `validation` (735 queries) is used to compare profiles and choose settings. `test` (1,050 queries) is run only at the end, on the chosen settings, as an independent check. All 101,341 products are searched either way; only the queries, and the judgements they are scored against, change. A third set, `train` (1,715 queries), is used in later chapters. The option has no default, so you cannot run the test queries by accident. |
| `--ranking` | The rank profile to score with, such as `bm25_title` or `bm25_tuned`. |
| `--hits 100` | Keeps the top 100 results for each query, which recall@100 and mrr need. |
| `--passes 3` | Runs the whole query set three times after one discarded warm-up pass, so that latency can be measured. `random` uses `--passes 1`, because its order changes on every pass. |
| `--param` | Sets a rank-profile input for every query in the run, such as a field weight or a boost weight. |
| `--label` | The name the run is given in its report and in the chapter's tables. |
| `--out` | Where the report is saved. It is a JSON file with the four averages, a score for every query, and the run's latency. The chapter's tables are built from these reports in the last step. |

The two starting points, `random` and Chapter 2's `default`:

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 1 --ranking random  --label validation-random  --out chapters/ch03/expected/validation-random.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking default --label validation-default --out chapters/ch03/expected/validation-default.json
```

**What you should see:** ndcg@10 0.020 for `random` and 0.299 for `default`.

### BM25 on the title, and why more fields made it worse

BM25 on the title only, then on four fields added together, then on four fields weighted 3 / 1 / 0.5 / 1:

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_title    --label validation-bm25_title    --out chapters/ch03/expected/validation-bm25_title.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_all      --label validation-bm25_all      --out chapters/ch03/expected/validation-bm25_all.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_weighted --label validation-bm25_weighted --out chapters/ch03/expected/validation-bm25_weighted.json
```

**What you should see:** ndcg@10 0.422 for `bm25_title`, 0.323 for `bm25_all` and 0.400 for `bm25_weighted`. Both multi-field profiles score below the title alone.

To see which field causes the drop, *Measuring the Impact of Each Field* keeps the title at weight 1 and adds one other field at a time, using `bm25_weighted`'s weights as query inputs:

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_weighted --param 'input.query(w_title)=1' --param 'input.query(w_bullets)=0'   --param 'input.query(w_description)=0'   --param 'input.query(w_brand)=0.25' --label validation-bm25_weighted-t1-br025 --out chapters/ch03/expected/validation-bm25_weighted-t1-br025.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_weighted --param 'input.query(w_title)=1' --param 'input.query(w_bullets)=0.5' --param 'input.query(w_description)=0'   --param 'input.query(w_brand)=0'    --label validation-bm25_weighted-t1-b05   --out chapters/ch03/expected/validation-bm25_weighted-t1-b05.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_weighted --param 'input.query(w_title)=1' --param 'input.query(w_bullets)=0'   --param 'input.query(w_description)=0.5' --param 'input.query(w_brand)=0'    --label validation-bm25_weighted-t1-d05   --out chapters/ch03/expected/validation-bm25_weighted-t1-d05.json
```

**What you should see:** ndcg@10 0.423 with brand, 0.397 with bullets and 0.368 with description. Adding description costs the most.

The per-field scores behind Figure 3.4 come from the `explained` profile:

```
.venv/bin/python shared/tools/query.py --query "running shoes" --ranking explained --hits 5 --block features > chapters/ch03/expected/features-running-shoes.block.md
```

**What you should see** (in the saved file): a table with each hit's `title_score`, `bullets_score`, `description_score` and `brand_score`. The top hit's relevance is 35.652.

### Tuning BM25 and adding ranking signals

**The k1 × b grid.** `k1` controls how much a repeated word in the title adds to its score; `b` controls how much the title's length affects it. The application package holds fifteen rank profiles, one for each combination of five `k1` values (0.6, 0.9, 1.2, 1.5, 2.0) and three `b` values (0.4, 0.75, 1.0). Each is named after its values, so `bm25_k06_b075` means `k1` 0.6 and `b` 0.75. This loop runs all fifteen:

```
for k in 06 09 12 15 20; do
  for b in 04 075 10; do
    .venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 \
      --ranking bm25_k${k}_b${b} --label validation-bm25_k${k}_b${b} \
      --out chapters/ch03/expected/validation-bm25_k${k}_b${b}.json
  done
done
```

**What you should see:** fifteen sets of scores. The default setting, `bm25_k12_b075`, gives ndcg@10 0.422; `bm25_k06_b075` gives 0.432, the best in the grid.

**Query completeness and brand matching.** `bm25_tuned` uses `k1` 0.6 and `b` 0.75, and adds two signals with their own weights: `w_qcomplete` rewards a title that contains more of the query's words, and `w_brand` rewards a query word that matches the brand. The weights are query inputs, so each run below changes them with `--param` and nothing is redeployed.

First, both weights set to zero. This is BM25 with `k1` 0.6 alone, the baseline the other runs are compared against:

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=0' --param 'input.query(w_brand)=0' --label validation-bm25_tuned-k1only --out chapters/ch03/expected/validation-bm25_tuned-k1only.json
```

Then the profile with its default weights (5 and 1), and with other weights:

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --label validation-bm25_tuned --out chapters/ch03/expected/validation-bm25_tuned.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=3'  --param 'input.query(w_brand)=0' --label validation-bm25_tuned-qc3        --out chapters/ch03/expected/validation-bm25_tuned-qc3.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=5'  --param 'input.query(w_brand)=0' --label validation-bm25_tuned-qc5        --out chapters/ch03/expected/validation-bm25_tuned-qc5.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=10' --param 'input.query(w_brand)=0' --label validation-bm25_tuned-qc10       --out chapters/ch03/expected/validation-bm25_tuned-qc10.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=5'  --param 'input.query(w_brand)=3' --label validation-bm25_tuned-qc5-brand3  --out chapters/ch03/expected/validation-bm25_tuned-qc5-brand3.json
```

**What you should see:** ndcg@10 0.432 with both weights at zero, and 0.437 with the default weights. The last run, with the brand weight raised to 3, is in the saved comparison but not in the chapter's table; it scores 0.430.

### Reading a score: rank features

The `explained` command from the BM25 step is the one this section reads. The chapter also shows the top five under the final profile:

```
.venv/bin/python shared/tools/query.py --query "running shoes" --ranking bm25_tuned --hits 5 --block query > chapters/ch03/expected/query-101341.block.md
```

**What you should see** (in the saved file): five running shoes, with the top hit at 12.585. Ranks 2 and 3 are two different listings with the same title and the same score.

### Query profiles and ranking parameters

The query profile in `app/search/query-profiles/default.xml` makes `bm25_tuned` the default rank profile. Chapter 2's command, unchanged, now uses it:

```
.venv/bin/python shared/tools/query.py --query "running shoes" --hits 5
```

**What you should see:** the same five results as the `bm25_tuned` command above.

When you override a query input, use the full form, `--param 'input.query(w_qcomplete)=3'`. A bare `--param w_qcomplete=3` is accepted without an error but does not set the input, so the rank profile keeps its default value.

### The baseline report

The test queries, run once on the profiles the chapter compares:

```
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 1 --ranking random        --label test-random        --out chapters/ch03/expected/test-random.json
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking default       --label test-default       --out chapters/ch03/expected/test-default.json
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking bm25_title    --label test-bm25_title    --out chapters/ch03/expected/test-bm25_title.json
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking bm25_weighted --label test-bm25_weighted --out chapters/ch03/expected/test-bm25_weighted.json
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=0' --param 'input.query(w_brand)=0' --label test-bm25_tuned-k1only --out chapters/ch03/expected/test-bm25_tuned-k1only.json
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking bm25_tuned    --label test-bm25_tuned    --out chapters/ch03/expected/test-bm25_tuned.json
```

**What you should see:** ndcg@10 0.020, 0.295, 0.426, 0.409, 0.438 and 0.443, in that order. `bm25_tuned` is the highest.

One more validation run repeats `bm25_title` under a different label. Its scores should match the first `bm25_title` run exactly, which shows that repeating a run gives the same results:

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_title --label validation-bm25_title-tail --out chapters/ch03/expected/validation-bm25_title-tail.json
```

### Build the chapter's tables

`compare.py` does not query Vespa. It reads the reports saved above and prints one table, which the redirect (`>`) saves in `expected/`. `--block` chooses the kind of table:

- `evaluations` — one row per run, with its ndcg@10, recall@10, recall@100 and mrr  
- `comparison` — one line per run, showing how far it is above or below a chosen baseline run, with a 95% bootstrap interval for the difference  
- `grid` — the fifteen k1 × b results as a table, each compared with the default setting, `bm25_k12_b075`  
- `evaluations-latency` — the p50 and p95 latency of each run  
- `headline` — one run's scores, and how far it is above `random`

`--baseline` names the run that every other run is compared against. For example, `--baseline validation-bm25_title` makes each line read as "this profile against BM25 on the title alone". The baseline has no line of its own, because comparing it with itself would always give zero.

In comparison tables, each difference is followed by its interval and a label: **real** when the interval excludes zero, **inside the noise** when it includes zero.

Where each table appears in the chapter:

| Saved file | Where the chapter uses it |
| :---- | :---- |
| `compare-validation-evaluations.block.md` | *A starting point for comparison* and *BM25 on the title*: the validation scores of each profile |
| `compare-validation-comparison.block.md` | *Adding More Fields to BM25 Scoring*: each profile against `bm25_title` |
| `compare-validation-weights.block.md` | *Measuring the Impact of Each Field*: one extra field at a time against `bm25_title` |
| `compare-validation-grid.block.md` | *Tuning BM25 and Adding Ranking Signals*: the k1 × b grid |
| `compare-validation-boosts.block.md` | *Rewarding a title that matches every word*: each weight setting against `bm25_tuned-k1only` |
| `compare-test-evaluations.block.md` | *The Baseline Report*: the test scores of each profile |
| `compare-test-comparison.block.md` | *The Baseline Report*: `bm25_tuned` and the others against `bm25_title` on test |
| `compare-test-boost.block.md` | *The Baseline Report*: `bm25_tuned` against `bm25_tuned-k1only` on test |
| `compare-validation-latency.block.md` | *Query Latency Across Ranking Profiles* |
| `compare-validation-headline.block.md` | *Establishing the Baseline for Later Chapters*: `bm25_tuned` against `random` |

The commands, in the same order:

```
.venv/bin/python chapters/ch03/compare.py --block evaluations chapters/ch03/expected/validation-random.json chapters/ch03/expected/validation-default.json chapters/ch03/expected/validation-bm25_title.json chapters/ch03/expected/validation-bm25_all.json chapters/ch03/expected/validation-bm25_weighted.json chapters/ch03/expected/validation-bm25_tuned-k1only.json chapters/ch03/expected/validation-bm25_tuned.json > chapters/ch03/expected/compare-validation-evaluations.block.md
.venv/bin/python chapters/ch03/compare.py --block comparison --baseline validation-bm25_title chapters/ch03/expected/validation-bm25_title.json chapters/ch03/expected/validation-default.json chapters/ch03/expected/validation-bm25_all.json chapters/ch03/expected/validation-bm25_weighted.json chapters/ch03/expected/validation-bm25_tuned-k1only.json chapters/ch03/expected/validation-bm25_tuned.json chapters/ch03/expected/validation-bm25_title-tail.json > chapters/ch03/expected/compare-validation-comparison.block.md
.venv/bin/python chapters/ch03/compare.py --block comparison --baseline validation-bm25_title chapters/ch03/expected/validation-bm25_title.json chapters/ch03/expected/validation-bm25_weighted-t1-br025.json chapters/ch03/expected/validation-bm25_weighted-t1-b05.json chapters/ch03/expected/validation-bm25_weighted-t1-d05.json chapters/ch03/expected/validation-bm25_weighted.json > chapters/ch03/expected/compare-validation-weights.block.md
.venv/bin/python chapters/ch03/compare.py --block grid chapters/ch03/expected/validation-bm25_k06_b04.json chapters/ch03/expected/validation-bm25_k06_b075.json chapters/ch03/expected/validation-bm25_k06_b10.json chapters/ch03/expected/validation-bm25_k09_b04.json chapters/ch03/expected/validation-bm25_k09_b075.json chapters/ch03/expected/validation-bm25_k09_b10.json chapters/ch03/expected/validation-bm25_k12_b04.json chapters/ch03/expected/validation-bm25_k12_b075.json chapters/ch03/expected/validation-bm25_k12_b10.json chapters/ch03/expected/validation-bm25_k15_b04.json chapters/ch03/expected/validation-bm25_k15_b075.json chapters/ch03/expected/validation-bm25_k15_b10.json chapters/ch03/expected/validation-bm25_k20_b04.json chapters/ch03/expected/validation-bm25_k20_b075.json chapters/ch03/expected/validation-bm25_k20_b10.json > chapters/ch03/expected/compare-validation-grid.block.md
.venv/bin/python chapters/ch03/compare.py --block comparison --baseline validation-bm25_tuned-k1only chapters/ch03/expected/validation-bm25_tuned-k1only.json chapters/ch03/expected/validation-bm25_tuned-qc3.json chapters/ch03/expected/validation-bm25_tuned-qc5.json chapters/ch03/expected/validation-bm25_tuned-qc10.json chapters/ch03/expected/validation-bm25_tuned-qc5-brand3.json chapters/ch03/expected/validation-bm25_tuned.json > chapters/ch03/expected/compare-validation-boosts.block.md
.venv/bin/python chapters/ch03/compare.py --block evaluations chapters/ch03/expected/test-random.json chapters/ch03/expected/test-default.json chapters/ch03/expected/test-bm25_title.json chapters/ch03/expected/test-bm25_weighted.json chapters/ch03/expected/test-bm25_tuned-k1only.json chapters/ch03/expected/test-bm25_tuned.json > chapters/ch03/expected/compare-test-evaluations.block.md
.venv/bin/python chapters/ch03/compare.py --block comparison --baseline test-bm25_title chapters/ch03/expected/test-bm25_title.json chapters/ch03/expected/test-default.json chapters/ch03/expected/test-bm25_weighted.json chapters/ch03/expected/test-bm25_tuned-k1only.json chapters/ch03/expected/test-bm25_tuned.json > chapters/ch03/expected/compare-test-comparison.block.md
.venv/bin/python chapters/ch03/compare.py --block comparison --baseline test-bm25_tuned-k1only chapters/ch03/expected/test-bm25_tuned-k1only.json chapters/ch03/expected/test-bm25_tuned.json > chapters/ch03/expected/compare-test-boost.block.md
.venv/bin/python chapters/ch03/compare.py --block evaluations-latency chapters/ch03/expected/validation-default.json chapters/ch03/expected/validation-bm25_title.json chapters/ch03/expected/validation-bm25_all.json chapters/ch03/expected/validation-bm25_weighted.json chapters/ch03/expected/validation-bm25_tuned-k1only.json chapters/ch03/expected/validation-bm25_tuned.json > chapters/ch03/expected/compare-validation-latency.block.md
.venv/bin/python chapters/ch03/compare.py --block headline --headline validation-bm25_tuned --baseline validation-random chapters/ch03/expected/validation-random.json chapters/ch03/expected/validation-bm25_tuned.json > chapters/ch03/expected/compare-validation-headline.block.md
```

### What the lexical lens cannot see

The chapter's examples, such as `talkbox keyboard`, are products that share no searchable word with the query. `vocabulary_mismatch.py` counts how many judged-relevant products are in that position. The chapter text does not quote its counts, but the script and its reference output are included here:

```
.venv/bin/python chapters/ch03/vocabulary_mismatch.py --split validation --ranking bm25_tuned --out chapters/ch03/expected/vocabulary-validation.json > chapters/ch03/expected/vocabulary-validation.block.md
.venv/bin/python chapters/ch03/vocabulary_mismatch.py --split test       --ranking bm25_tuned --out chapters/ch03/expected/vocabulary-test.json       > chapters/ch03/expected/vocabulary-test.block.md
```

For each judged-relevant product that `bm25_tuned` did not return in its top 100, the script re-runs the query restricted to that one product. If nothing matches, the query and the product share no searchable term.

**What you should see** (test split): 11,527 found, 6,132 missed, 1,452 of the missed with no term to match on, 647 of those graded Exact: 8.2% of all 17,659 relevant query-product pairs. Example pairs, including `talkbox keyboard`, are printed to the terminal and saved in the JSON file.

## Comparing your run with the book's

`expected/` holds the output of every command above, exactly as it ran when the book was written, on a fresh run (`--fresh`). Two kinds of number are in there, and they behave differently:

- **Quality numbers** — ndcg@10, recall, mrr, the bootstrap intervals and the vocabulary counts. Given the same build and the same 101,341 documents, every ndcg@10 and recall figure should come back within 0.002, apart from `random`, which reorders on every run. mrr can move by up to about 0.003, because products with equal relevance scores, such as the two *Nike Women's Revolution 4 Running Shoe* listings, are not always returned in the same order. In the vocabulary counts, the no-match and Exact numbers come back exactly, while the found and missed numbers can move by a few products at the top-100 boundary. If your numbers differ by more than that, something about what you ran is different; start with `docs/pins.md`.  
- **Cost numbers** — feed timings, documents per second, and p50 and p95 latency. These describe one machine on one day (an Apple M4 Pro, Docker with 4 CPUs / 10 GB). Latency is measured after a discarded warm-up pass. Yours will differ, and that is expected.

After a run, `git diff chapters/ch03/expected/` shows every difference.

## If something goes wrong

**The deploy prints a re-index warning about `title_grams`** — expected when continuing from Chapter 2\. The full feed that follows processes every product under the updated schema.

**A boost or field-weight setting seems to have no effect** — check the parameter name. It must be the full form, `--param 'input.query(w_qcomplete)=3'`. The bare form, `--param w_qcomplete=3`, is accepted without an error but leaves the rank profile on its default value, so the run looks normal.

**`compare.py` stops with an error about a missing file** — it reads saved reports, so every run it names has to have been run first, with `--out`. Run the missing evaluation, then the `compare.py` command again.

**Your relevance values are a few hundredths lower than the book's** — you probably continued from Chapter 2\. That path indexes Chapter 2's 2,000 products twice, and BM25's collection statistics reflect what was indexed, so every relevance value comes out slightly lower: the top `running shoes` hit scores 12.530 instead of 12.585, and rank 5 can be a different product. The evaluation tables still agree with the book's to within 0.001 in ndcg@10. Rerun with `--fresh` for identical relevance values.

**A quality number differs from the book's by 0.001, or an mrr by up to 0.003** — tied results, not a fault. See *Comparing your run with the book's*.

**`running shoes` reports 1,300 matches, not every product containing either word** — expected. `userQuery()` uses weakAnd, and its reported count is not an exhaustive count of every product that contains a query term.

**The container fails to start because a port is already allocated** — something else on your machine is using port 8080 or 19071\. Stop it, or stop the other Vespa container, then rerun with `--fresh`.

**The deploy or feed fails, or Vespa stops responding partway** — check that Docker really has 4 CPUs and 10 GB. Every run behind the book used exactly that, so too little memory is the first thing to rule out.

**The first run is very slow** — if the dataset is not cached yet, it is limited by your network, not your machine. Once the dataset is cached, it does not need downloading again.

**The vocabulary counts appear with extra lines in your terminal** — the example query-product pairs go to a different output stream from the counts, and a terminal shows both. Redirect the output to a file and you will see only the counts.

## Next

When you are ready for Chapter 4:

```
./bootstrap.sh ch04
```

It keeps the catalogue this chapter fed and adds semantic retrieval.