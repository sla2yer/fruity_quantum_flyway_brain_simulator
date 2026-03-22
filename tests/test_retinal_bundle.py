from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.retinal_bundle import (
    FRAME_ARCHIVE_REPLAY_SOURCE,
    RETINAL_FRAME_ARCHIVE_VERSION,
    load_recorded_retinal_bundle,
    record_retinal_bundle,
)
from flywire_wave.retinal_geometry import resolve_retinal_geometry_spec
from flywire_wave.retinal_sampling import AnalyticVisualFieldSource, project_visual_source
from flywire_wave.stimulus_generators import synthesize_stimulus


class RetinalBundleWorkflowTest(unittest.TestCase):
    def test_record_and_load_constant_retinal_bundle_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            geometry = _build_forward_fixture_geometry()
            source = AnalyticVisualFieldSource(
                source_family="fixture_scene",
                source_name="constant_half",
                width_deg=240.0,
                height_deg=180.0,
                source_metadata={"scene_rule": "constant_scalar_field"},
                field_sampler=lambda time_ms, azimuth_deg, elevation_deg: 0.35,
            )
            projection = project_visual_source(
                retinal_geometry=geometry,
                visual_source=source,
                frame_times_ms=[0.0, 10.0, 20.0],
                sampling_kernel={
                    "acceptance_angle_deg": 1.5,
                    "support_radius_deg": 3.0,
                    "background_fill_value": 0.35,
                },
            )

            first = record_retinal_bundle(
                projection_result=projection,
                processed_retinal_dir=tmp_dir / "retinal",
            )
            metadata_path = Path(first["retinal_bundle_metadata_path"])
            archive_path = Path(first["frame_archive_path"])
            first_metadata_text = metadata_path.read_text(encoding="utf-8")
            first_archive_bytes = archive_path.read_bytes()

            second = record_retinal_bundle(
                projection_result=projection,
                processed_retinal_dir=tmp_dir / "retinal",
            )

            self.assertEqual(
                second["retinal_bundle_metadata_path"],
                first["retinal_bundle_metadata_path"],
            )
            self.assertEqual(second["frame_archive_path"], first["frame_archive_path"])
            self.assertEqual(metadata_path.read_text(encoding="utf-8"), first_metadata_text)
            self.assertEqual(archive_path.read_bytes(), first_archive_bytes)

            replay = load_recorded_retinal_bundle(metadata_path)
            self.assertEqual(replay.replay_source, FRAME_ARCHIVE_REPLAY_SOURCE)
            self.assertEqual(
                replay.bundle_metadata["recording"]["frame_archive_version"],
                RETINAL_FRAME_ARCHIVE_VERSION,
            )
            self.assertEqual(
                replay.bundle_metadata["simulator_input"]["channel_order"],
                ["irradiance"],
            )
            self.assertEqual(
                replay.bundle_metadata["simulator_input"]["mapping"]["identity_rule"],
                "unit_index_matches_source_ommatidium_index",
            )
            self.assertEqual(
                replay.bundle_metadata["simulator_input"]["mapping"]["per_eye_unit_tables"]["left"][0][
                    "source_ommatidium_index"
                ],
                0,
            )
            self.assertEqual(replay.bundle_metadata["source_reference"]["source_kind"], "fixture_scene")
            self.assertEqual(len(replay.bundle_metadata["source_reference"]["source_hash"]), 64)

            np.testing.assert_allclose(replay.retinal_frames, 0.35, atol=1.0e-7)
            np.testing.assert_allclose(
                replay.early_visual_units[..., 0],
                replay.retinal_frames,
                atol=0.0,
                rtol=0.0,
            )
            np.testing.assert_allclose(replay.retinal_frames[0], replay.retinal_frames[1], atol=0.0, rtol=0.0)

            frame = replay.frame_at_time_ms(15.0)
            self.assertEqual(frame.frame_index, 1)
            self.assertAlmostEqual(frame.time_ms, 10.0)
            np.testing.assert_allclose(frame.early_visual_frame[..., 0], frame.retinal_frame, atol=0.0, rtol=0.0)

    def test_motion_onset_bundle_keeps_mapping_fixed_while_values_change(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            geometry = _build_forward_fixture_geometry()
            stimulus = synthesize_stimulus(
                stimulus_family="translated_edge",
                stimulus_name="simple_translated_edge",
                overrides={
                    "onset_ms": 50.0,
                    "offset_ms": 120.0,
                    "background_level": 0.2,
                    "contrast": 0.6,
                    "velocity_deg_per_s": 45.0,
                    "edge_width_deg": 8.0,
                },
            )
            projection = project_visual_source(
                retinal_geometry=geometry,
                visual_source=stimulus,
                frame_times_ms=[40.0, 60.0],
                sampling_kernel={
                    "acceptance_angle_deg": 0.25,
                    "support_radius_deg": 0.5,
                    "background_fill_value": 0.5,
                },
            )
            summary = record_retinal_bundle(
                projection_result=projection,
                processed_retinal_dir=tmp_dir / "retinal",
            )
            replay = load_recorded_retinal_bundle(summary["retinal_bundle_metadata_path"])
            before = replay.frame_at_time_ms(40.0)
            after = replay.frame_at_time_ms(60.0)

            self.assertEqual(replay.retinal_frames.shape, (2, 2, 19))
            self.assertEqual(replay.early_visual_units.shape, (2, 2, 19, 1))
            self.assertEqual(
                replay.bundle_metadata["simulator_input"]["mapping"]["per_eye_unit_tables"]["left"][5][
                    "source_ommatidium_index"
                ],
                5,
            )
            self.assertEqual(
                replay.bundle_metadata["simulator_input"]["mapping"]["per_eye_unit_tables"]["right"][5][
                    "source_ommatidium_index"
                ],
                5,
            )

            self.assertAlmostEqual(
                float(np.max(before.retinal_frame) - np.min(before.retinal_frame)),
                0.0,
                places=7,
            )
            self.assertGreater(
                float(np.max(after.retinal_frame) - np.min(after.retinal_frame)),
                1.0e-3,
            )
            np.testing.assert_allclose(
                after.early_visual_frame[..., 0],
                after.retinal_frame,
                atol=0.0,
                rtol=0.0,
            )
            np.testing.assert_allclose(
                before.retinal_frame[0],
                before.retinal_frame[1],
                atol=1.0e-7,
            )
            np.testing.assert_allclose(
                after.retinal_frame[0],
                after.retinal_frame[1],
                atol=1.0e-7,
            )
            self.assertEqual(
                replay.bundle_metadata["source_reference"]["source_kind"],
                "stimulus_bundle",
            )


def _build_forward_fixture_geometry():
    return resolve_retinal_geometry_spec(
        {
            "retinal_geometry": {
                "geometry_name": "fixture",
                "eyes": {
                    "left": {
                        "optical_axis_head": [1.0, 0.0, 0.0],
                        "torsion_deg": 0.0,
                    },
                    "symmetry": {
                        "mode": "mirror_across_head_sagittal_plane",
                    },
                },
            }
        }
    )


if __name__ == "__main__":
    unittest.main()
