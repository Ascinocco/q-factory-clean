#!/usr/bin/env bash
# One definition of a Claude Code tmux session, for terminals (the `claude-tmux`
# alias) and for Chadmux over SSH. Install with scripts/install-claude-tmux.sh.
#
#   claude-tmux                             list running sessions and how to start or join one
#   claude-tmux new [claude args...]        start a fresh session (auto-numbered name)
#   claude-tmux new NAME [claude args...]   start a fresh session called NAME
#   claude-tmux connect NAME                reattach to an existing session called NAME
#
# Sessions are found by name only when you give one: there is no per-folder
# "home" session, so renaming a session never changes what any command does.
#
# Machine-friendly subcommands (no terminal needed; used by Chadmux over SSH):
#
#   claude-tmux create NAME --dir FOLDER
#       Start a detached session called NAME in FOLDER running claude.
#   claude-tmux close NAME [--id SESSION_ID] [--instance PID:CREATED]
#       Kill a session. With --id it is found by id (NAME is informational, so a
#       session renamed elsewhere is still found); without, by exact NAME.
#       Refuses if it is no longer that session (replaced).
#   claude-tmux rename OLD NEW [--id SESSION_ID [--instance PID:CREATED]]
#       Rename a session to NEW (ASCII letters, digits, - and _, 1-64 characters,
#       not starting with -). With --id it is found by id (as Chadmux does);
#       without, by exact name OLD, for renaming by hand. Attached clients stay
#       attached.
#
# Each prints exactly one JSON line on stdout and exits with one of the codes
# below; the human-readable message is also written to stderr.
set -euo pipefail

EXIT_USAGE=2
EXIT_NAME_TAKEN=3
EXIT_FOLDER_MISSING=4
EXIT_CLAUDE_MISSING=5
EXIT_TMUX_MISSING=6
EXIT_NOT_FOUND=7
EXIT_REPLACED=8
EXIT_TMUX_FAILED=9

# tmux rejects '.' and ':' in session names; keep names to a safe charset.
sanitize() {
  printf '%s' "$1" | tr -c 'a-zA-Z0-9_-' '-'
}

