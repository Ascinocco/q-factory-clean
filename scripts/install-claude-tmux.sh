#!/usr/bin/env bash
# Install the versioned claude-tmux on this host:
#   ~/.claude/scripts/claude-tmux.sh -> <this checkout>/scripts/claude-tmux.sh
# and ensure the `claude-tmux` alias exists in the login shell's rc file.
#
#   scripts/install-claude-tmux.sh [--rc FILE]
#
# Chadmux calls ~/.claude/scripts/claude-tmux.sh by absolute path, so that
# symlink (not the alias) is what makes phone-created sessions work.
# An existing regular file is kept as claude-tmux.sh.bak-<timestamp>.
# Rerunning is safe.
set -euo pipefail

source_script="$(cd "$(dirname "$0")" && pwd)/claude-tmux.sh"
target_dir="$HOME/.claude/scripts"
target="$target_dir/claude-tmux.sh"
alias_line='alias claude-tmux="~/.claude/scripts/claude-tmux.sh"'

rc=""
while [ $# -gt 0 ]; do
  case "$1" in
    --rc) rc=$2; shift 2 ;;
    *) echo "usage: install-claude-tmux.sh [--rc FILE]" >&2; exit 2 ;;
  esac
done
if [ -z "$rc" ]; then
  case "$(basename "${SHELL:-/bin/bash}")" in
    zsh) rc="$HOME/.zshrc" ;;
    *) rc="$HOME/.bashrc" ;;
  esac
fi

[ -x "$source_script" ] || { echo "install-claude-tmux: $source_script is missing or not executable" >&2; exit 1; }
mkdir -p "$target_dir"

if [ -L "$target" ] && [ "$(readlink "$target")" = "$source_script" ]; then
  echo "claude-tmux: $target already links to $source_script"
else
  if [ -e "$target" ] && [ ! -L "$target" ]; then
    backup="$target.bak-$(date +%Y%m%d%H%M%S)"
    mv "$target" "$backup"
    echo "claude-tmux: kept the previous script as $backup"
  fi
  ln -sfn "$source_script" "$target"
  echo "claude-tmux: linked $target -> $source_script"
fi

if [ -f "$rc" ] && grep -Eq '^[[:space:]]*alias claude-tmux=' "$rc"; then
  echo "claude-tmux: alias already present in $rc"
else
  printf '\n%s\n' "$alias_line" >> "$rc"
  echo "claude-tmux: added alias to $rc (open a new shell to use it)"
fi
