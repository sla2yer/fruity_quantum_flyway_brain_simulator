from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.retinal_contract import (
    ASSET_STATUS_MISSING,
    ASSET_STATUS_READY,
    DEFAULT_RETINAL_REPRESENTATION_FAMILY,
    FRAME_ARCHIVE_KEY,
    METADATA_JSON_KEY,
    RETINAL_BUNDLE_DESIGN_NOTE,
    RETINAL_INPUT_BUNDLE_CONTRACT_VERSION,
    build_retinal_bundle_metadata,
    build_retinal_bundle_paths,
    build_retinal_contract_manifest_metadata,
    build_retinal_source_reference,
    discover_retinal_bundle_paths,
    load_retinal_bundle_metadata,
    resolve_retinal_bundle_metadata_path,
    write_retinal_bundle_metadata,
)
from flywire_wave.retinal_geometry import DEFAULT_GEOMETRY_FAMILY, FIXTURE_GEOMETRY_NAME


class RetinalContractTest(unittest.TestCase):
    def test_bundle_paths_are_deterministic(self) -> None:
        source_reference = build_retinal_source_reference(
            source_kind="stimulus_bundle",
            source_contract_version="stimulus_bundle.v1",
            source_family="translated_edge",
            source_name="simple_translated_edge",
            source_id=(
                "stimulus_bundle.v1:translated_edge:simple_translated_edge:"
                "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            ),
            source_hash="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        )
        retinal_spec_hash = "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
        bundle_paths = build_retinal_bundle_paths(
            source_reference=source_reference,
            processed_retinal_dir=ROOT / "data" / "processed" / "retinal",
            retinal_spec_hash=retinal_spec_hash,
        )

        expected_bundle_dir = (
            ROOT
            / "data"
            / "processed"
            / "retinal"
            / "bundles"
            / "stimulus_bundle"
            / "translated_edge"
            / "simple_translated_edge"
            / "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            / retinal_spec_hash
        ).resolve()
        self.assertEqual(bundle_paths.bundle_directory, expected_bundle_dir)
        self.assertEqual(bundle_paths.metadata_json_path, expected_bundle_dir / "retinal_input_bundle.json")
        self.assertEqual(bundle_paths.frame_archive_path, expected_bundle_dir / "retinal_frames.npz")
        self.assertEqual(
            bundle_paths.bundle_id,
            (
                "retinal_input_bundle.v1:stimulus_bundle:translated_edge:simple_translated_edge:"
                "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef:"
                f"{retinal_spec_hash}"
            ),
        )

    def test_fixture_retinal_metadata_serializes_deterministically_and_discovers_bundle(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            retinal_dir = Path(tmp_dir_str) / "retinal"
            source_reference = build_retinal_source_reference(
                source_kind="stimulus_bundle",
                source_contract_version="stimulus_bundle.v1",
                source_family="translated_edge",
                source_name="simple_translated_edge",
                source_id=(
                    "stimulus_bundle.v1:translated_edge:simple_translated_edge:"
                    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
                ),
                source_hash="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            )
            eye_sampling_a = {
                "geometry_family": "ommatidial_lattice",
                "geometry_name": "fixture",
            }
            eye_sampling_b = {
                "geometry_family": "compound_eye_geometry",
                "geometry_name": "fixture_hex_19",
            }
            temporal_sampling = {
                "dt_ms": 10.0,
                "duration_ms": 100.0,
                "frame_count": 10,
            }
            sampling_kernel = {
                "kernel_family": "gaussian_acceptance_weighted_mean",
                "acceptance_angle_deg": 4.5,
                "support_radius_deg": 9.0,
                "background_fill_value": 0.5,
            }

            metadata_a = build_retinal_bundle_metadata(
                source_reference=source_reference,
                eye_sampling=eye_sampling_a,
                temporal_sampling=temporal_sampling,
                sampling_kernel=sampling_kernel,
                processed_retinal_dir=retinal_dir,
                frame_archive_status=ASSET_STATUS_MISSING,
            )
            metadata_b = build_retinal_bundle_metadata(
                source_reference=source_reference,
                eye_sampling=eye_sampling_b,
                temporal_sampling=temporal_sampling,
                sampling_kernel=sampling_kernel,
                processed_retinal_dir=retinal_dir,
                frame_archive_status=ASSET_STATUS_MISSING,
            )
            manifest_metadata = build_retinal_contract_manifest_metadata(
                processed_retinal_dir=retinal_dir
            )

            self.assertEqual(metadata_a, metadata_b)
            self.assertEqual(metadata_a["contract_version"], RETINAL_INPUT_BUNDLE_CONTRACT_VERSION)
            self.assertEqual(metadata_a["design_note"], RETINAL_BUNDLE_DESIGN_NOTE)
            self.assertEqual(
                metadata_a["representation_family"],
                DEFAULT_RETINAL_REPRESENTATION_FAMILY,
            )
            self.assertEqual(metadata_a["source_reference"]["source_kind"], "stimulus_bundle")
            self.assertEqual(metadata_a["eye_sampling"]["geometry_family"], DEFAULT_GEOMETRY_FAMILY)
            self.assertEqual(metadata_a["eye_sampling"]["geometry_name"], FIXTURE_GEOMETRY_NAME)
            self.assertEqual(metadata_a["eye_sampling"]["eye_order"], ["left", "right"])
            self.assertEqual(metadata_a["eye_sampling"]["ommatidium_count_per_eye"], 19)
            self.assertEqual(metadata_a["eye_sampling"]["lattice"]["ring_count"], 2)
            self.assertEqual(metadata_a["eye_sampling"]["lattice_indexing"]["ring_detector_counts"], [1, 6, 12])
            self.assertEqual(
                len(metadata_a["eye_sampling"]["per_eye"]["left"]["detector_table"]),
                19,
            )
            self.assertEqual(metadata_a["frame_layout"]["layout"], "dense_t_eye_ommatidium")
            self.assertEqual(
                metadata_a["frame_layout"]["value_semantics"],
                "per_ommatidium_linear_irradiance",
            )
            self.assertEqual(
                metadata_a["simulator_input"]["representation"],
                "early_visual_unit_stack",
            )
            self.assertEqual(
                metadata_a["simulator_input"]["layout"],
                "dense_t_eye_unit_channel",
            )
            self.assertEqual(
                metadata_a["simulator_input"]["channel_order"],
                ["irradiance"],
            )
            self.assertEqual(
                metadata_a["simulator_input"]["mapping"]["mapping_family"],
                "identity_per_ommatidium",
            )
            self.assertEqual(
                metadata_a["simulator_input"]["mapping"]["per_eye_unit_tables"]["left"][0][
                    "source_ommatidium_index"
                ],
                0,
            )
            self.assertEqual(metadata_a["temporal_sampling"]["frame_count"], 10)
            self.assertEqual(
                metadata_a["sampling_kernel"]["kernel_family"],
                "gaussian_acceptance_weighted_mean",
            )
            self.assertEqual(
                metadata_a["signal_convention"]["encoding"],
                "linear_irradiance_unit_interval",
            )
            self.assertEqual(manifest_metadata["version"], RETINAL_INPUT_BUNDLE_CONTRACT_VERSION)
            self.assertEqual(manifest_metadata["design_note"], RETINAL_BUNDLE_DESIGN_NOTE)
            self.assertEqual(
                manifest_metadata["default_representation_family"],
                DEFAULT_RETINAL_REPRESENTATION_FAMILY,
            )
            self.assertEqual(manifest_metadata["default_geometry_family"], DEFAULT_GEOMETRY_FAMILY)
            self.assertEqual(manifest_metadata["default_geometry_name"], "canonical_hex_91")
            self.assertEqual(
                manifest_metadata["supported_representation_families"],
                [DEFAULT_RETINAL_REPRESENTATION_FAMILY],
            )
            self.assertEqual(
                manifest_metadata["default_simulator_input_representation"],
                "early_visual_unit_stack",
            )
            self.assertEqual(
                manifest_metadata["default_simulator_mapping_family"],
                "identity_per_ommatidium",
            )

            metadata_path = write_retinal_bundle_metadata(metadata_a)
            loaded_metadata = load_retinal_bundle_metadata(metadata_path)
            discovered_paths = discover_retinal_bundle_paths(metadata_a)
            nested_discovered_paths = discover_retinal_bundle_paths({"retinal_bundle": metadata_a})

            self.assertEqual(loaded_metadata, metadata_a)
            self.assertEqual(discovered_paths[METADATA_JSON_KEY], metadata_path.resolve())
            self.assertEqual(
                discovered_paths[FRAME_ARCHIVE_KEY],
                Path(metadata_a["assets"][FRAME_ARCHIVE_KEY]["path"]).resolve(),
            )
            self.assertEqual(nested_discovered_paths, discovered_paths)

            resolved_metadata_path = resolve_retinal_bundle_metadata_path(
                source_reference=source_reference,
                processed_retinal_dir=retinal_dir,
                eye_sampling=eye_sampling_b,
                temporal_sampling=temporal_sampling,
                sampling_kernel=sampling_kernel,
            )
            self.assertEqual(resolved_metadata_path, metadata_path.resolve())

            serialized = json.dumps(metadata_a, indent=2, sort_keys=True)
            self.assertEqual(metadata_path.read_text(encoding="utf-8"), serialized)


if __name__ == "__main__":
    unittest.main()
