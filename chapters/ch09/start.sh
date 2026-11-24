#!/usr/bin/env bash
# Bring a machine to the start of chapter 9: the products and the
# application package through the shared bootstrap, then this chapter's own
# state - the user documents - which no earlier chapter has.
#
#   chapters/ch09/start.sh            continue from wherever the container is
#   chapters/ch09/start.sh --fresh    throw the venv and the container away first
#
# The user side runs in four commands: derive the users from the training
# judgements, feed them as empty documents, derive the event stream, and
# apply it one partial update at a time - the same path a live system's
# events would take. A user counts as filled once at least one event has
# reached it. When the container already holds every user and every one is
# filled, the four commands are skipped; when either count is short the
# whole chain runs again from the feed, which puts every profile back to
# empty first, so a run that stopped halfway leaves nothing a rerun would
# double.
set -euo pipefail
cd "$(dirname "$0")/../.."

# `--help` prints the header above and stops here; otherwise the shared
# bootstrap would print its own help, return, and the user chain would run.
for arg in "$@"; do case "$arg" in -h|--help) sed -e '1d' -e '/^[^#]/,$d' -e 's/^# \{0,1\}//' "$0"; exit 0 ;; esac; done

BUILD=builds/esci-us-hard-book-s42-kdd-v4
WANT_USERS=4210
READY="events_applied > 0"

./bootstrap.sh ch09 "$@"

say()  { printf '\n== %s\n' "$*"; }
skip() { printf '   skip  %s\n' "$*"; }
do_()  { printf '   do    %s\n' "$*"; }
# The default query profile names the product schema's rank profile, which
# the user schema does not have; counting user documents therefore asks for
# Vespa's built-in `unranked` profile, and a query that still answers with
# an error counts as zero rather than as a silent number.
count_users() {
  curl -fs -G 'http://localhost:8080/search/' --data-urlencode "yql=select * from user where ${1:-true}" \
    --data-urlencode 'ranking.profile=unranked' --data-urlencode 'hits=0' 2>/dev/null \
    | python3 -c 'import sys, json; r = json.load(sys.stdin)["root"]; print(0 if r.get("errors") else r["fields"]["totalCount"])' 2>/dev/null || echo 0
}

say "users (want $WANT_USERS, filled: $READY)"
have=$(count_users); filled=$(count_users "$READY")
if [ "$have" -ge "$WANT_USERS" ] && [ "$filled" -ge "$WANT_USERS" ]; then
  skip "$have user documents, $filled filled"
else
  do_ "derive users, feed them empty, derive events, apply events  ($have of $WANT_USERS user documents, $filled filled)"
  .venv/bin/python chapters/ch09/derive_users.py --split train --out chapters/ch09/expected/users.json
  .venv/bin/python shared/tools/feed.py "$BUILD/users.jsonl" --out chapters/ch09/expected/feed-users.json
  .venv/bin/python chapters/ch09/derive_events.py --split train --out chapters/ch09/expected/events.json
  .venv/bin/python chapters/ch09/profile_updater.py --split train --out chapters/ch09/expected/profile-updates.json
  have=$(count_users); filled=$(count_users "$READY")
  if [ "$have" -lt "$WANT_USERS" ] || [ "$filled" -lt "$WANT_USERS" ]; then
    echo "   users: $have documents, $filled filled, wanted $WANT_USERS" >&2; exit 1
  fi
fi

say "at the start of ch09 (users)"
echo "   users      $have ($filled filled)"
