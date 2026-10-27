# Выразительные шрифты: библиотека по стилям

Каталог `references/fonts.json` — 225 шрифтов Google Fonts (OFL/Apache:
бесплатно, в т. ч. для коммерции и логотипов) в 15 стилях. Кириллица проверена
по самим файлам, а не по описаниям. Образцы каждого стиля —
`references/specimens/<стиль>.jpg` (открой Read, прежде чем выбирать).

```bash
S=~/.claude/skills/graphic-design/scripts
python3 $S/typelib.py styles                         # стили и сколько с кириллицей
python3 $S/typelib.py list gothic                    # шрифты стиля; --cyr только с кириллицей
uv run --with fonttools python $S/typelib.py specimen pick.jpg --style horror --text "Кровавая луна"
uv run --with fonttools python $S/typelib.py specimen pick.jpg --fonts "Shafarik,Monomakh,Ruslan Display" --text "Тёмный рыцарь" --heavy
python3 $S/typelib.py get "Shafarik" "Rubik Wet Paint" --out fonts   # в проект + fonts.css
uv run --with fonttools python $S/typelib.py check fonts/Shafarik-400.ttf "Тёмный рыцарь"
uv run --with fonttools python $S/typelib.py add ~/Downloads/MyGothic.otf --style gothic --license "куплен, desktop+web"
```

**Всегда** делай `specimen` с настоящим текстом пользователя по 5–10 кандидатам
и выбирай глазами: декоративные шрифты сильно различаются на конкретных буквах
(Ж, Ф, Щ, Ы, Я — слабые места кириллицы).

## Правила для декоративных шрифтов

- Только для 1–5 слов: заголовок, логотип, название. Всё остальное — спокойный
  текстовый шрифт (пары ниже). Два декоративных в одном макете — почти всегда ошибка.
- Чем экспрессивнее шрифт, тем проще всё вокруг: фон, композиция, палитра.
- Эффекты (`templates/type-effects.html`) — не больше одного на заголовок.
  Шрифт с текстурой (Rubik Wet Paint, Rubik Burned) уже эффект; не добавляй к нему второй.
- Цветные шрифты (Nabla, Bungee Spice, Honk, Foldit) несут градиент внутри:
  не задавай им `color`, не накладывай обводки; цвет меняют
  `font-palette` / `@font-palette-values`. Только латиница.
- Шрифты с пометкой «кириллица на ширину иероглифа» (японские: Rampart One,
  Train One, Reggae One, DotGothic16, Klee One, Kosugi Maru, Hachi Maru Pop,
  Yomogi) — для русского текста обязательно `letter-spacing`/`word-spacing`
  из `typelib.py list` (значения в каталоге), иначе текст вразрядку.
- Перед сдачей: `check.cjs` (шрифт загрузился?) и `typelib.py check` (все буквы есть?).
- Логотип из декоративного шрифта — в кривые (`text2path.py`), потом доработать.

## Стили: что брать

Формат: **лучшее с кириллицей** · только латиница (для английских слов) ·
текстовая пара · эффекты: CSS из `type-effects.html` (№). 3D-пресеты `text3d.cjs` по стилям:
готика → gold, stone, blood; древнерусский → gold, stone; хоррор → blood, slime, rust;
металл → chrome, steel, rust, lava; Y2K → y2k, chrome, glass, candy; киберпанк → neon,
chrome, glass; граффити → candy, neon; пиксель → neon, candy; ретро-70 → candy, gold;
вестерн → gold, rust, stone; каллиграфия → neon, gold; люкс → gold, glass;
советский → steel, rust, gold, stone; мило → candy, y2k; объём → любой.

