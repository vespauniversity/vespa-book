"""Apply a derived event stream to user documents, one partial update per
event - the online side of a profile: a judgement arrives, one partial update
changes one document, the next query sees it.

A `judged_relevant` event moves the user's `profile_vector` to the plain
running mean of every product title vector judged relevant so far (the same
pinned embedder used everywhere else in this project, encoded once up front
for speed and then sent one update at a time, in event order), adds one to
that product's brand in `brand_weights` - except the brand that defined the
user in the first place, which this tool never counts, so the profile is
built from a user's *other* interests rather than restating the one thing
already known about them - and records when the event happened in
`event_times`, one cell per product id. A `judged_substitute` event only
records that the product was seen. Both append the product id to `seen` and
count one more event applied.

`profile_vector` itself never ages - it is the plain average, and every
number this chapter reports is measured against it. `event_times` is what
lets a request compute an aged version of the profile on demand
(`recommend.py --half-life`), without this tool needing to know, at write
time, how old any event will be asked to look.

`--after-snapshot <k>` re-stamps every event this run sends as `k` days past
the fixed snapshot day `derive_events.py` uses, instead of the time already
written into the event stream - for showing the same profile a day later
without waiting for a real next day. With `--events`, an event the document
has already applied (its product is in `seen`) is not applied twice: it only
has its `event_times` stamp rewritten, so the mean, `seen` and the event count
stay what the full history made them. A run without `--events` applies every
event in the stream, a product that repeats in it included.

    .venv/bin/python chapters/ch09/profile_updater.py builds/<build>/events.jsonl \\
        --split train --out chapters/ch09/expected/profile-updates.json --block updates
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))
import builds       # noqa: E402
import deployed     # noqa: E402
import embed_offline  # noqa: E402
import hostinfo     # noqa: E402
from derive_events import SNAPSHOT_EPOCH, DAY_SECONDS  # noqa: E402
from query import Vespa  # noqa: E402


def repo_relative(path: Path) -> str:
    """A path for the committed report: relative to the repository root when it
    lies under it (`builds/<build>/events.jsonl`), so the report does not carry
    one machine's home directory; any other path as given."""
    try:
        return str(Path(path).relative_to(builds.ROOT))
    except ValueError:
        return str(path)

DOCTYPE = "user"


def require_train_split(split: str) -> None:
    if split != "train":
        raise SystemExit(
            f"--split {split!r} refused: the event stream this tool applies "
            f"was derived from training judgements only, never validation "
            f"or test")


def normalise_brand(raw: str | None) -> str:
    return " ".join((raw or "").split()).lower()


def load_product_titles_and_brands(products_path: Path) -> dict[str, tuple[str, str]]:
    """product id -> (title, normalised brand)."""
    out: dict[str, tuple[str, str]] = {}
    with products_path.open() as fh:
        for line in fh:
            rec = json.loads(line)
            fields = rec["fields"]
            out[fields["id"]] = (fields.get("title", ""), normalise_brand(fields.get("brand")))
    return out


def load_defining_brands(users_path: Path) -> dict[str, str]:
    payload = json.loads(users_path.read_text())
    return {u["user_id"]: u["defining_brand"] for u in payload["users"]}


def encode_in_batches(encoder, title_of: dict[str, str], prefix: str,
                      batch: int = 64) -> dict[str, list[float]]:
    """Encode every title, a batch at a time, in product-id order.

    One call over twenty thousand titles is a single forward pass whose
    working memory grows with the batch (the padded token matrix and every
    layer's activations for all of them at once) - on this machine it was
    killed at around twelve gigabytes. Sixty-four at a time is what the
    corpus encoder uses, and the vectors are the same either way: each title
    is encoded on its own, so the batch it happens to share changes nothing.
    """
    pids = sorted(title_of)
    out: dict[str, list[float]] = {}
    for start in range(0, len(pids), batch):
        chunk = pids[start:start + batch]
        vectors = encoder.encode([title_of[pid] for pid in chunk], prefix)
        for pid, vec in zip(chunk, vectors):
            out[pid] = [float(x) for x in vec]
    return out


def load_events(events_path: Path, user: str | None) -> list[dict]:
    events = []
    with events_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            if user is not None and e["user_id"] != user:
                continue
            events.append(e)
    return events


def group_by_user(events: list[dict]) -> dict[str, list[dict]]:
    """Preserves each user's own event order and the file's own user order -
    a plain dict, not a Counter or a set, because both matter here."""
    grouped: dict[str, list[dict]] = {}
    for e in events:
        grouped.setdefault(e["user_id"], []).append(e)
    return grouped


