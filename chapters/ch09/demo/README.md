# Agent demo: alternatives in a product catalogue

A small local web page for demonstrating a search agent. The agent gets a question from the question set: find a product that is an acceptable alternative to a given one (the anchor) but made by another brand, or list the other brands that sell such alternatives. It answers by searching the catalogue, step by step. On the page you pick the question, the planner and what the planner is shown, run it, and watch each step as it happens.

One question, one time, nothing measured or saved. The model's choices vary from run to run, and nothing the page shows is a measurement.

Presenting it? `WALKTHROUGH.md` beside this file takes a presenter from an empty machine to the page, then through the run of show, the fallbacks and a cue card.

Everything below is run from the repository's root directory.

## 1. What you need

- **A container runtime** that speaks the Docker Engine API — Docker Engine, Docker Desktop, Rancher Desktop or Podman — with **4 CPUs and 10 GB** of memory given to it.
- **Python 3.11** on the machine (the setup script builds the project's `.venv` from it) and `git`.
- **The Vespa CLI** (`vespa`), which the setup script uses to deploy the application: see [the Vespa CLI documentation](https://docs.vespa.ai/en/vespa-cli.html).
- **An internet connection** the first time, for the dataset, the container image and the models.
- **For the language-model planner only: an OpenAI API key.** The fixed-recipe planner needs no key.

## 2. Set up the engine and the catalogue

```
./bootstrap.sh ch10 --tests
```

The script brings the machine to the state the demo needs and skips every part that is already right:

1. **the venv**: `.venv` with Python 3.11 and the pinned packages (`--tests` adds pytest, for step 6);
2. **the catalogue build**: on a machine without one, it downloads the product dataset from Hugging Face and builds the catalogue under `builds/`;
3. **the container**: starts the search engine (Vespa) on `http://localhost:8080`;
4. **the application**: deploys the schema, the rank profiles and the embedding models;
5. **the feed**: feeds the 101,341 products of the catalogue with their vectors and their sellers.

The first time it takes about 35 minutes, most of it the feed; run again, it takes seconds. If it refuses the container you have, it says why; `./bootstrap.sh ch10 --fresh` throws the venv and the container away and starts over.

Then make the question set (seconds, no container needed):

```
.venv/bin/python chapters/ch10/build_multihop_set.py --split test --threshold 3 > /dev/null
```

It writes `multihop_test.jsonl` into the catalogue build: 872 questions, each with its anchor product, the products people judged acceptable alternatives (the answer key) and the pool of candidate products the agent searches.

## 3. The model key (language-model planner only)

Either put one line in a file named `.env` in the repository's root (git ignores it):

```
OPENAI_API_KEY=<your key>
```

or export `OPENAI_API_KEY` in the shell before starting the server, or, with neither, paste the key into the page's key box. A key in the box is kept in the server's memory for that session only: it is not written to disk, not logged and not shown again, and it is gone when the server stops. A key from the environment or `.env` is used first; the box then does not appear.

The key is sent only to the model's API. Every turn of the language-model planner is one request to that API and costs money; a question takes up to four turns.

## 4. Check the setup

```
.venv/bin/python chapters/ch10/demo/serve.py --check
```

It prints one line for each of the engine, the catalogue build, the question set and the key, with the fix for anything missing, and ends with `ready` (exit code 0). It exits with 1 when the page could not run a question: the engine down, no products in it, no catalogue build, no question set. A missing key is only a warning, since the fixed-recipe planner needs none.

## 5. Start the page

```
.venv/bin/python chapters/ch10/demo/serve.py
```

Then open `http://localhost:8765`. Stop it with Ctrl-C. `--port` serves on another port; `--endpoint` points it at another engine.

At the top, the setup panel shows the same lines as `--check` (and the key box when no key is found). Then:

- **Question**: the question set, each question named by its anchor product and the size of its candidate pool. The list opens with a few questions a presenter reaches for (the skillet 1230, a dress 16911, the Thermos bottle 184, the Sony earbuds 230, a second dress 8139 — `FEATURED` in `serve.py`); the rest follow in the set's own order.
- **Planner**: `rules`, a fixed recipe (search for the anchor, read its brand, then search for its kind of product without that brand and take the top result), or `llm`, a language model choosing each step.
- **Surface**: what the language model is given to search with: three tools (search, lookup, group), or the engine's own query language, which it writes itself from a description of the catalogue (`chapters/ch10/demo/skill.md`). The query language is for the language-model planner only.
- **Shape**: one alternative product, or a table of other brands and their counts.
- **k**: how many results each search returns, 3 or 20.
- **Hand over**: nothing; the anchor's brand and the words that say what kind of product it is; or the answer key's products themselves, so that a miss is the planner's choice and not the search's.

Each step shows what was asked (the tool and its arguments, or the statement the model wrote and the statement sent after the candidate pool was added), its status, the top results with their titles, and the time. The end shows the answer and whether it is in the answer key; for the brands shape, the share of the answer key's brands it named. One run at a time: a second Run while one is going is refused until the first ends.

Below the run settings, the **Skill** panel (closed at first; it opens by itself when you choose the query-language surface) shows the description of the catalogue the language model is given on that surface, the same file the server sends, with its path. It is generated from the deployed application package by `chapters/ch10/schema_skill.py`; nothing in it is written by hand except the one paragraph of the catalogue's own measurements, which the owner adds. The server answers it at `/api/skill`.

The file is the demo kit's own copy, `chapters/ch10/demo/skill.md`, generated the same way as the chapter's own description (`chapters/ch10/expected/skill.md`, which the chapter's runs were shown and which stays as it is), with two differences: `--statement-labels none`, so the example statements carry no label saying which chapter each is from, and a measurements paragraph that states the results as facts about this catalogue. After a change to the application package, regenerate it with:

```
.venv/bin/python chapters/ch10/schema_skill.py --app chapters/ch10/app --profiles hybrid_rrf,bm25_tuned,semantic --statement-labels none --note 'Measured against the human relevance labels of this catalogue: `hybrid_rrf`, the keyword and vector rankings merged by rank, ranked better than `bm25_tuned` (keyword only) and than `semantic` (the vector side alone), and further down its list reaches more labelled products than `bm25_tuned` and as many as `semantic`; among keyword-only rankings `bm25_tuned` ranked best.' --out chapters/ch10/demo/skill.md
```

`--skill PATH` serves another description instead.

Under it, the **Prompt** panel (closed at first) shows what the model receives on the surface chosen, and reloads when the surface changes: the instructions text exactly as the language-model planner sends it — its tools, and on the query surface the Skill above set into it — then the template of the rest of each turn's message (the question, the evidence so far, the turns left), with each placeholder explained and the question's wording for each shape. The server builds it from the planner's own text and code in `chapters/ch10/agent_loop.py`, without a key or a model call, and answers it at `/api/prompt?surface=tools|query`.

## 6. Test the kit

```
.venv/bin/python -m pytest tests/test_ch10_demo.py -q
```

Needs pytest (`./bootstrap.sh ch10 --tests`). No test calls the model's API, and none uses port 8765: the tests start their own server on a free port.

- **Need nothing running**: the page is served with no outside resource and carries the Skill and Prompt panels; `/api/skill` answers the file a query-surface run sends; `/api/prompt` answers, for both surfaces, the text the planner builds; the status with the engine down; a key typed into the box is reported as `session` and appears in no answer and no output; the box is refused when a key is on file; `--check` exits 1 with the engine down.
- **Need the catalogue build and the question set**: the question list is the whole set; bad requests are refused.
- **Need the engine on `localhost:8080` as well**: the status with the engine up; one fixed-recipe run completes with every field the page reads; a second run while one is going is refused; `--check` exits 0.

A test whose requirement is missing is skipped and says why.

## If it does not work

- **Port 8765 in use**: `serve.py --port 8766`, then open that port.
- **The engine does not answer** (`--check` says `FAIL Vespa`, or the page's first line is red): run `./bootstrap.sh ch10` again; it starts what is not running and feeds what is missing.
- **No question set**: the `build_multihop_set.py` command of step 2.
- **No key**: step 3; the fixed-recipe planner works without one.
- **The key is rejected**: the step shows the model API's own message as it came back (an invalid key, no credit, a rate limit); fix it on the provider's side, or paste another key after restarting the server.
- **A step says `empty`, `over_constrained` or `malformed`**: that is the agent's search coming back with nothing usable, which the planner then has to deal with; it is part of what the demo shows, not a fault of the kit.
