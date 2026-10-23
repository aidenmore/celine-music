"""Recon pass 4: profile front-matter keys & value shapes across all skill.md files."""
import os, collections, itertools, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HITSF = r"C:\Users\Thinkbook\OneDrive\Celine\scripts\_hits.txt"
keys = collections.Counter()
samples = {}
shapes = collections.Counter()
n = 0
with open(HITSF, encoding="utf-8") as f:
    paths = [p.strip() for p in f if p.strip()]
print("paths:", len(paths))
for p in paths:
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(4000)
    except OSError:
        continue
    n += 1
    if not head.startswith("---"):
        shapes["NO_FRONTMATTER"] += 1
        continue
    end = head.find("\n---", 3)
    if end == -1:
        shapes["UNTERMINATED"] += 1
        continue
    fm = head[3:end]
    for line in fm.splitlines():
        if not line.strip() or line.startswith((" ", "\t", "-", "#")):
            continue
        if ":" in line:
            k = line.split(":", 1)[0].strip().lower()
            keys[k] += 1
            if k not in samples:
                samples[k] = (p, line[:160])
        else:
            shapes["NOCOLON_LINE"] += 1

print("parsed:", n)
print("\n--- front-matter keys ---")
for k, v in keys.most_common(45):
    print(f"{v:6d}  {k}")
    print(f"         e.g. {samples[k][1]}")
print("\n--- shapes ---", dict(shapes))
