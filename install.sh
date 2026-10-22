#!/usr/bin/env bash
# Sync skills from this repo into ~/.claude/skills so Claude Code picks
# them up in any project.
#
#   ./install.sh                 core skills only (skills/)
#   ./install.sh video mobile    core + the named packs (packs/<name>/skills/)
#   ./install.sh all             core + every pack
#
# Packs can also come from CLAUDE_SKILL_PACKS="video mobile". Safe to
# re-run: skills this script installed earlier but that are no longer
# selected (or no longer exist here) are removed; skills it never
# installed are left alone.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dest="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
manifest="$dest/.claude-skills-installed"
mkdir -p "$dest"

packs=("$@")
if [ ${#packs[@]} -eq 0 ] && [ -n "${CLAUDE_SKILL_PACKS:-}" ]; then
  read -r -a packs <<< "$CLAUDE_SKILL_PACKS"
fi
if [ "${packs[*]:-}" = "all" ]; then
  packs=()
  for p in "$root"/packs/*/; do packs+=("$(basename "$p")"); done
fi

sources=("$root/skills")
for p in ${packs[@]+"${packs[@]}"}; do
  if [ ! -d "$root/packs/$p/skills" ]; then
    echo "unknown pack: $p (available: $(ls "$root/packs" | tr '\n' ' '))" >&2
    exit 1
  fi
  sources+=("$root/packs/$p/skills")
done

installed=()
for src in "${sources[@]}"; do
  for dir in "$src"/*/; do
    name="$(basename "$dir")"
    rm -rf "${dest:?}/$name"
    cp -R "$dir" "$dest/$name"
    installed+=("$name")
    echo "installed $name"
  done
done

if [ -f "$manifest" ]; then
  while IFS= read -r old; do
    [ -n "$old" ] || continue
    if ! printf '%s\n' "${installed[@]}" | grep -qxF "$old"; then
      rm -rf "${dest:?}/$old"
      echo "removed $old"
    fi
  done < "$manifest"
fi
printf '%s\n' "${installed[@]}" > "$manifest"
