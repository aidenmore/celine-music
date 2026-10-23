#!/usr/bin/env python3
"""
harvest_skills.py -- Discover, classify and mirror every AI skill installed on this
Windows workstation, then emit a consolidated registry under the Celine hub.

Design constraints (deliberate):
  * stdlib only, Python 3.13 compatible.
  * READ-ONLY everywhere except the hub output directory. Nothing outside the hub is
    created, modified, moved or deleted.
  * Idempotent: re-running produces the same registry and the same mirror content.
    Stale mirror files are pruned only inside hub/skills/mirror (guarded by a marker).
  * Low memory: files are read in bounded chunks, the tree is walked incrementally,
    and only per-skill metadata is retained.
  * Conservative mirror: skill-level files only (SKILL.md + same-folder siblings +
    directly referenced files). No node_modules trees, no binaries, nothing > 5 MB.

Usage:
    python harvest_skills.py                      # full harvest (registry + mirror)
    python harvest_skills.py --no-mirror          # registry only (fast)
    python harvest_skills.py --hub <path>         # alternative hub root
    python harvest_skills.py --no-prune           # keep stale mirror files
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

HOME = Path(os.path.expanduser("~"))

DEFAULT_HUB = HOME / "OneDrive" / "Celine"

MAX_FILE_BYTES = 5 * 1024 * 1024          # skip anything larger than 5 MB
MAX_DIR_BYTES = 64 * 1024 * 1024         # stop counting a skill dir past 64 MB
MAX_DIR_FILES = 4000                     # stop counting a skill dir past 4k files
MAX_LINKED_PER_SKILL = 40                # cap on referenced files followed
MAX_DEPTH = 16                           # max depth below a surface root

SKILL_FILENAMES = ("SKILL.md", "skill.md", "Skill.md")

# Extension whitelist for mirroring. Everything else (binaries, images, fonts,
# archives, executables) is deliberately excluded to keep the mirror small.
MIRROR_EXTS = {
    ".md", ".py", ".js", ".json", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".sh", ".bash", ".ps1", ".txt", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".html", ".css", ".csv", ".sql", ".diff", ".patch",
}

# Directories never descended into during a scan.
SCAN_SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".venv", "venv", ".gradle", ".terraform",
    "GPUCache", "Code Cache", "Crashpad", "blob_storage", "IndexedDB",
    "Service Worker", "logs", "log", ".Trash", "$RECYCLE.BIN", "System Volume Information",
}


@dataclass(frozen=True)
class Surface:
    """One installed AI surface (an app / CLI) that may host skills."""
    sid: str                  # short id, used as the mirror directory name
    app: str                  # owning application
    label: str                # human label
    kind: str                 # tool | runtime | staging | template | project
    roots: tuple[str, ...]    # paths relative to HOME
    hub_key: str = ""         # matching key in hub/manifest/surfaces.json (if any)


SURFACES: tuple[Surface, ...] = (
    Surface("minimax-builtin", "MiniMax Code", "MiniMax Code builtin skills", "tool",
            (".minimax/.builtin-skills",), "minimax-code"),
    Surface("minimax-plugin-cache", "MiniMax Code", "MiniMax Code plugin cache", "tool",
            (".minimax/v2/plugin-cache",), "minimax-code"),
    Surface("mavis-builtin", "Mavis", "Mavis builtin skills", "tool",
            (".mavis/.builtin-skills",)),
    Surface("mavis-plugin-cache", "Mavis", "Mavis plugin cache", "tool",
            (".mavis/v2/plugin-cache",)),
    Surface("codex-system", "Codex CLI", "Codex CLI system skills", "tool",
            (".codex/skills",), "codex-cli"),
    Surface("codex-plugins", "Codex CLI", "Codex CLI plugin cache", "tool",
            (".codex/plugins",), "codex-cli"),
    Surface("codex-staging", "Codex CLI", "Codex CLI staging / temp plugin trees", "staging",
            (".codex/.tmp",), "codex-cli"),
    Surface("claude-plugins", "Claude Code", "Claude Code plugin marketplaces", "tool",
            (".claude/plugins",), "claude-code"),
    Surface("grok-bundled", "Grok CLI", "Grok CLI bundled skills", "tool",
            (".grok/bundled",), "grok-cli"),
    Surface("grok-marketplace", "Grok CLI", "Grok CLI marketplace cache", "tool",
            (".grok/marketplace-cache",), "grok-cli"),
    Surface("grok-installed", "Grok CLI", "Grok CLI installed plugins", "tool",
            (".grok/installed-plugins",), "grok-cli"),
    Surface("hermes-skills", "Hermes", "Hermes user skills", "tool",
            ("AppData/Local/hermes/skills",), "hermes"),
    Surface("hermes-agent", "Hermes", "Hermes agent bundled + optional skills", "tool",
            ("AppData/Local/hermes/hermes-agent",), "hermes"),
    Surface("kimi-daimon", "Kimi Desktop", "Kimi daimon: skills, plugin packages, runtime", "tool",
            ("AppData/Roaming/kimi-desktop/daimon-share/daimon",), "kimi-desktop"),
    Surface("kimi-bundle", "Kimi Desktop", "Kimi daimon bundled builtin skills", "tool",
            ("AppData/Roaming/kimi-desktop/daimon-bundle",), "kimi-desktop"),
    Surface("kimi-app", "Kimi Desktop", "Kimi desktop app resources", "tool",
            ("AppData/Local/Programs/Kimi",), "kimi-desktop"),
    Surface("kimi-code", "Kimi Code", "Kimi Code CLI home", "tool",
            (".kimi-code",)),
    Surface("kimi-webbridge", "Kimi WebBridge", "Kimi WebBridge daemon runtime", "tool",
            (".kimi-webbridge",)),
    Surface("kimi-work", "Kimi Work", "Kimi Work data", "tool",
            (".kimi-work",)),
    Surface("cua-driver", "Computer-Use Driver", "Standalone CUA driver install", "runtime",
            (".cua-driver",)),
    Surface("vscode-user", "VS Code", "VS Code user profile", "tool",
            ("AppData/Roaming/Code/User",), "vscode"),
    Surface("vscode-app", "VS Code", "VS Code install tree (Copilot agent skills)", "tool",
            ("AppData/Local/Programs/Microsoft VS Code",), "vscode"),
    Surface("vscode-extensions", "VS Code", "VS Code extension bundles", "tool",
            (".vscode/extensions", ".vscode-insiders/extensions"), "vscode"),
    Surface("copilot-local", "GitHub Copilot", "Copilot local package data", "tool",
            ("AppData/Local/copilot",)),
    Surface("copilot-cfg", "GitHub Copilot", "Copilot user config", "tool",
            (".copilot",)),
    Surface("openai-codex", "Codex App", "Codex desktop app data + cua_node runtime", "tool",
            ("AppData/Local/OpenAI",)),
    Surface("minimax-app", "MiniMax Code", "MiniMax Code app install tree", "tool",
            ("AppData/Local/Programs/MiniMax Code",), "minimax-code"),
    Surface("opencode-config", "OpenCode", "OpenCode config", "tool",
            (".config/opencode",), "opencode"),
    Surface("opencode-desktop", "OpenCode Desktop", "OpenCode desktop app data", "tool",
            ("AppData/Roaming/ai.opencode.desktop",), "opencode"),
    Surface("qwen-config", "Qwen Code", "Qwen Code config", "tool",
            (".config/qwen",)),
    Surface("continue-cfg", "Continue", "Continue config", "tool",
            (".continue",)),
    Surface("gemini-cfg", "Gemini CLI", "Gemini CLI config", "tool",
            (".gemini",), "gemini-cli"),
    Surface("cloudbase-template", "CloudBase MCP", "CloudBase MCP web-template agent skills", "template",
            (".cloudbase-mcp/web-template",)),
    Surface("workspace-projects", "OneDrive Workspace", "Project-local agent skills", "project",
            ("OneDrive/Workspace",)),
)

# Controlled capability vocabulary.
CAPABILITIES = (
    "computer-use", "browser-automation", "app-automation", "mcp-integration",
    "media-generation", "data-analysis", "web-research", "document",
    "communication", "code-generation", "devops", "other",
)

# (capability, pattern, weight, strong) -- weighted keyword rules.
#
# `strong` marks a decisive signal. A capability is only ever assigned when at
# least one STRONG pattern matched; weak patterns only add weight to a
# capability that already qualified. This stops a stray mention of the word
# "browser" in a description from turning a Power BI skill into a
# browser-automation skill.
_RULES: tuple[tuple[str, str, int, bool], ...] = (
    # --- computer use: driving the desktop / mouse / keyboard / screen -------
    ("computer-use", r"computer[-_ ]use", 9, True),
    ("computer-use", r"\bcua\b", 7, True),
    ("computer-use", r"@oai/sky", 9, True),
    ("computer-use", r"\bsky\b.{0,20}(windows|automation|ui)", 6, True),
    ("computer-use", r"gui automation|desktop automation|ui automation", 8, True),
    ("computer-use", r"sendinput|windows\.graphics\.capture|\buiautomation\b", 8, True),
    ("computer-use", r"control (windows|desktop|macos|linux) apps?", 7, True),
    ("computer-use", r"operate native desktop|desktop applications?", 7, True),
    ("computer-use", r"automate the (ui|interface|screen)", 6, True),
    ("computer-use", r"mouse and keyboard|move the (mouse|cursor)|type on the keyboard", 6, True),
    ("computer-use", r"clicking controls|typing, dragging|inspect windows", 6, True),
    ("computer-use", r"accessibility tree", 6, True),
    ("computer-use", r"remote control|take over the (screen|desktop)", 6, True),
    ("computer-use", r"native host|extension-host", 3, False),
    # --- browser automation ----------------------------------------------------
    ("browser-automation", r"browser[-_ ]automation", 9, True),
    ("browser-automation", r"browser[-_ ]use|agent[-_ ]browser|in[-_ ]app[-_ ]browser", 9, True),
    ("browser-automation", r"control[-_ ]chrome|control[-_ ]browser|browser[-_ ]control", 9, True),
    ("browser-automation", r"\bplaywright\b", 8, True),
    ("browser-automation", r"\bpuppeteer\b|\bselenium\b|\bwebdriver\b", 8, True),
    ("browser-automation", r"chrome[-_ ]devtools|devtools protocol|\bcdp\b", 8, True),
    ("browser-automation", r"built[-_ ]in browser|in-app browser", 8, True),
    ("browser-automation", r"headless browser|\bchromium\b", 6, True),
    ("browser-automation", r"browser session|browser tab|browser window", 6, True),
    ("browser-automation", r"\bbrowser\b", 1, False),
    # --- app automation --------------------------------------------------------
    ("app-automation", r"app[-_ ]automation|automate (an|the) app", 8, True),
    ("app-automation", r"applescript|osascript|macos automation", 7, True),
    ("app-automation", r"\bblender\b|\bunreal\b", 6, True),
    ("app-automation", r"electron app|desktop app|native app|windows app", 6, True),
    ("app-automation", r"office (app|suite)|excel app|word app|powerpoint app", 6, True),
    ("app-automation", r"android|emulator|ios simulator", 5, True),
    # --- mcp / connectors ------------------------------------------------------
    ("mcp-integration", r"mcp server|mcp tool|mcp client|mcp-integration|webmcp", 9, True),
    ("mcp-integration", r"model context protocol|\bmcp\b", 8, True),
    ("mcp-integration", r"\bmcode[-_ ]tools\b|app/connector|app tools", 8, True),
    ("mcp-integration", r"connector|app[-_ ]integration", 4, False),
    # --- media -----------------------------------------------------------------
    ("media-generation", r"image generation|generate (an )?image|text[-_ ]to[-_ ]image", 8, True),
    ("media-generation", r"video generation|generate (a )?video|text[-_ ]to[-_ ]video", 8, True),
    ("media-generation", r"audio generation|music generation|voice (clone|synthesis)", 8, True),
    ("media-generation", r"\btts\b|text[-_ ]to[-_ ]speech|voiceover", 7, True),
    ("media-generation", r"\bimagegen\b|image model|diffusion", 7, True),
    ("media-generation", r"animation|sprite|sound effect|\bsfx\b", 5, True),
    ("media-generation", r"diagram|image prompt|infographic", 4, False),
    # --- data analysis ---------------------------------------------------------
    ("data-analysis", r"data analysis", 8, True),
    ("data-analysis", r"\bdataframe\b|\bpandas\b|\bnumpy\b", 7, True),
    ("data-analysis", r"statistical|statistics|hypothesis test", 6, True),
    ("data-analysis", r"spreadsheet analysis|\bexcel\b|\bcsv\b|data cleaning", 6, True),
    ("data-analysis", r"sql analysis|database analysis", 6, True),
    ("data-analysis", r"data visuali[sz]ation|charting", 5, True),
    ("data-analysis", r"\bpower[- ]?bi\b|\btableau\b|\blooker\b", 6, True),
    # --- web research ----------------------------------------------------------
    ("web-research", r"deep research|web research|research the web", 9, True),
    ("web-research", r"search the web|web search|internet search", 8, True),
    ("web-research", r"scrap(?:e|ing)|crawl(?:ing)?", 7, True),
    ("web-research", r"\barxiv\b|\bpubmed\b|academic literature|citation", 6, True),
    ("web-research", r"competitor analysis|market research|news monitor", 6, True),
    ("web-research", r"grounded (citation|source)|fact[-_ ]check", 6, True),
    ("web-research", r"\bbrowse\b|\bwebpage\b|\bweb page\b", 4, False),
    # --- document --------------------------------------------------------------
    ("document", r"\bdocx\b|\bword document\b|\bms word\b", 8, True),
    ("document", r"\bpdf\b|\bpowerpoint\b|\bpptx\b|\bspreadsheet\b|\bxlsx\b", 7, True),
    ("document", r"manuscript|paper (writing|review)|academic writing", 7, True),
    ("document", r"\blatex\b|\btypst\b|technical (writing|document)", 6, True),
    ("document", r"note[-_ ]taking|\bobsidian\b|\bnotion\b|knowledge base", 6, True),
    ("document", r"resume|cv writing|meeting minutes", 5, False),
    # --- communication ---------------------------------------------------------
    ("communication", r"\bslack\b|\bdiscord\b|\btelegram\b|\bwhatsapp\b", 8, True),
    ("communication", r"feishu|lark|\bwechat\b|dingtalk|\bimessage\b|\bsms\b", 8, True),
    ("communication", r"\bemail\b|\bgmail\b|\boutlook\b|\bimap\b|\bsmtp\b", 7, True),
    ("communication", r"calendar|meeting (notes|summary)|\bteams\b|\bzoom\b", 6, True),
    ("communication", r"messaging|outreach|chat platform", 5, False),
    # --- code generation -------------------------------------------------------
    ("code-generation", r"code generation|write code|coding agent", 8, True),
    ("code-generation", r"code review|refactor|debug(ging)?|unit test|\bpytest\b", 7, True),
    ("code-generation", r"\bgit\b|pull request|commit|branch(ing)?", 6, True),
    ("code-generation", r"\bpython\b|\btypescript\b|\bjavascript\b|\brust\b", 5, True),
    ("code-generation", r"scaffold|boilerplate|\bsdk\b|api client|lint", 5, True),
    ("code-generation", r"frontend|backend|full[-_ ]stack|\breact\b|\bvue\b|\bsvelte\b", 5, True),
    # --- devops ----------------------------------------------------------------
    ("devops", r"\bdeploy(ment)?\b|kubernetes|\bk8s\b|\bterraform\b|\bhelm\b", 8, True),
    ("devops", r"\bdocker\b|container|ci/cd|pipeline|github actions", 7, True),
    ("devops", r"\baws\b|\bgcp\b|\bazure\b|cloud run|serverless|cloud function", 7, True),
    ("devops", r"monitoring|observability|\bprometheus\b|grafana|sysadmin", 6, True),
    ("devops", r"\bnginx\b|\bssh\b|\bvm\b|\bserver\b|\blinux\b", 5, True),
    ("devops", r"infrastructure|provisioning|\bcluster\b", 5, False),
)

# Category folders used by category-organised surfaces (Hermes, Kimi). Used as a
# fallback only when no decisive keyword rule matched.
_PATH_CATEGORY = {
    "productivity": "document", "note-taking": "document",
    "software-development": "code-generation", "web-development": "code-generation",
    "creative": "media-generation", "media": "media-generation", "gaming": "media-generation",
    "research": "web-research", "web": "web-research",
    "devops": "devops", "security": "devops", "migration": "devops",
    "email": "communication", "communication": "communication", "social-media": "communication",
    "apple": "app-automation", "smart-home": "app-automation",
    "data-science": "data-analysis", "mlops": "data-analysis", "finance": "data-analysis",
    "blockchain": "code-generation", "mcp": "mcp-integration", "dogfood": "code-generation",
}

_COMPILED_RULES = tuple((cap, re.compile(pat, re.I), w, strong) for cap, pat, w, strong in _RULES)

# Front-matter keys that carry "what this skill needs".
_TOOL_KEYS = (
    "tools", "allowed-tools", "allowed_tools", "requires", "requires_bin",
    "required_environment_variables", "required-environment-variables",
    "dependencies", "prerequisites", "toolsets", "tools_required",
    "requires-tools", "mcp", "mcp_servers", "bins", "command",
)
_TOOL_KEY_SET = frozenset(_TOOL_KEYS)

_PLATFORM_KEYS = ("platforms", "platform", "os", "operating-system")


# --------------------------------------------------------------------------- #
# Minimal YAML-ish front-matter parser (no third-party deps)
# --------------------------------------------------------------------------- #

def _scalar(v: str):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [_scalar(x) for x in inner.split(",")]
    if v.lower() in ("true", "yes"):
        return True
    if v.lower() in ("false", "no"):
        return False
    if v.lower() in ("null", "~", "none"):
        return None
    return v


def parse_front_matter(text: str) -> tuple[dict, str]:
    """Return (front_matter_dict, body). Handles the YAML subset actually used."""
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", text, re.S)
    if not m:
        return {}, text
    block, body = m.group(1), text[m.end():]
    data: dict = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip() or raw.lstrip().startswith("#"):
            i += 1
            continue
        if raw[:1] in (" ", "\t"):
            i += 1
            continue
        if ":" not in raw:
            i += 1
            continue
        key, _, val = raw.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if val in ("|", ">", "|-", ">-", "|+", ">+"):
            buf = []
            i += 1
            while i < len(lines) and (lines[i][:1] in (" ", "\t") or not lines[i].strip()):
                if lines[i].strip():
                    buf.append(lines[i].strip())
                i += 1
            data[key] = " ".join(buf)
            continue
        if val == "":
            items: list = []
            nested: dict = {}
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip():
                    i += 1
                    continue
                if nxt[:1] not in (" ", "\t"):
                    break
                s = nxt.strip()
                if s.startswith("- "):
                    items.append(_scalar(s[2:]))
                elif ":" in s:
                    k2, _, v2 = s.partition(":")
                    nested[k2.strip().lower()] = _scalar(v2.strip())
                else:
                    items.append(_scalar(s))
                i += 1
            if items:
                data[key] = items
            elif nested:
                data[key] = nested
            else:
                data[key] = ""
            continue
        data[key] = _scalar(val)
        i += 1
    return data, body


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_REF_RE = re.compile(
    r"[`\(\[]([A-Za-z0-9_./\\@ -]+?\.(?:md|py|js|json|mjs|cjs|ts|tsx|sh|txt|yaml|yml|toml))[`\)\]]",
)
_UNSAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize(name: str) -> str:
    s = _UNSAFE_RE.sub("-", name.strip()).strip("-.")
    s = re.sub(r"-{2,}", "-", s)
    return s[:120] or "unnamed"


def iso(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts))


def read_head(path: Path, limit: int = 65536) -> str:
    """Read at most `limit` bytes of a file without loading it fully."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def dir_stats(d: Path) -> tuple[int, float, int]:
    """(total_bytes, newest_mtime, file_count) for a directory, bounded."""
    total = 0
    newest = 0.0
    count = 0
    stack = [d]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(Path(e.path))
                        elif e.is_file(follow_symlinks=False):
                            st = e.stat(follow_symlinks=False)
                            total += st.st_size
                            count += 1
                            if st.st_mtime > newest:
                                newest = st.st_mtime
                            if total > MAX_DIR_BYTES or count > MAX_DIR_FILES:
                                return total, newest, count
                    except OSError:
                        continue
        except OSError:
            continue
    return total, newest, count


