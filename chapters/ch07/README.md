# Chapter 7 — Machine-Learned Ranking Inside the Engine

This directory is the code for Chapter 7 of *Production AI Search with Vespa*. It trains two small gradient-boosted tree models with LightGBM from the rank-feature log Chapter 6 wrote, serves them inside Vespa, and compares them with the first stage and with Chapter 6's hand-tuned funnel, `phased`, on the same 101,341 products and the same judged queries. M1 reads 51 features and reranks all 400 candidates in the second phase. M2 also reads the cross-encoder's logit and reranks the best ten in the global phase. The chapter then exports both models to ONNX, checks that the engine scores what the trained files score, and measures the same model behind an external HTTP service.

The book explains what each step does and why. This page is the practical half: what to run, in the same order as the chapter, what you should see, and what to do when something goes wrong.

## What is in this directory

```
chapters/ch07/
├── app/                                  the application package Vespa deploys
│   ├── services.xml                      unchanged from Chapter 6
│   ├── models/
│   │   ├── ltr_second.json               M1, 3 leaves × 100 rounds (the chosen shape)
│   │   ├── ltr_second_tiny.json          3 × 50     ┐
│   │   ├── ltr_second_offline.json       3 × 200    │ the other M1 shapes the
│   │   ├── ltr_second_mid.json           15 × 200   │ chapter compares
│   │   ├── ltr_second_large.json         31 × 800   ┘
│   │   ├── ltr_global.json               M2, 3 × 100 (the chosen shape)
│   │   ├── ltr_global_200.json           M2, 3 × 200 (the runner-up)
│   │   └── onnx/
│   │       ├── ltr_second.onnx           M1 exported to ONNX
│   │       └── ltr_global.onnx           M2 exported to ONNX
│   ├── schemas/
│   │   ├── product.sd                    Chapter 6's schema, plus the onnx-model declarations
│   │   │                                 for the two ONNX files; no new fields
│   │   └── product/                      one file per rank profile
│   │       ├── ltr_second*.profile       new: M1 and its shapes, and ltr_second_onnx
│   │       ├── ltr_global*.profile       new: M2 on top of M1, ltr_global_200 and ltr_global_onnx
│   │       ├── features_second.profile   new: logs M1's 51 features only, for the external benchmark
│   │       └── …                         Chapters 3 to 6's profiles, unchanged
│   └── search/query-profiles/
│       └── default.xml                   request defaults, unchanged: bm25_tuned is still the default
├── models_native/                        LightGBM's own save files, read by the export and parity tools
├── chapter.toml                          what bootstrap.sh needs for this chapter
├── ltr_data.py                           reads the feature log into training rows
├── train_ltr.py                          trains one shape, or a grid of shapes
├── export_onnx.py                        converts a trained model to ONNX and checks the conversion
├── test_model_parity.py                  checks the engine's scores against the trained file
├── benchmark_inference.py                the same model in the engine and behind an external service
├── COMMANDS.md                           every command, as run for the book
└── expected/                             the book's reference output
```

Chapter 6's `features_log.py` writes this chapter's feature log. The query tool, the evaluation tool, the comparison tool and the memory tool are shared by every chapter and live in `shared/tools/`.

## What you need

The same as Chapter 6, plus a group of Python packages for training and export.

|  | Version used for the book | Notes |
| :---- | :---- | :---- |
| Docker | — | Give it **4 CPUs and 10 GB of memory**. Docker Desktop or Rancher Desktop both work. |
| Python | 3.11 (3.11.13) | Only needed to create the virtual environment. |
| Vespa CLI | 8.562.17 | macOS: `brew install vespa-cli`. Linux and Windows: the Vespa GitHub releases page. |
| Models | Chapter 6's three | `bge-small-en-v1.5`, `colbertv2.0` and `ms-marco-MiniLM-L6-v2`, already in place if you are continuing. |
| Training packages | LightGBM 4.7.0, onnxmltools 1.16.0, onnx 1.22.0, onnxruntime 1.30.0, scikit-learn, skl2onnx | New. `bootstrap.sh` installs them as the `ml` requirements group. Only the tools use them; the deployed application reads the model files directly. |
| Network | — | Access to Hugging Face, only when starting fresh. |

Every pinned version is listed in `docs/pins.md` at the repository root.

## Run it

From the repository root:

```
./bootstrap.sh ch07
```

If you are continuing from Chapter 6, this installs the `ml` packages, confirms the corpus and the cross-encoder file, and deploys this chapter's application package: nine model files and ten new rank profiles. The chapter adds no fields, so nothing is fed. If you are starting with this chapter, add `--fresh`: it builds everything from the beginning and feeds the catalogue once, exactly as Chapter 6 did.

The deployment prints the same warning as in Chapters 5 and 6, about `document-summary 'context'`. That is expected.

On the reference machine (Apple M4 Pro, container VM with 4 CPUs and 10 GB), continuing from Chapter 6 took 15.2 seconds. A fresh run took 31 minutes 25 seconds, most of it the feed; a first run that also had to download the dataset took 68 minutes 11 seconds. Your timings will differ.

A successful run ends with the same state as Chapter 6:

