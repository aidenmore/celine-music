"""
build_songs.py - Compose and render the five tracks.

Each song is a real LMMS 1.2.2 project (.mmpp) built from:
  * custom-rendered, non-stock instruments (samples/custom)
  * real, freely-licensed samples (samples/library)
  * LMMS community presets (Monstro / Organic / TripleOscillator / ZynAddSubFX)
  * verified native LMMS effects and LADSPA FX

Rendered headlessly with `lmms render` and encoded to 320 kbps MP3.
"""
from __future__ import annotations

import json
import os
import re
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mmpp import Song, Pattern, Note, write_song, TICKS_PER_BAR, TICKS_PER_16TH
from songkit import (track_sample, track_kicker, track_preset, track_zyn, pat,
                     fx_native, fx_ladspa, REVERB_FREEVERB3, REVERB_PLATE,
                     REVERB_CALF, SATURATOR, VINTAGE_DELAY, MULTI_CHORUS,
                     CLIP, HARD_LIMITER, FAST_LIMITER, AMP_STEREO, TAP_ECHO,
                     TAP_AUTOPAN, TAP_CHORUS, DC_REMOVE, FX_DUALFILTER,
                     FX_AMPLIFIER, FX_STEREO, FX_BASSBOOST, FX_STEREOMATRIX,
                     lmms_key, hz)
from lmms_render import render_project, to_mp3
import presets as P

from config_paths import ROOT, sample_manifest
CUSTOM = json.load(open(sample_manifest("custom"),
                        encoding="utf-8"))
LIB = json.load(open(sample_manifest("library"),
                     encoding="utf-8"))
CATALOG = P.catalog()

ZYN = {c["rel"]: c for c in CATALOG if c["kind"] == "xiz"}
XPF = {c["rel"]: c for c in CATALOG if c["kind"] == "xpf"}


def L(cat: str, pattern: str, idx: int = 0) -> str:
    """Pick a real sample from the downloaded library."""
    rx = re.compile(pattern, re.I)
    keys = [k for k in LIB if k.startswith(cat + "/") and rx.search(k)]
    if not keys:
        raise KeyError(f"no library sample for {cat}/{pattern}")
    return LIB[keys[idx % len(keys)]]


def C(name: str) -> str:
    return CUSTOM[name]


class Voice:
    """A pitched sample voice -> one LMMS track per distinct pitch."""

    def __init__(self, pool: str, name: str, vol=100, pan=0, fx=None,
                 note_len=180, amp=210, basename=None):
        self.pool = pool
        self.name = name
        self.vol = vol
        self.pan = pan
        self.fx = fx or []
        self.note_len = note_len
        self.amp = amp
        self.basename = basename or pool
        self.notes: dict[int, list[tuple[int, int]]] = {}

    def add(self, midi_note: int, tick: int, length: int | None = None,
            vol: int | None = None):
        self.notes.setdefault(midi_note, []).append(
            (tick, length if length is not None else self.note_len))
        return self

    def tracks(self):
        out = []
        for m, evs in sorted(self.notes.items()):
            key = f"{self.basename}_{m}"
            if key not in CUSTOM:
                print(f"    [skip] missing sample {key} for {self.name}", flush=True)
                continue
            path = CUSTOM[key]
            notes = [Note(lmms_key(m), t, ln) for (t, ln) in evs]
            out.append(track_sample(path, f"{self.name} {m}", [pat(notes, 0, 1)],
                                    vol=self.vol, pan=self.pan, fx=self.fx,
                                    amp=self.amp))
        return out


def hits(start_bar: int, pattern: str, pitches, length: int = 180,
         step: int = TICKS_PER_16TH, vol=None):
    """Expand a 16-step rhythm string into (midi, tick, len) tuples.

    '.' = rest, 'x' = hit.  `pitches` may be a single note or a list cycled
    over the hits.
    """
    if not isinstance(pitches, (list, tuple)):
        pitches = [pitches]
    out = []
    k = 0
    for i, c in enumerate(pattern):
        if c in "xX":
            p = pitches[k % len(pitches)]
            k += 1
            out.append((p, start_bar * TICKS_PER_BAR + i * step, length))
    return out


