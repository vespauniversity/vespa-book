# ch10 commands

Every command this chapter's reports were written by, verbatim, in the order they were run: one line the command, one line the file it writes, with the wall time where a command runs anything. The model runs need no key in the shell: `agent_loop.py` reads `OPENAI_API_KEY` from the repository's `.env` and sends it in a request header; the key is never printed or written. Every run below is over the full test set (872 questions, `--limit 872`); the question set is limited to each question's pool of judged products and the oracle is the S or E products of another brand. Wall times are from one run each on the reference machine, an Apple M4 Pro with a 4 CPU / 10 GB container VM (Rancher Desktop); a reader's will differ, and a model run is one record — the same command again will not give the same answers.

## M-set — the question set

# 872 questions at threshold 3 under the S-or-E oracle; each question line carries `pool`, the ids every search for it is limited to

.venv/bin/python chapters/ch10/build_multihop_set.py --split test --threshold 3 --out chapters/ch10/expected/multihop-set.json > chapters/ch10/expected/multihop-set.block.md
chapters/ch10/expected/multihop-set.json, chapters/ch10/expected/multihop-set.block.md   # also writes builds/esci-us-hard-book-s42-kdd-v4/multihop_test.jsonl (git-ignored); needs no Vespa

## Core

### The catalogue description the query surface is shown

.venv/bin/python chapters/ch10/schema_skill.py --app chapters/ch10/app --profiles hybrid_rrf,bm25_tuned,semantic --note 'Measured in earlier chapters against the human relevance labels of this catalogue: `hybrid_rrf`, the keyword and vector rankings merged by rank, ranked better than `bm25_tuned` (keyword only) and than `semantic` (the vector side alone), and further down its list reaches more labelled products than `bm25_tuned` and as many as `semantic`; among keyword-only rankings `bm25_tuned` ranked best.' --out chapters/ch10/expected/skill.md
chapters/ch10/expected/skill.md   # 3,715 characters; `--profiles` lists only the three rank profiles the tool surface offers, `--note` appends the paragraph after that list; every `--surface query` run below takes it with `--skill`, so the text the model saw in those runs is this file, byte for byte
chapters/ch10/expected/skill-allprofiles.md   # kept, not written by any command here: the earlier description, listing every rank profile of the package (the same command without `--profiles` and `--note`, 5,998 characters), which the first query-surface run at k = 3 was made with; that run's lean log is kept as chapters/ch10/expected/trajectories/llm-query-alternative-k3-allprofiles.jsonl and is the fifth column of the profile count below. It also lists one field since removed from the schema, so the command today no longer writes it byte for byte

### Rules planner (no model; the container alone)

# A warm-up pass first — the same command as the first run below, its output discarded — so the timings in the kept logs are from a warm container.

.venv/bin/python chapters/ch10/agent_loop.py --split test --planner rules --limit 872 --shape alternative --k 3 --out chapters/ch10/expected/trajectories/rules-alternative-k3.jsonl
chapters/ch10/expected/trajectories/rules-alternative-k3.jsonl   # 34 s (the discarded warm-up pass before it: 36 s)
.venv/bin/python chapters/ch10/agent_loop.py --split test --planner rules --limit 872 --shape alternative --k 3 --oracle --out chapters/ch10/expected/trajectories/rules-alternative-k3-oracle.jsonl
chapters/ch10/expected/trajectories/rules-alternative-k3-oracle.jsonl   # 12 s
.venv/bin/python chapters/ch10/agent_loop.py --split test --planner rules --limit 872 --shape alternative --k 20 --out chapters/ch10/expected/trajectories/rules-alternative-k20.jsonl
chapters/ch10/expected/trajectories/rules-alternative-k20.jsonl   # 35 s
.venv/bin/python chapters/ch10/agent_loop.py --split test --planner rules --limit 872 --shape alternative --k 20 --oracle --out chapters/ch10/expected/trajectories/rules-alternative-k20-oracle.jsonl
chapters/ch10/expected/trajectories/rules-alternative-k20-oracle.jsonl   # 12 s
.venv/bin/python chapters/ch10/agent_loop.py --split test --planner rules --limit 872 --shape brands --k 3 --out chapters/ch10/expected/trajectories/rules-brands-k3.jsonl
chapters/ch10/expected/trajectories/rules-brands-k3.jsonl   # 33 s

### Model planner (gpt-6-sol through its API; three runs at a time, each in the background)

# Each run: nohup … > chapters/ch10/review/logs/<name>.stderr 2>&1 &  (the stderr is one progress line per question). The three gap runs below went in together; run each splice only after its gap run has finished (its stderr file stops growing). Wall times are with three runs sharing the container and the model's API.
# The four tool-surface logs were written at the time to chapters/ch10/expected/trajectories/, with every prompt, and then moved, as written, to builds/esci-us-hard-book-s42-kdd-v4/trajectories/ (not in version control); the query-surface logs were written there directly, by the commands as shown. The commands below show the path a new run writes its full log to, and the wall times beside them are those of the runs as made. What ships under chapters/ch10/expected/trajectories/ is the lean copy the `trajectory_lean.py` loop right after these commands writes from each full log - the same name, every field but the prompts.
# A request to the model that comes back empty, times out, cannot connect or is answered with HTTP 429 or 5xx is sent once more, and the step records it (`retries`, `retry_reason`, `finish_reason`, `refusal`); each question's line is written to the log as it completes, and the same command run again over a log that exists skips the questions already in it and appends the rest. The query-surface runs at k = 3, k = 20 and with two sellers were made before the loop asked a second time: the questions whose reply came back empty were asked again afterwards, alone, by the commands under each run, and their lines replaced the first ones in place, marked `"second_pass": true`.
# Prompt characters beside each run are counted from its full log as the run wrote it, before the second passes were spliced in; the token figure assumes 2.5 characters per token and the dollar figure is estimated: prompt characters ÷ 2.5 characters per token × $2 per million input tokens; replies not priced.

