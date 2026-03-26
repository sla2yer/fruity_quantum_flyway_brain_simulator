from __future__ import annotations

import copy
import json
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse as sp

from .readout_analysis_contract import (
    PER_WAVE_ROOT_SET_WINDOW_SCOPE,
    PER_WAVE_ROOT_WINDOW_SCOPE,
    READOUT_ANALYSIS_CONTRACT_VERSION,
    SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
    SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
    SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
    SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
    get_readout_analysis_metric_definition,
)
from .shared_readout_analysis import _rounded_float
from .simulator_result_contract import (
    MIXED_MORPHOLOGY_INDEX_KEY,
    MODEL_ARTIFACTS_KEY,
    SURFACE_WAVE_MODEL_MODE,
    parse_simulator_result_bundle_metadata,
)
from .stimulus_contract import ASSET_STATUS_READY, _normalize_float, _normalize_identifier, _normalize_nonempty_string, _normalize_positive_float
from .surface_operators import deserialize_sparse_matrix


WAVE_STRUCTURE_DIAGNOSTIC_INTERFACE_VERSION = "wave_structure_diagnostics.v1"

SURFACE_WAVE_SUMMARY_ARTIFACT_ID = "surface_wave_summary"
SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID = "surface_wave_patch_traces"
SURFACE_WAVE_PHASE_MAP_ARTIFACT_ID = "surface_wave_phase_map"

SURFACE_WAVE_PHASE_MAP_FORMAT = "npz_surface_wave_phase_map.v1"

SUPPORTED_WAVE_STRUCTURE_METRIC_IDS = frozenset(
    {
        "patch_activation_entropy_bits",
        "phase_gradient_dispersion_rad_per_patch",
        "phase_gradient_mean_rad_per_patch",
        "synchrony_coherence_index",
        "wavefront_curvature_inv_patch",
        "wavefront_speed_patch_per_ms",
    }
)

DEFAULT_WAVE_STRUCTURE_POLICY = {
    "minimum_signal_amplitude": 1.0e-9,
    "minimum_trace_std": 1.0e-12,
    "wavefront_initial_threshold_fraction": 0.25,
    "wavefront_global_threshold_fraction": 0.05,
    "minimum_gradient_magnitude": 1.0e-9,
}

_TIME_ABS_TOLERANCE = 1.0e-9
_ROOT_PATCH_TRACE_PATTERN = re.compile(r"^root_(\d+)_patch_activation$")
_ROOT_PHASE_TRACE_PATTERN = re.compile(r"^root_(\d+)_(phase_rad|phase)$")

_METRIC_STATISTIC_BY_ID = {
    "patch_activation_entropy_bits": "shannon_entropy_mean_abs_patch_activation",
    "phase_gradient_dispersion_rad_per_patch": "phase_gradient_magnitude_dispersion",
    "phase_gradient_mean_rad_per_patch": "phase_gradient_magnitude_mean",
    "synchrony_coherence_index": "mean_abs_pairwise_root_correlation",
    "wavefront_curvature_inv_patch": "phase_wavefront_curvature_mean",
    "wavefront_speed_patch_per_ms": "wavefront_speed_linear_fit",
}


