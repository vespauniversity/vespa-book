rank-profile features inherits hybrid_rrf {
    # Not a reranker: a logging profile. Its job is to compute and record
    # the fifty-two rank features its `match-features` block names, for every
    # judged (query, product) pair, for chapter 7 to learn a ranking function
    # from. `bm25(title)`'s k1 and b are not set again here - they come from
    # `bm25_tuned`, which `hybrid_rrf` already inherits from, and this
    # profile inherits `hybrid_rrf` in turn. Ordering here is not what is
    # logged, so the inherited first phase and global phase are left as they
    # are.
    inputs {
        query(q) tensor<float>(x[384])
        query(qt) tensor<float>(querytoken{}, v[128])
        query(qt_cross) tensor<float>(d0[32])
    }

    # Late interaction, the same expression the funnel profile scores with:
    # every query token compared against every title token, each query token
    # keeping its best match.
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

    # The cross-encoder's own logit, for chapter 7 to learn from as a
    # feature rather than to rerank with here - this is a logging profile, so
    # the inherited first phase and global phase still decide ordering, and
    # this is computed only because `match-features` asks for it below.
    # Scores with the same `onnx-model cross` declared once at schema level
    # (`product.sd`) - this profile does not inherit `phased`'s rank
    # profile, but it refers to that one declaration the same way `phased`
    # and `phased_replace` do. Token functions copied from `phased.profile`:
    # the same 320-token input window (32 query tokens + 256 document tokens
    # + 3 specials = 291, padded to 320) and the same `text_tokens` field -
    # title + bullets.
    function input_ids() {
        expression: tokenInputIds(320, query(qt_cross), attribute(text_tokens))
    }
    function token_type_ids() {
        expression: tokenTypeIds(320, query(qt_cross), attribute(text_tokens))
    }
    function attention_mask() {
        expression: tokenAttentionMask(320, query(qt_cross), attribute(text_tokens))
    }

    function cross_logit() {
        expression: onnx(cross).logits{d0:0,d1:0}
    }

    # Every text field's own BM25, unsummed and unweighted - not the
    # `lexical()` combination `hybrid_rrf` scores with, but the plain
    # per-field number a learned ranker can weigh for itself.
    function title_score()       { expression: bm25(title) }
    function bullets_score()     { expression: bm25(bullets) }
    function description_score() { expression: bm25(description) }
    function brand_score()       { expression: bm25(brand) }

    match-features {
        # The per-field BM25 scores above.
        title_score
        bullets_score
        description_score
        brand_score

        # Vespa's own composite scores.
        nativeRank
        nativeFieldMatch
        nativeProximity
        nativeAttributeMatch

        # How well the query matched the title, taken apart: where the terms
        # landed, how close together, in what order, how much of the query
        # they covered. This is the family a learned ranker has most to
        # learn from.
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

        # A second text field, so a learned ranker can weigh title against
        # body.
        fieldMatch(description).completeness
        fieldMatch(description).proximity
        fieldMatch(description).earliness

        # Arrays match differently from free text. `attributeMatch` is not
        # here: brand is declared as both index and attribute, the query
        # matches it through the index, and the feature refuses to set up
        # against a field it is not matching through that way.
        elementCompleteness(bullets).completeness
        elementCompleteness(bullets).queryCompleteness
        elementCompleteness(bullets).fieldCompleteness

        # Ratio-shaped similarities, bounded unlike bm25.
        textSimilarity(title).score
        textSimilarity(title).proximity
        textSimilarity(title).order
        textSimilarity(title).queryCoverage
        textSimilarity(title).fieldCoverage

        # Which fields matched at all, and how long the query was.
        matches(title)
        matches(bullets)
        matches(description)
        matches(brand)
        queryTermCount

        # The retrieval side: chapter 6's first-stage features, so a
        # learned ranker sees the lexical and vector signals the funnel
        # itself is built from, plus the late-interaction score above.
        lexical
        vector
        max_sim

        # The cross-encoder's own logit, logged last so a learned ranker
        # can weigh it: the most expensive of chapter 6's signals, and the
        # only score the funnel ranks by that reads the bullets - text the
        # cheap first phase never scores.
        cross_logit
    }
}
