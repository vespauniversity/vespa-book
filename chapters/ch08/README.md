# Chapter 8 — Filtering, Constraints, and Access Control

This directory is the code for Chapter 8 of *Production AI Search with Vespa*. It gives every product a seller identity, `tenant_id`, derived from its brand, and then asks two questions about the same 101,341 products and the same validation queries. First: does adding a filter break vector search, and does the answer depend on whether the filter is checked before or after the search runs? The chapter measures five filters of very different selectivity (the *ladder*) under five strategies. Second: can a seller's staff be kept to their own listings? The chapter builds an authorized query path whose mandatory filter comes from the caller's identity rather than from the request, and tests it for leaks with a test that is itself shown to catch one.

The book explains what each step does and why. This page is the practical half: what to run, in the same order as the chapter, what you should see, and what to do when something goes wrong.

## What is in this directory

```
chapters/ch08/
├── app/                                  the application package Vespa deploys
│   ├── services.xml                      unchanged from Chapters 6 and 7
│   ├── models/                           the cross-encoder file, fetched by bootstrap.sh (not in the repository)
│   ├── schemas/
│   │   ├── product.sd                    Chapter 6's schema, plus tenant_id and fast-search on has_description
│   │   └── product/                      one file per rank profile: Chapters 3 to 6's, unchanged
│   └── search/query-profiles/
│       ├── default.xml                   request defaults, unchanged: bm25_tuned is still the default
│       ├── tenant.xml                    new: the hybrid request with the seller boundary attached
│       └── types/
│           └── tenant.xml                new: makes the tenant value a mandatory string
├── chapter.toml                          what bootstrap.sh needs for this chapter
├── derive_tenants.py                     derives tenant_id from brand, the staff registry and the ladder
├── rungs.py                              the five filter clauses, and wrap_where, which ANDs a clause onto a request
├── filtered_ann.py                       filtered nearest-neighbor search: one rung, one strategy, several exploration settings
├── authorized_query.py                   the trusted endpoint: derives the filter from the caller's identity
├── leakage_test.py                       the negative test: counts hits outside each account's allowed sellers
├── COMMANDS.md                           every command, as run for the book
└── expected/                             the book's reference output
```

Chapter 7's trained models and their rank profiles are not in this package. Nothing in this chapter ranks with them; every question here is about which products a request may consider, not the order they come back in.

The query tool and the memory tool are shared by every chapter and live in `shared/tools/`.

## What you need

The same as Chapter 6. The training packages Chapter 7 added are not needed here.

|  | Version used for the book | Notes |
| :---- | :---- | :---- |
| Docker | — | Give it **4 CPUs and 10 GB of memory**. Docker Desktop or Rancher Desktop both work. |
| Python | 3.11 (3.11.13) | Only needed to create the virtual environment. |
| Vespa CLI | 8.562.17 | macOS: `brew install vespa-cli`. Linux and Windows: the Vespa GitHub releases page. |
| Models | Chapter 6's three | `bge-small-en-v1.5`, `colbertv2.0` and `ms-marco-MiniLM-L6-v2`, already in place if you are continuing. The package still declares the ColBERT and cross-encoder fields and profiles, so the files must be present even though this chapter's measurements do not use them. |
| Network | — | Access to Hugging Face, only when starting fresh. |

Every pinned version is listed in `docs/pins.md` at the repository root.

## Run it

From the repository root:

```
./bootstrap.sh ch08
```

If you are continuing from Chapter 7, this deploys the chapter's application package, which adds `tenant_id`, turns on `fast-search` for `has_description`, and drops Chapter 7's model files and rank profiles. The chapter then fills `tenant_id` on every product with a partial update.

The deployment prints two warnings. The first, about `document-summary 'context'`, is the same as in Chapters 5 to 7 and is expected. The second says the change requires a restart:

```
WARNING Change(s) between active and new application that require restart:
...
    1) Document type 'product': Field 'has_description' changed: add attribute 'fast-search'
```

That is expected too. Turning on `fast-search` for an attribute that already holds data takes effect only after the search node restarts. `bootstrap.sh` restarts it, waits until it answers again at the full document count, and only then sends the partial update. It also counts the documents carrying `tenant_id` afterwards and sends the update again if the count is short of 101,341.

