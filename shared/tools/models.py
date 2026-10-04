"""Fetch a pinned model file by URL and commit, and verify it by hash.

`embed_offline.py`'s `MODELS` dict fetches the book's one retrieval embedder.
Nothing fetches the reranker add-ons - chapter 6's cross-encoder ONNX export
has sat in `shared/cache/models/` since it was put there by hand, with no
tool that produced it and
no check that its bytes are the ones the pinned commit serves
(`docs/pins.md`). This is that tool, for the one model chapter 6 needs; a
later chapter's model is a second entry in `MODELS`, not a second file.

    python shared/tools/models.py fetch --model cross --into shared/cache/models
    python shared/tools/models.py --check chapters/ch06/app/models/cross_encoder.onnx

`fetch` skips the download when a file with the pinned sha256 is already at
the destination, and refuses - deleting the partial file - when a download
finishes with the wrong hash. `--check` only verifies a file already on disk;
it downloads nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import requests

# One entry today - chapter 6's cross-encoder. The filename is the underscore
# spelling because Vespa refuses a hyphen in a model file name (the schema
# declares `file: models/cross_encoder.onnx`), which is
# not the name Hugging Face's URL ends in, so the two are recorded separately
# rather than derived from one another.
MODELS = {
    "cross": {
        "url": ("https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2/"
                "resolve/233902d25c440f23af6f7d6e94d2946bac0bee0a/onnx/model.onnx"),
        "filename": "cross_encoder.onnx",
        "sha256": "5d3e70fd0c9ff14b9b5169a51e957b7a9c74897afd0a35ce4bd318150c1d4d4a",
    },
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(model: str, into: Path) -> Path:
    """Download `model` into `into`, skipping it if the pinned hash is
    already there and refusing (exit 2, partial file deleted) if a download
    finishes with the wrong one."""
    spec = MODELS[model]
    into.mkdir(parents=True, exist_ok=True)
    path = into / spec["filename"]
    if path.exists():
        found = sha256_of(path)
        if found == spec["sha256"]:
            print(f"  {path} already has the pinned sha256, not re-downloading",
                 file=sys.stderr)
            return path
        print(f"{path} exists with sha256 {found}, which is not the pinned "
             f"{spec['sha256']} - remove it or point --into elsewhere rather "
             f"than silently overwrite a file that might be there on purpose",
             file=sys.stderr)
        raise SystemExit(2)

    print(f"  downloading {spec['url']}", file=sys.stderr, flush=True)
    tmp = path.with_name(path.name + ".part")
    h = hashlib.sha256()
    try:
        with requests.get(spec["url"], stream=True, timeout=120) as r:
            r.raise_for_status()
            with tmp.open("wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    fh.write(chunk)
                    h.update(chunk)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    found = h.hexdigest()
    if found != spec["sha256"]:
        tmp.unlink(missing_ok=True)
        print(f"downloaded {spec['url']} but sha256 {found} does not match the "
             f"pinned {spec['sha256']} - refusing to keep it; the partial "
             f"file was deleted", file=sys.stderr)
        raise SystemExit(2)
    tmp.rename(path)
    print(f"  wrote {path}, sha256 {found} (matches the pin)", file=sys.stderr)
    return path


def check(path: Path, model: str) -> bool:
    """Verify a file already on disk against the pin. Downloads nothing."""
    spec = MODELS[model]
    if not path.exists():
        print(f"{path} does not exist", file=sys.stderr)
        return False
    found = sha256_of(path)
    ok = found == spec["sha256"]
    print(f"{path}: sha256 {found} "
         f"{'matches' if ok else 'does NOT match'} the pinned "
         f"{spec['sha256']} ({model})", file=sys.stderr)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("fetch",), nargs="?", default=None,
                    help="download a pinned model. Omit this and pass "
                         "--check to only verify a file already on disk")
    ap.add_argument("--model", choices=sorted(MODELS), default="cross")
    ap.add_argument("--into", type=Path, default=None,
                    help="destination directory; required with `fetch`")
    ap.add_argument("--check", type=Path, default=None, metavar="PATH",
                    help="verify PATH's sha256 against the pin and exit; "
                         "no `fetch` needed, and nothing is downloaded")
    args = ap.parse_args()

    if args.check is not None:
        return 0 if check(args.check, args.model) else 1
    if args.command == "fetch":
        if args.into is None:
            ap.error("--into is required with `fetch`")
        fetch(args.model, args.into)
        return 0
    ap.error("pass `fetch --model <name> --into <dir>` to download, or "
             "`--check <path>` to only verify a file already on disk")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
