"""Build the context a generated answer would be written from, and price it.

Hybrid retrieval is where a RAG pipeline gets its evidence, so this chapter ends
by producing that evidence rather than by describing it. Two properties are what
make a context block usable and they pull against each other:

**Attributable.** Every line carries the product id it came from, so a claim in
an answer can be traced to a document rather than to the model. Nothing here is
merged, summarised or reordered - the ids survive to the end.

**Compact.** A context block is paid for twice, in what it costs to send and in
what it costs a model to read, and the second is the expensive one. So the
interesting question is not "how good is the retrieval" but **how much context
buys how much of the answer** - which is a number, and this measures it.

The retrieval is always the union of both arms - `userQuery() or
nearestNeighbor(...)`, the chapter's premise - and does not change with
`--ranking`. What changes is which rank profile orders that union, which is why
`--ranking` is required rather than fixed to `hybrid_linear`: a reader comparing
what `hybrid_linear` hands a generator against what `hybrid_rrf` does is asking a
question this chapter's own tools should be able to answer, not one that needs
a second script. `--alpha` only means something under `hybrid_linear`, which is
the only profile that reads `input.query(alpha)`; passing it with any other
profile is refused rather than silently doing nothing.

    python chapters/ch05/context.py --query "waterproof hiking boots" --ranking hybrid_linear
    python chapters/ch05/context.py --split validation --depths 1 3 5 10 20 --ranking hybrid_linear --alpha 0.3

`--query` prints one context block, which is what a prompt would be built from.
`--split` measures the curve and prints the table the chapter carries. Either
way stdout is the block: the running count, the byte total and the summary a
person reads are on stderr, because the swap that puts a block on the page
replaces a marked region with stdout whole.

Both halves are quality rather than cost. The bytes are a property of the
documents retrieved, not of the machine that retrieved them, so a reader
running this gets our figures and the block is theirs to replace.

**Deduplication.** This corpus holds one document per product id, so
deduplicating by id is a no-op - every id in a hit list is already unique, and
a dedup step that only ever removes zero entries would be worth nothing to
disclose. What actually repeats, on rare occasions, is the *title*: two
different ids can carry the same title text once whitespace is normalised.
`dedupe()` keeps the first (higher-ranked) of any such pair and drops the
rest, and the curve block's `dropped` column reports how many entries that
removed at each depth - zero at depth 1, 18 to 115 at depths 3 to 20 on this corpus, which is itself
the finding worth stating rather than hiding the column.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))

import builds                       # noqa: E402
import deployed                   # noqa: E402
import hostinfo                     # noqa: E402
from evaluate import QUERY_PREFIX   # noqa: E402
from query import Vespa             # noqa: E402

# The retrieval this chapter arrived at: both arms, fused. Which rank profile
# orders the union is `--ranking`'s job, not this constant's - see the
# module docstring.
YQL = ("select id, title, snippet from product where userQuery() or "
       "({targetHits:100}nearestNeighbor(title_embedding, q))")


def retrieve(app: Vespa, text: str, hits: int, *, ranking: str, alpha: float | None = None):
    safe = text.replace("\\", "\\\\").replace('"', '\\"')
    params = {"input.query(q)": f'embed(embedder, "{QUERY_PREFIX}{safe}")'}
    if alpha is not None:
        params["input.query(alpha)"] = alpha
    return app.query(YQL, query=text, ranking=ranking, hits=hits,
                     summary="context", **params)


def plain(text: str) -> str:
    """A dynamic summary comes back marked up, and the markup is not noise.

    `<hi>` wraps the matched terms - useful in a search result page, nothing to
    a model, so it goes. `<sep />` marks where the summariser cut text out, and
    dropping it silently joins two unrelated clauses into one sentence the
    product never said. It becomes an ellipsis, because a model reading this
    should be able to tell that something is missing.
    """
    text = text or ""
    text = re.sub(r"</?hi>", "", text)
    text = re.sub(r"\s*<sep\s*/>\s*", " ... ", text)
    text = re.sub(r"<br\s*/>", " ", text)
    return re.sub(r"\s+", " ", text).strip(" .")


def block(hits, raw: bool = False) -> list[dict]:
    """One entry per product, id first. The id is not decoration: it is the
    only thing that makes an answer checkable."""
    out = []
    for h in hits:
        f = h.fields
        out.append({
            "id": f.get("id", ""),
            "title": (f.get("title") or "").strip(),
            # `--raw` leaves the markup in, because a chapter that describes
            # `<hi>` and `<sep />` should be able to show them rather than
            # asking a reader to take the description on trust.
            "snippet": (f.get("snippet") or "") if raw else plain(f.get("snippet")),
        })
    return out


def dedupe(entries: list[dict]) -> tuple[list[dict], int]:
    """Drop later entries whose title, once whitespace-normalised, repeats an
    earlier (higher-ranked) one; return the survivors and how many were
    dropped.

    Deduplicating by id is a no-op on this corpus - one document per product
    id, so every hit list is already id-unique. What this removes instead is a
    title that appears twice under two different ids: the entry kept is
    whichever ranked higher, because that is the one a reader (or a model)
    would have already seen by the time the second copy arrived.
    """
    seen: set[str] = set()
    out: list[dict] = []
    dropped = 0
    for e in entries:
        key = " ".join((e["title"] or "").split())
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        out.append(e)
    return out, dropped


def render(entries: list[dict]) -> str:
    """What actually goes into a prompt. Plain text, one product per block,
    the id on its own line so it survives whatever the model does to the rest."""
    parts = []
    for e in entries:
        body = f"[{e['id']}] {e['title']}"
        if e["snippet"]:
            body += f"\n{e['snippet']}"
        parts.append(body)
    return "\n\n".join(parts)


def context_block(report: dict) -> str:
    """What context costs and what it buys, as the finished block for the page.

    The share is what the chapter's argument turns on - the first few hundred
    bytes buy most of what there is to buy - so the bytes and the share sit on
    the same row and a reader can divide one by the other themselves.

    `dropped` is its own column rather than a footnote: a column that is
    zero at depth 1 and small after it is still the honest way to show a reader
    what dedup did, rather than asserting that in prose with no number behind
    it.
    """
    out = ["| products | mean bytes | contains an exact match | dropped |",
          "|---|---|---|---|"]
    for r in report["rows"]:
        out.append(f"| {r['products']} | {r['mean_bytes']:,} | "
                   f"{r['share_with_exact_match']:.1%} | {r['dropped']} |")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query", help="show the context for one query (--query mode; "
                         "--out, --build and --split are not read in this mode)")
    ap.add_argument("--raw", action="store_true",
                    help="leave the summariser's markup in, to see what "
                         "is being stripped (--query mode only; ignored with "
                         "--split)")
    ap.add_argument("--build", type=Path, default=None,
                    help="corpus build (--split mode only)")
    ap.add_argument("--split", choices=builds.SPLITS,
                    help="measure what context costs and what it buys "
                         "(--split mode)")
    ap.add_argument("--depths", type=int, nargs="+", default=[1, 3, 5, 10, 20])
    ap.add_argument("--ranking", required=True,
                    help="rank profile the union candidate set is ordered "
                         "under - not fixed to hybrid_linear, so a reader can "
                         "compare what a different profile hands a generator")
    ap.add_argument("--alpha", type=float, default=None,
                    help="input.query(alpha); only hybrid_linear reads it, "
                         "so passing this with any other --ranking is an "
                         "error rather than a silent no-op")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--out", type=Path, default=None,
                    help="where the curve's JSON report is written "
                         "(--split mode only)")
    args = ap.parse_args()

    if args.alpha is not None and args.ranking != "hybrid_linear":
        raise SystemExit(
            f"--alpha only means something under hybrid_linear "
            f"({args.ranking!r} does not declare input.query(alpha)); Vespa "
            f"would silently ignore it, which this refuses to do instead")

    app = Vespa(args.endpoint)

    if args.query:
        entries, dropped = dedupe(
            block(retrieve(app, args.query, max(args.depths),
                          ranking=args.ranking, alpha=args.alpha).hits, raw=args.raw))
        text = render(entries[:5])
        print(text)
        print(f"\n--- {len(text.encode()):,} bytes, {len(entries[:5])} products, "
              f"{dropped} dropped as duplicate titles", file=sys.stderr)
        return 0

    if not args.split:
        raise SystemExit("--query or --split")

    build = args.build or builds.latest()
    queries = builds.load_queries(build, args.split)
    judgements = builds.load_judgements(build, args.split)
    deepest = max(args.depths)

    # What "buys the answer" means here: the context contains at least one
    # product a human judged an exact match. If it does not, no amount of
    # generation will produce a right answer - it will produce a fluent one.
    exact = {q: {d for d, g in j.items() if g >= 1.0} for q, j in judgements.items()}

    found = {d: 0 for d in args.depths}
    total_bytes = {d: 0 for d in args.depths}
    dropped_total = {d: 0 for d in args.depths}
    scored = 0
    for n, qid in enumerate(sorted(queries), 1):
        if not exact.get(qid):
            continue
        scored += 1
        all_entries = block(retrieve(app, queries[qid], deepest,
                                     ranking=args.ranking, alpha=args.alpha).hits)
        for d in args.depths:
            entries, dropped = dedupe(all_entries[:d])
            dropped_total[d] += dropped
            text = render(entries)
            total_bytes[d] += len(text.encode())
            if any(e["id"] in exact[qid] for e in entries):
                found[d] += 1
        if n % 50 == 0:
            print(f"  {n}/{len(queries)}", file=sys.stderr, flush=True)

    report = {"build": builds.meta(build)["build_id"],
              # Which model was in the index when this ran.
              **deployed.stamp(),
              "split": args.split,
              "ranking": args.ranking, "alpha": args.alpha,
              "queries_with_an_exact_match": scored,
              "rows": [], "host": hostinfo.collect()}
    print(f"\n{scored} of {len(queries)} {args.split} queries have an exact "
          f"match to find\n", file=sys.stderr)
    print(f"{'products':>9} {'mean bytes':>11} {'has an exact match':>20} "
          f"{'dropped':>8}", file=sys.stderr)
    for d in args.depths:
        share = found[d] / scored
        mean = total_bytes[d] / scored
        report["rows"].append({"products": d, "mean_bytes": round(mean),
                               "share_with_exact_match": round(share, 4),
                               "dropped": dropped_total[d]})
        print(f"{d:>9} {mean:>11,.0f} {share:>19.1%} {dropped_total[d]:>8}",
              file=sys.stderr)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote {args.out}", file=sys.stderr)
    # The block goes to stdout on its own. Everything above it is on stderr:
    # this command printed its whole summary there and nothing at all here, so
    # a run pasting stdout into the page had nothing to paste.
    print(context_block(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
