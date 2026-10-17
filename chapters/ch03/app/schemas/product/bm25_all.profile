rank-profile bm25_all {
    # Every text field, summed. Summing untransformed BM25 scores across fields
    # is not obviously right - a long description can outweigh an exact title
    # match - and the evaluation is what settles whether it helps.
    function title_score()       { expression: bm25(title) }
    function bullets_score()     { expression: bm25(bullets) }
    function description_score() { expression: bm25(description) }
    function brand_score()       { expression: bm25(brand) }

    match-features {
        title_score
        bullets_score
        description_score
        brand_score
    }

    first-phase {
        expression: title_score + bullets_score + description_score + brand_score
    }
}
