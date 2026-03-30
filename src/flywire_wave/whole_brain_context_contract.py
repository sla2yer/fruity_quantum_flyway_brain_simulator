from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .coupling_contract import COUPLING_BUNDLE_CONTRACT_VERSION, LOCAL_SYNAPSE_REGISTRY_KEY
from .dashboard_session_contract import DASHBOARD_SESSION_CONTRACT_VERSION
from .io_utils import write_json
from .showcase_session_contract import SHOWCASE_SESSION_CONTRACT_VERSION
from .simulator_result_contract import DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR
from .stimulus_contract import (
    ASSET_STATUS_MISSING,
    ASSET_STATUS_READY,
    DEFAULT_HASH_ALGORITHM,
    _normalize_asset_status,
    _normalize_float,
    _normalize_identifier,
    _normalize_json_mapping,
    _normalize_nonempty_string,
)


WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION = "whole_brain_context_session.v1"
WHOLE_BRAIN_CONTEXT_SESSION_DESIGN_NOTE = "docs/whole_brain_context_design.md"
WHOLE_BRAIN_CONTEXT_SESSION_DESIGN_NOTE_VERSION = (
    "whole_brain_context_design_note.v1"
)

DEFAULT_WHOLE_BRAIN_CONTEXT_SESSION_DIRECTORY_NAME = "whole_brain_context_sessions"

PACKAGED_LOCAL_CONTEXT_BUNDLE_DELIVERY_MODEL = "packaged_local_context_bundle"
SUPPORTED_DELIVERY_MODELS = (PACKAGED_LOCAL_CONTEXT_BUNDLE_DELIVERY_MODEL,)
DEFAULT_DELIVERY_MODEL = PACKAGED_LOCAL_CONTEXT_BUNDLE_DELIVERY_MODEL

METADATA_JSON_KEY = "metadata_json"
CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID = "context_view_payload"
CONTEXT_QUERY_CATALOG_ARTIFACT_ID = "context_query_catalog"
CONTEXT_VIEW_STATE_ARTIFACT_ID = "context_view_state"

CONTRACT_METADATA_SCOPE = "contract_metadata"
SUBSET_SELECTION_SCOPE = "subset_selection"
LOCAL_CONNECTIVITY_SCOPE = "local_connectivity"
DASHBOARD_CONTEXT_SCOPE = "dashboard_context"
SHOWCASE_CONTEXT_SCOPE = "showcase_context"
CONTEXT_QUERY_SCOPE = "context_query"
CONTEXT_VIEW_SCOPE = "context_view"
CONTEXT_STATE_SCOPE = "context_state"

SUPPORTED_ARTIFACT_SCOPES = (
    CONTRACT_METADATA_SCOPE,
    SUBSET_SELECTION_SCOPE,
    LOCAL_CONNECTIVITY_SCOPE,
    DASHBOARD_CONTEXT_SCOPE,
    SHOWCASE_CONTEXT_SCOPE,
    CONTEXT_QUERY_SCOPE,
    CONTEXT_VIEW_SCOPE,
    CONTEXT_STATE_SCOPE,
)

SUBSET_SELECTION_SOURCE_KIND = "subset_selection_bundle"
LOCAL_CONNECTIVITY_SOURCE_KIND = "local_connectivity_registry"
DASHBOARD_SESSION_SOURCE_KIND = "dashboard_session_package"
SHOWCASE_SESSION_SOURCE_KIND = "showcase_session_package"
WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND = "whole_brain_context_session_package"

SUPPORTED_ARTIFACT_SOURCE_KINDS = (
    SUBSET_SELECTION_SOURCE_KIND,
    LOCAL_CONNECTIVITY_SOURCE_KIND,
    DASHBOARD_SESSION_SOURCE_KIND,
    SHOWCASE_SESSION_SOURCE_KIND,
    WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND,
)

LOCAL_SHELL_QUERY_FAMILY = "local_shell"
UPSTREAM_CONTEXT_QUERY_FAMILY = "upstream_context"
DOWNSTREAM_CONTEXT_QUERY_FAMILY = "downstream_context"
BIDIRECTIONAL_CONTEXT_QUERY_FAMILY = "bidirectional_context"
PATHWAY_REVIEW_QUERY_FAMILY = "pathway_review"
DOWNSTREAM_MODULE_REVIEW_QUERY_FAMILY = "downstream_module_review"

SUPPORTED_QUERY_FAMILIES = (
    LOCAL_SHELL_QUERY_FAMILY,
    UPSTREAM_CONTEXT_QUERY_FAMILY,
    DOWNSTREAM_CONTEXT_QUERY_FAMILY,
    BIDIRECTIONAL_CONTEXT_QUERY_FAMILY,
    PATHWAY_REVIEW_QUERY_FAMILY,
    DOWNSTREAM_MODULE_REVIEW_QUERY_FAMILY,
)

ACTIVE_SUBSET_SHELL_QUERY_PROFILE_ID = "active_subset_shell"
UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID = "upstream_connectivity_context"
DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID = "downstream_connectivity_context"
BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID = (
    "bidirectional_connectivity_context"
)
PATHWAY_HIGHLIGHT_REVIEW_QUERY_PROFILE_ID = "pathway_highlight_review"
DOWNSTREAM_MODULE_REVIEW_QUERY_PROFILE_ID = "downstream_module_review"

SUPPORTED_QUERY_PROFILE_IDS = (
    ACTIVE_SUBSET_SHELL_QUERY_PROFILE_ID,
    UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
    DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
    BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
    PATHWAY_HIGHLIGHT_REVIEW_QUERY_PROFILE_ID,
    DOWNSTREAM_MODULE_REVIEW_QUERY_PROFILE_ID,
)
DEFAULT_QUERY_PROFILE_ID = BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID

ACTIVE_BOUNDARY_STATUS = "active"
CONTEXT_BOUNDARY_STATUS = "context"
SUPPORTED_NODE_BOUNDARY_STATUSES = (
    ACTIVE_BOUNDARY_STATUS,
    CONTEXT_BOUNDARY_STATUS,
)

ACTIVE_SELECTED_NODE_ROLE_ID = "active_selected"
CONTEXT_ONLY_NODE_ROLE_ID = "context_only"
ACTIVE_PATHWAY_HIGHLIGHT_NODE_ROLE_ID = "active_pathway_highlight"
CONTEXT_PATHWAY_HIGHLIGHT_NODE_ROLE_ID = "context_pathway_highlight"

SUPPORTED_NODE_ROLE_IDS = (
    ACTIVE_SELECTED_NODE_ROLE_ID,
    CONTEXT_ONLY_NODE_ROLE_ID,
    ACTIVE_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
    CONTEXT_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
)

INTERNAL_EDGE_DIRECTION_FAMILY = "internal"
UPSTREAM_EDGE_DIRECTION_FAMILY = "upstream"
DOWNSTREAM_EDGE_DIRECTION_FAMILY = "downstream"
SUMMARY_EDGE_DIRECTION_FAMILY = "summary"

SUPPORTED_EDGE_DIRECTION_FAMILIES = (
    INTERNAL_EDGE_DIRECTION_FAMILY,
    UPSTREAM_EDGE_DIRECTION_FAMILY,
    DOWNSTREAM_EDGE_DIRECTION_FAMILY,
    SUMMARY_EDGE_DIRECTION_FAMILY,
)

ACTIVE_INTERNAL_EDGE_ROLE_ID = "active_internal"
ACTIVE_TO_CONTEXT_EDGE_ROLE_ID = "active_to_context"
CONTEXT_TO_ACTIVE_EDGE_ROLE_ID = "context_to_active"
CONTEXT_INTERNAL_EDGE_ROLE_ID = "context_internal"
PATHWAY_HIGHLIGHT_EDGE_ROLE_ID = "pathway_highlight"
DOWNSTREAM_MODULE_SUMMARY_EDGE_ROLE_ID = "downstream_module_summary"

SUPPORTED_EDGE_ROLE_IDS = (
    ACTIVE_INTERNAL_EDGE_ROLE_ID,
    ACTIVE_TO_CONTEXT_EDGE_ROLE_ID,
    CONTEXT_TO_ACTIVE_EDGE_ROLE_ID,
    CONTEXT_INTERNAL_EDGE_ROLE_ID,
    PATHWAY_HIGHLIGHT_EDGE_ROLE_ID,
    DOWNSTREAM_MODULE_SUMMARY_EDGE_ROLE_ID,
)

ACTIVE_LAYER_KIND = "active"
CONTEXT_LAYER_KIND = "context"
HIGHLIGHT_LAYER_KIND = "highlight"
MODULE_LAYER_KIND = "module"
SUPPORTED_LAYER_KINDS = (
    ACTIVE_LAYER_KIND,
    CONTEXT_LAYER_KIND,
    HIGHLIGHT_LAYER_KIND,
    MODULE_LAYER_KIND,
)

ACTIVE_SUBSET_CONTEXT_LAYER_ID = "active_subset"
UPSTREAM_CONTEXT_LAYER_ID = "upstream_context"
DOWNSTREAM_CONTEXT_LAYER_ID = "downstream_context"
PATHWAY_HIGHLIGHT_CONTEXT_LAYER_ID = "pathway_highlight"
DOWNSTREAM_MODULE_CONTEXT_LAYER_ID = "downstream_module"

SUPPORTED_CONTEXT_LAYER_IDS = (
    ACTIVE_SUBSET_CONTEXT_LAYER_ID,
    UPSTREAM_CONTEXT_LAYER_ID,
    DOWNSTREAM_CONTEXT_LAYER_ID,
    PATHWAY_HIGHLIGHT_CONTEXT_LAYER_ID,
    DOWNSTREAM_MODULE_CONTEXT_LAYER_ID,
)

BOUNDARY_OVERLAY_CATEGORY = "boundary"
DIRECTIONAL_CONTEXT_OVERLAY_CATEGORY = "directional_context"
PATHWAY_HIGHLIGHT_OVERLAY_CATEGORY = "pathway_highlight"
DOWNSTREAM_MODULE_OVERLAY_CATEGORY = "downstream_module"
METADATA_FACET_OVERLAY_CATEGORY = "metadata_facet"

SUPPORTED_OVERLAY_CATEGORIES = (
    BOUNDARY_OVERLAY_CATEGORY,
    DIRECTIONAL_CONTEXT_OVERLAY_CATEGORY,
    PATHWAY_HIGHLIGHT_OVERLAY_CATEGORY,
    DOWNSTREAM_MODULE_OVERLAY_CATEGORY,
    METADATA_FACET_OVERLAY_CATEGORY,
)

ACTIVE_BOUNDARY_OVERLAY_ID = "active_boundary"
UPSTREAM_GRAPH_OVERLAY_ID = "upstream_graph"
DOWNSTREAM_GRAPH_OVERLAY_ID = "downstream_graph"
PATHWAY_HIGHLIGHT_OVERLAY_ID = "pathway_highlight"
DOWNSTREAM_MODULE_OVERLAY_ID = "downstream_module"
METADATA_FACET_BADGES_OVERLAY_ID = "metadata_facet_badges"

SUPPORTED_OVERLAY_IDS = (
    ACTIVE_BOUNDARY_OVERLAY_ID,
    UPSTREAM_GRAPH_OVERLAY_ID,
    DOWNSTREAM_GRAPH_OVERLAY_ID,
    PATHWAY_HIGHLIGHT_OVERLAY_ID,
    DOWNSTREAM_MODULE_OVERLAY_ID,
    METADATA_FACET_BADGES_OVERLAY_ID,
)
DEFAULT_OVERLAY_ID = ACTIVE_BOUNDARY_OVERLAY_ID

LOCAL_SHELL_COMPACT_REDUCTION_PROFILE_ID = "local_shell_compact"
BALANCED_NEIGHBORHOOD_REDUCTION_PROFILE_ID = "balanced_neighborhood"
PATHWAY_FOCUS_REDUCTION_PROFILE_ID = "pathway_focus"
DOWNSTREAM_MODULE_COLLAPSED_REDUCTION_PROFILE_ID = "downstream_module_collapsed"

SUPPORTED_REDUCTION_PROFILE_IDS = (
    LOCAL_SHELL_COMPACT_REDUCTION_PROFILE_ID,
    BALANCED_NEIGHBORHOOD_REDUCTION_PROFILE_ID,
    PATHWAY_FOCUS_REDUCTION_PROFILE_ID,
    DOWNSTREAM_MODULE_COLLAPSED_REDUCTION_PROFILE_ID,
)
DEFAULT_REDUCTION_PROFILE_ID = BALANCED_NEIGHBORHOOD_REDUCTION_PROFILE_ID

NODE_METADATA_FACET_SCOPE = "node"
DOWNSTREAM_MODULE_METADATA_FACET_SCOPE = "downstream_module"
BOTH_METADATA_FACET_SCOPE = "both"
SUPPORTED_METADATA_FACET_SCOPES = (
    NODE_METADATA_FACET_SCOPE,
    DOWNSTREAM_MODULE_METADATA_FACET_SCOPE,
    BOTH_METADATA_FACET_SCOPE,
)

CELL_CLASS_METADATA_FACET_ID = "cell_class"
CELL_TYPE_METADATA_FACET_ID = "cell_type"
NEUROPIL_METADATA_FACET_ID = "neuropil"
SIDE_METADATA_FACET_ID = "side"
NT_TYPE_METADATA_FACET_ID = "nt_type"
SELECTION_BOUNDARY_STATUS_METADATA_FACET_ID = "selection_boundary_status"
PATHWAY_RELEVANCE_STATUS_METADATA_FACET_ID = "pathway_relevance_status"

SUPPORTED_METADATA_FACET_IDS = (
    CELL_CLASS_METADATA_FACET_ID,
    CELL_TYPE_METADATA_FACET_ID,
    NEUROPIL_METADATA_FACET_ID,
    SIDE_METADATA_FACET_ID,
    NT_TYPE_METADATA_FACET_ID,
    SELECTION_BOUNDARY_STATUS_METADATA_FACET_ID,
    PATHWAY_RELEVANCE_STATUS_METADATA_FACET_ID,
)

SIMPLIFIED_READOUT_MODULE_ROLE_ID = "simplified_readout_module"
COLLAPSED_PROJECTION_MODULE_ROLE_ID = "collapsed_projection_module"
SUPPORTED_DOWNSTREAM_MODULE_ROLE_IDS = (
    SIMPLIFIED_READOUT_MODULE_ROLE_ID,
    COLLAPSED_PROJECTION_MODULE_ROLE_ID,
)

SELECTED_ROOT_IDS_ROLE_ID = "selected_root_ids"
SUBSET_MANIFEST_ROLE_ID = "subset_manifest"
SUBSET_STATS_ROLE_ID = "subset_stats"
SYNAPSE_REGISTRY_ROLE_ID = "synapse_registry"
DASHBOARD_SESSION_METADATA_ROLE_ID = "dashboard_session_metadata"
DASHBOARD_SESSION_PAYLOAD_ROLE_ID = "dashboard_session_payload"
DASHBOARD_SESSION_STATE_ROLE_ID = "dashboard_session_state"
SHOWCASE_SESSION_METADATA_ROLE_ID = "showcase_session_metadata"
SHOWCASE_PRESENTATION_STATE_ROLE_ID = "showcase_presentation_state"
WHOLE_BRAIN_CONTEXT_SESSION_METADATA_ROLE_ID = "whole_brain_context_session_metadata"
CONTEXT_VIEW_PAYLOAD_ROLE_ID = "context_view_payload"
CONTEXT_QUERY_CATALOG_ROLE_ID = "context_query_catalog"
CONTEXT_VIEW_STATE_ROLE_ID = "context_view_state"

SUPPORTED_ARTIFACT_ROLE_IDS = (
    SELECTED_ROOT_IDS_ROLE_ID,
    SUBSET_MANIFEST_ROLE_ID,
    SUBSET_STATS_ROLE_ID,
    SYNAPSE_REGISTRY_ROLE_ID,
    DASHBOARD_SESSION_METADATA_ROLE_ID,
    DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
    DASHBOARD_SESSION_STATE_ROLE_ID,
    SHOWCASE_SESSION_METADATA_ROLE_ID,
    SHOWCASE_PRESENTATION_STATE_ROLE_ID,
    WHOLE_BRAIN_CONTEXT_SESSION_METADATA_ROLE_ID,
    CONTEXT_VIEW_PAYLOAD_ROLE_ID,
    CONTEXT_QUERY_CATALOG_ROLE_ID,
    CONTEXT_VIEW_STATE_ROLE_ID,
)

ACTIVE_SUBSET_INPUTS_DISCOVERY_HOOK_ID = "active_subset_inputs"
LOCAL_CONNECTIVITY_INPUTS_DISCOVERY_HOOK_ID = "local_connectivity_inputs"
DASHBOARD_CONTEXT_BRIDGE_DISCOVERY_HOOK_ID = "dashboard_context_bridge"
SHOWCASE_CONTEXT_BRIDGE_DISCOVERY_HOOK_ID = "showcase_context_bridge"
WHOLE_BRAIN_CONTEXT_PACKAGE_DISCOVERY_HOOK_ID = "whole_brain_context_package"

SUPPORTED_DISCOVERY_HOOK_IDS = (
    ACTIVE_SUBSET_INPUTS_DISCOVERY_HOOK_ID,
    LOCAL_CONNECTIVITY_INPUTS_DISCOVERY_HOOK_ID,
    DASHBOARD_CONTEXT_BRIDGE_DISCOVERY_HOOK_ID,
    SHOWCASE_CONTEXT_BRIDGE_DISCOVERY_HOOK_ID,
    WHOLE_BRAIN_CONTEXT_PACKAGE_DISCOVERY_HOOK_ID,
)

