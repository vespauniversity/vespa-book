"""Did the wider net still climb into the top ten once a funnel reranks it?

Chapter 5 asked whether fusion moves vector-only and keyword-only relevant
products into the top ten and top hundred. This chapter's funnel reranks on
top of ch05's own first stage (`phased` inherits `hybrid_rrf`), so the
same count answers whether reranking carries the wider net into the top
ten: is the reranked top ten the same products ch05 already found
reordered, or does reranking finally lift some of the vector-only survivors
in.

Adapted from `chapters/ch05/wider_net.py`, which stays ch05's own. Copied
rather than imported: ch05 is published and its README's commands must keep
working byte for byte, so a fix or an extension here cannot reach back into
that file. What is new relative to
the ch05 copy:

- `--profiles` defaults to `phased hybrid_linear hybrid_rrf semantic` -
  `phased` in the set this chapter cares about, `hybrid_linear` / `hybrid_rrf`
  as ch05's own reference rows recomputed on this container, `semantic` for
  the same reason ch05 kept it: every vector-only product is in its own
  vector-only top 100 by definition, and under the union request it still
  keeps almost all of them in its top 100.
- `--param KEY=VALUE` (repeatable), applied only to `phased` requests - the
  two rerank knobs (`ranking.rerankCount`, `ranking.globalPhase.rerankCount`),
  so this can be pointed at whichever counts the sweeps choose without a
  second copy of this file.
- the `qt` / `qt_cross` reranker inputs are added whenever the profile being
  measured is `phased` (`chapters/ch06/funnel.build_phased_request`) - without
  them the funnel's second and global phases score with an empty tensor and
  MaxSim is silently 0, which would not fail the request and would look like
  a `phased` row that reranked nothing.

    .venv/bin/python chapters/ch06/wider_net.py --split validation
    .venv/bin/python chapters/ch06/wider_net.py --split validation \\
        --param ranking.rerankCount=100 --param ranking.globalPhase.rerankCount=50

Stdout is the `wider-net` block, unchanged in shape from ch05's: the two set
sizes above one row per profile, no interval (the book's bootstrap covers
score differences, not overlap counts).
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
from evaluate import build_request, parse_params  # noqa: E402
from query import Vespa              # noqa: E402

DEFAULT_PROFILES = ("phased", "hybrid_linear", "hybrid_rrf", "semantic")


def reached_sets(app: Vespa, queries: dict[str, str], judgements: dict[str, dict[str, float]],
                 *, hits: int, lexical_ranking: str, semantic_ranking: str
                 ) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Per query: the relevant products only `semantic` reaches at this depth,
    and the relevant products only `lexical_ranking` reaches - ch04's method
    (`retriever_overlap.py`) by way of ch05's `wider_net.py`, recomputed
    rather than imported.
    """
    vector_only: dict[str, set[str]] = {}
    keyword_only: dict[str, set[str]] = {}
    for n, (qid, text) in enumerate(sorted(queries.items()), 1):
        relevant = {d for d, g in judgements.get(qid, {}).items() if g > 0}
        if not relevant:
            continue
        found = {}
        for name, ranking, retriever in (("lexical", lexical_ranking, "lexical"),
                                         ("semantic", semantic_ranking, "semantic")):
            r = app.query(ranking=ranking, hits=hits,
                          **build_request(retriever, text, hits))
            found[name] = {h.fields.get("id") for h in r.hits} & relevant
        vector_only[qid] = found["semantic"] - found["lexical"]
        keyword_only[qid] = found["lexical"] - found["semantic"]
        if n % 40 == 0:
            print(f"  {n}/{len(queries)} queries (reach)", file=sys.stderr, flush=True)
    return vector_only, keyword_only


def profile_counts(app: Vespa, queries: dict[str, str],
                   vector_only: dict[str, set[str]], keyword_only: dict[str, set[str]],
                   *, profile: str, hits: int, alpha: float | None = None,
                   extra_params: dict[str, str] | None = None) -> dict[str, int]:
    """How many of the vector-only and keyword-only relevant products land in
    this profile's own top 10 / top 100, under the union request every
    profile in this chapter actually sees.

    `extra_params` (this chapter's `--param`) and the two reranker inputs are
    only added when `profile == "phased"` - every other profile in
    `DEFAULT_PROFILES` declares no `qt` / `qt_cross` input and no rerank
    knob, and sending them would be a parameter with no effect, the same bug
    class `--param` without `input.` was in chapter 3.
    """
    v10 = v100 = k10 = k100 = 0
    params = dict(extra_params or {})
    if alpha is not None:
        params["input.query(alpha)"] = alpha
    for n, (qid, text) in enumerate(sorted(queries.items()), 1):
        vo, ko = vector_only.get(qid), keyword_only.get(qid)
        if not vo and not ko:
            continue
        if profile == "phased":
            request = funnel.build_phased_request(text, hits)
        else:
            request = build_request("hybrid", text, hits)
        r = app.query(ranking=profile, hits=hits, **request, **params)
        ids = [h.fields.get("id", "") for h in r.hits]
        top10, top100 = set(ids[:10]), set(ids[:100])
        v10 += len(vo & top10)
        v100 += len(vo & top100)
        k10 += len(ko & top10)
        k100 += len(ko & top100)
        if n % 100 == 0:
            print(f"    {profile} {n}/{len(queries)} queries", file=sys.stderr, flush=True)
    return {"vector_only_in_top10": v10, "vector_only_in_top100": v100,
            "keyword_only_in_top10": k10, "keyword_only_in_top100": k100}


