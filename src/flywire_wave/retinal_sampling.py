from __future__ import annotations

import copy
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from .retinal_contract import (
    default_signal_convention,
    normalize_retinal_sampling_kernel,
)
from .retinal_geometry import (
    ResolvedRetinalGeometry,
    build_body_to_head_transform,
    build_eye_to_head_transform,
    build_world_to_body_transform,
    compose_rigid_transforms,
    resolve_retinal_geometry_spec,
)
from .stimulus_contract import (
    _normalize_nonempty_string,
    _normalize_parameter_hash,
    _normalize_positive_float,
)
from .stimulus_generators import StimulusRenderResult, sample_stimulus_field
from .stimulus_registry import (
    ResolvedStimulusSpec,
    has_stimulus_reference,
    resolve_stimulus_spec,
)


RETINAL_PROJECTOR_VERSION = "retinal_projector.v1"
ANALYTIC_VISUAL_FIELD_CONTRACT_VERSION = "analytic_visual_field.v1"

GAUSSIAN_ACCEPTANCE_ANGLE_SEMANTICS = "acceptance_angle_deg_is_gaussian_sigma"
SUPPORT_RADIUS_SEMANTICS = "support_radius_deg_is_hard_truncation_radius"
SUPPORT_GRID_FAMILY = "eye_local_hexagonal_support_grid"
WORLD_DIRECTION_TO_VISUAL_FIELD_CONVENTION = (
    "world_cartesian_to_visual_field_angles_deg_with_positive_azimuth_right_and_positive_elevation_up"
)
FIELD_OF_VIEW_CLIPPING_RULE = "inclusive_rectangular_bounds_with_background_fill_for_out_of_field_support"
PER_EYE_HANDLING_RULE = "shared_eye_local_support_grid_with_eye_specific_world_rotation"
OUT_OF_FIELD_BLEND_RULE = "background_fill_applied_to_out_of_field_support_samples_before_weighted_sum"
FLOAT_ABS_TOL = 1.0e-12
_SQRT3_OVER_2 = math.sqrt(3.0) * 0.5


@dataclass(frozen=True)
class AnalyticVisualFieldSource:
    source_family: str
    source_name: str
    field_sampler: Callable[[float, Any, Any], Any]
    width_deg: float
    height_deg: float
    source_kind: str = "fixture_scene"
    source_contract_version: str = ANALYTIC_VISUAL_FIELD_CONTRACT_VERSION
    source_id: str | None = None
    source_hash: str | None = None
    source_metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not callable(self.field_sampler):
            raise ValueError("field_sampler must be callable.")
        object.__setattr__(
            self,
            "source_family",
            _normalize_nonempty_string(self.source_family, field_name="source_family"),
        )
        object.__setattr__(
            self,
            "source_name",
            _normalize_nonempty_string(self.source_name, field_name="source_name"),
        )
        object.__setattr__(
            self,
            "source_kind",
            _normalize_nonempty_string(self.source_kind, field_name="source_kind"),
        )
        object.__setattr__(
            self,
            "source_contract_version",
            _normalize_nonempty_string(
                self.source_contract_version,
                field_name="source_contract_version",
            ),
        )
        object.__setattr__(
            self,
            "width_deg",
            _normalize_positive_float(self.width_deg, field_name="width_deg"),
        )
        object.__setattr__(
            self,
            "height_deg",
            _normalize_positive_float(self.height_deg, field_name="height_deg"),
        )
        if self.source_id is not None:
            object.__setattr__(
                self,
                "source_id",
                _normalize_nonempty_string(
                    self.source_id,
                    field_name="source_id",
                ),
            )
        if self.source_hash is not None:
            object.__setattr__(
                self,
                "source_hash",
                _normalize_parameter_hash(self.source_hash),
            )
        metadata = (
            _normalize_json_mapping_like(
                self.source_metadata,
                field_name="source_metadata",
            )
            if self.source_metadata is not None
            else {}
        )
        object.__setattr__(self, "source_metadata", metadata)

    def sample_field(
        self,
        *,
        time_ms: float,
        azimuth_deg: Any,
        elevation_deg: Any,
    ) -> np.ndarray | float:
        azimuth_array, elevation_array = np.broadcast_arrays(
            np.asarray(azimuth_deg, dtype=np.float64),
            np.asarray(elevation_deg, dtype=np.float64),
        )
        sampled = np.asarray(
            self.field_sampler(float(time_ms), azimuth_array, elevation_array),
            dtype=np.float64,
        )
        if sampled.shape == ():
            sampled = np.full(azimuth_array.shape, float(sampled), dtype=np.float64)
        else:
            sampled = np.broadcast_to(sampled, azimuth_array.shape).astype(np.float64, copy=False)
        if azimuth_array.shape == () and elevation_array.shape == ():
            return float(sampled.reshape(()))
        return sampled


