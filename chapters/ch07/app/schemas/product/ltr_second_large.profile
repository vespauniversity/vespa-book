rank-profile ltr_second_large inherits features {
    # The in-engine "larger than chosen" row of the shape sweep: 31 leaves
    # x 800 rounds, fixed regardless of what the grid picked - the grid's
    # own largest cell, kept as the "bigger is not
    # better" row (`chapters/ch07/expected/train-second-large.json`:
    # the offline validation ndcg@10 there sits below the chosen shape's, a
    # training-side number, not this chapter's headline). This is
    # also the largest model file in the package: `dump_model()`'s JSON for
    # this shape is 9.69 MB on its own, all of it deployed here because every
    # model this chapter measures from is shipped, not shrunk to fit.
    # See `ltr_second.profile` for why every other line below is shaped this
    # way.
    function ltr_score() {
        expression: lightgbm("ltr_second_large.json")
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
