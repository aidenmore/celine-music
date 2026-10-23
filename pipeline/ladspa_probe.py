"""
ladspa_probe.py - Read LADSPA plugin descriptors (port names, types, ranges,
defaults) from the installed plugin DLLs.

Locates the exported `lsps_` descriptor via the PE export table, then walks the
descriptor array using the loaded module base address.

Result is cached to ladspa_ports.json for use by the song builder.
"""
from __future__ import annotations

import ctypes
import json
import os
import struct
import sys

LADSPA_DIR = r"C:\Program Files\LMMS\plugins\ladspa"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ladspa_ports.json")

PORT_INPUT, PORT_OUTPUT, PORT_CONTROL, PORT_AUDIO = 0x1, 0x2, 0x4, 0x8


# ---------------------------------------------------------------- PE parsing
def pe_exports(path: str) -> dict[str, int]:
    """Return {export_name: rva} for a PE file."""
    with open(path, "rb") as fh:
        data = fh.read()
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        raise ValueError("not a PE file")
    coff = e_lfanew + 4
    num_sections = struct.unpack_from("<H", data, coff + 2)[0]
    opt_size = struct.unpack_from("<H", data, coff + 16)[0]
    opt = coff + 20
    magic = struct.unpack_from("<H", data, opt)[0]
    pe32plus = (magic == 0x20B)
    dd = opt + (112 if pe32plus else 96)
    exp_rva, exp_size = struct.unpack_from("<II", data, dd)
    if not exp_rva:
        return {}
    sect_off = opt + opt_size
    sections = []
    for i in range(num_sections):
        s = sect_off + i * 40
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, s + 8)
        sections.append((vaddr, vsize, rawptr, rawsize))

    def rva2off(rva: int) -> int:
        for vaddr, vsize, rawptr, rawsize in sections:
            if vaddr <= rva < vaddr + max(vsize, rawsize):
                return rawptr + (rva - vaddr)
        raise ValueError(f"rva {rva:#x} not mapped")

    eo = rva2off(exp_rva)
    (_, _, _, _, name_rva, ordinal_base, num_funcs, num_names,
     addr_funcs, addr_names, addr_ords) = struct.unpack_from("<IIHHIIIIIII", data, eo)
    names_off = rva2off(addr_names)
    ords_off = rva2off(addr_ords)
    funcs_off = rva2off(addr_funcs)
    out = {}
    for i in range(num_names):
        nrva = struct.unpack_from("<I", data, names_off + i * 4)[0]
        noff = rva2off(nrva)
        end = data.index(b"\0", noff)
        name = data[noff:end].decode("ascii", "replace")
        ordv = struct.unpack_from("<H", data, ords_off + i * 2)[0]
        frva = struct.unpack_from("<I", data, funcs_off + ordv * 4)[0]
        out[name] = frva
    return out


# --------------------------------------------------------------- descriptors
class RangeHint(ctypes.Structure):
    _fields_ = [("LowerBound", ctypes.c_int), ("UpperBound", ctypes.c_int)]


class PortDescriptor(ctypes.Structure):
    _fields_ = [("Name", ctypes.c_char_p), ("Label", ctypes.c_char_p),
                ("RangeHint", RangeHint), ("Type", ctypes.c_int),
                ("DefaultValue", ctypes.c_char_p)]


class Descriptor(ctypes.Structure):
    _fields_ = [("UniqueID", ctypes.c_ulong), ("Label", ctypes.c_char_p),
                ("Properties", ctypes.c_int), ("Name", ctypes.c_char_p),
                ("Maker", ctypes.c_char_p), ("Copyright", ctypes.c_char_p),
                ("PortCount", ctypes.c_ulong),
                ("PortDescriptors", ctypes.POINTER(PortDescriptor)),
                ("ImplementationData", ctypes.c_void_p),
                ("Instantiation", ctypes.c_void_p), ("Deinstantiation", ctypes.c_void_p),
                ("Cookie", ctypes.c_void_p), ("Activate", ctypes.c_void_p),
                ("Run", ctypes.c_void_p), ("SetRunInputGain", ctypes.c_void_p),
                ("SetRunOutputGain", ctypes.c_void_p), ("RunAdding", ctypes.c_void_p),
                ("SetRunInputGainAdding", ctypes.c_void_p),
                ("SetRunOutputGainAdding", ctypes.c_void_p)]


