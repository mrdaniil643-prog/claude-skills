# claude-skills

Все мои скиллы для Claude Code в одном месте. Репозиторий одновременно:

- **плагин-маркетплейс** Claude Code (`.claude-plugin/marketplace.json`), так что ставится одной командой;
- **обычная папка скиллов** (`skills/<name>/SKILL.md`), которую можно скопировать в `~/.claude/skills` через `install.sh`.

## Скиллы

| Скилл | Для чего | Источник / лицензия |
|---|---|---|
| `mcp-builder` | Создание MCP-серверов (Python / TypeScript) | Anthropic, см. `LICENSE.txt` |
| `stop-slop` | Убирает «ИИ-шные» обороты из текста | Hardik Pandya, см. `LICENSE` |
| `theme-factory` | 10 готовых тем (цвета, шрифты) для артефактов и сайтов | Anthropic, см. `LICENSE.txt` |
| `ui-ux-pro-max` | База стилей, палитр, шрифтов и UX-правил | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) |
| `web-artifacts-builder` | Сложные HTML-артефакты на React + Tailwind + shadcn/ui | Anthropic, см. `LICENSE.txt` |
| `webapp-testing` | Тестирование веб-приложений через Playwright | Anthropic, см. `LICENSE.txt` |

`frontend-design` сюда не входит: он подключается в проектах как официальный плагин
`frontend-design@claude-plugins-official` через `enabledPlugins` в `.claude/settings.json`.

## Подключение

### Вариант 1. Как плагин (CLI, десктоп)

```
/plugin marketplace add mrdaniil643-prog/claude-skills
/plugin install skills@claude-skills
```

Скиллы появятся с префиксом `skills:` (например, `skills:stop-slop`).

### Вариант 2. Для проекта (в том числе облачные сессии claude.ai/code)

Добавь в `.claude/settings.json` проекта:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "d=\"$HOME/.cache/claude-skills\"; if [ -d \"$d/.git\" ]; then git -C \"$d\" pull -q --ff-only; else git clone -q --depth 1 https://github.com/mrdaniil643-prog/claude-skills \"$d\"; fi && \"$d/install.sh\" >/dev/null || true",
            "timeout": 120
          }
        ]
      }
    ]
  }
}
```

Хук на старте сессии скачивает (или обновляет) репозиторий и копирует скиллы в `~/.claude/skills`. Работает и в облаке, и локально, без установки плагинов. Плагин из варианта 1 вместе с хуком не включай: каждый скилл появится дважды.

### Вариант 3. Вручную

```
git clone https://github.com/mrdaniil643-prog/claude-skills
./claude-skills/install.sh
```

## Добавить новый скилл

1. Создай `skills/<имя>/SKILL.md` с frontmatter (`name`, `description`) и инструкциями.
2. Положи рядом скрипты, справочники и лицензию, если они есть.
3. Добавь строку в таблицу выше и закоммить. Проекты подтянут скилл при следующем старте сессии.