# The progress lines of a background run go to chapters/ch10/review/logs/, a folder that is not shipped: create it once before the first run.
mkdir -p chapters/ch10/review/logs

.venv/bin/python chapters/ch10/agent_loop.py --split test --planner llm --limit 872 --surface tools --shape alternative --k 3 --out builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-tools-alternative-k3.jsonl
builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-tools-alternative-k3.jsonl   # 4368 s; 7.4 M prompt characters, ≈ 3.0 M tokens at 2.5 characters per token, ≈ $6 estimated
.venv/bin/python chapters/ch10/agent_loop.py --split test --planner llm --limit 872 --surface tools --shape alternative --k 3 --oracle --out builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-tools-alternative-k3-oracle.jsonl
builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-tools-alternative-k3-oracle.jsonl   # 4405 s; 7.7 M prompt characters, ≈ 3.1 M tokens at 2.5 characters per token, ≈ $6 estimated
.venv/bin/python chapters/ch10/agent_loop.py --split test --planner llm --limit 872 --surface query --skill chapters/ch10/expected/skill.md --shape alternative --k 3 --out builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3.jsonl
builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3.jsonl   # 6683 s; 17.2 M prompt characters, ≈ 6.9 M tokens at 2.5 characters per token, ≈ $14 estimated
.venv/bin/python -c 'import json,sys; log,src,out=sys.argv[1:]; ids={json.loads(l)["question_id"] for l in open(log) if json.loads(l)["error"]}; open(out,"w").writelines(l for l in open(src) if l.strip() and json.loads(l)["question_id"] in ids)' builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3.jsonl builds/esci-us-hard-book-s42-kdd-v4/multihop_test.jsonl chapters/ch10/review/gaps/llm-query-alternative-k3.jsonl
chapters/ch10/review/gaps/llm-query-alternative-k3.jsonl   # run before the splice below: the 6 questions of this run whose line carries an error — on this log, made before the loop asked again, the empty replies — (18953, 23749, 35118, 48098, 58312, 77858), their lines as in the question file
nohup .venv/bin/python chapters/ch10/agent_loop.py --split test --planner llm --limit 872 --surface query --skill chapters/ch10/expected/skill.md --shape alternative --k 3 --questions chapters/ch10/review/gaps/llm-query-alternative-k3.jsonl --out builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3-gaps.jsonl > chapters/ch10/review/logs/gaps-llm-query-alternative-k3.stderr 2>&1 &
builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3-gaps.jsonl   # 61 s, the three second passes side by side and nothing else against the model's API; 21 model turns, 154,293 prompt characters, ≈ $0.12 estimated; every question answered, none empty again: 5 succeed, 77858 does not
.venv/bin/python -c 'import json,sys; full,gaps=sys.argv[1:]; new={json.loads(l)["question_id"]:{**json.loads(l),"second_pass":True} for l in open(gaps)}; lines=[json.loads(l) for l in open(full)]; open(full,"w").write("".join(json.dumps(new.get(x["question_id"],x),ensure_ascii=False)+"\n" for x in lines))' builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3.jsonl builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3-gaps.jsonl
builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3.jsonl   # the 6 lines replaced in place by the second pass's, each with `"second_pass": true`; the other 866 lines byte for byte as they were
.venv/bin/python chapters/ch10/agent_loop.py --split test --planner llm --limit 872 --surface query --skill chapters/ch10/expected/skill.md --shape alternative --k 3 --oracle --out builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3-oracle.jsonl
builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3-oracle.jsonl   # 6590 s; 17.0 M prompt characters, ≈ 6.8 M tokens at 2.5 characters per token, ≈ $14 estimated
.venv/bin/python chapters/ch10/agent_loop.py --split test --planner llm --limit 872 --surface tools --shape alternative --k 20 --out builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-tools-alternative-k20.jsonl
builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-tools-alternative-k20.jsonl   # 4456 s; 12.5 M prompt characters, ≈ 5.0 M tokens at 2.5 characters per token, ≈ $10 estimated
.venv/bin/python chapters/ch10/agent_loop.py --split test --planner llm --limit 872 --surface query --skill chapters/ch10/expected/skill.md --shape alternative --k 20 --out builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k20.jsonl
builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k20.jsonl   # 6803 s; 22.0 M prompt characters, ≈ 8.8 M tokens at 2.5 characters per token, ≈ $18 estimated
.venv/bin/python -c 'import json,sys; log,src,out=sys.argv[1:]; ids={json.loads(l)["question_id"] for l in open(log) if json.loads(l)["error"]}; open(out,"w").writelines(l for l in open(src) if l.strip() and json.loads(l)["question_id"] in ids)' builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k20.jsonl builds/esci-us-hard-book-s42-kdd-v4/multihop_test.jsonl chapters/ch10/review/gaps/llm-query-alternative-k20.jsonl
chapters/ch10/review/gaps/llm-query-alternative-k20.jsonl   # run before the splice below: the 9 questions of this run whose line carries an error — on this log, made before the loop asked again, the empty replies — (7103, 7679, 17539, 49679, 53850, 74172, 77858, 94932, 102736), their lines as in the question file
nohup .venv/bin/python chapters/ch10/agent_loop.py --split test --planner llm --limit 872 --surface query --skill chapters/ch10/expected/skill.md --shape alternative --k 20 --questions chapters/ch10/review/gaps/llm-query-alternative-k20.jsonl --out builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k20-gaps.jsonl > chapters/ch10/review/logs/gaps-llm-query-alternative-k20.stderr 2>&1 &
builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k20-gaps.jsonl   # 95 s, the three second passes side by side and nothing else against the model's API; 32 model turns, 329,497 prompt characters, ≈ $0.26 estimated; every question answered, none empty again: 7 succeed, 77858 and 102736 do not
.venv/bin/python -c 'import json,sys; full,gaps=sys.argv[1:]; new={json.loads(l)["question_id"]:{**json.loads(l),"second_pass":True} for l in open(gaps)}; lines=[json.loads(l) for l in open(full)]; open(full,"w").write("".join(json.dumps(new.get(x["question_id"],x),ensure_ascii=False)+"\n" for x in lines))' builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k20.jsonl builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k20-gaps.jsonl
builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k20.jsonl   # the 9 lines replaced in place by the second pass's, each with `"second_pass": true`; the other 863 lines byte for byte as they were
.venv/bin/python chapters/ch10/agent_loop.py --split test --planner llm --limit 872 --surface tools --shape brands --k 3 --out builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-tools-brands-k3.jsonl
builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-tools-brands-k3.jsonl   # 7619 s; 11.2 M prompt characters, ≈ 4.5 M tokens at 2.5 characters per token, ≈ $9 estimated
.venv/bin/python chapters/ch10/agent_loop.py --split test --planner llm --limit 872 --surface query --skill chapters/ch10/expected/skill.md --shape brands --k 3 --out builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-brands-k3.jsonl
builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-brands-k3.jsonl   # 11,680 s (195 min), the only model run against the API, on the loop that asks a second time; shift B of the query surface ran against the container for its first 49 minutes; 25.5 M prompt characters over 3,425 model turns, 25.9 M sent counting the 45 turns asked a second time after an empty reply, ≈ 10.3 M tokens at 2.5 characters per token, ≈ $21 estimated; 2 questions whose reply came back empty twice (54325, 63486) are recorded as the planner's error

