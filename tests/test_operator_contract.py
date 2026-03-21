from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.geometry_contract import (
    ASSET_STATUS_READY,
    DESCRIPTOR_SIDECAR_KEY,
    FINE_OPERATOR_KEY,
    OPERATOR_METADATA_KEY,
    PATCH_GRAPH_KEY,
    QA_SIDECAR_KEY,
    RAW_MESH_KEY,
    SIMPLIFIED_MESH_KEY,
    SURFACE_GRAPH_KEY,
    TRANSFER_OPERATORS_KEY,
    build_geometry_bundle_paths,
    build_geometry_manifest,
    build_geometry_manifest_record,
    default_asset_statuses,
    discover_operator_bundle_paths,
    load_operator_bundle_metadata,
)
from flywire_wave.io_utils import write_json


class OperatorContractFixtureTest(unittest.TestCase):
    def test_fixture_operator_metadata_serializes_manifest_deterministically(self) -> None:
        operator_metadata = load_operator_bundle_metadata(ROOT / "tests/fixtures/operator_metadata_fixture.json")
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
            meshing_config_snapshot={"fetch_skeletons": False, "patch_hops": 2, "patch_vertex_cap": 32},
            registry_metadata={"cell_type": "T5a"},
            bundle_metadata={"patch_generation_method": "deterministic_bfs_partition"},
            operator_bundle_metadata=operator_metadata,
        )
        manifest = build_geometry_manifest(
            bundle_records={101: record},
            dataset_name="public",
            materialization_version=783,
            meshing_config_snapshot={"fetch_skeletons": False, "patch_hops": 2, "patch_vertex_cap": 32},
        )

        discovered_paths = discover_operator_bundle_paths(manifest["101"])
        self.assertEqual(discovered_paths[FINE_OPERATOR_KEY], Path("/tmp/flywire_wave_fixture/101_graph.npz"))
        self.assertEqual(
            discovered_paths[TRANSFER_OPERATORS_KEY],
            Path("/tmp/flywire_wave_fixture/101_transfer_operators.npz"),
        )

        serialized = json.dumps(manifest, indent=2, sort_keys=True)
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            first_path = tmp_dir / "manifest_a.json"
            second_path = tmp_dir / "manifest_b.json"
            write_json(manifest, first_path)
            write_json(manifest, second_path)
            self.assertEqual(first_path.read_text(encoding="utf-8"), second_path.read_text(encoding="utf-8"))
            self.assertEqual(first_path.read_text(encoding="utf-8"), serialized)


if __name__ == "__main__":
    unittest.main()
