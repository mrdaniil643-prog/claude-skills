# claude-skills

Все мои скиллы для Claude Code в одном месте. Скиллы разложены на **базовый набор**, который ставится всегда, и **тематические наборы**, которые проект подключает по необходимости. Так в каждом проекте остаются только нужные скиллы и список не съедает контекст.

Репозиторий одновременно:

- **плагин-маркетплейс** Claude Code (`.claude-plugin/marketplace.json`): базовый набор это плагин `skills`, каждый тематический набор отдельный плагин;
- **обычная папка скиллов**, которую `install.sh` копирует в `~/.claude/skills`.

| Набор | Папка | Скиллов |
|---|---|---|
| базовый | `skills/` | 10 |
| `video` | `packs/video/skills/` | 8 |
| `security` | `packs/security/skills/` | 4 |
| `mobile` | `packs/mobile/skills/` | 44 |
| `3d` | `packs/3d/skills/` | 51 |
| `adobe` | `packs/adobe/skills/` | 1 |
| `design` | `packs/design/skills/` | 1 |

`frontend-design` сюда не входит: он подключается в проектах как официальный плагин
`frontend-design@claude-plugins-official` через `enabledPlugins` в `.claude/settings.json`.

## Подключение

### Для проекта (в том числе облачные сессии claude.ai/code)

