from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .readout_analysis_contract import (
    READOUT_ANALYSIS_CONTRACT_VERSION,
    get_readout_analysis_metric_definition,
)
from .simulator_result_contract import (
    load_simulator_shared_readout_payload,
    normalize_simulator_timebase,
    parse_simulator_result_bundle_metadata,
)
from .stimulus_contract import (
    _normalize_float,
    _normalize_identifier,
    _normalize_nonempty_string,
    _normalize_positive_float,
)


SUPPORTED_SHARED_READOUT_ANALYSIS_METRIC_IDS = frozenset(
    {
        "direction_selectivity_index",
        "null_direction_suppression_index",
        "on_off_selectivity_index",
        "response_latency_to_peak_ms",
    }
)

DEFAULT_SHARED_READOUT_ANALYSIS_POLICY = {
    "baseline_mode": "mean_pre_window_else_first_window_sample",
    "negative_response_mode": "clip_to_zero_after_baseline_subtraction",
    "peak_selection_mode": "first_maximum_sample_in_window",
    "pairing_key_mode": "derive_from_nonpaired_condition_ids",
    "latency_onset_threshold_fraction_of_peak": 0.1,
    "minimum_signal_amplitude": 1.0e-9,
}

_LATENCY_STATISTIC = "latency_to_peak_ms"
_SELECTIVITY_STATISTIC = "normalized_peak_selectivity_index"
_DEFAULT_PAIRING_KEY = "all_conditions"
_TIME_ABS_TOLERANCE = 1.0e-9


