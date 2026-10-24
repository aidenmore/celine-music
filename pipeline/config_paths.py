"""Paths shared by Celine's command-line production tools."""
from __future__ import annotations

import os
from pathlib import Path


def workspace_root() -> Path:
    """Use CELINE_ROOT when set; otherwise use the repository checkout."""
    configured = os.environ.get("CELINE_ROOT")
    base = Path(configured).expanduser() if configured else Path(__file__).resolve().parent.parent
    return base.resolve()


ROOT = str(workspace_root())


def sample_manifest(kind: str) -> str:
    """Give an actionable error when an untracked asset manifest is missing."""
    if kind not in {"custom", "library"}:
        raise ValueError("sample manifest kind must be custom or library")
    path = Path(ROOT) / "samples" / kind / "manifest.json"
    if not path.is_file():
        command = ("python pipeline/render_custom.py" if kind == "custom"
                   else "python pipeline/download_samples.py; python pipeline/lib_samples.py")
        raise FileNotFoundError(
            f"Missing {kind} sample manifest: {path}. Generate it with: {command}. "
            "The original audio samples are not stored in this Git repository."
        )
    return str(path)
