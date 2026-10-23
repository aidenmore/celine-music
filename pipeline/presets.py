"""
presets.py - Load LMMS instrument presets (.xpf XML and .xiz gzip-XML)
and convert them into project-ready XML fragments.
"""
from __future__ import annotations

import gzip
import io
import os
import xml.etree.ElementTree as ET

PRESETS_ROOT = r"C:\Program Files\LMMS\data\presets"

# Instruments whose presets are plain XML (.xpf)
XML_PRESET_DIRS = [
    "Monstro", "Organic", "Watsyn", "TripleOscillator", "LB302", "Vibed",
    "OpulenZ", "SID", "BitInvader", "Kicker", "AudioFileProcessor",
]


def _strip_ns(el):
    for e in el.iter():
        if "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]
    return el


def load_xpf(path: str) -> dict | None:
    """Return {instrument, eldata, fxchain, track_attrs} from an LMMS .xpf preset."""
    try:
        tree = ET.parse(path)
    except Exception:
        return None
    root = tree.getroot()
    its = root.find("instrumenttracksettings")
    if its is None:
        return None
    it = its.find("instrumenttrack")
    if it is None:
        return None
    inst = it.find("instrument")
    if inst is None:
        return None
    return {
        "instrument": inst,
        "eldata": it.find("eldata"),
        "fxchain": it.find("fxchain"),
        "track_attrs": dict(it.attrib),
    }


def load_xiz(path: str) -> ET.Element | None:
    """Return a <ZynAddSubFX-data> element built from a gzip-compressed .xiz preset."""
    try:
        raw = gzip.open(path, "rb").read()
    except Exception:
        return None
    raw = raw.lstrip()          # some .xiz files start with a newline before <?xml
    try:
        root = ET.fromstring(raw)
    except Exception:
        return None
    root = _strip_ns(root)
    out = ET.Element("ZynAddSubFX-data")
    for child in list(root):
        out.append(child)
    if len(out) == 0:
        return None
    return out


def catalog() -> list[dict]:
    """Enumerate every instrument preset available on this machine."""
    out = []
    for d in XML_PRESET_DIRS:
        pdir = os.path.join(PRESETS_ROOT, d)
        if not os.path.isdir(pdir):
            continue
        for dirpath, _, files in os.walk(pdir):
            for f in sorted(files):
                if f.lower().endswith(".xpf"):
                    full = os.path.join(dirpath, f)
                    rel = os.path.relpath(full, PRESETS_ROOT).replace("\\", "/")
                    out.append({"kind": "xpf", "instrument": d, "name": f[:-4],
                                "path": full, "rel": rel})
    zdir = os.path.join(PRESETS_ROOT, "ZynAddSubFX")
    if os.path.isdir(zdir):
        for dirpath, _, files in os.walk(zdir):
            for f in sorted(files):
                if f.lower().endswith(".xiz"):
                    full = os.path.join(dirpath, f)
                    rel = os.path.relpath(full, PRESETS_ROOT).replace("\\", "/")
                    out.append({"kind": "xiz", "instrument": "ZynAddSubFX",
                                "name": f[:-4], "path": full, "rel": rel})
    return out


def search(substr: str, limit: int = 40) -> list[dict]:
    s = substr.lower()
    hits = [c for c in catalog() if s in c["rel"].lower()]
    return hits[:limit]


if __name__ == "__main__":
    cat = catalog()
    print("total presets:", len(cat))
    from collections import Counter
    for k, v in Counter(c["instrument"] for c in cat).most_common():
        print(f"  {k:<24} {v}")
    print("\n-- sample Zyn names --")
    for c in [c for c in cat if c["kind"] == "xiz"][:15]:
        print("   ", c["rel"])
    print("\n-- xiz parse test --")
    z = [c for c in cat if c["kind"] == "xiz"][0]
    el = load_xiz(z["path"])
    print(z["rel"], "->", None if el is None else f"{len(list(el))} children")
