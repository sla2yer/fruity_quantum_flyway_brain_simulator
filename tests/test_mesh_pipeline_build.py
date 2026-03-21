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
            patch_graph_a = _read_npz(bundle_paths_a.patch_graph_path)
            surface_graph_b = _read_npz(bundle_paths_b.surface_graph_path)
            patch_graph_b = _read_npz(bundle_paths_b.patch_graph_path)

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

            self.assertTrue(expected_surface_keys.issubset(surface_graph_a))
            self.assertTrue(expected_patch_keys.issubset(patch_graph_a))
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

            self.assertEqual(surface_adj.shape, (n_vertices, n_vertices))
            self.assertEqual(surface_lap.shape, (n_vertices, n_vertices))
            self.assertEqual(patch_adj.shape, (patch_count, patch_count))
            self.assertEqual(patch_lap.shape, (patch_count, patch_count))
            self.assertGreater(patch_adj.nnz, 0)

            descriptor_payload = json.loads(bundle_paths_a.descriptor_sidecar_path.read_text(encoding="utf-8"))
            qa_payload = json.loads(bundle_paths_a.qa_sidecar_path.read_text(encoding="utf-8"))

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

            self.assertEqual(outputs_a["bundle_metadata"]["patch_count"], patch_count)
            self.assertEqual(outputs_a["bundle_metadata"]["surface_to_patch_count"], n_vertices)
            self.assertEqual(outputs_a["bundle_metadata"]["patch_generation_method"], "deterministic_bfs_partition")
            self.assertEqual(outputs_a["bundle_metadata"]["qa_overall_status"], "pass")
            self.assertEqual(outputs_b["bundle_metadata"], outputs_a["bundle_metadata"])

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
