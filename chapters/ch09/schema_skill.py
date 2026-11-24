"""The agent's description of the catalogue, generated from the deployed
package, plus one paragraph its owner may add.

An agent that writes the engine's query language itself needs to know what
there is to query: the fields and how each one matches, the rank profiles and
what each ranks by, and what a statement looks like. Nothing in the generated
part is written by hand. The schema file and the rank-profile files of the
application package are read, and the description is whatever they say, so a
package with more fields or more profiles gives a longer description with no
change to this file or to the agent.

What the description holds, in order:

    the document type and its fields - type, index or attribute, how it
        matches (`word` or text), the vector fields and which profiles
        read them; fields the rerankers read and a query cannot use are
        marked "not for queries"
    the fieldset `default` - what `userQuery()` searches when no field is
        named
    every rank profile by name, or those `--profiles` names - its phases'
        expressions, the query inputs a request has to carry, and, when it is
        at most 72 characters, the first sentence of the comment the profile
        opens with
    query shapes - YQL statements the earlier chapters sent, with the request
        parameters each one needs

`--profiles NAME[,NAME…]` lists only the rank profiles named, so the
description offers an agent the rankings the catalogue's owner chooses rather
than every profile the package carries; a vector field then names only the
listed profiles that read it, and only the query tensors they need are shown.
Without it every profile is listed.

`--note TEXT` adds one paragraph after the rank-profile list, under the line
"What this catalogue's own measurements say:", the text as given; without it
the description is what the package and `--profiles` give.

`--statement-labels {chapters,none}` says whether each example statement
carries, in parentheses, the chapter it is from (`chapters`, the default) or
no label (`none`); with `none` the line before them reads "Example
statements, ..." rather than "Statements earlier chapters sent, ...", so the
text names no chapter, for a reader who has not the book in hand (the demo
kit's copy). The statements, their order and their numbers, and the rest of
the text, are the same either way.

The text is what the model is shown on every turn, so it is kept short: the
length is printed on stderr and should stay under the cap. The same package
with the same flags gives the same text, byte for byte.

Usage (the first is the chapter's command; `chapters/ch10/COMMANDS.md` has
its `--note` text in full; the second is the demo kit's copy, whose command,
with its `--note` in full, is in `chapters/ch10/demo/README.md`; the others
write every profile, or no note):
    python chapters/ch10/schema_skill.py --app chapters/ch10/app --profiles hybrid_rrf,bm25_tuned,semantic --note "..." --out chapters/ch10/expected/skill.md
    python chapters/ch10/schema_skill.py --app chapters/ch10/app --profiles hybrid_rrf,bm25_tuned,semantic --statement-labels none --note "..." --out chapters/ch10/demo/skill.md
    python chapters/ch10/schema_skill.py --app chapters/ch10/app --profiles hybrid_rrf,bm25_tuned,semantic --out skill.md
    python chapters/ch10/schema_skill.py --app chapters/ch10/app --note "..." --out skill.md
    python chapters/ch10/schema_skill.py --app chapters/ch10/app > skill.md
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))
import evaluate   # noqa: E402  (the query prefix lives there and nowhere else)

LENGTH_CAP = 6000
EXPRESSION_WIDTH = 110
NOTE_HEADING = "What this catalogue's own measurements say:"
NO_READER = "read by no profile"
NO_LISTED_READER = "read by no profile listed here"   # when --profiles leaves some out
GLOSS_WIDTH = 72
STATEMENTS_HEADING = {   # by --statement-labels
    "chapters": "Statements earlier chapters sent, with the request parameters each needs:",
    "none": "Example statements, with the request parameters each needs:",
}
STATEMENT_LABELS = tuple(STATEMENTS_HEADING)

# How a request writes the three query tensors the profiles read, as the
# earlier chapters' commands wrote them: chapter 4 the title vector, chapter 6
# the late-interaction and cross-encoder inputs.
QUERY_TENSORS = {
    "q": 'embed(embedder, "{prefix}<words>")',
    "qt": 'embed(colbert, "<words>")',
    "qt_cross": 'embed(tokenizer, "<words>")',
}

# Statements the earlier chapters sent, as their tools and commands sent them.
# (purpose, statement, the request parameters it needs, where it is from)
EXAMPLES = [
    ("Keyword search over the fieldset `default`",
     "select id, title from product where userQuery()",
     "query=<words>", "chapter 2"),
    ("Nearest neighbours of the query vector; totalTargetHits is how many "
     "nearest neighbours it asks for in total across the content nodes; "
     "at least a hundred",
     "select id from product where {totalTargetHits:100}nearestNeighbor(title_embedding, q)",
     "input.query(q)", "chapter 4"),
    ("Both arms in one request, for a hybrid profile",
     "select id, title, snippet from product where userQuery() or "
     "({totalTargetHits:100}nearestNeighbor(title_embedding, q))",
     "query, input.query(q)", "chapter 5"),
    ("A condition ANDed onto the union, which goes in parentheses",
     "select id, title from product where (userQuery() or "
     "({totalTargetHits:100}nearestNeighbor(title_embedding, q))) and has_description = true",
     "query, input.query(q)", "chapter 5"),
    ("A text match on one field",
     'select id, title from product where (userQuery()) and tenant_id contains "nike"',
     "query", "chapter 8"),
    ("Set membership on an attribute",
     'select id, title from product where (userQuery()) and tenant_id in ("nike", "adidas")',
     "query", "chapter 8"),
    ("One count per value of a field, after `|`",
     "select id, title, brand from product where userQuery() "
     "| all(group(brand) max(20) each(output(count())))",
     "query", "this chapter's grouping tool"),
]


# ---------------------------------------------------------------- parsing

@dataclass
class Block:
    header: str
    lines: list[str] = field(default_factory=list)
    children: list["Block"] = field(default_factory=list)

    def child(self, prefix: str) -> "Block | None":
        return next((c for c in self.children if c.header == prefix
                     or c.header.startswith(prefix + " ")), None)

    def kids(self, prefix: str) -> list["Block"]:
        return [c for c in self.children if c.header == prefix
                or c.header.startswith(prefix + " ")]


ONE_LINE_BLOCK = re.compile(r"^([^:{}]+?)\s*\{\s*(.*?)\s*\}\s*$")


def strip_comment(line: str) -> str:
    return line.split("#", 1)[0].rstrip()


def parse(text: str) -> Block:
    """The brace structure of a schema or profile file, comments dropped."""
    root = Block("")
    stack = [root]
    for raw in text.splitlines():
        line = strip_comment(raw).strip()
        if not line:
            continue
        if line == "}":
            stack.pop()
        elif line.endswith("{"):
            block = Block(line[:-1].strip())
            stack[-1].children.append(block)
            stack.append(block)
        elif (m := ONE_LINE_BLOCK.match(line)):
            block = Block(m.group(1).strip())
            if m.group(2):
                block.lines.append(m.group(2))
            stack[-1].children.append(block)
        else:
            stack[-1].lines.append(line)
    return root


def first_comment(text: str) -> str:
    """The first sentence of the comment block a profile opens with, or ""."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip().startswith("rank-profile")), None)
    if start is None:
        return ""
    collected: list[str] = []
    for line in lines[start + 1:]:
        s = line.strip()
        if s.startswith("#"):
            collected.append(s.lstrip("#").strip())
        elif s:
            break
    para = " ".join(x for x in collected if x)
    sentence = " ".join(re.split(r"(?<=[.!?])\s", para, 1)[0].split()) if para else ""
    return sentence if len(sentence) <= GLOSS_WIDTH else ""


