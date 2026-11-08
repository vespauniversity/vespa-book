rank-profile ltr_second inherits features {
    # The placement rule's second-phase model: a model trained on every
    # feature the second phase can afford to compute for every candidate at
    # depth - 51 columns, everything `features.profile` logs except
    # `cross_logit`, which exists only where the cross-encoder ran and so
    # would cost a cross-encoder run on all 400 candidates as a second-phase
    # feature, not the ten the global phase reranks (`docs/pins.md`,
    # `cross-encoder`).
    #
    # **Which shape this name serves is chosen in the engine, not offline:**
    # the offline grid over this same log picked 3 leaves x 200 rounds by
    # its own validation ndcg@10, but in retrieval mode - the task this
    # chapter's numbers are printed from - that pick sat inside the noise
    # against the first stage alone while the smaller, 3 x 100 shape cleared
    # it real. `ltr_second` is 3 leaves x 100 rounds, chosen from an earlier
    # in-engine reading of three shapes before the five-shape sweep, and
    # kept as the engine's own pick; the offline grid's own pick is kept,
    # unchanged, as its own row - `ltr_second_offline.profile` - so a reader
    # can see both selection methods side by side rather than only the one
    # this chapter chose. See `ltr_second_offline.profile`,
    # `ltr_second_tiny.profile` and `ltr_second_mid.profile` for the rest of
    # the shape curve.
    #
    # `inherits features`, not `hybrid_rrf`: `features` is ch06's logging
    # profile - it already carries `lexical`, `vector`, `max_sim` and every
    # `fieldMatch` / `nativeRank` / `textSimilarity` function this model was
    # trained on, by the exact names `train_ltr.py` logged them under and
    # `lightgbm(...)` maps to rank features by name. Both later phases are
    # overridden below because `features` inherits `hybrid_rrf`'s own RRF
    # global phase (`reciprocal_rank_fusion(lexical, vector)`), which would
    # otherwise re-sort whatever this profile's second phase ranks: a
    # profile that inherits another inherits its phases too, unless it
    # overrides them.

    # LightGBM's own trees, read from the `dump_model()` JSON `train_ltr.py`
    # wrote (this is the only format
    # `lightgbm(...)` reads; the sibling `.onnx` file is a different export,
    # scored by `ltr_second_onnx` below, not this profile).
    function ltr_score() {
        expression: lightgbm("ltr_second.json")
    }

    match-features {
        lexical
        vector
        max_sim
        ltr_score
    }

    # Every candidate the first phase let through (depth 400, this chapter's
    # union retrieval) gets the learned score. `rerank-count` here is a
    # per-request knob (`ranking.rerankCount`, chapter 6's `phased.profile`);
    # 400 asks for every one of them, because the whole point of M1 (M1 =
    # the second-phase model, trained without `cross_logit`; M2 = the
    # global-phase model, trained with it) - the placement rule - is that
    # this model can afford to see every candidate, not a shrinking slice of
    # them.
    second-phase {
        rerank-count: 400
        expression: ltr_score
    }

    # M1 places nothing in the global phase - there is no second model here,
    # only the second phase's own score carried through. `rerank-count: 0`
    # is the direct way to say "global phase touches nothing", and Vespa
    # accepts it at deploy; the expression still scores `secondPhase`
    # unchanged.
    global-phase {
        rerank-count: 0
        expression: secondPhase
    }
}
