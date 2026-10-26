rank-profile bm25_title {
    # The smallest thing that could work: one field, one feature.
    first-phase {
        expression: bm25(title)
    }
}
