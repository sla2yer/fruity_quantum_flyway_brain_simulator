from __future__ import annotations

import hashlib
import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import scipy.sparse as sp
import trimesh

from .geometry_contract import (
    PATCH_GRAPH_KEY,
    RAW_MESH_KEY,
    SIMPLIFIED_MESH_KEY,
    SURFACE_GRAPH_KEY,
    build_geometry_bundle_paths,
)
from .geometry_qa import describe_skeleton
from .io_utils import ensure_dir, write_json


PREVIEW_REPORT_VERSION = "geometry_preview.v2"
SVG_WIDTH = 320
SVG_HEIGHT = 260
SVG_PADDING = 18.0
MESH_EDGE_LIMIT = 2400
SURFACE_EDGE_LIMIT = 2600
PATCH_EDGE_LIMIT = 1800
SURFACE_VERTEX_LIMIT = 1200
ROTATION_Z_DEGREES = 38.0
ROTATION_X_DEGREES = -28.0
PATCH_PALETTE = (
    "#0f766e",
    "#c2410c",
    "#1d4ed8",
    "#b91c1c",
    "#4d7c0f",
    "#6d28d9",
    "#0369a1",
    "#be123c",
    "#854d0e",
    "#166534",
)
PREVIEW_STATUS_READY = "ready"
PREVIEW_STATUS_BLOCKED = "blocked"
_MAKE_MESHES_TARGET = "make meshes"
_MAKE_ASSETS_TARGET = "make assets"
_REQUIRED_PREVIEW_INPUTS = (
    (RAW_MESH_KEY, "raw_mesh_path"),
    (SIMPLIFIED_MESH_KEY, "simplified_mesh_path"),
    (SURFACE_GRAPH_KEY, "surface_graph_path"),
    (PATCH_GRAPH_KEY, "patch_graph_path"),
)
_REMEDIATION_TARGETS_BY_ASSET_KEY = {
    RAW_MESH_KEY: (_MAKE_MESHES_TARGET, _MAKE_ASSETS_TARGET),
    SIMPLIFIED_MESH_KEY: (_MAKE_ASSETS_TARGET,),
    SURFACE_GRAPH_KEY: (_MAKE_ASSETS_TARGET,),
    PATCH_GRAPH_KEY: (_MAKE_ASSETS_TARGET,),
}
_MAKE_TARGET_ORDER = (_MAKE_MESHES_TARGET, _MAKE_ASSETS_TARGET)


@dataclass(frozen=True)
class ProjectionFrame:
    rotation: np.ndarray
    center: np.ndarray
    bounds_min: np.ndarray
    bounds_max: np.ndarray


def generate_geometry_preview_report(
    *,
    root_ids: Iterable[int],
    meshes_raw_dir: str | Path,
    skeletons_raw_dir: str | Path,
    processed_mesh_dir: str | Path,
    processed_graph_dir: str | Path,
    geometry_preview_dir: str | Path,
) -> dict[str, Any]:
    normalized_root_ids = _normalize_root_ids(root_ids)
    output_dir = build_preview_output_dir(geometry_preview_dir, normalized_root_ids)
    ensure_dir(output_dir)

    root_entries = [
        _build_root_preview_entry(
            root_id=root_id,
            meshes_raw_dir=meshes_raw_dir,
            skeletons_raw_dir=skeletons_raw_dir,
            processed_mesh_dir=processed_mesh_dir,
            processed_graph_dir=processed_graph_dir,
            output_dir=output_dir,
        )
        for root_id in normalized_root_ids
    ]

    index_path = (output_dir / "index.html").resolve()
    summary_path = (output_dir / "summary.json").resolve()
    root_ids_path = (output_dir / "root_ids.txt").resolve()
    blocked_root_entries = [
        entry for entry in root_entries if str(entry["summary"]["preview_status"]) == PREVIEW_STATUS_BLOCKED
    ]
    missing_prerequisites = [
        {"root_id": int(entry["root_id"]), **dict(item)}
        for entry in root_entries
        for item in entry.get("missing_prerequisites", [])
    ]
    recommended_make_targets = _aggregate_make_targets(missing_prerequisites)

    summary = {
        "report_version": PREVIEW_REPORT_VERSION,
        "root_ids": normalized_root_ids,
        "output_dir": str(output_dir.resolve()),
        "report_path": str(index_path),
        "summary_path": str(summary_path),
        "root_ids_path": str(root_ids_path),
        "root_count": len(normalized_root_ids),
        "overall_status": PREVIEW_STATUS_BLOCKED if blocked_root_entries else PREVIEW_STATUS_READY,
        "ready_root_count": len(normalized_root_ids) - len(blocked_root_entries),
        "blocked_root_count": len(blocked_root_entries),
        "missing_prerequisite_count": len(missing_prerequisites),
        "missing_prerequisite_root_ids": [int(entry["root_id"]) for entry in blocked_root_entries],
        "missing_prerequisites": missing_prerequisites,
        "recommended_make_targets": recommended_make_targets,
        "recommended_make_target_scope": _summarize_make_targets(recommended_make_targets),
        "roots": {str(entry["root_id"]): _root_summary_payload(entry) for entry in root_entries},
    }

    index_path.write_text(_render_report_html(root_entries, summary), encoding="utf-8")
    write_json(summary, summary_path)
    root_ids_path.write_text("".join(f"{root_id}\n" for root_id in normalized_root_ids), encoding="utf-8")
    return summary


def build_preview_output_dir(geometry_preview_dir: str | Path, root_ids: Iterable[int]) -> Path:
    return Path(geometry_preview_dir).resolve() / build_preview_slug(root_ids)


def build_preview_slug(root_ids: Iterable[int]) -> str:
    normalized_root_ids = _normalize_root_ids(root_ids)
    joined = "-".join(str(root_id) for root_id in normalized_root_ids)
    if len(joined) <= 64:
        return f"root-ids-{joined}"
    digest = hashlib.sha1(",".join(str(root_id) for root_id in normalized_root_ids).encode("utf-8")).hexdigest()[:12]
    prefix = "-".join(str(root_id) for root_id in normalized_root_ids[:4])
    return f"root-ids-{prefix}-n{len(normalized_root_ids)}-{digest}"