### Lean copies of the eight model logs (the shipped form; seconds)

# Placed here because the scoring below reads its output; our lean copies were written after the scoring commands had been run from the full logs. A model run you did not make has no full log: its line in the loop says so and leaves the shipped copy as it is.

for f in llm-tools-alternative-k3 llm-tools-alternative-k3-oracle llm-query-alternative-k3 llm-query-alternative-k3-oracle llm-tools-alternative-k20 llm-query-alternative-k20 llm-tools-brands-k3 llm-query-brands-k3; do .venv/bin/python chapters/ch10/trajectory_lean.py builds/esci-us-hard-book-s42-kdd-v4/trajectories/$f.jsonl --out chapters/ch10/expected/trajectories/$f.jsonl; done
chapters/ch10/expected/trajectories/llm-*.jsonl   # 1 s for the eight; 147,543,294 -> 22,388,948 bytes. Every scoring command below was run again from the lean copies afterwards: every block came out byte-identical, every JSON identical but for the host's capture time

### Scoring each log (re-scoring measures nothing; seconds each)

# The scoring commands read the lean copies under chapters/ch10/expected/trajectories/. After a model run of your own, run its lean command (the section above) first, so what is scored is your log and not the shipped one.

for f in rules-alternative-k3 rules-alternative-k3-oracle rules-alternative-k20 rules-alternative-k20-oracle rules-brands-k3 llm-tools-alternative-k3 llm-tools-alternative-k3-oracle llm-query-alternative-k3 llm-query-alternative-k3-oracle llm-tools-alternative-k20 llm-query-alternative-k20 llm-tools-brands-k3 llm-query-brands-k3; do .venv/bin/python chapters/ch10/eval_trajectory.py chapters/ch10/expected/trajectories/$f.jsonl --split test --out chapters/ch10/expected/trajectory-$f.json --block summary > chapters/ch10/expected/trajectory-$f.block.md; done
chapters/ch10/expected/trajectory-<name>.json, chapters/ch10/expected/trajectory-<name>.block.md   # <name> as in the loop; the summary block carries the status counts and, for `brands`, brand recall / precision

### Retrieved evidence against supplied evidence

