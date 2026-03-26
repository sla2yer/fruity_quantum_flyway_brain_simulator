from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .readout_analysis_contract import (
    MOTION_DECODER_ESTIMATES_TASK_FAMILY,
    PER_TASK_DECODER_WINDOW_SCOPE,
    READOUT_ANALYSIS_CONTRACT_VERSION,
    RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS,
    SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
    SHARED_READOUT_TRACES_ARTIFACT_CLASS,
    SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
    STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
    TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
    get_readout_analysis_metric_definition,
)
from .retinal_contract import load_retinal_bundle_metadata
from .shared_readout_analysis import (
    _bundle_pairing_key,
    _compute_window_response_summary,
    _group_bundle_records,
    _normalize_analysis_plan,
    _normalize_bundle_record,
    _normalize_kernel_policy,
    _rounded_float,
)
from .simulator_result_contract import parse_simulator_result_bundle_metadata
from .stimulus_contract import (
    load_stimulus_bundle_metadata,
    _normalize_float,
    _normalize_identifier,
    _normalize_nonempty_string,
    _normalize_positive_float,
)


TASK_DECODER_INTERFACE_VERSION = "task_decoder_interface.v1"

MOTION_VECTOR_DECODER_ID = "motion_vector"
OPTIC_FLOW_DECODER_ID = "optic_flow"

SUPPORTED_TASK_DECODER_IDS = (
    MOTION_VECTOR_DECODER_ID,
    OPTIC_FLOW_DECODER_ID,
)
SUPPORTED_TASK_DECODER_ANALYSIS_METRIC_IDS = frozenset(
    {
        "motion_vector_heading_deg",
        "motion_vector_speed_deg_per_s",
        "optic_flow_heading_deg",
        "optic_flow_speed_deg_per_s",
    }
)

DEFAULT_TASK_DECODER_POLICY = {
    "baseline_mode": "mean_pre_window_else_first_window_sample",
    "negative_response_mode": "clip_to_zero_after_baseline_subtraction",
    "peak_selection_mode": "first_maximum_sample_in_window",
    "pairing_key_mode": "derive_from_nonpaired_condition_ids",
    "latency_onset_threshold_fraction_of_peak": 0.1,
    "minimum_signal_amplitude": 1.0e-9,
    "minimum_vector_norm": 1.0e-9,
    "speed_scale_mode": "declared_speed_times_normalized_directional_evidence",
}

_TASK_KIND_LOCAL_MOTION_PATCH = "local_motion_patch"
_HEADING_REFERENCE = "0_deg_positive_azimuth_counterclockwise_to_positive_elevation"
_AGGREGATED_PAIRING_KEY = "aggregated_direction_pairs"
_DIRECTION_VALUE_TOLERANCE = 1.0e-6
_SPEED_VALUE_TOLERANCE = 1.0e-9
_LOCAL_AXIS_TOLERANCE = 1.0e-9

_DIRECTION_STATISTIC = "decoded_heading_deg"
_SPEED_STATISTIC = "decoded_speed_deg_per_s"
_SUPPORTED_DIRECTION_PARAMETER_NAMES = ("direction_deg", "drift_direction_deg")
_SUPPORTED_SPEED_PARAMETER_NAMES = (
    "velocity_deg_per_s",
    "radial_speed_deg_per_s",
    "angular_velocity_deg_per_s",
)
_SUPPORTED_RETINAL_ARTIFACT_TYPES = ("retinal_bundle", "retinal_input_bundle")


def build_task_decoder_definition(
    *,
    decoder_id: str,
    display_name: str,
    description: str,
    supported_metric_ids: Sequence[str],
    required_condition_pair_ids: Sequence[str],
    required_source_artifact_classes: Sequence[str],
    required_task_context_fields: Sequence[str],
    required_retinotopic_context_fields: Sequence[str],
    derived_shared_readout_quantities: Sequence[str],
    minimum_condition_structure: str,
    output_conventions: Mapping[str, Any],
) -> dict[str, Any]:
    return parse_task_decoder_definition(
        {
            "decoder_id": decoder_id,
            "task_family_id": MOTION_DECODER_ESTIMATES_TASK_FAMILY,
            "scope_rule": PER_TASK_DECODER_WINDOW_SCOPE,
            "display_name": display_name,
            "description": description,
            "supported_metric_ids": list(supported_metric_ids),
            "required_condition_pair_ids": list(required_condition_pair_ids),
            "required_source_artifact_classes": list(required_source_artifact_classes),
            "required_task_context_fields": list(required_task_context_fields),
            "required_retinotopic_context_fields": list(
                required_retinotopic_context_fields
            ),
            "derived_shared_readout_quantities": list(derived_shared_readout_quantities),
            "minimum_condition_structure": minimum_condition_structure,
            "output_conventions": copy.deepcopy(dict(output_conventions)),
        }
    )


def parse_task_decoder_definition(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Task-decoder definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "decoder_id",
        "task_family_id",
        "scope_rule",
        "display_name",
        "description",
        "supported_metric_ids",
        "required_condition_pair_ids",
        "required_source_artifact_classes",
        "required_task_context_fields",
        "required_retinotopic_context_fields",
        "derived_shared_readout_quantities",
        "minimum_condition_structure",
        "output_conventions",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"Task-decoder definition is missing required fields: {missing_fields!r}."
        )
    normalized["decoder_id"] = _normalize_identifier(
        normalized["decoder_id"],
        field_name="task_decoder.decoder_id",
    )
    if normalized["decoder_id"] not in SUPPORTED_TASK_DECODER_IDS:
        raise ValueError(
            f"Unsupported task_decoder.decoder_id {normalized['decoder_id']!r}."
        )
    normalized["task_family_id"] = _normalize_identifier(
        normalized["task_family_id"],
        field_name="task_decoder.task_family_id",
    )
    if normalized["task_family_id"] != MOTION_DECODER_ESTIMATES_TASK_FAMILY:
        raise ValueError(
            "Task-decoder definitions must stay in task_family_id "
            f"{MOTION_DECODER_ESTIMATES_TASK_FAMILY!r}."
        )
    normalized["scope_rule"] = _normalize_nonempty_string(
        normalized["scope_rule"],
        field_name="task_decoder.scope_rule",
    )
    if normalized["scope_rule"] != PER_TASK_DECODER_WINDOW_SCOPE:
        raise ValueError(
            "Task-decoder definitions must use scope_rule "
            f"{PER_TASK_DECODER_WINDOW_SCOPE!r}."
        )
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="task_decoder.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="task_decoder.description",
    )
    normalized["supported_metric_ids"] = _normalize_identifier_list(
        normalized["supported_metric_ids"],
        field_name="task_decoder.supported_metric_ids",
        allow_empty=False,
    )
    unsupported_metric_ids = sorted(
        set(normalized["supported_metric_ids"]) - set(SUPPORTED_TASK_DECODER_ANALYSIS_METRIC_IDS)
    )
    if unsupported_metric_ids:
        raise ValueError(
            f"Task-decoder definitions reference unsupported metric ids {unsupported_metric_ids!r}."
        )
    normalized["required_condition_pair_ids"] = _normalize_identifier_list(
        normalized["required_condition_pair_ids"],
        field_name="task_decoder.required_condition_pair_ids",
        allow_empty=False,
    )
    normalized["required_source_artifact_classes"] = _normalize_nonempty_string_list(
        normalized["required_source_artifact_classes"],
        field_name="task_decoder.required_source_artifact_classes",
    )
    normalized["required_task_context_fields"] = _normalize_nonempty_string_list(
        normalized["required_task_context_fields"],
        field_name="task_decoder.required_task_context_fields",
    )
    normalized["required_retinotopic_context_fields"] = _normalize_nonempty_string_list(
        normalized["required_retinotopic_context_fields"],
        field_name="task_decoder.required_retinotopic_context_fields",
    )
    normalized["derived_shared_readout_quantities"] = _normalize_nonempty_string_list(
        normalized["derived_shared_readout_quantities"],
        field_name="task_decoder.derived_shared_readout_quantities",
    )
    normalized["minimum_condition_structure"] = _normalize_nonempty_string(
        normalized["minimum_condition_structure"],
        field_name="task_decoder.minimum_condition_structure",
    )
    if not isinstance(normalized["output_conventions"], Mapping):
        raise ValueError("task_decoder.output_conventions must be a mapping.")
    normalized["output_conventions"] = copy.deepcopy(dict(normalized["output_conventions"]))
    return normalized


