# Chapter 3 — Text Search Foundations

This directory is the code for Chapter 3 of *Production AI Search with Vespa*. It loads the full catalogue of 101,341 products from Amazon's ESCI shopping dataset into the application Chapter 2 built, measures a BM25 baseline against ESCI's human relevance judgements, tunes it, and counts the relevant products that lexical retrieval still cannot match.

The book explains what each step does and why. This page is the practical half: what to install, what to run, what you should see, and what to do when something goes wrong.

## What is in this directory

```
chapters/ch03/
├── app/                              the application package Vespa deploys
│   ├── services.xml                  the container and content nodes, unchanged
│   ├── schemas/
│   │   ├── product.sd                Chapter 2's schema, plus enable-bm25 and title_grams
│   │   └── product/                  one file per rank profile
│   │       ├── random.profile        random order, the floor
│   │       ├── default.profile       Chapter 2's nativeRank, unchanged
│   │       ├── bm25_title.profile
│   │       ├── bm25_all.profile
│   │       ├── bm25_weighted.profile
│   │       ├── bm25_tuned.profile    the chapter's final baseline
│   │       ├── explained.profile     returns rank features with each hit
│   │       └── bm25_k*_b*.profile    the fifteen k1 × b grid profiles
│   └── search/query-profiles/
│       └── default.xml               request defaults: hits, rank profile, timing
├── chapter.toml                      what bootstrap.sh needs for this chapter
├── compare.py                        renders the chapter's tables from the reports
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

On the reference machine, continuing from Chapter 2 took 3 minutes 30 seconds, and a fresh run with the dataset already cached took 4 minutes 37 seconds. If the dataset still needs to be downloaded, add the time described in Chapter 2; the `[corpus] shard N/15` lines mean it is working, not stuck.

A successful run ends with this state:

```
== at the start of ch03
   build      builds/esci-us-hard-book-s42-kdd-v4
   image      vespaengine/vespa:8.751.13
   documents  101341
   embedders  none declared
```

`embedders none declared` is correct: this chapter still uses only lexical retrieval.

## The commands in this chapter

Run these from the repository root, in this order, to repeat the individual steps after `bootstrap.sh` has finished. Bootstrap already deploys and feeds when needed; repeating the feed replaces documents with the same IDs. Every evaluation reads the same index, so you can run them in any order once the feed has finished.

| Purpose | Command | What you should see |
| :---- | :---- | :---- |
| Deploy the application package | `vespa deploy --wait 300 chapters/ch03/app` | `Success: Deployed 'chapters/ch03/app' with session ID …`. Safe to repeat; an unchanged package changes nothing. |
| Feed the full catalogue and display statistics | `.venv/bin/python shared/tools/feed.py builds/esci-us-hard-book-s42-kdd-v4/products.jsonl` | `101,341 ok, 0 failed, 0 retried in …` |
| Send the chapter's query | `.venv/bin/python shared/tools/query.py --query "running shoes" --hits 5` | `1,300 matched, showing 5`, then five titles, all of them running shoes. The command names no rank profile, so the query profile's default, `bm25_tuned`, is used. |
| The same, with rank features | `.venv/bin/python shared/tools/query.py --query "running shoes" --ranking explained --hits 5 --block features` | A table of each hit's per-field BM25 scores and match features. The top hit's relevance is 35.652. |
| Evaluate one rank profile on the validation split | `.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_title` | ndcg@10 0.422. With `--ranking default`: 0.299; `bm25_all`: 0.323; `bm25_weighted`: 0.400; `bm25_tuned`: 0.437. Run `random` with `--passes 1`: 0.020. |
| Change the boost weights for one request | `.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=0' --param 'input.query(w_brand)=0'` | ndcg@10 0.432: the lower `k1` on its own, with both boosts switched off. |
| Evaluate one cell of the k1 × b grid | `.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_k06_b075` | ndcg@10 0.432. The fifteen grid profiles are named `bm25_k<k1>_b<b>`, with `k1` 06, 09, 12, 15 or 20 and `b` 04, 075 or 10\. |
| Evaluate the final profile on the test split | `.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking bm25_tuned` | ndcg@10 0.443 on the 1,050 held-out queries |
| Count relevant products with no matching term | `.venv/bin/python chapters/ch03/vocabulary_mismatch.py --split test --ranking bm25_tuned` | A five-line block: 11,527 found, 6,132 missed, 1,452 with no term to match on, 647 of those graded Exact, 8.2% of all 17,659 relevant. Example query-product pairs follow in the terminal. The full report is written to `expected/vocabulary-test.json`, replacing the book's copy. |

To try the query language, send the four YQL examples from the chapter with the Vespa CLI:

