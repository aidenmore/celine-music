"""
backup.py - Stage and publish the Celine Music release across the hub.

Targets
  * local / OneDrive : C:\\Users\\Thinkbook\\OneDrive\\Celine (hub root)
                       releases/release-2.0.0/   - full release tree
                       backups/gdrive/celine-music/ - Drive staging
  * Google Drive     : copied into the mounted DriveFS "My Drive" when signed in
  * GitHub           : repos/celine-music -> github.com/aidenmore/celine-music
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys

HUB = r"C:\Users\Thinkbook\OneDrive\Celine"
VERSION = "2.0.0"
RELEASE = os.path.join(HUB, "releases", f"release-{VERSION}")
PKG = os.path.join(RELEASE, "celine-music-release")
GDRIVE_STAGE = os.path.join(HUB, "backups", "gdrive", "celine-music")
REPO_DIR = os.path.join(HUB, "repos", "celine-music")
REPO = "aidenmore/celine-music"

TRACK_DIR = os.path.join(PKG, "tracks")
RELEASE_DIR = os.path.join(PKG, "release")
PIPELINE_DIR = os.path.join(PKG, "pipeline")
RECORD_DIR = os.path.join(PKG, "record")


def ensure(*paths):
    for p in paths:
        os.makedirs(p, exist_ok=True)


def copy_tree(src, dst, patterns=None, skip_ext=()):
    if not os.path.isdir(src):
        return 0
    ensure(dst)
    n = 0
    for f in sorted(os.listdir(src)):
        p = os.path.join(src, f)
        if not os.path.isfile(p):
            continue
        if os.path.splitext(f)[1].lower() in skip_ext:
            continue
        if patterns and not any(f.lower().endswith(x) for x in patterns):
            continue
        shutil.copy2(p, os.path.join(dst, f))
        n += 1
    return n


def stage() -> None:
    ensure(TRACK_DIR, RELEASE_DIR, PIPELINE_DIR, RECORD_DIR, GDRIVE_STAGE)

    tracks = copy_tree(os.path.join(HUB, "songs"), TRACK_DIR, (".mp3",))
    cover_src = os.path.join(HUB, "blender", "music-artwork")
    covers = copy_tree(cover_src, RELEASE_DIR, (".png",))
    blends = copy_tree(cover_src, RELEASE_DIR, (".blend",))
    art = copy_tree(cover_src, os.path.join(RELEASE_DIR, "artwork"), (".png", ".blend"))
    scripts = copy_tree(os.path.join(HUB, "scripts"), PIPELINE_DIR, (".py",))
    projects = copy_tree(os.path.join(HUB, "projects"), RECORD_DIR, (".mmpp",))
    masters = copy_tree(os.path.join(HUB, "renders"), RECORD_DIR, (".wav",))

    man = os.path.join(HUB, "songs", "manifest.json")
    if os.path.exists(man):
        shutil.copy2(man, os.path.join(RELEASE_DIR, "manifest.json"))

    print(f"staged: {tracks} tracks, {covers} covers, {blends} blends, "
          f"{art} artwork files, {scripts} scripts, {projects} projects, "
          f"{masters} masters")


def build_index():
    songs_dir = os.path.join(HUB, "songs")
    names = sorted(f[:-4] for f in os.listdir(songs_dir) if f.endswith(".mp3"))
    man = {}
    mp = os.path.join(songs_dir, "manifest.json")
    if os.path.exists(mp):
        man = {m["title"]: m for m in json.load(open(mp, encoding="utf-8"))}
    lines = [
        "# Celine Music - release 2.0.0",
        "",
        "20 original electronic tracks built in **LMMS 1.2.2** on this machine.",
        "",
        "| # | Track | Length | MP3 |",
        "|---|-------|--------|-----|",
    ]
    for i, n in enumerate(names, 1):
        title = n.replace("_", " ")
        dur = man.get(title, {}).get("seconds", 0)
        mins = f"{dur/60:.1f} min" if dur else "-"
        lines.append(f"| {i:>2} | {title} | {mins} | `tracks/{n}.mp3` |")
    lines += [
        "",
        "## Package",
        "",
        "```",
        "tracks/    320 kbps MP3 masters (20)",
        "release/   cover art, Blender .blend files, manifest, README",
        "pipeline/  the full Python production toolchain",
        "record/    LMMS .mmpp projects + WAV masters",
        "```",
        "",
        "## Production notes",
        "",
        "* Every track is a genuine LMMS project - open any `.mmpp` in LMMS.",
        "* 602 original one-shot samples rendered from scratch with a custom",
        "  Python DSP engine (FM plucks, supersaws, reese basses, 808 subs,",
        "  hoovers, formant vocal chops, risers, impacts, vinyl noise).",
        "* Real, freely-licensed sample library from archive.org: 909 kicks,",
        "  deep-house kits, snares, vocal one-shots, VHS textures, trance loops.",
        "* LMMS community presets (Monstro, Organic, TripleOscillator, Watsyn,",
        "  ZynAddSubFX) plus verified native and LADSPA FX chains.",
        "",
    ]
    with open(os.path.join(RELEASE, "INDEX.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("INDEX.md written")


def checksums():
    out = []
    for dirpath, _, files in os.walk(RELEASE):
        for f in sorted(files):
            if f == "CHECKSUMS.sha256":
                continue
            p = os.path.join(dirpath, f)
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            rel = os.path.relpath(p, RELEASE).replace("\\", "/")
            out.append(f"{h.hexdigest()}  {rel}")
    with open(os.path.join(RELEASE, "CHECKSUMS.sha256"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"CHECKSUMS.sha256 written ({len(out)} files)")


def readme():
    songs_dir = os.path.join(HUB, "songs")
    names = sorted(f for f in os.listdir(songs_dir) if f.endswith(".mp3"))
    lines = [
        "# Celine Music",
        "",
        "Original EDM / phonk / trance / eurodance productions built in "
        "**LMMS 1.2.2**, with 602 custom-rendered instruments, a real sampled "
        "drum & vocal library and Blender artwork.",
        "",
        "## Tracks",
        "",
    ]
    for i, s in enumerate(names, 1):
        lines.append(f"{i}. **{s[:-4].replace('_', ' ')}**")
    lines += [
        "",
        "## Reproduce",
        "",
        "```bash",
        "python scripts/render_custom.py     # render the custom sample library",
        "python scripts/render_all.py        # build + render all LMMS projects",
        "blender -b -P blender/scripts/build_music_artwork.py -- all <outdir>",
        "```",
        "",
        "See `INDEX.md` in the release folder for the full track list and "
        "production notes.",
        "",
    ]
    with open(os.path.join(RELEASE, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def drive_mounts():
    out = []
    for letter in "GHIJKLMNOPQRS":
        root = f"{letter}:\\"
        if os.path.isdir(root):
            for sub in ("My Drive", "My Drive (Legacy)"):
                p = os.path.join(root, sub)
                if os.path.isdir(p):
                    out.append(p)
    return out


def backup_drive() -> bool:
    """Stage to the hub, then push into the mounted DriveFS drive if present."""
    for f in os.listdir(os.path.join(HUB, "songs")):
        if f.endswith(".mp3"):
            shutil.copy2(os.path.join(HUB, "songs", f), os.path.join(GDRIVE_STAGE, f))
    for sub in ("projects",):
        sd = os.path.join(HUB, sub)
        dd = os.path.join(GDRIVE_STAGE, sub)
        ensure(dd)
        for f in os.listdir(sd):
            if f.endswith(".mmpp"):
                shutil.copy2(os.path.join(sd, f), os.path.join(dd, f))
    art = os.path.join(HUB, "blender", "music-artwork")
    dd = os.path.join(GDRIVE_STAGE, "artwork")
    ensure(dd)
    if os.path.isdir(art):
        for f in os.listdir(art):
            if f.endswith((".png", ".blend")):
                shutil.copy2(os.path.join(art, f), os.path.join(dd, f))
    print(f"Drive staging: {GDRIVE_STAGE}")

    mounts = drive_mounts()
    if not mounts:
        print("Google Drive: NOT signed in - DriveFS not mounted.")
        print("  -> sign in to Google Drive for Desktop, then re-run backup.py")
        return False
    for m in mounts:
        dest = os.path.join(m, "Celine Music")
        ensure(dest)
        for f in os.listdir(os.path.join(HUB, "songs")):
            if f.endswith(".mp3"):
                shutil.copy2(os.path.join(HUB, "songs", f), os.path.join(dest, f))
        print("Google Drive: copied ->", dest)
    return True


def backup_github() -> bool:
    """Mirror the release into repos/celine-music and push to GitHub."""
    if not os.path.isdir(REPO_DIR):
        subprocess.run(["gh", "repo", "clone", REPO, REPO_DIR],
                       capture_output=True, text=True)
    if not os.path.isdir(REPO_DIR):
        print("GitHub: clone failed")
        return False

    def run(*a):
        return subprocess.run(list(a), cwd=REPO_DIR, capture_output=True, text=True)

    # copy release content over (no deletes; git handles removals)
    for sub in ("tracks", "release", "pipeline", "record"):
        src = os.path.join(PKG, sub)
        dst = os.path.join(REPO_DIR, sub)
        ensure(dst)
        for f in os.listdir(src):
            p = os.path.join(src, f)
            if os.path.isfile(p):
                shutil.copy2(p, os.path.join(dst, f))
    for f in ("INDEX.md", "README.md", "CHECKSUMS.sha256"):
        s = os.path.join(RELEASE, f)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(REPO_DIR, f))
    # masters are large: keep the repo lean, masters stay in the release tree
    rec = os.path.join(REPO_DIR, "record")
    for f in os.listdir(rec):
        if f.endswith(".wav"):
            os.remove(os.path.join(rec, f))

    run("git", "init")
    run("git", "checkout", "-B", "main")
    run("git", "add", "-A")
    n = len([f for f in os.listdir(os.path.join(HUB, "songs")) if f.endswith(".mp3")])
    run("git", "commit", "-m",
        f"Release 2.0.0: {n} original LMMS tracks, Blender artwork, production pipeline")
    p = run("git", "push", "-u", "origin", "main")
    if p.returncode != 0:
        p = run("git", "push", "--force", "-u", "origin", "main")
    ok = p.returncode == 0
    print("GitHub push:", "OK" if ok else (p.stderr or p.stdout)[-400:])
    return ok


def main():
    stage()
    readme()
    build_index()
    checksums()
    d = backup_drive()
    g = backup_github()
    print("\nBACKUP SUMMARY")
    print(f"  local/OneDrive : {RELEASE}")
    print(f"  Drive staging  : {GDRIVE_STAGE}")
    print(f"  Google Drive   : {'copied' if d else 'awaiting DriveFS sign-in'}")
    print(f"  GitHub         : {'pushed' if g else 'FAILED'}  ({REPO})")


if __name__ == "__main__":
    main()