def compute_shared_readout_analysis(
    *,
    analysis_plan: Mapping[str, Any],
    bundle_records: Sequence[Mapping[str, Any]],
    kernel_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_plan = _normalize_analysis_plan(analysis_plan)
    normalized_policy = _normalize_kernel_policy(kernel_policy)
    normalized_bundles = [
        _normalize_bundle_record(
            item,
            condition_ids_by_id=normalized_plan["condition_ids_by_id"],
        )
        for item in bundle_records
    ]
    grouped_bundles = _group_bundle_records(normalized_bundles)

    metric_rows: list[dict[str, Any]] = []
    metric_summaries: list[dict[str, Any]] = []
    skipped_recipes: list[dict[str, Any]] = []

    for recipe in normalized_plan["metric_recipe_catalog"]:
        metric_id = str(recipe["metric_id"])
        if metric_id not in SUPPORTED_SHARED_READOUT_ANALYSIS_METRIC_IDS:
            skipped_recipes.append(
                {
                    "recipe_id": str(recipe["recipe_id"]),
                    "metric_id": metric_id,
                    "reason": "metric_id_not_yet_implemented",
                }
            )
            continue
        if metric_id == "response_latency_to_peak_ms":
            recipe_rows, recipe_summaries = _compute_latency_recipe_outputs(
                recipe=recipe,
                bundles=normalized_bundles,
                policy=normalized_policy,
            )
        else:
            recipe_rows, recipe_summaries = _compute_pair_recipe_outputs(
                recipe=recipe,
                grouped_bundles=grouped_bundles,
                condition_pairs_by_id=normalized_plan["condition_pairs_by_id"],
                policy=normalized_policy,
            )
        metric_rows.extend(recipe_rows)
        metric_summaries.extend(recipe_summaries)

    metric_rows.sort(
        key=lambda row: (
            str(row["analysis_group_id"]),
            str(row["metric_id"]),
            str(row["readout_id"]),
            str(row.get("condition_pair_id") or ""),
            str(row.get("pairing_key") or ""),
            str(row.get("condition_signature") or ""),
            str(row["recipe_id"]),
        )
    )
    metric_summaries.sort(
        key=lambda item: (
            str(item["analysis_group_id"]),
            str(item["metric_id"]),
            str(item["readout_id"]),
            str(item.get("condition_pair_id") or ""),
            str(item.get("pairing_key") or ""),
            str(item.get("condition_signature") or ""),
            str(item["recipe_id"]),
        )
    )
    skipped_recipes.sort(key=lambda item: (str(item["metric_id"]), str(item["recipe_id"])))

    return {
        "contract_version": READOUT_ANALYSIS_CONTRACT_VERSION,
        "analysis_plan_version": str(normalized_plan["plan_version"]),
        "kernel_policy": copy.deepcopy(normalized_policy),
        "supported_metric_ids": sorted(SUPPORTED_SHARED_READOUT_ANALYSIS_METRIC_IDS),
        "metric_rows": metric_rows,
        "metric_summaries": metric_summaries,
        "skipped_recipes": skipped_recipes,
    }


def _compute_latency_recipe_outputs(
    *,
    recipe: Mapping[str, Any],
    bundles: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    readout_id = str(recipe["active_readout_id"])
    condition_ids = set(recipe["condition_ids"])
    metric_definition = get_readout_analysis_metric_definition(str(recipe["metric_id"]))
    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for bundle in bundles:
        bundle_condition_ids = set(bundle["condition_ids"])
        if condition_ids and not bundle_condition_ids.intersection(condition_ids):
            continue
        response_summary = _compute_window_response_summary(
            bundle=bundle,
            readout_id=readout_id,
            window=recipe["window_reference"],
            policy=policy,
        )
        summary = {
            "recipe_id": str(recipe["recipe_id"]),
            "metric_id": str(recipe["metric_id"]),
            "analysis_group_id": str(bundle["analysis_group_id"]),
            "readout_id": readout_id,
            "scope": str(response_summary["readout_scope"]),
            "window_id": str(recipe["window_id"]),
            "units": str(metric_definition["units"]),
            "status": str(response_summary["signal_classification"]),
            "condition_ids": list(bundle["condition_ids"]),
            "condition_signature": str(bundle["condition_signature"]),
            "condition_pair_id": None,
            "pairing_key": None,
            "bundle_ids": [str(bundle["bundle_id"])],
            "arm_id": str(bundle["arm_id"]),
            "baseline_family": bundle["baseline_family"],
            "model_mode": str(bundle["model_mode"]),
            "seed": int(bundle["seed"]),
            "value": (
                _rounded_float(float(response_summary["peak_latency_ms"]))
                if response_summary["signal_classification"] == "ok"
                else None
            ),
            "response_summary": response_summary,
        }
        summaries.append(summary)
        if summary["status"] != "ok":
            continue
        rows.append(
            {
                "recipe_id": str(recipe["recipe_id"]),
                "metric_id": str(recipe["metric_id"]),
                "readout_id": readout_id,
                "scope": str(response_summary["readout_scope"]),
                "window_id": str(recipe["window_id"]),
                "statistic": _LATENCY_STATISTIC,
                "value": _rounded_float(float(response_summary["peak_latency_ms"])),
                "units": str(metric_definition["units"]),
                "analysis_group_id": str(bundle["analysis_group_id"]),
                "condition_ids": list(bundle["condition_ids"]),
                "condition_signature": str(bundle["condition_signature"]),
                "condition_pair_id": None,
                "pairing_key": None,
                "bundle_ids": [str(bundle["bundle_id"])],
                "arm_id": str(bundle["arm_id"]),
                "baseline_family": bundle["baseline_family"],
                "model_mode": str(bundle["model_mode"]),
                "seed": int(bundle["seed"]),
            }
        )
    return rows, summaries


def _compute_pair_recipe_outputs(
    *,
    recipe: Mapping[str, Any],
    grouped_bundles: Mapping[str, Sequence[Mapping[str, Any]]],
    condition_pairs_by_id: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    readout_id = str(recipe["active_readout_id"])
    pair_definition = dict(condition_pairs_by_id[str(recipe["condition_pair_id"])])
    left_condition_id = str(pair_definition["left_condition_id"])
    right_condition_id = str(pair_definition["right_condition_id"])
    metric_definition = get_readout_analysis_metric_definition(str(recipe["metric_id"]))
    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    for analysis_group_id, bundles in grouped_bundles.items():
        keys = {
            _bundle_pairing_key(bundle, pair_definition)
            for bundle in bundles
            if left_condition_id in set(bundle["condition_ids"])
            or right_condition_id in set(bundle["condition_ids"])
        }
        for pairing_key in sorted(keys):
            left_candidates = [
                bundle
                for bundle in bundles
                if left_condition_id in set(bundle["condition_ids"])
                and _bundle_pairing_key(bundle, pair_definition) == pairing_key
            ]
            right_candidates = [
                bundle
                for bundle in bundles
                if right_condition_id in set(bundle["condition_ids"])
                and _bundle_pairing_key(bundle, pair_definition) == pairing_key
            ]
            if not left_candidates and not right_candidates:
                continue
            if len(left_candidates) > 1 or len(right_candidates) > 1:
                raise ValueError(
                    f"Shared-readout analysis found ambiguous pairing for recipe "
                    f"{recipe['recipe_id']!r}, analysis_group_id {analysis_group_id!r}, "
                    f"pairing_key {pairing_key!r}. Provide unique condition bundles or "
                    "explicit per-pair pairing_keys."
                )
            if not left_candidates or not right_candidates:
                summaries.append(
                    {
                        "recipe_id": str(recipe["recipe_id"]),
                        "metric_id": str(recipe["metric_id"]),
                        "analysis_group_id": str(analysis_group_id),
                        "readout_id": readout_id,
                        "scope": None,
                        "window_id": str(recipe["window_id"]),
                        "units": str(metric_definition["units"]),
                        "status": "missing_condition",
                        "condition_pair_id": str(recipe["condition_pair_id"]),
                        "pairing_key": str(pairing_key),
                        "left_condition_id": left_condition_id,
                        "right_condition_id": right_condition_id,
                        "bundle_ids": [
                            *[str(item["bundle_id"]) for item in left_candidates],
                            *[str(item["bundle_id"]) for item in right_candidates],
                        ],
                        "value": None,
                        "left_response_summary": None,
                        "right_response_summary": None,
                    }
                )
                continue

            left_bundle = left_candidates[0]
            right_bundle = right_candidates[0]
            if left_bundle["timebase"] != right_bundle["timebase"]:
                raise ValueError(
                    f"Shared-readout pair recipe {recipe['recipe_id']!r} requires a shared "
                    f"timebase, but bundle {left_bundle['bundle_id']!r} and "
                    f"{right_bundle['bundle_id']!r} disagree."
                )
            left_summary = _compute_window_response_summary(
                bundle=left_bundle,
                readout_id=readout_id,
                window=recipe["window_reference"],
                policy=policy,
            )
            right_summary = _compute_window_response_summary(
                bundle=right_bundle,
                readout_id=readout_id,
                window=recipe["window_reference"],
                policy=policy,
            )
            left_peak = float(left_summary["peak_value"])
            right_peak = float(right_summary["peak_value"])
            denominator = left_peak + right_peak
            status = "ok"
            value: float | None = None
            if denominator <= float(policy["minimum_signal_amplitude"]):
                status = "no_signal"
            else:
                value = _rounded_float((left_peak - right_peak) / denominator)
            summary = {
                "recipe_id": str(recipe["recipe_id"]),
                "metric_id": str(recipe["metric_id"]),
                "analysis_group_id": str(analysis_group_id),
                "readout_id": readout_id,
                "scope": str(left_summary["readout_scope"]),
                "window_id": str(recipe["window_id"]),
                "units": str(metric_definition["units"]),
                "status": status,
                "condition_pair_id": str(recipe["condition_pair_id"]),
                "pairing_key": str(pairing_key),
                "left_condition_id": left_condition_id,
                "right_condition_id": right_condition_id,
                "bundle_ids": [
                    str(left_bundle["bundle_id"]),
                    str(right_bundle["bundle_id"]),
                ],
                "arm_id": str(left_bundle["arm_id"]),
                "baseline_family": left_bundle["baseline_family"],
                "model_mode": str(left_bundle["model_mode"]),
                "seed": int(left_bundle["seed"]),
                "value": value,
                "left_response_summary": left_summary,
                "right_response_summary": right_summary,
            }
            summaries.append(summary)
            if status != "ok" or value is None:
                continue
            rows.append(
                {
                    "recipe_id": str(recipe["recipe_id"]),
                    "metric_id": str(recipe["metric_id"]),
                    "readout_id": readout_id,
                    "scope": str(left_summary["readout_scope"]),
                    "window_id": str(recipe["window_id"]),
                    "statistic": _SELECTIVITY_STATISTIC,
                    "value": value,
                    "units": str(metric_definition["units"]),
                    "analysis_group_id": str(analysis_group_id),
                    "condition_ids": [
                        left_condition_id,
                        right_condition_id,
                    ],
                    "condition_signature": f"{left_condition_id}__vs__{right_condition_id}",
                    "condition_pair_id": str(recipe["condition_pair_id"]),
                    "pairing_key": str(pairing_key),
                    "bundle_ids": [
                        str(left_bundle["bundle_id"]),
                        str(right_bundle["bundle_id"]),
                    ],
                    "arm_id": str(left_bundle["arm_id"]),
                    "baseline_family": left_bundle["baseline_family"],
                    "model_mode": str(left_bundle["model_mode"]),
                    "seed": int(left_bundle["seed"]),
                }
            )
    return rows, summaries


def _compute_window_response_summary(
    *,
    bundle: Mapping[str, Any],
    readout_id: str,
    window: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    readout_index = int(bundle["readout_index_by_id"][readout_id])
    readout_catalog_entry = dict(bundle["readout_catalog_by_id"][readout_id])
    time_ms = np.asarray(bundle["time_ms"], dtype=np.float64)
    values = np.asarray(bundle["values"][:, readout_index], dtype=np.float64)
    window_mask = (
        (time_ms >= float(window["start_ms"]) - _TIME_ABS_TOLERANCE)
        & (time_ms <= float(window["end_ms"]) + _TIME_ABS_TOLERANCE)
    )
    if not np.any(window_mask):
        raise ValueError(
            f"Analysis window {window['window_id']!r} does not overlap any samples in bundle "
            f"{bundle['bundle_id']!r}."
        )
    window_time_ms = time_ms[window_mask]
    window_values = values[window_mask]
    baseline_mask = time_ms < float(window["start_ms"]) - _TIME_ABS_TOLERANCE
    if np.any(baseline_mask):
        baseline_value = float(np.mean(values[baseline_mask], dtype=np.float64))
    else:
        baseline_value = float(window_values[0])
    baseline_subtracted = np.asarray(window_values - baseline_value, dtype=np.float64)
    if str(policy["negative_response_mode"]) == "clip_to_zero_after_baseline_subtraction":
        positive_response = np.maximum(baseline_subtracted, 0.0)
    else:  # pragma: no cover - guarded by normalization
        positive_response = baseline_subtracted

    peak_value = float(np.max(positive_response))
    peak_index = int(np.argmax(positive_response))
    onset_threshold_value = max(
        float(policy["minimum_signal_amplitude"]),
        float(policy["latency_onset_threshold_fraction_of_peak"]) * peak_value,
    )
    signal_classification = "ok"
    onset_index: int | None = None
    onset_segment_count_before_peak = 0
    if peak_value <= float(policy["minimum_signal_amplitude"]):
        signal_classification = "no_signal"
    else:
        above_threshold = positive_response >= onset_threshold_value
        segments = _contiguous_true_segments(above_threshold)
        relevant_segments = [
            segment
            for segment in segments
            if int(segment[0]) <= peak_index
        ]
        onset_segment_count_before_peak = len(relevant_segments)
        containing_segments = [
            segment
            for segment in relevant_segments
            if int(segment[0]) <= peak_index <= int(segment[1])
        ]
        if not containing_segments:
            signal_classification = "ambiguous_onset"
        else:
            onset_index = int(containing_segments[-1][0])
            if onset_segment_count_before_peak > 1:
                signal_classification = "ambiguous_onset"

    onset_time_ms = (
        _rounded_float(float(window_time_ms[onset_index]))
        if onset_index is not None
        else None
    )
    onset_latency_ms = (
        _rounded_float(float(window_time_ms[onset_index] - float(window["start_ms"])))
        if onset_index is not None
        else None
    )
    peak_time_ms = _rounded_float(float(window_time_ms[peak_index]))
    peak_latency_ms = _rounded_float(float(window_time_ms[peak_index] - float(window["start_ms"])))
    return {
        "bundle_id": str(bundle["bundle_id"]),
        "condition_ids": list(bundle["condition_ids"]),
        "condition_signature": str(bundle["condition_signature"]),
        "readout_id": readout_id,
        "readout_scope": str(readout_catalog_entry["scope"]),
        "readout_units": str(readout_catalog_entry["units"]),
        "window_id": str(window["window_id"]),
        "window_start_ms": _rounded_float(float(window["start_ms"])),
        "window_end_ms": _rounded_float(float(window["end_ms"])),
        "baseline_value": _rounded_float(baseline_value),
        "window_time_ms": _rounded_float_list(window_time_ms),
        "window_values": _rounded_float_list(window_values),
        "baseline_subtracted_values": _rounded_float_list(baseline_subtracted),
        "positive_response_values": _rounded_float_list(positive_response),
        "peak_value": _rounded_float(peak_value),
        "peak_time_ms": peak_time_ms,
        "peak_latency_ms": peak_latency_ms,
        "peak_selection_mode": str(policy["peak_selection_mode"]),
        "onset_threshold_value": _rounded_float(onset_threshold_value),
        "onset_time_ms": onset_time_ms,
        "onset_latency_ms": onset_latency_ms,
        "onset_segment_count_before_peak": int(onset_segment_count_before_peak),
        "signal_classification": signal_classification,
    }


def _normalize_analysis_plan(
    analysis_plan: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(analysis_plan, Mapping):
        raise ValueError("analysis_plan must be a mapping.")
    plan_version = _normalize_nonempty_string(
        analysis_plan.get("plan_version"),
        field_name="analysis_plan.plan_version",
    )
    condition_catalog_payload = analysis_plan.get("condition_catalog")
    if not isinstance(condition_catalog_payload, Sequence) or isinstance(
        condition_catalog_payload,
        (str, bytes),
    ):
        raise ValueError("analysis_plan.condition_catalog must be a list.")
    condition_ids_by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(condition_catalog_payload):
        if not isinstance(item, Mapping):
            raise ValueError(
                f"analysis_plan.condition_catalog[{index}] must be a mapping."
            )
        condition_id = _normalize_identifier(
            item.get("condition_id"),
            field_name=f"analysis_plan.condition_catalog[{index}].condition_id",
        )
        if condition_id in condition_ids_by_id:
            raise ValueError(
                f"analysis_plan.condition_catalog contains duplicate condition_id "
                f"{condition_id!r}."
            )
        condition_ids_by_id[condition_id] = copy.deepcopy(dict(item))

    window_catalog_payload = analysis_plan.get("analysis_window_catalog")
    if not isinstance(window_catalog_payload, Sequence) or isinstance(
        window_catalog_payload,
        (str, bytes),
    ):
        raise ValueError("analysis_plan.analysis_window_catalog must be a list.")
    windows_by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(window_catalog_payload):
        if not isinstance(item, Mapping):
            raise ValueError(
                f"analysis_plan.analysis_window_catalog[{index}] must be a mapping."
            )
        window_id = _normalize_identifier(
            item.get("window_id"),
            field_name=f"analysis_plan.analysis_window_catalog[{index}].window_id",
        )
        start_ms = _normalize_float(
            item.get("start_ms"),
            field_name=f"analysis_plan.analysis_window_catalog[{index}].start_ms",
        )
        end_ms = _normalize_float(
            item.get("end_ms"),
            field_name=f"analysis_plan.analysis_window_catalog[{index}].end_ms",
        )
        if end_ms <= start_ms:
            raise ValueError(
                f"analysis_plan.analysis_window_catalog[{index}] has end_ms <= start_ms."
            )
        windows_by_id[window_id] = {
            "window_id": window_id,
            "start_ms": float(start_ms),
            "end_ms": float(end_ms),
            "description": _normalize_nonempty_string(
                item.get("description", window_id),
                field_name=(
                    f"analysis_plan.analysis_window_catalog[{index}].description"
                ),
            ),
        }

    pair_catalog_payload = analysis_plan.get("condition_pair_catalog")
    if not isinstance(pair_catalog_payload, Sequence) or isinstance(
        pair_catalog_payload,
        (str, bytes),
    ):
        raise ValueError("analysis_plan.condition_pair_catalog must be a list.")
    condition_pairs_by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(pair_catalog_payload):
        if not isinstance(item, Mapping):
            raise ValueError(
                f"analysis_plan.condition_pair_catalog[{index}] must be a mapping."
            )
        pair_id = _normalize_identifier(
            item.get("pair_id"),
            field_name=f"analysis_plan.condition_pair_catalog[{index}].pair_id",
        )
        left_condition_id = _normalize_identifier(
            item.get("left_condition_id"),
            field_name=(
                f"analysis_plan.condition_pair_catalog[{index}].left_condition_id"
            ),
        )
        right_condition_id = _normalize_identifier(
            item.get("right_condition_id"),
            field_name=(
                f"analysis_plan.condition_pair_catalog[{index}].right_condition_id"
            ),
        )
        if left_condition_id not in condition_ids_by_id:
            raise ValueError(
                f"analysis_plan.condition_pair_catalog[{index}] references unknown "
                f"left_condition_id {left_condition_id!r}."
            )
        if right_condition_id not in condition_ids_by_id:
            raise ValueError(
                f"analysis_plan.condition_pair_catalog[{index}] references unknown "
                f"right_condition_id {right_condition_id!r}."
            )
        condition_pairs_by_id[pair_id] = {
            "pair_id": pair_id,
            "left_condition_id": left_condition_id,
            "right_condition_id": right_condition_id,
        }

    metric_recipe_payload = analysis_plan.get("metric_recipe_catalog")
    if not isinstance(metric_recipe_payload, Sequence) or isinstance(
        metric_recipe_payload,
        (str, bytes),
    ):
        raise ValueError("analysis_plan.metric_recipe_catalog must be a list.")
    metric_recipe_catalog: list[dict[str, Any]] = []
    for index, item in enumerate(metric_recipe_payload):
        if not isinstance(item, Mapping):
            raise ValueError(
                f"analysis_plan.metric_recipe_catalog[{index}] must be a mapping."
            )
        metric_id = _normalize_identifier(
            item.get("metric_id"),
            field_name=f"analysis_plan.metric_recipe_catalog[{index}].metric_id",
        )
        readout_ids_payload = item.get("active_readout_ids")
        if not isinstance(readout_ids_payload, Sequence) or isinstance(
            readout_ids_payload,
            (str, bytes),
        ):
            raise ValueError(
                f"analysis_plan.metric_recipe_catalog[{index}].active_readout_ids "
                "must be a list."
            )
        normalized_readout_ids = [
            _normalize_identifier(
                readout_id,
                field_name=(
                    f"analysis_plan.metric_recipe_catalog[{index}].active_readout_ids"
                ),
            )
            for readout_id in readout_ids_payload
        ]
        if len(normalized_readout_ids) != 1:
            raise ValueError(
                f"Shared-readout analysis expects exactly one active_readout_id per "
                f"recipe, got {normalized_readout_ids!r} for recipe index {index}."
            )
        window_id = _normalize_identifier(
            item.get("window_id"),
            field_name=f"analysis_plan.metric_recipe_catalog[{index}].window_id",
        )
        if window_id not in windows_by_id:
            raise ValueError(
                f"analysis_plan.metric_recipe_catalog[{index}] references unknown "
                f"window_id {window_id!r}."
            )
        condition_ids_payload = item.get("condition_ids", [])
        if not isinstance(condition_ids_payload, Sequence) or isinstance(
            condition_ids_payload,
            (str, bytes),
        ):
            raise ValueError(
                f"analysis_plan.metric_recipe_catalog[{index}].condition_ids must be a list."
            )
        normalized_condition_ids = sorted(
            {
                _normalize_identifier(
                    condition_id,
                    field_name=(
                        f"analysis_plan.metric_recipe_catalog[{index}].condition_ids"
                    ),
                )
                for condition_id in condition_ids_payload
            }
        )
        unknown_condition_ids = sorted(
            set(normalized_condition_ids) - set(condition_ids_by_id)
        )
        if unknown_condition_ids:
            raise ValueError(
                f"analysis_plan.metric_recipe_catalog[{index}] references unknown "
                f"condition_ids {unknown_condition_ids!r}."
            )
        condition_pair_id_payload = item.get("condition_pair_id")
        condition_pair_id = (
            _normalize_identifier(
                condition_pair_id_payload,
                field_name=(
                    f"analysis_plan.metric_recipe_catalog[{index}].condition_pair_id"
                ),
            )
            if condition_pair_id_payload is not None
            else None
        )
        if condition_pair_id is not None and condition_pair_id not in condition_pairs_by_id:
            raise ValueError(
                f"analysis_plan.metric_recipe_catalog[{index}] references unknown "
                f"condition_pair_id {condition_pair_id!r}."
            )
        metric_recipe_catalog.append(
            {
                "recipe_id": _normalize_identifier(
                    item.get("recipe_id"),
                    field_name=f"analysis_plan.metric_recipe_catalog[{index}].recipe_id",
                ),
                "metric_id": metric_id,
                "active_readout_id": normalized_readout_ids[0],
                "condition_ids": normalized_condition_ids,
                "condition_pair_id": condition_pair_id,
                "window_id": window_id,
                "window_reference": copy.deepcopy(windows_by_id[window_id]),
            }
        )
    return {
        "plan_version": plan_version,
        "condition_ids_by_id": condition_ids_by_id,
        "condition_pairs_by_id": condition_pairs_by_id,
        "metric_recipe_catalog": metric_recipe_catalog,
    }


def _normalize_kernel_policy(
    kernel_policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw_policy = dict(DEFAULT_SHARED_READOUT_ANALYSIS_POLICY)
    if kernel_policy is not None:
        if not isinstance(kernel_policy, Mapping):
            raise ValueError("kernel_policy must be a mapping when provided.")
        raw_policy.update(kernel_policy)
    baseline_mode = _normalize_nonempty_string(
        raw_policy.get("baseline_mode"),
        field_name="kernel_policy.baseline_mode",
    )
    negative_response_mode = _normalize_nonempty_string(
        raw_policy.get("negative_response_mode"),
        field_name="kernel_policy.negative_response_mode",
    )
    peak_selection_mode = _normalize_nonempty_string(
        raw_policy.get("peak_selection_mode"),
        field_name="kernel_policy.peak_selection_mode",
    )
    pairing_key_mode = _normalize_nonempty_string(
        raw_policy.get("pairing_key_mode"),
        field_name="kernel_policy.pairing_key_mode",
    )
    if baseline_mode != "mean_pre_window_else_first_window_sample":
        raise ValueError(
            f"Unsupported kernel_policy.baseline_mode {baseline_mode!r}."
        )
    if negative_response_mode != "clip_to_zero_after_baseline_subtraction":
        raise ValueError(
            f"Unsupported kernel_policy.negative_response_mode {negative_response_mode!r}."
        )
    if peak_selection_mode != "first_maximum_sample_in_window":
        raise ValueError(
            f"Unsupported kernel_policy.peak_selection_mode {peak_selection_mode!r}."
        )
    if pairing_key_mode != "derive_from_nonpaired_condition_ids":
        raise ValueError(
            f"Unsupported kernel_policy.pairing_key_mode {pairing_key_mode!r}."
        )
    return {
        "baseline_mode": baseline_mode,
        "negative_response_mode": negative_response_mode,
        "peak_selection_mode": peak_selection_mode,
        "pairing_key_mode": pairing_key_mode,
        "latency_onset_threshold_fraction_of_peak": _normalize_positive_float(
            raw_policy.get("latency_onset_threshold_fraction_of_peak"),
            field_name="kernel_policy.latency_onset_threshold_fraction_of_peak",
        ),
        "minimum_signal_amplitude": _normalize_positive_float(
            raw_policy.get("minimum_signal_amplitude"),
            field_name="kernel_policy.minimum_signal_amplitude",
        ),
    }


def _normalize_bundle_record(
    record: Mapping[str, Any],
    *,
    condition_ids_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise ValueError("bundle_records entries must be mappings.")
    metadata_payload = record.get("bundle_metadata", record)
    metadata = parse_simulator_result_bundle_metadata(metadata_payload)
    condition_ids_payload = record.get("condition_ids")
    if not isinstance(condition_ids_payload, Sequence) or isinstance(
        condition_ids_payload,
        (str, bytes),
    ):
        raise ValueError("bundle_records.condition_ids must be a list.")
    condition_ids = sorted(
        {
            _normalize_identifier(
                condition_id,
                field_name="bundle_records.condition_ids",
            )
            for condition_id in condition_ids_payload
        }
    )
    unknown_condition_ids = sorted(
        set(condition_ids) - set(condition_ids_by_id)
    )
    if unknown_condition_ids:
        raise ValueError(
            f"bundle_records.condition_ids contains unknown condition ids "
            f"{unknown_condition_ids!r}."
        )
    payload = (
        _normalize_shared_readout_payload(
            record["shared_readout_payload"],
            metadata=metadata,
        )
        if "shared_readout_payload" in record
        else _normalize_shared_readout_payload(
            load_simulator_shared_readout_payload(metadata),
            metadata=metadata,
        )
    )
    pairing_keys = _normalize_pairing_keys(record.get("pairing_keys"))
    analysis_group_id_payload = record.get("analysis_group_id")
    if analysis_group_id_payload is None:
        analysis_group_id = _default_analysis_group_id(metadata)
    else:
        analysis_group_id = _normalize_nonempty_string(
            analysis_group_id_payload,
            field_name="bundle_records.analysis_group_id",
        )
    readout_catalog = [
        copy.deepcopy(dict(item))
        for item in metadata["readout_catalog"]
    ]
    readout_catalog_by_id = {
        str(item["readout_id"]): copy.deepcopy(dict(item))
        for item in readout_catalog
    }
    return {
        "analysis_group_id": analysis_group_id,
        "bundle_id": str(metadata["bundle_id"]),
        "arm_id": str(metadata["arm_reference"]["arm_id"]),
        "baseline_family": metadata["arm_reference"]["baseline_family"],
        "model_mode": str(metadata["arm_reference"]["model_mode"]),
        "seed": int(metadata["determinism"]["seed"]),
        "timebase": copy.deepcopy(dict(metadata["timebase"])),
        "condition_ids": condition_ids,
        "condition_signature": _condition_signature(condition_ids),
        "pairing_keys": pairing_keys,
        "time_ms": np.asarray(payload["time_ms"], dtype=np.float64),
        "values": np.asarray(payload["values"], dtype=np.float64),
        "readout_ids": tuple(str(item) for item in payload["readout_ids"]),
        "readout_index_by_id": {
            str(readout_id): index
            for index, readout_id in enumerate(payload["readout_ids"])
        },
        "readout_catalog_by_id": readout_catalog_by_id,
    }


def _normalize_shared_readout_payload(
    payload: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("shared_readout_payload must be a mapping.")
    time_ms = np.asarray(payload.get("time_ms"), dtype=np.float64)
    readout_ids_raw = payload.get("readout_ids")
    values = np.asarray(payload.get("values"), dtype=np.float64)
    if time_ms.ndim != 1:
        raise ValueError("shared_readout_payload.time_ms must be a 1D array.")
    if values.ndim != 2:
        raise ValueError("shared_readout_payload.values must be a 2D array.")
    if not isinstance(readout_ids_raw, Sequence) or isinstance(readout_ids_raw, (str, bytes)):
        raise ValueError("shared_readout_payload.readout_ids must be a sequence.")
    readout_ids = tuple(
        _normalize_identifier(
            item,
            field_name="shared_readout_payload.readout_ids",
        )
        for item in readout_ids_raw
    )
    if len(set(readout_ids)) != len(readout_ids):
        raise ValueError("shared_readout_payload.readout_ids contains duplicates.")
    if values.shape != (time_ms.size, len(readout_ids)):
        raise ValueError(
            "shared_readout_payload.values shape must match "
            "(len(time_ms), len(readout_ids))."
        )
    normalized_timebase = normalize_simulator_timebase(metadata["timebase"])
    expected_time_ms = (
        float(normalized_timebase["time_origin_ms"])
        + float(normalized_timebase["dt_ms"]) * np.arange(
            int(normalized_timebase["sample_count"]),
            dtype=np.float64,
        )
    )
    if time_ms.size != expected_time_ms.size or not np.allclose(
        time_ms,
        expected_time_ms,
        rtol=0.0,
        atol=_TIME_ABS_TOLERANCE,
    ):
        raise ValueError(
            f"shared_readout_payload.time_ms must match the declared simulator timebase "
            f"for bundle {metadata['bundle_id']!r}."
        )
    metadata_readout_ids = tuple(
        str(item["readout_id"])
        for item in metadata["readout_catalog"]
    )
    if readout_ids != metadata_readout_ids:
        raise ValueError(
            f"shared_readout_payload.readout_ids {readout_ids!r} do not match the "
            f"bundle readout catalog order {metadata_readout_ids!r}."
        )
    return {
        "time_ms": time_ms,
        "readout_ids": readout_ids,
        "values": values,
    }


def _normalize_pairing_keys(payload: Any) -> dict[str, str]:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError("bundle_records.pairing_keys must be a mapping when provided.")
    return {
        _normalize_identifier(pair_id, field_name="bundle_records.pairing_keys"): _normalize_nonempty_string(
            pairing_key,
            field_name=f"bundle_records.pairing_keys.{pair_id}",
        )
        for pair_id, pairing_key in payload.items()
    }


def _group_bundle_records(
    bundles: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for bundle in bundles:
        grouped.setdefault(str(bundle["analysis_group_id"]), []).append(
            copy.deepcopy(dict(bundle))
        )
    for group_id in list(grouped):
        grouped[group_id].sort(
            key=lambda item: (
                str(item["condition_signature"]),
                str(item["bundle_id"]),
            )
        )
    return grouped


def _default_analysis_group_id(metadata: Mapping[str, Any]) -> str:
    return (
        f"{metadata['manifest_reference']['experiment_id']}::"
        f"{metadata['arm_reference']['arm_id']}::"
        f"seed_{metadata['determinism']['seed']}"
    )


def _bundle_pairing_key(
    bundle: Mapping[str, Any],
    pair_definition: Mapping[str, Any],
) -> str:
    pair_id = str(pair_definition["pair_id"])
    explicit_key = bundle["pairing_keys"].get(pair_id)
    if explicit_key is not None:
        return explicit_key
    remaining_conditions = sorted(
        set(bundle["condition_ids"])
        - {
            str(pair_definition["left_condition_id"]),
            str(pair_definition["right_condition_id"]),
        }
    )
    if not remaining_conditions:
        return _DEFAULT_PAIRING_KEY
    return "__".join(remaining_conditions)


def _condition_signature(condition_ids: Sequence[str]) -> str:
    if not condition_ids:
        return "unlabeled"
    return "__".join(sorted(str(item) for item in condition_ids))


def _contiguous_true_segments(mask: np.ndarray) -> list[tuple[int, int]]:
    segments: list[tuple[int, int]] = []
    start_index: int | None = None
    for index, value in enumerate(mask.tolist()):
        if bool(value):
            if start_index is None:
                start_index = index
            continue
        if start_index is not None:
            segments.append((start_index, index - 1))
            start_index = None
    if start_index is not None:
        segments.append((start_index, len(mask) - 1))
    return segments


def _rounded_float(value: float) -> float:
    if not math.isfinite(float(value)):
        raise ValueError(f"Expected a finite float, got {value!r}.")
    return round(float(value), 12)


def _rounded_float_list(values: np.ndarray) -> list[float]:
    return [_rounded_float(float(value)) for value in np.asarray(values, dtype=np.float64).tolist()]
