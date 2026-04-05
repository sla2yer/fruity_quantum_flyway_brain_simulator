from __future__ import annotations

import base64
import copy
import csv
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .coupling_contract import discover_edge_coupling_bundle_paths
from .dashboard_session_contract import CIRCUIT_PANE_ID, SCENE_PANE_ID
from .geometry_contract import (
    PATCH_GRAPH_KEY,
    RAW_SKELETON_KEY,
    SIMPLIFIED_MESH_KEY,
    SURFACE_GRAPH_KEY,
    discover_operator_bundle_paths,
    load_geometry_manifest_records,
)
from .hybrid_morphology_contract import (
    POINT_NEURON_CLASS,
    SKELETON_NEURON_CLASS,
    SURFACE_NEURON_CLASS,
)
from .retinal_bundle import load_recorded_retinal_bundle
from .retinal_contract import (
    FRAME_ARCHIVE_KEY,
    RETINAL_INPUT_BUNDLE_CONTRACT_VERSION,
    load_retinal_bundle_metadata,
)
from .stimulus_bundle import load_recorded_stimulus_bundle
from .stimulus_contract import (
    FRAME_CACHE_KEY,
    STIMULUS_BUNDLE_CONTRACT_VERSION,
    load_stimulus_bundle_metadata,
)
from .whole_brain_context_contract import (
    ACTIVE_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
    ACTIVE_SELECTED_NODE_ROLE_ID,
    ACTIVE_TO_CONTEXT_EDGE_ROLE_ID,
    CONTEXT_INTERNAL_EDGE_ROLE_ID,
    CONTEXT_ONLY_NODE_ROLE_ID,
    CONTEXT_QUERY_CATALOG_ARTIFACT_ID,
    CONTEXT_TO_ACTIVE_EDGE_ROLE_ID,
    CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID,
    CONTEXT_VIEW_STATE_ARTIFACT_ID,
    DOWNSTREAM_MODULE_SUMMARY_EDGE_ROLE_ID,
    METADATA_JSON_KEY as WHOLE_BRAIN_CONTEXT_METADATA_JSON_KEY,
    PATHWAY_HIGHLIGHT_EDGE_ROLE_ID,
    CONTEXT_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
    discover_whole_brain_context_session_bundle_paths,
    load_whole_brain_context_session_metadata,
)


DASHBOARD_SCENE_CONTEXT_VERSION = "dashboard_scene_context.v1"
DASHBOARD_CIRCUIT_CONTEXT_VERSION = "dashboard_circuit_context.v1"
DASHBOARD_LINKED_NEURON_PAYLOAD_VERSION = "dashboard_linked_neuron_payload.v1"
DASHBOARD_WHOLE_BRAIN_CONTEXT_VERSION = "dashboard_whole_brain_context.v1"

SCENE_FRAME_UINT8_ENCODING = "base64_uint8_grayscale_row_major"
DEFAULT_SCENE_MAX_RENDER_DIMENSION = 48
DEFAULT_OVERVIEW_CONTEXT_MAX_RENDER_NODE_COUNT = 28
DEFAULT_OVERVIEW_CONTEXT_MAX_RENDER_EDGE_COUNT = 36
DEFAULT_FOCUSED_CONTEXT_MAX_RENDER_NODE_COUNT = 18
DEFAULT_FOCUSED_CONTEXT_MAX_RENDER_EDGE_COUNT = 24

OVERVIEW_CONTEXT_PRESET_ID = "overview_context"
PATHWAY_FOCUS_PRESET_ID = "pathway_focus"


def resolve_dashboard_scene_context(
    *,
    source_kind: str,
    metadata_path: str | Path,
    selected_condition_ids: Sequence[str],
    max_render_dimension: int = DEFAULT_SCENE_MAX_RENDER_DIMENSION,
) -> dict[str, Any]:
    resolved_path = Path(metadata_path).resolve()
    if str(source_kind) == "stimulus_bundle":
        return _resolve_stimulus_scene_context(
            metadata_path=resolved_path,
            selected_condition_ids=selected_condition_ids,
            max_render_dimension=max_render_dimension,
        )
    if str(source_kind) == "retinal_bundle":
        return _resolve_retinal_scene_context(
            metadata_path=resolved_path,
            selected_condition_ids=selected_condition_ids,
            max_render_dimension=max_render_dimension,
        )
    raise ValueError(f"Unsupported dashboard scene source_kind {source_kind!r}.")


def normalize_dashboard_circuit_context(
    *,
    geometry_manifest_path: str | Path,
    selected_root_ids: Sequence[int],
    local_synapse_registry_path: str | Path,
) -> dict[str, Any]:
    manifest_path = Path(geometry_manifest_path).resolve()
    synapse_path = Path(local_synapse_registry_path).resolve()
    manifest_records = load_geometry_manifest_records(manifest_path)
    normalized_selected_root_ids = sorted({int(root_id) for root_id in selected_root_ids})
    missing_roots = [
        int(root_id)
        for root_id in normalized_selected_root_ids
        if str(int(root_id)) not in manifest_records
    ]
    if missing_roots:
        raise ValueError(
            "geometry_manifest is missing selected roots required for the dashboard session: "
            f"{missing_roots!r}."
        )

    selected_root_catalog: list[dict[str, Any]] = []
    edge_bundle_records: dict[tuple[int, int], dict[str, Any]] = {}
    for root_id in normalized_selected_root_ids:
        manifest_record = _require_mapping(
            manifest_records[str(root_id)],
            field_name=f"geometry_manifest[{root_id}]",
        )
        selected_root_record = _build_selected_root_record(root_id, manifest_record)
        selected_root_catalog.append(selected_root_record)
        for edge_bundle in selected_root_record["edge_bundle_paths"]:
            edge_key = (
                int(edge_bundle["pre_root_id"]),
                int(edge_bundle["post_root_id"]),
            )
            if edge_key not in edge_bundle_records:
                edge_bundle_records[edge_key] = copy.deepcopy(edge_bundle)
                continue
            existing = edge_bundle_records[edge_key]
            existing["referenced_by_root_ids"] = sorted(
                {
                    *existing["referenced_by_root_ids"],
                    *edge_bundle["referenced_by_root_ids"],
                }
            )
            existing["exists"] = bool(existing["exists"]) or bool(edge_bundle["exists"])
            existing["status"] = (
                existing["status"]
                if str(existing["status"]) == "ready"
                else str(edge_bundle["status"])
            )

    synapse_rows = _load_dashboard_synapse_registry(synapse_path)
    connectivity_context = _build_connectivity_context(
        synapse_rows=synapse_rows,
        selected_root_ids=normalized_selected_root_ids,
        manifest_records=manifest_records,
        edge_bundle_records=edge_bundle_records,
    )

    connectivity_summary_by_root: dict[int, dict[str, Any]] = {}
    for node in connectivity_context["node_catalog"]:
        connectivity_summary_by_root[int(node["root_id"])] = {
            "incoming_synapse_count": int(node["incoming_synapse_count"]),
            "outgoing_synapse_count": int(node["outgoing_synapse_count"]),
            "incident_synapse_count": int(node["incident_synapse_count"]),
            "neighbor_root_ids": list(node["neighbor_root_ids"]),
            "context_root_ids": list(node["context_root_ids"]),
        }

    for root_record in selected_root_catalog:
        root_id = int(root_record["root_id"])
        root_record["connectivity_summary"] = copy.deepcopy(
            connectivity_summary_by_root.get(
                root_id,
                {
                    "incoming_synapse_count": 0,
                    "outgoing_synapse_count": 0,
                    "incident_synapse_count": 0,
                    "neighbor_root_ids": [],
                    "context_root_ids": [],
                },
            )
        )

    return {
        "pane_id": CIRCUIT_PANE_ID,
        "context_version": DASHBOARD_CIRCUIT_CONTEXT_VERSION,
        "geometry_manifest_path": str(manifest_path),
        "local_synapse_registry_path": str(synapse_path),
        "selected_root_ids": normalized_selected_root_ids,
        "root_catalog": selected_root_catalog,
        "connectivity_context": connectivity_context,
        "whole_brain_context": _absent_dashboard_whole_brain_context(
            selected_root_ids=normalized_selected_root_ids
        ),
    }


def build_dashboard_linked_neuron_payload(
    *,
    root_id: int,
    source_layer: str,
    source_item_id: str | None = None,
    selection_enabled: bool = True,
) -> dict[str, Any]:
    normalized_root_id = int(root_id)
    item_id = str(normalized_root_id) if source_item_id is None else str(source_item_id)
    payload: dict[str, Any] = {
        "payload_version": DASHBOARD_LINKED_NEURON_PAYLOAD_VERSION,
        "root_id": normalized_root_id,
        "source_pane_id": CIRCUIT_PANE_ID,
        "source_layer": str(source_layer),
        "source_item_id": item_id,
        "selection_enabled": bool(selection_enabled),
        "hover": {
            "hovered_neuron_id": normalized_root_id,
            "source_pane_id": CIRCUIT_PANE_ID,
            "source_layer": str(source_layer),
            "source_item_id": item_id,
        },
    }
    if selection_enabled:
        payload["select"] = {
            "selected_neuron_id": normalized_root_id,
            "source_pane_id": CIRCUIT_PANE_ID,
            "source_layer": str(source_layer),
            "source_item_id": item_id,
        }
    else:
        payload["select"] = None
    return payload


