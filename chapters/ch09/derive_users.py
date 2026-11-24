"""Who is shopping: users derived from brand-affinity groups of judged queries.

ESCI has no user accounts and no sessions. What it has is judgements: a query
is a stated intent, and an `E` judgement on a product is a person saying "this
satisfies it". This tool turns those judgements into a set of interest
clusters we call users: every query whose Exact-judged products include a
given brand joins that brand's cluster, so one query can join several
clusters at once (a query about a jacket that turned up an Exact Nike result
and an Exact Adidas result feeds both). A cluster is capped at 30 queries so
no one brand dominates the evaluation, and only clusters with at least two
queries can be split into a profile half and a held-out half - the profile
half stands in for what a shopper has already told the system, the held-out
half for what recommendation quality is measured against.

The query pool this runs over is this corpus's own training queries plus a
second pool: training-split queries that were never part of this build at
all, kept only if at least one of their Exact-judged products exists in this
corpus. That second pool exists because the corpus alone does not carry
enough queries per cluster to say anything with a resolvable interval; adding
it is a deliberate trade of "every query in the pool is one this corpus's
documents were chosen around" for "there are enough held-out queries per user
to measure something".

Everything here comes from the training split. `--split` takes no default and
refuses anything else, because a document signal or an evaluation set built
from validation or test judgements would leak the split whose whole job is to
never be looked at until a chapter is ready to report a number.

    .venv/bin/python chapters/ch09/derive_users.py --split train \\
        --out chapters/ch09/expected/users.json \\
        --users-out builds/<build>/users.json \\
        --feed-out builds/<build>/users.jsonl --block users
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))
import builds       # noqa: E402
import deployed     # noqa: E402
import hostinfo     # noqa: E402

VECTOR_DIMS = 384
POPULAR_SIZE = 100

# The pool file this build's own queries are extended with: every row of the
# wider judgement table, restricted here to its training-split, hard-subset
# rows (the same restriction the corpus itself was built under), and then to
# queries this build does not already carry.
POOL_SPLIT = "train"

RULE_TEXT = (
    "A user is every query whose Exact-judged products share a normalised "
    "brand: group queries by that brand, cap each group at 30 queries (a "
    "seeded sample), and keep groups with at least two queries so each can "
    "be split into a profile half and a held-out half. The query pool is "
    "this build's own training queries plus training-split queries outside "
    "the build that carry at least one Exact-judged product this corpus "
    "already holds. One query can belong to more than one user.")

EXPECTED_COUNTS = {
    False: {"splittable_users": 4210, "held_out_queries": 7100},   # pool enabled
    True: {"splittable_users": 912, "held_out_queries": 1221},     # --no-pool
}


def repo_relative(path: Path) -> str:
    """A path for the committed report: relative to the repository root when it
    lies under it (`builds/<build>/users.json`), so the report does not carry
    one machine's home directory; any other path as given."""
    try:
        return str(Path(path).relative_to(builds.ROOT))
    except ValueError:
        return str(path)


def require_train_split(split: str) -> None:
    if split != "train":
        raise SystemExit(
            f"--split {split!r} refused: every user, profile query and "
            f"popularity count this tool derives comes from training "
            f"judgements only, never validation or test")


def normalise_brand(raw: str | None) -> str:
    """`" ".join(s.split()).lower()` - the same normalisation the tenant
    field on `product` already carries, so a brand string on either side of
    a ranking expression is the same string."""
    return " ".join((raw or "").split()).lower()


def load_corpus_brands(products_path: Path) -> dict[str, str]:
    """product id -> normalised brand (`""` for no brand), for every product
    this corpus holds. A product with no brand groups into no user at all -
    it never surfaces here as `""` joining anything, since grouping only
    happens where `normalise_brand(...)` is non-empty."""
    brand_of: dict[str, str] = {}
    with products_path.open() as fh:
        for line in fh:
            rec = json.loads(line)
            fields = rec["fields"]
            brand_of[fields["id"]] = normalise_brand(fields.get("brand"))
    return brand_of


def load_build_query_ids(build: Path) -> set[str]:
    ids: set[str] = set()
    for split in builds.SPLITS:
        with (build / f"queries_{split}.csv").open() as fh:
            ids.update(row["query_id"] for row in csv.DictReader(fh))
    return ids