def cstr(v):
    """Accept bytes (auto-converted c_char_p field) or a raw pointer."""
    if v is None:
        return None
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    try:
        return ctypes.cast(v, ctypes.c_char_p).value.decode("utf-8", "replace")
    except Exception:
        return None


def probe(path: str, max_plugins: int = 60) -> list[dict]:
    exports = pe_exports(path)
    dll = ctypes.CDLL(path)
    base = dll._handle
    out = []

    # Modern LADSPA: exported FUNCTION  ladspa_descriptor(unsigned long index)
    fn = None
    if "ladspa_descriptor" in exports:
        fn = dll.ladspa_descriptor
        fn.restype = ctypes.c_void_p
        fn.argtypes = [ctypes.c_ulong]

    # Legacy LADSPA: exported DATA symbol lsps_
    data_addr = None
    if "lsps_" in exports:
        data_addr = base + exports["lsps_"]

    for i in range(max_plugins):
        if fn is not None:
            addr = fn(ctypes.c_ulong(i))
            if not addr:
                break
        elif data_addr is not None:
            addr = data_addr + i * ctypes.sizeof(Descriptor)
        else:
            return [{"error": "no ladspa_descriptor/lsps_ export"}]
        try:
            d = ctypes.cast(addr, ctypes.POINTER(Descriptor)).contents
        except Exception:
            break
        label = cstr(d.Label)
        nm = cstr(d.Name)
        if not label or not nm:
            break
        ports = []
        for p in range(min(d.PortCount, 64)):
            try:
                pd = d.PortDescriptors[p]
            except Exception:
                break
            ports.append({
                "idx": p,
                "name": cstr(pd.Name),
                "label": cstr(pd.Label),
                "type": pd.Type, "lo": pd.RangeHint.LowerBound,
                "hi": pd.RangeHint.UpperBound,
                "default": cstr(pd.DefaultValue),
            })
        out.append({"label": label, "unique_id": d.UniqueID, "ports": ports})
    if not out:
        return [{"error": "descriptor enumeration failed"}]
    return out


def build_catalog() -> dict:
    """Probe every DLL in a child process so a bad plugin cannot kill the run."""
    import subprocess
    cat = {}
    here = os.path.dirname(os.path.abspath(__file__))
    for f in sorted(os.listdir(LADSPA_DIR)):
        if not f.lower().endswith(".dll"):
            continue
        try:
            p = subprocess.run([sys.executable, os.path.join(here, "ladspa_probe.py"),
                                "--one", f], capture_output=True, text=True, timeout=60)
            if p.returncode != 0:
                print(f"  skip {f} (rc={p.returncode})", flush=True)
                continue
            res = json.loads(p.stdout)
            if res and "error" not in res[0]:
                cat[f[:-4]] = res
        except Exception as e:
            print(f"  skip {f} ({e})", flush=True)
    return cat


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--one":
        res = probe(os.path.join(LADSPA_DIR, sys.argv[2]))
        print(json.dumps(res))
        sys.exit(0)

    cat = build_catalog()
    with open(CACHE, "w", encoding="utf-8") as fh:
        json.dump(cat, fh, indent=1)
    total = sum(len(v) for v in cat.values())
    print(f"libraries: {len(cat)}  plugins: {total}")
    want = sys.argv[1:]
    for lib, plugs in cat.items():
        if want and lib not in want and not any(w.lower() in p["label"].lower() for p in plugs for w in want):
            continue
        for pl in plugs:
            ctrls = [x for x in pl["ports"] if x["type"] & PORT_CONTROL]
            print(f"  {lib:<22} {pl['label']:<24} ctrl={len(ctrls)}")
            for c in ctrls:
                print(f"        [{c['idx']:>2}] {c['label']:<24} {c['lo']}..{c['hi']} def={c['default']}")