def load_dashboard_whole_brain_context(
    *,
    metadata_path: str | Path,
    selected_root_ids: Sequence[int],
    max_overview_node_count: int = DEFAULT_OVERVIEW_CONTEXT_MAX_RENDER_NODE_COUNT,
    max_overview_edge_count: int = DEFAULT_OVERVIEW_CONTEXT_MAX_RENDER_EDGE_COUNT,
    max_focused_node_count: int = DEFAULT_FOCUSED_CONTEXT_MAX_RENDER_NODE_COUNT,
    max_focused_edge_count: int = DEFAULT_FOCUSED_CONTEXT_MAX_RENDER_EDGE_COUNT,
) -> dict[str, Any]:
    resolved_metadata_path = Path(metadata_path).resolve()
    normalized_selected_root_ids = sorted({int(root_id) for root_id in selected_root_ids})
    result = _absent_dashboard_whole_brain_context(
        selected_root_ids=normalized_selected_root_ids
    )
    result["availability"] = "unavailable"
    result["artifact_paths"]["metadata_path"] = str(resolved_metadata_path)
    try:
        metadata = load_whole_brain_context_session_metadata(resolved_metadata_path)
    except Exception as exc:
        result["reason"] = (
            "Packaged whole-brain context metadata could not be loaded: "
            f"{exc}"
        )
        result["summary"]["status"] = "metadata_unavailable"
        return result

    bundle_paths = discover_whole_brain_context_session_bundle_paths(metadata)
    result["bundle_id"] = str(metadata["bundle_id"])
    result["artifact_paths"] = {
        "metadata_path": str(bundle_paths[WHOLE_BRAIN_CONTEXT_METADATA_JSON_KEY].resolve()),
        "context_view_payload_path": str(
            bundle_paths[CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID].resolve()
        ),
        "context_query_catalog_path": str(
            bundle_paths[CONTEXT_QUERY_CATALOG_ARTIFACT_ID].resolve()
        ),
        "context_view_state_path": str(
            bundle_paths[CONTEXT_VIEW_STATE_ARTIFACT_ID].resolve()
        ),
    }
    result["artifact_statuses"] = _whole_brain_context_artifact_statuses(metadata)
    result["summary"] = _whole_brain_context_session_summary(
        metadata=metadata,
        dashboard_selected_root_ids=normalized_selected_root_ids,
    )

    payload, payload_error = _load_optional_json_mapping(
        bundle_paths[CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID]
    )
    query_catalog, _query_catalog_error = _load_optional_json_mapping(
        bundle_paths[CONTEXT_QUERY_CATALOG_ARTIFACT_ID]
    )
    view_state, _view_state_error = _load_optional_json_mapping(
        bundle_paths[CONTEXT_VIEW_STATE_ARTIFACT_ID]
    )

    result["linked_sessions"] = copy.deepcopy(
        _require_mapping(payload.get("linked_sessions", {}), field_name="context_payload.linked_sessions")
        if payload is not None and isinstance(payload.get("linked_sessions", {}), Mapping)
        else (
            {
                "dashboard": copy.deepcopy(
                    dict(_require_mapping(view_state.get("linked_dashboard", {}), field_name="context_view_state.linked_dashboard"))
                )
                if view_state is not None and isinstance(view_state.get("linked_dashboard", {}), Mapping)
                else {},
                "showcase": copy.deepcopy(
                    dict(_require_mapping(view_state.get("linked_showcase", {}), field_name="context_view_state.linked_showcase"))
                )
                if view_state is not None and isinstance(view_state.get("linked_showcase", {}), Mapping)
                else {},
            }
        )
    )

    preset_payloads = _context_preset_payloads(
        payload=payload,
        view_state=view_state,
    )
    result["preset_catalog"] = _dashboard_context_preset_catalog(
        preset_payloads=preset_payloads,
        query_catalog=query_catalog,
    )
    result["available_preset_ids"] = [
        str(item["preset_id"]) for item in result["preset_catalog"]
    ]
    result["active_preset_id"] = _context_active_preset_id(
        payload=payload,
        view_state=view_state,
        available_preset_ids=result["available_preset_ids"],
    )

    if payload is None:
        result["reason"] = (
            "Packaged whole-brain context payload is unavailable: "
            f"{payload_error or 'context_view_payload.json is missing or unreadable.'}"
        )
        result["summary"]["status"] = "payload_unavailable"
        result["representation_catalog"] = [
            _context_representation_stub(
                representation_id="overview",
                display_name="Whole-Brain Overview",
                description="Budgeted Milestone 17 overview graph around the active subset.",
                reason=result["reason"],
            ),
            _context_representation_stub(
                representation_id="focused",
                display_name="Focused Context",
                description="Path-preserving focused extract around the active subset.",
                reason=result["reason"],
            ),
        ]
        return result

    selection = _require_mapping(payload.get("selection", {}), field_name="context_payload.selection")
    context_selected_root_ids = sorted(
        {int(root_id) for root_id in selection.get("selected_root_ids", [])}
    )
    result["summary"]["context_selected_root_ids"] = list(context_selected_root_ids)
    if context_selected_root_ids:
        if context_selected_root_ids == normalized_selected_root_ids:
            result["selection_alignment"] = {
                "status": "matched",
                "dashboard_selected_root_ids": list(normalized_selected_root_ids),
                "context_selected_root_ids": list(context_selected_root_ids),
                "reason": None,
            }
        else:
            mismatch_reason = (
                "Packaged whole-brain context selected_root_ids do not match the active dashboard subset."
            )
            result["selection_alignment"] = {
                "status": "mismatch",
                "dashboard_selected_root_ids": list(normalized_selected_root_ids),
                "context_selected_root_ids": list(context_selected_root_ids),
                "reason": mismatch_reason,
            }
            result["reason"] = mismatch_reason
            result["summary"]["status"] = "selection_mismatch"
            result["representation_catalog"] = [
                _context_representation_stub(
                    representation_id="overview",
                    display_name="Whole-Brain Overview",
                    description="Budgeted Milestone 17 overview graph around the active subset.",
                    reason=mismatch_reason,
                ),
                _context_representation_stub(
                    representation_id="focused",
                    display_name="Focused Context",
                    description="Path-preserving focused extract around the active subset.",
                    reason=mismatch_reason,
                ),
            ]
            return result

    overview_preset_id = _preferred_preset_id(
        preset_payloads=preset_payloads,
        preferred_ids=[
            OVERVIEW_CONTEXT_PRESET_ID,
            result["active_preset_id"],
        ],
        graph_view_id="overview_graph",
    )
    focused_preset_id = _preferred_preset_id(
        preset_payloads=preset_payloads,
        preferred_ids=[
            PATHWAY_FOCUS_PRESET_ID,
            result["active_preset_id"],
            overview_preset_id,
        ],
        graph_view_id="focused_subgraph",
    )

    overview_representation = _build_dashboard_context_representation(
        representation_id="overview",
        display_name="Whole-Brain Overview",
        description="Budgeted Milestone 17 overview graph around the active subset.",
        preset_id=overview_preset_id,
        graph_view_id="overview_graph",
        preset_payloads=preset_payloads,
        max_node_count=max_overview_node_count,
        max_edge_count=max_overview_edge_count,
    )
    focused_representation = _build_dashboard_context_representation(
        representation_id="focused",
        display_name="Focused Context",
        description="Path-preserving focused extract around the active subset.",
        preset_id=focused_preset_id,
        graph_view_id="focused_subgraph",
        preset_payloads=preset_payloads,
        max_node_count=max_focused_node_count,
        max_edge_count=max_focused_edge_count,
    )
    result["representation_catalog"] = [
        overview_representation,
        focused_representation,
    ]
    available_representation_ids = [
        str(item["representation_id"])
        for item in result["representation_catalog"]
        if str(item["availability"]) in {"available", "summary_only"}
    ]
    result["available_representation_ids"] = available_representation_ids
    result["active_representation_id"] = (
        available_representation_ids[0] if available_representation_ids else "overview"
    )
    availability_values = {
        str(item["availability"]) for item in result["representation_catalog"]
    }
    if "available" in availability_values and len(availability_values) == 1:
        result["availability"] = "available"
        result["reason"] = None
        result["summary"]["status"] = "available"
    elif "available" in availability_values or "summary_only" in availability_values:
        result["availability"] = "partial"
        result["reason"] = (
            "One or more whole-brain context representations were reduced to summary-only mode."
        )
        result["summary"]["status"] = "partial"
    else:
        result["availability"] = "unavailable"
        result["reason"] = "No whole-brain context representation is graph-renderable."
        result["summary"]["status"] = "unavailable"
    return result


def _absent_dashboard_whole_brain_context(
    *,
    selected_root_ids: Sequence[int],
) -> dict[str, Any]:
    return {
        "context_version": DASHBOARD_WHOLE_BRAIN_CONTEXT_VERSION,
        "availability": "absent",
        "reason": "No packaged whole-brain context session is linked to this dashboard package.",
        "bundle_id": None,
        "artifact_paths": {
            "metadata_path": None,
            "context_view_payload_path": None,
            "context_query_catalog_path": None,
            "context_view_state_path": None,
        },
        "artifact_statuses": {},
        "summary": {
            "status": "absent",
            "dashboard_selected_root_ids": [int(root_id) for root_id in selected_root_ids],
            "representative_context_root_count": 0,
            "representative_context_node_role_counts": {},
        },
        "selection_alignment": {
            "status": "absent",
            "dashboard_selected_root_ids": [int(root_id) for root_id in selected_root_ids],
            "context_selected_root_ids": [],
            "reason": "No packaged whole-brain context session is linked to this dashboard package.",
        },
        "linked_sessions": {},
        "preset_catalog": [],
        "available_preset_ids": [],
        "active_preset_id": None,
        "active_representation_id": "overview",
        "available_representation_ids": [],
        "representation_catalog": [
            _context_representation_stub(
                representation_id="overview",
                display_name="Whole-Brain Overview",
                description="Budgeted Milestone 17 overview graph around the active subset.",
                reason="No packaged whole-brain context session is linked to this dashboard package.",
            ),
            _context_representation_stub(
                representation_id="focused",
                display_name="Focused Context",
                description="Path-preserving focused extract around the active subset.",
                reason="No packaged whole-brain context session is linked to this dashboard package.",
            ),
        ],
    }


