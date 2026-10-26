rank-profile bm25_k12_b04 {
    rank-properties {
        bm25(title).k1: 1.2
        bm25(title).b: 0.4
    }
    first-phase {
        expression: bm25(title)
    }
}
