import json, collections, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d = json.load(open(r"C:\Users\Thinkbook\OneDrive\Celine\hub\skills\registry.json", encoding="utf-8"))
print("entries:", len(d["skills"]))
print("counts.total:", d["counts"]["total"], "computer_use:", d["counts"]["computer_use"])
print()
print("--- by capability ---")
for k, v in sorted(d["counts"]["by_capability"].items(), key=lambda kv: -kv[1]):
    print(f"{v:6d}  {k}")
print()
print("--- computer_use=True ---")
cu = [s for s in d["skills"] if s["computer_use"]]
print("count:", len(cu))
for s in sorted(cu, key=lambda x: (x["surface"], x["name"].lower())):
    print(f"  {s['capability']:20s} {s['surface']:20s} {s['name']}")
print()
print("--- top duplicate names ---")
dups = d["duplicate_names"]
for name, grp in sorted(dups.items(), key=lambda kv: -len(kv[1]))[:25]:
    print(f"{len(grp):3d}  {name}   <- {sorted({g['surface'] for g in grp})}")
print()
print("dup names:", len(dups))
