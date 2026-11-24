"""Score a trajectory log against the question set it was run on.

`agent_loop.py` writes one line per question. This reads that file and the
question file and reports, for the whole run:

    success_rate       the share of questions whose answer was correct - a
                       product from the oracle set (shape `alternative`), or a
                       brand table naming every oracle brand (shape `brands`)
                       - with a binomial interval, +/- 1.96 * sqrt(p(1-p)/n)
    brand_recall /     shape `brands` only, and what its summary shows instead
    brand_precision    of a success rate: how much of the oracle's brands the
                       table names, and how much of the table the oracle
                       names, averaged over questions
    hit_at_k           the share of questions where any product the planner
                       saw in its last search is in the oracle set
    precision_at_k     of the products it saw, the share in the oracle set,
                       averaged over questions
    context_bytes      how much result text the planner was handed, on average
    status_counts      how often each tool status came back, over all steps
    queries_per_task   how many Vespa requests one question cost (median, p95)
    invalid_queries_per_task
                       `malformed` steps divided by questions: statements or
                       calls the engine or the tool refused, per task
    surface            what the planner worked: the tools, or the query
                       language itself (`agent_loop.py --surface`); a log
                       written before the surface was recorded has none

The summary block prints the last two only for a log that records its
surface, so a block printed from an older log is unchanged.

Two more readings of the same log, each under a block name of its own so the
summary block stays what it was:

    --subset hardneg   score only the questions whose pool holds at least one
                       product labelled irrelevant (`I`): a search inside such
                       a pool can rank a labelled non-answer first, where a
                       pool with no `I` product cannot (`summary-hardneg`)
    --success all-top-k
                       a stricter success: the answer is in the oracle set AND
                       every product the planner saw in its last search is in
                       it (`summary-alltopk`). Showing the planner more results
                       cannot lower the first definition's hit@k; it can lower
                       this one.

A log written with the oracle's products supplied (`agent_loop.py
--oracle-products`, `oracle_kind` "products" on its lines) is scored the same
way; its report copies `oracle_kind`, and every block's run label says ", the
oracle's products supplied" where a log with the first hop's facts supplied
says ", evidence supplied".

A log written under a seller boundary (`agent_loop.py --tenant-from-anchor`
or `--tenant-pair`; the `tenant` on each line) gets one more reading, under
the block name `boundary`: the ceiling the boundary leaves - how many
questions have at least one oracle product inside the sellers the question
ran under, and what share of the oracle is inside, read from the build's
`tenants.jsonl` and no planner - and what the planner did with a `filtered`
status: how many came back, what the next action was, and how many of the
questions that met one still ended with an answer in the oracle (recovered).
The block refuses a log with no boundary.

The binomial interval is honest only for a large n. At n = 5 an observed rate
of 0 or 1 gets a zero-width interval, so the block also prints the widest
interval the sample size allows (the one at a rate of 0.5). A run of five
questions is an example of the tool, not a measurement.

Usage:
    python chapters/ch10/eval_trajectory.py rules.jsonl --split test \\
        --out report.json --block summary
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import builds      # noqa: E402
import deployed    # noqa: E402
import hostinfo    # noqa: E402
import metrics     # noqa: E402

CAPTION = ("n = {n}{example}. The interval is "
           "1.96 * sqrt(p(1-p)/n); the widest case for this n is shown "
           "because the observed-rate interval collapses at 0 and 1.")
EXAMPLE_N = 100   # fewer questions than this is an example of the tool, not a measurement
LATENCY_CAPTION = ("Retrieval time only: the sum of a task's tool calls as the loop timed "
                   "them (every request a call made, re-runs included), model time "
                   "excluded. {conditions}")
MACHINE = ("One pass over the whole set after a warm-up pass over it, on an Apple M4 Pro "
           "with a 4 CPU / 10 GB container VM; a reader's machine will give other numbers.")


def supplied_words(report: dict) -> str:
    """What the run was handed, as the captions say it: nothing, the first
    hop's facts (", evidence supplied"), or the oracle's products (a log
    from `agent_loop.py --oracle-products`, its `oracle_kind` "products")."""
    if not report.get("oracle_mode"):
        return ""
    if report.get("oracle_kind") == "products":
        return ", the oracle's products supplied"
    return ", evidence supplied"


def example_phrase(n: int) -> str:
    return ", an example run, not a measurement" if n < EXAMPLE_N else ""


def binomial_half_width(p: float, n: int) -> float:
    """Half the 95% interval around a rate p seen in n trials."""
    return 1.96 * math.sqrt(p * (1 - p) / n) if n else float("nan")


def load_lines(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def load_questions(build: Path, split: str, path: Path | None = None) -> dict[str, dict]:
    path = path or (build / f"multihop_{split}.jsonl")
    if not path.exists():
        raise SystemExit(f"{path} does not exist; make it with build_multihop_set.py")
    return {q["question_id"]: q for q in
            (json.loads(x) for x in path.read_text().splitlines() if x.strip())}


SUBSETS = ("all", "hardneg")
SUCCESS = ("answer", "all-top-k")
SUCCESS_WORDS = {"answer": "the answer is in the oracle set",
                 "all-top-k": "the answer and every product of the last search are in "
                              "the oracle set"}


def in_subset(question: dict, subset: str) -> bool:
    if subset == "all":
        return True
    if subset == "hardneg":
        return bool(question.get("negatives"))
    raise SystemExit(f"no such subset: {subset!r}")


def subset_lines(lines: list[dict], questions: dict[str, dict], subset: str) -> list[dict]:
    """The log's lines for the questions in `subset`; refuses an unknown question."""
    missing = [x["question_id"] for x in lines if x["question_id"] not in questions]
    if missing:
        raise SystemExit(f"questions not in the question file: {missing[:5]}")
    return [x for x in lines if in_subset(questions[x["question_id"]], subset)]


