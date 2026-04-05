from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .readout_analysis_contract import (
    ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
    ANALYSIS_NULL_TEST_ROWS_ARTIFACT_CLASS,
    EXPERIMENT_BUNDLE_SET_ARTIFACT_CLASS,
    LATENCY_SHIFT_COMPARISON_OUTPUT_ID,
    MILESTONE_1_DECISION_PANEL_OUTPUT_ID,
    NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID,
    PER_SHARED_READOUT_CONDITION_PAIR_SCOPE,
    PER_SHARED_READOUT_CONDITION_WINDOW_SCOPE,
    PER_TASK_DECODER_WINDOW_SCOPE,
    PER_WAVE_ROOT_SET_WINDOW_SCOPE,
    PER_WAVE_ROOT_WINDOW_SCOPE,
    RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS,
    SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
    SHARED_READOUT_TRACES_ARTIFACT_CLASS,
    SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
    STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
    SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
    SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
    SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
    TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
    WAVE_DIAGNOSTIC_ROWS_ARTIFACT_CLASS,
    build_readout_analysis_contract_metadata,
    get_experiment_comparison_output_definition,
    get_readout_analysis_metric_definition,
    get_readout_analysis_null_test_hook,
)
from .simulation_planning import (
    ALLOWED_ANALYSIS_CONFIG_KEYS,
    ALLOWED_ANALYSIS_OUTPUT_TARGET_KEYS,
    ALLOWED_ANALYSIS_WINDOW_KEYS,
    ANALYSIS_WINDOW_ORDER,
    DEFAULT_SEED_SWEEP_ORDERING,
    FULL_TIMEBASE_WINDOW_ID,
    MANIFEST_SEED_SWEEP_ROLLUP_RULE_ID,
    MANIFEST_TASK_METRIC_RECIPES,
    MIXED_FIDELITY_PLAN_VERSION,
    NULL_DIRECTION_CONDITION_ID,
    OFF_POLARITY_CONDITION_ID,
    ON_POLARITY_CONDITION_ID,
    ON_VS_OFF_PAIR_ID,
    PER_RUN_SINGLE_SEED_RULE_ID,
    PREFERRED_DIRECTION_CONDITION_ID,
    PREFERRED_VS_NULL_PAIR_ID,
    READOUT_ANALYSIS_CONFIG_VERSION,
    READOUT_ANALYSIS_PLAN_VERSION,
    SHARED_RESPONSE_WINDOW_ID,
    SUCCESS_CRITERION_NULL_TEST_IDS,
    TASK_DECODER_WINDOW_ID,
    WAVE_DIAGNOSTIC_WINDOW_ID,
    _normalize_float,
    _normalize_identifier,
    _normalize_identifier_list,
    _normalize_nonempty_string,
    _require_mapping,
    _require_sequence,
    _resolve_project_path,
)
from .simulator_result_contract import (
    P0_BASELINE_FAMILY,
    P1_BASELINE_FAMILY,
    SURFACE_WAVE_MODEL_MODE,
    normalize_simulator_timebase,
)


MANIFEST_TO_ANALYSIS_OUTPUT_ID = {
    "latency_shift_comparison": LATENCY_SHIFT_COMPARISON_OUTPUT_ID,
    "milestone_decision_panel": MILESTONE_1_DECISION_PANEL_OUTPUT_ID,
    "null_direction_suppression_comparison": NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID,
}


def build_readout_analysis_plan(
    *,
    manifest_payload: Mapping[str, Any],
    manifest_summary: Mapping[str, Any],
    cfg: Mapping[str, Any],
    project_root: Path,
    manifest_reference: Mapping[str, Any],
    runtime_config: Mapping[str, Any],
    arm_plans: Sequence[Mapping[str, Any]],
    output_targets: Mapping[str, Any],
    seed_sweep: Sequence[int],
) -> dict[str, Any]:
    analysis_contract = build_readout_analysis_contract_metadata()
    normalized_analysis_config = _normalize_readout_analysis_config(
        cfg.get("analysis"),
        project_root=project_root,
        timebase=runtime_config["timebase"],
        resolved_stimulus=manifest_summary["resolved_stimulus"],
    )
    active_shared_readouts = _resolve_active_shared_readouts(
        runtime_config["shared_readout_catalog"],
        requested_readout_ids=normalized_analysis_config["active_readout_ids"],
    )
    condition_catalog, condition_pair_catalog = _resolve_analysis_condition_catalog(
        manifest_summary["resolved_stimulus"]
    )
    analysis_window_catalog = _build_analysis_window_catalog(
        timebase=runtime_config["timebase"],
        resolved_stimulus=manifest_summary["resolved_stimulus"],
        overrides=normalized_analysis_config["analysis_windows"],
    )
    arm_pair_catalog = _build_analysis_arm_pair_catalog(arm_plans)
    comparison_group_catalog = _build_analysis_comparison_group_catalog(arm_pair_catalog)
    seed_aggregation_rules = _build_seed_aggregation_rules(seed_sweep)
    experiment_output_targets = _build_experiment_output_targets(
        manifest_payload=manifest_payload,
        output_targets=output_targets,
        requested_output_ids=normalized_analysis_config["output_ids"],
        configured_output_targets=normalized_analysis_config["experiment_output_targets"],
        comparison_group_catalog=comparison_group_catalog,
        arm_pair_catalog=arm_pair_catalog,
        analysis_contract=analysis_contract,
    )
    selection = _resolve_active_analysis_selection(
        manifest_payload=manifest_payload,
        analysis_contract=analysis_contract,
        requested_metric_ids=normalized_analysis_config["active_metric_ids"],
        requested_null_test_ids=normalized_analysis_config["null_test_ids"],
        experiment_output_targets=experiment_output_targets,
    )
    base_artifact_classes = _resolve_base_analysis_artifact_classes(
        cfg=cfg,
        arm_plans=arm_plans,
    )
    _validate_active_analysis_metrics(
        active_metric_ids=selection["active_metric_ids"],
        analysis_contract=analysis_contract,
        active_shared_readouts=active_shared_readouts,
        condition_pair_catalog=condition_pair_catalog,
        base_artifact_classes=base_artifact_classes,
    )
    metric_recipe_catalog = _build_metric_recipe_catalog(
        active_metric_ids=selection["active_metric_ids"],
        analysis_contract=analysis_contract,
        active_shared_readouts=active_shared_readouts,
        analysis_window_catalog=analysis_window_catalog,
        condition_catalog=condition_catalog,
        condition_pair_catalog=condition_pair_catalog,
        arm_plans=arm_plans,
    )
    available_artifact_classes = _resolve_available_analysis_artifact_classes(
        base_artifact_classes=base_artifact_classes,
        active_metric_ids=selection["active_metric_ids"],
        active_null_test_ids=selection["active_null_test_ids"],
        analysis_contract=analysis_contract,
    )
    null_test_declarations = _build_null_test_declarations(
        active_null_test_ids=selection["active_null_test_ids"],
        analysis_contract=analysis_contract,
        available_artifact_classes=available_artifact_classes,
        condition_pair_catalog=condition_pair_catalog,
        comparison_group_catalog=comparison_group_catalog,
        metric_recipe_catalog=metric_recipe_catalog,
        seed_aggregation_rules=seed_aggregation_rules,
    )
    _validate_experiment_output_targets(
        experiment_output_targets=experiment_output_targets,
        active_metric_ids=selection["active_metric_ids"],
        available_artifact_classes=available_artifact_classes,
        comparison_group_catalog=comparison_group_catalog,
        arm_pair_catalog=arm_pair_catalog,
        active_shared_readouts=active_shared_readouts,
        analysis_contract=analysis_contract,
    )
    manifest_metric_requests = _build_manifest_metric_request_catalog(
        manifest_payload=manifest_payload,
        analysis_contract=analysis_contract,
        metric_recipe_catalog=metric_recipe_catalog,
        comparison_group_catalog=comparison_group_catalog,
        arm_pair_catalog=arm_pair_catalog,
        seed_aggregation_rules=seed_aggregation_rules,
    )
    active_metric_definitions = [
        get_readout_analysis_metric_definition(metric_id, record=analysis_contract)
        for metric_id in selection["active_metric_ids"]
    ]
    active_output_definitions = [
        get_experiment_comparison_output_definition(output_id, record=analysis_contract)
        for output_id in selection["active_output_ids"]
    ]
    return {
        "plan_version": READOUT_ANALYSIS_PLAN_VERSION,
        "manifest_reference": copy.deepcopy(dict(manifest_reference)),
        "contract_reference": {
            "contract_version": analysis_contract["contract_version"],
            "design_note": analysis_contract["design_note"],
            "design_note_version": analysis_contract["design_note_version"],
            "locked_readout_stop_point": analysis_contract["locked_readout_stop_point"],
        },
        "analysis_config": copy.deepcopy(normalized_analysis_config),
        "active_shared_readout_ordering": "readout_id_ascending",
        "active_shared_readouts": active_shared_readouts,
        "condition_catalog": condition_catalog,
        "condition_pair_catalog": condition_pair_catalog,
        "analysis_window_catalog": analysis_window_catalog,
        "arm_pair_catalog": arm_pair_catalog,
        "comparison_group_catalog": comparison_group_catalog,
        "seed_aggregation_rules": seed_aggregation_rules,
        "active_metric_ids": list(selection["active_metric_ids"]),
        "active_metric_definitions": active_metric_definitions,
        "active_output_ids": list(selection["active_output_ids"]),
        "active_output_definitions": active_output_definitions,
        "active_null_test_ids": list(selection["active_null_test_ids"]),
        "manifest_metric_requests": manifest_metric_requests,
        "metric_recipe_catalog": metric_recipe_catalog,
        "null_test_declarations": null_test_declarations,
        "analysis_artifact_classes": sorted(available_artifact_classes),
        "per_run_output_targets": _build_per_run_analysis_output_targets(arm_plans),
        "experiment_output_targets": experiment_output_targets,
    }


