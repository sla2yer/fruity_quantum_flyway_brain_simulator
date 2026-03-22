from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.simulator_execution import execute_manifest_simulation
from flywire_wave.simulator_visualization import generate_simulator_visualization_report

try:
    from test_simulator_execution import _materialize_execution_fixture
except ModuleNotFoundError:
    from tests.test_simulator_execution import _materialize_execution_fixture


class SimulatorVisualizationReportTest(unittest.TestCase):
    def test_generate_visualization_report_writes_deterministic_html_for_baseline_and_wave_runs(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_execution_fixture(Path(tmp_dir_str))

            baseline_summary = execute_manifest_simulation(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                model_mode="baseline",
                arm_id="baseline_p0_intact",
            )
            surface_wave_summary = execute_manifest_simulation(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                model_mode="surface_wave",
                arm_id="surface_wave_intact",
            )
            metadata_paths = [
                baseline_summary["executed_runs"][0]["metadata_path"],
                surface_wave_summary["executed_runs"][0]["metadata_path"],
            ]

            first = generate_simulator_visualization_report(
                bundle_metadata_paths=metadata_paths,
            )
            second = generate_simulator_visualization_report(
                bundle_metadata_paths=list(reversed(metadata_paths)),
            )

            report_path = Path(first["report_path"])
            summary_path = Path(first["summary_path"])
            self.assertTrue(report_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertEqual(first, second)

            report_html = report_path.read_text(encoding="utf-8")
            self.assertIn("Simulator Result Viewer", report_html)
            self.assertIn("baseline_p0_intact", report_html)
            self.assertIn("surface_wave_intact", report_html)
            self.assertIn("signed log10 overlay", report_html)
            self.assertIn("Wave Detail: surface_wave_intact", report_html)

            persisted_summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted_summary["report_version"], first["report_version"])
            self.assertEqual(persisted_summary["bundle_count"], 2)
            self.assertEqual(
                [item["arm_id"] for item in persisted_summary["compared_bundles"]],
                ["baseline_p0_intact", "surface_wave_intact"],
            )


if __name__ == "__main__":
    unittest.main()
