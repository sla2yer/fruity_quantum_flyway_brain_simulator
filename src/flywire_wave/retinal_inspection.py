from __future__ import annotations

import copy
import html
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

from .io_utils import ensure_dir, write_json
from .retinal_contract import FRAME_ARCHIVE_KEY, load_retinal_bundle_metadata, write_retinal_bundle_metadata
from .scene_playback import resolve_scene_spec, sample_scene_field
from .stimulus_bundle import load_recorded_stimulus_bundle


RETINAL_INSPECTION_REPORT_VERSION = "retinal_inspection.v1"
RETINAL_INSPECTION_DIR_NAME = "inspection"
RETINAL_INSPECTION_FRAMES_DIR_NAME = "frames"
RETINAL_INSPECTION_CELL_SIZE_PX = 6
RETINAL_INSPECTION_MAX_DIMENSION_PX = 96
RETINAL_PANEL_WIDTH_PX = 220
RETINAL_PANEL_HEIGHT_PX = 220
RETINAL_PANEL_PADDING_PX = 20.0
RETINAL_LATTICE_LABEL_FONT_SIZE_PX = 10
DEFAULT_SCENE_PREVIEW_WIDTH_PX = 96
_FLOAT_ABS_TOL = 1.0e-9

STATUS_PASS = "pass"
STATUS_WARN = "warn"
STATUS_FAIL = "fail"
STATUS_UNKNOWN = "unknown"

STATUS_RANK = {
    STATUS_PASS: 0,
    STATUS_WARN: 1,
    STATUS_FAIL: 2,
}

_COVERAGE_STATUS_COLORS = {
    STATUS_PASS: "#0f766e",
    STATUS_WARN: "#d97706",
    STATUS_FAIL: "#b91c1c",
    STATUS_UNKNOWN: "#64748b",
}


@dataclass(frozen=True)
class RetinalInspectionArchive:
    bundle_metadata: dict[str, Any]
    metadata_path: Path
    frame_archive_path: Path
    retinal_frames: np.ndarray
    early_visual_units: np.ndarray
    frame_times_ms: np.ndarray
    frame_metadata: list[dict[str, Any]]
    source_descriptor: dict[str, Any]
    projector_metadata: dict[str, Any]
    load_errors: tuple[str, ...]


@dataclass(frozen=True)
class SourcePreviewContext:
    source_kind: str
    source_family: str
    source_name: str
    source_hash: str
    field_of_view: dict[str, Any]
    frame_count: int | None
    frame_shape_y_x: list[int]
    entrypoint_path: str | None
    details: dict[str, Any]
    render_frame: Callable[[float], np.ndarray] | None


def generate_retinal_inspection_report(
    bundle_metadata: Mapping[str, Any] | str | Path,
) -> dict[str, Any]:
    archive = _load_retinal_inspection_archive(bundle_metadata)
    bundle_dir = archive.metadata_path.parent.resolve()
    output_dir = (bundle_dir / RETINAL_INSPECTION_DIR_NAME).resolve()
    frames_dir = output_dir / RETINAL_INSPECTION_FRAMES_DIR_NAME
    ensure_dir(frames_dir)

    source_context, source_errors = _build_source_preview_context(archive)
    qa_checks = _build_qa_checks(archive=archive, source_context=source_context, source_errors=source_errors)
    qa_summary = _summarize_checks(qa_checks)
    selected_frame_indices = _select_frame_indices(_usable_frame_count(archive))

    coverage_layout_svg_path = (output_dir / "coverage_layout.svg").resolve()
    coverage_layout_svg_path.write_text(
        _render_coverage_layout_svg(
            eye_sampling=archive.bundle_metadata["eye_sampling"],
            projector_metadata=archive.projector_metadata,
        ),
        encoding="utf-8",
    )

    selected_frames: list[dict[str, Any]] = []
    for frame_index in selected_frame_indices:
        time_ms = float(archive.frame_times_ms[frame_index])
        retinal_svg_path = (frames_dir / f"frame-{frame_index:04d}-retinal.svg").resolve()
        retinal_svg_path.write_text(
            _render_retinal_frame_svg(
                eye_sampling=archive.bundle_metadata["eye_sampling"],
                retinal_frame=archive.retinal_frames[frame_index],
            ),
            encoding="utf-8",
        )

        world_view_svg_path: Path | None = None
        world_frame_summary: dict[str, Any] | None = None
        if source_context.render_frame is not None:
            world_view_svg_path = (frames_dir / f"frame-{frame_index:04d}-world.svg").resolve()
            world_frame = source_context.render_frame(time_ms)
            preview_frame = _downsample_frame_for_preview(
                world_frame,
                max_dimension=RETINAL_INSPECTION_MAX_DIMENSION_PX,
            )
            world_view_svg_path.write_text(_render_frame_svg(preview_frame), encoding="utf-8")
            world_frame_summary = {
                "shape_y_x": [int(world_frame.shape[0]), int(world_frame.shape[1])],
                "preview_shape_y_x": [int(preview_frame.shape[0]), int(preview_frame.shape[1])],
                "mean_value": _rounded_float(float(np.mean(world_frame))),
                "min_value": _rounded_float(float(np.min(world_frame))),
                "max_value": _rounded_float(float(np.max(world_frame))),
            }

        retinal_frame = np.asarray(archive.retinal_frames[frame_index], dtype=np.float32)
        per_eye_stats = {}
        for eye_index, eye_label in enumerate(archive.bundle_metadata["eye_sampling"]["eye_order"]):
            eye_values = np.asarray(retinal_frame[eye_index], dtype=np.float32)
            per_eye_stats[eye_label] = {
                "mean_value": _rounded_float(float(np.mean(eye_values))),
                "min_value": _rounded_float(float(np.nanmin(eye_values))),
                "max_value": _rounded_float(float(np.nanmax(eye_values))),
            }
        selected_frames.append(
            {
                "frame_index": int(frame_index),
                "time_ms": _rounded_float(time_ms),
                "world_view_svg_path": str(world_view_svg_path) if world_view_svg_path is not None else None,
                "retinal_view_svg_path": str(retinal_svg_path),
                "world_view": world_frame_summary,
                "retinal_view": {
                    "shape_eye_ommatidium": [
                        int(retinal_frame.shape[0]),
                        int(retinal_frame.shape[1]),
                    ],
                    "per_eye": per_eye_stats,
                },
            }
        )

    summary_path = (output_dir / "summary.json").resolve()
    report_path = (output_dir / "index.html").resolve()
    markdown_path = (output_dir / "report.md").resolve()

    temporal_sampling = archive.bundle_metadata["temporal_sampling"]
    source_reference = archive.bundle_metadata["source_reference"]
    source_field_of_view = archive.projector_metadata.get("source_field_of_view", {})
    coverage_summary = _coverage_summary(
        eye_sampling=archive.bundle_metadata["eye_sampling"],
        projector_metadata=archive.projector_metadata,
    )
    summary = {
        "report_version": RETINAL_INSPECTION_REPORT_VERSION,
        "retinal_bundle_id": archive.bundle_metadata["bundle_id"],
        "retinal_bundle_metadata_path": str(archive.metadata_path),
        "frame_archive_path": str(archive.frame_archive_path),
        "output_dir": str(output_dir),
        "report_path": str(report_path),
        "summary_path": str(summary_path),
        "markdown_path": str(markdown_path),
        "coverage_layout_svg_path": str(coverage_layout_svg_path),
        "selected_frame_indices": selected_frame_indices,
        "selected_frame_times_ms": [
            _rounded_float(float(archive.frame_times_ms[index])) for index in selected_frame_indices
        ],
        "frame_count": int(temporal_sampling["frame_count"]),
        "source_reference": copy.deepcopy(source_reference),
        "source_preview": {
            "source_kind": source_context.source_kind,
            "source_family": source_context.source_family,
            "source_name": source_context.source_name,
            "source_hash": source_context.source_hash,
            "field_of_view": copy.deepcopy(source_context.field_of_view),
            "frame_count": source_context.frame_count,
            "frame_shape_y_x": list(source_context.frame_shape_y_x),
            "entrypoint_path": source_context.entrypoint_path,
            "details": copy.deepcopy(source_context.details),
            "available": bool(source_context.render_frame is not None),
        },
        "retinal_preview": {
            "retinal_spec_hash": archive.bundle_metadata["retinal_spec_hash"],
            "geometry_family": archive.bundle_metadata["eye_sampling"]["geometry_family"],
            "geometry_name": archive.bundle_metadata["eye_sampling"]["geometry_name"],
            "eye_order": list(archive.bundle_metadata["eye_sampling"]["eye_order"]),
            "ommatidium_count_per_eye": int(archive.bundle_metadata["eye_sampling"]["ommatidium_count_per_eye"]),
            "timing": {
                "time_origin_ms": _rounded_float(float(temporal_sampling["time_origin_ms"])),
                "dt_ms": _rounded_float(float(temporal_sampling["dt_ms"])),
                "duration_ms": _rounded_float(float(temporal_sampling["duration_ms"])),
            },
            "sampling_kernel": copy.deepcopy(archive.bundle_metadata["sampling_kernel"]),
            "source_field_of_view": copy.deepcopy(source_field_of_view),
        },
        "coverage": coverage_summary,
        "qa": qa_summary,
        "selected_frames": selected_frames,
    }

    report_path.write_text(
        _render_report_html(summary=summary, qa_checks=qa_checks),
        encoding="utf-8",
    )
    markdown_path.write_text(
        _render_report_markdown(summary=summary, qa_checks=qa_checks),
        encoding="utf-8",
    )
    write_json(summary, summary_path)
    _write_inspection_metadata(archive.bundle_metadata, summary)
    return summary


