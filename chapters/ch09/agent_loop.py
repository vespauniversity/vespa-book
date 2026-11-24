"""A small agent loop over the search tools, with two interchangeable planners.

The loop is the same whoever decides what to do next:

    planner.next_action(question, evidence) -> an action
    the loop runs the action (a search, a lookup, a grouping) and appends what
    came back to the evidence
    ... until the planner gives an answer or runs out of steps

Two planners:

    rules   A fixed recipe. The first hop searches for the anchor product by its
            title and reads the brand off the top hit; the second hop searches (or
            groups) for the product's category words with that brand
            excluded; the answer is the top result. Deterministic, so a run
            can be repeated exactly. It makes no reasoning error - what it
            returns is whatever the search ranks first - so it measures the
            retrieval, not a consumer's judgement.
    llm     A language model (`MODEL`, or `--model`), called directly through
            the provider's chat-completions API, one request per turn. It is
            shown the tools, the evidence so far and the question, and replies
            with one JSON action; the API's structured output guides the reply
            toward the action's shape (`ACTION_SCHEMA`). It can be misled by what
            it is shown, so it is the planner whose failures say something
            about the evidence. The model accepts only its default sampling
            temperature, so none is sent and a run is one record, not
            something to average.

Two surfaces for the model planner (`--surface`):

    tools   The three callables of `tools_schema` (search, lookup, group): the
            model fills in words and a condition, the tool writes the query.
    query   The model writes the engine's query language itself. It is shown
            a description of the catalogue generated from the deployed schema
            (`schema_skill.py`, or a saved copy given with `--skill`), and the
            `query` and `lookup` tools only; every statement it writes goes
            through the wrap that ANDs the question's pool and the user's
            seller boundary onto its `where`. The rules planner has no query
            surface: its recipe is written against the tools.

`--oracle` hands the planner the anchor's brand and category words up front
instead of making it find them. Comparing a run with and without it separates
"the evidence was not retrieved" from "the evidence was there and was not
used".

`--oracle-products` hands it more: every product of the question's oracle,
sorted by id, each with the id, title and brand a search result shows (read
from the build's products), and not the anchor's brand or category words.
That is what a perfect retrieval would have returned, so a miss with it is
the planner's pick, not the search's ranking. The model is told in one
sentence what the list is and that it may answer from it or search; the
rules planner answers with the first product of the list and sends no
request. The two flags are not taken together. Each line records
`oracle_mode` and, when it is on, `oracle_kind`: `facts` (`--oracle`) or
`products` (`--oracle-products`).

The number of results per search is fixed at `--k` for both planners, whatever
the planner asks for, because k is the thing being varied.

Searches and groupings are limited to the question's `pool`: the products the
query has a human judgement for. A product nobody judged is then never
returned, so it can never be scored as a miss for want of a label. The pool
contains the anchor, so the first hop finds it there too.

`--tenant-from-anchor` runs every question as a user of one seller's
storefront: the seller (`tenant_id`) of the question's anchor product, read
from the build's `tenants.jsonl`, is passed to every search, grouping and
statement the way the pool is - from the user's identity, never from the
planner - so a result outside that seller is withheld and the tool answers
`filtered`. Each log line records the `tenant` it ran under (`null` without
the flag).

`--tenant-pair` widens that boundary to two sellers, the way a staff account
of chapter 8 has an allowed set rather than one seller: the anchor's seller
plus one seller of the question's oracle - the seller with the most products
in the oracle, ties broken by seller name - chosen from the build alone, so
the pair is the same on every run. Under one seller every question's answer
is outside the boundary (the oracle is another brand by construction, and the
seller is the brand), so the run can show only how a planner reacts to
`filtered`; under the pair the answer is reachable and the boundary can still
withhold most of the oracle. The pair goes where the single seller goes - to
every search, grouping and statement, never to the planner - and the line
records it as a list (`tenant: ["<anchor's seller>", "<oracle seller>"]`);
`tenant_rule` on the line says which rule made it (`anchor` or `pair`).

Scoring. For the question shape `alternative` a run succeeds when the answer
is in the oracle set. For `brands` the planner hands back a table of
brand -> count, and the run is scored by brand coverage: `brand_recall` is
the share of the oracle's brands the table names, `brand_precision` the share
of the table's brands the oracle names. A `brands` run succeeds when
`brand_recall` is 1.0. Counts are not compared.

A request to the model that comes back empty, times out, cannot connect, or
is answered with HTTP 429 or a 5xx status is sent once more, the same request,
after a few seconds; the step records `retries` (0 or 1), the reason for the
second request (`retry_reason`), the API's `finish_reason` and, when it gives
one, its `refusal`. A request that fails twice is the planner's error, its
reason saying which (`empty reply twice`, `timeout twice`, ...).

One line per question goes to `--out` (JSON lines), written as each question
completes. For the model planner, if `--out` already exists, the questions it
holds are skipped and the rest appended, so a run that stopped is finished by
the same command; a file written by a different run (another planner,
surface, shape, k, oracle mode, seller boundary, model, build, split or
description) is refused. The rules planner, which takes
seconds and gives the same lines every time, writes `--out` afresh.

The model key is read from the OPENAI_API_KEY environment variable, or from
the repository's `.env` file, and is sent to the model's API in the
Authorization header of each request, and nowhere else. It is never printed
or written to a log. Searches, lookups and groupings go to the Vespa endpoint
(`--endpoint`), which needs no key.

Usage:
    python chapters/ch10/agent_loop.py --split test --planner rules \\
        --shape alternative --k 3 --limit 5 --out rules.jsonl
    set -a; source .env; set +a
    python chapters/ch10/agent_loop.py --split test --planner llm \\
        --shape alternative --k 3 --limit 5 --out llm.jsonl
    python chapters/ch10/agent_loop.py --split test --planner llm \\
        --surface query --skill chapters/ch10/expected/skill.md \\
        --shape alternative --k 3 --limit 5 --out llm-query.jsonl
    python chapters/ch10/agent_loop.py --split test --from llm.jsonl \\
        --block trajectory
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Protocol

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared" / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import builds       # noqa: E402
import deployed     # noqa: E402
from query import Vespa   # noqa: E402

import schema_skill   # noqa: E402
import tools_schema   # noqa: E402

APP_DIR = Path(__file__).resolve().parent / "app"
SHAPES = ("alternative", "brands")
SURFACES = {"tools": ("search", "lookup", "group"), "query": ("query", "lookup")}
MAX_STEPS = 4
CATEGORY_WORDS = 4
MAX_TOKENS = 800
# Seconds to wait before a request that failed in transport is sent once more.
RETRY_WAIT_S = 5
KEY_NAME = "OPENAI_API_KEY"
# The model the planner asks, and where; `--model` overrides the name.
MODEL = "gpt-6-sol"
API_URL = "https://api.openai.com/v1/chat/completions"

# Words that describe a listing rather than what kind of thing it is.
STOPWORDS = frozenset("""
a an and or the of for with without in on at by to from as is are be
new pack packs set sets size sizes count piece pieces inch inches oz ml
pcs pc lot bundle women womens men mens kids kid boys girls unisex adult
black white red blue green grey gray pink brown yellow orange purple silver
gold
""".split())

# The action a model is asked to produce; sent with every request as the
# API's structured-output schema, so the reply is one object of this shape.
ACTION_SCHEMA = {
    "type": "object",
    "properties": {"tool": {"type": "string"},
                   "args": {"type": "object"},
                   "final_answer": {"type": "string"}},
    "required": ["tool"],
}

SYSTEM_TEXT = """\
You answer product-search questions by calling tools over a catalogue. You
cannot see the catalogue except through the tools.

