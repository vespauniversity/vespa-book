"""Do the queries an agent sends look like the queries people wrote?

The relevance sets this book measures with were written by people typing into
a search box. An agent writes its queries differently - usually longer, more
complete, made of the words on a product page - so a ranking that wins on the
human set may or may not win on the agent's. Two questions follow, and this
tool answers both:

    A  How do the two query sets differ on their face? Length in characters,
       number of words, and how many of a query's words occur in any product
       title of the corpus (a query full of words nobody put in a title is
       harder for a lexical ranker whatever else is true).
    B  Do the four retrieval settings the book compared (`bm25_tuned`,
       `semantic`, `hybrid_rrf`, `phased`) score the same, and in the same
       order, on what the agent wrote as on what people wrote? `--mode b`.

Mode A. The agent queries come from any trajectory file `agent_loop.py`
wrote - the rules planner's or a model's - every `search` and `group` query it
sent, and on the query surface the words a `query` statement searched for (its
`query` request parameter, what `userQuery()` reads, or, for a statement that
searched the vector index only, the words inside the `embed(...)` it wrote -
the same words mode B scores it by, without the embedder's instruction
(`evaluate.QUERY_PREFIX`) in front when the agent copied it in, since that
sentence is not a word the agent chose); a statement with neither is counted,
not described - its words, where it has any, are written into the YQL itself
(`title contains ...`), which neither mode reads, and the rest are field
conditions only. With a handful of questions this is a description of the tool's
output, not a finding about agents.

Mode B. Every statement the agent sent belongs to a question, and every
question to a human query with judgements, so the statement's words can be
scored against those judgements. What is compared is the **wording**: under
each of the four profiles, a statement's words are sent as the request the
book builds for that profile (`evaluate.build_request` with the profile's
retriever, the two reranker inputs added for `phased`), inside the question's
pool, exactly as the human query is - and the conditions the agent wrote
itself (a brand exclusion, a field condition, a `nearestNeighbor` of its own)
are dropped. A statement's words are the `query` argument on the tool surface;
on the query surface, the `query` request parameter, or, for a statement that
searched the vector index only, the words inside its `embed(...)` without the
embedder's instruction in front - the same words mode A describes. So the two
surfaces are scored the same way, every request has a shape the profile
accepts, and the paired difference per profile is "the agent's wording
against the shopper's, same candidates, same labels, same retriever".
`hits` is 100 so recall@100 can be read. The human query is scored twice:
inside the question's pool, which is the paired comparison, and over the
whole corpus, the way the earlier chapters measured it, as context. A
statement is left out, and counted, when the engine refused it as the agent
sent it (`malformed`), when it searched for no words at all (nothing to
embed, nothing to compare), or when it was a grouping call (counts, not a
ranking). ndcg@10 and recall@100 per statement, their distribution per
profile, and the paired difference agent minus human with a bootstrap
interval.

The profiles block (`--block profiles`, no container) counts, per log, the
rank profile each statement named: the `ranking` argument of every `search`
call on the tool surface and of every `query` statement on the query surface,
refused ones included. A statement that named none ran under `hybrid_rrf`,
the default on both surfaces, and is counted on its own row. Grouping calls
on the tool surface take no profile and are counted apart. One column per log
given; `--common-questions` counts only the questions every log holds, so a
short run can be set beside the same questions of a full one.

Usage:
    python chapters/ch10/analyze_query_distribution.py --split test \\
        --trajectories llm.jsonl --block shift
    python chapters/ch10/analyze_query_distribution.py --split test --block profiles \\
        --trajectories llm-tools-alternative-k3.jsonl llm-query-alternative-k3.jsonl
    python chapters/ch10/analyze_query_distribution.py --split test --mode b \\
        --trajectories llm-query-alternative-k3.jsonl --block shift-b --out shift-b-query.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import builds      # noqa: E402
import deployed    # noqa: E402
import evaluate    # noqa: E402
import hostinfo    # noqa: E402
import metrics     # noqa: E402
from query import Vespa, add_where_clause   # noqa: E402

import tools_schema   # noqa: E402

TOKEN = re.compile(r"[a-z0-9]+")
CAPTION = ("Descriptive only. Human queries: every query of the {split} split "
           "({n_h}). Agent queries: every search and group query in the "
           "trajectory file ({n_a}). Vocabulary overlap = the share of a "
           "query's words that occur in some product title of the corpus, "
           "averaged over queries.")


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def title_vocabulary(products: Path) -> set[str]:
    vocab: set[str] = set()
    with products.open() as fh:
        for line in fh:
            vocab.update(tokens(json.loads(line)["fields"].get("title", "")))
    return vocab


def agent_queries(paths: list[Path]) -> tuple[list[str], int]:
    """(the text queries, how many `query` statements carried none)."""
    out: list[str] = []
    wordless = 0
    for path in paths:
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            for step in json.loads(line)["steps"]:
                args = step.get("args") or {}
                if step.get("tool") in ("search", "group"):
                    q = args.get("query")
                    if q:
                        out.append(str(q))
                elif step.get("tool") == "query":
                    params = args.get("params")
                    params = ({k: v for k, v in params.items() if k not in FIXED_KEYS}
                              if isinstance(params, dict) else {})
                    q = params.get("query") or strip_prefix(embed_text(params))
                    if q:
                        out.append(str(q))
                    else:
                        wordless += 1
    return out, wordless


def strip_prefix(text: str | None) -> str | None:
    """The words inside an `embed(...)` without the embedder's instruction
    (`evaluate.QUERY_PREFIX`) in front: the agent copies that sentence from
    the description, and it is not a word of its query."""
    if text and text.startswith(evaluate.QUERY_PREFIX):
        return text[len(evaluate.QUERY_PREFIX):].strip() or None
    return text


def describe(queries: list[str], vocab: set[str]) -> dict:
    lengths = [float(len(q)) for q in queries]
    words = [float(len(tokens(q))) for q in queries]
    overlap = []
    for q in queries:
        t = tokens(q)
        if t:
            overlap.append(sum(1 for w in t if w in vocab) / len(t))
    return {
        "n": len(queries),
        "chars": metrics.percentiles(lengths),
        "words": metrics.percentiles(words),
        "vocabulary_overlap": sum(overlap) / len(overlap) if overlap else None,
    }


def block_shift(human: dict, agent: dict, split: str, wordless: int = 0) -> str:
    rows = ["| | human | agent |", "|---|---|---|"]

    def cell(d: dict, key: str) -> str:
        if not d["n"]:
            return "—"
        s = d[key]
        return f"{s['p50']:g} / {s['mean']:.1f} / {s['max']:g}"

    rows.append(f"| queries | {human['n']:,} | {agent['n']:,} |")
    rows.append(f"| characters (median / mean / max) | {cell(human, 'chars')} | "
                f"{cell(agent, 'chars')} |")
    rows.append(f"| words (median / mean / max) | {cell(human, 'words')} | "
                f"{cell(agent, 'words')} |")
    rows.append(f"| vocabulary overlap | {metrics.fmt_metric(human['vocabulary_overlap'])}"
                f" | {metrics.fmt_metric(agent['vocabulary_overlap'])} |")
    caption = CAPTION.format(split=split, n_h=human["n"], n_a=agent["n"])
    if wordless:
        caption += (f" {wordless:,} `query` statements put no words in a `query` parameter "
                    "or an `embed(…)` and are not described: their words, where they have "
                    "any, are written into the YQL itself (`title contains …`), and the "
                    "rest are field conditions only.")
    return "\n".join(rows) + "\n\n" + caption + "\n"


# ------------------------------------------------------------------ shift B

PROFILES = ("bm25_tuned", "semantic", "hybrid_rrf", "phased")
RETRIEVER = {"bm25_tuned": "lexical", "semantic": "semantic",
             "hybrid_rrf": "hybrid", "phased": "hybrid"}
RERANKER_INPUTS = {"qt": "colbert", "qt_cross": "tokenizer"}
HITS_B = 100
SCOPES = ("pool", "corpus")
EMBED_TEXT = re.compile(r'embed\(\s*\w+\s*,\s*"((?:[^"\\]|\\.)*)"\s*\)')
FIXED_KEYS = ("yql", "hits", "ranking", "ranking.profile")
CAPTION_B = (
    "n = {n} statements from {q} questions of the {surface} surface, k = {k}; left out: "
    "{skipped}. "
    "Each statement's words, the agent's own conditions dropped, and its question's human "
    "query are sent as the book's request for each profile ({hits} hits) and scored "
    "against that question's human judgements: in the question's pool, the paired "
    "comparison (same candidates, same labels, only the wording differs), and the human "
    "query also over the whole corpus, as context. "
    "Mean, then p25 / p50 / p75; difference = agent minus the human query of the same "
    "question, per statement, with a bootstrap interval. "
    "Profile order by mean ndcg@10, read off the means with no profile-against-profile "
    "interval - agent: {o_agent}; human in the pool: {o_pool}; human over the corpus: "
    "{o_corpus}.")


def embed_text(params: dict) -> str | None:
    """The words inside an `embed(component, "...")` the agent wrote, if any."""
    for value in params.values():
        if isinstance(value, str):
            m = EMBED_TEXT.search(value)
            if m:
                return m.group(1).replace('\\"', '"').replace("\\\\", "\\")
    return None


def statements(lines: list[dict], questions: dict[str, dict]) -> tuple[list[dict], dict]:
    """Every scorable statement of a log - its question, its pool and the
    words it searched for - and the counts of those left out. A `search`
    step's words are its `query` argument; a `query` step's are its `query`
    request parameter, else the words inside its `embed(...)` without the
    embedder's instruction. Nothing else the agent wrote is kept."""
    out: list[dict] = []
    skipped = {"malformed": 0, "wordless": 0, "grouping": 0}
    for line in lines:
        q = questions[line["question_id"]]
        for step in line["steps"]:
            tool, args = step.get("tool"), step.get("args") or {}
            if tool not in ("query", "search", "group"):
                continue
            if step.get("status") == "malformed":
                skipped["malformed"] += 1
                continue
            if tool == "group":
                skipped["grouping"] += 1
                continue
            if tool == "query":
                if not step.get("yql_sent"):
                    skipped["malformed"] += 1
                    continue
                params = args.get("params") if isinstance(args.get("params"), dict) else {}
                params = {k: v for k, v in params.items() if k not in FIXED_KEYS}
                text = params.get("query") or strip_prefix(embed_text(params))
            else:
                text = args.get("query")
            if not text or not tokens(str(text)):
                skipped["wordless"] += 1
                continue
            out.append({"id": f"{line['question_id']}#{step['step']}",
                        "question_id": line["question_id"], "pool": q.get("pool"),
                        "text": str(text)})
    return out, skipped