def _normalize_readout_analysis_config(
    payload: Any,
    *,
    project_root: Path,
    timebase: Mapping[str, Any],
    resolved_stimulus: Mapping[str, Any],
) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError("analysis must be a mapping when provided.")
    unknown_keys = sorted(set(raw_payload) - ALLOWED_ANALYSIS_CONFIG_KEYS)
    if unknown_keys:
        raise ValueError(
            "analysis contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    version = _normalize_nonempty_string(
        raw_payload.get("version", READOUT_ANALYSIS_CONFIG_VERSION),
        field_name="analysis.version",
    )
    if version != READOUT_ANALYSIS_CONFIG_VERSION:
        raise ValueError(
            "analysis.version must be "
            f"{READOUT_ANALYSIS_CONFIG_VERSION!r}."
        )
    analysis_windows = _normalize_analysis_window_overrides(
        raw_payload.get("analysis_windows"),
        timebase=timebase,
        resolved_stimulus=resolved_stimulus,
    )
    experiment_output_targets = _normalize_analysis_output_targets(
        raw_payload.get("experiment_output_targets"),
        project_root=project_root,
    )
    requested_output_ids = set(
        _normalize_identifier_list(
            raw_payload.get("output_ids"),
            field_name="analysis.output_ids",
        )
    )
    requested_output_ids.update(item["output_id"] for item in experiment_output_targets)
    return {
        "version": version,
        "active_readout_ids": _normalize_identifier_list(
            raw_payload.get("active_readout_ids"),
            field_name="analysis.active_readout_ids",
        ),
        "active_metric_ids": _normalize_identifier_list(
            raw_payload.get("active_metric_ids"),
            field_name="analysis.active_metric_ids",
        ),
        "analysis_windows": analysis_windows,
        "null_test_ids": _normalize_identifier_list(
            raw_payload.get("null_test_ids"),
            field_name="analysis.null_test_ids",
        ),
        "output_ids": sorted(requested_output_ids),
        "experiment_output_targets": experiment_output_targets,
    }


