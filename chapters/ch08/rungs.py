"""The five-rung selectivity ladder, in one place.

Every tool in this chapter that names a rung — `derive_tenants.py`'s report,
`filtered_ann.py`'s sweep — reads the same five clauses from here, so a
rung's YQL is written once and never retyped (`authorized_query.py` names no
rung; it uses only `wrap_where`, below). `docs/synthetic-data.md` derives
the field this ladder filters on (`tenant_id`); these five rungs were chosen
because no single brand on this 101,341-document build reaches 1% (`nike`
is the largest single brand, 604 documents, 0.596% of this build), so the
ladder spans selectivity through fields that come from the catalogue's own
data (`tenant_id` is derived from `brand`) rather than one invented to hit
chosen percentages.

`none` carries no clause at all — it is the no-filter row ch04 already
measured (`chapters/ch04/expected/validation-ann-sweep.json`), re-measured
here (first, and again later as a drift check) so every row in this
chapter's table comes from the same container.
"""
from __future__ import annotations

# name -> YQL clause (no leading "and", no clause at all for "none")
RUNGS: dict[str, str] = {
    "has_description": 'has_description = true',
    "has_brand": '!(tenant_id contains "__marketplace__")',
    "marketplace": 'tenant_id contains "__marketplace__"',
    "nike": 'tenant_id contains "nike"',
    "small_brand": 'tenant_id contains "20th century fox"',
    "none": "",
}

# The rungs in the order the ladder block prints them (has_brand is the
# loosest). `none` is not a rung of the ladder and is listed separately so a
# caller that means "every rung" does not accidentally include it.
LADDER = ("has_description", "has_brand", "marketplace", "nike", "small_brand")


def clause(rung: str) -> str:
    """The bare YQL clause for a rung name, or `""` for `none` — never a
    leading `and`, so a caller decides for itself whether it has anything
    else in its `where` to join onto."""
    if rung not in RUNGS:
        raise ValueError(f"unknown rung {rung!r}; choose one of {sorted(RUNGS)}")
    return RUNGS[rung]


def and_clause(base_where: str, rung: str) -> str:
    """`base_where` with the rung's clause ANDed on, or `base_where`
    unchanged for `none` — the shape every retrieval request in this
    chapter builds its `where` from."""
    c = clause(rung)
    return base_where if not c else f"{base_where} and {c}"


def wrap_where(yql: str, extra_clause: str) -> str:
    """AND `extra_clause` onto a YQL string's `where` expression.

    Parenthesises whatever was already there, so an `or` inside it (chapter
    5's hybrid retriever's `userQuery() or nearestNeighbor(...)`) cannot
    leak past the new clause — `a or b and c` is `a or (b and c)` in YQL,
    not `(a or b) and c`, which is the bug this exists to prevent.
    `extra_clause` falsy (the `none` rung, or an unrestricted user) returns
    `yql` unchanged. `filtered_ann.py` and `authorized_query.py` both build a
    retriever's plain YQL first (`evaluate.build_request`, or
    `filtered_ann.py`'s own annotated `nearestNeighbor`) and use this to add
    the one thing ch08 itself contributes.
    """
    if not extra_clause:
        return yql
    prefix, sep, where_expr = yql.partition(" where ")
    if not sep:
        raise ValueError(f"no ' where ' clause in yql: {yql!r}")
    return f"{prefix} where ({where_expr}) and {extra_clause}"
