# Catalogue: document type `product`

Fields (name: type — index = searchable; attribute = filters, grouping, ranking):
- locale: string — not indexed, not an attribute: cannot be queried
- id: string — index (whole value as one word); rank filter; name it to search it
- title: string — index (text, bm25)
- bullets: array<string> — index (text, bm25)
- description: string — index (text, bm25)
- brand: string — index (text, bm25); attribute
- color: string — index (text, bm25); attribute
- has_description: bool — attribute, fast-search
- tenant_id: string — attribute, fast-search; rank filter
- title_embedding_precomputed: tensor<float>(x[384]) — attribute, no index; distance prenormalized-angular; read by no profile listed here
- title_embedding: tensor<float>(x[384]) — HNSW index: nearestNeighbor(title_embedding, q); distance prenormalized-angular; read by hybrid_rrf, semantic
- colbert: tensor<int8>(token{}, v[16]) — attribute, no index; read by no profile listed here
- title_tokens: tensor<float>(d0[96]) — attribute, no index; read by no profile listed here
- text_tokens: tensor<float>(d0[256]) — attribute, no index; read by no profile listed here

Fieldset `default` (what userQuery() searches): title, bullets, description, brand, color

Rank profiles (ranking=<name>):
- bm25_tuned: first phase: bm25(title) + query(w_qcomplete) * fieldMatch(title).queryCompleteness + query(w_brand) * matches(brand). Adjustable: w_qcomplete = 5.0, w_brand = 1.0
- hybrid_rrf: inherits bm25_tuned; first phase: lexical / (1 + lexical) + vector; global phase (rerank 100): reciprocal_rank_fusion(lexical, vector). Needs q
- semantic: first phase: closeness(field, title_embedding). Needs q

What this catalogue's own measurements say:
Measured in earlier chapters against the human relevance labels of this catalogue: `hybrid_rrf`, the keyword and vector rankings merged by rank, ranked better than `bm25_tuned` (keyword only) and than `semantic` (the vector side alone), and further down its list reaches more labelled products than `bm25_tuned` and as many as `semantic`; among keyword-only rankings `bm25_tuned` ranked best.

Query tensors are request parameters input.query(<name>): q = embed(embedder, "Represent this sentence for searching relevant passages: <words>").

Statements earlier chapters sent, with the request parameters each needs:
1. Keyword search over the fieldset `default` (chapter 2); params: query=<words>
   select id, title from product where userQuery()
2. Nearest neighbours of the query vector; targetHits is how many it nominates (chapter 4); params: input.query(q)
   select id from product where {targetHits:1}nearestNeighbor(title_embedding, q)
3. Both arms in one request, for a hybrid profile (chapter 5); params: query, input.query(q)
   select id, title, snippet from product where userQuery() or ({targetHits:100}nearestNeighbor(title_embedding, q))
4. A condition ANDed onto the union, which goes in parentheses (chapter 5); params: query, input.query(q)
   select id, title from product where (userQuery() or ({targetHits:100}nearestNeighbor(title_embedding, q))) and has_description = true
5. A text match on one field (chapter 8); params: query
   select id, title from product where (userQuery()) and tenant_id contains "nike"
6. Set membership on an attribute (chapter 8); params: query
   select id, title from product where (userQuery()) and tenant_id in ("nike", "adidas")
7. One count per value of a field, after `|` (this chapter's grouping tool); params: query
   select id, title, brand from product where userQuery() | all(group(brand) max(20) each(output(count())))

A statement selects the fields it wants back (id, title, brand); `where` is required.
