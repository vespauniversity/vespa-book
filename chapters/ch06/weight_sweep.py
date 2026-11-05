"""How to choose `w_sim` and `w_cross`: a one-dimensional sweep on validation.

This chapter replaced two phases that scored with a reranker's own feature
alone (`phased_replace`, kept as this chapter's negative example) with phases
that add a *scaled* reranker score to the stage before it: `second-phase`
adds `query(w_sim) * max_sim` to `firstPhase`, `global-phase` blends the
cross-encoder logit and the second phase's own score by `query(w_cross)`
(`chapters/ch06/app/schemas/product/phased.profile`). Both weights are query
inputs so a request can override them; this tool is how their schema defaults
get chosen, one weight at a time, quality only - `alpha_sweep.py`'s shape
(chapter 5), not `rerank_sweep.py`'s (that one sweeps a rerank *count*, this
one sweeps a *weight* at fixed, pinned counts).

    python chapters/ch06/weight_sweep.py --split validation --input w_sim \\
        --values 0 0.002 0.005 0.01 0.02 0.05 --second 100 --global 0 \\
        --passes 1 --out chapters/ch06/expected/validation-weight-sim.json
    python chapters/ch06/weight_sweep.py --split validation --input w_cross \\
        --values 0 0.3 0.5 0.7 1.0 --second 25 --global 10 --passes 1 \\
        --param 'input.query(w_sim)=0.002' \\
        --out chapters/ch06/expected/validation-weight-cross.json

Quality decides the weight; latency does not move with a weight the way it
moves with a rerank count (the two knobs already pinned here are what costs
time), so this tool runs one pass by default and reports p50 without a
latency verdict - `rerank_sweep.py` / `funnel_budget.py` are where the count
sweeps and the cost table live.

**The first `--values` entry is the floor** (this profile's own default
weight or 0, whichever the caller passes first) and is measured first and
again last, exactly as `rerank_sweep.py` re-measures its floor row - so the
report can show the two readings agree instead of assuming a container that
ran a whole sweep in between did not drift.

Every row's ndcg@10 carries two brackets: against the floor, and against
`vs_best` - the row with the sweep's own highest ndcg@10 - so the rule fixed
before any sweep ran (the smallest value whose bracket against the best row
crosses zero) can be read straight off the block instead of recomputed by eye.

Reuses `chapters/ch06/funnel.run` (the warm-then-measure loop and the two
rerank-count knobs) and the metric code `rerank_sweep.py` already imports
from `shared/tools/metrics.py` - neither is copied here.
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


def _fmean(per_query: dict[str, float]) -> float:
    import math
    import statistics as _st
    finite = [v for v in per_query.values() if not math.isnan(v)]
    return _st.fmean(finite) if finite else float("nan")


def measure_row(app: Vespa, queries: dict[str, str], judgements: dict[str, dict[str, float]],
                *, input_name: str, value: float, second_count: int, global_count: int,
                hits: int, query_prefix: str | None, passes: int, out, label_prefix: str,
                profile: str, base_params: dict[str, str] | None) -> dict:
    """One weight value, fully warmed and measured (`funnel.run`) - the same
    shape `rerank_sweep.measure_row` uses for one rerank count."""
    extra_params = dict(base_params or {})
    extra_params[f"input.query({input_name})"] = value
    results, client_ms_per_pass, _ = funnel.run(
        app, queries, hits=hits, second_count=second_count, global_count=global_count,
        query_prefix=query_prefix, passes=passes, out=out, label_prefix=label_prefix,
        profile=profile, extra_params=extra_params)
    per_ndcg = {q: metrics.ndcg_at_k(results[q], judgements.get(q, {}), 10)
               for q in results}
    per_recall10, per_recall100, per_rr = {}, {}, {}
    for q in results:
        relevant = {d for d, g in judgements.get(q, {}).items() if g > 0}
        per_recall10[q] = metrics.recall_at_k(results[q], relevant, 10)
        per_recall100[q] = metrics.recall_at_k(results[q], relevant, 100)
        per_rr[q] = metrics.reciprocal_rank(results[q], relevant)
    return {
        "value": value,
        "per_query_ndcg10": {q: round(v, 6) for q, v in sorted(per_ndcg.items())},
        "ndcg10": round(_fmean(per_ndcg), 4),
        "recall10": round(_fmean(per_recall10), 4),
        "recall100": round(_fmean(per_recall100), 4),
        "mrr": round(_fmean(per_rr), 4),
        "latency_ms": funnel.latency_stats(client_ms_per_pass),
    }


def weight_sweep_block(report: dict) -> str:
    """The sweep, as the finished block for the page.

    Every row's ndcg@10 carries two brackets - against the floor and against
    `vs_best` (the row with this sweep's own highest ndcg@10) - the same
    "bracket against two fixed rows" shape `rerank_sweep_block` uses, so a
    reader (or the pre-registered rule) reads "smallest value indistinguishable
    from the best" straight off the table rather than the raw numbers.
    """
    caption = (f"_Profile `{report['profile']}`, input `query({report['input']})`, "
              f"second-phase count {report['second_count']} "
              f"(`ranking.rerankCount`), global-phase count "
              f"{report['global_count']} (`ranking.globalPhase.rerankCount`), "
              f"candidate depth {report['hits']}_")
    out = [caption, "",
           f"| {report['input']} | ndcg@10 | ndcg@10 vs floor "
           f"({report['floor_value']}) | ndcg@10 vs best "
           f"({report['best_value']}) | recall@10 | recall@100 | mrr | p50 |",
           "|---|---|---|---|---|---|---|---|"]
    for r in report["rows"]:
        lat = r["latency_ms"]
        out.append(
            f"| {r['value']} | {metrics.fmt_metric(r['ndcg10'])} | "
            f"{metrics.fmt_delta(r['vs_floor'])} | "
            f"{metrics.fmt_delta(r['vs_best'])} | "
            f"{metrics.fmt_metric(r['recall10'])} | "
            f"{metrics.fmt_metric(r['recall100'])} | "
            f"{metrics.fmt_metric(r['mrr'])} | "
            f"{metrics.fmt_latency(lat.get('p50'))} |")
    return "\n".join(out) + "\n"


# A dict, not a bare call: one entry today, but `--block` is read through it
# rather than printed unconditionally - the accepted-but-ignored-flag class
# this chapter's own tools do not repeat.
BLOCKS = {"weight-sweep": weight_sweep_block}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=builds.SPLITS, required=True,
                    help="no default: test is for reporting, not deciding")
    ap.add_argument("--input", choices=("w_sim", "w_cross"), required=True,
                    help="which of `phased`'s two blend weights this sweeps")
    ap.add_argument("--values", type=float, nargs="+", required=True,
                    help="the first value is the floor, measured first and "
                         "again last")
    ap.add_argument("--second", type=int, default=100,
                    help="second-phase (ColBERT) rerank count, pinned for "
                         "the whole sweep")
    ap.add_argument("--global", dest="global_count_arg", type=int, default=0,
                    help="global-phase (cross-encoder) rerank count, pinned "
                         "for the whole sweep")
    ap.add_argument("--hits", type=int, default=400,
                    help="candidate depth; must be >= both --second and "
                         "--global or a pinned count reranks past the "
                         "candidates this sweep actually retrieved")
    ap.add_argument("--passes", type=int, default=1,
                    help="quality decides the weight, not latency (see "
                         "latency_conditions.note in the report); the count "
                         "sweeps are where multi-pass latency is measured")
    ap.add_argument("--param", action="append", default=None, metavar="KEY=VALUE",
                    help="an extra query parameter, repeatable, added to "
                         "every request alongside the swept weight, the two "
                         "pinned rerank counts and the reranker inputs")
    ap.add_argument("--profile", default=funnel.PROFILE)
    ap.add_argument("--query-prefix", default=None)
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--timeout", type=float, default=30.0,
                    help="a cross-encoder over a hundred candidates takes "
                         "seconds; passed straight to query.Vespa")
    ap.add_argument("--block", choices=("weight-sweep",), default="weight-sweep")
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    help="print the block from a report this command wrote "
                         "earlier, without querying anything")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.from_report is not None:
        print(BLOCKS[args.block](json.loads(args.from_report.read_text())))
        return 0

    if args.hits < args.second or args.hits < args.global_count_arg:
        ap.error(f"--hits {args.hits} (candidate depth) must be >= both "
                 f"--second {args.second} and --global {args.global_count_arg} "
                 f"- a pinned count past the depth reranks the same "
                 f"candidates as the depth")

    base_params = parse_params(args.param) if args.param else {}
    build = builds.latest()
    app = Vespa(args.endpoint, timeout=args.timeout)
    if not app.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1

    queries = builds.load_queries(build, args.split)
    judgements = builds.load_judgements(build, args.split)
    floor_value = args.values[0]
    print(f"{builds.describe(build)}\n{len(queries)} {args.split} queries | "
          f"profile {args.profile} | input {args.input} | second "
          f"{args.second} | global {args.global_count_arg} | hits {args.hits} "
          f"| values {args.values} | {args.passes} passes\n", file=sys.stderr)

    rows = []
    per_value_ndcg: dict[float, dict[str, float]] = {}
    floor_first = None
    for n, value in enumerate(args.values):
        label_prefix = f"[{args.input}={value}] "
        row = measure_row(app, queries, judgements, input_name=args.input, value=value,
                          second_count=args.second, global_count=args.global_count_arg,
                          hits=args.hits, query_prefix=args.query_prefix,
                          passes=args.passes, out=sys.stderr, label_prefix=label_prefix,
                          profile=args.profile, base_params=base_params)
        per_value_ndcg[value] = row["per_query_ndcg10"]
        rows.append(row)
        print(f"  {args.input}={value:<8} ndcg@10 {metrics.fmt_metric(row['ndcg10'])}  "
              f"p50 {metrics.fmt_latency(row['latency_ms'].get('p50'))}",
              file=sys.stderr, flush=True)
        if n == 0:
            floor_first = row

    print(f"\nre-measuring the floor ({args.input}={floor_value}) once more, "
          f"to compare against the first reading", file=sys.stderr)
    floor_repeat_row = measure_row(
        app, queries, judgements, input_name=args.input, value=floor_value,
        second_count=args.second, global_count=args.global_count_arg,
        hits=args.hits, query_prefix=args.query_prefix, passes=args.passes,
        out=sys.stderr, label_prefix="[floor repeat] ", profile=args.profile,
        base_params=base_params)
    floor_agreement = metrics.bootstrap_delta(floor_first["per_query_ndcg10"],
                                              floor_repeat_row["per_query_ndcg10"])
    print(f"  floor first {floor_first['ndcg10']:.4f} vs second "
          f"{floor_repeat_row['ndcg10']:.4f} — "
          f"{'agree' if not floor_agreement['significant'] else 'DISAGREE'} "
          f"{metrics.fmt_delta(floor_agreement)}", file=sys.stderr)

    best_value = max(rows, key=lambda r: r["ndcg10"])["value"]
    floor_scores = per_value_ndcg[floor_value]
    best_scores = per_value_ndcg[best_value]
    for row in rows:
        row["vs_floor"] = (None if row["value"] == floor_value else
                           metrics.bootstrap_delta(floor_scores, row["per_query_ndcg10"]))
        row["vs_best"] = (None if row["value"] == best_value else
                          metrics.bootstrap_delta(best_scores, row["per_query_ndcg10"]))

    report = {
        "build": builds.meta(build)["build_id"],
        "split": args.split,
        "profile": args.profile,
        "input": args.input,
        "second_count": args.second,
        "global_count": args.global_count_arg,
        "hits": args.hits,
        "values": args.values,
        "floor_value": floor_value,
        "best_value": best_value,
        "extra_params": base_params or None,
        **deployed.stamp(),
        "rows": rows,
        "floor_repeat": {
            "value": floor_value,
            "first": {"ndcg10": floor_first["ndcg10"]},
            "second": {"ndcg10": floor_repeat_row["ndcg10"]},
            "delta": floor_agreement,
            "agree": not floor_agreement["significant"],
        },
        "latency_conditions": {
            "warm": True,
            "passes": args.passes,
            "note": ("Quality decides the weight; latency does not move with "
                    "it the way it moves with a rerank count. p50 is printed "
                    "for each row, but with the default of one measured pass "
                    "it is not a multi-pass reading - see "
                    "chapters/ch06/rerank_sweep.py / funnel_budget.py for "
                    "the count sweeps' p50/p95/p99 under 3 passes."),
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
