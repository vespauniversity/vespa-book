rank-profile bm25_k12_b10 {
    rank-properties {
        bm25(title).k1: 1.2
        bm25(title).b: 1.0
    }
    first-phase {
        expression: bm25(title)
    }
}
