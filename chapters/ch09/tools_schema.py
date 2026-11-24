"""The tools an agent programs against: four tools and their reasons.

A person who gets zero results rewords the query. An agent needs to be told
*why* there were none, because the fix differs:

    ok               hits came back
    empty            nothing matched, and there was nothing to relax
    over_constrained the structured condition (`where`) removed everything;
                     the same query without it has hits
    filtered         the seller boundary (`tenant`) removed everything; the
                     same query without it has hits
    malformed        Vespa refused the request; `message` says why, and the
                     agent loop passes it to the planner with the status

The three in the middle are found by asking again with the clause removed,
which is why every call reports the requests it issued (`requests`): one tool
call can be two or three Vespa queries, and the agent loop counts those.

A `pool` - the ids a question may be answered from - is a third clause, and
it is different from the other two: it is part of the question, not something
an agent chose, so it is never relaxed. Every re-run keeps it. A search that
returns nothing inside a pool is therefore classified by taking off the
agent's own `where` (still inside the pool): hits then mean `over_constrained`,
none mean `empty`. The pool alone is never the reason for `over_constrained`.

Filtered results are never returned. The whole point of the boundary is that
an agent repeats what it is given; the status says something was hidden, and
that is all it learns.

Four tools, a few words each, so a model can be handed the list as text:

    search(query, where, ranking, hits, params, tenant, pool)
    lookup(product_id)
    group(query, where, field, max_groups, ranking, hits, tenant, pool)
    query(yql, ranking, hits, params, tenant, pool)

The first three are a translation layer: the agent fills in words and a
condition, the tool writes the statement. `query` is the other way of
working: the agent writes the whole statement itself, and the tool only
*wraps* it - the statement's `where` is put in parentheses and the pool and
the seller boundary are ANDed onto it, so nothing a well-formed statement says
can argue either away. A `where` whose parentheses do not balance outside its
quoted strings could close the wrap's parenthesis itself, so it is refused as
`malformed` before any request is sent - on every tool that takes a `where`.
A grouping tail (`| all(group(...) ...)`) is split off before the
wrap and put back after it. `query` returns the same record as `search`
(status, hits with id / title / brand, groups when the statement grouped), so
a log from either way of working is scored alike. Under `query`, `malformed`
is no longer theoretical: a statement the engine refuses comes back with the
engine's message, and so does one with no `where` or one that is not a
`select ... from product` at all. `over_constrained` is found by re-running
with the agent's whole `where` replaced by the pool-and-tenant skeleton.

`TOOLS` is that list in the JSON-schema shape most tool-calling APIs take.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))
import evaluate            # noqa: E402
from query import Vespa, add_where_clause   # noqa: E402
from corpus import LOCALE                   # noqa: E402  (the document id's namespace)

SELECT = "select id, title, brand from product"

STATUSES = ("ok", "empty", "over_constrained", "filtered", "malformed")


def quote(value: str) -> str:
    """A YQL string literal."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def exclude_brand(brand: str) -> str:
    """The clause "not made by this brand".

    `brand` is matched as text, not as an exact string, so excluding "adidas"
    also excludes "adidas Originals" and "Adidas Kids": every product whose
    brand contains the word. That is usually what "not by this brand" means,
    and it is why a shop with many sub-brands can over-exclude.
    """
    return f"!(brand contains {quote(brand)})"


def tenant_clause(tenants: list[str] | str) -> str:
    """The seller boundary as `tenant_id in ("a", "b")`; `""` for no boundary
    (the auditor's `"*"`)."""
    if tenants == "*" or not tenants:
        return ""
    if isinstance(tenants, str):
        tenants = [tenants]
    return "tenant_id in (" + ", ".join(quote(t) for t in tenants) + ")"


def pool_clause(pool: list[str]) -> str:
    """Limit a search to the given product ids: `id in ("a", "b")`.

    `id` is an indexed word-matched field, and `in` works on it in this
    application (checked on the running container: two ids, two hits), so
    no chain of `id contains ... or id contains ...` is needed.
    """
    return "id in (" + ", ".join(quote(i) for i in pool) + ")"


