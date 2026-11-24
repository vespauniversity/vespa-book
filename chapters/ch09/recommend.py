"""Recommendation with no query at all: a user's own profile vector in place
of a search term.

Every row here answers the same question a different way: given a hundred
candidates for this person, how many of the products they will later judge
Exact turn up? **own** sends the user's own profile vector into
`nearestNeighbor(title_embedding, ...)`. **shuffled** sends someone else's
profile vector against this user's own held-out products - the control that
says how much of `own`'s score is this person's own context and how much is just
"vectors near popular products score well for everyone". **popular** sends no
vector at all: the same short list of widely Exact-judged products for every
user, the control for "any list would have worked". **cross_brand** repeats
`own`'s candidates, but only counts a held-out product if its brand is not in
this user's `brand_weights` - the brands of their other relevant products;
the defining brand is never there, so its products stay in the target set.

    .venv/bin/python chapters/ch09/recommend.py --split train --half reporting \\
        --rows own,shuffled,popular,cross_brand --passes 1 \\
        --out chapters/ch09/expected/recommend-reporting.json --block recall

    .venv/bin/python chapters/ch09/recommend.py --split train --user generic --block hits
"""
from __future__ import annotations

import argparse
import calendar
import datetime
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))
import builds       # noqa: E402
import deployed     # noqa: E402
import embed_offline  # noqa: E402
import hostinfo     # noqa: E402
import metrics      # noqa: E402
from query import Vespa, add_where_clause  # noqa: E402

from derive_events import SNAPSHOT_EPOCH  # noqa: E402

DOCTYPE = "user"
RANKING = "semantic"
VECTOR_FIELD = "title_embedding"
ROW_NAMES = ("own", "shuffled", "popular", "cross_brand")
RECALL_K = (10, 50, 100)
SEED = 42


def require_train_split(split: str) -> None:
    if split != "train":
        raise SystemExit(
            f"--split {split!r} refused: the users and held-out products "
            f"this tool reads are derived from training judgements only")


def normalise_brand(raw: str | None) -> str:
    return " ".join((raw or "").split()).lower()


def load_users(users_path: Path) -> dict:
    return json.loads(users_path.read_text())


def users_in_half(payload: dict, half: str) -> list[dict]:
    return [u for u in payload["users"] if u["half"] == half]


def held_out_targets(user: dict) -> set[str]:
    """Union of Exact product ids across every one of this user's held-out
    queries - the set a recommendation row's recall is measured against."""
    ids: set[str] = set()
    for q in user["held_out_queries"]:
        ids.update(q["e_products"])
    return ids


def load_product_brands(products_path: Path) -> dict[str, str]:
    brands: dict[str, str] = {}
    with products_path.open() as fh:
        for line in fh:
            rec = json.loads(line)
            fields = rec["fields"]
            brands[fields["id"]] = normalise_brand(fields.get("brand"))
    return brands


def load_product_titles(products_path: Path) -> dict[str, str]:
    titles: dict[str, str] = {}
    with products_path.open() as fh:
        for line in fh:
            rec = json.loads(line)
            fields = rec["fields"]
            titles[fields["id"]] = fields.get("title", "")
    return titles


def seeded_permutation(user_ids: list[str], seed: int) -> tuple[dict[str, str], int]:
    """A seeded permutation mapping every user to another user's id: shuffle
    once, then repair any position a shuffle happened to leave fixed by
    swapping it with its neighbour. Returns (mapping, fixed points left after
    the repair) - the repair is not guaranteed to reach a perfect derangement
    on every seed, so what is left is counted rather than assumed away."""
    ordered = sorted(user_ids)
    rng = random.Random(seed)
    permuted = ordered[:]
    rng.shuffle(permuted)
    n = len(ordered)
    for i in range(n):
        if permuted[i] == ordered[i]:
            j = (i + 1) % n
            permuted[i], permuted[j] = permuted[j], permuted[i]
    remaining = sum(1 for a, b in zip(ordered, permuted) if a == b)
    return dict(zip(ordered, permuted)), remaining


