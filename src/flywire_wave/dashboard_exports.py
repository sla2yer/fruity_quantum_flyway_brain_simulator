from __future__ import annotations

import base64
import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .dashboard_analysis import resolve_dashboard_analysis_view_model
from .dashboard_replay import (
    build_dashboard_replay_state,
    resolve_dashboard_time_series_view_model,
)
from .dashboard_session_contract import (
    ANALYSIS_PANE_ID,
    APP_SHELL_INDEX_ARTIFACT_ID,
    METADATA_JSON_KEY,
    METRICS_EXPORT_KIND,
    METRICS_EXPORT_TARGET_ID,
    MORPHOLOGY_PANE_ID,
    PANE_SNAPSHOT_EXPORT_TARGET_ID,
    REPLAY_EXPORT_KIND,
    REPLAY_FRAME_SEQUENCE_EXPORT_TARGET_ID,
    SCENE_PANE_ID,
    SESSION_PAYLOAD_ARTIFACT_ID,
    SESSION_STATE_ARTIFACT_ID,
    SESSION_STATE_EXPORT_KIND,
    SESSION_STATE_EXPORT_TARGET_ID,
    STILL_IMAGE_EXPORT_KIND,
    TIME_SERIES_PANE_ID,
    build_dashboard_session_contract_metadata,
    discover_dashboard_export_targets,
    discover_dashboard_session_bundle_paths,
    load_dashboard_session_metadata,
)
from .io_utils import ensure_dir, write_json
from .stimulus_contract import DEFAULT_HASH_ALGORITHM


DASHBOARD_EXPORT_METADATA_VERSION = "dashboard_export_metadata.v1"
DASHBOARD_METRICS_EXPORT_VERSION = "dashboard_metrics_export.v1"
DASHBOARD_FRAME_SEQUENCE_MANIFEST_VERSION = "dashboard_frame_sequence_manifest.v1"
DEFAULT_DASHBOARD_EXPORT_DIRECTORY_NAME = "exports"


def execute_dashboard_export(
    *,
    dashboard_session_metadata_path: str | Path,
    export_target_id: str,
    pane_id: str | None = None,
    sample_index: int | None = None,
    selected_neuron_id: int | None = None,
    selected_readout_id: str | None = None,
    active_overlay_id: str | None = None,
    comparison_mode: str | None = None,
    active_arm_id: str | None = None,
) -> dict[str, Any]:
    source = _load_dashboard_source(Path(dashboard_session_metadata_path).resolve())
    contract_metadata = build_dashboard_session_contract_metadata()
    resolved_pane_id = _resolve_pane_id(
        export_target_id=export_target_id,
        pane_id=pane_id,
    )
    export_target = _resolve_export_target_definition(
        contract_metadata=contract_metadata,
        export_target_id=export_target_id,
        pane_id=resolved_pane_id,
    )
    export_state = _resolve_export_state(
        payload=source["payload"],
        session_state=source["session_state"],
        sample_index=sample_index,
        selected_neuron_id=selected_neuron_id,
        selected_readout_id=selected_readout_id,
        active_overlay_id=active_overlay_id,
        comparison_mode=comparison_mode,
        active_arm_id=active_arm_id,
    )
    export_spec_hash = _build_export_spec_hash(
        bundle_id=str(source["metadata"]["bundle_id"]),
        export_target_id=str(export_target_id),
        pane_id=resolved_pane_id,
        global_interaction_state=export_state["global_interaction_state"],
    )
    output_directory = (
        Path(source["metadata"]["bundle_layout"]["bundle_directory"]).resolve()
        / DEFAULT_DASHBOARD_EXPORT_DIRECTORY_NAME
        / _pane_directory_name(resolved_pane_id)
        / str(export_target_id)
        / export_spec_hash
    ).resolve()
    ensure_dir(output_directory)

    result = _write_export_artifacts(
        source=source,
        export_target=export_target,
        pane_id=resolved_pane_id,
        export_state=export_state,
        output_directory=output_directory,
    )
    metadata_payload = {
        "format_version": DASHBOARD_EXPORT_METADATA_VERSION,
        "bundle_reference": {
            "bundle_id": str(source["metadata"]["bundle_id"]),
            "experiment_id": str(source["metadata"]["experiment_id"]),
            "session_spec_hash": str(source["metadata"]["session_spec_hash"]),
        },
        "export_target": {
            "export_target_id": str(export_target["export_target_id"]),
            "display_name": str(export_target["display_name"]),
            "target_kind": str(export_target["target_kind"]),
            "pane_id": resolved_pane_id,
            "requires_time_cursor": bool(export_target["requires_time_cursor"]),
        },
        "hash_algorithm": DEFAULT_HASH_ALGORITHM,
        "export_spec_hash": export_spec_hash,
        "output_directory": str(output_directory),
        "source_paths": {
            "dashboard_session_metadata": str(
                source["bundle_paths"][METADATA_JSON_KEY].resolve()
            ),
            "dashboard_session_payload": str(
                source["bundle_paths"][SESSION_PAYLOAD_ARTIFACT_ID].resolve()
            ),
            "dashboard_session_state": str(
                source["bundle_paths"][SESSION_STATE_ARTIFACT_ID].resolve()
            ),
            "app_shell": str(
                source["bundle_paths"][APP_SHELL_INDEX_ARTIFACT_ID].resolve()
            ),
        },
        "global_interaction_state": copy.deepcopy(
            dict(export_state["global_interaction_state"])
        ),
        "replay_state": copy.deepcopy(dict(export_state["replay_state"])),
        "artifact_inventory": copy.deepcopy(list(result["artifact_inventory"])),
        "summary": copy.deepcopy(dict(result["summary"])),
    }
    metadata_path = write_json(metadata_payload, output_directory / "export_metadata.json")
    return {
        "metadata_path": str(metadata_path.resolve()),
        "output_directory": str(output_directory),
        "export_target_id": str(export_target["export_target_id"]),
        "pane_id": resolved_pane_id,
        "export_spec_hash": export_spec_hash,
        "artifact_inventory": copy.deepcopy(list(result["artifact_inventory"])),
        "summary": copy.deepcopy(dict(result["summary"])),
    }


