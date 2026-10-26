# Connect Claude Code to Adobe Premiere Pro and Photoshop on Windows.
#
#   powershell -ExecutionPolicy Bypass -File setup-windows.ps1              both apps
#   powershell -ExecutionPolicy Bypass -File setup-windows.ps1 premiere     Premiere only
#   powershell -ExecutionPolicy Bypass -File setup-windows.ps1 photoshop    Photoshop only
#
# Premiere: premiere-pro-mcp (npm, CEP connector).
# Photoshop: mikechambers/adb-mcp (Python MCP server + Node proxy + UXP plugin),
# pinned to a reviewed commit and patched so its proxy listens on 127.0.0.1 only.
# Safe to re-run: it updates in place and re-registers the MCP servers.
param([ValidateSet('all', 'premiere', 'photoshop')][string]$Target = 'all')
$ErrorActionPreference = 'Stop'

$PremiereMcpVersion = '1.25.0'
$AdbMcpCommit = 'afe5d09cdbdd4cc60434dce6b3f46fdafe15a21c'
$Root = if ($env:ADOBE_MCP_HOME) { $env:ADOBE_MCP_HOME } else { Join-Path $env:USERPROFILE '.adobe-mcp' }

function Need($cmd, $hint) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "Нет $cmd. Установи: $hint" }
}
# Native tools don't throw on failure in Windows PowerShell 5; stop on a non-zero exit.
function Run {
  & $args[0] @($args | Select-Object -Skip 1)
  if ($LASTEXITCODE -ne 0) { throw "Команда завершилась с ошибкой: $($args -join ' ')" }
}
function Replace-InFile($path, $old, $new) {
  $text = [IO.File]::ReadAllText($path)
  [IO.File]::WriteAllText($path, $text.Replace($old, $new))  # UTF-8 without BOM
}

Need claude 'https://code.claude.com/docs (Claude Code CLI)'
Need node 'winget install OpenJS.NodeJS.LTS (нужен 20.19+)'
Need npm 'winget install OpenJS.NodeJS.LTS'
$nodeVersion = [version]((node -v).TrimStart('v'))
if ($nodeVersion -lt [version]'20.19.0') { throw "Node $nodeVersion слишком старый, нужен 20.19+: winget upgrade OpenJS.NodeJS.LTS" }

New-Item -ItemType Directory -Force -Path $Root | Out-Null

if ($Target -ne 'photoshop') {
  Write-Host "== Premiere Pro: premiere-pro-mcp@$PremiereMcpVersion"
  Run npm install -g "premiere-pro-mcp@$PremiereMcpVersion"
  Run premiere-pro-mcp --install-cep
  try { & claude mcp remove -s user premiere-pro *> $null } catch {}  # absent on first run
  # npm puts a .cmd shim on PATH; Claude Code on Windows launches those through cmd /c.
  Run claude mcp add -s user premiere-pro '--' cmd /c premiere-pro-mcp
  & premiere-pro-mcp --doctor
  if ($LASTEXITCODE -ne 0) { Write-Host '(doctor показал замечания: открой Premiere и проверь панель коннектора)' }
  if (-not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    Write-Host 'Совет: winget install Gyan.FFmpeg — без ffprobe не работают trim_clip и slip_edit.'
  }
}

if ($Target -ne 'premiere') {
  Write-Host "== Photoshop: adb-mcp @ $($AdbMcpCommit.Substring(0, 7))"
  Need git 'winget install Git.Git'
  Need uv 'winget install astral-sh.uv'
  $repo = Join-Path $Root 'adb-mcp'
  if (Test-Path (Join-Path $repo '.git')) {
    Run git -C $repo fetch -q origin
  } else {
    Run git clone -q https://github.com/mikechambers/adb-mcp $repo
  }
  Run git -C $repo checkout -q -f $AdbMcpCommit

  # Upstream proxy binds every interface without auth; keep it on loopback.
  $proxy = Join-Path $repo 'adb-proxy-socket\proxy.js'
  Replace-InFile $proxy 'server.listen(PORT, () =>' 'server.listen(PORT, "127.0.0.1", () =>'
  $clients = @(Get-ChildItem (Join-Path $repo 'mcp\*.py')).FullName +
    (Join-Path $repo 'uxp\ps\main.js') + (Join-Path $repo 'uxp\pr\main.js')
  foreach ($f in $clients) { Replace-InFile $f 'localhost:3001' '127.0.0.1:3001' }
  if (-not (Select-String -Path $proxy -SimpleMatch '"127.0.0.1"' -Quiet)) {
    throw 'Не удалось ограничить прокси локальным адресом, остановлено.'
  }

  Push-Location (Join-Path $repo 'adb-proxy-socket')
  try { Run npm ci --omit=dev --no-audit --no-fund } finally { Pop-Location }
  Run uv --directory (Join-Path $repo 'mcp') sync -q

  try { & claude mcp remove -s user photoshop *> $null } catch {}
  Run claude mcp add -s user photoshop '--' uv --directory (Join-Path $repo 'mcp') run mcp run ps-mcp.py

  $starter = Join-Path $Root 'start-photoshop-proxy.cmd'
  Set-Content -Path $starter -Encoding ASCII -Value @(
    '@echo off',
    'rem Keep this window open while Claude works with Photoshop.',
    "node `"$proxy`""
  )
}

Write-Host ''
Write-Host 'Готово. Осталось сделать руками (один раз):'
if ($Target -ne 'photoshop') {
  Write-Host '  Premiere: перезапусти Premiere, открой проект, Window > Extensions > MCP for Adobe Premiere Pro.'
}
if ($Target -ne 'premiere') {
  Write-Host '  Photoshop:'
  Write-Host '   1. Edit > Preferences > Plugins > Enable Developer Mode, перезапусти Photoshop.'
  Write-Host '   2. Creative Cloud > установи и открой UXP Developer Tools.'
  Write-Host "   3. File > Add Plugin > $repo\uxp\ps\manifest.json, затем Load."
  Write-Host "   4. Запусти прокси: $Root\start-photoshop-proxy.cmd (или его запустит Claude),"
  Write-Host '      в панели Photoshop MCP Agent нажми Connect.'
  Write-Host '   После перезапуска Photoshop плагин снова загружается кнопкой Load в UXP Developer Tools.'
}
Write-Host '  Перезапусти Claude Code, чтобы появились инструменты (/mcp покажет статус).'
