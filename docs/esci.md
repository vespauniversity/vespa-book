# ESCI dataset

`amazon-science/esci-data` — *Shopping Queries Dataset: A Large-Scale ESCI
Benchmark for Improving Product Search*. Repo licence Apache-2.0.

## What it gives us

`shopping_queries_dataset_products.parquet`
: `product_id` (ASIN), `product_title`, `product_description`,
  `product_bullet_point`, `product_brand`, `product_color`, `product_locale`

`shopping_queries_dataset_examples.parquet`
: `example_id`, `query`, `query_id`, `product_id`, `product_locale`,
  `esci_label` (E/S/C/I), `small_version`, `large_version`, `split`

`shopping_queries_dataset_sources.csv`
: `query_id`, `source`

English (US), reduced version: 29,844 queries / 601,354 judgements, average
depth 20.15, already split train/test. Larger version: 97,345 / 1,818,825.

`product_id` is unique **per locale**, not globally. Document ids must carry
the locale.

## Why this replaces the workshop data

| | Workshop | ESCI |
|---|---|---|
| Judgements | 499 queries, LLM-generated, self-described PoC | 29,844 queries, human-annotated |
| Grades | 0–3, produced by a prompt | E/S/C/I, the benchmark's own labels |
| Split | 80/20 random, made up here | Official train/test that the literature uses |
| Licence | Myntra catalogue, unclear | Apache-2.0 |
| Rating / price | `random.uniform(1, 5)` | Absent — see *Derived signals* |

## Where we get it

Two sources, both supported by `download.py`. `BUILD.md` records which was used
and the resulting row counts, so any build is verifiable.

**Canonical — `amazon-science/esci-data`.** The parquet files are git-LFS
pointers (133 and 135 bytes in the repo tree), so this path needs `git lfs` and
a join between examples and products. This is the source the book cites.

**Access path — `tasksource/esci` on Hugging Face.** Apache-2.0, already joined
(examples × products in one table), sharded parquet, streamable without
downloading the corpus. 2,027,874 train rows and 652,490 test rows.

This mirror is what makes chapter 2's "stream a dataset from Hugging Face
without downloading the full corpus" work unchanged — that heading needs no
revision.

Differences from the canonical files, all harmless but worth knowing:

- `esci_label` is spelled out (`Irrelevant`) rather than the single letter
- the train/test split is the Hugging Face split, not a `split` column
- an extra derived `product_text` column (title + brand + colour + bullets)
- no `shopping_queries_dataset_sources.csv`

Read with `pyarrow` over HTTP range requests — row groups are pulled lazily, so
a build that needs 1,000 queries never fetches the whole file. Fetch once,
cache, checksum. Nothing downstream touches the network.

## Corpus build

This section described a planned `esci/build_corpus.py` with flags and outputs
that were never built under those names. What exists is
`shared/tools/corpus.py`, and `--help` is the authority:

```
.venv/bin/python shared/tools/corpus.py build
  --preset tiny|small|full    queries and distractors together, as one name
  --seed 42
  --gains kdd|vespa-sample    which grade-to-gain mapping
  --difficulty hard|all       which ESCI query set
  --shards N                  first N shards only; marks the build partial
```

There is no `--locale` (US is the only locale read), no `--queries` or
`--distractors` (a preset carries both), no `--out` (the build id names the
directory), and **no `--dev-fraction`**: the carved-out split is fixed and is
called `validation`, not `dev`, because `dev` already means something else in
most repositories and a reader assuming the usual meaning would assume the wrong
thing about which numbers may be tuned against.

Outputs, all deterministic for the same inputs:

```
builds/<build-id>/
  products.jsonl              Vespa feed format
  queries_train.csv           query_id,query_text
  queries_validation.csv
  queries_test.csv
  judgements_train.csv        query_id,document_id,rating
  judgements_validation.csv
  judgements_test.csv
  doc_signals.jsonl           train-derived document fields (see below)
  build.json                  the machine-readable record, including counts
  BUILD.md                    build id, arguments, source checksum, row counts
```

`query_id,query_text` and `query_id,document_id,rating` match the column names
the existing workshop scripts already use, so `evaluate.py` and the
`train_reranker` scripts port with minimal change.

### One streaming pass, then everything is local

The first build streams the dataset once and caches the US rows it needs under
`shared/cache/`. This has since been done in full and recorded, so the
extrapolation that stood here — two shards at 276 MB and 103 seconds, hence
"roughly 2.5 GB and fifteen minutes" for fifteen shards — can come out:
every chapter's `review/bootstrap-cold.txt` records a whole cold run from an
empty cache (ch02 14m 18.6s, ch03 17m 57s, ch04 22m 19s, the dataset stream
13–15 minutes of each), which is roughly where the extrapolation landed and is
also why it looked right. (The old project's whole-book timing reports
were removed with the old project.)
After the first build, changing preset, seed or gain mapping costs nothing but
local compute.

