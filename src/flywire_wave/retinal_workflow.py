from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .config import REPO_ROOT, load_config
from .retinal_bundle import load_recorded_retinal_bundle, record_retinal_bundle
from .retinal_contract import (
    DEFAULT_PROCESSED_RETINAL_DIR,
    build_retinal_bundle_metadata,
    build_retinal_source_reference_from_descriptor,
    normalize_retinal_sampling_kernel,
)
from .retinal_geometry import ResolvedRetinalGeometry, build_body_to_head_transform, build_world_to_body_transform, resolve_retinal_geometry_spec
from .retinal_inspection import generate_retinal_inspection_report
from .retinal_sampling import AnalyticVisualFieldSource, project_visual_source
from .scene_playback import ResolvedSceneSpec, load_scene_entrypoint, resolve_scene_spec
from .stimulus_bundle import (
    ResolvedStimulusInput,
    StimulusBundleReplay,
    load_recorded_stimulus_bundle,
    record_stimulus_bundle,
    resolve_stimulus_input,
)
from .stimulus_contract import _normalize_json_mapping


_FLOAT_ABS_TOL = 1.0e-9


@dataclass(frozen=True)
class ResolvedRetinalBundleInput:
    entrypoint_kind: str
    entrypoint_path: Path
    processed_retinal_dir: Path
    retinal_geometry: ResolvedRetinalGeometry
    visual_source: AnalyticVisualFieldSource
    source_descriptor: dict[str, Any]
    source_lineage: dict[str, Any]
    frame_times_ms: np.ndarray
    sampling_kernel: dict[str, Any]
    body_pose: dict[str, Any] | None
    head_pose: dict[str, Any] | None
    retinal_bundle_metadata_path: Path