Each turn, reply with ONE JSON object and nothing else:
  {"tool": "<search|lookup|group>", "args": {...}}   to call a tool, or
  {"tool": "final", "final_answer": "<answer>"}      when you can answer.

Tools:
{tools}

The condition `where` uses this form to exclude a brand:
  !(brand contains "the brand")
Searches and groupings look only at a set of candidate products chosen for
this question; you do not see the set.
Every result you have seen so far is in the evidence. Answer only from it."""

SYSTEM_TEXT_QUERY = """\
You answer product-search questions by writing statements in the search
engine's own query language (YQL) against a catalogue, through the tools
below. You cannot see the catalogue except through them.

Each turn, reply with ONE JSON object and nothing else:
  {"tool": "<query|lookup>", "args": {...}}   to call a tool, or
  {"tool": "final", "final_answer": "<answer>"}      when you can answer.

Tools:
{tools}

The catalogue, as deployed:
{skill}

To exclude a brand in a where clause:
  !(brand contains "the brand")
Every statement looks only at a set of candidate products chosen for this
question; that condition is added to your where for you, and you do not see
the set. Do not write it.
Every result you have seen so far is in the evidence. Answer only from it."""

# Added to either system text when the evidence opens with the oracle's
# products (`--oracle-products`); the other runs' prompts are unchanged.
GIVEN_PRODUCTS_TEXT = """\
The evidence opens with "given": the products a perfect search would have
returned for this question - each judged an acceptable alternative, none made
by the anchor's brand. They count as results you have seen: you may answer
with one of their ids, or search first."""


class Planner(Protocol):
    name: str

    def next_action(self, question: dict, evidence: list[dict]) -> dict: ...


# ---------------------------------------------------------------- helpers

def category_words(title: str, brand: str, limit: int = CATEGORY_WORDS) -> list[str]:
    """What kind of thing a listing is: its title's words without the brand's
    words, the filler words and anything with a digit in it (model numbers)."""
    brand_tokens = set(re.findall(r"[a-z0-9]+", brand.lower()))
    out: list[str] = []
    for token in re.findall(r"[a-z0-9]+", title.lower()):
        if (len(token) < 3 or token in STOPWORDS or token in brand_tokens
                or any(c.isdigit() for c in token) or token in out):
            continue
        out.append(token)
        if len(out) == limit:
            break
    return out


def norm_brand(brand: str) -> str:
    return " ".join((brand or "").split()).lower()


def brand_table(groups: list[dict], exclude: str) -> dict[str, int]:
    """Grouping result -> {lower-cased brand: count}, without the anchor's brand
    and without the empty brand."""
    table: dict[str, int] = {}
    skip = norm_brand(exclude)
    for g in groups:
        b = norm_brand(g["value"])
        if b and b != skip:
            table[b] = table.get(b, 0) + int(g["count"])
    return dict(sorted(table.items()))


def load_api_key() -> str:
    """The key from the environment, else from the repository's `.env`.

    Only the one variable is read from the file; a line is `NAME=value`.
    """
    key = os.environ.get(KEY_NAME)
    if key:
        return key
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            name, sep, value = line.strip().partition("=")
            if sep and name.strip() == KEY_NAME:
                return value.strip().strip("'\"")
    raise SystemExit(f"no {KEY_NAME}: export it, or put {KEY_NAME}=... "
                     "in the repository's .env file")


def result_bytes(result: dict) -> int:
    """Size of the results a tool call puts in front of the planner: its
    products, its groups, its document, each one that is there. A statement
    that ends in a grouping returns products and groups, and the planner gets
    both. A refusal's message is not a result and is not counted."""
    payloads = [result[key] for key in ("hits", "groups", "document") if result.get(key)]
    return sum(len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
               for payload in payloads or [[]])


