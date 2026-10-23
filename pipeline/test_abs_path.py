"""Test: does LMMS load samples from an absolute path? (flac + wav)"""
import os
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mmpp import Song, InstrumentTrack, Pattern, Note
from lmms_render import render_song

ROOT = r"C:\Users\Thinkbook\OneDrive\Celine"
FLAC = r"C:\Users\Thinkbook\OneDrive\Celine\samples\909\909 KICK 2.flac"
WAV = r"C:\Users\Thinkbook\OneDrive\Celine\samples\_unpacked\One Shots Snare www.alimelody.ir\Ghosthack-Snare_Crunch.wav"

OUT = os.path.join(ROOT, "renders", "abstest.wav")


def afp(src, name):
    return InstrumentTrack(
        name=name, instrument="audiofileprocessor",
        instrument_params={"interp": "1", "reversed": "0", "looped": "0",
                           "sframe": "0", "lframe": "0", "eframe": "1",
                           "src": src.replace("\\", "/"), "amp": "210",
                           "stutter": "0"},
        patterns=[Pattern(notes=[Note(57, 0), Note(57, 96)], pos=0, len=192, name=name)],
        basenote=57, vol=100)


song = Song(name="AbsTest", bpm=128, tracks=[afp(FLAC, "FlacKick"), afp(WAV, "WavSnare")])
ok = render_song(song, OUT, os.path.join(ROOT, "logs", "abstest.log"))
print("render ok:", ok)
if ok:
    with wave.open(OUT, "rb") as w:
        n = w.getnframes()
        print("frames", n, "secs", round(n / w.getframerate(), 2))
    # check for non-silence
    import struct
    with open(OUT, "rb") as fh:
        fh.read(44)
        raw = fh.read()
    vals = struct.unpack("<" + "h" * (len(raw) // 2), raw[:len(raw) // 2 * 2])
    peak = max(abs(v) for v in vals)
    print("peak", peak, "nonzero", sum(1 for v in vals if v != 0))
else:
    print(open(os.path.join(ROOT, "logs", "abstest.log"), encoding="utf-8").read()[-2500:])
