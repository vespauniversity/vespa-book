rank-profile features_second inherits features {
    # A logging profile for one leg of `benchmark_inference.py`'s external
    # benchmark, not for a served ranking - built to
    # avoid a bias: ch06's `features` logging profile computes `cross_logit`
    # for every one of the N candidates it returns even though M1 (M1 = the
    # second-phase model, trained without `cross_logit`; M2 = the
    # global-phase model, trained with it) - `ltr_second`, the model under
    # test both ways - never reads
    # `cross_logit`, so a fetch leg on `features` pays the cross-encoder's own
    # per-document cost (about 81–85 ms a document, chapter 6) once per returned
    # candidate - growing linearly in N - which is not M1's cost at all.
    # `features_second` removes that cost by never
    # invoking the cross-encoder at all, so the "external inference" number
    # is what shipping and scoring M1's own 51 columns actually cost, not
    # what shipping the cross-encoder's homework happened to cost alongside
    # it.
    #
    # `inherits features`, then **replaces** `match-features` rather than
    # adding to it: a `match-features` block in a profile that inherits
    # another fully replaces the parent's list (the same rule
    # `ltr_second.profile` already relies on, cutting `features`'s 52 down to
    # its own `lexical vector max_sim ltr_score`) - so simply never naming
    # `cross_logit` here means its `onnx(cross)` function is never evaluated
    # for a hit under this profile, not merely left off the printed list.
    # Every other function `features.profile` defines (the per-field BM25
    # scores, the token functions, `max_sim`) is still available; this
    # profile only asks for the 51 that are not `cross_logit`, in the exact
    # order `train_ltr.py` logs and trains the `second` model on
    # (`ltr_data.feature_columns(..., "second")`) - the same order
    # `ltr_second_onnx.profile`'s `ltr_input` walks by index, copied here by
    # hand from that list (both are read off the same logged column order,
    # not independently typed).
    match-features {
        title_score
        bullets_score
        description_score
        brand_score

        nativeRank
        nativeFieldMatch
        nativeProximity
        nativeAttributeMatch

        fieldMatch(title)
        fieldMatch(title).proximity
        fieldMatch(title).unweightedProximity
        fieldMatch(title).absoluteProximity
        fieldMatch(title).completeness
        fieldMatch(title).queryCompleteness
        fieldMatch(title).fieldCompleteness
        fieldMatch(title).earliness
        fieldMatch(title).longestSequence
        fieldMatch(title).longestSequenceRatio
        fieldMatch(title).orderness
        fieldMatch(title).outOfOrder
        fieldMatch(title).gaps
        fieldMatch(title).gapLength
        fieldMatch(title).head
        fieldMatch(title).tail
        fieldMatch(title).segments
        fieldMatch(title).occurrence
        fieldMatch(title).weightedOccurrence
        fieldMatch(title).significantOccurrence
        fieldMatch(title).significance
        fieldMatch(title).importance
        fieldMatch(title).relatedness
        fieldMatch(title).matches

        fieldMatch(description).completeness
        fieldMatch(description).proximity
        fieldMatch(description).earliness

        elementCompleteness(bullets).completeness
        elementCompleteness(bullets).queryCompleteness
        elementCompleteness(bullets).fieldCompleteness

        textSimilarity(title).score
        textSimilarity(title).proximity
        textSimilarity(title).order
        textSimilarity(title).queryCoverage
        textSimilarity(title).fieldCoverage

        matches(title)
        matches(bullets)
        matches(description)
        matches(brand)
        queryTermCount

        lexical
        vector
        max_sim
    }
}
