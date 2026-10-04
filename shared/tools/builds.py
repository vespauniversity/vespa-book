"""Read what a corpus build produced.

Chapters need the same three things out of a build — its queries, its
judgements, and what it says about itself — and getting the split wrong is a
mistake with no symptom, so the loaders take the split as an argument and there
is no default.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

SPLITS = ("train", "validation", "test")
ROOT = Path(__file__).resolve().parents[2]


def latest(builds_dir: Path | None = None) -> Path:
    """The most recent usable build.

    Every command would otherwise carry a twenty-four character build id that
    the reader has to look up and retype. Builds made with `--shards` live in
    `builds/partial/` and are not candidates, because their ground truth is
    truncated.
    """
    root = builds_dir or (ROOT / "builds")
    candidates = [p for p in root.glob("*") if (p / "products.jsonl").exists()]
    if not candidates:
        raise SystemExit(
            f"no corpus build in {root}. Make one with:\n"
            "  python shared/tools/corpus.py build --preset small")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_queries(build: Path, split: str) -> dict[str, str]:
    _check(split)
    with (build / f"queries_{split}.csv").open() as fh:
        return {row["query_id"]: row["query_text"] for row in csv.DictReader(fh)}


def load_judgements(build: Path, split: str) -> dict[str, dict[str, float]]:
    """query id -> {document id: gain}, using the gain the build was made with."""
    _check(split)
    out: dict[str, dict[str, float]] = {}
    with (build / f"judgements_{split}.csv").open() as fh:
        for row in csv.DictReader(fh):
            out.setdefault(row["query_id"], {})[row["document_id"]] = float(row["gain"])
    return out


def meta(build: Path) -> dict:
    return json.loads((build / "build.json").read_text())


def describe(build: Path) -> str:
    m = meta(build)
    return (f"{m['build_id']} — {m['counts']['corpus_documents']:,} documents, "
            f"gains `{m['gain_mapping']}`")


def _check(split: str) -> None:
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}, not {split!r}")