def _write_export_artifacts(
    *,
    source: Mapping[str, Any],
    export_target: Mapping[str, Any],
    pane_id: str | None,
    export_state: Mapping[str, Any],
    output_directory: Path,
) -> dict[str, Any]:
    target_kind = str(export_target["target_kind"])
    if target_kind == SESSION_STATE_EXPORT_KIND:
        return _write_session_state_export(
            source=source,
            export_state=export_state,
            output_directory=output_directory,
        )
    if target_kind == STILL_IMAGE_EXPORT_KIND:
        return _write_snapshot_export(
            source=source,
            pane_id=_require_pane_id(pane_id, target_kind=target_kind),
            export_state=export_state,
            output_directory=output_directory,
        )
    if target_kind == METRICS_EXPORT_KIND:
        return _write_metrics_export(
            source=source,
            pane_id=_require_pane_id(pane_id, target_kind=target_kind),
            export_state=export_state,
            output_directory=output_directory,
        )
    if target_kind == REPLAY_EXPORT_KIND:
        return _write_replay_frame_sequence_export(
            source=source,
            pane_id=_require_pane_id(pane_id, target_kind=target_kind),
            export_state=export_state,
            output_directory=output_directory,
        )
    raise ValueError(f"Unsupported dashboard export target kind {target_kind!r}.")


def _write_session_state_export(
    *,
    source: Mapping[str, Any],
    export_state: Mapping[str, Any],
    output_directory: Path,
) -> dict[str, Any]:
    export_payload = {
        "format_version": str(source["session_state"]["format_version"]),
        "bundle_reference": copy.deepcopy(
            dict(source["session_state"]["bundle_reference"])
        ),
        "manifest_reference": copy.deepcopy(
            dict(source["session_state"]["manifest_reference"])
        ),
        "global_interaction_state": copy.deepcopy(
            dict(export_state["global_interaction_state"])
        ),
        "replay_state": copy.deepcopy(dict(export_state["replay_state"])),
        "enabled_export_target_ids": list(
            source["session_state"]["enabled_export_target_ids"]
        ),
        "default_export_target_id": str(
            source["session_state"]["default_export_target_id"]
        ),
    }
    export_path = write_json(export_payload, output_directory / "session_state.json")
    return {
        "artifact_inventory": [
            _artifact_record(
                artifact_id=SESSION_STATE_EXPORT_TARGET_ID,
                path=export_path,
                format="json_dashboard_session_state.v1",
                media_type="application/json",
            )
        ],
        "summary": {
            "export_kind": "session_state",
            "playback_state": str(
                export_state["global_interaction_state"]["time_cursor"]["playback_state"]
            ),
            "sample_index": int(
                export_state["global_interaction_state"]["time_cursor"]["sample_index"]
            ),
        },
    }


def _write_snapshot_export(
    *,
    source: Mapping[str, Any],
    pane_id: str,
    export_state: Mapping[str, Any],
    output_directory: Path,
) -> dict[str, Any]:
    snapshot_path = (output_directory / "pane_snapshot.png").resolve()
    image = _render_snapshot_image(
        source=source,
        pane_id=pane_id,
        export_state=export_state,
    )
    image.save(snapshot_path, format="PNG")
    return {
        "artifact_inventory": [
            _artifact_record(
                artifact_id=PANE_SNAPSHOT_EXPORT_TARGET_ID,
                path=snapshot_path,
                format="png_dashboard_pane_snapshot.v1",
                media_type="image/png",
            )
        ],
        "summary": {
            "export_kind": "still_image",
            "pane_id": pane_id,
            "image_size": list(image.size),
            "active_overlay_id": str(
                export_state["global_interaction_state"]["active_overlay_id"]
            ),
        },
    }


def _write_metrics_export(
    *,
    source: Mapping[str, Any],
    pane_id: str,
    export_state: Mapping[str, Any],
    output_directory: Path,
) -> dict[str, Any]:
    metrics_payload = _build_metrics_payload(
        source=source,
        pane_id=pane_id,
        export_state=export_state,
    )
    metrics_path = write_json(metrics_payload, output_directory / "metrics.json")
    return {
        "artifact_inventory": [
            _artifact_record(
                artifact_id=METRICS_EXPORT_TARGET_ID,
                path=metrics_path,
                format="json_dashboard_metrics_export.v1",
                media_type="application/json",
            )
        ],
        "summary": copy.deepcopy(dict(metrics_payload["summary"])),
    }


def _write_replay_frame_sequence_export(
    *,
    source: Mapping[str, Any],
    pane_id: str,
    export_state: Mapping[str, Any],
    output_directory: Path,
) -> dict[str, Any]:
    if pane_id == SCENE_PANE_ID:
        return _write_scene_frame_sequence_export(
            source=source,
            export_state=export_state,
            output_directory=output_directory,
        )
    if pane_id == TIME_SERIES_PANE_ID:
        return _write_time_series_frame_sequence_export(
            source=source,
            export_state=export_state,
            output_directory=output_directory,
        )
    raise ValueError(
        "The first replay frame-sequence export supports only the scene and "
        f"time_series panes, got {pane_id!r}."
    )