def _normalize_root_ids(root_ids: Iterable[int]) -> list[int]:
    normalized = sorted({int(root_id) for root_id in root_ids})
    if not normalized:
        raise ValueError("At least one root ID is required for preview generation.")
    return normalized


def _build_root_preview_entry(
    *,
    root_id: int,
    meshes_raw_dir: str | Path,
    skeletons_raw_dir: str | Path,
    processed_mesh_dir: str | Path,
    processed_graph_dir: str | Path,
    output_dir: Path,
) -> dict[str, Any]:
    bundle_paths = build_geometry_bundle_paths(
        root_id,
        meshes_raw_dir=meshes_raw_dir,
        skeletons_raw_dir=skeletons_raw_dir,
        processed_mesh_dir=processed_mesh_dir,
        processed_graph_dir=processed_graph_dir,
    )
    missing_prerequisites = _collect_missing_preview_inputs(bundle_paths)
    if missing_prerequisites:
        return _build_blocked_root_preview_entry(
            root_id=root_id,
            bundle_paths=bundle_paths,
            output_dir=output_dir,
            missing_prerequisites=missing_prerequisites,
        )

    raw_mesh = _load_trimesh(bundle_paths.raw_mesh_path)
    simplified_mesh = _load_trimesh(bundle_paths.simplified_mesh_path)
    descriptor_payload = _load_json_if_exists(bundle_paths.descriptor_sidecar_path)
    qa_payload = _load_json_if_exists(bundle_paths.qa_sidecar_path)
    surface_graph_payload = _load_npz_payload(bundle_paths.surface_graph_path)
    patch_graph_payload = _load_npz_payload(bundle_paths.patch_graph_path)
    skeleton_geometry = _load_skeleton_geometry(bundle_paths.raw_skeleton_path)
    skeleton_summary = (
        descriptor_payload["representations"]["skeleton"]
        if descriptor_payload is not None and "representations" in descriptor_payload
        else describe_skeleton(bundle_paths.raw_skeleton_path)
    )

    raw_summary = _extract_summary(descriptor_payload, "raw_mesh") or _fallback_mesh_summary(raw_mesh)
    simplified_summary = _extract_summary(descriptor_payload, "simplified_mesh") or _fallback_mesh_summary(
        simplified_mesh
    )
    coarse_summary = _extract_summary(descriptor_payload, "coarse_patches") or _fallback_patch_summary(
        surface_graph_payload,
        patch_graph_payload,
    )
    qa_summary = dict(qa_payload.get("summary", {})) if qa_payload is not None else {}
    registry_metadata = dict(descriptor_payload.get("registry_metadata", {})) if descriptor_payload is not None else {}

    frame = _build_projection_frame(
        [
            np.asarray(raw_mesh.vertices, dtype=np.float64),
            np.asarray(simplified_mesh.vertices, dtype=np.float64),
            np.asarray(patch_graph_payload.get("patch_centroids", np.empty((0, 3))), dtype=np.float64),
            skeleton_geometry["points"],
        ]
    )

    raw_edges = np.asarray(raw_mesh.edges_unique, dtype=np.int32)
    simplified_edges = np.asarray(simplified_mesh.edges_unique, dtype=np.int32)
    surface_edges = _csr_edges(_load_csr(surface_graph_payload, prefix="adj"))
    patch_edges = _csr_edges(_load_csr(patch_graph_payload, prefix="adj"))
    patch_sizes = np.asarray(patch_graph_payload.get("patch_sizes", np.empty(0, dtype=np.int32)), dtype=np.int32)
    patch_centroids = np.asarray(patch_graph_payload.get("patch_centroids", np.empty((0, 3))), dtype=np.float64)
    surface_vertices = np.asarray(surface_graph_payload.get("vertices", np.empty((0, 3))), dtype=np.float64)
    surface_to_patch = np.asarray(surface_graph_payload.get("surface_to_patch", np.empty(0, dtype=np.int32)), dtype=np.int32)

    panels = [
        _make_wireframe_panel(
            title="Raw Mesh",
            subtitle=f"{raw_summary['vertex_count']} vertices, {raw_summary['face_count']} faces",
            points=np.asarray(raw_mesh.vertices, dtype=np.float64),
            edges=raw_edges,
            frame=frame,
            edge_limit=MESH_EDGE_LIMIT,
            stroke="#184e77",
        ),
        _make_wireframe_panel(
            title="Simplified Mesh",
            subtitle=f"{simplified_summary['vertex_count']} vertices, {simplified_summary['face_count']} faces",
            points=np.asarray(simplified_mesh.vertices, dtype=np.float64),
            edges=simplified_edges,
            frame=frame,
            edge_limit=MESH_EDGE_LIMIT,
            stroke="#9a3412",
        ),
        _make_skeleton_panel(
            title="Skeleton",
            skeleton_summary=skeleton_summary,
            points=skeleton_geometry["points"],
            edges=skeleton_geometry["edges"],
            frame=frame,
        ),
        _make_surface_graph_panel(
            title="Surface Graph",
            points=surface_vertices,
            edges=surface_edges,
            frame=frame,
            edge_limit=SURFACE_EDGE_LIMIT,
            surface_to_patch=surface_to_patch,
        ),
        _make_patch_graph_panel(
            title="Patch Graph",
            patch_centroids=patch_centroids,
            patch_sizes=patch_sizes,
            edges=patch_edges,
            frame=frame,
            edge_limit=PATCH_EDGE_LIMIT,
        ),
    ]

    qa_highlights = _qa_highlights(qa_payload)
    stats = {
        "raw_face_count": int(raw_summary["face_count"]),
        "simplified_face_count": int(simplified_summary["face_count"]),
        "simplified_to_raw_face_ratio": _safe_float(
            descriptor_payload.get("derived_relations", {}).get("simplified_to_raw_face_ratio")
            if descriptor_payload is not None
            else _ratio(simplified_summary["face_count"], raw_summary["face_count"])
        ),
        "surface_graph_edge_count": int(surface_edges.shape[0]),
        "patch_count": int(coarse_summary["patch_count"]),
        "patch_graph_edge_count": int(patch_edges.shape[0]),
        "skeleton_available": bool(skeleton_summary.get("available", False)),
    }
    summary_rows = [
        ("QA status", qa_summary.get("overall_status", "not available")),
        ("Cell type", registry_metadata.get("cell_type", "n/a")),
        ("Project role", registry_metadata.get("project_role", "n/a")),
        ("Raw mesh", f"{raw_summary['vertex_count']} vertices / {raw_summary['face_count']} faces"),
        (
            "Simplified mesh",
            f"{simplified_summary['vertex_count']} vertices / {simplified_summary['face_count']} faces",
        ),
        ("Face ratio", _format_ratio(stats["simplified_to_raw_face_ratio"])),
        ("Surface graph", f"{int(surface_edges.shape[0])} undirected edges"),
        ("Patch graph", f"{int(coarse_summary['patch_count'])} patches / {int(patch_edges.shape[0])} edges"),
        (
            "Patch occupancy",
            (
                f"largest {int(coarse_summary.get('patch_size_max', 0))} vertices"
                f" ({_format_ratio(_safe_float(coarse_summary.get('max_patch_vertex_fraction')))})"
            ),
        ),
        (
            "Skeleton",
            (
                f"available: {int(skeleton_summary.get('node_count', 0))} nodes /"
                f" {int(skeleton_summary.get('segment_count', 0))} segments"
                if skeleton_summary.get("available")
                else "not available"
            ),
        ),
    ]

    return {
        "root_id": int(root_id),
        "summary": {
            "preview_status": PREVIEW_STATUS_READY,
            "qa_overall_status": str(qa_summary.get("overall_status", "unknown")),
        },
        "qa_summary": qa_summary,
        "qa_highlights": qa_highlights,
        "registry_metadata": registry_metadata,
        "summary_rows": summary_rows,
        "panels": panels,
        "stats": stats,
        "missing_prerequisites": [],
        "artifacts": {
            "raw_mesh_path": str(bundle_paths.raw_mesh_path.resolve()),
            "raw_skeleton_path": str(bundle_paths.raw_skeleton_path.resolve()),
            "simplified_mesh_path": str(bundle_paths.simplified_mesh_path.resolve()),
            "surface_graph_path": str(bundle_paths.surface_graph_path.resolve()),
            "patch_graph_path": str(bundle_paths.patch_graph_path.resolve()),
            "descriptor_sidecar_path": str(bundle_paths.descriptor_sidecar_path.resolve()),
            "qa_sidecar_path": str(bundle_paths.qa_sidecar_path.resolve()),
        },
    }