def _context_representation_stub(
    *,
    representation_id: str,
    display_name: str,
    description: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "representation_id": str(representation_id),
        "display_name": str(display_name),
        "description": str(description),
        "availability": "unavailable",
        "render_mode": "unavailable",
        "reason": str(reason),
        "source_preset_id": None,
        "source_query_profile_id": None,
        "source_query_family": None,
        "source_graph_view_id": None,
        "summary": {
            "distinct_root_count": 0,
            "node_count": 0,
            "edge_count": 0,
            "active_root_count": 0,
            "context_root_count": 0,
            "pathway_highlight_root_count": 0,
            "downstream_module_count": 0,
            "node_style_counts": {},
            "edge_style_counts": {},
        },
        "node_catalog": [],
        "edge_catalog": [],
        "pathway_catalog": [],
        "downstream_module_catalog": [],
    }


def _whole_brain_context_artifact_statuses(
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    artifacts = _require_mapping(
        metadata.get("artifacts", {}),
        field_name="whole_brain_context_metadata.artifacts",
    )
    result: dict[str, Any] = {}
    for artifact_id in (
        WHOLE_BRAIN_CONTEXT_METADATA_JSON_KEY,
        CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID,
        CONTEXT_QUERY_CATALOG_ARTIFACT_ID,
        CONTEXT_VIEW_STATE_ARTIFACT_ID,
    ):
        artifact = _require_mapping(
            artifacts.get(artifact_id, {}),
            field_name=f"whole_brain_context_metadata.artifacts[{artifact_id!r}]",
        )
        result[str(artifact_id)] = {
            "status": str(artifact.get("status", "unknown")),
            "path": str(artifact.get("path", "")),
            "format": artifact.get("format"),
            "artifact_scope": artifact.get("artifact_scope"),
        }
    return result


def _whole_brain_context_session_summary(
    *,
    metadata: Mapping[str, Any],
    dashboard_selected_root_ids: Sequence[int],
) -> dict[str, Any]:
    representative_context = _require_mapping(
        metadata.get("representative_context", {}),
        field_name="whole_brain_context_metadata.representative_context",
    )
    node_records = representative_context.get("node_records", [])
    node_role_counts = Counter(
        str(_require_mapping(item, field_name="representative_context.node_records[]")["node_role_id"])
        for item in node_records
        if isinstance(item, Mapping)
    )
    distinct_root_ids = {
        int(_require_mapping(item, field_name="representative_context.node_records[]")["root_id"])
        for item in node_records
        if isinstance(item, Mapping)
    }
    return {
        "status": "metadata_available",
        "dashboard_selected_root_ids": [int(root_id) for root_id in dashboard_selected_root_ids],
        "representative_context_root_count": len(distinct_root_ids),
        "representative_context_node_role_counts": dict(sorted(node_role_counts.items())),
        "query_profile_id": (
            _require_mapping(metadata.get("query_state", {}), field_name="whole_brain_context_metadata.query_state").get("query_profile_id")
            if isinstance(metadata.get("query_state", {}), Mapping)
            else None
        ),
    }


def _load_optional_json_mapping(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    resolved_path = Path(path).resolve()
    if not resolved_path.exists():
        return (None, f"{resolved_path.name} is missing.")
    try:
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return (None, f"{resolved_path.name} could not be parsed: {exc}")
    if not isinstance(payload, Mapping):
        return (None, f"{resolved_path.name} must contain a JSON object.")
    return (copy.deepcopy(dict(payload)), None)


def _context_active_preset_id(
    *,
    payload: Mapping[str, Any] | None,
    view_state: Mapping[str, Any] | None,
    available_preset_ids: Sequence[str],
) -> str | None:
    if payload is not None and payload.get("active_preset_id") is not None:
        return str(payload["active_preset_id"])
    if view_state is not None and view_state.get("active_preset_id") is not None:
        return str(view_state["active_preset_id"])
    return None if not available_preset_ids else str(available_preset_ids[0])


def _context_preset_payloads(
    *,
    payload: Mapping[str, Any] | None,
    view_state: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if payload is not None and isinstance(payload.get("query_preset_payloads", {}), Mapping):
        return {
            str(preset_id): copy.deepcopy(dict(preset_payload))
            for preset_id, preset_payload in payload["query_preset_payloads"].items()
            if isinstance(preset_payload, Mapping)
        }
    if payload is not None and isinstance(payload.get("query_execution", {}), Mapping):
        active_preset_id = _context_active_preset_id(
            payload=payload,
            view_state=view_state,
            available_preset_ids=[],
        ) or OVERVIEW_CONTEXT_PRESET_ID
        query_execution = _require_mapping(
            payload.get("query_execution", {}),
            field_name="context_payload.query_execution",
        )
        return {
            str(active_preset_id): {
                "preset_id": str(active_preset_id),
                "display_name": "Packaged Whole-Brain Context",
                "query_profile_id": query_execution.get("query_profile_id"),
                "query_family": query_execution.get("query_family"),
                "execution_summary": copy.deepcopy(
                    dict(_require_mapping(query_execution.get("execution_summary", {}), field_name="context_payload.query_execution.execution_summary"))
                ),
                "overview_graph": copy.deepcopy(
                    dict(_require_mapping(query_execution.get("overview_graph", {}), field_name="context_payload.query_execution.overview_graph"))
                ),
                "focused_subgraph": copy.deepcopy(
                    dict(_require_mapping(query_execution.get("focused_subgraph", {}), field_name="context_payload.query_execution.focused_subgraph"))
                ),
                "pathway_highlights": [
                    copy.deepcopy(dict(item))
                    for item in query_execution.get("pathway_highlights", [])
                    if isinstance(item, Mapping)
                ],
            }
        }
    return {}


def _dashboard_context_preset_catalog(
    *,
    preset_payloads: Mapping[str, Mapping[str, Any]],
    query_catalog: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    records_by_id: dict[str, dict[str, Any]] = {}
    if query_catalog is not None:
        for item in query_catalog.get("available_query_presets", []):
            if not isinstance(item, Mapping):
                continue
            preset_id = str(item.get("preset_id", "")).strip()
            if not preset_id:
                continue
            records_by_id[preset_id] = {
                "preset_id": preset_id,
                "display_name": str(item.get("display_name", preset_id)),
                "description": str(item.get("description", "")),
                "query_profile_id": item.get("query_profile_id"),
                "primary_graph_view_id": item.get("primary_graph_view_id"),
                "availability": str(item.get("availability", "available")),
            }
    for preset_id, payload in preset_payloads.items():
        existing = records_by_id.setdefault(
            str(preset_id),
            {
                "preset_id": str(preset_id),
                "display_name": str(payload.get("display_name", preset_id)),
                "description": "",
                "query_profile_id": payload.get("query_profile_id"),
                "primary_graph_view_id": "overview_graph",
                "availability": "available",
            },
        )
        existing["display_name"] = str(
            existing.get("display_name")
            or payload.get("display_name")
            or preset_id
        )
        existing["query_profile_id"] = (
            existing.get("query_profile_id") or payload.get("query_profile_id")
        )
    return [
        records_by_id[preset_id]
        for preset_id in sorted(records_by_id)
    ]


def _preferred_preset_id(
    *,
    preset_payloads: Mapping[str, Mapping[str, Any]],
    preferred_ids: Sequence[str | None],
    graph_view_id: str,
) -> str | None:
    for preferred_id in preferred_ids:
        if preferred_id is None:
            continue
        payload = preset_payloads.get(str(preferred_id))
        if payload is None:
            continue
        graph_view = payload.get(graph_view_id)
        if isinstance(graph_view, Mapping):
            summary = graph_view.get("summary", {})
            if isinstance(summary, Mapping) and int(summary.get("node_record_count", 0)) >= 1:
                return str(preferred_id)
    for preset_id in sorted(preset_payloads):
        graph_view = preset_payloads[preset_id].get(graph_view_id)
        if isinstance(graph_view, Mapping):
            summary = graph_view.get("summary", {})
            if isinstance(summary, Mapping) and int(summary.get("node_record_count", 0)) >= 1:
                return str(preset_id)
    return None


def _build_dashboard_context_representation(
    *,
    representation_id: str,
    display_name: str,
    description: str,
    preset_id: str | None,
    graph_view_id: str,
    preset_payloads: Mapping[str, Mapping[str, Any]],
    max_node_count: int,
    max_edge_count: int,
) -> dict[str, Any]:
    if preset_id is None or preset_id not in preset_payloads:
        return _context_representation_stub(
            representation_id=representation_id,
            display_name=display_name,
            description=description,
            reason="The packaged whole-brain context session does not include the required preset.",
        )
    preset_payload = _require_mapping(
        preset_payloads[preset_id],
        field_name=f"query_preset_payloads[{preset_id!r}]",
    )
    graph_view = _require_mapping(
        preset_payload.get(graph_view_id, {}),
        field_name=f"query_preset_payloads[{preset_id!r}].{graph_view_id}",
    )
    emphasize_pathway_highlight = str(representation_id) == "focused"
    collapsed_nodes = _collapse_context_nodes(
        graph_view.get("node_records", []),
        emphasize_pathway_highlight=emphasize_pathway_highlight,
    )
    collapsed_edges = _collapse_context_edges(
        graph_view.get("edge_records", []),
        emphasize_pathway_highlight=emphasize_pathway_highlight,
    )
    _apply_context_incident_stats(
        nodes=collapsed_nodes,
        edges=collapsed_edges,
    )
    downstream_module_catalog = _normalize_downstream_module_catalog(
        graph_view.get("downstream_module_records", [])
    )
    pathway_catalog = _normalize_pathway_catalog(
        preset_payload.get("pathway_highlights", [])
    )
    overlay_workflow_catalog = _normalize_context_overlay_workflow_catalog(
        graph_view.get("overlay_workflow_catalog", [])
    )
    metadata_facet_group_catalog = _normalize_context_metadata_facet_group_catalog(
        graph_view.get("metadata_facet_group_catalog", [])
    )
    metadata_facet_filter_catalog = _normalize_context_metadata_facet_filter_catalog(
        graph_view.get("metadata_facet_filter_catalog", [])
    )
    pathway_explanation_catalog = _normalize_context_pathway_explanation_catalog(
        graph_view.get("pathway_explanation_catalog", [])
    )
    interaction_flow_catalog = _normalize_context_interaction_flow_catalog(
        graph_view.get("interaction_flow_catalog", [])
    )
    reviewer_summary_cards = _normalize_context_reviewer_summary_cards(
        graph_view.get("reviewer_summary_cards", [])
    )
    summary = {
        "distinct_root_count": len(collapsed_nodes),
        "node_count": len(collapsed_nodes),
        "edge_count": len(collapsed_edges),
        "active_root_count": sum(
            1 for item in collapsed_nodes if bool(item["selection_enabled"])
        ),
        "context_root_count": sum(
            1 for item in collapsed_nodes if not bool(item["selection_enabled"])
        ),
        "pathway_highlight_root_count": sum(
            1 for item in collapsed_nodes if bool(item["pathway_highlight"])
        ),
        "downstream_module_count": len(downstream_module_catalog),
        "node_style_counts": dict(
            sorted(Counter(str(item["style_variant"]) for item in collapsed_nodes).items())
        ),
        "edge_style_counts": dict(
            sorted(Counter(str(item["style_variant"]) for item in collapsed_edges).items())
        ),
        "overlay_workflow_count": len(overlay_workflow_catalog),
        "metadata_facet_group_count": len(metadata_facet_group_catalog),
        "metadata_facet_filter_count": len(metadata_facet_filter_catalog),
        "pathway_explanation_mode_count": len(pathway_explanation_catalog),
        "interaction_flow_count": len(interaction_flow_catalog),
    }
    record = {
        "representation_id": str(representation_id),
        "display_name": str(display_name),
        "description": str(description),
        "availability": "available",
        "render_mode": "graph",
        "reason": None,
        "source_preset_id": str(preset_id),
        "source_query_profile_id": preset_payload.get("query_profile_id"),
        "source_query_family": preset_payload.get("query_family"),
        "source_graph_view_id": str(graph_view_id),
        "summary": summary,
        "node_catalog": collapsed_nodes,
        "edge_catalog": collapsed_edges,
        "pathway_catalog": pathway_catalog,
        "downstream_module_catalog": downstream_module_catalog,
        "reviewer_caption": str(graph_view.get("reviewer_caption") or description),
        "overlay_workflow_catalog": overlay_workflow_catalog,
        "metadata_facet_group_catalog": metadata_facet_group_catalog,
        "metadata_facet_filter_catalog": metadata_facet_filter_catalog,
        "pathway_explanation_catalog": pathway_explanation_catalog,
        "interaction_flow_catalog": interaction_flow_catalog,
        "reviewer_summary_cards": reviewer_summary_cards,
    }
    if len(collapsed_nodes) == 0:
        record["availability"] = "unavailable"
        record["render_mode"] = "unavailable"
        record["reason"] = "The packaged representation does not contain any graph nodes."
        return record
    if len(collapsed_nodes) > int(max_node_count) or len(collapsed_edges) > int(max_edge_count):
        record["availability"] = "summary_only"
        record["render_mode"] = "summary_only"
        record["reason"] = (
            "The packaged representation exceeds the dashboard render budget and was reduced to summary cards."
        )
        record["node_catalog"] = []
        record["edge_catalog"] = []
    return record


def _collapse_context_nodes(
    payload: Any,
    *,
    emphasize_pathway_highlight: bool,
) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence):
        return []
    grouped: dict[int, dict[str, Any]] = {}
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        record = copy.deepcopy(dict(item))
        root_id = int(record["root_id"])
        entry = grouped.setdefault(
            root_id,
            {"base_record": None, "highlight_record": None, "source_records": []},
        )
        entry["source_records"].append(record)
        node_role_id = str(record.get("node_role_id", ""))
        if node_role_id in {
            ACTIVE_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
            CONTEXT_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
        }:
            entry["highlight_record"] = record
        elif entry["base_record"] is None:
            entry["base_record"] = record
    collapsed: list[dict[str, Any]] = []
    for root_id, entry in grouped.items():
        base_record = entry["base_record"] or entry["highlight_record"]
        if base_record is None:
            continue
        highlight_record = entry["highlight_record"]
        metadata_facet_values = {}
        for record in (base_record, highlight_record):
            if record is None:
                continue
            if isinstance(record.get("metadata_facet_values", {}), Mapping):
                metadata_facet_values.update(dict(record["metadata_facet_values"]))
        anchor_record = None
        for record in (base_record, highlight_record):
            if record is None:
                continue
            if isinstance(record.get("anchor_record"), Mapping):
                anchor_record = copy.deepcopy(dict(record["anchor_record"]))
                break
        selection_enabled = bool(base_record.get("is_active_selected"))
        pathway_highlight = highlight_record is not None
        style_variant = _context_node_style_variant(
            selection_enabled=selection_enabled,
            pathway_highlight=pathway_highlight,
            emphasize_pathway_highlight=emphasize_pathway_highlight,
        )
        collapsed.append(
            {
                "root_id": int(root_id),
                "display_label": str(base_record.get("display_label") or root_id),
                "context_layer_id": str(base_record.get("context_layer_id") or ""),
                "highlight_context_layer_id": (
                    None
                    if highlight_record is None
                    else str(highlight_record.get("context_layer_id") or "")
                ),
                "node_role_id": str(base_record.get("node_role_id") or ""),
                "source_node_role_ids": sorted(
                    {
                        str(record.get("node_role_id") or "")
                        for record in entry["source_records"]
                    }
                ),
                "style_variant": style_variant,
                "pathway_highlight": pathway_highlight,
                "selection_enabled": selection_enabled,
                "boundary_status": str(base_record.get("boundary_status") or ""),
                "nearest_active_hop_count": base_record.get("nearest_active_hop_count"),
                "directional_context": sorted(
                    {
                        str(value)
                        for record in entry["source_records"]
                        for value in record.get("directional_context", [])
                    }
                ),
                "overlay_ids": sorted(
                    {
                        str(value)
                        for record in entry["source_records"]
                        for value in record.get("overlay_ids", [])
                    }
                ),
                "cell_type": (
                    str(metadata_facet_values.get("cell_type"))
                    if metadata_facet_values.get("cell_type") is not None
                    else (
                        ""
                        if anchor_record is None
                        else str(anchor_record.get("cell_type") or "")
                    )
                ),
                "cell_class": (
                    str(metadata_facet_values.get("cell_class"))
                    if metadata_facet_values.get("cell_class") is not None
                    else (
                        ""
                        if anchor_record is None
                        else str(
                            anchor_record.get("project_role")
                            or anchor_record.get("super_class")
                            or ""
                        )
                    )
                ),
                "project_role": (
                    ""
                    if anchor_record is None
                    else str(anchor_record.get("project_role") or "")
                ),
                "morphology_class": (
                    ""
                    if anchor_record is None
                    else str(anchor_record.get("morphology_class") or "")
                ),
                "neuropil": (
                    "" if metadata_facet_values.get("neuropil") is None else str(metadata_facet_values.get("neuropil"))
                ),
                "side": (
                    "" if metadata_facet_values.get("side") is None else str(metadata_facet_values.get("side"))
                ),
                "nt_type": (
                    "" if metadata_facet_values.get("nt_type") is None else str(metadata_facet_values.get("nt_type"))
                ),
                "selection_boundary_status": (
                    "" if metadata_facet_values.get("selection_boundary_status") is None else str(metadata_facet_values.get("selection_boundary_status"))
                ),
                "pathway_relevance_status": (
                    ""
                    if metadata_facet_values.get("pathway_relevance_status") is None
                    else str(metadata_facet_values.get("pathway_relevance_status"))
                ),
                "metadata_facet_values": metadata_facet_values,
                "anchor_record": anchor_record,
                "subset_membership": (
                    "selected_subset" if selection_enabled else "whole_brain_context"
                ),
                "source_node_ids": sorted(
                    {
                        str(record.get("node_id") or "")
                        for record in entry["source_records"]
                    }
                ),
                "neighbor_root_ids": [],
                "context_root_ids": [],
                "incoming_synapse_count": 0,
                "outgoing_synapse_count": 0,
                "incident_synapse_count": 0,
                "linked_selection": build_dashboard_linked_neuron_payload(
                    root_id=int(root_id),
                    source_layer="whole_brain_context",
                    source_item_id=(
                        str(highlight_record.get("node_id"))
                        if highlight_record is not None
                        else str(base_record.get("node_id") or root_id)
                    ),
                    selection_enabled=selection_enabled,
                ),
            }
        )
    collapsed.sort(key=_context_node_sort_key)
    return collapsed


def _collapse_context_edges(
    payload: Any,
    *,
    emphasize_pathway_highlight: bool,
) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence):
        return []
    grouped: dict[tuple[int, int], dict[str, Any]] = {}
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        record = copy.deepcopy(dict(item))
        edge_key = (int(record["source_root_id"]), int(record["target_root_id"]))
        entry = grouped.setdefault(
            edge_key,
            {"base_record": None, "highlight_record": None, "source_records": []},
        )
        entry["source_records"].append(record)
        edge_role_id = str(record.get("edge_role_id") or "")
        if edge_role_id == PATHWAY_HIGHLIGHT_EDGE_ROLE_ID:
            entry["highlight_record"] = record
        elif entry["base_record"] is None:
            entry["base_record"] = record
    collapsed: list[dict[str, Any]] = []
    for (source_root_id, target_root_id), entry in grouped.items():
        base_record = entry["base_record"] or entry["highlight_record"]
        if base_record is None:
            continue
        highlight_record = entry["highlight_record"]
        style_variant = _context_edge_style_variant(
            base_edge_role_id=str(base_record.get("edge_role_id") or ""),
            highlighted=highlight_record is not None,
            emphasize_pathway_highlight=emphasize_pathway_highlight,
        )
        collapsed.append(
            {
                "source_root_id": int(source_root_id),
                "target_root_id": int(target_root_id),
                "edge_role_id": str(base_record.get("edge_role_id") or ""),
                "style_variant": style_variant,
                "highlighted": highlight_record is not None,
                "synapse_count": int(base_record.get("synapse_count", 0) or 0),
                "weight": float(base_record.get("weight", 0.0) or 0.0),
                "mean_confidence": _parse_optional_float(base_record.get("mean_confidence")),
                "overlay_ids": sorted(
                    {
                        str(value)
                        for record in entry["source_records"]
                        for value in record.get("overlay_ids", [])
                    }
                ),
                "directional_context": sorted(
                    {
                        str(value)
                        for record in entry["source_records"]
                        for value in record.get("directional_context", [])
                    }
                ),
                "dominant_neuropil": base_record.get("dominant_neuropil"),
                "dominant_nt_type": base_record.get("dominant_nt_type"),
                "source_edge_ids": sorted(
                    {
                        str(record.get("edge_id") or "")
                        for record in entry["source_records"]
                    }
                ),
            }
        )
    collapsed.sort(key=_context_edge_sort_key)
    return collapsed


def _normalize_downstream_module_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence):
        return []
    result: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        record = copy.deepcopy(dict(item))
        result.append(
            {
                "module_id": str(record.get("module_id") or ""),
                "display_name": str(record.get("display_name") or record.get("module_id") or ""),
                "downstream_module_role_id": str(record.get("downstream_module_role_id") or ""),
                "represented_root_ids": [
                    int(root_id) for root_id in record.get("represented_root_ids", [])
                ],
                "metadata_facet_values": copy.deepcopy(
                    dict(record.get("metadata_facet_values", {}))
                )
                if isinstance(record.get("metadata_facet_values", {}), Mapping)
                else {},
                "summary_labels": copy.deepcopy(
                    dict(record.get("summary_labels", {}))
                )
                if isinstance(record.get("summary_labels", {}), Mapping)
                else {},
                "lineage": copy.deepcopy(dict(record.get("lineage", {})))
                if isinstance(record.get("lineage", {}), Mapping)
                else {},
                "handoff_targets": [
                    copy.deepcopy(dict(item))
                    for item in record.get("handoff_targets", [])
                    if isinstance(item, Mapping)
                ],
            }
        )
    return result


def _normalize_pathway_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence):
        return []
    result: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        record = copy.deepcopy(dict(item))
        result.append(
            {
                "pathway_id": str(record.get("pathway_id") or ""),
                "direction": str(record.get("direction") or ""),
                "anchor_root_id": int(record.get("anchor_root_id", 0) or 0),
                "target_root_id": int(record.get("target_root_id", 0) or 0),
                "node_root_ids": [int(root_id) for root_id in record.get("node_root_ids", [])],
                "hop_count": int(record.get("hop_count", 0) or 0),
                "path_synapse_count": int(record.get("path_synapse_count", 0) or 0),
            }
        )
    return result


