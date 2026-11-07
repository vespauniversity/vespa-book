bg_run() {
  if [ "$#" -eq 0 ]; then
    printf 'Usage: bg_run COMMAND [ARGUMENTS...]\n' >&2
    return 2
  fi

  local run_dir
  mkdir -p "$PWD/logs" || return 1
  run_dir="$(mktemp -d "$PWD/logs/bg-XXXXXXXX")" || return 1
  printf 'State: QUEUED\n' > "$run_dir/status.txt"

  nohup bash -c '
    run_dir=$1
    shift
    export PYTHONUNBUFFERED=1
    start=$(date +%s)
    status_file="$run_dir/status.txt"

    finish() {
      code=$?
      elapsed=$(( $(date +%s) - start ))
      {
        date -u "+Finished: %Y-%m-%d %H:%M:%S UTC"
        printf "Exit code: %s\n" "$code"
        printf "Elapsed: %dh %dm %ds\n" \
          "$((elapsed / 3600))" \
          "$(((elapsed % 3600) / 60))" \
          "$((elapsed % 60))"
        if [ "$code" -eq 0 ]; then
          printf "State: COMPLETED\n"
        else
          printf "State: FAILED\n"
        fi
      } >> "$status_file"
    }
    trap finish EXIT
    trap "exit 130" INT
    trap "exit 143" TERM

    {
      date -u "+Started: %Y-%m-%d %H:%M:%S UTC"
      printf "State: RUNNING\nCommand: "
      printf "%q " "$@"
      printf "\n"
    } > "$status_file"

    /usr/bin/time -p "$@"
    exit "$?"
  ' bash "$run_dir" "$@" \
    > "$run_dir/output.log" 2>&1 < /dev/null &

  echo "$!" > "$run_dir/pid"
  printf 'Run folder: %s\n' "$run_dir"
  printf 'Watch:  tail -f "%s/output.log"\n' "$run_dir"
  printf 'Status: cat "%s/status.txt"\n' "$run_dir"
}
