from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from .stimulus_registry import (
    POLARITY_NEGATIVE,
    POLARITY_POSITIVE,
    RADIAL_FLOW_CONTRACTION,
    RADIAL_FLOW_EXPANSION,
    ResolvedStimulusSpec,
    ROTATION_CLOCKWISE,
    ROTATION_COUNTERCLOCKWISE,
    WAVEFORM_SINE,
    WAVEFORM_SQUARE,
    resolve_stimulus_spec,
)


STIMULUS_GENERATOR_VERSION = "stimulus_generator.v1"
_IMPLEMENTED_FAMILIES = {
    "looming",
    "radial_flow",
    "rotating_flow",
    "flash",
    "moving_bar",
    "translated_edge",
    "drifting_grating",
}
_DIRECTION_REFERENCE = "0_deg_positive_azimuth_counterclockwise_to_positive_elevation"
_VISIBILITY_RULE = "active_when_time_origin_relative_t_in_[onset_ms,offset_ms)"
_FRAME_TIME_RULE = "frame_i_time_ms = time_origin_ms + i * dt_ms"
_TRANSITION_PROFILE = "linear_ramp"


@dataclass(frozen=True)
class StimulusRenderResult:
    stimulus_spec: dict[str, Any]
    registry_entry: dict[str, Any]
    frames: np.ndarray
    frame_times_ms: np.ndarray
    x_coordinates_deg: np.ndarray
    y_coordinates_deg: np.ndarray
    render_metadata: dict[str, Any]

    def sample_field(
        self,
        *,
        time_ms: float,
        azimuth_deg: Any,
        elevation_deg: Any,
    ) -> np.ndarray | float:
        return sample_stimulus_field(
            self,
            time_ms=time_ms,
            azimuth_deg=azimuth_deg,
            elevation_deg=elevation_deg,
        )


def synthesize_stimulus(
    stimulus: Mapping[str, Any] | ResolvedStimulusSpec | StimulusRenderResult | None = None,
    *,
    stimulus_family: str | None = None,
    stimulus_name: str | None = None,
    overrides: Mapping[str, Any] | None = None,
    temporal_sampling: Mapping[str, Any] | None = None,
    spatial_frame: Mapping[str, Any] | None = None,
    luminance_convention: Mapping[str, Any] | None = None,
    determinism: Mapping[str, Any] | None = None,
    seed: int | str | None = None,
) -> StimulusRenderResult:
    resolved = _coerce_resolved_stimulus(
        stimulus,
        stimulus_family=stimulus_family,
        stimulus_name=stimulus_name,
        overrides=overrides,
        temporal_sampling=temporal_sampling,
        spatial_frame=spatial_frame,
        luminance_convention=luminance_convention,
        determinism=determinism,
        seed=seed,
    )
    _validate_implemented_family(resolved.stimulus_family)

    x_coordinates_deg, y_coordinates_deg = build_stimulus_coordinate_axes(
        resolved.stimulus_spec["spatial_frame"]
    )
    frame_times_ms = _build_frame_times_ms(resolved.stimulus_spec["temporal_sampling"])
    frames = np.stack(
        [
            np.asarray(
                _evaluate_family_field(
                    resolved,
                    time_ms=float(frame_time_ms),
                    azimuth_deg=x_coordinates_deg[None, :],
                    elevation_deg=y_coordinates_deg[:, None],
                ),
                dtype=np.float32,
            )
            for frame_time_ms in frame_times_ms
        ],
        axis=0,
    )
    render_metadata = _build_render_metadata(
        resolved=resolved,
        x_coordinates_deg=x_coordinates_deg,
        y_coordinates_deg=y_coordinates_deg,
    )
    return StimulusRenderResult(
        stimulus_spec=copy.deepcopy(resolved.stimulus_spec),
        registry_entry=copy.deepcopy(resolved.registry_entry),
        frames=frames,
        frame_times_ms=frame_times_ms,
        x_coordinates_deg=x_coordinates_deg,
        y_coordinates_deg=y_coordinates_deg,
        render_metadata=render_metadata,
    )


