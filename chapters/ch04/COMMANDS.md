# ch04 COMMANDS

One line per command exactly as run, one line per file it wrote.

```
./bootstrap.sh ch04
```
wrote nothing (state check only; its `4/5 application` stage redeployed unconditionally, no reindex warning — no schema change since ch04's own app was already deployed; its `5/5 documents` stage said `title_embedding present` as required)

```
.venv/bin/python shared/tools/feed.py builds/esci-us-hard-book-s42-kdd-v4/products.jsonl --label "ch04 full feed with the in-app embedder (re-feed onto the populated index)" --out chapters/ch04/expected/feed.json > chapters/ch04/expected/feed.block.md
```
wrote `chapters/ch04/expected/feed.json`, `chapters/ch04/expected/feed.block.md` (101,341 ok, 0 failed, 0 retried, 461.4s, 220 docs/s; field check: build/deployed_embedders/host present)

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --label validation-bm25_tuned --out chapters/ch04/expected/validation-bm25_tuned.json > chapters/ch04/expected/validation-bm25_tuned.block.md
```
wrote `chapters/ch04/expected/validation-bm25_tuned.json`, `chapters/ch04/expected/validation-bm25_tuned.block.md` (ndcg@10 0.437, recall@10 0.298, recall@100 0.625, mrr 0.745; field check passed)

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --retriever semantic --ranking semantic --label validation-semantic --out chapters/ch04/expected/validation-semantic.json > chapters/ch04/expected/validation-semantic.block.md
```
wrote `chapters/ch04/expected/validation-semantic.json`, `chapters/ch04/expected/validation-semantic.block.md` (ndcg@10 0.451, recall@10 0.308, recall@100 0.678, mrr 0.746; field check passed)

```
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking bm25_tuned --label test-bm25_tuned --out chapters/ch04/expected/test-bm25_tuned.json > chapters/ch04/expected/test-bm25_tuned.block.md
```
wrote `chapters/ch04/expected/test-bm25_tuned.json`, `chapters/ch04/expected/test-bm25_tuned.block.md` (ndcg@10 0.443, recall@10 0.314, recall@100 0.644, mrr 0.755; field check passed)

```
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --retriever semantic --ranking semantic --label test-semantic --out chapters/ch04/expected/test-semantic.json > chapters/ch04/expected/test-semantic.block.md
```
wrote `chapters/ch04/expected/test-semantic.json`, `chapters/ch04/expected/test-semantic.block.md` (ndcg@10 0.454, recall@10 0.318, recall@100 0.686, mrr 0.747; field check passed)

```
.venv/bin/python shared/tools/compare.py chapters/ch04/expected/validation-bm25_tuned.json chapters/ch04/expected/validation-semantic.json --baseline validation-bm25_tuned --block evaluations > chapters/ch04/expected/compare-validation-evaluations.block.md
```
wrote `chapters/ch04/expected/compare-validation-evaluations.block.md`

```
.venv/bin/python shared/tools/compare.py chapters/ch04/expected/validation-bm25_tuned.json chapters/ch04/expected/validation-semantic.json --baseline validation-bm25_tuned --block evaluations-latency > chapters/ch04/expected/compare-validation-latency.block.md
```
wrote `chapters/ch04/expected/compare-validation-latency.block.md`

```
.venv/bin/python shared/tools/compare.py chapters/ch04/expected/validation-bm25_tuned.json chapters/ch04/expected/validation-semantic.json --baseline validation-bm25_tuned --block comparison > chapters/ch04/expected/compare-validation-comparison.block.md
```
wrote `chapters/ch04/expected/compare-validation-comparison.block.md` (ndcg@10 +0.014 [-0.002, +0.030] inside the noise; recall@100 +0.053 [+0.037, +0.069] real)

```
.venv/bin/python shared/tools/compare.py chapters/ch04/expected/validation-bm25_tuned.json chapters/ch04/expected/validation-semantic.json --baseline validation-bm25_tuned --block headline --headline validation-semantic > chapters/ch04/expected/compare-validation-headline.block.md
```
wrote `chapters/ch04/expected/compare-validation-headline.block.md`

```
.venv/bin/python shared/tools/compare.py chapters/ch04/expected/test-bm25_tuned.json chapters/ch04/expected/test-semantic.json --baseline test-bm25_tuned --block evaluations > chapters/ch04/expected/compare-test-evaluations.block.md
```
wrote `chapters/ch04/expected/compare-test-evaluations.block.md`

```
.venv/bin/python shared/tools/compare.py chapters/ch04/expected/test-bm25_tuned.json chapters/ch04/expected/test-semantic.json --baseline test-bm25_tuned --block comparison > chapters/ch04/expected/compare-test-comparison.block.md
```
wrote `chapters/ch04/expected/compare-test-comparison.block.md` (ndcg@10 +0.010 [-0.005, +0.025] inside the noise; recall@100 +0.041 [+0.027, +0.055] real)

```
.venv/bin/python chapters/ch04/retriever_overlap.py --split validation --out chapters/ch04/expected/validation-overlap.json > chapters/ch04/expected/validation-overlap.block.md
```
wrote `chapters/ch04/expected/validation-overlap.json`, `chapters/ch04/expected/validation-overlap.block.md` (relevant 12,751; both 56.8%; keyword only 7.2%; vector only 12.6%; neither 23.4%; field check passed)

```
.venv/bin/python chapters/ch04/retriever_overlap.py --split test --out chapters/ch04/expected/test-overlap.json > chapters/ch04/expected/test-overlap.block.md
```
wrote `chapters/ch04/expected/test-overlap.json`, `chapters/ch04/expected/test-overlap.block.md` (relevant 17,659; both 57.9%; keyword only 7.4%; vector only 12.2%; neither 22.5%; field check passed)

```
.venv/bin/python chapters/ch04/reach.py --split validation --against chapters/ch04/expected/validation-overlap.json --out chapters/ch04/expected/validation-reach.json > chapters/ch04/expected/validation-reach.block.md
```
wrote `chapters/ch04/expected/validation-reach.json`, `chapters/ch04/expected/validation-reach.block.md` (of 1,613 vector-only: 192 (11.9%) no word in common, 1,421 (88.1%) matched but ranked past 100; field check passed)

```
.venv/bin/python chapters/ch04/reach.py --split test --against chapters/ch04/expected/test-overlap.json --out chapters/ch04/expected/test-reach.json > chapters/ch04/expected/test-reach.block.md
```
wrote `chapters/ch04/expected/test-reach.json`, `chapters/ch04/expected/test-reach.block.md` (of 2,153 vector-only: 210 (9.8%) no word in common, 1,943 (90.2%) matched but ranked past 100; field check passed)

```
.venv/bin/python shared/tools/evaluate.py --split validation --retriever semantic --ranking semantic --hits 100 --passes 3 --label prefix-correct --out chapters/ch04/expected/validation-prefix-correct.json > chapters/ch04/expected/validation-prefix-correct.block.md
```
wrote `chapters/ch04/expected/validation-prefix-correct.json`, `chapters/ch04/expected/validation-prefix-correct.block.md` (no `--query-prefix` flag; tool's own default sent: `query_prefix` = "Represent this sentence for searching relevant passages: "; ndcg@10 0.451; field check passed)

```
.venv/bin/python shared/tools/evaluate.py --split validation --retriever semantic --ranking semantic --hits 100 --passes 3 --label prefix-none --query-prefix "" --out chapters/ch04/expected/validation-prefix-none.json > chapters/ch04/expected/validation-prefix-none.block.md
```
wrote `chapters/ch04/expected/validation-prefix-none.json`, `chapters/ch04/expected/validation-prefix-none.block.md` (`query_prefix` recorded as "" — sent verbatim; ndcg@10 0.433; field check passed)

```
.venv/bin/python shared/tools/evaluate.py --split validation --retriever semantic --ranking semantic --hits 100 --passes 3 --label prefix-wrong --query-prefix "query: " --out chapters/ch04/expected/validation-prefix-wrong.json > chapters/ch04/expected/validation-prefix-wrong.block.md
```
wrote `chapters/ch04/expected/validation-prefix-wrong.json`, `chapters/ch04/expected/validation-prefix-wrong.block.md` (`query_prefix` recorded as "query: " — sent verbatim; ndcg@10 0.416; field check passed)

```
.venv/bin/python shared/tools/compare.py chapters/ch04/expected/validation-prefix-correct.json chapters/ch04/expected/validation-prefix-none.json chapters/ch04/expected/validation-prefix-wrong.json --baseline prefix-correct --block prefixes > chapters/ch04/expected/compare-validation-prefixes.block.md
```
wrote `chapters/ch04/expected/compare-validation-prefixes.block.md` (no prefix: ndcg@10 -0.017 [-0.025, -0.010] real; wrong prefix: ndcg@10 -0.035 [-0.045, -0.025] real)

```
.venv/bin/python chapters/ch04/ann_sweep.py --split validation --out chapters/ch04/expected/validation-ann-sweep.json > chapters/ch04/expected/validation-ann-sweep.block.md
```
wrote `chapters/ch04/expected/validation-ann-sweep.json`, `chapters/ch04/expected/validation-ann-sweep.block.md` (exact agree@10/100 1.000/1.000 ndcg@10 0.454; HNSW default 0.979/0.911 ndcg@10 0.451, run first and last, both agree p50 12.6ms; +20 explored 0.982/0.928; +100 explored 0.991/0.961; +500 explored 0.997/0.990; field check passed)

```
.venv/bin/python chapters/ch04/ann_sweep.py --split validation --from chapters/ch04/expected/validation-ann-sweep.json --block ann-sweep-latency > chapters/ch04/expected/validation-ann-sweep-latency.block.md
```
wrote `chapters/ch04/expected/validation-ann-sweep-latency.block.md`

```
.venv/bin/python chapters/ch04/model_tradeoff.py --deploy-base
```
wrote nothing to `expected/` (deploys a scratch copy of `app/` with bge-base swapped in, session ID 4; the deploy warns of the new field `title_embedding_base`, as expected)

```
.venv/bin/python shared/tools/feed.py builds/esci-us-hard-book-s42-kdd-v4/products.jsonl --label "bge-base full feed (comparison, measured once)" --out chapters/ch04/expected/feed-base.json > chapters/ch04/expected/feed-base.block.md
```
wrote `chapters/ch04/expected/feed-base.json`, `chapters/ch04/expected/feed-base.block.md` (101,341 ok, 0 failed, 0 retried, 1511.1s, 67 docs/s; first progress line 85 docs/s, above the 40 docs/s floor; field check passed)

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --retriever semantic --ranking semantic_base --vector-field title_embedding_base --embedder embedder_base --query-tensor qb --label validation-semantic-base --out chapters/ch04/expected/validation-semantic-base.json > chapters/ch04/expected/validation-semantic-base.block.md
```
wrote `chapters/ch04/expected/validation-semantic-base.json`, `chapters/ch04/expected/validation-semantic-base.block.md` (ndcg@10 0.467, recall@10 0.321, recall@100 0.706, mrr 0.750, p50 33.1ms; field check passed)

```
.venv/bin/python shared/tools/memory.py --settle 600 --rounds 3 --tolerance 0.01 --dimensions 768 --label "bge-base, one vector per title" --out chapters/ch04/expected/memory-base.json > chapters/ch04/expected/memory-base.block.md
```
wrote `chapters/ch04/expected/memory-base.json`, `chapters/ch04/expected/memory-base.block.md` (settled true after two readings 600s apart; index memory 1,470 MB, vectors by hand 311 MB, everything else 1,158 MB; field check passed)


```
.venv/bin/python chapters/ch04/model_tradeoff.py --restore
```
wrote nothing to `expected/` (deploys `app/` as shipped, session ID 5; the deploy warns that `title_embedding` is empty again — the redeploy does not reindex the documents already in the index — so a small re-feed is required next)

```
.venv/bin/python shared/tools/feed.py builds/esci-us-hard-book-s42-kdd-v4/products.jsonl --label "small re-feed after the bge-base comparison" --out chapters/ch04/review/refeed-small.json > chapters/ch04/review/refeed-small.block.md
```
wrote `chapters/ch04/review/refeed-small.json`, `chapters/ch04/review/refeed-small.block.md` (101,341 ok, 0 failed, 0 retried, 477.7s, 212 docs/s; not an `expected/` report: it measures nothing the chapter reports)

Confirm after restore + re-feed:
```
.venv/bin/python shared/tools/deployed.py
```
→ `embedder=BAAI/bge-small-en-v1.5@5c38ec7c`

```
curl -fs -G 'http://localhost:8080/search/' --data-urlencode 'yql=select id from product where {targetHits:1}nearestNeighbor(title_embedding, q)' --data-urlencode 'ranking.profile=semantic' --data-urlencode 'input.query(q)=embed(embedder, "probe")' --data-urlencode 'hits=0'
```
→ `totalCount: 1` (> 0: a semantic query finds documents, so `title_embedding` is populated again)

```
.venv/bin/python shared/tools/memory.py --settle 600 --rounds 3 --tolerance 0.01 --dimensions 384 --label "one vector per title (bge-small)" --out chapters/ch04/expected/memory.json > chapters/ch04/expected/memory.block.md
```
wrote `chapters/ch04/expected/memory.json`, `chapters/ch04/expected/memory.block.md` (settled true after two readings 600s apart; index memory 1,194 MB, vectors by hand 156 MB, everything else 1,038 MB; field check passed)


> 2026-09-16: the `embed_offline.py --out` command below was run twice. The first run wrote the JSONL that the precomputed feed below loaded, and a report without `deployed_embedders`; the tool then gained the deployed stamp and the command was re-run so the committed report carries it — the JSONL was regenerated by the same deterministic model on the same machine (a sample title's vector equals the in-application one exactly, the `--check` command below), but the file the precomputed feed loaded was not byte-compared against it.

```
.venv/bin/python shared/tools/embed_offline.py --out chapters/ch04/expected/encode.json > chapters/ch04/expected/encode.block.md
```
wrote `chapters/ch04/expected/encode.json`, `chapters/ch04/expected/encode.block.md`, `builds/esci-us-hard-book-s42-kdd-v4/products_precomputed_bge.jsonl` (101,341 partial updates, 416 MB; 275.9 s, 367 docs/s on the host CPU)

The title for the equality check is the first hit of `running shoes` under `bm25_tuned` (`.venv/bin/python shared/tools/query.py --query "running shoes" --ranking bm25_tuned --hits 1`, full title read from the search API), so it is a title the reader can find the same way:
```
.venv/bin/python shared/tools/embed_offline.py --check "MARSVOVO Women's Sports Non Slip Running Shoes Work Shoes Fashion Sneakers Air Knitted Ultra Lightweight Breathable Athletic Gym Walking Running Shoes Black Size 8" --out chapters/ch04/expected/encode-check.json > chapters/ch04/expected/encode-check.block.md
```
wrote `chapters/ch04/expected/encode-check.json`, `chapters/ch04/expected/encode-check.block.md` (max absolute difference 0.000000, cosine 1.000000 against the document API's `title_embedding` for `us_B07L2V81VS`)

```
.venv/bin/python shared/tools/feed.py builds/esci-us-hard-book-s42-kdd-v4/products_precomputed_bge.jsonl --label "precomputed vectors, partial update of title_embedding_precomputed" --out chapters/ch04/expected/feed-precomputed.json > chapters/ch04/expected/feed-precomputed.block.md
```
wrote `chapters/ch04/expected/feed-precomputed.json`, `chapters/ch04/expected/feed-precomputed.block.md` (101,341 ok, 0 failed, 0 retried, 241.1 s, 420 docs/s)

```
.venv/bin/python shared/tools/memory.py --settle 600 --rounds 3 --tolerance 0.01 --dimensions 384 --vectors 2 --against chapters/ch04/expected/memory.json --label "with the precomputed field filled" --against-label "one vector field" --delta-label "the second vector field" --out chapters/ch04/expected/memory-precomputed.json > chapters/ch04/expected/memory-precomputed.block.md
```
wrote `chapters/ch04/expected/memory-precomputed.json`, `chapters/ch04/expected/memory-precomputed.block.md` (the settled readings are in the report, `readings_mb`)


```
.venv/bin/python chapters/ch04/model_tradeoff.py --block model-tradeoff --baseline chapters/ch04/expected/validation-bm25_tuned.json --small-eval chapters/ch04/expected/validation-semantic.json --small-feed chapters/ch04/expected/feed.json --small-memory chapters/ch04/expected/memory.json --base-eval chapters/ch04/expected/validation-semantic-base.json --base-feed chapters/ch04/expected/feed-base.json --base-memory chapters/ch04/expected/memory-base.json > chapters/ch04/expected/model-tradeoff.block.md
```
wrote `chapters/ch04/expected/model-tradeoff.block.md`

```
.venv/bin/python chapters/ch04/reach.py --split validation --from chapters/ch04/expected/validation-reach.json --block reach-depths > chapters/ch04/expected/validation-reach-depths.block.md
```
wrote `chapters/ch04/expected/validation-reach-depths.block.md` (rendered from the report above, nothing re-measured)

```
.venv/bin/python chapters/ch04/reach.py --split test --from chapters/ch04/expected/test-reach.json --block reach-depths > chapters/ch04/expected/test-reach-depths.block.md
```
wrote `chapters/ch04/expected/test-reach-depths.block.md`

```
.venv/bin/python shared/tools/compare.py chapters/ch04/expected/validation-semantic.json chapters/ch04/expected/validation-semantic-base.json --baseline validation-semantic --block comparison > chapters/ch04/expected/compare-validation-base-vs-small.block.md
```
wrote `chapters/ch04/expected/compare-validation-base-vs-small.block.md` (bge-base against bge-small, brackets on ndcg@10 and recall@100)

The overlap block gained a net row; both blocks re-rendered from their reports, nothing re-measured:
```
.venv/bin/python chapters/ch04/retriever_overlap.py --split validation --from chapters/ch04/expected/validation-overlap.json > chapters/ch04/expected/validation-overlap.block.md
```
wrote `chapters/ch04/expected/validation-overlap.block.md`
```
.venv/bin/python chapters/ch04/retriever_overlap.py --split test --from chapters/ch04/expected/test-overlap.json > chapters/ch04/expected/test-overlap.block.md
```
wrote `chapters/ch04/expected/test-overlap.block.md`

> 2026-09-16: `embed_offline.py --check` gained a `build` field in its report; the check command above was re-run unchanged and `expected/encode-check.json` rewritten (block identical).

> 2026-09-16: every block table gets a named first column; the model-choice table names its two difference columns. Blocks re-rendered from their reports (nothing re-measured):

```
.venv/bin/python chapters/ch04/ann_sweep.py --split validation --from chapters/ch04/expected/validation-ann-sweep.json --block ann-sweep > chapters/ch04/expected/validation-ann-sweep.block.md
```
wrote `chapters/ch04/expected/validation-ann-sweep.block.md` (re-rendered from its report; header columns named)

```
.venv/bin/python chapters/ch04/ann_sweep.py --split validation --from chapters/ch04/expected/validation-ann-sweep.json --block ann-sweep-latency > chapters/ch04/expected/validation-ann-sweep-latency.block.md
```
wrote `chapters/ch04/expected/validation-ann-sweep-latency.block.md` (re-rendered from its report; header columns named)

```
.venv/bin/python chapters/ch04/reach.py --split validation --from chapters/ch04/expected/validation-reach.json --block reach-depths > chapters/ch04/expected/validation-reach-depths.block.md
```
wrote `chapters/ch04/expected/validation-reach-depths.block.md` (re-rendered from its report; header columns named)

```
.venv/bin/python chapters/ch04/reach.py --split test --from chapters/ch04/expected/test-reach.json --block reach-depths > chapters/ch04/expected/test-reach-depths.block.md
```
wrote `chapters/ch04/expected/test-reach-depths.block.md` (re-rendered from its report; header columns named)

```
.venv/bin/python shared/tools/memory.py --from chapters/ch04/expected/memory.json --dimensions 384 --label "one vector per title (bge-small)" > chapters/ch04/expected/memory.block.md
```
wrote `chapters/ch04/expected/memory.block.md` (re-rendered from its report; header columns named)

```
.venv/bin/python shared/tools/memory.py --from chapters/ch04/expected/memory-base.json --dimensions 768 --label "bge-base, one vector per title" > chapters/ch04/expected/memory-base.block.md
```
wrote `chapters/ch04/expected/memory-base.block.md` (re-rendered from its report; header columns named)

```
.venv/bin/python shared/tools/memory.py --from chapters/ch04/expected/memory-precomputed.json --against chapters/ch04/expected/memory.json --dimensions 384 --vectors 2 --label "with the precomputed field filled" --against-label "one vector field" --delta-label "the second vector field" > chapters/ch04/expected/memory-precomputed.block.md
```
wrote `chapters/ch04/expected/memory-precomputed.block.md` (re-rendered from its report; header columns named)

```
.venv/bin/python shared/tools/embed_offline.py --from chapters/ch04/expected/encode.json > chapters/ch04/expected/encode.block.md
```
wrote `chapters/ch04/expected/encode.block.md` (re-rendered from its report; header columns named)

```
.venv/bin/python shared/tools/embed_offline.py --from chapters/ch04/expected/encode-check.json > chapters/ch04/expected/encode-check.block.md
```
wrote `chapters/ch04/expected/encode-check.block.md` (re-rendered from its report; header columns named)

```
.venv/bin/python chapters/ch04/model_tradeoff.py --block model-tradeoff --baseline chapters/ch04/expected/validation-bm25_tuned.json --small-eval chapters/ch04/expected/validation-semantic.json --small-feed chapters/ch04/expected/feed.json --small-memory chapters/ch04/expected/memory.json --base-eval chapters/ch04/expected/validation-semantic-base.json --base-feed chapters/ch04/expected/feed-base.json --base-memory chapters/ch04/expected/memory-base.json > chapters/ch04/expected/model-tradeoff.block.md
```
wrote `chapters/ch04/expected/model-tradeoff.block.md` (re-rendered from its report; header columns named)

## 2026-10-06 (A-01)

The authors asked for the locale in the document id's namespace (`id:us:product::B07L2V81VS`, the user-specified part the bare ASIN); the equality check names that document, so it was re-run on a chapter-4 container built from the rebuilt corpus (`review/bootstrap-a01-2026-10-06.txt`: `./bootstrap.sh ch04` on the fresh chapter-2 container, 101,341 documents fed in 8m 04s, 209 docs/s — a bootstrap record, not a report; the shipped `expected/feed.json` was restored). The command is the one above, unchanged:
```
.venv/bin/python shared/tools/embed_offline.py --check "MARSVOVO Women's Sports Non Slip Running Shoes Work Shoes Fashion Sneakers Air Knitted Ultra Lightweight Breathable Athletic Gym Walking Running Shoes Black Size 8" --out chapters/ch04/expected/encode-check.json > chapters/ch04/expected/encode-check.block.md
```
wrote `chapters/ch04/expected/encode-check.json`, `chapters/ch04/expected/encode-check.block.md` (max absolute difference 0.000000, cosine 1.000000 against the document API's `title_embedding` for `B07L2V81VS`; the block is byte-identical to the 2026-09-16 one, the report's `compared_against` now names the bare ASIN)