def resolve_retinal_bundle_input(
    *,
    config_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    scene_path: str | Path | None = None,
    retinal_config_path: str | Path | None = None,
    schema_path: str | Path | None = None,
    design_lock_path: str | Path | None = None,
    processed_stimulus_dir: str | Path | None = None,
    processed_retinal_dir: str | Path | None = None,
) -> ResolvedRetinalBundleInput:
    source_count = int(config_path is not None) + int(manifest_path is not None) + int(scene_path is not None)
    if source_count != 1:
        raise ValueError("Exactly one of config_path, manifest_path, or scene_path must be provided.")

    if config_path is not None:
        cfg = load_config(config_path)
        retinal_geometry = _resolve_retinal_geometry_from_payload(
            cfg,
            context="config",
        )
        recording = _resolve_recording_options(
            payload=cfg,
            processed_retinal_dir=processed_retinal_dir,
            fallback_processed_retinal_dir=cfg["paths"]["processed_retinal_dir"],
        )
        resolved_stimulus_input = resolve_stimulus_input(
            config_path=config_path,
            processed_stimulus_dir=processed_stimulus_dir or cfg["paths"]["processed_stimulus_dir"],
        )
        visual_source, source_descriptor, source_lineage, frame_times_ms = _resolve_stimulus_visual_source(
            resolved_input=resolved_stimulus_input,
            retinal_geometry=retinal_geometry,
            body_pose=recording["body_pose"],
            head_pose=recording["head_pose"],
        )
        bundle_metadata_path = _predict_retinal_bundle_metadata_path(
            processed_retinal_dir=recording["processed_retinal_dir"],
            source_descriptor=source_descriptor,
            retinal_geometry=retinal_geometry,
            frame_times_ms=frame_times_ms,
            sampling_kernel=recording["sampling_kernel"],
        )
        return ResolvedRetinalBundleInput(
            entrypoint_kind="config",
            entrypoint_path=Path(config_path).resolve(),
            processed_retinal_dir=recording["processed_retinal_dir"],
            retinal_geometry=retinal_geometry,
            visual_source=visual_source,
            source_descriptor=source_descriptor,
            source_lineage=source_lineage,
            frame_times_ms=frame_times_ms,
            sampling_kernel=recording["sampling_kernel"],
            body_pose=recording["body_pose"],
            head_pose=recording["head_pose"],
            retinal_bundle_metadata_path=bundle_metadata_path,
        )

    if manifest_path is not None:
        if retinal_config_path is None:
            raise ValueError("retinal_config_path is required when resolving from a manifest.")
        retinal_cfg = load_config(retinal_config_path)
        retinal_geometry = _resolve_retinal_geometry_from_payload(
            retinal_cfg,
            context="retinal_config",
        )
        recording = _resolve_recording_options(
            payload=retinal_cfg,
            processed_retinal_dir=processed_retinal_dir,
            fallback_processed_retinal_dir=retinal_cfg["paths"]["processed_retinal_dir"],
        )
        resolved_stimulus_input = resolve_stimulus_input(
            manifest_path=manifest_path,
            schema_path=schema_path,
            design_lock_path=design_lock_path,
            processed_stimulus_dir=processed_stimulus_dir or retinal_cfg["paths"]["processed_stimulus_dir"],
        )
        visual_source, source_descriptor, source_lineage, frame_times_ms = _resolve_stimulus_visual_source(
            resolved_input=resolved_stimulus_input,
            retinal_geometry=retinal_geometry,
            body_pose=recording["body_pose"],
            head_pose=recording["head_pose"],
        )
        bundle_metadata_path = _predict_retinal_bundle_metadata_path(
            processed_retinal_dir=recording["processed_retinal_dir"],
            source_descriptor=source_descriptor,
            retinal_geometry=retinal_geometry,
            frame_times_ms=frame_times_ms,
            sampling_kernel=recording["sampling_kernel"],
        )
        return ResolvedRetinalBundleInput(
            entrypoint_kind="manifest",
            entrypoint_path=Path(manifest_path).resolve(),
            processed_retinal_dir=recording["processed_retinal_dir"],
            retinal_geometry=retinal_geometry,
            visual_source=visual_source,
            source_descriptor=source_descriptor,
            source_lineage=source_lineage,
            frame_times_ms=frame_times_ms,
            sampling_kernel=recording["sampling_kernel"],
            body_pose=recording["body_pose"],
            head_pose=recording["head_pose"],
            retinal_bundle_metadata_path=bundle_metadata_path,
        )

    scene_payload = load_scene_entrypoint(scene_path)
    retinal_geometry = _resolve_retinal_geometry_from_payload(
        scene_payload,
        context="scene",
    )
    recording = _resolve_recording_options(
        payload=scene_payload,
        processed_retinal_dir=processed_retinal_dir,
        fallback_processed_retinal_dir=_default_processed_retinal_dir(scene_payload),
    )
    resolved_scene = resolve_scene_spec(scene_payload)
    visual_source, source_descriptor, source_lineage, frame_times_ms = _resolve_scene_visual_source(
        scene_path=Path(scene_path).resolve(),
        resolved_scene=resolved_scene,
        retinal_geometry=retinal_geometry,
        body_pose=recording["body_pose"],
        head_pose=recording["head_pose"],
    )
    bundle_metadata_path = _predict_retinal_bundle_metadata_path(
        processed_retinal_dir=recording["processed_retinal_dir"],
        source_descriptor=source_descriptor,
        retinal_geometry=retinal_geometry,
        frame_times_ms=frame_times_ms,
        sampling_kernel=recording["sampling_kernel"],
    )
    return ResolvedRetinalBundleInput(
        entrypoint_kind="scene",
        entrypoint_path=Path(scene_path).resolve(),
        processed_retinal_dir=recording["processed_retinal_dir"],
        retinal_geometry=retinal_geometry,
        visual_source=visual_source,
        source_descriptor=source_descriptor,
        source_lineage=source_lineage,
        frame_times_ms=frame_times_ms,
        sampling_kernel=recording["sampling_kernel"],
        body_pose=recording["body_pose"],
        head_pose=recording["head_pose"],
        retinal_bundle_metadata_path=bundle_metadata_path,
    )


