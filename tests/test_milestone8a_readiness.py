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

from flywire_wave.milestone8a_readiness import execute_milestone8a_readiness_pass


class Milestone8AReadinessReportTest(unittest.TestCase):
    def test_execute_readiness_pass_writes_deterministic_report_and_exercises_all_families(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = tmp_dir / "milestone_8a_verification.yaml"
            config_path.write_text(
                textwrap.dedent(
                    f"""
                    paths:
                      processed_stimulus_dir: {tmp_dir / "out" / "stimuli"}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            report = execute_milestone8a_readiness_pass(
                config_path=config_path,
                fixture_verification={"status": "pass", "command": "python -m unittest"},
                python_executable=sys.executable,
                root_dir=ROOT,
            )

            report_dir = tmp_dir / "out" / "stimuli" / "readiness" / "milestone_8a"
            markdown_path = report_dir / "milestone_8a_readiness.md"
            json_path = report_dir / "milestone_8a_readiness.json"

            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())
            self.assertEqual(report["report_dir"], str(report_dir.resolve()))
            self.assertEqual(report["markdown_path"], str(markdown_path.resolve()))
            self.assertEqual(report["json_path"], str(json_path.resolve()))
            self.assertEqual(
                sorted(report["exercised_stimulus_families"]),
                [
                    "drifting_grating",
                    "flash",
                    "looming",
                    "moving_bar",
                    "radial_flow",
                    "rotating_flow",
                    "translated_edge",
                ],
            )
            self.assertEqual(report["family_count"], 7)
            self.assertTrue(report["family_coverage_ok"])
            self.assertEqual(report["registry_catalog_audit"]["overall_status"], "pass")
            self.assertTrue(report["registry_catalog_audit"]["coverage_ok"])
            self.assertEqual(report["manifest_audit"]["overall_status"], "pass")
            self.assertEqual(report["manifest_audit"]["validation_summary"]["resolved_stimulus_family"], "translated_edge")
            self.assertTrue(report["manifest_audit"]["deterministic_file_hashes"])
            self.assertEqual(report["documentation_audit"]["overall_status"], "pass")
            self.assertTrue(
                all(audit["overall_status"] == "pass" for audit in report["family_audits"])
            )
            self.assertTrue(
                all(audit["deterministic_file_hashes"] for audit in report["family_audits"])
            )
            self.assertTrue(
                all(audit["descriptor_regeneration_matches_cache"] for audit in report["family_audits"])
            )

            translated_edge_audit = next(
                audit for audit in report["family_audits"] if audit["stimulus_family"] == "translated_edge"
            )
            self.assertTrue(translated_edge_audit["compatibility_alias_used"])
            self.assertTrue(translated_edge_audit["family_alias_used"])
            self.assertTrue(translated_edge_audit["name_alias_used"])
            self.assertEqual(report["follow_on_readiness"]["status"], "ready")
            self.assertTrue(report["follow_on_readiness"]["ready_for_follow_on_work"])

            markdown_text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("Milestone 8A Readiness Report", markdown_text)
            self.assertIn("Families Exercised", markdown_text)
            self.assertIn("Milestones 8B, 8C", markdown_text)

            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["markdown_path"], report["markdown_path"])


if __name__ == "__main__":
    unittest.main()
