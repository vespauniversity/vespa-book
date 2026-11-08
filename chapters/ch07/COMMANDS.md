# ch07 COMMANDS

One command per line, verbatim, followed by the file(s) it wrote. Six
sections: the first three the same split as chapter 6's, then *Measured
wall times*, then two dated re-measurements (2026-10-04, 2026-10-05) whose
reports the README's *A fully learned funnel against the hand-tuned one* and
*What each placement costs in latency and memory* cite:

- **Core** is the README's run sheet (*Notes → Run sheet*), command for
  command, in the order the commands ran here, with one difference: the
  three `chapters/ch06/features_log.py` runs that write
  `expected/features-{train,validation,test}.json` are on the run sheet but
  not in this file.
- **Ours, not for the reader** is kept for the record but needs something a
  reader does not have: a feature log written on another container, or one
  written before chapter 6's logging tool was corrected.
- **Extended** holds the two commands that are this chapter's own extended
  measurement — the README's *Reproducing the extended sweeps* — not part of
  a reader's path: item 20 (the chosen global-phase model reranking 25
  candidates instead of 10) and the latency table with that row added. Both
  ran in the Core sequence here (item 20 after item 19, the latency table
  after item 21), and the section explains what they measured.

**What is served.** M1, the learned second phase, in five shapes:
`ltr_second_tiny` 3x50, `ltr_second` 3x100 (chosen before the
in-engine sweep and kept as the engine's own pick), `ltr_second_offline`
3x200 (the offline grid's own pick, kept as a comparison row),
`ltr_second_mid` 15x200, `ltr_second_large` 31x800 — plus `ltr_second`'s
ONNX pair. M2, the learned global phase over M1, in two shapes:
`ltr_global` 3x100 (chosen before its validation run, with the rule
that a tie goes to the smaller shape) and `ltr_global_200` 3x200 — plus
`ltr_global`'s ONNX pair.

**The container.** This chapter's app deployed, 101,341 documents,
`embedder=BAAI/bge-small-en-v1.5@5c38ec7c, colbert=colbert-ir/colbertv2.0@
c1e84128`, confirmed with `deployed.py` and one `query.py --ranking
ltr_second` call before anything else ran (and one `query.py --ranking
ltr_global --hits 10` call before the global-phase rows);
`git status --porcelain -- chapters/ch07/app` stayed empty throughout.

**Every `ltr_global*` request asks for as many hits as the global phase
reranks — ten by default; the parity runs and the 25-hit row widen both
counts together.** Those profiles
declare the global-phase model's score, `ltr_score_global`, as a
match-feature, and Vespa computes every declared match-feature for every hit
returned, not only for the 10 candidates the global phase reranks — so the
cost is set by whichever is larger, the hits returned or the global
rerank count, and at
`--hits 400` the cross-encoder ran about 400 times per query and the
evaluation timed out. Leaving the match-feature out does not work either: the
global phase then fails to construct ("missing global-phase input"). Asking
for the 10 hits the global phase reranks costs ≈0.91 s per query (913.5 ms
p50, `compare-validation-latency.block.md`), close to `phased`'s 947.3 ms.
A ten-hit request also asks the vector arm for ten nearest neighbours
(`evaluate.py` sets `targetHits` from `--hits`), so the M2 rows' candidates
are not exactly the 400-hit rows' (README, *Reading these measurements*).
One consequence: `evaluate.py` measures recall only up to the
hits requested (`recall_cutoffs(hits)`), so no M2 report carries
`per_query_recall100`, and `compare.py` prints `recall@100` as a dash
wherever an M2 report sits beside an M1 or `phased` one in a compare block.

**The feature log is the corrected one.** An earlier version of
`chapters/ch06/features_log.py` never sent the cross-encoder its query
(`input.query(qt_cross)`) when it logged the `features` profile's
`cross_logit` column, so that column scored an empty query — no signal.
The tool was corrected and the three logs regenerated: only `cross_logit`
changed meaningfully; five BM25-based columns differ in their last digits.
The second-phase models, their ONNX export and their parity check ran on
the earlier log, the global-phase models on the corrected one. With the
real column, `cross_logit` is the top feature at 57% of `ltr_global`'s gain
(`train-global-importance.block.md`), and the offline grid picks the M2
shape that was served and kept, 3×100 (0.7576), with 3×200 the runner-up
(0.7570). The M2 reports measured on the
defective log are kept under `expected/before-cross-fix/` — see *Ours, not
for the reader*.

**M2 choice = `ltr_global` (3×100), the shape chosen in advance.**
`compare-validation-global-shapes.block.md` puts both M2 shapes inside the
noise against `phased` (`ltr_global` +0.008 [-0.001, +0.016],
`ltr_global_200` +0.007 [-0.002, +0.016]); the tie-break
(`compare-validation-global-tiebreak.block.md`, baseline `ltr_global`) is
-0.001 [-0.003, +0.002], also inside the noise, so "a tie goes to the
smaller" keeps `ltr_global`, the name already deployed. Against
`first_stage`, M2 is real on both splits
(`compare-validation-vs-first-stage.block.md` +0.028 [+0.019, +0.038];
`compare-test-vs-first-stage.block.md` +0.014 [+0.006, +0.022]). Against
`phased` the edge is small and inside the noise on both splits (validation
+0.008 [-0.001, +0.016]; test +0.004 [-0.002, +0.011]). Native vs ONNX in
the engine is exact (`compare-*-global-native-vs-onnx`, +0.000 both splits).

## Core

# item 1: memory. The run sheet takes it before any evaluation; so was the committed
# reading (./bootstrap.sh ch06 --fresh, then ./bootstrap.sh ch07, then this command).
# settled: true.
.venv/bin/python shared/tools/memory.py --settle 600 --rounds 3 --tolerance 0.01 --out chapters/ch07/expected/memory.json
chapters/ch07/expected/memory.json

.venv/bin/python shared/tools/memory.py --from chapters/ch07/expected/memory.json > chapters/ch07/expected/memory.block.md
chapters/ch07/expected/memory.block.md

# item 2: baselines, retrieval mode. (i) first stage alone -- `phased` with
# both rerank counts 0, depth 400, both reranker inputs (ch06's exact
# command: `first_stage` is a label on `phased`, not a profile of its own).
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking phased --hits 400 --param 'ranking.rerankCount=0' --param 'ranking.globalPhase.rerankCount=0' --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label first_stage --block headline --out chapters/ch07/expected/validation-first_stage.json > chapters/ch07/expected/validation-first_stage.block.md
chapters/ch07/expected/validation-first_stage.json, chapters/ch07/expected/validation-first_stage.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking phased --hits 400 --param 'ranking.rerankCount=0' --param 'ranking.globalPhase.rerankCount=0' --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label first_stage --block headline --out chapters/ch07/expected/test-first_stage.json > chapters/ch07/expected/test-first_stage.block.md
chapters/ch07/expected/test-first_stage.json, chapters/ch07/expected/test-first_stage.block.md

# item 3: baselines, rerank mode (judged pairs only, passes 1) -- the
# engine-side counterpart of any offline figure.
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking phased --mode rerank --passes 1 --hits 400 --param 'ranking.rerankCount=0' --param 'ranking.globalPhase.rerankCount=0' --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label first_stage --block headline --out chapters/ch07/expected/validation-first_stage-rerank.json > chapters/ch07/expected/validation-first_stage-rerank.block.md
chapters/ch07/expected/validation-first_stage-rerank.json, chapters/ch07/expected/validation-first_stage-rerank.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking phased --mode rerank --passes 1 --hits 400 --param 'ranking.rerankCount=0' --param 'ranking.globalPhase.rerankCount=0' --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label first_stage --block headline --out chapters/ch07/expected/test-first_stage-rerank.json > chapters/ch07/expected/test-first_stage-rerank.block.md
chapters/ch07/expected/test-first_stage-rerank.json, chapters/ch07/expected/test-first_stage-rerank.block.md

# item 4: `phased` baseline -- chapter 6's hand-tuned funnel, the second
# baseline every learned row is compared against -- retrieval and rerank
# mode, both splits.
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking phased --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label phased --block headline --out chapters/ch07/expected/validation-phased.json > chapters/ch07/expected/validation-phased.block.md
chapters/ch07/expected/validation-phased.json, chapters/ch07/expected/validation-phased.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking phased --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label phased --block headline --out chapters/ch07/expected/test-phased.json > chapters/ch07/expected/test-phased.block.md
chapters/ch07/expected/test-phased.json, chapters/ch07/expected/test-phased.block.md

.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking phased --mode rerank --passes 1 --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label phased --block headline --out chapters/ch07/expected/validation-phased-rerank.json > chapters/ch07/expected/validation-phased-rerank.block.md
chapters/ch07/expected/validation-phased-rerank.json, chapters/ch07/expected/validation-phased-rerank.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking phased --mode rerank --passes 1 --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label phased --block headline --out chapters/ch07/expected/test-phased-rerank.json > chapters/ch07/expected/test-phased-rerank.block.md
chapters/ch07/expected/test-phased-rerank.json, chapters/ch07/expected/test-phased-rerank.block.md

<!-- Comparisons pairing `phased` with any `ltr_second*` / `ltr_global*`
     report (compare-{validation,test}-vs-first-stage, compare-*-vs-phased,
     compare-*-rerank-vs-first-stage, evaluations, evaluations-latency) are
     at item 21 below, once every M2 report exists. -->

# item 5: training (an artefact, not a measurement -- module docstring). One
# shape at a time, same train CSV, seed 42. M1's
# chosen shape, its offline-grid counterpart, the two extra curve points, and
# the fixed large shape (already trained, left as is); M2's two shapes.
.venv/bin/python chapters/ch07/train_ltr.py --split train --model second --leaves 3 --rounds 100 --out chapters/ch07/expected/train-second.json --model-out chapters/ch07/app/models/ltr_second.json --native-out chapters/ch07/models_native/ltr_second.lgb
chapters/ch07/expected/train-second.json, chapters/ch07/app/models/ltr_second.json, chapters/ch07/models_native/ltr_second.lgb

.venv/bin/python chapters/ch07/train_ltr.py --split train --model second --grid --out chapters/ch07/expected/train-second-offline.json --model-out chapters/ch07/app/models/ltr_second_offline.json --native-out chapters/ch07/models_native/ltr_second_offline.lgb
chapters/ch07/expected/train-second-offline.json, chapters/ch07/app/models/ltr_second_offline.json, chapters/ch07/models_native/ltr_second_offline.lgb

.venv/bin/python chapters/ch07/train_ltr.py --split train --model second --leaves 3 --rounds 50 --out chapters/ch07/expected/train-second-tiny.json --model-out chapters/ch07/app/models/ltr_second_tiny.json
chapters/ch07/expected/train-second-tiny.json, chapters/ch07/app/models/ltr_second_tiny.json

.venv/bin/python chapters/ch07/train_ltr.py --split train --model second --leaves 15 --rounds 200 --out chapters/ch07/expected/train-second-mid.json --model-out chapters/ch07/app/models/ltr_second_mid.json
chapters/ch07/expected/train-second-mid.json, chapters/ch07/app/models/ltr_second_mid.json

# `ltr_second_large` (31 x 800) is already trained on this log and left as is
# (`expected/train-second-large.json` records its shape and sha256) -- no
# command re-run here.

.venv/bin/python chapters/ch07/train_ltr.py --split train --model global --grid --out chapters/ch07/expected/train-global.json --model-out chapters/ch07/app/models/ltr_global.json --native-out chapters/ch07/models_native/ltr_global.lgb
chapters/ch07/expected/train-global.json, chapters/ch07/app/models/ltr_global.json, chapters/ch07/models_native/ltr_global.lgb

.venv/bin/python chapters/ch07/train_ltr.py --split train --model global --leaves 3 --rounds 200 --out chapters/ch07/expected/train-global-200.json --model-out chapters/ch07/app/models/ltr_global_200.json --native-out chapters/ch07/models_native/ltr_global_200.lgb
chapters/ch07/expected/train-global-200.json, chapters/ch07/app/models/ltr_global_200.json, chapters/ch07/models_native/ltr_global_200.lgb

# item 6: ONNX export of the two chosen models only
# (`ltr_second_offline` / `ltr_global_200` are comparison rows, not a
# second ONNX pair; see `ltr_second_onnx.profile`'s own comment).
.venv/bin/python chapters/ch07/export_onnx.py --model chapters/ch07/models_native/ltr_second.lgb --out chapters/ch07/app/models/onnx/ltr_second.onnx --out-report chapters/ch07/expected/export-second.json
chapters/ch07/app/models/onnx/ltr_second.onnx, chapters/ch07/expected/export-second.json

.venv/bin/python chapters/ch07/export_onnx.py --model chapters/ch07/models_native/ltr_global.lgb --out chapters/ch07/app/models/onnx/ltr_global.onnx --out-report chapters/ch07/expected/export-global.json
chapters/ch07/app/models/onnx/ltr_global.onnx, chapters/ch07/expected/export-global.json

<!-- The package is deployed here, with the model files above and the profiles that read them (five M1 + M1 onnx + two M2 + M2 onnx) and `features_second`. The committed package already carries these files; the run sheet redeploys (`vespa deploy --wait 300 chapters/ch07/app`) only if a sha256 in a train-*.json or export-*.json differs from the committed report. -->

# item 7: M1 family, retrieval mode, validation -- the five-point shape
# curve plus the ONNX pair. Ordered along the curve: tiny, chosen,
# offline, mid, large.
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second_tiny --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_tiny --block headline --out chapters/ch07/expected/validation-ltr_second_tiny.json > chapters/ch07/expected/validation-ltr_second_tiny.block.md
chapters/ch07/expected/validation-ltr_second_tiny.json, chapters/ch07/expected/validation-ltr_second_tiny.block.md

.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second --block headline --out chapters/ch07/expected/validation-ltr_second.json > chapters/ch07/expected/validation-ltr_second.block.md
chapters/ch07/expected/validation-ltr_second.json, chapters/ch07/expected/validation-ltr_second.block.md

.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second_offline --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_offline --block headline --out chapters/ch07/expected/validation-ltr_second_offline.json > chapters/ch07/expected/validation-ltr_second_offline.block.md
chapters/ch07/expected/validation-ltr_second_offline.json, chapters/ch07/expected/validation-ltr_second_offline.block.md

.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second_mid --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_mid --block headline --out chapters/ch07/expected/validation-ltr_second_mid.json > chapters/ch07/expected/validation-ltr_second_mid.block.md
chapters/ch07/expected/validation-ltr_second_mid.json, chapters/ch07/expected/validation-ltr_second_mid.block.md

.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second_large --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_large --block headline --out chapters/ch07/expected/validation-ltr_second_large.json > chapters/ch07/expected/validation-ltr_second_large.block.md
chapters/ch07/expected/validation-ltr_second_large.json, chapters/ch07/expected/validation-ltr_second_large.block.md

.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second_onnx --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_onnx --block headline --out chapters/ch07/expected/validation-ltr_second_onnx.json > chapters/ch07/expected/validation-ltr_second_onnx.block.md
chapters/ch07/expected/validation-ltr_second_onnx.json, chapters/ch07/expected/validation-ltr_second_onnx.block.md

# item 8: M1 chosen test, retrieval mode -- only the chosen shape and its
# ONNX pair spend test (the shape-sweep rows stay validation-only).
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_second --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second --block headline --out chapters/ch07/expected/test-ltr_second.json > chapters/ch07/expected/test-ltr_second.block.md
chapters/ch07/expected/test-ltr_second.json, chapters/ch07/expected/test-ltr_second.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_second_onnx --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_onnx --block headline --out chapters/ch07/expected/test-ltr_second_onnx.json > chapters/ch07/expected/test-ltr_second_onnx.block.md
chapters/ch07/expected/test-ltr_second_onnx.json, chapters/ch07/expected/test-ltr_second_onnx.block.md

# item 9: M1 family, rerank mode, passes 1, both splits (chosen shape and its
# ONNX pair only -- same rule as retrieval-mode test).
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second --mode rerank --passes 1 --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second --block headline --out chapters/ch07/expected/validation-ltr_second-rerank.json > chapters/ch07/expected/validation-ltr_second-rerank.block.md
chapters/ch07/expected/validation-ltr_second-rerank.json, chapters/ch07/expected/validation-ltr_second-rerank.block.md

.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second_onnx --mode rerank --passes 1 --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_onnx --block headline --out chapters/ch07/expected/validation-ltr_second_onnx-rerank.json > chapters/ch07/expected/validation-ltr_second_onnx-rerank.block.md
chapters/ch07/expected/validation-ltr_second_onnx-rerank.json, chapters/ch07/expected/validation-ltr_second_onnx-rerank.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_second --mode rerank --passes 1 --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second --block headline --out chapters/ch07/expected/test-ltr_second-rerank.json > chapters/ch07/expected/test-ltr_second-rerank.block.md
chapters/ch07/expected/test-ltr_second-rerank.json, chapters/ch07/expected/test-ltr_second-rerank.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_second_onnx --mode rerank --passes 1 --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_onnx --block headline --out chapters/ch07/expected/test-ltr_second_onnx-rerank.json > chapters/ch07/expected/test-ltr_second_onnx-rerank.block.md
chapters/ch07/expected/test-ltr_second_onnx-rerank.json, chapters/ch07/expected/test-ltr_second_onnx-rerank.block.md

# item 9b: the offline pick's own rerank-mode row, validation only -- the
# mode where the offline choice is expected to hold.
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second_offline --mode rerank --passes 1 --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_offline --block headline --out chapters/ch07/expected/validation-ltr_second_offline-rerank.json > chapters/ch07/expected/validation-ltr_second_offline-rerank.block.md
chapters/ch07/expected/validation-ltr_second_offline-rerank.json, chapters/ch07/expected/validation-ltr_second_offline-rerank.block.md

# item 10: compare blocks, M1. The retrieval-mode validation block against
# first_stage over the full five-shape curve plus ONNX -- where the offline
# pick's noise against the chosen shape's real win shows -- is built at
# item 21, together with `phased` and the three M2 profiles, and shown once
# there.

# item 10 (native vs ONNX, M1):

# native vs ONNX, both splits -- parity's engine-side counterpart (the
# quality numbers, not the per-pair diffs `test_model_parity.py` reports).
.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_second --out chapters/ch07/expected/compare-validation-native-vs-onnx.json chapters/ch07/expected/validation-ltr_second.json chapters/ch07/expected/validation-ltr_second_onnx.json > chapters/ch07/expected/compare-validation-native-vs-onnx.block.md
chapters/ch07/expected/compare-validation-native-vs-onnx.json, chapters/ch07/expected/compare-validation-native-vs-onnx.block.md

.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_second --out chapters/ch07/expected/compare-test-native-vs-onnx.json chapters/ch07/expected/test-ltr_second.json chapters/ch07/expected/test-ltr_second_onnx.json > chapters/ch07/expected/compare-test-native-vs-onnx.block.md
chapters/ch07/expected/compare-test-native-vs-onnx.json, chapters/ch07/expected/compare-test-native-vs-onnx.block.md

# evaluations / evaluations-latency (validation) and the rerank-mode
# vs-first-stage compares (both splits) are likewise built at item 21, with
# `phased` and the M2 profiles included -- shown once, there.

# item 11: parity, M1 -- native first (exact agreement expected), then the
# ONNX pair. Full validation split, no --limit. The M2 parity runs are
# below, after item 17.
.venv/bin/python chapters/ch07/test_model_parity.py --split validation --profile ltr_second --model chapters/ch07/models_native/ltr_second.lgb --check-shape --out chapters/ch07/expected/parity-validation-ltr_second.json --block parity > chapters/ch07/expected/parity-validation-ltr_second.block.md
chapters/ch07/expected/parity-validation-ltr_second.json, chapters/ch07/expected/parity-validation-ltr_second.block.md

.venv/bin/python chapters/ch07/test_model_parity.py --split validation --profile ltr_second_onnx --model chapters/ch07/models_native/ltr_second.lgb --onnx chapters/ch07/app/models/onnx/ltr_second.onnx --check-shape --out chapters/ch07/expected/parity-validation-ltr_second_onnx.json --block parity > chapters/ch07/expected/parity-validation-ltr_second_onnx.block.md
chapters/ch07/expected/parity-validation-ltr_second_onnx.json, chapters/ch07/expected/parity-validation-ltr_second_onnx.block.md

# item 12: training-side blocks, `--from` a committed report -- no training,
# app/ untouched. M1's grid table comes from `train-second-offline.json`
# (`ltr_second`'s own report is fixed-shape, `grid: null`); M2's grid and
# importance both come from `train-global.json`, the `--grid` run above,
# whose pick is the 3 x 100 model the package ships, byte-identical.
.venv/bin/python chapters/ch07/train_ltr.py --from chapters/ch07/expected/train-second.json --block importance > chapters/ch07/expected/train-second-importance.block.md
chapters/ch07/expected/train-second-importance.block.md

.venv/bin/python chapters/ch07/train_ltr.py --from chapters/ch07/expected/train-second-offline.json --block grid > chapters/ch07/expected/train-second-grid.block.md
chapters/ch07/expected/train-second-grid.block.md

.venv/bin/python chapters/ch07/train_ltr.py --from chapters/ch07/expected/train-global.json --block importance > chapters/ch07/expected/train-global-importance.block.md
chapters/ch07/expected/train-global-importance.block.md

.venv/bin/python chapters/ch07/train_ltr.py --from chapters/ch07/expected/train-global.json --block grid > chapters/ch07/expected/train-global-grid.block.md
chapters/ch07/expected/train-global-grid.block.md

# item 13: worked query -- the tie pattern (3-leaf model, many equal scores)
# against the 31-leaf model.
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking ltr_second --param 'input.query(qt)=embed(colbert, "running shoes")' --param 'input.query(qt_cross)=embed(tokenizer, "running shoes")' --param 'timeout=10s' --hits 10 --block features > chapters/ch07/expected/features-running-shoes-ltr_second.block.md
chapters/ch07/expected/features-running-shoes-ltr_second.block.md

.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking ltr_second_large --param 'input.query(qt)=embed(colbert, "running shoes")' --param 'input.query(qt_cross)=embed(tokenizer, "running shoes")' --param 'timeout=10s' --hits 10 --block features > chapters/ch07/expected/features-running-shoes-ltr_second_large.block.md
chapters/ch07/expected/features-running-shoes-ltr_second_large.block.md

# item 13b: the same worked query under M2.
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking ltr_global --param 'input.query(qt)=embed(colbert, "running shoes")' --param 'input.query(qt_cross)=embed(tokenizer, "running shoes")' --param 'timeout=10s' --hits 10 --block features > chapters/ch07/expected/features-running-shoes-ltr_global.block.md
chapters/ch07/expected/features-running-shoes-ltr_global.block.md

# item 14: external inference benchmark, M1 only, mock service on the host
# (not the container). Full split, no `--limit`: the fetch leg uses
# `features_second`, which never runs the cross-encoder, so the full
# validation split stays affordable (22 m measured, below).
.venv/bin/python chapters/ch07/benchmark_inference.py --split validation --model chapters/ch07/models_native/ltr_second.lgb --candidates 10,25,100 --passes 3 --out chapters/ch07/expected/benchmark-inference.json --block benchmark > chapters/ch07/expected/benchmark-inference.block.md
chapters/ch07/expected/benchmark-inference.json, chapters/ch07/expected/benchmark-inference.block.md

# items 15-20: every M2 request asks for exactly the hits the global phase
# reranks (the top of this file says why). `--hits 10` costs ≈ 0.91 s/query,
# close to `phased`'s 0.95 s.

# item 15: M2 retrieval, validation, both shapes -- the inputs to the
# choice between them.
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_global --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global --block headline --out chapters/ch07/expected/validation-ltr_global.json > chapters/ch07/expected/validation-ltr_global.block.md
chapters/ch07/expected/validation-ltr_global.json, chapters/ch07/expected/validation-ltr_global.block.md

.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_global_200 --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global_200 --block headline --out chapters/ch07/expected/validation-ltr_global_200.json > chapters/ch07/expected/validation-ltr_global_200.block.md
chapters/ch07/expected/validation-ltr_global_200.json, chapters/ch07/expected/validation-ltr_global_200.block.md

# item 16: the tie rule -- compare.py --baseline phased over
# the two M2 shapes, then the tie-break (--baseline ltr_global over the two).
# Both inside the noise against `phased`; the tie-break also inside the noise
# -- "ties -> the smaller" keeps `ltr_global` (3x100), the name already
# deployed.
.venv/bin/python shared/tools/compare.py --block comparison --baseline phased --out chapters/ch07/expected/compare-validation-global-shapes.json chapters/ch07/expected/validation-phased.json chapters/ch07/expected/validation-ltr_global.json chapters/ch07/expected/validation-ltr_global_200.json > chapters/ch07/expected/compare-validation-global-shapes.block.md
chapters/ch07/expected/compare-validation-global-shapes.json, chapters/ch07/expected/compare-validation-global-shapes.block.md

.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_global --out chapters/ch07/expected/compare-validation-global-tiebreak.json chapters/ch07/expected/validation-ltr_global.json chapters/ch07/expected/validation-ltr_global_200.json > chapters/ch07/expected/compare-validation-global-tiebreak.block.md
chapters/ch07/expected/compare-validation-global-tiebreak.json, chapters/ch07/expected/compare-validation-global-tiebreak.block.md

# item 18: M2 chosen (`ltr_global`), retrieval mode, test -- only the winner
# spends test.
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_global --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global --block headline --out chapters/ch07/expected/test-ltr_global.json > chapters/ch07/expected/test-ltr_global.block.md
chapters/ch07/expected/test-ltr_global.json, chapters/ch07/expected/test-ltr_global.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_global --mode rerank --passes 1 --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global --block headline --out chapters/ch07/expected/test-ltr_global-rerank.json > chapters/ch07/expected/test-ltr_global-rerank.block.md
chapters/ch07/expected/test-ltr_global-rerank.json, chapters/ch07/expected/test-ltr_global-rerank.block.md

# item 19: M2 chosen's ONNX pair, `ltr_global_onnx` (the winner is
# `ltr_global`, so its ONNX export is the one served) -- validation, test,
# rerank test.
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_global_onnx --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global_onnx --block headline --out chapters/ch07/expected/validation-ltr_global_onnx.json > chapters/ch07/expected/validation-ltr_global_onnx.block.md
chapters/ch07/expected/validation-ltr_global_onnx.json, chapters/ch07/expected/validation-ltr_global_onnx.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_global_onnx --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global_onnx --block headline --out chapters/ch07/expected/test-ltr_global_onnx.json > chapters/ch07/expected/test-ltr_global_onnx.block.md
chapters/ch07/expected/test-ltr_global_onnx.json, chapters/ch07/expected/test-ltr_global_onnx.block.md

.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_global_onnx --mode rerank --passes 1 --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global_onnx --block headline --out chapters/ch07/expected/test-ltr_global_onnx-rerank.json > chapters/ch07/expected/test-ltr_global_onnx-rerank.block.md
chapters/ch07/expected/test-ltr_global_onnx-rerank.json, chapters/ch07/expected/test-ltr_global_onnx-rerank.block.md

# item 17: M2 rerank mode, validation, all three profiles. Rerank mode
# restricts the candidates to a query's judged ids via `recall`, but the
# match-feature `ltr_score_global` is still computed for every hit returned,
# and most validation queries carry more than ten judged ids (mean about 20,
# up to 94) -- so these requests ask for 10 hits, as many as the global phase reranks,
# like every other request on these profiles except the parity runs and the
# 25-hit row, which widen both counts together; the committed reports record
# `hits_requested: 10`. The
# winner's own rerank test is item 18 above.
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_global --mode rerank --passes 1 --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global --block headline --out chapters/ch07/expected/validation-ltr_global-rerank.json > chapters/ch07/expected/validation-ltr_global-rerank.block.md
chapters/ch07/expected/validation-ltr_global-rerank.json, chapters/ch07/expected/validation-ltr_global-rerank.block.md

.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_global_200 --mode rerank --passes 1 --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global_200 --block headline --out chapters/ch07/expected/validation-ltr_global_200-rerank.json > chapters/ch07/expected/validation-ltr_global_200-rerank.block.md
chapters/ch07/expected/validation-ltr_global_200-rerank.json, chapters/ch07/expected/validation-ltr_global_200-rerank.block.md

.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_global_onnx --mode rerank --passes 1 --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global_onnx --block headline --out chapters/ch07/expected/validation-ltr_global_onnx-rerank.json > chapters/ch07/expected/validation-ltr_global_onnx-rerank.block.md
chapters/ch07/expected/validation-ltr_global_onnx-rerank.json, chapters/ch07/expected/validation-ltr_global_onnx-rerank.block.md

# parity, all three M2 profiles (also `recall`-bounded, unaffected): exact for
# both native shapes, about 1.2e-6 for the ONNX sibling (`expected/parity-validation-
# ltr_global*.json`). The earlier failing row belonged to the models trained
# on the defective log and lives under `expected/before-cross-fix/`.
.venv/bin/python chapters/ch07/test_model_parity.py --split validation --profile ltr_global --model chapters/ch07/models_native/ltr_global.lgb --check-shape --out chapters/ch07/expected/parity-validation-ltr_global.json --block parity > chapters/ch07/expected/parity-validation-ltr_global.block.md
chapters/ch07/expected/parity-validation-ltr_global.json, chapters/ch07/expected/parity-validation-ltr_global.block.md

.venv/bin/python chapters/ch07/test_model_parity.py --split validation --profile ltr_global_200 --model chapters/ch07/models_native/ltr_global_200.lgb --check-shape --out chapters/ch07/expected/parity-validation-ltr_global_200.json --block parity > chapters/ch07/expected/parity-validation-ltr_global_200.block.md
chapters/ch07/expected/parity-validation-ltr_global_200.json, chapters/ch07/expected/parity-validation-ltr_global_200.block.md

.venv/bin/python chapters/ch07/test_model_parity.py --split validation --profile ltr_global_onnx --model chapters/ch07/models_native/ltr_global.lgb --onnx chapters/ch07/app/models/onnx/ltr_global.onnx --check-shape --out chapters/ch07/expected/parity-validation-ltr_global_onnx.json --block parity > chapters/ch07/expected/parity-validation-ltr_global_onnx.block.md
chapters/ch07/expected/parity-validation-ltr_global_onnx.json, chapters/ch07/expected/parity-validation-ltr_global_onnx.block.md

# item 21: compare blocks completing item 10 / ch06's forms, once every M2
# retrieval-mode report exists. `compare.py` prints a dash for `recall@100`
# on any M2 report (M2 reports never measure it -- the top of this file says
# why).

# vs `phased`, both splits -- `ltr_second` (M1 chosen) and the M2 winner
# (`ltr_global`) plus its ONNX pair, against the fully hand-tuned funnel.
.venv/bin/python shared/tools/compare.py --block comparison --baseline phased --out chapters/ch07/expected/compare-validation-vs-phased.json chapters/ch07/expected/validation-phased.json chapters/ch07/expected/validation-ltr_second.json chapters/ch07/expected/validation-ltr_global.json chapters/ch07/expected/validation-ltr_global_onnx.json > chapters/ch07/expected/compare-validation-vs-phased.block.md
chapters/ch07/expected/compare-validation-vs-phased.json, chapters/ch07/expected/compare-validation-vs-phased.block.md

.venv/bin/python shared/tools/compare.py --block comparison --baseline phased --out chapters/ch07/expected/compare-test-vs-phased.json chapters/ch07/expected/test-phased.json chapters/ch07/expected/test-ltr_second.json chapters/ch07/expected/test-ltr_global.json chapters/ch07/expected/test-ltr_global_onnx.json > chapters/ch07/expected/compare-test-vs-phased.block.md
chapters/ch07/expected/compare-test-vs-phased.json, chapters/ch07/expected/compare-test-vs-phased.block.md

# vs `first_stage`, validation: the five-shape M1 curve plus ONNX (item 10),
# `phased`, and the three M2 profiles (`ltr_global_200` included).
.venv/bin/python shared/tools/compare.py --block comparison --baseline first_stage --out chapters/ch07/expected/compare-validation-vs-first-stage.json chapters/ch07/expected/validation-first_stage.json chapters/ch07/expected/validation-ltr_second_tiny.json chapters/ch07/expected/validation-ltr_second.json chapters/ch07/expected/validation-ltr_second_offline.json chapters/ch07/expected/validation-ltr_second_mid.json chapters/ch07/expected/validation-ltr_second_large.json chapters/ch07/expected/validation-ltr_second_onnx.json chapters/ch07/expected/validation-phased.json chapters/ch07/expected/validation-ltr_global.json chapters/ch07/expected/validation-ltr_global_200.json chapters/ch07/expected/validation-ltr_global_onnx.json > chapters/ch07/expected/compare-validation-vs-first-stage.block.md
chapters/ch07/expected/compare-validation-vs-first-stage.json, chapters/ch07/expected/compare-validation-vs-first-stage.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_second --out chapters/ch07/expected/compare-validation-second-vs-tiny.json chapters/ch07/expected/validation-ltr_second.json chapters/ch07/expected/validation-ltr_second_tiny.json > chapters/ch07/expected/compare-validation-second-vs-tiny.block.md
chapters/ch07/expected/compare-validation-second-vs-tiny.json, chapters/ch07/expected/compare-validation-second-vs-tiny.block.md (rendered 2026-09-27 from the two committed validation reports, offline; the chosen shape against the smaller one — ndcg@10 inside the noise, recall@100 real)

.venv/bin/python shared/tools/compare.py --block comparison --baseline first_stage --out chapters/ch07/expected/compare-test-vs-first-stage.json chapters/ch07/expected/test-first_stage.json chapters/ch07/expected/test-ltr_second.json chapters/ch07/expected/test-ltr_second_onnx.json chapters/ch07/expected/test-phased.json chapters/ch07/expected/test-ltr_global.json chapters/ch07/expected/test-ltr_global_onnx.json > chapters/ch07/expected/compare-test-vs-first-stage.block.md
chapters/ch07/expected/compare-test-vs-first-stage.json, chapters/ch07/expected/compare-test-vs-first-stage.block.md

# the global phase's own share -- baseline `ltr_second` (M1 chosen, the
# learned second phase over 400), the winner (`ltr_global`, the same second
# phase plus a learned global phase over 10).
.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_second --out chapters/ch07/expected/compare-validation-global-vs-second.json chapters/ch07/expected/validation-ltr_second.json chapters/ch07/expected/validation-ltr_global.json > chapters/ch07/expected/compare-validation-global-vs-second.block.md
chapters/ch07/expected/compare-validation-global-vs-second.json, chapters/ch07/expected/compare-validation-global-vs-second.block.md

# M2 native vs ONNX, both splits -- parity's engine-side counterpart, the
# same form as item 10's M1 pair.
.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_global --out chapters/ch07/expected/compare-validation-global-native-vs-onnx.json chapters/ch07/expected/validation-ltr_global.json chapters/ch07/expected/validation-ltr_global_onnx.json > chapters/ch07/expected/compare-validation-global-native-vs-onnx.block.md
chapters/ch07/expected/compare-validation-global-native-vs-onnx.json, chapters/ch07/expected/compare-validation-global-native-vs-onnx.block.md

.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_global --out chapters/ch07/expected/compare-test-global-native-vs-onnx.json chapters/ch07/expected/test-ltr_global.json chapters/ch07/expected/test-ltr_global_onnx.json > chapters/ch07/expected/compare-test-global-native-vs-onnx.block.md
chapters/ch07/expected/compare-test-global-native-vs-onnx.json, chapters/ch07/expected/compare-test-global-native-vs-onnx.block.md

# rerank-mode vs `first_stage`, both splits, each including everything
# measured in that mode (on test, the M2 rows are the winner and its ONNX
# pair, the only M2 rerank-mode test rows).
.venv/bin/python shared/tools/compare.py --block comparison --baseline first_stage --out chapters/ch07/expected/compare-validation-rerank-vs-first-stage.json chapters/ch07/expected/validation-first_stage-rerank.json chapters/ch07/expected/validation-ltr_second-rerank.json chapters/ch07/expected/validation-ltr_second_onnx-rerank.json chapters/ch07/expected/validation-ltr_second_offline-rerank.json chapters/ch07/expected/validation-ltr_global-rerank.json chapters/ch07/expected/validation-ltr_global_200-rerank.json chapters/ch07/expected/validation-ltr_global_onnx-rerank.json > chapters/ch07/expected/compare-validation-rerank-vs-first-stage.block.md
chapters/ch07/expected/compare-validation-rerank-vs-first-stage.json, chapters/ch07/expected/compare-validation-rerank-vs-first-stage.block.md

.venv/bin/python shared/tools/compare.py --block comparison --baseline first_stage --out chapters/ch07/expected/compare-test-rerank-vs-first-stage.json chapters/ch07/expected/test-first_stage-rerank.json chapters/ch07/expected/test-ltr_second-rerank.json chapters/ch07/expected/test-ltr_second_onnx-rerank.json chapters/ch07/expected/test-ltr_global-rerank.json chapters/ch07/expected/test-ltr_global_onnx-rerank.json > chapters/ch07/expected/compare-test-rerank-vs-first-stage.block.md
chapters/ch07/expected/compare-test-rerank-vs-first-stage.json, chapters/ch07/expected/compare-test-rerank-vs-first-stage.block.md

# M2 against `phased` in rerank mode, validation -- a rerank-mode reading
# of its own; the choice between the M2 shapes is made in retrieval mode
# (items 16/21), not here.
.venv/bin/python shared/tools/compare.py --block comparison --baseline phased --out chapters/ch07/expected/compare-validation-rerank-vs-phased.json chapters/ch07/expected/validation-phased-rerank.json chapters/ch07/expected/validation-ltr_global-rerank.json chapters/ch07/expected/validation-ltr_global_200-rerank.json chapters/ch07/expected/validation-ltr_global_onnx-rerank.json > chapters/ch07/expected/compare-validation-rerank-vs-phased.block.md
chapters/ch07/expected/compare-validation-rerank-vs-phased.json, chapters/ch07/expected/compare-validation-rerank-vs-phased.block.md

# evaluations / evaluations-latency, validation, every row including
# `phased` and the three M2 profiles.
.venv/bin/python shared/tools/compare.py --block evaluations --out chapters/ch07/expected/compare-validation-evaluations.json chapters/ch07/expected/validation-first_stage.json chapters/ch07/expected/validation-ltr_second_tiny.json chapters/ch07/expected/validation-ltr_second.json chapters/ch07/expected/validation-ltr_second_offline.json chapters/ch07/expected/validation-ltr_second_mid.json chapters/ch07/expected/validation-ltr_second_large.json chapters/ch07/expected/validation-ltr_second_onnx.json chapters/ch07/expected/validation-phased.json chapters/ch07/expected/validation-ltr_global.json chapters/ch07/expected/validation-ltr_global_200.json chapters/ch07/expected/validation-ltr_global_onnx.json > chapters/ch07/expected/compare-validation-evaluations.block.md
chapters/ch07/expected/compare-validation-evaluations.json, chapters/ch07/expected/compare-validation-evaluations.block.md

.venv/bin/python shared/tools/compare.py --block evaluations-latency --out chapters/ch07/expected/compare-validation-latency.json chapters/ch07/expected/validation-first_stage.json chapters/ch07/expected/validation-ltr_second_tiny.json chapters/ch07/expected/validation-ltr_second.json chapters/ch07/expected/validation-ltr_second_offline.json chapters/ch07/expected/validation-ltr_second_mid.json chapters/ch07/expected/validation-ltr_second_large.json chapters/ch07/expected/validation-ltr_second_onnx.json chapters/ch07/expected/validation-phased.json chapters/ch07/expected/validation-ltr_global.json chapters/ch07/expected/validation-ltr_global_200.json chapters/ch07/expected/validation-ltr_global_onnx.json > chapters/ch07/expected/compare-validation-latency.block.md
chapters/ch07/expected/compare-validation-latency.json, chapters/ch07/expected/compare-validation-latency.block.md

## Ours, not for the reader (kept for the record)

# drift demonstration 1: the current `ltr_second` (3 x 100) against a CSV
# logged on an older container (a reader has no older container). This
# chapter's feature logs are written on the container that serves the
# models; a log written on another container carries BM25 statistics a few
# hundredths different, and this row shows what that does to parity.
.venv/bin/python chapters/ch07/test_model_parity.py --split validation --profile ltr_second --model chapters/ch07/models_native/ltr_second.lgb --check-shape --features-csv builds/esci-us-hard-book-s42-kdd-v4/features/old-container-2026-09-21/features-validation.csv --out chapters/ch07/expected/parity-validation-ltr_second-oldlog.json --block parity > chapters/ch07/expected/parity-validation-ltr_second-oldlog.block.md
chapters/ch07/expected/parity-validation-ltr_second-oldlog.json, chapters/ch07/expected/parity-validation-ltr_second-oldlog.block.md

# drift demonstration 2: the corrected model scored against the defective
# log (a reader who regenerated their own log has
# no defective one to compare against -- this is ours, and it is a parity
# check catching a feature logged wrong). `nocross-2026-09-22` is the
# feature log ch06's tool wrote before it was corrected -- `cross_logit`
# computed against an empty query, no signal. The gap this shows (86%
# of pairs beyond tolerance, max 2.13) is not the few-thousandths drift
# approximate retrieval causes; it is what training on the
# corrected model but scoring against the broken column looks like.
.venv/bin/python chapters/ch07/test_model_parity.py --split validation --profile ltr_global --model chapters/ch07/models_native/ltr_global.lgb --check-shape --features-csv builds/esci-us-hard-book-s42-kdd-v4/features/nocross-2026-09-22/features-validation.csv --out chapters/ch07/expected/parity-validation-ltr_global-nocross.json --block parity > chapters/ch07/expected/parity-validation-ltr_global-nocross.block.md
chapters/ch07/expected/parity-validation-ltr_global-nocross.json, chapters/ch07/expected/parity-validation-ltr_global-nocross.block.md

# `chapters/ch07/expected/before-cross-fix/`: every M2 report this file's
# own commands (items 15-21 above) produced on the defective `cross_logit`
# log -- kept exactly as measured, not deleted or
# hand-edited, because it is the "before" half of a parity check catching
# a silently wrong feature. It holds the earlier `ltr_global` (3x100) and
# the profile then named `ltr_global_offline` (3x200, the offline grid's
# pick on that log -- on the corrected log the grid picks 3x100, the shape
# the tie rule keeps, and 3x200 lives on as `ltr_global_200`), both shapes'
# ONNX and rerank rows, and the compare blocks built from them. None of it is
# reproducible by a reader who regenerated their own (correct) log; a reader
# who wants to see the defect for themselves runs the nocross drift
# demonstration above instead, against the *current* fixed models.

## Extended (ours, one machine)

# The extended row: M2 at global rerank-count 25 rather than 10, a served
# override (`ranking.globalPhase.rerankCount`), not a second profile -- the
# same convention chapter 6 uses for `phased`. Validation only, one pass.
# `--hits 25`, by the same rule as every M2 request (the top of this file),
# costs ≈ 25 x 81–85 ms ≈ 2.0–2.1 s/query. The two commands follow.
#
# Result: ndcg@10 0.521, p50 2,179.5 ms (mean 2,184.9 ms) -- above both this profile's own
# @10 row (0.510) and `phased` (0.502); no bracket taken against either (the
# extended row is reported on its own, not compared). The reading on the
# defective log is kept under `expected/before-cross-fix/`.

# item 20: @25 extended row -- the winner, validation
# only, one pass, hits 25 == the global phase's own rerank count override.
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_global --param 'ranking.globalPhase.rerankCount=25' --hits 25 --passes 1 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global_g25 --block headline --out chapters/ch07/expected/validation-ltr_global-g25.json > chapters/ch07/expected/validation-ltr_global-g25.block.md
chapters/ch07/expected/validation-ltr_global-g25.json, chapters/ch07/expected/validation-ltr_global-g25.block.md

# evaluations-latency again, adding the @25 extended report (item 20).
.venv/bin/python shared/tools/compare.py --block evaluations-latency --out chapters/ch07/expected/compare-validation-latency-extended.json chapters/ch07/expected/validation-first_stage.json chapters/ch07/expected/validation-ltr_second_tiny.json chapters/ch07/expected/validation-ltr_second.json chapters/ch07/expected/validation-ltr_second_offline.json chapters/ch07/expected/validation-ltr_second_mid.json chapters/ch07/expected/validation-ltr_second_large.json chapters/ch07/expected/validation-ltr_second_onnx.json chapters/ch07/expected/validation-phased.json chapters/ch07/expected/validation-ltr_global.json chapters/ch07/expected/validation-ltr_global_200.json chapters/ch07/expected/validation-ltr_global_onnx.json chapters/ch07/expected/validation-ltr_global-g25.json > chapters/ch07/expected/compare-validation-latency-extended.block.md
chapters/ch07/expected/compare-validation-latency-extended.json, chapters/ch07/expected/compare-validation-latency-extended.block.md

## Measured wall times

Every Core command was run once more from an empty machine on 2026-09-24 (Apple M4 Pro, 4 CPU / 10 GB Rancher Desktop VM), with each command's wall time recorded. Sums: cold bootstrap 45 m; feature log × 3 1 h 45 m; memory 20 m; `first_stage` four rows 18 m; `phased` four rows 2 h 48 m; training + export 1 m; M1 six validation rows 27 m, two test rows 13 m, five rerank rows 10 m; parity M1 2 m; benchmark 22 m; M2 two validation rows 1 h 30 m; M2 test + rerank test 1 h 36 m; ONNX global validation / test / rerank 2 h 21 m; M2 rerank validation rows ≈ 2 h 10 m at 43 m each (the three rows were timed at the earlier 400-hit setting; the documented 10-hit form was not re-timed); M2 parity three rows ≈ 1 h 06 m. **From an empty machine, 16 h 13 m in total. Rebuilding chapter 6's state from an empty container, then the bootstrap, the integration tests, the three feature-log passes, the first-stage baselines, every M1 row, M1 parity and the benchmark: 3 h 54 m.** An estimate for running them again starts from these numbers.

## 2026-10-04 re-measurement (targetHits decoupled from hits)

`shared/tools/evaluate.py` gained `--target-hits N` (default: the same number as
`--hits`, so every earlier command and block is unchanged; the report records
`"target_hits"` beside `hits_requested`). The shipped `ltr_global*` rows return
ten hits and so also asked the vector arm for ten neighbours; with the flag a
ten-hit request keeps a four-hundred-candidate union. Run on a fresh container
at chapter 6's state (see chapter 6's `COMMANDS.md`, *2026-10-04 regeneration*),
then `./bootstrap.sh ch07` (about 30 s: the `ml` group installed, the cross-encoder
file verified, this chapter's package deployed with its shipped model files, no
feed; log `chapters/ch07/review/bootstrap-regen-2026-10-04.txt`). Every new
report has its own name; no shipped file was overwritten.

./bootstrap.sh ch07
(embedder=BAAI/bge-small-en-v1.5@5c38ec7c colbert=colbert-ir/colbertv2.0@c1e84128; 101,341 documents)

# Validation, `--passes 3` (quality from the first pass, latency the median of three).
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_global --hits 10 --passes 3 --label ltr_global --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --block headline --out chapters/ch07/expected/validation-ltr_global-rerun.json > chapters/ch07/expected/validation-ltr_global-rerun.block.md
chapters/ch07/expected/validation-ltr_global-rerun.json, chapters/ch07/expected/validation-ltr_global-rerun.block.md
(45m 08s)

.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_global --hits 10 --target-hits 400 --passes 3 --label ltr_global_t400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --block headline --out chapters/ch07/expected/validation-ltr_global-t400.json > chapters/ch07/expected/validation-ltr_global-t400.block.md
chapters/ch07/expected/validation-ltr_global-t400.json, chapters/ch07/expected/validation-ltr_global-t400.block.md
(45m 19s)

.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking phased --hits 10 --target-hits 400 --passes 3 --label phased_h10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --block headline --out chapters/ch07/expected/validation-phased-h10-t400.json > chapters/ch07/expected/validation-phased-h10-t400.block.md
chapters/ch07/expected/validation-phased-h10-t400.json, chapters/ch07/expected/validation-phased-h10-t400.block.md
(45m 35s)

# Test, `--passes 1` (quality only).
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_global --hits 10 --passes 1 --label ltr_global --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --block headline --out chapters/ch07/expected/test-ltr_global-rerun.json > chapters/ch07/expected/test-ltr_global-rerun.block.md
chapters/ch07/expected/test-ltr_global-rerun.json, chapters/ch07/expected/test-ltr_global-rerun.block.md
(31m 58s)

.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_global --hits 10 --target-hits 400 --passes 1 --label ltr_global_t400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --block headline --out chapters/ch07/expected/test-ltr_global-t400.json > chapters/ch07/expected/test-ltr_global-t400.block.md
chapters/ch07/expected/test-ltr_global-t400.json, chapters/ch07/expected/test-ltr_global-t400.block.md
(32m 01s)

# Comparisons. The rerun and the shipped report carry the same label
# (`ltr_global`), and `compare.py` keys runs by label, so two reports with one
# label would collapse into one row; the rerun is read from a copy whose
# `label` is `ltr_global_rerun` (only that key changed; the copy lives outside
# the repository). Everything else is `compare.py` as it is.
.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_global --out chapters/ch07/expected/compare-validation-target400.json chapters/ch07/expected/validation-ltr_global-rerun.json chapters/ch07/expected/validation-ltr_global-t400.json > chapters/ch07/expected/compare-validation-target400.block.md
chapters/ch07/expected/compare-validation-target400.json, chapters/ch07/expected/compare-validation-target400.block.md

.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_global --out chapters/ch07/expected/compare-test-target400.json chapters/ch07/expected/test-ltr_global-rerun.json chapters/ch07/expected/test-ltr_global-t400.json > chapters/ch07/expected/compare-test-target400.block.md
chapters/ch07/expected/compare-test-target400.json, chapters/ch07/expected/compare-test-target400.block.md

.venv/bin/python -c "import json; d=json.load(open('chapters/ch07/expected/validation-ltr_global-rerun.json')); d['label']='ltr_global_rerun'; json.dump(d, open('<scratch>/validation-ltr_global-rerun-relabelled.json', 'w'), indent=2)"
.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_global --out chapters/ch07/expected/compare-validation-rerun-drift.json chapters/ch07/expected/validation-ltr_global.json <scratch>/validation-ltr_global-rerun-relabelled.json > chapters/ch07/expected/compare-validation-rerun-drift.block.md
chapters/ch07/expected/compare-validation-rerun-drift.json, chapters/ch07/expected/compare-validation-rerun-drift.block.md

.venv/bin/python -c "import json; d=json.load(open('chapters/ch07/expected/test-ltr_global-rerun.json')); d['label']='ltr_global_rerun'; json.dump(d, open('<scratch>/test-ltr_global-rerun-relabelled.json', 'w'), indent=2)"
.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_global --out chapters/ch07/expected/compare-test-rerun-drift.json chapters/ch07/expected/test-ltr_global.json <scratch>/test-ltr_global-rerun-relabelled.json > chapters/ch07/expected/compare-test-rerun-drift.block.md
chapters/ch07/expected/compare-test-rerun-drift.json, chapters/ch07/expected/compare-test-rerun-drift.block.md

.venv/bin/python shared/tools/compare.py --block evaluations-latency --out chapters/ch07/expected/compare-validation-latency-target400.json chapters/ch07/expected/validation-phased-h10-t400.json chapters/ch07/expected/validation-ltr_global-rerun.json chapters/ch07/expected/validation-ltr_global-t400.json > chapters/ch07/expected/compare-validation-latency-target400.block.md
chapters/ch07/expected/compare-validation-latency-target400.json, chapters/ch07/expected/compare-validation-latency-target400.block.md

# Three more brackets against the shipped 400-hit `phased` row, so the t400 and
# ten-hit-shape effects can be read on their own.
.venv/bin/python shared/tools/compare.py --block comparison --baseline phased --out chapters/ch07/expected/compare-validation-t400-vs-phased.json chapters/ch07/expected/validation-phased.json chapters/ch07/expected/validation-ltr_global-t400.json > chapters/ch07/expected/compare-validation-t400-vs-phased.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline phased --out chapters/ch07/expected/compare-test-t400-vs-phased.json chapters/ch07/expected/test-phased.json chapters/ch07/expected/test-ltr_global-t400.json > chapters/ch07/expected/compare-test-t400-vs-phased.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline phased --out chapters/ch07/expected/compare-validation-phased-h10-vs-phased.json chapters/ch07/expected/validation-phased.json chapters/ch07/expected/validation-phased-h10-t400.json > chapters/ch07/expected/compare-validation-phased-h10-vs-phased.block.md
chapters/ch07/expected/compare-{validation,test}-t400-vs-phased.*, chapters/ch07/expected/compare-validation-phased-h10-vs-phased.*

# 2026-10-05: the two ten-hit rows against each other on the one container (same candidates, same response size; validation only).
.venv/bin/python shared/tools/compare.py --block comparison --baseline phased_h10 --out chapters/ch07/expected/compare-validation-t400-vs-phased-h10.json chapters/ch07/expected/validation-phased-h10-t400.json chapters/ch07/expected/validation-ltr_global-t400.json > chapters/ch07/expected/compare-validation-t400-vs-phased-h10.block.md
chapters/ch07/expected/compare-validation-t400-vs-phased-h10.json, chapters/ch07/expected/compare-validation-t400-vs-phased-h10.block.md   # +0.008 [+0.000, +0.017], the lower end at zero

What the runs say (every figure is in the reports above):

| row | validation ndcg@10 | test ndcg@10 | validation p50 / p95 (ms) |
|---|---|---|---|
| `ltr_global`, shipped (earlier container, `hits` 10, `targetHits` 10) | 0.5102 | 0.5037 | 913.5 / 922.1 |
| `ltr_global`, rerun (this container, `hits` 10, `targetHits` 10) | 0.5110 | 0.5028 | 921.3 / 934.1 |
| `ltr_global_t400` (this container, `hits` 10, `targetHits` 400) | 0.5094 | 0.5007 | 922.1 / 940.0 |
| `phased_h10` (this container, `hits` 10, `targetHits` 400) | 0.5009 | not run | 927.8 / 940.2 |
| `phased`, shipped (earlier container, `hits` 400) | 0.5023 | 0.4993 | 947.3 / 970.2 |

| difference in ndcg@10 (95% bootstrap interval) | validation | test |
|---|---|---|
| `ltr_global_t400` − `ltr_global` rerun (the vector arm's depth, one container) | −0.002 [−0.005, +0.001] | −0.002 [−0.004, +0.000] |
| `ltr_global` rerun − shipped (container to container, same configuration) | +0.001 [−0.000, +0.002] | −0.001 [−0.002, +0.000] |
| `ltr_global_t400` − shipped `phased` (400 hits) | +0.007 [−0.001, +0.015] | +0.001 [−0.005, +0.008] |
| `ltr_global_t400` − `phased_h10` (same response size, same candidates) | +0.008 [+0.000, +0.017] | not run |
| `phased_h10` − shipped `phased` (response size only) | −0.001 [−0.004, +0.001] | not run |

Latency p50 / p95 on this container (median of three warm passes, validation):
`phased_h10` 927.8 / 940.2 ms, `ltr_global` 921.3 / 934.1 ms,
`ltr_global_t400` 922.1 / 940.0 ms.

## 2026-10-05 (the ten-hit pair's test half)

One loose end from the re-measurement above: the `phased_h10` row on the test split, so the ten-hit pair has a test bracket as well as a validation one. The container had to go back to chapter 7's state for it and was rebuilt for later work afterwards.

# A. A chapter-7 container (the container held a later state; removed, then rebuilt from the cached corpus).
docker rm -f vespa-book
./bootstrap.sh ch07
(embedder=BAAI/bge-small-en-v1.5@5c38ec7c colbert=colbert-ir/colbertv2.0@c1e84128; 101,341 documents; feed 29m 14s, whole command about 31 min; log `chapters/ch07/review/bootstrap-d138-2026-10-05.txt`)
The bootstrap rewrote the shipped `chapters/ch07/expected/feed.json`; it was restored with `git checkout -- chapters/ch07/expected/feed.json`. `ltr_second`, `ltr_global` and `phased` answered at ten hits with `timeout=30s`.

# B1. The `phased_h10` test row (`--passes 1`: quality only).
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking phased --hits 10 --target-hits 400 --passes 1 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label phased_h10 --block headline --out chapters/ch07/expected/test-phased-h10-t400.json > chapters/ch07/expected/test-phased-h10-t400.block.md
chapters/ch07/expected/test-phased-h10-t400.json, chapters/ch07/expected/test-phased-h10-t400.block.md
(34m 36s)

# B2. The two comparisons.
.venv/bin/python shared/tools/compare.py --block comparison --baseline phased_h10 --out chapters/ch07/expected/compare-test-t400-vs-phased-h10.json chapters/ch07/expected/test-phased-h10-t400.json chapters/ch07/expected/test-ltr_global-t400.json > chapters/ch07/expected/compare-test-t400-vs-phased-h10.block.md
chapters/ch07/expected/compare-test-t400-vs-phased-h10.json, chapters/ch07/expected/compare-test-t400-vs-phased-h10.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline phased --out chapters/ch07/expected/compare-test-phased-h10-vs-phased.json chapters/ch07/expected/test-phased.json chapters/ch07/expected/test-phased-h10-t400.json > chapters/ch07/expected/compare-test-phased-h10-vs-phased.block.md
chapters/ch07/expected/compare-test-phased-h10-vs-phased.json, chapters/ch07/expected/compare-test-phased-h10-vs-phased.block.md
(a few seconds each)

What the runs say (every figure is in the reports above):

| row | test ndcg@10 | validation ndcg@10 |
|---|---|---|
| `phased_h10` (this container, `hits` 10, `targetHits` 400) | 0.498 (recall@10 0.351, mrr 0.796; 1 pass, p50 / p95 983.2 / 1000.6 ms) | 0.5009 |

| difference in ndcg@10 (95% bootstrap interval) | test | validation (from the section above) |
|---|---|---|
| `ltr_global_t400` − `phased_h10` (same response size; test across two containers, validation on one) | +0.003 [−0.004, +0.009] | +0.008 [+0.000, +0.017] |
| `phased_h10` − shipped `phased` (response size only) | −0.001 [−0.004, +0.002] | −0.001 [−0.004, +0.001] |

# C. The container was then rebuilt for later work; nothing in this chapter reads it afterwards.
