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

from flywire_wave.milestone11_readiness import (
    DEFAULT_FIXTURE_TEST_TARGETS,
    execute_milestone11_readiness_pass,
)


class Milestone11ReadinessReportTest(unittest.TestCase):
    def test_execute_readiness_pass_writes_review_report_for_mixed_fidelity_fixture(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = tmp_dir / "milestone_11_verification.yaml"
            config_path.write_text(
                textwrap.dedent(
                    f"""
                    paths:
                      processed_stimulus_dir: {tmp_dir / "out" / "stimuli"}
                      processed_retinal_dir: {tmp_dir / "out" / "retinal"}
                      processed_simulator_results_dir: {tmp_dir / "out" / "simulator_results"}
                      mixed_fidelity_inspection_dir: {tmp_dir / "out" / "mixed_fidelity_inspection"}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            report = execute_milestone11_readiness_pass(
                config_path=config_path,
                fixture_verification={
                    "status": "pass",
                    "command": "python -m unittest",
                    "targets": list(DEFAULT_FIXTURE_TEST_TARGETS),
                },
                python_executable=sys.executable,
                root_dir=ROOT,
            )

            report_dir = tmp_dir / "out" / "simulator_results" / "readiness" / "milestone_11"
            markdown_path = report_dir / "milestone_11_readiness.md"
            json_path = report_dir / "milestone_11_readiness.json"

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

            plan_audit = report["manifest_plan_audit"]
            self.assertEqual(plan_audit["overall_status"], "pass")
            self.assertEqual(plan_audit["surface_wave_arm_count"], 2)
            self.assertEqual(
                plan_audit["surface_wave_topology_conditions"],
                ["intact", "shuffled"],
            )
            self.assertEqual(
                plan_audit["intact_mixed_fidelity_plan"]["resolved_class_counts"],
                {
                    "point_neuron": 2,
                    "skeleton_neuron": 1,
                    "surface_neuron": 1,
                },
            )
            self.assertEqual(
                plan_audit["intact_mixed_fidelity_plan"]["promotion_recommendation_root_ids"],
                [303],
            )

            execution_audit = report["mixed_execution_audit"]
            self.assertEqual(execution_audit["overall_status"], "pass")
            self.assertEqual(execution_audit["executed_run_count"], 1)
            self.assertTrue(execution_audit["summary_stable"])
            self.assertTrue(execution_audit["file_hashes_stable"])
            self.assertEqual(execution_audit["executed_arm_ids"], ["surface_wave_intact"])
            self.assertEqual(
                execution_audit["projection_routes"],
                [
                    "point_state_projection_to_surface_patch_injection",
                    "skeleton_node_projection_to_point_state_injection",
                    "surface_patch_projection_to_skeleton_node_injection",
                ],
            )
            self.assertEqual(
                execution_audit["root_morphology_classes"],
                [
                    "surface_neuron",
                    "skeleton_neuron",
                    "point_neuron",
                    "point_neuron",
                ],
            )
            self.assertEqual(execution_audit["mixed_route_component_count"], 3)

            visualization_audit = report["visualization_audit"]
            self.assertEqual(visualization_audit["overall_status"], "pass")
            self.assertTrue(visualization_audit["summary_stable"])
            self.assertTrue(visualization_audit["artifact_hashes_stable"])
            self.assertTrue(visualization_audit["viewer_is_self_contained"])
            self.assertIn("no local server is required", visualization_audit["viewer_open_hint"])
            self.assertEqual(
                visualization_audit["root_morphology_classes"],
                [
                    "surface_neuron",
                    "skeleton_neuron",
                    "point_neuron",
                    "point_neuron",
                ],
            )

            inspection_audit = report["inspection_audit"]
            self.assertEqual(inspection_audit["overall_status"], "review")
            self.assertEqual(inspection_audit["inspection_summary_status"], "blocking")
            self.assertTrue(inspection_audit["summary_stable"])
            self.assertTrue(inspection_audit["artifact_hashes_stable"])
            self.assertEqual(
                inspection_audit["reference_roots"],
                [
                    {
                        "root_id": 303,
                        "reference_morphology_class": "surface_neuron",
                        "reference_source": "policy_recommendation",
                    }
                ],
            )
            self.assertEqual(inspection_audit["blocking_root_ids"], [303])
            self.assertEqual(inspection_audit["recommended_promotion_root_ids"], [303])

            documentation_audit = report["documentation_audit"]
            self.assertEqual(documentation_audit["overall_status"], "pass")

            self.assertEqual(report["follow_on_readiness"]["status"], "review")
            self.assertTrue(report["follow_on_readiness"]["ready_for_follow_on_work"])
            self.assertEqual(
                report["follow_on_readiness"]["ready_for_workstreams"],
                ["readouts", "validation", "ui"],
            )

            workflow_coverage = report["workflow_coverage"]
            self.assertTrue(all(workflow_coverage.values()))

            follow_on_issues = report["follow_on_issues"]
            self.assertEqual(
                [item["ticket_id"] for item in follow_on_issues],
                ["FW-M11-FOLLOW-001", "FW-M11-FOLLOW-002"],
            )

            markdown_text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("Milestone 11 Readiness Report", markdown_text)
            self.assertIn("Inspection audit: `blocking`", markdown_text)
            self.assertIn("FW-M11-FOLLOW-002", markdown_text)
            self.assertIn("Visualization open URL:", markdown_text)
            self.assertIn("no local server is required", markdown_text)

            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["markdown_path"], report["markdown_path"])
            self.assertEqual(
                persisted["visualization_report_file_url"],
                report["visualization_report_file_url"],
            )


if __name__ == "__main__":
    unittest.main()
