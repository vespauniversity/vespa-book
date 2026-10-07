"""Feed documents to Vespa over the document API, with retries and progress.

Chapter 2 asks for "feeding documents with retry, batching, and progress
reporting". Vespa's CLI can feed a file in one command and is the right tool
in production, but the point here is that the reader sees what feeding actually
involves: an operation per document, a response to check, transient failures
that should be retried and permanent ones that should not, and enough
throughput that a hundred thousand documents is not an afternoon.

The input is the JSONL a corpus build produces:

    {"put":    "id:us:product::B01N0TQ0OH", "fields": {...}}
    {"update": "id:us:product::B01N0TQ0OH", "fields": {"popularity": {"assign": 3}}}

(namespace `us`, the locale; document type `product`; the user-specified part
is the bare ASIN, the same value as the document's `id` field).

A `put` replaces the document; an `update` changes named fields and leaves the
rest alone, which is how a later chapter fills a field after the feed without
reindexing the text.

**What this prints is a cost**, and one row of it: how long this feed took and
how fast it went. It is our record of one machine at one moment - four CPUs
given to the container runtime's VM, no GPU, the host in the report - and not
something a reader is asked to reproduce, because their machine decides the
answer.

**One row, and no joiner.** The chapter used to show two or three feeds side by
side in one table, and no single command can print that: no tool owns both
runs. The comparison between them is a sentence, and it is written as prose
with each feed's own row beside it. Do not build a mode that reads another feed
report - that is the dependency the design is removing, not a gap in it.

Everything a person reads goes to stderr; stdout is the block.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).parent))

import builds  # noqa: E402

RETRYABLE = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 5
BACKOFF = 0.5


@dataclass
class Result:
    ok: int = 0
    failed: int = 0
    retried: int = 0
    seconds: float = 0.0
    # The batch size actually used, after `feed_file` applies its default
    # (`concurrency * 8`). q06's gap: a report wrote `concurrency` and nothing
    # about batching, so a feed run with a hand-picked batch size and one run
    # on the default looked identical in the file. Set once, inside
    # `feed_file`, so a caller never has to redo that arithmetic to report it.
    batch_size: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.ok / self.seconds if self.seconds else 0.0

    def summary(self) -> str:
        s = (f"{self.ok:,} ok, {self.failed:,} failed, {self.retried:,} retried "
             f"in {self.seconds:.1f}s ({self.rate:,.0f} docs/s)")
        if self.errors:
            s += "\nfirst errors:\n  " + "\n  ".join(self.errors[:5])
        return s


def parse_document_id(doc_id: str) -> tuple[str, str, str]:
    """'id:us:product::B01N0TQ0OH' -> namespace, doctype, user id."""
    parts = doc_id.split(":")
    if len(parts) < 5 or parts[0] != "id":
        raise ValueError(f"not a Vespa document id: {doc_id!r}")
    return parts[1], parts[2], ":".join(parts[4:])


def _endpoint(base: str, doc_id: str) -> str:
    # The local part of the id is a path segment, so it is percent-encoded
    # whole: a `#` (a real brand name starts with one) or a `?` or `/` in an
    # id would otherwise end the URL early and the request would land on the
    # collection root instead of the document.
    ns, doctype, user = parse_document_id(doc_id)
    return f"{base.rstrip('/')}/document/v1/{ns}/{doctype}/docid/{quote(user, safe='')}"


def _send(session: requests.Session, url: str, method: str, body: dict,
          result: Result, lock: threading.Lock) -> None:
    for attempt in range(MAX_ATTEMPTS):
        try:
            r = session.request(method, url, json=body, timeout=60)
            if r.status_code < 300:
                with lock:
                    result.ok += 1
                return
            if r.status_code not in RETRYABLE:
                with lock:
                    result.failed += 1
                    result.errors.append(f"{r.status_code} {url} {r.text[:160]}")
                return
            detail = f"HTTP {r.status_code}"
        except requests.RequestException as exc:
            detail = f"{type(exc).__name__}: {exc}"
        with lock:
            result.retried += 1
        if attempt == MAX_ATTEMPTS - 1:
            with lock:
                result.failed += 1
                result.errors.append(f"gave up on {url}: {detail}")
            return
        # Back off, because hammering a saturated cluster is how a slow feed
        # becomes a failed one.
        time.sleep(BACKOFF * (2 ** attempt))


def _operations(path: Path, endpoint: str, limit: int | None):
    """Yield (url, method, body) for each line of a feed file."""
    with path.open() as fh:
        for n, line in enumerate(fh):
            if limit and n >= limit:
                return
            line = line.strip()
            if not line:
                continue
            op = json.loads(line)
            if "put" in op:
                yield _endpoint(endpoint, op["put"]), "POST", {"fields": op["fields"]}
            elif "update" in op:
                yield _endpoint(endpoint, op["update"]), "PUT", {"fields": op["fields"]}
            else:
                raise ValueError(f"neither put nor update: {line[:80]}")


def feed_file(path: Path, endpoint: str = "http://localhost:8080",
              concurrency: int = 16, batch_size: int = 0,
              progress_every: int = 20_000,
              limit: int | None = None, out=sys.stderr) -> Result:
    result = Result()
    lock = threading.Lock()
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=concurrency,
                                            pool_maxsize=concurrency)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Feed in batches rather than queueing every operation at once. Submitting
    # a hundred thousand futures holds every request body in memory and makes
    # progress meaningless - the submitted count races ahead of what the
    # cluster has actually acknowledged. A batch is sent, waited for, reported,
    # and only then is the next one built.
    batch_size = batch_size or concurrency * 8
    result.batch_size = batch_size
    started = time.time()
    batch: list[tuple[str, str, dict]] = []

    def flush(pool: ThreadPoolExecutor) -> None:
        futures = [pool.submit(_send, session, url, method, body, result, lock)
                   for url, method, body in batch]
        for f in futures:
            f.result()
        batch.clear()

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for op in _operations(path, endpoint, limit):
            batch.append(op)
            if len(batch) >= batch_size:
                flush(pool)
                done = result.ok + result.failed
                if progress_every and done % progress_every < batch_size:
                    elapsed = time.time() - started
                    print(f"  {done:,} acknowledged | {done / elapsed:,.0f} docs/s",
                          file=out, flush=True)
        if batch:
            flush(pool)

    result.seconds = time.time() - started
    return result


def fmt_duration(seconds: float) -> str:
    """A duration: one decimal below a minute, `Xm YYs` at and above it.

    CLAUDE.md's rule 2. `8m 02s` at and above 60 s did not change: truncation,
    because that is what eight of the nine existing spellings say, and a whole
    second is under 1% of a multi-minute feed. Below 60 s this used to
    truncate the same way, and that is where it cost something: a short feed's
    row read something like "4s" beside a rate of "495 docs/s", and the two do
    not multiply back to the document count - truncating 4.04s to "4s" throws
    away a fraction that is 1% of a feed but the report's own field for
    `seconds` still carries. One decimal below 60 s keeps the row honest at
    the size where a whole second is not noise.
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    whole = int(seconds)
    return f"{whole // 60}m {whole % 60:02d}s"