def succeeded(line: dict, question: dict, success: str = "answer") -> bool:
    if success == "answer":
        return bool(line["success"])
    if success == "all-top-k":
        if line.get("shape") == "brands":
            raise SystemExit("all-top-k is a success definition for shape `alternative`")
        oracle = set(question["oracle"])
        candidates = line.get("candidates") or []
        return bool(line["success"]) and bool(candidates) and all(c in oracle for c in candidates)
    raise SystemExit(f"no such success definition: {success!r}")


def has_boundary(lines: list[dict]) -> bool:
    return any(x.get("tenant") for x in lines)


def tenants_for(lines: list[dict], build: Path) -> dict[str, str] | None:
    """The build's product -> seller map when the log ran under a boundary,
    else None (a log with no `tenant` needs no tenants file)."""
    if not has_boundary(lines):
        return None
    from agent_loop import load_tenants
    return load_tenants(build)


def step_after(steps: list[dict], i: int) -> str:
    """What followed step i, as the boundary block names it."""
    if i + 1 >= len(steps):
        return "nothing (step limit)"
    nxt = steps[i + 1]
    if nxt.get("tool") in ("final", "error"):
        return nxt["tool"]
    return f"{nxt.get('tool')} {nxt.get('status')}"


def boundary_analysis(lines: list[dict], questions: dict[str, dict],
                      tenants: dict[str, str]) -> dict:
    """The seller boundary's reading of a log: the ceiling it leaves (from the
    build, no planner) and what the planner did with `filtered`."""
    answerable = 0
    shares: list[float] = []
    for x in lines:
        allowed = x["tenant"] if isinstance(x["tenant"], list) else [x["tenant"]]
        oracle = questions[x["question_id"]]["oracle"]
        missing = [pid for pid in oracle if pid not in tenants]
        if missing:
            raise SystemExit(f"no seller on file for oracle products, e.g. {missing[:3]}")
        inside = sum(1 for pid in oracle if tenants[pid] in allowed)
        answerable += 1 if inside else 0
        shares.append(inside / len(oracle) if oracle else 0.0)
    filtered_steps = 0
    after: dict[str, int] = {}
    met, went_on, recovered = 0, 0, 0
    successes_without = 0
    for x in lines:
        steps = x["steps"]
        where = [i for i, step in enumerate(steps) if step.get("status") == "filtered"]
        for i in where:
            filtered_steps += 1
            what = step_after(steps, i)
            after[what] = after.get(what, 0) + 1
        if where:
            met += 1
            later = steps[where[0] + 1:]
            if any(s.get("status") == "ok" and s.get("tool") in ("search", "query", "group")
                   for s in later):
                went_on += 1
            recovered += 1 if x["success"] else 0
        else:
            successes_without += 1 if x["success"] else 0
    n = len(lines)
    first = lines[0]
    sellers = len(first["tenant"]) if isinstance(first["tenant"], list) else 1
    return {
        "tenant_rule": first.get("tenant_rule"),
        "sellers_per_question": sellers,
        "answerable": answerable, "answerable_share": answerable / n,
        "oracle_share_inside": {key: value for key, value in
                                metrics.percentiles(shares).items()
                                if key in ("mean", "p50")} | {
                                    "p25": sorted(shares)[max(0, math.ceil(0.25 * n) - 1)],
                                    "p75": sorted(shares)[max(0, math.ceil(0.75 * n) - 1)]},
        "filtered_steps": filtered_steps,
        "after_filtered": dict(sorted(after.items())),
        "questions_with_filtered": met,
        "went_on_to_an_ok_search": went_on,
        "recovered": recovered,
        "questions_without_filtered": n - met,
        "successes_without_filtered": successes_without,
    }


