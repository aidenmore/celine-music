"""One-shot patch: make hits() call sites unpack (pitch, tick, length)."""
import re

P = r"C:\Users\Thinkbook\OneDrive\Celine\scripts\build_songs.py"
t = open(P, encoding="utf-8").read()

t = t.replace("for p, ln in hits(", "for pit, tk, ln in hits(")
t = re.sub(r"(\w+)\.add\(p, ln\)", r"\1.add(pit, tk, ln)", t)

old_arp = ('for i, p in enumerate(hits(bar, "x.xx.x.xx.x.xx.x.", [r, r + 3, r + 7, r + 12],\n'
           '                                   length=60)):\n'
           '            arp.add(p, p[1], 60)')
new_arp = ('for pit, tk, ln in hits(bar, "x.xx.x.xx.x.xx.x.",\n'
           '                                    [r, r + 3, r + 7, r + 12], length=60):\n'
           '            arp.add(pit, tk, ln)')
t = t.replace(old_arp, new_arp)

open(P, "w", encoding="utf-8").write(t)

bad = [ln for ln in t.splitlines()
       if "for p, ln in hits" in ln or ".add(p, ln)" in ln or "for i, p in enumerate(hits" in ln]
print("remaining bad sites:", len(bad))
for b in bad:
    print("  ", b.strip())