def agent_request(statement: dict, profile: str) -> dict:
    """The statement under `profile`: its words sent as the book's request
    for that profile, inside its question's pool - the request a human query
    of the same words gets. The agent's own conditions are not in it."""
    return human_request(statement["text"], profile, statement["pool"])


def human_request(text: str, profile: str, pool: list[str] | None = None) -> dict:
    """The book's request for `text` under `profile` (the retriever the
    profile implies), inside `pool` when one is given."""
    req = evaluate.build_request(RETRIEVER[profile], text, HITS_B)
    if profile == "phased":
        evaluate.add_reranker_inputs(req, text, RERANKER_INPUTS)
    if pool is not None:
        req["yql"] = add_where_clause(req["yql"], tools_schema.pool_clause(pool))
    return req


def score(ids: list[str], judged: dict[str, float]) -> tuple[float, float]:
    """(ndcg@10, recall@100) of a hit list against one query's judgements."""
    ids = [i for i in ids if not str(i).startswith("group:")]
    relevant = {d for d, g in judged.items() if g > 0}
    ndcg = metrics.ndcg_at_k(ids, judged, 10)
    return (0.0 if ndcg != ndcg else ndcg), metrics.recall_at_k(ids, relevant, HITS_B)


def quartiles(values: list[float]) -> dict:
    """mean, p25 / p50 / p75 by nearest rank, as `metrics.percentiles` does."""
    if not values:
        return {"n": 0}
    ordered = sorted(values)

    def at(p: float) -> float:
        return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]
    return {"n": len(ordered), "mean": sum(ordered) / len(ordered),
            "p25": at(25), "p50": at(50), "p75": at(75)}


