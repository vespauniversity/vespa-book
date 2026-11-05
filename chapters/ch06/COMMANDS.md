# ch06 COMMANDS

One command per line, verbatim, followed by the file it wrote.

Four sections, by heading. `## Core` is every command in the README's run
sheet except the two `w_cross` sweep commands, plus four lines the run sheet
leaves out: two `./bootstrap.sh ch06` runs, the `vespa deploy` of this
chapter's package, and the `deployed.py` stamp after it.
`## Ours, not for the reader (kept for the record)` holds the feed command
behind `expected/feed.json` (the same command every bootstrap that feeds
runs, so a bootstrap rewrites that file) and four depth-100 reference runs,
three of which (`hybrid_linear` on both splits, `hybrid_rrf` on test) the
README cites. `## Extended (ours, one machine)` holds the
replace-design (negative example) curve, the `w_cross` grid (which the run
sheet also lists, since the chosen `w_cross` comes from it), and the
cross-encoder count sweep out to 25, with the command that renders its block;
the `w_cross` grid and the count sweep carry the wall time measured on one
machine, the replace-design curve none. `## 2026-10-04 regeneration` records
the re-run of the four feature-log commands under `## Core` that wrote the
shipped feature logs. Each file below is written by exactly one command.

## Core


# `expected/feed.json` is written by the `feed.py` command under *Ours*
# below, on the shipped schema (all three indexing-time fields). A bootstrap
# that feeds runs the same command and writes the same file.

# `./bootstrap.sh ch06` run once at the start of a measurement session.
# venv/corpus/container skip, models.py fetch skip (pinned sha256 already
# present), deploy ran (the bootstrap always deploys; session ID 8, the same
# pre-existing document-summary warning as the deploy before it, no reindex
# warning), feed skip: 101341 documents in the index, colbert present. No
# feed started. This command wrote nothing under chapters/.
./bootstrap.sh ch06
(no file written; prints a state block only)


# w_sim sweep, validation, at the grid fixed before any weight sweep ran.
.venv/bin/python chapters/ch06/weight_sweep.py --split validation --input w_sim --values 0 0.002 0.005 0.01 0.02 0.05 --second 100 --global 0 --passes 1 --out chapters/ch06/expected/validation-weight-sim.json
chapters/ch06/expected/validation-weight-sim.json

.venv/bin/python chapters/ch06/weight_sweep.py --split validation --input w_sim --values 0 0.002 0.005 0.01 0.02 0.05 --from chapters/ch06/expected/validation-weight-sim.json --block weight-sweep > chapters/ch06/expected/validation-weight-sim.block.md
chapters/ch06/expected/validation-weight-sim.block.md

# ColBERT second-phase count sweep at the chosen w_sim (0.002). The
# replace-design curve has its own report and block under Extended below.
.venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase second --param 'input.query(w_sim)=0.002' --out chapters/ch06/expected/validation-rerank-colbert.json
chapters/ch06/expected/validation-rerank-colbert.json

.venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase second --from chapters/ch06/expected/validation-rerank-colbert.json --block rerank-sweep > chapters/ch06/expected/validation-rerank-colbert.block.md
chapters/ch06/expected/validation-rerank-colbert.block.md


# Reference rows and the bounded first stage at depth 400, both splits, on
# the index of the shipped schema.
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking hybrid_linear --param 'input.query(alpha)=0.3' --hits 400 --label hybrid_linear --block headline --out chapters/ch06/expected/validation-hybrid_linear.json > chapters/ch06/expected/validation-hybrid_linear.block.md
chapters/ch06/expected/validation-hybrid_linear.json, chapters/ch06/expected/validation-hybrid_linear.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking hybrid_linear --param 'input.query(alpha)=0.3' --hits 400 --label hybrid_linear --block headline --out chapters/ch06/expected/test-hybrid_linear.json > chapters/ch06/expected/test-hybrid_linear.block.md
chapters/ch06/expected/test-hybrid_linear.json, chapters/ch06/expected/test-hybrid_linear.block.md

