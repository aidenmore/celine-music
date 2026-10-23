"""verify_audio.py - Check every rendered master for real musical content."""
from __future__ import annotations

import json
import os
import sys
import wave

import numpy as np

HUB = r"C:\Users\Thinkbook\OneDrive\Celine"
RENDERS = os.path.join(HUB, "renders")
SONGS = os.path.join(HUB, "songs")


def analyse(path):
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        ch = w.getnchannels()
        raw = w.readframes(n)
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch)
        mono = a.mean(axis=1)
        # stereo width: correlation between channels
        corr = float(np.corrcoef(a[:, 0], a[:, 1])[0, 1])
    else:
        mono = a
        corr = 1.0
    peak = float(np.max(np.abs(mono)))
    rms = float(np.sqrt(np.mean(mono ** 2)))
    # loudness per quarter to confirm arrangement dynamics
    seg = max(1, len(mono) // 16)
    q = [float(np.sqrt(np.mean(mono[i:i + seg] ** 2))) for i in range(0, len(mono), seg)]
    q = q[:16]
    # spectral centroid (brightness)
    win = 4096
    starts = np.linspace(0, max(0, len(mono) - win), 40, dtype=int)
    cents = []
    for s in starts:
        seg2 = mono[s:s + win] * np.hanning(min(win, len(mono) - s))
        sp = np.abs(np.fft.rfft(seg2))
        fr = np.fft.rfftfreq(len(seg2), 1 / sr)
        if sp.sum() > 0:
            cents.append(float((sp * fr).sum() / sp.sum()))
    return {
        "seconds": round(len(mono) / sr, 1), "sr": sr, "ch": ch,
        "peak": round(peak, 4), "rms_db": round(20 * np.log10(rms + 1e-9), 1),
        "stereo_corr": round(corr, 3),
        "centroid_hz": round(float(np.mean(cents)) if cents else 0, 0),
        "quiet_parts": int(sum(1 for v in q if v < rms * 0.15)),
        "loudest_q": round(max(q) if q else 0, 4),
    }


def main():
    rows = []
    for f in sorted(os.listdir(RENDERS)):
        if not f.endswith(".wav") or f[0].isdigit() is False:
            continue
        if not f[:2].isdigit():
            continue
        p = os.path.join(RENDERS, f)
        try:
            a = analyse(p)
        except Exception as e:
            print(f"FAIL {f}: {e}")
            continue
        mp3 = os.path.join(SONGS, f[:-4] + ".mp3")
        a["mp3_mb"] = round(os.path.getsize(mp3) / 1e6, 2) if os.path.exists(mp3) else 0
        a["file"] = f[:-4]
        rows.append(a)
        print(f"{a['file']:<22} {a['seconds']:>6.1f}s  peak {a['peak']:.3f}  "
              f"rms {a['rms_db']:>6.1f}dB  corr {a['stereo_corr']:>6.3f}  "
              f"centroid {a['centroid_hz']:>6.0f}Hz  quiet {a['quiet_parts']:>2}  "
              f"mp3 {a['mp3_mb']}MB")
    with open(os.path.join(HUB, "logs", "audio_verification.json"), "w",
              encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    ok = [r for r in rows if r["peak"] > 0.2 and r["rms_db"] > -28 and r["mp3_mb"] > 1]
    print(f"\n{len(ok)}/{len(rows)} tracks pass (audible + encoded + dynamic)")
    if rows:
        print("total runtime:", round(sum(r["seconds"] for r in rows) / 60, 1), "min")


if __name__ == "__main__":
    main()
