from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from .retinal_sampling import AnalyticVisualFieldSource
from .stimulus_contract import (
    DEFAULT_HASH_ALGORITHM,
    _normalize_float,
    _normalize_identifier,
    _normalize_json_mapping,
    _normalize_nonempty_string,
    _normalize_positive_float,
    normalize_temporal_sampling,
)


SCENE_DESCRIPTION_CONTRACT_VERSION = "scene_description.v1"
ANALYTIC_PANORAMA_FAMILY = "analytic_panorama"
YAW_GRADIENT_PANORAMA_NAME = "yaw_gradient_panorama"

DEFAULT_SCENE_VISUAL_FIELD = {
    "width_deg": 360.0,
    "height_deg": 180.0,
}
DEFAULT_SCENE_TEMPORAL_SAMPLING = {
    "time_origin_ms": 0.0,
    "dt_ms": 20.0,
    "duration_ms": 100.0,
}
DEFAULT_SCENE_PARAMETERS = {
    "background_level": 0.5,
    "azimuth_gain_per_deg": 0.0015,
    "elevation_gain_per_deg": 0.0005,
    "temporal_modulation_amplitude": 0.1,
    "temporal_frequency_hz": 1.0,
    "phase_deg": 0.0,
}


@dataclass(frozen=True)
class ResolvedSceneSpec:
    scene_spec: dict[str, Any]

    @property
    def scene_family(self) -> str:
        return str(self.scene_spec["scene_family"])

    @property
    def scene_name(self) -> str:
        return str(self.scene_spec["scene_name"])

    @property
    def scene_hash(self) -> str:
        return str(self.scene_spec["scene_hash"])

    @property
    def visual_field(self) -> dict[str, Any]:
        return copy.deepcopy(self.scene_spec["visual_field"])

    @property
    def temporal_sampling(self) -> dict[str, Any]:
        return copy.deepcopy(self.scene_spec["temporal_sampling"])

    @property
    def frame_times_ms(self) -> np.ndarray:
        temporal_sampling = self.scene_spec["temporal_sampling"]
        frame_count = int(temporal_sampling["frame_count"])
        time_origin_ms = float(temporal_sampling["time_origin_ms"])
        dt_ms = float(temporal_sampling["dt_ms"])
        return time_origin_ms + np.arange(frame_count, dtype=np.float64) * dt_ms

    def build_visual_source(
        self,
        *,
        source_hash: str,
        source_id: str | None = None,
        source_metadata: Mapping[str, Any] | None = None,
    ) -> AnalyticVisualFieldSource:
        metadata = {
            "scene_contract_version": SCENE_DESCRIPTION_CONTRACT_VERSION,
            "scene_hash": self.scene_hash,
            "scene_spec": copy.deepcopy(self.scene_spec),
        }
        if source_metadata is not None:
            metadata.update(
                _normalize_json_mapping(
                source_metadata,
                field_name="source_metadata",
            )
            )
        return AnalyticVisualFieldSource(
            source_family=self.scene_family,
            source_name=self.scene_name,
            width_deg=float(self.scene_spec["visual_field"]["width_deg"]),
            height_deg=float(self.scene_spec["visual_field"]["height_deg"]),
            source_kind="scene_description",
            source_contract_version=SCENE_DESCRIPTION_CONTRACT_VERSION,
            source_id=source_id,
            source_hash=source_hash,
            source_metadata=metadata,
            field_sampler=lambda time_ms, azimuth_deg, elevation_deg: sample_scene_field(
                self.scene_spec,
                time_ms=time_ms,
                azimuth_deg=azimuth_deg,
                elevation_deg=elevation_deg,
            ),
        )


def load_scene_entrypoint(path: str | Path) -> dict[str, Any]:
    entrypoint_path = Path(path).resolve()
    with entrypoint_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"Scene entrypoint at {entrypoint_path} is not a mapping.")
    normalized = copy.deepcopy(dict(payload))
    normalized["__scene_entrypoint_path__"] = str(entrypoint_path)
    return normalized


