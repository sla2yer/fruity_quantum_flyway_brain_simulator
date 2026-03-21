from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse as sp
import trimesh


GEOMETRY_DESCRIPTOR_VERSION = "geometry_descriptors.v1"
GEOMETRY_QA_VERSION = "geometry_qa.v1"
EPSILON = 1e-12
TOP_COMPONENT_COUNTS = 8

DEFAULT_GEOMETRY_QA_THRESHOLDS: dict[str, dict[str, Any]] = {
    "simplified_component_count_delta": {
        "warn": None,
        "fail": 0.0,
        "blocking": True,
        "description": "Simplification should not change the number of connected components.",
    },
    "simplified_surface_area_rel_error": {
        "warn": 0.15,
        "fail": 0.30,
        "blocking": True,
        "description": "Surface area should stay close enough for later operator scaling.",
    },
    "simplified_extent_rel_error_max": {
        "warn": 0.10,
        "fail": 0.20,
        "blocking": True,
        "description": "Axis-aligned extents should not drift enough to change propagation length scales.",
    },
    "simplified_centroid_shift_fraction_of_diagonal": {
        "warn": 0.05,
        "fail": 0.10,
        "blocking": False,
        "description": "Large centroid shifts indicate global translation or asymmetric distortion.",
    },
    "simplified_volume_rel_error": {
        "warn": 0.20,
        "fail": 0.40,
        "blocking": False,
        "description": "Volume drift is informative when both meshes are watertight, but not a hard blocker.",
    },
    "coarse_component_count_delta": {
        "warn": None,
        "fail": 0.0,
        "blocking": True,
        "description": "Patch graph connectivity should preserve the simplified surface component structure.",
    },
    "coarse_surface_vertex_coverage_gap": {
        "warn": None,
        "fail": 0.0,
        "blocking": True,
        "description": "Every simplified surface vertex should map to exactly one coarse patch.",
    },
    "coarse_max_patch_vertex_fraction": {
        "warn": 0.60,
        "fail": 0.80,
        "blocking": False,
        "description": "One patch should not dominate the simplified surface unless explicitly configured that way.",
    },
    "coarse_singleton_patch_fraction": {
        "warn": 0.25,
        "fail": 0.50,
        "blocking": False,
        "description": "Too many singleton patches indicate over-fragmented coarse occupancy.",
    },
}


