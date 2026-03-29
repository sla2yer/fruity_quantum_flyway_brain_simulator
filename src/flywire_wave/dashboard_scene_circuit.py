from __future__ import annotations

import base64
import copy
import csv
from collections import defaultdict
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


DASHBOARD_SCENE_CONTEXT_VERSION = "dashboard_scene_context.v1"
DASHBOARD_CIRCUIT_CONTEXT_VERSION = "dashboard_circuit_context.v1"
DASHBOARD_LINKED_NEURON_PAYLOAD_VERSION = "dashboard_linked_neuron_payload.v1"

SCENE_FRAME_UINT8_ENCODING = "base64_uint8_grayscale_row_major"
DEFAULT_SCENE_MAX_RENDER_DIMENSION = 48


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
    "build_dashboard_linked_neuron_payload",
    "normalize_dashboard_circuit_context",
    "resolve_dashboard_scene_context",
]
