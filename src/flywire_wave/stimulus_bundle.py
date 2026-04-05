from __future__ import annotations

import copy
import html
import io
import json
import math
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .config import load_config
from .io_utils import ensure_dir, write_json
from .manifests import resolve_manifest_input_roots, validate_manifest
from .stimulus_contract import (
    ASSET_STATUS_READY,
    ASSET_STATUS_SKIPPED,
    FRAME_CACHE_KEY,
    PREVIEW_GIF_KEY,
    load_stimulus_bundle_metadata,
    parse_stimulus_bundle_metadata,
    write_stimulus_bundle_metadata,
)
from .stimulus_generators import StimulusRenderResult, synthesize_stimulus
from .stimulus_registry import (
    STIMULUS_SPEC_VERSION,
    ResolvedStimulusSpec,
    get_stimulus_registry_entry,
)


STIMULUS_RECORDING_VERSION = "stimulus_recording.v1"
STIMULUS_FRAME_CACHE_VERSION = "stimulus_frame_cache.v1"
STIMULUS_PREVIEW_VERSION = "stimulus_preview.v1"

FRAME_CACHE_REPLAY_SOURCE = "frame_cache"
DESCRIPTOR_REPLAY_SOURCE = "descriptor_regeneration"

PREVIEW_DIR_NAME = "preview"
PREVIEW_FRAMES_DIR_NAME = "frames"
PREVIEW_IMAGE_MAX_DIMENSION_PX = 64
PREVIEW_CELL_SIZE_PX = 8
_FIXED_ZIP_DATETIME = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class ResolvedStimulusInput:
    source_kind: str
    source_path: Path
    processed_stimulus_dir: Path
    bundle_metadata_path: Path
    resolved_stimulus: ResolvedStimulusSpec


@dataclass(frozen=True)
class StimulusReplayFrame:
    frame_index: int
    time_ms: float
    frame: np.ndarray


@dataclass(frozen=True)
class StimulusBundleReplay:
    bundle_metadata: dict[str, Any]
    registry_entry: dict[str, Any]
    frames: np.ndarray
    frame_times_ms: np.ndarray
    x_coordinates_deg: np.ndarray
    y_coordinates_deg: np.ndarray
    render_metadata: dict[str, Any]
    replay_source: str

    @property
    def bundle_metadata_path(self) -> Path:
        return Path(self.bundle_metadata["assets"]["metadata_json"]["path"]).resolve()

    def iter_frames(self) -> list[StimulusReplayFrame]:
        return [
            StimulusReplayFrame(
                frame_index=index,
                time_ms=float(self.frame_times_ms[index]),
                frame=self.frames[index],
            )
            for index in range(self.frames.shape[0])
        ]

    def frame_index_for_time_ms(self, time_ms: float) -> int:
        if self.frame_times_ms.size == 0:
            raise ValueError("Recorded stimulus bundle does not contain any frames.")
        insertion_index = int(np.searchsorted(self.frame_times_ms, float(time_ms), side="right") - 1)
        return int(np.clip(insertion_index, 0, self.frame_times_ms.size - 1))

    def frame_at_time_ms(self, time_ms: float) -> np.ndarray:
        return self.frames[self.frame_index_for_time_ms(time_ms)]