```
== at the start of ch07
   build      builds/esci-us-hard-book-s42-kdd-v4
   image      vespaengine/vespa:8.751.13
   documents  101341
   embedders  embedder=BAAI/bge-small-en-v1.5@5c38ec7c colbert=colbert-ir/colbertv2.0@c1e84128
```

## The commands in this chapter

The steps below follow the chapter, section by section. Run them from the repository root after `bootstrap.sh` has finished.

Most commands save their result in `expected/`, replacing the book's copy of that file, so that `git diff chapters/ch07/expected/` shows how your run compares with the book's. To put the book's files back, run `git checkout chapters/ch07/expected/`.

**Budget your time.** Running every command below took about 16 hours on the reference machine, from an empty machine. Most of that is the requests that reach the cross-encoder: each one takes close to a second, and the `phased` and `ltr_global` rows run hundreds of them. The feature log, the first-stage rows, every M1 row, the M1 parity check and the external benchmark together took under 4 hours. Long steps are marked below.

**The same options as Chapter 6.** `--hits 400` returns 400 hits and asks the vector side for 400 nearest neighbors. `--reranker-input qt=colbert --reranker-input qt_cross=tokenizer` supplies the two query representations the late-interaction model and the cross-encoder need. Every request in this chapter sends both, even to profiles that do not rerank, because every profile here inherits features that read them.

**One new option.** `--mode rerank` restricts each query's request to the products judged for it, the task the feature log describes; `--passes 1` runs it once. Without `--mode`, the evaluation is in retrieval mode, ranking everything the request returns, as in every earlier chapter.

**Comparison tables are built last.** Several tables in the chapter set M1, M2 and their ONNX versions side by side, so they can only be built once every report exists. The commands for them are collected under *Building the comparison tables*, after the ONNX section. Each section below says which numbers you should see once they are built.

### Why model placement affects latency, cost, and feature availability

Nothing to run. The two placements are in `app/schemas/product/ltr_second.profile` (M1, second phase) and `app/schemas/product/ltr_global.profile` (M2, global phase).

### Training a compact learning-to-rank model from logged features

**Regenerating the log where the model will run.** Chapter 6's tool, writing this chapter's reports. Together these took about 1 hour 45 minutes:

```
.venv/bin/python chapters/ch06/features_log.py --split train --out chapters/ch07/expected/features-train.json
.venv/bin/python chapters/ch06/features_log.py --split validation --out chapters/ch07/expected/features-validation.json
.venv/bin/python chapters/ch06/features_log.py --split test --out chapters/ch07/expected/features-test.json
```

The CSV files are written under `builds/esci-us-hard-book-s42-kdd-v4/features/` and are not part of the repository; each JSON report records its CSV's sha256.

**What you should see:** 35,019, 14,926 and 21,503 judged pairs over 1,715, 735 and 1,050 queries.

**The two baselines, in both modes.** The first stage alone (`phased` with both rerank counts set to zero) and `phased` itself, on both splits, in retrieval mode and in rerank mode. The four `phased` rows took about 2 hours 48 minutes:

```
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking phased --hits 400 --param 'ranking.rerankCount=0' --param 'ranking.globalPhase.rerankCount=0' --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label first_stage --block headline --out chapters/ch07/expected/validation-first_stage.json > chapters/ch07/expected/validation-first_stage.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking phased --hits 400 --param 'ranking.rerankCount=0' --param 'ranking.globalPhase.rerankCount=0' --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label first_stage --block headline --out chapters/ch07/expected/test-first_stage.json > chapters/ch07/expected/test-first_stage.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking phased --mode rerank --passes 1 --hits 400 --param 'ranking.rerankCount=0' --param 'ranking.globalPhase.rerankCount=0' --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label first_stage --block headline --out chapters/ch07/expected/validation-first_stage-rerank.json > chapters/ch07/expected/validation-first_stage-rerank.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking phased --mode rerank --passes 1 --hits 400 --param 'ranking.rerankCount=0' --param 'ranking.globalPhase.rerankCount=0' --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label first_stage --block headline --out chapters/ch07/expected/test-first_stage-rerank.json > chapters/ch07/expected/test-first_stage-rerank.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking phased --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label phased --block headline --out chapters/ch07/expected/validation-phased.json > chapters/ch07/expected/validation-phased.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking phased --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label phased --block headline --out chapters/ch07/expected/test-phased.json > chapters/ch07/expected/test-phased.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking phased --mode rerank --passes 1 --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label phased --block headline --out chapters/ch07/expected/validation-phased-rerank.json > chapters/ch07/expected/validation-phased-rerank.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking phased --mode rerank --passes 1 --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label phased --block headline --out chapters/ch07/expected/test-phased-rerank.json > chapters/ch07/expected/test-phased-rerank.block.md
```

**What you should see:** in retrieval mode, NDCG@10 0.482 for the first stage and 0.502 for `phased` on validation; 0.489 and 0.499 on test. These agree with Chapter 6 within 0.0002. In rerank mode, 0.732 and 0.740 on validation; 0.723 and 0.728 on test. Rerank-mode scores are higher because only judged products are ranked.

