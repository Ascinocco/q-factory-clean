#!/usr/bin/env bash
# q-factory SessionStart sync: keep this checkout current with origin/main.
#
# Runs from the SessionStart hook in .claude/settings.json at every session
# start. It only ever FAST-FORWARDS `main`. Anything else is a skip with a
# one-line reason (printed to stdout, which Claude Code adds to the session's
# context), never a merge, rebase, stash, reset or discard:
#   - not on `main`, a detached HEAD, or uncommitted tracked changes;
#   - offline or the fetch failed;
#   - local commits not on origin/main (diverged or ahead);
#   - the fast-forward itself refused (an untracked file in the way, or a
#     lock held by another git process).
# Where git said why, its first error line is appended (URL credentials
# stripped), still on the one line.
# Project submodules under projects/ are deliberately NOT updated, even with
# submodule.recurse=true: they are pinned, and another session may be
# working inside one.
#
# Exit status is always 0 so a sync problem never blocks a session.
set -u

say() { printf 'q-factory sync: %s\n' "$*"; }
# First line of git's stderr, credentials removed, bounded; empty if none.
why() {
  local line
  line="$(printf '%s\n' "$1" | sed -n '/[^[:space:]]/{p;q;}' | sed -E 's#://[^/@[:space:]]*@#://#g' | cut -c1-160)"
  [ -n "$line" ] && printf ': %s' "$line"
}

root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$root" 2>/dev/null || { say "skipped (cannot enter $root)"; exit 0; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { say "skipped (not a git checkout)"; exit 0; }

branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
if [ "$branch" != "main" ]; then
  say "skipped (on ${branch:-a detached HEAD}, not main)"; exit 0
fi
if [ -n "$(git status --porcelain --untracked-files=no --ignore-submodules=all)" ]; then
  say "skipped (uncommitted changes on main; commit or move them to a branch)"; exit 0
fi

export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -o BatchMode=yes -o ConnectTimeout=8}"
if ! err="$(git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=8 fetch --quiet --no-recurse-submodules origin main 2>&1 >/dev/null)"; then
  say "skipped (could not fetch origin; working on $(git rev-parse --short HEAD))$(why "$err")"; exit 0
fi

local_sha="$(git rev-parse HEAD)"
remote_sha="$(git rev-parse FETCH_HEAD)"
if [ "$local_sha" = "$remote_sha" ]; then
  say "up to date ($(git rev-parse --short HEAD))"; exit 0
fi
if git merge-base --is-ancestor "$local_sha" "$remote_sha"; then
  if err="$(git -c submodule.recurse=false merge --ff-only --quiet "$remote_sha" 2>&1 >/dev/null)"; then
    count="$(git rev-list --count "$local_sha..$remote_sha")"
    say "fast-forwarded main by $count commit(s) to $(git rev-parse --short HEAD)"
  else
    say "skipped (fast-forward refused; run 'git merge --ff-only origin/main' to see why)$(why "$err")"
  fi
  exit 0
fi
if git merge-base --is-ancestor "$remote_sha" "$local_sha"; then
  say "skipped (main has local commits not on origin; push them)"
else
  say "skipped (main has diverged from origin; resolve by hand)"
fi
exit 0