def _normalize_context_overlay_workflow_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence):
        return []
    result: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        result.append(
            {
                "overlay_workflow_id": str(item.get("overlay_workflow_id") or ""),
                "overlay_id": str(item.get("overlay_id") or ""),
                "display_name": str(item.get("display_name") or item.get("overlay_id") or ""),
                "availability": str(item.get("availability") or "unavailable"),
                "query_family": str(item.get("query_family") or ""),
                "matching_root_ids": [
                    int(root_id) for root_id in item.get("matching_root_ids", [])
                ],
                "visible_root_ids": [
                    int(root_id) for root_id in item.get("visible_root_ids", [])
                ],
                "matching_edge_pairs": [
                    [int(pair[0]), int(pair[1])]
                    for pair in item.get("matching_edge_pairs", [])
                    if isinstance(pair, Sequence) and len(pair) == 2
                ],
                "matching_module_ids": [
                    str(module_id) for module_id in item.get("matching_module_ids", [])
                ],
                "matching_active_root_count": int(
                    item.get("matching_active_root_count", 0) or 0
                ),
                "matching_context_root_count": int(
                    item.get("matching_context_root_count", 0) or 0
                ),
                "caption": str(item.get("caption") or ""),
                "boundary_note": str(item.get("boundary_note") or ""),
            }
        )
    return result


