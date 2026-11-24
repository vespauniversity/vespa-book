"""Put a run with retrieved evidence next to the same run with evidence supplied.

Two trajectory files over the same questions: one where the planner found its
own evidence, one where `agent_loop.py --oracle` handed it the anchor's brand
and category words. The gap between them is what finding that evidence cost.
A planner that fails even when handed the evidence is failing somewhere else.

The difference is taken question by question and given with a bootstrap
interval and the words "real" or "inside the noise". Five questions cannot show
a real difference; that is what the interval will say.

Both logs may come from either surface of `agent_loop.py` (the tools or the
query language), but from the same one: a gap between surfaces is a different
comparison from the gap between retrieved and supplied evidence.

`--subset hardneg` (block `compare-hardneg`) takes the same difference over the
questions whose pool holds at least one product labelled irrelevant, where a
search can rank a labelled non-answer first.

A supplied log written with `agent_loop.py --oracle-products` handed the
planner the oracle's products themselves, not the first hop's facts. It is
compared under its own block name, `compare-products` (`compare-products-hardneg`
over the subset), and `compare` refuses it, as `compare-products` refuses a
log that supplied facts: the two kinds of "supplied" never print under one
name.

Usage:
    python chapters/ch10/oracle_compare.py retrieved.jsonl oracle.jsonl \\
        --split test --block compare
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import builds            # noqa: E402
import deployed          # noqa: E402
import hostinfo          # noqa: E402
import metrics           # noqa: E402

import eval_trajectory   # noqa: E402

CAPTION = ("n = {n}{example}. Difference = evidence "
           "supplied minus evidence retrieved, question by question, with a "
           "bootstrap interval.")


def compare(retrieved: list[dict], supplied: list[dict],
            questions: dict[str, dict], subset: str = "all",
            tenants: dict[str, str] | None = None) -> dict:
    n_all = len(retrieved)
    retrieved = eval_trajectory.subset_lines(retrieved, questions, subset)
    supplied = eval_trajectory.subset_lines(supplied, questions, subset)
    a = eval_trajectory.evaluate_log(retrieved, questions, tenants=tenants)
    b = eval_trajectory.evaluate_log(supplied, questions, tenants=tenants)
    if a["surface"] != b["surface"]:
        raise SystemExit(f"the two logs were run on different surfaces "
                         f"({a['surface']} and {b['surface']}); compare like with like")
    delta = metrics.bootstrap_delta(eval_trajectory.per_question_success(retrieved),
                                    eval_trajectory.per_question_success(supplied))
    return {**({"subset": subset, "subset_of": n_all} if subset != "all" else {}),
            "retrieved": a, "supplied": b, "delta": delta}


CAPTION_PRODUCTS = ("n = {n}{example}. Difference = the oracle's products "
                    "supplied minus evidence retrieved, question by question, with a "
                    "bootstrap interval. Supplied: every product of the question's "
                    "oracle, with its title and brand, in the evidence before the "
                    "first turn.")


def _table(result: dict, supplied_name: str, caption: str) -> str:
    fmt = metrics.fmt_metric
    rows = ["| evidence | success | queries per task, p50 |", "|---|---|---|"]
    for name, key in (("retrieved by the planner", "retrieved"),
                      (supplied_name, "supplied")):
        r = result[key]
        rows.append(f"| {name} | {fmt(r['success_rate'])} ± {fmt(r['half_width'])} | "
                    f"{r['queries_per_task'].get('p50', 0):g} |")
    rows.append(f"| difference | {metrics.fmt_delta(result['delta'])} | |")
    n = result["retrieved"]["n"]
    return "\n".join(rows) + "\n\n" + caption.format(
        n=n, example=eval_trajectory.example_phrase(n)) + "\n"


def block_compare(result: dict) -> str:
    return _table(result, "supplied", CAPTION)


def block_compare_products(result: dict) -> str:
    return _table(result, "the oracle's products supplied", CAPTION_PRODUCTS)


def _hardneg(text: str, result: dict) -> str:
    return text.rstrip("\n") + (
        f" Hard-negative subset: the {result['retrieved']['n']} questions, of "
        f"{result['subset_of']}, whose pool holds at least one product labelled "
        "irrelevant (I).\n")


def block_compare_hardneg(result: dict) -> str:
    return _hardneg(block_compare(result), result)


def block_compare_products_hardneg(result: dict) -> str:
    return _hardneg(block_compare_products(result), result)


BLOCKS = {"compare": block_compare, "compare-hardneg": block_compare_hardneg,
          "compare-products": block_compare_products,
          "compare-products-hardneg": block_compare_products_hardneg}
# a block name says which reading it is: the subset, and what the supplied log
# was handed (the first hop's facts, or the oracle's products)
BLOCK_NEEDS = {"compare": ("all", "facts"), "compare-hardneg": ("hardneg", "facts"),
               "compare-products": ("all", "products"),
               "compare-products-hardneg": ("hardneg", "products")}


def supplied_kind(lines: list[dict]) -> str:
    """What a supplied log was handed: `products`, or `facts` - also for a
    log from before the products mode, which records no kind. Refuses a log
    whose lines disagree."""
    kinds = {x.get("oracle_kind", "facts") for x in lines}
    if len(kinds) != 1:
        raise SystemExit(f"the supplied log mixes kinds of evidence: {sorted(kinds)}")
    return kinds.pop()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("retrieved", type=Path, help="trajectories, evidence retrieved")
    ap.add_argument("oracle", type=Path, help="trajectories, evidence supplied")
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--split", required=True, choices=builds.SPLITS,
                    help="which split's question file; no default")
    ap.add_argument("--questions", type=Path, default=None)
    ap.add_argument("--block", choices=sorted(BLOCKS), default="compare")
    ap.add_argument("--out", type=Path, default=None, help="write the comparison JSON here")
    ap.add_argument("--subset", choices=eval_trajectory.SUBSETS, default="all",
                    help="every question (all), or those whose pool holds an "
                         "I-labelled product (hardneg; block compare-hardneg)")
    args = ap.parse_args(argv)
    if BLOCK_NEEDS[args.block][0] != args.subset:
        raise SystemExit(f"--block {args.block} goes with --subset {BLOCK_NEEDS[args.block][0]}")

    build = args.build or builds.latest()
    questions = eval_trajectory.load_questions(build, args.split, args.questions)
    retrieved = eval_trajectory.load_lines(args.retrieved)
    supplied = eval_trajectory.load_lines(args.oracle)
    kind = supplied_kind(supplied)
    if BLOCK_NEEDS[args.block][1] != kind:
        wanted = [name for name, need in BLOCK_NEEDS.items()
                  if need == (args.subset, kind)][0]
        raise SystemExit(f"--block {args.block} reads a log supplied "
                         f"{BLOCK_NEEDS[args.block][1]}; this one was supplied {kind}: "
                         f"--block {wanted}. The two kinds of supplied evidence are not "
                         "printed under one name")
    result = compare(retrieved, supplied, questions, args.subset,
                     eval_trajectory.tenants_for(retrieved + supplied, build))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        report = {"build": builds.meta(build)["build_id"], "split": args.split,
                  # what answered the runs, copied from the log; this tool queries nothing
                  deployed.FIELD: retrieved[0].get(deployed.FIELD, "not recorded"),
                  **result, "host": hostinfo.collect()}
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    print(BLOCKS[args.block](result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