**Gradient-boosted trees.** Train M1 and the three other M1 shapes from the train split:

```
.venv/bin/python chapters/ch07/train_ltr.py --split train --model second --leaves 3 --rounds 100 --out chapters/ch07/expected/train-second.json --model-out chapters/ch07/app/models/ltr_second.json --native-out chapters/ch07/models_native/ltr_second.lgb
.venv/bin/python chapters/ch07/train_ltr.py --split train --model second --grid --out chapters/ch07/expected/train-second-offline.json --model-out chapters/ch07/app/models/ltr_second_offline.json --native-out chapters/ch07/models_native/ltr_second_offline.lgb
.venv/bin/python chapters/ch07/train_ltr.py --split train --model second --leaves 3 --rounds 50 --out chapters/ch07/expected/train-second-tiny.json --model-out chapters/ch07/app/models/ltr_second_tiny.json
.venv/bin/python chapters/ch07/train_ltr.py --split train --model second --leaves 15 --rounds 200 --out chapters/ch07/expected/train-second-mid.json --model-out chapters/ch07/app/models/ltr_second_mid.json
```

| Option | What it does |
| :---- | :---- |
| `--model second` | Trains on the 51 features other than `cross_logit`. `--model global` trains on all 52. |
| `--leaves`, `--rounds` | The model's shape: leaves per tree and boosting rounds. |
| `--grid` | Tries 16 shapes (3, 7, 15 or 31 leaves × 100, 200, 300 or 800 rounds) and keeps the best by LightGBM's own NDCG@10 over the judged validation pairs: the offline pick. |
| `--model-out` | The JSON file a rank profile reads through `lightgbm(...)`. |
| `--native-out` | LightGBM's own save file of the same trees, which the export and parity tools read. |

Training takes about a minute in total. The 31 × 800 shape, `ltr_second_large.json`, is the book's own file, trained once and committed; no command here retrains it.

**Important: the training commands overwrite the deployed model files.** With the fixed seed and the same feature log, they reproduce the committed files byte for byte, and each training report records the file's sha256, so the container is already serving what you trained. If a sha256 in your `train-*.json` differs from the committed report, your log differs slightly, usually because your container has a different feeding history. In that case, run all six training commands (these four and the two in *A fully learned funnel*) and the two exports (in *Exporting to ONNX*) first, then `vespa deploy --wait 300 chapters/ch07/app` once, before any evaluation. Otherwise the engine scores the book's models and the parity check compares your files with them.

**Serving the model in a rank profile.** Nothing to run; `ltr_second.profile` is already deployed.

**Two ways to measure the same model.** M1 in retrieval mode and rerank mode, both splits:

```
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second --block headline --out chapters/ch07/expected/validation-ltr_second.json > chapters/ch07/expected/validation-ltr_second.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_second --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second --block headline --out chapters/ch07/expected/test-ltr_second.json > chapters/ch07/expected/test-ltr_second.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second --mode rerank --passes 1 --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second --block headline --out chapters/ch07/expected/validation-ltr_second-rerank.json > chapters/ch07/expected/validation-ltr_second-rerank.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_second --mode rerank --passes 1 --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second --block headline --out chapters/ch07/expected/test-ltr_second-rerank.json > chapters/ch07/expected/test-ltr_second-rerank.block.md
```

**What you should see:** NDCG@10 0.495 on validation and 0.494 on test in retrieval mode. Once the comparison tables are built, against the first stage: in rerank mode, +0.013 [+0.005, +0.021] on validation and +0.007 [+0.000, +0.014] on test; in retrieval mode, +0.013 [+0.005, +0.022] on validation and +0.004 [−0.003, +0.012] on test, an interval that includes zero. Recall@100 improves by +0.008 on validation and +0.007 on test.

### Choosing the model's shape where the task is measured

The other M1 shapes, validation only, in retrieval mode:

```
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second_tiny --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_tiny --block headline --out chapters/ch07/expected/validation-ltr_second_tiny.json > chapters/ch07/expected/validation-ltr_second_tiny.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second_offline --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_offline --block headline --out chapters/ch07/expected/validation-ltr_second_offline.json > chapters/ch07/expected/validation-ltr_second_offline.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second_mid --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_mid --block headline --out chapters/ch07/expected/validation-ltr_second_mid.json > chapters/ch07/expected/validation-ltr_second_mid.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second_large --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_large --block headline --out chapters/ch07/expected/validation-ltr_second_large.json > chapters/ch07/expected/validation-ltr_second_large.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second_offline --mode rerank --passes 1 --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_offline --block headline --out chapters/ch07/expected/validation-ltr_second_offline-rerank.json > chapters/ch07/expected/validation-ltr_second_offline-rerank.block.md
```

The offline grid and the feature-importance table, printed from the training reports without training anything:

```
.venv/bin/python chapters/ch07/train_ltr.py --from chapters/ch07/expected/train-second-offline.json --block grid > chapters/ch07/expected/train-second-grid.block.md
.venv/bin/python chapters/ch07/train_ltr.py --from chapters/ch07/expected/train-second.json --block importance > chapters/ch07/expected/train-second-importance.block.md
```