def resolve_stimulus_input(
    *,
    config_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    schema_path: str | Path | None = None,
    design_lock_path: str | Path | None = None,
    processed_stimulus_dir: str | Path | None = None,
) -> ResolvedStimulusInput:
    if (config_path is None) == (manifest_path is None):
        raise ValueError("Exactly one of config_path or manifest_path must be provided.")

    if config_path is not None:
        cfg = load_config(config_path)
        if "stimulus" not in cfg or "stimulus_registry_entry" not in cfg:
            raise ValueError("Config does not resolve a canonical stimulus reference.")
        resolved_dir = resolve_manifest_input_roots(
            processed_stimulus_dir=processed_stimulus_dir
            or cfg["paths"]["processed_stimulus_dir"]
        ).processed_stimulus_dir
        resolved_stimulus = ResolvedStimulusSpec(
            stimulus_spec=copy.deepcopy(cfg["stimulus"]),
            registry_entry=copy.deepcopy(cfg["stimulus_registry_entry"]),
        )
        bundle_metadata_path = Path(
            resolved_stimulus.resolve_bundle_metadata_path(
                processed_stimulus_dir=resolved_dir,
            )
        ).resolve()
        return ResolvedStimulusInput(
            source_kind="config",
            source_path=Path(config_path).resolve(),
            processed_stimulus_dir=resolved_dir,
            bundle_metadata_path=bundle_metadata_path,
            resolved_stimulus=resolved_stimulus,
        )

    if schema_path is None or design_lock_path is None:
        raise ValueError("schema_path and design_lock_path are required when resolving from a manifest.")

    resolved_dir = resolve_manifest_input_roots(
        processed_stimulus_dir=processed_stimulus_dir
    ).processed_stimulus_dir
    summary = validate_manifest(
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        processed_stimulus_dir=resolved_dir,
    )
    resolved_stimulus = ResolvedStimulusSpec(
        stimulus_spec=copy.deepcopy(summary["resolved_stimulus"]),
        registry_entry=copy.deepcopy(summary["stimulus_registry_entry"]),
    )
    return ResolvedStimulusInput(
        source_kind="manifest",
        source_path=Path(manifest_path).resolve(),
        processed_stimulus_dir=resolved_dir,
        bundle_metadata_path=Path(summary["stimulus_bundle_metadata_path"]).resolve(),
        resolved_stimulus=resolved_stimulus,
    )


def record_stimulus_bundle(
    resolved_input: ResolvedStimulusInput,
    *,
    preview_frame_indices: Sequence[int] | None = None,
) -> dict[str, Any]:
    render_result = synthesize_stimulus(resolved_input.resolved_stimulus)
    bundle_metadata = resolved_input.resolved_stimulus.build_bundle_metadata(
        processed_stimulus_dir=resolved_input.processed_stimulus_dir
    )
    bundle_metadata["assets"][FRAME_CACHE_KEY]["status"] = ASSET_STATUS_READY
    bundle_metadata["assets"][PREVIEW_GIF_KEY]["status"] = ASSET_STATUS_SKIPPED

    frame_cache_path = _write_stimulus_frame_cache(
        render_result=render_result,
        frame_cache_path=Path(bundle_metadata["assets"][FRAME_CACHE_KEY]["path"]),
    )
    preview_summary = generate_stimulus_preview(
        bundle_metadata=bundle_metadata,
        render_result=render_result,
        selected_frame_indices=preview_frame_indices,
    )

    bundle_metadata["recording"] = _build_recording_metadata(
        render_result=render_result,
        frame_cache_path=frame_cache_path,
    )
    bundle_metadata["preview"] = {
        "preview_version": STIMULUS_PREVIEW_VERSION,
        "output_dir": preview_summary["output_dir"],
        "report_path": preview_summary["report_path"],
        "summary_path": preview_summary["summary_path"],
        "frame_image_paths": [
            frame_record["path"] for frame_record in preview_summary["selected_frames"]
        ],
        "selected_frame_indices": preview_summary["selected_frame_indices"],
        "selected_frame_times_ms": preview_summary["selected_frame_times_ms"],
    }

    metadata_path = write_stimulus_bundle_metadata(bundle_metadata)
    replay = load_recorded_stimulus_bundle(metadata_path)

    return {
        "mode": "record",
        "source_kind": resolved_input.source_kind,
        "source_path": str(resolved_input.source_path),
        "processed_stimulus_dir": str(resolved_input.processed_stimulus_dir),
        "stimulus_bundle_id": replay.bundle_metadata["bundle_id"],
        "stimulus_bundle_metadata_path": str(metadata_path.resolve()),
        "bundle_directory": str(metadata_path.resolve().parent),
        "frame_cache_path": str(frame_cache_path.resolve()),
        "preview_output_dir": preview_summary["output_dir"],
        "preview_report_path": preview_summary["report_path"],
        "preview_summary_path": preview_summary["summary_path"],
        "preview_frame_image_paths": [
            frame_record["path"] for frame_record in preview_summary["selected_frames"]
        ],
        "selected_preview_frame_indices": preview_summary["selected_frame_indices"],
        "frame_count": int(replay.frames.shape[0]),
        "frame_shape_y_x": [int(replay.frames.shape[1]), int(replay.frames.shape[2])],
        "replay_source": replay.replay_source,
        "parameter_hash": replay.bundle_metadata["parameter_hash"],
    }


