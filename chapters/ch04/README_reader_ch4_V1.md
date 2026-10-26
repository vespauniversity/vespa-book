# Chapter 4 — Semantic Search and the Tensor Model

This directory is the code for Chapter 4 of *Production AI Search with Vespa*. It adds an embedding model to the application Chapter 3 built, stores one vector for each of the 101,341 product titles, and compares semantic retrieval with Chapter 3's tuned lexical baseline on the same judged queries. It then measures the query instruction, which relevant query–product pairs each lens finds, exact search against HNSW, the cost of vectors in feed time and memory, precomputed against in-application embeddings, and a second, larger model.

The book explains what each step does and why. This page is the practical half: what to run, in the same order as the chapter, what you should see, and what to do when something goes wrong.

## What is in this directory

```
chapters/ch04/
├── app/                              the application package Vespa deploys
│   ├── services.xml                  adds the embedder component to the container
│   ├── schemas/
│   │   ├── product.sd                Chapter 3's schema, plus title_embedding and
│   │   │                             title_embedding_precomputed
│   │   └── product/                  one file per rank profile
│   │       ├── semantic.profile      new: ranks by closeness to the query vector
│   │       └── …                     Chapter 3's profiles, unchanged
│   └── search/query-profiles/
│       └── default.xml               request defaults, unchanged: bm25_tuned is still the default
├── chapter.toml                      what bootstrap.sh needs for this chapter
├── ann_sweep.py                      exact search against HNSW at several exploration settings
├── retriever_overlap.py              which relevant pairs each lens finds in its top 100
├── reach.py                          which of those pairs the lexical lens could never match
├── model_tradeoff.py                 the optional bge-base comparison
├── models/
│   ├── README.md                     the four things to change when you swap a model
│   ├── bge-base.xml                  the larger model, used only by model_tradeoff.py
│   └── colbert.md                    late interaction, described but not deployed
├── COMMANDS.md                       every command, as run for the book
└── expected/                         the book's reference output
```

The feeder, the query tool, the evaluation tool, the comparison tool, the offline encoder and the memory tool are shared by every chapter and live in `shared/tools/`.

## What you need

The same as Chapter 3, plus the embedding model's weights.

|  | Version used for the book | Notes |
| :---- | :---- | :---- |
| Docker | — | Give it **4 CPUs and 10 GB of memory**. Docker Desktop or Rancher Desktop both work. |
| Python | 3.11 (3.11.13) | Only needed to create the virtual environment. This chapter also installs `onnxruntime` and `tokenizers` into it, for the offline encoder. |
| Vespa CLI | 8.562.17 | macOS: `brew install vespa-cli`. Linux and Windows: the Vespa GitHub releases page. |
| Embedding model | `BAAI/bge-small-en-v1.5`, commit `5c38ec7c` | Downloaded by the container from Hugging Face when the application is deployed, and by the offline encoder into `shared/cache/models/`. |
| Network | — | Access to Hugging Face, for the model weights, and for the dataset if it is not already cached. |

Every pinned version is listed in `docs/pins.md` at the repository root.

## Run it

From the repository root:

```
./bootstrap.sh ch04
```

If you are continuing from Chapter 3, this deploys this chapter's application package to the running container. If you are starting with this chapter, add `--fresh`: it removes any earlier virtual environment and Vespa container and builds everything from the beginning.

When you continue from Chapter 3, the deployment prints this warning:

```
WARNING Change(s) between active and new application that may require re-index:
reindexing: Consider re-indexing document type 'product' in cluster 'content' because:
    1) Document type 'product': Non-document field 'title_embedding' added; this may be populated by reindexing
```

That is expected. None of the products already in the index has a vector yet. The script checks by sending one vector query; when nothing comes back, it feeds all 101,341 products again, and the embedder computes each title's vector as the product is written. You do not need to reindex separately.

On the reference machine (Apple M4 Pro, container VM with 4 CPUs and 10 GB), continuing from Chapter 3 took 8 minutes 30 seconds, of which the feed took 481.8 seconds at 210 documents per second. A fresh run with the dataset already cached took 9 minutes 13 seconds; a first run that also had to download the dataset took 22 minutes 19 seconds. Running `./bootstrap.sh ch04` again afterwards takes a few seconds, because the vector check now finds vectors and nothing is fed. Your timings will differ.

