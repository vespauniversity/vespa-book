"""In-engine inference versus an external model service. Cost, ours - both
paths score the **same** M1 model (`ltr_second`, no `cross_logit`, "like for
like"), so no quality number comes out of
this file, only wall time and payload size.

Two legs, per query, per candidate count `N`:

    **fetch**        one Vespa request, `ranking=features_second` (a
                     logging profile with the 51 second-phase columns and no
                     `cross_logit`, so shipping M1's own inputs never also
                     pays the cross-encoder's cost - see `features_second.
                     profile`'s own comment for the bias this replaced.
                     `hits=N`, ordinary retrieval (not `recall`-restricted -
                     these are "the top N candidates", the same shape a real
                     second phase would see, not a judged subset). Its
                     match-features are asserted, once per run, to equal
                     M1's own `feature_name()` set exactly (`assert_fetch_
                     profile_shape`) - a profile/model mismatch is a bug in
                     this tool's setup, not a number to silently compute
                     around.
    **ship + score**  those N x 51 rows, JSON-serialised, POSTed to a mock
                     HTTP service on this same host (not the container) that
                     loads `--model` once and returns N scores.

Against **the in-engine counterpart**: the identical retrieval, `ranking=
ltr_second`, `ranking.rerankCount=N` - one round trip that both finds and
scores the candidates, instead of two.

Warm pass discarded, `--passes` measured passes, p50/p95 = the median of each pass's
own value, the same convention `evaluate.py` uses and for the same reason: a
pass that ran while something else on the machine was busy should not smear
into every other pass's percentile.

    .venv/bin/python chapters/ch07/benchmark_inference.py \\
        --split validation --model chapters/ch07/models_native/ltr_second.lgb \\
        --candidates 10,25,100 --out chapters/ch07/expected/benchmark-inference.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))

import builds                        # noqa: E402
import deployed                      # noqa: E402
import hostinfo                      # noqa: E402
import metrics                       # noqa: E402
from evaluate import build_request, add_reranker_inputs  # noqa: E402
from query import Vespa              # noqa: E402
import export_onnx                   # noqa: E402

FETCH_PROFILE = "features_second"
ENGINE_PROFILE = "ltr_second"
RERANKER_INPUTS = {"qt": "colbert", "qt_cross": "tokenizer"}

# The reference machine, said beside every cost number in this report.
CONDITION_SENTENCE = ("Apple M4 Pro, a 4 CPU / 10 GB container VM (Rancher "
                     "Desktop). The mock model service runs on the host, "
                     "not inside the container VM.")


class _ScoreHandler(BaseHTTPRequestHandler):
    """POST a JSON list of N feature rows, get back a JSON list of N scores.

    `booster` is bound per-server (`start_mock_service`) rather than global,
    so nothing here needs a lock: `Booster.predict` only reads.
    """
    booster = None  # bound in start_mock_service

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        rows = json.loads(body)
        X = np.asarray(rows, dtype=np.float32)
        scores = self.__class__.booster.predict(X).tolist()
        payload = json.dumps(scores).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args) -> None:  # noqa: A002 - stdlib signature
        pass  # the tool's own progress lines cover this; keep stderr clean


def start_mock_service(booster, port: int) -> tuple[ThreadingHTTPServer, threading.Thread]:
    handler = type("BoundScoreHandler", (_ScoreHandler,), {"booster": booster})
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread


def parse_candidates(arg: str) -> list[int]:
    try:
        values = [int(x) for x in arg.split(",")]
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--candidates wants a comma-separated list of integers, got {arg!r}")
    if not values:
        raise argparse.ArgumentTypeError("--candidates must name at least one N")
    return values


def assert_fetch_profile_shape(app: Vespa, feature_names: list[str]) -> None:
    """One cheap query against `FETCH_PROFILE`, asserting its match-features
    are exactly M1's own `feature_name()` set (`features_second` never
    computes `cross_logit`, so there is no per-candidate cross-encoder cost
    to bound, only a profile/model mismatch to catch). Runs once
    per `main()`, before any timed pass, so a renamed column or a profile
    that drifts from the model it is meant to feed is a clear `SystemExit`
    here, not a silent `0.0` fill-in inside a timed loop
    (`one_query_one_n`'s own `.get(f, 0.0)`, kept only as a defence against a
    single stray hit, not against a systematic mismatch this check already
    rules out)."""
    request = build_request("hybrid", "running shoes", 1)
    add_reranker_inputs(request, "running shoes", RERANKER_INPUTS)
    r = app.query(ranking=FETCH_PROFILE, hits=1, **request)
    if not r.hits:
        raise SystemExit(
            f"{FETCH_PROFILE}: shape check query returned no hits - cannot "
            f"verify the fetch leg's match-features before timing it")
    got = set(r.hits[0].features.keys())
    want = set(feature_names)
    if got != want:
        raise SystemExit(
            f"{FETCH_PROFILE}: match-features {sorted(got)} do not equal "
            f"{ENGINE_PROFILE}'s own feature_name() {sorted(want)} - "
            f"missing {sorted(want - got)}, extra {sorted(got - want)}")


def one_query_one_n(app: Vespa, text: str, n: int, feature_names: list[str],
                    port: int) -> dict | None:
    """One query at one candidate count: fetch, ship+score, in-engine. `None`
    if the query matched nothing (so there is no leg to time).

    The fetch leg's shape (that it returns exactly M1's 51 columns, not more
    and not fewer) is checked once, at the start of `main()`
    (`assert_fetch_profile_shape`), rather than on every request here - this
    loop runs once per query per pass and must stay cheap.
    """
    request = build_request("hybrid", text, n)
    add_reranker_inputs(request, text, RERANKER_INPUTS)

    t0 = time.perf_counter()
    r = app.query(ranking=FETCH_PROFILE, hits=n, **request)
    fetch_ms = (time.perf_counter() - t0) * 1000
    if not r.hits:
        return None
    rows = [[hit.features.get(f, 0.0) for f in feature_names] for hit in r.hits]
    payload = json.dumps(rows).encode()

    t1 = time.perf_counter()
    resp = requests.post(f"http://127.0.0.1:{port}/", data=payload, timeout=30)
    resp.raise_for_status()
    resp.json()
    ship_score_ms = (time.perf_counter() - t1) * 1000

    t2 = time.perf_counter()
    app.query(ranking=ENGINE_PROFILE, hits=n, **request,
             **{"ranking.rerankCount": str(n)})
    engine_ms = (time.perf_counter() - t2) * 1000

    return {"fetch_ms": fetch_ms, "ship_score_ms": ship_score_ms,
           "total_external_ms": fetch_ms + ship_score_ms, "engine_ms": engine_ms,
           "bytes": len(payload), "candidates_returned": len(r.hits)}


def run_for_n(app: Vespa, queries: dict[str, str], n: int,
             feature_names: list[str], port: int, passes: int,
             out=sys.stderr) -> dict:
    ids = sorted(queries)
    print(f"  N={n}: warming through {len(ids)} queries once, discarded",
         file=out, flush=True)
    for qid in ids:
        one_query_one_n(app, queries[qid], n, feature_names, port)

    per_pass: dict[str, list[dict[str, float]]] = {
        "fetch_ms": [], "ship_score_ms": [], "total_external_ms": [],
        "engine_ms": [], "bytes": []}
    for p in range(1, passes + 1):
        print(f"  N={n}: measuring pass {p}/{passes}", file=out, flush=True)
        samples: dict[str, list[float]] = {k: [] for k in per_pass}
        skipped = 0
        for qid in ids:
            result = one_query_one_n(app, queries[qid], n, feature_names, port)
            if result is None:
                skipped += 1
                continue
            for key in samples:
                samples[key].append(result[key])
        if skipped:
            print(f"    {skipped} quer{'y' if skipped == 1 else 'ies'} "
                 f"matched nothing at N={n}, skipped", file=out)
        for key in per_pass:
            per_pass[key].append(metrics.percentiles(samples[key]))

    def median_stat(stat: str, key: str) -> float | None:
        values = [p[stat] for p in per_pass[key] if stat in p]
        return round(statistics.median(values), 3) if values else None

    return {
        "n": n,
        "fetch_ms": {s: median_stat(s, "fetch_ms") for s in ("p50", "p95")},
        "ship_score_ms": {s: median_stat(s, "ship_score_ms") for s in ("p50", "p95")},
        "total_external_ms": {s: median_stat(s, "total_external_ms") for s in ("p50", "p95")},
        "engine_ms": {s: median_stat(s, "engine_ms") for s in ("p50", "p95")},
        "bytes_per_request": {s: median_stat(s, "bytes") for s in ("p50", "p95")},
    }


def benchmark_block(report: dict) -> str:
    """One row per candidate count, every column named with its unit."""
    out = ["| candidates (N) | fetch p50 (ms) | fetch p95 (ms) | "
          "ship+score p50 (ms) | ship+score p95 (ms) | external total p50 (ms) | "
          "in-engine p50 (ms) | in-engine p95 (ms) | bytes/request p50 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for row in report["rows"]:
        f, s, t, e, b = (row["fetch_ms"], row["ship_score_ms"],
                        row["total_external_ms"], row["engine_ms"],
                        row["bytes_per_request"])
        out.append(
            f"| {row['n']} | {metrics.fmt_latency(f['p50'])} | "
            f"{metrics.fmt_latency(f['p95'])} | {metrics.fmt_latency(s['p50'])} | "
            f"{metrics.fmt_latency(s['p95'])} | {metrics.fmt_latency(t['p50'])} | "
            f"{metrics.fmt_latency(e['p50'])} | {metrics.fmt_latency(e['p95'])} | "
            f"{b['p50']:.0f} |")
    return "\n".join(out) + "\n\n" + CONDITION_SENTENCE + "\n"


BLOCKS = {"benchmark": benchmark_block}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=("validation",), required=True,
                    help="no default (this tool only ever runs on validation "
                         "- a cost measurement, not a decision on test)")
    ap.add_argument("--model", type=Path, required=True,
                    help="the native LightGBM file the mock service loads "
                         "(train_ltr.py --native-out for ltr_second)")
    ap.add_argument("--candidates", type=parse_candidates, required=True,
                    metavar="N,N,...", help="comma-separated candidate counts, "
                                            "no default, e.g. 10,25,100")
    ap.add_argument("--passes", type=int, default=3,
                    help="warm once (discarded), then this many measured "
                         "passes; p50/p95 are the median over every "
                         "pass's own")
    ap.add_argument("--port", type=int, default=8099,
                    help="localhost port for the mock model service")
    ap.add_argument("--limit", type=int, default=None,
                    help="how many queries; default is every query in the "
                         "split (a self-check uses this, a real report does "
                         "not)")
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--block", choices=sorted(BLOCKS), default="benchmark")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.passes < 1:
        raise SystemExit(f"--passes must be at least 1, got {args.passes}")

    build = args.build or builds.latest()
    build_id = builds.meta(build)["build_id"]

    bst = export_onnx.load_booster(args.model)
    feature_names = bst.feature_name()

    app = Vespa(args.endpoint, timeout=args.timeout)
    if not app.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1

    assert_fetch_profile_shape(app, feature_names)
    print(f"  {FETCH_PROFILE}: match-features verified against "
         f"{len(feature_names)} columns of {args.model.name}", file=sys.stderr)

    queries = builds.load_queries(build, args.split)
    ids = sorted(queries)
    if args.limit:
        ids = ids[:args.limit]
        queries = {q: queries[q] for q in ids}
    print(f"{builds.describe(build)}\n{len(ids)} {args.split} queries, "
         f"{len(feature_names)} features, candidates {args.candidates}, "
         f"{args.passes} passes", file=sys.stderr)

    httpd, thread = start_mock_service(bst, args.port)
    try:
        rows = []
        for n in args.candidates:
            rows.append(run_for_n(app, queries, n, feature_names, args.port,
                                  args.passes))
    finally:
        httpd.shutdown()
        httpd.server_close()

    report = {
        "build": build_id,
        "split": args.split,
        "model_file": str(args.model),
        "fetch_profile": FETCH_PROFILE,
        "engine_profile": ENGINE_PROFILE,
        "candidates": args.candidates,
        "queries": len(ids),
        "limit": args.limit,
        "rows": rows,
        "latency_conditions": {
            "warm": True,
            "passes": args.passes,
            "mock_service_host": "the host machine, not the container VM",
            "note": CONDITION_SENTENCE,
        },
        **deployed.stamp(),
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
