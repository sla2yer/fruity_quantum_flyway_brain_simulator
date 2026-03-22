from __future__ import annotations

import copy
import hashlib
import json
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse as sp

from .io_utils import write_deterministic_npz, write_json
from .surface_operators import deserialize_sparse_matrix, serialize_sparse_matrix
from .surface_wave_solver import estimate_sparse_operator_spectral_radius


SKELETON_RUNTIME_ASSET_CONTRACT_VERSION = "skeleton_runtime_asset.v1"
SKELETON_RUNTIME_APPROXIMATION_FAMILY = "mass_normalized_tree_graph_wave.v1"
SKELETON_RUNTIME_GRAPH_OPERATOR_FAMILY = "mass_normalized_skeleton_laplacian"
SKELETON_RUNTIME_ASSET_KEY = "skeleton_runtime_asset"


@dataclass(frozen=True)
class SkeletonRuntimeAssetPaths:
    root_id: int
    data_path: Path
    metadata_path: Path


@dataclass(frozen=True)
class SkeletonRuntimeAsset:
    metadata: dict[str, Any]
    node_ids: np.ndarray
    node_coordinates: np.ndarray
    parent_indices: np.ndarray
    segment_lengths: np.ndarray
    node_mass: np.ndarray
    readout_weights: np.ndarray
    branch_mask: np.ndarray
    leaf_mask: np.ndarray
    graph_operator: sp.csr_matrix

    @property
    def root_id(self) -> int:
        return int(self.metadata["root_id"])

    @property
    def node_count(self) -> int:
        return int(self.node_ids.shape[0])

    @property
    def edge_count(self) -> int:
        return int(self.node_count - 1)

    @property
    def asset_hash(self) -> str:
        return str(self.metadata["asset_hash"])


def build_skeleton_runtime_asset_paths(
    root_id: int,
    *,
    processed_graph_dir: str | Path,
) -> SkeletonRuntimeAssetPaths:
    root_label = str(int(root_id))
    graph_dir = Path(processed_graph_dir).resolve()
    return SkeletonRuntimeAssetPaths(
        root_id=int(root_id),
        data_path=graph_dir / f"{root_label}_skeleton_runtime_asset.npz",
        metadata_path=graph_dir / f"{root_label}_skeleton_runtime_asset.json",
    )


def build_skeleton_runtime_asset_record(
    *,
    root_id: int,
    raw_skeleton_path: str | Path,
    processed_graph_dir: str | Path,
) -> dict[str, Any]:
    metadata = materialize_skeleton_runtime_asset(
        root_id=root_id,
        raw_skeleton_path=raw_skeleton_path,
        processed_graph_dir=processed_graph_dir,
    )
    return {
        "root_id": int(metadata["root_id"]),
        "contract_version": str(metadata["contract_version"]),
        "approximation_family": str(metadata["approximation_family"]),
        "graph_operator_family": str(metadata["graph_operator_family"]),
        "state_layout": str(metadata["state_layout"]),
        "projection_surface": str(metadata["projection_surface"]),
        "projection_layout": str(metadata["projection_layout"]),
        "source_injection_strategy": str(metadata["source_injection_strategy"]),
        "raw_skeleton_path": str(metadata["raw_skeleton_path"]),
        "data_path": str(metadata["asset_data_path"]),
        "metadata_path": str(metadata["metadata_path"]),
        "path": str(metadata["metadata_path"]),
        "status": "ready",
        "exists": True,
        "asset_hash": str(metadata["asset_hash"]),
        "node_count": int(metadata["counts"]["node_count"]),
        "edge_count": int(metadata["counts"]["edge_count"]),
        "branch_point_count": int(metadata["counts"]["branch_point_count"]),
        "leaf_count": int(metadata["counts"]["leaf_count"]),
        "readout_semantics": copy.deepcopy(metadata["readout_semantics"]),
        "operator": copy.deepcopy(metadata["operator"]),
    }


