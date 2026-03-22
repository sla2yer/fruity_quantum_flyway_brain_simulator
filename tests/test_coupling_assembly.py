from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.geometry_contract import build_geometry_bundle_paths
from flywire_wave.mesh_pipeline import process_mesh_into_wave_assets
from flywire_wave.synapse_mapping import (
    lookup_edge_blocked_synapses,
    lookup_edge_coupling_bundle,
    materialize_synapse_anchor_maps,
)


class CouplingAssemblyFixtureTest(unittest.TestCase):
    def test_edge_coupling_bundle_serializes_deterministically_and_preserves_sign_delay_and_aggregation(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            bundle_a = _materialize_fixture(tmp_dir / "run_a")
            bundle_b = _materialize_fixture(tmp_dir / "run_b")

            self.assertEqual(bundle_a.status, "partial")
            self.assertEqual(bundle_a.topology_family, "distributed_patch_cloud")
            self.assertEqual(bundle_a.kernel_family, "separable_rank_one_cloud")
            self.assertEqual(bundle_a.sign_representation, "categorical_sign_with_signed_weight")
            self.assertEqual(bundle_a.delay_model, "euclidean_anchor_distance_over_velocity")
            self.assertEqual(bundle_a.aggregation_rule, "sum_over_synapses_preserving_sign_and_delay_bins")
            self.assertEqual(bundle_a.blocked_synapse_table["synapse_id"].tolist(), ["edge-e"])
            self.assertEqual(bundle_a.component_table["synapse_count"].sum(), 4)
            self.assertTrue((bundle_a.component_table["source_cloud_normalization"] == "sum_to_one_per_component").all())
            self.assertTrue((bundle_a.component_table["target_cloud_normalization"] == "sum_to_one_per_component").all())

            pd.testing.assert_frame_equal(bundle_a.synapse_table, bundle_b.synapse_table)
            pd.testing.assert_frame_equal(bundle_a.component_table, bundle_b.component_table)
            pd.testing.assert_frame_equal(bundle_a.blocked_synapse_table, bundle_b.blocked_synapse_table)
            pd.testing.assert_frame_equal(bundle_a.source_anchor_table, bundle_b.source_anchor_table)
            pd.testing.assert_frame_equal(bundle_a.target_anchor_table, bundle_b.target_anchor_table)
            pd.testing.assert_frame_equal(bundle_a.source_cloud_table, bundle_b.source_cloud_table)
            pd.testing.assert_frame_equal(bundle_a.target_cloud_table, bundle_b.target_cloud_table)
            pd.testing.assert_frame_equal(bundle_a.component_synapse_table, bundle_b.component_synapse_table)

            membership = bundle_a.component_synapse_table.sort_values(
                ["source_row_number", "synapse_row_id"],
                kind="mergesort",
            ).reset_index(drop=True)
            raw_synapses = bundle_a.synapse_table.sort_values(
                ["source_row_number", "synapse_row_id"],
                kind="mergesort",
            ).reset_index(drop=True)
            membership_join = membership.merge(
                raw_synapses.loc[
                    :,
                    [
                        "synapse_row_id",
                        "weight",
                        "pre_anchor_x",
                        "pre_anchor_y",
                        "pre_anchor_z",
                        "post_anchor_x",
                        "post_anchor_y",
                        "post_anchor_z",
                    ],
                ],
                on="synapse_row_id",
                how="left",
                validate="one_to_one",
            )
            expected_delay_ms = (
                np.linalg.norm(
                    membership_join.loc[:, ["pre_anchor_x", "pre_anchor_y", "pre_anchor_z"]].to_numpy(dtype=float)
                    - membership_join.loc[:, ["post_anchor_x", "post_anchor_y", "post_anchor_z"]].to_numpy(dtype=float),
                    axis=1,
                )
                / 2.0
            ) + 0.25
            np.testing.assert_allclose(
                membership_join["delay_ms"].to_numpy(dtype=float),
                expected_delay_ms,
                rtol=0.0,
                atol=1.0e-9,
            )

            grouped_membership = (
                membership.groupby(["sign_label", "delay_bin_label"], sort=True, dropna=False)
                .agg(
                    synapse_count=("synapse_row_id", "count"),
                    signed_weight_total=("signed_weight", "sum"),
                    absolute_weight_total=("absolute_weight", "sum"),
                )
                .reset_index()
                .sort_values(["sign_label", "delay_bin_label"], kind="mergesort")
                .reset_index(drop=True)
            )
            grouped_components = (
                bundle_a.component_table.loc[
                    :,
                    ["sign_label", "delay_bin_label", "synapse_count", "signed_weight_total", "absolute_weight_total"],
                ]
                .sort_values(["sign_label", "delay_bin_label"], kind="mergesort")
                .reset_index(drop=True)
            )
            pd.testing.assert_frame_equal(grouped_components, grouped_membership)
            self.assertIn(3, grouped_components["synapse_count"].tolist())

            for component_index in bundle_a.component_table["component_index"].tolist():
                source_cloud = bundle_a.source_cloud_table.loc[
                    bundle_a.source_cloud_table["component_index"] == int(component_index)
                ]
                target_cloud = bundle_a.target_cloud_table.loc[
                    bundle_a.target_cloud_table["component_index"] == int(component_index)
                ]
                self.assertAlmostEqual(float(source_cloud["cloud_weight"].sum()), 1.0, places=9)
                self.assertAlmostEqual(float(target_cloud["cloud_weight"].sum()), 1.0, places=9)

            blocked = lookup_edge_blocked_synapses(202, 101, processed_coupling_dir=tmp_dir / "run_a" / "processed_coupling")
            self.assertEqual(blocked["synapse_id"].tolist(), ["edge-e"])


def _materialize_fixture(base_dir: Path):
    coupling_dir = base_dir / "processed_coupling"

    bundle_paths_101 = build_geometry_bundle_paths(
        101,
        meshes_raw_dir=base_dir / "meshes_raw",
        skeletons_raw_dir=base_dir / "skeletons_raw",
        processed_mesh_dir=base_dir / "processed_meshes",
        processed_graph_dir=base_dir / "processed_graphs",
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
        meshes_raw_dir=base_dir / "meshes_raw",
        skeletons_raw_dir=base_dir / "skeletons_raw",
        processed_mesh_dir=base_dir / "processed_meshes",
        processed_graph_dir=base_dir / "processed_graphs",
    )
    _write_stub_swc(bundle_paths_202.raw_skeleton_path)
    _write_synapse_registry(coupling_dir / "synapse_registry.csv")

    neuron_registry = pd.DataFrame(
        {
            "root_id": [101, 202],
            "project_role": ["surface_simulated", "skeleton_simulated"],
        }
    )
    summary = materialize_synapse_anchor_maps(
        root_ids=[101, 202],
        processed_coupling_dir=coupling_dir,
        meshes_raw_dir=base_dir / "meshes_raw",
        skeletons_raw_dir=base_dir / "skeletons_raw",
        processed_mesh_dir=base_dir / "processed_meshes",
        processed_graph_dir=base_dir / "processed_graphs",
        neuron_registry=neuron_registry,
        synapse_registry_path=coupling_dir / "synapse_registry.csv",
        coupling_assembly={
            "kernel_family": "separable_rank_one_cloud",
            "delay_model": {
                "mode": "euclidean_anchor_distance_over_velocity",
                "base_delay_ms": 0.25,
                "velocity_distance_units_per_ms": 2.0,
                "delay_bin_size_ms": 10.0,
            },
        },
    )
    assert summary["edge_count"] == 1
    return lookup_edge_coupling_bundle(202, 101, processed_coupling_dir=coupling_dir)


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
                "y": 0.0,
                "z": 0.0,
                "pre_x": 1.0,
                "pre_y": 0.0,
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
                "x": 0.0,
                "y": 0.2,
                "z": 0.0,
                "pre_x": 0.0,
                "pre_y": 1.0,
                "pre_z": 0.0,
                "post_x": 1.0,
                "post_y": 0.0,
                "post_z": 0.0,
                "neuropil": "LOP_R",
                "nt_type": "ACH",
                "sign": "excitatory",
                "confidence": 0.95,
                "weight": 0.5,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
            {
                "synapse_row_id": "fixture.csv#3",
                "source_row_number": 3,
                "synapse_id": "edge-c",
                "pre_root_id": 202,
                "post_root_id": 101,
                "x": 0.0,
                "y": -0.2,
                "z": 0.0,
                "pre_x": 0.0,
                "pre_y": 0.0,
                "pre_z": -1.0,
                "post_x": 0.0,
                "post_y": 1.0,
                "post_z": 0.0,
                "neuropil": "LOP_R",
                "nt_type": "ACH",
                "sign": "excitatory",
                "confidence": 0.9,
                "weight": 0.25,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
            {
                "synapse_row_id": "fixture.csv#4",
                "source_row_number": 4,
                "synapse_id": "edge-d",
                "pre_root_id": 202,
                "post_root_id": 101,
                "x": 0.1,
                "y": 0.0,
                "z": 0.0,
                "pre_x": 1.0,
                "pre_y": 0.0,
                "pre_z": 0.0,
                "post_x": -1.0,
                "post_y": 0.0,
                "post_z": 0.0,
                "neuropil": "LOP_R",
                "nt_type": "GABA",
                "sign": "inhibitory",
                "confidence": 0.85,
                "weight": -0.75,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
            {
                "synapse_row_id": "fixture.csv#5",
                "source_row_number": 5,
                "synapse_id": "edge-e",
                "pre_root_id": 202,
                "post_root_id": 101,
                "x": np.nan,
                "y": np.nan,
                "z": np.nan,
                "pre_x": np.nan,
                "pre_y": np.nan,
                "pre_z": np.nan,
                "post_x": 0.0,
                "post_y": -1.0,
                "post_z": 0.0,
                "neuropil": "LOP_R",
                "nt_type": "ACH",
                "sign": "excitatory",
                "confidence": 0.7,
                "weight": 0.4,
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