def _write_scene_frame_sequence_export(
    *,
    source: Mapping[str, Any],
    export_state: Mapping[str, Any],
    output_directory: Path,
) -> dict[str, Any]:
    scene_context = _pane_context(source["payload"], SCENE_PANE_ID)
    frames = _sequence_mapping(
        scene_context.get("replay_frames", []),
        field_name="scene_context.replay_frames",
    )
    if not frames:
        raise ValueError("Scene frame-sequence export requires packaged replay_frames.")
    frames_directory = ensure_dir(output_directory / "frames")
    frame_records: list[dict[str, Any]] = []
    for index, frame in enumerate(frames):
        file_name = f"frame_{index:04d}.png"
        frame_path = (frames_directory / file_name).resolve()
        image = _render_scene_frame_png(frame)
        image.save(frame_path, format="PNG")
        frame_records.append(
            {
                "frame_index": int(frame["frame_index"]),
                "time_ms": float(frame["time_ms"]),
                "path": str(frame_path),
                "width": int(image.size[0]),
                "height": int(image.size[1]),
            }
        )
    manifest_payload = {
        "format_version": DASHBOARD_FRAME_SEQUENCE_MANIFEST_VERSION,
        "pane_id": SCENE_PANE_ID,
        "frame_count": len(frame_records),
        "frame_records": frame_records,
        "active_sample_index": int(
            export_state["global_interaction_state"]["time_cursor"]["sample_index"]
        ),
    }
    manifest_path = write_json(manifest_payload, output_directory / "frame_sequence_manifest.json")
    artifact_inventory = [
        _artifact_record(
            artifact_id="frame_sequence_manifest",
            path=manifest_path,
            format="json_dashboard_frame_sequence_manifest.v1",
            media_type="application/json",
        )
    ]
    for frame_record in frame_records:
        artifact_inventory.append(
            _artifact_record(
                artifact_id=f"scene_frame_{frame_record['frame_index']:04d}",
                path=frame_record["path"],
                format="png_dashboard_scene_frame.v1",
                media_type="image/png",
            )
        )
    return {
        "artifact_inventory": artifact_inventory,
        "summary": {
            "export_kind": "replay_frame_sequence",
            "pane_id": SCENE_PANE_ID,
            "frame_count": len(frame_records),
            "first_frame_path": frame_records[0]["path"],
            "last_frame_path": frame_records[-1]["path"],
            "active_sample_index": int(
                export_state["global_interaction_state"]["time_cursor"]["sample_index"]
            ),
        },
    }


def _write_time_series_frame_sequence_export(
    *,
    source: Mapping[str, Any],
    export_state: Mapping[str, Any],
    output_directory: Path,
) -> dict[str, Any]:
    time_series_context = _pane_context(source["payload"], TIME_SERIES_PANE_ID)
    replay_model = _mapping(time_series_context.get("replay_model"), field_name="time_series_context.replay_model")
    sample_count = int(_mapping(replay_model.get("timebase"), field_name="replay_model.timebase")["sample_count"])
    frames_directory = ensure_dir(output_directory / "frames")
    frame_records: list[dict[str, Any]] = []
    for sample_index in range(sample_count):
        frame_path = (frames_directory / f"frame_{sample_index:04d}.png").resolve()
        image = _render_time_series_frame_image(
            source=source,
            export_state=export_state,
            sample_index=sample_index,
        )
        image.save(frame_path, format="PNG")
        frame_records.append(
            {
                "frame_index": sample_index,
                "time_ms": float(replay_model["canonical_time_ms"][sample_index]),
                "path": str(frame_path),
                "width": int(image.size[0]),
                "height": int(image.size[1]),
            }
        )
    manifest_payload = {
        "format_version": DASHBOARD_FRAME_SEQUENCE_MANIFEST_VERSION,
        "pane_id": TIME_SERIES_PANE_ID,
        "frame_count": len(frame_records),
        "frame_records": frame_records,
        "active_sample_index": int(
            export_state["global_interaction_state"]["time_cursor"]["sample_index"]
        ),
    }
    manifest_path = write_json(manifest_payload, output_directory / "frame_sequence_manifest.json")
    artifact_inventory = [
        _artifact_record(
            artifact_id="frame_sequence_manifest",
            path=manifest_path,
            format="json_dashboard_frame_sequence_manifest.v1",
            media_type="application/json",
        )
    ]
    for frame_record in frame_records:
        artifact_inventory.append(
            _artifact_record(
                artifact_id=f"time_series_frame_{frame_record['frame_index']:04d}",
                path=frame_record["path"],
                format="png_dashboard_time_series_frame.v1",
                media_type="image/png",
            )
        )
    return {
        "artifact_inventory": artifact_inventory,
        "summary": {
            "export_kind": "replay_frame_sequence",
            "pane_id": TIME_SERIES_PANE_ID,
            "frame_count": len(frame_records),
            "first_frame_path": frame_records[0]["path"],
            "last_frame_path": frame_records[-1]["path"],
            "active_sample_index": int(
                export_state["global_interaction_state"]["time_cursor"]["sample_index"]
            ),
        },
    }


def _build_metrics_payload(
    *,
    source: Mapping[str, Any],
    pane_id: str,
    export_state: Mapping[str, Any],
) -> dict[str, Any]:
    if pane_id == ANALYSIS_PANE_ID:
        return _build_analysis_metrics_payload(
            source=source,
            export_state=export_state,
        )
    if pane_id == TIME_SERIES_PANE_ID:
        return _build_time_series_metrics_payload(
            source=source,
            export_state=export_state,
        )
    raise ValueError(
        "Metrics export is available only for the analysis and time_series panes, "
        f"got {pane_id!r}."
    )


