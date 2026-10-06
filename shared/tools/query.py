"""Query Vespa over the search API, and read what came back.

A thin wrapper: build a request, send it, return the hits with their relevance
and whatever rank features were asked for. Chapters call it rather than
repeating the same twenty lines of `requests` each time.

Tracing is here because chapter 2 asks the reader to read a result trace, and
because a query that returns the wrong thing is usually explained by the trace
rather than by the hits.
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import requests

import deployed


@dataclass
class Hit:
    id: str
    relevance: float
    fields: dict[str, Any] = field(default_factory=dict)

    @property
    def features(self) -> dict[str, float]:
        """Whatever the rank profile exposed as match- or summary-features."""
        return {**self.fields.get("matchfeatures", {}),
                **self.fields.get("summaryfeatures", {})}


@dataclass
class Response:
    hits: list[Hit]
    total: int
    ms: float
    raw: dict

    @property
    def trace(self) -> list:
        return self.raw.get("trace", {}).get("children", [])

    @property
    def vespa_ms(self) -> float | None:
        """What Vespa says it spent, as opposed to what the client observed.

        The difference between the two is network and serialisation. Worth
        reporting separately: a chapter that blames Vespa for a client's JSON
        parsing has measured the wrong thing.
        """
        timing = self.raw.get("timing")
        if not timing:
            return None
        return (timing.get("searchtime", 0.0)) * 1000

    def ids(self) -> list[str]:
        return [h.id for h in self.hits]


class Vespa:
    def __init__(self, endpoint: str = "http://localhost:8080",
                 timeout: float = 30.0):
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def query(self, yql: str | None, *, ranking: str | None = "default",
              hits: int | None = None, query: str | None = None, trace: int = 0,
              timing: bool | None = None, **params: Any) -> Response:
        body: dict[str, Any] = {"timeout": f"{self.timeout}s"}
        # `None` sends no YQL: the request then relies on a query profile that
        # carries the YQL itself (`queryProfile=...` among `params`), which is
        # how a deployed application keeps a request's shape out of the
        # caller's hands.
        if yql is not None:
            body["yql"] = yql
        # `None` on any of these three sends nothing at all and lets the
        # application's query profile decide. The three the chapters teach a
        # reader to put in `search/query-profiles/default.xml` are `hits`,
        # `ranking.profile` and `presentation.timing`.
        #
        # `ranking` learned this first, and for the same reason: this method
        # always sent a profile, so the command chapter 2 prints ran `default`
        # long after the application's own default had moved on. The other two
        # were still hard-sent on every request until 2026-09-14, so two thirds
        # of the thing the chapters teach was never exercised by a documented
        # command - a reader could have deleted both lines from the profile and
        # every command in the book would have behaved identically.
        #
        # An explicit value still overrides, which is how it should be: a
        # measurement pins the parameters it depends on - `evaluate.py` needs a
        # hundred hits and needs Vespa's own timing - and a demonstration shows
        # the reader what the deployed application does on its own.
        if ranking is not None:
            body["ranking.profile"] = ranking
        if hits is not None:
            body["hits"] = hits
        if timing is not None:
            body["presentation.timing"] = timing
        if query is not None:
            body["query"] = query
        if trace:
            body["tracelevel"] = trace
        body.update(params)

        started = time.perf_counter()
        r = self.session.post(f"{self.endpoint}/search/", json=body,
                              timeout=self.timeout + 5)
        elapsed = (time.perf_counter() - started) * 1000
        if r.status_code >= 400:
            # One error type out of this method, and the body with it. Vespa
            # puts the reason in the body - "no such rank profile", "expected
            # query(q) to be a tensor" - and raise_for_status() throws that
            # away and raises a different exception class than the two below,
            # so a caller had to catch two types to catch one failure. A test
            # that meant to skip when a profile is not deployed caught only one
            # of them and failed instead, for as long as nobody ran it.
            raise RuntimeError(
                f"query failed: {r.status_code} {r.text[:400]}")
        payload = r.json()

        if "root" not in payload:
            raise RuntimeError(f"unexpected response: {json.dumps(payload)[:400]}")
        root = payload["root"]
        if "errors" in root:
            raise RuntimeError(f"query error: {json.dumps(root['errors'])[:400]}")

        parsed = []
        for h in root.get("children", []):
            fields = h.get("fields", {})
            parsed.append(Hit(id=fields.get("id") or h.get("id", ""),
                              relevance=h.get("relevance", 0.0), fields=fields))
        return Response(hits=parsed, total=root.get("fields", {}).get("totalCount", 0),
                        ms=elapsed, raw=payload)

    def count(self, doctype: str = "product") -> int:
        r = self.query(f"select * from {doctype} where true", hits=0)
        return r.total

    def get_document(self, doctype: str, doc_id: str) -> dict | None:
        """GET one document's fields by id, or `None` if it does not exist.

        `doctype` is also the namespace: every document id this project
        writes is `id:<doctype>:<doctype>::<doc_id>` (`shared/tools/feed.py`'s
        `parse_document_id` reads it back the same way), so there is nothing
        else for a caller to supply. This is for state that lives in a
        document between requests - a profile a stream of events updates one
        field at a time - where a caller needs the current value before it
        sends a query or applies the next change.
        """
        url = f"{self.endpoint}/document/v1/{doctype}/{doctype}/docid/{quote(doc_id, safe='')}"
        r = self.session.get(url, timeout=self.timeout)
        if r.status_code == 404:
            return None
        if r.status_code >= 400:
            raise RuntimeError(f"get_document failed: {r.status_code} {r.text[:400]}")
        return r.json().get("fields", {})

    def update_document(self, doctype: str, doc_id: str, fields: dict) -> dict:
        """PUT a partial update against one document, and return the parsed
        response (carries `id` and nothing about the fields that changed -
        the document API does not echo a partial update back).

        `fields` is already in the document API's own update shape, one entry
        per field - `{"profile_vector": {"assign": {"values": [...]}}}`,
        `{"seen": {"add": ["B000..."]}}`, `{"events_applied": {"increment": 1}}`
        - because different fields take different update verbs and only the
        caller knows which one a given change needs.
        """
        url = f"{self.endpoint}/document/v1/{doctype}/{doctype}/docid/{quote(doc_id, safe='')}"
        r = self.session.put(url, json={"fields": fields}, timeout=self.timeout)
        if r.status_code >= 400:
            raise RuntimeError(f"update_document failed: {r.status_code} {r.text[:400]}")
        return r.json()

    def healthy(self) -> bool:
        try:
            return self.session.get(f"{self.endpoint}/ApplicationStatus",
                                    timeout=5).status_code == 200
        except requests.RequestException:
            return False

    def wait_until_ready(self, timeout: float = 180.0, interval: float = 3.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.healthy():
                return True
            time.sleep(interval)
        return False


# Title text a reader has not seen printed anywhere else in this file - the
# plain-text branch below already truncates to the same width, so a title
# reads the same length whichever mode showed it.
TITLE_WIDTH = 150

# A dict, not a bare flag, because every other tool in this repository that
# takes `--block` chooses a name from one (`evaluate.py`, `smoke_test.py`,
# `compare.py`...), and a second name is an entry added here, not a second
# flag invented later.
BLOCKS = {"query": "one query's top hits, as a markdown table",
         "features": "one query's hits with their match-features, at three "
                     "decimals"}


def format_feature(value: Any) -> str:
    """One feature value for the hit listing: numbers to three decimals, a
    tensor (Vespa sends it as a dict with `type` and `cells` / `values` / `blocks`)
    as its type string, anything else as-is - a summary feature that is a
    tensor used to abort the whole listing."""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return f"{value:.3f}"
    if isinstance(value, dict) and "type" in value:
        return f"<{value['type']}>"
    return str(value)


def query_block(response: Response, query: str, ranking: str,
                embedders: str, title_width: int = TITLE_WIDTH) -> str:
    """One query's top hits, as the finished block for the page.

    Chapter 2 feeds 2,000 documents on purpose and then has to say why a
    reader's own results look thin - this is the evidence: the titles that
    actually came back, at the size the chapter actually ran at, not a number
    quoted from memory. Relevance
    at three decimals, `metrics.py`'s convention for a score. No timing: this
    is a quality block, and a reader who reruns it at a different document
    count reproduces different titles, not a different number.

    The caption carries what a table of titles alone cannot: the query, which
    profile answered it, how many matched in total, and what the running
    system says it has loaded (`deployed_embedders` - a query tool does not
    know its own `build`, only `corpus.py`'s build directory does, so that
    field is not here).
    """
    lines = [
        f"_Query {query!r}, rank profile `{ranking}`, "
        f"{response.total:,} matched, deployed_embedders: {embedders}_",
        "",
        "| rank | title | relevance |",
        "|---|---|---|",
    ]
    for i, hit in enumerate(response.hits, 1):
        title = (hit.fields.get("title", "") or "")[:title_width]
        # A title is free text from the corpus, not a value this file made up,
        # so it can carry the two characters that would otherwise break a
        # markdown table row: a literal backslash (escaped first, or escaping
        # the pipe below would double it) and the pipe itself.
        title = title.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {i} | {title} | {hit.relevance:.3f} |")
    return "\n".join(lines) + "\n"


def features_block(response: Response, query: str, ranking: str, embedders: str,
                   title_width: int = TITLE_WIDTH) -> str:
    """One query's hits with their match-features, as the finished block for
    the page - the concrete nativeRank / bm25 numbers rather than a
    description of them.

    Columns come from `fields.matchfeatures` (`Response.features` also merges
    in `summaryfeatures`, which this profile does not use, so reading
    `matchfeatures` directly is what decides whether there is anything to
    print at all) and are taken in **the order the response lists them**,
    which is Vespa's own ordering for the deployed rank profile, not one
    guessed here - a profile that adds or reorders `match-features` changes
    this table's columns without an edit to this file.
    """
    if not response.hits or not response.hits[0].fields.get("matchfeatures"):
        raise SystemExit(
            f"rank profile `{ranking}` exposes no match-features "
            f"(fields.matchfeatures is empty) - deploy a profile that "
            f"declares `match-features`, e.g. `explained`")
    columns = list(response.hits[0].fields["matchfeatures"].keys())
    lines = [
        f"_Query {query!r}, rank profile `{ranking}`, "
        f"deployed_embedders: {embedders}_",
        "",
        "| rank | relevance | title | " + " | ".join(columns) + " |",
        "|---|---|---|" + "---|" * len(columns),
    ]
    for i, hit in enumerate(response.hits, 1):
        title = (hit.fields.get("title", "") or "")[:title_width]
        title = title.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")
        feats = hit.fields.get("matchfeatures", {})
        cells = [f"{feats.get(c, 0.0):.3f}" for c in columns]
        lines.append(f"| {i} | {hit.relevance:.3f} | {title} | "
                     + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def add_where_clause(yql: str, clause: str) -> str:
    """AND `clause` onto a YQL string's `where` expression.

    Parenthesises whatever was already there, so an `or` inside it - the
    union request `--retriever hybrid` builds - cannot leak past the new
    clause: `a or b and c` is `a or (b and c)` in YQL, not `(a or b) and c`.
    Ch08 needs exactly this to AND a tenant filter onto any retriever's
    request without retyping its YQL, which is what `--where` is for.
    """
    prefix, sep, where_expr = yql.partition(" where ")
    if not sep:
        raise SystemExit(f"--where needs a ' where ' clause in the YQL: {yql!r}")
    return f"{prefix} where ({where_expr}) and {clause}"


def main() -> int:
    """Ask the running application something, from a terminal.

    Chapter 2 tells a reader that feeding and querying are ordinary HTTP and
    then never has them issue a query - the smoke test does it on their behalf.
    This is the missing half: type a question, see what comes back, and ask for
    the trace when the answer is surprising.

    `--block` is the other caller: not a person at a terminal but a chapter
    that needs the same query's hits as a finished table on the page. It
    replaces this command's usual output rather than adding to it - **one
    block per run**, on stdout and nothing else, everything a person reads
    moved to stderr - so a run without `--block` is exactly the terminal tool
    this always was.

    Chapter 5's worked query needs the union request `evaluate.py` builds for
    hybrid retrieval, with match-features on top - not a second, hand-typed
    YQL string that happens to look like `evaluate.build_request`'s. `--block
    features` already prints whatever columns the deployed rank profile
    exposes as match-features, in the order Vespa lists them, so
    `hybrid_rrf`'s `lexical` and `vector` need no new block, only a way to
    send the request `evaluate.py` sends:

        python shared/tools/query.py --query "running shoes" \\
            --retriever hybrid --ranking hybrid_rrf --block features
    """
    import argparse
    ap = argparse.ArgumentParser(description="Query a running Vespa application.")
    ap.add_argument("--query", required=True, help="what to search for")
    ap.add_argument("--hits", type=int, default=None,
                    help="how many results; omit to use the application's own "
                         "default from its query profile")
    ap.add_argument("--ranking", default=None,
                    help="rank profile; omit to use the application's own "
                         "default from its query profile")
    ap.add_argument("--trace", type=int, default=0,
                    help="ask Vespa to explain itself; 3 is a readable level")
    ap.add_argument("--yql", default="select id, title from product where userQuery()")
    ap.add_argument("--retriever", choices=("lexical", "semantic", "hybrid"),
                    default=None,
                    help="build the request through evaluate.build_request "
                         "instead of --yql - the identical union YQL and "
                         "input.query(q) the chapter's evaluation reports "
                         "use for 'hybrid', not a hand-typed near-copy of "
                         "it. Mutually exclusive with a non-default --yql")
    ap.add_argument("--param", action="append", default=None, metavar="KEY=VALUE",
                    help="an extra query parameter, repeatable - e.g. "
                         "--param 'input.query(alpha)=0.3' for hybrid_linear. "
                         "Reuses evaluate.parse_params, same syntax as "
                         "evaluate.py and alpha_sweep.py")
    ap.add_argument("--where", default=None, metavar="CLAUSE",
                    help="AND this clause onto the request's YQL - "
                         "whichever it is, --retriever's or --yql's - e.g. "
                         "--where 'tenant_id contains \"nike\"' (ch08). "
                         "Additive only: with no --where, --retriever and "
                         "--yql behave exactly as they did before this flag "
                         "existed (existing output is frozen once a chapter has pasted it)")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--block", choices=sorted(BLOCKS), default=None,
                    help="print the finished block for the page instead of "
                         "the usual terminal output. Stdout then carries only "
                         "the block; omit this to get the plain output a "
                         "person reads at a terminal, unchanged")
    args = ap.parse_args()

    if args.retriever and args.yql != ap.get_default("yql"):
        raise SystemExit(
            "--retriever builds its own YQL through evaluate.build_request; "
            "--yql would be silently ignored, so pass one or the other")

    extra_params = {}
    if args.param:
        from evaluate import parse_params   # local: avoids importing evaluate,
        extra_params = parse_params(args.param)  # which imports this file, at load time

    app = Vespa(args.endpoint)
    if not app.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1

    if args.retriever:
        from evaluate import build_request   # local, for the reason above
        hits = args.hits if args.hits is not None else 10
        request = build_request(args.retriever, args.query, hits)
        # evaluate.py asks for ids only; the blocks print a title column, so
        # widen the select list and nothing else about the request.
        request["yql"] = request["yql"].replace("select id from", "select id, title from", 1)
        if args.where:
            request["yql"] = add_where_clause(request["yql"], args.where)
        r = app.query(ranking=args.ranking, hits=hits, trace=args.trace,
                      **request, **extra_params)
    else:
        yql = args.yql if not args.where else add_where_clause(args.yql, args.where)
        r = app.query(yql, query=args.query, hits=args.hits,
                      ranking=args.ranking, trace=args.trace, **extra_params)

    if args.block:
        # What the caption calls the profile. Vespa treats an unset
        # `ranking.profile` as a request for the rank-profile literally named
        # `default` - not a guess made here - so this is accurate whether or
        # not `--ranking` was passed.
        ranking = args.ranking if args.ranking is not None else "default"
        if args.block == "features":
            print(features_block(r, args.query, ranking, deployed.embedder()))
        else:
            print(query_block(r, args.query, ranking, deployed.embedder()))
        return 0

    # Vespa's own figure is here only when the application asked for it -
    # `presentation.timing` in the query profile - so this line is also where a
    # reader sees that field doing something. Nothing here turns it on.
    reported = "" if r.vespa_ms is None else f" ({r.vespa_ms:.0f} ms in Vespa)"
    print(f"{r.total:,} matched, showing {len(r.hits)}, "
          f"{r.ms:.0f} ms round trip{reported}\n")
    for i, hit in enumerate(r.hits, 1):
        title = hit.fields.get("title", "")
        print(f"{i:>2}. {hit.relevance:8.4f}  {title[:150]}")
        if hit.features:
            print("      " + "  ".join(f"{k}={format_feature(v)}" for k, v in hit.features.items()))

    if args.trace:
        print("\n--- trace ---")
        print(json.dumps(r.trace, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
