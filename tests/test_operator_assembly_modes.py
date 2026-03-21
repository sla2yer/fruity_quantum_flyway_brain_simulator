from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.geometry_contract import (
    CLAMPED_BOUNDARY_CONDITION_MODE,
    IDENTITY_ANISOTROPY_EQUIVALENCE_ATOL,
    TANGENT_DIAGONAL_ANISOTROPY_MODEL,
)
from flywire_wave.surface_operators import assemble_fine_surface_operator


class OperatorAssemblyModesTest(unittest.TestCase):
    def test_identity_tangent_diagonal_matches_isotropic_operator(self) -> None:
        vertices, faces = _open_square_fixture()
        isotropic_bundle = assemble_fine_surface_operator(
            root_id=301,
            vertices=vertices,
            faces=faces,
        )
        identity_anisotropy_bundle = assemble_fine_surface_operator(
            root_id=301,
            vertices=vertices,
            faces=faces,
            operator_assembly={
                "version": "operator_assembly.v1",
                "anisotropy": {
                    "model": TANGENT_DIAGONAL_ANISOTROPY_MODEL,
                    "default_tensor": [1.0, 1.0],
                },
            },
        )

        isotropic_stiffness = _load_csr(isotropic_bundle.payload, prefix="stiffness").toarray()
        anisotropic_stiffness = _load_csr(identity_anisotropy_bundle.payload, prefix="stiffness").toarray()
        isotropic_operator = _load_csr(isotropic_bundle.payload, prefix="operator").toarray()
        anisotropic_operator = _load_csr(identity_anisotropy_bundle.payload, prefix="operator").toarray()

        self.assertTrue(
            np.allclose(
                anisotropic_stiffness,
                isotropic_stiffness,
                atol=IDENTITY_ANISOTROPY_EQUIVALENCE_ATOL,
            )
        )
        self.assertTrue(
            np.allclose(
                anisotropic_operator,
                isotropic_operator,
                atol=IDENTITY_ANISOTROPY_EQUIVALENCE_ATOL,
            )
        )
        self.assertTrue(
            np.allclose(
                identity_anisotropy_bundle.payload["anisotropy_edge_multiplier"],
                1.0,
                atol=IDENTITY_ANISOTROPY_EQUIVALENCE_ATOL,
            )
        )
        self.assertEqual(
            identity_anisotropy_bundle.metadata["anisotropy_model"],
            TANGENT_DIAGONAL_ANISOTROPY_MODEL,
        )
        self.assertEqual(
            identity_anisotropy_bundle.metadata["anisotropy"]["coefficient_source"],
            "global_default_diagonal",
        )

    def test_nontrivial_anisotropy_and_clamped_boundary_change_realized_operator(self) -> None:
        vertices, faces = _open_square_fixture()
        isotropic_bundle = assemble_fine_surface_operator(
            root_id=302,
            vertices=vertices,
            faces=faces,
        )
        anisotropic_bundle = assemble_fine_surface_operator(
            root_id=302,
            vertices=vertices,
            faces=faces,
            operator_assembly={
                "version": "operator_assembly.v1",
                "anisotropy": {
                    "model": TANGENT_DIAGONAL_ANISOTROPY_MODEL,
                    "default_tensor": [2.0, 0.5],
                },
            },
        )
        clamped_bundle = assemble_fine_surface_operator(
            root_id=302,
            vertices=vertices,
            faces=faces,
            operator_assembly={
                "version": "operator_assembly.v1",
                "boundary_condition": {
                    "mode": CLAMPED_BOUNDARY_CONDITION_MODE,
                },
            },
        )

        isotropic_operator = _load_csr(isotropic_bundle.payload, prefix="operator").toarray()
        anisotropic_operator = _load_csr(anisotropic_bundle.payload, prefix="operator").toarray()
        clamped_operator = _load_csr(clamped_bundle.payload, prefix="operator").toarray()
        clamped_stiffness = _load_csr(clamped_bundle.payload, prefix="stiffness").toarray()

        self.assertFalse(np.allclose(anisotropic_operator, isotropic_operator, atol=1e-8))
        self.assertTrue(
            np.allclose(
                anisotropic_bundle.payload["anisotropy_edge_multiplier"],
                np.asarray([2.0, 1.25, 0.5, 0.5, 2.0], dtype=np.float32),
                atol=1e-6,
            )
        )
        self.assertTrue(
            np.allclose(
                anisotropic_bundle.payload["effective_cotangent_weights"],
                anisotropic_bundle.payload["cotangent_weights"] * anisotropic_bundle.payload["anisotropy_edge_multiplier"],
                atol=1e-6,
            )
        )
        self.assertEqual(anisotropic_bundle.metadata["counts"]["anisotropy_nontrivial_vertex_count"], 4)
        self.assertEqual(anisotropic_bundle.metadata["counts"]["anisotropy_nontrivial_edge_count"], 5)

        self.assertTrue(np.allclose(clamped_operator, np.eye(4), atol=1e-7))
        self.assertTrue(np.allclose(clamped_stiffness, np.diag(clamped_bundle.payload["mass_diagonal"]), atol=1e-7))
        self.assertEqual(clamped_bundle.metadata["boundary_condition_mode"], CLAMPED_BOUNDARY_CONDITION_MODE)
        self.assertEqual(
            clamped_bundle.metadata["boundary_condition"]["assembly_rule"],
            "boundary_vertices_identity_pinned_after_lumped_mass_normalization",
        )
        self.assertFalse(clamped_bundle.metadata["matrix_properties"]["constant_nullspace_on_stiffness"])


def _open_square_fixture() -> tuple[np.ndarray, np.ndarray]:
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
    return vertices, faces


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
