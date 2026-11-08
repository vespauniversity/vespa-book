rank-profile bm25_k06_b075 {
    rank-properties {
        bm25(title).k1: 0.6
        bm25(title).b: 0.75
    }
    first-phase {
        expression: bm25(title)
    }
}
