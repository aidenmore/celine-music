"""Extract the XML that native LMMS plugins write, from their saveSettings()."""
import os
import re

SRC = r"C:\Users\Thinkbook\Downloads\lmms_src\lmms-1.2.2\plugins"

TARGETS = ["Amplifier", "BassBooster", "Bitcrush", "bit_invader", "CrossoverEQ",
           "Delay", "DualFilter", "dynamics_processor", "Eq", "Flanger",
           "MultitapEcho", "ReverbSC", "stereo_enhancer", "stereo_matrix",
           "waveshaper", "kicker", "sfxr", "vestige", "patman", "sid", "nes",
           "opl2", "papu", "triple_oscillator", "watsyn", "lb302", "vibed",
           "OpulenZ", "organic", "monstro", "audio_file_processor"]

fn_re = re.compile(r"void\s+(\w+)::saveSettings\s*\(\s*QDomDocument\s*&\s*\w+\s*,\s*QDomElement\s*&\s*\w+\s*\)")


def dump(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    out = []
    for m in fn_re.finditer(txt):
        start = m.start()
        # capture until matching closing brace at column 0
        end = txt.find("\n}\n", start)
        body = txt[start:end if end > 0 else start + 4000]
        lines = [l.strip() for l in body.split("\n") if l.strip()]
        out.append((m.group(1), lines))
    return out


for t in TARGETS:
    pdir = os.path.join(SRC, t)
    if not os.path.isdir(pdir):
        continue
    print(f"=== {t}")
    for f in os.listdir(pdir):
        if not f.endswith(".cpp"):
            continue
        for name, lines in dump(os.path.join(pdir, f)):
            interesting = [l for l in lines
                           if ("setAttribute" in l or "createElement" in l or
                               "addChild" in l or "setText" in l or "firstChildElement" in l
                               or "QDomElement" in l)]
            if not interesting:
                continue
            print(f"  -- {name} ({f})")
            for l in interesting[:70]:
                print("      " + l[:190])
