from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.retinal_geometry import resolve_retinal_geometry_spec
from flywire_wave.retinal_sampling import (
    GAUSSIAN_ACCEPTANCE_ANGLE_SEMANTICS,
    AnalyticVisualFieldSource,
    RetinalProjector,
)
from flywire_wave.stimulus_generators import synthesize_stimulus


class RetinalSamplingTest(unittest.TestCase):
    def test_fixture_visual_field_projects_deterministically_and_clips_out_of_field_support(self) -> None:
        geometry = _build_forward_fixture_geometry()
        source = AnalyticVisualFieldSource(
            source_family="fixture_scene",
            source_name="constant_one_patch",
            width_deg=6.0,
            height_deg=6.0,
            source_metadata={"rule": "constant_one_inside_rectangular_patch"},
            field_sampler=lambda time_ms, azimuth_deg, elevation_deg: 1.0,
        )
        sampling_kernel = {
            "acceptance_angle_deg": 1.5,
            "support_radius_deg": 3.0,
            "background_fill_value": 0.25,
        }

        projector_a = RetinalProjector(
            retinal_geometry=geometry,
            visual_source=source,
            sampling_kernel=sampling_kernel,
        )
        projector_b = RetinalProjector(
            retinal_geometry=geometry,
            visual_source=source,
            sampling_kernel=sampling_kernel,
        )
        frame_a = projector_a.sample_frame(0.0)
        frame_b = projector_b.sample_frame(0.0)

        np.testing.assert_allclose(frame_a.samples, frame_b.samples, atol=0.0, rtol=0.0)
        self.assertEqual(frame_a.frame_metadata, frame_b.frame_metadata)
        self.assertEqual(projector_a.projector_metadata, projector_b.projector_metadata)
        np.testing.assert_allclose(frame_a.samples[0], frame_a.samples[1], atol=1.0e-7)
        self.assertAlmostEqual(float(frame_a.samples[0, 0]), 1.0, places=7)

        per_eye_projection = projector_a.projector_metadata["per_eye_projection"]["left"]
        self.assertEqual(per_eye_projection["fully_in_field_detector_count"], 1)
        self.assertEqual(per_eye_projection["partially_clipped_detector_count"], 6)
        self.assertEqual(per_eye_projection["fully_out_of_field_detector_count"], 12)
        self.assertEqual(
            per_eye_projection["fully_out_of_field_ommatidia"],
            list(range(7, 19)),
        )
        np.testing.assert_allclose(
            frame_a.samples[:, per_eye_projection["fully_out_of_field_ommatidia"]],
            0.25,
            atol=1.0e-7,
        )
        self.assertEqual(
            projector_a.projector_metadata["kernel_realization"]["acceptance_angle_semantics"],
            GAUSSIAN_ACCEPTANCE_ANGLE_SEMANTICS,
        )
        self.assertEqual(
            projector_a.projector_metadata["projection_model"]["out_of_field_blend_rule"],
            "background_fill_applied_to_out_of_field_support_samples_before_weighted_sum",
        )

    def test_canonical_translated_edge_sampling_is_deterministic_across_repeated_frame_generation(self) -> None:
        geometry = _build_forward_fixture_geometry()
        stimulus = synthesize_stimulus(
            stimulus_family="translated_edge",
            stimulus_name="simple_translated_edge",
            overrides={
                "onset_ms": 0.0,
                "offset_ms": 40.0,
                "background_level": 0.2,
                "contrast": 0.6,
                "velocity_deg_per_s": 0.001,
                "edge_width_deg": 0.25,
                "phase_offset_deg": 0.0,
            },
        )
        projector = RetinalProjector(
            retinal_geometry=geometry,
            visual_source=stimulus,
            sampling_kernel={
                "acceptance_angle_deg": 0.25,
                "support_radius_deg": 0.5,
                "background_fill_value": 0.5,
            },
        )

        explicit_times = stimulus.frame_times_ms[:3]
        explicit_a = projector.sample_times(explicit_times)
        explicit_b = projector.sample_times(explicit_times)
        timeline = projector.project_source_timeline()

        np.testing.assert_allclose(explicit_a.samples, explicit_b.samples, atol=0.0, rtol=0.0)
        self.assertEqual(explicit_a.frame_metadata, explicit_b.frame_metadata)
        self.assertEqual(explicit_a.projector_metadata, explicit_b.projector_metadata)
        np.testing.assert_allclose(timeline.frame_times_ms[:3], explicit_times, atol=0.0, rtol=0.0)
        np.testing.assert_allclose(timeline.samples[:3], explicit_a.samples, atol=0.0, rtol=0.0)
        np.testing.assert_allclose(explicit_a.samples[:, 0, :], explicit_a.samples[:, 1, :], atol=1.0e-7)

        detector_table = geometry.retinal_geometry["per_eye"]["left"]["detector_table"]
        positive_mask = np.asarray(
            [float(detector["eye_azimuth_deg"]) > 0.0 for detector in detector_table],
            dtype=bool,
        )
        negative_mask = np.asarray(
            [float(detector["eye_azimuth_deg"]) < 0.0 for detector in detector_table],
            dtype=bool,
        )
        center_value = float(explicit_a.samples[0, 0, 0])
        positive_values = explicit_a.samples[0, 0, positive_mask]
        negative_values = explicit_a.samples[0, 0, negative_mask]

        self.assertGreater(float(np.min(negative_values)), center_value)
        self.assertGreater(center_value, float(np.max(positive_values)))
        self.assertEqual(explicit_a.source_descriptor["source_kind"], "stimulus_bundle")
        self.assertEqual(
            explicit_a.projector_metadata["per_eye_projection"]["left"]["fully_out_of_field_detector_count"],
            0,
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