If you are starting with this chapter, add `--fresh`. It builds everything from the beginning, deploys the schema before feeding, so there is no restart, then feeds the catalogue once and runs the same update.

On the reference machine (Apple M4 Pro, container VM with 4 CPUs and 10 GB), continuing from Chapter 7 took 266 seconds, of which the update was 224.0 seconds at 452 documents per second. A fresh run fed the catalogue in 1,742.6 seconds and ran the update in another 232.4 seconds. A first run that also had to read the dataset from Hugging Face spent a further 832 seconds on that. Your timings will differ.

While the update runs, the derivation prints a summary of the tenants it found:

```
40,337 tenants, 27,342 singletons, marketplace 5,397, largest brand 'nike' (604)
```

A successful run ends with the same state as Chapter 7:

```
== at the start of ch08
   build      builds/esci-us-hard-book-s42-kdd-v4
   image      vespaengine/vespa:8.751.13
   documents  101341
   embedders  embedder=BAAI/bge-small-en-v1.5@5c38ec7c colbert=colbert-ir/colbertv2.0@c1e84128
```

## The commands in this chapter

The steps below follow the chapter, section by section. Run them from the repository root after `bootstrap.sh` has finished.

Most commands save their result in `expected/`, replacing the book's copy of that file, so that `git diff chapters/ch08/expected/` shows how your run compares with the book's. To put the book's files back, run `git checkout chapters/ch08/expected/`.

**Budget your time.** This chapter is much quicker than Chapters 6 and 7: no request reaches the cross-encoder. Going by the latencies they record, each filtered-search run takes about one to two minutes on the reference machine, and the 26 of them about half an hour together. The memory reading takes at least twenty minutes on its own.

**How the filtered-search commands work.** `filtered_ann.py` takes Chapter 4's `nearestNeighbor(title_embedding, q)` request unchanged, adds the clause for one rung of the ladder, and sends the strategy as `ranking.matching.*` request parameters:

| Option | What it does |
| :---- | :---- |
| `--rung` | One of `has_brand`, `has_description`, `marketplace`, `nike`, `small_brand`, or `none` for no filter. The clauses are in `rungs.py`. |
| `--strategy` | `default` sends no strategy parameters, so Vespa's own thresholds decide. `pre` checks the filter during the graph search. `post` searches without the filter and discards failures afterward. `pre_full` is `pre` with the filter-first walk switched off. `exact` skips the graph and scores every passing product. |
| `--explore` | The `hnsw.exploreAdditionalHits` values to run, Chapter 4's 0, 20, 100 and 500. |
| `--hits 100` | The vector side's target, and the size of the top 100 compared with exact search. |
| `--passes 3` | Three timed passes after one discarded warm-up pass; latency is their median. |
| `--retriever` | `lexical` or `hybrid` instead of the vector-only request. These rows report latency only. |

Each run writes a JSON report; the same tool with `--from <report> --block rung` prints the table for the page and queries nothing.

**Reading the tables.** The column the chapter calls *neighbor recall@100* is printed as `agreement@100`: the share of exact search's own top 100, under the same filter, that the approximate search also returned. When a rung has fewer than 100 products (small_brand has ten), the denominator is what exact search actually returned. `empty queries` counts the queries for which approximate search returned nothing while exact search found something. `algorithm` is the branch Vespa's query trace reports for one traced query of the run.

### Structured attributes, eligibility rules, and exact-match filters

The `tenant_id` declaration and the `fast-search` change are in `app/schemas/product.sd`. Nothing to run for them; `bootstrap.sh` deployed and filled them.

**A ladder of filters.** `bootstrap.sh` has already run the derivation once. Run it again, then print the ladder:

```
.venv/bin/python chapters/ch08/derive_tenants.py --out chapters/ch08/expected/tenants.json --users-out chapters/ch08/expected/users.json
.venv/bin/python chapters/ch08/derive_tenants.py --from chapters/ch08/expected/tenants.json --block ladder > chapters/ch08/expected/ladder.block.md
```

