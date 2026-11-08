rank-profile ltr_second_mid inherits features {
    # A middle point on the in-engine shape curve (five points so the
    # curve is a curve and not two dots): 15 leaves x 200 rounds - wider
    # trees than `ltr_second` / `ltr_second_offline`, between them and
    # `ltr_second_large`'s 31 x 800 on both axes. Trained the same way as
    # every other row here (`chapters/ch07/expected/train-second-mid.json`),
    # served in the engine so this row's place in the validation curve is
    # measured, not assumed from the offline grid table alone.
    # See `ltr_second.profile` for why every line below is shaped this way.
    function ltr_score() {
        expression: lightgbm("ltr_second_mid.json")
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
