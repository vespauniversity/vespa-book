"""Who owns a listing: `tenant_id` from `brand`, and the ladder it lets the
chapter measure.

`docs/synthetic-data.md` §1 says the rule: tenant is normalised brand,
`" ".join(brand.split()).lower()`, and a listing with no brand at all — or a
brand that is empty once whitespace is collapsed — becomes one marketplace
tenant, `__marketplace__`, which is a real category (listings the platform
owns) rather than a dumping ground.

**No `--split`.** Every other derivation tool in this project takes a split
because it reads judgements, and a document signal built from every judgement
(not only the train split) leaks test labels into the index. Brand carries no
judgement — it is product data, present on every row of the corpus file
regardless of which split, if any, a query belongs to — so there is nothing
here for a split argument to guard.

This tool reads a build's `products.jsonl` and writes three things:

1. `builds/<build>/tenants.jsonl` — one partial-update line per product,
   in the same `{"update": ..., "fields": {...}}` shape `feed.py` already
   feeds (`shared/tools/feed.py`'s `update` branch).
2. `--out <report.json>` — the tenant registry summary and the five ladder
   rungs (`rungs.py`) with their document counts and share, computed from
   this file, before anything is fed. The live counts, once `tenants.jsonl`
   has actually been fed, are a separate check (`filtered_ann.py` queries
   each rung's live count and records it in its report).
3. `--users-out <json>` — an **invented** staff registry: five users, each
   with an allowed set of tenants, chosen so each of the three seller rungs
   of the ladder (marketplace, nike, small_brand) is somebody's whole
   allowed set. These are made up to demonstrate
   authorization and to run the leakage test (`leakage_test.py`); they
   support a demonstration that a mechanism works, never a relevance claim
   (`docs/synthetic-data.md`, "How this reaches the reader").
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))

import builds                       # noqa: E402
import hostinfo                     # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rungs import LADDER, RUNGS      # noqa: E402

# The pinned build (`docs/pins.md`): the one every ch08 report is measured
# against. `--build` can still point elsewhere for a one-off check, but
# nothing here guesses "the most recent build" the way `builds.latest()`
# does for a chapter that has only ever had one candidate — ch08 needs the
# same 101,341-document build every other tool in this chapter reads.
PINNED_BUILD = "esci-us-hard-book-s42-kdd-v4"

# The invented staff registry (`docs/synthetic-data.md` §1: user / group /
# role hang off the tenant). Fixed in code, not sampled — "deterministic" for
# a registry with no random draw in it just means "the same five names every
# time", which a literal dict already is. Chosen so each of the three seller rungs
# of the ladder is somebody's whole allowed set: `nike_staff` reaches the
# `nike` rung, `fox_staff` reaches `small_brand`, `marketplace_staff` reaches
# `marketplace`, and `agency` / `auditor` are the multi-tenant and
# everything-visible cases the leakage test needs a contrast against.
INVENTED_USERS: dict[str, list[str] | str] = {
    "nike_staff": ["nike"],
    "fox_staff": ["20th century fox"],
    "marketplace_staff": ["__marketplace__"],
    "agency": ["nike", "adidas", "hanes"],
    "auditor": "*",
}

USERS_LABEL = (
    "These five users are invented to demonstrate authorization and to run "
    "the leakage test (docs/synthetic-data.md §1); they are not evidence "
    "for any relevance claim.")


def normalise_tenant(brand: str | None) -> str:
    """`docs/synthetic-data.md` §1's rule, verbatim: collapse whitespace,
    lowercase, and anything that comes out empty (no brand, or a brand that
    is only whitespace) becomes the marketplace tenant."""
    collapsed = " ".join((brand or "").split()).lower()
    return collapsed or "__marketplace__"


def iter_products(products_path: Path):
    """Yield `(product_id, brand, has_description)` for every `put` in a
    build's `products.jsonl`. `product_id` is the user-specified part of the
    document id, after the last `::` — the bare ASIN, the same value as the
    document's `id` field.

    Only `put` lines carry product data; a build's own product file has no
    `update` lines (those are what this tool itself produces), but a stray
    one is skipped rather than crashing this read, since this tool does not
    own that file's shape.
    """
    with products_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            op = json.loads(line)
            if "put" not in op:
                continue
            doc_id = op["put"].rsplit("::", 1)[-1]
            fields = op["fields"]
            yield doc_id, fields.get("brand"), bool(fields.get("has_description"))


def build_registry(products_path: Path) -> tuple[dict[str, int], dict[str, str], int]:
    """`(tenant -> document count, product_id -> tenant, total documents)`."""
    registry: dict[str, int] = {}
    assignment: dict[str, str] = {}
    total = 0
    for doc_id, brand, _has_description in iter_products(products_path):
        tenant = normalise_tenant(brand)
        registry[tenant] = registry.get(tenant, 0) + 1
        assignment[doc_id] = tenant
        total += 1
    return registry, assignment, total


def write_update_lines(products_path: Path, assignment: dict[str, str],
                        out_path: Path) -> int:
    """`builds/<build>/tenants.jsonl`: one `update` line per product, with
    the `put` line's own document id (`id:<locale>:product::<asin>`), the
    form `feed.py` already parses (`shared/tools/feed.py:parse_document_id`)
    — the namespace is the locale, the part after the last `::` the ASIN."""
    written = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with products_path.open() as in_fh, out_path.open("w") as out_fh:
        for line in in_fh:
            line = line.strip()
            if not line:
                continue
            op = json.loads(line)
            if "put" not in op:
                continue
            doc_id = op["put"].rsplit("::", 1)[-1]
            tenant = assignment[doc_id]
            update = {
                "update": op["put"],
                "fields": {"tenant_id": {"assign": tenant}},
            }
            out_fh.write(json.dumps(update) + "\n")
            written += 1
    return written


def ladder_rows(registry: dict[str, int], total: int,
                 description_count: int) -> list[dict]:
    """The five rungs with their document count and share, computed from
    this file — not a live query, which is a separate check once
    `tenants.jsonl` has actually been fed."""
    marketplace = registry.get("__marketplace__", 0)
    counts = {
        "has_description": description_count,
        "has_brand": total - marketplace,
        "marketplace": marketplace,
        "nike": registry.get("nike", 0),
        "small_brand": registry.get("20th century fox", 0),
    }
    return [
        {"rung": rung, "clause": RUNGS[rung], "documents": counts[rung],
         "share": round(counts[rung] / total, 4) if total else 0.0}
        for rung in LADDER
    ]


def registry_summary(registry: dict[str, int]) -> dict:
    non_marketplace = {t: n for t, n in registry.items() if t != "__marketplace__"}
    singleton_count = sum(1 for n in non_marketplace.values() if n == 1)
    largest_tenant, largest_size = (
        max(non_marketplace.items(), key=lambda kv: kv[1])
        if non_marketplace else (None, 0))
    return {
        "tenant_count": len(registry),
        "singleton_tenant_count": singleton_count,
        "marketplace_size": registry.get("__marketplace__", 0),
        "largest_brand": largest_tenant,
        "largest_brand_size": largest_size,
    }


def ladder_block(rows: list[dict]) -> str:
    """The rung table for the page: rung, filter clause, documents, share."""
    out = ["| rung | filter clause | documents | share |", "|---|---|---|---|"]
    for r in rows:
        clause = r["clause"] or "(no filter)"
        out.append(f"| {r['rung']} | `{clause}` | {r['documents']:,} | "
                   f"{r['share'] * 100:.2f}% |")
    return "\n".join(out) + "\n"


BLOCKS = {"ladder": ladder_block}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None,
                    help=f"a corpus build; default the pinned build "
                         f"({PINNED_BUILD}, docs/pins.md)")
    ap.add_argument("--out", type=Path, default=None,
                    help="the registry + ladder report; required unless "
                         "--from re-renders an existing one")
    ap.add_argument("--users-out", type=Path, default=None,
                    help="the invented staff registry; required unless "
                         "--from re-renders an existing report")
    ap.add_argument("--block", choices=sorted(BLOCKS), default="ladder",
                    help="the finished block for the page; one per run")
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    metavar="REPORT",
                    help="print --block from a report this tool already "
                         "wrote, deriving nothing - --out/--users-out are "
                         "not needed with this")
    args = ap.parse_args()

    if args.from_report:
        report = json.loads(args.from_report.read_text())
        print(BLOCKS[args.block](report["ladder"]))
        return 0

    if not args.out or not args.users_out:
        raise SystemExit("--out and --users-out are required unless --from "
                         "re-renders an existing report")

    build = args.build or (builds.ROOT / "builds" / PINNED_BUILD)
    if not build.exists():
        raise SystemExit(f"no build at {build}")
    products_path = build / "products.jsonl"

    registry, assignment, total = build_registry(products_path)
    description_count = sum(
        1 for _doc_id, _brand, has_description in iter_products(products_path)
        if has_description)

    tenants_path = build / "tenants.jsonl"
    written = write_update_lines(products_path, assignment, tenants_path)
    print(f"{written:,} update lines -> {tenants_path}", file=sys.stderr)

    rows = ladder_rows(registry, total, description_count)
    summary = registry_summary(registry)
    print(f"{summary['tenant_count']:,} tenants, "
          f"{summary['singleton_tenant_count']:,} singletons, "
          f"marketplace {summary['marketplace_size']:,}, "
          f"largest brand {summary['largest_brand']!r} "
          f"({summary['largest_brand_size']:,})", file=sys.stderr)

    report = {
        "build": builds.meta(build)["build_id"],
        "host": hostinfo.collect(),
        "documents": total,
        "registry_summary": summary,
        "ladder": rows,
        "update_file": str(tenants_path.relative_to(builds.ROOT)),
        "update_lines_written": written,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {args.out}", file=sys.stderr)

    users_report = {
        "invented": True,
        "label": USERS_LABEL,
        "users": INVENTED_USERS,
    }
    args.users_out.parent.mkdir(parents=True, exist_ok=True)
    args.users_out.write_text(json.dumps(users_report, indent=2) + "\n")
    print(f"wrote {args.users_out}", file=sys.stderr)

    print(BLOCKS[args.block](rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