@dataclass(frozen=True)
class RetinalProjectionFrame:
    time_ms: float
    samples: np.ndarray
    frame_metadata: dict[str, Any]
    projector_metadata: dict[str, Any]


@dataclass(frozen=True)
class RetinalProjectionResult:
    eye_sampling: dict[str, Any]
    sampling_kernel: dict[str, Any]
    signal_convention: dict[str, Any]
    source_descriptor: dict[str, Any]
    projector_metadata: dict[str, Any]
    frame_times_ms: np.ndarray
    samples: np.ndarray
    frame_metadata: tuple[dict[str, Any], ...]

    def frame_index_for_time_ms(self, time_ms: float) -> int:
        if self.frame_times_ms.size == 0:
            raise ValueError("RetinalProjectionResult does not contain any frames.")
        insertion_index = int(np.searchsorted(self.frame_times_ms, float(time_ms), side="right") - 1)
        return int(np.clip(insertion_index, 0, self.frame_times_ms.size - 1))

    def frame_at_time_ms(self, time_ms: float) -> RetinalProjectionFrame:
        index = self.frame_index_for_time_ms(time_ms)
        return RetinalProjectionFrame(
            time_ms=float(self.frame_times_ms[index]),
            samples=np.asarray(self.samples[index], dtype=np.float32),
            frame_metadata=copy.deepcopy(self.frame_metadata[index]),
            projector_metadata=copy.deepcopy(self.projector_metadata),
        )


@dataclass(frozen=True)
class _ResolvedVisualSource:
    source_descriptor: dict[str, Any]
    field_of_view: dict[str, Any]
    default_frame_times_ms: np.ndarray | None
    sampler: Callable[..., np.ndarray | float]

    def sample_field(
        self,
        *,
        time_ms: float,
        azimuth_deg: Any,
        elevation_deg: Any,
    ) -> np.ndarray:
        azimuth_array, elevation_array = np.broadcast_arrays(
            np.asarray(azimuth_deg, dtype=np.float64),
            np.asarray(elevation_deg, dtype=np.float64),
        )
        sampled = np.asarray(
            self.sampler(
                time_ms=float(time_ms),
                azimuth_deg=azimuth_array,
                elevation_deg=elevation_array,
            ),
            dtype=np.float64,
        )
        if sampled.shape == ():
            sampled = np.full(azimuth_array.shape, float(sampled), dtype=np.float64)
        else:
            sampled = np.broadcast_to(sampled, azimuth_array.shape).astype(np.float64, copy=False)
        return sampled


@dataclass(frozen=True)
class _PerEyeProjectorCache:
    eye_label: str
    eye_to_world_rotation: np.ndarray
    eye_center_world_mm: np.ndarray
    source_azimuth_deg: np.ndarray
    source_elevation_deg: np.ndarray
    in_field_mask: np.ndarray