def replay_stimulus_bundle(
    *,
    bundle_metadata_path: str | Path | None = None,
    resolved_input: ResolvedStimulusInput | None = None,
    time_ms: Sequence[float] | None = None,
) -> dict[str, Any]:
    metadata_path = _resolve_bundle_metadata_path(
        bundle_metadata_path=bundle_metadata_path,
        resolved_input=resolved_input,
    )
    replay = load_recorded_stimulus_bundle(metadata_path)
    requested_times = [float(value) for value in (time_ms or [])]

    samples = [
        {
            "requested_time_ms": requested_time_ms,
            "frame_index": replay.frame_index_for_time_ms(requested_time_ms),
            "frame_time_ms": float(
                replay.frame_times_ms[replay.frame_index_for_time_ms(requested_time_ms)]
            ),
            "mean_luminance": float(
                np.mean(replay.frames[replay.frame_index_for_time_ms(requested_time_ms)])
            ),
        }
        for requested_time_ms in requested_times
    ]

    preview_summary = replay.bundle_metadata.get("preview", {})
    return {
        "mode": "replay",
        "stimulus_bundle_id": replay.bundle_metadata["bundle_id"],
        "stimulus_bundle_metadata_path": str(metadata_path.resolve()),
        "parameter_hash": replay.bundle_metadata["parameter_hash"],
        "replay_source": replay.replay_source,
        "frame_count": int(replay.frames.shape[0]),
        "frame_shape_y_x": [int(replay.frames.shape[1]), int(replay.frames.shape[2])],
        "frame_time_range_ms": [
            float(replay.frame_times_ms[0]),
            float(replay.frame_times_ms[-1]),
        ],
        "preview_report_path": preview_summary.get("report_path"),
        "preview_summary_path": preview_summary.get("summary_path"),
        "requested_samples": samples,
    }


def load_recorded_stimulus_bundle(
    bundle_metadata: Mapping[str, Any] | str | Path,
) -> StimulusBundleReplay:
    normalized_metadata = _load_or_parse_bundle_metadata(bundle_metadata)
    frame_cache_record = normalized_metadata["assets"][FRAME_CACHE_KEY]
    frame_cache_path = Path(frame_cache_record["path"]).resolve()
    replay_source = DESCRIPTOR_REPLAY_SOURCE

    if frame_cache_record["status"] == ASSET_STATUS_READY and frame_cache_path.exists():
        frames, frame_times_ms, x_coordinates_deg, y_coordinates_deg, render_metadata = (
            _load_stimulus_frame_cache(frame_cache_path)
        )
        replay_source = FRAME_CACHE_REPLAY_SOURCE
    else:
        resolved = resolved_stimulus_from_bundle_metadata(normalized_metadata)
        render_result = synthesize_stimulus(resolved)
        frames = render_result.frames
        frame_times_ms = render_result.frame_times_ms
        x_coordinates_deg = render_result.x_coordinates_deg
        y_coordinates_deg = render_result.y_coordinates_deg
        render_metadata = render_result.render_metadata

    _validate_replay_arrays(
        metadata=normalized_metadata,
        frames=frames,
        frame_times_ms=frame_times_ms,
        x_coordinates_deg=x_coordinates_deg,
        y_coordinates_deg=y_coordinates_deg,
    )
    return StimulusBundleReplay(
        bundle_metadata=normalized_metadata,
        registry_entry=get_stimulus_registry_entry(
            normalized_metadata["stimulus_family"],
            normalized_metadata["stimulus_name"],
        ),
        frames=np.asarray(frames, dtype=np.float32),
        frame_times_ms=np.asarray(frame_times_ms, dtype=np.float64),
        x_coordinates_deg=np.asarray(x_coordinates_deg, dtype=np.float64),
        y_coordinates_deg=np.asarray(y_coordinates_deg, dtype=np.float64),
        render_metadata=copy.deepcopy(render_metadata),
        replay_source=replay_source,
    )