def resolve_scene_spec(scene: Mapping[str, Any]) -> ResolvedSceneSpec:
    if not isinstance(scene, Mapping):
        raise ValueError("scene must be a mapping.")
    source_payload = scene.get("scene") if isinstance(scene.get("scene"), Mapping) else scene
    if not isinstance(source_payload, Mapping):
        raise ValueError("scene entrypoint is missing a usable scene mapping.")

    scene_family = _normalize_identifier(
        source_payload.get("scene_family"),
        field_name="scene.scene_family",
    )
    if scene_family != ANALYTIC_PANORAMA_FAMILY:
        raise ValueError(
            f"Unsupported scene.scene_family {scene_family!r}. "
            f"Supported families: {[ANALYTIC_PANORAMA_FAMILY]!r}."
        )
    scene_name = _normalize_identifier(
        source_payload.get("scene_name"),
        field_name="scene.scene_name",
    )
    if scene_name != YAW_GRADIENT_PANORAMA_NAME:
        raise ValueError(
            f"Unsupported scene.scene_name {scene_name!r}. "
            f"Supported names: {[YAW_GRADIENT_PANORAMA_NAME]!r}."
        )

    parameter_snapshot = _normalize_scene_parameters(
        source_payload.get("scene_parameters"),
    )
    visual_field = _normalize_scene_visual_field(source_payload.get("visual_field"))
    temporal_sampling = normalize_temporal_sampling(
        source_payload.get("temporal_sampling", DEFAULT_SCENE_TEMPORAL_SAMPLING)
    )
    scene_spec = {
        "scene_contract_version": SCENE_DESCRIPTION_CONTRACT_VERSION,
        "scene_family": scene_family,
        "scene_name": scene_name,
        "parameter_snapshot": parameter_snapshot,
        "visual_field": visual_field,
        "temporal_sampling": temporal_sampling,
    }
    serialized = json.dumps(
        scene_spec,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    scene_spec["scene_hash"] = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    scene_spec["scene_hash_algorithm"] = DEFAULT_HASH_ALGORITHM
    return ResolvedSceneSpec(scene_spec=scene_spec)


def sample_scene_field(
    scene: Mapping[str, Any] | ResolvedSceneSpec,
    *,
    time_ms: float,
    azimuth_deg: Any,
    elevation_deg: Any,
) -> np.ndarray | float:
    if isinstance(scene, ResolvedSceneSpec):
        resolved = scene
    else:
        resolved = resolve_scene_spec(scene)
    azimuth_array, elevation_array = np.broadcast_arrays(
        np.asarray(azimuth_deg, dtype=np.float64),
        np.asarray(elevation_deg, dtype=np.float64),
    )
    if resolved.scene_family != ANALYTIC_PANORAMA_FAMILY:
        raise NotImplementedError(f"No scene sampler is available for {resolved.scene_family!r}.")
    if resolved.scene_name != YAW_GRADIENT_PANORAMA_NAME:
        raise NotImplementedError(f"No scene sampler is available for {resolved.scene_name!r}.")

    parameters = resolved.scene_spec["parameter_snapshot"]
    relative_time_ms = float(time_ms) - float(resolved.scene_spec["temporal_sampling"]["time_origin_ms"])
    temporal_phase = (
        2.0
        * math.pi
        * float(parameters["temporal_frequency_hz"])
        * (relative_time_ms / 1000.0)
        + math.radians(float(parameters["phase_deg"]))
    )
    rendered = (
        float(parameters["background_level"])
        + float(parameters["azimuth_gain_per_deg"]) * azimuth_array
        + float(parameters["elevation_gain_per_deg"]) * elevation_array
        + float(parameters["temporal_modulation_amplitude"]) * np.sin(temporal_phase)
    )
    clipped = np.clip(rendered, 0.0, 1.0).astype(np.float32, copy=False)
    if clipped.ndim == 0:
        return float(clipped)
    return clipped


def _normalize_scene_parameters(payload: Any) -> dict[str, Any]:
    if payload is None:
        payload = {}
    if not isinstance(payload, Mapping):
        raise ValueError("scene.scene_parameters must be a mapping when provided.")
    return {
        "background_level": _normalize_unit_interval(
            payload.get("background_level", DEFAULT_SCENE_PARAMETERS["background_level"]),
            field_name="scene.scene_parameters.background_level",
        ),
        "azimuth_gain_per_deg": _normalize_float(
            payload.get(
                "azimuth_gain_per_deg",
                DEFAULT_SCENE_PARAMETERS["azimuth_gain_per_deg"],
            ),
            field_name="scene.scene_parameters.azimuth_gain_per_deg",
        ),
        "elevation_gain_per_deg": _normalize_float(
            payload.get(
                "elevation_gain_per_deg",
                DEFAULT_SCENE_PARAMETERS["elevation_gain_per_deg"],
            ),
            field_name="scene.scene_parameters.elevation_gain_per_deg",
        ),
        "temporal_modulation_amplitude": _normalize_unit_interval(
            payload.get(
                "temporal_modulation_amplitude",
                DEFAULT_SCENE_PARAMETERS["temporal_modulation_amplitude"],
            ),
            field_name="scene.scene_parameters.temporal_modulation_amplitude",
        ),
        "temporal_frequency_hz": _normalize_nonnegative_float(
            payload.get(
                "temporal_frequency_hz",
                DEFAULT_SCENE_PARAMETERS["temporal_frequency_hz"],
            ),
            field_name="scene.scene_parameters.temporal_frequency_hz",
        ),
        "phase_deg": _normalize_float(
            payload.get("phase_deg", DEFAULT_SCENE_PARAMETERS["phase_deg"]),
            field_name="scene.scene_parameters.phase_deg",
        ),
    }


def _normalize_scene_visual_field(payload: Any) -> dict[str, Any]:
    if payload is None:
        payload = {}
    if not isinstance(payload, Mapping):
        raise ValueError("scene.visual_field must be a mapping when provided.")
    return {
        "width_deg": _normalize_positive_float(
            payload.get("width_deg", DEFAULT_SCENE_VISUAL_FIELD["width_deg"]),
            field_name="scene.visual_field.width_deg",
        ),
        "height_deg": _normalize_positive_float(
            payload.get("height_deg", DEFAULT_SCENE_VISUAL_FIELD["height_deg"]),
            field_name="scene.visual_field.height_deg",
        ),
    }


def _normalize_unit_interval(value: Any, *, field_name: str) -> float:
    normalized = _normalize_float(value, field_name=field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must lie in the unit interval [0.0, 1.0].")
    return normalized


def _normalize_nonnegative_float(value: Any, *, field_name: str) -> float:
    normalized = _normalize_float(value, field_name=field_name)
    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized
