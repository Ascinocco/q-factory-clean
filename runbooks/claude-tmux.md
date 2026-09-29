# claude-tmux: one definition of a Claude tmux session

`scripts/claude-tmux.sh` is the single definition of how a Claude Code tmux
session is made, used both at a terminal (through the `claude-tmux` alias) and by
Chadmux over SSH. Chadmux calls it rather than reimplementing it, so a session
created from the phone is the same as one created at the Mac.

Moved here from an earlier repository: q-factory is
cloned on every machine and kept current by its SessionStart hook, so every
host has the same script and a pushed change reaches the others at their next
session start.

## Install on a host

From the q-factory clone on that host:

```sh
scripts/install-claude-tmux.sh            # or: --rc ~/.bashrc
```

It symlinks `~/.claude/scripts/claude-tmux.sh` to this checkout's script (keeping
any previous regular file as `claude-tmux.sh.bak-<timestamp>`) and adds
`alias claude-tmux="~/.claude/scripts/claude-tmux.sh"` to the login shell's rc
file if missing. Rerunning is safe, and re-points a link that went into
another checkout (an old one). Link from the main checkout, not a task
worktree: the link follows whatever that checkout has checked out. Chadmux runs
the symlinked path directly, so the alias only matters at a terminal.

## Terminal usage

```text
claude-tmux                             list running sessions and how to start or join one
claude-tmux new [NAME] [claude args...] start a fresh session (NAME, or an automatic one)
claude-tmux connect NAME                reattach to an existing session
```

Plain `claude-tmux` has no side effects: it lists each session's name, folder and
whether a client is attached, then prints the commands above. It no longer
reattaches to or creates a per-folder "home" session (dropped
2026-09-25): sessions are named explicitly, so renaming one never changes
what any command does. Extra arguments without `new` are refused (exit 2).
Automatic `new` names are numbered per folder (`claude-<folder>-`, `…-2`, …).
Only `new` needs `claude` on PATH.

## Current before Claude starts

When the folder is inside a q-factory checkout, `new` and `create` run
`scripts/session-sync.sh` first, so the session starts on current `main`. The
SessionStart hook runs the same sync, but only after Claude Code has already
loaded `CLAUDE.md`, settings and skills, so a pull that happens there only
takes effect in the next session. The sync has the same rules as the hook:
fast-forward only, otherwise a one-line skip. Its line goes to stderr, a
problem never stops the launch, and folders outside q-factory are untouched.

## Machine interface (no terminal needed)

```text
claude-tmux create NAME --dir FOLDER
claude-tmux close NAME [--id SESSION_ID] [--instance PID:CREATED]
claude-tmux rename OLD NEW [--id SESSION_ID [--instance PID:CREATED]]
```

`create` starts a detached session running `claude` in FOLDER (a leading `~` is
expanded), with the same name sanitizing and duplicate refusal as `new NAME`.

`close` kills a session. With `--id` it is found **by id** and NAME is only
informational, so a session renamed elsewhere still closes. Without `--id` it
closes the session called exactly NAME (any tmux session).

`rename` renames a session to NEW in place (`tmux rename-session`): with `--id`
the session with that id (Chadmux's rename button uses this), without it the
session called exactly OLD, for renaming by hand (`claude-tmux rename old new`).
Attached clients stay attached and what runs inside keeps running. NEW must be
ASCII letters, digits, `-` and `_` (in any locale), 1–64 characters and not
start with `-`; it is rejected rather than sanitized. Renaming to the current name is a no-op success.

`close` and `rename` refuse a session that is no longer the one identified by
`--id`/`--instance` (another session now has the name, or a restarted server
reused the id). Session ids repeat after a tmux server restart;
`--instance` (`#{pid}:#{session_created}`) does not.

Each prints one JSON line on stdout — `{"ok":true,"name":…,"id":…}` (plus `dir`
for create and `old` for rename) or `{"ok":false,"error":…,"message":…}` — and
writes the message to stderr. Exit codes: 0 ok, 2 usage or invalid name
(`invalid_name`), 3 name taken, 4 folder missing, 5 `claude` not on PATH,
6 tmux missing, 7 no such session, 8 replaced, 9 other tmux failure.

Non-interactive SSH commands skip shell startup files, so callers run the script
through a login shell (`"$SHELL" -lc`) to find `claude`, and prepend Homebrew's
tmux directory. Over SSH there is usually no UTF-8 locale; the script reads
session names with `tmux -u` so tabs and non-ASCII names survive.

## Tests

`tests/test_claude_tmux.py` runs the script against a private tmux server per
test (its own HOME and short `TMUX_TMPDIR`, no inherited `$TMUX`, and an explicit
`-S` socket for teardown) with a fake `claude` that only sleeps; it never lists or
touches personal sessions. For any manual check, use `tmux -S <private socket>`
on every call: `$TMUX` overrides `TMUX_TMPDIR`, and a bare `kill-server` from
inside tmux stops your real server. Chadmux's
`scripts/test-transport.py --claude-tmux PATH` exercises the same script over
real SSH from the iOS Simulator.

Where bash is outside `/usr/bin` and `/bin` (NixOS), the tests' restricted PATH
ends with a copy of the running bash's directory without `claude` and `tmux`, so
the tests alone decide whether those are present. The script must also run
under macOS's bash 3.2: to check that on Linux, build bash 3.2.57 and run the
suite with `CLAUDE_TMUX_TEST_BASH=/path/to/bash`, which puts that bash first on
the scripts' PATH.
