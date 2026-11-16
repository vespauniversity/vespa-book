"""Filtered ANN agreement@100 vs exact, and what a filter-matching strategy
costs, under one rung of the selectivity ladder (`rungs.py`).

Same shape as `chapters/ch04/ann_sweep.py`: warm through the split once and
discard it, then `--passes` measured passes; agreement comes from the
first measured pass and `algorithm` from one traced request (the split's
first query) before the passes, p50/p95 are the median of every pass's own
value. What ch04 swept was `hnsw.exploreAdditionalHits`
alone; this chapter adds a filter on top of the same `nearestNeighbor
(title_embedding, q)` request (a system property, not a relevance
number: agreement is how much of the *exact* answer under the same filter
the approximate search found, nothing about whether the products were any
good) and a **matching strategy** — how Vespa's HNSW graph search and the
filter interact:

    pre      approximateThreshold 0, postFilterThreshold 1.0 — the filter is
             checked inside the graph search; HNSW never falls back to exact
             and never post-filters. Below Vespa's filter-first threshold
             (0.2 of the documents) the graph search also switches to its
             "filter-first" walk, which checks the filter before computing a
             node's distance and steers by the neighbours that pass
             (looking two hops out, and sometimes three, to find them) - on
             a very selective filter a walk steered only by passing
             neighbours can run out of them before it finds anything, and the
             query returns no hits at all (the `empty queries` column).
    pre_full pre, plus filterFirstThreshold 0 — the same pre-filtered graph
             search with the filter-first walk switched off: every visited
             node's distance is computed and the filter checked afterwards.
    post     postFilterThreshold 0, approximateThreshold 0 — HNSW runs
             unfiltered, then the filter is applied to what it returned.
    exact    approximateThreshold 1.0 — the graph is never used: the filter
             selects the candidates and every one of them is scored, which
             is what Vespa's defaults do on their own below 0.02. Its
             agreement is 1.000 by construction; the row exists for its
             latency at rungs where the defaults do not fall back. The
             threshold only applies to a request that has a filter, so on
             the `none` rung this strategy is the plain graph search.
    default  no knob sent — whatever Vespa's defaults, which this chapter's
             profile leaves unchanged (`approximate-threshold` 0.02,
             `filter-first-threshold` 0.2, `post-filter-threshold` 1.0),
             choose; `default`'s own row records which branch that was, in
             `algorithm`.

**Agreement@100's denominator is what exact returned**, not always `hits`:
a rung small enough that fewer than `hits` documents exist under the filter
at all (`small_brand`, ten documents) cannot have a hundred correct answers
to find, so scoring it out of `hits` would make a perfect small rung look
imperfect. `AGREEMENT_DENOMINATOR_NOTE` says this in every report, verbatim.

**`--retriever lexical` and `--retriever hybrid`** are not part of the
agreement sweep at all — the strategy and exploration settings are not sent
for either row (`lexical` has no `nearestNeighbor`; for `hybrid`, whichever
branch Vespa's defaults choose for its vector arm is not recorded). They
exist for the latency-only rows at the `nike` rung (0.60%) and with no
filter: `lexical` is `evaluate.py`'s `bm25_tuned` / `userQuery()` request,
`hybrid` is its `hybrid_linear` union request, each with the rung's clause
ANDed on (`rungs.wrap_where`) — copied through `evaluate.build_request`,
never retyped. `--strategy` and `--explore` are accepted but not sent for
these two, and the block shows a dash where agreement would be.

    python chapters/ch08/filtered_ann.py --split validation --rung nike \\
        --strategy pre --explore 0 20 100 500 --block rung
    python chapters/ch08/filtered_ann.py --split validation --rung nike \\
        --retriever lexical --block rung
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import textwrap
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))

import builds                       # noqa: E402
import deployed                     # noqa: E402
import hostinfo                     # noqa: E402
import metrics                      # noqa: E402
from evaluate import QUERY_PREFIX, WARM_NOTE, build_request   # noqa: E402
from query import Vespa             # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rungs                         # noqa: E402

FIELD = "title_embedding"
SEMANTIC_RANKING = "semantic"
# ch03's tuned profile and ch05's linear-fusion profile - not re-derived,
# named here once so a caller can see which two `evaluate.build_request`
# retrievers back `--retriever lexical` / `--retriever hybrid`.
LEXICAL_RANKING = "bm25_tuned"
HYBRID_RANKING = "hybrid_linear"

DEFAULT_EXPLORE = (0, 20, 100, 500)

# Per-request knobs (Vespa Query API `ranking.matching.*`), checked once
# against this container when the tool was written: each is accepted with
# no error (no report holds what it returned). `default` sends nothing -
# Vespa's defaults, which this chapter's profile leaves unchanged, reported
# in the `default` rows.
STRATEGY_PARAMS: dict[str, dict[str, float]] = {
    "pre": {"ranking.matching.approximateThreshold": 0,
            "ranking.matching.postFilterThreshold": 1.0},
    "pre_full": {"ranking.matching.approximateThreshold": 0,
                 "ranking.matching.postFilterThreshold": 1.0,
                 "ranking.matching.filterFirstThreshold": 0},
    "post": {"ranking.matching.postFilterThreshold": 0,
             "ranking.matching.approximateThreshold": 0},
    "exact": {"ranking.matching.approximateThreshold": 1.0},
    "default": {},
}

AGREEMENT_DENOMINATOR_NOTE = (
    "agreement@100 per query is |approximate hits ∩ exact hits| / |exact "
    "hits|, not / hits requested: a rung with fewer than `hits` documents "
    "under it at all (small_brand, ten documents) cannot have a hundred "
    "correct answers to find, so the denominator is what the exact row "
    "itself returned for that query (ch04's ann_sweep.py convention).")


def semantic_yql(rung: str, hits: int, *, approximate: bool, explore: int) -> str:
    # `totalTargetHits`: the neighbours asked for in total across the content
    # nodes (floor 100; the rows run at --hits 100).
    annotations = [f"totalTargetHits:{hits}"]
    if not approximate:
        annotations.append("approximate:false")
    if explore:
        annotations.append(f"hnsw.exploreAdditionalHits:{explore}")
    base = (f"select id from product where "
            f"{{{','.join(annotations)}}}nearestNeighbor({FIELD}, q)")
    return rungs.wrap_where(base, rungs.clause(rung))


def semantic_request(rung: str, text: str, hits: int, *, approximate: bool,
                     explore: int) -> dict:
    return {
        "yql": semantic_yql(rung, hits, approximate=approximate, explore=explore),
        "input.query(q)": f'embed(embedder, "{QUERY_PREFIX}{text}")',
    }


def ranking_for(retriever: str) -> str:
    """Which profile a `--retriever lexical`/`hybrid` row measures under -
    ch03's tuned profile, ch05's linear-fusion profile."""
    return LEXICAL_RANKING if retriever == "lexical" else HYBRID_RANKING


def retriever_request(retriever: str, rung: str, text: str, hits: int) -> tuple[dict, str]:
    """`(request, ranking profile)` for the lexical/hybrid latency-only rows -
    `evaluate.build_request`'s own YQL, the rung's clause ANDed on, never a
    hand-typed near-copy of it."""
    request = build_request(retriever, text, hits)
    request["yql"] = rungs.wrap_where(request["yql"], rungs.clause(rung))
    return request, ranking_for(retriever)


def find_algorithm(node) -> str | None:
    """Walk a trace tree for the first `"algorithm"` string it carries.

    Proton's nearestNeighbor blueprint logs its chosen branch under this key
    (observed on this container: `"index top k using filter"` for pre,
    `"index top k"` for post, `"exact"` for default at a selective-enough
    rung) somewhere inside the nested `children` of a `trace.level` response.
    Not a fixed path - the depth this appears at is not documented and is not
    this tool's business to pin - so this looks at every dict, in whatever
    shape the response holds it.
    """
    if isinstance(node, dict):
        found = node.get("algorithm")
        if isinstance(found, str):
            return found
        for value in node.values():
            deeper = find_algorithm(value)
            if deeper:
                return deeper
    elif isinstance(node, list):
        for item in node:
            deeper = find_algorithm(item)
            if deeper:
                return deeper
    return None


def capture_algorithm(app: Vespa, rung: str, strategy_params: dict, text: str,
                      hits: int) -> str | None:
    """One `trace.level=7` query, one hit: which branch Vespa's nearest-
    neighbour blueprint took, under this rung and strategy. Run once per
    (rung, strategy) - not once per explore setting, because the exact/
    post/pre-filter decision does not depend on how many additional hits
    HNSW explores, only on the filter and the thresholds - and the same
    string is stamped on every explore row of the run."""
    request = semantic_request(rung, text, hits, approximate=True, explore=0)
    r = app.query(ranking=SEMANTIC_RANKING, hits=1, trace=7, **request,
                  **strategy_params)
    return find_algorithm(r.raw.get("trace"))


def rung_document_count(app: Vespa, rung: str) -> int:
    """A `hits=0` query: how many documents this rung's clause matches right
    now, live - not the offline count `derive_tenants.py`'s report carries,
    which was taken before the field was fed."""
    clause = rungs.clause(rung)
    yql = "select id from product where true" if not clause \
        else f"select id from product where {clause}"
    return app.query(yql, hits=0).total


def exact_results(app: Vespa, ids: list[str], queries: dict[str, str], rung: str,
                  hits: int) -> dict[str, list[str]]:
    """One request per query, `approximate:false` - the reference every
    approximate row in this run is scored against. Not warmed and not
    repeated: exact search is deterministic given a static index; not
    timed here either (the `exact` strategy's own timed rows are a separate
    run)."""
    results: dict[str, list[str]] = {}
    for qid in ids:
        request = semantic_request(rung, queries[qid], hits, approximate=False,
                                   explore=0)
        r = app.query(ranking=SEMANTIC_RANKING, hits=hits, **request)
        results[qid] = r.ids()
    return results


def one_pass(app: Vespa, ids: list[str], queries: dict[str, str], *, rung: str,
            hits: int, explore: int, strategy_params: dict, out, label: str
            ) -> tuple[dict[str, list[str]], list[float]]:
    results: dict[str, list[str]] = {}
    ms: list[float] = []
    for n, qid in enumerate(ids, 1):
        request = semantic_request(rung, queries[qid], hits, approximate=True,
                                   explore=explore)
        started = time.perf_counter()
        r = app.query(ranking=SEMANTIC_RANKING, hits=hits, timing=True,
                      **request, **strategy_params)
        ms.append((time.perf_counter() - started) * 1000)
        results[qid] = r.ids()
        if n % 100 == 0:
            print(f"  {label} {n}/{len(ids)} queries", file=out, flush=True)
    return results, ms


def sweep_explore(app: Vespa, ids: list[str], queries: dict[str, str], *,
                  rung: str, hits: int, explore: int, strategy_params: dict,
                  passes: int, out=sys.stderr
                  ) -> tuple[dict[str, list[str]], list[list[float]]]:
    """Warmed the way `evaluate.py` / `ann_sweep.py` warm: the whole split
    run once and discarded under this explore setting, then `passes`
    measured passes. Refuses (`SystemExit`) if a later pass disagrees with
    the first on any query's hit ids - a static index does not answer the
    same request two different ways, so a disagreement is a moving index
    caught in the act, not a second measurement (the same refusal
    `evaluate.run` makes)."""
    common = dict(rung=rung, hits=hits, explore=explore,
                  strategy_params=strategy_params, out=out)
    one_pass(app, ids, queries, label="warming", **common)
    first_results: dict[str, list[str]] | None = None
    client_ms_per_pass: list[list[float]] = []
    for p in range(1, passes + 1):
        label = "measuring" if passes == 1 else f"measuring pass {p}/{passes}"
        results, ms = one_pass(app, ids, queries, label=label, **common)
        if first_results is None:
            first_results = results
        else:
            for qid in sorted(first_results):
                if results.get(qid) != first_results[qid]:
                    raise SystemExit(
                        f"pass {p}/{passes} returned different hits for "
                        f"query {qid!r} at explore {explore} than pass 1 - a "
                        f"moving index is a measurement error, not data")
        client_ms_per_pass.append(ms)
    return first_results, client_ms_per_pass


def agreement_stats(approx: dict[str, list[str]], exact: dict[str, list[str]]
                    ) -> tuple[float, float, list[str]]:
    """`(mean, min, empty)` of per-query agreement@100 - see
    `AGREEMENT_DENOMINATOR_NOTE` for the denominator. `empty` lists the
    queries for which the approximate search returned nothing at all while
    exact found something: a whole-query miss, not a partial one."""
    per_query = []
    empty = []
    for qid, exact_ids in exact.items():
        approx_ids = approx.get(qid, [])
        denom = len(exact_ids) or 1
        per_query.append(len(set(approx_ids) & set(exact_ids)) / denom)
        if exact_ids and not approx_ids:
            empty.append(qid)
    return statistics.fmean(per_query), min(per_query), empty


def latency_stats(client_ms_per_pass: list[list[float]]) -> dict[str, float]:
    per_pass = [metrics.percentiles(cm) for cm in client_ms_per_pass]
    out = {}
    for stat in ("mean", "p50", "p95", "p99", "max"):
        values = [p[stat] for p in per_pass if stat in p]
        if values:
            out[stat] = round(statistics.median(values), 2)
    return out


def explore_label(row: dict) -> str:
    if row.get("retriever", "semantic") != "semantic":
        return row["retriever"]
    e = row.get("explore")
    return "default" if not e else f"+{e} explored"


def empty_label(row: dict) -> str:
    """How many queries came back with no hits at all, as `n / N`; a dash
    for a row that has no agreement (the latency-only retrievers)."""
    n = row.get("queries_empty")
    total = row.get("queries")
    if n is None or row.get("agreement_mean") is None:
        return "—"
    return f"{n} / {total}" if total else str(n)


def rung_block(report: dict) -> str:
    """One rung × strategy run: explore, agreement@100, p50, p95, algorithm -
    plus the condition sentence (`docs/measurement.md`), naming this
    rung's document count and the strategy."""
    out = ["| explore | agreement@100 | empty queries | p50 | p95 | algorithm |",
           "|---|---|---|---|---|---|"]
    for row in report["rows"]:
        out.append(
            f"| {explore_label(row)} | "
            f"{metrics.fmt_metric(row.get('agreement_mean'))} | "
            f"{empty_label(row)} | "
            f"{metrics.fmt_latency(row.get('p50'))} | "
            f"{metrics.fmt_latency(row.get('p95'))} | "
            f"{row.get('algorithm') or '—'} |")
    conditions = report.get("latency_conditions", {})
    passes = conditions.get("passes", 1)
    retriever = report.get("retriever", "semantic")
    who = (f"strategy `{report['strategy']}`" if retriever == "semantic"
           else f"retriever `{retriever}` (no ANN strategy)")
    note = (
        f"Cost, one machine: Apple M4 Pro, a 4 CPU / 10 GB container VM "
        f"(Rancher Desktop), median of {passes} warm "
        f"pass{'es' if passes != 1 else ''}, client-measured, {report['split']} "
        f"split, {conditions.get('queries', report.get('queries'))} queries, "
        f"rung `{report['rung']}` ({report.get('rung_documents', 0):,} "
        f"documents), {who} — a reader's machine gives a different number.")
    return "\n".join(out) + "\n\n" + textwrap.fill(note, 79) + "\n"


