"""Tail latency and throughput of the engine under fan-out, with and without
a stream of writes - the engine's side of an agent's cost, the model left out.

An agent's task is several requests in a row, and many agents at once are
many such sequences interleaved. This replays the requests the rules planner
sent over the whole question set (from its trajectory log: the first-hop
title search and the second-hop category search, each inside its question's
pool, under `hybrid_rrf`) with N loops running at the same time, each walking
the questions in order and starting over when it reaches the end. Every
request is timed on the client, as `evaluate.py` times its queries; the
first `--warm-up` seconds are discarded and the `--window` seconds after them
are the measurement: p50 / p95 / p99 over the requests that completed inside
the window, and requests per second.

**Continuous indexing** is the same window with writes going on: one process
sends partial updates through the document API at a steady rate, each one
re-assigning a product its own current `tenant_id` (one partial update per
request), so the data does not change but
the engine does the work of a write for every one of them. The difference
between the two tables is what reads pay for writes on this machine.

One pass per cell, not three: this is one machine's record, taken once, and
the block says so. The model is not involved at all.

Usage:
    python chapters/ch10/fanout_latency.py \\
        chapters/ch10/expected/trajectories/rules-alternative-k3.jsonl --split test \\
        --out chapters/ch10/expected/fanout-latency.json --block fanout
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import builds       # noqa: E402
import deployed     # noqa: E402
import hostinfo     # noqa: E402
import metrics      # noqa: E402
from corpus import LOCALE                 # noqa: E402
from query import Vespa, add_where_clause   # noqa: E402

import eval_trajectory   # noqa: E402
import tools_schema      # noqa: E402

PROFILE = "hybrid_rrf"
CONCURRENCY = (1, 2, 4)
WARM_UP_S = 20.0
WINDOW_S = 60.0
UPDATE_RATE = 200.0
STREAM_THREADS = 8
MACHINE = ("One pass per cell on an Apple M4 Pro with a 4 CPU / 10 GB container VM "
           "(Rancher Desktop); a reader's machine will give other numbers.")
CAPTION = ("Replay of the rules planner's requests ({requests:,} from `{log}`: each "
           "search as the planner sent it, inside its question's pool, under `{profile}`) "
           "by N loops at once, each walking the questions in order, for a {window:.0f} s "
           "window after a {warm:.0f} s warm-up; client-measured, over the requests that "
           "completed inside the window. The update stream is one process re-assigning "
           "each product its own `tenant_id` through the document API at a target of "
           "{rate:.0f} updates/s (achieved {achieved}), so the data does not change "
           "while the engine does every write. The model is not involved: this is the "
           "engine's side only. {machine}")


def replay_requests(lines: list[dict], questions: dict[str, dict]) -> list[dict]:
    """The requests the rules planner's log says it sent, in log order: one
    per `search` step (the statement as the tool built it; a status re-run
    the tool made on its own is not replayed)."""
    out: list[dict] = []
    for line in lines:
        q = questions[line["question_id"]]
        for step in line["steps"]:
            if step.get("tool") != "search":
                continue
            args = step["args"]
            hits = int(args.get("hits") or line["k"])
            req = tools_schema._request(str(args["query"]), args.get("ranking") or PROFILE, hits)
            yql = req.pop("yql")
            if q.get("pool"):
                yql = add_where_clause(yql, tools_schema.pool_clause(q["pool"]))
            if args.get("where"):
                yql = add_where_clause(yql, args["where"])
            out.append({"yql": yql, "ranking": args.get("ranking") or PROFILE,
                        "hits": hits, **req})
    return out


def summarise(samples: list[tuple[float, float]], start: float, end: float) -> dict:
    """p50 / p95 / p99 / mean / max and the rate over the samples (wall time
    of completion, ms) that completed between `start` and `end`."""
    inside = [ms for t, ms in samples if start <= t < end]
    window = end - start
    return {"requests": len(inside), "rps": len(inside) / window if window else 0.0,
            "latency_ms": metrics.percentiles(inside)}


def _loop(endpoint: str, requests_: list[dict], deadline: float,
          samples: list, errors: list) -> None:
    app = Vespa(endpoint)
    i = 0
    while time.time() < deadline:
        req = dict(requests_[i])
        i = (i + 1) % len(requests_)
        started = time.perf_counter()
        try:
            app.query(req.pop("yql"), **req)
        except RuntimeError:
            errors.append(1)
            continue
        samples.append((time.time(), (time.perf_counter() - started) * 1000))


def run_cell(endpoint: str, requests_: list[dict], concurrency: int,
             warm_up: float, window: float) -> dict:
    samples: list[tuple[float, float]] = []
    errors: list[int] = []
    start = time.time()
    deadline = start + warm_up + window
    threads = [threading.Thread(target=_loop, args=(endpoint, requests_, deadline,
                                                    samples, errors), daemon=True)
               for _ in range(concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return {"concurrency": concurrency, "errors": len(errors),
            **summarise(samples, start + warm_up, deadline)}


def load_updates(build: Path) -> list[tuple[str, str]]:
    """(product id, its current tenant_id) from the build's `tenants.jsonl`."""
    out = []
    for line in (build / "tenants.jsonl").read_text().splitlines():
        if line.strip():
            rec = json.loads(line)
            out.append((rec["update"].rsplit("::", 1)[1], rec["fields"]["tenant_id"]["assign"]))
    return out


