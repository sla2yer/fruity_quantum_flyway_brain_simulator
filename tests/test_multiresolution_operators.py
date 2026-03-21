from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.surface_operators import (
    FineSurfaceOperatorAssemblyError,
    assemble_fine_surface_operator,
    assemble_patch_multiresolution_operators,
)


class PatchMultiresolutionOperatorTest(unittest.TestCase):
    def test_patch_multiresolution_assembly_is_deterministic(self) -> None:
        fixture = _build_fixture_bundle()

        first = assemble_patch_multiresolution_operators(**fixture)
        second = assemble_patch_multiresolution_operators(**fixture)

        for payload_a, payload_b in (
            (first.coarse_payload, second.coarse_payload),
            (first.transfer_payload, second.transfer_payload),
        ):
            self.assertEqual(set(payload_a), set(payload_b))
            for key in payload_a:
                self.assertTrue(np.array_equal(payload_a[key], payload_b[key]), msg=f"payload key {key!r} changed")
        self.assertEqual(first.metadata, second.metadata)

    def test_patch_multiresolution_assembly_rejects_inconsistent_patch_membership(self) -> None:
        fixture = _build_fixture_bundle()
        fixture["member_vertex_indices"] = np.asarray([0, 1, 2, 2, 4, 5], dtype=np.int32)

        with self.assertRaises(FineSurfaceOperatorAssemblyError):
            assemble_patch_multiresolution_operators(**fixture)

    def test_patch_multiresolution_assembly_preserves_constants_mass_and_galerkin_consistency(self) -> None:
        bundle = assemble_patch_multiresolution_operators(**_build_fixture_bundle())

        coarse_payload = bundle.coarse_payload
        transfer_payload = bundle.transfer_payload
        coarse_stiffness = _load_csr(coarse_payload, prefix="stiffness")
        coarse_operator = _load_csr(coarse_payload, prefix="operator")
        restriction = _load_csr(transfer_payload, prefix="restriction")
        prolongation = _load_csr(transfer_payload, prefix="prolongation")
        normalized_restriction = _load_csr(transfer_payload, prefix="normalized_restriction")
        normalized_prolongation = _load_csr(transfer_payload, prefix="normalized_prolongation")

        patch_count = int(coarse_payload["patch_count"])
        surface_vertex_count = int(coarse_payload["surface_vertex_count"])
        fine_mass = transfer_payload["fine_mass_diagonal"].astype(np.float64)
        coarse_mass = transfer_payload["coarse_mass_diagonal"].astype(np.float64)
        fine_probe = _vertices()[:, 0].astype(np.float64)

        self.assertEqual(coarse_stiffness.shape, (patch_count, patch_count))
        self.assertEqual(coarse_operator.shape, (patch_count, patch_count))
        self.assertEqual(restriction.shape, (patch_count, surface_vertex_count))
        self.assertEqual(prolongation.shape, (surface_vertex_count, patch_count))
        self.assertTrue(np.allclose(restriction @ np.ones(surface_vertex_count), 1.0))
        self.assertTrue(np.allclose(prolongation @ np.ones(patch_count), 1.0))
        self.assertTrue(np.allclose(normalized_restriction.toarray(), normalized_prolongation.toarray().T, atol=1e-7))
        self.assertTrue(
            np.allclose(
                (normalized_restriction @ normalized_prolongation).toarray(),
                np.eye(patch_count),
                atol=1e-7,
            )
        )
        self.assertTrue(np.allclose(coarse_stiffness.toarray(), coarse_stiffness.toarray().T, atol=1e-7))
        self.assertTrue(np.allclose(coarse_operator.toarray(), coarse_operator.toarray().T, atol=1e-7))
        self.assertTrue(np.allclose(np.asarray(coarse_stiffness.sum(axis=1)).ravel(), 0.0, atol=1e-7))
        self.assertAlmostEqual(float(coarse_mass.sum()), float(fine_mass.sum()), places=7)
        self.assertAlmostEqual(float(coarse_mass @ (restriction @ fine_probe)), float(fine_mass @ fine_probe), places=7)

        self.assertLessEqual(float(transfer_payload["quality_constant_field_restriction_residual_inf"]), 1e-8)
        self.assertLessEqual(float(transfer_payload["quality_constant_field_prolongation_residual_inf"]), 1e-8)
        self.assertLessEqual(float(transfer_payload["quality_mass_total_relative_error"]), 1e-8)
        self.assertLessEqual(float(transfer_payload["quality_mass_preservation_probe_absolute_error"]), 1e-8)
        self.assertLessEqual(float(transfer_payload["quality_normalized_transfer_identity_residual_inf"]), 1e-8)
        self.assertLessEqual(float(transfer_payload["quality_normalized_transfer_adjoint_residual_inf"]), 1e-8)
        self.assertLessEqual(float(transfer_payload["quality_galerkin_operator_residual_inf"]), 1e-8)
        self.assertLessEqual(float(transfer_payload["quality_coarse_application_residual_relative"]), 1e-8)
        self.assertLessEqual(float(transfer_payload["quality_coarse_rayleigh_quotient_drift_absolute"]), 1e-8)
        self.assertLessEqual(float(transfer_payload["quality_fine_state_projection_residual_relative"]), 0.9)
        self.assertLessEqual(float(transfer_payload["quality_fine_application_projection_residual_relative"]), 0.9)
        self.assertEqual(bundle.metadata["transfer_restriction_mode"], "lumped_mass_patch_average")
        self.assertEqual(bundle.metadata["transfer_prolongation_mode"], "constant_on_patch")
        self.assertEqual(bundle.metadata["coarse_operator_construction"]["coarse_stiffness"], "galerkin_projection_PtKP")


