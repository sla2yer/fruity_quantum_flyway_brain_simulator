from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from .stimulus_contract import _normalize_nonempty_string


EXPERIMENT_COMPARISON_SUMMARY_VERSION = "experiment_comparison_summary.v1"
_CONDITION_VALUE_TOLERANCE = 1.0e-6
_EFFECT_ABS_TOLERANCE = 1.0e-12
_IGNORED_SELECTED_ASSET_ROLES = frozenset({"input_bundle"})
_PATH_RELAXED_SELECTED_ASSET_ROLES = frozenset({"model_configuration"})


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
    "_CONDITION_VALUE_TOLERANCE",
    "_EFFECT_ABS_TOLERANCE",
    "_IGNORED_SELECTED_ASSET_ROLES",
    "_PATH_RELAXED_SELECTED_ASSET_ROLES",
    "_condition_signature",
    "_normalize_analysis_plan",
    "_normalize_bundle_set",
    "_normalize_simulation_plan",
    "_normalize_summary",
    "_require_mapping",
]
