#!/usr/bin/env python3
"""Scan Codex CLI/Desktop rollout sessions for a keyword and report matching threads.

Sessions are stored either as plain .jsonl or zstd-compressed .jsonl.zst under
~/.codex/sessions. This reads both without mutating anything.

Usage:
    python scan_codex_threads.py elois
    python scan_codex_threads.py elois --context 400 --max-hits 60
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import zstandard as zstd
except ImportError:  # pragma: no cover
    zstd = None


def iter_text_lines(path: Path):
    if path.suffix == ".zst":
        if zstd is None:
            return
        dctx = zstd.ZstdDecompressor()
        with path.open("rb") as fh:
            with dctx.stream_reader(fh) as reader:
                data = reader.read().decode("utf-8", errors="replace")
        for line in data.splitlines():
            yield line
    else:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                yield line


def extract_text(line: str) -> str:
    """Best-effort pull of human-readable payload out of a rollout JSONL record."""
    try:
        obj = json.loads(line)
    except Exception:
        return line[:2000]
    if not isinstance(obj, dict):
        return str(obj)[:2000]

    chunks: list[str] = []
    payload = obj.get("payload")
    if isinstance(payload, dict):
        for key in ("text", "message", "content", "title", "summary", "value"):
            val = payload.get(key)
            if isinstance(val, str):
                chunks.append(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        chunks.append(item)
                    elif isinstance(item, dict):
                        for k2 in ("text", "content"):
                            if isinstance(item.get(k2), str):
                                chunks.append(item[k2])
    for key in ("type", "role", "cwd", "id", "thread_name"):
        val = obj.get(key)
        if isinstance(val, str):
            chunks.append(f"[{key}={val}]")
    return "\n".join(c for c in chunks if c)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("keyword")
    ap.add_argument("--root", default=str(Path.home() / ".codex" / "sessions"))
    ap.add_argument("--context", type=int, default=300)
    ap.add_argument("--max-hits", type=int, default=60)
    args = ap.parse_args()

    kw = args.keyword.lower()
    root = Path(args.root)
    if not root.exists():
        print(f"NO_SESSION_ROOT {root}")
        return 2

    files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in (".jsonl", ".zst"))
    print(f"scanning {len(files)} session files under {root}")

    hit_files = 0
    total_hits = 0
    for f in files:
        hits: list[tuple[str, str]] = []
        try:
            for line in iter_text_lines(f):
                low = line.lower()
                if kw in low:
                    text = extract_text(line)
                    hits.append((line[:200], text))
        except Exception as exc:  # corrupt file should not abort the sweep
            print(f"  !! {f.name}: {exc}")
            continue
        if not hits:
            continue
        hit_files += 1
        total_hits += len(hits)
        print("=" * 100)
        print(f"FILE: {f}  ({len(hits)} hit lines)")
        for raw, text in hits[: args.max_hits]:
            snippet = text.replace("\n", " ")
            idx = snippet.lower().find(kw)
            start = max(0, idx - args.context)
            end = min(len(snippet), idx + len(kw) + args.context)
            print(f"  ...{snippet[start:end]}...")
        if len(hits) > args.max_hits:
            print(f"  ... {len(hits) - args.max_hits} more hit lines suppressed")

    print("=" * 100)
    print(f"SUMMARY keyword={kw!r} files_with_hits={hit_files} total_hit_lines={total_hits}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