.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking hybrid_rrf --hits 400 --label hybrid_rrf --block headline --out chapters/ch06/expected/validation-hybrid_rrf.json > chapters/ch06/expected/validation-hybrid_rrf.block.md
chapters/ch06/expected/validation-hybrid_rrf.json, chapters/ch06/expected/validation-hybrid_rrf.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking hybrid_rrf --hits 400 --label hybrid_rrf --block headline --out chapters/ch06/expected/test-hybrid_rrf.json > chapters/ch06/expected/test-hybrid_rrf.block.md
chapters/ch06/expected/test-hybrid_rrf.json, chapters/ch06/expected/test-hybrid_rrf.block.md

.venv/bin/python shared/tools/evaluate.py --split validation --retriever semantic --ranking semantic --hits 400 --label semantic --block headline --out chapters/ch06/expected/validation-semantic.json > chapters/ch06/expected/validation-semantic.block.md
chapters/ch06/expected/validation-semantic.json, chapters/ch06/expected/validation-semantic.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever semantic --ranking semantic --hits 400 --label semantic --block headline --out chapters/ch06/expected/test-semantic.json > chapters/ch06/expected/test-semantic.block.md
chapters/ch06/expected/test-semantic.json, chapters/ch06/expected/test-semantic.block.md

.venv/bin/python shared/tools/evaluate.py --split validation --retriever lexical --ranking bm25_tuned --hits 400 --label bm25_tuned --block headline --out chapters/ch06/expected/validation-bm25_tuned.json > chapters/ch06/expected/validation-bm25_tuned.block.md
chapters/ch06/expected/validation-bm25_tuned.json, chapters/ch06/expected/validation-bm25_tuned.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever lexical --ranking bm25_tuned --hits 400 --label bm25_tuned --block headline --out chapters/ch06/expected/test-bm25_tuned.json > chapters/ch06/expected/test-bm25_tuned.block.md
chapters/ch06/expected/test-bm25_tuned.json, chapters/ch06/expected/test-bm25_tuned.block.md

.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking phased --hits 400 --param 'ranking.rerankCount=0' --param 'ranking.globalPhase.rerankCount=0' --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label first_stage --block headline --out chapters/ch06/expected/validation-first_stage.json > chapters/ch06/expected/validation-first_stage.block.md
chapters/ch06/expected/validation-first_stage.json, chapters/ch06/expected/validation-first_stage.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking phased --hits 400 --param 'ranking.rerankCount=0' --param 'ranking.globalPhase.rerankCount=0' --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label first_stage --block headline --out chapters/ch06/expected/test-first_stage.json > chapters/ch06/expected/test-first_stage.block.md
chapters/ch06/expected/test-first_stage.json, chapters/ch06/expected/test-first_stage.block.md


# `./bootstrap.sh ch06` run once at the start of the next measurement
# session. venv/corpus/container skip, models.py fetch skip (pinned sha256
# already present), deploy ran (session ID 9, same pre-existing
# document-summary warning, no reindex warning), feed skip: 101341
# documents in the index, colbert present. No feed started.
./bootstrap.sh ch06
(no file written; prints a state block only)

# w_sim fine grid, plateau only. Does NOT change the chosen weight (0.002,
# already chosen from the grid above) -- this only shows where the plateau
# sits.
.venv/bin/python chapters/ch06/weight_sweep.py --split validation --input w_sim --values 0 0.001 0.002 0.003 0.005 --second 100 --global 0 --passes 1 --out chapters/ch06/expected/validation-weight-sim-fine.json
chapters/ch06/expected/validation-weight-sim-fine.json

.venv/bin/python chapters/ch06/weight_sweep.py --split validation --input w_sim --values 0 0.001 0.002 0.003 0.005 --from chapters/ch06/expected/validation-weight-sim-fine.json --block weight-sweep > chapters/ch06/expected/validation-weight-sim-fine.block.md
chapters/ch06/expected/validation-weight-sim-fine.block.md