def materialize_skeleton_runtime_asset(
    *,
    root_id: int,
    raw_skeleton_path: str | Path,
    processed_graph_dir: str | Path,
) -> dict[str, Any]:
    normalized_root_id = int(root_id)
    skeleton_path = Path(raw_skeleton_path).resolve()
    if not skeleton_path.exists():
        raise ValueError(
            f"Skeleton runtime asset for root {normalized_root_id} requires a local raw "
            f"SWC at {skeleton_path}."
        )

    paths = build_skeleton_runtime_asset_paths(
        normalized_root_id,
        processed_graph_dir=processed_graph_dir,
    )
    payload = _build_runtime_asset_payload(
        root_id=normalized_root_id,
        raw_skeleton_path=skeleton_path,
    )
    write_deterministic_npz(payload["arrays"], paths.data_path)
    metadata = copy.deepcopy(payload["metadata"])
    metadata["asset_data_path"] = str(paths.data_path)
    metadata["metadata_path"] = str(paths.metadata_path)
    write_json(metadata, paths.metadata_path)
    return parse_skeleton_runtime_asset_metadata(metadata)


def load_skeleton_runtime_asset(metadata_path: str | Path) -> SkeletonRuntimeAsset:
    metadata = load_skeleton_runtime_asset_metadata(metadata_path)
    data_path = Path(str(metadata["asset_data_path"])).resolve()
    with np.load(data_path, allow_pickle=False) as payload:
        arrays = {key: np.asarray(payload[key]) for key in payload.files}
    graph_operator = deserialize_sparse_matrix(arrays, prefix="graph_operator")
    return SkeletonRuntimeAsset(
        metadata=metadata,
        node_ids=np.asarray(arrays["node_ids"], dtype=np.int64),
        node_coordinates=np.asarray(arrays["node_coordinates"], dtype=np.float64),
        parent_indices=np.asarray(arrays["parent_indices"], dtype=np.int32),
        segment_lengths=np.asarray(arrays["segment_lengths"], dtype=np.float64),
        node_mass=np.asarray(arrays["node_mass"], dtype=np.float64),
        readout_weights=np.asarray(arrays["readout_weights"], dtype=np.float64),
        branch_mask=np.asarray(arrays["branch_mask"], dtype=bool),
        leaf_mask=np.asarray(arrays["leaf_mask"], dtype=bool),
        graph_operator=graph_operator,
    )


def load_skeleton_runtime_asset_metadata(metadata_path: str | Path) -> dict[str, Any]:
    path = Path(metadata_path).resolve()
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_skeleton_runtime_asset_metadata(payload)


def parse_skeleton_runtime_asset_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Skeleton runtime asset metadata must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "approximation_family",
        "graph_operator_family",
        "root_id",
        "raw_skeleton_path",
        "asset_data_path",
        "metadata_path",
        "state_layout",
        "projection_surface",
        "projection_layout",
        "source_injection_strategy",
        "readout_semantics",
        "counts",
        "operator",
        "asset_hash",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "Skeleton runtime asset metadata is missing required fields: "
            f"{missing_fields!r}."
        )
    if normalized["contract_version"] != SKELETON_RUNTIME_ASSET_CONTRACT_VERSION:
        raise ValueError(
            "Skeleton runtime asset contract_version does not match "
            f"{SKELETON_RUNTIME_ASSET_CONTRACT_VERSION!r}."
        )
    if not isinstance(normalized["counts"], Mapping):
        raise ValueError("Skeleton runtime asset counts must be a mapping.")
    if not isinstance(normalized["operator"], Mapping):
        raise ValueError("Skeleton runtime asset operator must be a mapping.")
    if not isinstance(normalized["readout_semantics"], Mapping):
        raise ValueError("Skeleton runtime asset readout_semantics must be a mapping.")
    normalized["root_id"] = int(normalized["root_id"])
    normalized["raw_skeleton_path"] = str(Path(normalized["raw_skeleton_path"]).resolve())
    normalized["asset_data_path"] = str(Path(normalized["asset_data_path"]).resolve())
    normalized["metadata_path"] = str(Path(normalized["metadata_path"]).resolve())
    normalized["asset_hash"] = str(normalized["asset_hash"])
    normalized["counts"] = {
        "node_count": int(normalized["counts"]["node_count"]),
        "edge_count": int(normalized["counts"]["edge_count"]),
        "branch_point_count": int(normalized["counts"]["branch_point_count"]),
        "leaf_count": int(normalized["counts"]["leaf_count"]),
        "root_index": int(normalized["counts"]["root_index"]),
    }
    normalized["operator"] = copy.deepcopy(dict(normalized["operator"]))
    normalized["readout_semantics"] = copy.deepcopy(dict(normalized["readout_semantics"]))
    return normalized