def run_b(app: Vespa, stmts: list[dict], questions: dict[str, dict],
          queries: dict[str, str], judgements: dict[str, dict[str, float]],
          out=sys.stderr) -> dict:
    """Score every statement and every question's human query under the four
    profiles; the paired differences per profile and scope."""
    refused = 0
    reasons: dict[str, int] = {}
    agent: dict[str, dict[str, dict[str, float]]] = {p: {"ndcg": {}, "recall": {}}
                                                     for p in PROFILES}
    for n, st in enumerate(stmts, 1):
        judged = judgements[questions[st["question_id"]]["query_id"]]
        for profile in PROFILES:
            req = agent_request(st, profile)
            try:
                r = app.query(req.pop("yql"), ranking=profile, hits=HITS_B, **req)
            except RuntimeError as exc:
                refused += 1
                key = f"{profile}: " + tools_schema.engine_reason(str(exc), 120)
                reasons[key] = reasons.get(key, 0) + 1
                continue
            ndcg, recall = score(r.ids(), judged)
            agent[profile]["ndcg"][st["id"]] = ndcg
            agent[profile]["recall"][st["id"]] = recall
        if n % 200 == 0:
            print(f"  {n}/{len(stmts)} statements", file=out, flush=True)
    qids = sorted({st["question_id"] for st in stmts})
    human: dict[str, dict[str, dict[str, dict[str, float]]]] = {
        s: {p: {"ndcg": {}, "recall": {}} for p in PROFILES} for s in SCOPES}
    for n, qid in enumerate(qids, 1):
        q = questions[qid]
        text, judged = queries[q["query_id"]], judgements[q["query_id"]]
        for scope in SCOPES:
            for profile in PROFILES:
                req = human_request(text, profile, q["pool"] if scope == "pool" else None)
                r = app.query(req.pop("yql"), ranking=profile, hits=HITS_B, **req)
                ndcg, recall = score(r.ids(), judged)
                human[scope][profile]["ndcg"][qid] = ndcg
                human[scope][profile]["recall"][qid] = recall
        if n % 200 == 0:
            print(f"  {n}/{len(qids)} human queries", file=out, flush=True)
    profiles: dict[str, dict] = {}
    for profile in PROFILES:
        row: dict = {"agent": {m: quartiles(list(agent[profile][m].values()))
                               for m in ("ndcg", "recall")}}
        for scope in SCOPES:
            row[f"human_{scope}"] = {m: quartiles(list(human[scope][profile][m].values()))
                                     for m in ("ndcg", "recall")}
            # the human score of each statement's own question, keyed like the statement
            row[f"delta_{scope}"] = {}
            for m in ("ndcg", "recall"):
                paired = {st["id"]: human[scope][profile][m][st["question_id"]]
                          for st in stmts if st["id"] in agent[profile][m]}
                row[f"delta_{scope}"][m] = metrics.bootstrap_delta(paired, agent[profile][m])
        profiles[profile] = row

    def order(key) -> list[str]:
        return sorted(PROFILES, key=lambda p: -key(p))
    return {
        "profiles": profiles, "refused": refused, "refused_reasons": reasons, "hits": HITS_B,
        "order_by_mean_ndcg": {
            "agent": order(lambda p: profiles[p]["agent"]["ndcg"]["mean"]),
            "human_pool": order(lambda p: profiles[p]["human_pool"]["ndcg"]["mean"]),
            "human_corpus": order(lambda p: profiles[p]["human_corpus"]["ndcg"]["mean"])},
    }


