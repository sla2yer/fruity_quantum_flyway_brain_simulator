from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from .coupling_assembly import (
    ANCHOR_COLUMN_TYPES,
    CLOUD_COLUMN_TYPES,
    COMPONENT_COLUMN_TYPES,
    COMPONENT_SYNAPSE_COLUMN_TYPES,
    EDGE_COUPLING_BUNDLE_VERSION,
    EdgeCouplingBundle,
    assemble_edge_coupling_bundle,
)
from .coupling_contract import (
    ASSET_STATUS_MISSING,
    ASSET_STATUS_READY,
    POINT_NEURON_LUMPED_MODE,
    SKELETON_SEGMENT_CLOUD_MODE,
    SURFACE_PATCH_CLOUD_MODE,
    build_coupling_bundle_metadata,
    build_coupling_contract_paths,
    build_edge_coupling_bundle_path,
    build_edge_coupling_bundle_reference,
    build_root_coupling_bundle_paths,
    normalize_coupling_assembly_config,
)
from .geometry_contract import build_geometry_bundle_paths
from .io_utils import ensure_dir, write_json
from .registry import (
    ROLE_CONTEXT_ONLY,
    ROLE_POINT_SIMULATED,
    ROLE_SKELETON_SIMULATED,
    ROLE_SURFACE_SIMULATED,
    load_synapse_registry,
)


SYNAPSE_ANCHOR_MAP_VERSION = "synapse_anchor_map.v1"

MAPPING_STATUS_MAPPED = "mapped"
MAPPING_STATUS_MAPPED_WITH_FALLBACK = "mapped_with_fallback"
MAPPING_STATUS_BLOCKED = "blocked"

QUALITY_STATUS_OK = "ok"
QUALITY_STATUS_WARN = "warn"
QUALITY_STATUS_UNAVAILABLE = "unavailable"

ANCHOR_TYPE_SURFACE_PATCH = "surface_patch"
ANCHOR_TYPE_SKELETON_NODE = "skeleton_node"
ANCHOR_TYPE_POINT_STATE = "point_state"

ANCHOR_RESOLUTION_COARSE_PATCH = "coarse_patch"
ANCHOR_RESOLUTION_SKELETON_NODE = "skeleton_node"
ANCHOR_RESOLUTION_LUMPED_ROOT_STATE = "lumped_root_state"

QUERY_SOURCE_PRE = "pre_xyz"
QUERY_SOURCE_POST = "post_xyz"
QUERY_SOURCE_CENTER = "synapse_xyz"

INCOMING_RELATION = "incoming"
OUTGOING_RELATION = "outgoing"

EDGE_BUNDLE_COLUMN_TYPES: dict[str, str] = {
    "synapse_row_id": "string",
    "source_row_number": "int",
    "synapse_id": "string",
    "pre_root_id": "int",
    "post_root_id": "int",
    "synapse_x": "float",
    "synapse_y": "float",
    "synapse_z": "float",
    "pre_source_x": "float",
    "pre_source_y": "float",
    "pre_source_z": "float",
    "post_source_x": "float",
    "post_source_y": "float",
    "post_source_z": "float",
    "neuropil": "string",
    "nt_type": "string",
    "sign": "string",
    "confidence": "float",
    "weight": "float",
    "source_file": "string",
    "snapshot_version": "string",
    "materialization_version": "string",
    "pre_query_source": "string",
    "pre_query_x": "float",
    "pre_query_y": "float",
    "pre_query_z": "float",
    "pre_mapping_status": "string",
    "pre_quality_status": "string",
    "pre_quality_reason": "string",
    "pre_fallback_used": "bool",
    "pre_fallback_reason": "string",
    "pre_blocked_reason": "string",
    "pre_anchor_mode": "string",
    "pre_anchor_type": "string",
    "pre_anchor_resolution": "string",
    "pre_anchor_index": "int",
    "pre_anchor_x": "float",
    "pre_anchor_y": "float",
    "pre_anchor_z": "float",
    "pre_anchor_distance": "float",
    "pre_anchor_residual_x": "float",
    "pre_anchor_residual_y": "float",
    "pre_anchor_residual_z": "float",
    "pre_support_index": "int",
    "pre_support_distance": "float",
    "pre_support_scale": "float",
    "post_query_source": "string",
    "post_query_x": "float",
    "post_query_y": "float",
    "post_query_z": "float",
    "post_mapping_status": "string",
    "post_quality_status": "string",
    "post_quality_reason": "string",
    "post_fallback_used": "bool",
    "post_fallback_reason": "string",
    "post_blocked_reason": "string",
    "post_anchor_mode": "string",
    "post_anchor_type": "string",
    "post_anchor_resolution": "string",
    "post_anchor_index": "int",
    "post_anchor_x": "float",
    "post_anchor_y": "float",
    "post_anchor_z": "float",
    "post_anchor_distance": "float",
    "post_anchor_residual_x": "float",
    "post_anchor_residual_y": "float",
    "post_anchor_residual_z": "float",
    "post_support_index": "int",
    "post_support_distance": "float",
    "post_support_scale": "float",
}
EDGE_BUNDLE_COLUMNS = tuple(EDGE_BUNDLE_COLUMN_TYPES)

ROOT_MAP_COLUMN_TYPES: dict[str, str] = {
    "synapse_row_id": "string",
    "source_row_number": "int",
    "synapse_id": "string",
    "root_id": "int",
    "peer_root_id": "int",
    "pre_root_id": "int",
    "post_root_id": "int",
    "neuropil": "string",
    "nt_type": "string",
    "sign": "string",
    "confidence": "float",
    "weight": "float",
    "source_file": "string",
    "snapshot_version": "string",
    "materialization_version": "string",
    "query_source": "string",
    "query_x": "float",
    "query_y": "float",
    "query_z": "float",
    "mapping_status": "string",
    "quality_status": "string",
    "quality_reason": "string",
    "fallback_used": "bool",
    "fallback_reason": "string",
    "blocked_reason": "string",
    "anchor_mode": "string",
    "anchor_type": "string",
    "anchor_resolution": "string",
    "anchor_index": "int",
    "anchor_x": "float",
    "anchor_y": "float",
    "anchor_z": "float",
    "anchor_distance": "float",
    "anchor_residual_x": "float",
    "anchor_residual_y": "float",
    "anchor_residual_z": "float",
    "support_index": "int",
    "support_distance": "float",
    "support_scale": "float",
}
ROOT_MAP_COLUMNS = tuple(ROOT_MAP_COLUMN_TYPES)

ROLE_SUPPORTED_MODES = {
    ROLE_SURFACE_SIMULATED: [SURFACE_PATCH_CLOUD_MODE, SKELETON_SEGMENT_CLOUD_MODE, POINT_NEURON_LUMPED_MODE],
    ROLE_SKELETON_SIMULATED: [SKELETON_SEGMENT_CLOUD_MODE, POINT_NEURON_LUMPED_MODE],
    ROLE_POINT_SIMULATED: [POINT_NEURON_LUMPED_MODE],
    ROLE_CONTEXT_ONLY: [POINT_NEURON_LUMPED_MODE],
}

MAPPING_STATUS_DEFINITIONS = {
    MAPPING_STATUS_MAPPED: "Primary anchor mode for the root representation was used successfully.",
    MAPPING_STATUS_MAPPED_WITH_FALLBACK: (
        "A lower-priority fallback representation was used because a higher-resolution anchor was unavailable or "
        "unsupported for this root."
    ),
    MAPPING_STATUS_BLOCKED: "No supported anchor could be produced for the query point and root representation.",
}

QUALITY_STATUS_DEFINITIONS = {
    QUALITY_STATUS_OK: "Anchor distance stays within the local support scale of the chosen representation.",
    QUALITY_STATUS_WARN: "Anchor distance exceeds the local support scale; inspect the recorded residuals.",
    QUALITY_STATUS_UNAVAILABLE: "Quality metrics are unavailable because the mapping was blocked.",
}

_NEAREST_NEIGHBOR_QUERY_EPSILON = 1.0e-12


@dataclass(frozen=True)
class RootLocalNearestNeighborIndex:
    tree: cKDTree