def top_ids(result: dict, n: int = 5) -> list[str]:
    if result.get("hits"):
        return [h["id"] for h in result["hits"][:n]]
    if result.get("groups"):
        return [f"{g['value']}:{g['count']}" for g in result["groups"][:n]]
    if result.get("document"):
        return [result["document"]["id"]]
    return []


def execute(client: Vespa, action: dict, k: int, pool: list[str] | None = None,
            surface: str = "tools", tenant: str | list[str] | None = None) -> dict:
    """Run one tool action. A search returns k results unless the planner's
    recipe itself sets `hits` on the action (the rules planner's first look-up
    wants exactly one); a model's `hits` argument is ignored. A tool that is
    not on the surface is no tool at all. `tenant` is the user's seller
    boundary, passed like the pool; `lookup` fetches by id and takes none."""
    tool, args = action.get("tool"), dict(action.get("args") or {})
    if tool not in SURFACES[surface]:
        return {"status": "malformed", "message": f"no such tool: {tool!r}",
                "hits": [], "count": 0, "requests": []}
    try:
        if tool == "query":
            return tools_schema.query(
                client, str(args["yql"]), ranking=args.get("ranking") or "hybrid_rrf",
                hits=k, params=args.get("params") or None, tenant=tenant, pool=pool)
        if tool == "search":
            return tools_schema.search(
                client, str(args["query"]), where=args.get("where") or None,
                ranking=args.get("ranking") or "hybrid_rrf",
                hits=int(action.get("hits", k)), tenant=tenant, pool=pool)
        if tool == "lookup":
            return tools_schema.lookup(client, str(args["product_id"]))
        if tool == "group":
            return tools_schema.group(
                client, str(args["query"]), where=args.get("where") or None,
                field=args.get("field") or "brand",
                max_groups=int(args.get("max_groups") or 20), tenant=tenant, pool=pool)
    except (KeyError, TypeError, ValueError) as exc:
        return {"status": "malformed", "message": f"bad arguments: {exc!r}",
                "hits": [], "count": 0, "requests": []}
    return {"status": "malformed", "message": f"no such tool: {tool!r}",
            "hits": [], "count": 0, "requests": []}


# ---------------------------------------------------------------- planners

class RulesPlanner:
    """Fixed two-hop recipe; see the module docstring."""
    name = "rules"

    def __init__(self, shape: str, k: int):
        self.shape = shape
        self.k = k

    @staticmethod
    def _given(evidence: list[dict]) -> dict | None:
        return next((e["given"] for e in evidence if "given" in e), None)

    def next_action(self, question: dict, evidence: list[dict]) -> dict:
        given = self._given(evidence)
        calls = [e for e in evidence if "tool" in e]
        if given is not None and "products" in given:
            # the oracle's products in hand: the first is an answer, no search needed
            first = given["products"][0]["id"] if given["products"] else ""
            return {"tool": "final", "final_answer": first}
        if given is None and not calls:
            return {"tool": "search", "hits": 1,
                    "args": {"query": question["anchor_title"]}}
        if given is not None:
            brand, words = given["anchor_brand"], given["category_words"]
        else:
            first = calls[0]
            if first["status"] != "ok":
                return {"tool": "final", "final_answer": ""}
            brand = first["hits"][0]["brand"]
            words = category_words(question["anchor_title"], brand)
        if not any(e["tool"] in ("search", "group") and e.get("hop") == 2
                   for e in calls):
            where = tools_schema.exclude_brand(brand) if brand else None
            tool = "group" if self.shape == "brands" else "search"
            return {"tool": tool, "hop": 2,
                    "args": {"query": " ".join(words), "where": where}}
        last = calls[-1]
        if last["status"] != "ok":
            return {"tool": "final", "final_answer": ""}
        if self.shape == "brands":
            return {"tool": "final",
                    "final_answer": json.dumps(brand_table(last["groups"], brand))}
        return {"tool": "final", "final_answer": last["hits"][0]["id"]}


