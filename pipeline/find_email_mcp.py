"""find_email_mcp.py - locate the local email MCP endpoint."""
import json
import urllib.request
import urllib.error

PAYLOAD = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list",
                      "params": {}}).encode()
HEADERS = {"Content-Type": "application/json",
           "Accept": "application/json, text/event-stream"}

ports = set()
try:
    import subprocess
    out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True,
                         text=True).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) > 3 and parts[0] == "TCP" and "LISTENING" in line:
            local = parts[1]
            host, _, p = local.rpartition(":")
            if host.startswith("127.") or host.startswith("0.0.0.0") or host in ("[::1]", "::"):
                ports.add(int(p))
except Exception as e:
    print("netstat failed:", e)

print(f"probing {len(ports)} listening ports for /mcp/email ...")
for port in sorted(ports):
    for path in ("/mcp/email", "/email/mcp", "/mcp"):
        url = f"http://127.0.0.1:{port}{path}"
        try:
            req = urllib.request.Request(url, data=PAYLOAD, headers=HEADERS,
                                         method="POST")
            with urllib.request.urlopen(req, timeout=4) as r:
                body = r.read().decode("utf-8", "replace")
                if "tool" in body.lower() or "jsonrpc" in body.lower():
                    print(f"  HIT {url} -> {body[:600]}")
                    raise SystemExit(0)
        except urllib.error.HTTPError as e:
            if e.code not in (404, 403, 400):
                print(f"  {url} -> HTTP {e.code}")
        except SystemExit:
            raise
        except Exception:
            pass
print("no /mcp/email endpoint found on local ports")