json_string() {
  local s=$1
  s=${s//\\/\\\\}
  s=${s//\"/\\\"}
  s=${s//$'\n'/\\n}
  s=${s//$'\r'/\\r}
  s=${s//$'\t'/\\t}
  # Any remaining control bytes would make the line invalid JSON.
  printf '"%s"' "$(printf '%s' "$s" | LC_ALL=C tr -d '\000-\037')"
}

# fail CODE ERROR MESSAGE: report a machine-readable failure and exit.
fail() {
  local code=$1 error=$2 message=$3
  echo "$message" >&2
  printf '{"ok":false,"error":%s,"message":%s}\n' "$(json_string "$error")" "$(json_string "$message")"
  exit "$code"
}

# Resolve a leading ~ the way an interactive shell would; the value arrives quoted.
expand_dir() {
  case "$1" in
    "~") printf '%s' "$HOME" ;;
    "~/"*) printf '%s/%s' "$HOME" "${1#"~/"}" ;;
    *) printf '%s' "$1" ;;
  esac
}

# Print the id of the session named exactly $1 (no tmux name-pattern matching).
# -u: without a UTF-8 locale (typical over SSH) tmux prints the tab and any
# non-ASCII name characters as '_', and no name would ever match.
session_id_for() {
  local name id
  while IFS=$'\t' read -r id name; do
    if [ "$name" = "$1" ]; then printf '%s' "$id"; return 0; fi
  done < <(tmux -u list-sessions -F $'#{session_id}\t#{session_name}' 2>/dev/null || true)
  return 1
}

# Bring a q-factory clone up to date BEFORE claude starts in it, so the new
# session loads the current CLAUDE.md, settings and skills. The SessionStart
# hook runs the same script, but only after Claude Code has read those, so on
# its own a pull takes effect one session late. A folder anywhere inside a
# q-factory checkout counts (its top level has q-factory.toml and the script);
# any other folder is left alone. Output goes to stderr, keeping `create`'s
# stdout to its one JSON line, and a sync problem never stops the launch.
# (A fast-forward may replace this very script; git writes a new file rather
# than editing it in place, so the copy running now is unaffected.)
presync() {
  local top
  top="$(git -C "$1" rev-parse --show-toplevel 2>/dev/null)" || return 0
  [ -f "$top/q-factory.toml" ] && [ -x "$top/scripts/session-sync.sh" ] || return 0
  CLAUDE_PROJECT_DIR="$top" "$top/scripts/session-sync.sh" >&2 || true
}

create_session() {
  local name="" dir=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --dir)
        [ $# -ge 2 ] || fail $EXIT_USAGE usage "usage: claude-tmux create NAME --dir FOLDER"
        dir=$2; shift 2 ;;
      *)
        [ -z "$name" ] || fail $EXIT_USAGE usage "usage: claude-tmux create NAME --dir FOLDER"
        name=$1; shift ;;
    esac
  done
  [ -n "$name" ] && [ -n "$dir" ] || fail $EXIT_USAGE usage "usage: claude-tmux create NAME --dir FOLDER"
  command -v tmux >/dev/null 2>&1 || fail $EXIT_TMUX_MISSING tmux_missing "claude-tmux: tmux is not installed (brew install tmux)"
  command -v claude >/dev/null 2>&1 || fail $EXIT_CLAUDE_MISSING claude_missing "claude-tmux: claude CLI not found on PATH"

  local session_name
  session_name="$(sanitize "$name")"
  local folder
  folder="$(expand_dir "$dir")"
  [ -d "$folder" ] || fail $EXIT_FOLDER_MISSING folder_missing "claude-tmux: folder '$dir' does not exist"
  folder="$(cd "$folder" && pwd)"
  if tmux has-session -t "=$session_name" 2>/dev/null; then
    fail $EXIT_NAME_TAKEN name_taken "claude-tmux: session '$session_name' already exists"
  fi
  presync "$folder"
  local id
  if ! id="$(tmux new-session -d -P -F '#{session_id}' -s "$session_name" -c "$folder" claude 2>&1)"; then
    # Lost a race with another creator of the same name.
    if tmux has-session -t "=$session_name" 2>/dev/null; then
      fail $EXIT_NAME_TAKEN name_taken "claude-tmux: session '$session_name' already exists"
    fi
    fail $EXIT_TMUX_FAILED tmux_failed "claude-tmux: tmux could not create '$session_name': $id"
  fi
  printf '{"ok":true,"name":%s,"id":%s,"dir":%s}\n' "$(json_string "$session_name")" "$(json_string "$id")" "$(json_string "$folder")"
}

# The name a session id currently has, or nothing if there is no such session.
name_for_id() {
  local id name
  while IFS=$'\t' read -r id name; do
    if [ "$id" = "$1" ]; then printf '%s' "$name"; return 0; fi
  done < <(tmux -u list-sessions -F $'#{session_id}\t#{session_name}' 2>/dev/null || true)
  return 1
}

# resolve_id NAME ID VERB: continue if that session exists. Otherwise, a session
# still called NAME means it was replaced; nothing means it is gone. (Not called
# in $(...): its failure JSON must reach stdout.)
resolve_id() {
  local name=$1 id=$2 verb=$3
  if name_for_id "$id" >/dev/null; then return 0; fi
  if session_id_for "$name" >/dev/null; then
    fail $EXIT_REPLACED replaced "claude-tmux: session '$name' was replaced; refusing to $verb it"
  fi
  fail $EXIT_NOT_FOUND not_found "claude-tmux: no session named '$name'"
}

# check_instance ID PID:CREATED NAME VERB: refuse if a restarted server reused the id.
check_instance() {
  local instance
  instance="$(tmux display-message -p -t "$1" '#{pid}:#{session_created}' 2>/dev/null || true)"
  [ "$instance" = "$2" ] || fail $EXIT_REPLACED replaced "claude-tmux: session '$3' was replaced; refusing to $4 it"
}

# The characters are spelled out, not ranges: a range like [A-Za-z] follows the
# locale's collation, and under en_US.UTF-8 on glibc it matches 'ï' and 'é'.
valid_new_name() {
  case "$1" in
    "" | -* | *[!ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-]*) return 1 ;;
  esac
  [ ${#1} -le 64 ]
}

rename_session() {
  local old="" new="" expected_id="" expected_instance="" names=0
  local usage="usage: claude-tmux rename OLD NEW [--id SESSION_ID [--instance PID:CREATED]]"
  while [ $# -gt 0 ]; do
    case "$1" in
      --id)
        [ $# -ge 2 ] || fail $EXIT_USAGE usage "$usage"
        expected_id=$2; shift 2 ;;
      --instance)
        [ $# -ge 2 ] || fail $EXIT_USAGE usage "$usage"
        expected_instance=$2; shift 2 ;;
      *)
        case $names in
          0) old=$1 ;;
          1) new=$1 ;;
          *) fail $EXIT_USAGE usage "$usage" ;;
        esac
        names=$((names + 1)); shift ;;
    esac
  done
  [ "$names" -eq 2 ] && [ -n "$old" ] || fail $EXIT_USAGE usage "$usage"
  [ -n "$expected_id" ] || [ -z "$expected_instance" ] || fail $EXIT_USAGE usage "$usage"  # --instance needs --id
  valid_new_name "$new" || fail $EXIT_USAGE invalid_name "claude-tmux: '$new' is not a valid session name (ASCII letters, digits, - and _, up to 64, not starting with -)"
  command -v tmux >/dev/null 2>&1 || fail $EXIT_TMUX_MISSING tmux_missing "claude-tmux: tmux is not installed (brew install tmux)"

  local id current
  # By id (Chadmux), or by exact name when typed at a terminal.
  if [ -n "$expected_id" ]; then
    resolve_id "$old" "$expected_id" rename; id=$expected_id
  else
    id="$(session_id_for "$old")" || fail $EXIT_NOT_FOUND not_found "claude-tmux: no session named '$old'"
  fi
  [ -z "$expected_instance" ] || check_instance "$id" "$expected_instance" "$old" rename
  current="$(name_for_id "$id")"
  if [ "$current" != "$new" ]; then
    if session_id_for "$new" >/dev/null; then
      fail $EXIT_NAME_TAKEN name_taken "claude-tmux: session '$new' already exists"
    fi
    local output
    if ! output="$(tmux rename-session -t "$id" "$new" 2>&1)"; then
      if session_id_for "$new" >/dev/null; then  # lost a race with another rename or create
        fail $EXIT_NAME_TAKEN name_taken "claude-tmux: session '$new' already exists"
      fi
      fail $EXIT_TMUX_FAILED tmux_failed "claude-tmux: tmux could not rename '$current': $output"
    fi
  fi
  printf '{"ok":true,"old":%s,"name":%s,"id":%s}\n' "$(json_string "$current")" "$(json_string "$new")" "$(json_string "$id")"
}

