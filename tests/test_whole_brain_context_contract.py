from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.whole_brain_context_contract import (
    ACTIVE_BOUNDARY_OVERLAY_ID,
    ACTIVE_SELECTED_NODE_ROLE_ID,
    BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
    CONTEXT_ONLY_NODE_ROLE_ID,
    CONTEXT_QUERY_CATALOG_ROLE_ID,
    CONTEXT_VIEW_PAYLOAD_ROLE_ID,
    CONTEXT_VIEW_STATE_ROLE_ID,
    METADATA_JSON_KEY,
    WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
    WHOLE_BRAIN_CONTEXT_SESSION_DESIGN_NOTE,
    WHOLE_BRAIN_CONTEXT_SESSION_METADATA_ROLE_ID,
    build_whole_brain_context_artifact_reference,
    build_whole_brain_context_contract_metadata,
    build_whole_brain_context_downstream_module_record,
    build_whole_brain_context_edge_record,
    build_whole_brain_context_node_record,
    build_whole_brain_context_query_state,
    build_whole_brain_context_session_metadata,
    discover_whole_brain_context_node_roles,
    discover_whole_brain_context_overlays,
    discover_whole_brain_context_query_profiles,
    discover_whole_brain_context_session_artifact_references,
    discover_whole_brain_context_session_bundle_paths,
    get_whole_brain_context_query_profile_definition,
    load_whole_brain_context_contract_metadata,
    load_whole_brain_context_session_metadata,
    write_whole_brain_context_contract_metadata,
    write_whole_brain_context_session_metadata,
)


def _humanize_identifier(identifier: str) -> str:
    return identifier.replace("_", " ").title()


def _mutate_contract_fixture(metadata: dict[str, object], *, reverse: bool) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    for field_name, id_key in (
        ("query_profile_catalog", "query_profile_id"),
        ("node_role_catalog", "node_role_id"),
        ("edge_role_catalog", "edge_role_id"),
        ("context_layer_catalog", "context_layer_id"),
        ("overlay_catalog", "overlay_id"),
        ("reduction_profile_catalog", "reduction_profile_id"),
        ("metadata_facet_catalog", "metadata_facet_id"),
        ("downstream_module_role_catalog", "downstream_module_role_id"),
        ("artifact_hook_catalog", "artifact_role_id"),
        ("discovery_hook_catalog", "hook_id"),
    ):
        entries: list[dict[str, object]] = []
        for item in metadata[field_name]:
            mutated = copy.deepcopy(item)
            mutated[id_key] = _humanize_identifier(str(mutated[id_key]))
            for key in (
                "query_family",
                "selection_boundary_status",
                "direction_family",
                "layer_kind",
                "overlay_category",
                "facet_scope",
                "source_kind",
                "artifact_scope",
            ):
                if key in mutated:
                    mutated[key] = _humanize_identifier(str(mutated[key]))
            for key in (
                "default_context_layer_ids",
                "supported_overlay_ids",
                "required_artifact_role_ids",
                "supported_context_layer_ids",
                "allowed_source_node_role_ids",
                "allowed_target_node_role_ids",
                "supported_node_role_ids",
                "supported_query_profile_ids",
                "required_node_role_ids",
                "required_edge_role_ids",
                "artifact_role_ids",
            ):
                if key in mutated:
                    mutated[key] = [_humanize_identifier(str(value)) for value in mutated[key]]
            for key in (
                "default_overlay_id",
                "default_reduction_profile_id",
                "default_context_layer_id",
                "canonical_anchor_artifact_role_id",
            ):
                if key in mutated and mutated[key] is not None:
                    mutated[key] = _humanize_identifier(str(mutated[key]))
            entries.append(mutated)
        if reverse:
            entries.reverse()
        result[field_name] = entries
    return {
        "query_profile_definitions": result["query_profile_catalog"],
        "node_role_definitions": result["node_role_catalog"],
        "edge_role_definitions": result["edge_role_catalog"],
        "context_layer_definitions": result["context_layer_catalog"],
        "overlay_definitions": result["overlay_catalog"],
        "reduction_profile_definitions": result["reduction_profile_catalog"],
        "metadata_facet_definitions": result["metadata_facet_catalog"],
        "downstream_module_role_definitions": result["downstream_module_role_catalog"],
        "artifact_hook_definitions": result["artifact_hook_catalog"],
        "discovery_hook_definitions": result["discovery_hook_catalog"],
    }


