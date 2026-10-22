#!/usr/bin/env bash
# Sync every skill from this repo into ~/.claude/skills so Claude Code
# picks them up in any project. Safe to re-run; only touches skills
# that exist in this repo.
set -euo pipefail

src="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skills"
dest="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
mkdir -p "$dest"

for dir in "$src"/*/; do
  name="$(basename "$dir")"
  rm -rf "${dest:?}/$name"
  cp -R "$dir" "$dest/$name"
  echo "installed $name"
done
