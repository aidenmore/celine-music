"""Recon pass 2: per-root breakdown + check for non-SKILL.md skill formats."""
import os, collections

HOME = r"C:\Users\Thinkbook"

ROOTS = {
    "minimax-builtin":   os.path.join(HOME, ".minimax", ".builtin-skills"),
    "mavis-builtin":     os.path.join(HOME, ".mavis", ".builtin-skills"),
    "mavis-plugin-cache":os.path.join(HOME, ".mavis", "v2", "plugin-cache"),
    "codex-skills":      os.path.join(HOME, ".codex", "skills"),
    "codex-plugins":     os.path.join(HOME, ".codex", "plugins"),
    "claude":            os.path.join(HOME, ".claude"),
    "grok-bundled":      os.path.join(HOME, ".grok", "bundled", "skills"),
    "grok-marketplace":  os.path.join(HOME, ".grok", "marketplace-cache"),
    "grok-installed":    os.path.join(HOME, ".grok", "installed-plugins"),
    "hermes-skills":     os.path.join(HOME, "AppData", "Local", "hermes", "skills"),
    "hermes-agent":      os.path.join(HOME, "AppData", "Local", "hermes", "hermes-agent"),
    "vscode-user":       os.path.join(HOME, "AppData", "Roaming", "Code", "User"),
    "minimax-app":       os.path.join(HOME, "AppData", "Local", "Programs", "MiniMax Code"),
    "kimi-app":          os.path.join(HOME, "AppData", "Local", "Programs", "Kimi"),
    "opencode-config":   os.path.join(HOME, ".config", "opencode"),
    "opencode-desktop":  os.path.join(HOME, "AppData", "Roaming", "ai.opencode.desktop"),
    "kimi-code":         os.path.join(HOME, ".kimi-code"),
    "continue":          os.path.join(HOME, ".continue"),
    "gemini":            os.path.join(HOME, ".gemini"),
    "copilot":           os.path.join(HOME, ".copilot"),
    "cua-driver":        os.path.join(HOME, ".cua-driver"),
    "kimi-webbridge":    os.path.join(HOME, ".kimi-webbridge"),
    "kimi-work":         os.path.join(HOME, ".kimi-work"),
    "mcode":             os.path.join(HOME, ".mcode"),
    "cline":             os.path.join(HOME, ".cline"),
    "roo":               os.path.join(HOME, ".roo"),
    "aider":             os.path.join(HOME, ".aider"),
    "cursor":            os.path.join(HOME, ".cursor"),
}

SKIP = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".cache", "Cache",
        "Code Cache", "GPUCache", "temp", "tmp", "site-packages", ".pnpm-store",
        ".yarn", ".next", "target", ".pytest_cache", "logs", "log"}

for label, root in ROOTS.items():
    if not os.path.isdir(root):
        print(f"{label:20s} MISSING")
        continue
    n = 0
    dirs_hit = collections.Counter()
    for dp, dn, fns in os.walk(root):
        dn[:] = [x for x in dn if x not in SKIP]
        for fn in fns:
            if fn.lower() == "skill.md":
                n += 1
                dirs_hit[os.path.relpath(dp, root).split(os.sep)[0]] += 1
    top = ", ".join(f"{k}={v}" for k, v in dirs_hit.most_common(6))
    print(f"{label:20s} {n:5d}   [{top}]")

print("\n--- alt skill filename formats under each root ---")
ALT = ("skill.yaml", "skill.yml", "skill.json", "skills.md", "agent.md")
for label, root in ROOTS.items():
    if not os.path.isdir(root):
        continue
    found = collections.Counter()
    for dp, dn, fns in os.walk(root):
        dn[:] = [x for x in dn if x not in SKIP]
        for fn in fns:
            if fn.lower() in ALT:
                found[fn.lower()] += 1
    if found:
        print(f"{label:20s} {dict(found)}")
