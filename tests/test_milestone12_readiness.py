from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.milestone12_readiness import (
    DEFAULT_FIXTURE_TEST_TARGETS,
    execute_milestone12_readiness_pass,
)
from flywire_wave.readout_analysis_contract import (
    RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS,
    SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
)


class Milestone12ReadinessReportTest(unittest.TestCase):
    def test_execute_readiness_pass_writes_ready_report_for_task_layer_fixture(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = tmp_dir / "milestone_12_verification.yaml"
            config_path.write_text(
                textwrap.dedent(
                    f"""
                    paths:
                      processed_stimulus_dir: {tmp_dir / "out" / "stimuli"}
                      processed_retinal_dir: {tmp_dir / "out" / "retinal"}
                      processed_simulator_results_dir: {tmp_dir / "out" / "simulator_results"}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            report = execute_milestone12_readiness_pass(
                config_path=config_path,
                fixture_verification={
                    "status": "pass",
                    "command": "python -m unittest",
                    "targets": list(DEFAULT_FIXTURE_TEST_TARGETS),
                },
                python_executable=sys.executable,
                root_dir=ROOT,
            )

            report_dir = tmp_dir / "out" / "simulator_results" / "readiness" / "milestone_12"
            markdown_path = report_dir / "milestone_12_readiness.md"
            json_path = report_dir / "milestone_12_readiness.json"

            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())
            self.assertEqual(report["report_dir"], str(report_dir.resolve()))
            self.assertEqual(report["markdown_path"], str(markdown_path.resolve()))
            self.assertEqual(report["json_path"], str(json_path.resolve()))
            self.assertTrue(report["visualization_report_path"].endswith("/visualization/index.html"))
            self.assertEqual(
                report["visualization_report_file_url"],
                Path(report["visualization_report_path"]).resolve().as_uri(),
            )
            self.assertIn("no local server is required", report["visualization_open_hint"])

            analysis_plan_audit = report["analysis_plan_audit"]
            self.assertEqual(analysis_plan_audit["overall_status"], "pass")
            self.assertGreater(len(analysis_plan_audit["shared_metric_ids"]), 0)
            self.assertGreater(len(analysis_plan_audit["task_metric_ids"]), 0)
            self.assertGreater(len(analysis_plan_audit["wave_metric_ids"]), 0)
            self.assertIn(
                RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS,
                analysis_plan_audit["analysis_artifact_classes"],
            )
            self.assertIn(
                SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
                analysis_plan_audit["analysis_artifact_classes"],
            )

            comparison_workflow_audit = report["comparison_workflow_audit"]
            self.assertEqual(comparison_workflow_audit["overall_status"], "pass")
            self.assertTrue(comparison_workflow_audit["summary_stable"])
            self.assertTrue(comparison_workflow_audit["artifact_hashes_stable"])
            self.assertTrue(comparison_workflow_audit["quantitative_comparison_verified"])
            self.assertEqual(comparison_workflow_audit["decision_panel_status"], "pass")
            self.assertEqual(comparison_workflow_audit["bundle_inventory_count"], 72)
            self.assertGreater(comparison_workflow_audit["shared_metric_row_count"], 0)
            self.assertGreater(comparison_workflow_audit["task_metric_row_count"], 0)
            self.assertGreater(comparison_workflow_audit["wave_metric_row_count"], 0)
            self.assertEqual(
                comparison_workflow_audit["null_test_status_by_id"],
                {
                    "geometry_shuffle_collapse": "pass",
                    "seed_stability": "pass",
                    "stronger_baseline_survival": "pass",
                },
            )

            packaged_export_audit = report["packaged_export_audit"]
            self.assertEqual(packaged_export_audit["overall_status"], "pass")
            self.assertIn(
                "shared_task_rollup_matrix",
                packaged_export_audit["comparison_matrix_ids"],
            )
            self.assertIn(
                "wave_diagnostic_rollup_matrix",
                packaged_export_audit["comparison_matrix_ids"],
            )
            self.assertGreater(packaged_export_audit["phase_map_reference_count"], 0)
            self.assertIn(
                "motion_decoder_summary",
                packaged_export_audit["comparison_card_output_ids"],
            )
            self.assertIn(
                "wave_diagnostic_summary",
                packaged_export_audit["comparison_card_output_ids"],
            )

            visualization_audit = report["visualization_audit"]
            self.assertEqual(visualization_audit["overall_status"], "pass")
            self.assertTrue(visualization_audit["summary_stable"])
            self.assertTrue(visualization_audit["artifact_hashes_stable"])
            self.assertIn("no local server is required", visualization_audit["viewer_open_hint"])
            self.assertGreater(visualization_audit["phase_map_reference_count"], 0)

            markdown_text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("Milestone 12 Readiness Report", markdown_text)
            self.assertIn("motion_decoder_summary", markdown_text)
            self.assertIn("FW-M12-FOLLOW-002", markdown_text)
            self.assertIn("no local server is required", markdown_text)

            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["markdown_path"], report["markdown_path"])
            self.assertEqual(
                persisted["visualization_report_file_url"],
                report["visualization_report_file_url"],
            )


if __name__ == "__main__":
    unittest.main()
