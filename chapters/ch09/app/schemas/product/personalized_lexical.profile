rank-profile personalized_lexical inherits bm25_tuned {
    # The same brand-context term as `personalized`, added to chapter 3's
    # lexical profile instead of chapter 6's funnel. It exists for one
    # comparison: how much a user's brand context adds when the relevance
    # score underneath it is keyword matching alone, against how much it
    # adds on a funnel whose first stage already reads a vector and whose
    # second phase reranks with token vectors. `bm25_tuned`'s own inputs
    # (`w_qcomplete`, `w_brand` - the weight on a brand word matched in the
    # query) are inherited untouched;
    # the context term's weight has its own name so the two never collide.
    inputs {
        query(user_brands) tensor<float>(brand{})
        query(w_affinity) double: 0
    }

    function brand_affinity() {
        expression: sum(query(user_brands) * tensorFromLabels(attribute(tenant_id), brand))
    }

    # `bm25_tuned`'s expression, copied, plus the one context term. BM25 is
    # unbounded, so the weight that matters here is on its scale, not the
    # fraction that suits the bounded fused first phase.
    first-phase {
        expression {
            bm25(title) +
            query(w_qcomplete) * fieldMatch(title).queryCompleteness +
            query(w_brand)     * matches(brand) +
            query(w_affinity)  * brand_affinity
        }
    }

    match-features {
        brand_affinity
    }
}