class RetinalProjector:
    def __init__(
        self,
        retinal_geometry: Mapping[str, Any] | ResolvedRetinalGeometry,
        visual_source: (
            Mapping[str, Any]
            | ResolvedStimulusSpec
            | StimulusRenderResult
            | AnalyticVisualFieldSource
            | _ResolvedVisualSource
        ),
        *,
        sampling_kernel: Mapping[str, Any] | None = None,
        body_pose: Mapping[str, Any] | None = None,
        head_pose: Mapping[str, Any] | None = None,
    ) -> None:
        self.eye_sampling = _resolve_eye_sampling(retinal_geometry)
        self.sampling_kernel = normalize_retinal_sampling_kernel(sampling_kernel)
        self.signal_convention = default_signal_convention()
        self.visual_source = resolve_visual_source(visual_source)

        (
            self._support_offsets_azimuth_deg,
            self._support_offsets_elevation_deg,
            self._support_angular_distance_deg,
            self._support_weights,
            support_grid_spacing_deg,
            support_ring_count,
        ) = _build_support_kernel(self.sampling_kernel)

        detector_table = self.eye_sampling["per_eye"][self.eye_sampling["eye_order"][0]]["detector_table"]
        detector_azimuth_deg = np.asarray(
            [float(detector["eye_azimuth_deg"]) for detector in detector_table],
            dtype=np.float64,
        )
        detector_elevation_deg = np.asarray(
            [float(detector["eye_elevation_deg"]) for detector in detector_table],
            dtype=np.float64,
        )
        support_azimuth_deg = detector_azimuth_deg[:, None] + self._support_offsets_azimuth_deg[None, :]
        support_elevation_deg = (
            detector_elevation_deg[:, None] + self._support_offsets_elevation_deg[None, :]
        )
        support_directions_eye = _angles_to_direction_array(
            support_azimuth_deg,
            support_elevation_deg,
        )

        world_to_body = build_world_to_body_transform(body_pose)
        body_to_head = build_body_to_head_transform(self.eye_sampling, pose=head_pose)
        self._per_eye_caches: list[_PerEyeProjectorCache] = []
        per_eye_projection_metadata: dict[str, Any] = {}
        eye_to_world_metadata: dict[str, Any] = {}

        for eye_label in self.eye_sampling["eye_order"]:
            eye_to_world = compose_rigid_transforms(
                build_eye_to_head_transform(self.eye_sampling, eye_label),
                body_to_head.inverse(),
                world_to_body.inverse(),
            )
            source_directions_world = np.einsum(
                "ij,nkj->nki",
                eye_to_world.rotation_matrix,
                support_directions_eye,
            )
            source_azimuth_deg, source_elevation_deg = _world_directions_to_visual_field_angles_deg(
                source_directions_world.reshape(-1, 3)
            )
            source_azimuth_deg = source_azimuth_deg.reshape(support_azimuth_deg.shape)
            source_elevation_deg = source_elevation_deg.reshape(support_elevation_deg.shape)
            in_field_mask = _field_of_view_mask(
                source_azimuth_deg,
                source_elevation_deg,
                self.visual_source.field_of_view,
            )
            self._per_eye_caches.append(
                _PerEyeProjectorCache(
                    eye_label=eye_label,
                    eye_to_world_rotation=np.asarray(
                        eye_to_world.rotation_matrix,
                        dtype=np.float64,
                    ),
                    eye_center_world_mm=np.asarray(
                        eye_to_world.translation_vector,
                        dtype=np.float64,
                    ),
                    source_azimuth_deg=source_azimuth_deg,
                    source_elevation_deg=source_elevation_deg,
                    in_field_mask=in_field_mask,
                )
            )
            per_eye_projection_metadata[eye_label] = _build_eye_projection_summary(in_field_mask)
            eye_to_world_metadata[eye_label] = {
                "rotation_matrix": _matrix_to_list(eye_to_world.rotation_matrix),
                "translation_vector_mm": _vector_to_list(eye_to_world.translation_vector),
            }

        self.projector_metadata = {
            "projector_version": RETINAL_PROJECTOR_VERSION,
            "source_field_of_view": copy.deepcopy(self.visual_source.field_of_view),
            "projection_model": {
                "world_direction_to_source_angle_convention": WORLD_DIRECTION_TO_VISUAL_FIELD_CONVENTION,
                "field_of_view_clipping_rule": FIELD_OF_VIEW_CLIPPING_RULE,
                "per_eye_handling_rule": PER_EYE_HANDLING_RULE,
                "out_of_field_blend_rule": OUT_OF_FIELD_BLEND_RULE,
            },
            "kernel_realization": {
                "kernel_family": self.sampling_kernel["kernel_family"],
                "acceptance_angle_deg": _rounded_float(self.sampling_kernel["acceptance_angle_deg"]),
                "acceptance_angle_semantics": GAUSSIAN_ACCEPTANCE_ANGLE_SEMANTICS,
                "support_radius_deg": _rounded_float(self.sampling_kernel["support_radius_deg"]),
                "support_radius_semantics": SUPPORT_RADIUS_SEMANTICS,
                "normalization": self.sampling_kernel["normalization"],
                "out_of_field_policy": self.sampling_kernel["out_of_field_policy"],
                "background_fill_value": _rounded_float(self.sampling_kernel["background_fill_value"]),
                "support_grid_family": SUPPORT_GRID_FAMILY,
                "support_grid_spacing_deg": _rounded_float(support_grid_spacing_deg),
                "support_ring_count": int(support_ring_count),
                "support_sample_count": int(self._support_weights.size),
                "support_offsets_azimuth_deg": _vector_to_list(self._support_offsets_azimuth_deg),
                "support_offsets_elevation_deg": _vector_to_list(self._support_offsets_elevation_deg),
                "support_angular_distance_deg": _vector_to_list(self._support_angular_distance_deg),
                "support_weights": _vector_to_list(self._support_weights),
            },
            "effective_transforms": {
                "world_to_body": _serialize_transform(world_to_body),
                "body_to_head": _serialize_transform(body_to_head),
                "eye_to_world": eye_to_world_metadata,
            },
            "per_eye_projection": per_eye_projection_metadata,
        }

    def sample_frame(self, time_ms: float) -> RetinalProjectionFrame:
        result = self.sample_times([time_ms])
        return RetinalProjectionFrame(
            time_ms=float(result.frame_times_ms[0]),
            samples=np.asarray(result.samples[0], dtype=np.float32),
            frame_metadata=copy.deepcopy(result.frame_metadata[0]),
            projector_metadata=copy.deepcopy(result.projector_metadata),
        )

    def sample_times(self, frame_times_ms: Sequence[float] | np.ndarray) -> RetinalProjectionResult:
        times = np.asarray([float(value) for value in frame_times_ms], dtype=np.float64)
        eye_count = len(self.eye_sampling["eye_order"])
        detector_count = int(self.eye_sampling["ommatidium_count_per_eye"])
        sampled_frames = np.empty((times.size, eye_count, detector_count), dtype=np.float32)
        frame_metadata: list[dict[str, Any]] = []

        for frame_index, time_ms in enumerate(times):
            per_eye_frame_metadata: dict[str, Any] = {}
            for eye_index, eye_cache in enumerate(self._per_eye_caches):
                raw_values = self.visual_source.sample_field(
                    time_ms=float(time_ms),
                    azimuth_deg=eye_cache.source_azimuth_deg,
                    elevation_deg=eye_cache.source_elevation_deg,
                )
                clipped_values = np.clip(raw_values, 0.0, 1.0)
                realized_support_values = np.where(
                    eye_cache.in_field_mask,
                    clipped_values,
                    float(self.sampling_kernel["background_fill_value"]),
                )
                weighted = realized_support_values @ self._support_weights
                sampled_frames[frame_index, eye_index, :] = weighted.astype(np.float32, copy=False)
                per_eye_frame_metadata[eye_cache.eye_label] = {
                    "min_value": _rounded_float(float(np.min(weighted))),
                    "max_value": _rounded_float(float(np.max(weighted))),
                    "mean_value": _rounded_float(float(np.mean(weighted))),
                }
            frame_metadata.append(
                {
                    "time_ms": _rounded_float(float(time_ms)),
                    "per_eye": per_eye_frame_metadata,
                }
            )

        return RetinalProjectionResult(
            eye_sampling=copy.deepcopy(self.eye_sampling),
            sampling_kernel=copy.deepcopy(self.sampling_kernel),
            signal_convention=copy.deepcopy(self.signal_convention),
            source_descriptor=copy.deepcopy(self.visual_source.source_descriptor),
            projector_metadata=copy.deepcopy(self.projector_metadata),
            frame_times_ms=times,
            samples=sampled_frames,
            frame_metadata=tuple(frame_metadata),
        )

    def project_source_timeline(self) -> RetinalProjectionResult:
        if self.visual_source.default_frame_times_ms is None:
            raise ValueError("The visual source does not expose a default frame timeline.")
        return self.sample_times(self.visual_source.default_frame_times_ms)


