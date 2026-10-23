"""Verification for the harvested skill registry.

Checks:
  1. registry.json parses with the json module.
  2. INDEX.md headline counts match the registry entry count.
  3. Every source_path in registry.csv exists on disk.
  4. Every mirrored file exists and the mirror total (files/bytes) is reported.
  5. All registry source paths exist on disk.
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILLS = Path(r"C:\Users\Thinkbook\OneDrive\Celine\hub\skills")
MIRROR = SKILLS / "mirror"

failures = []
notes = []

# --- 1. registry.json parses -------------------------------------------------
try:
    reg = json.loads((SKILLS / "registry.json").read_text(encoding="utf-8"))
    print(f"[PASS] registry.json parses as JSON  (schema_version={reg.get('schema_version')})")
except Exception as exc:                                        # noqa: BLE001
    print(f"[FAIL] registry.json does not parse: {exc}")
    raise SystemExit(1)

skills = reg["skills"]
n = len(skills)
print(f"[INFO] registry contains {n} skill entries")
if n != reg["counts"]["total"]:
    failures.append(f"registry counts.total ({reg['counts']['total']}) != len(skills) ({n})")
    print(f"[FAIL] counts.total mismatch")
else:
    print("[PASS] counts.total == len(skills)")

# --- 2. INDEX.md counts ------------------------------------------------------
index = (SKILLS / "INDEX.md").read_text(encoding="utf-8")
m = re.search(r"\*\*Total skills discovered:\s*(\d+)\*\*", index)
if not m:
    failures.append("INDEX.md: 'Total skills discovered' line not found")
    print("[FAIL] INDEX.md total-skills line not found")
else:
    idx_n = int(m.group(1))
    if idx_n == n:
        print(f"[PASS] INDEX.md total ({idx_n}) == registry entries ({n})")
    else:
        failures.append(f"INDEX.md total {idx_n} != registry {n}")
        print(f"[FAIL] INDEX.md total {idx_n} != registry {n}")

m = re.search(r"Computer-use / browser-automation / app-automation skills:\s*\*\*(\d+)\*\*", index)
if m:
    idx_cu = int(m.group(1))
    if idx_cu == reg["counts"]["computer_use"]:
        print(f"[PASS] INDEX.md computer-use count ({idx_cu}) == registry count")
    else:
        failures.append(f"INDEX.md computer-use {idx_cu} != registry {reg['counts']['computer_use']}")
        print("[FAIL] INDEX.md computer-use count mismatch")

# capability table in INDEX.md must sum to the total
cap_rows = re.findall(r"^\|\s*(computer-use|browser-automation|app-automation|mcp-integration|"
                      r"media-generation|data-analysis|web-research|document|communication|"
                      r"code-generation|devops|other)\s*\|\s*(\d+)\s*\|", index, re.M)
cap_sum = sum(int(v) for _, v in cap_rows)
if cap_sum == n:
    print(f"[PASS] INDEX.md capability table sums to {cap_sum} == registry entries")
else:
    failures.append(f"INDEX.md capability table sums to {cap_sum}, expected {n}")
    print(f"[FAIL] INDEX.md capability table sums to {cap_sum}, expected {n}")

# --- 3./5. CSV + registry source paths exist --------------------------------
missing_csv = []
with (SKILLS / "registry.csv").open(encoding="utf-8", newline="") as fh:
    rows = list(csv.DictReader(fh))
for r in rows:
    if not Path(r["source_path"]).exists():
        missing_csv.append(r["source_path"])
print(f"[INFO] registry.csv has {len(rows)} data rows")
if missing_csv:
    failures.append(f"{len(missing_csv)} CSV source_path entries do not exist on disk")
    print(f"[FAIL] {len(missing_csv)} CSV paths missing, e.g. {missing_csv[:3]}")
else:
    print("[PASS] every CSV source_path exists on disk")

missing_reg = [s["source_path"] for s in skills if not Path(s["source_path"]).exists()]
if missing_reg:
    failures.append(f"{len(missing_reg)} registry source_path entries do not exist")
    print(f"[FAIL] {len(missing_reg)} registry paths missing, e.g. {missing_reg[:3]}")
else:
    print("[PASS] every registry source_path exists on disk")

# --- 4. mirror ---------------------------------------------------------------
if MIRROR.is_dir():
    files = [p for p in MIRROR.rglob("*") if p.is_file()]
    total_bytes = sum(p.stat().st_size for p in files)
    skill_dirs = sorted({p.parent for p in files})
    surface_dirs = sorted({p.parent.parent for p in files if p.parent.parent != MIRROR})
    print(f"[INFO] mirror: {len(files)} files, {total_bytes:,} bytes "
          f"({total_bytes / 1048576:.2f} MiB) in {len(skill_dirs)} skill folders "
          f"across {len(surface_dirs)} surfaces")
    reg_mirror = reg.get("mirror", {})
    if reg_mirror.get("files_copied") == len(files):
        print(f"[PASS] registry mirror.files_copied ({reg_mirror.get('files_copied')}) == files on disk ({len(files)})")
    else:
        notes.append(f"registry mirror.files_copied={reg_mirror.get('files_copied')} vs {len(files)} on disk")
    if reg_mirror.get("bytes_copied") == total_bytes:
        print(f"[PASS] registry mirror.bytes_copied == bytes on disk ({total_bytes:,})")
    else:
        notes.append(f"registry mirror.bytes_copied={reg_mirror.get('bytes_copied')} vs {total_bytes} on disk")

    # every skill that claims a mirror path must have it
    no_mirror = [s["name"] for s in skills
                 if not (SKILLS / s["mirror_path"]).exists()]
    if no_mirror:
        failures.append(f"{len(no_mirror)} skills have no mirrored folder")
        print(f"[FAIL] {len(no_mirror)} skills have no mirrored folder, e.g. {no_mirror[:5]}")
    else:
        print(f"[PASS] every one of the {len(skills)} skills has a mirrored folder")

    # oversized files must not have been copied
    big = [p for p in files if p.stat().st_size > 5 * 1024 * 1024]
    if big:
        failures.append(f"{len(big)} mirrored files exceed 5 MB")
        print(f"[FAIL] {len(big)} mirrored files exceed 5 MB")
    else:
        print("[PASS] no mirrored file exceeds the 5 MB limit")
else:
    failures.append("mirror directory missing")
    print("[FAIL] mirror directory missing")

# --- summary -----------------------------------------------------------------
print()
if notes:
    print("NOTES:")
    for x in notes:
        print("  - " + x)
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S)")
    for f in failures:
        print("  * " + f)
    raise SystemExit(1)
print("RESULT: ALL CHECKS PASSED")
