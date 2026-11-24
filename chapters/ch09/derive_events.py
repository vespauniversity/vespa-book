"""Turn a user's profile-half queries into an ordered event stream.

`derive_users.py` says which queries build a profile and which are held out;
it says nothing about order, because ESCI carries no timestamps. This tool
imposes one: for each user, its profile queries in the order they were split
into that half, and within a query its judged products in product-id order.
Every (user, query, product) triple where the product was judged Exact or
Substitute becomes one event, numbered from 1 per user.

The vocabulary is deliberately neutral. A judgement is an annotator's opinion
about a query and a product, made outside any shopping session - it is not a
purchase and not a click, and calling an Exact judgement "bought" or a
Substitute one "viewed" would make a false claim look like a measurement.
`judged_relevant` and `judged_substitute` are what the label actually says;
whatever a chapter wants that to stand in for is a sentence in its own
prose, not a word this file writes.

Every event also carries a time, because a profile that is meant to age has
to age against something. There is no real clock behind these judgements, so
one is chosen and fixed: a single snapshot day, Black Friday 2026, and every
user's newest event lands exactly there. Earlier events count back one day
each. That makes the whole file the same for every reader who runs this
command - a fixed day, not "whenever you happen to run this" - while still
giving each user's history the property recency weighting needs: later
events are newer.

    .venv/bin/python chapters/ch09/derive_events.py --split train \\
        --users builds/<build>/users.json \\
        --events-out builds/<build>/events.jsonl \\
        --out chapters/ch09/expected/events.json --block events
"""
from __future__ import annotations

import argparse
import calendar
import datetime
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))
import builds       # noqa: E402
import deployed     # noqa: E402
import hostinfo     # noqa: E402

ACTION_OF_LABEL = {"E": "judged_relevant", "S": "judged_substitute"}

# The one fixed day every derived event is measured against: a user's newest
# event lands here, and earlier events count back one calendar day apiece.
# Fixed rather than "whenever this command runs" so the file this writes is
# identical for every reader, and a story with a reason to be shopping -
# Black Friday 2026.
SNAPSHOT = "2026-11-27T00:00:00Z"
SNAPSHOT_EPOCH = calendar.timegm(
    datetime.datetime.strptime(SNAPSHOT, "%Y-%m-%dT%H:%M:%SZ").timetuple())
DAY_SECONDS = 86400


def repo_relative(path: Path) -> str:
    """A path for the committed report: relative to the repository root when it
    lies under it (`builds/<build>/events.jsonl`), so the report does not carry
    one machine's home directory; any other path as given."""
    try:
        return str(Path(path).relative_to(builds.ROOT))
    except ValueError:
        return str(path)


def require_train_split(split: str) -> None:
    if split != "train":
        raise SystemExit(
            f"--split {split!r} refused: this chapter's users and their "
            f"profile-half queries are derived from training judgements "
            f"only, never validation or test")


def event_epoch(sequence_no: int, user_total: int,
                snapshot_epoch: int = SNAPSHOT_EPOCH) -> int:
    """The one clock every event is stamped with: the user's last event
    (`sequence_no == user_total`) lands on the snapshot day, and every
    earlier one counts back a day per step - `t = snapshot - (total - seq)
    * 86400`."""
    return snapshot_epoch - (user_total - sequence_no) * DAY_SECONDS


def iso_time(epoch: int) -> str:
    return datetime.datetime.fromtimestamp(
        epoch, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_events(users: list[dict]) -> list[dict]:
    """One event per (user, profile-half query, Exact-or-Substitute product),
    in file order for the users, profile-half order for a user's queries,
    and product-id order within a query - `sequence_no` counts 1..n per user
    across every one of their queries, and each event's time counts back
    from the snapshot day by one day per step, newest event on the snapshot
    itself."""
    per_user_events: list[tuple[dict, str, str, str, int]] = []
    for user in users:
        seq = 0
        for query in user["profile_queries"]:
            judged = query["judgements"]
            for pid, label in sorted(judged.items()):
                action = ACTION_OF_LABEL.get(label)
                if action is None:
                    continue
                seq += 1
                per_user_events.append(
                    (user, query["query_id"], pid, action, seq))

    events = []
    totals: dict[str, int] = {}
    for user, _, _, _, seq in per_user_events:
        uid = user["user_id"]
        totals[uid] = max(totals.get(uid, 0), seq)
    for user, qid, pid, action, seq in per_user_events:
        uid = user["user_id"]
        epoch = event_epoch(seq, totals[uid])
        events.append({
            "user_id": uid,
            "sequence_no": seq,
            "query_id": qid,
            "product_id": pid,
            "action": action,
            "event_epoch": epoch,
            "event_time": iso_time(epoch),
        })
    return events


def event_counts(events: list[dict]) -> dict:
    per_action: dict[str, int] = {}
    for e in events:
        per_action[e["action"]] = per_action.get(e["action"], 0) + 1
    per_user: dict[str, int] = {}
    for e in events:
        per_user[e["user_id"]] = max(per_user.get(e["user_id"], 0), e["sequence_no"])
    counts = sorted(per_user.values())
    return {
        "per_action": per_action,
        "users_with_events": len(per_user),
        "events_per_user_min": counts[0] if counts else 0,
        "events_per_user_median": statistics.median(counts) if counts else 0,
        "events_per_user_max": counts[-1] if counts else 0,
    }


def events_block(report: dict) -> str:
    c = report["counts"]
    rows = [
        ("judged_relevant events", c["per_action"].get("judged_relevant", 0)),
        ("judged_substitute events", c["per_action"].get("judged_substitute", 0)),
        ("users with events", c["users_with_events"]),
        ("events per user (min)", c["events_per_user_min"]),
        ("events per user (median)", c["events_per_user_median"]),
        ("events per user (max)", c["events_per_user_max"]),
    ]
    out = ["| metric | value |", "|---|---|"]
    out += [f"| {k} | {v:,} |" for k, v in rows]
    return "\n".join(out) + "\n"


BLOCKS = {"events": events_block}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--split", required=True,
                    help="must be 'train' - this tool refuses any other value")
    ap.add_argument("--users", type=Path, default=None,
                    help="the users.json derive_users.py wrote; default "
                         "<build>/users.json")
    ap.add_argument("--events-out", type=Path, default=None,
                    help="the event stream; default <build>/events.jsonl")
    ap.add_argument("--out", type=Path, default=None, help="the derivation report")
    ap.add_argument("--block", choices=sorted(BLOCKS), default="events")
    args = ap.parse_args()

    require_train_split(args.split)

    build = args.build or builds.latest()
    users_path = args.users or (build / "users.json")
    users_payload = json.loads(users_path.read_text())
    users = users_payload["users"]

    events = build_events(users)
    counts = event_counts(events)

    events_out = args.events_out or (build / "events.jsonl")
    events_out.parent.mkdir(parents=True, exist_ok=True)
    with events_out.open("w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    print(f"wrote {events_out} ({len(events)} events)", file=sys.stderr)

    report = {
        "build": builds.meta(build)["build_id"],
        "split": args.split,
        **deployed.stamp(),
        "users_source": repo_relative(users_path),
        "snapshot": SNAPSHOT,
        "snapshot_epoch": SNAPSHOT_EPOCH,
        "events": len(events),
        "counts": counts,
        "events_out": repo_relative(events_out),
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