def resolve_visual_source(
    source: (
        Mapping[str, Any]
        | ResolvedStimulusSpec
        | StimulusRenderResult
        | AnalyticVisualFieldSource
        | _ResolvedVisualSource
    ),
) -> _ResolvedVisualSource:
    if isinstance(source, _ResolvedVisualSource):
        return source

    if isinstance(source, AnalyticVisualFieldSource):
        source_descriptor = {
            "source_kind": source.source_kind,
            "source_contract_version": source.source_contract_version,
            "source_family": source.source_family,
            "source_name": source.source_name,
            "source_metadata": copy.deepcopy(source.source_metadata),
        }
        if source.source_id is not None:
            source_descriptor["source_id"] = source.source_id
        if source.source_hash is not None:
            source_descriptor["source_hash"] = source.source_hash
        return _ResolvedVisualSource(
            source_descriptor=source_descriptor,
            field_of_view=_build_rectangular_field_of_view(
                width_deg=source.width_deg,
                height_deg=source.height_deg,
                field_name="visual_field_degrees_centered",
                x_axis="azimuth_deg_positive_right",
                y_axis="elevation_deg_positive_up",
                origin="aperture_center",
            ),
            default_frame_times_ms=None,
            sampler=source.sample_field,
        )

    if isinstance(source, (ResolvedStimulusSpec, StimulusRenderResult)) or (
        isinstance(source, Mapping) and has_stimulus_reference(source)
    ):
        if isinstance(source, StimulusRenderResult):
            resolved = ResolvedStimulusSpec(
                stimulus_spec=copy.deepcopy(source.stimulus_spec),
                registry_entry=copy.deepcopy(source.registry_entry),
            )
            default_frame_times_ms = np.asarray(source.frame_times_ms, dtype=np.float64)
            source_for_sampling = source
        elif isinstance(source, ResolvedStimulusSpec):
            resolved = source
            default_frame_times_ms = _build_frame_times_ms(resolved.stimulus_spec["temporal_sampling"])
            source_for_sampling = resolved
        else:
            resolved = resolve_stimulus_spec(source)
            default_frame_times_ms = _build_frame_times_ms(resolved.stimulus_spec["temporal_sampling"])
            source_for_sampling = resolved
        stimulus_spec = resolved.stimulus_spec
        return _ResolvedVisualSource(
            source_descriptor={
                "source_kind": "stimulus_bundle",
                "source_contract_version": str(stimulus_spec["bundle_contract_version"]),
                "source_family": str(stimulus_spec["stimulus_family"]),
                "source_name": str(stimulus_spec["stimulus_name"]),
                "source_id": (
                    f"{stimulus_spec['bundle_contract_version']}:"
                    f"{stimulus_spec['stimulus_family']}:"
                    f"{stimulus_spec['stimulus_name']}:"
                    f"{stimulus_spec['parameter_hash']}"
                ),
                "source_hash": str(stimulus_spec["parameter_hash"]),
                "determinism": copy.deepcopy(stimulus_spec["determinism"]),
                "spatial_frame": copy.deepcopy(stimulus_spec["spatial_frame"]),
                "temporal_sampling": copy.deepcopy(stimulus_spec["temporal_sampling"]),
            },
            field_of_view=_build_rectangular_field_of_view(
                width_deg=float(stimulus_spec["spatial_frame"]["width_deg"]),
                height_deg=float(stimulus_spec["spatial_frame"]["height_deg"]),
                field_name=str(stimulus_spec["spatial_frame"]["frame_name"]),
                x_axis=str(stimulus_spec["spatial_frame"]["x_axis"]),
                y_axis=str(stimulus_spec["spatial_frame"]["y_axis"]),
                origin=str(stimulus_spec["spatial_frame"]["origin"]),
            ),
            default_frame_times_ms=default_frame_times_ms,
            sampler=lambda *, time_ms, azimuth_deg, elevation_deg: sample_stimulus_field(
                source_for_sampling,
                time_ms=time_ms,
                azimuth_deg=azimuth_deg,
                elevation_deg=elevation_deg,
            ),
        )

    raise ValueError(
        "visual_source must be a canonical stimulus mapping, ResolvedStimulusSpec, "
        "StimulusRenderResult, or AnalyticVisualFieldSource."
    )


