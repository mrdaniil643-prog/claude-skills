"""Ice clinks and soda fizz for the mojito reel, timed to mojito.html.

python3 sfx.py sfx.wav
Timings mirror the animation: each ice cube first touches down ~0.2 s after
it starts falling (bounce easing over 0.55 s), cubes start 0.085 s apart from
10.5 s; soda pours from 15.625 s to 17.0 s and keeps fizzing to the end.
"""
import sys
import wave

import numpy as np

SR, DUR = 44100, 20.0
N = int(SR * DUR)
L = np.zeros(N)
R = np.zeros(N)
rng = np.random.default_rng(11)


def add(sig, t, pan=0.0, gain=1.0):
    i = int(t * SR)
    if i >= N:
        return
    sig = sig[: N - i] * gain
    L[i:i + len(sig)] += sig * (1 - pan)
    R[i:i + len(sig)] += sig * (1 + pan)


def highpass(x, a=.97):
    y = np.zeros_like(x)
    for i in range(1, len(x)):
        y[i] = a * (y[i - 1] + x[i] - x[i - 1])
    return y


def clink(size=1.0):
    """Ice on glass: inharmonic bright partials plus a tiny noise tick."""
    n = int(.45 * SR)
    t = np.arange(n) / SR
    base = rng.uniform(2300, 3400) / size
    s = np.zeros(n)
    for ratio, amp, dec in ((1, 1, .09), (2.76, .6, .05), (5.4, .35, .03), (8.9, .2, .02)):
        if base * ratio > 18000:  # keep partials below Nyquist, no aliasing
            continue
        s += amp * np.sin(2 * np.pi * base * ratio * t + rng.uniform(0, 6)) * np.exp(-t / dec)
    tick = rng.standard_normal(n) * np.exp(-t / .004)
    return (s + .5 * highpass(tick)) * np.minimum(t / .0007, 1)


def thud():
    """Cube landing on the pile: low knock."""
    n = int(.12 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * (180 + 120 * np.exp(-t * 60)) * t) * np.exp(-t / .03)


# ---------- ice: 15 cubes, 10.5 s + 0.085 s * i, first impact +0.2 s ----------
ICE_START, STAGGER, FALL = 10.5, .085, .55
for i in range(15):
    land = ICE_START + i * STAGGER + FALL * .364
    pan = ((i % 3) - 1) * .35
    add(clink(1 + rng.uniform(-.1, .15)), land, pan, .5)
    add(thud(), land, pan, .35)
    # bounce-easing hops at 72.7 % and 90.9 % of the fall
    add(clink(.9), ICE_START + i * STAGGER + FALL * .727, pan, .2)
    if i % 2:
        add(clink(.85), ICE_START + i * STAGGER + FALL * .909, pan, .1)

# ---------- soda: pour stream + carbonation crackle ----------
POUR_START, POUR_END = 15.625, 17.0
t = np.arange(N) / SR
pour_env = np.clip((t - POUR_START) / .08, 0, 1) * np.clip((POUR_END + .05 - t) / .15, 0, 1)
# liquid stream: band-limited noise, wobbling brightness
noise = rng.standard_normal(N)
stream = highpass(np.convolve(noise, np.ones(6) / 6, 'same'), .9)
stream *= pour_env * (.6 + .4 * np.sin(2 * np.pi * 7 * t) ** 2)
add(stream, 0, -.1, .22)
# fizz: dense random micro-pops, swelling during the pour, then settling
fizz_env = np.clip((t - POUR_START - .1) / .5, 0, 1) * (.35 + .65 * np.exp(-np.clip(t - POUR_END, 0, None) / 1.3))
fizz_env *= np.clip((DUR - t) / 1.5, 0, 1)
pops = (rng.random(N) < .012) * rng.standard_normal(N)
pops = highpass(np.convolve(pops, np.exp(-np.arange(40) / 6), 'same'), .8)
hiss = highpass(rng.standard_normal(N), .6) * .25
for ch, pan in ((pops, .3), (np.roll(pops, 997), -.3)):
    add((ch + hiss) * fizz_env, 0, pan, .28)

mix = np.stack([L, R], 1)
mix /= np.abs(mix).max() / .89
with wave.open(sys.argv[1], 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype('<i2').tobytes())
print('ok', sys.argv[1])
