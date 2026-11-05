"""Shared machinery for this chapter's own tools: the `phased` request (ch05's
hybrid retrieval plus the two reranker inputs) and which query parameter
overrides which phase's rerank count.

Chapter-local, not `shared/tools/`: the profile this builds requests for,
and the two knob names, are this chapter's own - a tool moves to
`shared/tools/` only once two chapters use it, and nothing else in the book
reranks in two phases.

`rerank_sweep.py` and `funnel_budget.py` both need the identical request (the
union request every measurement in this chapter sees, extended with the
ColBERT and cross-encoder inputs) and the identical warm-then-measure
procedure, so it lives here once rather than twice.
"""
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))

from evaluate import add_reranker_inputs, build_request  # noqa: E402
import metrics                      # noqa: E402
from query import Vespa             # noqa: E402

# The rank profile every tool in this chapter measures. A constant, not a
# flag: chapter 6 has one funnel; a second shape (a cheap global-phase blend
# of the normalised `lexical`, `vector` and `max_sim`) was considered and not
# built.
PROFILE = "phased"

# This chapter's two reranker inputs: `qt`, the
# per-token tensor the ColBERT embedder produces for the second phase's
# MaxSim, and `qt_cross`, the tokenised query the cross-encoder's global phase
# reads. `evaluate.py --reranker-input` takes the same `{name: embedder}`
# shape as a repeatable flag; this chapter's tools pin it to these two rather
# than exposing it as a flag, because nothing else in the book reranks in two
# phases (module docstring).
RERANKER_INPUTS = {"qt": "colbert", "qt_cross": "tokenizer"}

# Which query parameter overrides which phase's rerank count. Getting this
# backwards is silent: the query still succeeds, and on `phased` the other
# reranker's count moves while the one the request meant stays at the
# profile's own default - a plausible curve about the wrong reranker.
PHASE_KNOB = {
    "second": "ranking.rerankCount",
    "global": "ranking.globalPhase.rerankCount",
}


def other_phase(phase: str) -> str:
    """The phase this chapter's tools pin to 0 while sweeping `phase`."""
    if phase not in PHASE_KNOB:
        raise ValueError(f"phase must be one of {sorted(PHASE_KNOB)}, not {phase!r}")
    return "global" if phase == "second" else "second"


def build_phased_request(text: str, hits: int, *,
                         query_prefix: str | None = None,
                         extra_params: dict[str, str] | None = None) -> dict:
    """The union request every `phased` measurement in this chapter sends.

    `evaluate.build_request("hybrid", ...)` is ch05's first stage, imported
    rather than re-typed. Extended with `RERANKER_INPUTS`
    through `evaluate.add_reranker_inputs` - both are computed from the raw
    query text, not the retrieval prefix: `QUERY_PREFIX` marks a query for the
    *retrieval* embedder; the two rerankers are pinned
    add-ons with their own tokenisation and take the text as written. The
    escaping (backslash, double quote) that `embed(...)` needs now lives once,
    in `add_reranker_inputs`, rather than copied here.

    `extra_params` is merged in last, so a caller's
    `input.query(w_sim)`, `input.query(w_cross)` or a `--profile` override's
    own extra inputs reach the request the same way `evaluate.py`'s own
    `--param` does - a key with no effect on the run is the bug class ch03's
    `--param` without `input.` was.
    """
    request = build_request("hybrid", text, hits, query_prefix)
    add_reranker_inputs(request, text, RERANKER_INPUTS)
    if extra_params:
        request.update(extra_params)
    return request


def one_pass(app: Vespa, ids: list[str], queries: dict[str, str],
            *, hits: int, second_count: int, global_count: int,
            query_prefix: str | None, out, label: str,
            progress_every: int = 100, profile: str = PROFILE,
            extra_params: dict[str, str] | None = None,
            ) -> tuple[dict[str, list[str]], list[float], list[float]]:
    """One sweep of the query set under `profile` (default `phased`) at fixed
    rerank counts.

    `extra_params` (e.g. `input.query(w_sim)=0.05`, a `weight_sweep.py`
    reading) are merged in after the two rerank-count knobs, so a caller can
    override either without this function needing a parameter per query
    input; `profile` lets `--profile` reach the request the same way, for a
    caller measuring `phased_replace` instead of `phased`.
    """
    results: dict[str, list[str]] = {}
    client_ms: list[float] = []
    vespa_ms: list[float] = []
    params = {PHASE_KNOB["second"]: second_count, PHASE_KNOB["global"]: global_count}
    params.update(extra_params or {})
    for n, qid in enumerate(ids, 1):
        request = build_phased_request(queries[qid], hits, query_prefix=query_prefix)
        started = time.perf_counter()
        r = app.query(ranking=profile, hits=hits, timing=True, **request, **params)
        client_ms.append((time.perf_counter() - started) * 1000)
        if r.vespa_ms is not None:
            vespa_ms.append(r.vespa_ms)
        results[qid] = [h.fields.get("id", "") for h in r.hits]
        if progress_every and n % progress_every == 0:
            print(f"  {label} {n}/{len(ids)} queries", file=out, flush=True)
    return results, client_ms, vespa_ms


