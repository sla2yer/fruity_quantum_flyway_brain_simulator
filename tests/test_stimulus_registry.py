from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.config import load_config
from flywire_wave.manifests import load_yaml, validate_manifest
from flywire_wave.stimulus_registry import (
    get_stimulus_registry_entry,
    list_stimulus_families,
    list_stimulus_presets,
    resolve_stimulus_spec,
)


class StimulusRegistryTest(unittest.TestCase):
    def test_reserved_milestone8a_families_and_aliases_are_discoverable(self) -> None:
        families = list_stimulus_families()
        self.assertEqual(
            {item["stimulus_family"] for item in families},
            {
                "flash",
                "moving_bar",
                "drifting_grating",
                "looming",
                "radial_flow",
                "rotating_flow",
                "translated_edge",
            },
        )

        edge_presets = list_stimulus_presets("moving_edge")
        self.assertEqual(len(edge_presets), 1)
        self.assertEqual(edge_presets[0]["stimulus_family"], "translated_edge")
        self.assertEqual(edge_presets[0]["stimulus_name"], "simple_translated_edge")

        edge_entry = get_stimulus_registry_entry("moving_edge", "simple_moving_edge")
        self.assertEqual(edge_entry["stimulus_family"], "translated_edge")
        self.assertEqual(edge_entry["stimulus_name"], "simple_translated_edge")
        self.assertIn("moving_edge", edge_entry["family_aliases"])
        self.assertIn("simple_moving_edge", edge_entry["name_aliases"])
        self.assertIn(
            {
                "stimulus_family": "moving_edge",
                "stimulus_name": "simple_moving_edge",
            },
            edge_entry["compatibility_aliases"],
        )

    def test_fixture_cases_resolve_normalized_specs(self) -> None:
        fixtures = load_yaml(ROOT / "tests/fixtures/stimulus_resolution_cases.yaml")

        flash = resolve_stimulus_spec(fixtures["valid_cases"]["flash_defaults"])
        self.assertEqual(flash.stimulus_spec["stimulus_family"], "flash")
        self.assertEqual(flash.stimulus_spec["stimulus_name"], "simple_flash")
        self.assertEqual(flash.stimulus_spec["temporal_sampling"]["frame_count"], 25)
        self.assertEqual(flash.stimulus_spec["presentation"]["background_level"], 0.5)
        self.assertEqual(flash.stimulus_spec["determinism"]["seed"], 0)
        self.assertEqual(flash.stimulus_spec["determinism"]["seed_source"], "preset_default")
        self.assertEqual(
            flash.registry_entry["default_luminance_convention"]["contrast_semantics"],
            "signed_delta_from_neutral_gray",
        )

        moving_edge = resolve_stimulus_spec(fixtures["valid_cases"]["moving_edge_manifest_compat"])
        self.assertEqual(moving_edge.stimulus_spec["stimulus_family"], "translated_edge")
        self.assertEqual(moving_edge.stimulus_spec["stimulus_name"], "simple_translated_edge")
        self.assertTrue(moving_edge.stimulus_spec["compatibility"]["family_alias_used"])
        self.assertTrue(moving_edge.stimulus_spec["compatibility"]["name_alias_used"])
        self.assertEqual(moving_edge.stimulus_spec["determinism"]["seed"], 11)
        self.assertEqual(moving_edge.stimulus_spec["spatial_frame"]["width_px"], 96)
        self.assertEqual(moving_edge.stimulus_spec["spatial_frame"]["height_px"], 48)

        grating = resolve_stimulus_spec(fixtures["valid_cases"]["grating_override_aliases"])
        self.assertEqual(grating.stimulus_spec["stimulus_family"], "drifting_grating")
        self.assertEqual(grating.stimulus_spec["parameter_snapshot"]["spatial_frequency_cpd"], 0.12)
        self.assertEqual(grating.stimulus_spec["parameter_snapshot"]["temporal_frequency_hz"], 3.0)
        self.assertEqual(grating.stimulus_spec["parameter_snapshot"]["phase_deg"], 180.0)
        self.assertEqual(grating.stimulus_spec["temporal_sampling"]["frame_count"], 20)
        self.assertEqual(grating.stimulus_spec["spatial_frame"]["width_px"], 64)
        self.assertEqual(grating.stimulus_spec["spatial_frame"]["height_px"], 64)

        rotating_flow = resolve_stimulus_spec(fixtures["valid_cases"]["rotating_flow_alias_and_seed"])
        self.assertEqual(rotating_flow.stimulus_spec["stimulus_family"], "rotating_flow")
        self.assertEqual(rotating_flow.stimulus_spec["stimulus_name"], "clockwise_rotation")
        self.assertTrue(rotating_flow.stimulus_spec["compatibility"]["name_alias_used"])
        self.assertEqual(rotating_flow.stimulus_spec["determinism"]["seed"], 5)
        self.assertEqual(
            rotating_flow.stimulus_spec["parameter_snapshot"]["angular_velocity_deg_per_s"],
            120.0,
        )

    def test_fixture_invalid_cases_fail_clearly(self) -> None:
        fixtures = load_yaml(ROOT / "tests/fixtures/stimulus_resolution_cases.yaml")
        for case_name, case in fixtures["invalid_cases"].items():
            with self.subTest(case=case_name):
                with self.assertRaises(ValueError) as ctx:
                    resolve_stimulus_spec(case)
                self.assertIn(case["error_substring"], str(ctx.exception))

    def test_load_config_normalizes_fixture_stimulus_section(self) -> None:
        cfg = load_config(
            ROOT / "tests/fixtures/stimulus_config_fixture.yaml",
            project_root=ROOT,
        )

        self.assertEqual(cfg["stimulus"]["stimulus_family"], "translated_edge")
        self.assertEqual(cfg["stimulus"]["stimulus_name"], "simple_translated_edge")
        self.assertEqual(cfg["stimulus"]["determinism"]["seed"], 17)
        self.assertEqual(cfg["stimulus"]["parameter_snapshot"]["background_level"], 0.45)
        self.assertEqual(cfg["stimulus"]["parameter_snapshot"]["velocity_deg_per_s"], 55.0)
        self.assertEqual(cfg["stimulus_registry_entry"]["stimulus_family"], "translated_edge")
        self.assertEqual(cfg["stimulus_registry_entry"]["stimulus_name"], "simple_translated_edge")
        self.assertEqual(cfg["stimulus_contract"]["version"], "stimulus_bundle.v1")
        self.assertEqual(cfg["stimulus_bundle_reference"]["contract_version"], "stimulus_bundle.v1")
        self.assertEqual(
            cfg["stimulus_bundle_reference"]["parameter_hash"],
            cfg["stimulus"]["parameter_hash"],
        )
        self.assertEqual(
            Path(cfg["stimulus_bundle_metadata_path"]),
            (
                ROOT
                / "data/processed/test_stimuli/bundles/translated_edge/simple_translated_edge"
                / cfg["stimulus"]["parameter_hash"]
                / "stimulus_bundle.json"
            ).resolve(),
        )

    def test_manifest_validation_resolves_milestone1_stimulus_compatibly(self) -> None:
        summary = validate_manifest(
            manifest_path=ROOT / "manifests/examples/milestone_1_demo.yaml",
            schema_path=ROOT / "schemas/milestone_1_experiment_manifest.schema.json",
            design_lock_path=ROOT / "config/milestone_1_design_lock.yaml",
        )

        self.assertEqual(summary["resolved_stimulus_family"], "translated_edge")
        self.assertEqual(summary["resolved_stimulus_name"], "simple_translated_edge")
        self.assertTrue(summary["resolved_stimulus_parameter_hash"])
        self.assertEqual(summary["stimulus_bundle_reference"]["contract_version"], "stimulus_bundle.v1")


if __name__ == "__main__":
    unittest.main()
