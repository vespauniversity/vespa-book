#!/usr/bin/env bash
# Bring this machine to the starting point of one chapter.
#
#   ./bootstrap.sh ch02            from wherever you are, to chapter 2's start
#   ./bootstrap.sh ch03            from a chapter-2 container, only what is missing
#   ./bootstrap.sh ch03 --fresh    throw the venv and the container away first
#   ./bootstrap.sh ch03 --tests    the same, plus the test framework (see step 1)
#
# The same command works whether you are starting the book here or continuing
# from the previous chapter. Each of the five resources below is checked and
# skipped if it is already right, so "continuing" is just this script skipping
# more steps. Nothing here decides anything about your results; it only gets
# you to the point where the chapter's own commands can.
#
# From a container that holds a later chapter, use --fresh: the script skips a
# feed the count says it does not need and does not remove a later chapter's
# document types.
#
#   1. venv       .venv with Python 3.11 and the pinned packages this chapter
#                 needs (chapter.toml [requirements] groups, each from its lock
#                 file under shared/requirements/lock/). There is one
#                 environment and it only grows: following the book in order
#                 means running this script as you reach each chapter, not
#                 keeping seven virtual environments. --tests adds the
#                 `tests` group (pytest) as well; nothing a chapter asks you
#                 to run wants a test framework, so it is off by default -
#                 the suite under tests/ belongs to whoever maintains this
#                 repository, not to anyone reading the book.
#   2. corpus     the ESCI sample under builds/, built from the cached dataset;
#                 a build whose documents predate the current document-id
#                 format (namespace = the locale, user part = the bare ASIN)
#                 is rebuilt in place, same directory name
#   3. container  one Vespa container, the pinned image, named vespa-book-fable
#   4. app        this chapter's application package deployed - after any
#                 model file it declares by `file:` has been fetched into
#                 app/models/ and verified by hash (chapter.toml [bootstrap]
#                 models). When Vespa answers the deploy with "require
#                 restart" (an attribute setting changed on a running
#                 container), the search node is restarted here and the
#                 script waits until every document answers again. A deploy
#                 Vespa refuses (its answer starts with "Error:" - a package
#                 that fails validation, say a field whose indexing changed)
#                 stops the script with that answer: the CLI exits 0 on a
#                 refusal, so the text is the only signal.
#   5. documents  this chapter's documents fed, if the container has fewer -
#                 or, for a chapter whose documents carry a field computed at
#                 indexing time, if none of them has it yet (the count alone
#                 cannot tell). A dense HNSW field is probed with one
#                 nearest-neighbour query; any other field with one query
#                 under a rank profile that exposes it as a match-feature
#                 (chapter.toml [bootstrap] probe_*). A chapter that fills
#                 a plain attribute afterwards by a partial update names it
#                 as [bootstrap] update_field and the command as update; that
#                 update runs when no document carries a value yet. Before
#                 any of this, when the index already holds documents, the
#                 first document of the build file is fetched by id through
#                 the document API: a 404 means the index was fed under an
#                 older document-id format, and the script refuses and asks
#                 for --fresh rather than feeding on top.
#
# Pins live in docs/pins.md. The chapter's own needs live in its chapter.toml.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$root"

VESPA_IMAGE="vespaengine/vespa:8.751.13"
CONTAINER="vespa-book-fable"
PYTHON_MINOR="3.11"

chapter=""
fresh=0
with_tests=0
for arg in "$@"; do
  case "$arg" in
    --fresh) fresh=1 ;;
    --tests) with_tests=1 ;;
    -h|--help) sed -e '1d' -e '/^[^#]/,$d' -e 's/^# \{0,1\}//' "${BASH_SOURCE[0]}"; exit 0 ;;
    ch[0-9][0-9]) chapter="$arg" ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done
[ -n "$chapter" ] || { echo "usage: ./bootstrap.sh chNN [--fresh] [--tests]" >&2; exit 2; }

toml="chapters/$chapter/chapter.toml"
[ -f "$toml" ] || { echo "no $toml" >&2; exit 1; }

say()  { printf '\n== %s\n' "$*"; }
skip() { printf '   skip  %s\n' "$*"; }
do_()  { printf '   do    %s\n' "$*"; }
# How many documents the index holds. macOS bash 3.2 mis-parses a `)` inside
# quotes inside `"$( )"`, so this is a function and never inline.
count_docs() {
  curl -fs 'http://localhost:8080/search/?yql=select%20*%20from%20product%20where%20true&hits=0' 2>/dev/null \
    | python3 -c 'import sys, json; print(json.load(sys.stdin)["root"]["fields"]["totalCount"])' 2>/dev/null || echo 0
}

