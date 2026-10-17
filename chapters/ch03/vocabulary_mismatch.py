"""How much of what the search missed could never have been found.

A third of the relevant products never appear in the first hundred results.
Some of those were there and ranked too low, which is a tuning problem. Others
had no word in common with the query, and no amount of tuning reaches them.
This splits the two apart and counts the second group.

The point is to turn a claim into a number. "Keyword search cannot match a
meaning" is something anyone can assert; "of what it missed, about a quarter
could never have been found, and hundreds of those were the exactly right
product" is a reason to read the next chapter.

**The engine decides, not this script.** Each missed product is probed by
re-running the query against that one product alone. An empty result means the
engine's own tokenisation and stemming find no word in common - so it could not
have retrieved it at any weight. An earlier version compared regex-split word
sets and called `running shoe` and `Running Shoes` a mismatch, overstating the
problem. The engine is what would have to do the retrieving, so the engine is
what gets asked.

    python chapters/ch03/vocabulary_mismatch.py --split validation

**Stdout is the five-line block the chapter carries and nothing else.** The
worked examples underneath it - the queries and the products a lexical index
cannot reach - are for whoever is running this, and they go to stderr. They
used to be printed together, which mattered the moment the block became the
thing the chapter pastes: regenerating the page replaces the pasted block with
stdout, so five examples chosen by whatever ran first would have gone into the
book under the counts.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))

import builds                    # noqa: E402
import deployed                  # noqa: E402
import hostinfo                  # noqa: E402
from query import Vespa          # noqa: E402


def vocabulary_block(report: dict) -> str:
    """What lexical retrieval missed, as the finished block for the page.

    Chapter 3 showed this as terminal output and it was not: the labels were
    not this tool's, and its fourth line was one this tool never printed at
    all. Correct numbers, typed, in a block a re-measurement could not
    move. They come from here now, and the share is printed beside the two
    counts it divides so a reader can redo the arithmetic.

    Counts, so a reader running the command reproduces them - the block is
    theirs to replace. Nothing in it is a cost.
    """
    found = report["relevant_found"]
    missed = report["relevant_missed"]
    unmatchable = report["missed_with_no_matchable_term"]
    share = report["share_unreachable_by_lexical_retrieval"]
    perfect = report["unmatchable_by_gain"].get("1.0", 0)
    # Two shares, two denominators, both printed beside their operands. The
    # third line's is "of what was missed"; the fifth's is "of everything
    # relevant", which is the chapter's own ceiling - an earlier README
    # quoted an 8.2% that no line of this block printed.
    of_all = report["share_of_all_relevant"]
    out = [f"relevant products found:    {found:>7,}",
           f"relevant products missed:   {missed:>7,}",
           f"  with no term to match on: {unmatchable:>7,}   ({share:.1%} of the missed)",
           f"  of those, graded Exact: {perfect:>4,}",
           f"  as a share of all {found + missed:,} relevant: {of_all:.1%}"]
    return "```\n" + "\n".join(out) + "\n```\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None,
                    help="a corpus build; default is the most recent")
    ap.add_argument("--split", choices=builds.SPLITS, required=True)
    ap.add_argument("--ranking", default="bm25_tuned")
    ap.add_argument("--hits", type=int, default=100)
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--examples", type=int, default=8)
    ap.add_argument("--out", type=Path, default=None,
                    help="where the report goes; defaults to this chapter's "
                         "expected/vocabulary-<split>.json, the name the "
                         "chapter's own commands write. A script "
                         "whose report has to be asked for produces numbers "
                         "nobody captured")
    args = ap.parse_args()
    out = args.out or (Path(__file__).resolve().parent / "expected" / f"vocabulary-{args.split}.json")
    build = args.build or builds.latest()

    app = Vespa(args.endpoint)
    queries = builds.load_queries(build, args.split)
    judgements = builds.load_judgements(build, args.split)

    found_total = 0
    missed_total = 0
    unmatchable = 0
    missed_by_gain: Counter[str] = Counter()
    unmatchable_by_gain: Counter[str] = Counter()
    examples: list[dict] = []

    for n, (qid, text) in enumerate(sorted(queries.items()), 1):
        relevant = {d for d, g in judgements.get(qid, {}).items() if g > 0}
        if not relevant:
            continue
        r = app.query("select id from product where userQuery()", query=text,
                      ranking=args.ranking, hits=args.hits)
        retrieved = {h.fields.get("id") for h in r.hits}
        found_total += len(relevant & retrieved)

        for doc in sorted(relevant - retrieved):
            missed_total += 1
            gain = judgements[qid][doc]
            missed_by_gain[str(gain)] += 1

            # Can the engine match this query to this document at all? Not
            # "would it rank it well" - whether a single term connects them.
            probe = app.query(
                f'select id, title from product '
                f'where userQuery() and id contains "{doc}"',
                query=text, ranking=args.ranking, hits=1)
            if probe.hits:
                continue

            unmatchable += 1
            unmatchable_by_gain[str(gain)] += 1
            if len(examples) < args.examples:
                d = app.query(f'select title from product where id contains "{doc}"',
                              hits=1)
                examples.append({
                    "query": text, "gain": gain,
                    "product": (d.hits[0].fields.get("title", "")[:110]
                                if d.hits else doc),
                })
        if n % 40 == 0:
            print(f"  {n}/{len(queries)} queries", file=sys.stderr, flush=True)

    share = unmatchable / missed_total if missed_total else 0.0
    report = {
        "build": builds.meta(build)["build_id"],
        # Every one of these counts came out of a query to a running
        # container, so the report says which one. It did not, and the
        # omission is not cosmetic: this script's whole claim is that *the
        # engine* decides what could never have been retrieved, and which
        # engine was asked is part of the claim. `stamp()` owns the key.
        **deployed.stamp(),
        "split": args.split,
        "ranking_profile": args.ranking,
        "hits": args.hits,
        "method": "the query re-run restricted to the missed document; no hit "
                  "means Vespa's own tokenisation and stemming find no shared term",
        "relevant_found": found_total,
        "relevant_missed": missed_total,
        "missed_with_no_matchable_term": unmatchable,
        "share_unreachable_by_lexical_retrieval": round(share, 4),
        "share_of_all_relevant": round(unmatchable / (found_total + missed_total), 4)
                                 if (found_total + missed_total) else 0.0,
        "missed_by_gain": dict(sorted(missed_by_gain.items(), reverse=True)),
        "unmatchable_by_gain": dict(sorted(unmatchable_by_gain.items(), reverse=True)),
        "examples": examples,
        "host": hostinfo.collect(),
    }

    # The examples are for whoever is running this. They are in the report as
    # well, so nothing is lost by keeping them off stdout - and stdout is the
    # block, so anything else there ends up in the book.
    print("\nexamples a lexical index cannot reach:", file=sys.stderr)
    for e in examples[:5]:
        print(f'  query "{e["query"]}"  (gain {e["gain"]})', file=sys.stderr)
        print(f'    {e["product"]}', file=sys.stderr)

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote {out}", file=sys.stderr)
    print(vocabulary_block(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
