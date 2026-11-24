"""Personalized search: the same funnel a query already runs through, with
one or more extra inputs - the brands in a user's intent context, its colours, or their
own profile vector - added to its first phase.

Two rank profiles carry these terms. **personalized** (the default,
`--ranking personalized`) sits on top of chapter 6's funnel: a fused first
stage, a ColBERT second phase, the cross-encoder switched off for this
tool's own measurements (`ranking.globalPhase.rerankCount=0`, the same
per-request knob chapter 6 already uses to turn a phase off without
touching the profile). **personalized_lexical** (`--ranking
personalized_lexical`) carries only the brand term, on top of chapter 3's
keyword-matching profile alone - no vector retrieval, no reranker - so the
same brand context can be measured against a much plainer relevance score
underneath it. Every row on `personalized_lexical` sends a keyword-only
request (`userQuery()`); it has no colour row and no vector rows, because
neither one means anything without the vector term or the vector retrieval
`personalized` carries.

Every row on `personalized` sends the identical union request (`userQuery()`
lexical match, or-ed with a `nearestNeighbor` over the title vector, ColBERT
reranking the fused first-phase score) and changes only what a user's
context contributes to that first phase. **baseline** contributes nothing -
the unpersonalized funnel (or, under `personalized_lexical`, the
unpersonalized keyword profile). **own** feeds back the second-order brand
distribution the profile-updater actually built for this user (their other
Exact brands, never the one that named them). **shuffled** feeds back
someone else's distribution against this user's own query - the control
that separates "personalization helps" from "any plausible-looking brand
bias helps". **upper** adds the defining brand back in as one more count
(the weight one judged product carries) before normalising - a circular,
best-case number, since nudging toward the brand
that named the user is answering with the label. **colour** repeats the same
mechanism over product colour instead of brand (`--ranking personalized`
only). **vector** sends this user's own stored
profile vector - normalised to unit length before it goes out, since the
stored mean is shorter than that - as a second opinion alongside the query:
how close a candidate sits to what this person has judged relevant before,
regardless of the words they typed (`--ranking personalized` only).
**vector_shuffled** is vector's own control, another user's vector against
this user's query, the same permutation `shuffled` uses.

    .venv/bin/python chapters/ch09/personalized_eval.py --split train --half tuning \\
        --phase tune --out chapters/ch09/expected/personalized-tune.json \\
        --block tune

    .venv/bin/python chapters/ch09/personalized_eval.py --split train --half reporting \\
        --phase report --w own=0.05 shuffled=0.05 upper=0.5 colour=0.1 \\
        vector=1 vector_shuffled=1 \\
        --out chapters/ch09/expected/personalized-report.json --block report

    .venv/bin/python chapters/ch09/personalized_eval.py --split train --half tuning \\
        --phase tune --from chapters/ch09/expected/personalized-tune.json \\
        --block coverage
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))
import builds       # noqa: E402
import deployed     # noqa: E402
import evaluate     # noqa: E402
import gains        # noqa: E402
import hostinfo     # noqa: E402
import metrics      # noqa: E402
from query import Vespa  # noqa: E402

from recommend import seeded_permutation, load_product_brands  # noqa: E402

DOCTYPE = "user"
RERANKER_INPUTS = {"qt": "colbert", "qt_cross": "tokenizer"}
GAIN_MAPPING = "kdd"
VECTOR_DIMENSIONS = 384
SEED = 42

# The rows each rank profile answers for, and in what order they are always
# tried. `personalized_lexical` carries only the brand term, so it has
# nothing to say about colour or a title vector - both are refused there
# rather than silently skipped, so a request for a number this profile
# cannot produce fails loudly instead of coming back short a row.
ROWS_BY_RANKING = {
    "personalized": ("own", "shuffled", "upper", "colour", "vector", "vector_shuffled"),
    "personalized_lexical": ("own", "shuffled", "upper"),
}

# The tune grid for `personalized`'s brand/colour terms is deliberately
# small: a request input is not the score itself, it is one weighted term
# inside a first-phase expression whose other terms already sit near [0, 1],
# while the affinity feature this term multiplies is a share of one (a
# normalised distribution), so the grid is read against that scale, not
# against a rank score's own range.
TUNE_GRID = "0.05,0.1,0.2,0.5"

# `personalized_lexical`'s first phase is BM25 plus the same weighted
# brand-affinity share of one. BM25 is unbounded, so the weight that matters
# here is on its scale, not the fraction that suits the bounded fused first
# phase.
TUNE_GRID_LEXICAL = "1,2,5,10"

# The vector term is a cosine between two unit vectors, not the [0, 1]
# share a brand/colour distribution's own weight multiplies - so it gets its
# own grid, wider than the brand/colour one.
TUNE_GRID_VECTOR = "0.1,0.2,0.5,1"


def require_train_split(split: str) -> None:
    if split != "train":
        raise SystemExit(
            f"--split {split!r} refused: the users and held-out queries "
            f"this tool reads are derived from training judgements only")


UNSAFE_LABEL_CHARS = '"\\{}:,'


def clean_label(label: str) -> str:
    """A mapped-tensor literal's own parser does not honour an escape
    inside a label: a quote, backslash, brace, colon or comma breaks the
    whole request, tested live against this container. Those characters
    are dropped rather than escaped - escaping them still fails to parse -
    so a label that carries only one of them may end up matching nothing on
    the document side, a known and accepted loss."""
    return "".join(ch for ch in label if ch not in UNSAFE_LABEL_CHARS).strip()


def format_mapped_tensor(cells: dict[str, float], dim: str) -> str | None:
    """A Vespa mapped-tensor literal for `input.query(...)`, or `None` if
    every cell dropped out empty - a row with nothing to say should send no
    input at all rather than an empty tensor literal.

    Two distinct raw labels can clean to the same string (a brand recorded
    both as "tena" and "tena," collapses to one cell once the comma drops),
    and a literal with the same address written twice is not a bigger cell -
    Vespa refuses to parse it at all (`Could not parse '{ ... }'`, found live
    against this container). Weights for a colliding cleaned label are summed
    before the literal is built, the same merge normalise_weights would do if
    the collision had already happened before this function saw it."""
    merged: dict[str, float] = {}
    for label, weight in cells.items():
        cleaned = clean_label(label)
        if cleaned:
            merged[cleaned] = merged.get(cleaned, 0.0) + weight
    if not merged:
        return None
    parts = [f'{{{dim}:"{cleaned}"}}:{weight}' for cleaned, weight in merged.items()]
    return "{ " + ", ".join(parts) + " }"


def normalise_weights(cells: dict[str, float]) -> dict[str, float]:
    total = sum(cells.values())
    if not total:
        return {}
    return {k: v / total for k, v in cells.items()}


def normalise_vector(values: list[float]) -> list[float]:
    """Unit length, or the vector unchanged if it has none to begin with.

    `profile_vector` is a plain running mean over unit-length title vectors,
    so its own length is under 1 once more than one direction is averaged
    into it - `vector_affinity`'s dot product against a unit-length document
    vector is only a cosine similarity if this side is unit length too, so the
    request
    normalises it before it goes out rather than sending the stored mean
    as is."""
    norm = math.sqrt(sum(v * v for v in values))
    if not norm:
        return list(values)
    return [v / norm for v in values]


def with_defining_brand(cells: dict[str, float], defining_brand: str) -> dict[str, float]:
    out = dict(cells)
    out[defining_brand] = out.get(defining_brand, 0.0) + 1.0
    return out


def colour_distribution(profile_queries: list[dict], color_of: dict[str, str]) -> dict[str, float]:
    """Raw ESCI colour strings across a user's profile-half Exact products,
    computed here rather than stored - the `user` document has no colour
    field."""
    counts: Counter[str] = Counter()
    for q in profile_queries:
        for pid in q["e_products"]:
            colour = color_of.get(pid)
            if colour:
                counts[colour] += 1
    return normalise_weights(dict(counts))


def load_color_of(products_path: Path) -> dict[str, str]:
    colors: dict[str, str] = {}
    with products_path.open() as fh:
        for line in fh:
            rec = json.loads(line)
            fields = rec["fields"]
            if fields.get("color"):
                colors[fields["id"]] = fields["color"]
    return colors


def user_brand_set(user: dict, brand_of: dict[str, str]) -> set[str]:
    """The brands this user's own profile-half Exact products carry, minus
    the brand that defined them - the same set `profile_updater.py` turns
    into `brand_weights` cells, recomputed here from the build's own files
    (`derive_users.py`'s own `users.json` and `products.jsonl`) rather than
    read off a live document, since the coverage split runs with no
    container at all."""
    brands: set[str] = set()
    for q in user["profile_queries"]:
        for pid in q["e_products"]:
            brand = brand_of.get(pid)
            if brand:
                brands.add(brand)
    brands.discard(user["defining_brand"])
    return brands


def query_is_covered(q: dict, brand_of: dict[str, str], user_brands: set[str]) -> bool:
    """Whether at least one of this held-out query's Exact products carries
    a brand this user's own profile already has an opinion about."""
    return any(brand_of.get(pid) in user_brands for pid in q["e_products"])


def best_weight(tune_row: dict[str, dict]) -> str:
    """The weight with the best (highest) delta vs baseline - the same rule
    the chapter's own weight choice used: the highest delta on the grid,
    whether or not any point on it clears the noise band."""
    return max(tune_row, key=lambda w: tune_row[w]["delta"])


def restrict(per_query: dict[str, float], keys: list[str]) -> dict[str, float]:
    return {k: per_query[k] for k in keys if k in per_query}


def coverage_block(report: dict, users: list[dict], brand_of: dict[str, str]) -> str:
    """An exploratory split of the tuning half's (user, query) pairs into
    "covered" (this user's own profile already has an opinion about at
    least one Exact product's brand for this query) and "not covered" -
    computed once the tune report exists, from the build's own files, with
    no engine call. The weight used for `own` (and, at the same weight, for
    `shuffled`) is the one the tune report itself already picked out as
    least-bad-or-best on the whole grid."""
    own_weight = best_weight(report["tune"]["own"])
    baseline_pq = report["baseline_per_query"]
    own_pq = report["tune"]["own"][own_weight]["per_query"]
    shuffled_pq = report["tune"]["shuffled"][own_weight]["per_query"]

    covered: list[str] = []
    not_covered: list[str] = []
    for user in users:
        uid = user["user_id"]
        brands = user_brand_set(user, brand_of)
        for q in user["held_out_queries"]:
            key = f"{uid}|{q['query_id']}"
            (covered if query_is_covered(q, brand_of, brands) else not_covered).append(key)

    lines = ["_exploratory, tuning half, split chosen after the data was seen_", "",
             "| group | n | own vs baseline | own vs shuffled |",
             "|---|---|---|---|"]
    for name, keys in (("covered", covered), ("not covered", not_covered)):
        vs_baseline = metrics.bootstrap_delta(restrict(baseline_pq, keys), restrict(own_pq, keys))
        vs_shuffled = metrics.bootstrap_delta(restrict(shuffled_pq, keys), restrict(own_pq, keys))
        lines.append(f"| {name} | {len(keys)} | {metrics.fmt_delta(vs_baseline)} | "
                     f"{metrics.fmt_delta(vs_shuffled)} |")
    return "\n".join(lines) + "\n"


def build_row_request(text: str, row: str, w: float | None, ranking: str,
                      cells) -> dict:
    """The request for one row. `cells` is whatever this row's own context
    is made of: a brand-weight dict for own/shuffled/upper, a colour-weight
    dict for colour, a 384-number unit vector for vector/vector_shuffled, or
    `None` for baseline - `row` alone says which."""
    if ranking == "personalized_lexical":
        request = evaluate.build_request("lexical", text, hits=100)
    else:
        request = evaluate.build_request("hybrid", text, hits=100)
        evaluate.add_reranker_inputs(request, text, RERANKER_INPUTS)
        request["ranking.globalPhase.rerankCount"] = 0

    if row == "baseline":
        return request
    if row == "colour":
        literal = format_mapped_tensor(cells or {}, "colour")
        if literal:
            request["input.query(user_colours)"] = literal
            request["input.query(w_colour)"] = str(w)
        return request
    if row in ("vector", "vector_shuffled"):
        if cells:
            request["input.query(user_vector)"] = {"values": list(cells)}
            request["input.query(w_vector)"] = str(w)
        return request
    # own / shuffled / upper: the brand term. Named `w_affinity`, never
    # `w_brand` - that input already exists up the inheritance chain (the
    # weight on a brand word matched in the query, from chapter 3's
    # profile) and redeclaring it here would silently change that term too.
    literal = format_mapped_tensor(cells or {}, "brand")
    if literal:
        request["input.query(user_brands)"] = literal
        request["input.query(w_affinity)"] = str(w)
    return request


def gain_judgements(judgements: dict[str, str]) -> dict[str, float]:
    return {pid: gains.gain(label, GAIN_MAPPING) for pid, label in judgements.items()}


def eval_pairs(app: Vespa, pairs: list[tuple[str, str, dict]], row: str, w: float | None,
              ranking: str, cells_by_key: dict, warm: bool
              ) -> tuple[dict[str, dict], list[float]]:
    """`pairs` is (key, query text, gain judgements). Returns (key -> {ndcg10,
    recall10}, client ms per request) for one measured pass; a caller runs
    this once discarded (`warm=True`) before the measured call."""
    results: dict[str, dict] = {}
    client_ms: list[float] = []
    for key, text, judged in pairs:
        request = build_row_request(text, row, w, ranking, cells_by_key.get(key))
        started = time.perf_counter()
        r = app.query(ranking=ranking, hits=100, timing=True, **request)
        client_ms.append((time.perf_counter() - started) * 1000)
        if warm:
            continue
        ids = [h.fields.get("id", "") for h in r.hits]
        relevant = {d for d, g in judged.items() if g > 0}
        results[key] = {
            "ndcg10": metrics.ndcg_at_k(ids, judged, 10),
            "recall10": metrics.recall_at_k(ids, relevant, 10) if relevant else 0.0,
        }
    return results, client_ms


def parse_row_weights(items: list[str]) -> dict[str, float]:
    """`["own=0.1", "vector=0.3"]` -> `{"own": 0.1, "vector": 0.3}` - the
    `--phase report` shape of `--w`, one weight per row as NAME=VALUE."""
    out: dict[str, float] = {}
    for item in items:
        name, sep, value = item.partition("=")
        if not sep or not name:
            raise SystemExit(f"--w wants NAME=VALUE in --phase report, got {item!r}")
        out[name] = float(value)
    return out


def parse_grid(tokens: list[str] | None, default: str) -> list[float]:
    raw = tokens if tokens else [default]
    return [float(x) for token in raw for x in token.split(",") if x]


def tune_block(report: dict) -> str:
    out = ["| row | w | ndcg@10 delta vs baseline |", "|---|---|---|"]
    for row_name, by_w in report["tune"].items():
        for w, delta in sorted(by_w.items(), key=lambda kv: float(kv[0])):
            out.append(f"| {row_name} | {w} | {metrics.fmt_delta(delta)} |")
    return "\n".join(out) + "\n"


def report_block(report: dict) -> str:
    out = ["| row | ndcg@10 | recall@10 | ndcg@10 delta vs baseline |", "|---|---|---|---|"]
    for row_name, row in report["rows"].items():
        out.append(f"| {row_name} | {metrics.fmt_metric(row['ndcg10'])} | "
                   f"{metrics.fmt_metric(row['recall10'])} | "
                   f"{metrics.fmt_delta(row.get('vs_baseline'))} |")
    out.append("")
    out.append(f"own vs shuffled: {metrics.fmt_delta(report['deltas'].get('own_vs_shuffled'))}")
    if "vector_vs_vector_shuffled" in report["deltas"]:
        out.append(f"vector vs vector_shuffled: "
                   f"{metrics.fmt_delta(report['deltas']['vector_vs_vector_shuffled'])}")
    return "\n".join(out) + "\n"


BLOCKS = {"tune": tune_block, "report": report_block}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--split", required=True,
                    help="must be 'train' - this tool refuses any other value")
    ap.add_argument("--users", type=Path, default=None,
                    help="the users.json derive_users.py wrote; default "
                         "<build>/users.json")
    ap.add_argument("--half", choices=("tuning", "reporting"), required=True)
    ap.add_argument("--phase", choices=("tune", "report"), required=True)
    ap.add_argument("--ranking", choices=("personalized", "personalized_lexical"),
                    default="personalized",
                    help="personalized (default): chapter 6's funnel plus "
                         "this chapter's terms - brand, colour, and the "
                         "user's own title vector. personalized_lexical: "
                         "chapter 3's keyword-matching profile plus only "
                         "the brand term - own/shuffled/upper only, no "
                         "colour row, no vector rows")
    ap.add_argument("--w", nargs="+", default=None,
                    help="--phase tune: a comma list of weights swept for "
                         "every row but vector/vector_shuffled (default "
                         f"{TUNE_GRID} under --ranking personalized, "
                         f"{TUNE_GRID_LEXICAL} under personalized_lexical). "
                         "--phase report: one weight per row, as separate "
                         "NAME=VALUE arguments - own=0.05 shuffled=0.05 upper=0.5 "
                         "colour=0.1 vector=1 vector_shuffled=1, the "
                         "chapter's weights (colour and the two vector "
                         "rows only exist under --ranking personalized)")
    ap.add_argument("--w-vector", dest="w_vector", nargs="+", default=None,
                    help="--phase tune only, --ranking personalized only: a "
                         "comma list of weights swept for the vector / "
                         f"vector_shuffled rows (default {TUNE_GRID_VECTOR}) "
                         "- the term is a cosine on real candidates, a "
                         "different scale from the brand/colour terms' "
                         "share-of-one, so it gets its own grid")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--block", choices=sorted(set(BLOCKS) | {"coverage"}), default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    metavar="REPORT",
                    help="print --block tune/report from a report this tool "
                         "already wrote, measuring nothing; with --block "
                         "coverage, REPORT must be a tune-phase report and "
                         "this also reads the build's own users.json and "
                         "products.jsonl (still no engine call)")
    args = ap.parse_args()

    require_train_split(args.split)
    if args.block is None:
        args.block = "tune" if args.phase == "tune" else "report"
    if args.block == "coverage" and not args.from_report:
        raise SystemExit(
            "--block coverage only prints from an existing tune report - "
            "pass --from <tune report>; it measures nothing on its own")

    applicable_rows = ROWS_BY_RANKING[args.ranking]

    if args.from_report:
        report = json.loads(args.from_report.read_text())
        if args.block == "coverage":
            build = args.build or builds.latest()
            users_path = args.users or (build / "users.json")
            payload = json.loads(users_path.read_text())
            users = [u for u in payload["users"] if u["half"] == args.half]
            brand_of = load_product_brands(build / "products.jsonl")
            print(coverage_block(report, users, brand_of))
        else:
            print(BLOCKS[args.block](report))
        return 0

    if args.ranking == "personalized_lexical" and args.w_vector:
        raise SystemExit(
            "--w-vector refused under --ranking personalized_lexical: it "
            "has no vector rows to sweep")

    # Validated before anything is measured (no build, no container, no
    # baseline pass yet): a row name this ranking cannot produce, or a row
    # this ranking needs with no weight given, is a refusal, not a partial
    # report five minutes into a run.
    w_by_row: dict[str, float] = {}
    if args.phase == "report":
        if not args.w:
            raise SystemExit(
                "--phase report needs --w, one weight per row: "
                + " ".join(f"{row}=0.1" for row in applicable_rows))
        w_by_row = parse_row_weights(args.w)
        unknown = sorted(set(w_by_row) - set(applicable_rows))
        if unknown:
            raise SystemExit(
                f"--w names {unknown}, not valid under --ranking "
                f"{args.ranking!r} (rows here: {', '.join(applicable_rows)})")
        missing = [row for row in applicable_rows if row not in w_by_row]
        if missing:
            raise SystemExit(f"--w is missing a weight for row(s): "
                             f"{', '.join(missing)}")

    build = args.build or builds.latest()
    users_path = args.users or (build / "users.json")
    payload = json.loads(users_path.read_text())
    users = [u for u in payload["users"] if u["half"] == args.half]
    color_of = load_color_of(build / "products.jsonl")

    app = Vespa(args.endpoint)
    if not app.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1

    user_ids = [u["user_id"] for u in users]
    docs = {uid: app.get_document(DOCTYPE, uid) for uid in user_ids}
    for uid, doc in docs.items():
        if doc is None:
            raise SystemExit(f"user document {uid!r} not found - feed and "
                             f"update the user documents before running "
                             f"this tool")
    shuffle_map, fixed_points = seeded_permutation(user_ids, SEED)

    own_brands: dict[str, dict[str, float]] = {}
    upper_brands: dict[str, dict[str, float]] = {}
    colours: dict[str, dict[str, float]] = {}
    own_vectors: dict[str, list[float]] = {}
    for user in users:
        uid = user["user_id"]
        cells = docs[uid].get("brand_weights", {}).get("cells", {})
        own_brands[uid] = normalise_weights(cells)
        upper_brands[uid] = normalise_weights(with_defining_brand(cells, user["defining_brand"]))
        colours[uid] = colour_distribution(user["profile_queries"], color_of)
        own_vectors[uid] = normalise_vector(docs[uid]["profile_vector"]["values"])

    # One (key, text, judgements) tuple per (user, held-out query) - a query
    # shared by several users is evaluated once per user, because each
    # user's profile row is different even when the query text is not. The
    # key is "<user_id>|<query_id>", so a later block (the coverage split)
    # can regroup these same per-query scores without re-measuring anything.
    pairs: list[tuple[str, str, dict]] = []
    brands_own_by_key: dict[str, dict] = {}
    brands_shuffled_by_key: dict[str, dict] = {}
    brands_upper_by_key: dict[str, dict] = {}
    colours_by_key: dict[str, dict] = {}
    vectors_own_by_key: dict[str, list] = {}
    vectors_shuffled_by_key: dict[str, list] = {}
    for user in users:
        uid = user["user_id"]
        other = shuffle_map[uid]
        for q in user["held_out_queries"]:
            key = f"{uid}|{q['query_id']}"
            pairs.append((key, q["query_text"], gain_judgements(q["judgements"])))
            brands_own_by_key[key] = own_brands[uid]
            brands_shuffled_by_key[key] = own_brands[other]
            brands_upper_by_key[key] = upper_brands[uid]
            colours_by_key[key] = colours[uid]
            vectors_own_by_key[key] = own_vectors[uid]
            vectors_shuffled_by_key[key] = own_vectors[other]

    cells_by_row = {
        "own": brands_own_by_key,
        "shuffled": brands_shuffled_by_key,
        "upper": brands_upper_by_key,
        "colour": colours_by_key,
        "vector": vectors_own_by_key,
        "vector_shuffled": vectors_shuffled_by_key,
    }

    print(f"{args.half} half: {len(users)} users, {len(pairs)} (user, "
          f"held-out query) pairs, ranking {args.ranking}", file=sys.stderr)

    def evaluate_row(row: str, w: float | None) -> tuple[dict, dict]:
        cells = cells_by_row.get(row, {})
        eval_pairs(app, pairs, row, w, args.ranking, cells, warm=True)
        return eval_pairs(app, pairs, row, w, args.ranking, cells, warm=False)

    started = time.time()
    baseline_results, baseline_ms = evaluate_row("baseline", None)

    if args.phase == "tune":
        default_grid = TUNE_GRID_LEXICAL if args.ranking == "personalized_lexical" else TUNE_GRID
        grid = parse_grid(args.w, default_grid)
        vector_grid = (parse_grid(args.w_vector, TUNE_GRID_VECTOR)
                      if "vector" in applicable_rows else [])
        tune: dict[str, dict[str, dict]] = {}
        for row in applicable_rows:
            tune[row] = {}
            row_grid = vector_grid if row in ("vector", "vector_shuffled") else grid
            for w in row_grid:
                results, _ms = evaluate_row(row, w)
                delta = metrics.bootstrap_delta(
                    {k: baseline_results[k]["ndcg10"] for k in results},
                    {k: v["ndcg10"] for k, v in results.items()})
                tune[row][str(w)] = {
                    **delta,
                    "per_query": {k: v["ndcg10"] for k, v in results.items()},
                }
        elapsed = time.time() - started
        report = {
            "build": builds.meta(build)["build_id"],
            "split": args.split,
            **deployed.stamp(),
            "half": args.half,
            "phase": args.phase,
            "ranking": args.ranking,
            "grid": grid,
            "vector_grid": vector_grid,
            "pairs": len(pairs),
            "tune": tune,
            "baseline_per_query": {k: v["ndcg10"] for k, v in baseline_results.items()},
            "shuffled_fixed_points_remaining": fixed_points,
            "latency_conditions": {"warm": True, "seconds": round(elapsed, 1)},
            "host": hostinfo.collect(),
        }
    else:
        # --w is already parsed and validated against this ranking's rows
        # (see w_by_row above, checked before any build/container access).
        rows = {"baseline": {
            "ndcg10": statistics.fmean(v["ndcg10"] for v in baseline_results.values()),
            "recall10": statistics.fmean(v["recall10"] for v in baseline_results.values()),
            "per_query": {k: v["ndcg10"] for k, v in baseline_results.items()},
        }}
        row_results = {}
        for row in applicable_rows:
            w = w_by_row.get(row)
            if w is None:
                raise SystemExit(f"--w is missing a weight for row {row!r}")
            results, _ms = evaluate_row(row, w)
            row_results[row] = results
            delta = metrics.bootstrap_delta(
                {k: baseline_results[k]["ndcg10"] for k in results},
                {k: v["ndcg10"] for k, v in results.items()})
            rows[row] = {
                "ndcg10": statistics.fmean(v["ndcg10"] for v in results.values()),
                "recall10": statistics.fmean(v["recall10"] for v in results.values()),
                "vs_baseline": delta,
                "per_query": {k: v["ndcg10"] for k, v in results.items()},
            }
        deltas = {
            "own_vs_shuffled": metrics.bootstrap_delta(
                {k: row_results["shuffled"][k]["ndcg10"] for k in row_results["own"]},
                {k: v["ndcg10"] for k, v in row_results["own"].items()}),
        }
        if "vector" in applicable_rows:
            deltas["vector_vs_vector_shuffled"] = metrics.bootstrap_delta(
                {k: row_results["vector_shuffled"][k]["ndcg10"] for k in row_results["vector"]},
                {k: v["ndcg10"] for k, v in row_results["vector"].items()})
        elapsed = time.time() - started
        report = {
            "build": builds.meta(build)["build_id"],
            "split": args.split,
            **deployed.stamp(),
            "half": args.half,
            "phase": args.phase,
            "ranking": args.ranking,
            "w": w_by_row,
            "pairs": len(pairs),
            "rows": rows,
            "deltas": deltas,
            "shuffled_fixed_points_remaining": fixed_points,
            "latency_conditions": {"warm": True, "seconds": round(elapsed, 1)},
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
