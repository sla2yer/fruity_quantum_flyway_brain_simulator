from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from unittest import mock
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.geometry_contract import build_geometry_bundle_paths
from flywire_wave.mesh_pipeline import process_mesh_into_wave_assets
from flywire_wave.synapse_mapping import (
    ANCHOR_TYPE_POINT_STATE,
    ANCHOR_TYPE_SKELETON_NODE,
    ANCHOR_TYPE_SURFACE_PATCH,
    MAPPING_STATUS_BLOCKED,
    MAPPING_STATUS_MAPPED,
    QUALITY_STATUS_OK,
    RootContext,
    _build_root_context,
    _build_root_local_nearest_neighbor_index,
    _skeleton_mapping,
    _surface_patch_mapping,
    load_root_anchor_map,
    lookup_edge_synapses,
    lookup_inbound_synapses,
    lookup_outbound_synapses,
    materialize_synapse_anchor_maps,
)


class SynapseAnchorMappingTest(unittest.TestCase):
    def test_build_root_context_caches_root_local_lookup_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            coupling_dir = tmp_dir / "processed_coupling"

            bundle_paths_101 = build_geometry_bundle_paths(
                101,
                meshes_raw_dir=tmp_dir / "meshes_raw",
                skeletons_raw_dir=tmp_dir / "skeletons_raw",
                processed_mesh_dir=tmp_dir / "processed_meshes",
                processed_graph_dir=tmp_dir / "processed_graphs",
            )
            _write_octahedron_mesh(bundle_paths_101.raw_mesh_path)
            process_mesh_into_wave_assets(
                root_id=101,
                bundle_paths=bundle_paths_101,
                simplify_target_faces=8,
                patch_hops=1,
                patch_vertex_cap=2,
                registry_metadata={"cell_type": "T5a", "project_role": "surface_simulated"},
            )

            bundle_paths_202 = build_geometry_bundle_paths(
                202,
                meshes_raw_dir=tmp_dir / "meshes_raw",
                skeletons_raw_dir=tmp_dir / "skeletons_raw",
                processed_mesh_dir=tmp_dir / "processed_meshes",
                processed_graph_dir=tmp_dir / "processed_graphs",
            )
            _write_stub_swc(bundle_paths_202.raw_skeleton_path)

            synapse_registry_path = coupling_dir / "synapse_registry.csv"
            _write_synapse_registry(synapse_registry_path)
            root_synapses = pd.read_csv(synapse_registry_path)

            surface_context = _build_root_context(
                root_id=101,
                project_role="surface_simulated",
                root_synapses=root_synapses,
                meshes_raw_dir=tmp_dir / "meshes_raw",
                skeletons_raw_dir=tmp_dir / "skeletons_raw",
                processed_mesh_dir=tmp_dir / "processed_meshes",
                processed_graph_dir=tmp_dir / "processed_graphs",
            )
            skeleton_context = _build_root_context(
                root_id=202,
                project_role="skeleton_simulated",
                root_synapses=root_synapses,
                meshes_raw_dir=tmp_dir / "meshes_raw",
                skeletons_raw_dir=tmp_dir / "skeletons_raw",
                processed_mesh_dir=tmp_dir / "processed_meshes",
                processed_graph_dir=tmp_dir / "processed_graphs",
            )

            self.assertIsNotNone(surface_context.surface_support_index)
            self.assertIsNone(surface_context.skeleton_support_index)
            self.assertIsNone(skeleton_context.surface_support_index)
            self.assertIsNotNone(skeleton_context.skeleton_support_index)

    def test_root_local_lookup_reuses_indices_and_preserves_lowest_support_tie_break(self) -> None:
        surface_vertices = np.asarray(
            [
                [-1.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
            ],
            dtype=np.float64,
        )
        skeleton_points = np.asarray(
            [
                [-2.0, 0.0, 0.0],
                [2.0, 0.0, 0.0],
            ],
            dtype=np.float64,
        )
        context = RootContext(
            root_id=999,
            project_role="surface_simulated",
            supported_modes=("surface_patch_cloud", "skeleton_segment_cloud"),
            surface_vertices=surface_vertices,
            surface_support_index=_build_root_local_nearest_neighbor_index(surface_vertices),
            surface_to_patch=np.asarray([0, 1], dtype=np.int32),
            patch_centroids=surface_vertices.copy(),
            patch_radii=np.asarray([1.0, 1.0], dtype=np.float64),
            skeleton_node_ids=np.asarray([10, 20], dtype=np.int64),
            skeleton_points=skeleton_points,
            skeleton_support_index=_build_root_local_nearest_neighbor_index(skeleton_points),
            skeleton_local_scales=np.asarray([1.5, 1.5], dtype=np.float64),
            point_incoming_anchor=np.full(3, np.nan, dtype=np.float64),
            point_incoming_radius=float("nan"),
            point_outgoing_anchor=np.full(3, np.nan, dtype=np.float64),
            point_outgoing_radius=float("nan"),
            surface_unavailable_reason="",
            skeleton_unavailable_reason="",
            point_incoming_unavailable_reason="",
            point_outgoing_unavailable_reason="",
        )
        original_norm = np.linalg.norm

        def guarded_norm(values, *args, **kwargs):
            axis = kwargs.get("axis")
            shape = np.shape(values)
            if axis == 1 and shape in {surface_vertices.shape, skeleton_points.shape}:
                raise AssertionError("full geometry nearest-neighbor scan should not run during mapping")
            return original_norm(values, *args, **kwargs)

        with mock.patch("flywire_wave.synapse_mapping.np.linalg.norm", side_effect=guarded_norm):
            surface_mapping = _surface_patch_mapping(
                context=context,
                query_point=np.asarray([0.0, 0.0, 0.0], dtype=np.float64),
            )
            skeleton_mapping = _skeleton_mapping(
                context=context,
                query_point=np.asarray([0.0, 0.0, 0.0], dtype=np.float64),
            )

        assert surface_mapping is not None
        assert skeleton_mapping is not None
        self.assertEqual(int(surface_mapping["support_index"]), 0)
        self.assertEqual(int(surface_mapping["anchor_index"]), 0)
        self.assertAlmostEqual(float(surface_mapping["support_distance"]), 1.0, places=9)
        self.assertEqual(int(skeleton_mapping["support_index"]), 0)
        self.assertEqual(int(skeleton_mapping["anchor_index"]), 10)
        self.assertAlmostEqual(float(skeleton_mapping["support_distance"]), 2.0, places=9)

    def test_materialize_synapse_anchor_maps_maps_surface_and_fallbacks_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            coupling_dir = tmp_dir / "processed_coupling"

            bundle_paths_101 = build_geometry_bundle_paths(
                101,
                meshes_raw_dir=tmp_dir / "meshes_raw",
                skeletons_raw_dir=tmp_dir / "skeletons_raw",
                processed_mesh_dir=tmp_dir / "processed_meshes",
                processed_graph_dir=tmp_dir / "processed_graphs",
            )
            _write_octahedron_mesh(bundle_paths_101.raw_mesh_path)
            process_mesh_into_wave_assets(
                root_id=101,
                bundle_paths=bundle_paths_101,
                simplify_target_faces=8,
                patch_hops=1,
                patch_vertex_cap=2,
                registry_metadata={"cell_type": "T5a", "project_role": "surface_simulated"},
            )

            bundle_paths_202 = build_geometry_bundle_paths(
                202,
                meshes_raw_dir=tmp_dir / "meshes_raw",
                skeletons_raw_dir=tmp_dir / "skeletons_raw",
                processed_mesh_dir=tmp_dir / "processed_meshes",
                processed_graph_dir=tmp_dir / "processed_graphs",
            )
            _write_stub_swc(bundle_paths_202.raw_skeleton_path)

            synapse_registry_path = coupling_dir / "synapse_registry.csv"
            _write_synapse_registry(synapse_registry_path)

            neuron_registry = pd.DataFrame(
                {
                    "root_id": [101, 202, 303],
                    "project_role": ["surface_simulated", "skeleton_simulated", "point_simulated"],
                }
            )

            first_summary = materialize_synapse_anchor_maps(
                root_ids=[101, 202, 303],
                processed_coupling_dir=coupling_dir,
                meshes_raw_dir=tmp_dir / "meshes_raw",
                skeletons_raw_dir=tmp_dir / "skeletons_raw",
                processed_mesh_dir=tmp_dir / "processed_meshes",
                processed_graph_dir=tmp_dir / "processed_graphs",
                neuron_registry=neuron_registry,
                synapse_registry_path=synapse_registry_path,
            )
            second_summary = materialize_synapse_anchor_maps(
                root_ids=[101, 202, 303],
                processed_coupling_dir=coupling_dir,
                meshes_raw_dir=tmp_dir / "meshes_raw",
                skeletons_raw_dir=tmp_dir / "skeletons_raw",
                processed_mesh_dir=tmp_dir / "processed_meshes",
                processed_graph_dir=tmp_dir / "processed_graphs",
                neuron_registry=neuron_registry,
                synapse_registry_path=synapse_registry_path,
            )

            self.assertEqual(first_summary["synapse_count"], 3)
            self.assertEqual(first_summary["edge_count"], 2)
            self.assertEqual(first_summary["root_summaries"], second_summary["root_summaries"])
            self.assertEqual(first_summary["bundle_metadata_by_root"][101]["status"], "partial")
            self.assertEqual(first_summary["bundle_metadata_by_root"][202]["status"], "partial")
            self.assertEqual(first_summary["bundle_metadata_by_root"][303]["status"], "ready")

            incoming_101 = lookup_inbound_synapses(101, processed_coupling_dir=coupling_dir)
            outgoing_202 = lookup_outbound_synapses(202, processed_coupling_dir=coupling_dir, post_root_id=101)
            outgoing_101 = lookup_outbound_synapses(101, processed_coupling_dir=coupling_dir, post_root_id=303)
            incoming_303 = lookup_inbound_synapses(303, processed_coupling_dir=coupling_dir, pre_root_id=101)
            edge_202_101 = lookup_edge_synapses(202, 101, processed_coupling_dir=coupling_dir)
            edge_101_303 = lookup_edge_synapses(101, 303, processed_coupling_dir=coupling_dir)

            pd.testing.assert_frame_equal(
                incoming_101,
                lookup_inbound_synapses(101, processed_coupling_dir=coupling_dir),
            )
            pd.testing.assert_frame_equal(
                edge_202_101,
                lookup_edge_synapses(202, 101, processed_coupling_dir=coupling_dir),
            )

            self.assertEqual(incoming_101["synapse_id"].tolist(), ["edge-a", "edge-b"])
            self.assertTrue((incoming_101["anchor_type"] == ANCHOR_TYPE_SURFACE_PATCH).all())
            self.assertTrue((incoming_101["mapping_status"] == MAPPING_STATUS_MAPPED).all())
            self.assertTrue((incoming_101["quality_status"] == QUALITY_STATUS_OK).all())

            with np.load(bundle_paths_101.surface_graph_path, allow_pickle=False) as surface_payload:
                surface_to_patch = np.asarray(surface_payload["surface_to_patch"], dtype=np.int64)
            self.assertEqual(
                int(incoming_101.loc[incoming_101["synapse_id"] == "edge-a", "anchor_index"].iloc[0]),
                int(surface_to_patch[0]),
            )
            self.assertEqual(
                int(incoming_101.loc[incoming_101["synapse_id"] == "edge-b", "anchor_index"].iloc[0]),
                int(surface_to_patch[1]),
            )

            self.assertEqual(outgoing_202["synapse_id"].tolist(), ["edge-a", "edge-b"])
            mapped_row = outgoing_202.loc[outgoing_202["synapse_id"] == "edge-a"].iloc[0]
            blocked_row = outgoing_202.loc[outgoing_202["synapse_id"] == "edge-b"].iloc[0]
            self.assertEqual(mapped_row["anchor_type"], ANCHOR_TYPE_SKELETON_NODE)
            self.assertEqual(int(mapped_row["anchor_index"]), 3)
            self.assertEqual(mapped_row["mapping_status"], MAPPING_STATUS_MAPPED)
            self.assertEqual(blocked_row["mapping_status"], MAPPING_STATUS_BLOCKED)
            self.assertEqual(blocked_row["blocked_reason"], "missing_presynaptic_query_coordinates")

            self.assertEqual(outgoing_101["synapse_id"].tolist(), ["edge-c"])
            self.assertEqual(outgoing_101.iloc[0]["anchor_type"], ANCHOR_TYPE_SURFACE_PATCH)
            self.assertEqual(incoming_303["synapse_id"].tolist(), ["edge-c"])
            self.assertEqual(incoming_303.iloc[0]["anchor_type"], ANCHOR_TYPE_POINT_STATE)
            self.assertAlmostEqual(float(incoming_303.iloc[0]["anchor_distance"]), 0.0, places=7)
            self.assertAlmostEqual(float(incoming_303.iloc[0]["anchor_x"]), 5.0, places=7)

            self.assertEqual(edge_202_101["synapse_id"].tolist(), ["edge-a", "edge-b"])
            self.assertEqual(
                edge_202_101.loc[edge_202_101["synapse_id"] == "edge-a", "pre_anchor_type"].iloc[0],
                ANCHOR_TYPE_SKELETON_NODE,
            )
            self.assertEqual(
                edge_202_101.loc[edge_202_101["synapse_id"] == "edge-b", "pre_mapping_status"].iloc[0],
                MAPPING_STATUS_BLOCKED,
            )
            self.assertEqual(
                edge_202_101.loc[edge_202_101["synapse_id"] == "edge-b", "post_anchor_type"].iloc[0],
                ANCHOR_TYPE_SURFACE_PATCH,
            )
            self.assertEqual(edge_101_303["synapse_id"].tolist(), ["edge-c"])
            self.assertEqual(edge_101_303.iloc[0]["post_anchor_type"], ANCHOR_TYPE_POINT_STATE)

            anchor_map_202 = load_root_anchor_map(coupling_dir / "roots" / "202_outgoing_anchor_map.npz")
            self.assertEqual(anchor_map_202.root_id, 202)
            self.assertEqual(anchor_map_202.relation_to_root, "outgoing")
            self.assertEqual(anchor_map_202.peer_root_ids.tolist(), [101])
            self.assertEqual(anchor_map_202.peer_root_indptr.tolist(), [0, 2])

            index_101 = json.loads((coupling_dir / "roots" / "101_coupling_index.json").read_text(encoding="utf-8"))
            self.assertEqual(index_101["incoming_anchor_map"]["status"], "ready")
            self.assertEqual(index_101["outgoing_anchor_map"]["status"], "ready")
            self.assertEqual(index_101["incoming_edges"][0]["status"], "partial")
            self.assertIn("mapped_with_fallback", index_101["mapping_status_definitions"])
            self.assertIn("warn", index_101["quality_status_definitions"])


def _write_synapse_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "synapse_row_id": "fixture.csv#1",
                "source_row_number": 1,
                "synapse_id": "edge-a",
                "pre_root_id": 202,
                "post_root_id": 101,
                "x": 0.0,
                "y": 0.5,
                "z": 0.5,
                "pre_x": 0.0,
                "pre_y": 1.0,
                "pre_z": 0.0,
                "post_x": 0.0,
                "post_y": 0.0,
                "post_z": 1.0,
                "neuropil": "LOP_R",
                "nt_type": "ACH",
                "sign": "excitatory",
                "confidence": 0.99,
                "weight": 1.0,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
            {
                "synapse_row_id": "fixture.csv#2",
                "source_row_number": 2,
                "synapse_id": "edge-b",
                "pre_root_id": 202,
                "post_root_id": 101,
                "x": np.nan,
                "y": np.nan,
                "z": np.nan,
                "pre_x": np.nan,
                "pre_y": np.nan,
                "pre_z": np.nan,
                "post_x": 1.0,
                "post_y": 0.0,
                "post_z": 0.0,
                "neuropil": "LOP_R",
                "nt_type": "ACH",
                "sign": "excitatory",
                "confidence": 0.75,
                "weight": 0.5,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
            {
                "synapse_row_id": "fixture.csv#3",
                "source_row_number": 3,
                "synapse_id": "edge-c",
                "pre_root_id": 101,
                "post_root_id": 303,
                "x": 5.0,
                "y": 5.0,
                "z": 5.0,
                "pre_x": 1.0,
                "pre_y": 0.0,
                "pre_z": 0.0,
                "post_x": np.nan,
                "post_y": np.nan,
                "post_z": np.nan,
                "neuropil": "ME_R",
                "nt_type": "GABA",
                "sign": "inhibitory",
                "confidence": 0.88,
                "weight": -1.0,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
        ]
    ).to_csv(path, index=False)


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
