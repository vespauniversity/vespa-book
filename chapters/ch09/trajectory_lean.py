"""The shipped copy of a trajectory log: everything but the prompts.

`agent_loop.py` writes, for every turn of a model run, the whole prompt the
model was shown (the tool list or the catalogue description, the question and
the evidence so far - two to twenty thousand characters a turn) and the raw
reply. Over a full set that is about a hundred and fifty megabytes for eight runs,
nearly all of it the same description repeated and evidence that is already
in the steps. The copy this tool writes keeps every field of every line and
every step - the statements, the profiles, the statuses, the ids, the parsed
action, the timings, the answer - and replaces each step's `prompt` by its
length (`prompt_chars`) and sha256 (`prompt_sha256`); a `raw_reply` longer
than `LONG_REPLY` characters (a reply that ran on into whitespace until the
token limit) is replaced the same way (`raw_reply_chars`, `raw_reply_sha256`),
a shorter one is kept. Every tool that scores a log reads neither field, so
the lean copy and the full log give the same blocks, and the same JSON apart
from the host's capture time; the tests hold that.

The full log stays where the run wrote it, under the corpus build
(`builds/<build>/trajectories/`, not in version control); the lean copy goes
under the chapter's `expected/trajectories/` with the same name. A full log
can be made again by running the same command with a model key. A full log
that is not there is skipped with one line on stderr, so the loop over the
eight runs can be run after only some of them.

Usage:
    python chapters/ch10/trajectory_lean.py \\
        builds/<build>/trajectories/llm-tools-alternative-k3.jsonl \\
        --out chapters/ch10/expected/trajectories/llm-tools-alternative-k3.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

LONG_REPLY = 2000
PROMPT = "prompt"
REPLY = "raw_reply"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def lean_step(step: dict) -> dict:
    """One step with its prompt (and an over-long raw reply) replaced by
    length and hash, in the place the text had, every other key as it was."""
    out: dict = {}
    for key, value in step.items():
        if key == PROMPT and isinstance(value, str):
            out["prompt_chars"] = len(value)
            out["prompt_sha256"] = digest(value)
        elif key == REPLY and isinstance(value, str) and len(value) > LONG_REPLY:
            out["raw_reply_chars"] = len(value)
            out["raw_reply_sha256"] = digest(value)
        else:
            out[key] = value
    return out


def lean_line(line: dict) -> dict:
    return {key: ([lean_step(s) for s in value] if key == "steps" else value)
            for key, value in line.items()}


def lean_file(src: Path, dst: Path) -> tuple[int, int]:
    """Write the lean copy; returns (lines, prompt characters dropped)."""
    n = dropped = 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open() as fh, dst.open("w") as out:
        for raw in fh:
            if not raw.strip():
                continue
            line = json.loads(raw)
            for s in line.get("steps", []):
                dropped += len(s.get(PROMPT) or "")
            out.write(json.dumps(lean_line(line), ensure_ascii=False) + "\n")
            n += 1
    return n, dropped


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trajectories", type=Path, help="a full log written by agent_loop.py")
    ap.add_argument("--out", type=Path, required=True, help="where the lean copy goes")
    args = ap.parse_args(argv)
    if args.out.resolve() == args.trajectories.resolve():
        raise SystemExit("--out must not be the full log itself")
    if not args.trajectories.is_file():
        # A reader who made only some of the model runs loops over all of
        # them: a run not made leaves its copy under --out as it was.
        print(f"no full log at {args.trajectories}: {args.out} is left as it is",
              file=sys.stderr)
        return 0
    n, dropped = lean_file(args.trajectories, args.out)
    print(f"wrote {args.out}: {n} lines, {args.trajectories.stat().st_size:,} -> "
          f"{args.out.stat().st_size:,} bytes ({dropped:,} prompt characters replaced "
          "by length and hash)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
