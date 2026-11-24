# Chapter 10 — Recommendation and Personalization as a Ranking Problem

This directory is the code for Chapter 10 of *Production AI Search with Vespa*. It treats recommendation and personalization as one more input to the retrieval and ranking machinery the book has already built, not as a separate system. Each synthetic user's profile lives in a second document type, `user`, kept current with partial updates, and reaches the product search as request inputs.

The chapter then asks three questions of the same 101,341 products:

- **With no query,** does a user's own profile, sent as the query of a vector search, find the products labelled relevant to that user's held-out queries?
- **With a typed query,** does adding the profile to the ranking help, and which part of the profile does the work?
- **How quickly** does a new event become visible to the next request?

The book explains what each step does and why. This page is the practical half: what to run, in the same order as the chapter, what you should see, and what to do when something goes wrong.

## What is in this directory

```
chapters/ch10/
├── app/                                  the application package Vespa deploys
│   ├── services.xml                      Chapter 8's, plus the user document type in the content cluster
│   ├── schemas/
│   │   ├── product.sd                    byte-identical to Chapter 8's
│   │   ├── user.sd                       new: the profile document, seven attributes, nothing indexed
│   │   └── product/                      one file per rank profile
│   │       ├── personalized.profile      new: the funnel with three profile terms in its first phase
│   │       ├── personalized_lexical.profile  new: the brand term on Chapter 3's keyword profile
│   │       └── …                         Chapters 3 to 8's profiles, unchanged
│   └── search/query-profiles/            unchanged from Chapter 8
├── chapter.toml                          what bootstrap.sh needs for this chapter
├── start.sh                              runs bootstrap.sh, then derives, feeds and fills the users
├── derive_users.py                       builds the brand-cluster users and their profile / held-out split
├── derive_events.py                      turns each user's profile-half judgements into an ordered event stream
├── profile_updater.py                    applies events to user documents, one partial update each
├── recommend.py                          recommendation with no query: the profile as the query
├── personalized_eval.py                  the profile inside the ranking, against baseline and controls
├── freshness.py                          how soon a new event is visible to a read, a search and a recommendation
├── COMMANDS.md                           every command, as run for the book
└── expected/                             the book's reference output
```

The query tool, the feed tool and the memory tool are shared by every chapter and live in `shared/tools/`.

## What you need

The same as Chapter 8. This chapter trains nothing.

|  | Version used for the book | Notes |
| :---- | :---- | :---- |
| Docker | — | Give it **4 CPUs and 10 GB of memory**. Docker Desktop or Rancher Desktop both work. |
| Python | 3.11 (3.11.13) | Only needed to create the virtual environment. |
| Vespa CLI | 8.562.17 | macOS: `brew install vespa-cli`. Linux and Windows: the Vespa GitHub releases page. |
| Models | Chapter 6's three | `bge-small-en-v1.5`, `colbertv2.0` and `ms-marco-MiniLM-L6-v2`, already in place if you are continuing. The personalized requests use the funnel's ColBERT second phase. |
| Network | — | Access to Hugging Face, only when starting fresh. |

Every pinned version is listed in `docs/pins.md` at the repository root.

## Run it

From the repository root:

```
chapters/ch10/start.sh
```

**Run `start.sh`, not `./bootstrap.sh ch10`.** `start.sh` runs the shared bootstrap first, then the chapter's own chain:

1. `derive_users.py` derives the users.
2. `feed.py` feeds them as empty documents.
3. `derive_events.py` derives the event stream.
4. `profile_updater.py` applies the events one partial update at a time.

Running `./bootstrap.sh ch10` on its own deploys the right package but leaves zero `user` documents, and every command below needs them.

If you are continuing from Chapter 8, the bootstrap only deploys this chapter's package, which adds the `user` type and the two new rank profiles. Nothing about the products changes, so nothing is refed. The user chain then derives 4,210 users and 86,036 events and applies them.