```
vespa query 'yql=select id, title from product where title contains "running"' 'hits=5'
vespa query 'yql=select id, title from product where title contains "running" and brand contains "nike"' 'hits=5'
vespa query 'yql=select id, title from product where title contains phrase("running", "shoes")' 'hits=5'
vespa query 'yql=select id, title from product where userQuery() and has_description = true' 'query=running shoes' 'hits=5'
```

These are for exploring; the book does not measure them, and nothing in `expected/` corresponds to them.

When you override a boost weight, use the full form, `--param 'input.query(w_qcomplete)=3'`. A bare `--param w_qcomplete=3` is accepted without an error but does not set the input, so the rank profile keeps its default value.

## Comparing your run with the book's

`expected/` holds the output of every command the chapter quotes, exactly as it ran when the book was written, on a fresh run (`--fresh`). Two kinds of number are in there, and they behave differently:

- **Quality numbers** — ndcg@10, recall, mrr, the bootstrap intervals and the vocabulary counts. Given the same build and the same 101,341 documents, every ndcg@10 and recall figure should come back within 0.002, apart from `random`, which reorders on every run. mrr can move by up to about 0.003, because products with equal relevance scores, such as the two identical *Nike Women's Revolution 4 Running Shoe* listings, are not always returned in the same order. In the vocabulary blocks, the no-match and Exact counts come back exactly, while the found and missed counts can move by a few query-product pairs at the top-100 boundary. If your numbers differ by more than that, something about what you ran is different; start with `docs/pins.md`.  
- **Cost numbers** — feed timings, documents per second, and p50 and p95 latency. These describe one machine on one day (an Apple M4 Pro, Docker with 4 CPUs / 10 GB). Latency is measured after a discarded warm-up pass. Yours will differ, and that is expected.

In the comparison blocks, each difference is followed by its bootstrap interval and a label: **real** when the interval excludes zero, **inside the noise** when it includes zero.

To regenerate the files from your own run, use these forms; each one overwrites the file it names, and `git diff chapters/ch03/expected/` then shows the difference. First the feed, the two queries, and the evaluations on the validation split:

```
.venv/bin/python shared/tools/feed.py builds/esci-us-hard-book-s42-kdd-v4/products.jsonl --out chapters/ch03/expected/feed.json --label "ch03 full feed (re-feed onto the populated index)" > chapters/ch03/expected/feed.block.md
.venv/bin/python shared/tools/query.py --query "running shoes" --ranking bm25_tuned --hits 5 --block query    > chapters/ch03/expected/query-101341.block.md
.venv/bin/python shared/tools/query.py --query "running shoes" --ranking explained  --hits 5 --block features > chapters/ch03/expected/features-running-shoes.block.md

.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 1 --ranking random        --label validation-random        --out chapters/ch03/expected/validation-random.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking default       --label validation-default       --out chapters/ch03/expected/validation-default.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_title    --label validation-bm25_title    --out chapters/ch03/expected/validation-bm25_title.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_all      --label validation-bm25_all      --out chapters/ch03/expected/validation-bm25_all.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_weighted --label validation-bm25_weighted --out chapters/ch03/expected/validation-bm25_weighted.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=0' --param 'input.query(w_brand)=0' --label validation-bm25_tuned-k1only --out chapters/ch03/expected/validation-bm25_tuned-k1only.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned    --label validation-bm25_tuned    --out chapters/ch03/expected/validation-bm25_tuned.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_title    --label validation-bm25_title-tail --out chapters/ch03/expected/validation-bm25_title-tail.json
```

The title plus one other field at a time:

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_weighted --param 'input.query(w_title)=1' --param 'input.query(w_bullets)=0'   --param 'input.query(w_description)=0.5' --param 'input.query(w_brand)=0'    --label validation-bm25_weighted-t1-d05   --out chapters/ch03/expected/validation-bm25_weighted-t1-d05.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_weighted --param 'input.query(w_title)=1' --param 'input.query(w_bullets)=0.5' --param 'input.query(w_description)=0'   --param 'input.query(w_brand)=0'    --label validation-bm25_weighted-t1-b05   --out chapters/ch03/expected/validation-bm25_weighted-t1-b05.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_weighted --param 'input.query(w_title)=1' --param 'input.query(w_bullets)=0'   --param 'input.query(w_description)=0'   --param 'input.query(w_brand)=0.25' --label validation-bm25_weighted-t1-br025 --out chapters/ch03/expected/validation-bm25_weighted-t1-br025.json
```

The k1 × b grid and the boost sweep:

```
for k in 06 09 12 15 20; do
  for b in 04 075 10; do
    .venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 \
      --ranking bm25_k${k}_b${b} --label validation-bm25_k${k}_b${b} \
      --out chapters/ch03/expected/validation-bm25_k${k}_b${b}.json
  done