class LlmPlanner:
    """Asks the model's API for one JSON action per step."""
    name = "llm"

    def __init__(self, shape: str, k: int, url: str, model: str,
                 max_steps: int = MAX_STEPS, max_tokens: int = MAX_TOKENS,
                 surface: str = "tools", skill: str | None = None):
        self.shape, self.k = shape, k
        self.url = url
        self.model = model
        self.max_steps, self.max_tokens = max_steps, max_tokens
        self.surface = surface
        if surface == "query" and not skill:
            raise ValueError("the query surface needs the catalogue description")
        self.skill = skill or ""
        self._key = load_api_key()
        self.session = requests.Session()

    # -- prompt --------------------------------------------------------
    def render_tools(self) -> str:
        shown = SURFACES[self.surface]
        return "\n".join(
            f"- {t['name']}: {t['description']}\n  parameters: "
            f"{json.dumps(t['parameters']['properties'], ensure_ascii=False)}"
            for t in tools_schema.TOOLS if t["name"] in shown)

    def question_text(self, question: dict) -> str:
        title = question["anchor_title"]
        if self.shape == "brands":
            return (f'Which brands, other than the brand that makes "{title}", '
                    "sell acceptable alternatives to it, and how many products "
                    "does each have among the results? final_answer must be a "
                    'JSON object as text mapping each lower-case brand name to '
                    'its count, e.g. {"acme": 3}.')
        return (f'Find one product that is an acceptable alternative to "{title}" '
                "but is not made by the same brand. final_answer must be the "
                "product id of a product you have seen in a result.")

    def build_prompt(self, question: dict, evidence: list[dict]) -> str:
        used = len([e for e in evidence if "tool" in e])
        left = self.max_steps - used
        must = (" This is your last turn: reply with the final answer now."
                if left <= 1 else "")
        system = (SYSTEM_TEXT_QUERY.replace("{skill}", self.skill.rstrip())
                  if self.surface == "query" else SYSTEM_TEXT)
        if any("products" in e.get("given", {}) for e in evidence):
            system += "\n" + GIVEN_PRODUCTS_TEXT
        return (system.replace("{tools}", self.render_tools())
                + f"\n\nQuestion: {self.question_text(question)}\n\n"
                + "Evidence so far (JSON):\n"
                + json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
                + f"\n\nTurns left: {left}.{must} Reply with one JSON action.")

    # -- call ----------------------------------------------------------
    def _post(self, body: dict) -> tuple[str | None, dict | None, float, dict]:
        """One request: (reply text, error, ms, what came back). One of the
        first two is None. The last holds `finish_reason`, `refusal` when the
        API gave one, and `failed`: why the request is worth sending again (an
        empty reply, a timeout, a connection error, HTTP 429 or 5xx), else
        absent."""
        started = time.perf_counter()
        try:
            r = self.session.post(self.url, json=body,
                                  headers={"Authorization": f"Bearer {self._key}"},
                                  timeout=180)
        except requests.exceptions.Timeout:
            ms = (time.perf_counter() - started) * 1000
            return None, {"code": None, "error": "timeout"}, ms, {"failed": "timeout"}
        except requests.exceptions.ConnectionError:
            ms = (time.perf_counter() - started) * 1000
            return (None, {"code": None, "error": "connection error"}, ms,
                    {"failed": "connection error"})
        ms = (time.perf_counter() - started) * 1000
        try:
            reply = r.json()
        except ValueError:
            reply = None
        api_error = reply.get("error") if isinstance(reply, dict) else None
        if r.status_code >= 400 or api_error:
            if isinstance(api_error, dict):
                message = str(api_error.get("message") or api_error)
            elif api_error:
                message = str(api_error)
            else:
                message = r.text[:300]
            code = r.status_code if r.status_code >= 400 else (
                api_error.get("code") if isinstance(api_error, dict) else None)
            info = ({"failed": f"HTTP {r.status_code}"}
                    if r.status_code == 429 or r.status_code >= 500 else {})
            return None, {"code": code, "error": self._scrub(message[:300])}, ms, info
        try:
            choice = reply["choices"][0]
            message = choice["message"]
            content = message.get("content")
        except (KeyError, IndexError, TypeError, AttributeError):
            return None, {"code": None, "error": "the reply has no choices"}, ms, {}
        info: dict = {"finish_reason": choice.get("finish_reason")}
        if message.get("refusal"):
            info["refusal"] = self._scrub(str(message["refusal"]))
        if not content:
            info["failed"] = "empty reply"
            return None, {"code": None, "error": "empty reply"}, ms, info
        return content, None, ms, info

    def ask(self, prompt: str) -> tuple[str | None, dict | None, float, dict]:
        """(reply text, error, ms, call). One of the first two is None; `call`
        is what the step records about the request: `retries`,
        `finish_reason`, `refusal` when the API gave one, `retry_reason` when
        it was sent twice.

        One chat-completions request: the prompt as the one user message,
        `ACTION_SCHEMA` as the API's structured-output schema, no temperature
        (the model takes only its default). The schema is sent without the
        API's strict mode, which refuses it: strict mode wants every object
        closed to properties it does not list, and `args` is open on purpose,
        each tool taking its own arguments. A request that fails in transport
        (an empty reply, a timeout, a connection error, HTTP 429 or 5xx) is
        sent once more after `RETRY_WAIT_S` seconds; `ms` is the two requests'
        time together, without the wait."""
        body = {"model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": "action",
                                                    "schema": ACTION_SCHEMA}},
                "max_completion_tokens": self.max_tokens}
        text, error, ms, info = self._post(body)
        call: dict = {"retries": 0}
        first = info.get("failed")
        refusal = info.get("refusal")
        if first:
            time.sleep(RETRY_WAIT_S)
            text, error, more_ms, info = self._post(body)
            ms += more_ms
            call = {"retries": 1, "retry_reason": first}
            refusal = info.get("refusal") or refusal
            second = info.get("failed")
            if second:
                why = f"{first} twice" if second == first else f"{first}, then {second}"
                if second.startswith("HTTP"):
                    why += f": {error['error']}"
                error = {"code": error["code"], "error": why}
        call["finish_reason"] = info.get("finish_reason")
        if refusal:
            call["refusal"] = refusal
        return text, error, ms, call

    def _scrub(self, text: str) -> str:
        return text.replace(self._key, "<key>")

    def next_action(self, question: dict, evidence: list[dict]) -> dict:
        prompt = self.build_prompt(question, evidence)
        reply, error, ms, call = self.ask(prompt)
        trace = {"prompt": prompt, "raw_reply": self._scrub(reply or ""),
                 "llm_ms": round(ms, 1), **call}
        if error:
            return {"tool": "error", "error": error, "trace": trace}
        try:
            action = json.loads(reply)
        except (TypeError, json.JSONDecodeError):
            found = re.search(r"\{.*\}", reply or "", re.S)
            try:
                action = json.loads(found.group(0)) if found else None
            except json.JSONDecodeError:
                action = None
        if not isinstance(action, dict) or "tool" not in action:
            return {"tool": "error", "trace": trace,
                    "error": {"code": None, "error": "the reply is not a JSON action"}}
        if action.get("final_answer") not in (None, "") or action["tool"] == "final":
            return {"tool": "final", "final_answer": str(action.get("final_answer", "")),
                    "trace": trace}
        return {"tool": action["tool"], "args": action.get("args") or {}, "trace": trace}