def sample_stimulus_field(
    stimulus: Mapping[str, Any] | ResolvedStimulusSpec | StimulusRenderResult,
    *,
    time_ms: float,
    azimuth_deg: Any,
    elevation_deg: Any,
) -> np.ndarray | float:
    resolved = _coerce_resolved_stimulus(stimulus)
    _validate_implemented_family(resolved.stimulus_family)
    return _evaluate_family_field(
        resolved,
        time_ms=float(time_ms),
        azimuth_deg=azimuth_deg,
        elevation_deg=elevation_deg,
    )


def build_stimulus_coordinate_axes(
    spatial_frame: Mapping[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    width_px = int(spatial_frame["width_px"])
    height_px = int(spatial_frame["height_px"])
    width_deg = float(spatial_frame["width_deg"])
    height_deg = float(spatial_frame["height_deg"])
    x_step_deg = width_deg / width_px
    y_step_deg = height_deg / height_px
    x_coordinates_deg = (
        -width_deg / 2.0 + (np.arange(width_px, dtype=np.float64) + 0.5) * x_step_deg
    )
    y_coordinates_deg = (
        height_deg / 2.0 - (np.arange(height_px, dtype=np.float64) + 0.5) * y_step_deg
    )
    return x_coordinates_deg, y_coordinates_deg


def _coerce_resolved_stimulus(
    stimulus: Mapping[str, Any] | ResolvedStimulusSpec | StimulusRenderResult | None = None,
    *,
    stimulus_family: str | None = None,
    stimulus_name: str | None = None,
    overrides: Mapping[str, Any] | None = None,
    temporal_sampling: Mapping[str, Any] | None = None,
    spatial_frame: Mapping[str, Any] | None = None,
    luminance_convention: Mapping[str, Any] | None = None,
    determinism: Mapping[str, Any] | None = None,
    seed: int | str | None = None,
) -> ResolvedStimulusSpec:
    if isinstance(stimulus, StimulusRenderResult):
        return ResolvedStimulusSpec(
            stimulus_spec=copy.deepcopy(stimulus.stimulus_spec),
            registry_entry=copy.deepcopy(stimulus.registry_entry),
        )
    if isinstance(stimulus, ResolvedStimulusSpec):
        return stimulus
    if stimulus is None and stimulus_family is None and stimulus_name is None:
        raise ValueError("A stimulus mapping or stimulus_family/stimulus_name must be provided.")
    return resolve_stimulus_spec(
        stimulus,
        stimulus_family=stimulus_family,
        stimulus_name=stimulus_name,
        overrides=overrides,
        temporal_sampling=temporal_sampling,
        spatial_frame=spatial_frame,
        luminance_convention=luminance_convention,
        determinism=determinism,
        seed=seed,
    )


def _validate_implemented_family(stimulus_family: str) -> None:
    if stimulus_family not in _IMPLEMENTED_FAMILIES:
        supported = sorted(_IMPLEMENTED_FAMILIES)
        raise NotImplementedError(
            f"Stimulus family {stimulus_family!r} does not have a canonical generator yet. "
            f"Implemented families: {supported!r}."
        )


def _build_frame_times_ms(temporal_sampling: Mapping[str, Any]) -> np.ndarray:
    frame_count = int(temporal_sampling["frame_count"])
    dt_ms = float(temporal_sampling["dt_ms"])
    time_origin_ms = float(temporal_sampling["time_origin_ms"])
    return time_origin_ms + np.arange(frame_count, dtype=np.float64) * dt_ms


def _evaluate_family_field(
    resolved: ResolvedStimulusSpec,
    *,
    time_ms: float,
    azimuth_deg: Any,
    elevation_deg: Any,
) -> np.ndarray | float:
    azimuth_array, elevation_array = np.broadcast_arrays(
        np.asarray(azimuth_deg, dtype=np.float64),
        np.asarray(elevation_deg, dtype=np.float64),
    )
    parameters = resolved.stimulus_spec["parameter_snapshot"]
    background_level = float(parameters["background_level"])
    relative_time_ms = _relative_time_ms(resolved, time_ms=time_ms)

    if not _is_active(resolved, relative_time_ms=relative_time_ms):
        background = np.full(azimuth_array.shape, background_level, dtype=np.float64)
        return _finalize_output(background, resolved.stimulus_spec["luminance_convention"])

    if resolved.stimulus_family == "flash":
        rendered = _render_flash(
            resolved,
            azimuth_array=azimuth_array,
            elevation_array=elevation_array,
        )
    elif resolved.stimulus_family == "looming":
        rendered = _render_looming(
            resolved,
            relative_time_ms=relative_time_ms,
            azimuth_array=azimuth_array,
            elevation_array=elevation_array,
        )
    elif resolved.stimulus_family == "moving_bar":
        rendered = _render_moving_bar(
            resolved,
            relative_time_ms=relative_time_ms,
            azimuth_array=azimuth_array,
            elevation_array=elevation_array,
        )
    elif resolved.stimulus_family == "translated_edge":
        rendered = _render_translated_edge(
            resolved,
            relative_time_ms=relative_time_ms,
            azimuth_array=azimuth_array,
            elevation_array=elevation_array,
        )
    elif resolved.stimulus_family == "drifting_grating":
        rendered = _render_drifting_grating(
            resolved,
            relative_time_ms=relative_time_ms,
            azimuth_array=azimuth_array,
            elevation_array=elevation_array,
        )
    elif resolved.stimulus_family == "radial_flow":
        rendered = _render_radial_flow(
            resolved,
            relative_time_ms=relative_time_ms,
            azimuth_array=azimuth_array,
            elevation_array=elevation_array,
        )
    elif resolved.stimulus_family == "rotating_flow":
        rendered = _render_rotating_flow(
            resolved,
            relative_time_ms=relative_time_ms,
            azimuth_array=azimuth_array,
            elevation_array=elevation_array,
        )
    else:
        raise NotImplementedError(f"No evaluator is available for {resolved.stimulus_family!r}.")

    return _finalize_output(rendered, resolved.stimulus_spec["luminance_convention"])


def _render_flash(
    resolved: ResolvedStimulusSpec,
    *,
    azimuth_array: np.ndarray,
    elevation_array: np.ndarray,
) -> np.ndarray:
    parameters = resolved.stimulus_spec["parameter_snapshot"]
    background_level = float(parameters["background_level"])
    feature_level = _feature_level_unclipped(resolved)
    radius = np.hypot(
        azimuth_array - float(parameters["center_azimuth_deg"]),
        elevation_array - float(parameters["center_elevation_deg"]),
    )
    coverage = _soft_disc_coverage(
        radial_distance_deg=radius,
        radius_deg=float(parameters["radius_deg"]),
        edge_softness_deg=float(parameters["edge_softness_deg"]),
    )
    return background_level + coverage * (feature_level - background_level)


def _render_looming(
    resolved: ResolvedStimulusSpec,
    *,
    relative_time_ms: float,
    azimuth_array: np.ndarray,
    elevation_array: np.ndarray,
) -> np.ndarray:
    parameters = resolved.stimulus_spec["parameter_snapshot"]
    background_level = float(parameters["background_level"])
    feature_level = _feature_level_unclipped(resolved)
    radius = np.hypot(
        azimuth_array - float(parameters["center_azimuth_deg"]),
        elevation_array - float(parameters["center_elevation_deg"]),
    )
    current_radius_deg = (
        float(parameters["initial_radius_deg"])
        + _active_interval_fraction(resolved, relative_time_ms=relative_time_ms)
        * (float(parameters["final_radius_deg"]) - float(parameters["initial_radius_deg"]))
    )
    coverage = _soft_disc_coverage(
        radial_distance_deg=radius,
        radius_deg=current_radius_deg,
        edge_softness_deg=float(parameters["edge_softness_deg"]),
    )
    return background_level + coverage * (feature_level - background_level)


def _render_moving_bar(
    resolved: ResolvedStimulusSpec,
    *,
    relative_time_ms: float,
    azimuth_array: np.ndarray,
    elevation_array: np.ndarray,
) -> np.ndarray:
    parameters = resolved.stimulus_spec["parameter_snapshot"]
    background_level = float(parameters["background_level"])
    feature_level = _feature_level_unclipped(resolved)
    relative_x = azimuth_array - float(parameters["center_azimuth_deg"])
    relative_y = elevation_array - float(parameters["center_elevation_deg"])
    motion_axis = _direction_unit_vector(float(parameters["direction_deg"]))
    motion_position_deg = (
        float(parameters["velocity_deg_per_s"]) * (relative_time_ms / 1000.0)
    )
    motion_coordinate = relative_x * motion_axis[0] + relative_y * motion_axis[1]
    bar_distance = np.abs(motion_coordinate - motion_position_deg)
    bar_coverage = _soft_band_coverage(
        signed_distance_deg=bar_distance,
        half_width_deg=float(parameters["bar_width_deg"]) / 2.0,
        edge_softness_deg=float(parameters["edge_softness_deg"]),
    )
    aperture_radius = np.hypot(relative_x, relative_y)
    aperture_coverage = (aperture_radius <= float(parameters["aperture_radius_deg"])).astype(
        np.float64
    )
    coverage = bar_coverage * aperture_coverage
    return background_level + coverage * (feature_level - background_level)


def _render_translated_edge(
    resolved: ResolvedStimulusSpec,
    *,
    relative_time_ms: float,
    azimuth_array: np.ndarray,
    elevation_array: np.ndarray,
) -> np.ndarray:
    parameters = resolved.stimulus_spec["parameter_snapshot"]
    background_level = float(parameters["background_level"])
    feature_level = _feature_level_unclipped(resolved)
    relative_x = azimuth_array - float(parameters["center_azimuth_deg"])
    relative_y = elevation_array - float(parameters["center_elevation_deg"])
    motion_axis = _direction_unit_vector(float(parameters["direction_deg"]))
    projected_position_deg = relative_x * motion_axis[0] + relative_y * motion_axis[1]
    edge_position_deg = float(parameters["phase_offset_deg"]) + float(
        parameters["velocity_deg_per_s"]
    ) * (relative_time_ms / 1000.0)
    signed_distance_to_edge_deg = projected_position_deg - edge_position_deg
    coverage = _translated_edge_coverage(
        signed_distance_deg=signed_distance_to_edge_deg,
        edge_width_deg=float(parameters["edge_width_deg"]),
    )
    return background_level + coverage * (feature_level - background_level)


def _render_drifting_grating(
    resolved: ResolvedStimulusSpec,
    *,
    relative_time_ms: float,
    azimuth_array: np.ndarray,
    elevation_array: np.ndarray,
) -> np.ndarray:
    parameters = resolved.stimulus_spec["parameter_snapshot"]
    background_level = float(parameters["background_level"])
    relative_x = azimuth_array - float(parameters["center_azimuth_deg"])
    relative_y = elevation_array - float(parameters["center_elevation_deg"])
    motion_axis = _direction_unit_vector(float(parameters["drift_direction_deg"]))
    projected_position_deg = relative_x * motion_axis[0] + relative_y * motion_axis[1]
    spatial_phase_rad = (
        2.0 * math.pi * float(parameters["spatial_frequency_cpd"]) * projected_position_deg
    )
    temporal_phase_rad = (
        2.0 * math.pi * float(parameters["temporal_frequency_hz"]) * (relative_time_ms / 1000.0)
    )
    initial_phase_rad = math.radians(float(parameters["phase_deg"]))
    carrier_phase = spatial_phase_rad - temporal_phase_rad + initial_phase_rad
    grating_wave = _evaluate_waveform(carrier_phase, waveform=str(parameters["waveform"]))
    modulation = _signed_contrast_delta(resolved) * grating_wave
    neutral_value = float(resolved.stimulus_spec["luminance_convention"]["neutral_value"])
    active_level = neutral_value + modulation
    aperture_radius = np.hypot(relative_x, relative_y)
    aperture_coverage = (aperture_radius <= float(parameters["aperture_radius_deg"])).astype(
        np.float64
    )
    return background_level + aperture_coverage * (active_level - background_level)


def _render_radial_flow(
    resolved: ResolvedStimulusSpec,
    *,
    relative_time_ms: float,
    azimuth_array: np.ndarray,
    elevation_array: np.ndarray,
) -> np.ndarray:
    parameters = resolved.stimulus_spec["parameter_snapshot"]
    background_level = float(parameters["background_level"])
    relative_x = azimuth_array - float(parameters["center_azimuth_deg"])
    relative_y = elevation_array - float(parameters["center_elevation_deg"])
    radial_distance_deg = np.hypot(relative_x, relative_y)
    sign_multiplier = _radial_motion_sign_multiplier(str(parameters["motion_sign"]))
    radial_displacement_deg = (
        sign_multiplier * float(parameters["radial_speed_deg_per_s"]) * (relative_time_ms / 1000.0)
    )
    carrier_phase = (
        2.0
        * math.pi
        * float(parameters["radial_spatial_frequency_cpd"])
        * (radial_distance_deg - radial_displacement_deg)
        + math.radians(float(parameters["phase_deg"]))
    )
    radial_wave = _evaluate_waveform(carrier_phase, waveform=str(parameters["waveform"]))
    modulation = _signed_contrast_delta(resolved) * radial_wave
    neutral_value = float(resolved.stimulus_spec["luminance_convention"]["neutral_value"])
    active_level = neutral_value + modulation
    annulus_coverage = _annulus_coverage(
        radial_distance_deg=radial_distance_deg,
        inner_radius_deg=float(parameters["inner_radius_deg"]),
        outer_radius_deg=float(parameters["outer_radius_deg"]),
    )
    return background_level + annulus_coverage * (active_level - background_level)


def _render_rotating_flow(
    resolved: ResolvedStimulusSpec,
    *,
    relative_time_ms: float,
    azimuth_array: np.ndarray,
    elevation_array: np.ndarray,
) -> np.ndarray:
    parameters = resolved.stimulus_spec["parameter_snapshot"]
    background_level = float(parameters["background_level"])
    relative_x = azimuth_array - float(parameters["center_azimuth_deg"])
    relative_y = elevation_array - float(parameters["center_elevation_deg"])
    radial_distance_deg = np.hypot(relative_x, relative_y)
    polar_angle_rad = np.arctan2(relative_y, relative_x)
    sign_multiplier = _rotation_sign_multiplier(str(parameters["rotation_direction"]))
    angular_displacement_rad = (
        sign_multiplier
        * math.radians(float(parameters["angular_velocity_deg_per_s"]))
        * (relative_time_ms / 1000.0)
    )
    carrier_phase = (
        int(parameters["angular_cycle_count"]) * (polar_angle_rad - angular_displacement_rad)
        + math.radians(float(parameters["phase_deg"]))
    )
    rotating_wave = _evaluate_waveform(carrier_phase, waveform=str(parameters["waveform"]))
    modulation = _signed_contrast_delta(resolved) * rotating_wave
    neutral_value = float(resolved.stimulus_spec["luminance_convention"]["neutral_value"])
    active_level = neutral_value + modulation
    annulus_coverage = _annulus_coverage(
        radial_distance_deg=radial_distance_deg,
        inner_radius_deg=float(parameters["inner_radius_deg"]),
        outer_radius_deg=float(parameters["outer_radius_deg"]),
    )
    return background_level + annulus_coverage * (active_level - background_level)


def _relative_time_ms(resolved: ResolvedStimulusSpec, *, time_ms: float) -> float:
    time_origin_ms = float(resolved.stimulus_spec["temporal_sampling"]["time_origin_ms"])
    return float(time_ms) - time_origin_ms


def _is_active(resolved: ResolvedStimulusSpec, *, relative_time_ms: float) -> bool:
    parameters = resolved.stimulus_spec["parameter_snapshot"]
    return float(parameters["onset_ms"]) <= relative_time_ms < float(parameters["offset_ms"])


def _feature_level_unclipped(resolved: ResolvedStimulusSpec) -> float:
    neutral_value = float(resolved.stimulus_spec["luminance_convention"]["neutral_value"])
    return neutral_value + _signed_contrast_delta(resolved)


def _active_interval_fraction(resolved: ResolvedStimulusSpec, *, relative_time_ms: float) -> float:
    parameters = resolved.stimulus_spec["parameter_snapshot"]
    onset_ms = float(parameters["onset_ms"])
    offset_ms = float(parameters["offset_ms"])
    if offset_ms <= onset_ms:
        return 0.0
    return float(np.clip((relative_time_ms - onset_ms) / (offset_ms - onset_ms), 0.0, 1.0))


def _signed_contrast_delta(resolved: ResolvedStimulusSpec) -> float:
    parameters = resolved.stimulus_spec["parameter_snapshot"]
    polarity = str(parameters["polarity"])
    sign = 1.0 if polarity == POLARITY_POSITIVE else -1.0
    if polarity not in {POLARITY_POSITIVE, POLARITY_NEGATIVE}:
        raise ValueError(f"Unsupported polarity {polarity!r}.")
    return sign * float(parameters["contrast"])


def _direction_unit_vector(direction_deg: float) -> np.ndarray:
    direction_rad = math.radians(direction_deg)
    return np.array([math.cos(direction_rad), math.sin(direction_rad)], dtype=np.float64)


def _evaluate_waveform(carrier_phase: np.ndarray, *, waveform: str) -> np.ndarray:
    if waveform == WAVEFORM_SINE:
        return np.sin(carrier_phase)
    if waveform == WAVEFORM_SQUARE:
        return np.where(np.sin(carrier_phase) >= 0.0, 1.0, -1.0)
    raise NotImplementedError(f"Unsupported waveform {waveform!r}.")


def _radial_motion_sign_multiplier(motion_sign: str) -> float:
    if motion_sign == RADIAL_FLOW_EXPANSION:
        return 1.0
    if motion_sign == RADIAL_FLOW_CONTRACTION:
        return -1.0
    raise ValueError(f"Unsupported radial-flow motion_sign {motion_sign!r}.")


def _rotation_sign_multiplier(rotation_direction: str) -> float:
    if rotation_direction == ROTATION_COUNTERCLOCKWISE:
        return 1.0
    if rotation_direction == ROTATION_CLOCKWISE:
        return -1.0
    raise ValueError(f"Unsupported rotation_direction {rotation_direction!r}.")


def _soft_disc_coverage(
    *,
    radial_distance_deg: np.ndarray,
    radius_deg: float,
    edge_softness_deg: float,
) -> np.ndarray:
    if edge_softness_deg <= 0.0:
        return (radial_distance_deg <= radius_deg).astype(np.float64)
    lower_bound = radius_deg - edge_softness_deg / 2.0
    upper_bound = radius_deg + edge_softness_deg / 2.0
    return np.clip((upper_bound - radial_distance_deg) / (upper_bound - lower_bound), 0.0, 1.0)


def _soft_band_coverage(
    *,
    signed_distance_deg: np.ndarray,
    half_width_deg: float,
    edge_softness_deg: float,
) -> np.ndarray:
    if edge_softness_deg <= 0.0:
        return (signed_distance_deg <= half_width_deg).astype(np.float64)
    lower_bound = half_width_deg - edge_softness_deg / 2.0
    upper_bound = half_width_deg + edge_softness_deg / 2.0
    return np.clip((upper_bound - signed_distance_deg) / (upper_bound - lower_bound), 0.0, 1.0)


def _translated_edge_coverage(
    *,
    signed_distance_deg: np.ndarray,
    edge_width_deg: float,
) -> np.ndarray:
    if edge_width_deg <= 0.0:
        return (signed_distance_deg <= 0.0).astype(np.float64)
    half_width = edge_width_deg / 2.0
    return np.clip((half_width - signed_distance_deg) / edge_width_deg, 0.0, 1.0)


def _annulus_coverage(
    *,
    radial_distance_deg: np.ndarray,
    inner_radius_deg: float,
    outer_radius_deg: float,
) -> np.ndarray:
    return (
        (radial_distance_deg >= inner_radius_deg) & (radial_distance_deg <= outer_radius_deg)
    ).astype(np.float64)


def _finalize_output(
    rendered: np.ndarray,
    luminance_convention: Mapping[str, Any],
) -> np.ndarray | float:
    clipped = np.clip(
        rendered,
        float(luminance_convention["minimum_value"]),
        float(luminance_convention["maximum_value"]),
    ).astype(np.float32, copy=False)
    if clipped.ndim == 0:
        return float(clipped)
    return clipped


def _build_render_metadata(
    *,
    resolved: ResolvedStimulusSpec,
    x_coordinates_deg: np.ndarray,
    y_coordinates_deg: np.ndarray,
) -> dict[str, Any]:
    parameters = resolved.stimulus_spec["parameter_snapshot"]
    temporal_sampling = resolved.stimulus_spec["temporal_sampling"]
    luminance_convention = resolved.stimulus_spec["luminance_convention"]
    family_specific = _build_family_rendering_metadata(resolved)
    return {
        "generator_version": STIMULUS_GENERATOR_VERSION,
        "stimulus_family": resolved.stimulus_family,
        "stimulus_name": resolved.stimulus_name,
        "parameter_hash": resolved.stimulus_spec["parameter_hash"],
        "frame_time_rule": _FRAME_TIME_RULE,
        "visibility_rule": _VISIBILITY_RULE,
        "frame_shape_t_y_x": [
            int(temporal_sampling["frame_count"]),
            int(resolved.stimulus_spec["spatial_frame"]["height_px"]),
            int(resolved.stimulus_spec["spatial_frame"]["width_px"]),
        ],
        "frame_dtype": "float32",
        "coordinate_sampling": {
            "direction_reference": _DIRECTION_REFERENCE,
            "x_sample_spacing_deg": float(_sample_spacing_deg(x_coordinates_deg)),
            "y_sample_spacing_deg": float(_sample_spacing_deg(y_coordinates_deg)),
            "row_zero_elevation_deg": float(y_coordinates_deg[0]),
            "column_zero_azimuth_deg": float(x_coordinates_deg[0]),
        },
        "timing": {
            "time_origin_ms": float(temporal_sampling["time_origin_ms"]),
            "dt_ms": float(temporal_sampling["dt_ms"]),
            "frame_count": int(temporal_sampling["frame_count"]),
            "onset_ms": float(parameters["onset_ms"]),
            "offset_ms": float(parameters["offset_ms"]),
            "sampling_mode": str(temporal_sampling["sampling_mode"]),
        },
        "luminance_mapping": {
            "background_level": float(parameters["background_level"]),
            "neutral_value": float(luminance_convention["neutral_value"]),
            "contrast_magnitude": float(parameters["contrast"]),
            "polarity": str(parameters["polarity"]),
            "signed_contrast_delta": float(_signed_contrast_delta(resolved)),
            "feature_level_unclipped": float(_feature_level_unclipped(resolved)),
            "clip_range": [
                float(luminance_convention["minimum_value"]),
                float(luminance_convention["maximum_value"]),
            ],
            "clip_mode": "clip_final_frame_values_to_unit_interval",
        },
        "determinism": {
            **copy.deepcopy(resolved.stimulus_spec["determinism"]),
            "stochastic_branches_used": False,
        },
        "family_rendering": family_specific,
    }


def _build_family_rendering_metadata(resolved: ResolvedStimulusSpec) -> dict[str, Any]:
    parameters = resolved.stimulus_spec["parameter_snapshot"]
    common = {
        "center_azimuth_deg": float(parameters["center_azimuth_deg"]),
        "center_elevation_deg": float(parameters["center_elevation_deg"]),
        "direction_reference": _DIRECTION_REFERENCE,
        "phase_reference": "bundle_time_origin_ms",
        "transition_profile": _TRANSITION_PROFILE,
    }
    if resolved.stimulus_family == "flash":
        return {
            **common,
            "family_kind": "disc_flash",
            "radius_deg": float(parameters["radius_deg"]),
            "edge_softness_deg": float(parameters["edge_softness_deg"]),
            "mask_handling": "flash_disc_blends_to_background_with_linear_boundary_ramp",
        }
    if resolved.stimulus_family == "looming":
        return {
            **common,
            "family_kind": "looming_disc",
            "initial_radius_deg": float(parameters["initial_radius_deg"]),
            "final_radius_deg": float(parameters["final_radius_deg"]),
            "edge_softness_deg": float(parameters["edge_softness_deg"]),
            "radius_units": "deg",
            "growth_schedule": (
                "radius_deg = initial_radius_deg + "
                "((t_ms - onset_ms)/(offset_ms - onset_ms)) * "
                "(final_radius_deg - initial_radius_deg)"
            ),
            "growth_domain": "active_interval_only",
            "motion_sign": "expansion",
            "mask_handling": "soft_disc_blends_to_background_with_linear_boundary_ramp",
        }
    if resolved.stimulus_family == "moving_bar":
        return {
            **common,
            "family_kind": "moving_bar",
            "direction_deg": float(parameters["direction_deg"]),
            "bar_orientation_deg": float((float(parameters["direction_deg"]) + 90.0) % 360.0),
            "velocity_deg_per_s": float(parameters["velocity_deg_per_s"]),
            "bar_width_deg": float(parameters["bar_width_deg"]),
            "aperture_radius_deg": float(parameters["aperture_radius_deg"]),
            "edge_softness_deg": float(parameters["edge_softness_deg"]),
            "mask_handling": "hard_circular_aperture_with_soft_bar_edges",
            "motion_reference": "bar_center_crosses_stimulus_center_at_bundle_time_origin_ms",
        }
    if resolved.stimulus_family == "translated_edge":
        return {
            **common,
            "family_kind": "translated_edge",
            "direction_deg": float(parameters["direction_deg"]),
            "velocity_deg_per_s": float(parameters["velocity_deg_per_s"]),
            "edge_width_deg": float(parameters["edge_width_deg"]),
            "phase_offset_deg": float(parameters["phase_offset_deg"]),
            "mask_handling": "full_frame_edge_without_aperture_clipping",
            "feature_region_rule": "feature_on_negative_signed_distance_side_of_translated_edge",
            "motion_reference": "edge_position_deg = phase_offset_deg + velocity_deg_per_s * t_s",
        }
    if resolved.stimulus_family == "drifting_grating":
        return {
            **common,
            "family_kind": "drifting_grating",
            "direction_deg": float(parameters["drift_direction_deg"]),
            "spatial_frequency_cpd": float(parameters["spatial_frequency_cpd"]),
            "temporal_frequency_hz": float(parameters["temporal_frequency_hz"]),
            "phase_deg": float(parameters["phase_deg"]),
            "waveform": str(parameters["waveform"]),
            "aperture_radius_deg": float(parameters["aperture_radius_deg"]),
            "mask_handling": "hard_circular_aperture_around_center",
            "motion_reference": "carrier_phase = 2pi*sf*x_along_direction - 2pi*tf*t + phase0",
        }
    if resolved.stimulus_family == "radial_flow":
        return {
            **common,
            "family_kind": "radial_flow",
            "motion_sign": str(parameters["motion_sign"]),
            "radial_speed_deg_per_s": float(parameters["radial_speed_deg_per_s"]),
            "radial_speed_units": "deg_per_s_along_radius",
            "radial_spatial_frequency_cpd": float(parameters["radial_spatial_frequency_cpd"]),
            "phase_deg": float(parameters["phase_deg"]),
            "waveform": str(parameters["waveform"]),
            "inner_radius_deg": float(parameters["inner_radius_deg"]),
            "outer_radius_deg": float(parameters["outer_radius_deg"]),
            "mask_handling": "hard_annulus_centered_on_motion_center",
            "motion_reference": (
                "carrier_phase = 2pi*radial_spatial_frequency_cpd*"
                "(radius_deg - signed_radial_speed_deg_per_s*t_s) + phase0"
            ),
            "radius_reference": "radius_deg = hypot(x_deg - center_x_deg, y_deg - center_y_deg)",
        }
    if resolved.stimulus_family == "rotating_flow":
        return {
            **common,
            "family_kind": "rotating_flow",
            "rotation_direction": str(parameters["rotation_direction"]),
            "angular_velocity_deg_per_s": float(parameters["angular_velocity_deg_per_s"]),
            "angular_velocity_units": "deg_per_s_about_motion_center",
            "angular_cycle_count": int(parameters["angular_cycle_count"]),
            "phase_deg": float(parameters["phase_deg"]),
            "waveform": str(parameters["waveform"]),
            "inner_radius_deg": float(parameters["inner_radius_deg"]),
            "outer_radius_deg": float(parameters["outer_radius_deg"]),
            "mask_handling": "hard_annulus_centered_on_motion_center",
            "rotation_reference": (
                "theta_rad = atan2(y_deg - center_y_deg, x_deg - center_x_deg); "
                "positive_theta_is_counterclockwise"
            ),
            "motion_reference": (
                "carrier_phase = angular_cycle_count*"
                "(theta_rad - signed_angular_velocity_rad_per_s*t_s) + phase0"
            ),
        }
    raise NotImplementedError(f"No render metadata is available for {resolved.stimulus_family!r}.")


def _sample_spacing_deg(values: np.ndarray) -> float:
    if values.size < 2:
        return 0.0
    return float(np.abs(values[1] - values[0]))
