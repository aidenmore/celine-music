import json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d = json.load(open(r"C:\Users\Thinkbook\OneDrive\Celine\hub\skills\registry.json", encoding="utf-8"))
names = {"game-studio", "agents-sdk", "dsh", "implicit-cad", "power-bi", "pretext",
         "reddit-reading", "kimi-webmcp", "mcode-tools-master", "inspecting-hermes-desktop-dom",
         "computer-use", "in-app-browser", "fast-browser-use", "playwright-scraper-skill",
         "blender-h3-dcc", "reverse-engineer-anything", "playwright-cli", "control-chrome",
         "chrome-devtools", "email-account-setup", "ios-simulator-browser", "game-playtest"}
seen = set()
for s in d["skills"]:
    if s["name"] in names and s["name"] not in seen:
        seen.add(s["name"])
        print(f"### {s['name']}  [{s['surface']}] cap={s['capability']}")
        print(f"    path: {s['source_path']}")
        print(f"    desc: {s['description'][:300]}")
        print(f"    tools: {s['tools_required']}")
        print()
print("missing from registry:", names - seen)
