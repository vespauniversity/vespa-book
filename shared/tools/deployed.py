"""What is actually deployed, asked of the running system rather than assumed.

Every measurement in this book is taken by sending queries to a container that
is already up. Nothing in that arrangement records *which application* was up,
and that mattered: chapter 4's package in git named an
embedding model the chapter had measured and rejected, while every number in
the chapter came from a run that had rewritten the package before deploying it.
Both facts were true at once and no report held the field that would have shown
it.

Vespa's config server serves the deployed application package back, so the
question has an answer and the answer costs one HTTP request. Reports carry it
from here on, which means a number measured against the wrong model says so on
its face instead of needing an accident to surface it.

**Every embedder, not the first one.** This searched for `<component
id="embedder">` by name, so chapter 4's ColBERT add-on — `<component
id="colbert" type="colbert-embedder">` — was invisible, and the with-ColBERT
and without-ColBERT memory reports carried identical `deployed_embedders`
strings. Two measurements of two different applications that say they were
taken against the same thing are worse than two measurements that say nothing:
the field exists so that a number taken against the wrong model says so on its
face, and it was quietly saying the opposite. A component is an embedder
because of what it *is* — its type — not because of what somebody called it.

**The field is `deployed_embedders`, plural, since 2026-09-14.** It was
`deployed_embedder` while this file reported one, and a name that describes one
thing while the value describes several is how the value stops being read.

**This module owns the name now, and `stamp()` is how a report gets it.** It did
not until 2026-09-14, and the cost of that was exact: the rename reached the
readers and all 38 committed reports and none of the eight writers, because
nothing tied the writers to the name. Every
report written in between carried the old key while the docstring here claimed
the new one. A name typed in eight places is a name that will drift; a test
(`tests/test_tools.py`) now refuses the literal anywhere but here and accepts
the plural key and nothing else, so a caller left behind produces a report
that fails rather than one that quietly disagrees.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET

import requests

CONFIG_SERVER = os.environ.get("VESPA_CONFIG_SERVER", "http://localhost:19071")
_SERVICES = ("/application/v2/tenant/default/application/default"
             "/environment/prod/region/default/instance/default"
             "/content/services.xml")

# `hugging-face-embedder`, `colbert-embedder`, `bert-embedder`,
# `splade-embedder` - Vespa spells every one of them this way, and matching the
# type is what makes a component an embedder here rather than its id.
_MODEL_URL = re.compile(
    r"huggingface\.co/([^/]+/[^/]+)/(?:resolve|raw)/([0-9a-f]{8})")


def parse_embedders(services: str) -> list[tuple[str, str]]:
    """Every embedder in a `services.xml`, as (component id, org/model@revision).

    In declaration order, which is the order the package declares them in and
    not one this tool invents. Raises `ET.ParseError` on something that is not
    XML; a caller that would rather have a word than an exception uses
    `embedder()`.
    """
    root = ET.fromstring(services)
    found: list[tuple[str, str]] = []
    for el in root.iter("component"):
        if "embedder" not in (el.get("type") or ""):
            continue
        # The transformer model specifically, not the first URL in the
        # component: the tokenizer sits beside it and names the same repository
        # at the same revision today, which would make a mismatch between them
        # invisible exactly when it mattered.
        source = ""
        for child in el:
            if child.tag == "transformer-model":
                source = child.get("url") or child.get("model-id") or ""
                break
        m = _MODEL_URL.search(source)
        found.append((el.get("id") or "unnamed",
                      f"{m.group(1)}@{m.group(2)}" if m else "unrecognised"))
    return found


def embedders(config_server: str | None = None) -> list[tuple[str, str]] | None:
    """What the running system says it has deployed, or `None` if it would not say.

    `None` means the question could not be answered - no config server, or an
    answer that is not XML. An empty list means it was answered and there are
    no embedders, which is what chapters 2 and 3 deploy and is not a failure.
    """
    base = (config_server or CONFIG_SERVER).rstrip("/")
    try:
        r = requests.get(base + _SERVICES, timeout=10)
        r.raise_for_status()
        services = r.text
    except requests.RequestException as exc:
        print(f"  warning: could not read the deployed application from {base}"
              f" ({exc.__class__.__name__}); the report will say so",
              file=sys.stderr)
        return None
    try:
        return parse_embedders(services)
    except ET.ParseError as exc:
        print(f"  warning: {base} answered with something that is not an "
              f"application package ({exc}); the report will say so",
              file=sys.stderr)
        return None


def embedder(config_server: str | None = None) -> str:
    """Every embedder deployed, as one line for a report field.

        embedder=BAAI/bge-small-en-v1.5@5c38ec7c
        embedder=BAAI/bge-small-en-v1.5@5c38ec7c, colbert=colbert-ir/colbertv2.0@c1e84128

    Each one carries the id it was declared under, so the two lines above are
    different strings - which is the entire point, and which they were not.
    The id is kept even when there is only one, because a value whose shape
    changes with how many things it describes is a value that has to be parsed
    before it can be compared.

    Returns a string in every case, because a report with the word
    "unreachable" in it can be read six months later and a missing key cannot.
    """
    found = embedders(config_server)
    if found is None:
        return "unreachable"
    if not found:
        return "none declared"
    return ", ".join(f"{name}={model}" for name, model in found)


FIELD = "deployed_embedders"


def stamp(config_server: str | None = None) -> dict:
    """The one line every report carries about what answered it.

    Spread into a report dict with `**deployed.stamp()`. The key is here and
    nowhere else, so renaming it is one edit rather than nine - which is the
    lesson of the rename that reached 38 reports and none of their writers.
    """
    # `embedder()` with no argument, not `embedder(None)`: every caller in
    # this repository calls it that way and the tests replace it with a
    # zero-argument stand-in, so passing one positional argument here would
    # make this helper the only thing that cannot be faked.
    return {FIELD: embedder(config_server) if config_server else embedder()}


def main(argv: list[str] | None = None) -> int:
    """Ask the running system and print the answer, one embedder per line.

    Running this file printed nothing and exited 0 until 2026-09-14 - a module
    with functions and no entry point, documented in two places as the command
    that asks the running system what it loaded.
    **Silence reads as "no embedders."** That happened to be the right reading
    for chapters 2 and 3, which declare none, and it is the wrong reading for
    chapter 4, in exactly the way this module exists to prevent: the chapter
    that shipped declaring a model it had rejected is the reason the field
    exists at all, and a command that says nothing about it is the same
    absence in a different place.

    So the two empty answers are printed as different sentences, because the
    module has always distinguished them and the terminal did not:

        unreachable    nobody answered, or what answered was not an
                       application package. This says nothing about what is
                       deployed.
        none declared  the config server answered and the package it served
                       back has no embedder component. That is chapters 2
                       and 3, and it is not a failure.

    The words are `embedder()`'s, so what a person reads here is what a report
    taken at that moment would carry in `deployed_embedders` - the two being
    different strings is how a wrong number is caught, and they cannot be
    compared if the command prints a third vocabulary.

    Exits non-zero only on `unreachable`. A question that could not be asked is
    not an answer of "none", and exiting 0 on it is the silence again.
    """
    ap = argparse.ArgumentParser(
        description="Every embedder the running system says it deployed.")
    ap.add_argument("--config-server", default=None,
                    help=f"where to ask; default {CONFIG_SERVER}, "
                         f"or $VESPA_CONFIG_SERVER")
    args = ap.parse_args(argv)
    base = (args.config_server or CONFIG_SERVER).rstrip("/")

    found = embedders(args.config_server)
    if found is None:
        print(f"unreachable  {base} did not answer with an application "
              f"package; nothing here says what is deployed")
        return 1
    if not found:
        print(f"none declared  {base} answered, and the package it served "
              f"back declares no embedder")
        return 0
    for name, model in found:
        print(f"{name}={model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