The first command also writes `users.json`, the registry of five invented staff accounts used in the authorization sections.

**What you should see:** 95,944 products (94.67%) for has_brand, 51,995 (51.31%) for has_description, 5,397 (5.33%) for marketplace, 604 (0.60%) for nike and 10 (0.01%) for small_brand. These depend only on the corpus build, so they come back exactly.

### Expressing constraints in YQL

The running query, unfiltered and with the Nike filter:

```
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking hybrid_linear --hits 5 --block query > chapters/ch08/expected/query-running-shoes.block.md
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking hybrid_linear --hits 5 --where 'tenant_id contains "nike"' --block query > chapters/ch08/expected/query-running-shoes-nike.block.md
```

`--where` ANDs its clause onto the retriever's own YQL through `rungs.wrap_where`, which puts the existing `where` expression in parentheses first, so the hybrid request's `or` cannot let keyword matches past the filter.

**What you should see:** 1,300 matched without the filter and 204 with it. With the filter, all five hits are Nike listings. *Nike Kids' Preschool Flex Runner Running Shoes*, rank 2 at 0.759 without the filter, is rank 1 at 0.956 with it.

### Filters meet the graph: selectivity, pre-filtering, and post-filtering

**The baseline with no filter.** Run this first, before any filtered run:

```
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-none-default.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --from chapters/ch08/expected/validation-filtered-ann-none-default.json --block rung > chapters/ch08/expected/validation-filtered-ann-none-default.block.md
```

**What you should see:** neighbor recall@100 of 0.908, 0.928, 0.960 and 0.990 at the four exploration settings, at 13.8 to 15.2 ms p50. Chapter 4 measured 0.911, 0.928, 0.961 and 0.990 on a different feed of the same data.

**A loose filter is close to free.** Pre-filtering and Vespa's default at the two loose rungs:

```
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_description --strategy pre --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-has_description-pre.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_description --strategy pre --from chapters/ch08/expected/validation-filtered-ann-has_description-pre.json --block rung > chapters/ch08/expected/validation-filtered-ann-has_description-pre.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_description --strategy default --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-has_description-default.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_description --strategy default --from chapters/ch08/expected/validation-filtered-ann-has_description-default.json --block rung > chapters/ch08/expected/validation-filtered-ann-has_description-default.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_brand --strategy pre --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-has_brand-pre.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_brand --strategy pre --from chapters/ch08/expected/validation-filtered-ann-has_brand-pre.json --block rung > chapters/ch08/expected/validation-filtered-ann-has_brand-pre.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_brand --strategy default --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-has_brand-default.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_brand --strategy default --from chapters/ch08/expected/validation-filtered-ann-has_brand-default.json --block rung > chapters/ch08/expected/validation-filtered-ann-has_brand-default.block.md
```

**What you should see:** at has_description, `pre` reads 0.919, 0.936, 0.966 and 0.993 with 0 empty queries, at 14.2 to 16.5 ms. At has_brand, 0.910 at the default exploration and 0.990 at the widest, at 13.7 to 15.1 ms. The `default` rows match `pre` at both rungs, and `algorithm` reads `index top k using filter`.

**Searching first, filtering after.** Post-filtering at every rung:

```
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_brand --strategy post --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-has_brand-post.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_brand --strategy post --from chapters/ch08/expected/validation-filtered-ann-has_brand-post.json --block rung > chapters/ch08/expected/validation-filtered-ann-has_brand-post.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_description --strategy post --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-has_description-post.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_description --strategy post --from chapters/ch08/expected/validation-filtered-ann-has_description-post.json --block rung > chapters/ch08/expected/validation-filtered-ann-has_description-post.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy post --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-marketplace-post.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy post --from chapters/ch08/expected/validation-filtered-ann-marketplace-post.json --block rung > chapters/ch08/expected/validation-filtered-ann-marketplace-post.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy post --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-nike-post.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy post --from chapters/ch08/expected/validation-filtered-ann-nike-post.json --block rung > chapters/ch08/expected/validation-filtered-ann-nike-post.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung small_brand --strategy post --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-small_brand-post.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung small_brand --strategy post --from chapters/ch08/expected/validation-filtered-ann-small_brand-post.json --block rung > chapters/ch08/expected/validation-filtered-ann-small_brand-post.block.md
```