.venv/bin/python chapters/ch10/oracle_compare.py chapters/ch10/expected/trajectories/rules-alternative-k3.jsonl chapters/ch10/expected/trajectories/rules-alternative-k3-oracle.jsonl --split test --out chapters/ch10/expected/oracle-compare-rules-tools-k3.json --block compare > chapters/ch10/expected/oracle-compare-rules-tools-k3.block.md
chapters/ch10/expected/oracle-compare-rules-tools-k3.json, chapters/ch10/expected/oracle-compare-rules-tools-k3.block.md
.venv/bin/python chapters/ch10/oracle_compare.py chapters/ch10/expected/trajectories/rules-alternative-k20.jsonl chapters/ch10/expected/trajectories/rules-alternative-k20-oracle.jsonl --split test --out chapters/ch10/expected/oracle-compare-rules-tools-k20.json --block compare > chapters/ch10/expected/oracle-compare-rules-tools-k20.block.md
chapters/ch10/expected/oracle-compare-rules-tools-k20.json, chapters/ch10/expected/oracle-compare-rules-tools-k20.block.md
.venv/bin/python chapters/ch10/oracle_compare.py chapters/ch10/expected/trajectories/llm-tools-alternative-k3.jsonl chapters/ch10/expected/trajectories/llm-tools-alternative-k3-oracle.jsonl --split test --out chapters/ch10/expected/oracle-compare-llm-tools-k3.json --block compare > chapters/ch10/expected/oracle-compare-llm-tools-k3.block.md
chapters/ch10/expected/oracle-compare-llm-tools-k3.json, chapters/ch10/expected/oracle-compare-llm-tools-k3.block.md
.venv/bin/python chapters/ch10/oracle_compare.py chapters/ch10/expected/trajectories/llm-query-alternative-k3.jsonl chapters/ch10/expected/trajectories/llm-query-alternative-k3-oracle.jsonl --split test --out chapters/ch10/expected/oracle-compare-llm-query-k3.json --block compare > chapters/ch10/expected/oracle-compare-llm-query-k3.block.md
chapters/ch10/expected/oracle-compare-llm-query-k3.json, chapters/ch10/expected/oracle-compare-llm-query-k3.block.md

### Tool surface against query surface, and k = 3 against k = 20

.venv/bin/python chapters/ch10/surface_compare.py chapters/ch10/expected/trajectories/llm-tools-alternative-k3.jsonl chapters/ch10/expected/trajectories/llm-query-alternative-k3.jsonl --split test --block surfaces --out chapters/ch10/expected/surface-compare-k3.json > chapters/ch10/expected/surface-compare-k3.block.md
chapters/ch10/expected/surface-compare-k3.json, chapters/ch10/expected/surface-compare-k3.block.md
.venv/bin/python chapters/ch10/surface_compare.py chapters/ch10/expected/trajectories/llm-tools-alternative-k20.jsonl chapters/ch10/expected/trajectories/llm-query-alternative-k20.jsonl --split test --block surfaces --out chapters/ch10/expected/surface-compare-k20.json > chapters/ch10/expected/surface-compare-k20.block.md
chapters/ch10/expected/surface-compare-k20.json, chapters/ch10/expected/surface-compare-k20.block.md
.venv/bin/python chapters/ch10/surface_compare.py chapters/ch10/expected/trajectories/llm-tools-alternative-k3.jsonl chapters/ch10/expected/trajectories/llm-tools-alternative-k20.jsonl --split test --block k --out chapters/ch10/expected/k-compare-tools.json > chapters/ch10/expected/k-compare-tools.block.md
chapters/ch10/expected/k-compare-tools.json, chapters/ch10/expected/k-compare-tools.block.md
.venv/bin/python chapters/ch10/surface_compare.py chapters/ch10/expected/trajectories/llm-query-alternative-k3.jsonl chapters/ch10/expected/trajectories/llm-query-alternative-k20.jsonl --split test --block k --out chapters/ch10/expected/k-compare-query.json > chapters/ch10/expected/k-compare-query.block.md
chapters/ch10/expected/k-compare-query.json, chapters/ch10/expected/k-compare-query.block.md
.venv/bin/python chapters/ch10/surface_compare.py chapters/ch10/expected/trajectories/rules-alternative-k3.jsonl chapters/ch10/expected/trajectories/rules-alternative-k20.jsonl --split test --block k --out chapters/ch10/expected/k-compare-rules.json > chapters/ch10/expected/k-compare-rules.block.md
chapters/ch10/expected/k-compare-rules.json, chapters/ch10/expected/k-compare-rules.block.md   # the rules planner's cost side of the same question

### Query shift A — human queries against the agent's queries

.venv/bin/python chapters/ch10/analyze_query_distribution.py --split test --trajectories chapters/ch10/expected/trajectories/llm-tools-alternative-k3.jsonl --out chapters/ch10/expected/shift-a-tools.json --block shift > chapters/ch10/expected/shift-a-tools.block.md
chapters/ch10/expected/shift-a-tools.json, chapters/ch10/expected/shift-a-tools.block.md
.venv/bin/python chapters/ch10/analyze_query_distribution.py --split test --trajectories chapters/ch10/expected/trajectories/llm-query-alternative-k3.jsonl --out chapters/ch10/expected/shift-a-query.json --block shift > chapters/ch10/expected/shift-a-query.block.md
chapters/ch10/expected/shift-a-query.json, chapters/ch10/expected/shift-a-query.block.md   # shift B, which queries the container, is its own section below

### Per-task retrieval latency of the rules loop

.venv/bin/python chapters/ch10/eval_trajectory.py chapters/ch10/expected/trajectories/rules-alternative-k3.jsonl --split test --out chapters/ch10/expected/latency-rules.json --block latency --warmed-up > chapters/ch10/expected/latency-rules.block.md
chapters/ch10/expected/latency-rules.json, chapters/ch10/expected/latency-rules.block.md   # `--warmed-up` records that the log was written right after the discarded pass above; stdout redirected to the block file

