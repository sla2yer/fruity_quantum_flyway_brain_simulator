from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .dashboard_session_contract import (
    PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
    PAIRED_DELTA_COMPARISON_MODE,
    PLAYBACK_PAUSED,
    SINGLE_ARM_COMPARISON_MODE,
    TIME_SERIES_PANE_ID,
)
from .dashboard_session_contract import build_dashboard_time_cursor
from .simulator_result_contract import (
    load_simulator_shared_readout_payload,
    normalize_simulator_timebase,
)
from .stimulus_contract import DEFAULT_HASH_ALGORITHM, _normalize_identifier


DASHBOARD_REPLAY_MODEL_VERSION = "dashboard_replay_model.v1"
DASHBOARD_REPLAY_STATE_VERSION = "dashboard_replay_state.v1"
DASHBOARD_TIME_SERIES_CONTEXT_VERSION = "dashboard_time_series_context.v1"
DASHBOARD_TIME_SERIES_VIEW_MODEL_VERSION = "dashboard_time_series_view_model.v1"

_SUPPORTED_REPLAY_COMPARISON_MODES = (
    SINGLE_ARM_COMPARISON_MODE,
    PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
    PAIRED_DELTA_COMPARISON_MODE,
)


def build_dashboard_replay_model(
    *,
    baseline_arm_id: str,
    wave_arm_id: str | None,
    baseline_timebase: Mapping[str, Any],
    wave_timebase: Mapping[str, Any] | None,
) -> dict[str, Any]:
    normalized_baseline_timebase = normalize_simulator_timebase(baseline_timebase)
    normalized_wave_timebase = (
        None if wave_timebase is None else normalize_simulator_timebase(wave_timebase)
    )
    canonical_time_ms = _timebase_time_samples(normalized_baseline_timebase)
    distinct_arm_pair = (
        wave_arm_id is not None
        and _normalize_identifier(baseline_arm_id, field_name="baseline_arm_id")
        != _normalize_identifier(wave_arm_id, field_name="wave_arm_id")
    )
    shared_timebase_compatible = (
        normalized_wave_timebase is not None
        and normalized_baseline_timebase == normalized_wave_timebase
    )
    pair_reason = None
    if not distinct_arm_pair:
        pair_reason = (
            "session does not expose one distinct baseline-versus-wave arm pair"
        )
    shared_timebase_reason = None
    if normalized_wave_timebase is None:
        shared_timebase_reason = "wave arm metadata is missing for shared-timebase replay"
    elif not shared_timebase_compatible:
        shared_timebase_reason = (
            "session does not expose baseline and wave traces on one canonical shared timebase"
        )

    comparison_mode_statuses = []
    for comparison_mode_id in _SUPPORTED_REPLAY_COMPARISON_MODES:
        reason = None
        if comparison_mode_id != SINGLE_ARM_COMPARISON_MODE:
            if pair_reason is not None:
                reason = pair_reason
            elif shared_timebase_reason is not None:
                reason = shared_timebase_reason
        comparison_mode_statuses.append(
            {
                "comparison_mode_id": comparison_mode_id,
                "availability": "available" if reason is None else "unavailable",
                "reason": reason,
            }
        )

    return {
        "format_version": DASHBOARD_REPLAY_MODEL_VERSION,
        "hash_algorithm": DEFAULT_HASH_ALGORITHM,
        "timebase": copy.deepcopy(dict(normalized_baseline_timebase)),
        "timebase_signature": _stable_hash_payload(normalized_baseline_timebase),
        "canonical_time_ms": canonical_time_ms.astype(np.float64).tolist(),
        "time_cursor_bounds": {
            "min_sample_index": 0,
            "max_sample_index": max(0, int(normalized_baseline_timebase["sample_count"]) - 1),
        },
        "playback_interval_ms": int(
            max(
                180,
                min(
                    900,
                    round(max(float(normalized_baseline_timebase["dt_ms"]), 1.0) * 18.0),
                ),
            )
        ),
        "selected_pair_status": {
            "baseline_arm_id": _normalize_identifier(
                baseline_arm_id,
                field_name="baseline_arm_id",
            ),
            "wave_arm_id": (
                None
                if wave_arm_id is None
                else _normalize_identifier(wave_arm_id, field_name="wave_arm_id")
            ),
            "has_distinct_arm_pair": bool(distinct_arm_pair),
            "reason": pair_reason,
        },
        "shared_timebase_status": {
            "availability": (
                "available" if shared_timebase_reason is None else "unavailable"
            ),
            "reason": shared_timebase_reason,
        },
        "comparison_mode_statuses": comparison_mode_statuses,
    }