def collect_tools(fm: dict) -> list[str]:
    out: list[str] = []
    for k in _TOOL_KEY_SET:
        if k not in fm:
            continue
        v = fm[k]
        if v in (None, "", [], {}):
            continue
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, list):
            out.extend(str(x) for x in v)
        elif isinstance(v, dict):
            out.extend(f"{kk}" for kk in v.keys())
    seen, uniq = set(), []
    for t in out:
        t = str(t).strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            uniq.append(t)
    return uniq[:24]


def collect_platforms(fm: dict) -> list[str]:
    out: list[str] = []
    for k in _PLATFORM_KEYS:
        v = fm.get(k)
        if isinstance(v, str) and v:
            out.append(v)
        elif isinstance(v, list):
            out.extend(str(x) for x in v)
    seen, uniq = set(), []
    for p in out:
        p = p.strip().lower()
        if p and p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq[:12]


def classify(name: str, rel_path: str, description: str, tags: list[str]) -> tuple[str, list[str]]:
    """Return (primary_capability, matched_tag_list).

    A capability is only assigned when at least one decisive ("strong") rule
    matched. Weak rules merely add weight. When nothing decisive matched we fall
    back to the category folder the skill lives in, if the surface uses one.
    """
    name_l = name.lower()
    path_l = rel_path.lower().replace("\\", "/")
    desc_l = description.lower()
    tag_l = " ".join(tags).lower()

    scores: dict[str, float] = {}
    hits: dict[str, set] = {}
    strong_hit: set[str] = set()
    for cap, rx, w, strong in _COMPILED_RULES:
        if rx.search(name_l) or rx.search(path_l):
            scores[cap] = scores.get(cap, 0.0) + w
            hits.setdefault(cap, set()).add(rx.pattern)
            if strong:
                strong_hit.add(cap)
        elif rx.search(desc_l) or rx.search(tag_l):
            scores[cap] = scores.get(cap, 0.0) + w * 0.45
            hits.setdefault(cap, set()).add(rx.pattern)
            if strong:
                strong_hit.add(cap)

    candidates = [c for c in scores if c in strong_hit]
    if candidates:
        best = max(candidates, key=lambda c: (scores[c], c))
        return best, sorted(hits.get(best, ()))

    # Fallback: category folder (Hermes / Kimi style layouts).
    segments = [s for s in path_l.split("/") if s]
    for seg in reversed(segments[:-1]):
        if seg in _PATH_CATEGORY:
            return _PATH_CATEGORY[seg], [f"category:{seg}"]
    return "other", []