Добавь в `.claude/settings.json` проекта хук. Наборы перечисляются после `install.sh` через пробел; без них ставится только базовый набор, `all` ставит всё.

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "d=\"$HOME/.cache/claude-skills\"; if [ -d \"$d/.git\" ]; then git -C \"$d\" pull -q --ff-only; else git clone -q --depth 1 https://github.com/mrdaniil643-prog/claude-skills \"$d\"; fi && \"$d/install.sh\" video 3d >/dev/null || true",
            "timeout": 120
          }
        ]
      }
    ]
  }
}
```

Хук на старте сессии скачивает (или обновляет) репозиторий и копирует скиллы в `~/.claude/skills`. Скиллы, которые он ставил раньше, но которые больше не выбраны, он удаляет; чужие скиллы в `~/.claude/skills` не трогает.

### Как плагин (CLI, десктоп)

```
/plugin marketplace add mrdaniil643-prog/claude-skills
/plugin install skills@claude-skills
/plugin install video@claude-skills
```

Скиллы появятся с префиксом плагина (`skills:stop-slop`, `video:jumpcut`). Плагин вместе с хуком не включай: каждый скилл появится дважды.

### Вручную

```
git clone https://github.com/mrdaniil643-prog/claude-skills
./claude-skills/install.sh mobile
```

## Базовый набор (`skills/`)

| Скилл | Описание |
|---|---|
| `domain-modeling` | Build and sharpen a project's domain model. |
| `grill-me` | A relentless interview to sharpen a plan or design. |
| `grill-with-docs` | A relentless interview to sharpen a plan or design, which also creates docs (ADR's and glossary) as we go. |
| `grilling` | Grill the user relentlessly about a plan, decision, or idea. |
| `mcp-builder` | Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to interact with external servi… |
| `stop-slop` | Remove AI writing patterns from prose. |
| `theme-factory` | Toolkit for styling artifacts with a theme. |
| `ui-ux-pro-max` | UI/UX design intelligence. |
| `web-artifacts-builder` | Suite of tools for creating elaborate, multi-component claude.ai HTML artifacts using modern frontend web technologie… |
| `webapp-testing` | Toolkit for interacting with and testing local web applications using Playwright. |

Источники: `mcp-builder`, `theme-factory`, `web-artifacts-builder`, `webapp-testing`: [anthropics/skills](https://github.com/anthropics/skills). `stop-slop`: Hardik Pandya. `ui-ux-pro-max`: [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill). `grill-me`, `grilling`, `grill-with-docs`, `domain-modeling`: [mattpocock/skills](https://github.com/mattpocock/skills) (MIT).

## Видео и рилсы (`video`)

Нарезка длинного видео в вертикальные Reels, вырезание пауз, моушн-ролики, обложки и версии под разные площадки.

| Скилл | Описание |
|---|---|
| `ffmpeg-skill` | Набор из 42 скриптов на локальном FFmpeg: обрезка, склейка, 9:16, субтитры и караоке, громкость, экспорт и проверка под… |
| `jumpcut` | Убирает из видео паузы, тишину и слова-паразиты, сохраняя смысл и синхрон звука с картинкой: длинная лекция ужимается… |
| `motion-reel` | Создаёт анимационный Reels/Shorts без камеры из темы, сценария или готовой озвучки в AutoMontage-Agent: script, выбор… |
| `opus-video-prompts` | Библиотека из 703 промптов для видео, которые Claude пишет кодом (HTML, Canvas, SVG, GSAP, Three.js): поиск, адапт… |
| `reel-from-donor` | Превращает полезный разговорный Reels, Short или TikTok в авторский Reels с живыми, конкретными карточками: сначала р… |
| `reel-turnkey` | Собирает ролик под ключ в AutoMontage-Agent: проверяет исходник, транскрибирует речь, готовит один полный пакет ТЗ со… |
| `reels-autocut` | Режет длинное видео (лекцию, подкаст, стрим, интервью, вебинар) на готовые вертикальные Reels/Shorts/TikTok: локальна… |
| `reels-publish-pack` | Готовит нарезанные клипы к выкладке: обложки с заголовком, версии под разные площадки (4:5, 1:1, 16:9 из вертикальног… |

Источники: `reel-turnkey`, `motion-reel`, `reel-from-donor`: [mcdenil-skills/AutoMontage-Agent](https://github.com/mcdenil-skills/AutoMontage-Agent) (MIT), им нужен движок, ставится `~/.claude/skills/reel-turnkey/scripts/install-automontage-engine.sh`. `reels-autocut`, `jumpcut`, `reels-publish-pack`: свои, работают на ffmpeg и Python. `ffmpeg-skill`: [kajisho5/ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) (MIT), только стандартная библиотека Python и ffmpeg; для субтитров по речи нужен локальный распознаватель (faster-whisper, whisper.cpp). `opus-video-prompts`: промпты из [yihui-dev/awesome-opus5-5-videos](https://github.com/yihui-dev/awesome-opus5-5-videos) (MIT), запись в MP4 через Playwright и ffmpeg.

## Безопасность (`security`)

Аудит веб-приложений по OWASP, поиск уязвимостей, защита и цепочка поставок.

| Скилл | Описание |
|---|---|
| `cyber-blue-team-defense` | System hardening, detection engineering, security baseline monitoring, patch management, defense-in-depth architectur… |
| `cyber-supply-chain-security` | Software supply chain security — SBOM generation and analysis, dependency confusion and typosquatting detection, mali… |
| `cyber-vulnerability-scanner` | Dependency auditing, CVE detection, configuration security review, CVSS scoring, and prioritized vulnerability reporting |
| `cyber-web-security` | OWASP Top 10 testing, injection vulnerability detection, API security assessment, authentication testing, and web vul… |

Источники: автор Masriyan (MIT).

## Мобильная разработка (`mobile`)

SwiftUI, Swift concurrency, отладка в симуляторе iOS, Jetpack Compose, Kotlin, Expo и EAS.

| Скилл | Описание |
|---|---|
| `compose-animations` | Use when writing or reviewing Jetpack Compose motion: visibility enter/exit, animating one property toward a target, … |
| `compose-component-design` | Use when designing or reviewing reusable Jetpack Compose component APIs with modifier parameters, root layout placeme… |
| `compose-focus-navigation` | Use when writing or reviewing Jetpack Compose UI for TV, keyboard, desktop, accessibility focus, D-pad navigation, Fo… |
| `compose-performance` | Use when investigating Jetpack Compose recomposition cost, compiler stability reports, skippability, unstable paramet… |
| `compose-state-and-effects` | Use when writing or reviewing Jetpack Compose state ownership, remember state, state hoisting, screen state holders, … |
| `compose-ui-testing-patterns` | Use when writing or reviewing Jetpack Compose UI tests, screenshot tests, previews, semantics assertions, fake image … |
| `eas-app-stores` | EAS service (paid). |
| `eas-hosting` | EAS service (paid). |
| `eas-observe` | EAS service (paid). |
| `eas-simulator` | EAS service (paid). |
| `eas-update` | EAS service (paid). |
| `eas-update-insights` | EAS service (paid). |
| `eas-workflows` | EAS service (paid). |
| `expo-animation` | Framework (OSS). |
| `expo-app-clip` | Framework (OSS). |
| `expo-brownfield` | Framework (OSS). |
| `expo-data-fetching` | Framework (OSS). |
| `expo-design-system` | Framework (OSS). |
| `expo-dev-client` | Framework (OSS). |
| `expo-dom` | Framework (OSS). |
| `expo-examples` | Framework (OSS). |
| `expo-migrate-module` | Framework (OSS). |
| `expo-module` | Framework (OSS). |
| `expo-native-ui` | Framework (OSS). |
| `expo-overview` | Framework (OSS). |
| `expo-project-structure` | Framework (OSS). |
| `expo-router` | Framework (OSS). |
| `expo-ui` | Framework (OSS). |
| `expo-upgrade` | Framework (OSS). |
| `expo-web-to-native` | Framework (OSS). |
| `gradle-run` | Use when planning to execute Gradle through `gradle`, `./gradlew`, or a custom `gradlew*` wrapper script, or diagnosi… |
| `ios-debugger-agent` | Build, run, and debug iOS apps on a simulator. |
| `ios-simulator-skill` | 29 production-ready scripts for iOS app testing, building, and automation. |
| `kotlin-api-design` | Use when designing or reviewing Kotlin function ownership, member or extension functions, factories, single-field dom… |
| `kotlin-concurrency-and-flow` | Use when writing or reviewing Kotlin coroutine scope ownership, raw Thread or Executor work, init launches, non-suspe… |
| `kotlin-control-flow` | Use when writing or reviewing Kotlin branching and control flow: when expressions, guard conditions, sealed type exha… |
| `native-app-profiling` | Profile native macOS/iOS apps using Time Profiler via CLI (xctrace). |
| `release-app-store-changelog` | Create user-facing App Store release notes from git history. |
| `swift-concurrency-expert` | Swift Concurrency review and remediation for Swift 6.2+. |
| `swiftui-liquid-glass` | Implement, review, or improve SwiftUI features using the iOS 26+ Liquid Glass API. |
| `swiftui-performance-audit` | Audit and improve SwiftUI runtime performance. |
| `swiftui-pro` | Comprehensively reviews SwiftUI code for best practices on modern APIs, maintainability, and performance. |
| `swiftui-ui-patterns` | Best practices and patterns for building SwiftUI views and components. |
| `swiftui-view-refactor` | Refactor SwiftUI view files for consistent structure, dependency injection, and Observation usage. |

Источники: `swiftui-pro`: [twostraws/swiftui-agent-skill](https://github.com/twostraws/swiftui-agent-skill) (MIT). `swiftui-*`, `swift-concurrency-expert`, `ios-debugger-agent`, `native-app-profiling`, `release-app-store-changelog`: [patrickserrano/skills](https://github.com/patrickserrano/skills) (MIT). `compose-*`, `kotlin-*`, `gradle-run`: [chrisbanes/skills](https://github.com/chrisbanes/skills) (Apache-2.0). `expo-*`, `eas-*`: официальные скиллы Expo.

## 3D (`3d`)

Three.js, React Three Fiber, шейдеры GLSL, постобработка, WebGPU/TSL, glTF, Blender и генерация 3D-моделей.

| Скилл | Описание |
|---|---|
| `gltf-transform` | Optimize and post-process GLB/glTF 3D models. |
| `meshy` | Generate 3D models from text or images via 5 providers: Meshy (text-to-3D, texturing, batch), fal.ai Hunyuan3D Pro ($… |
| `meshy-3d-generation` | Create or edit digital 3D assets with Meshy: models, textures, rigging, animation, and reference images. |
| `particles-gpu` | GPU-based particle systems using instanced rendering, buffer attributes, Points geometry, and custom shaders. |
| `postfx-bloom` | Bloom and glow effects using Three.js UnrealBloomPass with React Three Fiber. |
| `postfx-composer` | EffectComposer setup and architecture for Three.js post-processing pipelines. |
| `postfx-effects` | Post-processing visual effects including chromatic aberration, vignette, depth of field, film grain, color grading, a… |
| `postfx-router` | Router for Three.js post-processing effects domain. |
| `r3f-animation` | Animate React Three Fiber objects with useFrame, damping, and GLTF clips. |
| `r3f-best-practices` | React Three Fiber (R3F) and Poimandres ecosystem best practices. |
| `r3f-fundamentals` | Set up React Three Fiber scenes, Canvas, typed JSX, hooks, and resource ownership. |
| `r3f-geometry` | Build React Three Fiber geometry, custom buffers, instanced meshes, points, and lines. |
| `r3f-interaction` | Implement React Three Fiber pointer events, picking, dragging, keyboard input, and camera controls. |
| `r3f-lighting` | Light React Three Fiber scenes with direct lights, environment maps, and shadows. |
| `r3f-loaders` | Load and reuse 3D assets in React Three Fiber with useGLTF, useLoader, Suspense, and preloading. |
| `r3f-materials` | Choose and configure React Three Fiber surface materials, PBR, transparency, and transmission. |
| `r3f-physics` | Add Rapier rigid bodies, colliders, forces, sensors, and joints to React Three Fiber. |
| `r3f-postprocessing` | Configure React Three Fiber postprocessing, bloom, selection effects, ambient occlusion, and depth of field. |
| `r3f-shaders` | Implement custom GLSL or TSL materials in React Three Fiber, including uniforms and vertex deformation. |
| `r3f-textures` | Configure textures in React Three Fiber, including color spaces, UV channels, sampling, video, and render targets. |
| `scenario-blender-animation` | Use when animating characters or objects in Blender through Python, a bouncing ball, walk or run cycle, jump, acting … |
| `scenario-blender-expert` | Use when doing any 3D work in Blender through Python or an MCP bridge, headless or in a live session: modeling, sculp… |
| `scenario-blender-geometry-nodes` | Use when building or debugging Geometry Nodes, headless or live: procedural modeling, scattering objects on a surface… |
| `scenario-blender-grease-pencil` | Use when drawing or animating with Grease Pencil in Blender 5.x from Python: 2D or 2.5D illustration, frame-by-frame … |
| `scenario-blender-hair` | Use when grooming hair or fur in Blender with hair curves, such as a character hairstyle, animal fur, procedural fur … |
| `scenario-blender-hard-surface` | Use when modeling hard-surface objects in Blender (sci-fi panels, props, weapons, vehicles, robots, machined or produ… |
| `scenario-blender-lighting-rendering` | Use when lighting, rendering or compositing in Blender: light a character, product or hero shot, interior at dusk or … |
| `scenario-blender-previs-storyboard` | Use when turning a script or story into previs, layout, storyboards or an animatic in Blender: beats to shot list, ca… |
| `scenario-blender-retopology` | Use when turning a dense sculpt, scan or AI-generated mesh into clean topology in Blender, for animation, subdivision… |
| `scenario-blender-rigging` | Use when rigging a character, creature or prop in Blender through Python: "rig this character", Rigify metarig fittin… |
| `scenario-blender-sculpting` | Use when sculpting in Blender through Python: sculpt a head, face or bust, a stylized or cartoon character, a creatur… |
| `scenario-blender-texturing-shading` | Use when texturing, shading or look-developing in Blender: building a PBR material from a texture set, displacement, … |
| `scenario-blender-uv-baking` | Use when UV unwrapping, placing seams, straightening or packing UVs, setting texel density, laying out UDIMs or mirro… |
| `shader-effects` | Visual shader effects—glow/bloom, chromatic aberration, distortion, vignette, film grain, scanlines, glitch, dissolve… |
| `shader-fundamentals` | GLSL shader fundamentals—vertex and fragment shaders, uniforms, varyings, attributes, coordinate systems, built-in va… |
| `shader-noise` | Procedural noise functions in GLSL—Perlin, simplex, Worley/cellular, value noise, FBM (Fractal Brownian Motion), turb… |
| `shader-programming-glsl` | Expert guide for writing efficient GLSL shaders (Vertex/Fragment) for web and game engines, covering syntax, uniforms… |
| `shader-router` | Decision framework for GLSL shader projects. |
| `shader-sdf` | Signed Distance Functions (SDFs) in GLSL—2D/3D shape primitives, boolean operations (union, intersection, subtraction… |
| `three-best-practices` | Three.js performance optimization and best practices guidelines. |
| `threejs-animation` | Three.js animation - keyframe animation, skeletal animation, morph targets, animation mixing. |
| `threejs-fundamentals` | Three.js scene setup, cameras, renderer, Object3D hierarchy, coordinate systems. |
| `threejs-geometry` | Three.js geometry creation - built-in shapes, BufferGeometry, custom geometry, instancing. |
| `threejs-interaction` | Three.js interaction - raycasting, controls, mouse/touch input, object selection. |
| `threejs-lighting` | Three.js lighting - light types, shadows, environment lighting. |
| `threejs-loaders` | Three.js asset loading - GLTF, textures, images, models, async patterns. |
| `threejs-materials` | Three.js materials - PBR, basic, phong, shader materials, material properties. |
| `threejs-postprocessing` | Three.js post-processing - EffectComposer, bloom, DOF, screen effects. |
| `threejs-shaders` | Three.js shaders - GLSL, ShaderMaterial, uniforms, custom effects. |
| `threejs-textures` | Three.js textures - texture types, UV mapping, environment maps, texture settings. |
| `webgpu-threejs-tsl` | Reference WebGPU APIs, TSL syntax, node materials, WGSL integration, compute shaders, and post-processing in Three.js. |

Источники: `threejs-*`, `shader-programming-glsl`: [sickn33/antigravity-awesome-skills](https://github.com/sickn33/antigravity-awesome-skills) (MIT / CC BY 4.0). `r3f-*`: [EnzeD/r3f-skills](https://github.com/EnzeD/r3f-skills) (MIT). `shader-*`, `postfx-*`, `particles-gpu`: [Bbeierle12/Skill-MCP-Claude](https://github.com/Bbeierle12/Skill-MCP-Claude) (MIT). `webgpu-threejs-tsl`, `meshy`: [tdimino/claude-code-minoan](https://github.com/tdimino/claude-code-minoan) (MIT). `gltf-transform`: [rawwerks/VibeCAD](https://github.com/rawwerks/VibeCAD) (MIT). `scenario-blender-*`: [scenario-labs/skills](https://github.com/scenario-labs/skills) (MIT). `meshy-3d-generation`: [meshy-dev/meshy-3d-agent](https://github.com/meshy-dev/meshy-3d-agent) (MIT).

## Adobe на компьютере (`adobe`)

| Скилл | Описание |
|---|---|
| `adobe-desktop` | Управляет установленными на компьютере Adobe Premiere Pro и Photoshop из Claude Code через локальные MCP-серверы на Windo… |

Источники: [leancoderkavy/premiere-pro-mcp](https://github.com/leancoderkavy/premiere-pro-mcp) (MIT) для Premiere и [mikechambers/adb-mcp](https://github.com/mikechambers/adb-mcp) (MIT) для Photoshop; скилл содержит только скрипты установки, сами серверы скачиваются при запуске. Работает в Claude Code на том же компьютере, где стоят программы, не в облачной сессии. Установка: `~/.claude/skills/adobe-desktop/scripts/setup-mac.sh` или `setup-windows.ps1`.

## Графический дизайн (`design`)

| Скилл | Описание |
|---|---|
| `graphic-design` | Дизайн логотипов и фирменного стиля, превью и обложек (YouTube, VK, Rutube, Reels/Shorts, подкасты), афиш, постеров… |

Свой скилл: арт-дирекция и рубрика самокритики, справочники по логотипам, превью и афишам, 16 проверенных приёмов оформления, шаблоны; инструменты — рендер в точные размеры (PNG, JPG, ICO, PDF с вылетами), линтер макета (контраст по пикселям, размеры, безопасные зоны, шрифты), листы восприятия (лента YouTube, фавикон, афиша на стене, сравнение концепций), надписи в кривые (harfbuzz), шрифты Google Fonts с кириллицей, палитры OKLCH, иконки Iconify, CC-фото Openverse, вырезка фона rembg и генератор пакета логотипа с листом фирменного стиля. Библиотека выразительных шрифтов: 225 шрифтов Google Fonts в 15 стилях (готика, древнерусский, хоррор, металл, Y2K, киберпанк, граффити, пиксель и др.) с проверенной по файлам кириллицей, образцами и добавлением своих шрифтов, плюс 3D-надписи на Three.js (выдавленные буквы из любого шрифта, 13 физических материалов: хром, золото, сталь, ржавчина, кровь с каплями, слизь, лёд с сосульками, стекло, Y2K-пузырь, пластик, неоновые трубки, лава, камень) и 16 плоских CSS-эффектов.

## Добавить новый скилл

1. Создай `skills/<имя>/SKILL.md` (или `packs/<набор>/skills/<имя>/SKILL.md`) с frontmatter `name` и `description`.
2. Положи рядом скрипты, справочники и лицензию, если они есть. Пути к своим файлам пиши от `~/.claude/skills/<имя>/`, а не от корня проекта.
3. Перегенерируй таблицы в README, подними версию в `plugin.json` набора и закоммить. Проекты подтянут скилл при следующем старте сессии.

Новый набор: папка `packs/<набор>/` с `.claude-plugin/plugin.json` и `skills/`, плюс строка в `.claude-plugin/marketplace.json`.