def _normalize_context_metadata_facet_group_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence):
        return []
    result: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        result.append(
            {
                "metadata_facet_id": (
                    None
                    if item.get("metadata_facet_id") is None
                    else str(item.get("metadata_facet_id"))
                ),
                "display_name": str(item.get("display_name") or ""),
                "availability": str(item.get("availability") or "unavailable"),
                "default_filter_id": (
                    None
                    if item.get("default_filter_id") is None
                    else str(item.get("default_filter_id"))
                ),
                "available_filter_ids": [
                    str(filter_id) for filter_id in item.get("available_filter_ids", [])
                ],
                "facet_value_count": int(item.get("facet_value_count", 0) or 0),
                "caption": str(item.get("caption") or ""),
            }
        )
    return result


def _normalize_context_metadata_facet_filter_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence):
        return []
    result: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        result.append(
            {
                "filter_id": str(item.get("filter_id") or ""),
                "display_name": str(item.get("display_name") or ""),
                "metadata_facet_id": (
                    None
                    if item.get("metadata_facet_id") is None
                    else str(item.get("metadata_facet_id"))
                ),
                "facet_value": (
                    None if item.get("facet_value") is None else str(item.get("facet_value"))
                ),
                "availability": str(item.get("availability") or "unavailable"),
                "matching_root_ids": [
                    int(root_id) for root_id in item.get("matching_root_ids", [])
                ],
                "visible_root_ids": [
                    int(root_id) for root_id in item.get("visible_root_ids", [])
                ],
                "visible_edge_pairs": [
                    [int(pair[0]), int(pair[1])]
                    for pair in item.get("visible_edge_pairs", [])
                    if isinstance(pair, Sequence) and len(pair) == 2
                ],
                "visible_module_ids": [
                    str(module_id) for module_id in item.get("visible_module_ids", [])
                ],
                "matching_active_root_count": int(
                    item.get("matching_active_root_count", 0) or 0
                ),
                "matching_context_root_count": int(
                    item.get("matching_context_root_count", 0) or 0
                ),
                "caption": str(item.get("caption") or ""),
                "boundary_note": str(item.get("boundary_note") or ""),
            }
        )
    return result


def _normalize_context_pathway_explanation_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence):
        return []
    result: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        cards: list[dict[str, Any]] = []
        for card in item.get("cards", []):
            if not isinstance(card, Mapping):
                continue
            cards.append(
                {
                    "explanation_id": str(card.get("explanation_id") or ""),
                    "pathway_id": str(card.get("pathway_id") or ""),
                    "display_name": str(card.get("display_name") or ""),
                    "biological_direction": str(card.get("biological_direction") or ""),
                    "review_direction": str(card.get("review_direction") or ""),
                    "anchor_root_id": int(card.get("anchor_root_id", 0) or 0),
                    "target_root_id": int(card.get("target_root_id", 0) or 0),
                    "review_node_root_ids": [
                        int(root_id) for root_id in card.get("review_node_root_ids", [])
                    ],
                    "node_root_ids": [
                        int(root_id) for root_id in card.get("node_root_ids", [])
                    ],
                    "edge_key_pairs": [
                        [int(pair[0]), int(pair[1])]
                        for pair in card.get("edge_key_pairs", [])
                        if isinstance(pair, Sequence) and len(pair) == 2
                    ],
                    "hop_count": int(card.get("hop_count", 0) or 0),
                    "path_synapse_count": int(card.get("path_synapse_count", 0) or 0),
                    "path_weight": float(card.get("path_weight", 0.0) or 0.0),
                    "active_root_ids": [
                        int(root_id) for root_id in card.get("active_root_ids", [])
                    ],
                    "context_root_ids": [
                        int(root_id) for root_id in card.get("context_root_ids", [])
                    ],
                    "facet_groupings": [
                        {
                            "metadata_facet_id": str(group.get("metadata_facet_id") or ""),
                            "display_name": str(group.get("display_name") or ""),
                            "facet_value": str(group.get("facet_value") or ""),
                        }
                        for group in card.get("facet_groupings", [])
                        if isinstance(group, Mapping)
                    ],
                    "facet_caption": str(card.get("facet_caption") or ""),
                    "caption": str(card.get("caption") or ""),
                    "why_included": str(card.get("why_included") or ""),
                    "boundary_note": str(card.get("boundary_note") or ""),
                }
            )
        result.append(
            {
                "explanation_mode_id": str(item.get("explanation_mode_id") or ""),
                "display_name": str(item.get("display_name") or ""),
                "description": str(item.get("description") or ""),
                "availability": str(item.get("availability") or "unavailable"),
                "default_explanation_id": (
                    None
                    if item.get("default_explanation_id") is None
                    else str(item.get("default_explanation_id"))
                ),
                "card_count": int(item.get("card_count", 0) or 0),
                "caption": str(item.get("caption") or ""),
                "boundary_note": str(item.get("boundary_note") or ""),
                "cards": cards,
            }
        )
    return result