**What you should see:** offline, the grid picks 3 × 200 at 0.7479, and its scores span about two hundredths, down to 0.7261 for 31 × 800. In the engine, NDCG@10 is 0.492 for 3 × 50, 0.495 for 3 × 100, 0.490 for 3 × 200, 0.475 for 15 × 200 and 0.403 for 31 × 800. Once the comparison tables are built, only 3 × 50 and 3 × 100 beat the first stage with intervals above zero, and 31 × 800 is −0.079 [−0.092, −0.065]. Against 3 × 100, the smaller 3 × 50 is −0.003 [−0.007, +0.001] on NDCG@10 but −0.004 [−0.007, −0.001] on Recall@100.

**What the model reads.** In the importance table, `vector` has 3,463.1 of 7,773.9 total gain, `fieldMatch(title).completeness` 1,745.5 and `max_sim` 1,423.2. The last line collapses the 29 features the model never used. The chapter's percentages are these values divided by the total.

### A fully learned funnel

Train M2 and its runner-up shape:

```
.venv/bin/python chapters/ch07/train_ltr.py --split train --model global --grid --out chapters/ch07/expected/train-global.json --model-out chapters/ch07/app/models/ltr_global.json --native-out chapters/ch07/models_native/ltr_global.lgb
.venv/bin/python chapters/ch07/train_ltr.py --split train --model global --leaves 3 --rounds 200 --out chapters/ch07/expected/train-global-200.json --model-out chapters/ch07/app/models/ltr_global_200.json --native-out chapters/ch07/models_native/ltr_global_200.lgb
.venv/bin/python chapters/ch07/train_ltr.py --from chapters/ch07/expected/train-global.json --block grid > chapters/ch07/expected/train-global-grid.block.md
.venv/bin/python chapters/ch07/train_ltr.py --from chapters/ch07/expected/train-global.json --block importance > chapters/ch07/expected/train-global-importance.block.md
```

Here the offline grid's pick, 3 × 100, is the served model.

**A cost rule for model features.** As shipped, `ltr_global.profile` lists `ltr_score_global` among its match-features, so the evaluation and the parity check can read M2's score. That is the configuration every number in this chapter was measured with. A match-feature is computed for every hit the response returns, and `ltr_score_global` depends on `cross_logit`, so asking `ltr_global` for 400 hits would run the cross-encoder 400 times. Every `ltr_global` command below therefore uses `--hits 10`, the number its global phase reranks. The chapter shows a production version of the profile that leaves `ltr_score_global` out of the match-features; that version is not in this directory and was not measured.

`--hits 10` also sets the vector side's target to ten, and the reports print a dash for Recall@100, which ten hits cannot measure.

M2 on validation, both shapes, and the chosen shape on test. These took about 3 hours together:

```
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_global --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global --block headline --out chapters/ch07/expected/validation-ltr_global.json > chapters/ch07/expected/validation-ltr_global.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_global_200 --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global_200 --block headline --out chapters/ch07/expected/validation-ltr_global_200.json > chapters/ch07/expected/validation-ltr_global_200.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_global --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global --block headline --out chapters/ch07/expected/test-ltr_global.json > chapters/ch07/expected/test-ltr_global.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_global --mode rerank --passes 1 --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global --block headline --out chapters/ch07/expected/test-ltr_global-rerank.json > chapters/ch07/expected/test-ltr_global-rerank.block.md
```

M2 in rerank mode on validation, both shapes. Allow about 45 minutes each:

```
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_global --mode rerank --passes 1 --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global --block headline --out chapters/ch07/expected/validation-ltr_global-rerank.json > chapters/ch07/expected/validation-ltr_global-rerank.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_global_200 --mode rerank --passes 1 --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global_200 --block headline --out chapters/ch07/expected/validation-ltr_global_200-rerank.json > chapters/ch07/expected/validation-ltr_global_200-rerank.block.md
```

**What you should see:** NDCG@10 0.510 on validation and 0.504 on test. Once the comparison tables are built: against the first stage, +0.028 [+0.019, +0.038] on validation and +0.014 [+0.006, +0.022] on test; against `phased`, +0.008 [−0.001, +0.016] and +0.004 [−0.002, +0.011], intervals that include zero; in rerank mode against `phased` on validation, +0.015 [+0.008, +0.022]. The two M2 shapes cannot be told apart, −0.001 [−0.003, +0.002], so the smaller stays.

**What the global model reads.** In `train-global-importance.block.md`, `cross_logit` has 4,702.6 of 8,239.2 total gain and `vector` 2,157.1; `max_sim` is among the 30 features M2 never uses.

### Exporting to ONNX and checking parity

**Two files from one model.** Convert both chosen shapes to ONNX:

```
.venv/bin/python chapters/ch07/export_onnx.py --model chapters/ch07/models_native/ltr_second.lgb --out chapters/ch07/app/models/onnx/ltr_second.onnx --out-report chapters/ch07/expected/export-second.json
.venv/bin/python chapters/ch07/export_onnx.py --model chapters/ch07/models_native/ltr_global.lgb --out chapters/ch07/app/models/onnx/ltr_global.onnx --out-report chapters/ch07/expected/export-global.json
```

