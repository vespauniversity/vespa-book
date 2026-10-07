"""Compute the document vectors yourself, instead of letting Vespa do it.

Chapter 4 asks what the difference is between the two. It is not mainly speed.
The container has to run the model once per document either way; what changes is
*where* that happens, what has to be redone when the model changes, and who is
responsible for the two sides agreeing.

**In the application.** The model is part of the application package. Feeding is
simple - send text, get a vector - and the query encoder is guaranteed to be the
same model as the document encoder, because there is only one. Changing the
model means redeploying and re-feeding everything.

**Computed here.** The feed carries the vectors, so the container does no work
per document and feeds much faster. But the query still has to be encoded at
request time by something, and making sure that something is the same model is
now your job. A mismatch produces no error at all - just results that are
quietly wrong - which is the failure this script exists to demonstrate.

The schema difference is the interesting part, and it decides the shape of what
this writes: `title_embedding`, the in-application field, sits outside
`document {}` because Vespa derives it - nothing can feed it directly.
`title_embedding_precomputed` sits inside `document {}` because the feed
supplies it. So this writes **partial updates against that second field**, not
`put`s against the first:

    {"update": "id:us:product::B01N0TQ0OH",
     "fields": {"title_embedding_precomputed": {"assign": {"values": [...]}}}}

which is the form `shared/tools/feed.py` already reads as an `update`
operation.

    python shared/tools/embed_offline.py --limit 1000
    python shared/tools/embed_offline.py --check "wireless headphones"

**`--out` is the report; `--vectors` is the JSONL.** The two used to be one
path doing two jobs (`--capture` was the report under another name, and the
main output doubled as both the feed's input and, read back, evidence of what
the run cost). They are separate now: `--vectors <path>` is what `feed.py`
reads, `--out <path>` is what a chapter cites for seconds, rate, size and
model.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import builds     # noqa: E402
from corpus import LOCALE  # noqa: E402
import hostinfo   # noqa: E402
from evaluate import QUERY_PREFIX  # noqa: E402  (the one definition of the query prefix)
import deployed   # noqa: E402

CACHE = Path(__file__).resolve().parents[2] / "shared" / "cache" / "models"

# The same file, at the same commit, that the application package points at.
# If this drifts from services.xml the two sides stop agreeing and nothing
# says so. Only the pinned embedder remains here (docs/pins.md) - e5 and
# MiniLM were candidates this chapter measured and rejected, and a
# second entry that nothing deploys is a second copy of the "wrong model,
# quietly wrong results" failure this file exists to demonstrate.
MODELS = {
    "bge": {
        "model": "https://huggingface.co/BAAI/bge-small-en-v1.5/resolve/5c38ec7c405ec4b44b94cc5a9bb96e735b38267a/onnx/model.onnx",
        "tokenizer": "https://huggingface.co/BAAI/bge-small-en-v1.5/raw/5c38ec7c405ec4b44b94cc5a9bb96e735b38267a/tokenizer.json",
        "pooling": "cls", "doc_prefix": "",
        # Not a second copy: the string lives in evaluate.QUERY_PREFIX and is
        # referenced here so an offline caller encodes queries the same way.
        "query_prefix": QUERY_PREFIX,
    },
}

_COMMIT_RE = re.compile(r"/(?:resolve|raw)/([0-9a-f]{40})/")


def model_commit(model: str) -> str:
    """The 40-character commit `model`'s files are pinned at."""
    m = _COMMIT_RE.search(MODELS[model]["model"])
    return m.group(1) if m else "unknown"