done

.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=3'  --param 'input.query(w_brand)=0' --label validation-bm25_tuned-qc3        --out chapters/ch03/expected/validation-bm25_tuned-qc3.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=5'  --param 'input.query(w_brand)=0' --label validation-bm25_tuned-qc5        --out chapters/ch03/expected/validation-bm25_tuned-qc5.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=10' --param 'input.query(w_brand)=0' --label validation-bm25_tuned-qc10       --out chapters/ch03/expected/validation-bm25_tuned-qc10.json
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=5'  --param 'input.query(w_brand)=3' --label validation-bm25_tuned-qc5-brand3  --out chapters/ch03/expected/validation-bm25_tuned-qc5-brand3.json
```

The test split, and the vocabulary counts:

```
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking bm25_title    --label test-bm25_title    --out chapters/ch03/expected/test-bm25_title.json
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 1 --ranking random        --label test-random        --out chapters/ch03/expected/test-random.json
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking default       --label test-default       --out chapters/ch03/expected/test-default.json
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking bm25_weighted --label test-bm25_weighted --out chapters/ch03/expected/test-bm25_weighted.json
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=0' --param 'input.query(w_brand)=0' --label test-bm25_tuned-k1only --out chapters/ch03/expected/test-bm25_tuned-k1only.json
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking bm25_tuned    --label test-bm25_tuned    --out chapters/ch03/expected/test-bm25_tuned.json