def shorten(text: str, width: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[:width - 1].rstrip() + "…"


# ----------------------------------------------------------------- fields

@dataclass
class Field:
    name: str
    type: str
    indexing: str = ""
    index: list[str] = field(default_factory=list)
    attribute: list[str] = field(default_factory=list)
    match: list[str] = field(default_factory=list)
    rank: str = ""

    @property
    def is_index(self) -> bool:
        return "index" in self.indexing.split("|") or "index" in self.indexing

    @property
    def is_attribute(self) -> bool:
        return "attribute" in self.indexing

    @property
    def is_tensor(self) -> bool:
        return self.type.startswith("tensor")


def read_field(block: Block) -> Field:
    m = re.match(r"field\s+(\w+)\s+type\s+(.+)$", block.header)
    f = Field(name=m.group(1), type=m.group(2).strip())
    for line in block.lines:
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "indexing":
            f.indexing = " ".join(value.split())
        elif key == "index":
            f.index.append(value)
        elif key == "match":
            f.match.append(value)
        elif key == "rank":
            f.rank = value
    for child in block.children:
        if child.header == "index":
            f.index += child.lines + [c.header for c in child.children]
        elif child.header == "attribute":
            f.attribute += child.lines
        elif child.header == "match":
            f.match += child.lines
    return f


def read_schema(text: str) -> tuple[str, list[Field], list[str]]:
    """(document type, fields in file order, the fieldset `default`)."""
    root = parse(text)
    schema = next(c for c in root.children if c.header.startswith("schema "))
    doctype = schema.header.split()[1]
    fields: list[Field] = []
    document = schema.child("document")
    for block in (document.kids("field") if document else []) + schema.kids("field"):
        fields.append(read_field(block))
    fieldset = schema.child("fieldset default")
    names: list[str] = []
    for line in (fieldset.lines if fieldset else []):
        if line.startswith("fields:"):
            names = [x.strip() for x in line.partition(":")[2].split(",") if x.strip()]
    return doctype, fields, names


# --------------------------------------------------------------- profiles

@dataclass
class Profile:
    name: str
    inherits: str | None
    gloss: str
    inputs: dict[str, str]                # name -> type, or "= default"
    phases: dict[str, tuple[str, str]]    # phase -> (rerank-count, expression)
    functions: dict[str, str]
    properties: list[str]
    text: str                             # own text without comments


def read_profile(text: str) -> Profile:
    root = parse(text)
    block = next(c for c in root.children if c.header.startswith("rank-profile "))
    m = re.match(r"rank-profile\s+(\w+)(?:\s+inherits\s+(\w+))?", block.header)
    inputs: dict[str, str] = {}
    for line in (block.child("inputs").lines if block.child("inputs") else []):
        im = re.match(r"(query\(\w+\))\s+(.+?)(?:\s*:\s*([^:]+))?$", line)
        if im:
            inputs[im.group(1)] = (f"= {im.group(3).strip()}" if im.group(3)
                                   else im.group(2).strip())
    phases: dict[str, tuple[str, str]] = {}
    for phase in ("first-phase", "second-phase", "global-phase"):
        p = block.child(phase)
        if p is None:
            continue
        rerank = next((l.partition(":")[2].strip() for l in p.lines
                       if l.startswith("rerank-count")), "")
        expr = next((l.partition(":")[2].strip() for l in p.lines
                     if l.startswith("expression")), "")
        if not expr and p.child("expression") is not None:
            expr = " ".join(" ".join(p.child("expression").lines).split())
        phases[phase] = (rerank, expr)
    functions: dict[str, str] = {}
    for fn in block.kids("function"):
        fm = re.match(r"function\s+(\w+)\(", fn.header)
        expr = next((l.partition(":")[2].strip() for l in fn.lines if l.startswith("expression")), "")
        if not expr and fn.child("expression") is not None:
            expr = " ".join(" ".join(fn.child("expression").lines).split())
        if fm:
            functions[fm.group(1)] = expr
    props = block.child("rank-properties")
    return Profile(name=m.group(1), inherits=m.group(2), gloss=first_comment(text),
                   inputs=inputs, phases=phases, functions=functions,
                   properties=list(props.lines) if props else [],
                   text="\n".join(strip_comment(l) for l in text.splitlines()))


def chain(profile: Profile, by_name: dict[str, Profile]) -> list[Profile]:
    """The profile and its ancestors, nearest first."""
    out, seen = [profile], {profile.name}
    while out[-1].inherits and out[-1].inherits in by_name and out[-1].inherits not in seen:
        nxt = by_name[out[-1].inherits]
        out.append(nxt)
        seen.add(nxt.name)
    return out


def effective(profile: Profile, by_name: dict[str, Profile]) -> tuple[dict, dict, str]:
    """Phases and inputs with inheritance applied, and the whole text the
    profile is scored by (own and inherited), for finding which fields it reads."""
    phases: dict[str, tuple[str, str]] = {}
    inputs: dict[str, str] = {}
    texts: list[str] = []
    for p in reversed(chain(profile, by_name)):
        phases.update(p.phases)
        inputs.update(p.inputs)
        texts.append(p.text)
    ordered = {k: phases[k] for k in ("first-phase", "second-phase", "global-phase") if k in phases}
    return ordered, inputs, "\n".join(texts)


def reads_field(profile_text: str, name: str) -> bool:
    return re.search(rf"(attribute|closeness\(field|distance\(field)\s*[(,]\s*{name}\)", profile_text) is not None


# ----------------------------------------------------------------- render

def describe_field(f: Field, readers: list[str], fieldset: list[str],
                   no_reader: str = NO_READER) -> str:
    parts: list[str] = []
    if f.is_tensor:
        if f.is_index and any("hnsw" in x for x in f.index):
            parts.append("HNSW index: nearestNeighbor(%s, q)" % f.name)
        elif f.is_attribute:
            parts.append("attribute, no index")
        metric = next((x.partition(":")[2].strip() for x in f.attribute if x.startswith("distance-metric")), "")
        if metric:
            parts.append(f"distance {metric}")
        if readers:
            parts.append("read by " + ", ".join(readers) + ("" if f.is_index else "; not for queries"))
        else:
            parts.append(no_reader)
        return f"- {f.name}: {f.type} — " + "; ".join(parts)
    how: list[str] = []
    if f.is_index:
        match = ", ".join(f.match) if f.match else "text"
        if match == "word":
            match = "whole value as one word"
        how.append(f"index ({match}" + (", bm25)" if any("bm25" in x for x in f.index) else ")"))
    if f.is_attribute:
        fast = ", fast-search" if any("fast-search" in x for x in f.attribute) else ""
        how.append(f"attribute{fast}")
    if not how:
        how.append("not indexed, not an attribute: cannot be queried")
    if f.rank:
        how.append(f"rank {f.rank}")
    if f.is_index and f.name not in fieldset and not f.is_tensor:
        how.append("name it to search it")
    return f"- {f.name}: {f.type} — " + "; ".join(how)


def describe_profile(p: Profile, by_name: dict[str, Profile]) -> tuple[str, str]:
    """(the line's body, a grouping key for profiles that only differ in rank-properties).

    A profile that inherits shows only the phases it changes; one that changes
    nothing "ranks as" its parent. Inputs are named without `query(...)`, the
    way a request writes them.
    """
    phases, inputs, _ = effective(p, by_name)
    parent = by_name.get(p.inherits or "")
    parent_phases = effective(parent, by_name)[0] if parent else {}
    own = {k: v for k, v in phases.items() if parent_phases.get(k) != v}
    bits: list[str] = []
    for phase, (rerank, expr) in own.items():
        label = phase.replace("-", " ") + (f" (rerank {rerank})" if rerank else "")
        bits.append(f"{label}: {shorten(expr, EXPRESSION_WIDTH)}")
    if parent and not own:
        body = f"ranks as {parent.name}"
        if p.functions and len(p.functions) <= 4:
            body += ", redefining " + ", ".join(p.functions)
        elif p.functions:
            body += f", redefining {len(p.functions)} functions"
    else:
        body = (f"inherits {parent.name}; " if parent else "") + ("; ".join(bits) or "no phase of its own")
    needed = [name[6:-1] for name, kind in inputs.items() if not kind.startswith("=")]
    if needed:
        body += ". Needs " + ", ".join(needed)
    # Only the defaults this profile declares itself; inherited ones are on the parent's line.
    defaults = [f"{name[6:-1]} {kind}" for name, kind in p.inputs.items() if kind.startswith("=")]
    if defaults:
        body += ". Adjustable: " + ", ".join(defaults)
    key = body
    if p.gloss:
        body += f'. "{p.gloss}"'
    return body, key


def describe(app: Path, schema: str = "product", note: str | None = None,
             profiles: list[str] | None = None, statement_labels: str = "chapters") -> str:
    """The description; `profiles` names the rank profiles to list (None: all of them);
    `statement_labels` is "chapters" (each example statement names the chapter
    it is from) or "none" (no label, and the line before them names no chapter)."""
    if statement_labels not in STATEMENTS_HEADING:
        raise SystemExit(f"--statement-labels is one of {', '.join(STATEMENT_LABELS)}, "
                         f"not {statement_labels}")
    schema_file = app / "schemas" / f"{schema}.sd"
    doctype, fields, fieldset = read_schema(schema_file.read_text())
    every = sorted((read_profile(p.read_text()) for p in
                    (app / "schemas" / schema).glob("*.profile")), key=lambda p: p.name)
    by_name = {p.name: p for p in every}   # inheritance is read over every profile
    if profiles is None:
        listed, no_reader = every, NO_READER
    else:
        unknown = [n for n in profiles if n not in by_name]
        if unknown:
            raise SystemExit(f"no rank profile named {', '.join(unknown)} in {app / 'schemas' / schema}")
        if not profiles:
            raise SystemExit("--profiles names no profile")
        listed = [p for p in every if p.name in set(profiles)]
        no_reader = NO_READER if len(listed) == len(every) else NO_LISTED_READER
    texts = {p.name: effective(p, by_name)[2] for p in listed}

    out: list[str] = [f"# Catalogue: document type `{doctype}`", "",
                      "Fields (name: type — index = searchable; attribute = filters, grouping, ranking):"]
    for f in fields:
        readers = [name for name in texts if reads_field(texts[name], f.name)] if f.is_tensor else []
        out.append(describe_field(f, readers, fieldset, no_reader))
    out += ["", f"Fieldset `default` (what userQuery() searches): " + ", ".join(fieldset), ""]

    prefix = evaluate.QUERY_PREFIX
    out.append("Rank profiles (ranking=<name>):")
    rendered: list[tuple[str, str]] = [(p.name, *describe_profile(p, by_name)) for p in listed]
    done: set[str] = set()
    for name, body, key in rendered:
        if name in done:
            continue
        same = [n for n, b, k in rendered if k == key and b == key and body == key]
        if len(same) > 1:
            names = ", ".join(same) if len(same) <= 4 else f"{same[0]} … {same[-1]} ({len(same)} profiles)"
            props = sorted({l.partition(":")[0].strip() for n in same for l in by_name[n].properties})
            out.append(f"- {names}: {key}; each sets " + ", ".join(props) + " as its name says")
            done.update(same)
        else:
            out.append(f"- {name}: {body}")
            done.add(name)
    if note:
        out += ["", NOTE_HEADING, note.strip()]
    wanted = QUERY_TENSORS
    if profiles is not None:   # only the tensors the listed profiles need
        needed = {name[6:-1] for p in listed for name, kind in effective(p, by_name)[1].items()
                  if not kind.startswith("=")}
        wanted = {k: v for k, v in QUERY_TENSORS.items() if k in needed}
    tensors = ", ".join(f"{k} = {v.format(prefix=prefix)}" for k, v in wanted.items())
    out += [""] + ([f"Query tensors are request parameters input.query(<name>): {tensors}.", ""]
                   if tensors else [])

    out.append(STATEMENTS_HEADING[statement_labels])
    for i, (purpose, yql, params, source) in enumerate(EXAMPLES, 1):
        label = f" ({source})" if statement_labels == "chapters" else ""
        out.append(f"{i}. {purpose}{label}; params: {params}")
        out.append(f"   {yql}")
    out.append("")
    out.append("A statement selects the fields it wants back (id, title, brand); "
               "`where` is required.")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", type=Path, required=True,
                    help="the application package (its schemas/ directory is read)")
    ap.add_argument("--schema", default="product", help="document type to describe")
    ap.add_argument("--out", type=Path, default=None,
                    help="also write the description here")
    ap.add_argument("--note", default=None,
                    help="one paragraph added after the rank-profile list, under the line "
                         f"\"{NOTE_HEADING}\", the text as given; without it the package "
                         "alone decides the text")
    ap.add_argument("--profiles", default=None, metavar="NAME[,NAME...]",
                    help="list only these rank profiles, comma-separated, so an agent is offered "
                         "the rankings chosen for it rather than every profile in the package; "
                         "without it every profile is listed")
    ap.add_argument("--statement-labels", choices=STATEMENT_LABELS, default="chapters",
                    help="chapters (the default): each example statement names, in "
                         "parentheses, the chapter it is from; none: no label, and the line "
                         "before them reads \"Example statements, ...\", so the text names "
                         "no chapter (the demo kit's copy); the rest of the text is the same")
    args = ap.parse_args(argv)
    names = ([n.strip() for n in args.profiles.split(",") if n.strip()]
             if args.profiles is not None else None)
    text = describe(args.app, args.schema, args.note, names, args.statement_labels)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        print(f"wrote {args.out}", file=sys.stderr)
    print(f"{len(text)} characters" + (f" (over the {LENGTH_CAP} cap)" if len(text) > LENGTH_CAP else ""),
          file=sys.stderr)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