def record_resolved_retinal_bundle(resolved_input: ResolvedRetinalBundleInput) -> dict[str, Any]:
    projection = project_visual_source(
        retinal_geometry=resolved_input.retinal_geometry,
        visual_source=resolved_input.visual_source,
        frame_times_ms=resolved_input.frame_times_ms,
        sampling_kernel=resolved_input.sampling_kernel,
        body_pose=resolved_input.body_pose,
        head_pose=resolved_input.head_pose,
    )
    summary = record_retinal_bundle(
        projection_result=projection,
        processed_retinal_dir=resolved_input.processed_retinal_dir,
    )
    summary["mode"] = "record"
    summary["entrypoint_kind"] = resolved_input.entrypoint_kind
    summary["entrypoint_path"] = str(resolved_input.entrypoint_path)
    summary["resolved_retinal_bundle_metadata_path"] = str(
        resolved_input.retinal_bundle_metadata_path.resolve()
    )
    summary["source_lineage"] = copy.deepcopy(resolved_input.source_lineage)
    summary["frame_times_ms"] = [_rounded_float(value) for value in resolved_input.frame_times_ms]
    return summary


def replay_retinal_bundle_workflow(
    *,
    bundle_metadata_path: str | Path | None = None,
    resolved_input: ResolvedRetinalBundleInput | None = None,
    time_ms: Sequence[float] | None = None,
) -> dict[str, Any]:
    metadata_path = _resolve_retinal_bundle_metadata_path(
        bundle_metadata_path=bundle_metadata_path,
        resolved_input=resolved_input,
    )
    replay = load_recorded_retinal_bundle(metadata_path)
    requested_times = [float(value) for value in (time_ms or [])]

    requested_samples = []
    for requested_time_ms in requested_times:
        frame = replay.frame_at_time_ms(requested_time_ms)
        requested_samples.append(
            {
                "requested_time_ms": _rounded_float(requested_time_ms),
                "frame_index": int(frame.frame_index),
                "frame_time_ms": _rounded_float(frame.time_ms),
                "mean_irradiance": _rounded_float(float(np.mean(frame.retinal_frame))),
                "max_irradiance": _rounded_float(float(np.max(frame.retinal_frame))),
            }
        )

    return {
        "mode": "replay",
        "retinal_bundle_id": replay.bundle_metadata["bundle_id"],
        "retinal_bundle_metadata_path": str(metadata_path.resolve()),
        "replay_source": replay.replay_source,
        "retinal_spec_hash": replay.bundle_metadata["retinal_spec_hash"],
        "frame_count": int(replay.retinal_frames.shape[0]),
        "frame_time_range_ms": [
            _rounded_float(float(replay.frame_times_ms[0])),
            _rounded_float(float(replay.frame_times_ms[-1])),
        ],
        "source_reference": copy.deepcopy(replay.bundle_metadata["source_reference"]),
        "source_lineage": copy.deepcopy(
            replay.source_descriptor.get("source_metadata", {}).get("lineage", {})
        ),
        "requested_samples": requested_samples,
    }


def inspect_retinal_bundle_workflow(
    *,
    bundle_metadata_path: str | Path | None = None,
    resolved_input: ResolvedRetinalBundleInput | None = None,
) -> dict[str, Any]:
    metadata_path, materialized_bundle = _resolve_or_materialize_retinal_bundle(
        bundle_metadata_path=bundle_metadata_path,
        resolved_input=resolved_input,
    )
    summary = generate_retinal_inspection_report(metadata_path)
    summary["mode"] = "inspect"
    summary["bundle_materialized"] = bool(materialized_bundle)
    if resolved_input is not None:
        summary["entrypoint_kind"] = resolved_input.entrypoint_kind
        summary["entrypoint_path"] = str(resolved_input.entrypoint_path)
    return summary