# Whether any document carries this chapter's vector field. A chapter that
# adds an embedder keeps the same document count and still needs every document
# fed again, because the vectors are computed at index time. One
# nearest-neighbour probe answers it: zero hits means no document has the field.
# The probe assumes the chapter's rank profile `semantic` and embedder id
# `embedder`, the names every chapter from chapter 4 on keeps; a synthetic
# field is not something the document API is asked about.
has_field() {
  local yql="select id from product where {targetHits:1}nearestNeighbor($1, q)"
  curl -fs -G 'http://localhost:8080/search/' --data-urlencode "yql=$yql" \
    --data-urlencode 'ranking.profile=semantic' \
    --data-urlencode 'input.query(q)=embed(embedder, "probe")' \
    --data-urlencode 'hits=0' 2>/dev/null \
    | python3 -c 'import sys, json; sys.exit(0 if json.load(sys.stdin)["root"]["fields"]["totalCount"] > 0 else 1)' 2>/dev/null
}

# The same question for a field a nearest-neighbour query cannot see - a
# mapped token tensor, a token-id vector with no index. One query over
# every document, ranked by the chapter's own profile with the extra query
# inputs the profile needs, one hit: if that hit's match-feature for the field
# is all zeros, no document carries it yet. `probe_profile`, `probe_feature`
# and `probe_params` come from chapter.toml [bootstrap].
has_feature() {
  local profile="$1" feature="$2"; shift 2
  local args=()
  for kv in "$@"; do args+=(--data-urlencode "$kv"); done
  curl -fs -G 'http://localhost:8080/search/' \
    --data-urlencode 'yql=select id from product where true' \
    --data-urlencode "ranking.profile=$profile" \
    --data-urlencode 'input.query(q)=embed(embedder, "probe")' \
    --data-urlencode 'hits=1' --data-urlencode 'timeout=30s' "${args[@]}" 2>/dev/null \
    | python3 -c '
import sys, json
feature = sys.argv[1]
hit = (json.load(sys.stdin)["root"].get("children") or [{}])[0]
v = hit.get("fields", {}).get("matchfeatures", {}).get(feature)
def nonzero(x):
    if isinstance(x, dict):
        return any(nonzero(c) for c in (x.get("values") or x.get("cells") or x.get("blocks") or {}).__iter__()) if x else False
    if isinstance(x, list):
        return any(nonzero(c) for c in x)
    return bool(x)
sys.exit(0 if nonzero(v) else 1)' "$feature" 2>/dev/null
}

# The document count only when the index reports full coverage (a search
# node still loading answers with a partial count); 0 otherwise.
count_docs_full() {
  curl -fs 'http://localhost:8080/search/?yql=select%20*%20from%20product%20where%20true&hits=0' 2>/dev/null \
    | python3 -c 'import sys, json; r = json.load(sys.stdin)["root"]; print(r["fields"]["totalCount"] if r.get("coverage", {}).get("full") else 0)' 2>/dev/null || echo 0
}
# The pid of the running search node, from Vespa's own process supervisor.
searchnode_pid() {
  docker exec "$CONTAINER" vespa-sentinel-cmd list 2>/dev/null \
    | sed -n 's/^searchnode state=RUNNING .*pid=\([0-9][0-9]*\).*/\1/p'
}

# How many documents carry a value in a plain string attribute.
count_with_attribute() {
  local yql="select id from product where $1 matches \".\""
  curl -fs -G 'http://localhost:8080/search/' --data-urlencode "yql=$yql" \
    --data-urlencode 'hits=0' 2>/dev/null \
    | python3 -c 'import sys, json; print(json.load(sys.stdin)["root"]["fields"]["totalCount"])' 2>/dev/null || echo 0
}

# Whether any document carries a value in a plain string attribute - a field a
# chapter fills by a partial update after the feed. One regular-expression
# match on the attribute (`matches` is an attribute-only operator): a hit means
# some document has a non-empty value.
has_attribute() {
  local yql="select id from product where $1 matches \".\""
  curl -fs -G 'http://localhost:8080/search/' --data-urlencode "yql=$yql" \
    --data-urlencode 'hits=0' 2>/dev/null \
    | python3 -c 'import sys, json; sys.exit(0 if json.load(sys.stdin)["root"]["fields"]["totalCount"] > 0 else 1)' 2>/dev/null
}