def _normalize_context_interaction_flow_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence):
        return []
    result: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        result.append(
            {
                "interaction_flow_id": str(item.get("interaction_flow_id") or ""),
                "display_name": str(item.get("display_name") or ""),
                "flow_kind": str(item.get("flow_kind") or ""),
                "graph_view_id": str(item.get("graph_view_id") or ""),
                "query_profile_id": str(item.get("query_profile_id") or ""),
                "overlay_id": (
                    None if item.get("overlay_id") is None else str(item.get("overlay_id"))
                ),
                "metadata_facet_id": (
                    None
                    if item.get("metadata_facet_id") is None
                    else str(item.get("metadata_facet_id"))
                ),
                "pathway_explanation_mode_id": (
                    None
                    if item.get("pathway_explanation_mode_id") is None
                    else str(item.get("pathway_explanation_mode_id"))
                ),
                "availability": str(item.get("availability") or "unavailable"),
                "default_target_id": (
                    None
                    if item.get("default_target_id") is None
                    else str(item.get("default_target_id"))
                ),
                "caption": str(item.get("caption") or ""),
            }
        )
    return result


def _normalize_context_reviewer_summary_cards(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence):
        return []
    result: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        facts = item.get("facts", {})
        result.append(
            {
                "card_id": str(item.get("card_id") or ""),
                "display_name": str(item.get("display_name") or ""),
                "caption": str(item.get("caption") or ""),
                "facts": (
                    copy.deepcopy(dict(facts))
                    if isinstance(facts, Mapping)
                    else {}
                ),
            }
        )
    return result


def _apply_context_incident_stats(
    *,
    nodes: list[dict[str, Any]],
    edges: Sequence[Mapping[str, Any]],
) -> None:
    node_by_root = {int(item["root_id"]): item for item in nodes}
    neighbor_sets: dict[int, set[int]] = defaultdict(set)
    context_neighbor_sets: dict[int, set[int]] = defaultdict(set)
    for edge in edges:
        source_root_id = int(edge["source_root_id"])
        target_root_id = int(edge["target_root_id"])
        synapse_count = int(edge["synapse_count"])
        neighbor_sets[source_root_id].add(target_root_id)
        neighbor_sets[target_root_id].add(source_root_id)
        source_node = node_by_root.get(source_root_id)
        target_node = node_by_root.get(target_root_id)
        if source_node is not None:
            source_node["outgoing_synapse_count"] += synapse_count
            source_node["incident_synapse_count"] += synapse_count
        if target_node is not None:
            target_node["incoming_synapse_count"] += synapse_count
            target_node["incident_synapse_count"] += synapse_count
        if source_node is not None and target_node is not None:
            if not bool(target_node["selection_enabled"]):
                context_neighbor_sets[source_root_id].add(target_root_id)
            if not bool(source_node["selection_enabled"]):
                context_neighbor_sets[target_root_id].add(source_root_id)
    for root_id, node in node_by_root.items():
        node["neighbor_root_ids"] = sorted(int(value) for value in neighbor_sets.get(root_id, set()))
        node["context_root_ids"] = sorted(
            int(value) for value in context_neighbor_sets.get(root_id, set())
        )


def _context_node_style_variant(
    *,
    selection_enabled: bool,
    pathway_highlight: bool,
    emphasize_pathway_highlight: bool,
) -> str:
    if selection_enabled:
        return "active_selected"
    if pathway_highlight and emphasize_pathway_highlight:
        return "context_pathway_highlight"
    return "context_only"


def _context_edge_style_variant(
    *,
    base_edge_role_id: str,
    highlighted: bool,
    emphasize_pathway_highlight: bool,
) -> str:
    if highlighted and emphasize_pathway_highlight:
        return "pathway_highlight"
    if base_edge_role_id == ACTIVE_TO_CONTEXT_EDGE_ROLE_ID:
        return "active_to_context"
    if base_edge_role_id == CONTEXT_TO_ACTIVE_EDGE_ROLE_ID:
        return "context_to_active"
    if base_edge_role_id == CONTEXT_INTERNAL_EDGE_ROLE_ID:
        return "context_internal"
    if base_edge_role_id == DOWNSTREAM_MODULE_SUMMARY_EDGE_ROLE_ID:
        return "downstream_module_summary"
    return "active_internal"


def _context_node_sort_key(node: Mapping[str, Any]) -> tuple[Any, ...]:
    style_order = {
        "active_selected": 0,
        "active_pathway_highlight": 1,
        "context_pathway_highlight": 2,
        "context_only": 3,
    }
    hop_count = node.get("nearest_active_hop_count")
    return (
        style_order.get(str(node.get("style_variant")), 9),
        999 if hop_count is None else int(hop_count),
        int(node["root_id"]),
    )


def _context_edge_sort_key(edge: Mapping[str, Any]) -> tuple[Any, ...]:
    style_order = {
        "active_internal": 0,
        "active_to_context": 1,
        "context_to_active": 2,
        "pathway_highlight": 3,
        "context_internal": 4,
        "downstream_module_summary": 5,
    }
    return (
        style_order.get(str(edge.get("style_variant")), 9),
        -int(edge.get("synapse_count", 0) or 0),
        int(edge["source_root_id"]),
        int(edge["target_root_id"]),
    )


def _resolve_stimulus_scene_context(
    *,
    metadata_path: Path,
    selected_condition_ids: Sequence[str],
    max_render_dimension: int,
) -> dict[str, Any]:
    try:
        replay = load_recorded_stimulus_bundle(metadata_path)
        replay_frames = [
            _encode_scene_frame(
                frame_index=int(frame_index),
                time_ms=float(replay.frame_times_ms[frame_index]),
                frame=np.asarray(
                    _downsample_frame(
                        replay.frames[frame_index],
                        max_render_dimension=max_render_dimension,
                    ),
                    dtype=np.float32,
                ),
            )
            for frame_index in range(replay.frames.shape[0])
        ]
        render_layers = [
            {
                "layer_id": "canonical_scene",
                "display_name": "Canonical Scene Raster",
                "availability": "available",
                "artifact_kind": (
                    FRAME_CACHE_KEY
                    if str(replay.replay_source) == "frame_cache"
                    else "descriptor_metadata"
                ),
                "artifact_path": str(metadata_path),
                "reason": None,
                "replay_source": str(replay.replay_source),
            }
        ]
        render_status = "available"
        unavailable_reason = None
    except Exception as exc:
        replay = None
        replay_frames = []
        render_layers = [
            {
                "layer_id": "canonical_scene",
                "display_name": "Canonical Scene Raster",
                "availability": "unavailable",
                "artifact_kind": "descriptor_metadata",
                "artifact_path": str(metadata_path),
                "reason": str(exc),
                "replay_source": "unavailable",
            }
        ]
        render_status = "unavailable"
        unavailable_reason = str(exc)
    bundle_metadata = (
        replay.bundle_metadata
        if replay is not None
        else load_stimulus_bundle_metadata(metadata_path)
    )
    replay_times = [float(item["time_ms"]) for item in replay_frames]
    return {
        "pane_id": SCENE_PANE_ID,
        "context_version": DASHBOARD_SCENE_CONTEXT_VERSION,
        "source_kind": "stimulus_bundle",
        "source_contract_version": STIMULUS_BUNDLE_CONTRACT_VERSION,
        "metadata_path": str(metadata_path),
        "bundle_id": str(bundle_metadata["bundle_id"]),
        "stimulus_family": str(bundle_metadata["stimulus_family"]),
        "stimulus_name": str(bundle_metadata["stimulus_name"]),
        "parameter_snapshot": copy.deepcopy(dict(bundle_metadata["parameter_snapshot"])),
        "temporal_sampling": copy.deepcopy(dict(bundle_metadata["temporal_sampling"])),
        "representation_family": str(bundle_metadata["representation_family"]),
        "selected_condition_ids": sorted(str(item) for item in selected_condition_ids),
        "render_status": render_status,
        "render_layers": render_layers,
        "active_layer_id": "canonical_scene",
        "replay_frames": replay_frames,
        "frame_discovery": {
            "render_status": render_status,
            "replay_source": str(render_layers[0]["replay_source"]),
            "artifact_kind": str(render_layers[0]["artifact_kind"]),
            "artifact_path": str(render_layers[0]["artifact_path"]),
            "frame_count": len(replay_frames),
            "unavailable_reason": unavailable_reason,
            "time_range_ms": (
                []
                if not replay_times
                else [float(replay_times[0]), float(replay_times[-1])]
            ),
        },
    }