def resolved_stimulus_from_bundle_metadata(bundle_metadata: Mapping[str, Any]) -> ResolvedStimulusSpec:
    normalized = parse_stimulus_bundle_metadata(bundle_metadata)
    registry_entry = get_stimulus_registry_entry(
        normalized["stimulus_family"],
        normalized["stimulus_name"],
    )
    parameters = normalized["parameter_snapshot"]
    luminance = normalized["luminance_convention"]
    stimulus_spec = {
        "spec_version": STIMULUS_SPEC_VERSION,
        "bundle_contract_version": normalized["contract_version"],
        "requested_stimulus_family": normalized["stimulus_family"],
        "requested_stimulus_name": normalized["stimulus_name"],
        "stimulus_family": normalized["stimulus_family"],
        "stimulus_name": normalized["stimulus_name"],
        "parameter_hash": normalized["parameter_hash"],
        "compatibility": {
            "family_alias_used": False,
            "name_alias_used": False,
        },
        "parameter_snapshot": copy.deepcopy(parameters),
        "temporal_sampling": copy.deepcopy(normalized["temporal_sampling"]),
        "spatial_frame": copy.deepcopy(normalized["spatial_frame"]),
        "luminance_convention": copy.deepcopy(luminance),
        "presentation": {
            "background_level": parameters["background_level"],
            "contrast": parameters["contrast"],
            "polarity": parameters["polarity"],
            "contrast_semantics": luminance["contrast_semantics"],
            "positive_polarity": luminance["positive_polarity"],
            "clip_mode": "clip_to_unit_interval",
        },
        "determinism": copy.deepcopy(normalized["determinism"]),
    }
    return ResolvedStimulusSpec(
        stimulus_spec=stimulus_spec,
        registry_entry=registry_entry,
    )


def generate_stimulus_preview(
    *,
    bundle_metadata: Mapping[str, Any],
    render_result: StimulusRenderResult,
    selected_frame_indices: Sequence[int] | None = None,
) -> dict[str, Any]:
    normalized_metadata = parse_stimulus_bundle_metadata(bundle_metadata)
    output_dir = (
        Path(normalized_metadata["assets"]["metadata_json"]["path"]).resolve().parent / PREVIEW_DIR_NAME
    )
    frames_dir = output_dir / PREVIEW_FRAMES_DIR_NAME
    ensure_dir(frames_dir)

    preview_indices = _normalize_preview_frame_indices(
        frame_count=int(render_result.frames.shape[0]),
        selected_frame_indices=selected_frame_indices,
        frame_times_ms=render_result.frame_times_ms,
        stimulus_spec=render_result.stimulus_spec,
    )

    selected_frames: list[dict[str, Any]] = []
    for frame_index in preview_indices:
        frame_path = frames_dir / f"frame-{frame_index:04d}.svg"
        preview_frame = _downsample_frame_for_preview(
            render_result.frames[frame_index],
            max_dimension=PREVIEW_IMAGE_MAX_DIMENSION_PX,
        )
        frame_path.write_text(
            _render_frame_svg(preview_frame),
            encoding="utf-8",
        )
        selected_frames.append(
            {
                "frame_index": frame_index,
                "time_ms": float(render_result.frame_times_ms[frame_index]),
                "path": str(frame_path.resolve()),
                "mean_luminance": float(np.mean(render_result.frames[frame_index])),
                "min_luminance": float(np.min(render_result.frames[frame_index])),
                "max_luminance": float(np.max(render_result.frames[frame_index])),
                "preview_shape_y_x": [
                    int(preview_frame.shape[0]),
                    int(preview_frame.shape[1]),
                ],
            }
        )

    report_path = (output_dir / "index.html").resolve()
    summary_path = (output_dir / "summary.json").resolve()
    summary = {
        "preview_version": STIMULUS_PREVIEW_VERSION,
        "bundle_id": normalized_metadata["bundle_id"],
        "output_dir": str(output_dir.resolve()),
        "report_path": str(report_path),
        "summary_path": str(summary_path),
        "selected_frame_indices": preview_indices,
        "selected_frame_times_ms": [
            float(render_result.frame_times_ms[index]) for index in preview_indices
        ],
        "frame_count": int(render_result.frames.shape[0]),
        "frame_shape_y_x": [
            int(render_result.frames.shape[1]),
            int(render_result.frames.shape[2]),
        ],
        "selected_frames": selected_frames,
    }
    report_path.write_text(
        _render_preview_html(
            bundle_metadata=normalized_metadata,
            render_result=render_result,
            summary=summary,
        ),
        encoding="utf-8",
    )
    write_json(summary, summary_path)
    return summary


