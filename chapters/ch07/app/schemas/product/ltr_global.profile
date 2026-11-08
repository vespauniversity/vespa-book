rank-profile ltr_global inherits ltr_second {
    # M2 (M1 = the second-phase model, trained without `cross_logit`; M2 =
    # the global-phase model, trained with it), the placement rule's
    # global-phase model: the model that gets the one
    # feature the second phase never can - `cross_logit`, the cross-encoder's
    # own logit, which exists only on the handful of candidates the global
    # phase reranks because the cross-encoder had to run to produce it
    # (`phased.profile`, `docs/pins.md`). 52 features: M1's 51 plus this
    # one.
    #
    # **Shape:** `ltr_global` is 3 leaves x 100 rounds, chosen before this
    # profile's own in-engine validation run rather than picked after seeing
    # it - the same rule `ltr_second` was chosen under, applied here in
    # advance because M2 is expensive enough (`cross_logit`, ~1 s per query)
    # that two candidate shapes are served and validation decides between
    # them, not swept across five points the way M1 was. Validation kept it:
    # against `phased` both shapes sit inside the noise, and the tie rule
    # chosen before that run - a tie goes to the smaller - picks this one.
    # The other shape, 3 x 200 (the offline grid's runner-up on this log),
    # is kept as its own row, `ltr_global_200.profile`, not overwritten.
    #
    # A fully learned funnel, not a second model replacing the first:
    # `inherits ltr_second` keeps its `second-phase` - 400 candidates scored
    # by the *M1* model - untouched, because M2 is only asking what the
    # global phase adds on top of it (M1 vs the first stage alone isolates
    # the second phase's own share; M2 vs M1 isolates this one, the vector
    # arm's depth aside - see the match-features comment below). That is why
    # this profile defines a second function, `ltr_score_global`, instead of
    # overriding `ltr_score`: `ltr_score` is read by the inherited
    # `second-phase` below, and redefining it here would silently swap the
    # second phase's model out from under it.
    function ltr_score_global() {
        expression: lightgbm("ltr_global.json")
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

    # Ten candidates, `phased.profile`'s own global rerank count (this
    # chapter's extended row measures 25 as a served override rather
    # than a second profile) - the survivors of the *learned* second phase
    # above, scored again by the model that can see `cross_logit`.
    global-phase {
        rerank-count: 10
        expression: ltr_score_global
    }
}
