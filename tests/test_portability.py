"""Exercise installation portability without network access or project writes."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]


class PortabilityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="frontend-skill-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / "skill installed with spaces"
        for relative in ("scripts/select_references.py", "references/library/catalog.json", "references/library/PROMPTS.md"):
            target = self.skill / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SOURCE / relative, target)
        self.env = os.environ.copy()
        self.env.pop("FRONTEND_DESIGN_LIBRARY", None)

    def run_selector(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(self.skill / "scripts/select_references.py"), *args],
            cwd=self.root, env=self.env if env is None else env,
            capture_output=True, text=True, encoding="utf-8",
        )

    def make_library(self, name, marker):
        library = self.root / name
        shutil.copytree(self.skill / "references/library", library)
        catalog_path = library / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog["updatedAt"] = marker
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        prompts_path = library / "PROMPTS.md"
        prompts = prompts_path.read_text(encoding="utf-8")
        prompts_path.write_text(prompts.replace("```text\n", "```text\n" + marker + "\n"), encoding="utf-8")
        return library

    def test_four_types_work_after_relocation(self):
        for page in ("dashboard", "report", "product", "personal"):
            with self.subTest(page=page):
                result = self.run_selector("--type", page)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(data["pageType"]["id"], page)
                self.assertGreaterEqual(data["candidateCount"], 2)
                self.assertGreater(len(data["promptTemplate"]), 100)
                self.assertEqual(Path(data["libraryPath"]), (self.skill / "references/library").resolve())
                self.assertNotIn("/Users/", data["promptTemplate"])

    def test_environment_reads_current_external_template(self):
        library = self.make_library("external library", "EXTERNAL-LIVE")
        env = dict(self.env, FRONTEND_DESIGN_LIBRARY=str(library))
        result = self.run_selector("--type", "后台", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["catalogUpdatedAt"], "EXTERNAL-LIVE")
        self.assertTrue(data["promptTemplate"].startswith("EXTERNAL-LIVE"))

    def test_explicit_library_overrides_environment(self):
        library = self.make_library("explicit library", "EXPLICIT")
        env = dict(self.env, FRONTEND_DESIGN_LIBRARY=str(self.root / "missing-env-library"))
        result = self.run_selector("--type", "report", "--library", str(library), env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["catalogUpdatedAt"], "EXPLICIT")

    def test_missing_library_fails_with_guidance(self):
        result = self.run_selector("--type", "personal", "--library", str(self.root / "missing"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--library", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_unknown_style_is_not_silently_replaced(self):
        result = self.run_selector("--type", "product", "--style", "nonexistent-style")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("nonexistent-style", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
