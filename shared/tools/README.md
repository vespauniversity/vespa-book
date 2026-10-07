# Shared tools

One copy, on the path of every environment `bootstrap.sh` creates. Nothing is
copied between chapter directories, so a fix here is a fix everywhere — and
each chapter's `chapter.toml` lists which of these it ships, so a chapter hands
over what it asks you to run and not what a later one will.

The Vespa application packages under `chapters/*/app/` are the opposite: each
is a complete copy, because an application package is a deployment unit and the
difference between two chapters' packages is what that chapter added.

<!-- given: what each module is, the chapter that introduces it, and whether a reader runs it -->
| Module | Introduced by | A reader runs it | What it is |
|---|---|---|---|
| `corpus.py` | chapter 2 | yes | Builds a deterministic ESCI corpus for the book's examples |
| `feed.py` | chapter 2 | yes | Feeds documents over the document API, with retries and progress |
| `query.py` | chapter 2 | yes | Queries over the search API, and reads what came back |
| `evaluate.py` | chapter 3 | yes | Measures a rank profile against a corpus build |
| `embed_offline.py` | chapter 4 | yes | Computes the document vectors yourself, instead of letting Vespa do it |
| `memory.py` | chapter 4 | yes | What the index costs in memory and on disk, read once it has settled |
| `compare.py` | chapter 4 | yes | Puts evaluation reports side by side: tables, brackets on every difference, the verdict word (chapter 3 ships its own copy with a grid block) |
| `models.py` | chapter 6 | yes | Fetches a pinned model file by URL and commit, and verifies it by hash |
| `hf.py` | chapter 2 | no | Reads a Hugging Face parquet dataset over HTTP range requests, so a build fetches the columns it needs rather than the 2.5 GB file |
| `gains.py` | chapter 2 | no | ESCI relevance labels and the two gain mappings in circulation |
| `metrics.py` | chapter 3 | no | Retrieval metrics, implemented here rather than imported |
| `builds.py` | tooling | no | Reads what a corpus build produced |
| `hostinfo.py` | tooling | no | Records the machine a measurement was taken on |
| `deployed.py` | tooling | no | What is actually deployed, asked of the running system rather than assumed |

The eight a reader runs are the ones a chapter puts on a command line. The other
six are imported by those and by each other; they are here because a fix to one
is a fix everywhere, not because anything asks you to invoke them.

**The table covers every chapter's tools, and the book is released a few
chapters at a time**, so the *Introduced by* column is also how you tell what is
in front of you: a module belonging to a chapter you have not been given yet is
not in your copy, and nothing you do have asks for it. The three marked
*tooling* are in every copy, because everything else imports them.

## Building a corpus

```
.venv/bin/python shared/tools/corpus.py build --preset book
```

The defaults are what the book measures. Changing one gives a different corpus
and different numbers, which is what the flags are for; the book just will not
be describing what you have.

Presets, so the corpus a chapter used is a name rather than a paragraph of
flags:

<!-- given: the preset definitions themselves -->
| Preset | Queries | Documents | For |
|---|---|---|---|
| `tiny` | 200 | ~7K | iterating |
| `book` | 3,500 | ~101K | the numbers that appear in the book |
| `small` | 1,000 | ~100K | the previous book preset, kept so its reports stay readable |
| `full` | all | ~480K | whoever has the machine |

The first build streams the dataset once and caches the US rows under
`shared/cache/`, roughly a quarter of an hour. Later builds are local: changing
a preset, a seed or the gain mapping does not touch the network.

Every build writes a `BUILD.md` recording what it was made from: the arguments,
the pinned dataset commit, the row counts, and a content hash. Builds from the
same arguments are byte-identical.

`--shards N` reads only part of the dataset. It exercises the tooling quickly
and produces a build marked partial — a query's judgements can be split across
shards, so partial builds have truncated ground truth and cannot be measured
against.

## What a build contains

```
products.jsonl          Vespa feed format, judged products plus distractors
doc_signals.jsonl       popularity, exact_rate, n_judgements — partial updates
queries_{train,validation,test}.csv
judgements_{train,validation,test}.csv    query_id, document_id, label, gain, ordinal
BUILD.md  build.json
```

Three rules the builder enforces, because breaking any of them is silent:

**Sampling is by query.** Every retained query keeps all of its judgements.
Removing a judged product from the index while leaving it in the qrels would
penalise a system for not finding something that is not there.

**Document signals come from the train split only.** Deriving `popularity` or
`exact_rate` from every judgement would put test labels into the index and
inflate every metric with no visible symptom.

**The validation split is carved out of train.** ESCI ships train and test
only; the third split is ours, and it is called `validation` rather than `dev`
because `dev` means too many different things in too many repositories to be a
split name. The official train/test boundary is kept. Test is touched to
produce a number that gets reported, never to make a decision.
