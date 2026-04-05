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

from flywire_wave.milestone17_readiness import (
    DEFAULT_FIXTURE_TEST_TARGETS,
    execute_milestone17_readiness_pass,
)


class Milestone17ReadinessReportTest(unittest.TestCase):
    def test_execute_readiness_pass_writes_ready_report_for_whole_brain_context(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = tmp_dir / "milestone_17_verification.yaml"
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

            report = execute_milestone17_readiness_pass(
                config_path=config_path,
                fixture_verification={
                    "status": "pass",
                    "command": "python -m unittest",
                    "targets": list(DEFAULT_FIXTURE_TEST_TARGETS),
                },
                python_executable=sys.executable,
                root_dir=ROOT,
            )

            report_dir = tmp_dir / "out" / "simulator_results" / "readiness" / "milestone_17"
            markdown_path = report_dir / "milestone_17_readiness.md"
            json_path = report_dir / "milestone_17_readiness.json"

            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())
            self.assertEqual(report["report_dir"], str(report_dir.resolve()))
            self.assertEqual(report["markdown_path"], str(markdown_path.resolve()))
            self.assertEqual(report["json_path"], str(json_path.resolve()))

            self.assertEqual(report["showcase_audit"]["overall_status"], "pass")
            self.assertEqual(report["context_review_audit"]["overall_status"], "pass")
            self.assertTrue(report["context_review_audit"]["deterministic"])
            self.assertEqual(report["dashboard_audit"]["overall_status"], "pass")
            self.assertTrue(report["dashboard_audit"]["summary_only_verified"])
            self.assertEqual(report["downstream_module_audit"]["overall_status"], "pass")
            readiness = report["follow_on_readiness"]
            markdown_text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("Milestone 17 Whole-Brain Context Readiness Report", markdown_text)
            self.assertIn("make milestone17-readiness", markdown_text)
            self.assertIn("scripts/36_whole_brain_context_session.py", markdown_text)
            self.assertIn("FW-M17-FOLLOW-001", markdown_text)

            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["markdown_path"], report["markdown_path"])
            self.assertEqual(
                persisted["context_review_audit"]["metadata_path"],
                report["context_review_audit"]["metadata_path"],
            )


if __name__ == "__main__":
    unittest.main()