def discover_task_decoder_definitions() -> list[dict[str, Any]]:
    return [
        copy.deepcopy(item)
        for item in _default_task_decoder_catalog()
    ]


def get_task_decoder_definition(decoder_id: str) -> dict[str, Any]:
    normalized_decoder_id = _normalize_identifier(
        decoder_id,
        field_name="decoder_id",
    )
    for item in _default_task_decoder_catalog():
        if item["decoder_id"] == normalized_decoder_id:
            return copy.deepcopy(item)
    raise ValueError(f"Unknown task decoder {normalized_decoder_id!r}.")


def decoder_id_for_metric(metric_id: str) -> str:
    normalized_metric_id = _normalize_identifier(metric_id, field_name="metric_id")
    if normalized_metric_id in {
        "motion_vector_heading_deg",
        "motion_vector_speed_deg_per_s",
    }:
        return MOTION_VECTOR_DECODER_ID
    if normalized_metric_id in {
        "optic_flow_heading_deg",
        "optic_flow_speed_deg_per_s",
    }:
        return OPTIC_FLOW_DECODER_ID
    raise ValueError(f"Metric {normalized_metric_id!r} is not a supported task-decoder metric.")


def compute_task_decoder_analysis(
    *,
    analysis_plan: Mapping[str, Any],
    bundle_records: Sequence[Mapping[str, Any]],
    task_context: Mapping[str, Any] | None = None,
    retinotopic_context: Mapping[str, Any] | None = None,
    decoder_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_plan = _normalize_analysis_plan(analysis_plan)
    normalized_policy = _normalize_decoder_policy(decoder_policy)
    normalized_global_task_context = _normalize_task_context(task_context)
    normalized_global_retinotopic_context = _normalize_retinotopic_context(
        retinotopic_context
    )
    normalized_bundles = [
        _normalize_task_decoder_bundle_record(
            item,
            condition_ids_by_id=normalized_plan["condition_ids_by_id"],
        )
        for item in bundle_records
    ]
    grouped_bundles = _group_bundle_records(normalized_bundles)
    decoder_requests = _build_decoder_requests(normalized_plan)

    metric_rows: list[dict[str, Any]] = []
    decoder_summaries: list[dict[str, Any]] = []
    skipped_recipes: list[dict[str, Any]] = []

    for request in decoder_requests:
        if request["decoder_id"] not in SUPPORTED_TASK_DECODER_IDS:
            skipped_recipes.extend(
                [
                    {
                        "recipe_id": str(request["recipe_ids_by_metric"][metric_id]),
                        "metric_id": metric_id,
                        "reason": "decoder_id_not_yet_implemented",
                    }
                    for metric_id in request["metric_ids"]
                ]
            )
            continue
        decoder_definition = get_task_decoder_definition(str(request["decoder_id"]))
        for analysis_group_id, bundles in grouped_bundles.items():
            summary = _compute_decoder_summary(
                request=request,
                decoder_definition=decoder_definition,
                analysis_group_id=str(analysis_group_id),
                bundles=bundles,
                condition_pairs_by_id=normalized_plan["condition_pairs_by_id"],
                condition_ids_by_id=normalized_plan["condition_ids_by_id"],
                global_task_context=normalized_global_task_context,
                global_retinotopic_context=normalized_global_retinotopic_context,
                policy=normalized_policy,
            )
            decoder_summaries.append(summary)
            metric_rows.extend(
                _decoder_summary_metric_rows(
                    request=request,
                    summary=summary,
                )
            )

    metric_rows.sort(
        key=lambda row: (
            str(row["analysis_group_id"]),
            str(row["metric_id"]),
            str(row["readout_id"]),
            str(row["recipe_id"]),
        )
    )
    decoder_summaries.sort(
        key=lambda item: (
            str(item["analysis_group_id"]),
            str(item["decoder_id"]),
            str(item["readout_id"]),
            str(item["window_id"]),
        )
    )
    skipped_recipes.sort(key=lambda item: (str(item["metric_id"]), str(item["recipe_id"])))

    return {
        "contract_version": READOUT_ANALYSIS_CONTRACT_VERSION,
        "analysis_plan_version": str(normalized_plan["plan_version"]),
        "task_decoder_interface_version": TASK_DECODER_INTERFACE_VERSION,
        "decoder_policy": copy.deepcopy(normalized_policy),
        "decoder_catalog": discover_task_decoder_definitions(),
        "supported_decoder_ids": list(SUPPORTED_TASK_DECODER_IDS),
        "supported_metric_ids": sorted(SUPPORTED_TASK_DECODER_ANALYSIS_METRIC_IDS),
        "metric_rows": metric_rows,
        "decoder_summaries": decoder_summaries,
        "skipped_recipes": skipped_recipes,
    }


def _build_decoder_requests(
    normalized_plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    grouped_requests: dict[tuple[str, str, str, str | None], dict[str, Any]] = {}
    for recipe in normalized_plan["metric_recipe_catalog"]:
        metric_id = str(recipe["metric_id"])
        if metric_id not in SUPPORTED_TASK_DECODER_ANALYSIS_METRIC_IDS:
            continue
        decoder_id = decoder_id_for_metric(metric_id)
        key = (
            decoder_id,
            str(recipe["active_readout_id"]),
            str(recipe["window_id"]),
            (
                str(recipe["condition_pair_id"])
                if recipe["condition_pair_id"] is not None
                else None
            ),
        )
        request = grouped_requests.setdefault(
            key,
            {
                "decoder_id": decoder_id,
                "readout_id": str(recipe["active_readout_id"]),
                "window_id": str(recipe["window_id"]),
                "window_reference": copy.deepcopy(dict(recipe["window_reference"])),
                "condition_pair_id": (
                    str(recipe["condition_pair_id"])
                    if recipe["condition_pair_id"] is not None
                    else None
                ),
                "metric_ids": [],
                "recipe_ids_by_metric": {},
            },
        )
        request["metric_ids"].append(metric_id)
        request["recipe_ids_by_metric"][metric_id] = str(recipe["recipe_id"])
    records = []
    for request in grouped_requests.values():
        request["metric_ids"] = sorted(set(request["metric_ids"]))
        records.append(request)
    records.sort(
        key=lambda item: (
            str(item["decoder_id"]),
            str(item["readout_id"]),
            str(item["window_id"]),
            str(item["condition_pair_id"] or ""),
        )
    )
    return records


def _compute_decoder_summary(
    *,
    request: Mapping[str, Any],
    decoder_definition: Mapping[str, Any],
    analysis_group_id: str,
    bundles: Sequence[Mapping[str, Any]],
    condition_pairs_by_id: Mapping[str, Mapping[str, Any]],
    condition_ids_by_id: Mapping[str, Mapping[str, Any]],
    global_task_context: Mapping[str, Any],
    global_retinotopic_context: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    pair_id = request["condition_pair_id"]
    if pair_id is None:
        raise ValueError(
            f"Task decoder {request['decoder_id']!r} requires a directional condition pair, "
            f"but recipe(s) {sorted(request['recipe_ids_by_metric'].values())!r} do not declare one."
        )
    if pair_id not in condition_pairs_by_id:
        raise ValueError(
            f"Task decoder {request['decoder_id']!r} references unknown condition_pair_id "
            f"{pair_id!r}."
        )
    pair_definition = dict(condition_pairs_by_id[pair_id])

    left_condition_id = str(pair_definition["left_condition_id"])
    right_condition_id = str(pair_definition["right_condition_id"])
    relevant_bundles = [
        bundle
        for bundle in bundles
        if left_condition_id in set(bundle["condition_ids"])
        or right_condition_id in set(bundle["condition_ids"])
    ]
    if not relevant_bundles:
        return _unavailable_decoder_summary(
            request=request,
            decoder_definition=decoder_definition,
            analysis_group_id=analysis_group_id,
            status="missing_condition",
            message=(
                f"Analysis group {analysis_group_id!r} does not provide any bundles for "
                f"condition pair {pair_id!r}."
            ),
        )

    resolved_task_context = _resolve_group_task_context(
        relevant_bundles=relevant_bundles,
        pair_definition=pair_definition,
        condition_ids_by_id=condition_ids_by_id,
        global_task_context=global_task_context,
    )
    resolved_retinotopic_context = _resolve_group_retinotopic_context(
        relevant_bundles=relevant_bundles,
        global_retinotopic_context=global_retinotopic_context,
    )
    _require_decoder_context(
        decoder_definition=decoder_definition,
        task_context=resolved_task_context,
        retinotopic_context=resolved_retinotopic_context,
        metric_ids=request["metric_ids"],
    )

    evidence_rows: list[dict[str, Any]] = []
    missing_pairing_keys: list[str] = []
    keys = {
        _bundle_pairing_key(bundle, pair_definition)
        for bundle in relevant_bundles
        if left_condition_id in set(bundle["condition_ids"])
        or right_condition_id in set(bundle["condition_ids"])
    }
    for pairing_key in sorted(keys):
        left_candidates = [
            bundle
            for bundle in relevant_bundles
            if left_condition_id in set(bundle["condition_ids"])
            and _bundle_pairing_key(bundle, pair_definition) == pairing_key
        ]
        right_candidates = [
            bundle
            for bundle in relevant_bundles
            if right_condition_id in set(bundle["condition_ids"])
            and _bundle_pairing_key(bundle, pair_definition) == pairing_key
        ]
        if len(left_candidates) > 1 or len(right_candidates) > 1:
            raise ValueError(
                f"Task decoder {request['decoder_id']!r} found ambiguous bundle pairing for "
                f"analysis_group_id {analysis_group_id!r} and pairing_key {pairing_key!r}. "
                "Provide one unique preferred/null bundle pair per non-directional condition."
            )
        if not left_candidates or not right_candidates:
            missing_pairing_keys.append(str(pairing_key))
            continue

        left_bundle = left_candidates[0]
        right_bundle = right_candidates[0]
        if left_bundle["timebase"] != right_bundle["timebase"]:
            raise ValueError(
                f"Task decoder {request['decoder_id']!r} requires a shared timebase, but "
                f"bundle {left_bundle['bundle_id']!r} and {right_bundle['bundle_id']!r} disagree."
            )
        left_summary = _compute_window_response_summary(
            bundle=left_bundle,
            readout_id=str(request["readout_id"]),
            window=request["window_reference"],
            policy=policy,
        )
        right_summary = _compute_window_response_summary(
            bundle=right_bundle,
            readout_id=str(request["readout_id"]),
            window=request["window_reference"],
            policy=policy,
        )
        preferred_peak = float(left_summary["peak_value"])
        null_peak = float(right_summary["peak_value"])
        response_total = preferred_peak + null_peak
        response_delta = preferred_peak - null_peak
        if response_total <= float(policy["minimum_signal_amplitude"]):
            signal_status = "no_signal"
            normalized_directional_evidence = 0.0
        else:
            signal_status = "ok"
            normalized_directional_evidence = response_delta / response_total
        preferred_heading_deg = float(resolved_task_context["preferred_direction_deg"])
        contribution_vector = normalized_directional_evidence * _direction_unit_vector(
            preferred_heading_deg
        )
        evidence_rows.append(
            {
                "pairing_key": str(pairing_key),
                "preferred_bundle_id": str(left_bundle["bundle_id"]),
                "null_bundle_id": str(right_bundle["bundle_id"]),
                "preferred_condition_id": left_condition_id,
                "null_condition_id": right_condition_id,
                "preferred_peak_value": _rounded_float(preferred_peak),
                "null_peak_value": _rounded_float(null_peak),
                "response_total": _rounded_float(response_total),
                "response_delta": _rounded_float(response_delta),
                "normalized_directional_evidence": _rounded_float(
                    normalized_directional_evidence
                ),
                "preferred_direction_deg": _rounded_float(preferred_heading_deg),
                "signal_status": signal_status,
                "preferred_response_summary": left_summary,
                "null_response_summary": right_summary,
                "contribution_unit_vector": _rounded_float_list(contribution_vector),
            }
        )

    valid_evidence = [
        item
        for item in evidence_rows
        if item["signal_status"] == "ok"
    ]
    if not valid_evidence:
        return _unavailable_decoder_summary(
            request=request,
            decoder_definition=decoder_definition,
            analysis_group_id=analysis_group_id,
            status="no_signal",
            message=(
                f"Task decoder {request['decoder_id']!r} found no valid preferred/null "
                "readout evidence above the minimum signal threshold."
            ),
            task_context=resolved_task_context,
            retinotopic_context=resolved_retinotopic_context,
            evidence_rows=evidence_rows,
            missing_pairing_keys=missing_pairing_keys,
        )

    aggregate_vector = np.sum(
        [
            np.asarray(item["contribution_unit_vector"], dtype=np.float64)
            * abs(float(item["response_total"]))
            for item in valid_evidence
        ],
        axis=0,
        dtype=np.float64,
    )
    aggregate_support = float(
        np.sum(
            [abs(float(item["response_total"])) for item in valid_evidence],
            dtype=np.float64,
        )
    )
    if aggregate_support <= float(policy["minimum_signal_amplitude"]):
        return _unavailable_decoder_summary(
            request=request,
            decoder_definition=decoder_definition,
            analysis_group_id=analysis_group_id,
            status="no_signal",
            message=(
                f"Task decoder {request['decoder_id']!r} could not realize a nonzero "
                "aggregate directional support value."
            ),
            task_context=resolved_task_context,
            retinotopic_context=resolved_retinotopic_context,
            evidence_rows=evidence_rows,
            missing_pairing_keys=missing_pairing_keys,
        )

    net_vector_norm = float(np.linalg.norm(aggregate_vector))
    normalized_directional_support = min(
        1.0,
        max(0.0, net_vector_norm / aggregate_support),
    )
    if net_vector_norm <= float(policy["minimum_vector_norm"]):
        return _unavailable_decoder_summary(
            request=request,
            decoder_definition=decoder_definition,
            analysis_group_id=analysis_group_id,
            status="no_directional_signal",
            message=(
                f"Task decoder {request['decoder_id']!r} found balanced preferred/null evidence "
                "with no resolvable directional vector."
            ),
            task_context=resolved_task_context,
            retinotopic_context=resolved_retinotopic_context,
            evidence_rows=evidence_rows,
            missing_pairing_keys=missing_pairing_keys,
        )

    motion_heading_deg = _heading_deg_from_vector(aggregate_vector)
    declared_speed_deg_per_s = float(resolved_task_context["declared_speed_deg_per_s"])
    if str(policy["speed_scale_mode"]) != "declared_speed_times_normalized_directional_evidence":
        raise ValueError(
            f"Unsupported decoder_policy.speed_scale_mode {policy['speed_scale_mode']!r}."
        )
    motion_speed_deg_per_s = declared_speed_deg_per_s * normalized_directional_support
    motion_vector_global = _direction_unit_vector(motion_heading_deg) * motion_speed_deg_per_s
    optic_flow_local = _project_global_vector_into_retinotopic_basis(
        global_vector=motion_vector_global,
        retinotopic_context=resolved_retinotopic_context,
    )
    optic_flow_heading_deg = _heading_deg_from_vector(optic_flow_local)
    optic_flow_speed_deg_per_s = float(np.linalg.norm(optic_flow_local))

    representative_evidence = valid_evidence[0]
    metric_values = {
        "motion_vector_heading_deg": _rounded_float(motion_heading_deg),
        "motion_vector_speed_deg_per_s": _rounded_float(motion_speed_deg_per_s),
        "optic_flow_heading_deg": _rounded_float(optic_flow_heading_deg),
        "optic_flow_speed_deg_per_s": _rounded_float(optic_flow_speed_deg_per_s),
    }
    return {
        "decoder_id": str(request["decoder_id"]),
        "task_family_id": MOTION_DECODER_ESTIMATES_TASK_FAMILY,
        "analysis_group_id": str(analysis_group_id),
        "status": "ok",
        "status_message": None,
        "readout_id": str(request["readout_id"]),
        "scope": str(representative_evidence["preferred_response_summary"]["readout_scope"]),
        "window_id": str(request["window_id"]),
        "condition_pair_id": str(pair_id),
        "condition_ids": [left_condition_id, right_condition_id],
        "condition_signature": f"{left_condition_id}__vs__{right_condition_id}",
        "pairing_key": _AGGREGATED_PAIRING_KEY,
        "bundle_ids": sorted(
            {
                str(item["preferred_bundle_id"])
                for item in evidence_rows
            }
            | {
                str(item["null_bundle_id"])
                for item in evidence_rows
            }
        ),
        "arm_id": str(relevant_bundles[0]["arm_id"]),
        "baseline_family": relevant_bundles[0]["baseline_family"],
        "model_mode": str(relevant_bundles[0]["model_mode"]),
        "seed": int(relevant_bundles[0]["seed"]),
        "requested_metric_ids": list(request["metric_ids"]),
        "recipe_ids_by_metric": copy.deepcopy(dict(request["recipe_ids_by_metric"])),
        "task_context": resolved_task_context,
        "retinotopic_context": resolved_retinotopic_context,
        "required_inputs": {
            "required_condition_pair_ids": list(
                decoder_definition["required_condition_pair_ids"]
            ),
            "required_source_artifact_classes": list(
                decoder_definition["required_source_artifact_classes"]
            ),
            "required_task_context_fields": list(
                decoder_definition["required_task_context_fields"]
            ),
            "required_retinotopic_context_fields": list(
                decoder_definition["required_retinotopic_context_fields"]
            ),
            "minimum_condition_structure": str(
                decoder_definition["minimum_condition_structure"]
            ),
        },
        "derived_quantities": {
            "aggregate_support": _rounded_float(aggregate_support),
            "aggregate_vector_xy": _rounded_float_list(aggregate_vector),
            "normalized_directional_support": _rounded_float(
                normalized_directional_support
            ),
            "global_motion_vector_xy_deg_per_s": _rounded_float_list(motion_vector_global),
            "local_optic_flow_vector_xy_deg_per_s": _rounded_float_list(optic_flow_local),
        },
        "metric_values": metric_values,
        "motion_vector": {
            "heading_deg": metric_values["motion_vector_heading_deg"],
            "speed_deg_per_s": metric_values["motion_vector_speed_deg_per_s"],
        },
        "optic_flow": {
            "heading_deg": metric_values["optic_flow_heading_deg"],
            "speed_deg_per_s": metric_values["optic_flow_speed_deg_per_s"],
        },
        "diagnostics": {
            "direction_reference": _HEADING_REFERENCE,
            "speed_scale_mode": str(policy["speed_scale_mode"]),
            "missing_pairing_keys": list(missing_pairing_keys),
            "evidence_rows": evidence_rows,
        },
    }


def _decoder_summary_metric_rows(
    *,
    request: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if str(summary["status"]) != "ok":
        return []
    rows: list[dict[str, Any]] = []
    for metric_id in request["metric_ids"]:
        metric_definition = get_readout_analysis_metric_definition(metric_id)
        value = summary["metric_values"].get(metric_id)
        if value is None:
            continue
        statistic = (
            _DIRECTION_STATISTIC
            if metric_id.endswith("_heading_deg")
            else _SPEED_STATISTIC
        )
        rows.append(
            {
                "recipe_id": str(request["recipe_ids_by_metric"][metric_id]),
                "metric_id": metric_id,
                "readout_id": str(summary["readout_id"]),
                "scope": str(summary["scope"]),
                "window_id": str(summary["window_id"]),
                "statistic": statistic,
                "value": value,
                "units": str(metric_definition["units"]),
                "analysis_group_id": str(summary["analysis_group_id"]),
                "condition_ids": list(summary["condition_ids"]),
                "condition_signature": str(summary["condition_signature"]),
                "condition_pair_id": str(summary["condition_pair_id"]),
                "pairing_key": str(summary["pairing_key"]),
                "bundle_ids": list(summary["bundle_ids"]),
                "arm_id": str(summary["arm_id"]),
                "baseline_family": summary["baseline_family"],
                "model_mode": str(summary["model_mode"]),
                "seed": int(summary["seed"]),
                "decoder_id": str(summary["decoder_id"]),
            }
        )
    return rows


def _unavailable_decoder_summary(
    *,
    request: Mapping[str, Any],
    decoder_definition: Mapping[str, Any],
    analysis_group_id: str,
    status: str,
    message: str,
    task_context: Mapping[str, Any] | None = None,
    retinotopic_context: Mapping[str, Any] | None = None,
    evidence_rows: Sequence[Mapping[str, Any]] | None = None,
    missing_pairing_keys: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "decoder_id": str(request["decoder_id"]),
        "task_family_id": MOTION_DECODER_ESTIMATES_TASK_FAMILY,
        "analysis_group_id": str(analysis_group_id),
        "status": str(status),
        "status_message": _normalize_nonempty_string(
            message,
            field_name="task_decoder.status_message",
        ),
        "readout_id": str(request["readout_id"]),
        "scope": None,
        "window_id": str(request["window_id"]),
        "condition_pair_id": request["condition_pair_id"],
        "condition_ids": [],
        "condition_signature": "unavailable",
        "pairing_key": _AGGREGATED_PAIRING_KEY,
        "bundle_ids": [],
        "arm_id": None,
        "baseline_family": None,
        "model_mode": None,
        "seed": None,
        "requested_metric_ids": list(request["metric_ids"]),
        "recipe_ids_by_metric": copy.deepcopy(dict(request["recipe_ids_by_metric"])),
        "task_context": copy.deepcopy(dict(task_context or {})),
        "retinotopic_context": copy.deepcopy(dict(retinotopic_context or {})),
        "required_inputs": {
            "required_condition_pair_ids": list(
                decoder_definition["required_condition_pair_ids"]
            ),
            "required_source_artifact_classes": list(
                decoder_definition["required_source_artifact_classes"]
            ),
            "required_task_context_fields": list(
                decoder_definition["required_task_context_fields"]
            ),
            "required_retinotopic_context_fields": list(
                decoder_definition["required_retinotopic_context_fields"]
            ),
            "minimum_condition_structure": str(
                decoder_definition["minimum_condition_structure"]
            ),
        },
        "derived_quantities": {},
        "metric_values": {},
        "motion_vector": None,
        "optic_flow": None,
        "diagnostics": {
            "direction_reference": _HEADING_REFERENCE,
            "missing_pairing_keys": list(missing_pairing_keys or []),
            "evidence_rows": [copy.deepcopy(dict(item)) for item in evidence_rows or []],
        },
    }


def _normalize_task_decoder_bundle_record(
    record: Mapping[str, Any],
    *,
    condition_ids_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    normalized = _normalize_bundle_record(record, condition_ids_by_id=condition_ids_by_id)
    metadata_payload = record.get("bundle_metadata", record)
    normalized["bundle_metadata"] = parse_simulator_result_bundle_metadata(metadata_payload)
    normalized["task_context_override"] = _normalize_task_context(record.get("task_context"))
    normalized["retinotopic_context_override"] = _normalize_retinotopic_context(
        record.get("retinotopic_context")
    )
    return normalized


def _resolve_group_task_context(
    *,
    relevant_bundles: Sequence[Mapping[str, Any]],
    pair_definition: Mapping[str, Any],
    condition_ids_by_id: Mapping[str, Mapping[str, Any]],
    global_task_context: Mapping[str, Any],
) -> dict[str, Any]:
    direction_context = _resolve_direction_context_from_plan(
        pair_definition=pair_definition,
        condition_ids_by_id=condition_ids_by_id,
    )
    merged = {
        "task_kind": _TASK_KIND_LOCAL_MOTION_PATCH,
        "direction_reference": _HEADING_REFERENCE,
        "direction_parameter_name": direction_context["parameter_name"],
        "preferred_direction_deg": direction_context["preferred_direction_deg"],
        "null_direction_deg": direction_context["null_direction_deg"],
        "condition_pair_id": str(pair_definition["pair_id"]),
    }
    if global_task_context:
        merged.update(copy.deepcopy(dict(global_task_context)))

    speed_values: list[float] = []
    speed_parameter_names: list[str] = []
    stimulus_families: list[str] = []
    stimulus_names: list[str] = []

    for bundle in relevant_bundles:
        if bundle["task_context_override"]:
            merged.update(copy.deepcopy(dict(bundle["task_context_override"])))
        stimulus_metadata = _load_bundle_stimulus_metadata(bundle["bundle_metadata"])
        if stimulus_metadata is None:
            continue
        parameter_snapshot = copy.deepcopy(dict(stimulus_metadata["parameter_snapshot"]))
        stimulus_families.append(str(stimulus_metadata["stimulus_family"]))
        stimulus_names.append(str(stimulus_metadata["stimulus_name"]))
        _validate_bundle_direction_context(
            bundle=bundle,
            parameter_snapshot=parameter_snapshot,
            direction_context=direction_context,
        )
        speed_parameter = _infer_speed_parameter(parameter_snapshot)
        if speed_parameter is not None:
            speed_parameter_names.append(speed_parameter["parameter_name"])
            speed_values.append(float(speed_parameter["value"]))

    if stimulus_families:
        _ensure_consistent_scalar(
            stimulus_families,
            field_name="stimulus_family",
        )
        merged.setdefault("stimulus_family", stimulus_families[0])
    if stimulus_names:
        unique_names = sorted(set(stimulus_names))
        if len(unique_names) == 1:
            merged.setdefault("stimulus_name", unique_names[0])
        else:
            merged.setdefault("stimulus_name_variants", unique_names)
    if speed_values:
        _ensure_consistent_numeric(
            speed_values,
            field_name="declared_speed_deg_per_s",
            tolerance=_SPEED_VALUE_TOLERANCE,
        )
        merged.setdefault("declared_speed_deg_per_s", speed_values[0])
    if speed_parameter_names:
        _ensure_consistent_scalar(
            speed_parameter_names,
            field_name="speed_parameter_name",
        )
        merged.setdefault("speed_parameter_name", speed_parameter_names[0])
    return _normalize_task_context(merged)


def _resolve_group_retinotopic_context(
    *,
    relevant_bundles: Sequence[Mapping[str, Any]],
    global_retinotopic_context: Mapping[str, Any],
) -> dict[str, Any]:
    merged = {
        "coordinate_frame": "visual_field_degrees_centered",
        "center_azimuth_deg": None,
        "center_elevation_deg": None,
        "azimuth_axis_unit_vector": [1.0, 0.0],
        "elevation_axis_unit_vector": [0.0, 1.0],
    }
    if global_retinotopic_context:
        merged.update(copy.deepcopy(dict(global_retinotopic_context)))

    center_azimuth_values: list[float] = []
    center_elevation_values: list[float] = []
    coordinate_frames: list[str] = []
    for bundle in relevant_bundles:
        if bundle["retinotopic_context_override"]:
            merged.update(copy.deepcopy(dict(bundle["retinotopic_context_override"])))
        stimulus_metadata = _load_bundle_stimulus_metadata(bundle["bundle_metadata"])
        if stimulus_metadata is not None:
            parameter_snapshot = dict(stimulus_metadata["parameter_snapshot"])
            if "center_azimuth_deg" in parameter_snapshot:
                center_azimuth_values.append(float(parameter_snapshot["center_azimuth_deg"]))
            if "center_elevation_deg" in parameter_snapshot:
                center_elevation_values.append(float(parameter_snapshot["center_elevation_deg"]))
            coordinate_frames.append("visual_field_degrees_centered")
        retinal_metadata = _load_bundle_retinal_metadata(bundle["bundle_metadata"])
        if retinal_metadata is not None:
            coordinate_frames.append("visual_field_degrees_centered")

    if center_azimuth_values:
        _ensure_consistent_numeric(
            center_azimuth_values,
            field_name="center_azimuth_deg",
            tolerance=_DIRECTION_VALUE_TOLERANCE,
        )
        if merged.get("center_azimuth_deg") is None:
            merged["center_azimuth_deg"] = center_azimuth_values[0]
    if center_elevation_values:
        _ensure_consistent_numeric(
            center_elevation_values,
            field_name="center_elevation_deg",
            tolerance=_DIRECTION_VALUE_TOLERANCE,
        )
        if merged.get("center_elevation_deg") is None:
            merged["center_elevation_deg"] = center_elevation_values[0]
    if coordinate_frames:
        _ensure_consistent_scalar(
            coordinate_frames,
            field_name="coordinate_frame",
        )
        merged.setdefault("coordinate_frame", coordinate_frames[0])
    return _normalize_retinotopic_context(merged)


def _require_decoder_context(
    *,
    decoder_definition: Mapping[str, Any],
    task_context: Mapping[str, Any],
    retinotopic_context: Mapping[str, Any],
    metric_ids: Sequence[str],
) -> None:
    missing_task_fields = [
        field
        for field in decoder_definition["required_task_context_fields"]
        if task_context.get(field) is None
    ]
    if missing_task_fields:
        raise ValueError(
            f"Task decoder {decoder_definition['decoder_id']!r} requires task context fields "
            f"{missing_task_fields!r}, but the manifest/result bundle did not provide them."
        )
    missing_retinotopic_fields = [
        field
        for field in decoder_definition["required_retinotopic_context_fields"]
        if retinotopic_context.get(field) is None
    ]
    if missing_retinotopic_fields:
        raise ValueError(
            f"Task decoder {decoder_definition['decoder_id']!r} requires retinotopic context "
            f"fields {missing_retinotopic_fields!r}, but the manifest/result bundle did not "
            "provide enough local geometry metadata."
        )
    if any(metric_id.endswith("_speed_deg_per_s") for metric_id in metric_ids) and task_context.get(
        "declared_speed_deg_per_s"
    ) is None:
        raise ValueError(
            f"Task decoder {decoder_definition['decoder_id']!r} requires a declared local speed "
            "in deg_per_s to realize speed metrics, but task_context.declared_speed_deg_per_s is missing."
        )


def _resolve_direction_context_from_plan(
    *,
    pair_definition: Mapping[str, Any],
    condition_ids_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    left_condition = dict(condition_ids_by_id[str(pair_definition["left_condition_id"])])
    right_condition = dict(condition_ids_by_id[str(pair_definition["right_condition_id"])])
    left_parameter_name = _normalize_identifier(
        left_condition.get("parameter_name"),
        field_name="condition_catalog.parameter_name",
    )
    right_parameter_name = _normalize_identifier(
        right_condition.get("parameter_name"),
        field_name="condition_catalog.parameter_name",
    )
    if left_parameter_name != right_parameter_name:
        raise ValueError(
            "Task decoders require a shared preferred/null direction parameter name, but the "
            f"analysis plan pairs {left_parameter_name!r} with {right_parameter_name!r}."
        )
    if left_parameter_name not in _SUPPORTED_DIRECTION_PARAMETER_NAMES:
        raise ValueError(
            "Task decoders currently support only numeric direction conditions derived from "
            f"{list(_SUPPORTED_DIRECTION_PARAMETER_NAMES)!r}, got {left_parameter_name!r}."
        )
    left_value = _normalize_float(
        left_condition.get("value"),
        field_name=f"condition_catalog.{left_condition['condition_id']}.value",
    )
    right_value = _normalize_float(
        right_condition.get("value"),
        field_name=f"condition_catalog.{right_condition['condition_id']}.value",
    )
    return {
        "parameter_name": left_parameter_name,
        "preferred_direction_deg": left_value,
        "null_direction_deg": right_value,
    }


def _validate_bundle_direction_context(
    *,
    bundle: Mapping[str, Any],
    parameter_snapshot: Mapping[str, Any],
    direction_context: Mapping[str, Any],
) -> None:
    bundle_condition_ids = set(bundle["condition_ids"])
    expected_value: float | None = None
    if "preferred_direction" in bundle_condition_ids:
        expected_value = float(direction_context["preferred_direction_deg"])
    elif "null_direction" in bundle_condition_ids:
        expected_value = float(direction_context["null_direction_deg"])
    if expected_value is None:
        return
    parameter_name = str(direction_context["parameter_name"])
    if parameter_name not in parameter_snapshot:
        return
    observed_value = float(parameter_snapshot[parameter_name])
    if not math.isclose(
        observed_value,
        expected_value,
        rel_tol=0.0,
        abs_tol=_DIRECTION_VALUE_TOLERANCE,
    ):
        raise ValueError(
            f"Bundle {bundle['bundle_id']!r} declares condition_ids {sorted(bundle_condition_ids)!r} "
            f"but stimulus parameter {parameter_name!r}={observed_value!r} does not match the "
            f"analysis-plan direction label value {expected_value!r}."
        )


def _load_bundle_stimulus_metadata(
    bundle_metadata: Mapping[str, Any],
) -> dict[str, Any] | None:
    selected_asset = _find_selected_asset(bundle_metadata, artifact_types=("stimulus_bundle",))
    if selected_asset is None:
        return None
    return load_stimulus_bundle_metadata(Path(selected_asset["path"]))


def _load_bundle_retinal_metadata(
    bundle_metadata: Mapping[str, Any],
) -> dict[str, Any] | None:
    selected_asset = _find_selected_asset(
        bundle_metadata,
        artifact_types=_SUPPORTED_RETINAL_ARTIFACT_TYPES,
    )
    if selected_asset is None:
        return None
    return load_retinal_bundle_metadata(Path(selected_asset["path"]))


def _find_selected_asset(
    bundle_metadata: Mapping[str, Any],
    *,
    artifact_types: Sequence[str],
) -> dict[str, Any] | None:
    for item in bundle_metadata["selected_assets"]:
        if str(item["artifact_type"]) in set(artifact_types):
            return copy.deepcopy(dict(item))
    return None


def _infer_speed_parameter(
    parameter_snapshot: Mapping[str, Any],
) -> dict[str, Any] | None:
    for parameter_name in _SUPPORTED_SPEED_PARAMETER_NAMES:
        if parameter_name in parameter_snapshot:
            return {
                "parameter_name": parameter_name,
                "value": _normalize_positive_float(
                    parameter_snapshot[parameter_name],
                    field_name=f"parameter_snapshot.{parameter_name}",
                ),
            }
    return None


def _normalize_decoder_policy(
    decoder_policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw_policy = dict(DEFAULT_TASK_DECODER_POLICY)
    if decoder_policy is not None:
        if not isinstance(decoder_policy, Mapping):
            raise ValueError("decoder_policy must be a mapping when provided.")
        raw_policy.update(decoder_policy)
    normalized_shared_policy = _normalize_kernel_policy(raw_policy)
    speed_scale_mode = _normalize_nonempty_string(
        raw_policy.get("speed_scale_mode"),
        field_name="decoder_policy.speed_scale_mode",
    )
    if speed_scale_mode != "declared_speed_times_normalized_directional_evidence":
        raise ValueError(
            f"Unsupported decoder_policy.speed_scale_mode {speed_scale_mode!r}."
        )
    return {
        **normalized_shared_policy,
        "minimum_vector_norm": _normalize_positive_float(
            raw_policy.get("minimum_vector_norm"),
            field_name="decoder_policy.minimum_vector_norm",
        ),
        "speed_scale_mode": speed_scale_mode,
    }


def _normalize_task_context(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError("task_context must be a mapping when provided.")
    normalized = copy.deepcopy(dict(payload))
    if "task_kind" in normalized and normalized["task_kind"] is not None:
        normalized["task_kind"] = _normalize_identifier(
            normalized["task_kind"],
            field_name="task_context.task_kind",
        )
    if "direction_reference" in normalized and normalized["direction_reference"] is not None:
        normalized["direction_reference"] = _normalize_nonempty_string(
            normalized["direction_reference"],
            field_name="task_context.direction_reference",
        )
    if (
        "direction_parameter_name" in normalized
        and normalized["direction_parameter_name"] is not None
    ):
        normalized["direction_parameter_name"] = _normalize_identifier(
            normalized["direction_parameter_name"],
            field_name="task_context.direction_parameter_name",
        )
    if (
        "preferred_direction_deg" in normalized
        and normalized["preferred_direction_deg"] is not None
    ):
        normalized["preferred_direction_deg"] = _normalize_float(
            normalized["preferred_direction_deg"],
            field_name="task_context.preferred_direction_deg",
        )
    if "null_direction_deg" in normalized and normalized["null_direction_deg"] is not None:
        normalized["null_direction_deg"] = _normalize_float(
            normalized["null_direction_deg"],
            field_name="task_context.null_direction_deg",
        )
    if (
        "declared_speed_deg_per_s" in normalized
        and normalized["declared_speed_deg_per_s"] is not None
    ):
        normalized["declared_speed_deg_per_s"] = _normalize_positive_float(
            normalized["declared_speed_deg_per_s"],
            field_name="task_context.declared_speed_deg_per_s",
        )
    if "speed_parameter_name" in normalized and normalized["speed_parameter_name"] is not None:
        normalized["speed_parameter_name"] = _normalize_identifier(
            normalized["speed_parameter_name"],
            field_name="task_context.speed_parameter_name",
        )
    if "stimulus_family" in normalized and normalized["stimulus_family"] is not None:
        normalized["stimulus_family"] = _normalize_identifier(
            normalized["stimulus_family"],
            field_name="task_context.stimulus_family",
        )
    if "stimulus_name" in normalized and normalized["stimulus_name"] is not None:
        normalized["stimulus_name"] = _normalize_identifier(
            normalized["stimulus_name"],
            field_name="task_context.stimulus_name",
        )
    if "condition_pair_id" in normalized and normalized["condition_pair_id"] is not None:
        normalized["condition_pair_id"] = _normalize_identifier(
            normalized["condition_pair_id"],
            field_name="task_context.condition_pair_id",
        )
    return normalized


def _normalize_retinotopic_context(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError("retinotopic_context must be a mapping when provided.")
    normalized = copy.deepcopy(dict(payload))
    if "coordinate_frame" in normalized and normalized["coordinate_frame"] is not None:
        normalized["coordinate_frame"] = _normalize_nonempty_string(
            normalized["coordinate_frame"],
            field_name="retinotopic_context.coordinate_frame",
        )
    if "center_azimuth_deg" in normalized and normalized["center_azimuth_deg"] is not None:
        normalized["center_azimuth_deg"] = _normalize_float(
            normalized["center_azimuth_deg"],
            field_name="retinotopic_context.center_azimuth_deg",
        )
    if (
        "center_elevation_deg" in normalized
        and normalized["center_elevation_deg"] is not None
    ):
        normalized["center_elevation_deg"] = _normalize_float(
            normalized["center_elevation_deg"],
            field_name="retinotopic_context.center_elevation_deg",
        )
    if (
        "azimuth_axis_unit_vector" in normalized
        and normalized["azimuth_axis_unit_vector"] is not None
    ):
        normalized["azimuth_axis_unit_vector"] = _normalize_unit_vector(
            normalized["azimuth_axis_unit_vector"],
            field_name="retinotopic_context.azimuth_axis_unit_vector",
        )
    if (
        "elevation_axis_unit_vector" in normalized
        and normalized["elevation_axis_unit_vector"] is not None
    ):
        normalized["elevation_axis_unit_vector"] = _normalize_unit_vector(
            normalized["elevation_axis_unit_vector"],
            field_name="retinotopic_context.elevation_axis_unit_vector",
        )
    return normalized


def _project_global_vector_into_retinotopic_basis(
    *,
    global_vector: np.ndarray,
    retinotopic_context: Mapping[str, Any],
) -> np.ndarray:
    basis_matrix = np.column_stack(
        [
            np.asarray(retinotopic_context["azimuth_axis_unit_vector"], dtype=np.float64),
            np.asarray(retinotopic_context["elevation_axis_unit_vector"], dtype=np.float64),
        ]
    )
    determinant = float(np.linalg.det(basis_matrix))
    if abs(determinant) <= _LOCAL_AXIS_TOLERANCE:
        raise ValueError(
            "retinotopic_context axis vectors must span a valid local basis; the provided "
            "azimuth/elevation unit vectors are nearly singular."
        )
    return np.linalg.solve(basis_matrix, np.asarray(global_vector, dtype=np.float64))


def _direction_unit_vector(direction_deg: float) -> np.ndarray:
    direction_rad = math.radians(float(direction_deg))
    return np.asarray(
        [math.cos(direction_rad), math.sin(direction_rad)],
        dtype=np.float64,
    )


def _heading_deg_from_vector(vector: np.ndarray) -> float:
    heading_deg = math.degrees(math.atan2(float(vector[1]), float(vector[0]))) % 360.0
    return _rounded_float(heading_deg)


def _normalize_unit_vector(payload: Any, *, field_name: str) -> list[float]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a length-2 list.")
    values = [
        _normalize_float(value, field_name=f"{field_name}[{index}]")
        for index, value in enumerate(payload)
    ]
    if len(values) != 2:
        raise ValueError(f"{field_name} must contain exactly two coordinates.")
    vector = np.asarray(values, dtype=np.float64)
    norm = float(np.linalg.norm(vector))
    if norm <= _LOCAL_AXIS_TOLERANCE:
        raise ValueError(f"{field_name} must have nonzero magnitude.")
    return _rounded_float_list(vector / norm)


def _normalize_identifier_list(
    payload: Any,
    *,
    field_name: str,
    allow_empty: bool,
) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a list.")
    normalized = sorted(
        {
            _normalize_identifier(value, field_name=f"{field_name}[{index}]")
            for index, value in enumerate(payload)
        }
    )
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} must contain at least one identifier.")
    return normalized


def _normalize_nonempty_string_list(payload: Any, *, field_name: str) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a list.")
    normalized = sorted(
        {
            _normalize_nonempty_string(value, field_name=f"{field_name}[{index}]")
            for index, value in enumerate(payload)
        }
    )
    if not normalized:
        raise ValueError(f"{field_name} must contain at least one string.")
    return normalized


def _rounded_float_list(values: Sequence[float] | np.ndarray) -> list[float]:
    return [_rounded_float(float(value)) for value in np.asarray(values, dtype=np.float64).tolist()]


def _ensure_consistent_numeric(
    values: Sequence[float],
    *,
    field_name: str,
    tolerance: float,
) -> None:
    anchor = float(values[0])
    for value in values[1:]:
        if not math.isclose(float(value), anchor, rel_tol=0.0, abs_tol=float(tolerance)):
            raise ValueError(
                f"Task-decoder context field {field_name!r} is inconsistent across bundles: "
                f"{[float(item) for item in values]!r}."
            )


def _ensure_consistent_scalar(values: Sequence[str], *, field_name: str) -> None:
    anchor = values[0]
    for value in values[1:]:
        if str(value) != str(anchor):
            raise ValueError(
                f"Task-decoder context field {field_name!r} is inconsistent across bundles: "
                f"{list(values)!r}."
            )


def _default_task_decoder_catalog() -> list[dict[str, Any]]:
    return [
        build_task_decoder_definition(
            decoder_id=MOTION_VECTOR_DECODER_ID,
            display_name="Motion Vector Decoder",
            description=(
                "Deterministic local motion-vector estimate derived from matched preferred/null "
                "shared-readout responses plus declared task context."
            ),
            supported_metric_ids=[
                "motion_vector_heading_deg",
                "motion_vector_speed_deg_per_s",
            ],
            required_condition_pair_ids=["preferred_vs_null"],
            required_source_artifact_classes=[
                RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS,
                SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
                SHARED_READOUT_TRACES_ARTIFACT_CLASS,
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
                TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
            ],
            required_task_context_fields=[
                "condition_pair_id",
                "declared_speed_deg_per_s",
                "direction_parameter_name",
                "direction_reference",
                "null_direction_deg",
                "preferred_direction_deg",
            ],
            required_retinotopic_context_fields=[
                "azimuth_axis_unit_vector",
                "center_azimuth_deg",
                "center_elevation_deg",
                "coordinate_frame",
                "elevation_axis_unit_vector",
            ],
            derived_shared_readout_quantities=[
                "aggregate_directional_vector",
                "normalized_directional_support",
                "preferred_minus_null_peak_evidence",
            ],
            minimum_condition_structure=(
                "At least one matched preferred/null bundle pair must exist for the active shared "
                "readout in the task-decoder window. Additional non-directional condition keys "
                "such as ON/OFF polarity are pooled as independent evidence rows."
            ),
            output_conventions={
                "heading_units": "deg",
                "heading_reference": _HEADING_REFERENCE,
                "speed_units": "deg_per_s",
                "speed_semantics": "declared_local_speed_scaled_by_normalized_directional_evidence",
            },
        ),
        build_task_decoder_definition(
            decoder_id=OPTIC_FLOW_DECODER_ID,
            display_name="Optic Flow Decoder",
            description=(
                "Deterministic local optic-flow estimate derived from the shared motion vector "
                "plus declared retinotopic geometry for the active patch."
            ),
            supported_metric_ids=[
                "optic_flow_heading_deg",
                "optic_flow_speed_deg_per_s",
            ],
            required_condition_pair_ids=["preferred_vs_null"],
            required_source_artifact_classes=[
                RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS,
                SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
                SHARED_READOUT_TRACES_ARTIFACT_CLASS,
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
                TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
            ],
            required_task_context_fields=[
                "condition_pair_id",
                "declared_speed_deg_per_s",
                "direction_parameter_name",
                "direction_reference",
                "null_direction_deg",
                "preferred_direction_deg",
            ],
            required_retinotopic_context_fields=[
                "azimuth_axis_unit_vector",
                "center_azimuth_deg",
                "center_elevation_deg",
                "coordinate_frame",
                "elevation_axis_unit_vector",
            ],
            derived_shared_readout_quantities=[
                "aggregate_directional_vector",
                "normalized_directional_support",
                "retinotopic_basis_projection",
            ],
            minimum_condition_structure=(
                "At least one matched preferred/null bundle pair must exist and the task input "
                "must declare a local retinotopic patch center plus azimuth/elevation basis vectors."
            ),
            output_conventions={
                "heading_units": "deg",
                "heading_reference": _HEADING_REFERENCE,
                "speed_units": "deg_per_s",
                "optic_flow_approximation": "small_field_tangent_plane_at_declared_patch_center",
            },
        ),
    ]