def per_question_success(lines: list[dict], questions: dict[str, dict] | None = None,
                         success: str = "answer") -> dict[str, float]:
    """question id -> 1.0 / 0.0, the shape `metrics.bootstrap_delta` takes."""
    if success == "answer":
        return {x["question_id"]: 1.0 if x["success"] else 0.0 for x in lines}
    return {x["question_id"]: 1.0 if succeeded(x, questions[x["question_id"]], success) else 0.0
            for x in lines}


def evaluate_log(lines: list[dict], questions: dict[str, dict],
                 success: str = "answer", tenants: dict[str, str] | None = None) -> dict:
    n = len(lines)
    if not n:
        raise SystemExit("the trajectory file has no lines")
    missing = [x["question_id"] for x in lines if x["question_id"] not in questions]
    if missing:
        raise SystemExit(f"questions not in the question file: {missing[:5]}")
    if has_boundary(lines) and tenants is None:
        raise SystemExit("the log ran under a seller boundary; the build's tenants "
                         "are needed to read it (tenants_for)")
    wins_answer = sum(1 for x in lines if x["success"])
    wins = (wins_answer if success == "answer" else
            sum(1 for x in lines if succeeded(x, questions[x["question_id"]], success)))
    rate = wins / n

    hits, precisions = [], []
    for x in lines:
        if x["shape"] != "alternative" or not x["candidates"]:
            continue
        oracle = set(questions[x["question_id"]]["oracle"])
        inside = [c for c in x["candidates"] if c in oracle]
        hits.append(1.0 if inside else 0.0)
        precisions.append(len(inside) / len(x["candidates"]))

    statuses: dict[str, int] = {}
    for x in lines:
        for s in x["steps"]:
            if "status" in s:
                statuses[s["status"]] = statuses.get(s["status"], 0) + 1
    errors = sum(1 for x in lines if x.get("error"))
    if errors:
        statuses["planner_error"] = errors
    invalid = statuses.get("malformed", 0)

    def mean(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    task_ms = [sum(float(s["ms"]) for s in x["steps"] if "ms" in s) for x in lines]
    per_query = [ms / x["queries_issued"] for ms, x in zip(task_ms, lines)
                 if x["queries_issued"]]

    recalls = [x["brand_recall"] for x in lines if x.get("brand_recall") is not None]
    precisions_b = [x["brand_precision"] for x in lines
                    if x.get("brand_precision") is not None]
    first = lines[0]
    return {
        "planner": first["planner"], "oracle_mode": first["oracle_mode"],
        # what was supplied, copied from the log when it says (`facts` or
        # `products`); a log from before the products mode has none and the
        # report keeps the shape it was shipped with
        **({"oracle_kind": first["oracle_kind"]} if "oracle_kind" in first else {}),
        "shape": first["shape"], "k": first["k"], "n": n, "successes": wins,
        "success_rate": rate,
        "half_width": binomial_half_width(rate, n),
        "half_width_widest": binomial_half_width(0.5, n),
        # the stricter definition carries the first one beside it; the default
        # report keeps the shape it was shipped with
        **({"success_definition": success, "successes_answer": wins_answer,
            "success_rate_answer": wins_answer / n} if success != "answer" else {}),
        "hit_at_k": mean(hits), "precision_at_k": mean(precisions),
        "scored_for_hit_precision": len(hits),
        "brand_recall_mean": mean(recalls), "brand_precision_mean": mean(precisions_b),
        "context_bytes_mean": mean([float(x["context_bytes"]) for x in lines]),
        "status_counts": dict(sorted(statuses.items())),
        "queries_per_task": {key: value for key, value in
                             metrics.percentiles([float(x["queries_issued"])
                                                  for x in lines]).items()
                             if key in ("p50", "p95")},
        "invalid_queries_per_task": invalid / n,
        "queries_per_task_mean": mean([float(x["queries_issued"]) for x in lines]),
        "latency_per_task_ms": metrics.percentiles(task_ms),
        "latency_per_query_ms_mean": mean(per_query),
        "surface": first.get("surface"),
        "model": first.get("model"), "date": first.get("date"),
        "vespa": first.get("vespa"),
        # only a log run under a seller boundary carries this; the others keep
        # the shape they were shipped with
        **({"boundary": boundary_analysis(lines, questions, tenants)}
           if has_boundary(lines) else {}),
    }


def block_summary(report: dict) -> str:
    fmt = metrics.fmt_metric
    label = f"{report['planner']}, k = {report['k']}" + supplied_words(report)
    rows = [
        ("run", f"{label}, shape `{report['shape']}`"),
        ("questions", f"{report['n']}"),
    ]
    if report["shape"] == "brands":
        rows += [("brand recall, mean", fmt(report["brand_recall_mean"])),
                 ("brand precision, mean", fmt(report["brand_precision_mean"]))]
    else:
        rows += [
            ("success", f"{fmt(report['success_rate'])} ± {fmt(report['half_width'])} "
                        f"(widest for this n: ± {fmt(report['half_width_widest'])})"),
            ("hit@k", fmt(report["hit_at_k"])),
            ("precision@k", fmt(report["precision_at_k"])),
        ]
    rows += [
        ("context bytes, mean", "—" if report["context_bytes_mean"] is None
         else f"{report['context_bytes_mean']:,.0f}"),
        ("tool statuses", ", ".join(f"{k} {v}" for k, v in
                                    report["status_counts"].items()) or "—"),
        ("queries per task, p50 / p95",
         f"{report['queries_per_task'].get('p50', 0):g} / "
         f"{report['queries_per_task'].get('p95', 0):g}"),
    ]
    if report.get("surface"):
        rows += [("surface", report["surface"]),
                 ("invalid queries per task", fmt(report["invalid_queries_per_task"]))]
    lines = ["| | |", "|---|---|"] + [f"| {a} | {b} |" for a, b in rows]
    example = example_phrase(report["n"])
    caption = (CAPTION.format(n=report["n"], example=example) if report["shape"] != "brands"
               else f"n = {report['n']}{example}. Recall: the "
               "share of the oracle's brands the table names; precision: the share "
               "of the table's brands the oracle names.")
    return "\n".join(lines) + "\n\n" + caption + "\n"


def block_latency(report: dict) -> str:
    """Per-task retrieval latency of a run: the cost side of heading 9."""
    lat = report["latency_per_task_ms"]
    label = f"{report['planner']}, k = {report['k']}" + supplied_words(report)
    rows = [
        ("run", f"{label}, shape `{report['shape']}`"),
        ("tasks", f"{report['n']}"),
        ("queries per task, p50 / p95 (mean)",
         f"{report['queries_per_task'].get('p50', 0):g} / "
         f"{report['queries_per_task'].get('p95', 0):g} "
         f"({report['queries_per_task_mean']:.2f})"),
        ("latency per task, p50 / p95",
         f"{metrics.fmt_latency(lat.get('p50'))} / {metrics.fmt_latency(lat.get('p95'))}"),
        ("latency per task, max", metrics.fmt_latency(lat.get("max"))),
        ("latency per query, mean", metrics.fmt_latency(report["latency_per_query_ms_mean"])),
    ]
    conditions = report.get("latency_conditions", {})
    note = conditions.get("note", "") if conditions.get("warm") else \
        "One pass with no warm-up; not a latency measurement."
    lines = ["| | |", "|---|---|"] + [f"| {a} | {b} |" for a, b in rows]
    return "\n".join(lines) + "\n\n" + LATENCY_CAPTION.format(conditions=note) + "\n"


def block_summary_hardneg(report: dict) -> str:
    """The summary block over the hard-negative subset, said so in the caption."""
    text = block_summary(report)
    return text.rstrip("\n") + (
        f" Hard-negative subset: the {report['n']} questions, of {report['subset_of']}, "
        "whose pool holds at least one product labelled irrelevant (I).\n")


def block_summary_alltopk(report: dict) -> str:
    """Success under the stricter definition beside the first one."""
    fmt = metrics.fmt_metric
    label = f"{report['planner']}, k = {report['k']}" + supplied_words(report)
    rows = [
        ("run", f"{label}, shape `{report['shape']}`"),
        ("questions", f"{report['n']}"),
        ("success, all of top-k", f"{fmt(report['success_rate'])} ± {fmt(report['half_width'])} "
                                  f"(widest for this n: ± {fmt(report['half_width_widest'])})"),
        ("success, answer only", f"{fmt(report['success_rate_answer'])} ± "
                                 f"{fmt(binomial_half_width(report['success_rate_answer'], report['n']))}"),
        ("hit@k", fmt(report["hit_at_k"])),
        ("precision@k", fmt(report["precision_at_k"])),
        ("context bytes, mean", "—" if report["context_bytes_mean"] is None
         else f"{report['context_bytes_mean']:,.0f}"),
    ]
    if report.get("surface"):
        rows.append(("surface", report["surface"]))
    lines = ["| | |", "|---|---|"] + [f"| {a} | {b} |" for a, b in rows]
    caption = (f"n = {report['n']}{example_phrase(report['n'])}. All of top-k: a task "
               "succeeds only when the answer is in the oracle set and so is every "
               "product the planner saw in its last search; answer only: the first "
               "definition, the answer alone. The interval is 1.96 * sqrt(p(1-p)/n).")
    return "\n".join(lines) + "\n\n" + caption + "\n"


RULE_WORDS = {"anchor": "one seller per question, the anchor product's",
              "pair": "two sellers per question: the anchor product's and the oracle "
                      "seller with the most products in the oracle"}


def block_boundary(report: dict) -> str:
    """The seller boundary's reading: the ceiling it leaves and what the
    planner did with `filtered`."""
    b = report.get("boundary")
    if not b:
        raise SystemExit("--block boundary needs a log run under a seller boundary "
                         "(agent_loop.py --tenant-from-anchor or --tenant-pair)")
    fmt = metrics.fmt_metric
    label = f"{report['planner']}, k = {report['k']}" + supplied_words(report)
    if report.get("surface"):
        label += f", {report['surface']} surface"
    rule = RULE_WORDS.get(b.get("tenant_rule"),
                          f"{b['sellers_per_question']} seller(s) per question")
    share = b["oracle_share_inside"]
    n = report["n"]
    rows = [
        ("run", f"{label}, shape `{report['shape']}`"),
        ("boundary", rule),
        ("questions", f"{n}"),
        ("answerable: an oracle product inside the boundary",
         f"{b['answerable']} of {n} ({fmt(b['answerable_share'])})"),
        ("oracle share inside the boundary, p25 / p50 / p75",
         f"{fmt(share['p25'])} / {fmt(share['p50'])} / {fmt(share['p75'])}"),
        ("success", f"{fmt(report['success_rate'])} ± {fmt(report['half_width'])} "
                    f"(widest for this n: ± {fmt(report['half_width_widest'])})"),
        ("tool statuses", ", ".join(f"{k} {v}" for k, v in
                                    report["status_counts"].items()) or "—"),
        ("`filtered` statuses", f"{b['filtered_steps']} over "
                                f"{b['questions_with_filtered']} questions"),
        ("after a `filtered`, the next step", ", ".join(
            f"{k} {v}" for k, v in b["after_filtered"].items()) or "—"),
        ("questions with a `filtered` that went on to an ok search",
         f"{b['went_on_to_an_ok_search']} of {b['questions_with_filtered']}"),
        ("recovered: met a `filtered`, answer in the oracle",
         f"{b['recovered']} of {b['questions_with_filtered']}"),
        ("no `filtered`, answer in the oracle",
         f"{b['successes_without_filtered']} of {b['questions_without_filtered']}"),
    ]
    lines = ["| | |", "|---|---|"] + [f"| {a} | {v} |" for a, v in rows]
    caption = (f"n = {n}{example_phrase(n)}. The boundary is the `tenant` each question "
               "ran under; the sellers of the oracle's products come from the build, so "
               "the answerable count is the ceiling of success under this boundary and "
               "needs no planner. The success interval is 1.96 * sqrt(p(1-p)/n).")
    return "\n".join(lines) + "\n\n" + caption + "\n"


BLOCKS = {"summary": block_summary, "latency": block_latency,
          "summary-hardneg": block_summary_hardneg, "summary-alltopk": block_summary_alltopk,
          "boundary": block_boundary}
# a block name says which reading it is; the readings are not mixed under one name
BLOCK_NEEDS = {"summary": ("all", "answer"), "latency": ("all", "answer"),
               "summary-hardneg": ("hardneg", "answer"), "summary-alltopk": ("all", "all-top-k"),
               "boundary": ("all", "answer")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trajectories", type=Path, help="a file written by agent_loop.py")
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--split", required=True, choices=builds.SPLITS,
                    help="which split's question file to score against; no default")
    ap.add_argument("--questions", type=Path, default=None,
                    help="question file (default: <build>/multihop_<split>.jsonl)")
    ap.add_argument("--out", type=Path, default=None, help="write the report JSON here")
    ap.add_argument("--block", choices=sorted(BLOCKS), default="summary",
                    help="the one markdown block printed on stdout")
    ap.add_argument("--warmed-up", action="store_true",
                    help="the log was written right after a discarded pass over the "
                         "same questions, so its timings are warm (the latency block)")
    ap.add_argument("--subset", choices=SUBSETS, default="all",
                    help="score every question (all) or only those whose pool holds "
                         "an I-labelled product (hardneg; block summary-hardneg)")
    ap.add_argument("--success", choices=SUCCESS, default="answer",
                    help="what counts as success: the answer in the oracle set (answer), "
                         "or that and every product of the last search in it "
                         "(all-top-k; block summary-alltopk)")
    args = ap.parse_args(argv)
    if BLOCK_NEEDS[args.block] != (args.subset, args.success):
        wanted = BLOCK_NEEDS[args.block]
        raise SystemExit(f"--block {args.block} goes with --subset {wanted[0]} "
                         f"--success {wanted[1]}; the readings are not mixed under one name")

    build = args.build or builds.latest()
    questions = load_questions(build, args.split, args.questions)
    all_lines = load_lines(args.trajectories)
    lines = subset_lines(all_lines, questions, args.subset)
    if not lines:
        raise SystemExit(f"no question of the log is in the subset {args.subset!r}")
    report = evaluate_log(lines, questions, args.success, tenants_for(lines, build))
    report = {
        "build": builds.meta(build)["build_id"], "split": args.split,
        # what answered the run, copied from the log: this tool queries nothing
        deployed.FIELD: lines[0].get(deployed.FIELD, "not recorded"),
        **({"subset": args.subset, "subset_of": len(all_lines)}
           if args.subset != "all" else {}),
        **report,
        "latency_conditions": ({"warm": True, "passes": 1, "note": MACHINE}
                               if args.warmed_up else {
            "warm": False,
            "note": "the step timings in the log come from one pass with no "
                    "warm-up; they are not latency measurements"}),
        "host": hostinfo.collect(),
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    print(BLOCKS[args.block](report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