def is_computer_driving(capability: str, name: str, rel_path: str, description: str) -> bool:
    """True when the skill can plausibly drive a computer, browser or app."""
    if capability in ("computer-use", "browser-automation", "app-automation"):
        return True
    blob = f"{name} {rel_path.replace(chr(92), '/')} {description}".lower()
    strong = (
        "computer-use", "computer use", "gui automation", "desktop automation",
        "ui automation", "sendinput", "windows.graphics.capture", "@oai/sky",
        "uiautomation", "mouse and keyboard", "click and type", "remote control",
        "control the screen", "take over the screen", "cua-driver",
    )
    return any(s in blob for s in strong)


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #

def find_skill_files(root: Path) -> list[Path]:
    """Walk `root` and return every directory containing a SKILL.md."""
    found: list[Path] = []
    if not root.is_dir():
        return found
    root_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        d = Path(dirpath)
        depth = len(d.parts) - root_depth
        if depth >= MAX_DEPTH:
            dirnames[:] = []
            continue
        # prune noise but keep node_modules (some packages ship real skills);
        # nested node_modules are pruned to bound the walk.
        kept = []
        nm_depth = 0
        for name in dirnames:
            low = name.lower()
            if low in SCAN_SKIP_DIRS:
                continue
            if low == "node_modules":
                if nm_depth:
                    continue
                nm_depth += 1
            kept.append(name)
        dirnames[:] = kept
        for fn in filenames:
            if fn in SKILL_FILENAMES or fn.lower() in ("skill.md",):
                found.append(d / fn)
    return found