def _root_summary_payload(entry: Mapping[str, Any]) -> dict[str, Any]:
    summary = {
        "preview_status": str(entry["summary"]["preview_status"]),
        "qa_overall_status": str(entry["summary"].get("qa_overall_status", "unknown")),
        "artifacts": dict(entry["artifacts"]),
    }
    if summary["preview_status"] == PREVIEW_STATUS_BLOCKED:
        summary["missing_prerequisite_count"] = int(entry["summary"].get("missing_prerequisite_count", 0))
        summary["missing_prerequisites"] = list(entry.get("missing_prerequisites", []))
        summary["recommended_make_targets"] = list(entry["summary"].get("recommended_make_targets", []))
        summary["recommended_make_target_scope"] = str(entry["summary"].get("recommended_make_target_scope", "none"))
        return summary

    summary.update(
        {
            "skeleton_available": bool(entry["stats"]["skeleton_available"]),
            "patch_count": int(entry["stats"]["patch_count"]),
            "surface_graph_edge_count": int(entry["stats"]["surface_graph_edge_count"]),
            "patch_graph_edge_count": int(entry["stats"]["patch_graph_edge_count"]),
        }
    )
    return summary


def _collect_missing_preview_inputs(bundle_paths: Any) -> list[dict[str, Any]]:
    missing_prerequisites: list[dict[str, Any]] = []
    for asset_key, attribute_name in _REQUIRED_PREVIEW_INPUTS:
        path = Path(getattr(bundle_paths, attribute_name))
        if path.exists():
            continue
        recommended_make_targets = list(_REMEDIATION_TARGETS_BY_ASSET_KEY.get(str(asset_key), (_MAKE_ASSETS_TARGET,)))
        missing_prerequisites.append(
            {
                "asset_key": str(asset_key),
                "path": str(path.resolve()),
                "reason": "missing_required_preview_input",
                "recommended_make_targets": recommended_make_targets,
                "recommended_make_target_scope": _summarize_make_targets(recommended_make_targets),
            }
        )
    return missing_prerequisites


def _build_blocked_root_preview_entry(
    *,
    root_id: int,
    bundle_paths: Any,
    output_dir: Path,
    missing_prerequisites: list[dict[str, Any]],
) -> dict[str, Any]:
    recommended_make_targets = _aggregate_make_targets(missing_prerequisites)
    return {
        "root_id": int(root_id),
        "summary": {
            "preview_status": PREVIEW_STATUS_BLOCKED,
            "qa_overall_status": "not_available",
            "missing_prerequisite_count": len(missing_prerequisites),
            "recommended_make_targets": recommended_make_targets,
            "recommended_make_target_scope": _summarize_make_targets(recommended_make_targets),
        },
        "qa_summary": {"overall_status": "not_available"},
        "qa_highlights": [],
        "registry_metadata": {},
        "summary_rows": [
            ("Preview status", PREVIEW_STATUS_BLOCKED),
            ("Missing prerequisites", str(len(missing_prerequisites))),
            ("Operator action", _format_make_target_guidance(recommended_make_targets)),
        ],
        "panels": [],
        "stats": {},
        "missing_prerequisites": list(missing_prerequisites),
        "artifacts": {
            "output_dir": str(output_dir.resolve()),
            "raw_mesh_path": str(bundle_paths.raw_mesh_path.resolve()),
            "raw_skeleton_path": str(bundle_paths.raw_skeleton_path.resolve()),
            "simplified_mesh_path": str(bundle_paths.simplified_mesh_path.resolve()),
            "surface_graph_path": str(bundle_paths.surface_graph_path.resolve()),
            "patch_graph_path": str(bundle_paths.patch_graph_path.resolve()),
            "descriptor_sidecar_path": str(bundle_paths.descriptor_sidecar_path.resolve()),
            "qa_sidecar_path": str(bundle_paths.qa_sidecar_path.resolve()),
        },
    }


def _aggregate_make_targets(records: Iterable[Mapping[str, Any]]) -> list[str]:
    requested_targets = {
        str(target)
        for record in records
        for target in record.get("recommended_make_targets", [])
        if str(target).strip()
    }
    return [target for target in _MAKE_TARGET_ORDER if target in requested_targets]