def fmt_rate(docs_per_second: float) -> str:
    """A rate, one way: `208 docs/s`."""
    return f"{int(round(docs_per_second)):,} docs/s"


def feed_block(result: Result, label: str) -> str:
    """This feed, as the finished row that goes on the page.

    One row. The table it goes into may have another feed's row beside it, and
    that row comes from that feed's own run - nothing here reads a second
    report, because a block joining two runs is a block no single command can
    print.
    """
    return ("| label | feed | rate |\n|---|---|---|\n"
            f"| {label} | {fmt_duration(result.seconds)} | "
            f"{fmt_rate(result.rate)} |\n")


def feed_block_from_report(saved: dict) -> str:
    """The same one-row block as `feed_block`, built from a report this tool
    already wrote instead of a live `Result`.

    The report's own `docs_per_second` was computed at measurement time from
    the *unrounded* elapsed seconds; `seconds` in the same report is already
    rounded to one decimal for display, so rebuilding a `Result` and reading
    `.rate` back off it would silently recompute a slightly different rate
    from the rounded figure. Reading the report's stored rate directly
    reprints exactly what the original run's own block said, not a close
    recomputation of it.
    """
    label = saved.get("label", "this feed")
    return ("| label | feed | rate |\n|---|---|---|\n"
            f"| {label} | {fmt_duration(saved['seconds'])} | "
            f"{fmt_rate(saved['docs_per_second'])} |\n")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Feed a corpus build into Vespa.")
    ap.add_argument("file", type=Path, nargs="?", default=None,
                    help="a build's products.jsonl; default is the most recent "
                         "build. `builds/*/products.jsonl` is not a safe way to "
                         "say that - it takes one file, and the glob only "
                         "resolves while exactly one build exists")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--batch-size", type=int, default=0,
                    help="operations sent before waiting; default concurrency x 8")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", type=Path, default=None,
                    help="capture the feed rate to a report. Chapters quote it, "
                         "so it has to come from a run rather than from memory")
    ap.add_argument("--label", default=None,
                    help="what this feed is called in the block; default is the "
                         "file that was fed")
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    metavar="REPORT",
                    help="print this run's own block again from the report "
                         "it already wrote, feeding nothing a second time - "
                         "not a joiner: it takes exactly one report, its own")
    args = ap.parse_args()

    if args.from_report:
        saved = json.loads(args.from_report.read_text())
        print(feed_block_from_report(saved))
        return 0

    if args.file:
        path = args.file
    else:
        path = builds.latest() / "products.jsonl"
    print(f"feeding {path}", file=sys.stderr)
    result = feed_file(path, args.endpoint, args.concurrency,
                       batch_size=args.batch_size, limit=args.limit)
    print(result.summary(), file=sys.stderr)
    label = args.label or path.name

    if args.out:
        import deployed
        import hostinfo
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({
            "source": path.name,
            "build": path.parent.name,
            # What answered, asked of the running system rather than assumed.
            # This report said which file went in and how fast, and nothing
            # about the application it went into - so a feed into chapter 4's
            # package and a feed into chapter 3's produced the same report,
            # and the rate is not the same rate: one of them runs every
            # document through an embedding model on the way in. `stamp()`
            # owns the key; nothing here spells it.
            **deployed.stamp(),
            "documents": result.ok,
            "failed": result.failed,
            "retried": result.retried,
            "seconds": round(result.seconds, 1),
            "docs_per_second": round(result.ok / result.seconds) if result.seconds else None,
            "concurrency": args.concurrency,
            # a gap the Phase-1 feed-method check found: these three were
            # each a flag that changed what ran without changing what the
            # report said, so a partial feed (`--limit`) and a full one could
            # write identical-looking reports apart from a smaller `documents`
            # count - nothing said whether that was deliberate or a failure.
            # `batch_size` is the effective value (`feed_file`'s default
            # applied), not the raw flag, so the field means the same thing
            # whether or not `--batch-size` was passed.
            "batch_size": result.batch_size,
            "limit": args.limit,
            "label": label,
            "host": hostinfo.collect(),
        }, indent=2) + "\n")
        print(f"wrote {args.out}", file=sys.stderr)

    # The block goes to stdout on its own. This command printed everything to
    # stderr and nothing here, so a rerun of the chapter had nothing to lift.
    print(feed_block(result, label))
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
