"""What the index costs in memory and on disk.

Chapter 4's outline asks for recall, latency and memory, and memory is the one
that is usually asserted rather than measured. It is also the one where a
reader can check the arithmetic: documents × dimensions × bytes per cell is
the floor for a vector field, and nothing can make it less. What the arithmetic
does not predict is everything around it - the graph that makes approximate
search possible, and the attribute machinery underneath - and the gap between
the two numbers is the interesting part.

Vespa does not expose memory per field on any endpoint reachable from outside
the container, so this reports the document type as a whole and prints what the
vectors alone should account for. Attributing a number to one field means
measuring with and without it, which costs a second feed.

    python shared/tools/memory.py
    python shared/tools/memory.py --vectors 1 --dimensions 384
    python shared/tools/memory.py --against chapters/ch04/expected/memory.json

**Everything this prints is a cost**, so the blocks are our record of one
machine at one moment rather than something a reader is invited to reproduce:
they would need the container state, the feed, and twenty minutes of waiting
for the index to stop moving. That makes the settled-reading refusal below
*more* load-bearing than it was, not less. A number a reader re-measures is
wrong until the next run; a number frozen into a chapter is wrong for the life
of the chapter, and this book has had to withdraw a published memory figure
that was read before the index had finished settling.

`--against` subtracts another memory report from this reading and prints the
difference. It refuses if either side is unsettled, and it refuses if the two
counted different numbers of documents.

Stdout is the block and nothing else; the progress and the warnings are on
stderr.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import builds    # noqa: E402
import deployed  # noqa: E402

import hostinfo                     # noqa: E402
from query import Vespa             # noqa: E402

WANTED = (
    "content.proton.documentdb.memory_usage.allocated_bytes.last",
    "content.proton.documentdb.disk_usage.last",
    "content.proton.transactionlog.disk_usage.last",
    "cluster-controller.resource_usage.max_memory_utilization.last",
    "cluster-controller.resource_usage.max_disk_utilization.last",
)


def container_name() -> str | None:
    out = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                         capture_output=True, text=True, timeout=10)
    names = [n for n in out.stdout.split() if "vespa" in n]
    return names[0] if names else None


def read_metrics(container: str, doctype: str = "product") -> dict[str, float]:
    """The metrics proxy is only reachable from inside the container.

    Every `content.proton.documentdb.*` metric carries a `documenttype`
    dimension - this container reports one set of readings for `product` and
    a separate, independent set for `user` (16 MB vs 1,851 MB on this build),
    not one number for the index as a whole. A metric with no `documenttype`
    dimension (the cluster-controller utilisation figures) is not per type and
    is always kept, whichever `doctype` was asked for.
    """
    out = subprocess.run(
        ["docker", "exec", container, "curl", "-s", "--max-time", "15",
         "http://localhost:19092/metrics/v2/values"],
        capture_output=True, text=True, timeout=40)
    if out.returncode or not out.stdout.strip():
        raise SystemExit(f"no metrics from {container}")
    payload = json.loads(out.stdout)
    found: dict[str, float] = {}
    for node in payload.get("nodes", []):
        for service in node.get("services", []):
            for metric in service.get("metrics", []):
                dims = metric.get("dimensions", {})
                metric_doctype = dims.get("documenttype")
                if metric_doctype is not None and metric_doctype != doctype:
                    continue
                for key, value in metric.get("values", {}).items():
                    if key in WANTED:
                        found[key] = value
    return found


def predicted_bytes(documents: int, *, vectors: int, dimensions: int,
                    bytes_per_cell: int) -> int:
    """What the vectors alone should account for, by hand.

    Kept as a function rather than an expression inside main() so it can be
    checked: the whole point of this tool is putting a measured number beside a
    predicted one, and a prediction nothing verifies is decoration.
    """
    return documents * vectors * dimensions * bytes_per_cell


ALLOCATED = "content.proton.documentdb.memory_usage.allocated_bytes.last"


def has_settled(first: float, second: float, tolerance: float = 0.01) -> bool:
    """Whether two readings of the same index agree closely enough to believe.

    Vespa keeps working on an index after a feed reports done, and a number
    read before it finishes is not a smaller version of the truth - it is a
    different number. A memory figure in this book was read too early and had
    to be withdrawn from a published chapter once the settled reading
    disagreed with it. So this tool no longer reports a single reading.
    """
    if not first or not second:
        return False
    return abs(second - first) / max(first, second) <= tolerance


def settled_reading(container: str, *, wait: int, tolerance: float, rounds: int = 2,
                    sleep=time.sleep, read=None, doctype: str = "product"
                    ) -> tuple[dict[str, float], bool, list[float]]:
    """Read `rounds` times, `wait` seconds apart, until the last two agree.

    Returns the last reading, whether it settled, and every allocated-bytes
    figure seen - because "not settled" is useless without knowing by how much,
    and the first honest run of this said False after ten minutes with no way
    to tell whether that was 1% or 40%.
    """
    read = read or read_metrics
    seen: list[float] = []
    metrics: dict[str, float] = {}
    for _ in range(max(2, rounds)):
        # Wait before the *first* reading too. A reading taken the instant a
        # feed returns is always the outlier - watched minute by minute, an
        # index sits flat from some minutes on, while the reading taken at
        # zero disagrees with it by more than a per cent. Comparing
        # zero against ten minutes therefore never settled, and the tool kept
        # reporting a disagreement that was an artefact of when it started.
        sleep(wait)
        metrics = read(container, doctype)
        seen.append(metrics.get(ALLOCATED, 0))
        if len(seen) >= 2 and has_settled(seen[-2], seen[-1], tolerance):
            return metrics, True, seen
    return metrics, False, seen


def settle_words(seconds: int) -> str:
    """`ten minutes` for 600, otherwise the interval in plain words - the
    caption must say what the run actually waited, not what it usually does."""
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
             7: "seven", 8: "eight", 9: "nine", 10: "ten", 15: "fifteen",
             20: "twenty", 30: "thirty"}
    if seconds % 60 == 0 and seconds // 60 in words:
        n = seconds // 60
        return f"{words[n]} minute{'s' if n != 1 else ''}"
    if seconds in words:
        return f"{words[seconds]} second{'s' if seconds != 1 else ''}"
    return f"{seconds} seconds"


def fmt_size_mb(megabytes: float) -> str:
    """A size, one way, everywhere: thousands-separated whole megabytes.

    CLAUDE.md's rule 2 - a fact wears more than one form, and changing it means
    listing every place it is written before changing any of them.
    """
    return f"{int(round(megabytes)):,} MB"


def allocated(report: dict) -> float:
    return report["metrics"].get(ALLOCATED, 0)


def memory_block(report: dict) -> str:
    """What one index costs, predicted beside measured.

    The chapter told a reader to run this and then never said what came back.
    The measured half is a settled reading or it says it is not, in the block,
    where it cannot be dropped by an edit to the sentence underneath.
    """
    total = allocated(report)
    raw = report["predicted_vector_bytes"]
    rows = [
        ("the vectors, by hand", fmt_size_mb(raw / 1e6),
         f"{report['documents']:,} x {report['dimensions']} x "
         f"{report['bytes_per_cell']} bytes"),
        ("the index, measured", fmt_size_mb(total / 1e6),
         f"settled: two readings {settle_words(report.get('settle_seconds', 600))} apart agreed"
         if report.get("settled") else "NOT settled - do not quote this"),
        ("everything else", fmt_size_mb((total - raw) / 1e6),
         f"{(total - raw) / raw:.1f}x the vectors" if raw else "—"),
    ]
    out = ["| what | memory | how |", "|---|---|---|"]
    out += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    return "\n".join(out) + "\n"


def memory_delta_block(baseline: dict, current: dict, *, baseline_name: str,
                       current_name: str, baseline_label: str,
                       current_label: str, delta_label: str) -> str:
    """What a second model costs to keep, as the difference between two readings.

    The first attempt at this quoted a difference between two readings taken
    straight after two feeds, and against a settled baseline it came out
    negative. So **both sides must be settled**, and that refusal moves here
    with the arithmetic: Vespa keeps working on an index after a feed reports
    done, and a number read before it finishes is not a smaller version of the
    truth, it is a different number.

    Both sides must also have counted the same documents. A difference between
    two indexes holding different corpora is not the cost of the second model.
    """
    for report, name in ((baseline, baseline_name), (current, current_name)):
        if not report.get("settled"):
            raise SystemExit(
                f"{name} is not a settled reading; a number read while the "
                f"index is still moving is a different number, not a smaller "
                f"one. Re-run with --settle and wait for two readings to agree.")
    if baseline["documents"] != current["documents"]:
        raise SystemExit(
            f"{baseline_name} measured {baseline['documents']:,} documents and "
            f"{current_name} measured {current['documents']:,}; the difference "
            f"between them is not what the second model costs.")

    a, b = baseline["readings_mb"][-1], current["readings_mb"][-1]
    rows = [(baseline_label, a), (current_label, b), (delta_label, b - a)]
    out = [f"  {name:<40} {fmt_size_mb(value):>9}" for name, value in rows]
    return "```\n" + "\n".join(out) + "\n```\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--container", default=None)
    ap.add_argument("--doctype", default="product",
                    help="which proton documentdb's metrics to read - a "
                         "document type is a separate documentdb with its "
                         "own memory/disk figures, not a slice of one "
                         "shared number. Default 'product' so every command "
                         "already published is unchanged; ch10 also reads "
                         "'user'")
    ap.add_argument("--build", type=Path, default=None,
                    help="a corpus build, to stamp the report with; default "
                         "is the most recent")
    ap.add_argument("--against", type=Path, default=None,
                    help="another memory report; with it this prints the "
                         "difference between the two readings instead of this "
                         "one on its own")
    ap.add_argument("--label", default="this reading",
                    help="what this reading is called in the block")
    ap.add_argument("--against-label", default="the earlier reading",
                    help="what the --against reading is called in the block")
    ap.add_argument("--delta-label", default="difference",
                    help="what the difference between them is called. Neutral "
                         "by default; name the two readings for whatever this "
                         "run is comparing, e.g. chapter 4's second vector "
                         "field priced against the first")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--vectors", type=int, default=1,
                    help="vector fields per document")
    ap.add_argument("--dimensions", type=int, default=384)
    ap.add_argument("--bytes-per-cell", type=int, default=4,
                    help="4 for float, 2 for bfloat16, 1 for int8")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    metavar="REPORT",
                    help="print the block from a report this tool already wrote, "
                         "reading nothing from the container (with --against: "
                         "the delta block between the two reports)")
    ap.add_argument("--settle", type=int, default=600,
                    help="seconds between the two readings; 0 to read once and "
                         "say so in the report")
    ap.add_argument("--rounds", type=int, default=3,
                    help="how many readings to take before giving up on the "
                         "index settling")
    ap.add_argument("--tolerance", type=float, default=0.01,
                    help="how close the two readings must be to count as settled")
    args = ap.parse_args()
    if args.from_report:
        report = json.loads(args.from_report.read_text())
        if args.against:
            other = json.loads(args.against.read_text())
            print(memory_delta_block(
                other, report, baseline_name=args.against.name,
                current_name=args.from_report.name, baseline_label=args.against_label,
                current_label=args.label, delta_label=args.delta_label))
        else:
            print(memory_block(report))
        return 0

    container = args.container or container_name()
    if not container:
        raise SystemExit("no running Vespa container found")

    documents = Vespa(args.endpoint).count(args.doctype)
    if args.settle:
        print(f"reading twice, {args.settle}s apart, because a reading taken "
              f"too soon after a feed is a different number rather than a "
              f"smaller one", file=sys.stderr)
        metrics, settled, seen = settled_reading(
            container, wait=args.settle, tolerance=args.tolerance,
            rounds=args.rounds, doctype=args.doctype)
    else:
        metrics, settled, seen = read_metrics(container, args.doctype), False, []

    raw = predicted_bytes(documents, vectors=args.vectors,
                          dimensions=args.dimensions,
                          bytes_per_cell=args.bytes_per_cell)
    total = metrics.get(ALLOCATED, 0)
    if not settled and seen:
        spread = (max(seen) - min(seen)) / max(seen) if max(seen) else 0
        print(f"\n*** NOT settled: readings were "
              f"{', '.join(f'{v/1e6:,.0f} MB' for v in seen)}, a spread of "
              f"{spread:.1%}. Do not quote this. ***", file=sys.stderr)

    # For a person, so stderr: stdout is the block, and the disk rows and the
    # utilisation line are not on the page.
    print(f"document type              {args.doctype:>14}", file=sys.stderr)
    print(f"documents indexed          {documents:>14,}", file=sys.stderr)
    print(f"vectors predicted by hand  {raw/1e6:>14,.0f} MB"
          f"   ({args.vectors} x {args.dimensions} x {args.bytes_per_cell} bytes each)",
          file=sys.stderr)
    print(f"index memory, measured     {total/1e6:>14,.0f} MB", file=sys.stderr)
    if total and raw:
        print(f"everything else            {(total-raw)/1e6:>14,.0f} MB"
              f"   ({(total-raw)/raw:.1f}x the vectors)", file=sys.stderr)
    print(f"disk, documents            "
          f"{metrics.get('content.proton.documentdb.disk_usage.last',0)/1e6:>14,.0f} MB",
          file=sys.stderr)
    print(f"disk, transaction log      "
          f"{metrics.get('content.proton.transactionlog.disk_usage.last',0)/1e6:>14,.0f} MB",
          file=sys.stderr)
    mu = metrics.get("cluster-controller.resource_usage.max_memory_utilization.last")
    du = metrics.get("cluster-controller.resource_usage.max_disk_utilization.last")
    if mu is not None:
        print(f"\nof what the container allows: memory {mu:.1%}, disk {du:.1%}",
              file=sys.stderr)

    build = args.build or builds.latest()
    report = {
        "build": builds.meta(build)["build_id"],
        **deployed.stamp(),
        "doctype": args.doctype,
        "documents": documents,
        "vectors_per_document": args.vectors,
        "dimensions": args.dimensions,
        "bytes_per_cell": args.bytes_per_cell,
        "predicted_vector_bytes": raw,
        # The measured half, named the same way the arithmetic half is named -
        # so a report and its block agree on what "the index costs" means.
        "allocated_bytes": total,
        # Whether two readings ten minutes apart agreed. A report that does not
        # say this cannot be told apart from one taken while the index was
        # still settling, and a published figure in this book was.
        "settled": settled,
        "settle_seconds": args.settle,
        "rounds": args.rounds,
        "tolerance": args.tolerance,
        "readings_mb": [round(v / 1e6) for v in seen],
        "metrics": metrics,
        "host": hostinfo.collect(),
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote {args.out}", file=sys.stderr)

    if args.against:
        other = json.loads(args.against.read_text())
        print(memory_delta_block(
            other, report, baseline_name=args.against.name,
            current_name="this reading", baseline_label=args.against_label,
            current_label=args.label, delta_label=args.delta_label))
    else:
        print(memory_block(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
