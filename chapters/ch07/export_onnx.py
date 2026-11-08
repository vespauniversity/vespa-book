"""Export a trained LightGBM model to ONNX and verify the export agrees
with the model it came from - the export half of the parity test (the
other half, engine vs offline, is `test_model_parity.py`).

**Reads the native LightGBM file, not the served JSON**
(`train_ltr.py`'s docstring): `train_ltr.py --native-out` writes it, next to
the `dump_model()` JSON `train_ltr.py --model-out` writes for the deployed
profile. Passing the JSON here fails fast with the reload error this file
found instead of a confusing one from inside `onnxmltools`.

    .venv/bin/python chapters/ch07/export_onnx.py \\
        --model chapters/ch07/models_native/ltr_second.lgb \\
        --out chapters/ch07/app/models/onnx/ltr_second.onnx \\
        --out-report chapters/ch07/expected/export-second.json

`--profile-snippet` is a second, independent action (no `--out` / `--out-report`
needed): it prints the Vespa function body that builds the `onnx-model`'s
`tensor<float>(d0[1],d1[N])` input from this model's own feature names, in
this model's own order - generated from the trained model rather than typed
by hand, so the profile's input can never silently drift from what the model
was trained on: the shape check, the model's declared inputs against the
profile's, settled by construction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import onnx
import onnxmltools
from onnxmltools.convert.common.data_types import FloatTensorType
import onnxruntime as ort

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))

import builds                        # noqa: E402
import deployed                      # noqa: E402
import hostinfo                      # noqa: E402
import ltr_data                      # noqa: E402

DEFAULT_TOLERANCE = 1e-4
INPUT_NAME = "input"


def load_booster(path: Path) -> lgb.Booster:
    try:
        return lgb.Booster(model_file=str(path))
    except lgb.basic.LightGBMError as exc:
        raise SystemExit(
            f"{path}: LightGBM could not load this as a native model "
            f"({exc}). If this is a train_ltr.py --model-out JSON "
            f"(dump_model() output), that format cannot be reloaded - "
            f"train_ltr.py's docstring names the error verified for this "
            f"project. Pass the --native-out file for the same shape "
            f"instead.") from exc


def vespa_input_snippet(feature_names: list[str],
                        function_name: str = "ltr_input") -> str:
    """The Vespa function body an `onnx-model`'s `input` binds to: a
    `tensor<float>(d0[1],d1[N])` generated cell by cell, whose N cells are
    this model's own feature names, in this model's own order - each one a
    rank-feature or function reference already valid in any profile that
    `inherits features`, the same names
    `train_ltr.py` logged and trained on.

    **A `d1`-indexed `if` chain, not a tensor literal** (`vespa deploy`
    rejected both `tensor<float>(...):
    [[a, b, c]]`, the array short form - constants only, a parse error at
    the first non-numeral token - and `tensor<float>(...):{ {d0:0,d1:0}:a,
    ... }`, the addressed-cell form - a parse error at the address's own
    opening `{`). Both of those are tensor *literals*, and a literal's cells
    can only be constants in this grammar; a cell whose value is a
    rank-feature reference needs the tensor *generator* form instead -
    `tensor<float>(d0[1],d1[N])(<expr over d0, d1>)`, evaluated once per
    cell - with the one free variable this model's input actually varies
    over, `d1`, walked down to a single feature by a chain of `if(d1==i,
    feature_i, ...)`. `d0` is always 0 (one row at a time) and is not
    referenced in the body.
    """
    body = feature_names[-1]
    for i in range(len(feature_names) - 2, -1, -1):
        body = f"if (d1 == {i}, {feature_names[i]}, {body})"
    return (
        f"    function {function_name}() {{\n"
        f"        expression: tensor<float>(d0[1],d1[{len(feature_names)}])({body})\n"
        f"    }}\n"
    )


def _sha256(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", type=Path, required=True,
                    help="the native LightGBM file (train_ltr.py --native-out)")
    ap.add_argument("--out", type=Path, default=None,
                    help="the .onnx file; required unless --profile-snippet")
    ap.add_argument("--out-report", type=Path, default=None,
                    help="the committed parity report; required unless "
                         "--profile-snippet")
    ap.add_argument("--profile-snippet", action="store_true",
                    help="print the Vespa function body for this model's "
                         "onnx-model input and exit; does not convert")
    ap.add_argument("--function-name", default="ltr_input")
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--validation-csv", type=Path, default=None,
                    help="default: <build>/features/features-validation.csv")
    ap.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE,
                    help="max abs difference a (query, product) pair may "
                         "carry between the LightGBM and ONNX scores before "
                         "it is counted outside tolerance")
    args = ap.parse_args()

    bst = load_booster(args.model)
    feature_names = bst.feature_name()

    if args.profile_snippet:
        print(vespa_input_snippet(feature_names, args.function_name))
        return 0

    if args.out is None or args.out_report is None:
        ap.error("--out and --out-report are required unless --profile-snippet")

    build = args.build or builds.latest()
    build_id = builds.meta(build)["build_id"]
    validation_csv = args.validation_csv or (build / "features" / "features-validation.csv")
    validation = ltr_data.load_split(validation_csv, feature_names)
    print(f"{build_id}: {validation.rows:,} validation rows, "
         f"{len(feature_names)} features", file=sys.stderr)

    initial_types = [(INPUT_NAME, FloatTensorType([None, len(feature_names)]))]
    onnx_model = onnxmltools.convert_lightgbm(bst, initial_types=initial_types)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    onnx.save_model(onnx_model, str(args.out))
    onnx_sha256, onnx_bytes = _sha256(args.out)
    print(f"wrote {args.out}: {onnx_bytes:,} bytes, sha256 {onnx_sha256}",
         file=sys.stderr)

    lgb_scores = bst.predict(validation.X)
    session = ort.InferenceSession(str(args.out))
    onnx_input_name = session.get_inputs()[0].name
    onnx_scores = session.run(None, {onnx_input_name: validation.X})[0].reshape(-1)

    diffs = np.abs(lgb_scores - onnx_scores)
    max_abs_diff = float(diffs.max())
    mean_abs_diff = float(diffs.mean())
    beyond_tolerance = int((diffs > args.tolerance).sum())
    print(f"parity: max abs diff {max_abs_diff:.6g}, mean abs diff "
         f"{mean_abs_diff:.6g}, {beyond_tolerance}/{validation.rows} rows "
         f"beyond tolerance {args.tolerance:g}", file=sys.stderr)

    report = {
        "build": build_id,
        "model_file": str(args.model),
        "onnx_file": {"path": str(args.out), "sha256": onnx_sha256,
                     "bytes": onnx_bytes},
        "feature_names": feature_names,
        "rows_compared": validation.rows,
        "tolerance": args.tolerance,
        "max_abs_diff": max_abs_diff,
        "mean_abs_diff": mean_abs_diff,
        "rows_beyond_tolerance": beyond_tolerance,
        **deployed.stamp(),
        "host": hostinfo.collect(),
    }
    args.out_report.parent.mkdir(parents=True, exist_ok=True)
    args.out_report.write_text(json.dumps(report, indent=2))
    print(f"wrote {args.out_report}", file=sys.stderr)
    print(f"{args.model.name} -> {args.out.name}: max_abs_diff={max_abs_diff:.6g} "
         f"({beyond_tolerance}/{validation.rows} beyond {args.tolerance:g})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