def project_visual_source(
    *,
    retinal_geometry: Mapping[str, Any] | ResolvedRetinalGeometry,
    visual_source: (
        Mapping[str, Any]
        | ResolvedStimulusSpec
        | StimulusRenderResult
        | AnalyticVisualFieldSource
        | _ResolvedVisualSource
    ),
    frame_times_ms: Sequence[float] | np.ndarray | None = None,
    sampling_kernel: Mapping[str, Any] | None = None,
    body_pose: Mapping[str, Any] | None = None,
    head_pose: Mapping[str, Any] | None = None,
) -> RetinalProjectionResult:
    projector = RetinalProjector(
        retinal_geometry=retinal_geometry,
        visual_source=visual_source,
        sampling_kernel=sampling_kernel,
        body_pose=body_pose,
        head_pose=head_pose,
    )
    if frame_times_ms is None:
        return projector.project_source_timeline()
    return projector.sample_times(frame_times_ms)


def _resolve_eye_sampling(
    retinal_geometry: Mapping[str, Any] | ResolvedRetinalGeometry,
) -> dict[str, Any]:
    if isinstance(retinal_geometry, ResolvedRetinalGeometry):
        return retinal_geometry.build_eye_sampling()
    if isinstance(retinal_geometry, Mapping):
        return resolve_retinal_geometry_spec(retinal_geometry).build_eye_sampling()
    raise ValueError("retinal_geometry must be a mapping or ResolvedRetinalGeometry instance.")


