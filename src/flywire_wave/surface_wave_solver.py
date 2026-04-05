from __future__ import annotations

import copy
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .geometry_contract import (
    CLAMPED_BOUNDARY_CONDITION_MODE,
    DEFAULT_BOUNDARY_CONDITION_MODE,
)
from .surface_operators import deserialize_sparse_matrix
from .surface_wave_contract import (
    ACTIVITY_DRIVEN_FIRST_ORDER_RECOVERY_MODE,
    BRANCHING_DISABLED_MODE,
    DEFAULT_SURFACE_WAVE_MODEL_FAMILY,
    DESCRIPTOR_SCALED_DAMPING_BRANCHING_MODE,
    EXTRA_LOCAL_DAMPING_BRANCHING_RESPONSE,
    ISOTROPIC_ANISOTROPY_MODE,
    LINEAR_VELOCITY_DAMPING_MODE,
    NONLINEARITY_DISABLED_MODE,
    OPERATOR_EMBEDDED_ANISOTROPY_MODE,
    POSITIVE_SURFACE_ACTIVATION_RECOVERY_DRIVE,
    RECOVERY_DISABLED_MODE,
    SEMI_IMPLICIT_VELOCITY_SPLIT_SOLVER_FAMILY,
    SURFACE_ACTIVATION_STATE_ID,
    SURFACE_VELOCITY_STATE_ID,
    TANH_SOFT_CLIP_NONLINEARITY_MODE,
    build_surface_wave_model_metadata,
    parse_surface_wave_model_metadata,
)


SURFACE_WAVE_SOLVER_VERSION = "surface_wave_solver.v2"
SURFACE_STATE_RESOLUTION = "surface"
PATCH_STATE_RESOLUTION = "patch"
SUPPORTED_SURFACE_WAVE_STATE_RESOLUTIONS = (
    SURFACE_STATE_RESOLUTION,
    PATCH_STATE_RESOLUTION,
)

INITIALIZED_STAGE = "initialized"
STEP_COMPLETED_STAGE = "step_completed"
FINALIZED_STAGE = "finalized"

LOCALIZED_PULSE_INITIALIZATION = "localized_pulse"
ZERO_INITIALIZATION = "all_zero"
EXPLICIT_STATE_INITIALIZATION = "explicit_state"
SUPPORTED_INITIALIZATION_MODES = (
    ZERO_INITIALIZATION,
    LOCALIZED_PULSE_INITIALIZATION,
    EXPLICIT_STATE_INITIALIZATION,
)

SEMI_IMPLICIT_VELOCITY_SPLIT_STEP_ORDER = (
    "apply_boundary_policy_pre_step",
    "assemble_surface_drive",
    "apply_surface_operator",
    "apply_restoring_sink",
    "apply_recovery_sink",
    "apply_branching_damping",
    "semi_implicit_velocity_damping",
    "update_surface_activation",
    "apply_activation_nonlinearity",
    "update_recovery_state",
    "apply_boundary_policy_post_step",
)

_EPSILON = 1.0e-12
_DT_TOLERANCE_MS = 1.0e-9
_DEFAULT_PULSE_RADIUS_SCALE = 1.5


@dataclass
class SurfaceWaveState:
    resolution: str
    activation: np.ndarray
    velocity: np.ndarray
    recovery: np.ndarray | None = None

    def __post_init__(self) -> None:
        self.resolution = _normalize_resolution(self.resolution)
        self.activation = _as_float_vector(
            self.activation,
            field_name=f"{self.resolution}.activation",
        )
        self.velocity = _as_float_vector(
            self.velocity,
            field_name=f"{self.resolution}.velocity",
        )
        if self.activation.shape != self.velocity.shape:
            raise ValueError(
                f"{self.resolution} activation and velocity must have identical shapes."
            )
        if self.recovery is not None:
            self.recovery = _as_float_vector(
                self.recovery,
                field_name=f"{self.resolution}.recovery",
            )
            if self.recovery.shape != self.activation.shape:
                raise ValueError(
                    f"{self.resolution} recovery must match activation shape."
                )

    @classmethod
    def zeros(
        cls,
        *,
        resolution: str,
        size: int,
        include_recovery: bool = False,
    ) -> SurfaceWaveState:
        normalized_size = _normalize_positive_size(size, field_name="size")
        zeros = np.zeros(normalized_size, dtype=np.float64)
        return cls(
            resolution=resolution,
            activation=zeros.copy(),
            velocity=zeros.copy(),
            recovery=zeros.copy() if include_recovery else None,
        )

    @property
    def size(self) -> int:
        return int(self.activation.shape[0])

    @property
    def has_recovery(self) -> bool:
        return self.recovery is not None

    def copy(self) -> SurfaceWaveState:
        return SurfaceWaveState(
            resolution=self.resolution,
            activation=self.activation.copy(),
            velocity=self.velocity.copy(),
            recovery=None if self.recovery is None else self.recovery.copy(),
        )

    def frozen_copy(self) -> SurfaceWaveState:
        copied = self.copy()
        copied.activation.setflags(write=False)
        copied.velocity.setflags(write=False)
        if copied.recovery is not None:
            copied.recovery.setflags(write=False)
        return copied

    def as_mapping(self) -> dict[str, Any]:
        return {
            "resolution": self.resolution,
            "activation": np.asarray(self.activation, dtype=np.float64).tolist(),
            "velocity": np.asarray(self.velocity, dtype=np.float64).tolist(),
            "recovery": (
                None
                if self.recovery is None
                else np.asarray(self.recovery, dtype=np.float64).tolist()
            ),
        }