JSON_CONTEXT_VIEW_PAYLOAD_FORMAT = "json_whole_brain_context_view_payload.v1"
JSON_CONTEXT_QUERY_CATALOG_FORMAT = "json_whole_brain_context_query_catalog.v1"
JSON_CONTEXT_VIEW_STATE_FORMAT = "json_whole_brain_context_view_state.v1"

REQUIRED_UPSTREAM_CONTRACTS = (
    COUPLING_BUNDLE_CONTRACT_VERSION,
    DASHBOARD_SESSION_CONTRACT_VERSION,
    SHOWCASE_SESSION_CONTRACT_VERSION,
)

_QUERY_PROFILE_ORDER = {
    value: index for index, value in enumerate(SUPPORTED_QUERY_PROFILE_IDS)
}
_NODE_ROLE_ORDER = {value: index for index, value in enumerate(SUPPORTED_NODE_ROLE_IDS)}
_EDGE_ROLE_ORDER = {value: index for index, value in enumerate(SUPPORTED_EDGE_ROLE_IDS)}
_CONTEXT_LAYER_ORDER = {
    value: index for index, value in enumerate(SUPPORTED_CONTEXT_LAYER_IDS)
}
_OVERLAY_ID_ORDER = {value: index for index, value in enumerate(SUPPORTED_OVERLAY_IDS)}
_REDUCTION_PROFILE_ORDER = {
    value: index for index, value in enumerate(SUPPORTED_REDUCTION_PROFILE_IDS)
}
_METADATA_FACET_ORDER = {
    value: index for index, value in enumerate(SUPPORTED_METADATA_FACET_IDS)
}
_DOWNSTREAM_MODULE_ROLE_ORDER = {
    value: index for index, value in enumerate(SUPPORTED_DOWNSTREAM_MODULE_ROLE_IDS)
}
_ARTIFACT_SOURCE_KIND_ORDER = {
    value: index for index, value in enumerate(SUPPORTED_ARTIFACT_SOURCE_KINDS)
}
_ARTIFACT_ROLE_ORDER = {value: index for index, value in enumerate(SUPPORTED_ARTIFACT_ROLE_IDS)}
_DISCOVERY_HOOK_ORDER = {
    value: index for index, value in enumerate(SUPPORTED_DISCOVERY_HOOK_IDS)
}


@dataclass(frozen=True)
class WholeBrainContextSessionBundlePaths:
    processed_simulator_results_dir: Path
    experiment_id: str
    context_spec_hash: str
    bundle_directory: Path
    metadata_json_path: Path
    context_view_payload_path: Path
    context_query_catalog_path: Path
    context_view_state_path: Path

    @property
    def bundle_id(self) -> str:
        return (
            f"{WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION}:"
            f"{self.experiment_id}:{self.context_spec_hash}"
        )

    def asset_paths(self) -> dict[str, Path]:
        return {
            METADATA_JSON_KEY: self.metadata_json_path,
            CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID: self.context_view_payload_path,
            CONTEXT_QUERY_CATALOG_ARTIFACT_ID: self.context_query_catalog_path,
            CONTEXT_VIEW_STATE_ARTIFACT_ID: self.context_view_state_path,
        }


def build_whole_brain_context_session_bundle_paths(
    *,
    experiment_id: str,
    context_spec_hash: str,
    processed_simulator_results_dir: str | Path = DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
) -> WholeBrainContextSessionBundlePaths:
    normalized_experiment_id = _normalize_identifier(
        experiment_id,
        field_name="experiment_id",
    )
    normalized_context_spec_hash = _normalize_hex_hash(
        context_spec_hash,
        field_name="context_spec_hash",
    )
    processed_dir = Path(processed_simulator_results_dir).resolve()
    bundle_directory = (
        processed_dir
        / DEFAULT_WHOLE_BRAIN_CONTEXT_SESSION_DIRECTORY_NAME
        / normalized_experiment_id
        / normalized_context_spec_hash
    )
    return WholeBrainContextSessionBundlePaths(
        processed_simulator_results_dir=processed_dir,
        experiment_id=normalized_experiment_id,
        context_spec_hash=normalized_context_spec_hash,
        bundle_directory=bundle_directory,
        metadata_json_path=bundle_directory / "whole_brain_context_session.json",
        context_view_payload_path=bundle_directory / "context_view_payload.json",
        context_query_catalog_path=bundle_directory / "context_query_catalog.json",
        context_view_state_path=bundle_directory / "context_view_state.json",
    )


def build_whole_brain_context_query_profile_definition(
    *,
    query_profile_id: str,
    display_name: str,
    description: str,
    query_family: str,
    default_context_layer_ids: Sequence[str],
    supported_overlay_ids: Sequence[str],
    default_overlay_id: str,
    default_reduction_profile_id: str,
    required_artifact_role_ids: Sequence[str],
    scientific_curation_required: bool,
    truthfulness_note: str,
) -> dict[str, Any]:
    return parse_whole_brain_context_query_profile_definition(
        {
            "query_profile_id": query_profile_id,
            "display_name": display_name,
            "description": description,
            "query_family": query_family,
            "default_context_layer_ids": list(default_context_layer_ids),
            "supported_overlay_ids": list(supported_overlay_ids),
            "default_overlay_id": default_overlay_id,
            "default_reduction_profile_id": default_reduction_profile_id,
            "required_artifact_role_ids": list(required_artifact_role_ids),
            "scientific_curation_required": scientific_curation_required,
            "truthfulness_note": truthfulness_note,
        }
    )


def build_whole_brain_context_node_role_definition(
    *,
    node_role_id: str,
    display_name: str,
    description: str,
    selection_boundary_status: str,
    supported_context_layer_ids: Sequence[str],
    counts_as_active_selected: bool,
    counts_as_context_only: bool,
    truthfulness_note: str,
) -> dict[str, Any]:
    return parse_whole_brain_context_node_role_definition(
        {
            "node_role_id": node_role_id,
            "display_name": display_name,
            "description": description,
            "selection_boundary_status": selection_boundary_status,
            "supported_context_layer_ids": list(supported_context_layer_ids),
            "counts_as_active_selected": counts_as_active_selected,
            "counts_as_context_only": counts_as_context_only,
            "truthfulness_note": truthfulness_note,
        }
    )


def build_whole_brain_context_edge_role_definition(
    *,
    edge_role_id: str,
    display_name: str,
    description: str,
    direction_family: str,
    allowed_source_node_role_ids: Sequence[str],
    allowed_target_node_role_ids: Sequence[str],
    truthfulness_note: str,
) -> dict[str, Any]:
    return parse_whole_brain_context_edge_role_definition(
        {
            "edge_role_id": edge_role_id,
            "display_name": display_name,
            "description": description,
            "direction_family": direction_family,
            "allowed_source_node_role_ids": list(allowed_source_node_role_ids),
            "allowed_target_node_role_ids": list(allowed_target_node_role_ids),
            "truthfulness_note": truthfulness_note,
        }
    )


def build_whole_brain_context_layer_definition(
    *,
    context_layer_id: str,
    display_name: str,
    description: str,
    sequence_index: int,
    layer_kind: str,
    default_visible: bool,
    supported_node_role_ids: Sequence[str],
) -> dict[str, Any]:
    return parse_whole_brain_context_layer_definition(
        {
            "context_layer_id": context_layer_id,
            "display_name": display_name,
            "description": description,
            "sequence_index": sequence_index,
            "layer_kind": layer_kind,
            "default_visible": default_visible,
            "supported_node_role_ids": list(supported_node_role_ids),
        }
    )


def build_whole_brain_context_overlay_definition(
    *,
    overlay_id: str,
    display_name: str,
    description: str,
    overlay_category: str,
    supported_query_profile_ids: Sequence[str],
    supported_context_layer_ids: Sequence[str],
    required_node_role_ids: Sequence[str],
    required_edge_role_ids: Sequence[str],
    fairness_note: str,
) -> dict[str, Any]:
    return parse_whole_brain_context_overlay_definition(
        {
            "overlay_id": overlay_id,
            "display_name": display_name,
            "description": description,
            "overlay_category": overlay_category,
            "supported_query_profile_ids": list(supported_query_profile_ids),
            "supported_context_layer_ids": list(supported_context_layer_ids),
            "required_node_role_ids": list(required_node_role_ids),
            "required_edge_role_ids": list(required_edge_role_ids),
            "fairness_note": fairness_note,
        }
    )


def build_whole_brain_context_reduction_profile_definition(
    *,
    reduction_profile_id: str,
    display_name: str,
    description: str,
    max_context_node_count: int,
    max_edge_count: int,
    max_pathway_highlight_count: int,
    max_downstream_module_count: int,
    preserve_active_subset: bool,
) -> dict[str, Any]:
    return parse_whole_brain_context_reduction_profile_definition(
        {
            "reduction_profile_id": reduction_profile_id,
            "display_name": display_name,
            "description": description,
            "max_context_node_count": max_context_node_count,
            "max_edge_count": max_edge_count,
            "max_pathway_highlight_count": max_pathway_highlight_count,
            "max_downstream_module_count": max_downstream_module_count,
            "preserve_active_subset": preserve_active_subset,
        }
    )


def build_whole_brain_context_metadata_facet_definition(
    *,
    metadata_facet_id: str,
    display_name: str,
    description: str,
    facet_scope: str,
    default_enabled: bool,
) -> dict[str, Any]:
    return parse_whole_brain_context_metadata_facet_definition(
        {
            "metadata_facet_id": metadata_facet_id,
            "display_name": display_name,
            "description": description,
            "facet_scope": facet_scope,
            "default_enabled": default_enabled,
        }
    )


def build_whole_brain_context_downstream_module_role_definition(
    *,
    downstream_module_role_id: str,
    display_name: str,
    description: str,
    default_context_layer_id: str,
    allows_aggregated_readout: bool,
    requires_scientific_curation: bool,
    truthfulness_note: str,
) -> dict[str, Any]:
    return parse_whole_brain_context_downstream_module_role_definition(
        {
            "downstream_module_role_id": downstream_module_role_id,
            "display_name": display_name,
            "description": description,
            "default_context_layer_id": default_context_layer_id,
            "allows_aggregated_readout": allows_aggregated_readout,
            "requires_scientific_curation": requires_scientific_curation,
            "truthfulness_note": truthfulness_note,
        }
    )


def build_whole_brain_context_artifact_hook_definition(
    *,
    artifact_role_id: str,
    display_name: str,
    description: str,
    source_kind: str,
    required_contract_version: str | None,
    artifact_id: str,
    artifact_scope: str,
    discovery_note: str,
) -> dict[str, Any]:
    return parse_whole_brain_context_artifact_hook_definition(
        {
            "artifact_role_id": artifact_role_id,
            "display_name": display_name,
            "description": description,
            "source_kind": source_kind,
            "required_contract_version": required_contract_version,
            "artifact_id": artifact_id,
            "artifact_scope": artifact_scope,
            "discovery_note": discovery_note,
        }
    )


def build_whole_brain_context_discovery_hook_definition(
    *,
    hook_id: str,
    display_name: str,
    description: str,
    source_kind: str,
    artifact_role_ids: Sequence[str],
    canonical_anchor_artifact_role_id: str,
    required_contract_version: str | None,
) -> dict[str, Any]:
    return parse_whole_brain_context_discovery_hook_definition(
        {
            "hook_id": hook_id,
            "display_name": display_name,
            "description": description,
            "source_kind": source_kind,
            "artifact_role_ids": list(artifact_role_ids),
            "canonical_anchor_artifact_role_id": canonical_anchor_artifact_role_id,
            "required_contract_version": required_contract_version,
        }
    )


