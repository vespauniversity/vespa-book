rank-profile bm25_k15_b075 {
    rank-properties {
        bm25(title).k1: 1.5
        bm25(title).b: 0.75
    }
    first-phase {
        expression: bm25(title)
    }
}
