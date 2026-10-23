"""Recon pass 3: dump ALL skill.md hits grouped by surface key; find ones outside known roots."""
import os, collections

HOME = r"C:\Users\Thinkbook"
SKIP = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".cache", "Cache",
        "Code Cache", "GPUCache", "temp", "tmp", "site-packages", ".pnpm-store",
        ".yarn", ".next", "target", ".pytest_cache", "logs", "log", "dist-info"}

hits = []
for dp, dn, fns in os.walk(HOME):
    dn[:] = [x for x in dn if x not in SKIP]
    for fn in fns:
        if fn.lower() == "skill.md":
            hits.append(os.path.join(dp, fn))

with open(r"C:\Users\Thinkbook\OneDrive\Celine\scripts\_hits.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(hits))

# group by surface key = first 4 segments under HOME
groups = collections.Counter()
for h in hits:
    rel = os.path.relpath(h, HOME)
    parts = rel.split(os.sep)
    key = os.sep.join(parts[:4]) if len(parts) > 4 else rel
    groups[key] += 1

print("TOTAL:", len(hits))
for k, v in groups.most_common(60):
    print(f"{v:5d}  {k}")