Each export also scores every validation row with LightGBM and with `onnxruntime` and records the difference.

**What you should see:** `max_abs_diff` of 5.06e-07 for M1 and 4.84e-07 for M2 in the two reports, and `rows_beyond_tolerance` of 0.

**Invoking an ONNX model from a rank profile.** The schema declarations are in `app/schemas/product.sd`; the profiles are `ltr_second_onnx.profile` and `ltr_global_onnx.profile`. The long `ltr_input` function in each profile was generated, not typed: `export_onnx.py --model <file> --profile-snippet` prints it from the model's own feature list. If you retrain on a log with different columns, regenerate it this way.

The ONNX profiles, evaluated the same way as their native siblings. The three `ltr_global_onnx` rows took about 2 hours 20 minutes; the validation rerank-mode row adds about 45 minutes:

```
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second_onnx --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_onnx --block headline --out chapters/ch07/expected/validation-ltr_second_onnx.json > chapters/ch07/expected/validation-ltr_second_onnx.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_second_onnx --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_onnx --block headline --out chapters/ch07/expected/test-ltr_second_onnx.json > chapters/ch07/expected/test-ltr_second_onnx.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_second_onnx --mode rerank --passes 1 --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_onnx --block headline --out chapters/ch07/expected/validation-ltr_second_onnx-rerank.json > chapters/ch07/expected/validation-ltr_second_onnx-rerank.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_second_onnx --mode rerank --passes 1 --hits 400 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_second_onnx --block headline --out chapters/ch07/expected/test-ltr_second_onnx-rerank.json > chapters/ch07/expected/test-ltr_second_onnx-rerank.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_global_onnx --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global_onnx --block headline --out chapters/ch07/expected/validation-ltr_global_onnx.json > chapters/ch07/expected/validation-ltr_global_onnx.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_global_onnx --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global_onnx --block headline --out chapters/ch07/expected/test-ltr_global_onnx.json > chapters/ch07/expected/test-ltr_global_onnx.block.md
.venv/bin/python shared/tools/evaluate.py --split test --retriever hybrid --ranking ltr_global_onnx --mode rerank --passes 1 --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global_onnx --block headline --out chapters/ch07/expected/test-ltr_global_onnx-rerank.json > chapters/ch07/expected/test-ltr_global_onnx-rerank.block.md
.venv/bin/python shared/tools/evaluate.py --split validation --retriever hybrid --ranking ltr_global_onnx --mode rerank --passes 1 --hits 10 --reranker-input qt=colbert --reranker-input qt_cross=tokenizer --label ltr_global_onnx --block headline --out chapters/ch07/expected/validation-ltr_global_onnx-rerank.json > chapters/ch07/expected/validation-ltr_global_onnx-rerank.block.md
```

**What you should see:** the same NDCG@10 as the native profiles, 0.495 and 0.510 on validation, 0.494 and 0.504 on test.

**Parity: is the engine scoring the file we trained?** One check per profile, over all 14,926 validation pairs. The two M1 checks take about 2 minutes; the three M2 checks about an hour, because each pair runs the cross-encoder:

```
.venv/bin/python chapters/ch07/test_model_parity.py --split validation --profile ltr_second --model chapters/ch07/models_native/ltr_second.lgb --check-shape --out chapters/ch07/expected/parity-validation-ltr_second.json --block parity > chapters/ch07/expected/parity-validation-ltr_second.block.md
.venv/bin/python chapters/ch07/test_model_parity.py --split validation --profile ltr_second_onnx --model chapters/ch07/models_native/ltr_second.lgb --onnx chapters/ch07/app/models/onnx/ltr_second.onnx --check-shape --out chapters/ch07/expected/parity-validation-ltr_second_onnx.json --block parity > chapters/ch07/expected/parity-validation-ltr_second_onnx.block.md
.venv/bin/python chapters/ch07/test_model_parity.py --split validation --profile ltr_global --model chapters/ch07/models_native/ltr_global.lgb --check-shape --out chapters/ch07/expected/parity-validation-ltr_global.json --block parity > chapters/ch07/expected/parity-validation-ltr_global.block.md
.venv/bin/python chapters/ch07/test_model_parity.py --split validation --profile ltr_global_200 --model chapters/ch07/models_native/ltr_global_200.lgb --check-shape --out chapters/ch07/expected/parity-validation-ltr_global_200.json --block parity > chapters/ch07/expected/parity-validation-ltr_global_200.block.md
.venv/bin/python chapters/ch07/test_model_parity.py --split validation --profile ltr_global_onnx --model chapters/ch07/models_native/ltr_global.lgb --onnx chapters/ch07/app/models/onnx/ltr_global.onnx --check-shape --out chapters/ch07/expected/parity-validation-ltr_global_onnx.json --block parity > chapters/ch07/expected/parity-validation-ltr_global_onnx.block.md
```

`--check-shape` compares the model's feature names with the logged columns, in order, before any query runs, and stops if they differ. `--onnx` scores with `onnxruntime` on the ONNX file instead of LightGBM. The tool reports how many pairs differ beyond 0.001 but does not fail on them; read the `count beyond tolerance` rows.