def _resolve_stimulus_visual_source(
    *,
    resolved_input: ResolvedStimulusInput,
    retinal_geometry: ResolvedRetinalGeometry,
    body_pose: Mapping[str, Any] | None,
    head_pose: Mapping[str, Any] | None,
) -> tuple[AnalyticVisualFieldSource, dict[str, Any], dict[str, Any], np.ndarray]:
    replay = _ensure_recorded_stimulus_bundle(resolved_input)
    effective_transforms = _serialize_effective_transforms(
        retinal_geometry=retinal_geometry,
        body_pose=body_pose,
        head_pose=head_pose,
    )
    effective_source_hash = _sha256_json(
        {
            "upstream_bundle_id": replay.bundle_metadata["bundle_id"],
            "upstream_parameter_hash": replay.bundle_metadata["parameter_hash"],
            "effective_transforms": effective_transforms,
        }
    )
    source_lineage = {
        "upstream_source_kind": "stimulus_bundle",
        "upstream_bundle_id": replay.bundle_metadata["bundle_id"],
        "upstream_bundle_metadata_path": str(resolved_input.bundle_metadata_path.resolve()),
        "upstream_parameter_hash": replay.bundle_metadata["parameter_hash"],
        "upstream_frame_cache_path": replay.bundle_metadata["assets"]["frame_cache"]["path"],
        "upstream_replay_source": replay.replay_source,
        "effective_transforms": effective_transforms,
    }
    source_descriptor = {
        "source_kind": "stimulus_bundle",
        "source_contract_version": replay.bundle_metadata["contract_version"],
        "source_family": replay.bundle_metadata["stimulus_family"],
        "source_name": replay.bundle_metadata["stimulus_name"],
        "source_id": (
            f"{replay.bundle_metadata['bundle_id']}:retinal_view:{effective_source_hash}"
        ),
        "source_hash": effective_source_hash,
        "source_metadata": {
            "lineage": copy.deepcopy(source_lineage),
            "resolved_visual_source": {
                "sampler_kind": "cached_stimulus_bundle_sample_hold_nearest_pixel",
                "spatial_frame": copy.deepcopy(replay.bundle_metadata["spatial_frame"]),
                "temporal_sampling": copy.deepcopy(replay.bundle_metadata["temporal_sampling"]),
            },
        },
    }
    visual_source = AnalyticVisualFieldSource(
        source_family=replay.bundle_metadata["stimulus_family"],
        source_name=replay.bundle_metadata["stimulus_name"],
        width_deg=float(replay.bundle_metadata["spatial_frame"]["width_deg"]),
        height_deg=float(replay.bundle_metadata["spatial_frame"]["height_deg"]),
        source_kind="stimulus_bundle",
        source_contract_version=replay.bundle_metadata["contract_version"],
        source_id=source_descriptor["source_id"],
        source_hash=effective_source_hash,
        source_metadata=source_descriptor["source_metadata"],
        field_sampler=lambda time_ms, azimuth_deg, elevation_deg: _sample_stimulus_bundle_field(
            replay,
            time_ms=time_ms,
            azimuth_deg=azimuth_deg,
            elevation_deg=elevation_deg,
        ),
    )
    return (
        visual_source,
        source_descriptor,
        source_lineage,
        np.asarray(replay.frame_times_ms, dtype=np.float64),
    )


def _resolve_scene_visual_source(
    *,
    scene_path: Path,
    resolved_scene: ResolvedSceneSpec,
    retinal_geometry: ResolvedRetinalGeometry,
    body_pose: Mapping[str, Any] | None,
    head_pose: Mapping[str, Any] | None,
) -> tuple[AnalyticVisualFieldSource, dict[str, Any], dict[str, Any], np.ndarray]:
    effective_transforms = _serialize_effective_transforms(
        retinal_geometry=retinal_geometry,
        body_pose=body_pose,
        head_pose=head_pose,
    )
    effective_source_hash = _sha256_json(
        {
            "scene_hash": resolved_scene.scene_hash,
            "effective_transforms": effective_transforms,
        }
    )
    source_lineage = {
        "upstream_source_kind": "scene_description",
        "scene_path": str(scene_path),
        "scene_contract_version": resolved_scene.scene_spec["scene_contract_version"],
        "scene_hash": resolved_scene.scene_hash,
        "effective_transforms": effective_transforms,
    }
    source_descriptor = {
        "source_kind": "scene_description",
        "source_contract_version": resolved_scene.scene_spec["scene_contract_version"],
        "source_family": resolved_scene.scene_family,
        "source_name": resolved_scene.scene_name,
        "source_id": (
            f"{resolved_scene.scene_spec['scene_contract_version']}:"
            f"{resolved_scene.scene_family}:{resolved_scene.scene_name}:{effective_source_hash}"
        ),
        "source_hash": effective_source_hash,
        "source_metadata": {
            "lineage": copy.deepcopy(source_lineage),
            "resolved_visual_source": {
                "scene_hash": resolved_scene.scene_hash,
                "visual_field": resolved_scene.visual_field,
                "temporal_sampling": resolved_scene.temporal_sampling,
            },
        },
    }
    visual_source = resolved_scene.build_visual_source(
        source_hash=effective_source_hash,
        source_id=source_descriptor["source_id"],
        source_metadata=source_descriptor["source_metadata"],
    )
    return (
        visual_source,
        source_descriptor,
        source_lineage,
        resolved_scene.frame_times_ms,
    )


