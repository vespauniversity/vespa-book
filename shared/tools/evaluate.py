"""Measure a rank profile against a corpus build.

Two modes, which answer different questions and produce numbers that are not
comparable with each other:

**retrieval** runs each query against the whole index. It answers "does the
system find the relevant products at all, among a hundred thousand others",
which is what Recall@K means and what chapter 3 reports.

**rerank** restricts scoring to the documents that were judged for that query,
using Vespa's `recall` parameter. It answers "given these candidates, is the
ordering better" — the task ESCI was built for, and the right question for the
ranking chapters, where retrieval is held constant on purpose.

    python shared/tools/evaluate.py --split validation --ranking bm25_weighted

Which split to use is an argument with no default, because using test to make a
decision is the mistake this whole arrangement exists to prevent.

**Every latency this prints is a warm reading**, and it says so wherever it
prints one. See `WARM_NOTE`.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import textwrap
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import builds                       # noqa: E402
import deployed                     # noqa: E402
import hostinfo                     # noqa: E402
import metrics                      # noqa: E402
from query import Vespa             # noqa: E402

# How a query reaches candidates. Not the same axis as the rank profile: the
# retriever decides what is considered, the profile decides how it is ordered.
RETRIEVERS = ("lexical", "semantic", "hybrid")


# What the model wants stamped on a query. The default is what the deployed
# application expects; the models differ - BGE marks the query and leaves the
# document alone, e5 marks both sides, MiniLM marks neither - and using the
# wrong one produces no error, only worse results. Every tool that builds a
# query shares this default so that swapping the model is one edit rather than
# a hunt through the chapter's scripts.
QUERY_PREFIX = os.environ.get(
    "QUERY_PREFIX", "Represent this sentence for searching relevant passages: ")

# What the latency figures here are, and are not. Printed under every block and
# stored in every report, because a latency with no condition beside it gets
# read as a property of Vespa rather than of one warm container on one machine.
#
# This used to warm with five queries and then measure five hundred and sixty,
# against an index that was still moving: on a cold container the first batch
# of a hundred and forty queries read 17.4 ms and the same queries settled at
# 4.4, so the reported mean was mostly the warm-up. Chapter 3's five profiles
# shared a container and their p50 descends monotonically with the order they
# ran in, which is the same artefact seen from the other side.
#
# The fix is not a settle loop and not a wait - both would be this tool
# guessing how long somebody else's machine takes. The query set is simply run
# once and thrown away, so every number below is taken under the same condition
# every time. How long a real system takes to get there is not a number this
# book claims.
WARM_NOTE = (
    "Warm readings. The whole query set was run once and discarded before any "
    "pass was measured, so they describe a container whose index has already "
    "been touched. A cold container answers its first queries more slowly; "
    "this book does not measure by how much, or for how long.")


def build_request(retriever: str, text: str, hits: int,
                  query_prefix: str | None = None,
                  vector_field: str = "title_embedding",
                  embedder: str = "embedder",
                  query_tensor: str = "q",
                  target_hits: int | None = None) -> dict:
    """The YQL and inputs for one retrieval strategy.

    `hits` is how many documents the request returns; the vector arm asks for
    that many nearest neighbours too unless `target_hits` says otherwise, so a
    ten-hit request can still keep a union of hundreds of candidates.

    `vector_field`, `embedder` and `query_tensor` default to the book's one
    embedding setup. Chapter 4 compares setups — another model, or a vector over
    more than the title — and each of those is a field and a component with its
    own name, so the three are arguments rather than constants.
    """
    if retriever == "lexical":
        return {"yql": "select id from product where userQuery()", "query": text}
    prefix = QUERY_PREFIX if query_prefix is None else query_prefix
    embed = {f"input.query({query_tensor})": f'embed({embedder}, "{prefix}{text}")'}
    # Each annotated operator needs its own parentheses once it is combined
    # with anything else; without them YQL fails to parse at the `or`.
    title_nn = "({targetHits:%d}nearestNeighbor(%s, %s))" % (
        hits if target_hits is None else target_hits, vector_field, query_tensor)
    # Semantic retrieval is a nearest-neighbour search over title_embedding and
    # nothing else. Per-bullet vectors were built, measured and removed in
    # chapter 4 - worse as a retriever, nothing as a signal - and this comment
    # used to describe the field they lived in, which no schema has carried
    # since.
    if retriever == "semantic":
        return {"yql": f"select id from product where {title_nn}", **embed}
    return {"yql": f"select id from product where userQuery() or {title_nn}",
            "query": text, **embed}


def parse_params(items: list[str] | None) -> dict[str, str]:
    """`--param input.query(w_title)=3.0` becomes one query parameter.

    Rank profiles can take their weights from the query (`inputs { query(w_title)
    double: 3.0 }`), which is how chapter 3 tunes field weights without a
    redeploy per attempt. Anything after the first `=` is the value, verbatim.
    """
    out: dict[str, str] = {}
    for item in items or []:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise SystemExit(f"--param wants key=value, got {item!r}")
        out[key] = value
    return out


def parse_reranker_inputs(items: list[str] | None) -> dict[str, str]:
    """`--reranker-input qt=colbert` becomes one `{name: embedder}` entry.

    Repeatable: a `phased` measurement needs one input
    per reranker, e.g. `qt=colbert` for the second phase's MaxSim and
    `qt_cross=tokenizer` for the global phase's cross-encoder. Anything after
    the first `=` is the embedder's component id, verbatim - the same shape as
    `--param`, and the same refusal for a value with no `=`.
    """
    out: dict[str, str] = {}
    for item in items or []:
        name, sep, embedder = item.partition("=")
        if not sep or not name:
            raise SystemExit(f"--reranker-input wants NAME=EMBEDDER, got {item!r}")
        out[name] = embedder
    return out


def add_reranker_inputs(request: dict, text: str,
                        reranker_inputs: dict[str, str] | None) -> dict:
    """Add `input.query(NAME)=embed(EMBEDDER, "<text>")` for each reranker
    input, in place, and return `request`.

    No prefix: `QUERY_PREFIX` marks a query for the *retrieval* embedder only
    (see `QUERY_PREFIX`) - a reranker takes the query as written. Backslashes
    and double quotes are escaped before they reach Vespa's `embed(...)`
    expression, the same two characters and the same escaping
    `chapters/ch06/funnel.py:build_phased_request` used before this helper
    replaced its copy of the logic.
    """
    if not reranker_inputs:
        return request
    safe = text.replace("\\", "\\\\").replace('"', '\\"')
    for name, embedder in reranker_inputs.items():
        request[f"input.query({name})"] = f'embed({embedder}, "{safe}")'
    return request


def recall_cutoffs(hits: int) -> tuple[int, ...]:
    """The recall cutoffs a request for `hits` hits can honestly report:
    (10, 100) at a hundred or more, (10,) below - recall@100 over ten
    returned documents would be recall@10 under the wrong name."""
    return tuple(k for k in (10, 100) if k <= hits)


def recall_clause(doc_ids) -> str:
    """Vespa's `recall` parameter: restrict scoring to these documents."""
    return "+({})".format(" ".join(f"id:{d}" for d in doc_ids))


