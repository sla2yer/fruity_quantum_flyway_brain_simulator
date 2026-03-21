from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.geometry_contract import build_geometry_bundle_paths
from flywire_wave.geometry_contract import load_operator_bundle_metadata
from flywire_wave.mesh_pipeline import process_mesh_into_wave_assets


class MeshBuildPipelineTest(unittest.TestCase):
    def test_process_mesh_builds_explicit_multiresolution_graph_artifacts_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            bundle_paths_a = _bundle_paths(tmp_dir / "run_a")
            bundle_paths_b = _bundle_paths(tmp_dir / "run_b")

            _write_octahedron_mesh(bundle_paths_a.raw_mesh_path)
            _write_octahedron_mesh(bundle_paths_b.raw_mesh_path)
            _write_stub_swc(bundle_paths_a.raw_skeleton_path)
            _write_stub_swc(bundle_paths_b.raw_skeleton_path)

            outputs_a = process_mesh_into_wave_assets(
                root_id=101,
                bundle_paths=bundle_paths_a,
                simplify_target_faces=8,
                patch_hops=1,
                patch_vertex_cap=2,
                registry_metadata={"cell_type": "T5a", "project_role": "surface_simulated"},
            )
            outputs_b = process_mesh_into_wave_assets(
                root_id=101,
                bundle_paths=bundle_paths_b,
                simplify_target_faces=8,
                patch_hops=1,
                patch_vertex_cap=2,
                registry_metadata={"cell_type": "T5a", "project_role": "surface_simulated"},
            )

            surface_graph_a = _read_npz(bundle_paths_a.surface_graph_path)
            fine_operator_a = _read_npz(bundle_paths_a.fine_operator_path)
            patch_graph_a = _read_npz(bundle_paths_a.patch_graph_path)
            coarse_operator_a = _read_npz(bundle_paths_a.coarse_operator_path)
            transfer_ops_a = _read_npz(bundle_paths_a.transfer_operator_path)
            surface_graph_b = _read_npz(bundle_paths_b.surface_graph_path)
            fine_operator_b = _read_npz(bundle_paths_b.fine_operator_path)
            patch_graph_b = _read_npz(bundle_paths_b.patch_graph_path)
            coarse_operator_b = _read_npz(bundle_paths_b.coarse_operator_path)
            transfer_ops_b = _read_npz(bundle_paths_b.transfer_operator_path)

            expected_surface_keys = {
                "root_id",
                "patch_count",
                "vertices",
                "faces",
                "surface_to_patch",
                "adj_data",
                "adj_indices",
                "adj_indptr",
                "adj_shape",
                "lap_data",
                "lap_indices",
                "lap_indptr",
                "lap_shape",
            }
            expected_patch_keys = {
                "root_id",
                "patch_count",
                "surface_vertex_count",
                "surface_to_patch",
                "patch_seed_vertices",
                "patch_sizes",
                "patch_centroids",
                "member_vertex_indices",
                "member_vertex_indptr",
                "adj_data",
                "adj_indices",
                "adj_indptr",
                "adj_shape",
                "lap_data",
                "lap_indices",
                "lap_indptr",
                "lap_shape",
            }
            expected_fine_operator_keys = {
                "root_id",
                "vertices",
                "faces",
                "face_areas",
                "face_normals",
                "vertex_normals",
                "tangent_u",
                "tangent_v",
                "mass_diagonal",
                "vertex_areas",
                "edge_vertex_indices",
                "edge_lengths",
                "edge_vectors",
                "edge_face_counts",
                "cotangent_weights",
                "boundary_vertex_mask",
                "boundary_edge_mask",
                "boundary_face_mask",
                "geodesic_neighbor_indices",
                "geodesic_neighbor_indptr",
                "geodesic_neighbor_distances",
                "geodesic_neighbor_hops",
                "adj_data",
                "adj_indices",
                "adj_indptr",
                "adj_shape",
                "edge_length_data",
                "edge_length_indices",
                "edge_length_indptr",
                "edge_length_shape",
                "cotangent_weight_data",
                "cotangent_weight_indices",
                "cotangent_weight_indptr",
                "cotangent_weight_shape",
                "stiffness_data",
                "stiffness_indices",
                "stiffness_indptr",
                "stiffness_shape",
                "operator_data",
                "operator_indices",
                "operator_indptr",
                "operator_shape",
            }
            quality_metric_keys = {
                "quality_coarse_application_residual_relative",
                "quality_coarse_rayleigh_quotient_drift_absolute",
                "quality_constant_field_prolongation_residual_inf",
                "quality_constant_field_restriction_residual_inf",
                "quality_fine_application_projection_residual_relative",
                "quality_fine_state_projection_residual_relative",
                "quality_galerkin_operator_residual_inf",
                "quality_mass_preservation_probe_absolute_error",
                "quality_mass_total_relative_error",
                "quality_normalized_transfer_adjoint_residual_inf",
                "quality_normalized_transfer_identity_residual_inf",
            }
            expected_coarse_operator_keys = {
                "root_id",
                "patch_count",
                "surface_vertex_count",
                "surface_to_patch",
                "patch_sizes",
                "patch_seed_vertices",
                "patch_centroids",
                "member_vertex_indices",
                "member_vertex_indptr",
                "mass_diagonal",
                "patch_areas",
                "fine_mass_total",
                "coarse_mass_total",
                "stiffness_data",
                "stiffness_indices",
                "stiffness_indptr",
                "stiffness_shape",
                "operator_data",
                "operator_indices",
                "operator_indptr",
                "operator_shape",
            } | quality_metric_keys
            expected_transfer_keys = {
                "root_id",
                "patch_count",
                "surface_vertex_count",
                "surface_to_patch",
                "patch_sizes",
                "member_vertex_indices",
                "member_vertex_indptr",
                "fine_mass_diagonal",
                "coarse_mass_diagonal",
                "fine_mass_total",
                "coarse_mass_total",
                "restriction_data",
                "restriction_indices",
                "restriction_indptr",
                "restriction_shape",
                "prolongation_data",
                "prolongation_indices",
                "prolongation_indptr",
                "prolongation_shape",
                "normalized_restriction_data",
                "normalized_restriction_indices",
                "normalized_restriction_indptr",
                "normalized_restriction_shape",
                "normalized_prolongation_data",
                "normalized_prolongation_indices",
                "normalized_prolongation_indptr",
                "normalized_prolongation_shape",
            } | quality_metric_keys

            self.assertTrue(expected_surface_keys.issubset(surface_graph_a))
            self.assertTrue(expected_patch_keys.issubset(patch_graph_a))
            self.assertTrue(expected_fine_operator_keys.issubset(fine_operator_a))
            self.assertTrue(expected_coarse_operator_keys.issubset(coarse_operator_a))
            self.assertTrue(expected_transfer_keys.issubset(transfer_ops_a))
            self.assertNotIn("patch_mask", surface_graph_a)
            self.assertNotIn("patch_vertices", surface_graph_a)

            n_vertices = int(surface_graph_a["vertices"].shape[0])
            surface_to_patch = surface_graph_a["surface_to_patch"]
            patch_count = int(surface_graph_a["patch_count"])
            patch_sizes = patch_graph_a["patch_sizes"]
            member_vertex_indices = patch_graph_a["member_vertex_indices"]
            member_vertex_indptr = patch_graph_a["member_vertex_indptr"]

            self.assertEqual(surface_to_patch.shape, (n_vertices,))
            self.assertGreater(patch_count, 1)
            self.assertEqual(int(patch_graph_a["patch_count"]), patch_count)
            self.assertEqual(int(patch_graph_a["surface_vertex_count"]), n_vertices)
            self.assertEqual(patch_sizes.shape, (patch_count,))
            self.assertEqual(int(patch_sizes.sum()), n_vertices)
            self.assertTrue(np.array_equal(patch_graph_a["surface_to_patch"], surface_to_patch))
            self.assertEqual(member_vertex_indptr.shape, (patch_count + 1,))
            self.assertEqual(member_vertex_indices.shape[0], n_vertices)
            self.assertTrue(np.array_equal(np.sort(member_vertex_indices), np.arange(n_vertices, dtype=np.int32)))

            reconstructed_surface_to_patch = np.full(n_vertices, -1, dtype=np.int32)
            for patch_id in range(patch_count):
                members = member_vertex_indices[member_vertex_indptr[patch_id] : member_vertex_indptr[patch_id + 1]]
                self.assertEqual(members.shape[0], int(patch_sizes[patch_id]))
                reconstructed_surface_to_patch[members] = patch_id
            self.assertTrue(np.array_equal(reconstructed_surface_to_patch, surface_to_patch))

            surface_adj = _load_csr(surface_graph_a, prefix="adj")
            surface_lap = _load_csr(surface_graph_a, prefix="lap")
            patch_adj = _load_csr(patch_graph_a, prefix="adj")
            patch_lap = _load_csr(patch_graph_a, prefix="lap")
            fine_adj = _load_csr(fine_operator_a, prefix="adj")
            edge_length_matrix = _load_csr(fine_operator_a, prefix="edge_length")
            cotangent_weight_matrix = _load_csr(fine_operator_a, prefix="cotangent_weight")
            stiffness = _load_csr(fine_operator_a, prefix="stiffness")
            operator = _load_csr(fine_operator_a, prefix="operator")
            coarse_stiffness = _load_csr(coarse_operator_a, prefix="stiffness")
            coarse_operator = _load_csr(coarse_operator_a, prefix="operator")
            restriction = _load_csr(transfer_ops_a, prefix="restriction")
            prolongation = _load_csr(transfer_ops_a, prefix="prolongation")
            normalized_restriction = _load_csr(transfer_ops_a, prefix="normalized_restriction")
            normalized_prolongation = _load_csr(transfer_ops_a, prefix="normalized_prolongation")

            self.assertEqual(surface_adj.shape, (n_vertices, n_vertices))
            self.assertEqual(surface_lap.shape, (n_vertices, n_vertices))
            self.assertEqual(patch_adj.shape, (patch_count, patch_count))
            self.assertEqual(patch_lap.shape, (patch_count, patch_count))
            self.assertEqual(fine_adj.shape, (n_vertices, n_vertices))
            self.assertEqual(edge_length_matrix.shape, (n_vertices, n_vertices))
            self.assertEqual(cotangent_weight_matrix.shape, (n_vertices, n_vertices))
            self.assertEqual(stiffness.shape, (n_vertices, n_vertices))
            self.assertEqual(operator.shape, (n_vertices, n_vertices))
            self.assertEqual(coarse_stiffness.shape, (patch_count, patch_count))
            self.assertEqual(coarse_operator.shape, (patch_count, patch_count))
            self.assertEqual(restriction.shape, (patch_count, n_vertices))
            self.assertEqual(prolongation.shape, (n_vertices, patch_count))
            self.assertEqual(normalized_restriction.shape, (patch_count, n_vertices))
            self.assertEqual(normalized_prolongation.shape, (n_vertices, patch_count))
            self.assertGreater(patch_adj.nnz, 0)
            self.assertTrue(np.allclose(restriction @ np.ones(n_vertices, dtype=np.float32), 1.0))
            self.assertTrue(np.allclose(prolongation @ np.ones(patch_count, dtype=np.float32), 1.0))
            self.assertTrue(
                np.allclose(normalized_restriction.toarray(), normalized_prolongation.toarray().T, atol=1e-6)
            )
            self.assertTrue(
                np.allclose(
                    (normalized_restriction @ normalized_prolongation).toarray(),
                    np.eye(patch_count),
                    atol=1e-6,
                )
            )
            self.assertTrue(np.array_equal(fine_operator_a["vertex_areas"], fine_operator_a["mass_diagonal"]))
            self.assertTrue(np.all(fine_operator_a["mass_diagonal"] > 0.0))
            self.assertTrue(np.all(coarse_operator_a["mass_diagonal"] > 0.0))
            self.assertTrue(np.allclose(coarse_operator_a["patch_areas"], coarse_operator_a["mass_diagonal"]))
            self.assertTrue(np.allclose(fine_adj.toarray(), surface_adj.toarray()))
            self.assertTrue(np.allclose(stiffness.toarray(), stiffness.toarray().T, atol=1e-6))
            self.assertTrue(np.allclose(operator.toarray(), operator.toarray().T, atol=1e-6))
            self.assertTrue(np.allclose(coarse_stiffness.toarray(), coarse_stiffness.toarray().T, atol=1e-6))
            self.assertTrue(np.allclose(coarse_operator.toarray(), coarse_operator.toarray().T, atol=1e-6))
            self.assertTrue(np.allclose(np.asarray(stiffness.sum(axis=1)).ravel(), 0.0, atol=1e-5))
            self.assertTrue(np.allclose(np.asarray(coarse_stiffness.sum(axis=1)).ravel(), 0.0, atol=1e-5))
            self.assertTrue(np.allclose(np.cross(fine_operator_a["tangent_u"], fine_operator_a["tangent_v"]), fine_operator_a["vertex_normals"], atol=1e-5))
            self.assertTrue(np.allclose(np.sum(fine_operator_a["tangent_u"] * fine_operator_a["vertex_normals"], axis=1), 0.0, atol=1e-5))
            self.assertTrue(np.allclose(np.sum(fine_operator_a["tangent_v"] * fine_operator_a["vertex_normals"], axis=1), 0.0, atol=1e-5))
            self.assertTrue(np.allclose(np.linalg.norm(fine_operator_a["vertex_normals"], axis=1), 1.0, atol=1e-5))
            self.assertTrue(np.allclose(np.linalg.norm(fine_operator_a["tangent_u"], axis=1), 1.0, atol=1e-5))
            self.assertTrue(np.allclose(np.linalg.norm(fine_operator_a["tangent_v"], axis=1), 1.0, atol=1e-5))
            self.assertEqual(int(np.count_nonzero(fine_operator_a["boundary_vertex_mask"])), 0)
            self.assertEqual(int(np.count_nonzero(fine_operator_a["boundary_edge_mask"])), 0)
            self.assertEqual(int(np.count_nonzero(fine_operator_a["boundary_face_mask"])), 0)
            self.assertEqual(fine_operator_a["edge_vertex_indices"].shape[0], surface_adj.nnz // 2)
            self.assertTrue(np.all(fine_operator_a["edge_lengths"] > 0.0))
            self.assertTrue(np.all(fine_operator_a["edge_face_counts"] == 2))
            geodesic_indptr = fine_operator_a["geodesic_neighbor_indptr"]
            geodesic_indices = fine_operator_a["geodesic_neighbor_indices"]
            geodesic_distances = fine_operator_a["geodesic_neighbor_distances"]
            geodesic_hops = fine_operator_a["geodesic_neighbor_hops"]
            self.assertEqual(geodesic_indptr.shape, (n_vertices + 1,))
            for vertex_index in range(n_vertices):
                start = int(geodesic_indptr[vertex_index])
                end = int(geodesic_indptr[vertex_index + 1])
                self.assertGreaterEqual(end - start, 1)
                self.assertEqual(int(geodesic_indices[start]), vertex_index)
                self.assertEqual(float(geodesic_distances[start]), 0.0)
                self.assertEqual(int(geodesic_hops[start]), 0)
                self.assertTrue(np.all(np.diff(geodesic_distances[start:end]) >= -1e-7))

            operator_eigenvalues = np.linalg.eigvalsh(operator.toarray())
            self.assertGreaterEqual(float(operator_eigenvalues.min()), -1e-5)
            coarse_operator_eigenvalues = np.linalg.eigvalsh(coarse_operator.toarray())
            self.assertGreaterEqual(float(coarse_operator_eigenvalues.min()), -1e-5)

            fine_mass = transfer_ops_a["fine_mass_diagonal"].astype(np.float64)
            coarse_mass = transfer_ops_a["coarse_mass_diagonal"].astype(np.float64)
            fine_probe = surface_graph_a["vertices"][:, 0].astype(np.float64)
            self.assertAlmostEqual(
                float(coarse_mass @ (restriction @ fine_probe)),
                float(fine_mass @ fine_probe),
                places=6,
            )
            self.assertAlmostEqual(
                float(transfer_ops_a["fine_mass_total"]),
                float(transfer_ops_a["coarse_mass_total"]),
                places=6,
            )
            self.assertAlmostEqual(
                float(coarse_operator_a["fine_mass_total"]),
                float(coarse_operator_a["coarse_mass_total"]),
                places=6,
            )
            for payload in (coarse_operator_a, transfer_ops_a):
                self.assertLessEqual(float(payload["quality_constant_field_restriction_residual_inf"]), 1e-7)
                self.assertLessEqual(float(payload["quality_constant_field_prolongation_residual_inf"]), 1e-7)
                self.assertLessEqual(float(payload["quality_mass_total_relative_error"]), 1e-7)
                self.assertLessEqual(float(payload["quality_mass_preservation_probe_absolute_error"]), 1e-7)
                self.assertLessEqual(float(payload["quality_normalized_transfer_identity_residual_inf"]), 1e-6)
                self.assertLessEqual(float(payload["quality_normalized_transfer_adjoint_residual_inf"]), 1e-7)
                self.assertLessEqual(float(payload["quality_galerkin_operator_residual_inf"]), 1e-6)
                self.assertLessEqual(float(payload["quality_coarse_application_residual_relative"]), 1e-6)
                self.assertLessEqual(float(payload["quality_coarse_rayleigh_quotient_drift_absolute"]), 1e-6)
                self.assertLessEqual(float(payload["quality_fine_state_projection_residual_relative"]), 0.75)
                self.assertLessEqual(float(payload["quality_fine_application_projection_residual_relative"]), 0.75)

            descriptor_payload = json.loads(bundle_paths_a.descriptor_sidecar_path.read_text(encoding="utf-8"))
            qa_payload = json.loads(bundle_paths_a.qa_sidecar_path.read_text(encoding="utf-8"))
            operator_metadata = load_operator_bundle_metadata(bundle_paths_a.operator_metadata_path)

            self.assertEqual(descriptor_payload["patch_generation_method"], "deterministic_bfs_partition")
            self.assertEqual(descriptor_payload["patch_count"], patch_count)
            self.assertEqual(descriptor_payload["surface_to_patch_count"], n_vertices)
            self.assertEqual(descriptor_payload["patch_membership_index_count"], n_vertices)
            self.assertEqual(descriptor_payload["raw_mesh_path"], str(bundle_paths_a.raw_mesh_path))
            self.assertEqual(descriptor_payload["raw_skeleton_path"], str(bundle_paths_a.raw_skeleton_path))
            self.assertEqual(descriptor_payload["patch_graph_edge_count"], int(patch_adj.nnz // 2))
            self.assertIn("representations", descriptor_payload)
            self.assertEqual(descriptor_payload["representations"]["raw_mesh"]["face_count"], 8)
            self.assertEqual(descriptor_payload["representations"]["simplified_mesh"]["component_count"], 1)
            self.assertGreater(descriptor_payload["representations"]["coarse_patches"]["max_patch_vertex_fraction"], 0.0)
            self.assertTrue(descriptor_payload["representations"]["skeleton"]["available"])
            self.assertEqual(descriptor_payload["representations"]["skeleton"]["segment_count"], 3)
            self.assertIn("derived_relations", descriptor_payload)
            self.assertTrue(qa_payload["surface_to_patch_is_complete"])
            self.assertTrue(qa_payload["patch_membership_covers_surface"])
            self.assertTrue(qa_payload["patch_graph_node_count_matches_mapping"])
            self.assertEqual(qa_payload["summary"]["overall_status"], "pass")
            self.assertTrue(qa_payload["summary"]["downstream_usable"])
            self.assertEqual(qa_payload["checks"]["simplified_surface_area_rel_error"]["status"], "pass")
            self.assertEqual(qa_payload["checks"]["coarse_component_count_delta"]["status"], "pass")
            self.assertEqual(operator_metadata["contract_version"], "operator_bundle.v1")
            self.assertEqual(operator_metadata["realization_mode"], "cotangent_fem_galerkin_patch_multiresolution")
            self.assertEqual(operator_metadata["discretization_family"], "triangle_mesh_cotangent_fem")
            self.assertEqual(operator_metadata["mass_treatment"], "lumped_mass")
            self.assertEqual(operator_metadata["normalization"], "mass_normalized")
            self.assertEqual(operator_metadata["weighting_scheme"], "cotangent_half_weight")
            self.assertEqual(
                operator_metadata["coarse_discretization_family"],
                "piecewise_constant_patch_galerkin_on_triangle_mesh_cotangent_fem",
            )
            self.assertEqual(operator_metadata["coarse_mass_treatment"], "patch_aggregated_lumped_mass")
            self.assertEqual(
                operator_metadata["coarse_operator_construction"]["coarse_stiffness"],
                "galerkin_projection_PtKP",
            )
            self.assertEqual(operator_metadata["operator_matrix_role"], "symmetric_mass_normalized_stiffness")
            self.assertEqual(
                operator_metadata["orientation_convention"]["tangent_frame"],
                "right_handed",
            )
            self.assertTrue(operator_metadata["transfer_operators"]["fine_to_coarse_restriction"]["available"])
            self.assertEqual(
                operator_metadata["transfer_operators"]["fine_to_coarse_restriction"]["normalization"],
                "lumped_mass_patch_average",
            )
            self.assertTrue(
                operator_metadata["transfer_operators"]["fine_to_coarse_restriction"]["preserves_mass_or_area_totals"]
            )
            self.assertTrue(operator_metadata["transfer_operators"]["normalized_state_transfer"]["available"])
            self.assertFalse(operator_metadata["fallback_policy"]["used"])
            self.assertEqual(operator_metadata["geodesic_neighborhood"]["mode"], "edge_path_dijkstra_hop_capped")
            self.assertEqual(operator_metadata["geodesic_neighborhood"]["max_hops"], 2)
            self.assertEqual(operator_metadata["geodesic_neighborhood"]["max_vertices_per_seed"], 32)
            self.assertEqual(
                operator_metadata["assets"]["fine_operator"]["path"],
                str(bundle_paths_a.fine_operator_path),
            )
            self.assertNotIn("legacy_alias", operator_metadata["assets"]["fine_operator"])
            self.assertEqual(
                operator_metadata["assets"]["coarse_operator"]["path"],
                str(bundle_paths_a.coarse_operator_path),
            )
            self.assertNotIn("legacy_alias", operator_metadata["assets"]["coarse_operator"])
            self.assertLessEqual(
                float(operator_metadata["coarse_operator_quality_metrics"]["galerkin_operator_residual_inf"]),
                1e-6,
            )
            self.assertLessEqual(
                float(operator_metadata["coarse_operator_quality_metrics"]["coarse_application_residual_relative"]),
                1e-6,
            )

            self.assertEqual(outputs_a["bundle_metadata"]["patch_count"], patch_count)
            self.assertEqual(outputs_a["bundle_metadata"]["surface_to_patch_count"], n_vertices)
            self.assertEqual(outputs_a["bundle_metadata"]["patch_generation_method"], "deterministic_bfs_partition")
            self.assertEqual(outputs_a["bundle_metadata"]["fine_geodesic_hops"], 2)
            self.assertEqual(outputs_a["bundle_metadata"]["fine_geodesic_vertex_cap"], 32)
            self.assertAlmostEqual(
                float(outputs_a["bundle_metadata"]["coarse_mass_total"]),
                float(coarse_operator_a["coarse_mass_total"]),
                places=6,
            )
            self.assertEqual(outputs_a["bundle_metadata"]["qa_overall_status"], "pass")
            self.assertEqual(outputs_b["bundle_metadata"], outputs_a["bundle_metadata"])
            self.assertEqual(outputs_a["operator_bundle_metadata"], operator_metadata)

            for key in expected_surface_keys:
                self.assertTrue(
                    np.array_equal(surface_graph_a[key], surface_graph_b[key]),
                    msg=f"surface graph key {key!r} changed across identical builds",
                )
            for key in expected_patch_keys:
                self.assertTrue(
                    np.array_equal(patch_graph_a[key], patch_graph_b[key]),
                    msg=f"patch graph key {key!r} changed across identical builds",
                )
            for key in expected_coarse_operator_keys:
                self.assertTrue(
                    np.array_equal(coarse_operator_a[key], coarse_operator_b[key]),
                    msg=f"coarse operator key {key!r} changed across identical builds",
                )
            for key in expected_transfer_keys:
                self.assertTrue(
                    np.array_equal(transfer_ops_a[key], transfer_ops_b[key]),
                    msg=f"transfer operator key {key!r} changed across identical builds",
                )
            for key in expected_fine_operator_keys:
                self.assertTrue(
                    np.array_equal(fine_operator_a[key], fine_operator_b[key]),
                    msg=f"fine operator key {key!r} changed across identical builds",
                )

    def test_process_mesh_applies_threshold_overrides_to_warn_and_fail(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            bundle_paths_warn = _bundle_paths(tmp_dir / "warn")
            bundle_paths_fail = _bundle_paths(tmp_dir / "fail")

            _write_octahedron_mesh(bundle_paths_warn.raw_mesh_path)
            _write_octahedron_mesh(bundle_paths_fail.raw_mesh_path)

            warn_outputs = process_mesh_into_wave_assets(
                root_id=101,
                bundle_paths=bundle_paths_warn,
                simplify_target_faces=8,
                patch_hops=1,
                patch_vertex_cap=2,
                qa_thresholds={
                    "coarse_max_patch_vertex_fraction": {
                        "warn": 0.3,
                        "fail": 0.4,
                        "blocking": False,
                    }
                },
            )
            fail_outputs = process_mesh_into_wave_assets(
                root_id=101,
                bundle_paths=bundle_paths_fail,
                simplify_target_faces=8,
                patch_hops=1,
                patch_vertex_cap=2,
                qa_thresholds={
                    "coarse_max_patch_vertex_fraction": {
                        "warn": 0.2,
                        "fail": 0.3,
                        "blocking": True,
                    }
                },
            )

            warn_payload = json.loads(bundle_paths_warn.qa_sidecar_path.read_text(encoding="utf-8"))
            fail_payload = json.loads(bundle_paths_fail.qa_sidecar_path.read_text(encoding="utf-8"))

            self.assertEqual(warn_payload["checks"]["coarse_max_patch_vertex_fraction"]["status"], "warn")
            self.assertEqual(warn_payload["summary"]["overall_status"], "warn")
            self.assertTrue(warn_payload["summary"]["downstream_usable"])
            self.assertEqual(warn_outputs["bundle_metadata"]["qa_warning_count"], 1)

            self.assertEqual(fail_payload["checks"]["coarse_max_patch_vertex_fraction"]["status"], "fail")
            self.assertEqual(fail_payload["summary"]["overall_status"], "fail")
            self.assertFalse(fail_payload["summary"]["downstream_usable"])
            self.assertEqual(fail_outputs["bundle_metadata"]["qa_blocking_failure_count"], 1)


def _bundle_paths(tmp_dir: Path):
    return build_geometry_bundle_paths(
        101,
        meshes_raw_dir=tmp_dir / "meshes_raw",
        skeletons_raw_dir=tmp_dir / "skeletons_raw",
        processed_mesh_dir=tmp_dir / "processed_meshes",
        processed_graph_dir=tmp_dir / "processed_graphs",
    )


def _read_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as payload:
        return {key: payload[key] for key in payload.files}


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


def _write_octahedron_mesh(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """
            ply
            format ascii 1.0
            element vertex 6
            property float x
            property float y
            property float z
            element face 8
            property list uchar int vertex_indices
            end_header
            0 0 1
            1 0 0
            0 1 0
            -1 0 0
            0 -1 0
            0 0 -1
            3 0 1 2
            3 0 2 3
            3 0 3 4
            3 0 4 1
            3 5 2 1
            3 5 3 2
            3 5 4 3
            3 5 1 4
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_stub_swc(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# stub skeleton",
                "1 1 0 0 1 1 -1",
                "2 3 1 0 0 1 1",
                "3 3 0 1 0 1 1",
                "4 3 0 0 -1 1 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