def build_dashboard_replay_state(
    *,
    global_interaction_state: Mapping[str, Any],
    replay_model: Mapping[str, Any],
) -> dict[str, Any]:
    interaction = _require_mapping(
        global_interaction_state,
        field_name="global_interaction_state",
    )
    normalized_replay_model = _require_mapping(
        replay_model,
        field_name="replay_model",
    )
    selected_mode = _normalize_identifier(
        interaction["comparison_mode"],
        field_name="global_interaction_state.comparison_mode",
    )
    _require_available_comparison_mode(
        normalized_replay_model,
        comparison_mode=selected_mode,
    )
    cursor = build_dashboard_time_cursor(
        time_ms=float(_cursor_time_ms(normalized_replay_model, interaction["time_cursor"])),
        sample_index=int(
            _clamp_sample_index(
                interaction["time_cursor"]["sample_index"],
                replay_model=normalized_replay_model,
            )
        ),
        playback_state=str(interaction["time_cursor"]["playback_state"]),
    )
    return {
        "format_version": DASHBOARD_REPLAY_STATE_VERSION,
        "timebase_signature": str(normalized_replay_model["timebase_signature"]),
        "playback_interval_ms": int(normalized_replay_model["playback_interval_ms"]),
        "selected_arm_pair": copy.deepcopy(dict(interaction["selected_arm_pair"])),
        "selected_neuron_id": interaction["selected_neuron_id"],
        "selected_readout_id": interaction["selected_readout_id"],
        "active_overlay_id": str(interaction["active_overlay_id"]),
        "comparison_mode": selected_mode,
        "time_cursor": cursor,
        "comparison_mode_statuses": copy.deepcopy(
            list(normalized_replay_model["comparison_mode_statuses"])
        ),
    }


