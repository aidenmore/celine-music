"""
songkit.py - High-level LMMS song construction helpers.

Provides track factories for samples, LMMS presets (.xpf) and ZynAddSubFX
presets (.xiz), plus FX chain builders and musical pattern helpers.
"""
from __future__ import annotations

import copy
import os
import xml.etree.ElementTree as ET

from mmpp import (Song, InstrumentTrack, Pattern, Note, Effect, LadspaEffect,
                  write_song, TICKS_PER_BAR, TICKS_PER_BEAT, TICKS_PER_16TH)
import presets as P

# --------------------------------------------------------------------- FX ----
def fx_native(name: str, ctrl: dict, wet: float = 1.0, on: int = 1,
              gate: float = 0.0) -> ET.Element:
    """Native LMMS effect: ctrl = {controlElementName: {attr: value}}."""
    e = ET.Element("effect", {
        "on": str(on), "wet": str(wet),
        "autoquit_denominator": "1", "gate": str(gate),
        "name": name, "autoquit_numerator": "1", "syncmode": "0",
        "autoquit": "2400",
    })
    for celem, attrs in ctrl.items():
        ch = ET.SubElement(e, celem)
        for k, v in attrs.items():
            ch.set(k, str(v))
    ET.SubElement(e, "key")
    return e


def fx_ladspa(file: str, plugin: str, ports: dict, wet: float = 1.0,
              on: int = 1, gate: float = 0.0) -> ET.Element:
    """LADSPA effect. `file` is the plugin library base name (e.g. 'calf'),
    `ports` maps LADSPA control-port index -> value."""
    e = ET.Element("effect", {
        "on": str(on), "wet": str(wet),
        "autoquit_denominator": "1", "gate": str(gate),
        "name": "ladspaeffect", "autoquit_numerator": "1", "syncmode": "0",
        "autoquit": "2400",
    })
    ctrls = ET.SubElement(e, "ladspacontrols", {"ports": str(len(ports))})
    for idx, val in sorted(ports.items()):
        p = ET.SubElement(ctrls, f"port{idx:02d}")
        p.set("data", str(val))
    key = ET.SubElement(e, "key")
    ET.SubElement(key, "attribute", {"name": "file", "value": file})
    ET.SubElement(key, "attribute", {"name": "plugin", "value": plugin})
    return e


# Verified LADSPA port maps (harvested from LMMS's own shipped presets)
REVERB_FREEVERB3 = lambda wet=0.35, room=0.8, damp=0.4, width=0.5: fx_ladspa(
    "cmt", "freeverb3", {4: 0, 5: room, 6: 0, 7: damp, 8: 1, 9: width}, wet=wet)
REVERB_PLATE = lambda wet=0.3: fx_ladspa(
    "caps", "Plate2x2", {2: 0.5, 3: 0.37, 4: 0.25, 5: 0.25}, wet=wet)
REVERB_CALF = lambda wet=0.3: fx_ladspa(
    "calf", "Reverb", {7: 0, 8: 0, 9: 0, 10: 1, 11: 0.5, 12: 1, 13: 0, 14: 0, 15: 0},
    wet=wet)
SATURATOR = lambda wet=1.0: fx_ladspa(
    "calf", "Saturator", {4: 0, 5: 1.02, 6: 0.96, 7: 0.5, 12: 5.05, 13: 10,
                          15: 0, 16: 0, 17: 0, 18: 0, 19: 0, 20: 16, 21: 0}, wet=wet)
VINTAGE_DELAY = lambda wet=0.3, time=0.36: fx_ladspa(
    "calf", "VintageDelay", {4: 144.1, 5: 16, 6: 8, 7: 8, 8: 0.5, 9: 0.39,
                              10: 2, 11: 1, 12: 1, 13: 1}, wet=wet)
MULTI_CHORUS = lambda wet=0.4: fx_ladspa(
    "calf", "MultiChorus", {4: 3.17, 5: 10.0, 6: 0.7, 7: 180, 8: 4, 9: 212.4,
                             10: 2, 11: 1, 12: 99.95, 13: 2998.5, 14: 0.125,
                             15: 0.38}, wet=wet)
CLIP = lambda wet=1.0: fx_ladspa("caps", "Clip", {1: 50.76, 11: 50.76}, wet=wet)
HARD_LIMITER = lambda wet=1.0: fx_ladspa(
    "hard_limiter_1413", "hardLimiter", {0: -4.875, 1: 1, 2: 0, 10: -4.875,
                                         11: 1, 12: 0}, wet=wet)