def bootstrap_mean(values: dict[str, float], samples: int = 2000, seed: int = SEED,
                   confidence: float = 0.95) -> dict:
    """A mean over users with a bootstrap interval - the same resampling
    `metrics.bootstrap_delta` does, without a second system to subtract,
    since a recall row here is a number on its own, not a difference."""
    vals = list(values.values())
    if not vals:
        return {}
    rng = random.Random(seed)
    n = len(vals)
    means = [statistics.fmean(rng.choices(vals, k=n)) for _ in range(samples)]
    means.sort()
    lo = means[int((1 - confidence) / 2 * samples)]
    hi = means[int((1 + confidence) / 2 * samples) - 1]
    return {"mean": statistics.fmean(vals), "lo": lo, "hi": hi, "n": n}


def fmt_interval(d: dict | None) -> str:
    if not d:
        return "—"
    return f"{d['mean']:.3f} [{d['lo']:.3f}, {d['hi']:.3f}]"


def parse_now(spec: str | None) -> int:
    """An epoch integer, an ISO date, or (the default) the fixed snapshot
    day every derived event is measured against."""
    if spec is None:
        return SNAPSHOT_EPOCH
    if spec.lstrip("-").isdigit():
        return int(spec)
    return calendar.timegm(
        datetime.datetime.strptime(spec, "%Y-%m-%dT%H:%M:%SZ").timetuple())


def decayed_vector(event_times: dict[str, float], titles: dict[str, str],
                   now_epoch: int, half_life_days: float, encoder) -> list[float]:
    """A profile vector aged against `now_epoch`: each remembered product
    counts for less the older it is, on a half-life schedule, and the ages
    are shifted by the smallest one before the exponent so a `now` far in
    the future cannot underflow every weight to zero at once - the
    *ratios* between weights are all this needs, and shifting preserves them
    exactly while keeping the largest weight at 1.0."""
    pids = sorted(event_times)
    ages = [now_epoch - event_times[pid] for pid in pids]
    min_age = min(ages)
    half_life_seconds = half_life_days * 86400
    weights = [math.exp(-math.log(2) * (age - min_age) / half_life_seconds)
              for age in ages]
    total = sum(weights)
    texts = [titles.get(pid, "") for pid in pids]
    vectors = encoder.encode(texts, encoder.cfg["doc_prefix"])
    dims = len(vectors[0])
    mean = [0.0] * dims
    for weight, vec in zip(weights, vectors):
        for i in range(dims):
            mean[i] += weight * float(vec[i])
    return [round(x / total, 6) for x in mean]


def normalise_vector(values: list[float]) -> list[float]:
    """Unit length, or the vector unchanged if it has none to begin with
    (a zero vector has no direction to keep)."""
    norm = math.sqrt(sum(v * v for v in values))
    if not norm:
        return list(values)
    return [v / norm for v in values]


def recommend_request(vector: list[float], hits: int, where: str | None) -> dict:
    """The no-query request for one profile vector. The vector is sent at unit
    length: `title_embedding`'s distance metric (prenormalized-angular)
    assumes a unit-length query vector, and a mean of unit-length title
    vectors is shorter than one - sent as is, every hit would read the same
    closeness and come back in document order instead of nearest first."""
    vector = normalise_vector(vector)
    # `title` rides along for the single-user demonstration block, which
    # prints it; the recall rows only ever read `id` back out of a hit, so
    # carrying the extra summary field costs the multi-user rows nothing.
    # `totalTargetHits`: the neighbours asked for in total across the content
    # nodes (floor 100; the rows ask for --hits 100 plus the profile's own
    # products, which are dropped from the result).
    yql = f"select id, brand, tenant_id, title from product where {{totalTargetHits:{hits}}}nearestNeighbor({VECTOR_FIELD}, q)"
    if where:
        yql = add_where_clause(yql, where)
    return {"yql": yql, "input.query(q)": {"values": vector}}