def build_dashboard_time_series_context(
    *,
    baseline_metadata: Mapping[str, Any],
    wave_metadata: Mapping[str, Any],
    morphology_context: Mapping[str, Any],
    selected_readout_id: str | None,
) -> dict[str, Any]:
    baseline_record = _require_mapping(
        baseline_metadata,
        field_name="baseline_metadata",
    )
    wave_record = _require_mapping(wave_metadata, field_name="wave_metadata")
    morphology = _require_mapping(
        morphology_context,
        field_name="morphology_context",
    )

    replay_model = build_dashboard_replay_model(
        baseline_arm_id=str(baseline_record["arm_reference"]["arm_id"]),
        wave_arm_id=str(wave_record["arm_reference"]["arm_id"]),
        baseline_timebase=baseline_record["timebase"],
        wave_timebase=wave_record["timebase"],
    )
    _require_available_comparison_mode(
        replay_model,
        comparison_mode=PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
    )
    comparable_readouts = _comparable_readout_catalog(
        baseline_record["readout_catalog"],
        wave_record["readout_catalog"],
    )
    if not comparable_readouts:
        raise ValueError(
            "Dashboard time-series context requires at least one shared comparable readout."
        )

    baseline_payload = load_simulator_shared_readout_payload(baseline_record)
    wave_payload = load_simulator_shared_readout_payload(wave_record)
    canonical_time_ms = np.asarray(
        replay_model["canonical_time_ms"],
        dtype=np.float64,
    )
    _validate_shared_trace_payload(
        payload=baseline_payload,
        time_ms=canonical_time_ms,
        field_name="baseline_shared_readout_payload",
    )
    _validate_shared_trace_payload(
        payload=wave_payload,
        time_ms=canonical_time_ms,
        field_name="wave_shared_readout_payload",
    )

    baseline_index_by_id = {
        str(readout_id): index
        for index, readout_id in enumerate(baseline_payload["readout_ids"])
    }
    wave_index_by_id = {
        str(readout_id): index
        for index, readout_id in enumerate(wave_payload["readout_ids"])
    }
    shared_trace_catalog = []
    for definition in comparable_readouts:
        readout_id = str(definition["readout_id"])
        if readout_id not in baseline_index_by_id or readout_id not in wave_index_by_id:
            raise ValueError(
                "Dashboard time-series context requires shared trace arrays for every "
                f"comparable readout_id, missing {readout_id!r}."
            )
        baseline_series = np.asarray(
            baseline_payload["values"][:, baseline_index_by_id[readout_id]],
            dtype=np.float64,
        )
        wave_series = np.asarray(
            wave_payload["values"][:, wave_index_by_id[readout_id]],
            dtype=np.float64,
        )
        delta_series = wave_series - baseline_series
        combined_domain = np.asarray(
            [
                *baseline_series.tolist(),
                *wave_series.tolist(),
                *delta_series.tolist(),
            ],
            dtype=np.float64,
        )
        shared_trace_catalog.append(
            {
                "readout_id": readout_id,
                "display_name": _readout_display_name(definition),
                "scope": str(definition["scope"]),
                "aggregation": str(definition["aggregation"]),
                "units": str(definition["units"]),
                "value_semantics": str(definition["value_semantics"]),
                "description": definition.get("description"),
                "scope_label": "shared_comparison",
                "time_ms": canonical_time_ms.astype(np.float64).tolist(),
                "baseline_values": baseline_series.astype(np.float64).tolist(),
                "wave_values": wave_series.astype(np.float64).tolist(),
                "delta_values": delta_series.astype(np.float64).tolist(),
                "abs_value_scale": float(
                    max(
                        np.max(np.abs(np.asarray([baseline_series, wave_series]))),
                        1.0e-9,
                    )
                ),
                "abs_delta_scale": float(
                    max(np.max(np.abs(delta_series)), 1.0e-9)
                ),
                "cursor_alignment_ms": 0.0,
            }
        )

    comparable_readout_catalog = [
        {
            "readout_id": str(item["readout_id"]),
            "display_name": _readout_display_name(item),
            "scope": str(item["scope"]),
            "aggregation": str(item["aggregation"]),
            "units": str(item["units"]),
            "value_semantics": str(item["value_semantics"]),
            "description": item.get("description"),
        }
        for item in comparable_readouts
    ]
    resolved_selected_readout_id = _resolve_selected_readout_id(
        readout_catalog=comparable_readout_catalog,
        selected_readout_id=selected_readout_id,
    )

    selection_catalog = _selection_catalog(
        morphology_context=morphology,
        comparable_readout_catalog=comparable_readout_catalog,
        canonical_time_ms=canonical_time_ms,
    )

    return {
        "pane_id": TIME_SERIES_PANE_ID,
        "context_version": DASHBOARD_TIME_SERIES_CONTEXT_VERSION,
        "timebase": copy.deepcopy(dict(replay_model["timebase"])),
        "replay_model": replay_model,
        "selected_readout_id": resolved_selected_readout_id,
        "comparable_readout_catalog": comparable_readout_catalog,
        "shared_trace_catalog": shared_trace_catalog,
        "selection_catalog": selection_catalog,
        "trace_sources": {
            "baseline": {
                "bundle_id": str(baseline_record["bundle_id"]),
                "readout_trace_payload_path": str(baseline_payload["path"]),
            },
            "wave": {
                "bundle_id": str(wave_record["bundle_id"]),
                "readout_trace_payload_path": str(wave_payload["path"]),
            },
        },
    }