def _resolve_retinal_geometry_from_payload(
    payload: Mapping[str, Any],
    *,
    context: str,
) -> ResolvedRetinalGeometry:
    if "retinal_geometry" not in payload:
        raise ValueError(f"{context} does not define retinal_geometry.")
    return resolve_retinal_geometry_spec(payload)


def _resolve_recording_options(
    *,
    payload: Mapping[str, Any],
    processed_retinal_dir: str | Path | None,
    fallback_processed_retinal_dir: str | Path,
) -> dict[str, Any]:
    recording_payload = payload.get("retinal_recording", {})
    if not isinstance(recording_payload, Mapping):
        raise ValueError("retinal_recording must be a mapping when provided.")

    resolved_processed_retinal_dir = (
        Path(processed_retinal_dir).resolve()
        if processed_retinal_dir is not None
        else Path(fallback_processed_retinal_dir).resolve()
    )
    body_pose = _normalize_optional_mapping(recording_payload.get("body_pose"))
    head_pose = _normalize_optional_mapping(recording_payload.get("head_pose"))
    return {
        "processed_retinal_dir": resolved_processed_retinal_dir,
        "sampling_kernel": normalize_retinal_sampling_kernel(recording_payload.get("sampling_kernel")),
        "body_pose": body_pose,
        "head_pose": head_pose,
    }


def _predict_retinal_bundle_metadata_path(
    *,
    processed_retinal_dir: Path,
    source_descriptor: Mapping[str, Any],
    retinal_geometry: ResolvedRetinalGeometry,
    frame_times_ms: np.ndarray,
    sampling_kernel: Mapping[str, Any],
) -> Path:
    source_reference = build_retinal_source_reference_from_descriptor(source_descriptor)
    bundle_metadata = build_retinal_bundle_metadata(
        source_reference=source_reference,
        eye_sampling=retinal_geometry.build_eye_sampling(),
        temporal_sampling=_build_temporal_sampling_from_frame_times(frame_times_ms),
        processed_retinal_dir=processed_retinal_dir,
        sampling_kernel=sampling_kernel,
    )
    return Path(bundle_metadata["assets"]["metadata_json"]["path"]).resolve()


def _ensure_recorded_stimulus_bundle(resolved_input: ResolvedStimulusInput) -> StimulusBundleReplay:
    metadata_path = resolved_input.bundle_metadata_path.resolve()
    if metadata_path.exists():
        try:
            return load_recorded_stimulus_bundle(metadata_path)
        except (FileNotFoundError, ValueError):
            pass
    record_stimulus_bundle(resolved_input)
    return load_recorded_stimulus_bundle(metadata_path)


def _sample_stimulus_bundle_field(
    replay: StimulusBundleReplay,
    *,
    time_ms: float,
    azimuth_deg: Any,
    elevation_deg: Any,
) -> np.ndarray | float:
    azimuth_array, elevation_array = np.broadcast_arrays(
        np.asarray(azimuth_deg, dtype=np.float64),
        np.asarray(elevation_deg, dtype=np.float64),
    )
    frame = replay.frame_at_time_ms(time_ms)
    x_coordinates = np.asarray(replay.x_coordinates_deg, dtype=np.float64)
    y_coordinates = np.asarray(replay.y_coordinates_deg, dtype=np.float64)
    x_step = float(x_coordinates[1] - x_coordinates[0]) if x_coordinates.size > 1 else 1.0
    y_step = float(y_coordinates[0] - y_coordinates[1]) if y_coordinates.size > 1 else 1.0
    x_indices = np.rint((azimuth_array - x_coordinates[0]) / x_step).astype(np.int64)
    y_indices = np.rint((y_coordinates[0] - elevation_array) / y_step).astype(np.int64)
    x_indices = np.clip(x_indices, 0, x_coordinates.size - 1)
    y_indices = np.clip(y_indices, 0, y_coordinates.size - 1)
    sampled = np.asarray(frame[y_indices, x_indices], dtype=np.float32)
    if sampled.shape == ():
        return float(sampled)
    return sampled


