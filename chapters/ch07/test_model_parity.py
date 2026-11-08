"""Does the score the engine exposes as a match-feature agree with the same
model's own prediction on the same feature values?

Two different diffs, not one, because two different things can go wrong and
they read differently in the book: the
model can disagree with itself on identical inputs (a scoring bug - the file
served does not compute what the training-side file computes), or the inputs
themselves can differ (`vector` and `max_sim` can move by a few thousandths
between containers, the BM25-based columns by a few hundredths with feeding
history; this chapter's feature log is
written on the container it serves from and nothing has been refed since,
so the index has not moved, but the check is still made rather than
assumed).

    **vs_logged_features**   engine score vs. the model's prediction on the
                             row ch06's `features_log.py` logged for this
                             pair - "given the training-time inputs, does the
                             served file score the same as the same trees
                             loaded offline".
    **vs_engine_features**   engine score vs. the model's prediction on a row
                             built from the logged CSV but with whichever
                             columns the profile exposes as match-features
                             (`lexical`, `vector`, `max_sim` here - every
                             `ltr_*` profile's match-features) replaced
                             by what the
                             engine returned *this* run - "given what the
                             engine actually saw just now, does the model
                             score it the same". Only ever computed over the
                             features the profile exposes (this file's
                             own docstring below) - the other
                             48/49 columns still come from the CSV, so this is
                             a partial check, not a full re-derivation, and
                             the report says so.

One request per query, in rerank mode, `recall`-restricted to that query's
judged ids - the same request shape `chapters/ch06/features_log.py`'s union
arm sends (`evaluate.build_request("hybrid", ...)` plus both reranker
inputs), not the two-arm union+direct fallback that tool uses: a judged id the
union arm cannot select as a candidate is not a parity failure, it is recorded
as missing and why.

**`ranking.rerankCount` (and, for the `ltr_global*` profiles,
`ranking.globalPhase.rerankCount`) are set to at least the number of judged
ids being requested.** A phase's own match-features are only meaningful for
the candidates that phase actually reranked; for `ltr_global*` the deployed
default is 10 (`phased`'s own count), and a query with more than 10 judged
ids would silently carry `ltr_score_global` from candidates the global phase
never touched. This is stated in every report as `rerank_count_params`.

**The offline predictor is native LightGBM (`export_onnx.load_booster` on
`--model`, reused rather than re-implemented, including its clear failure on
a `dump_model()` JSON) unless the
profile under test is one of the `*_onnx` profiles, which are scored in the
engine by `onnx(...)` - for those, `--onnx` is required and `onnxruntime` is
the offline predictor, because comparing an ONNX-scored engine feature
against a LightGBM-native offline prediction would blur "does the served file
agree with itself" with "do the two export formats agree with each other",
which `export_onnx.py`'s own parity report already answers separately.**

    .venv/bin/python chapters/ch07/test_model_parity.py \\
        --split validation --profile ltr_second \\
        --model chapters/ch07/models_native/ltr_second.lgb \\
        --check-shape --out chapters/ch07/expected/parity-validation-ltr_second.json \\
        --block parity > chapters/ch07/expected/parity-validation-ltr_second.block.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))

import builds                        # noqa: E402
import deployed                      # noqa: E402
import hostinfo                      # noqa: E402
import ltr_data                      # noqa: E402
from evaluate import build_request, add_reranker_inputs, recall_clause  # noqa: E402
from query import Vespa              # noqa: E402
import export_onnx                   # noqa: E402

# Both reranker inputs, every request, on every `ltr_*` / `features` /
# `phased` profile. `qt_cross` is sent even where the model under test
# never reads `cross_logit`, because a request that leaves it out on a
# profile that does read it still answers - with a `cross_logit` computed
# against an empty query (README, *What goes wrong, and how you would know*)
# - and one request shape for every profile is the simpler thing to keep
# right.
RERANKER_INPUTS = {"qt": "colbert", "qt_cross": "tokenizer"}

# The three columns every `ltr_*` profile exposes as match-features beyond its
# own model score (`ltr_second.profile`, `ltr_global.profile` - both list
# `lexical vector max_sim` alongside `ltr_score`[`_global`]). `vs_engine_features`
# can only ever be recomputed over the intersection of this set and the
# model's own feature names - never all 51/52, because the profile does not
# expose the rest as match-features (this file's docstring).
ENGINE_EXPOSED_FEATURES = ("lexical", "vector", "max_sim")

DEFAULT_TOLERANCE = 1e-3
WORST_ROWS = 10


def model_type_of(profile: str) -> str:
    """M1 (`second`) or M2 (`global`), from the profile's own name - every
    `ltr_*` profile is named after the model it serves (`ltr_second*` /
    `ltr_global*`)."""
    return "global" if "global" in profile else "second"


def default_feature_of(model_type: str) -> str:
    """`ltr_score` (M1) or `ltr_score_global` (M2) - the match-feature each
    profile exposes for its own model. `--feature relevance` remains
    available: with both rerank counts widened to the judged-id
    count, every returned hit was scored by the global phase, so its
    relevance equals the model's score too."""
    return "ltr_score_global" if model_type == "global" else "ltr_score"