def parse_range(spec: str | None) -> tuple[int, int] | None:
    if spec is None:
        return None
    a, sep, b = spec.partition("-")
    if not sep:
        raise SystemExit(f"--events wants A-B, got {spec!r}")
    return int(a), int(b)


def in_range(seq: int, rng: tuple[int, int] | None) -> bool:
    return rng is None or (rng[0] <= seq <= rng[1])


def running_mean(vectors: list[list[float]]) -> list[float]:
    """The plain average `judged_relevant` assigns `profile_vector` to -
    every product title vector judged relevant so far, weighted equally.
    This is the one profile every chapter measurement reads; nothing here
    ages it."""
    dims = len(vectors[0])
    sums = [0.0] * dims
    for vec in vectors:
        for i, x in enumerate(vec):
            sums[i] += x
    n = len(vectors)
    return [s / n for s in sums]


def reset_fields(dims: int = 384) -> dict:
    return {
        "profile_vector": {"assign": {"values": [0.0] * dims}},
        "brand_weights": {"assign": {"cells": []}},
        "event_times": {"assign": {"cells": []}},
        "seen": {"assign": []},
        "events_applied": {"assign": 0},
    }


def apply_events_for_user(app: Vespa, user_id: str, events: list[dict],
                          titles_brands: dict[str, tuple[str, str]],
                          defining_brand: str, vectors_by_pid: dict[str, list[float]],
                          *, rng: tuple[int, int] | None, reset: bool,
                          after_snapshot: int | None,
                          already_seen: set[str] | None = None) -> tuple[int, int, int]:
    """Replays this user's whole event history in memory (so the running
    mean and the brand totals are correct regardless of `rng`), and sends
    one partial update to the document for every event inside `rng` (every
    event, if `rng` is `None`). Only on a range run (`rng` given), an event
    inside `rng` whose product the document has already applied
    (`already_seen`, the document's `seen`) is re-stamped only: its
    `event_times` cell gets this run's time and nothing else is sent for
    it. A full run (`rng` is `None`) applies every event, a product that
    repeats in the stream included - it enters the mean, `seen` and the
    count again, as it did when the chapter's state was built. Returns
    (events replayed, updates sent, events re-stamped)."""
    if reset:
        app.update_document(DOCTYPE, user_id, reset_fields())

    history_vectors: list[list[float]] = []
    brand_totals: dict[str, float] = {}
    sent = 0
    restamped = 0
    applied = set(already_seen or ())

    for event in events:
        seq = event["sequence_no"]
        pid = event["product_id"]
        fields: dict = {}

        if after_snapshot is not None:
            event_epoch = SNAPSHOT_EPOCH + after_snapshot * DAY_SECONDS
        else:
            event_epoch = event["event_epoch"]

        if event["action"] == "judged_relevant":
            history_vectors.append(vectors_by_pid[pid])
            mean = running_mean(history_vectors)
            fields["profile_vector"] = {
                "assign": {"values": [round(float(x), 6) for x in mean]}}
            fields["event_times"] = {
                "add": {"cells": [{"address": {"product": pid}, "value": event_epoch}]}}

            _title, brand = titles_brands.get(pid, ("", ""))
            if brand and brand != defining_brand:
                brand_totals[brand] = brand_totals.get(brand, 0.0) + 1.0
                fields["brand_weights"] = {
                    "add": {"cells": [{"address": {"brand": brand},
                                       "value": brand_totals[brand]}]}}

        fields["seen"] = {"add": [pid]}
        fields["events_applied"] = {"increment": 1}

        if in_range(seq, rng):
            # The re-stamp branch is for `--events` only: a full run sends
            # every event, repeats included.
            if rng is not None and pid in applied:
                if "event_times" in fields:
                    app.update_document(DOCTYPE, user_id, {"event_times": fields["event_times"]})
                    restamped += 1
            else:
                app.update_document(DOCTYPE, user_id, fields)
                sent += 1
                applied.add(pid)

    return len(events), sent, restamped


def updates_block(report: dict) -> str:
    return ("| events applied | seconds | updates per second |\n"
            "|---|---|---|\n"
            f"| {report['events_sent']:,} | {report['seconds']:.1f} | "
            f"{report['updates_per_second']:,.0f} |\n")