def resolve_dashboard_time_series_view_model(
    time_series_context: Mapping[str, Any],
    *,
    selected_neuron_id: int,
    selected_readout_id: str,
    comparison_mode: str,
    active_arm_id: str,
    sample_index: int,
) -> dict[str, Any]:
    context = _require_mapping(
        time_series_context,
        field_name="time_series_context",
    )
    replay_model = _require_mapping(
        context["replay_model"],
        field_name="time_series_context.replay_model",
    )
    normalized_comparison_mode = _normalize_identifier(
        comparison_mode,
        field_name="comparison_mode",
    )
    comparison_status = _require_available_comparison_mode(
        replay_model,
        comparison_mode=normalized_comparison_mode,
    )
    selected_trace = next(
        (
            _require_mapping(item, field_name="time_series_context.shared_trace_catalog[]")
            for item in context["shared_trace_catalog"]
            if str(
                _require_mapping(
                    item,
                    field_name="time_series_context.shared_trace_catalog[]",
                )["readout_id"]
            )
            == _normalize_identifier(
                selected_readout_id,
                field_name="selected_readout_id",
            )
        ),
        None,
    )
    if selected_trace is None:
        raise ValueError(
            f"selected_readout_id {selected_readout_id!r} is not packaged in time_series_context."
        )
    selected_root = next(
        (
            _require_mapping(item, field_name="time_series_context.selection_catalog[]")
            for item in context["selection_catalog"]
            if int(
                _require_mapping(
                    item,
                    field_name="time_series_context.selection_catalog[]",
                )["root_id"]
            )
            == int(selected_neuron_id)
        ),
        None,
    )
    if selected_root is None:
        raise ValueError(
            f"selected_neuron_id {int(selected_neuron_id)!r} is not packaged in time_series_context."
        )

    resolved_sample_index = _clamp_sample_index(
        sample_index,
        replay_model=replay_model,
    )
    time_ms = _cursor_time_ms(
        replay_model,
        {"sample_index": resolved_sample_index},
    )
    baseline_value = float(selected_trace["baseline_values"][resolved_sample_index])
    wave_value = float(selected_trace["wave_values"][resolved_sample_index])
    delta_value = float(selected_trace["delta_values"][resolved_sample_index])
    shared_chart = _shared_chart_series(
        trace=selected_trace,
        comparison_mode=normalized_comparison_mode,
        active_arm_id=active_arm_id,
        baseline_arm_id=str(replay_model["selected_pair_status"]["baseline_arm_id"]),
        wave_arm_id=str(replay_model["selected_pair_status"]["wave_arm_id"]),
        sample_index=resolved_sample_index,
    )
    wave_diagnostic = _resolved_wave_diagnostic(
        selected_root=selected_root,
        sample_index=resolved_sample_index,
    )
    return {
        "format_version": DASHBOARD_TIME_SERIES_VIEW_MODEL_VERSION,
        "cursor": {
            "sample_index": int(resolved_sample_index),
            "time_ms": float(time_ms),
        },
        "comparison_status": copy.deepcopy(dict(comparison_status)),
        "selected_root": {
            "root_id": int(selected_root["root_id"]),
            "cell_type": str(selected_root["cell_type"]),
            "morphology_class": str(selected_root["morphology_class"]),
            "shared_readout_ids": list(selected_root["shared_readout_ids"]),
        },
        "shared_comparison": {
            "scope_label": "shared_comparison",
            "readout_id": str(selected_trace["readout_id"]),
            "display_name": str(selected_trace["display_name"]),
            "units": str(selected_trace["units"]),
            "comparison_mode": normalized_comparison_mode,
            "baseline_value": baseline_value,
            "wave_value": wave_value,
            "delta_value": delta_value,
            "primary_value": float(shared_chart["primary_value"]),
            "chart_series": shared_chart["chart_series"],
            "primary_series_id": str(shared_chart["primary_series_id"]),
            "fairness_note": str(shared_chart["fairness_note"]),
        },
        "wave_diagnostic": wave_diagnostic,
    }


def _selection_catalog(
    *,
    morphology_context: Mapping[str, Any],
    comparable_readout_catalog: Sequence[Mapping[str, Any]],
    canonical_time_ms: np.ndarray,
) -> list[dict[str, Any]]:
    comparable_readout_ids = [
        str(item["readout_id"]) for item in comparable_readout_catalog
    ]
    selection_catalog = []
    for root in _require_sequence(
        morphology_context.get("root_catalog"),
        field_name="morphology_context.root_catalog",
    ):
        root_record = _require_mapping(
            root,
            field_name="morphology_context.root_catalog[]",
        )
        mixed_morphology = _require_mapping(
            root_record.get("mixed_morphology", {}),
            field_name="root_record.mixed_morphology",
        )
        shared_readout_ids = list(
            mixed_morphology.get("shared_readout_ids") or comparable_readout_ids
        )
        wave_overlay = _require_mapping(
            _require_mapping(
                root_record.get("overlay_samples", {}),
                field_name="root_record.overlay_samples",
            ).get("wave_patch_activity", {}),
            field_name="root_record.overlay_samples.wave_patch_activity",
        )
        selection_catalog.append(
            {
                "root_id": int(root_record["root_id"]),
                "cell_type": str(root_record.get("cell_type", "")),
                "morphology_class": str(root_record.get("morphology_class", "")),
                "shared_readout_ids": shared_readout_ids,
                "wave_diagnostic": _wave_diagnostic_record(
                    root_id=int(root_record["root_id"]),
                    wave_overlay=wave_overlay,
                    canonical_time_ms=canonical_time_ms,
                ),
            }
        )
    selection_catalog.sort(key=lambda item: int(item["root_id"]))
    return selection_catalog


