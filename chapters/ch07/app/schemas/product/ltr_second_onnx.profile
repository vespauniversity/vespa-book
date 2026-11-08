rank-profile ltr_second_onnx inherits features {
    # The ONNX sibling of `ltr_second` (both formats are
    # served and measured) - the same trained trees
    # (`export_onnx.py`'s parity report, `expected/export-second.json`,
    # checks the two agree), read here through `onnx(...)` instead of
    # `lightgbm(...)`. Same placement, same 51 features, same reasons for
    # `inherits features` and for overriding both later phases - see
    # `ltr_second.profile`.
    #
    # Always the chosen shape's ONNX, not the offline pick's: this
    # profile's model is exported from the same file `ltr_second` was
    # trained into (`chapters/ch07/models_native/ltr_second.lgb`), so
    # `ltr_second` and `ltr_second_onnx` are always the same
    # trees, one native, one ONNX, and there is no `ltr_second_offline_onnx`
    # because the offline row is a comparison point, not a served format
    # this chapter also demonstrates ONNX for.
    #
    # A cross-encoder reads the query and one document's tokens; this model
    # reads 51 already-computed numbers, so its input is not a field but a
    # tensor built from this profile's own functions and features, in the
    # exact order `train_ltr.py` logged and trained on - generated here by
    # `export_onnx.py --model chapters/ch07/models_native/ltr_second.lgb
    # --profile-snippet`, not typed by hand, so the profile's input can never
    # silently drift from what the model was trained on - the shape check,
    # settled by construction. `onnx-model ltr_second_onnx` is declared once at
    # schema level (`product.sd`, beside `onnx-model cross`) and binds its
    # `input` to this function by name.
    #
    # A generator, `tensor<float>(d0[1],d1[51])(<expr over d1>)`, not a
    # tensor literal (`vespa deploy` rejected both
    # the array short form and the addressed-cell form - a literal's cells
    # can only be constants). The generator's expression is evaluated once
    # per cell with `d1` bound to that cell's index, walked down to one
    # feature by an `if (d1 == i, feature_i, ...)` chain - ugly to read by
    # hand at 51 deep, which is why nothing hand-types it.
    function ltr_input() {
        expression: tensor<float>(d0[1],d1[51])(if (d1 == 0, title_score, if (d1 == 1, bullets_score, if (d1 == 2, description_score, if (d1 == 3, brand_score, if (d1 == 4, nativeRank, if (d1 == 5, nativeFieldMatch, if (d1 == 6, nativeProximity, if (d1 == 7, nativeAttributeMatch, if (d1 == 8, fieldMatch(title), if (d1 == 9, fieldMatch(title).proximity, if (d1 == 10, fieldMatch(title).unweightedProximity, if (d1 == 11, fieldMatch(title).absoluteProximity, if (d1 == 12, fieldMatch(title).completeness, if (d1 == 13, fieldMatch(title).queryCompleteness, if (d1 == 14, fieldMatch(title).fieldCompleteness, if (d1 == 15, fieldMatch(title).earliness, if (d1 == 16, fieldMatch(title).longestSequence, if (d1 == 17, fieldMatch(title).longestSequenceRatio, if (d1 == 18, fieldMatch(title).orderness, if (d1 == 19, fieldMatch(title).outOfOrder, if (d1 == 20, fieldMatch(title).gaps, if (d1 == 21, fieldMatch(title).gapLength, if (d1 == 22, fieldMatch(title).head, if (d1 == 23, fieldMatch(title).tail, if (d1 == 24, fieldMatch(title).segments, if (d1 == 25, fieldMatch(title).occurrence, if (d1 == 26, fieldMatch(title).weightedOccurrence, if (d1 == 27, fieldMatch(title).significantOccurrence, if (d1 == 28, fieldMatch(title).significance, if (d1 == 29, fieldMatch(title).importance, if (d1 == 30, fieldMatch(title).relatedness, if (d1 == 31, fieldMatch(title).matches, if (d1 == 32, fieldMatch(description).completeness, if (d1 == 33, fieldMatch(description).proximity, if (d1 == 34, fieldMatch(description).earliness, if (d1 == 35, elementCompleteness(bullets).completeness, if (d1 == 36, elementCompleteness(bullets).queryCompleteness, if (d1 == 37, elementCompleteness(bullets).fieldCompleteness, if (d1 == 38, textSimilarity(title).score, if (d1 == 39, textSimilarity(title).proximity, if (d1 == 40, textSimilarity(title).order, if (d1 == 41, textSimilarity(title).queryCoverage, if (d1 == 42, textSimilarity(title).fieldCoverage, if (d1 == 43, matches(title), if (d1 == 44, matches(bullets), if (d1 == 45, matches(description), if (d1 == 46, matches(brand), if (d1 == 47, queryTermCount, if (d1 == 48, lexical, if (d1 == 49, vector, max_sim)))))))))))))))))))))))))))))))))))))))))))))))))))
    }

    # `variable` is not a name chosen here: it is what `onnxmltools` names a
    # LightGBM regressor's output when the conversion does not ask for
    # another one (`export_onnx.py`'s conversion call), confirmed against
    # the deployed file with `onnxruntime`'s own `get_outputs()`. `{d0:0,
    # d1:0}` reads the one score back out of the `[1,1]` tensor the model
    # returns for a single row.
    function ltr_score() {
        expression: onnx(ltr_second_onnx).variable{d0:0,d1:0}
    }

    match-features {
        lexical
        vector
        max_sim
        ltr_score
    }

    second-phase {
        rerank-count: 400
        expression: ltr_score
    }

    global-phase {
        rerank-count: 0
        expression: secondPhase
    }
}