def query_once(app: Vespa, vector: list[float], hits: int, where: str | None = None):
    request = recommend_request(vector, hits, where)
    started = time.perf_counter()
    r = app.query(ranking=RANKING, hits=hits, timing=True, **request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return r, elapsed_ms


def candidates_excluding_seen(ids: list[str], seen: set[str], k: int) -> list[str]:
    return [pid for pid in ids if pid not in seen][:k]


def hits_block(rows: list[dict], caption: str | None = None) -> str:
    out = []
    if caption:
        out.append(f"_{caption}_")
        out.append("")
    out += ["| id | brand | title |", "|---|---|---|"]
    for r in rows:
        title = (r["title"] or "")[:70].replace("|", "\\|")
        out.append(f"| {r['id']} | {r['brand']} | {title} |")
    return "\n".join(out) + "\n"


def recall_block(report: dict) -> str:
    out = ["| row | recall@10 | recall@50 | recall@100 |", "|---|---|---|---|"]
    for row in report["rows"]:
        cells = [fmt_interval(row["recall"].get(f"@{k}")) for k in RECALL_K]
        out.append(f"| {row['name']} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def deltas_block(report: dict) -> str:
    out = ["| comparison | recall@10 | recall@50 | recall@100 |", "|---|---|---|---|"]
    for label, deltas in report["deltas"].items():
        cells = [metrics.fmt_delta(deltas.get(f"@{k}")) for k in RECALL_K]
        out.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def latency_block(report: dict) -> str:
    """Client-measured request latency per row, from the same run as the
    recall table - only the rows that send a request carry one (the popular
    list sends none)."""
    out = ["| row | p50 | p95 | mean |", "|---|---|---|---|"]
    for row in report["rows"]:
        lat = row.get("latency_ms")
        if not lat:
            continue
        out.append(f"| {row['name']} | {metrics.fmt_latency(lat['p50'])} | "
                   f"{metrics.fmt_latency(lat['p95'])} | {metrics.fmt_latency(lat['mean'])} |")
    return "\n".join(out) + "\n"


BLOCKS = {"recall": recall_block, "deltas": deltas_block, "hits": hits_block,
          "latency": latency_block}


def run_recall_rows(app: Vespa, users: list[dict], rows_wanted: list[str],
                    hits: int, brand_of: dict[str, str], popular: list[str],
                    passes: int) -> dict:
    user_ids = [u["user_id"] for u in users]
    docs: dict[str, dict] = {}
    for uid in user_ids:
        doc = app.get_document(DOCTYPE, uid)
        if doc is None:
            raise SystemExit(f"user document {uid!r} not found - feed the "
                             f"user documents before running this tool")
        docs[uid] = doc

    targets = {u["user_id"]: held_out_targets(u) for u in users}
    shuffle_map, fixed_points = seeded_permutation(user_ids, SEED)

    def own_query_ms(passes_n: int):
        client_ms_per_pass = []
        hits_by_user: dict[str, list[str]] = {}
        for p in range(passes_n + 1):   # pass 0 is the warm pass, discarded
            pass_ms = []
            for uid in user_ids:
                seen = set(docs[uid].get("seen") or [])
                vec = docs[uid]["profile_vector"]["values"]
                r, ms = query_once(app, vec, hits + len(seen))
                pass_ms.append(ms)
                if p == 1:   # quality comes from the first measured pass
                    hits_by_user[uid] = [h.fields.get("id", "") for h in r.hits
                                         if h.fields.get("id") not in seen][:hits]
            if p > 0:
                client_ms_per_pass.append(pass_ms)
        return hits_by_user, client_ms_per_pass

    def shuffled_query_ms(passes_n: int):
        client_ms_per_pass = []
        hits_by_user: dict[str, list[str]] = {}
        for p in range(passes_n + 1):
            pass_ms = []
            for uid in user_ids:
                other = shuffle_map[uid]
                seen = set(docs[uid].get("seen") or [])
                vec = docs[other]["profile_vector"]["values"]
                r, ms = query_once(app, vec, hits + len(seen))
                pass_ms.append(ms)
                if p == 1:
                    hits_by_user[uid] = [h.fields.get("id", "") for h in r.hits
                                         if h.fields.get("id") not in seen][:hits]
            if p > 0:
                client_ms_per_pass.append(pass_ms)
        return hits_by_user, client_ms_per_pass

    own_hits: dict[str, list[str]] = {}
    own_latency = None
    shuffled_hits: dict[str, list[str]] = {}
    shuffled_latency = None

    if "own" in rows_wanted or "cross_brand" in rows_wanted:
        own_hits, own_ms = own_query_ms(passes)
        own_latency = latency_stats(own_ms)
    if "shuffled" in rows_wanted:
        shuffled_hits, shuffled_ms = shuffled_query_ms(passes)
        shuffled_latency = latency_stats(shuffled_ms)

    rows = []
    per_user_recall: dict[str, dict[int, dict[str, float]]] = {}
    cross_brand_skipped = 0

    if "own" in rows_wanted:
        per_query = {k: {} for k in RECALL_K}
        for uid in user_ids:
            relevant = targets[uid]
            for k in RECALL_K:
                per_query[k][uid] = metrics.recall_at_k(own_hits[uid], relevant, k) if relevant else 0.0
        rows.append({"name": "own",
                    "recall": {f"@{k}": bootstrap_mean(per_query[k]) for k in RECALL_K},
                    "latency_ms": own_latency})
        per_user_recall["own"] = per_query

    if "shuffled" in rows_wanted:
        per_query = {k: {} for k in RECALL_K}
        for uid in user_ids:
            relevant = targets[uid]
            for k in RECALL_K:
                per_query[k][uid] = metrics.recall_at_k(shuffled_hits[uid], relevant, k) if relevant else 0.0
        rows.append({"name": "shuffled",
                    "recall": {f"@{k}": bootstrap_mean(per_query[k]) for k in RECALL_K},
                    "latency_ms": shuffled_latency})
        per_user_recall["shuffled"] = per_query

    if "popular" in rows_wanted:
        per_query = {k: {} for k in RECALL_K}
        for uid in user_ids:
            seen = set(docs[uid].get("seen") or [])
            candidates = [pid for pid in popular if pid not in seen]
            relevant = targets[uid]
            for k in RECALL_K:
                per_query[k][uid] = metrics.recall_at_k(candidates, relevant, k) if relevant else 0.0
        rows.append({"name": "popular",
                    "recall": {f"@{k}": bootstrap_mean(per_query[k]) for k in RECALL_K},
                    "latency_ms": None})
        per_user_recall["popular"] = per_query

    if "cross_brand" in rows_wanted:
        per_query = {k: {} for k in RECALL_K}
        for uid in user_ids:
            own_brands = set(docs[uid].get("brand_weights", {}).get("cells", {}))
            relevant = {pid for pid in targets[uid] if brand_of.get(pid) not in own_brands}
            if not relevant:
                cross_brand_skipped += 1
                continue
            for k in RECALL_K:
                per_query[k][uid] = metrics.recall_at_k(own_hits[uid], relevant, k)
        rows.append({"name": "cross_brand",
                    "recall": {f"@{k}": bootstrap_mean(per_query[k]) for k in RECALL_K},
                    "latency_ms": None,
                    "users_skipped_empty_target": cross_brand_skipped})
        per_user_recall["cross_brand"] = per_query

    deltas = {}
    if "own" in per_user_recall and "shuffled" in per_user_recall:
        deltas["own vs shuffled"] = {
            f"@{k}": metrics.bootstrap_delta(per_user_recall["shuffled"][k], per_user_recall["own"][k])
            for k in RECALL_K}
    if "own" in per_user_recall and "popular" in per_user_recall:
        deltas["own vs popular"] = {
            f"@{k}": metrics.bootstrap_delta(per_user_recall["popular"][k], per_user_recall["own"][k])
            for k in RECALL_K}

    return {
        "rows": rows,
        "deltas": deltas,
        "users": len(user_ids),
        "shuffled_fixed_points_remaining": fixed_points,
        "cross_brand_users_skipped": cross_brand_skipped,
    }


def latency_stats(client_ms_per_pass: list[list[float]]) -> dict:
    if not client_ms_per_pass:
        return {}
    per_pass = [metrics.percentiles(cm) for cm in client_ms_per_pass]
    out = {}
    for stat in ("mean", "p50", "p95", "p99", "max"):
        values = [p[stat] for p in per_pass if stat in p]
        if values:
            out[stat] = round(statistics.median(values), 2)
    return out


def rows_from_ids(ids: list[str], brand_of: dict[str, str], titles: dict[str, str],
                  limit: int = 10) -> list[dict]:
    return [{"id": pid, "brand": brand_of.get(pid, ""), "title": titles.get(pid, "")}
            for pid in ids[:limit]]


def run_hits_demo(app: Vespa, user_id: str, build: Path, hits: int, where: str | None,
                  half_life: float | None, now_epoch: int, max_age_days: float | None,
                  popular: list[str]) -> tuple[list[dict], str | None]:
    doc = app.get_document(DOCTYPE, user_id)
    if doc is None:
        raise SystemExit(f"user document {user_id!r} not found")
    seen = set(doc.get("seen") or [])
    brand_of = load_product_brands(build / "products.jsonl")
    caption = None

    if half_life is not None:
        event_times = doc.get("event_times", {}).get("cells", {})
        if not event_times:
            raise SystemExit(f"user {user_id!r} has no event_times yet - "
                             f"nothing to age")
        if max_age_days is not None:
            window_seconds = max_age_days * 86400
            event_times = {pid: t for pid, t in event_times.items()
                          if (now_epoch - t) <= window_seconds}
            if not event_times:
                caption = (f"profile older than {max_age_days} days at "
                          f"now={now_epoch}: popular list shown")
                print(caption, file=sys.stderr)
                titles = load_product_titles(build / "products.jsonl")
                candidates = [pid for pid in popular if pid not in seen]
                return rows_from_ids(candidates, brand_of, titles), caption
        titles = load_product_titles(build / "products.jsonl")
        encoder = embed_offline.Encoder("bge")
        vector = decayed_vector(event_times, titles, now_epoch, half_life, encoder)
    else:
        vector = doc["profile_vector"]["values"]

    r, _ms = query_once(app, vector, hits + len(seen), where)
    rows = []
    for h in r.hits:
        if h.fields.get("id") in seen:
            continue
        pid = h.fields.get("id", "")
        rows.append({"id": pid, "brand": h.fields.get("brand", brand_of.get(pid, "")),
                    "title": h.fields.get("title", "")})
        if len(rows) >= 10:
            break
    return rows, caption


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--split", required=True,
                    help="must be 'train' - this tool refuses any other value")
    ap.add_argument("--users", type=Path, default=None,
                    help="the users.json derive_users.py wrote; default "
                         "<build>/users.json")
    ap.add_argument("--half", choices=("tuning", "reporting"), default="reporting",
                    help="which half of the users this run scores")
    ap.add_argument("--rows", default=",".join(ROW_NAMES),
                    help="comma list of rows to compute")
    ap.add_argument("--hits", type=int, default=100)
    ap.add_argument("--passes", type=int, default=1,
                    help="measured passes after one warm pass over every "
                         "request this run sends")
    ap.add_argument("--where", default=None, metavar="CLAUSE",
                    help="AND this clause onto the recommendation request - "
                         "the business-constraint demonstration; only valid "
                         "with --user")
    ap.add_argument("--user", default=None,
                    help="one user id: print their top ten instead of a "
                         "recall table (--block hits)")
    ap.add_argument("--half-life", type=float, default=None, metavar="DAYS",
                    help="age the profile against event_times on a half-life "
                         "of DAYS instead of using the stored profile_vector "
                         "- only valid with --user; refused on the recall "
                         "rows, which are always measured undecayed")
    ap.add_argument("--now", default=None,
                    help="an epoch integer or an ISO date the half-life "
                         "decay is measured against; default is the fixed "
                         "snapshot day every derived event is stamped "
                         "relative to - pass the real clock to see how old "
                         "a profile has become since then")
    ap.add_argument("--max-age", type=float, default=None, metavar="DAYS",
                    help="only with --half-life --user: drop events older "
                         "than this many days at --now before aging the "
                         "rest; a normalised decayed profile does not "
                         "change when --now moves on its own (only the "
                         "spacing between events matters), so this window "
                         "is where a later --now actually changes the "
                         "answer - if nothing survives it, the profile is "
                         "empty and the popular list is shown instead")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--block", choices=sorted(BLOCKS), default="recall")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    metavar="REPORT",
                    help="print --block recall/deltas from a report this "
                         "tool already wrote, measuring nothing")
    args = ap.parse_args()

    require_train_split(args.split)

    if args.from_report:
        if args.block not in ("recall", "deltas", "latency"):
            raise SystemExit("--from only re-renders --block recall, --block deltas or "
                             "--block latency - a hits demo is not a saved report")
        report = json.loads(args.from_report.read_text())
        print(BLOCKS[args.block](report))
        return 0

    if args.passes < 1:
        raise SystemExit(f"--passes must be at least 1, got {args.passes}")
    if args.where and not args.user:
        raise SystemExit("--where only applies to --user's single-user demo")
    if args.half_life is not None and not args.user:
        raise SystemExit(
            "--half-life is refused without --user: every recall row this "
            "tool reports is measured against the stored, undecayed "
            "profile_vector, on purpose - an aged profile is a "
            "demonstration (--user ... --block hits), never a measured row")
    if args.max_age is not None and args.half_life is None:
        raise SystemExit("--max-age only applies together with --half-life "
                         "and --user")

    build = args.build or builds.latest()
    users_path = args.users or (build / "users.json")
    payload = load_users(users_path)

    app = Vespa(args.endpoint)
    if not app.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1

    if args.user:
        now_epoch = parse_now(args.now)
        rows, caption = run_hits_demo(app, args.user, build, args.hits, args.where,
                                      args.half_life, now_epoch, args.max_age,
                                      payload["popular"])
        print(hits_block(rows, caption))
        return 0

    users = users_in_half(payload, args.half)
    rows_wanted = [r.strip() for r in args.rows.split(",") if r.strip()]
    for r in rows_wanted:
        if r not in ROW_NAMES:
            raise SystemExit(f"--rows: unknown row {r!r}, choose from {ROW_NAMES}")

    brand_of = load_product_brands(build / "products.jsonl")
    result = run_recall_rows(app, users, rows_wanted, args.hits, brand_of,
                             payload["popular"], args.passes)

    report = {
        "build": builds.meta(build)["build_id"],
        "split": args.split,
        **deployed.stamp(),
        "half": args.half,
        "hits": args.hits,
        "rows": result["rows"],
        "deltas": result["deltas"],
        "users": result["users"],
        "shuffled_fixed_points_remaining": result["shuffled_fixed_points_remaining"],
        "cross_brand_users_skipped": result["cross_brand_users_skipped"],
        "latency_conditions": {
            "warm": True,
            "note": "one warm pass over every request this run sends, "
                    "discarded, then the measured passes below",
            "passes": args.passes,
        },
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
