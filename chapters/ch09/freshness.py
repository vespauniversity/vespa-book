"""How long a partial update takes to become visible: from the moment it is
acknowledged to the moment a plain GET shows it, to the moment the query API
finds the same update, and to the moment a recommendation request built from
the document reflects it.

For a sample of reporting-half users this sends one real event - the user's
own first held-out Exact product, folded into the profile exactly the way
`profile_updater.py` folds every event (running mean, brand weight unless the
brand defined the user, seen, event time, event count) - records how long each
kind of visibility took, then puts the document back as it was and checks that
it did. The query API check looks the id up the way a search would, a plain match on
the `user_id` attribute with no ranking, and counts the update as found when
the one hit's `events_applied` has gone up by one. "Reflects it" means the
recommendation's top ten equals the top ten the
new profile vector produces; one more product in a mean of many moves it a
little, so for a few users that top ten is the same as before, and for them
the recommendation check cannot tell the new profile from the old. The event
is stamped one day past the snapshot day, on the chapter's one clock. The
order the events would arrive in is invented (no chapter claims otherwise);
how long one update takes to be seen on this machine is measured, not
invented.

    .venv/bin/python chapters/ch09/freshness.py --split train --users 50 \\
        --out chapters/ch09/expected/freshness.json --block freshness-search
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))
import builds       # noqa: E402
import deployed     # noqa: E402
import embed_offline  # noqa: E402
import hostinfo     # noqa: E402
import metrics      # noqa: E402
from query import Vespa  # noqa: E402

from recommend import query_once  # noqa: E402
import profile_updater  # noqa: E402
from derive_events import SNAPSHOT_EPOCH, DAY_SECONDS  # noqa: E402

DOCTYPE = "user"
POLL_INTERVAL = 0.05
POLL_CAP_SECONDS = 5.0
SEED = 42


def require_train_split(split: str) -> None:
    if split != "train":
        raise SystemExit(
            f"--split {split!r} refused: the reporting-half users this "
            f"tool samples are derived from training judgements only")


def first_held_out_product(user: dict) -> str | None:
    for q in user["held_out_queries"]:
        if q["e_products"]:
            return q["e_products"][0]
    return None


def top_ten_ids(app: Vespa, vector: list[float], seen: set[str], hits: int = 100) -> list[str]:
    r, _ms = query_once(app, vector, hits + len(seen))
    return [h.fields.get("id", "") for h in r.hits if h.fields.get("id") not in seen][:10]


def user_search_yql(user_id: str) -> str:
    """The query-API lookup of one user: a plain match on the `user_id`
    attribute. A YQL string literal is double-quoted, so a backslash and a
    double quote in the id are escaped; an apostrophe or a space needs
    nothing."""
    escaped = user_id.replace("\\", "\\\\").replace('"', '\\"')
    return f'select * from {DOCTYPE} where user_id contains "{escaped}"'


def search_user(app: Vespa, user_id: str):
    """One query-API request for one user: `unranked` (the user schema has no
    other rank profile) and one hit, which is all the lookup needs."""
    return app.query(user_search_yql(user_id), ranking="unranked", hits=1)


def poll_until(condition, interval: float = POLL_INTERVAL,
              cap: float = POLL_CAP_SECONDS, since: float | None = None) -> float | None:
    """Polls `condition()` until it is true, returning the milliseconds from
    `since` (a `perf_counter` reading; the call itself when omitted) to the
    moment it held, or `None` (a miss) if `cap` seconds pass first."""
    started = time.perf_counter()
    origin = started if since is None else since
    while True:
        if condition():
            return (time.perf_counter() - origin) * 1000
        if time.perf_counter() - started > cap:
            return None
        time.sleep(interval)


class _CaptureFields:
    """Stands in for the Vespa client inside `profile_updater.apply_events_for_user`
    so the one update that function would send is captured instead of sent -
    this tool sends it itself, timing the acknowledgement."""

    def __init__(self) -> None:
        self.fields: list[dict] = []

    def update_document(self, doctype, doc_id, fields):
        self.fields.append(fields)
        return {}


def event_fields(user_id: str, events: list[dict], pid: str, event_epoch: float,
                 titles_brands: dict[str, tuple[str, str]], defining_brand: str,
                 vectors_by_pid: dict[str, list[float]]) -> dict:
    """The partial update `profile_updater.py` would send for one more
    `judged_relevant` event on this user - the whole history replayed in
    memory first, so the running mean and the brand total are right."""
    last_seq = max((e["sequence_no"] for e in events), default=0)
    new_event = {"sequence_no": last_seq + 1, "product_id": pid,
                 "action": "judged_relevant", "event_epoch": event_epoch}
    capture = _CaptureFields()
    profile_updater.apply_events_for_user(
        capture, user_id, events + [new_event], titles_brands, defining_brand,
        vectors_by_pid, rng=(last_seq + 1, last_seq + 1), reset=False,
        after_snapshot=None)
    if len(capture.fields) != 1:
        raise SystemExit(f"expected one update for {user_id!r}, got {len(capture.fields)}")
    return capture.fields[0]


def one_user(app: Vespa, user_id: str, user: dict, events: list[dict],
            titles_brands: dict[str, tuple[str, str]], defining_brand: str,
            vectors_by_pid: dict[str, list[float]]) -> dict:
    original = app.get_document(DOCTYPE, user_id)
    if original is None:
        raise SystemExit(f"user document {user_id!r} not found")

    pid = first_held_out_product(user)
    if pid is None:
        return {"user_id": user_id, "skipped": "no held-out Exact product"}

    original_seen = list(original.get("seen") or [])
    original_vector = original["profile_vector"]["values"]
    original_events_applied = original["events_applied"]
    # The `event_times` / `brand_weights` cells this event touches may already
    # exist (a product judged for a profile-half query can be the held-out
    # product of another); the restore puts those values back rather than
    # deleting the cells.
    original_cells = (original.get("event_times") or {}).get("cells", {})
    had_cell = pid in original_cells
    original_cell_value = original_cells.get(pid)
    original_brand_cells = (original.get("brand_weights") or {}).get("cells", {})

    # The chapter's one clock: every time in `event_times` is counted from the
    # snapshot day `derive_events.py` fixes, never from the wall clock, so
    # this event is stamped one day past it, like the next-day demonstration.
    event_epoch = SNAPSHOT_EPOCH + DAY_SECONDS
    fields = event_fields(user_id, events, pid, event_epoch, titles_brands,
                          defining_brand, vectors_by_pid)
    new_vector = fields["profile_vector"]["assign"]["values"]
    brand = None
    if "brand_weights" in fields:
        brand = fields["brand_weights"]["add"]["cells"][0]["address"]["brand"]
    had_brand_cell = brand is not None and brand in original_brand_cells
    original_brand_value = original_brand_cells.get(brand) if brand else None

    seen_after = set(original_seen) | {pid}
    before_top_ten = top_ten_ids(app, original_vector, seen_after)
    # What the recommendation built from the updated document must show: the
    # top ten the new profile vector produces (the request carries the vector,
    # so it can be asked before the document changes).
    expected_top_ten = top_ten_ids(app, new_vector, seen_after)

    ack_started = time.perf_counter()  # only for timing the acknowledgement
    app.update_document(DOCTYPE, user_id, fields)
    acked = time.perf_counter()
    ack_ms = (acked - ack_started) * 1000

    def get_shows_it() -> bool:
        doc = app.get_document(DOCTYPE, user_id)
        return doc is not None and doc["events_applied"] == original_events_applied + 1

    def search_shows_it() -> bool:
        r = search_user(app, user_id)
        return (len(r.hits) == 1
                and r.hits[0].fields.get("events_applied") == original_events_applied + 1)

    def query_shows_it() -> bool:
        doc = app.get_document(DOCTYPE, user_id)
        if doc is None:
            return False
        current = top_ten_ids(app, doc["profile_vector"]["values"],
                              set(doc.get("seen") or []) | {pid})
        return current == expected_top_ten

    t_get_ms = poll_until(get_shows_it, since=acked)
    t_search_ms = poll_until(search_shows_it, since=acked)
    t_query_ms = poll_until(query_shows_it, since=acked)

    if had_cell:
        restore_cell = {"add": {"cells": [
            {"address": {"product": pid}, "value": original_cell_value}]}}
    else:
        restore_cell = {"remove": {"addresses": [{"product": pid}]}}
    restore = {
        "profile_vector": {"assign": {"values": original_vector}},
        "events_applied": {"assign": original_events_applied},
        "seen": {"assign": original_seen},
        "event_times": restore_cell,
    }
    if brand is not None:
        restore["brand_weights"] = (
            {"add": {"cells": [{"address": {"brand": brand}, "value": original_brand_value}]}}
            if had_brand_cell else
            {"remove": {"addresses": [{"brand": brand}]}})
    app.update_document(DOCTYPE, user_id, restore)
    restored = app.get_document(DOCTYPE, user_id)
    restored_cells = ((restored or {}).get("event_times") or {}).get("cells", {})
    restored_brands = ((restored or {}).get("brand_weights") or {}).get("cells", {})
    cell_ok = (restored_cells.get(pid) == original_cell_value if had_cell
               else pid not in restored_cells)
    brand_ok = (brand is None
                or (restored_brands.get(brand) == original_brand_value if had_brand_cell
                    else brand not in restored_brands))
    restore_ok = (restored is not None
                 and restored["events_applied"] == original_events_applied
                 and list(restored.get("seen") or []) == original_seen
                 and restored["profile_vector"]["values"] == original_vector
                 and cell_ok and brand_ok)

    return {
        "user_id": user_id,
        "product_id": pid,
        "ack_ms": round(ack_ms, 2),
        "get_visible_ms": None if t_get_ms is None else round(t_get_ms, 2),
        "get_visible_miss": t_get_ms is None,
        "search_visible_ms": None if t_search_ms is None else round(t_search_ms, 2),
        "search_visible_miss": t_search_ms is None,
        "query_visible_ms": None if t_query_ms is None else round(t_query_ms, 2),
        "query_visible_miss": t_query_ms is None,
        "top_ten_changed": expected_top_ten != before_top_ten,
        "restore_verified": restore_ok,
    }


def freshness_block(report: dict) -> str:
    s = report["summary"]
    out = ["| n | ack -> GET p50 | ack -> GET p95 | ack -> query p50 | "
          "ack -> query p95 | top ten changed | misses |",
          "|---|---|---|---|---|---|---|"]
    out.append(
        f"| {s['n']} | {metrics.fmt_latency(s['get_visible_p50'])} | "
        f"{metrics.fmt_latency(s['get_visible_p95'])} | "
        f"{metrics.fmt_latency(s['query_visible_p50'])} | "
        f"{metrics.fmt_latency(s['query_visible_p95'])} | "
        f"{s['top_ten_changed']} of {s['n']} | "
        f"{s['get_visible_misses']} get / {s['query_visible_misses']} query |")
    return "\n".join(out) + "\n"


def freshness_search_block(report: dict) -> str:
    s = report["summary"]
    out = ["| n | ack -> GET p50 | ack -> GET p95 | ack -> search p50 | "
          "ack -> search p95 | ack -> query p50 | ack -> query p95 | "
          "top ten changed | misses |",
          "|---|---|---|---|---|---|---|---|---|"]
    out.append(
        f"| {s['n']} | {metrics.fmt_latency(s['get_visible_p50'])} | "
        f"{metrics.fmt_latency(s['get_visible_p95'])} | "
        f"{metrics.fmt_latency(s['search_visible_p50'])} | "
        f"{metrics.fmt_latency(s['search_visible_p95'])} | "
        f"{metrics.fmt_latency(s['query_visible_p50'])} | "
        f"{metrics.fmt_latency(s['query_visible_p95'])} | "
        f"{s['top_ten_changed']} of {s['n']} | "
        f"{s['get_visible_misses']} get / {s['search_visible_misses']} search / "
        f"{s['query_visible_misses']} query |")
    return "\n".join(out) + "\n"


BLOCKS = {"freshness": freshness_block,
          "freshness-search": freshness_search_block}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--split", required=True,
                    help="must be 'train' - this tool refuses any other value")
    ap.add_argument("--users-file", type=Path, default=None,
                    help="the users.json derive_users.py wrote; default "
                         "<build>/users.json")
    ap.add_argument("--events-file", type=Path, default=None,
                    help="the event stream derive_events.py wrote; default "
                         "<build>/events.jsonl")
    ap.add_argument("--users", type=int, default=50, metavar="N",
                    help="how many reporting-half users to sample, seeded")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--block", choices=sorted(BLOCKS), default="freshness")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    metavar="REPORT",
                    help="print --block from a report this tool "
                         "already wrote, touching no document a second time")
    args = ap.parse_args()

    require_train_split(args.split)

    if args.from_report:
        report = json.loads(args.from_report.read_text())
        print(BLOCKS[args.block](report))
        return 0

    build = args.build or builds.latest()
    users_path = args.users_file or (build / "users.json")
    payload = json.loads(users_path.read_text())
    reporting = [u for u in payload["users"] if u["half"] == "reporting"]

    rng = random.Random(SEED)
    chosen = rng.sample(reporting, min(args.users, len(reporting)))

    app = Vespa(args.endpoint)
    if not app.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1

    # The event is folded in the way `profile_updater.py` folds every event,
    # which needs each sampled user's whole history (for the running mean and
    # the brand total) and the title vectors of every product in it.
    events_path = args.events_file or (build / "events.jsonl")
    grouped = profile_updater.group_by_user(profile_updater.load_events(events_path, None))
    defining_brand_of = profile_updater.load_defining_brands(users_path)
    titles_brands = profile_updater.load_product_titles_and_brands(build / "products.jsonl")
    pids = set()
    for u in chosen:
        pid = first_held_out_product(u)
        if pid is not None:
            pids.add(pid)
        pids.update(e["product_id"] for e in grouped.get(u["user_id"], [])
                    if e["action"] == "judged_relevant")
    print(f"encoding {len(pids)} product titles", file=sys.stderr)
    encoder = embed_offline.Encoder("bge")
    vectors_by_pid = profile_updater.encode_in_batches(
        encoder, {pid: titles_brands.get(pid, ("", ""))[0] for pid in sorted(pids)},
        encoder.cfg["doc_prefix"])

    # Warm the recommendation request and the query-API lookup once before
    # any of it is timed - the same convention every latency figure in this
    # project follows.
    if chosen:
        search_user(app, chosen[0]["user_id"])
        warm_doc = app.get_document(DOCTYPE, chosen[0]["user_id"])
        if warm_doc is not None:
            top_ten_ids(app, warm_doc["profile_vector"]["values"],
                       set(warm_doc.get("seen") or []))

    results = []
    for user in chosen:
        results.append(one_user(app, user["user_id"], user,
                                grouped.get(user["user_id"], []), titles_brands,
                                defining_brand_of.get(user["user_id"], ""), vectors_by_pid))
        print(f"  {results[-1]['user_id']}: "
              f"{ {k: v for k, v in results[-1].items() if k != 'user_id'} }",
              file=sys.stderr)

    measured = [r for r in results if "skipped" not in r]
    get_values = [r["get_visible_ms"] for r in measured if r["get_visible_ms"] is not None]
    search_values = [r["search_visible_ms"] for r in measured if r["search_visible_ms"] is not None]
    query_values = [r["query_visible_ms"] for r in measured if r["query_visible_ms"] is not None]
    get_p = metrics.percentiles(get_values)
    search_p = metrics.percentiles(search_values)
    query_p = metrics.percentiles(query_values)
    summary = {
        "n": len(measured),
        "skipped": len(results) - len(measured),
        "get_visible_p50": get_p.get("p50"),
        "get_visible_p95": get_p.get("p95"),
        "get_visible_misses": sum(1 for r in measured if r["get_visible_miss"]),
        "search_visible_p50": search_p.get("p50"),
        "search_visible_p95": search_p.get("p95"),
        "search_visible_misses": sum(1 for r in measured if r["search_visible_miss"]),
        "query_visible_p50": query_p.get("p50"),
        "query_visible_p95": query_p.get("p95"),
        "query_visible_misses": sum(1 for r in measured if r["query_visible_miss"]),
        "top_ten_changed": sum(1 for r in measured if r["top_ten_changed"]),
        "restore_verified_all": all(r["restore_verified"] for r in measured),
    }

    report = {
        "build": builds.meta(build)["build_id"],
        "split": args.split,
        **deployed.stamp(),
        "sample": args.users,
        "results": results,
        "summary": summary,
        "latency_conditions": {
            "warm": True,
            "note": "the recommendation request and the query-API lookup "
                    "were each warmed once before any user in the sample "
                    "was timed; all three visibility times count from the "
                    "acknowledgement; each check starts when the one "
                    "before it has passed; poll interval "
                    f"{POLL_INTERVAL}s, capped at {POLL_CAP_SECONDS}s per wait",
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