def _build_runtime_asset_payload(
    *,
    root_id: int,
    raw_skeleton_path: Path,
) -> dict[str, Any]:
    tree = _parse_rooted_swc_tree(raw_skeleton_path)
    adjacency = _build_weighted_adjacency(
        parent_indices=tree["parent_indices"],
        segment_lengths=tree["segment_lengths"],
    )
    degree = np.asarray(adjacency.getnnz(axis=1), dtype=np.int32)
    node_mass = _compute_node_mass(
        parent_indices=tree["parent_indices"],
        segment_lengths=tree["segment_lengths"],
    )
    if np.any(node_mass <= 0.0):
        raise ValueError(
            f"Skeleton runtime asset for root {root_id} produced non-positive node mass "
            f"from {raw_skeleton_path}."
        )
    graph_laplacian = _build_graph_laplacian(adjacency)
    mass_inverse = sp.diags(1.0 / node_mass, offsets=0, dtype=np.float64, format="csr")
    graph_operator = (mass_inverse @ graph_laplacian).tocsr()
    graph_operator.eliminate_zeros()
    graph_operator.sort_indices()
    spectral_radius = estimate_sparse_operator_spectral_radius(graph_operator)
    if spectral_radius <= 0.0:
        raise ValueError(
            f"Skeleton runtime asset for root {root_id} must expose a positive graph "
            "spectral radius."
        )

    branch_mask = degree > 2
    branch_mask[int(tree["root_index"])] = bool(degree[int(tree["root_index"])] > 1)
    leaf_mask = degree == 1
    leaf_mask[int(tree["root_index"])] = False
    readout_weights = node_mass / float(np.sum(node_mass))
    asset_hash = _hash_runtime_asset(
        node_ids=tree["node_ids"],
        node_coordinates=tree["node_coordinates"],
        parent_indices=tree["parent_indices"],
        segment_lengths=tree["segment_lengths"],
        node_mass=node_mass,
        readout_weights=readout_weights,
        graph_operator=graph_operator,
    )

    arrays = {
        "root_id": np.asarray([root_id], dtype=np.int64),
        "node_ids": tree["node_ids"].astype(np.int64, copy=False),
        "node_coordinates": tree["node_coordinates"].astype(np.float64, copy=False),
        "parent_indices": tree["parent_indices"].astype(np.int32, copy=False),
        "segment_lengths": tree["segment_lengths"].astype(np.float64, copy=False),
        "node_mass": node_mass.astype(np.float64, copy=False),
        "readout_weights": readout_weights.astype(np.float64, copy=False),
        "branch_mask": branch_mask.astype(bool, copy=False),
        "leaf_mask": leaf_mask.astype(bool, copy=False),
        **{
            f"graph_operator_{key}": value
            for key, value in serialize_sparse_matrix(
                graph_operator,
                data_dtype=np.float64,
            ).items()
        },
    }
    metadata = {
        "contract_version": SKELETON_RUNTIME_ASSET_CONTRACT_VERSION,
        "approximation_family": SKELETON_RUNTIME_APPROXIMATION_FAMILY,
        "graph_operator_family": SKELETON_RUNTIME_GRAPH_OPERATOR_FAMILY,
        "root_id": int(root_id),
        "raw_skeleton_path": str(raw_skeleton_path),
        "state_layout": "activation_velocity_by_skeleton_node",
        "projection_surface": "skeleton_anchor_cloud",
        "projection_layout": "asset_node_order_activation",
        "source_injection_strategy": "uniform_per_node_fill_from_shared_root_scalar",
        "readout_semantics": {
            "shared_readout_value_semantics": "shared_downstream_activation",
            "root_summary_semantics": "mass_weighted_mean_activation",
            "projection_semantics": "identity_projection_in_asset_node_order",
        },
        "counts": {
            "node_count": int(tree["node_ids"].shape[0]),
            "edge_count": int(tree["node_ids"].shape[0] - 1),
            "branch_point_count": int(np.count_nonzero(branch_mask)),
            "leaf_count": int(np.count_nonzero(leaf_mask)),
            "root_index": int(tree["root_index"]),
        },
        "operator": {
            "serialization": "npz_csr_and_dense_arrays.v1",
            "normalization": "mass_normalized",
            "edge_weight_semantics": "inverse_segment_length",
            "node_mass_semantics": "half_incident_segment_length",
            "spectral_radius": float(spectral_radius),
        },
        "asset_hash": asset_hash,
    }
    return {
        "arrays": arrays,
        "metadata": metadata,
    }