**What you should see:** 14,926 pairs compared in every report, `shape check PASS`, and 0 pairs beyond tolerance. The largest difference is 0 for `ltr_second`, `ltr_global` and `ltr_global_200`, 9.53674e-07 for `ltr_second_onnx`, and 1.19209e-06 for `ltr_global_onnx`.

### Building the comparison tables

Every report now exists. These commands read them and query nothing:

```
.venv/bin/python shared/tools/compare.py --block evaluations --out chapters/ch07/expected/compare-validation-evaluations.json chapters/ch07/expected/validation-first_stage.json chapters/ch07/expected/validation-ltr_second_tiny.json chapters/ch07/expected/validation-ltr_second.json chapters/ch07/expected/validation-ltr_second_offline.json chapters/ch07/expected/validation-ltr_second_mid.json chapters/ch07/expected/validation-ltr_second_large.json chapters/ch07/expected/validation-ltr_second_onnx.json chapters/ch07/expected/validation-phased.json chapters/ch07/expected/validation-ltr_global.json chapters/ch07/expected/validation-ltr_global_200.json chapters/ch07/expected/validation-ltr_global_onnx.json > chapters/ch07/expected/compare-validation-evaluations.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline first_stage --out chapters/ch07/expected/compare-validation-vs-first-stage.json chapters/ch07/expected/validation-first_stage.json chapters/ch07/expected/validation-ltr_second_tiny.json chapters/ch07/expected/validation-ltr_second.json chapters/ch07/expected/validation-ltr_second_offline.json chapters/ch07/expected/validation-ltr_second_mid.json chapters/ch07/expected/validation-ltr_second_large.json chapters/ch07/expected/validation-ltr_second_onnx.json chapters/ch07/expected/validation-phased.json chapters/ch07/expected/validation-ltr_global.json chapters/ch07/expected/validation-ltr_global_200.json chapters/ch07/expected/validation-ltr_global_onnx.json > chapters/ch07/expected/compare-validation-vs-first-stage.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline first_stage --out chapters/ch07/expected/compare-test-vs-first-stage.json chapters/ch07/expected/test-first_stage.json chapters/ch07/expected/test-ltr_second.json chapters/ch07/expected/test-ltr_second_onnx.json chapters/ch07/expected/test-phased.json chapters/ch07/expected/test-ltr_global.json chapters/ch07/expected/test-ltr_global_onnx.json > chapters/ch07/expected/compare-test-vs-first-stage.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline first_stage --out chapters/ch07/expected/compare-validation-rerank-vs-first-stage.json chapters/ch07/expected/validation-first_stage-rerank.json chapters/ch07/expected/validation-ltr_second-rerank.json chapters/ch07/expected/validation-ltr_second_onnx-rerank.json chapters/ch07/expected/validation-ltr_second_offline-rerank.json chapters/ch07/expected/validation-ltr_global-rerank.json chapters/ch07/expected/validation-ltr_global_200-rerank.json chapters/ch07/expected/validation-ltr_global_onnx-rerank.json > chapters/ch07/expected/compare-validation-rerank-vs-first-stage.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline first_stage --out chapters/ch07/expected/compare-test-rerank-vs-first-stage.json chapters/ch07/expected/test-first_stage-rerank.json chapters/ch07/expected/test-ltr_second-rerank.json chapters/ch07/expected/test-ltr_second_onnx-rerank.json chapters/ch07/expected/test-ltr_global-rerank.json chapters/ch07/expected/test-ltr_global_onnx-rerank.json > chapters/ch07/expected/compare-test-rerank-vs-first-stage.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_second --out chapters/ch07/expected/compare-validation-second-vs-tiny.json chapters/ch07/expected/validation-ltr_second.json chapters/ch07/expected/validation-ltr_second_tiny.json > chapters/ch07/expected/compare-validation-second-vs-tiny.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline phased --out chapters/ch07/expected/compare-validation-vs-phased.json chapters/ch07/expected/validation-phased.json chapters/ch07/expected/validation-ltr_second.json chapters/ch07/expected/validation-ltr_global.json chapters/ch07/expected/validation-ltr_global_onnx.json > chapters/ch07/expected/compare-validation-vs-phased.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline phased --out chapters/ch07/expected/compare-test-vs-phased.json chapters/ch07/expected/test-phased.json chapters/ch07/expected/test-ltr_second.json chapters/ch07/expected/test-ltr_global.json chapters/ch07/expected/test-ltr_global_onnx.json > chapters/ch07/expected/compare-test-vs-phased.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline phased --out chapters/ch07/expected/compare-validation-rerank-vs-phased.json chapters/ch07/expected/validation-phased-rerank.json chapters/ch07/expected/validation-ltr_global-rerank.json chapters/ch07/expected/validation-ltr_global_200-rerank.json chapters/ch07/expected/validation-ltr_global_onnx-rerank.json > chapters/ch07/expected/compare-validation-rerank-vs-phased.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline phased --out chapters/ch07/expected/compare-validation-global-shapes.json chapters/ch07/expected/validation-phased.json chapters/ch07/expected/validation-ltr_global.json chapters/ch07/expected/validation-ltr_global_200.json > chapters/ch07/expected/compare-validation-global-shapes.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_global --out chapters/ch07/expected/compare-validation-global-tiebreak.json chapters/ch07/expected/validation-ltr_global.json chapters/ch07/expected/validation-ltr_global_200.json > chapters/ch07/expected/compare-validation-global-tiebreak.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_second --out chapters/ch07/expected/compare-validation-global-vs-second.json chapters/ch07/expected/validation-ltr_second.json chapters/ch07/expected/validation-ltr_global.json > chapters/ch07/expected/compare-validation-global-vs-second.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_second --out chapters/ch07/expected/compare-validation-native-vs-onnx.json chapters/ch07/expected/validation-ltr_second.json chapters/ch07/expected/validation-ltr_second_onnx.json > chapters/ch07/expected/compare-validation-native-vs-onnx.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_second --out chapters/ch07/expected/compare-test-native-vs-onnx.json chapters/ch07/expected/test-ltr_second.json chapters/ch07/expected/test-ltr_second_onnx.json > chapters/ch07/expected/compare-test-native-vs-onnx.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_global --out chapters/ch07/expected/compare-validation-global-native-vs-onnx.json chapters/ch07/expected/validation-ltr_global.json chapters/ch07/expected/validation-ltr_global_onnx.json > chapters/ch07/expected/compare-validation-global-native-vs-onnx.block.md
.venv/bin/python shared/tools/compare.py --block comparison --baseline ltr_global --out chapters/ch07/expected/compare-test-global-native-vs-onnx.json chapters/ch07/expected/test-ltr_global.json chapters/ch07/expected/test-ltr_global_onnx.json > chapters/ch07/expected/compare-test-global-native-vs-onnx.block.md
```