### One trajectory as a table

.venv/bin/python chapters/ch10/agent_loop.py --split test --from chapters/ch10/expected/trajectories/llm-tools-alternative-k3.jsonl --question-id 19 --block trajectory > chapters/ch10/expected/trajectory-example-llm.block.md
chapters/ch10/expected/trajectory-example-llm.block.md   # the first question of the tool-surface log; re-renders, runs nothing

### Hard-negative subset: the 470 questions whose pool holds a product labelled irrelevant (re-scoring; seconds)

for f in rules-alternative-k3 rules-alternative-k3-oracle llm-tools-alternative-k3 llm-tools-alternative-k3-oracle llm-query-alternative-k3 llm-query-alternative-k3-oracle; do .venv/bin/python chapters/ch10/eval_trajectory.py chapters/ch10/expected/trajectories/$f.jsonl --split test --subset hardneg --out chapters/ch10/expected/trajectory-$f-hardneg.json --block summary-hardneg > chapters/ch10/expected/trajectory-$f-hardneg.block.md; done
chapters/ch10/expected/trajectory-<name>-hardneg.json, chapters/ch10/expected/trajectory-<name>-hardneg.block.md
.venv/bin/python chapters/ch10/oracle_compare.py chapters/ch10/expected/trajectories/rules-alternative-k3.jsonl chapters/ch10/expected/trajectories/rules-alternative-k3-oracle.jsonl --split test --subset hardneg --out chapters/ch10/expected/oracle-compare-rules-tools-k3-hardneg.json --block compare-hardneg > chapters/ch10/expected/oracle-compare-rules-tools-k3-hardneg.block.md
chapters/ch10/expected/oracle-compare-rules-tools-k3-hardneg.json, chapters/ch10/expected/oracle-compare-rules-tools-k3-hardneg.block.md
.venv/bin/python chapters/ch10/oracle_compare.py chapters/ch10/expected/trajectories/llm-tools-alternative-k3.jsonl chapters/ch10/expected/trajectories/llm-tools-alternative-k3-oracle.jsonl --split test --subset hardneg --out chapters/ch10/expected/oracle-compare-llm-tools-k3-hardneg.json --block compare-hardneg > chapters/ch10/expected/oracle-compare-llm-tools-k3-hardneg.block.md
chapters/ch10/expected/oracle-compare-llm-tools-k3-hardneg.json, chapters/ch10/expected/oracle-compare-llm-tools-k3-hardneg.block.md
.venv/bin/python chapters/ch10/oracle_compare.py chapters/ch10/expected/trajectories/llm-query-alternative-k3.jsonl chapters/ch10/expected/trajectories/llm-query-alternative-k3-oracle.jsonl --split test --subset hardneg --out chapters/ch10/expected/oracle-compare-llm-query-k3-hardneg.json --block compare-hardneg > chapters/ch10/expected/oracle-compare-llm-query-k3-hardneg.block.md
chapters/ch10/expected/oracle-compare-llm-query-k3-hardneg.json, chapters/ch10/expected/oracle-compare-llm-query-k3-hardneg.block.md

### All of top-k: success only when every product of the last search is in the oracle (re-scoring; seconds)

for f in rules-alternative-k3 rules-alternative-k20 llm-tools-alternative-k3 llm-tools-alternative-k20 llm-query-alternative-k3 llm-query-alternative-k20; do .venv/bin/python chapters/ch10/eval_trajectory.py chapters/ch10/expected/trajectories/$f.jsonl --split test --success all-top-k --out chapters/ch10/expected/trajectory-$f-alltopk.json --block summary-alltopk > chapters/ch10/expected/trajectory-$f-alltopk.block.md; done
chapters/ch10/expected/trajectory-<name>-alltopk.json, chapters/ch10/expected/trajectory-<name>-alltopk.block.md

### The seller boundary: the rules planner run as a user of the anchor's seller (no model)

.venv/bin/python chapters/ch10/agent_loop.py --split test --planner rules --limit 872 --shape alternative --k 3 --tenant-from-anchor --out chapters/ch10/expected/trajectories/rules-alternative-k3-tenant.jsonl
chapters/ch10/expected/trajectories/rules-alternative-k3-tenant.jsonl   # 43 s; each question's tenant is its anchor product's `tenant_id` from builds/esci-us-hard-book-s42-kdd-v4/tenants.jsonl, recorded per line as `tenant`
.venv/bin/python chapters/ch10/eval_trajectory.py chapters/ch10/expected/trajectories/rules-alternative-k3-tenant.jsonl --split test --out chapters/ch10/expected/trajectory-rules-alternative-k3-tenant.json --block summary > chapters/ch10/expected/trajectory-rules-alternative-k3-tenant.block.md
chapters/ch10/expected/trajectory-rules-alternative-k3-tenant.json, chapters/ch10/expected/trajectory-rules-alternative-k3-tenant.block.md

.venv/bin/python chapters/ch10/eval_trajectory.py chapters/ch10/expected/trajectories/rules-alternative-k3-tenant.jsonl --split test --out chapters/ch10/expected/trajectory-rules-alternative-k3-tenant.json --block boundary > chapters/ch10/expected/trajectory-rules-alternative-k3-tenant-boundary.block.md
chapters/ch10/expected/trajectory-rules-alternative-k3-tenant-boundary.block.md   # the ceiling under one seller, from the build: 0 of 872 answerable; the same JSON as the summary command above, now with its `boundary` section

