rank-profile personalized inherits phased {
    # `phased` is ch06's funnel: a fused first stage, a ColBERT second
    # phase, a cross-encoder global phase. This profile adds three terms to
    # it, each reading one part of a user's intent context - the brands and
    # the colours of the products that satisfied their earlier queries, and
    # the mean vector of those products - and adds them
    # in the first phase, so every later phase (which carries the first
    # phase's score forward rather than replacing it, `phased`'s own
    # comment says why) keeps the term all the way to the top of the
    # funnel. The global phase (the cross-encoder) is switched off for this
    # profile's own measurements by the request itself, with
    # `ranking.globalPhase.rerankCount=0` - the same per-request knob
    # chapter 6 already uses to turn a phase off without touching the
    # profile - so nothing below this comment needs to change; `second-phase`
    # and `global-phase` are inherited exactly as `phased` wrote them.
    inputs {
        # A mapped tensor: instead of a fixed list of positions (like
        # `profile_vector`'s 384 numbers, one per position), this tensor has
        # one cell per brand *label* the request supplies - "nike", "adidas",
        # whatever brands this particular user's judgements touched - and
        # nothing for every other brand in the corpus. The size is not fixed
        # up front because which brands a user has an opinion about is not
        # fixed up front either.
        query(user_brands) tensor<float>(brand{})
        # The weight this term carries, as a request input rather than a
        # constant baked into the expression. Left at 0 by default: a
        # request that never sets `w_affinity` gets exactly `phased`'s own
        # first-phase score back, unchanged, which is what makes this
        # profile the unpersonalized baseline until a request chooses
        # otherwise. The tuning half of chapter 9's evaluation picks the
        # weight that gets set here; that choice is not this file. The name
        # is deliberately not `w_brand`: that input already exists up the
        # inheritance chain (the weight on a brand word matched in the query,
        # from chapter 3's profile) and redeclaring it here would silently
        # change that term too.
        query(w_affinity) double: 0
        # The same two inputs for colour: a mapped tensor over the colour
        # strings a user's judged products carried, and its weight. Colour
        # is here so the chapter can measure it with the same machinery as
        # brand and report what it finds either way; a request that sets
        # neither leaves both terms at 0.
        query(user_colours) tensor<float>(colour{})
        query(w_colour) double: 0
        # The user's profile vector - the same 384 numbers the recommendation
        # request sends as its query - and its weight. With a query present
        # this is a second opinion on every candidate: how close the product
        # sits to what this person has judged relevant before, regardless of
        # the words they typed.
        query(user_vector) tensor<float>(x[384])
        query(w_vector) double: 0
    }

    # `tensorFromLabels` turns a single-value attribute into a one-cell
    # mapped tensor: it reads `attribute(tenant_id)` on this document (the
    # normalised brand string ch08 already fills for every product,
    # reused here as an identity rather than a filter clause) and returns a
    # tensor with weight 1 at the cell whose label is that string - `{nike:
    # 1.0}` for a Nike product, `{acme: 1.0}` for an Acme product. Multiplying
    # that one-cell tensor against the user's whole `user_brands`
    # distribution and summing keeps only the one cell that lines up: the
    # weight the user's own context assigns to *this document's* brand. A
    # product whose brand never appears in the user's distribution
    # contributes 0.
    function brand_affinity() {
        expression: sum(query(user_brands) * tensorFromLabels(attribute(tenant_id), brand))
    }

    # The same lookup on the product's `color` attribute (the raw ESCI
    # string, so the user's colour distribution is built from the same raw
    # strings); one cell lights up when this product's colour is one the
    # user's context carries.
    function colour_affinity() {
        expression: sum(query(user_colours) * tensorFromLabels(attribute(color), colour))
    }

    # The dot product of the user's vector with the product's title vector.
    # The product side is unit length (the embedder normalises its output);
    # the stored profile is a plain mean, so the request normalises it before
    # sending, and the term is then the cosine between the two - the
    # quantity behind the closeness the recommendation request ranks by -
    # here one more term rather than the whole score. A request that sends
    # no vector leaves it at 0.
    function vector_affinity() {
        expression: sum(query(user_vector) * attribute(title_embedding))
    }

    # `phased` inherits `hybrid_rrf`'s first phase as is: `lexical / (1 +
    # lexical) + vector`. This profile copies that same expression rather
    # than inheriting it silently, because the whole point of this profile
    # is to add three more terms to it - `query(w_affinity) * brand_affinity()`,
    # its colour twin, and the vector term -
    # so a request that weights the brand term heavily (a high `w_affinity`) can
    # move a product with a small lexical/vector score above one with a
    # bigger score but a brand this user has shown no interest in. Nothing
    # else in `first-phase` changes.
    first-phase {
        expression: lexical / (1 + lexical) + vector + query(w_affinity) * brand_affinity + query(w_colour) * colour_affinity + query(w_vector) * vector_affinity
    }

    # Same list `phased` declares, with the three context terms added so a
    # request can read each term's own contribution alongside the funnel's
    # existing features.
    match-features {
        lexical
        vector
        max_sim
        brand_affinity
        colour_affinity
        vector_affinity
    }
}