def _build_analysis_metrics_payload(
    *,
    source: Mapping[str, Any],
    export_state: Mapping[str, Any],
) -> dict[str, Any]:
    analysis_context = _pane_context(source["payload"], ANALYSIS_PANE_ID)
    time_series_context = _pane_context(source["payload"], TIME_SERIES_PANE_ID)
    state = export_state["global_interaction_state"]
    analysis_view = resolve_dashboard_analysis_view_model(
        analysis_context,
        time_series_context=time_series_context,
        selected_neuron_id=int(state["selected_neuron_id"]),
        selected_readout_id=str(state["selected_readout_id"]),
        comparison_mode=str(state["comparison_mode"]),
        active_arm_id=str(state["selected_arm_pair"]["active_arm_id"]),
        active_overlay_id=str(state["active_overlay_id"]),
        sample_index=int(state["time_cursor"]["sample_index"]),
    )
    shared = _mapping(analysis_view.get("shared_comparison"), field_name="analysis_view.shared_comparison")
    wave = _mapping(analysis_view.get("wave_only_diagnostics"), field_name="analysis_view.wave_only_diagnostics")
    validation = _mapping(
        analysis_view.get("validation_evidence"),
        field_name="analysis_view.validation_evidence",
    )
    return {
        "format_version": DASHBOARD_METRICS_EXPORT_VERSION,
        "pane_id": ANALYSIS_PANE_ID,
        "bundle_reference": {
            "bundle_id": str(source["metadata"]["bundle_id"]),
            "experiment_id": str(source["metadata"]["experiment_id"]),
        },
        "global_interaction_state": copy.deepcopy(dict(state)),
        "replay_state": copy.deepcopy(dict(export_state["replay_state"])),
        "active_overlay": copy.deepcopy(
            _mapping(analysis_view.get("active_overlay"), field_name="analysis_view.active_overlay")
        ),
        "shared_comparison": {
            "task_summary_cards": copy.deepcopy(
                _sequence_mapping(
                    shared.get("task_summary_cards", []),
                    field_name="analysis_view.shared_comparison.task_summary_cards",
                )
            ),
            "comparison_cards": copy.deepcopy(
                _sequence_mapping(
                    shared.get("comparison_cards", []),
                    field_name="analysis_view.shared_comparison.comparison_cards",
                )
            ),
            "ablation_summaries": copy.deepcopy(
                _sequence_mapping(
                    shared.get("ablation_summaries", []),
                    field_name="analysis_view.shared_comparison.ablation_summaries",
                )
            ),
            "matrix_views": copy.deepcopy(
                _sequence_mapping(
                    shared.get("matrix_views", []),
                    field_name="analysis_view.shared_comparison.matrix_views",
                )
            ),
        },
        "wave_only_diagnostics": {
            "diagnostic_cards": copy.deepcopy(
                _sequence_mapping(
                    wave.get("diagnostic_cards", []),
                    field_name="analysis_view.wave_only_diagnostics.diagnostic_cards",
                )
            ),
            "phase_map_references": copy.deepcopy(
                _sequence_mapping(
                    wave.get("phase_map_references", []),
                    field_name="analysis_view.wave_only_diagnostics.phase_map_references",
                )
            ),
            "matrix_views": copy.deepcopy(
                _sequence_mapping(
                    wave.get("matrix_views", []),
                    field_name="analysis_view.wave_only_diagnostics.matrix_views",
                )
            ),
        },
        "validation_evidence": {
            "status_card": copy.deepcopy(
                _mapping(
                    validation.get("status_card", {}),
                    field_name="analysis_view.validation_evidence.status_card",
                )
            ),
            "validator_summaries": copy.deepcopy(
                _sequence_mapping(
                    validation.get("validator_summaries", []),
                    field_name="analysis_view.validation_evidence.validator_summaries",
                )
            ),
            "open_findings": copy.deepcopy(
                _sequence_mapping(
                    validation.get("open_findings", []),
                    field_name="analysis_view.validation_evidence.open_findings",
                )
            ),
        },
        "summary": {
            "export_kind": "metrics_export",
            "pane_id": ANALYSIS_PANE_ID,
            "task_summary_card_count": len(shared.get("task_summary_cards", [])),
            "matrix_view_count": len(shared.get("matrix_views", [])) + len(wave.get("matrix_views", [])),
            "phase_map_reference_count": len(wave.get("phase_map_references", [])),
            "open_finding_count": len(validation.get("open_findings", [])),
            "active_overlay_id": str(state["active_overlay_id"]),
            "selected_neuron_id": int(state["selected_neuron_id"]),
            "selected_readout_id": str(state["selected_readout_id"]),
        },
    }


def _build_time_series_metrics_payload(
    *,
    source: Mapping[str, Any],
    export_state: Mapping[str, Any],
) -> dict[str, Any]:
    time_series_context = _pane_context(source["payload"], TIME_SERIES_PANE_ID)
    state = export_state["global_interaction_state"]
    time_series_view = resolve_dashboard_time_series_view_model(
        time_series_context,
        selected_neuron_id=int(state["selected_neuron_id"]),
        selected_readout_id=str(state["selected_readout_id"]),
        comparison_mode=str(state["comparison_mode"]),
        active_arm_id=str(state["selected_arm_pair"]["active_arm_id"]),
        sample_index=int(state["time_cursor"]["sample_index"]),
    )
    return {
        "format_version": DASHBOARD_METRICS_EXPORT_VERSION,
        "pane_id": TIME_SERIES_PANE_ID,
        "bundle_reference": {
            "bundle_id": str(source["metadata"]["bundle_id"]),
            "experiment_id": str(source["metadata"]["experiment_id"]),
        },
        "global_interaction_state": copy.deepcopy(dict(state)),
        "replay_state": copy.deepcopy(dict(export_state["replay_state"])),
        "time_series_view": copy.deepcopy(dict(time_series_view)),
        "summary": {
            "export_kind": "metrics_export",
            "pane_id": TIME_SERIES_PANE_ID,
            "chart_series_count": len(
                _mapping(
                    time_series_view.get("shared_comparison", {}),
                    field_name="time_series_view.shared_comparison",
                ).get("chart_series", [])
            ),
            "selected_neuron_id": int(state["selected_neuron_id"]),
            "selected_readout_id": str(state["selected_readout_id"]),
            "sample_index": int(state["time_cursor"]["sample_index"]),
        },
    }