def resolve_geometry_qa_thresholds(overrides: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    thresholds = copy.deepcopy(DEFAULT_GEOMETRY_QA_THRESHOLDS)
    if not overrides:
        return thresholds

    for metric_name, override in overrides.items():
        if isinstance(override, dict):
            thresholds.setdefault(metric_name, {})
            thresholds[metric_name].update(copy.deepcopy(override))
        else:
            thresholds.setdefault(metric_name, {})
            thresholds[metric_name]["fail"] = override
    return thresholds


def describe_mesh(
    mesh: trimesh.Trimesh,
    *,
    adj: sp.csr_matrix,
) -> dict[str, Any]:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int32)
    bounds = np.asarray(mesh.bounds, dtype=np.float64)
    bounds_min = bounds[0]
    bounds_max = bounds[1]
    extent = bounds_max - bounds_min
    component_summary = _component_summary(adj, faces=faces)
    edge_lengths = _edge_length_stats(vertices, adj)

    return {
        "vertex_count": int(vertices.shape[0]),
        "face_count": int(faces.shape[0]),
        "edge_count": int(adj.nnz // 2),
        "surface_area": float(mesh.area),
        "volume": _finite_float(mesh.volume),
        "watertight": bool(mesh.is_watertight),
        "bounds_min": bounds_min.tolist(),
        "bounds_max": bounds_max.tolist(),
        "extent": extent.tolist(),
        "bbox_diagonal_length": float(np.linalg.norm(extent)),
        "vertex_centroid": vertices.mean(axis=0).tolist(),
        "mean_edge_length": edge_lengths["mean"],
        "median_edge_length": edge_lengths["median"],
        "max_edge_length": edge_lengths["max"],
        **component_summary,
    }


def describe_patch_decomposition(
    *,
    surface_vertex_count: int,
    surface_extent: np.ndarray,
    surface_component_count: int,
    patch_sizes: np.ndarray,
    patch_centroids: np.ndarray,
    surface_to_patch: np.ndarray,
    member_vertex_indices: np.ndarray,
    patch_adj: sp.csr_matrix,
) -> dict[str, Any]:
    patch_count = int(patch_sizes.size)
    component_summary = _component_summary(patch_adj)
    singleton_count = int(np.count_nonzero(patch_sizes == 1))
    centroid_bounds_min, centroid_bounds_max, centroid_extent = _bounds_from_points(patch_centroids)

    return {
        "patch_count": patch_count,
        "graph_edge_count": int(patch_adj.nnz // 2),
        "surface_vertex_count": int(surface_vertex_count),
        "surface_to_patch_count": int(surface_to_patch.size),
        "member_vertex_index_count": int(member_vertex_indices.size),
        "surface_vertex_coverage_ratio": _coverage_ratio(surface_vertex_count, member_vertex_indices),
        "patch_size_total": int(patch_sizes.sum()) if patch_count else 0,
        "patch_size_min": int(patch_sizes.min()) if patch_count else 0,
        "patch_size_max": int(patch_sizes.max()) if patch_count else 0,
        "patch_size_mean": float(patch_sizes.mean()) if patch_count else 0.0,
        "patch_size_median": float(np.median(patch_sizes)) if patch_count else 0.0,
        "patch_size_std": float(patch_sizes.std()) if patch_count else 0.0,
        "max_patch_vertex_fraction": _fraction(int(patch_sizes.max()) if patch_count else 0, surface_vertex_count),
        "singleton_patch_count": singleton_count,
        "singleton_patch_fraction": _fraction(singleton_count, patch_count),
        "patch_centroid_bounds_min": centroid_bounds_min,
        "patch_centroid_bounds_max": centroid_bounds_max,
        "patch_centroid_extent": centroid_extent,
        "patch_centroid_extent_vs_surface_extent": _vector_ratio(centroid_extent, surface_extent),
        "surface_component_count_reference": int(surface_component_count),
        **component_summary,
    }


def describe_skeleton(path: str | Path) -> dict[str, Any]:
    swc_path = Path(path)
    payload: dict[str, Any] = {
        "available": False,
        "path": str(swc_path),
    }
    if not swc_path.exists():
        return payload

    nodes: list[tuple[int, np.ndarray, int]] = []
    with swc_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 7:
                raise ValueError(f"Invalid SWC row in {swc_path}: expected 7 columns, got {len(parts)}")
            node_id = int(parts[0])
            coords = np.asarray(
                [
                    float(parts[2]),
                    float(parts[3]),
                    float(parts[4]),
                ],
                dtype=np.float64,
            )
            parent_id = int(parts[6])
            nodes.append((node_id, coords, parent_id))

    if not nodes:
        return payload

    node_index = {node_id: idx for idx, (node_id, _coords, _parent_id) in enumerate(nodes)}
    coords = np.vstack([coords for _node_id, coords, _parent_id in nodes])
    rows: list[int] = []
    cols: list[int] = []
    cable_length = 0.0
    child_counts = np.zeros(len(nodes), dtype=np.int32)
    root_count = 0

    for idx, (_node_id, node_coords, parent_id) in enumerate(nodes):
        parent_idx = node_index.get(parent_id)
        if parent_idx is None:
            root_count += 1
            continue
        rows.extend([idx, parent_idx])
        cols.extend([parent_idx, idx])
        child_counts[parent_idx] += 1
        cable_length += float(np.linalg.norm(node_coords - coords[parent_idx]))

    skeleton_adj = sp.csr_matrix(
        (np.ones(len(rows), dtype=np.float32), (rows, cols)),
        shape=(len(nodes), len(nodes)),
    )
    component_summary = _component_summary(skeleton_adj)
    bounds_min, bounds_max, extent = _bounds_from_points(coords)

    payload.update(
        {
            "available": True,
            "node_count": int(len(nodes)),
            "segment_count": int(len(rows) // 2),
            "root_count": int(root_count),
            "branch_point_count": int(np.count_nonzero(child_counts > 1)),
            "leaf_count": int(np.count_nonzero(child_counts == 0)),
            "total_cable_length": float(cable_length),
            "bounds_min": bounds_min,
            "bounds_max": bounds_max,
            "extent": extent,
            "vertex_centroid": coords.mean(axis=0).tolist(),
            **component_summary,
        }
    )
    return payload


def build_descriptor_payload(
    *,
    root_id: int,
    raw_mesh_summary: dict[str, Any],
    simplified_mesh_summary: dict[str, Any],
    coarse_summary: dict[str, Any],
    skeleton_summary: dict[str, Any],
    simplify_target_faces: int,
    patch_hops: int,
    patch_vertex_cap: int,
    raw_mesh_path: str | Path,
    raw_skeleton_path: str | Path,
    processed_mesh_path: str | Path,
    surface_graph_path: str | Path,
    patch_graph_path: str | Path,
    registry_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    face_ratio = _safe_ratio(
        float(simplified_mesh_summary["face_count"]),
        float(raw_mesh_summary["face_count"]),
    )
    vertex_ratio = _safe_ratio(
        float(simplified_mesh_summary["vertex_count"]),
        float(raw_mesh_summary["vertex_count"]),
    )

    return {
        "root_id": int(root_id),
        "descriptor_version": GEOMETRY_DESCRIPTOR_VERSION,
        "inputs": {
            "raw_mesh_path": str(raw_mesh_path),
            "raw_skeleton_path": str(raw_skeleton_path),
            "processed_mesh_path": str(processed_mesh_path),
            "surface_graph_path": str(surface_graph_path),
            "patch_graph_path": str(patch_graph_path),
        },
        "config": {
            "simplify_target_faces": int(simplify_target_faces),
            "patch_hops": int(patch_hops),
            "patch_vertex_cap": int(patch_vertex_cap),
            "patch_generation_method": "deterministic_bfs_partition",
        },
        "representations": {
            "raw_mesh": raw_mesh_summary,
            "simplified_mesh": simplified_mesh_summary,
            "coarse_patches": coarse_summary,
            "skeleton": skeleton_summary,
        },
        "derived_relations": {
            "simplified_to_raw_face_ratio": face_ratio,
            "simplified_to_raw_vertex_ratio": vertex_ratio,
        },
        "registry_metadata": dict(registry_metadata or {}),
        "n_vertices": int(simplified_mesh_summary["vertex_count"]),
        "n_faces": int(simplified_mesh_summary["face_count"]),
        "surface_graph_edge_count": int(simplified_mesh_summary["edge_count"]),
        "patch_count": int(coarse_summary["patch_count"]),
        "patch_graph_vertex_count": int(coarse_summary["patch_count"]),
        "patch_graph_edge_count": int(coarse_summary["graph_edge_count"]),
        "surface_to_patch_count": int(coarse_summary["surface_to_patch_count"]),
        "patch_membership_index_count": int(coarse_summary["member_vertex_index_count"]),
        "patch_hops": int(patch_hops),
        "patch_vertex_cap": int(patch_vertex_cap),
        "patch_generation_method": "deterministic_bfs_partition",
        "simplify_target_faces": int(simplify_target_faces),
        "raw_mesh_face_count": int(raw_mesh_summary["face_count"]),
        "surface_area": float(simplified_mesh_summary["surface_area"]),
        "volume": simplified_mesh_summary["volume"],
        "bounds_min": list(simplified_mesh_summary["bounds_min"]),
        "bounds_max": list(simplified_mesh_summary["bounds_max"]),
        "raw_mesh_path": str(raw_mesh_path),
        "raw_skeleton_path": str(raw_skeleton_path),
        "processed_mesh_path": str(processed_mesh_path),
        "surface_graph_path": str(surface_graph_path),
        "patch_graph_path": str(patch_graph_path),
    }


def evaluate_geometry_qa(
    descriptor_payload: dict[str, Any],
    *,
    thresholds: dict[str, Any] | None = None,
    surface_to_patch_is_complete: bool,
    patch_membership_covers_surface: bool,
    patch_graph_node_count_matches_mapping: bool,
    vertex_count_matches_surface_graph: bool,
) -> dict[str, Any]:
    applied_thresholds = resolve_geometry_qa_thresholds(thresholds)
    raw_summary = descriptor_payload["representations"]["raw_mesh"]
    simplified_summary = descriptor_payload["representations"]["simplified_mesh"]
    coarse_summary = descriptor_payload["representations"]["coarse_patches"]

    extent_rel_error = _relative_extent_error_max(
        np.asarray(raw_summary["extent"], dtype=np.float64),
        np.asarray(simplified_summary["extent"], dtype=np.float64),
    )
    centroid_shift_fraction = _centroid_shift_fraction_of_diagonal(
        np.asarray(raw_summary["vertex_centroid"], dtype=np.float64),
        np.asarray(simplified_summary["vertex_centroid"], dtype=np.float64),
        float(raw_summary["bbox_diagonal_length"]),
    )
    volume_rel_error = _relative_volume_error(raw_summary, simplified_summary)

    checks = {
        "simplified_component_count_delta": _evaluate_upper_bound_check(
            metric_name="simplified_component_count_delta",
            value=float(
                abs(int(simplified_summary["component_count"]) - int(raw_summary["component_count"]))
            ),
            thresholds=applied_thresholds["simplified_component_count_delta"],
            representation_pair=["raw_mesh", "simplified_mesh"],
            unit="count",
        ),
        "simplified_surface_area_rel_error": _evaluate_upper_bound_check(
            metric_name="simplified_surface_area_rel_error",
            value=_relative_scalar_error(
                float(raw_summary["surface_area"]),
                float(simplified_summary["surface_area"]),
            ),
            thresholds=applied_thresholds["simplified_surface_area_rel_error"],
            representation_pair=["raw_mesh", "simplified_mesh"],
            unit="ratio",
        ),
        "simplified_extent_rel_error_max": _evaluate_upper_bound_check(
            metric_name="simplified_extent_rel_error_max",
            value=extent_rel_error,
            thresholds=applied_thresholds["simplified_extent_rel_error_max"],
            representation_pair=["raw_mesh", "simplified_mesh"],
            unit="ratio",
        ),
        "simplified_centroid_shift_fraction_of_diagonal": _evaluate_upper_bound_check(
            metric_name="simplified_centroid_shift_fraction_of_diagonal",
            value=centroid_shift_fraction,
            thresholds=applied_thresholds["simplified_centroid_shift_fraction_of_diagonal"],
            representation_pair=["raw_mesh", "simplified_mesh"],
            unit="ratio",
        ),
        "simplified_volume_rel_error": _evaluate_upper_bound_check(
            metric_name="simplified_volume_rel_error",
            value=volume_rel_error,
            thresholds=applied_thresholds["simplified_volume_rel_error"],
            representation_pair=["raw_mesh", "simplified_mesh"],
            unit="ratio",
        ),
        "coarse_component_count_delta": _evaluate_upper_bound_check(
            metric_name="coarse_component_count_delta",
            value=float(
                abs(int(coarse_summary["component_count"]) - int(simplified_summary["component_count"]))
            ),
            thresholds=applied_thresholds["coarse_component_count_delta"],
            representation_pair=["simplified_mesh", "coarse_patches"],
            unit="count",
        ),
        "coarse_surface_vertex_coverage_gap": _evaluate_upper_bound_check(
            metric_name="coarse_surface_vertex_coverage_gap",
            value=float(max(0.0, 1.0 - float(coarse_summary["surface_vertex_coverage_ratio"]))),
            thresholds=applied_thresholds["coarse_surface_vertex_coverage_gap"],
            representation_pair=["simplified_mesh", "coarse_patches"],
            unit="ratio",
        ),
        "coarse_max_patch_vertex_fraction": _evaluate_upper_bound_check(
            metric_name="coarse_max_patch_vertex_fraction",
            value=float(coarse_summary["max_patch_vertex_fraction"]),
            thresholds=applied_thresholds["coarse_max_patch_vertex_fraction"],
            representation_pair=["simplified_mesh", "coarse_patches"],
            unit="ratio",
            skip_reason="patch_count_lt_2" if int(coarse_summary["patch_count"]) < 2 else None,
        ),
        "coarse_singleton_patch_fraction": _evaluate_upper_bound_check(
            metric_name="coarse_singleton_patch_fraction",
            value=float(coarse_summary["singleton_patch_fraction"]),
            thresholds=applied_thresholds["coarse_singleton_patch_fraction"],
            representation_pair=["simplified_mesh", "coarse_patches"],
            unit="ratio",
            skip_reason="patch_count_lt_2" if int(coarse_summary["patch_count"]) < 2 else None,
        ),
        "surface_to_patch_is_complete": _evaluate_boolean_check(
            metric_name="surface_to_patch_is_complete",
            passed=surface_to_patch_is_complete,
            representation_pair=["simplified_mesh", "coarse_patches"],
            blocking=True,
            description="Every simplified surface vertex should have a patch assignment.",
        ),
        "patch_membership_covers_surface": _evaluate_boolean_check(
            metric_name="patch_membership_covers_surface",
            passed=patch_membership_covers_surface,
            representation_pair=["simplified_mesh", "coarse_patches"],
            blocking=True,
            description="Patch membership indices should cover the simplified surface exactly once.",
        ),
        "patch_graph_node_count_matches_mapping": _evaluate_boolean_check(
            metric_name="patch_graph_node_count_matches_mapping",
            passed=patch_graph_node_count_matches_mapping,
            representation_pair=["simplified_mesh", "coarse_patches"],
            blocking=True,
            description="Patch graph node count should match the number of generated patches.",
        ),
        "vertex_count_matches_surface_graph": _evaluate_boolean_check(
            metric_name="vertex_count_matches_surface_graph",
            passed=vertex_count_matches_surface_graph,
            representation_pair=["simplified_mesh", "surface_graph"],
            blocking=True,
            description="Simplified mesh vertex count should match the serialized surface graph.",
        ),
    }

    summary = _summarize_checks(checks)
    return {
        "root_id": int(descriptor_payload["root_id"]),
        "qa_version": GEOMETRY_QA_VERSION,
        "thresholds": applied_thresholds,
        "checks": checks,
        "summary": summary,
        "availability": {
            "raw_mesh_available": True,
            "raw_skeleton_available": bool(descriptor_payload["representations"]["skeleton"]["available"]),
            "simplified_mesh_available": True,
            "surface_graph_available": True,
            "patch_graph_available": True,
            "descriptor_sidecar_available": True,
        },
        "raw_mesh_available": True,
        "raw_skeleton_available": bool(descriptor_payload["representations"]["skeleton"]["available"]),
        "simplified_mesh_available": True,
        "surface_graph_available": True,
        "patch_graph_available": True,
        "descriptor_sidecar_available": True,
        "is_watertight": bool(simplified_summary["watertight"]),
        "vertex_count_matches_surface_graph": bool(vertex_count_matches_surface_graph),
        "patch_count": int(coarse_summary["patch_count"]),
        "patch_is_nonempty": bool(int(coarse_summary["patch_count"]) > 0),
        "surface_to_patch_length_matches_vertex_count": int(coarse_summary["surface_to_patch_count"])
        == int(simplified_summary["vertex_count"]),
        "surface_to_patch_is_complete": bool(surface_to_patch_is_complete),
        "patch_membership_covers_surface": bool(patch_membership_covers_surface),
        "patch_graph_node_count_matches_mapping": bool(patch_graph_node_count_matches_mapping),
    }


def _summarize_checks(checks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    warning_checks = sorted(name for name, check in checks.items() if check["status"] == "warn")
    failure_checks = sorted(name for name, check in checks.items() if check["status"] == "fail")
    skipped_checks = sorted(name for name, check in checks.items() if check["status"] == "skip")
    pass_checks = sorted(name for name, check in checks.items() if check["status"] == "pass")
    blocking_failure_checks = sorted(
        name for name, check in checks.items() if check["status"] == "fail" and bool(check["blocking"])
    )
    overall_status = "pass"
    if failure_checks:
        overall_status = "fail"
    elif warning_checks:
        overall_status = "warn"

    return {
        "overall_status": overall_status,
        "pass_count": int(len(pass_checks)),
        "warning_count": int(len(warning_checks)),
        "failure_count": int(len(failure_checks)),
        "blocking_failure_count": int(len(blocking_failure_checks)),
        "skipped_count": int(len(skipped_checks)),
        "warning_checks": warning_checks,
        "failure_checks": failure_checks,
        "blocking_failure_checks": blocking_failure_checks,
        "skipped_checks": skipped_checks,
        "pass_checks": pass_checks,
        "downstream_usable": not bool(blocking_failure_checks),
    }


def _evaluate_upper_bound_check(
    *,
    metric_name: str,
    value: float | None,
    thresholds: dict[str, Any],
    representation_pair: list[str],
    unit: str,
    skip_reason: str | None = None,
) -> dict[str, Any]:
    if skip_reason is not None:
        return {
            "metric": metric_name,
            "representation_pair": representation_pair,
            "unit": unit,
            "value": value,
            "warn_threshold": thresholds.get("warn"),
            "fail_threshold": thresholds.get("fail"),
            "blocking": bool(thresholds.get("blocking", False)),
            "status": "skip",
            "description": str(thresholds.get("description", "")),
            "skip_reason": skip_reason,
        }

    if value is None:
        return {
            "metric": metric_name,
            "representation_pair": representation_pair,
            "unit": unit,
            "value": None,
            "warn_threshold": thresholds.get("warn"),
            "fail_threshold": thresholds.get("fail"),
            "blocking": bool(thresholds.get("blocking", False)),
            "status": "skip",
            "description": str(thresholds.get("description", "")),
            "skip_reason": "metric_unavailable",
        }

    warn_threshold = thresholds.get("warn")
    fail_threshold = thresholds.get("fail")
    status = "pass"
    if fail_threshold is not None and float(value) > float(fail_threshold):
        status = "fail"
    elif warn_threshold is not None and float(value) > float(warn_threshold):
        status = "warn"

    return {
        "metric": metric_name,
        "representation_pair": representation_pair,
        "unit": unit,
        "value": float(value),
        "warn_threshold": warn_threshold,
        "fail_threshold": fail_threshold,
        "blocking": bool(thresholds.get("blocking", False)),
        "status": status,
        "description": str(thresholds.get("description", "")),
    }


def _evaluate_boolean_check(
    *,
    metric_name: str,
    passed: bool,
    representation_pair: list[str],
    blocking: bool,
    description: str,
) -> dict[str, Any]:
    return {
        "metric": metric_name,
        "representation_pair": representation_pair,
        "unit": "bool",
        "value": bool(passed),
        "warn_threshold": None,
        "fail_threshold": False,
        "blocking": bool(blocking),
        "status": "pass" if passed else "fail",
        "description": description,
    }


def _component_summary(adj: sp.csr_matrix, faces: np.ndarray | None = None) -> dict[str, Any]:
    if int(adj.shape[0]) == 0:
        return {
            "component_count": 0,
            "largest_component_vertex_count": 0,
            "largest_component_vertex_fraction": 0.0,
            "smallest_component_vertex_count": 0,
            "component_vertex_count_topk": [],
            "largest_component_face_count": 0,
            "largest_component_face_fraction": 0.0,
            "component_face_count_topk": [],
        }

    component_count, labels = sp.csgraph.connected_components(adj, directed=False, return_labels=True)
    vertex_counts = np.bincount(labels, minlength=component_count)
    order = np.argsort(-vertex_counts, kind="stable")
    sorted_vertex_counts = vertex_counts[order]
    total_vertices = int(vertex_counts.sum())

    face_counts_sorted: list[int] = []
    largest_face_count = 0
    largest_face_fraction = 0.0
    if faces is not None and faces.size:
        face_component_labels = labels[np.asarray(faces[:, 0], dtype=np.int32)]
        face_counts = np.bincount(face_component_labels, minlength=component_count)
        sorted_face_counts = face_counts[order]
        face_counts_sorted = [int(count) for count in sorted_face_counts[:TOP_COMPONENT_COUNTS]]
        largest_face_count = int(sorted_face_counts[0])
        largest_face_fraction = _fraction(largest_face_count, int(face_counts.sum()))

    return {
        "component_count": int(component_count),
        "largest_component_vertex_count": int(sorted_vertex_counts[0]),
        "largest_component_vertex_fraction": _fraction(int(sorted_vertex_counts[0]), total_vertices),
        "smallest_component_vertex_count": int(sorted_vertex_counts[-1]),
        "component_vertex_count_topk": [int(count) for count in sorted_vertex_counts[:TOP_COMPONENT_COUNTS]],
        "largest_component_face_count": largest_face_count,
        "largest_component_face_fraction": largest_face_fraction,
        "component_face_count_topk": face_counts_sorted,
    }


def _edge_length_stats(vertices: np.ndarray, adj: sp.csr_matrix) -> dict[str, float]:
    upper_edges = sp.triu(adj, k=1).tocoo()
    if upper_edges.nnz == 0:
        return {
            "mean": 0.0,
            "median": 0.0,
            "max": 0.0,
        }

    lengths = np.linalg.norm(vertices[upper_edges.row] - vertices[upper_edges.col], axis=1)
    return {
        "mean": float(lengths.mean()),
        "median": float(np.median(lengths)),
        "max": float(lengths.max()),
    }


def _bounds_from_points(points: np.ndarray) -> tuple[list[float], list[float], list[float]]:
    if points.size == 0:
        zero = [0.0, 0.0, 0.0]
        return zero, zero, zero

    mins = np.asarray(points.min(axis=0), dtype=np.float64)
    maxs = np.asarray(points.max(axis=0), dtype=np.float64)
    return mins.tolist(), maxs.tolist(), (maxs - mins).tolist()


def _coverage_ratio(surface_vertex_count: int, member_vertex_indices: np.ndarray) -> float:
    if surface_vertex_count <= 0:
        return 0.0
    if member_vertex_indices.size == 0:
        return 0.0
    unique_vertices = int(np.unique(member_vertex_indices).size)
    return _fraction(unique_vertices, surface_vertex_count)


def _relative_scalar_error(reference_value: float, observed_value: float) -> float | None:
    if abs(reference_value) <= EPSILON:
        if abs(observed_value) <= EPSILON:
            return 0.0
        return None
    return float(abs(observed_value - reference_value) / abs(reference_value))


def _relative_extent_error_max(reference_extent: np.ndarray, observed_extent: np.ndarray) -> float | None:
    valid_axes = np.abs(reference_extent) > EPSILON
    if not bool(np.any(valid_axes)):
        return None
    rel_errors = np.abs(observed_extent[valid_axes] - reference_extent[valid_axes]) / np.abs(reference_extent[valid_axes])
    return float(rel_errors.max())


def _centroid_shift_fraction_of_diagonal(
    raw_centroid: np.ndarray,
    simplified_centroid: np.ndarray,
    raw_diagonal_length: float,
) -> float | None:
    if raw_diagonal_length <= EPSILON:
        return None
    return float(np.linalg.norm(simplified_centroid - raw_centroid) / raw_diagonal_length)


def _relative_volume_error(raw_summary: dict[str, Any], simplified_summary: dict[str, Any]) -> float | None:
    raw_volume = raw_summary.get("volume")
    simplified_volume = simplified_summary.get("volume")
    if (
        raw_volume is None
        or simplified_volume is None
        or not bool(raw_summary.get("watertight"))
        or not bool(simplified_summary.get("watertight"))
    ):
        return None
    return _relative_scalar_error(float(raw_volume), float(simplified_volume))


def _vector_ratio(numerator: list[float], denominator: np.ndarray) -> list[float | None]:
    return [_safe_ratio(float(num), float(den)) for num, den in zip(numerator, denominator)]


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if abs(denominator) <= EPSILON:
        if abs(numerator) <= EPSILON:
            return 1.0
        return None
    return float(numerator / denominator)


def _fraction(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator / denominator)


def _finite_float(value: Any) -> float | None:
    scalar = float(value)
    if not np.isfinite(scalar):
        return None
    return scalar
