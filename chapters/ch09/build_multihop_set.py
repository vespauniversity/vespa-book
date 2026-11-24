"""Turn the human relevance labels into questions with a verified answer.

ESCI already carries what an agent question needs. For a query, the products
labelled `E` (exact) are what the shopper wanted, the ones labelled `S`
(substitute) are acceptable alternatives, and the ones labelled `I`
(irrelevant) are labelled non-answers. So, for each query:

    anchor      the highest-gain `E` product (ties: smallest product id)
    question    "find an alternative to the anchor that is not made by its brand"
    oracle      the query's `S` or `E` products whose brand differs from the
                anchor's (another brand's exact match is a better alternative
                than a substitute; the anchor itself is never in the set)
    negatives   the query's `I` products
    pool        every product the query has a judgement for, whatever the
                label, anchor included: the candidate set a search for this
                question is limited to, so that a product nobody judged can
                never be returned (and wrongly scored as a miss)

A question is kept only when its oracle set has at least `--threshold`
members, so every kept question can be answered. An anchor with no brand on
file is dropped and counted: "not made by <nothing>" is not a question.

Two answer shapes come from the same anchors:

    alternative   hand back one product from the oracle set
    brands        hand back which brands (other than the anchor's) offer an
                  alternative, and how many each - a group-by over the oracle

The labels are human, so the answer key is not generated. What cannot be
derived is genuinely multi-step reasoning: these are two-step questions built
from one query's judgements.

Usage:
    python chapters/ch10/build_multihop_set.py --split test --threshold 3 \\
        --out chapters/ch10/expected/multihop-set.json
    python chapters/ch10/build_multihop_set.py --split test --block set

stdout carries the one markdown block asked for; everything else goes to
stderr. Nothing here needs a running Vespa.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))
import builds      # noqa: E402
import hostinfo    # noqa: E402

THRESHOLDS = (1, 3, 5)
SHAPES = ["alternative", "brands"]
CAPTION = ("Counts over the {split} split's questions. Deterministic: the same "
           "build and threshold always give the same table.")


def norm_brand(brand: str) -> str:
    """Brands are compared as lower-cased, whitespace-collapsed strings."""
    return " ".join((brand or "").split()).lower()


def load_products(path: Path) -> dict[str, dict]:
    """product id -> {title, brand}, from the build's feed file."""
    out: dict[str, dict] = {}
    with path.open() as fh:
        for line in fh:
            fields = json.loads(line)["fields"]
            out[fields["id"]] = {"title": fields.get("title", ""),
                                 "brand": fields.get("brand", "") or ""}
    return out


def load_judgement_rows(build: Path, split: str) -> dict[str, list[dict]]:
    """query id -> [{product_id, label, gain}], in file order."""
    builds._check(split)
    out: dict[str, list[dict]] = {}
    with (build / f"judgements_{split}.csv").open() as fh:
        for row in csv.DictReader(fh):
            out.setdefault(row["query_id"], []).append(
                {"product_id": row["document_id"], "label": row["label"],
                 "gain": float(row["gain"])})
    return out


def query_order(qid: str) -> tuple:
    """Numeric ids sort as numbers, anything else after them as text."""
    return (0, int(qid), "") if qid.isdigit() else (1, 0, qid)


def derive(rows_by_query: dict[str, list[dict]], queries: dict[str, str],
           products: dict[str, dict]) -> dict:
    """Every question the labels allow, before any threshold.

    Returns the built questions (branded anchors), the number of queries with
    no `E` product at all, and the anchors dropped for having no brand.
    """
    built: list[dict] = []
    no_anchor = 0
    dropped_no_brand: list[dict] = []
    for qid in sorted(rows_by_query, key=query_order):
        rows = rows_by_query[qid]
        exact = [r for r in rows if r["label"] == "E"]
        if not exact:
            no_anchor += 1
            continue
        best = max(r["gain"] for r in exact)
        anchor_id = min(r["product_id"] for r in exact if r["gain"] == best)
        anchor = products.get(anchor_id, {"title": "", "brand": ""})
        anchor_brand = anchor["brand"]
        oracle = [r["product_id"] for r in rows if r["label"] in ("S", "E")
                  and r["product_id"] != anchor_id
                  and norm_brand(products.get(r["product_id"], {}).get("brand", ""))
                  != norm_brand(anchor_brand)]
        negatives = [r["product_id"] for r in rows if r["label"] == "I"]
        brands: dict[str, int] = {}
        for pid in oracle:
            b = norm_brand(products.get(pid, {}).get("brand", ""))
            if b:
                brands[b] = brands.get(b, 0) + 1
        question = {
            "question_id": qid, "query_id": qid, "query": queries.get(qid, ""),
            "anchor_id": anchor_id, "anchor_title": anchor["title"],
            "anchor_brand": anchor_brand, "oracle": oracle,
            "oracle_brands": dict(sorted(brands.items())),
            "negatives": negatives, "shape": list(SHAPES),
            "pool": list(dict.fromkeys(r["product_id"] for r in rows)),
        }
        if not norm_brand(anchor_brand):
            dropped_no_brand.append(question)
            continue
        built.append(question)
    return {"built": built, "no_anchor": no_anchor, "dropped": dropped_no_brand}


