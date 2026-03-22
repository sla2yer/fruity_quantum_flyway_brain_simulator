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

from flywire_wave.milestone8b_readiness import execute_milestone8b_readiness_pass


class Milestone8BReadinessReportTest(unittest.TestCase):
    def test_execute_readiness_pass_writes_deterministic_report_and_exercises_all_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = tmp_dir / "milestone_8b_verification.yaml"
            config_path.write_text(
                textwrap.dedent(
                    f"""
                    paths:
                      processed_stimulus_dir: {tmp_dir / "out" / "stimuli"}
                      processed_retinal_dir: {tmp_dir / "out" / "retinal"}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            report = execute_milestone8b_readiness_pass(
                config_path=config_path,
                fixture_verification={"status": "pass", "command": "python -m unittest"},
                python_executable=sys.executable,
                root_dir=ROOT,
            )

            report_dir = tmp_dir / "out" / "retinal" / "readiness" / "milestone_8b"
            markdown_path = report_dir / "milestone_8b_readiness.md"
            json_path = report_dir / "milestone_8b_readiness.json"

            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())
            self.assertEqual(report["report_dir"], str(report_dir.resolve()))
            self.assertEqual(report["markdown_path"], str(markdown_path.resolve()))
            self.assertEqual(report["json_path"], str(json_path.resolve()))
            self.assertEqual(report["documentation_audit"]["overall_status"], "pass")
            self.assertEqual(sorted(report["entrypoint_audits"].keys()), ["manifest_demo", "scene_entrypoint", "stimulus_config"])
            self.assertTrue(report["workflow_coverage"]["bundle_discovery_compatible"])
            self.assertTrue(report["workflow_coverage"]["coordinate_transforms_compatible"])
            self.assertTrue(report["workflow_coverage"]["projection_and_sampling_compatible"])
            self.assertTrue(report["workflow_coverage"]["temporal_bundling_compatible"])
            self.assertTrue(report["workflow_coverage"]["offline_inspection_compatible"])

            stimulus_audit = report["entrypoint_audits"]["stimulus_config"]
            manifest_audit = report["entrypoint_audits"]["manifest_demo"]
            scene_audit = report["entrypoint_audits"]["scene_entrypoint"]
            self.assertEqual(stimulus_audit["overall_status"], "pass")
            self.assertEqual(manifest_audit["overall_status"], "pass")
            self.assertEqual(scene_audit["overall_status"], "pass")
            self.assertEqual(
                stimulus_audit["source_reference"]["source_kind"],
                "stimulus_bundle",
            )
            self.assertEqual(
                scene_audit["source_reference"]["source_kind"],
                "scene_description",
            )
            self.assertTrue(stimulus_audit["workflow_checks"]["record_hashes_stable"])
            self.assertTrue(stimulus_audit["workflow_checks"]["resolved_replay_matches_bundle_replay"])
            self.assertTrue(stimulus_audit["workflow_checks"]["transform_metadata_consistent"])
            self.assertTrue(scene_audit["workflow_checks"]["inspection_hashes_stable"])
            self.assertEqual(manifest_audit["inspection"]["qa_overall_status"], "pass")
            self.assertEqual(scene_audit["inspection"]["coverage_overall_status"], "pass")

            self.assertEqual(report["follow_on_readiness"]["status"], "ready")
            self.assertTrue(report["follow_on_readiness"]["ready_for_follow_on_work"])
            self.assertEqual(
                report["follow_on_readiness"]["ready_for_milestones"],
                ["8C", "9", "later_ui_review"],
            )

            markdown_text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("Milestone 8B Readiness Report", markdown_text)
            self.assertIn("Workflow Coverage", markdown_text)
            self.assertIn("stimulus_config", markdown_text)
            self.assertIn("scene_entrypoint", markdown_text)

            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["markdown_path"], report["markdown_path"])


if __name__ == "__main__":
    unittest.main()