A successful run ends with this state:

```
== at the start of ch04
   build      builds/esci-us-hard-book-s42-kdd-v4
   image      vespaengine/vespa:8.751.13
   documents  101341
   embedders  embedder=BAAI/bge-small-en-v1.5@5c38ec7c
```

The last line is new: for the first time, the application declares an embedding model.

## The commands in this chapter

The steps below follow the chapter, section by section. Run them from the repository root after `bootstrap.sh` has finished.

Most commands save their result in `expected/`, replacing the book's copy of that file, so that `git diff chapters/ch04/expected/` shows how your run compares with the book's. To put the book's files back, run `git checkout chapters/ch04/expected/`.

### Adding an embedder to the application

Bootstrap has already done this. The embedder component is declared in `app/services.xml`, and the feed that computed every vector is the one described under *Run it*.

### Embeddings: from words to meaning

Nothing to run. The settings this section describes are in `app/services.xml`: the model's pinned URLs, `pooling-strategy` and `normalize`. The recommended BGE retrieval instruction, which the evaluation tool adds in front of every semantic query, is defined once, as `QUERY_PREFIX` in `shared/tools/evaluate.py`.

### Tensors: how Vespa stores a vector

Nothing to run. The `title_embedding` field, its distance metric and its HNSW settings are in `app/schemas/product.sd`; the `semantic` rank profile is in `app/schemas/product/semantic.profile`.

### The semantic lens against the lexical baseline

Send one semantic query:

```
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever semantic --ranking semantic --hits 5
```

**What you should see:** five products, ranked by closeness to the query vector. `--retriever semantic` makes the tool send a `nearestNeighbor` query, with the query text embedded by the same model and with the BGE instruction in front of it. Try other queries from the chapter, such as `"talkbox keyboard"`. The book does not keep reference output for single queries, so there is nothing in `expected/` to compare against.

