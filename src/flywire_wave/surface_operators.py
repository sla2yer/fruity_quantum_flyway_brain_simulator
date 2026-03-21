from __future__ import annotations

import heapq
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import scipy.sparse as sp

from .geometry_contract import (
    DEFAULT_BOUNDARY_CONDITION_MODE,
    DEFAULT_FINE_DISCRETIZATION_FAMILY,
    DEFAULT_MASS_TREATMENT,
    DEFAULT_NORMALIZATION,
)


DEFAULT_GEODESIC_NEIGHBORHOOD_HOPS = 2
DEFAULT_GEODESIC_NEIGHBORHOOD_VERTEX_CAP = 32
_GEOMETRY_EPSILON = 1.0e-12


class FineSurfaceOperatorAssemblyError(RuntimeError):
    """Raised when a fine surface operator cannot be assembled safely."""


@dataclass(frozen=True)
class FineSurfaceOperatorBundle:
    payload: dict[str, np.ndarray]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PatchMultiresolutionOperatorBundle:
    coarse_payload: dict[str, np.ndarray]
    transfer_payload: dict[str, np.ndarray]
    metadata: dict[str, Any]


def faces_to_adjacency(faces: np.ndarray, n_vertices: int) -> sp.csr_matrix:
    edges = set()
    for tri in np.asarray(faces, dtype=np.int32):
        a, b, c = (int(tri[0]), int(tri[1]), int(tri[2]))
        edges.add(tuple(sorted((a, b))))
        edges.add(tuple(sorted((b, c))))
        edges.add(tuple(sorted((a, c))))

    if not edges:
        raise ValueError("No edges could be built from faces.")

    rows: list[int] = []
    cols: list[int] = []
    for i, j in sorted(edges):
        rows.extend([i, j])
        cols.extend([j, i])

    data = np.ones(len(rows), dtype=np.float32)
    adj = sp.csr_matrix((data, (rows, cols)), shape=(n_vertices, n_vertices), dtype=np.float32)
    adj.eliminate_zeros()
    adj.sort_indices()
    return adj


def serialize_sparse_matrix(matrix: sp.spmatrix, *, data_dtype: np.dtype = np.float32) -> dict[str, np.ndarray]:
    csr = matrix.tocsr().astype(data_dtype)
    csr.eliminate_zeros()
    csr.sort_indices()
    return {
        "data": csr.data.astype(data_dtype, copy=False),
        "indices": csr.indices.astype(np.int32, copy=False),
        "indptr": csr.indptr.astype(np.int32, copy=False),
        "shape": np.asarray(csr.shape, dtype=np.int32),
    }


def deserialize_sparse_matrix(
    payload: Mapping[str, np.ndarray],
    *,
    prefix: str,
    data_dtype: np.dtype = np.float64,
) -> sp.csr_matrix:
    shape = tuple(int(value) for value in np.asarray(payload[f"{prefix}_shape"], dtype=np.int64))
    matrix = sp.csr_matrix(
        (
            np.asarray(payload[f"{prefix}_data"], dtype=data_dtype),
            np.asarray(payload[f"{prefix}_indices"], dtype=np.int32),
            np.asarray(payload[f"{prefix}_indptr"], dtype=np.int32),
        ),
        shape=shape,
        dtype=data_dtype,
    )
    matrix.eliminate_zeros()
    matrix.sort_indices()
    return matrix


