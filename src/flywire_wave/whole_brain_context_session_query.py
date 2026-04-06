from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .stimulus_contract import _normalize_identifier, _normalize_nonempty_string
from .whole_brain_context_contract import (
    ACTIVE_BOUNDARY_OVERLAY_ID,
    ACTIVE_SUBSET_SHELL_QUERY_PROFILE_ID,
    BALANCED_NEIGHBORHOOD_REDUCTION_PROFILE_ID,
    BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
    BIDIRECTIONAL_CONTEXT_GRAPH_OVERLAY_ID,
    CONTEXT_VIEW_PAYLOAD_ROLE_ID,
    DASHBOARD_SESSION_METADATA_ROLE_ID,
    DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
    DOWNSTREAM_GRAPH_OVERLAY_ID,
    DOWNSTREAM_MODULE_COLLAPSED_REDUCTION_PROFILE_ID,
    DOWNSTREAM_MODULE_OVERLAY_ID,
    DOWNSTREAM_MODULE_REVIEW_QUERY_PROFILE_ID,
    METADATA_FACET_BADGES_OVERLAY_ID,
    PATHWAY_FOCUS_REDUCTION_PROFILE_ID,
    PATHWAY_HIGHLIGHT_OVERLAY_ID,
    PATHWAY_HIGHLIGHT_REVIEW_QUERY_PROFILE_ID,
    SHOWCASE_SESSION_METADATA_ROLE_ID,
    UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
    UPSTREAM_GRAPH_OVERLAY_ID,
    WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
    build_whole_brain_context_query_state,
    discover_whole_brain_context_query_profiles,
)
from .whole_brain_context_query import execute_whole_brain_context_query


DEFAULT_CONTEXT_QUERY_PRESET_LIBRARY_ID = "milestone17_review_query_preset_library.v1"

OVERVIEW_CONTEXT_PRESET_ID = "overview_context"
UPSTREAM_HALO_PRESET_ID = "upstream_halo"
DOWNSTREAM_HALO_PRESET_ID = "downstream_halo"
PATHWAY_FOCUS_PRESET_ID = "pathway_focus"
DASHBOARD_HANDOFF_PRESET_ID = "dashboard_handoff"
SHOWCASE_HANDOFF_PRESET_ID = "showcase_handoff"

WHOLE_BRAIN_CONTEXT_HANDOFF_LINK_KIND = "whole_brain_context_handoff"

SUPPORTED_CONTEXT_QUERY_PRESET_IDS = (
    OVERVIEW_CONTEXT_PRESET_ID,
    UPSTREAM_HALO_PRESET_ID,
    DOWNSTREAM_HALO_PRESET_ID,
    PATHWAY_FOCUS_PRESET_ID,
    DASHBOARD_HANDOFF_PRESET_ID,
    SHOWCASE_HANDOFF_PRESET_ID,
)


def execute_whole_brain_context_session_queries(
    *,
    plan_version: str,
    config_path: str,
    contract_metadata: Mapping[str, Any],
    selection_context: Mapping[str, Any],
    registry_sources: Mapping[str, Any],
    query_profile_resolution: Mapping[str, Any],
    query_state: Mapping[str, Any],
    reduction_profile: Mapping[str, Any],
    metadata_facet_requests: Sequence[Mapping[str, Any]],
    downstream_module_requests: Sequence[Mapping[str, Any]],
    linked_sessions: Mapping[str, Any],
    fixture_profile: Mapping[str, Any],
) -> dict[str, Any]:
    query_execution = execute_whole_brain_context_query(
        _build_query_execution_input(
            plan_version=plan_version,
            config_path=config_path,
            selection_context=selection_context,
            registry_sources=registry_sources,
            query_profile_resolution=query_profile_resolution,
            query_state=query_state,
            reduction_profile=reduction_profile,
            metadata_facet_requests=metadata_facet_requests,
            downstream_module_requests=downstream_module_requests,
        )
    )
    query_preset_library = hydrate_whole_brain_context_query_preset_library(
        plan_version=plan_version,
        config_path=config_path,
        contract_metadata=contract_metadata,
        selection_context=selection_context,
        registry_sources=registry_sources,
        query_profile_resolution=query_profile_resolution,
        query_state=query_state,
        metadata_facet_requests=metadata_facet_requests,
        downstream_module_requests=downstream_module_requests,
        linked_sessions=linked_sessions,
        fixture_profile=fixture_profile,
    )
    query_preset_library = _apply_downstream_module_handoffs_to_query_preset_library(
        query_preset_library=query_preset_library,
        linked_sessions=linked_sessions,
    )
    query_execution = _apply_downstream_module_handoffs_to_query_execution(
        query_execution=query_execution,
        query_preset_library=query_preset_library,
        linked_sessions=linked_sessions,
    )
    return {
        "query_execution": copy.deepcopy(query_execution),
        "query_preset_library": copy.deepcopy(query_preset_library),
    }