Then evaluate both lenses on the same judged queries. The options are the same as in Chapter 3; `--retriever semantic` is the only new one here:

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --label validation-bm25_tuned --out chapters/ch04/expected/validation-bm25_tuned.json > chapters/ch04/expected/validation-bm25_tuned.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --retriever semantic --ranking semantic --label validation-semantic --out chapters/ch04/expected/validation-semantic.json > chapters/ch04/expected/validation-semantic.block.md
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking bm25_tuned --label test-bm25_tuned --out chapters/ch04/expected/test-bm25_tuned.json > chapters/ch04/expected/test-bm25_tuned.block.md
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --retriever semantic --ranking semantic --label test-semantic --out chapters/ch04/expected/test-semantic.json > chapters/ch04/expected/test-semantic.block.md
```

**What you should see:** ndcg@10 0.437 for `bm25_tuned` and 0.451 for `semantic` on validation; 0.443 and 0.454 on test.

The tables in this section are built from those four reports by `shared/tools/compare.py`. It reads the saved reports and queries nothing; `--block` chooses the table, and `--baseline` names the run the others are compared against:

```
.venv/bin/python shared/tools/compare.py chapters/ch04/expected/validation-bm25_tuned.json chapters/ch04/expected/validation-semantic.json --baseline validation-bm25_tuned --block evaluations > chapters/ch04/expected/compare-validation-evaluations.block.md
.venv/bin/python shared/tools/compare.py chapters/ch04/expected/validation-bm25_tuned.json chapters/ch04/expected/validation-semantic.json --baseline validation-bm25_tuned --block comparison > chapters/ch04/expected/compare-validation-comparison.block.md
.venv/bin/python shared/tools/compare.py chapters/ch04/expected/validation-bm25_tuned.json chapters/ch04/expected/validation-semantic.json --baseline validation-bm25_tuned --block headline --headline validation-semantic > chapters/ch04/expected/compare-validation-headline.block.md
.venv/bin/python shared/tools/compare.py chapters/ch04/expected/test-bm25_tuned.json chapters/ch04/expected/test-semantic.json --baseline test-bm25_tuned --block evaluations > chapters/ch04/expected/compare-test-evaluations.block.md
.venv/bin/python shared/tools/compare.py chapters/ch04/expected/test-bm25_tuned.json chapters/ch04/expected/test-semantic.json --baseline test-bm25_tuned --block comparison > chapters/ch04/expected/compare-test-comparison.block.md
```

**What you should see:** against `bm25_tuned`, `semantic` changes ndcg@10 by \+0.014 \[−0.002, \+0.030\] on validation and \+0.010 \[−0.005, \+0.025\] on test. Both intervals include zero, and the tool labels them **inside the noise**. recall@100 changes by \+0.053 \[+0.037, \+0.069\] and \+0.041 \[+0.027, \+0.055\]; both intervals exclude zero, and the tool labels them **real**.

The latency table, *What a semantic query costs*, comes from the same validation reports:

```
.venv/bin/python shared/tools/compare.py chapters/ch04/expected/validation-bm25_tuned.json chapters/ch04/expected/validation-semantic.json --baseline validation-bm25_tuned --block evaluations-latency > chapters/ch04/expected/compare-validation-latency.block.md
```

**What you should see:** p50 4.4 ms for `bm25_tuned` and 12.9 ms for `semantic` on the reference machine. Yours will differ.

### Getting the query side right

The same deployed vectors, queried three ways: with the recommended BGE retrieval prefix (the tool's default), with no prefix, and with `query:` , the prefix the e5 model family expects:

```
.venv/bin/python shared/tools/evaluate.py --split validation --retriever semantic --ranking semantic --hits 100 --passes 3 --label prefix-correct --out chapters/ch04/expected/validation-prefix-correct.json > chapters/ch04/expected/validation-prefix-correct.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever semantic --ranking semantic --hits 100 --passes 3 --label prefix-none --query-prefix "" --out chapters/ch04/expected/validation-prefix-none.json > chapters/ch04/expected/validation-prefix-none.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever semantic --ranking semantic --hits 100 --passes 3 --label prefix-wrong --query-prefix "query: " --out chapters/ch04/expected/validation-prefix-wrong.json > chapters/ch04/expected/validation-prefix-wrong.block.md
.venv/bin/python shared/tools/compare.py chapters/ch04/expected/validation-prefix-correct.json chapters/ch04/expected/validation-prefix-none.json chapters/ch04/expected/validation-prefix-wrong.json --baseline prefix-correct --block prefixes > chapters/ch04/expected/compare-validation-prefixes.block.md
```

`--query-prefix` replaces the text placed in front of each query before it is embedded. Without it, the tool uses the recommended BGE prefix.

**What you should see:** ndcg@10 0.451 with the recommended prefix, 0.433 with no prefix, and 0.416 with the other model's prefix. All three runs succeed and return full result lists; only the scores show the difference.

### What the semantic lens reaches

Which relevant query–product pairs each lens places in its top 100, then, of the pairs only the semantic lens found, which ones fail the configured lexical probe. Validation first, then test:

```
.venv/bin/python chapters/ch04/retriever_overlap.py --split validation --out chapters/ch04/expected/validation-overlap.json > chapters/ch04/expected/validation-overlap.block.md
.venv/bin/python chapters/ch04/reach.py --split validation --against chapters/ch04/expected/validation-overlap.json --out chapters/ch04/expected/validation-reach.json > chapters/ch04/expected/validation-reach.block.md
.venv/bin/python chapters/ch04/reach.py --split validation --from chapters/ch04/expected/validation-reach.json --block reach-depths > chapters/ch04/expected/validation-reach-depths.block.md

