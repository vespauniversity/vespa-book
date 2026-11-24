"""Put two runs of the same questions side by side along one axis.

`oracle_compare.py` compares evidence retrieved with evidence supplied. The
three other comparisons this chapter makes are between runs that differ in one
other setting, with everything else held:

    surfaces   the tool surface against the query surface - same model, same
               questions, same k, same evidence mode. Did taking the
               translation layer away change anything?
    k          k = 3 against k = 20 on one surface - same everything else.
               Did showing the model more results make its answer worse?
    tenant     no seller boundary against a run under one (the `tenant` on
               the log's lines) - same surface, same everything else. What
               did the boundary cost, question by question? The block adds
               the tool statuses of both runs, where `filtered` shows.

Both logs are scored with `eval_trajectory`, and the difference in success is
taken question by question with a bootstrap interval, labelled "real" when the
interval stays on one side of zero and "inside the noise" when it spans it.
Queries per task, context bytes and invalid queries per task (refused
statements or calls, counted per question) are compared the same way.

The two logs must differ in the axis and agree on everything else: a run that
differs in two settings cannot say which one did it.

Usage:
    python chapters/ch10/surface_compare.py tools.jsonl query.jsonl \\
        --split test --block surfaces --out surface-compare-k3.json
    python chapters/ch10/surface_compare.py k3.jsonl k20.jsonl \\
        --split test --block k --out k-compare-tools.json
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

# axis -> (the field that must differ, the fields that must agree)
AXES = {
    "surfaces": ("surface", ("planner", "shape", "k", "oracle_mode", "model")),
    "k": ("k", ("planner", "shape", "surface", "oracle_mode", "model")),
    "tenant": ("boundary", ("planner", "shape", "k", "surface", "oracle_mode", "model")),
}
LABELS = {"surface": {"tools": "tool surface", "query": "query surface"}}

CAPTION = ("n = {n}. Difference = {b} minus {a}, question by question, with a "
           "bootstrap interval; success is 1 or 0 per question, queries and bytes "
           "are per question. Invalid queries per task = statements or calls "
           "refused, over questions.")


def label(field: str, value) -> str:
    if field == "k":
        return f"k = {value}"
    if field == "boundary":
        if not value:
            return "no boundary"
        return (f"boundary of {value['sellers_per_question']} seller"
                + ("s" if value["sellers_per_question"] != 1 else "")
                + (f" ({value['tenant_rule']})" if value.get("tenant_rule") else ""))
    return LABELS.get(field, {}).get(value, f"{field} {value}")


def per_question(lines: list[dict], key: str) -> dict[str, float]:
    return {x["question_id"]: float(x[key]) for x in lines}


def per_question_invalid(lines: list[dict]) -> dict[str, float]:
    """question id -> refused statements or calls in it, the count whose mean
    over questions is the report's `invalid_queries_per_task`."""
    return {x["question_id"]: float(sum(1 for s in x["steps"] if s.get("status") == "malformed"))
            for x in lines}


def compare(a: list[dict], b: list[dict], questions: dict[str, dict], axis: str,
            tenants: dict[str, str] | None = None) -> dict:
    differ, agree = AXES[axis]
    ra = eval_trajectory.evaluate_log(a, questions, tenants=tenants)
    rb = eval_trajectory.evaluate_log(b, questions, tenants=tenants)
    if ra.get(differ) == rb.get(differ):
        raise SystemExit(f"both logs have {differ} = {ra.get(differ)!r}; the {axis} "
                         "comparison needs two values")
    same = [f for f in agree if ra.get(f) != rb.get(f)]
    if same:
        raise SystemExit("the logs differ in more than the axis: " + ", ".join(
            f"{f} {ra.get(f)!r} / {rb.get(f)!r}" for f in same))
    if set(x["question_id"] for x in a) != set(x["question_id"] for x in b):
        raise SystemExit("the two logs do not cover the same questions")
    delta = {
        "success": metrics.bootstrap_delta(eval_trajectory.per_question_success(a),
                                           eval_trajectory.per_question_success(b)),
        "queries_per_task": metrics.bootstrap_delta(per_question(a, "queries_issued"),
                                                    per_question(b, "queries_issued")),
        "context_bytes": metrics.bootstrap_delta(per_question(a, "context_bytes"),
                                                 per_question(b, "context_bytes")),
        "invalid_queries_per_task": metrics.bootstrap_delta(per_question_invalid(a),
                                                            per_question_invalid(b)),
    }
    return {"axis": axis, "a": ra, "b": rb, "delta": delta,
            "a_label": label(differ, ra.get(differ)), "b_label": label(differ, rb.get(differ))}


