rank-profile phased_title inherits phased {
    # Chapter 6's control for "what the model is given to read decides
    # what it can add": the same cross-encoder, the same funnel, the
    # same weights - only the three token functions are overridden, back to
    # `title_tokens` (96 tokens, title alone) instead of `phased`'s
    # `text_tokens` (256 tokens, title + bullets). Everything else - the
    # first phase, `max_sim`, the second-phase and global-phase expressions,
    # `w_sim` / `w_cross` - is inherited unchanged, so the only thing that can
    # move between `phased_title` and `phased` is what the cross-encoder read.
    function input_ids() {
        expression: tokenInputIds(96, query(qt_cross), attribute(title_tokens))
    }
    function token_type_ids() {
        expression: tokenTypeIds(96, query(qt_cross), attribute(title_tokens))
    }
    function attention_mask() {
        expression: tokenAttentionMask(96, query(qt_cross), attribute(title_tokens))
    }
}