def load_build_train_query_text(build: Path) -> dict[str, str]:
    with (build / "queries_train.csv").open() as fh:
        return {row["query_id"]: row["query_text"] for row in csv.DictReader(fh)}


def load_build_train_judgements(build: Path) -> dict[str, dict[str, str]]:
    """query id -> {product id: label} - this build's own training queries,
    every judgement (not only Exact), because the held-out half of a user's
    queries is later scored against all of it, not only what makes a user."""
    out: dict[str, dict[str, str]] = defaultdict(dict)
    with (build / "judgements_train.csv").open() as fh:
        for row in csv.DictReader(fh):
            out[row["query_id"]][row["document_id"]] = row["label"]
    return out


def load_pool(parquet_path: Path, exclude_ids: set[str],
              corpus_ids: set[str]) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """The second pool: training-split, hard-subset queries this build does
    not already carry, kept only if at least one Exact-judged product is in
    this corpus. Returns (query id -> text, query id -> {product id: label}),
    the judgements already restricted to products this corpus holds - a
    judgement on a product outside the 101,341 documents in the index can
    never be found by any request this chapter sends, so it is not scored
    against either.
    """
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    table = pq.read_table(
        parquet_path,
        columns=["query_id", "query", "product_id", "esci_label", "split",
                 "small_version"])
    mask = pc.and_(pc.equal(table.column("split"), POOL_SPLIT),
                   pc.equal(table.column("small_version"), True))
    subset = table.filter(mask)

    qids = [str(q) for q in subset.column("query_id").to_pylist()]
    texts = subset.column("query").to_pylist()
    products = subset.column("product_id").to_pylist()
    labels = subset.column("esci_label").to_pylist()

    text_of: dict[str, str] = {}
    judged: dict[str, dict[str, str]] = defaultdict(dict)
    has_corpus_exact: set[str] = set()
    for qid, text, pid, label in zip(qids, texts, products, labels):
        if qid in exclude_ids:
            continue
        text_of.setdefault(qid, text)
        if pid in corpus_ids:
            judged[qid][pid] = label
            if label == "E":
                has_corpus_exact.add(qid)

    return ({qid: text_of[qid] for qid in has_corpus_exact},
            {qid: judged[qid] for qid in has_corpus_exact})


def build_brand_groups(query_judgements: dict[str, dict[str, str]],
                       brand_of: dict[str, str]) -> dict[str, set[str]]:
    """brand -> the set of query ids with at least one Exact-judged product
    of that brand. A query with several Exact brands joins every one of
    them - this is a multi-membership grouping, not a partition."""
    groups: dict[str, set[str]] = defaultdict(set)
    for qid, judged in query_judgements.items():
        brands = {brand_of[pid] for pid, label in judged.items()
                 if label == "E" and brand_of.get(pid)}
        for b in brands:
            groups[b].add(qid)
    return groups


def cap_groups(groups: dict[str, set[str]], cap: int, seed: int) -> dict[str, list[str]]:
    """Deterministic cap: brands visited alphabetically, each group over the
    cap reduced by a seeded sample - so the same seed and cap always produce
    the same reduced group, run to run."""
    rng = random.Random(seed)
    capped: dict[str, list[str]] = {}
    for brand in sorted(groups):
        qs = sorted(groups[brand], key=lambda x: int(x))
        if len(qs) > cap:
            qs = sorted(rng.sample(qs, cap), key=lambda x: int(x))
        capped[brand] = qs
    return capped


