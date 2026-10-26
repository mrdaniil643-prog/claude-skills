# Пример: мохито, explainer-рецепт

20 секунд, 1080×1920, 9:16. Референсы из библиотеки: `ror-fly-880547`, `sarut0bisasuke-069973`.

- `mojito.html` — анимация на Canvas; `?t=12` показывает статичный кадр на 12-й секунде.
- `music.py` — оригинальный латин-лаунж трек (112 BPM), синтез на numpy.
- `sfx.py` — звон льда и шипение содовой, тайминги совпадают с анимацией.
- `mojito.mp4` — готовый ролик с музыкой и звуками, −14 LUFS.

Сборка:

```bash
S=~/.claude/skills/opus-video-prompts
node $S/scripts/record.cjs mojito.html video.mp4 --seconds 20 --size 1080x1920
python3 music.py music.wav && python3 sfx.py sfx.wav
ffmpeg -i music.wav -i sfx.wav -filter_complex \
  "[0:a]volume=-4dB[m];[1:a]volume=-2dB[s];[m][s]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]" \
  -map "[a]" -ar 44100 mix.wav
ffmpeg -i video.mp4 -i mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart mojito.mp4
```
