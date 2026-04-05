from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.manifests import load_json, load_yaml, validate_manifest, validate_manifest_payload
from flywire_wave.simulation_planning import resolve_manifest_simulation_plan
from flywire_wave.stimulus_bundle import record_stimulus_bundle, resolve_stimulus_input
from tests.test_simulation_planning import _write_simulation_fixture


class ManifestValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = load_json(ROOT / "schemas/milestone_1_experiment_manifest.schema.json")
        cls.design_lock = load_yaml(ROOT / "config/milestone_1_design_lock.yaml")
        cls.base_manifest = load_yaml(ROOT / "manifests/examples/milestone_1_demo.yaml")
        cls.stimulus_cases = load_yaml(ROOT / "tests/fixtures/manifest_stimulus_cases.yaml")

    def test_example_manifest_validates_against_schema_and_design_lock(self) -> None:
        summary = validate_manifest(
            manifest_path=ROOT / "manifests/examples/milestone_1_demo.yaml",
            schema_path=ROOT / "schemas/milestone_1_experiment_manifest.schema.json",
            design_lock_path=ROOT / "config/milestone_1_design_lock.yaml",
        )

        self.assertEqual(summary["milestone"], "milestone_1")
        self.assertEqual(summary["comparison_arm_count"], 6)
        self.assertEqual(summary["success_criteria_count"], 5)
        self.assertEqual(summary["stimulus_contract_version"], "stimulus_bundle.v1")
        self.assertEqual(summary["stimulus_bundle_reference"]["stimulus_family"], "translated_edge")
        self.assertEqual(summary["stimulus_bundle_reference"]["stimulus_name"], "simple_translated_edge")
        self.assertEqual(
            summary["stimulus_bundle"]["parameter_hash"],
            summary["resolved_stimulus_parameter_hash"],
        )

    def test_thresholds_remain_intentionally_unspecified(self) -> None:
        design_lock = load_yaml(ROOT / "config/milestone_1_design_lock.yaml")
        for criterion in design_lock["success_criteria"]:
            self.assertIsNone(criterion["metric"]["threshold"])
            self.assertEqual(criterion["metric"]["threshold_status"], "intentionally_unspecified")

    def test_fixture_manifest_resolves_normalized_stimulus_metadata(self) -> None:
        manifest = self._build_manifest_fixture(
            self.stimulus_cases["valid_cases"]["nested_stimulus_overrides"]
        )

        summary = validate_manifest_payload(
            manifest=manifest,
            schema=self.schema,
            design_lock=self.design_lock,
            processed_stimulus_dir=ROOT / "data/processed/test_manifest_stimuli",
        )

        self.assertEqual(summary["resolved_stimulus_family"], "translated_edge")
        self.assertEqual(summary["resolved_stimulus_name"], "simple_translated_edge")
        self.assertEqual(summary["resolved_stimulus"]["determinism"]["seed"], 17)
        self.assertEqual(summary["resolved_stimulus"]["determinism"]["seed_source"], "random_seed")
        self.assertEqual(summary["resolved_stimulus"]["parameter_snapshot"]["background_level"], 0.45)
        self.assertEqual(summary["resolved_stimulus"]["parameter_snapshot"]["velocity_deg_per_s"], 55.0)
        self.assertEqual(summary["resolved_stimulus"]["temporal_sampling"]["frame_count"], 25)
        self.assertEqual(summary["resolved_stimulus"]["spatial_frame"]["width_px"], 64)
        self.assertEqual(summary["stimulus_bundle_reference"]["contract_version"], "stimulus_bundle.v1")
        self.assertEqual(summary["stimulus_bundle_reference"]["parameter_hash"], summary["resolved_stimulus_parameter_hash"])
        self.assertEqual(
            Path(summary["stimulus_bundle_metadata_path"]),
            (
                ROOT
                / "data/processed/test_manifest_stimuli/bundles/translated_edge/simple_translated_edge"
                / summary["resolved_stimulus_parameter_hash"]
                / "stimulus_bundle.json"
            ).resolve(),
        )

    def test_fixture_manifest_invalid_stimulus_references_fail_clearly(self) -> None:
        for case_name, case in self.stimulus_cases["invalid_cases"].items():
            with self.subTest(case=case_name):
                manifest = self._build_manifest_fixture(case)
                with self.assertRaises(ValueError) as ctx:
                    validate_manifest_payload(
                        manifest=manifest,
                        schema=self.schema,
                        design_lock=self.design_lock,
                    )
                self.assertIn(case["error_substring"], str(ctx.exception))

    def test_validation_and_simulation_plan_share_nondefault_processed_stimulus_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            manifest_path = ROOT / "manifests/examples/milestone_1_demo.yaml"
            schema_path = ROOT / "schemas/milestone_1_experiment_manifest.schema.json"
            design_lock_path = ROOT / "config/milestone_1_design_lock.yaml"
            config_path = _write_simulation_fixture(tmp_dir)

            resolved_input = resolve_stimulus_input(
                manifest_path=manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
                processed_stimulus_dir=tmp_dir / "out" / "stimuli",
            )
            recorded_summary = record_stimulus_bundle(resolved_input)
            validation_summary = validate_manifest(
                manifest_path=manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
                config_path=config_path,
            )
            simulation_plan = resolve_manifest_simulation_plan(
                manifest_path=manifest_path,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )

            expected_metadata_path = str(Path(recorded_summary["stimulus_bundle_metadata_path"]).resolve())
            self.assertTrue(
                expected_metadata_path.startswith(str((tmp_dir / "out" / "stimuli").resolve()))
            )
            self.assertEqual(
                validation_summary["stimulus_bundle_metadata_path"],
                expected_metadata_path,
            )
            self.assertEqual(
                validation_summary["stimulus_bundle_reference"]["bundle_id"],
                recorded_summary["stimulus_bundle_id"],
            )
            for arm_plan in simulation_plan["arm_plans"]:
                self.assertEqual(
                    arm_plan["stimulus_reference"],
                    validation_summary["stimulus_bundle_reference"],
                )
                self.assertEqual(
                    arm_plan["input_reference"]["stimulus_bundle_reference"],
                    validation_summary["stimulus_bundle_reference"],
                )
                self.assertEqual(
                    arm_plan["input_reference"]["stimulus_bundle_metadata_path"],
                    expected_metadata_path,
                )

    def _build_manifest_fixture(self, patch: dict[str, object]) -> dict[str, object]:
        manifest = copy.deepcopy(self.base_manifest)
        patch_payload = {key: value for key, value in patch.items() if key != "error_substring"}
        return _deep_merge(manifest, patch_payload)


def _deep_merge(base: dict[str, object], patch: dict[str, object]) -> dict[str, object]:
    for key, value in patch.items():
        current = base.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            base[key] = _deep_merge(dict(current), dict(value))
        else:
            base[key] = value
    return base


if __name__ == "__main__":
    unittest.main()
