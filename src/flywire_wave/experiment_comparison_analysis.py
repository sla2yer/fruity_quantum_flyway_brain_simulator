from __future__ import annotations

import copy
import itertools
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .io_utils import write_json
from .readout_analysis_contract import (
    ANALYSIS_UI_PAYLOAD_OUTPUT_ID,
    LATENCY_SHIFT_COMPARISON_OUTPUT_ID,
    MILESTONE_1_DECISION_PANEL_OUTPUT_ID,
    NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID,
    WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID,
    WAVE_ONLY_DIAGNOSTIC_CLASS,
    get_experiment_comparison_output_definition,
    get_readout_analysis_metric_definition,
)
from .shared_readout_analysis import (
    SUPPORTED_SHARED_READOUT_ANALYSIS_METRIC_IDS,
    _rounded_float,
    compute_shared_readout_analysis,
)
from .simulation_planning import (
    MANIFEST_SEED_SWEEP_ROLLUP_RULE_ID,
    PER_RUN_SINGLE_SEED_RULE_ID,
    discover_simulation_run_plans,
    resolve_manifest_readout_analysis_plan,
    resolve_manifest_simulation_plan,
)
from .simulator_result_contract import (
    READOUT_TRACES_KEY,
    STATE_SUMMARY_KEY,
    load_simulator_result_bundle_metadata,
    parse_simulator_readout_definition,
    parse_simulator_result_bundle_metadata,
)
from .stimulus_contract import (
    load_stimulus_bundle_metadata,
    _normalize_float,
    _normalize_identifier,
    _normalize_nonempty_string,
)
from .task_decoder_analysis import (
    SUPPORTED_TASK_DECODER_ANALYSIS_METRIC_IDS,
    compute_task_decoder_analysis,
)
from .wave_structure_analysis import (
    SUPPORTED_WAVE_STRUCTURE_METRIC_IDS,
    compute_wave_structure_diagnostics,
)


EXPERIMENT_COMPARISON_SUMMARY_VERSION = "experiment_comparison_summary.v1"
_CONDITION_VALUE_TOLERANCE = 1.0e-6
_EFFECT_ABS_TOLERANCE = 1.0e-12
_IGNORED_SELECTED_ASSET_ROLES = frozenset({"input_bundle"})