# Cross-encoder global-phase count sweep, validation, at the chosen weights
# (w_sim 0.002, w_cross 0.7) -- the grid the chosen count comes from; the
# same sweep out to 25 is under Extended. --phase global pins the second
# phase's knob (ranking.rerankCount) to 0 by design, so this measures the
# cross-encoder ALONE on top of the first stage -- the README's *Where the
# cross-encoder's cost falls, and how many candidates it gets* compares this
# against the ColBERT curve (validation-rerank-colbert.json).
.venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase global --counts 0 5 10 --reference-count 10 --param 'input.query(w_sim)=0.002' --param 'input.query(w_cross)=0.7' --out chapters/ch06/expected/validation-rerank-cross.json
chapters/ch06/expected/validation-rerank-cross.json

.venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase global --from chapters/ch06/expected/validation-rerank-cross.json --block rerank-sweep > chapters/ch06/expected/validation-rerank-cross.block.md
chapters/ch06/expected/validation-rerank-cross.block.md

# Deploy of the package with the validation-chosen values: phased.profile's
# query(w_sim) / query(w_cross) and its two rerank-count defaults are
# 0.002 / 0.7 / 25 / 10, and features.profile carries cross_logit, appended
# last in match-features. No feed (rank-profile text only).
vespa deploy --wait 300 chapters/ch06/app
(session ID 10; only the pre-existing document-summary 'context' warning; no reindex warning)

.venv/bin/python shared/tools/deployed.py
(embedder=BAAI/bge-small-en-v1.5@5c38ec7c colbert=colbert-ir/colbertv2.0@c1e84128)

# Feature log x3 at the shipped defaults, 56 columns (cross_logit last).
# Row counts: 35,019 / 14,926 / 21,503.
.venv/bin/python chapters/ch06/features_log.py --split train --out chapters/ch06/expected/features-train.json
chapters/ch06/expected/features-train.json (CSV to builds/esci-us-hard-book-s42-kdd-v4/features/features-train.csv, gitignored)

.venv/bin/python chapters/ch06/features_log.py --split validation --out chapters/ch06/expected/features-validation.json
chapters/ch06/expected/features-validation.json (CSV to builds/esci-us-hard-book-s42-kdd-v4/features/features-validation.csv, gitignored)

.venv/bin/python chapters/ch06/features_log.py --split test --out chapters/ch06/expected/features-test.json
chapters/ch06/expected/features-test.json (CSV to builds/esci-us-hard-book-s42-kdd-v4/features/features-test.csv, gitignored)

.venv/bin/python chapters/ch06/features_log.py --from chapters/ch06/expected/features-train.json chapters/ch06/expected/features-validation.json chapters/ch06/expected/features-test.json --block features-log > chapters/ch06/expected/features-log.block.md
chapters/ch06/expected/features-log.block.md

# phased and phased_title at the chosen settings -- no knob params passed
# (rerankCount / globalPhase.rerankCount / w_sim / w_cross all come from the
# defaults the deploy above carries); the reranker-input flags
# are not knobs, they populate the qt/qt_cross tensors the profiles need.
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking phased --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label phased --block headline --out chapters/ch06/expected/validation-phased.json > chapters/ch06/expected/validation-phased.block.md
chapters/ch06/expected/validation-phased.json, chapters/ch06/expected/validation-phased.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking phased --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label phased --block headline --out chapters/ch06/expected/test-phased.json > chapters/ch06/expected/test-phased.block.md
chapters/ch06/expected/test-phased.json, chapters/ch06/expected/test-phased.block.md

.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking phased_title --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label phased_title --block headline --out chapters/ch06/expected/validation-phased_title.json > chapters/ch06/expected/validation-phased_title.block.md
chapters/ch06/expected/validation-phased_title.json, chapters/ch06/expected/validation-phased_title.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking phased_title --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label phased_title --block headline --out chapters/ch06/expected/test-phased_title.json > chapters/ch06/expected/test-phased_title.block.md
chapters/ch06/expected/test-phased_title.json, chapters/ch06/expected/test-phased_title.block.md