@dataclass(frozen=True)
class RootContext:
    root_id: int
    project_role: str
    supported_modes: tuple[str, ...]
    surface_vertices: np.ndarray
    surface_support_index: RootLocalNearestNeighborIndex | None
    surface_to_patch: np.ndarray
    patch_centroids: np.ndarray
    patch_radii: np.ndarray
    skeleton_node_ids: np.ndarray
    skeleton_points: np.ndarray
    skeleton_support_index: RootLocalNearestNeighborIndex | None
    skeleton_local_scales: np.ndarray
    point_incoming_anchor: np.ndarray
    point_incoming_radius: float
    point_outgoing_anchor: np.ndarray
    point_outgoing_radius: float
    surface_unavailable_reason: str
    skeleton_unavailable_reason: str
    point_incoming_unavailable_reason: str
    point_outgoing_unavailable_reason: str


@dataclass(frozen=True)
class LoadedRootAnchorMap:
    root_id: int
    relation_to_root: str
    peer_root_ids: np.ndarray
    peer_root_indptr: np.ndarray
    table: pd.DataFrame


def materialize_synapse_anchor_maps(
    *,
    root_ids: Iterable[int],
    processed_coupling_dir: str | Path,
    meshes_raw_dir: str | Path,
    skeletons_raw_dir: str | Path,
    processed_mesh_dir: str | Path,
    processed_graph_dir: str | Path,
    neuron_registry: pd.DataFrame | None = None,
    synapse_registry_path: str | Path | None = None,
    coupling_assembly: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_root_ids = sorted({int(root_id) for root_id in root_ids})
    if not normalized_root_ids:
        raise ValueError("At least one root ID is required to materialize synapse anchor maps.")
    normalized_coupling_assembly = normalize_coupling_assembly_config(coupling_assembly)

    contract_paths = build_coupling_contract_paths(processed_coupling_dir)
    registry_path = (
        contract_paths.local_synapse_registry_path
        if synapse_registry_path is None
        else Path(synapse_registry_path).resolve()
    )
    if not registry_path.exists():
        return _missing_registry_summary(root_ids=normalized_root_ids, registry_path=registry_path, processed_coupling_dir=processed_coupling_dir)

    synapse_df = load_synapse_registry(registry_path)
    synapse_df = synapse_df.loc[
        synapse_df["pre_root_id"].isin(normalized_root_ids) & synapse_df["post_root_id"].isin(normalized_root_ids)
    ].copy()
    synapse_df = synapse_df.sort_values(
        ["pre_root_id", "post_root_id", "source_row_number", "synapse_row_id"],
        kind="mergesort",
    ).reset_index(drop=True)

    project_roles = _project_role_lookup(neuron_registry=neuron_registry)
    root_contexts = {
        root_id: _build_root_context(
            root_id=root_id,
            project_role=project_roles.get(int(root_id), ROLE_CONTEXT_ONLY),
            root_synapses=synapse_df,
            meshes_raw_dir=meshes_raw_dir,
            skeletons_raw_dir=skeletons_raw_dir,
            processed_mesh_dir=processed_mesh_dir,
            processed_graph_dir=processed_graph_dir,
        )
        for root_id in normalized_root_ids
    }

    edge_records = [
        _build_edge_record(
            row=row,
            pre_context=root_contexts[int(row.pre_root_id)],
            post_context=root_contexts[int(row.post_root_id)],
        )
        for row in synapse_df.itertuples(index=False)
    ]
    edge_df = pd.DataFrame.from_records(edge_records, columns=EDGE_BUNDLE_COLUMNS)

    edge_summaries: dict[tuple[int, int], dict[str, Any]] = {}
    edge_tables: dict[tuple[int, int], pd.DataFrame] = {}
    if not edge_df.empty:
        grouped = edge_df.groupby(["pre_root_id", "post_root_id"], sort=True, dropna=False)
        for (pre_root_id, post_root_id), edge_table in grouped:
            normalized_edge = edge_table.sort_values(
                ["source_row_number", "synapse_row_id"],
                kind="mergesort",
            ).reset_index(drop=True)
            edge_path = build_edge_coupling_bundle_path(
                int(pre_root_id),
                int(post_root_id),
                processed_coupling_dir=processed_coupling_dir,
            )
            assembled_bundle = assemble_edge_coupling_bundle(
                normalized_edge,
                coupling_assembly=normalized_coupling_assembly,
            )
            _write_edge_coupling_bundle_npz(path=edge_path, bundle=assembled_bundle)
            edge_tables[(int(pre_root_id), int(post_root_id))] = normalized_edge
            edge_summaries[(int(pre_root_id), int(post_root_id))] = {
                "pre_root_id": int(pre_root_id),
                "post_root_id": int(post_root_id),
                "path": str(edge_path),
                "status": str(assembled_bundle.status),
                "synapse_count": int(len(normalized_edge)),
                "component_count": int(len(assembled_bundle.component_table)),
                "blocked_synapse_count": int(len(assembled_bundle.blocked_synapse_table)),
                "source_anchor_count": int(len(assembled_bundle.source_anchor_table)),
                "target_anchor_count": int(len(assembled_bundle.target_anchor_table)),
                "topology_family": str(assembled_bundle.topology_family),
                "kernel_family": str(assembled_bundle.kernel_family),
                "sign_representation": str(assembled_bundle.sign_representation),
                "delay_representation": str(assembled_bundle.delay_representation),
                "delay_model": str(assembled_bundle.delay_model),
                "aggregation_rule": str(assembled_bundle.aggregation_rule),
                "source_cloud_normalization": str(assembled_bundle.source_cloud_normalization),
                "target_cloud_normalization": str(assembled_bundle.target_cloud_normalization),
                "pre_mapping_status_counts": _count_values(normalized_edge["pre_mapping_status"]),
                "post_mapping_status_counts": _count_values(normalized_edge["post_mapping_status"]),
                "pre_quality_status_counts": _count_values(normalized_edge["pre_quality_status"]),
                "post_quality_status_counts": _count_values(normalized_edge["post_quality_status"]),
            }

    bundle_metadata_by_root: dict[int, dict[str, Any]] = {}
    root_summaries: dict[int, dict[str, Any]] = {}
    for root_id in normalized_root_ids:
        bundle_paths = build_root_coupling_bundle_paths(root_id, processed_coupling_dir=processed_coupling_dir)
        incoming_table = _build_root_anchor_map_table(
            edge_df.loc[edge_df["post_root_id"] == int(root_id)].copy(),
            root_id=root_id,
            relation_to_root=INCOMING_RELATION,
        )
        outgoing_table = _build_root_anchor_map_table(
            edge_df.loc[edge_df["pre_root_id"] == int(root_id)].copy(),
            root_id=root_id,
            relation_to_root=OUTGOING_RELATION,
        )

        incoming_peer_root_ids, incoming_peer_root_indptr = _build_peer_index(incoming_table)
        outgoing_peer_root_ids, outgoing_peer_root_indptr = _build_peer_index(outgoing_table)

        _write_table_npz(
            path=bundle_paths.incoming_anchor_map_path,
            column_types=ROOT_MAP_COLUMN_TYPES,
            table=incoming_table,
            metadata={
                "meta_schema_version": str(SYNAPSE_ANCHOR_MAP_VERSION),
                "meta_bundle_kind": "root_anchor_map",
                "meta_relation_to_root": INCOMING_RELATION,
                "meta_root_id": int(root_id),
                "meta_synapse_count": int(len(incoming_table)),
            },
            extra_arrays={
                "peer_root_ids": incoming_peer_root_ids,
                "peer_root_indptr": incoming_peer_root_indptr,
            },
        )
        _write_table_npz(
            path=bundle_paths.outgoing_anchor_map_path,
            column_types=ROOT_MAP_COLUMN_TYPES,
            table=outgoing_table,
            metadata={
                "meta_schema_version": str(SYNAPSE_ANCHOR_MAP_VERSION),
                "meta_bundle_kind": "root_anchor_map",
                "meta_relation_to_root": OUTGOING_RELATION,
                "meta_root_id": int(root_id),
                "meta_synapse_count": int(len(outgoing_table)),
            },
            extra_arrays={
                "peer_root_ids": outgoing_peer_root_ids,
                "peer_root_indptr": outgoing_peer_root_indptr,
            },
        )

        incoming_edges = [
            _root_edge_summary(
                root_id=root_id,
                edge_summary=edge_summaries[key],
                relation_to_root=INCOMING_RELATION,
            )
            for key in sorted(edge_summaries)
            if key[1] == int(root_id)
        ]
        outgoing_edges = [
            _root_edge_summary(
                root_id=root_id,
                edge_summary=edge_summaries[key],
                relation_to_root=OUTGOING_RELATION,
            )
            for key in sorted(edge_summaries)
            if key[0] == int(root_id)
        ]

        coupling_index_payload = {
            "schema_version": SYNAPSE_ANCHOR_MAP_VERSION,
            "root_id": int(root_id),
            "coupling_assembly": dict(normalized_coupling_assembly),
            "local_synapse_registry_path": str(registry_path),
            "incoming_anchor_map": {
                "path": str(bundle_paths.incoming_anchor_map_path),
                "status": _root_table_status(incoming_table),
                "synapse_count": int(len(incoming_table)),
                "peer_root_ids": [int(value) for value in incoming_peer_root_ids.tolist()],
                "mapping_status_counts": _count_values(incoming_table["mapping_status"]),
                "quality_status_counts": _count_values(incoming_table["quality_status"]),
            },
            "outgoing_anchor_map": {
                "path": str(bundle_paths.outgoing_anchor_map_path),
                "status": _root_table_status(outgoing_table),
                "synapse_count": int(len(outgoing_table)),
                "peer_root_ids": [int(value) for value in outgoing_peer_root_ids.tolist()],
                "mapping_status_counts": _count_values(outgoing_table["mapping_status"]),
                "quality_status_counts": _count_values(outgoing_table["quality_status"]),
            },
            "incoming_edges": incoming_edges,
            "outgoing_edges": outgoing_edges,
            "mapping_status_definitions": dict(MAPPING_STATUS_DEFINITIONS),
            "quality_status_definitions": dict(QUALITY_STATUS_DEFINITIONS),
        }
        write_json(coupling_index_payload, bundle_paths.coupling_index_path)

        edge_references = [
            build_edge_coupling_bundle_reference(
                root_id=root_id,
                pre_root_id=int(summary["pre_root_id"]),
                post_root_id=int(summary["post_root_id"]),
                processed_coupling_dir=processed_coupling_dir,
                status=str(summary["status"]),
            )
            for summary in [*incoming_edges, *outgoing_edges]
        ]
        bundle_metadata = build_coupling_bundle_metadata(
            root_id=root_id,
            processed_coupling_dir=processed_coupling_dir,
            local_synapse_registry_status=ASSET_STATUS_READY,
            incoming_anchor_map_status=_root_table_status(incoming_table),
            outgoing_anchor_map_status=_root_table_status(outgoing_table),
            coupling_index_status=_index_status(incoming_edges, outgoing_edges, incoming_table, outgoing_table),
            edge_bundles=edge_references,
            coupling_assembly=normalized_coupling_assembly,
        )
        bundle_metadata_by_root[int(root_id)] = bundle_metadata
        root_summaries[int(root_id)] = {
            "incoming_synapse_count": int(len(incoming_table)),
            "outgoing_synapse_count": int(len(outgoing_table)),
            "incoming_anchor_map_status": _root_table_status(incoming_table),
            "outgoing_anchor_map_status": _root_table_status(outgoing_table),
            "coupling_index_status": _index_status(incoming_edges, outgoing_edges, incoming_table, outgoing_table),
            "incoming_edge_count": len(incoming_edges),
            "outgoing_edge_count": len(outgoing_edges),
            "status": str(bundle_metadata["status"]),
            "kernel_family": str(bundle_metadata["kernel_family"]),
            "delay_model": str(bundle_metadata["delay_model"]),
            "aggregation_rule": str(bundle_metadata["aggregation_rule"]),
        }

    return {
        "schema_version": SYNAPSE_ANCHOR_MAP_VERSION,
        "processed_coupling_dir": str(contract_paths.processed_coupling_dir),
        "synapse_registry_path": str(registry_path),
        "coupling_assembly": dict(normalized_coupling_assembly),
        "synapse_count": int(len(synapse_df)),
        "edge_count": len(edge_summaries),
        "bundle_metadata_by_root": bundle_metadata_by_root,
        "root_summaries": root_summaries,
    }


def load_root_anchor_map(path: str | Path) -> LoadedRootAnchorMap:
    payload = _load_npz_payload(path)
    table = _payload_to_dataframe(payload, ROOT_MAP_COLUMN_TYPES)
    return LoadedRootAnchorMap(
        root_id=int(_payload_scalar(payload["meta_root_id"])),
        relation_to_root=str(_payload_scalar(payload["meta_relation_to_root"])),
        peer_root_ids=np.asarray(payload.get("peer_root_ids", np.empty(0, dtype=np.int64)), dtype=np.int64),
        peer_root_indptr=np.asarray(payload.get("peer_root_indptr", np.asarray([0], dtype=np.int64)), dtype=np.int64),
        table=table,
    )


def load_edge_coupling_bundle(path: str | Path) -> EdgeCouplingBundle:
    payload = _load_npz_payload(path)
    schema_version = str(_payload_scalar(payload["meta_schema_version"]))
    if schema_version != EDGE_COUPLING_BUNDLE_VERSION:
        raise ValueError(
            f"Unsupported edge coupling bundle schema version {schema_version!r}; "
            f"expected {EDGE_COUPLING_BUNDLE_VERSION!r}."
        )
    delay_model_parameters = _json_mapping_scalar(payload["meta_delay_model_parameters_json"])
    return EdgeCouplingBundle(
        pre_root_id=int(_payload_scalar(payload["meta_pre_root_id"])),
        post_root_id=int(_payload_scalar(payload["meta_post_root_id"])),
        status=str(_payload_scalar(payload["meta_status"])),
        topology_family=str(_payload_scalar(payload["meta_topology_family"])),
        kernel_family=str(_payload_scalar(payload["meta_kernel_family"])),
        sign_representation=str(_payload_scalar(payload["meta_sign_representation"])),
        delay_representation=str(_payload_scalar(payload["meta_delay_representation"])),
        delay_model=str(_payload_scalar(payload["meta_delay_model"])),
        delay_model_parameters={
            key: float(value)
            for key, value in delay_model_parameters.items()
        },
        aggregation_rule=str(_payload_scalar(payload["meta_aggregation_rule"])),
        missing_geometry_policy=str(_payload_scalar(payload["meta_missing_geometry_policy"])),
        source_cloud_normalization=str(_payload_scalar(payload["meta_source_cloud_normalization"])),
        target_cloud_normalization=str(_payload_scalar(payload["meta_target_cloud_normalization"])),
        synapse_table=_payload_to_dataframe(payload, EDGE_BUNDLE_COLUMN_TYPES, prefix="synapse_"),
        component_table=_payload_to_dataframe(payload, COMPONENT_COLUMN_TYPES, prefix="component_"),
        blocked_synapse_table=_payload_to_dataframe(payload, EDGE_BUNDLE_COLUMN_TYPES, prefix="blocked_synapse_"),
        source_anchor_table=_payload_to_dataframe(payload, ANCHOR_COLUMN_TYPES, prefix="source_anchor_"),
        target_anchor_table=_payload_to_dataframe(payload, ANCHOR_COLUMN_TYPES, prefix="target_anchor_"),
        source_cloud_table=_payload_to_dataframe(payload, CLOUD_COLUMN_TYPES, prefix="source_cloud_"),
        target_cloud_table=_payload_to_dataframe(payload, CLOUD_COLUMN_TYPES, prefix="target_cloud_"),
        component_synapse_table=_payload_to_dataframe(
            payload,
            COMPONENT_SYNAPSE_COLUMN_TYPES,
            prefix="component_synapse_",
        ),
    )


def load_edge_synapses(path: str | Path) -> pd.DataFrame:
    return load_edge_coupling_bundle(path).synapse_table.copy()


def lookup_inbound_synapses(
    root_id: int,
    *,
    processed_coupling_dir: str | Path,
    pre_root_id: int | None = None,
) -> pd.DataFrame:
    bundle_paths = build_root_coupling_bundle_paths(root_id, processed_coupling_dir=processed_coupling_dir)
    anchor_map = load_root_anchor_map(bundle_paths.incoming_anchor_map_path)
    return _slice_anchor_map(anchor_map, peer_root_id=pre_root_id)


def lookup_outbound_synapses(
    root_id: int,
    *,
    processed_coupling_dir: str | Path,
    post_root_id: int | None = None,
) -> pd.DataFrame:
    bundle_paths = build_root_coupling_bundle_paths(root_id, processed_coupling_dir=processed_coupling_dir)
    anchor_map = load_root_anchor_map(bundle_paths.outgoing_anchor_map_path)
    return _slice_anchor_map(anchor_map, peer_root_id=post_root_id)


def lookup_edge_synapses(
    pre_root_id: int,
    post_root_id: int,
    *,
    processed_coupling_dir: str | Path,
) -> pd.DataFrame:
    return lookup_edge_coupling_bundle(
        pre_root_id,
        post_root_id,
        processed_coupling_dir=processed_coupling_dir,
    ).synapse_table.copy()


def lookup_edge_coupling_bundle(
    pre_root_id: int,
    post_root_id: int,
    *,
    processed_coupling_dir: str | Path,
) -> EdgeCouplingBundle:
    path = build_edge_coupling_bundle_path(
        pre_root_id,
        post_root_id,
        processed_coupling_dir=processed_coupling_dir,
    )
    return load_edge_coupling_bundle(path)


def lookup_edge_coupling_components(
    pre_root_id: int,
    post_root_id: int,
    *,
    processed_coupling_dir: str | Path,
) -> pd.DataFrame:
    return lookup_edge_coupling_bundle(
        pre_root_id,
        post_root_id,
        processed_coupling_dir=processed_coupling_dir,
    ).component_table.copy()


def lookup_edge_blocked_synapses(
    pre_root_id: int,
    post_root_id: int,
    *,
    processed_coupling_dir: str | Path,
) -> pd.DataFrame:
    return lookup_edge_coupling_bundle(
        pre_root_id,
        post_root_id,
        processed_coupling_dir=processed_coupling_dir,
    ).blocked_synapse_table.copy()


def _missing_registry_summary(
    *,
    root_ids: list[int],
    registry_path: Path,
    processed_coupling_dir: str | Path,
) -> dict[str, Any]:
    missing_bundles = {
        root_id: build_coupling_bundle_metadata(
            root_id=root_id,
            processed_coupling_dir=processed_coupling_dir,
            local_synapse_registry_status=ASSET_STATUS_MISSING,
            incoming_anchor_map_status=ASSET_STATUS_MISSING,
            outgoing_anchor_map_status=ASSET_STATUS_MISSING,
            coupling_index_status=ASSET_STATUS_MISSING,
            edge_bundles=[],
        )
        for root_id in root_ids
    }
    return {
        "schema_version": SYNAPSE_ANCHOR_MAP_VERSION,
        "processed_coupling_dir": str(Path(processed_coupling_dir).resolve()),
        "synapse_registry_path": str(registry_path),
        "coupling_assembly": normalize_coupling_assembly_config(None),
        "synapse_count": 0,
        "edge_count": 0,
        "bundle_metadata_by_root": missing_bundles,
        "root_summaries": {
            root_id: {
                "incoming_synapse_count": 0,
                "outgoing_synapse_count": 0,
                "incoming_anchor_map_status": ASSET_STATUS_MISSING,
                "outgoing_anchor_map_status": ASSET_STATUS_MISSING,
                "coupling_index_status": ASSET_STATUS_MISSING,
                "incoming_edge_count": 0,
                "outgoing_edge_count": 0,
                "status": ASSET_STATUS_MISSING,
                "reason": "missing_local_synapse_registry",
            }
            for root_id in root_ids
        },
        "reason": "missing_local_synapse_registry",
    }


def _project_role_lookup(*, neuron_registry: pd.DataFrame | None) -> dict[int, str]:
    if neuron_registry is None or neuron_registry.empty:
        return {}
    required = {"root_id", "project_role"}
    if not required.issubset(neuron_registry.columns):
        return {}
    return {
        int(row.root_id): str(row.project_role or ROLE_CONTEXT_ONLY)
        for row in neuron_registry.loc[:, ["root_id", "project_role"]].itertuples(index=False)
    }


def _build_root_context(
    *,
    root_id: int,
    project_role: str,
    root_synapses: pd.DataFrame,
    meshes_raw_dir: str | Path,
    skeletons_raw_dir: str | Path,
    processed_mesh_dir: str | Path,
    processed_graph_dir: str | Path,
) -> RootContext:
    bundle_paths = build_geometry_bundle_paths(
        root_id,
        meshes_raw_dir=meshes_raw_dir,
        skeletons_raw_dir=skeletons_raw_dir,
        processed_mesh_dir=processed_mesh_dir,
        processed_graph_dir=processed_graph_dir,
    )
    surface_vertices, surface_to_patch, patch_centroids, patch_radii, surface_reason = _load_surface_patch_geometry(
        surface_graph_path=bundle_paths.surface_graph_path,
        patch_graph_path=bundle_paths.patch_graph_path,
    )
    skeleton_node_ids, skeleton_points, skeleton_local_scales, skeleton_reason = _load_skeleton_geometry(
        bundle_paths.raw_skeleton_path
    )
    point_incoming_anchor, point_incoming_radius, point_incoming_reason = _build_point_anchor_proxy(
        root_synapses.loc[root_synapses["post_root_id"] == int(root_id)],
        relation_to_root=INCOMING_RELATION,
    )
    point_outgoing_anchor, point_outgoing_radius, point_outgoing_reason = _build_point_anchor_proxy(
        root_synapses.loc[root_synapses["pre_root_id"] == int(root_id)],
        relation_to_root=OUTGOING_RELATION,
    )
    supported_modes = tuple(ROLE_SUPPORTED_MODES.get(str(project_role), ROLE_SUPPORTED_MODES[ROLE_SURFACE_SIMULATED]))
    return RootContext(
        root_id=int(root_id),
        project_role=str(project_role),
        supported_modes=supported_modes,
        surface_vertices=surface_vertices,
        surface_support_index=_build_root_local_nearest_neighbor_index(surface_vertices),
        surface_to_patch=surface_to_patch,
        patch_centroids=patch_centroids,
        patch_radii=patch_radii,
        skeleton_node_ids=skeleton_node_ids,
        skeleton_points=skeleton_points,
        skeleton_support_index=_build_root_local_nearest_neighbor_index(skeleton_points),
        skeleton_local_scales=skeleton_local_scales,
        point_incoming_anchor=point_incoming_anchor,
        point_incoming_radius=float(point_incoming_radius),
        point_outgoing_anchor=point_outgoing_anchor,
        point_outgoing_radius=float(point_outgoing_radius),
        surface_unavailable_reason=surface_reason,
        skeleton_unavailable_reason=skeleton_reason,
        point_incoming_unavailable_reason=point_incoming_reason,
        point_outgoing_unavailable_reason=point_outgoing_reason,
    )


def _load_surface_patch_geometry(
    *,
    surface_graph_path: Path,
    patch_graph_path: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, str]:
    if not surface_graph_path.exists() or not patch_graph_path.exists():
        return (
            np.empty((0, 3), dtype=np.float64),
            np.empty(0, dtype=np.int32),
            np.empty((0, 3), dtype=np.float64),
            np.empty(0, dtype=np.float64),
            "surface_patch_assets_missing",
        )
    try:
        with np.load(surface_graph_path, allow_pickle=False) as surface_payload:
            vertices = np.asarray(surface_payload["vertices"], dtype=np.float64)
            surface_to_patch = np.asarray(surface_payload["surface_to_patch"], dtype=np.int32)
        with np.load(patch_graph_path, allow_pickle=False) as patch_payload:
            patch_centroids = np.asarray(patch_payload["patch_centroids"], dtype=np.float64)
            member_vertex_indices = np.asarray(patch_payload["member_vertex_indices"], dtype=np.int32)
            member_vertex_indptr = np.asarray(patch_payload["member_vertex_indptr"], dtype=np.int32)
    except Exception:
        return (
            np.empty((0, 3), dtype=np.float64),
            np.empty(0, dtype=np.int32),
            np.empty((0, 3), dtype=np.float64),
            np.empty(0, dtype=np.float64),
            "surface_patch_assets_invalid",
        )

    patch_count = int(patch_centroids.shape[0])
    if vertices.ndim != 2 or vertices.shape[1] != 3 or patch_count <= 0:
        return (
            np.empty((0, 3), dtype=np.float64),
            np.empty(0, dtype=np.int32),
            np.empty((0, 3), dtype=np.float64),
            np.empty(0, dtype=np.float64),
            "surface_patch_assets_invalid",
        )
    if surface_to_patch.shape != (vertices.shape[0],):
        return (
            np.empty((0, 3), dtype=np.float64),
            np.empty(0, dtype=np.int32),
            np.empty((0, 3), dtype=np.float64),
            np.empty(0, dtype=np.float64),
            "surface_patch_assets_invalid",
        )

    patch_radii = np.zeros(patch_count, dtype=np.float64)
    for patch_id in range(patch_count):
        start = int(member_vertex_indptr[patch_id])
        end = int(member_vertex_indptr[patch_id + 1])
        if end <= start:
            continue
        member_vertices = vertices[member_vertex_indices[start:end]]
        distances = np.linalg.norm(member_vertices - patch_centroids[patch_id], axis=1)
        patch_radii[patch_id] = float(distances.max(initial=0.0))
    return vertices, surface_to_patch, patch_centroids, patch_radii, ""


def _load_skeleton_geometry(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    if not path.exists():
        return (
            np.empty(0, dtype=np.int64),
            np.empty((0, 3), dtype=np.float64),
            np.empty(0, dtype=np.float64),
            "skeleton_asset_missing",
        )

    nodes: list[tuple[int, np.ndarray, int]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) != 7:
                    return (
                        np.empty(0, dtype=np.int64),
                        np.empty((0, 3), dtype=np.float64),
                        np.empty(0, dtype=np.float64),
                        "skeleton_asset_invalid",
                    )
                node_id = int(parts[0])
                coords = np.asarray([float(parts[2]), float(parts[3]), float(parts[4])], dtype=np.float64)
                parent_id = int(parts[6])
                nodes.append((node_id, coords, parent_id))
    except Exception:
        return (
            np.empty(0, dtype=np.int64),
            np.empty((0, 3), dtype=np.float64),
            np.empty(0, dtype=np.float64),
            "skeleton_asset_invalid",
        )

    if not nodes:
        return (
            np.empty(0, dtype=np.int64),
            np.empty((0, 3), dtype=np.float64),
            np.empty(0, dtype=np.float64),
            "skeleton_asset_empty",
        )

    node_ids = np.asarray([node_id for node_id, _coords, _parent_id in nodes], dtype=np.int64)
    points = np.vstack([coords for _node_id, coords, _parent_id in nodes]).astype(np.float64, copy=False)
    node_index = {int(node_id): idx for idx, node_id in enumerate(node_ids.tolist())}
    incident_lengths: list[list[float]] = [[] for _ in range(len(nodes))]
    for idx, (_node_id, coords, parent_id) in enumerate(nodes):
        parent_idx = node_index.get(int(parent_id))
        if parent_idx is None:
            continue
        length = float(np.linalg.norm(coords - points[parent_idx]))
        incident_lengths[idx].append(length)
        incident_lengths[parent_idx].append(length)
    local_scales = np.asarray(
        [float(np.mean(lengths)) if lengths else 0.0 for lengths in incident_lengths],
        dtype=np.float64,
    )
    return node_ids, points, local_scales, ""


def _build_point_anchor_proxy(
    root_rows: pd.DataFrame,
    *,
    relation_to_root: str,
) -> tuple[np.ndarray, float, str]:
    if root_rows.empty:
        return np.full(3, np.nan, dtype=np.float64), float("nan"), "no_root_local_synapses"

    points: list[np.ndarray] = []
    for row in root_rows.itertuples(index=False):
        query = _resolve_query_point(row, relation_to_root=relation_to_root)
        if query["blocked_reason"]:
            continue
        points.append(np.asarray(query["query_point"], dtype=np.float64))
    if not points:
        return np.full(3, np.nan, dtype=np.float64), float("nan"), "no_query_points_for_point_anchor"

    stacked = np.vstack(points)
    anchor = stacked.mean(axis=0).astype(np.float64)
    distances = np.linalg.norm(stacked - anchor, axis=1)
    radius = float(distances.max(initial=0.0))
    return anchor, radius, ""


def _build_root_local_nearest_neighbor_index(points: np.ndarray) -> RootLocalNearestNeighborIndex | None:
    normalized = np.asarray(points, dtype=np.float64)
    if normalized.ndim != 2 or normalized.shape[1] != 3 or normalized.shape[0] == 0:
        return None
    return RootLocalNearestNeighborIndex(tree=cKDTree(normalized, copy_data=False))


def _query_root_local_nearest_neighbor(
    *,
    points: np.ndarray,
    lookup: RootLocalNearestNeighborIndex | None,
    query_point: np.ndarray,
) -> tuple[int, float] | None:
    if lookup is None:
        return None

    normalized_query = np.asarray(query_point, dtype=np.float64)
    if normalized_query.shape != (3,) or not np.all(np.isfinite(normalized_query)):
        return None

    nearest_distance, nearest_index = lookup.tree.query(normalized_query, k=1)
    if not np.isfinite(nearest_distance):
        return None

    support_distance = float(nearest_distance)
    support_index = int(nearest_index)
    tie_radius = float(np.nextafter(support_distance + _NEAREST_NEIGHBOR_QUERY_EPSILON, np.inf))
    candidate_indices = np.asarray(lookup.tree.query_ball_point(normalized_query, r=tie_radius), dtype=np.int64)
    if candidate_indices.size <= 1:
        return support_index, support_distance

    candidate_indices.sort()
    candidate_points = np.asarray(points[candidate_indices], dtype=np.float64)
    candidate_residuals = candidate_points - normalized_query
    candidate_distances_sq = np.einsum("ij,ij->i", candidate_residuals, candidate_residuals, dtype=np.float64)
    minimum_distance_sq = float(candidate_distances_sq.min(initial=np.inf))
    closest_mask = candidate_distances_sq <= np.nextafter(minimum_distance_sq, np.inf)
    support_index = int(candidate_indices[np.flatnonzero(closest_mask)[0]])
    return support_index, float(np.sqrt(minimum_distance_sq))


def _build_edge_record(*, row: Any, pre_context: RootContext, post_context: RootContext) -> dict[str, Any]:
    pre_query = _resolve_query_point(row, relation_to_root=OUTGOING_RELATION)
    post_query = _resolve_query_point(row, relation_to_root=INCOMING_RELATION)
    pre_mapping = _map_query_to_anchor(
        context=pre_context,
        query=pre_query,
        relation_to_root=OUTGOING_RELATION,
    )
    post_mapping = _map_query_to_anchor(
        context=post_context,
        query=post_query,
        relation_to_root=INCOMING_RELATION,
    )
    return {
        "synapse_row_id": _text_value(getattr(row, "synapse_row_id", "")),
        "source_row_number": _int_value(getattr(row, "source_row_number", -1), default=-1),
        "synapse_id": _text_value(getattr(row, "synapse_id", "")),
        "pre_root_id": int(row.pre_root_id),
        "post_root_id": int(row.post_root_id),
        "synapse_x": _float_value(getattr(row, "x", np.nan)),
        "synapse_y": _float_value(getattr(row, "y", np.nan)),
        "synapse_z": _float_value(getattr(row, "z", np.nan)),
        "pre_source_x": _float_value(getattr(row, "pre_x", np.nan)),
        "pre_source_y": _float_value(getattr(row, "pre_y", np.nan)),
        "pre_source_z": _float_value(getattr(row, "pre_z", np.nan)),
        "post_source_x": _float_value(getattr(row, "post_x", np.nan)),
        "post_source_y": _float_value(getattr(row, "post_y", np.nan)),
        "post_source_z": _float_value(getattr(row, "post_z", np.nan)),
        "neuropil": _text_value(getattr(row, "neuropil", "")),
        "nt_type": _text_value(getattr(row, "nt_type", "")),
        "sign": _text_value(getattr(row, "sign", "")),
        "confidence": _float_value(getattr(row, "confidence", np.nan)),
        "weight": _float_value(getattr(row, "weight", np.nan)),
        "source_file": _text_value(getattr(row, "source_file", "")),
        "snapshot_version": _text_value(getattr(row, "snapshot_version", "")),
        "materialization_version": _text_value(getattr(row, "materialization_version", "")),
        **{f"pre_{key}": value for key, value in pre_mapping.items()},
        **{f"post_{key}": value for key, value in post_mapping.items()},
    }


def _resolve_query_point(row: Any, *, relation_to_root: str) -> dict[str, Any]:
    if relation_to_root == OUTGOING_RELATION:
        preferred = ("pre_x", "pre_y", "pre_z")
        preferred_source = QUERY_SOURCE_PRE
        missing_reason = "missing_presynaptic_query_coordinates"
    else:
        preferred = ("post_x", "post_y", "post_z")
        preferred_source = QUERY_SOURCE_POST
        missing_reason = "missing_postsynaptic_query_coordinates"

    preferred_point = np.asarray([_float_value(getattr(row, axis, np.nan)) for axis in preferred], dtype=np.float64)
    if np.all(np.isfinite(preferred_point)):
        return {
            "query_source": preferred_source,
            "query_point": preferred_point,
            "blocked_reason": "",
        }

    center_point = np.asarray(
        [
            _float_value(getattr(row, "x", np.nan)),
            _float_value(getattr(row, "y", np.nan)),
            _float_value(getattr(row, "z", np.nan)),
        ],
        dtype=np.float64,
    )
    if np.all(np.isfinite(center_point)):
        return {
            "query_source": QUERY_SOURCE_CENTER,
            "query_point": center_point,
            "blocked_reason": "",
        }
    return {
        "query_source": "",
        "query_point": np.full(3, np.nan, dtype=np.float64),
        "blocked_reason": missing_reason,
    }


def _map_query_to_anchor(
    *,
    context: RootContext,
    query: dict[str, Any],
    relation_to_root: str,
) -> dict[str, Any]:
    query_source = str(query["query_source"])
    query_point = np.asarray(query["query_point"], dtype=np.float64)
    blocked_reason = str(query["blocked_reason"])
    if blocked_reason:
        return _blocked_mapping(query_source=query_source, query_point=query_point, blocked_reason=blocked_reason)

    attempted_fallback_reasons: list[str] = []
    for mode_index, mode in enumerate(context.supported_modes):
        if mode == SURFACE_PATCH_CLOUD_MODE:
            result = _surface_patch_mapping(context=context, query_point=query_point)
            if result is None:
                attempted_fallback_reasons.append(
                    f"{SURFACE_PATCH_CLOUD_MODE}:{context.surface_unavailable_reason or 'unavailable'}"
                )
                continue
        elif mode == SKELETON_SEGMENT_CLOUD_MODE:
            result = _skeleton_mapping(context=context, query_point=query_point)
            if result is None:
                attempted_fallback_reasons.append(
                    f"{SKELETON_SEGMENT_CLOUD_MODE}:{context.skeleton_unavailable_reason or 'unavailable'}"
                )
                continue
        elif mode == POINT_NEURON_LUMPED_MODE:
            result = _point_mapping(context=context, query_point=query_point, relation_to_root=relation_to_root)
            if result is None:
                point_reason = (
                    context.point_outgoing_unavailable_reason
                    if relation_to_root == OUTGOING_RELATION
                    else context.point_incoming_unavailable_reason
                )
                attempted_fallback_reasons.append(
                    f"{POINT_NEURON_LUMPED_MODE}:{point_reason or 'unavailable'}"
                )
                continue
        else:
            attempted_fallback_reasons.append(f"{mode}:unsupported_mode")
            continue

        fallback_used = mode_index > 0
        quality_status = _quality_status(
            anchor_distance=float(result["anchor_distance"]),
            support_scale=float(result["support_scale"]),
        )
        quality_reason = (
            "distance_exceeds_local_support_scale"
            if quality_status == QUALITY_STATUS_WARN
            else "distance_within_local_support_scale"
        )
        fallback_reason = ";".join(attempted_fallback_reasons)
        return {
            "query_source": query_source,
            "query_x": float(query_point[0]),
            "query_y": float(query_point[1]),
            "query_z": float(query_point[2]),
            "mapping_status": MAPPING_STATUS_MAPPED_WITH_FALLBACK if fallback_used else MAPPING_STATUS_MAPPED,
            "quality_status": quality_status,
            "quality_reason": quality_reason,
            "fallback_used": bool(fallback_used),
            "fallback_reason": fallback_reason,
            "blocked_reason": "",
            **result,
        }

    blocked_reason = ";".join(attempted_fallback_reasons) or "no_supported_anchor_modes"
    return _blocked_mapping(
        query_source=query_source,
        query_point=query_point,
        blocked_reason=blocked_reason,
    )


def _surface_patch_mapping(*, context: RootContext, query_point: np.ndarray) -> dict[str, Any] | None:
    if (
        context.surface_vertices.size == 0
        or context.surface_support_index is None
        or context.patch_centroids.size == 0
        or context.surface_to_patch.size == 0
    ):
        return None
    nearest = _query_root_local_nearest_neighbor(
        points=context.surface_vertices,
        lookup=context.surface_support_index,
        query_point=query_point,
    )
    if nearest is None:
        return None
    support_index, support_distance = nearest
    patch_id = int(context.surface_to_patch[support_index])
    if patch_id < 0 or patch_id >= int(context.patch_centroids.shape[0]):
        return None
    anchor_point = np.asarray(context.patch_centroids[patch_id], dtype=np.float64)
    residual = anchor_point - query_point
    return {
        "anchor_mode": SURFACE_PATCH_CLOUD_MODE,
        "anchor_type": ANCHOR_TYPE_SURFACE_PATCH,
        "anchor_resolution": ANCHOR_RESOLUTION_COARSE_PATCH,
        "anchor_index": patch_id,
        "anchor_x": float(anchor_point[0]),
        "anchor_y": float(anchor_point[1]),
        "anchor_z": float(anchor_point[2]),
        "anchor_distance": float(np.linalg.norm(residual)),
        "anchor_residual_x": float(residual[0]),
        "anchor_residual_y": float(residual[1]),
        "anchor_residual_z": float(residual[2]),
        "support_index": support_index,
        "support_distance": support_distance,
        "support_scale": float(context.patch_radii[patch_id]) if context.patch_radii.size else 0.0,
    }


def _skeleton_mapping(*, context: RootContext, query_point: np.ndarray) -> dict[str, Any] | None:
    if context.skeleton_points.size == 0 or context.skeleton_support_index is None:
        return None
    nearest = _query_root_local_nearest_neighbor(
        points=context.skeleton_points,
        lookup=context.skeleton_support_index,
        query_point=query_point,
    )
    if nearest is None:
        return None
    support_index, support_distance = nearest
    anchor_point = np.asarray(context.skeleton_points[support_index], dtype=np.float64)
    residual = anchor_point - query_point
    return {
        "anchor_mode": SKELETON_SEGMENT_CLOUD_MODE,
        "anchor_type": ANCHOR_TYPE_SKELETON_NODE,
        "anchor_resolution": ANCHOR_RESOLUTION_SKELETON_NODE,
        "anchor_index": int(context.skeleton_node_ids[support_index]) if context.skeleton_node_ids.size else support_index,
        "anchor_x": float(anchor_point[0]),
        "anchor_y": float(anchor_point[1]),
        "anchor_z": float(anchor_point[2]),
        "anchor_distance": float(np.linalg.norm(residual)),
        "anchor_residual_x": float(residual[0]),
        "anchor_residual_y": float(residual[1]),
        "anchor_residual_z": float(residual[2]),
        "support_index": support_index,
        "support_distance": support_distance,
        "support_scale": float(context.skeleton_local_scales[support_index]) if context.skeleton_local_scales.size else 0.0,
    }


def _point_mapping(
    *,
    context: RootContext,
    query_point: np.ndarray,
    relation_to_root: str,
) -> dict[str, Any] | None:
    if relation_to_root == OUTGOING_RELATION:
        anchor_point = np.asarray(context.point_outgoing_anchor, dtype=np.float64)
        support_scale = float(context.point_outgoing_radius)
    else:
        anchor_point = np.asarray(context.point_incoming_anchor, dtype=np.float64)
        support_scale = float(context.point_incoming_radius)
    if anchor_point.shape != (3,) or not np.all(np.isfinite(anchor_point)):
        return None
    residual = anchor_point - query_point
    return {
        "anchor_mode": POINT_NEURON_LUMPED_MODE,
        "anchor_type": ANCHOR_TYPE_POINT_STATE,
        "anchor_resolution": ANCHOR_RESOLUTION_LUMPED_ROOT_STATE,
        "anchor_index": 0,
        "anchor_x": float(anchor_point[0]),
        "anchor_y": float(anchor_point[1]),
        "anchor_z": float(anchor_point[2]),
        "anchor_distance": float(np.linalg.norm(residual)),
        "anchor_residual_x": float(residual[0]),
        "anchor_residual_y": float(residual[1]),
        "anchor_residual_z": float(residual[2]),
        "support_index": 0,
        "support_distance": float(np.linalg.norm(residual)),
        "support_scale": support_scale,
    }


def _blocked_mapping(*, query_source: str, query_point: np.ndarray, blocked_reason: str) -> dict[str, Any]:
    point = np.asarray(query_point, dtype=np.float64)
    return {
        "query_source": str(query_source),
        "query_x": float(point[0]) if point.shape == (3,) else float("nan"),
        "query_y": float(point[1]) if point.shape == (3,) else float("nan"),
        "query_z": float(point[2]) if point.shape == (3,) else float("nan"),
        "mapping_status": MAPPING_STATUS_BLOCKED,
        "quality_status": QUALITY_STATUS_UNAVAILABLE,
        "quality_reason": "blocked_no_anchor",
        "fallback_used": False,
        "fallback_reason": "",
        "blocked_reason": str(blocked_reason),
        "anchor_mode": "",
        "anchor_type": "",
        "anchor_resolution": "",
        "anchor_index": -1,
        "anchor_x": float("nan"),
        "anchor_y": float("nan"),
        "anchor_z": float("nan"),
        "anchor_distance": float("nan"),
        "anchor_residual_x": float("nan"),
        "anchor_residual_y": float("nan"),
        "anchor_residual_z": float("nan"),
        "support_index": -1,
        "support_distance": float("nan"),
        "support_scale": float("nan"),
    }


def _quality_status(*, anchor_distance: float, support_scale: float) -> str:
    if not np.isfinite(anchor_distance):
        return QUALITY_STATUS_UNAVAILABLE
    effective_scale = float(support_scale) if np.isfinite(support_scale) and support_scale > 0.0 else 1.0e-6
    return QUALITY_STATUS_OK if anchor_distance <= effective_scale + 1.0e-9 else QUALITY_STATUS_WARN


def _build_root_anchor_map_table(
    edge_table: pd.DataFrame,
    *,
    root_id: int,
    relation_to_root: str,
) -> pd.DataFrame:
    if edge_table.empty:
        return pd.DataFrame(columns=ROOT_MAP_COLUMNS)

    if relation_to_root == INCOMING_RELATION:
        peer_root_column = "pre_root_id"
        prefix = "post_"
    else:
        peer_root_column = "post_root_id"
        prefix = "pre_"

    records = [
        {
            "synapse_row_id": _text_value(row.synapse_row_id),
            "source_row_number": _int_value(row.source_row_number, default=-1),
            "synapse_id": _text_value(row.synapse_id),
            "root_id": int(root_id),
            "peer_root_id": int(getattr(row, peer_root_column)),
            "pre_root_id": int(row.pre_root_id),
            "post_root_id": int(row.post_root_id),
            "neuropil": _text_value(row.neuropil),
            "nt_type": _text_value(row.nt_type),
            "sign": _text_value(row.sign),
            "confidence": _float_value(row.confidence),
            "weight": _float_value(row.weight),
            "source_file": _text_value(row.source_file),
            "snapshot_version": _text_value(row.snapshot_version),
            "materialization_version": _text_value(row.materialization_version),
            "query_source": _text_value(getattr(row, f"{prefix}query_source")),
            "query_x": _float_value(getattr(row, f"{prefix}query_x")),
            "query_y": _float_value(getattr(row, f"{prefix}query_y")),
            "query_z": _float_value(getattr(row, f"{prefix}query_z")),
            "mapping_status": _text_value(getattr(row, f"{prefix}mapping_status")),
            "quality_status": _text_value(getattr(row, f"{prefix}quality_status")),
            "quality_reason": _text_value(getattr(row, f"{prefix}quality_reason")),
            "fallback_used": bool(getattr(row, f"{prefix}fallback_used")),
            "fallback_reason": _text_value(getattr(row, f"{prefix}fallback_reason")),
            "blocked_reason": _text_value(getattr(row, f"{prefix}blocked_reason")),
            "anchor_mode": _text_value(getattr(row, f"{prefix}anchor_mode")),
            "anchor_type": _text_value(getattr(row, f"{prefix}anchor_type")),
            "anchor_resolution": _text_value(getattr(row, f"{prefix}anchor_resolution")),
            "anchor_index": _int_value(getattr(row, f"{prefix}anchor_index"), default=-1),
            "anchor_x": _float_value(getattr(row, f"{prefix}anchor_x")),
            "anchor_y": _float_value(getattr(row, f"{prefix}anchor_y")),
            "anchor_z": _float_value(getattr(row, f"{prefix}anchor_z")),
            "anchor_distance": _float_value(getattr(row, f"{prefix}anchor_distance")),
            "anchor_residual_x": _float_value(getattr(row, f"{prefix}anchor_residual_x")),
            "anchor_residual_y": _float_value(getattr(row, f"{prefix}anchor_residual_y")),
            "anchor_residual_z": _float_value(getattr(row, f"{prefix}anchor_residual_z")),
            "support_index": _int_value(getattr(row, f"{prefix}support_index"), default=-1),
            "support_distance": _float_value(getattr(row, f"{prefix}support_distance")),
            "support_scale": _float_value(getattr(row, f"{prefix}support_scale")),
        }
        for row in edge_table.itertuples(index=False)
    ]
    out = pd.DataFrame.from_records(records, columns=ROOT_MAP_COLUMNS)
    return out.sort_values(["peer_root_id", "source_row_number", "synapse_row_id"], kind="mergesort").reset_index(drop=True)


def _build_peer_index(table: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    if table.empty:
        return np.empty(0, dtype=np.int64), np.asarray([0], dtype=np.int64)
    peer_root_ids = sorted(int(value) for value in table["peer_root_id"].drop_duplicates().tolist())
    indptr = np.zeros(len(peer_root_ids) + 1, dtype=np.int64)
    offset = 0
    for index, peer_root_id in enumerate(peer_root_ids):
        count = int((table["peer_root_id"] == int(peer_root_id)).sum())
        offset += count
        indptr[index + 1] = offset
    return np.asarray(peer_root_ids, dtype=np.int64), indptr


def _root_edge_summary(
    *,
    root_id: int,
    edge_summary: Mapping[str, Any],
    relation_to_root: str,
) -> dict[str, Any]:
    pre_root_id = int(edge_summary["pre_root_id"])
    post_root_id = int(edge_summary["post_root_id"])
    return {
        "pre_root_id": pre_root_id,
        "post_root_id": post_root_id,
        "peer_root_id": pre_root_id if relation_to_root == INCOMING_RELATION else post_root_id,
        "relation_to_root": relation_to_root,
        "path": str(edge_summary["path"]),
        "status": str(edge_summary["status"]),
        "synapse_count": int(edge_summary["synapse_count"]),
        "component_count": int(edge_summary.get("component_count", 0)),
        "blocked_synapse_count": int(edge_summary.get("blocked_synapse_count", 0)),
        "source_anchor_count": int(edge_summary.get("source_anchor_count", 0)),
        "target_anchor_count": int(edge_summary.get("target_anchor_count", 0)),
        "topology_family": str(edge_summary.get("topology_family", "")),
        "kernel_family": str(edge_summary.get("kernel_family", "")),
        "sign_representation": str(edge_summary.get("sign_representation", "")),
        "delay_representation": str(edge_summary.get("delay_representation", "")),
        "delay_model": str(edge_summary.get("delay_model", "")),
        "aggregation_rule": str(edge_summary.get("aggregation_rule", "")),
        "source_cloud_normalization": str(edge_summary.get("source_cloud_normalization", "")),
        "target_cloud_normalization": str(edge_summary.get("target_cloud_normalization", "")),
        "pre_mapping_status_counts": dict(edge_summary["pre_mapping_status_counts"]),
        "post_mapping_status_counts": dict(edge_summary["post_mapping_status_counts"]),
        "pre_quality_status_counts": dict(edge_summary["pre_quality_status_counts"]),
        "post_quality_status_counts": dict(edge_summary["post_quality_status_counts"]),
    }


def _root_table_status(table: pd.DataFrame) -> str:
    if table.empty:
        return ASSET_STATUS_READY
    if any(str(value) == MAPPING_STATUS_BLOCKED for value in table["mapping_status"].tolist()):
        return "partial"
    if any(str(value) == QUALITY_STATUS_WARN for value in table["quality_status"].tolist()):
        return "partial"
    return ASSET_STATUS_READY


def _edge_table_status(table: pd.DataFrame) -> str:
    if table.empty:
        return ASSET_STATUS_READY
    status_columns = ["pre_mapping_status", "post_mapping_status"]
    quality_columns = ["pre_quality_status", "post_quality_status"]
    for column in status_columns:
        if any(str(value) == MAPPING_STATUS_BLOCKED for value in table[column].tolist()):
            return "partial"
    for column in quality_columns:
        if any(str(value) == QUALITY_STATUS_WARN for value in table[column].tolist()):
            return "partial"
    return ASSET_STATUS_READY


def _index_status(
    incoming_edges: list[dict[str, Any]],
    outgoing_edges: list[dict[str, Any]],
    incoming_table: pd.DataFrame,
    outgoing_table: pd.DataFrame,
) -> str:
    if _root_table_status(incoming_table) != ASSET_STATUS_READY or _root_table_status(outgoing_table) != ASSET_STATUS_READY:
        return "partial"
    if any(str(item["status"]) != ASSET_STATUS_READY for item in [*incoming_edges, *outgoing_edges]):
        return "partial"
    return ASSET_STATUS_READY


def _write_edge_coupling_bundle_npz(
    *,
    path: Path,
    bundle: EdgeCouplingBundle,
) -> None:
    ensure_dir(path.parent)
    payload: dict[str, Any] = {
        "meta_schema_version": _scalar_array(EDGE_COUPLING_BUNDLE_VERSION),
        "meta_bundle_kind": _scalar_array("edge_coupling_bundle"),
        "meta_pre_root_id": _scalar_array(bundle.pre_root_id),
        "meta_post_root_id": _scalar_array(bundle.post_root_id),
        "meta_status": _scalar_array(bundle.status),
        "meta_topology_family": _scalar_array(bundle.topology_family),
        "meta_kernel_family": _scalar_array(bundle.kernel_family),
        "meta_sign_representation": _scalar_array(bundle.sign_representation),
        "meta_delay_representation": _scalar_array(bundle.delay_representation),
        "meta_delay_model": _scalar_array(bundle.delay_model),
        "meta_delay_model_parameters_json": _scalar_array(
            json.dumps(bundle.delay_model_parameters, sort_keys=True)
        ),
        "meta_aggregation_rule": _scalar_array(bundle.aggregation_rule),
        "meta_missing_geometry_policy": _scalar_array(bundle.missing_geometry_policy),
        "meta_source_cloud_normalization": _scalar_array(bundle.source_cloud_normalization),
        "meta_target_cloud_normalization": _scalar_array(bundle.target_cloud_normalization),
        "meta_synapse_count": _scalar_array(len(bundle.synapse_table)),
        "meta_component_count": _scalar_array(len(bundle.component_table)),
        "meta_blocked_synapse_count": _scalar_array(len(bundle.blocked_synapse_table)),
    }
    _append_table_payload(payload, prefix="synapse_", column_types=EDGE_BUNDLE_COLUMN_TYPES, table=bundle.synapse_table)
    _append_table_payload(
        payload,
        prefix="component_",
        column_types=COMPONENT_COLUMN_TYPES,
        table=bundle.component_table,
    )
    _append_table_payload(
        payload,
        prefix="blocked_synapse_",
        column_types=EDGE_BUNDLE_COLUMN_TYPES,
        table=bundle.blocked_synapse_table,
    )
    _append_table_payload(
        payload,
        prefix="source_anchor_",
        column_types=ANCHOR_COLUMN_TYPES,
        table=bundle.source_anchor_table,
    )
    _append_table_payload(
        payload,
        prefix="target_anchor_",
        column_types=ANCHOR_COLUMN_TYPES,
        table=bundle.target_anchor_table,
    )
    _append_table_payload(
        payload,
        prefix="source_cloud_",
        column_types=CLOUD_COLUMN_TYPES,
        table=bundle.source_cloud_table,
    )
    _append_table_payload(
        payload,
        prefix="target_cloud_",
        column_types=CLOUD_COLUMN_TYPES,
        table=bundle.target_cloud_table,
    )
    _append_table_payload(
        payload,
        prefix="component_synapse_",
        column_types=COMPONENT_SYNAPSE_COLUMN_TYPES,
        table=bundle.component_synapse_table,
    )
    np.savez_compressed(path, **payload)


def _write_table_npz(
    *,
    path: Path,
    column_types: Mapping[str, str],
    table: pd.DataFrame,
    metadata: Mapping[str, Any],
    extra_arrays: Mapping[str, np.ndarray] | None = None,
) -> None:
    ensure_dir(path.parent)
    payload: dict[str, Any] = {
    }
    for key, value in metadata.items():
        payload[key] = _scalar_array(value)
    if extra_arrays:
        for key, value in extra_arrays.items():
            payload[key] = np.asarray(value)
    _append_table_payload(payload, prefix="", column_types=column_types, table=table)
    np.savez_compressed(path, **payload)


def _append_table_payload(
    payload: dict[str, Any],
    *,
    prefix: str,
    column_types: Mapping[str, str],
    table: pd.DataFrame,
) -> None:
    payload[f"{prefix}column_order"] = np.asarray(list(column_types), dtype=np.str_)
    for column, kind in column_types.items():
        series = table[column] if column in table.columns else pd.Series([], dtype="object")
        payload[f"{prefix}{column}"] = _series_to_array(series, kind=kind)


def _series_to_array(series: pd.Series, *, kind: str) -> np.ndarray:
    values = series.tolist()
    if kind == "string":
        return np.asarray([_text_value(value) for value in values], dtype=np.str_)
    if kind == "int":
        return np.asarray([_int_value(value, default=-1) for value in values], dtype=np.int64)
    if kind == "float":
        return np.asarray([_float_value(value) for value in values], dtype=np.float64)
    if kind == "bool":
        return np.asarray([bool(value) for value in values], dtype=np.bool_)
    raise ValueError(f"Unsupported column kind {kind!r}.")


def _payload_to_dataframe(
    payload: Mapping[str, np.ndarray],
    column_types: Mapping[str, str],
    *,
    prefix: str = "",
) -> pd.DataFrame:
    data: dict[str, Any] = {}
    for column in column_types:
        payload_key = f"{prefix}{column}"
        if payload_key not in payload:
            if column_types[column] == "string":
                data[column] = np.asarray([], dtype=np.str_)
            elif column_types[column] == "int":
                data[column] = np.asarray([], dtype=np.int64)
            elif column_types[column] == "float":
                data[column] = np.asarray([], dtype=np.float64)
            elif column_types[column] == "bool":
                data[column] = np.asarray([], dtype=np.bool_)
            continue
        array = np.asarray(payload[payload_key])
        if column_types[column] == "string":
            data[column] = array.astype(str)
        elif column_types[column] == "int":
            data[column] = array.astype(np.int64, copy=False)
        elif column_types[column] == "float":
            data[column] = array.astype(np.float64, copy=False)
        elif column_types[column] == "bool":
            data[column] = array.astype(np.bool_, copy=False)
    return pd.DataFrame(data, columns=list(column_types))


def _load_npz_payload(path: str | Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as payload:
        return {key: payload[key] for key in payload.files}


def _slice_anchor_map(anchor_map: LoadedRootAnchorMap, *, peer_root_id: int | None) -> pd.DataFrame:
    if peer_root_id is None:
        return anchor_map.table.copy()
    normalized_peer_root_id = int(peer_root_id)
    if anchor_map.peer_root_ids.size:
        matches = np.flatnonzero(anchor_map.peer_root_ids == normalized_peer_root_id)
        if matches.size:
            offset = int(matches[0])
            start = int(anchor_map.peer_root_indptr[offset])
            end = int(anchor_map.peer_root_indptr[offset + 1])
            return anchor_map.table.iloc[start:end].reset_index(drop=True)
    return anchor_map.table.iloc[0:0].copy().reset_index(drop=True)


def _count_values(series: pd.Series) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in series.tolist():
        label = _text_value(value)
        counts[label] = counts.get(label, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _scalar_array(value: Any) -> np.ndarray:
    if isinstance(value, bool):
        return np.asarray(value, dtype=np.bool_)
    if isinstance(value, (int, np.integer)):
        return np.asarray(int(value), dtype=np.int64)
    if isinstance(value, (float, np.floating)):
        return np.asarray(float(value), dtype=np.float64)
    return np.asarray(_text_value(value), dtype=np.str_)


def _payload_scalar(value: np.ndarray) -> Any:
    array = np.asarray(value)
    if array.shape == ():
        return array.item()
    if array.size == 1:
        return array.reshape(()).item()
    return array


def _json_mapping_scalar(value: np.ndarray) -> dict[str, Any]:
    scalar = _payload_scalar(value)
    if not scalar:
        return {}
    parsed = json.loads(str(scalar))
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON mapping payload.")
    return parsed


def _int_value(value: Any, *, default: int) -> int:
    if value is None or value is pd.NA:
        return int(default)
    try:
        if pd.isna(value):  # type: ignore[arg-type]
            return int(default)
    except Exception:
        pass
    return int(value)


def _float_value(value: Any) -> float:
    if value is None or value is pd.NA:
        return float("nan")
    try:
        if pd.isna(value):  # type: ignore[arg-type]
            return float("nan")
    except Exception:
        pass
    return float(value)


def _text_value(value: Any) -> str:
    if value is None or value is pd.NA:
        return ""
    try:
        if pd.isna(value):  # type: ignore[arg-type]
            return ""
    except Exception:
        pass
    return str(value)
