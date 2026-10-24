"""Dependency-free path preflight for the Celine production scripts."""
from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
PIPELINE = REPO / "pipeline"
ROOT_CONSUMERS = ("render_all.py", "build_songs.py", "synth.py",
                  "download_samples.py", "lib_samples.py")


def call_python(expr: str, *, root: str | None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if root is None:
        env.pop("CELINE_ROOT", None)
    else:
        env["CELINE_ROOT"] = root
    env["PYTHONPATH"] = str(PIPELINE)
    with tempfile.TemporaryDirectory() as elsewhere:
        return subprocess.run([sys.executable, "-c", expr], cwd=elsewhere,
                              env=env, text=True, capture_output=True, check=False)


class ProductionPathTests(unittest.TestCase):
    def test_default_is_checkout_even_when_invoked_elsewhere(self):
        p = call_python("from config_paths import ROOT; print(ROOT)", root=None)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(Path(p.stdout.strip()), REPO)

    def test_environment_override(self):
        with tempfile.TemporaryDirectory() as chosen:
            p = call_python("from config_paths import ROOT; print(ROOT)", root=chosen)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(Path(p.stdout.strip()), Path(chosen).resolve())

    def test_missing_manifest_explains_regeneration(self):
        with tempfile.TemporaryDirectory() as chosen:
            p = call_python("from config_paths import sample_manifest; sample_manifest('custom')", root=chosen)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("python pipeline/render_custom.py", p.stderr)
            self.assertIn("Missing custom sample manifest", p.stderr)

    def test_production_scripts_use_shared_root(self):
        for filename in ROOT_CONSUMERS:
            with self.subTest(filename=filename):
                source = (PIPELINE / filename).read_text(encoding="utf-8")
                tree = ast.parse(source)
                self.assertTrue(any(isinstance(node, ast.ImportFrom)
                                    and node.module == "config_paths"
                                    for node in tree.body))
                self.assertNotIn("Thinkbook", source)

    def test_tool_paths_can_be_overridden(self):
        expr = "import lmms_render, presets; print(lmms_render.LMMS); print(presets.PRESETS_ROOT)"
        env = os.environ.copy()
        env["CELINE_LMMS_BIN"] = "/test/lmms"
        env["CELINE_LMMS_PRESETS"] = "/test/presets"
        env["PYTHONPATH"] = str(PIPELINE)
        p = subprocess.run([sys.executable, "-c", expr], env=env,
                           text=True, capture_output=True, check=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.splitlines(), ["/test/lmms", "/test/presets"])

    def test_entrypoints_exist(self):
        for name in ("render_custom.py", "render_all.py", "blender_designs.py"):
            self.assertTrue((PIPELINE / name).is_file())


if __name__ == "__main__":
    unittest.main()
