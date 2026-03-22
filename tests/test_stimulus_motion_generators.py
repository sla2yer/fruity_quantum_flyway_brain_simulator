from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.manifests import load_yaml
from flywire_wave.stimulus_generators import synthesize_stimulus


class StimulusMotionGeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_cases = load_yaml(ROOT / "tests/fixtures/stimulus_generator_cases.yaml")["cases"]

    def test_motion_family_fixtures_are_deterministic_and_record_motion_metadata(self) -> None:
        fixture_expectations = {
            "looming_growth": {
                "motion_sign": "expansion",
                "growth_domain": "active_interval_only",
            },
            "radial_flow_expansion_square": {
                "motion_sign": "expansion",
                "radial_speed_units": "deg_per_s_along_radius",
                "mask_handling": "hard_annulus_centered_on_motion_center",
            },
            "rotating_flow_clockwise_square": {
                "rotation_direction": "clockwise",
                "angular_velocity_units": "deg_per_s_about_motion_center",
                "mask_handling": "hard_annulus_centered_on_motion_center",
            },
        }
        for case_name, metadata_checks in fixture_expectations.items():
            with self.subTest(case=case_name):
                case = self.fixture_cases[case_name]
                expected = case["expected"]
                result_a = synthesize_stimulus(case["stimulus"])
                result_b = synthesize_stimulus(case["stimulus"])

                np.testing.assert_array_equal(result_a.frames, result_b.frames)
                np.testing.assert_array_equal(result_a.frame_times_ms, result_b.frame_times_ms)
                self.assertEqual(
                    result_a.render_metadata["family_rendering"]["family_kind"],
                    expected["family_kind"],
                )
                for key, value in metadata_checks.items():
                    self.assertEqual(result_a.render_metadata["family_rendering"][key], value)
                for sample in expected["samples"]:
                    observed = result_a.sample_field(
                        time_ms=float(sample["time_ms"]),
                        azimuth_deg=float(sample["azimuth_deg"]),
                        elevation_deg=float(sample["elevation_deg"]),
                    )
                    self.assertAlmostEqual(float(observed), float(sample["value"]), places=6)

    def test_radial_flow_motion_sign_controls_outward_and_inward_replay(self) -> None:
        common_stimulus = {
            "temporal_sampling": {
                "dt_ms": 50.0,
                "duration_ms": 300.0,
            },
            "stimulus_overrides": {
                "background_level": 0.5,
                "contrast": 0.25,
                "polarity": "positive",
                "onset_ms": 0.0,
                "offset_ms": 300.0,
                "radial_speed_deg_per_s": 15.0,
                "radial_spatial_frequency_cpd": 0.1,
                "phase_deg": 30.0,
                "waveform": "sine",
                "inner_radius_deg": 2.0,
                "outer_radius_deg": 12.0,
            },
        }
        expansion = synthesize_stimulus(
            {
                "stimulus": {
                    "stimulus_family": "radial_flow",
                    "stimulus_name": "expanding_flow",
                    **common_stimulus,
                }
            }
        )
        contraction = synthesize_stimulus(
            {
                "stimulus": {
                    "stimulus_family": "radial_flow",
                    "stimulus_name": "contracting_flow",
                    **common_stimulus,
                }
            }
        )

        expansion_current = float(
            expansion.sample_field(time_ms=100.0, azimuth_deg=6.0, elevation_deg=0.0)
        )
        contraction_current = float(
            contraction.sample_field(time_ms=100.0, azimuth_deg=6.0, elevation_deg=0.0)
        )
        shifted_outward = float(expansion.sample_field(time_ms=0.0, azimuth_deg=4.5, elevation_deg=0.0))
        shifted_inward = float(contraction.sample_field(time_ms=0.0, azimuth_deg=7.5, elevation_deg=0.0))
        opposite_outward = float(expansion.sample_field(time_ms=0.0, azimuth_deg=7.5, elevation_deg=0.0))
        opposite_inward = float(contraction.sample_field(time_ms=0.0, azimuth_deg=4.5, elevation_deg=0.0))

        self.assertAlmostEqual(expansion_current, shifted_outward, places=6)
        self.assertAlmostEqual(contraction_current, shifted_inward, places=6)
        self.assertNotAlmostEqual(expansion_current, opposite_outward, places=4)
        self.assertNotAlmostEqual(contraction_current, opposite_inward, places=4)

    def test_rotating_flow_direction_controls_clockwise_and_counterclockwise_replay(self) -> None:
        common_stimulus = {
            "temporal_sampling": {
                "dt_ms": 250.0,
                "duration_ms": 1250.0,
            },
            "stimulus_overrides": {
                "background_level": 0.5,
                "contrast": 0.25,
                "polarity": "positive",
                "onset_ms": 0.0,
                "offset_ms": 1250.0,
                "angular_velocity_deg_per_s": 30.0,
                "angular_cycle_count": 1,
                "phase_deg": 20.0,
                "waveform": "sine",
                "inner_radius_deg": 2.0,
                "outer_radius_deg": 12.0,
            },
        }
        clockwise = synthesize_stimulus(
            {
                "stimulus": {
                    "stimulus_family": "rotating_flow",
                    "stimulus_name": "clockwise_rotation",
                    **common_stimulus,
                }
            }
        )
        counterclockwise = synthesize_stimulus(
            {
                "stimulus": {
                    "stimulus_family": "rotating_flow",
                    "stimulus_name": "counterclockwise_rotation",
                    **common_stimulus,
                }
            }
        )

        radius_deg = 6.0
        clockwise_current = float(
            clockwise.sample_field(time_ms=1000.0, azimuth_deg=radius_deg, elevation_deg=0.0)
        )
        counterclockwise_current = float(
            counterclockwise.sample_field(time_ms=1000.0, azimuth_deg=radius_deg, elevation_deg=0.0)
        )
        clockwise_origin = self._polar_sample(clockwise, time_ms=0.0, radius_deg=radius_deg, angle_deg=30.0)
        clockwise_opposite = self._polar_sample(clockwise, time_ms=0.0, radius_deg=radius_deg, angle_deg=-30.0)
        counterclockwise_origin = self._polar_sample(
            counterclockwise,
            time_ms=0.0,
            radius_deg=radius_deg,
            angle_deg=-30.0,
        )
        counterclockwise_opposite = self._polar_sample(
            counterclockwise,
            time_ms=0.0,
            radius_deg=radius_deg,
            angle_deg=30.0,
        )

        self.assertAlmostEqual(clockwise_current, clockwise_origin, places=6)
        self.assertAlmostEqual(counterclockwise_current, counterclockwise_origin, places=6)
        self.assertNotAlmostEqual(clockwise_current, clockwise_opposite, places=4)
        self.assertNotAlmostEqual(counterclockwise_current, counterclockwise_opposite, places=4)

    def test_shifted_motion_centers_follow_the_canonical_azimuth_and_elevation_axes(self) -> None:
        result = synthesize_stimulus(
            {
                "stimulus": {
                    "stimulus_family": "radial_flow",
                    "stimulus_name": "expanding_flow",
                    "temporal_sampling": {
                        "dt_ms": 50.0,
                        "duration_ms": 250.0,
                    },
                    "stimulus_overrides": {
                        "background_level": 0.5,
                        "contrast": 0.25,
                        "polarity": "positive",
                        "onset_ms": 0.0,
                        "offset_ms": 250.0,
                        "center_azimuth_deg": 2.0,
                        "center_elevation_deg": -1.0,
                        "motion_sign": "expansion",
                        "radial_speed_deg_per_s": 20.0,
                        "radial_spatial_frequency_cpd": 0.25,
                        "phase_deg": 90.0,
                        "waveform": "square",
                        "inner_radius_deg": 2.0,
                        "outer_radius_deg": 12.0,
                    },
                }
            }
        )

        horizontal_sample = float(
            result.sample_field(time_ms=100.0, azimuth_deg=8.0, elevation_deg=-1.0)
        )
        vertical_sample = float(
            result.sample_field(time_ms=100.0, azimuth_deg=2.0, elevation_deg=5.0)
        )
        motion_center_sample = float(
            result.sample_field(time_ms=100.0, azimuth_deg=2.0, elevation_deg=-1.0)
        )

        self.assertAlmostEqual(horizontal_sample, vertical_sample, places=6)
        self.assertAlmostEqual(motion_center_sample, 0.5, places=6)

    @staticmethod
    def _polar_sample(result: object, *, time_ms: float, radius_deg: float, angle_deg: float) -> float:
        azimuth_deg = radius_deg * math.cos(math.radians(angle_deg))
        elevation_deg = radius_deg * math.sin(math.radians(angle_deg))
        return float(
            result.sample_field(
                time_ms=time_ms,
                azimuth_deg=azimuth_deg,
                elevation_deg=elevation_deg,
            )
        )


if __name__ == "__main__":
    unittest.main()
