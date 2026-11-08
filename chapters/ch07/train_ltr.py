"""Train a LightGBM lambdarank model over ch06's feature log. Not a
measurement: every number this
tool prints is offline, against the ESCI judgements, a training-side
choice - the chapter's own quality numbers all
come from the engine, later, over this model's served score.

Two models, from the same CSVs, differing only in which columns they read
(`ltr_data.feature_columns`):

    second   every logged feature except `cross_logit` - what a second
             phase can compute for every candidate at depth (the
             placement rule)
    global   the same set plus `cross_logit` - the extra signal only the
             global phase can afford, because the cross-encoder had to run
             to produce it

Shape (`num_leaves` x `num_boost_round`) is chosen on the **validation** CSV
by LightGBM's own `ndcg@10` (`--grid`, 3/7/15/31 x 100/200/300/800), or
fixed explicitly (`--leaves` / `--rounds`) for the fixed-shape rows the
engine serves. Train decides the model; validation decides the
shape; test is untouched here (never tune on test).

    .venv/bin/python chapters/ch07/train_ltr.py --split train --model second \\
        --grid --out chapters/ch07/expected/train-second-offline.json \\
        --model-out chapters/ch07/app/models/ltr_second_offline.json \\
        --native-out chapters/ch07/models_native/ltr_second_offline.lgb

**The model file Vespa reads and the model file `export_onnx.py` reads are
two different files, deliberately.** `--model-out` writes
LightGBM's `dump_model()` JSON - the one format `lightgbm(...)` in a rank
profile understands, with `feature_names` exactly the logged column names
`lightgbm()` maps to rank features by name. Loading that same JSON back into
a `lightgbm.Booster` to convert it to ONNX does not work: verified here,
`lgb.Booster(model_file=<dump_model json>)` raises `LightGBMError("Unknown
model format or submodel type in model file ...")` - `dump_model()`'s JSON is
a *description* of the trees, not LightGBM's own serialisation of them.
`--native-out` (optional; passed wherever a reloadable file is needed, such
as the two shapes `export_onnx.py` converts) saves the same booster with `save_model()`,
LightGBM's own text format, which reloads exactly - `export_onnx.py`'s
`--model` reads this file, not the JSON. Both are the same trees; only the
JSON is served, only the native file is convertible, and both come from the
one `Booster` this process trains, never retrained.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import lightgbm as lgb

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))

import builds                        # noqa: E402
import deployed                      # noqa: E402
import gains                         # noqa: E402
import hostinfo                      # noqa: E402
import ltr_data                      # noqa: E402

LAMBDARANK_TRUNCATION_LEVEL = 10
EVAL_AT = 10


def file_info(path: Path) -> dict:
    """path, sha256 and size of a file a report depends on, so the report
    says which feature log the model was trained from."""
    digest, size = _sha256(path)
    return {"path": str(path), "sha256": digest, "bytes": size}


def _sha256(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def _base_params(seed: int) -> dict:
    return {
        "objective": "lambdarank",
        "lambdarank_truncation_level": LAMBDARANK_TRUNCATION_LEVEL,
        "eval_at": [EVAL_AT],
        "metric": "ndcg",
        "label_gain": gains.label_gain("kdd"),
        "seed": seed,
        "deterministic": True,
        "verbose": -1,
    }


def _train_one(train: ltr_data.Split, validation: ltr_data.Split, *,
               leaves: int, rounds: int, seed: int) -> tuple[lgb.Booster, float]:
    """One LightGBM run; returns the booster and validation's own `ndcg@10`
    at the final round - LightGBM's own metric, not `shared/tools/metrics.py`
    (module docstring: this is the training-side number)."""
    train_set = lgb.Dataset(train.X, label=train.y, group=train.groups,
                            feature_name=train.feature_names)
    val_set = lgb.Dataset(validation.X, label=validation.y,
                          group=validation.groups,
                          feature_name=validation.feature_names,
                          reference=train_set)
    params = {**_base_params(seed), "num_leaves": leaves}
    evals_result: dict = {}
    bst = lgb.train(params, train_set, num_boost_round=rounds,
                    valid_sets=[val_set], valid_names=["validation"],
                    callbacks=[lgb.record_evaluation(evals_result)])
    ndcg10 = evals_result["validation"][f"ndcg@{EVAL_AT}"][-1]
    return bst, ndcg10


def run_grid(train: ltr_data.Split, validation: ltr_data.Split, seed: int,
            out: list[str] | None = None) -> tuple[lgb.Booster, float, int, int, list[dict]]:
    """The shape grid, trained once per cell; picks the cell with the highest
    validation `ndcg@10`, first cell wins a tie (ascending leaves, then
    ascending rounds - a deterministic order, not "whichever finished last").
    """
    rows: list[dict] = []
    best: dict | None = None
    for leaves in ltr_data.GRID_LEAVES:
        for rounds in ltr_data.GRID_ROUNDS:
            print(f"  grid: leaves={leaves} rounds={rounds} ...", file=sys.stderr)
            bst, ndcg10 = _train_one(train, validation, leaves=leaves,
                                     rounds=rounds, seed=seed)
            rows.append({"leaves": leaves, "rounds": rounds,
                        "validation_ndcg10_offline": round(ndcg10, 4)})
            if best is None or ndcg10 > best["ndcg10"]:
                best = {"leaves": leaves, "rounds": rounds, "ndcg10": ndcg10,
                        "booster": bst}
    assert best is not None
    return best["booster"], best["ndcg10"], best["leaves"], best["rounds"], rows


def importance_block(feature_names: list[str], gains_: list[float]) -> str:
    """The book's markdown table: feature, gain, in descending gain order -
    every column the model actually used prints, none invented."""
    pairs = sorted(zip(feature_names, gains_), key=lambda p: p[1], reverse=True)
    lines = ["| feature | gain |", "|---|---|"]
    for name, g in pairs:
        lines.append(f"| `{name}` | {g:.1f} |")
    return "\n".join(lines) + "\n"


def grid_block(rows: list[dict], chosen_leaves: int, chosen_rounds: int) -> str:
    lines = ["| leaves | rounds | validation ndcg@10 (offline) | chosen |",
            "|---|---|---|---|"]
    for row in rows:
        chosen = "*" if (row["leaves"] == chosen_leaves
                         and row["rounds"] == chosen_rounds) else ""
        lines.append(f"| {row['leaves']} | {row['rounds']} | "
                     f"{row['validation_ndcg10_offline']:.4f} | {chosen} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=("train",), default=None,
                    help="no default: the CSV this trains from. "
                         "Always 'train' - judgement-derived signals come "
                         "from the train split only - the flag is explicit "
                         "so a command never silently trains on anything "
                         "else. Required unless --from re-renders a block "
                         "from a report already on disk")
    ap.add_argument("--model", choices=ltr_data.MODELS, default=None,
                    help="required unless --from re-renders a block")
    ap.add_argument("--leaves", type=int, default=None,
                    help="fixed shape; mutually exclusive with --grid")
    ap.add_argument("--rounds", type=int, default=None,
                    help="fixed shape; mutually exclusive with --grid")
    ap.add_argument("--grid", action="store_true",
                    help="run the shape grid (3/7/15/31 leaves x 100/200/300/800 "
                         "rounds) and pick by validation ndcg@10")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None,
                    help="the committed report; required unless --from")
    ap.add_argument("--model-out", type=Path, default=None,
                    help="dump_model() JSON - what the deployed rank "
                         "profile's lightgbm(...) reads; required unless --from")
    ap.add_argument("--native-out", type=Path, default=None,
                    help="LightGBM's own save_model() text format - what "
                         "export_onnx.py and test_model_parity.py read; the "
                         "chapter writes it for ltr_second, "
                         "ltr_second_offline, ltr_global and ltr_global_200 "
                         "and omits it for ltr_second_tiny, ltr_second_mid "
                         "and ltr_second_large")
    ap.add_argument("--block", choices=("importance", "grid"), default=None,
                    help="print one finished block to stdout instead of the "
                         "usual terminal summary; everything else stays on "
                         "stderr")
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    help="print --block's finished block from a training "
                         "report this command already wrote, without "
                         "training again - retraining here would rewrite "
                         "the served model file, which must not change once "
                         "the engine has been measured with it (the --from "
                         "convention of features_log.py / compare.py)")
    args = ap.parse_args()

    if args.from_report is not None:
        if args.block is None:
            ap.error("--block is required with --from (importance or grid)")
        report = json.loads(args.from_report.read_text())
        if args.block == "importance":
            feature_names = [row["feature"] for row in report["feature_importance_gain"]]
            gains_ = [row["gain"] for row in report["feature_importance_gain"]]
            print(importance_block(feature_names, gains_))
        else:
            if report.get("grid") is None:
                ap.error(f"{args.from_report} has no grid (trained with "
                         f"fixed --leaves/--rounds, not --grid)")
            chosen = report["chosen_shape"]
            print(grid_block(report["grid"], chosen["leaves"], chosen["rounds"]))
        return 0

    if args.split is None:
        ap.error("--split is required (always 'train') unless --from is used")
    if args.model is None:
        ap.error("--model is required unless --from is used")
    if args.out is None:
        ap.error("--out is required (the committed report) unless --from is used")
    if args.model_out is None:
        ap.error("--model-out is required unless --from is used")
    if args.grid and (args.leaves is not None or args.rounds is not None):
        ap.error("--grid picks the shape itself; --leaves/--rounds would be ignored")
    if not args.grid and (args.leaves is None or args.rounds is None):
        ap.error("without --grid, both --leaves and --rounds are required")
    if args.block == "grid" and not args.grid:
        ap.error("--block grid has nothing to print without --grid")

    build = args.build or builds.latest()
    build_id = builds.meta(build)["build_id"]
    train_csv = build / "features" / "features-train.csv"
    validation_csv = build / "features" / "features-validation.csv"

    with train_csv.open(newline="") as fh:
        header = next(csv.reader(fh))
    feature_names = ltr_data.feature_columns(header, args.model)
    print(f"{build_id}: model={args.model}, {len(feature_names)} feature "
         f"columns (cross_logit {'included' if args.model == 'global' else 'excluded'})",
         file=sys.stderr)

    train = ltr_data.load_split(train_csv, feature_names)
    validation = ltr_data.load_split(validation_csv, feature_names)
    print(f"train: {train.queries:,} queries, {train.rows:,} rows  "
         f"validation: {validation.queries:,} queries, {validation.rows:,} rows",
         file=sys.stderr)

    grid_rows: list[dict] | None = None
    if args.grid:
        bst, ndcg10, leaves, rounds, grid_rows = run_grid(
            train, validation, args.seed)
    else:
        leaves, rounds = args.leaves, args.rounds
        bst, ndcg10 = _train_one(train, validation, leaves=leaves,
                                 rounds=rounds, seed=args.seed)
    print(f"chosen shape: leaves={leaves} rounds={rounds}  "
         f"validation ndcg@10 (offline) {ndcg10:.4f}", file=sys.stderr)

    args.model_out.parent.mkdir(parents=True, exist_ok=True)
    dumped = bst.dump_model()
    assert dumped.get("feature_names") == feature_names, (
        "dump_model()'s feature_names must equal the logged column names "
        "in order - this is what lightgbm(...) maps to rank features by "
        "name in the deployed profile")
    args.model_out.write_text(json.dumps(dumped))
    model_sha256, model_bytes = _sha256(args.model_out)
    print(f"wrote {args.model_out}: {model_bytes:,} bytes, sha256 {model_sha256}",
         file=sys.stderr)

    native_info = None
    if args.native_out:
        args.native_out.parent.mkdir(parents=True, exist_ok=True)
        bst.save_model(str(args.native_out))
        native_sha256, native_bytes = _sha256(args.native_out)
        native_info = {"path": str(args.native_out), "sha256": native_sha256,
                       "bytes": native_bytes}
        print(f"wrote {args.native_out}: {native_bytes:,} bytes, "
             f"sha256 {native_sha256} (onnxmltools input, not served)",
             file=sys.stderr)

    importances = [float(g) for g in bst.feature_importance(importance_type="gain")]
    importance_rows = sorted(zip(feature_names, importances), key=lambda p: p[1],
                             reverse=True)

    report = {
        "build": build_id,
        "split": args.split,
        "model": args.model,
        "columns": feature_names,
        "seed": args.seed,
        "grid": grid_rows,
        "chosen_shape": {"leaves": leaves, "rounds": rounds},
        "validation_ndcg10": round(ndcg10, 4),
        "offline_judged_only": True,
        "model_file": {"path": str(args.model_out), "sha256": model_sha256,
                       "bytes": model_bytes},
        "features_csv": {"train": file_info(train_csv),
                         "validation": file_info(validation_csv)},
        "native_model_file": native_info,
        "feature_importance_gain": [{"feature": f, "gain": g}
                                    for f, g in importance_rows],
        **deployed.stamp(),
        "host": hostinfo.collect(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(f"wrote {args.out}", file=sys.stderr)

    if args.block == "importance":
        print(importance_block(feature_names, importances))
    elif args.block == "grid":
        print(grid_block(grid_rows, leaves, rounds))
    else:
        print(f"{args.model}: leaves={leaves} rounds={rounds} "
             f"validation_ndcg10={ndcg10:.4f} -> {args.model_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
