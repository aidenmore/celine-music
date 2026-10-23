"""
gen_songs.py - Spec-driven generator for the wider track list.

Each SPEC describes a distinct production: tempo, key, chord progression, drum
character, bass voice, arrangement sections and FX.  The builder assembles a
real LMMS project from the custom instruments, the downloaded sample library and
verified FX chains.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mmpp import Song, Pattern, Note, write_song, TICKS_PER_BAR, TICKS_PER_16TH
from songkit import (track_sample, track_zyn, pat, lmms_key,
                     REVERB_FREEVERB3, REVERB_PLATE, REVERB_CALF, SATURATOR,
                     VINTAGE_DELAY, MULTI_CHORUS, CLIP, HARD_LIMITER,
                     TAP_ECHO, TAP_AUTOPAN, TAP_CHORUS,
                     FX_DUALFILTER, FX_AMPLIFIER, FX_STEREO, FX_BASSBOOST,
                     FX_STEREOMATRIX)
from build_songs import Voice, hits, chord_voice, drum_track, L, C, ROOT

NOTE_NAMES = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4,
              "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9,
              "A#": 10, "Bb": 10, "B": 11}
TRIAD = {"min": [0, 3, 7], "maj": [0, 4, 7], "min7": [0, 3, 7, 10],
         "maj7": [0, 4, 7, 11], "sus2": [0, 2, 7], "sus4": [0, 5, 7],
         "min9": [0, 3, 7, 10, 14], "maj9": [0, 4, 7, 11, 14],
         "dim": [0, 3, 6], "aug": [0, 4, 8], "min6": [0, 3, 7, 9],
         "maj6": [0, 4, 7, 9], "m7b5": [0, 3, 6, 10], "dom7": [0, 4, 7, 10]}

# Key of the real vocal one-shots, parsed from their file names
VOCAL_KEYS = {
    "A_AhBreathyVox": ("A", 0), "Abm_EasyVocal": ("Ab", 0),
    "Bm_CarefreeVocal": ("B", 0), "Cm_HeyVocal": ("C", 0),
    "C_OhMyGodVox": ("C", 0), "Dm_OhAh": ("D", 0),
    "Ebm_GospelVocal": ("Eb", 0), "Ebm_OhhhVocal": ("Eb", 0),
    "Ebm_ScatVocal": ("Eb", 0), "EeyaVox": ("E", 0), "E_HeyVocal": ("E", 0),
    "F2_Oohh": ("F", 0), "G2_Aahh": ("G", 0), "IVox": ("C", 0),
}


def root_midi(name: str, octave: int = 3) -> int:
    i = 2 if len(name) > 1 and name[1] in "#b" else 1
    p = name[:i]
    return 12 * (octave + 1) + NOTE_NAMES[p]


def triad(root: int, quality: str) -> list[int]:
    return [root + i for i in TRIAD[quality]]


def vocal_sample(pattern: str, idx: int = 0):
    """Return (path, source_root_midi) for a real vocal one-shot."""
    rx = re.compile(pattern, re.I)
    hits_found = []
    for k, path in LIB.items():
        if not k.startswith("vocal/"):
            continue
        if not rx.search(k):
            continue
        base = os.path.basename(k)[:-4]
        for pref, (nm, octv) in VOCAL_KEYS.items():
            if base.startswith(pref):
                hits_found.append((path, root_midi(nm, 3)))
                break
        else:
            hits_found.append((path, root_midi("C", 3)))
    if not hits_found:
        return None, None
    return hits_found[idx % len(hits_found)]


# ------------------------------------------------------------------ specs ---
@dataclass
class Spec:
    title: str
    genre: str
    bpm: int
    key: str                       # e.g. "D"
    scale: str = "min"             # tonic chord quality
    prog: list = field(default_factory=list)   # [(root_name, quality)]
    bars: int = 64
    kick_pat: str = "x...x...x...x..."
    snare_pat: str = "..x...x...x...x."
    hat_pat: str = "..x...x...x...x."
    hat_roll: str = ""
    perc_pat: str = ""
    bass_voice: str = "fm_pluck_dk"
    bass_pat: str = "x...x...x...x..."
    bass_oct: int = 0
    chord_voice: str = "supersaw"
    chord_every: int = 1
    chord_style: str = "stab"
    lead_voice: str = ""
    lead_pat: str = ""
    lead_oct: int = 0
    vocal: str = ""
    fx: list = field(default_factory=list)
    sections: list = field(default_factory=list)   # (start, end, flags)
    real_kick: str = ""
    real_clap: str = ""
    real_hat: str = ""
    perc_lib: str = ""
    master_width: int = 28
    zyn_lead: str = ""


def std_sections(bars=64, intro=8, build=8, main=16, brk=8, main2=16, outro=8):
    s = []
    a = 0
    s.append((a, a + intro, {"pad": 1, "hat": 1, "fx": 0}))
    a += intro
    s.append((a, a + build, {"pad": 1, "hat": 1, "kick": 1, "bass": 1, "perc": 1, "fx": 0}))
    a += build
    s.append((a, a + main, {"drums": 1, "bass": 1, "chord": 1, "lead": 1, "perc": 1, "hat": 1, "vocal": 1, "fx": 1}))
    a += main
    s.append((a, a + brk, {"pad": 1, "lead": 1, "vocal": 1, "hat": 0, "fx": 0}))
    a += brk
    s.append((a, a + main2, {"drums": 1, "bass": 1, "chord": 1, "lead": 1, "perc": 1, "hat": 1, "vocal": 1, "fx": 1}))
    a += main2
    s.append((a, a + outro, {"drums": 1, "bass": 1, "chord": 1, "hat": 1, "perc": 1, "fx": 1}))
    return s


SPECS = [
    Spec("06 Solar Flare", "Future Bass", 150, "D", "min",
         [("D", "min"), ("Bb", "maj"), ("F", "maj"), ("C", "maj")],
         kick_pat="x...x...x...x...", snare_pat="..x...x...x...x.",
         hat_pat="..x...x...x...x.", bass_voice="fm_pluck_dk",
         bass_pat="x.x...x...x.x...", chord_voice="supersaw",
         lead_voice="supersaw", lead_pat="x.x.x.x.x.x.x.x.",
         vocal="A_AhBreathyVox|Abm_EasyVocal|Bm_CarefreeVocal",
         fx=["riser", "impact"], sections=std_sections(64, 8, 8, 16, 8, 16, 8),
         real_kick=r"DH_Kick_(13|14)$", real_clap=r"DH_Clap_(9|10)$"),
    Spec("07 Deep Current", "Deep House", 122, "D", "min",
         [("D", "min"), ("G", "min"), ("Bb", "maj"), ("A", "maj7")],
         kick_pat="x...x...x...x...", snare_pat="..x...x...x...x.",
         hat_pat="..x...x...x...x.", hat_roll="x.x.x.x.x.x.x.x.",
         bass_voice="fm_pluck_dk", bass_pat="x.....x.x.....x.",
         chord_voice="pluck", chord_every=1, lead_voice="pluck",
         lead_pat="x.x.x.x.x.x.x.x.", vocal="C_OhMyGodVox|Cm_HeyVocal",
         fx=["riser"], sections=std_sections(64, 12, 8, 12, 8, 16, 8),
         real_kick=r"DH_Kick_(1|2)$", real_clap=r"DH_Clap_(1|2)$"),
    Spec("08 Chrome Runner", "Electro / Big Room", 128, "F#", "min",
         [("F#", "min"), ("D", "maj"), ("A", "maj"), ("E", "maj")],
         kick_pat="x...x...x...x...", snare_pat="..x...x...x...x.",
         hat_pat="x.x.x.x.x.x.x.x.", bass_voice="sub808_dk",
         bass_pat="x.x.x.x.x.x.x.x.", chord_voice="supersaw", chord_every=2,
         lead_voice="supersaw", lead_pat="..x...x...x...x.",
         vocal="E_HeyVocal|Ebm_ScatVocal", fx=["riser", "impact", "rev_crash"],
         sections=std_sections(64, 8, 8, 16, 8, 16, 8),
         real_kick=r"DH_Kick_(15|16)$", real_clap=r"DH_Clap_(13|14)$"),
    Spec("09 Neon Circuit", "Peak-Time Techno", 132, "A", "min",
         [("A", "min"), ("F", "maj"), ("C", "maj"), ("G", "maj")],
         kick_pat="x...x...x...x...", snare_pat="..x...x...x...x.",
         hat_pat="..x...x...x...x.", hat_roll="x.x.x.x.x.x.x.x.",
         perc_pat="x.x..x.x.x..x.x.",
         bass_voice="hoover_dk", bass_pat="x.x.x.x.x.x.x.x.",
         chord_voice="pluck", chord_every=1,
         lead_voice="trance_lead", lead_pat="x.x.x.x.x.x.x.x.",
         vocal="IVox|EeyaVox", fx=["riser", "impact", "sweep_down"],
         sections=std_sections(64, 12, 8, 16, 8, 12, 8),
         real_kick=r"DH_Kick_(17|18)$", real_clap=r"DH_Clap_(15|16)$"),
    Spec("10 Velvet Machine", "Melodic Techno", 124, "F", "min",
         [("F", "min"), ("Db", "maj"), ("Ab", "maj"), ("Eb", "maj7")],
         kick_pat="x...x...x...x...", snare_pat="..x...x...x...x.",
         hat_pat="..x...x...x...x.", hat_roll="....x.x.x.x.x.x",
         bass_voice="reese_dk", bass_pat="x.......x...x.....",
         chord_voice="pad", chord_style="sustain", chord_every=2,
         lead_voice="supersaw", lead_pat="x.x.x...x...x.x.",
         vocal="F2_Oohh|G2_Aahh", fx=["riser", "impact"],
         sections=std_sections(64, 16, 8, 12, 8, 12, 8),
         real_kick=r"DH_Kick_(3|4)$", real_clap=r"DH_Clap_(3|4)$"),
    Spec("11 Pressure Drop", "Drum & Bass / Neurofunk", 174, "E", "min",
         [("E", "min"), ("G", "min"), ("B", "min"), ("D", "maj")],
         bars=48, kick_pat="x.......x...x.....",
         snare_pat="....x.......x.....",
         hat_pat="x.x.x.x.x.x.x.x.",
         bass_voice="reese_dk", bass_pat="x.x.x.x.x.x.x.x.",
         chord_voice="pad", chord_style="sustain", chord_every=2,
         lead_voice="pluck", lead_pat="x.xxx.xxx.xxx.xxx",
         fx=["riser", "impact", "rev_crash"],
         sections=[(0, 8, {"hat": 1, "pad": 1}), (8, 16, {"hat": 1, "pad": 1, "kick": 1, "bass": 1}),
                   (16, 28, {"drums": 1, "bass": 1, "chord": 1, "lead": 1, "hat": 1}),
                   (28, 36, {"pad": 1, "lead": 1, "vocal": 1}),
                   (36, 44, {"drums": 1, "bass": 1, "chord": 1, "lead": 1, "hat": 1, "fx": 1}),
                   (44, 48, {"drums": 1, "bass": 1, "hat": 1, "fx": 1})],
         real_kick=r"DH_Kick_(19|20)$", real_clap=r"DH_Clap_(17|18)$"),
    Spec("12 Moonlit Garage", "UK Garage", 132, "C", "min",
         [("C", "min"), ("Eb", "maj"), ("Ab", "maj"), ("Bb", "maj7")],
         kick_pat="x..x..x...x..x...",
         snare_pat="..x..x...x..x...",
         hat_pat="x.x.x.x.x.x.x.x.",
         bass_voice="fm_pluck_dk", bass_pat="x..x..x...x..x...",
         chord_voice="pluck", chord_every=1,
         lead_voice="pluck", lead_pat="x.x.x.x.x.x.x.x.",
         vocal="C_OhMyGodVox|Cm_HeyVocal", fx=["riser", "rev_crash"],
         sections=std_sections(64, 8, 8, 16, 8, 16, 8),
         real_kick=r"DH_Kick_(5|6)$", real_clap=r"DH_Clap_(5|6)$"),
    Spec("13 Slow Burn", "Moombahton", 108, "G", "min",
         [("G", "min"), ("Eb", "maj"), ("C", "maj"), ("D", "min7")],
         kick_pat="x.....x...x.....", snare_pat="..x...x...x...x.",
         hat_pat="..x...x...x...x.", hat_roll="x.x.x.x.x.x.x.x.",
         bass_voice="sub808_dk", bass_pat="x.......x.x.....",
         chord_voice="supersaw", chord_every=2,
         lead_voice="vocal_ah", lead_pat="x..x..x...x..x..",
         vocal="Dm_OhAh|G2_Aahh", fx=["riser", "impact"],
         sections=std_sections(64, 12, 8, 12, 8, 16, 8),
         real_kick=r"DH_Kick_(9|10)$", real_clap=r"DH_Clap_(7|8)$"),
    Spec("14 Afterhours", "Hard Techno", 150, "D", "min",
         [("D", "min"), ("A", "min"), ("F", "maj"), ("G", "min")],
         kick_pat="x...x...x...x...", snare_pat="..x...x...x...x.",
         hat_pat="x.x.x.x.x.x.x.x.", hat_roll="x.x.x.x.x.x.x.x.",
         perc_pat="x.xx.x.xx.x.xx.x",
         bass_voice="hoover_dk", bass_pat="x.x.x.x.x.x.x.x.",
         chord_voice="pluck", chord_every=1,
         lead_voice="trance_lead", lead_pat="x.x.x.x.x.x.x.x.",
         fx=["riser", "impact", "sweep_down", "rev_crash"],
         sections=std_sections(64, 8, 8, 16, 4, 20, 8),
         real_kick=r"DH_Kick_(11|12)$", real_clap=r"DH_Clap_(11|12)$"),
    Spec("15 Heaven's Gate", "Uplifting Trance", 138, "A", "min",
         [("A", "min"), ("F", "maj"), ("C", "maj"), ("G", "maj")],
         kick_pat="x...x...x...x...", snare_pat="..x...x...x...x.",
         hat_pat="..x...x...x...x.",
         bass_voice="reese_dk", bass_pat="x.x.x.x.x.x.x.x.",
         chord_voice="supersaw", chord_every=1,
         lead_voice="trance_lead", lead_pat="x.xx.x.x.x.xx.x.",
         vocal="E_HeyVocal|C_OhMyGodVox", fx=["riser", "impact"],
         sections=std_sections(64, 8, 8, 16, 8, 16, 8),
         real_kick=r"DH_Kick_(2|3)$", real_clap=r"DH_Clap_(4|5)$"),
    Spec("16 Acid Rain", "Acid Techno", 135, "E", "min",
         [("E", "min"), ("G", "min"), ("D", "maj"), ("A", "min")],
         kick_pat="x...x...x...x...", snare_pat="..x...x...x...x.",
         hat_pat="x.x.x.x.x.x.x.x.", hat_roll="x.x.x.x.x.x.x.x.",
         bass_voice="fm_pluck_dk", bass_pat="x.x.x.x.x.x.x.x.",
         chord_voice="pluck", chord_every=1,
         lead_voice="trance_lead", lead_pat="x.xxx.x.xxx.x.xx",
         fx=["riser", "impact", "sweep_down"],
         sections=std_sections(64, 8, 8, 16, 8, 16, 8),
         real_kick=r"DH_Kick_(6|7)$", real_clap=r"DH_Clap_(6|7)$"),
    Spec("17 Goldrush", "Progressive House", 124, "B", "min",
         [("B", "min"), ("G", "maj"), ("D", "maj"), ("A", "maj")],
         kick_pat="x...x...x...x...", snare_pat="..x...x...x...x.",
         hat_pat="..x...x...x...x.", hat_roll="....x.x.x.x.x.x",
         bass_voice="fm_pluck_dk", bass_pat="x.....x.x.....x.",
         chord_voice="pad", chord_style="sustain", chord_every=2,
         lead_voice="supersaw", lead_pat="x.x...x...x.x...",
         vocal="B_Eyeball|EeyaVox", fx=["riser", "impact"],
         sections=std_sections(64, 12, 8, 12, 8, 16, 8),
         real_kick=r"DH_Kick_(8|9)$", real_clap=r"DH_Clap_(8|9)$"),
    Spec("18 Midnight Runner", "Melodic House", 122, "C", "min",
         [("C", "min"), ("Ab", "maj"), ("F", "maj"), ("G", "min7")],
         kick_pat="x...x...x...x...", snare_pat="..x...x...x...x.",
         hat_pat="..x...x...x...x.", hat_roll="x.x.x.x.x.x.x.x.",
         bass_voice="fm_pluck_dk", bass_pat="x.....x.x.....x.",
         chord_voice="supersaw", chord_every=1,
         lead_voice="pluck", lead_pat="x.x.x.x.x.x.x.x.",
         vocal="Cm_HeyVocal|Dm_OhAh", fx=["riser"],
         sections=std_sections(64, 12, 8, 12, 8, 16, 8),
         real_kick=r"DH_Kick_(4|5)$", real_clap=r"DH_Clap_(2|3)$"),
    Spec("19 Concrete Jungle", "Jungle / Liquid DnB", 172, "A", "min",
         [("A", "min"), ("D", "min"), ("F", "maj"), ("G", "min")],
         bars=48, kick_pat="x.....x...x.....",
         snare_pat="....x.......x.....",
         hat_pat="x.x.x.x.x.x.x.x.",
         bass_voice="reese_dk", bass_pat="x.x.x.x.x.x.x.x.",
         chord_voice="pad", chord_style="sustain", chord_every=2,
         lead_voice="pluck", lead_pat="x.xxx.xxx.xxx.xxx",
         vocal="E_HeyVocal|A_AhBreathyVox", fx=["riser", "impact", "rev_crash"],
         sections=[(0, 8, {"hat": 1, "pad": 1}), (8, 16, {"hat": 1, "pad": 1, "kick": 1, "bass": 1}),
                   (16, 28, {"drums": 1, "bass": 1, "chord": 1, "lead": 1, "hat": 1}),
                   (28, 36, {"pad": 1, "lead": 1, "vocal": 1}),
                   (36, 44, {"drums": 1, "bass": 1, "chord": 1, "lead": 1, "hat": 1, "fx": 1}),
                   (44, 48, {"drums": 1, "bass": 1, "hat": 1, "fx": 1})],
         real_kick=r"DH_Kick_(20|21)$", real_clap=r"DH_Clap_(19|20)$"),
    Spec("20 Starlight", "Big Room Anthem", 128, "G", "min",
         [("G", "min"), ("Eb", "maj"), ("Bb", "maj"), ("D", "maj")],
         kick_pat="x...x...x...x...", snare_pat="..x...x...x...x.",
         hat_pat="x.x.x.x.x.x.x.x.",
         bass_voice="sub808_dk", bass_pat="x...x...x...x...",
         chord_voice="supersaw", chord_every=2,
         lead_voice="supersaw", lead_pat="..x...x...x...x.",
         vocal="B_Eyeball|Dm_OhAh", fx=["riser", "impact", "rev_crash"],
         sections=std_sections(64, 8, 8, 16, 8, 16, 8),
         real_kick=r"DH_Kick_(12|13)$", real_clap=r"DH_Clap_(10|11)$"),
]

# library manifest (needed by vocal_sample)
LIB = json.load(open(os.path.join(ROOT, "samples", "library", "manifest.json"),
                     encoding="utf-8"))


def build(spec: Spec) -> Song:
    total = spec.bars
    tonic = root_midi(spec.key, 3)
    prog_roots = [root_midi(r, 3) for r, q in spec.prog]
    prog_chords = [triad(r, q) for r, (_, q) in zip(prog_roots, spec.prog)]
    tracks = []

    def in_section(bar, flag):
        for a, b, f in spec.sections:
            if a <= bar < b:
                return f.get(flag, 0)
        return 0

    # ---------- drums ----------
    kick_path = L("kick", spec.real_kick) if spec.real_kick else C("kick_synth")
    clap_path = L("snare", spec.real_clap) if spec.real_clap else C("clap")
    hat_path = L("hat", spec.real_hat) if spec.real_hat else C("hat_closed")

    kick_pos, clap_pos, hat_pos, roll_pos, perc_pos = [], [], [], [], []
    for bar in range(total):
        if in_section(bar, "drums") or in_section(bar, "kick"):
            kick_pos += [bar * TICKS_PER_BAR + i * TICKS_PER_16TH
                         for i, c in enumerate(spec.kick_pat) if c == "x"]
        if in_section(bar, "drums"):
            clap_pos += [bar * TICKS_PER_BAR + i * TICKS_PER_16TH
                         for i, c in enumerate(spec.snare_pat) if c == "x"]
        if in_section(bar, "hat"):
            hat_pos += [bar * TICKS_PER_BAR + i * TICKS_PER_16TH
                        for i, c in enumerate(spec.hat_pat) if c == "x"]
            if spec.hat_roll:
                roll_pos += [bar * TICKS_PER_BAR + i * TICKS_PER_16TH
                             for i, c in enumerate(spec.hat_roll) if c == "x"]
        if in_section(bar, "perc") and spec.perc_pat:
            perc_pos += [bar * TICKS_PER_BAR + i * TICKS_PER_16TH
                         for i, c in enumerate(spec.perc_pat) if c == "x"]

    if kick_pos:
        tracks.append(drum_track(kick_path, "Kick", kick_pos, vol=112,
                                  fx=[FX_DUALFILTER(cut1=45, cut2=9000, mix=-0.2)]))
    if clap_pos:
        tracks.append(drum_track(clap_path, "Clap", clap_pos, vol=100,
                                  fx=[REVERB_FREEVERB3(wet=0.18, room=0.55)]))
    if hat_pos:
        tracks.append(drum_track(hat_path, "Hat", hat_pos, vol=80, pan=-14))
    if roll_pos:
        tracks.append(drum_track(C("hat_closed"), "HatRoll", roll_pos, vol=62,
                                  pan=16))
    if perc_pos:
        p = L("perc", spec.perc_lib) if spec.perc_lib else C("clap")
        tracks.append(drum_track(p, "Perc", perc_pos, vol=70, pan=28))

    # ---------- bass ----------
    bass = Voice(spec.bass_voice, "Bass", vol=116,
                 fx=[FX_DUALFILTER(cut1=140, cut2=5200, mix=-0.12, res1=0.5),
                     FX_AMPLIFIER(volume=120)])
    for bar in range(total):
        if not in_section(bar, "bass"):
            continue
        r = prog_roots[bar % len(prog_roots)]
        for pit, tk, ln in hits(bar, spec.bass_pat, [r + spec.bass_oct],
                                length=100):
            bass.add(pit, tk, ln)
    tracks += bass.tracks()

    # ---------- chords / pads ----------
    if spec.chord_voice == "pad":
        cv = chord_voice("pad", "Pad", prog_chords, 0, spec.chord_every, total,
                         vol=64, note_len=spec.chord_every * TICKS_PER_BAR - 30,
                         fx=[REVERB_CALF(wet=0.42), FX_STEREO(width=44),
                             FX_DUALFILTER(cut1=260, cut2=6000, mix=-0.3)],
                         style="sustain")
    else:
        cv = chord_voice(spec.chord_voice, "Chord", prog_chords, 0,
                         spec.chord_every, total, vol=76, note_len=140,
                         fx=[REVERB_FREEVERB3(wet=0.24, room=0.88),
                             FX_STEREO(width=40),
                             FX_DUALFILTER(cut1=700, cut2=11000, mix=-0.3)])
    tracks += cv.tracks()

    # ---------- lead ----------
    if spec.lead_voice:
        lead = Voice(spec.lead_voice, "Lead", vol=90,
                     fx=[REVERB_FREEVERB3(wet=0.32, room=0.94, damp=0.45),
                         VINTAGE_DELAY(wet=0.24), FX_STEREO(width=42)])
        scale = [0, 3, 5, 7, 10] if spec.scale == "min" else [0, 2, 4, 7, 9, 11]
        for bar in range(total):
            if not in_section(bar, "lead"):
                continue
            base = prog_roots[bar % len(prog_roots)] + 12 + spec.lead_oct
            hits_ = [t for t in hits(bar, spec.lead_pat, [base], length=100)]
            for i, (pit, tk, ln) in enumerate(hits_):
                deg = scale[i % len(scale)]
                lead.add(base + deg - scale[0], tk, ln)
        tracks += lead.tracks()

    # ---------- vocals (real library one-shots, pitched to the song key) ----
    if spec.vocal:
        vpath, src_root = vocal_sample(spec.vocal.split("|")[0])
        if vpath:
            tgt = tonic
            key = lmms_key(tgt) if src_root is None else lmms_key(tgt)
            vnotes = []
            for bar in range(total):
                if not in_section(bar, "vocal"):
                    continue
                for i in (2, 6, 10, 14):
                    vnotes.append(Note(key, bar * TICKS_PER_BAR + i * TICKS_PER_16TH, 110))
            vt = track_sample(vpath, "Vox", [pat(vnotes, 0, 1)], vol=92,
                              fx=[REVERB_CALF(wet=0.38),
                                  FX_DUALFILTER(cut1=320, cut2=10000, mix=-0.2),
                                  TAP_ECHO(wet=0.2, time=280)])
            tracks.append(vt)

    # ---------- FX ----------
    fx_map = {"riser": ("riser", 0.78, 8 * TICKS_PER_BAR),
              "impact": ("impact", 96, 2 * TICKS_PER_BAR),
              "rev_crash": ("rev_crash", 70, TICKS_PER_BAR),
              "sweep_down": ("sweep_down", 74, 4 * TICKS_PER_BAR),
              "sweep_up": ("sweep_up", 72, 4 * TICKS_PER_BAR)}
    for i, f in enumerate(spec.fx):
        nm, vol, ln = fx_map[f]
        start = total - 8 if f in ("riser", "sweep_down", "sweep_up") else total // 2
        tracks.append(drum_track(C(nm), nm + "FX", [start * TICKS_PER_BAR],
                                  vol=vol, length=ln))

    return Song(name=spec.title, bpm=spec.bpm, tracks=tracks,
                master_fx=[FX_STEREO(width=spec.master_width),
                           HARD_LIMITER(wet=1.0),
                           FX_AMPLIFIER(volume=100)])


if __name__ == "__main__":
    only = sys.argv[1:]
    for s in SPECS:
        if only and not any(o.lower() in s.title.lower() for o in only):
            continue
        song = build(s)
        path = os.path.join(ROOT, "projects", s.title.replace(" ", "_") + ".mmpp")
        write_song(song, path)
        print(f"{s.title:<20} {s.genre:<26} {s.bpm:>4} BPM  {len(song.tracks):>3} tracks"
              f"  -> {os.path.basename(path)}", flush=True)
