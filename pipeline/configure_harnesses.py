#!/usr/bin/env python3
"""Configure every installed AI harness for unattended / agentic operation.

- auto-accept (no interactive permission prompts)
- local Ollama wired in as an OpenAI-compatible backend where supported
- a consistent "Celine" operator identity across surfaces
- canonical copies of every touched config inside the Celine hub

Everything is idempotent: running it twice produces the same result.
Backups are written next to each file as <name>.pre-celine.bak (once).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

HOME = Path(os.environ.get("USERPROFILE", r"C:\Users\Thinkbook"))
HUB = Path(r"C:\Users\Thinkbook\OneDrive\Celine")
CFG = HUB / "config"
OLLAMA_BASE = "http://127.0.0.1:11434/v1"
OLLAMA_MODEL = "qwen2.5:3b"
IDENTITY = "Celine"

results: list[tuple[str, str, str]] = []  # (surface, action, detail)


def note(surface: str, action: str, detail: str = "") -> None:
    results.append((surface, action, detail))
    print(f"[{surface:<14}] {action}{(' :: ' + detail) if detail else ''}", flush=True)


def backup_once(path: Path) -> None:
    if not path.exists():
        return
    bak = path.with_name(path.name + ".pre-celine.bak")
    if not bak.exists():
        try:
            shutil.copy2(path, bak)
        except OSError:
            pass


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_once(path)
    path.write_text(content, encoding="utf-8", newline="\n")


def toml_set(text: str, key: str, value: str, *, section: str | None = None) -> str:
    """Set a top-level (or section-scoped) TOML key, preserving everything else.

    Inside a table the key is written bare (`yolo = true`); the dotted form
    (`[ui].yolo = true`) is not valid TOML.
    """
    lines = text.splitlines()
    pat = re.compile(rf"^{re.escape(key)}\s*=")
    replaced = False
    out = []
    in_section = section is None
    for line in lines:
        stripped = line.strip()
        if section is not None:
            if stripped.startswith("["):
                # entering the target table resets the flag; leaving it clears it
                in_section = stripped == f"[{section}]"
        if (section is None or in_section) and pat.match(line):
            out.append(f"{key} = {value}")
            replaced = True
            continue
        out.append(line)
    if not replaced:
        if section is None:
            # insert before the first table header to keep it top-level
            idx = next((i for i, l in enumerate(out) if l.strip().startswith("[")), len(out))
            out.insert(idx, f"{key} = {value}")
            out.insert(idx + 1, "")
        else:
            # find the target table and append the key at its end
            start = next(
                (i for i, l in enumerate(out) if l.strip() == f"[{section}]"),
                None,
            )
            if start is None:
                out.append(f"[{section}]")
                out.append(f"{key} = {value}")
            else:
                end = next(
                    (i for i in range(start + 1, len(out)) if out[i].strip().startswith("[")),
                    len(out),
                )
                out.insert(end, f"{key} = {value}")
    return "\n".join(out) + "\n"


def toml_dedupe_tables(text: str) -> str:
    """Remove duplicate table headers (a TOML hard error) keeping the last one.

    Only collapses exact duplicate headers such as `[ui]` appearing twice.
    """
    lines = text.splitlines()
    header_idx: dict[str, int] = {}
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("[") and s.endswith("]") and not s.startswith("[["):
            header_idx.setdefault(s, []).append(i)  # type: ignore[union-attr]
    for header, idxs in header_idx.items():
        if len(idxs) < 2:
            continue
        keep = idxs[-1]
        drop = set(idxs[:-1])
        # find the extent of each occurrence
        out_lines = []
        bounds = idxs + [len(lines)]
        for j in range(len(idxs)):
            body = lines[bounds[j] + 1 : bounds[j + 1]]
            if j < len(idxs) - 1:
                out_lines.append(lines[idxs[j]])
                out_lines.extend(body)
            else:
                out_lines.append(lines[keep])
                out_lines.extend(body)
        lines = out_lines
    # collapse duplicated keys inside the same table, keeping the LAST value
    seen_table = None
    seen_keys: dict[str, dict[str, int]] = {}
    final: list[str | None] = []
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            seen_table = s
            seen_keys.setdefault(seen_table, {})
            final.append(line)
            continue
        m = re.match(r"^([A-Za-z0-9_.\-\"]+)\s*=", s)
        if m and seen_table is not None:
            k = m.group(1)
            table_seen = seen_keys.setdefault(seen_table, {})
            if k in table_seen:
                final[table_seen[k]] = None  # drop the earlier duplicate
            table_seen[k] = len(final)
        final.append(line)
    return "\n".join(l for l in final if l is not None) + "\n"


def json_load(path: Path) -> dict:
    try:
        return json.loads(read(path) or "{}")
    except Exception:
        return {}


def json_dump(path: Path, data: dict) -> None:
    write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------
# Codex CLI
# --------------------------------------------------------------------------
def configure_codex() -> None:
    p = HOME / ".codex" / "config.toml"
    t = read(p)
    if not t:
        note("codex-cli", "SKIP", "config.toml not found")
        return
    t = toml_set(t, "approval_policy", '"never"')
    t = toml_set(t, "sandbox_mode", '"danger-full-access"')
    t = toml_set(t, "model_reasoning_effort", '"medium"')
    # Ollama as a local provider
    if "[model_providers.ollama]" not in t:
        t += (
            "\n[model_providers.ollama]\n"
            'name = "Ollama (local)"\n'
            'base_url = "http://127.0.0.1:11434/v1"\n'
            'wire_api = "responses"\n'
            'env_key = "OLLAMA_API_KEY"\n'
        )
    # a stable project entry for the hub
    if "[projects.'c:\\users\\thinkbook\\onedrive\\celine']" not in t.lower():
        t += (
            "\n[projects.'c:\\users\\thinkbook\\onedrive\\celine']\n"
            'trust_level = "trusted"\n'
        )
    write(p, t)
    note("codex-cli", "configured", "approval_policy=never, sandbox=danger-full-access, ollama provider added")
    write(CFG / "codex" / "config.toml", t)


# --------------------------------------------------------------------------
# Grok CLI
# --------------------------------------------------------------------------
def configure_grok() -> None:
    p = HOME / ".grok" / "config.toml"
    t = read(p)
    if not t:
        note("grok-cli", "SKIP", "config.toml not found")
        return
    t = toml_dedupe_tables(t)
    t = toml_set(t, "yolo", "true", section="ui")
    t = toml_set(t, "permission_mode", '"always-approve"', section="ui")
    t = toml_dedupe_tables(t)
    if "[ollama]" not in t:
        t += (
            "\n[ollama]\n"
            'base_url = "http://127.0.0.1:11434/v1"\n'
            f'model = "{OLLAMA_MODEL}"\n'
        )
    write(p, t)
    note("grok-cli", "configured", "yolo=true, permission_mode=always-approve")
    write(CFG / "grok" / "config.toml", t)


# --------------------------------------------------------------------------
# Claude Code
# --------------------------------------------------------------------------
def configure_claude() -> None:
    p = HOME / ".claude" / "settings.json"
    d = json_load(p)
    perms = d.setdefault("permissions", {})
    perms["defaultMode"] = "bypassPermissions"
    allow = perms.setdefault("allow", [])
    for rule in ["Bash(*)", "Read(*)", "Edit(*)", "Write(*)", "WebFetch(*)", "WebSearch(*)"]:
        if rule not in allow:
            allow.append(rule)
    d.setdefault("env", {}).update(
        {
            "OLLAMA_HOST": "127.0.0.1:11434",
            "ANTHROPIC_BASE_URL": OLLAMA_BASE,
            "ANTHROPIC_API_KEY": "ollama",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        }
    )
    d.setdefault("includeCoAuthoredBy", False)
    json_dump(p, d)
    note("claude-code", "configured", "defaultMode=bypassPermissions, ollama env wired")
    write(CFG / "claude" / "settings.json", json.dumps(d, indent=2) + "\n")


# --------------------------------------------------------------------------
# Gemini CLI
# --------------------------------------------------------------------------
def configure_gemini() -> None:
    p = HOME / ".gemini" / "settings.json"
    d = json_load(p)
    d.setdefault("security", {}).setdefault("auth", {}).setdefault("selectedType", "ollama")
    d.setdefault("general", {}).update({"previewFeatures": True})
    d.setdefault("model", {})
    d["model"].setdefault("name", OLLAMA_MODEL)
    d.setdefault("env", {}).update({"OLLAMA_HOST": "127.0.0.1:11434"})
    json_dump(p, d)
    note("gemini-cli", "configured", "model + ollama env")
    write(CFG / "gemini" / "settings.json", json.dumps(d, indent=2) + "\n")


# --------------------------------------------------------------------------
# OpenCode
# --------------------------------------------------------------------------
def configure_opencode() -> None:
    p = HOME / ".config" / "opencode" / "opencode.jsonc"
    base = read(p) or "{}"
    # strip trailing commas / comments for jsonc safety: rebuild as json
    stripped = re.sub(r"//.*", "", base)
    stripped = re.sub(r",\s*([}\]])", r"\1", stripped)
    try:
        d = json.loads(stripped)
    except Exception:
        d = {}
    d.setdefault("$schema", "https://opencode.ai/config.json")
    d.setdefault("model", "ollama/" + OLLAMA_MODEL)
    d.setdefault("provider", {}).setdefault("ollama", {}).update(
        {
            "npm": "@ai-sdk/openai-compatible",
            "name": "Ollama (local)",
            "options": {"baseURL": OLLAMA_BASE},
            "models": {OLLAMA_MODEL: {"name": "Qwen2.5 3B (local)"}},
        }
    )
    d.setdefault("permission", {}).update(
        {
            "edit": "allow",
            "bash": "allow",
            "webfetch": "allow",
        }
    )
    d.setdefault("autoupdate", True)
    out = json.dumps(d, indent=2, ensure_ascii=False) + "\n"
    write(p, out)
    note("opencode", "configured", "ollama provider + full permissions")
    write(CFG / "opencode" / "opencode.json", out)


# --------------------------------------------------------------------------
# Hermes
# --------------------------------------------------------------------------
def configure_hermes() -> None:
    root = HOME / "AppData" / "Local" / "hermes"
    cfg = root / "config.yaml"
    t = read(cfg)
    if t:
        t = re.sub(r'(?m)^(\s*default:\s*)"[^"]*"', r'\1"ollama/' + OLLAMA_MODEL + '"', t, count=1)
        t = re.sub(r'(?m)^(\s*provider:\s*)"[^"]*"', r'\1"custom"', t, count=1)
        if "base_url" in t:
            t = re.sub(r'(?m)^(\s*base_url:\s*)"[^"]*"', r'\1"' + OLLAMA_BASE + '"', t, count=1)
        else:
            t = t.rstrip() + f'\n  base_url: "{OLLAMA_BASE}"\n'
        write(cfg, t)
        write(CFG / "hermes" / "config.yaml", t)
        note("hermes", "configured", "provider=custom -> ollama, model=ollama/" + OLLAMA_MODEL)
    soul = root / "SOUL.md"
    if soul.exists():
        s = read(soul)
        if IDENTITY not in s.split("\n")[0]:
            s = (
                f"You are {IDENTITY}, the operator of this workstation's AI hub. "
                "Everything on this machine runs under the Celine hub: sessions, config, "
                "reports and backups live in C:\\Users\\Thinkbook\\OneDrive\\Celine. "
                "Be direct: match the length of your reply to the weight of the ask. "
                "No filler, no restating the request. Plain claims over adjectives; when "
                "unsure, say so plainly. Prefer verified evidence over intent.\n\n" + s
            )
            write(soul, s)
            note("hermes", "identity", "SOUL.md signed as Celine")


# --------------------------------------------------------------------------
# MiniMax Code / Mavis runtime identity
# --------------------------------------------------------------------------
def configure_minimax() -> None:
    for root in (HOME / ".minimax", HOME / ".mavis"):
        cfg = root / "config.yaml"
        if not cfg.exists():
            continue
        t = read(cfg)
        if "celineIdentity" not in t:
            t = t.rstrip() + (
                "\n\n# --- Celine hub identity (added by configure_harnesses.py) ---\n"
                "celineIdentity:\n"
                f"  name: {IDENTITY}\n"
                "  role: owner-operator\n"
                '  hubRoot: "C:\\\\Users\\\\Thinkbook\\\\OneDrive\\\\Celine"\n'
                "  signing: true\n"
            )
            write(cfg, t)
            note("minimax", "identity", f"celineIdentity added to {root.name}/config.yaml")
        write(CFG / "minimax" / f"config.{root.name}.yaml", t)


# --------------------------------------------------------------------------
# VS Code
# --------------------------------------------------------------------------
def configure_vscode() -> None:
    p = HOME / "AppData" / "Roaming" / "Code" / "User" / "settings.json"
    d = json_load(p)
    d.setdefault("chat.agent.autoApprove", True)
    d.setdefault("chat.runTasks.enable", True)
    d.setdefault("terminal.integrated.defaultProfile.windows", "PowerShell")
    d.setdefault("codex.chatSidebar", True)
    d.setdefault("github.copilot.chat.agent.enabled", True)
    d.setdefault("files.watcherExclude", {})
    d["files.watcherExclude"].update(
        {
            "**/.git/objects/**": True,
            "**/node_modules/**": True,
            "**/.codex/packages/**": True,
            "**/hub/surfaces/**": True,
        }
    )
    json_dump(p, d)
    note("vscode", "configured", "chat auto-approve + watcher excludes")
    write(CFG / "vscode" / "settings.json", json.dumps(d, indent=2) + "\n")


# --------------------------------------------------------------------------
# Global identity files every harness can pick up
# --------------------------------------------------------------------------
IDENTITY_MD = f"""# {IDENTITY} - workstation identity