def _resolve_retinal_scene_context(
    *,
    metadata_path: Path,
    selected_condition_ids: Sequence[str],
    max_render_dimension: int,
) -> dict[str, Any]:
    try:
        replay = load_recorded_retinal_bundle(metadata_path)
        replay_frames = [
            _encode_scene_frame(
                frame_index=int(frame.frame_index),
                time_ms=float(frame.time_ms),
                frame=np.asarray(
                    _downsample_frame(
                        _retinal_frame_for_display(frame.retinal_frame),
                        max_render_dimension=max_render_dimension,
                    ),
                    dtype=np.float32,
                ),
            )
            for frame in (
                replay.frame_at_time_ms(float(time_ms))
                for time_ms in replay.frame_times_ms.tolist()
            )
        ]
        render_layers = [
            {
                "layer_id": "fly_view_retinal",
                "display_name": "Fly-View Retinal Lattice",
                "availability": "available",
                "artifact_kind": FRAME_ARCHIVE_KEY,
                "artifact_path": str(metadata_path),
                "reason": None,
                "replay_source": str(replay.replay_source),
            }
        ]
        render_status = "available"
        unavailable_reason = None
        bundle_metadata = replay.bundle_metadata
    except Exception as exc:
        bundle_metadata = load_retinal_bundle_metadata(metadata_path)
        replay_frames = []
        render_layers = [
            {
                "layer_id": "fly_view_retinal",
                "display_name": "Fly-View Retinal Lattice",
                "availability": "unavailable",
                "artifact_kind": FRAME_ARCHIVE_KEY,
                "artifact_path": str(metadata_path),
                "reason": str(exc),
                "replay_source": "unavailable",
            }
        ]
        render_status = "unavailable"
        unavailable_reason = str(exc)

    replay_times = [float(item["time_ms"]) for item in replay_frames]
    return {
        "pane_id": SCENE_PANE_ID,
        "context_version": DASHBOARD_SCENE_CONTEXT_VERSION,
        "source_kind": "retinal_bundle",
        "source_contract_version": RETINAL_INPUT_BUNDLE_CONTRACT_VERSION,
        "metadata_path": str(metadata_path),
        "bundle_id": str(bundle_metadata["bundle_id"]),
        "source_reference": copy.deepcopy(dict(bundle_metadata["source_reference"])),
        "temporal_sampling": copy.deepcopy(dict(bundle_metadata["temporal_sampling"])),
        "representation_family": str(bundle_metadata["representation_family"]),
        "selected_condition_ids": sorted(str(item) for item in selected_condition_ids),
        "render_status": render_status,
        "render_layers": render_layers,
        "active_layer_id": "fly_view_retinal",
        "replay_frames": replay_frames,
        "frame_discovery": {
            "render_status": render_status,
            "replay_source": str(render_layers[0]["replay_source"]),
            "artifact_kind": str(render_layers[0]["artifact_kind"]),
            "artifact_path": str(render_layers[0]["artifact_path"]),
            "frame_count": len(replay_frames),
            "unavailable_reason": unavailable_reason,
            "time_range_ms": (
                []
                if not replay_times
                else [float(replay_times[0]), float(replay_times[-1])]
            ),
        },
        "frame_layout": copy.deepcopy(dict(bundle_metadata["frame_layout"])),
        "signal_convention": copy.deepcopy(dict(bundle_metadata["signal_convention"])),
    }


def _build_selected_root_record(
    root_id: int,
    manifest_record: Mapping[str, Any],
) -> dict[str, Any]:
    assets = _require_mapping(
        manifest_record.get("assets"),
        field_name=f"geometry_manifest[{root_id}].assets",
    )
    simplified_mesh = _path_status_record(
        _require_mapping(
            assets[SIMPLIFIED_MESH_KEY],
            field_name=f"geometry_manifest[{root_id}].assets.simplified_mesh",
        )
    )
    raw_skeleton = _path_status_record(
        _require_mapping(
            assets[RAW_SKELETON_KEY],
            field_name=f"geometry_manifest[{root_id}].assets.raw_skeleton",
        )
    )
    surface_graph = _path_status_record(
        _require_mapping(
            assets[SURFACE_GRAPH_KEY],
            field_name=f"geometry_manifest[{root_id}].assets.surface_graph",
        )
    )
    patch_graph = _path_status_record(
        _require_mapping(
            assets[PATCH_GRAPH_KEY],
            field_name=f"geometry_manifest[{root_id}].assets.patch_graph",
        )
    )
    operator_paths = {
        artifact_id: str(Path(path).resolve())
        for artifact_id, path in discover_operator_bundle_paths(manifest_record).items()
    }
    edge_bundle_paths = []
    for item in discover_edge_coupling_bundle_paths(manifest_record):
        edge_bundle_paths.append(
            {
                "pre_root_id": int(item["pre_root_id"]),
                "post_root_id": int(item["post_root_id"]),
                "peer_root_id": int(item["peer_root_id"]),
                "relation_to_root": str(item["relation_to_root"]),
                "path": str(Path(item["path"]).resolve()),
                "status": str(item["status"]),
                "exists": Path(item["path"]).resolve().exists(),
                "referenced_by_root_ids": [int(root_id)],
            }
        )
    edge_bundle_paths.sort(
        key=lambda item: (
            int(item["pre_root_id"]),
            int(item["post_root_id"]),
            str(item["relation_to_root"]),
        )
    )
    return {
        "root_id": int(root_id),
        "cell_type": str(manifest_record.get("cell_type", "")),
        "project_role": str(manifest_record.get("project_role", "")),
        "morphology_class": _infer_morphology_class(
            simplified_mesh_exists=bool(simplified_mesh["exists"]),
            raw_skeleton_exists=bool(raw_skeleton["exists"]),
        ),
        "geometry_assets": {
            "simplified_mesh": simplified_mesh,
            "raw_skeleton": raw_skeleton,
            "surface_graph": surface_graph,
            "patch_graph": patch_graph,
        },
        "operator_artifacts": operator_paths,
        "edge_bundle_paths": edge_bundle_paths,
        "linked_selection": build_dashboard_linked_neuron_payload(
            root_id=int(root_id),
            source_layer="selected_root_catalog",
        ),
    }


def _build_connectivity_context(
    *,
    synapse_rows: Sequence[Mapping[str, Any]],
    selected_root_ids: Sequence[int],
    manifest_records: Mapping[str, Mapping[str, Any]],
    edge_bundle_records: Mapping[tuple[int, int], Mapping[str, Any]],
) -> dict[str, Any]:
    selected_root_set = {int(root_id) for root_id in selected_root_ids}
    grouped_edges: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    connected_root_ids: set[int] = set(selected_root_set)
    for row in synapse_rows:
        pre_root_id = int(row["pre_root_id"])
        post_root_id = int(row["post_root_id"])
        if pre_root_id not in selected_root_set and post_root_id not in selected_root_set:
            continue
        grouped_edges[(pre_root_id, post_root_id)].append(copy.deepcopy(dict(row)))
        connected_root_ids.add(pre_root_id)
        connected_root_ids.add(post_root_id)

    incoming_counts: dict[int, int] = defaultdict(int)
    outgoing_counts: dict[int, int] = defaultdict(int)
    neighbor_sets: dict[int, set[int]] = defaultdict(set)
    context_neighbor_sets: dict[int, set[int]] = defaultdict(set)
    edge_catalog: list[dict[str, Any]] = []
    for (pre_root_id, post_root_id), rows in grouped_edges.items():
        synapse_count = len(rows)
        outgoing_counts[pre_root_id] += synapse_count
        incoming_counts[post_root_id] += synapse_count
        neighbor_sets[pre_root_id].add(post_root_id)
        neighbor_sets[post_root_id].add(pre_root_id)
        if post_root_id not in selected_root_set:
            context_neighbor_sets[pre_root_id].add(post_root_id)
        if pre_root_id not in selected_root_set:
            context_neighbor_sets[post_root_id].add(pre_root_id)

        edge_bundle = edge_bundle_records.get((pre_root_id, post_root_id))
        edge_catalog.append(
            {
                "pre_root_id": int(pre_root_id),
                "post_root_id": int(post_root_id),
                "synapse_count": int(synapse_count),
                "source_selected": pre_root_id in selected_root_set,
                "target_selected": post_root_id in selected_root_set,
                "relation_to_subset": _relation_to_subset(
                    pre_root_id=pre_root_id,
                    post_root_id=post_root_id,
                    selected_root_ids=selected_root_set,
                ),
                "edge_bundle_path": None if edge_bundle is None else str(edge_bundle["path"]),
                "edge_bundle_status": "unknown" if edge_bundle is None else str(edge_bundle["status"]),
                "edge_bundle_exists": False if edge_bundle is None else bool(edge_bundle["exists"]),
                "referenced_by_root_ids": [] if edge_bundle is None else list(edge_bundle["referenced_by_root_ids"]),
            }
        )
    edge_catalog.sort(
        key=lambda item: (
            0 if bool(item["source_selected"]) and bool(item["target_selected"]) else 1,
            -int(item["synapse_count"]),
            int(item["pre_root_id"]),
            int(item["post_root_id"]),
        )
    )

    node_catalog: list[dict[str, Any]] = []
    for root_id in sorted(
        connected_root_ids,
        key=lambda value: (
            0 if int(value) in selected_root_set else 1,
            -(
                int(incoming_counts.get(int(value), 0))
                + int(outgoing_counts.get(int(value), 0))
            ),
            int(value),
        ),
    ):
        manifest_record = manifest_records.get(str(int(root_id)))
        geometry_assets = (
            _geometry_assets_for_node_record(manifest_record)
            if manifest_record is not None
            else None
        )
        selection_enabled = int(root_id) in selected_root_set
        node_catalog.append(
            {
                "root_id": int(root_id),
                "subset_membership": (
                    "selected_subset"
                    if int(root_id) in selected_root_set
                    else "connectivity_context"
                ),
                "has_manifest_record": manifest_record is not None,
                "cell_type": (
                    ""
                    if manifest_record is None
                    else str(manifest_record.get("cell_type", ""))
                ),
                "project_role": (
                    ""
                    if manifest_record is None
                    else str(manifest_record.get("project_role", ""))
                ),
                "morphology_class": (
                    ""
                    if geometry_assets is None
                    else _infer_morphology_class(
                        simplified_mesh_exists=bool(
                            geometry_assets["simplified_mesh"]["exists"]
                        ),
                        raw_skeleton_exists=bool(
                            geometry_assets["raw_skeleton"]["exists"]
                        ),
                    )
                ),
                "incoming_synapse_count": int(incoming_counts.get(int(root_id), 0)),
                "outgoing_synapse_count": int(outgoing_counts.get(int(root_id), 0)),
                "incident_synapse_count": int(incoming_counts.get(int(root_id), 0))
                + int(outgoing_counts.get(int(root_id), 0)),
                "neighbor_root_ids": sorted(
                    int(item) for item in neighbor_sets.get(int(root_id), set())
                ),
                "context_root_ids": sorted(
                    int(item)
                    for item in context_neighbor_sets.get(int(root_id), set())
                ),
                "selection_enabled": selection_enabled,
                "linked_selection": build_dashboard_linked_neuron_payload(
                    root_id=int(root_id),
                    source_layer="connectivity_context",
                    selection_enabled=selection_enabled,
                ),
            }
        )

    edge_count = len(edge_catalog)
    available_edge_bundles = sum(
        1 for item in edge_catalog if bool(item["edge_bundle_exists"])
    )
    known_edge_bundle_paths = sum(
        1 for item in edge_catalog if str(item["edge_bundle_status"]) != "unknown"
    )
    missing_manifest_context_roots = sorted(
        int(root_id)
        for root_id in connected_root_ids
        if int(root_id) not in selected_root_set and str(int(root_id)) not in manifest_records
    )
    return {
        "node_catalog": node_catalog,
        "edge_catalog": edge_catalog,
        "network_summary": {
            "selected_root_count": len(selected_root_set),
            "context_root_count": max(0, len(node_catalog) - len(selected_root_set)),
            "edge_count": edge_count,
            "total_synapse_count": sum(int(item["synapse_count"]) for item in edge_catalog),
        },
        "context_layers": {
            "local_synapse_registry": {
                "availability": "available",
                "row_count": len(synapse_rows),
            },
            "edge_coupling_bundles": {
                "availability": _layer_availability(
                    total_count=edge_count,
                    ready_count=available_edge_bundles,
                    known_count=known_edge_bundle_paths,
                ),
                "known_edge_count": known_edge_bundle_paths,
                "ready_edge_count": available_edge_bundles,
                "edge_count": edge_count,
            },
            "geometry_manifest_context": {
                "availability": (
                    "available"
                    if not missing_manifest_context_roots
                    else "partial"
                ),
                "missing_context_root_ids": missing_manifest_context_roots,
            },
        },
    }


