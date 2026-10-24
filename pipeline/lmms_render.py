"""lmms_render.py - headless LMMS render helpers."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

LMMS = os.environ.get("CELINE_LMMS_BIN") or shutil.which("lmms") or r"C:\Program Files\LMMS\lmms.exe"
def _find_ffmpeg() -> str:
    """Locate ffmpeg: PATH first, then the winget package folder."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    import glob
    local = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
    hits = sorted(glob.glob(os.path.join(local, "Gyan.FFmpeg*", "ffmpeg-*", "bin", "ffmpeg.exe")))
    if hits:
        return hits[-1]
    for base in (r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                 r"C:\ffmpeg\bin\ffmpeg.exe"):
        if os.path.exists(base):
            return base
    return "ffmpeg"


FFMPEG = os.environ.get("CELINE_FFMPEG_BIN") or _find_ffmpeg()


def render_project(project_path: str, out_path: str, fmt: str = "wav",
                   samplerate: int = 44100, timeout: int = 1800) -> tuple[bool, str]:
    """Render an .mmpp headlessly via LMMS. Returns (ok, log)."""
    cmd = [LMMS, "render", project_path, "-f", fmt, "-s", str(samplerate), "-o", out_path]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    log = (p.stdout or "") + (p.stderr or "")
    log = re.sub(r"\r", "\n", log)
    ok = os.path.exists(out_path) and os.path.getsize(out_path) > 1000
    return ok, log


def render_song(song, out_wav: str, log_path: str | None = None) -> bool:
    """Write the song to a temp .mmpp and render it."""
    from mmpp import write_song
    tmp = os.path.splitext(out_wav)[0] + ".mmpp"
    write_song(song, tmp)
    ok, log = render_project(tmp, out_wav)
    if log_path:
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write(f"# cmd: lmms render {tmp}\n# ok={ok}\n{log}")
    return ok


def to_mp3(src_wav: str, dst_mp3: str, bitrate: str = "320") -> bool:
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", src_wav,
           "-codec:a", "libmp3lame", "-b:a", f"{bitrate}k", "-ar", "44100", dst_mp3]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode == 0 and os.path.exists(dst_mp3)


if __name__ == "__main__":
    print("LMMS:", LMMS, os.path.exists(LMMS))
    print("FFMPEG:", FFMPEG, os.path.exists(FFMPEG))