class WholeBrainContextContractTest(unittest.TestCase):
    def test_default_contract_serializes_deterministically_and_exposes_taxonomy(self) -> None:
        default_metadata = build_whole_brain_context_contract_metadata()
        mutated_metadata = build_whole_brain_context_contract_metadata(
            **_mutate_contract_fixture(default_metadata, reverse=True)
        )

        self.assertEqual(default_metadata, mutated_metadata)
        self.assertEqual(
            default_metadata["contract_version"],
            WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
        )
        self.assertEqual(
            default_metadata["design_note"],
            WHOLE_BRAIN_CONTEXT_SESSION_DESIGN_NOTE,
        )
        self.assertEqual(
            [item["query_profile_id"] for item in discover_whole_brain_context_query_profiles(default_metadata)],
            [
                "active_subset_shell",
                "upstream_connectivity_context",
                "downstream_connectivity_context",
                "bidirectional_connectivity_context",
                "pathway_highlight_review",
                "downstream_module_review",
            ],
        )
        self.assertEqual(
            [item["node_role_id"] for item in discover_whole_brain_context_node_roles(default_metadata, selection_boundary_status="Context")],
            [CONTEXT_ONLY_NODE_ROLE_ID, "context_pathway_highlight"],
        )
        self.assertEqual(
            [item["overlay_id"] for item in discover_whole_brain_context_overlays(default_metadata, overlay_category="Directional Context")],
            ["upstream_graph", "downstream_graph"],
        )
        self.assertEqual(
            get_whole_brain_context_query_profile_definition(
                "Bidirectional Connectivity Context",
                record=default_metadata,
            )["query_profile_id"],
            BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
        )

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            metadata_path = Path(tmp_dir_str) / "whole_brain_context_contract.json"
            written_path = write_whole_brain_context_contract_metadata(
                default_metadata,
                metadata_path,
            )
            self.assertEqual(
                load_whole_brain_context_contract_metadata(written_path),
                default_metadata,
            )

    def test_fixture_session_metadata_serializes_deterministically_and_discovers_artifacts(self) -> None:
        contract = build_whole_brain_context_contract_metadata()
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            temp_root = Path(tmp_dir_str)

            external_refs = [
                build_whole_brain_context_artifact_reference(
                    artifact_role_id="Selected Root Ids",
                    source_kind="Subset Selection Bundle",
                    path=temp_root / "subset/root_ids.txt",
                    contract_version=None,
                    bundle_id="subset:demo",
                    artifact_id="root_ids",
                    artifact_scope="Subset Selection",
                ),
                build_whole_brain_context_artifact_reference(
                    artifact_role_id="Subset Manifest",
                    source_kind="Subset Selection Bundle",
                    path=temp_root / "subset/subset_manifest.json",
                    contract_version=None,
                    bundle_id="subset:demo",
                    artifact_id="subset_manifest",
                    artifact_scope="Subset Selection",
                ),
                build_whole_brain_context_artifact_reference(
                    artifact_role_id="Subset Stats",
                    source_kind="Subset Selection Bundle",
                    path=temp_root / "subset/subset_stats.json",
                    contract_version=None,
                    bundle_id="subset:demo",
                    artifact_id="subset_stats",
                    artifact_scope="Subset Selection",
                ),
                build_whole_brain_context_artifact_reference(
                    artifact_role_id="Synapse Registry",
                    source_kind="Local Connectivity Registry",
                    path=temp_root / "coupling/synapse_registry.csv",
                    contract_version="coupling_bundle.v1",
                    bundle_id="coupling:demo",
                    artifact_id="local_synapse_registry",
                    artifact_scope="Local Connectivity",
                ),
                build_whole_brain_context_artifact_reference(
                    artifact_role_id="Dashboard Session Metadata",
                    source_kind="Dashboard Session Package",
                    path=temp_root / "dashboard/dashboard_session.json",
                    contract_version="dashboard_session.v1",
                    bundle_id="dashboard:demo",
                    artifact_id="metadata_json",
                    artifact_scope="Dashboard Context",
                ),
                build_whole_brain_context_artifact_reference(
                    artifact_role_id="Showcase Session Metadata",
                    source_kind="Showcase Session Package",
                    path=temp_root / "showcase/showcase_session.json",
                    contract_version="showcase_session.v1",
                    bundle_id="showcase:demo",
                    artifact_id="metadata_json",
                    artifact_scope="Showcase Context",
                ),
            ]

            representative_context_a = {
                "node_records": [
                    build_whole_brain_context_node_record(
                        root_id=101,
                        node_role_id="Active Selected",
                        context_layer_id="Active Subset",
                        overlay_ids=["Active Boundary", "Metadata Facet Badges"],
                        metadata_facet_values={
                            "Cell Class": "VPN",
                            "Selection Boundary Status": "active_selected",
                        },
                    ),
                    build_whole_brain_context_node_record(
                        root_id=202,
                        node_role_id="Context Only",
                        context_layer_id="Upstream Context",
                        overlay_ids=["Upstream Graph", "Metadata Facet Badges"],
                        metadata_facet_values={
                            "Neuropil": "AME",
                            "Pathway Relevance Status": "context_only",
                        },
                    ),
                    build_whole_brain_context_node_record(
                        root_id=303,
                        node_role_id="Context Pathway Highlight",
                        context_layer_id="Pathway Highlight",
                        overlay_ids=["Pathway Highlight", "Metadata Facet Badges"],
                        metadata_facet_values={
                            "Neuropil": "LO",
                            "Pathway Relevance Status": "highlighted",
                        },
                    ),
                ],
                "edge_records": [
                    build_whole_brain_context_edge_record(
                        source_root_id=202,
                        target_root_id=101,
                        edge_role_id="Context To Active",
                        overlay_ids=["Upstream Graph"],
                        weight=4,
                    ),
                    build_whole_brain_context_edge_record(
                        source_root_id=303,
                        target_root_id=101,
                        edge_role_id="Pathway Highlight",
                        overlay_ids=["Pathway Highlight"],
                        weight=2,
                    ),
                ],
                "downstream_module_records": [
                    build_whole_brain_context_downstream_module_record(
                        module_id="Readout Module A",
                        downstream_module_role_id="Simplified Readout Module",
                        display_name="Readout Module A",
                        description="Compact downstream readout summary.",
                        represented_root_ids=[101, 303],
                        overlay_ids=["Downstream Module", "Metadata Facet Badges"],
                        metadata_facet_values={
                            "Cell Class": "readout_proxy",
                            "Pathway Relevance Status": "summary",
                        },
                    )
                ],
            }
            representative_context_b = {
                "node_records": list(reversed(representative_context_a["node_records"])),
                "edge_records": list(reversed(representative_context_a["edge_records"])),
                "downstream_module_records": list(
                    reversed(representative_context_a["downstream_module_records"])
                ),
            }

            query_state_a = build_whole_brain_context_query_state(
                query_profile_id="Bidirectional Connectivity Context",
                enabled_overlay_ids=[
                    "Metadata Facet Badges",
                    "Downstream Module",
                    "Pathway Highlight",
                    "Downstream Graph",
                    "Upstream Graph",
                    "Active Boundary",
                ],
                enabled_metadata_facet_ids=[
                    "Pathway Relevance Status",
                    "Selection Boundary Status",
                    "Neuropil",
                    "Cell Class",
                    "Cell Type",
                ],
                contract_metadata=contract,
            )
            query_state_b = {
                "query_profile_id": "Bidirectional Connectivity Context",
                "default_overlay_id": "Active Boundary",
                "default_reduction_profile_id": "Balanced Neighborhood",
                "enabled_overlay_ids": list(reversed(query_state_a["enabled_overlay_ids"])),
                "enabled_metadata_facet_ids": list(
                    reversed(query_state_a["enabled_metadata_facet_ids"])
                ),
            }

            metadata_a = build_whole_brain_context_session_metadata(
                experiment_id="Demo Whole Brain Context",
                artifact_references=external_refs,
                representative_context=representative_context_a,
                query_state=query_state_a,
                contract_metadata=contract,
            )
            metadata_b = build_whole_brain_context_session_metadata(
                experiment_id="demo_whole_brain_context",
                artifact_references=list(reversed(external_refs)),
                representative_context=representative_context_b,
                query_state=query_state_b,
                contract_metadata=contract,
            )

            self.assertEqual(metadata_a, metadata_b)
            self.assertEqual(
                metadata_a["query_state"]["query_profile_id"],
                BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
            )
            self.assertEqual(
                metadata_a["query_state"]["default_overlay_id"],
                ACTIVE_BOUNDARY_OVERLAY_ID,
            )
            self.assertEqual(
                [item["artifact_role_id"] for item in discover_whole_brain_context_session_artifact_references(metadata_a, source_kind="Whole Brain Context Session Package")],
                [
                    WHOLE_BRAIN_CONTEXT_SESSION_METADATA_ROLE_ID,
                    CONTEXT_VIEW_PAYLOAD_ROLE_ID,
                    CONTEXT_QUERY_CATALOG_ROLE_ID,
                    CONTEXT_VIEW_STATE_ROLE_ID,
                ],
            )
            self.assertEqual(
                discover_whole_brain_context_session_bundle_paths(metadata_a)[METADATA_JSON_KEY].name,
                "whole_brain_context_session.json",
            )
            self.assertEqual(
                metadata_a["representative_context"]["node_records"][0]["node_role_id"],
                ACTIVE_SELECTED_NODE_ROLE_ID,
            )

            with tempfile.TemporaryDirectory(dir=ROOT) as output_dir_str:
                metadata_path = Path(output_dir_str) / "whole_brain_context_session.json"
                written_path = write_whole_brain_context_session_metadata(
                    metadata_a,
                    metadata_path,
                )
                self.assertEqual(
                    load_whole_brain_context_session_metadata(written_path),
                    metadata_a,
                )