def assemble_fine_surface_operator(
    *,
    root_id: int,
    vertices: np.ndarray,
    faces: np.ndarray,
    geodesic_hops: int = DEFAULT_GEODESIC_NEIGHBORHOOD_HOPS,
    geodesic_vertex_cap: int = DEFAULT_GEODESIC_NEIGHBORHOOD_VERTEX_CAP,
) -> FineSurfaceOperatorBundle:
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int32)

    if vertices.ndim != 2 or vertices.shape[1] != 3:
        raise FineSurfaceOperatorAssemblyError("Fine operator assembly requires vertices with shape (n, 3).")
    if faces.ndim != 2 or faces.shape[1] != 3:
        raise FineSurfaceOperatorAssemblyError("Fine operator assembly requires triangular faces with shape (m, 3).")
    if geodesic_hops < 0:
        raise FineSurfaceOperatorAssemblyError("geodesic_hops must be non-negative.")
    if geodesic_vertex_cap <= 0:
        raise FineSurfaceOperatorAssemblyError("geodesic_vertex_cap must be positive.")

    vertex_count = int(vertices.shape[0])
    face_count = int(faces.shape[0])
    if vertex_count == 0 or face_count == 0:
        raise FineSurfaceOperatorAssemblyError("Fine operator assembly requires a non-empty triangular mesh.")

    face_areas, face_normals, vertex_normals, mass_diagonal = _compute_face_and_vertex_geometry(vertices, faces)
    edge_bundle = _build_edge_bundle(vertices, faces)
    tangent_u, tangent_v = _build_tangent_frames(vertex_normals)

    adjacency = faces_to_adjacency(faces, vertex_count)
    edge_length_matrix = _build_symmetric_edge_matrix(
        vertex_count=vertex_count,
        edge_vertex_indices=edge_bundle["edge_vertex_indices"],
        edge_values=edge_bundle["edge_lengths"],
    )
    cotangent_weight_matrix = _build_symmetric_edge_matrix(
        vertex_count=vertex_count,
        edge_vertex_indices=edge_bundle["edge_vertex_indices"],
        edge_values=edge_bundle["cotangent_weights"],
    )
    stiffness = _assemble_stiffness_matrix(
        vertex_count=vertex_count,
        edge_vertex_indices=edge_bundle["edge_vertex_indices"],
        cotangent_weights=edge_bundle["cotangent_weights"],
    )
    operator = _assemble_mass_normalized_operator(stiffness=stiffness, mass_diagonal=mass_diagonal)
    geodesic = _assemble_geodesic_neighborhoods(
        edge_length_matrix,
        max_hops=geodesic_hops,
        max_vertices_per_seed=geodesic_vertex_cap,
    )

    payload: dict[str, np.ndarray] = {
        "root_id": np.asarray(int(root_id), dtype=np.int64),
        "vertices": vertices.astype(np.float32),
        "faces": faces.astype(np.int32, copy=False),
        "face_areas": face_areas.astype(np.float32),
        "face_normals": face_normals.astype(np.float32),
        "vertex_normals": vertex_normals.astype(np.float32),
        "tangent_u": tangent_u.astype(np.float32),
        "tangent_v": tangent_v.astype(np.float32),
        "mass_diagonal": mass_diagonal.astype(np.float32),
        "vertex_areas": mass_diagonal.astype(np.float32),
        "edge_vertex_indices": edge_bundle["edge_vertex_indices"].astype(np.int32),
        "edge_lengths": edge_bundle["edge_lengths"].astype(np.float32),
        "edge_vectors": edge_bundle["edge_vectors"].astype(np.float32),
        "edge_face_counts": edge_bundle["edge_face_counts"].astype(np.int32),
        "cotangent_weights": edge_bundle["cotangent_weights"].astype(np.float32),
        "boundary_vertex_mask": edge_bundle["boundary_vertex_mask"].astype(bool),
        "boundary_edge_mask": edge_bundle["boundary_edge_mask"].astype(bool),
        "boundary_face_mask": edge_bundle["boundary_face_mask"].astype(bool),
        "geodesic_neighbor_indices": geodesic["indices"].astype(np.int32),
        "geodesic_neighbor_indptr": geodesic["indptr"].astype(np.int32),
        "geodesic_neighbor_distances": geodesic["distances"].astype(np.float32),
        "geodesic_neighbor_hops": geodesic["hops"].astype(np.int32),
    }
    for prefix, matrix in (
        ("adj", adjacency),
        ("edge_length", edge_length_matrix),
        ("cotangent_weight", cotangent_weight_matrix),
        ("stiffness", stiffness),
        ("operator", operator),
    ):
        payload.update({f"{prefix}_{key}": value for key, value in serialize_sparse_matrix(matrix).items()})

    metadata = {
        "realization_mode": "cotangent_fem_fine_operator",
        "preferred_discretization_family": DEFAULT_FINE_DISCRETIZATION_FAMILY,
        "discretization_family": DEFAULT_FINE_DISCRETIZATION_FAMILY,
        "mass_treatment": DEFAULT_MASS_TREATMENT,
        "normalization": DEFAULT_NORMALIZATION,
        "boundary_condition_mode": DEFAULT_BOUNDARY_CONDITION_MODE,
        "weighting_scheme": "cotangent_half_weight",
        "operator_matrix_role": "symmetric_mass_normalized_stiffness",
        "stiffness_matrix_role": "cotangent_stiffness",
        "mass_matrix_role": "diagonal_lumped_mass",
        "orientation_convention": {
            "face_winding": "input_simplified_mesh_winding",
            "tangent_frame": "right_handed",
            "tangent_u_construction": "least_aligned_global_axis_projected_to_tangent_plane",
            "tangent_v_construction": "cross(vertex_normal, tangent_u)",
        },
        "geodesic_neighborhood": {
            "mode": "edge_path_dijkstra_hop_capped",
            "distance_metric": "piecewise_linear_edge_path",
            "max_hops": int(geodesic_hops),
            "max_vertices_per_seed": int(geodesic_vertex_cap),
            "includes_self": True,
        },
        "matrix_properties": {
            "stiffness_symmetric": True,
            "operator_symmetric": True,
            "expected_semidefinite": "positive_semidefinite",
            "constant_nullspace_on_stiffness": True,
        },
        "supporting_geometry": {
            "stores_vertices_and_faces": True,
            "stores_edge_geometry": True,
            "stores_boundary_masks": True,
            "stores_vertex_normals": True,
            "stores_tangent_frames": True,
            "stores_geodesic_neighborhoods": True,
            "stores_mass_diagonal": True,
        },
        "counts": {
            "vertex_count": vertex_count,
            "face_count": face_count,
            "edge_count": int(edge_bundle["edge_vertex_indices"].shape[0]),
            "boundary_vertex_count": int(np.count_nonzero(edge_bundle["boundary_vertex_mask"])),
            "boundary_edge_count": int(np.count_nonzero(edge_bundle["boundary_edge_mask"])),
            "boundary_face_count": int(np.count_nonzero(edge_bundle["boundary_face_mask"])),
            "geodesic_row_nnz_max": int(geodesic["row_nnz_max"]),
        },
    }
    return FineSurfaceOperatorBundle(payload=payload, metadata=metadata)


