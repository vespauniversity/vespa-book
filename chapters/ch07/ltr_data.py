"""Shared machinery for this chapter's own tools: reading ch06's feature log
CSV, and the two feature sets the chapter's placement rule draws between.

Chapter-local (only this chapter's tools read
this CSV shape, so it lives beside them rather than in `shared/tools/`), used
by `train_ltr.py`, `export_onnx.py`, `test_model_parity.py` and
`tests/test_ch07_tools.py`.

The CSV is ch06's `features_log.py` output (`chapters/ch07/expected/
features-train.json` `columns`): `query_id, product_id, label, retrieved`,
then every rank feature the `features` profile logs, `cross_logit` last.
Rows for one query are contiguous (verified against this build's CSVs -
ch06's `features_log.py` writes one query's
rows as a block, never interleaved), which is what lets group sizes be read
off file order instead of a sort.
"""
from __future__ import annotations

import csv
import itertools
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))
import gains  # noqa: E402

ID_COLUMNS = ("query_id", "product_id", "label", "retrieved")

# The feature named last in `features.profile`'s `match-features` - the
# one signal the placement rule gates behind the global
# phase, because it exists only where the cross-encoder ran.
CROSS_LOGIT = "cross_logit"

MODELS = ("second", "global")

# The shape grid: num_leaves x
# num_boost_round, sixteen combinations.
GRID_LEAVES = (3, 7, 15, 31)
GRID_ROUNDS = (100, 200, 300, 800)


def feature_columns(columns: list[str], model: str) -> list[str]:
    """Every logged column `model` trains on, in the CSV's own order.

    `second` is every feature column except `cross_logit`: what a second
    phase can compute for every candidate at depth (the placement
    rule). `global` is the same set plus `cross_logit`: the extra signal only
    the global phase can afford, because the cross-encoder had to run to
    produce it. `query_id`, `product_id`, `label` and `retrieved` are never
    features - `retrieved` is this CSV's own union-vs-direct bookkeeping
    (ch06 `features_log.py`), not a signal about the product.
    """
    if model not in MODELS:
        raise ValueError(f"model must be one of {MODELS}, not {model!r}")
    feats = [c for c in columns if c not in ID_COLUMNS]
    if model == "second":
        feats = [c for c in feats if c != CROSS_LOGIT]
    return feats


class Split:
    """One CSV's worth of rows, as LightGBM wants them."""

    def __init__(self, X: np.ndarray, y: np.ndarray, groups: list[int],
                query_ids: list[str], product_ids: list[str],
                feature_names: list[str]):
        self.X = X
        self.y = y
        self.groups = groups
        self.query_ids = query_ids
        self.product_ids = product_ids
        self.feature_names = feature_names

    @property
    def rows(self) -> int:
        return len(self.y)

    @property
    def queries(self) -> int:
        return len(self.groups)


def load_split(csv_path: Path, feature_names: list[str]) -> Split:
    """Read `csv_path`, keeping only `feature_names`, in that order.

    Labels come back as `gains.ordinal` (I/C/S/E -> 0/1/2/3), which is the
    scale LightGBM's `label_gain` is indexed by - not the gain itself, which
    `label_gain` supplies once, from `gains.label_gain`, rather than being
    recomputed per row here.

    Group sizes are read off contiguous runs of `query_id` in file order
    (module docstring), the "groups by query_id in file order" contract.
    A `query_id` that reappears in a second, separated run
    is not silently accepted: it would still sum to the right row count but
    split one query's pairs into two LightGBM groups, losing the comparisons
    between them - `SystemExit` names the file and the id instead.
    """
    with csv_path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        missing = [c for c in feature_names if c not in header]
        if missing:
            raise SystemExit(f"{csv_path}: missing columns {missing}")
        rows_x: list[list[float]] = []
        labels: list[int] = []
        query_ids: list[str] = []
        product_ids: list[str] = []
        for row in reader:
            rows_x.append([float(row[c]) for c in feature_names])
            labels.append(gains.ordinal(row["label"]))
            query_ids.append(row["query_id"])
            product_ids.append(row["product_id"])

    groups = [len(list(g)) for _, g in itertools.groupby(query_ids)]
    if len(groups) != len(set(query_ids)):
        raise SystemExit(
            f"{csv_path}: a query_id repeats in a non-contiguous block - "
            f"group sizes would not match `query_id` (found "
            f"{len(groups)} contiguous runs for {len(set(query_ids))} "
            f"distinct query ids); the 'file order' contract "
            f"does not hold for this file")
    if sum(groups) != len(query_ids):
        raise AssertionError("group sizes do not sum to the row count")

    X = np.asarray(rows_x, dtype=np.float32)
    y = np.asarray(labels, dtype=np.int32)
    return Split(X, y, groups, query_ids, product_ids, list(feature_names))
