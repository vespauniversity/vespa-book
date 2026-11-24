# Presenter's walkthrough: the agent demo

For a talk or a webinar: from an empty machine to the page, then what to click and what to say, step by step. `README.md` beside this file is the setup-and-test reference; this guide repeats its commands so a presenter can follow one document.

The story the demo tells: **the agent is given a description of the search engine (the Skill) and works out the rest on its own** — which fields to search, which ranking to use, how to exclude a brand, what to do when a search comes back thin. The audience watches every statement it writes, as it writes it.

Everything below is run from the repository's root directory.

---

## Part 1. Before the day

Do all of this at least a day ahead, on the machine you will present from.

### 1.1 The machine

- **A container runtime** that speaks the Docker Engine API — Docker Engine, Docker Desktop, Rancher Desktop or Podman — with **4 CPUs and 10 GB** of memory given to it. Check its settings; the defaults are often smaller.
- **Python 3.11** and **git**.
- **The Vespa CLI** (`vespa`), which the setup script uses to deploy the application: see [the Vespa CLI documentation](https://docs.vespa.ai/en/vespa-cli.html).
- **About 4 GB of free disk** (the dataset cache, the models, the catalogue build, the Python environment and the Vespa image).
- **An internet connection** the first time, for the dataset, the container image and the models. On the day itself only the language-model planner needs the network (it calls the model's API).
- **For the language-model planner only: an OpenAI API key.** The fixed-recipe planner needs no key.

### 1.2 The code

```
git clone <the repository's URL>
cd <the repository's directory>
```

Every command from here on is run from that directory.

### 1.3 The engine and the catalogue

```
./bootstrap.sh ch10 --tests
```

The script brings the machine to the state the demo needs and skips every part that is already right:

1. **the venv**: `.venv` with Python 3.11 and the pinned packages (`--tests` adds pytest, for 1.6);
2. **the catalogue build**: on a machine without one, it downloads the product dataset from Hugging Face and builds the catalogue under `builds/` (a one-time fetch);
3. **the container**: starts the search engine (Vespa) on `http://localhost:8080`;
4. **the application**: deploys the schema, the rank profiles and the embedding models;
5. **the feed**: feeds the 101,341 products of the catalogue with their vectors and their sellers.

The first time it takes from half an hour to well over an hour, almost all of it the feed — run it the day before; run again, it takes seconds. If it refuses the container you have, it says why; `./bootstrap.sh ch10 --fresh` throws the venv and the container away and starts over.

The page's Skill, the description of the catalogue the language model is given on the query-language surface, is a file the kit carries, `chapters/ch10/demo/skill.md`, generated from the application package the same way as the chapter's own description; nothing to make. The kit's README (*Start the page*) has the command that regenerates it.

Then make the question set (seconds, no container needed):

```
.venv/bin/python chapters/ch10/build_multihop_set.py --split test --threshold 3 > /dev/null
```

It writes `multihop_test.jsonl` into the catalogue build: 872 questions, each with its anchor product, the products people judged acceptable alternatives (the answer key) and the pool of candidate products the agent searches.

### 1.4 The model key

Either put one line in a file named `.env` in the repository's root (git ignores it):

```
OPENAI_API_KEY=<your key>
```

or export `OPENAI_API_KEY` in the shell before starting the server, or, with neither, paste the key into the page's key box. A key in the box is kept in the server's memory for that session only: it is not written to disk, not logged and not shown again, and it is gone when the server stops. A key from the environment or `.env` is used first; the box then does not appear.

For a live audience, prefer `.env`: the key box is on the screen everyone is watching, and a restart of the server forgets a pasted key.

**Cost.** Only the `llm` planner costs money. Every turn is one request to the model's API, and a question takes up to four turns, so a run costs a handful of small requests. A rehearsal plus the talk is a few dozen runs at most. Check that the account has credit before the day.

### 1.5 Check the setup

```
.venv/bin/python chapters/ch10/demo/serve.py --check
```

It prints one line for each of the engine, the catalogue build, the question set and the key, with the fix for anything missing. On a machine that is ready it reads:

```
ok    Vespa <version> at http://localhost:8080: 101,341 products
ok    catalogue build: present
ok    question set: present
ok    model key: from .env (model <model name>)
ready
```

and exits with 0. Any `FAIL` line means the page could not run a question (the engine down, no products in it, no catalogue build, no question set); its `fix:` line says what to run. A `warn` on the key means only the fixed-recipe planner will work.

### 1.6 Test the kit (optional)

```
.venv/bin/python -m pytest tests/test_ch10_demo.py -q
```

No test calls the model's API, and none uses port 8765. A test whose requirement is missing is skipped and says why.

### 1.7 Start the page and smoke-test it

```
.venv/bin/python chapters/ch10/demo/serve.py
```

Then open `http://localhost:8765`. Stop it with Ctrl-C. `--port` serves on another port; `--endpoint` points it at another engine.

The smoke test, two runs:

1. **Planner `rules`**, surface `tools`, shape *one alternative product*, k = 3, hand over *nothing*, question **184** (the Thermos bottle). Run. Three steps appear within a second: a search for the anchor, a search for its kind of product without its brand, the answer. No key, no cost.
2. **Planner `llm`**, surface `query language`, same settings, question **1230** (the Cuisinart skillet). Run. Steps appear every few seconds as the model decides; the run ends with an answer and a judgement line. This proves the key works and the account has credit.

### 1.8 Keep a recording for the fallback

After a good `llm` run you would like to show, keep it before you stop the server, in one or both of these ways:

- **a screenshot or a saved copy of the page** (the browser's *Save page as*), scrolled to show the steps and the answer;
- **the run's raw record**: run ids count from 1 each time the server starts, so the first run after a start is

  ```
  curl -s http://localhost:8765/api/runs/1 > recorded-run.json
  ```

  It holds every step the page showed: the statements, the results, the answer and the judgement.

### 1.9 The morning of

So that the first live run is not the cold one:

1. **Start the container runtime**, then `./bootstrap.sh ch10` (seconds when everything is there; it starts the engine if it is not running).
2. `.venv/bin/python chapters/ch10/demo/serve.py --check` — every line `ok`, then `ready`.
3. **Start the page** and open `http://localhost:8765` in the browser you will present from; zoom the browser so the steps are readable from the back of the room.
4. **Send one query**: one `rules` run on question 184 warms the engine and the embedding model.
5. **One `llm` run** on the question you will open with, to see the key is loaded and the API answers. Leave the page on that question, with the output cleared by a reload.
6. Silence notifications; keep a terminal with the server's output on a second screen if you have one.

---

## Part 2. The run of show (10–15 minutes)

### 2.1 Open the page (1 minute)

Point at the **Setup** block: every line green — the engine with its 101,341 products, the catalogue build, the question set, the model key.

> "This is a product catalogue of about a hundred thousand real Amazon products, in Vespa on this laptop. The questions come from real shoppers' searches, and each one has an answer key: the products people judged acceptable."

### 2.2 Show the Skill (2–3 minutes)

Select **llm** and **query language**; the **Skill** panel opens by itself (or click *Skill — what the model is given on the query surface*).

> "This is everything the agent is told about the engine. Nobody wrote it by hand: it is generated from the application package that is deployed right now."

(What the panel shows is `chapters/ch10/demo/skill.md`, the demo kit's copy, generated by `schema_skill.py` the same way as the chapter's own description but with no chapter labels on it; the kit's README has the command that regenerates it.)

Walk down it briefly:

- **Fields**: each field's type and how it can be matched — searchable text, a filterable attribute, a vector with its nearest-neighbour index.
- **Fieldset `default`**: what a plain keyword search covers.
- **Rank profiles**: `bm25_tuned` (keywords), `semantic` (vectors), `hybrid_rrf` (both, merged), with what each needs.
- **Example statements**: real queries in Vespa's query language (YQL), with the request parameters each needs.
- The one paragraph under *What this catalogue's own measurements say* is the only part the owner adds: which ranking measured best on this catalogue.

> "There is no translation layer and no tool per feature. The agent gets this page and writes the engine's own query language."

Then open **Prompt — what the model receives** below it: the Skill sits inside the instructions, with the reply format and the tools around it, and under them the shape of each turn's message (the question, the evidence so far, the turns left).

> "This is everything the model is told."

### 2.3 The question (30 seconds)

Pick **1230: Cuisinart Chef's Classic Nonstick Hard-Anodized 10-Inch Open Skillet** from the Question list (it opens with the featured questions: 1230, the dress 16911, 184, 230, then a second dress, 8139). For a clothing question use **8139** (GOBLES tank dress): in rehearsal it was answered from the key on both surfaces, twice. **16911** (Alex Evenings tea-length dress) is the harder one — its key holds 18 of a pool of 38, and the agent missed it on the query surface in every rehearsal (it found alternatives, not ones in the key) and hit it on the tools surface once; in a later run of this walkthrough it was answered from the key on the query surface twice. It may go either way, so do not open with it and do not count on it for a miss: to show a miss and how the judgement line reads, run the fixed recipe on 1230 (2.7).

> "The task: find an acceptable alternative to this skillet, made by another brand. The agent searches a pool of candidates — the products people judged for this search — so every answer it gives can be checked against the answer key."

### 2.4 The agent writes its own queries (4–5 minutes)

Settings: planner **llm**, surface **query language**, shape **one alternative product**, k **3**, hand over **nothing**. Click **Run**.

Narrate each step as it appears (a few seconds apart; the state line reads `running (planner)` while the model thinks and `running (engine)` while Vespa answers):

- **"the model wrote"** — the statement the agent composed. Point at what it took from the Skill: the ranking it chose (in the rehearsals, `hybrid_rrf`, the one the Skill says measured best), keyword and vector search in one request, and `!(brand contains "Cuisinart")` to exclude the anchor's brand.
- **"sent to the engine"** — the same statement with `id in (...)` added: the candidate pool, added by the loop. The agent never writes it and cannot remove it.
- **The top results** with their brands, the engine time (milliseconds) and the model time (seconds).
- **A correction, if it makes one**: in a rehearsal the model saw a 12-inch pan and a 5-quart pan in the first results and wrote a second statement requiring "10" in the title. Say so when it happens: "it read its own results and narrowed the search." It may equally answer from the first search.
- **The answer**: a product id, and below it the **judgement line** — "The answer is in the answer key" (green) or "is not" (red), with the size of the answer key.

> "Nobody told it which ranking to use or how to filter a brand. It read the Skill and the results, and decided."

### 2.5 The same question with tools instead (2–3 minutes)

Switch **surface** to **tools**, keep everything else, **Run**.

> "Now the agent does not see the engine at all. It gets three tools — search, lookup, group — each with a few arguments, and no Skill."

The steps now show tool calls (`search` with a query, a `where` and a number of hits) instead of statements. Point out what is gone: no ranking choice, no vector parameters, no query language — the tools decide those for it. Both surfaces can answer this question; the difference is in how much of the engine the agent can reach and how much it has to know.

### 2.6 Optional: the brands shape (2 minutes)

Shape **brands and counts**, surface **tools** or **query language**, question **184** (the Thermos bottle). The agent hands back a table of other brands and how many of their products it found. The fixed recipe gets it with one grouping request, a call that counts by brand instead of reading every product; watch whether the model does the same. The judgement line shows the share of the answer key's brands it named and how many of its brands are right.

### 2.7 For contrast: the fixed recipe (1 minute, optional)

Planner **rules**, question **1230**, **Run**. It finishes in well under a second: search for the anchor to read its brand, search for the words of its title that say what kind of product it is, without that brand, and take the top result. In the rehearsals it picked a 12-inch pan with a lid and missed the answer key — a recipe cannot read its results and change course. On question **184** (Thermos) the same recipe hits. No key, no cost, and the same answer every time.

### 2.8 What to say about cost and variance

- **Cost**: each model turn is one paid API request; this question has taken two to four turns. The engine's part is tens of milliseconds a search; the time you see is almost all the model's.
- **Variance**: the model's choices vary from run to run — another ranking, another wording, one search or two, sometimes a different answer. If the audience asks to run it again, do; the variation is part of the story.

### 2.9 What not to claim

The page says it under every answer: **one question, one time, nothing measured or saved.** A green line on one question is not a success rate, and one run on tools against one on the query language says nothing about which surface is better. Do not say the agent "always" picks a ranking or "usually" succeeds on the strength of what the page shows.

---

## Part 3. If something goes wrong live

### 3.1 Fallbacks, in order

1. **Switch to the `rules` planner.** No key, no network to the model, no cost, and deterministic: question 184 gives the same correct answer every time. It still shows every step, its results and the judgement.
2. **Try another question.** If the model takes an odd path on 1230, go to 184 (Thermos bottle) or 230 (Sony in-ear earbuds with mic). In the rehearsals the fixed recipe missed on 230, so it is a fair question to hand the model.
3. **Show the recording** from 1.8: the screenshot, the saved page, or `recorded-run.json` opened in the browser. Say plainly that it is a recorded run.
4. **For a setup fault** (before the talk, or if you have a minute), the README's list:
   - **Port 8765 in use**: `serve.py --port 8766`, then open that port.
   - **The engine does not answer** (`--check` says `FAIL Vespa`, or the page's first line is red): run `./bootstrap.sh ch10` again; it starts what is not running and feeds what is missing.
   - **No question set**: the `build_multihop_set.py` command of 1.3.
   - **No key**: 1.4; the fixed-recipe planner works without one.
   - **The key is rejected**: the step shows the model API's own message as it came back (an invalid key, no credit, a rate limit); fix it on the provider's side, or paste another key after restarting the server.

### 3.2 What the failures look like on screen

- **No key**: the Setup block's last line is red ("model key: none") and a key box appears; Run with the `llm` planner shows, in red under the Run button, "the llm planner needs a model key". Switch to `rules`, or paste the key.
- **The engine not answering**: the Setup block's first line is red ("no Vespa answers at http://localhost:8080"); Run shows "no Vespa at http://localhost:8080; start the container first". The container runtime has usually stopped or the laptop slept; start it, run `./bootstrap.sh ch10`, reload the page.
- **The key rejected or the API out of credit**: a step named `error` appears with the model API's message. Switch to `rules`.
- **A second Run while one is going**: the Run button is disabled during a run; a second run from another tab is refused with "another run is going; wait for it to finish". Wait for the first to end.
- **A step says `empty`, `over_constrained` or `malformed`**: not a fault. The agent's search came back with nothing usable — too strict a filter, or a statement the engine could not parse — and the planner has to deal with it. Narrate it: "it wrote a query that found nothing; watch what it does next."
- **The page says "the demo server does not answer"**: the server in the terminal has stopped. Start it again (1.7); a pasted key has to be pasted again.

---

## Part 4. Cue card

**Before:** runtime up → `./bootstrap.sh ch10` → `serve.py --check` says `ready` → `serve.py` → `http://localhost:8765` → one `rules` run on 184 → one `llm` run on 1230 → reload.

| # | Click | Say |
|---|---|---|
| 1 | Point at Setup, all green | "A hundred thousand real products in Vespa on this laptop; real shoppers' questions with an answer key." |
| 2 | llm + query language → Skill opens | "Everything the agent knows about the engine — generated from the deployed package, not written by hand." |
| 3 | Scroll: fields, rank profiles, examples | "Fields and how they match, the rankings, real example queries." |
| 4 | Question 1230 (Cuisinart skillet), k 3, hand over nothing | "Find an alternative from another brand." |
| 5 | Run; point at "the model wrote" | "It chose the ranking and wrote the brand filter itself." |
| 6 | Point at "sent to the engine" | "The candidate pool is added by the loop; the agent cannot remove it." |
| 7 | A second statement, if any | "It read its results and narrowed the search." |
| 8 | Answer + judgement line | "Checked against what people judged acceptable." |
| 9 | Surface tools, Run | "Same question with three tools and no Skill: it no longer sees the engine." |
| 10 | (optional) Shape brands, question 184 | "The fixed recipe counts by brand in one grouping request; watch what the model does with the same tool." |
| 11 | (optional) Planner rules, 1230 | "A fixed recipe cannot change course." |
| 12 | Close | "One question, one time, nothing measured. Choices vary run to run; each model turn costs one API call." |

**If it breaks:** `rules` planner → question 184 or 230 → the recording → `./bootstrap.sh ch10`.