def _wave_diagnostic_record(
    *,
    root_id: int,
    wave_overlay: Mapping[str, Any],
    canonical_time_ms: np.ndarray,
) -> dict[str, Any]:
    availability = str(wave_overlay.get("availability", "unavailable"))
    element_series = [
        _require_mapping(item, field_name="wave_overlay.element_series[]")
        for item in _require_sequence(
            wave_overlay.get("element_series", []),
            field_name="wave_overlay.element_series",
        )
    ]
    time_ms = np.asarray(wave_overlay.get("time_ms", []), dtype=np.float64)
    if availability != "available":
        return {
            "diagnostic_id": f"root_{int(root_id)}_wave_diagnostic",
            "scope_label": "wave_only_diagnostic",
            "availability": availability,
            "reason": str(
                wave_overlay.get(
                    "reason",
                    "wave-only diagnostics are unavailable for the selected root",
                )
            ),
            "root_id": int(root_id),
            "display_name": f"Root {int(root_id)} Wave Diagnostic",
            "units": "activation_au",
            "time_ms": [],
            "values": [],
            "projection_semantics": wave_overlay.get("projection_semantics"),
            "element_count": int(wave_overlay.get("element_count", 0)),
            "aligned_to_shared_timebase": False,
        }
    if len(element_series) == 0 or time_ms.size == 0:
        return {
            "diagnostic_id": f"root_{int(root_id)}_wave_diagnostic",
            "scope_label": "wave_only_diagnostic",
            "availability": "unavailable",
            "reason": "wave-only diagnostic trace is empty for the selected root",
            "root_id": int(root_id),
            "display_name": f"Root {int(root_id)} Wave Diagnostic",
            "units": "activation_au",
            "time_ms": [],
            "values": [],
            "projection_semantics": wave_overlay.get("projection_semantics"),
            "element_count": int(wave_overlay.get("element_count", 0)),
            "aligned_to_shared_timebase": False,
        }
    aligned = time_ms.shape == canonical_time_ms.shape and np.allclose(
        time_ms,
        canonical_time_ms,
        rtol=0.0,
        atol=1.0e-9,
    )
    if not aligned:
        return {
            "diagnostic_id": f"root_{int(root_id)}_wave_diagnostic",
            "scope_label": "wave_only_diagnostic",
            "availability": "unavailable",
            "reason": "wave-only diagnostic trace does not align to the canonical dashboard timebase",
            "root_id": int(root_id),
            "display_name": f"Root {int(root_id)} Wave Diagnostic",
            "units": "activation_au",
            "time_ms": time_ms.astype(np.float64).tolist(),
            "values": [],
            "projection_semantics": wave_overlay.get("projection_semantics"),
            "element_count": int(wave_overlay.get("element_count", 0)),
            "aligned_to_shared_timebase": False,
        }
    values = np.mean(
        np.asarray([item["values"] for item in element_series], dtype=np.float64),
        axis=0,
    )
    return {
        "diagnostic_id": f"root_{int(root_id)}_wave_diagnostic",
        "scope_label": "wave_only_diagnostic",
        "availability": "available",
        "reason": None,
        "root_id": int(root_id),
        "display_name": f"Root {int(root_id)} Wave Diagnostic",
        "units": "activation_au",
        "time_ms": time_ms.astype(np.float64).tolist(),
        "values": values.astype(np.float64).tolist(),
        "projection_semantics": wave_overlay.get("projection_semantics"),
        "element_count": int(wave_overlay.get("element_count", len(element_series))),
        "aligned_to_shared_timebase": True,
        "abs_value_scale": float(max(np.max(np.abs(values)), 1.0e-9)),
    }