If you are starting with this chapter, add `--fresh`. It builds everything from the beginning, feeds the catalogue and fills `tenant_id` as Chapter 8 did, then runs the same user chain.

The deployment prints the same warning as in earlier chapters, about `document-summary 'context'`. That is expected.

On the reference machine (Apple M4 Pro, container VM with 4 CPUs and 10 GB), timings were:

- continuing from Chapter 8: 366 seconds
- a fresh run: 2,440 seconds, about 29 minutes of it the product feed
- a first run that also had to read the dataset from Hugging Face: 3,281 seconds in total

Your timings will differ.

The script counts the user documents, and the filled ones, before it reports the container ready. If either count is short, it reruns the whole chain from the empty feed, so nothing is applied twice. A successful run ends with both document types:

```
== at the start of ch10
   build      builds/esci-us-hard-book-s42-kdd-v4
   image      vespaengine/vespa:8.751.13
   documents  101341
   embedders  embedder=BAAI/bge-small-en-v1.5@5c38ec7c colbert=colbert-ir/colbertv2.0@c1e84128

== at the start of ch10 (users)
   users      4210 (4210 filled)
```

## The commands in this chapter

The steps below follow the chapter, section by section. Run them from the repository root after `start.sh` has finished.

Most commands save their result in `expected/`, replacing the book's copy of that file, so that `git diff chapters/ch10/expected/` shows how your run compares with the book's. To put the book's files back, run `git checkout chapters/ch10/expected/`. `start.sh` itself rewrites four reports: `users.json`, `feed-users.json`, `events.json` and `profile-updates.json`.

**Budget your time.** Everything below except the profile inside the ranking takes minutes. The personalized report runs the full hybrid funnel, ColBERT second phase included, over thousands of pairs, and took about 70 minutes on the reference machine. The memory reading takes at least twenty minutes. The weight sweeps that chose the chapter's weights took over four hours; their results ship in `expected/`, so they are listed separately at the end and are optional.

**What the synthetic users are.** A user here is not a person: it is a cluster of up to 30 ESCI training queries whose Exact-labelled products share a brand. Each user's queries are split in half:

- the **profile** half builds what the system is allowed to know;
- the **held-out** half is what it is scored against.

The 4,210 users are split again:

- a **tuning** half (2,105 users, 3,512 held-out pairs) chooses every weight;
- a **reporting** half (2,105 users, 3,588 pairs) is scored once, at those weights.

The events are judgements, named `judged_relevant` (Exact) and `judged_substitute` (Substitute). They are not clicks or purchases. `--split train` on every command below means the users are built from training judgements.

### Recommendation as retrieval plus ranking

Nothing to run beyond `start.sh`. The new document type is declared in `app/services.xml`; the new rank profiles are in `app/schemas/product/`.

### A profile built from events

The profile document is `app/schemas/user.sd`. `start.sh` already filled it. Three commands print the reports it wrote and measure what the type costs.

**Feeding the empty users and applying the events:**

```
.venv/bin/python shared/tools/feed.py --from chapters/ch10/expected/feed-users.json > chapters/ch10/expected/feed-users.block.md
.venv/bin/python chapters/ch10/profile_updater.py --split train --from chapters/ch10/expected/profile-updates.json --block updates > chapters/ch10/expected/profile-updates.block.md
```

**What you should see:** 4,210 users fed in about 2.7 seconds, and 86,036 events applied in about 290.9 seconds, 296 updates per second, on the reference machine. The titles' one-time encoding before the first update is in neither figure.

**What the user type adds to memory.** At least twenty minutes:

```
.venv/bin/python shared/tools/memory.py --settle 600 --rounds 3 --tolerance 0.01 --doctype user --label "ch10 user type" --out chapters/ch10/expected/memory-user.json
.venv/bin/python shared/tools/memory.py --from chapters/ch10/expected/memory-user.json > chapters/ch10/expected/memory-user.block.md
```

**What you should see:** about 16 MB for the `user` type, beside 6 MB computed by hand for the profile vectors (4,210 × 384 × 4 bytes). Check that the report says `settled: true`.