`--block evaluations` prints the table of scores; `--block comparison` prints each profile's change against the `--baseline` run, with a 95% interval, labelled **real** when the interval excludes zero and **inside the noise** when it does not. Rows for `ltr_global*` print a dash for Recall@100.

**What you should see:** the numbers quoted under each section above. The native-against-ONNX comparisons read +0.000 [+0.000, +0.000] on both splits: every query gets the same NDCG@10 from both versions.

### Versioning, monitoring, and rollback

The worked query under three profiles, showing the tie the chapter describes:

```
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking ltr_second --param 'input.query(qt)=embed(colbert, "running shoes")' --param 'input.query(qt_cross)=embed(tokenizer, "running shoes")' --param 'timeout=10s' --hits 10 --block features > chapters/ch07/expected/features-running-shoes-ltr_second.block.md
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking ltr_second_large --param 'input.query(qt)=embed(colbert, "running shoes")' --param 'input.query(qt_cross)=embed(tokenizer, "running shoes")' --param 'timeout=10s' --hits 10 --block features > chapters/ch07/expected/features-running-shoes-ltr_second_large.block.md
.venv/bin/python shared/tools/query.py --query "running shoes" --retriever hybrid --ranking ltr_global --param 'input.query(qt)=embed(colbert, "running shoes")' --param 'input.query(qt_cross)=embed(tokenizer, "running shoes")' --param 'timeout=10s' --hits 10 --block features > chapters/ch07/expected/features-running-shoes-ltr_global.block.md
```

**What you should see:** under `ltr_second`, ranks 3 and 4 both score 1.546, the same *Mens Running Shoes Non Slip Athletic Walking Blade Type Sneakers* listed in black and in white. Under `ltr_second_large` every hit has a different score. Under `ltr_global` the two still tie, at 1.282, in the `ltr_score_global` column. The order between tied hits is not guaranteed, so yours may print them the other way round.

Versioning and rollback are configuration, not commands: each model is a file under `app/models/`, each training report records its sha256, and a request chooses between served models with `ranking.profile`.

### Distributed model evaluation and external inference

**Evaluating models across content nodes.** Nothing to run. This book uses one content node.

**The same model behind an external service.** M1 scored in the engine and by a small HTTP service on your machine that loads the same model file. About 22 minutes:

```
.venv/bin/python chapters/ch07/benchmark_inference.py --split validation --model chapters/ch07/models_native/ltr_second.lgb --candidates 10,25,100 --passes 3 --out chapters/ch07/expected/benchmark-inference.json --block benchmark > chapters/ch07/expected/benchmark-inference.block.md
```

The tool starts the service itself. For each candidate count it times three paths: the in-engine request (`ltr_second`, second phase reranking N), the fetch of N candidates' 51 features through the `features_second` profile, and the round trip that ships those features as JSON and returns scores.

**What you should see:** in-engine p50 of 68.8, 69.7 and 73.2 ms at 10, 25 and 100 candidates; external totals of 73.9, 74.9 and 79.7 ms; ship-and-score medians of 2.0 to 2.7 ms; payloads of about 6.3, 15.6 and 61.3 KB. The in-engine timings here are for N returned hits, so they are not the same measurement as the 400-hit latency table below.

**What the placements cost in the engine.** The latency table, from the validation reports above:

