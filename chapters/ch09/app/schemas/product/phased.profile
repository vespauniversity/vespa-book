rank-profile phased inherits hybrid_rrf {
    # Chapter 6's funnel: one cheap first phase over every
    # candidate, then two rerankers of increasing cost applied to shrinking
    # slices of the result. The first phase is not redeclared here - it is
    # `hybrid_rrf`'s own `lexical / (1 + lexical) + vector`, inherited as is,
    # because this profile's argument is what happens after it, not a
    # replacement for it.
    #
    # Each later phase *carries the earlier stage's score forward*
    # instead of replacing it. `phased_replace`, kept beside this
    # profile, is the design that scores each phase with its own reranker
    # alone; measured on top of chapter 6's fused first stage it never
    # beats reranking nothing at all - a reranker whose expression
    # throws away the stage before it is competing with that stage, not
    # improving on it. This profile adds a scaled reranker score to what came
    # before instead.
    inputs {
        query(q) tensor<float>(x[384])
        query(qt) tensor<float>(querytoken{}, v[128])
        query(qt_cross) tensor<float>(d0[32])
        # `w_sim` scales `max_sim` onto the first phase's own scale before the
        # two are added (below). `w_cross` is the global phase's blend weight
        # between the cross-encoder and the score carried up from the second
        # phase. Both are query inputs, not constants: a request can override
        # either, both rerank counts, or both, and chapter 6's validation
        # sweeps chose their values that way, one input at a time - these are
        # the validation-chosen values, not placeholders; a request can still
        # override either.
        query(w_sim) double: 0.002
        query(w_cross) double: 0.7
    }

    # Late interaction. Instead of comparing one vector for the query against
    # one vector for the product, every query token is compared against every
    # title token and each query token keeps its best match. That is what
    # MaxSim is: a sum over every query token's best match, not a distance an
    # HNSW graph can search by, so it reorders candidates something else found.
    function max_sim() {
        expression {
            sum(
                reduce(
                    sum(
                        query(qt) * unpack_bits(attribute(colbert)), v
                    ),
                    max, token
                ),
                querytoken
            )
        }
    }

    # The cross-encoder reads the query and the document together rather than
    # comparing two independently-computed vectors, so it cannot be reduced to
    # a stored embedding: what it needs is prepared here from the query's
    # tokens and the document's precomputed `text_tokens` (title + bullets)
    # - what the model is given to read decides what it can add, and the
    # first phase already reads only the title and brand as text. 320 is the
    # padded input window for 32 query tokens + 256 document tokens + 3
    # specials (291, padded to 320), comfortably under MiniLM's 512-token
    # limit.
    #
    # The model itself (`onnx-model cross`) is declared once at schema level,
    # not here - every profile that scores with it refers to that one
    # declaration (`product.sd`). Only these token functions live per profile,
    # because they are what decide which field the model reads.
    function input_ids() {
        expression: tokenInputIds(320, query(qt_cross), attribute(text_tokens))
    }
    function token_type_ids() {
        expression: tokenTypeIds(320, query(qt_cross), attribute(text_tokens))
    }
    function attention_mask() {
        expression: tokenAttentionMask(320, query(qt_cross), attribute(text_tokens))
    }

    # The cross-encoder's own logit, on its own scale, named so the global
    # phase below can normalise it without repeating the expression.
    function cross_logit() {
        expression: onnx(cross).logits{d0:0,d1:0}
    }

    match-features {
        lexical
        vector
        max_sim
    }

    # Second phase: ColBERT MaxSim, run on each content node over the
    # candidates the first phase let through. Its knob is
    # `ranking.rerankCount` - a per-request override of the count below.
    #
    # `max_sim` is added to `firstPhase`, not used in place of it. For one
    # worked query on this corpus `max_sim` came out around 119-129 while
    # `firstPhase` (the bounded `lexical / (1 + lexical) + vector` sum) sat
    # around 1-2, so `query(w_sim)` is not a taste parameter - it is the scale
    # factor that keeps a hundred-point MaxSim score from simply overriding a
    # two-point first phase, which would be `phased_replace` under a
    # different name. This is what feature normalisation means here:
    # `normalize_linear` exists only in the global phase (used below), so
    # here the two scores are put on a comparable footing by hand, with a
    # weight rather than a rank-window normalisation.
    second-phase {
        rerank-count: 25
        expression: firstPhase + query(w_sim) * max_sim
    }

    # Global phase: the cross-encoder, run once results from every content
    # node have been merged, over the survivors of the second phase. Its knob
    # is `ranking.globalPhase.rerankCount`, a different query parameter from
    # `ranking.rerankCount` above because it overrides a different phase.
    # Setting the wrong one is silent: the query still succeeds, and on
    # `phased`, which has both phases, the other reranker's count moves
    # while the one you meant stays at the profile default.
    #
    # Two scores on unrelated scales - a cross-encoder logit and the second
    # phase's own (already-blended) score - are each squashed to [0,1] over
    # this rerank window by `normalize_linear` and then blended by
    # `query(w_cross)`, rather than one replacing the other the way
    # `phased_replace`'s global phase does.
    global-phase {
        rerank-count: 10
        expression {
            query(w_cross) * normalize_linear(cross_logit) +
            (1 - query(w_cross)) * normalize_linear(secondPhase)
        }
    }
}