def _sender(endpoint: str, updates: list[tuple[str, str]], offset: int, rate: float,
            stop: threading.Event, stats: dict) -> None:
    app = Vespa(endpoint)
    i = offset
    sent = errors = 0
    latencies: list[float] = []
    t0 = time.perf_counter()
    while not stop.is_set():
        due = t0 + sent / rate
        now = time.perf_counter()
        if due > now:
            time.sleep(min(due - now, 0.05))
            continue
        pid, tenant = updates[i]
        i = (i + 1) % len(updates)
        started = time.perf_counter()
        try:
            app.update_document("product", pid, {"tenant_id": {"assign": tenant}},
                                namespace=LOCALE)
            latencies.append((time.perf_counter() - started) * 1000)
        except RuntimeError:
            errors += 1
        sent += 1
    stats["sent"] = stats.get("sent", 0) + sent
    stats["errors"] = stats.get("errors", 0) + errors
    stats.setdefault("latencies", []).extend(latencies)


def update_stream(endpoint: str, updates: list[tuple[str, str]], rate: float,
                  threads: int, conn) -> None:
    """The write process: `threads` senders sharing `rate`, until told to stop;
    reports what it sent back over `conn`."""
    stop = threading.Event()
    stats: dict = {}
    step = len(updates) // threads
    senders = [threading.Thread(target=_sender, args=(endpoint, updates, n * step,
                                                      rate / threads, stop, stats), daemon=True)
               for n in range(threads)]
    started = time.perf_counter()
    for t in senders:
        t.start()
    conn.send("started")
    conn.recv()   # "stop"
    stop.set()
    for t in senders:
        t.join()
    elapsed = time.perf_counter() - started
    conn.send({"sent": stats.get("sent", 0), "errors": stats.get("errors", 0),
               "seconds": elapsed,
               "achieved_per_second": stats.get("sent", 0) / elapsed if elapsed else 0.0,
               "latency_ms": metrics.percentiles(stats.get("latencies", []))})