**What you should see:** at the default exploration, 0.874 at has_brand, 0.860 at has_description, 0.342 at marketplace (22 empty queries), 0.085 at nike (395 empty) and 0.011 at small_brand (701 empty). Post-filtering trails pre-filtering at every rung. At has_description its widest setting, 0.898, is still below `pre`'s narrowest, 0.919. From marketplace down the lines are nearly flat across exploration settings, and the p50 is 16.4 to 16.9 ms, slower than pre-filtering at the same rungs.

### When the filtered walk finds nothing

Pre-filtering at the three selective rungs:

```
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy pre --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-marketplace-pre.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy pre --from chapters/ch08/expected/validation-filtered-ann-marketplace-pre.json --block rung > chapters/ch08/expected/validation-filtered-ann-marketplace-pre.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy pre --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-nike-pre.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy pre --from chapters/ch08/expected/validation-filtered-ann-nike-pre.json --block rung > chapters/ch08/expected/validation-filtered-ann-nike-pre.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung small_brand --strategy pre --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-small_brand-pre.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung small_brand --strategy pre --from chapters/ch08/expected/validation-filtered-ann-small_brand-pre.json --block rung > chapters/ch08/expected/validation-filtered-ann-small_brand-pre.block.md
```

**What you should see:** at nike, 0.242 with 557 of 735 queries empty, at every exploration setting. At marketplace, 99 queries empty at every setting, while recall rises from 0.697 to 0.822 as exploration widens. At small_brand, 0.017 with 720 empty. `algorithm` reads `index top k using filter` on both sides of the filter-first threshold; the trace field that names the switch, `filter_first_heuristic_used`, is not read by this tool.

**Switching the filter-first walk off.** The same three rungs with `pre_full`:

```
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy pre_full --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-marketplace-pre_full.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy pre_full --from chapters/ch08/expected/validation-filtered-ann-marketplace-pre_full.json --block rung > chapters/ch08/expected/validation-filtered-ann-marketplace-pre_full.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy pre_full --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-nike-pre_full.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy pre_full --from chapters/ch08/expected/validation-filtered-ann-nike-pre_full.json --block rung > chapters/ch08/expected/validation-filtered-ann-nike-pre_full.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung small_brand --strategy pre_full --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-small_brand-pre_full.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung small_brand --strategy pre_full --from chapters/ch08/expected/validation-filtered-ann-small_brand-pre_full.json --block rung > chapters/ch08/expected/validation-filtered-ann-small_brand-pre_full.block.md
```

**What you should see:** no empty queries at any of the three rungs. At the default exploration, recall is 0.964 at marketplace, 0.995 at nike and 1.000 at small_brand, at a p50 of 25.4, 36.2 and 47.2 ms, against 13.9, 12.3 and 11.7 ms for `pre`.

### What Vespa's defaults choose

The default at the three selective rungs, and exact search forced at the two rungs where the default does not choose it:

```
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy default --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-marketplace-default.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy default --from chapters/ch08/expected/validation-filtered-ann-marketplace-default.json --block rung > chapters/ch08/expected/validation-filtered-ann-marketplace-default.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy default --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-nike-default.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy default --from chapters/ch08/expected/validation-filtered-ann-nike-default.json --block rung > chapters/ch08/expected/validation-filtered-ann-nike-default.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung small_brand --strategy default --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-small_brand-default.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung small_brand --strategy default --from chapters/ch08/expected/validation-filtered-ann-small_brand-default.json --block rung > chapters/ch08/expected/validation-filtered-ann-small_brand-default.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy exact --explore 0 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-marketplace-exact.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung marketplace --strategy exact --from chapters/ch08/expected/validation-filtered-ann-marketplace-exact.json --block rung > chapters/ch08/expected/validation-filtered-ann-marketplace-exact.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_description --strategy exact --explore 0 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-has_description-exact.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung has_description --strategy exact --from chapters/ch08/expected/validation-filtered-ann-has_description-exact.json --block rung > chapters/ch08/expected/validation-filtered-ann-has_description-exact.block.md
```

