"""Build a deterministic ESCI corpus for the book's examples.

Two stages. The first streams the dataset once and caches what it needs
locally; the second selects queries and products from that cache and writes a
build. Rebuilding with different presets touches the network only if the cache
is missing.

The defaults are what the book measures. Change one and you get a different
corpus and different numbers, which is fine and is the point of the flags - the
book just will not be describing what you have.

  python shared/tools/corpus.py build --preset small
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parent))
import gains as gains_mod  # noqa: E402
import hf  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "shared" / "cache"
BUILDS = ROOT / "builds"

LOCALE = "us"

# ESCI ships two query sets. The larger one is everything; the reduced one is
# what remains after the queries judged easy were removed, and it is what the
# ranking task is scored on. Which one a corpus is built from changes every
# number measured against it, so it is named in the build id rather than being
# a default nobody looks at.
DIFFICULTIES = {
    "hard": "small_version",   # the reduced set: easy queries filtered out
    "all": "large_version",    # everything, easy queries included
}
VERSION = "v4"          # bump when a build's content changes
#   v2: strip control characters that Vespa refuses (see clean_text)
#   v3: the third split is called validation, not dev
#   v4: both ESCI query sets are cached; --difficulty selects one

INDEX_COLUMNS = ["query_id", "query", "product_id", "product_locale",
                 "esci_label", "small_version", "large_version"]
PRODUCT_COLUMNS = ["product_id", "product_locale", "product_title",
                   "product_description", "product_bullet_point",
                   "product_brand", "product_color"]


@dataclass(frozen=True)
class Preset:
    name: str
    queries: int
    distractors: int
    validation_fraction: float = 0.2


PRESETS = {
    # For iterating. Not for anything that gets printed.
    "tiny": Preset("tiny", queries=200, distractors=6_000),
    # The book's numbers come from this one. 3,500 hard US queries, 30% of
    # them test, 30% of the rest validation: about 1,715 / 735 / 1,050. Sized
    # by probes/q01-validation-size (a split that must call a 0.03 difference
    # needs ~700 queries; test, which reports 0.02 differences, ~1,000) and
    # probes/q02-corpus-size (100k products feed in 3 min plain, 8 min with the
    # embedder). Judged products come to about 67k, so 33k distractors make
    # the corpus about 100k.
    "book": Preset("book", queries=3_500, distractors=33_000,
                   validation_fraction=0.3),
    # The previous book preset, kept so its reports stay readable.
    "small": Preset("small", queries=1_000, distractors=80_000),
    # Everything judged, for whoever has the machine for it.
    "full": Preset("full", queries=0, distractors=0),
}


# --------------------------------------------------------------------------
# Stage 1 — stream once, cache locally
# --------------------------------------------------------------------------

def _log(msg: str) -> None:
    print(f"[corpus] {msg}", flush=True)


def build_cache(max_shards: int | None = None) -> tuple[Path, Path]:
    """Stream the dataset and cache the US rows we need.

    Reads twelve of the dataset's fourteen columns. The largest column,
    `product_text`, is a derived concatenation we have no use for, so skipping
    it removes a large share of the transfer.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    suffix = f".partial{max_shards}" if max_shards else ""
    index_path = CACHE / f"index_{LOCALE}{suffix}.parquet"
    products_path = CACHE / f"products_{LOCALE}{suffix}.parquet"
    if index_path.exists() and products_path.exists():
        _log(f"cache present: {index_path.name}, {products_path.name}")
        return index_path, products_path

    session = hf.new_session()
    shards = hf.list_shards(session)
    if max_shards:
        by_split = defaultdict(list)
        for s in shards:
            by_split[s.split].append(s)
        shards = [s for split in sorted(by_split) for s in by_split[split][:max_shards]]

    columns = sorted(set(INDEX_COLUMNS) | set(PRODUCT_COLUMNS))
    idx_rows = {c: [] for c in ["query_id", "query", "product_id", "esci_label",
                                "split", "small_version"]}
    products: dict[str, dict] = {}
    started = time.time()
    seen = 0

    for n, shard in enumerate(shards, 1):
        _log(f"shard {n}/{len(shards)} {shard.path.rsplit('/', 1)[-1]} "
             f"({shard.size / 1e6:.0f} MB)")
        for batch in hf.iter_batches(shard, session, columns, batch_size=65_536):
            d = batch.to_pydict()
            for i in range(batch.num_rows):
                seen += 1
                # Cache both query sets. Deciding here would mean re-streaming
                # 2.5 GB to answer a question about the other one.
                if d["product_locale"][i] != LOCALE or not d["large_version"][i]:
                    continue
                pid = d["product_id"][i]
                idx_rows["query_id"].append(int(d["query_id"][i]))
                idx_rows["query"].append(d["query"][i])
                idx_rows["product_id"].append(pid)
                idx_rows["esci_label"].append(gains_mod.normalise(d["esci_label"][i]))
                idx_rows["split"].append(shard.split)
                idx_rows["small_version"].append(bool(d["small_version"][i]))
                if pid not in products:
                    products[pid] = {
                        "product_id": pid,
                        "title": d["product_title"][i] or "",
                        "description": d["product_description"][i] or "",
                        "bullets": d["product_bullet_point"][i] or "",
                        "brand": d["product_brand"][i] or "",
                        "color": d["product_color"][i] or "",
                    }
        _log(f"  judged rows so far: {len(idx_rows['query_id']):,} "
             f"| products: {len(products):,} | {time.time() - started:.0f}s")

    pq.write_table(pa.table(idx_rows), index_path)
    keys = ["product_id", "title", "description", "bullets", "brand", "color"]
    ordered = [products[p] for p in sorted(products)]
    pq.write_table(pa.table({k: [p[k] for p in ordered] for k in keys}), products_path)
    _log(f"scanned {seen:,} rows -> {len(idx_rows['query_id']):,} US judgements, "
         f"{len(products):,} products in {time.time() - started:.0f}s")
    return index_path, products_path


