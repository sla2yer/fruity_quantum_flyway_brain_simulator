from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import scipy.sparse as sp
import trimesh

from .geometry_contract import (
    ASSET_STATUS_MISSING,
    ASSET_STATUS_READY,
    ASSET_STATUS_SKIPPED,
    COARSE_OPERATOR_KEY,
    FETCH_STATUS_CACHE_HIT,
    FETCH_STATUS_FAILED,
    FETCH_STATUS_FETCHED,
    FETCH_STATUS_SKIPPED,
    GeometryBundlePaths,
    FINE_OPERATOR_KEY,
    OPERATOR_METADATA_KEY,
    PATCH_GRAPH_KEY,
    QA_SIDECAR_KEY,
    RAW_MESH_KEY,
    RAW_SKELETON_KEY,
    SIMPLIFIED_MESH_KEY,
    SURFACE_GRAPH_KEY,
    TRANSFER_OPERATORS_KEY,
    DESCRIPTOR_SIDECAR_KEY,
    build_operator_bundle_metadata,
    normalize_operator_assembly_config,
)
from .geometry_qa import (
    build_descriptor_payload,
    describe_mesh,
    describe_patch_decomposition,
    describe_skeleton,
    evaluate_geometry_qa,
)
from .io_utils import ensure_dir, write_json
from .surface_operators import (
    DEFAULT_GEODESIC_NEIGHBORHOOD_HOPS,
    DEFAULT_GEODESIC_NEIGHBORHOOD_VERTEX_CAP,
    assemble_patch_multiresolution_operators,
    assemble_fine_surface_operator,
    deserialize_sparse_matrix,
    faces_to_adjacency,
    serialize_sparse_matrix,
)


_MESH_FACE_AREA_EPSILON = 1.0e-12


class RawAssetFetchError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        asset_statuses: dict[str, str],
        raw_asset_provenance: dict[str, dict[str, Any]],
    ) -> None:
        super().__init__(message)
        self.asset_statuses = asset_statuses
        self.raw_asset_provenance = raw_asset_provenance


@dataclass(frozen=True)
class PatchDecomposition:
    surface_to_patch: np.ndarray
    patch_seed_vertices: np.ndarray
    patch_sizes: np.ndarray
    patch_centroids: np.ndarray
    member_vertex_indices: np.ndarray
    member_vertex_indptr: np.ndarray
    patch_adj: sp.csr_matrix
    patch_lap: sp.csr_matrix


def _optional_imports() -> tuple[Any, Any]:
    try:
        from fafbseg import flywire  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "fafbseg is required for FlyWire mesh access. Install requirements.txt first."
        ) from exc

    try:
        import navis  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "navis is required for exporting skeletons. Install requirements.txt first."
        ) from exc

    return flywire, navis


def _uniform_laplacian(adj: sp.csr_matrix) -> sp.csr_matrix:
    deg = np.asarray(adj.sum(axis=1)).ravel()
    d = sp.diags(deg)
    return d - adj