def block_fanout(report: dict) -> str:
    rows = ["| loops at once | update stream | p50 | p95 | p99 | requests / s |",
            "|---|---|---|---|---|---|"]
    achieved = []
    for cell in report["cells"]:
        lat = cell["latency_ms"]
        stream = cell.get("update_stream")
        if stream:
            achieved.append(stream["achieved_per_second"])
        rows.append(f"| {cell['concurrency']} | {'yes' if stream else 'no'} | "
                    f"{metrics.fmt_latency(lat.get('p50'))} | {metrics.fmt_latency(lat.get('p95'))} | "
                    f"{metrics.fmt_latency(lat.get('p99'))} | {cell['rps']:,.1f} |")
    ach = (", ".join(f"{a:,.0f}" for a in achieved) + " updates/s in the three cells"
           if achieved else "no stream cell")
    caption = CAPTION.format(requests=report["requests_replayed"], log=report["source_log"],
                             profile=report["profile"], window=report["window_s"],
                             warm=report["warm_up_s"], rate=report["update_rate_target"],
                             achieved=ach, machine=MACHINE)
    return "\n".join(rows) + "\n\n" + caption + "\n"


BLOCKS = {"fanout": block_fanout}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trajectories", type=Path, help="the rules planner's log to replay")
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--split", required=True, choices=builds.SPLITS,
                    help="which split's question file the log was run on; no default")
    ap.add_argument("--questions", type=Path, default=None)
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--concurrency", type=int, nargs="+", default=list(CONCURRENCY))
    ap.add_argument("--warm-up", type=float, default=WARM_UP_S)
    ap.add_argument("--window", type=float, default=WINDOW_S)
    ap.add_argument("--update-rate", type=float, default=UPDATE_RATE,
                    help="updates per second the stream aims at")
    ap.add_argument("--stream-threads", type=int, default=STREAM_THREADS)
    ap.add_argument("--no-stream", action="store_true", help="the quiet cells only")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--block", choices=sorted(BLOCKS), default="fanout")
    args = ap.parse_args(argv)

    build = args.build or builds.latest()
    questions = eval_trajectory.load_questions(build, args.split, args.questions)
    lines = eval_trajectory.load_lines(args.trajectories)
    requests_ = replay_requests(lines, questions)
    if not requests_:
        raise SystemExit("no search request in the log")
    app = Vespa(args.endpoint)
    if not app.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1
    updates = [] if args.no_stream else load_updates(build)

    cells: list[dict] = []
    for stream in ((False,) if args.no_stream else (False, True)):
        for n in args.concurrency:
            label = f"{n} loop(s), {'with' if stream else 'no'} update stream"
            print(f"  {label}: {args.warm_up:.0f} s warm-up + {args.window:.0f} s window",
                  file=sys.stderr, flush=True)
            proc = conn = None
            if stream:
                conn, child = multiprocessing.Pipe()
                proc = multiprocessing.Process(target=update_stream,
                                               args=(args.endpoint, updates, args.update_rate,
                                                     args.stream_threads, child), daemon=True)
                proc.start()
                conn.recv()   # the senders are running
            cell = run_cell(args.endpoint, requests_, n, args.warm_up, args.window)
            if stream:
                conn.send("stop")
                cell["update_stream"] = conn.recv()
                proc.join(timeout=60)
            cells.append(cell)
            lat = cell["latency_ms"]
            print(f"    p50 {lat.get('p50', 0):.1f} ms, p95 {lat.get('p95', 0):.1f} ms, "
                  f"p99 {lat.get('p99', 0):.1f} ms, {cell['rps']:.1f} requests/s"
                  + (f"; stream {cell['update_stream']['achieved_per_second']:.0f} updates/s"
                     if stream else ""), file=sys.stderr, flush=True)

    report = {"build": builds.meta(build)["build_id"], "split": args.split, **deployed.stamp(),
              "source_log": str(args.trajectories), "requests_replayed": len(requests_),
              "profile": PROFILE, "warm_up_s": args.warm_up, "window_s": args.window,
              "passes": 1, "update_rate_target": args.update_rate,
              "stream_threads": args.stream_threads,
              "note": "The model is not involved; retrieval requests only. " + MACHINE,
              "cells": cells, "host": hostinfo.collect()}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    print(BLOCKS[args.block](report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
