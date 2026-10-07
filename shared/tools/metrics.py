"""Retrieval metrics, implemented here rather than imported.

Every quality claim from chapter 3 onward rests on these four numbers, so the
definitions are written out where a reader can check them against the ones in
their own head. Three of them have more than one definition in circulation, and
a book that reports NDCG without saying which one it used has not reported
anything.

The choices made here, all of them arguable and all of them stated:

- **Relevant means a gain above zero.** ESCI's irrelevant label maps to zero, so
  Recall and MRR count exact, substitute and complement results as finds. Where
  that is too generous, pass a higher `threshold`.
- **A query with nothing relevant is skipped**, not scored zero. Scoring it zero
  would mean a system is punished for a query whose answer is not in the corpus.
  The number of skipped queries is reported alongside, because a metric computed
  over a shrinking set of queries is a metric that can be gamed by accident.
- **NDCG's ideal ranking comes from every judgement for that query**, not only
  from the documents retrieved. A system that retrieves nothing scores zero
  rather than one.
- **Recall's denominator is every judged relevant document**, including ones no
  query ever reached. So recall is bounded by what is in the corpus, which is
  the point of measuring it.

How these numbers are *written* is here too, at the bottom of the file, because
a number's format is part of what it claims and this is where the number is
defined.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field


@dataclass
class Scores:
    """What one evaluation run produced."""
    queries: int = 0
    skipped: int = 0
    recall: dict[int, float] = field(default_factory=dict)
    mrr: float = 0.0
    ndcg: dict[int, float] = field(default_factory=dict)
    latency_ms: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "queries": self.queries,
            "skipped_no_relevant": self.skipped,
            "recall": {f"@{k}": round(v, 4) for k, v in sorted(self.recall.items())},
            "mrr": round(self.mrr, 4),
            "ndcg": {f"@{k}": round(v, 4) for k, v in sorted(self.ndcg.items())},
            "latency_ms": {k: round(v, 2) for k, v in self.latency_ms.items()},
        }

    def summary(self) -> str:
        parts = [f"{self.queries} queries"]
        if self.skipped:
            parts.append(f"({self.skipped} skipped, nothing relevant judged)")
        parts.append("  ".join(f"recall@{k} {fmt_metric(v)}"
                               for k, v in sorted(self.recall.items())))
        parts.append(f"mrr {fmt_metric(self.mrr)}")
        parts.append("  ".join(f"ndcg@{k} {fmt_metric(v)}"
                               for k, v in sorted(self.ndcg.items())))
        if self.latency_ms:
            parts.append("  ".join(f"{k} {fmt_latency(v)}"
                                   for k, v in self.latency_ms.items()))
        return "\n  ".join(parts)


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return float("nan")
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for i, doc in enumerate(retrieved, start=1):
        if doc in relevant:
            return 1.0 / i
    return 0.0


def dcg(gains: list[float]) -> float:
    """Discounted cumulative gain, the standard log2(rank + 1) discount."""
    return sum(g / math.log2(i + 1) for i, g in enumerate(gains, start=1))


def ndcg_at_k(retrieved: list[str], judgements: dict[str, float], k: int) -> float:
    """Normalised DCG at k.

    The ideal ranking is every judged document for this query, best first,
    truncated at k — not only the documents this system happened to retrieve.
    """
    ideal = dcg(sorted(judgements.values(), reverse=True)[:k])
    if ideal == 0:
        return float("nan")
    actual = dcg([judgements.get(doc, 0.0) for doc in retrieved[:k]])
    return actual / ideal


def evaluate(results: dict[str, list[str]],
             judgements: dict[str, dict[str, float]],
             recall_k: tuple[int, ...] = (10, 100),
             ndcg_k: tuple[int, ...] = (10,),
             threshold: float = 0.0,
             latencies_ms: list[float] | None = None) -> Scores:
    """Score a run.

    `results` maps a query id to the document ids it returned, best first.
    `judgements` maps a query id to {document id: gain}.
    """
    scored = Scores()
    recalls: dict[int, list[float]] = {k: [] for k in recall_k}
    ndcgs: dict[int, list[float]] = {k: [] for k in ndcg_k}
    rrs: list[float] = []

    for qid, retrieved in results.items():
        judged = judgements.get(qid, {})
        relevant = {d for d, g in judged.items() if g > threshold}
        if not relevant:
            scored.skipped += 1
            continue
        scored.queries += 1
        for k in recall_k:
            recalls[k].append(recall_at_k(retrieved, relevant, k))
        for k in ndcg_k:
            value = ndcg_at_k(retrieved, judged, k)
            if not math.isnan(value):
                ndcgs[k].append(value)
        rrs.append(reciprocal_rank(retrieved, relevant))

    scored.recall = {k: statistics.fmean(v) if v else 0.0 for k, v in recalls.items()}
    scored.ndcg = {k: statistics.fmean(v) if v else 0.0 for k, v in ndcgs.items()}
    scored.mrr = statistics.fmean(rrs) if rrs else 0.0
    if latencies_ms:
        scored.latency_ms = percentiles(latencies_ms)
    return scored


def percentiles(values: list[float]) -> dict[str, float]:
    """p50, p95, p99 and the mean, by nearest rank on the sorted sample.

    Not interpolated: with a few hundred queries, interpolating between two
    observations invents precision that is not there.
    """
    if not values:
        return {}
    ordered = sorted(values)
    def at(p: float) -> float:
        idx = max(0, math.ceil(p / 100 * len(ordered)) - 1)
        return ordered[idx]
    return {"mean": statistics.fmean(ordered), "p50": at(50),
            "p95": at(95), "p99": at(99), "max": ordered[-1]}


def bootstrap_delta(a: dict[str, float], b: dict[str, float],
                    samples: int = 2000, seed: int = 42,
                    confidence: float = 0.95) -> dict[str, float]:
    """Is b better than a, or is the difference noise?

    Resamples the per-query scores with replacement and reports the mean
    difference with a confidence interval. An interval that straddles zero means
    the sample cannot tell the two apart — which is worth saying in a book
    rather than reporting the difference as an improvement.
    """
    import random
    shared = sorted(set(a) & set(b))
    if not shared:
        return {}
    deltas = [b[q] - a[q] for q in shared]
    rng = random.Random(seed)
    means = []
    n = len(deltas)
    for _ in range(samples):
        means.append(statistics.fmean(rng.choices(deltas, k=n)))
    means.sort()
    lo = means[int((1 - confidence) / 2 * samples)]
    hi = means[int((1 + confidence) / 2 * samples) - 1]
    return {"delta": statistics.fmean(deltas), "lo": lo, "hi": hi,
            "significant": lo > 0 or hi < 0, "n": n}


# --------------------------------------------------------------------------
# How a number is written
# --------------------------------------------------------------------------
#
# **Three decimals, wherever a number is shown to a person.** One setting, and
# nothing selects between settings: not the width of an interval, not how many
# queries were evaluated, not which chapter the number appears in.
#
# This said two until 2026-09-14, and the argument for two conflated two
# different resolutions a score has. They differ by an order of magnitude and
# they answer different questions:
#
# **How reproducible a score is.** Feed the same corpus into a fresh empty
# container, evaluate the same profile, and see how far the number moves. Three
# rounds of exactly that, on one machine, gave:
#
#     lexical    0.3958  0.3957  0.3958      drift 0.0001 — the fourth decimal
#     semantic   0.4358  0.4401  0.4401      drift 0.0043 — the third
#
# **Whether two systems can be told apart.** That is the bootstrap interval,
# which in this book runs from under 0.01 to several hundredths wide.
#
# Two decimals threw the first away to prevent a misuse of the second — a
# reader ordering three scores by a gap the interval says is invisible. The
# third decimal is reproducible, so blunting it is discarding a measured fact;
# and the misuse it was guarding against is prevented directly now, in words.
# `fmt_delta` spells out "real" or "inside the noise" on every row rather than
# leaving a reader to compare two brackets by eye, and `alpha_sweep` names the
# settings its sample cannot separate in a column of its own. With the verdict
# said out loud, the digits do not have to be blunted to stop it being got
# wrong.
#
# The two passages two decimals was argued from do not need it either:
#
# - "0.3957 against 0.3958, coincidence or identity" is an argument about the
#   *fourth* decimal. Three decimals collapses it to 0.396 against 0.396 just
#   as well as two collapses it to 0.40 against 0.40.
# - The rebuild variance 0.436 / 0.440 / 0.440 was claimed as a benefit — "at
#   two decimals that variance does not exist". It does exist. Hiding a true
#   fact is not dissolving a problem, and the table that documented it has
#   since been removed for reasons of its own.
#
# **One setting, and no mechanism for the exception.** Where a re-run's drift
# makes a third-decimal difference misleading at one point in the prose, that
# is said at that point, in words — about the same, or a figure rounded there
# by whoever writes the sentence. It is not a mode here, not an option, and not
# a branch: a code path nothing selects is what this project keeps paying for,
# and a formatter that can be asked for a different precision is a formatter
# whose output is no longer the book's format.
#
# **The boundary is here and only here.** A report keeps whatever precision it
# stores — a report is data, and rounding data destroys it; `bootstrap_delta`
# needs the per-query scores as they were, and an interval cannot be recovered
# from a rounded one. What rounds is the text a tool prints, including the
# finished block it prints for the page. There is no renderer downstream of the
# tool any more, so the tool's own output is the book's format and this is the
# last place the decision can live.
#
# Latency is not on this scale. A millisecond is not a metric between zero and
# one, and `5.8 ms` at one decimal is what every table in this book already
# shows; `query.py`'s relevance and rank-feature scores are not bounded by one
# either, and stay at four and three. Those are different decisions about
# different quantities, and this one does not make them.

PLACES = 3
NOTHING = "—"


def fmt_metric(value: float | None) -> str:
    """A score, as the book writes it: `0.481`.

    `None` and NaN come out as a dash rather than as `0.000` or `nan`, because
    a metric that could not be computed and a metric that came out at zero are
    different facts and a reader cannot tell them apart once both are digits.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return NOTHING
    return f"{value:.{PLACES}f}"