Seven of the dataset's fourteen columns are read. The largest, `product_text`,
is a derived concatenation of the others and is skipped.

### Sampling rule: by query, never by judged product

The one way to break the ground truth is to remove a judged product from the
index while leaving it in the qrels. The system is then penalised for failing to
find something that does not exist, and every retrieval metric is wrong by an
amount nobody can see.

So the build samples queries and keeps each retained query's judgements whole:

```
select N queries, inside the official splits, proportionally
  keep ALL judged products for those queries
  add M unjudged products as distractors
corpus = deduplicated judged products + M
```

NDCG over a query's twenty judgements is a valid NDCG whether or not other
queries were dropped. Dropping queries costs statistical power and nothing else.
Dropping judgements inside a retained query costs correctness.

If the corpus is too large for the machine, reduce in this order:

1. **Fewer distractors.** Changes how hard retrieval is, not whether the
   measurement is valid — provided the corpus composition is stated wherever the
   numbers appear.
2. **Fewer queries.** Costs statistical power; the confidence interval widens.
3. **Precompute embeddings offline**, removing the feed-time CPU cost entirely.
   This is chapter 4 material regardless.
4. **Drop the `description` embedding** — half of them encode an empty string
   anyway.
5. **Quantize** to int8 or bfloat16. Also chapter 4 material.

### Unjudged is not the same as irrelevant

ESCI's judgement pool is finite — only part of the catalogue was ever graded
against any one query. Anything outside that pool is unjudged, which is not a
statement that it is irrelevant — some distractors will be genuinely relevant
products that nobody ever labelled.

Treating unjudged as irrelevant is the standard pooling assumption, and it
biases recall downward. It does so uniformly across ranking methods, so
comparisons between them stay valid; only the absolute number is pessimistic.
The text says this rather than presenting recall as if it were exact. **That
argument needs the pool to be finite and needs no bound on it**, which is the
whole reason a bound was never checked.

**How deep the pool goes is a property of the build, and is measured.** Until
2026-09-14 this paragraph opened with a flat bound of forty judgements per
query, asserted of ESCI itself. It was the third surviving form of a claim
already corrected in `shared/tools/corpus.py` and in the root `README.md`, and
it had never been measured against any build. The sentence is not quoted here,
because a document that reprints a false claim in order to deny it is how this
one acquired it.

`shared/tools/corpus.py`'s `judgement_depth()` measures it per build — minimum,
maximum, mean, median, and how many queries are past forty — into that build's
`build.json` under `judgements_per_query`, and that build's `BUILD.md` prints
what is in `build.json`. **Take the bound from that field, not from a sentence
here.** On `esci-us-hard-small-s42-kdd-v4`, the build the chapters use, it reads
8 to 136, median 16, mean 20.7, with 31 of 1,000 queries past forty. Those five
figures are that field's and move with the build; `build.json` is not committed,
so the build is where they are read, not this page. Forty survives only as a
reference point, because it is what a reader will have heard.

### Distractors are not optional

If the corpus contains only judged products, every judged document is reachable
and recall approaches 1.0 for any competent retrieval method. The chapters would
then report meaningless improvements. `--distractors` samples from products
never judged for any selected query. The ratio used for the book's numbers is
stated in the text.

### Deterministic sampling

Query selection sorts by `query_id` before sampling with a seeded RNG.
Distractor selection sorts by `(locale, product_id)`. Output rows are written in
sorted order. Two builds with the same arguments produce byte-identical files,
verified by checksum in `BUILD.md`.

## Judgement grades

ESCI labels map to gains. Two conventions, both recorded, one selected per
build:

| Label | Default (KDD Cup) | Alternative (Vespa sample app) |
|---|---|---|
| E — Exact | 1.00 | 1.00 |
| S — Substitute | 0.10 | 0.01 |
| C — Complement | 0.01 | 0.10 |
| I — Irrelevant | 0.00 | 0.00 |

The two disagree on the middle pair. The default is the widely cited mapping and
the one that matches what the labels mean — a substitute is an alternative
product, a complement is an accessory. The alternative is a build flag, for
cross-checking against Vespa's published LTR numbers. LightGBM's `label_gain`
follows whichever is selected.

Gains are already in 0–1, so they need no rescaling. A 0–3 integer variant is
emitted as well, because the workshop scripts assume that scale and divide by
three.

The chosen mapping is stated wherever a number derived from it appears. NDCG is
not comparable across mappings.