def _render_snapshot_image(
    *,
    source: Mapping[str, Any],
    pane_id: str,
    export_state: Mapping[str, Any],
) -> Image.Image:
    if pane_id == ANALYSIS_PANE_ID:
        return _render_analysis_snapshot_image(
            source=source,
            export_state=export_state,
        )
    if pane_id == TIME_SERIES_PANE_ID:
        return _render_time_series_frame_image(
            source=source,
            export_state=export_state,
            sample_index=int(
                export_state["global_interaction_state"]["time_cursor"]["sample_index"]
            ),
        )
    if pane_id == SCENE_PANE_ID:
        scene_context = _pane_context(source["payload"], SCENE_PANE_ID)
        sample_index = int(
            export_state["global_interaction_state"]["time_cursor"]["sample_index"]
        )
        frames = _sequence_mapping(
            scene_context.get("replay_frames", []),
            field_name="scene_context.replay_frames",
        )
        if not frames:
            raise ValueError("Scene snapshot export requires packaged replay_frames.")
        return _render_scene_frame_png(
            frames[min(sample_index, len(frames) - 1)]
        )
    return _render_generic_snapshot_image(
        source=source,
        pane_id=pane_id,
        export_state=export_state,
    )


def _render_analysis_snapshot_image(
    *,
    source: Mapping[str, Any],
    export_state: Mapping[str, Any],
) -> Image.Image:
    analysis_context = _pane_context(source["payload"], ANALYSIS_PANE_ID)
    time_series_context = _pane_context(source["payload"], TIME_SERIES_PANE_ID)
    state = export_state["global_interaction_state"]
    analysis_view = resolve_dashboard_analysis_view_model(
        analysis_context,
        time_series_context=time_series_context,
        selected_neuron_id=int(state["selected_neuron_id"]),
        selected_readout_id=str(state["selected_readout_id"]),
        comparison_mode=str(state["comparison_mode"]),
        active_arm_id=str(state["selected_arm_pair"]["active_arm_id"]),
        active_overlay_id=str(state["active_overlay_id"]),
        sample_index=int(state["time_cursor"]["sample_index"]),
    )
    image = Image.new("RGB", (1280, 960), (245, 242, 234))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    _draw_header(
        draw=draw,
        title="Milestone 14 Analysis Snapshot",
        subtitle=str(source["metadata"]["bundle_id"]),
        width=image.size[0],
        font=font,
    )
    y = 104
    y = _draw_info_box(
        draw=draw,
        box=(32, y, 1248, y + 92),
        title="Linked state",
        rows=[
            f"Overlay: {state['active_overlay_id']}",
            f"Comparison: {state['comparison_mode']}",
            f"Neuron: {state['selected_neuron_id']}",
            f"Readout: {state['selected_readout_id']}",
            f"Cursor: {state['time_cursor']['time_ms']:.1f} ms @ sample {state['time_cursor']['sample_index']}",
        ],
        font=font,
    )
    y += 112
    active_overlay = _mapping(
        analysis_view.get("active_overlay"),
        field_name="analysis_view.active_overlay",
    )
    y = _draw_info_box(
        draw=draw,
        box=(32, y, 606, y + 128),
        title="Active overlay",
        rows=[
            f"Scope: {active_overlay.get('scope_label', 'n/a')}",
            f"Availability: {active_overlay.get('availability', 'unknown')}",
            f"Reason: {active_overlay.get('reason', 'none')}",
        ],
        font=font,
    )
    shared = _mapping(
        analysis_view.get("shared_comparison"),
        field_name="analysis_view.shared_comparison",
    )
    _draw_info_box(
        draw=draw,
        box=(642, y - 128, 1248, y),
        title="Shared comparison counts",
        rows=[
            f"Task cards: {len(shared.get('task_summary_cards', []))}",
            f"Comparison cards: {len(shared.get('comparison_cards', []))}",
            f"Ablations: {len(shared.get('ablation_summaries', []))}",
            f"Matrices: {len(shared.get('matrix_views', []))}",
        ],
        font=font,
    )
    y += 24
    wave = _mapping(
        analysis_view.get("wave_only_diagnostics"),
        field_name="analysis_view.wave_only_diagnostics",
    )
    validation = _mapping(
        analysis_view.get("validation_evidence"),
        field_name="analysis_view.validation_evidence",
    )
    _draw_info_box(
        draw=draw,
        box=(32, y, 606, y + 144),
        title="Wave diagnostics",
        rows=[
            f"Diagnostic cards: {len(wave.get('diagnostic_cards', []))}",
            f"Phase maps: {len(wave.get('phase_map_references', []))}",
            f"Matrices: {len(wave.get('matrix_views', []))}",
        ],
        font=font,
    )
    status_card = _mapping(
        validation.get("status_card", {}),
        field_name="analysis_view.validation_evidence.status_card",
    )
    _draw_info_box(
        draw=draw,
        box=(642, y, 1248, y + 144),
        title="Validation evidence",
        rows=[
            f"Overall: {status_card.get('overall_status', 'unknown')}",
            f"Review: {status_card.get('review_status', 'unknown')}",
            f"Open findings: {status_card.get('open_finding_count', 0)}",
            f"Validators: {len(validation.get('validator_summaries', []))}",
        ],
        font=font,
    )
    matrix_views = _sequence_mapping(
        shared.get("matrix_views", []),
        field_name="analysis_view.shared_comparison.matrix_views",
    )
    if matrix_views:
        _draw_matrix_preview(
            draw=draw,
            matrix=matrix_views[0],
            box=(32, 520, 1248, 900),
            font=font,
        )
    return image