def _normalize_analysis_window_overrides(
    payload: Any,
    *,
    timebase: Mapping[str, Any],
    resolved_stimulus: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError("analysis.analysis_windows must be a mapping when provided.")
    default_windows = {
        item["window_id"]: item
        for item in _build_analysis_window_catalog(
            timebase=timebase,
            resolved_stimulus=resolved_stimulus,
            overrides={},
        )
    }
    overrides: dict[str, dict[str, Any]] = {}
    for window_id, record in dict(payload).items():
        normalized_window_id = _normalize_identifier(
            window_id,
            field_name="analysis.analysis_windows.window_id",
        )
        if normalized_window_id not in default_windows:
            raise ValueError(
                "analysis.analysis_windows may only override known window ids, got "
                f"{normalized_window_id!r}."
            )
        if not isinstance(record, Mapping):
            raise ValueError(
                f"analysis.analysis_windows.{normalized_window_id} must be a mapping."
            )
        raw_record = dict(record)
        unknown_keys = sorted(set(raw_record) - ALLOWED_ANALYSIS_WINDOW_KEYS)
        if unknown_keys:
            raise ValueError(
                f"analysis.analysis_windows.{normalized_window_id} contains unsupported keys: "
                f"{unknown_keys!r}."
            )
        merged = copy.deepcopy(default_windows[normalized_window_id])
        if "start_ms" in raw_record:
            merged["start_ms"] = _normalize_float(
                raw_record["start_ms"],
                field_name=f"analysis.analysis_windows.{normalized_window_id}.start_ms",
            )
        if "end_ms" in raw_record:
            merged["end_ms"] = _normalize_float(
                raw_record["end_ms"],
                field_name=f"analysis.analysis_windows.{normalized_window_id}.end_ms",
            )
        if "description" in raw_record:
            merged["description"] = _normalize_nonempty_string(
                raw_record["description"],
                field_name=f"analysis.analysis_windows.{normalized_window_id}.description",
            )
        overrides[normalized_window_id] = merged
    return overrides


def _normalize_analysis_output_targets(
    payload: Any,
    *,
    project_root: Path,
) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("analysis.experiment_output_targets must be a list when provided.")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError(
                f"analysis.experiment_output_targets[{index}] must be a mapping."
            )
        raw_item = dict(item)
        unknown_keys = sorted(set(raw_item) - ALLOWED_ANALYSIS_OUTPUT_TARGET_KEYS)
        if unknown_keys:
            raise ValueError(
                "analysis.experiment_output_targets contains unsupported keys: "
                f"{unknown_keys!r}."
            )
        normalized.append(
            {
                "output_id": _normalize_identifier(
                    raw_item.get("output_id"),
                    field_name=f"analysis.experiment_output_targets[{index}].output_id",
                ),
                "path": str(
                    _resolve_project_path(
                        _normalize_nonempty_string(
                            raw_item.get("path"),
                            field_name=f"analysis.experiment_output_targets[{index}].path",
                        ),
                        project_root,
                    )
                ),
            }
        )
    normalized.sort(key=lambda item: (item["output_id"], item["path"]))
    seen_output_ids: set[str] = set()
    for item in normalized:
        if item["output_id"] in seen_output_ids:
            raise ValueError(
                "analysis.experiment_output_targets contains duplicate output_id "
                f"{item['output_id']!r}."
            )
        seen_output_ids.add(item["output_id"])
    return normalized


def _build_analysis_window_catalog(
    *,
    timebase: Mapping[str, Any],
    resolved_stimulus: Mapping[str, Any],
    overrides: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    normalized_timebase = normalize_simulator_timebase(timebase)
    time_origin_ms = float(normalized_timebase["time_origin_ms"])
    end_ms = time_origin_ms + float(normalized_timebase["duration_ms"])
    parameter_snapshot = _require_mapping(
        resolved_stimulus.get("parameter_snapshot"),
        field_name="resolved_stimulus.parameter_snapshot",
    )
    stimulus_onset_ms = float(parameter_snapshot.get("onset_ms", time_origin_ms))
    stimulus_offset_ms = float(parameter_snapshot.get("offset_ms", end_ms))
    clamped_onset_ms = max(time_origin_ms, min(end_ms, stimulus_onset_ms))
    clamped_offset_ms = max(clamped_onset_ms, min(end_ms, stimulus_offset_ms))
    defaults = {
        FULL_TIMEBASE_WINDOW_ID: {
            "window_id": FULL_TIMEBASE_WINDOW_ID,
            "start_ms": time_origin_ms,
            "end_ms": end_ms,
            "description": "Entire declared simulator timebase window.",
            "source": "simulation.timebase",
        },
        SHARED_RESPONSE_WINDOW_ID: {
            "window_id": SHARED_RESPONSE_WINDOW_ID,
            "start_ms": clamped_onset_ms,
            "end_ms": clamped_offset_ms,
            "description": "Shared response window derived from the declared stimulus onset/offset.",
            "source": "resolved_stimulus.parameter_snapshot",
        },
        TASK_DECODER_WINDOW_ID: {
            "window_id": TASK_DECODER_WINDOW_ID,
            "start_ms": clamped_onset_ms,
            "end_ms": clamped_offset_ms,
            "description": "Task-decoder window derived from the declared stimulus onset/offset.",
            "source": "resolved_stimulus.parameter_snapshot",
        },
        WAVE_DIAGNOSTIC_WINDOW_ID: {
            "window_id": WAVE_DIAGNOSTIC_WINDOW_ID,
            "start_ms": clamped_onset_ms,
            "end_ms": clamped_offset_ms,
            "description": "Wave-diagnostic window derived from the declared stimulus onset/offset.",
            "source": "resolved_stimulus.parameter_snapshot",
        },
    }
    windows: list[dict[str, Any]] = []
    for window_id in ANALYSIS_WINDOW_ORDER:
        merged = copy.deepcopy(defaults[window_id])
        if window_id in overrides:
            merged.update(copy.deepcopy(dict(overrides[window_id])))
            merged["window_id"] = window_id
        if float(merged["end_ms"]) <= float(merged["start_ms"]):
            raise ValueError(
                f"analysis window {window_id!r} must have end_ms greater than start_ms."
            )
        windows.append(merged)
    return windows


def _resolve_analysis_condition_catalog(
    resolved_stimulus: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    parameter_snapshot = _require_mapping(
        resolved_stimulus.get("parameter_snapshot"),
        field_name="resolved_stimulus.parameter_snapshot",
    )
    conditions: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    direction_context = _resolve_direction_condition_context(parameter_snapshot)
    if direction_context is not None:
        conditions.extend(
            [
                {
                    "condition_id": PREFERRED_DIRECTION_CONDITION_ID,
                    "display_name": "Preferred Direction",
                    "parameter_name": direction_context["parameter_name"],
                    "value": direction_context["preferred_value"],
                },
                {
                    "condition_id": NULL_DIRECTION_CONDITION_ID,
                    "display_name": "Null Direction",
                    "parameter_name": direction_context["parameter_name"],
                    "value": direction_context["null_value"],
                },
            ]
        )
        pairs.append(
            {
                "pair_id": PREFERRED_VS_NULL_PAIR_ID,
                "pair_kind": "direction_opposition",
                "left_condition_id": PREFERRED_DIRECTION_CONDITION_ID,
                "right_condition_id": NULL_DIRECTION_CONDITION_ID,
                "description": "Preferred-versus-null directional pairing derived from the declared stimulus direction parameter.",
            }
        )
    if "polarity" in parameter_snapshot:
        conditions.extend(
            [
                {
                    "condition_id": ON_POLARITY_CONDITION_ID,
                    "display_name": "ON Polarity",
                    "parameter_name": "polarity",
                    "value": "positive",
                },
                {
                    "condition_id": OFF_POLARITY_CONDITION_ID,
                    "display_name": "OFF Polarity",
                    "parameter_name": "polarity",
                    "value": "negative",
                },
            ]
        )
        pairs.append(
            {
                "pair_id": ON_VS_OFF_PAIR_ID,
                "pair_kind": "polarity_opposition",
                "left_condition_id": ON_POLARITY_CONDITION_ID,
                "right_condition_id": OFF_POLARITY_CONDITION_ID,
                "description": "ON-versus-OFF polarity pairing derived from the declared stimulus polarity semantics.",
            }
        )
    return conditions, pairs


def _resolve_direction_condition_context(
    parameter_snapshot: Mapping[str, Any],
) -> dict[str, Any] | None:
    if "direction_deg" in parameter_snapshot:
        preferred_value = float(parameter_snapshot["direction_deg"])
        return {
            "parameter_name": "direction_deg",
            "preferred_value": preferred_value,
            "null_value": round((preferred_value + 180.0) % 360.0, 6),
        }
    if "drift_direction_deg" in parameter_snapshot:
        preferred_value = float(parameter_snapshot["drift_direction_deg"])
        return {
            "parameter_name": "drift_direction_deg",
            "preferred_value": preferred_value,
            "null_value": round((preferred_value + 180.0) % 360.0, 6),
        }
    if "rotation_direction" in parameter_snapshot:
        preferred_value = _normalize_identifier(
            parameter_snapshot["rotation_direction"],
            field_name="resolved_stimulus.parameter_snapshot.rotation_direction",
        )
        if preferred_value == "clockwise":
            null_value = "counterclockwise"
        elif preferred_value == "counterclockwise":
            null_value = "clockwise"
        else:
            raise ValueError(
                "resolved_stimulus.parameter_snapshot.rotation_direction must be "
                "'clockwise' or 'counterclockwise'."
            )
        return {
            "parameter_name": "rotation_direction",
            "preferred_value": preferred_value,
            "null_value": null_value,
        }
    return None


def _resolve_active_shared_readouts(
    shared_readout_catalog: Sequence[Mapping[str, Any]],
    *,
    requested_readout_ids: Sequence[str],
) -> list[dict[str, Any]]:
    catalog_by_id = {
        str(item["readout_id"]): copy.deepcopy(dict(item))
        for item in shared_readout_catalog
    }
    if requested_readout_ids:
        missing_readout_ids = sorted(set(requested_readout_ids) - set(catalog_by_id))
        if missing_readout_ids:
            raise ValueError(
                "analysis.active_readout_ids references readout ids that are not present "
                f"in simulation.shared_readout_catalog: {missing_readout_ids!r}."
            )
        resolved = [catalog_by_id[readout_id] for readout_id in requested_readout_ids]
    else:
        resolved = [copy.deepcopy(dict(item)) for item in shared_readout_catalog]
    if not resolved:
        raise ValueError(
            "The readout-analysis plan requires at least one active shared readout."
        )
    resolved.sort(key=lambda item: item["readout_id"])
    return resolved


def _build_analysis_arm_pair_catalog(
    arm_plans: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    wave_by_topology: dict[str, Mapping[str, Any]] = {}
    baseline_by_family_and_topology: dict[tuple[str, str], Mapping[str, Any]] = {}
    topology_conditions: set[str] = set()
    for arm_plan in arm_plans:
        arm_reference = _require_mapping(
            arm_plan.get("arm_reference"),
            field_name="arm_plan.arm_reference",
        )
        topology_condition = _normalize_identifier(
            arm_plan.get("topology_condition"),
            field_name="arm_plan.topology_condition",
        )
        topology_conditions.add(topology_condition)
        model_mode = _normalize_identifier(
            arm_reference.get("model_mode"),
            field_name="arm_plan.arm_reference.model_mode",
        )
        if model_mode == SURFACE_WAVE_MODEL_MODE:
            wave_by_topology[topology_condition] = arm_plan
            continue
        baseline_family = arm_reference.get("baseline_family")
        if baseline_family is None:
            continue
        normalized_family = _normalize_nonempty_string(
            baseline_family,
            field_name="arm_plan.arm_reference.baseline_family",
        )
        baseline_by_family_and_topology[(normalized_family, topology_condition)] = arm_plan

    records: list[dict[str, Any]] = []
    for baseline_family in (P0_BASELINE_FAMILY, P1_BASELINE_FAMILY):
        for topology_condition in sorted(topology_conditions, key=_topology_sort_key):
            baseline_arm = baseline_by_family_and_topology.get((baseline_family, topology_condition))
            wave_arm = wave_by_topology.get(topology_condition)
            if baseline_arm is None or wave_arm is None:
                continue
            baseline_arm_id = str(
                _require_mapping(
                    baseline_arm.get("arm_reference"),
                    field_name="baseline_arm.arm_reference",
                )["arm_id"]
            )
            surface_wave_arm_id = str(
                _require_mapping(
                    wave_arm.get("arm_reference"),
                    field_name="wave_arm.arm_reference",
                )["arm_id"]
            )
            records.append(
                {
                    "group_id": (
                        f"matched_surface_wave_vs_{baseline_family.lower()}__"
                        f"{topology_condition}"
                    ),
                    "group_kind": "matched_surface_wave_vs_baseline",
                    "baseline_family": baseline_family,
                    "topology_condition": topology_condition,
                    "baseline_arm_id": baseline_arm_id,
                    "surface_wave_arm_id": surface_wave_arm_id,
                    "arm_ids": [baseline_arm_id, surface_wave_arm_id],
                    "comparison_semantics": "surface_wave_minus_baseline",
                }
            )
    return records


def _build_analysis_comparison_group_catalog(
    arm_pair_catalog: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    pairs_by_family_and_topology = {
        (str(item["baseline_family"]), str(item["topology_condition"])): item
        for item in arm_pair_catalog
    }
    records: list[dict[str, Any]] = []
    for baseline_family in (P0_BASELINE_FAMILY, P1_BASELINE_FAMILY):
        intact_pair = pairs_by_family_and_topology.get((baseline_family, "intact"))
        shuffled_pair = pairs_by_family_and_topology.get((baseline_family, "shuffled"))
        if intact_pair is not None and shuffled_pair is not None:
            records.append(
                {
                    "group_id": f"geometry_ablation__{baseline_family.lower()}",
                    "group_kind": "geometry_ablation",
                    "baseline_family": baseline_family,
                    "component_group_ids": [
                        str(intact_pair["group_id"]),
                        str(shuffled_pair["group_id"]),
                    ],
                    "comparison_semantics": "intact_gap_minus_shuffled_gap",
                }
            )
    topologies = {str(item["topology_condition"]) for item in arm_pair_catalog}
    for topology_condition in sorted(topologies, key=_topology_sort_key):
        p0_pair = pairs_by_family_and_topology.get((P0_BASELINE_FAMILY, topology_condition))
        p1_pair = pairs_by_family_and_topology.get((P1_BASELINE_FAMILY, topology_condition))
        if p0_pair is not None and p1_pair is not None:
            records.append(
                {
                    "group_id": f"baseline_strength_challenge__{topology_condition}",
                    "group_kind": "baseline_strength_challenge",
                    "topology_condition": topology_condition,
                    "component_group_ids": [
                        str(p0_pair["group_id"]),
                        str(p1_pair["group_id"]),
                    ],
                    "comparison_semantics": "p1_survival_against_canonical_p0_reference",
                }
            )
    return records


def _build_seed_aggregation_rules(seed_sweep: Sequence[int]) -> list[dict[str, Any]]:
    rules = [
        {
            "rule_id": PER_RUN_SINGLE_SEED_RULE_ID,
            "aggregation_scope": "single_run",
            "summary_statistics": ["identity"],
            "seed_count": 1,
            "seed_ordering": DEFAULT_SEED_SWEEP_ORDERING,
        }
    ]
    if seed_sweep:
        rules.append(
            {
                "rule_id": MANIFEST_SEED_SWEEP_ROLLUP_RULE_ID,
                "aggregation_scope": "arm_metric_across_seed_sweep",
                "seed_sweep": [int(seed) for seed in seed_sweep],
                "seed_count": len(seed_sweep),
                "summary_statistics": ["mean", "median", "min", "max", "std"],
                "seed_ordering": DEFAULT_SEED_SWEEP_ORDERING,
            }
        )
    return rules


def _build_experiment_output_targets(
    *,
    manifest_payload: Mapping[str, Any],
    output_targets: Mapping[str, Any],
    requested_output_ids: Sequence[str],
    configured_output_targets: Sequence[Mapping[str, Any]],
    comparison_group_catalog: Sequence[Mapping[str, Any]],
    arm_pair_catalog: Sequence[Mapping[str, Any]],
    analysis_contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    del comparison_group_catalog
    del arm_pair_catalog
    declared_targets: dict[str, dict[str, Any]] = {}
    for plot in output_targets.get("plots", []):
        declared_targets[str(plot["id"])] = {
            "path": str(plot["path"]),
            "declared_output_kind": "plot",
        }
    for state in output_targets.get("ui_states", []):
        declared_targets[str(state["id"])] = {
            "path": str(state["path"]),
            "declared_output_kind": "ui_state",
        }

    records: list[dict[str, Any]] = []
    seen_analysis_output_ids: set[str] = set()
    for output_id in manifest_payload.get("must_show_outputs", []):
        normalized_output_id = _normalize_identifier(
            output_id,
            field_name="manifest.must_show_outputs",
        )
        target = declared_targets.get(normalized_output_id)
        if target is None:
            raise ValueError(
                f"Manifest must_show_output {normalized_output_id!r} is missing from the resolved output bundle."
            )
        analysis_output_id = MANIFEST_TO_ANALYSIS_OUTPUT_ID.get(normalized_output_id)
        record = {
            "output_id": normalized_output_id,
            "analysis_output_id": analysis_output_id,
            "path": target["path"],
            "source": "manifest.output_bundle",
            "declared_output_kind": target["declared_output_kind"],
        }
        if analysis_output_id is not None:
            output_definition = get_experiment_comparison_output_definition(
                analysis_output_id,
                record=analysis_contract,
            )
            record["output_kind"] = output_definition["output_kind"]
            record["scope_rule"] = output_definition["scope_rule"]
            record["required_metric_ids"] = list(output_definition["required_metric_ids"])
            record["required_source_artifact_classes"] = list(
                output_definition["required_source_artifact_classes"]
            )
            seen_analysis_output_ids.add(analysis_output_id)
        else:
            record["output_kind"] = target["declared_output_kind"]
            record["scope_rule"] = "manifest_declared_output"
            record["required_metric_ids"] = _manifest_only_output_required_metric_ids(
                normalized_output_id
            )
            record["required_source_artifact_classes"] = []
        records.append(record)

    configured_by_output_id = {
        str(item["output_id"]): dict(item)
        for item in configured_output_targets
    }
    for output_id in sorted(set(requested_output_ids)):
        if output_id in seen_analysis_output_ids:
            continue
        configured_target = configured_by_output_id.get(output_id)
        path = configured_target["path"] if configured_target is not None else None
        output_definition = get_experiment_comparison_output_definition(
            output_id,
            record=analysis_contract,
        )
        records.append(
            {
                "output_id": output_id,
                "analysis_output_id": output_id,
                "path": path,
                "source": (
                    "analysis.experiment_output_targets"
                    if configured_target is not None
                    else "analysis.output_ids"
                ),
                "declared_output_kind": output_definition["output_kind"],
                "output_kind": output_definition["output_kind"],
                "scope_rule": output_definition["scope_rule"],
                "required_metric_ids": list(output_definition["required_metric_ids"]),
                "required_source_artifact_classes": list(
                    output_definition["required_source_artifact_classes"]
                ),
            }
        )
    return records


def _resolve_active_analysis_selection(
    *,
    manifest_payload: Mapping[str, Any],
    analysis_contract: Mapping[str, Any],
    requested_metric_ids: Sequence[str],
    requested_null_test_ids: Sequence[str],
    experiment_output_targets: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    manifest_metric_requests = [
        _normalize_manifest_metric_request(
            manifest_payload["primary_metric"],
            field_name="manifest.primary_metric",
            analysis_contract=analysis_contract,
        ),
        *[
            _normalize_manifest_metric_request(
                metric_id,
                field_name=f"manifest.companion_metrics[{index}]",
                analysis_contract=analysis_contract,
            )
            for index, metric_id in enumerate(manifest_payload.get("companion_metrics", []))
        ],
    ]
    active_metric_ids = set(requested_metric_ids)
    active_null_test_ids = set(requested_null_test_ids)
    active_output_ids: set[str] = set()

    for request in manifest_metric_requests:
        active_metric_ids.update(request["resolved_metric_ids"])
    for target in experiment_output_targets:
        analysis_output_id = target.get("analysis_output_id")
        if analysis_output_id is None:
            continue
        normalized_output_id = _normalize_identifier(
            analysis_output_id,
            field_name="experiment_output_targets.analysis_output_id",
        )
        active_output_ids.add(normalized_output_id)
        output_definition = get_experiment_comparison_output_definition(
            normalized_output_id,
            record=analysis_contract,
        )
        active_metric_ids.update(output_definition["required_metric_ids"])
    for success_criterion_id in manifest_payload.get("success_criteria_ids", []):
        normalized_success_id = _normalize_identifier(
            success_criterion_id,
            field_name="manifest.success_criteria_ids",
        )
        active_null_test_ids.update(
            SUCCESS_CRITERION_NULL_TEST_IDS.get(normalized_success_id, ())
        )

    changed = True
    while changed:
        changed = False
        for null_test_id in list(active_null_test_ids):
            null_test_definition = get_readout_analysis_null_test_hook(
                null_test_id,
                record=analysis_contract,
            )
            new_metric_ids = set(null_test_definition["required_metric_ids"]) - active_metric_ids
            if new_metric_ids:
                active_metric_ids.update(new_metric_ids)
                changed = True

    return {
        "manifest_metric_requests": manifest_metric_requests,
        "active_metric_ids": sorted(active_metric_ids),
        "active_null_test_ids": sorted(active_null_test_ids),
        "active_output_ids": sorted(active_output_ids),
    }


def _resolve_base_analysis_artifact_classes(
    *,
    cfg: Mapping[str, Any],
    arm_plans: Sequence[Mapping[str, Any]],
) -> set[str]:
    artifact_classes = {
        SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
        SHARED_READOUT_TRACES_ARTIFACT_CLASS,
        SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
        STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
        TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
    }
    if len(arm_plans) > 1:
        artifact_classes.add(EXPERIMENT_BUNDLE_SET_ARTIFACT_CLASS)
    if any(
        str(_require_mapping(arm_plan["arm_reference"], field_name="arm_reference")["model_mode"])
        == SURFACE_WAVE_MODEL_MODE
        for arm_plan in arm_plans
    ):
        artifact_classes.update(
            {
                SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
                SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
                SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
            }
        )
    if cfg.get("retinal_geometry") is not None or any(
        arm_plan.get("retinal_input_reference") is not None
        for arm_plan in arm_plans
    ):
        artifact_classes.add(RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS)
    return artifact_classes


def _resolve_available_analysis_artifact_classes(
    *,
    base_artifact_classes: set[str],
    active_metric_ids: Sequence[str],
    active_null_test_ids: Sequence[str],
    analysis_contract: Mapping[str, Any],
) -> set[str]:
    artifact_classes = set(base_artifact_classes)
    if active_metric_ids:
        artifact_classes.add(ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS)
    if active_null_test_ids:
        artifact_classes.add(ANALYSIS_NULL_TEST_ROWS_ARTIFACT_CLASS)
    if any(
        get_readout_analysis_metric_definition(metric_id, record=analysis_contract)["metric_class"]
        == "wave_only_diagnostic"
        for metric_id in active_metric_ids
    ):
        artifact_classes.add(WAVE_DIAGNOSTIC_ROWS_ARTIFACT_CLASS)
    return artifact_classes


def _validate_active_analysis_metrics(
    *,
    active_metric_ids: Sequence[str],
    analysis_contract: Mapping[str, Any],
    active_shared_readouts: Sequence[Mapping[str, Any]],
    condition_pair_catalog: Sequence[Mapping[str, Any]],
    base_artifact_classes: set[str],
) -> None:
    available_pair_ids = {str(item["pair_id"]) for item in condition_pair_catalog}
    for metric_id in active_metric_ids:
        metric_definition = get_readout_analysis_metric_definition(
            metric_id,
            record=analysis_contract,
        )
        missing_artifact_classes = sorted(
            set(metric_definition["required_source_artifact_classes"]) - set(base_artifact_classes)
        )
        if missing_artifact_classes:
            raise ValueError(
                f"Readout-analysis metric {metric_id!r} cannot be realized from local artifacts; "
                f"missing source artifact classes {missing_artifact_classes!r}."
            )
        if (
            SHARED_READOUT_CATALOG_ARTIFACT_CLASS in metric_definition["required_source_artifact_classes"]
            or SHARED_READOUT_TRACES_ARTIFACT_CLASS
            in metric_definition["required_source_artifact_classes"]
        ) and not active_shared_readouts:
            raise ValueError(
                f"Readout-analysis metric {metric_id!r} requires at least one active shared readout."
            )
        missing_pair_ids = sorted(
            set(_required_condition_pair_ids_for_metric(metric_definition)) - available_pair_ids
        )
        if missing_pair_ids:
            raise ValueError(
                f"Readout-analysis metric {metric_id!r} requires stimulus condition pair "
                f"declarations {missing_pair_ids!r}, but the resolved stimulus does not support them."
            )


def _build_metric_recipe_catalog(
    *,
    active_metric_ids: Sequence[str],
    analysis_contract: Mapping[str, Any],
    active_shared_readouts: Sequence[Mapping[str, Any]],
    analysis_window_catalog: Sequence[Mapping[str, Any]],
    condition_catalog: Sequence[Mapping[str, Any]],
    condition_pair_catalog: Sequence[Mapping[str, Any]],
    arm_plans: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    windows_by_id = {
        str(item["window_id"]): item
        for item in analysis_window_catalog
    }
    available_pair_ids = {str(item["pair_id"]) for item in condition_pair_catalog}
    condition_ids = [str(item["condition_id"]) for item in condition_catalog]
    wave_root_ids = _eligible_wave_root_ids(arm_plans)
    records: list[dict[str, Any]] = []
    for metric_id in active_metric_ids:
        metric_definition = get_readout_analysis_metric_definition(
            metric_id,
            record=analysis_contract,
        )
        scope_rule = str(metric_definition["scope_rule"])
        window_id = _analysis_window_id_for_scope(scope_rule)
        recipe_base = {
            "metric_id": metric_id,
            "task_family_id": metric_definition["task_family_id"],
            "metric_class": metric_definition["metric_class"],
            "scope_rule": scope_rule,
            "window_id": window_id,
            "window_reference": copy.deepcopy(windows_by_id[window_id]),
            "required_source_artifact_classes": list(
                metric_definition["required_source_artifact_classes"]
            ),
        }
        if scope_rule == PER_SHARED_READOUT_CONDITION_PAIR_SCOPE:
            for readout in active_shared_readouts:
                for pair_id in _required_condition_pair_ids_for_metric(metric_definition):
                    if pair_id not in available_pair_ids:
                        continue
                    records.append(
                        {
                            **copy.deepcopy(recipe_base),
                            "recipe_id": _build_metric_recipe_id(
                                metric_id,
                                readout_id=str(readout["readout_id"]),
                                window_id=window_id,
                                suffix=pair_id,
                            ),
                            "active_readout_ids": [str(readout["readout_id"])],
                            "condition_ids": [],
                            "condition_pair_id": pair_id,
                            "eligible_root_ids": [],
                        }
                    )
        elif scope_rule == PER_SHARED_READOUT_CONDITION_WINDOW_SCOPE:
            for readout in active_shared_readouts:
                records.append(
                    {
                        **copy.deepcopy(recipe_base),
                        "recipe_id": _build_metric_recipe_id(
                            metric_id,
                            readout_id=str(readout["readout_id"]),
                            window_id=window_id,
                            suffix="conditions",
                        ),
                        "active_readout_ids": [str(readout["readout_id"])],
                        "condition_ids": list(condition_ids),
                        "condition_pair_id": None,
                        "eligible_root_ids": [],
                    }
                )
        elif scope_rule == PER_TASK_DECODER_WINDOW_SCOPE:
            for readout in active_shared_readouts:
                records.append(
                    {
                        **copy.deepcopy(recipe_base),
                        "recipe_id": _build_metric_recipe_id(
                            metric_id,
                            readout_id=str(readout["readout_id"]),
                            window_id=window_id,
                            suffix="task_decoder",
                        ),
                        "active_readout_ids": [str(readout["readout_id"])],
                        "condition_ids": [],
                        "condition_pair_id": (
                            PREFERRED_VS_NULL_PAIR_ID
                            if PREFERRED_VS_NULL_PAIR_ID in available_pair_ids
                            else None
                        ),
                        "eligible_root_ids": [],
                    }
                )
        elif scope_rule in {PER_WAVE_ROOT_WINDOW_SCOPE, PER_WAVE_ROOT_SET_WINDOW_SCOPE}:
            records.append(
                {
                    **copy.deepcopy(recipe_base),
                    "recipe_id": _build_metric_recipe_id(
                        metric_id,
                        readout_id="wave",
                        window_id=window_id,
                        suffix="wave_scope",
                    ),
                    "active_readout_ids": [],
                    "condition_ids": [],
                    "condition_pair_id": None,
                    "eligible_root_ids": list(wave_root_ids),
                }
            )
        else:
            records.append(
                {
                    **copy.deepcopy(recipe_base),
                    "recipe_id": _build_metric_recipe_id(
                        metric_id,
                        readout_id="global",
                        window_id=window_id,
                        suffix="global",
                    ),
                    "active_readout_ids": [],
                    "condition_ids": [],
                    "condition_pair_id": None,
                    "eligible_root_ids": [],
                }
            )
    records.sort(key=lambda item: item["recipe_id"])
    return records


def _build_null_test_declarations(
    *,
    active_null_test_ids: Sequence[str],
    analysis_contract: Mapping[str, Any],
    available_artifact_classes: set[str],
    condition_pair_catalog: Sequence[Mapping[str, Any]],
    comparison_group_catalog: Sequence[Mapping[str, Any]],
    metric_recipe_catalog: Sequence[Mapping[str, Any]],
    seed_aggregation_rules: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    available_pair_ids = {str(item["pair_id"]) for item in condition_pair_catalog}
    available_group_ids_by_kind: dict[str, list[str]] = {}
    for item in comparison_group_catalog:
        available_group_ids_by_kind.setdefault(str(item["group_kind"]), []).append(
            str(item["group_id"])
        )
    seed_rule_ids = {
        str(item["rule_id"])
        for item in seed_aggregation_rules
    }
    recipe_ids_by_metric: dict[str, list[str]] = {}
    for recipe in metric_recipe_catalog:
        recipe_ids_by_metric.setdefault(str(recipe["metric_id"]), []).append(
            str(recipe["recipe_id"])
        )

    records: list[dict[str, Any]] = []
    for null_test_id in active_null_test_ids:
        null_test_definition = get_readout_analysis_null_test_hook(
            null_test_id,
            record=analysis_contract,
        )
        missing_artifact_classes = sorted(
            set(null_test_definition["required_source_artifact_classes"])
            - set(available_artifact_classes)
        )
        if missing_artifact_classes:
            raise ValueError(
                f"Readout-analysis null test {null_test_id!r} cannot be realized from local artifacts; "
                f"missing source artifact classes {missing_artifact_classes!r}."
            )
        required_pair_ids = _required_condition_pair_ids_for_null_test(null_test_id)
        missing_pair_ids = sorted(set(required_pair_ids) - available_pair_ids)
        if missing_pair_ids:
            raise ValueError(
                f"Readout-analysis null test {null_test_id!r} requires condition pair "
                f"declarations {missing_pair_ids!r}, but the resolved stimulus does not support them."
            )
        comparison_group_ids = _required_comparison_group_ids_for_null_test(
            null_test_id,
            available_group_ids_by_kind,
        )
        if null_test_id == "seed_stability" and MANIFEST_SEED_SWEEP_ROLLUP_RULE_ID not in seed_rule_ids:
            raise ValueError(
                "Readout-analysis null test 'seed_stability' requires a declared manifest seed_sweep."
            )
        records.append(
            {
                **copy.deepcopy(null_test_definition),
                "comparison_group_ids": comparison_group_ids,
                "condition_pair_ids": required_pair_ids,
                "metric_recipe_ids": [
                    recipe_id
                    for metric_id in null_test_definition["required_metric_ids"]
                    for recipe_id in recipe_ids_by_metric.get(str(metric_id), [])
                ],
                "seed_aggregation_rule_id": (
                    MANIFEST_SEED_SWEEP_ROLLUP_RULE_ID
                    if null_test_id == "seed_stability"
                    else PER_RUN_SINGLE_SEED_RULE_ID
                ),
            }
        )
    records.sort(key=lambda item: item["null_test_id"])
    return records


def _validate_experiment_output_targets(
    *,
    experiment_output_targets: Sequence[Mapping[str, Any]],
    active_metric_ids: Sequence[str],
    available_artifact_classes: set[str],
    comparison_group_catalog: Sequence[Mapping[str, Any]],
    arm_pair_catalog: Sequence[Mapping[str, Any]],
    active_shared_readouts: Sequence[Mapping[str, Any]],
    analysis_contract: Mapping[str, Any],
) -> None:
    available_group_kinds = {
        str(item["group_kind"])
        for item in comparison_group_catalog
    }
    has_matched_pairs = bool(arm_pair_catalog)
    for target in experiment_output_targets:
        output_id = str(target["output_id"])
        analysis_output_id = target.get("analysis_output_id")
        if analysis_output_id is not None:
            normalized_analysis_output_id = _normalize_identifier(
                analysis_output_id,
                field_name="experiment_output_targets.analysis_output_id",
            )
            if target.get("path") in (None, ""):
                raise ValueError(
                    f"Readout-analysis output {normalized_analysis_output_id!r} was requested "
                    "but no experiment output target path was declared."
                )
            output_definition = get_experiment_comparison_output_definition(
                normalized_analysis_output_id,
                record=analysis_contract,
            )
            missing_artifact_classes = sorted(
                set(output_definition["required_source_artifact_classes"])
                - set(available_artifact_classes)
            )
            if missing_artifact_classes:
                raise ValueError(
                    f"Readout-analysis output {normalized_analysis_output_id!r} cannot be realized "
                    f"from local artifacts; missing source artifact classes {missing_artifact_classes!r}."
                )
            missing_metric_ids = sorted(
                set(output_definition["required_metric_ids"]) - set(active_metric_ids)
            )
            if missing_metric_ids:
                raise ValueError(
                    f"Readout-analysis output {normalized_analysis_output_id!r} requires metric ids "
                    f"{missing_metric_ids!r} that are not active in the normalized analysis plan."
                )
            continue

        if output_id in {"shared_output_trace_overlay", "surface_vs_baseline_split_view"} and not has_matched_pairs:
            raise ValueError(
                f"Manifest output {output_id!r} cannot be realized because no matched baseline-versus-surface_wave arm pair exists."
            )
        if output_id == "shared_output_trace_overlay" and not active_shared_readouts:
            raise ValueError(
                "Manifest output 'shared_output_trace_overlay' requires at least one active shared readout."
            )
        if output_id == "topology_ablation_comparison" and "geometry_ablation" not in available_group_kinds:
            raise ValueError(
                "Manifest output 'topology_ablation_comparison' cannot be realized because no geometry-ablation comparison group exists."
            )
        if output_id == "baseline_challenge_comparison" and "baseline_strength_challenge" not in available_group_kinds:
            raise ValueError(
                "Manifest output 'baseline_challenge_comparison' cannot be realized because no baseline-strength challenge comparison group exists."
            )


def _build_manifest_metric_request_catalog(
    *,
    manifest_payload: Mapping[str, Any],
    analysis_contract: Mapping[str, Any],
    metric_recipe_catalog: Sequence[Mapping[str, Any]],
    comparison_group_catalog: Sequence[Mapping[str, Any]],
    arm_pair_catalog: Sequence[Mapping[str, Any]],
    seed_aggregation_rules: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    available_pair_ids = {
        str(recipe["condition_pair_id"])
        for recipe in metric_recipe_catalog
        if recipe.get("condition_pair_id") is not None
    }
    recipe_ids_by_metric: dict[str, list[str]] = {}
    for recipe in metric_recipe_catalog:
        recipe_ids_by_metric.setdefault(str(recipe["metric_id"]), []).append(
            str(recipe["recipe_id"])
        )
    comparison_groups_by_kind: dict[str, list[str]] = {}
    for item in comparison_group_catalog:
        comparison_groups_by_kind.setdefault(str(item["group_kind"]), []).append(
            str(item["group_id"])
        )
    matched_pair_ids = [str(item["group_id"]) for item in arm_pair_catalog]
    seed_rule_ids = {
        str(item["rule_id"])
        for item in seed_aggregation_rules
    }

    requests = [
        ("primary", manifest_payload["primary_metric"]),
        *[
            ("companion", metric_id)
            for metric_id in manifest_payload.get("companion_metrics", [])
        ],
    ]
    records: list[dict[str, Any]] = []
    for request_index, (request_role, requested_metric_id) in enumerate(requests):
        request = _normalize_manifest_metric_request(
            requested_metric_id,
            field_name=f"manifest.{request_role}_metric",
            analysis_contract=analysis_contract,
        )
        missing_pair_ids = sorted(
            set(request["required_condition_pair_ids"]) - available_pair_ids
        )
        if missing_pair_ids:
            raise ValueError(
                f"Manifest metric request {request['requested_metric_id']!r} requires condition pair "
                f"declarations {missing_pair_ids!r}, but the resolved stimulus does not support them."
            )
        comparison_group_ids = []
        for group_kind in request["comparison_group_kinds"]:
            if group_kind == "matched_surface_wave_vs_baseline":
                comparison_group_ids.extend(matched_pair_ids)
            else:
                comparison_group_ids.extend(comparison_groups_by_kind.get(group_kind, []))
        comparison_group_ids = sorted(set(comparison_group_ids))
        if not comparison_group_ids:
            raise ValueError(
                f"Manifest metric request {request['requested_metric_id']!r} does not have any compatible comparison groups in the normalized analysis plan."
            )
        seed_rule_id = (
            MANIFEST_SEED_SWEEP_ROLLUP_RULE_ID
            if request["recipe_kind"] == "seed_rolled_geometry_sensitive_metric_family"
            else PER_RUN_SINGLE_SEED_RULE_ID
        )
        if seed_rule_id == MANIFEST_SEED_SWEEP_ROLLUP_RULE_ID and seed_rule_id not in seed_rule_ids:
            raise ValueError(
                f"Manifest metric request {request['requested_metric_id']!r} requires a declared manifest seed_sweep."
            )
        records.append(
            {
                "requested_metric_id": request["requested_metric_id"],
                "request_role": request_role,
                "request_order": request_index,
                "recipe_kind": request["recipe_kind"],
                "resolved_metric_ids": list(request["resolved_metric_ids"]),
                "metric_recipe_ids": [
                    recipe_id
                    for metric_id in request["resolved_metric_ids"]
                    for recipe_id in recipe_ids_by_metric.get(metric_id, [])
                ],
                "comparison_group_ids": comparison_group_ids,
                "condition_pair_ids": list(request["required_condition_pair_ids"]),
                "seed_aggregation_rule_id": seed_rule_id,
            }
        )
    return records


def _build_per_run_analysis_output_targets(
    arm_plans: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for arm_plan in arm_plans:
        arm_reference = _require_mapping(
            arm_plan.get("arm_reference"),
            field_name="arm_plan.arm_reference",
        )
        bundle_metadata = _require_mapping(
            _require_mapping(
                arm_plan.get("result_bundle"),
                field_name="arm_plan.result_bundle",
            ).get("metadata"),
            field_name="arm_plan.result_bundle.metadata",
        )
        artifacts = _require_mapping(
            bundle_metadata.get("artifacts"),
            field_name="arm_plan.result_bundle.metadata.artifacts",
        )
        artifact_ids = ("metadata_json", "state_summary", "readout_traces", "metrics_table")
        records.append(
            {
                "arm_id": str(arm_reference["arm_id"]),
                "model_mode": str(arm_reference["model_mode"]),
                "bundle_id": str(bundle_metadata["bundle_id"]),
                "artifact_targets": [
                    {
                        "artifact_id": artifact_id,
                        "path": str(_require_mapping(artifacts[artifact_id], field_name=f"artifacts.{artifact_id}")["path"]),
                        "status": str(_require_mapping(artifacts[artifact_id], field_name=f"artifacts.{artifact_id}")["status"]),
                        "artifact_scope": str(_require_mapping(artifacts[artifact_id], field_name=f"artifacts.{artifact_id}")["artifact_scope"]),
                    }
                    for artifact_id in artifact_ids
                ],
            }
        )
    return records


def _normalize_manifest_metric_request(
    requested_metric_id: Any,
    *,
    field_name: str,
    analysis_contract: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_metric_id = _normalize_identifier(
        requested_metric_id,
        field_name=field_name,
    )
    recipe = MANIFEST_TASK_METRIC_RECIPES.get(normalized_metric_id)
    if recipe is not None:
        return {
            "requested_metric_id": normalized_metric_id,
            "recipe_kind": str(recipe["recipe_kind"]),
            "resolved_metric_ids": [str(item) for item in recipe["resolved_metric_ids"]],
            "required_condition_pair_ids": [
                str(item) for item in recipe["required_condition_pair_ids"]
            ],
            "comparison_group_kinds": [str(item) for item in recipe["comparison_group_kinds"]],
        }
    try:
        metric_definition = get_readout_analysis_metric_definition(
            normalized_metric_id,
            record=analysis_contract,
        )
    except ValueError as exc:
        raise ValueError(
            f"Manifest requested unsupported analysis metric id {normalized_metric_id!r}."
        ) from exc
    return {
        "requested_metric_id": normalized_metric_id,
        "recipe_kind": "contract_metric",
        "resolved_metric_ids": [normalized_metric_id],
        "required_condition_pair_ids": _required_condition_pair_ids_for_metric(metric_definition),
        "comparison_group_kinds": ["matched_surface_wave_vs_baseline"],
    }


def _required_condition_pair_ids_for_metric(
    metric_definition: Mapping[str, Any],
) -> list[str]:
    metric_id = str(metric_definition["metric_id"])
    if metric_id in {
        "direction_selectivity_index",
        "motion_vector_heading_deg",
        "motion_vector_speed_deg_per_s",
        "null_direction_suppression_index",
        "optic_flow_heading_deg",
        "optic_flow_speed_deg_per_s",
    }:
        return [PREFERRED_VS_NULL_PAIR_ID]
    if metric_id == "on_off_selectivity_index":
        return [ON_VS_OFF_PAIR_ID]
    return []


def _required_condition_pair_ids_for_null_test(null_test_id: str) -> list[str]:
    if null_test_id == "direction_label_swap":
        return [PREFERRED_VS_NULL_PAIR_ID]
    if null_test_id == "polarity_label_swap":
        return [ON_VS_OFF_PAIR_ID]
    return []


def _required_comparison_group_ids_for_null_test(
    null_test_id: str,
    available_group_ids_by_kind: Mapping[str, Sequence[str]],
) -> list[str]:
    if null_test_id == "geometry_shuffle_collapse":
        group_ids = list(available_group_ids_by_kind.get("geometry_ablation", []))
        if not group_ids:
            raise ValueError(
                "Readout-analysis null test 'geometry_shuffle_collapse' requires a geometry-ablation comparison group."
            )
        return group_ids
    if null_test_id == "stronger_baseline_survival":
        group_ids = list(available_group_ids_by_kind.get("baseline_strength_challenge", []))
        if not group_ids:
            raise ValueError(
                "Readout-analysis null test 'stronger_baseline_survival' requires a baseline-strength challenge comparison group."
            )
        return group_ids
    if null_test_id == "seed_stability":
        return list(available_group_ids_by_kind.get("geometry_ablation", []))
    return []


def _analysis_window_id_for_scope(scope_rule: str) -> str:
    if scope_rule in {
        PER_SHARED_READOUT_CONDITION_PAIR_SCOPE,
        PER_SHARED_READOUT_CONDITION_WINDOW_SCOPE,
    }:
        return SHARED_RESPONSE_WINDOW_ID
    if scope_rule == PER_TASK_DECODER_WINDOW_SCOPE:
        return TASK_DECODER_WINDOW_ID
    if scope_rule in {
        PER_WAVE_ROOT_SET_WINDOW_SCOPE,
        PER_WAVE_ROOT_WINDOW_SCOPE,
    }:
        return WAVE_DIAGNOSTIC_WINDOW_ID
    return FULL_TIMEBASE_WINDOW_ID


def _build_metric_recipe_id(
    metric_id: str,
    *,
    readout_id: str,
    window_id: str,
    suffix: str,
) -> str:
    return f"{metric_id}__{readout_id}__{window_id}__{suffix}"


def _eligible_wave_root_ids(arm_plans: Sequence[Mapping[str, Any]]) -> list[int]:
    root_ids: set[int] = set()
    for arm_plan in arm_plans:
        arm_reference = _require_mapping(
            arm_plan.get("arm_reference"),
            field_name="arm_plan.arm_reference",
        )
        if str(arm_reference["model_mode"]) != SURFACE_WAVE_MODEL_MODE:
            continue
        model_configuration = _require_mapping(
            arm_plan.get("model_configuration"),
            field_name="arm_plan.model_configuration",
        )
        execution_plan = model_configuration.get("surface_wave_execution_plan")
        if not isinstance(execution_plan, Mapping):
            continue
        for item in execution_plan.get("selected_root_operator_assets", []):
            if not isinstance(item, Mapping):
                continue
            root_ids.add(int(item["root_id"]))
    return sorted(root_ids)


def _manifest_only_output_required_metric_ids(output_id: str) -> list[str]:
    if output_id == "baseline_challenge_comparison":
        return [
            "null_direction_suppression_index",
            "response_latency_to_peak_ms",
        ]
    if output_id == "topology_ablation_comparison":
        return [
            "direction_selectivity_index",
            "null_direction_suppression_index",
            "response_latency_to_peak_ms",
        ]
    if output_id == "shared_output_trace_overlay":
        return ["null_direction_suppression_index"]
    return []


def _topology_sort_key(value: str) -> tuple[int, str]:
    if value == "intact":
        return (0, value)
    if value == "shuffled":
        return (1, value)
    return (2, value)