def _sanitize_mesh_for_operator_pipeline(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, dict[str, int]]:
    sanitized = mesh.copy()
    faces = np.asarray(sanitized.faces, dtype=np.int64)
    original_face_count = int(faces.shape[0])
    original_vertex_count = int(np.asarray(sanitized.vertices).shape[0])
    cleanup = {
        "original_face_count": original_face_count,
        "sanitized_face_count": original_face_count,
        "removed_face_count": 0,
        "removed_invalid_index_face_count": 0,
        "removed_repeated_vertex_face_count": 0,
        "removed_zero_area_face_count": 0,
        "removed_duplicate_face_count": 0,
        "original_vertex_count": original_vertex_count,
        "sanitized_vertex_count": original_vertex_count,
    }
    if faces.ndim != 2 or faces.shape[0] == 0 or faces.shape[1] != 3:
        return sanitized, cleanup

    vertex_count = original_vertex_count
    valid_index_mask = np.all((faces >= 0) & (faces < vertex_count), axis=1)
    repeated_vertex_mask = valid_index_mask & (
        (faces[:, 0] == faces[:, 1]) | (faces[:, 1] == faces[:, 2]) | (faces[:, 0] == faces[:, 2])
    )
    area_candidate_mask = valid_index_mask & ~repeated_vertex_mask
    positive_area_mask = np.zeros(faces.shape[0], dtype=bool)
    if np.any(area_candidate_mask):
        area_faces = faces[area_candidate_mask]
        vertices = np.asarray(sanitized.vertices, dtype=np.float64)
        areas = np.linalg.norm(
            np.cross(
                vertices[area_faces[:, 1]] - vertices[area_faces[:, 0]],
                vertices[area_faces[:, 2]] - vertices[area_faces[:, 0]],
            ),
            axis=1,
        ) / 2.0
        positive_area_mask[area_candidate_mask] = areas > _MESH_FACE_AREA_EPSILON
    zero_area_mask = area_candidate_mask & ~positive_area_mask

    duplicate_face_mask = np.zeros(faces.shape[0], dtype=bool)
    unique_candidate_mask = valid_index_mask & ~repeated_vertex_mask & positive_area_mask
    if np.any(unique_candidate_mask):
        canonical_faces = np.sort(faces[unique_candidate_mask], axis=1)
        _, unique_indices = np.unique(canonical_faces, axis=0, return_index=True)
        keep_unique_mask = np.zeros(canonical_faces.shape[0], dtype=bool)
        keep_unique_mask[np.sort(unique_indices)] = True
        duplicate_face_mask[np.flatnonzero(unique_candidate_mask)] = ~keep_unique_mask

    keep_face_mask = valid_index_mask & ~repeated_vertex_mask & positive_area_mask & ~duplicate_face_mask
    if not np.any(keep_face_mask):
        raise ValueError("Mesh sanitization removed all faces; cannot build wave assets.")

    cleanup.update(
        {
            "sanitized_face_count": int(np.count_nonzero(keep_face_mask)),
            "removed_face_count": int(np.count_nonzero(~keep_face_mask)),
            "removed_invalid_index_face_count": int(np.count_nonzero(~valid_index_mask)),
            "removed_repeated_vertex_face_count": int(np.count_nonzero(repeated_vertex_mask)),
            "removed_zero_area_face_count": int(np.count_nonzero(zero_area_mask)),
            "removed_duplicate_face_count": int(np.count_nonzero(duplicate_face_mask)),
        }
    )

    if not np.all(keep_face_mask):
        sanitized.update_faces(keep_face_mask)
        sanitized.remove_unreferenced_vertices()
        cleanup["sanitized_vertex_count"] = int(np.asarray(sanitized.vertices).shape[0])

    return sanitized, cleanup


def _collect_patch_vertices(
    adj: sp.csr_matrix,
    *,
    seed: int,
    unassigned: np.ndarray,
    patch_hops: int,
    cap: int,
) -> np.ndarray:
    queue: deque[tuple[int, int]] = deque([(int(seed), 0)])
    visited = {int(seed)}
    patch_vertices: list[int] = []

    while queue and len(patch_vertices) < cap:
        vertex, distance = queue.popleft()
        if not bool(unassigned[vertex]):
            continue

        patch_vertices.append(vertex)
        if distance >= patch_hops:
            continue

        start = int(adj.indptr[vertex])
        end = int(adj.indptr[vertex + 1])
        for neighbor in adj.indices[start:end]:
            neighbor_idx = int(neighbor)
            if neighbor_idx in visited or not bool(unassigned[neighbor_idx]):
                continue
            visited.add(neighbor_idx)
            queue.append((neighbor_idx, distance + 1))

    return np.asarray(patch_vertices, dtype=np.int32)


