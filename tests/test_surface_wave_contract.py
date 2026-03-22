from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.surface_wave_contract import (
    DEFAULT_SURFACE_WAVE_MODEL_FAMILY,
    HYBRID_DAMPED_WAVE_RECOVERY_MODEL_FAMILY,
    METADATA_JSON_KEY,
    SELECTED_ROADMAP_MODEL_FAMILY,
    SURFACE_WAVE_MODEL_CONTRACT_VERSION,
    SURFACE_WAVE_MODEL_DESIGN_NOTE,
    SURFACE_WAVE_PARAMETER_SCHEMA_VERSION,
    build_surface_wave_contract_manifest_metadata,
    build_surface_wave_model_metadata,
    build_surface_wave_model_paths,
    build_surface_wave_model_reference,
    discover_surface_wave_model_paths,
    load_surface_wave_model_metadata,
    resolve_surface_wave_model_metadata_path,
    write_surface_wave_model_metadata,
)


class SurfaceWaveContractTest(unittest.TestCase):
    def test_bundle_paths_are_deterministic(self) -> None:
        parameter_hash = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        bundle_paths = build_surface_wave_model_paths(
            model_family="Hybrid_Damped_Wave_Recovery",
            processed_surface_wave_dir=ROOT / "data" / "processed" / "surface_wave_models",
            parameter_hash=parameter_hash,
        )

        expected_bundle_dir = (
            ROOT
            / "data"
            / "processed"
            / "surface_wave_models"
            / "bundles"
            / HYBRID_DAMPED_WAVE_RECOVERY_MODEL_FAMILY
            / parameter_hash
        ).resolve()
        self.assertEqual(bundle_paths.bundle_directory, expected_bundle_dir)
        self.assertEqual(
            bundle_paths.metadata_json_path,
            expected_bundle_dir / "surface_wave_model.json",
        )
        self.assertEqual(
            bundle_paths.bundle_id,
            (
                f"{SURFACE_WAVE_MODEL_CONTRACT_VERSION}:"
                f"{HYBRID_DAMPED_WAVE_RECOVERY_MODEL_FAMILY}:{parameter_hash}"
            ),
        )

    def test_fixture_wave_model_metadata_serializes_deterministically_and_discovers_bundle(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            surface_wave_dir = Path(tmp_dir_str) / "surface_wave_models"
            parameter_bundle_a = {
                "parameter_preset": "m10_fixture_profile",
                "propagation": {
                    "wave_speed_sq_scale": 1.3,
                    "restoring_strength_per_ms2": 0.08,
                },
                "damping": {
                    "gamma_per_ms": 0.17,
                },
                "recovery": {
                    "mode": "activity_driven_first_order",
                    "time_constant_ms": 18.0,
                    "drive_gain": 0.35,
                    "coupling_strength_per_ms2": 0.14,
                    "baseline": 0.0,
                    "drive_semantics": "positive_surface_activation",
                },
                "nonlinearity": {
                    "mode": "tanh_soft_clip",
                    "activation_scale": 1.25,
                },
                "anisotropy": {
                    "mode": "operator_embedded",
                    "strength_scale": 1.2,
                },
                "branching": {
                    "mode": "descriptor_scaled_damping",
                    "gain": 0.18,
                    "junction_response": "extra_local_damping",
                },
            }
            parameter_bundle_b = {
                "branching": {
                    "junction_response": "extra_local_damping",
                    "gain": 0.18,
                    "mode": "descriptor_scaled_damping",
                },
                "anisotropy": {
                    "strength_scale": 1.2,
                    "mode": "operator_embedded",
                },
                "nonlinearity": {
                    "activation_scale": 1.25,
                    "mode": "tanh_soft_clip",
                },
                "damping": {
                    "gamma_per_ms": 0.17,
                },
                "parameter_preset": "m10_fixture_profile",
                "recovery": {
                    "drive_semantics": "positive_surface_activation",
                    "baseline": 0.0,
                    "coupling_strength_per_ms2": 0.14,
                    "drive_gain": 0.35,
                    "time_constant_ms": 18.0,
                    "mode": "activity_driven_first_order",
                },
                "propagation": {
                    "restoring_strength_per_ms2": 0.08,
                    "wave_speed_sq_scale": 1.3,
                },
            }

            metadata_a = build_surface_wave_model_metadata(
                processed_surface_wave_dir=surface_wave_dir,
                parameter_bundle=parameter_bundle_a,
            )
            metadata_b = build_surface_wave_model_metadata(
                processed_surface_wave_dir=surface_wave_dir,
                parameter_bundle=parameter_bundle_b,
            )
            contract_manifest_metadata = build_surface_wave_contract_manifest_metadata(
                processed_surface_wave_dir=surface_wave_dir
            )

            self.assertEqual(metadata_a, metadata_b)
            self.assertEqual(
                metadata_a["contract_version"],
                SURFACE_WAVE_MODEL_CONTRACT_VERSION,
            )
            self.assertEqual(
                metadata_a["parameter_schema_version"],
                SURFACE_WAVE_PARAMETER_SCHEMA_VERSION,
            )
            self.assertEqual(metadata_a["design_note"], SURFACE_WAVE_MODEL_DESIGN_NOTE)
            self.assertEqual(
                metadata_a["model_family"],
                DEFAULT_SURFACE_WAVE_MODEL_FAMILY,
            )
            self.assertEqual(
                metadata_a["roadmap_model_family"],
                SELECTED_ROADMAP_MODEL_FAMILY,
            )
            self.assertEqual(
                metadata_a["solver_family"],
                "semi_implicit_velocity_split",
            )
            self.assertEqual(
                metadata_a["recovery_mode"],
                "activity_driven_first_order",
            )
            self.assertEqual(metadata_a["nonlinearity_mode"], "tanh_soft_clip")
            self.assertEqual(metadata_a["anisotropy_mode"], "operator_embedded")
            self.assertEqual(
                metadata_a["branching_mode"],
                "descriptor_scaled_damping",
            )
            self.assertEqual(
                metadata_a["parameter_bundle"]["synaptic_source"]["readout_state"],
                "surface_activation",
            )
            self.assertEqual(
                metadata_a["state_variables"][0]["state_id"],
                "surface_activation",
            )
            self.assertEqual(contract_manifest_metadata["version"], SURFACE_WAVE_MODEL_CONTRACT_VERSION)
            self.assertEqual(
                contract_manifest_metadata["parameter_schema_version"],
                SURFACE_WAVE_PARAMETER_SCHEMA_VERSION,
            )
            self.assertEqual(
                contract_manifest_metadata["selected_roadmap_model_family"],
                SELECTED_ROADMAP_MODEL_FAMILY,
            )
            self.assertEqual(
                contract_manifest_metadata["default_model_family"],
                DEFAULT_SURFACE_WAVE_MODEL_FAMILY,
            )

            metadata_path = write_surface_wave_model_metadata(metadata_a)
            loaded_metadata = load_surface_wave_model_metadata(metadata_path)
            discovered_paths = discover_surface_wave_model_paths(metadata_a)
            nested_discovered_paths = discover_surface_wave_model_paths(
                {"surface_wave_model": metadata_a}
            )
            reference = build_surface_wave_model_reference(metadata_a)

            self.assertEqual(loaded_metadata, metadata_a)
            self.assertEqual(discovered_paths[METADATA_JSON_KEY], metadata_path.resolve())
            self.assertEqual(nested_discovered_paths, discovered_paths)
            self.assertEqual(reference["contract_version"], SURFACE_WAVE_MODEL_CONTRACT_VERSION)
            self.assertEqual(reference["model_family"], DEFAULT_SURFACE_WAVE_MODEL_FAMILY)
            self.assertEqual(reference["parameter_hash"], metadata_a["parameter_hash"])

            resolved_metadata_path = resolve_surface_wave_model_metadata_path(
                processed_surface_wave_dir=surface_wave_dir,
                parameter_bundle=parameter_bundle_b,
            )
            self.assertEqual(resolved_metadata_path, metadata_path.resolve())

            serialized = json.dumps(metadata_a, indent=2, sort_keys=True)
            self.assertEqual(metadata_path.read_text(encoding="utf-8"), serialized)

    def test_active_mode_guardrails_fail_clearly(self) -> None:
        with self.assertRaises(ValueError) as recovery_ctx:
            build_surface_wave_model_metadata(
                parameter_bundle={
                    "recovery": {
                        "mode": "activity_driven_first_order",
                        "drive_gain": 0.0,
                        "coupling_strength_per_ms2": 0.12,
                    }
                }
            )
        self.assertIn(
            "surface_wave.recovery.drive_gain must be positive",
            str(recovery_ctx.exception),
        )

        with self.assertRaises(ValueError) as branching_ctx:
            build_surface_wave_model_metadata(
                parameter_bundle={
                    "branching": {
                        "mode": "descriptor_scaled_damping",
                        "gain": 0.0,
                    }
                }
            )
        self.assertIn(
            "surface_wave.branching.gain must be positive",
            str(branching_ctx.exception),
        )


if __name__ == "__main__":
    unittest.main()
