from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.coupling_contract import (
    ASSET_STATUS_MISSING,
    ASSET_STATUS_READY,
    COUPLING_BUNDLE_CONTRACT_VERSION,
    COUPLING_BUNDLE_DESIGN_NOTE,
    COUPLING_INDEX_KEY,
    DEFAULT_COUPLING_KERNEL_FAMILY,
    DEFAULT_DELAY_MODEL,
    DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
    INCOMING_ANCHOR_MAP_KEY,
    LOCAL_SYNAPSE_REGISTRY_KEY,
    OUTGOING_ANCHOR_MAP_KEY,
    build_coupling_bundle_metadata,
    build_edge_coupling_bundle_reference,
    build_root_coupling_bundle_paths,
    default_coupling_assembly_config,
    discover_coupling_bundle_paths,
    discover_edge_coupling_bundle_paths,
)
from flywire_wave.geometry_contract import (
    DESCRIPTOR_SIDECAR_KEY,
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
)
from flywire_wave.io_utils import write_json


class CouplingContractFixtureTest(unittest.TestCase):
    def test_root_coupling_paths_are_deterministic(self) -> None:
        processed_coupling_dir = ROOT / "data" / "processed" / "coupling"
        bundle_paths = build_root_coupling_bundle_paths(101, processed_coupling_dir=processed_coupling_dir)

        self.assertEqual(
            bundle_paths.local_synapse_registry_path,
            (ROOT / "data/processed/coupling/synapse_registry.csv").resolve(),
        )
        self.assertEqual(
            bundle_paths.incoming_anchor_map_path,
            (ROOT / "data/processed/coupling/roots/101_incoming_anchor_map.npz").resolve(),
        )
        self.assertEqual(
            bundle_paths.outgoing_anchor_map_path,
            (ROOT / "data/processed/coupling/roots/101_outgoing_anchor_map.npz").resolve(),
        )
        self.assertEqual(
            bundle_paths.coupling_index_path,
            (ROOT / "data/processed/coupling/roots/101_coupling_index.json").resolve(),
        )

    def test_fixture_coupling_metadata_serializes_manifest_deterministically(self) -> None:
        processed_coupling_dir = Path("/tmp/flywire_wave_fixture/coupling")
        coupling_metadata = build_coupling_bundle_metadata(
            root_id=101,
            processed_coupling_dir=processed_coupling_dir,
            local_synapse_registry_status=ASSET_STATUS_READY,
            incoming_anchor_map_status=ASSET_STATUS_READY,
            outgoing_anchor_map_status=ASSET_STATUS_READY,
            coupling_index_status=ASSET_STATUS_READY,
            edge_bundles=[
                build_edge_coupling_bundle_reference(
                    root_id=101,
                    pre_root_id=202,
                    post_root_id=101,
                    processed_coupling_dir=processed_coupling_dir,
                    status=ASSET_STATUS_READY,
                ),
                build_edge_coupling_bundle_reference(
                    root_id=101,
                    pre_root_id=101,
                    post_root_id=303,
                    processed_coupling_dir=processed_coupling_dir,
                    status=ASSET_STATUS_READY,
                ),
            ],
            topology_family=DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
        )
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
            registry_metadata={"cell_type": "T5a"},
            coupling_bundle_metadata=coupling_metadata,
            processed_coupling_dir=processed_coupling_dir,
        )
        manifest = build_geometry_manifest(
            bundle_records={101: record},
            dataset_name="public",
            materialization_version=783,
            meshing_config_snapshot={"fetch_skeletons": False, "patch_hops": 2},
            processed_coupling_dir=processed_coupling_dir,
        )

        self.assertEqual(manifest["_coupling_contract_version"], COUPLING_BUNDLE_CONTRACT_VERSION)
        self.assertEqual(manifest["_coupling_contract"]["design_note"], COUPLING_BUNDLE_DESIGN_NOTE)
        self.assertEqual(
            manifest["_coupling_contract"]["local_synapse_registry"]["path"],
            str((processed_coupling_dir / "synapse_registry.csv").resolve()),
        )
        self.assertEqual(
            manifest["_coupling_contract"]["preferred_coupling_assembly"],
            default_coupling_assembly_config(),
        )
        self.assertEqual(manifest["101"]["coupling_bundle"]["status"], ASSET_STATUS_READY)
        self.assertEqual(
            manifest["101"]["coupling_bundle"]["topology_family"],
            DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
        )
        self.assertEqual(
            manifest["101"]["coupling_bundle"]["kernel_family"],
            DEFAULT_COUPLING_KERNEL_FAMILY,
        )
        self.assertEqual(
            manifest["101"]["coupling_bundle"]["delay_model"],
            DEFAULT_DELAY_MODEL,
        )

        discovered_paths = discover_coupling_bundle_paths(manifest["101"])
        self.assertEqual(
            discovered_paths[LOCAL_SYNAPSE_REGISTRY_KEY],
            (processed_coupling_dir / "synapse_registry.csv").resolve(),
        )
        self.assertEqual(
            discovered_paths[INCOMING_ANCHOR_MAP_KEY],
            (processed_coupling_dir / "roots/101_incoming_anchor_map.npz").resolve(),
        )
        self.assertEqual(
            discovered_paths[OUTGOING_ANCHOR_MAP_KEY],
            (processed_coupling_dir / "roots/101_outgoing_anchor_map.npz").resolve(),
        )
        self.assertEqual(
            discovered_paths[COUPLING_INDEX_KEY],
            (processed_coupling_dir / "roots/101_coupling_index.json").resolve(),
        )

        discovered_edge_bundles = discover_edge_coupling_bundle_paths(manifest["101"])
        self.assertEqual(
            [
                (item["pre_root_id"], item["post_root_id"], item["relation_to_root"], item["path"])
                for item in discovered_edge_bundles
            ],
            [
                (
                    101,
                    303,
                    "outgoing",
                    (processed_coupling_dir / "edges/101__to__303_coupling.npz").resolve(),
                ),
                (
                    202,
                    101,
                    "incoming",
                    (processed_coupling_dir / "edges/202__to__101_coupling.npz").resolve(),
                ),
            ],
        )

        operator_paths = discover_operator_bundle_paths(manifest["101"])
        self.assertEqual(
            operator_paths[TRANSFER_OPERATORS_KEY],
            bundle_paths.transfer_operator_path,
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

    def test_manifest_header_uses_explicit_processed_coupling_dir_and_rejects_stale_lower_root_bundle(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            explicit_coupling_dir = tmp_dir / "expected_coupling"
            stale_coupling_dir = tmp_dir / "stale_coupling"

            manifest = build_geometry_manifest(
                bundle_records={
                    202: _build_fixture_geometry_record(
                        root_id=202,
                        processed_coupling_dir=explicit_coupling_dir,
                        local_synapse_registry_status=ASSET_STATUS_READY,
                    )
                },
                dataset_name="public",
                materialization_version=783,
                meshing_config_snapshot={"fetch_skeletons": False, "patch_hops": 2},
                processed_coupling_dir=explicit_coupling_dir,
            )

            self.assertEqual(
                manifest["_coupling_contract"]["local_synapse_registry"]["path"],
                str((explicit_coupling_dir / "synapse_registry.csv").resolve()),
            )
            self.assertEqual(
                manifest["_coupling_contract"]["local_synapse_registry"]["status"],
                ASSET_STATUS_READY,
            )

            with self.assertRaisesRegex(
                ValueError,
                r"root 101 has coupling_bundle\.assets\.local_synapse_registry\.path",
            ):
                build_geometry_manifest(
                    bundle_records={
                        202: _build_fixture_geometry_record(
                            root_id=202,
                            processed_coupling_dir=explicit_coupling_dir,
                            local_synapse_registry_status=ASSET_STATUS_READY,
                        ),
                        101: _build_fixture_geometry_record(
                            root_id=101,
                            processed_coupling_dir=stale_coupling_dir,
                            local_synapse_registry_status=ASSET_STATUS_READY,
                        ),
                    },
                    dataset_name="public",
                    materialization_version=783,
                    meshing_config_snapshot={"fetch_skeletons": False, "patch_hops": 2},
                    processed_coupling_dir=explicit_coupling_dir,
                )

    def test_manifest_build_fails_for_conflicting_per_root_local_synapse_registry_status(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            coupling_dir = tmp_dir / "processed_coupling"

            with self.assertRaisesRegex(
                ValueError,
                r"local_synapse_registry status conflicts across roots",
            ):
                build_geometry_manifest(
                    bundle_records={
                        101: _build_fixture_geometry_record(
                            root_id=101,
                            processed_coupling_dir=coupling_dir,
                            local_synapse_registry_status=ASSET_STATUS_READY,
                        ),
                        202: _build_fixture_geometry_record(
                            root_id=202,
                            processed_coupling_dir=coupling_dir,
                            local_synapse_registry_status=ASSET_STATUS_MISSING,
                        ),
                    },
                    dataset_name="public",
                    materialization_version=783,
                    meshing_config_snapshot={"fetch_skeletons": False, "patch_hops": 2},
                    processed_coupling_dir=coupling_dir,
                )


def _build_fixture_geometry_record(
    *,
    root_id: int,
    processed_coupling_dir: Path,
    local_synapse_registry_status: str,
) -> dict[str, object]:
    bundle_paths = build_geometry_bundle_paths(
        root_id,
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
    coupling_metadata = build_coupling_bundle_metadata(
        root_id=root_id,
        processed_coupling_dir=processed_coupling_dir,
        local_synapse_registry_status=local_synapse_registry_status,
        incoming_anchor_map_status=ASSET_STATUS_READY,
        outgoing_anchor_map_status=ASSET_STATUS_READY,
        coupling_index_status=ASSET_STATUS_READY,
        edge_bundles=[],
    )
    return build_geometry_manifest_record(
        bundle_paths=bundle_paths,
        asset_statuses=asset_statuses,
        dataset_name="public",
        materialization_version=783,
        meshing_config_snapshot={"fetch_skeletons": False, "patch_hops": 2},
        coupling_bundle_metadata=coupling_metadata,
        processed_coupling_dir=processed_coupling_dir,
    )


if __name__ == "__main__":
    unittest.main()
