# Chapter 2 — Getting Started with Vespa

This directory is the code for Chapter 2 of *Production AI Search with Vespa*. It takes you from an empty machine to a running Vespa application holding 2,000 products from Amazon's ESCI shopping dataset, checked by ten smoke tests and answering its first query.

The book explains what each step does and why. This page is the practical half: what to install, what to run, what you should see, and what to do when something goes wrong.

## What you need

|  | Version used for the book | Notes |
| :---- | :---- | :---- |
| Docker | — | Give it **4 CPUs and 10 GB of memory**. Docker Desktop or Rancher Desktop both work. |
| Python | 3.11 (3.11.13) | Only needed to create the virtual environment; nothing is installed globally. |
| Vespa CLI | 8.562.17 | macOS: `brew install vespa-cli`. Linux and Windows: the Vespa GitHub releases page. |
| Disk | about 3 GB | 1.5 GB for the Vespa image, 1.1 GB for the cached dataset, 150 MB for the sample. |
| Network | — | Access to Hugging Face, the first time only. |

The CLI and the Vespa server image (`vespaengine/vespa:8.751.13`) have different version numbers on purpose. Every pinned version is listed in `docs/pins.md` at the repository root.

## Run it

From the repository root:

```
./bootstrap.sh ch02 --fresh
```

`--fresh` starts clean: it removes any earlier virtual environment and Vespa container. If you have run this chapter before, leave it off — `./bootstrap.sh ch02` checks what is already in place and skips it.

The script works through five stages — **venv**, **corpus**, **container**, **app**, **documents** — and prints a heading for each. **The first run takes about a quarter of an hour**, almost all of it in the corpus stage, which reads the ESCI dataset from Hugging Face. While it runs you will see lines like:

```
[corpus] shard 3/15 test-00002-of-00004-a81cff173329b486.parquet (193 MB)
[corpus]   judged rows so far: 372,954 | products: 301,192 | 176s
```

Those lines mean it is working, not stuck. The script calls this *streaming the dataset*; that refers to how it reads files over HTTP, not to Vespa's streaming search mode. Later runs take seconds, because the dataset is cached under `shared/cache/`.

A successful run ends with the ten checks and this state:

```
10/10 checks passed

== at the start of ch02
   build      builds/esci-us-hard-book-s42-kdd-v4
   image      vespaengine/vespa:8.751.13
   documents  2000
   embedders  none declared
```

`embedders none declared` is correct: nothing in this chapter turns text into vectors.

## The commands in this chapter

Run these from the repository root, in this order, after `bootstrap.sh` has finished.

| Purpose | Command | What you should see |
| :---- | :---- | :---- |
| Deploy the application package | `vespa deploy --wait 300 chapters/ch02/app` | `Success: Deployed 'chapters/ch02/app' with session ID …`. Safe to repeat; an unchanged package changes nothing. |
| Run the ten checks against the reference | `.venv/bin/python chapters/ch02/smoke_test.py --build builds/esci-us-hard-book-s42-kdd-v4 --limit 2000` | `10/10 checks passed`, then `the same 10 checks, all agreeing` |
| Feed the sample and record the run | `.venv/bin/python shared/tools/feed.py builds/esci-us-hard-book-s42-kdd-v4/products.jsonl --limit 2000` | `2,000 ok, 0 failed, 0 retried in …` |
| Send the chapter's query | `.venv/bin/python shared/tools/query.py --query "running shoes" --hits 5` | `15 matched, showing 5`, then five titles — none of them shoes. Section 2.8 of the book explains why. |
| The same, with a trace | `.venv/bin/python shared/tools/query.py --query "running shoes" --hits 5 --trace 3` | The same five results, followed by Vespa's trace of the query |

## Comparing your run with the book's

`expected/` holds the output of every command the chapter quotes, exactly as it ran when the book was written. Two kinds of number are in there, and they behave differently:

- **Quality numbers** — the ten checks, the 15 matches, the five titles and their scores. Given the same build and the same 2,000 documents, you should get exactly these. If you do not, something about what you ran is different; start with `docs/pins.md`.  
- **Cost numbers** — timings and documents per second. These describe one machine on one day (an Apple M4 Pro, Docker with 4 CPUs / 10 GB). Yours will differ, and that is expected.

The smoke test already compares itself with `expected/smoke.json`. To regenerate the other files from your own run, use these forms instead; each one overwrites the file it names, and `git diff chapters/ch02/expected/` then shows the difference:

```
.venv/bin/python shared/tools/feed.py builds/esci-us-hard-book-s42-kdd-v4/products.jsonl --limit 2000 --out chapters/ch02/expected/feed.json --label "ch02 2,000-document feed" > chapters/ch02/expected/feed.block.md
.venv/bin/python chapters/ch02/smoke_test.py --build builds/esci-us-hard-book-s42-kdd-v4 --limit 2000 --block smoke-output > chapters/ch02/expected/smoke-output.block.md
.venv/bin/python shared/tools/query.py --query "running shoes" --hits 5 --block query > chapters/ch02/expected/query-2000.block.md
```

## What is in this directory

```
chapters/ch02/
├── app/                  the application package Vespa deploys
│   ├── services.xml      the container and content nodes
│   └── schemas/
│       └── product.sd    what a product document is
├── chapter.toml          what bootstrap.sh needs for this chapter
├── smoke_test.py         the ten checks
└── expected/             the book's reference output
```

The feeder and the query tool are shared by every chapter and live in `shared/tools/`.

## If something goes wrong

**`Python 3.11 not found`** — install Python 3.11 and make sure `python3.11` is on your `PATH`, then run the command again.

**The container fails to start because a port is already allocated** — something else on your machine is using port 8080 or 19071\. Stop it, or stop the other Vespa container, then rerun with `--fresh`.

**`vespa-book-fable runs …, not vespaengine/vespa:8.751.13`** — an older container from a different image is still around. Rerun with `--fresh` to replace it.

**`FAIL container responds`** — the application is not deployed or not up yet. Run `vespa deploy --wait 300 chapters/ch02/app` and try the checks again.

**A check fails, or the smoke test prints `DIFFERS`** — the line names the check. The table in Section 2.6 of the book says what each check would catch.

**The deploy or feed fails, or Vespa stops responding partway** — check that Docker really has 4 CPUs and 10 GB. Every run behind the book used exactly that, so too little memory is the first thing to rule out.

**The first run is very slow** — it is limited by your network, not your machine. Once the dataset is cached, it does not need downloading again.

**The PASS block appears twice in your terminal** — it does not; the progress lines and the final block go to different output streams, and a terminal shows both. Redirect the output to a file and you will see it once.

## Next

When you are ready for Chapter 3:

```
./bootstrap.sh ch03
```

It keeps everything this chapter built and feeds the rest of the catalogue.