def _render_generic_snapshot_image(
    *,
    source: Mapping[str, Any],
    pane_id: str,
    export_state: Mapping[str, Any],
) -> Image.Image:
    image = Image.new("RGB", (960, 640), (245, 242, 234))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    _draw_header(
        draw=draw,
        title=f"Milestone 14 {pane_id} Snapshot",
        subtitle=str(source["metadata"]["bundle_id"]),
        width=image.size[0],
        font=font,
    )
    state = export_state["global_interaction_state"]
    _draw_info_box(
        draw=draw,
        box=(32, 112, 928, 320),
        title="Linked state summary",
        rows=[
            f"Pane: {pane_id}",
            f"Overlay: {state['active_overlay_id']}",
            f"Comparison: {state['comparison_mode']}",
            f"Neuron: {state['selected_neuron_id']}",
            f"Readout: {state['selected_readout_id']}",
            f"Cursor: {state['time_cursor']['time_ms']:.1f} ms @ sample {state['time_cursor']['sample_index']}",
        ],
        font=font,
    )
    return image


def _render_time_series_frame_image(
    *,
    source: Mapping[str, Any],
    export_state: Mapping[str, Any],
    sample_index: int,
) -> Image.Image:
    time_series_context = _pane_context(source["payload"], TIME_SERIES_PANE_ID)
    state = copy.deepcopy(dict(export_state["global_interaction_state"]))
    state["time_cursor"]["sample_index"] = int(sample_index)
    state["time_cursor"]["time_ms"] = float(
        _mapping(
            _mapping(time_series_context.get("replay_model"), field_name="time_series_context.replay_model"),
            field_name="time_series_context.replay_model",
        )["canonical_time_ms"][sample_index]
    )
    view = resolve_dashboard_time_series_view_model(
        time_series_context,
        selected_neuron_id=int(state["selected_neuron_id"]),
        selected_readout_id=str(state["selected_readout_id"]),
        comparison_mode=str(state["comparison_mode"]),
        active_arm_id=str(state["selected_arm_pair"]["active_arm_id"]),
        sample_index=int(sample_index),
    )
    image = Image.new("RGB", (1280, 720), (245, 242, 234))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    _draw_header(
        draw=draw,
        title="Milestone 14 Time-Series Replay",
        subtitle=str(source["metadata"]["bundle_id"]),
        width=image.size[0],
        font=font,
    )
    shared = _mapping(view.get("shared_comparison"), field_name="time_series_view.shared_comparison")
    series = _sequence_mapping(
        shared.get("chart_series", []),
        field_name="time_series_view.shared_comparison.chart_series",
    )
    _draw_line_chart(
        draw=draw,
        box=(48, 132, 1232, 540),
        series=series,
        cursor_index=int(sample_index),
    )
    _draw_info_box(
        draw=draw,
        box=(48, 572, 1232, 688),
        title="Selection",
        rows=[
            f"Readout: {shared.get('display_name', shared.get('readout_id', 'n/a'))}",
            f"Comparison mode: {state['comparison_mode']}",
            f"Baseline: {shared.get('baseline_value', 0.0):.3f}",
            f"Wave: {shared.get('wave_value', 0.0):.3f}",
            f"Delta: {shared.get('delta_value', 0.0):.3f}",
            f"Cursor: {view['cursor']['time_ms']:.1f} ms @ sample {view['cursor']['sample_index']}",
        ],
        font=font,
    )
    return image


def _render_scene_frame_png(frame: Mapping[str, Any]) -> Image.Image:
    pixels = _decode_scene_frame(frame)
    image = Image.fromarray(pixels, mode="L")
    scale = max(1, int(round(360 / max(1, image.size[1]))))
    return image.resize(
        (image.size[0] * scale, image.size[1] * scale),
        resample=Image.Resampling.NEAREST,
    ).convert("RGB")


def _draw_header(
    *,
    draw: ImageDraw.ImageDraw,
    title: str,
    subtitle: str,
    width: int,
    font: ImageFont.ImageFont,
) -> None:
    draw.rectangle((0, 0, width, 80), fill=(18, 69, 89))
    draw.text((28, 18), title, fill=(255, 255, 255), font=font)
    draw.text((28, 44), subtitle, fill=(219, 235, 236), font=font)


def _draw_info_box(
    *,
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    rows: Sequence[str],
    font: ImageFont.ImageFont,
) -> int:
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=18, fill=(255, 255, 255), outline=(207, 213, 214))
    draw.text((left + 16, top + 14), title, fill=(31, 41, 51), font=font)
    y = top + 40
    for row in rows:
        if y > bottom - 20:
            break
        draw.text((left + 16, y), str(row), fill=(91, 103, 112), font=font)
        y += 18
    return bottom


