"""Read a Hugging Face parquet dataset over HTTP without downloading it.

Chapter 2 asks for "streaming a dataset ... without downloading the full
corpus". ESCI on Hugging Face is 2.5 GB of parquet across fifteen shards, and a
corpus build needs twelve of its fourteen columns - five for the judgements,
five for the products, and two that are in both (the product id and the locale). Parquet is columnar and stores a
footer describing where every column chunk lives, so with HTTP range requests a
reader can fetch the footer, decide which byte ranges it wants, and pull only
those — which for the columns we need is a fraction of the file.

No fsspec, no datasets library: a file-like object over HTTP ranges is about
sixty lines and is the thing the chapter is actually about.
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass

import pyarrow.parquet as pq
import requests

REPO = "tasksource/esci"

# Pinned to a commit, not to a branch. `main` is a moving target: the dataset's
# owner can push at any time, every corpus built afterwards would differ, and
# nothing in a build would show that anything had changed. The content hash a
# build reports is only a promise about our own determinism; this is what makes
# it a promise about the data as well.
#
# This commit is from 2023-08-09 and is the head of main as of 2026-09-12.
# Pass --revision to build against something else deliberately.
REVISION = "8113b17a5d4099e20243282c926f1bc1a08a4d13"
_API = "https://huggingface.co/api/datasets/{repo}"
_RESOLVE = "https://huggingface.co/datasets/{repo}/resolve/{rev}/{path}"

RETRIES = 4
BACKOFF = 1.5


@dataclass(frozen=True)
class Shard:
    path: str
    size: int
    split: str
    revision: str = REVISION

    @property
    def url(self) -> str:
        return _RESOLVE.format(repo=REPO, rev=self.revision, path=self.path)


def list_shards(session: requests.Session, split: str | None = None,
                revision: str = REVISION) -> list[Shard]:
    """Every parquet shard in the dataset, optionally filtered to one split.

    Sorted by path so a build is reproducible regardless of API ordering.
    """
    r = session.get(_API.format(repo=REPO), params={"blobs": "true",
                                                    "revision": revision},
                    timeout=30)
    r.raise_for_status()
    shards = []
    for f in r.json().get("siblings", []):
        name = f["rfilename"]
        if not name.endswith(".parquet"):
            continue
        base = name.rsplit("/", 1)[-1]
        s = base.split("-", 1)[0]          # "train-00000-of-00011-....parquet"
        if split and s != split:
            continue
        shards.append(Shard(path=name, size=f.get("size") or 0, split=s,
                            revision=revision))
    return sorted(shards, key=lambda s: s.path)


class HttpRangeFile(io.RawIOBase):
    """A seekable, read-only file over HTTP range requests."""

    def __init__(self, url: str, session: requests.Session, size: int | None = None):
        self._url = url
        self._session = session
        self._pos = 0
        self._size = size if size is not None else self._head_size()

    def _head_size(self) -> int:
        r = self._session.head(self._url, allow_redirects=True, timeout=30)
        r.raise_for_status()
        length = r.headers.get("Content-Length")
        if length is None:
            raise RuntimeError(f"no Content-Length for {self._url}")
        return int(length)

    # -- io.RawIOBase ------------------------------------------------------
    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self._pos = offset
        elif whence == io.SEEK_CUR:
            self._pos += offset
        elif whence == io.SEEK_END:
            self._pos = self._size + offset
        else:
            raise ValueError(f"bad whence {whence}")
        self._pos = max(0, min(self._pos, self._size))
        return self._pos

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = self._size - self._pos
        n = min(n, self._size - self._pos)
        if n <= 0:
            return b""
        data = self._range(self._pos, self._pos + n - 1)
        self._pos += len(data)
        return data

    def readall(self) -> bytes:
        return self.read(-1)

    def readinto(self, b) -> int:
        # BufferedReader drives reads through readinto, and RawIOBase does not
        # supply one. Without this pyarrow fails with a bare NotImplementedError.
        data = self.read(len(b))
        n = len(data)
        b[:n] = data
        return n

    # ----------------------------------------------------------------------
    def _range(self, start: int, end: int) -> bytes:
        headers = {"Range": f"bytes={start}-{end}"}
        last = None
        for attempt in range(RETRIES):
            try:
                r = self._session.get(self._url, headers=headers, timeout=120)
                if r.status_code in (200, 206):
                    return r.content
                if r.status_code in (429, 500, 502, 503, 504):
                    last = RuntimeError(f"HTTP {r.status_code}")
                else:
                    r.raise_for_status()
            except requests.RequestException as exc:
                last = exc
            time.sleep(BACKOFF ** attempt)
        raise RuntimeError(f"range {start}-{end} failed after {RETRIES} tries: {last}")

    @property
    def size(self) -> int:
        return self._size


def open_shard(shard: Shard, session: requests.Session) -> pq.ParquetFile:
    raw = HttpRangeFile(shard.url, session, size=shard.size or None)
    # Parquet reads the footer, then whole column chunks. Buffering keeps the
    # metadata phase from turning into hundreds of tiny requests.
    return pq.ParquetFile(io.BufferedReader(raw, buffer_size=4 << 20))


def iter_batches(shard: Shard, session: requests.Session, columns: list[str],
                 batch_size: int = 65_536):
    """Yield record batches of `columns` only. Other columns are never fetched."""
    pf = open_shard(shard, session)
    yield from pf.iter_batches(batch_size=batch_size, columns=columns)


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "packt-book-project/esci-loader"
    return s
