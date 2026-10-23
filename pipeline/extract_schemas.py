"""Extract exact XML attribute names each LMMS plugin writes/reads."""
import os
import re

SRC = r"C:\Users\Thinkbook\Downloads\lmms_src\lmms-1.2.2\plugins"

setattr_re = re.compile(r'setAttribute\s*\(\s*(?:QStringLiteral\s*\(\s*)?"([^"]+)"')
child_re = re.compile(
    r'(?:addChild\s*\(|createElement\s*\(\s*|firstChildElement\s*\(\s*)'
    r'(?:QStringLiteral\s*\(\s*)?"([^"]+)"')

SKIP = {"width", "height", "x", "y", "visible", "maximized", "minimized",
        "name", "type", "pos", "len", "vol", "pan", "key", "muted", "solo",
        "steps", "on", "wet", "ports", "fxch", "basenote", "pitch", "pitchrange",
        "usemasterpitch", "autoquit", "autoquit_numerator", "autoquit_denominator",
        "gate", "syncmode"}

for d in sorted(os.listdir(SRC)):
    pdir = os.path.join(SRC, d)
    if not os.path.isdir(pdir):
        continue
    attrs, children = set(), set()
    for f in os.listdir(pdir):
        if not f.endswith(".cpp"):
            continue
        with open(os.path.join(pdir, f), encoding="utf-8", errors="replace") as fh:
            txt = fh.read()
        for m in setattr_re.finditer(txt):
            attrs.add(m.group(1))
        for m in child_re.finditer(txt):
            children.add(m.group(1))
    attrs -= SKIP
    if not attrs and not children:
        continue
    print(f"--- {d}")
    if attrs:
        print("    attrs :", ", ".join(sorted(attrs)))
    if children:
        print("    child :", ", ".join(sorted(children)))
