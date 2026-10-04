"""Compare evaluation runs, and say which differences are real.

A table of NDCG numbers invites the reader to treat every difference as an
improvement. Most are not: with a few hundred queries, a gap of a couple of
points is inside the noise. This resamples the per-query scores to put a
confidence interval on each difference, so the text can say which changes are
worth making and which only look like changes.

    python shared/tools/compare.py chapters/ch04/expected/validation-*.json

**This tool is where most of the book's comparison blocks come from**, so it
says which one it is printing. Nothing renders them from the reports
afterwards: a block is whatever the documented command puts on stdout:

| `--block` | what it is | class |
|---|---|---|
| `evaluations` | one row per run: ndcg, recall, mrr | quality |
| `evaluations-latency` | the same runs' p50 and p95, with the warm note | cost |
| `comparison` | every difference against the baseline, ndcg@10 and recall@100 each with its bracket | quality |
| `prefixes` | the three prefix runs against the right one | quality |
| `headline` | one run on its own, plus its distance from the floor | quality |

The first two are separate blocks because a reader re-running a command
reproduces our ndcg and does **not** reproduce our latency, so the two cannot
share a block that a reader is told to replace. They need not sit together on
the page either.

**This module is `chapters/ch03/compare.py`'s generic half, shared from
chapter 4 on.** `chapters/ch03/compare.py` stays exactly as
published - its README's commands must keep working byte for byte - and keeps
the one block that was always chapter 3's own: `grid`, the k1 x b sweep. Every
chapter after it imports this file instead of writing its own copy.

**`evaluations` re-prints six fields from reports this tool did not write**,
which is the one place the rule that a tool prints what it produces is
strained. It is allowed here and nowhere else, because the alternative is one
block per run, which changes the page and loses the shared header that makes
the rows comparable.

Stdout is the block and nothing else. The running commentary - which files were
skipped, what each run scored, where the report went - is on stderr, because
the swap that puts a block on the page replaces a marked region with stdout
whole.
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import deployed                   # noqa: E402  - for the field name only;
                                  #   this tool reads reports, it asks no system
import hostinfo                   # noqa: E402  - and this one asks the machine,
                                  #   not the container; see the note at `host`
import metrics                    # noqa: E402
from evaluate import WARM_NOTE    # noqa: E402

# The three runs the prefix block reports, in the order the chapter argues
# them: what the model asks for, then the two ways of getting it wrong.
PREFIX_ROWS = (("prefix-correct", "the prefix this model asks for"),
               ("prefix-none", "no prefix at all"),
               ("prefix-wrong", "a prefix from a different model"))


def embedders_of(report: dict):
    """Which embedding models a report was measured against.

    `deployed_embedder` is being renamed `deployed_embedders` - it was always a
    list of components written as one string, and singular was how the ColBERT
    add-on's second component went unrecorded. Both spellings are read, because
    every report committed before the rename carries the old one.
    """
    return report.get("deployed_embedders", report.get("deployed_embedder"))


def named(label: str, display: dict[str, str]) -> str:
    """A run's name as the page writes it, if the command gave it one."""
    return display.get(label, label)


