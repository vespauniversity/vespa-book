rank-profile bm25_k20_b04 {
    rank-properties {
        bm25(title).k1: 2.0
        bm25(title).b: 0.4
    }
    first-phase {
        expression: bm25(title)
    }
}