### Candidate generation with no query

The profile vector, normalized to unit length, is sent as the query of Chapter 4's `nearestNeighbor(title_embedding, q)` request, and products already in the user's `seen` list are dropped. Four rows, reporting half. This took about 68 seconds:

```
.venv/bin/python chapters/ch10/recommend.py --split train --half reporting --rows own,shuffled,popular,cross_brand --passes 1 --out chapters/ch10/expected/recommend-reporting.json --block recall
.venv/bin/python chapters/ch10/recommend.py --split train --from chapters/ch10/expected/recommend-reporting.json --block recall > chapters/ch10/expected/recommend-reporting-recall.block.md
.venv/bin/python chapters/ch10/recommend.py --split train --from chapters/ch10/expected/recommend-reporting.json --block deltas > chapters/ch10/expected/recommend-reporting-deltas.block.md
.venv/bin/python chapters/ch10/recommend.py --split train --from chapters/ch10/expected/recommend-reporting.json --block latency > chapters/ch10/expected/recommend-reporting-latency.block.md
```

| Row | What it sends |
| :---- | :---- |
| `own` | This user's own profile vector |
| `shuffled` | Another user's profile vector, against this user's held-out targets |
| `popular` | No request: the products with the most Exact judgements in the training pool, one list for everyone, minus the user's seen products |
| `cross_brand` | `own`'s candidates, counting only held-out targets whose brand is not in the user's `brand_weights` |

**What you should see:**

- Recall@10, @50 and @100 of 0.094, 0.219 and 0.278 for `own`.
- 0.001, 0.002 and 0.002 for `shuffled`.
- 0.000, 0.002 and 0.005 for `popular`.
- 0.098, 0.231 and 0.294 for `cross_brand`. Its target set is different, so compare its direction with `own`, not its size.
- In the deltas block, `own` against `shuffled` is +0.276 [+0.263, +0.289] at K=100, and `own` against `popular` +0.273 [+0.260, +0.286]. Both intervals exclude zero at every K.
- In the latency block, `own` at 6.3 ms p50 and 9.0 ms p95.

**Adding a business constraint.** One reporting-half user, `generic`, unfiltered and with Chapter 8's `has_description` filter:

```
.venv/bin/python chapters/ch10/recommend.py --split train --user generic --block hits > chapters/ch10/expected/demo-generic-recommend.block.md
.venv/bin/python chapters/ch10/recommend.py --split train --user generic --where 'has_description = true' --block hits > chapters/ch10/expected/demo-generic-recommend-filtered.block.md
```

**What you should see:** a home-decor mix in the unfiltered top ten (a drink coaster, wall sconces, a curtain rod, sink drains, a vanity tray). With the filter, nine of the ten are the same. The curtain rod, which has no description, is replaced by the next nearest product that has one. A rebuilt HNSW graph can swap one item at the edge of the ten.

### The profile inside the ranking

The `personalized` profile inherits `phased` and adds three terms to its first phase: `brand_affinity`, `colour_affinity` and `vector_affinity`. Each has its own weight, sent as a request input that defaults to 0. Every request sends the hybrid query with `ranking.globalPhase.rerankCount=0`, so the cross-encoder is off.

**Choosing weights on one half, reporting on the other.** The reporting half, at the weights the tuning half chose. About 70 minutes:

```
.venv/bin/python chapters/ch10/personalized_eval.py --split train --half reporting --phase report --w own=0.05 shuffled=0.05 upper=0.5 colour=0.1 vector=1 vector_shuffled=1 --out chapters/ch10/expected/personalized-report.json --block report
.venv/bin/python chapters/ch10/personalized_eval.py --split train --half reporting --phase report --from chapters/ch10/expected/personalized-report.json --block report > chapters/ch10/expected/personalized-report.block.md
```