def chord_voice(prefix: str, name: str, prog, start_bar: int, bars_per: int,
                total_bars: int, vol=100, fx=None, note_len=180, amp=210,
                style="stab"):
    """Voice that plays a chord progression as stabs / sustained pads."""
    v = Voice(prefix, name, vol=vol, fx=fx, note_len=note_len, amp=amp)
    bar = start_bar
    idx = 0
    while bar < total_bars:
        notes = prog[idx % len(prog)]
        if style == "stab":
            for n in notes:
                v.add(n, bar * TICKS_PER_BAR, note_len)
        else:
            for n in notes:
                v.add(n, bar * TICKS_PER_BAR, bars_per * TICKS_PER_BAR - 20)
        bar += bars_per
        idx += 1
    return v


def drum_track(path, name, positions, vol=100, pan=0, fx=None, length=90,
               amp=210):
    notes = [Note(lmms_key(60), p, length) for p in positions]
    return track_sample(path, name, [pat(notes, 0, 1)], vol=vol, pan=pan,
                        fx=fx, amp=amp)


def all_positions(start_bar: int, end_bar: int, every: int = TICKS_PER_BAR):
    return list(range(start_bar * TICKS_PER_BAR, end_bar * TICKS_PER_BAR, every))


# =========================================================== SONG 1 ==========
def neon_drift():
    """FUTURE HOUSE - 126 BPM - F minor"""
    BPM, BARS = 126, 64
    SONG = "01 Neon Drift"
    # Fm - Db - Ab - Eb
    prog_bass = [41, 49, 44, 51]
    prog_chord = [[53, 56, 60], [61, 65, 68], [56, 60, 63], [63, 67, 70]]

    tracks = []
    kick = L("kick", r"DH_Kick_(1|2|3)$")
    clap = L("snare", r"DH_Clap_(1|2)$")
    hat_c = L("hat", r"DH_HiHat_(1|2)$")
    hat_o = L("hat", r"DH_HiHat_(8|9)$")
    perc = L("perc", r"DH_Perc_(1|2)$")
    vocal = L("vocal", r"A_AhBreathyVox")

    # ---- drums
    tracks.append(drum_track(kick, "Kick", all_positions(8, BARS), vol=112,
                              fx=[FX_DUALFILTER(cut1=40, cut2=9000, mix=-0.2,
                                                res1=0.4, res2=0.5)]))
    tracks.append(drum_track(clap, "Clap", hits(16, "..x...x...x...x.",
                                                [60], length=120)[0:0] or
                              [p for _, p, _ in hits(16, "..x...x...x...x.", [60])]
                              + [p + 32 * TICKS_PER_BAR for p in
                                 [p for _, p, _ in hits(16, "..x...x...x...x.", [60])]],
                              vol=104, fx=[REVERB_FREEVERB3(wet=0.20, room=0.6)]))
    tracks.append(drum_track(hat_c, "HatClosed",
                              [p for _, p, _ in hits(8, "x.x.x.x.x.x.x.x.", [60])]
                              + [p for _, p, _ in hits(8, "x.x.x.x.x.x.x.x.", [60])
                                 for p in [p + 8 * TICKS_PER_BAR]],
                              vol=86, pan=-12))
    tracks.append(drum_track(hat_o, "HatOpen",
                              [p for _, p, _ in hits(16, "......x.......x.", [60])]
                              + [p + 16 * TICKS_PER_BAR for p in
                                 [p for _, p, _ in hits(16, "......x.......x.", [60])]],
                              vol=80, pan=12))
    tracks.append(drum_track(perc, "Perc",
                              [p for _, p, _ in hits(16, "..x..x.x..x..x.x", [60])],
                              vol=74, pan=30))

    # ---- bass: FM pluck, sidechain ducked
    bass = Voice("fm_pluck_dk", "Bass", vol=118,
                 fx=[FX_DUALFILTER(cut1=120, cut2=6000, mix=-0.15, res1=0.55),
                     FX_AMPLIFIER(volume=120)])
    for bar in range(8, BARS):
        root = prog_bass[(bar) % 4]
        for pit, tk, ln in hits(bar, "x...x...x...x...", [root], length=120):
            bass.add(pit, tk, ln)
        for pit, tk, ln in hits(bar, "....x.......x...", [root + 12], length=110):
            bass.add(pit, tk, ln)
    tracks += bass.tracks()

    # ---- chords: supersaw stabs
    chords = chord_voice("supersaw", "Chord", prog_chord, 16, 1, BARS,
                          vol=74, note_len=150,
                          fx=[REVERB_FREEVERB3(wet=0.24, room=0.85, damp=0.5),
                              FX_STEREO(width=42)])
    tracks += chords.tracks()

    # ---- pads (sustained) in intro + breakdown
    pads = chord_voice("pad", "Pad", prog_chord, 0, 2, BARS, vol=62,
                       note_len=2 * TICKS_PER_BAR - 30,
                       fx=[REVERB_CALF(wet=0.35), FX_DUALFILTER(cut1=200, cut2=4200,
                                                                 mix=-0.3)],
                       style="sustain")
    tracks += pads.tracks()

    # ---- vocal chops (real sample) + synthetic chops
    vc = Voice("vocal_ah", "VoxSynth", vol=96,
               fx=[REVERB_FREEVERB3(wet=0.30, room=0.9),
                   TAP_ECHO(wet=0.22, time=260)])
    for bar in range(16, 32):
        root = prog_bass[bar % 4]
        for pit, tk, ln in hits(bar, "..x...x..x..x...", [root + 12], length=95):
            vc.add(pit, tk, ln)
    for bar in range(40, 56):
        root = prog_bass[bar % 4]
        for pit, tk, ln in hits(bar, "..x...x..x..x...", [root + 12], length=95):
            vc.add(pit, tk, ln)
    tracks += vc.tracks()

    vox = drum_track(vocal, "VoxReal", [], vol=92)
    vox.patterns = [pat([Note(lmms_key(60), 20 * TICKS_PER_BAR + 6 * TICKS_PER_16TH, 110),
                         Note(lmms_key(60), 28 * TICKS_PER_BAR + 6 * TICKS_PER_16TH, 110),
                         Note(lmms_key(60), 44 * TICKS_PER_BAR + 6 * TICKS_PER_16TH, 110),
                         Note(lmms_key(60), 52 * TICKS_PER_BAR + 6 * TICKS_PER_16TH, 110)],
                        0, 1)]
    vox.fxchain = [REVERB_FREEVERB3(wet=0.32, room=0.9), TAP_ECHO(wet=0.25, time=300)]
    tracks.append(vox)

    # ---- FX
    tracks.append(drum_track(C("riser"), "Riser",
                              [48 * TICKS_PER_BAR, 56 * TICKS_PER_BAR], vol=78,
                              length=8 * TICKS_PER_BAR))
    tracks.append(drum_track(C("impact"), "Impact",
                              [32 * TICKS_PER_BAR, 56 * TICKS_PER_BAR], vol=96,
                              length=2 * TICKS_PER_BAR))
    tracks.append(drum_track(C("vinyl_short"), "Vinyl",
                              [0, 8 * TICKS_PER_BAR, 32 * TICKS_PER_BAR], vol=40,
                              length=8 * TICKS_PER_BAR, amp=60))

    song = Song(name=SONG, bpm=BPM, tracks=tracks,
                master_fx=[FX_STEREO(width=26), HARD_LIMITER(wet=1.0),
                           FX_AMPLIFIER(volume=100)])
    return song


