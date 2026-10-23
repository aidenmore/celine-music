"""One-shot patch: resilient voice builder + wider pools."""
import re

# --- 1. pool ranges -------------------------------------------------------
P = r"C:\Users\Thinkbook\OneDrive\Celine\scripts\render_custom.py"
t = open(P, encoding="utf-8").read()
RANGES = {
    "fm_pluck": (24, 76), "supersaw": (41, 85), "trance_lead": (55, 85),
    "reese": (31, 62), "sub808": (24, 60), "hoover": (29, 62),
    "pluck": (41, 85), "vocal_ah": (41, 80), "vocal_eh": (41, 80),
    "vocal_oo": (41, 80), "pad": (41, 85),
}
for name, (lo, hi) in RANGES.items():
    m = re.search(rf'"{name}": \{{', t)
    if not m:
        print("MISSING pool", name)
        continue
    seg_end = t.find('"render":', m.end())
    seg = t[m.end():seg_end]
    seg = re.sub(r'"notes": [^\n]*\n', f'"notes": list(range({lo}, {hi})),\n', seg)
    t = t[:m.end()] + seg + t[seg_end:]
open(P, "w", encoding="utf-8").write(t)
print("pools widened")

# --- 2. resilient Voice.tracks() -----------------------------------------
B = r"C:\Users\Thinkbook\OneDrive\Celine\scripts\build_songs.py"
b = open(B, encoding="utf-8").read()
old = '''    def tracks(self):
        out = []
        for m, evs in sorted(self.notes.items()):
            path = C(f"{self.basename}_{m}")
            notes = [Note(lmms_key(m), t, ln) for (t, ln) in evs]
            out.append(track_sample(path, f"{self.name} {m}", [pat(notes, 0, 1)],
                                    vol=self.vol, pan=self.pan, fx=self.fx,
                                    amp=self.amp))
        return out'''
new = '''    def tracks(self):
        out = []
        for m, evs in sorted(self.notes.items()):
            key = f"{self.basename}_{m}"
            if key not in CUSTOM:
                print(f"    [skip] missing sample {key} for {self.name}", flush=True)
                continue
            path = CUSTOM[key]
            notes = [Note(lmms_key(m), t, ln) for (t, ln) in evs]
            out.append(track_sample(path, f"{self.name} {m}", [pat(notes, 0, 1)],
                                    vol=self.vol, pan=self.pan, fx=self.fx,
                                    amp=self.amp))
        return out'''
if old in b:
    b = b.replace(old, new)
    open(B, "w", encoding="utf-8").write(b)
    print("Voice.tracks() made resilient")
else:
    print("WARN: Voice.tracks() pattern not found")
