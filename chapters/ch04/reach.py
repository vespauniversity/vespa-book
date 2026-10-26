"""How much of chapter 3's blind spot semantic search actually reaches.

Chapter 3 ends with a count: products a shopper wanted that keyword search
could never find, because no word connects the query to the product. The
obvious next sentence is that vector search fixes this. It does not, and the
shape of how it fails is the useful part.

Two things are separated here that are easy to conflate:

**Whether the product is reachable at all** - does the vector search place it
anywhere in its results, or is it nowhere near the query even in the embedding
space.

**Whether you would see it** - a system that retrieves a hundred candidates
cannot rank something lying at position a hundred and fifty. Retrieval depth is
a parameter, and where it is cut decides what can possibly be ranked. That is
usually treated as a ranking concern and it is a retrieval one first.

    python chapters/ch04/reach.py --split validation
    python chapters/ch04/reach.py --split validation \
        --against chapters/ch04/expected/validation-overlap.json

**The block needs both runs**, which is what `--against` is. The split it
prints - of the products vector search finds and keyword search does not, how
many keyword search could never have matched - is one number from here and one
from `retriever_overlap.py`, and the subtraction between them used to be done
in prose. Done by hand, that subtraction invites one rounded share written
against both rows although the two rows have different denominators - two
different quantities rounding to the same characters, with nothing saying
which denominator was meant. The arithmetic is here now, and so is the refusal
that goes with it - two reports are only a split of one population if they
agree on the build, the embedding model and the split they were measured on.

Without `--against` this measures, writes its report, and prints no block:
there is no single-report block on this page, and inventing one would be a
different table from the one the chapter carries.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))

import builds                       # noqa: E402
import deployed                     # noqa: E402
import hostinfo                     # noqa: E402
from evaluate import build_request  # noqa: E402
from query import Vespa             # noqa: E402

# Vespa refuses more than this per query unless the query profile raises it.
VESPA_HIT_LIMIT = 400


def refuse_if_silently_capped(response, depth: int) -> None:
    """A query profile can cap `hits` below what was asked without Vespa
    refusing the request - fewer rows come back and nothing on the wire says
    why. `response.total` is how many matched in total, independent of how
    many were returned, so a request for `depth` that matched at least that
    many but returned fewer is exactly that silent cap - and this is a "how
    deep is it ranked" measurement, where fewer rows read as a smaller number
    rather than as a broken request.
    """
    if response.total >= depth and len(response.hits) < depth:
        raise SystemExit(
            f"asked for {depth} hits and got {len(response.hits)} back, "
            f"although {response.total} matched - the query profile is "
            f"silently capping hits below {depth}; raise its hits limit "
            f"before this tool can measure depth {depth}")


def unreachable_by_keyword(app: Vespa, text: str, relevant: set[str],
                           ranking: str, hits: int) -> set[str]:
    """Relevant products no keyword query could match, at any weight.

    The engine decides: the query is re-run against each missed product alone,
    and an empty result means its tokenisation and stemming find no word in
    common.
    """
    r = app.query(ranking=ranking, hits=hits, **build_request("lexical", text, hits))
    missed = relevant - {h.fields.get("id") for h in r.hits}
    out = set()
    for doc in sorted(missed):
        probe = app.query(
            f'select id from product where userQuery() and id contains "{doc}"',
            query=text, ranking=ranking, hits=1)
        if not probe.hits:
            out.add(doc)
    return out


def embedders_of(report: dict):
    """Which embedding models a report was measured against.

    `deployed_embedder` is being renamed `deployed_embedders`, because it was
    always a list of components written as one string and the singular name is
    how the ColBERT add-on's second component went unrecorded. Both spellings
    are read: every report committed before the rename carries the old one, and
    a guard that cannot read its own inputs is not a guard.
    """
    return report.get("deployed_embedders", report.get("deployed_embedder"))


def reach_split_block(reach: dict, overlap: dict, *, reach_name: str,
                      overlap_name: str) -> str:
    """What vector search adds, split by whether keyword could match at all.

    Two reports, so the first thing is whether they are two views of one
    population. They are only that if they agree on the corpus build, on the
    embedding model that was in the index, and on the split - and a
    disagreement on any of the three produces a difference that looks like a
    finding and is an artefact of measuring two different things.

    Counts, so this is a block a reader replaces by re-running both commands.
    """
    for field in ("build", "split"):
        a, b = reach.get(field), overlap.get(field)
        if a != b:
            raise SystemExit(
                f"{reach_name} and {overlap_name} disagree on {field}: "
                f"{a!r} vs {b!r}. A split across two reports is only a split "
                f"if both measured the same thing.")
    a, b = embedders_of(reach), embedders_of(overlap)
    if a != b:
        raise SystemExit(
            f"{reach_name} and {overlap_name} disagree on "
            f"deployed_embedders: {a!r} vs {b!r}. A split across two reports "
            f"is only a split if both measured the same thing.")

    depth = overlap["hits"]
    if str(depth) not in reach["reached_at_depth"]:
        raise SystemExit(
            f"{overlap_name} counted what each search reached in the first "
            f"{depth}, and {reach_name} never measured that depth (it has "
            f"{sorted(reach['reached_at_depth'])}). Re-run reach.py with "
            f"--depths including {depth}.")
    unmatchable = reach["reached_at_depth"][str(depth)]
    total = overlap["found_by_vector_only"]
    ranked_low = total - unmatchable
    if ranked_low < 0:
        raise SystemExit(
            f"more keyword-unmatchable products ({unmatchable}) than products "
            f"vector search finds alone ({total}); the two reports are not "
            f"measuring the same population")

    rows = [("no word in common - keyword could never match them", unmatchable),
            (f"matched, but ranked past {depth}", ranked_low)]
    out = [f'{"found by vector and not by keyword":<52}{total:>6,}']
    for name, value in rows:
        share = f"{value / total:>6.1%}" if total else "     -"
        out.append(f"  {name:<50} {value:>6,}   {share}")
    return "```\n" + "\n".join(out) + "\n```\n"


def reach_depths_block(report: dict) -> str:
    """How much of the keyword blind spot vector search reaches, by depth.

    One report, the reach run's own: the blind spot as the engine counted it,
    how many of those are graded Exact, and how many vector search places in
    the top 100 / 200 / 400. Shares are of the blind spot, printed here so the
    page does not divide by hand - two different denominators once rounded to
    the same two characters on this very table (module docstring).
    """
    total = report["keyword_blind_spot"]
    exact = report["of_which_perfect_matches"]
    depths = sorted(int(d) for d in report["reached_at_depth"])
    def share(n): return f"{n / total:.1%}" if total else "—"
    out = ["| blind spot | products | share of the blind spot |", "|---|---|---|",
           f"| relevant products keyword search can never match | {total:,} | — |",
           f"| of which graded Exact | {exact:,} | {share(exact)} |"]
    for i, d in enumerate(depths):
        n = report["reached_at_depth"][str(d)]
        label = f"reached by vector search in the top {d}" if i == 0 else f"in the top {d}"
        out.append(f"| {label} | {n:,} | {share(n)} |")
    beyond = report["beyond_depth"]
    out.append(f"| not in the top {depths[-1]} | {beyond:,} | {share(beyond)} |")
    return "\n".join(out) + "\n"


BLOCKS = ("reach-split", "reach-depths")


def emit_block(args, report: dict) -> int:
    """Print the one block asked for; stdout carries nothing else."""
    if args.block == "reach-depths":
        print(reach_depths_block(report))
        return 0
    if args.against:
        overlap = json.loads(args.against.read_text())
        print(reach_split_block(report, overlap, reach_name="this run",
                                overlap_name=args.against.name))
    else:
        print("no --against, so no block: the split the chapter shows needs "
              "this run and a retriever_overlap.py report together.",
              file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--against", type=Path, default=None,
                    help="a retriever_overlap.py report from the same build, "
                         "model and split; with it this prints the split block "
                         "the chapter carries")
    ap.add_argument("--split", choices=builds.SPLITS, required=True)
    ap.add_argument("--hits", type=int, default=100,
                    help="the depth keyword search is judged at")
    ap.add_argument("--depths", type=int, nargs="+", default=[100, 200, 400])
    ap.add_argument("--lexical-ranking", default="bm25_tuned")
    ap.add_argument("--semantic-ranking", default="semantic",
                    help="the rank profile used for the semantic side")
    ap.add_argument("--retriever", default="semantic")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--examples", type=int, default=6)
    ap.add_argument("--out", type=Path, default=None,
                    help="where the report goes; defaults to this chapter's "
                         "expected/ directory, named for the split. A script "
                         "whose report has to be asked for produces numbers "
                         "nobody captured")
    ap.add_argument("--block", choices=BLOCKS, default="reach-split",
                    help="which finished block goes to stdout: `reach-split` "
                         "needs --against (the overlap report), `reach-depths` "
                         "needs only this run's report")
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    metavar="REPORT",
                    help="print --block from a report this tool already "
                         "wrote, measuring nothing")
    args = ap.parse_args()
    if args.from_report:
        report = json.loads(args.from_report.read_text())
        if report.get("split") != args.split:
            raise SystemExit(f"{args.from_report} is a {report.get('split')!r} "
                             f"report; --split says {args.split!r}")
        return emit_block(args, report)
    out = args.out or (Path(__file__).resolve().parent / "expected" / f"{args.split}-reach.json")
    build = args.build or builds.latest()
    depth = min(max(args.depths), VESPA_HIT_LIMIT)

    app = Vespa(args.endpoint)
    queries = builds.load_queries(build, args.split)
    judgements = builds.load_judgements(build, args.split)

    total = beyond = 0
    exact_total = exact_reached = 0
    at_depth = {d: 0 for d in args.depths}
    ranks: list[int] = []
    examples: list[dict] = []

    for n, qid in enumerate(sorted(queries), 1):
        text = queries[qid]
        judged = judgements.get(qid, {})
        relevant = {d for d, g in judged.items() if g > 0}
        if not relevant:
            continue
        blind = unreachable_by_keyword(app, text, relevant,
                                       args.lexical_ranking, args.hits)
        if not blind:
            continue

        deep = app.query(ranking=args.semantic_ranking, hits=depth,
                         **build_request(args.retriever, text, depth))
        refuse_if_silently_capped(deep, depth)
        position = {h.fields.get("id"): i + 1 for i, h in enumerate(deep.hits)}

        for doc in sorted(blind):
            total += 1
            is_exact = judged[doc] >= 1.0
            exact_total += is_exact
            rank = position.get(doc)
            if rank is None:
                beyond += 1
                continue
            ranks.append(rank)
            exact_reached += is_exact
            for d in args.depths:
                if rank <= d:
                    at_depth[d] += 1
            if len(examples) < args.examples:
                t = app.query(f'select title from product where id contains "{doc}"',
                              hits=1)
                examples.append({
                    "query": text, "rank": rank, "grade": judged[doc],
                    "product": t.hits[0].fields.get("title", "")[:90] if t.hits else doc})
        if n % 40 == 0:
            print(f"  {n}/{len(queries)} queries", file=sys.stderr, flush=True)

    report = {
        "build": builds.meta(build)["build_id"],
        # Which model was in the index when this was measured, asked of
        # the running system. These scripts query whatever container is
        # up and deploy nothing, so without this the report cannot say
        # what it was measured against - and four of
        # them could not.
        **deployed.stamp(),
        "split": args.split,
        # The depth the keyword side was judged at, so the report says what
        # `reached_at_depth` is a reach *past*. It was not recorded, and the
        # renderer that used to do this split defaulted to 100 when it was
        # missing - a default that is right until somebody passes --hits.
        "hits": args.hits,
        "semantic_ranking": args.semantic_ranking,
        "retriever": args.retriever,
        "keyword_blind_spot": total,
        "of_which_perfect_matches": exact_total,
        "reached_at_depth": {str(d): at_depth[d] for d in args.depths},
        "share_at_depth": {str(d): round(at_depth[d] / total, 4) if total else 0
                           for d in args.depths},
        "beyond_depth": beyond,
        "perfect_matches_reached": exact_reached,
        "rank_median": statistics.median(ranks) if ranks else None,
        "rank_best": min(ranks) if ranks else None,
        "rank_worst": max(ranks) if ranks else None,
        "examples": examples,
        "host": hostinfo.collect(),
    }

    print(f"\nproducts keyword search can never reach: {total:,}"
          f"  ({exact_total:,} of them a perfect match)", file=sys.stderr)
    for d in args.depths:
        print(f"  vector search puts it in the top {d:>4}: {at_depth[d]:4}"
              f"  ({at_depth[d] / total:5.1%})" if total else "", file=sys.stderr)
    print(f"  below rank {depth}, or not returned:      {beyond:4}"
          f"  ({beyond / total:5.1%})" if total else "", file=sys.stderr)
    if ranks:
        print(f"\nof the {len(ranks)} it does reach: median rank "
              f"{statistics.median(ranks):.0f}, best {min(ranks)}, "
              f"worst {max(ranks)}", file=sys.stderr)
        print("Depth is a parameter. Where it is cut decides what can be ranked.",
              file=sys.stderr)

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote {out}", file=sys.stderr)

    return emit_block(args, report)


if __name__ == "__main__":
    raise SystemExit(main())