def _load_retinal_inspection_archive(
    bundle_metadata: Mapping[str, Any] | str | Path,
) -> RetinalInspectionArchive:
    normalized_metadata = (
        load_retinal_bundle_metadata(bundle_metadata)
        if not isinstance(bundle_metadata, Mapping)
        else load_retinal_bundle_metadata(Path(bundle_metadata["assets"]["metadata_json"]["path"]))
    )
    metadata_path = Path(normalized_metadata["assets"]["metadata_json"]["path"]).resolve()
    frame_archive_path = Path(normalized_metadata["assets"][FRAME_ARCHIVE_KEY]["path"]).resolve()
    load_errors: list[str] = []

    retinal_frames = np.empty((0, 0, 0), dtype=np.float32)
    early_visual_units = np.empty((0, 0, 0, 0), dtype=np.float32)
    frame_times_ms = np.empty((0,), dtype=np.float64)
    frame_metadata: list[dict[str, Any]] = []
    source_descriptor: dict[str, Any] = {}
    projector_metadata: dict[str, Any] = {}

    if not frame_archive_path.exists():
        load_errors.append(f"frame_archive_missing:{frame_archive_path}")
        return RetinalInspectionArchive(
            bundle_metadata=normalized_metadata,
            metadata_path=metadata_path,
            frame_archive_path=frame_archive_path,
            retinal_frames=retinal_frames,
            early_visual_units=early_visual_units,
            frame_times_ms=frame_times_ms,
            frame_metadata=frame_metadata,
            source_descriptor=source_descriptor,
            projector_metadata=projector_metadata,
            load_errors=tuple(load_errors),
        )

    with np.load(frame_archive_path, allow_pickle=False) as payload:
        if "retinal_frames" in payload:
            retinal_frames = np.asarray(payload["retinal_frames"], dtype=np.float32)
        else:
            load_errors.append("missing_archive_key:retinal_frames")
        if "early_visual_units" in payload:
            early_visual_units = np.asarray(payload["early_visual_units"], dtype=np.float32)
        else:
            load_errors.append("missing_archive_key:early_visual_units")
        if "frame_times_ms" in payload:
            frame_times_ms = np.asarray(payload["frame_times_ms"], dtype=np.float64)
        else:
            load_errors.append("missing_archive_key:frame_times_ms")
        frame_metadata = _parse_json_array(payload, "frame_metadata_json", load_errors)
        source_descriptor = _parse_json_mapping(payload, "source_descriptor_json", load_errors)
        projector_metadata = _parse_json_mapping(payload, "projector_metadata_json", load_errors)

    return RetinalInspectionArchive(
        bundle_metadata=normalized_metadata,
        metadata_path=metadata_path,
        frame_archive_path=frame_archive_path,
        retinal_frames=retinal_frames,
        early_visual_units=early_visual_units,
        frame_times_ms=frame_times_ms,
        frame_metadata=frame_metadata,
        source_descriptor=source_descriptor,
        projector_metadata=projector_metadata,
        load_errors=tuple(load_errors),
    )