FAST_LIMITER = lambda wet=1.0: fx_ladspa(
    "fast_lookahead_limiter_1913", "fastLookaheadLimiter", {0: 0, 1: 0, 2: 507.45},
    wet=wet)
AMP_STEREO = lambda wet=1.0, gain=5.46: fx_ladspa("cmt", "amp_stereo", {0: gain},
                                                   wet=wet)
TAP_ECHO = lambda wet=0.3, time=320: fx_ladspa(
    "tap_echo", "tap_stereo_echo", {0: time, 1: 50, 2: 430, 3: 50, 4: 0, 5: 0,
                                     6: -70, 7: 1, 8: 0, 9: 1}, wet=wet)
TAP_AUTOPAN = lambda wet=0.6: fx_ladspa(
    "tap_autopan", "tap_autopan", {0: 0.2, 1: 27, 2: 10.125}, wet=wet)
TAP_CHORUS = lambda wet=0.4: fx_ladspa(
    "tap_chorusflanger", "tap_chorusflanger",
    {0: 2.8, 1: 90, 2: 100, 3: 0, 4: 20, 5: 0, 6: 0}, wet=wet)
DC_REMOVE = lambda wet=1.0: fx_ladspa("dc_remove_1207", "dcRemove", {}, wet=wet)

# Native LMMS effects (control element names verified against shipped presets)
FX_DUALFILTER = lambda cut1=800, cut2=8000, res1=0.7, res2=0.7, mix=-0.3, g1=100, g2=100: \
    fx_native("dualfilter", {"DualFilterControls": {
        "gain1": g1, "gain2": g2, "cut1": cut1, "cut2": cut2, "mix": mix,
        "res1": res1, "res2": res2, "filter1": "1", "filter2": "1",
        "enabled1": "1", "enabled2": "1", "scale_type": "linear"}})
FX_AMPLIFIER = lambda volume=100, left=100, right=100, pan=0: \
    fx_native("amplifier", {"AmplifierControls": {
        "volume": volume, "left": left, "right": right, "pan": pan}})
FX_STEREO = lambda width=30: fx_native("stereoenhancer", {"stereoenhancercontrols": {
    "width": width}})
FX_BASSBOOST = lambda ratio=2, freq=100, gain=1: fx_native(
    "bassbooster", {"bassboostercontrols": {"ratio": ratio, "freq": freq, "gain": gain}})
FX_STEREOMATRIX = lambda ll=-0.3, lr=-0.3, rl=-0.3, rr=-0.3: fx_native(
    "stereomatrix", {"stereomatrixcontrols": {
        "l-l": ll, "l-r": lr, "r-l": rl, "r-r": rr}})


# ----------------------------------------------------------------- tracks ----
def _patterns_xml(patterns):
    return patterns


def track_sample(sample_path: str, name: str, patterns, vol=100, pan=0,
                 basenote=57, fx=None, amp=210, stutter=0, reversed_=0,
                 looped=0, sframe=0, lframe=0, eframe=1) -> InstrumentTrack:
    """A track that plays a WAV sample via LMMS's AudioFileProcessor."""
    src = os.path.abspath(sample_path).replace("\\", "/")
    return InstrumentTrack(
        name=name, instrument="audiofileprocessor",
        instrument_params={"interp": "1", "reversed": str(reversed_),
                           "looped": str(looped), "sframe": str(sframe),
                           "lframe": str(lframe), "eframe": str(eframe),
                           "src": src, "amp": str(amp), "stutter": str(stutter)},
        patterns=patterns, vol=vol, pan=pan, basenote=basenote, fxchain=fx or [])


def track_kicker(name: str, patterns, vol=100, pan=0, basenote=57, fx=None,
                 **params) -> InstrumentTrack:
    base = {"env": "1", "distend": "2", "noise": "0", "version": "1",
            "startfreq": "200", "dist": "2", "endfreq": "5", "syncmode": "0",
            "slope": "1", "decay_denominator": "4", "decay_numerator": "4",
            "decay": "213", "startnote": "0", "gain": "5", "click": "0",
            "endnote": "0"}
    base.update({k: str(v) for k, v in params.items()})
    return InstrumentTrack(name=name, instrument="kicker",
                           instrument_params=base, patterns=patterns,
                           vol=vol, pan=pan, basenote=basenote, fxchain=fx or [])