# =========================================================== SONG 2 ==========
def glitch_district():
    """STUTTER HOUSE - 128 BPM - A minor"""
    BPM, BARS = 128, 64
    prog = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G
    roots = [45, 41, 48, 43]

    tracks = []
    kick = L("kick", r"DH_Kick_(4|5)$")
    clap = L("snare", r"DH_Clap_(5|6)$")
    hat_c = L("hat", r"DH_HiHat_(3|4)$")

    tracks.append(drum_track(kick, "Kick", all_positions(8, BARS), vol=110))
    tracks.append(drum_track(clap, "Clap",
                              [p for _, p, _ in hits(8, "..x...x...x...x.", [60])]
                              + [p + 16 * TICKS_PER_BAR for p in
                                 [p for _, p, _ in hits(8, "..x...x...x...x.", [60])]],
                              vol=100, fx=[REVERB_FREEVERB3(wet=0.18, room=0.5)]))
    tracks.append(drum_track(hat_c, "Hat",
                              [p for _, p, _ in hits(8, "x.x.x.x.x.x.x.x.", [60])]
                              + [p + 8 * TICKS_PER_BAR for p in
                                 [p for _, p, _ in hits(8, "x.x.x.x.x.x.x.x.", [60])]],
                              vol=84, pan=-14))

    # rolling 16th bass
    bass = Voice("fm_pluck_dk", "Bass", vol=112,
                 fx=[FX_DUALFILTER(cut1=150, cut2=5200, mix=-0.12, res1=0.5)])
    for bar in range(8, BARS):
        r = roots[bar % 4]
        for pit, tk, ln in hits(bar, "x.x.x.x.x.x.x.x.", [r], length=80):
            bass.add(pit, tk, ln)
    tracks += bass.tracks()

    # STUTTERS: dense 16th/32th repeated chops
    for vi, (pool, vname, vvol) in enumerate(
            [("vocal_eh", "StutterA", 100), ("vocal_oo", "StutterB", 92)]):
        v = Voice(pool, vname, vol=vvol,
                  fx=[REVERB_FREEVERB3(wet=0.26, room=0.85),
                      FX_DUALFILTER(cut1=300, cut2=12000, mix=-0.25)])
        for bar in range(16, 64):
            r = roots[bar % 4]
            pattern = ("x.x.x.x.x.x.x.x." if bar % 8 < 4
                       else "..xx..xx..xx..xx")
            step = TICKS_PER_16TH if bar % 8 < 4 else TICKS_PER_16TH // 2
            for pit, tk, ln in hits(bar, pattern, [r + 12], length=70, step=step):
                v.add(pit, tk, ln)
        tracks += v.tracks()

    # glitch stabs
    st = chord_voice("supersaw", "Stab", prog, 16, 2, BARS, vol=62,
                     note_len=110,
                     fx=[REVERB_PLATE(wet=0.3), FX_DUALFILTER(cut1=800, cut2=9000,
                                                               mix=-0.35)])
    tracks += st.tracks()

    # pad
    pads = chord_voice("pad", "Pad", prog, 0, 2, BARS, vol=58,
                       note_len=2 * TICKS_PER_BAR - 30,
                       fx=[REVERB_CALF(wet=0.4)], style="sustain")
    tracks += pads.tracks()

    # ZynAddSubFX bright lead for the drop
    zyn_rel = next((r for r in ZYN if "Laba170bank/0005-BrightLead" in r), None)
    if zyn_rel:
        lead = track_zyn(ZYN[zyn_rel]["path"], "ZynLead",
                         [pat([Note(lmms_key(p), 24 * TICKS_PER_BAR + i * TICKS_PER_BAR, 170)
                                for i, p in enumerate([57, 60, 64, 69, 64, 60])]
                               + [Note(lmms_key(p), 40 * TICKS_PER_BAR + i * TICKS_PER_BAR, 170)
                                  for i, p in enumerate([57, 60, 64, 69, 64, 60])], 0, 1)],
                         vol=88,
                         fx=[REVERB_FREEVERB3(wet=0.30, room=0.95),
                             FX_DUALFILTER(cut1=600, cut2=11000, mix=-0.2)])
        tracks.append(lead)

    tracks.append(drum_track(C("rev_crash"), "RevCrash",
                              [16 * TICKS_PER_BAR, 40 * TICKS_PER_BAR], vol=72,
                              length=TICKS_PER_BAR))
    tracks.append(drum_track(C("riser"), "Riser",
                              [56 * TICKS_PER_BAR], vol=80, length=8 * TICKS_PER_BAR))
    tracks.append(drum_track(C("sweep_down"), "Sweep",
                              [56 * TICKS_PER_BAR], vol=70, length=8 * TICKS_PER_BAR))

    song = Song(name="02 Glitch District", bpm=BPM, tracks=tracks,
                master_fx=[FX_STEREO(width=30), HARD_LIMITER(wet=1.0),
                           FX_AMPLIFIER(volume=100)])
    return song


