from __future__ import annotations

import unittest

from .cli_startup_test_utils import run_script_with_blocked_imports


class PipelineCliStartupTest(unittest.TestCase):
    def test_select_startup_missing_networkx_is_shaped(self) -> None:
        result = run_script_with_blocked_imports(
            "01_select_subset.py",
            blocked_imports=["networkx"],
        )

        self.assertNotEqual(result.returncode, 0)
        combined_output = result.stdout + result.stderr
        self.assertNotIn("Traceback", combined_output)
        self.assertIn("networkx", combined_output)
        self.assertIn("make bootstrap", combined_output)
        self.assertIn("make select", combined_output)

    def test_meshes_startup_missing_declared_packages_is_shaped(self) -> None:
        cases = [
            ("dotenv", "python-dotenv"),
            ("tqdm", "tqdm"),
        ]
        for blocked_module, expected_package in cases:
            with self.subTest(blocked_module=blocked_module):
                result = run_script_with_blocked_imports(
                    "02_fetch_meshes.py",
                    blocked_imports=[blocked_module],
                )

                self.assertNotEqual(result.returncode, 0)
                combined_output = result.stdout + result.stderr
                self.assertNotIn("Traceback", combined_output)
                self.assertIn(expected_package, combined_output)
                self.assertIn("make bootstrap", combined_output)
                self.assertIn("make meshes", combined_output)

    def test_assets_startup_missing_trimesh_is_shaped(self) -> None:
        result = run_script_with_blocked_imports(
            "03_build_wave_assets.py",
            blocked_imports=["trimesh"],
        )

        self.assertNotEqual(result.returncode, 0)
        combined_output = result.stdout + result.stderr
        self.assertNotIn("Traceback", combined_output)
        self.assertIn("trimesh", combined_output)
        self.assertIn("make bootstrap", combined_output)
        self.assertIn("make assets", combined_output)


if __name__ == "__main__":
    unittest.main()