def _summarize_make_targets(targets: Iterable[str]) -> str:
    normalized_targets = [str(target) for target in targets if str(target).strip()]
    has_make_meshes = _MAKE_MESHES_TARGET in normalized_targets
    has_make_assets = _MAKE_ASSETS_TARGET in normalized_targets
    if has_make_meshes and has_make_assets:
        return "both"
    if has_make_meshes:
        return _MAKE_MESHES_TARGET
    if has_make_assets:
        return _MAKE_ASSETS_TARGET
    return "none"


def _format_make_target_guidance(targets: Iterable[str]) -> str:
    target_summary = _summarize_make_targets(targets)
    if target_summary == "both":
        return "rerun make meshes, then make assets"
    if target_summary == _MAKE_MESHES_TARGET:
        return "rerun make meshes"
    if target_summary == _MAKE_ASSETS_TARGET:
        return "rerun make assets"
    return "none"


def _extract_summary(descriptor_payload: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
    if descriptor_payload is None:
        return None
    representations = descriptor_payload.get("representations", {})
    payload = representations.get(key)
    if isinstance(payload, dict):
        return dict(payload)
    return None


def _fallback_mesh_summary(mesh: trimesh.Trimesh) -> dict[str, Any]:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int32)
    bounds = np.asarray(mesh.bounds, dtype=np.float64)
    extent = bounds[1] - bounds[0]
    return {
        "vertex_count": int(vertices.shape[0]),
        "face_count": int(faces.shape[0]),
        "edge_count": int(np.asarray(mesh.edges_unique).shape[0]),
        "surface_area": float(mesh.area),
        "watertight": bool(mesh.is_watertight),
        "bounds_min": bounds[0].tolist(),
        "bounds_max": bounds[1].tolist(),
        "extent": extent.tolist(),
    }


def _fallback_patch_summary(
    surface_graph_payload: dict[str, np.ndarray],
    patch_graph_payload: dict[str, np.ndarray],
) -> dict[str, Any]:
    patch_sizes = np.asarray(patch_graph_payload.get("patch_sizes", np.empty(0, dtype=np.int32)), dtype=np.int32)
    surface_to_patch = np.asarray(surface_graph_payload.get("surface_to_patch", np.empty(0, dtype=np.int32)))
    surface_vertex_count = int(surface_graph_payload.get("vertices", np.empty((0, 3))).shape[0])
    patch_count = int(patch_sizes.size)
    singleton_count = int(np.count_nonzero(patch_sizes == 1))
    patch_edges = _csr_edges(_load_csr(patch_graph_payload, prefix="adj"))
    max_patch_size = int(patch_sizes.max()) if patch_count else 0
    return {
        "patch_count": patch_count,
        "graph_edge_count": int(patch_edges.shape[0]),
        "surface_vertex_count": surface_vertex_count,
        "surface_to_patch_count": int(surface_to_patch.size),
        "patch_size_max": max_patch_size,
        "patch_size_mean": float(patch_sizes.mean()) if patch_count else 0.0,
        "patch_size_median": float(np.median(patch_sizes)) if patch_count else 0.0,
        "max_patch_vertex_fraction": _ratio(max_patch_size, surface_vertex_count),
        "singleton_patch_count": singleton_count,
        "singleton_patch_fraction": _ratio(singleton_count, patch_count),
    }


def _load_trimesh(path: Path) -> trimesh.Trimesh:
    mesh = trimesh.load_mesh(path, process=False)
    if not isinstance(mesh, trimesh.Trimesh):
        raise TypeError(f"Expected a Trimesh at {path}, got {type(mesh)!r}")
    return mesh


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}.")
    return payload