def _parse_json_array(payload: Any, key: str, load_errors: list[str]) -> list[dict[str, Any]]:
    if key not in payload:
        load_errors.append(f"missing_archive_key:{key}")
        return []
    try:
        value = json.loads(str(payload[key].item()))
    except Exception as exc:
        load_errors.append(f"invalid_json:{key}:{exc}")
        return []
    if not isinstance(value, list):
        load_errors.append(f"invalid_json_type:{key}:list")
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _parse_json_mapping(payload: Any, key: str, load_errors: list[str]) -> dict[str, Any]:
    if key not in payload:
        load_errors.append(f"missing_archive_key:{key}")
        return {}
    try:
        value = json.loads(str(payload[key].item()))
    except Exception as exc:
        load_errors.append(f"invalid_json:{key}:{exc}")
        return {}
    if not isinstance(value, Mapping):
        load_errors.append(f"invalid_json_type:{key}:mapping")
        return {}
    return copy.deepcopy(dict(value))


def _build_source_preview_context(
    archive: RetinalInspectionArchive,
) -> tuple[SourcePreviewContext, list[str]]:
    source_reference = archive.bundle_metadata["source_reference"]
    source_kind = str(source_reference["source_kind"])
    errors: list[str] = []
    field_of_view = copy.deepcopy(archive.projector_metadata.get("source_field_of_view", {}))
    if source_kind == "stimulus_bundle":
        lineage = archive.source_descriptor.get("source_metadata", {}).get("lineage", {})
        upstream_path_value = lineage.get("upstream_bundle_metadata_path")
        if not isinstance(upstream_path_value, str) or not upstream_path_value:
            errors.append("missing_upstream_stimulus_bundle_metadata_path")
            return (
                SourcePreviewContext(
                    source_kind=source_kind,
                    source_family=str(source_reference["source_family"]),
                    source_name=str(source_reference["source_name"]),
                    source_hash=str(source_reference["source_hash"]),
                    field_of_view=field_of_view,
                    frame_count=None,
                    frame_shape_y_x=[],
                    entrypoint_path=None,
                    details={"lineage": copy.deepcopy(lineage)},
                    render_frame=None,
                ),
                errors,
            )
        upstream_path = Path(upstream_path_value).resolve()
        if not upstream_path.exists():
            errors.append(f"missing_upstream_stimulus_bundle:{upstream_path}")
            return (
                SourcePreviewContext(
                    source_kind=source_kind,
                    source_family=str(source_reference["source_family"]),
                    source_name=str(source_reference["source_name"]),
                    source_hash=str(source_reference["source_hash"]),
                    field_of_view=field_of_view,
                    frame_count=None,
                    frame_shape_y_x=[],
                    entrypoint_path=str(upstream_path),
                    details={"lineage": copy.deepcopy(lineage)},
                    render_frame=None,
                ),
                errors,
            )
        stimulus_replay = load_recorded_stimulus_bundle(upstream_path)
        return (
            SourcePreviewContext(
                source_kind=source_kind,
                source_family=str(source_reference["source_family"]),
                source_name=str(source_reference["source_name"]),
                source_hash=str(source_reference["source_hash"]),
                field_of_view=field_of_view,
                frame_count=int(stimulus_replay.frames.shape[0]),
                frame_shape_y_x=[int(stimulus_replay.frames.shape[1]), int(stimulus_replay.frames.shape[2])],
                entrypoint_path=str(upstream_path),
                details={
                    "upstream_bundle_id": stimulus_replay.bundle_metadata["bundle_id"],
                    "upstream_replay_source": stimulus_replay.replay_source,
                },
                render_frame=lambda time_ms: np.asarray(
                    stimulus_replay.frame_at_time_ms(time_ms),
                    dtype=np.float32,
                ),
            ),
            errors,
        )

    if source_kind == "scene_description":
        scene_spec = archive.source_descriptor.get("source_metadata", {}).get("scene_spec")
        if not isinstance(scene_spec, Mapping):
            errors.append("missing_scene_spec_for_source_preview")
            return (
                SourcePreviewContext(
                    source_kind=source_kind,
                    source_family=str(source_reference["source_family"]),
                    source_name=str(source_reference["source_name"]),
                    source_hash=str(source_reference["source_hash"]),
                    field_of_view=field_of_view,
                    frame_count=None,
                    frame_shape_y_x=[],
                    entrypoint_path=archive.source_descriptor.get("source_metadata", {}).get("lineage", {}).get("scene_path"),
                    details={},
                    render_frame=None,
                ),
                errors,
            )
        resolved_scene = resolve_scene_spec(scene_spec)
        if not field_of_view:
            field_of_view = _build_rectangular_field_of_view_from_width_height(
                width_deg=float(resolved_scene.visual_field["width_deg"]),
                height_deg=float(resolved_scene.visual_field["height_deg"]),
            )
        preview_shape = _scene_preview_shape(field_of_view=field_of_view)
        return (
            SourcePreviewContext(
                source_kind=source_kind,
                source_family=str(source_reference["source_family"]),
                source_name=str(source_reference["source_name"]),
                source_hash=str(source_reference["source_hash"]),
                field_of_view=field_of_view,
                frame_count=int(resolved_scene.frame_times_ms.size),
                frame_shape_y_x=[preview_shape[0], preview_shape[1]],
                entrypoint_path=archive.source_descriptor.get("source_metadata", {}).get("lineage", {}).get("scene_path"),
                details={"scene_hash": resolved_scene.scene_hash},
                render_frame=lambda time_ms: _sample_scene_preview_frame(
                    resolved_scene.scene_spec,
                    time_ms=time_ms,
                    field_of_view=field_of_view,
                    frame_shape_y_x=preview_shape,
                ),
            ),
            errors,
        )

    errors.append(f"unsupported_source_kind:{source_kind}")
    return (
        SourcePreviewContext(
            source_kind=source_kind,
            source_family=str(source_reference["source_family"]),
            source_name=str(source_reference["source_name"]),
            source_hash=str(source_reference["source_hash"]),
            field_of_view=field_of_view,
            frame_count=None,
            frame_shape_y_x=[],
            entrypoint_path=None,
            details={},
            render_frame=None,
        ),
        errors,
    )


