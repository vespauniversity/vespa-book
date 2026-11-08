rank-profile ltr_second_offline inherits features {
    # The offline grid's own pick, kept as its own row rather than
    # overwritten: LightGBM's own validation ndcg@10, computed only over
    # judged pairs (`train_ltr.py --grid`), picked 3 leaves x 200 rounds -
    # the same 3-leaf width `ltr_second` settled on, twice the rounds. In
    # retrieval mode (400 candidates, most unjudged - the task this
    # chapter's own numbers come from) that pick sits inside the noise
    # against the first stage alone, while `ltr_second`'s 3 x 100 clears it
    # real (`chapters/ch07/expected/compare-validation-vs-first-stage.
    # block.md`). This row is the point of the comparison: the model that
    # wins by the training-side metric is not the model that wins by the
    # metric the book prints (offline selection, not only offline scoring,
    # can disagree with the engine).
    # See `ltr_second.profile` for why every line below is shaped this way.
    function ltr_score() {
        expression: lightgbm("ltr_second_offline.json")
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
