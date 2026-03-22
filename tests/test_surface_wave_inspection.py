from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.surface_wave_inspection import execute_surface_wave_inspection_workflow
from test_simulator_execution import _materialize_execution_fixture


class SurfaceWaveInspectionWorkflowTest(unittest.TestCase):
    def test_fixture_sweep_writes_deterministic_reports_and_summary_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _materialize_execution_fixture(tmp_dir)
            sweep_spec_path = tmp_dir / "sweep_spec.yaml"
            inspection_output_dir = tmp_dir / "inspection"
            sweep_spec_path.write_text(
                yaml.safe_dump(
                    {
                        "version": "surface_wave_sweep.v1",
                        "representative_root_limit": 1,
                        "parameter_sets": [
                            {
                                "sweep_point_id": "reference",
                                "parameter_bundle": {
                                    "parameter_preset": "inspection_reference",
                                },
                            },
                            {
                                "sweep_point_id": "guardrail_fail",
                                "parameter_bundle": {
                                    "parameter_preset": "inspection_guardrail_fail",
                                    "propagation": {
                                        "wave_speed_sq_scale": 1.0e6,
                                    },
                                },
                            },
                        ],
                        "grid": {
                            "sweep_id": "gamma_probe",
                            "axes": [
                                {
                                    "key": "damping.gamma_per_ms",
                                    "values": [0.18, 0.28],
                                }
                            ],
                        },
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            first = execute_surface_wave_inspection_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                arm_ids=["surface_wave_intact"],
                sweep_spec_path=sweep_spec_path,
                output_dir=inspection_output_dir,
            )
            second = execute_surface_wave_inspection_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                arm_ids=["surface_wave_intact"],
                sweep_spec_path=sweep_spec_path,
                output_dir=inspection_output_dir,
            )

            self.assertEqual(first["output_dir"], second["output_dir"])
            self.assertEqual(first["report_path"], second["report_path"])
            self.assertEqual(first["run_count"], 4)
            self.assertEqual(
                [item["run_id"] for item in first["run_summaries"]],
                [item["run_id"] for item in second["run_summaries"]],
            )

            summary_path = Path(first["summary_path"]).resolve()
            report_path = Path(first["report_path"]).resolve()
            runs_csv_path = Path(first["runs_csv_path"]).resolve()
            self.assertTrue(summary_path.exists())
            self.assertTrue(report_path.exists())
            self.assertTrue(runs_csv_path.exists())

            run_by_point = {
                item["parameter_context"]["sweep_point_id"]: item
                for item in first["run_summaries"]
            }
            self.assertIn("reference", run_by_point)
            self.assertIn("guardrail_fail", run_by_point)
            self.assertIn("gamma_probe-000", run_by_point)
            self.assertIn("gamma_probe-001", run_by_point)

            reference_run = run_by_point["reference"]
            self.assertIn(reference_run["overall_status"], {"warn", "fail"})
            self.assertIn("shared_output_peak_abs", reference_run["metrics"])
            self.assertIn("pulse_energy_growth_factor_max", reference_run["metrics"])
            self.assertIn("pulse_wavefront_detected_count", reference_run["metrics"])
            self.assertIn("checks", reference_run["diagnostics"])
            self.assertTrue(
                {
                    "coupled_values_finite",
                    "pulse_values_finite",
                    "pulse_wavefront_detected",
                }.issubset(
                    {
                        item["check_id"]
                        for item in reference_run["diagnostics"]["checks"]
                    }
                )
            )
            self.assertTrue(Path(reference_run["artifacts"]["report_path"]).exists())
            self.assertTrue(Path(reference_run["artifacts"]["summary_path"]).exists())
            self.assertTrue(Path(reference_run["artifacts"]["traces_path"]).exists())
            self.assertTrue(
                Path(reference_run["artifacts"]["coupled_shared_trace_svg_path"]).exists()
            )

            failed_run = run_by_point["guardrail_fail"]
            self.assertEqual(failed_run["overall_status"], "fail")
            self.assertIn("execution_error", failed_run)
            self.assertEqual(
                failed_run["diagnostics"]["checks"][0]["check_id"],
                "execution_completed",
            )
            self.assertTrue(Path(failed_run["artifacts"]["report_path"]).exists())
            self.assertTrue(Path(failed_run["artifacts"]["summary_path"]).exists())


if __name__ == "__main__":
    unittest.main()