def _draw_matrix_preview(
    *,
    draw: ImageDraw.ImageDraw,
    matrix: Mapping[str, Any],
    box: tuple[int, int, int, int],
    font: ImageFont.ImageFont,
) -> None:
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=18, fill=(255, 255, 255), outline=(207, 213, 214))
    draw.text(
        (left + 16, top + 14),
        f"Matrix preview: {matrix.get('matrix_id', 'matrix')}",
        fill=(31, 41, 51),
        font=font,
    )
    values = _matrix_numeric_values(matrix)
    if values.size == 0:
        draw.text((left + 16, top + 40), "No numeric values are packaged for this matrix.", fill=(91, 103, 112), font=font)
        return
    rows = min(len(matrix.get("row_axis", {}).get("ids", [])), 6)
    cols = min(len(matrix.get("column_axis", {}).get("ids", [])), 8)
    cell_left = left + 16
    cell_top = top + 54
    cell_width = max(24, (right - left - 32) // max(1, cols))
    cell_height = max(24, (bottom - top - 74) // max(1, rows))
    min_value = float(np.min(values))
    max_value = float(np.max(values))
    span = max(max_value - min_value, 1.0e-9)
    matrix_values = matrix.get("values", [])
    for row_index in range(rows):
        row = matrix_values[row_index] if row_index < len(matrix_values) else []
        for col_index in range(cols):
            value = row[col_index] if col_index < len(row) else None
            x0 = cell_left + col_index * cell_width
            y0 = cell_top + row_index * cell_height
            x1 = x0 + cell_width - 4
            y1 = y0 + cell_height - 4
            if isinstance(value, (int, float)):
                t = (float(value) - min_value) / span
                fill = (
                    int(232 - 64 * t),
                    int(246 - 88 * t),
                    int(244 - 76 * t),
                )
                label = f"{float(value):.2f}"
            else:
                fill = (241, 242, 242)
                label = "n/a"
            draw.rounded_rectangle((x0, y0, x1, y1), radius=6, fill=fill, outline=(224, 227, 228))
            draw.text((x0 + 4, y0 + 8), label, fill=(31, 41, 51), font=font)


def _draw_line_chart(
    *,
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    series: Sequence[Mapping[str, Any]],
    cursor_index: int,
) -> None:
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=18, fill=(255, 255, 255), outline=(207, 213, 214))
    inner_left = left + 32
    inner_top = top + 20
    inner_right = right - 24
    inner_bottom = bottom - 28
    all_values: list[float] = []
    sample_count = 0
    for item in series:
        values = [
            float(value)
            for value in item.get("values", [])
            if isinstance(value, (int, float))
        ]
        if values:
            all_values.extend(values)
            sample_count = max(sample_count, len(values))
    if not all_values or sample_count < 2:
        return
    min_value = min(all_values)
    max_value = max(all_values)
    span = max(max_value - min_value, 1.0e-9)
    colors = [
        (74, 90, 102),
        (10, 92, 99),
        (181, 106, 43),
    ]
    for index, item in enumerate(series):
        values = [
            float(value)
            for value in item.get("values", [])
        ]
        if len(values) < 2:
            continue
        points = []
        for sample, value in enumerate(values):
            x = inner_left + (inner_right - inner_left) * sample / float(max(1, len(values) - 1))
            y = inner_bottom - (inner_bottom - inner_top) * (value - min_value) / span
            points.append((x, y))
        draw.line(points, fill=colors[index % len(colors)], width=3)
    cursor_x = inner_left + (inner_right - inner_left) * cursor_index / float(max(1, sample_count - 1))
    draw.line((cursor_x, inner_top, cursor_x, inner_bottom), fill=(120, 111, 104), width=2)


def _load_dashboard_source(metadata_path: Path) -> dict[str, Any]:
    metadata = load_dashboard_session_metadata(metadata_path)
    bundle_paths = discover_dashboard_session_bundle_paths(metadata)
    payload = _load_json_mapping(
        bundle_paths[SESSION_PAYLOAD_ARTIFACT_ID].resolve(),
        field_name="dashboard_session_payload",
    )
    session_state = _load_json_mapping(
        bundle_paths[SESSION_STATE_ARTIFACT_ID].resolve(),
        field_name="dashboard_session_state",
    )
    return {
        "metadata": metadata,
        "bundle_paths": bundle_paths,
        "payload": payload,
        "session_state": session_state,
    }


def _resolve_export_state(
    *,
    payload: Mapping[str, Any],
    session_state: Mapping[str, Any],
    sample_index: int | None,
    selected_neuron_id: int | None,
    selected_readout_id: str | None,
    active_overlay_id: str | None,
    comparison_mode: str | None,
    active_arm_id: str | None,
) -> dict[str, Any]:
    global_state = copy.deepcopy(
        dict(
            _mapping(
                session_state.get("global_interaction_state", {}),
                field_name="session_state.global_interaction_state",
            )
        )
    )
    time_series_context = _pane_context(payload, TIME_SERIES_PANE_ID)
    morphology_context = _pane_context(payload, MORPHOLOGY_PANE_ID)
    replay_model = _mapping(
        time_series_context.get("replay_model", {}),
        field_name="time_series_context.replay_model",
    )
    if active_arm_id is not None:
        arm_ids = {
            str(global_state["selected_arm_pair"]["baseline_arm_id"]),
            str(global_state["selected_arm_pair"]["wave_arm_id"]),
        }
        if str(active_arm_id) not in arm_ids:
            raise ValueError(
                f"active_arm_id must be one of {sorted(arm_ids)!r}, got {active_arm_id!r}."
            )
        global_state["selected_arm_pair"]["active_arm_id"] = str(active_arm_id)
    if selected_neuron_id is not None:
        root_ids = {
            int(item["root_id"])
            for item in _sequence_mapping(
                morphology_context.get("root_catalog", []),
                field_name="morphology_context.root_catalog",
            )
        }
        if int(selected_neuron_id) not in root_ids:
            raise ValueError(
                f"selected_neuron_id must be one of {sorted(root_ids)!r}, got {selected_neuron_id!r}."
            )
        global_state["selected_neuron_id"] = int(selected_neuron_id)
    if selected_readout_id is not None:
        readout_ids = {
            str(item["readout_id"])
            for item in _sequence_mapping(
                time_series_context.get("comparable_readout_catalog", []),
                field_name="time_series_context.comparable_readout_catalog",
            )
        }
        if str(selected_readout_id) not in readout_ids:
            raise ValueError(
                "selected_readout_id must be present in the dashboard shared readout "
                f"catalog {sorted(readout_ids)!r}, got {selected_readout_id!r}."
            )
        global_state["selected_readout_id"] = str(selected_readout_id)
    if active_overlay_id is not None:
        overlay_ids = {
            str(item["overlay_id"])
            for item in build_dashboard_session_contract_metadata()["overlay_catalog"]
        }
        if str(active_overlay_id) not in overlay_ids:
            raise ValueError(
                f"active_overlay_id must be one of {sorted(overlay_ids)!r}, got {active_overlay_id!r}."
            )
        global_state["active_overlay_id"] = str(active_overlay_id)
    if comparison_mode is not None:
        global_state["comparison_mode"] = str(comparison_mode)
    if sample_index is not None:
        global_state["time_cursor"]["sample_index"] = int(sample_index)
    replay_state = build_dashboard_replay_state(
        global_interaction_state=global_state,
        replay_model=replay_model,
    )
    global_state["time_cursor"] = copy.deepcopy(dict(replay_state["time_cursor"]))
    return {
        "global_interaction_state": global_state,
        "replay_state": replay_state,
    }


def _resolve_export_target_definition(
    *,
    contract_metadata: Mapping[str, Any],
    export_target_id: str,
    pane_id: str | None,
) -> dict[str, Any]:
    candidates = discover_dashboard_export_targets(
        contract_metadata,
        pane_id=pane_id,
    )
    match = next(
        (
            item
            for item in candidates
            if str(item["export_target_id"]) == str(export_target_id)
        ),
        None,
    )
    if match is None:
        supported = [
            str(item["export_target_id"])
            for item in discover_dashboard_export_targets(contract_metadata)
            if pane_id is None or pane_id in item["supported_pane_ids"]
        ]
        raise ValueError(
            f"Export target {export_target_id!r} is not supported for pane_id {pane_id!r}. "
            f"Supported targets: {supported!r}."
        )
    return copy.deepcopy(dict(match))


def _resolve_pane_id(
    *,
    export_target_id: str,
    pane_id: str | None,
) -> str | None:
    if pane_id is not None:
        return str(pane_id)
    if export_target_id == SESSION_STATE_EXPORT_TARGET_ID:
        return None
    if export_target_id in {PANE_SNAPSHOT_EXPORT_TARGET_ID, METRICS_EXPORT_TARGET_ID}:
        return ANALYSIS_PANE_ID
    if export_target_id == REPLAY_FRAME_SEQUENCE_EXPORT_TARGET_ID:
        return SCENE_PANE_ID
    return None


def _build_export_spec_hash(
    *,
    bundle_id: str,
    export_target_id: str,
    pane_id: str | None,
    global_interaction_state: Mapping[str, Any],
) -> str:
    payload = {
        "bundle_id": str(bundle_id),
        "export_target_id": str(export_target_id),
        "pane_id": pane_id,
        "global_interaction_state": copy.deepcopy(dict(global_interaction_state)),
    }
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _pane_context(payload: Mapping[str, Any], pane_id: str) -> dict[str, Any]:
    pane_inputs = _mapping(payload.get("pane_inputs", {}), field_name="payload.pane_inputs")
    return _load_mapping(
        pane_inputs.get(pane_id, {}),
        field_name=f"payload.pane_inputs[{pane_id!r}]",
    )


def _decode_scene_frame(frame: Mapping[str, Any]) -> np.ndarray:
    height = int(frame["height"])
    width = int(frame["width"])
    pixels = base64.b64decode(str(frame["pixels_b64"]))
    array = np.frombuffer(pixels, dtype=np.uint8)
    if array.size != height * width:
        raise ValueError("Scene frame pixel buffer does not match height/width.")
    return array.reshape((height, width))


def _artifact_record(
    *,
    artifact_id: str,
    path: str | Path,
    format: str,
    media_type: str,
) -> dict[str, Any]:
    resolved = Path(path).resolve()
    return {
        "artifact_id": str(artifact_id),
        "path": str(resolved),
        "format": str(format),
        "media_type": str(media_type),
        "byte_size": resolved.stat().st_size,
        "content_hash": hashlib.sha256(resolved.read_bytes()).hexdigest(),
    }


def _load_json_mapping(path: Path, *, field_name: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping JSON payload.")
    return copy.deepcopy(dict(payload))


def _mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value


def _load_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    return copy.deepcopy(dict(_mapping(value, field_name=field_name)))


def _sequence_mapping(value: Any, *, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence of mappings.")
    return [
        copy.deepcopy(dict(_mapping(item, field_name=f"{field_name}[]")))
        for item in value
    ]


def _matrix_numeric_values(matrix: Mapping[str, Any]) -> np.ndarray:
    values = [
        float(cell)
        for row in matrix.get("values", [])
        if isinstance(row, Sequence)
        for cell in row
        if isinstance(cell, (int, float))
    ]
    return np.asarray(values, dtype=np.float64)


def _require_pane_id(pane_id: str | None, *, target_kind: str) -> str:
    if pane_id is None:
        raise ValueError(f"pane_id is required for export target kind {target_kind!r}.")
    return str(pane_id)


def _pane_directory_name(pane_id: str | None) -> str:
    return "session" if pane_id is None else str(pane_id)


__all__ = [
    "DASHBOARD_EXPORT_METADATA_VERSION",
    "DASHBOARD_FRAME_SEQUENCE_MANIFEST_VERSION",
    "DASHBOARD_METRICS_EXPORT_VERSION",
    "DEFAULT_DASHBOARD_EXPORT_DIRECTORY_NAME",
    "execute_dashboard_export",
]