def build_whole_brain_context_query_state(
    *,
    query_profile_id: str = DEFAULT_QUERY_PROFILE_ID,
    default_overlay_id: str | None = None,
    default_reduction_profile_id: str | None = None,
    enabled_overlay_ids: Sequence[str] | None = None,
    enabled_metadata_facet_ids: Sequence[str] | None = None,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_contract = parse_whole_brain_context_contract_metadata(
        contract_metadata
        if contract_metadata is not None
        else build_whole_brain_context_contract_metadata()
    )
    query_profile = get_whole_brain_context_query_profile_definition(
        query_profile_id,
        record=normalized_contract,
    )
    return parse_whole_brain_context_query_state(
        {
            "query_profile_id": query_profile["query_profile_id"],
            "default_overlay_id": (
                query_profile["default_overlay_id"]
                if default_overlay_id is None
                else default_overlay_id
            ),
            "default_reduction_profile_id": (
                query_profile["default_reduction_profile_id"]
                if default_reduction_profile_id is None
                else default_reduction_profile_id
            ),
            "enabled_overlay_ids": (
                list(query_profile["supported_overlay_ids"])
                if enabled_overlay_ids is None
                else list(enabled_overlay_ids)
            ),
            "enabled_metadata_facet_ids": (
                [
                    item["metadata_facet_id"]
                    for item in discover_whole_brain_context_metadata_facets(
                        normalized_contract
                    )
                    if item["default_enabled"]
                ]
                if enabled_metadata_facet_ids is None
                else list(enabled_metadata_facet_ids)
            ),
        },
        contract_metadata=normalized_contract,
    )


def build_whole_brain_context_artifact_reference(
    *,
    artifact_role_id: str,
    source_kind: str,
    path: str | Path,
    contract_version: str | None,
    bundle_id: str,
    artifact_id: str,
    format: str | None = None,
    artifact_scope: str | None = None,
    status: str = ASSET_STATUS_READY,
) -> dict[str, Any]:
    return parse_whole_brain_context_artifact_reference(
        {
            "artifact_role_id": artifact_role_id,
            "source_kind": source_kind,
            "path": str(Path(path).resolve()),
            "contract_version": contract_version,
            "bundle_id": bundle_id,
            "artifact_id": artifact_id,
            "format": format,
            "artifact_scope": artifact_scope,
            "status": status,
        }
    )


def build_whole_brain_context_node_record(
    *,
    root_id: str | int,
    node_role_id: str,
    context_layer_id: str,
    overlay_ids: Sequence[str] | None = None,
    metadata_facet_values: Mapping[str, Any] | None = None,
    display_label: str | None = None,
) -> dict[str, Any]:
    return parse_whole_brain_context_node_record(
        {
            "root_id": root_id,
            "node_role_id": node_role_id,
            "context_layer_id": context_layer_id,
            "overlay_ids": [] if overlay_ids is None else list(overlay_ids),
            "metadata_facet_values": (
                {} if metadata_facet_values is None else dict(metadata_facet_values)
            ),
            "display_label": display_label,
        }
    )


def build_whole_brain_context_edge_record(
    *,
    source_root_id: str | int,
    target_root_id: str | int,
    edge_role_id: str,
    overlay_ids: Sequence[str] | None = None,
    weight: float | int | None = None,
) -> dict[str, Any]:
    return parse_whole_brain_context_edge_record(
        {
            "source_root_id": source_root_id,
            "target_root_id": target_root_id,
            "edge_role_id": edge_role_id,
            "overlay_ids": [] if overlay_ids is None else list(overlay_ids),
            "weight": weight,
        }
    )


def build_whole_brain_context_downstream_module_record(
    *,
    module_id: str,
    downstream_module_role_id: str,
    display_name: str,
    description: str,
    represented_root_ids: Sequence[str | int],
    overlay_ids: Sequence[str] | None = None,
    metadata_facet_values: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return parse_whole_brain_context_downstream_module_record(
        {
            "module_id": module_id,
            "downstream_module_role_id": downstream_module_role_id,
            "display_name": display_name,
            "description": description,
            "represented_root_ids": list(represented_root_ids),
            "overlay_ids": [] if overlay_ids is None else list(overlay_ids),
            "metadata_facet_values": (
                {} if metadata_facet_values is None else dict(metadata_facet_values)
            ),
        }
    )


def build_whole_brain_context_contract_metadata(
    *,
    query_profile_definitions: Sequence[Mapping[str, Any]] | None = None,
    node_role_definitions: Sequence[Mapping[str, Any]] | None = None,
    edge_role_definitions: Sequence[Mapping[str, Any]] | None = None,
    context_layer_definitions: Sequence[Mapping[str, Any]] | None = None,
    overlay_definitions: Sequence[Mapping[str, Any]] | None = None,
    reduction_profile_definitions: Sequence[Mapping[str, Any]] | None = None,
    metadata_facet_definitions: Sequence[Mapping[str, Any]] | None = None,
    downstream_module_role_definitions: Sequence[Mapping[str, Any]] | None = None,
    artifact_hook_definitions: Sequence[Mapping[str, Any]] | None = None,
    discovery_hook_definitions: Sequence[Mapping[str, Any]] | None = None,
    default_delivery_model: str = DEFAULT_DELIVERY_MODEL,
) -> dict[str, Any]:
    return parse_whole_brain_context_contract_metadata(
        {
            "contract_version": WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
            "design_note": WHOLE_BRAIN_CONTEXT_SESSION_DESIGN_NOTE,
            "design_note_version": WHOLE_BRAIN_CONTEXT_SESSION_DESIGN_NOTE_VERSION,
            "default_delivery_model": default_delivery_model,
            "supported_delivery_models": list(SUPPORTED_DELIVERY_MODELS),
            "required_upstream_contracts": list(REQUIRED_UPSTREAM_CONTRACTS),
            "supported_query_families": list(SUPPORTED_QUERY_FAMILIES),
            "supported_query_profile_ids": list(SUPPORTED_QUERY_PROFILE_IDS),
            "supported_node_boundary_statuses": list(
                SUPPORTED_NODE_BOUNDARY_STATUSES
            ),
            "supported_node_role_ids": list(SUPPORTED_NODE_ROLE_IDS),
            "supported_edge_direction_families": list(
                SUPPORTED_EDGE_DIRECTION_FAMILIES
            ),
            "supported_edge_role_ids": list(SUPPORTED_EDGE_ROLE_IDS),
            "supported_layer_kinds": list(SUPPORTED_LAYER_KINDS),
            "supported_context_layer_ids": list(SUPPORTED_CONTEXT_LAYER_IDS),
            "supported_overlay_categories": list(SUPPORTED_OVERLAY_CATEGORIES),
            "supported_overlay_ids": list(SUPPORTED_OVERLAY_IDS),
            "supported_reduction_profile_ids": list(SUPPORTED_REDUCTION_PROFILE_IDS),
            "supported_metadata_facet_scopes": list(
                SUPPORTED_METADATA_FACET_SCOPES
            ),
            "supported_metadata_facet_ids": list(SUPPORTED_METADATA_FACET_IDS),
            "supported_downstream_module_role_ids": list(
                SUPPORTED_DOWNSTREAM_MODULE_ROLE_IDS
            ),
            "supported_artifact_source_kinds": list(
                SUPPORTED_ARTIFACT_SOURCE_KINDS
            ),
            "supported_artifact_scopes": list(SUPPORTED_ARTIFACT_SCOPES),
            "supported_artifact_role_ids": list(SUPPORTED_ARTIFACT_ROLE_IDS),
            "supported_discovery_hook_ids": list(SUPPORTED_DISCOVERY_HOOK_IDS),
            "default_query_profile_id": DEFAULT_QUERY_PROFILE_ID,
            "default_overlay_id": DEFAULT_OVERLAY_ID,
            "default_reduction_profile_id": DEFAULT_REDUCTION_PROFILE_ID,
            "active_boundary_invariants": list(_default_active_boundary_invariants()),
            "truthfulness_invariants": list(_default_truthfulness_invariants()),
            "query_profile_catalog": list(
                query_profile_definitions
                if query_profile_definitions is not None
                else _default_query_profile_catalog()
            ),
            "node_role_catalog": list(
                node_role_definitions
                if node_role_definitions is not None
                else _default_node_role_catalog()
            ),
            "edge_role_catalog": list(
                edge_role_definitions
                if edge_role_definitions is not None
                else _default_edge_role_catalog()
            ),
            "context_layer_catalog": list(
                context_layer_definitions
                if context_layer_definitions is not None
                else _default_context_layer_catalog()
            ),
            "overlay_catalog": list(
                overlay_definitions
                if overlay_definitions is not None
                else _default_overlay_catalog()
            ),
            "reduction_profile_catalog": list(
                reduction_profile_definitions
                if reduction_profile_definitions is not None
                else _default_reduction_profile_catalog()
            ),
            "metadata_facet_catalog": list(
                metadata_facet_definitions
                if metadata_facet_definitions is not None
                else _default_metadata_facet_catalog()
            ),
            "downstream_module_role_catalog": list(
                downstream_module_role_definitions
                if downstream_module_role_definitions is not None
                else _default_downstream_module_role_catalog()
            ),
            "artifact_hook_catalog": list(
                artifact_hook_definitions
                if artifact_hook_definitions is not None
                else _default_artifact_hook_catalog()
            ),
            "discovery_hook_catalog": list(
                discovery_hook_definitions
                if discovery_hook_definitions is not None
                else _default_discovery_hook_catalog()
            ),
        }
    )


def build_whole_brain_context_session_spec_hash(
    *,
    experiment_id: str,
    delivery_model: str,
    query_state: Mapping[str, Any],
    artifact_references: Sequence[Mapping[str, Any]],
    representative_context: Mapping[str, Any],
) -> str:
    identity_payload = {
        "experiment_id": _normalize_identifier(experiment_id, field_name="experiment_id"),
        "delivery_model": _normalize_delivery_model(delivery_model),
        "query_state": parse_whole_brain_context_query_state(
            query_state,
            contract_metadata=build_whole_brain_context_contract_metadata(),
        ),
        "artifact_references": _normalize_artifact_reference_catalog(
            artifact_references,
            field_name="artifact_references",
        ),
        "representative_context": _normalize_representative_context(
            representative_context,
            field_name="representative_context",
        ),
    }
    serialized = json.dumps(
        identity_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_whole_brain_context_session_metadata(
    *,
    experiment_id: str,
    artifact_references: Sequence[Mapping[str, Any]],
    representative_context: Mapping[str, Any] | None = None,
    query_state: Mapping[str, Any] | None = None,
    processed_simulator_results_dir: str | Path = DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
    delivery_model: str = DEFAULT_DELIVERY_MODEL,
    context_view_payload_status: str = ASSET_STATUS_MISSING,
    context_query_catalog_status: str = ASSET_STATUS_MISSING,
    context_view_state_status: str = ASSET_STATUS_READY,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_contract = parse_whole_brain_context_contract_metadata(
        contract_metadata
        if contract_metadata is not None
        else build_whole_brain_context_contract_metadata()
    )
    normalized_query_state = parse_whole_brain_context_query_state(
        query_state
        if query_state is not None
        else build_whole_brain_context_query_state(contract_metadata=normalized_contract),
        contract_metadata=normalized_contract,
    )
    normalized_representative_context = _normalize_representative_context(
        {
            "node_records": [],
            "edge_records": [],
            "downstream_module_records": [],
        }
        if representative_context is None
        else representative_context,
        field_name="representative_context",
    )
    _validate_representative_context_against_contract(
        normalized_representative_context,
        contract_metadata=normalized_contract,
        query_state=normalized_query_state,
        field_name="representative_context",
    )
    normalized_artifact_references = _normalize_artifact_reference_catalog(
        artifact_references,
        field_name="artifact_references",
    )
    _validate_artifact_references_against_contract(
        normalized_artifact_references,
        contract_metadata=normalized_contract,
        field_name="artifact_references",
    )
    normalized_experiment_id = _normalize_identifier(
        experiment_id,
        field_name="experiment_id",
    )
    normalized_delivery_model = _normalize_delivery_model(delivery_model)
    context_spec_hash = build_whole_brain_context_session_spec_hash(
        experiment_id=normalized_experiment_id,
        delivery_model=normalized_delivery_model,
        query_state=normalized_query_state,
        artifact_references=normalized_artifact_references,
        representative_context=normalized_representative_context,
    )
    bundle_paths = build_whole_brain_context_session_bundle_paths(
        experiment_id=normalized_experiment_id,
        context_spec_hash=context_spec_hash,
        processed_simulator_results_dir=processed_simulator_results_dir,
    )
    artifacts = {
        METADATA_JSON_KEY: _artifact_record(
            path=bundle_paths.metadata_json_path,
            format="json_whole_brain_context_session_metadata.v1",
            status=ASSET_STATUS_READY,
            artifact_scope=CONTRACT_METADATA_SCOPE,
            description="Authoritative Milestone 17 whole-brain context session metadata.",
        ),
        CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID: _artifact_record(
            path=bundle_paths.context_view_payload_path,
            format=JSON_CONTEXT_VIEW_PAYLOAD_FORMAT,
            status=context_view_payload_status,
            artifact_scope=CONTEXT_VIEW_SCOPE,
            description="Reserved packaged whole-brain context view payload for local review surfaces.",
        ),
        CONTEXT_QUERY_CATALOG_ARTIFACT_ID: _artifact_record(
            path=bundle_paths.context_query_catalog_path,
            format=JSON_CONTEXT_QUERY_CATALOG_FORMAT,
            status=context_query_catalog_status,
            artifact_scope=CONTEXT_QUERY_SCOPE,
            description="Reserved packaged query-taxonomy catalog for deterministic Milestone 17 discovery.",
        ),
        CONTEXT_VIEW_STATE_ARTIFACT_ID: _artifact_record(
            path=bundle_paths.context_view_state_path,
            format=JSON_CONTEXT_VIEW_STATE_FORMAT,
            status=context_view_state_status,
            artifact_scope=CONTEXT_STATE_SCOPE,
            description="Exportable serialized whole-brain context view state for deterministic replay and review.",
        ),
    }
    local_artifact_references = [
        build_whole_brain_context_artifact_reference(
            artifact_role_id=WHOLE_BRAIN_CONTEXT_SESSION_METADATA_ROLE_ID,
            source_kind=WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND,
            path=artifacts[METADATA_JSON_KEY]["path"],
            contract_version=WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
            bundle_id=bundle_paths.bundle_id,
            artifact_id=METADATA_JSON_KEY,
            format=artifacts[METADATA_JSON_KEY]["format"],
            artifact_scope=artifacts[METADATA_JSON_KEY]["artifact_scope"],
            status=artifacts[METADATA_JSON_KEY]["status"],
        ),
        build_whole_brain_context_artifact_reference(
            artifact_role_id=CONTEXT_VIEW_PAYLOAD_ROLE_ID,
            source_kind=WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND,
            path=artifacts[CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID]["path"],
            contract_version=WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
            bundle_id=bundle_paths.bundle_id,
            artifact_id=CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID,
            format=artifacts[CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID]["format"],
            artifact_scope=artifacts[CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID]["artifact_scope"],
            status=artifacts[CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID]["status"],
        ),
        build_whole_brain_context_artifact_reference(
            artifact_role_id=CONTEXT_QUERY_CATALOG_ROLE_ID,
            source_kind=WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND,
            path=artifacts[CONTEXT_QUERY_CATALOG_ARTIFACT_ID]["path"],
            contract_version=WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
            bundle_id=bundle_paths.bundle_id,
            artifact_id=CONTEXT_QUERY_CATALOG_ARTIFACT_ID,
            format=artifacts[CONTEXT_QUERY_CATALOG_ARTIFACT_ID]["format"],
            artifact_scope=artifacts[CONTEXT_QUERY_CATALOG_ARTIFACT_ID]["artifact_scope"],
            status=artifacts[CONTEXT_QUERY_CATALOG_ARTIFACT_ID]["status"],
        ),
        build_whole_brain_context_artifact_reference(
            artifact_role_id=CONTEXT_VIEW_STATE_ROLE_ID,
            source_kind=WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND,
            path=artifacts[CONTEXT_VIEW_STATE_ARTIFACT_ID]["path"],
            contract_version=WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
            bundle_id=bundle_paths.bundle_id,
            artifact_id=CONTEXT_VIEW_STATE_ARTIFACT_ID,
            format=artifacts[CONTEXT_VIEW_STATE_ARTIFACT_ID]["format"],
            artifact_scope=artifacts[CONTEXT_VIEW_STATE_ARTIFACT_ID]["artifact_scope"],
            status=artifacts[CONTEXT_VIEW_STATE_ARTIFACT_ID]["status"],
        ),
    ]
    return parse_whole_brain_context_session_metadata(
        {
            "contract_version": WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
            "design_note": WHOLE_BRAIN_CONTEXT_SESSION_DESIGN_NOTE,
            "design_note_version": WHOLE_BRAIN_CONTEXT_SESSION_DESIGN_NOTE_VERSION,
            "bundle_id": bundle_paths.bundle_id,
            "experiment_id": normalized_experiment_id,
            "context_spec_hash": context_spec_hash,
            "context_spec_hash_algorithm": DEFAULT_HASH_ALGORITHM,
            "delivery_model": normalized_delivery_model,
            "query_state": normalized_query_state,
            "artifact_references": list(normalized_artifact_references)
            + list(local_artifact_references),
            "representative_context": normalized_representative_context,
            "output_root_reference": {
                "processed_simulator_results_dir": str(
                    bundle_paths.processed_simulator_results_dir
                )
            },
            "bundle_layout": {
                "bundle_directory": str(bundle_paths.bundle_directory),
            },
            "artifacts": artifacts,
        },
        contract_metadata=normalized_contract,
    )


def parse_whole_brain_context_query_profile_definition(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("whole-brain context query-profile definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "query_profile_id",
        "display_name",
        "description",
        "query_family",
        "default_context_layer_ids",
        "supported_overlay_ids",
        "default_overlay_id",
        "default_reduction_profile_id",
        "required_artifact_role_ids",
        "scientific_curation_required",
        "truthfulness_note",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "whole-brain context query-profile definition is missing fields: "
            f"{missing_fields!r}."
        )
    normalized["query_profile_id"] = _normalize_query_profile_id(
        normalized["query_profile_id"]
    )
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="query_profile.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="query_profile.description",
    )
    normalized["query_family"] = _normalize_query_family(normalized["query_family"])
    normalized["default_context_layer_ids"] = _normalize_known_value_list(
        normalized["default_context_layer_ids"],
        field_name="query_profile.default_context_layer_ids",
        supported_values=SUPPORTED_CONTEXT_LAYER_IDS,
        allow_empty=False,
    )
    normalized["supported_overlay_ids"] = _normalize_known_value_list(
        normalized["supported_overlay_ids"],
        field_name="query_profile.supported_overlay_ids",
        supported_values=SUPPORTED_OVERLAY_IDS,
        allow_empty=False,
    )
    normalized["default_overlay_id"] = _normalize_overlay_id(
        normalized["default_overlay_id"]
    )
    if normalized["default_overlay_id"] not in normalized["supported_overlay_ids"]:
        raise ValueError(
            "query_profile.default_overlay_id must be listed in supported_overlay_ids."
        )
    normalized["default_reduction_profile_id"] = _normalize_reduction_profile_id(
        normalized["default_reduction_profile_id"]
    )
    normalized["required_artifact_role_ids"] = _normalize_known_value_list(
        normalized["required_artifact_role_ids"],
        field_name="query_profile.required_artifact_role_ids",
        supported_values=SUPPORTED_ARTIFACT_ROLE_IDS,
        allow_empty=False,
    )
    normalized["scientific_curation_required"] = _normalize_boolean(
        normalized["scientific_curation_required"],
        field_name="query_profile.scientific_curation_required",
    )
    normalized["truthfulness_note"] = _normalize_nonempty_string(
        normalized["truthfulness_note"],
        field_name="query_profile.truthfulness_note",
    )
    return normalized


def parse_whole_brain_context_node_role_definition(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("whole-brain context node-role definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "node_role_id",
        "display_name",
        "description",
        "selection_boundary_status",
        "supported_context_layer_ids",
        "counts_as_active_selected",
        "counts_as_context_only",
        "truthfulness_note",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"whole-brain context node-role definition is missing fields: {missing_fields!r}."
        )
    normalized["node_role_id"] = _normalize_node_role_id(normalized["node_role_id"])
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="node_role.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="node_role.description",
    )
    normalized["selection_boundary_status"] = _normalize_node_boundary_status(
        normalized["selection_boundary_status"]
    )
    normalized["supported_context_layer_ids"] = _normalize_known_value_list(
        normalized["supported_context_layer_ids"],
        field_name="node_role.supported_context_layer_ids",
        supported_values=SUPPORTED_CONTEXT_LAYER_IDS,
        allow_empty=False,
    )
    normalized["counts_as_active_selected"] = _normalize_boolean(
        normalized["counts_as_active_selected"],
        field_name="node_role.counts_as_active_selected",
    )
    normalized["counts_as_context_only"] = _normalize_boolean(
        normalized["counts_as_context_only"],
        field_name="node_role.counts_as_context_only",
    )
    normalized["truthfulness_note"] = _normalize_nonempty_string(
        normalized["truthfulness_note"],
        field_name="node_role.truthfulness_note",
    )
    return normalized


def parse_whole_brain_context_edge_role_definition(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("whole-brain context edge-role definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "edge_role_id",
        "display_name",
        "description",
        "direction_family",
        "allowed_source_node_role_ids",
        "allowed_target_node_role_ids",
        "truthfulness_note",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"whole-brain context edge-role definition is missing fields: {missing_fields!r}."
        )
    normalized["edge_role_id"] = _normalize_edge_role_id(normalized["edge_role_id"])
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="edge_role.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="edge_role.description",
    )
    normalized["direction_family"] = _normalize_edge_direction_family(
        normalized["direction_family"]
    )
    normalized["allowed_source_node_role_ids"] = _normalize_known_value_list(
        normalized["allowed_source_node_role_ids"],
        field_name="edge_role.allowed_source_node_role_ids",
        supported_values=SUPPORTED_NODE_ROLE_IDS,
        allow_empty=True,
    )
    normalized["allowed_target_node_role_ids"] = _normalize_known_value_list(
        normalized["allowed_target_node_role_ids"],
        field_name="edge_role.allowed_target_node_role_ids",
        supported_values=SUPPORTED_NODE_ROLE_IDS,
        allow_empty=True,
    )
    normalized["truthfulness_note"] = _normalize_nonempty_string(
        normalized["truthfulness_note"],
        field_name="edge_role.truthfulness_note",
    )
    return normalized


def parse_whole_brain_context_layer_definition(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("whole-brain context layer definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "context_layer_id",
        "display_name",
        "description",
        "sequence_index",
        "layer_kind",
        "default_visible",
        "supported_node_role_ids",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"whole-brain context layer definition is missing fields: {missing_fields!r}."
        )
    normalized["context_layer_id"] = _normalize_context_layer_id(
        normalized["context_layer_id"]
    )
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="context_layer.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="context_layer.description",
    )
    normalized["sequence_index"] = _normalize_nonnegative_int(
        normalized["sequence_index"],
        field_name="context_layer.sequence_index",
    )
    normalized["layer_kind"] = _normalize_layer_kind(normalized["layer_kind"])
    normalized["default_visible"] = _normalize_boolean(
        normalized["default_visible"],
        field_name="context_layer.default_visible",
    )
    normalized["supported_node_role_ids"] = _normalize_known_value_list(
        normalized["supported_node_role_ids"],
        field_name="context_layer.supported_node_role_ids",
        supported_values=SUPPORTED_NODE_ROLE_IDS,
        allow_empty=True,
    )
    return normalized


def parse_whole_brain_context_overlay_definition(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("whole-brain context overlay definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "overlay_id",
        "display_name",
        "description",
        "overlay_category",
        "supported_query_profile_ids",
        "supported_context_layer_ids",
        "required_node_role_ids",
        "required_edge_role_ids",
        "fairness_note",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"whole-brain context overlay definition is missing fields: {missing_fields!r}."
        )
    normalized["overlay_id"] = _normalize_overlay_id(normalized["overlay_id"])
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="overlay.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="overlay.description",
    )
    normalized["overlay_category"] = _normalize_overlay_category(
        normalized["overlay_category"]
    )
    normalized["supported_query_profile_ids"] = _normalize_known_value_list(
        normalized["supported_query_profile_ids"],
        field_name="overlay.supported_query_profile_ids",
        supported_values=SUPPORTED_QUERY_PROFILE_IDS,
        allow_empty=False,
    )
    normalized["supported_context_layer_ids"] = _normalize_known_value_list(
        normalized["supported_context_layer_ids"],
        field_name="overlay.supported_context_layer_ids",
        supported_values=SUPPORTED_CONTEXT_LAYER_IDS,
        allow_empty=False,
    )
    normalized["required_node_role_ids"] = _normalize_known_value_list(
        normalized["required_node_role_ids"],
        field_name="overlay.required_node_role_ids",
        supported_values=SUPPORTED_NODE_ROLE_IDS,
        allow_empty=False,
    )
    normalized["required_edge_role_ids"] = _normalize_known_value_list(
        normalized["required_edge_role_ids"],
        field_name="overlay.required_edge_role_ids",
        supported_values=SUPPORTED_EDGE_ROLE_IDS,
        allow_empty=False,
    )
    normalized["fairness_note"] = _normalize_nonempty_string(
        normalized["fairness_note"],
        field_name="overlay.fairness_note",
    )
    return normalized


def parse_whole_brain_context_reduction_profile_definition(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(
            "whole-brain context reduction-profile definitions must be mappings."
        )
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "reduction_profile_id",
        "display_name",
        "description",
        "max_context_node_count",
        "max_edge_count",
        "max_pathway_highlight_count",
        "max_downstream_module_count",
        "preserve_active_subset",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "whole-brain context reduction-profile definition is missing fields: "
            f"{missing_fields!r}."
        )
    normalized["reduction_profile_id"] = _normalize_reduction_profile_id(
        normalized["reduction_profile_id"]
    )
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="reduction_profile.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="reduction_profile.description",
    )
    normalized["max_context_node_count"] = _normalize_positive_int(
        normalized["max_context_node_count"],
        field_name="reduction_profile.max_context_node_count",
    )
    normalized["max_edge_count"] = _normalize_positive_int(
        normalized["max_edge_count"],
        field_name="reduction_profile.max_edge_count",
    )
    normalized["max_pathway_highlight_count"] = _normalize_nonnegative_int(
        normalized["max_pathway_highlight_count"],
        field_name="reduction_profile.max_pathway_highlight_count",
    )
    normalized["max_downstream_module_count"] = _normalize_nonnegative_int(
        normalized["max_downstream_module_count"],
        field_name="reduction_profile.max_downstream_module_count",
    )
    normalized["preserve_active_subset"] = _normalize_boolean(
        normalized["preserve_active_subset"],
        field_name="reduction_profile.preserve_active_subset",
    )
    return normalized


def parse_whole_brain_context_metadata_facet_definition(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("whole-brain context metadata-facet definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "metadata_facet_id",
        "display_name",
        "description",
        "facet_scope",
        "default_enabled",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "whole-brain context metadata-facet definition is missing fields: "
            f"{missing_fields!r}."
        )
    normalized["metadata_facet_id"] = _normalize_metadata_facet_id(
        normalized["metadata_facet_id"]
    )
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="metadata_facet.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="metadata_facet.description",
    )
    normalized["facet_scope"] = _normalize_metadata_facet_scope(
        normalized["facet_scope"]
    )
    normalized["default_enabled"] = _normalize_boolean(
        normalized["default_enabled"],
        field_name="metadata_facet.default_enabled",
    )
    return normalized


def parse_whole_brain_context_downstream_module_role_definition(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(
            "whole-brain context downstream-module-role definitions must be mappings."
        )
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "downstream_module_role_id",
        "display_name",
        "description",
        "default_context_layer_id",
        "allows_aggregated_readout",
        "requires_scientific_curation",
        "truthfulness_note",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "whole-brain context downstream-module-role definition is missing fields: "
            f"{missing_fields!r}."
        )
    normalized["downstream_module_role_id"] = _normalize_downstream_module_role_id(
        normalized["downstream_module_role_id"]
    )
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="downstream_module_role.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="downstream_module_role.description",
    )
    normalized["default_context_layer_id"] = _normalize_context_layer_id(
        normalized["default_context_layer_id"]
    )
    normalized["allows_aggregated_readout"] = _normalize_boolean(
        normalized["allows_aggregated_readout"],
        field_name="downstream_module_role.allows_aggregated_readout",
    )
    normalized["requires_scientific_curation"] = _normalize_boolean(
        normalized["requires_scientific_curation"],
        field_name="downstream_module_role.requires_scientific_curation",
    )
    normalized["truthfulness_note"] = _normalize_nonempty_string(
        normalized["truthfulness_note"],
        field_name="downstream_module_role.truthfulness_note",
    )
    return normalized


def parse_whole_brain_context_artifact_hook_definition(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("whole-brain context artifact-hook definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "artifact_role_id",
        "display_name",
        "description",
        "source_kind",
        "required_contract_version",
        "artifact_id",
        "artifact_scope",
        "discovery_note",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"whole-brain context artifact-hook definition is missing fields: {missing_fields!r}."
        )
    normalized["artifact_role_id"] = _normalize_artifact_role_id(
        normalized["artifact_role_id"]
    )
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="artifact_hook.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="artifact_hook.description",
    )
    normalized["source_kind"] = _normalize_artifact_source_kind(
        normalized["source_kind"]
    )
    normalized["required_contract_version"] = _normalize_optional_string(
        normalized["required_contract_version"],
        field_name="artifact_hook.required_contract_version",
    )
    normalized["artifact_id"] = _normalize_identifier(
        normalized["artifact_id"],
        field_name="artifact_hook.artifact_id",
    )
    normalized["artifact_scope"] = _normalize_artifact_scope(
        normalized["artifact_scope"]
    )
    normalized["discovery_note"] = _normalize_nonempty_string(
        normalized["discovery_note"],
        field_name="artifact_hook.discovery_note",
    )
    return normalized


def parse_whole_brain_context_discovery_hook_definition(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("whole-brain context discovery-hook definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "hook_id",
        "display_name",
        "description",
        "source_kind",
        "artifact_role_ids",
        "canonical_anchor_artifact_role_id",
        "required_contract_version",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"whole-brain context discovery-hook definition is missing fields: {missing_fields!r}."
        )
    normalized["hook_id"] = _normalize_discovery_hook_id(normalized["hook_id"])
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="discovery_hook.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="discovery_hook.description",
    )
    normalized["source_kind"] = _normalize_artifact_source_kind(
        normalized["source_kind"]
    )
    normalized["artifact_role_ids"] = _normalize_known_value_list(
        normalized["artifact_role_ids"],
        field_name="discovery_hook.artifact_role_ids",
        supported_values=SUPPORTED_ARTIFACT_ROLE_IDS,
        allow_empty=False,
    )
    normalized["canonical_anchor_artifact_role_id"] = _normalize_artifact_role_id(
        normalized["canonical_anchor_artifact_role_id"]
    )
    normalized["required_contract_version"] = _normalize_optional_string(
        normalized["required_contract_version"],
        field_name="discovery_hook.required_contract_version",
    )
    return normalized


def parse_whole_brain_context_query_state(
    payload: Mapping[str, Any],
    *,
    contract_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("whole-brain context query_state must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "query_profile_id",
        "default_overlay_id",
        "default_reduction_profile_id",
        "enabled_overlay_ids",
        "enabled_metadata_facet_ids",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"whole-brain context query_state is missing fields: {missing_fields!r}."
        )
    contract = parse_whole_brain_context_contract_metadata(contract_metadata)
    query_profile = get_whole_brain_context_query_profile_definition(
        normalized["query_profile_id"],
        record=contract,
    )
    normalized["query_profile_id"] = query_profile["query_profile_id"]
    normalized["default_overlay_id"] = _normalize_overlay_id(
        normalized["default_overlay_id"]
    )
    normalized["default_reduction_profile_id"] = _normalize_reduction_profile_id(
        normalized["default_reduction_profile_id"]
    )
    normalized["enabled_overlay_ids"] = _normalize_known_value_list(
        normalized["enabled_overlay_ids"],
        field_name="query_state.enabled_overlay_ids",
        supported_values=SUPPORTED_OVERLAY_IDS,
        allow_empty=False,
    )
    normalized["enabled_metadata_facet_ids"] = _normalize_known_value_list(
        normalized["enabled_metadata_facet_ids"],
        field_name="query_state.enabled_metadata_facet_ids",
        supported_values=SUPPORTED_METADATA_FACET_IDS,
        allow_empty=False,
    )
    if normalized["default_overlay_id"] not in normalized["enabled_overlay_ids"]:
        raise ValueError(
            "query_state.default_overlay_id must be one of enabled_overlay_ids."
        )
    for overlay_id in normalized["enabled_overlay_ids"]:
        if overlay_id not in query_profile["supported_overlay_ids"]:
            raise ValueError(
                "query_state.enabled_overlay_ids includes overlays not supported by "
                f"{query_profile['query_profile_id']!r}."
            )
    return normalized


def parse_whole_brain_context_artifact_reference(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("whole-brain context artifact references must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "artifact_role_id",
        "source_kind",
        "path",
        "contract_version",
        "bundle_id",
        "artifact_id",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"whole-brain context artifact reference is missing fields: {missing_fields!r}."
        )
    normalized["artifact_role_id"] = _normalize_artifact_role_id(
        normalized["artifact_role_id"]
    )
    normalized["source_kind"] = _normalize_artifact_source_kind(
        normalized["source_kind"]
    )
    normalized["path"] = str(
        Path(
            _normalize_nonempty_string(
                normalized["path"],
                field_name="artifact_reference.path",
            )
        ).resolve()
    )
    normalized["contract_version"] = _normalize_optional_string(
        normalized["contract_version"],
        field_name="artifact_reference.contract_version",
    )
    normalized["bundle_id"] = _normalize_nonempty_string(
        normalized["bundle_id"],
        field_name="artifact_reference.bundle_id",
    )
    normalized["artifact_id"] = _normalize_identifier(
        normalized["artifact_id"],
        field_name="artifact_reference.artifact_id",
    )
    normalized["format"] = _normalize_optional_string(
        normalized.get("format"),
        field_name="artifact_reference.format",
    )
    normalized["artifact_scope"] = _normalize_optional_artifact_scope(
        normalized.get("artifact_scope"),
        field_name="artifact_reference.artifact_scope",
    )
    normalized["status"] = _normalize_asset_status(
        normalized.get("status", ASSET_STATUS_READY),
        field_name="artifact_reference.status",
    )
    return normalized


def parse_whole_brain_context_node_record(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("whole-brain context node records must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "root_id",
        "node_role_id",
        "context_layer_id",
        "overlay_ids",
        "metadata_facet_values",
        "display_label",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"whole-brain context node record is missing fields: {missing_fields!r}."
        )
    normalized["root_id"] = _normalize_identifier(
        normalized["root_id"],
        field_name="node_record.root_id",
    )
    normalized["node_role_id"] = _normalize_node_role_id(normalized["node_role_id"])
    normalized["context_layer_id"] = _normalize_context_layer_id(
        normalized["context_layer_id"]
    )
    normalized["overlay_ids"] = _normalize_known_value_list(
        normalized["overlay_ids"],
        field_name="node_record.overlay_ids",
        supported_values=SUPPORTED_OVERLAY_IDS,
        allow_empty=True,
    )
    normalized["metadata_facet_values"] = _normalize_metadata_facet_values(
        normalized["metadata_facet_values"],
        field_name="node_record.metadata_facet_values",
    )
    normalized["display_label"] = _normalize_optional_string(
        normalized["display_label"],
        field_name="node_record.display_label",
    )
    return normalized


def parse_whole_brain_context_edge_record(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("whole-brain context edge records must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "source_root_id",
        "target_root_id",
        "edge_role_id",
        "overlay_ids",
        "weight",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"whole-brain context edge record is missing fields: {missing_fields!r}."
        )
    normalized["source_root_id"] = _normalize_identifier(
        normalized["source_root_id"],
        field_name="edge_record.source_root_id",
    )
    normalized["target_root_id"] = _normalize_identifier(
        normalized["target_root_id"],
        field_name="edge_record.target_root_id",
    )
    normalized["edge_role_id"] = _normalize_edge_role_id(normalized["edge_role_id"])
    normalized["overlay_ids"] = _normalize_known_value_list(
        normalized["overlay_ids"],
        field_name="edge_record.overlay_ids",
        supported_values=SUPPORTED_OVERLAY_IDS,
        allow_empty=True,
    )
    normalized["weight"] = _normalize_optional_float(
        normalized["weight"],
        field_name="edge_record.weight",
    )
    return normalized


def parse_whole_brain_context_downstream_module_record(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("whole-brain context downstream-module records must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "module_id",
        "downstream_module_role_id",
        "display_name",
        "description",
        "represented_root_ids",
        "overlay_ids",
        "metadata_facet_values",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "whole-brain context downstream-module record is missing fields: "
            f"{missing_fields!r}."
        )
    normalized["module_id"] = _normalize_identifier(
        normalized["module_id"],
        field_name="downstream_module_record.module_id",
    )
    normalized["downstream_module_role_id"] = _normalize_downstream_module_role_id(
        normalized["downstream_module_role_id"]
    )
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="downstream_module_record.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="downstream_module_record.description",
    )
    normalized["represented_root_ids"] = _normalize_identifier_list(
        normalized["represented_root_ids"],
        field_name="downstream_module_record.represented_root_ids",
        allow_empty=False,
    )
    normalized["overlay_ids"] = _normalize_known_value_list(
        normalized["overlay_ids"],
        field_name="downstream_module_record.overlay_ids",
        supported_values=SUPPORTED_OVERLAY_IDS,
        allow_empty=True,
    )
    normalized["metadata_facet_values"] = _normalize_metadata_facet_values(
        normalized["metadata_facet_values"],
        field_name="downstream_module_record.metadata_facet_values",
    )
    return normalized


def parse_whole_brain_context_contract_metadata(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("whole-brain context contract metadata must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "design_note",
        "design_note_version",
        "default_delivery_model",
        "supported_delivery_models",
        "required_upstream_contracts",
        "supported_query_families",
        "supported_query_profile_ids",
        "supported_node_boundary_statuses",
        "supported_node_role_ids",
        "supported_edge_direction_families",
        "supported_edge_role_ids",
        "supported_layer_kinds",
        "supported_context_layer_ids",
        "supported_overlay_categories",
        "supported_overlay_ids",
        "supported_reduction_profile_ids",
        "supported_metadata_facet_scopes",
        "supported_metadata_facet_ids",
        "supported_downstream_module_role_ids",
        "supported_artifact_source_kinds",
        "supported_artifact_scopes",
        "supported_artifact_role_ids",
        "supported_discovery_hook_ids",
        "default_query_profile_id",
        "default_overlay_id",
        "default_reduction_profile_id",
        "active_boundary_invariants",
        "truthfulness_invariants",
        "query_profile_catalog",
        "node_role_catalog",
        "edge_role_catalog",
        "context_layer_catalog",
        "overlay_catalog",
        "reduction_profile_catalog",
        "metadata_facet_catalog",
        "downstream_module_role_catalog",
        "artifact_hook_catalog",
        "discovery_hook_catalog",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "whole-brain context contract metadata is missing required fields: "
            f"{missing_fields!r}."
        )
    normalized["contract_version"] = _normalize_nonempty_string(
        normalized["contract_version"],
        field_name="contract_version",
    )
    normalized["design_note"] = _normalize_nonempty_string(
        normalized["design_note"],
        field_name="design_note",
    )
    normalized["design_note_version"] = _normalize_nonempty_string(
        normalized["design_note_version"],
        field_name="design_note_version",
    )
    normalized["default_delivery_model"] = _normalize_delivery_model(
        normalized["default_delivery_model"]
    )
    normalized["supported_delivery_models"] = _normalize_known_value_list(
        normalized["supported_delivery_models"],
        field_name="supported_delivery_models",
        supported_values=SUPPORTED_DELIVERY_MODELS,
        allow_empty=False,
    )
    normalized["required_upstream_contracts"] = _normalize_nonempty_string_list(
        normalized["required_upstream_contracts"],
        field_name="required_upstream_contracts",
    )
    normalized["active_boundary_invariants"] = _normalize_nonempty_string_list(
        normalized["active_boundary_invariants"],
        field_name="active_boundary_invariants",
    )
    normalized["truthfulness_invariants"] = _normalize_nonempty_string_list(
        normalized["truthfulness_invariants"],
        field_name="truthfulness_invariants",
    )
    normalized["query_profile_catalog"] = _normalize_definition_catalog(
        normalized["query_profile_catalog"],
        field_name="query_profile_catalog",
        parser=parse_whole_brain_context_query_profile_definition,
        key_name="query_profile_id",
        expected_ids=set(SUPPORTED_QUERY_PROFILE_IDS),
        order_map=_QUERY_PROFILE_ORDER,
    )
    normalized["node_role_catalog"] = _normalize_definition_catalog(
        normalized["node_role_catalog"],
        field_name="node_role_catalog",
        parser=parse_whole_brain_context_node_role_definition,
        key_name="node_role_id",
        expected_ids=set(SUPPORTED_NODE_ROLE_IDS),
        order_map=_NODE_ROLE_ORDER,
    )
    normalized["edge_role_catalog"] = _normalize_definition_catalog(
        normalized["edge_role_catalog"],
        field_name="edge_role_catalog",
        parser=parse_whole_brain_context_edge_role_definition,
        key_name="edge_role_id",
        expected_ids=set(SUPPORTED_EDGE_ROLE_IDS),
        order_map=_EDGE_ROLE_ORDER,
    )
    normalized["context_layer_catalog"] = _normalize_definition_catalog(
        normalized["context_layer_catalog"],
        field_name="context_layer_catalog",
        parser=parse_whole_brain_context_layer_definition,
        key_name="context_layer_id",
        expected_ids=set(SUPPORTED_CONTEXT_LAYER_IDS),
        order_map=_CONTEXT_LAYER_ORDER,
    )
    normalized["overlay_catalog"] = _normalize_definition_catalog(
        normalized["overlay_catalog"],
        field_name="overlay_catalog",
        parser=parse_whole_brain_context_overlay_definition,
        key_name="overlay_id",
        expected_ids=set(SUPPORTED_OVERLAY_IDS),
        order_map=_OVERLAY_ID_ORDER,
    )
    normalized["reduction_profile_catalog"] = _normalize_definition_catalog(
        normalized["reduction_profile_catalog"],
        field_name="reduction_profile_catalog",
        parser=parse_whole_brain_context_reduction_profile_definition,
        key_name="reduction_profile_id",
        expected_ids=set(SUPPORTED_REDUCTION_PROFILE_IDS),
        order_map=_REDUCTION_PROFILE_ORDER,
    )
    normalized["metadata_facet_catalog"] = _normalize_definition_catalog(
        normalized["metadata_facet_catalog"],
        field_name="metadata_facet_catalog",
        parser=parse_whole_brain_context_metadata_facet_definition,
        key_name="metadata_facet_id",
        expected_ids=set(SUPPORTED_METADATA_FACET_IDS),
        order_map=_METADATA_FACET_ORDER,
    )
    normalized["downstream_module_role_catalog"] = _normalize_definition_catalog(
        normalized["downstream_module_role_catalog"],
        field_name="downstream_module_role_catalog",
        parser=parse_whole_brain_context_downstream_module_role_definition,
        key_name="downstream_module_role_id",
        expected_ids=set(SUPPORTED_DOWNSTREAM_MODULE_ROLE_IDS),
        order_map=_DOWNSTREAM_MODULE_ROLE_ORDER,
    )
    normalized["artifact_hook_catalog"] = _normalize_definition_catalog(
        normalized["artifact_hook_catalog"],
        field_name="artifact_hook_catalog",
        parser=parse_whole_brain_context_artifact_hook_definition,
        key_name="artifact_role_id",
        expected_ids=set(SUPPORTED_ARTIFACT_ROLE_IDS),
        order_map=_ARTIFACT_ROLE_ORDER,
    )
    normalized["discovery_hook_catalog"] = _normalize_definition_catalog(
        normalized["discovery_hook_catalog"],
        field_name="discovery_hook_catalog",
        parser=parse_whole_brain_context_discovery_hook_definition,
        key_name="hook_id",
        expected_ids=set(SUPPORTED_DISCOVERY_HOOK_IDS),
        order_map=_DISCOVERY_HOOK_ORDER,
    )
    normalized["default_query_profile_id"] = _normalize_query_profile_id(
        normalized["default_query_profile_id"]
    )
    normalized["default_overlay_id"] = _normalize_overlay_id(
        normalized["default_overlay_id"]
    )
    normalized["default_reduction_profile_id"] = _normalize_reduction_profile_id(
        normalized["default_reduction_profile_id"]
    )
    return normalized


def parse_whole_brain_context_session_metadata(
    payload: Mapping[str, Any],
    *,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("whole-brain context session metadata must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "design_note",
        "design_note_version",
        "bundle_id",
        "experiment_id",
        "context_spec_hash",
        "context_spec_hash_algorithm",
        "delivery_model",
        "query_state",
        "artifact_references",
        "representative_context",
        "output_root_reference",
        "bundle_layout",
        "artifacts",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "whole-brain context session metadata is missing required fields: "
            f"{missing_fields!r}."
        )
    contract = parse_whole_brain_context_contract_metadata(
        contract_metadata
        if contract_metadata is not None
        else build_whole_brain_context_contract_metadata()
    )
    normalized["contract_version"] = _normalize_nonempty_string(
        normalized["contract_version"],
        field_name="contract_version",
    )
    normalized["design_note"] = _normalize_nonempty_string(
        normalized["design_note"],
        field_name="design_note",
    )
    normalized["design_note_version"] = _normalize_nonempty_string(
        normalized["design_note_version"],
        field_name="design_note_version",
    )
    normalized["bundle_id"] = _normalize_nonempty_string(
        normalized["bundle_id"],
        field_name="bundle_id",
    )
    normalized["experiment_id"] = _normalize_identifier(
        normalized["experiment_id"],
        field_name="experiment_id",
    )
    normalized["context_spec_hash"] = _normalize_hex_hash(
        normalized["context_spec_hash"],
        field_name="context_spec_hash",
    )
    normalized["context_spec_hash_algorithm"] = _normalize_nonempty_string(
        normalized["context_spec_hash_algorithm"],
        field_name="context_spec_hash_algorithm",
    )
    normalized["delivery_model"] = _normalize_delivery_model(normalized["delivery_model"])
    normalized["query_state"] = parse_whole_brain_context_query_state(
        normalized["query_state"],
        contract_metadata=contract,
    )
    normalized["artifact_references"] = _normalize_artifact_reference_catalog(
        normalized["artifact_references"],
        field_name="artifact_references",
    )
    normalized["representative_context"] = _normalize_representative_context(
        normalized["representative_context"],
        field_name="representative_context",
    )
    normalized["output_root_reference"] = _normalize_output_root_reference(
        normalized["output_root_reference"]
    )
    normalized["bundle_layout"] = _normalize_bundle_layout(normalized["bundle_layout"])
    normalized["artifacts"] = _normalize_artifacts_mapping(normalized["artifacts"])
    _validate_artifact_references_against_contract(
        normalized["artifact_references"],
        contract_metadata=contract,
        field_name="artifact_references",
    )
    _validate_representative_context_against_contract(
        normalized["representative_context"],
        contract_metadata=contract,
        query_state=normalized["query_state"],
        field_name="representative_context",
    )
    return normalized


def write_whole_brain_context_contract_metadata(
    contract_metadata: Mapping[str, Any],
    metadata_path: str | Path,
) -> Path:
    normalized = parse_whole_brain_context_contract_metadata(contract_metadata)
    return write_json(normalized, metadata_path)


def load_whole_brain_context_contract_metadata(
    metadata_path: str | Path,
) -> dict[str, Any]:
    path = Path(metadata_path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_whole_brain_context_contract_metadata(payload)


def write_whole_brain_context_session_metadata(
    bundle_metadata: Mapping[str, Any],
    metadata_path: str | Path | None = None,
) -> Path:
    normalized = parse_whole_brain_context_session_metadata(bundle_metadata)
    output_path = (
        Path(str(normalized["artifacts"][METADATA_JSON_KEY]["path"])).resolve()
        if metadata_path is None
        else Path(metadata_path)
    )
    return write_json(normalized, output_path)


def load_whole_brain_context_session_metadata(
    metadata_path: str | Path,
) -> dict[str, Any]:
    path = Path(metadata_path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_whole_brain_context_session_metadata(payload)


def discover_whole_brain_context_query_profiles(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    metadata = parse_whole_brain_context_contract_metadata(
        _extract_whole_brain_context_contract_mapping(record)
    )
    return [copy.deepcopy(item) for item in metadata["query_profile_catalog"]]


def discover_whole_brain_context_node_roles(
    record: Mapping[str, Any],
    *,
    selection_boundary_status: str | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_whole_brain_context_contract_metadata(
        _extract_whole_brain_context_contract_mapping(record)
    )
    discovered: list[dict[str, Any]] = []
    normalized_status = (
        None
        if selection_boundary_status is None
        else _normalize_node_boundary_status(selection_boundary_status)
    )
    for item in metadata["node_role_catalog"]:
        if normalized_status is not None and item["selection_boundary_status"] != normalized_status:
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def discover_whole_brain_context_overlays(
    record: Mapping[str, Any],
    *,
    overlay_category: str | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_whole_brain_context_contract_metadata(
        _extract_whole_brain_context_contract_mapping(record)
    )
    discovered: list[dict[str, Any]] = []
    normalized_category = (
        None if overlay_category is None else _normalize_overlay_category(overlay_category)
    )
    for item in metadata["overlay_catalog"]:
        if normalized_category is not None and item["overlay_category"] != normalized_category:
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def discover_whole_brain_context_metadata_facets(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    metadata = parse_whole_brain_context_contract_metadata(
        _extract_whole_brain_context_contract_mapping(record)
    )
    return [copy.deepcopy(item) for item in metadata["metadata_facet_catalog"]]


def discover_whole_brain_context_session_bundle_paths(
    record: Mapping[str, Any],
) -> dict[str, Path]:
    metadata = parse_whole_brain_context_session_metadata(
        _extract_whole_brain_context_session_mapping(record)
    )
    return {
        artifact_id: Path(str(artifact["path"])).resolve()
        for artifact_id, artifact in metadata["artifacts"].items()
    }


def discover_whole_brain_context_session_artifact_references(
    record: Mapping[str, Any],
    *,
    source_kind: str | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_whole_brain_context_session_metadata(
        _extract_whole_brain_context_session_mapping(record)
    )
    normalized_source_kind = (
        None if source_kind is None else _normalize_artifact_source_kind(source_kind)
    )
    discovered: list[dict[str, Any]] = []
    for item in metadata["artifact_references"]:
        if normalized_source_kind is not None and item["source_kind"] != normalized_source_kind:
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def get_whole_brain_context_query_profile_definition(
    query_profile_id: str,
    *,
    record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_query_profile_id = _normalize_query_profile_id(query_profile_id)
    metadata = (
        build_whole_brain_context_contract_metadata()
        if record is None
        else parse_whole_brain_context_contract_metadata(
            _extract_whole_brain_context_contract_mapping(record)
        )
    )
    for item in metadata["query_profile_catalog"]:
        if item["query_profile_id"] == normalized_query_profile_id:
            return copy.deepcopy(item)
    raise ValueError(f"Unknown whole-brain context query_profile_id {normalized_query_profile_id!r}.")


def get_whole_brain_context_node_role_definition(
    node_role_id: str,
    *,
    record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_node_role_id = _normalize_node_role_id(node_role_id)
    metadata = (
        build_whole_brain_context_contract_metadata()
        if record is None
        else parse_whole_brain_context_contract_metadata(
            _extract_whole_brain_context_contract_mapping(record)
        )
    )
    for item in metadata["node_role_catalog"]:
        if item["node_role_id"] == normalized_node_role_id:
            return copy.deepcopy(item)
    raise ValueError(f"Unknown whole-brain context node_role_id {normalized_node_role_id!r}.")


def get_whole_brain_context_overlay_definition(
    overlay_id: str,
    *,
    record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_overlay_id = _normalize_overlay_id(overlay_id)
    metadata = (
        build_whole_brain_context_contract_metadata()
        if record is None
        else parse_whole_brain_context_contract_metadata(
            _extract_whole_brain_context_contract_mapping(record)
        )
    )
    for item in metadata["overlay_catalog"]:
        if item["overlay_id"] == normalized_overlay_id:
            return copy.deepcopy(item)
    raise ValueError(f"Unknown whole-brain context overlay_id {normalized_overlay_id!r}.")


def _default_active_boundary_invariants() -> tuple[str, ...]:
    return (
        "active_selected and active_pathway_highlight nodes must resolve to roots already present in the active subset-selection artifacts",
        "context_only and context_pathway_highlight nodes must remain outside the active subset even when they are packaged beside active nodes",
        "whole-brain context packaging may collapse or trim context, but it may not silently remove active selected nodes from the delivered context session",
    )


def _default_truthfulness_invariants() -> tuple[str, ...]:
    return (
        "upstream and downstream overlays are deterministic packaging views over local subset and synapse artifacts, not new scientific claims by themselves",
        "pathway_highlight overlays remain interpretive emphasis that requires Grant-owned scientific curation rather than automatic rank-based truth claims",
        "downstream modules are explicit summary objects and may not be mislabeled as one-to-one neuron records or fair simulator readouts",
        "dashboard_session.v1 and showcase_session.v1 stay bridge inputs for interaction and narrative context and are not rewritten by Milestone 17 packaging",
    )


def _default_query_profile_catalog() -> list[dict[str, Any]]:
    return [
        build_whole_brain_context_query_profile_definition(
            query_profile_id=ACTIVE_SUBSET_SHELL_QUERY_PROFILE_ID,
            display_name="Active Subset Shell",
            description="Show the active visual subset with only the minimal boundary shell required to situate it in the larger brain.",
            query_family=LOCAL_SHELL_QUERY_FAMILY,
            default_context_layer_ids=[ACTIVE_SUBSET_CONTEXT_LAYER_ID],
            supported_overlay_ids=[
                ACTIVE_BOUNDARY_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            default_overlay_id=ACTIVE_BOUNDARY_OVERLAY_ID,
            default_reduction_profile_id=LOCAL_SHELL_COMPACT_REDUCTION_PROFILE_ID,
            required_artifact_role_ids=[
                SELECTED_ROOT_IDS_ROLE_ID,
                SUBSET_MANIFEST_ROLE_ID,
                SUBSET_STATS_ROLE_ID,
            ],
            scientific_curation_required=False,
            truthfulness_note="This profile shows where the active subset sits; it does not claim anything about omitted context beyond the contracted budget boundary.",
        ),
        build_whole_brain_context_query_profile_definition(
            query_profile_id=UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
            display_name="Upstream Connectivity Context",
            description="Expose incoming whole-brain context around the active subset without widening the active simulator surface.",
            query_family=UPSTREAM_CONTEXT_QUERY_FAMILY,
            default_context_layer_ids=[
                ACTIVE_SUBSET_CONTEXT_LAYER_ID,
                UPSTREAM_CONTEXT_LAYER_ID,
            ],
            supported_overlay_ids=[
                ACTIVE_BOUNDARY_OVERLAY_ID,
                UPSTREAM_GRAPH_OVERLAY_ID,
                PATHWAY_HIGHLIGHT_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            default_overlay_id=UPSTREAM_GRAPH_OVERLAY_ID,
            default_reduction_profile_id=BALANCED_NEIGHBORHOOD_REDUCTION_PROFILE_ID,
            required_artifact_role_ids=[
                SELECTED_ROOT_IDS_ROLE_ID,
                SUBSET_MANIFEST_ROLE_ID,
                SYNAPSE_REGISTRY_ROLE_ID,
            ],
            scientific_curation_required=False,
            truthfulness_note="Incoming context is chosen deterministically from local connectivity inputs and should remain labeled as context rather than active simulation state.",
        ),
        build_whole_brain_context_query_profile_definition(
            query_profile_id=DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
            display_name="Downstream Connectivity Context",
            description="Expose outgoing context and optional downstream summaries that help orient interpretation beyond the active subset.",
            query_family=DOWNSTREAM_CONTEXT_QUERY_FAMILY,
            default_context_layer_ids=[
                ACTIVE_SUBSET_CONTEXT_LAYER_ID,
                DOWNSTREAM_CONTEXT_LAYER_ID,
                DOWNSTREAM_MODULE_CONTEXT_LAYER_ID,
            ],
            supported_overlay_ids=[
                ACTIVE_BOUNDARY_OVERLAY_ID,
                DOWNSTREAM_GRAPH_OVERLAY_ID,
                DOWNSTREAM_MODULE_OVERLAY_ID,
                PATHWAY_HIGHLIGHT_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            default_overlay_id=DOWNSTREAM_GRAPH_OVERLAY_ID,
            default_reduction_profile_id=DOWNSTREAM_MODULE_COLLAPSED_REDUCTION_PROFILE_ID,
            required_artifact_role_ids=[
                SELECTED_ROOT_IDS_ROLE_ID,
                SUBSET_MANIFEST_ROLE_ID,
                SYNAPSE_REGISTRY_ROLE_ID,
            ],
            scientific_curation_required=False,
            truthfulness_note="Outgoing context may introduce collapsed downstream modules, but those summaries stay explicitly separate from neuron-level active state.",
        ),
        build_whole_brain_context_query_profile_definition(
            query_profile_id=BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
            display_name="Bidirectional Connectivity Context",
            description="Default Milestone 17 profile that packages both upstream and downstream context around the active visual subset.",
            query_family=BIDIRECTIONAL_CONTEXT_QUERY_FAMILY,
            default_context_layer_ids=[
                ACTIVE_SUBSET_CONTEXT_LAYER_ID,
                UPSTREAM_CONTEXT_LAYER_ID,
                DOWNSTREAM_CONTEXT_LAYER_ID,
                DOWNSTREAM_MODULE_CONTEXT_LAYER_ID,
            ],
            supported_overlay_ids=list(SUPPORTED_OVERLAY_IDS),
            default_overlay_id=ACTIVE_BOUNDARY_OVERLAY_ID,
            default_reduction_profile_id=DEFAULT_REDUCTION_PROFILE_ID,
            required_artifact_role_ids=[
                SELECTED_ROOT_IDS_ROLE_ID,
                SUBSET_MANIFEST_ROLE_ID,
                SYNAPSE_REGISTRY_ROLE_ID,
                DASHBOARD_SESSION_METADATA_ROLE_ID,
            ],
            scientific_curation_required=False,
            truthfulness_note="The default profile is packaging-first: it fixes vocabulary and deterministic budgets before it attempts to settle which whole-brain pathways matter scientifically.",
        ),
        build_whole_brain_context_query_profile_definition(
            query_profile_id=PATHWAY_HIGHLIGHT_REVIEW_QUERY_PROFILE_ID,
            display_name="Pathway Highlight Review",
            description="Curated context profile for reviewer-facing pathway emphasis on top of the deterministic active-versus-context split.",
            query_family=PATHWAY_REVIEW_QUERY_FAMILY,
            default_context_layer_ids=[
                ACTIVE_SUBSET_CONTEXT_LAYER_ID,
                PATHWAY_HIGHLIGHT_CONTEXT_LAYER_ID,
            ],
            supported_overlay_ids=[
                ACTIVE_BOUNDARY_OVERLAY_ID,
                PATHWAY_HIGHLIGHT_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            default_overlay_id=PATHWAY_HIGHLIGHT_OVERLAY_ID,
            default_reduction_profile_id=PATHWAY_FOCUS_REDUCTION_PROFILE_ID,
            required_artifact_role_ids=[
                SELECTED_ROOT_IDS_ROLE_ID,
                SYNAPSE_REGISTRY_ROLE_ID,
                SHOWCASE_SESSION_METADATA_ROLE_ID,
            ],
            scientific_curation_required=True,
            truthfulness_note="Pathway highlight views are downstream interpretation aids. They should remain visibly distinct from fair active-versus-context packaging and require scientific approval.",
        ),
        build_whole_brain_context_query_profile_definition(
            query_profile_id=DOWNSTREAM_MODULE_REVIEW_QUERY_PROFILE_ID,
            display_name="Downstream Module Review",
            description="Curated profile for optional simplified downstream readout modules attached to the active subset context.",
            query_family=DOWNSTREAM_MODULE_REVIEW_QUERY_FAMILY,
            default_context_layer_ids=[
                ACTIVE_SUBSET_CONTEXT_LAYER_ID,
                DOWNSTREAM_CONTEXT_LAYER_ID,
                DOWNSTREAM_MODULE_CONTEXT_LAYER_ID,
            ],
            supported_overlay_ids=[
                ACTIVE_BOUNDARY_OVERLAY_ID,
                DOWNSTREAM_GRAPH_OVERLAY_ID,
                DOWNSTREAM_MODULE_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            default_overlay_id=DOWNSTREAM_MODULE_OVERLAY_ID,
            default_reduction_profile_id=DOWNSTREAM_MODULE_COLLAPSED_REDUCTION_PROFILE_ID,
            required_artifact_role_ids=[
                SELECTED_ROOT_IDS_ROLE_ID,
                SYNAPSE_REGISTRY_ROLE_ID,
                SHOWCASE_SESSION_METADATA_ROLE_ID,
            ],
            scientific_curation_required=True,
            truthfulness_note="Downstream-module review is an optional simplification layer. Module objects remain summaries of broader pathways, not new scientific endpoints by default.",
        ),
    ]


def _default_node_role_catalog() -> list[dict[str, Any]]:
    return [
        build_whole_brain_context_node_role_definition(
            node_role_id=ACTIVE_SELECTED_NODE_ROLE_ID,
            display_name="Active Selected",
            description="A node that belongs to the active selected subset and is treated as part of the active review surface.",
            selection_boundary_status=ACTIVE_BOUNDARY_STATUS,
            supported_context_layer_ids=[ACTIVE_SUBSET_CONTEXT_LAYER_ID],
            counts_as_active_selected=True,
            counts_as_context_only=False,
            truthfulness_note="Active selected nodes inherit membership from subset-selection outputs rather than later UI curation.",
        ),
        build_whole_brain_context_node_role_definition(
            node_role_id=CONTEXT_ONLY_NODE_ROLE_ID,
            display_name="Context Only",
            description="A biological node introduced only to provide larger-brain context around the active subset.",
            selection_boundary_status=CONTEXT_BOUNDARY_STATUS,
            supported_context_layer_ids=[
                UPSTREAM_CONTEXT_LAYER_ID,
                DOWNSTREAM_CONTEXT_LAYER_ID,
            ],
            counts_as_active_selected=False,
            counts_as_context_only=True,
            truthfulness_note="Context-only nodes are explanatory scaffolding and must not be restated as active simulated nodes.",
        ),
        build_whole_brain_context_node_role_definition(
            node_role_id=ACTIVE_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
            display_name="Active Pathway Highlight",
            description="An active selected node that is also intentionally highlighted inside a curated pathway overlay.",
            selection_boundary_status=ACTIVE_BOUNDARY_STATUS,
            supported_context_layer_ids=[
                ACTIVE_SUBSET_CONTEXT_LAYER_ID,
                PATHWAY_HIGHLIGHT_CONTEXT_LAYER_ID,
            ],
            counts_as_active_selected=True,
            counts_as_context_only=False,
            truthfulness_note="Pathway highlight never overrides active membership.",
        ),
        build_whole_brain_context_node_role_definition(
            node_role_id=CONTEXT_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
            display_name="Context Pathway Highlight",
            description="A context-only node that is intentionally highlighted as part of a curated broader pathway.",
            selection_boundary_status=CONTEXT_BOUNDARY_STATUS,
            supported_context_layer_ids=[
                UPSTREAM_CONTEXT_LAYER_ID,
                DOWNSTREAM_CONTEXT_LAYER_ID,
                PATHWAY_HIGHLIGHT_CONTEXT_LAYER_ID,
            ],
            counts_as_active_selected=False,
            counts_as_context_only=True,
            truthfulness_note="A highlighted context node stays context.",
        ),
    ]


def _default_edge_role_catalog() -> list[dict[str, Any]]:
    return [
        build_whole_brain_context_edge_role_definition(
            edge_role_id=ACTIVE_INTERNAL_EDGE_ROLE_ID,
            display_name="Active Internal",
            description="Connectivity edge with both endpoints inside the active selected subset.",
            direction_family=INTERNAL_EDGE_DIRECTION_FAMILY,
            allowed_source_node_role_ids=[
                ACTIVE_SELECTED_NODE_ROLE_ID,
                ACTIVE_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
            ],
            allowed_target_node_role_ids=[
                ACTIVE_SELECTED_NODE_ROLE_ID,
                ACTIVE_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
            ],
            truthfulness_note="Active-internal edges preserve the existing active-subset boundary.",
        ),
        build_whole_brain_context_edge_role_definition(
            edge_role_id=ACTIVE_TO_CONTEXT_EDGE_ROLE_ID,
            display_name="Active To Context",
            description="Outgoing edge from an active selected node toward broader context.",
            direction_family=DOWNSTREAM_EDGE_DIRECTION_FAMILY,
            allowed_source_node_role_ids=[
                ACTIVE_SELECTED_NODE_ROLE_ID,
                ACTIVE_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
            ],
            allowed_target_node_role_ids=[
                CONTEXT_ONLY_NODE_ROLE_ID,
                CONTEXT_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
            ],
            truthfulness_note="This edge expresses context packaging beyond the active subset.",
        ),
        build_whole_brain_context_edge_role_definition(
            edge_role_id=CONTEXT_TO_ACTIVE_EDGE_ROLE_ID,
            display_name="Context To Active",
            description="Incoming edge from broader context into an active selected node.",
            direction_family=UPSTREAM_EDGE_DIRECTION_FAMILY,
            allowed_source_node_role_ids=[
                CONTEXT_ONLY_NODE_ROLE_ID,
                CONTEXT_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
            ],
            allowed_target_node_role_ids=[
                ACTIVE_SELECTED_NODE_ROLE_ID,
                ACTIVE_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
            ],
            truthfulness_note="This edge marks upstream context around the active subset without relabeling the upstream source as active.",
        ),
        build_whole_brain_context_edge_role_definition(
            edge_role_id=CONTEXT_INTERNAL_EDGE_ROLE_ID,
            display_name="Context Internal",
            description="Edge wholly inside packaged context outside the active subset.",
            direction_family=INTERNAL_EDGE_DIRECTION_FAMILY,
            allowed_source_node_role_ids=[
                CONTEXT_ONLY_NODE_ROLE_ID,
                CONTEXT_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
            ],
            allowed_target_node_role_ids=[
                CONTEXT_ONLY_NODE_ROLE_ID,
                CONTEXT_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
            ],
            truthfulness_note="Context-internal edges help orient the packaged whole-brain neighborhood.",
        ),
        build_whole_brain_context_edge_role_definition(
            edge_role_id=PATHWAY_HIGHLIGHT_EDGE_ROLE_ID,
            display_name="Pathway Highlight",
            description="Curated pathway edge intentionally emphasized for interpretation across active and context nodes.",
            direction_family=SUMMARY_EDGE_DIRECTION_FAMILY,
            allowed_source_node_role_ids=list(SUPPORTED_NODE_ROLE_IDS),
            allowed_target_node_role_ids=list(SUPPORTED_NODE_ROLE_IDS),
            truthfulness_note="A pathway-highlight edge is a labeled interpretation layer.",
        ),
        build_whole_brain_context_edge_role_definition(
            edge_role_id=DOWNSTREAM_MODULE_SUMMARY_EDGE_ROLE_ID,
            display_name="Downstream Module Summary",
            description="Collapsed summary edge from biological roots into an optional downstream module record.",
            direction_family=SUMMARY_EDGE_DIRECTION_FAMILY,
            allowed_source_node_role_ids=list(SUPPORTED_NODE_ROLE_IDS),
            allowed_target_node_role_ids=[],
            truthfulness_note="Summary edges leading to downstream modules are reduced representations.",
        ),
    ]


def _default_context_layer_catalog() -> list[dict[str, Any]]:
    return [
        build_whole_brain_context_layer_definition(
            context_layer_id=ACTIVE_SUBSET_CONTEXT_LAYER_ID,
            display_name="Active Subset",
            description="The active selected visual subset inherited from subset selection and earlier milestone packages.",
            sequence_index=0,
            layer_kind=ACTIVE_LAYER_KIND,
            default_visible=True,
            supported_node_role_ids=[
                ACTIVE_SELECTED_NODE_ROLE_ID,
                ACTIVE_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
            ],
        ),
        build_whole_brain_context_layer_definition(
            context_layer_id=UPSTREAM_CONTEXT_LAYER_ID,
            display_name="Upstream Context",
            description="Context-only nodes or highlighted context nodes that feed into the active subset.",
            sequence_index=1,
            layer_kind=CONTEXT_LAYER_KIND,
            default_visible=True,
            supported_node_role_ids=[
                CONTEXT_ONLY_NODE_ROLE_ID,
                CONTEXT_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
            ],
        ),
        build_whole_brain_context_layer_definition(
            context_layer_id=DOWNSTREAM_CONTEXT_LAYER_ID,
            display_name="Downstream Context",
            description="Context-only nodes or highlighted context nodes reached from the active subset.",
            sequence_index=2,
            layer_kind=CONTEXT_LAYER_KIND,
            default_visible=True,
            supported_node_role_ids=[
                CONTEXT_ONLY_NODE_ROLE_ID,
                CONTEXT_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
            ],
        ),
        build_whole_brain_context_layer_definition(
            context_layer_id=PATHWAY_HIGHLIGHT_CONTEXT_LAYER_ID,
            display_name="Pathway Highlight",
            description="Curated emphasis layer for pathway-relevant active and context nodes.",
            sequence_index=3,
            layer_kind=HIGHLIGHT_LAYER_KIND,
            default_visible=False,
            supported_node_role_ids=[
                ACTIVE_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
                CONTEXT_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
            ],
        ),
        build_whole_brain_context_layer_definition(
            context_layer_id=DOWNSTREAM_MODULE_CONTEXT_LAYER_ID,
            display_name="Downstream Module",
            description="Optional simplified downstream-module summaries that sit outside one-to-one neuron identity.",
            sequence_index=4,
            layer_kind=MODULE_LAYER_KIND,
            default_visible=False,
            supported_node_role_ids=[],
        ),
    ]


def _default_overlay_catalog() -> list[dict[str, Any]]:
    return [
        build_whole_brain_context_overlay_definition(
            overlay_id=ACTIVE_BOUNDARY_OVERLAY_ID,
            display_name="Active Boundary",
            description="Makes the active-versus-context split explicit in every query profile.",
            overlay_category=BOUNDARY_OVERLAY_CATEGORY,
            supported_query_profile_ids=list(SUPPORTED_QUERY_PROFILE_IDS),
            supported_context_layer_ids=[
                ACTIVE_SUBSET_CONTEXT_LAYER_ID,
                UPSTREAM_CONTEXT_LAYER_ID,
                DOWNSTREAM_CONTEXT_LAYER_ID,
                PATHWAY_HIGHLIGHT_CONTEXT_LAYER_ID,
            ],
            required_node_role_ids=list(SUPPORTED_NODE_ROLE_IDS),
            required_edge_role_ids=[
                ACTIVE_INTERNAL_EDGE_ROLE_ID,
                ACTIVE_TO_CONTEXT_EDGE_ROLE_ID,
                CONTEXT_TO_ACTIVE_EDGE_ROLE_ID,
                CONTEXT_INTERNAL_EDGE_ROLE_ID,
            ],
            fairness_note="This is the core truthfulness boundary: active subset membership comes from subset selection, and every other node stays visibly contextual.",
        ),
        build_whole_brain_context_overlay_definition(
            overlay_id=UPSTREAM_GRAPH_OVERLAY_ID,
            display_name="Upstream Graph",
            description="Highlights incoming graph context around the active visual subset.",
            overlay_category=DIRECTIONAL_CONTEXT_OVERLAY_CATEGORY,
            supported_query_profile_ids=[
                UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                PATHWAY_HIGHLIGHT_REVIEW_QUERY_PROFILE_ID,
            ],
            supported_context_layer_ids=[
                ACTIVE_SUBSET_CONTEXT_LAYER_ID,
                UPSTREAM_CONTEXT_LAYER_ID,
                PATHWAY_HIGHLIGHT_CONTEXT_LAYER_ID,
            ],
            required_node_role_ids=list(SUPPORTED_NODE_ROLE_IDS),
            required_edge_role_ids=[
                CONTEXT_TO_ACTIVE_EDGE_ROLE_ID,
                CONTEXT_INTERNAL_EDGE_ROLE_ID,
                PATHWAY_HIGHLIGHT_EDGE_ROLE_ID,
            ],
            fairness_note="Incoming graph context is packaged as directional context, not as a claim that all upstream nodes are equally relevant or active.",
        ),
        build_whole_brain_context_overlay_definition(
            overlay_id=DOWNSTREAM_GRAPH_OVERLAY_ID,
            display_name="Downstream Graph",
            description="Highlights outgoing graph context from the active subset into the larger brain.",
            overlay_category=DIRECTIONAL_CONTEXT_OVERLAY_CATEGORY,
            supported_query_profile_ids=[
                DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                DOWNSTREAM_MODULE_REVIEW_QUERY_PROFILE_ID,
            ],
            supported_context_layer_ids=[
                ACTIVE_SUBSET_CONTEXT_LAYER_ID,
                DOWNSTREAM_CONTEXT_LAYER_ID,
                PATHWAY_HIGHLIGHT_CONTEXT_LAYER_ID,
                DOWNSTREAM_MODULE_CONTEXT_LAYER_ID,
            ],
            required_node_role_ids=list(SUPPORTED_NODE_ROLE_IDS),
            required_edge_role_ids=[
                ACTIVE_TO_CONTEXT_EDGE_ROLE_ID,
                CONTEXT_INTERNAL_EDGE_ROLE_ID,
                PATHWAY_HIGHLIGHT_EDGE_ROLE_ID,
                DOWNSTREAM_MODULE_SUMMARY_EDGE_ROLE_ID,
            ],
            fairness_note="Outgoing graph context should show bridges and branches without overstating them as validated downstream pathway claims.",
        ),
        build_whole_brain_context_overlay_definition(
            overlay_id=PATHWAY_HIGHLIGHT_OVERLAY_ID,
            display_name="Pathway Highlight",
            description="Adds curated pathway emphasis on top of the deterministic context package.",
            overlay_category=PATHWAY_HIGHLIGHT_OVERLAY_CATEGORY,
            supported_query_profile_ids=[
                UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                PATHWAY_HIGHLIGHT_REVIEW_QUERY_PROFILE_ID,
            ],
            supported_context_layer_ids=[PATHWAY_HIGHLIGHT_CONTEXT_LAYER_ID],
            required_node_role_ids=[
                ACTIVE_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
                CONTEXT_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
            ],
            required_edge_role_ids=[PATHWAY_HIGHLIGHT_EDGE_ROLE_ID],
            fairness_note="Pathway highlights are explicitly curated and must not replace the active boundary overlay as the fair packaging surface.",
        ),
        build_whole_brain_context_overlay_definition(
            overlay_id=DOWNSTREAM_MODULE_OVERLAY_ID,
            display_name="Downstream Module",
            description="Shows optional simplified downstream-module summaries attached to the active context package.",
            overlay_category=DOWNSTREAM_MODULE_OVERLAY_CATEGORY,
            supported_query_profile_ids=[
                DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                DOWNSTREAM_MODULE_REVIEW_QUERY_PROFILE_ID,
            ],
            supported_context_layer_ids=[DOWNSTREAM_MODULE_CONTEXT_LAYER_ID],
            required_node_role_ids=list(SUPPORTED_NODE_ROLE_IDS),
            required_edge_role_ids=[DOWNSTREAM_MODULE_SUMMARY_EDGE_ROLE_ID],
            fairness_note="Downstream modules are honest simplifications and must stay labeled as aggregated summaries.",
        ),
        build_whole_brain_context_overlay_definition(
            overlay_id=METADATA_FACET_BADGES_OVERLAY_ID,
            display_name="Metadata Facet Badges",
            description="Annotates nodes and downstream modules with compact metadata facets.",
            overlay_category=METADATA_FACET_OVERLAY_CATEGORY,
            supported_query_profile_ids=list(SUPPORTED_QUERY_PROFILE_IDS),
            supported_context_layer_ids=list(SUPPORTED_CONTEXT_LAYER_IDS),
            required_node_role_ids=list(SUPPORTED_NODE_ROLE_IDS),
            required_edge_role_ids=list(SUPPORTED_EDGE_ROLE_IDS),
            fairness_note="Metadata facets explain what is being shown; they do not confer pathway importance or scientific approval by themselves.",
        ),
    ]


def _default_reduction_profile_catalog() -> list[dict[str, Any]]:
    return [
        build_whole_brain_context_reduction_profile_definition(
            reduction_profile_id=LOCAL_SHELL_COMPACT_REDUCTION_PROFILE_ID,
            display_name="Local Shell Compact",
            description="Smallest deterministic budget that keeps the active subset legible inside a whole-brain scaffold.",
            max_context_node_count=96,
            max_edge_count=240,
            max_pathway_highlight_count=16,
            max_downstream_module_count=0,
            preserve_active_subset=True,
        ),
        build_whole_brain_context_reduction_profile_definition(
            reduction_profile_id=BALANCED_NEIGHBORHOOD_REDUCTION_PROFILE_ID,
            display_name="Balanced Neighborhood",
            description="Default Milestone 17 budget that balances upstream and downstream context without turning the package into a full graph export.",
            max_context_node_count=256,
            max_edge_count=768,
            max_pathway_highlight_count=40,
            max_downstream_module_count=6,
            preserve_active_subset=True,
        ),
        build_whole_brain_context_reduction_profile_definition(
            reduction_profile_id=PATHWAY_FOCUS_REDUCTION_PROFILE_ID,
            display_name="Pathway Focus",
            description="Tighter review budget that privileges explicitly highlighted pathway context over wider graph coverage.",
            max_context_node_count=160,
            max_edge_count=360,
            max_pathway_highlight_count=64,
            max_downstream_module_count=4,
            preserve_active_subset=True,
        ),
        build_whole_brain_context_reduction_profile_definition(
            reduction_profile_id=DOWNSTREAM_MODULE_COLLAPSED_REDUCTION_PROFILE_ID,
            display_name="Downstream Module Collapsed",
            description="Budget tuned for optional downstream readout modules where one-to-one neuron context is partially collapsed.",
            max_context_node_count=192,
            max_edge_count=420,
            max_pathway_highlight_count=24,
            max_downstream_module_count=12,
            preserve_active_subset=True,
        ),
    ]


def _default_metadata_facet_catalog() -> list[dict[str, Any]]:
    return [
        build_whole_brain_context_metadata_facet_definition(
            metadata_facet_id=CELL_CLASS_METADATA_FACET_ID,
            display_name="Cell Class",
            description="Broad cell-class label from local registry metadata.",
            facet_scope=BOTH_METADATA_FACET_SCOPE,
            default_enabled=True,
        ),
        build_whole_brain_context_metadata_facet_definition(
            metadata_facet_id=CELL_TYPE_METADATA_FACET_ID,
            display_name="Cell Type",
            description="Narrower resolved cell-type label when the local registry can provide one.",
            facet_scope=NODE_METADATA_FACET_SCOPE,
            default_enabled=True,
        ),
        build_whole_brain_context_metadata_facet_definition(
            metadata_facet_id=NEUROPIL_METADATA_FACET_ID,
            display_name="Neuropil",
            description="Dominant neuropil or neuropil grouping used to orient the context package.",
            facet_scope=BOTH_METADATA_FACET_SCOPE,
            default_enabled=True,
        ),
        build_whole_brain_context_metadata_facet_definition(
            metadata_facet_id=SIDE_METADATA_FACET_ID,
            display_name="Side",
            description="Body side or hemisphere label carried through the packaged context surface.",
            facet_scope=BOTH_METADATA_FACET_SCOPE,
            default_enabled=False,
        ),
        build_whole_brain_context_metadata_facet_definition(
            metadata_facet_id=NT_TYPE_METADATA_FACET_ID,
            display_name="NT Type",
            description="Local neurotransmitter or transmitter-family tag when available.",
            facet_scope=NODE_METADATA_FACET_SCOPE,
            default_enabled=False,
        ),
        build_whole_brain_context_metadata_facet_definition(
            metadata_facet_id=SELECTION_BOUNDARY_STATUS_METADATA_FACET_ID,
            display_name="Selection Boundary Status",
            description="Explicit indicator of whether a node is active selected, context only, or pathway highlighted.",
            facet_scope=NODE_METADATA_FACET_SCOPE,
            default_enabled=True,
        ),
        build_whole_brain_context_metadata_facet_definition(
            metadata_facet_id=PATHWAY_RELEVANCE_STATUS_METADATA_FACET_ID,
            display_name="Pathway Relevance Status",
            description="Explicit label for whether a node or downstream module is merely contextual or intentionally pathway highlighted.",
            facet_scope=BOTH_METADATA_FACET_SCOPE,
            default_enabled=True,
        ),
    ]


def _default_downstream_module_role_catalog() -> list[dict[str, Any]]:
    return [
        build_whole_brain_context_downstream_module_role_definition(
            downstream_module_role_id=SIMPLIFIED_READOUT_MODULE_ROLE_ID,
            display_name="Simplified Readout Module",
            description="Optional collapsed module representing broader downstream readout structure without claiming neuron-level fidelity.",
            default_context_layer_id=DOWNSTREAM_MODULE_CONTEXT_LAYER_ID,
            allows_aggregated_readout=True,
            requires_scientific_curation=True,
            truthfulness_note="A simplified readout module is a summary object intended for orientation.",
        ),
        build_whole_brain_context_downstream_module_role_definition(
            downstream_module_role_id=COLLAPSED_PROJECTION_MODULE_ROLE_ID,
            display_name="Collapsed Projection Module",
            description="Optional compact module that summarizes a wider downstream projection fan-out.",
            default_context_layer_id=DOWNSTREAM_MODULE_CONTEXT_LAYER_ID,
            allows_aggregated_readout=False,
            requires_scientific_curation=True,
            truthfulness_note="Collapsed projection modules explain broader relationships but stay clearly labeled as reduction products.",
        ),
    ]


def _default_artifact_hook_catalog() -> list[dict[str, Any]]:
    return [
        build_whole_brain_context_artifact_hook_definition(
            artifact_role_id=SELECTED_ROOT_IDS_ROLE_ID,
            display_name="Selected Root Ids",
            description="Authoritative active-subset root roster from subset selection.",
            source_kind=SUBSET_SELECTION_SOURCE_KIND,
            required_contract_version=None,
            artifact_id="root_ids",
            artifact_scope=SUBSET_SELECTION_SCOPE,
            discovery_note="Use the subset-selection artifact directory or active-preset output to resolve the active selected root roster.",
        ),
        build_whole_brain_context_artifact_hook_definition(
            artifact_role_id=SUBSET_MANIFEST_ROLE_ID,
            display_name="Subset Manifest",
            description="Deterministic subset-selection manifest that explains how the active subset was formed.",
            source_kind=SUBSET_SELECTION_SOURCE_KIND,
            required_contract_version=None,
            artifact_id="subset_manifest",
            artifact_scope=SUBSET_SELECTION_SCOPE,
            discovery_note="Use the subset-selection artifact directory to discover the resolved selection rules and selected roster.",
        ),
        build_whole_brain_context_artifact_hook_definition(
            artifact_role_id=SUBSET_STATS_ROLE_ID,
            display_name="Subset Stats",
            description="Compact subset-selection statistics used to report active-versus-boundary counts.",
            source_kind=SUBSET_SELECTION_SOURCE_KIND,
            required_contract_version=None,
            artifact_id="subset_stats",
            artifact_scope=SUBSET_SELECTION_SCOPE,
            discovery_note="Use the subset-selection artifact directory to discover graph and boundary summaries for the active subset.",
        ),
        build_whole_brain_context_artifact_hook_definition(
            artifact_role_id=SYNAPSE_REGISTRY_ROLE_ID,
            display_name="Synapse Registry",
            description="Canonical local synapse registry aligned to the active selected roots.",
            source_kind=LOCAL_CONNECTIVITY_SOURCE_KIND,
            required_contract_version=COUPLING_BUNDLE_CONTRACT_VERSION,
            artifact_id=LOCAL_SYNAPSE_REGISTRY_KEY,
            artifact_scope=LOCAL_CONNECTIVITY_SCOPE,
            discovery_note="Resolve through the coupling bundle contract and canonical local synapse registry path.",
        ),
        build_whole_brain_context_artifact_hook_definition(
            artifact_role_id=DASHBOARD_SESSION_METADATA_ROLE_ID,
            display_name="Dashboard Session Metadata",
            description="Packaged dashboard-session metadata used as a UI bridge into whole-brain context views.",
            source_kind=DASHBOARD_SESSION_SOURCE_KIND,
            required_contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            artifact_id="metadata_json",
            artifact_scope=DASHBOARD_CONTEXT_SCOPE,
            discovery_note="Resolve through dashboard_session.v1 metadata rather than by guessing dashboard file names.",
        ),
        build_whole_brain_context_artifact_hook_definition(
            artifact_role_id=DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
            display_name="Dashboard Session Payload",
            description="Packaged dashboard-session payload used for linked interaction and pane-state bridge semantics.",
            source_kind=DASHBOARD_SESSION_SOURCE_KIND,
            required_contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            artifact_id="session_payload",
            artifact_scope=DASHBOARD_CONTEXT_SCOPE,
            discovery_note="Resolve through dashboard_session.v1 artifact references when a whole-brain context view needs the packaged dashboard payload.",
        ),
        build_whole_brain_context_artifact_hook_definition(
            artifact_role_id=DASHBOARD_SESSION_STATE_ROLE_ID,
            display_name="Dashboard Session State",
            description="Serialized dashboard interaction state used to bridge linked replay and selection semantics.",
            source_kind=DASHBOARD_SESSION_SOURCE_KIND,
            required_contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            artifact_id="session_state",
            artifact_scope=DASHBOARD_CONTEXT_SCOPE,
            discovery_note="Resolve through dashboard_session.v1 artifact references when linked replay or exported dashboard state is needed.",
        ),
        build_whole_brain_context_artifact_hook_definition(
            artifact_role_id=SHOWCASE_SESSION_METADATA_ROLE_ID,
            display_name="Showcase Session Metadata",
            description="Packaged showcase-session metadata used as a bridge into narrative whole-brain context views.",
            source_kind=SHOWCASE_SESSION_SOURCE_KIND,
            required_contract_version=SHOWCASE_SESSION_CONTRACT_VERSION,
            artifact_id="metadata_json",
            artifact_scope=SHOWCASE_CONTEXT_SCOPE,
            discovery_note="Resolve through showcase_session.v1 metadata instead of replaying a showcase from ad hoc notes or presets.",
        ),
        build_whole_brain_context_artifact_hook_definition(
            artifact_role_id=SHOWCASE_PRESENTATION_STATE_ROLE_ID,
            display_name="Showcase Presentation State",
            description="Serialized showcase presentation state used to bridge narrative emphasis into context-review packages.",
            source_kind=SHOWCASE_SESSION_SOURCE_KIND,
            required_contract_version=SHOWCASE_SESSION_CONTRACT_VERSION,
            artifact_id="showcase_presentation_state",
            artifact_scope=SHOWCASE_CONTEXT_SCOPE,
            discovery_note="Use showcase_session.v1 presentation-state references when a Milestone 17 view needs scripted context or approved presentation framing.",
        ),
        build_whole_brain_context_artifact_hook_definition(
            artifact_role_id=WHOLE_BRAIN_CONTEXT_SESSION_METADATA_ROLE_ID,
            display_name="Whole-Brain Context Session Metadata",
            description="Authoritative discovery anchor for a packaged whole-brain context session.",
            source_kind=WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND,
            required_contract_version=WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
            artifact_id=METADATA_JSON_KEY,
            artifact_scope=CONTRACT_METADATA_SCOPE,
            discovery_note="Use the whole-brain context session metadata as the canonical discovery anchor for the package.",
        ),
        build_whole_brain_context_artifact_hook_definition(
            artifact_role_id=CONTEXT_VIEW_PAYLOAD_ROLE_ID,
            display_name="Context View Payload",
            description="Reserved packaged whole-brain context view payload for later UI and graph export work.",
            source_kind=WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND,
            required_contract_version=WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
            artifact_id=CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID,
            artifact_scope=CONTEXT_VIEW_SCOPE,
            discovery_note="Resolve through whole_brain_context_session.v1 artifact references rather than creating dashboard-local JSON patches.",
        ),
        build_whole_brain_context_artifact_hook_definition(
            artifact_role_id=CONTEXT_QUERY_CATALOG_ROLE_ID,
            display_name="Context Query Catalog",
            description="Reserved packaged query taxonomy export for deterministic replay and inspection.",
            source_kind=WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND,
            required_contract_version=WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
            artifact_id=CONTEXT_QUERY_CATALOG_ARTIFACT_ID,
            artifact_scope=CONTEXT_QUERY_SCOPE,
            discovery_note="Resolve through whole_brain_context_session.v1 artifact references for query-profile discovery and replay.",
        ),
        build_whole_brain_context_artifact_hook_definition(
            artifact_role_id=CONTEXT_VIEW_STATE_ROLE_ID,
            display_name="Context View State",
            description="Serialized whole-brain context view state for deterministic local replay and review exports.",
            source_kind=WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND,
            required_contract_version=WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
            artifact_id=CONTEXT_VIEW_STATE_ARTIFACT_ID,
            artifact_scope=CONTEXT_STATE_SCOPE,
            discovery_note="Resolve through whole_brain_context_session.v1 artifact references for deterministic saved-state replay.",
        ),
    ]


def _default_discovery_hook_catalog() -> list[dict[str, Any]]:
    return [
        build_whole_brain_context_discovery_hook_definition(
            hook_id=ACTIVE_SUBSET_INPUTS_DISCOVERY_HOOK_ID,
            display_name="Active Subset Inputs",
            description="Deterministic discovery hook for the subset-selection artifacts that define the active root boundary.",
            source_kind=SUBSET_SELECTION_SOURCE_KIND,
            artifact_role_ids=[
                SELECTED_ROOT_IDS_ROLE_ID,
                SUBSET_MANIFEST_ROLE_ID,
                SUBSET_STATS_ROLE_ID,
            ],
            canonical_anchor_artifact_role_id=SUBSET_MANIFEST_ROLE_ID,
            required_contract_version=None,
        ),
        build_whole_brain_context_discovery_hook_definition(
            hook_id=LOCAL_CONNECTIVITY_INPUTS_DISCOVERY_HOOK_ID,
            display_name="Local Connectivity Inputs",
            description="Deterministic discovery hook for the local registry or synapse inputs used to widen the active subset into whole-brain context.",
            source_kind=LOCAL_CONNECTIVITY_SOURCE_KIND,
            artifact_role_ids=[SYNAPSE_REGISTRY_ROLE_ID],
            canonical_anchor_artifact_role_id=SYNAPSE_REGISTRY_ROLE_ID,
            required_contract_version=COUPLING_BUNDLE_CONTRACT_VERSION,
        ),
        build_whole_brain_context_discovery_hook_definition(
            hook_id=DASHBOARD_CONTEXT_BRIDGE_DISCOVERY_HOOK_ID,
            display_name="Dashboard Context Bridge",
            description="Deterministic discovery hook for packaged dashboard-session artifacts that whole-brain context views may link through.",
            source_kind=DASHBOARD_SESSION_SOURCE_KIND,
            artifact_role_ids=[DASHBOARD_SESSION_METADATA_ROLE_ID],
            canonical_anchor_artifact_role_id=DASHBOARD_SESSION_METADATA_ROLE_ID,
            required_contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
        ),
        build_whole_brain_context_discovery_hook_definition(
            hook_id=SHOWCASE_CONTEXT_BRIDGE_DISCOVERY_HOOK_ID,
            display_name="Showcase Context Bridge",
            description="Deterministic discovery hook for packaged showcase-session artifacts that whole-brain context views may cite or synchronize with.",
            source_kind=SHOWCASE_SESSION_SOURCE_KIND,
            artifact_role_ids=[SHOWCASE_SESSION_METADATA_ROLE_ID],
            canonical_anchor_artifact_role_id=SHOWCASE_SESSION_METADATA_ROLE_ID,
            required_contract_version=SHOWCASE_SESSION_CONTRACT_VERSION,
        ),
        build_whole_brain_context_discovery_hook_definition(
            hook_id=WHOLE_BRAIN_CONTEXT_PACKAGE_DISCOVERY_HOOK_ID,
            display_name="Whole-Brain Context Package",
            description="Deterministic discovery hook for whole-brain-context-owned artifacts.",
            source_kind=WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND,
            artifact_role_ids=[
                WHOLE_BRAIN_CONTEXT_SESSION_METADATA_ROLE_ID,
                CONTEXT_VIEW_PAYLOAD_ROLE_ID,
                CONTEXT_QUERY_CATALOG_ROLE_ID,
                CONTEXT_VIEW_STATE_ROLE_ID,
            ],
            canonical_anchor_artifact_role_id=WHOLE_BRAIN_CONTEXT_SESSION_METADATA_ROLE_ID,
            required_contract_version=WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
        ),
    ]


def _artifact_record(
    *,
    path: str | Path,
    format: str,
    status: str,
    artifact_scope: str,
    description: str,
) -> dict[str, Any]:
    return {
        "path": str(Path(path).resolve()),
        "format": _normalize_nonempty_string(format, field_name="artifact.format"),
        "status": _normalize_asset_status(status, field_name="artifact.status"),
        "artifact_scope": _normalize_artifact_scope(artifact_scope),
        "description": _normalize_nonempty_string(
            description,
            field_name="artifact.description",
        ),
    }


def _normalize_representative_context(
    payload: Mapping[str, Any],
    *,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    normalized["node_records"] = _normalize_node_record_catalog(
        normalized.get("node_records", []),
        field_name=f"{field_name}.node_records",
    )
    normalized["edge_records"] = _normalize_edge_record_catalog(
        normalized.get("edge_records", []),
        field_name=f"{field_name}.edge_records",
    )
    normalized["downstream_module_records"] = _normalize_downstream_module_record_catalog(
        normalized.get("downstream_module_records", []),
        field_name=f"{field_name}.downstream_module_records",
    )
    return normalized


def _normalize_output_root_reference(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("output_root_reference must be a mapping.")
    return {
        "processed_simulator_results_dir": str(
            Path(
                _normalize_nonempty_string(
                    payload.get("processed_simulator_results_dir"),
                    field_name="output_root_reference.processed_simulator_results_dir",
                )
            ).resolve()
        )
    }


def _normalize_bundle_layout(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("bundle_layout must be a mapping.")
    return {
        "bundle_directory": str(
            Path(
                _normalize_nonempty_string(
                    payload.get("bundle_directory"),
                    field_name="bundle_layout.bundle_directory",
                )
            ).resolve()
        )
    }


def _normalize_artifacts_mapping(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, Mapping):
        raise ValueError("artifacts must be a mapping.")
    normalized: dict[str, dict[str, Any]] = {}
    for artifact_id in (
        METADATA_JSON_KEY,
        CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID,
        CONTEXT_QUERY_CATALOG_ARTIFACT_ID,
        CONTEXT_VIEW_STATE_ARTIFACT_ID,
    ):
        item = payload.get(artifact_id)
        if not isinstance(item, Mapping):
            raise ValueError(f"artifacts[{artifact_id!r}] must be a mapping.")
        normalized[artifact_id] = {
            "path": str(
                Path(
                    _normalize_nonempty_string(
                        item.get("path"),
                        field_name=f"artifacts.{artifact_id}.path",
                    )
                ).resolve()
            ),
            "format": _normalize_nonempty_string(
                item.get("format"),
                field_name=f"artifacts.{artifact_id}.format",
            ),
            "status": _normalize_asset_status(
                item.get("status"),
                field_name=f"artifacts.{artifact_id}.status",
            ),
            "artifact_scope": _normalize_artifact_scope(item.get("artifact_scope")),
            "description": _normalize_nonempty_string(
                item.get("description"),
                field_name=f"artifacts.{artifact_id}.description",
            ),
        }
    return normalized


def _normalize_definition_catalog(
    payload: Any,
    *,
    field_name: str,
    parser: Any,
    key_name: str,
    expected_ids: set[str],
    order_map: Mapping[str, int],
) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of mappings.")
    normalized_items = [parser(item) for item in payload]
    _ensure_unique_ids(normalized_items, key_name=key_name, field_name=field_name)
    _ensure_catalog_ids_match(
        catalog_name=field_name,
        actual_ids={str(item[key_name]) for item in normalized_items},
        expected_ids=expected_ids,
    )
    return sorted(normalized_items, key=lambda item: order_map[str(item[key_name])])


def _normalize_artifact_reference_catalog(
    payload: Any,
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of mappings.")
    normalized_items = [
        parse_whole_brain_context_artifact_reference(item) for item in payload
    ]
    return sorted(
        normalized_items,
        key=lambda item: (
            _ARTIFACT_SOURCE_KIND_ORDER[item["source_kind"]],
            _ARTIFACT_ROLE_ORDER[item["artifact_role_id"]],
            item["path"],
        ),
    )


def _normalize_node_record_catalog(payload: Any, *, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of mappings.")
    normalized_items = [parse_whole_brain_context_node_record(item) for item in payload]
    _ensure_unique_ids(normalized_items, key_name="root_id", field_name=field_name)
    return sorted(
        normalized_items,
        key=lambda item: _identifier_sort_key(str(item["root_id"])),
    )


def _normalize_edge_record_catalog(payload: Any, *, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of mappings.")
    normalized_items = [parse_whole_brain_context_edge_record(item) for item in payload]
    return sorted(
        normalized_items,
        key=lambda item: (
            _identifier_sort_key(str(item["source_root_id"])),
            _identifier_sort_key(str(item["target_root_id"])),
            _EDGE_ROLE_ORDER[item["edge_role_id"]],
        ),
    )


def _normalize_downstream_module_record_catalog(
    payload: Any,
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of mappings.")
    normalized_items = [
        parse_whole_brain_context_downstream_module_record(item) for item in payload
    ]
    _ensure_unique_ids(normalized_items, key_name="module_id", field_name=field_name)
    return sorted(
        normalized_items,
        key=lambda item: _identifier_sort_key(str(item["module_id"])),
    )


def _validate_artifact_references_against_contract(
    artifact_references: Sequence[Mapping[str, Any]],
    *,
    contract_metadata: Mapping[str, Any],
    field_name: str,
) -> None:
    hooks = {
        item["artifact_role_id"]: item for item in contract_metadata["artifact_hook_catalog"]
    }
    for index, reference in enumerate(artifact_references):
        hook = hooks.get(str(reference["artifact_role_id"]))
        if hook is None:
            raise ValueError(
                f"{field_name}[{index}] artifact_role_id is not part of the whole-brain context contract."
            )
        if reference["source_kind"] != hook["source_kind"]:
            raise ValueError(
                f"{field_name}[{index}] source_kind does not match artifact_hook_catalog."
            )


def _validate_representative_context_against_contract(
    representative_context: Mapping[str, Any],
    *,
    contract_metadata: Mapping[str, Any],
    query_state: Mapping[str, Any],
    field_name: str,
) -> None:
    layer_support = {
        item["context_layer_id"]: set(item["supported_node_role_ids"])
        for item in contract_metadata["context_layer_catalog"]
    }
    enabled_overlays = set(query_state["enabled_overlay_ids"])
    enabled_facets = set(query_state["enabled_metadata_facet_ids"])
    node_root_ids = {str(item["root_id"]) for item in representative_context["node_records"]}
    for index, item in enumerate(representative_context["node_records"]):
        if item["node_role_id"] not in layer_support.get(item["context_layer_id"], set()):
            raise ValueError(
                f"{field_name}.node_records[{index}] assigns node_role_id to an unsupported context layer."
            )
        for overlay_id in item["overlay_ids"]:
            if overlay_id not in enabled_overlays:
                raise ValueError(
                    f"{field_name}.node_records[{index}] includes an overlay not enabled by query_state."
                )
        for facet_id in item["metadata_facet_values"]:
            if facet_id not in enabled_facets:
                raise ValueError(
                    f"{field_name}.node_records[{index}] includes a metadata facet not enabled by query_state."
                )
    for index, item in enumerate(representative_context["edge_records"]):
        if item["source_root_id"] not in node_root_ids or item["target_root_id"] not in node_root_ids:
            raise ValueError(
                f"{field_name}.edge_records[{index}] references roots missing from node_records."
            )
    for index, item in enumerate(representative_context["downstream_module_records"]):
        for represented_root_id in item["represented_root_ids"]:
            if represented_root_id not in node_root_ids:
                raise ValueError(
                    f"{field_name}.downstream_module_records[{index}] references represented roots missing from node_records."
                )


def _normalize_identifier_list(
    payload: Any,
    *,
    field_name: str,
    allow_empty: bool,
) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of identifiers.")
    normalized_values = {
        _normalize_identifier(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(payload)
    }
    if not allow_empty and not normalized_values:
        raise ValueError(f"{field_name} must not be empty.")
    return sorted(normalized_values, key=_identifier_sort_key)


def _normalize_known_value_list(
    payload: Any,
    *,
    field_name: str,
    supported_values: Sequence[str],
    allow_empty: bool,
) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of strings.")
    seen: set[str] = set()
    supported_set = set(supported_values)
    for index, item in enumerate(payload):
        normalized_item = _normalize_identifier(
            item,
            field_name=f"{field_name}[{index}]",
        )
        if normalized_item not in supported_set:
            raise ValueError(
                f"{field_name}[{index}] must be one of {tuple(supported_values)!r}."
            )
        seen.add(normalized_item)
    if not allow_empty and not seen:
        raise ValueError(f"{field_name} must not be empty.")
    return [value for value in supported_values if value in seen]


def _normalize_nonempty_string_list(payload: Any, *, field_name: str) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of strings.")
    normalized_values = {
        _normalize_nonempty_string(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(payload)
    }
    return sorted(normalized_values)


def _normalize_metadata_facet_values(payload: Any, *, field_name: str) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    normalized_keys = {
        _normalize_metadata_facet_id(key): value for key, value in dict(payload).items()
    }
    return _normalize_json_mapping(normalized_keys, field_name=field_name)


def _normalize_optional_string(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _normalize_nonempty_string(value, field_name=field_name)


def _normalize_optional_float(value: Any, *, field_name: str) -> float | None:
    if value is None:
        return None
    normalized = _normalize_float(value, field_name=field_name)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def _normalize_boolean(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} must be a boolean.")


def _normalize_positive_int(value: Any, *, field_name: str) -> int:
    normalized = int(value)
    if normalized <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _normalize_nonnegative_int(value: Any, *, field_name: str) -> int:
    normalized = int(value)
    if normalized < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def _normalize_hex_hash(value: Any, *, field_name: str) -> str:
    normalized = _normalize_nonempty_string(value, field_name=field_name).lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError(f"{field_name} must be a 64-character lowercase hexadecimal sha256 digest.")
    return normalized


def _normalize_delivery_model(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="delivery_model")
    if normalized not in SUPPORTED_DELIVERY_MODELS:
        raise ValueError(f"delivery_model must be one of {SUPPORTED_DELIVERY_MODELS!r}.")
    return normalized


def _normalize_query_family(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="query_family")
    if normalized not in SUPPORTED_QUERY_FAMILIES:
        raise ValueError(f"query_family must be one of {SUPPORTED_QUERY_FAMILIES!r}.")
    return normalized


def _normalize_query_profile_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="query_profile_id")
    if normalized not in SUPPORTED_QUERY_PROFILE_IDS:
        raise ValueError(f"query_profile_id must be one of {SUPPORTED_QUERY_PROFILE_IDS!r}.")
    return normalized


def _normalize_node_boundary_status(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="selection_boundary_status")
    if normalized not in SUPPORTED_NODE_BOUNDARY_STATUSES:
        raise ValueError(
            f"selection_boundary_status must be one of {SUPPORTED_NODE_BOUNDARY_STATUSES!r}."
        )
    return normalized


def _normalize_node_role_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="node_role_id")
    if normalized not in SUPPORTED_NODE_ROLE_IDS:
        raise ValueError(f"node_role_id must be one of {SUPPORTED_NODE_ROLE_IDS!r}.")
    return normalized


def _normalize_edge_direction_family(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="direction_family")
    if normalized not in SUPPORTED_EDGE_DIRECTION_FAMILIES:
        raise ValueError(
            f"direction_family must be one of {SUPPORTED_EDGE_DIRECTION_FAMILIES!r}."
        )
    return normalized


def _normalize_edge_role_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="edge_role_id")
    if normalized not in SUPPORTED_EDGE_ROLE_IDS:
        raise ValueError(f"edge_role_id must be one of {SUPPORTED_EDGE_ROLE_IDS!r}.")
    return normalized


def _normalize_layer_kind(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="layer_kind")
    if normalized not in SUPPORTED_LAYER_KINDS:
        raise ValueError(f"layer_kind must be one of {SUPPORTED_LAYER_KINDS!r}.")
    return normalized


def _normalize_context_layer_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="context_layer_id")
    if normalized not in SUPPORTED_CONTEXT_LAYER_IDS:
        raise ValueError(f"context_layer_id must be one of {SUPPORTED_CONTEXT_LAYER_IDS!r}.")
    return normalized


def _normalize_overlay_category(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="overlay_category")
    if normalized not in SUPPORTED_OVERLAY_CATEGORIES:
        raise ValueError(f"overlay_category must be one of {SUPPORTED_OVERLAY_CATEGORIES!r}.")
    return normalized


def _normalize_overlay_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="overlay_id")
    if normalized not in SUPPORTED_OVERLAY_IDS:
        raise ValueError(f"overlay_id must be one of {SUPPORTED_OVERLAY_IDS!r}.")
    return normalized


def _normalize_reduction_profile_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="reduction_profile_id")
    if normalized not in SUPPORTED_REDUCTION_PROFILE_IDS:
        raise ValueError(
            f"reduction_profile_id must be one of {SUPPORTED_REDUCTION_PROFILE_IDS!r}."
        )
    return normalized


def _normalize_metadata_facet_scope(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="facet_scope")
    if normalized not in SUPPORTED_METADATA_FACET_SCOPES:
        raise ValueError(
            f"facet_scope must be one of {SUPPORTED_METADATA_FACET_SCOPES!r}."
        )
    return normalized


def _normalize_metadata_facet_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="metadata_facet_id")
    if normalized not in SUPPORTED_METADATA_FACET_IDS:
        raise ValueError(
            f"metadata_facet_id must be one of {SUPPORTED_METADATA_FACET_IDS!r}."
        )
    return normalized


def _normalize_downstream_module_role_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="downstream_module_role_id")
    if normalized not in SUPPORTED_DOWNSTREAM_MODULE_ROLE_IDS:
        raise ValueError(
            "downstream_module_role_id must be one of "
            f"{SUPPORTED_DOWNSTREAM_MODULE_ROLE_IDS!r}."
        )
    return normalized


def _normalize_artifact_source_kind(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="artifact_reference.source_kind")
    if normalized not in SUPPORTED_ARTIFACT_SOURCE_KINDS:
        raise ValueError(
            f"artifact source kind must be one of {SUPPORTED_ARTIFACT_SOURCE_KINDS!r}."
        )
    return normalized


def _normalize_artifact_scope(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="artifact_scope")
    if normalized not in SUPPORTED_ARTIFACT_SCOPES:
        raise ValueError(f"artifact_scope must be one of {SUPPORTED_ARTIFACT_SCOPES!r}.")
    return normalized


def _normalize_optional_artifact_scope(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = _normalize_identifier(value, field_name=field_name)
    if normalized not in SUPPORTED_ARTIFACT_SCOPES:
        raise ValueError(f"{field_name} must be one of {SUPPORTED_ARTIFACT_SCOPES!r}.")
    return normalized


def _normalize_artifact_role_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="artifact_role_id")
    if normalized not in SUPPORTED_ARTIFACT_ROLE_IDS:
        raise ValueError(f"artifact_role_id must be one of {SUPPORTED_ARTIFACT_ROLE_IDS!r}.")
    return normalized


def _normalize_discovery_hook_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="hook_id")
    if normalized not in SUPPORTED_DISCOVERY_HOOK_IDS:
        raise ValueError(f"hook_id must be one of {SUPPORTED_DISCOVERY_HOOK_IDS!r}.")
    return normalized


def _extract_whole_brain_context_contract_mapping(
    record: Mapping[str, Any],
) -> Mapping[str, Any]:
    if not isinstance(record, Mapping):
        raise ValueError("whole-brain context contract record must be a mapping.")
    if isinstance(record.get("whole_brain_context_contract"), Mapping):
        return record["whole_brain_context_contract"]
    return record


def _extract_whole_brain_context_session_mapping(
    record: Mapping[str, Any],
) -> Mapping[str, Any]:
    if not isinstance(record, Mapping):
        raise ValueError("whole-brain context session record must be a mapping.")
    if isinstance(record.get("whole_brain_context_session"), Mapping):
        return record["whole_brain_context_session"]
    return record


def _ensure_unique_ids(
    items: Sequence[Mapping[str, Any]],
    *,
    key_name: str,
    field_name: str,
) -> None:
    ids = [str(item[key_name]) for item in items]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        raise ValueError(f"{field_name} contains duplicate {key_name} values {duplicates!r}.")


def _ensure_catalog_ids_match(
    *,
    catalog_name: str,
    actual_ids: set[str],
    expected_ids: set[str],
) -> None:
    if actual_ids != expected_ids:
        missing_ids = sorted(expected_ids - actual_ids)
        extra_ids = sorted(actual_ids - expected_ids)
        raise ValueError(
            f"{catalog_name} must contain the canonical v1 ids. Missing={missing_ids!r} extra={extra_ids!r}."
        )


def _identifier_sort_key(value: str) -> tuple[int, int | str]:
    text = str(value)
    if text.isdigit():
        return (0, int(text))
    return (1, text)