def evaluations_block(runs: dict[str, dict], display: dict[str, str]) -> str:
    """One row per run: the four quality numbers every chapter shows.

    In the order the reports were named on the command line, which is the order
    the chapter argues them in - not sorted by score, because sorting by score
    is how a table starts making a recommendation nobody wrote.
    """
    cols = ("ndcg@10", "recall@10", "recall@100", "mrr")
    out = ["| run | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for label, report in runs.items():
        s = report["scores"]
        cells = [metrics.fmt_metric(s["ndcg"].get("@10")),
                 metrics.fmt_metric(s["recall"].get("@10")),
                 metrics.fmt_metric(s["recall"].get("@100")),
                 metrics.fmt_metric(s.get("mrr"))]
        out.append(f"| {named(label, display)} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def evaluations_latency_block(runs: dict[str, dict],
                              display: dict[str, str]) -> str:
    """What those same runs cost, as a block of its own.

    A cost, so it is our record of one machine at one moment rather than
    something a reader checks us on. The condition is inside the block: five of
    chapter 3's profiles shared one container and their p50 descends with the
    order they ran in, which is an index warming up and was very nearly
    published as a difference between rank profiles.
    """
    out = ["| run | p50 | p95 |", "|---|---|---|"]
    for label, report in runs.items():
        lat = report["scores"].get("latency_ms", {})
        out.append(f"| {named(label, display)} | "
                   f"{metrics.fmt_latency(lat.get('p50'))} | "
                   f"{metrics.fmt_latency(lat.get('p95'))} |")
    return "\n".join(out) + "\n\n" + textwrap.fill(WARM_NOTE, 79) + "\n"


def comparison_block(comparisons: dict[str, dict], recall_comparisons: dict[str, dict],
                     display: dict[str, str]) -> str:
    """Every difference against the baseline, largest ndcg@10 first.

    An earlier draft of chapter 3 carried the same difference twice, with
    digits that disagreed with each other and with the report. Printed by the
    tool, it cannot say two things.

    The verdict is on every row including the real ones. Until 2026-09-14 one
    table said nothing when a difference was real and "inside the noise" when
    it was not, while two others named both, so the *absence* of a phrase
    carried meaning in one place and nothing in another. `metrics.fmt_delta`
    owns that and it is not re-derived here.

    **recall@100 sits beside ndcg@10 now.** A wider net can trade order
    for reach - more fields matched, more candidates found, ranked worse -
    and a table that only showed ndcg@10 could not say so; `main` refuses to
    build `recall_comparisons` from a report that reports recall@100 without
    its per-query figures, and prints a dash for a run that did not measure
    recall@100 at all (a `--hits 10` report).
    """
    if not comparisons:
        return ""
    names = {k: named(k, display) for k in comparisons}
    width = max(len(v) for v in names.values())
    out = []
    # A tie (or a near-tie equal at the printed precision) used to fall
    # back on dict-insertion order, which was `reversed(ordered)` from `main`
    # (descending ndcg@10, itself only broken by command-line order for its
    # own ties) - an order nothing here promises to keep. The comparison
    # label, ascending, is a second key that always exists and never changes
    # between two runs of the same command, so two equal deltas print in the
    # same order every time rather than however the caller happened to order
    # `--baseline`'s siblings on the command line that day.
    for label, d in sorted(comparisons.items(), key=lambda kv: (-kv[1]["delta"], kv[0])):
        r = recall_comparisons.get(label)
        out.append(f"{names[label]:<{width}}   ndcg@10 {metrics.fmt_delta(d)}"
                   f"   recall@100 {metrics.fmt_delta(r)}")
    return "```\n" + "\n".join(out) + "\n```\n"


def prefixes_block(runs: dict[str, dict], comparisons: dict[str, dict],
                   baseline: str) -> str:
    """The three prefix runs, each against the one the model asks for.

    The bracket column is not decoration. Without it this table printed three
    scores that look ordered, the chapter argued from the order, and one of the
    two differences was inside the noise - in a table that matched its report
    perfectly, which is why nothing mechanical could question it.
    """
    missing = [k for k, _ in PREFIX_ROWS if k not in runs]
    if missing:
        raise SystemExit(
            f"the prefix block needs runs labelled {missing}; this command "
            f"loaded {sorted(runs)}. `--label` on evaluate.py is what names a "
            f"run in its report.")
    if baseline != "prefix-correct":
        raise SystemExit(
            f"the prefix block's last column is 'against the right prefix', "
            f"and this comparison is against {baseline!r}. Re-run with "
            f"--baseline prefix-correct.")
    out = ["| run | ndcg@10 | recall@100 | against the right prefix |",
           "|---|---|---|---|"]
    for key, name in PREFIX_ROWS:
        s = runs[key]["scores"]
        ndcg = metrics.fmt_metric(s["ndcg"].get("@10"))
        recall = metrics.fmt_metric(s["recall"].get("@100"))
        if key == baseline:
            ndcg, verdict = f"**{ndcg}**", metrics.NOTHING
        else:
            verdict = metrics.fmt_delta(comparisons.get(key))
        out.append(f"| {name} | {ndcg} | {recall} | {verdict} |")
    return "\n".join(out) + "\n"


def headline_block(runs: dict[str, dict], comparisons: dict[str, dict],
                   baseline: str, label: str) -> str:
    """One run set out on its own, and how far it is from the floor.

    `evaluate.py` prints the first four rows from its own run. The fifth needs
    a second run to compare against, and only this tool has both - so the whole
    block comes from here, under the same latitude `evaluations` has.

    With its bracket. This row was quoting a difference without one, in a
    chapter that spends a section explaining why that turns a finding into a
    coincidence.
    """
    if label not in runs:
        raise SystemExit(f"--headline {label!r} is not one of the runs loaded: "
                         f"{sorted(runs)}")
    if label == baseline:
        raise SystemExit(f"{label!r} is the baseline, so the last row would be "
                         f"its distance from itself. Name the run being "
                         f"reported, not the floor it is measured against.")
    s = runs[label]["scores"]
    rows = [("ndcg@10", f"**{metrics.fmt_metric(s['ndcg'].get('@10'))}**"),
            ("recall@10", metrics.fmt_metric(s["recall"].get("@10"))),
            ("recall@100", metrics.fmt_metric(s["recall"].get("@100"))),
            ("mrr", metrics.fmt_metric(s.get("mrr"))),
            (f"against the {baseline} floor",
             metrics.fmt_delta(comparisons.get(label)))]
    return ("| measurement | value |\n|---|---|\n"
            + "".join(f"| {k} | {v} |\n" for k, v in rows))


BLOCKS = ("evaluations", "evaluations-latency", "comparison", "prefixes",
          "headline")


def render_block(block: str, runs: dict[str, dict], comparisons: dict[str, dict],
           recall_comparisons: dict[str, dict] | None,
           baseline: str, display: dict[str, str], headline: str | None) -> str:
    if block == "evaluations":
        return evaluations_block(runs, display)
    if block == "evaluations-latency":
        return evaluations_latency_block(runs, display)
    if block == "comparison":
        return comparison_block(comparisons, recall_comparisons or {}, display)
    if block == "prefixes":
        return prefixes_block(runs, comparisons, baseline)
    if not headline:
        raise SystemExit(
            f"--block headline needs --headline <label> saying which run is "
            f"being reported. Loaded: {sorted(runs)}, baseline {baseline!r}.")
    return headline_block(runs, comparisons, baseline, headline)


def parse_label(arg: str) -> tuple[str, str]:
    """`--label semantic=vector search` - the run's label, then the page's name.

    Named rather than positional. The natural thing to type is a glob, the glob
    quietly skips whatever is not an evaluation report, and a positional list
    of names would then be attached to the wrong rows with nothing to say so.
    """
    if "=" not in arg:
        raise argparse.ArgumentTypeError(
            f"--label takes <run label>=<name on the page>, not {arg!r}")
    label, _, display = arg.partition("=")
    return label, display


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reports", nargs="+", type=Path)
    ap.add_argument("--baseline", default=None,
                    help="label to compare against; default is the lowest ndcg@10")
    ap.add_argument("--block", choices=BLOCKS, default="comparison",
                    help="which finished block goes to stdout; one per run, "
                         "because a swap replaces a marked region with stdout "
                         "whole and two blocks in one stream cannot be told "
                         "apart")
    ap.add_argument("--headline", default=None,
                    help="for --block headline: which run is being reported")
    ap.add_argument("--label", action="append", type=parse_label, default=[],
                    metavar="LABEL=NAME",
                    help="rename a run for the page, e.g. "
                         "--label semantic='vector search'. Repeatable")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    display = dict(args.label)

    # The natural thing to type is a glob over the expected/ directory, which
    # also matches the comparison and analysis files this tool writes. Skip
    # anything that is not an evaluation report rather than failing on a
    # KeyError three frames deep.
    runs, skipped = {}, []
    for path in args.reports:
        r = json.loads(path.read_text())
        if not {"label", "scores", "per_query_ndcg10"} <= r.keys():
            skipped.append(path.name)
            continue
        runs[r["label"]] = r

    if skipped:
        print(f"not evaluation reports, skipped: {', '.join(sorted(skipped))}\n",
              file=sys.stderr)
    if not runs:
        print("no evaluation reports among the files given. Produce one with:\n"
              "  python shared/tools/evaluate.py --build <build> --split validation "
              "--ranking bm25_tuned --out report.json", file=sys.stderr)
        return 1

    if len(runs) < 2:
        print(f"only one run ({next(iter(runs))}); nothing to compare against.",
              file=sys.stderr)

    # ndcg@10, then the run's own label ascending - a stable secondary
    # key so two runs tied (or equal at the printed three decimals) sort the
    # same way on every invocation instead of falling back on Python's
    # sort-stability over whatever order `runs` happened to be built in.
    ordered = sorted(runs, key=lambda k: (runs[k]["scores"]["ndcg"]["@10"], k))
    baseline = args.baseline or ordered[0]
    if baseline not in runs:
        raise SystemExit(f"--baseline {baseline!r} is not one of the runs "
                         f"loaded: {sorted(runs)}")

    unknown = sorted(set(display) - set(runs))
    if unknown:
        raise SystemExit(f"--label names runs that were not loaded: {unknown}. "
                         f"Loaded: {sorted(runs)}")

    # Everything from here to the block is for a person, so it is on stderr.
    print(f"{'profile':16} {'ndcg@10':>8} {'recall@10':>10} {'recall@100':>11} "
          f"{'mrr':>7} {'p50':>8} {'p95':>8}", file=sys.stderr)
    print("-" * 74, file=sys.stderr)
    for label in reversed(ordered):
        s = runs[label]["scores"]
        lat = s.get("latency_ms", {})
        print(f"{label:16} {metrics.fmt_metric(s['ndcg']['@10']):>8} "
              f"{metrics.fmt_metric(s['recall']['@10']):>10} "
              f"{metrics.fmt_metric(s['recall'].get('@100')):>11} "
              f"{metrics.fmt_metric(s['mrr']):>7} "
              f"{metrics.fmt_latency(lat.get('p50')):>8} "
              f"{metrics.fmt_latency(lat.get('p95')):>8}", file=sys.stderr)

    print(f"\nndcg@10 against `{baseline}`, 95% interval over 2000 resamples "
          f"of the per-query scores:\n", file=sys.stderr)
    comparisons = {}
    base_scores = runs[baseline]["per_query_ndcg10"]
    for label in reversed(ordered):
        if label == baseline:
            continue
        d = metrics.bootstrap_delta(base_scores, runs[label]["per_query_ndcg10"])
        comparisons[label] = d
        print(f"  {label:16} {metrics.fmt_delta(d)}", file=sys.stderr)

    # The `comparison` block's recall@100 bracket needs a run's
    # `per_query_recall100`. Until ch07 a report without it was refused,
    # because the only way to lack it was to be an older report. A report
    # measured with `--hits 10` (ch07's global-phase profiles, whose
    # match-features are computed per returned hit) has no recall@100 *by
    # construction* - a global phase over ten documents cannot change which
    # documents are in the hundred - so its row prints a dash for the recall
    # bracket, named on stderr, and the ndcg@10 bracket stands. A report that
    # still carries `scores.recall.@100` but no per-query figures is the old
    # case and is still refused: that number was measured and its bracket
    # is missing, which is different from a number nobody measured.
    recall_comparisons = None
    if args.block == "comparison":
        stale = sorted(label for label in runs
                       if "per_query_recall100" not in runs[label]
                       and runs[label]["scores"]["recall"].get("@100") is not None)
        if stale:
            raise SystemExit(
                f"the comparison block's recall@100 bracket needs "
                f"`per_query_recall100` in every report that reports "
                f"recall@100; missing from: {stale}. That field comes from "
                f"the current `evaluate.py` - regenerate any older report "
                f"before comparing it.")
        not_measured = sorted(label for label in runs
                              if "per_query_recall100" not in runs[label])
        if not_measured:
            print(f"recall@100 not measured (hits below 100) for: "
                  f"{not_measured} - their recall@100 bracket prints as a "
                  "dash", file=sys.stderr)
        recall_comparisons = {}
        base_recall = runs[baseline].get("per_query_recall100")
        for label in reversed(ordered):
            if label == baseline:
                continue
            theirs = runs[label].get("per_query_recall100")
            if base_recall is None or theirs is None:
                recall_comparisons[label] = None
                continue
            recall_comparisons[label] = metrics.bootstrap_delta(base_recall, theirs)

    # Which embedding model each run was measured against. When the runs
    # disagree it is either the comparison's whole point (chapter 4's bge-base
    # against bge-small) or a mistake (a lexical baseline measured on one
    # container, a semantic run on another) - the tool cannot tell which, so it
    # says what it saw, on stderr, and lets the person decide. It used to
    # print "*** these runs are not comparable ***", which read as refusing
    # the one table that exists to compare two embedders.
    embedders = sorted({e for e in (embedders_of(r) for r in runs.values()) if e})
    if len(embedders) > 1:
        print(f"\nnote: these runs were measured against different embedders - "
              f"{embedders}. Fine if that is what you are comparing (a model "
              f"choice); a mistake if both runs should have seen the same index.",
              file=sys.stderr)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({
            "baseline": baseline,
            "split": runs[baseline]["split"],
            "build": runs[baseline]["build"],
            deployed.FIELD: (embedders[0] if len(embedders) == 1
                             else embedders or None),
            # **The machine that did the comparing, and when.** Not the
            # machine the runs were measured on - each run's own report holds
            # that, and this tool may be run anywhere against reports taken
            # anywhere.
            "host": hostinfo.collect(),
            "runs": {k: v["scores"] for k, v in runs.items()},
            "ndcg10_vs_baseline": comparisons,
            # The recall@100 bracket the `comparison` block prints, kept
            # in the report too (it was once stdout-only, so every
            # recall verdict a chapter quoted had no report behind it).
            "recall100_vs_baseline": recall_comparisons,
        }, indent=2) + "\n")
        print(f"\nwrote {args.out}", file=sys.stderr)

    # The block goes to stdout on its own, so it can be piped, diffed or lifted
    # into the page.
    print(render_block(args.block, runs, comparisons, recall_comparisons,
                       baseline, display, args.headline))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