def _parse_rooted_swc_tree(path: Path) -> dict[str, Any]:
    nodes_by_id: dict[int, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 7:
                raise ValueError(
                    f"Skeleton runtime asset requires seven-column SWC rows; {path} line "
                    f"{line_number} had {len(parts)} columns."
                )
            node_id = int(parts[0])
            if node_id in nodes_by_id:
                raise ValueError(
                    f"Skeleton runtime asset requires unique SWC node IDs; {path} "
                    f"repeated node_id {node_id}."
                )
            coordinates = np.asarray(
                [float(parts[2]), float(parts[3]), float(parts[4])],
                dtype=np.float64,
            )
            radius = float(parts[5])
            parent_id = int(parts[6])
            if not np.all(np.isfinite(coordinates)) or not np.isfinite(radius):
                raise ValueError(
                    f"Skeleton runtime asset requires finite coordinates and radius; {path} "
                    f"line {line_number} was invalid."
                )
            nodes_by_id[node_id] = {
                "node_id": node_id,
                "coordinates": coordinates,
                "radius": radius,
                "parent_id": parent_id,
            }

    if not nodes_by_id:
        raise ValueError("Skeleton runtime asset requires a non-empty SWC skeleton.")

    root_ids = sorted(
        node_id
        for node_id, node in nodes_by_id.items()
        if int(node["parent_id"]) == -1
    )
    if len(root_ids) != 1:
        raise ValueError(
            "Skeleton runtime asset requires exactly one SWC root node with parent_id -1."
        )
    root_id = int(root_ids[0])

    child_ids_by_parent: dict[int, list[int]] = {node_id: [] for node_id in nodes_by_id}
    for node_id, node in nodes_by_id.items():
        parent_id = int(node["parent_id"])
        if node_id == root_id:
            continue
        if parent_id not in nodes_by_id:
            raise ValueError(
                f"Skeleton runtime asset requires parent IDs to exist locally; "
                f"{path} references missing parent_id {parent_id} for node_id {node_id}."
            )
        child_ids_by_parent[parent_id].append(node_id)

    for child_ids in child_ids_by_parent.values():
        child_ids.sort()

    ordered_node_ids: list[int] = []
    queue: deque[int] = deque([root_id])
    visited: set[int] = set()
    while queue:
        current = int(queue.popleft())
        if current in visited:
            raise ValueError(
                f"Skeleton runtime asset requires an acyclic rooted tree; {path} contains "
                f"a repeated traversal node {current}."
            )
        visited.add(current)
        ordered_node_ids.append(current)
        queue.extend(child_ids_by_parent[current])

    if len(visited) != len(nodes_by_id):
        missing = sorted(set(nodes_by_id) - visited)
        raise ValueError(
            "Skeleton runtime asset requires one connected rooted tree; unreachable node_ids "
            f"{missing!r} were found in {path}."
        )
    if len(ordered_node_ids) < 2:
        raise ValueError(
            "Skeleton runtime asset requires at least one segment; one-node skeletons are "
            "scientifically unsupported for this morphology class."
        )

    index_by_node_id = {
        int(node_id): index
        for index, node_id in enumerate(ordered_node_ids)
    }
    parent_indices = np.full(len(ordered_node_ids), -1, dtype=np.int32)
    segment_lengths = np.zeros(len(ordered_node_ids), dtype=np.float64)
    node_coordinates = np.empty((len(ordered_node_ids), 3), dtype=np.float64)
    for index, node_id in enumerate(ordered_node_ids):
        node = nodes_by_id[node_id]
        coordinates = np.asarray(node["coordinates"], dtype=np.float64)
        node_coordinates[index, :] = coordinates
        parent_id = int(node["parent_id"])
        if parent_id == -1:
            continue
        parent_index = index_by_node_id[parent_id]
        parent_indices[index] = int(parent_index)
        segment_length = float(
            np.linalg.norm(coordinates - node_coordinates[parent_index, :])
        )
        if not np.isfinite(segment_length) or segment_length <= 0.0:
            raise ValueError(
                "Skeleton runtime asset requires positive finite parent-child segment "
                f"lengths; node_id {node_id} in {path} was invalid."
            )
        segment_lengths[index] = segment_length

    return {
        "node_ids": np.asarray(ordered_node_ids, dtype=np.int64),
        "node_coordinates": node_coordinates,
        "parent_indices": parent_indices,
        "segment_lengths": segment_lengths,
        "root_index": 0,
    }


def _build_weighted_adjacency(
    *,
    parent_indices: np.ndarray,
    segment_lengths: np.ndarray,
) -> sp.csr_matrix:
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    node_count = int(parent_indices.shape[0])
    for node_index in range(node_count):
        parent_index = int(parent_indices[node_index])
        if parent_index < 0:
            continue
        weight = 1.0 / float(segment_lengths[node_index])
        rows.extend([node_index, parent_index])
        cols.extend([parent_index, node_index])
        data.extend([weight, weight])
    adjacency = sp.csr_matrix(
        (np.asarray(data, dtype=np.float64), (rows, cols)),
        shape=(node_count, node_count),
        dtype=np.float64,
    )
    adjacency.eliminate_zeros()
    adjacency.sort_indices()
    return adjacency


def _build_graph_laplacian(adjacency: sp.csr_matrix) -> sp.csr_matrix:
    degree = np.asarray(adjacency.sum(axis=1)).ravel().astype(np.float64, copy=False)
    laplacian = sp.diags(degree, offsets=0, dtype=np.float64, format="csr") - adjacency
    laplacian.eliminate_zeros()
    laplacian.sort_indices()
    return laplacian


def _compute_node_mass(
    *,
    parent_indices: np.ndarray,
    segment_lengths: np.ndarray,
) -> np.ndarray:
    mass = np.zeros(parent_indices.shape[0], dtype=np.float64)
    for node_index in range(parent_indices.shape[0]):
        parent_index = int(parent_indices[node_index])
        if parent_index < 0:
            continue
        half_length = 0.5 * float(segment_lengths[node_index])
        mass[node_index] += half_length
        mass[parent_index] += half_length
    return mass


def _hash_runtime_asset(
    *,
    node_ids: np.ndarray,
    node_coordinates: np.ndarray,
    parent_indices: np.ndarray,
    segment_lengths: np.ndarray,
    node_mass: np.ndarray,
    readout_weights: np.ndarray,
    graph_operator: sp.csr_matrix,
) -> str:
    hasher = hashlib.sha256()
    for array in (
        np.asarray(node_ids, dtype=np.int64),
        np.asarray(node_coordinates, dtype=np.float64),
        np.asarray(parent_indices, dtype=np.int32),
        np.asarray(segment_lengths, dtype=np.float64),
        np.asarray(node_mass, dtype=np.float64),
        np.asarray(readout_weights, dtype=np.float64),
        np.asarray(graph_operator.data, dtype=np.float64),
        np.asarray(graph_operator.indices, dtype=np.int32),
        np.asarray(graph_operator.indptr, dtype=np.int32),
        np.asarray(graph_operator.shape, dtype=np.int32),
    ):
        contiguous = np.ascontiguousarray(array)
        hasher.update(contiguous.view(np.uint8))
    return hasher.hexdigest()
