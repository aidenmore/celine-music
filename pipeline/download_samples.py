"""Download real, freely-licensed samples from archive.org into the workspace."""
import os
import shutil
import sys
import urllib.parse
import urllib.request
import zipfile

from config_paths import ROOT
OUT = os.path.join(ROOT, "samples")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# (item_id, remote_filename, local_subdir)
FILES = [
    ("tr-909-picture", "909 KICK 2.flac", "909"),
    ("tr-909-picture", "909 kick fat.flac", "909"),
    ("tr-909-picture", "kick 4 distorted.flac", "909"),
    ("tr-909-picture", "CLAP 3.flac", "909"),
    ("tr-909-picture", "Hardclap.flac", "909"),
    ("tr-909-picture", "Hc2clap.flac", "909"),
    ("tr-909-picture", "Hypersd2.flac", "909"),
    ("tr-909-picture", "Punchy KickDrum -Looped 138-BPM.flac", "909"),
    ("alesis-vintage-drum-machine-samples", "Bassdrum-01.flac", "909"),
    ("alesis-vintage-drum-machine-samples", "Bassdrum-02.flac", "909"),
    ("alesis-vintage-drum-machine-samples", "Bassdrum-03.flac", "909"),
    ("alesis-vintage-drum-machine-samples", "Bassdrum-04.flac", "909"),
    ("alesis-vintage-drum-machine-samples", "Bassdrum-05.flac", "909"),
    ("alesis-vintage-drum-machine-samples", "Cowbell.flac", "perc"),
    ("alesis-vintage-drum-machine-samples", "Edge Hat.flac", "hats"),
    ("SamplesAndLoopsForTranceAndTechno", "trance_techno_samples.zip", "_zips"),
    ("collection-samples-drum-kit-soundfonts", "One Shots Vocal Woman S6.zip", "_zips"),
    ("collection-samples-drum-kit-soundfonts", "Deep House Drum.zip", "_zips"),
    ("collection-samples-drum-kit-soundfonts", "One Shots Snare.zip", "_zips"),
    ("BSSP0001", "00-BSSP0001_WAV.zip", "_zips"),
]

# individual FLAC one-shots from the "50 best free synth samples" item
SYNTH_ITEMS = ["50-best-free-synth-samples"]


def fetch(url, dest, retries=3):
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        return True, "cached"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as fh:
                shutil.copyfileobj(r, fh, 1024 * 64)
            if os.path.getsize(dest) > 1000:
                return True, f"{os.path.getsize(dest)} bytes"
        except Exception as e:
            err = str(e)
    return False, err


def main():
    os.makedirs(OUT, exist_ok=True)
    zips = os.path.join(OUT, "_zips")
    os.makedirs(zips, exist_ok=True)

    for item, fname, sub in FILES:
        target_dir = os.path.join(OUT, sub)
        os.makedirs(target_dir, exist_ok=True)
        base = fname if sub == "_zips" else f"{sub}/{fname}"
        dest = os.path.join(zips, fname) if sub == "_zips" else os.path.join(target_dir, fname)
        url = (f"https://archive.org/download/{urllib.parse.quote(item)}/"
               f"{urllib.parse.quote(fname)}")
        ok, info = fetch(url, dest)
        print(f"{'OK ' if ok else 'FAIL'} {item}/{fname} -> {info}", flush=True)

    # expand zips into per-category folders
    for zp in sorted(os.listdir(zips)):
        if not zp.lower().endswith(".zip"):
            continue
        zp_path = os.path.join(zips, zp)
        target = os.path.join(OUT, "_unpacked", os.path.splitext(zp)[0])
        if os.path.isdir(target) and any(os.scandir(target)):
            print(f"skip unpack {zp} (already present)")
            continue
        os.makedirs(target, exist_ok=True)
        try:
            with zipfile.ZipFile(zp_path) as z:
                z.extractall(target)
            print(f"unpacked {zp} -> {target}", flush=True)
        except Exception as e:
            print(f"unpack FAIL {zp}: {e}", flush=True)

    print("DONE")


if __name__ == "__main__":
    main()