def discover_experiment_bundle_set(
    *,
    simulation_plan: Mapping[str, Any],
    analysis_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_simulation_plan = _normalize_simulation_plan(simulation_plan)
    normalized_analysis_plan = _normalize_analysis_plan(
        analysis_plan or normalized_simulation_plan["readout_analysis_plan"]
    )
    manifest_reference = _require_mapping(
        normalized_simulation_plan.get("manifest_reference"),
        field_name="simulation_plan.manifest_reference",
    )
    experiment_id = _normalize_identifier(
        manifest_reference.get("experiment_id"),
        field_name="simulation_plan.manifest_reference.experiment_id",
    )
    arm_ids = [
        _normalize_identifier(arm_id, field_name="simulation_plan.arm_order")
        for arm_id in normalized_simulation_plan["arm_order"]
    ]
    per_seed_run_plans = discover_simulation_run_plans(
        normalized_simulation_plan,
        use_manifest_seed_sweep=True,
    )
    canonical_arm_plans = {
        str(item["arm_reference"]["arm_id"]): copy.deepcopy(dict(item))
        for item in normalized_simulation_plan["arm_plans"]
    }
    expected_seeds_by_arm_id: dict[str, list[int]] = {}
    for item in per_seed_run_plans:
        arm_id = str(item["arm_reference"]["arm_id"])
        expected_seeds_by_arm_id.setdefault(arm_id, []).append(
            int(item["determinism"]["seed"])
        )
    expected_seeds_by_arm_id = {
        arm_id: sorted(set(seeds))
        for arm_id, seeds in expected_seeds_by_arm_id.items()
    }
    processed_simulator_results_dir = Path(
        _require_mapping(
            normalized_simulation_plan["arm_plans"][0]["runtime"],
            field_name="simulation_plan.arm_plans[0].runtime",
        )["processed_simulator_results_dir"]
    ).resolve()
    condition_groups = _condition_groups_from_plan(normalized_analysis_plan)
    requires_condition_labels = _plan_requires_condition_labels(normalized_analysis_plan)
    expected_condition_signatures = _expected_condition_signatures(
        condition_groups if requires_condition_labels else {}
    )
    expected_signature_keys = {
        tuple(signature["condition_ids"])
        for signature in expected_condition_signatures
    }

    bundle_records: list[dict[str, Any]] = []
    bundle_inventory: list[dict[str, Any]] = []
    seen_bundle_keys: set[tuple[str, int, tuple[str, ...]]] = set()

    for arm_id in arm_ids:
        arm_plan = canonical_arm_plans.get(arm_id)
        if arm_plan is None:
            raise ValueError(
                f"Simulation plan is missing canonical arm plan metadata for arm_id {arm_id!r}."
            )
        arm_bundle_dir = (
            processed_simulator_results_dir / "bundles" / experiment_id / arm_id
        ).resolve()
        metadata_paths = sorted(arm_bundle_dir.glob("*/simulator_result_bundle.json"))
        if not metadata_paths:
            raise ValueError(
                f"Experiment {experiment_id!r} is missing local simulator bundles for arm_id "
                f"{arm_id!r} under {arm_bundle_dir}."
            )
        for metadata_path in metadata_paths:
            metadata = load_simulator_result_bundle_metadata(metadata_path)
            _validate_bundle_against_arm_plan(
                bundle_metadata=metadata,
                arm_plan=arm_plan,
                analysis_plan=normalized_analysis_plan,
                experiment_id=experiment_id,
            )
            seed = int(metadata["determinism"]["seed"])
            expected_seeds = expected_seeds_by_arm_id.get(arm_id, [])
            if seed not in set(expected_seeds):
                raise ValueError(
                    f"Discovered simulator bundle {metadata['bundle_id']!r} uses seed {seed!r}, "
                    f"but the normalized simulation plan expects seeds {expected_seeds!r} for "
                    f"arm_id {arm_id!r}."
                )
            inferred = _infer_bundle_conditions(
                bundle_metadata=metadata,
                condition_groups=condition_groups,
                requires_condition_labels=requires_condition_labels,
            )
            condition_ids = list(inferred["condition_ids"])
            condition_key = tuple(condition_ids)
            if requires_condition_labels and condition_key not in expected_signature_keys:
                raise ValueError(
                    f"Discovered simulator bundle {metadata['bundle_id']!r} maps to unexpected "
                    f"condition_ids {condition_ids!r}; expected one of "
                    f"{sorted(expected_signature_keys)!r} from the normalized analysis plan."
                )
            bundle_key = (arm_id, seed, condition_key)
            if bundle_key in seen_bundle_keys:
                raise ValueError(
                    f"Experiment bundle discovery found duplicate coverage for arm_id {arm_id!r}, "
                    f"seed {seed!r}, and condition_ids {condition_ids!r}."
                )
            seen_bundle_keys.add(bundle_key)
            bundle_records.append(
                {
                    "bundle_metadata": metadata,
                    "bundle_metadata_path": str(metadata_path.resolve()),
                    "condition_ids": condition_ids,
                }
            )
            bundle_inventory.append(
                {
                    "bundle_id": str(metadata["bundle_id"]),
                    "metadata_path": str(metadata_path.resolve()),
                    "arm_id": arm_id,
                    "model_mode": str(metadata["arm_reference"]["model_mode"]),
                    "baseline_family": metadata["arm_reference"]["baseline_family"],
                    "seed": seed,
                    "condition_ids": condition_ids,
                    "condition_signature": _condition_signature(condition_ids),
                    "stimulus_family": inferred["stimulus_family"],
                    "stimulus_name": inferred["stimulus_name"],
                    "parameter_snapshot": inferred["parameter_snapshot"],
                    "available_readout_ids": [
                        str(item["readout_id"]) for item in metadata["readout_catalog"]
                    ],
                }
            )

    _validate_bundle_coverage(
        bundle_inventory=bundle_inventory,
        arm_ids=arm_ids,
        expected_seeds_by_arm_id=expected_seeds_by_arm_id,
        expected_condition_signatures=expected_condition_signatures,
        requires_condition_labels=requires_condition_labels,
    )
    bundle_inventory.sort(
        key=lambda item: (
            str(item["arm_id"]),
            int(item["seed"]),
            str(item["condition_signature"]),
            str(item["bundle_id"]),
        )
    )
    bundle_records.sort(
        key=lambda item: (
            str(item["bundle_metadata"]["arm_reference"]["arm_id"]),
            int(item["bundle_metadata"]["determinism"]["seed"]),
            _condition_signature(item["condition_ids"]),
            str(item["bundle_metadata"]["bundle_id"]),
        )
    )
    return {
        "bundle_set_version": "experiment_bundle_set.v1",
        "experiment_id": experiment_id,
        "processed_simulator_results_dir": str(processed_simulator_results_dir),
        "expected_arm_ids": arm_ids,
        "expected_seeds_by_arm_id": expected_seeds_by_arm_id,
        "expected_condition_signatures": expected_condition_signatures,
        "bundle_inventory": bundle_inventory,
        "bundle_records": bundle_records,
    }


def compute_experiment_comparison_summary(
    *,
    analysis_plan: Mapping[str, Any],
    bundle_set: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_analysis_plan = _normalize_analysis_plan(analysis_plan)
    normalized_bundle_set = _normalize_bundle_set(bundle_set)
    bundle_records = [
        copy.deepcopy(dict(item)) for item in normalized_bundle_set["bundle_records"]
    ]

    comparable_metric_ids = _comparable_metric_ids(normalized_analysis_plan)
    shared_metric_ids = sorted(
        set(normalized_analysis_plan["active_metric_ids"])
        & set(SUPPORTED_SHARED_READOUT_ANALYSIS_METRIC_IDS)
    )
    task_metric_ids = sorted(
        set(normalized_analysis_plan["active_metric_ids"])
        & set(SUPPORTED_TASK_DECODER_ANALYSIS_METRIC_IDS)
    )
    wave_metric_ids = sorted(
        set(normalized_analysis_plan["active_metric_ids"])
        & set(SUPPORTED_WAVE_STRUCTURE_METRIC_IDS)
    )

    shared_result = (
        compute_shared_readout_analysis(
            analysis_plan=_subset_analysis_plan(
                normalized_analysis_plan,
                metric_ids=shared_metric_ids,
            ),
            bundle_records=bundle_records,
        )
        if shared_metric_ids
        else {
            "contract_version": None,
            "analysis_plan_version": normalized_analysis_plan["plan_version"],
            "metric_rows": [],
            "metric_summaries": [],
            "skipped_recipes": [],
        }
    )
    task_result = (
        compute_task_decoder_analysis(
            analysis_plan=_subset_analysis_plan(
                normalized_analysis_plan,
                metric_ids=task_metric_ids,
            ),
            bundle_records=bundle_records,
        )
        if task_metric_ids
        else {
            "contract_version": None,
            "analysis_plan_version": normalized_analysis_plan["plan_version"],
            "metric_rows": [],
            "decoder_summaries": [],
            "skipped_recipes": [],
        }
    )
    wave_records = [
        copy.deepcopy(dict(item))
        for item in bundle_records
        if str(item["bundle_metadata"]["arm_reference"]["model_mode"]) == "surface_wave"
    ]
    wave_result = (
        compute_wave_structure_diagnostics(
            bundle_records=wave_records,
            analysis_windows=_wave_analysis_windows(normalized_analysis_plan),
            requested_metric_ids=wave_metric_ids,
        )
        if wave_metric_ids
        else {
            "contract_version": None,
            "wave_diagnostic_interface_version": None,
            "metric_rows": [],
            "diagnostic_summaries": [],
        }
    )

    combined_metric_rows = _combined_metric_rows(
        shared_result=shared_result,
        task_result=task_result,
        wave_result=wave_result,
    )
    combined_metric_rows.sort(key=_metric_row_sort_key)

    combined_group_catalog = _combined_group_catalog(normalized_analysis_plan)
    expected_seeds_by_group_id = _expected_seeds_by_group_id(
        analysis_plan=normalized_analysis_plan,
        bundle_set=normalized_bundle_set,
    )
    metric_rows_by_arm_seed_key = _index_metric_rows_by_arm_seed_key(
        metric_rows=combined_metric_rows,
        comparable_metric_ids=comparable_metric_ids,
    )
    matched_detail_rows = _build_matched_pair_detail_rows(
        analysis_plan=normalized_analysis_plan,
        expected_seeds_by_group_id=expected_seeds_by_group_id,
        metric_rows_by_arm_seed_key=metric_rows_by_arm_seed_key,
    )
    detail_rows_by_group_id = {
        str(item["group_id"]): [] for item in combined_group_catalog
    }
    for row in matched_detail_rows:
        detail_rows_by_group_id[str(row["group_id"])].append(copy.deepcopy(dict(row)))
    derived_detail_rows = _build_derived_detail_rows(
        analysis_plan=normalized_analysis_plan,
        detail_rows_by_group_id=detail_rows_by_group_id,
        expected_seeds_by_group_id=expected_seeds_by_group_id,
    )
    comparison_detail_rows = matched_detail_rows + derived_detail_rows
    comparison_detail_rows.sort(key=_comparison_detail_row_sort_key)
    group_metric_seed_rows = _build_group_metric_seed_rows(comparison_detail_rows)
    group_metric_seed_rows.sort(key=_group_metric_seed_row_sort_key)
    group_metric_rollups = _build_group_metric_rollups(
        group_metric_seed_rows=group_metric_seed_rows,
        expected_seeds_by_group_id=expected_seeds_by_group_id,
        analysis_plan=normalized_analysis_plan,
    )
    group_metric_rollups.sort(key=_group_metric_rollup_sort_key)
    wave_metric_seed_rows = _build_wave_metric_seed_rows(wave_result.get("metric_rows", []))
    wave_metric_seed_rows.sort(key=_wave_metric_seed_row_sort_key)
    wave_metric_rollups = _build_wave_metric_rollups(wave_metric_seed_rows)
    wave_metric_rollups.sort(key=_wave_metric_rollup_sort_key)

    null_test_results = _evaluate_null_tests(
        analysis_plan=normalized_analysis_plan,
        group_metric_seed_rows=group_metric_seed_rows,
        group_metric_rollups=group_metric_rollups,
        shared_result=shared_result,
        task_result=task_result,
        wave_result=wave_result,
    )
    null_test_results.sort(key=lambda item: str(item["null_test_id"]))
    task_scores, task_score_families = _build_task_scores(
        analysis_plan=normalized_analysis_plan,
        group_metric_rollups=group_metric_rollups,
    )
    task_scores.sort(key=_task_score_sort_key)
    task_score_families.sort(key=lambda item: str(item["requested_metric_id"]))
    decision_panel = _build_milestone_1_decision_panel(
        analysis_plan=normalized_analysis_plan,
        task_scores=task_scores,
        null_test_results=null_test_results,
    )
    output_summaries = _build_output_summaries(
        analysis_plan=normalized_analysis_plan,
        group_metric_rollups=group_metric_rollups,
        wave_metric_rollups=wave_metric_rollups,
        task_scores=task_scores,
        task_score_families=task_score_families,
        null_test_results=null_test_results,
        decision_panel=decision_panel,
    )
    output_summaries.sort(key=lambda item: str(item["output_id"]))

    return {
        "summary_version": EXPERIMENT_COMPARISON_SUMMARY_VERSION,
        "analysis_plan_version": str(normalized_analysis_plan["plan_version"]),
        "manifest_reference": copy.deepcopy(dict(normalized_analysis_plan["manifest_reference"])),
        "contract_reference": copy.deepcopy(dict(normalized_analysis_plan["contract_reference"])),
        "bundle_set": {
            "bundle_set_version": str(normalized_bundle_set["bundle_set_version"]),
            "experiment_id": str(normalized_bundle_set["experiment_id"]),
            "processed_simulator_results_dir": str(
                normalized_bundle_set["processed_simulator_results_dir"]
            ),
            "expected_arm_ids": list(normalized_bundle_set["expected_arm_ids"]),
            "expected_seeds_by_arm_id": copy.deepcopy(
                dict(normalized_bundle_set["expected_seeds_by_arm_id"])
            ),
            "expected_condition_signatures": copy.deepcopy(
                list(normalized_bundle_set["expected_condition_signatures"])
            ),
            "bundle_inventory": copy.deepcopy(list(normalized_bundle_set["bundle_inventory"])),
        },
        "analysis_results": {
            "shared_readout_analysis": shared_result,
            "task_decoder_analysis": task_result,
            "wave_diagnostic_analysis": wave_result,
            "combined_metric_rows": combined_metric_rows,
        },
        "comparison_group_catalog": combined_group_catalog,
        "comparison_detail_rows": comparison_detail_rows,
        "group_metric_seed_rows": group_metric_seed_rows,
        "group_metric_rollups": group_metric_rollups,
        "wave_metric_seed_rows": wave_metric_seed_rows,
        "wave_metric_rollups": wave_metric_rollups,
        "null_test_results": null_test_results,
        "task_scores": task_scores,
        "task_score_families": task_score_families,
        "milestone_1_decision_panel": decision_panel,
        "output_summaries": output_summaries,
    }


def execute_experiment_comparison_workflow(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    simulation_plan = resolve_manifest_simulation_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    analysis_plan = resolve_manifest_readout_analysis_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    bundle_set = discover_experiment_bundle_set(
        simulation_plan=simulation_plan,
        analysis_plan=analysis_plan,
    )
    summary = compute_experiment_comparison_summary(
        analysis_plan=analysis_plan,
        bundle_set=bundle_set,
    )
    written_path = (
        write_experiment_comparison_summary(summary, output_path)
        if output_path is not None
        else None
    )
    result = copy.deepcopy(dict(summary))
    result["summary_path"] = None if written_path is None else str(written_path)
    return result


def write_experiment_comparison_summary(
    summary: Mapping[str, Any],
    output_path: str | Path,
) -> Path:
    normalized_summary = _normalize_summary(summary)
    return write_json(normalized_summary, output_path)


def _normalize_simulation_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, Mapping):
        raise ValueError("simulation_plan must be a mapping.")
    required_fields = (
        "manifest_reference",
        "runtime_config",
        "arm_order",
        "arm_plans",
        "readout_analysis_plan",
    )
    missing_fields = [field for field in required_fields if field not in plan]
    if missing_fields:
        raise ValueError(
            f"simulation_plan is missing required fields {missing_fields!r}."
        )
    return copy.deepcopy(dict(plan))


def _normalize_analysis_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, Mapping):
        raise ValueError("analysis_plan must be a mapping.")
    required_fields = (
        "plan_version",
        "manifest_reference",
        "contract_reference",
        "condition_catalog",
        "condition_pair_catalog",
        "analysis_window_catalog",
        "arm_pair_catalog",
        "comparison_group_catalog",
        "seed_aggregation_rules",
        "active_metric_ids",
        "active_metric_definitions",
        "active_output_ids",
        "active_null_test_ids",
        "metric_recipe_catalog",
        "null_test_declarations",
        "manifest_metric_requests",
        "active_shared_readouts",
        "experiment_output_targets",
    )
    missing_fields = [field for field in required_fields if field not in plan]
    if missing_fields:
        raise ValueError(
            f"analysis_plan is missing required fields {missing_fields!r}."
        )
    return copy.deepcopy(dict(plan))


def _normalize_bundle_set(bundle_set: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle_set, Mapping):
        raise ValueError("bundle_set must be a mapping.")
    required_fields = (
        "bundle_set_version",
        "experiment_id",
        "processed_simulator_results_dir",
        "expected_arm_ids",
        "expected_seeds_by_arm_id",
        "expected_condition_signatures",
        "bundle_inventory",
        "bundle_records",
    )
    missing_fields = [field for field in required_fields if field not in bundle_set]
    if missing_fields:
        raise ValueError(f"bundle_set is missing required fields {missing_fields!r}.")
    return copy.deepcopy(dict(bundle_set))


def _normalize_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(summary, Mapping):
        raise ValueError("summary must be a mapping.")
    version = _normalize_nonempty_string(
        summary.get("summary_version"),
        field_name="summary.summary_version",
    )
    if version != EXPERIMENT_COMPARISON_SUMMARY_VERSION:
        raise ValueError(
            f"summary.summary_version must be {EXPERIMENT_COMPARISON_SUMMARY_VERSION!r}."
        )
    return copy.deepcopy(dict(summary))


def _validate_bundle_against_arm_plan(
    *,
    bundle_metadata: Mapping[str, Any],
    arm_plan: Mapping[str, Any],
    analysis_plan: Mapping[str, Any],
    experiment_id: str,
) -> None:
    normalized_metadata = parse_simulator_result_bundle_metadata(bundle_metadata)
    expected_arm_id = str(arm_plan["arm_reference"]["arm_id"])
    discovered_experiment_id = str(normalized_metadata["manifest_reference"]["experiment_id"])
    if discovered_experiment_id != experiment_id:
        raise ValueError(
            f"Discovered bundle {normalized_metadata['bundle_id']!r} belongs to experiment "
            f"{discovered_experiment_id!r}, expected {experiment_id!r}."
        )
    if str(normalized_metadata["arm_reference"]["arm_id"]) != expected_arm_id:
        raise ValueError(
            f"Discovered bundle {normalized_metadata['bundle_id']!r} belongs to arm_id "
            f"{normalized_metadata['arm_reference']['arm_id']!r}, expected {expected_arm_id!r}."
        )
    if str(normalized_metadata["arm_reference"]["model_mode"]) != str(
        arm_plan["arm_reference"]["model_mode"]
    ):
        raise ValueError(
            f"Discovered bundle {normalized_metadata['bundle_id']!r} has model_mode "
            f"{normalized_metadata['arm_reference']['model_mode']!r}, expected "
            f"{arm_plan['arm_reference']['model_mode']!r}."
        )
    if normalized_metadata["arm_reference"]["baseline_family"] != arm_plan["arm_reference"]["baseline_family"]:
        raise ValueError(
            f"Discovered bundle {normalized_metadata['bundle_id']!r} has baseline_family "
            f"{normalized_metadata['arm_reference']['baseline_family']!r}, expected "
            f"{arm_plan['arm_reference']['baseline_family']!r}."
        )
    if dict(normalized_metadata["timebase"]) != dict(arm_plan["runtime"]["timebase"]):
        raise ValueError(
            f"Discovered bundle {normalized_metadata['bundle_id']!r} has an incompatible "
            "timebase relative to the normalized simulation plan."
        )
    _validate_bundle_selected_assets(normalized_metadata, arm_plan)
    _validate_bundle_readout_inventory(
        bundle_metadata=normalized_metadata,
        analysis_plan=analysis_plan,
    )


def _validate_bundle_selected_assets(
    bundle_metadata: Mapping[str, Any],
    arm_plan: Mapping[str, Any],
) -> None:
    expected_assets = [
        _selected_asset_identity(item)
        for item in arm_plan["selected_assets"]
        if str(item["asset_role"]) not in _IGNORED_SELECTED_ASSET_ROLES
    ]
    discovered_assets = [
        _selected_asset_identity(item)
        for item in bundle_metadata["selected_assets"]
        if str(item["asset_role"]) not in _IGNORED_SELECTED_ASSET_ROLES
    ]
    if expected_assets != discovered_assets:
        raise ValueError(
            f"Discovered bundle {bundle_metadata['bundle_id']!r} does not match the "
            "normalized non-input selected-asset inventory for its arm plan."
        )


def _selected_asset_identity(asset: Mapping[str, Any]) -> tuple[str, str, str, str | None, str | None]:
    return (
        str(asset["asset_role"]),
        str(asset["artifact_type"]),
        str(Path(asset["path"]).resolve()),
        asset["artifact_id"],
        asset["bundle_id"],
    )


def _validate_bundle_readout_inventory(
    *,
    bundle_metadata: Mapping[str, Any],
    analysis_plan: Mapping[str, Any],
) -> None:
    readout_catalog_by_id = {
        str(item["readout_id"]): parse_simulator_readout_definition(item)
        for item in bundle_metadata["readout_catalog"]
    }
    for active_readout in analysis_plan["active_shared_readouts"]:
        readout_id = str(active_readout["readout_id"])
        discovered = readout_catalog_by_id.get(readout_id)
        if discovered is None:
            raise ValueError(
                f"Discovered bundle {bundle_metadata['bundle_id']!r} is missing active "
                f"shared readout_id {readout_id!r} required by the normalized analysis plan."
            )
        for field_name in (
            "aggregation",
            "scope",
            "units",
            "value_semantics",
        ):
            if str(discovered[field_name]) != str(active_readout[field_name]):
                raise ValueError(
                    f"Discovered bundle {bundle_metadata['bundle_id']!r} exposes readout_id "
                    f"{readout_id!r} with incompatible {field_name} "
                    f"{discovered[field_name]!r}; expected {active_readout[field_name]!r}."
                )


def _condition_groups_from_plan(
    analysis_plan: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in analysis_plan["condition_catalog"]:
        parameter_name = _normalize_identifier(
            item["parameter_name"],
            field_name="analysis_plan.condition_catalog.parameter_name",
        )
        groups.setdefault(parameter_name, []).append(copy.deepcopy(dict(item)))
    for values in groups.values():
        values.sort(key=lambda item: str(item["condition_id"]))
    return dict(sorted(groups.items()))


def _plan_requires_condition_labels(analysis_plan: Mapping[str, Any]) -> bool:
    for metric_definition in analysis_plan["active_metric_definitions"]:
        if str(metric_definition["metric_class"]) == WAVE_ONLY_DIAGNOSTIC_CLASS:
            continue
        return True
    return False


def _expected_condition_signatures(
    condition_groups: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    if not condition_groups:
        return [{"condition_ids": [], "condition_signature": "unlabeled"}]
    grouped_condition_ids = [
        [str(item["condition_id"]) for item in group]
        for _, group in sorted(condition_groups.items())
    ]
    signatures = []
    for combo in itertools.product(*grouped_condition_ids):
        condition_ids = sorted(str(item) for item in combo)
        signatures.append(
            {
                "condition_ids": condition_ids,
                "condition_signature": _condition_signature(condition_ids),
            }
        )
    signatures.sort(key=lambda item: str(item["condition_signature"]))
    return signatures


def _infer_bundle_conditions(
    *,
    bundle_metadata: Mapping[str, Any],
    condition_groups: Mapping[str, Sequence[Mapping[str, Any]]],
    requires_condition_labels: bool,
) -> dict[str, Any]:
    stimulus_asset = _find_input_asset(bundle_metadata, artifact_type="stimulus_bundle")
    if stimulus_asset is None:
        if requires_condition_labels:
            raise ValueError(
                f"Discovered bundle {bundle_metadata['bundle_id']!r} is missing its selected "
                "stimulus bundle metadata, so the workflow cannot infer analysis condition labels."
            )
        return {
            "condition_ids": [],
            "stimulus_family": None,
            "stimulus_name": None,
            "parameter_snapshot": None,
        }
    stimulus_metadata = load_stimulus_bundle_metadata(Path(stimulus_asset["path"]))
    parameter_snapshot = copy.deepcopy(dict(stimulus_metadata["parameter_snapshot"]))
    condition_ids: list[str] = []
    for parameter_name, candidates in sorted(condition_groups.items()):
        if parameter_name not in parameter_snapshot:
            raise ValueError(
                f"Stimulus bundle {stimulus_metadata['bundle_id']!r} for simulator bundle "
                f"{bundle_metadata['bundle_id']!r} is missing parameter {parameter_name!r} "
                "required by the normalized analysis condition catalog."
            )
        observed_value = parameter_snapshot[parameter_name]
        matched_condition_ids = [
            str(item["condition_id"])
            for item in candidates
            if _condition_value_matches(
                observed_value=observed_value,
                expected_value=item["value"],
            )
        ]
        if len(matched_condition_ids) != 1:
            raise ValueError(
                f"Stimulus bundle {stimulus_metadata['bundle_id']!r} for simulator bundle "
                f"{bundle_metadata['bundle_id']!r} matched condition ids "
                f"{matched_condition_ids!r} for parameter {parameter_name!r}; expected exactly one."
            )
        condition_ids.append(matched_condition_ids[0])
    return {
        "condition_ids": sorted(condition_ids),
        "stimulus_family": str(stimulus_metadata["stimulus_family"]),
        "stimulus_name": str(stimulus_metadata["stimulus_name"]),
        "parameter_snapshot": parameter_snapshot,
    }


def _condition_value_matches(*, observed_value: Any, expected_value: Any) -> bool:
    if isinstance(expected_value, str):
        return _normalize_identifier(
            observed_value,
            field_name="stimulus.parameter_snapshot.value",
        ) == _normalize_identifier(
            expected_value,
            field_name="analysis_plan.condition_catalog.value",
        )
    observed_float = _normalize_float(
        observed_value,
        field_name="stimulus.parameter_snapshot.value",
    )
    expected_float = _normalize_float(
        expected_value,
        field_name="analysis_plan.condition_catalog.value",
    )
    return math.isclose(
        float(observed_float),
        float(expected_float),
        rel_tol=0.0,
        abs_tol=_CONDITION_VALUE_TOLERANCE,
    )


def _find_input_asset(
    bundle_metadata: Mapping[str, Any],
    *,
    artifact_type: str,
) -> dict[str, Any] | None:
    normalized_artifact_type = _normalize_nonempty_string(
        artifact_type,
        field_name="artifact_type",
    )
    for item in bundle_metadata["selected_assets"]:
        if (
            str(item["asset_role"]) == "input_bundle"
            and str(item["artifact_type"]) == normalized_artifact_type
        ):
            return copy.deepcopy(dict(item))
    return None


def _validate_bundle_coverage(
    *,
    bundle_inventory: Sequence[Mapping[str, Any]],
    arm_ids: Sequence[str],
    expected_seeds_by_arm_id: Mapping[str, Sequence[int]],
    expected_condition_signatures: Sequence[Mapping[str, Any]],
    requires_condition_labels: bool,
) -> None:
    expected_condition_keys = [
        tuple(item["condition_ids"]) for item in expected_condition_signatures
    ]
    inventory_by_arm_seed: dict[tuple[str, int], set[tuple[str, ...]]] = {}
    for item in bundle_inventory:
        key = (str(item["arm_id"]), int(item["seed"]))
        inventory_by_arm_seed.setdefault(key, set()).add(tuple(item["condition_ids"]))
    for arm_id in arm_ids:
        expected_seeds = expected_seeds_by_arm_id.get(arm_id, [])
        for seed in expected_seeds:
            seen_conditions = inventory_by_arm_seed.get((arm_id, int(seed)), set())
            if requires_condition_labels:
                missing_conditions = [
                    list(condition_ids)
                    for condition_ids in expected_condition_keys
                    if condition_ids not in seen_conditions
                ]
                if missing_conditions:
                    raise ValueError(
                        f"Experiment bundle set is missing required condition coverage for "
                        f"arm_id {arm_id!r}, seed {seed!r}: {missing_conditions!r}."
                    )
            elif not seen_conditions:
                raise ValueError(
                    f"Experiment bundle set is missing any bundle coverage for arm_id {arm_id!r}, "
                    f"seed {seed!r}."
                )


def _subset_analysis_plan(
    analysis_plan: Mapping[str, Any],
    *,
    metric_ids: Sequence[str],
) -> dict[str, Any]:
    active_metric_ids = {
        _normalize_identifier(metric_id, field_name="metric_ids")
        for metric_id in metric_ids
    }
    return {
        "plan_version": str(analysis_plan["plan_version"]),
        "condition_catalog": copy.deepcopy(list(analysis_plan["condition_catalog"])),
        "condition_pair_catalog": copy.deepcopy(list(analysis_plan["condition_pair_catalog"])),
        "analysis_window_catalog": copy.deepcopy(list(analysis_plan["analysis_window_catalog"])),
        "metric_recipe_catalog": [
            copy.deepcopy(dict(item))
            for item in analysis_plan["metric_recipe_catalog"]
            if str(item["metric_id"]) in active_metric_ids
            and item["active_readout_ids"]
        ],
    }


def _wave_analysis_windows(analysis_plan: Mapping[str, Any]) -> list[dict[str, Any]] | None:
    windows_by_id = {
        str(item["window_id"]): copy.deepcopy(dict(item))
        for item in analysis_plan["analysis_window_catalog"]
    }
    requested_window_ids = sorted(
        {
            str(item["window_id"])
            for item in analysis_plan["metric_recipe_catalog"]
            if str(item["metric_id"]) in set(SUPPORTED_WAVE_STRUCTURE_METRIC_IDS)
        }
    )
    if not requested_window_ids:
        return None
    return [windows_by_id[window_id] for window_id in requested_window_ids]


def _comparable_metric_ids(analysis_plan: Mapping[str, Any]) -> set[str]:
    comparable: set[str] = set()
    for item in analysis_plan["active_metric_definitions"]:
        if str(item["metric_class"]) == WAVE_ONLY_DIAGNOSTIC_CLASS:
            continue
        comparable.add(str(item["metric_id"]))
    return comparable


def _combined_metric_rows(
    *,
    shared_result: Mapping[str, Any],
    task_result: Mapping[str, Any],
    wave_result: Mapping[str, Any],
) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    for source_name, result in (
        ("shared_readout_analysis", shared_result),
        ("task_decoder_analysis", task_result),
        ("wave_diagnostic_analysis", wave_result),
    ):
        for item in result.get("metric_rows", []):
            row = copy.deepcopy(dict(item))
            row["analysis_source"] = source_name
            combined.append(row)
    return combined


def _combined_group_catalog(analysis_plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = [
        copy.deepcopy(dict(item)) for item in analysis_plan["arm_pair_catalog"]
    ] + [
        copy.deepcopy(dict(item)) for item in analysis_plan["comparison_group_catalog"]
    ]
    records.sort(key=lambda item: str(item["group_id"]))
    return records


def _expected_seeds_by_group_id(
    *,
    analysis_plan: Mapping[str, Any],
    bundle_set: Mapping[str, Any],
) -> dict[str, list[int]]:
    seeds_by_arm_id = {
        str(arm_id): [int(seed) for seed in seeds]
        for arm_id, seeds in bundle_set["expected_seeds_by_arm_id"].items()
    }
    seeds_by_group_id: dict[str, list[int]] = {}
    for item in analysis_plan["arm_pair_catalog"]:
        baseline_arm_id = str(item["baseline_arm_id"])
        surface_wave_arm_id = str(item["surface_wave_arm_id"])
        baseline_seeds = seeds_by_arm_id.get(baseline_arm_id, [])
        surface_wave_seeds = seeds_by_arm_id.get(surface_wave_arm_id, [])
        if baseline_seeds != surface_wave_seeds:
            raise ValueError(
                f"Matched arm-pair group {item['group_id']!r} has incompatible seed coverage: "
                f"{baseline_arm_id!r} -> {baseline_seeds!r}, "
                f"{surface_wave_arm_id!r} -> {surface_wave_seeds!r}."
            )
        seeds_by_group_id[str(item["group_id"])] = list(baseline_seeds)
    groups_by_id = {
        str(item["group_id"]): item for item in analysis_plan["comparison_group_catalog"]
    }
    changed = True
    while changed:
        changed = False
        for group_id, group in groups_by_id.items():
            if group_id in seeds_by_group_id:
                continue
            component_group_ids = [
                str(component_group_id)
                for component_group_id in group.get("component_group_ids", [])
            ]
            if not component_group_ids:
                seeds_by_group_id[group_id] = []
                changed = True
                continue
            if any(component_group_id not in seeds_by_group_id for component_group_id in component_group_ids):
                continue
            component_seeds = [tuple(seeds_by_group_id[component_group_id]) for component_group_id in component_group_ids]
            if len(set(component_seeds)) != 1:
                raise ValueError(
                    f"Derived comparison group {group_id!r} has incompatible seed coverage across "
                    f"component groups {component_group_ids!r}."
                )
            seeds_by_group_id[group_id] = list(component_seeds[0])
            changed = True
    missing_group_ids = sorted(
        set(groups_by_id) - set(seeds_by_group_id)
    )
    if missing_group_ids:
        raise ValueError(
            f"Could not resolve expected seed coverage for derived comparison groups "
            f"{missing_group_ids!r}."
        )
    return seeds_by_group_id


def _index_metric_rows_by_arm_seed_key(
    *,
    metric_rows: Sequence[Mapping[str, Any]],
    comparable_metric_ids: set[str],
) -> dict[tuple[str, int], dict[tuple[Any, ...], dict[str, Any]]]:
    index: dict[tuple[str, int], dict[tuple[Any, ...], dict[str, Any]]] = {}
    for item in metric_rows:
        metric_id = str(item["metric_id"])
        if metric_id not in comparable_metric_ids:
            continue
        arm_id = str(item["arm_id"])
        seed = int(item["seed"])
        key = _metric_row_identity(item)
        index.setdefault((arm_id, seed), {})
        if key in index[(arm_id, seed)]:
            raise ValueError(
                f"Experiment comparison analysis found duplicate metric coverage for arm_id "
                f"{arm_id!r}, seed {seed!r}, and metric identity {key!r}."
            )
        index[(arm_id, seed)][key] = copy.deepcopy(dict(item))
    return index


def _build_matched_pair_detail_rows(
    *,
    analysis_plan: Mapping[str, Any],
    expected_seeds_by_group_id: Mapping[str, Sequence[int]],
    metric_rows_by_arm_seed_key: Mapping[tuple[str, int], Mapping[tuple[Any, ...], Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in analysis_plan["arm_pair_catalog"]:
        group_id = str(group["group_id"])
        baseline_arm_id = str(group["baseline_arm_id"])
        surface_wave_arm_id = str(group["surface_wave_arm_id"])
        for seed in expected_seeds_by_group_id[group_id]:
            baseline_rows = metric_rows_by_arm_seed_key.get((baseline_arm_id, int(seed)))
            surface_wave_rows = metric_rows_by_arm_seed_key.get((surface_wave_arm_id, int(seed)))
            if not baseline_rows:
                raise ValueError(
                    f"Comparison group {group_id!r} is missing baseline metric rows for "
                    f"arm_id {baseline_arm_id!r} seed {seed!r}."
                )
            if not surface_wave_rows:
                raise ValueError(
                    f"Comparison group {group_id!r} is missing surface-wave metric rows for "
                    f"arm_id {surface_wave_arm_id!r} seed {seed!r}."
                )
            baseline_keys = set(baseline_rows)
            surface_wave_keys = set(surface_wave_rows)
            if baseline_keys != surface_wave_keys:
                raise ValueError(
                    f"Comparison group {group_id!r} has incompatible metric/readout coverage "
                    f"between arm_id {baseline_arm_id!r} and arm_id {surface_wave_arm_id!r} "
                    f"for seed {seed!r}."
                )
            for metric_key in sorted(baseline_keys):
                baseline_row = baseline_rows[metric_key]
                surface_wave_row = surface_wave_rows[metric_key]
                if str(baseline_row["units"]) != str(surface_wave_row["units"]):
                    raise ValueError(
                        f"Comparison group {group_id!r} metric {baseline_row['metric_id']!r} has "
                        "incompatible units between matched arms."
                    )
                rows.append(
                    {
                        "group_id": group_id,
                        "group_kind": str(group["group_kind"]),
                        "comparison_semantics": str(group["comparison_semantics"]),
                        "metric_id": str(baseline_row["metric_id"]),
                        "readout_id": str(baseline_row["readout_id"]),
                        "window_id": str(baseline_row["window_id"]),
                        "statistic": str(baseline_row["statistic"]),
                        "condition_pair_id": baseline_row.get("condition_pair_id"),
                        "pairing_key": baseline_row.get("pairing_key"),
                        "condition_signature": baseline_row.get("condition_signature"),
                        "decoder_id": baseline_row.get("decoder_id"),
                        "root_id": baseline_row.get("root_id"),
                        "units": str(baseline_row["units"]),
                        "seed": int(seed),
                        "baseline_family": str(group["baseline_family"]),
                        "topology_condition": str(group["topology_condition"]),
                        "value": _rounded_float(
                            float(surface_wave_row["value"]) - float(baseline_row["value"])
                        ),
                        "component_values": {
                            "baseline": _rounded_float(float(baseline_row["value"])),
                            "surface_wave": _rounded_float(float(surface_wave_row["value"])),
                        },
                        "component_group_ids": [],
                    }
                )
    return rows


def _build_derived_detail_rows(
    *,
    analysis_plan: Mapping[str, Any],
    detail_rows_by_group_id: Mapping[str, Sequence[Mapping[str, Any]]],
    expected_seeds_by_group_id: Mapping[str, Sequence[int]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in analysis_plan["comparison_group_catalog"]:
        group_id = str(group["group_id"])
        component_group_ids = [str(item) for item in group["component_group_ids"]]
        component_indices = {
            component_group_id: _index_detail_rows_by_seed_and_identity(
                detail_rows_by_group_id.get(component_group_id, [])
            )
            for component_group_id in component_group_ids
        }
        for seed in expected_seeds_by_group_id[group_id]:
            missing_component_groups = [
                component_group_id
                for component_group_id, index in component_indices.items()
                if int(seed) not in index
            ]
            if missing_component_groups:
                raise ValueError(
                    f"Derived comparison group {group_id!r} is missing component coverage for "
                    f"seed {seed!r}: {missing_component_groups!r}."
                )
            reference_keys = set(component_indices[component_group_ids[0]][int(seed)])
            for component_group_id in component_group_ids[1:]:
                if set(component_indices[component_group_id][int(seed)]) != reference_keys:
                    raise ValueError(
                        f"Derived comparison group {group_id!r} has incompatible detail-row "
                        f"coverage across component groups {component_group_ids!r} for seed {seed!r}."
                    )
            for detail_key in sorted(reference_keys):
                component_rows = {
                    component_group_id: component_indices[component_group_id][int(seed)][detail_key]
                    for component_group_id in component_group_ids
                }
                first_row = component_rows[component_group_ids[0]]
                if str(group["group_kind"]) == "geometry_ablation":
                    intact_row = component_rows[component_group_ids[0]]
                    shuffled_row = component_rows[component_group_ids[1]]
                    rows.append(
                        _derived_detail_row(
                            group=group,
                            seed=int(seed),
                            template_row=first_row,
                            value=_rounded_float(
                                float(intact_row["value"]) - float(shuffled_row["value"])
                            ),
                            component_values={
                                "intact": _rounded_float(float(intact_row["value"])),
                                "shuffled": _rounded_float(float(shuffled_row["value"])),
                            },
                            component_group_ids=component_group_ids,
                        )
                    )
                elif str(group["group_kind"]) == "baseline_strength_challenge":
                    p0_row = component_rows[component_group_ids[0]]
                    p1_row = component_rows[component_group_ids[1]]
                    rows.append(
                        _derived_detail_row(
                            group=group,
                            seed=int(seed),
                            template_row=first_row,
                            value=_rounded_float(float(p1_row["value"])),
                            component_values={
                                "p0_reference": _rounded_float(float(p0_row["value"])),
                                "p1_challenge": _rounded_float(float(p1_row["value"])),
                                "delta_from_reference": _rounded_float(
                                    float(p1_row["value"]) - float(p0_row["value"])
                                ),
                            },
                            component_group_ids=component_group_ids,
                        )
                    )
                else:
                    raise ValueError(
                        f"Unsupported derived comparison group_kind {group['group_kind']!r}."
                    )
    return rows


def _index_detail_rows_by_seed_and_identity(
    rows: Sequence[Mapping[str, Any]],
) -> dict[int, dict[tuple[Any, ...], dict[str, Any]]]:
    index: dict[int, dict[tuple[Any, ...], dict[str, Any]]] = {}
    for item in rows:
        seed = int(item["seed"])
        detail_key = _comparison_detail_identity(item)
        index.setdefault(seed, {})
        if detail_key in index[seed]:
            raise ValueError(
                f"Derived comparison construction found duplicate detail coverage for seed "
                f"{seed!r} and identity {detail_key!r}."
            )
        index[seed][detail_key] = copy.deepcopy(dict(item))
    return index


def _derived_detail_row(
    *,
    group: Mapping[str, Any],
    seed: int,
    template_row: Mapping[str, Any],
    value: float,
    component_values: Mapping[str, float],
    component_group_ids: Sequence[str],
) -> dict[str, Any]:
    return {
        "group_id": str(group["group_id"]),
        "group_kind": str(group["group_kind"]),
        "comparison_semantics": str(group["comparison_semantics"]),
        "metric_id": str(template_row["metric_id"]),
        "readout_id": str(template_row["readout_id"]),
        "window_id": str(template_row["window_id"]),
        "statistic": str(template_row["statistic"]),
        "condition_pair_id": template_row.get("condition_pair_id"),
        "pairing_key": template_row.get("pairing_key"),
        "condition_signature": template_row.get("condition_signature"),
        "decoder_id": template_row.get("decoder_id"),
        "root_id": template_row.get("root_id"),
        "units": str(template_row["units"]),
        "seed": int(seed),
        "baseline_family": group.get("baseline_family"),
        "topology_condition": group.get("topology_condition"),
        "value": value,
        "component_values": copy.deepcopy(dict(component_values)),
        "component_group_ids": list(component_group_ids),
    }


def _build_group_metric_seed_rows(
    comparison_detail_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    for item in comparison_detail_rows:
        key = (str(item["group_id"]), str(item["metric_id"]), int(item["seed"]))
        grouped.setdefault(key, []).append(copy.deepcopy(dict(item)))
    rows: list[dict[str, Any]] = []
    for (group_id, metric_id, seed), items in grouped.items():
        template = items[0]
        values = np.asarray([float(item["value"]) for item in items], dtype=np.float64)
        component_names = sorted(
            {
                str(component_name)
                for item in items
                for component_name in item.get("component_values", {})
            }
        )
        component_values = {
            component_name: _rounded_float(
                float(
                    np.mean(
                        [
                            float(item["component_values"][component_name])
                            for item in items
                            if component_name in item.get("component_values", {})
                        ],
                        dtype=np.float64,
                    )
                )
            )
            for component_name in component_names
        }
        rows.append(
            {
                "group_id": group_id,
                "group_kind": str(template["group_kind"]),
                "comparison_semantics": str(template["comparison_semantics"]),
                "metric_id": metric_id,
                "readout_id": str(template["readout_id"]),
                "window_id": str(template["window_id"]),
                "statistic": str(template["statistic"]),
                "units": str(template["units"]),
                "seed": int(seed),
                "baseline_family": template.get("baseline_family"),
                "topology_condition": template.get("topology_condition"),
                "value": _rounded_float(float(np.mean(values, dtype=np.float64))),
                "component_values": component_values,
                "source_detail_count": len(items),
                "source_condition_signatures": sorted(
                    {
                        str(item["condition_signature"])
                        for item in items
                        if item.get("condition_signature") is not None
                    }
                ),
                "source_pairing_keys": sorted(
                    {
                        str(item["pairing_key"])
                        for item in items
                        if item.get("pairing_key") is not None
                    }
                ),
                "source_component_group_ids": list(template.get("component_group_ids", [])),
            }
        )
    return rows


def _build_group_metric_rollups(
    *,
    group_metric_seed_rows: Sequence[Mapping[str, Any]],
    expected_seeds_by_group_id: Mapping[str, Sequence[int]],
    analysis_plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rule_by_id = {
        str(item["rule_id"]): copy.deepcopy(dict(item))
        for item in analysis_plan["seed_aggregation_rules"]
    }
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in group_metric_seed_rows:
        grouped.setdefault(
            (str(item["group_id"]), str(item["metric_id"])),
            [],
        ).append(copy.deepcopy(dict(item)))
    rows: list[dict[str, Any]] = []
    for (group_id, metric_id), items in grouped.items():
        items.sort(key=lambda item: int(item["seed"]))
        expected_seeds = [int(seed) for seed in expected_seeds_by_group_id[group_id]]
        if [int(item["seed"]) for item in items] != expected_seeds:
            raise ValueError(
                f"Experiment comparison aggregation requires complete seed coverage for "
                f"group_id {group_id!r} metric_id {metric_id!r}; expected {expected_seeds!r}, "
                f"got {[int(item['seed']) for item in items]!r}."
            )
        values = np.asarray([float(item["value"]) for item in items], dtype=np.float64)
        component_names = sorted(
            {
                str(component_name)
                for item in items
                for component_name in item.get("component_values", {})
            }
        )
        component_stats = {
            component_name: _summary_statistics(
                np.asarray(
                    [float(item["component_values"][component_name]) for item in items],
                    dtype=np.float64,
                )
            )
            for component_name in component_names
        }
        signs = [_value_sign(float(item["value"])) for item in items]
        sign_consistency = len({sign for sign in signs if sign != "zero"}) <= 1
        aggregation_rule_id = (
            MANIFEST_SEED_SWEEP_ROLLUP_RULE_ID
            if len(expected_seeds) > 1
            else PER_RUN_SINGLE_SEED_RULE_ID
        )
        if aggregation_rule_id not in rule_by_id:
            raise ValueError(
                f"Missing seed aggregation rule {aggregation_rule_id!r} required for "
                f"group_id {group_id!r}."
            )
        template = items[0]
        rows.append(
            {
                "group_id": group_id,
                "group_kind": str(template["group_kind"]),
                "comparison_semantics": str(template["comparison_semantics"]),
                "metric_id": metric_id,
                "readout_id": str(template["readout_id"]),
                "window_id": str(template["window_id"]),
                "statistic": str(template["statistic"]),
                "units": str(template["units"]),
                "seed_aggregation_rule_id": aggregation_rule_id,
                "seed_count": len(expected_seeds),
                "seeds": expected_seeds,
                "baseline_family": template.get("baseline_family"),
                "topology_condition": template.get("topology_condition"),
                "summary_statistics": _summary_statistics(values),
                "component_statistics": component_stats,
                "sign_consistency": bool(sign_consistency),
                "effect_direction": _value_sign(float(np.mean(values, dtype=np.float64))),
            }
        )
    return rows


def _summary_statistics(values: np.ndarray) -> dict[str, float]:
    if values.ndim != 1 or values.size < 1:
        raise ValueError("summary statistics require a non-empty 1D array.")
    return {
        "mean": _rounded_float(float(np.mean(values, dtype=np.float64))),
        "median": _rounded_float(float(np.median(values))),
        "min": _rounded_float(float(np.min(values))),
        "max": _rounded_float(float(np.max(values))),
        "std": _rounded_float(float(np.std(values, dtype=np.float64))),
    }


def _build_wave_metric_seed_rows(
    metric_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    for item in metric_rows:
        key = (str(item["arm_id"]), str(item["metric_id"]), int(item["seed"]))
        grouped.setdefault(key, []).append(copy.deepcopy(dict(item)))
    rows: list[dict[str, Any]] = []
    for (arm_id, metric_id, seed), items in grouped.items():
        values = np.asarray([float(item["value"]) for item in items], dtype=np.float64)
        rows.append(
            {
                "arm_id": arm_id,
                "metric_id": metric_id,
                "seed": int(seed),
                "value": _rounded_float(float(np.mean(values, dtype=np.float64))),
                "units": str(items[0]["units"]),
                "source_row_count": len(items),
            }
        )
    return rows


def _build_wave_metric_rollups(
    wave_metric_seed_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in wave_metric_seed_rows:
        grouped.setdefault((str(item["arm_id"]), str(item["metric_id"])), []).append(
            copy.deepcopy(dict(item))
        )
    rows: list[dict[str, Any]] = []
    for (arm_id, metric_id), items in grouped.items():
        items.sort(key=lambda item: int(item["seed"]))
        values = np.asarray([float(item["value"]) for item in items], dtype=np.float64)
        rows.append(
            {
                "arm_id": arm_id,
                "metric_id": metric_id,
                "seed_count": len(items),
                "seeds": [int(item["seed"]) for item in items],
                "units": str(items[0]["units"]),
                "summary_statistics": _summary_statistics(values),
            }
        )
    return rows


def _evaluate_null_tests(
    *,
    analysis_plan: Mapping[str, Any],
    group_metric_seed_rows: Sequence[Mapping[str, Any]],
    group_metric_rollups: Sequence[Mapping[str, Any]],
    shared_result: Mapping[str, Any],
    task_result: Mapping[str, Any],
    wave_result: Mapping[str, Any],
) -> list[dict[str, Any]]:
    seed_rows_by_group_metric: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in group_metric_seed_rows:
        seed_rows_by_group_metric.setdefault(
            (str(item["group_id"]), str(item["metric_id"])),
            [],
        ).append(copy.deepcopy(dict(item)))
    rollups_by_group_metric = {
        (str(item["group_id"]), str(item["metric_id"])): copy.deepcopy(dict(item))
        for item in group_metric_rollups
    }
    shared_metric_rows = [copy.deepcopy(dict(item)) for item in shared_result.get("metric_rows", [])]
    task_metric_rows = [copy.deepcopy(dict(item)) for item in task_result.get("metric_rows", [])]
    wave_diagnostic_summaries = [
        copy.deepcopy(dict(item)) for item in wave_result.get("diagnostic_summaries", [])
    ]

    results: list[dict[str, Any]] = []
    for declaration in analysis_plan["null_test_declarations"]:
        null_test_id = str(declaration["null_test_id"])
        if null_test_id == "geometry_shuffle_collapse":
            results.append(
                _evaluate_geometry_shuffle_collapse(
                    declaration=declaration,
                    rollups_by_group_metric=rollups_by_group_metric,
                )
            )
        elif null_test_id == "stronger_baseline_survival":
            results.append(
                _evaluate_stronger_baseline_survival(
                    declaration=declaration,
                    rollups_by_group_metric=rollups_by_group_metric,
                )
            )
        elif null_test_id == "seed_stability":
            results.append(
                _evaluate_seed_stability(
                    declaration=declaration,
                    seed_rows_by_group_metric=seed_rows_by_group_metric,
                )
            )
        elif null_test_id == "polarity_label_swap":
            results.append(
                _evaluate_polarity_label_swap(
                    declaration=declaration,
                    shared_metric_rows=shared_metric_rows,
                )
            )
        elif null_test_id == "direction_label_swap":
            results.append(
                _evaluate_direction_label_swap(
                    declaration=declaration,
                    task_metric_rows=task_metric_rows,
                )
            )
        elif null_test_id == "wave_artifact_presence_guard":
            results.append(
                _evaluate_wave_artifact_presence_guard(
                    declaration=declaration,
                    wave_diagnostic_summaries=wave_diagnostic_summaries,
                )
            )
        else:
            raise ValueError(f"Unsupported null_test_id {null_test_id!r}.")
    return results


def _evaluate_geometry_shuffle_collapse(
    *,
    declaration: Mapping[str, Any],
    rollups_by_group_metric: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    metric_outcomes: list[dict[str, Any]] = []
    for group_id in declaration["comparison_group_ids"]:
        for metric_id in declaration["required_metric_ids"]:
            rollup = rollups_by_group_metric.get((str(group_id), str(metric_id)))
            if rollup is None:
                metric_outcomes.append(
                    {
                        "group_id": str(group_id),
                        "metric_id": str(metric_id),
                        "status": "unavailable",
                        "reason": "missing_group_metric_rollup",
                    }
                )
                continue
            intact_mean = rollup["component_statistics"].get("intact", {}).get("mean")
            shuffled_mean = rollup["component_statistics"].get("shuffled", {}).get("mean")
            if intact_mean is None or shuffled_mean is None:
                metric_outcomes.append(
                    {
                        "group_id": str(group_id),
                        "metric_id": str(metric_id),
                        "status": "unavailable",
                        "reason": "missing_component_statistics",
                    }
                )
                continue
            passed = abs(float(intact_mean)) > abs(float(shuffled_mean)) + _EFFECT_ABS_TOLERANCE
            metric_outcomes.append(
                {
                    "group_id": str(group_id),
                    "metric_id": str(metric_id),
                    "status": "pass" if passed else "fail",
                    "intact_mean": intact_mean,
                    "shuffled_mean": shuffled_mean,
                    "geometry_gap_mean": rollup["summary_statistics"]["mean"],
                }
            )
    return _null_test_result(
        declaration=declaration,
        metric_outcomes=metric_outcomes,
    )


def _evaluate_stronger_baseline_survival(
    *,
    declaration: Mapping[str, Any],
    rollups_by_group_metric: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    metric_outcomes: list[dict[str, Any]] = []
    for group_id in declaration["comparison_group_ids"]:
        for metric_id in declaration["required_metric_ids"]:
            rollup = rollups_by_group_metric.get((str(group_id), str(metric_id)))
            if rollup is None:
                metric_outcomes.append(
                    {
                        "group_id": str(group_id),
                        "metric_id": str(metric_id),
                        "status": "unavailable",
                        "reason": "missing_group_metric_rollup",
                    }
                )
                continue
            p0_mean = rollup["component_statistics"].get("p0_reference", {}).get("mean")
            p1_mean = rollup["component_statistics"].get("p1_challenge", {}).get("mean")
            if p0_mean is None or p1_mean is None:
                metric_outcomes.append(
                    {
                        "group_id": str(group_id),
                        "metric_id": str(metric_id),
                        "status": "unavailable",
                        "reason": "missing_component_statistics",
                    }
                )
                continue
            both_collapsed = (
                abs(float(p0_mean)) <= _EFFECT_ABS_TOLERANCE
                and abs(float(p1_mean)) <= _EFFECT_ABS_TOLERANCE
            )
            same_sign = _same_effect_direction(float(p0_mean), float(p1_mean))
            survives = both_collapsed or (
                abs(float(p1_mean)) > _EFFECT_ABS_TOLERANCE and same_sign
            )
            metric_outcomes.append(
                {
                    "group_id": str(group_id),
                    "metric_id": str(metric_id),
                    "status": "pass" if survives else "fail",
                    "p0_reference_mean": p0_mean,
                    "p1_challenge_mean": p1_mean,
                    "delta_from_reference_mean": rollup["component_statistics"]["delta_from_reference"]["mean"],
                    "both_collapsed": bool(both_collapsed),
                }
            )
    return _null_test_result(
        declaration=declaration,
        metric_outcomes=metric_outcomes,
    )


def _evaluate_seed_stability(
    *,
    declaration: Mapping[str, Any],
    seed_rows_by_group_metric: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    metric_outcomes: list[dict[str, Any]] = []
    for group_id in declaration["comparison_group_ids"]:
        for metric_id in declaration["required_metric_ids"]:
            seed_rows = list(seed_rows_by_group_metric.get((str(group_id), str(metric_id)), []))
            if not seed_rows:
                metric_outcomes.append(
                    {
                        "group_id": str(group_id),
                        "metric_id": str(metric_id),
                        "status": "unavailable",
                        "reason": "missing_seed_rows",
                    }
                )
                continue
            nonzero_signs = {
                _value_sign(float(item["value"])) for item in seed_rows if _value_sign(float(item["value"])) != "zero"
            }
            consistent = bool(nonzero_signs) and len(nonzero_signs) == 1
            metric_outcomes.append(
                {
                    "group_id": str(group_id),
                    "metric_id": str(metric_id),
                    "status": "pass" if consistent else "fail",
                    "seed_values": [
                        {
                            "seed": int(item["seed"]),
                            "value": item["value"],
                        }
                        for item in seed_rows
                    ],
                }
            )
    return _null_test_result(
        declaration=declaration,
        metric_outcomes=metric_outcomes,
    )


def _evaluate_polarity_label_swap(
    *,
    declaration: Mapping[str, Any],
    shared_metric_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    relevant_rows = [
        copy.deepcopy(dict(item))
        for item in shared_metric_rows
        if str(item["metric_id"]) == "on_off_selectivity_index"
    ]
    status = "pass" if relevant_rows else "unavailable"
    metric_outcomes = [
        {
            "group_id": None,
            "metric_id": "on_off_selectivity_index",
            "status": status,
            "observed_row_count": len(relevant_rows),
        }
    ]
    return _null_test_result(declaration=declaration, metric_outcomes=metric_outcomes)


def _evaluate_direction_label_swap(
    *,
    declaration: Mapping[str, Any],
    task_metric_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    relevant_rows = [
        copy.deepcopy(dict(item))
        for item in task_metric_rows
        if str(item["metric_id"]) in set(declaration["required_metric_ids"])
    ]
    status = "pass" if relevant_rows else "unavailable"
    metric_outcomes = [
        {
            "group_id": None,
            "metric_id": metric_id,
            "status": status,
            "observed_row_count": len(
                [item for item in relevant_rows if str(item["metric_id"]) == str(metric_id)]
            ),
        }
        for metric_id in declaration["required_metric_ids"]
    ]
    return _null_test_result(declaration=declaration, metric_outcomes=metric_outcomes)


def _evaluate_wave_artifact_presence_guard(
    *,
    declaration: Mapping[str, Any],
    wave_diagnostic_summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    unavailable_count = sum(
        1 for item in wave_diagnostic_summaries if str(item["status"]) != "ok"
    )
    metric_outcomes = [
        {
            "group_id": None,
            "metric_id": metric_id,
            "status": "pass",
            "unavailable_summary_count": unavailable_count,
        }
        for metric_id in declaration["required_metric_ids"]
    ]
    return _null_test_result(declaration=declaration, metric_outcomes=metric_outcomes)


def _null_test_result(
    *,
    declaration: Mapping[str, Any],
    metric_outcomes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    statuses = [str(item["status"]) for item in metric_outcomes]
    if statuses and all(status == "pass" for status in statuses):
        overall_status = "pass"
    elif any(status == "fail" for status in statuses):
        overall_status = "fail"
    else:
        overall_status = "unavailable"
    return {
        "null_test_id": str(declaration["null_test_id"]),
        "display_name": str(declaration["display_name"]),
        "description": str(declaration["description"]),
        "pass_criterion": str(declaration["pass_criterion"]),
        "seed_aggregation_rule_id": str(declaration["seed_aggregation_rule_id"]),
        "comparison_group_ids": list(declaration["comparison_group_ids"]),
        "required_metric_ids": list(declaration["required_metric_ids"]),
        "status": overall_status,
        "metric_outcomes": [copy.deepcopy(dict(item)) for item in metric_outcomes],
    }


def _build_task_scores(
    *,
    analysis_plan: Mapping[str, Any],
    group_metric_rollups: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rollups_by_group_metric = {
        (str(item["group_id"]), str(item["metric_id"])): copy.deepcopy(dict(item))
        for item in group_metric_rollups
    }
    score_rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    for request in analysis_plan["manifest_metric_requests"]:
        requested_metric_id = str(request["requested_metric_id"])
        resolved_metric_ids = [str(metric_id) for metric_id in request["resolved_metric_ids"]]
        if len(resolved_metric_ids) == 1:
            metric_id = resolved_metric_ids[0]
            for group_id in request["comparison_group_ids"]:
                rollup = rollups_by_group_metric.get((str(group_id), metric_id))
                if rollup is None:
                    raise ValueError(
                        f"Manifest metric request {requested_metric_id!r} requires group_id "
                        f"{group_id!r} metric_id {metric_id!r}, but no experiment-level rollup "
                        "was available."
                    )
                score_rows.append(
                    {
                        "score_id": f"{requested_metric_id}__{group_id}",
                        "requested_metric_id": requested_metric_id,
                        "recipe_kind": str(request["recipe_kind"]),
                        "group_id": str(group_id),
                        "group_kind": str(rollup["group_kind"]),
                        "metric_id": metric_id,
                        "seed_aggregation_rule_id": str(request["seed_aggregation_rule_id"]),
                        "value": rollup["summary_statistics"]["mean"],
                        "units": str(rollup["units"]),
                        "effect_direction": str(rollup["effect_direction"]),
                        "component_statistics": copy.deepcopy(
                            dict(rollup["component_statistics"])
                        ),
                        "summary_statistics": copy.deepcopy(
                            dict(rollup["summary_statistics"])
                        ),
                    }
                )
            continue
        family_components = []
        for metric_id in resolved_metric_ids:
            for group_id in request["comparison_group_ids"]:
                rollup = rollups_by_group_metric.get((str(group_id), str(metric_id)))
                if rollup is None:
                    continue
                family_components.append(
                    {
                        "group_id": str(group_id),
                        "metric_id": str(metric_id),
                        "group_kind": str(rollup["group_kind"]),
                        "value": rollup["summary_statistics"]["mean"],
                        "units": str(rollup["units"]),
                    }
                )
        family_rows.append(
            {
                "requested_metric_id": requested_metric_id,
                "recipe_kind": str(request["recipe_kind"]),
                "resolved_metric_ids": resolved_metric_ids,
                "comparison_group_ids": list(request["comparison_group_ids"]),
                "seed_aggregation_rule_id": str(request["seed_aggregation_rule_id"]),
                "component_scores": family_components,
            }
        )
    return score_rows, family_rows


def _build_milestone_1_decision_panel(
    *,
    analysis_plan: Mapping[str, Any],
    task_scores: Sequence[Mapping[str, Any]],
    null_test_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    primary_metric_id = str(
        _require_mapping(
            analysis_plan["manifest_reference"],
            field_name="analysis_plan.manifest_reference",
        ).get("experiment_id")
    )
    del primary_metric_id
    primary_request = analysis_plan["manifest_metric_requests"][0]
    requested_primary_metric_id = str(primary_request["requested_metric_id"])
    primary_scores = [
        copy.deepcopy(dict(item))
        for item in task_scores
        if str(item["requested_metric_id"]) == requested_primary_metric_id
    ]
    primary_score = (
        sorted(primary_scores, key=_task_score_priority_key)[0]
        if primary_scores
        else None
    )
    null_test_by_id = {
        str(item["null_test_id"]): copy.deepcopy(dict(item)) for item in null_test_results
    }
    decision_items = [
        {
            "item_id": "m1_nonzero_shared_output_effect",
            "status": (
                "pass"
                if primary_score is not None
                and abs(float(primary_score["value"])) > _EFFECT_ABS_TOLERANCE
                else "fail"
                if primary_score is not None
                else "unavailable"
            ),
            "evidence": None if primary_score is None else copy.deepcopy(dict(primary_score)),
        },
        {
            "item_id": "m1_geometry_dependence",
            "status": null_test_by_id.get("geometry_shuffle_collapse", {}).get(
                "status", "unavailable"
            ),
            "evidence": copy.deepcopy(
                null_test_by_id.get("geometry_shuffle_collapse", {})
            ),
        },
        {
            "item_id": "m1_survives_stronger_baseline",
            "status": null_test_by_id.get("stronger_baseline_survival", {}).get(
                "status", "unavailable"
            ),
            "evidence": copy.deepcopy(
                null_test_by_id.get("stronger_baseline_survival", {})
            ),
        },
        {
            "item_id": "m1_seed_parameter_stability",
            "status": null_test_by_id.get("seed_stability", {}).get(
                "status", "unavailable"
            ),
            "evidence": copy.deepcopy(null_test_by_id.get("seed_stability", {})),
        },
    ]
    overall_status = (
        "pass"
        if decision_items and all(item["status"] == "pass" for item in decision_items)
        else "fail"
        if any(item["status"] == "fail" for item in decision_items)
        else "unavailable"
    )
    return {
        "output_id": MILESTONE_1_DECISION_PANEL_OUTPUT_ID,
        "required_all": True,
        "overall_status": overall_status,
        "primary_requested_metric_id": requested_primary_metric_id,
        "primary_score": primary_score,
        "decision_items": decision_items,
    }


def _build_output_summaries(
    *,
    analysis_plan: Mapping[str, Any],
    group_metric_rollups: Sequence[Mapping[str, Any]],
    wave_metric_rollups: Sequence[Mapping[str, Any]],
    task_scores: Sequence[Mapping[str, Any]],
    task_score_families: Sequence[Mapping[str, Any]],
    null_test_results: Sequence[Mapping[str, Any]],
    decision_panel: Mapping[str, Any],
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    rollups_by_metric = {}
    for item in group_metric_rollups:
        rollups_by_metric.setdefault(str(item["metric_id"]), []).append(copy.deepcopy(dict(item)))
    for output_id in analysis_plan["active_output_ids"]:
        normalized_output_id = _normalize_identifier(output_id, field_name="output_id")
        output_definition = get_experiment_comparison_output_definition(normalized_output_id)
        if normalized_output_id == NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID:
            outputs.append(
                {
                    "output_id": normalized_output_id,
                    "output_kind": str(output_definition["output_kind"]),
                    "metric_rollups": rollups_by_metric.get(
                        "null_direction_suppression_index", []
                    ),
                }
            )
        elif normalized_output_id == LATENCY_SHIFT_COMPARISON_OUTPUT_ID:
            outputs.append(
                {
                    "output_id": normalized_output_id,
                    "output_kind": str(output_definition["output_kind"]),
                    "metric_rollups": rollups_by_metric.get(
                        "response_latency_to_peak_ms", []
                    ),
                }
            )
        elif normalized_output_id == WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID:
            outputs.append(
                {
                    "output_id": normalized_output_id,
                    "output_kind": str(output_definition["output_kind"]),
                    "wave_metric_rollups": copy.deepcopy(list(wave_metric_rollups)),
                }
            )
        elif normalized_output_id == MILESTONE_1_DECISION_PANEL_OUTPUT_ID:
            outputs.append(copy.deepcopy(dict(decision_panel)))
        elif normalized_output_id == ANALYSIS_UI_PAYLOAD_OUTPUT_ID:
            outputs.append(
                {
                    "output_id": normalized_output_id,
                    "output_kind": str(output_definition["output_kind"]),
                    "shared_comparison": {
                        "task_scores": [copy.deepcopy(dict(item)) for item in task_scores],
                        "task_score_families": [
                            copy.deepcopy(dict(item)) for item in task_score_families
                        ],
                        "null_test_results": [
                            copy.deepcopy(dict(item)) for item in null_test_results
                        ],
                        "milestone_1_decision_panel": copy.deepcopy(dict(decision_panel)),
                    },
                    "wave_only_diagnostics": {
                        "wave_metric_rollups": copy.deepcopy(list(wave_metric_rollups)),
                    },
                }
            )
        else:
            outputs.append(
                {
                    "output_id": normalized_output_id,
                    "output_kind": str(output_definition["output_kind"]),
                    "required_metric_ids": list(output_definition["required_metric_ids"]),
                }
            )
    return outputs


def _metric_row_identity(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["metric_id"]),
        str(row["readout_id"]),
        str(row["window_id"]),
        str(row["statistic"]),
        None if row.get("condition_pair_id") is None else str(row["condition_pair_id"]),
        None if row.get("pairing_key") is None else str(row["pairing_key"]),
        None
        if row.get("condition_signature") is None
        else str(row["condition_signature"]),
        None if row.get("decoder_id") is None else str(row["decoder_id"]),
        None if row.get("root_id") is None else int(row["root_id"]),
    )


def _comparison_detail_identity(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["metric_id"]),
        str(row["readout_id"]),
        str(row["window_id"]),
        str(row["statistic"]),
        None if row.get("condition_pair_id") is None else str(row["condition_pair_id"]),
        None if row.get("pairing_key") is None else str(row["pairing_key"]),
        None
        if row.get("condition_signature") is None
        else str(row["condition_signature"]),
        None if row.get("decoder_id") is None else str(row["decoder_id"]),
        None if row.get("root_id") is None else int(row["root_id"]),
    )


def _metric_row_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["analysis_source"]),
        str(row["arm_id"]),
        int(row["seed"]),
        str(row["metric_id"]),
        str(row["readout_id"]),
        str(row["window_id"]),
        str(row["statistic"]),
        "" if row.get("condition_signature") is None else str(row["condition_signature"]),
        "" if row.get("pairing_key") is None else str(row["pairing_key"]),
        "" if row.get("decoder_id") is None else str(row["decoder_id"]),
        -1 if row.get("root_id") is None else int(row["root_id"]),
    )


def _comparison_detail_row_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["group_id"]),
        str(row["metric_id"]),
        int(row["seed"]),
        str(row["readout_id"]),
        str(row["window_id"]),
        str(row["statistic"]),
        "" if row.get("condition_signature") is None else str(row["condition_signature"]),
        "" if row.get("pairing_key") is None else str(row["pairing_key"]),
        "" if row.get("decoder_id") is None else str(row["decoder_id"]),
        -1 if row.get("root_id") is None else int(row["root_id"]),
    )


def _group_metric_seed_row_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["group_id"]),
        str(row["metric_id"]),
        int(row["seed"]),
    )


def _group_metric_rollup_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["group_id"]),
        str(row["metric_id"]),
    )


def _wave_metric_seed_row_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["arm_id"]),
        str(row["metric_id"]),
        int(row["seed"]),
    )


def _wave_metric_rollup_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["arm_id"]),
        str(row["metric_id"]),
    )


def _task_score_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["requested_metric_id"]),
        _task_score_priority_key(row),
        str(row["group_id"]),
    )


def _task_score_priority_key(row: Mapping[str, Any]) -> tuple[int, int, int, str]:
    group_kind = str(row["group_kind"])
    if group_kind == "geometry_ablation":
        group_priority = 0
    elif group_kind == "matched_surface_wave_vs_baseline":
        group_priority = 1
    elif group_kind == "baseline_strength_challenge":
        group_priority = 2
    else:
        group_priority = 3
    group_id = str(row["group_id"])
    baseline_priority = 0 if "p0" in group_id else 1 if "p1" in group_id else 2
    topology_priority = 0 if "intact" in group_id else 1 if "shuffled" in group_id else 2
    return (group_priority, baseline_priority, topology_priority, group_id)


def _value_sign(value: float) -> str:
    if abs(float(value)) <= _EFFECT_ABS_TOLERANCE:
        return "zero"
    return "positive" if float(value) > 0.0 else "negative"


def _same_effect_direction(left: float, right: float) -> bool:
    left_sign = _value_sign(left)
    right_sign = _value_sign(right)
    if left_sign == "zero" or right_sign == "zero":
        return False
    return left_sign == right_sign


def _condition_signature(condition_ids: Sequence[str]) -> str:
    if not condition_ids:
        return "unlabeled"
    return "__".join(sorted(str(item) for item in condition_ids))


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value


__all__ = [
    "EXPERIMENT_COMPARISON_SUMMARY_VERSION",
    "compute_experiment_comparison_summary",
    "discover_experiment_bundle_set",
    "execute_experiment_comparison_workflow",
    "write_experiment_comparison_summary",
]