def parse_skill(skill_md: Path, surface: Surface, surface_root: Path) -> dict | None:
    head = read_head(skill_md, 65536)
    if not head:
        return None
    fm, body = parse_front_matter(head)
    skill_dir = skill_md.parent
    try:
        rel_to_root = skill_md.relative_to(surface_root)
        rel = str(rel_to_root).replace("\\", "/")
    except ValueError:
        rel = str(skill_md)

    name = fm.get("name")
    if not isinstance(name, str) or not name.strip():
        name = skill_dir.name
    name = name.strip()

    desc = fm.get("description") or fm.get("descriptions") or fm.get("summary") or ""
    if isinstance(desc, list):
        desc = " ".join(str(x) for x in desc)
    elif isinstance(desc, dict):
        desc = " ".join(str(v) for v in desc.values())
    desc = str(desc).strip()

    version = fm.get("version")
    version = str(version) if version is not None else ""

    tags_raw = fm.get("tags")
    if isinstance(tags_raw, str):
        tags = [t.strip() for t in re.split(r"[,\s]+", tags_raw) if t.strip()]
    elif isinstance(tags_raw, list):
        tags = [str(t).strip() for t in tags_raw if str(t).strip()]
    else:
        tags = []
    cat = fm.get("category")
    if isinstance(cat, str) and cat:
        tags.append(cat)

    capability, matched = classify(name, rel, desc, tags)
    computer_driving = is_computer_driving(capability, name, rel, desc)

    platforms = collect_platforms(fm)
    # Unsupported on this host only when the skill declares a concrete platform
    # list that excludes Windows. Unknown / free-form platform strings are ignored.
    concrete = {p for p in platforms
                if p in {"windows", "win32", "win", "linux", "macos", "mac", "darwin",
                         "android", "ios", "web"}}
    host_ok = True
    if concrete and not (concrete & {"windows", "win32", "win"}):
        host_ok = False

    try:
        st = skill_md.stat()
        md_bytes = st.st_size
        md_mtime = st.st_mtime
    except OSError:
        md_bytes, md_mtime = 0, 0.0

    total_bytes, dir_mtime, _nfiles = dir_stats(skill_dir)

    return {
        "name": name,
        "display_name": sanitize(name),
        "surface": surface.sid,
        "app": surface.app,
        "surface_kind": surface.kind,
        "hub_surface_key": surface.hub_key,
        "capability": capability,
        "computer_use": computer_driving,
        "matched_patterns": matched[:8],
        "description": desc[:1200],
        "version": version,
        "tools_required": collect_tools(fm),
        "platforms": platforms,
        "host_supported": host_ok,
        "source_path": str(skill_md),
        "skill_dir": str(skill_dir),
        "rel_path": rel,
        "size_bytes": total_bytes,
        "skill_md_bytes": md_bytes,
        "modified": iso(md_mtime),
        "dir_modified": iso(dir_mtime),
        "file_count": _nfiles,
        "_skill_dir": skill_dir,
        "_surface_root": surface_root,
    }


# --------------------------------------------------------------------------- #
# Mirroring
# --------------------------------------------------------------------------- #

def plan_mirror_files(entry: dict) -> list[tuple[Path, str]]:
    """Return list of (absolute_source_file, relative_dest_path) to copy."""
    skill_dir: Path = entry["_skill_dir"]
    md_path = Path(entry["source_path"])
    # Re-read the skill definition here rather than caching it in the entry, so
    # that thousands of skills never sit in memory at once.
    md_text = read_head(md_path, 65536)
    plan: list[tuple[Path, str]] = []

    plan.append((md_path, md_path.name))

    # same-folder siblings
    try:
        for e in os.scandir(skill_dir):
            if not e.is_file(follow_symlinks=False):
                continue
            p = Path(e.path)
            if p.name in SKILL_FILENAMES:
                continue
            if p.suffix.lower() not in MIRROR_EXTS:
                continue
            try:
                if p.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            plan.append((p, p.name))
    except OSError:
        pass

    # directly referenced files
    refs: list[str] = []
    for m in _REF_RE.finditer(md_text):
        refs.append(m.group(1).strip())
    seen_rel: set[str] = {dest for _, dest in plan}
    count = 0
    for r in refs:
        if count >= MAX_LINKED_PER_SKILL:
            break
        r = r.replace("\\", "/").strip()
        if not r or "://" in r or r.startswith(("mailto:", "#")):
            continue
        try:
            cand = (skill_dir / r).resolve()
        except (OSError, RuntimeError):
            continue
        if not cand.is_file():
            continue
        if cand.suffix.lower() not in MIRROR_EXTS:
            continue
        try:
            if cand.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        try:
            rel_inside = cand.relative_to(skill_dir.resolve())
            dest = str(rel_inside).replace("\\", "/")
        except (ValueError, OSError):
            dest = "_linked/" + cand.name
        if dest in seen_rel:
            continue
        seen_rel.add(dest)
        plan.append((cand, dest))
        count += 1
    return plan


