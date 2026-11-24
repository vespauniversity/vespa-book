rank-profile phased_replace inherits hybrid_rrf {
    # Chapter 6's negative example, kept so the reader can see why
    # the real funnel below (`phased`) is built the way it is. Every phase
    # here *replaces* the score the phase before it computed - second-phase
    # scores with `max_sim` alone, global-phase with the cross-encoder logit
    # alone - so each reranker competes with the stage in front of it instead
    # of adding to it. Measured: on top of chapter 6's fused first stage,
    # ColBERT's second phase never beats reranking nothing -
    # every rerank count from 25 upward is at or below the floor, and 100 and
    # above are a real decline. As reasoning rather than a measurement here:
    # replacing a strong stage's score loses more than replacing a weak
    # one's. The first phase is not redeclared here - it is
    # `hybrid_rrf`'s own `lexical / (1 + lexical) + vector`, inherited as is;
    # this profile's argument is that inheriting it is not enough once a
    # later phase throws its score away.
    inputs {
        query(q) tensor<float>(x[384])
        query(qt) tensor<float>(querytoken{}, v[128])
        query(qt_cross) tensor<float>(d0[32])
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
    # tokens and the document's precomputed `title_tokens`.
    #
    # Scores with the same `onnx-model cross` declared once at schema level
    # (`product.sd`) - the one declaration this profile, `phased` and
    # `features` all refer to.
    function input_ids() {
        expression: tokenInputIds(96, query(qt_cross), attribute(title_tokens))
    }
    function token_type_ids() {
        expression: tokenTypeIds(96, query(qt_cross), attribute(title_tokens))
    }
    function attention_mask() {
        expression: tokenAttentionMask(96, query(qt_cross), attribute(title_tokens))
    }

    match-features {
        lexical
        vector
        max_sim
    }

    # Second phase: ColBERT MaxSim, run on each content node over the
    # candidates the first phase let through. Its knob is
    # `ranking.rerankCount` - a per-request override of the count below.
    second-phase {
        rerank-count: 100
        expression: max_sim
    }

    # Global phase: the cross-encoder, run once results from every content
    # node have been merged, over the survivors of the second phase. Its knob
    # is `ranking.globalPhase.rerankCount`, a different query parameter from
    # `ranking.rerankCount` above because it overrides a different phase.
    # Setting the wrong one is silent: the query still succeeds, and on
    # `phased_replace`, which has both phases, the other reranker's count
    # moves while the one you meant stays at the profile default.
    global-phase {
        rerank-count: 50
        expression: onnx(cross).logits{d0:0,d1:0}
    }
}