@dataclass
class SurfaceWaveOperatorBundle:
    root_id: int
    surface_operator: sp.csr_matrix
    coarse_operator: sp.csr_matrix | None = None
    restriction: sp.csr_matrix | None = None
    prolongation: sp.csr_matrix | None = None
    normalized_restriction: sp.csr_matrix | None = None
    normalized_prolongation: sp.csr_matrix | None = None
    mass_diagonal: np.ndarray | None = None
    patch_mass_diagonal: np.ndarray | None = None
    vertices: np.ndarray | None = None
    boundary_vertex_mask: np.ndarray | None = None
    geodesic_neighbor_indptr: np.ndarray | None = None
    geodesic_neighbor_indices: np.ndarray | None = None
    geodesic_neighbor_distances: np.ndarray | None = None
    surface_to_patch: np.ndarray | None = None
    edge_vertex_indices: np.ndarray | None = None
    cotangent_weights: np.ndarray | None = None
    effective_cotangent_weights: np.ndarray | None = None
    anisotropy_edge_multiplier: np.ndarray | None = None
    geometry_descriptors: dict[str, Any] = field(default_factory=dict)
    boundary_condition_mode: str = DEFAULT_BOUNDARY_CONDITION_MODE
    operator_metadata: dict[str, Any] = field(default_factory=dict)
    source_reference: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.root_id = int(self.root_id)
        self.surface_operator = _as_sorted_csr(
            self.surface_operator,
            field_name="surface_operator",
        )
        if self.surface_operator.shape[0] != self.surface_operator.shape[1]:
            raise ValueError(
                "surface_operator must be square for the surface-wave solver."
            )
        surface_vertex_count = int(self.surface_operator.shape[0])
        if surface_vertex_count < 1:
            raise ValueError("surface_operator must be non-empty.")

        self.coarse_operator = _normalize_optional_csr(
            self.coarse_operator,
            field_name="coarse_operator",
        )
        if self.coarse_operator is not None and (
            self.coarse_operator.shape[0] != self.coarse_operator.shape[1]
        ):
            raise ValueError("coarse_operator must be square when provided.")

        self.restriction = _normalize_optional_csr(
            self.restriction,
            field_name="restriction",
        )
        self.prolongation = _normalize_optional_csr(
            self.prolongation,
            field_name="prolongation",
        )
        self.normalized_restriction = _normalize_optional_csr(
            self.normalized_restriction,
            field_name="normalized_restriction",
        )
        self.normalized_prolongation = _normalize_optional_csr(
            self.normalized_prolongation,
            field_name="normalized_prolongation",
        )

        if self.mass_diagonal is None:
            self.mass_diagonal = np.ones(surface_vertex_count, dtype=np.float64)
        else:
            self.mass_diagonal = _as_float_vector(
                self.mass_diagonal,
                field_name="mass_diagonal",
            )
            if self.mass_diagonal.shape[0] != surface_vertex_count:
                raise ValueError("mass_diagonal must match the surface operator size.")

        patch_count = (
            int(self.coarse_operator.shape[0])
            if self.coarse_operator is not None
            else None
        )
        if self.patch_mass_diagonal is not None:
            self.patch_mass_diagonal = _as_float_vector(
                self.patch_mass_diagonal,
                field_name="patch_mass_diagonal",
            )
            if patch_count is None:
                patch_count = int(self.patch_mass_diagonal.shape[0])
            elif self.patch_mass_diagonal.shape[0] != patch_count:
                raise ValueError(
                    "patch_mass_diagonal must match the coarse operator size."
                )

        if self.vertices is not None:
            vertices = np.asarray(self.vertices, dtype=np.float64)
            if vertices.ndim != 2 or vertices.shape[1] != 3:
                raise ValueError("vertices must have shape (n, 3) when provided.")
            if vertices.shape[0] != surface_vertex_count:
                raise ValueError("vertices must match the surface operator size.")
            self.vertices = np.asarray(vertices, dtype=np.float64)

        if self.boundary_vertex_mask is None:
            self.boundary_vertex_mask = np.zeros(surface_vertex_count, dtype=bool)
        else:
            boundary_vertex_mask = np.asarray(self.boundary_vertex_mask, dtype=bool)
            if boundary_vertex_mask.ndim != 1 or boundary_vertex_mask.shape[0] != surface_vertex_count:
                raise ValueError(
                    "boundary_vertex_mask must be a 1D boolean vector aligned to the surface operator."
                )
            self.boundary_vertex_mask = boundary_vertex_mask.copy()

        self.geodesic_neighbor_indptr = _normalize_optional_int_vector(
            self.geodesic_neighbor_indptr,
            field_name="geodesic_neighbor_indptr",
        )
        self.geodesic_neighbor_indices = _normalize_optional_int_vector(
            self.geodesic_neighbor_indices,
            field_name="geodesic_neighbor_indices",
        )
        self.geodesic_neighbor_distances = _normalize_optional_float_vector(
            self.geodesic_neighbor_distances,
            field_name="geodesic_neighbor_distances",
        )
        if self.geodesic_neighbor_indptr is not None:
            if self.geodesic_neighbor_indptr.shape[0] != surface_vertex_count + 1:
                raise ValueError(
                    "geodesic_neighbor_indptr must have length surface_vertex_count + 1."
                )
            if self.geodesic_neighbor_indices is None or self.geodesic_neighbor_distances is None:
                raise ValueError(
                    "geodesic_neighbor_indices and geodesic_neighbor_distances are required when geodesic_neighbor_indptr is provided."
                )
            if self.geodesic_neighbor_indices.shape != self.geodesic_neighbor_distances.shape:
                raise ValueError(
                    "geodesic_neighbor_indices and geodesic_neighbor_distances must share the same shape."
                )

        self.surface_to_patch = _normalize_optional_int_vector(
            self.surface_to_patch,
            field_name="surface_to_patch",
        )
        if self.surface_to_patch is not None and self.surface_to_patch.shape[0] != surface_vertex_count:
            raise ValueError("surface_to_patch must match the surface operator size.")
        if self.surface_to_patch is not None and patch_count is None:
            patch_count = int(np.max(self.surface_to_patch)) + 1
        if (
            self.surface_to_patch is not None
            and patch_count is not None
            and np.any(self.surface_to_patch >= patch_count)
        ):
            raise ValueError(
                "surface_to_patch indices exceed the inferred patch count."
            )
        self.edge_vertex_indices = _normalize_optional_edge_index_array(
            self.edge_vertex_indices,
            field_name="edge_vertex_indices",
        )
        if self.edge_vertex_indices is not None:
            if np.any(self.edge_vertex_indices < 0) or np.any(
                self.edge_vertex_indices >= surface_vertex_count
            ):
                raise ValueError(
                    "edge_vertex_indices contains out-of-range surface vertices."
                )
        self.cotangent_weights = _normalize_optional_float_vector(
            self.cotangent_weights,
            field_name="cotangent_weights",
        )
        self.effective_cotangent_weights = _normalize_optional_float_vector(
            self.effective_cotangent_weights,
            field_name="effective_cotangent_weights",
        )
        self.anisotropy_edge_multiplier = _normalize_optional_float_vector(
            self.anisotropy_edge_multiplier,
            field_name="anisotropy_edge_multiplier",
        )
        edge_count = (
            None
            if self.edge_vertex_indices is None
            else int(self.edge_vertex_indices.shape[0])
        )
        for field_name, vector in (
            ("cotangent_weights", self.cotangent_weights),
            ("effective_cotangent_weights", self.effective_cotangent_weights),
            ("anisotropy_edge_multiplier", self.anisotropy_edge_multiplier),
        ):
            if vector is not None:
                if edge_count is None:
                    edge_count = int(vector.shape[0])
                elif vector.shape[0] != edge_count:
                    raise ValueError(
                        f"{field_name} must match the number of serialized edges."
                    )
        if self.edge_vertex_indices is None and edge_count is not None:
            raise ValueError(
                "edge_vertex_indices are required when serialized edge weights are provided."
            )
        if (
            self.effective_cotangent_weights is None
            and self.cotangent_weights is not None
            and self.anisotropy_edge_multiplier is not None
        ):
            self.effective_cotangent_weights = (
                self.cotangent_weights * self.anisotropy_edge_multiplier
            )

        if self.restriction is not None:
            expected_patch_count = int(self.restriction.shape[0])
            if patch_count is None:
                patch_count = expected_patch_count
            elif expected_patch_count != patch_count:
                raise ValueError("restriction row count must match the patch count.")
            if int(self.restriction.shape[1]) != surface_vertex_count:
                raise ValueError(
                    "restriction column count must match the surface operator size."
                )
        if self.prolongation is not None:
            expected_patch_count = int(self.prolongation.shape[1])
            if patch_count is None:
                patch_count = expected_patch_count
            elif expected_patch_count != patch_count:
                raise ValueError(
                    "prolongation column count must match the patch count."
                )
            if int(self.prolongation.shape[0]) != surface_vertex_count:
                raise ValueError(
                    "prolongation row count must match the surface operator size."
                )
        if self.normalized_restriction is not None:
            if patch_count is None:
                patch_count = int(self.normalized_restriction.shape[0])
            if self.normalized_restriction.shape != (patch_count, surface_vertex_count):
                raise ValueError(
                    "normalized_restriction must have shape (patch_count, surface_vertex_count)."
                )
        if self.normalized_prolongation is not None:
            if patch_count is None:
                patch_count = int(self.normalized_prolongation.shape[1])
            if self.normalized_prolongation.shape != (surface_vertex_count, patch_count):
                raise ValueError(
                    "normalized_prolongation must have shape (surface_vertex_count, patch_count)."
                )

        self.boundary_condition_mode = str(self.boundary_condition_mode or DEFAULT_BOUNDARY_CONDITION_MODE)
        if (
            self.boundary_condition_mode == CLAMPED_BOUNDARY_CONDITION_MODE
            and not np.any(self.boundary_vertex_mask)
        ):
            raise ValueError(
                "boundary_vertices_clamped_zero requires a non-empty boundary_vertex_mask."
            )
        self.operator_metadata = copy.deepcopy(dict(self.operator_metadata))
        self.geometry_descriptors = copy.deepcopy(dict(self.geometry_descriptors))
        self.source_reference = copy.deepcopy(dict(self.source_reference))

    @classmethod
    def from_fixture(
        cls,
        *,
        root_id: int,
        surface_operator: sp.spmatrix,
        coarse_operator: sp.spmatrix | None = None,
        restriction: sp.spmatrix | None = None,
        prolongation: sp.spmatrix | None = None,
        normalized_restriction: sp.spmatrix | None = None,
        normalized_prolongation: sp.spmatrix | None = None,
        mass_diagonal: Sequence[float] | np.ndarray | None = None,
        patch_mass_diagonal: Sequence[float] | np.ndarray | None = None,
        boundary_vertex_mask: Sequence[bool] | np.ndarray | None = None,
        vertices: np.ndarray | None = None,
        geodesic_neighbor_indptr: Sequence[int] | np.ndarray | None = None,
        geodesic_neighbor_indices: Sequence[int] | np.ndarray | None = None,
        geodesic_neighbor_distances: Sequence[float] | np.ndarray | None = None,
        surface_to_patch: Sequence[int] | np.ndarray | None = None,
        edge_vertex_indices: np.ndarray | None = None,
        cotangent_weights: Sequence[float] | np.ndarray | None = None,
        effective_cotangent_weights: Sequence[float] | np.ndarray | None = None,
        anisotropy_edge_multiplier: Sequence[float] | np.ndarray | None = None,
        geometry_descriptors: Mapping[str, Any] | None = None,
        boundary_condition_mode: str = DEFAULT_BOUNDARY_CONDITION_MODE,
        operator_metadata: Mapping[str, Any] | None = None,
        fixture_name: str = "surface_wave_fixture",
    ) -> SurfaceWaveOperatorBundle:
        return cls(
            root_id=root_id,
            surface_operator=surface_operator.tocsr(),
            coarse_operator=None if coarse_operator is None else coarse_operator.tocsr(),
            restriction=None if restriction is None else restriction.tocsr(),
            prolongation=None if prolongation is None else prolongation.tocsr(),
            normalized_restriction=(
                None if normalized_restriction is None else normalized_restriction.tocsr()
            ),
            normalized_prolongation=(
                None if normalized_prolongation is None else normalized_prolongation.tocsr()
            ),
            mass_diagonal=None if mass_diagonal is None else np.asarray(mass_diagonal, dtype=np.float64),
            patch_mass_diagonal=(
                None if patch_mass_diagonal is None else np.asarray(patch_mass_diagonal, dtype=np.float64)
            ),
            boundary_vertex_mask=(
                None if boundary_vertex_mask is None else np.asarray(boundary_vertex_mask, dtype=bool)
            ),
            vertices=None if vertices is None else np.asarray(vertices, dtype=np.float64),
            geodesic_neighbor_indptr=(
                None if geodesic_neighbor_indptr is None else np.asarray(geodesic_neighbor_indptr, dtype=np.int32)
            ),
            geodesic_neighbor_indices=(
                None if geodesic_neighbor_indices is None else np.asarray(geodesic_neighbor_indices, dtype=np.int32)
            ),
            geodesic_neighbor_distances=(
                None if geodesic_neighbor_distances is None else np.asarray(geodesic_neighbor_distances, dtype=np.float64)
            ),
            surface_to_patch=(
                None if surface_to_patch is None else np.asarray(surface_to_patch, dtype=np.int32)
            ),
            edge_vertex_indices=(
                None
                if edge_vertex_indices is None
                else np.asarray(edge_vertex_indices, dtype=np.int32)
            ),
            cotangent_weights=(
                None
                if cotangent_weights is None
                else np.asarray(cotangent_weights, dtype=np.float64)
            ),
            effective_cotangent_weights=(
                None
                if effective_cotangent_weights is None
                else np.asarray(effective_cotangent_weights, dtype=np.float64)
            ),
            anisotropy_edge_multiplier=(
                None
                if anisotropy_edge_multiplier is None
                else np.asarray(anisotropy_edge_multiplier, dtype=np.float64)
            ),
            geometry_descriptors=dict(geometry_descriptors or {}),
            boundary_condition_mode=boundary_condition_mode,
            operator_metadata=dict(operator_metadata or {}),
            source_reference={
                "source_kind": "fixture",
                "fixture_name": str(fixture_name),
            },
        )

    @classmethod
    def from_operator_paths(
        cls,
        *,
        fine_operator_path: str | Path,
        coarse_operator_path: str | Path | None = None,
        transfer_operator_path: str | Path | None = None,
        operator_metadata_path: str | Path | None = None,
        descriptor_sidecar_path: str | Path | None = None,
        root_id: int | None = None,
        operator_metadata: Mapping[str, Any] | None = None,
        geometry_descriptors: Mapping[str, Any] | None = None,
        stability_metadata: Mapping[str, Any] | None = None,
    ) -> SurfaceWaveOperatorBundle:
        fine_path = Path(fine_operator_path).resolve()
        fine_payload = _load_npz_payload(fine_path)
        surface_operator = deserialize_sparse_matrix(fine_payload, prefix="operator")
        resolved_root_id = (
            int(root_id)
            if root_id is not None
            else int(_extract_optional_scalar(fine_payload, "root_id", default=0))
        )

        coarse_path = (
            None if coarse_operator_path is None else Path(coarse_operator_path).resolve()
        )
        coarse_payload = None if coarse_path is None else _load_npz_payload(coarse_path)
        coarse_operator = (
            None
            if coarse_payload is None or "operator_shape" not in coarse_payload
            else deserialize_sparse_matrix(coarse_payload, prefix="operator")
        )

        transfer_path = (
            None if transfer_operator_path is None else Path(transfer_operator_path).resolve()
        )
        transfer_payload = None if transfer_path is None else _load_npz_payload(transfer_path)
        resolved_operator_metadata: dict[str, Any] = (
            copy.deepcopy(dict(operator_metadata))
            if isinstance(operator_metadata, Mapping)
            else {}
        )
        metadata_path = (
            None if operator_metadata_path is None else Path(operator_metadata_path).resolve()
        )
        if metadata_path is not None and not resolved_operator_metadata:
            with metadata_path.open("r", encoding="utf-8") as handle:
                resolved_operator_metadata = json.load(handle)
        if isinstance(stability_metadata, Mapping):
            resolved_operator_metadata.setdefault(
                "_resolved_stability",
                copy.deepcopy(dict(stability_metadata)),
            )
        descriptor_sidecar = (
            None
            if descriptor_sidecar_path is None
            else Path(descriptor_sidecar_path).resolve()
        )
        resolved_geometry_descriptors: dict[str, Any] = (
            copy.deepcopy(dict(geometry_descriptors))
            if isinstance(geometry_descriptors, Mapping)
            else {}
        )
        if descriptor_sidecar is not None and not resolved_geometry_descriptors:
            with descriptor_sidecar.open("r", encoding="utf-8") as handle:
                resolved_geometry_descriptors = json.load(handle)
        boundary_condition_mode = str(
            resolved_operator_metadata.get(
                "boundary_condition_mode",
                DEFAULT_BOUNDARY_CONDITION_MODE,
            )
        )

        return cls(
            root_id=resolved_root_id,
            surface_operator=surface_operator,
            coarse_operator=coarse_operator,
            restriction=_deserialize_optional_sparse_matrix(
                transfer_payload,
                prefix="restriction",
            ),
            prolongation=_deserialize_optional_sparse_matrix(
                transfer_payload,
                prefix="prolongation",
            ),
            normalized_restriction=_deserialize_optional_sparse_matrix(
                transfer_payload,
                prefix="normalized_restriction",
            ),
            normalized_prolongation=_deserialize_optional_sparse_matrix(
                transfer_payload,
                prefix="normalized_prolongation",
            ),
            mass_diagonal=_extract_optional_vector(fine_payload, "mass_diagonal"),
            patch_mass_diagonal=(
                None
                if coarse_payload is None
                else _extract_optional_vector(coarse_payload, "mass_diagonal")
            ),
            vertices=_extract_optional_vertices(fine_payload, "vertices"),
            boundary_vertex_mask=_extract_optional_bool_vector(
                fine_payload,
                "boundary_vertex_mask",
            ),
            geodesic_neighbor_indptr=_extract_optional_int_vector(
                fine_payload,
                "geodesic_neighbor_indptr",
            ),
            geodesic_neighbor_indices=_extract_optional_int_vector(
                fine_payload,
                "geodesic_neighbor_indices",
            ),
            geodesic_neighbor_distances=_extract_optional_float_vector(
                fine_payload,
                "geodesic_neighbor_distances",
            ),
            edge_vertex_indices=_extract_optional_edge_index_array(
                fine_payload,
                "edge_vertex_indices",
            ),
            cotangent_weights=_extract_optional_float_vector(
                fine_payload,
                "cotangent_weights",
            ),
            effective_cotangent_weights=_extract_optional_float_vector(
                fine_payload,
                "effective_cotangent_weights",
            ),
            anisotropy_edge_multiplier=_extract_optional_float_vector(
                fine_payload,
                "anisotropy_edge_multiplier",
            ),
            surface_to_patch=(
                None
                if transfer_payload is None
                else _extract_optional_int_vector(transfer_payload, "surface_to_patch")
            ),
            geometry_descriptors=resolved_geometry_descriptors,
            boundary_condition_mode=boundary_condition_mode,
            operator_metadata=resolved_operator_metadata,
            source_reference={
                "source_kind": "operator_bundle",
                "fine_operator_path": str(fine_path),
                "coarse_operator_path": None if coarse_path is None else str(coarse_path),
                "transfer_operator_path": None if transfer_path is None else str(transfer_path),
                "operator_metadata_path": (
                    None if metadata_path is None else str(metadata_path)
                ),
                "descriptor_sidecar_path": (
                    None if descriptor_sidecar is None else str(descriptor_sidecar)
                ),
            },
        )

    @classmethod
    def from_operator_asset(
        cls,
        operator_asset: Mapping[str, Any],
    ) -> SurfaceWaveOperatorBundle:
        if not isinstance(operator_asset, Mapping):
            raise ValueError("operator_asset must be a mapping.")
        return cls.from_operator_paths(
            root_id=int(operator_asset.get("root_id", 0)),
            fine_operator_path=str(operator_asset["fine_operator_path"]),
            coarse_operator_path=operator_asset.get("coarse_operator_path"),
            transfer_operator_path=operator_asset.get("transfer_operator_path"),
            operator_metadata_path=operator_asset.get("operator_metadata_path"),
            descriptor_sidecar_path=operator_asset.get("descriptor_sidecar_path"),
            operator_metadata=operator_asset.get("operator_metadata"),
            geometry_descriptors=operator_asset.get("geometry_descriptors"),
            stability_metadata=operator_asset.get("stability_metadata"),
        )

    @property
    def surface_vertex_count(self) -> int:
        return int(self.surface_operator.shape[0])

    @property
    def patch_count(self) -> int | None:
        if self.coarse_operator is not None:
            return int(self.coarse_operator.shape[0])
        if self.restriction is not None:
            return int(self.restriction.shape[0])
        if self.normalized_restriction is not None:
            return int(self.normalized_restriction.shape[0])
        if self.patch_mass_diagonal is not None:
            return int(self.patch_mass_diagonal.shape[0])
        if self.surface_to_patch is not None:
            return int(np.max(self.surface_to_patch)) + 1
        return None

    @property
    def supports_patch_projection(self) -> bool:
        return self.restriction is not None and self.prolongation is not None

    @property
    def supports_normalized_patch_projection(self) -> bool:
        return (
            self.normalized_restriction is not None
            and self.normalized_prolongation is not None
        )

    @property
    def supports_anisotropy_reconstruction(self) -> bool:
        return (
            self.edge_vertex_indices is not None
            and self.cotangent_weights is not None
            and self.anisotropy_edge_multiplier is not None
            and self.mass_diagonal is not None
        )

    def select_default_seed_vertex(self) -> int:
        candidate_indices = np.flatnonzero(~self.boundary_vertex_mask)
        if candidate_indices.size == 0:
            candidate_indices = np.arange(self.surface_vertex_count, dtype=np.int32)
        if self.vertices is None:
            return int(candidate_indices[candidate_indices.size // 2])
        weights = np.asarray(self.mass_diagonal, dtype=np.float64)
        total_weight = float(np.sum(weights))
        if total_weight <= _EPSILON:
            centroid = np.mean(np.asarray(self.vertices, dtype=np.float64), axis=0)
        else:
            centroid = np.average(
                np.asarray(self.vertices, dtype=np.float64),
                axis=0,
                weights=weights,
            )
        distances = np.linalg.norm(
            np.asarray(self.vertices[candidate_indices], dtype=np.float64)
            - centroid[None, :],
            axis=1,
        )
        return int(candidate_indices[int(np.argmin(distances))])

    def build_localized_pulse(
        self,
        *,
        seed_vertex: int | None = None,
        amplitude: float = 1.0,
        support_radius_scale: float = _DEFAULT_PULSE_RADIUS_SCALE,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        resolved_seed_vertex = (
            self.select_default_seed_vertex()
            if seed_vertex is None
            else _normalize_index(
                seed_vertex,
                upper_bound=self.surface_vertex_count,
                field_name="seed_vertex",
            )
        )
        if support_radius_scale <= 0.0:
            raise ValueError("support_radius_scale must be positive.")

        used_geodesic_support = (
            self.geodesic_neighbor_indptr is not None
            and self.geodesic_neighbor_indices is not None
            and self.geodesic_neighbor_distances is not None
        )
        if used_geodesic_support:
            start = int(self.geodesic_neighbor_indptr[resolved_seed_vertex])
            end = int(self.geodesic_neighbor_indptr[resolved_seed_vertex + 1])
            support_vertex_indices = np.asarray(
                self.geodesic_neighbor_indices[start:end],
                dtype=np.int32,
            )
            support_distances = np.asarray(
                self.geodesic_neighbor_distances[start:end],
                dtype=np.float64,
            )
        else:
            support_vertex_indices = np.asarray([resolved_seed_vertex], dtype=np.int32)
            support_distances = np.asarray([0.0], dtype=np.float64)

        if support_vertex_indices.size == 0:
            support_vertex_indices = np.asarray([resolved_seed_vertex], dtype=np.int32)
            support_distances = np.asarray([0.0], dtype=np.float64)

        positive_distances = support_distances[support_distances > _EPSILON]
        support_sigma: float | None
        if positive_distances.size == 0:
            support_sigma = None
            weights = np.ones(support_vertex_indices.shape[0], dtype=np.float64)
        else:
            support_sigma = max(
                float(np.median(positive_distances)) * float(support_radius_scale),
                float(np.min(positive_distances)),
            )
            weights = np.exp(
                -0.5 * np.square(support_distances / max(support_sigma, _EPSILON))
            )

        weights = np.asarray(weights, dtype=np.float64)
        peak = float(np.max(weights))
        if peak <= _EPSILON:
            weights[:] = 0.0
            weights[0] = 1.0
        else:
            weights /= peak

        pulse = np.zeros(self.surface_vertex_count, dtype=np.float64)
        pulse[support_vertex_indices] = float(amplitude) * weights
        if self.boundary_condition_mode == CLAMPED_BOUNDARY_CONDITION_MODE:
            pulse[self.boundary_vertex_mask] = 0.0

        return pulse, {
            "mode": LOCALIZED_PULSE_INITIALIZATION,
            "seed_vertex": int(resolved_seed_vertex),
            "support_vertex_indices": [int(index) for index in support_vertex_indices.tolist()],
            "support_sigma": None if support_sigma is None else float(support_sigma),
            "used_geodesic_support": bool(used_geodesic_support),
            "amplitude": float(amplitude),
            "normalization": "peak_amplitude",
        }


@dataclass(frozen=True)
class SurfaceWaveInitializationMetadata:
    mode: str
    resolution: str
    amplitude: float
    seed_vertex: int | None = None
    support_vertex_indices: tuple[int, ...] = ()
    support_sigma: float | None = None
    used_geodesic_support: bool = False

    def __post_init__(self) -> None:
        if self.mode not in SUPPORTED_INITIALIZATION_MODES:
            raise ValueError(
                f"Unsupported initialization mode {self.mode!r}."
            )
        if self.resolution != SURFACE_STATE_RESOLUTION:
            raise ValueError(
                "Single-neuron surface-wave initialization metadata must refer to surface resolution."
            )

    def as_mapping(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "resolution": self.resolution,
            "amplitude": float(self.amplitude),
            "seed_vertex": None if self.seed_vertex is None else int(self.seed_vertex),
            "support_vertex_indices": [int(index) for index in self.support_vertex_indices],
            "support_sigma": None if self.support_sigma is None else float(self.support_sigma),
            "used_geodesic_support": bool(self.used_geodesic_support),
        }


@dataclass(frozen=True)
class SurfaceWaveRuntimeMetadata:
    solver_version: str
    root_id: int
    model_family: str
    solver_family: str
    state_layout: str
    readout_state: str
    operator_family: str
    boundary_condition_mode: str
    boundary_handling: str
    integration_timestep_ms: float
    shared_output_timestep_ms: float
    internal_substep_count: int
    cfl_safety_factor: float
    spectral_radius: float
    max_supported_integration_timestep_ms: float
    wave_speed_sq_scale: float
    restoring_strength_per_ms2: float
    gamma_per_ms: float
    recovery_mode: str
    nonlinearity_mode: str
    anisotropy_mode: str
    branching_mode: str
    recovery_summary: dict[str, Any]
    nonlinearity_summary: dict[str, Any]
    anisotropy_summary: dict[str, Any]
    branching_summary: dict[str, Any]
    surface_vertex_count: int
    patch_count: int | None
    step_order: tuple[str, ...]
    source_reference: dict[str, Any]

    def as_mapping(self) -> dict[str, Any]:
        return {
            "solver_version": self.solver_version,
            "root_id": int(self.root_id),
            "model_family": self.model_family,
            "solver_family": self.solver_family,
            "state_layout": self.state_layout,
            "readout_state": self.readout_state,
            "operator_family": self.operator_family,
            "boundary_condition_mode": self.boundary_condition_mode,
            "boundary_handling": self.boundary_handling,
            "integration_timestep_ms": float(self.integration_timestep_ms),
            "shared_output_timestep_ms": float(self.shared_output_timestep_ms),
            "internal_substep_count": int(self.internal_substep_count),
            "cfl_safety_factor": float(self.cfl_safety_factor),
            "spectral_radius": float(self.spectral_radius),
            "max_supported_integration_timestep_ms": float(
                self.max_supported_integration_timestep_ms
            ),
            "wave_speed_sq_scale": float(self.wave_speed_sq_scale),
            "restoring_strength_per_ms2": float(self.restoring_strength_per_ms2),
            "gamma_per_ms": float(self.gamma_per_ms),
            "recovery_mode": self.recovery_mode,
            "nonlinearity_mode": self.nonlinearity_mode,
            "anisotropy_mode": self.anisotropy_mode,
            "branching_mode": self.branching_mode,
            "recovery_summary": copy.deepcopy(self.recovery_summary),
            "nonlinearity_summary": copy.deepcopy(self.nonlinearity_summary),
            "anisotropy_summary": copy.deepcopy(self.anisotropy_summary),
            "branching_summary": copy.deepcopy(self.branching_summary),
            "surface_vertex_count": int(self.surface_vertex_count),
            "patch_count": None if self.patch_count is None else int(self.patch_count),
            "step_order": list(self.step_order),
            "source_reference": copy.deepcopy(self.source_reference),
        }


@dataclass(frozen=True)
class SurfaceWaveStepDiagnostics:
    step_index: int
    time_ms: float
    activation_l2: float
    velocity_l2: float
    recovery_l2: float
    patch_activation_l2: float | None
    patch_velocity_l2: float | None
    surface_operator_response_l2: float
    anisotropy_delta_l2: float
    total_drive_l2: float
    recovery_drive_l2: float
    recovery_sink_l2: float
    branching_sink_l2: float
    nonlinear_adjustment_l2: float
    energy: float
    activation_peak_abs: float
    velocity_peak_abs: float

    def as_mapping(self) -> dict[str, Any]:
        return {
            "step_index": int(self.step_index),
            "time_ms": float(self.time_ms),
            "activation_l2": float(self.activation_l2),
            "velocity_l2": float(self.velocity_l2),
            "recovery_l2": float(self.recovery_l2),
            "patch_activation_l2": (
                None if self.patch_activation_l2 is None else float(self.patch_activation_l2)
            ),
            "patch_velocity_l2": (
                None if self.patch_velocity_l2 is None else float(self.patch_velocity_l2)
            ),
            "surface_operator_response_l2": float(self.surface_operator_response_l2),
            "anisotropy_delta_l2": float(self.anisotropy_delta_l2),
            "total_drive_l2": float(self.total_drive_l2),
            "recovery_drive_l2": float(self.recovery_drive_l2),
            "recovery_sink_l2": float(self.recovery_sink_l2),
            "branching_sink_l2": float(self.branching_sink_l2),
            "nonlinear_adjustment_l2": float(self.nonlinear_adjustment_l2),
            "energy": float(self.energy),
            "activation_peak_abs": float(self.activation_peak_abs),
            "velocity_peak_abs": float(self.velocity_peak_abs),
        }


@dataclass(frozen=True)
class SurfaceWaveSnapshot:
    lifecycle_stage: str
    step_index: int
    time_ms: float
    state: SurfaceWaveState
    diagnostics: SurfaceWaveStepDiagnostics

    def as_mapping(self) -> dict[str, Any]:
        return {
            "lifecycle_stage": self.lifecycle_stage,
            "step_index": int(self.step_index),
            "time_ms": float(self.time_ms),
            "state": self.state.as_mapping(),
            "diagnostics": self.diagnostics.as_mapping(),
        }


@dataclass(frozen=True)
class SurfaceWaveRunResult:
    runtime_metadata: SurfaceWaveRuntimeMetadata
    initialization: SurfaceWaveInitializationMetadata
    initial_snapshot: SurfaceWaveSnapshot
    final_snapshot: SurfaceWaveSnapshot
    diagnostics_history: tuple[SurfaceWaveStepDiagnostics, ...]

    def as_mapping(self) -> dict[str, Any]:
        return {
            "runtime_metadata": self.runtime_metadata.as_mapping(),
            "initialization": self.initialization.as_mapping(),
            "initial_snapshot": self.initial_snapshot.as_mapping(),
            "final_snapshot": self.final_snapshot.as_mapping(),
            "diagnostics_history": [
                item.as_mapping() for item in self.diagnostics_history
            ],
        }


class SurfaceWaveSparseKernels:
    def __init__(self, operator_bundle: SurfaceWaveOperatorBundle) -> None:
        self._operator_bundle = operator_bundle

    @property
    def operator_bundle(self) -> SurfaceWaveOperatorBundle:
        return self._operator_bundle

    def apply_field(
        self,
        values: Sequence[float] | np.ndarray,
        *,
        resolution: str,
    ) -> np.ndarray:
        normalized_resolution = _normalize_resolution(resolution)
        vector = _as_float_vector(
            values,
            field_name=f"{normalized_resolution}_field",
        )
        if normalized_resolution == SURFACE_STATE_RESOLUTION:
            if vector.shape[0] != self._operator_bundle.surface_vertex_count:
                raise ValueError(
                    "surface_field must match the surface operator size."
                )
            return np.asarray(
                self._operator_bundle.surface_operator @ vector,
                dtype=np.float64,
            )
        patch_count = self._operator_bundle.patch_count
        if patch_count is None or self._operator_bundle.coarse_operator is None:
            raise ValueError(
                "Patch operator application requires a coarse operator bundle."
            )
        if vector.shape[0] != patch_count:
            raise ValueError("patch_field must match the patch operator size.")
        return np.asarray(
            self._operator_bundle.coarse_operator @ vector,
            dtype=np.float64,
        )

    def apply_operator_to_state(self, state: SurfaceWaveState) -> SurfaceWaveState:
        return SurfaceWaveState(
            resolution=state.resolution,
            activation=self.apply_field(
                state.activation,
                resolution=state.resolution,
            ),
            velocity=self.apply_field(
                state.velocity,
                resolution=state.resolution,
            ),
            recovery=(
                None
                if state.recovery is None
                else self.apply_field(
                    state.recovery,
                    resolution=state.resolution,
                )
            ),
        )

    def project_state_to_patch(
        self,
        state: SurfaceWaveState,
        *,
        normalized: bool = False,
    ) -> SurfaceWaveState:
        if state.resolution != SURFACE_STATE_RESOLUTION:
            raise ValueError("project_state_to_patch requires a surface-resolution state.")
        projector = self._select_projector(
            normalized=normalized,
            direction="surface_to_patch",
        )
        return SurfaceWaveState(
            resolution=PATCH_STATE_RESOLUTION,
            activation=np.asarray(projector @ state.activation, dtype=np.float64),
            velocity=np.asarray(projector @ state.velocity, dtype=np.float64),
            recovery=(
                None
                if state.recovery is None
                else np.asarray(projector @ state.recovery, dtype=np.float64)
            ),
        )

    def project_state_to_surface(
        self,
        state: SurfaceWaveState,
        *,
        normalized: bool = False,
    ) -> SurfaceWaveState:
        if state.resolution != PATCH_STATE_RESOLUTION:
            raise ValueError(
                "project_state_to_surface requires a patch-resolution state."
            )
        projector = self._select_projector(
            normalized=normalized,
            direction="patch_to_surface",
        )
        return SurfaceWaveState(
            resolution=SURFACE_STATE_RESOLUTION,
            activation=np.asarray(projector @ state.activation, dtype=np.float64),
            velocity=np.asarray(projector @ state.velocity, dtype=np.float64),
            recovery=(
                None
                if state.recovery is None
                else np.asarray(projector @ state.recovery, dtype=np.float64)
            ),
        )

    def project_patch_field_to_surface(
        self,
        values: Sequence[float] | np.ndarray,
        *,
        normalized: bool = False,
    ) -> np.ndarray:
        projector = self._select_projector(
            normalized=normalized,
            direction="patch_to_surface",
        )
        vector = _as_float_vector(values, field_name="patch_field")
        expected_length = int(projector.shape[1])
        if vector.shape[0] != expected_length:
            raise ValueError(
                f"patch_field must have length {expected_length}, got {vector.shape[0]}."
            )
        return np.asarray(projector @ vector, dtype=np.float64)

    def _select_projector(
        self,
        *,
        normalized: bool,
        direction: str,
    ) -> sp.csr_matrix:
        if direction == "surface_to_patch":
            projector = (
                self._operator_bundle.normalized_restriction
                if normalized
                else self._operator_bundle.restriction
            )
        else:
            projector = (
                self._operator_bundle.normalized_prolongation
                if normalized
                else self._operator_bundle.prolongation
            )
        if projector is None:
            mode = "normalized" if normalized else "physical"
            raise ValueError(
                f"{mode} {direction} projection is unavailable in this operator bundle."
            )
        return projector


class SingleNeuronSurfaceWaveSolver:
    def __init__(
        self,
        *,
        operator_bundle: SurfaceWaveOperatorBundle,
        surface_wave_model: Mapping[str, Any] | None = None,
        integration_timestep_ms: float | None = None,
        shared_output_timestep_ms: float | None = None,
    ) -> None:
        normalized_model = parse_surface_wave_model_metadata(
            surface_wave_model
            if surface_wave_model is not None
            else build_surface_wave_model_metadata(
                model_family=DEFAULT_SURFACE_WAVE_MODEL_FAMILY
            )
        )
        parameter_bundle = copy.deepcopy(normalized_model["parameter_bundle"])
        self._validate_supported_modes(parameter_bundle)

        self._operator_bundle = operator_bundle
        self._kernels = SurfaceWaveSparseKernels(operator_bundle)
        self._parameter_bundle = parameter_bundle

        solver = parameter_bundle["solver"]
        propagation = parameter_bundle["propagation"]
        damping = parameter_bundle["damping"]
        recovery = parameter_bundle["recovery"]
        nonlinearity = parameter_bundle["nonlinearity"]
        anisotropy = parameter_bundle["anisotropy"]
        branching = parameter_bundle["branching"]
        self._recovery_baseline = float(recovery["baseline"])
        self._isotropic_surface_operator = _resolve_reference_surface_operator(
            operator_bundle
        )
        (
            self._propagation_operator,
            anisotropy_summary,
        ) = _resolve_runtime_surface_operator(
            operator_bundle=operator_bundle,
            anisotropy=anisotropy,
            isotropic_surface_operator=self._isotropic_surface_operator,
        )
        (
            self._branching_damping_vector,
            branching_summary,
        ) = _resolve_branching_damping_profile(
            operator_bundle=operator_bundle,
            branching=branching,
        )
        recovery_summary = {
            "mode": str(normalized_model["recovery_mode"]),
            "active": str(normalized_model["recovery_mode"]) != RECOVERY_DISABLED_MODE,
            "time_constant_ms": float(recovery["time_constant_ms"]),
            "drive_gain": float(recovery["drive_gain"]),
            "coupling_strength_per_ms2": float(
                recovery["coupling_strength_per_ms2"]
            ),
            "baseline": float(recovery["baseline"]),
            "drive_semantics": str(recovery["drive_semantics"]),
        }
        nonlinearity_summary = {
            "mode": str(normalized_model["nonlinearity_mode"]),
            "active": (
                str(normalized_model["nonlinearity_mode"])
                != NONLINEARITY_DISABLED_MODE
            ),
            "activation_scale": float(nonlinearity["activation_scale"]),
        }
        spectral_radius = _resolve_cached_runtime_spectral_radius(
            operator_bundle=self._operator_bundle,
            propagation_operator=self._propagation_operator,
            anisotropy_summary=anisotropy_summary,
        )
        max_supported_dt_ms = compute_surface_wave_stability_timestep_ms(
            spectral_radius=spectral_radius,
            cfl_safety_factor=float(solver["cfl_safety_factor"]),
            wave_speed_sq_scale=float(propagation["wave_speed_sq_scale"]),
            restoring_strength_per_ms2=float(
                propagation["restoring_strength_per_ms2"]
            ),
            recovery_coupling_strength_per_ms2=float(
                recovery["coupling_strength_per_ms2"]
            ),
        )
        default_timestep_ms = (
            1.0 if math.isinf(max_supported_dt_ms) else float(max_supported_dt_ms)
        )

        resolved_shared_output_timestep_ms = float(
            shared_output_timestep_ms
            if shared_output_timestep_ms is not None
            else (
                integration_timestep_ms
                if integration_timestep_ms is not None
                else default_timestep_ms
            )
        )
        if resolved_shared_output_timestep_ms <= 0.0:
            raise ValueError("shared_output_timestep_ms must be positive.")

        resolved_integration_timestep_ms = float(
            integration_timestep_ms
            if integration_timestep_ms is not None
            else min(resolved_shared_output_timestep_ms, default_timestep_ms)
        )
        if resolved_integration_timestep_ms <= 0.0:
            raise ValueError("integration_timestep_ms must be positive.")
        if resolved_integration_timestep_ms > max_supported_dt_ms + _DT_TOLERANCE_MS:
            raise ValueError(
                "integration_timestep_ms exceeds the conservative spectral stability bound: "
                f"{resolved_integration_timestep_ms:.6f} > {max_supported_dt_ms:.6f}."
            )

        internal_substep_count = max(
            1,
            int(
                math.ceil(
                    resolved_shared_output_timestep_ms
                    / resolved_integration_timestep_ms
                )
            ),
        )

        self._surface_wave_model = normalized_model
        self._runtime_metadata = SurfaceWaveRuntimeMetadata(
            solver_version=SURFACE_WAVE_SOLVER_VERSION,
            root_id=int(self._operator_bundle.root_id),
            model_family=str(normalized_model["model_family"]),
            solver_family=str(normalized_model["solver_family"]),
            state_layout=str(normalized_model["state_layout"]),
            readout_state=str(normalized_model["readout_state"]),
            operator_family=str(propagation["operator_family"]),
            boundary_condition_mode=str(self._operator_bundle.boundary_condition_mode),
            boundary_handling=(
                "zero_flux_embedded_in_operator"
                if self._operator_bundle.boundary_condition_mode
                == DEFAULT_BOUNDARY_CONDITION_MODE
                else "clamped_zero_vertices_enforced_each_step"
            ),
            integration_timestep_ms=resolved_integration_timestep_ms,
            shared_output_timestep_ms=resolved_shared_output_timestep_ms,
            internal_substep_count=internal_substep_count,
            cfl_safety_factor=float(solver["cfl_safety_factor"]),
            spectral_radius=float(spectral_radius),
            max_supported_integration_timestep_ms=float(max_supported_dt_ms),
            wave_speed_sq_scale=float(propagation["wave_speed_sq_scale"]),
            restoring_strength_per_ms2=float(
                propagation["restoring_strength_per_ms2"]
            ),
            gamma_per_ms=float(damping["gamma_per_ms"]),
            recovery_mode=str(normalized_model["recovery_mode"]),
            nonlinearity_mode=str(normalized_model["nonlinearity_mode"]),
            anisotropy_mode=str(normalized_model["anisotropy_mode"]),
            branching_mode=str(normalized_model["branching_mode"]),
            recovery_summary=recovery_summary,
            nonlinearity_summary=nonlinearity_summary,
            anisotropy_summary=anisotropy_summary,
            branching_summary=branching_summary,
            surface_vertex_count=int(self._operator_bundle.surface_vertex_count),
            patch_count=self._operator_bundle.patch_count,
            step_order=SEMI_IMPLICIT_VELOCITY_SPLIT_STEP_ORDER,
            source_reference=copy.deepcopy(self._operator_bundle.source_reference),
        )

        self._state: SurfaceWaveState | None = None
        self._time_ms = 0.0
        self._step_index = 0
        self._initialization: SurfaceWaveInitializationMetadata | None = None
        self._initial_snapshot: SurfaceWaveSnapshot | None = None
        self._diagnostics_history: list[SurfaceWaveStepDiagnostics] = []
        self._final_result: SurfaceWaveRunResult | None = None

    @classmethod
    def from_operator_asset(
        cls,
        *,
        operator_asset: Mapping[str, Any],
        surface_wave_model: Mapping[str, Any] | None = None,
        integration_timestep_ms: float | None = None,
        shared_output_timestep_ms: float | None = None,
    ) -> SingleNeuronSurfaceWaveSolver:
        return cls(
            operator_bundle=SurfaceWaveOperatorBundle.from_operator_asset(operator_asset),
            surface_wave_model=surface_wave_model,
            integration_timestep_ms=integration_timestep_ms,
            shared_output_timestep_ms=shared_output_timestep_ms,
        )

    @property
    def runtime_metadata(self) -> SurfaceWaveRuntimeMetadata:
        return self._runtime_metadata

    @property
    def kernels(self) -> SurfaceWaveSparseKernels:
        return self._kernels

    @property
    def state(self) -> SurfaceWaveState:
        if self._state is None:
            raise ValueError("Surface-wave solver has not been initialized.")
        return self._state

    @property
    def is_initialized(self) -> bool:
        return self._state is not None

    @property
    def is_finalized(self) -> bool:
        return self._final_result is not None

    @property
    def step_index(self) -> int:
        return int(self._step_index)

    @property
    def current_time_ms(self) -> float:
        return float(self._time_ms)

    @property
    def _recovery_is_active(self) -> bool:
        return self._runtime_metadata.recovery_mode != RECOVERY_DISABLED_MODE

    @property
    def _nonlinearity_is_active(self) -> bool:
        return self._runtime_metadata.nonlinearity_mode != NONLINEARITY_DISABLED_MODE

    @property
    def _branching_is_active(self) -> bool:
        return self._runtime_metadata.branching_mode != BRANCHING_DISABLED_MODE

    def initialize_zero(self) -> SurfaceWaveSnapshot:
        state = SurfaceWaveState.zeros(
            resolution=SURFACE_STATE_RESOLUTION,
            size=self._operator_bundle.surface_vertex_count,
            include_recovery=self._recovery_is_active,
        )
        if state.recovery is not None:
            state.recovery[:] = self._recovery_baseline
        initialization = SurfaceWaveInitializationMetadata(
            mode=ZERO_INITIALIZATION,
            resolution=SURFACE_STATE_RESOLUTION,
            amplitude=0.0,
        )
        return self._initialize(state=state, initialization=initialization)

    def initialize_localized_pulse(
        self,
        *,
        seed_vertex: int | None = None,
        amplitude: float = 1.0,
        support_radius_scale: float = _DEFAULT_PULSE_RADIUS_SCALE,
        initial_velocity: Sequence[float] | np.ndarray | None = None,
    ) -> SurfaceWaveSnapshot:
        activation, pulse_metadata = self._operator_bundle.build_localized_pulse(
            seed_vertex=seed_vertex,
            amplitude=amplitude,
            support_radius_scale=support_radius_scale,
        )
        velocity = np.zeros_like(activation, dtype=np.float64)
        if initial_velocity is not None:
            velocity = _as_float_vector(
                initial_velocity,
                field_name="initial_velocity",
            )
            if velocity.shape[0] != activation.shape[0]:
                raise ValueError("initial_velocity must match the surface state length.")
        state = SurfaceWaveState(
            resolution=SURFACE_STATE_RESOLUTION,
            activation=activation,
            velocity=velocity,
            recovery=(
                None
                if not self._recovery_is_active
                else np.full_like(activation, self._recovery_baseline, dtype=np.float64)
            ),
        )
        initialization = SurfaceWaveInitializationMetadata(
            mode=LOCALIZED_PULSE_INITIALIZATION,
            resolution=SURFACE_STATE_RESOLUTION,
            amplitude=float(pulse_metadata["amplitude"]),
            seed_vertex=int(pulse_metadata["seed_vertex"]),
            support_vertex_indices=tuple(pulse_metadata["support_vertex_indices"]),
            support_sigma=(
                None
                if pulse_metadata["support_sigma"] is None
                else float(pulse_metadata["support_sigma"])
            ),
            used_geodesic_support=bool(pulse_metadata["used_geodesic_support"]),
        )
        return self._initialize(state=state, initialization=initialization)

    def initialize_state(
        self,
        state: SurfaceWaveState,
        *,
        initialization_mode: str = EXPLICIT_STATE_INITIALIZATION,
    ) -> SurfaceWaveSnapshot:
        if initialization_mode not in SUPPORTED_INITIALIZATION_MODES:
            raise ValueError(
                f"Unsupported initialization_mode {initialization_mode!r}."
            )
        normalized_state = state.copy()
        if self._recovery_is_active:
            if normalized_state.recovery is None:
                normalized_state.recovery = np.full(
                    normalized_state.activation.shape[0],
                    self._recovery_baseline,
                    dtype=np.float64,
                )
        elif normalized_state.recovery is not None:
            raise ValueError(
                "surface-wave initialization states may only include recovery when "
                "surface_wave.recovery.mode is enabled."
            )
        initialization = SurfaceWaveInitializationMetadata(
            mode=initialization_mode,
            resolution=SURFACE_STATE_RESOLUTION,
            amplitude=(
                float(np.max(np.abs(normalized_state.activation)))
                if normalized_state.activation.size
                else 0.0
            ),
        )
        return self._initialize(state=normalized_state, initialization=initialization)

    def step(
        self,
        *,
        surface_drive: Sequence[float] | np.ndarray | None = None,
        patch_drive: Sequence[float] | np.ndarray | None = None,
    ) -> SurfaceWaveSnapshot:
        if self._state is None:
            raise ValueError("Surface-wave solver has not been initialized.")
        if self._final_result is not None:
            raise ValueError("Surface-wave solver has already been finalized.")

        state = self._state.copy()
        self._apply_boundary_policy_to_state(state)
        total_surface_drive = self._assemble_surface_drive(
            surface_drive=surface_drive,
            patch_drive=patch_drive,
        )
        surface_operator_response = self._apply_surface_operator(state.activation)
        dt_ms = float(self._runtime_metadata.integration_timestep_ms)
        gamma_per_ms = float(self._runtime_metadata.gamma_per_ms)
        wave_speed_sq_scale = float(self._runtime_metadata.wave_speed_sq_scale)
        restoring_strength_per_ms2 = float(
            self._runtime_metadata.restoring_strength_per_ms2
        )
        recovery_sink = self._compute_recovery_sink(state)
        effective_gamma = gamma_per_ms + self._branching_damping_vector

        velocity_rhs = (
            -wave_speed_sq_scale * surface_operator_response
            -restoring_strength_per_ms2 * state.activation
            -recovery_sink
            + total_surface_drive
        )
        updated_velocity = (
            state.velocity + dt_ms * velocity_rhs
        ) / (1.0 + effective_gamma * dt_ms)
        updated_activation = state.activation + dt_ms * updated_velocity
        updated_activation, nonlinear_adjustment = self._apply_activation_nonlinearity(
            updated_activation
        )
        if self._nonlinearity_is_active:
            updated_velocity = (updated_activation - state.activation) / dt_ms
        updated_recovery = self._update_recovery_state(
            recovery=state.recovery,
            activation=updated_activation,
            dt_ms=dt_ms,
        )
        next_state = SurfaceWaveState(
            resolution=SURFACE_STATE_RESOLUTION,
            activation=updated_activation,
            velocity=updated_velocity,
            recovery=updated_recovery,
        )
        self._apply_boundary_policy_to_state(next_state)

        self._state = next_state
        self._step_index += 1
        self._time_ms += dt_ms
        diagnostics = self._build_diagnostics(
            state=next_state,
            total_surface_drive=total_surface_drive,
            nonlinear_adjustment=nonlinear_adjustment,
        )
        self._diagnostics_history.append(diagnostics)
        return SurfaceWaveSnapshot(
            lifecycle_stage=STEP_COMPLETED_STAGE,
            step_index=self._step_index,
            time_ms=self._time_ms,
            state=next_state.frozen_copy(),
            diagnostics=diagnostics,
        )

    def extract_snapshot(
        self,
        *,
        lifecycle_stage: str = "inspection",
    ) -> SurfaceWaveSnapshot:
        if self._state is None:
            raise ValueError("Surface-wave solver has not been initialized.")
        diagnostics = self._build_diagnostics(
            state=self._state,
            total_surface_drive=np.zeros(
                self._operator_bundle.surface_vertex_count,
                dtype=np.float64,
            ),
            nonlinear_adjustment=np.zeros(
                self._operator_bundle.surface_vertex_count,
                dtype=np.float64,
            ),
        )
        return SurfaceWaveSnapshot(
            lifecycle_stage=lifecycle_stage,
            step_index=self._step_index,
            time_ms=self._time_ms,
            state=self._state.frozen_copy(),
            diagnostics=diagnostics,
        )

    def current_patch_state(self) -> SurfaceWaveState:
        return self._kernels.project_state_to_patch(self.state)

    def finalize(self) -> SurfaceWaveRunResult:
        if self._final_result is not None:
            return self._final_result
        if self._state is None or self._initialization is None or self._initial_snapshot is None:
            raise ValueError("Surface-wave solver cannot finalize before initialization.")
        final_snapshot = self.extract_snapshot(lifecycle_stage=FINALIZED_STAGE)
        result = SurfaceWaveRunResult(
            runtime_metadata=self._runtime_metadata,
            initialization=self._initialization,
            initial_snapshot=self._initial_snapshot,
            final_snapshot=final_snapshot,
            diagnostics_history=tuple(self._diagnostics_history),
        )
        self._final_result = result
        return result

    def _initialize(
        self,
        *,
        state: SurfaceWaveState,
        initialization: SurfaceWaveInitializationMetadata,
    ) -> SurfaceWaveSnapshot:
        if self._state is not None:
            raise ValueError("Surface-wave solver has already been initialized.")
        if state.resolution != SURFACE_STATE_RESOLUTION:
            raise ValueError(
                "Single-neuron surface-wave solver requires a surface-resolution state."
            )
        if state.size != self._operator_bundle.surface_vertex_count:
            raise ValueError(
                "Surface-wave initialization state does not match the operator bundle size."
            )

        self._state = state.copy()
        self._apply_boundary_policy_to_state(self._state)
        self._time_ms = 0.0
        self._step_index = 0
        self._initialization = initialization

        diagnostics = self._build_diagnostics(
            state=self._state,
            total_surface_drive=np.zeros(
                self._operator_bundle.surface_vertex_count,
                dtype=np.float64,
            ),
            nonlinear_adjustment=np.zeros(
                self._operator_bundle.surface_vertex_count,
                dtype=np.float64,
            ),
        )
        self._diagnostics_history = [diagnostics]
        initial_snapshot = SurfaceWaveSnapshot(
            lifecycle_stage=INITIALIZED_STAGE,
            step_index=0,
            time_ms=0.0,
            state=self._state.frozen_copy(),
            diagnostics=diagnostics,
        )
        self._initial_snapshot = initial_snapshot
        return initial_snapshot

    def _assemble_surface_drive(
        self,
        *,
        surface_drive: Sequence[float] | np.ndarray | None,
        patch_drive: Sequence[float] | np.ndarray | None,
    ) -> np.ndarray:
        total_surface_drive = np.zeros(
            self._operator_bundle.surface_vertex_count,
            dtype=np.float64,
        )
        if surface_drive is not None:
            resolved_surface_drive = _as_float_vector(
                surface_drive,
                field_name="surface_drive",
            )
            if resolved_surface_drive.shape[0] != total_surface_drive.shape[0]:
                raise ValueError(
                    "surface_drive must match the surface operator size."
                )
            total_surface_drive += resolved_surface_drive
        if patch_drive is not None:
            total_surface_drive += self._kernels.project_patch_field_to_surface(
                patch_drive,
                normalized=False,
            )
        self._apply_boundary_policy_to_vector(total_surface_drive)
        return total_surface_drive

    def _apply_surface_operator(self, activation: np.ndarray) -> np.ndarray:
        return np.asarray(self._propagation_operator @ activation, dtype=np.float64)

    def _compute_recovery_drive(self, activation: np.ndarray) -> np.ndarray:
        if not self._recovery_is_active:
            return np.zeros_like(activation, dtype=np.float64)
        drive_gain = float(self._runtime_metadata.recovery_summary["drive_gain"])
        return drive_gain * np.maximum(np.asarray(activation, dtype=np.float64), 0.0)

    def _compute_recovery_sink(self, state: SurfaceWaveState) -> np.ndarray:
        if not self._recovery_is_active or state.recovery is None:
            return np.zeros_like(state.activation, dtype=np.float64)
        coupling_strength = float(
            self._runtime_metadata.recovery_summary["coupling_strength_per_ms2"]
        )
        return coupling_strength * np.asarray(state.recovery, dtype=np.float64)

    def _apply_activation_nonlinearity(
        self,
        activation: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        if not self._nonlinearity_is_active:
            zeros = np.zeros_like(activation, dtype=np.float64)
            return np.asarray(activation, dtype=np.float64), zeros
        activation_scale = float(
            self._runtime_metadata.nonlinearity_summary["activation_scale"]
        )
        clipped = activation_scale * np.tanh(
            np.asarray(activation, dtype=np.float64) / max(activation_scale, _EPSILON)
        )
        return clipped, np.asarray(activation, dtype=np.float64) - clipped

    def _update_recovery_state(
        self,
        *,
        recovery: np.ndarray | None,
        activation: np.ndarray,
        dt_ms: float,
    ) -> np.ndarray | None:
        if not self._recovery_is_active:
            return None
        current_recovery = (
            np.full_like(activation, self._recovery_baseline, dtype=np.float64)
            if recovery is None
            else np.asarray(recovery, dtype=np.float64)
        )
        target = self._recovery_baseline + self._compute_recovery_drive(activation)
        time_constant_ms = float(self._runtime_metadata.recovery_summary["time_constant_ms"])
        decay = math.exp(-float(dt_ms) / max(time_constant_ms, _EPSILON))
        updated = target + (current_recovery - target) * decay
        return np.asarray(updated, dtype=np.float64)

    def _apply_boundary_policy_to_vector(self, values: np.ndarray) -> None:
        if self._operator_bundle.boundary_condition_mode == CLAMPED_BOUNDARY_CONDITION_MODE:
            values[self._operator_bundle.boundary_vertex_mask] = 0.0

    def _apply_boundary_policy_to_state(self, state: SurfaceWaveState) -> None:
        self._apply_boundary_policy_to_vector(state.activation)
        self._apply_boundary_policy_to_vector(state.velocity)
        if state.recovery is not None:
            if (
                self._operator_bundle.boundary_condition_mode
                == CLAMPED_BOUNDARY_CONDITION_MODE
            ):
                state.recovery[self._operator_bundle.boundary_vertex_mask] = (
                    self._recovery_baseline
                )

    def _build_diagnostics(
        self,
        *,
        state: SurfaceWaveState,
        total_surface_drive: np.ndarray,
        nonlinear_adjustment: np.ndarray,
    ) -> SurfaceWaveStepDiagnostics:
        surface_operator_response = self._apply_surface_operator(state.activation)
        isotropic_surface_operator_response = np.asarray(
            self._isotropic_surface_operator @ state.activation,
            dtype=np.float64,
        )
        patch_state: SurfaceWaveState | None = None
        if self._operator_bundle.supports_patch_projection:
            patch_state = self._kernels.project_state_to_patch(state)
        recovery_sink = self._compute_recovery_sink(state)
        recovery_drive = self._compute_recovery_drive(state.activation)
        branching_sink = self._branching_damping_vector * state.velocity

        energy = 0.5 * (
            float(np.dot(state.velocity, state.velocity))
            + float(self._runtime_metadata.wave_speed_sq_scale)
            * float(np.dot(state.activation, surface_operator_response))
            + float(self._runtime_metadata.restoring_strength_per_ms2)
            * float(np.dot(state.activation, state.activation))
            + float(
                self._runtime_metadata.recovery_summary["coupling_strength_per_ms2"]
            )
            * float(
                np.dot(
                    np.zeros_like(state.activation)
                    if state.recovery is None
                    else state.recovery,
                    np.zeros_like(state.activation)
                    if state.recovery is None
                    else state.recovery,
                )
            )
        )
        return SurfaceWaveStepDiagnostics(
            step_index=int(self._step_index),
            time_ms=float(self._time_ms),
            activation_l2=float(np.linalg.norm(state.activation)),
            velocity_l2=float(np.linalg.norm(state.velocity)),
            recovery_l2=(
                0.0
                if state.recovery is None
                else float(np.linalg.norm(state.recovery))
            ),
            patch_activation_l2=(
                None
                if patch_state is None
                else float(np.linalg.norm(patch_state.activation))
            ),
            patch_velocity_l2=(
                None
                if patch_state is None
                else float(np.linalg.norm(patch_state.velocity))
            ),
            surface_operator_response_l2=float(
                np.linalg.norm(surface_operator_response)
            ),
            anisotropy_delta_l2=float(
                np.linalg.norm(
                    surface_operator_response - isotropic_surface_operator_response
                )
            ),
            total_drive_l2=float(np.linalg.norm(total_surface_drive)),
            recovery_drive_l2=float(np.linalg.norm(recovery_drive)),
            recovery_sink_l2=float(np.linalg.norm(recovery_sink)),
            branching_sink_l2=float(np.linalg.norm(branching_sink)),
            nonlinear_adjustment_l2=float(np.linalg.norm(nonlinear_adjustment)),
            energy=float(energy),
            activation_peak_abs=float(np.max(np.abs(state.activation))),
            velocity_peak_abs=float(np.max(np.abs(state.velocity))),
        )

    def _validate_supported_modes(self, parameter_bundle: Mapping[str, Any]) -> None:
        if str(parameter_bundle["solver"]["family"]) != SEMI_IMPLICIT_VELOCITY_SPLIT_SOLVER_FAMILY:
            raise ValueError(
                "surface-wave solver only supports solver.family == "
                f"{SEMI_IMPLICIT_VELOCITY_SPLIT_SOLVER_FAMILY!r}."
            )
        if str(parameter_bundle["damping"]["mode"]) != LINEAR_VELOCITY_DAMPING_MODE:
            raise ValueError(
                "surface-wave solver only supports damping.mode == "
                f"{LINEAR_VELOCITY_DAMPING_MODE!r}."
            )
        if str(parameter_bundle["recovery"]["mode"]) not in (
            RECOVERY_DISABLED_MODE,
            ACTIVITY_DRIVEN_FIRST_ORDER_RECOVERY_MODE,
        ):
            raise ValueError(
                "surface-wave solver only supports recovery.mode in "
                f"{[RECOVERY_DISABLED_MODE, ACTIVITY_DRIVEN_FIRST_ORDER_RECOVERY_MODE]!r}."
            )
        if str(parameter_bundle["recovery"]["drive_semantics"]) != POSITIVE_SURFACE_ACTIVATION_RECOVERY_DRIVE:
            raise ValueError(
                "surface_wave.recovery.drive_semantics must remain "
                f"{POSITIVE_SURFACE_ACTIVATION_RECOVERY_DRIVE!r}."
            )
        if str(parameter_bundle["nonlinearity"]["mode"]) not in (
            NONLINEARITY_DISABLED_MODE,
            TANH_SOFT_CLIP_NONLINEARITY_MODE,
        ):
            raise ValueError(
                "surface-wave solver only supports nonlinearity.mode in "
                f"{[NONLINEARITY_DISABLED_MODE, TANH_SOFT_CLIP_NONLINEARITY_MODE]!r}."
            )
        if str(parameter_bundle["anisotropy"]["mode"]) not in (
            ISOTROPIC_ANISOTROPY_MODE,
            OPERATOR_EMBEDDED_ANISOTROPY_MODE,
        ):
            raise ValueError(
                "surface-wave solver only supports anisotropy.mode in "
                f"{[ISOTROPIC_ANISOTROPY_MODE, OPERATOR_EMBEDDED_ANISOTROPY_MODE]!r}."
            )
        if str(parameter_bundle["branching"]["mode"]) not in (
            BRANCHING_DISABLED_MODE,
            DESCRIPTOR_SCALED_DAMPING_BRANCHING_MODE,
        ):
            raise ValueError(
                "surface-wave solver only supports branching.mode in "
                f"{[BRANCHING_DISABLED_MODE, DESCRIPTOR_SCALED_DAMPING_BRANCHING_MODE]!r}."
            )
        if (
            str(parameter_bundle["branching"]["mode"])
            == DESCRIPTOR_SCALED_DAMPING_BRANCHING_MODE
            and str(parameter_bundle["branching"]["junction_response"])
            != EXTRA_LOCAL_DAMPING_BRANCHING_RESPONSE
        ):
            raise ValueError(
                "surface_wave.branching.junction_response must remain "
                f"{EXTRA_LOCAL_DAMPING_BRANCHING_RESPONSE!r}."
            )
        if (
            str(parameter_bundle["synaptic_source"]["readout_state"])
            != SURFACE_ACTIVATION_STATE_ID
        ):
            raise ValueError(
                "surface_wave.synaptic_source.readout_state must remain surface_activation."
            )
        if (
            str(parameter_bundle["synaptic_source"]["injection_target_state"])
            != SURFACE_VELOCITY_STATE_ID
        ):
            raise ValueError(
                "surface_wave.synaptic_source.injection_target_state must remain surface_velocity."
            )


def build_single_neuron_surface_wave_solver_from_execution_plan(
    *,
    surface_wave_model: Mapping[str, Any],
    surface_wave_execution_plan: Mapping[str, Any],
    root_id: int,
) -> SingleNeuronSurfaceWaveSolver:
    if not isinstance(surface_wave_execution_plan, Mapping):
        raise ValueError("surface_wave_execution_plan must be a mapping.")
    selected_root_operator_assets = surface_wave_execution_plan.get(
        "selected_root_operator_assets"
    )
    if not isinstance(selected_root_operator_assets, Sequence) or isinstance(
        selected_root_operator_assets,
        (str, bytes),
    ):
        raise ValueError(
            "surface_wave_execution_plan.selected_root_operator_assets must be a sequence."
        )
    matching_assets = [
        item
        for item in selected_root_operator_assets
        if isinstance(item, Mapping) and int(item.get("root_id")) == int(root_id)
    ]
    if len(matching_assets) != 1:
        raise ValueError(
            f"Expected exactly one operator asset for root_id {root_id}, found {len(matching_assets)}."
        )
    solver_mapping = surface_wave_execution_plan.get("solver")
    if not isinstance(solver_mapping, Mapping):
        raise ValueError("surface_wave_execution_plan.solver must be a mapping.")
    return SingleNeuronSurfaceWaveSolver.from_operator_asset(
        operator_asset=matching_assets[0],
        surface_wave_model=surface_wave_model,
        integration_timestep_ms=float(solver_mapping["integration_timestep_ms"]),
        shared_output_timestep_ms=float(solver_mapping["shared_output_timestep_ms"]),
    )


def estimate_sparse_operator_spectral_radius(operator: sp.spmatrix) -> float:
    normalized_operator = _as_sorted_csr(operator, field_name="operator").astype(np.float64)
    if normalized_operator.shape[0] != normalized_operator.shape[1]:
        raise ValueError("operator must be square to estimate a spectral radius.")
    if normalized_operator.shape[0] < 1:
        raise ValueError("operator must be non-empty to estimate a spectral radius.")
    if normalized_operator.shape[0] <= 4:
        eigenvalues = np.linalg.eigvalsh(normalized_operator.toarray())
        spectral_radius = float(np.max(eigenvalues))
    else:
        spectral_radius = float(
            spla.eigsh(
                normalized_operator,
                k=1,
                which="LA",
                return_eigenvectors=False,
            )[0]
        )
    if not math.isfinite(spectral_radius):
        raise ValueError("Spectral radius estimate was not finite.")
    return round(max(0.0, spectral_radius), 12)


def _resolve_cached_runtime_spectral_radius(
    *,
    operator_bundle: SurfaceWaveOperatorBundle,
    propagation_operator: sp.spmatrix,
    anisotropy_summary: Mapping[str, Any],
) -> float:
    cache = operator_bundle.operator_metadata.setdefault(
        "_runtime_stability_cache",
        {},
    )
    if not isinstance(cache, dict):
        cache = {}
        operator_bundle.operator_metadata["_runtime_stability_cache"] = cache

    cache_key = json.dumps(
        {
            "mode": str(anisotropy_summary.get("mode", "")),
            "identity_equivalent": bool(
                anisotropy_summary.get("identity_equivalent", False)
            ),
            "strength_scale": round(
                float(anisotropy_summary.get("strength_scale", 0.0)),
                12,
            ),
            "source_anisotropy_model": str(
                anisotropy_summary.get("source_anisotropy_model", "")
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    cached_entry = cache.get(cache_key)
    if isinstance(cached_entry, Mapping) and "spectral_radius" in cached_entry:
        return float(cached_entry["spectral_radius"])

    planner_entry = operator_bundle.operator_metadata.get("_resolved_stability")
    if (
        bool(anisotropy_summary.get("identity_equivalent", False))
        and isinstance(planner_entry, Mapping)
        and "spectral_radius" in planner_entry
    ):
        spectral_radius = float(planner_entry["spectral_radius"])
    else:
        spectral_radius = estimate_sparse_operator_spectral_radius(propagation_operator)

    cache[cache_key] = {
        "spectral_radius": float(spectral_radius),
    }
    return float(spectral_radius)


def compute_surface_wave_stability_timestep_ms(
    *,
    spectral_radius: float,
    cfl_safety_factor: float,
    wave_speed_sq_scale: float,
    restoring_strength_per_ms2: float,
    recovery_coupling_strength_per_ms2: float = 0.0,
) -> float:
    normalized_spectral_radius = float(spectral_radius)
    if normalized_spectral_radius < 0.0:
        raise ValueError("spectral_radius must be non-negative.")
    angular_frequency_sq_bound = (
        float(wave_speed_sq_scale) * normalized_spectral_radius
        + float(restoring_strength_per_ms2)
        + float(recovery_coupling_strength_per_ms2)
    )
    if angular_frequency_sq_bound <= 0.0:
        return math.inf
    return float((2.0 * float(cfl_safety_factor)) / math.sqrt(angular_frequency_sq_bound))


def _resolve_reference_surface_operator(
    operator_bundle: SurfaceWaveOperatorBundle,
) -> sp.csr_matrix:
    if (
        operator_bundle.edge_vertex_indices is None
        or operator_bundle.cotangent_weights is None
    ):
        return operator_bundle.surface_operator
    return _build_surface_operator_from_edge_weights(
        surface_vertex_count=operator_bundle.surface_vertex_count,
        edge_vertex_indices=operator_bundle.edge_vertex_indices,
        edge_weights=operator_bundle.cotangent_weights,
        mass_diagonal=np.asarray(operator_bundle.mass_diagonal, dtype=np.float64),
        boundary_condition_mode=operator_bundle.boundary_condition_mode,
        boundary_vertex_mask=np.asarray(
            operator_bundle.boundary_vertex_mask,
            dtype=bool,
        ),
    )


def _resolve_runtime_surface_operator(
    *,
    operator_bundle: SurfaceWaveOperatorBundle,
    anisotropy: Mapping[str, Any],
    isotropic_surface_operator: sp.csr_matrix,
) -> tuple[sp.csr_matrix, dict[str, Any]]:
    mode = str(anisotropy["mode"])
    summary = {
        "mode": mode,
        "active": mode == OPERATOR_EMBEDDED_ANISOTROPY_MODE,
        "operator_source": str(anisotropy["operator_source"]),
        "strength_scale": float(anisotropy["strength_scale"]),
        "source_anisotropy_model": str(
            operator_bundle.operator_metadata.get("anisotropy_model", "unknown")
        ),
    }
    if mode == ISOTROPIC_ANISOTROPY_MODE:
        summary.update(
            {
                "identity_equivalent": True,
                "edge_multiplier_min": 1.0,
                "edge_multiplier_mean": 1.0,
                "edge_multiplier_max": 1.0,
                "operator_delta_inf": 0.0,
            }
        )
        return isotropic_surface_operator, summary

    if not operator_bundle.supports_anisotropy_reconstruction:
        raise ValueError(
            "surface_wave anisotropy.mode 'operator_embedded' requires serialized "
            "edge weights plus anisotropy multipliers in the operator bundle."
        )

    embedded_multiplier = np.asarray(
        operator_bundle.anisotropy_edge_multiplier,
        dtype=np.float64,
    )
    strength_scale = float(anisotropy["strength_scale"])
    effective_multiplier = 1.0 + strength_scale * (embedded_multiplier - 1.0)
    runtime_operator = _build_surface_operator_from_edge_weights(
        surface_vertex_count=operator_bundle.surface_vertex_count,
        edge_vertex_indices=np.asarray(operator_bundle.edge_vertex_indices, dtype=np.int64),
        edge_weights=np.asarray(operator_bundle.cotangent_weights, dtype=np.float64)
        * effective_multiplier,
        mass_diagonal=np.asarray(operator_bundle.mass_diagonal, dtype=np.float64),
        boundary_condition_mode=operator_bundle.boundary_condition_mode,
        boundary_vertex_mask=np.asarray(
            operator_bundle.boundary_vertex_mask,
            dtype=bool,
        ),
    )
    operator_delta = (runtime_operator - isotropic_surface_operator).tocsr()
    delta_inf = 0.0 if operator_delta.nnz == 0 else float(np.max(np.abs(operator_delta.data)))
    summary.update(
        {
            "identity_equivalent": bool(
                np.allclose(effective_multiplier, 1.0, atol=1.0e-12)
            ),
            "edge_multiplier_min": float(np.min(effective_multiplier)),
            "edge_multiplier_mean": float(np.mean(effective_multiplier)),
            "edge_multiplier_max": float(np.max(effective_multiplier)),
            "embedded_edge_multiplier_min": float(np.min(embedded_multiplier)),
            "embedded_edge_multiplier_mean": float(np.mean(embedded_multiplier)),
            "embedded_edge_multiplier_max": float(np.max(embedded_multiplier)),
            "operator_delta_inf": delta_inf,
        }
    )
    return runtime_operator, summary


def _resolve_branching_damping_profile(
    *,
    operator_bundle: SurfaceWaveOperatorBundle,
    branching: Mapping[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    mode = str(branching["mode"])
    zero_profile = np.zeros(operator_bundle.surface_vertex_count, dtype=np.float64)
    summary = {
        "mode": mode,
        "active": mode == DESCRIPTOR_SCALED_DAMPING_BRANCHING_MODE,
        "descriptor_source": str(branching["descriptor_source"]),
        "gain": float(branching["gain"]),
        "junction_response": str(branching["junction_response"]),
    }
    if mode == BRANCHING_DISABLED_MODE:
        summary.update(
            {
                "branch_point_count": 0,
                "leaf_count": 0,
                "root_count": 0,
                "total_cable_length": 0.0,
                "branch_complexity": 0.0,
                "local_damping_min": 0.0,
                "local_damping_mean": 0.0,
                "local_damping_max": 0.0,
            }
        )
        return zero_profile, summary

    descriptors = operator_bundle.geometry_descriptors
    if not descriptors:
        raise ValueError(
            "surface_wave branching.mode 'descriptor_scaled_damping' requires "
            "loaded geometry descriptors."
        )
    representations = descriptors.get("representations")
    if not isinstance(representations, Mapping):
        raise ValueError("Geometry descriptors are missing the 'representations' block.")
    skeleton = representations.get("skeleton")
    if not isinstance(skeleton, Mapping) or not bool(skeleton.get("available", False)):
        raise ValueError(
            "surface_wave branching.mode 'descriptor_scaled_damping' requires "
            "an available skeleton summary in the geometry descriptors."
        )

    branch_point_count = int(skeleton.get("branch_point_count", 0))
    leaf_count = int(skeleton.get("leaf_count", 0))
    root_count = int(skeleton.get("root_count", 0))
    total_cable_length = float(skeleton.get("total_cable_length", 0.0))
    if branch_point_count <= 0:
        raise ValueError(
            "surface_wave branching.mode 'descriptor_scaled_damping' requires "
            "geometry descriptors with branch_point_count > 0."
        )
    branch_complexity = branch_point_count / max(
        float(branch_point_count + leaf_count + max(root_count, 1)),
        1.0,
    )
    local_profile = np.ones(operator_bundle.surface_vertex_count, dtype=np.float64)
    if operator_bundle.surface_to_patch is not None:
        patch_sizes = np.bincount(
            np.asarray(operator_bundle.surface_to_patch, dtype=np.int64),
            minlength=max(int(operator_bundle.patch_count or 0), 1),
        ).astype(np.float64)
        local_profile = patch_sizes[np.asarray(operator_bundle.surface_to_patch, dtype=np.int64)]
        local_profile /= max(float(np.max(local_profile)), 1.0)
    realized_profile = (
        float(branching["gain"]) * branch_complexity * np.asarray(local_profile, dtype=np.float64)
    )
    summary.update(
        {
            "branch_point_count": branch_point_count,
            "leaf_count": leaf_count,
            "root_count": root_count,
            "total_cable_length": total_cable_length,
            "branch_complexity": float(branch_complexity),
            "local_damping_min": float(np.min(realized_profile)),
            "local_damping_mean": float(np.mean(realized_profile)),
            "local_damping_max": float(np.max(realized_profile)),
        }
    )
    return realized_profile, summary


def _build_surface_operator_from_edge_weights(
    *,
    surface_vertex_count: int,
    edge_vertex_indices: np.ndarray,
    edge_weights: np.ndarray,
    mass_diagonal: np.ndarray,
    boundary_condition_mode: str,
    boundary_vertex_mask: np.ndarray,
) -> sp.csr_matrix:
    stiffness = _assemble_edge_stiffness_matrix(
        vertex_count=surface_vertex_count,
        edge_vertex_indices=edge_vertex_indices,
        edge_weights=edge_weights,
    )
    if boundary_condition_mode == CLAMPED_BOUNDARY_CONDITION_MODE:
        stiffness = _apply_clamped_boundary_to_stiffness(
            stiffness=stiffness,
            mass_diagonal=mass_diagonal,
            boundary_vertex_mask=boundary_vertex_mask,
        )
    inv_sqrt_mass = 1.0 / np.sqrt(np.asarray(mass_diagonal, dtype=np.float64))
    scaling = sp.diags(inv_sqrt_mass.astype(np.float64, copy=False))
    operator = (scaling @ stiffness @ scaling).tocsr()
    operator.eliminate_zeros()
    operator.sort_indices()
    return operator


def _assemble_edge_stiffness_matrix(
    *,
    vertex_count: int,
    edge_vertex_indices: np.ndarray,
    edge_weights: np.ndarray,
) -> sp.csr_matrix:
    diagonal = np.zeros(vertex_count, dtype=np.float64)
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    for (i, j), weight in zip(
        np.asarray(edge_vertex_indices, dtype=np.int64),
        np.asarray(edge_weights, dtype=np.float64),
    ):
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
            (
                np.asarray(rows, dtype=np.int32),
                np.asarray(cols, dtype=np.int32),
            ),
        ),
        shape=(vertex_count, vertex_count),
        dtype=np.float64,
    )
    stiffness.sum_duplicates()
    stiffness.eliminate_zeros()
    stiffness.sort_indices()
    return stiffness


def _apply_clamped_boundary_to_stiffness(
    *,
    stiffness: sp.csr_matrix,
    mass_diagonal: np.ndarray,
    boundary_vertex_mask: np.ndarray,
) -> sp.csr_matrix:
    boundary_indices = np.flatnonzero(np.asarray(boundary_vertex_mask, dtype=bool))
    if boundary_indices.size == 0:
        return stiffness
    adjusted = stiffness.tolil(copy=True)
    adjusted[boundary_indices, :] = 0.0
    adjusted[:, boundary_indices] = 0.0
    adjusted[boundary_indices, boundary_indices] = np.asarray(
        mass_diagonal[boundary_indices],
        dtype=np.float64,
    )
    adjusted = adjusted.tocsr()
    adjusted.eliminate_zeros()
    adjusted.sort_indices()
    return adjusted


def _normalize_resolution(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in SUPPORTED_SURFACE_WAVE_STATE_RESOLUTIONS:
        raise ValueError(
            f"Unsupported state resolution {value!r}. Supported resolutions: {list(SUPPORTED_SURFACE_WAVE_STATE_RESOLUTIONS)!r}."
        )
    return normalized


def _normalize_positive_size(value: int, *, field_name: str) -> int:
    normalized = int(value)
    if normalized < 1:
        raise ValueError(f"{field_name} must be positive, got {value!r}.")
    return normalized


def _normalize_index(value: int, *, upper_bound: int, field_name: str) -> int:
    normalized = int(value)
    if normalized < 0 or normalized >= int(upper_bound):
        raise ValueError(
            f"{field_name} must satisfy 0 <= value < {upper_bound}, got {value!r}."
        )
    return normalized


def _as_float_vector(value: Sequence[float] | np.ndarray, *, field_name: str) -> np.ndarray:
    vector = np.asarray(value, dtype=np.float64)
    if vector.ndim != 1:
        raise ValueError(f"{field_name} must be a 1D float vector.")
    return np.asarray(vector, dtype=np.float64).copy()


def _as_sorted_csr(matrix: sp.spmatrix, *, field_name: str) -> sp.csr_matrix:
    if not sp.issparse(matrix):
        raise ValueError(f"{field_name} must be a scipy sparse matrix.")
    csr = matrix.tocsr().astype(np.float64)
    csr.eliminate_zeros()
    csr.sort_indices()
    return csr


def _normalize_optional_csr(
    matrix: sp.spmatrix | None,
    *,
    field_name: str,
) -> sp.csr_matrix | None:
    if matrix is None:
        return None
    return _as_sorted_csr(matrix, field_name=field_name)


def _normalize_optional_float_vector(
    value: Sequence[float] | np.ndarray | None,
    *,
    field_name: str,
) -> np.ndarray | None:
    if value is None:
        return None
    return _as_float_vector(value, field_name=field_name)


def _normalize_optional_int_vector(
    value: Sequence[int] | np.ndarray | None,
    *,
    field_name: str,
) -> np.ndarray | None:
    if value is None:
        return None
    vector = np.asarray(value, dtype=np.int64)
    if vector.ndim != 1:
        raise ValueError(f"{field_name} must be a 1D integer vector.")
    return np.asarray(vector, dtype=np.int64).copy()


def _normalize_optional_edge_index_array(
    value: np.ndarray | None,
    *,
    field_name: str,
) -> np.ndarray | None:
    if value is None:
        return None
    array = np.asarray(value, dtype=np.int64)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError(f"{field_name} must have shape (n_edges, 2).")
    return np.asarray(array, dtype=np.int64).copy()


def _load_npz_payload(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as payload:
        return {
            key: np.asarray(payload[key])
            for key in payload.files
        }


def _deserialize_optional_sparse_matrix(
    payload: Mapping[str, np.ndarray] | None,
    *,
    prefix: str,
) -> sp.csr_matrix | None:
    if payload is None or f"{prefix}_shape" not in payload:
        return None
    return deserialize_sparse_matrix(payload, prefix=prefix)


def _extract_optional_scalar(
    payload: Mapping[str, np.ndarray],
    key: str,
    *,
    default: int,
) -> int:
    if key not in payload:
        return int(default)
    value = np.asarray(payload[key])
    if value.size == 0:
        return int(default)
    return int(np.asarray(value).reshape(-1)[0])


def _extract_optional_vector(
    payload: Mapping[str, np.ndarray],
    key: str,
) -> np.ndarray | None:
    if key not in payload:
        return None
    return np.asarray(payload[key], dtype=np.float64).reshape(-1)


def _extract_optional_vertices(
    payload: Mapping[str, np.ndarray],
    key: str,
) -> np.ndarray | None:
    if key not in payload:
        return None
    return np.asarray(payload[key], dtype=np.float64)


def _extract_optional_bool_vector(
    payload: Mapping[str, np.ndarray],
    key: str,
) -> np.ndarray | None:
    if key not in payload:
        return None
    return np.asarray(payload[key], dtype=bool).reshape(-1)


def _extract_optional_int_vector(
    payload: Mapping[str, np.ndarray],
    key: str,
) -> np.ndarray | None:
    if key not in payload:
        return None
    return np.asarray(payload[key], dtype=np.int64).reshape(-1)


def _extract_optional_edge_index_array(
    payload: Mapping[str, np.ndarray],
    key: str,
) -> np.ndarray | None:
    if key not in payload:
        return None
    array = np.asarray(payload[key], dtype=np.int64)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError(f"{key} must have shape (n_edges, 2).")
    return np.asarray(array, dtype=np.int64)


def _extract_optional_float_vector(
    payload: Mapping[str, np.ndarray],
    key: str,
) -> np.ndarray | None:
    if key not in payload:
        return None
    return np.asarray(payload[key], dtype=np.float64).reshape(-1)


__all__ = [
    "EXPLICIT_STATE_INITIALIZATION",
    "FINALIZED_STAGE",
    "INITIALIZED_STAGE",
    "LOCALIZED_PULSE_INITIALIZATION",
    "PATCH_STATE_RESOLUTION",
    "STEP_COMPLETED_STAGE",
    "SURFACE_STATE_RESOLUTION",
    "SURFACE_WAVE_SOLVER_VERSION",
    "SingleNeuronSurfaceWaveSolver",
    "SurfaceWaveInitializationMetadata",
    "SurfaceWaveOperatorBundle",
    "SurfaceWaveRunResult",
    "SurfaceWaveRuntimeMetadata",
    "SurfaceWaveSnapshot",
    "SurfaceWaveSparseKernels",
    "SurfaceWaveState",
    "SurfaceWaveStepDiagnostics",
    "ZERO_INITIALIZATION",
    "build_single_neuron_surface_wave_solver_from_execution_plan",
    "compute_surface_wave_stability_timestep_ms",
    "estimate_sparse_operator_spectral_radius",
]