.venv/bin/python chapters/ch03/vocabulary_mismatch.py --split validation --ranking bm25_tuned --out chapters/ch03/expected/vocabulary-validation.json > chapters/ch03/expected/vocabulary-validation.block.md
.venv/bin/python chapters/ch03/vocabulary_mismatch.py --split test       --ranking bm25_tuned --out chapters/ch03/expected/vocabulary-test.json       > chapters/ch03/expected/vocabulary-test.block.md
```

Finally, the tables and comparison blocks the chapter prints, rendered from those reports. `--baseline` names the run every other row is compared against; the baseline itself is not a row.

```
.venv/bin/python chapters/ch03/compare.py --block evaluations chapters/ch03/expected/validation-random.json chapters/ch03/expected/validation-default.json chapters/ch03/expected/validation-bm25_title.json chapters/ch03/expected/validation-bm25_all.json chapters/ch03/expected/validation-bm25_weighted.json chapters/ch03/expected/validation-bm25_tuned-k1only.json chapters/ch03/expected/validation-bm25_tuned.json > chapters/ch03/expected/compare-validation-evaluations.block.md
.venv/bin/python chapters/ch03/compare.py --block headline --headline validation-bm25_tuned --baseline validation-random chapters/ch03/expected/validation-random.json chapters/ch03/expected/validation-bm25_tuned.json > chapters/ch03/expected/compare-validation-headline.block.md
.venv/bin/python chapters/ch03/compare.py --block comparison --baseline validation-bm25_title chapters/ch03/expected/validation-bm25_title.json chapters/ch03/expected/validation-default.json chapters/ch03/expected/validation-bm25_all.json chapters/ch03/expected/validation-bm25_weighted.json chapters/ch03/expected/validation-bm25_tuned-k1only.json chapters/ch03/expected/validation-bm25_tuned.json chapters/ch03/expected/validation-bm25_title-tail.json > chapters/ch03/expected/compare-validation-comparison.block.md
.venv/bin/python chapters/ch03/compare.py --block comparison --baseline validation-bm25_title chapters/ch03/expected/validation-bm25_title.json chapters/ch03/expected/validation-bm25_weighted-t1-br025.json chapters/ch03/expected/validation-bm25_weighted-t1-b05.json chapters/ch03/expected/validation-bm25_weighted-t1-d05.json chapters/ch03/expected/validation-bm25_weighted.json > chapters/ch03/expected/compare-validation-weights.block.md
.venv/bin/python chapters/ch03/compare.py --block grid chapters/ch03/expected/validation-bm25_k06_b04.json chapters/ch03/expected/validation-bm25_k06_b075.json chapters/ch03/expected/validation-bm25_k06_b10.json chapters/ch03/expected/validation-bm25_k09_b04.json chapters/ch03/expected/validation-bm25_k09_b075.json chapters/ch03/expected/validation-bm25_k09_b10.json chapters/ch03/expected/validation-bm25_k12_b04.json chapters/ch03/expected/validation-bm25_k12_b075.json chapters/ch03/expected/validation-bm25_k12_b10.json chapters/ch03/expected/validation-bm25_k15_b04.json chapters/ch03/expected/validation-bm25_k15_b075.json chapters/ch03/expected/validation-bm25_k15_b10.json chapters/ch03/expected/validation-bm25_k20_b04.json chapters/ch03/expected/validation-bm25_k20_b075.json chapters/ch03/expected/validation-bm25_k20_b10.json > chapters/ch03/expected/compare-validation-grid.block.md
.venv/bin/python chapters/ch03/compare.py --block comparison --baseline validation-bm25_tuned-k1only chapters/ch03/expected/validation-bm25_tuned-k1only.json chapters/ch03/expected/validation-bm25_tuned-qc3.json chapters/ch03/expected/validation-bm25_tuned-qc5.json chapters/ch03/expected/validation-bm25_tuned-qc10.json chapters/ch03/expected/validation-bm25_tuned-qc5-brand3.json chapters/ch03/expected/validation-bm25_tuned.json > chapters/ch03/expected/compare-validation-boosts.block.md
.venv/bin/python chapters/ch03/compare.py --block evaluations-latency chapters/ch03/expected/validation-default.json chapters/ch03/expected/validation-bm25_title.json chapters/ch03/expected/validation-bm25_all.json chapters/ch03/expected/validation-bm25_weighted.json chapters/ch03/expected/validation-bm25_tuned-k1only.json chapters/ch03/expected/validation-bm25_tuned.json > chapters/ch03/expected/compare-validation-latency.block.md
.venv/bin/python chapters/ch03/compare.py --block evaluations chapters/ch03/expected/test-random.json chapters/ch03/expected/test-default.json chapters/ch03/expected/test-bm25_title.json chapters/ch03/expected/test-bm25_weighted.json chapters/ch03/expected/test-bm25_tuned-k1only.json chapters/ch03/expected/test-bm25_tuned.json > chapters/ch03/expected/compare-test-evaluations.block.md
.venv/bin/python chapters/ch03/compare.py --block comparison --baseline test-bm25_title chapters/ch03/expected/test-bm25_title.json chapters/ch03/expected/test-default.json chapters/ch03/expected/test-bm25_weighted.json chapters/ch03/expected/test-bm25_tuned-k1only.json chapters/ch03/expected/test-bm25_tuned.json > chapters/ch03/expected/compare-test-comparison.block.md
.venv/bin/python chapters/ch03/compare.py --block comparison --baseline test-bm25_tuned-k1only chapters/ch03/expected/test-bm25_tuned-k1only.json chapters/ch03/expected/test-bm25_tuned.json > chapters/ch03/expected/compare-test-boost.block.md
```

## If something goes wrong

**The deploy prints a re-index warning about `title_grams`** — expected when continuing from Chapter 2\. The full feed that follows processes every product under the updated schema.

**A boost or field-weight setting seems to have no effect** — check the parameter name. It must be the full form, `--param 'input.query(w_qcomplete)=3'`. The bare form, `--param w_qcomplete=3`, is accepted without an error but leaves the rank profile on its default value, so the run looks normal.

**Your relevance values are a few hundredths lower than the book's** — you probably continued from Chapter 2\. That path indexes Chapter 2's 2,000 products twice, and BM25's collection statistics reflect what was indexed, so every relevance value comes out slightly lower: the top `running shoes` hit scores 12.530 instead of 12.585, and rank 5 can be a different product. The evaluation tables still agree with the book's to within 0.001 in ndcg@10. Rerun with `--fresh` for identical relevance values.

**A quality number differs from the book's by 0.001, or an mrr by up to 0.003** — tied results, not a fault. See *Comparing your run with the book's*.

**`running shoes` reports 1,300 matches, not every product containing either word** — expected. `userQuery()` uses weakAnd, and its reported count is not an exhaustive count of every product that contains a query term. The chapter explains why.

**The container fails to start because a port is already allocated** — something else on your machine is using port 8080 or 19071\. Stop it, or stop the other Vespa container, then rerun with `--fresh`.

**The deploy or feed fails, or Vespa stops responding partway** — check that Docker really has 4 CPUs and 10 GB. Every run behind the book used exactly that, so too little memory is the first thing to rule out.

**The first run is very slow** — if the dataset is not cached yet, it is limited by your network, not your machine. Once the dataset is cached, it does not need downloading again.

**The five-line vocabulary block appears with extra lines in your terminal** — the example query-product pairs go to a different output stream from the block, and a terminal shows both. Redirect the output to a file and you will see only the block.

## Next

When you are ready for Chapter 4:

```
./bootstrap.sh ch04
```

It keeps the catalogue this chapter fed and adds semantic retrieval.