def assemble_patch_multiresolution_operators(
    *,
    root_id: int,
    vertices: np.ndarray,
    surface_to_patch: np.ndarray,
    patch_sizes: np.ndarray,
    patch_seed_vertices: np.ndarray,
    patch_centroids: np.ndarray,
    member_vertex_indices: np.ndarray,
    member_vertex_indptr: np.ndarray,
    fine_mass_diagonal: np.ndarray,
    fine_stiffness: sp.csr_matrix,
    fine_operator: sp.csr_matrix | None = None,
) -> PatchMultiresolutionOperatorBundle:
    vertices = np.asarray(vertices, dtype=np.float64)
    surface_to_patch = np.asarray(surface_to_patch, dtype=np.int32)
    patch_sizes = np.asarray(patch_sizes, dtype=np.int32)
    patch_seed_vertices = np.asarray(patch_seed_vertices, dtype=np.int32)
    patch_centroids = np.asarray(patch_centroids, dtype=np.float64)
    member_vertex_indices = np.asarray(member_vertex_indices, dtype=np.int32)
    member_vertex_indptr = np.asarray(member_vertex_indptr, dtype=np.int32)
    fine_mass_diagonal = np.asarray(fine_mass_diagonal, dtype=np.float64)
    fine_stiffness = _sorted_csr(fine_stiffness.astype(np.float64))
    fine_operator = (
        _assemble_mass_normalized_operator(stiffness=fine_stiffness, mass_diagonal=fine_mass_diagonal)
        if fine_operator is None
        else _sorted_csr(fine_operator.astype(np.float64))
    )

    surface_vertex_count = int(surface_to_patch.shape[0])
    patch_count = int(patch_sizes.shape[0])
    _validate_patch_membership(
        vertices=vertices,
        surface_to_patch=surface_to_patch,
        patch_sizes=patch_sizes,
        patch_seed_vertices=patch_seed_vertices,
        patch_centroids=patch_centroids,
        member_vertex_indices=member_vertex_indices,
        member_vertex_indptr=member_vertex_indptr,
        fine_mass_diagonal=fine_mass_diagonal,
        fine_stiffness=fine_stiffness,
        fine_operator=fine_operator,
    )

    restriction, prolongation, coarse_mass_diagonal = _build_mass_aware_patch_transfer_operators(
        surface_to_patch=surface_to_patch,
        fine_mass_diagonal=fine_mass_diagonal,
        patch_count=patch_count,
    )
    normalized_restriction, normalized_prolongation = _build_mass_normalized_patch_transfer_operators(
        surface_to_patch=surface_to_patch,
        fine_mass_diagonal=fine_mass_diagonal,
        coarse_mass_diagonal=coarse_mass_diagonal,
        patch_count=patch_count,
    )

    coarse_stiffness = _symmetrize_sparse_matrix(prolongation.transpose().tocsr() @ fine_stiffness @ prolongation)
    coarse_operator = _assemble_mass_normalized_operator(
        stiffness=coarse_stiffness,
        mass_diagonal=coarse_mass_diagonal,
    )
    coarse_operator = _symmetrize_sparse_matrix(coarse_operator)

    quality_metrics = _build_multiresolution_quality_metrics(
        vertices=vertices,
        patch_centroids=patch_centroids,
        fine_mass_diagonal=fine_mass_diagonal,
        coarse_mass_diagonal=coarse_mass_diagonal,
        restriction=restriction,
        prolongation=prolongation,
        normalized_restriction=normalized_restriction,
        normalized_prolongation=normalized_prolongation,
        fine_operator=fine_operator,
        coarse_operator=coarse_operator,
    )

    coarse_payload: dict[str, np.ndarray] = {
        "root_id": np.asarray(int(root_id), dtype=np.int64),
        "patch_count": np.asarray(patch_count, dtype=np.int32),
        "surface_vertex_count": np.asarray(surface_vertex_count, dtype=np.int32),
        "surface_to_patch": surface_to_patch.astype(np.int32, copy=False),
        "patch_sizes": patch_sizes.astype(np.int32, copy=False),
        "patch_seed_vertices": patch_seed_vertices.astype(np.int32, copy=False),
        "patch_centroids": patch_centroids.astype(np.float32),
        "member_vertex_indices": member_vertex_indices.astype(np.int32, copy=False),
        "member_vertex_indptr": member_vertex_indptr.astype(np.int32, copy=False),
        "mass_diagonal": coarse_mass_diagonal.astype(np.float32),
        "patch_areas": coarse_mass_diagonal.astype(np.float32),
        "fine_mass_total": np.asarray(float(fine_mass_diagonal.sum()), dtype=np.float64),
        "coarse_mass_total": np.asarray(float(coarse_mass_diagonal.sum()), dtype=np.float64),
    }
    coarse_payload.update(
        {f"stiffness_{key}": value for key, value in serialize_sparse_matrix(coarse_stiffness).items()}
    )
    coarse_payload.update(
        {f"operator_{key}": value for key, value in serialize_sparse_matrix(coarse_operator).items()}
    )
    coarse_payload.update(_serialize_quality_metrics(quality_metrics))

    transfer_payload: dict[str, np.ndarray] = {
        "root_id": np.asarray(int(root_id), dtype=np.int64),
        "patch_count": np.asarray(patch_count, dtype=np.int32),
        "surface_vertex_count": np.asarray(surface_vertex_count, dtype=np.int32),
        "surface_to_patch": surface_to_patch.astype(np.int32, copy=False),
        "patch_sizes": patch_sizes.astype(np.int32, copy=False),
        "member_vertex_indices": member_vertex_indices.astype(np.int32, copy=False),
        "member_vertex_indptr": member_vertex_indptr.astype(np.int32, copy=False),
        "fine_mass_diagonal": fine_mass_diagonal.astype(np.float32),
        "coarse_mass_diagonal": coarse_mass_diagonal.astype(np.float32),
        "fine_mass_total": np.asarray(float(fine_mass_diagonal.sum()), dtype=np.float64),
        "coarse_mass_total": np.asarray(float(coarse_mass_diagonal.sum()), dtype=np.float64),
    }
    transfer_payload.update({f"restriction_{key}": value for key, value in serialize_sparse_matrix(restriction).items()})
    transfer_payload.update({f"prolongation_{key}": value for key, value in serialize_sparse_matrix(prolongation).items()})
    transfer_payload.update(
        {
            f"normalized_restriction_{key}": value
            for key, value in serialize_sparse_matrix(normalized_restriction).items()
        }
    )
    transfer_payload.update(
        {
            f"normalized_prolongation_{key}": value
            for key, value in serialize_sparse_matrix(normalized_prolongation).items()
        }
    )
    transfer_payload.update(_serialize_quality_metrics(quality_metrics))

    metadata = {
        "realization_mode": "cotangent_fem_galerkin_patch_multiresolution",
        "coarse_discretization_family": "piecewise_constant_patch_galerkin_on_triangle_mesh_cotangent_fem",
        "coarse_mass_treatment": "patch_aggregated_lumped_mass",
        "transfer_restriction_mode": "lumped_mass_patch_average",
        "transfer_prolongation_mode": "constant_on_patch",
        "transfer_preserves_mass_or_area_totals": True,
        "normalized_state_transfer_available": True,
        "coarse_operator_construction": {
            "basis_family": "surface_patch_piecewise_constant",
            "restriction": "lumped_mass_patch_average",
            "prolongation": "piecewise_constant_patch_injection",
            "normalized_transfer": "mass_normalized_orthogonal_patch_basis",
            "coarse_mass": "patch_aggregated_lumped_mass",
            "coarse_stiffness": "galerkin_projection_PtKP",
            "coarse_operator": "mass_normalized_from_projected_stiffness",
        },
        "coarse_operator_quality_metrics": quality_metrics,
        "matrix_properties": {
            "coarse_stiffness_symmetric": True,
            "coarse_operator_symmetric": True,
            "coarse_constant_nullspace_on_stiffness": True,
            "normalized_transfer_adjoint_pair": True,
        },
        "supporting_geometry": {
            "stores_transfer_operators": True,
            "stores_normalized_transfer_operators": True,
            "stores_patch_membership": True,
            "stores_coarse_mass_diagonal": True,
            "stores_quality_metrics": True,
        },
        "counts": {
            "patch_count": patch_count,
            "coarse_operator_nnz": int(coarse_operator.nnz),
            "coarse_stiffness_nnz": int(coarse_stiffness.nnz),
            "restriction_nnz": int(restriction.nnz),
            "prolongation_nnz": int(prolongation.nnz),
            "normalized_restriction_nnz": int(normalized_restriction.nnz),
            "normalized_prolongation_nnz": int(normalized_prolongation.nnz),
        },
    }
    return PatchMultiresolutionOperatorBundle(
        coarse_payload=coarse_payload,
        transfer_payload=transfer_payload,
        metadata=metadata,
    )