close_session() {
  local name="" expected_id="" expected_instance="" have_name=0
  local usage="usage: claude-tmux close NAME [--id SESSION_ID] [--instance PID:CREATED]"
  while [ $# -gt 0 ]; do
    case "$1" in
      --id)
        [ $# -ge 2 ] || fail $EXIT_USAGE usage "$usage"
        expected_id=$2; shift 2 ;;
      --instance)
        [ $# -ge 2 ] || fail $EXIT_USAGE usage "$usage"
        expected_instance=$2; shift 2 ;;
      *)
        [ "$have_name" -eq 0 ] || fail $EXIT_USAGE usage "$usage"
        name=$1; have_name=1; shift ;;
    esac
  done
  [ -n "$name" ] || fail $EXIT_USAGE usage "$usage"
  command -v tmux >/dev/null 2>&1 || fail $EXIT_TMUX_MISSING tmux_missing "claude-tmux: tmux is not installed (brew install tmux)"

  # With --id the session is found by id, so one renamed elsewhere still closes;
  # without, by exact name (any tmux session, not only claude-tmux ones).
  local id
  if [ -n "$expected_id" ]; then
    resolve_id "$name" "$expected_id" close; id=$expected_id
  else
    id="$(session_id_for "$name")" || fail $EXIT_NOT_FOUND not_found "claude-tmux: no session named '$name'"
  fi
  [ -z "$expected_instance" ] || check_instance "$id" "$expected_instance" "$name" close
  local output
  if ! output="$(tmux kill-session -t "$id" 2>&1)"; then
    fail $EXIT_TMUX_FAILED tmux_failed "claude-tmux: tmux could not close '$name': $output"
  fi
  printf '{"ok":true,"name":%s,"id":%s}\n' "$(json_string "$name")" "$(json_string "$id")"
}