def compute_wave_structure_diagnostics(
    *,
    bundle_records: Sequence[Mapping[str, Any]],
    analysis_windows: Sequence[Mapping[str, Any]] | None = None,
    requested_metric_ids: Sequence[str] | None = None,
    kernel_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_metric_ids = _normalize_requested_metric_ids(requested_metric_ids)
    normalized_policy = _normalize_wave_structure_policy(kernel_policy)
    normalized_windows = _normalize_analysis_windows(analysis_windows)
    normalized_bundles = [
        _normalize_wave_bundle_record(
            item,
            requested_metric_ids=normalized_metric_ids,
        )
        for item in bundle_records
    ]

    metric_rows: list[dict[str, Any]] = []
    diagnostic_summaries: list[dict[str, Any]] = []

    for bundle in normalized_bundles:
        windows = (
            [copy.deepcopy(item) for item in normalized_windows]
            if normalized_windows is not None
            else [_default_analysis_window(bundle)]
        )
        for window in windows:
            if "synchrony_coherence_index" in normalized_metric_ids:
                summary = _compute_synchrony_summary(
                    bundle=bundle,
                    window=window,
                    policy=normalized_policy,
                )
                diagnostic_summaries.append(summary)
                if summary["status"] == "ok":
                    metric_rows.append(_summary_to_metric_row(summary))
            for root in bundle["roots"]:
                for metric_id in (
                    "patch_activation_entropy_bits",
                    "phase_gradient_mean_rad_per_patch",
                    "phase_gradient_dispersion_rad_per_patch",
                    "wavefront_speed_patch_per_ms",
                    "wavefront_curvature_inv_patch",
                ):
                    if metric_id not in normalized_metric_ids:
                        continue
                    summary = _compute_root_metric_summary(
                        metric_id=metric_id,
                        bundle=bundle,
                        root=root,
                        window=window,
                        policy=normalized_policy,
                    )
                    diagnostic_summaries.append(summary)
                    if summary["status"] == "ok":
                        metric_rows.append(_summary_to_metric_row(summary))

    metric_rows.sort(
        key=lambda row: (
            str(row["analysis_group_id"]),
            str(row["metric_id"]),
            "" if row["root_id"] is None else f"{int(row['root_id']):012d}",
            str(row["window_id"]),
            str(row["bundle_id"]),
        )
    )
    diagnostic_summaries.sort(
        key=lambda item: (
            str(item["analysis_group_id"]),
            str(item["metric_id"]),
            "" if item["root_id"] is None else f"{int(item['root_id']):012d}",
            str(item["window_id"]),
            str(item["bundle_id"]),
        )
    )

    return {
        "contract_version": READOUT_ANALYSIS_CONTRACT_VERSION,
        "wave_diagnostic_interface_version": WAVE_STRUCTURE_DIAGNOSTIC_INTERFACE_VERSION,
        "kernel_policy": copy.deepcopy(normalized_policy),
        "supported_metric_ids": sorted(SUPPORTED_WAVE_STRUCTURE_METRIC_IDS),
        "requested_metric_ids": list(normalized_metric_ids),
        "metric_rows": metric_rows,
        "diagnostic_summaries": diagnostic_summaries,
    }


def mean_abs_pairwise_root_correlation(
    per_root_trace: Mapping[int, np.ndarray],
    *,
    minimum_trace_std: float | None = None,
) -> float | None:
    minimum_std = (
        float(DEFAULT_WAVE_STRUCTURE_POLICY["minimum_trace_std"])
        if minimum_trace_std is None
        else float(minimum_trace_std)
    )
    values = [
        np.asarray(item, dtype=np.float64)
        for _, item in sorted(per_root_trace.items())
    ]
    valid = [
        item
        for item in values
        if item.ndim == 1 and item.size >= 2 and float(np.std(item)) > minimum_std
    ]
    if len(valid) < 2:
        return None
    correlations: list[float] = []
    for first_index, first in enumerate(valid):
        for second in valid[first_index + 1 :]:
            correlation = np.corrcoef(first, second)[0, 1]
            if np.isfinite(correlation):
                correlations.append(abs(float(correlation)))
    if not correlations:
        return None
    return float(np.mean(correlations))


def estimate_patch_wavefront_speed(
    *,
    patch_activation_history: np.ndarray,
    time_ms: np.ndarray,
    seed_patch: int,
    operator_bundle: Any | None = None,
    coarse_operator: sp.spmatrix | None = None,
    minimum_signal_amplitude: float | None = None,
    initial_threshold_fraction: float | None = None,
    global_threshold_fraction: float | None = None,
) -> dict[str, Any]:
    history = np.asarray(patch_activation_history, dtype=np.float64)
    resolved_time_ms = np.asarray(time_ms, dtype=np.float64)
    if history.ndim != 2:
        raise ValueError("patch_activation_history must be a 2D array.")
    if resolved_time_ms.ndim != 1:
        raise ValueError("time_ms must be a 1D array.")
    if history.shape[0] != resolved_time_ms.size:
        raise ValueError(
            "patch_activation_history row count must match len(time_ms)."
        )
    if history.shape[1] < 1:
        raise ValueError("patch_activation_history must contain at least one patch.")
    if seed_patch < 0 or seed_patch >= history.shape[1]:
        raise ValueError(
            f"seed_patch {seed_patch!r} is out of range for patch_count {history.shape[1]!r}."
        )

    resolved_operator = coarse_operator
    if resolved_operator is None and operator_bundle is not None:
        resolved_operator = operator_bundle.coarse_operator
    if resolved_operator is None:
        return {
            "detected": False,
            "detection_mode": "coarse_operator_unavailable",
            "distance_degenerate": False,
            "speed_units_per_ms": None,
            "distance_units": "patch_hops",
            "fit_r2": None,
            "arrival_count": 0,
            "threshold": None,
            "seed_patch": int(seed_patch),
            "arrival_times_ms": [],
            "arrival_distances_patch": [],
        }

    graph = _coarse_operator_to_patch_graph(resolved_operator)
    distances = sp.csgraph.dijkstra(graph, directed=False, indices=int(seed_patch))
    min_signal = (
        float(DEFAULT_WAVE_STRUCTURE_POLICY["minimum_signal_amplitude"])
        if minimum_signal_amplitude is None
        else float(minimum_signal_amplitude)
    )
    initial_fraction = (
        float(DEFAULT_WAVE_STRUCTURE_POLICY["wavefront_initial_threshold_fraction"])
        if initial_threshold_fraction is None
        else float(initial_threshold_fraction)
    )
    global_fraction = (
        float(DEFAULT_WAVE_STRUCTURE_POLICY["wavefront_global_threshold_fraction"])
        if global_threshold_fraction is None
        else float(global_threshold_fraction)
    )
    threshold = max(
        float(np.max(np.abs(history[0]))) * initial_fraction,
        float(np.max(np.abs(history))) * global_fraction,
        min_signal,
    )
    arrival_times: list[float] = []
    arrival_distances: list[float] = []
    for patch_index, distance in enumerate(np.asarray(distances, dtype=np.float64)):
        if patch_index == seed_patch or not np.isfinite(distance) or float(distance) <= 0.0:
            continue
        crossings = np.flatnonzero(np.abs(history[:, patch_index]) >= threshold)
        if crossings.size == 0:
            continue
        arrival_time_ms = float(resolved_time_ms[int(crossings[0])])
        if arrival_time_ms <= 0.0:
            continue
        arrival_times.append(arrival_time_ms)
        arrival_distances.append(float(distance))
    if len(arrival_times) < 2:
        return {
            "detected": False,
            "detection_mode": "insufficient_arrivals",
            "distance_degenerate": False,
            "speed_units_per_ms": None,
            "distance_units": "patch_hops",
            "fit_r2": None,
            "arrival_count": len(arrival_times),
            "threshold": float(threshold),
            "seed_patch": int(seed_patch),
            "arrival_times_ms": [_rounded_float(item) for item in arrival_times],
            "arrival_distances_patch": [_rounded_float(item) for item in arrival_distances],
        }
    x = np.asarray(arrival_times, dtype=np.float64)
    y = np.asarray(arrival_distances, dtype=np.float64)
    if np.allclose(y, y[0]):
        return {
            "detected": True,
            "detection_mode": "equal_distance_arrivals",
            "distance_degenerate": True,
            "speed_units_per_ms": None,
            "distance_units": "patch_hops",
            "fit_r2": None,
            "arrival_count": len(arrival_times),
            "threshold": float(threshold),
            "seed_patch": int(seed_patch),
            "arrival_times_ms": [_rounded_float(item) for item in arrival_times],
            "arrival_distances_patch": [_rounded_float(item) for item in arrival_distances],
        }
    if np.allclose(x, x[0]):
        return {
            "detected": False,
            "detection_mode": "simultaneous_arrivals",
            "distance_degenerate": False,
            "speed_units_per_ms": None,
            "distance_units": "patch_hops",
            "fit_r2": None,
            "arrival_count": len(arrival_times),
            "threshold": float(threshold),
            "seed_patch": int(seed_patch),
            "arrival_times_ms": [_rounded_float(item) for item in arrival_times],
            "arrival_distances_patch": [_rounded_float(item) for item in arrival_distances],
        }
    slope, intercept = np.polyfit(x, y, deg=1)
    if not np.isfinite(slope) or float(slope) <= 0.0:
        return {
            "detected": False,
            "detection_mode": "nonpositive_speed_fit",
            "distance_degenerate": False,
            "speed_units_per_ms": None,
            "distance_units": "patch_hops",
            "fit_r2": None,
            "arrival_count": len(arrival_times),
            "threshold": float(threshold),
            "seed_patch": int(seed_patch),
            "arrival_times_ms": [_rounded_float(item) for item in arrival_times],
            "arrival_distances_patch": [_rounded_float(item) for item in arrival_distances],
        }
    predicted = slope * x + intercept
    residual_sum = float(np.sum((y - predicted) ** 2))
    centered_sum = float(np.sum((y - np.mean(y)) ** 2))
    fit_r2 = None if centered_sum <= 0.0 else float(1.0 - residual_sum / centered_sum)
    return {
        "detected": True,
        "detection_mode": "speed_fit",
        "distance_degenerate": False,
        "speed_units_per_ms": float(slope),
        "distance_units": "patch_hops",
        "fit_r2": fit_r2,
        "arrival_count": len(arrival_times),
        "threshold": float(threshold),
        "seed_patch": int(seed_patch),
        "arrival_times_ms": [_rounded_float(item) for item in arrival_times],
        "arrival_distances_patch": [_rounded_float(item) for item in arrival_distances],
    }


def compute_patch_activation_entropy(
    *,
    patch_activation_history: np.ndarray,
    minimum_signal_amplitude: float | None = None,
) -> dict[str, Any]:
    history = np.asarray(patch_activation_history, dtype=np.float64)
    if history.ndim != 2:
        raise ValueError("patch_activation_history must be a 2D array.")
    if history.shape[1] < 1:
        raise ValueError("patch_activation_history must contain at least one patch.")
    weights = np.mean(np.abs(history), axis=0)
    total = float(np.sum(weights))
    threshold = (
        float(DEFAULT_WAVE_STRUCTURE_POLICY["minimum_signal_amplitude"])
        if minimum_signal_amplitude is None
        else float(minimum_signal_amplitude)
    )
    if total <= threshold:
        return {
            "status": "no_signal",
            "entropy_bits": None,
            "normalized_patch_weights": [],
            "patch_count": int(history.shape[1]),
        }
    probabilities = weights / total
    valid = probabilities[probabilities > 0.0]
    entropy_bits = float(-np.sum(valid * np.log2(valid)))
    return {
        "status": "ok",
        "entropy_bits": entropy_bits,
        "normalized_patch_weights": [
            _rounded_float(float(value)) for value in probabilities.tolist()
        ],
        "patch_count": int(history.shape[1]),
    }


def compute_phase_gradient_statistics(
    *,
    phase_history: np.ndarray,
    coarse_operator: sp.spmatrix,
) -> dict[str, Any]:
    phase = np.asarray(phase_history, dtype=np.float64)
    if phase.ndim != 2:
        raise ValueError("phase_history must be a 2D array.")
    graph = _coarse_operator_to_patch_graph(coarse_operator)
    edge_pairs = _undirected_edge_pairs(graph)
    if not edge_pairs:
        return {
            "status": "unavailable",
            "reason": "insufficient_patch_graph",
            "mean_rad_per_patch": None,
            "dispersion_rad_per_patch": None,
            "edge_count": 0,
            "sample_count": 0,
        }
    gradient_values: list[float] = []
    for left_index, right_index in edge_pairs:
        differences = _wrapped_phase_difference(
            phase[:, right_index] - phase[:, left_index]
        )
        gradient_values.extend(
            float(abs(value))
            for value in np.asarray(differences, dtype=np.float64).tolist()
        )
    if not gradient_values:
        return {
            "status": "unavailable",
            "reason": "empty_phase_history",
            "mean_rad_per_patch": None,
            "dispersion_rad_per_patch": None,
            "edge_count": len(edge_pairs),
            "sample_count": 0,
        }
    values = np.asarray(gradient_values, dtype=np.float64)
    return {
        "status": "ok",
        "reason": None,
        "mean_rad_per_patch": float(np.mean(values)),
        "dispersion_rad_per_patch": float(np.std(values)),
        "edge_count": len(edge_pairs),
        "sample_count": int(values.size),
    }


def compute_wavefront_curvature(
    *,
    phase_history: np.ndarray,
    coarse_operator: sp.spmatrix,
    minimum_gradient_magnitude: float | None = None,
) -> dict[str, Any]:
    phase = np.asarray(phase_history, dtype=np.float64)
    if phase.ndim != 2:
        raise ValueError("phase_history must be a 2D array.")
    graph = _coarse_operator_to_patch_graph(coarse_operator)
    neighbors = _graph_neighbors(graph)
    threshold = (
        float(DEFAULT_WAVE_STRUCTURE_POLICY["minimum_gradient_magnitude"])
        if minimum_gradient_magnitude is None
        else float(minimum_gradient_magnitude)
    )
    curvature_values: list[float] = []
    for sample_index in range(int(phase.shape[0])):
        sample = phase[sample_index]
        for patch_index, patch_neighbors in enumerate(neighbors):
            if patch_neighbors.size < 2:
                continue
            deltas = _wrapped_phase_difference(sample[patch_neighbors] - sample[patch_index])
            gradient_magnitude = float(np.mean(np.abs(deltas)))
            if gradient_magnitude <= threshold:
                continue
            laplacian_magnitude = float(abs(np.mean(deltas)))
            curvature_values.append(laplacian_magnitude / gradient_magnitude)
    if not curvature_values:
        return {
            "status": "unavailable",
            "reason": "insufficient_curvature_support",
            "curvature_inv_patch": None,
            "sample_count": 0,
        }
    values = np.asarray(curvature_values, dtype=np.float64)
    return {
        "status": "ok",
        "reason": None,
        "curvature_inv_patch": float(np.mean(values)),
        "sample_count": int(values.size),
    }


def _compute_synchrony_summary(
    *,
    bundle: Mapping[str, Any],
    window: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    metric_definition = get_readout_analysis_metric_definition("synchrony_coherence_index")
    traces_by_root: dict[int, np.ndarray] = {}
    unavailable_roots: dict[int, str] = {}
    for root in bundle["roots"]:
        root_id = int(root["root_id"])
        if str(root["projection_semantics"]) != "surface_patch_activation":
            unavailable_roots[root_id] = "incompatible_projection_semantics"
            continue
        trace = root.get("patch_trace")
        if trace is None:
            unavailable_roots[root_id] = "missing_patch_trace"
            continue
        time_ms = np.asarray(bundle["patch_trace_payload"]["time_ms"], dtype=np.float64)
        windowed_trace = _windowed_matrix(trace, time_ms=time_ms, window=window)
        if windowed_trace is None:
            unavailable_roots[root_id] = "empty_window"
            continue
        traces_by_root[root_id] = np.mean(windowed_trace, axis=1)

    value = mean_abs_pairwise_root_correlation(
        traces_by_root,
        minimum_trace_std=float(policy["minimum_trace_std"]),
    )
    if value is None:
        return _base_metric_summary(
            bundle=bundle,
            metric_definition=metric_definition,
            window=window,
            scope="wave_root_set",
            root_id=None,
            status="unavailable",
            reason="insufficient_wave_roots",
            value=None,
            diagnostics={
                "available_root_ids": sorted(traces_by_root),
                "unavailable_root_ids": unavailable_roots,
                "required_root_count": 2,
            },
        )
    return _base_metric_summary(
        bundle=bundle,
        metric_definition=metric_definition,
        window=window,
        scope="wave_root_set",
        root_id=None,
        status="ok",
        reason=None,
        value=value,
        diagnostics={
            "available_root_ids": sorted(traces_by_root),
            "unavailable_root_ids": unavailable_roots,
            "pair_count": len(traces_by_root) * (len(traces_by_root) - 1) // 2,
        },
    )


def _compute_root_metric_summary(
    *,
    metric_id: str,
    bundle: Mapping[str, Any],
    root: Mapping[str, Any],
    window: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    metric_definition = get_readout_analysis_metric_definition(metric_id)
    root_id = int(root["root_id"])
    patch_trace = root.get("patch_trace")
    phase_trace = root.get("phase_trace")
    coarse_operator = _load_root_coarse_operator(bundle=bundle, root=root)

    if str(root["projection_semantics"]) != "surface_patch_activation":
        return _base_metric_summary(
            bundle=bundle,
            metric_definition=metric_definition,
            window=window,
            scope="wave_root",
            root_id=root_id,
            status="unavailable",
            reason="incompatible_projection_semantics",
            value=None,
            diagnostics={
                "projection_semantics": str(root["projection_semantics"]),
                "morphology_class": str(root["morphology_class"]),
            },
        )

    if metric_id == "patch_activation_entropy_bits":
        if patch_trace is None:
            return _base_metric_summary(
                bundle=bundle,
                metric_definition=metric_definition,
                window=window,
                scope="wave_root",
                root_id=root_id,
                status="unavailable",
                reason="missing_patch_trace",
                value=None,
                diagnostics={},
            )
        time_ms = np.asarray(bundle["patch_trace_payload"]["time_ms"], dtype=np.float64)
        windowed_trace = _windowed_matrix(patch_trace, time_ms=time_ms, window=window)
        if windowed_trace is None:
            return _base_metric_summary(
                bundle=bundle,
                metric_definition=metric_definition,
                window=window,
                scope="wave_root",
                root_id=root_id,
                status="unavailable",
                reason="empty_window",
                value=None,
                diagnostics={},
            )
        entropy = compute_patch_activation_entropy(
            patch_activation_history=windowed_trace,
            minimum_signal_amplitude=float(policy["minimum_signal_amplitude"]),
        )
        return _base_metric_summary(
            bundle=bundle,
            metric_definition=metric_definition,
            window=window,
            scope="wave_root",
            root_id=root_id,
            status=str(entropy["status"]),
            reason=None if entropy["status"] == "ok" else str(entropy["status"]),
            value=entropy["entropy_bits"],
            diagnostics={
                "patch_count": int(entropy["patch_count"]),
                "normalized_patch_weights": entropy["normalized_patch_weights"],
            },
        )

    if metric_id == "wavefront_speed_patch_per_ms":
        if patch_trace is None:
            return _base_metric_summary(
                bundle=bundle,
                metric_definition=metric_definition,
                window=window,
                scope="wave_root",
                root_id=root_id,
                status="unavailable",
                reason="missing_patch_trace",
                value=None,
                diagnostics={},
            )
        if coarse_operator is None:
            return _base_metric_summary(
                bundle=bundle,
                metric_definition=metric_definition,
                window=window,
                scope="wave_root",
                root_id=root_id,
                status="unavailable",
                reason="missing_coarse_operator",
                value=None,
                diagnostics={},
            )
        time_ms = np.asarray(bundle["patch_trace_payload"]["time_ms"], dtype=np.float64)
        windowed_trace = _windowed_matrix(patch_trace, time_ms=time_ms, window=window)
        windowed_time_ms = _windowed_time(time_ms, window=window)
        if windowed_trace is None or windowed_time_ms is None:
            return _base_metric_summary(
                bundle=bundle,
                metric_definition=metric_definition,
                window=window,
                scope="wave_root",
                root_id=root_id,
                status="unavailable",
                reason="empty_window",
                value=None,
                diagnostics={},
            )
        seed_patch = _infer_wavefront_seed_patch(
            patch_activation_history=windowed_trace,
            time_ms=windowed_time_ms,
            minimum_signal_amplitude=float(policy["minimum_signal_amplitude"]),
        )
        wavefront = estimate_patch_wavefront_speed(
            patch_activation_history=windowed_trace,
            time_ms=windowed_time_ms,
            seed_patch=int(seed_patch["seed_patch"]),
            coarse_operator=coarse_operator,
            minimum_signal_amplitude=float(policy["minimum_signal_amplitude"]),
            initial_threshold_fraction=float(policy["wavefront_initial_threshold_fraction"]),
            global_threshold_fraction=float(policy["wavefront_global_threshold_fraction"]),
        )
        return _base_metric_summary(
            bundle=bundle,
            metric_definition=metric_definition,
            window=window,
            scope="wave_root",
            root_id=root_id,
            status="ok" if bool(wavefront["detected"]) else "unavailable",
            reason=None if bool(wavefront["detected"]) else str(wavefront["detection_mode"]),
            value=wavefront["speed_units_per_ms"],
            diagnostics={
                "seed_patch": int(seed_patch["seed_patch"]),
                "seed_selection_mode": str(seed_patch["selection_mode"]),
                "arrival_count": int(wavefront["arrival_count"]),
                "fit_r2": (
                    None
                    if wavefront["fit_r2"] is None
                    else _rounded_float(float(wavefront["fit_r2"]))
                ),
                "threshold": (
                    None
                    if wavefront["threshold"] is None
                    else _rounded_float(float(wavefront["threshold"]))
                ),
            },
        )

    if phase_trace is None:
        return _base_metric_summary(
            bundle=bundle,
            metric_definition=metric_definition,
            window=window,
            scope="wave_root",
            root_id=root_id,
            status="unavailable",
            reason="missing_wave_artifact",
            value=None,
            diagnostics={"missing_artifact_id": SURFACE_WAVE_PHASE_MAP_ARTIFACT_ID},
        )
    if coarse_operator is None:
        return _base_metric_summary(
            bundle=bundle,
            metric_definition=metric_definition,
            window=window,
            scope="wave_root",
            root_id=root_id,
            status="unavailable",
            reason="missing_coarse_operator",
            value=None,
            diagnostics={},
        )
    phase_time_ms = np.asarray(bundle["phase_map_payload"]["time_ms"], dtype=np.float64)
    windowed_phase = _windowed_matrix(phase_trace, time_ms=phase_time_ms, window=window)
    if windowed_phase is None:
        return _base_metric_summary(
            bundle=bundle,
            metric_definition=metric_definition,
            window=window,
            scope="wave_root",
            root_id=root_id,
            status="unavailable",
            reason="empty_window",
            value=None,
            diagnostics={},
        )
    if metric_id in {
        "phase_gradient_mean_rad_per_patch",
        "phase_gradient_dispersion_rad_per_patch",
    }:
        gradients = compute_phase_gradient_statistics(
            phase_history=windowed_phase,
            coarse_operator=coarse_operator,
        )
        value_key = (
            "mean_rad_per_patch"
            if metric_id == "phase_gradient_mean_rad_per_patch"
            else "dispersion_rad_per_patch"
        )
        return _base_metric_summary(
            bundle=bundle,
            metric_definition=metric_definition,
            window=window,
            scope="wave_root",
            root_id=root_id,
            status=str(gradients["status"]),
            reason=gradients.get("reason"),
            value=gradients[value_key],
            diagnostics={
                "edge_count": int(gradients["edge_count"]),
                "sample_count": int(gradients["sample_count"]),
                "mean_rad_per_patch": gradients["mean_rad_per_patch"],
                "dispersion_rad_per_patch": gradients["dispersion_rad_per_patch"],
            },
        )

    curvature = compute_wavefront_curvature(
        phase_history=windowed_phase,
        coarse_operator=coarse_operator,
        minimum_gradient_magnitude=float(policy["minimum_gradient_magnitude"]),
    )
    return _base_metric_summary(
        bundle=bundle,
        metric_definition=metric_definition,
        window=window,
        scope="wave_root",
        root_id=root_id,
        status=str(curvature["status"]),
        reason=curvature.get("reason"),
        value=curvature["curvature_inv_patch"],
        diagnostics={"sample_count": int(curvature["sample_count"])},
    )


def _normalize_wave_bundle_record(
    record: Mapping[str, Any],
    *,
    requested_metric_ids: Sequence[str],
) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise ValueError("bundle_records entries must be mappings.")
    metadata_payload = record.get("bundle_metadata", record)
    metadata = parse_simulator_result_bundle_metadata(metadata_payload)
    if str(metadata["arm_reference"]["model_mode"]) != SURFACE_WAVE_MODEL_MODE:
        raise ValueError(
            f"Wave diagnostics require surface_wave bundles, got model_mode "
            f"{metadata['arm_reference']['model_mode']!r}."
        )

    analysis_group_id = (
        _normalize_nonempty_string(
            record.get("analysis_group_id"),
            field_name="bundle_records.analysis_group_id",
        )
        if record.get("analysis_group_id") is not None
        else _default_analysis_group_id(metadata)
    )
    artifact_records = _model_artifact_records_by_id(metadata)

    summary_required = any(
        metric_id
        in {
            "synchrony_coherence_index",
            "phase_gradient_mean_rad_per_patch",
            "phase_gradient_dispersion_rad_per_patch",
            "wavefront_curvature_inv_patch",
            "wavefront_speed_patch_per_ms",
        }
        for metric_id in requested_metric_ids
    )
    patch_required = any(
        metric_id
        in {
            "patch_activation_entropy_bits",
            "synchrony_coherence_index",
            "wavefront_speed_patch_per_ms",
        }
        for metric_id in requested_metric_ids
    )

    summary_payload = _resolve_surface_wave_summary_payload(
        record=record,
        artifact_records=artifact_records,
        required=summary_required,
    )
    patch_trace_payload = _resolve_patch_trace_payload(
        record=record,
        artifact_records=artifact_records,
        summary_payload=summary_payload,
        required=patch_required,
    )
    phase_map_payload = _resolve_phase_map_payload(
        record=record,
        artifact_records=artifact_records,
        summary_payload=summary_payload,
    )

    available_source_artifact_classes = {
        SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
    }
    if summary_payload is not None:
        available_source_artifact_classes.add(SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS)
    if patch_trace_payload is not None:
        available_source_artifact_classes.add(SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS)
    if phase_map_payload is not None:
        available_source_artifact_classes.add(SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS)

    roots = _build_root_catalog(
        metadata=metadata,
        summary_payload=summary_payload,
        patch_trace_payload=patch_trace_payload,
        phase_map_payload=phase_map_payload,
    )
    return {
        "analysis_group_id": analysis_group_id,
        "bundle_id": str(metadata["bundle_id"]),
        "arm_id": str(metadata["arm_reference"]["arm_id"]),
        "baseline_family": metadata["arm_reference"]["baseline_family"],
        "model_mode": str(metadata["arm_reference"]["model_mode"]),
        "seed": int(metadata["determinism"]["seed"]),
        "metadata": metadata,
        "summary_payload": summary_payload,
        "patch_trace_payload": patch_trace_payload,
        "phase_map_payload": phase_map_payload,
        "available_source_artifact_classes": sorted(available_source_artifact_classes),
        "roots": roots,
        "coarse_operator_cache": {},
    }


def _resolve_surface_wave_summary_payload(
    *,
    record: Mapping[str, Any],
    artifact_records: Mapping[str, Mapping[str, Any]],
    required: bool,
) -> dict[str, Any] | None:
    explicit = record.get("surface_wave_summary_payload")
    if explicit is not None:
        if not isinstance(explicit, Mapping):
            raise ValueError("surface_wave_summary_payload must be a mapping when provided.")
        return copy.deepcopy(dict(explicit))
    artifact = artifact_records.get(SURFACE_WAVE_SUMMARY_ARTIFACT_ID)
    if artifact is None:
        if required:
            raise ValueError(
                f"surface-wave bundle is missing required artifact "
                f"{SURFACE_WAVE_SUMMARY_ARTIFACT_ID!r}."
            )
        return None
    if str(artifact["status"]) != ASSET_STATUS_READY:
        if required:
            raise ValueError(
                f"surface-wave bundle artifact {SURFACE_WAVE_SUMMARY_ARTIFACT_ID!r} is "
                f"not ready (status={artifact['status']!r})."
            )
        return None
    with Path(artifact["path"]).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError("surface_wave_summary payload must be a mapping.")
    return copy.deepcopy(dict(payload))


def _resolve_patch_trace_payload(
    *,
    record: Mapping[str, Any],
    artifact_records: Mapping[str, Mapping[str, Any]],
    summary_payload: Mapping[str, Any] | None,
    required: bool,
) -> dict[str, Any] | None:
    explicit = record.get("surface_wave_patch_trace_payload")
    if explicit is not None:
        return _normalize_patch_trace_payload(explicit)
    artifact_id = SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID
    if isinstance(summary_payload, Mapping):
        wave_specific_artifacts = summary_payload.get("wave_specific_artifacts")
        if isinstance(wave_specific_artifacts, Mapping):
            artifact_id = _normalize_identifier(
                wave_specific_artifacts.get(
                    "patch_traces_artifact_id",
                    SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID,
                ),
                field_name="surface_wave_summary.wave_specific_artifacts.patch_traces_artifact_id",
            )
    artifact = artifact_records.get(artifact_id)
    if artifact is None:
        if required:
            raise ValueError(
                f"surface-wave bundle is missing required artifact {artifact_id!r}."
            )
        return None
    if str(artifact["status"]) != ASSET_STATUS_READY:
        if required:
            raise ValueError(
                f"surface-wave bundle artifact {artifact_id!r} is not ready "
                f"(status={artifact['status']!r})."
            )
        return None
    return _normalize_patch_trace_payload(Path(artifact["path"]))


def _resolve_phase_map_payload(
    *,
    record: Mapping[str, Any],
    artifact_records: Mapping[str, Mapping[str, Any]],
    summary_payload: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    explicit = record.get("surface_wave_phase_map_payload")
    if explicit is not None:
        return _normalize_phase_map_payload(explicit)
    artifact_id = SURFACE_WAVE_PHASE_MAP_ARTIFACT_ID
    if isinstance(summary_payload, Mapping):
        wave_specific_artifacts = summary_payload.get("wave_specific_artifacts")
        if isinstance(wave_specific_artifacts, Mapping) and wave_specific_artifacts.get(
            "phase_map_artifact_id"
        ) is not None:
            artifact_id = _normalize_identifier(
                wave_specific_artifacts["phase_map_artifact_id"],
                field_name="surface_wave_summary.wave_specific_artifacts.phase_map_artifact_id",
            )
    artifact = artifact_records.get(artifact_id)
    if artifact is None or str(artifact["status"]) != ASSET_STATUS_READY:
        return None
    return _normalize_phase_map_payload(Path(artifact["path"]))


def _build_root_catalog(
    *,
    metadata: Mapping[str, Any],
    summary_payload: Mapping[str, Any] | None,
    patch_trace_payload: Mapping[str, Any] | None,
    phase_map_payload: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    roots_by_id: dict[int, dict[str, Any]] = {}
    summary_root_metadata_by_id: dict[int, dict[str, Any]] = {}

    if isinstance(summary_payload, Mapping):
        runtime_metadata_by_root = summary_payload.get("runtime_metadata_by_root", [])
        if isinstance(runtime_metadata_by_root, Sequence) and not isinstance(
            runtime_metadata_by_root,
            (str, bytes),
        ):
            for item in runtime_metadata_by_root:
                if not isinstance(item, Mapping) or item.get("root_id") is None:
                    continue
                root_id = int(item["root_id"])
                summary_root_metadata_by_id[root_id] = copy.deepcopy(dict(item))
                roots_by_id.setdefault(
                    root_id,
                    {
                        "root_id": root_id,
                        "morphology_class": str(item.get("morphology_class", "surface_neuron")),
                        "projection_semantics": "surface_patch_activation",
                        "summary_runtime_metadata": copy.deepcopy(dict(item)),
                    },
                )

    mixed_morphology_index = metadata.get(MIXED_MORPHOLOGY_INDEX_KEY)
    if isinstance(mixed_morphology_index, Mapping):
        roots_payload = mixed_morphology_index.get("roots", [])
        if isinstance(roots_payload, Sequence) and not isinstance(roots_payload, (str, bytes)):
            for item in roots_payload:
                if not isinstance(item, Mapping):
                    continue
                root_id = int(item["root_id"])
                root = roots_by_id.setdefault(
                    root_id,
                    {
                        "root_id": root_id,
                        "morphology_class": str(item.get("morphology_class", "surface_neuron")),
                        "projection_semantics": str(
                            item.get("projection_semantics", "surface_patch_activation")
                        ),
                    },
                )
                root["morphology_class"] = str(item.get("morphology_class", root["morphology_class"]))
                root["projection_semantics"] = str(
                    item.get("projection_semantics", root["projection_semantics"])
                )
                root["projection_trace_array"] = item.get("projection_trace_array")

    if isinstance(patch_trace_payload, Mapping):
        for root_id in patch_trace_payload["arrays_by_root_id"]:
            roots_by_id.setdefault(
                int(root_id),
                {
                    "root_id": int(root_id),
                    "morphology_class": "surface_neuron",
                    "projection_semantics": "surface_patch_activation",
                },
            )

    if isinstance(phase_map_payload, Mapping):
        for root_id in phase_map_payload["arrays_by_root_id"]:
            roots_by_id.setdefault(
                int(root_id),
                {
                    "root_id": int(root_id),
                    "morphology_class": "surface_neuron",
                    "projection_semantics": "surface_patch_activation",
                },
            )

    roots: list[dict[str, Any]] = []
    for root_id in sorted(roots_by_id):
        item = copy.deepcopy(dict(roots_by_id[root_id]))
        item["summary_runtime_metadata"] = copy.deepcopy(
            summary_root_metadata_by_id.get(root_id, item.get("summary_runtime_metadata", {}))
        )
        patch_trace = None
        if isinstance(patch_trace_payload, Mapping):
            patch_trace = patch_trace_payload["arrays_by_root_id"].get(int(root_id))
        item["patch_trace"] = None if patch_trace is None else np.asarray(patch_trace, dtype=np.float64)
        phase_trace = None
        if isinstance(phase_map_payload, Mapping):
            phase_trace = phase_map_payload["arrays_by_root_id"].get(int(root_id))
        item["phase_trace"] = None if phase_trace is None else np.asarray(phase_trace, dtype=np.float64)
        roots.append(item)
    return roots


def _normalize_patch_trace_payload(
    payload: Mapping[str, Any] | Path,
) -> dict[str, Any]:
    arrays = _load_npz_mapping(payload)
    time_ms = _extract_time_array(
        arrays,
        supported_names=("substep_time_ms", "shared_time_ms", "time_ms"),
        field_name="surface_wave_patch_trace_payload",
    )
    arrays_by_root_id: dict[int, np.ndarray] = {}
    for key, value in arrays.items():
        match = _ROOT_PATCH_TRACE_PATTERN.match(str(key))
        if match is None:
            continue
        trace = np.asarray(value, dtype=np.float64)
        if trace.ndim != 2 or trace.shape[0] != time_ms.size:
            raise ValueError(
                f"Patch trace array {key!r} must have shape (len(time_ms), patch_count)."
            )
        arrays_by_root_id[int(match.group(1))] = trace
    if not arrays_by_root_id:
        raise ValueError("surface_wave_patch_trace_payload does not contain any root patch traces.")
    return {
        "time_ms": time_ms,
        "arrays_by_root_id": arrays_by_root_id,
    }


def _normalize_phase_map_payload(
    payload: Mapping[str, Any] | Path,
) -> dict[str, Any]:
    arrays = _load_npz_mapping(payload)
    time_ms = _extract_time_array(
        arrays,
        supported_names=("substep_time_ms", "shared_time_ms", "time_ms"),
        field_name="surface_wave_phase_map_payload",
    )
    arrays_by_root_id: dict[int, np.ndarray] = {}
    for key, value in arrays.items():
        match = _ROOT_PHASE_TRACE_PATTERN.match(str(key))
        if match is None:
            continue
        trace = np.asarray(value, dtype=np.float64)
        if trace.ndim != 2 or trace.shape[0] != time_ms.size:
            raise ValueError(
                f"Phase-map array {key!r} must have shape (len(time_ms), patch_count)."
            )
        arrays_by_root_id[int(match.group(1))] = trace
    if not arrays_by_root_id:
        raise ValueError("surface_wave_phase_map_payload does not contain any root phase arrays.")
    return {
        "time_ms": time_ms,
        "arrays_by_root_id": arrays_by_root_id,
    }


def _normalize_requested_metric_ids(
    requested_metric_ids: Sequence[str] | None,
) -> list[str]:
    if requested_metric_ids is None:
        return sorted(SUPPORTED_WAVE_STRUCTURE_METRIC_IDS)
    if not isinstance(requested_metric_ids, Sequence) or isinstance(
        requested_metric_ids,
        (str, bytes),
    ):
        raise ValueError("requested_metric_ids must be a list when provided.")
    normalized = sorted(
        {
            _normalize_identifier(metric_id, field_name="requested_metric_ids")
            for metric_id in requested_metric_ids
        }
    )
    unsupported = sorted(set(normalized) - set(SUPPORTED_WAVE_STRUCTURE_METRIC_IDS))
    if unsupported:
        raise ValueError(
            f"Unsupported wave diagnostic metric ids {unsupported!r}."
        )
    return normalized


def _normalize_wave_structure_policy(
    policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw_policy = dict(DEFAULT_WAVE_STRUCTURE_POLICY)
    if policy is not None:
        if not isinstance(policy, Mapping):
            raise ValueError("kernel_policy must be a mapping when provided.")
        raw_policy.update(policy)
    return {
        "minimum_signal_amplitude": _normalize_positive_float(
            raw_policy.get("minimum_signal_amplitude"),
            field_name="kernel_policy.minimum_signal_amplitude",
        ),
        "minimum_trace_std": _normalize_positive_float(
            raw_policy.get("minimum_trace_std"),
            field_name="kernel_policy.minimum_trace_std",
        ),
        "wavefront_initial_threshold_fraction": _normalize_positive_float(
            raw_policy.get("wavefront_initial_threshold_fraction"),
            field_name="kernel_policy.wavefront_initial_threshold_fraction",
        ),
        "wavefront_global_threshold_fraction": _normalize_positive_float(
            raw_policy.get("wavefront_global_threshold_fraction"),
            field_name="kernel_policy.wavefront_global_threshold_fraction",
        ),
        "minimum_gradient_magnitude": _normalize_positive_float(
            raw_policy.get("minimum_gradient_magnitude"),
            field_name="kernel_policy.minimum_gradient_magnitude",
        ),
    }


def _normalize_analysis_windows(
    analysis_windows: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    if analysis_windows is None:
        return None
    if not isinstance(analysis_windows, Sequence) or isinstance(
        analysis_windows,
        (str, bytes),
    ):
        raise ValueError("analysis_windows must be a list when provided.")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(analysis_windows):
        if not isinstance(item, Mapping):
            raise ValueError(f"analysis_windows[{index}] must be a mapping.")
        window_id = _normalize_identifier(
            item.get("window_id"),
            field_name=f"analysis_windows[{index}].window_id",
        )
        start_ms = _normalize_float(
            item.get("start_ms"),
            field_name=f"analysis_windows[{index}].start_ms",
        )
        end_ms = _normalize_float(
            item.get("end_ms"),
            field_name=f"analysis_windows[{index}].end_ms",
        )
        if float(end_ms) <= float(start_ms):
            raise ValueError(
                f"analysis_windows[{index}] has end_ms <= start_ms."
            )
        normalized.append(
            {
                "window_id": window_id,
                "start_ms": float(start_ms),
                "end_ms": float(end_ms),
                "description": _normalize_nonempty_string(
                    item.get("description", window_id),
                    field_name=f"analysis_windows[{index}].description",
                ),
            }
        )
    return normalized


def _default_analysis_window(bundle: Mapping[str, Any]) -> dict[str, Any]:
    if bundle["patch_trace_payload"] is not None:
        time_ms = np.asarray(bundle["patch_trace_payload"]["time_ms"], dtype=np.float64)
    elif bundle["phase_map_payload"] is not None:
        time_ms = np.asarray(bundle["phase_map_payload"]["time_ms"], dtype=np.float64)
    else:
        raise ValueError(
            f"Wave bundle {bundle['bundle_id']!r} does not expose any usable wave timebase."
        )
    return {
        "window_id": "full_wave_diagnostic_window",
        "start_ms": float(time_ms[0]),
        "end_ms": float(time_ms[-1]),
        "description": "Full available wave-artifact window.",
    }


def _base_metric_summary(
    *,
    bundle: Mapping[str, Any],
    metric_definition: Mapping[str, Any],
    window: Mapping[str, Any],
    scope: str,
    root_id: int | None,
    status: str,
    reason: str | None,
    value: float | None,
    diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    required_source_artifact_classes = list(metric_definition["required_source_artifact_classes"])
    available_source_artifact_classes = list(bundle["available_source_artifact_classes"])
    missing_source_artifact_classes = sorted(
        set(required_source_artifact_classes) - set(available_source_artifact_classes)
    )
    return {
        "analysis_group_id": str(bundle["analysis_group_id"]),
        "bundle_id": str(bundle["bundle_id"]),
        "arm_id": str(bundle["arm_id"]),
        "baseline_family": bundle["baseline_family"],
        "model_mode": str(bundle["model_mode"]),
        "seed": int(bundle["seed"]),
        "metric_id": str(metric_definition["metric_id"]),
        "scope_rule": str(metric_definition["scope_rule"]),
        "scope": scope,
        "root_id": None if root_id is None else int(root_id),
        "window_id": str(window["window_id"]),
        "window_start_ms": _rounded_float(float(window["start_ms"])),
        "window_end_ms": _rounded_float(float(window["end_ms"])),
        "status": str(status),
        "reason": None if reason is None else str(reason),
        "value": None if value is None else _rounded_float(float(value)),
        "units": str(metric_definition["units"]),
        "required_source_artifact_classes": required_source_artifact_classes,
        "available_source_artifact_classes": available_source_artifact_classes,
        "missing_source_artifact_classes": missing_source_artifact_classes,
        "diagnostics": copy.deepcopy(dict(diagnostics)),
    }


def _summary_to_metric_row(summary: Mapping[str, Any]) -> dict[str, Any]:
    metric_id = str(summary["metric_id"])
    return {
        "metric_id": metric_id,
        "readout_id": None,
        "scope": str(summary["scope"]),
        "window_id": str(summary["window_id"]),
        "statistic": str(_METRIC_STATISTIC_BY_ID[metric_id]),
        "value": float(summary["value"]),
        "units": str(summary["units"]),
        "analysis_group_id": str(summary["analysis_group_id"]),
        "bundle_id": str(summary["bundle_id"]),
        "bundle_ids": [str(summary["bundle_id"])],
        "arm_id": str(summary["arm_id"]),
        "baseline_family": summary["baseline_family"],
        "model_mode": str(summary["model_mode"]),
        "seed": int(summary["seed"]),
        "root_id": None if summary["root_id"] is None else int(summary["root_id"]),
    }


def _infer_wavefront_seed_patch(
    *,
    patch_activation_history: np.ndarray,
    time_ms: np.ndarray,
    minimum_signal_amplitude: float,
) -> dict[str, Any]:
    history = np.asarray(patch_activation_history, dtype=np.float64)
    abs_history = np.abs(history)
    threshold = max(
        float(np.max(abs_history)) * 0.05,
        float(minimum_signal_amplitude),
    )
    earliest_time_ms = math.inf
    seed_patch = 0
    selection_mode = "global_peak_patch"
    peak_by_patch = np.max(abs_history, axis=0)
    for patch_index in range(int(history.shape[1])):
        crossings = np.flatnonzero(abs_history[:, patch_index] >= threshold)
        if crossings.size == 0:
            continue
        arrival_time_ms = float(time_ms[int(crossings[0])])
        candidate = (
            arrival_time_ms,
            -float(peak_by_patch[patch_index]),
            int(patch_index),
        )
        current = (
            earliest_time_ms,
            -float(peak_by_patch[seed_patch]),
            int(seed_patch),
        )
        if candidate < current:
            earliest_time_ms = arrival_time_ms
            seed_patch = int(patch_index)
            selection_mode = "earliest_threshold_crossing"
    if not np.isfinite(earliest_time_ms):
        seed_patch = int(np.argmax(peak_by_patch))
    return {
        "seed_patch": int(seed_patch),
        "selection_mode": selection_mode,
        "threshold": _rounded_float(float(threshold)),
    }


def _windowed_time(
    time_ms: np.ndarray,
    *,
    window: Mapping[str, Any],
) -> np.ndarray | None:
    mask = _window_mask(time_ms, window=window)
    if not np.any(mask):
        return None
    return np.asarray(time_ms[mask], dtype=np.float64)


def _windowed_matrix(
    values: np.ndarray,
    *,
    time_ms: np.ndarray,
    window: Mapping[str, Any],
) -> np.ndarray | None:
    mask = _window_mask(time_ms, window=window)
    if not np.any(mask):
        return None
    return np.asarray(values[mask], dtype=np.float64)


def _window_mask(time_ms: np.ndarray, *, window: Mapping[str, Any]) -> np.ndarray:
    return (
        (np.asarray(time_ms, dtype=np.float64) >= float(window["start_ms"]) - _TIME_ABS_TOLERANCE)
        & (np.asarray(time_ms, dtype=np.float64) <= float(window["end_ms"]) + _TIME_ABS_TOLERANCE)
    )


def _load_root_coarse_operator(
    *,
    bundle: Mapping[str, Any],
    root: Mapping[str, Any],
) -> sp.csr_matrix | None:
    runtime_metadata = root.get("summary_runtime_metadata")
    if not isinstance(runtime_metadata, Mapping):
        return None
    source_reference = runtime_metadata.get("source_reference")
    if not isinstance(source_reference, Mapping):
        return None
    coarse_operator_path = source_reference.get("coarse_operator_path")
    if not isinstance(coarse_operator_path, str) or not coarse_operator_path:
        return None
    cache = bundle["coarse_operator_cache"]
    resolved_path = str(Path(coarse_operator_path).resolve())
    if resolved_path in cache:
        return cache[resolved_path]
    path = Path(resolved_path)
    if not path.exists():
        return None
    with np.load(path, allow_pickle=False) as payload:
        cache[resolved_path] = deserialize_sparse_matrix(payload, prefix="operator").tocsr()
    return cache[resolved_path]


def _model_artifact_records_by_id(
    metadata: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    artifacts = metadata["artifacts"]
    model_artifacts = artifacts.get(MODEL_ARTIFACTS_KEY, [])
    if not isinstance(model_artifacts, Sequence) or isinstance(model_artifacts, (str, bytes)):
        raise ValueError("model_artifacts must be a list.")
    return {
        str(item["artifact_id"]): copy.deepcopy(dict(item))
        for item in model_artifacts
        if isinstance(item, Mapping)
    }


def _coarse_operator_to_patch_graph(
    coarse_operator: sp.spmatrix,
) -> sp.csr_matrix:
    matrix = coarse_operator.tocoo()
    mask = matrix.row != matrix.col
    return sp.csr_matrix(
        (
            np.ones(int(np.count_nonzero(mask)), dtype=np.float64),
            (matrix.row[mask], matrix.col[mask]),
        ),
        shape=coarse_operator.shape,
    )


def _undirected_edge_pairs(graph: sp.csr_matrix) -> list[tuple[int, int]]:
    coo = graph.tocoo()
    pairs = {
        (int(min(left, right)), int(max(left, right)))
        for left, right in zip(coo.row.tolist(), coo.col.tolist(), strict=False)
        if int(left) != int(right)
    }
    return sorted(pairs)


def _graph_neighbors(graph: sp.csr_matrix) -> list[np.ndarray]:
    neighbors: list[np.ndarray] = []
    for patch_index in range(int(graph.shape[0])):
        start = int(graph.indptr[patch_index])
        end = int(graph.indptr[patch_index + 1])
        row = np.asarray(graph.indices[start:end], dtype=np.int64)
        neighbors.append(row[row != patch_index])
    return neighbors


def _wrapped_phase_difference(delta: np.ndarray) -> np.ndarray:
    values = np.asarray(delta, dtype=np.float64)
    return (values + math.pi) % (2.0 * math.pi) - math.pi


def _load_npz_mapping(payload: Mapping[str, Any] | Path) -> dict[str, np.ndarray]:
    if isinstance(payload, Mapping):
        return {
            str(key): np.asarray(value)
            for key, value in payload.items()
        }
    path = Path(payload).resolve()
    with np.load(path, allow_pickle=False) as arrays:
        return {
            str(key): np.asarray(arrays[key])
            for key in arrays.files
        }


def _extract_time_array(
    arrays: Mapping[str, np.ndarray],
    *,
    supported_names: Sequence[str],
    field_name: str,
) -> np.ndarray:
    for name in supported_names:
        if name not in arrays:
            continue
        time_ms = np.asarray(arrays[name], dtype=np.float64)
        if time_ms.ndim != 1:
            raise ValueError(f"{field_name}.{name} must be a 1D array.")
        return time_ms
    raise ValueError(
        f"{field_name} is missing a supported time array from {list(supported_names)!r}."
    )


def _default_analysis_group_id(metadata: Mapping[str, Any]) -> str:
    return (
        f"{metadata['manifest_reference']['experiment_id']}::"
        f"{metadata['arm_reference']['arm_id']}::"
        f"seed_{metadata['determinism']['seed']}"
    )