### The seller boundary widened to two sellers: the anchor's and the oracle seller with the most products in the question's oracle (`--tenant-pair`)

.venv/bin/python chapters/ch10/agent_loop.py --split test --planner rules --limit 872 --shape alternative --k 3 --tenant-pair --out chapters/ch10/expected/trajectories/rules-alternative-k3-tenant-pair.jsonl
chapters/ch10/expected/trajectories/rules-alternative-k3-tenant-pair.jsonl   # 31 s; each line records the pair as `tenant: [anchor's seller, oracle seller]` and `tenant_rule: pair`
.venv/bin/python chapters/ch10/eval_trajectory.py chapters/ch10/expected/trajectories/rules-alternative-k3-tenant-pair.jsonl --split test --out chapters/ch10/expected/trajectory-rules-alternative-k3-tenant-pair.json --block summary > chapters/ch10/expected/trajectory-rules-alternative-k3-tenant-pair.block.md
.venv/bin/python chapters/ch10/eval_trajectory.py chapters/ch10/expected/trajectories/rules-alternative-k3-tenant-pair.jsonl --split test --out chapters/ch10/expected/trajectory-rules-alternative-k3-tenant-pair.json --block boundary > chapters/ch10/expected/trajectory-rules-alternative-k3-tenant-pair-boundary.block.md
chapters/ch10/expected/trajectory-rules-alternative-k3-tenant-pair.json, chapters/ch10/expected/trajectory-rules-alternative-k3-tenant-pair.block.md, chapters/ch10/expected/trajectory-rules-alternative-k3-tenant-pair-boundary.block.md   # the boundary block carries the ceiling (872 of 872 answerable, oracle share inside p50 0.214) and what followed each `filtered`
nohup .venv/bin/python chapters/ch10/agent_loop.py --split test --planner llm --limit 872 --surface query --skill chapters/ch10/expected/skill.md --shape alternative --k 3 --tenant-pair --out builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3-tenant-pair.jsonl > chapters/ch10/review/logs/tenant-pair-query.stderr 2>&1 &
builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3-tenant-pair.jsonl   # 7,131 s (119 min), run alongside the brands query-surface run above, and for 49 of those minutes an earlier pass of shift B below; 22,337,785 bytes with the prompts as the run wrote it, 22,384,969 after the splice below (18.2 M prompt characters, ≈ 7.3 M tokens at 2.5 characters per token, ≈ $15 estimated)
.venv/bin/python -c 'import json,sys; log,src,out=sys.argv[1:]; ids={json.loads(l)["question_id"] for l in open(log) if json.loads(l)["error"]}; open(out,"w").writelines(l for l in open(src) if l.strip() and json.loads(l)["question_id"] in ids)' builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3-tenant-pair.jsonl builds/esci-us-hard-book-s42-kdd-v4/multihop_test.jsonl chapters/ch10/review/gaps/llm-query-alternative-k3-tenant-pair.jsonl
chapters/ch10/review/gaps/llm-query-alternative-k3-tenant-pair.jsonl   # run before the splice below: the 3 questions of this run whose line carries an error — on this log, made before the loop asked again, the empty replies — (20822, 25924, 66338), their lines as in the question file
nohup .venv/bin/python chapters/ch10/agent_loop.py --split test --planner llm --limit 872 --surface query --skill chapters/ch10/expected/skill.md --shape alternative --k 3 --tenant-pair --questions chapters/ch10/review/gaps/llm-query-alternative-k3-tenant-pair.jsonl --out builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3-tenant-pair-gaps.jsonl > chapters/ch10/review/logs/gaps-llm-query-alternative-k3-tenant-pair.stderr 2>&1 &
builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3-tenant-pair-gaps.jsonl   # 31 s, the three second passes side by side and nothing else against the model's API; 11 model turns, 78,827 prompt characters, ≈ $0.06 estimated; every question answered, none empty again: 2 succeed, 66338 does not
.venv/bin/python -c 'import json,sys; full,gaps=sys.argv[1:]; new={json.loads(l)["question_id"]:{**json.loads(l),"second_pass":True} for l in open(gaps)}; lines=[json.loads(l) for l in open(full)]; open(full,"w").write("".join(json.dumps(new.get(x["question_id"],x),ensure_ascii=False)+"\n" for x in lines))' builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3-tenant-pair.jsonl builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3-tenant-pair-gaps.jsonl
builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3-tenant-pair.jsonl   # the 3 lines replaced in place by the second pass's, each with `"second_pass": true`; the other 869 lines byte for byte as they were
.venv/bin/python chapters/ch10/trajectory_lean.py builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-query-alternative-k3-tenant-pair.jsonl --out chapters/ch10/expected/trajectories/llm-query-alternative-k3-tenant-pair.jsonl
chapters/ch10/expected/trajectories/llm-query-alternative-k3-tenant-pair.jsonl   # 3,611,237 bytes, from the full log after the splice above; the two scoring commands below were also run from the full log: both blocks byte-identical
.venv/bin/python chapters/ch10/eval_trajectory.py chapters/ch10/expected/trajectories/llm-query-alternative-k3-tenant-pair.jsonl --split test --out chapters/ch10/expected/trajectory-llm-query-alternative-k3-tenant-pair.json --block summary > chapters/ch10/expected/trajectory-llm-query-alternative-k3-tenant-pair.block.md
.venv/bin/python chapters/ch10/eval_trajectory.py chapters/ch10/expected/trajectories/llm-query-alternative-k3-tenant-pair.jsonl --split test --out chapters/ch10/expected/trajectory-llm-query-alternative-k3-tenant-pair.json --block boundary > chapters/ch10/expected/trajectory-llm-query-alternative-k3-tenant-pair-boundary.block.md
chapters/ch10/expected/trajectory-llm-query-alternative-k3-tenant-pair.json, chapters/ch10/expected/trajectory-llm-query-alternative-k3-tenant-pair.block.md, chapters/ch10/expected/trajectory-llm-query-alternative-k3-tenant-pair-boundary.block.md
.venv/bin/python chapters/ch10/surface_compare.py chapters/ch10/expected/trajectories/llm-query-alternative-k3.jsonl chapters/ch10/expected/trajectories/llm-query-alternative-k3-tenant-pair.jsonl --split test --block tenant --out chapters/ch10/expected/tenant-compare-query-k3.json > chapters/ch10/expected/tenant-compare-query-k3.block.md
chapters/ch10/expected/tenant-compare-query-k3.json, chapters/ch10/expected/tenant-compare-query-k3.block.md   # the unrestricted query-surface k = 3 run against the bounded one, question by question

