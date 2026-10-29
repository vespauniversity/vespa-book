"""How much does the fusion weighting matter, and where should it sit?

`hybrid_linear` combines a normalised lexical score with a normalised vector
score, and `alpha` says how much of the first to use. It is a query input rather
than a constant in the profile, so finding the right value is a sweep of query
parameters against one deployment - no redeploy, no re-feed.

Both ends are meaningful: alpha 1.0 is the lexical score alone, alpha 0.0 the
vector score alone, both still retrieved by the union of the two arms (the
same candidate set every alpha in between sees). Every row's ndcg@10 and
recall@100 are bracketed against those two endpoints, so the middle of the
sweep is read against what it is actually competing with, not against a
separately-run `bm25_tuned` or `semantic` report that answered a different
candidate set.

Use a split you are allowed to decide on. The chapter sweeps validation,
keeps `hybrid_linear`'s declared default and reports test once - the same
split discipline chapter 3 used for k1 and b - so this sweeps validation,
never test:

    .venv/bin/python chapters/ch05/alpha_sweep.py --split validation --out validation-alpha-sweep.json

Without `--out` the report is written to `chapters/ch05/expected/`, over the
shipped one.

**This names no winner.** On this sweep 0.3, 0.4 and 0.5 come out at 0.481,
0.482 and 0.479, and 735 queries cannot tell those apart. Picking the largest of
several numbers is not a measurement, and a bold row is read as a
recommendation, so what this emits instead is every row, every interval, and -
for each alpha - which other alphas the sample cannot distinguish it from.
Which one to deploy is a decision, and it is the reader's.

**The baseline row runs twice.** `--baseline-alpha` (default 0.3, the value
`hybrid_linear` declares as its own default) is measured once before every
other alpha in `--alphas` and once again after all of them, so the report
carries a check on whether the container drifted while the sweep ran rather
than assuming it did not.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))

import builds                       # noqa: E402
import deployed                     # noqa: E402
import evaluate                     # noqa: E402
import hostinfo                     # noqa: E402
import metrics                      # noqa: E402
from query import Vespa             # noqa: E402


def measure(app: Vespa, queries: dict[str, str], judgements: dict[str, dict[str, float]],
           *, hits: int, alpha: float
           ) -> tuple[dict[str, float], dict[str, float], list[float]]:
    """One pass over the queries under `hybrid_linear` at this alpha.

    The request is built through `evaluate.build_request("hybrid", ...)`, the
    same call every evaluation report in this chapter goes through - so the
    YQL here is the identical union of the two arms and the query prefix is
    `evaluate.QUERY_PREFIX` and nothing typed a second time in this file.
    """
    per_ndcg: dict[str, float] = {}
    per_recall: dict[str, float] = {}
    latency: list[float] = []
    for n, qid in enumerate(sorted(queries), 1):
        text = queries[qid]
        request = evaluate.build_request("hybrid", text, hits)
        started = time.perf_counter()
        r = app.query(ranking="hybrid_linear", hits=hits, **request,
                      **{"input.query(alpha)": alpha})
        latency.append((time.perf_counter() - started) * 1000)
        ids = [h.fields.get("id", "") for h in r.hits]
        judged = judgements.get(qid, {})
        per_ndcg[qid] = metrics.ndcg_at_k(ids, judged, 10)
        relevant = {d for d, g in judged.items() if g > 0}
        per_recall[qid] = metrics.recall_at_k(ids, relevant, 100)
        if n % 200 == 0:
            print(f"  {n}/{len(queries)}", file=sys.stderr, flush=True)
    return per_ndcg, per_recall, latency


def _finite(per_query: dict[str, float]) -> dict[str, float]:
    """Drop the queries a metric could not be computed for
    (`per_query_recall100` can carry a NaN for a query with nothing relevant,
    same as `evaluate.py`'s) so a mean or a bootstrap over the rest is not
    poisoned by one."""
    return {q: v for q, v in per_query.items() if not math.isnan(v)}


def _mean(per_query: dict[str, float]) -> float:
    finite = _finite(per_query)
    return statistics.fmean(finite.values()) if finite else float("nan")


def indistinguishable(per_alpha: dict[float, dict[str, float]]) -> dict[float, list[float]]:
    """For each alpha, the alphas this sample cannot tell it apart from.

    The paired bootstrap, every unordered pair once - `significant` is a
    property of the pair, not of its direction, so the other half of the matrix
    is the same answer with the sign flipped and is not worth the seconds.

    This is what replaces `best_alpha`. Deleting the field on its own would
    have left three rows reading 0.48 and nothing at all saying whether they
    differ, which is an invitation to pick the biggest by eye - the same act,
    now performed by the reader instead of by the script, with the script's
    authority removed and no information put in its place.
    """
    alphas = sorted(per_alpha)
    same: dict[float, list[float]] = {a: [] for a in alphas}
    for i, a in enumerate(alphas):
        for b in alphas[i + 1:]:
            d = metrics.bootstrap_delta(per_alpha[a], per_alpha[b])
            if d and not d["significant"]:
                same[a].append(b)
                same[b].append(a)
    return {a: sorted(v) for a, v in same.items()}


def alpha_block(report: dict) -> str:
    """The sweep, as the finished block that goes on the page.

    Nothing renders it from the report afterwards: this command prints it, the
    chapter marks where it goes, and a rerun replaces it whole.

    Every row's ndcg@10 and recall@100 each carry two brackets - against
    alpha 0.0 (vector alone on the union candidate set) and against alpha 1.0
    (lexical alone, same candidate set) - because those are the two things a
    point in the middle of the sweep is actually competing with, not a
    separately-measured `bm25_tuned` or `semantic` report. The endpoint rows
    print a dash for the bracket against themselves: comparing a row to
    itself is not a measurement.

    Three decimals, for the reason in `metrics.py`. This said two until
    2026-09-14, and this was the strongest case for it: the middle of this
    sweep reads 0.481 / 0.482 / 0.479, which looks like an ordering, where at
    two it read 0.48 / 0.48 / 0.48 - what 735 queries actually establish.
    That work is now done by the last column and the verdict on every row,
    which name each alpha's twins outright instead of blurring the digits
    until the ordering cannot be written.
    """
    out = ["| alpha | ndcg@10 | ndcg@10 vs vector-only (0.0) | ndcg@10 vs lexical-only (1.0) | "
           "recall@100 | recall@100 vs vector-only (0.0) | recall@100 vs lexical-only (1.0) | "
           "cannot be told apart from |",
           "|---|---|---|---|---|---|---|---|"]
    for r in report["rows"]:
        name = {0.0: "0.0 — vector only", 1.0: "1.0 — lexical only"}.get(
            r["alpha"], str(r["alpha"]))
        same = ", ".join(str(a) for a in r["indistinguishable_from"]) or "—"
        out.append(
            f"| {name} | {metrics.fmt_metric(r['ndcg10'])} | "
            f"{metrics.fmt_delta(r['vs_vector'])} | "
            f"{metrics.fmt_delta(r['vs_lexical'])} | "
            f"{metrics.fmt_metric(r['recall100'])} | "
            f"{metrics.fmt_delta(r['recall100_vs_vector'])} | "
            f"{metrics.fmt_delta(r['recall100_vs_lexical'])} | {same} |")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    help="print the block from a report this command wrote "
                         "earlier, without querying anything - the way a "
                         "block is re-rendered after its column names change")
    ap.add_argument("--split", choices=builds.SPLITS, required=False,
                    help="no default: choosing a weighting on test would make "
                         "test a second validation split")
    ap.add_argument("--alphas", type=float, nargs="+",
                    default=[0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0])
    ap.add_argument("--baseline-alpha", type=float, default=0.3,
                    help="the profile's own declared default for "
                         "input.query(alpha); measured first and last (both "
                         "kept in the report) regardless of whether it is "
                         "also in --alphas, as this sweep's own warm/drift "
                         "check")
    ap.add_argument("--hits", type=int, default=100)
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    if args.from_report is not None:
        print(alpha_block(json.loads(args.from_report.read_text())))
        return 0
    if args.split is None:
        ap.error("--split is required (no default: choosing a split is a decision)")

    alphas = sorted(set(args.alphas))
    if 0.0 not in alphas or 1.0 not in alphas:
        raise SystemExit(
            "--alphas must include both 0.0 and 1.0: every row's bracket is "
            "against those two endpoints (vector alone / lexical alone, both "
            "on the union candidate set), so without them there is nothing "
            "to bracket against")

    build = args.build or builds.latest()
    queries = builds.load_queries(build, args.split)
    judgements = builds.load_judgements(build, args.split)
    app = Vespa(args.endpoint)
    out = args.out or (Path(__file__).resolve().parent / "expected" /
                       f"{args.split}-alpha-sweep.json")
    print(f"{builds.describe(build)}\n{len(queries)} {args.split} queries\n",
          file=sys.stderr)

    baseline = args.baseline_alpha
    others = [a for a in alphas if a != baseline]

    print(f"baseline alpha {baseline} — first pass", file=sys.stderr, flush=True)
    base_first_ndcg, base_first_recall, _ = measure(
        app, queries, judgements, hits=args.hits, alpha=baseline)

    measured: dict[float, tuple[dict, dict]] = {baseline: (base_first_ndcg, base_first_recall)}
    for alpha in others:
        print(f"alpha {alpha}", file=sys.stderr, flush=True)
        ndcg_pq, recall_pq, _ = measure(app, queries, judgements, hits=args.hits, alpha=alpha)
        measured[alpha] = (ndcg_pq, recall_pq)

    print(f"baseline alpha {baseline} — last pass", file=sys.stderr, flush=True)
    base_last_ndcg, base_last_recall, _ = measure(
        app, queries, judgements, hits=args.hits, alpha=baseline)

    per_alpha_ndcg = {a: measured[a][0] for a in alphas}
    per_alpha_recall = {a: measured[a][1] for a in alphas}
    vector_ndcg, lexical_ndcg = _finite(per_alpha_ndcg[0.0]), _finite(per_alpha_ndcg[1.0])
    vector_recall, lexical_recall = _finite(per_alpha_recall[0.0]), _finite(per_alpha_recall[1.0])

    report = {"build": builds.meta(build)["build_id"],
              # Which model was in the index when this ran.
              **deployed.stamp(),
              "split": args.split,
              "hits": args.hits,
              "baseline_alpha": baseline,
              "rows": [], "host": hostinfo.collect()}

    for alpha in alphas:
        ndcg_pq = per_alpha_ndcg[alpha]
        recall_pq = _finite(per_alpha_recall[alpha])
        row = {
            "alpha": alpha,
            "ndcg10": round(_mean(ndcg_pq), 4),
            "recall100": round(_mean(per_alpha_recall[alpha]), 4),
            "vs_vector": None if alpha == 0.0 else metrics.bootstrap_delta(vector_ndcg, ndcg_pq),
            "vs_lexical": None if alpha == 1.0 else metrics.bootstrap_delta(lexical_ndcg, ndcg_pq),
            "recall100_vs_vector": (None if alpha == 0.0 else
                                    metrics.bootstrap_delta(vector_recall, recall_pq)),
            "recall100_vs_lexical": (None if alpha == 1.0 else
                                     metrics.bootstrap_delta(lexical_recall, recall_pq)),
        }
        report["rows"].append(row)
        print(f"alpha {alpha:<4} ndcg@10 {metrics.fmt_metric(row['ndcg10'])}  "
              f"recall@100 {metrics.fmt_metric(row['recall100'])}", file=sys.stderr)

    # Which alphas this sample cannot separate. Computed from the per-query
    # scores already in hand - no extra queries, and no ordering implied.
    print("\ncomparing every pair of alphas", file=sys.stderr, flush=True)
    same = indistinguishable(per_alpha_ndcg)
    for row in report["rows"]:
        row["indistinguishable_from"] = same[row["alpha"]]

    # The sweep's baseline row, run once before it started and once after
    # it finished, both kept - not averaged into one number, because the
    # question this answers is whether the two agree, not what their mean is.
    report["baseline_repeat"] = {
        "alpha": baseline,
        "ndcg10_first": round(_mean(base_first_ndcg), 4),
        "ndcg10_last": round(_mean(base_last_ndcg), 4),
        "delta": metrics.bootstrap_delta(_finite(base_first_ndcg), _finite(base_last_ndcg)),
    }
    print(f"\nbaseline alpha {baseline}: first {metrics.fmt_metric(report['baseline_repeat']['ndcg10_first'])}"
          f"  last {metrics.fmt_metric(report['baseline_repeat']['ndcg10_last'])}"
          f"  {metrics.fmt_delta(report['baseline_repeat']['delta'])}", file=sys.stderr)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nwrote {out}", file=sys.stderr)
    # The block goes to stdout on its own, so it can be piped, diffed or lifted
    # into the page. Everything else this command says goes to stderr.
    print(alpha_block(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