def _build_patch_membership_arrays(patches: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    member_vertex_indptr = np.zeros(len(patches) + 1, dtype=np.int32)
    if not patches:
        return np.empty(0, dtype=np.int32), member_vertex_indptr

    counts = np.asarray([int(patch.size) for patch in patches], dtype=np.int32)
    member_vertex_indptr[1:] = np.cumsum(counts, dtype=np.int32)
    member_vertex_indices = np.concatenate(patches).astype(np.int32, copy=False)
    return member_vertex_indices, member_vertex_indptr


def _build_patch_adjacency(
    adj: sp.csr_matrix,
    surface_to_patch: np.ndarray,
    *,
    patch_count: int,
) -> sp.csr_matrix:
    if patch_count <= 0:
        return sp.csr_matrix((0, 0), dtype=np.float32)

    upper_edges = sp.triu(adj, k=1).tocoo()
    edge_weights: dict[tuple[int, int], float] = {}
    for row, col, weight in zip(upper_edges.row, upper_edges.col, upper_edges.data):
        patch_u = int(surface_to_patch[int(row)])
        patch_v = int(surface_to_patch[int(col)])
        if patch_u == patch_v:
            continue
        if patch_u > patch_v:
            patch_u, patch_v = patch_v, patch_u
        edge_weights[(patch_u, patch_v)] = edge_weights.get((patch_u, patch_v), 0.0) + float(weight)

    if not edge_weights:
        return sp.csr_matrix((patch_count, patch_count), dtype=np.float32)

    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    for (patch_u, patch_v), weight in sorted(edge_weights.items()):
        rows.extend([patch_u, patch_v])
        cols.extend([patch_v, patch_u])
        data.extend([weight, weight])

    patch_adj = sp.csr_matrix(
        (np.asarray(data, dtype=np.float32), (rows, cols)),
        shape=(patch_count, patch_count),
    )
    patch_adj.eliminate_zeros()
    patch_adj.sort_indices()
    return patch_adj


def _partition_surface_into_patches(
    adj: sp.csr_matrix,
    vertices: np.ndarray,
    *,
    patch_hops: int,
    patch_vertex_cap: int,
) -> PatchDecomposition:
    n_vertices = int(adj.shape[0])
    if patch_hops < 0:
        raise ValueError("patch_hops must be non-negative.")
    if patch_vertex_cap <= 0:
        raise ValueError("patch_vertex_cap must be positive.")
    if n_vertices != int(vertices.shape[0]):
        raise ValueError("Surface graph vertex count does not match vertex coordinates.")

    unassigned = np.ones(n_vertices, dtype=bool)
    surface_to_patch = np.full(n_vertices, -1, dtype=np.int32)
    patches: list[np.ndarray] = []
    patch_seed_vertices: list[int] = []
    patch_centroids: list[np.ndarray] = []

    while bool(np.any(unassigned)):
        seed = int(np.flatnonzero(unassigned)[0])
        patch_vertices = _collect_patch_vertices(
            adj,
            seed=seed,
            unassigned=unassigned,
            patch_hops=patch_hops,
            cap=patch_vertex_cap,
        )
        if patch_vertices.size == 0:
            patch_vertices = np.asarray([seed], dtype=np.int32)

        patch_id = len(patches)
        patches.append(patch_vertices)
        patch_seed_vertices.append(seed)
        surface_to_patch[patch_vertices] = patch_id
        unassigned[patch_vertices] = False
        patch_centroids.append(vertices[patch_vertices].mean(axis=0).astype(np.float32))

    if np.any(surface_to_patch < 0):
        raise RuntimeError("Patch generation did not cover the full surface graph.")

    member_vertex_indices, member_vertex_indptr = _build_patch_membership_arrays(patches)
    patch_adj = _build_patch_adjacency(adj, surface_to_patch, patch_count=len(patches))
    patch_lap = _uniform_laplacian(patch_adj)

    return PatchDecomposition(
        surface_to_patch=surface_to_patch,
        patch_seed_vertices=np.asarray(patch_seed_vertices, dtype=np.int32),
        patch_sizes=np.asarray([int(patch.size) for patch in patches], dtype=np.int32),
        patch_centroids=np.asarray(patch_centroids, dtype=np.float32),
        member_vertex_indices=member_vertex_indices,
        member_vertex_indptr=member_vertex_indptr,
        patch_adj=patch_adj,
        patch_lap=patch_lap,
    )


def fetch_mesh_and_optional_skeleton(
    *,
    root_id: int,
    bundle_paths: GeometryBundlePaths,
    flywire_dataset: str = "public",
    fetch_skeletons: bool = True,
    refetch_mesh: bool = False,
    refetch_skeleton: bool = False,
    require_skeletons: bool = False,
    set_default_dataset: Callable[[str], None] | None = None,
    mesh_fetcher: Callable[[int], Any] | None = None,
    skeleton_fetcher: Callable[[int], Any] | None = None,
    skeleton_writer: Callable[[Any, str | Path], None] | None = None,
) -> dict[str, Any]:
    needs_default_clients = (
        set_default_dataset is None
        or mesh_fetcher is None
        or (fetch_skeletons and (skeleton_fetcher is None or skeleton_writer is None))
    )
    if needs_default_clients:
        flywire, navis = _optional_imports()
        set_default_dataset = flywire.set_default_dataset
        mesh_fetcher = flywire.get_mesh_neuron
        skeleton_fetcher = flywire.get_skeletons
        skeleton_writer = navis.write_swc

    if require_skeletons and not fetch_skeletons:
        raise ValueError("Skeletons cannot be required when meshing.fetch_skeletons is disabled.")

    ensure_dir(bundle_paths.raw_mesh_path.parent)
    ensure_dir(bundle_paths.raw_skeleton_path.parent)

    set_default_dataset(flywire_dataset)

    mesh_provenance = _materialize_raw_mesh(
        root_id=root_id,
        asset_path=bundle_paths.raw_mesh_path,
        refetch=refetch_mesh,
        mesh_fetcher=mesh_fetcher,
    )
    skeleton_provenance = _materialize_raw_skeleton(
        root_id=root_id,
        asset_path=bundle_paths.raw_skeleton_path,
        fetch_skeletons=fetch_skeletons,
        refetch=refetch_skeleton,
        skeleton_fetcher=skeleton_fetcher,
        skeleton_writer=skeleton_writer,
    )

    asset_statuses = {
        RAW_MESH_KEY: str(mesh_provenance["asset_status"]),
        RAW_SKELETON_KEY: str(skeleton_provenance["asset_status"]),
    }
    raw_asset_provenance = {
        RAW_MESH_KEY: mesh_provenance,
        RAW_SKELETON_KEY: skeleton_provenance,
    }

    if mesh_provenance["fetch_status"] == FETCH_STATUS_FAILED:
        raise RawAssetFetchError(
            f"Mesh fetch failed for root_id={root_id}: {mesh_provenance.get('error', 'unknown error')}",
            asset_statuses=asset_statuses,
            raw_asset_provenance=raw_asset_provenance,
        )
    if require_skeletons and skeleton_provenance["fetch_status"] == FETCH_STATUS_FAILED:
        raise RawAssetFetchError(
            f"Skeleton fetch failed for root_id={root_id}: {skeleton_provenance.get('error', 'unknown error')}",
            asset_statuses=asset_statuses,
            raw_asset_provenance=raw_asset_provenance,
        )

    return {
        "asset_statuses": asset_statuses,
        "raw_asset_provenance": raw_asset_provenance,
    }


def _materialize_raw_mesh(
    *,
    root_id: int,
    asset_path: Path,
    refetch: bool,
    mesh_fetcher: Callable[[int], Any],
) -> dict[str, Any]:
    def fetch_and_write() -> None:
        neuron = mesh_fetcher(int(root_id))
        mesh = trimesh.Trimesh(vertices=np.asarray(neuron.vertices), faces=np.asarray(neuron.faces), process=False)
        _write_mesh_atomically(mesh, asset_path)

    return _materialize_raw_asset(
        asset_key=RAW_MESH_KEY,
        asset_path=asset_path,
        fetch_enabled=True,
        refetch=refetch,
        required=True,
        validator=_validate_cached_mesh,
        fetch_and_write=fetch_and_write,
    )


def _materialize_raw_skeleton(
    *,
    root_id: int,
    asset_path: Path,
    fetch_skeletons: bool,
    refetch: bool,
    skeleton_fetcher: Callable[[int], Any] | None,
    skeleton_writer: Callable[[Any, str | Path], None] | None,
) -> dict[str, Any]:
    def fetch_and_write() -> None:
        assert skeleton_fetcher is not None
        assert skeleton_writer is not None
        skeleton = skeleton_fetcher(int(root_id))
        _write_skeleton_atomically(skeleton, asset_path, skeleton_writer)

    return _materialize_raw_asset(
        asset_key=RAW_SKELETON_KEY,
        asset_path=asset_path,
        fetch_enabled=fetch_skeletons,
        refetch=refetch,
        required=False,
        validator=_validate_cached_skeleton,
        fetch_and_write=fetch_and_write if fetch_skeletons else None,
    )


def _materialize_raw_asset(
    *,
    asset_key: str,
    asset_path: Path,
    fetch_enabled: bool,
    refetch: bool,
    required: bool,
    validator: Callable[[Path], tuple[bool, str]],
    fetch_and_write: Callable[[], None] | None,
) -> dict[str, Any]:
    cache_before = _cache_snapshot(asset_path, validator)
    provenance = {
        "path": str(asset_path),
        "required": required,
        "fetch_requested": fetch_enabled,
        "refetch_requested": refetch,
        "checked_at_utc": _utc_now(),
        "cache_before": cache_before,
        "cache_after": dict(cache_before),
        "asset_status": ASSET_STATUS_MISSING,
        "fetch_status": FETCH_STATUS_FAILED,
        "fetch_reason": "",
        "size_bytes": None,
        "mtime_utc": None,
        "error": None,
    }

    if not fetch_enabled:
        provenance["fetch_status"] = FETCH_STATUS_SKIPPED
        provenance["fetch_reason"] = "fetch_disabled"
        provenance["asset_status"] = ASSET_STATUS_SKIPPED
        if cache_before["state"] == "valid":
            provenance["size_bytes"], provenance["mtime_utc"] = _file_metadata(asset_path)
        return provenance

    if cache_before["state"] == "valid" and not refetch:
        provenance["fetch_status"] = FETCH_STATUS_CACHE_HIT
        provenance["fetch_reason"] = "existing_valid_cache"
        provenance["asset_status"] = ASSET_STATUS_READY
        provenance["size_bytes"], provenance["mtime_utc"] = _file_metadata(asset_path)
        return provenance

    provenance["fetch_reason"] = "forced_refetch" if refetch else f"{cache_before['state']}_cache"
    try:
        if fetch_and_write is None:
            raise RuntimeError(f"No fetch handler configured for {asset_key}.")
        fetch_and_write()
        cache_after = _cache_snapshot(asset_path, validator)
        provenance["cache_after"] = cache_after
        if cache_after["state"] != "valid":
            raise RuntimeError(f"Fetched {asset_key} did not validate: {cache_after['reason']}")
        provenance["fetch_status"] = FETCH_STATUS_FETCHED
        provenance["asset_status"] = ASSET_STATUS_READY
        provenance["size_bytes"], provenance["mtime_utc"] = _file_metadata(asset_path)
        return provenance
    except Exception as exc:
        cache_after = _cache_snapshot(asset_path, validator)
        provenance["cache_after"] = cache_after
        provenance["error"] = f"{type(exc).__name__}: {exc}"
        if cache_after["state"] == "valid":
            provenance["asset_status"] = ASSET_STATUS_READY
            provenance["size_bytes"], provenance["mtime_utc"] = _file_metadata(asset_path)
        elif not fetch_enabled:
            provenance["asset_status"] = ASSET_STATUS_SKIPPED
        else:
            provenance["asset_status"] = ASSET_STATUS_MISSING
        return provenance


def _cache_snapshot(path: Path, validator: Callable[[Path], tuple[bool, str]]) -> dict[str, str]:
    valid, reason = validator(path)
    if valid:
        state = "valid"
    elif path.exists():
        state = "invalid"
    else:
        state = "missing"
    return {
        "state": state,
        "reason": reason,
    }


def _validate_cached_mesh(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing_file"
    if path.stat().st_size <= 0:
        return False, "empty_file"
    try:
        mesh = trimesh.load_mesh(path, process=False)
    except Exception as exc:
        return False, f"load_failed:{type(exc).__name__}"
    if not isinstance(mesh, trimesh.Trimesh):
        return False, f"unexpected_type:{type(mesh).__name__}"
    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)
    if vertices.ndim != 2 or vertices.shape[0] == 0 or vertices.shape[1] != 3:
        return False, "invalid_vertices"
    if faces.ndim != 2 or faces.shape[0] == 0 or faces.shape[1] < 3:
        return False, "invalid_faces"
    return True, "validated_trimesh"


def _validate_cached_skeleton(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing_file"
    if path.stat().st_size <= 0:
        return False, "empty_file"

    data_lines = 0
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 7:
                return False, "invalid_swc_columns"
            try:
                int(parts[0])
                int(parts[1])
                float(parts[2])
                float(parts[3])
                float(parts[4])
                float(parts[5])
                int(parts[6])
            except ValueError:
                return False, "invalid_swc_values"
            data_lines += 1
    if data_lines == 0:
        return False, "missing_swc_nodes"
    return True, "validated_swc"


def _write_mesh_atomically(mesh: trimesh.Trimesh, path: Path) -> None:
    tmp_path = path.with_suffix(f".tmp{path.suffix}")
    try:
        mesh.export(tmp_path)
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _write_skeleton_atomically(
    skeleton: Any,
    path: Path,
    skeleton_writer: Callable[[Any, str | Path], None],
) -> None:
    tmp_path = path.with_suffix(f".tmp{path.suffix}")
    try:
        skeleton_writer(skeleton, tmp_path)
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _file_metadata(path: Path) -> tuple[int | None, str | None]:
    if not path.exists():
        return None, None
    stat = path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat()
    return int(stat.st_size), mtime


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _merge_operator_metadata(*metadata_items: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for metadata in metadata_items:
        for key, value in metadata.items():
            if key in {"counts", "matrix_properties", "supporting_geometry"} and isinstance(value, dict):
                nested = dict(merged.get(key, {}))
                nested.update(value)
                merged[key] = nested
                continue
            merged[key] = value
    return merged


def process_mesh_into_wave_assets(
    *,
    root_id: int,
    bundle_paths: GeometryBundlePaths,
    simplify_target_faces: int = 15000,
    patch_hops: int = 6,
    patch_vertex_cap: int = 2500,
    fine_geodesic_hops: int = DEFAULT_GEODESIC_NEIGHBORHOOD_HOPS,
    fine_geodesic_vertex_cap: int = DEFAULT_GEODESIC_NEIGHBORHOOD_VERTEX_CAP,
    operator_assembly: dict[str, Any] | None = None,
    registry_metadata: dict[str, Any] | None = None,
    qa_thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_operator_assembly = normalize_operator_assembly_config(operator_assembly)

    ensure_dir(bundle_paths.simplified_mesh_path.parent)
    ensure_dir(bundle_paths.surface_graph_path.parent)
    ensure_dir(bundle_paths.fine_operator_path.parent)
    ensure_dir(bundle_paths.coarse_operator_path.parent)

    raw_mesh = trimesh.load_mesh(bundle_paths.raw_mesh_path, process=False)
    if not isinstance(raw_mesh, trimesh.Trimesh):
        raise TypeError(f"Expected a Trimesh at {bundle_paths.raw_mesh_path}, got {type(raw_mesh)!r}")
    raw_vertices = np.asarray(raw_mesh.vertices, dtype=np.float32)
    raw_faces = np.asarray(raw_mesh.faces, dtype=np.int32)
    raw_adj = faces_to_adjacency(raw_faces, raw_vertices.shape[0])
    raw_mesh_summary = describe_mesh(raw_mesh, adj=raw_adj)

    mesh = raw_mesh.copy()
    original_face_count = int(len(mesh.faces))
    target_faces = min(int(simplify_target_faces), int(len(mesh.faces)))
    if 4 <= target_faces < original_face_count:
        try:
            mesh = mesh.simplify_quadric_decimation(target_faces)
        except Exception:
            # Fallback: keep original mesh if local environment lacks simplification backend.
            pass

    mesh, mesh_cleanup = _sanitize_mesh_for_operator_pipeline(mesh)

    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.int32)
    adj = faces_to_adjacency(faces, vertices.shape[0])
    lap = _uniform_laplacian(adj)
    patch_decomposition = _partition_surface_into_patches(
        adj,
        vertices,
        patch_hops=patch_hops,
        patch_vertex_cap=patch_vertex_cap,
    )
    surface_graph_payload = {
        "root_id": np.asarray(int(root_id), dtype=np.int64),
        "patch_count": np.asarray(int(patch_decomposition.patch_sizes.size), dtype=np.int32),
        "vertices": vertices,
        "faces": faces,
        "surface_to_patch": patch_decomposition.surface_to_patch,
    }
    surface_graph_payload.update(
        {
            f"adj_{key}": value
            for key, value in serialize_sparse_matrix(adj).items()
        }
    )
    surface_graph_payload.update(
        {
            f"lap_{key}": value
            for key, value in serialize_sparse_matrix(lap).items()
        }
    )

    patch_graph_payload = {
        "root_id": np.asarray(int(root_id), dtype=np.int64),
        "patch_count": np.asarray(int(patch_decomposition.patch_sizes.size), dtype=np.int32),
        "surface_vertex_count": np.asarray(int(vertices.shape[0]), dtype=np.int32),
        "surface_to_patch": patch_decomposition.surface_to_patch,
        "patch_seed_vertices": patch_decomposition.patch_seed_vertices,
        "patch_sizes": patch_decomposition.patch_sizes,
        "patch_centroids": patch_decomposition.patch_centroids,
        "member_vertex_indices": patch_decomposition.member_vertex_indices,
        "member_vertex_indptr": patch_decomposition.member_vertex_indptr,
    }
    patch_graph_payload.update(
        {
            f"adj_{key}": value
            for key, value in serialize_sparse_matrix(patch_decomposition.patch_adj).items()
        }
    )
    patch_graph_payload.update(
        {
            f"lap_{key}": value
            for key, value in serialize_sparse_matrix(patch_decomposition.patch_lap).items()
        }
    )

    fine_operator_bundle = assemble_fine_surface_operator(
        root_id=root_id,
        vertices=vertices,
        faces=faces,
        geodesic_hops=int(fine_geodesic_hops),
        geodesic_vertex_cap=int(fine_geodesic_vertex_cap),
        operator_assembly=operator_assembly,
    )
    multiresolution_bundle = assemble_patch_multiresolution_operators(
        root_id=root_id,
        vertices=vertices,
        surface_to_patch=patch_decomposition.surface_to_patch,
        patch_sizes=patch_decomposition.patch_sizes,
        patch_seed_vertices=patch_decomposition.patch_seed_vertices,
        patch_centroids=patch_decomposition.patch_centroids,
        member_vertex_indices=patch_decomposition.member_vertex_indices,
        member_vertex_indptr=patch_decomposition.member_vertex_indptr,
        fine_mass_diagonal=np.asarray(fine_operator_bundle.payload["mass_diagonal"], dtype=np.float64),
        fine_stiffness=deserialize_sparse_matrix(fine_operator_bundle.payload, prefix="stiffness"),
        fine_operator=deserialize_sparse_matrix(fine_operator_bundle.payload, prefix="operator"),
    )
    realized_operator_metadata = _merge_operator_metadata(
        fine_operator_bundle.metadata,
        multiresolution_bundle.metadata,
    )

    mesh.export(bundle_paths.simplified_mesh_path)

    np.savez_compressed(bundle_paths.surface_graph_path, **surface_graph_payload)
    np.savez_compressed(bundle_paths.fine_operator_path, **fine_operator_bundle.payload)
    np.savez_compressed(bundle_paths.patch_graph_path, **patch_graph_payload)
    np.savez_compressed(bundle_paths.coarse_operator_path, **multiresolution_bundle.coarse_payload)

    simplified_mesh_summary = describe_mesh(mesh, adj=adj)
    coarse_summary = describe_patch_decomposition(
        surface_vertex_count=int(vertices.shape[0]),
        surface_extent=np.asarray(simplified_mesh_summary["extent"], dtype=np.float64),
        surface_component_count=int(simplified_mesh_summary["component_count"]),
        patch_sizes=patch_decomposition.patch_sizes,
        patch_centroids=patch_decomposition.patch_centroids,
        surface_to_patch=patch_decomposition.surface_to_patch,
        member_vertex_indices=patch_decomposition.member_vertex_indices,
        patch_adj=patch_decomposition.patch_adj,
    )
    skeleton_summary = describe_skeleton(bundle_paths.raw_skeleton_path)
    descriptor_payload = build_descriptor_payload(
        root_id=root_id,
        raw_mesh_summary=raw_mesh_summary,
        simplified_mesh_summary=simplified_mesh_summary,
        coarse_summary=coarse_summary,
        skeleton_summary=skeleton_summary,
        simplify_target_faces=int(simplify_target_faces),
        patch_hops=int(patch_hops),
        patch_vertex_cap=int(patch_vertex_cap),
        raw_mesh_path=bundle_paths.raw_mesh_path,
        raw_skeleton_path=bundle_paths.raw_skeleton_path,
        processed_mesh_path=bundle_paths.simplified_mesh_path,
        surface_graph_path=bundle_paths.surface_graph_path,
        patch_graph_path=bundle_paths.patch_graph_path,
        registry_metadata=registry_metadata,
        mesh_cleanup=mesh_cleanup,
    )
    write_json(descriptor_payload, bundle_paths.descriptor_sidecar_path)

    vertex_count_matches_surface_graph = int(vertices.shape[0]) == int(adj.shape[0])
    surface_to_patch_is_complete = bool(np.all(patch_decomposition.surface_to_patch >= 0))
    patch_membership_covers_surface = bool(
        patch_decomposition.member_vertex_indices.size == vertices.shape[0]
        and np.array_equal(
            np.sort(patch_decomposition.member_vertex_indices),
            np.arange(vertices.shape[0], dtype=np.int32),
        )
    )
    patch_graph_node_count_matches_mapping = int(patch_decomposition.patch_adj.shape[0]) == int(
        patch_decomposition.patch_sizes.size
    )
    qa_payload = evaluate_geometry_qa(
        descriptor_payload,
        thresholds=qa_thresholds,
        surface_to_patch_is_complete=surface_to_patch_is_complete,
        patch_membership_covers_surface=patch_membership_covers_surface,
        patch_graph_node_count_matches_mapping=patch_graph_node_count_matches_mapping,
        vertex_count_matches_surface_graph=vertex_count_matches_surface_graph,
    )
    write_json(qa_payload, bundle_paths.qa_sidecar_path)

    write_json(
        {
            **descriptor_payload,
            "descriptor_sidecar_path": str(bundle_paths.descriptor_sidecar_path),
            "qa_sidecar_path": str(bundle_paths.qa_sidecar_path),
            "qa_summary": qa_payload["summary"],
        },
        bundle_paths.legacy_meta_json_path,
    )

    np.savez_compressed(bundle_paths.transfer_operator_path, **multiresolution_bundle.transfer_payload)

    bundle_metadata = {
        "n_vertices": int(descriptor_payload["n_vertices"]),
        "n_faces": int(descriptor_payload["n_faces"]),
        "surface_graph_edge_count": int(descriptor_payload["surface_graph_edge_count"]),
        "patch_count": int(descriptor_payload["patch_count"]),
        "patch_graph_vertex_count": int(descriptor_payload["patch_graph_vertex_count"]),
        "patch_graph_edge_count": int(descriptor_payload["patch_graph_edge_count"]),
        "surface_to_patch_count": int(descriptor_payload["surface_to_patch_count"]),
        "patch_generation_method": "deterministic_bfs_partition",
        "simplify_target_faces": int(simplify_target_faces),
        "raw_mesh_face_count": original_face_count,
        "fine_geodesic_hops": int(fine_geodesic_hops),
        "fine_geodesic_vertex_cap": int(fine_geodesic_vertex_cap),
        "operator_assembly_version": str(normalized_operator_assembly["version"]),
        "boundary_condition_mode": str(normalized_operator_assembly["boundary_condition"]["mode"]),
        "anisotropy_model": str(normalized_operator_assembly["anisotropy"]["model"]),
        "coarse_mass_total": float(multiresolution_bundle.coarse_payload["coarse_mass_total"]),
        "mesh_cleanup": mesh_cleanup,
        "qa_overall_status": str(qa_payload["summary"]["overall_status"]),
        "qa_warning_count": int(qa_payload["summary"]["warning_count"]),
        "qa_failure_count": int(qa_payload["summary"]["failure_count"]),
        "qa_blocking_failure_count": int(qa_payload["summary"]["blocking_failure_count"]),
        "qa_downstream_usable": bool(qa_payload["summary"]["downstream_usable"]),
    }
    asset_statuses = {
        RAW_MESH_KEY: ASSET_STATUS_READY if bundle_paths.raw_mesh_path.exists() else ASSET_STATUS_MISSING,
        SIMPLIFIED_MESH_KEY: ASSET_STATUS_READY,
        SURFACE_GRAPH_KEY: ASSET_STATUS_READY,
        FINE_OPERATOR_KEY: ASSET_STATUS_READY,
        PATCH_GRAPH_KEY: ASSET_STATUS_READY,
        COARSE_OPERATOR_KEY: ASSET_STATUS_READY,
        DESCRIPTOR_SIDECAR_KEY: ASSET_STATUS_READY,
        QA_SIDECAR_KEY: ASSET_STATUS_READY,
        TRANSFER_OPERATORS_KEY: ASSET_STATUS_READY,
        OPERATOR_METADATA_KEY: ASSET_STATUS_READY,
    }
    if bundle_paths.raw_skeleton_path.exists():
        asset_statuses[RAW_SKELETON_KEY] = ASSET_STATUS_READY

    operator_bundle_metadata = build_operator_bundle_metadata(
        bundle_paths=bundle_paths,
        asset_statuses=asset_statuses,
        meshing_config_snapshot={
            "simplify_target_faces": int(simplify_target_faces),
            "patch_hops": int(patch_hops),
            "patch_vertex_cap": int(patch_vertex_cap),
            "fine_geodesic_hops": int(fine_geodesic_hops),
            "fine_geodesic_vertex_cap": int(fine_geodesic_vertex_cap),
            "operator_assembly": normalized_operator_assembly,
            "transfer_restriction_mode": "lumped_mass_patch_average",
            "transfer_prolongation_mode": "constant_on_patch",
        },
        bundle_metadata=bundle_metadata,
        realized_operator_metadata=realized_operator_metadata,
    )
    write_json(operator_bundle_metadata, bundle_paths.operator_metadata_path)

    return {
        "asset_statuses": asset_statuses,
        "descriptor_payload": descriptor_payload,
        "operator_bundle_metadata": operator_bundle_metadata,
        "qa_payload": qa_payload,
        "qa_summary": dict(qa_payload["summary"]),
        "bundle_metadata": bundle_metadata,
    }
