"""Synthesise a 20 s latin-lounge loop for the mojito reel (original, royalty-free).

python3 music.py music.wav
Bar 1 is chords and shaker only; the groove drops at ~2.1 s when the recipe
starts, and the last bar (~17.1 s, the "Готово!" finale) rings out on Cmaj9.
"""
import sys
import wave

import numpy as np

SR, DUR, BPM = 44100, 20.0, 112
BEAT = 60 / BPM
BAR = BEAT * 4
N = int(SR * DUR)
L = np.zeros(N)
Rt = np.zeros(N)
rng = np.random.default_rng(3)


def hz(midi):
    return 440 * 2 ** ((midi - 69) / 12)


def add(sig, t, pan=0.0, gain=1.0):
    i = int(t * SR)
    if i >= N:
        return
    sig = sig[: N - i] * gain
    L[i:i + len(sig)] += sig * (1 - pan) / 2 * 2 ** .5
    Rt[i:i + len(sig)] += sig * (1 + pan) / 2 * 2 ** .5


def env(n, a=.005, d=.3):
    t = np.arange(n) / SR
    return np.minimum(t / a, 1) * np.exp(-t / d)


def kick():
    n = int(.35 * SR)
    t = np.arange(n) / SR
    f = 45 + 90 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, .002, .12)


def clave():
    n = int(.12 * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 2500 * t) + .4 * np.sin(2 * np.pi * 3700 * t)) * env(n, .001, .025)


def shaker(accent):
    n = int(.08 * SR)
    s = rng.standard_normal(n)
    s = np.diff(np.concatenate([[0], s]))  # crude high-pass
    return s * env(n, .01, .02) * (.5 + .5 * accent)


def bass(note, length):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = hz(note)
    s = np.sin(2 * np.pi * f * t) + .3 * np.sin(4 * np.pi * f * t)
    return np.tanh(1.5 * s) * env(n, .008, length * .7)


def keys(notes, length):
    n = int(length * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for m in notes:
        f = hz(m) * (1 + rng.uniform(-.0015, .0015))
        s += np.sin(2 * np.pi * f * t + .8 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t * 6))
    s *= 1 + .15 * np.sin(2 * np.pi * 5 * t)  # tremolo, Rhodes-ish
    return s / len(notes) * env(n, .01, length * .6)


def pluck(note, length=.4):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = hz(note)
    return (np.sin(2 * np.pi * f * t) + .5 * np.sin(2 * np.pi * 3 * f * t) * np.exp(-t * 20)) * env(n, .002, .12)


# Am9 - Dm9 - G13 - Cmaj9
CHORDS = [
    (45, [60, 64, 67, 71]),
    (50, [60, 65, 69, 64 + 12]),
    (43, [59, 64, 65, 69]),
    (48, [59, 62, 64, 67]),
]
ARP = [[69, 72, 76, 79], [69, 72, 74, 77], [67, 71, 74, 77], [67, 71, 74, 76]]
CLAVE = [0, 1.5, 3, 5, 6]  # 3-2 son clave, in beats over two bars

bars = int(DUR / BAR) + 1
last = bars - 1
for b in range(bars):
    t0 = b * BAR
    root, chord = CHORDS[b % 4]
    if b == last:
        add(keys([60, 64, 67, 71, 74], 3.0), t0, gain=.5)
        add(bass(36, 2.5), t0, gain=.55)
        add(kick(), t0, gain=.8)
        add(pluck(84, 1.2), t0 + BEAT * .5, pan=.4, gain=.25)
        break
    # Rhodes stabs on the off-beats
    for k in (0, 1.5, 2.5, 3.5) if b else (0, 2):
        add(keys(chord, BEAT * (1.4 if b else 3)), t0 + k * BEAT, pan=-.15, gain=.32)
    # shaker 16ths throughout
    for s in range(16):
        add(shaker(s % 4 == 2), t0 + s * BEAT / 4, pan=.45, gain=.07 if b else .05)
    if b == 0:
        continue
    # groove from bar 2
    for k in (0, 2):
        add(kick(), t0 + k * BEAT, gain=.7)
    for c in CLAVE:
        if (b % 2) * 4 <= c < (b % 2) * 4 + 4:
            add(clave(), t0 + (c - (b % 2) * 4) * BEAT, pan=-.4, gain=.13)
    # tumbao-style bass: anticipations on the "and" of 2 and on 4
    add(bass(root, BEAT * .9), t0, gain=.5)
    add(bass(root + 7, BEAT * .9), t0 + 1.5 * BEAT, gain=.45)
    add(bass(root + 12 if b % 2 else root, BEAT * 1.4), t0 + 3 * BEAT, gain=.45)
    # marimba-ish arpeggio from bar 3
    if b >= 2:
        for i, k in enumerate((.5, 1, 2, 2.5, 3.5)):
            add(pluck(ARP[b % 4][i % 4]), t0 + k * BEAT, pan=.35 * (-1) ** i, gain=.16)

mix = np.stack([L, Rt], 1)
fade = np.ones(N)
fi, fo = int(.3 * SR), int(1.8 * SR)
fade[:fi] = np.linspace(0, 1, fi)
fade[-fo:] = np.linspace(1, 0, fo) ** 1.5
mix *= fade[:, None]
mix /= np.abs(mix).max() / .89
with wave.open(sys.argv[1], 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype('<i2').tobytes())
print('ok', sys.argv[1])
