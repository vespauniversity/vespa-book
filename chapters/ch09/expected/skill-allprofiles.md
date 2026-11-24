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
- title_embedding_precomputed: tensor<float>(x[384]) — attribute, no index; distance prenormalized-angular; read by no profile
- title_grams: string — index (3-character grams, every gram of the query must match, bm25); name it to search it
- title_embedding: tensor<float>(x[384]) — HNSW index: nearestNeighbor(title_embedding, q); distance prenormalized-angular; read by features, hybrid_linear, hybrid_rrf, hybrid_starved, personalized, phased, phased_replace, phased_title, semantic
- colbert: tensor<int8>(token{}, v[16]) — attribute, no index; read by features, personalized, phased, phased_replace, phased_title; not for queries
- title_tokens: tensor<float>(d0[96]) — attribute, no index; read by phased_replace, phased_title; not for queries
- text_tokens: tensor<float>(d0[256]) — attribute, no index; read by features, personalized, phased, phased_title; not for queries

Fieldset `default` (what userQuery() searches): title, bullets, description, brand, color

Rank profiles (ranking=<name>):
- bm25_all: first phase: title_score + bullets_score + description_score + brand_score. "Every text field, summed."
- bm25_k06_b04 … bm25_k20_b10 (15 profiles): first phase: bm25(title); each sets bm25(title).b, bm25(title).k1 as its name says
- bm25_title: first phase: bm25(title). "The smallest thing that could work: one field, one feature."
- bm25_tuned: first phase: bm25(title) + query(w_qcomplete) * fieldMatch(title).queryCompleteness + query(w_brand) * matches(brand). Adjustable: w_qcomplete = 5.0, w_brand = 1.0
- bm25_weighted: inherits bm25_all; first phase: query(w_title) * title_score + query(w_bullets) * bullets_score + query(w_description) * description_score +…. Adjustable: w_title = 3.0, w_bullets = 1.0, w_description = 0.5, w_brand = 1.0
- default: first phase: nativeRank(title, bullets, description). "Carried from chapter 2 so the two are comparable."
- explained: ranks as bm25_weighted. "Not for ranking - for looking, at one query rather than at a run."
- features: ranks as hybrid_rrf, redefining 9 functions. Needs q, qt, qt_cross. "Not a reranker: a logging profile."
- hybrid_linear: inherits hybrid_rrf; global phase (rerank 100): query(alpha) * normalize_linear(lexical) + (1 - query(alpha)) * normalize_linear(vector). Needs q. Adjustable: alpha = 0.3. "`hybrid_rrf` throws both scores away and keeps only rank."
- hybrid_rrf: inherits bm25_tuned; first phase: lexical / (1 + lexical) + vector; global phase (rerank 100): reciprocal_rank_fusion(lexical, vector). Needs q
- hybrid_starved: inherits hybrid_rrf; first phase: lexical + vector. Needs q
- personalized: inherits phased; first phase: lexical / (1 + lexical) + vector + query(w_affinity) * brand_affinity + query(w_colour) * colour_affinity + q…. Needs q, qt, qt_cross, user_brands, user_colours, user_vector. Adjustable: w_affinity = 0, w_colour = 0, w_vector = 0
- personalized_lexical: inherits bm25_tuned; first phase: bm25(title) + query(w_qcomplete) * fieldMatch(title).queryCompleteness + query(w_brand) * matches(brand) + qu…. Needs user_brands. Adjustable: w_affinity = 0
- phased: inherits hybrid_rrf; second phase (rerank 25): firstPhase + query(w_sim) * max_sim; global phase (rerank 10): query(w_cross) * normalize_linear(cross_logit) + (1 - query(w_cross)) * normalize_linear(secondPhase). Needs q, qt, qt_cross. Adjustable: w_sim = 0.002, w_cross = 0.7
- phased_replace: inherits hybrid_rrf; second phase (rerank 100): max_sim; global phase (rerank 50): onnx(cross).logits{d0:0,d1:0}. Needs q, qt, qt_cross
- phased_title: ranks as phased, redefining input_ids, token_type_ids, attention_mask. Needs q, qt, qt_cross
- random: first phase: random. "The floor."
- semantic: first phase: closeness(field, title_embedding). Needs q

Query tensors are request parameters input.query(<name>): q = embed(embedder, "Represent this sentence for searching relevant passages: <words>"), qt = embed(colbert, "<words>"), qt_cross = embed(tokenizer, "<words>").

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