### Fan-out latency, with and without a stream of writes (the engine's side only; one pass per cell)

# Run alone; start shift B only after it finishes.
nohup .venv/bin/python chapters/ch10/fanout_latency.py chapters/ch10/expected/trajectories/rules-alternative-k3.jsonl --split test --out chapters/ch10/expected/fanout-latency.json --block fanout > chapters/ch10/expected/fanout-latency.block.md 2> chapters/ch10/review/logs/fanout.stderr &
chapters/ch10/expected/fanout-latency.json, chapters/ch10/expected/fanout-latency.block.md   # 8 min 11 s: six cells of 20 s warm-up + 60 s window (1 / 2 / 4 loops, then the same with 200 tenant_id updates/s); nothing else was running against the container

### Query shift B — the agent's statements and the human queries under the four profiles (the container; no model)

nohup .venv/bin/python chapters/ch10/analyze_query_distribution.py --split test --mode b --trajectories chapters/ch10/expected/trajectories/llm-query-alternative-k3.jsonl --out chapters/ch10/expected/shift-b-query.json --block shift-b > chapters/ch10/expected/shift-b-query.block.md 2> chapters/ch10/review/logs/shift-b-query.stderr &
chapters/ch10/expected/shift-b-query.json, chapters/ch10/expected/shift-b-query.block.md   # 49 min, run again on the log with its second passes spliced in, with the brands query-surface model run in flight at the same time; 1,300 statements × 4 profiles + 871 human queries × 4 profiles × 2 scopes
nohup .venv/bin/python chapters/ch10/analyze_query_distribution.py --split test --mode b --trajectories chapters/ch10/expected/trajectories/llm-tools-alternative-k3.jsonl --out chapters/ch10/expected/shift-b-tools.json --block shift-b > chapters/ch10/expected/shift-b-tools.block.md 2> chapters/ch10/review/logs/shift-b-tools.stderr &
chapters/ch10/expected/shift-b-tools.json, chapters/ch10/expected/shift-b-tools.block.md   # 55 min, side by side with an earlier shift B of the query surface; the scores do not depend on the load, only the wall time does
.venv/bin/python chapters/ch10/analyze_query_distribution.py --split test --mode b --from chapters/ch10/expected/shift-b-query.json > chapters/ch10/expected/shift-b-query.block.md
.venv/bin/python chapters/ch10/analyze_query_distribution.py --split test --mode b --from chapters/ch10/expected/shift-b-tools.json > chapters/ch10/expected/shift-b-tools.block.md
chapters/ch10/expected/shift-b-<surface>.block.md   # the blocks as shipped, rendered from the two reports; `--from` queries nothing

### The rank profile each statement named (re-counting the four logs of the surface comparisons and the earlier query-surface log; seconds)

.venv/bin/python chapters/ch10/analyze_query_distribution.py --split test --block profiles --trajectories chapters/ch10/expected/trajectories/llm-tools-alternative-k3.jsonl chapters/ch10/expected/trajectories/llm-query-alternative-k3.jsonl chapters/ch10/expected/trajectories/llm-tools-alternative-k20.jsonl chapters/ch10/expected/trajectories/llm-query-alternative-k20.jsonl chapters/ch10/expected/trajectories/llm-query-alternative-k3-allprofiles.jsonl --out chapters/ch10/expected/profile-choice.json > chapters/ch10/expected/profile-choice.block.md
chapters/ch10/expected/profile-choice.json, chapters/ch10/expected/profile-choice.block.md   # reads the five lean logs and sends nothing; the report records each log's size and sha256; a statement that names no profile ran under `hybrid_rrf`; the fifth column is the k = 3 query-surface run made with `skill-allprofiles.md`, the description that listed every rank profile

### The oracle's products supplied: every product of the question's oracle, with its title and brand, in the evidence before the first turn (`--oracle-products`)