def _compute_face_and_vertex_geometry(
    vertices: np.ndarray,
    faces: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    face_areas = np.zeros(int(faces.shape[0]), dtype=np.float64)
    face_normals = np.zeros((int(faces.shape[0]), 3), dtype=np.float64)
    vertex_normal_accumulator = np.zeros((int(vertices.shape[0]), 3), dtype=np.float64)
    mass_diagonal = np.zeros(int(vertices.shape[0]), dtype=np.float64)

    for face_index, tri in enumerate(faces):
        i, j, k = (int(tri[0]), int(tri[1]), int(tri[2]))
        vi = vertices[i]
        vj = vertices[j]
        vk = vertices[k]
        cross_vector = np.cross(vj - vi, vk - vi)
        double_area = float(np.linalg.norm(cross_vector))
        if double_area <= _GEOMETRY_EPSILON:
            raise FineSurfaceOperatorAssemblyError(
                f"Degenerate triangle detected during fine operator assembly at face index {face_index}."
            )
        face_area = 0.5 * double_area
        unit_normal = cross_vector / double_area

        face_areas[face_index] = face_area
        face_normals[face_index] = unit_normal
        vertex_normal_accumulator[i] += cross_vector
        vertex_normal_accumulator[j] += cross_vector
        vertex_normal_accumulator[k] += cross_vector
        shared_mass = face_area / 3.0
        mass_diagonal[i] += shared_mass
        mass_diagonal[j] += shared_mass
        mass_diagonal[k] += shared_mass

    vertex_normals = _normalize_vectors(vertex_normal_accumulator, label="vertex normals")
    if np.any(mass_diagonal <= _GEOMETRY_EPSILON):
        raise FineSurfaceOperatorAssemblyError("Lumped mass assembly produced a non-positive vertex mass.")
    return face_areas, face_normals, vertex_normals, mass_diagonal


def _build_edge_bundle(vertices: np.ndarray, faces: np.ndarray) -> dict[str, np.ndarray]:
    edge_records: dict[tuple[int, int], dict[str, float]] = {}
    face_edges: list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]] = []

    for face_index, tri in enumerate(faces):
        i, j, k = (int(tri[0]), int(tri[1]), int(tri[2]))
        vi = vertices[i]
        vj = vertices[j]
        vk = vertices[k]

        cot_i = _cotangent(vi, vj, vk, face_index=face_index)
        cot_j = _cotangent(vj, vi, vk, face_index=face_index)
        cot_k = _cotangent(vk, vi, vj, face_index=face_index)

        face_edge_keys = (
            tuple(sorted((j, k))),
            tuple(sorted((i, k))),
            tuple(sorted((i, j))),
        )
        face_edges.append(face_edge_keys)

        for edge_key, cotangent in zip(face_edge_keys, (cot_i, cot_j, cot_k)):
            record = edge_records.setdefault(edge_key, {"face_count": 0.0, "cotangent_weight": 0.0})
            record["face_count"] += 1.0
            record["cotangent_weight"] += 0.5 * float(cotangent)

    sorted_edges = sorted(edge_records)
    edge_vertex_indices = np.asarray(sorted_edges, dtype=np.int32)
    edge_vectors = np.asarray([vertices[j] - vertices[i] for i, j in sorted_edges], dtype=np.float64)
    edge_lengths = np.linalg.norm(edge_vectors, axis=1)
    if np.any(edge_lengths <= _GEOMETRY_EPSILON):
        raise FineSurfaceOperatorAssemblyError("Zero-length edge detected during fine operator assembly.")

    edge_face_counts = np.asarray(
        [int(edge_records[edge_key]["face_count"]) for edge_key in sorted_edges],
        dtype=np.int32,
    )
    cotangent_weights = np.asarray(
        [float(edge_records[edge_key]["cotangent_weight"]) for edge_key in sorted_edges],
        dtype=np.float64,
    )
    boundary_edge_mask = edge_face_counts == 1
    boundary_vertex_mask = np.zeros(int(vertices.shape[0]), dtype=bool)
    for is_boundary, (i, j) in zip(boundary_edge_mask, sorted_edges):
        if is_boundary:
            boundary_vertex_mask[int(i)] = True
            boundary_vertex_mask[int(j)] = True
    boundary_edges = {
        edge_key
        for edge_key, is_boundary in zip(sorted_edges, boundary_edge_mask)
        if bool(is_boundary)
    }
    boundary_face_mask = np.asarray(
        [any(edge_key in boundary_edges for edge_key in edge_triplet) for edge_triplet in face_edges],
        dtype=bool,
    )

    return {
        "edge_vertex_indices": edge_vertex_indices,
        "edge_vectors": edge_vectors,
        "edge_lengths": edge_lengths,
        "edge_face_counts": edge_face_counts,
        "cotangent_weights": cotangent_weights,
        "boundary_vertex_mask": boundary_vertex_mask,
        "boundary_edge_mask": boundary_edge_mask,
        "boundary_face_mask": boundary_face_mask,
    }