def _build_support_kernel(
    sampling_kernel: Mapping[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float, int]:
    acceptance_angle_deg = float(sampling_kernel["acceptance_angle_deg"])
    support_radius_deg = float(sampling_kernel["support_radius_deg"])
    support_grid_spacing_deg = min(acceptance_angle_deg * 0.5, support_radius_deg * 0.5)
    support_grid_spacing_deg = max(support_grid_spacing_deg, support_radius_deg / 8.0, FLOAT_ABS_TOL)
    support_ring_count = int(math.ceil(support_radius_deg / support_grid_spacing_deg))

    offset_azimuth_deg: list[float] = []
    offset_elevation_deg: list[float] = []
    angular_distance_deg: list[float] = []
    weights: list[float] = []

    for axial_q in range(-support_ring_count, support_ring_count + 1):
        for axial_r in range(-support_ring_count, support_ring_count + 1):
            axial_s = -axial_q - axial_r
            ring_index = max(abs(axial_q), abs(axial_r), abs(axial_s))
            if ring_index > support_ring_count:
                continue
            azimuth_deg = support_grid_spacing_deg * _SQRT3_OVER_2 * axial_q
            elevation_deg = support_grid_spacing_deg * (0.5 * axial_q + axial_r)
            direction = _angles_to_direction_array(
                np.asarray([[azimuth_deg]], dtype=np.float64),
                np.asarray([[elevation_deg]], dtype=np.float64),
            )[0, 0]
            distance_deg = _angular_distance_deg(direction, np.asarray([0.0, 0.0, 1.0], dtype=np.float64))
            if distance_deg > support_radius_deg + FLOAT_ABS_TOL:
                continue
            offset_azimuth_deg.append(azimuth_deg)
            offset_elevation_deg.append(elevation_deg)
            angular_distance_deg.append(distance_deg)
            weights.append(math.exp(-0.5 * (distance_deg / acceptance_angle_deg) ** 2))

    if not weights:
        raise AssertionError("Support kernel construction must retain at least the center sample.")

    order = sorted(
        range(len(weights)),
        key=lambda index: (
            round(angular_distance_deg[index], 12),
            round(offset_elevation_deg[index], 12),
            round(offset_azimuth_deg[index], 12),
        ),
    )
    offset_azimuth = np.asarray([offset_azimuth_deg[index] for index in order], dtype=np.float64)
    offset_elevation = np.asarray([offset_elevation_deg[index] for index in order], dtype=np.float64)
    angular_distance = np.asarray([angular_distance_deg[index] for index in order], dtype=np.float64)
    normalized_weights = np.asarray([weights[index] for index in order], dtype=np.float64)
    normalized_weights = normalized_weights / np.sum(normalized_weights)
    return (
        offset_azimuth,
        offset_elevation,
        angular_distance,
        normalized_weights,
        support_grid_spacing_deg,
        support_ring_count,
    )


def _build_eye_projection_summary(in_field_mask: np.ndarray) -> dict[str, Any]:
    detector_in_field_counts = np.sum(in_field_mask, axis=1)
    kernel_support_sample_count = int(in_field_mask.shape[1])
    fully_in_field = detector_in_field_counts == kernel_support_sample_count
    fully_out_of_field = detector_in_field_counts == 0
    partially_clipped = (~fully_in_field) & (~fully_out_of_field)
    return {
        "detector_count": int(in_field_mask.shape[0]),
        "kernel_support_sample_count": kernel_support_sample_count,
        "in_field_support_sample_count": int(np.sum(in_field_mask)),
        "out_of_field_support_sample_count": int(np.size(in_field_mask) - np.sum(in_field_mask)),
        "fully_in_field_detector_count": int(np.sum(fully_in_field)),
        "partially_clipped_detector_count": int(np.sum(partially_clipped)),
        "fully_out_of_field_detector_count": int(np.sum(fully_out_of_field)),
        "partially_clipped_ommatidia": [
            int(index) for index, clipped in enumerate(partially_clipped.tolist()) if clipped
        ],
        "fully_out_of_field_ommatidia": [
            int(index) for index, clipped in enumerate(fully_out_of_field.tolist()) if clipped
        ],
    }


def _build_rectangular_field_of_view(
    *,
    width_deg: float,
    height_deg: float,
    field_name: str,
    x_axis: str,
    y_axis: str,
    origin: str,
) -> dict[str, Any]:
    half_width = float(width_deg) * 0.5
    half_height = float(height_deg) * 0.5
    return {
        "frame_name": field_name,
        "x_axis": x_axis,
        "y_axis": y_axis,
        "origin": origin,
        "clip_shape": "rectangular",
        "width_deg": _rounded_float(float(width_deg)),
        "height_deg": _rounded_float(float(height_deg)),
        "azimuth_range_deg": [
            _rounded_float(-half_width),
            _rounded_float(half_width),
        ],
        "elevation_range_deg": [
            _rounded_float(-half_height),
            _rounded_float(half_height),
        ],
        "bounds_rule": "inclusive",
    }


def _build_frame_times_ms(temporal_sampling: Mapping[str, Any]) -> np.ndarray:
    frame_count = int(temporal_sampling["frame_count"])
    time_origin_ms = float(temporal_sampling["time_origin_ms"])
    dt_ms = float(temporal_sampling["dt_ms"])
    return time_origin_ms + np.arange(frame_count, dtype=np.float64) * dt_ms


def _field_of_view_mask(
    azimuth_deg: np.ndarray,
    elevation_deg: np.ndarray,
    field_of_view: Mapping[str, Any],
) -> np.ndarray:
    if field_of_view["clip_shape"] != "rectangular":
        raise ValueError(f"Unsupported field_of_view.clip_shape {field_of_view['clip_shape']!r}.")
    azimuth_min_deg, azimuth_max_deg = [float(value) for value in field_of_view["azimuth_range_deg"]]
    elevation_min_deg, elevation_max_deg = [float(value) for value in field_of_view["elevation_range_deg"]]
    return (
        (azimuth_deg >= azimuth_min_deg - FLOAT_ABS_TOL)
        & (azimuth_deg <= azimuth_max_deg + FLOAT_ABS_TOL)
        & (elevation_deg >= elevation_min_deg - FLOAT_ABS_TOL)
        & (elevation_deg <= elevation_max_deg + FLOAT_ABS_TOL)
    )


def _world_directions_to_visual_field_angles_deg(
    directions_world: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    normalized = _normalize_direction_array(directions_world)
    azimuth_deg = np.degrees(np.arctan2(-normalized[:, 1], normalized[:, 0]))
    elevation_deg = np.degrees(
        np.arctan2(
            normalized[:, 2],
            np.hypot(normalized[:, 0], normalized[:, 1]),
        )
    )
    return azimuth_deg, elevation_deg


def _angles_to_direction_array(
    azimuth_deg: np.ndarray,
    elevation_deg: np.ndarray,
) -> np.ndarray:
    azimuth_rad = np.radians(np.asarray(azimuth_deg, dtype=np.float64))
    elevation_rad = np.radians(np.asarray(elevation_deg, dtype=np.float64))
    cos_elevation = np.cos(elevation_rad)
    directions = np.stack(
        [
            np.sin(elevation_rad),
            cos_elevation * np.sin(azimuth_rad),
            cos_elevation * np.cos(azimuth_rad),
        ],
        axis=-1,
    )
    norms = np.linalg.norm(directions, axis=-1, keepdims=True)
    return directions / norms


def _normalize_direction_array(directions: np.ndarray) -> np.ndarray:
    array = np.asarray(directions, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("directions must have shape (N, 3).")
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    if np.any(norms <= FLOAT_ABS_TOL):
        raise ValueError("directions must not contain the zero vector.")
    return array / norms


def _angular_distance_deg(direction_a: np.ndarray, direction_b: np.ndarray) -> float:
    dot = float(np.dot(direction_a, direction_b))
    dot = min(1.0, max(-1.0, dot))
    return math.degrees(math.acos(dot))


def _serialize_transform(transform: Any) -> dict[str, Any]:
    return {
        "source_frame": str(transform.source_frame),
        "target_frame": str(transform.target_frame),
        "rotation_matrix": _matrix_to_list(transform.rotation_matrix),
        "translation_vector": _vector_to_list(transform.translation_vector),
    }


def _normalize_json_mapping_like(payload: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    normalized: dict[str, Any] = {}
    for key, value in payload.items():
        normalized[str(key)] = _normalize_json_value_like(value, field_name=f"{field_name}.{key}")
    return normalized


def _normalize_json_value_like(value: Any, *, field_name: str) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return _rounded_float(value)
    if isinstance(value, Mapping):
        return _normalize_json_mapping_like(value, field_name=field_name)
    if isinstance(value, list):
        return [_normalize_json_value_like(item, field_name=field_name) for item in value]
    raise ValueError(f"{field_name} contains a non-JSON-serializable value {type(value).__name__!r}.")


def _matrix_to_list(matrix: np.ndarray) -> list[list[float]]:
    array = np.asarray(matrix, dtype=np.float64)
    return [[_rounded_float(float(value)) for value in row] for row in array.tolist()]


def _vector_to_list(vector: np.ndarray | Sequence[float]) -> list[float]:
    array = np.asarray(vector, dtype=np.float64)
    return [_rounded_float(float(value)) for value in array.tolist()]


def _rounded_float(value: float) -> float:
    return round(float(value), 12)
