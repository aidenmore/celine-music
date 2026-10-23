"""mcp_client.py - Minimal MCP streamable-HTTP client for the local email server."""
from __future__ import annotations

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:18789/mcp/email"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

_session = {"id": 0}


def _next_id():
    _session["id"] += 1
    return _session["id"]


def rpc(method, params=None, notify=False):
    body = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        body["params"] = params
    if not notify:
        body["id"] = _next_id()
    data = json.dumps(body).encode()
    req = urllib.request.Request(BASE, data=data, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read().decode("utf-8", "replace")
    if not raw.strip():
        return None
    # streamable HTTP may reply as SSE
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def initialize():
    return rpc("initialize", {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "celine-automation", "version": "1.0.0"},
    })


def tools_list():
    return rpc("tools/list", {})


def call(tool, args=None):
    return rpc("tools/call", {"name": tool, "arguments": args or {}})


def text_of(resp):
    if not resp:
        return ""
    if "result" in resp and "content" in resp["result"]:
        return "\n".join(c.get("text", "") for c in resp["result"]["content"]
                         if c.get("type") == "text")
    return json.dumps(resp, ensure_ascii=False)[:2000]


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "init":
        print(json.dumps(initialize(), ensure_ascii=False)[:1500])
    elif cmd == "list":
        r = tools_list()
        if r and "result" in r:
            for t in r["result"].get("tools", []):
                props = t.get("inputSchema", {}).get("properties", {})
                req = t.get("inputSchema", {}).get("required", [])
                print(f"  {t['name']:<34} args={list(props.keys())} required={req}")
        else:
            print("no tools:", json.dumps(r, ensure_ascii=False)[:1200])
    elif cmd == "call":
        tool = sys.argv[2]
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        print(text_of(call(tool, args)))
    else:
        print("usage: mcp_client.py init|list|call <tool> [argsjson]")