# ---------------------------------------------------------------- the loop

def given_evidence(question: dict) -> dict:
    brand = question["anchor_brand"]
    return {"given": {"anchor_brand": brand,
                      "category_words": category_words(question["anchor_title"], brand)}}


def given_products_evidence(question: dict, products: dict[str, dict]) -> dict:
    """The oracle's products as the evidence's first entry: every product of
    the question's oracle, sorted by id, with the fields a search result
    shows. Raises KeyError for a product the build does not have."""
    return {"given": {"products": [
        {"id": pid, "title": products[pid]["title"], "brand": products[pid]["brand"]}
        for pid in sorted(question["oracle"])]}}


def brand_scores(question: dict, answer: str | None) -> tuple[float | None, float | None]:
    """(recall, precision) of an answered brand table against the oracle's
    brands. Recall is None when the oracle names no brand (nothing to cover);
    precision is None when the table names none. An answer that is not a
    table scores recall 0."""
    wanted = set(question["oracle_brands"])
    try:
        table = json.loads(answer) if answer else None
    except json.JSONDecodeError:
        table = None
    named = {norm_brand(b) for b in table} if isinstance(table, dict) else set()
    recall = len(named & wanted) / len(wanted) if wanted else None
    precision = len(named & wanted) / len(named) if named else None
    return recall, precision


def judge(question: dict, shape: str, answer: str | None) -> bool:
    if not answer:
        return False
    if shape == "brands":
        recall, _ = brand_scores(question, answer)
        return recall == 1.0
    return answer in question["oracle"]


def run_question(question: dict, planner: Planner, client: Vespa, *, shape: str,
                 k: int, oracle: bool, max_steps: int = MAX_STEPS,
                 surface: str = "tools", tenant: str | list[str] | None = None,
                 oracle_products: dict[str, dict] | None = None) -> dict:
    """One question through the loop. `oracle` supplies the first hop's facts;
    `oracle_products` (the build's products by id) supplies the oracle's
    products instead; not both."""
    if oracle and oracle_products is not None:
        raise ValueError("--oracle and --oracle-products are two different modes")
    kind = "facts" if oracle else "products" if oracle_products is not None else None
    evidence: list[dict] = ([given_evidence(question)] if kind == "facts" else
                            [given_products_evidence(question, oracle_products)]
                            if kind == "products" else [])
    steps: list[dict] = []
    answer: str | None = None
    error: dict | None = None
    context_bytes = 0
    queries = 0
    last_search: dict | None = None
    for n in range(1, max_steps + 1):
        action = planner.next_action(question, evidence)
        trace = action.get("trace")
        if action["tool"] == "error":
            error = action["error"]
            steps.append({"step": n, "tool": "error", "error": error, **(trace or {})})
            break
        if action["tool"] == "final":
            answer = action.get("final_answer")
            steps.append({"step": n, "tool": "final", "answer": answer, **(trace or {})})
            break
        started = time.perf_counter()
        result = execute(client, action, k, question.get("pool"), surface, tenant)
        ms = (time.perf_counter() - started) * 1000
        n_requests = len(result.get("requests", []))
        queries += n_requests
        context_bytes += result_bytes(result)
        shown = dict(action.get("args", {}))
        if action["tool"] in ("search", "query"):
            shown["hits"] = int(action.get("hits", k))
        step = {"step": n, "tool": action["tool"], "args": shown,
                "status": result["status"], "requests": n_requests,
                "top_ids": top_ids(result), "ms": round(ms, 1)}
        if action["tool"] == "query":
            # the statement as the model wrote it is in `args`; this is what went out
            step["yql_sent"] = result.get("yql")
        if result["status"] == "malformed":
            step["message"] = result.get("message", "")
        steps.append({**step, **(trace or {})})
        # `message` is on a malformed result only: the engine's reason reaches the planner
        entry = {"tool": action["tool"], "args": action.get("args", {}),
                 "hop": action.get("hop"), **{key: result[key] for key in
                 ("status", "message", "hits", "groups", "document", "count") if key in result}}
        evidence.append({key: v for key, v in entry.items() if v is not None})
        if action["tool"] in ("search", "query") and result["status"] == "ok":
            last_search = result
    candidates = [h["id"] for h in (last_search or {}).get("hits", [])]
    recall, precision = (brand_scores(question, answer) if shape == "brands"
                         else (None, None))
    hop1 = next((s for s in steps if s.get("tool") in ("search", "query")), None)
    return {
        "question_id": question["question_id"], "planner": planner.name,
        "surface": surface, "oracle_mode": kind is not None,
        **({"oracle_kind": kind} if kind else {}), "shape": shape, "k": k,
        "tenant": tenant, "steps": steps,
        "answer": answer, "success": judge(question, shape, answer),
        "brand_recall": recall, "brand_precision": precision,
        "candidates": candidates if shape == "alternative" else [],
        "context_bytes": context_bytes, "queries_issued": queries,
        "hop1_top_is_anchor": (None if kind or hop1 is None else
                               hop1["top_ids"][:1] == [question["anchor_id"]]),
        "error": error,
    }


