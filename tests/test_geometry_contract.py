from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.geometry_contract import (
    ASSET_STATUS_READY,
    ASSET_STATUS_SKIPPED,
    COARSE_OPERATOR_KEY,
    DESCRIPTOR_SIDECAR_KEY,
    FETCH_STATUS_CACHE_HIT,
    GEOMETRY_ASSET_CONTRACT_VERSION,
    OPERATOR_BUNDLE_CONTRACT_VERSION,
    OPERATOR_BUNDLE_DESIGN_NOTE,
    OPERATOR_METADATA_KEY,
    PATCH_GRAPH_KEY,
    QA_SIDECAR_KEY,
    TRANSFER_OPERATORS_KEY,
    RAW_MESH_KEY,
    RAW_SKELETON_KEY,
    SIMPLIFIED_MESH_KEY,
    SURFACE_GRAPH_KEY,
    FINE_OPERATOR_KEY,
    build_geometry_bundle_paths,
    build_geometry_manifest,
    build_geometry_manifest_record,
    default_asset_statuses,
    merge_geometry_manifest_record,
)


class GeometryContractTest(unittest.TestCase):
    def test_bundle_paths_are_deterministic(self) -> None:
        bundle_paths = build_geometry_bundle_paths(
            101,
            meshes_raw_dir=ROOT / "data" / "interim" / "meshes_raw",
            skeletons_raw_dir=ROOT / "data" / "interim" / "skeletons_raw",
            processed_mesh_dir=ROOT / "data" / "processed" / "meshes",
            processed_graph_dir=ROOT / "data" / "processed" / "graphs",
        )

        self.assertEqual(bundle_paths.raw_mesh_path, (ROOT / "data/interim/meshes_raw/101.ply").resolve())
        self.assertEqual(bundle_paths.raw_skeleton_path, (ROOT / "data/interim/skeletons_raw/101.swc").resolve())
        self.assertEqual(bundle_paths.simplified_mesh_path, (ROOT / "data/processed/meshes/101.ply").resolve())
        self.assertEqual(bundle_paths.surface_graph_path, (ROOT / "data/processed/graphs/101_graph.npz").resolve())
        self.assertEqual(
            bundle_paths.fine_operator_path,
            (ROOT / "data/processed/graphs/101_fine_operator.npz").resolve(),
        )
        self.assertEqual(bundle_paths.patch_graph_path, (ROOT / "data/processed/graphs/101_patch_graph.npz").resolve())
        self.assertEqual(
            bundle_paths.descriptor_sidecar_path,
            (ROOT / "data/processed/graphs/101_descriptors.json").resolve(),
        )
        self.assertEqual(bundle_paths.qa_sidecar_path, (ROOT / "data/processed/graphs/101_qa.json").resolve())
        self.assertEqual(
            bundle_paths.transfer_operator_path,
            (ROOT / "data/processed/graphs/101_transfer_operators.npz").resolve(),
        )
        self.assertEqual(
            bundle_paths.operator_metadata_path,
            (ROOT / "data/processed/graphs/101_operator_metadata.json").resolve(),
        )
        self.assertEqual(
            bundle_paths.coarse_operator_path,
            (ROOT / "data/processed/graphs/101_coarse_operator.npz").resolve(),
        )

    def test_manifest_record_captures_contract_metadata_and_asset_statuses(self) -> None:
        bundle_paths = build_geometry_bundle_paths(
            101,
            meshes_raw_dir=ROOT / "data" / "interim" / "meshes_raw",
            skeletons_raw_dir=ROOT / "data" / "interim" / "skeletons_raw",
            processed_mesh_dir=ROOT / "data" / "processed" / "meshes",
            processed_graph_dir=ROOT / "data" / "processed" / "graphs",
        )
        asset_statuses = default_asset_statuses(fetch_skeletons=False)
        asset_statuses.update(
            {
                RAW_MESH_KEY: ASSET_STATUS_READY,
                SIMPLIFIED_MESH_KEY: ASSET_STATUS_READY,
                SURFACE_GRAPH_KEY: ASSET_STATUS_READY,
                PATCH_GRAPH_KEY: ASSET_STATUS_READY,
                DESCRIPTOR_SIDECAR_KEY: ASSET_STATUS_READY,
                QA_SIDECAR_KEY: ASSET_STATUS_READY,
                TRANSFER_OPERATORS_KEY: ASSET_STATUS_READY,
                OPERATOR_METADATA_KEY: ASSET_STATUS_READY,
            }
        )

        record = build_geometry_manifest_record(
            bundle_paths=bundle_paths,
            asset_statuses=asset_statuses,
            dataset_name="public",
            materialization_version=783,
            meshing_config_snapshot={"fetch_skeletons": False, "patch_hops": 2},
            registry_metadata={"cell_type": "T5a", "project_role": "surface_simulated"},
            bundle_metadata={"n_faces": 4},
            raw_asset_provenance={
                RAW_MESH_KEY: {
                    "fetch_status": FETCH_STATUS_CACHE_HIT,
                    "asset_status": ASSET_STATUS_READY,
                }
            },
        )
        manifest = build_geometry_manifest(
            bundle_records={101: record},
            dataset_name="public",
            materialization_version=783,
            meshing_config_snapshot={"fetch_skeletons": False, "patch_hops": 2},
        )

        self.assertEqual(manifest["_asset_contract_version"], GEOMETRY_ASSET_CONTRACT_VERSION)
        self.assertEqual(manifest["_operator_contract_version"], OPERATOR_BUNDLE_CONTRACT_VERSION)
        self.assertEqual(manifest["_operator_contract"]["design_note"], OPERATOR_BUNDLE_DESIGN_NOTE)
        self.assertEqual(manifest["_dataset"]["materialization_version"], 783)
        self.assertEqual(manifest["101"]["bundle_version"], GEOMETRY_ASSET_CONTRACT_VERSION)
        self.assertEqual(manifest["101"]["build"]["meshing_config_snapshot"]["patch_hops"], 2)
        self.assertEqual(manifest["101"]["assets"][RAW_MESH_KEY]["status"], ASSET_STATUS_READY)
        self.assertEqual(manifest["101"]["assets"][RAW_SKELETON_KEY]["status"], ASSET_STATUS_SKIPPED)
        self.assertEqual(manifest["101"]["assets"][TRANSFER_OPERATORS_KEY]["status"], ASSET_STATUS_READY)
        self.assertEqual(
            manifest["101"]["artifact_sources"]["surface_graph"]["raw_mesh_path"],
            str(bundle_paths.raw_mesh_path),
        )
        self.assertEqual(
            manifest["101"]["artifact_sources"]["surface_graph"]["raw_skeleton_status"],
            ASSET_STATUS_SKIPPED,
        )
        self.assertEqual(manifest["101"]["raw_asset_provenance"][RAW_MESH_KEY]["fetch_status"], FETCH_STATUS_CACHE_HIT)
        self.assertEqual(manifest["101"]["processed_graph_path"], str(bundle_paths.surface_graph_path))
        self.assertEqual(manifest["101"]["patch_graph_path"], str(bundle_paths.patch_graph_path))
        self.assertEqual(manifest["101"]["transfer_operator_path"], str(bundle_paths.transfer_operator_path))
        self.assertEqual(manifest["101"]["operator_metadata_path"], str(bundle_paths.operator_metadata_path))
        self.assertEqual(manifest["101"]["operator_bundle"]["contract_version"], OPERATOR_BUNDLE_CONTRACT_VERSION)
        self.assertEqual(manifest["101"]["operator_bundle"]["discretization_family"], "surface_graph_uniform_laplacian")
        self.assertEqual(manifest["101"]["operator_bundle"]["mass_treatment"], "uniform_vertex_measure")
        self.assertEqual(
            manifest["101"]["operator_bundle"]["boundary_condition_mode"],
            "closed_surface_zero_flux",
        )
        self.assertEqual(
            manifest["101"]["operator_bundle"]["geodesic_neighborhood"]["patch_hops"],
            2,
        )
        self.assertTrue(
            manifest["101"]["operator_bundle"]["transfer_operators"]["fine_to_coarse_restriction"]["available"]
        )
        self.assertEqual(
            manifest["101"]["operator_bundle"]["assets"][FINE_OPERATOR_KEY]["legacy_alias"],
            SURFACE_GRAPH_KEY,
        )
        self.assertEqual(
            manifest["101"]["operator_bundle"]["assets"][COARSE_OPERATOR_KEY]["legacy_alias"],
            PATCH_GRAPH_KEY,
        )

    def test_merge_manifest_record_preserves_existing_provenance_when_build_step_updates_assets(self) -> None:
        bundle_paths = build_geometry_bundle_paths(
            101,
            meshes_raw_dir=ROOT / "data" / "interim" / "meshes_raw",
            skeletons_raw_dir=ROOT / "data" / "interim" / "skeletons_raw",
            processed_mesh_dir=ROOT / "data" / "processed" / "meshes",
            processed_graph_dir=ROOT / "data" / "processed" / "graphs",
        )
        fetch_record = build_geometry_manifest_record(
            bundle_paths=bundle_paths,
            asset_statuses=default_asset_statuses(fetch_skeletons=True) | {RAW_MESH_KEY: ASSET_STATUS_READY},
            dataset_name="public",
            materialization_version=783,
            meshing_config_snapshot={"fetch_skeletons": True},
            raw_asset_provenance={RAW_MESH_KEY: {"fetch_status": FETCH_STATUS_CACHE_HIT}},
        )
        build_asset_statuses = default_asset_statuses(fetch_skeletons=True)
        build_asset_statuses.update(
            {
                RAW_MESH_KEY: ASSET_STATUS_READY,
                RAW_SKELETON_KEY: ASSET_STATUS_SKIPPED,
                SIMPLIFIED_MESH_KEY: ASSET_STATUS_READY,
                SURFACE_GRAPH_KEY: ASSET_STATUS_READY,
                PATCH_GRAPH_KEY: ASSET_STATUS_READY,
                DESCRIPTOR_SIDECAR_KEY: ASSET_STATUS_READY,
                QA_SIDECAR_KEY: ASSET_STATUS_READY,
                TRANSFER_OPERATORS_KEY: ASSET_STATUS_READY,
                OPERATOR_METADATA_KEY: ASSET_STATUS_READY,
            }
        )
        build_record = build_geometry_manifest_record(
            bundle_paths=bundle_paths,
            asset_statuses=build_asset_statuses,
            dataset_name="public",
            materialization_version=783,
            meshing_config_snapshot={"fetch_skeletons": True},
            bundle_metadata={"n_faces": 4},
        )

        merged = merge_geometry_manifest_record(fetch_record, build_record)

        self.assertEqual(merged["bundle_status"], ASSET_STATUS_READY)
        self.assertEqual(merged["bundle_metadata"]["n_faces"], 4)
        self.assertEqual(merged["raw_asset_provenance"][RAW_MESH_KEY]["fetch_status"], FETCH_STATUS_CACHE_HIT)
        self.assertEqual(merged["operator_bundle"]["status"], ASSET_STATUS_READY)


if __name__ == "__main__":
    unittest.main()
