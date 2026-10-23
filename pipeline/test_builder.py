"""Smoke-test the mmpp builder: minimal song -> headless render -> wav check."""
import os
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mmpp import Song, InstrumentTrack, Pattern, Note, TICKS_PER_BAR
from lmms_render import render_song

ROOT = r"C:\Users\Thinkbook\OneDrive\Celine"
OUT = os.path.join(ROOT, "renders", "builder_test.wav")

kick = InstrumentTrack(
    name="Kick",
    instrument="kicker",
    instrument_params={
        "env": "1", "distend": "2", "noise": "0", "version": "1", "startfreq": "200",
        "dist": "2", "endfreq": "5", "syncmode": "0", "slope": "1",
        "decay_denominator": "4", "decay_numerator": "4", "decay": "213",
        "startnote": "0", "gain": "5", "click": "0", "endnote": "0"},
    patterns=[Pattern(notes=[Note(57, p) for p in (0, 48, 96, 144)],
                      pos=0, len=TICKS_PER_BAR, name="Default")],
    basenote=57, vol=80,
)

snare = InstrumentTrack(
    name="Snare",
    instrument="audiofileprocessor",
    instrument_params={
        "interp": "1", "reversed": "0", "looped": "0", "sframe": "0",
        "lframe": "0", "eframe": "1", "src": "drums/snare01.ogg", "amp": "210",
        "stutter": "0"},
    patterns=[Pattern(notes=[Note(57, p) for p in (48, 144)],
                      pos=0, len=TICKS_PER_BAR, name="Snare")],
    basenote=56, vol=90,
)

song = Song(name="BuilderTest", bpm=128, tracks=[kick, snare])

ok = render_song(song, OUT, os.path.join(ROOT, "logs", "builder_test.log"))
print("render ok:", ok)
if ok:
    with wave.open(OUT, "rb") as w:
        print("channels:", w.getnchannels(), "rate:", w.getframerate(),
              "frames:", w.getnframes(), "seconds:", round(w.getnframes() / w.getframerate(), 2))
    print("size:", os.path.getsize(OUT))
else:
    with open(os.path.join(ROOT, "logs", "builder_test.log"), encoding="utf-8") as fh:
        print(fh.read()[-3000:])
