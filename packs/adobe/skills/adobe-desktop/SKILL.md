---
name: adobe-desktop
description: >-
  Управляет установленными на компьютере Adobe Premiere Pro и Photoshop из Claude Code
  через локальные MCP-серверы на Windows и macOS: ставит и чинит подключение, затем
  монтирует в Premiere (проекты, бины, секвенции, склейка, маркеры, эффекты, переходы,
  экспорт) и работает в Photoshop (документы, слои, текст, выделения, удаление фона,
  коррекция, генеративная заливка, экспорт PNG). Используй, когда просят «подключи
  Photoshop/Premiere», «сделай в Премьере», «собери секвенцию», «экспортируй из Premiere»,
  «сделай обложку в Фотошопе», «переименуй слои», «убери фон в PS», или когда в
  `/mcp` нет серверов premiere-pro/photoshop. Только для Claude Code на том же
  компьютере, где стоят программы; облачным Adobe-инструментам нужен официальный
  плагин Adobe, а не этот скилл.
metadata:
  compatibility: Windows 10/11 или macOS; Claude Code CLI или десктоп на том же компьютере; Node.js 20.19+; для Photoshop ещё git, uv и UXP Developer Tools; Premiere Pro 2020–2026, Photoshop 26.0+.
  sources: premiere-pro-mcp@1.25.0 (MIT, github.com/leancoderkavy/premiere-pro-mcp); mikechambers/adb-mcp @ afe5d09 (MIT)
---

# Photoshop и Premiere Pro с компьютера

Две независимые связки, обе локальные:

- **Premiere** — `premiere-pro-mcp` (MCP-сервер из npm + CEP-панель в Premiere). Сервер
  в Claude Code называется `premiere-pro`.
- **Photoshop** — `adb-mcp`: Python MCP-сервер ↔ Node-прокси на `127.0.0.1:3001` ↔
  UXP-плагин в Photoshop. Сервер называется `photoshop`. Прокси должен работать,
  пока Claude управляет Photoshop.

## 1. Проверь подключение

Посмотри, есть ли инструменты `mcp__premiere-pro__*` и `mcp__photoshop__*`
(или `claude mcp list`). Если нужных нет — шаг 2. Если есть — шаг 3.

Работать можно только с Claude Code на компьютере пользователя. В облачной сессии
(claude.ai/code, контейнер Linux) программ Adobe нет: скажи об этом и предложи
официальный плагин Adobe для облачных инструментов.

## 2. Установка

Определи систему и запусти скрипт; аргумент `premiere` или `photoshop` ставит
только одну программу. Скрипты повторно запускать безопасно.

```bash
# macOS
bash ~/.claude/skills/adobe-desktop/scripts/setup-mac.sh
```
```powershell
# Windows
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.claude\skills\adobe-desktop\scripts\setup-windows.ps1"
```

Скрипт проверяет Node 20.19+, ставит `premiere-pro-mcp@1.25.0` и его CEP-панель
(`--install-cep` включает режим отладки CEP, без него Premiere не грузит панель),
клонирует `adb-mcp` в `~/.adobe-mcp/adb-mcp` на проверенном коммите и ограничивает
его прокси локальным адресом (в оригинале он без пароля слушает всю сеть).
Затем регистрирует оба сервера в Claude Code (`claude mcp add -s user`).

Если чего-то не хватает, скрипт остановится и назовёт команду установки
(`brew install node uv` / `winget install OpenJS.NodeJS.LTS astral-sh.uv Git.Git`).
Ставь недостающее только с согласия пользователя.

После скрипта перескажи пользователю ручные шаги, которые он напечатал: панель
в Premiere (Window > Extensions > MCP for Adobe Premiere Pro), режим разработчика
в Photoshop, загрузку плагина через UXP Developer Tools, кнопку Connect.
Затем попроси перезапустить Claude Code, чтобы появились инструменты.

## 3. Перед работой

**Premiere:** вызови `verify_premiere_connection` (только чтение). Если моста,
проекта или активной секвенции нет, сначала исправь это; диагностика —
`premiere-pro-mcp --doctor`. Список возможностей — `get_capabilities`.

**Photoshop:**
1. Запусти прокси в фоне: `node ~/.adobe-mcp/adb-mcp/adb-proxy-socket/proxy.js`
   (Windows: `%USERPROFILE%\.adobe-mcp\start-photoshop-proxy.cmd`). Если порт 3001
   уже занят, прокси уже работает.
2. Попроси нажать Connect в панели Photoshop MCP Agent (после перезапуска Photoshop
   плагин заново грузится кнопкой Load в UXP Developer Tools).
3. Прочитай ресурс `config://get_instructions` сервера `photoshop` и вызови
   `get_documents`. Ошибка «Could not connect to photoshop» значит, что плагин не
   нажал Connect или прокси не запущен.

## 4. Правила работы

- Сначала план, потом действия: перечисли шаги и что изменится; правки, которые
  трудно отменить (удаление клипов с ripple, `flatten_all_layers`, перезапись файлов),
  делай после явного согласия.
- Работай на копии: в Premiere `save_project_as` в новый файл или `create_sequence_checkpoint`
  перед крупной правкой,
  в Photoshop `duplicate_document` или `save_document_as`.
- Проверяй глазами: в Premiere `capture_frame` / `export_frame` по ключевым
  моментам, в Photoshop `get_document_image` после каждого заметного шага.
- Инструменты, исполняющие произвольный ExtendScript (`execute_extendscript`,
  `evaluate_expression`), сервер по умолчанию скрывает (нужен профиль `unsafe-script`
  в `PREMIERE_MCP_CAPABILITIES`); не включай его без просьбы.
- Пути к медиа передавай абсолютные; на Windows — с обратными слэшами.

## 5. Сценарии

**Черновой монтаж в Premiere из клипов** (например, после `reels-autocut`):
`import_media` → `create_bin` + `move_items_to_bin` → `create_sequence_from_clips` в нужном
порядке → `add_markers_batch` на ключевых местах → `batch_add_transitions` →
`capture_frame` на проверку → `export_sequence` с пресетом (`.epr`) в отдельную папку.

**Пакет в Premiere под площадки:** `duplicate_sequence`, затем `auto_reframe_sequence`
под 9:16, 1:1 или 16:9, экспорт каждой; громкость и итоговую проверку файла делай `ffmpeg-skill`.

**Обложка в Photoshop:** документ 1080×1920 → `place_image` кадр из ролика →
`remove_background` или `select_subject` + маска → заголовок
`create_multi_line_text_layer` и `align_content` → тень/обводка →
`get_document_image` на проверку → `export_layers_as_png` или `save_document_as`.

**Пакетная уборка PSD:** `get_layers` → предложи схему имён → `rename_layers`,
`group_layers`; скрытые и пустые слои удаляй только по списку, согласованному
с пользователем.

## Обновление и удаление

Повторный запуск скрипта обновляет всё до версий, зашитых в него. Удаление:
`claude mcp remove -s user premiere-pro`, `claude mcp remove -s user photoshop`,
`premiere-pro-mcp --uninstall-cep`, `npm uninstall -g premiere-pro-mcp`, удалить
`~/.adobe-mcp` и плагин в UXP Developer Tools.