# ---------------------------------------------------------------- blocks

def _short(value, width: int = 70) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    text = text.replace("|", "/")
    return text if len(text) <= width else text[:width - 1] + "…"


def metrics_fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def supplied_words(record: dict) -> str:
    """What a run was handed, as the captions say it: nothing, the first
    hop's facts, or the oracle's products (a log with no `oracle_kind` is
    from before the products mode and supplied facts)."""
    if not record.get("oracle_mode"):
        return ""
    if record.get("oracle_kind") == "products":
        return ", the oracle's products supplied"
    return ", evidence supplied"


def block_trajectory(line: dict) -> str:
    """One question's steps as a markdown table."""
    rows = ["| step | tool | args | status | results |", "|---|---|---|---|---|"]
    for s in line["steps"]:
        if s["tool"] == "final":
            rows.append(f"| {s['step']} | final | | | answer: {_short(s.get('answer'))} |")
        elif s["tool"] == "error":
            rows.append(f"| {s['step']} | error | | {_short(s['error'])} | |")
        else:
            rows.append(f"| {s['step']} | {s['tool']} | {_short(s['args'])} | "
                        f"{s['status']} | {_short(', '.join(s['top_ids'][:3]) or '-')} |")
    verdict = "is in the oracle set" if line["success"] else "is not in the oracle set"
    if line["shape"] == "brands":
        verdict = (f"covers {metrics_fmt(line['brand_recall'])} of the oracle's brands "
                   f"(precision {metrics_fmt(line['brand_precision'])})")
    rows.append("")
    rows.append(f"Question {line['question_id']}, planner `{line['planner']}`"
                f"{supplied_words(line)}, k = "
                f"{line['k']}: the answer {verdict}. "
                f"{line['queries_issued']} queries, {line['context_bytes']:,} bytes "
                "of results shown to the planner. One trajectory from an example "
                "run, not a measurement.")
    return "\n".join(rows) + "\n"


BLOCKS = {"trajectory": block_trajectory}


# ---------------------------------------------------------------- CLI

def vespa_version(endpoint: str) -> str:
    try:
        r = requests.get(endpoint.rstrip("/") + "/state/v1/version", timeout=10)
        return r.json().get("version", "unknown")
    except (requests.RequestException, ValueError):
        return "unreachable"


def load_tenants(build: Path) -> dict[str, str]:
    """product id -> its seller, from the build's `tenants.jsonl` (the partial
    updates chapter 8 derived; one line is `{"update": "id:us:product::<id>",
    "fields": {"tenant_id": {"assign": "<seller>"}}}`)."""
    path = build / "tenants.jsonl"
    if not path.exists():
        raise SystemExit(f"{path} does not exist; make it with chapters/ch08/derive_tenants.py")
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["update"].rsplit("::", 1)[1]] = rec["fields"]["tenant_id"]["assign"]
    return out


def tenant_pair(question: dict, tenants: dict[str, str]) -> list[str]:
    """The two-seller boundary of a question: the anchor's seller, then the
    seller with the most products in the oracle (ties: the first by seller
    name), among sellers other than the anchor's. Raises KeyError for a
    product with no seller on file."""
    anchor = tenants[question["anchor_id"]]
    counts: dict[str, int] = {}
    for pid in question["oracle"]:
        seller = tenants[pid]
        if seller != anchor:
            counts[seller] = counts.get(seller, 0) + 1
    if not counts:
        return [anchor]
    best = sorted(counts, key=lambda seller: (-counts[seller], seller))[0]
    return [anchor, best]


def load_products(build: Path, wanted: set[str]) -> dict[str, dict]:
    """product id -> {title, brand} for the `wanted` ids, from the build's
    feed file (`products.jsonl`, one put per line) - the same title and brand
    the deployed documents carry and a search result shows."""
    path = build / "products.jsonl"
    if not path.exists():
        raise SystemExit(f"{path} does not exist")
    out: dict[str, dict] = {}
    with path.open() as fh:
        for line in fh:
            head = line[:120]
            start = head.find("::")
            if start < 0 or head[start + 2:head.find('"', start)] not in wanted:
                continue
            fields = json.loads(line)["fields"]
            out[fields["id"]] = {"title": fields.get("title", ""),
                                 "brand": fields.get("brand", "") or ""}
    return out


