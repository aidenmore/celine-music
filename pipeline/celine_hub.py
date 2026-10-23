#!/usr/bin/env python3
"""Celine Hub - central session/config manager for every AI surface on this PC.

Goal: every AI surface (Codex, MiniMax Code, Claude Code, Gemini CLI, OpenCode,
Hermes, Kimi Desktop, VS Code, ChatGPT/Codex desktop, Ollama, Blender) keeps its
sessions and configuration for THIS machine inside the Celine folder, while the
apps keep working through their native paths (junctions), so nothing needs a
reboot or a re-install.

Commands
--------
init       Create the hub directory tree.
relocate   Move a surface's session store into the hub and junction the native
            path back to it (copy -> verify -> swap -> rollback on failure).
link       Create/repair a junction from a native path into the hub.
unlink     Remove a hub junction (does not touch the data inside).
status     Report every registered surface: paths, junction health, sizes.
registry   Regenerate manifest/surfaces.json from the live filesystem.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

HUB = Path(r"C:\Users\Thinkbook\OneDrive\Celine")
HUB_DIRS = {
    "hub": [
        "surfaces",
        "skills",
        "mcp",
        "logs",
        "state",
        "manifest",
    ],
    "config": [
        "codex",
        "minimax",
        "hermes",
        "claude",
        "gemini",
        "opencode",
        "kimi",
        "vscode",
        "ollama",
        "blender",
    ],
    "scripts": [],
    "reports": [],
    "research": [],
    "blender": ["assets", "bali-fps", "scripts"],
    "docs": [],
    "backups": [],
    "tracker": [],
}

# surface -> (native session path, label). Paths that get relocated + junctioned.
SURFACES: dict[str, dict] = {
    "codex-cli": {
        "label": "Codex CLI (OpenAI)",
        "native": r"C:\Users\Thinkbook\.codex\sessions",
        "hub": "hub/surfaces/codex-cli/sessions",
        "kind": "sessions",
    },
    "codex-desktop": {
        "label": "Codex Desktop (OpenAI ChatGPT app)",
        "native": r"C:\Users\Thinkbook\AppData\Roaming\Codex\storage",
        "hub": "hub/surfaces/codex-desktop/storage",
        "kind": "sessions",
        "optional": True,
    },
    "minimax-code": {
        "label": "MiniMax Code (MCode)",
        "native": r"C:\Users\Thinkbook\.minimax\v2\sessions",
        "hub": "hub/surfaces/minimax-code/sessions",
        "kind": "sessions",
        "optional": True,
    },
    "grok-cli": {
        "label": "Grok CLI (xAI)",
        "native": r"C:\Users\Thinkbook\.grok\sessions",
        "hub": "hub/surfaces/grok-cli/sessions",
        "kind": "sessions",
    },
    "kimi-desktop": {
        "label": "Kimi Desktop (Moonshot) conversations",
        "native": r"C:\Users\Thinkbook\AppData\Roaming\kimi-desktop\File System",
        "hub": "hub/surfaces/kimi-desktop/FileSystem",
        "kind": "sessions",
    },
    "claude-code": {
        "label": "Claude Code",
        "native": r"C:\Users\Thinkbook\.claude\projects",
        "hub": "hub/surfaces/claude-code/projects",
        "kind": "sessions",
    },
    "opencode": {
        "label": "OpenCode",
        "native": r"C:\Users\Thinkbook\.config\opencode\storage",
        "hub": "hub/surfaces/opencode/storage",
        "kind": "sessions",
        "optional": True,
    },
    "gemini-cli": {
        "label": "Gemini CLI",
        "native": r"C:\Users\Thinkbook\.gemini\tmp",
        "hub": "hub/surfaces/gemini-cli/tmp",
        "kind": "sessions",
        "optional": True,
    },
    "hermes": {
        "label": "Hermes Agent (Nous Research)",
        "native": r"C:\Users\Thinkbook\AppData\Roaming\Hermes\sessions",
        "hub": "hub/surfaces/hermes/sessions",
        "kind": "sessions",
        "optional": True,
    },
    "kimi-desktop": {
        "label": "Kimi Desktop (Moonshot)",
        "native": r"C:\Users\Thinkbook\AppData\Roaming\kimi-desktop\sessions",
        "hub": "hub/surfaces/kimi-desktop/sessions",
        "kind": "sessions",
        "optional": True,
    },
    "vscode": {
        "label": "VS Code (chat + workspace state)",
        "native": r"C:\Users\Thinkbook\AppData\Roaming\Code\User\workspaceStorage",
        "hub": "hub/surfaces/vscode/workspaceStorage",
        "kind": "sessions",
        "optional": True,
    },
}


def log(msg: str) -> None:
    print(f"[celine-hub] {msg}", flush=True)


def is_junction(path: Path) -> bool:
    """True when `path` is a reparse point (junction/symlink).

    Uses the Windows FILE_ATTRIBUTE_REPARSE_POINT attribute via os.lstat, which
    is reliable for junctions. `cmd dir /AL` output parsing is avoided because
    its formatting is locale-dependent and easy to mis-read.
    """
    try:
        st = os.lstat(path)
    except (OSError, ValueError):
        return False
    attrs = getattr(st, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if attrs & reparse:
        return True
    # fallback: symlink check
    try:
        return path.is_symlink()
    except OSError:
        return False


def junction_target(path: Path) -> str | None:
    """Resolve where a junction points (Windows-only, best effort)."""
    try:
        out = subprocess.run(
            ["cmd", "/c", "fsutil", "reparsepoint", "query", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout
    except Exception:
        return None
    for line in out.splitlines():
        if "Print Name:" in line:
            return line.split("Print Name:", 1)[1].strip()
    return None


def dir_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for p in path.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
        except OSError:
            continue
    return total


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def cmd_init(_args) -> int:
    for top, subs in HUB_DIRS.items():
        base = HUB / top
        base.mkdir(parents=True, exist_ok=True)
        for sub in subs:
            (base / sub).mkdir(parents=True, exist_ok=True)
    log(f"hub tree ready at {HUB}")
    return 0


def cmd_relocate(args) -> int:
    targets = args.surface or list(SURFACES)
    for key in targets:
        spec = SURFACES.get(key)
        if not spec:
            log(f"unknown surface {key!r}")
            continue
        native = Path(spec["native"])
        dest = HUB / spec["hub"]

        if not native.exists():
            log(f"{key}: native path absent ({native}) - skipping")
            continue

        if is_junction(native):
            log(f"{key}: already a junction - OK")
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        backup = Path(str(native) + ".celine-backup")

        # 1. copy
        log(f"{key}: copying {native} -> {dest}")
        if dest.exists():
            log(f"{key}: destination already has data, merging")
            shutil.copytree(native, dest, dirs_exist_ok=True)
        else:
            shutil.copytree(native, dest)

        # 2. verify counts/bytes
        src_n = sum(1 for _ in native.rglob("*") if _.is_file())
        dst_n = sum(1 for _ in dest.rglob("*") if _.is_file())
        if src_n != dst_n:
            log(f"{key}: COPY MISMATCH src={src_n} dst={dst_n} - leaving native untouched")
            continue

        # 3. swap native -> backup (may fail if the running app holds handles)
        try:
            log(f"{key}: renaming native -> {backup.name}")
            native.rename(backup)
        except OSError as exc:
            log(f"{key}: RENAME REFUSED (locked by running app): {exc}")
            log(f"{key}: leaving native in place; hub copy retained at {dest}")
            continue

        # 4. junction native -> dest
        rc = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(native), str(dest)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if rc.returncode != 0 or not is_junction(native):
            log(f"{key}: MKLINK FAILED rc={rc.returncode} {rc.stdout}{rc.stderr}")
            log(f"{key}: rolling back")
            try:
                if native.exists():
                    native.rmdir()
            except OSError:
                pass
            if backup.exists():
                backup.rename(native)
            continue

        log(f"{key}: linked {native} -> {dest} ({src_n} files)")

        # 5. drop the backup once the junction reads back correctly
        probe = native / next(iter([p.name for p in dest.iterdir()]), "") if any(dest.iterdir()) else native
        ok = probe.exists()
        if ok and backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
            log(f"{key}: verified, removed backup")
        else:
            log(f"{key}: verification probe inconclusive, keeping backup at {backup}")
    return 0


def cmd_link(args) -> int:
    native = Path(args.native)
    dest = HUB / args.hub
    if not native.exists():
        log(f"native path missing: {native}")
        return 1
    if is_junction(native):
        log(f"already junctioned: {native}")
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copytree(native, dest)
    if native.rename(str(native) + ".celine-backup"):
        pass
    rc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(native), str(dest)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    log(f"mklink rc={rc.returncode} {rc.stdout.strip()} {rc.stderr.strip()}")
    return rc.returncode


def cmd_unlink(args) -> int:
    native = Path(args.native)
    if not is_junction(native):
        log(f"not a junction: {native}")
        return 1
    target = subprocess.run(
        ["cmd", "/c", "dir", "/AL", str(native)], capture_output=True, text=True
    ).stdout
    rc = subprocess.run(["cmd", "/c", "rmdir", str(native)], capture_output=True, text=True)
    log(f"rmdir rc={rc.returncode} {rc.stdout.strip()} {rc.stderr.strip()}")
    return rc.returncode


def cmd_status(_args) -> int:
    rows = []
    for key, spec in SURFACES.items():
        native = Path(spec["native"])
        dest = HUB / spec["hub"]
        state = "missing"
        if is_junction(native):
            state = "junction"
        elif native.exists():
            state = "native"
        rows.append(
            {
                "surface": key,
                "label": spec["label"],
                "native": spec["native"],
                "native_exists": native.exists(),
                "hub_path": spec["hub"],
                "hub_exists": dest.exists(),
                "state": state,
                "native_size": human(dir_size(native)),
                "hub_size": human(dir_size(dest)),
            }
        )
        print(
            f"{key:<16} {state:<9} native={human(dir_size(native)):>9}  hub={human(dir_size(dest)):>9}  {spec['native']}"
        )
    out = HUB / "hub" / "manifest" / "surfaces-status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    log(f"status written to {out}")
    return 0


def cmd_registry(_args) -> int:
    rows = []
    for key, spec in SURFACES.items():
        native = Path(spec["native"])
        dest = HUB / spec["hub"]
        rows.append(
            {
                "key": key,
                "label": spec["label"],
                "kind": spec["kind"],
                "native_path": spec["native"],
                "hub_path": spec["hub"],
                "hub_abs": str(dest),
                "state": "junction" if is_junction(native) else ("native" if native.exists() else "missing"),
                "size_bytes": dir_size(dest) if dest.exists() else 0,
            }
        )
    payload = {
        "hub_root": str(HUB),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "surfaces": rows,
    }
    out = HUB / "hub" / "manifest" / "surfaces.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log(f"registry written to {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(func=cmd_init)
    p = sub.add_parser("relocate")
    p.add_argument("--surface", action="append", help="surface key (repeatable)")
    p.set_defaults(func=cmd_relocate)
    p = sub.add_parser("link")
    p.add_argument("--native", required=True)
    p.add_argument("--hub", required=True)
    p.set_defaults(func=cmd_link)
    p = sub.add_parser("unlink")
    p.add_argument("--native", required=True)
    p.set_defaults(func=cmd_unlink)
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("registry").set_defaults(func=cmd_registry)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
