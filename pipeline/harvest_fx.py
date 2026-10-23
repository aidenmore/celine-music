"""Harvest verified native-effect and LADSPA XML from LMMS's 1102 preset files."""
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict

PRESETS = r"C:\Program Files\LMMS\data\presets"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fx_library.json")

native = defaultdict(list)      # effect name -> list of {ctrlElem: {attr: val}}
ladspa = defaultdict(list)      # (file, plugin) -> list of {portIdx: value}
instruments = defaultdict(list)  # instrument name -> list of param dicts


def walk_effects(fxchain):
    for eff in fxchain.findall("effect"):
        name = eff.get("name")
        ctrl = {}
        for ch in list(eff):
            if ch.tag == "key":
                continue
            ctrl[ch.tag] = dict(ch.attrib)
        if name == "ladspaeffect":
            key = eff.find("key")
            fname = plugin = None
            if key is not None:
                for a in key.findall("attribute"):
                    if a.get("name") == "file":
                        fname = a.get("value")
                    if a.get("name") == "plugin":
                        plugin = a.get("value")
            lc = eff.find("ladspacontrols")
            ports = {}
            if lc is not None:
                for p in list(lc):
                    m = re.fullmatch(r"port(\d+)", p.tag)
                    if m:
                        ports[int(m.group(1))] = p.get("data")
            ladspa[(fname, plugin)].append(ports)
        elif name:
            native[name].append(ctrl)


def walk_instr(inst_el):
    name = inst_el.get("name")
    for child in list(inst_el):
        if child.tag == "key":
            continue
        instruments[name].append(dict(child.attrib))


count = 0
for dirpath, _, files in os.walk(PRESETS):
    for f in files:
        if not f.lower().endswith(".xpf"):
            continue
        p = os.path.join(dirpath, f)
        try:
            root = ET.parse(p).getroot()
        except Exception:
            continue
        count += 1
        for its in root.iter("instrumenttracksettings"):
            it = its.find("instrumenttrack")
            if it is None:
                continue
            inst = it.find("instrument")
            if inst is not None:
                walk_instr(inst)
            fx = it.find("fxchain")
            if fx is not None:
                walk_effects(fx)

lib = {
    "native": {k: v[:6] for k, v in native.items()},
    "ladspa": {f"{k[0]}|{k[1]}": v[:6] for k, v in ladspa.items()},
    "instruments": {k: v[:4] for k, v in instruments.items()},
}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(lib, fh, indent=1)

print("presets scanned:", count)
print("\n=== NATIVE EFFECTS (control element + attrs) ===")
for k, v in lib["native"].items():
    sample = v[0] if v else {}
    for celem, attrs in sample.items():
        print(f"  {k:<20} <{celem} {attrs}>")
print("\n=== LADSPA (file|plugin -> port idx:value) ===")
for k, v in lib["ladspa"].items():
    print(f"  {k:<34} {v[0]}")
print("\n=== INSTRUMENTS ===")
for k, v in lib["instruments"].items():
    print(f"  {k:<22} {len(v)} param sets, e.g. {sorted(v[0].keys())[:14] if v else []}")
