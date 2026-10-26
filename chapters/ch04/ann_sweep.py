"""What approximate nearest-neighbour search costs, and what it gives up.

Approximate search is a trade: it looks at a fraction of the vectors and
usually returns the same answer. "Usually" is the part worth measuring, and it
is measurable exactly, because the true answer is computable - brute-force
search over every vector is correct, and at this corpus size only a little
slower, and it is what every approximate setting here is scored against.

Two kinds of recall get confused in this chapter, so this tool is careful about
which it reports. **Agreement** is how much of the exact answer the approximate
search returned; it is a property of the index and has nothing to do with
whether the products were any good. Relevance recall, the kind chapter 3
reported, is measured by the evaluation harness instead.

    python chapters/ch04/ann_sweep.py --split validation
    python chapters/ch04/ann_sweep.py --split validation --block ann-sweep-latency

**Two blocks, because this measures two classes of thing.** Agreement and NDCG
are quality: a reader runs this against their own index and gets the same
numbers to within a few thousandths, since HNSW builds a slightly different
graph on every feed, so their run replaces that block. The p50 and p95 are what it cost on one
machine at one moment - a reader's are their machine's, and the chapter's
argument is that exploring harder buys agreement and no relevance while costing
latency, which is an argument across the two blocks rather than down one table.
One block, one class, one tag - a block a reader is told to replace may not
carry a figure their run will not reproduce.

**Warmed the way `evaluate.py` warms, per setting.** The whole split is run
once and discarded under a setting before any pass of it is measured, then
`--passes` (default 3) measured passes are timed; agreement and ndcg come from
the first measured pass, p50/p95 are the median over every pass's own.
`--queries` is no longer what gets swept - it is an optional cap on the split,
for a smoke run only; the default is every query of the split.

**The `HNSW, default` row runs twice, first and last.** Both rows are kept, in
the report and in the block, so a reader can see whether the two readings agree
or the index moved under the sweep.
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
from evaluate import QUERY_PREFIX, WARM_NOTE   # noqa: E402
from query import Vespa             # noqa: E402

FIELD = "title_embedding"


def search(app: Vespa, text: str, hits: int, *, approximate: bool,
           explore: int = 0, ranking: str = "semantic"):
    annotations = [f"targetHits:{hits}"]
    if not approximate:
        annotations.append("approximate:false")
    if explore:
        annotations.append(f"hnsw.exploreAdditionalHits:{explore}")
    yql = (f"select id from product where "
           f"{{{','.join(annotations)}}}nearestNeighbor({FIELD}, q)")
    # The prefix comes from one place (evaluate.QUERY_PREFIX), so swapping the
    # model does not leave a script quietly encoding queries with the old one.
    # The component name `embedder` is this chapter's own literal; it matches
    # the component id in app/services.xml.
    started = time.perf_counter()
    r = app.query(yql, ranking=ranking, hits=hits, timing=True,
                  **{"input.query(q)": f'embed(embedder, "{QUERY_PREFIX}{text}")'})
    return [h.fields.get("id") for h in r.hits], (time.perf_counter() - started) * 1000


def setting_rows(explore_settings: list[int]) -> list[tuple[str, bool, int | None]]:
    """(name, approximate, explore_additional_hits) for every row of the sweep.

    `exact`, then `HNSW, default` (explore 0), then each `--explore` value,
    then `HNSW, default` again - the baseline run twice, head and tail, so a
    reader can see whether the two readings agree.
    """
    return ([("exact", False, None), ("HNSW, default", True, 0)]
            + [(f"HNSW, +{e} explored", True, e) for e in explore_settings]
            + [("HNSW, default", True, 0)])


def sweep_setting(app: Vespa, ids: list[str], queries: dict[str, str], *,
                  approximate: bool, explore: int, hits: int, ranking: str,
                  passes: int, out=sys.stderr, label: str = ""
                  ) -> tuple[dict[str, list[str]], list[list[float]]]:
    """One setting, warmed the way `evaluate.py` warms: the whole split run
    once and discarded, then `passes` measured passes.

    Quality (agreement, ndcg) comes from the **first** measured pass; p50/p95
    are the median of every pass's own value, not one distribution pooled from
    every request in every pass.
    """
    def one_pass(tag: str) -> tuple[dict[str, list[str]], list[float]]:
        results: dict[str, list[str]] = {}
        ms: list[float] = []
        for n, qid in enumerate(ids, 1):
            hit_ids, took = search(app, queries[qid], hits, approximate=approximate,
                                   explore=explore, ranking=ranking)
            results[qid] = hit_ids
            ms.append(took)
            if out and n % 100 == 0:
                print(f"  {label} {tag} {n}/{len(ids)} queries", file=out, flush=True)
        return results, ms

    one_pass("warming")  # discarded
    first_results: dict[str, list[str]] | None = None
    client_ms_per_pass: list[list[float]] = []
    for p in range(1, passes + 1):
        tag = "measuring" if passes == 1 else f"measuring pass {p}/{passes}"
        results, ms = one_pass(tag)
        if first_results is None:
            first_results = results
        client_ms_per_pass.append(ms)
    return first_results, client_ms_per_pass


def setting_name(row: dict) -> str:
    """How the page names a row: `exact`, `HNSW, default`, `HNSW, +100 explored`."""
    if row["setting"] == "exact":
        return "exact"
    n = row["explore_additional_hits"]
    return "HNSW, default" if not n else f"HNSW, +{n} explored"


def ann_sweep_block(report: dict) -> str:
    """Agreement against relevance, kept apart - and both kept apart from cost.

    Agreement is a property of the index: how much of the exact answer the
    approximate search returned. Relevance is a property of the answer. The
    chapter reports both because they move independently, and this book's
    mistake would be tuning against the first.

    At three decimals. This said two until 2026-09-14, on the argument that
    0.409 / 0.407 / 0.407 invites an argument about a difference fifty queries
    cannot see - which is true, and the interval on each row is what refuses it,
    not the digit count. Two decimals cost more than it bought here: the 500
    row's agreement@10 printed 1.00, the same characters as exhaustive search,
    in the one table whose whole subject is how close approximate comes to
    exhaustive. At three it reads 0.998 against 1.000.
    """
    out = ["| setting | agreement@10 | agreement@100 | ndcg@10 |", "|---|---|---|---|"]
    for r in report["rows"]:
        out.append(f"| {setting_name(r)} | "
                   f"{metrics.fmt_metric(r['agreement_at_10'])} | "
                   f"{metrics.fmt_metric(r['agreement_at_hits'])} | "
                   f"{metrics.fmt_metric(r['ndcg10'])} |")
    return "\n".join(out) + "\n"


def ann_sweep_latency_block(report: dict) -> str:
    """What each setting cost, as a block of its own.

    Our record of one machine at one moment. Warmed the way `evaluate.py`
    warms - the whole split run once and discarded, then the measured passes -
    a condition stated here rather than in a sentence underneath that an edit
    can drop.
    """
    passes = report.get("latency_conditions", {}).get("passes", 1)
    out = ["| setting | p50 | p95 |", "|---|---|---|"]
    for r in report["rows"]:
        lat = r["latency_ms"]
        out.append(f"| {setting_name(r)} | {metrics.fmt_latency(lat.get('p50'))} "
                   f"| {metrics.fmt_latency(lat.get('p95'))} |")
    note = (f"Median of {passes} warm pass{'es' if passes != 1 else ''} over "
            f"{report['queries']} queries, after one warm-up pass over the "
            f"whole query set was discarded. " + WARM_NOTE)
    return "\n".join(out) + "\n\n" + textwrap.fill(note, 79) + "\n"


BLOCKS = {"ann-sweep": ann_sweep_block,
          "ann-sweep-latency": ann_sweep_latency_block}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--split", choices=builds.SPLITS, required=True)
    ap.add_argument("--block", choices=sorted(BLOCKS), default="ann-sweep",
                    help="which finished block goes to stdout; one per run, "
                         "because a swap replaces a marked region with stdout "
                         "whole")
    ap.add_argument("--hits", type=int, default=100)
    ap.add_argument("--queries", type=int, default=None,
                    help="cap on how many queries to sweep, for a smoke run "
                         "only; default is every query of the split")
    ap.add_argument("--passes", type=int, default=3,
                    help="warm once per setting (discarded), then this many "
                         "measured passes; agreement/ndcg come from the "
                         "first, p50/p95 are the median over every pass's "
                         "own")
    ap.add_argument("--explore", type=int, nargs="+", default=[20, 100, 500],
                    help="hnsw.exploreAdditionalHits settings to try, beyond "
                         "the default HNSW row (which is always included, "
                         "first and last)")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--out", type=Path, default=None,
                    help="where the report goes; defaults to this chapter's "
                         "expected/ directory, named for the split. A script "
                         "whose report has to be asked for produces numbers "
                         "nobody captured")
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    metavar="REPORT",
                    help="print --block from a report this tool already "
                         "wrote, measuring nothing: one sweep, two blocks, "
                         "and the second block cannot drift from the first "
                         "because it is the same file")
    args = ap.parse_args()
    if args.from_report:
        report = json.loads(args.from_report.read_text())
        if report.get("split") != args.split:
            raise SystemExit(f"{args.from_report} is a {report.get('split')!r} "
                             f"report; --split says {args.split!r}")
        print(BLOCKS[args.block](report))
        return 0
    if args.passes < 1:
        raise SystemExit(f"--passes must be at least 1, got {args.passes}")
    out = args.out or (Path(__file__).resolve().parent / "expected" / f"{args.split}-ann-sweep.json")
    build = args.build or builds.latest()

    app = Vespa(args.endpoint)
    queries = builds.load_queries(build, args.split)
    judgements = builds.load_judgements(build, args.split)
    ids = sorted(queries) if args.queries is None else sorted(queries)[:args.queries]

    rows: list[dict] = []
    truth: dict[str, list[str]] | None = None
    for name, approximate, explore in setting_rows(args.explore):
        print(f"{name}{' (exact)' if not approximate else ''}: warming, then "
              f"{args.passes} measured pass{'es' if args.passes != 1 else ''} "
              f"over {len(ids)} queries", file=sys.stderr)
        results, client_ms_per_pass = sweep_setting(
            app, ids, queries, approximate=approximate, explore=explore or 0,
            hits=args.hits, ranking="semantic", passes=args.passes, label=name)

        if truth is None:
            truth = results  # the exact row is always first

        agree10, agreeN, ndcgs = [], [], []
        for qid in ids:
            hit_ids, t = results[qid], truth[qid]
            agree10.append(len(set(hit_ids[:10]) & set(t[:10])) / max(1, len(t[:10])))
            agreeN.append(len(set(hit_ids) & set(t)) / max(1, len(t)))
            if judgements.get(qid):
                ndcgs.append(metrics.ndcg_at_k(hit_ids, judgements[qid], 10))

        per_pass = [metrics.percentiles(cm) for cm in client_ms_per_pass]
        latency_ms = {}
        for stat in ("mean", "p50", "p95", "p99", "max"):
            values = [p[stat] for p in per_pass if stat in p]
            if values:
                latency_ms[stat] = round(statistics.median(values), 2)

        rows.append({
            "setting": "exact" if not approximate else f"hnsw+{explore or 0}",
            "explore_additional_hits": explore if approximate else None,
            "agreement_at_10": round(statistics.fmean(agree10), 4),
            "agreement_at_hits": round(statistics.fmean(agreeN), 4),
            "ndcg10": round(statistics.fmean(ndcgs), 4) if ndcgs else None,
            "latency_ms": latency_ms,
        })

    print(f"\n{'setting':16} {'agree@10':>9} {'agree@100':>10} {'ndcg@10':>8} "
          f"{'p50':>9} {'p95':>9}", file=sys.stderr)
    print("-" * 64, file=sys.stderr)
    for r in rows:
        print(f"{setting_name(r):16} "
              f"{metrics.fmt_metric(r['agreement_at_10']):>9} "
              f"{metrics.fmt_metric(r['agreement_at_hits']):>10} "
              f"{metrics.fmt_metric(r['ndcg10']):>8} "
              f"{metrics.fmt_latency(r['latency_ms'].get('p50')):>9} "
              f"{metrics.fmt_latency(r['latency_ms'].get('p95')):>9}", file=sys.stderr)

    report = {
        "build": builds.meta(build)["build_id"],
        # Which model was in the index when this was measured, asked of
        # the running system. These scripts query whatever container is
        # up and deploy nothing, so without this the report cannot say
        # what it was measured against.
        **deployed.stamp(),
        "split": args.split,
        "queries": len(ids),
        "hits": args.hits,
        "field": FIELD,
        "note": "agreement is overlap with brute-force search, not relevance",
        "rows": rows,
        # p50/p95 in each row are the median over these many measured
        # passes, each warmed by one discarded pass over the whole split.
        "latency_conditions": {"warm": True, "passes": args.passes},
        "host": hostinfo.collect(),
    }
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote {out}", file=sys.stderr)
    print(BLOCKS[args.block](report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