def run(app: Vespa, queries: dict[str, str], *, hits: int,
        second_count: int, global_count: int, query_prefix: str | None = None,
        out=None, passes: int = 3, label_prefix: str = "",
        profile: str = PROFILE, extra_params: dict[str, str] | None = None,
        ) -> tuple[dict[str, list[str]], list[list[float]], list[float]]:
    """Warm through the whole query set once (discarded), then measure it
    `passes` times - `evaluate.py`'s `run()` shape, reused here rather than
    imported because every request also carries this chapter's two rerank
    knobs and reranker inputs, which `evaluate.run` has no parameter for.

    `profile` and `extra_params` pass straight
    through to every `one_pass` call, so a caller such as `weight_sweep.py`
    can set `input.query(w_sim)` / `input.query(w_cross)` or measure
    `phased_replace` without a second copy of this warm-then-measure loop.

    Refuses (`SystemExit`) if a later pass disagrees with the first on any
    query's hit list, the same refusal `evaluate.py` makes and for the same
    reason: a rank profile and a corpus do not change between two requests a
    few milliseconds apart, so a disagreeing pass is a moving index, not a
    second measurement.
    """
    out = out or sys.stderr
    if passes < 1:
        raise SystemExit(f"passes must be at least 1, got {passes}")
    ids = sorted(queries)
    common = dict(hits=hits, second_count=second_count, global_count=global_count,
                 query_prefix=query_prefix, out=out, profile=profile,
                 extra_params=extra_params)
    print(f"  {label_prefix}warming through all {len(ids)} queries once "
          f"(second={second_count}, global={global_count}); discarded",
          file=out, flush=True)
    one_pass(app, ids, queries, label=f"{label_prefix}warming", **common)

    first_results: dict[str, list[str]] | None = None
    client_ms_per_pass: list[list[float]] = []
    vespa_ms: list[float] = []
    for p in range(1, passes + 1):
        label = (f"{label_prefix}measuring" if passes == 1
                 else f"{label_prefix}measuring pass {p}/{passes}")
        results, client_ms, pass_vespa_ms = one_pass(app, ids, queries, label=label,
                                                     **common)
        if first_results is None:
            first_results = results
        else:
            for qid in sorted(first_results):
                if results.get(qid) != first_results[qid]:
                    raise SystemExit(
                        f"pass {p}/{passes} returned different hits for query "
                        f"{qid!r} than pass 1 - a moving index is a "
                        f"measurement error, not data")
        client_ms_per_pass.append(client_ms)
        vespa_ms.extend(pass_vespa_ms)
    return first_results, client_ms_per_pass, vespa_ms


def latency_stats(client_ms_per_pass: list[list[float]]) -> dict:
    """p50 / p95 (always) and p99 (only if the 3-pass jitter clears the 30%
    cutoff), each the median of that stat over every measured pass's own
    reading - `evaluate.py`'s convention, not a distribution pooled from every
    request in every pass.

    Jitter is `max(p99 over passes) / min(p99 over passes) - 1`. Below the
    cutoff, the median p99 is reported with its jitter alongside; at or above
    it, `p99` is `None` and `p99_reason` says why - a cell a block renders as
    `—` rather than a number the report cannot back up.
    """
    per_pass = [metrics.percentiles(cm) for cm in client_ms_per_pass]
    out: dict = {}
    for stat in ("p50", "p95"):
        values = [p[stat] for p in per_pass if stat in p]
        if values:
            out[stat] = round(statistics.median(values), 2)
    p99_values = [p["p99"] for p in per_pass if "p99" in p]
    if len(p99_values) < 2 or min(p99_values) <= 0:
        out["p99"] = None
        out["p99_jitter"] = None
        out["p99_reason"] = "fewer than two measured passes with a positive p99"
        return out
    jitter = round(max(p99_values) / min(p99_values) - 1, 3)
    out["p99_jitter"] = jitter
    if jitter <= 0.30:
        out["p99"] = round(statistics.median(p99_values), 2)
        out["p99_reason"] = None
    else:
        out["p99"] = None
        out["p99_reason"] = (f"3-pass jitter {jitter:.0%} exceeds the 30% cutoff")
    return out