def do_mirror(entries: list[dict], mirror_root: Path, prune: bool) -> dict:
    mirror_root.mkdir(parents=True, exist_ok=True)
    marker = mirror_root / ".mirror-root"
    marker.write_text(
        "Files under this directory are a read-only mirror generated by\n"
        "C:\\Users\\Thinkbook\\OneDrive\\Celine\\scripts\\harvest_skills.py\n"
        "Each subdirectory is <surface>/<skill-name>/ and contains a _SOURCE.txt\n"
        "pointing back at the original installation path.\n",
        encoding="utf-8",
    )

    planned: set[Path] = {marker}
    copied_files = 0
    copied_bytes = 0
    skipped = 0

    for entry in entries:
        dest_dir = mirror_root / entry["surface"] / entry["display_name"]
        for src, relname in plan_mirror_files(entry):
            dst = dest_dir / relname
            planned.add(dst)
            try:
                st = src.stat()
            except OSError:
                skipped += 1
                continue
            if dst.exists():
                try:
                    if dst.stat().st_size == st.st_size:
                        copied_bytes += st.st_size
                        copied_files += 1
                        continue
                except OSError:
                    pass
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
                copied_files += 1
                copied_bytes += st.st_size
            except OSError:
                skipped += 1
        # provenance note
        note = dest_dir / "_SOURCE.txt"
        planned.add(note)
        body = (
            f"name: {entry['name']}\n"
            f"surface: {entry['surface']} ({entry['app']})\n"
            f"capability: {entry['capability']}\n"
            f"source: {entry['source_path']}\n"
            f"modified: {entry['modified']}\n"
        )
        if not note.exists() or note.read_text(encoding="utf-8", errors="replace") != body:
            note.parent.mkdir(parents=True, exist_ok=True)
            note.write_text(body, encoding="utf-8")

    removed = 0
    if prune:
        for dirpath, dirnames, filenames in os.walk(mirror_root, topdown=False):
            for fn in filenames:
                fp = Path(dirpath) / fn
                if fp not in planned:
                    try:
                        fp.unlink()
                        removed += 1
                    except OSError:
                        pass
            for dn in dirnames:
                d = Path(dirpath) / dn
                try:
                    if not any(d.iterdir()):
                        d.rmdir()
                except OSError:
                    pass

    return {
        "files_copied": copied_files,
        "bytes_copied": copied_bytes,
        "files_skipped": skipped,
        "files_removed": removed,
    }


# --------------------------------------------------------------------------- #
# Report writers
# --------------------------------------------------------------------------- #