The `exact` runs take one exploration setting only, because exact search walks no graph. The `default` in their `explore` column means no exploration was sent, not the default strategy.

**What you should see:** at nike and small_brand the default reads 1.000 with `algorithm` `exact`, at 12.8 and 11.7 ms. At marketplace, the rung between the two thresholds, the default is identical to the failing `pre` row: 0.697 with 99 empty queries, at 13.5 ms. Forced exact search reads 1.000 at 14.9 ms at marketplace and 17.4 ms at has_description.

**The repeat of the baseline.** Run this after every filtered run above, as a check that the container's answers have not drifted during the session:

```
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --explore 0 20 100 500 --hits 100 --passes 3 --out chapters/ch08/expected/validation-filtered-ann-none-default-tail.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --from chapters/ch08/expected/validation-filtered-ann-none-default-tail.json --block rung > chapters/ch08/expected/validation-filtered-ann-none-default-tail.block.md
```

**What you should see:** the same recall as the first baseline run to four decimals, and latency a fraction of a millisecond apart.

**The summary tables.** Every rung and strategy side by side, at the narrowest and widest exploration settings. These read the reports and query nothing:

```
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --from chapters/ch08/expected/validation-filtered-ann-*.json --block summary --at-explore 0 > chapters/ch08/expected/validation-filtered-ann-summary-explore0.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --from chapters/ch08/expected/validation-filtered-ann-*.json --block summary --at-explore 500 > chapters/ch08/expected/validation-filtered-ann-summary-explore500.block.md
```

The `--rung` and `--strategy` values are required by the tool but ignored with `--block summary`. In the summary, the `exact` rows repeat their single run at both exploration settings, and the repeat of the baseline appears as `default, tail run`.

**What you should see:** the numbers quoted in the sections above, in one table for each exploration setting.

### The same filter under lexical, vector, and hybrid retrieval

The Nike filter and no filter, under the keyword-only and hybrid requests:

```
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy default --retriever lexical --explore 0 --passes 3 --out chapters/ch08/expected/validation-filtered-latency-nike-lexical.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy default --retriever lexical --from chapters/ch08/expected/validation-filtered-latency-nike-lexical.json --block rung > chapters/ch08/expected/validation-filtered-latency-nike-lexical.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy default --retriever hybrid --explore 0 --passes 3 --out chapters/ch08/expected/validation-filtered-latency-nike-hybrid.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung nike --strategy default --retriever hybrid --from chapters/ch08/expected/validation-filtered-latency-nike-hybrid.json --block rung > chapters/ch08/expected/validation-filtered-latency-nike-hybrid.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --retriever lexical --explore 0 --passes 3 --out chapters/ch08/expected/validation-filtered-latency-none-lexical.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --retriever lexical --from chapters/ch08/expected/validation-filtered-latency-none-lexical.json --block rung > chapters/ch08/expected/validation-filtered-latency-none-lexical.block.md
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --retriever hybrid --explore 0 --passes 3 --out chapters/ch08/expected/validation-filtered-latency-none-hybrid.json
.venv/bin/python chapters/ch08/filtered_ann.py --split validation --rung none --strategy default --retriever hybrid --from chapters/ch08/expected/validation-filtered-latency-none-hybrid.json --block rung > chapters/ch08/expected/validation-filtered-latency-none-hybrid.block.md
```

These rows print a dash for `agreement@100`, `empty queries` and `algorithm`. That is expected: a keyword-only or hybrid result is not compared with exact vector search, so only latency is reported.

**What you should see:** lexical at 4.5 ms without the filter and 3.5 ms with it; hybrid at 15.2 and 13.8 ms. The vector-only figures for the same comparison, 13.8 and 12.8 ms, are the `none` and `nike` default rows above.

### Tenants and authorization as mandatory filters

**Document-level authorization.** The staff registry is `expected/users.json`, written by `derive_tenants.py` above. Its five accounts are invented to demonstrate the mechanism and to run the leakage test; they support no relevance claim:

