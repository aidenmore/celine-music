"""Determine LMMS's note->frequency mapping (separate bars + autocorrelation)."""
import os
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from mmpp import Song
from songkit import track_preset, pat
from lmms_render import render_song
import presets as P

ROOT = r"C:\Users\Thinkbook\OneDrive\Celine"
OUT = os.path.join(ROOT, "renders", "pitch_test.wav")
SR = 44100

cat = P.catalog()
lb = [c for c in cat if c["instrument"] == "LB302"][0]
print("using preset:", lb["rel"])

KEYS = [45, 57, 69, 81]
tracks = []
for i, key in enumerate(KEYS):
    bar = i  # one key per bar
    tracks.append(track_preset(
        lb["path"], f"N{key}",
        [pat([(key, 0, 190)], pos=bar * 192, length=192)],
        vol=110))

song = Song(name="PitchTest", bpm=120, tracks=tracks)
ok = render_song(song, OUT, os.path.join(ROOT, "logs", "pitch_test.log"))
print("render ok:", ok)
if not ok:
    print(open(os.path.join(ROOT, "logs", "pitch_test.log"), encoding="utf-8").read()[-2000:])
    sys.exit(1)

with wave.open(OUT, "rb") as w:
    sr = w.getframerate()
    raw = w.readframes(w.getnframes())
a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
a = a.reshape(-1, 2).mean(axis=1)
print("duration", round(len(a) / sr, 2), "s  peak", float(np.max(np.abs(a))))

bar_secs = 4 * 60.0 / 120.0  # 2 s per bar at 120 bpm


def autocorr_f0(seg):
    seg = seg - seg.mean()
    if np.max(np.abs(seg)) < 1e-4:
        return 0.0
    corr = np.correlate(seg, seg, mode="full")[len(seg) - 1:]
    corr /= (corr[0] + 1e-12)
    lo, hi = int(sr / 1200), int(sr / 45)   # 45 Hz .. 1200 Hz
    if hi >= len(corr):
        hi = len(corr) - 1
    seg_c = corr[lo:hi]
    if len(seg_c) == 0:
        return 0.0
    k = int(np.argmax(seg_c)) + lo
    return sr / k


for i, key in enumerate(KEYS):
    st = int((i * bar_secs + 0.08) * sr)
    seg = a[st:st + int(0.9 * sr)]
    f = autocorr_f0(seg)
    if f > 0:
        as_midi = 69 + 12 * np.log2(f / 440.0)
        print(f"  LMMS key {key:>3} -> {f:8.2f} Hz  (MIDI {as_midi:6.2f})  offset={as_midi-key:+.2f}")
    else:
        print(f"  LMMS key {key:>3} -> no pitch detected")