def _cotangent(vertex: np.ndarray, other_a: np.ndarray, other_b: np.ndarray, *, face_index: int) -> float:
    edge_a = other_a - vertex
    edge_b = other_b - vertex
    cross_norm = float(np.linalg.norm(np.cross(edge_a, edge_b)))
    if cross_norm <= _GEOMETRY_EPSILON:
        raise FineSurfaceOperatorAssemblyError(
            f"Degenerate angle detected during fine operator assembly at face index {face_index}."
        )
    return float(np.dot(edge_a, edge_b) / cross_norm)


def _build_tangent_frames(vertex_normals: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    candidate_axes = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    tangent_u = np.zeros_like(vertex_normals)
    tangent_v = np.zeros_like(vertex_normals)

    for vertex_index, normal in enumerate(vertex_normals):
        alignments = np.abs(candidate_axes @ normal)
        axis = candidate_axes[int(np.argmin(alignments))]
        tangent = axis - float(np.dot(axis, normal)) * normal
        tangent_norm = float(np.linalg.norm(tangent))
        if tangent_norm <= _GEOMETRY_EPSILON:
            raise FineSurfaceOperatorAssemblyError(
                f"Could not construct a tangent frame at vertex index {vertex_index}."
            )
        tangent_u[vertex_index] = tangent / tangent_norm
        tangent_v[vertex_index] = np.cross(normal, tangent_u[vertex_index])

    tangent_v = _normalize_vectors(tangent_v, label="secondary tangent vectors")
    return tangent_u, tangent_v


def _normalize_vectors(vectors: np.ndarray, *, label: str) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1)
    if np.any(norms <= _GEOMETRY_EPSILON):
        raise FineSurfaceOperatorAssemblyError(f"Could not normalize {label}; at least one vector had near-zero norm.")
    return vectors / norms[:, None]


def _build_symmetric_edge_matrix(
    *,
    vertex_count: int,
    edge_vertex_indices: np.ndarray,
    edge_values: np.ndarray,
) -> sp.csr_matrix:
    rows = np.concatenate((edge_vertex_indices[:, 0], edge_vertex_indices[:, 1]))
    cols = np.concatenate((edge_vertex_indices[:, 1], edge_vertex_indices[:, 0]))
    data = np.concatenate((edge_values, edge_values)).astype(np.float64, copy=False)
    matrix = sp.csr_matrix((data, (rows, cols)), shape=(vertex_count, vertex_count), dtype=np.float64)
    matrix.eliminate_zeros()
    matrix.sort_indices()
    return matrix


def _assemble_stiffness_matrix(
    *,
    vertex_count: int,
    edge_vertex_indices: np.ndarray,
    cotangent_weights: np.ndarray,
) -> sp.csr_matrix:
    diagonal = np.zeros(vertex_count, dtype=np.float64)
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []

    for (i, j), weight in zip(edge_vertex_indices, cotangent_weights):
        i_idx = int(i)
        j_idx = int(j)
        w = float(weight)
        diagonal[i_idx] += w
        diagonal[j_idx] += w
        rows.extend([i_idx, j_idx])
        cols.extend([j_idx, i_idx])
        data.extend([-w, -w])

    diagonal_indices = np.arange(vertex_count, dtype=np.int32)
    rows.extend(int(index) for index in diagonal_indices)
    cols.extend(int(index) for index in diagonal_indices)
    data.extend(float(value) for value in diagonal)

    stiffness = sp.csr_matrix(
        (
            np.asarray(data, dtype=np.float64),
            (np.asarray(rows, dtype=np.int32), np.asarray(cols, dtype=np.int32)),
        ),
        shape=(vertex_count, vertex_count),
        dtype=np.float64,
    )
    stiffness.sum_duplicates()
    stiffness.eliminate_zeros()
    stiffness.sort_indices()
    return stiffness