| Row | What it adds to the first phase |
| :---- | :---- |
| `baseline` | Nothing: the unpersonalized funnel |
| `own` | This user's brand distribution |
| `shuffled` | Another user's brand distribution |
| `upper` | The brand distribution with the user's defining brand added back: circular by construction, a diagnostic, not a real upper bound |
| `colour` | This user's colour distribution (computed by the tool, not stored) |
| `vector` | This user's profile vector |
| `vector_shuffled` | Another user's profile vector |

**What you should see:** NDCG@10 against baseline (0.350):

| Row | Change | Interval |
| :---- | :---- | :---- |
| `own` | +0.000 | [−0.001, +0.001] |
| `shuffled` | −0.000 | [−0.000, +0.000] |
| `upper` | +0.045 | [+0.040, +0.050] |
| `colour` | +0.008 | [+0.005, +0.011] |
| `vector` | +0.039 | [+0.033, +0.045] |
| `vector_shuffled` | −0.036 | [−0.041, −0.031] |

The two summary lines read `own vs shuffled: +0.000 [-0.001, +0.001]` and `vector vs vector_shuffled: +0.075 [+0.068, +0.082]`. Recall@10 in this table counts products judged Exact, Substitute or Complement; the recommendation tables count Exact only.

**Is the brand result an artifact of the funnel?** The same brand term on Chapter 3's keyword profile, `bm25_tuned`, at w = 10. BM25 is unbounded, so the weight scale differs. About 3 minutes:

```
.venv/bin/python chapters/ch10/personalized_eval.py --split train --half reporting --phase report --ranking personalized_lexical --w own=10 shuffled=10 upper=10 --out chapters/ch10/expected/personalized-lexical-report.json --block report
.venv/bin/python chapters/ch10/personalized_eval.py --split train --half reporting --phase report --ranking personalized_lexical --from chapters/ch10/expected/personalized-lexical-report.json --block report > chapters/ch10/expected/personalized-lexical-report.block.md
```

**What you should see:** baseline NDCG@10 0.303. `own` +0.001 [−0.002, +0.003]. `upper` +0.046 [+0.041, +0.050]. `own vs shuffled: +0.001 [-0.001, +0.003]`.

**Why the average is flat.** The tuning-half pairs split by whether the user's brand distribution covers the brand of at least one of the query's Exact products. This reads the shipped sweep report and queries nothing:

```
.venv/bin/python chapters/ch10/personalized_eval.py --split train --half tuning --phase tune --from chapters/ch10/expected/personalized-tune.json --block coverage > chapters/ch10/expected/personalized-coverage.block.md
```

**What you should see:** for 1,184 covered pairs, `own` against baseline +0.007 [+0.005, +0.010]; for 2,328 uncovered pairs, −0.003 [−0.004, −0.002]. The block is marked exploratory, because the split was chosen after the flat average was seen.

**Cost.** The personalized report records only its total time, 4,178.8 seconds over seven rows. Each row runs a discarded warm pass and a measured pass over 3,588 pairs, so that is about 83 ms per request, averaged. The report has no per-request p50 or p95.

### Recency, sessions, diversity, and exploration

The chapter's clock is invented. Every user's newest event is stamped on one snapshot day, Black Friday 2026 (`2026-11-27T00:00:00Z`), and earlier events count back one day each. `--now` defaults to that day, so the same command gives the same answer whenever you run it. The decay worked example in the chapter is arithmetic, not a command.

**One user, before and after.** Re-stamp `generic`'s last two events one day past the snapshot, then ask for the profile aged with a seven-day half-life at that day:

```
.venv/bin/python chapters/ch10/profile_updater.py --split train --user generic --events 246-247 --after-snapshot 1
.venv/bin/python chapters/ch10/recommend.py --split train --user generic --half-life 7 --now 2026-11-28T00:00:00Z --block hits > chapters/ch10/expected/demo-generic-recommend-next-day.block.md
```

The first command changes only two cells of `event_times`. Its printed report shows `0` events applied, because re-stamps are reported on its progress line, not in its table.

