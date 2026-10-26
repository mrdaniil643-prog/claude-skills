#!/usr/bin/env bash
# Connect Claude Code to Adobe Premiere Pro and Photoshop on macOS.
#
#   setup-mac.sh                 both apps
#   setup-mac.sh premiere        Premiere only
#   setup-mac.sh photoshop       Photoshop only
#
# Premiere: premiere-pro-mcp (npm, CEP connector).
# Photoshop: mikechambers/adb-mcp (Python MCP server + Node proxy + UXP plugin),
# pinned to a reviewed commit and patched so its proxy listens on 127.0.0.1 only.
# Safe to re-run: it updates in place and re-registers the MCP servers.
set -euo pipefail

PREMIERE_MCP_VERSION="1.25.0"
ADB_MCP_COMMIT="afe5d09cdbdd4cc60434dce6b3f46fdafe15a21c"
ROOT="${ADOBE_MCP_HOME:-$HOME/.adobe-mcp}"
target="${1:-all}"

case "$target" in all|premiere|photoshop) ;; *) echo "usage: $0 [all|premiere|photoshop]" >&2; exit 1 ;; esac

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Нет $1. Установи: $2" >&2; exit 1; }
}
need claude "https://code.claude.com/docs (Claude Code CLI)"
need node "brew install node (нужен 20.19+)"
need npm "brew install node"
node -e 'const [a,b]=process.versions.node.split(".").map(Number);process.exit(a>20||(a===20&&b>=19)?0:1)' \
  || { echo "Node $(node -v) слишком старый, нужен 20.19+: brew upgrade node" >&2; exit 1; }

mkdir -p "$ROOT"

if [ "$target" != photoshop ]; then
  echo "== Premiere Pro: premiere-pro-mcp@$PREMIERE_MCP_VERSION"
  npm install -g "premiere-pro-mcp@$PREMIERE_MCP_VERSION"
  premiere-pro-mcp --install-cep
  claude mcp remove -s user premiere-pro >/dev/null 2>&1 || true
  claude mcp add -s user premiere-pro -- premiere-pro-mcp
  premiere-pro-mcp --doctor || echo "(doctor показал замечания: открой Premiere и проверь панель коннектора)"
  command -v ffprobe >/dev/null 2>&1 || echo "Совет: brew install ffmpeg — без ffprobe не работают trim_clip и slip_edit."
fi

if [ "$target" != premiere ]; then
  echo "== Photoshop: adb-mcp @ ${ADB_MCP_COMMIT:0:7}"
  need git "xcode-select --install"
  need uv "curl -LsSf https://astral.sh/uv/install.sh | sh"
  repo="$ROOT/adb-mcp"
  if [ -d "$repo/.git" ]; then
    git -C "$repo" fetch -q origin
  else
    git clone -q https://github.com/mikechambers/adb-mcp "$repo"
  fi
  git -C "$repo" checkout -q -f "$ADB_MCP_COMMIT"

  # Upstream proxy binds every interface without auth; keep it on loopback.
  perl -pi -e 's/server\.listen\(PORT, \(\) =>/server.listen(PORT, "127.0.0.1", () =>/' \
    "$repo/adb-proxy-socket/proxy.js"
  perl -pi -e 's#localhost:3001#127.0.0.1:3001#g' \
    "$repo"/mcp/*.py "$repo"/uxp/ps/main.js "$repo"/uxp/pr/main.js
  grep -q '"127.0.0.1"' "$repo/adb-proxy-socket/proxy.js" \
    || { echo "Не удалось ограничить прокси локальным адресом, остановлено." >&2; exit 1; }

  (cd "$repo/adb-proxy-socket" && npm ci --omit=dev --no-audit --no-fund)
  uv --directory "$repo/mcp" sync -q

  claude mcp remove -s user photoshop >/dev/null 2>&1 || true
  claude mcp add -s user photoshop -- uv --directory "$repo/mcp" run mcp run ps-mcp.py

  cat > "$ROOT/start-photoshop-proxy.command" <<EOF
#!/bin/bash
# Keep this window open while Claude works with Photoshop.
exec node "$repo/adb-proxy-socket/proxy.js"
EOF
  chmod +x "$ROOT/start-photoshop-proxy.command"
fi

cat <<EOF

Готово. Осталось сделать руками (один раз):
EOF
if [ "$target" != photoshop ]; then cat <<EOF
  Premiere: перезапусти Premiere, открой проект, Window > Extensions > MCP for Adobe Premiere Pro.
EOF
fi
if [ "$target" != premiere ]; then cat <<EOF
  Photoshop:
   1. Photoshop > Settings > Plugins > Enable Developer Mode, перезапусти Photoshop.
   2. Creative Cloud > установи и открой UXP Developer Tools.
   3. File > Add Plugin > $repo/uxp/ps/manifest.json, затем Load.
   4. Запусти прокси: двойной клик по $ROOT/start-photoshop-proxy.command
      (или его запустит Claude), в панели Photoshop MCP Agent нажми Connect.
   После перезапуска Photoshop плагин снова загружается кнопкой Load в UXP Developer Tools.
EOF
fi
echo "  Перезапусти Claude Code, чтобы появились инструменты (/mcp покажет статус)."