# --------------------------------------------------------------------------
# Deterministic selection
# --------------------------------------------------------------------------

def _digest(seed: int, key: str) -> int:
    return int.from_bytes(
        hashlib.blake2b(f"{seed}:{key}".encode(), digest_size=8).digest(), "big")


def select_queries(query_ids: list[int], n: int, seed: int) -> list[int]:
    """Order-independent, seed-stable. Take the n smallest hashes."""
    if n <= 0 or n >= len(query_ids):
        return sorted(query_ids)
    ranked = sorted(query_ids, key=lambda q: (_digest(seed, f"q{q}"), q))
    return sorted(ranked[:n])


def select_distractors(pool: list[str], m: int, seed: int) -> list[str]:
    if m <= 0:
        return []
    if m >= len(pool):
        return sorted(pool)
    ranked = sorted(pool, key=lambda p: (_digest(seed, f"d{p}"), p))
    return sorted(ranked[:m])


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

# Code points Vespa will not accept in a string field. Real catalogue text
# contains them: four documents in a hundred thousand carried a 0x05, and the
# feed rejected each with a 400 that is easy to miss if nobody counts failures.
_ILLEGAL = {c for c in range(0x00, 0x20)} - {0x09, 0x0A, 0x0D}
_ILLEGAL |= {0x7F}
_ILLEGAL |= set(range(0xD800, 0xE000))          # surrogates
_ILLEGAL |= {0xFFFE, 0xFFFF}
_STRIP = {c: None for c in _ILLEGAL}


def clean_text(raw: str | None) -> str:
    """Remove code points Vespa refuses, leaving tabs and newlines alone."""
    return (raw or "").translate(_STRIP)


def split_bullets(raw: str) -> list[str]:
    """ESCI ships bullet points as one newline-separated string."""
    return [b.strip() for b in clean_text(raw).splitlines() if b.strip()]


