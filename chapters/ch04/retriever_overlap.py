"""What each way of searching finds that the other does not.

Comparing two searches by a single quality score hides the thing that matters
here. Keyword search and vector search can land on the same number while
reaching different products: one matches the words, the other matches something
closer to the meaning, and a query where one fails is often a query where the
other does not.

So this counts, for every relevant product, which of the two found it - both,
one, or neither. The overlap is what says whether combining them could help,
and how much room there is to gain.

    python chapters/ch04/retriever_overlap.py --split validation

Stdout is the block the chapter carries. The examples of products only the
vector search reached are for whoever is running this and go to stderr - they
are in the report too, and a swap that replaces a marked region with stdout
would otherwise put four product titles into the book underneath the counts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))

import builds                    # noqa: E402
import deployed                     # noqa: E402
import hostinfo                  # noqa: E402
from evaluate import build_request  # noqa: E402
from query import Vespa          # noqa: E402


def overlap_block(report: dict) -> str:
    """Which search reached each relevant product, as the block for the page.

    Four counts and the share each is of the total, with the total printed
    above them so a reader can redo every division in the paragraph beside it.
    Counts of judged products: a reader running the command gets the same ones,
    so this block is theirs to replace and carries no cost figure.
    """
    total = report["relevant_products"]
    rows = [("found by both", report["found_by_both"]),
            ("only by keyword", report["found_by_keyword_only"]),
            ("only by vector", report["found_by_vector_only"]),
            ("found by neither", report["found_by_neither"])]
    out = [f"relevant products  {total:>10,}"]
    for name, value in rows:
        share = f"{value / total:>5.1%}" if total else "    -"
        out.append(f"  {name:<18} {value:>8,}   {share}")
    # The net, printed rather than subtracted on the page (§7: a derived value
    # is the tool's or it is not written): how many more relevant products
    # the vector side reaches at this depth than the keyword side does.
    net = report["found_by_vector_only"] - report["found_by_keyword_only"]
    out.append(f"  {'vector finds more, net':<18} {net:>+8,}")
    return "```\n" + "\n".join(out) + "\n```\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--split", choices=builds.SPLITS, required=True)
    ap.add_argument("--hits", type=int, default=100)
    ap.add_argument("--lexical-ranking", default="bm25_tuned")
    ap.add_argument("--semantic-ranking", default="semantic")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--examples", type=int, default=6)
    ap.add_argument("--out", type=Path, default=None,
                    help="where the report goes; defaults to this chapter's "
                         "expected/ directory, named for the split. A script "
                         "whose report has to be asked for produces numbers "
                         "nobody captured")
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    metavar="REPORT",
                    help="print the block from a report this tool already "
                         "wrote, measuring nothing")
    args = ap.parse_args()
    if args.from_report:
        report = json.loads(args.from_report.read_text())
        if report.get("split") != args.split:
            raise SystemExit(f"{args.from_report} is a {report.get('split')!r} "
                             f"report; --split says {args.split!r}")
        print(overlap_block(report))
        return 0
    out = args.out or (Path(__file__).resolve().parent / "expected" / f"{args.split}-overlap.json")
    build = args.build or builds.latest()

    app = Vespa(args.endpoint)
    queries = builds.load_queries(build, args.split)
    judgements = builds.load_judgements(build, args.split)

    both = lexical_only = semantic_only = neither = 0
    exact_semantic_only: list[dict] = []
    per_query_union_gain: list[float] = []

    for n, (qid, text) in enumerate(sorted(queries.items()), 1):
        judged = judgements.get(qid, {})
        relevant = {d for d, g in judged.items() if g > 0}
        if not relevant:
            continue

        found = {}
        for name, ranking in (("lexical", args.lexical_ranking),
                              ("semantic", args.semantic_ranking)):
            r = app.query(ranking=ranking, hits=args.hits,
                          **build_request(name, text, args.hits))
            found[name] = {h.fields.get("id") for h in r.hits} & relevant

        b = found["lexical"] & found["semantic"]
        lo = found["lexical"] - found["semantic"]
        so = found["semantic"] - found["lexical"]
        ne = relevant - found["lexical"] - found["semantic"]
        both += len(b)
        lexical_only += len(lo)
        semantic_only += len(so)
        neither += len(ne)

        union = len(b) + len(lo) + len(so)
        per_query_union_gain.append(union / len(relevant))

        for doc in sorted(so):
            if judged[doc] >= 1.0 and len(exact_semantic_only) < args.examples:
                d = app.query(f'select title from product where id contains "{doc}"',
                              hits=1)
                exact_semantic_only.append({
                    "query": text,
                    "product": d.hits[0].fields.get("title", "")[:100] if d.hits else doc,
                })
        if n % 40 == 0:
            print(f"  {n}/{len(queries)} queries", file=sys.stderr, flush=True)

    total = both + lexical_only + semantic_only + neither
    report = {
        "build": builds.meta(build)["build_id"],
        # Which model was in the index when this was measured, asked of
        # the running system. These scripts query whatever container is
        # up and deploy nothing, so without this the report cannot say
        # what it was measured against - and four of
        # them could not.
        **deployed.stamp(),
        "split": args.split,
        "hits": args.hits,
        "relevant_products": total,
        "found_by_both": both,
        "found_by_keyword_only": lexical_only,
        "found_by_vector_only": semantic_only,
        "found_by_neither": neither,
        "share_found_by_either": round((total - neither) / total, 4) if total else 0,
        "examples_only_vector_found": exact_semantic_only,
        "host": hostinfo.collect(),
    }

    print(f"\neither one would have found {report['share_found_by_either']:.1%}; "
          f"each alone finds less", file=sys.stderr)
    if exact_semantic_only:
        print("\nperfect matches only the vector search reached:", file=sys.stderr)
        for e in exact_semantic_only[:4]:
            print(f'  "{e["query"]}"', file=sys.stderr)
            print(f'    {e["product"]}', file=sys.stderr)

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote {out}", file=sys.stderr)
    print(overlap_block(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