## Field coverage — half the dataset has no description

Measured on the dataset's 2,027,874 training rows (`tasksource/esci`), not on
this book's 101,341-document build (whose own description figure, 48.7%, is in
`product.sd`):

| Field | Missing |
|---|---|
| `product_title` | 0% |
| `product_brand` | 6.2% |
| `product_bullet_point` | 13.7% |
| `product_color` | 34.4% |
| `product_description` | **51.9%** |

This is not a detail. Several chapters are built on "separate title and body
signals" — chapter 3 tunes field weights across them, chapter 4 gives each its
own embedding, chapters 5 and 6 fuse the two. In the dataset's training rows the body field is
absent for more than half the query–product rows, and an embedding of an empty string
still produces a vector with a closeness score, so the failure is silent rather
than loud.

Consequences for the schema:

- **`bullets` is the body field**, not `description`. On Amazon data the bullet
  points are where the substantive product text lives, and they are present for
  86% of documents.
- **`description` stays, as a third text field**, used where present.
- **`has_description` becomes an explicit attribute**, so a rank expression can
  account for absence instead of quietly scoring a vector built from nothing.
- Chapter 4 gives `bullets` an embedding; whether `description` also gets one is
  a measurement, not an assumption — if half of them encode empty strings, the
  field may be worth more as a lexical signal only.

This is worth teaching rather than hiding. A corpus where the obvious field is
missing half the time is an ordinary production situation, and noticing it
before tuning weights on it is exactly the discipline chapter 3 is about.

`product_bullet_point` arrives as a single newline-separated string. The loader
splits it into `array<string>`, which both matches how it reads and gives
chapter 4 its chunks for the multi-vector example. Note that BM25 over an array
field scores differently from BM25 over one concatenated string; the chapter
should say so rather than let the reader assume equivalence.

## Derived signals

ESCI has no price, rating, category or stock. The workshops filled that gap with
random numbers. Instead, derive from the data (`corpus.py build` writes them to
`doc_signals.jsonl`; **no chapter feeds them into the schema** — the book's
filters are `has_description` and the derived `tenant_id`, D23 / D101):

| Field | Definition | Purpose |
|---|---|---|
| `popularity` | number of distinct queries the product is judged against | cheap first-phase signal, LTR feature |
| `exact_rate` | fraction of the product's judgements labelled E | quality proxy |
| `n_judgements` | judgement count | denominator, and a diagnostic |
| `bullet_count`, `title_length`, `has_description` | from the product text | cheap document-quality features |

**These are computed from the train split only.** Deriving them over all
judgements puts test labels into the index, and every metric in the book
inflates with no visible error. `corpus.py build` writes `doc_signals.jsonl`
from train rows and refuses to run without an explicit split argument.

A distractor is a product not judged *for the queries in this build*, which is
not the same as never judged. Measured on a partial build of the 200-query
preset — `dev` at the time, `tiny` now — roughly half the distractors carry
train-split judgements from queries that were not selected. So `popularity` is a genuine signal rather than a disguised "is this
in the qrels" flag — better than feared, though the first-phase examples still
should not lean on it alone.

If a chapter genuinely needs price or customer rating, the option is a join to
Amazon Reviews 2023 on ASIN. That adds a second dataset and a second licence;
not taken unless a chapter requires it.

## Pre-processed data published by Vespa

The official sample application publishes files that shortcut parts of the
build. Useful for cross-checking our own builds, and as a fallback.

| | |
|---|---|
| Full feed, 1,215,854 products | `data.vespa-cloud.com/sample-apps-data/product-search-products.jsonl.zstd` |
| Test qrels, TREC format | `data.vespa-cloud.com/sample-apps-data/test.qrels` |
| Cross-encoder ONNX | `data.vespa-cloud.com/sample-apps-data/title_ranker.onnx` |

We still build our own corpus, because the book needs deterministic subsets with
a controlled distractor ratio and a validation split carved out of train, none
of which these files provide. But a build that disagrees with the published qrels on the queries they
share is a build with a bug.

## Sizing

Defaults for a developer laptop. These were estimates when written; `small` has
since been built and the row below is what it came out at, which is why it is
the only one with exact figures.

| Build | Queries | Judged products | Distractors | Total docs |
|---|---|---|---|---|
| `small` | 1,000 | 20,432 | 80,000 | 100,432 |
| `tiny` | 200 | ~4,000 | 6,000 | ~10,000 |
| `full` | 29,844 | ~480,000 | — | ~480,000 |

`tiny` — called `dev` while this page was first written — is for iteration.
`small` produces the numbers that go in the book unless a chapter states
otherwise. `full` is for the scaling chapter, out of scope here.