| Account | Allowed sellers |
| :---- | :---- |
| `nike_staff` | nike |
| `fox_staff` | 20th century fox |
| `marketplace_staff` | `__marketplace__` |
| `agency` | nike, adidas, hanes |
| `auditor` | every seller (`*`), so no filter |

**Trusted query construction.** The running query through the authorized endpoint:

```
.venv/bin/python chapters/ch08/authorized_query.py --user nike_staff --query "running shoes" --retriever hybrid --hits 5 --block hits > chapters/ch08/expected/authorized-running-shoes-nike_staff.block.md
```

`authorized_query.py` takes no filter. It looks the account up in the registry, builds `tenant_id in (...)` itself, and ANDs it onto the retriever's YQL with `wrap_where`. Here `--user` stands in for an authenticated identity: it is a test harness, not authentication, and anyone who can choose `--user` can choose `auditor`. A deployed service derives the identity from verified credentials.

**What you should see:** 204 matched and the same five Nike listings as the `--where` example in *Expressing constraints in YQL*, each with tenant `nike`.

**Moving the boundary into deployed configuration.** The same request through the `tenant` query profile, and the same request with the profile's mandatory value left out:

```
.venv/bin/python chapters/ch08/authorized_query.py --user nike_staff --query "running shoes" --retriever hybrid --hits 5 --profile --block hits > chapters/ch08/expected/authorized-running-shoes-nike_staff-profile.block.md
.venv/bin/python chapters/ch08/authorized_query.py --user nike_staff --query "running shoes" --retriever hybrid --hits 5 --profile --omit-tenant --block refusal > chapters/ch08/expected/authorized-profile-missing-tenant.block.md
```

With `--profile`, the request sends no YQL: only `queryProfile=tenant`, the query text, the query vector, `hits`, and the `tenant` value the endpoint built from the registry, a list of quoted seller names such as `"nike"`. The profile holds the hybrid request with `and tenant_id in (%{tenant})` attached, and its `yql` is declared `overridable="false"`. `--profile` works only with `--retriever hybrid`, and not for the `auditor`, because the profile always filters.

**What you should see:** the first command prints the same 204 matched and five hits, with the retriever shown as `hybrid via query profile tenant`. The second prints Vespa's refusal, verbatim:

```
Incomplete query: Parameter 'tenant' is mandatory in query profile 'tenant' of type 'tenant' but is not set
```

### Testing that nothing leaks

Every validation query, through the authorized endpoint, for each of the five accounts and each of the three retrievers, plus a forged request:

```
.venv/bin/python chapters/ch08/leakage_test.py --split validation --users chapters/ch08/expected/users.json --hits 10 --out chapters/ch08/expected/leakage-validation.json
.venv/bin/python chapters/ch08/leakage_test.py --split validation --from chapters/ch08/expected/leakage-validation.json --block leakage > chapters/ch08/expected/leakage-validation.block.md
```

The tool counts any returned hit whose `tenant_id` is outside the account's allowed sellers. The last three rows are the positive control: `nike_staff` through a deliberately untrusted variant of the endpoint (`authorized_query.py --untrusted --tenant`), which takes the seller from the request and asks for `adidas`. That variant exists only for this test; a trusted service never takes that path.

**What you should see:** `leaked total: 0` over the fifteen trusted rows, 96,952 hits returned in total, and a detection line reading `leaked 4514 (lexical) / 7350 (semantic) / 7350 (hybrid)`: every hit of the forged request counted as leaked.

**Safe is not the same as complete.** In the same table, `marketplace_staff`'s semantic row returns 6,279 hits out of a possible 7,350, with none leaked. That account's filter is exactly the marketplace rung, where the default takes the filter-first walk. The hybrid row for the same account returns 7,267.

**What the constraints cost in memory.** At least twenty minutes. For a reading comparable with the book's, run it straight after the bootstrap, before the evaluations:

```
.venv/bin/python shared/tools/memory.py --settle 600 --rounds 3 --tolerance 0.01 --out chapters/ch08/expected/memory.json
.venv/bin/python shared/tools/memory.py --from chapters/ch08/expected/memory.json > chapters/ch08/expected/memory.block.md
```