def block_shift_b(report: dict) -> str:
    fmt = metrics.fmt_metric
    out: list[str] = []
    for metric, name in (("ndcg", "ndcg@10"), ("recall", "recall@100")):
        out += [f"| profile | agent statements, {name}: mean (p25 / p50 / p75) | "
                "human query in the pool | human query over the corpus | "
                "agent − human, in the pool | agent − human, over the corpus |",
                "|---|---|---|---|---|---|"]
        for profile in PROFILES:
            row = report["profiles"][profile]

            def cell(d: dict, with_n: bool = False) -> str:
                if not d.get("n"):
                    return "—"
                return (f"{fmt(d['mean'])} ({fmt(d['p25'])} / {fmt(d['p50'])} / {fmt(d['p75'])})"
                        + (f", n = {d['n']:,}" if with_n else ""))
            out.append(f"| {profile} | {cell(row['agent'][metric], True)} | "
                       f"{cell(row['human_pool'][metric])} | {cell(row['human_corpus'][metric])} | "
                       f"{metrics.fmt_delta(row['delta_pool'][metric])} | "
                       f"{metrics.fmt_delta(row['delta_corpus'][metric])} |")
        out.append("")
    sk = report["skipped"]
    skipped = (f"{sk['malformed']} refused by the engine when the agent sent them, "
               f"{sk['wordless']} with no word to score in a `query` argument, a `query` "
               "parameter or an `embed(…)` (words written into the YQL itself, as "
               f"`title contains …`, are not read), {sk['grouping']} grouping calls"
               + (f", and {report['refused']} statement-profile pairs the engine refused "
                  "when re-run" if report["refused"] else ""))
    o = report["order_by_mean_ndcg"]
    caption = CAPTION_B.format(n=report["statements"], q=report["questions"],
                               surface=report["surface"], k=report["k"], hits=report["hits"],
                               skipped=skipped, o_agent=" > ".join(o["agent"]),
                               o_pool=" > ".join(o["human_pool"]),
                               o_corpus=" > ".join(o["human_corpus"]))
    return "\n".join(out) + "\n" + caption + "\n"


