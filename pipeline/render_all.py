"""
render_all.py - Build every LMMS project, render them headlessly in parallel,
encode 320 kbps MP3s and write a release manifest.
"""
from __future__ import annotations

import json
import os
import sys
import time
import wave
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mmpp import write_song
from lmms_render import render_project, to_mp3
import build_songs as B
import gen_songs as G

ROOT = r"C:\Users\Thinkbook\OneDrive\Celine"
PROJ = os.path.join(ROOT, "projects")
WAV = os.path.join(ROOT, "renders")
SONGS = os.path.join(ROOT, "songs")
LOGS = os.path.join(ROOT, "logs")
for d in (PROJ, WAV, SONGS, LOGS):
    os.makedirs(d, exist_ok=True)


def all_specs():
    out = []
    for name, fn, genre, bpm in B.SONGS:
        out.append((name, fn, genre, bpm))
    for s in G.SPECS:
        out.append((s.title, (lambda ss: (lambda: G.build(ss)))(s), s.genre, s.bpm))
    return out


def one(job):
    name, fn, genre, bpm = job
    slug = name.replace(" ", "_")
    mmpp = os.path.join(PROJ, slug + ".mmpp")
    wav = os.path.join(WAV, slug + ".wav")
    mp3 = os.path.join(SONGS, slug + ".mp3")
    t0 = time.time()
    try:
        song = fn()
    except Exception as e:
        return (name, False, f"build error: {e}", 0, 0)
    write_song(song, mmpp)
    if not (os.path.exists(wav) and os.path.getsize(wav) > 100000):
        ok, log = render_project(mmpp, wav)
    else:
        ok, log = True, "(reused existing render)"
    with open(os.path.join(LOGS, slug + ".log"), "w", encoding="utf-8") as fh:
        fh.write(log)
    if not ok:
        return (name, False, log[-400:], 0, 0)
    with wave.open(wav, "rb") as w:
        dur = w.getnframes() / w.getframerate()
        ch, sr = w.getnchannels(), w.getframerate()
    to_mp3(wav, mp3, "320")
    return (name, True, f"{ch}ch {sr}Hz {len(song.tracks)} tracks",
            dur, os.path.getsize(mp3))


def main():
    jobs = all_specs()
    only = sys.argv[1:]
    if only:
        jobs = [j for j in jobs if any(o.lower() in j[0].lower() for o in only)]
    print(f"rendering {len(jobs)} songs with 3 workers", flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(one, j): j for j in jobs}
        for f in as_completed(futs):
            r = f.result()
            results.append(r)
            status = "OK  " if r[1] else "FAIL"
            print(f"  {status} {r[0]:<20} {r[3]:7.1f}s  {r[4]/1e6:6.2f}MB  {r[2]}",
                  flush=True)
    results.sort(key=lambda r: r[0])
    man = [{"title": r[0], "ok": r[1], "seconds": round(r[3], 1),
            "mp3_bytes": r[4], "note": r[2]} for r in results]
    with open(os.path.join(SONGS, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1)
    good = sum(1 for r in results if r[1])
    total = sum(r[3] for r in results)
    print(f"\n{good}/{len(results)} songs rendered, {total/60:.1f} min of audio")


if __name__ == "__main__":
    main()
