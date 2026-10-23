#!/usr/bin/env python3
"""Fast binary-safe search for a keyword across large app stores.

PowerShell Select-String is far too slow for multi-hundred-MB browser/Electron
stores, so this streams files in chunks with an overlap window.

Usage:
    python find_text.py elois --root "C:/path" [--max-file-mb 400] [--context 160]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SKIP_DIR_NAMES = {
    "Cache", "Code Cache", "GPUCache", "DawnGraphiteCache", "DawnWebGPUCache",
    "node_modules", ".git", "Service Worker", "blob_storage", "Crashpad",
}
SKIP_EXT = {".exe", ".dll", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff",
            ".woff2", ".ttf", ".otf", ".mp4", ".webm", ".mp3", ".zip", ".7z", ".msi", ".pyc"}


def search_file(path: Path, needle: bytes, ctx: int, max_bytes: int) -> int:
    hits = 0
    overlap = len(needle) + ctx
    try:
        size = path.stat().st_size
        if size == 0:
            return 0
        with path.open("rb") as fh:
            prev = b""
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                buf = prev + chunk
                low = buf.lower()
                start = 0
                while True:
                    idx = low.find(needle, start)
                    if idx < 0:
                        break
                    hits += 1
                    if hits <= 5:
                        s = max(0, idx - ctx)
                        e = min(len(buf), idx + len(needle) + ctx)
                        snippet = buf[s:e]
                        text = snippet.decode("utf-8", errors="replace")
                        text = " ".join(text.split())
                        print(f"    {path}\n      ...{text}...")
                    start = idx + len(needle)
                    if start > len(buf):
                        break
                prev = buf[-overlap:] if len(buf) > overlap else buf
    except (OSError, PermissionError):
        return 0
    return hits


def main() -> int:
    # Windows consoles default to cp1252; binary snippets contain arbitrary bytes
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("keyword")
    ap.add_argument("--root", action="append", required=True)
    ap.add_argument("--max-file-mb", type=int, default=400)
    ap.add_argument("--context", type=int, default=160)
    args = ap.parse_args()

    needle = args.keyword.lower().encode("utf-8")
    total_files = 0
    total_hits = 0
    for root in args.root:
        rp = Path(root)
        if not rp.exists():
            print(f"SKIP missing {rp}")
            continue
        print(f"== scanning {rp}")
        for dirpath, dirnames, filenames in os.walk(rp):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
            for fn in filenames:
                p = Path(dirpath) / fn
                if p.suffix.lower() in SKIP_EXT:
                    continue
                try:
                    if p.stat().st_size > args.max_file_mb * 1024 * 1024:
                        continue
                except OSError:
                    continue
                total_files += 1
                h = search_file(p, needle, args.context, args.max_file_mb)
                if h:
                    total_hits += h
    print("=" * 80)
    print(f"SCANNED_FILES {total_files}  HITS {total_hits}  keyword={args.keyword!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