**What you should see:** every hit is artificial fruit or artificial plants (fake lemons, mini pumpkins, artificial flowers, a weeping willow), the theme of this user's most recent judgements. Without the re-stamp, the same ten come back with two neighbouring ranks traded.

**A profile with no recent history.** `now` thirteen months on, with a 90-day window:

```
.venv/bin/python chapters/ch10/recommend.py --split train --user generic --half-life 7 --now 2028-01-01T00:00:00Z --max-age 90 --block hits > chapters/ch10/expected/demo-generic-recommend-stale.block.md
```

**What you should see:** `profile older than 90.0 days at now=1830297600: popular list shown`, followed by the popular list (laptops, AirPods, an Echo Dot, a streaming stick, syringes) minus this user's seen products. No request is sent, so this block reproduces exactly.

**Restore the user.** Put `generic` back to its full 247-event history before moving on:

```
.venv/bin/python chapters/ch10/profile_updater.py --split train --user generic --reset
```

Session signals, diversity and exploration are discussed in the chapter but not built; there is nothing to run for them.

### Partial updates and feed-to-query freshness

For 50 reporting-half users, the tool sends one additional synthetic judgement event, folded in exactly as the updater folds every event. It then checks, in order:

1. a plain read of the user document;
2. a query-API lookup of the document;
3. a recommendation built from a fresh read.

Afterward, it restores every field it touched. About 8 seconds:

```
.venv/bin/python chapters/ch10/freshness.py --split train --users 50 --out chapters/ch10/expected/freshness.json --block freshness-search
.venv/bin/python chapters/ch10/freshness.py --split train --from chapters/ch10/expected/freshness.json --block freshness-search > chapters/ch10/expected/freshness-search.block.md
```

**What you should see:**

- `ack -> GET` p50 2.7 ms (p95 3.4 ms).
- `ack -> search` p50 5.8 ms (8.2 ms).
- `ack -> query` p50 14.6 ms (19.9 ms).
- `top ten changed` 48 of 50, and `0 get / 0 search / 0 query` misses.
- In the JSON report, `restore_verified` is true for all 50 users.

The tool checks immediately after the acknowledgement and then every 50 ms. Every figure is below that interval, so each is how long the checks took, not a visibility delay.

### Serving learned recommendation models; Offline metrics, counterfactual limits, and online signals

Nothing to run. No learned recommendation model is trained or served in this chapter.

### Optional: the weight sweeps

These two sweeps chose the weights the reporting tables use. Their reports ship in `expected/`, and the coverage command above reads the first one. Rerun them only if you want to reproduce the choice itself.

The funnel sweep took 14,713.9 seconds, just over four hours; the lexical sweep took 603.3 seconds:

```
.venv/bin/python chapters/ch10/personalized_eval.py --split train --half tuning --phase tune --w 0.05,0.1,0.2,0.5 --w-vector 0.1,0.2,0.5,1 --out chapters/ch10/expected/personalized-tune.json --block tune
.venv/bin/python chapters/ch10/personalized_eval.py --split train --half tuning --phase tune --from chapters/ch10/expected/personalized-tune.json --block tune > chapters/ch10/expected/personalized-tune.block.md
.venv/bin/python chapters/ch10/personalized_eval.py --split train --half tuning --phase tune --ranking personalized_lexical --w 1,2,5,10 --out chapters/ch10/expected/personalized-lexical-tune.json --block tune
.venv/bin/python chapters/ch10/personalized_eval.py --split train --half tuning --phase tune --ranking personalized_lexical --from chapters/ch10/expected/personalized-lexical-tune.json --block tune > chapters/ch10/expected/personalized-lexical-tune.block.md
```

**What you should see:**

- **Brand (`own`):** never clears zero on the positive side. Its best point estimate is +0.001 at w = 0.05, and its interval is below zero from w = 0.2 up.
- **Colour:** peaks at w = 0.1 (+0.007) and turns sharply negative at 0.5 (−0.045).
- **Vector:** rises to +0.030 at 0.5 and +0.032 at 1.0.
- **Upper:** rises across the whole grid to +0.045 at 0.5.
- **Lexical sweep:** `upper` reaches +0.044 at w = 10, and `own` never moves by more than a few thousandths.