.venv/bin/python chapters/ch10/agent_loop.py --split test --planner rules --limit 872 --shape alternative --k 3 --oracle-products --out chapters/ch10/expected/trajectories/rules-alternative-k3-oracle-products.jsonl
chapters/ch10/expected/trajectories/rules-alternative-k3-oracle-products.jsonl   # under 1 s (0.49 s): the recipe answers with the first product of the list and sends no request; each line records `oracle_mode: true` and `oracle_kind: products`
.venv/bin/python chapters/ch10/eval_trajectory.py chapters/ch10/expected/trajectories/rules-alternative-k3-oracle-products.jsonl --split test --out chapters/ch10/expected/trajectory-rules-alternative-k3-oracle-products.json --block summary > chapters/ch10/expected/trajectory-rules-alternative-k3-oracle-products.block.md
chapters/ch10/expected/trajectory-rules-alternative-k3-oracle-products.json, chapters/ch10/expected/trajectory-rules-alternative-k3-oracle-products.block.md
.venv/bin/python chapters/ch10/oracle_compare.py chapters/ch10/expected/trajectories/rules-alternative-k3.jsonl chapters/ch10/expected/trajectories/rules-alternative-k3-oracle-products.jsonl --split test --out chapters/ch10/expected/oracle-compare-rules-tools-k3-products.json --block compare-products > chapters/ch10/expected/oracle-compare-rules-tools-k3-products.block.md
chapters/ch10/expected/oracle-compare-rules-tools-k3-products.json, chapters/ch10/expected/oracle-compare-rules-tools-k3-products.block.md   # `--block compare` refuses a log with the products supplied, and `compare-products` one with the first hop's facts supplied
nohup .venv/bin/python chapters/ch10/agent_loop.py --split test --planner llm --limit 872 --surface tools --shape alternative --k 3 --oracle-products --out builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-tools-alternative-k3-oracle-products.jsonl > chapters/ch10/review/logs/oracle-products-tools.stderr 2>&1 &
builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-tools-alternative-k3-oracle-products.jsonl   # 1,460 s (24 min), the only run against the container and the model's API; most questions take one model turn, so the run is shorter than the retrieved one; 5,875,796 bytes with the prompts (4,856,548 prompt characters and 52,503 reply characters over 979 model turns, ≈ 1.94 M and 0.02 M tokens at 2.5 characters per token, ≈ $4 estimated)
.venv/bin/python chapters/ch10/trajectory_lean.py builds/esci-us-hard-book-s42-kdd-v4/trajectories/llm-tools-alternative-k3-oracle-products.jsonl --out chapters/ch10/expected/trajectories/llm-tools-alternative-k3-oracle-products.jsonl
chapters/ch10/expected/trajectories/llm-tools-alternative-k3-oracle-products.jsonl   # 792,131 bytes; the summary and compare-products commands below were also run from the full log: both blocks byte-identical
.venv/bin/python chapters/ch10/eval_trajectory.py chapters/ch10/expected/trajectories/llm-tools-alternative-k3-oracle-products.jsonl --split test --out chapters/ch10/expected/trajectory-llm-tools-alternative-k3-oracle-products.json --block summary > chapters/ch10/expected/trajectory-llm-tools-alternative-k3-oracle-products.block.md
.venv/bin/python chapters/ch10/eval_trajectory.py chapters/ch10/expected/trajectories/llm-tools-alternative-k3-oracle-products.jsonl --split test --subset hardneg --block summary-hardneg --out chapters/ch10/expected/trajectory-llm-tools-alternative-k3-oracle-products-hardneg.json > chapters/ch10/expected/trajectory-llm-tools-alternative-k3-oracle-products-hardneg.block.md
chapters/ch10/expected/trajectory-llm-tools-alternative-k3-oracle-products.json, chapters/ch10/expected/trajectory-llm-tools-alternative-k3-oracle-products.block.md, chapters/ch10/expected/trajectory-llm-tools-alternative-k3-oracle-products-hardneg.json, chapters/ch10/expected/trajectory-llm-tools-alternative-k3-oracle-products-hardneg.block.md
.venv/bin/python chapters/ch10/oracle_compare.py chapters/ch10/expected/trajectories/llm-tools-alternative-k3.jsonl chapters/ch10/expected/trajectories/llm-tools-alternative-k3-oracle-products.jsonl --split test --out chapters/ch10/expected/oracle-compare-llm-tools-k3-products.json --block compare-products > chapters/ch10/expected/oracle-compare-llm-tools-k3-products.block.md
.venv/bin/python chapters/ch10/oracle_compare.py chapters/ch10/expected/trajectories/llm-tools-alternative-k3.jsonl chapters/ch10/expected/trajectories/llm-tools-alternative-k3-oracle-products.jsonl --split test --subset hardneg --out chapters/ch10/expected/oracle-compare-llm-tools-k3-products-hardneg.json --block compare-products-hardneg > chapters/ch10/expected/oracle-compare-llm-tools-k3-products-hardneg.block.md
chapters/ch10/expected/oracle-compare-llm-tools-k3-products.json, chapters/ch10/expected/oracle-compare-llm-tools-k3-products.block.md, chapters/ch10/expected/oracle-compare-llm-tools-k3-products-hardneg.json, chapters/ch10/expected/oracle-compare-llm-tools-k3-products-hardneg.block.md   # the retrieved tool-surface k = 3 run against the products-supplied one, question by question, over the full set and the hard-negative subset

## Tests

.venv/bin/python -m pytest tests -q