def hydrate_whole_brain_context_query_preset_library(
    *,
    plan_version: str,
    config_path: str,
    contract_metadata: Mapping[str, Any],
    selection_context: Mapping[str, Any],
    registry_sources: Mapping[str, Any],
    query_profile_resolution: Mapping[str, Any],
    query_state: Mapping[str, Any],
    metadata_facet_requests: Sequence[Mapping[str, Any]],
    downstream_module_requests: Sequence[Mapping[str, Any]],
    linked_sessions: Mapping[str, Any],
    fixture_profile: Mapping[str, Any],
) -> dict[str, Any]:
    query_profiles_by_id = {
        str(item["query_profile_id"]): copy.deepcopy(dict(item))
        for item in discover_whole_brain_context_query_profiles(contract_metadata)
    }
    available_profile_ids = set(query_profile_resolution["available_query_profile_ids"])
    available_presets: list[dict[str, Any]] = []
    unavailable_presets: list[dict[str, Any]] = []
    preset_payloads: dict[str, dict[str, Any]] = {}
    enabled_metadata_facet_ids = list(query_state["enabled_metadata_facet_ids"])
    for sequence_index, blueprint in enumerate(_query_preset_blueprints()):
        preset_id = str(blueprint["preset_id"])
        required_linked_session_kind = blueprint.get("required_linked_session_kind")
        if (
            required_linked_session_kind is not None
            and required_linked_session_kind not in linked_sessions
        ):
            unavailable_presets.append(
                _build_unavailable_query_preset_record(
                    blueprint=blueprint,
                    sequence_index=sequence_index,
                    reason=(
                        f"Requires a linked {required_linked_session_kind}_session review surface."
                    ),
                )
            )
            continue
        resolved_query_profile_id = next(
            (
                profile_id
                for profile_id in blueprint["preferred_query_profile_ids"]
                if profile_id in available_profile_ids
            ),
            None,
        )
        if resolved_query_profile_id is None:
            unavailable_presets.append(
                _build_unavailable_query_preset_record(
                    blueprint=blueprint,
                    sequence_index=sequence_index,
                    reason=(
                        "Required query profiles are unavailable for the resolved artifact set: "
                        f"{list(blueprint['preferred_query_profile_ids'])!r}."
                    ),
                )
            )
            continue
        query_profile = query_profiles_by_id[resolved_query_profile_id]
        enabled_overlay_ids = [
            overlay_id
            for overlay_id in blueprint["preferred_overlay_ids"]
            if overlay_id in set(query_profile["supported_overlay_ids"])
        ]
        if not enabled_overlay_ids:
            enabled_overlay_ids = list(query_profile["supported_overlay_ids"])
        default_overlay_id = (
            str(blueprint["default_overlay_id"])
            if str(blueprint["default_overlay_id"]) in enabled_overlay_ids
            else str(query_profile["default_overlay_id"])
        )
        if default_overlay_id not in enabled_overlay_ids:
            default_overlay_id = str(enabled_overlay_ids[0])
        preset_query_state = build_whole_brain_context_query_state(
            query_profile_id=resolved_query_profile_id,
            default_overlay_id=default_overlay_id,
            default_reduction_profile_id=str(
                blueprint["default_reduction_profile_id"]
            ),
            enabled_overlay_ids=enabled_overlay_ids,
            enabled_metadata_facet_ids=enabled_metadata_facet_ids,
            contract_metadata=contract_metadata,
        )
        preset_reduction_profile = _catalog_item_by_id(
            contract_metadata["reduction_profile_catalog"],
            key_name="reduction_profile_id",
            identifier=preset_query_state["default_reduction_profile_id"],
        )
        preset_query_profile_resolution = {
            "active_query_profile_id": resolved_query_profile_id,
            "selected_query_profile_ids": [resolved_query_profile_id],
            "available_query_profile_ids": list(
                query_profile_resolution["available_query_profile_ids"]
            ),
        }
        preset_execution = execute_whole_brain_context_query(
            _build_query_execution_input(
                plan_version=plan_version,
                config_path=config_path,
                selection_context=selection_context,
                registry_sources=registry_sources,
                query_profile_resolution=preset_query_profile_resolution,
                query_state=preset_query_state,
                reduction_profile=preset_reduction_profile,
                metadata_facet_requests=metadata_facet_requests,
                downstream_module_requests=downstream_module_requests,
            ),
            reduction_controls=copy.deepcopy(
                dict(blueprint.get("reduction_controls_patch", {}))
            ),
        )
        if (
            blueprint.get("requires_pathway_highlight", False)
            and not preset_execution["pathway_highlights"]
        ):
            unavailable_presets.append(
                _build_unavailable_query_preset_record(
                    blueprint=blueprint,
                    sequence_index=sequence_index,
                    reason="No deterministic pathway highlight survived the packaged query budget.",
                )
            )
            continue
        preset_payloads[preset_id] = _build_query_preset_payload(
            blueprint=blueprint,
            preset_query_state=preset_query_state,
            preset_reduction_profile=preset_reduction_profile,
            preset_execution=preset_execution,
        )
        available_presets.append(
            _build_query_preset_record(
                blueprint=blueprint,
                sequence_index=sequence_index,
                query_profile=query_profile,
                preset_query_state=preset_query_state,
                preset_execution=preset_execution,
                linked_sessions=linked_sessions,
            )
        )
    active_preset_id = _resolve_active_query_preset_id(
        active_query_profile_id=str(
            query_profile_resolution["active_query_profile_id"]
        ),
        available_presets=available_presets,
    )
    return {
        "preset_library_id": DEFAULT_CONTEXT_QUERY_PRESET_LIBRARY_ID,
        "fixture_profile": copy.deepcopy(dict(fixture_profile)),
        "active_preset_id": active_preset_id,
        "available_preset_ids": [
            str(item["preset_id"]) for item in available_presets
        ],
        "preset_discovery_order": list(SUPPORTED_CONTEXT_QUERY_PRESET_IDS),
        "available_query_presets": [copy.deepcopy(dict(item)) for item in available_presets],
        "unavailable_query_presets": [
            copy.deepcopy(dict(item)) for item in unavailable_presets
        ],
        "handoff_preset_ids": {
            "dashboard": (
                DASHBOARD_HANDOFF_PRESET_ID
                if any(
                    str(item["preset_id"]) == DASHBOARD_HANDOFF_PRESET_ID
                    for item in available_presets
                )
                else None
            ),
            "showcase": (
                SHOWCASE_HANDOFF_PRESET_ID
                if any(
                    str(item["preset_id"]) == SHOWCASE_HANDOFF_PRESET_ID
                    for item in available_presets
                )
                else None
            ),
        },
        "preset_payloads_by_id": copy.deepcopy(preset_payloads),
    }