def _row(r: dict) -> list[str]:
    fmt = metrics.fmt_metric
    q = r["queries_per_task"]
    return [f"{fmt(r['success_rate'])} ± {fmt(r['half_width'])}",
            f"{q.get('p50', 0):g} / {q.get('p95', 0):g}",
            f"{r['context_bytes_mean']:,.0f}",
            fmt(r["invalid_queries_per_task"])]


def _delta_row(d: dict) -> list[str]:
    def plain(x: dict, places: int) -> str:
        return (f"{x['delta']:+.{places}f} [{x['lo']:+.{places}f}, {x['hi']:+.{places}f}], "
                + ("real" if x["significant"] else "inside the noise"))
    return [metrics.fmt_delta(d["success"]),
            plain(d["queries_per_task"], 2) + " (mean)",
            plain(d["context_bytes"], 0) + " (mean)",
            metrics.fmt_delta(d["invalid_queries_per_task"]) + " (mean)"]


def block(result: dict) -> str:
    head = ["| | success | queries per task, p50 / p95 | context bytes, mean | invalid queries per task |",
            "|---|---|---|---|---|"]
    rows = [f"| {result['a_label']} | " + " | ".join(_row(result["a"])) + " |",
            f"| {result['b_label']} | " + " | ".join(_row(result["b"])) + " |",
            "| difference | " + " | ".join(_delta_row(result["delta"])) + " |"]
    if result["axis"] == "k":
        fmt = metrics.fmt_metric
        rows.append("")
        rows.append("| | hit@k | precision@k |")
        rows.append("|---|---|---|")
        for key in ("a", "b"):
            r = result[key]
            rows.append(f"| {result[key + '_label']} | {fmt(r['hit_at_k'])} | "
                        f"{fmt(r['precision_at_k'])} |")
    if result["axis"] == "tenant":
        rows.append("")
        rows.append("| | tool statuses |")
        rows.append("|---|---|")
        for key in ("a", "b"):
            statuses = ", ".join(f"{k} {v}" for k, v in result[key]["status_counts"].items())
            rows.append(f"| {result[key + '_label']} | {statuses or '—'} |")
    n = result["a"]["n"]
    return "\n".join(head + rows) + "\n\n" + CAPTION.format(
        n=n, a=result["a_label"], b=result["b_label"]) + "\n"


BLOCKS = {"surfaces": block, "k": block, "tenant": block}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a", type=Path, help="trajectories, the first arm (tools, k = 3, "
                                         "or no boundary)")
    ap.add_argument("b", type=Path, help="trajectories, the second arm (query, k = 20, "
                                         "or the boundary)")
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--split", required=True, choices=builds.SPLITS,
                    help="which split's question file; no default")
    ap.add_argument("--questions", type=Path, default=None)
    ap.add_argument("--block", choices=sorted(BLOCKS), required=True,
                    help="which axis the two logs differ in")
    ap.add_argument("--out", type=Path, default=None, help="write the comparison JSON here")
    args = ap.parse_args(argv)

    build = args.build or builds.latest()
    questions = eval_trajectory.load_questions(build, args.split, args.questions)
    a = eval_trajectory.load_lines(args.a)
    b = eval_trajectory.load_lines(args.b)
    result = compare(a, b, questions, args.block, eval_trajectory.tenants_for(a + b, build))
    report = {"build": builds.meta(build)["build_id"], "split": args.split,
              deployed.FIELD: a[0].get(deployed.FIELD, "not recorded"),
              **result, "host": hostinfo.collect()}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    print(BLOCKS[args.block](result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
