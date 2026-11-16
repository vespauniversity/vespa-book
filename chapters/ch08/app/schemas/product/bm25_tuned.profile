rank-profile bm25_tuned {
    # A shopper types "running shoes men" against a title field where most
    # titles are one short line. BM25's default k1 assumes a body of text
    # where a word repeating five or six times is a real signal of what the
    # document is about; term frequency keeps adding score for a long stretch
    # before it saturates. A title does not have that room - "Running Shoes
    # Men Running Sneakers" repeating "Running" is padding, not aboutness, and
    # the default k1 would still reward the second occurrence - less than the
    # first, about a third of it. Lowering k1 to 0.6 makes saturation happen
    # fast: the first occurrence of a term in the title earns most of what
    # that term can contribute, and a second occurrence buys noticeably less
    # than it would at the default - so a padded title gains less from
    # repetition. `b` stays at 0.75, Vespa's default, which is the
    # length-normalisation knob, not the one this data asked us to touch.
    #
    # BM25 on its own only asks "how rare and how frequent are the words that
    # matched", not "did all of the query's words show up". Two titles can
    # match the same total BM25 weight while one has every query term and the
    # other is missing one - and a shopper who typed "red running shoes"
    # wanted all three words, not two out of three. `fieldMatch(title).query
    # Completeness` is exactly that share: 3 of 3 query terms found in the
    # title scores 1.0, 2 of 3 scores 0.67. Multiplying it by 5.0 means a
    # title with every query term present gets a flat +5 on top of its BM25
    # score, enough to move it ahead of a partial match that only won on
    # rarity. `matches(brand)` adds a smaller, flat +1 when the query's words
    # also hit the brand field, on the same idea: a query that names the
    # brand and gets it back is a query that found what it asked for.
    #
    # Both boosts are declared as query inputs, not literals in the
    # expression, so trying a different weight - 3.0 instead of 5.0 - is a
    # query parameter on the next request, not a redeploy of this file. That
    # is what makes chapter 3's boost sweep possible at all.
    rank-properties {
        bm25(title).k1: 0.6
        bm25(title).b: 0.75
    }
    inputs {
        query(w_qcomplete) double: 5.0
        query(w_brand)     double: 1.0
    }
    first-phase {
        expression {
            bm25(title) +
            query(w_qcomplete) * fieldMatch(title).queryCompleteness +
            query(w_brand)     * matches(brand)
        }
    }
}