# ------------------------------------------------------------------ profiles

NO_PROFILE = "no profile named"
# What a statement that names no profile runs under, on both surfaces: the
# loop sends `hybrid_rrf` when the `ranking` argument is missing or empty.
DEFAULT_PROFILE = "hybrid_rrf"
CAPTION_P = (
    "Each column is one log: how many statements named each rank profile in their "
    "`ranking` argument - every `search` call on the tool surface, every `query` "
    "statement on the query surface, refused ones included. A statement that named none "
    "ran under `{default}`, the default on both surfaces.{grouping}{common} "
    "Counts from one model run per log; no interval.")


def repo_relative(path: Path) -> str:
    """A path for the report: relative to the repository root when it lies
    under it, so the report does not carry one machine's directories."""
    try:
        return str(Path(path).resolve().relative_to(builds.ROOT))
    except ValueError:
        return str(path)


def read_log(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def profile_counts(lines: list[dict]) -> dict:
    """How often each rank profile was named in one log. A statement is a
    `search` call (tool surface) or a `query` statement (query surface),
    whatever its status; its profile is its `ranking` argument, or none.
    Grouping calls take no profile and are counted apart."""
    counts: dict[str, int] = {}
    statements = grouping = 0
    for line in lines:
        for step in line.get("steps") or []:
            tool = step.get("tool")
            if tool == "group":
                grouping += 1
                continue
            if tool not in ("search", "query"):
                continue
            statements += 1
            args = step.get("args") if isinstance(step.get("args"), dict) else {}
            name = args.get("ranking")
            key = str(name) if name else NO_PROFILE
            counts[key] = counts.get(key, 0) + 1
    first = lines[0] if lines else {}
    return {"surface": first.get("surface"), "k": first.get("k"),
            "model": first.get("model"), "build": first.get("build"),
            "skill": first.get("skill"), "questions": len(lines),
            "statements": statements, "grouping_calls": grouping, "counts": counts}


def block_profiles(report: dict) -> str:
    logs = report["logs"]
    total = {p: sum(l["counts"].get(p, 0) for l in logs)
             for l in logs for p in l["counts"] if p != NO_PROFILE}
    named = sorted(total, key=lambda p: (-total[p], p))
    rows = ["| profile named | " + " | ".join(f"`{l['name']}`" for l in logs) + " |",
            "|---" * (len(logs) + 1) + "|"]
    for p in named:
        rows.append(f"| `{p}` | " + " | ".join(f"{l['counts'].get(p, 0):,}" for l in logs) + " |")
    rows.append(f"| {NO_PROFILE} | "
                + " | ".join(f"{l['counts'].get(NO_PROFILE, 0):,}" for l in logs) + " |")
    rows.append("| statements | " + " | ".join(f"{l['statements']:,}" for l in logs) + " |")
    rows.append("| questions | " + " | ".join(f"{l['questions']:,}" for l in logs) + " |")
    grouping = sum(l["grouping_calls"] for l in logs)
    caption = CAPTION_P.format(
        default=report["default_profile"],
        grouping=(f" Grouping calls on the tool surface take no profile and are not "
                  f"counted ({grouping:,} in all)." if grouping else ""),
        common=(" Only the questions every log holds are counted." if
                report["common_questions"] else ""))
    return "\n".join(rows) + "\n\n" + caption + "\n"


def main_profiles(args, build: Path) -> int:
    logs = [(p, read_log(p)) for p in args.trajectories]
    if args.common_questions:
        common = set.intersection(*({x["question_id"] for x in lines} for _, lines in logs))
        logs = [(p, [x for x in lines if x["question_id"] in common]) for p, lines in logs]
    report = {"build": builds.meta(build)["build_id"], "split": args.split,
              "inputs": [{"path": repo_relative(p), "bytes": p.stat().st_size,
                          "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                         for p, _ in logs],
              "common_questions": bool(args.common_questions),
              "default_profile": DEFAULT_PROFILE,
              "logs": [{"name": p.stem, "path": repo_relative(p), **profile_counts(lines)}
                       for p, lines in logs]}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    print(block_profiles(report))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, default=None)
    ap.add_argument("--split", required=True, choices=builds.SPLITS,
                    help="which split's human queries to describe; no default")
    ap.add_argument("--trajectories", type=Path, nargs="+", default=None,
                    help="one or more files written by agent_loop.py")
    ap.add_argument("--mode", choices=("a", "b"), default="a",
                    help="a: describe the two query sets (block shift); b: score the "
                         "agent's statements and the human queries under the four "
                         "profiles against the same judgements (block shift-b; needs "
                         "the running application)")
    ap.add_argument("--block", choices=("shift", "shift-b", "profiles"), default=None,
                    help="the one block printed on stdout (default: the mode's own); "
                         "profiles: the rank profile each statement named, one column "
                         "per log, no container")
    ap.add_argument("--common-questions", action="store_true",
                    help="profiles: count only the questions every log given holds")
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--questions", type=Path, default=None,
                    help="question file for mode b (default: <build>/multihop_<split>.jsonl)")
    ap.add_argument("--limit", type=int, default=None,
                    help="mode b: score only the statements of the first N questions")
    ap.add_argument("--out", type=Path, default=None, help="write the report here")
    ap.add_argument("--from", dest="from_report", type=Path, default=None,
                    help="mode b: print the block from a report this tool wrote, querying nothing")
    args = ap.parse_args(argv)

    block = args.block or ("shift" if args.mode == "a" else "shift-b")
    if (block == "shift-b") != (args.mode == "b"):
        raise SystemExit(f"--block {block} goes with --mode {'b' if block == 'shift-b' else 'a'}")
    if args.from_report:
        if args.mode != "b":
            raise SystemExit("--from re-renders a mode b report")
        print(block_shift_b(json.loads(args.from_report.read_text())))
        return 0
    if not args.trajectories:
        raise SystemExit("--trajectories is needed: the agent queries come from a log")

    build = args.build or builds.latest()
    if block == "profiles":
        return main_profiles(args, build)
    if args.mode == "b":
        return main_b(args, build)
    vocab = title_vocabulary(build / "products.jsonl")
    human = describe(list(builds.load_queries(build, args.split).values()), vocab)
    queries, wordless = agent_queries(args.trajectories)
    agent = describe(queries, vocab)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        first = json.loads(args.trajectories[0].read_text().splitlines()[0])
        report = {"build": builds.meta(build)["build_id"], "split": args.split,
                  # what answered the agent's run, copied from its log; this tool queries nothing
                  deployed.FIELD: first.get(deployed.FIELD, "not recorded"),
                  "trajectories": [str(p) for p in args.trajectories],
                  "human": human, "agent": agent, "agent_wordless_statements": wordless,
                  "host": hostinfo.collect()}
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    print(block_shift(human, agent, args.split, wordless))
    return 0


def main_b(args, build: Path) -> int:
    import eval_trajectory
    questions = eval_trajectory.load_questions(build, args.split, args.questions)
    lines = [x for p in args.trajectories for x in eval_trajectory.load_lines(p)]
    if args.limit:
        lines = lines[:args.limit]
    missing = [x["question_id"] for x in lines if x["question_id"] not in questions]
    if missing:
        raise SystemExit(f"questions not in the question file: {missing[:5]}")
    stmts, skipped = statements(lines, questions)
    if not stmts:
        raise SystemExit("no scorable statement in the log")
    app = Vespa(args.endpoint)
    if not app.healthy():
        print(f"no Vespa at {args.endpoint}", file=sys.stderr)
        return 1
    queries = builds.load_queries(build, args.split)
    judgements = builds.load_judgements(build, args.split)
    print(f"  {len(stmts)} statements to score under {len(PROFILES)} profiles, "
          f"{len({s['question_id'] for s in stmts})} human queries under two scopes",
          file=sys.stderr, flush=True)
    result = run_b(app, stmts, questions, queries, judgements)
    first = lines[0]
    report = {"build": builds.meta(build)["build_id"], "split": args.split,
              **deployed.stamp(),
              "trajectories": [str(p) for p in args.trajectories],
              "surface": first.get("surface"), "k": first.get("k"),
              "planner": first.get("planner"), "model": first.get("model"),
              "statements": len(stmts),
              "questions": len({s["question_id"] for s in stmts}),
              "skipped": skipped, **result, "host": hostinfo.collect()}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    print(block_shift_b(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