case "${1:-}" in
  create) shift; create_session "$@"; exit 0 ;;
  close) shift; close_session "$@"; exit 0 ;;
  rename) shift; rename_session "$@"; exit 0 ;;
esac

if ! command -v tmux >/dev/null 2>&1; then
  echo "claude-tmux: tmux is not installed (brew install tmux)" >&2
  exit 1
fi

if [ "${1:-}" = "connect" ]; then
  if [ $# -ne 2 ]; then
    echo "usage: claude-tmux connect NAME" >&2
    exit 1
  fi
  session_name="$(sanitize "$2")"
  if ! tmux has-session -t "=$session_name" 2>/dev/null; then
    echo "claude-tmux: no session named '$session_name'" >&2
    tmux list-sessions -F '  #{session_name}' 2>/dev/null >&2 || true
    exit 1
  fi
  if [ -n "${TMUX:-}" ]; then
    exec tmux switch-client -t "=$session_name"
  fi
  exec tmux attach-session -t "=$session_name"
fi

usage_text() {
  cat <<'USAGE'
  claude-tmux new NAME [claude args...]   start a Claude session called NAME
  claude-tmux new [claude args...]        start one with an automatic name
  claude-tmux connect NAME                reattach to a session
USAGE
}

# Plain `claude-tmux`: show what is running and how to start or join; no side effects.
if [ "${1:-}" != "new" ]; then
  if [ $# -gt 0 ]; then
    echo "claude-tmux: unknown command '$1'" >&2
    usage_text >&2
    exit $EXIT_USAGE
  fi
  sessions="$(tmux -u list-sessions -F $'#{session_name}\t#{pane_current_path}\t#{session_attached}' 2>/dev/null || true)"
  if [ -z "$sessions" ]; then
    echo "No tmux sessions running."
  else
    echo "Running sessions:"
    while IFS=$'\t' read -r name path attached; do
      # Not ${path/#$HOME/~}: bash 5.2+ tilde-expands that '~' back into $HOME,
      # and bash 3.2 also turns a sibling such as $HOME-old into ~-old.
      case "$path" in
        "$HOME") path="~" ;;
        "$HOME"/*) path="~${path#"$HOME"}" ;;
      esac
      printf '  %-28s %s%s\n' "$name" "$path" "$([ "${attached:-0}" -gt 0 ] && echo '  (attached)')"
    done <<<"$sessions"
  fi
  echo
  usage_text
  exit 0
fi

# Only `new` starts Claude; listing and connect work without it.
if ! command -v claude >/dev/null 2>&1; then
  echo "claude-tmux: claude CLI not found on PATH" >&2
  exit 1
fi

shift
session_name=""
# A second argument is the session name unless it looks like a claude flag.
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then
  session_name="$(sanitize "$1")"
  shift
  if tmux has-session -t "=$session_name" 2>/dev/null; then
    echo "claude-tmux: session '$session_name' already exists (attach with: claude-tmux connect $session_name)" >&2
    exit 1
  fi
fi

# Automatic names are numbered per folder. (The trailing '-' from basename's
# newline is long-standing and kept, so names look as they always have.)
base_name="claude-$(basename "$PWD" | tr -c 'a-zA-Z0-9_-' '-')"

# `new` without a name: first free base, base2, base3, ...
if [ -z "$session_name" ]; then
  session_name="$base_name"
  n=2
  while tmux has-session -t "=$session_name" 2>/dev/null; do
    session_name="${base_name}${n}"
    n=$((n + 1))
  done
fi

presync "$PWD"

if [ -n "${TMUX:-}" ]; then
  # Can't nest sessions from inside tmux: create it detached and switch to it.
  tmux new-session -d -s "$session_name" -c "$PWD" claude "$@"
  exec tmux switch-client -t "=$session_name"
fi

exec tmux new-session -s "$session_name" -c "$PWD" claude "$@"
