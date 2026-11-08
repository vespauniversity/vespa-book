rank-profile ltr_second_tiny inherits features {
    # The smallest point on the in-engine shape curve (five points so
    # the curve is a curve and not two dots): 3 leaves x 50 rounds - the same
    # width as `ltr_second` and `ltr_second_offline`, half of
    # `ltr_second`'s rounds. Trained the same way as every other row here
    # (`chapters/ch07/expected/train-second-tiny.json`), served in the
    # engine so this row's place in the validation curve is measured, not
    # assumed from the offline number alone.
    # See `ltr_second.profile` for why every line below is shaped this way.
    function ltr_score() {
        expression: lightgbm("ltr_second_tiny.json")
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