You are {IDENTITY}, the primary AI operator for this Windows workstation.

- **Hub root**: `C:\\Users\\Thinkbook\\OneDrive\\Celine`
- Every AI surface on this PC keeps its sessions, config, logs, reports and
  backups under that hub. Treat the hub as the source of truth.
- **Operating mode**: unattended / agentic. Do not block on questions when a
  safe, reversible default exists. Make the call, log it, keep going.
- **Local inference**: Ollama serves at `http://127.0.0.1:11434/v1`
  (model `{OLLAMA_MODEL}`).
- **Reporting**: work is tracked in `reports/` and `tracker/`; status is
  published as HTML dashboards.
- **Verification beats intent**: check the actual state on disk before
  claiming something is done.
"""


def write_identity_files() -> None:
    for target in (
        HOME / "AGENTS.md",
        HOME / ".codex" / "AGENTS.md",
        HOME / ".minimax" / "AGENTS.md",
        HOME / ".mavis" / "AGENTS.md",
        HOME / ".grok" / "AGENTS.md",
        HOME / ".claude" / "CLAUDE.md",
        HOME / ".gemini" / "GEMINI.md",
        CFG / "IDENTITY.md",
    ):
        write(target, IDENTITY_MD)
    note("identity", "signed", f"AGENTS.md/CLAUDE.md/GEMINI.md written as {IDENTITY}")


def main() -> int:
    print(f"=== configuring harnesses as {IDENTITY} at {datetime.now().isoformat(timespec='seconds')} ===")
    CFG.mkdir(parents=True, exist_ok=True)
    for fn in (
        configure_codex,
        configure_grok,
        configure_claude,
        configure_gemini,
        configure_opencode,
        configure_hermes,
        configure_minimax,
        configure_vscode,
    ):
        try:
            fn()
        except Exception as exc:
            note(fn.__name__.replace("configure_", ""), "ERROR", str(exc))
    write_identity_files()

    manifest = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "identity": IDENTITY,
        "ollama": {"base_url": OLLAMA_BASE, "model": OLLAMA_MODEL},
        "actions": [{"surface": s, "action": a, "detail": d} for s, a, d in results],
    }
    out = HUB / "hub" / "manifest" / "harness-config.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nmanifest -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