# =========================================================== SONG 3 ==========
def phonk_pressure():
    """PHONK - 140 BPM - C minor"""
    BPM, BARS = 140, 64
    prog = [[48, 51, 55], [51, 55, 58], [44, 48, 51], [43, 46, 50]]  # Cm Eb Ab G
    roots = [36, 39, 44, 43]

    tracks = []
    kick = L("kick", r"DH_Kick_(7|8)$")
    tracks.append(drum_track(kick, "Kick", all_positions(0, BARS), vol=116,
                              fx=[SATURATOR(wet=0.8)]))
    tracks.append(drum_track(C("clap"), "Clap",
                              [p for _, p, _ in hits(0, "..x...x...x...x.", [60])]
                              + [p + 32 * TICKS_PER_BAR for p in
                                 [p for _, p, _ in hits(0, "..x...x...x...x.", [60])]],
                              vol=100, fx=[REVERB_FREEVERB3(wet=0.16, room=0.4)]))
    tracks.append(drum_track(C("hat_closed"), "Hat",
                              [p for _, p, _ in hits(0, "x.x.x.x.x.x.x.x.", [60])],
                              vol=80, pan=-18))
    tracks.append(drum_track(C("hat_open"), "HatOpen",
                              [p for _, p, _ in hits(0, "......x.......x.", [60])],
                              vol=76, pan=18))

    # 808 with slides
    sub = Voice("sub808_dk", "808", vol=124,
                fx=[SATURATOR(wet=1.0), FX_AMPLIFIER(volume=130)])
    for bar in range(0, BARS):
        r = roots[bar % 4]
        for pit, tk, ln in hits(bar, "x.....x...x.....", [r], length=150):
            sub.add(pit, tk, ln)
        if bar % 4 == 3:
            sub.add(r, bar * TICKS_PER_BAR + 11 * TICKS_PER_16TH, 90)
    tracks += sub.tracks()

    # dark stab chords
    st = chord_voice("supersaw", "Stab", prog, 8, 2, BARS, vol=58, note_len=140,
                     fx=[SATURATOR(wet=1.0), FX_DUALFILTER(cut1=400, cut2=5200,
                                                           mix=-0.3, res1=0.6),
                         REVERB_PLATE(wet=0.2)])
    tracks += st.tracks()

    # cowbell
    cow = L("perc", r"DH_Perc_(2[5-9]|3[0-5])$")
    tracks.append(drum_track(cow, "Cowbell",
                              [p for _, p, _ in hits(0, "..x...x...x...x.", [60])],
                              vol=66, pan=8, fx=[FX_DUALFILTER(cut1=1200, cut2=9000,
                                                               mix=-0.2)]))

    # vinyl texture throughout
    tracks.append(drum_track(C("vinyl"), "Vinyl", [0], vol=34,
                              length=BARS * TICKS_PER_BAR, amp=70))

    tracks.append(drum_track(C("impact"), "Impact", [32 * TICKS_PER_BAR], vol=100,
                              length=2 * TICKS_PER_BAR))
    tracks.append(drum_track(C("sweep_down"), "Sweep", [60 * TICKS_PER_BAR],
                              vol=78, length=4 * TICKS_PER_BAR))

    song = Song(name="03 Phonk Pressure", bpm=BPM, tracks=tracks,
                master_fx=[FX_STEREO(width=24), HARD_LIMITER(wet=1.0),
                           FX_AMPLIFIER(volume=100)])
    return song


