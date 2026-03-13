from __future__ import annotations

import shutil
import unittest
import importlib.util
from pathlib import Path


def _load_build():
    module_path = Path("scripts/distribution/build_skill_package.py")
    spec = importlib.util.spec_from_file_location("build_skill_package", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build


build = _load_build()


class DistributionBuildTest(unittest.TestCase):
    def tearDown(self) -> None:
        dist_dir = Path("dist")
        if dist_dir.exists():
            shutil.rmtree(dist_dir)

    def test_build_outputs_portable_skill_package(self) -> None:
        package_root, zip_path, tar_path = build()

        self.assertTrue(package_root.exists())
        self.assertTrue((package_root / "install.sh").exists())
        self.assertTrue((package_root / "config.example.json").exists())
        self.assertTrue((package_root / "profiles" / "research-interest.example.json").exists())
        self.assertTrue((package_root / "references" / "workflow.md").exists())
        self.assertTrue((package_root / "src" / "codex_research_assist" / "openclaw_runner.py").exists())
        self.assertTrue(zip_path.exists())
        self.assertTrue(tar_path.exists())


if __name__ == "__main__":
    unittest.main()