def _build_fixture_bundle() -> dict[str, object]:
    vertices = _vertices()
    faces = _faces()
    fine_bundle = assemble_fine_surface_operator(
        root_id=303,
        vertices=vertices,
        faces=faces,
        geodesic_hops=2,
        geodesic_vertex_cap=6,
    )
    surface_to_patch = np.asarray([0, 0, 1, 1, 2, 2], dtype=np.int32)
    patch_sizes = np.asarray([2, 2, 2], dtype=np.int32)
    patch_seed_vertices = np.asarray([0, 2, 4], dtype=np.int32)
    member_vertex_indices = np.asarray([0, 1, 2, 3, 4, 5], dtype=np.int32)
    member_vertex_indptr = np.asarray([0, 2, 4, 6], dtype=np.int32)
    patch_centroids = np.asarray(
        [
            vertices[[0, 1]].mean(axis=0),
            vertices[[2, 3]].mean(axis=0),
            vertices[[4, 5]].mean(axis=0),
        ],
        dtype=np.float32,
    )
    return {
        "root_id": 303,
        "vertices": vertices,
        "surface_to_patch": surface_to_patch,
        "patch_sizes": patch_sizes,
        "patch_seed_vertices": patch_seed_vertices,
        "patch_centroids": patch_centroids,
        "member_vertex_indices": member_vertex_indices,
        "member_vertex_indptr": member_vertex_indptr,
        "fine_mass_diagonal": fine_bundle.payload["mass_diagonal"],
        "fine_stiffness": _load_csr(fine_bundle.payload, prefix="stiffness"),
        "fine_operator": _load_csr(fine_bundle.payload, prefix="operator"),
    }


def _vertices() -> np.ndarray:
    return np.asarray(
        [
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, -1.0, 0.0],
            [0.0, 0.0, -1.0],
        ],
        dtype=np.float32,
    )


def _faces() -> np.ndarray:
    return np.asarray(
        [
            [0, 1, 2],
            [0, 2, 3],
            [0, 3, 4],
            [0, 4, 1],
            [5, 2, 1],
            [5, 3, 2],
            [5, 4, 3],
            [5, 1, 4],
        ],
        dtype=np.int32,
    )


def _load_csr(payload: dict[str, np.ndarray], *, prefix: str) -> sp.csr_matrix:
    shape = tuple(int(value) for value in payload[f"{prefix}_shape"])
    return sp.csr_matrix(
        (
            payload[f"{prefix}_data"],
            payload[f"{prefix}_indices"],
            payload[f"{prefix}_indptr"],
        ),
        shape=shape,
    )


if __name__ == "__main__":
    unittest.main()