def build(preset: Preset, seed: int, mapping: str, max_shards: int | None,
          difficulty: str = "hard") -> Path:
    index_path, products_path = build_cache(max_shards)
    index = pq.read_table(index_path).to_pydict()
    if "small_version" not in index:
        # A cache built before both query sets were kept holds the reduced set
        # only, so `hard` is what it already is and `all` cannot be served from
        # it. Rebuilding the cache is a quarter of an hour; saying so is better
        # than silently producing a corpus that is not what was asked for.
        if difficulty != "hard":
            raise SystemExit(
                f"this cache holds the reduced query set only, so --difficulty "
                f"{difficulty} cannot be built from it.\nDelete "
                f"{index_path.parent} and build again to stream both sets.")
    elif difficulty == "hard":
        keep = [i for i, v in enumerate(index["small_version"]) if v]
        index = {k: [v[i] for i in keep] for k, v in index.items()}
    n_rows = len(index["query_id"])

    # queries per split, and their text
    queries_by_split: dict[str, set[int]] = defaultdict(set)
    query_text: dict[int, str] = {}
    for i in range(n_rows):
        qid = index["query_id"][i]
        queries_by_split[index["split"][i]].add(qid)
        query_text.setdefault(qid, index["query"][i])

    train_all = sorted(queries_by_split["train"])
    test_all = sorted(queries_by_split["test"])

    # Keep the official split, then carve validation out of train. Test is
    # only ever used to produce a number that goes in the book.
    if preset.queries:
        share = preset.queries / (len(train_all) + len(test_all))
        n_train = max(1, round(len(train_all) * share))
        n_test = max(1, preset.queries - n_train)
    else:
        n_train, n_test = len(train_all), len(test_all)

    train_sel = select_queries(train_all, n_train, seed)
    test_sel = select_queries(test_all, n_test, seed)
    n_val = max(1, round(len(train_sel) * preset.validation_fraction))
    val_sel = select_queries(train_sel, n_val, seed + 1)
    train_sel = sorted(set(train_sel) - set(val_sel))

    selected = {"train": set(train_sel), "validation": set(val_sel),
                "test": set(test_sel)}
    all_selected = set().union(*selected.values())

    # judgements for selected queries, kept whole
    judgements: dict[str, dict[int, dict[str, str]]] = {
        s: defaultdict(dict) for s in selected}
    judged_products: set[str] = set()
    # train-only signals, from every train judgement, not just selected ones
    sig_queries: dict[str, set[int]] = defaultdict(set)
    sig_exact: dict[str, int] = defaultdict(int)
    sig_total: dict[str, int] = defaultdict(int)

    for i in range(n_rows):
        qid, pid = index["query_id"][i], index["product_id"][i]
        label, split = index["esci_label"][i], index["split"][i]
        if split == "train":
            sig_queries[pid].add(qid)
            sig_total[pid] += 1
            if label == "E":
                sig_exact[pid] += 1
        if qid in all_selected:
            target = "validation" if qid in selected["validation"] else (
                "train" if qid in selected["train"] else "test")
            judgements[target][qid][pid] = label
            judged_products.add(pid)

    products = pq.read_table(products_path).to_pydict()
    all_pids = products["product_id"]
    # Distractors come from the products the selected query set actually covers,
    # not from every product in the cache. The cache holds both ESCI query sets
    # so that switching between them costs nothing; letting the wider one widen
    # the distractor pool would change every retrieval number in a build that
    # asked for the narrower one.
    in_scope = set(index["product_id"])
    pool = [p for p in all_pids if p in in_scope and p not in judged_products]
    distractors = select_distractors(pool, preset.distractors, seed)
    corpus_pids = sorted(judged_products | set(distractors))

    partial = "-partial" if max_shards else ""
    build_id = (f"esci-{LOCALE}-{difficulty}-{preset.name}-s{seed}-{mapping}"
                f"-{VERSION}{partial}")
    # Partial builds have truncated ground truth and cannot be measured
    # against. Keeping them out of builds/ means a glob over real builds never
    # picks one up, and a reader never has to know the naming convention to
    # avoid one.
    out = (BUILDS / "partial" / build_id) if max_shards else (BUILDS / build_id)
    out.mkdir(parents=True, exist_ok=True)

    by_pid = {all_pids[i]: i for i in range(len(all_pids))}
    n_no_desc = 0
    with (out / "products.jsonl").open("w") as fh:
        for pid in corpus_pids:
            r = by_pid[pid]
            desc = clean_text(products["description"][r])
            bullets = split_bullets(products["bullets"][r])
            if not desc:
                n_no_desc += 1
            fh.write(json.dumps({
                "put": f"id:product:product::{LOCALE}_{pid}",
                "fields": {
                    "id": pid,
                    "locale": LOCALE,
                    "title": clean_text(products["title"][r]),
                    "description": desc,
                    "bullets": bullets,
                    "brand": clean_text(products["brand"][r]),
                    "color": clean_text(products["color"][r]),
                    "has_description": bool(desc),
                },
            }, ensure_ascii=False) + "\n")

    # Document signals, derived from the TRAIN split only. Deriving them from
    # every judgement would put test labels into the index.
    with (out / "doc_signals.jsonl").open("w") as fh:
        for pid in corpus_pids:
            fh.write(json.dumps({
                "update": f"id:product:product::{LOCALE}_{pid}",
                "fields": {
                    "popularity": {"assign": len(sig_queries.get(pid, ()))},
                    "exact_rate": {"assign": round(
                        sig_exact.get(pid, 0) / sig_total[pid], 6)
                        if sig_total.get(pid) else 0.0},
                    "n_judgements": {"assign": sig_total.get(pid, 0)},
                },
            }) + "\n")

    counts = {}
    # How many judgements each selected query carries, across every split. The
    # generated BUILD.md describes the pool from this rather than from a
    # sentence somebody half-remembered about the dataset.
    per_query_judgements: list[int] = []
    for split in ("train", "validation", "test"):
        qids = sorted(judgements[split])
        with (out / f"queries_{split}.csv").open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["query_id", "query_text"])
            w.writerows([[q, query_text[q]] for q in qids])
        rows = 0
        with (out / f"judgements_{split}.csv").open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["query_id", "document_id", "label", "gain", "ordinal"])
            for q in qids:
                per_query_judgements.append(len(judgements[split][q]))
                for pid in sorted(judgements[split][q]):
                    lab = judgements[split][q][pid]
                    w.writerow([q, pid, lab, gains_mod.gain(lab, mapping),
                                gains_mod.ordinal(lab)])
                    rows += 1
        counts[split] = {"queries": len(qids), "judgements": rows}

    hashed = sorted(p.name for p in out.iterdir()
                    if p.suffix in (".jsonl", ".csv"))
    content_hash = _hash_outputs(out, hashed)
    meta = {
        "build_id": build_id,
        "preset": asdict(preset),
        "difficulty": difficulty,
        "difficulty_column": DIFFICULTIES[difficulty],
        "seed": seed,
        "gain_mapping": mapping,
        "locale": LOCALE,
        "format_version": VERSION,
        "partial": bool(max_shards),
        "source": {"repo": hf.REPO, "revision": hf.REVISION,
                   "canonical": "amazon-science/esci-data"},
        "counts": {
            **counts,
            "corpus_documents": len(corpus_pids),
            "judged_products": len(judged_products),
            "distractors": len(distractors),
            "documents_without_description": n_no_desc,
        },
        "judgements_per_query": judgement_depth(per_query_judgements),
        "content_hash": content_hash,
        # The files that hash covers. Anything written into the build directory
        # afterwards is not part of the build and must not break `verify`.
        "hashed_files": hashed,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "built_on": f"{platform.system()} {platform.machine()} python{platform.python_version()}",
    }
    (out / "build.json").write_text(json.dumps(meta, indent=2) + "\n")
    (out / "BUILD.md").write_text(_render_build_md(meta))
    _log(f"wrote {out}")
    return out


