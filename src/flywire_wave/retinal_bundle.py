from __future__ import annotations

import copy
import io
import json
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .retinal_contract import (
    ASSET_STATUS_READY,
    DEFAULT_CHANNEL_NAME,
    DEFAULT_PROCESSED_RETINAL_DIR,
    FRAME_ARCHIVE_KEY,
    DEFAULT_FRAME_ARCHIVE_FORMAT,
    DEFAULT_SIGNAL_MAXIMUM_VALUE,
    DEFAULT_SIGNAL_MINIMUM_VALUE,
    build_retinal_bundle_metadata,
    build_retinal_source_reference_from_descriptor,
    load_retinal_bundle_metadata,
    parse_retinal_bundle_metadata,
    write_retinal_bundle_metadata,
)
from .retinal_geometry import ResolvedRetinalGeometry
from .retinal_sampling import (
    AnalyticVisualFieldSource,
    RetinalProjectionResult,
    project_visual_source,
)
from .stimulus_generators import StimulusRenderResult
from .stimulus_registry import ResolvedStimulusSpec


RETINAL_RECORDING_VERSION = "retinal_recording.v1"
RETINAL_FRAME_ARCHIVE_VERSION = "retinal_frame_archive.v1"
FRAME_ARCHIVE_REPLAY_SOURCE = "frame_archive"

_FIXED_ZIP_DATETIME = (1980, 1, 1, 0, 0, 0)
_FLOAT_ABS_TOL = 1.0e-9


@dataclass(frozen=True)
class RetinalBundleFrame:
    frame_index: int
    time_ms: float
    retinal_frame: np.ndarray
    early_visual_frame: np.ndarray
    frame_metadata: dict[str, Any]


@dataclass(frozen=True)
class RetinalBundleReplay:
    bundle_metadata: dict[str, Any]
    source_descriptor: dict[str, Any]
    projector_metadata: dict[str, Any]
    frame_times_ms: np.ndarray
    retinal_frames: np.ndarray
    early_visual_units: np.ndarray
    frame_metadata: tuple[dict[str, Any], ...]
    replay_source: str

    @property
    def bundle_metadata_path(self) -> Path:
        return Path(self.bundle_metadata["assets"]["metadata_json"]["path"]).resolve()

    def frame_index_for_time_ms(self, time_ms: float) -> int:
        if self.frame_times_ms.size == 0:
            raise ValueError("Recorded retinal bundle does not contain any frames.")
        insertion_index = int(np.searchsorted(self.frame_times_ms, float(time_ms), side="right") - 1)
        return int(np.clip(insertion_index, 0, self.frame_times_ms.size - 1))

    def frame_at_time_ms(self, time_ms: float) -> RetinalBundleFrame:
        frame_index = self.frame_index_for_time_ms(time_ms)
        return RetinalBundleFrame(
            frame_index=frame_index,
            time_ms=float(self.frame_times_ms[frame_index]),
            retinal_frame=np.asarray(self.retinal_frames[frame_index], dtype=np.float32),
            early_visual_frame=np.asarray(self.early_visual_units[frame_index], dtype=np.float32),
            frame_metadata=copy.deepcopy(self.frame_metadata[frame_index]),
        )

    def channel_index(self, channel_name: str) -> int:
        channel_order = list(self.bundle_metadata["simulator_input"]["channel_order"])
        try:
            return int(channel_order.index(str(channel_name)))
        except ValueError as exc:
            raise ValueError(f"Unknown retinal channel {channel_name!r}.") from exc

    def channel_values(self, channel_name: str) -> np.ndarray:
        return np.asarray(
            self.early_visual_units[..., self.channel_index(channel_name)],
            dtype=np.float32,
        )