def load_questions(build: Path, split: str, path: Path | None) -> list[dict]:
    path = path or (build / f"multihop_{split}.jsonl")
    if not path.exists():
        raise SystemExit(f"{path} does not exist; make it with build_multihop_set.py")
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# What has to match for a log to be finished by another invocation.
RUN_KEYS = ("planner", "surface", "shape", "k", "oracle_mode", "oracle_kind",
            "tenant_rule", "model", "build", "split")


def logged_ids(out: Path) -> set[str]:
    """The question ids a log already holds. A last line cut off in the middle
    (the process stopped while writing it) is removed from the file, so the
    question is asked again."""
    lines = out.read_text().splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    ids: set[str] = set()
    for i, raw in enumerate(lines):
        try:
            ids.add(json.loads(raw)["question_id"])
        except (json.JSONDecodeError, KeyError, TypeError):
            if i != len(lines) - 1:
                raise SystemExit(f"{out}: line {i + 1} is not a trajectory line")
            out.write_text("".join(x + "\n" for x in lines[:-1]))
            print(f"{out}: dropped a half-written last line", file=sys.stderr)
    return ids


def check_resumable(out: Path, expected: dict) -> None:
    """Refuse to append to a log written by a different run: its first line
    must agree with `expected` on every key of `RUN_KEYS` and on the
    description's sha256."""
    with out.open() as fh:
        first = next((json.loads(x) for x in fh if x.strip()), None)
    if first is None:
        return
    differ = [key for key in RUN_KEYS if first.get(key) != expected.get(key)]
    if (first.get("skill") or {}).get("sha256") != (expected.get("skill") or {}).get("sha256"):
        differ.append("skill")
    if differ:
        raise SystemExit(f"{out} holds a different run ({', '.join(differ)} differ); "
                         "give another --out, or move the file away to start again")


