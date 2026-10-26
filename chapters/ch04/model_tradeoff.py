"""Trade bge-small for bge-base once, and say what the swap costs.

The shipped application deploys one embedder, `BAAI/bge-small-en-v1.5`, and
that never changes. This tool answers the model-choice question the chapter
still owes a reader - is a bigger embedder worth its cost - by deploying a
second, temporary copy of `chapters/ch04/app/` with bge-small swapped for
bge-base, measuring it once, and putting the app back exactly as it shipped.

Three things, never in the same run:

    python chapters/ch04/model_tradeoff.py --deploy-base
    python chapters/ch04/model_tradeoff.py --restore
    python chapters/ch04/model_tradeoff.py --block model-tradeoff \\
        --small-eval ... --small-feed ... --small-memory ... \\
        --base-eval ... --base-feed ... --base-memory ... --baseline ...

**`--deploy-base` swaps, it does not add.** `chapters/ch04/models/bge-base.xml`
holds the base component, field and rank profile; they replace the small
model's component, `title_embedding` and `semantic.profile` in a copy under
a temporary directory, not sit beside them - so every number the comparison
measures afterwards is base alone, the same class of number the shipped app's
small numbers are. It deploys the copy and prints, on stderr, the exact feed /
evaluate / memory commands to run against it next.

**`--restore` deploys `app/` as shipped.** `title_embedding` comes back empty
(the redeploy does not reindex the documents already in the index), so a small
re-feed is required before any more numbers are taken against the shipped app -
and that feed's report belongs under `review/`, not `expected/`, because it
measures nothing the chapter reports.

**`--block model-tradeoff` only reads reports**; it deploys nothing. It
refuses if a memory report is not settled, or if the small and base
evaluations disagree on which build or split they measured - either would
make the two rows a comparison of two different things wearing one table.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))

import metrics    # noqa: E402
import feed as feed_tool      # noqa: E402
import memory as memory_tool  # noqa: E402

APP_DIR = Path(__file__).resolve().parent / "app"
MODELS_XML = Path(__file__).resolve().parent / "models" / "bge-base.xml"

SECTION_RE = re.compile(r"<!--\s*(component|field|profile):[^\n]*-->\n")


def load_sections(models_xml: Path) -> dict[str, str]:
    """The three splices `--deploy-base` makes, keyed by what they replace."""
    text = models_xml.read_text()
    parts = SECTION_RE.split(text)
    sections: dict[str, str] = {}
    it = iter(parts[1:])
    for name, content in zip(it, it):
        sections[name] = content.strip() + "\n"
    missing = sorted({"component", "field", "profile"} - set(sections))
    if missing:
        raise SystemExit(f"{models_xml} is missing section(s): {missing}")
    return sections


def extract_braced_block(text: str, marker: str) -> tuple[str, str, str]:
    """Split `text` at the braced block whose line contains `marker`.

    Runs from the start of that line to the matching closing brace, counting
    braces so a block with its own nested `{ }` (every vector field here has
    one, in `attribute { }` and `index { hnsw { } }`) is not cut off at the
    first `}`.
    """
    if marker not in text:
        raise SystemExit(f"{marker!r} not found - is this still app/'s "
                         f"shipped package?")
    start = text.index(marker)
    line_start = text.rfind("\n", 0, start) + 1
    open_brace = text.index("{", start)
    depth, i = 0, open_brace
    while True:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    end = i + 1
    if end < len(text) and text[end] == "\n":
        end += 1
    return text[:line_start], text[line_start:end], text[end:]


def extract_xml_block(text: str, open_tag: str, close_tag: str) -> tuple[str, str, str]:
    """Split `text` at a non-nested XML block, `open_tag ... close_tag`."""
    if open_tag not in text:
        raise SystemExit(f"{open_tag!r} not found - is this still app/'s "
                         f"shipped package?")
    start = text.index(open_tag)
    line_start = text.rfind("\n", 0, start) + 1
    end = text.index(close_tag, start) + len(close_tag)
    if end < len(text) and text[end] == "\n":
        end += 1
    return text[:line_start], text[line_start:end], text[end:]


def patch_services(text: str, component_snippet: str) -> str:
    """Swap the bge-small `embedder` component for `embedder_base`."""
    before, _, after = extract_xml_block(text, '<component id="embedder"',
                                         "</component>")
    return before + component_snippet.rstrip("\n") + "\n" + after


def patch_schema(text: str, field_snippet: str) -> str:
    """Swap the bge-small `title_embedding` field for `title_embedding_base`."""
    before, _, after = extract_braced_block(text, "field title_embedding type")
    return before + field_snippet.rstrip("\n") + "\n" + after


def patch_app(src: Path, dst: Path, models_xml: Path = MODELS_XML) -> None:
    """Copy `src` to `dst` with bge-small swapped for bge-base.

    Swapped, not added beside: every number the comparison measures - feed
    seconds, settled memory, p50 - is base alone this way, comparable to the
    shipped app's small numbers rather than diluted by carrying both.
    """
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    sections = load_sections(models_xml)

    services = dst / "services.xml"
    services.write_text(patch_services(services.read_text(), sections["component"]))

    schema = dst / "schemas" / "product.sd"
    schema.write_text(patch_schema(schema.read_text(), sections["field"]))

    small_profile = dst / "schemas" / "product" / "semantic.profile"
    if small_profile.exists():
        small_profile.unlink()
    (dst / "schemas" / "product" / "semantic_base.profile").write_text(
        sections["profile"])


def model_tradeoff_block(*, small_eval: dict, small_feed: dict, small_memory: dict,
                         base_eval: dict, base_feed: dict, base_memory: dict,
                         baseline: dict) -> str:
    """Small vs base, each against the `bm25_tuned` baseline, one table.

    Refuses rather than printing a number that is not what it claims to be: a
    memory reading taken before the index settled is a different number, not
    a smaller one, and a small/base pair measured on different builds or
    splits is not two rows of one comparison.
    """
    for name, report in (("small-memory", small_memory), ("base-memory", base_memory)):
        if not report.get("settled"):
            raise SystemExit(
                f"{name} is not a settled reading; a number read while the "
                f"index is still moving is a different number, not a "
                f"smaller one. Re-run memory.py with --settle and wait for "
                f"two readings to agree.")
    for field in ("split", "build"):
        a, b = small_eval.get(field), base_eval.get(field)
        if a != b:
            raise SystemExit(
                f"small-eval and base-eval disagree on {field}: {a!r} vs "
                f"{b!r} - they are not two rows of one comparison.")

    ndcg_delta = {
        "small": metrics.bootstrap_delta(baseline["per_query_ndcg10"],
                                         small_eval["per_query_ndcg10"]),
        "base": metrics.bootstrap_delta(baseline["per_query_ndcg10"],
                                        base_eval["per_query_ndcg10"]),
    }
    recall_delta = {
        "small": metrics.bootstrap_delta(baseline["per_query_recall100"],
                                         small_eval["per_query_recall100"]),
        "base": metrics.bootstrap_delta(baseline["per_query_recall100"],
                                        base_eval["per_query_recall100"]),
    }
    rows = [("small", small_eval, small_feed, small_memory),
            ("base", base_eval, base_feed, base_memory)]

    out = ["| model | ndcg@10 | ndcg@10 vs bm25_tuned | recall@100 | recall@100 vs bm25_tuned | "
           "p50 | feed | settled memory |",
           "|---|---|---|---|---|---|---|---|"]
    for name, ev, feed_r, mem_r in rows:
        s = ev["scores"]
        out.append(
            f"| {name} | {metrics.fmt_metric(s['ndcg'].get('@10'))} | "
            f"{metrics.fmt_delta(ndcg_delta[name])} | "
            f"{metrics.fmt_metric(s['recall'].get('@100'))} | "
            f"{metrics.fmt_delta(recall_delta[name])} | "
            f"{metrics.fmt_latency(s.get('latency_ms', {}).get('p50'))} | "
            f"{feed_tool.fmt_duration(feed_r['seconds'])} | "
            f"{memory_tool.fmt_size_mb(mem_r['allocated_bytes'] / 1e6)} |")
    return "\n".join(out) + "\n"


BLOCKS = {"model-tradeoff": model_tradeoff_block}


def deploy_base(wait: int, scratch: Path | None) -> int:
    tmp = Path(scratch) if scratch else Path(tempfile.mkdtemp(prefix="ch04-bge-base-"))
    patch_app(APP_DIR, tmp, MODELS_XML)
    subprocess.run(["vespa", "deploy", "--wait", str(wait), str(tmp)], check=True)
    print(f"deployed the bge-base copy at {tmp}\n", file=sys.stderr)
    print("run next, against this deployment:", file=sys.stderr)
    print("  .venv/bin/python shared/tools/feed.py "
          "builds/esci-us-hard-book-s42-kdd-v4/products.jsonl "
          "--label \"bge-base full feed (comparison, measured once)\" "
          "--out chapters/ch04/expected/feed-base.json "
          "> chapters/ch04/expected/feed-base.block.md", file=sys.stderr)
    print("  .venv/bin/python shared/tools/evaluate.py --split validation "
          "--hits 100 --passes 3 --retriever semantic "
          "--ranking semantic_base --vector-field title_embedding_base "
          "--embedder embedder_base --query-tensor qb "
          "--label validation-semantic-base "
          "--out chapters/ch04/expected/validation-semantic-base.json "
          "> chapters/ch04/expected/validation-semantic-base.block.md",
          file=sys.stderr)
    print("  .venv/bin/python shared/tools/memory.py --settle 600 --rounds 3 "
          "--tolerance 0.01 --dimensions 768 "
          "--label \"bge-base, one vector per title\" "
          "--out chapters/ch04/expected/memory-base.json "
          "> chapters/ch04/expected/memory-base.block.md", file=sys.stderr)
    print("\nthen restore the shipped app:", file=sys.stderr)
    print("  .venv/bin/python chapters/ch04/model_tradeoff.py --restore",
          file=sys.stderr)
    return 0


def restore(wait: int) -> int:
    subprocess.run(["vespa", "deploy", "--wait", str(wait), str(APP_DIR)], check=True)
    print("restored chapters/ch04/app/ as shipped. title_embedding is empty "
          "again (no reindex on restore) - a small re-feed is required "
          "before any more numbers are taken against the shipped app; its "
          "report goes under review/, not expected/, because it measures "
          "nothing the chapter reports:", file=sys.stderr)
    print("  .venv/bin/python shared/tools/feed.py "
          "builds/esci-us-hard-book-s42-kdd-v4/products.jsonl "
          "--label \"small re-feed after the bge-base comparison\" "
          "--out chapters/ch04/review/refeed-small.json", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deploy-base", action="store_true",
                    help="patch a temporary copy of app/ to bge-base and "
                         "deploy it")
    ap.add_argument("--restore", action="store_true",
                    help="deploy app/ as shipped, undoing --deploy-base")
    ap.add_argument("--block", choices=sorted(BLOCKS), default=None,
                    help="print the finished model-tradeoff table; needs the "
                         "six report flags below plus --baseline")
    ap.add_argument("--wait", type=int, default=300,
                    help="seconds `vespa deploy --wait` is given")
    ap.add_argument("--scratch", type=Path, default=None,
                    help="where --deploy-base writes the patched copy; "
                         "default is a fresh directory under the system "
                         "temp directory")
    for flag in ("small-eval", "small-feed", "small-memory",
                "base-eval", "base-feed", "base-memory", "baseline"):
        ap.add_argument(f"--{flag}", type=Path, default=None,
                        help=f"report for --block model-tradeoff's "
                             f"{flag.replace('-', ' ')} row/column")
    args = ap.parse_args()

    chosen = [n for n in ("deploy_base", "restore", "block")
             if getattr(args, n)]
    if len(chosen) != 1:
        raise SystemExit("pass exactly one of --deploy-base, --restore, "
                         "--block model-tradeoff")

    if args.deploy_base:
        return deploy_base(args.wait, args.scratch)
    if args.restore:
        return restore(args.wait)

    wanted = {"small_eval": args.small_eval, "small_feed": args.small_feed,
             "small_memory": args.small_memory, "base_eval": args.base_eval,
             "base_feed": args.base_feed, "base_memory": args.base_memory,
             "baseline": args.baseline}
    missing = [f"--{k.replace('_', '-')}" for k, v in wanted.items() if v is None]
    if missing:
        raise SystemExit(f"--block model-tradeoff needs all six reports plus "
                         f"--baseline; missing: {missing}")
    reports = {k: json.loads(v.read_text()) for k, v in wanted.items()}
    print(BLOCKS[args.block](**reports))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