def one_pass(app: Vespa, ids: list[str], queries: dict[str, str],
             judgements: dict[str, dict[str, float]], *, ranking: str, mode: str,
             hits: int, retriever: str, query_prefix: str | None,
             progress_every: int, out, label: str,
             extra_params: dict[str, str] | None = None,
             vector: dict[str, str] | None = None,
             reranker_inputs: dict[str, str] | None = None,
             target_hits: int | None = None,
             ) -> tuple[dict[str, list[str]], list[float], list[float]]:
    """One sweep of the query set, timed."""
    results: dict[str, list[str]] = {}
    client_ms: list[float] = []
    vespa_ms: list[float] = []

    for n, qid in enumerate(ids, 1):
        params = dict(extra_params or {})
        if mode == "rerank":
            judged = judgements.get(qid, {})
            if not judged:
                continue
            params["recall"] = recall_clause(sorted(judged))
        text = queries[qid]
        request = build_request(retriever, text, hits, query_prefix,
                                target_hits=target_hits, **(vector or {}))
        add_reranker_inputs(request, text, reranker_inputs)
        started = time.perf_counter()
        r = app.query(ranking=ranking, hits=hits, timing=True, **request, **params)
        client_ms.append((time.perf_counter() - started) * 1000)
        if r.vespa_ms is not None:
            vespa_ms.append(r.vespa_ms)
        results[qid] = [h.fields.get("id", "") for h in r.hits]
        if progress_every and n % progress_every == 0:
            print(f"  {label} {n}/{len(ids)} queries", file=out, flush=True)

    return results, client_ms, vespa_ms