def _resolve_retinal_bundle_metadata_path(
    *,
    bundle_metadata_path: str | Path | None,
    resolved_input: ResolvedRetinalBundleInput | None,
) -> Path:
    if bundle_metadata_path is not None:
        return Path(bundle_metadata_path).resolve()
    if resolved_input is None:
        raise ValueError("Either bundle_metadata_path or resolved_input must be provided.")
    return resolved_input.retinal_bundle_metadata_path.resolve()


def _resolve_or_materialize_retinal_bundle(
    *,
    bundle_metadata_path: str | Path | None,
    resolved_input: ResolvedRetinalBundleInput | None,
) -> tuple[Path, bool]:
    metadata_path = _resolve_retinal_bundle_metadata_path(
        bundle_metadata_path=bundle_metadata_path,
        resolved_input=resolved_input,
    )
    if metadata_path.exists():
        return metadata_path, False
    if resolved_input is None:
        raise FileNotFoundError(f"Retinal bundle metadata is missing at {metadata_path}.")
    record_resolved_retinal_bundle(resolved_input)
    return metadata_path.resolve(), True


def _serialize_effective_transforms(
    *,
    retinal_geometry: ResolvedRetinalGeometry,
    body_pose: Mapping[str, Any] | None,
    head_pose: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "world_to_body": _serialize_transform(build_world_to_body_transform(body_pose)),
        "body_to_head": _serialize_transform(
            build_body_to_head_transform(retinal_geometry, pose=head_pose)
        ),
    }


def _serialize_transform(transform: Any) -> dict[str, Any]:
    rotation = np.asarray(transform.rotation_matrix, dtype=np.float64)
    translation = np.asarray(transform.translation_vector, dtype=np.float64)
    return {
        "source_frame": str(transform.source_frame),
        "target_frame": str(transform.target_frame),
        "rotation_matrix": [[_rounded_float(value) for value in row] for row in rotation.tolist()],
        "translation_vector_mm": [_rounded_float(value) for value in translation.tolist()],
    }


def _build_temporal_sampling_from_frame_times(frame_times_ms: Sequence[float] | np.ndarray) -> dict[str, Any]:
    times = np.asarray(frame_times_ms, dtype=np.float64)
    if times.ndim != 1:
        raise ValueError("frame_times_ms must be one-dimensional.")
    if times.size == 0:
        raise ValueError("At least one frame time is required.")
    if times.size == 1:
        dt_ms = 1.0
    else:
        diffs = np.diff(times)
        if np.any(diffs <= 0.0):
            raise ValueError("frame_times_ms must be strictly increasing.")
        if not np.allclose(diffs, diffs[0], atol=_FLOAT_ABS_TOL, rtol=0.0):
            raise ValueError("frame_times_ms must be uniformly spaced.")
        dt_ms = float(diffs[0])
    return {
        "time_origin_ms": float(times[0]),
        "dt_ms": float(dt_ms),
        "duration_ms": float(dt_ms * times.size),
        "frame_count": int(times.size),
    }


def _normalize_optional_mapping(payload: Any) -> dict[str, Any] | None:
    if payload is None:
        return None
    return _normalize_json_mapping(payload, field_name="retinal_recording")


def _default_processed_retinal_dir(scene_payload: Mapping[str, Any]) -> Path:
    paths = scene_payload.get("paths", {})
    if isinstance(paths, Mapping) and paths.get("processed_retinal_dir") is not None:
        candidate = Path(paths["processed_retinal_dir"]).expanduser()
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        return candidate.resolve()
    return (REPO_ROOT / DEFAULT_PROCESSED_RETINAL_DIR).resolve()


def _sha256_json(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        _normalize_json_mapping(payload, field_name="hash_payload"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _rounded_float(value: float) -> float:
    return round(float(value), 12)
