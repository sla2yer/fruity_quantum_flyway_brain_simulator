from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.manifests import load_yaml
from flywire_wave.stimulus_generators import (
    build_stimulus_coordinate_axes,
    sample_stimulus_field,
    synthesize_stimulus,
)


class StimulusGeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_cases = load_yaml(ROOT / "tests/fixtures/stimulus_generator_cases.yaml")["cases"]

    def test_fixture_families_render_deterministically_with_expected_metadata_and_samples(self) -> None:
        for case_name, case in self.fixture_cases.items():
            if case_name == "moving_edge_alias_compat":
                continue

            with self.subTest(case=case_name):
                result_a = synthesize_stimulus(case["stimulus"])
                result_b = synthesize_stimulus(case["stimulus"])
                expected = case["expected"]

                self.assertEqual(result_a.frames.shape, tuple(expected["shape_t_y_x"]))
                np.testing.assert_allclose(result_a.frame_times_ms, expected["frame_times_ms"])
                self.assertEqual(
                    result_a.render_metadata["family_rendering"]["family_kind"],
                    expected["family_kind"],
                )
                self.assertEqual(result_a.render_metadata["frame_shape_t_y_x"], expected["shape_t_y_x"])
                self.assertEqual(result_a.render_metadata["frame_dtype"], "float32")
                self.assertEqual(
                    result_a.render_metadata["luminance_mapping"]["clip_mode"],
                    "clip_final_frame_values_to_unit_interval",
                )
                self.assertFalse(result_a.render_metadata["determinism"]["stochastic_branches_used"])
                self.assertTrue(np.all(result_a.frames >= 0.0))
                self.assertTrue(np.all(result_a.frames <= 1.0))

                np.testing.assert_array_equal(result_a.frames, result_b.frames)
                np.testing.assert_array_equal(result_a.frame_times_ms, result_b.frame_times_ms)
                self.assertEqual(result_a.render_metadata, result_b.render_metadata)

                for sample in expected["samples"]:
                    observed = result_a.sample_field(
                        time_ms=float(sample["time_ms"]),
                        azimuth_deg=float(sample["azimuth_deg"]),
                        elevation_deg=float(sample["elevation_deg"]),
                    )
                    self.assertAlmostEqual(float(observed), float(sample["value"]), places=6)

    def test_sample_field_api_matches_render_result_sampler(self) -> None:
        case = self.fixture_cases["translated_edge_ramp"]
        result = synthesize_stimulus(case["stimulus"])

        direct = sample_stimulus_field(
            case["stimulus"],
            time_ms=100.0,
            azimuth_deg=[-2.0, 0.0, 2.0],
            elevation_deg=[0.0, 0.0, 0.0],
        )
        via_result = result.sample_field(
            time_ms=100.0,
            azimuth_deg=[-2.0, 0.0, 2.0],
            elevation_deg=[0.0, 0.0, 0.0],
        )

        np.testing.assert_allclose(direct, via_result)

    def test_coordinate_axes_follow_centered_visual_field_convention(self) -> None:
        case = self.fixture_cases["drifting_grating_phase"]
        result = synthesize_stimulus(case["stimulus"])
        x_coordinates_deg, y_coordinates_deg = build_stimulus_coordinate_axes(
            result.stimulus_spec["spatial_frame"]
        )

        np.testing.assert_allclose(x_coordinates_deg, result.x_coordinates_deg)
        np.testing.assert_allclose(y_coordinates_deg, result.y_coordinates_deg)
        self.assertGreater(float(x_coordinates_deg[1] - x_coordinates_deg[0]), 0.0)
        self.assertLess(float(y_coordinates_deg[1] - y_coordinates_deg[0]), 0.0)
        self.assertAlmostEqual(float(x_coordinates_deg[0]), -15.5, places=6)
        self.assertAlmostEqual(float(x_coordinates_deg[-1]), 15.5, places=6)
        self.assertAlmostEqual(float(y_coordinates_deg[0]), 15.5, places=6)
        self.assertAlmostEqual(float(y_coordinates_deg[-1]), -15.5, places=6)

    def test_moving_edge_alias_renders_identically_to_canonical_translated_edge(self) -> None:
        alias_case = self.fixture_cases["moving_edge_alias_compat"]

        alias_result = synthesize_stimulus(alias_case["stimulus"])
        canonical_result = synthesize_stimulus(
            stimulus_family="translated_edge",
            stimulus_name="simple_translated_edge",
        )

        self.assertEqual(alias_result.stimulus_spec["stimulus_family"], "translated_edge")
        self.assertEqual(alias_result.stimulus_spec["stimulus_name"], "simple_translated_edge")
        self.assertTrue(alias_result.stimulus_spec["compatibility"]["family_alias_used"])
        self.assertTrue(alias_result.stimulus_spec["compatibility"]["name_alias_used"])
        np.testing.assert_array_equal(alias_result.frames, canonical_result.frames)
        np.testing.assert_array_equal(alias_result.frame_times_ms, canonical_result.frame_times_ms)
        self.assertEqual(alias_result.render_metadata, canonical_result.render_metadata)


if __name__ == "__main__":
    unittest.main()
