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

from flywire_wave.milestone15_readiness import (
    DEFAULT_FIXTURE_TEST_TARGETS,
    execute_milestone15_readiness_pass,
)


class Milestone15ReadinessReportTest(unittest.TestCase):
    def test_execute_readiness_pass_writes_hold_report_for_orchestration_blockers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = tmp_dir / "milestone_15_verification.yaml"
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

            report = execute_milestone15_readiness_pass(
                config_path=config_path,
                fixture_verification={
                    "status": "pass",
                    "command": "python -m unittest",
                    "targets": list(DEFAULT_FIXTURE_TEST_TARGETS),
                },
                python_executable=sys.executable,
                root_dir=ROOT,
            )

            report_dir = tmp_dir / "out" / "simulator_results" / "readiness" / "milestone_15"
            markdown_path = report_dir / "milestone_15_readiness.md"
            json_path = report_dir / "milestone_15_readiness.json"

            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())
            self.assertEqual(report["report_dir"], str(report_dir.resolve()))
            self.assertEqual(report["markdown_path"], str(markdown_path.resolve()))
            self.assertEqual(report["json_path"], str(json_path.resolve()))

            self.assertEqual(report["manifest_resolution_audit"]["overall_status"], "pass")
            self.assertEqual(report["shuffle_simulation_audit"]["overall_status"], "pass")
            self.assertEqual(report["review_audit"]["package_audit"]["overall_status"], "pass")
            self.assertEqual(report["review_audit"]["aggregation_audit"]["overall_status"], "pass")
            self.assertEqual(report["review_audit"]["report_audit"]["overall_status"], "pass")
            self.assertEqual(report["no_waves_audit"]["overall_status"], "pass")
            self.assertEqual(report["no_waves_audit"]["observed_suite_status"], "failed")
            self.assertEqual(report["full_stage_audit"]["overall_status"], "pass")
            self.assertEqual(report["full_stage_audit"]["observed_suite_status"], "failed")
            self.assertFalse(report["workflow_coverage"]["required_ablation_runtime"])
            self.assertFalse(report["workflow_coverage"]["full_stage_manifest_suite"])

            readiness = report["follow_on_readiness"]
            self.assertEqual(readiness["status"], "hold")
            self.assertFalse(readiness["ready_for_follow_on_work"])
            self.assertEqual(readiness["ready_for_milestones"], [])

            follow_on_ticket_ids = [item["ticket_id"] for item in report["follow_on_tickets"]]
            self.assertEqual(
                follow_on_ticket_ids,
                ["FW-M15-FOLLOW-001", "FW-M15-FOLLOW-002"],
            )

            markdown_text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("Milestone 15 Readiness Report", markdown_text)
            self.assertIn("make milestone15-readiness", markdown_text)
            self.assertIn("FW-M15-FOLLOW-001", markdown_text)
            self.assertIn("FW-M15-FOLLOW-002", markdown_text)

            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["markdown_path"], report["markdown_path"])
            self.assertEqual(
                persisted["review_audit"]["report_audit"]["summary_path"],
                report["review_audit"]["report_audit"]["summary_path"],
            )


if __name__ == "__main__":
    unittest.main()