def _scene_preview_shape(*, field_of_view: Mapping[str, Any]) -> tuple[int, int]:
    width_deg = float(field_of_view.get("width_deg", 360.0))
    height_deg = float(field_of_view.get("height_deg", 180.0))
    width_px = DEFAULT_SCENE_PREVIEW_WIDTH_PX
    height_px = max(16, int(round(width_px * (height_deg / max(width_deg, _FLOAT_ABS_TOL)))))
    return height_px, width_px


def _sample_scene_preview_frame(
    scene_spec: Mapping[str, Any],
    *,
    time_ms: float,
    field_of_view: Mapping[str, Any],
    frame_shape_y_x: list[int] | tuple[int, int],
) -> np.ndarray:
    height_px, width_px = [int(value) for value in frame_shape_y_x]
    x_coordinates_deg = np.linspace(
        float(field_of_view["azimuth_range_deg"][0]),
        float(field_of_view["azimuth_range_deg"][1]),
        width_px,
        endpoint=False,
        dtype=np.float64,
    )
    y_coordinates_deg = np.linspace(
        float(field_of_view["elevation_range_deg"][1]),
        float(field_of_view["elevation_range_deg"][0]),
        height_px,
        endpoint=False,
        dtype=np.float64,
    )
    sampled = sample_scene_field(
        scene_spec,
        time_ms=float(time_ms),
        azimuth_deg=x_coordinates_deg[None, :],
        elevation_deg=y_coordinates_deg[:, None],
    )
    return np.asarray(sampled, dtype=np.float32)


def _build_rectangular_field_of_view_from_width_height(
    *,
    width_deg: float,
    height_deg: float,
) -> dict[str, Any]:
    return {
        "width_deg": _rounded_float(float(width_deg)),
        "height_deg": _rounded_float(float(height_deg)),
        "azimuth_range_deg": [
            _rounded_float(-float(width_deg) * 0.5),
            _rounded_float(float(width_deg) * 0.5),
        ],
        "elevation_range_deg": [
            _rounded_float(-float(height_deg) * 0.5),
            _rounded_float(float(height_deg) * 0.5),
        ],
    }


def _build_qa_checks(
    *,
    archive: RetinalInspectionArchive,
    source_context: SourcePreviewContext,
    source_errors: list[str],
) -> list[dict[str, Any]]:
    temporal_sampling = archive.bundle_metadata["temporal_sampling"]
    eye_sampling = archive.bundle_metadata["eye_sampling"]
    frame_layout = archive.bundle_metadata["frame_layout"]
    simulator_input = archive.bundle_metadata["simulator_input"]

    expected_frame_count = int(temporal_sampling["frame_count"])
    expected_retinal_shape = (
        expected_frame_count,
        len(frame_layout["eye_axis_labels"]),
        int(frame_layout["ommatidium_count_per_eye"]),
    )
    expected_early_visual_shape = (
        expected_frame_count,
        len(simulator_input["eye_axis_labels"]),
        int(simulator_input["unit_count_per_eye"]),
        int(simulator_input["channel_count"]),
    )

    checks = [
        _make_check(
            "archive_load",
            STATUS_FAIL if archive.load_errors else STATUS_PASS,
            "The retinal frame archive and its required JSON sidecars should load cleanly.",
            value=list(archive.load_errors),
            blocking=True,
        ),
        _make_check(
            "retinal_frame_shape",
            STATUS_PASS if tuple(archive.retinal_frames.shape) == expected_retinal_shape else STATUS_FAIL,
            "The stored retinal frame tensor should match the bundle timing, eye order, and ommatidium count.",
            value={
                "expected": list(expected_retinal_shape),
                "actual": list(archive.retinal_frames.shape),
            },
            blocking=True,
        ),
        _make_check(
            "early_visual_shape",
            STATUS_PASS if tuple(archive.early_visual_units.shape) == expected_early_visual_shape else STATUS_FAIL,
            "The simulator-facing early-visual stack should stay aligned with the recorded retinal bundle.",
            value={
                "expected": list(expected_early_visual_shape),
                "actual": list(archive.early_visual_units.shape),
            },
            blocking=True,
        ),
        _make_check(
            "frame_times",
            STATUS_PASS if _frame_times_match(archive.frame_times_ms, temporal_sampling) else STATUS_FAIL,
            "The archive frame timeline should match the canonical sample-hold timing grid.",
            value={
                "expected_frame_count": expected_frame_count,
                "actual_frame_time_count": int(archive.frame_times_ms.size),
            },
            blocking=True,
        ),
        _make_check(
            "frame_metadata_count",
            STATUS_PASS if len(archive.frame_metadata) == expected_frame_count else STATUS_FAIL,
            "Each recorded retinal frame should carry one frame-metadata entry.",
            value={
                "expected": expected_frame_count,
                "actual": len(archive.frame_metadata),
            },
            blocking=True,
        ),
        _make_check(
            "detector_values_finite",
            STATUS_PASS if _array_all_finite(archive.retinal_frames) else STATUS_FAIL,
            "Recorded detector values must remain finite for offline inspection and simulator handoff.",
            value=_array_extrema_payload(archive.retinal_frames),
            blocking=True,
        ),
        _make_check(
            "detector_values_unit_interval",
            STATUS_PASS if _array_in_unit_interval(archive.retinal_frames) else STATUS_FAIL,
            "Recorded detector values should stay inside the canonical irradiance range [0.0, 1.0].",
            value=_array_extrema_payload(archive.retinal_frames),
            blocking=True,
        ),
        _make_check(
            "source_preview_available",
            STATUS_PASS if source_context.render_frame is not None else STATUS_FAIL,
            "The report should be able to reconstruct a reviewable world-view frame from local source artifacts.",
            value=list(source_errors),
            blocking=False,
        ),
        _make_check(
            "source_timeline",
            _source_timeline_status(source_context=source_context, expected_frame_count=expected_frame_count),
            "The world-view source should expose the same frame count as the retinal recording timeline.",
            value={
                "expected_frame_count": expected_frame_count,
                "source_frame_count": source_context.frame_count,
            },
            blocking=False,
        ),
        _coverage_check(eye_sampling=eye_sampling, projector_metadata=archive.projector_metadata),
    ]
    return checks


