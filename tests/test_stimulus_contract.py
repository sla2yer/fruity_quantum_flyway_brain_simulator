from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.stimulus_contract import (
    ASSET_STATUS_MISSING,
    ASSET_STATUS_READY,
    DEFAULT_REPRESENTATION_FAMILY,
    FRAME_CACHE_KEY,
    METADATA_JSON_KEY,
    PREVIEW_GIF_KEY,
    STIMULUS_BUNDLE_CONTRACT_VERSION,
    STIMULUS_BUNDLE_DESIGN_NOTE,
    build_stimulus_bundle_metadata,
    build_stimulus_bundle_paths,
    build_stimulus_contract_manifest_metadata,
    discover_stimulus_alias_paths,
    discover_stimulus_bundle_paths,
    load_stimulus_alias_record,
    load_stimulus_bundle_metadata,
    resolve_stimulus_bundle_metadata_path,
    write_stimulus_bundle_metadata,
)


class StimulusContractTest(unittest.TestCase):
    def test_bundle_paths_are_deterministic(self) -> None:
        parameter_hash = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        bundle_paths = build_stimulus_bundle_paths(
            stimulus_family="moving_edge",
            stimulus_name="simple_moving_edge",
            processed_stimulus_dir=ROOT / "data" / "processed" / "stimuli",
            parameter_hash=parameter_hash,
        )

        expected_bundle_dir = (
            ROOT
            / "data"
            / "processed"
            / "stimuli"
            / "bundles"
            / "moving_edge"
            / "simple_moving_edge"
            / parameter_hash
        ).resolve()
        self.assertEqual(bundle_paths.bundle_directory, expected_bundle_dir)
        self.assertEqual(bundle_paths.metadata_json_path, expected_bundle_dir / "stimulus_bundle.json")
        self.assertEqual(bundle_paths.frame_cache_path, expected_bundle_dir / "stimulus_frames.npz")
        self.assertEqual(bundle_paths.preview_gif_path, expected_bundle_dir / "stimulus_preview.gif")
        self.assertEqual(
            bundle_paths.bundle_id,
            f"{STIMULUS_BUNDLE_CONTRACT_VERSION}:moving_edge:simple_moving_edge:{parameter_hash}",
        )

    def test_fixture_bundle_metadata_serializes_deterministically_and_resolves_aliases(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            stimulus_dir = Path(tmp_dir_str) / "stimuli"
            temporal_sampling = {
                "dt_ms": 10.0,
                "duration_ms": 400.0,
                "frame_count": 40,
            }
            spatial_frame = {
                "width_px": 96,
                "height_px": 48,
                "width_deg": 120.0,
                "height_deg": 60.0,
            }
            parameter_snapshot_a = {
                "contrast": 0.6,
                "edge_width_deg": 8.0,
                "velocity_deg_per_s": 45.0,
                "phase_offsets_deg": [0.0, 90.0],
                "aperture": {
                    "soften_deg": 2.0,
                    "shape": "ellipse",
                },
            }
            parameter_snapshot_b = {
                "aperture": {
                    "shape": "ellipse",
                    "soften_deg": 2.0,
                },
                "phase_offsets_deg": [0.0, 90.0],
                "velocity_deg_per_s": 45.0,
                "edge_width_deg": 8.0,
                "contrast": 0.6,
            }

            metadata_a = build_stimulus_bundle_metadata(
                stimulus_family="moving_edge",
                stimulus_name="simple_moving_edge",
                parameter_snapshot=parameter_snapshot_a,
                seed=11,
                temporal_sampling=temporal_sampling,
                spatial_frame=spatial_frame,
                processed_stimulus_dir=stimulus_dir,
                frame_cache_status=ASSET_STATUS_READY,
                preview_gif_status=ASSET_STATUS_MISSING,
                compatibility_aliases=[
                    {
                        "stimulus_family": "legacy_edge",
                        "stimulus_name": "simple_edge_v0",
                    }
                ],
            )
            metadata_b = build_stimulus_bundle_metadata(
                stimulus_family="moving_edge",
                stimulus_name="simple_moving_edge",
                parameter_snapshot=parameter_snapshot_b,
                seed=11,
                temporal_sampling=temporal_sampling,
                spatial_frame=spatial_frame,
                processed_stimulus_dir=stimulus_dir,
                frame_cache_status=ASSET_STATUS_READY,
                preview_gif_status=ASSET_STATUS_MISSING,
                compatibility_aliases=[
                    {
                        "stimulus_family": "legacy_edge",
                        "stimulus_name": "simple_edge_v0",
                    }
                ],
            )
            manifest_metadata = build_stimulus_contract_manifest_metadata(
                processed_stimulus_dir=stimulus_dir
            )

            self.assertEqual(metadata_a, metadata_b)
            self.assertEqual(metadata_a["contract_version"], STIMULUS_BUNDLE_CONTRACT_VERSION)
            self.assertEqual(metadata_a["design_note"], STIMULUS_BUNDLE_DESIGN_NOTE)
            self.assertEqual(metadata_a["representation_family"], DEFAULT_REPRESENTATION_FAMILY)
            self.assertEqual(metadata_a["determinism"]["seed"], 11)
            self.assertEqual(metadata_a["temporal_sampling"]["frame_count"], 40)
            self.assertEqual(metadata_a["spatial_frame"]["frame_name"], "visual_field_degrees_centered")
            self.assertEqual(
                metadata_a["luminance_convention"]["contrast_semantics"],
                "signed_delta_from_neutral_gray",
            )
            self.assertEqual(manifest_metadata["version"], STIMULUS_BUNDLE_CONTRACT_VERSION)
            self.assertEqual(manifest_metadata["design_note"], STIMULUS_BUNDLE_DESIGN_NOTE)
            self.assertEqual(manifest_metadata["default_representation_family"], DEFAULT_REPRESENTATION_FAMILY)

            metadata_path = write_stimulus_bundle_metadata(metadata_a)
            loaded_metadata = load_stimulus_bundle_metadata(metadata_path)
            discovered_paths = discover_stimulus_bundle_paths(metadata_a)
            alias_paths = discover_stimulus_alias_paths(metadata_a)

            self.assertEqual(loaded_metadata, metadata_a)
            self.assertEqual(discovered_paths[METADATA_JSON_KEY], metadata_path.resolve())
            self.assertEqual(
                discovered_paths[FRAME_CACHE_KEY],
                Path(metadata_a["assets"][FRAME_CACHE_KEY]["path"]).resolve(),
            )
            self.assertEqual(
                discovered_paths[PREVIEW_GIF_KEY],
                Path(metadata_a["assets"][PREVIEW_GIF_KEY]["path"]).resolve(),
            )
            self.assertEqual(len(alias_paths), 1)
            alias_record = load_stimulus_alias_record(alias_paths[0])
            self.assertEqual(alias_record["bundle_metadata_path"], str(metadata_path.resolve()))
            self.assertEqual(alias_record["parameter_hash"], metadata_a["parameter_hash"])

            resolved_metadata_path = resolve_stimulus_bundle_metadata_path(
                stimulus_family="legacy_edge",
                stimulus_name="simple_edge_v0",
                processed_stimulus_dir=stimulus_dir,
                parameter_snapshot=parameter_snapshot_b,
                seed=11,
                temporal_sampling=temporal_sampling,
                spatial_frame=spatial_frame,
            )
            self.assertEqual(resolved_metadata_path, metadata_path.resolve())

            serialized = json.dumps(metadata_a, indent=2, sort_keys=True)
            self.assertEqual(metadata_path.read_text(encoding="utf-8"), serialized)


if __name__ == "__main__":
    unittest.main()