# The document API path (`<namespace>/<doctype>/docid/<user part>`) of the
# first `put` in a build's products file, split by feed.py's own rule.
first_document_path() {
  .venv/bin/python - "$1" <<'PY'
import json, sys
from urllib.parse import quote
from feed import parse_document_id
with open(sys.argv[1]) as fh:
    for line in fh:
        op = json.loads(line)
        if "put" in op:
            ns, doctype, user = parse_document_id(op["put"])
            print(f"{ns}/{doctype}/docid/{quote(user, safe='')}")
            break
PY
}

# ---- read chapter.toml ------------------------------------------------------
read_toml() {
  python3 - "$toml" "$1" <<'PY'
import sys, tomllib
d = tomllib.load(open(sys.argv[1], "rb"))
node = d
for key in sys.argv[2].split("."):
    node = node.get(key, {}) if isinstance(node, dict) else {}
if isinstance(node, list): print("\n".join(str(x) for x in node))
elif node not in ({}, None): print(node)
PY
}
preset=$(read_toml chapter.corpus_preset)
groups=$(read_toml requirements.groups)
# The test framework is a group like the others, installed from its own lock
# file, but no chapter declares it: it is asked for on the command line.
if [ "$with_tests" = 1 ]; then groups="$groups tests"; fi
feed_cmd=$(read_toml bootstrap.feed)
want_docs=$(read_toml bootstrap.documents)
want_field=$(read_toml bootstrap.requires_field)
probe_profile=$(read_toml bootstrap.probe_profile)
probe_feature=$(read_toml bootstrap.probe_feature)
probe_params=$(read_toml bootstrap.probe_params)
# one query parameter per line, kept whole (they contain spaces and quotes)
probe_args=()
while IFS= read -r line; do [ -n "$line" ] && probe_args+=("$line"); done <<< "$probe_params"
models=$(read_toml bootstrap.models)
update_cmd=$(read_toml bootstrap.update)
update_field=$(read_toml bootstrap.update_field)
[ -n "$preset" ] || { echo "$toml has no chapter.corpus_preset" >&2; exit 1; }
[ -n "$want_docs" ] || { echo "$toml has no bootstrap.documents" >&2; exit 1; }

# ---- 1. venv ----------------------------------------------------------------
say "1/5 venv"
if [ "$fresh" = 1 ] && [ -d .venv ]; then do_ "removing .venv (--fresh)"; rm -rf .venv; fi
py=""
for c in python$PYTHON_MINOR python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys; sys.exit(0 if sys.version_info[:2]==tuple(map(int,'$PYTHON_MINOR'.split('.'))) else 1)" 2>/dev/null; then py="$c"; break; fi
done
if [ -x "$HOME/.pyenv/versions/3.11.13/bin/python3.11" ] && [ -z "$py" ]; then py="$HOME/.pyenv/versions/3.11.13/bin/python3.11"; fi
[ -n "$py" ] || { echo "Python $PYTHON_MINOR not found. docs/pins.md says 3.11.13." >&2; exit 1; }
if [ -d .venv ]; then skip ".venv exists ($(.venv/bin/python --version 2>&1))"; else do_ "creating .venv with $py"; "$py" -m venv .venv; fi
for g in $groups; do
  lock="shared/requirements/lock/$g.txt"
  [ -f "$lock" ] || { echo "no $lock — pins are missing for group $g" >&2; exit 1; }
  if .venv/bin/python - "$lock" <<'PY' 2>/dev/null
import sys, importlib.metadata as m
for line in open(sys.argv[1]):
    line=line.strip()
    if not line or line.startswith("#"): continue
    name, ver = line.split("==")
    if m.version(name) != ver: sys.exit(1)
PY
  then skip "group $g already at pinned versions"
  else do_ "pip install -r $lock"; .venv/bin/python -m pip install -q -r "$lock"; fi
done
site=$(.venv/bin/python -c 'import site; print(site.getsitepackages()[0])')
echo "$root/shared/tools" > "$site/book_shared_tools.pth"

