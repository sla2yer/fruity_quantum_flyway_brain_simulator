from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import shortest_path
import trimesh

from .io_utils import ensure_dir, write_json


@dataclass
class MeshAssetPaths:
    raw_mesh_path: Path
    raw_skeleton_path: Path | None
    processed_mesh_path: Path
    processed_graph_path: Path
    meta_json_path: Path


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


def _faces_to_adjacency(faces: np.ndarray, n_vertices: int) -> sp.csr_matrix:
    edges = set()
    for tri in faces:
        a, b, c = (int(tri[0]), int(tri[1]), int(tri[2]))
        edges.add(tuple(sorted((a, b))))
        edges.add(tuple(sorted((b, c))))
        edges.add(tuple(sorted((a, c))))

    if not edges:
        raise ValueError("No edges could be built from faces.")

    rows = []
    cols = []
    for i, j in edges:
        rows.extend([i, j])
        cols.extend([j, i])

    data = np.ones(len(rows), dtype=np.float32)
    adj = sp.csr_matrix((data, (rows, cols)), shape=(n_vertices, n_vertices))
    adj.eliminate_zeros()
    return adj


def _uniform_laplacian(adj: sp.csr_matrix) -> sp.csr_matrix:
    deg = np.asarray(adj.sum(axis=1)).ravel()
    d = sp.diags(deg)
    return d - adj


def _choose_patch_vertices(adj: sp.csr_matrix, patch_hops: int, cap: int) -> np.ndarray:
    n_vertices = adj.shape[0]
    seed = n_vertices // 2
    dist = shortest_path(adj, directed=False, indices=seed, unweighted=True)
    patch = np.where(np.isfinite(dist) & (dist <= patch_hops))[0]
    if patch.size > cap:
        order = np.argsort(dist[patch])
        patch = patch[order[:cap]]
    return patch.astype(np.int32)


def fetch_mesh_and_optional_skeleton(
    *,
    root_id: int,
    raw_mesh_dir: str | Path,
    raw_skeleton_dir: str | Path,
    flywire_dataset: str = "public",
    fetch_skeletons: bool = True,
) -> tuple[Path, Path | None]:
    flywire, navis = _optional_imports()

    raw_mesh_dir = ensure_dir(raw_mesh_dir)
    raw_skeleton_dir = ensure_dir(raw_skeleton_dir)

    flywire.set_default_dataset(flywire_dataset)

    neuron = flywire.get_mesh_neuron(int(root_id))
    mesh = trimesh.Trimesh(vertices=np.asarray(neuron.vertices), faces=np.asarray(neuron.faces), process=False)
    raw_mesh_path = raw_mesh_dir / f"{int(root_id)}.ply"
    mesh.export(raw_mesh_path)

    raw_skeleton_path: Path | None = None
    if fetch_skeletons:
        try:
            sk = flywire.get_skeletons(int(root_id))
            raw_skeleton_path = raw_skeleton_dir / f"{int(root_id)}.swc"
            navis.write_swc(sk, raw_skeleton_path)
        except Exception:
            raw_skeleton_path = None

    return raw_mesh_path, raw_skeleton_path


def process_mesh_into_wave_assets(
    *,
    root_id: int,
    raw_mesh_path: str | Path,
    processed_mesh_dir: str | Path,
    processed_graph_dir: str | Path,
    simplify_target_faces: int = 15000,
    patch_hops: int = 6,
    patch_vertex_cap: int = 2500,
) -> dict[str, str]:
    processed_mesh_dir = ensure_dir(processed_mesh_dir)
    processed_graph_dir = ensure_dir(processed_graph_dir)

    raw_mesh = trimesh.load_mesh(raw_mesh_path, process=False)
    if not isinstance(raw_mesh, trimesh.Trimesh):
        raise TypeError(f"Expected a Trimesh at {raw_mesh_path}, got {type(raw_mesh)!r}")

    mesh = raw_mesh.copy()
    target_faces = min(int(simplify_target_faces), int(len(mesh.faces)))
    if target_faces >= 4:
        try:
            mesh = mesh.simplify_quadric_decimation(target_faces)
        except Exception:
            # Fallback: keep original mesh if local environment lacks simplification backend.
            pass

    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.int32)
    adj = _faces_to_adjacency(faces, vertices.shape[0])
    lap = _uniform_laplacian(adj)
    patch_vertices = _choose_patch_vertices(adj, patch_hops, patch_vertex_cap)
    patch_mask = np.zeros(vertices.shape[0], dtype=np.uint8)
    patch_mask[patch_vertices] = 1

    processed_mesh_path = processed_mesh_dir / f"{int(root_id)}.ply"
    graph_path = processed_graph_dir / f"{int(root_id)}_graph.npz"
    meta_json_path = processed_graph_dir / f"{int(root_id)}_meta.json"

    mesh.export(processed_mesh_path)

    np.savez_compressed(
        graph_path,
        vertices=vertices,
        faces=faces,
        adj_data=adj.data,
        adj_indices=adj.indices,
        adj_indptr=adj.indptr,
        adj_shape=np.asarray(adj.shape, dtype=np.int32),
        lap_data=lap.data,
        lap_indices=lap.indices,
        lap_indptr=lap.indptr,
        lap_shape=np.asarray(lap.shape, dtype=np.int32),
        patch_vertices=patch_vertices,
        patch_mask=patch_mask,
    )

    write_json(
        {
            "root_id": int(root_id),
            "n_vertices": int(vertices.shape[0]),
            "n_faces": int(faces.shape[0]),
            "patch_hops": int(patch_hops),
            "patch_vertex_count": int(patch_vertices.size),
            "simplify_target_faces": int(simplify_target_faces),
            "raw_mesh_path": str(raw_mesh_path),
            "processed_mesh_path": str(processed_mesh_path),
            "processed_graph_path": str(graph_path),
        },
        meta_json_path,
    )

    return {
        "processed_mesh_path": str(processed_mesh_path),
        "processed_graph_path": str(graph_path),
        "meta_json_path": str(meta_json_path),
    }