```
.venv/bin/python shared/tools/compare.py --block evaluations-latency --out chapters/ch07/expected/compare-validation-latency.json chapters/ch07/expected/validation-first_stage.json chapters/ch07/expected/validation-ltr_second_tiny.json chapters/ch07/expected/validation-ltr_second.json chapters/ch07/expected/validation-ltr_second_offline.json chapters/ch07/expected/validation-ltr_second_mid.json chapters/ch07/expected/validation-ltr_second_large.json chapters/ch07/expected/validation-ltr_second_onnx.json chapters/ch07/expected/validation-phased.json chapters/ch07/expected/validation-ltr_global.json chapters/ch07/expected/validation-ltr_global_200.json chapters/ch07/expected/validation-ltr_global_onnx.json > chapters/ch07/expected/compare-validation-latency.block.md
```

**What you should see:** p50 of 115.9 ms for the first stage, 91.3 ms for `ltr_second`, 96.0 ms for `ltr_second_large`, 947.3 ms for `phased` and 913.5 ms for `ltr_global`, on the reference machine. The `ltr_global*` rows return 10 hits and every other row 400. Vespa's own reported search time, which leaves out the response, is in `latency_ms_vespa_reported` in each report: 19 ms for the first stage and 22 ms for `ltr_second`.

**Memory.** At least twenty minutes. For a reading comparable with the book's, run it straight after the bootstrap and the feature log, before the evaluations:

```
.venv/bin/python shared/tools/memory.py --settle 600 --rounds 3 --tolerance 0.01 --out chapters/ch07/expected/memory.json
.venv/bin/python shared/tools/memory.py --from chapters/ch07/expected/memory.json > chapters/ch07/expected/memory.block.md
```

**What you should see:** about 1,848 MB on the book's container. As in Chapter 6, the reading depends on the container's history. Check that the report says `settled: true`.

## Comparing your run with the book's

`expected/` holds the output of every command above, exactly as it ran when the book was written. Five kinds of number are in there, and they behave differently:

- **Training numbers** — the offline grid, the feature importance and the model files' sha256. With the same feature log they reproduce exactly. A log from a container with a different feeding history can shift the BM25-based features by a few hundredths, and then the trees, the checksums and the importance values change too.
- **Quality numbers** — NDCG@10, recall and MRR for every profile and comparison. These should come back within a few thousandths, and no interval's label should change, with one caveat: M1's rerank-mode gain on test, +0.007 [+0.000, +0.014], has a lower end of +0.0005, so a rerun can move it either side of zero.
- **Parity numbers** — the differences between the engine and the trained files. These are properties of the files and should come back at the same tiny values, or exactly zero for the native profiles, whatever your machine.
- **The worked query** — `lexical` and the model scores can move slightly with feeding history; tied hits may print in either order.
- **Cost numbers** — bootstrap timings, latency, the external benchmark and memory. These describe one machine on one day (an Apple M4 Pro, Docker with 4 CPUs / 10 GB), one query at a time, after a discarded warm-up pass. Yours will differ, and that is expected.

After a run, `git diff chapters/ch07/expected/` shows every difference.

## If something goes wrong

**A sha256 in a training report differs from the book's** — your feature log differs slightly, usually because of your container's feeding history. Run all six training commands and both exports, then `vespa deploy --wait 300 chapters/ch07/app`, before any evaluation, so the engine serves the models you trained.

**`train_ltr.py` cannot find the feature log** — the CSV files are not in the repository. Run the three `features_log.py` commands first.

**The parity check reports pairs beyond tolerance** — the engine is not scoring the file you checked against. The most common cause is training new files without redeploying. If `shape check` fails instead, the model's feature list does not match the log's columns; retrain from the current log.

**A hand-typed `curl` against an `ltr_global*` profile returns `"Timed out"`** — the cross-encoder needs more than Vespa's default timeout. The tools send a 30-second timeout; add `&timeout=10s` or more to a raw request.

**An `ltr_global*` request is very slow** — check how many hits it asks for. As shipped, M2's score is a match-feature, so it is computed, with the cross-encoder, for every returned hit. Ask for 10.

**A request that leaves out `input.query(qt_cross)` still returns results** — with this application's query-tensor configuration, the cross-encoder then scores against an empty query, and nothing reports an error. `features_log.py` refuses such requests; a hand-typed request is not refused. Always send both query inputs.

**`ImportError` for `lightgbm` or `onnxmltools`** — the `ml` requirements group is not installed. Run `./bootstrap.sh ch07` again.

**The memory reading is higher than the book's** — the container has a longer history. If the report says `settled: false`, run it again when nothing else is querying the container.

**The deploy or feed fails, or Vespa stops responding partway** — check that Docker really has 4 CPUs and 10 GB. Every run behind the book used exactly that, so too little memory is the first thing to rule out.

**The container fails to start because a port is already allocated** — something else on your machine is using port 8080 or 19071. Stop it, or stop the other Vespa container, then rerun with `--fresh`.

## Next

When you are ready for Chapter 8:

```
./bootstrap.sh ch08
```

It adds one attribute, `tenant_id`, filled by a partial update rather than a full feed. Chapter 8 turns from deciding which products matter most to deciding which products a request is allowed to see at all.
