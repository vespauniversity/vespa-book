# Late interaction, as an add-on

This page describes a second kind of vector representation and shows exactly
what adding it to this chapter's application would take. **Nothing on it is
measured in this chapter**: no component below is in `app/`, nothing under
`expected/` was taken with it deployed, and no number is quoted. It is here
because what "multi-vector" means, and why the same tensor machinery carries
it, is a question about representation, not about a result. What late
interaction buys when it reranks candidates is a reranking question, which a
later chapter takes up.

## One vector, or one per token

The embedder the chapter deploys turns a whole title into **one** vector:
`tensor<float>(x[384])`, one cell per dimension, nothing else. Two titles are
compared by one dot product. That is cheap to store, cheap to index (HNSW works
over single points) and cheap to compare, and it loses something: the whole
title has been squeezed through 384 numbers before the query ever meets it.

ColBERT keeps a vector **per token** instead. A product's title becomes a
tensor with two dimensions — which token, and the vector for that token —
declared in Vespa as `tensor<int8>(token{}, v[16])`: `token{}` is a *mapped*
dimension (a label per token, however many there are), `v[16]` an *indexed* one
(sixteen cells per token). The query is encoded the same way. At scoring time
every query token is compared with every product token, each query token keeps
its best match, and those best matches are summed. That is **MaxSim**, and it
is what "late interaction" means: the two sides interact token by token, late,
at ranking time, instead of being collapsed to one point each beforehand.

Two consequences follow directly from the shape, before anything is measured:

- **It is not a distance an HNSW graph can search by.** MaxSim is a sum over
  every query token's best match, so it is used to *reorder* candidates
  something else already found, not to *find* them. That is why the profile
  below runs it in `second-phase`, over what the single-vector search already
  retrieved.
- **It is stored small and computed large.** Sixteen bytes a token, so a
  hundred-token title is 1.6 kilobytes by construction — affordable to keep.
  The cost is at indexing time, where the model runs once per document and
  emits a vector for every token, and at query time, where every pair of
  tokens is compared for every candidate reranked.

The tensor type system is the point of the page as much as ColBERT is: the
dense field the chapter measures, the token tensor here, and a per-user or
per-feature tensor a later chapter might add are the same kind of thing to
Vespa — a typed, named-dimension array that indexing expressions fill and rank
expressions read — which is how the tensor model generalises beyond a single
dense vector.

## Adding it

Three edits, then a redeploy and a re-feed (the vectors are computed when a
document is fed, so documents already in the index do not gain the field).
Every URL is pinned to a commit, as in `docs/pins.md`: a Hugging Face
repository is edited in place, and an unpinned URL fetches different weights on
a later deploy without saying so.

`services.xml`, beside the existing embedder:

```xml
<!-- A second model, of a different kind. The bi-encoder above turns a
     whole text into one vector. ColBERT keeps a vector per token and
     compares them pairwise at query time, which is more faithful and more
     expensive - the reason it belongs late in a ranking pipeline rather
     than in retrieval. -->
<component id="colbert" type="colbert-embedder">
  <transformer-model
    url="https://huggingface.co/colbert-ir/colbertv2.0/resolve/c1e84128e85ef755c096a95bdb06b47793b13acf/model.onnx"/>
  <tokenizer-model
    url="https://huggingface.co/colbert-ir/colbertv2.0/raw/c1e84128e85ef755c096a95bdb06b47793b13acf/tokenizer.json"/>
</component>
```

`schemas/product.sd`, outside `document {}` like `title_embedding`:

```
# One vector per token, quantised to sixteen bytes each. Stored as an
# attribute only, with no HNSW index: MaxSim, the score it serves, is a sum
# of per-token best matches, not a distance an HNSW graph can search by.
field colbert type tensor<int8>(token{}, v[16]) {
  indexing: input title | embed colbert | attribute
}
```

`schemas/product/colbert.profile`:

```
rank-profile colbert inherits semantic {
    # Late interaction. Instead of comparing one vector for the query with one
    # for the product, every query token is compared with every product token
    # and each query token keeps its best match. That is what MaxSim is: a sum
    # of per-token best matches, not a distance an HNSW graph can search by.
    #
    # It runs in second-phase, over the candidates the vector search already
    # found, because scoring every product this way would be absurd.
    inputs {
        query(q) tensor<float>(x[384])
        query(qt) tensor<float>(querytoken{}, v[128])
    }

    function max_sim() {
        expression {
            sum(
                reduce(
                    sum(
                        query(qt) * unpack_bits(attribute(colbert)), v
                    ),
                    max, token
                ),
                querytoken
            )
        }
    }

    match-features {
        max_sim
    }

    first-phase {
        expression: closeness(field, title_embedding)
    }

    second-phase {
        rerank-count: 100
        expression: max_sim
    }
}
```

Queries then carry both tensors: `embed(embedder, ...)` for the retrieval
vector and `embed(colbert, ...)` for the token tensor the second phase reads.
`unpack_bits` turns the sixteen stored bytes back into the 128 binary values
the query side compares against.

## What this page does not tell you

How much longer the feed takes, how much memory the token tensors hold, and
whether MaxSim reorders the candidates better than the single vector did. Each
of those is a measurement, each needs the add-on deployed and the corpus fed
again with it, and none of them belongs to this chapter's question. When a
chapter measures reranking it will measure this along with the rest; until then
the honest statement is the one at the top of the page.
