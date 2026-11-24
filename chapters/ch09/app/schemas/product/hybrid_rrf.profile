rank-profile hybrid_rrf inherits bm25_tuned {
    # A query for "running shoes" is sent to both retrievers at once: the
    # keyword arm and the nearest-neighbour arm each nominate candidates, and
    # the candidate set going into ranking is their union.
    # Deciding a single order over that union is the problem this profile
    # answers, and `hybrid_rrf` answers it without ever looking at either
    # retriever's raw score.
    #
    # `bm25_tuned`'s two query inputs, `w_qcomplete` and `w_brand`, come along
    # through inheritance with their defaults (5.0, 1.0) already set - nothing
    # here re-declares them.
    inputs {
        query(q) tensor<float>(x[384])
    }

    # The keyword side, unchanged from what `bm25_tuned` scores a document
    # with on its own: BM25 on the title, plus the two flat query-completeness
    # and brand-match bonuses. Kept as a function so both phases below can
    # name it without repeating the expression.
    function lexical() {
        expression {
            bm25(title) +
            query(w_qcomplete) * fieldMatch(title).queryCompleteness +
            query(w_brand)     * matches(brand)
        }
    }

    # The vector side: how close the query embedding sits to this product's
    # title embedding, the same feature `semantic` ranks on.
    function vector() {
        expression: closeness(field, title_embedding)
    }

    match-features {
        lexical
        vector
    }

    # This runs on every matched document, so it has to be cheap, and it must
    # not be one-sided. `lexical` is BM25 plus two bonuses and is unbounded -
    # on this corpus it runs into double digits - while `vector` is a
    # closeness, `1 / (1 + distance)`, which lies in (0, 1] and never exceeds
    # one. Adding them raw would mean the sum is BM25 with a
    # rounding error, because the vector term can almost never move the
    # ranking. `lexical / (1 + lexical)` squashes the unbounded side into
    # [0,1) so both terms can move the ordering; it is not a calibration and
    # does not need to be, because the first phase only decides who survives
    # to be reranked, not the final order.
    first-phase {
        expression: lexical / (1 + lexical) + vector
    }

    # Reciprocal rank fusion never looks at either score again, only at where
    # each score places a document among the hundred being reranked. That is
    # what lets it combine BM25 (unbounded, unnormalised) and closeness
    # (bounded, already comparable) without deciding how a point of one maps
    # to a point of the other - the question `hybrid_linear` has to answer and
    # this profile does not.
    global-phase {
        rerank-count: 100
        expression: reciprocal_rank_fusion(lexical, vector)
    }
}
