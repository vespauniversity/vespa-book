"""The negative test. Every user × retriever × every query of the split,
counting returned documents whose tenant is outside that user's allowed
set. **Must be 0.** A second run forges a tenant the same way
`authorized_query.py --untrusted` does, so the test is shown to detect
something rather than having only ever printed zero.

This run doubles as the mechanism's own test suite, the role a file named
`test_access_control.py` would play - not a `pytest` file (that is
`tests/test_ch08_leakage.py`, which checks the counting function and the
clause builder on fixtures, offline), but the same live check the chapter's
number comes from, on the real corpus and the real endpoint.

    python chapters/ch08/leakage_test.py --split validation --block leakage
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
from query import Vespa             # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from authorized_query import (       # noqa: E402
    DEFAULT_USERS_PATH, RANKING, RETRIEVERS, build_authorized_request,
    clause_for_allowed, load_users)

# nike_staff asking for adidas: a real user in the registry, a real tenant in
# the corpus, neither of which is in nike_staff's own allowed set - so every
# leaked document this row finds is a document that should not have come
# back and did.
FORGER = "nike_staff"
FORGED_TENANT = "adidas"


def count_leaked(hit_tenants: list[str], allowed: list[str] | str) -> int:
    """How many of `hit_tenants` are outside `allowed`.

    Hand-computable: three hits, one outside a two-tenant allowed set, is 1.
    The auditor's `"*"` means nothing is outside - everyone is allowed
    everything - so it always returns 0 without inspecting `hit_tenants` at
    all.
    """
    if allowed == "*":
        return 0
    allowed_set = set(allowed)
    return sum(1 for t in hit_tenants if t not in allowed_set)


def run_row(app: Vespa, clause: str, allowed: list[str] | str, retriever: str,
           ids: list[str], queries: dict[str, str], hits: int
           ) -> tuple[int, int]:
    """`(hits_returned, leaked)` over every query id given, for one clause
    (a user's own, or a forged one) under one retriever."""
    total_hits = 0
    leaked = 0
    for qid in ids:
        request = build_authorized_request(retriever, queries[qid], hits, clause)
        r = app.query(ranking=RANKING[retriever], hits=hits, **request)
        tenants = [h.fields.get("tenant_id", "") for h in r.hits]
        total_hits += len(tenants)
        leaked += count_leaked(tenants, allowed)
    return total_hits, leaked


def leakage_block(report: dict) -> str:
    out = ["| user | allowed | retriever | queries | hits returned | leaked |",
           "|---|---|---|---|---|---|"]
    trusted_total = 0
    detection_rows = []
    for row in report["rows"]:
        out.append(f"| {row['user']} | {row['allowed_size']} | "
                   f"{row['retriever']} | {row['queries']} | "
                   f"{row['hits_returned']} | {row['leaked']} |")
        if row.get("detection"):
            detection_rows.append(row)
        else:
            trusted_total += row["leaked"]
    out.append("")
    out.append(f"leaked total: {trusted_total}")
    if detection_rows:
        # one count per retriever, in table order - a single figure would name
        # only whichever row happened to come last
        first = detection_rows[0]
        counts = " / ".join(f"{r['leaked']} ({r['retriever']})" for r in detection_rows)
        out.append(
            f"detection ({first['user']} forging {first['forged_tenant']}): "
            f"leaked {counts}")
    return "\n".join(out) + "\n"


BLOCKS = {"leakage": leakage_block}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--split", choices=builds.SPLITS, required=True,
                    help="no default on purpose: test is for reporting, not deciding")
    ap.add_argument("--users", type=Path, default=DEFAULT_USERS_PATH)
    ap.add_argument("--retrievers", nargs="+", choices=RETRIEVERS,
                    default=list(RETRIEVERS))
    ap.add_argument("--hits", type=int, default=10)
    ap.add_argument("--queries", type=int, default=None,
                    help="cap on how many queries of the split to run, for a "
                         "smoke run only; default is every query - the chapter's "
                         "reported run uses every query")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--block", choices=sorted(BLOCKS), default="leakage")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    metavar="REPORT",
                    help="print --block from a report this tool already "
                         "wrote, measuring nothing")
    args = ap.parse_args()

    if args.from_report:
        report = json.loads(args.from_report.read_text())
        print(BLOCKS[args.block](report))
        return 0

    build = args.build or (builds.ROOT / "builds" / "esci-us-hard-book-s42-kdd-v4")
    queries = builds.load_queries(build, args.split)
    ids = sorted(queries) if args.queries is None else sorted(queries)[:args.queries]

    users = load_users(args.users)
    app = Vespa(args.endpoint)
    if not app.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1

    print(f"{builds.describe(build)}\n{len(ids)} {args.split} queries | "
          f"{len(users)} users | retrievers {list(args.retrievers)}",
          file=sys.stderr)

    rows = []
    for user, allowed in users.items():
        clause = clause_for_allowed(allowed)
        allowed_size = "*" if allowed == "*" else len(allowed)
        for retriever in args.retrievers:
            hits_returned, leaked = run_row(
                app, clause, allowed, retriever, ids, queries, args.hits)
            rows.append({"user": user, "allowed_size": allowed_size,
                        "retriever": retriever, "queries": len(ids),
                        "hits_returned": hits_returned, "leaked": leaked})
            print(f"  {user} / {retriever}: {hits_returned} hits, "
                  f"{leaked} leaked", file=sys.stderr, flush=True)

    if FORGER in users:
        real_allowed = users[FORGER]
        forged_clause = clause_for_allowed([FORGED_TENANT])
        for retriever in args.retrievers:
            hits_returned, leaked = run_row(
                app, forged_clause, real_allowed, retriever, ids, queries,
                args.hits)
            rows.append({"user": FORGER, "allowed_size": len(real_allowed),
                        "retriever": retriever, "queries": len(ids),
                        "hits_returned": hits_returned, "leaked": leaked,
                        "detection": True, "forged_tenant": FORGED_TENANT})
            print(f"  detection {FORGER} forging {FORGED_TENANT} / "
                  f"{retriever}: {hits_returned} hits, {leaked} leaked",
                  file=sys.stderr, flush=True)

    report = {
        "build": builds.meta(build)["build_id"],
        **deployed.stamp(),
        "split": args.split,
        "queries": len(ids),
        # how many hits each request asked for - the `leaked` count is over
        # these, so a reader can tell 0 of 10 from 0 of 100
        "hits": args.hits,
        "users_file": str(args.users),
        "rows": rows,
        "host": hostinfo.collect(),
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    print(BLOCKS[args.block](report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
