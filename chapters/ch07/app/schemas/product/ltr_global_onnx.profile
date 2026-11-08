rank-profile ltr_global_onnx inherits ltr_second_onnx {
    # The ONNX sibling of `ltr_global` (both formats are
    # served and measured), the same way `ltr_second_onnx`
    # is `ltr_second`'s. `inherits ltr_second_onnx` keeps its `second-phase` -
    # 400 candidates scored by the *M1* ONNX model (M1 = the second-phase
    # model, trained without `cross_logit`; M2 = the global-phase model,
    # trained with it), via the inherited
    # `ltr_input` / `ltr_score` and the schema's `onnx-model
    # ltr_second_onnx` - untouched, for the same reason `ltr_global` does
    # not touch `ltr_second`'s: this profile is only asking what the global
    # phase adds on top of it.
    #
    # This is the ONNX export of the M2 shape chosen before its own validation
    # run, `ltr_global` (3 x 100), which the in-engine validation run kept;
    # there is no `ltr_global_200_onnx` for the same reason there is no
    # `ltr_second_offline_onnx` - the other shape is a comparison point, not
    # a second format this chapter also demonstrates ONNX for.
    #
    # A second, 52-wide input for the model that also reads `cross_logit`
    # (generated the same way as `ltr_second_onnx`'s - see its own comment
    # for why this is a generator's `if` chain, not a tensor literal - from
    # `chapters/ch07/models_native/ltr_global.lgb`), under a different
    # function name so it cannot be confused with the inherited 51-wide one -
    # the schema's `onnx-model ltr_global_onnx` binds its own `input` to
    # this function, not to `ltr_input`.
    function ltr_input_global() {
        expression: tensor<float>(d0[1],d1[52])(if (d1 == 0, title_score, if (d1 == 1, bullets_score, if (d1 == 2, description_score, if (d1 == 3, brand_score, if (d1 == 4, nativeRank, if (d1 == 5, nativeFieldMatch, if (d1 == 6, nativeProximity, if (d1 == 7, nativeAttributeMatch, if (d1 == 8, fieldMatch(title), if (d1 == 9, fieldMatch(title).proximity, if (d1 == 10, fieldMatch(title).unweightedProximity, if (d1 == 11, fieldMatch(title).absoluteProximity, if (d1 == 12, fieldMatch(title).completeness, if (d1 == 13, fieldMatch(title).queryCompleteness, if (d1 == 14, fieldMatch(title).fieldCompleteness, if (d1 == 15, fieldMatch(title).earliness, if (d1 == 16, fieldMatch(title).longestSequence, if (d1 == 17, fieldMatch(title).longestSequenceRatio, if (d1 == 18, fieldMatch(title).orderness, if (d1 == 19, fieldMatch(title).outOfOrder, if (d1 == 20, fieldMatch(title).gaps, if (d1 == 21, fieldMatch(title).gapLength, if (d1 == 22, fieldMatch(title).head, if (d1 == 23, fieldMatch(title).tail, if (d1 == 24, fieldMatch(title).segments, if (d1 == 25, fieldMatch(title).occurrence, if (d1 == 26, fieldMatch(title).weightedOccurrence, if (d1 == 27, fieldMatch(title).significantOccurrence, if (d1 == 28, fieldMatch(title).significance, if (d1 == 29, fieldMatch(title).importance, if (d1 == 30, fieldMatch(title).relatedness, if (d1 == 31, fieldMatch(title).matches, if (d1 == 32, fieldMatch(description).completeness, if (d1 == 33, fieldMatch(description).proximity, if (d1 == 34, fieldMatch(description).earliness, if (d1 == 35, elementCompleteness(bullets).completeness, if (d1 == 36, elementCompleteness(bullets).queryCompleteness, if (d1 == 37, elementCompleteness(bullets).fieldCompleteness, if (d1 == 38, textSimilarity(title).score, if (d1 == 39, textSimilarity(title).proximity, if (d1 == 40, textSimilarity(title).order, if (d1 == 41, textSimilarity(title).queryCoverage, if (d1 == 42, textSimilarity(title).fieldCoverage, if (d1 == 43, matches(title), if (d1 == 44, matches(bullets), if (d1 == 45, matches(description), if (d1 == 46, matches(brand), if (d1 == 47, queryTermCount, if (d1 == 48, lexical, if (d1 == 49, vector, if (d1 == 50, max_sim, cross_logit))))))))))))))))))))))))))))))))))))))))))))))))))))
    }

    function ltr_score_global() {
        expression: onnx(ltr_global_onnx).variable{d0:0,d1:0}
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

    global-phase {
        rerank-count: 10
        expression: ltr_score_global
    }
}