def judgement_depth(sizes: list[int]) -> dict:
    """How deep this build's judgement pool actually goes.

    Every `BUILD.md` said "ESCI judged up to forty results per query" until
    2026-09-14. It is not true of this build and it was never measured: the
    deepest query here has 136 judgements, the mean is about 21, and dozens of
    queries are past forty. It is a sentence somebody had read somewhere,
    printed into a generated document, where being inside a generated document
    reads as having come from the build.

    What is true - that the pool is finite, so an unjudged document is not a
    judged-irrelevant one - does not need a bound to be worth saying, and where
    a figure is wanted the build is the only place it can honestly come from.
    Hence this: the numbers go into `build.json`, and `BUILD.md` prints what is
    in `build.json`. Forty survives only as a reference point, because it is
    what a reader will have heard.
    """
    if not sizes:
        return {"queries": 0, "min": 0, "max": 0, "mean": 0.0, "median": 0,
                "over_40": 0}
    ordered = sorted(sizes)
    return {
        "queries": len(ordered),
        "min": ordered[0],
        "max": ordered[-1],
        "mean": round(statistics.fmean(ordered), 1),
        "median": int(statistics.median(ordered)),
        "over_40": sum(1 for n in ordered if n > 40),
    }


def _hash_outputs(out: Path, names: list[str] | None = None) -> str:
    """Hash of the files this build wrote, so two people can confirm they match.

    `names` is the list the build recorded. Without it this hashed every
    `.jsonl` and `.csv` in the directory - including files something else put
    there later. Chapter 4 tells a reader to run `embed_offline.py`, which
    writes its vectors beside the corpus, and from that moment `verify`
    reported MISMATCH on a corpus nobody had touched. A checksum that fails for
    the wrong reason teaches people to ignore it.
    """
    if names is None:
        names = sorted(p.name for p in out.iterdir()
                       if p.suffix in (".jsonl", ".csv"))
    h = hashlib.blake2b(digest_size=16)
    for name in sorted(names):
        h.update(name.encode())
        h.update((out / name).read_bytes())
    return h.hexdigest()


