rank-profile bm25_weighted inherits bm25_all {
    # The same features, weighted by where a match is more likely to mean the
    # product is the one asked for. The weights are a hypothesis; the validation
    # split is what tests it. They are query inputs rather than constants so a sweep
    # does not need a redeploy per setting.
    inputs {
        query(w_title)       double: 3.0
        query(w_bullets)     double: 1.0
        query(w_description) double: 0.5
        query(w_brand)       double: 1.0
    }

    first-phase {
        expression {
            query(w_title)       * title_score +
            query(w_bullets)     * bullets_score +
            query(w_description) * description_score +
            query(w_brand)       * brand_score
        }
    }
}