# =========================================================== SONG 4 ==========
def euphoria_engine():
    """RAVE / TRANCE - 140 BPM - G minor"""
    BPM, BARS = 140, 64
    prog = [[55, 58, 62], [46, 50, 53], [48, 52, 55], [50, 53, 57]]  # Gm Bb C Dm
    roots = [43, 46, 48, 50]

    tracks = []
    tracks.append(drum_track(C("kick_synth"), "Kick", all_positions(0, BARS),
                              vol=112, fx=[FX_AMPLIFIER(volume=115)]))
    tracks.append(drum_track(C("snare_synth"), "Snare",
                              [p for _, p, _ in hits(0, "..x...x...x...x.", [60])]
                              + [p + 32 * TICKS_PER_BAR for p in
                                 [p for _, p, _ in hits(0, "..x...x...x...x.", [60])]],
                              vol=92, fx=[REVERB_CALF(wet=0.3)]))
    tracks.append(drum_track(C("hat_closed"), "Hat",
                              [p for _, p, _ in hits(0, "x.x.x.x.x.x.x.x.", [60])],
                              vol=72, pan=-16))
    tracks.append(drum_track(C("hat_open"), "HatOpen",
                              [p for _, p, _ in hits(0, "......x.......x.", [60])],
                              vol=70, pan=16))

    # rolling reese bass
    bass = Voice("reese_dk", "Reese", vol=110,
                 fx=[FX_DUALFILTER(cut1=120, cut2=4200, mix=-0.1, res1=0.55),
                     SATURATOR(wet=0.5)])
    for bar in range(0, BARS):
        r = roots[bar % 4]
        for pit, tk, ln in hits(bar, "x.x.x.x.x.x.x.x.", [r], length=75):
            bass.add(pit, tk, ln)
    tracks += bass.tracks()

    # supersaw lead
    lead = Voice("trance_lead", "Lead", vol=92,
                 fx=[REVERB_FREEVERB3(wet=0.34, room=0.95, damp=0.45),
                     VINTAGE_DELAY(wet=0.26), FX_STEREO(width=44),
                     FX_DUALFILTER(cut1=500, cut2=12000, mix=-0.15)])
    melody = [62, 65, 69, 72, 69, 65, 62, 60]
    for bar in range(16, 60):
        seq = melody if bar % 2 == 0 else [m + 3 for m in melody]
        for i, m in enumerate(seq):
            lead.add(m, bar * TICKS_PER_BAR + i * (TICKS_PER_BAR // 4), 110)
    tracks += lead.tracks()

    # arps
    arp = Voice("pluck", "Arp", vol=66,
                fx=[REVERB_FREEVERB3(wet=0.3, room=0.9),
                    FX_DUALFILTER(cut1=900, cut2=11000, mix=-0.3)])
    for bar in range(8, BARS):
        r = roots[bar % 4] + 12
        for pit, tk, ln in hits(bar, "x.xx.x.xx.x.xx.x.",
                                    [r, r + 3, r + 7, r + 12], length=60):
            arp.add(pit, tk, ln)
    tracks += arp.tracks()

    # big chords
    ch = chord_voice("supersaw", "Chord", prog, 0, 1, BARS, vol=58, note_len=170,
                     fx=[REVERB_CALF(wet=0.38), FX_STEREO(width=40)])
    tracks += ch.tracks()

    # real trance loop texture
    loop = L("loop", r"ttp_mixed_loop_19")
    tracks.append(drum_track(loop, "TTPTexture", [0], vol=46,
                              length=BARS * TICKS_PER_BAR, amp=80))

    tracks.append(drum_track(C("riser"), "Riser", [56 * TICKS_PER_BAR], vol=82,
                              length=8 * TICKS_PER_BAR))
    tracks.append(drum_track(C("impact"), "Impact", [32 * TICKS_PER_BAR], vol=96,
                              length=2 * TICKS_PER_BAR))
    tracks.append(drum_track(C("rev_crash"), "RevCrash", [16 * TICKS_PER_BAR],
                              vol=70, length=TICKS_PER_BAR))

    song = Song(name="04 Euphoria Engine", bpm=BPM, tracks=tracks,
                master_fx=[FX_STEREO(width=32), HARD_LIMITER(wet=1.0),
                           FX_AMPLIFIER(volume=100)])
    return song


# =========================================================== SONG 5 ==========
def eurodreams():
    """EURODANCE - 128 BPM - F minor"""
    BPM, BARS = 128, 64
    prog = [[53, 56, 60], [61, 65, 68], [58, 62, 65], [48, 52, 55]]  # Fm Db Bb C
    roots = [41, 49, 46, 48]

    tracks = []
    kick = L("kick", r"DH_Kick_(10|11)$")
    tracks.append(drum_track(kick, "Kick", all_positions(8, BARS), vol=110))
    tracks.append(drum_track(C("snare_synth"), "Snare",
                              [p for _, p, _ in hits(8, "..x...x...x...x.", [60])]
                              + [p + 32 * TICKS_PER_BAR for p in
                                 [p for _, p, _ in hits(8, "..x...x...x...x.", [60])]],
                              vol=98, fx=[REVERB_CALF(wet=0.42),
                                          FX_DUALFILTER(cut1=400, cut2=9000,
                                                        mix=-0.2)]))
    tracks.append(drum_track(C("hat_closed"), "Hat",
                              [p for _, p, _ in hits(8, "x.x.x.x.x.x.x.x.", [60])]
                              + [p + 8 * TICKS_PER_BAR for p in
                                 [p for _, p, _ in hits(8, "x.x.x.x.x.x.x.x.", [60])]],
                              vol=74, pan=-14))
    tracks.append(drum_track(C("hat_open"), "HatOpen",
                              [p for _, p, _ in hits(8, "......x.......x.", [60])],
                              vol=70, pan=14))

    # hoover bass
    bass = Voice("hoover_dk", "Hoover", vol=112,
                 fx=[FX_DUALFILTER(cut1=160, cut2=5000, mix=-0.15, res1=0.45),
                     FX_AMPLIFIER(volume=120)])
    for bar in range(8, BARS):
        r = roots[bar % 4]
        for pit, tk, ln in hits(bar, "x.......x.......", [r], length=170):
            bass.add(pit, tk, ln)
        for pit, tk, ln in hits(bar, "............x...", [r + 7], length=140):
            bass.add(pit, tk, ln)
    tracks += bass.tracks()

    # emotional pad chords
    pad = chord_voice("pad", "Pad", prog, 0, 2, BARS, vol=66,
                      note_len=2 * TICKS_PER_BAR - 30,
                      fx=[REVERB_CALF(wet=0.45), FX_STEREO(width=46),
                          FX_DUALFILTER(cut1=250, cut2=6000, mix=-0.3)],
                      style="sustain")
    tracks += pad.tracks()

    # piano stabs
    stab = chord_voice("pluck", "PianoStab", prog, 16, 1, BARS, vol=72,
                       note_len=130,
                       fx=[REVERB_FREEVERB3(wet=0.28, room=0.9),
                           FX_DUALFILTER(cut1=400, cut2=11000, mix=-0.25)])
    tracks += stab.tracks()

    # supersaw lead on the chorus
    lead = Voice("supersaw", "Lead", vol=74,
                 fx=[REVERB_FREEVERB3(wet=0.36, room=0.95, damp=0.4),
                     VINTAGE_DELAY(wet=0.24), FX_STEREO(width=42)])
    mel = [[65, 68, 72], [73, 72, 68], [70, 73, 77], [67, 71, 74]]
    for bar in range(32, 60):
        ch = mel[bar % 4]
        for i, m in enumerate(ch):
            lead.add(m, bar * TICKS_PER_BAR + i * (TICKS_PER_BAR // 4), 120)
    tracks += lead.tracks()

    # real vocal for the emotional peak
    vox = L("vocal", r"E_HeyVocal")
    vt = drum_track(vox, "Vox", [], vol=92,
                    fx=[REVERB_CALF(wet=0.4), FX_DUALFILTER(cut1=300, cut2=10000,
                                                            mix=-0.2)])
    vt.patterns = [pat([Note(lmms_key(60), 34 * TICKS_PER_BAR, 150),
                        Note(lmms_key(60), 42 * TICKS_PER_BAR, 150),
                        Note(lmms_key(60), 50 * TICKS_PER_BAR, 150)], 0, 1)]
    tracks.append(vt)

    tracks.append(drum_track(C("riser"), "Riser", [56 * TICKS_PER_BAR], vol=80,
                              length=8 * TICKS_PER_BAR))
    tracks.append(drum_track(C("impact"), "Impact", [32 * TICKS_PER_BAR], vol=94,
                              length=2 * TICKS_PER_BAR))

    song = Song(name="05 Eurodreams", bpm=BPM, tracks=tracks,
                master_fx=[FX_STEREO(width=28), HARD_LIMITER(wet=1.0),
                           FX_AMPLIFIER(volume=100)])
    return song


SONGS = [
    ("01 Neon Drift", neon_drift, "Future House", 126),
    ("02 Glitch District", glitch_district, "Stutter House", 128),
    ("03 Phonk Pressure", phonk_pressure, "Phonk", 140),
    ("04 Euphoria Engine", euphoria_engine, "Rave Trance", 140),
    ("05 Eurodreams", eurodreams, "Eurodance", 128),
]


def main():
    proj_dir = os.path.join(ROOT, "projects")
    out_dir = os.path.join(ROOT, "songs")
    wav_dir = os.path.join(ROOT, "renders")
    log_dir = os.path.join(ROOT, "logs")
    for d in (proj_dir, out_dir, wav_dir, log_dir):
        os.makedirs(d, exist_ok=True)

    only = sys.argv[1:] if len(sys.argv) > 1 else None
    results = []
    for name, fn, genre, bpm in SONGS:
        if only and not any(o.lower() in name.lower() for o in only):
            continue
        print(f"=== {name} ({genre}, {bpm} BPM)", flush=True)
        song = fn()
        mmpp_path = os.path.join(proj_dir, name.replace(" ", "_") + ".mmpp")
        write_song(song, mmpp_path)
        wav_path = os.path.join(wav_dir, name.replace(" ", "_") + ".wav")
        mp3_path = os.path.join(out_dir, name.replace(" ", "_") + ".mp3")
        ok, log = render_project(mmpp_path, wav_path)
        with open(os.path.join(log_dir, name.replace(" ", "_") + ".log"), "w",
                  encoding="utf-8") as fh:
            fh.write(log)
        if not ok:
            print("  RENDER FAILED")
            print(log[-1500:])
            results.append((name, False, 0, 0))
            continue
        with wave.open(wav_path, "rb") as w:
            dur = w.getnframes() / w.getframerate()
            ch, sr = w.getnchannels(), w.getframerate()
        to_mp3(wav_path, mp3_path, "320")
        print(f"  rendered {dur:.1f}s  {ch}ch {sr}Hz  mp3="
              f"{os.path.getsize(mp3_path)/1e6:.1f}MB", flush=True)
        results.append((name, True, dur, os.path.getsize(mp3_path)))

    print("\nSUMMARY")
    for n, ok, d, sz in results:
        print(f"  {'OK ' if ok else 'FAIL'} {n:<22} {d:6.1f}s  {sz/1e6:6.2f} MB")


if __name__ == "__main__":
    main()

