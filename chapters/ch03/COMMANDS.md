# ch03 COMMANDS

One line per command exactly as run, one line per file it wrote.

> 2026-09-15: the six `bm25_tuned` runs with `--param` were first run with bare keys (`--param w_qcomplete=0`), which Vespa ignores silently; they were re-run with the `input.query(...)` form shown here and the files overwritten, then the compare blocks that read them (validation evaluations, latency, comparison, boosts; test evaluations, comparison) were re-rendered with the commands below verbatim.

```
./bootstrap.sh ch03
```
wrote nothing (state check only; bootstrap re-applies the same application package every time — idempotent, a few seconds, not a second app — and the container already held 101341 documents, so nothing was fed)

```
.venv/bin/python shared/tools/feed.py builds/esci-us-hard-book-s42-kdd-v4/products.jsonl --out chapters/ch03/expected/feed.json --label "ch03 full feed (re-feed onto the populated index)" > chapters/ch03/expected/feed.block.md
```
wrote `chapters/ch03/expected/feed.json`, `chapters/ch03/expected/feed.block.md` (101,341 ok, 0 failed, 0 retried, 234.2s, 433 docs/s)

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_title --label validation-bm25_title --out chapters/ch03/expected/validation-bm25_title.json 
```
wrote `chapters/ch03/expected/validation-bm25_title.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 1 --ranking random --label validation-random --out chapters/ch03/expected/validation-random.json 
```
wrote `chapters/ch03/expected/validation-random.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking default --label validation-default --out chapters/ch03/expected/validation-default.json 
```
wrote `chapters/ch03/expected/validation-default.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_all --label validation-bm25_all --out chapters/ch03/expected/validation-bm25_all.json 
```
wrote `chapters/ch03/expected/validation-bm25_all.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_weighted --label validation-bm25_weighted --out chapters/ch03/expected/validation-bm25_weighted.json 
```
wrote `chapters/ch03/expected/validation-bm25_weighted.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --label validation-bm25_tuned --out chapters/ch03/expected/validation-bm25_tuned.json 
```
wrote `chapters/ch03/expected/validation-bm25_tuned.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=0' --param 'input.query(w_brand)=0' --label validation-bm25_tuned-k1only --out chapters/ch03/expected/validation-bm25_tuned-k1only.json 
```
wrote `chapters/ch03/expected/validation-bm25_tuned-k1only.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=3' --param 'input.query(w_brand)=0' --label validation-bm25_tuned-qc3 --out chapters/ch03/expected/validation-bm25_tuned-qc3.json 
```
wrote `chapters/ch03/expected/validation-bm25_tuned-qc3.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=5' --param 'input.query(w_brand)=0' --label validation-bm25_tuned-qc5 --out chapters/ch03/expected/validation-bm25_tuned-qc5.json 
```
wrote `chapters/ch03/expected/validation-bm25_tuned-qc5.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=10' --param 'input.query(w_brand)=0' --label validation-bm25_tuned-qc10 --out chapters/ch03/expected/validation-bm25_tuned-qc10.json 
```
wrote `chapters/ch03/expected/validation-bm25_tuned-qc10.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=5' --param 'input.query(w_brand)=3' --label validation-bm25_tuned-qc5-brand3 --out chapters/ch03/expected/validation-bm25_tuned-qc5-brand3.json 
```
wrote `chapters/ch03/expected/validation-bm25_tuned-qc5-brand3.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_k06_b04 --label validation-bm25_k06_b04 --out chapters/ch03/expected/validation-bm25_k06_b04.json 
```
wrote `chapters/ch03/expected/validation-bm25_k06_b04.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_k06_b075 --label validation-bm25_k06_b075 --out chapters/ch03/expected/validation-bm25_k06_b075.json 
```
wrote `chapters/ch03/expected/validation-bm25_k06_b075.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_k06_b10 --label validation-bm25_k06_b10 --out chapters/ch03/expected/validation-bm25_k06_b10.json 
```
wrote `chapters/ch03/expected/validation-bm25_k06_b10.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_k09_b04 --label validation-bm25_k09_b04 --out chapters/ch03/expected/validation-bm25_k09_b04.json 
```
wrote `chapters/ch03/expected/validation-bm25_k09_b04.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_k09_b075 --label validation-bm25_k09_b075 --out chapters/ch03/expected/validation-bm25_k09_b075.json 
```
wrote `chapters/ch03/expected/validation-bm25_k09_b075.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_k09_b10 --label validation-bm25_k09_b10 --out chapters/ch03/expected/validation-bm25_k09_b10.json 
```
wrote `chapters/ch03/expected/validation-bm25_k09_b10.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_k12_b04 --label validation-bm25_k12_b04 --out chapters/ch03/expected/validation-bm25_k12_b04.json 
```
wrote `chapters/ch03/expected/validation-bm25_k12_b04.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_k12_b075 --label validation-bm25_k12_b075 --out chapters/ch03/expected/validation-bm25_k12_b075.json 
```
wrote `chapters/ch03/expected/validation-bm25_k12_b075.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_k12_b10 --label validation-bm25_k12_b10 --out chapters/ch03/expected/validation-bm25_k12_b10.json 
```
wrote `chapters/ch03/expected/validation-bm25_k12_b10.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_k15_b04 --label validation-bm25_k15_b04 --out chapters/ch03/expected/validation-bm25_k15_b04.json 
```
wrote `chapters/ch03/expected/validation-bm25_k15_b04.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_k15_b075 --label validation-bm25_k15_b075 --out chapters/ch03/expected/validation-bm25_k15_b075.json 
```
wrote `chapters/ch03/expected/validation-bm25_k15_b075.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_k15_b10 --label validation-bm25_k15_b10 --out chapters/ch03/expected/validation-bm25_k15_b10.json 
```
wrote `chapters/ch03/expected/validation-bm25_k15_b10.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_k20_b04 --label validation-bm25_k20_b04 --out chapters/ch03/expected/validation-bm25_k20_b04.json 
```
wrote `chapters/ch03/expected/validation-bm25_k20_b04.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_k20_b075 --label validation-bm25_k20_b075 --out chapters/ch03/expected/validation-bm25_k20_b075.json 
```
wrote `chapters/ch03/expected/validation-bm25_k20_b075.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_k20_b10 --label validation-bm25_k20_b10 --out chapters/ch03/expected/validation-bm25_k20_b10.json 
```
wrote `chapters/ch03/expected/validation-bm25_k20_b10.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_title --label validation-bm25_title-tail --out chapters/ch03/expected/validation-bm25_title-tail.json 
```
wrote `chapters/ch03/expected/validation-bm25_title-tail.json`

## Test-split runs

```
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking bm25_title --label test-bm25_title --out chapters/ch03/expected/test-bm25_title.json
```
wrote `chapters/ch03/expected/test-bm25_title.json`

```
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 1 --ranking random --label test-random --out chapters/ch03/expected/test-random.json
```
wrote `chapters/ch03/expected/test-random.json`

```
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking default --label test-default --out chapters/ch03/expected/test-default.json
```
wrote `chapters/ch03/expected/test-default.json`

```
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking bm25_weighted --label test-bm25_weighted --out chapters/ch03/expected/test-bm25_weighted.json
```
wrote `chapters/ch03/expected/test-bm25_weighted.json`

```
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking bm25_tuned --param 'input.query(w_qcomplete)=0' --param 'input.query(w_brand)=0' --label test-bm25_tuned-k1only --out chapters/ch03/expected/test-bm25_tuned-k1only.json
```
wrote `chapters/ch03/expected/test-bm25_tuned-k1only.json` — re-run 2026-09-15 with the `input.query(...)` form (see the note at the top).

```
.venv/bin/python shared/tools/evaluate.py --split test --hits 100 --passes 3 --ranking bm25_tuned --label test-bm25_tuned --out chapters/ch03/expected/test-bm25_tuned.json
```
wrote `chapters/ch03/expected/test-bm25_tuned.json`

## compare.py blocks

Note on labels: every `evaluate.py` run above was given `--label <split>-<name>`, so each report's own `label` field already carries the `validation-`/`test-` prefix. `compare.py` prints rows keyed by that stored `label` (not by a `--label` rename), so no `compare.py --label` renames were used anywhere below — the row names shown are exactly the reports' own labels, unchanged.

```
.venv/bin/python chapters/ch03/compare.py --block evaluations chapters/ch03/expected/validation-random.json chapters/ch03/expected/validation-default.json chapters/ch03/expected/validation-bm25_title.json chapters/ch03/expected/validation-bm25_all.json chapters/ch03/expected/validation-bm25_weighted.json chapters/ch03/expected/validation-bm25_tuned-k1only.json chapters/ch03/expected/validation-bm25_tuned.json > chapters/ch03/expected/compare-validation-evaluations.block.md
```
wrote `chapters/ch03/expected/compare-validation-evaluations.block.md`

```
.venv/bin/python chapters/ch03/compare.py --block evaluations-latency chapters/ch03/expected/validation-default.json chapters/ch03/expected/validation-bm25_title.json chapters/ch03/expected/validation-bm25_all.json chapters/ch03/expected/validation-bm25_weighted.json chapters/ch03/expected/validation-bm25_tuned-k1only.json chapters/ch03/expected/validation-bm25_tuned.json > chapters/ch03/expected/compare-validation-latency.block.md
```
wrote `chapters/ch03/expected/compare-validation-latency.block.md`

```
.venv/bin/python chapters/ch03/compare.py --block comparison --baseline validation-bm25_title chapters/ch03/expected/validation-bm25_title.json chapters/ch03/expected/validation-default.json chapters/ch03/expected/validation-bm25_all.json chapters/ch03/expected/validation-bm25_weighted.json chapters/ch03/expected/validation-bm25_tuned-k1only.json chapters/ch03/expected/validation-bm25_tuned.json chapters/ch03/expected/validation-bm25_title-tail.json > chapters/ch03/expected/compare-validation-comparison.block.md
```
wrote `chapters/ch03/expected/compare-validation-comparison.block.md` (baseline report included among the positional `reports`, required by the tool)

```
.venv/bin/python chapters/ch03/compare.py --block comparison --baseline validation-bm25_tuned-k1only chapters/ch03/expected/validation-bm25_tuned-k1only.json chapters/ch03/expected/validation-bm25_tuned-qc3.json chapters/ch03/expected/validation-bm25_tuned-qc5.json chapters/ch03/expected/validation-bm25_tuned-qc10.json chapters/ch03/expected/validation-bm25_tuned-qc5-brand3.json chapters/ch03/expected/validation-bm25_tuned.json > chapters/ch03/expected/compare-validation-boosts.block.md
```
wrote `chapters/ch03/expected/compare-validation-boosts.block.md` — re-rendered after the re-run described in the note at the top; its first rendering, from the bare-key reports, read `+0.000 ... inside the noise` on every row because those reports were byte-identical

```
.venv/bin/python chapters/ch03/compare.py --block grid chapters/ch03/expected/validation-bm25_k06_b04.json chapters/ch03/expected/validation-bm25_k06_b075.json chapters/ch03/expected/validation-bm25_k06_b10.json chapters/ch03/expected/validation-bm25_k09_b04.json chapters/ch03/expected/validation-bm25_k09_b075.json chapters/ch03/expected/validation-bm25_k09_b10.json chapters/ch03/expected/validation-bm25_k12_b04.json chapters/ch03/expected/validation-bm25_k12_b075.json chapters/ch03/expected/validation-bm25_k12_b10.json chapters/ch03/expected/validation-bm25_k15_b04.json chapters/ch03/expected/validation-bm25_k15_b075.json chapters/ch03/expected/validation-bm25_k15_b10.json chapters/ch03/expected/validation-bm25_k20_b04.json chapters/ch03/expected/validation-bm25_k20_b075.json chapters/ch03/expected/validation-bm25_k20_b10.json > chapters/ch03/expected/compare-validation-grid.block.md
```
wrote `chapters/ch03/expected/compare-validation-grid.block.md`

```
.venv/bin/python chapters/ch03/compare.py --block headline --headline validation-bm25_tuned --baseline validation-random chapters/ch03/expected/validation-random.json chapters/ch03/expected/validation-bm25_tuned.json > chapters/ch03/expected/compare-validation-headline.block.md
```
wrote `chapters/ch03/expected/compare-validation-headline.block.md`

```
.venv/bin/python chapters/ch03/compare.py --block evaluations chapters/ch03/expected/test-random.json chapters/ch03/expected/test-default.json chapters/ch03/expected/test-bm25_title.json chapters/ch03/expected/test-bm25_weighted.json chapters/ch03/expected/test-bm25_tuned-k1only.json chapters/ch03/expected/test-bm25_tuned.json > chapters/ch03/expected/compare-test-evaluations.block.md
```
wrote `chapters/ch03/expected/compare-test-evaluations.block.md`

```
.venv/bin/python chapters/ch03/compare.py --block comparison --baseline test-bm25_title chapters/ch03/expected/test-bm25_title.json chapters/ch03/expected/test-default.json chapters/ch03/expected/test-bm25_weighted.json chapters/ch03/expected/test-bm25_tuned-k1only.json chapters/ch03/expected/test-bm25_tuned.json > chapters/ch03/expected/compare-test-comparison.block.md
```
wrote `chapters/ch03/expected/compare-test-comparison.block.md`

## Blind spot (vocabulary_mismatch.py)

```
.venv/bin/python chapters/ch03/vocabulary_mismatch.py --split validation --ranking bm25_tuned --out chapters/ch03/expected/vocabulary-validation.json > chapters/ch03/expected/vocabulary-validation.block.md
```
wrote `chapters/ch03/expected/vocabulary-validation.json`, `chapters/ch03/expected/vocabulary-validation.block.md` (no `--block` flag exists on this tool; the five-line block is the tool's plain stdout, per its own `--help`/docstring)

```
.venv/bin/python chapters/ch03/vocabulary_mismatch.py --split test --ranking bm25_tuned --out chapters/ch03/expected/vocabulary-test.json > chapters/ch03/expected/vocabulary-test.block.md
```
wrote `chapters/ch03/expected/vocabulary-test.json`, `chapters/ch03/expected/vocabulary-test.block.md`

## Query blocks

```
.venv/bin/python shared/tools/query.py --query "running shoes" --ranking bm25_tuned --hits 5 --block query > chapters/ch03/expected/query-101341.block.md
```
wrote `chapters/ch03/expected/query-101341.block.md`

```
.venv/bin/python shared/tools/query.py --query "running shoes" --ranking explained --hits 5 --block features > chapters/ch03/expected/features-running-shoes.block.md
```
wrote `chapters/ch03/expected/features-running-shoes.block.md`

## The boost's own bracket on test

```
.venv/bin/python chapters/ch03/compare.py --block comparison --baseline test-bm25_tuned-k1only chapters/ch03/expected/test-bm25_tuned-k1only.json chapters/ch03/expected/test-bm25_tuned.json > chapters/ch03/expected/compare-test-boost.block.md
```
wrote `chapters/ch03/expected/compare-test-boost.block.md`

## The one-field-at-a-time sweep: bm25_weighted query-time weights, one field at a time

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_weighted --param 'input.query(w_title)=1' --param 'input.query(w_bullets)=0' --param 'input.query(w_description)=0.5' --param 'input.query(w_brand)=0' --label validation-bm25_weighted-t1-d05 --out chapters/ch03/expected/validation-bm25_weighted-t1-d05.json
```
wrote `chapters/ch03/expected/validation-bm25_weighted-t1-d05.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_weighted --param 'input.query(w_title)=1' --param 'input.query(w_bullets)=0.5' --param 'input.query(w_description)=0' --param 'input.query(w_brand)=0' --label validation-bm25_weighted-t1-b05 --out chapters/ch03/expected/validation-bm25_weighted-t1-b05.json
```
wrote `chapters/ch03/expected/validation-bm25_weighted-t1-b05.json`

```
.venv/bin/python shared/tools/evaluate.py --split validation --hits 100 --passes 3 --ranking bm25_weighted --param 'input.query(w_title)=1' --param 'input.query(w_bullets)=0' --param 'input.query(w_description)=0' --param 'input.query(w_brand)=0.25' --label validation-bm25_weighted-t1-br025 --out chapters/ch03/expected/validation-bm25_weighted-t1-br025.json
```
wrote `chapters/ch03/expected/validation-bm25_weighted-t1-br025.json`

```
.venv/bin/python chapters/ch03/compare.py --block comparison --baseline validation-bm25_title chapters/ch03/expected/validation-bm25_title.json chapters/ch03/expected/validation-bm25_weighted-t1-br025.json chapters/ch03/expected/validation-bm25_weighted-t1-b05.json chapters/ch03/expected/validation-bm25_weighted-t1-d05.json chapters/ch03/expected/validation-bm25_weighted.json > chapters/ch03/expected/compare-validation-weights.block.md
```
wrote `chapters/ch03/expected/compare-validation-weights.block.md`