def _build_query_execution_input(
    *,
    plan_version: str,
    config_path: str,
    selection_context: Mapping[str, Any],
    registry_sources: Mapping[str, Any],
    query_profile_resolution: Mapping[str, Any],
    query_state: Mapping[str, Any],
    reduction_profile: Mapping[str, Any],
    metadata_facet_requests: Sequence[Mapping[str, Any]],
    downstream_module_requests: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "plan_version": str(plan_version),
        "config_path": str(Path(config_path).resolve()),
        "selection": copy.deepcopy(dict(selection_context)),
        "registry_sources": copy.deepcopy(dict(registry_sources)),
        "query_profile_resolution": copy.deepcopy(dict(query_profile_resolution)),
        "query_state": copy.deepcopy(dict(query_state)),
        "reduction_profile": copy.deepcopy(dict(reduction_profile)),
        "metadata_facet_requests": [
            copy.deepcopy(dict(item)) for item in metadata_facet_requests
        ],
        "downstream_module_requests": [
            copy.deepcopy(dict(item)) for item in downstream_module_requests
        ],
    }


def _query_preset_blueprints() -> list[dict[str, Any]]:
    return [
        {
            "preset_id": OVERVIEW_CONTEXT_PRESET_ID,
            "display_name": "Whole-Brain Overview",
            "description": "Default richer Milestone 17 review landing for the active subset plus a broader deterministic neighborhood.",
            "preferred_query_profile_ids": [
                BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                ACTIVE_SUBSET_SHELL_QUERY_PROFILE_ID,
            ],
            "preferred_overlay_ids": [
                ACTIVE_BOUNDARY_OVERLAY_ID,
                BIDIRECTIONAL_CONTEXT_GRAPH_OVERLAY_ID,
                UPSTREAM_GRAPH_OVERLAY_ID,
                DOWNSTREAM_GRAPH_OVERLAY_ID,
                PATHWAY_HIGHLIGHT_OVERLAY_ID,
                DOWNSTREAM_MODULE_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            "default_overlay_id": BIDIRECTIONAL_CONTEXT_GRAPH_OVERLAY_ID,
            "default_reduction_profile_id": BALANCED_NEIGHBORHOOD_REDUCTION_PROFILE_ID,
            "reduction_controls_patch": {},
            "primary_graph_view_id": "overview_graph",
            "required_linked_session_kind": None,
            "requires_pathway_highlight": False,
            "discovery_note": "Use this preset to compare the compact upstream gate against the richer packaged context graph.",
        },
        {
            "preset_id": UPSTREAM_HALO_PRESET_ID,
            "display_name": "Upstream Halo",
            "description": "Directional incoming-context review surface around the active subset.",
            "preferred_query_profile_ids": [
                UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
            ],
            "preferred_overlay_ids": [
                ACTIVE_BOUNDARY_OVERLAY_ID,
                UPSTREAM_GRAPH_OVERLAY_ID,
                PATHWAY_HIGHLIGHT_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            "default_overlay_id": UPSTREAM_GRAPH_OVERLAY_ID,
            "default_reduction_profile_id": BALANCED_NEIGHBORHOOD_REDUCTION_PROFILE_ID,
            "reduction_controls_patch": {},
            "primary_graph_view_id": "overview_graph",
            "required_linked_session_kind": None,
            "requires_pathway_highlight": False,
            "discovery_note": "Use this preset to review context-only nodes that feed into the active subset.",
        },
        {
            "preset_id": DOWNSTREAM_HALO_PRESET_ID,
            "display_name": "Downstream Halo",
            "description": "Directional outgoing-context review surface around the active subset.",
            "preferred_query_profile_ids": [
                DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
            ],
            "preferred_overlay_ids": [
                ACTIVE_BOUNDARY_OVERLAY_ID,
                DOWNSTREAM_GRAPH_OVERLAY_ID,
                DOWNSTREAM_MODULE_OVERLAY_ID,
                PATHWAY_HIGHLIGHT_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            "default_overlay_id": DOWNSTREAM_GRAPH_OVERLAY_ID,
            "default_reduction_profile_id": DOWNSTREAM_MODULE_COLLAPSED_REDUCTION_PROFILE_ID,
            "reduction_controls_patch": {},
            "primary_graph_view_id": "overview_graph",
            "required_linked_session_kind": None,
            "requires_pathway_highlight": False,
            "discovery_note": "Use this preset to review outgoing context breadth without relabeling it as active simulator state.",
        },
        {
            "preset_id": PATHWAY_FOCUS_PRESET_ID,
            "display_name": "Pathway Focus",
            "description": "Focused pathway review surface for one deterministic highlighted context path.",
            "preferred_query_profile_ids": [
                PATHWAY_HIGHLIGHT_REVIEW_QUERY_PROFILE_ID,
            ],
            "preferred_overlay_ids": [
                ACTIVE_BOUNDARY_OVERLAY_ID,
                PATHWAY_HIGHLIGHT_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            "default_overlay_id": PATHWAY_HIGHLIGHT_OVERLAY_ID,
            "default_reduction_profile_id": PATHWAY_FOCUS_REDUCTION_PROFILE_ID,
            "reduction_controls_patch": {},
            "primary_graph_view_id": "focused_subgraph",
            "required_linked_session_kind": None,
            "requires_pathway_highlight": True,
            "discovery_note": "Use this preset for the first local pathway-focused Milestone 17 review case.",
        },
        {
            "preset_id": DASHBOARD_HANDOFF_PRESET_ID,
            "display_name": "Dashboard Handoff",
            "description": "Bridge the compact dashboard gate into the richer whole-brain review package.",
            "preferred_query_profile_ids": [
                BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                ACTIVE_SUBSET_SHELL_QUERY_PROFILE_ID,
            ],
            "preferred_overlay_ids": [
                ACTIVE_BOUNDARY_OVERLAY_ID,
                BIDIRECTIONAL_CONTEXT_GRAPH_OVERLAY_ID,
                UPSTREAM_GRAPH_OVERLAY_ID,
                DOWNSTREAM_GRAPH_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            "default_overlay_id": BIDIRECTIONAL_CONTEXT_GRAPH_OVERLAY_ID,
            "default_reduction_profile_id": BALANCED_NEIGHBORHOOD_REDUCTION_PROFILE_ID,
            "reduction_controls_patch": {},
            "primary_graph_view_id": "overview_graph",
            "required_linked_session_kind": "dashboard",
            "requires_pathway_highlight": False,
            "discovery_note": "Use this preset when reviewing the packaged dashboard session as the fast readiness gate before opening broader context.",
        },
        {
            "preset_id": SHOWCASE_HANDOFF_PRESET_ID,
            "display_name": "Showcase Handoff",
            "description": "Bridge the compact showcase rehearsal surface into a richer whole-brain review state.",
            "preferred_query_profile_ids": [
                PATHWAY_HIGHLIGHT_REVIEW_QUERY_PROFILE_ID,
                DOWNSTREAM_MODULE_REVIEW_QUERY_PROFILE_ID,
                BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
            ],
            "preferred_overlay_ids": [
                ACTIVE_BOUNDARY_OVERLAY_ID,
                PATHWAY_HIGHLIGHT_OVERLAY_ID,
                DOWNSTREAM_GRAPH_OVERLAY_ID,
                DOWNSTREAM_MODULE_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            "default_overlay_id": PATHWAY_HIGHLIGHT_OVERLAY_ID,
            "default_reduction_profile_id": PATHWAY_FOCUS_REDUCTION_PROFILE_ID,
            "reduction_controls_patch": {},
            "primary_graph_view_id": "focused_subgraph",
            "required_linked_session_kind": "showcase",
            "requires_pathway_highlight": False,
            "discovery_note": "Use this preset for review handoff from the compact showcase surface into broader context and pathway emphasis.",
        },
    ]


def _build_query_preset_payload(
    *,
    blueprint: Mapping[str, Any],
    preset_query_state: Mapping[str, Any],
    preset_reduction_profile: Mapping[str, Any],
    preset_execution: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "preset_id": str(blueprint["preset_id"]),
        "display_name": str(blueprint["display_name"]),
        "query_profile_id": str(preset_execution["query_profile_id"]),
        "query_family": str(preset_execution["query_family"]),
        "query_state": copy.deepcopy(dict(preset_query_state)),
        "reduction_profile": copy.deepcopy(dict(preset_reduction_profile)),
        "reduction_controls": copy.deepcopy(dict(preset_execution["reduction_controls"])),
        "execution_summary": copy.deepcopy(dict(preset_execution["execution_summary"])),
        "overview_graph": copy.deepcopy(dict(preset_execution["overview_graph"])),
        "focused_subgraph": copy.deepcopy(dict(preset_execution["focused_subgraph"])),
        "pathway_highlights": [
            copy.deepcopy(dict(item)) for item in preset_execution["pathway_highlights"]
        ],
    }


def _build_query_preset_record(
    *,
    blueprint: Mapping[str, Any],
    sequence_index: int,
    query_profile: Mapping[str, Any],
    preset_query_state: Mapping[str, Any],
    preset_execution: Mapping[str, Any],
    linked_sessions: Mapping[str, Any],
) -> dict[str, Any]:
    preset_id = str(blueprint["preset_id"])
    primary_graph_view_id = _query_preset_primary_graph_view_id(
        blueprint=blueprint,
        preset_execution=preset_execution,
    )
    pathway_reference = {
        "artifact_role_id": CONTEXT_VIEW_PAYLOAD_ROLE_ID,
        "payload_path": f"query_preset_payloads.{preset_id}.pathway_highlights",
        "highlight_count": len(preset_execution["pathway_highlights"]),
    }
    if preset_execution["pathway_highlights"]:
        pathway_reference["primary_pathway_id"] = str(
            preset_execution["pathway_highlights"][0]["pathway_id"]
        )
    return {
        "preset_id": preset_id,
        "display_name": str(blueprint["display_name"]),
        "description": str(blueprint["description"]),
        "sequence_index": sequence_index,
        "availability": "available",
        "query_profile_id": str(query_profile["query_profile_id"]),
        "query_family": str(query_profile["query_family"]),
        "default_overlay_id": str(preset_query_state["default_overlay_id"]),
        "enabled_overlay_ids": list(preset_query_state["enabled_overlay_ids"]),
        "default_reduction_profile_id": str(
            preset_query_state["default_reduction_profile_id"]
        ),
        "execution_summary": copy.deepcopy(
            dict(preset_execution["execution_summary"])
        ),
        "primary_graph_view_id": primary_graph_view_id,
        "graph_payload_references": {
            "primary_graph": _build_graph_payload_reference(
                preset_id=preset_id,
                graph_view_id=primary_graph_view_id,
            ),
            "overview_graph": _build_graph_payload_reference(
                preset_id=preset_id,
                graph_view_id="overview_graph",
            ),
            "focused_subgraph": _build_graph_payload_reference(
                preset_id=preset_id,
                graph_view_id="focused_subgraph",
            ),
            "pathway_highlights": pathway_reference,
        },
        "linked_session_target": _build_linked_session_target(
            blueprint=blueprint,
            linked_sessions=linked_sessions,
        ),
        "scientific_curation_required": bool(
            query_profile["scientific_curation_required"]
        ),
        "discovery_note": str(blueprint["discovery_note"]),
    }


def _build_unavailable_query_preset_record(
    *,
    blueprint: Mapping[str, Any],
    sequence_index: int,
    reason: str,
) -> dict[str, Any]:
    return {
        "preset_id": str(blueprint["preset_id"]),
        "display_name": str(blueprint["display_name"]),
        "description": str(blueprint["description"]),
        "sequence_index": sequence_index,
        "availability": "unavailable",
        "preferred_query_profile_ids": list(blueprint["preferred_query_profile_ids"]),
        "required_linked_session_kind": blueprint.get("required_linked_session_kind"),
        "unavailable_reason": str(reason),
    }


def _resolve_active_query_preset_id(
    *,
    active_query_profile_id: str,
    available_presets: Sequence[Mapping[str, Any]],
) -> str | None:
    available_by_id = {
        str(item["preset_id"]): copy.deepcopy(dict(item)) for item in available_presets
    }
    preferred_by_profile = {
        ACTIVE_SUBSET_SHELL_QUERY_PROFILE_ID: [OVERVIEW_CONTEXT_PRESET_ID],
        UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID: [UPSTREAM_HALO_PRESET_ID],
        DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID: [DOWNSTREAM_HALO_PRESET_ID],
        BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID: [
            OVERVIEW_CONTEXT_PRESET_ID,
            DASHBOARD_HANDOFF_PRESET_ID,
        ],
        PATHWAY_HIGHLIGHT_REVIEW_QUERY_PROFILE_ID: [
            PATHWAY_FOCUS_PRESET_ID,
            SHOWCASE_HANDOFF_PRESET_ID,
        ],
        DOWNSTREAM_MODULE_REVIEW_QUERY_PROFILE_ID: [
            SHOWCASE_HANDOFF_PRESET_ID,
            DOWNSTREAM_HALO_PRESET_ID,
        ],
    }
    for preset_id in preferred_by_profile.get(active_query_profile_id, []):
        if (
            preset_id in available_by_id
            and str(available_by_id[preset_id]["query_profile_id"])
            == active_query_profile_id
        ):
            return preset_id
    for item in available_presets:
        if str(item["query_profile_id"]) == active_query_profile_id:
            return str(item["preset_id"])
    if available_presets:
        return str(available_presets[0]["preset_id"])
    return None


def _build_graph_payload_reference(*, preset_id: str, graph_view_id: str) -> dict[str, Any]:
    return {
        "artifact_role_id": CONTEXT_VIEW_PAYLOAD_ROLE_ID,
        "payload_path": f"query_preset_payloads.{preset_id}.{graph_view_id}",
        "view_id": graph_view_id,
    }


def _query_preset_primary_graph_view_id(
    *,
    blueprint: Mapping[str, Any],
    preset_execution: Mapping[str, Any],
) -> str:
    preferred_graph_view_id = str(blueprint["primary_graph_view_id"])
    if (
        preferred_graph_view_id == "focused_subgraph"
        and not preset_execution["pathway_highlights"]
    ):
        return "overview_graph"
    return preferred_graph_view_id


def _build_linked_session_target(
    *,
    blueprint: Mapping[str, Any],
    linked_sessions: Mapping[str, Any],
) -> dict[str, Any] | None:
    required_linked_session_kind = blueprint.get("required_linked_session_kind")
    if required_linked_session_kind is None:
        return None
    linked_session = linked_sessions.get(str(required_linked_session_kind))
    if not isinstance(linked_session, Mapping):
        return None
    artifact_role_id = (
        SHOWCASE_SESSION_METADATA_ROLE_ID
        if str(required_linked_session_kind) == "showcase"
        else DASHBOARD_SESSION_METADATA_ROLE_ID
    )
    return {
        "session_kind": str(required_linked_session_kind),
        "artifact_role_id": artifact_role_id,
        "bundle_id": str(linked_session["bundle_id"]),
        "metadata_path": str(linked_session["metadata_path"]),
        "source_preset_ids": sorted(
            {
                str(item["source_preset_id"])
                for item in linked_session.get("handoff_links", [])
                if isinstance(item, Mapping)
                and str(item.get("target_context_preset_id"))
                == str(blueprint.get("preset_id"))
                and item.get("source_preset_id") is not None
            }
        ),
    }


def discover_showcase_handoff_links(
    narrative_preset_catalog: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(narrative_preset_catalog, Mapping):
        return []
    result: list[dict[str, Any]] = []
    saved_presets = narrative_preset_catalog.get("saved_presets", [])
    if not isinstance(saved_presets, Sequence) or isinstance(saved_presets, (str, bytes)):
        return result
    for preset in saved_presets:
        if not isinstance(preset, Mapping):
            continue
        preset_id = _normalize_optional_identifier(
            preset.get("preset_id"),
            field_name="showcase_handoff.preset_id",
        )
        patch = preset.get("presentation_state_patch", {})
        if not isinstance(patch, Mapping):
            continue
        rehearsal_metadata = patch.get("rehearsal_metadata", {})
        if not isinstance(rehearsal_metadata, Mapping):
            continue
        presentation_links = rehearsal_metadata.get("presentation_links", [])
        if not isinstance(presentation_links, Sequence) or isinstance(
            presentation_links,
            (str, bytes),
        ):
            continue
        for item in presentation_links:
            if not isinstance(item, Mapping):
                continue
            if str(item.get("link_kind")) != WHOLE_BRAIN_CONTEXT_HANDOFF_LINK_KIND:
                continue
            shared_context = item.get("shared_context", {})
            if not isinstance(shared_context, Mapping):
                continue
            target_contract_version = _normalize_optional_string(
                shared_context.get("target_contract_version"),
                field_name="showcase_handoff.target_contract_version",
            )
            if (
                target_contract_version is not None
                and target_contract_version
                != WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION
            ):
                raise ValueError(
                    "Showcase whole-brain handoff links must target "
                    f"{WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION!r}."
                )
            target_context_preset_id = _normalize_optional_identifier(
                shared_context.get("target_context_preset_id"),
                field_name="showcase_handoff.target_context_preset_id",
            )
            if preset_id is None or target_context_preset_id is None:
                continue
            result.append(
                {
                    "source_preset_id": preset_id,
                    "source_link_id": _normalize_optional_identifier(
                        item.get("link_id"),
                        field_name="showcase_handoff.link_id",
                    ),
                    "target_context_preset_id": target_context_preset_id,
                    "discovery_note": _normalize_optional_string(
                        shared_context.get("discovery_note"),
                        field_name="showcase_handoff.discovery_note",
                    ),
                }
            )
    return sorted(
        result,
        key=lambda item: (
            item["source_preset_id"],
            "" if item["source_link_id"] is None else item["source_link_id"],
            item["target_context_preset_id"],
        ),
    )


def _apply_downstream_module_handoffs_to_query_preset_library(
    *,
    query_preset_library: Mapping[str, Any],
    linked_sessions: Mapping[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(dict(query_preset_library))
    handoff_targets = _build_downstream_module_handoff_targets(
        query_preset_library=result,
        linked_sessions=linked_sessions,
    )
    payloads = _require_mapping(
        result.get("preset_payloads_by_id", {}),
        field_name="query_preset_library.preset_payloads_by_id",
    )
    result["preset_payloads_by_id"] = {
        str(preset_id): _apply_downstream_module_handoffs_to_preset_payload(
            payload=payload,
            handoff_targets=handoff_targets,
        )
        for preset_id, payload in payloads.items()
        if isinstance(payload, Mapping)
    }
    return result


def _apply_downstream_module_handoffs_to_query_execution(
    *,
    query_execution: Mapping[str, Any],
    query_preset_library: Mapping[str, Any],
    linked_sessions: Mapping[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(dict(query_execution))
    handoff_targets = _build_downstream_module_handoff_targets(
        query_preset_library=query_preset_library,
        linked_sessions=linked_sessions,
    )
    result["representative_context"] = _apply_downstream_module_handoffs_to_context_record(
        result.get("representative_context", {}),
        handoff_targets=handoff_targets,
    )
    for graph_key in ("overview_graph", "focused_subgraph"):
        if isinstance(result.get(graph_key), Mapping):
            result[graph_key] = _apply_downstream_module_handoffs_to_graph_view(
                result[graph_key],
                handoff_targets=handoff_targets,
            )
    return result


def _build_downstream_module_handoff_targets(
    *,
    query_preset_library: Mapping[str, Any],
    linked_sessions: Mapping[str, Any],
) -> list[dict[str, Any]]:
    available_presets = {
        str(item["preset_id"]): dict(item)
        for item in query_preset_library.get("available_query_presets", [])
        if isinstance(item, Mapping)
    }
    handoff_targets: list[dict[str, Any]] = []
    handoff_preset_ids = _require_mapping(
        query_preset_library.get("handoff_preset_ids", {}),
        field_name="query_preset_library.handoff_preset_ids",
    )

    dashboard_preset_id = _normalize_optional_identifier(
        handoff_preset_ids.get("dashboard"),
        field_name="handoff_preset_ids.dashboard",
    )
    dashboard_session = linked_sessions.get("dashboard")
    if dashboard_preset_id is not None and isinstance(dashboard_session, Mapping):
        preset_record = available_presets.get(dashboard_preset_id)
        if preset_record is not None:
            handoff_targets.append(
                _build_downstream_module_handoff_target_record(
                    linked_session=dashboard_session,
                    linked_session_kind="dashboard",
                    preset_record=preset_record,
                    source_preset_id=None,
                    source_link_id=None,
                    discovery_note="Compact dashboard gate can hand off into the broader Milestone 17 context preset.",
                )
            )

    showcase_preset_id = _normalize_optional_identifier(
        handoff_preset_ids.get("showcase"),
        field_name="handoff_preset_ids.showcase",
    )
    showcase_session = linked_sessions.get("showcase")
    if showcase_preset_id is not None and isinstance(showcase_session, Mapping):
        preset_record = available_presets.get(showcase_preset_id)
        if preset_record is not None:
            matching_links = [
                dict(item)
                for item in showcase_session.get("handoff_links", [])
                if isinstance(item, Mapping)
                and str(item.get("target_context_preset_id")) == showcase_preset_id
            ]
            if not matching_links:
                matching_links = [
                    {
                        "source_preset_id": None,
                        "source_link_id": None,
                        "discovery_note": (
                            "Linked showcase surface may hand off into the packaged "
                            "Milestone 17 showcase_handoff preset."
                        ),
                    }
                ]
            for link in matching_links:
                handoff_targets.append(
                    _build_downstream_module_handoff_target_record(
                        linked_session=showcase_session,
                        linked_session_kind="showcase",
                        preset_record=preset_record,
                        source_preset_id=link.get("source_preset_id"),
                        source_link_id=link.get("source_link_id"),
                        discovery_note=link.get("discovery_note"),
                    )
                )
    return handoff_targets


def _build_downstream_module_handoff_target_record(
    *,
    linked_session: Mapping[str, Any],
    linked_session_kind: str,
    preset_record: Mapping[str, Any],
    source_preset_id: str | None,
    source_link_id: str | None,
    discovery_note: str | None,
) -> dict[str, Any]:
    graph_payload_references = _require_mapping(
        preset_record.get("graph_payload_references", {}),
        field_name="query_preset.graph_payload_references",
    )
    primary_graph = _require_mapping(
        graph_payload_references.get("primary_graph", {}),
        field_name="query_preset.graph_payload_references.primary_graph",
    )
    return {
        "target_kind": "context_query_preset",
        "linked_session_kind": str(linked_session_kind),
        "source_bundle_id": str(linked_session["bundle_id"]),
        "source_metadata_path": str(linked_session["metadata_path"]),
        "source_preset_id": None if source_preset_id is None else str(source_preset_id),
        "source_link_id": None if source_link_id is None else str(source_link_id),
        "artifact_role_id": CONTEXT_VIEW_PAYLOAD_ROLE_ID,
        "target_preset_id": str(preset_record["preset_id"]),
        "target_graph_view_id": str(preset_record["primary_graph_view_id"]),
        "target_payload_path": str(primary_graph["payload_path"]),
        "target_query_profile_id": str(preset_record["query_profile_id"]),
        "discovery_note": None if discovery_note is None else str(discovery_note),
    }


def _apply_downstream_module_handoffs_to_preset_payload(
    *,
    payload: Mapping[str, Any],
    handoff_targets: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    result = copy.deepcopy(dict(payload))
    for graph_key in ("overview_graph", "focused_subgraph"):
        if isinstance(result.get(graph_key), Mapping):
            result[graph_key] = _apply_downstream_module_handoffs_to_graph_view(
                result[graph_key],
                handoff_targets=handoff_targets,
            )
    return result


def _apply_downstream_module_handoffs_to_context_record(
    record: Mapping[str, Any],
    *,
    handoff_targets: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    result = copy.deepcopy(dict(record))
    result["downstream_module_records"] = _apply_handoff_targets_to_module_records(
        result.get("downstream_module_records", []),
        handoff_targets=handoff_targets,
    )
    return result


def _apply_downstream_module_handoffs_to_graph_view(
    graph_view: Mapping[str, Any],
    *,
    handoff_targets: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    result = copy.deepcopy(dict(graph_view))
    result["downstream_module_records"] = _apply_handoff_targets_to_module_records(
        result.get("downstream_module_records", []),
        handoff_targets=handoff_targets,
    )
    return result


def _apply_handoff_targets_to_module_records(
    payload: Any,
    *,
    handoff_targets: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        return []
    normalized_handoffs = [copy.deepcopy(dict(item)) for item in handoff_targets]
    result: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        record = copy.deepcopy(dict(item))
        record["handoff_targets"] = normalized_handoffs
        result.append(record)
    return result


def _catalog_item_by_id(
    catalog: Sequence[Mapping[str, Any]],
    *,
    key_name: str,
    identifier: str,
) -> dict[str, Any]:
    for item in catalog:
        if str(item[key_name]) == str(identifier):
            return copy.deepcopy(dict(item))
    raise ValueError(f"Could not find {key_name}={identifier!r} in contract catalog.")


def _normalize_optional_identifier(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _normalize_identifier(value, field_name=field_name)


def _normalize_optional_string(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _normalize_nonempty_string(value, field_name=field_name)


def _require_mapping(payload: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return copy.deepcopy(dict(payload))


__all__ = [
    "DASHBOARD_HANDOFF_PRESET_ID",
    "DEFAULT_CONTEXT_QUERY_PRESET_LIBRARY_ID",
    "DOWNSTREAM_HALO_PRESET_ID",
    "OVERVIEW_CONTEXT_PRESET_ID",
    "PATHWAY_FOCUS_PRESET_ID",
    "SHOWCASE_HANDOFF_PRESET_ID",
    "SUPPORTED_CONTEXT_QUERY_PRESET_IDS",
    "UPSTREAM_HALO_PRESET_ID",
    "discover_showcase_handoff_links",
    "execute_whole_brain_context_session_queries",
    "hydrate_whole_brain_context_query_preset_library",
]