def project_and_record_retinal_bundle(
    *,
    retinal_geometry: Mapping[str, Any] | ResolvedRetinalGeometry,
    visual_source: (
        Mapping[str, Any]
        | ResolvedStimulusSpec
        | StimulusRenderResult
        | AnalyticVisualFieldSource
    ),
    frame_times_ms: Sequence[float] | np.ndarray | None = None,
    sampling_kernel: Mapping[str, Any] | None = None,
    processed_retinal_dir: str | Path = DEFAULT_PROCESSED_RETINAL_DIR,
    body_pose: Mapping[str, Any] | None = None,
    head_pose: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    projection = project_visual_source(
        retinal_geometry=retinal_geometry,
        visual_source=visual_source,
        frame_times_ms=frame_times_ms,
        sampling_kernel=sampling_kernel,
        body_pose=body_pose,
        head_pose=head_pose,
    )
    return record_retinal_bundle(
        projection_result=projection,
        processed_retinal_dir=processed_retinal_dir,
    )


def record_retinal_bundle(
    *,
    projection_result: RetinalProjectionResult,
    processed_retinal_dir: str | Path = DEFAULT_PROCESSED_RETINAL_DIR,
) -> dict[str, Any]:
    if not isinstance(projection_result, RetinalProjectionResult):
        raise ValueError("projection_result must be a RetinalProjectionResult.")

    source_reference = build_retinal_source_reference_from_descriptor(
        projection_result.source_descriptor
    )
    temporal_sampling = _build_temporal_sampling_from_frame_times(projection_result.frame_times_ms)
    bundle_metadata = build_retinal_bundle_metadata(
        source_reference=source_reference,
        eye_sampling=projection_result.eye_sampling,
        temporal_sampling=temporal_sampling,
        processed_retinal_dir=processed_retinal_dir,
        sampling_kernel=projection_result.sampling_kernel,
        signal_convention=projection_result.signal_convention,
        frame_archive_status=ASSET_STATUS_READY,
    )
    early_visual_units = map_retinal_frames_to_early_visual_units(
        retinal_frames=projection_result.samples,
        bundle_metadata=bundle_metadata,
    )
    frame_archive_path = _write_retinal_frame_archive(
        frame_times_ms=projection_result.frame_times_ms,
        retinal_frames=projection_result.samples,
        early_visual_units=early_visual_units,
        frame_metadata=projection_result.frame_metadata,
        source_descriptor=projection_result.source_descriptor,
        projector_metadata=projection_result.projector_metadata,
        frame_archive_path=bundle_metadata["assets"][FRAME_ARCHIVE_KEY]["path"],
    )
    bundle_metadata["recording"] = _build_recording_metadata(
        projection_result=projection_result,
        early_visual_units=early_visual_units,
        frame_archive_path=frame_archive_path,
    )
    metadata_path = write_retinal_bundle_metadata(bundle_metadata)
    replay = load_recorded_retinal_bundle(metadata_path)
    return {
        "retinal_bundle_id": replay.bundle_metadata["bundle_id"],
        "retinal_bundle_metadata_path": str(metadata_path.resolve()),
        "bundle_directory": str(metadata_path.resolve().parent),
        "frame_archive_path": str(frame_archive_path.resolve()),
        "frame_archive_format": DEFAULT_FRAME_ARCHIVE_FORMAT,
        "retinal_spec_hash": replay.bundle_metadata["retinal_spec_hash"],
        "source_reference": copy.deepcopy(replay.bundle_metadata["source_reference"]),
        "frame_count": int(replay.retinal_frames.shape[0]),
        "retinal_frame_shape_t_eye_ommatidium": [
            int(replay.retinal_frames.shape[0]),
            int(replay.retinal_frames.shape[1]),
            int(replay.retinal_frames.shape[2]),
        ],
        "early_visual_shape_t_eye_unit_channel": [
            int(replay.early_visual_units.shape[0]),
            int(replay.early_visual_units.shape[1]),
            int(replay.early_visual_units.shape[2]),
            int(replay.early_visual_units.shape[3]),
        ],
        "replay_source": replay.replay_source,
    }


def load_recorded_retinal_bundle(
    bundle_metadata: Mapping[str, Any] | str | Path,
) -> RetinalBundleReplay:
    normalized_metadata = _load_or_parse_bundle_metadata(bundle_metadata)
    frame_archive_record = normalized_metadata["assets"][FRAME_ARCHIVE_KEY]
    frame_archive_path = Path(frame_archive_record["path"]).resolve()
    if frame_archive_record["status"] != ASSET_STATUS_READY:
        raise ValueError(
            "Recorded retinal bundles require a ready frame archive; "
            f"got status {frame_archive_record['status']!r}."
        )
    if not frame_archive_path.exists():
        raise FileNotFoundError(
            f"Retinal frame archive is missing at {frame_archive_path}."
        )
    (
        retinal_frames,
        early_visual_units,
        frame_times_ms,
        frame_metadata,
        source_descriptor,
        projector_metadata,
    ) = _load_retinal_frame_archive(frame_archive_path)
    _validate_loaded_bundle(
        bundle_metadata=normalized_metadata,
        retinal_frames=retinal_frames,
        early_visual_units=early_visual_units,
        frame_times_ms=frame_times_ms,
        frame_metadata=frame_metadata,
    )
    return RetinalBundleReplay(
        bundle_metadata=normalized_metadata,
        source_descriptor=copy.deepcopy(source_descriptor),
        projector_metadata=copy.deepcopy(projector_metadata),
        frame_times_ms=np.asarray(frame_times_ms, dtype=np.float64),
        retinal_frames=np.asarray(retinal_frames, dtype=np.float32),
        early_visual_units=np.asarray(early_visual_units, dtype=np.float32),
        frame_metadata=tuple(copy.deepcopy(frame_metadata)),
        replay_source=FRAME_ARCHIVE_REPLAY_SOURCE,
    )


def map_retinal_frames_to_early_visual_units(
    *,
    retinal_frames: np.ndarray,
    bundle_metadata: Mapping[str, Any] | None = None,
    simulator_input: Mapping[str, Any] | None = None,
    signal_convention: Mapping[str, Any] | None = None,
) -> np.ndarray:
    if bundle_metadata is None and simulator_input is None:
        raise ValueError("Either bundle_metadata or simulator_input must be provided.")
    frames = np.asarray(retinal_frames, dtype=np.float32)
    if frames.ndim != 3:
        raise ValueError("retinal_frames must have shape (time, eye, ommatidium).")

    if bundle_metadata is not None:
        normalized_metadata = parse_retinal_bundle_metadata(bundle_metadata)
        resolved_simulator_input = normalized_metadata["simulator_input"]
        resolved_signal_convention = normalized_metadata["signal_convention"]
        eye_axis_labels = list(normalized_metadata["eye_sampling"]["eye_order"])
        expected_detector_count = int(normalized_metadata["eye_sampling"]["ommatidium_count_per_eye"])
    else:
        if signal_convention is None:
            raise ValueError("signal_convention is required when bundle_metadata is omitted.")
        if not isinstance(simulator_input, Mapping):
            raise ValueError("simulator_input must be a mapping when bundle_metadata is omitted.")
        resolved_simulator_input = copy.deepcopy(dict(simulator_input))
        resolved_signal_convention = copy.deepcopy(dict(signal_convention))
        eye_axis_labels = list(resolved_simulator_input["eye_axis_labels"])
        expected_detector_count = int(resolved_simulator_input["unit_count_per_eye"])

    if frames.shape[1] != len(eye_axis_labels):
        raise ValueError("retinal_frames eye axis does not match simulator_input eye ordering.")
    if frames.shape[2] != expected_detector_count:
        raise ValueError("retinal_frames ommatidium axis does not match simulator_input.")

    channel_order = list(resolved_simulator_input["channel_order"])
    if channel_order != [DEFAULT_CHANNEL_NAME]:
        raise ValueError(
            "Only the default identity irradiance channel mapping is implemented "
            f"for {RETINAL_FRAME_ARCHIVE_VERSION!r}."
        )

    clipped_frames = np.clip(
        frames,
        float(resolved_signal_convention.get("minimum_value", DEFAULT_SIGNAL_MINIMUM_VALUE)),
        float(resolved_signal_convention.get("maximum_value", DEFAULT_SIGNAL_MAXIMUM_VALUE)),
    ).astype(np.float32, copy=False)
    unit_count = int(resolved_simulator_input["unit_count_per_eye"])
    early_visual_units = np.empty(
        (frames.shape[0], frames.shape[1], unit_count, len(channel_order)),
        dtype=np.float32,
    )
    per_eye_unit_tables = resolved_simulator_input["mapping"]["per_eye_unit_tables"]
    for eye_index, eye_label in enumerate(eye_axis_labels):
        unit_table = per_eye_unit_tables[eye_label]
        source_indices = np.asarray(
            [int(unit_record["source_ommatidium_index"]) for unit_record in unit_table],
            dtype=np.int64,
        )
        early_visual_units[:, eye_index, :, 0] = clipped_frames[:, eye_index, :][:, source_indices]
    return early_visual_units


def _build_recording_metadata(
    *,
    projection_result: RetinalProjectionResult,
    early_visual_units: np.ndarray,
    frame_archive_path: Path,
) -> dict[str, Any]:
    return {
        "recording_version": RETINAL_RECORDING_VERSION,
        "frame_archive_version": RETINAL_FRAME_ARCHIVE_VERSION,
        "frame_archive_path": str(frame_archive_path.resolve()),
        "retinal_frame_shape_t_eye_ommatidium": [
            int(projection_result.samples.shape[0]),
            int(projection_result.samples.shape[1]),
            int(projection_result.samples.shape[2]),
        ],
        "early_visual_shape_t_eye_unit_channel": [
            int(early_visual_units.shape[0]),
            int(early_visual_units.shape[1]),
            int(early_visual_units.shape[2]),
            int(early_visual_units.shape[3]),
        ],
        "frame_dtype": str(np.asarray(projection_result.samples).dtype),
        "early_visual_dtype": str(np.asarray(early_visual_units).dtype),
        "source_descriptor": copy.deepcopy(projection_result.source_descriptor),
        "projector_metadata": copy.deepcopy(projection_result.projector_metadata),
    }


def _build_temporal_sampling_from_frame_times(frame_times_ms: Sequence[float] | np.ndarray) -> dict[str, Any]:
    times = np.asarray(frame_times_ms, dtype=np.float64)
    if times.ndim != 1:
        raise ValueError("frame_times_ms must be one-dimensional.")
    if times.size == 0:
        raise ValueError("At least one frame time is required to build a retinal bundle.")
    if times.size == 1:
        dt_ms = 1.0
    else:
        diffs = np.diff(times)
        if np.any(diffs <= 0.0):
            raise ValueError("frame_times_ms must be strictly increasing.")
        if not np.allclose(diffs, diffs[0], atol=_FLOAT_ABS_TOL, rtol=0.0):
            raise ValueError(
                "retinal_input_bundle.v1 requires uniformly spaced frame_times_ms "
                "so the sample-hold timeline is explicit."
            )
        dt_ms = float(diffs[0])
    return {
        "time_origin_ms": float(times[0]),
        "dt_ms": float(dt_ms),
        "duration_ms": float(dt_ms * times.size),
        "frame_count": int(times.size),
    }


def _write_retinal_frame_archive(
    *,
    frame_times_ms: np.ndarray,
    retinal_frames: np.ndarray,
    early_visual_units: np.ndarray,
    frame_metadata: Sequence[Mapping[str, Any]],
    source_descriptor: Mapping[str, Any],
    projector_metadata: Mapping[str, Any],
    frame_archive_path: str | Path,
) -> Path:
    arrays = {
        "frame_times_ms": np.asarray(frame_times_ms, dtype=np.float64),
        "retinal_frames": np.asarray(retinal_frames, dtype=np.float32),
        "early_visual_units": np.asarray(early_visual_units, dtype=np.float32),
        "frame_metadata_json": np.asarray(
            json.dumps(
                list(frame_metadata),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
        ),
        "source_descriptor_json": np.asarray(
            json.dumps(
                source_descriptor,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
        ),
        "projector_metadata_json": np.asarray(
            json.dumps(
                projector_metadata,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
        ),
    }
    return _write_deterministic_npz(arrays, frame_archive_path)


def _load_retinal_frame_archive(
    frame_archive_path: str | Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    archive_path = Path(frame_archive_path)
    with np.load(archive_path, allow_pickle=False) as payload:
        retinal_frames = np.asarray(payload["retinal_frames"], dtype=np.float32)
        early_visual_units = np.asarray(payload["early_visual_units"], dtype=np.float32)
        frame_times_ms = np.asarray(payload["frame_times_ms"], dtype=np.float64)
        frame_metadata = json.loads(str(payload["frame_metadata_json"].item()))
        source_descriptor = json.loads(str(payload["source_descriptor_json"].item()))
        projector_metadata = json.loads(str(payload["projector_metadata_json"].item()))
    return (
        retinal_frames,
        early_visual_units,
        frame_times_ms,
        frame_metadata,
        source_descriptor,
        projector_metadata,
    )


def _write_deterministic_npz(arrays: Mapping[str, np.ndarray], out_path: str | Path) -> Path:
    output_path = Path(out_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        with zipfile.ZipFile(handle, mode="w", compression=zipfile.ZIP_STORED) as archive:
            for key in sorted(arrays):
                array_buffer = io.BytesIO()
                np.lib.format.write_array(
                    array_buffer,
                    np.asarray(arrays[key]),
                    allow_pickle=False,
                )
                info = zipfile.ZipInfo(f"{key}.npy", date_time=_FIXED_ZIP_DATETIME)
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = 0o600 << 16
                archive.writestr(info, array_buffer.getvalue())
    return output_path.resolve()


def _load_or_parse_bundle_metadata(
    bundle_metadata: Mapping[str, Any] | str | Path,
) -> dict[str, Any]:
    if isinstance(bundle_metadata, Mapping):
        return parse_retinal_bundle_metadata(bundle_metadata)
    return load_retinal_bundle_metadata(bundle_metadata)


def _validate_loaded_bundle(
    *,
    bundle_metadata: Mapping[str, Any],
    retinal_frames: np.ndarray,
    early_visual_units: np.ndarray,
    frame_times_ms: np.ndarray,
    frame_metadata: Sequence[Mapping[str, Any]],
) -> None:
    temporal_sampling = bundle_metadata["temporal_sampling"]
    frame_layout = bundle_metadata["frame_layout"]
    simulator_input = bundle_metadata["simulator_input"]

    expected_frame_count = int(temporal_sampling["frame_count"])
    if frame_times_ms.shape != (expected_frame_count,):
        raise ValueError("Retinal frame archive frame_times_ms does not match bundle metadata.")
    if retinal_frames.shape != (
        expected_frame_count,
        len(frame_layout["eye_axis_labels"]),
        int(frame_layout["ommatidium_count_per_eye"]),
    ):
        raise ValueError("Retinal frame archive retinal_frames shape does not match bundle metadata.")
    if early_visual_units.shape != (
        expected_frame_count,
        len(simulator_input["eye_axis_labels"]),
        int(simulator_input["unit_count_per_eye"]),
        int(simulator_input["channel_count"]),
    ):
        raise ValueError(
            "Retinal frame archive early_visual_units shape does not match bundle metadata."
        )
    if len(frame_metadata) != expected_frame_count:
        raise ValueError("Retinal frame archive frame_metadata length does not match frame_count.")
    expected_times = _expected_frame_times_ms(temporal_sampling)
    if not np.allclose(frame_times_ms, expected_times, atol=_FLOAT_ABS_TOL, rtol=0.0):
        raise ValueError("Retinal frame archive frame_times_ms does not match temporal_sampling.")


def _expected_frame_times_ms(temporal_sampling: Mapping[str, Any]) -> np.ndarray:
    frame_count = int(temporal_sampling["frame_count"])
    time_origin_ms = float(temporal_sampling["time_origin_ms"])
    dt_ms = float(temporal_sampling["dt_ms"])
    return time_origin_ms + np.arange(frame_count, dtype=np.float64) * dt_ms
