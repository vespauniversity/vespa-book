"""ESCI relevance labels and the gains they map to.

Two conventions are in circulation and they disagree about the middle pair.
NDCG computed under one is not comparable with NDCG computed under the other,
so the mapping is named in every build and quoted wherever a number derived
from it appears.
"""
from __future__ import annotations

# Labels arrive spelled out in the Hugging Face mirror and as single letters in
# the canonical parquet. Both are accepted.
CANONICAL = {
    "E": "E", "S": "S", "C": "C", "I": "I",
    "Exact": "E", "Substitute": "S", "Complement": "C", "Irrelevant": "I",
}

MAPPINGS: dict[str, dict[str, float]] = {
    # The default. A substitute is an alternative product, a complement is an
    # accessory, so the substitute is the more useful result.
    "kdd": {"E": 1.0, "S": 0.1, "C": 0.01, "I": 0.0},
    # Used by Vespa's ESCI sample application and its LTR blog series, which
    # places complement above substitute. Kept so our numbers can be compared
    # with theirs on request.
    "vespa-sample": {"E": 1.0, "C": 0.1, "S": 0.01, "I": 0.0},
}

# Integer scale for tools that expect ordinal labels rather than gains, and for
# LightGBM's label_gain, which is indexed by label value.
ORDINAL = {"I": 0, "C": 1, "S": 2, "E": 3}
DEFAULT = "kdd"


def normalise(label: str) -> str:
    """'Irrelevant' or 'I' -> 'I'. Raises on anything else."""
    try:
        return CANONICAL[label]
    except KeyError:
        raise ValueError(f"unknown ESCI label: {label!r}") from None


def gain(label: str, mapping: str = DEFAULT) -> float:
    return MAPPINGS[mapping][normalise(label)]


def ordinal(label: str) -> int:
    return ORDINAL[normalise(label)]


def label_gain(mapping: str = DEFAULT) -> list[float]:
    """LightGBM `label_gain`, indexed by the ordinal label value."""
    m = MAPPINGS[mapping]
    inverse = {v: k for k, v in ORDINAL.items()}
    return [m[inverse[i]] for i in range(len(ORDINAL))]