# Compare blocks over {bm25_tuned, semantic, hybrid_rrf,
# hybrid_linear, first_stage, phased_title, phased}, validation then test.
# The phased-vs-title comparison restricts to exactly two reports positionally
# (compare.py has no --display row filter; passing only phased_title.json
# and phased.json as the positional `reports` is how the tool itself
# restricts a comparison, per shared/tools/compare.py:286-292).
.venv/bin/python shared/tools/compare.py --block evaluations --out chapters/ch06/expected/compare-validation-evaluations.json chapters/ch06/expected/validation-bm25_tuned.json chapters/ch06/expected/validation-semantic.json chapters/ch06/expected/validation-hybrid_rrf.json chapters/ch06/expected/validation-hybrid_linear.json chapters/ch06/expected/validation-first_stage.json chapters/ch06/expected/validation-phased_title.json chapters/ch06/expected/validation-phased.json > chapters/ch06/expected/compare-validation-evaluations.block.md
chapters/ch06/expected/compare-validation-evaluations.json, chapters/ch06/expected/compare-validation-evaluations.block.md

.venv/bin/python shared/tools/compare.py --block evaluations-latency --out chapters/ch06/expected/compare-validation-latency.json chapters/ch06/expected/validation-bm25_tuned.json chapters/ch06/expected/validation-semantic.json chapters/ch06/expected/validation-hybrid_rrf.json chapters/ch06/expected/validation-hybrid_linear.json chapters/ch06/expected/validation-first_stage.json chapters/ch06/expected/validation-phased_title.json chapters/ch06/expected/validation-phased.json > chapters/ch06/expected/compare-validation-latency.block.md
chapters/ch06/expected/compare-validation-latency.json, chapters/ch06/expected/compare-validation-latency.block.md

.venv/bin/python shared/tools/compare.py --block comparison --baseline first_stage --out chapters/ch06/expected/compare-validation-vs-first-stage.json chapters/ch06/expected/validation-bm25_tuned.json chapters/ch06/expected/validation-semantic.json chapters/ch06/expected/validation-hybrid_rrf.json chapters/ch06/expected/validation-hybrid_linear.json chapters/ch06/expected/validation-first_stage.json chapters/ch06/expected/validation-phased_title.json chapters/ch06/expected/validation-phased.json > chapters/ch06/expected/compare-validation-vs-first-stage.block.md
chapters/ch06/expected/compare-validation-vs-first-stage.json, chapters/ch06/expected/compare-validation-vs-first-stage.block.md

.venv/bin/python shared/tools/compare.py --block comparison --baseline phased_title --out chapters/ch06/expected/compare-validation-phased-vs-title.json chapters/ch06/expected/validation-phased_title.json chapters/ch06/expected/validation-phased.json > chapters/ch06/expected/compare-validation-phased-vs-title.block.md
chapters/ch06/expected/compare-validation-phased-vs-title.json, chapters/ch06/expected/compare-validation-phased-vs-title.block.md

.venv/bin/python shared/tools/compare.py --block evaluations --out chapters/ch06/expected/compare-test-evaluations.json chapters/ch06/expected/test-bm25_tuned.json chapters/ch06/expected/test-semantic.json chapters/ch06/expected/test-hybrid_rrf.json chapters/ch06/expected/test-hybrid_linear.json chapters/ch06/expected/test-first_stage.json chapters/ch06/expected/test-phased_title.json chapters/ch06/expected/test-phased.json > chapters/ch06/expected/compare-test-evaluations.block.md
chapters/ch06/expected/compare-test-evaluations.json, chapters/ch06/expected/compare-test-evaluations.block.md

.venv/bin/python shared/tools/compare.py --block evaluations-latency --out chapters/ch06/expected/compare-test-latency.json chapters/ch06/expected/test-bm25_tuned.json chapters/ch06/expected/test-semantic.json chapters/ch06/expected/test-hybrid_rrf.json chapters/ch06/expected/test-hybrid_linear.json chapters/ch06/expected/test-first_stage.json chapters/ch06/expected/test-phased_title.json chapters/ch06/expected/test-phased.json > chapters/ch06/expected/compare-test-latency.block.md
chapters/ch06/expected/compare-test-latency.json, chapters/ch06/expected/compare-test-latency.block.md