def _request(query: str, ranking: str, hits: int) -> dict:
    """The YQL and inputs for `query` under a rank profile.

    A profile that ranks on the title vector needs the query embedded, so the
    hybrid profiles (any name beginning `hybrid`) get the union request the
    rest of the book uses, `semantic` the vector one; any other name gets the
    plain text query, a keyword-only request under that name.
    """
    if ranking.startswith("hybrid"):
        req = evaluate.build_request("hybrid", query, hits)
    elif ranking == "semantic":
        req = evaluate.build_request("semantic", query, hits)
    else:
        req = evaluate.build_request("lexical", query, hits)
    req["yql"] = req["yql"].replace("select id from product", SELECT, 1)
    return req


def _record(response: Any, yql: str, ranking: str) -> dict:
    return {"yql": yql, "ranking": ranking, "hits": len(response.hits),
            "ms": round(response.ms, 1)}


def _hit(h: Any) -> dict:
    return {"id": h.id, "title": h.fields.get("title", ""),
            "brand": h.fields.get("brand", "")}


def _products(hits: list) -> list[dict]:
    """The products among a response's hits. A statement that groups gets
    the grouping's root (`group:root:0`, no fields) back as a child beside
    the products, and that is not a product."""
    return [_hit(h) for h in hits if not str(h.id).startswith("group:")]