def track_preset(xpf_path: str, name: str, patterns, vol=100, pan=0,
                 basenote=57, fx=None, keep_fx=False, scale=1.0) -> InstrumentTrack:
    """Build a track from an LMMS .xpf preset (instrument + envelopes)."""
    data = P.load_xpf(xpf_path)
    if data is None:
        raise ValueError(f"cannot load preset {xpf_path}")
    inst = copy.deepcopy(data["instrument"])
    eld = copy.deepcopy(data["eldata"]) if data["eldata"] is not None else None
    preset_fx = []
    if keep_fx and data["fxchain"] is not None:
        preset_fx = [copy.deepcopy(e) for e in data["fxchain"]
                     if e.tag == "effect"]
    chain = preset_fx + list(fx or [])
    t = InstrumentTrack(name=name, instrument_element=inst, eldata_element=eld,
                        patterns=patterns, vol=int(vol * scale), pan=pan,
                        basenote=basenote, fxchain=chain)
    return t


def track_zyn(xiz_path: str, name: str, patterns, vol=100, pan=0,
              basenote=57, fx=None) -> InstrumentTrack:
    """Build a track from a ZynAddSubFX .xiz master preset."""
    data = P.load_xiz(xiz_path)
    if data is None:
        raise ValueError(f"cannot load zyn preset {xiz_path}")
    inst = ET.Element("instrument", {"name": "zynaddsubfx"})
    variant = ET.SubElement(inst, "zynaddsubfx")
    inst.append(data)
    return InstrumentTrack(name=name, instrument_element=inst,
                           patterns=patterns, vol=vol, pan=pan,
                           basenote=basenote, fxchain=fx or [])


# ----------------------------------------------------------------- music -----
NOTE_NAMES = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4,
              "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9,
              "A#": 10, "Bb": 10, "B": 11}


def midi(name: str) -> int:
    """'F#3' -> LMMS note key.  LMMS key = MIDI note - 12 (verified by
    frequency measurement against LMMS 1.2.2's own engine)."""
    i = 2 if len(name) > 1 and name[1] in "#b" else 1
    pitch = name[:i]
    octv = int(name[i:])
    if pitch not in NOTE_NAMES:
        raise ValueError(f"bad note name {name!r}")
    return 12 * (octv + 1) + NOTE_NAMES[pitch] - 12


def lmms_key(midi_note: int) -> int:
    """MIDI note number -> LMMS note key."""
    return midi_note - 12


def hz(midi_note: int) -> float:
    """MIDI note number -> frequency in Hz."""
    return 440.0 * 2 ** ((midi_note - 69) / 12.0)


def pat(notes, pos=0, length=TICKS_PER_BAR, name="Default", steps=16) -> Pattern:
    """notes: list of (key, pos, len) or Note objects."""
    ns = []
    for n in notes:
        if isinstance(n, Note):
            ns.append(n)
        else:
            key, p, ln = n
            ns.append(Note(key, p, ln))
    return Pattern(notes=ns, pos=pos, len=length, name=name, steps=steps)


def bars(start_bar: int, count: int) -> tuple[int, int]:
    """(start_tick, length_ticks) for a bar range."""
    return start_bar * TICKS_PER_BAR, count * TICKS_PER_BAR


def on_bar(bar: int) -> int:
    return bar * TICKS_PER_BAR


def grid(bar: int, steps: int = 16, hits=None) -> list[int]:
    """Tick positions inside a bar for the given 1/steps grid."""
    out = []
    step = TICKS_PER_BAR // steps
    for i in range(steps):
        if hits is None or i in hits:
            out.append(bar * TICKS_PER_BAR + i * step)
    return out


def chord(root: str, chord_type: str, octave: int = 3, inversion=0) -> list[int]:
    """Build a MIDI chord from a root name and type."""
    base = midi(f"{root}{octave}")
    ivs = {"min": [0, 3, 7], "maj": [0, 4, 7], "min7": [0, 3, 7, 10],
           "maj7": [0, 4, 7, 11], "sus2": [0, 2, 7], "sus4": [0, 5, 7],
           "min9": [0, 3, 7, 10, 14], "maj9": [0, 4, 7, 11, 14],
           "dim": [0, 3, 6], "aug": [0, 4, 8], "min6": [0, 3, 7, 9],
           "maj6": [0, 4, 7, 9], "m7b5": [0, 3, 6, 10]}[chord_type]
    if inversion:
        ivs = ivs[inversion:] + [i + 12 for i in ivs[:inversion]]
    return [base + i for i in ivs]


def write(song: Song, path: str) -> str:
    return write_song(song, path)
