rank-profile hybrid_linear inherits hybrid_rrf {
    # `hybrid_rrf` throws both scores away and keeps only rank. The
    # alternative this profile demonstrates is to keep the scores and put them
    # on a common scale first: `normalize_linear` rescales a feature across
    # the whole reranked set for this query, so 0 and 1 mean "worst and best
    # candidate seen here" for both the keyword side and the vector side. That
    # rescaling needs the whole candidate set in hand, which is exactly what
    # is not available in the first phase (it sees one document at a time) -
    # so normalisation, and everything built on it, can only live in the
    # global phase.
    #
    # `alpha` is a query input rather than a constant for the same reason
    # `bm25_tuned`'s weights are: sweeping it from 0 (vector alone) to 1
    # (lexical alone) is a parameter on the request, not a redeploy of this
    # file.
    inputs {
        query(alpha) double: 0.3
    }

    global-phase {
        rerank-count: 100
        expression {
            query(alpha) * normalize_linear(lexical) +
            (1 - query(alpha)) * normalize_linear(vector)
        }
    }
}