.venv/bin/python shared/tools/compare.py --block comparison --baseline first_stage --out chapters/ch06/expected/compare-test-vs-first-stage.json chapters/ch06/expected/test-bm25_tuned.json chapters/ch06/expected/test-semantic.json chapters/ch06/expected/test-hybrid_rrf.json chapters/ch06/expected/test-hybrid_linear.json chapters/ch06/expected/test-first_stage.json chapters/ch06/expected/test-phased_title.json chapters/ch06/expected/test-phased.json > chapters/ch06/expected/compare-test-vs-first-stage.block.md
chapters/ch06/expected/compare-test-vs-first-stage.json, chapters/ch06/expected/compare-test-vs-first-stage.block.md

.venv/bin/python shared/tools/compare.py --block comparison --baseline phased_title --out chapters/ch06/expected/compare-test-phased-vs-title.json chapters/ch06/expected/test-phased_title.json chapters/ch06/expected/test-phased.json > chapters/ch06/expected/compare-test-phased-vs-title.block.md
chapters/ch06/expected/compare-test-phased-vs-title.json, chapters/ch06/expected/compare-test-phased-vs-title.block.md

# Per-phase cost table at the chosen counts/weights.
.venv/bin/python chapters/ch06/funnel_budget.py --split validation --second 25 --global 10 --hits 400 --param 'input.query(w_sim)=0.002' --param 'input.query(w_cross)=0.7' --out chapters/ch06/expected/validation-funnel-budget.json
chapters/ch06/expected/validation-funnel-budget.json

.venv/bin/python chapters/ch06/funnel_budget.py --split validation --from chapters/ch06/expected/validation-funnel-budget.json --block funnel-budget > chapters/ch06/expected/validation-funnel-budget.block.md
chapters/ch06/expected/validation-funnel-budget.block.md

# Who moved -- the wider-net count at the chosen funnel settings. phased
# requests take the defaults the deploy above carries; no --param needed.
.venv/bin/python chapters/ch06/wider_net.py --split validation --profiles phased hybrid_linear hybrid_rrf semantic --alpha 0.3 --out chapters/ch06/expected/validation-wider-net.json
chapters/ch06/expected/validation-wider-net.json

.venv/bin/python chapters/ch06/wider_net.py --from chapters/ch06/expected/validation-wider-net.json --block wider-net > chapters/ch06/expected/validation-wider-net.block.md
chapters/ch06/expected/validation-wider-net.block.md

.venv/bin/python chapters/ch06/wider_net.py --split test --profiles phased hybrid_linear hybrid_rrf semantic --alpha 0.3 --out chapters/ch06/expected/test-wider-net.json
chapters/ch06/expected/test-wider-net.json

.venv/bin/python chapters/ch06/wider_net.py --from chapters/ch06/expected/test-wider-net.json --block wider-net > chapters/ch06/expected/test-wider-net.block.md
chapters/ch06/expected/test-wider-net.block.md

# Shipped memory.json = the reading on a FRESH container (./bootstrap.sh ch06 --fresh, then this command); the readings on this chapter's long-lived container are not shipped.
.venv/bin/python shared/tools/memory.py --settle 600 --rounds 3 --tolerance 0.01 --out chapters/ch06/expected/memory.json
chapters/ch06/expected/memory.json

.venv/bin/python shared/tools/memory.py --from chapters/ch06/expected/memory.json > chapters/ch06/expected/memory.block.md
chapters/ch06/expected/memory.block.md

# The same command on a container continued from chapter 5 (./bootstrap.sh ch05 --fresh, then ./bootstrap.sh ch06, nothing else run), 2026-10-22: the index fed by both chapters. The README's "reads higher" rests on it; expected/memory-other-containers.md lists it beside the fresh reading.
.venv/bin/python shared/tools/memory.py --settle 600 --rounds 3 --tolerance 0.01 --out chapters/ch06/expected/memory-fed-twice.json
chapters/ch06/expected/memory-fed-twice.json