def run(app: Vespa, queries: dict[str, str], judgements: dict[str, dict[str, float]],
        *, ranking: str, mode: str, hits: int, retriever: str = "lexical",
        query_prefix: str | None = None, progress_every: int = 100,
        out=sys.stderr, extra_params: dict[str, str] | None = None,
        vector: dict[str, str] | None = None, passes: int = 1,
        reranker_inputs: dict[str, str] | None = None,
        target_hits: int | None = None,
        ) -> tuple[dict[str, list[str]], list[list[float]], list[float]]:
    """Warm through the whole query set once, throw that away, then measure it
    `passes` times.

    Not five queries, which is what this did: five is a warm-up for the JIT and
    nothing else, and the index was still moving five hundred queries later. Not
    a settle loop and not a wait either - see `WARM_NOTE`. The warm pass sends
    the identical requests the measured passes will send, because a cache
    warmed by a different query is not warmed.

    Quality comes from the **first** measured pass: its hit-id lists are what
    is returned as `results` and what every score in the report is computed
    from. Every later pass exists only to measure latency again, and it must
    return the identical hit-id list for every query - a corpus and a rank
    profile do not change between two requests a few milliseconds apart, so a
    pass that disagrees with the first is not a second measurement, it is a
    moving index caught in the act (Q4). That is refused rather than averaged
    away: `SystemExit` naming the first query where the two passes disagree.

    Returns `(results, client_ms_per_pass, vespa_ms)` - `client_ms_per_pass` is
    a list of `passes` lists, one per measured pass, so a caller can take the
    median of each pass's own p50 / p95 rather than pooling every request from
    every pass into one distribution, which would hide a pass that ran while
    something else on the machine was busy.
    """
    if passes < 1:
        raise SystemExit(f"passes must be at least 1, got {passes}")
    ids = sorted(queries)
    common = dict(ranking=ranking, mode=mode, hits=hits, retriever=retriever,
                  query_prefix=query_prefix, progress_every=progress_every,
                  out=out, extra_params=extra_params, vector=vector,
                  reranker_inputs=reranker_inputs, target_hits=target_hits)
    print(f"  warming through all {len(ids)} queries once; these are discarded",
          file=out, flush=True)
    one_pass(app, ids, queries, judgements, label="warming", **common)

    first_results: dict[str, list[str]] | None = None
    client_ms_per_pass: list[list[float]] = []
    vespa_ms: list[float] = []
    for p in range(1, passes + 1):
        label = "measuring" if passes == 1 else f"measuring pass {p}/{passes}"
        results, client_ms, pass_vespa_ms = one_pass(
            app, ids, queries, judgements, label=label, **common)
        if first_results is None:
            first_results = results
        else:
            for qid in sorted(first_results):
                if results.get(qid) != first_results[qid]:
                    raise SystemExit(
                        f"pass {p}/{passes} returned different hits for query "
                        f"{qid!r} than pass 1 - a moving index is a "
                        f"measurement error, not data")
        client_ms_per_pass.append(client_ms)
        vespa_ms.extend(pass_vespa_ms)
    return first_results, client_ms_per_pass, vespa_ms