def fetch(url: str, name: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if not path.exists():
        print(f"  downloading {name}", file=sys.stderr, flush=True)
        urllib.request.urlretrieve(url, path)
    return path


class Encoder:
    def __init__(self, model: str, max_length: int = 128):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        cfg = MODELS[model]
        self.np, self.cfg = np, cfg
        self.tokenizer = Tokenizer.from_file(
            str(fetch(cfg["tokenizer"], f"{model}-tokenizer.json")))
        self.tokenizer.enable_truncation(max_length=max_length)
        self.tokenizer.enable_padding(length=None)
        self.session = ort.InferenceSession(
            str(fetch(cfg["model"], f"{model}-model.onnx")),
            providers=["CPUExecutionProvider"])
        self.inputs = {i.name for i in self.session.get_inputs()}

    def encode(self, texts: list[str], prefix: str = "") -> "list":
        np = self.np
        encoded = self.tokenizer.encode_batch([prefix + t for t in texts])
        ids = np.array([e.ids for e in encoded], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.inputs:
            feed["token_type_ids"] = np.zeros_like(ids)
        out = self.session.run(None, {k: v for k, v in feed.items()
                                      if k in self.inputs})[0]
        if self.cfg["pooling"] == "cls":
            pooled = out[:, 0]
        else:
            m = mask[..., None].astype(out.dtype)
            pooled = (out * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
        norm = np.linalg.norm(pooled, axis=1, keepdims=True)
        return pooled / np.clip(norm, 1e-9, None)


def encode_build(encoder, source: Path, out: Path, *, batch: int = 64,
                 limit: int | None = None, progress_every: int = 5000,
                 report_progress=sys.stderr) -> dict:
    """Encode every title in `source` and write partial updates to `out`.

    Returns what the report needs to say what this run cost: how many
    documents, how long, how big the output is. `source` is a build's
    `products.jsonl` (`put`s); what this writes is `update`s against
    `title_embedding_precomputed` - `title_embedding` sits outside
    `document {}` and nothing can feed it directly.
    """
    started = time.time()
    written = 0
    with source.open() as fh, out.open("w") as sink:
        batch_docs: list[dict] = []

        def flush() -> None:
            nonlocal written
            if not batch_docs:
                return
            vectors = encoder.encode([d["fields"]["title"] for d in batch_docs],
                                     encoder.cfg["doc_prefix"])
            for doc, vector in zip(batch_docs, vectors):
                sink.write(json.dumps({
                    "update": doc["put"],
                    "fields": {"title_embedding_precomputed": {
                        "assign": {"values":
                                   [round(float(x), 6) for x in vector]}}},
                }) + "\n")
            written += len(batch_docs)
            batch_docs.clear()
            if (report_progress and progress_every
                    and written % progress_every < batch):
                rate = written / (time.time() - started)
                print(f"  {written:,} documents | {rate:,.0f}/s",
                     file=report_progress, flush=True)

        for n, line in enumerate(fh):
            if limit and n >= limit:
                break
            batch_docs.append(json.loads(line))
            if len(batch_docs) >= batch:
                flush()
        flush()

    elapsed = time.time() - started
    return {
        "documents": written,
        "seconds": elapsed,
        "bytes_written": out.stat().st_size,
        "bytes_without_vectors": source.stat().st_size,
    }


def find_document_id(app, title: str, *, probe: int = 25) -> str:
    """The id of a product titled exactly `title`, among the top lexical hits.

    `--check` needs one real document's in-application vector to compare
    against, and the title has to match exactly - a substring match would
    compare two different pieces of text and call the difference an error.
    """
    r = app.query("select id, title from product where userQuery()",
                  query=title, hits=probe, ranking="default")
    for h in r.hits:
        if h.fields.get("title") == title:
            # The `id` field is the ASIN, and corpus.py makes it the
            # user-specified part of the document id as it is; the locale is
            # the namespace, which `fetch_attribute` supplies.
            return h.fields.get("id")
    raise SystemExit(
        f"no product titled {title!r} found in the top {probe} lexical hits; "
        f"--check needs an exact title from this corpus")


def fetch_attribute(endpoint: str, product_id: str, field: str,
                    session=None, namespace: str = LOCALE) -> list[float]:
    """One attribute field's value for one document, via the document API.

    `product_id` is the bare ASIN; the namespace is the locale (`corpus.py`
    names a document `id:<locale>:product::<asin>`).

    `title_embedding` sits outside `document {}`, so nothing echoes it in a
    search response the way `evaluate.py` reads `matchfeatures` - no deployed
    rank profile returns the raw query tensor either, and this tool may not
    touch `app/` to add one. The document API reads it when the field is
    named in `fieldSet`: the default field set is the document's own fields
    and leaves a synthetic field out.
    """
    import requests
    session = session or requests.Session()
    url = (f"{endpoint.rstrip('/')}/document/v1/{namespace}/product/docid/"
          f"{product_id}?fieldSet=product:{field}")
    r = session.get(url, timeout=15)
    r.raise_for_status()
    values = r.json().get("fields", {}).get(field, {}).get("values")
    if values is None:
        raise SystemExit(
            f"document {product_id} carries no {field!r} - has the "
            f"container been fed its vectors yet?")
    return values


def compare_vectors(a: list[float], b: list[float]) -> tuple[float, float]:
    """Max absolute difference and cosine similarity between two vectors."""
    import math
    max_abs_diff = max(abs(x - y) for x, y in zip(a, b))
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    cosine = dot / (na * nb) if na and nb else 0.0
    # Plain floats: the offline side arrives as numpy float32, and a float32
    # is not JSON-serialisable - `--check --out` died on exactly that.
    return float(max_abs_diff), float(cosine)


def check_block(result: dict) -> str:
    """Whether the offline vector and the in-application vector agree.

    A difference near zero and a cosine near one are the claim heading 5
    depends on - "the same model, computed twice, agrees" - so this is a
    number, not the two sides' first eight components printed for a person to
    eyeball, which is what this used to be.
    """
    out = ["| measurement | value |", "|---|---|",
          f"| max absolute difference | {result['max_abs_diff']:.6f} |",
          f"| cosine | {result['cosine']:.6f} |"]
    return "\n".join(out) + "\n"


def encode_block(report: dict) -> str:
    """What encoding the corpus outside Vespa cost, as the block on the page.

    A cost (ours, one machine): the reader's machine gives a different number,
    and the block says how many documents and how big the payload was so the
    number has its denominator beside it.
    """
    return "\n".join([
        "| measurement | value |", "|---|---|",
        f"| documents encoded | {report['documents']:,} |",
        f"| seconds | {report['seconds']:.1f} |",
        f"| documents per second | {report['docs_per_second']:,} |",
        f"| payload written | {report['bytes_written'] / 1e6:,.0f} MB |",
    ]) + "\n"


BLOCKS = {"check": check_block, "encode": encode_block}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None)
    # bge, because that is what the application deploys. This defaulted to e5
    # for as long as e5 was the candidate being tried, and a reader who ran
    # this without --model would have fed vectors from one model into an index
    # queried by another. No error, no warning, just worse results - the same
    # failure the chapter spends a section on.
    ap.add_argument("--model", choices=sorted(MODELS), default="bge")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--vectors", type=Path, default=None, metavar="PATH",
                    help="where the JSONL of partial updates goes; default "
                         "is <build>/products_precomputed_bge.jsonl")
    ap.add_argument("--out", type=Path, default=None,
                    help="write what this run cost to a report: seconds, "
                         "docs/s, documents, bytes, model and commit, build, "
                         "host")
    ap.add_argument("--check", metavar="TEXT", default=None,
                    help="encode TEXT offline (document side, no prefix) and "
                         "compare it against the in-application vector for a "
                         "product titled exactly TEXT")
    ap.add_argument("--endpoint", default="http://localhost:8080",
                    help="for --check: where to ask for the in-application "
                         "vector")
    ap.add_argument("--block", choices=sorted(BLOCKS), default=None,
                    help="which finished block goes to stdout; default "
                         "`check` with --check, `encode` otherwise")
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    metavar="REPORT",
                    help="print the block from a report this tool already "
                         "wrote (an encode report or a --check report), "
                         "running no model and asking no container")
    args = ap.parse_args()
    if args.from_report:
        report = json.loads(args.from_report.read_text())
        block = args.block or ("check" if "max_abs_diff" in report else "encode")
        print(BLOCKS[block](report))
        return 0
    if args.block is None:
        args.block = "check" if args.check else "encode"

    encoder = Encoder(args.model)

    if args.check:
        from query import Vespa
        offline = list(encoder.encode([args.check], "")[0])
        app = Vespa(args.endpoint)
        product_id = find_document_id(app, args.check)
        in_app = fetch_attribute(args.endpoint, product_id, "title_embedding")
        max_abs_diff, cosine = compare_vectors(offline, in_app)
        print(f"model {args.model}, document-side prefix "
              f"{encoder.cfg['doc_prefix']!r}", file=sys.stderr)
        print(f"compared against: document API title_embedding for product "
              f"{product_id!r} (no deployed rank profile echoes the query "
              f"tensor, and this tool may not add one)", file=sys.stderr)
        build = args.build or builds.latest()
        report = {
            "build": build.name,
            "model": args.model,
            "model_commit": model_commit(args.model),
            "check_text": args.check,
            "compared_against": f"document API title_embedding for {product_id}",
            "max_abs_diff": round(max_abs_diff, 6),
            "cosine": round(cosine, 6),
            **deployed.stamp(),
            "host": hostinfo.collect(),
        }
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(report, indent=2) + "\n")
            print(f"\nwrote {args.out}", file=sys.stderr)
        print(BLOCKS[args.block](report))
        return 0

    build = args.build or builds.latest()
    source = build / "products.jsonl"
    vectors = args.vectors or build / f"products_precomputed_{args.model}.jsonl"

    stats = encode_build(encoder, source, vectors, batch=args.batch,
                         limit=args.limit)
    rate = stats["documents"] / stats["seconds"] if stats["seconds"] else 0
    print(f"\n{stats['documents']:,} documents in {stats['seconds']:.0f}s "
          f"({rate:,.0f}/s)", file=sys.stderr)
    print(f"wrote {vectors}  ({stats['bytes_written']/1e6:,.0f} MB)",
          file=sys.stderr)
    print("\nThese are partial updates against title_embedding_precomputed, "
          "inside `document {}`; title_embedding, the in-application field, "
          "sits outside it and cannot be fed.", file=sys.stderr)

    report = {
        "source": source.name,
        "build": build.name,
        "model": args.model,
        "model_commit": model_commit(args.model),
        "documents": stats["documents"],
        "seconds": round(stats["seconds"], 1),
        "docs_per_second": round(rate) if rate else None,
        "batch": args.batch,
        "bytes_written": stats["bytes_written"],
        "bytes_without_vectors": stats["bytes_without_vectors"],
        **deployed.stamp(),
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
