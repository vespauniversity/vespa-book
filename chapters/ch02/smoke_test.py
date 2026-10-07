"""Does the application deploy, accept documents, and answer queries?

A smoke test is not a relevance test. It answers the question you actually have
after a deploy — is anything at all working — and it answers it in seconds, so
that when chapter 3 reports a disappointing NDCG you already know the problem
is the ranking and not the plumbing.

    vespa deploy --wait 300 chapters/ch02/app
    python chapters/ch02/smoke_test.py --build builds/<build-id> --limit 2000

This prints two of the chapter's blocks and says which:

    --block smoke-output   what a passing run looks like, from the run
    --block checks         the names of every check the suite runs

They are split because they answer different questions and the second is not a
measurement. What each check *catches* is for the chapter text, not this
command's output - but the list of names is the suite's and comes from here,
so that **a check added tomorrow appears in the block with nothing written
beside it** instead of being silently absent.
The hand-written version of that table missed a check and misnamed another.

Stdout is the block and nothing else: the PASS and FAIL lines you watch go by
are on stderr, and so is everything else this says.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))

import builds                  # noqa: E402
import deployed                # noqa: E402
import feed as feeder          # noqa: E402
import hostinfo                # noqa: E402
from query import Vespa        # noqa: E402
from corpus import LOCALE      # noqa: E402  (the document id's namespace)

CHECKS: list[tuple[str, bool, str]] = []

# Declare the complete suite so an early failure cannot shrink its documentation.
CHECK_NAMES: tuple[str, ...] = (
    "container responds",
    "documents are visible",
    "a known document is retrievable",
)


def checks_block() -> str:
    """The names of every check, as the finished block that goes on the page.

    Not a measurement and not a run: the suite's own list, so it can be printed
    without a container and cannot shrink because a run stopped early. What
    each one catches is for the chapter text, not this command's output - it
    is a judgement about what would have gone wrong, and no run knows that.
    """
    return ("| Check |\n|---|\n"
            + "".join(f"| `{name}` |\n" for name in CHECK_NAMES))


def smoke_output_block(checks: list[tuple[str, bool, str]]) -> str:
    """What a run of the suite printed, as the finished block.

    Chapter 2's whole purpose is that a reader ends with something demonstrably
    working, and it was the one chapter that never showed them what working
    looks like - four code blocks, all of them commands, and no output
    anywhere.
    """
    lines = []
    for name, ok, detail in checks:
        lines.append(f"  {'PASS' if ok else 'FAIL'}  {name}"
                     f"{'  — ' + detail if detail else ''}")
    passed = sum(1 for _, ok, _ in checks if ok)
    lines += ["", f"{passed}/{len(checks)} checks passed"]
    return "```\n" + "\n".join(lines) + "\n```\n"


BLOCKS = {"smoke-output": "a run of the suite", "checks": "the check names"}


def check(name: str, ok: bool, detail: str = "") -> bool:
    if name not in CHECK_NAMES:
        raise SystemExit(
            f"check {name!r} is not in CHECK_NAMES. Add it there, in the order "
            f"it runs - a check nobody can see is a check nobody maintains; "
            f"what it catches is for the chapter text, not this command's output.")
    CHECKS.append((name, ok, detail))
    # To stderr: this is the run going by, and stdout is reserved for the block.
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'  — ' + detail if detail else ''}",
          file=sys.stderr)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", type=Path, default=None,
                    help="a corpus build; default is the most recent")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--limit", type=int, default=2000,
                    help="documents to feed; the whole corpus is chapter 3's job")
    ap.add_argument("--capture", type=Path, default=None,
                    help="rewrite the reference in expected/. For us, when a "
                         "number has legitimately changed - not for a reader, "
                         "whose first act should not be to overwrite the file "
                         "they were given")
    ap.add_argument("--reference", type=Path,
                    default=Path(__file__).resolve().parent / "expected" / "smoke.json",
                    help="what to compare against; skipped if it is not there")
    ap.add_argument("--block", choices=sorted(BLOCKS), default="smoke-output",
                    help="which finished block goes to stdout. `checks` is the "
                         "suite's list of names and needs no container, so it "
                         "answers without deploying or feeding anything")
    args = ap.parse_args()

    # The names are a property of the suite, not of a run. Making them a
    # property of a run is what let a check disappear from the page by failing
    # early, so this answers before anything is deployed.
    if args.block == "checks":
        print(checks_block())
        return 0

    CHECKS.clear()
    build = args.build or builds.latest()

    app = Vespa(args.endpoint)

    print("deployment", file=sys.stderr)
    if not check("container responds", app.wait_until_ready(timeout=120)):
        print("\nIs the application deployed? "
              "vespa deploy --wait 300 chapters/ch02/app", file=sys.stderr)
        return 1

    products = build / "products.jsonl"
    if not products.exists():
        print(f"\nNo corpus at {products}. Build one:\n"
              "  python shared/tools/corpus.py build --preset book",
              file=sys.stderr)
        return 1

    print("\nfeeding", file=sys.stderr)
    result = feeder.feed_file(products, args.endpoint, limit=args.limit)
    print(f"  {result.summary()}", file=sys.stderr)
    print("\nqueries", file=sys.stderr)
    total = app.count()
    check("documents are visible", total >= result.ok,
          f"{total:,} in the index, {result.ok:,} fed")

    # Retrieve the first fed document through the document API, preserving
    # the current locale namespace and bare-ASIN document ID format.
    first = json.loads(products.open().readline())
    doc_id = first["put"].rsplit("::", 1)[1]
    f = app.get_document("product", doc_id, namespace=LOCALE)
    check("a known document is retrievable", f is not None, doc_id)

    passed = sum(1 for _, ok, _ in CHECKS if ok)
    print(f"\n{passed}/{len(CHECKS)} checks passed", file=sys.stderr)
    print(hostinfo.as_markdown(), file=sys.stderr)

    # An expected/ file nothing reads is a file that quietly stops being true.
    # This is the one that gets read.
    if args.reference and not args.capture:
        if args.reference.exists():
            want = json.loads(args.reference.read_text())
            # Older references may include checks that this suite no longer runs.
            theirs = {c["name"]: c["ok"] for c in want.get("checks", [])
                      if c["name"] in CHECK_NAMES}
            mine = {n: ok for n, ok, _ in CHECKS}
            differ = [n for n in sorted(set(theirs) | set(mine))
                      if theirs.get(n) != mine.get(n)]
            print(f"\nagainst {args.reference.name}:", file=sys.stderr)
            if differ:
                for n in differ:
                    print(f"  DIFFERS  {n}: expected {theirs.get(n)}, "
                          f"got {mine.get(n)}", file=sys.stderr)
            else:
                print(f"  the same {len(mine)} checks, all agreeing", file=sys.stderr)
            if want.get("fed") != result.ok:
                print(f"  fed {result.ok:,} where the reference fed "
                      f"{want.get('fed'):,}", file=sys.stderr)
        else:
            # `expected/smoke.json` is written by `--capture`; until a capture
            # has run there is nothing to compare against.
            # Silence here would read as "the same" - the one comparison this
            # block never prints - so a missing reference says so instead of
            # being indistinguishable from a passing one.
            print(f"\nno reference yet: {args.reference} "
                  f"(written by --capture)", file=sys.stderr)

    if args.capture:
        args.capture.parent.mkdir(parents=True, exist_ok=True)
        args.capture.write_text(json.dumps({
            "build": build.name,
            # What was in the index when these checks ran, asked of the running
            # system. Chapter 2 declares no embedder, so the value here is
            # `none declared` - and that is the informative one: it is what
            # would catch chapter 2 shipping with an embedder it does not
            # describe, in a report whose other fields would all still look
            # right. `unreachable` is the third answer and is not this one.
            **deployed.stamp(),
            "fed": result.ok,
            "failed": result.failed,
            "docs_per_second": round(result.rate),
            "indexed": total,
            "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in CHECKS],
            "host": hostinfo.collect(),
        }, indent=2) + "\n")
        print(f"captured to {args.capture}", file=sys.stderr)

    # The block goes to stdout on its own, so it can be piped, diffed or lifted
    # into the page - including when a check failed, because what a failing run
    # looks like is the other half of what chapter 2 is showing.
    print(smoke_output_block(CHECKS))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())