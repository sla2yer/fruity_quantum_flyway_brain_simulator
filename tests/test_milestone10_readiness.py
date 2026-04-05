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

from flywire_wave.milestone10_readiness import (
    DEFAULT_FIXTURE_TEST_TARGETS,
    execute_milestone10_readiness_pass,
)


class Milestone10ReadinessReportTest(unittest.TestCase):
    def test_execute_readiness_pass_writes_deterministic_report_and_audits_surface_wave_workflow(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = tmp_dir / "milestone_10_verification.yaml"
            config_path.write_text(
                textwrap.dedent(
                    f"""
                    paths:
                      processed_stimulus_dir: {tmp_dir / "out" / "stimuli"}
                      processed_retinal_dir: {tmp_dir / "out" / "retinal"}
                      processed_simulator_results_dir: {tmp_dir / "out" / "simulator_results"}
                      surface_wave_inspection_dir: {tmp_dir / "out" / "surface_wave_inspection"}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            report = execute_milestone10_readiness_pass(
                config_path=config_path,
                fixture_verification={
                    "status": "pass",
                    "command": "python -m unittest",
                    "targets": list(DEFAULT_FIXTURE_TEST_TARGETS),
                },
                python_executable=sys.executable,
                root_dir=ROOT,
            )

            report_dir = tmp_dir / "out" / "simulator_results" / "readiness" / "milestone_10"
            markdown_path = report_dir / "milestone_10_readiness.md"
            json_path = report_dir / "milestone_10_readiness.json"

            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())
            self.assertEqual(report["report_dir"], str(report_dir.resolve()))
            self.assertEqual(report["markdown_path"], str(markdown_path.resolve()))
            self.assertEqual(report["json_path"], str(json_path.resolve()))
            plan_audit = report["manifest_plan_audit"]
            self.assertEqual(plan_audit["overall_status"], "pass")
            self.assertEqual(plan_audit["baseline_arm_count"], 4)
            self.assertEqual(plan_audit["surface_wave_arm_count"], 2)
            self.assertEqual(plan_audit["surface_wave_seed_sweep_run_count"], 6)
            self.assertEqual(
                plan_audit["surface_wave_topology_conditions"],
                ["intact", "shuffled"],
            )
            self.assertEqual(
                plan_audit["surface_wave_model_audit"]["overall_status"],
                "pass",
            )

            execution_audit = report["surface_wave_execution_audit"]
            self.assertEqual(execution_audit["overall_status"], "pass")
            self.assertEqual(execution_audit["executed_run_count"], 1)
            self.assertTrue(execution_audit["summary_stable"])
            self.assertTrue(execution_audit["file_hashes_stable"])
            self.assertEqual(execution_audit["executed_arm_ids"], ["surface_wave_intact"])

            bundle_audit = execution_audit["bundle_audit"]
            self.assertEqual(bundle_audit["overall_status"], "pass")
            self.assertTrue(bundle_audit["comparison_ready_bundle"])
            self.assertEqual(bundle_audit["canonical_input_kind"], "stimulus_bundle")
            self.assertEqual(
                set(bundle_audit["wave_specific_artifact_ids"]),
                {
                    "surface_wave_summary",
                    "surface_wave_patch_traces",
                    "surface_wave_coupling_events",
                },
            )

            baseline_audit = report["baseline_comparison_audit"]
            self.assertEqual(baseline_audit["overall_status"], "pass")
            self.assertEqual(baseline_audit["baseline_arm_id"], "baseline_p1_intact")
            self.assertTrue(baseline_audit["comparison_surface_aligned"])

            inspection_audit = report["surface_wave_inspection_audit"]
            self.assertEqual(inspection_audit["overall_status"], "pass")
            self.assertEqual(inspection_audit["inspection_summary_status"], "pass")
            self.assertTrue(inspection_audit["summary_stable"])
            self.assertTrue(inspection_audit["artifact_hashes_stable"])
            self.assertEqual(inspection_audit["run_count"], 1)
            self.assertEqual(
                inspection_audit["sweep_point_ids"],
                ["verification_reference"],
            )
            self.assertEqual(
                inspection_audit["passing_sweep_point_ids"],
                ["verification_reference"],
            )

            self.assertEqual(
                report["follow_on_readiness"]["ready_for_workstreams"],
                ["mixed_fidelity", "metrics", "validation", "ui"],
            )

            follow_on_issues = report["follow_on_issues"]
            self.assertEqual(len(follow_on_issues), 1)
            self.assertEqual(follow_on_issues[0]["ticket_id"], "FW-M10-FOLLOW-001")

            markdown_text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("Milestone 10 Readiness Report", markdown_text)
            self.assertIn("Surface-Wave Execution Audit", markdown_text)
            self.assertIn("FW-M10-FOLLOW-001", markdown_text)

            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["markdown_path"], report["markdown_path"])


if __name__ == "__main__":
    unittest.main()