def summary_block(reports: list[dict], at_explore: int) -> str:
    """Rung × strategy at one explore value, across several reports this
    tool already wrote - no measurement here, only picking one row out of
    each report and printing it beside the rung's live document count."""
    out = ["| rung | documents | share | strategy | agreement@100 | empty queries | p50 | p95 | algorithm |",
           "|---|---|---|---|---|---|---|---|---|"]
    for report in reports:
        rows = report["rows"]
        row = next((r for r in rows if r.get("explore") == at_explore), None)
        if row is None:
            row = rows[0] if rows else {}
        label = report.get("retriever", "semantic")
        strategy = report["strategy"] if label == "semantic" else label
        if str(report.get("_source", "")).endswith("-tail.json"):
            # the baseline repeated later in the same session, as a drift check
            strategy += ", tail run"
        documents = report.get("rung_documents", 0)
        total = report.get("build_documents") or 1
        out.append(
            f"| {report['rung']} | {documents:,} | {documents / total * 100:.2f}% "
            f"| {strategy} | {metrics.fmt_metric(row.get('agreement_mean'))} | "
            f"{empty_label(row)} | "
            f"{metrics.fmt_latency(row.get('p50'))} | "
            f"{metrics.fmt_latency(row.get('p95'))} | "
            f"{row.get('algorithm') or '—'} |")
    return "\n".join(out) + "\n"


