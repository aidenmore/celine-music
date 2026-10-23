"""
render_custom.py - Render every custom (non-stock) instrument sample and FX
used by the songs, plus a manifest the song builder reads.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import synth as S

OUT = S.OUT
MANIFEST = os.path.join(OUT, "manifest.json")


def hz(m: int) -> float:
    return 440.0 * 2 ** ((m - 69) / 12.0)


# ---------------------------------------------------------------- pools -----
# MIDI note pools per instrument voice.
POOLS = {
    # Future-house FM bass (song 1)
    "fm_pluck": {
        "notes": list(range(24, 76)),
        "render": lambda f: S.fm_pluck(f, dur=0.42, ratio=2.0, index=7.0, decay=0.13),
        "dur": 0.42,
    },
    # Supersaw stabs (songs 1, 4, 5)
    "supersaw": {
        "notes": list(range(41, 85)),
        "render": lambda f: S.supersaw(f, dur=1.1, voices=7, detune=0.17,
                                       cut_lo=900, cut_hi=11000, q=0.42,
                                       env_s=0.72, env_r=0.30),
        "dur": 1.1,
    },
    # Trance lead (song 4)
    "trance_lead": {
        "notes": list(range(55, 85)),
        "render": lambda f: S.trance_lead(f, dur=0.9),
        "dur": 0.9,
    },
    # Reese bass (song 4)
    "reese": {
        "notes": list(range(31, 62)),
        "render": lambda f: S.reese(f, dur=0.34),
        "dur": 0.34,
    },
    # Phonk 808 (song 3)
    "sub808": {
        "notes": list(range(24, 60)),
        "render": lambda f: S.sub808(f, dur=0.65, drive=2.8),
        "dur": 0.65,
    },
    # Eurodance hoover bass (song 5)
    "hoover": {
        "notes": list(range(29, 62)),
        "render": lambda f: S.hoover(f, dur=0.55),
        "dur": 0.55,
    },
    # Bright pluck / arp (songs 2, 5)
    "pluck": {
        "notes": list(range(41, 85)),
        "render": lambda f: S.pluck(f, dur=0.40, bright=0.8),
        "dur": 0.40,
    },
    # Synthetic vocal chops (songs 1, 2)
    "vocal_ah": {
        "notes": list(range(41, 80)),
        "render": lambda f: S.vocal_chop(f, dur=0.34, vowel="ah", bright=0.65),
        "dur": 0.34,
    },
    "vocal_eh": {
        "notes": list(range(41, 80)),
        "render": lambda f: S.vocal_chop(f, dur=0.30, vowel="eh", bright=0.7),
        "dur": 0.30,
    },
    "vocal_oo": {
        "notes": list(range(41, 80)),
        "render": lambda f: S.vocal_chop(f, dur=0.40, vowel="oo", bright=0.5),
        "dur": 0.40,
    },
    # Deep-house style pad (song 5, 2)
    "pad": {
        "notes": list(range(41, 85)),
        "render": lambda f: S.supersaw(f, dur=2.6, voices=5, detune=0.10,
                                       cut_lo=700, cut_hi=5200, q=0.25,
                                       env_a=0.25, env_d=0.5, env_s=0.85, env_r=0.7),
        "dur": 2.6,
    },
}

# Sidechain-ducked variants: the amplitude dips at note onset and recovers,
# which produces the pumping feel of a sidechain-compressed bass.
DUCKED = {
    "fm_pluck_dk": ("fm_pluck", 0.55),
    "reese_dk": ("reese", 0.60),
    "sub808_dk": ("sub808", 0.65),
    "hoover_dk": ("hoover", 0.55),
}

# One-shot FX (unpitched)
FX = {
    "riser": lambda: S.riser(4.0),
    "riser_short": lambda: S.riser(2.0),
    "impact": lambda: S.impact(2.0),
    "vinyl": lambda: S.vinyl(4.0),
    "vinyl_short": lambda: S.vinyl(2.0),
    "sweep_up": lambda: S.noise_sweep(2.0, up=True),
    "sweep_down": lambda: S.noise_sweep(2.0, up=False),
    "rev_crash": lambda: S.reverse_crash(1.6),
    "clap": lambda: S.clap_layer(0.36),
    "hat_closed": lambda: S.hat(0.055, open_=False),
    "hat_open": lambda: S.hat(0.32, open_=True),
    "kick_synth": lambda: S.kick_synth(0.44),
    "snare_synth": lambda: S.snare_synth(0.24),
    "tom_low": lambda: S.tom(110, 0.34),
    "tom_mid": lambda: S.tom(170, 0.28),
    "tom_high": lambda: S.tom(240, 0.24),
}

# Custom wavetables for LMMS's Watsyn instrument
WAVETABLES = {
    "wt_bright_saw": [0.0, 1.0, 0.75, 0.55, 0.42, 0.33, 0.27, 0.22, 0.18,
                      0.15, 0.12, 0.10, 0.08, 0.06, 0.05, 0.04],
    "wt_harmonic": [0.0, 1.0, 0.0, 0.5, 0.0, 0.33, 0.0, 0.25, 0.0, 0.2,
                    0.0, 0.16, 0.0, 0.14, 0.0, 0.12],
    "wt_reedy": [0.0, 1.0, 0.2, 0.85, 0.15, 0.65, 0.12, 0.5, 0.1, 0.4,
                 0.08, 0.33, 0.06, 0.28, 0.05, 0.24],
}


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = {}

    for inst, spec in POOLS.items():
        for m in spec["notes"]:
            name = f"{inst}_{m}"
            path = os.path.join(OUT, name + ".wav")
            if not os.path.exists(path):
                x = spec["render"](hz(m))
                S.write_wav(name, x)
            manifest[name] = path
        print(f"pool {inst}: {len(spec['notes'])} notes", flush=True)

    for name, fn in FX.items():
        path = os.path.join(OUT, name + ".wav")
        if not os.path.exists(path):
            S.write_wav(name, fn())
        manifest[name] = path
    print(f"fx: {len(FX)} one-shots", flush=True)

    for dname, (base, depth) in DUCKED.items():
        spec = POOLS[base]
        for m in spec["notes"]:
            name = f"{dname}_{m}"
            path = os.path.join(OUT, name + ".wav")
            if not os.path.exists(path):
                x = S.duck(spec["render"](hz(m)), depth=depth,
                           hold=0.015, release=0.13)
                S.write_wav(name, x)
            manifest[name] = path
    print(f"ducked voices: {len(DUCKED)}", flush=True)

    for name, harm in WAVETABLES.items():
        path = os.path.join(OUT, name + ".wav")
        if not os.path.exists(path):
            S.wavetable(name, harm)
        manifest[name] = path
    print(f"wavetables: {len(WAVETABLES)}", flush=True)

    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    print("total samples:", len(manifest))


if __name__ == "__main__":
    main()