def _coverage_check(
    *,
    eye_sampling: Mapping[str, Any],
    projector_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    coverage = _coverage_summary(eye_sampling=eye_sampling, projector_metadata=projector_metadata)
    overall_status = str(coverage["overall_status"])
    if overall_status == STATUS_UNKNOWN:
        overall_status = STATUS_FAIL
    return _make_check(
        "detector_coverage",
        overall_status,
        "Detector support should cover the world-view source without fully missing ommatidia; clipped support should stay reviewable.",
        value={"per_eye": coverage["per_eye"]},
        blocking=False,
    )


def _summarize_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = {
        STATUS_PASS: sum(1 for check in checks if check["status"] == STATUS_PASS),
        STATUS_WARN: sum(1 for check in checks if check["status"] == STATUS_WARN),
        STATUS_FAIL: sum(1 for check in checks if check["status"] == STATUS_FAIL),
    }
    overall_status = STATUS_PASS
    for candidate in (STATUS_FAIL, STATUS_WARN):
        if status_counts[candidate] > 0:
            overall_status = candidate
            break
    blocking_failure_count = sum(
        1 for check in checks if check["blocking"] and check["status"] == STATUS_FAIL
    )
    return {
        "overall_status": overall_status,
        "status_counts": status_counts,
        "blocking_failure_count": blocking_failure_count,
        "checks": copy.deepcopy(checks),
    }


def _coverage_summary(
    *,
    eye_sampling: Mapping[str, Any],
    projector_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    detector_count = int(eye_sampling["ommatidium_count_per_eye"])
    per_eye_projection = projector_metadata.get("per_eye_projection")
    if not isinstance(per_eye_projection, Mapping):
        return {
            "overall_status": STATUS_UNKNOWN,
            "per_eye": {},
        }

    per_eye: dict[str, Any] = {}
    overall_status = STATUS_PASS
    for eye_label in eye_sampling["eye_order"]:
        projection = per_eye_projection.get(eye_label)
        if not isinstance(projection, Mapping):
            per_eye[str(eye_label)] = {"status": STATUS_UNKNOWN}
            overall_status = _combine_status(overall_status, STATUS_FAIL)
            continue
        fully_out_of_field = int(projection.get("fully_out_of_field_detector_count", detector_count))
        partially_clipped = int(projection.get("partially_clipped_detector_count", 0))
        fully_in_field = int(projection.get("fully_in_field_detector_count", 0))
        if fully_out_of_field > 0:
            status = STATUS_FAIL
        elif partially_clipped > 0:
            status = STATUS_WARN
        else:
            status = STATUS_PASS
        overall_status = _combine_status(overall_status, status)
        per_eye[str(eye_label)] = {
            "status": status,
            "detector_count": detector_count,
            "fully_in_field_detector_count": fully_in_field,
            "partially_clipped_detector_count": partially_clipped,
            "fully_out_of_field_detector_count": fully_out_of_field,
            "coverage_fraction": _rounded_float(
                (detector_count - fully_out_of_field) / max(detector_count, 1)
            ),
        }
    return {
        "overall_status": overall_status,
        "per_eye": per_eye,
    }


def _make_check(
    name: str,
    status: str,
    description: str,
    *,
    value: Any,
    blocking: bool,
) -> dict[str, Any]:
    return {
        "name": str(name),
        "status": str(status),
        "description": str(description),
        "blocking": bool(blocking),
        "value": value,
    }


def _source_timeline_status(*, source_context: SourcePreviewContext, expected_frame_count: int) -> str:
    if source_context.frame_count is None:
        return STATUS_WARN
    return STATUS_PASS if int(source_context.frame_count) == int(expected_frame_count) else STATUS_FAIL


def _usable_frame_count(archive: RetinalInspectionArchive) -> int:
    if archive.retinal_frames.ndim != 3:
        return 0
    return int(min(archive.retinal_frames.shape[0], archive.frame_times_ms.size))


def _select_frame_indices(frame_count: int) -> list[int]:
    if frame_count <= 0:
        return []
    if frame_count <= 3:
        return list(range(frame_count))
    candidates = [0, frame_count // 3, (2 * frame_count) // 3, frame_count - 1]
    selected: list[int] = []
    seen: set[int] = set()
    for candidate in candidates:
        bounded = int(np.clip(candidate, 0, frame_count - 1))
        if bounded not in seen:
            selected.append(bounded)
            seen.add(bounded)
    return selected


def _frame_times_match(frame_times_ms: np.ndarray, temporal_sampling: Mapping[str, Any]) -> bool:
    expected_frame_count = int(temporal_sampling["frame_count"])
    if frame_times_ms.shape != (expected_frame_count,):
        return False
    expected_times = float(temporal_sampling["time_origin_ms"]) + np.arange(
        expected_frame_count,
        dtype=np.float64,
    ) * float(temporal_sampling["dt_ms"])
    return bool(np.allclose(frame_times_ms, expected_times, atol=_FLOAT_ABS_TOL, rtol=0.0))


def _array_all_finite(array: np.ndarray) -> bool:
    return bool(array.size > 0 and np.all(np.isfinite(array)))


def _array_in_unit_interval(array: np.ndarray) -> bool:
    if array.size == 0 or not np.all(np.isfinite(array)):
        return False
    return bool(np.min(array) >= -_FLOAT_ABS_TOL and np.max(array) <= 1.0 + _FLOAT_ABS_TOL)


def _array_extrema_payload(array: np.ndarray) -> dict[str, Any]:
    if array.size == 0:
        return {"array_present": False}
    finite_mask = np.isfinite(array)
    payload = {
        "array_present": True,
        "shape": list(array.shape),
        "finite_fraction": _rounded_float(float(np.mean(finite_mask))),
    }
    if np.any(finite_mask):
        finite_values = array[finite_mask]
        payload["min_value"] = _rounded_float(float(np.min(finite_values)))
        payload["max_value"] = _rounded_float(float(np.max(finite_values)))
    return payload


def _render_report_html(*, summary: Mapping[str, Any], qa_checks: list[dict[str, Any]]) -> str:
    check_rows = "\n".join(_render_check_row_html(check) for check in qa_checks)
    frame_cards = "\n".join(_render_frame_card_html(frame_record) for frame_record in summary["selected_frames"])
    source_preview = summary["source_preview"]
    retinal_preview = summary["retinal_preview"]
    coverage = summary["coverage"]
    qa = summary["qa"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Offline Retinal Inspection</title>
  <style>
    body {{
      font-family: sans-serif;
      margin: 2rem;
      background: #f8fafc;
      color: #0f172a;
    }}
    main {{
      max-width: 1200px;
      margin: 0 auto;
    }}
    h1, h2, h3 {{
      margin-bottom: 0.4rem;
    }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 0.75rem;
      margin: 1.25rem 0;
    }}
    .card {{
      background: white;
      border: 1px solid #cbd5e1;
      border-radius: 12px;
      padding: 1rem;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
    }}
    .status-pill {{
      display: inline-block;
      padding: 0.2rem 0.55rem;
      border-radius: 999px;
      font-size: 0.9rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      background: {html.escape(_status_background_color(qa["overall_status"]))};
      color: white;
    }}
    .checks {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 0.75rem;
      background: white;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
    }}
    .checks th, .checks td {{
      border: 1px solid #e2e8f0;
      padding: 0.65rem 0.75rem;
      text-align: left;
      vertical-align: top;
    }}
    .frames {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 1rem;
      margin-top: 1rem;
    }}
    img {{
      width: 100%;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      background: #f1f5f9;
    }}
    code {{
      font-family: monospace;
      font-size: 0.95em;
      word-break: break-all;
    }}
    dl {{
      margin: 0;
    }}
    dt {{
      font-weight: 700;
      margin-top: 0.4rem;
    }}
    dd {{
      margin: 0.1rem 0 0;
    }}
    .layout {{
      margin-top: 1rem;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Offline Retinal Inspection</h1>
    <p><code>{html.escape(str(summary["retinal_bundle_id"]))}</code></p>
    <p><span class="status-pill">{html.escape(str(qa["overall_status"]))}</span></p>
    <div class="meta">
      <section class="card">
        <h2>World View</h2>
        <dl>
          <dt>Source kind</dt>
          <dd>{html.escape(str(source_preview["source_kind"]))}</dd>
          <dt>Source family</dt>
          <dd>{html.escape(str(source_preview["source_family"]))}</dd>
          <dt>Source name</dt>
          <dd>{html.escape(str(source_preview["source_name"]))}</dd>
          <dt>Field of view</dt>
          <dd>{_field_of_view_text(source_preview["field_of_view"])}</dd>
        </dl>
      </section>
      <section class="card">
        <h2>Fly View</h2>
        <dl>
          <dt>Geometry</dt>
          <dd>{html.escape(str(retinal_preview["geometry_family"]))} / {html.escape(str(retinal_preview["geometry_name"]))}</dd>
          <dt>Eye order</dt>
          <dd>{html.escape(", ".join(retinal_preview["eye_order"]))}</dd>
          <dt>Detectors per eye</dt>
          <dd>{int(retinal_preview["ommatidium_count_per_eye"])}</dd>
          <dt>Retinal spec hash</dt>
          <dd><code>{html.escape(str(retinal_preview["retinal_spec_hash"]))}</code></dd>
        </dl>
      </section>
      <section class="card">
        <h2>Timing</h2>
        <dl>
          <dt>Frame count</dt>
          <dd>{int(summary["frame_count"])}</dd>
          <dt>dt</dt>
          <dd>{float(retinal_preview["timing"]["dt_ms"]):.6f} ms</dd>
          <dt>Duration</dt>
          <dd>{float(retinal_preview["timing"]["duration_ms"]):.6f} ms</dd>
          <dt>Selected frames</dt>
          <dd>{html.escape(", ".join(str(index) for index in summary["selected_frame_indices"]))}</dd>
        </dl>
      </section>
      <section class="card">
        <h2>Coverage</h2>
        <dl>
          <dt>Overall</dt>
          <dd>{html.escape(str(coverage["overall_status"]))}</dd>
          <dt>Left</dt>
          <dd>{html.escape(str(coverage["per_eye"].get("left", {}).get("status", STATUS_UNKNOWN)))}</dd>
          <dt>Right</dt>
          <dd>{html.escape(str(coverage["per_eye"].get("right", {}).get("status", STATUS_UNKNOWN)))}</dd>
        </dl>
      </section>
    </div>
    <section>
      <h2>QA Checks</h2>
      <table class="checks">
        <thead>
          <tr>
            <th>Check</th>
            <th>Status</th>
            <th>Meaning</th>
            <th>Observed</th>
          </tr>
        </thead>
        <tbody>
          {check_rows}
        </tbody>
      </table>
    </section>
    <section class="layout">
      <h2>Detector Coverage and Lattice Layout</h2>
      <img src="{html.escape(Path(summary["coverage_layout_svg_path"]).name)}" alt="Detector coverage and lattice layout">
    </section>
    <section>
      <h2>Representative Frames</h2>
      <div class="frames">
        {frame_cards}
      </div>
    </section>
  </main>
</body>
</html>
"""


def _render_check_row_html(check: Mapping[str, Any]) -> str:
    value_text = html.escape(json.dumps(check["value"], sort_keys=True))
    return f"""
<tr>
  <td><code>{html.escape(str(check["name"]))}</code></td>
  <td>{html.escape(str(check["status"]))}</td>
  <td>{html.escape(str(check["description"]))}</td>
  <td><code>{value_text}</code></td>
</tr>
"""


def _render_frame_card_html(frame_record: Mapping[str, Any]) -> str:
    world_markup = "<p>World-view preview unavailable.</p>"
    if frame_record["world_view_svg_path"] is not None:
        relative_world_path = f"{RETINAL_INSPECTION_FRAMES_DIR_NAME}/{Path(frame_record['world_view_svg_path']).name}"
        world_markup = (
            f'<img src="{html.escape(relative_world_path)}" '
            f'alt="World-view frame {int(frame_record["frame_index"])}">'
        )
    relative_retinal_path = (
        f"{RETINAL_INSPECTION_FRAMES_DIR_NAME}/{Path(frame_record['retinal_view_svg_path']).name}"
    )
    return f"""
<article class="card">
  <h3>Frame {int(frame_record["frame_index"])}</h3>
  <p>{float(frame_record["time_ms"]):.6f} ms</p>
  <h4>World View</h4>
  {world_markup}
  <h4>Fly View</h4>
  <img src="{html.escape(relative_retinal_path)}" alt="Retinal frame {int(frame_record["frame_index"])}">
</article>
"""


def _render_report_markdown(*, summary: Mapping[str, Any], qa_checks: list[dict[str, Any]]) -> str:
    lines = [
        "# Offline Retinal Inspection",
        "",
        f"Bundle: `{summary['retinal_bundle_id']}`",
        "",
        f"Overall QA status: `{summary['qa']['overall_status']}`",
        "",
        "## What To Review",
        "",
        "- Confirm the world-view preview and the sampled fly-view change in ways that agree with the source motion or scene structure.",
        "- Use the detector coverage layout to spot fully missing ommatidia or broad clipped regions before simulator/UI integration.",
        "- Treat `fail` on detector values, frame counts, or timing as a bundle integrity problem, not a cosmetic preview issue.",
        "",
        "## QA Checks",
        "",
    ]
    for check in qa_checks:
        lines.append(
            f"- `{check['name']}`: `{check['status']}`. {check['description']} "
            f"Observed: `{json.dumps(check['value'], sort_keys=True)}`"
        )
    lines.extend(
        [
            "",
            "## Coverage Layout",
            "",
            f"![]({Path(summary['coverage_layout_svg_path']).name})",
            "",
            "## Representative Frames",
            "",
        ]
    )
    for frame_record in summary["selected_frames"]:
        lines.extend(
            [
                f"### Frame {int(frame_record['frame_index'])} at {float(frame_record['time_ms']):.6f} ms",
                "",
            ]
        )
        if frame_record["world_view_svg_path"] is not None:
            lines.append(
                f"World view: ![]({RETINAL_INSPECTION_FRAMES_DIR_NAME}/{Path(frame_record['world_view_svg_path']).name})"
            )
            lines.append("")
        lines.append(
            f"Fly view: ![]({RETINAL_INSPECTION_FRAMES_DIR_NAME}/{Path(frame_record['retinal_view_svg_path']).name})"
        )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_coverage_layout_svg(
    *,
    eye_sampling: Mapping[str, Any],
    projector_metadata: Mapping[str, Any],
) -> str:
    per_eye_projection = projector_metadata.get("per_eye_projection", {})
    eye_order = list(eye_sampling["eye_order"])
    view_box_width = int(len(eye_order) * (RETINAL_PANEL_WIDTH_PX + 40))
    view_box_height = int(RETINAL_PANEL_HEIGHT_PX + 70)
    groups = []
    for eye_index, eye_label in enumerate(eye_order):
        panel_x = float(eye_index * (RETINAL_PANEL_WIDTH_PX + 40))
        detector_table = eye_sampling["per_eye"][eye_label]["detector_table"]
        coverage_mapping = per_eye_projection.get(eye_label, {})
        fully_out = {
            int(index) for index in coverage_mapping.get("fully_out_of_field_ommatidia", [])
        }
        partially_clipped = {
            int(index) for index in coverage_mapping.get("partially_clipped_ommatidia", [])
        }
        groups.append(
            _render_lattice_panel(
                title=f"{eye_label.title()} eye",
                detector_table=detector_table,
                panel_x=panel_x,
                value_lookup=lambda ommatidium_index: _coverage_fill_color(
                    ommatidium_index=ommatidium_index,
                    fully_out=fully_out,
                    partially_clipped=partially_clipped,
                ),
                show_labels=True,
            )
        )
    legend = """
      <g transform="translate(12, {legend_y})">
        <circle cx="8" cy="8" r="6" fill="#0f766e" stroke="#0f172a" stroke-width="1"/>
        <text x="20" y="12" font-size="12" fill="#0f172a">fully in field</text>
        <circle cx="138" cy="8" r="6" fill="#d97706" stroke="#0f172a" stroke-width="1"/>
        <text x="150" y="12" font-size="12" fill="#0f172a">clipped support</text>
        <circle cx="266" cy="8" r="6" fill="#b91c1c" stroke="#0f172a" stroke-width="1"/>
        <text x="278" y="12" font-size="12" fill="#0f172a">missing coverage</text>
      </g>
    """.format(legend_y=RETINAL_PANEL_HEIGHT_PX + 28)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view_box_width} {view_box_height}" '
        f'width="{view_box_width}" height="{view_box_height}">\n'
        f'<rect x="0" y="0" width="{view_box_width}" height="{view_box_height}" fill="#f8fafc"/>\n'
        f'{"".join(groups)}\n{legend}\n'
        "</svg>\n"
    )


def _render_retinal_frame_svg(
    *,
    eye_sampling: Mapping[str, Any],
    retinal_frame: np.ndarray,
) -> str:
    eye_order = list(eye_sampling["eye_order"])
    view_box_width = int(len(eye_order) * (RETINAL_PANEL_WIDTH_PX + 40))
    view_box_height = int(RETINAL_PANEL_HEIGHT_PX + 30)
    groups = []
    for eye_index, eye_label in enumerate(eye_order):
        panel_x = float(eye_index * (RETINAL_PANEL_WIDTH_PX + 40))
        detector_table = eye_sampling["per_eye"][eye_label]["detector_table"]
        eye_values = np.asarray(retinal_frame[eye_index], dtype=np.float32)
        groups.append(
            _render_lattice_panel(
                title=f"{eye_label.title()} eye",
                detector_table=detector_table,
                panel_x=panel_x,
                value_lookup=lambda ommatidium_index, eye_values=eye_values: _irradiance_fill_color(
                    float(eye_values[ommatidium_index])
                ),
                show_labels=False,
            )
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view_box_width} {view_box_height}" '
        f'width="{view_box_width}" height="{view_box_height}">\n'
        f'<rect x="0" y="0" width="{view_box_width}" height="{view_box_height}" fill="#f8fafc"/>\n'
        f'{"".join(groups)}\n'
        "</svg>\n"
    )


def _render_lattice_panel(
    *,
    title: str,
    detector_table: list[dict[str, Any]],
    panel_x: float,
    value_lookup: Callable[[int], str],
    show_labels: bool,
) -> str:
    azimuths = np.asarray(
        [float(detector["lattice_local_azimuth_deg"]) for detector in detector_table],
        dtype=np.float64,
    )
    elevations = np.asarray(
        [float(detector["lattice_local_elevation_deg"]) for detector in detector_table],
        dtype=np.float64,
    )
    x_min, x_max = _expanded_bounds(azimuths)
    y_min, y_max = _expanded_bounds(elevations)
    panel_markup = [
        f'<g transform="translate({panel_x},0)">',
        f'<rect x="0" y="0" width="{RETINAL_PANEL_WIDTH_PX}" height="{RETINAL_PANEL_HEIGHT_PX}" '
        'fill="white" stroke="#cbd5e1" rx="10" ry="10"/>',
        f'<text x="{RETINAL_PANEL_WIDTH_PX / 2:.1f}" y="18" text-anchor="middle" '
        'font-size="13" font-weight="700" fill="#0f172a">'
        f"{html.escape(title)}</text>",
    ]
    for detector in detector_table:
        ommatidium_index = int(detector["ommatidium_index"])
        cx = _scale_to_panel(
            float(detector["lattice_local_azimuth_deg"]),
            x_min,
            x_max,
            RETINAL_PANEL_PADDING_PX,
            RETINAL_PANEL_WIDTH_PX - RETINAL_PANEL_PADDING_PX,
        )
        cy = _scale_to_panel(
            float(detector["lattice_local_elevation_deg"]),
            y_max,
            y_min,
            RETINAL_PANEL_PADDING_PX + 12.0,
            RETINAL_PANEL_HEIGHT_PX - RETINAL_PANEL_PADDING_PX,
        )
        panel_markup.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="8" fill="{value_lookup(ommatidium_index)}" '
            'stroke="#0f172a" stroke-width="1"/>'
        )
        if show_labels:
            panel_markup.append(
                f'<text x="{cx:.2f}" y="{cy + 3.5:.2f}" text-anchor="middle" '
                f'font-size="{RETINAL_LATTICE_LABEL_FONT_SIZE_PX}" fill="white">{ommatidium_index}</text>'
            )
    panel_markup.append("</g>")
    return "\n".join(panel_markup)


def _expanded_bounds(values: np.ndarray) -> tuple[float, float]:
    if values.size == 0:
        return -1.0, 1.0
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    if math.isclose(minimum, maximum, abs_tol=_FLOAT_ABS_TOL):
        return minimum - 1.0, maximum + 1.0
    padding = max(1.0, 0.08 * (maximum - minimum))
    return minimum - padding, maximum + padding


def _scale_to_panel(
    value: float,
    source_min: float,
    source_max: float,
    target_min: float,
    target_max: float,
) -> float:
    span = max(source_max - source_min, _FLOAT_ABS_TOL)
    fraction = (value - source_min) / span
    return target_min + fraction * (target_max - target_min)


def _coverage_fill_color(
    *,
    ommatidium_index: int,
    fully_out: set[int],
    partially_clipped: set[int],
) -> str:
    if ommatidium_index in fully_out:
        return _COVERAGE_STATUS_COLORS[STATUS_FAIL]
    if ommatidium_index in partially_clipped:
        return _COVERAGE_STATUS_COLORS[STATUS_WARN]
    return _COVERAGE_STATUS_COLORS[STATUS_PASS]


def _irradiance_fill_color(value: float) -> str:
    if not math.isfinite(value):
        return "#dc2626"
    clipped = max(0.0, min(1.0, float(value)))
    level = int(round(clipped * 255.0))
    return f"rgb({level},{level},{level})"


def _downsample_frame_for_preview(frame: np.ndarray, *, max_dimension: int) -> np.ndarray:
    if frame.ndim != 2:
        raise ValueError("Preview frame must be a 2D array.")
    height, width = frame.shape
    scale = max(1, int(math.ceil(max(height, width) / max_dimension)))
    if scale == 1:
        return np.asarray(frame, dtype=np.float32)
    padded_height = int(math.ceil(height / scale) * scale)
    padded_width = int(math.ceil(width / scale) * scale)
    padded = np.pad(
        np.asarray(frame, dtype=np.float32),
        ((0, padded_height - height), (0, padded_width - width)),
        mode="edge",
    )
    reshaped = padded.reshape(padded_height // scale, scale, padded_width // scale, scale)
    return reshaped.mean(axis=(1, 3), dtype=np.float32)


def _render_frame_svg(frame: np.ndarray) -> str:
    height, width = frame.shape
    rects: list[str] = []
    for y_index in range(height):
        for x_index in range(width):
            luminance = int(round(float(np.clip(frame[y_index, x_index], 0.0, 1.0)) * 255.0))
            rects.append(
                f'<rect x="{x_index * RETINAL_INSPECTION_CELL_SIZE_PX}" '
                f'y="{y_index * RETINAL_INSPECTION_CELL_SIZE_PX}" '
                f'width="{RETINAL_INSPECTION_CELL_SIZE_PX}" '
                f'height="{RETINAL_INSPECTION_CELL_SIZE_PX}" '
                f'fill="rgb({luminance},{luminance},{luminance})" />'
            )
    width_px = width * RETINAL_INSPECTION_CELL_SIZE_PX
    height_px = height * RETINAL_INSPECTION_CELL_SIZE_PX
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width_px} {height_px}" '
        f'width="{width_px}" height="{height_px}" shape-rendering="crispEdges">\n'
        f'{"".join(rects)}\n'
        "</svg>\n"
    )


def _write_inspection_metadata(bundle_metadata: Mapping[str, Any], summary: Mapping[str, Any]) -> None:
    updated_metadata = copy.deepcopy(dict(bundle_metadata))
    updated_metadata["inspection"] = {
        "inspection_version": RETINAL_INSPECTION_REPORT_VERSION,
        "output_dir": summary["output_dir"],
        "report_path": summary["report_path"],
        "summary_path": summary["summary_path"],
        "markdown_path": summary["markdown_path"],
        "coverage_layout_svg_path": summary["coverage_layout_svg_path"],
        "selected_frame_indices": list(summary["selected_frame_indices"]),
        "selected_frame_times_ms": list(summary["selected_frame_times_ms"]),
        "overall_status": summary["qa"]["overall_status"],
    }
    write_retinal_bundle_metadata(updated_metadata)


def _status_background_color(status: str) -> str:
    return _COVERAGE_STATUS_COLORS.get(status, "#64748b")


def _field_of_view_text(field_of_view: Mapping[str, Any]) -> str:
    if not isinstance(field_of_view, Mapping) or not field_of_view:
        return "unavailable"
    width_deg = field_of_view.get("width_deg")
    height_deg = field_of_view.get("height_deg")
    if width_deg is None or height_deg is None:
        return html.escape(json.dumps(field_of_view, sort_keys=True))
    return f"{float(width_deg):.3f} x {float(height_deg):.3f} deg"


def _combine_status(left: str, right: str) -> str:
    if left not in STATUS_RANK:
        return right
    if right not in STATUS_RANK:
        return left
    return left if STATUS_RANK[left] >= STATUS_RANK[right] else right


def _rounded_float(value: float) -> float:
    return round(float(value), 12)
