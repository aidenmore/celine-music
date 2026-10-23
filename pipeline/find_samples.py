"""Search archive.org for freely-licensed sample packs usable in LMMS."""
import json
import sys
import urllib.parse
import urllib.request

BASE = "https://archive.org/advancedsearch.php"


def search(query, rows=15):
    params = {
        "q": query,
        "fl[]": ["identifier", "title", "licenseurl", "mediatype"],
        "rows": str(rows),
        "page": "1",
        "output": "json",
    }
    url = BASE + "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.load(r)
    return data.get("response", {}).get("docs", [])


QUERIES = [
    'title:(drum samples) AND mediatype:(audio)',
    'title:(sample pack) AND mediatype:(audio)',
    'title:(vocal samples) AND mediatype:(audio)',
    'title:(909 samples) OR title:(techno samples)',
    'title:(loop samples) AND mediatype:(audio)',
    'title:(synth samples) AND mediatype:(audio)',
    'title:(percussion samples) AND mediatype:(audio)',
]

for q in QUERIES:
    print("=" * 78)
    print("QUERY:", q)
    try:
        for d in search(q):
            lic = d.get("licenseurl", "")
            lic_s = lic.split("/")[-1] if lic else "?"
            print(f"  {d.get('identifier',''):<52} | {lic_s:<22} | {str(d.get('title',''))[:44]}")
    except Exception as e:
        print("  ERR", e)