.venv/bin/python chapters/ch04/retriever_overlap.py --split test --out chapters/ch04/expected/test-overlap.json > chapters/ch04/expected/test-overlap.block.md
.venv/bin/python chapters/ch04/reach.py --split test --against chapters/ch04/expected/test-overlap.json --out chapters/ch04/expected/test-reach.json > chapters/ch04/expected/test-reach.block.md
.venv/bin/python chapters/ch04/reach.py --split test --from chapters/ch04/expected/test-reach.json --block reach-depths > chapters/ch04/expected/test-reach-depths.block.md
```

`reach.py --against` reads the overlap report the line above wrote; `reach.py --from` prints a second table from the reach report without measuring anything again. The tools say *keyword* and *vector* where the chapter says *lexical lens* and *semantic lens*.

**What you should see** (test): of 17,659 relevant query–product pairs, 10,216 found by both, 1,313 only by keyword, 2,153 only by vector, 3,977 by neither. Of the 2,153, 210 have no word in common with the query and 1,943 matched but ranked past 100\. In the depth table, 1,452 pairs fail the lexical probe, 647 of them graded Exact, and the semantic lens reaches 210 of them in its top 100, 284 in its top 200 and 383 in its top 400\. On validation the same tables read 7,242 / 916 / 1,613 / 2,980, then 192 / 1,421, then a blind spot of 1,128 pairs (560 Exact) reached at 192 / 254 / 334\. Example pairs, such as the bandsaw and tan extender queries the chapter quotes, are saved in the `examples` fields of the JSON reports.

### Exact search and HNSW

Every validation query, run under exact search and under HNSW with four exploration settings. The first command measures and writes the report and the quality table; the second prints the latency table from the same report:

```
.venv/bin/python chapters/ch04/ann_sweep.py --split validation --out chapters/ch04/expected/validation-ann-sweep.json > chapters/ch04/expected/validation-ann-sweep.block.md
.venv/bin/python chapters/ch04/ann_sweep.py --split validation --from chapters/ch04/expected/validation-ann-sweep.json --block ann-sweep-latency > chapters/ch04/expected/validation-ann-sweep-latency.block.md
```

The tool's *agreement@10* and *agreement@100* columns are what the chapter calls **neighbor recall**: the share of exact search's top 10 or top 100 that HNSW also returned. They say nothing about relevance; ndcg@10 is the relevance column. The `HNSW, default` setting is run first and last, as a check that the index did not change during the sweep.

**What you should see:** neighbor recall@100 of 1.000 for exact search, 0.911 for HNSW's default, rising to 0.990 with 500 additional candidates explored. ndcg@10 stays between 0.451 and 0.454 for every setting. On the reference machine, p50 was 14.9 ms for exact search and 12.6 ms for HNSW's default.

**Memory and feed cost.** A documented re-feed of the whole catalogue, with the embedder computing every vector:

```
.venv/bin/python shared/tools/feed.py builds/esci-us-hard-book-s42-kdd-v4/products.jsonl --label "ch04 full feed with the in-app embedder (re-feed onto the populated index)" --out chapters/ch04/expected/feed.json > chapters/ch04/expected/feed.block.md
```

**What you should see:** `101,341 ok, 0 failed, 0 retried`. The book's run took 7 minutes 41 seconds at 220 documents per second.

The memory reading takes **at least twenty minutes, and up to thirty**. It waits ten minutes before each reading and accepts the result only when two readings in a row agree within 1%:

```
.venv/bin/python shared/tools/memory.py --settle 600 --rounds 3 --tolerance 0.01 --dimensions 384 --label "one vector per title (bge-small)" --out chapters/ch04/expected/memory.json > chapters/ch04/expected/memory.block.md
```

**What you should see:** the vectors, calculated, 156 MB; the whole index, measured, about 1,605 MB on the reference machine. Check that the report says `settled: true`; if it says `false`, the readings never agreed and the number should not be used.

### Precomputed embeddings and in-application embeddings

Encode every title outside Vespa with the same pinned model, check one title against the vector Vespa computed, feed the precomputed vectors as partial updates, and take a second memory reading:

```
.venv/bin/python shared/tools/embed_offline.py --out chapters/ch04/expected/encode.json > chapters/ch04/expected/encode.block.md
.venv/bin/python shared/tools/embed_offline.py --check "MARSVOVO Women's Sports Non Slip Running Shoes Work Shoes Fashion Sneakers Air Knitted Ultra Lightweight Breathable Athletic Gym Walking Running Shoes Black Size 8" --out chapters/ch04/expected/encode-check.json > chapters/ch04/expected/encode-check.block.md
.venv/bin/python shared/tools/feed.py builds/esci-us-hard-book-s42-kdd-v4/products_precomputed_bge.jsonl --label "precomputed vectors, partial update of title_embedding_precomputed" --out chapters/ch04/expected/feed-precomputed.json > chapters/ch04/expected/feed-precomputed.block.md
.venv/bin/python shared/tools/memory.py --settle 600 --rounds 3 --tolerance 0.01 --dimensions 384 --vectors 2 --against chapters/ch04/expected/memory.json --label "with the precomputed field filled" --against-label "one vector field" --delta-label "the second vector field" --out chapters/ch04/expected/memory-precomputed.json > chapters/ch04/expected/memory-precomputed.block.md
```

The first command also writes `builds/esci-us-hard-book-s42-kdd-v4/products_precomputed_bge.jsonl`, one partial update per product, which the third command feeds. The title in the second command is the top `running shoes` result from Chapter 3, in full.

**What you should see:** 101,341 titles encoded in about 276 seconds on the reference machine; a maximum absolute difference of 0.000000 and a cosine of 1.000000 for the checked title; the precomputed feed at about 420 documents per second; and a second memory reading about 174 MB above the first.

### Choosing a model

This comparison is optional. The book ran it once, and it takes about an hour. It deploys a temporary copy of the application with `BAAI/bge-base-en-v1.5`, a 768-dimensional model, in place of bge-small; the shipped `app/` is never changed.

Before you start: the base feed and the restore feed below are full feeds, and a full feed leaves `title_embedding_precomputed` empty on every product it writes. If you have already run the precomputed step above, run its feed command again when you finish here.

```
.venv/bin/python chapters/ch04/model_tradeoff.py --deploy-base
.venv/bin/python shared/tools/feed.py builds/esci-us-hard-book-s42-kdd-v4/products.jsonl --label "bge-base full feed (comparison, measured once)" --out chapters/ch04/expected/feed-base.json > chapters/ch04/expected/feed-base.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --retriever semantic --ranking semantic_base --vector-field title_embedding_base --embedder embedder_base --query-tensor qb --label validation-semantic-base --out chapters/ch04/expected/validation-semantic-base.json > chapters/ch04/expected/validation-semantic-base.block.md
.venv/bin/python shared/tools/memory.py --settle 600 --rounds 3 --tolerance 0.01 --dimensions 768 --label "bge-base, one vector per title" --out chapters/ch04/expected/memory-base.json > chapters/ch04/expected/memory-base.block.md
```

`--vector-field`, `--embedder` and `--query-tensor` tell the evaluation tool to query the larger model's field, component and query input instead of the shipped ones.

Then put the shipped application back, refill its vectors, and confirm the container is back on bge-small:

```
.venv/bin/python chapters/ch04/model_tradeoff.py --restore
.venv/bin/python shared/tools/feed.py builds/esci-us-hard-book-s42-kdd-v4/products.jsonl --label "small re-feed after the bge-base comparison" --out chapters/ch04/review/refeed-small.json > chapters/ch04/review/refeed-small.block.md
.venv/bin/python shared/tools/deployed.py
```

`deployed.py` should name `BAAI/bge-small-en-v1.5`. The restore deploy prints the same `title_embedding` warning as the first one; the re-feed after it fills the field again.

Finally, the two tables in the chapter. The first needs `expected/memory.json` from *Exact search and HNSW*:

```
.venv/bin/python chapters/ch04/model_tradeoff.py --block model-tradeoff --baseline chapters/ch04/expected/validation-bm25_tuned.json --small-eval chapters/ch04/expected/validation-semantic.json --small-feed chapters/ch04/expected/feed.json --small-memory chapters/ch04/expected/memory.json --base-eval chapters/ch04/expected/validation-semantic-base.json --base-feed chapters/ch04/expected/feed-base.json --base-memory chapters/ch04/expected/memory-base.json > chapters/ch04/expected/model-tradeoff.block.md
.venv/bin/python shared/tools/compare.py chapters/ch04/expected/validation-semantic.json chapters/ch04/expected/validation-semantic-base.json --baseline validation-semantic --block comparison > chapters/ch04/expected/compare-validation-base-vs-small.block.md
```

**What you should see:** ndcg@10 0.467 for bge-base against 0.451 for bge-small; against bge-small directly, \+0.016 \[+0.004, \+0.027\]. On the reference machine, the bge-base feed took 25 minutes 11 seconds, its p50 was 33.1 ms, and its settled memory was about 1,739 MB.

`models/README.md` lists the four things that have to change together if you swap in a model of your own.

### Beyond a single vector

Nothing to run. `models/colbert.md` shows the component, the field and the rank profile that would add a late-interaction model. This chapter does not deploy it, and nothing in `expected/` was measured with it. Chapter 6 does.

## Comparing your run with the book's

`expected/` holds the output of every command above, exactly as it ran when the book was written. Three kinds of number are in there, and they behave differently:

- **Lexical quality numbers** — `bm25_tuned`'s ndcg@10, recall and mrr. These should come back within 0.001. `bm25_tuned`'s ndcg@10 matches Chapter 3's; its recall@10 and mrr can differ from Chapter 3's printed values in the third decimal.  
- **Semantic quality numbers** — every figure from a `semantic` run, the ANN sweep, the overlap and reach counts. HNSW builds a slightly different graph each time vectors are fed, so these can move by a few thousandths, and the counts by up to about fifteen pairs. The direction of every comparison, and whether its interval includes zero, should not change.  
- **Cost numbers** — feed timings, documents per second, p50 and p95 latency, and memory. These describe one machine on one day (an Apple M4 Pro, Docker with 4 CPUs / 10 GB). Latency is measured after a discarded warm-up pass. Yours will differ, and that is expected.

The bge-base numbers come from the optional comparison and are reproduced only if you run it.

After a run, `git diff chapters/ch04/expected/` shows every difference.

## If something goes wrong

**The deploy prints a re-index warning about `title_embedding`** — expected when continuing from Chapter 3, and again after `model_tradeoff.py --restore`. The feed that follows fills the field.

**Semantic queries return no hits** — the vectors have not been computed yet. Run `./bootstrap.sh ch04`: if no product has a vector, it feeds the catalogue again.

**`HTTP 429` from Hugging Face** — rate limiting, not a broken build. Run the same command again; it starts the dataset download from the first file.

**Semantic scores are lower than the book's, with no error** — check the query prefix. A missing or different prefix produces full, plausible-looking results with lower scores. `evaluate.py` and `query.py` use `QUERY_PREFIX` from `shared/tools/evaluate.py` unless `--query-prefix` is given.

**A document fetched through `/document/v1/` has no `title_embedding`** — the default field set returns only the fields inside `document { ... }`. Add `?fieldSet=%5Ball%5D` (`[all]`) to the request to see `title_embedding` and `title_grams` as well.

**`title_embedding_precomputed` is empty again** — a full feed was run after the precomputed feed. Run the precomputed feed command again.

**The memory report says `settled: false`** — three readings ten minutes apart never agreed. Do not use that number; run the command again when nothing else is feeding or querying the container.

**Changing `max-links-per-node` or `neighbors-to-explore-at-insert` seems to have no effect** — both are build settings. They need a content-node restart, and a changed `neighbors-to-explore-at-insert` applies only to vectors inserted afterwards. The chapter does not vary either.

**Results look wrong after the optional model comparison** — the container may still be on bge-base. Run `.venv/bin/python shared/tools/deployed.py`; if it does not name `BAAI/bge-small-en-v1.5`, run `model_tradeoff.py --restore` and the small re-feed.

**The deploy or feed fails, or Vespa stops responding partway** — check that Docker really has 4 CPUs and 10 GB. Every run behind the book used exactly that, so too little memory is the first thing to rule out.

**The container fails to start because a port is already allocated** — something else on your machine is using port 8080 or 19071\. Stop it, or stop the other Vespa container, then rerun with `--fresh`.

## Next

When you are ready for Chapter 5:

```
./bootstrap.sh ch05
```

It keeps the catalogue and its vectors and combines the lexical and semantic lenses in one search.