ERROR_MESSAGE = re.compile(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"?')


def balanced(text: str) -> bool:
    """Whether every `(` outside a quoted string is closed by a later `)`,
    no `)` closes one that was never opened, and every quoted string ends.

    The tools put the agent's condition in parentheses and AND the pool and
    the seller boundary onto it; a condition with one `)` too many would
    close that parenthesis itself and put its own `or` outside it.
    """
    depth, quote_char, i = 0, "", 0
    while i < len(text):
        ch = text[i]
        if quote_char:
            if ch == "\\":
                i += 2
                continue
            if ch == quote_char:
                quote_char = ""
        elif ch in "\"'":
            quote_char = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
        i += 1
    return depth == 0 and not quote_char


UNBALANCED = ("the condition's parentheses do not balance (or a quoted string is "
              "left open); every `(` needs its own `)`")


def refusal(text: str) -> str:
    """The engine's reason for a refused request, as the planner is handed it.

    The engine echoes the statement it refused, and the statement carries the
    question's pool clause - every judged id. The ids are the question's, not
    the planner's to see, so the clause becomes `id in (…)` before and after
    the message is taken out of the response body.
    """
    return POOL_IN_TEXT.sub("id in (…)", engine_reason(POOL_IN_TEXT.sub("id in (…)", text)))


def engine_reason(text: str, limit: int = 300) -> str:
    """What the engine said, cut to `limit` characters.

    A refused request comes back as a 4xx whose JSON body carries
    `errors[].message`; the body opens with timing and coverage, so the
    first 300 characters of it would end before the reason. The messages
    are taken out (joined with `; `) and the cut applied to them. Text with
    no such message is cut as it is.
    """
    found = []
    for raw in ERROR_MESSAGE.findall(text):
        try:
            found.append(json.loads('"' + raw + '"'))
        except json.JSONDecodeError:
            found.append(raw)
    reason = "; ".join(m for m in found if m) or text
    return reason[:limit]


def search(client: Vespa, query: str, where: str | None = None,
           ranking: str = "hybrid_rrf", hits: int = 10,
           params: dict | None = None,
           tenant: list[str] | str | None = None,
           pool: list[str] | None = None) -> dict:
    """Find products. `where` is a YQL condition ANDed onto the query
    (`!(brand contains "sony")`), in parentheses, so an `or` in a well-formed
    condition cannot reach past the pool or the seller boundary, and one whose
    parentheses do not balance is refused before any request; `ranking` picks
    the rank profile; `params` is any extra query parameter; `tenant` limits
    results to those sellers; `pool` limits them to those product ids (kept on
    every re-run).
    """
    if where and not balanced(where):
        return {"status": "malformed", "message": UNBALANCED, "hits": [],
                "count": 0, "requests": []}
    requests_made: list[dict] = []
    boundary = tenant_clause(tenant) if tenant else ""
    if pool is not None and not pool:
        return {"status": "empty", "hits": [], "count": 0, "requests": []}
    fixed = pool_clause(pool) if pool else ""

    def run(with_where: bool, with_tenant: bool) -> Any:
        req = _request(query, ranking, hits)
        clauses = []
        if with_where and where:
            clauses.append(f"({where})")
        if with_tenant and boundary:
            clauses.append(boundary)
        yql = req.pop("yql")
        for clause in ([fixed] if fixed else []) + clauses:
            yql = add_where_clause(yql, clause)
        response = client.query(yql, ranking=ranking, hits=hits,
                                **{**req, **(params or {})})
        requests_made.append(_record(response, yql, ranking))
        return response

    try:
        first = run(True, True)
    except RuntimeError as exc:
        return {"status": "malformed", "message": refusal(str(exc)), "hits": [],
                "count": 0, "requests": requests_made or
                [{"yql": None, "ranking": ranking, "hits": 0, "ms": None}]}
    if first.hits:
        return {"status": "ok", "hits": _products(first.hits),
                "count": len(first.hits), "requests": requests_made}

    try:
        if boundary and run(True, False).hits:
            return {"status": "filtered", "hits": [], "count": 0,
                    "requests": requests_made}
        if where and run(False, True).hits:
            return {"status": "over_constrained", "hits": [], "count": 0,
                    "requests": requests_made}
    except RuntimeError as exc:
        return {"status": "malformed", "message": refusal(str(exc)), "hits": [],
                "count": 0, "requests": requests_made}
    return {"status": "empty", "hits": [], "count": 0, "requests": requests_made}


def lookup(client: Vespa, product_id: str) -> dict:
    """Fetch one product by id. `empty` when there is no such product."""
    try:
        doc = client.get_document("product", product_id, namespace=LOCALE)
    except RuntimeError as exc:
        return {"status": "malformed", "message": refusal(str(exc)),
                "count": 0, "requests": [{"lookup": product_id}]}
    request = [{"lookup": product_id}]
    if doc is None:
        return {"status": "empty", "count": 0, "requests": request}
    keep = {k: doc.get(k) for k in ("id", "title", "brand", "color", "tenant_id")}
    return {"status": "ok", "document": keep, "count": 1, "requests": request}


def group(client: Vespa, query: str, where: str | None = None,
          field: str = "brand", max_groups: int = 20,
          ranking: str = "hybrid_rrf", hits: int = 100,
          tenant: list[str] | str | None = None,
          pool: list[str] | None = None) -> dict:
    """Count the matching products by a field: the answer to "which brands,
    how many each" in one request instead of reading the hits.

    Counts are over the `hits` best matches (the retrieval arm nominates
    that many), not over the whole corpus. `where` is taken as in `search`:
    in parentheses, and refused when its parentheses do not balance.
    """
    if where and not balanced(where):
        return {"status": "malformed", "message": UNBALANCED, "groups": [],
                "count": 0, "requests": []}
    if not field.replace("_", "").isalnum():
        return {"status": "malformed", "message": f"not a field name: {field!r}",
                "groups": [], "count": 0, "requests": []}
    requests_made: list[dict] = []
    boundary = tenant_clause(tenant) if tenant else ""
    if pool is not None and not pool:
        return {"status": "empty", "groups": [], "count": 0, "requests": []}
    fixed = pool_clause(pool) if pool else ""
    tail = f" | all(group({field}) max({int(max_groups)}) each(output(count())))"

    def run(with_where: bool, with_tenant: bool) -> list[dict]:
        req = _request(query, ranking, hits)
        yql = req.pop("yql")
        if fixed:
            yql = add_where_clause(yql, fixed)
        if with_where and where:
            yql = add_where_clause(yql, f"({where})")
        if with_tenant and boundary:
            yql = add_where_clause(yql, boundary)
        yql += tail
        response = client.query(yql, ranking=ranking, hits=0, **req)
        requests_made.append(_record(response, yql, ranking))
        return _groups(response.raw, field)

    try:
        groups = run(True, True)
    except RuntimeError as exc:
        return {"status": "malformed", "message": refusal(str(exc)), "groups": [],
                "count": 0, "requests": requests_made}
    if groups:
        return {"status": "ok", "groups": groups, "count": len(groups),
                "requests": requests_made}
    try:
        if boundary and run(True, False):
            return {"status": "filtered", "groups": [], "count": 0,
                    "requests": requests_made}
        if where and run(False, True):
            return {"status": "over_constrained", "groups": [], "count": 0,
                    "requests": requests_made}
    except RuntimeError as exc:
        return {"status": "malformed", "message": refusal(str(exc)), "groups": [],
                "count": 0, "requests": requests_made}
    return {"status": "empty", "groups": [], "count": 0, "requests": requests_made}


def _groups(raw: dict, field: str) -> list[dict]:
    """`[{value, count}]` out of a grouping response, biggest first."""
    out: list[dict] = []

    def walk(node: dict) -> None:
        if node.get("id", "").startswith(f"grouplist:{field}"):
            for child in node.get("children", []):
                out.append({"value": child.get("value", ""),
                            "count": child.get("fields", {}).get("count()", 0)})
            return
        for child in node.get("children", []):
            walk(child)

    walk(raw.get("root", {}))
    return sorted(out, key=lambda g: (-g["count"], g["value"]))


# ------------------------------------------------------------- query (the wrap)

# The pool clause as the engine echoes it: whole, cut off mid-way, or inside a
# JSON body whose quotes are escaped (`\"`).
POOL_IN_TEXT = re.compile(r'id in \((?:\s*\\?"[^"\\]*\\?",?)*\s*\\?"?[^")\\]*\)?')
GROUPING_TAIL = re.compile(r"\s*\|\s*(all\s*\(.*)$", re.S)
STATEMENT = re.compile(r"^select\s+(?P<fields>.+?)\s+from\s+(?P<source>[\w.]+)\s+where\s+(?P<where>.+?)\s*;?$",
                       re.S | re.I)


def split_grouping(yql: str) -> tuple[str, str]:
    """`(statement, grouping tail)`: the tail is everything from the `|`
    that starts an `all(...)` grouping, or "" when there is none."""
    m = GROUPING_TAIL.search(yql)
    if m is None:
        return yql.strip(), ""
    return yql[:m.start()].strip(), " | " + m.group(1).strip()


def normalise(yql: str) -> str:
    """One line, one space around `from` and `where`, so the wrap finds them."""
    text = yql.strip()
    text = re.sub(r"\s+from\s+", " from ", text, count=1, flags=re.I)
    text = re.sub(r"\s+where\s+", " where ", text, count=1, flags=re.I)
    return text


def wrap_statement(yql: str, clauses: list[str]) -> str:
    """The loop's wrap: the statement's `where` in parentheses, each clause
    ANDed onto it, the grouping tail put back at the end."""
    head, tail = split_grouping(normalise(yql))
    for clause in clauses:
        if clause:
            head = add_where_clause(head, clause)
    return head + tail


def parse_statement(yql: str) -> tuple[dict | None, str]:
    """`(parts, reason)`: the statement's `fields` / `source` / `where` /
    `tail`, or None and why it is not a statement this catalogue takes."""
    head, tail = split_grouping(normalise(yql))
    m = STATEMENT.match(head)
    if m is None:
        if not re.search(r"\swhere\s", head, re.I):
            return None, "the statement has no `where` clause"
        return None, "not a `select ... from ... where ...` statement"
    if m.group("source") != "product":
        return None, f"from {m.group('source')}: the only document type to query is product"
    return {**m.groupdict(), "tail": tail}, ""


def query(client: Vespa, yql: str, ranking: str = "hybrid_rrf", hits: int = 10,
          params: dict | None = None,
          tenant: list[str] | str | None = None,
          pool: list[str] | None = None) -> dict:
    """Run a whole YQL statement the agent wrote. The pool and the seller
    boundary are ANDed onto its `where` here, never by the agent; `ranking`
    picks the rank profile; `params` carries the request parameters the
    statement needs (`query` for userQuery(), `input.query(q)` for a
    nearestNeighbor); `hits` is fixed by the caller.
    """
    requests_made: list[dict] = []
    sent: str | None = None

    def malformed(message: str) -> dict:
        # The engine echoes the statement it refused, pool ids and all; the
        # ids are the question's, not the agent's to see, so they go.
        return {"status": "malformed", "message": refusal(message), "yql": sent, "hits": [],
                "count": 0, "requests": requests_made}

    if params is not None and not isinstance(params, dict):
        return malformed("params must be an object of request parameters")
    parts, reason = parse_statement(str(yql))
    if parts is None:
        return malformed(reason)
    if not balanced(parts["where"]):
        return malformed(UNBALANCED.replace("the condition's", "the `where`'s"))
    boundary = tenant_clause(tenant) if tenant else ""
    if pool is not None and not pool:
        return {"status": "empty", "yql": None, "hits": [], "count": 0, "requests": []}
    fixed = pool_clause(pool) if pool else ""
    grouped = re.search(r"group\((\w+)\)", parts["tail"])
    group_field = grouped.group(1) if grouped else ""
    # The caller fixes these three; a statement's own copy would clash.
    extra = {k: v for k, v in (params or {}).items()
             if k not in ("yql", "hits", "ranking", "ranking.profile")}

    def run(with_where: bool, with_tenant: bool) -> tuple[str, list[dict], list[dict]]:
        clauses = [fixed, boundary if with_tenant else ""]
        if with_where:
            statement = wrap_statement(yql, clauses)
        else:
            skeleton = " and ".join(c for c in clauses if c) or "true"
            statement = f"select {parts['fields']} from product where {skeleton}{parts['tail']}"
        try:
            response = client.query(statement, ranking=ranking, hits=hits, **extra)
        except RuntimeError:
            # a refused request was still a request; the loop counts it
            requests_made.append({"yql": statement, "ranking": ranking, "hits": 0, "ms": None})
            raise
        requests_made.append(_record(response, statement, ranking))
        groups = _groups(response.raw, group_field) if group_field else []
        return statement, _products(response.hits), groups

    try:
        sent, found, groups = run(True, True)
    except RuntimeError as exc:
        sent = requests_made[-1]["yql"]
        return malformed(str(exc))
    record = {"yql": sent, "requests": requests_made}
    if group_field:
        record["groups"] = groups
    if found or groups:
        return {"status": "ok", "hits": found, "count": len(found) or len(groups), **record}
    try:
        if boundary and any(run(True, False)[1:]):
            return {"status": "filtered", "hits": [], "count": 0, **record}
        if any(run(False, True)[1:]):
            return {"status": "over_constrained", "hits": [], "count": 0, **record}
    except RuntimeError as exc:
        return malformed(str(exc))
    return {"status": "empty", "hits": [], "count": 0, **record}


TOOLS: list[dict] = [
    {"name": "search",
     "description": "Find products by a text query, among the candidate "
                    "products set for this question. Returns up to `hits` "
                    "products (id, title, brand) and a status: ok, empty "
                    "(nothing matched), over_constrained (`where` removed "
                    "everything; retry without it or loosen it), filtered "
                    "(the seller boundary removed everything), malformed "
                    "(the request was rejected; fix it).",
     "parameters": {
         "type": "object",
         "properties": {
             "query": {"type": "string", "description": "words to search for"},
             "where": {"type": "string",
                       "description": "optional condition, e.g. "
                                      "!(brand contains \"sony\")"},
             "ranking": {"type": "string",
                         "description": "rank profile: hybrid_rrf (default), "
                                        "bm25_tuned, semantic"},
             "hits": {"type": "integer", "description": "how many results"}},
         "required": ["query"]}},
    {"name": "lookup",
     "description": "Fetch one product by its id: title, brand, color.",
     "parameters": {
         "type": "object",
         "properties": {"product_id": {"type": "string"}},
         "required": ["product_id"]}},
    {"name": "group",
     "description": "Count the products matching a query by a field, e.g. "
                    "how many per brand, among the candidate products set "
                    "for this question. One request instead of reading "
                    "every result. Same statuses as search.",
     "parameters": {
         "type": "object",
         "properties": {
             "query": {"type": "string"},
             "where": {"type": "string",
                       "description": "optional condition, as in search"},
             "field": {"type": "string", "description": "default brand"},
             "max_groups": {"type": "integer"}},
         "required": ["query"]}},
    {"name": "query",
     "description": "Run one whole YQL statement you write: `select id, title, "
                    "brand from product where ...`, with `| all(group(...) ...)` "
                    "at the end when you want counts. The candidate products set "
                    "for this question and the seller boundary are ANDed onto your "
                    "where for you: never write them. Returns up to `hits` "
                    "products (the fields you selected, among id, title, brand), "
                    "the groups when the statement grouped, and a status: ok, "
                    "empty (nothing matched), over_constrained (your where matched "
                    "none of the candidates; loosen it), filtered (the seller "
                    "boundary removed everything), malformed (the engine refused "
                    "the statement; `message` says why - fix it and retry).",
     "parameters": {
         "type": "object",
         "properties": {
             "yql": {"type": "string", "description": "the whole statement"},
             "ranking": {"type": "string",
                         "description": "rank profile by name (default hybrid_rrf)"},
             "hits": {"type": "integer", "description": "how many results"},
             "params": {"type": "object",
                        "description": "the request parameters the statement "
                                       "needs, e.g. {\"query\": \"...\"} for "
                                       "userQuery(), {\"input.query(q)\": "
                                       "\"embed(embedder, \\\"...\\\")\"} for "
                                       "nearestNeighbor(title_embedding, q)"}},
         "required": ["yql"]}},
]
