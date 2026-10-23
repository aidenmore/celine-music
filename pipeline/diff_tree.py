"""Compare LMMS project XML structure: reference vs hand-written."""
import sys
import xml.etree.ElementTree as ET

def walk(el, depth=0, maxdepth=4, out=None):
    if out is None:
        out = []
    if depth > maxdepth:
        return out
    tag = el.tag
    # show only structural attributes, skip noise
    skip = {"lspd_denominator", "lspd_numerator", "ctlenvamt", "lpdel", "pdel",
            "amt", "hold", "syncmode", "userwavefile", "latt", "sustain", "lamt",
            "lshp", "lspd", "x100", "rel", "dec", "att", "sus"}
    attrs = {k: v for k, v in el.attrib.items() if k not in skip}
    out.append("  " * depth + f"<{tag} {attrs}>")
    for c in list(el):
        walk(c, depth + 1, maxdepth, out)
    return out

for path in sys.argv[1:]:
    print("=" * 70)
    print(path)
    print("=" * 70)
    try:
        t = ET.parse(path)
        r = t.getroot()
        print("ROOT:", r.tag, r.attrib)
        for line in walk(r, 0, 3):
            print(line)
    except Exception as e:
        print("PARSE ERROR:", e)
    print()
