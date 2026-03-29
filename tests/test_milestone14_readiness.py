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

from flywire_wave.milestone14_readiness import (
    DEFAULT_FIXTURE_TEST_TARGETS,
    execute_milestone14_readiness_pass,
)


class Milestone14ReadinessReportTest(unittest.TestCase):
    def test_execute_readiness_pass_writes_ready_report_for_dashboard(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = tmp_dir / "milestone_14_verification.yaml"
            config_path.write_text(
                textwrap.dedent(
                    f"""
                    paths:
                      processed_stimulus_dir: {tmp_dir / "out" / "stimuli"}
                      processed_retinal_dir: {tmp_dir / "out" / "retinal"}
                      processed_simulator_results_dir: {tmp_dir / "out" / "simulator_results"}

                    dashboard_verification:
                      experiment_id: milestone_1_demo_motion_patch
                      baseline_arm_id: baseline_p0_intact
                      wave_arm_id: surface_wave_intact
                      preferred_seed: 11
                      preferred_condition_ids:
                        - on_polarity
                        - preferred_direction
                      snapshot_overlay_id: phase_map_reference
                      metrics_overlay_id: reviewer_findings
                      snapshot_sample_index: 3
                      metrics_sample_index: 2
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            report = execute_milestone14_readiness_pass(
                config_path=config_path,
                fixture_verification={
                    "status": "pass",
                    "command": "python -m unittest",
                    "targets": list(DEFAULT_FIXTURE_TEST_TARGETS),
                },
                python_executable=sys.executable,
                root_dir=ROOT,
            )

            report_dir = tmp_dir / "out" / "simulator_results" / "readiness" / "milestone_14"
            markdown_path = report_dir / "milestone_14_readiness.md"
            json_path = report_dir / "milestone_14_readiness.json"

            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())
            self.assertEqual(report["report_dir"], str(report_dir.resolve()))
            self.assertEqual(report["markdown_path"], str(markdown_path.resolve()))
            self.assertEqual(report["json_path"], str(json_path.resolve()))

            planning_audit = report["planning_audit"]
            self.assertEqual(planning_audit["overall_status"], "pass")
            self.assertTrue(planning_audit["payloads_match"])
            self.assertTrue(planning_audit["states_match"])
            self.assertEqual(
                planning_audit["pane_ids"],
                ["scene", "circuit", "morphology", "time_series", "analysis"],
            )

            workflow_audit = report["workflow_audit"]
            self.assertEqual(workflow_audit["overall_status"], "pass")
            self.assertEqual(workflow_audit["build_audit"]["overall_status"], "pass")
            self.assertEqual(workflow_audit["pane_audit"]["overall_status"], "pass")
            self.assertEqual(workflow_audit["export_audit"]["overall_status"], "pass")
            self.assertEqual(
                workflow_audit["build_audit"]["open_no_browser"]["parsed_summary"][
                    "browser_opened"
                ],
                False,
            )
            self.assertGreater(workflow_audit["pane_audit"]["scene_frame_count"], 0)
            self.assertGreater(workflow_audit["pane_audit"]["circuit_edge_count"], 0)
            self.assertGreater(
                workflow_audit["pane_audit"]["analysis_phase_map_reference_count"], 0
            )

            self.assertEqual(report["documentation_audit"]["overall_status"], "pass")
            self.assertTrue(all(report["workflow_coverage"].values()))

            readiness = report["follow_on_readiness"]
            self.assertEqual(readiness["status"], "ready")
            self.assertTrue(readiness["ready_for_follow_on_work"])
            self.assertEqual(
                readiness["ready_for_milestones"],
                ["milestone_15_experiment_orchestration", "milestone_16_showcase_mode"],
            )

            markdown_text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("Milestone 14 Dashboard Readiness Report", markdown_text)
            self.assertIn("make milestone14-readiness", markdown_text)
            self.assertIn("--no-browser", markdown_text)
            self.assertIn("FW-M14-FOLLOW-001", markdown_text)

            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["markdown_path"], report["markdown_path"])
            self.assertEqual(
                persisted["workflow_audit"]["build_audit"]["metadata_path"],
                report["workflow_audit"]["build_audit"]["metadata_path"],
            )


if __name__ == "__main__":
    unittest.main()