def is_onnx_profile(profile: str) -> bool:
    return profile.endswith("_onnx")


def _sha256(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def repo_relative(path: Path) -> str:
    """A path for the committed report: relative to the repository root when it
    lies under it (`builds/<build>/features/...`), so the report does not carry
    one machine's home directory; any other path as given."""
    try:
        return str(Path(path).relative_to(builds.ROOT))
    except ValueError:
        return str(path)


def check_shape(feature_names: list[str], expected: list[str]) -> dict:
    """The shape check: the model's own feature names, in order, against the
    logged columns this chapter trains that model type on - not against the
    profile file's text, which is the model's own claim about itself either
    way (`lightgbm(...)` and `onnx(...)` both map inputs by this same order)."""
    ok = feature_names == expected
    mismatches = []
    if not ok:
        for i, (a, b) in enumerate(zip(feature_names, expected)):
            if a != b:
                mismatches.append({"index": i, "model": a, "expected": b})
        if len(feature_names) != len(expected):
            mismatches.append({"length_model": len(feature_names),
                               "length_expected": len(expected)})
    return {"pass": ok, "model_features": feature_names,
            "expected_features": expected, "mismatches": mismatches}


def diff_stats(engine_scores: np.ndarray, offline_scores: np.ndarray,
              tolerance: float) -> dict:
    """max abs diff, mean abs diff, count beyond `tolerance` - one pair of
    arrays in, the three numbers every parity row reports out. Pulled out on
    its own so `tests/test_ch07_tools.py` can check it against a
    hand-computed pair of rows rather than only through a live run."""
    diffs = np.abs(np.asarray(engine_scores, dtype=np.float64)
                  - np.asarray(offline_scores, dtype=np.float64))
    if diffs.size == 0:
        return {"max_abs_diff": None, "mean_abs_diff": None,
                "count_beyond_tolerance": 0}
    return {"max_abs_diff": float(diffs.max()), "mean_abs_diff": float(diffs.mean()),
            "count_beyond_tolerance": int((diffs > tolerance).sum())}


def onnx_predict(onnx_path: Path, X: np.ndarray) -> np.ndarray:
    import onnxruntime as ort
    session = ort.InferenceSession(str(onnx_path))
    name = session.get_inputs()[0].name
    return session.run(None, {name: X.astype(np.float32)})[0].reshape(-1)


def resolve_features_csv(build: Path, split: str, override: Path | None) -> Path:
    """The CSV the offline prediction reads: `--features-csv` if given (the
    drift demonstration - point this at another container's logged CSV,
    e.g. `features/old-container-<date>/features-<split>.csv`, to compare
    the current engine against a log it was not trained on), otherwise the
    build's own `features/features-<split>.csv` (unchanged default)."""
    return override or (build / "features" / f"features-{split}.csv")


def build_parity_request(text: str, judged_ids, hits: int) -> dict:
    request = build_request("hybrid", text, hits)
    add_reranker_inputs(request, text, RERANKER_INPUTS)
    request["recall"] = recall_clause(sorted(judged_ids))
    return request


def collect_engine_scores(app: Vespa, queries: dict[str, str],
                          judgements: dict[str, dict[str, float]], *,
                          profile: str, feature: str, model_type: str,
                          progress_every: int = 100, out=sys.stderr,
                          ) -> tuple[dict, list, dict]:
    """One request per query, judged ids only. Returns `(collected,
    missing_engine, rerank_count_params)` - `collected` maps `(query_id,
    product_id)` to `{"engine_score": ..., <exposed feature>: ...}`,
    `missing_engine` lists judged pairs the union arm never returned."""
    collected: dict[tuple[str, str], dict] = {}
    missing_engine: list[dict] = []
    ids = sorted(queries)
    for n, qid in enumerate(ids, 1):
        judged = judgements.get(qid, {})
        if not judged:
            continue
        hits = len(judged)
        # `ltr_global*`'s global phase reranks 10 by default
        # (`phased`'s own count) - a request for more judged ids than that
        # would silently carry a global-phase feature computed on candidates
        # the global phase never reranked, so both counts are widened to at
        # least `hits` here rather than left at the profile's own default.
        params = {"ranking.rerankCount": str(hits)}
        if model_type == "global":
            params["ranking.globalPhase.rerankCount"] = str(hits)
        request = build_parity_request(queries[qid], judged, hits)
        r = app.query(ranking=profile, hits=hits, **request, **params)
        seen = set()
        for hit in r.hits:
            pid = hit.fields.get("id", "")
            if pid not in judged:
                continue
            seen.add(pid)
            feats = hit.features
            # `--feature relevance` reads the hit's relevance instead of a
            # match-feature: with both rerank counts widened to the judged-id
            # count above, every returned hit was scored by the global phase,
            # so its relevance *is* the model's score.
            row = {"engine_score": hit.relevance if feature == "relevance"
                   else feats.get(feature)}
            for name in ENGINE_EXPOSED_FEATURES:
                if name in feats:
                    row[name] = feats[name]
            collected[(qid, pid)] = row
        for pid in judged:
            if pid not in seen:
                missing_engine.append({
                    "query_id": qid, "product_id": pid,
                    "reason": "not returned by the union retrieval within "
                             "the recall set (no lexical/vector match)"})
        if progress_every and n % progress_every == 0:
            print(f"  {n}/{len(ids)} queries", file=out, flush=True)
    rerank_count_params = {
        "ranking.rerankCount": "per-query, equal to that query's judged-id "
                               "count",
        "ranking.globalPhase.rerankCount": (
            "per-query, equal to that query's judged-id count (>= hits, so "
            "every returned hit was scored by the global phase)"
            if model_type == "global" else None),
    }
    return collected, missing_engine, rerank_count_params


def parity_block(report: dict) -> str:
    v = report["vs_logged_features"]
    e = report["vs_engine_features"]
    shape = report.get("shape_check")
    rows = [
        ("rows compared", str(report["rows_compared"])),
        ("rows missing (engine)", str(len(report["missing_engine"]))),
        ("rows missing (csv)", str(len(report["missing_csv"]))),
        ("offline source", report["offline_source"]),
        ("max abs diff vs logged features", f"{v['max_abs_diff']:.6g}"),
        ("mean abs diff vs logged features", f"{v['mean_abs_diff']:.6g}"),
        (f"count beyond tolerance ({report['tolerance']:g})",
         str(v["count_beyond_tolerance"])),
        ("max abs diff vs engine features",
         "n/a" if e is None else f"{e['max_abs_diff']:.6g}"),
        (f"count beyond tolerance, engine features ({report['tolerance']:g})",
         "n/a" if e is None else str(e["count_beyond_tolerance"])),
        ("shape check", "not run" if shape is None
         else ("PASS" if shape["pass"] else "FAIL")),
    ]
    out = ["| measurement | value |", "|---|---|"]
    out += [f"| {k} | {v_} |" for k, v_ in rows]
    return "\n".join(out) + "\n"


BLOCKS = {"parity": parity_block}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=("validation", "test"), required=True,
                    help="no default: which judged pairs to check parity on")
    ap.add_argument("--profile", required=True,
                    help="the deployed rank profile under test, e.g. "
                         "ltr_second, ltr_global, ltr_second_onnx")
    ap.add_argument("--model", type=Path, required=True,
                    help="the native LightGBM file (train_ltr.py --native-out) "
                         "- a dump_model() JSON fails with a clear error "
                         "naming the fix (export_onnx.load_booster)")
    ap.add_argument("--onnx", type=Path, default=None,
                    help="the ONNX export matching --model; required when "
                         "--profile is one of the *_onnx profiles, since "
                         "those are scored in the engine by onnx(...), not "
                         "lightgbm(...)")
    ap.add_argument("--feature", default=None,
                    help="which match-feature carries the model's score; "
                         "default is chosen from --profile's name "
                         "(ltr_score, or ltr_score_global for a *global* "
                         "profile) and recorded in the report either way")
    ap.add_argument("--check-shape", action="store_true",
                    help="assert the model's own feature names equal the "
                         "logged columns for this model type, in order; "
                         "prints PASS/FAIL and exits non-zero on FAIL "
                         "before any engine call is made")
    ap.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE,
                    help="max abs difference before a pair counts as beyond "
                         "tolerance")
    ap.add_argument("--limit", type=int, default=None,
                    help="how many queries; default is every query with a "
                         "judgement in the split (a self-check uses this, "
                         "a real report does not)")
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--features-csv", type=Path, default=None,
                    help="override the CSV the offline prediction reads; "
                         "default is the build's own "
                         "features/features-<split>.csv. For a drift "
                         "demonstration: point this at another container's "
                         "logged CSV (e.g. features/old-container-<date>/"
                         "features-<split>.csv) to compare the current "
                         "engine against a log it was not trained on. The "
                         "report records the path and this CSV's sha256")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--block", choices=sorted(BLOCKS), default="parity")
    ap.add_argument("--out", type=Path, default=None,
                    help="the committed report")
    args = ap.parse_args()

    model_type = model_type_of(args.profile)
    feature = args.feature or default_feature_of(model_type)
    onnx_profile = is_onnx_profile(args.profile)
    if onnx_profile and args.onnx is None:
        ap.error(f"--profile {args.profile!r} is scored by onnx(...) in the "
                 f"engine; pass --onnx <path> so the offline prediction "
                 f"comes from the same file format, not lightgbm-native")

    build = args.build or builds.latest()
    build_id = builds.meta(build)["build_id"]
    csv_path = resolve_features_csv(build, args.split, args.features_csv)
    with csv_path.open() as fh:
        import csv as _csv
        header = next(_csv.reader(fh))
    expected_features = ltr_data.feature_columns(header, model_type)
    features_csv_sha256, features_csv_bytes = _sha256(csv_path)

    bst = export_onnx.load_booster(args.model)
    model_features = bst.feature_name()
    model_sha256, model_bytes = _sha256(args.model)

    shape_report = None
    if args.check_shape:
        shape_report = check_shape(model_features, expected_features)
        if not shape_report["pass"]:
            print(f"shape check: FAIL - {shape_report['mismatches']}",
                 file=sys.stderr)
            print(json.dumps({"shape_check": shape_report}, indent=2))
            return 1
        print("shape check: PASS", file=sys.stderr)

    onnx_info = None
    if args.onnx is not None:
        onnx_sha256, onnx_bytes = _sha256(args.onnx)
        onnx_info = {"path": repo_relative(args.onnx), "sha256": onnx_sha256,
                    "bytes": onnx_bytes}
    offline_source = "onnx" if onnx_profile else "native"

    app = Vespa(args.endpoint, timeout=args.timeout)
    if not app.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1

    queries = builds.load_queries(build, args.split)
    judgements = builds.load_judgements(build, args.split)
    ids = sorted(queries)
    if args.limit:
        ids = ids[:args.limit]
        queries = {q: queries[q] for q in ids}
    print(f"{builds.describe(build)}\n{len(ids)} {args.split} queries, "
         f"profile {args.profile}, feature {feature}, offline source "
         f"{offline_source}", file=sys.stderr)

    collected, missing_engine, rerank_count_params = collect_engine_scores(
        app, queries, judgements, profile=args.profile, feature=feature,
        model_type=model_type)

    # The logged CSV, once, in the model's own feature order - `ltr_data`
    # already asserts group contiguity and column presence.
    split = ltr_data.load_split(csv_path, expected_features)
    csv_index = {(q, p): i for i, (q, p) in
                enumerate(zip(split.query_ids, split.product_ids))}

    pairs = sorted(collected)
    missing_csv = [{"query_id": q, "product_id": p,
                    "reason": f"no logged feature row in "
                             f"features-{args.split}.csv"}
                  for q, p in pairs if (q, p) not in csv_index]
    compared = [(q, p) for q, p in pairs if (q, p) in csv_index]

    engine_scores = np.array([collected[qp]["engine_score"] for qp in compared],
                             dtype=np.float64)
    logged_X = split.X[[csv_index[qp] for qp in compared]].copy()
    engine_X = logged_X.copy()
    # `vs_engine_features`: only the columns both this model trains on and
    # this profile exposes as a match-feature get the value the engine
    # returned just now; every other column keeps the logged (train-time)
    # value - the partial recomputation the module docstring describes,
    # never a full second feature vector.
    exposed_in_model = [f for f in ENGINE_EXPOSED_FEATURES if f in expected_features]
    for name in exposed_in_model:
        col = expected_features.index(name)
        for row, qp in enumerate(compared):
            v = collected[qp].get(name)
            if v is not None:
                engine_X[row, col] = v

    def predict(X: np.ndarray) -> np.ndarray:
        if offline_source == "onnx":
            return onnx_predict(args.onnx, X)
        return bst.predict(X)

    offline_logged = predict(logged_X) if compared else np.array([])
    offline_engine = predict(engine_X) if compared else np.array([])

    vs_logged = diff_stats(engine_scores, offline_logged, args.tolerance)
    diffs_logged = (np.abs(engine_scores - offline_logged) if compared
                    else np.array([]))

    vs_engine = None
    if exposed_in_model:
        vs_engine = diff_stats(engine_scores, offline_engine, args.tolerance)
        vs_engine["columns_overridden"] = exposed_in_model
        vs_engine["note"] = ("computed only over the columns this profile "
                             "exposes as match-features; the remaining "
                             "columns keep the logged (train-time) value - "
                             "LEDGER Findings, step 3")

    order = np.argsort(-diffs_logged) if compared else []
    worst_rows = []
    for i in order[:WORST_ROWS]:
        qp = compared[i]
        row = {"query_id": qp[0], "product_id": qp[1],
              "engine_score": float(engine_scores[i]),
              "offline_score_vs_logged": float(offline_logged[i]),
              "diff": float(diffs_logged[i])}
        if exposed_in_model:
            best_name, best_diff = None, -1.0
            for name in exposed_in_model:
                col = expected_features.index(name)
                engine_v = collected[qp].get(name)
                if engine_v is None:
                    continue
                d = abs(engine_v - logged_X[i, col])
                if d > best_diff:
                    best_name, best_diff = name, d
            if best_name is not None:
                row["most_differing_exposed_feature"] = {
                    "name": best_name, "engine_value": collected[qp][best_name],
                    "logged_csv_value": float(logged_X[i, expected_features.index(best_name)]),
                    "diff": float(best_diff)}
        worst_rows.append(row)

    report = {
        "build": build_id,
        "split": args.split,
        "profile": args.profile,
        "model_type": model_type,
        "feature": feature,
        "offline_source": offline_source,
        "model_file": {"path": repo_relative(args.model), "sha256": model_sha256,
                       "bytes": model_bytes},
        "onnx_file": onnx_info,
        "features_csv": {"path": repo_relative(csv_path), "sha256": features_csv_sha256,
                         "bytes": features_csv_bytes},
        "tolerance": args.tolerance,
        "limit": args.limit,
        "queries": len(ids),
        "rows_compared": len(compared),
        "missing_engine": missing_engine,
        "missing_csv": missing_csv,
        "vs_logged_features": vs_logged,
        "vs_engine_features": vs_engine,
        "worst_rows": worst_rows,
        "rerank_count_params": rerank_count_params,
        "shape_check": shape_report,
        **deployed.stamp(),
        "host": hostinfo.collect(),
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.out}", file=sys.stderr)

    print(f"\n{len(compared)} pairs compared, {len(missing_engine)} missing "
         f"(engine), {len(missing_csv)} missing (csv)\n"
         f"vs_logged_features: max {vs_logged['max_abs_diff']}, "
         f"mean {vs_logged['mean_abs_diff']}, "
         f"{vs_logged['count_beyond_tolerance']} beyond {args.tolerance:g}",
         file=sys.stderr)

    print(BLOCKS[args.block](report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