def wider_net_block(report: dict) -> str:
    """One row per profile, as the finished block for the page - unchanged in
    shape from `chapters/ch05/wider_net.py`'s own block."""
    out = [f"vector-only relevant products   {report['vector_only_relevant_products']:>8,}",
          f"keyword-only relevant products  {report['keyword_only_relevant_products']:>8,}",
          "",
          "| profile | vector-only in top 10 | vector-only in top 100 | "
          "keyword-only in top 10 | keyword-only in top 100 |",
          "|---|---|---|---|---|"]
    for r in report["rows"]:
        out.append(f"| {r['profile']} | {r['vector_only_in_top10']:,} | "
                   f"{r['vector_only_in_top100']:,} | "
                   f"{r['keyword_only_in_top10']:,} | {r['keyword_only_in_top100']:,} |")
    return "\n".join(out) + "\n"


# A dict, not a bare call: one entry today, but `--block` is read
# through it rather than printed unconditionally - `chapters/ch05/
# wider_net.py`'s `--block` is accepted and never looked at again, an
# accepted-but-ignored flag this file does not repeat.
BLOCKS = {"wider-net": wider_net_block}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    help="print the block from a report this command wrote "
                         "earlier, without querying anything")
    ap.add_argument("--split", choices=builds.SPLITS, required=False)
    ap.add_argument("--hits", type=int, default=100)
    ap.add_argument("--lexical-ranking", default="bm25_tuned")
    ap.add_argument("--semantic-ranking", default="semantic")
    ap.add_argument("--profiles", nargs="+", default=list(DEFAULT_PROFILES))
    ap.add_argument("--alpha", type=float, default=None,
                    help="input.query(alpha) for hybrid_linear; refused if "
                         "hybrid_linear is not in --profiles, since a flag "
                         "with no effect on the run is a bug")
    ap.add_argument("--param", action="append", default=None, metavar="KEY=VALUE",
                    help="an extra query parameter, repeatable, applied only "
                         "to `phased` requests - e.g. --param "
                         "ranking.rerankCount=100 --param "
                         "ranking.globalPhase.rerankCount=50. Refused if "
                         "`phased` is not in --profiles")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--block", choices=("wider-net",), default="wider-net",
                    help="which finished block goes to stdout; one so far")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    if args.from_report is not None:
        print(BLOCKS[args.block](json.loads(args.from_report.read_text())))
        return 0
    if args.split is None:
        ap.error("--split is required (no default: choosing a split is a decision)")

    if args.alpha is not None and "hybrid_linear" not in args.profiles:
        raise SystemExit(
            "--alpha only affects hybrid_linear; put hybrid_linear in "
            "--profiles or drop --alpha")
    extra_params = parse_params(args.param) if args.param else {}
    if extra_params and "phased" not in args.profiles:
        raise SystemExit(
            "--param only affects phased; put phased in --profiles or drop "
            "--param")

    build = args.build or builds.latest()
    app = Vespa(args.endpoint)
    queries = builds.load_queries(build, args.split)
    judgements = builds.load_judgements(build, args.split)
    print(f"{builds.describe(build)}\n{len(queries)} {args.split} queries\n",
          file=sys.stderr)

    vector_only, keyword_only = reached_sets(
        app, queries, judgements, hits=args.hits,
        lexical_ranking=args.lexical_ranking, semantic_ranking=args.semantic_ranking)
    vector_only_total = sum(len(v) for v in vector_only.values())
    keyword_only_total = sum(len(v) for v in keyword_only.values())
    print(f"\nvector-only relevant products: {vector_only_total:,}\n"
          f"keyword-only relevant products: {keyword_only_total:,}\n",
          file=sys.stderr)

    rows = []
    for profile in args.profiles:
        alpha = args.alpha if profile == "hybrid_linear" else None
        params = extra_params if profile == "phased" else None
        print(f"  {profile}", file=sys.stderr, flush=True)
        counts = profile_counts(app, queries, vector_only, keyword_only,
                                profile=profile, hits=args.hits, alpha=alpha,
                                extra_params=params)
        rows.append({"profile": profile, **counts})

    out = args.out or (Path(__file__).resolve().parent / "expected" /
                       f"{args.split}-wider-net.json")
    report = {
        "build": builds.meta(build)["build_id"],
        **deployed.stamp(),
        "split": args.split,
        "hits": args.hits,
        "lexical_ranking": args.lexical_ranking,
        "semantic_ranking": args.semantic_ranking,
        "alpha": args.alpha,
        "phased_params": extra_params or None,
        "vector_only_relevant_products": vector_only_total,
        "keyword_only_relevant_products": keyword_only_total,
        "rows": rows,
        "host": hostinfo.collect(),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nwrote {out}", file=sys.stderr)
    print(BLOCKS[args.block](report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
