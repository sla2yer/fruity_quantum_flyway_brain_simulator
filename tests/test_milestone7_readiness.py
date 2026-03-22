from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.coupling_inspection import generate_coupling_inspection_report
from flywire_wave.geometry_contract import (
    build_geometry_bundle_paths,
    build_geometry_manifest_record,
    default_asset_statuses,
    write_geometry_manifest,
)
from flywire_wave.milestone7_readiness import generate_milestone7_readiness_report
from flywire_wave.mesh_pipeline import process_mesh_into_wave_assets
from flywire_wave.synapse_mapping import materialize_synapse_anchor_maps


class Milestone7ReadinessReportTest(unittest.TestCase):
    def test_generate_readiness_report_writes_deterministic_paths(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            coupling_dir = tmp_dir / "out" / "processed_coupling"
            processed_graph_dir = tmp_dir / "out" / "processed_graphs"

            root_outputs = {}
            for root_id, role in [(101, "surface_simulated"), (202, "skeleton_simulated"), (303, "point_simulated")]:
                bundle_paths = build_geometry_bundle_paths(
                    root_id,
                    meshes_raw_dir=tmp_dir / "out" / "meshes_raw",
                    skeletons_raw_dir=tmp_dir / "out" / "skeletons_raw",
                    processed_mesh_dir=tmp_dir / "out" / "processed_meshes",
                    processed_graph_dir=processed_graph_dir,
                )
                _write_octahedron_mesh(bundle_paths.raw_mesh_path)
                if root_id == 202:
                    _write_stub_swc(bundle_paths.raw_skeleton_path)
                root_outputs[root_id] = {
                    "bundle_paths": bundle_paths,
                    "outputs": process_mesh_into_wave_assets(
                        root_id=root_id,
                        bundle_paths=bundle_paths,
                        simplify_target_faces=8,
                        patch_hops=1,
                        patch_vertex_cap=2,
                        registry_metadata={"cell_type": f"fixture-{root_id}", "project_role": role},
                    ),
                }

            _write_synapse_registry(coupling_dir / "synapse_registry.csv")
            neuron_registry = pd.DataFrame(
                {
                    "root_id": [101, 202, 303],
                    "project_role": ["surface_simulated", "skeleton_simulated", "point_simulated"],
                }
            )
            mapping_summary = materialize_synapse_anchor_maps(
                root_ids=[101, 202, 303],
                processed_coupling_dir=coupling_dir,
                meshes_raw_dir=tmp_dir / "out" / "meshes_raw",
                skeletons_raw_dir=tmp_dir / "out" / "skeletons_raw",
                processed_mesh_dir=tmp_dir / "out" / "processed_meshes",
                processed_graph_dir=processed_graph_dir,
                neuron_registry=neuron_registry,
                synapse_registry_path=coupling_dir / "synapse_registry.csv",
            )
            self.assertEqual(mapping_summary["edge_count"], 3)

            manifest_path = tmp_dir / "out" / "asset_manifest.json"
            meshing_config = {
                "fetch_skeletons": True,
                "patch_hops": 1,
                "patch_vertex_cap": 2,
                "operator_assembly": {
                    "version": "operator_assembly.v1",
                    "boundary_condition": {"mode": "closed_surface_zero_flux"},
                    "anisotropy": {"model": "isotropic"},
                },
                "coupling_assembly": {
                    "version": "coupling_assembly.v1",
                    "topology_family": "distributed_patch_cloud",
                    "kernel_family": "separable_rank_one_cloud",
                },
            }
            records = {}
            for root_id in [101, 202, 303]:
                bundle_paths = root_outputs[root_id]["bundle_paths"]
                outputs = root_outputs[root_id]["outputs"]
                records[root_id] = build_geometry_manifest_record(
                    bundle_paths=bundle_paths,
                    asset_statuses={
                        **default_asset_statuses(fetch_skeletons=True),
                        **outputs["asset_statuses"],
                    },
                    dataset_name="public",
                    materialization_version=783,
                    meshing_config_snapshot=meshing_config,
                    registry_metadata={"cell_type": f"fixture-{root_id}", "project_role": neuron_registry.set_index("root_id").loc[root_id, "project_role"]},
                    bundle_metadata=outputs["bundle_metadata"],
                    operator_bundle_metadata=outputs["operator_bundle_metadata"],
                    coupling_bundle_metadata=mapping_summary["bundle_metadata_by_root"][root_id],
                    processed_coupling_dir=coupling_dir,
                )
            write_geometry_manifest(
                manifest_path=manifest_path,
                bundle_records=records,
                dataset_name="public",
                materialization_version=783,
                meshing_config_snapshot=meshing_config,
                processed_coupling_dir=coupling_dir,
            )

            inspection_summary = generate_coupling_inspection_report(
                edge_specs=[(202, 101), (101, 303), (303, 101)],
                processed_coupling_dir=coupling_dir,
                meshes_raw_dir=tmp_dir / "out" / "meshes_raw",
                skeletons_raw_dir=tmp_dir / "out" / "skeletons_raw",
                processed_mesh_dir=tmp_dir / "out" / "processed_meshes",
                processed_graph_dir=processed_graph_dir,
                coupling_inspection_dir=tmp_dir / "out" / "coupling_inspection",
            )
            self.assertEqual(inspection_summary["edge_count"], 3)

            connectivity_path = tmp_dir / "out" / "connectivity_registry.csv"
            pd.DataFrame(
                [
                    {"pre_root_id": 101, "post_root_id": 303, "neuropil": "ME_R", "syn_count": 1, "nt_type": "GABA"},
                    {"pre_root_id": 202, "post_root_id": 101, "neuropil": "LOP_R", "syn_count": 1, "nt_type": "ACH"},
                    {"pre_root_id": 303, "post_root_id": 101, "neuropil": "LOP_R", "syn_count": 1, "nt_type": "ACH"},
                ]
            ).to_csv(connectivity_path, index=False)

            synapse_provenance_path = coupling_dir / "synapse_registry_provenance.json"
            synapse_provenance_path.write_text(
                json.dumps(
                    {
                        "source": {"path": str(tmp_dir / "synapses.csv")},
                        "scope": {"mode": "root_id_subset", "root_ids": [101, 202, 303]},
                    }
                ),
                encoding="utf-8",
            )

            config_path = tmp_dir / "config.yaml"
            config_path.write_text("paths: {}\n", encoding="utf-8")

            report = generate_milestone7_readiness_report(
                config_path=config_path,
                manifest_path=manifest_path,
                connectivity_registry_path=connectivity_path,
                synapse_registry_path=coupling_dir / "synapse_registry.csv",
                synapse_registry_provenance_path=synapse_provenance_path,
                coupling_inspection_dir=tmp_dir / "out" / "coupling_inspection",
                root_ids=[101, 202, 303],
                edge_specs=[(202, 101), (101, 303), (303, 101)],
                fixture_verification={"status": "pass", "command": "python -m unittest"},
                registry_command={"status": "pass", "command": "scripts/build_registry.py --config config.yaml"},
                selection_command={"status": "pass", "command": "scripts/01_select_subset.py --config config.yaml"},
                build_command={"status": "pass", "command": "scripts/03_build_wave_assets.py --config config.yaml"},
                coupling_inspection_command={"status": "pass", "command": "scripts/08_coupling_inspection.py --config config.yaml"},
            )

            report_dir = Path(report["report_dir"])
            markdown_path = report_dir / "milestone_7_readiness.md"
            json_path = report_dir / "milestone_7_readiness.json"

            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())
            self.assertEqual(report["root_count"], 3)
            self.assertEqual(report["edge_count"], 3)
            self.assertEqual(report["coupling_contract_audit"]["synapse_registry_row_count"], 3)
            self.assertTrue(report["coupling_contract_audit"]["connectivity_registry_matches_synapse_scope"])
            self.assertTrue(report["mode_coverage"]["expected_anchor_type_coverage_ok"])
            self.assertEqual(
                report["mode_coverage"]["mapped_anchor_type_counts"],
                {
                    "point_state": 2,
                    "skeleton_node": 1,
                    "surface_patch": 3,
                },
            )
            self.assertEqual(report["follow_on_issues"], [])
            self.assertIn(report["follow_on_readiness"]["status"], {"ready", "review"})
            self.assertTrue(report["follow_on_readiness"]["ready_for_follow_on_work"])

            markdown_text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("Milestone 7 Readiness Report", markdown_text)
            self.assertIn("Local coupling gate", markdown_text)
            self.assertIn("Mode coverage", markdown_text)

            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["markdown_path"], report["markdown_path"])


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
            1 0 0
            -1 0 0
            0 1 0
            0 -1 0
            0 0 1
            0 0 -1
            3 0 2 4
            3 2 1 4
            3 1 3 4
            3 3 0 4
            3 2 0 5
            3 1 2 5
            3 3 1 5
            3 0 3 5
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_stub_swc(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """
            1 1 0.0 0.0 0.0 1.0 -1
            2 3 1.0 0.0 0.0 0.5 1
            3 3 0.0 1.0 0.0 0.5 1
            4 3 0.0 0.0 1.0 0.5 1
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


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
                "pre_root_id": 101,
                "post_root_id": 303,
                "x": 5.0,
                "y": 5.0,
                "z": 5.0,
                "pre_x": 1.0,
                "pre_y": 0.0,
                "pre_z": 0.0,
                "post_x": 5.0,
                "post_y": 5.0,
                "post_z": 5.0,
                "neuropil": "ME_R",
                "nt_type": "GABA",
                "sign": "inhibitory",
                "confidence": 0.88,
                "weight": -1.0,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
            {
                "synapse_row_id": "fixture.csv#3",
                "source_row_number": 3,
                "synapse_id": "edge-c",
                "pre_root_id": 303,
                "post_root_id": 101,
                "x": 4.0,
                "y": 4.0,
                "z": 4.0,
                "pre_x": 4.0,
                "pre_y": 4.0,
                "pre_z": 4.0,
                "post_x": 0.0,
                "post_y": 1.0,
                "post_z": 0.0,
                "neuropil": "LOP_R",
                "nt_type": "ACH",
                "sign": "excitatory",
                "confidence": 0.92,
                "weight": 0.5,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
        ]
    ).to_csv(path, index=False)


if __name__ == "__main__":
    unittest.main()