.venv/bin/python shared/tools/memory.py --from chapters/ch06/expected/memory-fed-twice.json > chapters/ch06/expected/memory-fed-twice.block.md
chapters/ch06/expected/memory-fed-twice.block.md


# Worked query under the shipped profiles. Defaults come from the schema.
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking phased --hits 10 --block features --param 'input.query(qt)=embed(colbert, "running shoes")' --param 'input.query(qt_cross)=embed(tokenizer, "running shoes")' > chapters/ch06/expected/features-running-shoes-phased.block.md
chapters/ch06/expected/features-running-shoes-phased.block.md
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking phased_title --hits 10 --block features --param 'input.query(qt)=embed(colbert, "running shoes")' --param 'input.query(qt_cross)=embed(tokenizer, "running shoes")' > chapters/ch06/expected/features-running-shoes-phased_title.block.md
chapters/ch06/expected/features-running-shoes-phased_title.block.md
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking phased_replace --hits 10 --block features --param 'input.query(qt)=embed(colbert, "running shoes")' --param 'input.query(qt_cross)=embed(tokenizer, "running shoes")' > chapters/ch06/expected/features-running-shoes-phased_replace.block.md
chapters/ch06/expected/features-running-shoes-phased_replace.block.md
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking hybrid_linear --hits 10 --param 'input.query(alpha)=0.3' --block features > chapters/ch06/expected/features-running-shoes-hybrid_linear.block.md
chapters/ch06/expected/features-running-shoes-hybrid_linear.block.md

## Ours, not for the reader (kept for the record)

# The depth-100 reference runs reproduce chapter 5's own condition, to check that the same profile still gives chapter 5's number on this container; the reader's rows are the depth-400 ones above. The feed command wrote the shipped expected/feed.json, on the shipped schema; a bootstrap that feeds runs the same command and rewrites that file.
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking hybrid_linear --param 'input.query(alpha)=0.3' --hits 100 --label hybrid_linear --block headline --out chapters/ch06/expected/validation-hybrid_linear-depth100.json > chapters/ch06/expected/validation-hybrid_linear-depth100.block.md
chapters/ch06/expected/validation-hybrid_linear-depth100.json, chapters/ch06/expected/validation-hybrid_linear-depth100.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking hybrid_linear --param 'input.query(alpha)=0.3' --hits 100 --label hybrid_linear --block headline --out chapters/ch06/expected/test-hybrid_linear-depth100.json > chapters/ch06/expected/test-hybrid_linear-depth100.block.md
chapters/ch06/expected/test-hybrid_linear-depth100.json, chapters/ch06/expected/test-hybrid_linear-depth100.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking hybrid_rrf --hits 100 --label hybrid_rrf --block headline --out chapters/ch06/expected/validation-hybrid_rrf-depth100.json > chapters/ch06/expected/validation-hybrid_rrf-depth100.block.md
chapters/ch06/expected/validation-hybrid_rrf-depth100.json, chapters/ch06/expected/validation-hybrid_rrf-depth100.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking hybrid_rrf --hits 100 --label hybrid_rrf --block headline --out chapters/ch06/expected/test-hybrid_rrf-depth100.json > chapters/ch06/expected/test-hybrid_rrf-depth100.block.md
chapters/ch06/expected/test-hybrid_rrf-depth100.json, chapters/ch06/expected/test-hybrid_rrf-depth100.block.md
.venv/bin/python shared/tools/feed.py --out chapters/ch06/expected/feed.json
chapters/ch06/expected/feed.json — 101,341 ok, 0 failed, 0 retried in 1717.7s (59 docs/s)

## Extended (ours, one machine)