def _assemble_mass_normalized_operator(
    *,
    stiffness: sp.csr_matrix,
    mass_diagonal: np.ndarray,
) -> sp.csr_matrix:
    inv_sqrt_mass = 1.0 / np.sqrt(mass_diagonal)
    scaling = sp.diags(inv_sqrt_mass.astype(np.float64, copy=False))
    operator = (scaling @ stiffness @ scaling).tocsr()
    operator.eliminate_zeros()
    operator.sort_indices()
    return operator


def _validate_patch_membership(
    *,
    vertices: np.ndarray,
    surface_to_patch: np.ndarray,
    patch_sizes: np.ndarray,
    patch_seed_vertices: np.ndarray,
    patch_centroids: np.ndarray,
    member_vertex_indices: np.ndarray,
    member_vertex_indptr: np.ndarray,
    fine_mass_diagonal: np.ndarray,
    fine_stiffness: sp.csr_matrix,
    fine_operator: sp.csr_matrix,
) -> None:
    surface_vertex_count = int(surface_to_patch.shape[0])
    patch_count = int(patch_sizes.shape[0])
    if vertices.ndim != 2 or vertices.shape != (surface_vertex_count, 3):
        raise FineSurfaceOperatorAssemblyError("Patch multiresolution assembly requires vertices with shape (n, 3).")
    if patch_count <= 0:
        raise FineSurfaceOperatorAssemblyError("Patch multiresolution assembly requires at least one coarse patch.")
    if patch_seed_vertices.shape != (patch_count,):
        raise FineSurfaceOperatorAssemblyError("patch_seed_vertices must have shape (patch_count,).")
    if patch_centroids.shape != (patch_count, 3):
        raise FineSurfaceOperatorAssemblyError("patch_centroids must have shape (patch_count, 3).")
    if fine_mass_diagonal.shape != (surface_vertex_count,):
        raise FineSurfaceOperatorAssemblyError("fine_mass_diagonal must match the fine surface vertex count.")
    if fine_stiffness.shape != (surface_vertex_count, surface_vertex_count):
        raise FineSurfaceOperatorAssemblyError("fine_stiffness must be square over the fine surface.")
    if fine_operator.shape != (surface_vertex_count, surface_vertex_count):
        raise FineSurfaceOperatorAssemblyError("fine_operator must be square over the fine surface.")
    if member_vertex_indptr.shape != (patch_count + 1,):
        raise FineSurfaceOperatorAssemblyError("member_vertex_indptr must have shape (patch_count + 1,).")
    if member_vertex_indices.shape != (int(patch_sizes.sum()),):
        raise FineSurfaceOperatorAssemblyError("member_vertex_indices length must equal the sum of patch_sizes.")
    if np.any(surface_to_patch < 0) or np.any(surface_to_patch >= patch_count):
        raise FineSurfaceOperatorAssemblyError("surface_to_patch contains out-of-range patch indices.")
    if np.any(patch_sizes <= 0):
        raise FineSurfaceOperatorAssemblyError("Every coarse patch must contain at least one fine vertex.")
    if np.any(fine_mass_diagonal <= _GEOMETRY_EPSILON):
        raise FineSurfaceOperatorAssemblyError("Fine mass diagonal must stay strictly positive.")
    if np.any(member_vertex_indices < 0) or np.any(member_vertex_indices >= surface_vertex_count):
        raise FineSurfaceOperatorAssemblyError("member_vertex_indices contains out-of-range surface vertices.")
    if not np.array_equal(member_vertex_indptr[1:], np.cumsum(patch_sizes, dtype=np.int32)):
        raise FineSurfaceOperatorAssemblyError("member_vertex_indptr must match the cumulative patch sizes.")

    expected_patch_sizes = np.bincount(surface_to_patch, minlength=patch_count)
    if not np.array_equal(expected_patch_sizes.astype(np.int32), patch_sizes):
        raise FineSurfaceOperatorAssemblyError("patch_sizes must match the realized surface_to_patch counts.")
    if not np.array_equal(np.sort(member_vertex_indices), np.arange(surface_vertex_count, dtype=np.int32)):
        raise FineSurfaceOperatorAssemblyError("Patch membership must cover each fine vertex exactly once.")

    reconstructed_surface_to_patch = np.full(surface_vertex_count, -1, dtype=np.int32)
    for patch_id in range(patch_count):
        start = int(member_vertex_indptr[patch_id])
        end = int(member_vertex_indptr[patch_id + 1])
        members = member_vertex_indices[start:end]
        reconstructed_surface_to_patch[members] = patch_id
    if not np.array_equal(reconstructed_surface_to_patch, surface_to_patch):
        raise FineSurfaceOperatorAssemblyError("member_vertex_indices/member_vertex_indptr do not match surface_to_patch.")


