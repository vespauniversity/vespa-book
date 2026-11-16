rank-profile explained inherits bm25_weighted {
    # Not for ranking - for looking, at one query rather than at a run.
    #
    # The four `*_score` components are inherited from `bm25_weighted`, which
    # already exposes all four, so they are not what this profile adds and
    # they cost nothing: the ranking computed them to make the score.
    #
    # What it adds is the six below them, and not one of those is in the
    # score at all. Five say how well the query matched the title, including
    # whether its words landed near each other, so a disappointing result can
    # be read against what the scoring function is ignoring; the sixth,
    # `queryTermCount`, is just how many terms the query had, and is here
    # because the other five read differently for a one-word query.
    #
    # Which is also why this is a profile you switch to rather than something
    # the default does all day: nothing in the expression needs any of them,
    # so asking for them is asking Vespa for work it would otherwise have
    # skipped, on every document that matched.
    match-features {
        title_score
        bullets_score
        description_score
        brand_score
        nativeRank(title)
        nativeProximity(title)
        fieldMatch(title)
        fieldMatch(title).proximity
        fieldMatch(title).completeness
        queryTermCount
    }
}
