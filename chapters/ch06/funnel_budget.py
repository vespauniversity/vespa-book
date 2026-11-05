"""What each stage of the funnel costs, and what it buys, read off three
fixed configurations rather than a sweep.

Where `rerank_sweep.py` asks "how does quality move as one phase's rerank
count grows", this asks the narrower question a reader wants answered in one
table: first stage alone, then the chosen ColBERT depth, then the chosen
cross-encoder depth on top of that — each stage's ndcg@10 / recall@100 and
its p50 / p95 bracketed against the *previous* stage, not against the floor.
The per-query vs per-document cost split is read off this table's Δp50
column and the sweep's own shape, not measured twice.

    .venv/bin/python chapters/ch06/funnel_budget.py --split validation \\
        --out chapters/ch06/expected/validation-funnel-budget.json

`--second` and `--global` are the counts `rerank_sweep.py`'s two sweeps pick
on validation. Their defaults (100, 50) are the counts
`chapters/ch06/app/schemas/product/phased.profile` declared before those
sweeps chose 25 and 10; the chapter's own command passes the chosen counts.
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


def measure_stage(app: Vespa, queries: dict[str, str], judgements: dict[str, dict[str, float]],
                  *, name: str, second_count: int, global_count: int, hits: int,
                  query_prefix: str | None, passes: int, out,
                  profile: str = funnel.PROFILE,
                  extra_params: dict[str, str] | None = None) -> dict:
    """`profile` and `extra_params` reach every
    request through `funnel.run`, the same wiring `rerank_sweep.py` uses -
    e.g. measuring the budget table at a chosen `w_sim` / `w_cross`, or
    against `phased_replace` instead of `phased`."""
    results, client_ms_per_pass, _ = funnel.run(
        app, queries, hits=hits, second_count=second_count,
        global_count=global_count, query_prefix=query_prefix, passes=passes,
        out=out, label_prefix=f"[{name}] ", profile=profile,
        extra_params=extra_params)
    per_ndcg, per_recall100 = {}, {}
    for q in results:
        judged = judgements.get(q, {})
        per_ndcg[q] = metrics.ndcg_at_k(results[q], judged, 10)
        relevant = {d for d, g in judged.items() if g > 0}
        per_recall100[q] = metrics.recall_at_k(results[q], relevant, 100)
    return {
        "stage": name, "second_count": second_count, "global_count": global_count,
        "per_query_ndcg10": {q: round(v, 6) for q, v in sorted(per_ndcg.items())},
        "ndcg10": round(_fmean(per_ndcg), 4),
        "recall100": round(_fmean(per_recall100), 4),
        "latency_ms": funnel.latency_stats(client_ms_per_pass),
    }


def funnel_budget_block(report: dict) -> str:
    """The three-stage table, as the finished block for the page.

    Every row after the first carries two brackets against the stage before
    it: ndcg@10 (is the extra reranking worth having) and Δp50 (what it cost)
    - `previous`, not the floor, because the funnel figure and the prose
    around it are about one stage's marginal cost on top of the one in
    front of it, not each stage against first-stage-alone.
    """
    out = [f"_Candidate depth {report['hits']}, second-phase count "
          f"{report['second_count']} (`ranking.rerankCount`), global-phase "
          f"count {report['global_count']} (`ranking.globalPhase.rerankCount`)_",
          "",
          "| stage | ndcg@10 | ndcg@10 vs previous | recall@100 | p50 | p95 | "
          "Δp50 vs previous |",
          "|---|---|---|---|---|---|---|"]
    for r in report["rows"]:
        lat = r["latency_ms"]
        dp50 = r.get("delta_p50_vs_previous")
        dp50_text = "—" if dp50 is None else f"{dp50:+.1f} ms"
        out.append(
            f"| {r['stage']} | {metrics.fmt_metric(r['ndcg10'])} | "
            f"{metrics.fmt_delta(r['vs_previous'])} | "
            f"{metrics.fmt_metric(r['recall100'])} | "
            f"{metrics.fmt_latency(lat.get('p50'))} | "
            f"{metrics.fmt_latency(lat.get('p95'))} | {dp50_text} |")
    return "\n".join(out) + "\n"


# A dict, not a bare call: one entry today, but `--block` is read
# through it rather than printed unconditionally - `chapters/ch05/
# wider_net.py`'s `--block` is accepted and never looked at again, an
# accepted-but-ignored flag this file does not repeat.
BLOCKS = {"funnel-budget": funnel_budget_block}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=builds.SPLITS, required=True)
    ap.add_argument("--profile", default=funnel.PROFILE,
                    help="which rank profile the three stages measure - "
                         "default `phased`; `phased_replace` for the "
                         "negative-example budget")
    ap.add_argument("--second", type=int, default=100,
                    help="second-phase (ColBERT) rerank count for stages 2 "
                         "and 3; default 100")
    ap.add_argument("--global", dest="global_count_arg", type=int, default=50,
                    help="global-phase (cross-encoder) rerank count for "
                         "stage 3; default 50")
    ap.add_argument("--hits", type=int, default=400, help="candidate depth")
    ap.add_argument("--passes", type=int, default=3)
    ap.add_argument("--param", action="append", default=None, metavar="KEY=VALUE",
                    help="an extra query parameter, repeatable, added to "
                         "every stage's request alongside its rerank-count "
                         "knobs and the reranker inputs - e.g. --param "
                         "input.query(w_sim)=0.05")
    ap.add_argument("--query-prefix", default=None)
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--block", choices=("funnel-budget",), default="funnel-budget")
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    help="print the block from a report this command wrote "
                         "earlier, without querying anything")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.from_report is not None:
        print(BLOCKS[args.block](json.loads(args.from_report.read_text())))
        return 0

    extra_params = parse_params(args.param) if args.param else {}
    build = builds.latest()
    app = Vespa(args.endpoint, timeout=args.timeout)
    if not app.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1
    queries = builds.load_queries(build, args.split)
    judgements = builds.load_judgements(build, args.split)
    print(f"{builds.describe(build)}\n{len(queries)} {args.split} queries | "
          f"profile {args.profile} | hits {args.hits} | second {args.second} "
          f"| global {args.global_count_arg} | {args.passes} passes"
          + (f" | params {extra_params}" if extra_params else "") + "\n",
          file=sys.stderr)

    stages = [
        ("first stage alone", 0, 0),
        ("+ second phase", args.second, 0),
        ("+ global phase", args.second, args.global_count_arg),
    ]
    rows = []
    previous = None
    for name, second_count, global_count in stages:
        row = measure_stage(app, queries, judgements, name=name,
                            second_count=second_count, global_count=global_count,
                            hits=args.hits, query_prefix=args.query_prefix,
                            passes=args.passes, out=sys.stderr,
                            profile=args.profile, extra_params=extra_params)
        if previous is None:
            row["vs_previous"] = None
            row["delta_p50_vs_previous"] = None
        else:
            row["vs_previous"] = metrics.bootstrap_delta(
                previous["per_query_ndcg10"], row["per_query_ndcg10"])
            p50, prev_p50 = row["latency_ms"].get("p50"), previous["latency_ms"].get("p50")
            row["delta_p50_vs_previous"] = (
                None if p50 is None or prev_p50 is None else round(p50 - prev_p50, 2))
        rows.append(row)
        print(f"  {name:<20} ndcg@10 {metrics.fmt_metric(row['ndcg10'])}  "
              f"p50 {metrics.fmt_latency(row['latency_ms'].get('p50'))}",
              file=sys.stderr, flush=True)
        previous = row

    report = {
        "build": builds.meta(build)["build_id"],
        "split": args.split,
        "profile": args.profile,
        "hits": args.hits,
        "second_count": args.second,
        "global_count": args.global_count_arg,
        "extra_params": extra_params or None,
        **deployed.stamp(),
        "rows": rows,
        "latency_conditions": {
            "warm": True, "passes": args.passes,
            "note": ("Warm readings. The whole query set was run once and "
                    "discarded before each stage's passes were measured."),
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
