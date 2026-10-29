"""Did the wider net move? Of the products only one retriever reached, how
many does a fused profile actually surface.

Chapter 4 found that vector search reaches relevant products keyword search
misses at depth 100, and keyword search reaches a smaller number vector search
misses (`retriever_overlap.py`, `reach.py`). It also found that a wider net at
depth 100 is not the same as a better top ten: nothing said whether those
extra products ever climb into the ranks a person - or a generator building a
RAG context - would actually see. This chapter's premise is that fusion is one
way to find out.

The method is ch04's `retriever_overlap.py`, recomputed here rather than
imported - that file stays chapter 4's own, and a number this chapter needs
from it is a number this chapter measures again on its own request, not one
borrowed from a report chapter 4 already froze. For every query, the relevant
(judged, gain > 0) products are split into **vector-only** (found by `semantic`
at depth 100 via `evaluate.build_request("semantic", ...)`, not by
`bm25_tuned`) and **keyword-only** (the reverse), using the same two single-arm
requests ch04 used.

Then, for each profile in `--profiles`, the *union* request
(`evaluate.build_request("hybrid", ...)`, hits 100 - the candidate set every
profile in this chapter actually sees) is sent under that profile, and this
counts how many of the vector-only and keyword-only products from above land
in that profile's own top 10 and top 100.

`bm25_tuned` is not in the default profiles, and not because it would score
badly: by construction every vector-only product is one `bm25_tuned`'s own
top 100 did not hold, so its two vector-only cells would read 0 / 0 before
anything ran. It
also declares no `query(q)` input, so the union request - which carries one -
is refused for it. `semantic` is in the defaults for the mirror reason:
every vector-only product is in its own vector-only top 100 by definition,
and under the union request it still keeps almost all of them in its top 100,
so the informative number is how many it puts in the top ten. `hybrid_starved`
is there to show what a starved first phase does to the same counts.

    .venv/bin/python chapters/ch05/wider_net.py --split validation --out validation-wider-net.json
    .venv/bin/python chapters/ch05/wider_net.py --split validation --alpha 0.3 --out validation-wider-net-alpha03.json

Without `--out` the report is written to `chapters/ch05/expected/`, over the
shipped one.

Stdout is the `wider-net` block the chapter carries: the two set sizes above
one row per profile. No interval - this book's metric set carries no
bootstrap for overlap counts, only for score differences.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))

import builds                       # noqa: E402
import deployed                     # noqa: E402
import hostinfo                     # noqa: E402
from evaluate import build_request  # noqa: E402
from query import Vespa             # noqa: E402

DEFAULT_PROFILES = ("hybrid_rrf", "hybrid_linear", "hybrid_starved", "semantic")


def reached_sets(app: Vespa, queries: dict[str, str], judgements: dict[str, dict[str, float]],
                 *, hits: int, lexical_ranking: str, semantic_ranking: str
                 ) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Per query: the relevant products only `semantic` reaches at this depth,
    and the relevant products only `lexical_ranking` reaches - ch04's method
    (`retriever_overlap.py`), recomputed rather than imported.
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
                   *, profile: str, hits: int, alpha: float | None = None) -> dict[str, int]:
    """How many of the vector-only and keyword-only relevant products land in
    this profile's own top 10 / top 100, under the union request every
    profile in this chapter actually sees.
    """
    v10 = v100 = k10 = k100 = 0
    params = {"input.query(alpha)": alpha} if alpha is not None else {}
    for n, (qid, text) in enumerate(sorted(queries.items()), 1):
        vo, ko = vector_only.get(qid), keyword_only.get(qid)
        if not vo and not ko:
            continue
        r = app.query(ranking=profile, hits=hits,
                      **build_request("hybrid", text, hits), **params)
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
    """One row per profile, as the finished block for the page.

    The two set sizes go above the table, printed rather than left for a
    reader to sum from the rows (a derived value is the tool's or it is
    not written). No interval: this book's metric set carries a
    bootstrap for score differences, not for overlap counts, which are exact
    - ch04's `retriever_overlap.py` block makes the same choice.
    """
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
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--block", choices=("wider-net",), default="wider-net",
                    help="which finished block goes to stdout; one so far")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    if args.from_report is not None:
        print(wider_net_block(json.loads(args.from_report.read_text())))
        return 0
    if args.split is None:
        ap.error("--split is required (no default: choosing a split is a decision)")

    if args.alpha is not None and "hybrid_linear" not in args.profiles:
        raise SystemExit(
            "--alpha only affects hybrid_linear; put hybrid_linear in "
            "--profiles or drop --alpha")

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
        print(f"  {profile}", file=sys.stderr, flush=True)
        counts = profile_counts(app, queries, vector_only, keyword_only,
                                profile=profile, hits=args.hits, alpha=alpha)
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
        "vector_only_relevant_products": vector_only_total,
        "keyword_only_relevant_products": keyword_only_total,
        "rows": rows,
        "host": hostinfo.collect(),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nwrote {out}", file=sys.stderr)
    print(wider_net_block(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