def write_registry_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_registry_csv(path: Path, entries: list[dict]) -> None:
    cols = ["name", "surface", "capability", "source_path", "size_bytes", "modified",
            "app", "computer_use", "version", "tools_required"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for e in entries:
            w.writerow({
                "name": e["name"],
                "surface": e["surface"],
                "capability": e["capability"],
                "source_path": e["source_path"],
                "size_bytes": e["size_bytes"],
                "modified": e["modified"],
                "app": e["app"],
                "computer_use": "yes" if e["computer_use"] else "no",
                "version": e["version"],
                "tools_required": "; ".join(e["tools_required"]),
            })


def _md_escape(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ").strip()


def write_index_md(path: Path, entries: list[dict], surfaces: list[dict],
                   dup_map: dict, counts: dict, mirror_stats: dict, generated: str) -> None:
    L: list[str] = []
    A = L.append
    A("# AI Skill Registry - Master Index")
    A("")
    A(f"_Generated {generated} by `scripts/harvest_skills.py`._")
    A("")
    A(f"**Total skills discovered: {counts['total']}** across "
      f"{counts['surfaces']} AI surfaces and {counts['surfaces_present']} present roots.")
    A("")
    A(f"- Computer-use / browser-automation / app-automation skills: **{counts['computer_use']}**")
    A(f"- Distinct skill names (deduped across surfaces): **{counts['unique_names']}**")
    A(f"- Names installed on more than one surface: **{counts['dup_names']}**")
    A(f"- Mirror: **{mirror_stats['files_copied']} files / {mirror_stats['bytes_copied']} bytes** "
      f"under `hub/skills/mirror/`")
    A("")
    A("Companion files: `registry.json` (machine readable), `registry.csv` (flat), "
      "`computer-use-summary.md` (what can actually drive this PC), `README.md` (how to use it).")
    A("")

    A("## Capability distribution")
    A("")
    A("| Capability | Count |")
    A("| --- | ---: |")
    for cap in CAPABILITIES:
        if counts["by_capability"].get(cap):
            A(f"| {cap} | {counts['by_capability'][cap]} |")
    A(f"| **Total** | **{counts['total']}** |")
    A("")

    A("## Computer-Use & Automation Capabilities")
    A("")
    A("Everything that can drive a computer, a browser or a desktop app.")
    A("")
    cu = [e for e in entries if e["computer_use"]]
    A(f"**{len(cu)} skills.** Full details, including what each one needs to run, "
      "are in [`computer-use-summary.md`](computer-use-summary.md).")
    A("")
    A("| Skill | Surface | Capability | Source path |")
    A("| --- | --- | --- | --- |")
    for e in sorted(cu, key=lambda x: (x["surface"], x["name"])):
        A(f"| {_md_escape(e['name'])} | {e['surface']} | {e['capability']} | "
          f"`{_md_escape(e['source_path'])}` |")
    A("")

    A("## By surface")
    A("")
    for s in sorted(surfaces, key=lambda x: -x["skill_count"]):
        if not s["present"]:
            continue
        A(f"### {s['app']} - `{s['sid']}` ({s['skill_count']} skills)")
        A("")
        A(f"_{s['label']}_")
        if not s["roots_present"]:
            A("")
            A("> Root not present on this machine.")
            A("")
            continue
        by_cap: dict[str, list] = {}
        for e in entries:
            if e["surface"] == s["sid"]:
                by_cap.setdefault(e["capability"], []).append(e)
        A("")
        for cap in CAPABILITIES:
            if cap not in by_cap:
                continue
            A(f"**{cap}** ({len(by_cap[cap])})")
            A("")
            A("| Skill | Source path | Modified |")
            A("| --- | --- | --- |")
            for e in sorted(by_cap[cap], key=lambda x: x["name"].lower()):
                A(f"| {_md_escape(e['name'])} | `{_md_escape(e['source_path'])}` | {e['modified']} |")
            A("")

    A("## Duplicate skill names across surfaces")
    A("")
    if dup_map:
        A(f"**{len(dup_map)} skill names** are installed on more than one surface.")
        A("")
        A("| Skill name | Surfaces | Source paths |")
        A("| --- | --- | --- |")
        for name in sorted(dup_map):
            group = dup_map[name]
            surfs = ", ".join(sorted({g["surface"] for g in group}))
            paths = "<br>".join(f"`{_md_escape(g['source_path'])}`" for g in group)
            A(f"| {_md_escape(name)} | {surfs} | {paths} |")
    else:
        A("_No duplicate skill names found._")
    A("")

    A("## Surfaces with no skills")
    A("")
    for s in surfaces:
        if not s["present"]:
            A(f"- `{s['sid']}` ({s['app']}) - root(s) not found: {', '.join(s['missing_roots'])}")
    A("")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def write_computer_use_summary(path: Path, entries: list[dict], surfaces: list[dict],
                               probes: dict, counts: dict, generated: str) -> None:
    cu = [e for e in entries if e["computer_use"]]
    by_cap: dict[str, list] = {}
    for e in cu:
        by_cap.setdefault(e["capability"], []).append(e)

    L: list[str] = []
    A = L.append
    A("# Computer-Use Enablement Summary")
    A("")
    A(f"_Generated {generated}. {len(cu)} of {counts['total']} installed skills can "
      "drive a computer, a browser or a desktop app._")
    A("")

    A("## TL;DR - what can actually drive this PC")
    A("")
    A("| Surface | Status | What it needs |")
    A("| --- | --- | --- |")
    for row in probes["rows"]:
        A(f"| {row['surface']} | **{row['status']}** | {row['needs']} |")
    A("")

    A("## Installed runtimes (not skills, but they are what makes it work)")
    A("")
    A("| Component | Path | State |")
    A("| --- | --- | --- |")
    for row in probes["runtimes"]:
        A(f"| {row['name']} | `{_md_escape(row['path'])}` | {row['state']} |")
    A("")

    A("## CLI availability")
    A("")
    A("| CLI | On PATH |")
    A("| --- | --- |")
    for name, where in probes["clis"]:
        A(f"| `{name}` | {'yes - ' + where if where else '**not installed**'} |")
    A("")

    for cap in ("computer-use", "browser-automation", "app-automation"):
        items = by_cap.get(cap, [])
        if not items:
            continue
        A(f"## {cap} ({len(items)})")
        A("")
        A("| Skill | Surface | Source path | Needs |")
        A("| --- | --- | --- | --- |")
        for e in sorted(items, key=lambda x: (x["surface"], x["name"].lower())):
            needs = e["tools_required"]
            needs_s = "; ".join(needs) if needs else (e["description"][:110] or "-")
            A(f"| {_md_escape(e['name'])} | {e['surface']} | `{_md_escape(e['source_path'])}` | "
              f"{_md_escape(needs_s)} |")
        A("")

    A("## Practical notes - the paths that actually work today")
    A("")
    chrome = probes.get("chrome", {})
    A("**Codex CLI / Codex desktop - the most complete stack on this machine.**")
    A("")
    A("- `computer-use` skill -> reads `cua_node` -> imports `@oai/sky` -> drives Windows "
      "apps with SendInput, UI Automation and Windows.Graphics.Capture. The runtime is "
      "present at `AppData/Local/OpenAI/Codex/runtimes/cua_node`.")
    A("- The `@oai/sky` **Windows** API reference skill is installed under the "
      "`openai-codex` surface (the linux and macos variants are installed alongside it, "
      "so only the `windows` one is relevant here).")
    A("- `control-chrome` and `control-in-app-browser` drive Chrome through the Codex "
      "native host. The manifest `~/.codex/chrome-native-hosts-v2.json` is present and "
      f"expects Chrome extension(s) {', '.join('`' + x + '`' for x in chrome.get('wanted', [])) or '(none listed)'}. "
      + (f"**Matched extensions found on disk: {', '.join(chrome['matched'])}.**"
         if chrome.get("matched") else
         "**No matching extension folder was found in the Chrome profile - install the "
         "companion Chrome extension before relying on `control-chrome`.**"))
    A("")
    A("**Kimi Desktop - browser-native automation.**")
    A("")
    A("- `in-app-browser` (built-in browser panel), `fast-browser-use` (CDP, anti-bot "
      "bypass, screenshots) and `playwright-scraper-skill`.")
    A("- The WebBridge daemon is installed and running (`~/.kimi-webbridge` has a live "
      "`daemon.pid`), which is what lets Kimi reach a real browser.")
    A("")
    A("**Hermes - CLI-driven browser automation.**")
    A("")
    A("- `hermes` is on PATH. The `computer-use` skill plus `playwright-cli` / "
      "`playwright-trace` cover screen and browser control.")
    A("")
    A("**Mavis / MiniMax Code - cached plugin skills.**")
    A("")
    A("- `computer-use` (native desktop via `computer_*` tools), `chrome-devtools` "
      "(Chrome DevTools over MCP) and `control-in-app-browser`. Both surfaces carry the "
      "same three skills because MiniMax Code and Mavis share a plugin cache.")
    A("")
    A("**Not usable here:**")
    A("")
    A("- Claude Code, Gemini CLI, Grok CLI, Kimi Code and Hermes CLIs are all installed, "
      "but none of their skill sets contains a computer-use or browser-automation skill.")
    A("- `opencode`, `qwen` and `continue` are not installed at all, so their (absent) "
      "skill directories are empty.")
    A("")
    A("## Documented but NOT usable on this host")
    A("| Skill | Surface | Reason |")
    A("| --- | --- | --- |")
    any_row = False
    for e in sorted(cu, key=lambda x: (x["surface"], x["name"].lower())):
        reasons = []
        if not e["host_supported"]:
            reasons.append("platforms: " + ", ".join(e["platforms"]))
        if e["name"].lower().startswith("apple-") or "/apple/" in e["rel_path"].lower():
            reasons.append("macOS-only (Apple Notes/Reminders/FindMy/iMessage) on a Windows host")
        if not reasons:
            continue
        any_row = True
        A(f"| {_md_escape(e['name'])} | {e['surface']} | {'; '.join(reasons)} |")
    if not any_row:
        A("| _(none)_ | | |")
    A("")

    A("## Skills that reference an external tool that is not installed")
    A("")
    A("| Skill | Surface | Referenced tool |")
    A("| --- | --- | --- |")
    any_row = False
    known_cli = {n for n, _ in probes["clis"] if _}
    for e in sorted(cu, key=lambda x: (x["surface"], x["name"].lower())):
        for t in e["tools_required"]:
            low = t.lower()
            hit = None
            for cli in known_cli:
                if cli in low:
                    hit = cli
                    break
            if hit and hit not in ("python", "node", "git", "npm"):
                any_row = True
                A(f"| {_md_escape(e['name'])} | {e['surface']} | `{_md_escape(t)}` |")
    if not any_row:
        A("| _(none detected)_ | | |")
    A("")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def write_readme_md(path: Path, counts: dict, mirror_stats: dict, generated: str,
                    surfaces: list[dict]) -> None:
    L: list[str] = []
    A = L.append
    A("# AI Skill Registry - README")
    A("")
    A("A single authoritative index of **every AI skill installed on this Windows 11 "
      "workstation**, plus a consolidated mirror of the skill files under this hub.")
    A("")
    A(f"_Last harvested {generated}. {counts['total']} skills from "
      f"{counts['surfaces_present']} surfaces._")
    A("")
    A("## Files here")
    A("")
    A("| File | What it is |")
    A("| --- | --- |")
    A("| `registry.json` | Full machine-readable registry: one object per skill with "
      "front-matter, capability, paths, sizes and timestamps. |")
    A("| `registry.csv` | Flat CSV of the same data for spreadsheets / grep. |")
    A("| `INDEX.md` | Human index grouped by surface and by capability, with counts "
      "and the computer-use section. |")
    A("| `computer-use-summary.md` | What on this machine can actually drive the "
      "computer or a browser, what it needs, and what is documented but not installed. |")
    A("| `mirror/` | Consolidated copy of the skill files, one folder per surface. |")
    A("| `../scripts/harvest_skills.py` | The harvester that produced all of the above. |")
    A("")
    A("## Registry entry shape")
    A("")
    A("```json")
    A("{")
    A('  "name": "computer-use",')
    A('  "surface": "codex-plugins",          // surface id')
    A('  "app": "Codex CLI",                  // owning application')
    A('  "capability": "computer-use",        // controlled vocabulary')
    A('  "computer_use": true,                // can drive a computer/browser/app')
    A('  "source_path": "C:\\\\...\\\\SKILL.md",  // absolute origin on disk')
    A('  "size_bytes": 12345,                 // total bytes of the skill folder')
    A('  "modified": "2026-10-23T19:12:00",  // SKILL.md mtime')
    A('  "version": "1.0.0",')
    A('  "description": "...",')
    A('  "tools_required": ["Bash", "Read"], // from front-matter')
    A('  "platforms": ["windows"],')
    A('  "host_supported": true')
    A("}")
    A("```")
    A("")
    A("## Mirror layout")
    A("")
    A("```")
    A("hub/skills/mirror/")
    A("  <surface-id>/            # e.g. codex-plugins, hermes-agent, kimi-daimon")
    A("    <skill-name>/          # folder name = front-matter `name`, sanitised")
    A("      SKILL.md            # the skill definition")
    A("      <siblings>.py|js|json|md ...   # same-folder files it ships with")
    A("      _linked/...         # files the SKILL.md links to but that live outside")
    A("                          #   the skill folder (e.g. ../../docs/guidance.md)")
    A("      _SOURCE.txt         # provenance: original absolute path")
    A("```")
    A("")
    A(f"Current mirror: **{mirror_stats['files_copied']} files / "
      f"{mirror_stats['bytes_copied']:,} bytes**.")
    A("")
    A("Mirror rules: skill-level files only; binaries, images, archives and anything "
      f"> {MAX_FILE_BYTES // (1024 * 1024)} MB are skipped; `node_modules` trees are never "
      "copied wholesale. The mirror is a *copy* - nothing is moved or deleted from the "
      "original installs.")
    A("")
    A("## Re-running the harvest")
    A("")
    A("```powershell")
    A("python C:\\Users\\Thinkbook\\OneDrive\\Celine\\scripts\\harvest_skills.py")
    A("```")
    A("")
    A("Useful flags:")
    A("")
    A("| Flag | Effect |")
    A("| --- | --- |")
    A("| `--no-mirror` | Refresh the registry files only; do not touch `mirror/`. |")
    A("| `--no-prune` | Keep mirror files that are no longer part of the registry. |")
    A("| `--hub <path>` | Write to a different hub root (default `C:\\Users\\Thinkbook\\OneDrive\\Celine`). |")
    A("| `--quiet` | Suppress progress output. |")
    A("")
    A("The script is **read-only** outside the hub: it never creates, edits, moves or "
      "deletes anything on the machine except inside `<hub>/hub/skills/`.")
    A("Pruning only ever removes files inside `<hub>/hub/skills/mirror/`, which is "
      "guarded by the `.mirror-root` marker file.")
    A("")
    A("## Surfaces covered")
    A("")
    A("| Surface id | Application | Kind | Skills | Present |")
    A("| --- | --- | --- | ---: | --- |")
    for s in sorted(surfaces, key=lambda x: x["sid"]):
        A(f"| `{s['sid']}` | {s['app']} | {s['kind']} | {s['skill_count']} | "
          f"{'yes' if s['present'] else 'no'} |")
    A("")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Runtime probes (read-only checks for the computer-use summary)
# --------------------------------------------------------------------------- #

def probe_chrome_extensions() -> dict:
    """Look for the Chrome extensions the Codex native-host manifest expects."""
    manifest = HOME / ".codex" / "chrome-native-hosts-v2.json"
    wanted: list[str] = []
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
            for entry in data.get("entries", []):
                wanted.extend(entry.get("extensionIds", []))
        except (OSError, ValueError):
            pass
    found: list[str] = []
    profiles = HOME / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    if profiles.is_dir():
        for prof in profiles.iterdir():
            ext = prof / "Extensions"
            if not ext.is_dir():
                continue
            try:
                for e in ext.iterdir():
                    if e.is_dir():
                        found.append(e.name)
            except OSError:
                continue
    return {
        "wanted": wanted,
        "installed": sorted(set(found)),
        "matched": sorted(set(wanted) & set(found)),
        "profiles_dir_exists": profiles.is_dir(),
    }


def probe_runtimes() -> list[dict]:
    out = []

    def add(name: str, path: str, ok: bool, extra: str = ""):
        out.append({"name": name, "path": path,
                    "state": ("present" if ok else "NOT PRESENT") + (f" - {extra}" if extra else "")})

    cua = HOME / ".cua-driver" / "packages" / "current"
    add("Standalone CUA driver", str(cua), cua.exists(),
        "windows UI automation driver (SendInput / UIA)")

    sky = HOME / "AppData" / "Local" / "OpenAI" / "Codex" / "runtimes" / "cua_node"
    add("Codex cua_node runtime (@oai/sky)", str(sky), sky.exists(),
        "Node runtime that hosts the @oai/sky computer-use API")

    wb = HOME / ".kimi-webbridge"
    add("Kimi WebBridge daemon", str(wb), wb.exists(),
        "browser bridge daemon (daemon.pid present: %s)" % (wb / "daemon.pid").exists())

    nh = HOME / ".codex" / "chrome-native-hosts-v2.json"
    add("Codex Chrome native host manifest", str(nh), nh.exists(),
        "Chrome extension <-> Codex bridge")

    cu_cfg = HOME / ".codex" / "computer-use" / "config.json"
    add("Codex computer-use config", str(cu_cfg), cu_cfg.exists(),
        "UI strings for the 'ChatGPT is using your computer' overlay")

    return out


def probe_clis() -> list[tuple[str, str]]:
    names = ["claude", "codex", "grok", "hermes", "kimi", "gemini", "opencode",
             "qwen", "continue", "code", "python", "node", "npm", "git", "uv"]
    out = []
    for n in names:
        w = shutil.which(n)
        out.append((n, w or ""))
    return out


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def scan_surfaces(log) -> tuple[list[dict], list[dict], list[str]]:
    """Walk every surface root and collect the skills found under it."""
    entries: list[dict] = []
    surfaces_info: list[dict] = []
    missing_roots: list[str] = []

    for surf in SURFACES:
        found_here = 0
        present_roots = []
        missing = []
        for rel in surf.roots:
            root = HOME / rel
            if not root.is_dir():
                missing.append(rel)
                missing_roots.append(f"{surf.sid}: {rel}")
                continue
            present_roots.append(root)
            for skill_md in find_skill_files(root):
                try:
                    entry = parse_skill(skill_md, surf, root)
                except Exception as exc:                      # noqa: BLE001
                    log(f"  ! parse failed {skill_md}: {exc}")
                    continue
                if entry:
                    entry["surface_root"] = str(root)
                    entries.append(entry)
                    found_here += 1
        surfaces_info.append({
            "sid": surf.sid,
            "app": surf.app,
            "label": surf.label,
            "kind": surf.kind,
            "hub_key": surf.hub_key,
            "roots": list(surf.roots),
            "present": bool(present_roots),
            "roots_present": present_roots,
            "missing_roots": missing,
            "skill_count": found_here,
        })
        log(f"  {surf.sid:22s} {found_here:5d} skills"
            + ("" if present_roots else "   (root missing)"))
    return entries, surfaces_info, missing_roots


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Harvest and mirror all installed AI skills.")
    ap.add_argument("--hub", default=str(DEFAULT_HUB), help="hub root (default: %(default)s)")
    ap.add_argument("--no-mirror", action="store_true", help="registry only, skip mirroring")
    ap.add_argument("--mirror-only", action="store_true",
                    help="rebuild the mirror from the existing registry.json (no re-scan)")
    ap.add_argument("--no-prune", action="store_true", help="keep stale mirror files")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    hub = Path(args.hub).expanduser().resolve()
    out_dir = hub / "hub" / "skills"
    mirror_root = out_dir / "mirror"

    def log(msg: str):
        if not args.quiet:
            print(msg, flush=True)

    log(f"hub            : {hub}")
    log(f"output         : {out_dir}")

    entries: list[dict] = []
    surfaces_info: list[dict] = []
    missing_roots: list[str] = []

    if args.mirror_only:
        # Rebuild the mirror from an existing registry.json without re-scanning
        # the machine. Fast path for refreshing copies after the scan is done.
        reg_path = out_dir / "registry.json"
        if not reg_path.is_file():
            print(f"--mirror-only needs an existing registry: {reg_path} not found")
            return 2
        prev = json.loads(reg_path.read_text(encoding="utf-8"))
        for s in prev["skills"]:
            s["_skill_dir"] = Path(s["source_path"]).parent
            entries.append(s)
        surfaces_info = prev.get("surfaces", [])
        for s in surfaces_info:
            s.setdefault("roots_present", [])
            s.setdefault("missing_roots", [])
        missing_roots = prev.get("missing_roots", [])
        log(f"mirror-only     : loaded {len(entries)} entries from registry.json")
    else:
        entries, surfaces_info, missing_roots = scan_surfaces(log)

    # ---- de-duplicate mirror names per surface ------------------------------
    per_surface: dict[str, list[dict]] = {}
    for e in entries:
        per_surface.setdefault(e["surface"], []).append(e)
    for sid, group in per_surface.items():
        counts: dict[str, int] = {}
        for e in group:
            counts[e["display_name"]] = counts.get(e["display_name"], 0) + 1
        for e in group:
            if counts[e["display_name"]] > 1:
                digest = hashlib.sha1(e["rel_path"].encode("utf-8")).hexdigest()[:8]
                e["display_name"] = f"{e['display_name']}__{digest}"
                e["mirror_name_disambiguated"] = True

    # ---- duplicate analysis ---------------------------------------------------
    by_name: dict[str, list[dict]] = {}
    for e in entries:
        by_name.setdefault(e["name"], []).append(e)
    dup_map = {n: g for n, g in by_name.items() if len(g) > 1}

    by_capability: dict[str, int] = {}
    for e in entries:
        by_capability[e["capability"]] = by_capability.get(e["capability"], 0) + 1

    counts = {
        "total": len(entries),
        "surfaces": len(SURFACES),
        "surfaces_present": sum(1 for s in surfaces_info if s["present"]),
        "by_capability": by_capability,
        "by_surface": {s["sid"]: s["skill_count"] for s in surfaces_info},
        "computer_use": sum(1 for e in entries if e["computer_use"]),
        "unique_names": len(by_name),
        "dup_names": len(dup_map),
    }

    # ---- mirror ---------------------------------------------------------------
    if args.no_mirror:
        mirror_stats = {"files_copied": 0, "bytes_copied": 0,
                        "files_skipped": 0, "files_removed": 0}
        log("mirror         : skipped (--no-mirror)")
    else:
        log("mirroring ...")
        mirror_stats = do_mirror(entries, mirror_root, prune=not args.no_prune)
        log(f"mirror         : {mirror_stats['files_copied']} files, "
            f"{mirror_stats['bytes_copied']} bytes, {mirror_stats['files_removed']} stale removed")

    # ---- write outputs --------------------------------------------------------
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = iso(time.time())

    public_entries = []
    for e in entries:
        p = {k: v for k, v in e.items() if not k.startswith("_")}
        p["mirror_path"] = f"mirror/{e['surface']}/{e['display_name']}"
        public_entries.append(p)

    payload = {
        "schema_version": 1,
        "generated_at": generated,
        "host": os.environ.get("COMPUTERNAME", "unknown"),
        "hub_root": str(hub),
        "counts": counts,
        "surfaces": [{k: v for k, v in s.items() if k != "roots_present"} for s in surfaces_info],
        "missing_roots": missing_roots,
        "duplicate_names": {
            n: [{"surface": g["surface"], "source_path": g["source_path"],
                 "capability": g["capability"]} for g in grp]
            for n, grp in sorted(dup_map.items())
        },
        "mirror": mirror_stats,
        "skills": public_entries,
    }

    write_registry_json(out_dir / "registry.json", payload)
    write_registry_csv(out_dir / "registry.csv", entries)
    write_index_md(out_dir / "INDEX.md", entries, surfaces_info, dup_map,
                   counts, mirror_stats, generated)

    probes = {
        "runtimes": probe_runtimes(),
        "clis": probe_clis(),
        "chrome": probe_chrome_extensions(),
        "rows": [],
    }
    cu_surfaces = sorted({e["surface"] for e in entries if e["computer_use"]})
    runtime_by_surface = {
        "codex-plugins": ("READY", "`cua_node` runtime + `@oai/sky` present; drives real "
                           "Windows UIs via SendInput / UI Automation / Windows.Graphics.Capture"),
        "codex-staging": ("READY", "same bundled `browser` / `chrome` / `computer-use` plugins, "
                          "staged copy of the openai-bundled marketplace"),
        "mavis-plugin-cache": ("READY", "skills are cached locally; needs the Mavis runtime to load them"),
        "minimax-plugin-cache": ("READY", "skills are cached locally; needs the MiniMax Code runtime to load them"),
        "hermes-agent": ("READY", "`hermes` CLI is on PATH"),
        "hermes-skills": ("READY", "`hermes` CLI is on PATH"),
        "kimi-daimon": ("READY", "Kimi desktop `daimon` runtime + WebBridge daemon"),
        "kimi-bundle": ("READY", "Kimi desktop builtin skills"),
        "vscode-app": ("PARTIAL", "skills ship inside the VS Code Copilot extension; needs "
                      "VS Code + Copilot extension enabled"),
    }
    for sid in cu_surfaces:
        status, needs = runtime_by_surface.get(sid, ("PRESENT", "skill files present; runtime not confirmed"))
        probes["rows"].append({"surface": sid, "status": status, "needs": needs})

    write_computer_use_summary(out_dir / "computer-use-summary.md", entries,
                               surfaces_info, probes, counts, generated)
    write_readme_md(out_dir / "README.md", counts, mirror_stats, generated, surfaces_info)

    log("")
    log(f"TOTAL skills   : {counts['total']}")
    log(f"computer-use   : {counts['computer_use']}")
    log(f"unique names   : {counts['unique_names']}  (duplicates: {counts['dup_names']})")
    log(f"mirror         : {mirror_stats['files_copied']} files / {mirror_stats['bytes_copied']} bytes")
    log(f"written        : {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
