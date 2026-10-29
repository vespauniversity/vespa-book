rank-profile hybrid_starved inherits hybrid_rrf {
    # Deliberately wrong, kept because the symptom misleads rather than
    # crashes. This overrides only the first phase, back to the raw,
    # unbounded sum `hybrid_rrf`'s comment warns against: `lexical + vector`
    # instead of `lexical / (1 + lexical) + vector`. `lexical` runs into
    # double digits on this corpus and `vector` never exceeds one, so the sum
    # is BM25 with a rounding error - every product only the vector arm found,
    # and every product BM25 scores at zero, sinks to the bottom of the
    # candidate set before the global phase ever runs. `rerank-count: 100`
    # then reranks whichever hundred the broken first phase let through, which
    # on this data is close to what `bm25_tuned` alone would have kept. The
    # global phase still computes `reciprocal_rank_fusion` correctly - fusion
    # is not what is broken here. What is starved is the candidate set fusion
    # gets to work with: recall@100 falls back toward keyword-only, which is
    # chapter 5's demonstration of why the first phase's only job is
    # deciding who is considered, never how good they are.
    first-phase {
        expression: lexical + vector
    }
}