def _render_build_md(m: dict) -> str:
    c = m["counts"]
    # Indexed, not `.get()`-ed with a fallback. A build made before this was
    # measured has no honest answer here, and a document that quietly prints a
    # default instead of failing is how the sentence this replaces survived for
    # as long as it did.
    j = m["judgements_per_query"]
    warning = ""
    if m["partial"]:
        warning = (
            "\n> **Partial build — not for published numbers.** Only some "
            "shards were read. The query universe is incomplete, and worse, a "
            "query's judgements can be split across shards, so some queries "
            "here have a truncated ground truth. Useful for exercising the "
            "tooling, useless for measurement.\n")
    return f"""# {m['build_id']}
{warning}
Built {m['built_at']} on {m['built_on']}.

    python shared/tools/corpus.py build --preset {m['preset']['name']} \\
        --seed {m['seed']} --gains {m['gain_mapping']}

Source: `{m['source']['repo']}` pinned at commit `{m['source']['revision'][:12]}`,
locale `{m['locale']}`, query set `{m['difficulty']}`
(`{m['difficulty_column']}`). The dataset itself is
[`{m['source']['canonical']}`](https://github.com/amazon-science/esci-data);
that repository is the citation, and this mirror is how it is read.

The commit is pinned rather than tracking `main`, so the dataset cannot change
underneath a measurement.

| | train | validation | test |
|---|---|---|---|
| queries | {c['train']['queries']:,} | {c['validation']['queries']:,} | {c['test']['queries']:,} |
| judgements | {c['train']['judgements']:,} | {c['validation']['judgements']:,} | {c['test']['judgements']:,} |

- corpus documents: **{c['corpus_documents']:,}**
- of which judged: {c['judged_products']:,}; distractors: {c['distractors']:,}
- without a description: {c['documents_without_description']:,}
  ({c['documents_without_description'] / max(1, c['corpus_documents']):.1%})

Gain mapping `{m['gain_mapping']}`. NDCG computed under one mapping is not
comparable with NDCG computed under another.

The validation split is carved out of train; ESCI ships only train and test, so
the third one is ours. Test is touched only to produce a number that is
reported, never to make a decision. `doc_signals.jsonl` is derived from train
judgements alone — deriving it from all of them would put test labels into the
index.

Unjudged is not the same as irrelevant: judgements are pooled, and the pool is
finite where the corpus is not, so some distractors are relevant products
nobody labelled. Treating them as irrelevant is the standard pooling assumption
and biases recall down uniformly, so comparisons stay valid while the absolute
number is pessimistic. How deep this build's pool goes, measured on this build:

- judgements per query: **{j['min']} to {j['max']}**
- median {j['median']}, mean {j['mean']}
- queries with more than forty judgements: {j['over_40']:,} of {j['queries']:,}

Content hash: `{m['content_hash']}` - two builds from the same arguments
produce the same bytes, and this is how you would tell.
"""


def verify(path: Path) -> int:
    meta = json.loads((path / "build.json").read_text())
    names = meta.get("hashed_files")
    missing = [n for n in (names or []) if not (path / n).exists()]
    if missing:
        print(f"MISSING from the build: {', '.join(missing)}")
        return 1
    actual = _hash_outputs(path, names)
    ok = actual == meta["content_hash"]
    print(f"expected {meta['content_hash']}\nactual   {actual}\n"
          f"{'match' if ok else 'MISMATCH'}")
    if ok and names:
        extra = sorted(p.name for p in path.iterdir()
                       if p.suffix in (".jsonl", ".csv") and p.name not in names)
        if extra:
            print(f"\n(also present, and not part of the build: "
                  f"{', '.join(extra)})")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--preset", choices=sorted(PRESETS), default="small")
    b.add_argument("--seed", type=int, default=42)
    b.add_argument("--gains", choices=sorted(gains_mod.MAPPINGS),
                   default=gains_mod.DEFAULT)
    b.add_argument("--difficulty", choices=sorted(DIFFICULTIES), default="hard",
                   help="which ESCI query set: `hard` is the reduced one the "
                        "ranking task uses, with easy queries removed; `all` "
                        "includes them")
    b.add_argument("--shards", type=int, default=None,
                   help="read only the first N shards per split. For exercising "
                        "the tooling: judgement sets come out truncated, so the "
                        "result is marked partial and cannot be measured against.")
    b.add_argument("--from-snapshot", metavar="URL", default=None,
                   help="not implemented yet: fetch a prebuilt corpus instead "
                        "of building one.")

    v = sub.add_parser("verify")
    v.add_argument("path", type=Path)

    args = ap.parse_args()
    if args.cmd == "verify":
        return verify(args.path)
    if args.from_snapshot:
        print("--from-snapshot is not implemented yet.", file=sys.stderr)
        return 2
    build(PRESETS[args.preset], args.seed, args.gains, args.shards,
          args.difficulty)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