| Стиль | Кириллица | Латиница | Пара для текста | Эффекты |
|---|---|---|---|---|
| Готика | **Shafarik, Monomakh, Pochaevsk** (стиль древнерусского устава — ближе всего к готике), Ruslan Display, Kelly Slab | UnifrakturCook, UnifrakturMaguntia, Pirata One, Grenze Gotisch, Fruktur, New Rocker, Jacquard 24 | Cormorant, Old Standard TT | 7 инициал, 2 золото, 1 кровь, 13 камень |
| Древнерусский | **Shafarik, Monomakh, Ponomar, Triodion**, Ruslan Display, Kurale | — | Kurale, Old Standard TT | 7, 13, 2 |
| Хоррор, кровь | **Rubik Wet Paint** (подтёки), Rubik Beastly, Rubik Burned, Rubik Distressed, Rubik Storm, Rubik Glitch; любой жирный (Dela Gothic One) + подтёки | Nosifer, Creepster, Butcherman, Eater, Jolly Lodger, Frijole | Special Elite (лат), PT Mono, Rubik | 1 кровь, 12 слизь, 4 ржавчина, 9 глитч |
| Металл, рок | **Stalinist One, Dela Gothic One, Russo One, Rubik Mono One**, Alumni Sans Collegiate One | Metal Mania, New Rocker, Black Ops One, Bungee, Faster One, Saira Stencil One | Oswald, Roboto Condensed | 3 металл, 2 золото, 4 ржавчина, 10 огонь |
| Y2K, рейв, хром | **Rubik Bubbles, Climate Crisis, Rubik Vinyl, Rubik Glitch Pop, Rubik Iso, Unbounded**, Rampart One, Kablammo | Monoton, Bagel Fat One, Tilt Warp, Tilt Prism, Nabla, Bungee Spice, Krona One, Zen Dots, Syne | Unbounded 400, Manrope | 5 хром-пузырь, 6 голограмма, 9 глитч, 8 неон |
| Киберпанк | **Tektur, Russo One, Exo 2, Jura, Handjet**, Rubik Broken Fax, Prosto One | Orbitron, Audiowide, Oxanium, Chakra Petch, Michroma, Bruno Ace | Jura, Exo 2, JetBrains Mono | 9 глитч, 8 неон, 6 голограмма |
| Граффити, улица | **Rubik Spray Paint, Rubik Marker Hatch, Rubik Scribble**, Oi, Kablammo, Rubik Doodle Shadow | Sedgwick Ave Display, Permanent Marker, Bangers, Rock Salt, Knewave | Rubik, Caveat | 16 граффити, 8 стикер (recipes) |
| Пиксель | **Press Start 2P, Tiny5, Handjet**, Rubik Pixels, DotGothic16 (с интервалом) | Silkscreen, Jersey 10, Micro 5, VT323, Sixtyfour | Handjet, JetBrains Mono | 15 8-бит, 9 глитч |
| Ретро 70-х | **Climate Crisis, Rubik Bubbles, Lobster, Oi**, Orelega One | Shrikhand, Bagel Fat One, Righteous, Chango, Titan One, Modak, Fascinate | Manrope, Comfortaa | 14 ретро-обводки, 2 золото |
| Вестерн, цирк | **Kelly Slab, Underdog** (мало — добавь свой) | Rye, Ewert, Sancreek, Smokum, Diplomata, Vast Shadow, Ultra | PT Serif, Old Standard TT | 14, 13, 2 |
| Каллиграфия | **Great Vibes, Marck Script, Bad Script, Comforter Brush**, Caveat, Lobster, Pacifico | Pinyon Script, Parisienne, Alex Brush, Kaushan Script | Cormorant, Lora | 2 золото |
| Люкс, ар-деко | **Poiret One, Forum, Yeseva One, Prata, Cormorant SC, Playfair Display SC**, Tenor Sans | Limelight, Federo, Italiana, Marcellus, Cinzel | Tenor Sans, Cormorant | 2 золото, 6 голограмма |
| Советский | **Stalinist One, Ruslan Display, Russo One, Rubik Mono One, Dela Gothic One, Underdog, Prosto One** | — | Oswald, PT Sans | 4 ржавчина, 13 камень, 2 золото |
| Мило, детское | **Comfortaa, Rubik Bubbles, Balsamiq Sans, Playpen Sans, Shantell Sans, Pangolin** | Sniglet, Fredoka, Mochiy Pop One | Nunito, Comfortaa | 14, стикер (recipes 8) |
| Объём, контур | **Rampart One, Train One** (с интервалом), Rubik Iso, Rubik Doodle Shadow, Rubik Lines | Bungee Shade, Bungee Outline, Monoton, Londrina Shadow, Tilt Prism, Nabla | Manrope | 14, 3, 6 |

## Когда нужной кириллицы нет

1. Возьми кириллический шрифт того же **духа** из таблицы (готика → Shafarik/
   Monomakh; вестерн → Kelly Slab; хоррор → Rubik Wet Paint) и добери образ
   эффектом: кровь, ржавчина, золото, инициал, гравировка.
2. Латинский шрифт оставь для латинских слов в том же макете (название бренда,
   «VOL. 2», «EST. 2024»): смешение даёт характер, если роли разные.
3. Нужен именно определённый шрифт — купи/скачай кириллическую версию и добавь:
   `typelib.py add font.otf --style gothic --license "..."`. Шрифт попадает в
   `~/.graphic-design/fonts` и доступен во всех проектах. Проверь лицензию:
   для логотипа нужна лицензия на логотип/коммерцию, для сайта — web.
4. Никогда не подставляй латинский шрифт с запасной кириллицей системы: CSS
   «дорисует» русские буквы другим шрифтом, `check.cjs` покажет FAIL шрифта.

## Свой шрифт в проекте

```bash
uv run --with fonttools python $S/typelib.py add "Fonts/Old London Cyr.otf" --style gothic --license "OFL"
python3 $S/typelib.py list gothic           # появится с пометкой «свой»
python3 $S/typelib.py get "Old London Cyr" --out fonts
```
