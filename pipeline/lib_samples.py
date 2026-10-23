"""Build a normalized sample library from all downloaded sources + a manifest."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

ROOT = r"C:\Users\Thinkbook\OneDrive\Celine"
SRC = os.path.join(ROOT, "samples", "_unpacked")
LIB = os.path.join(ROOT, "samples", "library")
FFMPEG = shutil.which("ffmpeg") or (
    "C:\\Users\\Thinkbook\\AppData\\Local\\Microsoft\\WinGet\\Packages\\"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\"
    "ffmpeg-9.0.1-full_build\\bin\\ffmpeg.exe")

AUDIO_EXT = (".wav", ".flac", ".mp3", ".ogg", ".aif", ".aiff")

CATEGORY_RULES = [
    ("kick", r"kick|bassdrum|bass drum|bd\b"),
    ("snare", r"snare|clap|rim"),
    ("hat", r"hat|hihat|hi-hat"),
    ("perc", r"perc|conga|bongo|tamb|shaker|shk|cowbell|clave|cymbal|crash|ride|tom"),
    ("vocal", r"vox|vocal|chant|ah|oh|hey|voc|aa\b"),
    ("bass", r"bass|sub|808"),
    ("loop", r"loop"),
    ("fx", r"riser|impact|sweep|vinyl|white noise|noise|glitch|vhs|tape"),
]


def category(name: str) -> str:
    low = name.lower()
    for cat, pat in CATEGORY_RULES:
        if re.search(pat, low):
            return cat
    return "misc"


def safe(s: str) -> str:
    s = re.sub(r"[\\/]+", "_", s)
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:70]


def convert(src: str, dst: str) -> bool:
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", src,
           "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
           "-af", "silenceremove=start_periods=1:start_duration=0.02:start_threshold=-60dB,"
                  "alimiter=limit=0.95:level=disabled",
           dst]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 512


def main():
    os.makedirs(LIB, exist_ok=True)
    manifest = {}
    n = 0
    for dirpath, _, files in os.walk(SRC):
        for f in files:
            if not f.lower().endswith(AUDIO_EXT):
                continue
            src = os.path.join(dirpath, f)
            rel = os.path.relpath(src, SRC)
            cat = category(rel)
            catdir = os.path.join(LIB, cat)
            os.makedirs(catdir, exist_ok=True)
            base = safe(os.path.splitext(rel)[0])
            dst = os.path.join(catdir, base + ".wav")
            if not os.path.exists(dst):
                if not convert(src, dst):
                    print("FAIL", rel, flush=True)
                    continue
            key = f"{cat}/{base}"
            manifest[key] = dst
            n += 1
    with open(os.path.join(LIB, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    print("library files:", n)
    from collections import Counter
    print(Counter(k.split("/")[0] for k in manifest))


if __name__ == "__main__":
    main()
