from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.config import load_config
from flywire_wave.manifests import load_yaml, resolve_manifest_retinal_geometry
from flywire_wave.retinal_geometry import (
    DEFAULT_GEOMETRY_FAMILY,
    FIXTURE_GEOMETRY_NAME,
    build_body_to_head_transform,
    build_head_to_eye_transform,
    build_world_to_body_transform,
    compose_rigid_transforms,
    eye_direction_to_lattice_coordinates,
    lattice_coordinates_to_eye_direction,
    resolve_retinal_geometry_spec,
)


class RetinalGeometryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = load_yaml(ROOT / "tests/fixtures/retinal_geometry_cases.yaml")

    def test_fixture_cases_resolve_normalized_spec_and_stable_indexing(self) -> None:
        resolved = resolve_retinal_geometry_spec(self.fixtures["valid_cases"]["alias_driven_fixture"])
        spec = resolved.retinal_geometry

        self.assertEqual(spec["geometry_family"], DEFAULT_GEOMETRY_FAMILY)
        self.assertEqual(spec["geometry_name"], FIXTURE_GEOMETRY_NAME)
        self.assertIn(
            {"geometry_family": "ommatidial_lattice", "geometry_name": "fixture"},
            spec["compatibility_aliases"],
        )
        self.assertEqual(spec["eye_order"], ["left", "right"])
        self.assertEqual(spec["ommatidium_count_per_eye"], 19)
        self.assertEqual(spec["lattice"]["ring_count"], 2)
        self.assertEqual(spec["lattice_indexing"]["ring_detector_counts"], [1, 6, 12])

        left_detectors = spec["per_eye"]["left"]["detector_table"]
        right_detectors = spec["per_eye"]["right"]["detector_table"]
        self.assertEqual(
            [detector["ommatidium_index"] for detector in left_detectors],
            list(range(19)),
        )
        self.assertEqual(
            [detector["ommatidium_index"] for detector in right_detectors],
            list(range(19)),
        )

        center_detector = left_detectors[0]
        self.assertEqual(center_detector["ring_index"], 0)
        self.assertEqual(center_detector["ring_position"], 0)
        np.testing.assert_allclose(center_detector["direction_eye"], [0.0, 0.0, 1.0], atol=1.0e-12)

        first_ring_detector = left_detectors[1]
        self.assertEqual(first_ring_detector["ring_index"], 1)
        self.assertEqual(first_ring_detector["ring_position"], 0)
        self.assertAlmostEqual(first_ring_detector["eye_azimuth_deg"], 0.0, places=9)
        self.assertAlmostEqual(first_ring_detector["eye_elevation_deg"], 6.0, places=9)

        self.assertEqual(spec["per_eye"]["left"]["symmetry_source"], "explicit")
        self.assertEqual(spec["per_eye"]["right"]["symmetry_source"], "mirrored_from_left")
        self.assertAlmostEqual(
            float(spec["per_eye"]["left"]["center_head_mm"][0]),
            float(spec["per_eye"]["right"]["center_head_mm"][0]),
            places=9,
        )
        self.assertAlmostEqual(
            float(spec["per_eye"]["left"]["center_head_mm"][1]),
            -float(spec["per_eye"]["right"]["center_head_mm"][1]),
            places=9,
        )
        self.assertAlmostEqual(
            float(spec["per_eye"]["left"]["optical_axis_head"][0]),
            float(spec["per_eye"]["right"]["optical_axis_head"][0]),
            places=9,
        )
        self.assertAlmostEqual(
            float(spec["per_eye"]["left"]["optical_axis_head"][1]),
            -float(spec["per_eye"]["right"]["optical_axis_head"][1]),
            places=9,
        )

        for left_detector, right_detector in zip(left_detectors, right_detectors, strict=True):
            np.testing.assert_allclose(left_detector["direction_eye"], right_detector["direction_eye"], atol=1.0e-12)

        self.assertAlmostEqual(
            float(left_detectors[1]["direction_head"][0]),
            float(right_detectors[1]["direction_head"][0]),
            places=9,
        )
        self.assertAlmostEqual(
            float(left_detectors[1]["direction_head"][1]),
            -float(right_detectors[1]["direction_head"][1]),
            places=9,
        )
        self.assertAlmostEqual(
            float(left_detectors[1]["direction_head"][2]),
            float(right_detectors[1]["direction_head"][2]),
            places=9,
        )

        nearest = resolved.find_nearest_ommatidium("left", direction_eye=[0.0, 0.0, 1.0])
        self.assertEqual(nearest["ommatidium_index"], 0)

    def test_transform_helpers_and_lattice_projection_are_orientation_sane(self) -> None:
        resolved = resolve_retinal_geometry_spec(self.fixtures["valid_cases"]["mirrored_override_fixture"])
        spec = resolved.retinal_geometry

        world_to_body = build_world_to_body_transform(
            {
                "translation_world_mm": [1.0, -2.0, 0.5],
                "yaw_pitch_roll_deg": [90.0, 0.0, 0.0],
            }
        )
        body_to_head = build_body_to_head_transform(spec)
        head_to_eye = build_head_to_eye_transform(spec, "left")
        world_to_eye = compose_rigid_transforms(world_to_body, body_to_head, head_to_eye)

        point_at_body_origin = world_to_body.apply_to_points([1.0, -2.0, 0.5])[0]
        np.testing.assert_allclose(point_at_body_origin, [0.0, 0.0, 0.0], atol=1.0e-12)

        body_forward = world_to_body.apply_to_directions([0.0, 1.0, 0.0])[0]
        np.testing.assert_allclose(body_forward, [1.0, 0.0, 0.0], atol=1.0e-12)

        eye_spec = spec["per_eye"]["left"]
        optical_axis_eye = head_to_eye.apply_to_directions(eye_spec["optical_axis_head"])[0]
        dorsal_axis_eye = head_to_eye.apply_to_directions(eye_spec["eye_axes_in_head"]["x"])[0]
        np.testing.assert_allclose(optical_axis_eye, [0.0, 0.0, 1.0], atol=1.0e-12)
        np.testing.assert_allclose(dorsal_axis_eye, [1.0, 0.0, 0.0], atol=1.0e-12)

        world_point = np.asarray([1.1, -1.6, 0.9], dtype=np.float64)
        eye_point = world_to_eye.apply_to_points(world_point)[0]
        recovered_world_point = world_to_eye.inverse().apply_to_points(eye_point)[0]
        np.testing.assert_allclose(recovered_world_point, world_point, atol=1.0e-12)

        top_detector = spec["per_eye"]["left"]["detector_table"][1]
        lattice_local = eye_direction_to_lattice_coordinates(spec, top_detector["direction_eye"])
        self.assertAlmostEqual(lattice_local["axial_q"], float(top_detector["axial_q"]), places=9)
        self.assertAlmostEqual(lattice_local["axial_r"], float(top_detector["axial_r"]), places=9)
        reconstructed_direction = lattice_coordinates_to_eye_direction(
            spec,
            {
                "axial_q": top_detector["axial_q"],
                "axial_r": top_detector["axial_r"],
            },
        )
        np.testing.assert_allclose(reconstructed_direction, top_detector["direction_eye"], atol=1.0e-12)

    def test_invalid_cases_fail_clearly(self) -> None:
        for case_name, case in self.fixtures["invalid_cases"].items():
            with self.subTest(case=case_name):
                with self.assertRaises(ValueError) as ctx:
                    resolve_retinal_geometry_spec(case)
                self.assertIn(case["error_substring"], str(ctx.exception))

    def test_load_config_resolves_retinal_geometry_fixture(self) -> None:
        cfg = load_config(
            ROOT / "tests/fixtures/retinal_geometry_config_fixture.yaml",
            project_root=ROOT,
        )

        self.assertEqual(cfg["retinal_geometry"]["geometry_name"], FIXTURE_GEOMETRY_NAME)
        self.assertEqual(cfg["retinal_geometry"]["geometry_family"], DEFAULT_GEOMETRY_FAMILY)
        self.assertEqual(cfg["retinal_geometry"]["ommatidium_count_per_eye"], 19)
        self.assertEqual(
            cfg["retinal_geometry_registry_entry"]["geometry_name"],
            FIXTURE_GEOMETRY_NAME,
        )
        self.assertEqual(
            Path(cfg["paths"]["processed_retinal_dir"]),
            (ROOT / "data/processed/test_retinal").resolve(),
        )

    def test_manifest_helper_resolves_nested_retinal_geometry(self) -> None:
        resolved = resolve_manifest_retinal_geometry(self.fixtures["valid_cases"]["explicit_both_eyes"])
        self.assertEqual(resolved.geometry_name, FIXTURE_GEOMETRY_NAME)
        self.assertEqual(
            resolved.retinal_geometry["symmetry"]["mode"],
            "explicit_per_eye",
        )


if __name__ == "__main__":
    unittest.main()