def _load_npz_payload(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as payload:
        return {key: payload[key] for key in payload.files}


def _load_csr(payload: dict[str, np.ndarray], *, prefix: str) -> sp.csr_matrix:
    shape = tuple(int(value) for value in np.asarray(payload[f"{prefix}_shape"]).tolist())
    return sp.csr_matrix(
        (
            np.asarray(payload[f"{prefix}_data"], dtype=np.float32),
            np.asarray(payload[f"{prefix}_indices"], dtype=np.int32),
            np.asarray(payload[f"{prefix}_indptr"], dtype=np.int32),
        ),
        shape=shape,
    )


def _csr_edges(adj: sp.csr_matrix) -> np.ndarray:
    upper = sp.triu(adj, k=1).tocoo()
    if upper.nnz == 0:
        return np.empty((0, 2), dtype=np.int32)
    edges = np.column_stack(
        [
            np.asarray(upper.row, dtype=np.int32),
            np.asarray(upper.col, dtype=np.int32),
        ]
    )
    order = np.lexsort((edges[:, 1], edges[:, 0]))
    return edges[order]


def _load_skeleton_geometry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "points": np.empty((0, 3), dtype=np.float64),
            "edges": np.empty((0, 2), dtype=np.int32),
        }

    nodes: list[tuple[int, np.ndarray, int]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 7:
                raise ValueError(f"Invalid SWC row in {path}: expected 7 columns, got {len(parts)}")
            node_id = int(parts[0])
            coords = np.asarray([float(parts[2]), float(parts[3]), float(parts[4])], dtype=np.float64)
            parent_id = int(parts[6])
            nodes.append((node_id, coords, parent_id))

    if not nodes:
        return {
            "points": np.empty((0, 3), dtype=np.float64),
            "edges": np.empty((0, 2), dtype=np.int32),
        }

    points = np.vstack([coords for _node_id, coords, _parent_id in nodes])
    node_index = {node_id: idx for idx, (node_id, _coords, _parent_id) in enumerate(nodes)}
    edges: list[list[int]] = []
    for idx, (_node_id, _coords, parent_id) in enumerate(nodes):
        parent_idx = node_index.get(parent_id)
        if parent_idx is None:
            continue
        edges.append([idx, parent_idx])

    return {
        "points": points,
        "edges": np.asarray(edges, dtype=np.int32) if edges else np.empty((0, 2), dtype=np.int32),
    }


def _build_projection_frame(point_sets: list[np.ndarray]) -> ProjectionFrame:
    nonempty_point_sets = [np.asarray(points, dtype=np.float64) for points in point_sets if np.asarray(points).size]
    if not nonempty_point_sets:
        rotation = _rotation_matrix()
        return ProjectionFrame(
            rotation=rotation,
            center=np.zeros(3, dtype=np.float64),
            bounds_min=np.asarray([-1.0, -1.0], dtype=np.float64),
            bounds_max=np.asarray([1.0, 1.0], dtype=np.float64),
        )

    points = np.vstack(nonempty_point_sets)
    center = points.mean(axis=0)
    centered = points - center
    rotated = centered @ _rotation_matrix().T
    projected = rotated[:, :2]
    bounds_min = projected.min(axis=0)
    bounds_max = projected.max(axis=0)
    if np.allclose(bounds_min, bounds_max):
        bounds_min = bounds_min - 1.0
        bounds_max = bounds_max + 1.0
    return ProjectionFrame(
        rotation=_rotation_matrix(),
        center=center,
        bounds_min=bounds_min,
        bounds_max=bounds_max,
    )


def _rotation_matrix() -> np.ndarray:
    theta = np.deg2rad(ROTATION_Z_DEGREES)
    phi = np.deg2rad(ROTATION_X_DEGREES)
    rot_z = np.asarray(
        [
            [np.cos(theta), -np.sin(theta), 0.0],
            [np.sin(theta), np.cos(theta), 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    rot_x = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.0, np.cos(phi), -np.sin(phi)],
            [0.0, np.sin(phi), np.cos(phi)],
        ],
        dtype=np.float64,
    )
    return rot_x @ rot_z


def _project_points(points: np.ndarray, frame: ProjectionFrame) -> np.ndarray:
    if points.size == 0:
        return np.empty((0, 2), dtype=np.float64)

    centered = np.asarray(points, dtype=np.float64) - frame.center
    projected = (centered @ frame.rotation.T)[:, :2]
    bounds_min = frame.bounds_min
    bounds_max = frame.bounds_max
    scale_x = max(bounds_max[0] - bounds_min[0], 1e-9)
    scale_y = max(bounds_max[1] - bounds_min[1], 1e-9)

    x = SVG_PADDING + ((projected[:, 0] - bounds_min[0]) / scale_x) * (SVG_WIDTH - (2.0 * SVG_PADDING))
    y = SVG_PADDING + (1.0 - ((projected[:, 1] - bounds_min[1]) / scale_y)) * (SVG_HEIGHT - (2.0 * SVG_PADDING))
    return np.column_stack([x, y])


def _make_wireframe_panel(
    *,
    title: str,
    subtitle: str,
    points: np.ndarray,
    edges: np.ndarray,
    frame: ProjectionFrame,
    edge_limit: int,
    stroke: str,
) -> dict[str, str]:
    sampled_edges = _sample_rows(edges, edge_limit)
    projected = _project_points(points, frame)
    svg = _render_svg(
        points_2d=projected,
        edges=sampled_edges,
        edge_stroke=stroke,
        edge_opacity=0.72,
        point_subset=np.empty(0, dtype=np.int32),
    )
    return {
        "title": title,
        "subtitle": subtitle,
        "caption": _edge_caption(sampled_edges.shape[0], edges.shape[0]),
        "svg": svg,
    }


def _make_skeleton_panel(
    *,
    title: str,
    skeleton_summary: dict[str, Any],
    points: np.ndarray,
    edges: np.ndarray,
    frame: ProjectionFrame,
) -> dict[str, str]:
    if not bool(skeleton_summary.get("available", False)):
        return {
            "title": title,
            "subtitle": "Optional raw skeleton missing",
            "caption": "No `.swc` file was present for this root ID.",
            "svg": _render_empty_svg("Skeleton unavailable"),
        }

    projected = _project_points(points, frame)
    svg = _render_svg(
        points_2d=projected,
        edges=edges,
        edge_stroke="#8b5cf6",
        edge_opacity=0.78,
        point_colors=["#5b21b6"] * projected.shape[0],
        point_radius=2.1,
    )
    return {
        "title": title,
        "subtitle": (
            f"{int(skeleton_summary.get('node_count', 0))} nodes,"
            f" {int(skeleton_summary.get('segment_count', 0))} segments"
        ),
        "caption": "Parent-child links projected from the raw SWC skeleton.",
        "svg": svg,
    }


def _make_surface_graph_panel(
    *,
    title: str,
    points: np.ndarray,
    edges: np.ndarray,
    frame: ProjectionFrame,
    edge_limit: int,
    surface_to_patch: np.ndarray,
) -> dict[str, str]:
    projected = _project_points(points, frame)
    sampled_edges = _sample_rows(edges, edge_limit)
    point_indices = _sample_indices(projected.shape[0], SURFACE_VERTEX_LIMIT)
    point_colors = [_patch_color(int(surface_to_patch[idx])) for idx in point_indices] if surface_to_patch.size else None
    svg = _render_svg(
        points_2d=projected,
        edges=sampled_edges,
        edge_stroke="#475569",
        edge_opacity=0.5,
        point_subset=point_indices,
        point_colors=point_colors,
        point_radius=1.6,
    )
    return {
        "title": title,
        "subtitle": f"{points.shape[0]} vertices, {edges.shape[0]} edges",
        "caption": (
            f"{sampled_edges.shape[0]} edges shown; sampled vertices are colored by `surface_to_patch`."
            if point_indices.size
            else _edge_caption(sampled_edges.shape[0], edges.shape[0])
        ),
        "svg": svg,
    }


def _make_patch_graph_panel(
    *,
    title: str,
    patch_centroids: np.ndarray,
    patch_sizes: np.ndarray,
    edges: np.ndarray,
    frame: ProjectionFrame,
    edge_limit: int,
) -> dict[str, str]:
    if patch_centroids.size == 0:
        return {
            "title": title,
            "subtitle": "No patch centroids found",
            "caption": "Patch graph payload was empty.",
            "svg": _render_empty_svg("Patch graph unavailable"),
        }

    projected = _project_points(patch_centroids, frame)
    sampled_edges = _sample_rows(edges, edge_limit)
    point_colors = [_patch_color(index) for index in range(projected.shape[0])]
    point_radius = _scale_patch_radii(patch_sizes)
    svg = _render_svg(
        points_2d=projected,
        edges=sampled_edges,
        edge_stroke="#b45309",
        edge_opacity=0.62,
        point_colors=point_colors,
        point_radius=point_radius,
    )
    return {
        "title": title,
        "subtitle": f"{patch_centroids.shape[0]} patches, {edges.shape[0]} edges",
        "caption": "Patch centroids sized by patch membership count.",
        "svg": svg,
    }


def _render_svg(
    *,
    points_2d: np.ndarray,
    edges: np.ndarray,
    edge_stroke: str,
    edge_opacity: float,
    point_subset: np.ndarray | None = None,
    point_colors: list[str] | None = None,
    point_radius: float | np.ndarray | None = None,
) -> str:
    if points_2d.size == 0:
        return _render_empty_svg("No geometry")

    edge_markup: list[str] = []
    for edge in np.asarray(edges, dtype=np.int32):
        start = points_2d[int(edge[0])]
        end = points_2d[int(edge[1])]
        edge_markup.append(
            (
                f'<line x1="{start[0]:.2f}" y1="{start[1]:.2f}"'
                f' x2="{end[0]:.2f}" y2="{end[1]:.2f}"'
                f' stroke="{edge_stroke}" stroke-width="1.15"'
                f' stroke-linecap="round" opacity="{edge_opacity:.2f}" />'
            )
        )

    if point_subset is None:
        point_indices = np.arange(points_2d.shape[0], dtype=np.int32)
    else:
        point_indices = np.asarray(point_subset, dtype=np.int32)

    if point_colors is None:
        point_colors = ["#0f172a"] * point_indices.shape[0]
    if point_radius is None:
        radii = np.full(point_indices.shape[0], 1.8, dtype=np.float64)
    elif np.isscalar(point_radius):
        radii = np.full(point_indices.shape[0], float(point_radius), dtype=np.float64)
    else:
        radii = np.asarray(point_radius, dtype=np.float64)

    point_markup: list[str] = []
    for idx, color, radius in zip(point_indices, point_colors, radii):
        x, y = points_2d[int(idx)]
        point_markup.append(
            (
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{float(radius):.2f}"'
                f' fill="{color}" opacity="0.90" />'
            )
        )

    return (
        f'<svg viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" role="img" aria-label="Geometry preview">'
        f'<rect x="0" y="0" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" rx="16"'
        ' fill="#fffdf8" stroke="#e5dccd" stroke-width="1" />'
        f"{''.join(edge_markup)}"
        f"{''.join(point_markup)}"
        "</svg>"
    )


def _render_empty_svg(message: str) -> str:
    safe_message = html.escape(message)
    return (
        f'<svg viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" role="img" aria-label="{safe_message}">'
        f'<rect x="0" y="0" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" rx="16"'
        ' fill="#faf7f2" stroke="#e5dccd" stroke-width="1" />'
        '<path d="M36 36 L284 224 M284 36 L36 224" stroke="#e2d8c8" stroke-width="3" opacity="0.6" />'
        f'<text x="{SVG_WIDTH / 2:.1f}" y="{SVG_HEIGHT / 2:.1f}" text-anchor="middle"'
        ' dominant-baseline="middle" fill="#7c6f60" font-size="18" font-family="Georgia, serif">'
        f"{safe_message}</text></svg>"
    )


def _sample_rows(values: np.ndarray, limit: int) -> np.ndarray:
    values = np.asarray(values)
    if values.shape[0] <= limit:
        return values
    indices = _sample_indices(values.shape[0], limit)
    return values[indices]


def _sample_indices(count: int, limit: int) -> np.ndarray:
    if count <= 0 or limit <= 0:
        return np.empty(0, dtype=np.int32)
    if count <= limit:
        return np.arange(count, dtype=np.int32)
    indices = np.linspace(0, count - 1, num=limit, dtype=np.int32)
    return np.unique(indices)


def _scale_patch_radii(patch_sizes: np.ndarray) -> np.ndarray:
    if patch_sizes.size == 0:
        return np.empty(0, dtype=np.float64)
    patch_sizes = np.asarray(patch_sizes, dtype=np.float64)
    if np.allclose(patch_sizes.min(), patch_sizes.max()):
        return np.full(patch_sizes.shape[0], 4.2, dtype=np.float64)
    normalized = (patch_sizes - patch_sizes.min()) / max(patch_sizes.max() - patch_sizes.min(), 1e-9)
    return 3.4 + (normalized * 4.0)


def _patch_color(index: int) -> str:
    return PATCH_PALETTE[int(index) % len(PATCH_PALETTE)]


def _edge_caption(rendered_edge_count: int, total_edge_count: int) -> str:
    if rendered_edge_count == total_edge_count:
        return f"Showing all {total_edge_count} undirected edges."
    return f"Showing {rendered_edge_count} of {total_edge_count} undirected edges."


def _qa_highlights(qa_payload: dict[str, Any] | None) -> list[dict[str, str]]:
    if qa_payload is None:
        return []
    checks = qa_payload.get("checks", {})
    highlights: list[dict[str, str]] = []
    for metric_name in sorted(checks):
        check = checks[metric_name]
        if check.get("status") not in {"warn", "fail"}:
            continue
        value = check.get("value")
        formatted_value = (
            _format_ratio(_safe_float(value))
            if check.get("unit") == "ratio"
            else str(value).lower() if isinstance(value, bool) else str(value)
        )
        highlights.append(
            {
                "metric": metric_name,
                "status": str(check.get("status")),
                "value": formatted_value,
                "description": str(check.get("description", "")),
            }
        )
    return highlights


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    if float(denominator) == 0.0:
        return None
    return float(numerator) / float(denominator)


def _format_ratio(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def _display_root_status(entry: Mapping[str, Any]) -> str:
    if str(entry["summary"]["preview_status"]) == PREVIEW_STATUS_BLOCKED:
        return PREVIEW_STATUS_BLOCKED
    return str(entry["summary"].get("qa_overall_status", "unknown"))


def _render_report_html(root_entries: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    toc_items = "".join(
        (
            f'<a class="toc-link" href="#root-{entry["root_id"]}">'
            f'root {entry["root_id"]}'
            f'<span class="toc-status status-{html.escape(_display_root_status(entry))}">'
            f'{html.escape(_display_root_status(entry))}</span></a>'
        )
        for entry in root_entries
    )
    sections = "".join(_render_root_section(entry) for entry in root_entries)
    overall_status = html.escape(str(summary["overall_status"]))
    operator_action_card = ""
    if int(summary.get("blocked_root_count", 0)) > 0:
        operator_action_card = (
            '<div class="hero-card">'
            "<strong>Operator action</strong>"
            f"<span>{html.escape(_format_make_target_guidance(summary.get('recommended_make_targets', [])))}</span>"
            "</div>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>FlyWire Geometry Preview</title>
  <style>
    :root {{
      --bg: #f3eee6;
      --paper: #fffdf8;
      --ink: #1f2937;
      --muted: #64594d;
      --line: #ddcfbd;
      --accent: #0f766e;
      --accent-2: #9a3412;
      --warn: #b45309;
      --fail: #b91c1c;
      --pass: #166534;
      --shadow: 0 18px 40px rgba(74, 52, 26, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(15, 118, 110, 0.10), transparent 28rem),
        radial-gradient(circle at top right, rgba(154, 52, 18, 0.10), transparent 24rem),
        var(--bg);
      color: var(--ink);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 32px 22px 56px;
    }}
    .hero, .root-section {{
      background: rgba(255, 253, 248, 0.92);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
    }}
    .hero {{
      padding: 28px;
      margin-bottom: 22px;
    }}
    h1, h2, h3 {{
      margin: 0;
      font-family: Georgia, "Iowan Old Style", serif;
      font-weight: 600;
      letter-spacing: -0.01em;
    }}
    h1 {{ font-size: 2.1rem; margin-bottom: 8px; }}
    h2 {{ font-size: 1.55rem; margin-bottom: 14px; }}
    h3 {{ font-size: 1.02rem; margin-bottom: 4px; }}
    p {{ margin: 0; color: var(--muted); }}
    code, .mono {{
      font-family: "SFMono-Regular", "Menlo", "Consolas", monospace;
      font-size: 0.92em;
    }}
    .hero-meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 12px;
      margin-top: 18px;
    }}
    .hero-card, .summary-card, .panel, .artifact-card, .qa-card {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 18px;
    }}
    .hero-card {{
      padding: 14px 16px;
    }}
    .hero-card strong {{
      display: block;
      margin-bottom: 4px;
      color: var(--ink);
    }}
    .toc {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .toc-link {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 10px 14px;
      text-decoration: none;
      color: var(--ink);
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff9f0;
    }}
    .toc-status, .status-pill {{
      padding: 3px 10px;
      border-radius: 999px;
      font-size: 0.82rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .status-pass {{ background: rgba(22, 101, 52, 0.12); color: var(--pass); }}
    .status-warn {{ background: rgba(180, 83, 9, 0.12); color: var(--warn); }}
    .status-fail {{ background: rgba(185, 28, 28, 0.12); color: var(--fail); }}
    .status-ready {{ background: rgba(15, 118, 110, 0.12); color: var(--accent); }}
    .status-blocked {{ background: rgba(185, 28, 28, 0.12); color: var(--fail); }}
    .status-unknown {{ background: rgba(71, 85, 105, 0.12); color: #475569; }}
    .root-section {{
      padding: 24px;
      margin-top: 18px;
    }}
    .root-header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 18px;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .summary-card {{
      padding: 14px 16px;
    }}
    .summary-card strong {{
      display: block;
      margin-bottom: 4px;
      color: var(--muted);
      font-size: 0.84rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .panel-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 14px;
      margin-bottom: 16px;
    }}
    .panel {{
      padding: 14px;
    }}
    .panel p {{
      margin-top: 2px;
      font-size: 0.94rem;
    }}
    .panel .caption {{
      margin-top: 10px;
      font-size: 0.88rem;
    }}
    .panel svg {{
      width: 100%;
      height: auto;
      display: block;
      margin-top: 12px;
    }}
    .detail-grid {{
      display: grid;
      grid-template-columns: minmax(280px, 1fr) minmax(280px, 1fr);
      gap: 14px;
    }}
    .artifact-card, .qa-card {{
      padding: 16px;
    }}
    .detail-table {{
      width: 100%;
      border-collapse: collapse;
    }}
    .detail-table td {{
      padding: 8px 0;
      vertical-align: top;
      border-bottom: 1px solid rgba(221, 207, 189, 0.7);
      font-size: 0.94rem;
    }}
    .detail-table tr:last-child td {{
      border-bottom: 0;
    }}
    .detail-table td:first-child {{
      width: 34%;
      color: var(--muted);
      padding-right: 14px;
    }}
    .qa-list {{
      display: grid;
      gap: 10px;
      margin-top: 8px;
    }}
    .qa-item {{
      padding: 12px 14px;
      border-radius: 14px;
      background: #fffbf4;
      border: 1px solid #ecdcc7;
    }}
    .qa-item strong {{
      display: inline-block;
      margin-right: 8px;
    }}
    .qa-empty {{
      color: var(--muted);
    }}
    @media (max-width: 900px) {{
      .detail-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Offline Geometry Preview</h1>
      <p>Static report for raw mesh, simplified mesh, skeleton, surface graph, and patch graph assets built from local pipeline outputs only.</p>
      <div class="hero-meta">
        <div class="hero-card">
          <strong>Preview set</strong>
          <span class="mono">{html.escape(", ".join(str(root_id) for root_id in summary["root_ids"]))}</span>
        </div>
        <div class="hero-card">
          <strong>Report version</strong>
          <span class="mono">{html.escape(str(summary["report_version"]))}</span>
        </div>
        <div class="hero-card">
          <strong>Preview status</strong>
          <span class="status-pill status-{overall_status}">{overall_status}</span>
        </div>
        <div class="hero-card">
          <strong>Blocked roots</strong>
          <span class="mono">{int(summary["blocked_root_count"])}</span>
        </div>
        <div class="hero-card">
          <strong>Deterministic output</strong>
          <span class="mono">{html.escape(str(summary["output_dir"]))}</span>
        </div>
        {operator_action_card}
      </div>
      <div class="toc">{toc_items}</div>
    </section>
    {sections}
  </main>
</body>
</html>
"""


def _render_root_section(entry: dict[str, Any]) -> str:
    if str(entry["summary"]["preview_status"]) == PREVIEW_STATUS_BLOCKED:
        return _render_blocked_root_section(entry)

    summary_rows = "".join(
        (
            "<tr>"
            f"<td>{html.escape(str(label))}</td>"
            f"<td>{html.escape(str(value))}</td>"
            "</tr>"
        )
        for label, value in entry["summary_rows"]
    )
    artifact_rows = "".join(
        (
            "<tr>"
            f"<td>{html.escape(key.replace('_', ' '))}</td>"
            f"<td class=\"mono\">{html.escape(str(value))}</td>"
            "</tr>"
        )
        for key, value in entry["artifacts"].items()
    )
    panels = "".join(
        (
            '<article class="panel">'
            f"<h3>{html.escape(panel['title'])}</h3>"
            f"<p>{html.escape(panel['subtitle'])}</p>"
            f"{panel['svg']}"
            f'<p class="caption">{html.escape(panel["caption"])}</p>'
            "</article>"
        )
        for panel in entry["panels"]
    )
    qa_highlights = entry["qa_highlights"]
    qa_markup = (
        "".join(
            (
                '<div class="qa-item">'
                f'<strong>{html.escape(item["metric"])}</strong>'
                f'<span class="status-pill status-{html.escape(item["status"])}">{html.escape(item["status"])}</span>'
                f"<p>value: {html.escape(item['value'])}</p>"
                f"<p>{html.escape(item['description'])}</p>"
                "</div>"
            )
            for item in qa_highlights
        )
        if qa_highlights
        else '<p class="qa-empty">No warning or failure checks for this root ID.</p>'
    )
    qa_status = html.escape(_display_root_status(entry))
    face_ratio_card = (
        '<div class="summary-card"><strong>Face ratio</strong>'
        f'<span>{html.escape(_format_ratio(entry["stats"]["simplified_to_raw_face_ratio"]))}</span></div>'
    )
    return (
        f'<section class="root-section" id="root-{entry["root_id"]}">'
        '<div class="root-header">'
        f'<div><h2>Root {entry["root_id"]}</h2><p>Bundle-level offline sanity check.</p></div>'
        f'<span class="status-pill status-{qa_status}">{qa_status}</span>'
        "</div>"
        '<div class="summary-grid">'
        f'<div class="summary-card"><strong>Raw faces</strong><span>{entry["stats"]["raw_face_count"]}</span></div>'
        f'<div class="summary-card"><strong>Simplified faces</strong><span>{entry["stats"]["simplified_face_count"]}</span></div>'
        f"{face_ratio_card}"
        f'<div class="summary-card"><strong>Surface edges</strong><span>{entry["stats"]["surface_graph_edge_count"]}</span></div>'
        f'<div class="summary-card"><strong>Patch count</strong><span>{entry["stats"]["patch_count"]}</span></div>'
        f'<div class="summary-card"><strong>Patch edges</strong><span>{entry["stats"]["patch_graph_edge_count"]}</span></div>'
        f'<div class="summary-card"><strong>Skeleton</strong><span>{"available" if entry["stats"]["skeleton_available"] else "missing"}</span></div>'
        "</div>"
        f'<div class="panel-grid">{panels}</div>'
        '<div class="detail-grid">'
        '<section class="artifact-card"><h3>Summary</h3><table class="detail-table">'
        f"{summary_rows}</table></section>"
        '<section class="artifact-card"><h3>Artifacts</h3><table class="detail-table">'
        f"{artifact_rows}</table></section>"
        "</div>"
        '<section class="qa-card" style="margin-top: 14px;"><h3>QA Highlights</h3>'
        f'<div class="qa-list">{qa_markup}</div></section>'
        "</section>"
    )


def _render_blocked_root_section(entry: Mapping[str, Any]) -> str:
    summary_rows = "".join(
        (
            "<tr>"
            f"<td>{html.escape(str(label))}</td>"
            f"<td>{html.escape(str(value))}</td>"
            "</tr>"
        )
        for label, value in entry["summary_rows"]
    )
    artifact_rows = "".join(
        (
            "<tr>"
            f"<td>{html.escape(str(key).replace('_', ' '))}</td>"
            f"<td class=\"mono\">{html.escape(str(value))}</td>"
            "</tr>"
        )
        for key, value in entry["artifacts"].items()
    )
    missing_markup = "".join(
        (
            '<div class="qa-item">'
            f"<strong>{html.escape(str(item['asset_key']))}</strong>"
            '<span class="status-pill status-blocked">blocked</span>'
            f'<p class="mono">{html.escape(str(item["path"]))}</p>'
            f'<p>Rerun target: {html.escape(str(item["recommended_make_target_scope"]))}</p>'
            f'<p>Operator action: {html.escape(_format_make_target_guidance(item["recommended_make_targets"]))}</p>'
            "</div>"
        )
        for item in entry["missing_prerequisites"]
    )
    operator_action = _format_make_target_guidance(entry["summary"].get("recommended_make_targets", []))
    return (
        f'<section class="root-section" id="root-{entry["root_id"]}">'
        '<div class="root-header">'
        f'<div><h2>Root {entry["root_id"]}</h2><p>Blocked before preview rendering because required local inputs are missing.</p></div>'
        '<span class="status-pill status-blocked">blocked</span>'
        "</div>"
        '<div class="summary-grid">'
        f'<div class="summary-card"><strong>Missing prerequisites</strong><span>{int(entry["summary"]["missing_prerequisite_count"])}</span></div>'
        f'<div class="summary-card"><strong>Rerun target</strong><span>{html.escape(str(entry["summary"]["recommended_make_target_scope"]))}</span></div>'
        f'<div class="summary-card"><strong>Operator action</strong><span>{html.escape(operator_action)}</span></div>'
        '<div class="summary-card"><strong>QA status</strong><span>not available</span></div>'
        "</div>"
        '<section class="qa-card" style="margin-bottom: 14px;"><h3>Blocked Preview Inputs</h3>'
        '<p>This root is incomplete. The preview bundle was still written so you can inspect every missing prerequisite together.</p>'
        f'<div class="qa-list">{missing_markup}</div></section>'
        '<div class="detail-grid">'
        '<section class="artifact-card"><h3>Summary</h3><table class="detail-table">'
        f"{summary_rows}</table></section>"
        '<section class="artifact-card"><h3>Expected Artifacts</h3><table class="detail-table">'
        f"{artifact_rows}</table></section>"
        "</div>"
        "</section>"
    )
