rank-profile bm25_k09_b10 {
    rank-properties {
        bm25(title).k1: 0.9
        bm25(title).b: 1.0
    }
    first-phase {
        expression: bm25(title)
    }
}