# ---- 2. corpus --------------------------------------------------------------
say "2/5 corpus (preset $preset)"
build_dir=$(ls -d builds/esci-*-"$preset"-s42-kdd-v* 2>/dev/null | head -1 || true)
verify_out=""
if [ -n "$build_dir" ] && verify_out=$(.venv/bin/python shared/tools/corpus.py verify "$build_dir" 2>&1); then
  skip "$build_dir verifies"
else
  # `verify` also compares the document-id format the build was written
  # with against the one corpus.py writes now; an older build is rebuilt
  # into the same directory (the name is what every chapter's commands
  # spell out), and the content hash changes with it.
  if [ -n "$build_dir" ] && printf '%s' "$verify_out" | grep -q '^document-id format'; then
    do_ "$build_dir predates the document-id format of 2026-10-06 (namespace = the locale, user part = the bare ASIN); rebuilding it in place"
  elif [ -n "$build_dir" ]; then
    do_ "$build_dir does not verify; rebuilding it in place. corpus.py verify said:"
    printf '%s\n' "$verify_out" | sed 's/^/         /'
  fi
  if [ -d shared/cache ] && [ -f shared/cache/products_us.parquet ]; then do_ "corpus.py build --preset $preset (from cache, under a minute)";
  else do_ "corpus.py build --preset $preset (first time: streams the dataset, about a quarter of an hour)"; fi
  .venv/bin/python shared/tools/corpus.py build --preset "$preset" --seed 42 --gains kdd
  build_dir=$(ls -d builds/esci-*-"$preset"-s42-kdd-v* | head -1)
fi

# ---- 3. container -----------------------------------------------------------
say "3/5 container ($CONTAINER, $VESPA_IMAGE)"
if [ "$fresh" = 1 ] && docker inspect "$CONTAINER" >/dev/null 2>&1; then do_ "removing $CONTAINER (--fresh)"; docker rm -f "$CONTAINER" >/dev/null; fi
if docker inspect "$CONTAINER" >/dev/null 2>&1; then
  running_image=$(docker inspect -f '{{.Config.Image}}' "$CONTAINER")
  if [ "$running_image" != "$VESPA_IMAGE" ]; then
    echo "   $CONTAINER runs $running_image, not $VESPA_IMAGE. Run with --fresh to replace it." >&2; exit 1
  fi
  if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER")" = "true" ]; then skip "$CONTAINER is running"; else do_ "starting $CONTAINER"; docker start "$CONTAINER" >/dev/null; fi
else
  do_ "docker run $VESPA_IMAGE"
  docker run -d --name "$CONTAINER" -p 19071:19071 -p 8080:8080 "$VESPA_IMAGE" >/dev/null
fi
vespa config set target local >/dev/null 2>&1 || true
printf '   wait  config server'
for _ in $(seq 1 120); do
  if curl -fs http://localhost:19071/state/v1/health 2>/dev/null | grep -q '"up"'; then echo " up"; break; fi
  printf '.'; sleep 2
done

# ---- 4. app -----------------------------------------------------------------
say "4/5 application (chapters/$chapter/app)"
for m in $models; do
  do_ "models.py fetch --model $m --into chapters/$chapter/app/models  (pinned url, verified by sha256; skipped when already there)"
  .venv/bin/python shared/tools/models.py fetch --model "$m" --into "chapters/$chapter/app/models" 2>&1 | sed 's/^/   /'
done
do_ "vespa deploy --wait 300 chapters/$chapter/app"
docs_before_deploy=$(count_docs)
deploy_out=$(vespa deploy --wait 300 "chapters/$chapter/app" 2>&1)
printf '%s\n' "$deploy_out" | sed 's/^/   /'
# The CLI exits 0 when the config server refuses the package (a 400 with "Invalid application"), so the
# answer's text is the only signal; without this the script went on to feed a package that was never deployed.
if printf '%s' "$deploy_out" | grep -q '^Error:\|Invalid application'; then
  echo "   the deploy was refused (see Vespa's answer above); nothing after this step ran. A container built under an" >&2
  echo "   earlier version of this chapter's package may need ./bootstrap.sh $chapter --fresh." >&2
  exit 1