def distribution(sizes: list[int]) -> dict:
    if not sizes:
        return {"n": 0}
    ordered = sorted(sizes)

    def pick(p: float) -> int:
        return ordered[min(len(ordered) - 1, int(round(p * (len(ordered) - 1))))]

    return {"n": len(ordered), "min": ordered[0], "p25": pick(0.25),
            "median": statistics.median(ordered), "p75": pick(0.75),
            "max": ordered[-1], "mean": round(statistics.fmean(ordered), 3)}


def survivors(questions: list[dict]) -> dict[str, int]:
    return {str(t): sum(1 for q in questions if len(q["oracle"]) >= t)
            for t in THRESHOLDS}


def summarise(derived: dict, threshold: int) -> tuple[dict, list[dict]]:
    """The report body and the questions kept at `threshold`."""
    built, dropped = derived["built"], derived["dropped"]
    kept = [q for q in built if len(q["oracle"]) >= threshold]
    # The same counts with the no-brand anchors left in, so the figure can be
    # compared with a count that never dropped them.
    with_unbranded = built + dropped
    report = {
        "threshold": threshold,
        "queries_with_judgements": len(built) + len(dropped) + derived["no_anchor"],
        "queries_without_exact_product": derived["no_anchor"],
        "anchors_dropped_empty_brand": len(dropped),
        "questions_built": len(built),
        "survivors_by_threshold": survivors(built),
        "survivors_by_threshold_with_unbranded_anchors": survivors(with_unbranded),
        "questions_kept": len(kept),
        "per_shape": {"alternative": len(kept),
                      "brands": sum(1 for q in kept if q["oracle_brands"])},
        "oracle_size_all_built": distribution([len(q["oracle"]) for q in built]),
        "negative_size_all_built": distribution([len(q["negatives"]) for q in built]),
        "oracle_size_kept": distribution([len(q["oracle"]) for q in kept]),
        "negative_size_kept": distribution([len(q["negatives"]) for q in kept]),
        "brands_per_question_kept": distribution(
            [len(q["oracle_brands"]) for q in kept]),
    }
    return report, kept


def block_set(report: dict) -> str:
    """One markdown table of the counts. Stdout of `--block set`."""
    s = report["survivors_by_threshold"]
    lines = [
        f"| {report['split']} split | count |",
        "|---|---|",
        "| oracle rule | `S` or `E` products of another brand than the anchor's |",
        f"| queries with judgements | {report['queries_with_judgements']:,} |",
        f"| anchors dropped, no brand on file | {report['anchors_dropped_empty_brand']:,} |",
        f"| questions built | {report['questions_built']:,} |",
        f"| survive at oracle ≥ 1 | {s['1']:,} |",
        f"| survive at oracle ≥ 3 | {s['3']:,} |",
        f"| survive at oracle ≥ 5 | {s['5']:,} |",
        f"| kept at threshold {report['threshold']}: shape `alternative` | "
        f"{report['per_shape']['alternative']:,} |",
        f"| kept at threshold {report['threshold']}: shape `brands` | "
        f"{report['per_shape']['brands']:,} |",
    ]
    for name, key in (("oracle size", "oracle_size_kept"),
                      ("negatives per question", "negative_size_kept")):
        d = report[key]
        lines.append(
            f"| {name}, kept (min / p25 / median / p75 / max, mean) | "
            f"{d['min']} / {d['p25']} / {d['median']:g} / {d['p75']} / {d['max']}, "
            f"{d['mean']:.3f} |")
    return "\n".join(lines) + "\n\n" + CAPTION.format(split=report["split"]) + "\n"


BLOCKS = {"set": block_set}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None,
                    help="a corpus build directory (default: the latest)")
    ap.add_argument("--split", required=True, choices=builds.SPLITS,
                    help="which split's judgements to derive from; no default")
    ap.add_argument("--threshold", type=int, default=3,
                    help="smallest oracle set a question may have (default 3)")
    ap.add_argument("--questions-out", type=Path, default=None,
                    help="question file, one JSON object per line (default: "
                         "<build>/multihop_<split>.jsonl)")
    ap.add_argument("--out", type=Path, default=None,
                    help="write the report JSON here")
    ap.add_argument("--block", choices=sorted(BLOCKS), default="set",
                    help="the one markdown block printed on stdout")
    args = ap.parse_args(argv)
    if args.threshold < 1:
        raise SystemExit("--threshold must be at least 1")

    build = args.build or builds.latest()
    rows = load_judgement_rows(build, args.split)
    queries = builds.load_queries(build, args.split)
    products = load_products(build / "products.jsonl")

    derived = derive(rows, queries, products)
    report, kept = summarise(derived, args.threshold)
    report = {"build": builds.meta(build)["build_id"], "split": args.split,
              **report, "host": hostinfo.collect()}

    questions_out = args.questions_out or (build / f"multihop_{args.split}.jsonl")
    questions_out.parent.mkdir(parents=True, exist_ok=True)
    with questions_out.open("w") as fh:
        for q in kept:
            fh.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(f"wrote {questions_out} ({len(kept)} questions)", file=sys.stderr)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.out}", file=sys.stderr)

    print(BLOCKS[args.block](report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