## Comparing your run with the book's

`expected/` holds the output of every command above, exactly as it ran when the book was written. Four kinds of number are in there, and they behave differently:

- **Counts from the corpus build and the derivation.** These come back exactly: 4,210 users, 7,100 held-out pairs, 86,036 events, and the tuning and reporting halves.
- **Quality numbers.** Recall@K, NDCG@10 and their intervals. Every row that sends a vector request goes through an HNSW graph, which is built slightly differently on every feed, so these come back within a few thousandths. The demonstration top tens can swap one item at the edge. The stale demonstration sends no request and reproduces exactly.
- **Freshness counts.** Expect 0 misses and `restore_verified` true. The number of users whose top ten changed can differ by one or two.
- **Cost numbers.** Bootstrap, feed and update timings, latency, freshness timings and memory. These describe one machine on one day (an Apple M4 Pro, Docker with 4 CPUs / 10 GB), one query at a time. Yours will differ, and that is expected.

After a run, `git diff chapters/ch10/expected/` shows every difference.

`expected/` also holds three product-type memory readings that the chapter does not quote: `memory-fresh` (taken right after `start.sh`), `memory` (taken after the measurements, compared with Chapter 8's container), and a tuning-half recall table, `recommend-tuning-recall`. `COMMANDS.md` lists how each was produced.

## If something goes wrong

**A command says a user document was not found, or every recall is zero.** The `user` documents are missing or empty. You probably ran `./bootstrap.sh ch10` instead of `chapters/ch10/start.sh`. Run `start.sh`; it fills the users and checks the counts.

**Counting `user` documents through the query API returns 0 with an error.** The default query profile names `bm25_tuned`, a rank profile only the `product` schema has. Add `ranking.profile=unranked` to a hand-typed count, as `start.sh` does.

**The demonstration top ten is not the book's after you ran the re-stamp.** Run `profile_updater.py --user generic --reset` to restore the full history, then repeat the demonstration steps in order. Rerunning `start.sh` also rebuilds every profile.

**The freshness tool reports misses or `restore_verified` false.** Something else was writing to the same user documents, or the container was under load. Rerun it when nothing else is using the container. If a restore failed, `start.sh --fresh` rebuilds every profile from the event stream.

**A hand-built request fails on a brand label.** Some brand strings need cleaning before they become tensor labels:

- Two spellings that clean to the same label must be merged into one cell; the engine rejects a literal with the same address twice.
- A double quote inside a label breaks the request even when escaped.
- A `#` in a document ID must be percent-encoded.

The chapter's tools already handle all three.

**The personalized report is very slow.** Expected: each request runs the full hybrid funnel with the ColBERT second phase. Check that `ranking.globalPhase.rerankCount=0` is being sent; with the cross-encoder on, each request takes close to a second.

**Encoding titles is killed partway, with no error.** The process ran out of memory. The tools encode in batches; if you changed the batch size, set it back.

**The memory reading is higher than the book's.** The container has a longer history. If the report says `settled: false`, run it again when nothing else is querying the container.

**The deploy or feed fails, or Vespa stops responding partway.** Check that Docker really has 4 CPUs and 10 GB. Every run behind the book used exactly that, so too little memory is the first thing to rule out.

**The container fails to start because a port is already allocated.** Something else on your machine is using port 8080 or 19071. Stop it, or stop the other Vespa container, then rerun with `--fresh`.

## Next

The next chapter changes who is searching. The same catalogue, lenses and ranking machinery serve a consumer that is not a person: an AI agent that issues many searches in sequence and reasons forward from what comes back. That chapter's code is on hold: `chapters/ch11/DESIGN.md` holds its design and a runnable five-question example, with no full lab yet.