# The negative example under its own name (phased_replace, the
# replace-design profile). Caption confirmed to show `phased_replace`, not
# `phased` -- `--profile` reaches the request and the caption. Wall time not
# separately captured (the measurement session it ran in took 165 min across
# six runs; this curve's own share was not isolated).
.venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase second --profile phased_replace --out chapters/ch06/expected/validation-rerank-colbert-replace.json
chapters/ch06/expected/validation-rerank-colbert-replace.json

.venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase second --profile phased_replace --from chapters/ch06/expected/validation-rerank-colbert-replace.json --block rerank-sweep > chapters/ch06/expected/validation-rerank-colbert-replace.block.md
chapters/ch06/expected/validation-rerank-colbert-replace.block.md

# w_cross sweep, validation, at the chosen w_sim (0.002), second-phase count
# pinned to 25 (chosen by the ColBERT count sweep), global-phase count pinned
# to 10 (the cross-encoder at 320 tokens, estimated before this sweep at
# ~86 ms/doc, makes 50 unaffordable for a sweep; the count sweep later
# measured 81-85 ms). Wall time (ours, one machine, Apple M4
# Pro, 4 CPU / 10 GB container VM, Rancher Desktop): started 2026-09-21
# 00:15:23, finished 02:34:40 -- 2h 19m 17s.
.venv/bin/python chapters/ch06/weight_sweep.py --split validation --input w_cross --values 0 0.3 0.5 0.7 1.0 --second 25 --global 10 --passes 1 --param 'input.query(w_sim)=0.002' --out chapters/ch06/expected/validation-weight-cross.json
chapters/ch06/expected/validation-weight-cross.json

.venv/bin/python chapters/ch06/weight_sweep.py --split validation --input w_cross --values 0 0.3 0.5 0.7 1.0 --from chapters/ch06/expected/validation-weight-cross.json --block weight-sweep > chapters/ch06/expected/validation-weight-cross.block.md
chapters/ch06/expected/validation-weight-cross.block.md

# The same cross-encoder global-phase sweep with count 25 added. Wall time (ours, one machine, Apple M4 Pro,
# 4 CPU / 10 GB container VM, Rancher Desktop): started 2026-09-21 03:59:44,
# finished 07:11:31 -- 3h 11m 47s. Does NOT change the chosen count (the
# Core sweep decides that); this is the curve for the reader's Notes.
.venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase global --counts 0 5 10 25 --reference-count 10 --param 'input.query(w_sim)=0.002' --param 'input.query(w_cross)=0.7' --out chapters/ch06/expected/validation-rerank-cross-extended.json
chapters/ch06/expected/validation-rerank-cross-extended.json

.venv/bin/python chapters/ch06/rerank_sweep.py --split validation --phase global --from chapters/ch06/expected/validation-rerank-cross-extended.json --block rerank-sweep > chapters/ch06/expected/validation-rerank-cross-extended.block.md
chapters/ch06/expected/validation-rerank-cross-extended.block.md

## 2026-10-04 regeneration

The three feature logs were written again on a fresh chapter-6 container
(`docker rm -f vespa-book`, then `./bootstrap.sh ch06`: package deployed,
101,341 documents fed in 29m 20s, both embedders present; the container before
it held a later chapter), with `features_log.py` sending `input.query(qt_cross)`.
The commands are the four under *Core* above, run verbatim and in order; the
shipped logs had been written before the tool sent that input, so their
`cross_logit` column had been computed against a zero-filled query.

Wall times: train 51m 46s, validation 21m 51s, test 31m 46s; the block render
under a second. The counts in `expected/features-log.block.md` are unchanged
(1,715 / 735 / 1,050 queries; 35,019 / 14,926 / 21,503 pairs, every one retrieved
by the union arm; E / S / C / I as before; 56 columns). Only the sha256 changed:

| split | sha256 before | sha256 after |
|---|---|---|
| train | 2fb774b22e72 | 6d24c0ac3874 |
| validation | 81753bb55c2c | fe3e027edc46 |
| test | 2fdeba3a906b | cec44125d6e2 |

`cross_logit` now carries values: among the first 1,000 rows of each log it has
998 (train), 992 (validation) and 1,000 (test) distinct values.
