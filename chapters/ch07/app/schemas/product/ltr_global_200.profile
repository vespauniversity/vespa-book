rank-profile ltr_global_200 inherits ltr_second {
    # The second global-phase shape, measured beside `ltr_global` so the
    # chapter can check the offline pick in the engine rather than trusting
    # the offline number alone: 3 leaves x 200 rounds, the offline grid's
    # runner-up on this log (the grid's pick, 3 x 100, is `ltr_global`,
    # which the tie rule keeps). Same 52 features, same placement, same
    # rerank counts as `ltr_global`; only the model file differs.
    function ltr_score_global() {
        expression: lightgbm("ltr_global_200.json")
    }

    # `ltr_score_global` *is* a match-feature, on purpose, and that has a
    # cost rule attached. A match-feature is computed on the content node
    # for every hit the response returns, not only for the documents the
    # global phase reranks: asking for 400 hits ran the cross-encoder once
    # per returned hit - hundreds of times a query, at about 81–85 ms each
    # (chapter 6) - and the evaluation timed out before the first pass
    # finished, although the global phase itself scores 10. Leaving it out
    # is not an option either: the global phase is evaluated in the
    # container, which then has to evaluate this GBDT itself and asks the
    # content node for every input - including the cross-encoder's token
    # tensors - and that configuration does not construct ("missing
    # global-phase input"). So the model's score is shipped as a
    # match-feature and *requests on this profile ask for as many hits as
    # the global phase reranks*: ten by default, which is what a production
    # request returns anyway; the parity runs and the 25-hit row widen both
    # counts together. recall@100 is not measured on this profile - a global
    # phase over 10 cannot change which documents are in the hundred, so it
    # would be this profile's own second phase's figure. That is not exactly
    # `ltr_second`'s row: a ten-hit request also asks the vector arm for ten
    # nearest neighbours (`evaluate.py` sets `targetHits` from `--hits`),
    # not the four hundred `ltr_second`'s rows asked for.
    match-features {
        lexical
        vector
        max_sim
        ltr_score
        ltr_score_global
    }

    # Same count as `ltr_global` (10, `phased`'s own global rerank count) -
    # the two M2 rows (M1 = the second-phase model, trained without
    # `cross_logit`; M2 = the global-phase model, trained with it) differ
    # only in which trained file scores the survivors, not in how many of
    # them there are.
    global-phase {
        rerank-count: 10
        expression: ltr_score_global
    }
}