def run_to_log(questions: list[dict], run_one, out: Path | None,
               resume: bool = True) -> tuple[list[dict], int]:
    """Run each question with `run_one` (question -> line). With `out`, each
    line is written and flushed as its question completes; with `resume`, a
    question already in `out` is skipped and the new lines are appended,
    without it `out` is written afresh. Returns (the lines run now, how many
    skipped)."""
    done = logged_ids(out) if resume and out and out.exists() else set()
    lines: list[dict] = []
    fh = None
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        fh = out.open("a" if resume else "w")
    try:
        for q in questions:
            if q["question_id"] in done:
                continue
            line = run_one(q)
            lines.append(line)
            if fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
                fh.flush()
    finally:
        if fh:
            fh.close()
    return lines, len([q for q in questions if q["question_id"] in done])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--split", required=True, choices=builds.SPLITS,
                    help="which split's questions; no default")
    ap.add_argument("--questions", type=Path, default=None,
                    help="question file (default: <build>/multihop_<split>.jsonl)")
    ap.add_argument("--planner", choices=("rules", "llm"), default="rules")
    ap.add_argument("--surface", choices=sorted(SURFACES), default="tools",
                    help="what the model planner is shown: the tools, or the "
                         "generated catalogue description and the `query` tool")
    ap.add_argument("--skill", type=Path, default=None,
                    help="a saved catalogue description to show (query "
                         "surface only); the chapter's runs give "
                         "chapters/ch10/expected/skill.md. Without it the "
                         "description is generated from app/ with every rank "
                         "profile listed and no note")
    ap.add_argument("--model", default=MODEL,
                    help=f"the model the llm planner asks (default: {MODEL})")
    ap.add_argument("--shape", choices=SHAPES, default="alternative")
    ap.add_argument("--k", type=int, default=3,
                    help="results per search, fixed for every planner")
    ap.add_argument("--limit", type=int, default=5,
                    help="the first N questions by query id")
    supplied = ap.add_mutually_exclusive_group()
    supplied.add_argument("--oracle", action="store_true",
                          help="give the planner the anchor's brand and category words")
    supplied.add_argument("--oracle-products", action="store_true",
                          help="give the planner every product of the question's oracle "
                               "(id, title, brand), sorted by id, before the first turn")
    boundary = ap.add_mutually_exclusive_group()
    boundary.add_argument("--tenant-from-anchor", action="store_true",
                          help="run each question as a user of the anchor product's seller: "
                               "that tenant_id (from the build's tenants.jsonl) bounds every "
                               "search, grouping and statement")
    boundary.add_argument("--tenant-pair", action="store_true",
                          help="run each question as a user allowed two sellers: the "
                               "anchor's and the oracle seller with the most products in "
                               "the question's oracle (ties by name); the pair bounds every "
                               "search, grouping and statement")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--out", type=Path, default=None,
                    help="trajectory file, one JSON line per question, written as "
                         "each question completes; for the llm planner, if it exists, "
                         "the questions in it are skipped and the rest appended")
    ap.add_argument("--from", dest="from_log", type=Path, default=None,
                    help="render --block from a trajectory file already written, "
                         "running nothing")
    ap.add_argument("--question-id", default=None,
                    help="which question --block trajectory prints (default: the first)")
    ap.add_argument("--block", choices=sorted(BLOCKS), default=None,
                    help="print this markdown block on stdout")
    args = ap.parse_args(argv)

    if args.from_log:
        if not args.block:
            raise SystemExit("--from needs --block: it only re-renders a log")
        lines = [json.loads(x) for x in args.from_log.read_text().splitlines() if x.strip()]
        chosen = next((x for x in lines if args.question_id in (None, x["question_id"])), None)
        if chosen is None:
            raise SystemExit(f"no question {args.question_id!r} in {args.from_log}")
        print(BLOCKS[args.block](chosen))
        return 0

    if args.k < 1 or args.limit < 1:
        raise SystemExit("--k and --limit must be at least 1")
    if args.surface == "query" and args.planner != "llm":
        raise SystemExit("--surface query is for the llm planner; the rules planner "
                         "works the tools")
    if args.skill and args.surface != "query":
        raise SystemExit("--skill goes with --surface query")
    skill: str | None = None
    if args.surface == "query":
        skill = args.skill.read_text() if args.skill else schema_skill.describe(APP_DIR)
    if args.oracle_products and args.shape != "alternative":
        raise SystemExit("--oracle-products is for shape alternative: its list is "
                         "the products, not a brand table")
    build = args.build or builds.latest()
    questions = sorted(load_questions(build, args.split, args.questions),
                       key=lambda q: (0, int(q["query_id"])) if q["query_id"].isdigit()
                       else (1, q["query_id"]))[:args.limit]
    tenant_rule = ("anchor" if args.tenant_from_anchor else
                   "pair" if args.tenant_pair else None)
    tenants: dict[str, str] = load_tenants(build) if tenant_rule else {}
    boundaries: dict[str, str | list[str]] = {}
    if tenant_rule:
        unknown = [q["anchor_id"] for q in questions if q["anchor_id"] not in tenants]
        if unknown:
            raise SystemExit(f"no seller on file for the anchor of {len(unknown)} "
                             f"questions, e.g. {unknown[:3]}")
        if tenant_rule == "anchor":
            boundaries = {q["question_id"]: tenants[q["anchor_id"]] for q in questions}
        else:
            unknown = sorted({pid for q in questions for pid in q["oracle"]
                              if pid not in tenants})
            if unknown:
                raise SystemExit(f"no seller on file for {len(unknown)} oracle products, "
                                 f"e.g. {unknown[:3]}")
            boundaries = {q["question_id"]: tenant_pair(q, tenants) for q in questions}
    oracle_products: dict[str, dict] | None = None
    if args.oracle_products:
        wanted = {pid for q in questions for pid in q["oracle"]}
        oracle_products = load_products(build, wanted)
        unknown = sorted(wanted - set(oracle_products))
        if unknown:
            raise SystemExit(f"{len(unknown)} oracle products are not in the build's "
                             f"products, e.g. {unknown[:3]}")
    client = Vespa(args.endpoint)
    if not client.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1

    model = args.model
    planner: Planner = (RulesPlanner(args.shape, args.k) if args.planner == "rules"
                        else LlmPlanner(args.shape, args.k, API_URL, model,
                                        surface=args.surface, skill=skill))
    stamp = {"date": datetime.date.today().isoformat(),
             "build": builds.meta(build)["build_id"], "split": args.split,
             "vespa": vespa_version(args.endpoint), **deployed.stamp()}
    if args.planner == "llm":
        stamp["model"] = model
    if tenant_rule:
        stamp["tenant_rule"] = tenant_rule
    if skill is not None:
        # enough to tell two runs apart and to check a saved copy is the one used
        stamp["skill"] = {"source": str(args.skill) if args.skill else "generated from app/",
                          "chars": len(skill),
                          "sha256": hashlib.sha256(skill.encode()).hexdigest()}

    def run_one(q: dict) -> dict:
        line = {**run_question(q, planner, client, shape=args.shape, k=args.k,
                               oracle=args.oracle, surface=args.surface,
                               tenant=boundaries.get(q["question_id"]),
                               oracle_products=oracle_products), **stamp}
        status = "ok" if line["success"] else ("ERROR" if line["error"] else "miss")
        print(f"  {q['question_id']}: {status}, {line['queries_issued']} queries",
              file=sys.stderr)
        if line["error"]:
            print(f"    error: {json.dumps(line['error'])}", file=sys.stderr)
        return line

    resume = args.planner == "llm"
    if resume and args.out and args.out.exists():
        check_resumable(args.out, {
            "planner": planner.name, "surface": args.surface, "shape": args.shape,
            "k": args.k, "oracle_mode": args.oracle or args.oracle_products,
            "oracle_kind": ("facts" if args.oracle else
                            "products" if args.oracle_products else None),
            **stamp})
    lines, skipped = run_to_log(questions, run_one, args.out, resume=resume)
    if skipped:
        print(f"resumed {args.out}: {skipped} questions already in it were skipped",
              file=sys.stderr)
    if args.out:
        print(f"wrote {args.out}", file=sys.stderr)
    if args.block:
        first = lines[0] if lines else json.loads(args.out.read_text().splitlines()[0])
        print(BLOCKS[args.block](first))
    if args.planner == "llm" and lines and all(x["error"] for x in lines):
        print("every question failed at the model", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