fi
if printf '%s' "$deploy_out" | grep -q 'require restart'; then
  # Vespa applied the package but an attribute setting only takes effect in a
  # restarted search node (the message names the field). Restart it and wait
  # until the index answers with every document it had before.
  do_ "vespa-sentinel-cmd restart searchnode  (the deploy said the change requires it)"
  old_pid=$(searchnode_pid)
  docker exec "$CONTAINER" vespa-sentinel-cmd restart searchnode 2>&1 | sed 's/^/   /'
  # The old process keeps answering queries while it shuts down, so the
  # document count alone cannot tell old from new. First wait for a new
  # search-node process, then for that process to answer with every document
  # the index held before the deploy, twice in a row.
  for _ in $(seq 1 150); do
    new_pid=$(searchnode_pid)
    [ -n "$new_pid" ] && [ "$new_pid" != "$old_pid" ] && break
    sleep 2
  done
  stable=0
  for _ in $(seq 1 300); do
    n=$(count_docs_full)
    if [ "$n" -ge "$docs_before_deploy" ] && [ "$n" -gt 0 ]; then stable=$((stable + 1)); else stable=0; fi
    if [ "$stable" -ge 2 ]; then echo "   search node back (process $old_pid -> $new_pid) with $n documents"; break; fi
    sleep 2
  done
fi

# ---- 5. documents -----------------------------------------------------------
say "5/5 documents (want $want_docs${want_field:+, carrying $want_field})"
have=$(count_docs)
# When the index already holds documents, ask the document API for one of
# them by id - the first `put` in the build file, split into namespace /
# document type / user part the way feed.py splits it. A 404 means these
# documents were fed under an older id format: feeding on top would leave
# them beside the new ones, so the script refuses and asks for --fresh.
if [ "$have" -gt 0 ]; then
  probe_path=$(first_document_path "$build_dir/products.jsonl")
  probe_code=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:8080/document/v1/$probe_path" 2>/dev/null)
  if [ "$probe_code" = "404" ]; then
    echo "   the index holds $have documents, but the build's first document ($probe_path) is not among them:" >&2
    echo "   they were fed under an older document-id format. Run ./bootstrap.sh $chapter --fresh to replace the container;" >&2
    echo "   feeding on top would leave the old documents beside the new ones." >&2
    exit 1
  fi
  echo "   probe $probe_path answers $probe_code"
fi
reason=""
if [ "$have" -lt "$want_docs" ]; then
  reason="$have of $want_docs documents"
elif [ -n "$want_field" ] && [ -n "$probe_profile" ]; then
  if ! has_feature "$probe_profile" "$probe_feature" ${probe_args[@]+"${probe_args[@]}"}; then
    reason="$have documents, none carrying $want_field yet (match-feature $probe_feature under $probe_profile is zero)"
  fi
elif [ -n "$want_field" ] && ! has_field "$want_field"; then
  reason="$have documents, none carrying $want_field yet"
fi
if [ -z "$reason" ]; then
  skip "$have documents in the index${want_field:+, $want_field present}"
else
  [ -n "$feed_cmd" ] || { echo "$toml has no bootstrap.feed and the index holds $reason" >&2; exit 1; }
  do_ "$feed_cmd  ($reason)"
  eval "$feed_cmd"
fi
if [ -n "$update_field" ]; then
  if has_attribute "$update_field"; then
    skip "$update_field carries values"
  else
    [ -n "$update_cmd" ] || { echo "$toml names bootstrap.update_field but no bootstrap.update" >&2; exit 1; }
    do_ "$update_cmd  (no document carries $update_field yet)"
    eval "$update_cmd"
    # A value a partial update gave a document lives only until that document
    # is fed again whole (a put replaces the whole document). Count the
    # documents that carry the field; if any are missing, send the update once
    # more and count again.
    have_field=$(count_with_attribute "$update_field")
    if [ "$have_field" -lt "$want_docs" ]; then
      do_ "$update_cmd  (second pass: $((want_docs - have_field)) of $want_docs documents did not take the update)"
      eval "$update_cmd"
      have_field=$(count_with_attribute "$update_field")
    fi
    if [ "$have_field" -lt "$want_docs" ]; then
      echo "   $update_field is set on $have_field of $want_docs documents after two passes" >&2; exit 1
    fi
    echo "   $update_field set on $have_field documents"
  fi
fi

# ---- state ------------------------------------------------------------------
say "at the start of $chapter"
echo "   build      $build_dir"
echo "   image      $VESPA_IMAGE"
docs_now=$(count_docs)
embedders_now=$(.venv/bin/python shared/tools/deployed.py 2>/dev/null | tr '\n' ' ')
echo "   documents  $docs_now"
echo "   embedders  $embedders_now"
