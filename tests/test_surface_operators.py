from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.surface_operators import assemble_fine_surface_operator


class FineSurfaceOperatorTest(unittest.TestCase):
    def test_open_square_mesh_emits_boundary_masks_and_symmetric_operators(self) -> None:
        vertices = np.asarray(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
                [0.0, 1.0, 0.0],
            ],
            dtype=np.float32,
        )
        faces = np.asarray(
            [
                [0, 1, 2],
                [0, 2, 3],
            ],
            dtype=np.int32,
        )

        bundle = assemble_fine_surface_operator(
            root_id=202,
            vertices=vertices,
            faces=faces,
            geodesic_hops=2,
            geodesic_vertex_cap=4,
        )
        payload = bundle.payload
        metadata = bundle.metadata

        stiffness = _load_csr(payload, prefix="stiffness")
        operator = _load_csr(payload, prefix="operator")
        adjacency = _load_csr(payload, prefix="adj")

        self.assertEqual(adjacency.shape, (4, 4))
        self.assertEqual(stiffness.shape, (4, 4))
        self.assertEqual(operator.shape, (4, 4))
        self.assertEqual(int(payload["root_id"]), 202)
        self.assertEqual(payload["edge_vertex_indices"].shape[0], 5)
        self.assertEqual(int(np.count_nonzero(payload["boundary_vertex_mask"])), 4)
        self.assertEqual(int(np.count_nonzero(payload["boundary_edge_mask"])), 4)
        self.assertEqual(int(np.count_nonzero(payload["boundary_face_mask"])), 2)
        self.assertEqual(int(np.count_nonzero(payload["edge_face_counts"] == 2)), 1)
        self.assertTrue(np.allclose(payload["effective_cotangent_weights"], payload["cotangent_weights"]))
        self.assertTrue(np.allclose(payload["anisotropy_vertex_tensor_diagonal"], 1.0))
        self.assertTrue(np.allclose(payload["anisotropy_edge_multiplier"], 1.0))
        self.assertTrue(np.all(payload["mass_diagonal"] > 0.0))
        self.assertTrue(np.allclose(stiffness.toarray(), stiffness.toarray().T, atol=1e-6))
        self.assertTrue(np.allclose(operator.toarray(), operator.toarray().T, atol=1e-6))
        self.assertTrue(np.allclose(np.asarray(stiffness.sum(axis=1)).ravel(), 0.0, atol=1e-6))
        self.assertTrue(np.allclose(np.cross(payload["tangent_u"], payload["tangent_v"]), payload["vertex_normals"], atol=1e-5))
        self.assertTrue(np.allclose(np.linalg.norm(payload["vertex_normals"], axis=1), 1.0, atol=1e-5))

        eigenvalues = np.linalg.eigvalsh(operator.toarray())
        self.assertGreaterEqual(float(eigenvalues.min()), -1e-5)

        geodesic_indptr = payload["geodesic_neighbor_indptr"]
        geodesic_indices = payload["geodesic_neighbor_indices"]
        geodesic_distances = payload["geodesic_neighbor_distances"]
        geodesic_hops = payload["geodesic_neighbor_hops"]
        self.assertEqual(geodesic_indptr.shape, (5,))
        for vertex_index in range(4):
            start = int(geodesic_indptr[vertex_index])
            end = int(geodesic_indptr[vertex_index + 1])
            self.assertGreaterEqual(end - start, 1)
            self.assertLessEqual(end - start, 4)
            self.assertEqual(int(geodesic_indices[start]), vertex_index)
            self.assertEqual(float(geodesic_distances[start]), 0.0)
            self.assertEqual(int(geodesic_hops[start]), 0)
            self.assertTrue(np.all(np.diff(geodesic_distances[start:end]) >= -1e-7))

        self.assertEqual(metadata["discretization_family"], "triangle_mesh_cotangent_fem")
        self.assertEqual(metadata["mass_treatment"], "lumped_mass")
        self.assertEqual(metadata["normalization"], "mass_normalized")
        self.assertEqual(metadata["boundary_condition_mode"], "closed_surface_zero_flux")
        self.assertEqual(metadata["operator_assembly"]["version"], "operator_assembly.v1")
        self.assertEqual(metadata["boundary_condition"]["assembly_rule"], "natural_open_boundary_terms")
        self.assertEqual(metadata["anisotropy_model"], "isotropic")
        self.assertEqual(metadata["anisotropy"]["coefficient_layout"], "implicit_identity")
        self.assertEqual(metadata["geodesic_neighborhood"]["mode"], "edge_path_dijkstra_hop_capped")
        self.assertEqual(metadata["counts"]["boundary_edge_count"], 4)
        self.assertEqual(metadata["counts"]["boundary_vertex_count"], 4)
        self.assertEqual(metadata["counts"]["anisotropy_nontrivial_vertex_count"], 0)
        self.assertEqual(metadata["counts"]["anisotropy_nontrivial_edge_count"], 0)

    def test_inconsistent_face_orientation_uses_fallback_vertex_normals(self) -> None:
        vertices = np.asarray(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 1.0, 0.0],
                [0.0, 1.0, 0.0],
            ],
            dtype=np.float32,
        )
        faces = np.asarray(
            [
                [0, 1, 2],
                [0, 3, 2],
            ],
            dtype=np.int32,
        )

        bundle = assemble_fine_surface_operator(
            root_id=203,
            vertices=vertices,
            faces=faces,
            geodesic_hops=2,
            geodesic_vertex_cap=4,
        )

        self.assertEqual(int(bundle.payload["root_id"]), 203)
        self.assertTrue(np.all(np.isfinite(bundle.payload["vertex_normals"])))
        self.assertTrue(np.allclose(np.linalg.norm(bundle.payload["vertex_normals"], axis=1), 1.0, atol=1e-5))


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