def _build_mass_aware_patch_transfer_operators(
    *,
    surface_to_patch: np.ndarray,
    fine_mass_diagonal: np.ndarray,
    patch_count: int,
) -> tuple[sp.csr_matrix, sp.csr_matrix, np.ndarray]:
    surface_vertex_count = int(surface_to_patch.shape[0])
    vertex_indices = np.arange(surface_vertex_count, dtype=np.int32)
    patch_indices = surface_to_patch.astype(np.int32, copy=False)

    prolongation = sp.csr_matrix(
        (
            np.ones(surface_vertex_count, dtype=np.float64),
            (vertex_indices, patch_indices),
        ),
        shape=(surface_vertex_count, patch_count),
        dtype=np.float64,
    )
    coarse_mass_diagonal = np.bincount(
        patch_indices,
        weights=fine_mass_diagonal.astype(np.float64, copy=False),
        minlength=patch_count,
    ).astype(np.float64, copy=False)
    if np.any(coarse_mass_diagonal <= _GEOMETRY_EPSILON):
        raise FineSurfaceOperatorAssemblyError("Coarse patch mass assembly produced a non-positive patch mass.")

    restriction = sp.csr_matrix(
        (
            (fine_mass_diagonal / coarse_mass_diagonal[patch_indices]).astype(np.float64, copy=False),
            (patch_indices, vertex_indices),
        ),
        shape=(patch_count, surface_vertex_count),
        dtype=np.float64,
    )
    return _sorted_csr(restriction), _sorted_csr(prolongation), coarse_mass_diagonal


def _build_mass_normalized_patch_transfer_operators(
    *,
    surface_to_patch: np.ndarray,
    fine_mass_diagonal: np.ndarray,
    coarse_mass_diagonal: np.ndarray,
    patch_count: int,
) -> tuple[sp.csr_matrix, sp.csr_matrix]:
    surface_vertex_count = int(surface_to_patch.shape[0])
    vertex_indices = np.arange(surface_vertex_count, dtype=np.int32)
    patch_indices = surface_to_patch.astype(np.int32, copy=False)
    normalized_prolongation = sp.csr_matrix(
        (
            (
                np.sqrt(fine_mass_diagonal.astype(np.float64, copy=False))
                / np.sqrt(coarse_mass_diagonal[patch_indices])
            ).astype(np.float64, copy=False),
            (vertex_indices, patch_indices),
        ),
        shape=(surface_vertex_count, patch_count),
        dtype=np.float64,
    )
    normalized_prolongation = _sorted_csr(normalized_prolongation)
    normalized_restriction = _sorted_csr(normalized_prolongation.transpose().tocsr())
    return normalized_restriction, normalized_prolongation


def _build_multiresolution_quality_metrics(
    *,
    vertices: np.ndarray,
    patch_centroids: np.ndarray,
    fine_mass_diagonal: np.ndarray,
    coarse_mass_diagonal: np.ndarray,
    restriction: sp.csr_matrix,
    prolongation: sp.csr_matrix,
    normalized_restriction: sp.csr_matrix,
    normalized_prolongation: sp.csr_matrix,
    fine_operator: sp.csr_matrix,
    coarse_operator: sp.csr_matrix,
) -> dict[str, float]:
    surface_vertex_count = int(fine_mass_diagonal.shape[0])
    patch_count = int(coarse_mass_diagonal.shape[0])
    fine_constant = np.ones(surface_vertex_count, dtype=np.float64)
    coarse_constant = np.ones(patch_count, dtype=np.float64)

    fine_probe_physical = _build_weighted_probe_vector(vertices, weights=fine_mass_diagonal)
    fine_probe_normalized = np.sqrt(fine_mass_diagonal) * fine_probe_physical
    coarse_probe = _build_weighted_probe_vector(patch_centroids, weights=coarse_mass_diagonal)

    galerkin_operator = _sorted_csr(normalized_restriction @ fine_operator @ normalized_prolongation)
    coarse_apply = coarse_operator @ coarse_probe
    transferred_apply = normalized_restriction @ (fine_operator @ (normalized_prolongation @ coarse_probe))
    projected_fine_state = normalized_prolongation @ (normalized_restriction @ fine_probe_normalized)
    projected_fine_apply = normalized_prolongation @ (coarse_operator @ (normalized_restriction @ fine_probe_normalized))
    fine_apply = fine_operator @ fine_probe_normalized

    return {
        "constant_field_restriction_residual_inf": float(
            np.max(np.abs(restriction @ fine_constant - coarse_constant))
        ),
        "constant_field_prolongation_residual_inf": float(
            np.max(np.abs(prolongation @ coarse_constant - fine_constant))
        ),
        "mass_total_relative_error": float(
            abs(float(coarse_mass_diagonal.sum()) - float(fine_mass_diagonal.sum()))
            / max(abs(float(fine_mass_diagonal.sum())), _GEOMETRY_EPSILON)
        ),
        "mass_preservation_probe_absolute_error": float(
            abs(
                float(coarse_mass_diagonal @ (restriction @ fine_probe_physical))
                - float(fine_mass_diagonal @ fine_probe_physical)
            )
        ),
        "normalized_transfer_identity_residual_inf": _sparse_max_abs(
            normalized_restriction @ normalized_prolongation - sp.eye(patch_count, dtype=np.float64, format="csr")
        ),
        "normalized_transfer_adjoint_residual_inf": _sparse_max_abs(
            normalized_restriction - normalized_prolongation.transpose().tocsr()
        ),
        "galerkin_operator_residual_inf": _sparse_max_abs(coarse_operator - galerkin_operator),
        "coarse_application_residual_relative": _relative_residual(
            coarse_apply - transferred_apply,
            coarse_apply,
        ),
        "coarse_rayleigh_quotient_drift_absolute": abs(
            _rayleigh_quotient(coarse_operator, coarse_probe)
            - _rayleigh_quotient(fine_operator, normalized_prolongation @ coarse_probe)
        ),
        "fine_state_projection_residual_relative": _relative_residual(
            fine_probe_normalized - projected_fine_state,
            fine_probe_normalized,
        ),
        "fine_application_projection_residual_relative": _relative_residual(
            fine_apply - projected_fine_apply,
            fine_apply,
        ),
    }


