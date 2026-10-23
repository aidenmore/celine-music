"""List downloadable files for archive.org items."""
import json
import sys
import urllib.request

IDS = [
    "soundcloud-783542614",
    "SamplesAndLoopsForTranceAndTechno",
    "musicradar-drum-samples",
    "collection-samples-drum-kit-soundfonts",
    "legowelt-jupiter-8-sample-pack",
    "tr-909-picture",
    "dicroismo-break-core-sample-pack",
    "alesis-vintage-drum-machine-samples",
    "BSSP0001",
    "50-best-free-synth-samples",
]

for ident in IDS:
    print("=" * 80)
    print(ident)
    try:
        req = urllib.request.Request(
            f"https://archive.org/metadata/{ident}",
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=45) as r:
            md = json.load(r)
        meta = md.get("metadata", {})
        lic = meta.get("licenseurl", "") or meta.get("rights", "")
        print("  license:", lic or meta.get("rights", "(none stated)"))
        print("  title  :", meta.get("title", ""))
        files = md.get("files", [])
        audio = [f for f in files
                 if f.get("format", "").lower() in ("wav", "mp3", "flac", "ogg", "aiff", "zip", "sf2")
                 and not f.get("name", "").endswith((".gif", ".jpg", ".png"))]
        for f in audio[:22]:
            print(f"   {f.get('format',''):<6} {int(f.get('size',0) or 0):>10} {f.get('name','')[:70]}")
        if len(audio) > 22:
            print(f"   ... and {len(audio)-22} more")
        if not audio:
            print("   (no audio/zip files)")
    except Exception as e:
        print("  ERR", e)