BLOCKS = {"rung": rung_block, "summary": summary_block}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--split", choices=builds.SPLITS, required=True,
                    help="no default on purpose: test is for reporting, not deciding")
    ap.add_argument("--rung", choices=sorted(rungs.RUNGS), required=True)
    ap.add_argument("--strategy", choices=sorted(STRATEGY_PARAMS), required=True,
                    help="not sent when --retriever is lexical or hybrid")
    ap.add_argument("--explore", type=int, nargs="+", default=list(DEFAULT_EXPLORE),
                    help="hnsw.exploreAdditionalHits settings to sweep; 0 is "
                         "the annotation omitted. Ignored for --retriever "
                         "lexical/hybrid")
    ap.add_argument("--hits", type=int, default=100)
    ap.add_argument("--passes", type=int, default=3,
                    help="warm once (discarded), then this many measured "
                         "passes; agreement comes from the first, "
                         "algorithm from one traced request (the split's "
                         "first query) before the passes, p50/p95 are the "
                         "median over every pass's own")
    ap.add_argument("--queries", type=int, default=None,
                    help="cap on how many queries of the split to run, for a "
                         "smoke run only; default is every query")
    ap.add_argument("--retriever", choices=("semantic", "lexical", "hybrid"),
                    default="semantic",
                    help="semantic sweeps agreement@100 vs exact under "
                         "--strategy/--explore (the chapter's main table); "
                         "lexical/hybrid are the latency-only rows "
                         "under this rung, no exact reference, strategy and "
                         "exploration not sent")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--block", choices=sorted(BLOCKS), default="rung")
    ap.add_argument("--at-explore", type=int, default=0,
                    help="--block summary only: which explore value's row to "
                         "print per rung x strategy report")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--from", dest="from_reports", type=Path, nargs="+",
                    default=None, metavar="REPORT",
                    help="print --block from report(s) already written, "
                         "measuring nothing; --block rung takes exactly one, "
                         "--block summary takes one or more")
    args = ap.parse_args()

    if args.from_reports:
        reports = []
        for p in args.from_reports:
            report = json.loads(p.read_text())
            report["_source"] = p.name   # lets the summary tell the tail run apart
            reports.append(report)
        if args.block == "rung":
            if len(reports) != 1:
                raise SystemExit("--block rung --from takes exactly one report")
            print(rung_block(reports[0]))
        else:
            print(summary_block(reports, args.at_explore))
        return 0

    if args.passes < 1:
        raise SystemExit(f"--passes must be at least 1, got {args.passes}")

    build = args.build or (builds.ROOT / "builds" / "esci-us-hard-book-s42-kdd-v4")
    app = Vespa(args.endpoint)
    if not app.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1

    queries = builds.load_queries(build, args.split)
    ids = sorted(queries) if args.queries is None else sorted(queries)[:args.queries]
    build_documents = builds.meta(build)["counts"]["corpus_documents"]

    rung_documents = rung_document_count(app, args.rung)
    print(f"{builds.describe(build)}\n"
          f"{len(ids)} {args.split} queries | rung {args.rung} "
          f"({rung_documents:,} documents) | retriever {args.retriever}",
          file=sys.stderr)

    if args.retriever != "semantic":
        def one(tag):
            r_out = {}
            ms = []
            for n, qid in enumerate(ids, 1):
                req, prof = retriever_request(args.retriever, args.rung,
                                              queries[qid], args.hits)
                started = time.perf_counter()
                resp = app.query(ranking=prof, hits=args.hits, timing=True, **req)
                ms.append((time.perf_counter() - started) * 1000)
                r_out[qid] = resp.ids()
                if n % 100 == 0:
                    print(f"  {tag} {n}/{len(ids)} queries", file=sys.stderr, flush=True)
            return r_out, ms

        one("warming")
        client_ms_per_pass = []
        for p in range(1, args.passes + 1):
            _, ms = one("measuring" if args.passes == 1 else f"measuring pass {p}/{args.passes}")
            client_ms_per_pass.append(ms)
        lat = latency_stats(client_ms_per_pass)
        rows = [{"retriever": args.retriever, "explore": None,
                 "agreement_mean": None, "agreement_min": None,
                 "algorithm": None, **lat}]
        strategy_params_used = None
    else:
        strategy_params = STRATEGY_PARAMS[args.strategy]
        exact = exact_results(app, ids, queries, args.rung, args.hits)
        algorithm = capture_algorithm(app, args.rung, strategy_params,
                                      queries[ids[0]], args.hits)
        print(f"strategy {args.strategy} {strategy_params or '(no knob)'} "
              f"-> algorithm observed: {algorithm!r}", file=sys.stderr)
        rows = []
        for explore in args.explore:
            print(f"explore {explore}: warming, then {args.passes} measured "
                  f"pass{'es' if args.passes != 1 else ''} over {len(ids)} "
                  f"queries", file=sys.stderr)
            approx, client_ms_per_pass = sweep_explore(
                app, ids, queries, rung=args.rung, hits=args.hits,
                explore=explore, strategy_params=strategy_params,
                passes=args.passes)
            agreement_mean, agreement_min, empty = agreement_stats(approx, exact)
            lat = latency_stats(client_ms_per_pass)
            rows.append({"explore": explore, "agreement_mean": round(agreement_mean, 4),
                        "agreement_min": round(agreement_min, 4),
                        "queries": len(exact), "queries_empty": len(empty),
                        "empty_query_ids": sorted(empty),
                        "algorithm": algorithm, **lat})
        strategy_params_used = strategy_params

    report = {
        "build": builds.meta(build)["build_id"],
        "build_documents": build_documents,
        **deployed.stamp(),
        "split": args.split,
        "queries": len(ids),
        "rung": args.rung,
        "rung_clause": rungs.clause(args.rung),
        "rung_documents": rung_documents,
        "strategy": args.strategy,
        "strategy_params": strategy_params_used,
        "retriever": args.retriever,
        "hits": args.hits,
        "agreement_denominator": AGREEMENT_DENOMINATOR_NOTE,
        "rows": rows,
        "latency_conditions": {"warm": True, "passes": args.passes,
                               "queries": len(ids), "note": WARM_NOTE},
        "host": hostinfo.collect(),
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    print(BLOCKS[args.block](report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