BLOCKS = {"updates": updates_block}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("events_file", type=Path, nargs="?", default=None,
                    help="the event stream derive_events.py wrote; default "
                         "<build>/events.jsonl")
    ap.add_argument("--split", required=True,
                    help="must be 'train' - this tool refuses any other value")
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--users", type=Path, default=None,
                    help="the users.json derive_users.py wrote, read only "
                         "for each user's defining brand; default "
                         "<build>/users.json")
    ap.add_argument("--user", default=None, help="restrict to one user id")
    ap.add_argument("--events", default=None, metavar="A-B",
                    help="send updates only for sequence numbers A..B "
                         "(inclusive); the full history up to B is still "
                         "replayed in memory first, so the running mean and "
                         "the brand totals are correct - only which updates "
                         "are actually sent is restricted")
    ap.add_argument("--reset", action="store_true",
                    help="with --user: put that document back to its empty "
                         "feed state before applying anything")
    ap.add_argument("--after-snapshot", type=int, default=None, metavar="K",
                    help="stamp every event this run sends as K days past "
                         "the snapshot day, instead of the time already in "
                         "the event stream - for a demonstration that moves "
                         "events past the snapshot day")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--block", choices=sorted(BLOCKS), default="updates")
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    metavar="REPORT",
                    help="print --block updates from a report this tool "
                         "already wrote, sending nothing")
    args = ap.parse_args()

    require_train_split(args.split)

    if args.from_report:
        report = json.loads(args.from_report.read_text())
        print(BLOCKS[args.block](report))
        return 0

    if args.reset and not args.user:
        raise SystemExit("--reset needs --user: it resets one document, not every user")

    build = args.build or builds.latest()
    events_path = args.events_file or (build / "events.jsonl")
    users_path = args.users or (build / "users.json")

    events = load_events(events_path, args.user)
    if not events:
        raise SystemExit(f"no events found in {events_path}"
                         + (f" for user {args.user!r}" if args.user else ""))
    grouped = group_by_user(events)
    defining_brand_of = load_defining_brands(users_path)
    titles_brands = load_product_titles_and_brands(build / "products.jsonl")

    relevant_pids = sorted({e["product_id"] for e in events
                            if e["action"] == "judged_relevant"})
    print(f"encoding {len(relevant_pids)} product titles", file=sys.stderr)
    encoder = embed_offline.Encoder("bge")
    vectors_by_pid = encode_in_batches(
        encoder, {pid: titles_brands.get(pid, ("", ""))[0] for pid in relevant_pids},
        encoder.cfg["doc_prefix"])

    rng = parse_range(args.events)
    app = Vespa(args.endpoint)
    if not app.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1

    started = time.time()
    total_replayed = 0
    total_sent = 0
    total_restamped = 0
    n_users = len(grouped)
    for i, (user_id, user_events) in enumerate(grouped.items(), 1):
        # With a range and no reset, the document already holds some history:
        # read its `seen` so an event it has applied is re-stamped, not
        # applied a second time.
        already_seen: set[str] | None = None
        if rng is not None and not args.reset:
            doc = app.get_document(DOCTYPE, user_id)
            already_seen = set((doc or {}).get("seen") or [])
        replayed, sent, restamped = apply_events_for_user(
            app, user_id, user_events, titles_brands,
            defining_brand_of.get(user_id, ""), vectors_by_pid,
            rng=rng, reset=args.reset, after_snapshot=args.after_snapshot,
            already_seen=already_seen)
        total_replayed += replayed
        total_sent += sent
        total_restamped += restamped
        # One line per user only when one user was asked for; a full run over
        # thousands of users reports every five hundred, so a terminal (or a
        # transcript of one) is not thousands of lines long.
        if args.user or i % 500 == 0 or i == n_users:
            label = user_id if args.user else f"{i} of {n_users} users"
            print(f"  {label}: {replayed} events replayed, {sent} updates sent, "
                  f"{restamped} re-stamped"
                  if args.user else
                  f"  {label}: {total_replayed} events replayed, {total_sent} updates sent so far",
                  file=sys.stderr)
    elapsed = time.time() - started

    report = {
        "build": builds.meta(build)["build_id"],
        "split": args.split,
        **deployed.stamp(),
        "events_file": repo_relative(events_path),
        "users_file": repo_relative(users_path),
        "users_processed": len(grouped),
        "events_replayed": total_replayed,
        "events_sent": total_sent,
        "events_restamped": total_restamped,
        "after_snapshot": args.after_snapshot,
        "reset": args.reset,
        "range": list(rng) if rng else None,
        "seconds": round(elapsed, 3),
        "updates_per_second": round(total_sent / elapsed) if elapsed else 0,
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