def fmt_signed(value: float | None) -> str:
    """A difference, which always carries its sign: `+0.020`, `-0.065`."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return NOTHING
    return f"{value:+.{PLACES}f}"


def fmt_latency(ms: float | None) -> str:
    """A latency: `5.8 ms`. One decimal — see the note above."""
    return NOTHING if ms is None else f"{ms:.1f} ms"


def fmt_delta(d: dict | None) -> str:
    """A `bootstrap_delta`, written out whole: `+0.020 [+0.008, +0.031], real`.

    The interval and the verdict are not decoration and are not optional. A
    difference quoted without its bracket is the single most damaging thing
    that has happened to this book's prose: three prefix scores reached a page
    in an order the chapter argued from, and one of the two gaps was inside the
    noise in the report the table was generated from.

    The verdict is spelled out on every row, including the significant ones.
    Until 2026-09-14 two conventions were in use — the alpha table said nothing
    when a difference was real and "inside the noise" when it was not, while
    the comparison and prefix tables named both — so the *absence* of a phrase
    carried meaning in one table and nothing in another. A meaning carried by
    an absence does not survive being rewritten.

    The word and the digits have to agree, and at three decimals they do where
    two decimals did not. Chapter 7's head-to-head on 2,000 held-out queries is
    `+0.0081 [+0.0022, +0.0134]`, significant; at two decimals that printed
    `+0.01 [+0.00, +0.01]`, an interval whose low end reads as touching zero
    beside the word "real". At three it is `+0.008 [+0.002, +0.013], real`.
    An illustrative `+0.0280 [+0.0027, +0.0525]` — a test fixture, not a
    chapter's measurement — does the same and reads `+0.028 [+0.003, +0.052], real`.
    """
    if not d:
        return NOTHING
    return (f"{fmt_signed(d['delta'])} "
            f"[{fmt_signed(d['lo'])}, {fmt_signed(d['hi'])}], "
            f"{'real' if d['significant'] else 'inside the noise'}")
