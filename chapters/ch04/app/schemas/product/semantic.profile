rank-profile semantic {
    # The query vector arrives as an input rather than being computed here: the
    # container encodes it once per request, not once per document.
    inputs {
        query(q) tensor<float>(x[384])
    }
    first-phase {
        expression: closeness(field, title_embedding)
    }
    match-features {
        closeness(field, title_embedding)
        distance(field, title_embedding)
    }
}
