"""Throwaway reconnaissance: locate SKILL.md / skill.md files under candidate roots."""
import os, sys, collections

HOME = r"C:\Users\Thinkbook"

ROOTS = [
    os.path.join(HOME, ".minimax"),
    os.path.join(HOME, ".mavis"),
    os.path.join(HOME, ".codex"),
    os.path.join(HOME, ".claude"),
    os.path.join(HOME, ".grok"),
    os.path.join(HOME, ".continue"),
    os.path.join(HOME, ".gemini"),
    os.path.join(HOME, ".copilot"),
    os.path.join(HOME, ".cua-driver"),
    os.path.join(HOME, ".kimi-code"),
    os.path.join(HOME, ".kimi-webbridge"),
    os.path.join(HOME, ".kimi-work"),
    os.path.join(HOME, ".config"),
    os.path.join(HOME, ".local"),
    os.path.join(HOME, ".vscode"),
    os.path.join(HOME, ".vscode-insiders"),
    os.path.join(HOME, ".vscode-shared"),
    os.path.join(HOME, ".t3"),
    os.path.join(HOME, ".cache"),
    os.path.join(HOME, "AppData", "Local", "hermes"),
    os.path.join(HOME, "AppData", "Local", "Programs"),
    os.path.join(HOME, "AppData", "Roaming"),
    os.path.join(HOME, "AppData", "Local"),
    os.path.join(HOME, "OneDrive", "Celine"),
]

SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".cache",
             "Cache", "Code Cache", "GPUCache", "temp", "tmp", "dist-info",
             "site-packages", ".pnpm-store", ".yarn", ".next", "target"}

MAX_DEPTH = 9
hits = []
counts = collections.Counter()
scanned = 0

for root in ROOTS:
    if not os.path.isdir(root):
        continue
    for dirpath, dirnames, filenames in os.walk(root):
        d = dirpath[len(root):].count(os.sep)
        dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS and not x.startswith(".git")]
        if d >= MAX_DEPTH:
            dirnames[:] = []
        scanned += 1
        for fn in filenames:
            if fn.lower() == "skill.md":
                hits.append(os.path.join(dirpath, fn))
                # attribute to surface: first path segment under HOME
                try:
                    rel = os.path.relpath(dirpath, HOME)
                except ValueError:
                    rel = dirpath
                seg = rel.split(os.sep)[0]
                counts[seg] += 1

print("scanned dirs:", scanned)
print("SKILL.md hits:", len(hits))
print("\n--- by top-level surface dir ---")
for k, v in counts.most_common():
    print(f"{v:5d}  {k}")
print("\n--- sample paths (first 40) ---")
for h in hits[:40]:
    print(h)