def _geometry_assets_for_node_record(
    manifest_record: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    assets = _require_mapping(
        manifest_record.get("assets"),
        field_name="geometry_manifest.assets",
    )
    return {
        "simplified_mesh": _path_status_record(
            _require_mapping(assets[SIMPLIFIED_MESH_KEY], field_name="assets.simplified_mesh")
        ),
        "raw_skeleton": _path_status_record(
            _require_mapping(assets[RAW_SKELETON_KEY], field_name="assets.raw_skeleton")
        ),
        "surface_graph": _path_status_record(
            _require_mapping(assets[SURFACE_GRAPH_KEY], field_name="assets.surface_graph")
        ),
        "patch_graph": _path_status_record(
            _require_mapping(assets[PATCH_GRAPH_KEY], field_name="assets.patch_graph")
        ),
    }


def _load_dashboard_synapse_registry(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Dashboard local synapse registry at {path} is missing a header row.")
        required = {"pre_root_id", "post_root_id"}
        missing = sorted(required - set(reader.fieldnames))
        if missing:
            raise ValueError(
                "Dashboard local synapse registry is missing required columns "
                f"{missing!r} at {path}."
            )
        rows: list[dict[str, Any]] = []
        for index, row in enumerate(reader, start=1):
            pre_root_id = _parse_required_int(
                row.get("pre_root_id"),
                field_name=f"local_synapse_registry[{index}].pre_root_id",
            )
            post_root_id = _parse_required_int(
                row.get("post_root_id"),
                field_name=f"local_synapse_registry[{index}].post_root_id",
            )
            synapse_row_id = row.get("synapse_row_id") or f"row-{index:06d}"
            rows.append(
                {
                    "synapse_row_id": str(synapse_row_id),
                    "source_row_number": _parse_optional_int(
                        row.get("source_row_number"),
                        default=index,
                    ),
                    "pre_root_id": pre_root_id,
                    "post_root_id": post_root_id,
                    "source_file": str(row.get("source_file") or path.name),
                    "weight": _parse_optional_float(row.get("weight")),
                    "confidence": _parse_optional_float(row.get("confidence")),
                    "nt_type": str(row.get("nt_type") or ""),
                    "sign": str(row.get("sign") or ""),
                }
            )
    rows.sort(
        key=lambda item: (
            int(item["pre_root_id"]),
            int(item["post_root_id"]),
            int(item["source_row_number"]),
            str(item["synapse_row_id"]),
        )
    )
    return rows


def _relation_to_subset(
    *,
    pre_root_id: int,
    post_root_id: int,
    selected_root_ids: set[int],
) -> str:
    if pre_root_id in selected_root_ids and post_root_id in selected_root_ids:
        return "selected_to_selected"
    if pre_root_id in selected_root_ids:
        return "selected_to_context"
    if post_root_id in selected_root_ids:
        return "context_to_selected"
    return "context_to_context"


def _layer_availability(
    *,
    total_count: int,
    ready_count: int,
    known_count: int,
) -> str:
    if total_count == 0:
        return "available"
    if ready_count == total_count:
        return "available"
    if ready_count > 0 or known_count > 0:
        return "partial"
    return "unavailable"


def _infer_morphology_class(
    *,
    simplified_mesh_exists: bool,
    raw_skeleton_exists: bool,
) -> str:
    if simplified_mesh_exists:
        return SURFACE_NEURON_CLASS
    if raw_skeleton_exists:
        return SKELETON_NEURON_CLASS
    return POINT_NEURON_CLASS


def _encode_scene_frame(
    *,
    frame_index: int,
    time_ms: float,
    frame: np.ndarray,
) -> dict[str, Any]:
    clipped = np.asarray(np.clip(frame, 0.0, 1.0), dtype=np.float32)
    encoded = np.rint(clipped * 255.0).astype(np.uint8)
    return {
        "frame_index": int(frame_index),
        "time_ms": float(time_ms),
        "height": int(encoded.shape[0]),
        "width": int(encoded.shape[1]),
        "encoding": SCENE_FRAME_UINT8_ENCODING,
        "pixels_b64": base64.b64encode(encoded.tobytes(order="C")).decode("ascii"),
        "mean_luminance": float(np.mean(clipped)),
        "min_luminance": float(np.min(clipped)),
        "max_luminance": float(np.max(clipped)),
    }


def _retinal_frame_for_display(frame: np.ndarray) -> np.ndarray:
    values = np.asarray(frame, dtype=np.float32)
    if values.ndim != 2:
        raise ValueError("Retinal display frames must have shape (eye, ommatidium).")
    return values


def _downsample_frame(
    frame: np.ndarray,
    *,
    max_render_dimension: int,
) -> np.ndarray:
    values = np.asarray(frame, dtype=np.float32)
    if values.ndim != 2:
        raise ValueError("Dashboard scene frames must be two-dimensional.")
    height, width = values.shape
    if height <= max_render_dimension and width <= max_render_dimension:
        return values
    scale = max(height, width) / float(max_render_dimension)
    out_height = max(1, min(max_render_dimension, int(round(height / scale))))
    out_width = max(1, min(max_render_dimension, int(round(width / scale))))
    y_edges = np.linspace(0, height, out_height + 1, dtype=np.int64)
    x_edges = np.linspace(0, width, out_width + 1, dtype=np.int64)
    reduced = np.empty((out_height, out_width), dtype=np.float32)
    for y_index in range(out_height):
        y_start = int(y_edges[y_index])
        y_stop = int(max(y_edges[y_index + 1], y_start + 1))
        for x_index in range(out_width):
            x_start = int(x_edges[x_index])
            x_stop = int(max(x_edges[x_index + 1], x_start + 1))
            reduced[y_index, x_index] = float(
                np.mean(values[y_start:y_stop, x_start:x_stop], dtype=np.float64)
            )
    return reduced


def _path_status_record(record: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(str(record.get("path", ""))).resolve()
    status = str(record.get("status", ""))
    return {
        "path": str(path),
        "status": status,
        "exists": path.exists(),
    }


def _parse_required_int(value: Any, *, field_name: str) -> int:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty integer value.")
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer, got {value!r}.") from exc


def _parse_optional_int(value: Any, *, default: int) -> int:
    text = "" if value is None else str(value).strip()
    if not text:
        return int(default)
    return int(text)


def _parse_optional_float(value: Any) -> float | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    return float(text)


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value


__all__ = [
    "DASHBOARD_CIRCUIT_CONTEXT_VERSION",
    "DASHBOARD_LINKED_NEURON_PAYLOAD_VERSION",
    "DASHBOARD_SCENE_CONTEXT_VERSION",
    "DASHBOARD_WHOLE_BRAIN_CONTEXT_VERSION",
    "build_dashboard_linked_neuron_payload",
    "load_dashboard_whole_brain_context",
    "normalize_dashboard_circuit_context",
    "resolve_dashboard_scene_context",
]