def split_profile_held_out(qids: list[str], seed: int, user_id: str) -> tuple[list[str], list[str]]:
    """One user's queries, split into (profile half, held-out half): sort,
    seed a shuffle on the user's own id so every user gets an independent
    ordering, then the first `max(1, n // 2)` become held-out and the rest
    become the profile."""
    ordered = sorted(qids)
    rng = random.Random(f"{seed}:{user_id}")
    rng.shuffle(ordered)
    n_held = max(1, len(ordered) // 2)
    held, profile = ordered[:n_held], ordered[n_held:]
    return profile, held


def query_entry(qid: str, query_text: dict[str, str],
                query_judgements: dict[str, dict[str, str]]) -> dict:
    judged = query_judgements[qid]
    return {
        "query_id": qid,
        "query_text": query_text[qid],
        "judgements": dict(sorted(judged.items())),
        "e_products": sorted(pid for pid, label in judged.items() if label == "E"),
        "s_products": sorted(pid for pid, label in judged.items() if label == "S"),
    }


def build_users(capped: dict[str, list[str]], seed: int, query_text: dict[str, str],
                query_judgements: dict[str, dict[str, str]]) -> list[dict]:
    """Every brand group with two or more queries, split into a profile half
    and a held-out half, then the whole list shuffled once (seeded on the
    project seed, not the user) and halved into a tuning half and a
    reporting half - the tuning half plays the part validation would in a
    chapter with one; the reporting half is what a number is taken from."""
    eligible = [brand for brand in capped if len(capped[brand]) >= 2]
    users = []
    for brand in eligible:
        profile_qids, held_qids = split_profile_held_out(capped[brand], seed, brand)
        users.append({
            "user_id": brand,
            "defining_brand": brand,
            "profile_queries": [query_entry(q, query_text, query_judgements)
                               for q in profile_qids],
            "held_out_queries": [query_entry(q, query_text, query_judgements)
                                 for q in held_qids],
        })
    rng = random.Random(seed)
    rng.shuffle(users)
    half = len(users) // 2
    for i, user in enumerate(users):
        user["half"] = "tuning" if i < half else "reporting"
    return users


def popular_products(query_judgements: dict[str, dict[str, str]], n: int = POPULAR_SIZE) -> list[str]:
    """The `n` products with the most Exact judgements across the whole
    query pool - one list, used the same way for every user, with ties
    broken by product id so the list is the same every run."""
    counts: Counter[str] = Counter()
    for judged in query_judgements.values():
        for pid, label in judged.items():
            if label == "E":
                counts[pid] += 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [pid for pid, _ in ranked[:n]]


def feed_lines(users: list[dict]) -> list[str]:
    """One `put` per user, the state a profile starts in before any event
    has been applied: a zero vector, no brand weights, nothing seen. The
    profile is built afterwards by applying events one partial update at a
    time - this feed only puts the user documents in existence."""
    lines = []
    for user in users:
        lines.append(json.dumps({
            "put": f"id:user:user::{user['user_id']}",
            "fields": {
                "user_id": user["user_id"],
                "defining_brand": user["defining_brand"],
                "profile_vector": {"values": [0.0] * VECTOR_DIMS},
                "brand_weights": {"cells": []},
                "seen": [],
                "events_applied": 0,
            },
        }))
    return lines


def users_block(report: dict) -> str:
    rows = [
        ("build-train queries", report["build_train_queries"]),
        ("pool queries", report["pool_queries"]),
        ("combined query pool", report["combined_queries"]),
        ("brand groups", report["brand_groups"]),
        ("splittable users", report["splittable_users"]),
        ("held-out queries", report["held_out_queries_total"]),
        ("tuning users", report["tuning_users"]),
        ("tuning held-out queries", report["tuning_held_out_queries"]),
        ("reporting users", report["reporting_users"]),
        ("reporting held-out queries", report["reporting_held_out_queries"]),
    ]
    out = ["| metric | value |", "|---|---|"]
    out += [f"| {k} | {v:,} |" for k, v in rows]
    return "\n".join(out) + "\n"


BLOCKS = {"users": users_block}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--split", required=True,
                    help="must be 'train' - this tool refuses any other value")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--cap", type=int, default=30,
                    help="the most queries a single user's cluster keeps")
    ap.add_argument("--no-pool", action="store_true",
                    help="use only this build's own training queries, "
                         "without the second pool of training-split queries "
                         "outside the build - a smaller, self-contained "
                         "query set, useful for a self-check against a "
                         "known count")
    ap.add_argument("--pool-file", type=Path, default=None,
                    help="the wider judgement table the second pool is read "
                         "from; default shared/cache/index_us.parquet")
    ap.add_argument("--out", type=Path, default=None, help="the derivation report")
    ap.add_argument("--users-out", type=Path, default=None,
                    help="per-user profile/held-out data; default "
                         "<build>/users.json")
    ap.add_argument("--feed-out", type=Path, default=None,
                    help="the user document feed; default <build>/users.jsonl")
    ap.add_argument("--block", choices=sorted(BLOCKS), default="users")
    args = ap.parse_args()

    require_train_split(args.split)

    build = args.build or builds.latest()
    products_path = build / "products.jsonl"

    brand_of = load_corpus_brands(products_path)
    corpus_ids = set(brand_of)

    build_query_ids = load_build_query_ids(build)
    query_text = load_build_train_query_text(build)
    query_judgements = load_build_train_judgements(build)
    build_train_count = len(query_text)

    pool_query_count = 0
    if not args.no_pool:
        pool_file = args.pool_file or (
            builds.ROOT / "shared" / "cache" / "index_us.parquet")
        pool_text, pool_judgements = load_pool(pool_file, build_query_ids, corpus_ids)
        pool_query_count = len(pool_text)
        query_text.update(pool_text)
        query_judgements.update(pool_judgements)
        print(f"pool: {pool_query_count} queries added from {pool_file}",
              file=sys.stderr)
    else:
        print("--no-pool: using only this build's own training queries",
              file=sys.stderr)

    groups = build_brand_groups(query_judgements, brand_of)
    capped = cap_groups(groups, args.cap, args.seed)
    users = build_users(capped, args.seed, query_text, query_judgements)
    popular = popular_products(query_judgements)

    held_out_total = sum(len(u["held_out_queries"]) for u in users)
    tuning = [u for u in users if u["half"] == "tuning"]
    reporting = [u for u in users if u["half"] == "reporting"]

    expected = EXPECTED_COUNTS[args.no_pool]
    self_check = {
        "expected_splittable_users": expected["splittable_users"],
        "actual_splittable_users": len(users),
        "expected_held_out_queries": expected["held_out_queries"],
        "actual_held_out_queries": held_out_total,
        "matches": (len(users) == expected["splittable_users"]
                   and held_out_total == expected["held_out_queries"]),
    }
    print(f"self-check ({'no-pool' if args.no_pool else 'with pool'}): "
          f"{len(users)} splittable users (expected "
          f"{expected['splittable_users']}), {held_out_total} held-out "
          f"queries (expected {expected['held_out_queries']}) - "
          f"{'match' if self_check['matches'] else 'DIFFERS'}", file=sys.stderr)

    users_out = args.users_out or (build / "users.json")
    feed_out = args.feed_out or (build / "users.jsonl")

    users_payload = {
        "build": builds.meta(build)["build_id"],
        "seed": args.seed,
        "cap": args.cap,
        "pool_enabled": not args.no_pool,
        "rule": RULE_TEXT,
        "popular": popular,
        "users": users,
    }
    users_out.parent.mkdir(parents=True, exist_ok=True)
    users_out.write_text(json.dumps(users_payload, indent=2) + "\n")
    print(f"wrote {users_out}", file=sys.stderr)

    feed_out.parent.mkdir(parents=True, exist_ok=True)
    lines = feed_lines(users)
    feed_out.write_text("\n".join(lines) + "\n")
    print(f"wrote {feed_out} ({len(lines)} users)", file=sys.stderr)

    report = {
        "build": builds.meta(build)["build_id"],
        "split": args.split,
        **deployed.stamp(),
        "seed": args.seed,
        "cap": args.cap,
        "pool_enabled": not args.no_pool,
        "rule": RULE_TEXT,
        "build_train_queries": build_train_count,
        "pool_queries": pool_query_count,
        "combined_queries": len(query_text),
        "brand_groups": len(groups),
        "splittable_users": len(users),
        "held_out_queries_total": held_out_total,
        "tuning_users": len(tuning),
        "tuning_held_out_queries": sum(len(u["held_out_queries"]) for u in tuning),
        "reporting_users": len(reporting),
        "reporting_held_out_queries": sum(len(u["held_out_queries"]) for u in reporting),
        "popular_products": len(popular),
        "self_check": self_check,
        "users_out": repo_relative(users_out),
        "feed_out": repo_relative(feed_out),
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
