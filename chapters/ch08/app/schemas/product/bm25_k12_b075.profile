rank-profile bm25_k12_b075 {
    # k1 1.2, b 0.75 are Vespa's own defaults, so this profile is the same
    # computation as `bm25_title` - it is chapter 3's k1/b grid's reference
    # point, not an extra argument for a different setting.
    rank-properties {
        bm25(title).k1: 1.2
        bm25(title).b: 0.75
    }
    first-phase {
        expression: bm25(title)
    }
}