def _resolved_wave_diagnostic(
    *,
    selected_root: Mapping[str, Any],
    sample_index: int,
) -> dict[str, Any]:
    diagnostic = _require_mapping(
        selected_root["wave_diagnostic"],
        field_name="selected_root.wave_diagnostic",
    )
    if str(diagnostic["availability"]) != "available":
        return copy.deepcopy(dict(diagnostic))
    resolved_sample_index = max(
        0,
        min(int(sample_index), len(diagnostic["time_ms"]) - 1),
    )
    result = copy.deepcopy(dict(diagnostic))
    result["sample_index"] = int(resolved_sample_index)
    result["time_ms"] = copy.deepcopy(list(diagnostic["time_ms"]))
    result["cursor_time_ms"] = float(diagnostic["time_ms"][resolved_sample_index])
    result["cursor_value"] = float(diagnostic["values"][resolved_sample_index])
    return result


def _shared_chart_series(
    *,
    trace: Mapping[str, Any],
    comparison_mode: str,
    active_arm_id: str,
    baseline_arm_id: str,
    wave_arm_id: str,
    sample_index: int,
) -> dict[str, Any]:
    baseline_series = list(trace["baseline_values"])
    wave_series = list(trace["wave_values"])
    delta_series = list(trace["delta_values"])
    if comparison_mode == PAIRED_DELTA_COMPARISON_MODE:
        return {
            "primary_series_id": "delta",
            "primary_value": float(delta_series[sample_index]) if delta_series else 0.0,
            "fairness_note": (
                "Shared delta view remains on the canonical paired timebase and does "
                "not absorb wave-only diagnostics."
            ),
            "chart_series": [
                {
                    "series_id": "delta",
                    "display_name": "Wave - Baseline",
                    "values": delta_series,
                    "scope_label": "shared_comparison",
                }
            ],
        }
    if comparison_mode == SINGLE_ARM_COMPARISON_MODE:
        use_wave = (
            _normalize_identifier(active_arm_id, field_name="active_arm_id")
            == _normalize_identifier(wave_arm_id, field_name="wave_arm_id")
        )
        active_values = wave_series if use_wave else baseline_series
        return {
            "primary_series_id": "wave" if use_wave else "baseline",
            "primary_value": float(active_values[sample_index]) if active_values else 0.0,
            "fairness_note": (
                "Single-arm replay still uses the shared readout surface, but only one "
                "arm is foregrounded at a time."
            ),
            "chart_series": [
                {
                    "series_id": "baseline" if not use_wave else "wave",
                    "display_name": (
                        "Wave" if use_wave else "Baseline"
                    ),
                    "values": active_values,
                    "scope_label": "shared_comparison",
                }
            ],
        }
    _normalize_identifier(baseline_arm_id, field_name="baseline_arm_id")
    _normalize_identifier(wave_arm_id, field_name="wave_arm_id")
    return {
        "primary_series_id": "paired",
        "primary_value": float(wave_series[sample_index]) if wave_series else 0.0,
        "fairness_note": (
            "Baseline-versus-wave replay is fairness-critical and stays on the shared "
            "readout catalog plus canonical shared timebase."
        ),
        "chart_series": [
            {
                "series_id": "baseline",
                "display_name": "Baseline",
                "values": baseline_series,
                "scope_label": "shared_comparison",
            },
            {
                "series_id": "wave",
                "display_name": "Wave",
                "values": wave_series,
                "scope_label": "shared_comparison",
            },
        ],
    }


def _resolve_selected_readout_id(
    *,
    readout_catalog: Sequence[Mapping[str, Any]],
    selected_readout_id: str | None,
) -> str:
    if not readout_catalog:
        raise ValueError("readout_catalog must not be empty.")
    if selected_readout_id is None:
        return str(readout_catalog[0]["readout_id"])
    normalized_selected_readout_id = _normalize_identifier(
        selected_readout_id,
        field_name="selected_readout_id",
    )
    if normalized_selected_readout_id not in {
        str(item["readout_id"]) for item in readout_catalog
    }:
        raise ValueError(
            f"selected_readout_id {normalized_selected_readout_id!r} is not present in the "
            "shared comparable readout catalog."
        )
    return normalized_selected_readout_id


