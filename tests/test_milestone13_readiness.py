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

from flywire_wave.io_utils import read_root_ids
from flywire_wave.milestone13_readiness import (
    DEFAULT_FIXTURE_TEST_TARGETS,
    _write_simulation_fixture,
    execute_milestone13_readiness_pass,
)
from flywire_wave.selection import build_subset_artifact_paths


class Milestone13ReadinessReportTest(unittest.TestCase):
    def test_execute_readiness_pass_writes_ready_report_for_validation_ladder(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = tmp_dir / "milestone_13_verification.yaml"
            config_path.write_text(
                textwrap.dedent(
                    f"""
                    paths:
                      processed_stimulus_dir: {tmp_dir / "out" / "stimuli"}
                      processed_retinal_dir: {tmp_dir / "out" / "retinal"}
                      processed_simulator_results_dir: {tmp_dir / "out" / "simulator_results"}

                    simulation_verification:
                      manifest_path: manifests/examples/milestone_1_demo.yaml
                      schema_path: schemas/milestone_1_experiment_manifest.schema.json
                      design_lock_path: config/milestone_1_design_lock.yaml

                    validation_verification:
                      smoke_baseline_path: tests/fixtures/validation_ladder_smoke_baseline.json
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            report = execute_milestone13_readiness_pass(
                config_path=config_path,
                fixture_verification={
                    "status": "pass",
                    "command": "python -m unittest",
                    "targets": list(DEFAULT_FIXTURE_TEST_TARGETS),
                },
                python_executable=sys.executable,
                root_dir=ROOT,
            )

            report_dir = tmp_dir / "out" / "simulator_results" / "readiness" / "milestone_13"
            markdown_path = report_dir / "milestone_13_readiness.md"
            json_path = report_dir / "milestone_13_readiness.json"

            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())
            self.assertEqual(report["report_dir"], str(report_dir.resolve()))
            self.assertEqual(report["markdown_path"], str(markdown_path.resolve()))
            self.assertEqual(report["json_path"], str(json_path.resolve()))

            plan_audit = report["validation_plan_audit"]
            self.assertEqual(plan_audit["overall_status"], "pass")
            self.assertEqual(
                plan_audit["active_layer_ids"],
                [
                    "numerical_sanity",
                    "morphology_sanity",
                    "circuit_sanity",
                    "task_sanity",
                ],
            )
            self.assertIn("task_decoder_robustness", plan_audit["layer_validator_ids"]["task_sanity"])
            self.assertIn("sign_delay_perturbations", plan_audit["perturbation_suite_ids"])

            smoke_audit = report["smoke_workflow_audit"]
            self.assertEqual(smoke_audit["overall_status"], "pass")
            self.assertEqual(smoke_audit["artifact_discovery_status"], "pass")
            self.assertTrue(smoke_audit["summary_stable"])
            self.assertTrue(smoke_audit["artifact_hashes_stable"])
            self.assertEqual(smoke_audit["packaged_overall_status"], "review")
            self.assertEqual(smoke_audit["regression_status"], "pass")
            self.assertEqual(
                smoke_audit["discovered_layer_ids"],
                [
                    "circuit_sanity",
                    "morphology_sanity",
                    "numerical_sanity",
                    "task_sanity",
                ],
            )

            self.assertEqual(report["command_surface_audit"]["overall_status"], "pass")
            readiness = report["follow_on_readiness"]
            markdown_text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("Milestone 13 Readiness Report", markdown_text)
            self.assertIn("make milestone13-readiness", markdown_text)
            self.assertIn("FW-M13-FOLLOW-001", markdown_text)

            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["markdown_path"], report["markdown_path"])
            self.assertEqual(
                persisted["smoke_workflow_audit"]["summary_path"],
                report["smoke_workflow_audit"]["summary_path"],
            )

    def test_simulation_fixture_uses_selection_contract_for_mixed_case_subset_names(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            subset_name = "Motion Minimal! Beta"

            _write_simulation_fixture(
                tmp_dir / "fixture",
                validation_config={"subset_name": subset_name},
            )

            expected_subset_paths = build_subset_artifact_paths(
                tmp_dir / "fixture" / "out" / "subsets",
                subset_name,
            )
            self.assertTrue(expected_subset_paths.manifest_json.exists())
            self.assertEqual(
                read_root_ids(tmp_dir / "fixture" / "out" / "selected_root_ids.txt"),
                [101, 202],
            )


if __name__ == "__main__":
    unittest.main()