def headline_block(report: dict) -> str:
    """This run's quality, as the finished block that goes on the page.

    Nothing renders it from the report afterwards: the command a reader runs
    prints the block, the chapter marks where it goes, and a full rerun of the
    chapter swaps it whole. So what a reader sees on their terminal and what is printed
    in the book are the same characters, which is the only arrangement where
    the two cannot drift.

    Three decimals, which is what a score reproduces to - the reasoning is in
    `metrics.py`.

    **The latency row is not here.** This block is the four
    numbers a reader reproduces by running the command, and their latency will
    not be ours. A block a reader is told to replace, with a
    latency row carrying its own condition inside it, is exactly how a warm-up
    artefact came to be printed as a 2.2x difference between two profiles. The
    latency is `latency_block` and it is our record of one machine at one
    moment, so the chapter carries the two under different tags.
    """
    s = report["scores"]
    rows = [
        ("ndcg@10", f"**{metrics.fmt_metric(s['ndcg'].get('@10'))}**"),
        ("recall@10", metrics.fmt_metric(s["recall"].get("@10"))),
        ("recall@100", metrics.fmt_metric(s["recall"].get("@100"))),
        ("mrr", metrics.fmt_metric(s.get("mrr"))),
    ]
    out = ["| measurement | value |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in rows]
    return "\n".join(out) + "\n"


def latency_block(report: dict) -> str:
    """What this run cost, as the finished block that goes on the page.

    A cost, not a quality metric: it is a property of one warm container on one
    machine, and a reader re-running the command gets their own machine's
    number rather than a check on ours. So it is taken once and stated with the
    conditions it was taken under, and the conditions are **inside the block**.

    The note is not a sentence somebody remembers to put underneath: a latency
    row whose condition can be dropped in an edit is a latency row that will
    be, and this book has already published one. It is said in three places on
    purpose - here, in `WARM_NOTE`, and in the report's `latency_conditions`.

    **p50 / p95 are a median over `passes` measured passes** (Q4), not one
    reading - so this says how many, in front of `WARM_NOTE` rather than
    leaving a reader to assume a single run.
    """
    lat = report["scores"].get("latency_ms", {})
    passes = report.get("latency_conditions", {}).get("passes", 1)
    out = ["| measurement | value |", "|---|---|",
           f"| p50 / p95 latency | {metrics.fmt_latency(lat.get('p50'))} / "
           f"{metrics.fmt_latency(lat.get('p95'))} |"]
    note = (f"Median of {passes} warm pass{'es' if passes != 1 else ''}. "
            + WARM_NOTE)
    # Wrapped for the page; the report stores the same sentence on one line,
    # where a line break would be noise in a JSON string.
    return "\n".join(out) + "\n\n" + textwrap.fill(note, 79) + "\n"


# One tool, two shapes, so the shape is selected rather than guessed. `headline`
# is the default because it is the one a reader is expected to reproduce.
BLOCKS = {"headline": headline_block, "latency": latency_block}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None,
                    help="a corpus build; default is the most recent")
    ap.add_argument("--split", choices=builds.SPLITS, required=True,
                    help="no default on purpose: test is for reporting, not deciding")
    ap.add_argument("--ranking", default="default")
    ap.add_argument("--query-prefix", default=None,
                    help="what the model wants stamped on a query; overrides "
                         "the QUERY_PREFIX environment variable")
    ap.add_argument("--retriever", choices=RETRIEVERS, default="lexical",
                    help="how candidates are reached, as distinct from how they "
                         "are ranked")
    ap.add_argument("--mode", choices=("retrieval", "rerank"), default="retrieval")
    ap.add_argument("--hits", type=int, default=100)
    ap.add_argument("--target-hits", type=int, default=None, metavar="N",
                    help="how many nearest neighbours the vector arm asks for, "
                         "when that should differ from --hits (default: the "
                         "same number) - a request that returns ten hits can "
                         "still keep a union of four hundred candidates")
    ap.add_argument("--passes", type=int, default=3,
                    help="warm once (discarded), then this many measured "
                         "passes (Q4); quality comes from the first, p50/p95 "
                         "are the median over every pass's own")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--label", default=None, help="name for this run in the report")
    ap.add_argument("--block", choices=sorted(BLOCKS), default="headline",
                    help="which finished block goes to stdout. `headline` is "
                         "the quality a reader reproduces; `latency` is what "
                         "it cost on this machine, with its conditions inside "
                         "it. One block per run, because a swap replaces a "
                         "marked region with stdout and two blocks in one "
                         "stream cannot be told apart")
    ap.add_argument("--param", action="append", default=None, metavar="KEY=VALUE",
                    help="an extra query parameter, repeatable — e.g. "
                         "--param 'input.query(w_title)=3.0' to set a rank "
                         "profile input without redeploying")
    ap.add_argument("--reranker-input", action="append", default=None,
                    metavar="NAME=EMBEDDER",
                    help="a reranker's own query input, repeatable — e.g. "
                         "--reranker-input qt=colbert adds "
                         "input.query(qt)=embed(colbert, \"<query text>\") to "
                         "every request this run sends, warm and measured, "
                         "retrieval and rerank alike. The query text carries "
                         "no prefix (QUERY_PREFIX marks q, the retrieval "
                         "input, only)")
    ap.add_argument("--vector-field", default="title_embedding",
                    help="the document tensor nearestNeighbor searches")
    ap.add_argument("--embedder", default="embedder",
                    help="the component id that embeds the query")
    ap.add_argument("--query-tensor", default="q",
                    help="the rank-profile input the query vector fills")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    extra_params = parse_params(args.param)
    reranker_inputs = parse_reranker_inputs(args.reranker_input)
    vector = {"vector_field": args.vector_field, "embedder": args.embedder,
              "query_tensor": args.query_tensor}

    if args.passes < 1:
        raise SystemExit(f"--passes must be at least 1, got {args.passes}")
    if args.target_hits is not None and args.target_hits < 1:
        raise SystemExit(f"--target-hits must be at least 1, got {args.target_hits}")
    target_hits = args.hits if args.target_hits is None else args.target_hits

    build = args.build or builds.latest()

    app = Vespa(args.endpoint)
    if not app.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1

    queries = builds.load_queries(build, args.split)
    judgements = builds.load_judgements(build, args.split)
    print(f"{builds.describe(build)}\n"
          f"{len(queries)} {args.split} queries | {args.retriever} retrieval "
          f"| profile {args.ranking} | hits {args.hits} | {args.passes} passes"
          + (f" | targetHits {target_hits}" if target_hits != args.hits else ""),
          file=sys.stderr)

    results, client_ms_per_pass, vespa_ms = run(
        app, queries, judgements, ranking=args.ranking, mode=args.mode,
        hits=args.hits, retriever=args.retriever,
        query_prefix=args.query_prefix, extra_params=extra_params, vector=vector,
        passes=args.passes, reranker_inputs=reranker_inputs,
        target_hits=args.target_hits)

    # A cutoff deeper than the hits a request returned is not a
    # measurement of that cutoff. A profile whose match-features are costly
    # per returned hit (ch07's global-phase models) is evaluated with
    # `--hits 10`; recall@100 is then left out of the report (a dash in the
    # block, no `per_query_recall100`) rather than printed from ten hits.
    recall_k = recall_cutoffs(args.hits)
    scores = metrics.evaluate(results, judgements, recall_k=recall_k, ndcg_k=(10,))
    # p50 / p95 are the median of each pass's own value (Q4), not one
    # distribution pooled from every request in every pass - pooling would let
    # one busy pass smear into every other pass's percentile instead of
    # standing as its own reading.
    per_pass = [metrics.percentiles(cm) for cm in client_ms_per_pass]
    latency_ms = {}
    for stat in ("mean", "p50", "p95", "p99", "max"):
        values = [p[stat] for p in per_pass if stat in p]
        if values:
            latency_ms[stat] = round(statistics.median(values), 2)
    scores.latency_ms = latency_ms

    report = {
        "label": args.label or f"{args.retriever}-{args.ranking}-{args.split}",
        "build": builds.meta(build)["build_id"],
        "gain_mapping": builds.meta(build)["gain_mapping"],
        "split": args.split,
        "ranking_profile": args.ranking,
        "retriever": args.retriever,
        "query_prefix": args.query_prefix if args.query_prefix is not None else QUERY_PREFIX,
        # Which model was in the index, asked of the running system. The query
        # prefix above says what we sent; this says what it was sent to, and
        # the two being right separately is not the same as them matching.
        **deployed.stamp(),
        "mode": args.mode,
        "hits_requested": args.hits,
        # The `targetHits` the vector arm asked for: `--target-hits` when
        # given, otherwise the same number as `hits_requested`.
        "target_hits": target_hits,
        # Rank-profile inputs sent with every query, if any. A weighted profile
        # measured under weights the report does not record is a number nobody
        # can reproduce.
        "query_params": extra_params,
        # Additive: the `phased` profile's own reranker
        # inputs, `{name: embedder}` — empty unless `--reranker-input` was
        # given. A report from a chapter that never uses this stays exactly
        # the shape it was.
        "reranker_inputs": reranker_inputs,
        "vector": vector if args.retriever != "lexical" else None,
        "scores": scores.as_dict(),
        # What the latencies in this report are. Without it, a report taken on
        # a warm container and one taken on a cold one are the same document
        # with different numbers in it, and the difference is a factor of four.
        "latency_conditions": {
            "warm": True,
            "warmup": "one pass over the whole query set, discarded",
            "note": WARM_NOTE,
            # Q4: p50 / p95 above are the median of these `passes` measured
            # passes, each identical in the hits it returned (`run` refuses
            # otherwise) and each timed on its own. `per_pass_p50_ms` is what
            # the median in `scores.latency_ms` was taken over.
            "passes": args.passes,
            "per_pass_p50_ms": [round(p.get("p50"), 2) for p in per_pass
                                if "p50" in p],
        },
        "latency_ms_vespa_reported": {
            k: round(v, 2) for k, v in metrics.percentiles(vespa_ms).items()},
        "per_query_ndcg10": {
            q: round(metrics.ndcg_at_k(results[q], judgements.get(q, {}), 10), 6)
            for q in sorted(results)},
        # recall@100's own per-query figures, same shape as
        # `per_query_ndcg10`, so `compare.py` can put a bootstrap interval on
        # the recall@100 difference the way it already does for ndcg@10.
        **({"per_query_recall100": {
            q: round(metrics.recall_at_k(
                results[q],
                {d for d, g in judgements.get(q, {}).items() if g > 0}, 100), 6)
            for q in sorted(results)}} if 100 in recall_k else
           {"recall_at_100": f"not computed: hits {args.hits} < 100"}),
        "host": hostinfo.collect(),
    }

    print(f"\n  {scores.summary()}\n"
          + textwrap.indent(textwrap.fill(WARM_NOTE, 77), "  "), file=sys.stderr)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote {args.out}", file=sys.stderr)
    # The block goes to stdout on its own, every time, whether or not a report
    # was written - so it can be piped, diffed, or lifted into the page without
    # anything else having to read the report back and re-render it. Everything
    # else this command says goes to stderr.
    print(BLOCKS[args.block](report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
