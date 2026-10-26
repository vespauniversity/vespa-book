# Model choice

The shipped application deploys one embedder (`BAAI/bge-small-en-v1.5`, pinned
in `docs/pins.md`), and this directory is not a menu of others to swap in on a
whim - it is the one comparison the chapter actually measures, plus the one
it only describes.

## The measured comparison

`bge-base.xml` holds the three pieces `chapters/ch04/model_tradeoff.py
--deploy-base` splices into a **temporary copy** of `app/`, in place of the
small model's own component, field and rank profile - a component, a vector
field at the wider dimension, and the rank profile that searches it. The swap
never reaches the shipped `app/`; `--restore` puts it back. `--block
model-tradeoff` reads the reports that run produced and prints the table: how
much quality moves, against what it costs.

## How a reader swaps a model themselves

Four things move together, and missing one produces no error - only quietly
wrong results, from queries and documents that are no longer encoded to
match each other:

1. The `<component>` block in `services.xml` (the model and its pinned commit).
2. The vector field's dimension in `schemas/product.sd` (the new model's
   width) and the component it embeds through.
3. The query-side prefix the new model wants, in `evaluate.QUERY_PREFIX` -
   nowhere else; a prefix hand-typed into a script is a prefix the next script
   forgets.
4. A redeploy, then a re-feed - the vectors already indexed were computed by
   the old model and do not update themselves.

## Late interaction

`colbert.md` documents multi-vector, late-interaction retrieval as an add-on
this chapter describes but does not deploy: no component here declares it,
and nothing under `expected/` measures it. Its effect is a reranking
question, which a later chapter takes up.
