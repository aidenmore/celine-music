#!/usr/bin/env python3
"""Search SQLite databases for a keyword across text-bearing tables.

Used to locate chats/threads in the Codex desktop local stores without
requiring the app to be running.

Usage:
    python sqlite_grep.py elois
    python sqlite_grep.py elois --db "C:/path/to/store.sqlite"
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def search_db(db: Path, kw: str, max_rows: int = 40) -> int:
    try:
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"  !! cannot open {db.name}: {exc}")
        return 0

    hits = 0
    try:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for t in tables:
            try:
                cols = [c[1] for c in conn.execute(f'PRAGMA table_info("{t}")')]
            except Exception:
                continue
            text_cols = [c for c in cols if c]
            if not text_cols:
                continue
            where = " OR ".join(f'CAST("{c}" AS TEXT) LIKE ?' for c in text_cols)
            try:
                cur = conn.execute(
                    f'SELECT rowid, * FROM "{t}" WHERE {where} LIMIT ?',
                    [f"%{kw}%"] * len(text_cols) + [max_rows],
                )
            except Exception:
                continue
            names = ["rowid"] + cols
            for row in cur.fetchall():
                hits += 1
                print(f"  [{db.name} :: {t}]")
                for n, v in zip(names, row):
                    sv = str(v)
                    if len(sv) > 400:
                        sv = sv[:400] + "..."
                    print(f"      {n} = {sv}")
                print()
    finally:
        conn.close()
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("keyword")
    ap.add_argument("--db", action="append", default=[])
    ap.add_argument("--dir", action="append", default=[])
    ap.add_argument("--max-rows", type=int, default=40)
    args = ap.parse_args()

    dbs: list[Path] = [Path(p) for p in args.db]
    if args.dir:
        for d in args.dir:
            dbs.extend(sorted(Path(d).glob("*.sqlite")))
            dbs.extend(sorted(Path(d).glob("*.db")))

    if not dbs:
        print("no databases supplied")
        return 2

    total = 0
    for db in dbs:
        if not db.exists():
            print(f"MISSING {db}")
            continue
        n = search_db(db, args.keyword, args.max_rows)
        print(f"--- {db.name}: {n} matching rows")
        total += n
    print(f"TOTAL_MATCHING_ROWS {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