**What you should see:** about 1,352 MB on the book's container, beside 156 MB computed by hand for the title vectors (101,341 × 384 × 4 bytes). As in Chapters 6 and 7, the reading depends on the container's history. Check that the report says `settled: true`.

## Comparing your run with the book's

`expected/` holds the output of every command above, exactly as it ran when the book was written. Four kinds of number are in there, and they behave differently:

- **Counts from the corpus build** — the ladder, the tenant summary and the registry. These come back exactly.
- **Recall and empty-query counts** — these come from the HNSW graph, which is built slightly differently on every feed. The unfiltered and loose-filter figures land within a few thousandths. At marketplace, nike and small_brand, another graph build empties a somewhat different number of queries and can move recall from the second decimal at marketplace; `marketplace_staff`'s hit counts in the leakage table move with it. What should reproduce is the pattern: post-filtering trailing everywhere, `pre` emptying whole queries below the filter-first threshold, `pre_full` and exact search emptying none, and the default matching `pre` at marketplace and exact search at nike and small_brand. The `exact` rows themselves read 1.000.
- **Leakage counts** — `leaked total: 0` on the trusted rows, and every forged hit counted as leaked, should come back exactly. Hit counts for the `semantic` and `hybrid` rows at marketplace can move with the graph, as above.
- **Cost numbers** — bootstrap timings, latency and memory. These describe one machine on one day (an Apple M4 Pro, Docker with 4 CPUs / 10 GB), one query at a time, after a discarded warm-up pass. Yours will differ, and that is expected.

After a run, `git diff chapters/ch08/expected/` shows every difference.

## If something goes wrong

**The nike rung matches fewer than 604 products, or brandless listings turn up in has_brand** — some products lost `tenant_id`. A value set by a partial update lasts only until the same product is fed again whole, and a later put without the field leaves it empty, with no error. If you have fed any products by hand since the bootstrap, run the update again; `./bootstrap.sh ch08` will not, because it skips the update once any document carries the field:

```
.venv/bin/python chapters/ch08/derive_tenants.py --out chapters/ch08/expected/tenants.json --users-out chapters/ch08/expected/users.json && .venv/bin/python shared/tools/feed.py builds/esci-us-hard-book-s42-kdd-v4/tenants.jsonl --out chapters/ch08/expected/feed-tenants.json
```

**The deploy warns that a restart is required** — expected when continuing from Chapter 7; `bootstrap.sh` restarts the search node itself. If you deployed by hand with `vespa deploy`, the `fast-search` change on `has_description` does not take effect until the search node restarts.

**Recall at small_brand looks impossibly low, or impossibly high** — small_brand has only ten products, so a query can have at most ten correct answers. The denominator is what exact search returned, not the 100 requested.

**Widening exploration does not change a selective rung's numbers** — expected at nike and small_brand under `pre`. Most queries return nothing, and exploration cannot rescue a walk that has already run out of passing neighbors. Read the `empty queries` column beside a flat recall figure before concluding the search has converged.

**A lexical or hybrid row prints dashes instead of recall** — expected. Those rows report latency only.

**`authorized_query.py` says `unknown user`** — the account is not in `users.json`. Use one of the five accounts, or rerun `derive_tenants.py` to rewrite the registry.

**`--profile` refuses to run** — it works only with `--retriever hybrid`, never with `--untrusted`, and not for the `auditor`, whose allowed set is every seller.

**The memory reading is higher than the book's** — the container has a longer history. If the report says `settled: false`, run it again when nothing else is querying the container.

**The deploy or feed fails, or Vespa stops responding partway** — check that Docker really has 4 CPUs and 10 GB. Every run behind the book used exactly that, so too little memory is the first thing to rule out.

**The container fails to start because a port is already allocated** — something else on your machine is using port 8080 or 19071. Stop it, or stop the other Vespa container, then rerun with `--fresh`.

## Next

The next chapter, Recommendation and Personalization, is in `chapters/ch10/` in this repository. Its own start script runs `bootstrap.sh` and then fills the user documents:

```
chapters/ch10/start.sh
```

The product catalogue and every filter from this chapter stay as they are. Chapter 8 used the caller's identity only to restrict what a request may see; the next chapter uses who is shopping as evidence for ranking.