def _serialize_quality_metrics(metrics: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {f"quality_{key}": np.asarray(float(value), dtype=np.float64) for key, value in sorted(metrics.items())}


def _build_weighted_probe_vector(values: np.ndarray, *, weights: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    if array.ndim == 1:
        array = array[:, None]
    if array.ndim != 2 or array.shape[0] != weights.shape[0]:
        raise FineSurfaceOperatorAssemblyError("Weighted probe construction requires aligned value and weight arrays.")

    total_weight = float(weights.sum())
    if total_weight <= _GEOMETRY_EPSILON:
        raise FineSurfaceOperatorAssemblyError("Weighted probe construction requires positive total weight.")

    centered_candidates: list[np.ndarray] = []
    weighted_variances: list[float] = []
    normalized_weights = weights / total_weight
    for column in range(array.shape[1]):
        values_column = array[:, column]
        centered = values_column - float(np.dot(normalized_weights, values_column))
        centered_candidates.append(centered)
        weighted_variances.append(float(np.dot(normalized_weights, centered * centered)))

    for column in np.argsort(weighted_variances)[::-1]:
        candidate = centered_candidates[int(column)]
        norm = float(np.linalg.norm(candidate))
        if norm > _GEOMETRY_EPSILON:
            return candidate / norm

    ramp = np.arange(array.shape[0], dtype=np.float64)
    centered_ramp = ramp - float(np.dot(normalized_weights, ramp))
    ramp_norm = float(np.linalg.norm(centered_ramp))
    if ramp_norm > _GEOMETRY_EPSILON:
        return centered_ramp / ramp_norm
    return np.ones(array.shape[0], dtype=np.float64)


def _relative_residual(delta: np.ndarray, reference: np.ndarray) -> float:
    numerator = float(np.linalg.norm(np.asarray(delta, dtype=np.float64)))
    denominator = float(np.linalg.norm(np.asarray(reference, dtype=np.float64)))
    if denominator <= _GEOMETRY_EPSILON:
        return 0.0 if numerator <= _GEOMETRY_EPSILON else float("inf")
    return numerator / denominator


def _rayleigh_quotient(operator: sp.csr_matrix, state: np.ndarray) -> float:
    state = np.asarray(state, dtype=np.float64)
    denominator = float(state @ state)
    if denominator <= _GEOMETRY_EPSILON:
        return 0.0
    return float(state @ (operator @ state) / denominator)


def _sparse_max_abs(matrix: sp.spmatrix) -> float:
    csr = matrix.tocsr()
    if csr.nnz == 0:
        return 0.0
    return float(np.max(np.abs(csr.data)))


def _sorted_csr(matrix: sp.spmatrix) -> sp.csr_matrix:
    csr = matrix.tocsr()
    csr.eliminate_zeros()
    csr.sort_indices()
    return csr


def _symmetrize_sparse_matrix(matrix: sp.spmatrix) -> sp.csr_matrix:
    return _sorted_csr(((matrix.tocsr() + matrix.transpose().tocsr()) * 0.5).tocsr())


def _assemble_geodesic_neighborhoods(
    edge_length_matrix: sp.csr_matrix,
    *,
    max_hops: int,
    max_vertices_per_seed: int,
) -> dict[str, np.ndarray | int]:
    if max_vertices_per_seed <= 0:
        raise FineSurfaceOperatorAssemblyError("max_vertices_per_seed must be positive.")
    if max_hops < 0:
        raise FineSurfaceOperatorAssemblyError("max_hops must be non-negative.")

    csr = edge_length_matrix.tocsr()
    vertex_count = int(csr.shape[0])
    all_indices: list[int] = []
    all_distances: list[float] = []
    all_hops: list[int] = []
    indptr = np.zeros(vertex_count + 1, dtype=np.int32)
    row_nnz_max = 0

    for source in range(vertex_count):
        indices, distances, hops = _limited_dijkstra_row(
            csr,
            source=source,
            max_hops=max_hops,
            max_vertices=max_vertices_per_seed,
        )
        all_indices.extend(indices)
        all_distances.extend(distances)
        all_hops.extend(hops)
        row_nnz_max = max(row_nnz_max, len(indices))
        indptr[source + 1] = len(all_indices)

    return {
        "indices": np.asarray(all_indices, dtype=np.int32),
        "indptr": indptr,
        "distances": np.asarray(all_distances, dtype=np.float64),
        "hops": np.asarray(all_hops, dtype=np.int32),
        "row_nnz_max": row_nnz_max,
    }


def _limited_dijkstra_row(
    csr: sp.csr_matrix,
    *,
    source: int,
    max_hops: int,
    max_vertices: int,
) -> tuple[list[int], list[float], list[int]]:
    heap: list[tuple[float, int, int]] = [(0.0, 0, int(source))]
    finalized: set[int] = set()
    indices: list[int] = []
    distances: list[float] = []
    hops_list: list[int] = []

    while heap and len(indices) < max_vertices:
        distance, hops, vertex = heapq.heappop(heap)
        if vertex in finalized:
            continue
        finalized.add(vertex)
        indices.append(int(vertex))
        distances.append(float(distance))
        hops_list.append(int(hops))

        if hops >= max_hops:
            continue

        row_start = int(csr.indptr[vertex])
        row_end = int(csr.indptr[vertex + 1])
        for neighbor, edge_length in zip(csr.indices[row_start:row_end], csr.data[row_start:row_end]):
            neighbor_idx = int(neighbor)
            if neighbor_idx in finalized:
                continue
            heapq.heappush(
                heap,
                (
                    float(distance + float(edge_length)),
                    int(hops + 1),
                    neighbor_idx,
                ),
            )

    return indices, distances, hops_list
