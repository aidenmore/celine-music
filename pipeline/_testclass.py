import sys, importlib.util
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
spec = importlib.util.spec_from_file_location(
    "hs", r"C:\Users\Thinkbook\OneDrive\Celine\scripts\harvest_skills.py")
hs = importlib.util.module_from_spec(spec)
sys.modules["hs"] = hs
spec.loader.exec_module(hs)

CASES = [
    ("game-studio", "skills/game-studio/SKILL.md",
     "Route early browser-game work. Use when the user needs stack selection and workflow planning across design, implementation, assets, and playtesting before moving to a specialist skill."),
    ("game-playtest", "skills/game-playtest/SKILL.md",
     "Run browser-game playtests and frontend QA. Use when the user asks for smoke tests, screenshot-based verification, browser automation, HUD or overlay review."),
    ("reddit-reading", "optional-skills/social-media/reddit-reading/SKILL.md",
     "Read Reddit: subreddits, search, threads, users. No browser."),
    ("implicit-cad", "skills/implicit-cad/SKILL.md",
     "Create, edit, render, and snapshot browser-native implicit CAD `.implicit.js` files using GLSL signed-distance fields."),
    ("pretext", "optional-skills/creative/pretext/SKILL.md",
     "Build creative browser demos with DOM-free text layout."),
    ("power-bi", "power-bi/0.1.4/skills/power-bi/SKILL.md",
     "Explore reports, build visuals, and publish dashboards through Power BI in your browser. This is a browser workflow, not API integration or local application automation."),
    ("kimi-webmcp", "skills/kimi-webmcp/SKILL.md",
     "Use when the user asks to operate a WebMCP-enabled site, inspect or call tools registered by the current Work in-app browser page."),
    ("dsh", "skills/dsh/SKILL.md",
     "Start, open, and operate a local DeepSeek Harness Web instance. Use when the user mentions DeepSeek Harness, DSH Web, running Harness in the built-in browser."),
    ("computer-use", "skills/computer-use/SKILL.md",
     "Operate native desktop applications with the computer_* tools. Use for inspecting windows, clicking controls, typing, dragging, scrolling, and verifying desktop tasks."),
    ("email-account-setup", "skills/email-account-setup/SKILL.md",
     "使用 computer use / browser use 按内置服务商指南在用户指定邮箱的官方网页或客户端定位设置、生成授权码或应用密码"),
    ("fast-browser-use", "skills/fast-browser-use/SKILL.md",
     "Fastest browser automation with anti-bot bypass and DOM extraction. Navigate pages, capture screenshots, manage sessions via Chrome DevTools Protocol."),
    ("inspecting-hermes-desktop-dom", "software-development/inspecting-hermes-desktop-dom/SKILL.md",
     "Read the live Hermes desktop DOM/CSS over CDP."),
    ("blender-h3-dcc", "skills/blender-h3-dcc/SKILL.md",
     "Use for Blender white-model handoffs, H3 rendering, Blender extension installation, or conversational Blender blockouts."),
    ("mcode-tools-master", ".builtin-skills/mcode-tools-master/SKILL.md",
     "The mcode-tools CLI is available on PATH and serves two purposes: (1) multimodal generation and understanding, including images, video, audio, music; (2) discovering, inspecting, and calling all App/Connector tools."),
    ("reverse-engineer-anything", "skills/reverse-engineer-anything/SKILL.md",
     "Reverse engineer native binaries, .NET assemblies, JavaScript/Electron apps, packages, Android, firmware with REA."),
    ("agents-sdk", "skills/agents-sdk/SKILL.md",
     "Build AI agents on Cloudflare Workers using the Agents SDK. Load when creating stateful agents, durable workflows, MCP servers, or chat applications."),
    ("chrome-devtools", "skills/chrome-devtools/SKILL.md",
     "Uses Chrome DevTools via MCP for efficient debugging, troubleshooting and browser automation."),
    ("playwright-cli", "node_modules/playwright-core/lib/tools/skills/playwright-cli/SKILL.md",
     "Automate browser interactions, test web pages and work with Playwright tests."),
    ("control-chrome", "plugins/chrome/skills/control-chrome/SKILL.md",
     "Control the user's Chrome browser for tasks that depend on existing Chrome state: tabs, logged-in sessions, or extensions."),
    ("in-app-browser", "skills/in-app-browser/SKILL.md",
     "Use when a task involves opening, viewing, reading, or interacting with a web page - the built-in browser (right panel) is the default way to open URLs."),
    ("control-in-app-browser", "plugins/browser/skills/control-in-app-browser/SKILL.md",
     "Control the in-app browser."),
    ("web-research-note", "research/arxiv/SKILL.md",
     "Search arXiv for papers and produce grounded citations."),
    ("docx-hermes", "productivity/docx/SKILL.md",
     "Create and edit Word documents."),
    ("hermes-computer-use", "autonomous-ai-agents/computer-use/SKILL.md",
     "Use computer use to drive the desktop: mouse, keyboard and screenshots."),
]

print(f"{'name':34s} {'capability':20s} {'cu':5s} matched")
print("-" * 110)
for name, path, desc in CASES:
    cap, matched = hs.classify(name, path, desc, [])
    cu = hs.is_computer_driving(cap, name, path, desc)
    print(f"{name:34s} {cap:20s} {str(cu):5s} {matched[:2]}")
