"""The public env template must never become a live inter-service credential."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ConfigSecretDefaultsTests(unittest.TestCase):
    def _load_in_isolated_config_dir(self, *, example: str | None = None, local: str | None = None) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            shutil.copy2(ROOT / "config.py", target / "config.py")
            if example is not None:
                (target / ".env.example").write_text(example, encoding="utf-8")
            if local is not None:
                (target / ".env").write_text(local, encoding="utf-8")
            env = os.environ.copy()
            env.pop("WEBAPP_SECRET", None)
            env.update({"ENV": "test", "VIDEL_SKIP_REQ": "1", "PYTHONPATH": directory})
            return subprocess.run(
                [sys.executable, "-c", "import config; print(config.WEBAPP_SECRET)"],
                cwd=directory,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )

    def test_public_example_template_is_not_loaded_at_runtime(self):
        result = self._load_in_isolated_config_dir(
            example="WEBAPP_SECRET=generate-" + "x" * 48 + "\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_short_secret_in_private_env_file_fails_closed(self):
        result = self._load_in_isolated_config_dir(local="WEBAPP_SECRET=short-test-secret\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        self.assertIn("WEBAPP_SECRET is weak or a placeholder", result.stderr)


if __name__ == "__main__":
    unittest.main()