def _validate_shared_trace_payload(
    *,
    payload: Mapping[str, Any],
    time_ms: np.ndarray,
    field_name: str,
) -> None:
    payload_time_ms = np.asarray(payload["time_ms"], dtype=np.float64)
    if payload_time_ms.shape != time_ms.shape or not np.allclose(
        payload_time_ms,
        time_ms,
        rtol=0.0,
        atol=1.0e-9,
    ):
        raise ValueError(
            f"{field_name} does not align to the canonical dashboard timebase."
        )


def _require_available_comparison_mode(
    replay_model: Mapping[str, Any],
    *,
    comparison_mode: str,
) -> dict[str, Any]:
    normalized_mode = _normalize_identifier(
        comparison_mode,
        field_name="comparison_mode",
    )
    status = next(
        (
            _require_mapping(item, field_name="replay_model.comparison_mode_statuses[]")
            for item in _require_sequence(
                replay_model.get("comparison_mode_statuses", []),
                field_name="replay_model.comparison_mode_statuses",
            )
            if str(
                _require_mapping(
                    item,
                    field_name="replay_model.comparison_mode_statuses[]",
                )["comparison_mode_id"]
            )
            == normalized_mode
        ),
        None,
    )
    if status is None:
        raise ValueError(
            f"comparison_mode {normalized_mode!r} is not declared in replay_model."
        )
    if str(status["availability"]) != "available":
        raise ValueError(
            f"Comparison mode {normalized_mode!r} is unavailable: {status['reason']}."
        )
    return copy.deepcopy(dict(status))


def _cursor_time_ms(
    replay_model: Mapping[str, Any],
    time_cursor: Mapping[str, Any],
) -> float:
    sample_index = _clamp_sample_index(
        time_cursor["sample_index"],
        replay_model=replay_model,
    )
    return float(replay_model["canonical_time_ms"][sample_index])


def _clamp_sample_index(
    sample_index: Any,
    *,
    replay_model: Mapping[str, Any],
) -> int:
    bounds = _require_mapping(
        replay_model.get("time_cursor_bounds", {}),
        field_name="replay_model.time_cursor_bounds",
    )
    return max(
        int(bounds["min_sample_index"]),
        min(
            int(bounds["max_sample_index"]),
            int(sample_index),
        ),
    )


def _comparable_readout_catalog(
    baseline_catalog: Sequence[Mapping[str, Any]],
    wave_catalog: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    wave_by_id = {
        str(item["readout_id"]): dict(item)
        for item in wave_catalog
    }
    comparable = []
    for baseline_item in baseline_catalog:
        readout_id = str(baseline_item["readout_id"])
        wave_item = wave_by_id.get(readout_id)
        if wave_item is None:
            continue
        for field_name in ("scope", "aggregation", "units", "value_semantics"):
            if str(baseline_item[field_name]) != str(wave_item[field_name]):
                raise ValueError(
                    "Dashboard replay requires matching baseline and wave readout "
                    f"definitions for readout_id {readout_id!r}."
                )
        comparable.append(copy.deepcopy(dict(baseline_item)))
    comparable.sort(key=lambda item: str(item["readout_id"]))
    return comparable


def _timebase_time_samples(timebase: Mapping[str, Any]) -> np.ndarray:
    normalized_timebase = normalize_simulator_timebase(timebase)
    return np.asarray(
        [
            float(normalized_timebase["time_origin_ms"])
            + float(normalized_timebase["dt_ms"]) * float(index)
            for index in range(int(normalized_timebase["sample_count"]))
        ],
        dtype=np.float64,
    )


def _stable_hash_payload(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _readout_display_name(readout_definition: Mapping[str, Any]) -> str:
    description = readout_definition.get("description")
    if isinstance(description, str) and description.strip():
        return description.strip()
    return str(readout_definition["readout_id"])


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value


def _require_sequence(value: Any, *, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence.")
    return value


__all__ = [
    "DASHBOARD_REPLAY_MODEL_VERSION",
    "DASHBOARD_REPLAY_STATE_VERSION",
    "DASHBOARD_TIME_SERIES_CONTEXT_VERSION",
    "DASHBOARD_TIME_SERIES_VIEW_MODEL_VERSION",
    "build_dashboard_replay_model",
    "build_dashboard_replay_state",
    "build_dashboard_time_series_context",
    "resolve_dashboard_time_series_view_model",
]
