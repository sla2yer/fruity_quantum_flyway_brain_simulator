from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave import simulator_cli, simulator_execution


class SimulatorCliSeamTest(unittest.TestCase):
    def test_build_parser_preserves_manifest_execution_flags(self) -> None:
        parser = simulator_cli.build_parser()

        args = parser.parse_args(
            [
                "--config",
                "config.yaml",
                "--manifest",
                "manifest.yaml",
                "--schema",
                "schema.json",
                "--design-lock",
                "design_lock.yaml",
                "--model-mode",
                "surface_wave",
                "--arm-id",
                "surface_wave_intact",
                "--use-manifest-seed-sweep",
            ]
        )

        self.assertEqual(args.config, "config.yaml")
        self.assertEqual(args.manifest, "manifest.yaml")
        self.assertEqual(args.schema, "schema.json")
        self.assertEqual(args.design_lock, "design_lock.yaml")
        self.assertEqual(args.model_mode, "surface_wave")
        self.assertEqual(args.arm_id, "surface_wave_intact")
        self.assertTrue(args.use_manifest_seed_sweep)

    def test_execution_main_delegates_to_cli_module(self) -> None:
        with mock.patch("flywire_wave.simulator_cli.main", return_value=7) as mocked_main:
            result = simulator_execution.main(["--config", "config.yaml"])

        self.assertEqual(result, 7)
        mocked_main.assert_called_once_with(["--config", "config.yaml"])

    def test_execution_module_no_longer_owns_argparse(self) -> None:
        source = (SRC / "flywire_wave" / "simulator_execution.py").read_text(encoding="utf-8")

        self.assertNotIn("import argparse", source)
        self.assertNotIn("ArgumentParser(", source)


if __name__ == "__main__":
    unittest.main()
