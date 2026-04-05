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
from flywire_wave.milestone9_readiness import (
    _materialize_verification_fixture,
    execute_milestone9_readiness_pass,
)
from flywire_wave.selection import build_subset_artifact_paths
try:
    from tests.simulation_planning_test_support import _write_manifest_fixture
except ModuleNotFoundError:
    from simulation_planning_test_support import _write_manifest_fixture  # type: ignore[no-redef]


class Milestone9ReadinessReportTest(unittest.TestCase):
    def test_execute_readiness_pass_writes_deterministic_report_and_audits_manifest_workflow(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = tmp_dir / "milestone_9_verification.yaml"
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

            report = execute_milestone9_readiness_pass(
                config_path=config_path,
                fixture_verification={"status": "pass", "command": "python -m unittest"},
                python_executable=sys.executable,
                root_dir=ROOT,
            )

            report_dir = tmp_dir / "out" / "simulator_results" / "readiness" / "milestone_9"
            markdown_path = report_dir / "milestone_9_readiness.md"
            json_path = report_dir / "milestone_9_readiness.json"

            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())
            self.assertEqual(report["report_dir"], str(report_dir.resolve()))
            self.assertEqual(report["markdown_path"], str(markdown_path.resolve()))
            self.assertEqual(report["json_path"], str(json_path.resolve()))
            plan_audit = report["manifest_plan_audit"]
            self.assertEqual(plan_audit["overall_status"], "pass")
            self.assertEqual(plan_audit["baseline_arm_count"], 4)
            self.assertEqual(plan_audit["surface_wave_arm_count"], 2)
            self.assertEqual(plan_audit["baseline_seed_sweep_run_count"], 12)
            self.assertEqual(plan_audit["baseline_families"], ["P0", "P1"])
            self.assertEqual(plan_audit["topology_conditions"], ["intact", "shuffled"])

            execution_audit = report["manifest_execution_audit"]
            self.assertEqual(execution_audit["overall_status"], "pass")
            self.assertEqual(execution_audit["executed_run_count"], 4)
            self.assertTrue(execution_audit["summary_stable"])
            self.assertTrue(execution_audit["file_hashes_stable"])
            self.assertEqual(
                execution_audit["executed_arm_ids"],
                ["baseline_p0_intact", "baseline_p0_shuffled", "baseline_p1_intact", "baseline_p1_shuffled"],
            )

            p0_audit = execution_audit["per_arm_audits"]["baseline_p0_intact"]
            p1_audit = execution_audit["per_arm_audits"]["baseline_p1_intact"]
            self.assertFalse(p0_audit["has_synaptic_current_state"])
            self.assertTrue(p1_audit["has_synaptic_current_state"])
            self.assertEqual(p0_audit["canonical_input_kind"], "stimulus_bundle")
            self.assertEqual(p1_audit["canonical_input_kind"], "stimulus_bundle")
            self.assertIn("final_endpoint_value", p0_audit["metric_ids"])
            self.assertIn("surface_vs_baseline_split_view", p1_audit["ui_view_ids"])

            self.assertEqual(
                report["follow_on_readiness"]["ready_for_workstreams"],
                ["surface_wave", "metrics", "ui_comparison"],
            )

            markdown_text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("Milestone 9 Readiness Report", markdown_text)
            self.assertIn("Per-Arm Bundle Audits", markdown_text)
            self.assertIn("baseline_p1_intact", markdown_text)

            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["markdown_path"], report["markdown_path"])

    def test_verification_fixture_uses_selection_contract_for_mixed_case_subset_names(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            subset_name = "Motion Minimal! Beta"
            manifest_path = _write_manifest_fixture(
                tmp_dir,
                manifest_overrides={"subset_name": subset_name},
            )

            fixture = _materialize_verification_fixture(
                manifest_path=manifest_path,
                verification_cfg={},
                generated_fixture_dir=tmp_dir / "fixture",
                processed_stimulus_dir=tmp_dir / "out" / "stimuli",
                processed_retinal_dir=tmp_dir / "out" / "retinal",
                processed_simulator_results_dir=tmp_dir / "out" / "simulator_results",
            )

            expected_subset_paths = build_subset_artifact_paths(
                tmp_dir / "fixture" / "subsets",
                subset_name,
            )
            self.assertEqual(
                fixture["subset_manifest_path"],
                str(expected_subset_paths.manifest_json.resolve()),
            )
            self.assertEqual(read_root_ids(fixture["selected_root_ids_path"]), [101, 202])


if __name__ == "__main__":
    unittest.main()