def _build_recording_metadata(
    *,
    render_result: StimulusRenderResult,
    frame_cache_path: Path,
) -> dict[str, Any]:
    return {
        "recording_version": STIMULUS_RECORDING_VERSION,
        "frame_cache_version": STIMULUS_FRAME_CACHE_VERSION,
        "frame_cache_path": str(frame_cache_path.resolve()),
        "frame_shape_t_y_x": [
            int(render_result.frames.shape[0]),
            int(render_result.frames.shape[1]),
            int(render_result.frames.shape[2]),
        ],
        "frame_dtype": str(render_result.frames.dtype),
        "render_metadata": copy.deepcopy(render_result.render_metadata),
    }


def _write_stimulus_frame_cache(
    *,
    render_result: StimulusRenderResult,
    frame_cache_path: str | Path,
) -> Path:
    arrays = {
        "frame_times_ms": np.asarray(render_result.frame_times_ms, dtype=np.float64),
        "frames": np.asarray(render_result.frames, dtype=np.float32),
        "render_metadata_json": np.asarray(
            json.dumps(
                render_result.render_metadata,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
        ),
        "x_coordinates_deg": np.asarray(render_result.x_coordinates_deg, dtype=np.float64),
        "y_coordinates_deg": np.asarray(render_result.y_coordinates_deg, dtype=np.float64),
    }
    return _write_deterministic_npz(arrays, frame_cache_path)


def _load_stimulus_frame_cache(
    frame_cache_path: str | Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    cache_path = Path(frame_cache_path)
    with np.load(cache_path, allow_pickle=False) as payload:
        frames = np.asarray(payload["frames"], dtype=np.float32)
        frame_times_ms = np.asarray(payload["frame_times_ms"], dtype=np.float64)
        x_coordinates_deg = np.asarray(payload["x_coordinates_deg"], dtype=np.float64)
        y_coordinates_deg = np.asarray(payload["y_coordinates_deg"], dtype=np.float64)
        render_metadata = json.loads(str(payload["render_metadata_json"].item()))
    return frames, frame_times_ms, x_coordinates_deg, y_coordinates_deg, render_metadata


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


def _render_preview_html(
    *,
    bundle_metadata: Mapping[str, Any],
    render_result: StimulusRenderResult,
    summary: Mapping[str, Any],
) -> str:
    selected_frame_cards = "\n".join(
        _render_preview_frame_card(frame_record)
        for frame_record in summary["selected_frames"]
    )
    temporal_sampling = bundle_metadata["temporal_sampling"]
    spatial_frame = bundle_metadata["spatial_frame"]
    determinism = bundle_metadata["determinism"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Offline Stimulus Preview</title>
  <style>
    body {{
      font-family: sans-serif;
      margin: 2rem;
      background: #f8fafc;
      color: #0f172a;
    }}
    main {{
      max-width: 1040px;
      margin: 0 auto;
    }}
    h1, h2 {{
      margin-bottom: 0.5rem;
    }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 0.75rem;
      margin: 1.5rem 0;
    }}
    .card {{
      background: white;
      border: 1px solid #cbd5e1;
      border-radius: 12px;
      padding: 1rem;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
    }}
    .frames {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1rem;
      margin-top: 1rem;
    }}
    img {{
      width: 100%;
      image-rendering: pixelated;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      background: #e2e8f0;
    }}
    code {{
      font-family: monospace;
      font-size: 0.95em;
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
  </style>
</head>
<body>
  <main>
    <h1>Offline Stimulus Preview</h1>
    <p><code>{html.escape(bundle_metadata["bundle_id"])}</code></p>
    <div class="meta">
      <section class="card">
        <h2>Identity</h2>
        <dl>
          <dt>Family</dt>
          <dd>{html.escape(str(bundle_metadata["stimulus_family"]))}</dd>
          <dt>Name</dt>
          <dd>{html.escape(str(bundle_metadata["stimulus_name"]))}</dd>
          <dt>Parameter hash</dt>
          <dd><code>{html.escape(str(bundle_metadata["parameter_hash"]))}</code></dd>
        </dl>
      </section>
      <section class="card">
        <h2>Timing</h2>
        <dl>
          <dt>Frame count</dt>
          <dd>{int(temporal_sampling["frame_count"])}</dd>
          <dt>dt</dt>
          <dd>{float(temporal_sampling["dt_ms"]):.6f} ms</dd>
          <dt>Duration</dt>
          <dd>{float(temporal_sampling["duration_ms"]):.6f} ms</dd>
        </dl>
      </section>
      <section class="card">
        <h2>Spatial frame</h2>
        <dl>
          <dt>Resolution</dt>
          <dd>{int(spatial_frame["width_px"])} x {int(spatial_frame["height_px"])}</dd>
          <dt>Extent</dt>
          <dd>{float(spatial_frame["width_deg"]):.3f} x {float(spatial_frame["height_deg"]):.3f} deg</dd>
          <dt>Frame name</dt>
          <dd>{html.escape(str(spatial_frame["frame_name"]))}</dd>
        </dl>
      </section>
      <section class="card">
        <h2>Determinism</h2>
        <dl>
          <dt>Seed</dt>
          <dd>{int(determinism["seed"])}</dd>
          <dt>RNG family</dt>
          <dd>{html.escape(str(determinism["rng_family"]))}</dd>
          <dt>Generator version</dt>
          <dd>{html.escape(str(render_result.render_metadata["generator_version"]))}</dd>
        </dl>
      </section>
    </div>
    <section>
      <h2>Representative Frames</h2>
      <div class="frames">
        {selected_frame_cards}
      </div>
    </section>
  </main>
</body>
</html>
"""


def _render_preview_frame_card(frame_record: Mapping[str, Any]) -> str:
    image_path = Path(frame_record["path"])
    relative_image_path = f"{PREVIEW_FRAMES_DIR_NAME}/{image_path.name}"
    return f"""
<article class="card">
  <h2>Frame {int(frame_record["frame_index"])}</h2>
  <p>{float(frame_record["time_ms"]):.6f} ms</p>
  <img src="{html.escape(relative_image_path)}" alt="Stimulus preview frame {int(frame_record["frame_index"])}">
  <dl>
    <dt>Mean luminance</dt>
    <dd>{float(frame_record["mean_luminance"]):.6f}</dd>
    <dt>Range</dt>
    <dd>{float(frame_record["min_luminance"]):.6f} to {float(frame_record["max_luminance"]):.6f}</dd>
  </dl>
</article>
"""


def _render_frame_svg(frame: np.ndarray) -> str:
    height, width = frame.shape
    rects: list[str] = []
    for y_index in range(height):
        for x_index in range(width):
            luminance = int(round(float(np.clip(frame[y_index, x_index], 0.0, 1.0)) * 255.0))
            rects.append(
                f'<rect x="{x_index * PREVIEW_CELL_SIZE_PX}" '
                f'y="{y_index * PREVIEW_CELL_SIZE_PX}" '
                f'width="{PREVIEW_CELL_SIZE_PX}" '
                f'height="{PREVIEW_CELL_SIZE_PX}" '
                f'fill="rgb({luminance},{luminance},{luminance})" />'
            )
    width_px = width * PREVIEW_CELL_SIZE_PX
    height_px = height * PREVIEW_CELL_SIZE_PX
    rects_markup = "\n".join(rects)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width_px} {height_px}" '
        f'width="{width_px}" height="{height_px}" shape-rendering="crispEdges">\n'
        f"{rects_markup}\n"
        "</svg>\n"
    )


def _normalize_preview_frame_indices(
    *,
    frame_count: int,
    selected_frame_indices: Sequence[int] | None,
    frame_times_ms: np.ndarray,
    stimulus_spec: Mapping[str, Any],
) -> list[int]:
    if frame_count <= 0:
        raise ValueError("Stimulus preview requires at least one frame.")

    if selected_frame_indices is not None:
        normalized = sorted({int(index) for index in selected_frame_indices})
        for index in normalized:
            if index < 0 or index >= frame_count:
                raise ValueError(f"Preview frame index {index} is out of range for {frame_count} frames.")
        return normalized

    parameters = stimulus_spec["parameter_snapshot"]
    onset_ms = float(parameters["onset_ms"])
    offset_ms = float(parameters["offset_ms"])
    active_indices = [
        index
        for index, time_ms in enumerate(frame_times_ms.tolist())
        if onset_ms <= float(time_ms) < offset_ms
    ]
    candidates = [0]
    if active_indices:
        candidates.extend(
            [
                active_indices[0],
                active_indices[len(active_indices) // 2],
                active_indices[-1],
            ]
        )
    candidates.append(frame_count - 1)

    normalized_candidates: list[int] = []
    seen: set[int] = set()
    for index in candidates:
        bounded = int(np.clip(index, 0, frame_count - 1))
        if bounded not in seen:
            normalized_candidates.append(bounded)
            seen.add(bounded)
    return normalized_candidates


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


def _validate_replay_arrays(
    *,
    metadata: Mapping[str, Any],
    frames: np.ndarray,
    frame_times_ms: np.ndarray,
    x_coordinates_deg: np.ndarray,
    y_coordinates_deg: np.ndarray,
) -> None:
    temporal_sampling = metadata["temporal_sampling"]
    spatial_frame = metadata["spatial_frame"]
    expected_shape = (
        int(temporal_sampling["frame_count"]),
        int(spatial_frame["height_px"]),
        int(spatial_frame["width_px"]),
    )
    if tuple(frames.shape) != expected_shape:
        raise ValueError(
            "Stimulus replay frames do not match the recorded temporal/spatial metadata. "
            f"Expected {expected_shape!r}, got {tuple(frames.shape)!r}."
        )
    if frame_times_ms.shape != (expected_shape[0],):
        raise ValueError("Stimulus replay frame_times_ms length does not match frame_count.")
    if x_coordinates_deg.shape != (expected_shape[2],):
        raise ValueError("Stimulus replay x_coordinates_deg length does not match width_px.")
    if y_coordinates_deg.shape != (expected_shape[1],):
        raise ValueError("Stimulus replay y_coordinates_deg length does not match height_px.")
    expected_frame_times = float(temporal_sampling["time_origin_ms"]) + np.arange(
        expected_shape[0],
        dtype=np.float64,
    ) * float(temporal_sampling["dt_ms"])
    if not np.allclose(frame_times_ms, expected_frame_times, rtol=0.0, atol=1.0e-9):
        raise ValueError("Stimulus replay frame_times_ms do not match the canonical sampling grid.")


def _load_or_parse_bundle_metadata(
    bundle_metadata: Mapping[str, Any] | str | Path,
) -> dict[str, Any]:
    if isinstance(bundle_metadata, (str, Path)):
        return load_stimulus_bundle_metadata(bundle_metadata)
    return parse_stimulus_bundle_metadata(bundle_metadata)


def _resolve_bundle_metadata_path(
    *,
    bundle_metadata_path: str | Path | None,
    resolved_input: ResolvedStimulusInput | None,
) -> Path:
    if bundle_metadata_path is not None:
        return Path(bundle_metadata_path).resolve()
    if resolved_input is None:
        raise ValueError("Either bundle_metadata_path or resolved_input must be provided.")
    return resolved_input.bundle_metadata_path.resolve()
