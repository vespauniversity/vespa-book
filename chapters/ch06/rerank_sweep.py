"""The rerank-count curve: how far ndcg@10 moves as a reranker is let touch
more of the candidate depth, and what that costs in latency.

Chapter 6's question - how many candidates a reranker is worth running
over - in one measurement, on the book's own build
(`esci-us-hard-book-s42-kdd-v4`). The funnel (`phased`) scores the bounded
first stage over every candidate, then reranks with one of two models
of opposite cost shape - ColBERT's MaxSim in `second-phase`, a cross-encoder in
`global-phase` - each behind its own knob:

    ranking.rerankCount               second-phase (ColBERT), per content node
    ranking.globalPhase.rerankCount   global-phase (cross-encoder), after merge

Using the wrong knob is silent - the query still succeeds, and on `phased`,
which has both phases, the other reranker's count moves while the one you
meant stays at the profile's own default, a plausible curve about the wrong
reranker - so this prints which knob it used and pins the *other*
phase's knob to 0 on every request, so a `--phase second` sweep is that
reranker alone on top of the first stage and nothing the global phase would
otherwise add is folded into the row (and the same the other way for
`--phase global`).

    .venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase second \\
        --out chapters/ch06/expected/validation-rerank-colbert.json
    .venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase global \\
        --out chapters/ch06/expected/validation-rerank-cross.json

Candidate depth must be at least the largest rerank count swept, or counts
past the depth rerank the same candidates and print identical rows - an
artifact this script refuses to produce rather than footnote. The floor (the first `--counts` value,
almost always 0 - first stage alone) is measured twice, once before the sweep
and once after, so the report
can show the two readings agree instead of assuming a container that ran a
whole sweep in between did not drift.

Retrieval mode, not rerank mode: every row retrieves the union candidate set
fresh (`chapters/ch06/funnel.build_phased_request`, ch05's hybrid retrieval)
rather than restricting scoring to the judged ids, so recall@10 and recall@100
say something a judged-only run cannot - `evaluate.py`'s two modes
(module docstring) apply here exactly as there.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import funnel                        # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))
import builds                        # noqa: E402
import deployed                      # noqa: E402
import hostinfo                      # noqa: E402
import metrics                       # noqa: E402
from evaluate import parse_params    # noqa: E402
from query import Vespa              # noqa: E402

# The two sweeps this chapter runs, at a candidate depth of 400 (so 200 and
# 400 do not silently rerank the same hundred candidates - the artifact the
# refusal above encodes).
DEFAULT_COUNTS = {
    "second": [0, 5, 25, 50, 100, 200, 400],
    "global": [0, 5, 10, 25, 50],
}
# The count each sweep's own bracket column is taken against, besides the
# floor - the counts `phased.profile` itself declared before these sweeps
# chose 25 and 10 (100 for the second phase, 50 for the global phase).
DEFAULT_REFERENCE = {"second": 100, "global": 50}


def _fmean(per_query: dict[str, float]) -> float:
    import math
    import statistics as _st
    finite = [v for v in per_query.values() if not math.isnan(v)]
    return _st.fmean(finite) if finite else float("nan")


def measure_row(app: Vespa, queries: dict[str, str], judgements: dict[str, dict[str, float]],
                *, phase: str, count: int, hits: int, query_prefix: str | None,
                passes: int, out, label_prefix: str, profile: str = funnel.PROFILE,
                extra_params: dict[str, str] | None = None) -> dict:
    """One rerank count, fully warmed and measured (`funnel.run`).

    `profile` and `extra_params` reach every request through `funnel.run` -
    a `--profile` read only by the caption and the report would be an
    accepted-but-ignored flag, the class this chapter's tools do not have;
    both are threaded through instead.
    """
    kwargs = {"second_count": count if phase == "second" else 0,
             "global_count": count if phase == "global" else 0}
    results, client_ms_per_pass, _ = funnel.run(
        app, queries, hits=hits, query_prefix=query_prefix, passes=passes,
        out=out, label_prefix=label_prefix, profile=profile,
        extra_params=extra_params, **kwargs)
    per_ndcg = {q: metrics.ndcg_at_k(results[q], judgements.get(q, {}), 10)
               for q in results}
    per_recall10, per_recall100, per_rr = {}, {}, {}
    for q in results:
        relevant = {d for d, g in judgements.get(q, {}).items() if g > 0}
        per_recall10[q] = metrics.recall_at_k(results[q], relevant, 10)
        per_recall100[q] = metrics.recall_at_k(results[q], relevant, 100)
        per_rr[q] = metrics.reciprocal_rank(results[q], relevant)
    return {
        "rerank_count": count,
        "per_query_ndcg10": {q: round(v, 6) for q, v in sorted(per_ndcg.items())},
        "ndcg10": round(_fmean(per_ndcg), 4),
        "recall10": round(_fmean(per_recall10), 4),
        "recall100": round(_fmean(per_recall100), 4),
        "mrr": round(_fmean(per_rr), 4),
        "latency_ms": funnel.latency_stats(client_ms_per_pass),
    }


def rerank_sweep_block(report: dict) -> str:
    """The sweep, as the finished block for the page.

    Every row's ndcg@10 carries two brackets - against the floor (first stage
    alone) and against `--reference-count` - because those are the two things
    a middle row is argued against, not a bare number. `p99` prints `—` with
    no bracket when this row's own 3-pass jitter would not support one (over
    the 30% cutoff);
    the caption line, not the table, is where a reader is told why - a
    per-row footnote would repeat the same sentence up to seven times.
    """
    knob = funnel.PHASE_KNOB[report["phase"]]
    other = funnel.other_phase(report["phase"])
    other_knob = funnel.PHASE_KNOB[other]
    caption = (f"_Profile `{report['profile']}`, phase `{report['phase']}` "
              f"(`{knob}`), candidate depth {report['hits']}, other phase "
              f"(`{other_knob}`) pinned at {report['other_phase_knob']}, "
              f"reference count {report['reference_count']}_")
    dropped = [str(r["rerank_count"]) for r in report["rows"]
              if r["latency_ms"].get("p99") is None]
    out = [caption, "",
           "| rerank count | ndcg@10 | ndcg@10 vs floor "
           f"({report['floor_count']}) | ndcg@10 vs reference "
           f"({report['reference_count']}) | recall@10 | recall@100 | mrr | "
           "p50 | p95 | p99 |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for r in report["rows"]:
        lat = r["latency_ms"]
        out.append(
            f"| {r['rerank_count']} | {metrics.fmt_metric(r['ndcg10'])} | "
            f"{metrics.fmt_delta(r['vs_floor'])} | "
            f"{metrics.fmt_delta(r['vs_reference'])} | "
            f"{metrics.fmt_metric(r['recall10'])} | "
            f"{metrics.fmt_metric(r['recall100'])} | "
            f"{metrics.fmt_metric(r['mrr'])} | "
            f"{metrics.fmt_latency(lat.get('p50'))} | "
            f"{metrics.fmt_latency(lat.get('p95'))} | "
            f"{metrics.fmt_latency(lat.get('p99'))} |")
    text = "\n".join(out) + "\n"
    if dropped:
        text += (f"\np99 not reported for rerank count{'s' if len(dropped) > 1 else ''} "
                 f"{', '.join(dropped)}: 3-pass jitter exceeded the 30% cutoff.\n")
    return text


# A dict, not a bare call: one entry today, but `--block` is read through it
# rather than printed unconditionally - `chapters/ch05/wider_net.py`'s
# `--block` is accepted and never looked at again, an accepted-but-ignored
# flag this chapter does not repeat.
BLOCKS = {"rerank-sweep": rerank_sweep_block}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=builds.SPLITS, required=True,
                    help="no default: test is for reporting, not deciding")
    ap.add_argument("--profile", default=funnel.PROFILE)
    ap.add_argument("--phase", choices=sorted(funnel.PHASE_KNOB), required=True,
                    help="which phase's rerank count this sweeps; the other "
                         "phase's knob is pinned to 0 on every request")
    ap.add_argument("--counts", type=int, nargs="+", default=None,
                    help="default depends on --phase")
    ap.add_argument("--hits", type=int, default=400,
                    help="candidate depth; must be >= the largest --counts "
                         "value or a count past it reranks the same "
                         "candidates as the depth and prints an identical row")
    ap.add_argument("--reference-count", type=int, default=None,
                    help="the count every row's second bracket is against; "
                         "default depends on --phase")
    ap.add_argument("--passes", type=int, default=3,
                    help="warm once (discarded), then this many measured "
                         "passes per row")
    ap.add_argument("--query-prefix", default=None)
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--timeout", type=float, default=30.0,
                    help="a cross-encoder over a hundred candidates takes "
                         "seconds; passed straight to query.Vespa")
    ap.add_argument("--block", choices=("rerank-sweep",), default="rerank-sweep")
    ap.add_argument("--param", action="append", default=None, metavar="KEY=VALUE",
                    help="an extra query parameter, repeatable, added to "
                         "every request alongside the rerank-count knobs and "
                         "the reranker inputs - e.g. --param "
                         "input.query(w_sim)=0.05")
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    help="print the block from a report this command wrote "
                         "earlier, without querying anything")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.from_report is not None:
        print(BLOCKS[args.block](json.loads(args.from_report.read_text())))
        return 0

    extra_params = parse_params(args.param) if args.param else {}
    counts = sorted(set(args.counts or DEFAULT_COUNTS[args.phase]))
    reference = (args.reference_count if args.reference_count is not None
                else DEFAULT_REFERENCE[args.phase])
    over = [c for c in counts if c > args.hits]
    if over:
        ap.error(f"--counts {over} exceed --hits {args.hits} (candidate depth); "
                 f"a count past the depth reranks the same candidates as the "
                 f"depth and its row would be identical to the largest count "
                 f"that fits — raise --hits or drop these counts")
    if reference not in counts:
        ap.error(f"--reference-count {reference} is not in --counts {counts}; "
                 f"the reference bracket needs a measured row to compare "
                 f"against, add it to --counts")

    build = builds.latest()
    app = Vespa(args.endpoint, timeout=args.timeout)
    if not app.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1

    queries = builds.load_queries(build, args.split)
    judgements = builds.load_judgements(build, args.split)
    floor_count = counts[0]
    print(f"{builds.describe(build)}\n{len(queries)} {args.split} queries | "
          f"profile {args.profile} | phase {args.phase} "
          f"({funnel.PHASE_KNOB[args.phase]}) | hits {args.hits} | "
          f"counts {counts} | reference {reference} | {args.passes} passes\n",
          file=sys.stderr)

    rows = []
    per_count_ndcg: dict[int, dict[str, float]] = {}
    for n, count in enumerate(counts):
        label_prefix = f"[{count}] "
        row = measure_row(app, queries, judgements, phase=args.phase, count=count,
                          hits=args.hits, query_prefix=args.query_prefix,
                          passes=args.passes, out=sys.stderr, label_prefix=label_prefix,
                          profile=args.profile, extra_params=extra_params)
        per_count_ndcg[count] = row["per_query_ndcg10"]
        rows.append(row)
        print(f"  rerank {count:>4}  ndcg@10 {metrics.fmt_metric(row['ndcg10'])}  "
              f"p50 {metrics.fmt_latency(row['latency_ms'].get('p50'))}  "
              f"p95 {metrics.fmt_latency(row['latency_ms'].get('p95'))}",
              file=sys.stderr, flush=True)
        if count == floor_count and n == 0:
            floor_first = row

    print(f"\nre-measuring the floor (rerank_count={floor_count}) once more, "
          f"to compare against the first reading", file=sys.stderr)
    floor_repeat_row = measure_row(app, queries, judgements, phase=args.phase,
                                   count=floor_count, hits=args.hits,
                                   query_prefix=args.query_prefix, passes=args.passes,
                                   out=sys.stderr, label_prefix="[floor repeat] ",
                                   profile=args.profile, extra_params=extra_params)
    floor_agreement = metrics.bootstrap_delta(floor_first["per_query_ndcg10"],
                                              floor_repeat_row["per_query_ndcg10"])
    print(f"  floor first {floor_first['ndcg10']:.4f} vs second "
          f"{floor_repeat_row['ndcg10']:.4f} — "
          f"{'agree' if not floor_agreement['significant'] else 'DISAGREE'} "
          f"{metrics.fmt_delta(floor_agreement)}", file=sys.stderr)

    floor_scores = per_count_ndcg[floor_count]
    reference_scores = per_count_ndcg[reference]
    for row in rows:
        row["vs_floor"] = (None if row["rerank_count"] == floor_count else
                           metrics.bootstrap_delta(floor_scores, row["per_query_ndcg10"]))
        row["vs_reference"] = (None if row["rerank_count"] == reference else
                               metrics.bootstrap_delta(reference_scores,
                                                       row["per_query_ndcg10"]))

    report = {
        "build": builds.meta(build)["build_id"],
        "split": args.split,
        "profile": args.profile,
        "phase": args.phase,
        "other_phase_knob": 0,
        "hits": args.hits,
        "counts": counts,
        "floor_count": floor_count,
        "reference_count": reference,
        "extra_params": extra_params or None,
        **deployed.stamp(),
        "rows": rows,
        "floor_repeat": {
            "rerank_count": floor_count,
            "first": {"ndcg10": floor_first["ndcg10"]},
            "second": {"ndcg10": floor_repeat_row["ndcg10"]},
            "delta": floor_agreement,
            "agree": not floor_agreement["significant"],
        },
        "latency_conditions": {
            "warm": True,
            "passes": args.passes,
            "note": ("Warm readings. The whole query set was run once and "
                    "discarded before each row's passes were measured "
                    "(the same rule as evaluate.py's WARM_NOTE)."),
        },
        "host": hostinfo.collect(),
    }

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote {args.out}", file=sys.stderr)

    print(BLOCKS[args.block](report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
