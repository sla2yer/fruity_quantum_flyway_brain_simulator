from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .io_utils import write_json
from .simulator_result_contract import SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION
from .surface_wave_contract import SURFACE_WAVE_MODEL_CONTRACT_VERSION
from .stimulus_contract import _normalize_identifier, _normalize_nonempty_string


READOUT_ANALYSIS_CONTRACT_VERSION = "readout_analysis.v1"
READOUT_ANALYSIS_DESIGN_NOTE = "docs/readout_analysis_design.md"
READOUT_ANALYSIS_DESIGN_NOTE_VERSION = "readout_analysis_design_note.v1"

LOCKED_READOUT_STOP_POINT = "t4a_t5a_axon_terminals_lobula_plate_layer_1"
LOCKED_HYPOTHESIS_REFERENCE = "config/milestone_1_design_lock.yaml"

SHARED_READOUT_METRIC_CLASS = "shared_readout_metric"
DERIVED_TASK_METRIC_CLASS = "derived_task_metric"
WAVE_ONLY_DIAGNOSTIC_CLASS = "wave_only_diagnostic"
SUPPORTED_METRIC_CLASSES = (
    SHARED_READOUT_METRIC_CLASS,
    DERIVED_TASK_METRIC_CLASS,
    WAVE_ONLY_DIAGNOSTIC_CLASS,
)

EXPERIMENT_COMPARISON_OUTPUT_CLASS = "experiment_comparison_output"
SUPPORTED_OUTPUT_CLASSES = (EXPERIMENT_COMPARISON_OUTPUT_CLASS,)

SHARED_READOUT_ONLY_FAIRNESS_MODE = "shared_readout_only"
WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE = "wave_extension_allowed"
MIXED_SCOPE_LABELED_FAIRNESS_MODE = "mixed_scope_labeled"
SUPPORTED_FAIRNESS_MODES = (
    SHARED_READOUT_ONLY_FAIRNESS_MODE,
    WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE,
    MIXED_SCOPE_LABELED_FAIRNESS_MODE,
)

PER_SHARED_READOUT_CONDITION_WINDOW_SCOPE = "per_shared_readout_condition_window"
PER_SHARED_READOUT_CONDITION_PAIR_SCOPE = "per_shared_readout_condition_pair"
PER_TASK_DECODER_WINDOW_SCOPE = "per_task_decoder_window"
PER_WAVE_ROOT_WINDOW_SCOPE = "per_wave_root_window"
PER_WAVE_ROOT_SET_WINDOW_SCOPE = "per_wave_root_set_window"
PER_EXPERIMENT_ARM_PAIR_SCOPE = "per_experiment_arm_pair"
PER_EXPERIMENT_MANIFEST_SCOPE = "per_experiment_manifest"
SUPPORTED_SCOPE_RULES = (
    PER_SHARED_READOUT_CONDITION_WINDOW_SCOPE,
    PER_SHARED_READOUT_CONDITION_PAIR_SCOPE,
    PER_TASK_DECODER_WINDOW_SCOPE,
    PER_WAVE_ROOT_WINDOW_SCOPE,
    PER_WAVE_ROOT_SET_WINDOW_SCOPE,
    PER_EXPERIMENT_ARM_PAIR_SCOPE,
    PER_EXPERIMENT_MANIFEST_SCOPE,
)

SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS = "simulator_bundle_metadata"
SHARED_READOUT_CATALOG_ARTIFACT_CLASS = "shared_readout_catalog"
SHARED_READOUT_TRACES_ARTIFACT_CLASS = "shared_readout_traces"
SHARED_METRICS_TABLE_ARTIFACT_CLASS = "shared_metrics_table"
TASK_CONTEXT_METADATA_ARTIFACT_CLASS = "task_context_metadata"
STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS = "stimulus_condition_metadata"
RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS = "retinotopic_context_metadata"
SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS = "surface_wave_summary_extension"
SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS = "surface_wave_patch_traces_extension"
SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS = "surface_wave_phase_map_extension"
EXPERIMENT_BUNDLE_SET_ARTIFACT_CLASS = "experiment_bundle_set"
ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS = "analysis_metric_rows"
ANALYSIS_NULL_TEST_ROWS_ARTIFACT_CLASS = "analysis_null_test_rows"
WAVE_DIAGNOSTIC_ROWS_ARTIFACT_CLASS = "wave_diagnostic_rows"
SUPPORTED_SOURCE_ARTIFACT_CLASSES = (
    ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
    ANALYSIS_NULL_TEST_ROWS_ARTIFACT_CLASS,
    EXPERIMENT_BUNDLE_SET_ARTIFACT_CLASS,
    RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS,
    SHARED_METRICS_TABLE_ARTIFACT_CLASS,
    SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
    SHARED_READOUT_TRACES_ARTIFACT_CLASS,
    SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
    STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
    SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
    SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
    SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
    TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
    WAVE_DIAGNOSTIC_ROWS_ARTIFACT_CLASS,
)
WAVE_EXTENSION_ARTIFACT_CLASSES = frozenset(
    {
        SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
        SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
        SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
        WAVE_DIAGNOSTIC_ROWS_ARTIFACT_CLASS,
    }
)

COMPARISON_SUMMARY_OUTPUT_KIND = "comparison_summary"
DECISION_PANEL_OUTPUT_KIND = "decision_panel"
DIAGNOSTIC_PANEL_OUTPUT_KIND = "diagnostic_panel"
UI_PAYLOAD_OUTPUT_KIND = "ui_payload"
SUPPORTED_OUTPUT_KINDS = (
    COMPARISON_SUMMARY_OUTPUT_KIND,
    DECISION_PANEL_OUTPUT_KIND,
    DIAGNOSTIC_PANEL_OUTPUT_KIND,
    UI_PAYLOAD_OUTPUT_KIND,
)

MILESTONE_1_SHARED_EFFECTS_TASK_FAMILY = "milestone_1_shared_effects"
MOTION_DECODER_ESTIMATES_TASK_FAMILY = "motion_decoder_estimates"
WAVE_STRUCTURE_DIAGNOSTICS_TASK_FAMILY = "wave_structure_diagnostics"
EXPERIMENT_COMPARISON_OUTPUTS_TASK_FAMILY = "experiment_comparison_outputs"

NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID = "null_direction_suppression_comparison"
LATENCY_SHIFT_COMPARISON_OUTPUT_ID = "latency_shift_comparison"
MOTION_DECODER_SUMMARY_OUTPUT_ID = "motion_decoder_summary"
WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID = "wave_diagnostic_summary"
MILESTONE_1_DECISION_PANEL_OUTPUT_ID = "milestone_1_decision_panel"
ANALYSIS_UI_PAYLOAD_OUTPUT_ID = "analysis_ui_payload"

_DEFAULT_FAIRNESS_INVARIANTS = (
    "The locked readout stop point stays at the T4a/T5a axon terminals in lobula plate layer 1.",
    "The same shared readout_id means the same observable, units, and timebase semantics across baseline, surface_wave, and mixed-fidelity runs.",
    "Shared comparison metrics may depend only on simulator_result_bundle.v1 shared readout artifacts plus arm-invariant task context such as declared condition labels or retinotopic geometry metadata.",
    "Wave-only diagnostics may consume surface_wave extension artifacts, but they stay explicitly labeled as diagnostics and do not replace shared comparison metrics.",
    "Milestone 12 does not move the fairness boundary downstream into LPi or tangential-cell decoders; the task layer interprets the locked T4a/T5a terminal readout surface.",
    "UI-facing payloads may package both shared-comparison and wave-only content only if those scopes remain visibly separated.",
)


def build_readout_analysis_metric_definition(
    *,
    metric_id: str,
    metric_class: str,
    task_family_id: str,
    display_name: str,
    description: str,
    units: str,
    scope_rule: str,
    required_source_artifact_classes: Sequence[str],
    fairness_mode: str,
    fairness_note: str,
    interpretation: str,
) -> dict[str, Any]:
    return parse_readout_analysis_metric_definition(
        {
            "metric_id": metric_id,
            "metric_class": metric_class,
            "task_family_id": task_family_id,
            "display_name": display_name,
            "description": description,
            "units": units,
            "scope_rule": scope_rule,
            "required_source_artifact_classes": list(required_source_artifact_classes),
            "fairness_mode": fairness_mode,
            "fairness_note": fairness_note,
            "interpretation": interpretation,
        }
    )


def build_experiment_comparison_output_definition(
    *,
    output_id: str,
    task_family_id: str,
    output_kind: str,
    display_name: str,
    description: str,
    scope_rule: str,
    required_metric_ids: Sequence[str],
    required_source_artifact_classes: Sequence[str],
    fairness_mode: str,
    fairness_note: str,
) -> dict[str, Any]:
    return parse_experiment_comparison_output_definition(
        {
            "output_id": output_id,
            "output_class": EXPERIMENT_COMPARISON_OUTPUT_CLASS,
            "task_family_id": task_family_id,
            "output_kind": output_kind,
            "display_name": display_name,
            "description": description,
            "scope_rule": scope_rule,
            "required_metric_ids": list(required_metric_ids),
            "required_source_artifact_classes": list(required_source_artifact_classes),
            "fairness_mode": fairness_mode,
            "fairness_note": fairness_note,
        }
    )


def build_readout_analysis_task_family_definition(
    *,
    task_family_id: str,
    display_name: str,
    description: str,
    metric_ids: Sequence[str] | None = None,
    output_ids: Sequence[str] | None = None,
    null_test_hook_ids: Sequence[str] | None = None,
    fairness_mode: str,
) -> dict[str, Any]:
    return parse_readout_analysis_task_family_definition(
        {
            "task_family_id": task_family_id,
            "display_name": display_name,
            "description": description,
            "metric_ids": list(metric_ids or []),
            "output_ids": list(output_ids or []),
            "null_test_hook_ids": list(null_test_hook_ids or []),
            "fairness_mode": fairness_mode,
        }
    )


def build_readout_analysis_null_test_hook(
    *,
    null_test_id: str,
    task_family_id: str,
    display_name: str,
    description: str,
    required_metric_ids: Sequence[str],
    required_source_artifact_classes: Sequence[str],
    fairness_mode: str,
    pass_criterion: str,
) -> dict[str, Any]:
    return parse_readout_analysis_null_test_hook(
        {
            "null_test_id": null_test_id,
            "task_family_id": task_family_id,
            "display_name": display_name,
            "description": description,
            "required_metric_ids": list(required_metric_ids),
            "required_source_artifact_classes": list(required_source_artifact_classes),
            "fairness_mode": fairness_mode,
            "pass_criterion": pass_criterion,
        }
    )


def build_readout_analysis_contract_metadata(
    *,
    metric_definitions: Sequence[Mapping[str, Any]] | None = None,
    output_definitions: Sequence[Mapping[str, Any]] | None = None,
    task_families: Sequence[Mapping[str, Any]] | None = None,
    null_test_hooks: Sequence[Mapping[str, Any]] | None = None,
    ui_facing_output_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    resolved_output_definitions = list(
        output_definitions if output_definitions is not None else _default_output_catalog()
    )
    payload = {
        "contract_version": READOUT_ANALYSIS_CONTRACT_VERSION,
        "design_note": READOUT_ANALYSIS_DESIGN_NOTE,
        "design_note_version": READOUT_ANALYSIS_DESIGN_NOTE_VERSION,
        "locked_readout_stop_point": LOCKED_READOUT_STOP_POINT,
        "locked_hypothesis_reference": LOCKED_HYPOTHESIS_REFERENCE,
        "required_upstream_contracts": [
            SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
            SURFACE_WAVE_MODEL_CONTRACT_VERSION,
        ],
        "supported_metric_classes": list(SUPPORTED_METRIC_CLASSES),
        "supported_output_classes": list(SUPPORTED_OUTPUT_CLASSES),
        "supported_fairness_modes": list(SUPPORTED_FAIRNESS_MODES),
        "supported_scope_rules": list(SUPPORTED_SCOPE_RULES),
        "supported_output_kinds": list(SUPPORTED_OUTPUT_KINDS),
        "supported_source_artifact_classes": list(SUPPORTED_SOURCE_ARTIFACT_CLASSES),
        "fairness_invariants": list(_DEFAULT_FAIRNESS_INVARIANTS),
        "task_family_catalog": list(
            task_families if task_families is not None else _default_task_family_catalog()
        ),
        "metric_catalog": list(
            metric_definitions if metric_definitions is not None else _default_metric_catalog()
        ),
        "output_catalog": resolved_output_definitions,
        "null_test_catalog": list(
            null_test_hooks if null_test_hooks is not None else _default_null_test_catalog()
        ),
        "ui_facing_output_ids": list(
            ui_facing_output_ids
            if ui_facing_output_ids is not None
            else (
                _default_ui_facing_output_ids()
                if output_definitions is None
                else _derived_ui_facing_output_ids(resolved_output_definitions)
            )
        ),
    }
    return parse_readout_analysis_contract_metadata(payload)


def parse_readout_analysis_metric_definition(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("readout-analysis metric definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "metric_id",
        "metric_class",
        "task_family_id",
        "display_name",
        "description",
        "units",
        "scope_rule",
        "required_source_artifact_classes",
        "fairness_mode",
        "fairness_note",
        "interpretation",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"readout-analysis metric definition is missing fields: {missing_fields!r}.")
    normalized["metric_id"] = _normalize_identifier(
        normalized["metric_id"],
        field_name="metric_definition.metric_id",
    )
    normalized["metric_class"] = _normalize_metric_class(normalized["metric_class"])
    normalized["task_family_id"] = _normalize_identifier(
        normalized["task_family_id"],
        field_name="metric_definition.task_family_id",
    )
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="metric_definition.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="metric_definition.description",
    )
    normalized["units"] = _normalize_nonempty_string(
        normalized["units"],
        field_name="metric_definition.units",
    )
    normalized["scope_rule"] = _normalize_scope_rule(normalized["scope_rule"])
    normalized["required_source_artifact_classes"] = _normalize_source_artifact_class_list(
        normalized["required_source_artifact_classes"],
        field_name="metric_definition.required_source_artifact_classes",
    )
    normalized["fairness_mode"] = _normalize_fairness_mode(normalized["fairness_mode"])
    normalized["fairness_note"] = _normalize_nonempty_string(
        normalized["fairness_note"],
        field_name="metric_definition.fairness_note",
    )
    normalized["interpretation"] = _normalize_nonempty_string(
        normalized["interpretation"],
        field_name="metric_definition.interpretation",
    )

    source_classes = set(normalized["required_source_artifact_classes"])
    if normalized["metric_class"] == WAVE_ONLY_DIAGNOSTIC_CLASS:
        if normalized["fairness_mode"] != WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE:
            raise ValueError(
                "wave_only_diagnostic metrics must use fairness_mode "
                f"{WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE!r}."
            )
        if not source_classes & WAVE_EXTENSION_ARTIFACT_CLASSES:
            raise ValueError(
                "wave_only_diagnostic metrics must depend on at least one wave extension artifact class."
            )
    else:
        if normalized["fairness_mode"] != SHARED_READOUT_ONLY_FAIRNESS_MODE:
            raise ValueError(
                "shared_readout_metric and derived_task_metric entries must use fairness_mode "
                f"{SHARED_READOUT_ONLY_FAIRNESS_MODE!r}."
            )
        if SHARED_READOUT_CATALOG_ARTIFACT_CLASS not in source_classes:
            raise ValueError(
                "shared-readout-backed metrics must include required source class "
                f"{SHARED_READOUT_CATALOG_ARTIFACT_CLASS!r}."
            )
        if SHARED_READOUT_TRACES_ARTIFACT_CLASS not in source_classes:
            raise ValueError(
                "shared-readout-backed metrics must include required source class "
                f"{SHARED_READOUT_TRACES_ARTIFACT_CLASS!r}."
            )
        if source_classes & WAVE_EXTENSION_ARTIFACT_CLASSES:
            raise ValueError(
                "shared_readout_metric and derived_task_metric entries may not depend on wave extension artifact classes."
            )
        if (
            normalized["metric_class"] == DERIVED_TASK_METRIC_CLASS
            and TASK_CONTEXT_METADATA_ARTIFACT_CLASS not in source_classes
        ):
            raise ValueError(
                "derived_task_metric entries must include required source class "
                f"{TASK_CONTEXT_METADATA_ARTIFACT_CLASS!r}."
            )
    return normalized


def parse_experiment_comparison_output_definition(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("experiment comparison output definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "output_id",
        "output_class",
        "task_family_id",
        "output_kind",
        "display_name",
        "description",
        "scope_rule",
        "required_metric_ids",
        "required_source_artifact_classes",
        "fairness_mode",
        "fairness_note",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"experiment comparison output definition is missing fields: {missing_fields!r}."
        )
    normalized["output_id"] = _normalize_identifier(
        normalized["output_id"],
        field_name="output_definition.output_id",
    )
    normalized["output_class"] = _normalize_output_class(normalized["output_class"])
    normalized["task_family_id"] = _normalize_identifier(
        normalized["task_family_id"],
        field_name="output_definition.task_family_id",
    )
    normalized["output_kind"] = _normalize_output_kind(normalized["output_kind"])
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="output_definition.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="output_definition.description",
    )
    normalized["scope_rule"] = _normalize_scope_rule(normalized["scope_rule"])
    normalized["required_metric_ids"] = _normalize_identifier_list(
        normalized["required_metric_ids"],
        field_name="output_definition.required_metric_ids",
        allow_empty=False,
    )
    normalized["required_source_artifact_classes"] = _normalize_source_artifact_class_list(
        normalized["required_source_artifact_classes"],
        field_name="output_definition.required_source_artifact_classes",
    )
    normalized["fairness_mode"] = _normalize_fairness_mode(normalized["fairness_mode"])
    normalized["fairness_note"] = _normalize_nonempty_string(
        normalized["fairness_note"],
        field_name="output_definition.fairness_note",
    )
    return normalized


def parse_readout_analysis_task_family_definition(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("readout-analysis task family definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "task_family_id",
        "display_name",
        "description",
        "metric_ids",
        "output_ids",
        "null_test_hook_ids",
        "fairness_mode",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"readout-analysis task family definition is missing fields: {missing_fields!r}."
        )
    normalized["task_family_id"] = _normalize_identifier(
        normalized["task_family_id"],
        field_name="task_family.task_family_id",
    )
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="task_family.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="task_family.description",
    )
    normalized["metric_ids"] = _normalize_identifier_list(
        normalized["metric_ids"],
        field_name="task_family.metric_ids",
        allow_empty=True,
    )
    normalized["output_ids"] = _normalize_identifier_list(
        normalized["output_ids"],
        field_name="task_family.output_ids",
        allow_empty=True,
    )
    normalized["null_test_hook_ids"] = _normalize_identifier_list(
        normalized["null_test_hook_ids"],
        field_name="task_family.null_test_hook_ids",
        allow_empty=True,
    )
    normalized["fairness_mode"] = _normalize_fairness_mode(normalized["fairness_mode"])
    if (
        not normalized["metric_ids"]
        and not normalized["output_ids"]
        and not normalized["null_test_hook_ids"]
    ):
        raise ValueError(
            "readout-analysis task families must name at least one metric, output, or null-test hook."
        )
    return normalized


def parse_readout_analysis_null_test_hook(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("readout-analysis null-test hooks must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "null_test_id",
        "task_family_id",
        "display_name",
        "description",
        "required_metric_ids",
        "required_source_artifact_classes",
        "fairness_mode",
        "pass_criterion",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"readout-analysis null-test hook is missing fields: {missing_fields!r}.")
    normalized["null_test_id"] = _normalize_identifier(
        normalized["null_test_id"],
        field_name="null_test.null_test_id",
    )
    normalized["task_family_id"] = _normalize_identifier(
        normalized["task_family_id"],
        field_name="null_test.task_family_id",
    )
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="null_test.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="null_test.description",
    )
    normalized["required_metric_ids"] = _normalize_identifier_list(
        normalized["required_metric_ids"],
        field_name="null_test.required_metric_ids",
        allow_empty=False,
    )
    normalized["required_source_artifact_classes"] = _normalize_source_artifact_class_list(
        normalized["required_source_artifact_classes"],
        field_name="null_test.required_source_artifact_classes",
    )
    normalized["fairness_mode"] = _normalize_fairness_mode(normalized["fairness_mode"])
    normalized["pass_criterion"] = _normalize_nonempty_string(
        normalized["pass_criterion"],
        field_name="null_test.pass_criterion",
    )
    return normalized


def parse_readout_analysis_contract_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("readout-analysis contract metadata must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "design_note",
        "design_note_version",
        "locked_readout_stop_point",
        "locked_hypothesis_reference",
        "required_upstream_contracts",
        "supported_metric_classes",
        "supported_output_classes",
        "supported_fairness_modes",
        "supported_scope_rules",
        "supported_output_kinds",
        "supported_source_artifact_classes",
        "fairness_invariants",
        "task_family_catalog",
        "metric_catalog",
        "output_catalog",
        "null_test_catalog",
        "ui_facing_output_ids",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "readout-analysis contract metadata is missing required fields: "
            f"{missing_fields!r}."
        )
    contract_version = _normalize_nonempty_string(
        normalized["contract_version"],
        field_name="contract_version",
    )
    if contract_version != READOUT_ANALYSIS_CONTRACT_VERSION:
        raise ValueError(
            "readout-analysis contract metadata contract_version does not match "
            f"{READOUT_ANALYSIS_CONTRACT_VERSION!r}."
        )
    normalized["contract_version"] = contract_version
    normalized["design_note"] = _normalize_nonempty_string(
        normalized["design_note"],
        field_name="design_note",
    )
    normalized["design_note_version"] = _normalize_nonempty_string(
        normalized["design_note_version"],
        field_name="design_note_version",
    )
    normalized["locked_readout_stop_point"] = _normalize_identifier(
        normalized["locked_readout_stop_point"],
        field_name="locked_readout_stop_point",
    )
    normalized["locked_hypothesis_reference"] = _normalize_nonempty_string(
        normalized["locked_hypothesis_reference"],
        field_name="locked_hypothesis_reference",
    )
    normalized["required_upstream_contracts"] = _normalize_nonempty_string_list(
        normalized["required_upstream_contracts"],
        field_name="required_upstream_contracts",
    )
    normalized["supported_metric_classes"] = _normalize_known_constant_list(
        normalized["supported_metric_classes"],
        field_name="supported_metric_classes",
        supported_values=SUPPORTED_METRIC_CLASSES,
    )
    normalized["supported_output_classes"] = _normalize_known_constant_list(
        normalized["supported_output_classes"],
        field_name="supported_output_classes",
        supported_values=SUPPORTED_OUTPUT_CLASSES,
    )
    normalized["supported_fairness_modes"] = _normalize_known_constant_list(
        normalized["supported_fairness_modes"],
        field_name="supported_fairness_modes",
        supported_values=SUPPORTED_FAIRNESS_MODES,
    )
    normalized["supported_scope_rules"] = _normalize_known_constant_list(
        normalized["supported_scope_rules"],
        field_name="supported_scope_rules",
        supported_values=SUPPORTED_SCOPE_RULES,
    )
    normalized["supported_output_kinds"] = _normalize_known_constant_list(
        normalized["supported_output_kinds"],
        field_name="supported_output_kinds",
        supported_values=SUPPORTED_OUTPUT_KINDS,
    )
    normalized["supported_source_artifact_classes"] = _normalize_known_constant_list(
        normalized["supported_source_artifact_classes"],
        field_name="supported_source_artifact_classes",
        supported_values=SUPPORTED_SOURCE_ARTIFACT_CLASSES,
    )
    normalized["fairness_invariants"] = _normalize_nonempty_string_list(
        normalized["fairness_invariants"],
        field_name="fairness_invariants",
    )
    normalized["task_family_catalog"] = _normalize_task_family_catalog(
        normalized["task_family_catalog"]
    )
    normalized["metric_catalog"] = _normalize_metric_catalog(normalized["metric_catalog"])
    normalized["output_catalog"] = _normalize_output_catalog(normalized["output_catalog"])
    normalized["null_test_catalog"] = _normalize_null_test_catalog(
        normalized["null_test_catalog"]
    )
    normalized["ui_facing_output_ids"] = _normalize_identifier_list(
        normalized["ui_facing_output_ids"],
        field_name="ui_facing_output_ids",
        allow_empty=False,
    )

    metric_catalog_by_id = {
        item["metric_id"]: item for item in normalized["metric_catalog"]
    }
    output_catalog_by_id = {
        item["output_id"]: item for item in normalized["output_catalog"]
    }
    null_test_by_id = {
        item["null_test_id"]: item for item in normalized["null_test_catalog"]
    }
    task_family_by_id = {
        item["task_family_id"]: item for item in normalized["task_family_catalog"]
    }

    for metric in normalized["metric_catalog"]:
        if metric["task_family_id"] not in task_family_by_id:
            raise ValueError(
                f"metric_catalog references unknown task_family_id {metric['task_family_id']!r}."
            )
    for output in normalized["output_catalog"]:
        if output["task_family_id"] not in task_family_by_id:
            raise ValueError(
                f"output_catalog references unknown task_family_id {output['task_family_id']!r}."
            )
        unknown_metric_ids = sorted(
            set(output["required_metric_ids"]) - set(metric_catalog_by_id)
        )
        if unknown_metric_ids:
            raise ValueError(
                f"output_catalog entry {output['output_id']!r} references unknown metric ids {unknown_metric_ids!r}."
            )
        if output["fairness_mode"] == SHARED_READOUT_ONLY_FAIRNESS_MODE:
            wave_metric_ids = [
                metric_id
                for metric_id in output["required_metric_ids"]
                if metric_catalog_by_id[metric_id]["metric_class"] == WAVE_ONLY_DIAGNOSTIC_CLASS
            ]
            if wave_metric_ids:
                raise ValueError(
                    f"shared-readout-only output {output['output_id']!r} may not reference wave-only metrics {wave_metric_ids!r}."
                )
    for null_test in normalized["null_test_catalog"]:
        if null_test["task_family_id"] not in task_family_by_id:
            raise ValueError(
                f"null_test_catalog references unknown task_family_id {null_test['task_family_id']!r}."
            )
        unknown_metric_ids = sorted(
            set(null_test["required_metric_ids"]) - set(metric_catalog_by_id)
        )
        if unknown_metric_ids:
            raise ValueError(
                f"null_test_catalog entry {null_test['null_test_id']!r} references unknown metric ids {unknown_metric_ids!r}."
            )
    for task_family in normalized["task_family_catalog"]:
        unknown_metric_ids = sorted(
            set(task_family["metric_ids"]) - set(metric_catalog_by_id)
        )
        if unknown_metric_ids:
            raise ValueError(
                f"task_family {task_family['task_family_id']!r} references unknown metric ids {unknown_metric_ids!r}."
            )
        unknown_output_ids = sorted(
            set(task_family["output_ids"]) - set(output_catalog_by_id)
        )
        if unknown_output_ids:
            raise ValueError(
                f"task_family {task_family['task_family_id']!r} references unknown output ids {unknown_output_ids!r}."
            )
        unknown_null_test_ids = sorted(
            set(task_family["null_test_hook_ids"]) - set(null_test_by_id)
        )
        if unknown_null_test_ids:
            raise ValueError(
                f"task_family {task_family['task_family_id']!r} references unknown null test ids {unknown_null_test_ids!r}."
            )
    unknown_ui_output_ids = sorted(
        set(normalized["ui_facing_output_ids"]) - set(output_catalog_by_id)
    )
    if unknown_ui_output_ids:
        raise ValueError(
            f"ui_facing_output_ids references unknown output ids {unknown_ui_output_ids!r}."
        )
    return normalized


def load_readout_analysis_contract_metadata(metadata_path: str | Path) -> dict[str, Any]:
    path = Path(metadata_path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_readout_analysis_contract_metadata(payload)


def write_readout_analysis_contract_metadata(
    contract_metadata: Mapping[str, Any],
    metadata_path: str | Path,
) -> Path:
    normalized = parse_readout_analysis_contract_metadata(contract_metadata)
    return write_json(normalized, metadata_path)


def discover_readout_analysis_metric_definitions(
    record: Mapping[str, Any],
    *,
    metric_class: str | None = None,
    task_family_id: str | None = None,
    fairness_mode: str | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_readout_analysis_contract_metadata(
        _extract_readout_analysis_contract_mapping(record)
    )
    normalized_metric_class = (
        None if metric_class is None else _normalize_metric_class(metric_class)
    )
    normalized_task_family_id = (
        None
        if task_family_id is None
        else _normalize_identifier(task_family_id, field_name="task_family_id")
    )
    normalized_fairness_mode = (
        None if fairness_mode is None else _normalize_fairness_mode(fairness_mode)
    )
    discovered: list[dict[str, Any]] = []
    for item in metadata["metric_catalog"]:
        if normalized_metric_class is not None and item["metric_class"] != normalized_metric_class:
            continue
        if normalized_task_family_id is not None and item["task_family_id"] != normalized_task_family_id:
            continue
        if normalized_fairness_mode is not None and item["fairness_mode"] != normalized_fairness_mode:
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def discover_experiment_comparison_output_definitions(
    record: Mapping[str, Any],
    *,
    task_family_id: str | None = None,
    fairness_mode: str | None = None,
    output_kind: str | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_readout_analysis_contract_metadata(
        _extract_readout_analysis_contract_mapping(record)
    )
    normalized_task_family_id = (
        None
        if task_family_id is None
        else _normalize_identifier(task_family_id, field_name="task_family_id")
    )
    normalized_fairness_mode = (
        None if fairness_mode is None else _normalize_fairness_mode(fairness_mode)
    )
    normalized_output_kind = (
        None if output_kind is None else _normalize_output_kind(output_kind)
    )
    discovered: list[dict[str, Any]] = []
    for item in metadata["output_catalog"]:
        if normalized_task_family_id is not None and item["task_family_id"] != normalized_task_family_id:
            continue
        if normalized_fairness_mode is not None and item["fairness_mode"] != normalized_fairness_mode:
            continue
        if normalized_output_kind is not None and item["output_kind"] != normalized_output_kind:
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def discover_readout_analysis_task_families(
    record: Mapping[str, Any],
    *,
    fairness_mode: str | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_readout_analysis_contract_metadata(
        _extract_readout_analysis_contract_mapping(record)
    )
    normalized_fairness_mode = (
        None if fairness_mode is None else _normalize_fairness_mode(fairness_mode)
    )
    discovered: list[dict[str, Any]] = []
    for item in metadata["task_family_catalog"]:
        if normalized_fairness_mode is not None and item["fairness_mode"] != normalized_fairness_mode:
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def discover_readout_analysis_null_test_hooks(
    record: Mapping[str, Any],
    *,
    task_family_id: str | None = None,
    fairness_mode: str | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_readout_analysis_contract_metadata(
        _extract_readout_analysis_contract_mapping(record)
    )
    normalized_task_family_id = (
        None
        if task_family_id is None
        else _normalize_identifier(task_family_id, field_name="task_family_id")
    )
    normalized_fairness_mode = (
        None if fairness_mode is None else _normalize_fairness_mode(fairness_mode)
    )
    discovered: list[dict[str, Any]] = []
    for item in metadata["null_test_catalog"]:
        if normalized_task_family_id is not None and item["task_family_id"] != normalized_task_family_id:
            continue
        if normalized_fairness_mode is not None and item["fairness_mode"] != normalized_fairness_mode:
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def get_readout_analysis_metric_definition(
    metric_id: str,
    *,
    record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_metric_id = _normalize_identifier(metric_id, field_name="metric_id")
    metadata = (
        build_readout_analysis_contract_metadata()
        if record is None
        else parse_readout_analysis_contract_metadata(_extract_readout_analysis_contract_mapping(record))
    )
    for item in metadata["metric_catalog"]:
        if item["metric_id"] == normalized_metric_id:
            return copy.deepcopy(item)
    raise ValueError(f"Unknown readout-analysis metric_id {normalized_metric_id!r}.")


def get_experiment_comparison_output_definition(
    output_id: str,
    *,
    record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_output_id = _normalize_identifier(output_id, field_name="output_id")
    metadata = (
        build_readout_analysis_contract_metadata()
        if record is None
        else parse_readout_analysis_contract_metadata(_extract_readout_analysis_contract_mapping(record))
    )
    for item in metadata["output_catalog"]:
        if item["output_id"] == normalized_output_id:
            return copy.deepcopy(item)
    raise ValueError(f"Unknown experiment comparison output_id {normalized_output_id!r}.")


def get_readout_analysis_task_family_definition(
    task_family_id: str,
    *,
    record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_task_family_id = _normalize_identifier(
        task_family_id,
        field_name="task_family_id",
    )
    metadata = (
        build_readout_analysis_contract_metadata()
        if record is None
        else parse_readout_analysis_contract_metadata(_extract_readout_analysis_contract_mapping(record))
    )
    for item in metadata["task_family_catalog"]:
        if item["task_family_id"] == normalized_task_family_id:
            return copy.deepcopy(item)
    raise ValueError(f"Unknown readout-analysis task_family_id {normalized_task_family_id!r}.")


def get_readout_analysis_null_test_hook(
    null_test_id: str,
    *,
    record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_null_test_id = _normalize_identifier(
        null_test_id,
        field_name="null_test_id",
    )
    metadata = (
        build_readout_analysis_contract_metadata()
        if record is None
        else parse_readout_analysis_contract_metadata(_extract_readout_analysis_contract_mapping(record))
    )
    for item in metadata["null_test_catalog"]:
        if item["null_test_id"] == normalized_null_test_id:
            return copy.deepcopy(item)
    raise ValueError(f"Unknown readout-analysis null_test_id {normalized_null_test_id!r}.")


def _default_metric_catalog() -> list[dict[str, Any]]:
    return [
        build_readout_analysis_metric_definition(
            metric_id="null_direction_suppression_index",
            metric_class=SHARED_READOUT_METRIC_CLASS,
            task_family_id=MILESTONE_1_SHARED_EFFECTS_TASK_FAMILY,
            display_name="Null-Direction Suppression Index",
            description="Normalized preferred-versus-null suppression score computed from matched shared terminal readout responses.",
            units="unitless",
            scope_rule=PER_SHARED_READOUT_CONDITION_PAIR_SCOPE,
            required_source_artifact_classes=[
                SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
                SHARED_READOUT_TRACES_ARTIFACT_CLASS,
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            fairness_note="This metric must be computable from the shared simulator readout catalog and declared preferred/null condition labels alone. Wave-only patch or phase extensions are forbidden.",
            interpretation="Higher values mean the locked T4a/T5a terminal readout suppresses null-direction responses more strongly relative to preferred-direction responses.",
        ),
        build_readout_analysis_metric_definition(
            metric_id="response_latency_to_peak_ms",
            metric_class=SHARED_READOUT_METRIC_CLASS,
            task_family_id=MILESTONE_1_SHARED_EFFECTS_TASK_FAMILY,
            display_name="Response Latency To Peak",
            description="Latency from the declared analysis-window onset to the first stable peak of a shared terminal readout response.",
            units="ms",
            scope_rule=PER_SHARED_READOUT_CONDITION_WINDOW_SCOPE,
            required_source_artifact_classes=[
                SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
                SHARED_READOUT_TRACES_ARTIFACT_CLASS,
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            fairness_note="Latency is a fairness-critical companion observable and must be derived only from the shared readout timebase plus declared window timing.",
            interpretation="Latency is a companion observable for Milestone 1 and should align with, not replace, the primary null-direction suppression effect.",
        ),
        build_readout_analysis_metric_definition(
            metric_id="direction_selectivity_index",
            metric_class=SHARED_READOUT_METRIC_CLASS,
            task_family_id=MILESTONE_1_SHARED_EFFECTS_TASK_FAMILY,
            display_name="Direction Selectivity Index",
            description="Normalized preferred-minus-null directional contrast measured on the locked shared terminal readout surface.",
            units="unitless",
            scope_rule=PER_SHARED_READOUT_CONDITION_PAIR_SCOPE,
            required_source_artifact_classes=[
                SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
                SHARED_READOUT_TRACES_ARTIFACT_CLASS,
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            fairness_note="Direction selectivity remains a shared-comparison metric and may not consume wave-only morphology or phase state.",
            interpretation="Higher values indicate stronger preferred-versus-null asymmetry at the T4a/T5a terminal boundary.",
        ),
        build_readout_analysis_metric_definition(
            metric_id="on_off_selectivity_index",
            metric_class=SHARED_READOUT_METRIC_CLASS,
            task_family_id=MILESTONE_1_SHARED_EFFECTS_TASK_FAMILY,
            display_name="ON/OFF Selectivity Index",
            description="Normalized ON-versus-OFF polarity contrast measured on matched shared readout responses.",
            units="unitless",
            scope_rule=PER_SHARED_READOUT_CONDITION_PAIR_SCOPE,
            required_source_artifact_classes=[
                SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
                SHARED_READOUT_TRACES_ARTIFACT_CLASS,
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            fairness_note="ON/OFF selectivity may use only shared readouts and declared polarity labels. It must stay fair between baseline and wave arms.",
            interpretation="Positive values mean the declared ON condition drives a stronger shared terminal response than the matched OFF condition.",
        ),
        build_readout_analysis_metric_definition(
            metric_id="motion_vector_heading_deg",
            metric_class=DERIVED_TASK_METRIC_CLASS,
            task_family_id=MOTION_DECODER_ESTIMATES_TASK_FAMILY,
            display_name="Motion Vector Heading",
            description="Decoded motion-vector heading derived from shared readout evidence on the current task window.",
            units="deg",
            scope_rule=PER_TASK_DECODER_WINDOW_SCOPE,
            required_source_artifact_classes=[
                RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS,
                SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
                SHARED_READOUT_TRACES_ARTIFACT_CLASS,
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
                TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            fairness_note="Motion-vector decoding may use shared readout evidence plus arm-invariant task context such as stimulus-direction labels and retinotopic geometry metadata, but it may not access wave-only extensions.",
            interpretation="The current Milestone 12 scope is the local motion patch around the locked horizontal channel, so heading estimates are task-level summaries rather than whole-field behavior claims.",
        ),
        build_readout_analysis_metric_definition(
            metric_id="motion_vector_speed_deg_per_s",
            metric_class=DERIVED_TASK_METRIC_CLASS,
            task_family_id=MOTION_DECODER_ESTIMATES_TASK_FAMILY,
            display_name="Motion Vector Speed",
            description="Decoded motion-vector speed magnitude derived from shared readout evidence on the current task window.",
            units="deg_per_s",
            scope_rule=PER_TASK_DECODER_WINDOW_SCOPE,
            required_source_artifact_classes=[
                RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS,
                SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
                SHARED_READOUT_TRACES_ARTIFACT_CLASS,
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
                TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            fairness_note="Motion-vector speed remains a fair task readout only when it is derived from shared readouts plus declared task context instead of wave-only hidden state.",
            interpretation="This is the decoded magnitude paired with motion_vector_heading_deg for the current task-analysis window.",
        ),
        build_readout_analysis_metric_definition(
            metric_id="optic_flow_heading_deg",
            metric_class=DERIVED_TASK_METRIC_CLASS,
            task_family_id=MOTION_DECODER_ESTIMATES_TASK_FAMILY,
            display_name="Optic-Flow Heading",
            description="Decoded optic-flow heading derived from shared readout evidence and declared local retinotopic context.",
            units="deg",
            scope_rule=PER_TASK_DECODER_WINDOW_SCOPE,
            required_source_artifact_classes=[
                RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS,
                SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
                SHARED_READOUT_TRACES_ARTIFACT_CLASS,
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
                TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            fairness_note="Optic-flow estimates may use only shared readouts plus arm-invariant task context. They may not consume wave-only patch, phase, or internal-state payloads.",
            interpretation="In the current Milestone 12 local-patch slice this is a small-field optic-flow estimate, not a whole-eye behavioral claim.",
        ),
        build_readout_analysis_metric_definition(
            metric_id="optic_flow_speed_deg_per_s",
            metric_class=DERIVED_TASK_METRIC_CLASS,
            task_family_id=MOTION_DECODER_ESTIMATES_TASK_FAMILY,
            display_name="Optic-Flow Speed",
            description="Decoded optic-flow speed magnitude derived from shared readout evidence and declared local retinotopic context.",
            units="deg_per_s",
            scope_rule=PER_TASK_DECODER_WINDOW_SCOPE,
            required_source_artifact_classes=[
                RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS,
                SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
                SHARED_READOUT_TRACES_ARTIFACT_CLASS,
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
                TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            fairness_note="Optic-flow speed must remain a fair task readout derived from shared traces plus declared task context, never from wave-only extension artifacts.",
            interpretation="This is the decoded magnitude paired with optic_flow_heading_deg for the current task-analysis window.",
        ),
        build_readout_analysis_metric_definition(
            metric_id="synchrony_coherence_index",
            metric_class=WAVE_ONLY_DIAGNOSTIC_CLASS,
            task_family_id=WAVE_STRUCTURE_DIAGNOSTICS_TASK_FAMILY,
            display_name="Synchrony/Coherence Index",
            description="Temporal synchrony or coherence summary computed across the available wave-resolved patch traces.",
            units="unitless",
            scope_rule=PER_WAVE_ROOT_SET_WINDOW_SCOPE,
            required_source_artifact_classes=[
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
                SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
            ],
            fairness_mode=WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE,
            fairness_note="This is a wave-only diagnostic. It may consume surface_wave patch traces and summary sidecars, but it may not be promoted to the shared comparison surface.",
            interpretation="Higher values mean the available wave-resolved patches evolve more coherently over the declared analysis window.",
        ),
        build_readout_analysis_metric_definition(
            metric_id="phase_gradient_mean_rad_per_patch",
            metric_class=WAVE_ONLY_DIAGNOSTIC_CLASS,
            task_family_id=WAVE_STRUCTURE_DIAGNOSTICS_TASK_FAMILY,
            display_name="Phase-Gradient Mean",
            description="Mean local phase-gradient magnitude across the available wave-resolved patch field.",
            units="rad_per_patch",
            scope_rule=PER_WAVE_ROOT_WINDOW_SCOPE,
            required_source_artifact_classes=[
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
                SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
            ],
            fairness_mode=WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE,
            fairness_note="Phase-gradient metrics are wave-only diagnostics and may consume future phase-map extensions under the bundle extension surface.",
            interpretation="Larger values indicate steeper local phase gradients across the patch field for one wave-resolved root.",
        ),
        build_readout_analysis_metric_definition(
            metric_id="phase_gradient_dispersion_rad_per_patch",
            metric_class=WAVE_ONLY_DIAGNOSTIC_CLASS,
            task_family_id=WAVE_STRUCTURE_DIAGNOSTICS_TASK_FAMILY,
            display_name="Phase-Gradient Dispersion",
            description="Dispersion of local phase-gradient magnitudes across one wave-resolved patch field.",
            units="rad_per_patch",
            scope_rule=PER_WAVE_ROOT_WINDOW_SCOPE,
            required_source_artifact_classes=[
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
                SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
            ],
            fairness_mode=WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE,
            fairness_note="Phase-gradient dispersion may use wave-only phase payloads and remains diagnostic-only rather than fairness-critical.",
            interpretation="Higher values indicate more heterogeneous phase-gradient structure across the wave-resolved patch field.",
        ),
        build_readout_analysis_metric_definition(
            metric_id="wavefront_speed_patch_per_ms",
            metric_class=WAVE_ONLY_DIAGNOSTIC_CLASS,
            task_family_id=WAVE_STRUCTURE_DIAGNOSTICS_TASK_FAMILY,
            display_name="Wavefront Speed",
            description="Finite-speed wavefront estimate expressed in coarse-patch units per millisecond.",
            units="patch_per_ms",
            scope_rule=PER_WAVE_ROOT_WINDOW_SCOPE,
            required_source_artifact_classes=[
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
                SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
            ],
            fairness_mode=WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE,
            fairness_note="Wavefront speed may consume wave-only patch traces and inspection-style summary payloads, but it must stay labeled as a morphology-aware diagnostic.",
            interpretation="Higher values indicate faster apparent propagation across the coarse patch graph for one wave-resolved root.",
        ),
        build_readout_analysis_metric_definition(
            metric_id="wavefront_curvature_inv_patch",
            metric_class=WAVE_ONLY_DIAGNOSTIC_CLASS,
            task_family_id=WAVE_STRUCTURE_DIAGNOSTICS_TASK_FAMILY,
            display_name="Wavefront Curvature",
            description="Wavefront curvature estimate expressed as inverse coarse-patch units.",
            units="inv_patch",
            scope_rule=PER_WAVE_ROOT_WINDOW_SCOPE,
            required_source_artifact_classes=[
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
                SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
            ],
            fairness_mode=WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE,
            fairness_note="Wavefront curvature is permitted to consume phase-map extensions and remains outside the shared comparison contract.",
            interpretation="Larger magnitudes indicate more strongly curved local wavefront geometry on the coarse patch field.",
        ),
        build_readout_analysis_metric_definition(
            metric_id="patch_activation_entropy_bits",
            metric_class=WAVE_ONLY_DIAGNOSTIC_CLASS,
            task_family_id=WAVE_STRUCTURE_DIAGNOSTICS_TASK_FAMILY,
            display_name="Patch Activation Entropy",
            description="Entropy of the realized patch-activation distribution over the declared wave-analysis window.",
            units="bits",
            scope_rule=PER_WAVE_ROOT_WINDOW_SCOPE,
            required_source_artifact_classes=[
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
            ],
            fairness_mode=WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE,
            fairness_note="Patch-activation entropy is a wave-only structural diagnostic and must not be compared as if it were a shared baseline-versus-wave observable.",
            interpretation="Higher entropy indicates more spatially distributed or less concentrated patch activation across the analyzed window.",
        ),
    ]


def _default_output_catalog() -> list[dict[str, Any]]:
    return [
        build_experiment_comparison_output_definition(
            output_id=NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID,
            task_family_id=EXPERIMENT_COMPARISON_OUTPUTS_TASK_FAMILY,
            output_kind=COMPARISON_SUMMARY_OUTPUT_KIND,
            display_name="Null-Direction Suppression Comparison",
            description="Experiment-level comparison output centered on the primary Milestone 1 null-direction suppression observable.",
            scope_rule=PER_EXPERIMENT_ARM_PAIR_SCOPE,
            required_metric_ids=["null_direction_suppression_index"],
            required_source_artifact_classes=[
                ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
                EXPERIMENT_BUNDLE_SET_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            fairness_note="This output is fairness-critical and must be derivable from shared-readout metrics only.",
        ),
        build_experiment_comparison_output_definition(
            output_id=LATENCY_SHIFT_COMPARISON_OUTPUT_ID,
            task_family_id=EXPERIMENT_COMPARISON_OUTPUTS_TASK_FAMILY,
            output_kind=COMPARISON_SUMMARY_OUTPUT_KIND,
            display_name="Latency Shift Comparison",
            description="Experiment-level comparison output centered on response-latency shifts across declared arm pairs.",
            scope_rule=PER_EXPERIMENT_ARM_PAIR_SCOPE,
            required_metric_ids=["response_latency_to_peak_ms"],
            required_source_artifact_classes=[
                ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
                EXPERIMENT_BUNDLE_SET_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            fairness_note="Latency comparison remains on the shared readout surface and may not incorporate wave-only diagnostics.",
        ),
        build_experiment_comparison_output_definition(
            output_id=MOTION_DECODER_SUMMARY_OUTPUT_ID,
            task_family_id=MOTION_DECODER_ESTIMATES_TASK_FAMILY,
            output_kind=COMPARISON_SUMMARY_OUTPUT_KIND,
            display_name="Motion Decoder Summary",
            description="Task-level summary of motion-vector and optic-flow estimates derived from shared readout evidence.",
            scope_rule=PER_EXPERIMENT_MANIFEST_SCOPE,
            required_metric_ids=[
                "motion_vector_heading_deg",
                "motion_vector_speed_deg_per_s",
                "optic_flow_heading_deg",
                "optic_flow_speed_deg_per_s",
            ],
            required_source_artifact_classes=[
                ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
                TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            fairness_note="Motion-decoder summaries remain fair only when they package shared-readout-derived task metrics rather than wave-only hidden state.",
        ),
        build_experiment_comparison_output_definition(
            output_id=WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID,
            task_family_id=WAVE_STRUCTURE_DIAGNOSTICS_TASK_FAMILY,
            output_kind=DIAGNOSTIC_PANEL_OUTPUT_KIND,
            display_name="Wave Diagnostic Summary",
            description="Diagnostic panel summarizing wave-only synchrony, phase-gradient, wavefront, and entropy metrics.",
            scope_rule=PER_EXPERIMENT_MANIFEST_SCOPE,
            required_metric_ids=[
                "synchrony_coherence_index",
                "phase_gradient_mean_rad_per_patch",
                "phase_gradient_dispersion_rad_per_patch",
                "wavefront_speed_patch_per_ms",
                "wavefront_curvature_inv_patch",
                "patch_activation_entropy_bits",
            ],
            required_source_artifact_classes=[
                SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
                SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
                WAVE_DIAGNOSTIC_ROWS_ARTIFACT_CLASS,
            ],
            fairness_mode=WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE,
            fairness_note="This output is explicitly wave-only and must stay visually separated from fairness-critical comparison summaries.",
        ),
        build_experiment_comparison_output_definition(
            output_id=MILESTONE_1_DECISION_PANEL_OUTPUT_ID,
            task_family_id=EXPERIMENT_COMPARISON_OUTPUTS_TASK_FAMILY,
            output_kind=DECISION_PANEL_OUTPUT_KIND,
            display_name="Milestone 1 Decision Panel",
            description="Decision-oriented experiment summary that packages the Milestone 1 shared-effect metrics and null-test outcomes into one review surface.",
            scope_rule=PER_EXPERIMENT_MANIFEST_SCOPE,
            required_metric_ids=[
                "direction_selectivity_index",
                "null_direction_suppression_index",
                "on_off_selectivity_index",
                "response_latency_to_peak_ms",
            ],
            required_source_artifact_classes=[
                ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
                ANALYSIS_NULL_TEST_ROWS_ARTIFACT_CLASS,
                EXPERIMENT_BUNDLE_SET_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            fairness_note="The decision panel is part of the locked Milestone 1 evidence surface and must remain driven by shared-comparison metrics plus explicit null-test outcomes.",
        ),
        build_experiment_comparison_output_definition(
            output_id=ANALYSIS_UI_PAYLOAD_OUTPUT_ID,
            task_family_id=EXPERIMENT_COMPARISON_OUTPUTS_TASK_FAMILY,
            output_kind=UI_PAYLOAD_OUTPUT_KIND,
            display_name="Analysis UI Payload",
            description="UI-facing payload that packages shared-comparison summaries, task-decoder outputs, null-test status, and wave diagnostics while preserving scope labels.",
            scope_rule=PER_EXPERIMENT_MANIFEST_SCOPE,
            required_metric_ids=[
                "motion_vector_heading_deg",
                "null_direction_suppression_index",
                "patch_activation_entropy_bits",
                "response_latency_to_peak_ms",
                "synchrony_coherence_index",
                "wavefront_speed_patch_per_ms",
            ],
            required_source_artifact_classes=[
                ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
                ANALYSIS_NULL_TEST_ROWS_ARTIFACT_CLASS,
                WAVE_DIAGNOSTIC_ROWS_ARTIFACT_CLASS,
            ],
            fairness_mode=MIXED_SCOPE_LABELED_FAIRNESS_MODE,
            fairness_note="UI packaging may reference both shared and wave-only sections only if the payload keeps the scopes explicitly separated and never collapses them into one fairness score.",
        ),
    ]


def _default_task_family_catalog() -> list[dict[str, Any]]:
    return [
        build_readout_analysis_task_family_definition(
            task_family_id=MILESTONE_1_SHARED_EFFECTS_TASK_FAMILY,
            display_name="Milestone 1 Shared Effects",
            description="Fair shared-readout metrics tied to the locked Milestone 1 evidence ladder at the T4a/T5a terminal boundary.",
            metric_ids=[
                "direction_selectivity_index",
                "null_direction_suppression_index",
                "on_off_selectivity_index",
                "response_latency_to_peak_ms",
            ],
            output_ids=[],
            null_test_hook_ids=[
                "geometry_shuffle_collapse",
                "polarity_label_swap",
                "seed_stability",
                "stronger_baseline_survival",
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
        ),
        build_readout_analysis_task_family_definition(
            task_family_id=MOTION_DECODER_ESTIMATES_TASK_FAMILY,
            display_name="Motion Decoder Estimates",
            description="Fair task readouts that decode motion-vector or optic-flow summaries from shared readout evidence plus declared task context.",
            metric_ids=[
                "motion_vector_heading_deg",
                "motion_vector_speed_deg_per_s",
                "optic_flow_heading_deg",
                "optic_flow_speed_deg_per_s",
            ],
            output_ids=[MOTION_DECODER_SUMMARY_OUTPUT_ID],
            null_test_hook_ids=["direction_label_swap"],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
        ),
        build_readout_analysis_task_family_definition(
            task_family_id=WAVE_STRUCTURE_DIAGNOSTICS_TASK_FAMILY,
            display_name="Wave Structure Diagnostics",
            description="Morphology-aware wave-only diagnostics that describe synchronization, phase, wavefront geometry, and patch-distribution structure.",
            metric_ids=[
                "patch_activation_entropy_bits",
                "phase_gradient_dispersion_rad_per_patch",
                "phase_gradient_mean_rad_per_patch",
                "synchrony_coherence_index",
                "wavefront_curvature_inv_patch",
                "wavefront_speed_patch_per_ms",
            ],
            output_ids=[WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID],
            null_test_hook_ids=["wave_artifact_presence_guard"],
            fairness_mode=WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE,
        ),
        build_readout_analysis_task_family_definition(
            task_family_id=EXPERIMENT_COMPARISON_OUTPUTS_TASK_FAMILY,
            display_name="Experiment Comparison Outputs",
            description="Experiment-level comparison views and UI-facing payloads that package Milestone 12 metrics without mutating their fairness boundaries.",
            metric_ids=[],
            output_ids=[
                ANALYSIS_UI_PAYLOAD_OUTPUT_ID,
                LATENCY_SHIFT_COMPARISON_OUTPUT_ID,
                MILESTONE_1_DECISION_PANEL_OUTPUT_ID,
                NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID,
            ],
            null_test_hook_ids=[],
            fairness_mode=MIXED_SCOPE_LABELED_FAIRNESS_MODE,
        ),
    ]


def _default_null_test_catalog() -> list[dict[str, Any]]:
    return [
        build_readout_analysis_null_test_hook(
            null_test_id="geometry_shuffle_collapse",
            task_family_id=MILESTONE_1_SHARED_EFFECTS_TASK_FAMILY,
            display_name="Geometry Shuffle Collapse",
            description="Check that the intact surface-minus-baseline effect shrinks or disappears when synapse landing geometry or topology is shuffled.",
            required_metric_ids=[
                "direction_selectivity_index",
                "null_direction_suppression_index",
                "response_latency_to_peak_ms",
            ],
            required_source_artifact_classes=[
                ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
                EXPERIMENT_BUNDLE_SET_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            pass_criterion="The intact shared-readout effect should exceed the shuffled effect in the same comparison family.",
        ),
        build_readout_analysis_null_test_hook(
            null_test_id="stronger_baseline_survival",
            task_family_id=MILESTONE_1_SHARED_EFFECTS_TASK_FAMILY,
            display_name="Stronger Baseline Survival",
            description="Check that the shared-readout effect remains detectable against the stronger reduced baseline P1 rather than only against P0.",
            required_metric_ids=[
                "null_direction_suppression_index",
                "response_latency_to_peak_ms",
            ],
            required_source_artifact_classes=[
                ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
                EXPERIMENT_BUNDLE_SET_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            pass_criterion="The qualitative Milestone 1 effect survives comparison against the declared P1 arm.",
        ),
        build_readout_analysis_null_test_hook(
            null_test_id="seed_stability",
            task_family_id=MILESTONE_1_SHARED_EFFECTS_TASK_FAMILY,
            display_name="Seed Stability",
            description="Check that the effect direction and interpretation remain stable across a declared seed sweep and modest parameter perturbations.",
            required_metric_ids=[
                "null_direction_suppression_index",
                "response_latency_to_peak_ms",
            ],
            required_source_artifact_classes=[
                ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
                EXPERIMENT_BUNDLE_SET_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            pass_criterion="The effect sign and qualitative interpretation stay consistent across the declared seed group.",
        ),
        build_readout_analysis_null_test_hook(
            null_test_id="polarity_label_swap",
            task_family_id=MILESTONE_1_SHARED_EFFECTS_TASK_FAMILY,
            display_name="Polarity Label Swap",
            description="Check that swapping ON/OFF condition labels flips or collapses the polarity-selectivity score instead of leaving it unchanged.",
            required_metric_ids=["on_off_selectivity_index"],
            required_source_artifact_classes=[
                ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
                STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            pass_criterion="The ON/OFF selectivity sign should reverse or collapse under a polarity-label swap control.",
        ),
        build_readout_analysis_null_test_hook(
            null_test_id="direction_label_swap",
            task_family_id=MOTION_DECODER_ESTIMATES_TASK_FAMILY,
            display_name="Direction Label Swap",
            description="Check that permuting preferred/null or directional labels flips or collapses decoded motion estimates rather than leaving them invariant.",
            required_metric_ids=[
                "motion_vector_heading_deg",
                "motion_vector_speed_deg_per_s",
                "optic_flow_heading_deg",
                "optic_flow_speed_deg_per_s",
            ],
            required_source_artifact_classes=[
                ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
                STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
                TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            pass_criterion="Decoder outputs should change materially when their direction labels are deliberately permuted.",
        ),
        build_readout_analysis_null_test_hook(
            null_test_id="wave_artifact_presence_guard",
            task_family_id=WAVE_STRUCTURE_DIAGNOSTICS_TASK_FAMILY,
            display_name="Wave Artifact Presence Guard",
            description="Check that wave diagnostics are emitted only when the required wave extension artifacts exist, especially in mixed-fidelity runs.",
            required_metric_ids=[
                "patch_activation_entropy_bits",
                "synchrony_coherence_index",
                "wavefront_speed_patch_per_ms",
            ],
            required_source_artifact_classes=[
                SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
                SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
            ],
            fairness_mode=WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE,
            pass_criterion="Missing wave extensions must produce explicit unavailable diagnostics rather than silently fabricated shared metrics.",
        ),
    ]


def _default_ui_facing_output_ids() -> list[str]:
    return [
        ANALYSIS_UI_PAYLOAD_OUTPUT_ID,
        LATENCY_SHIFT_COMPARISON_OUTPUT_ID,
        MILESTONE_1_DECISION_PANEL_OUTPUT_ID,
        MOTION_DECODER_SUMMARY_OUTPUT_ID,
        NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID,
        WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID,
    ]


def _derived_ui_facing_output_ids(
    output_definitions: Sequence[Mapping[str, Any]],
) -> list[str]:
    return sorted(
        {
            _normalize_identifier(
                item["output_id"],
                field_name="output_definitions.output_id",
            )
            for item in output_definitions
        }
    )


def _normalize_metric_catalog(payload: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("metric_catalog must be a list.")
    normalized = [parse_readout_analysis_metric_definition(item) for item in payload]
    if not normalized:
        raise ValueError("metric_catalog must contain at least one metric definition.")
    sorted_records = sorted(
        normalized,
        key=lambda item: (
            item["metric_id"],
            item["metric_class"],
            item["task_family_id"],
        ),
    )
    seen_ids: set[str] = set()
    for item in sorted_records:
        metric_id = str(item["metric_id"])
        if metric_id in seen_ids:
            raise ValueError(f"metric_catalog contains duplicate metric_id {metric_id!r}.")
        seen_ids.add(metric_id)
    return sorted_records


def _normalize_output_catalog(payload: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("output_catalog must be a list.")
    normalized = [parse_experiment_comparison_output_definition(item) for item in payload]
    if not normalized:
        raise ValueError("output_catalog must contain at least one output definition.")
    sorted_records = sorted(
        normalized,
        key=lambda item: (
            item["output_id"],
            item["output_kind"],
            item["task_family_id"],
        ),
    )
    seen_ids: set[str] = set()
    for item in sorted_records:
        output_id = str(item["output_id"])
        if output_id in seen_ids:
            raise ValueError(f"output_catalog contains duplicate output_id {output_id!r}.")
        seen_ids.add(output_id)
    return sorted_records


def _normalize_task_family_catalog(payload: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("task_family_catalog must be a list.")
    normalized = [parse_readout_analysis_task_family_definition(item) for item in payload]
    if not normalized:
        raise ValueError("task_family_catalog must contain at least one task family definition.")
    sorted_records = sorted(
        normalized,
        key=lambda item: item["task_family_id"],
    )
    seen_ids: set[str] = set()
    for item in sorted_records:
        task_family_id = str(item["task_family_id"])
        if task_family_id in seen_ids:
            raise ValueError(
                f"task_family_catalog contains duplicate task_family_id {task_family_id!r}."
            )
        seen_ids.add(task_family_id)
    return sorted_records


def _normalize_null_test_catalog(payload: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("null_test_catalog must be a list.")
    normalized = [parse_readout_analysis_null_test_hook(item) for item in payload]
    if not normalized:
        raise ValueError("null_test_catalog must contain at least one null-test hook.")
    sorted_records = sorted(
        normalized,
        key=lambda item: (
            item["null_test_id"],
            item["task_family_id"],
        ),
    )
    seen_ids: set[str] = set()
    for item in sorted_records:
        null_test_id = str(item["null_test_id"])
        if null_test_id in seen_ids:
            raise ValueError(
                f"null_test_catalog contains duplicate null_test_id {null_test_id!r}."
            )
        seen_ids.add(null_test_id)
    return sorted_records


def _extract_readout_analysis_contract_mapping(record: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = record.get("readout_analysis_contract")
    if isinstance(nested, Mapping):
        return nested
    return record


def _normalize_metric_class(value: Any) -> str:
    metric_class = _normalize_identifier(value, field_name="metric_class")
    if metric_class not in SUPPORTED_METRIC_CLASSES:
        raise ValueError(
            f"metric_class must be one of {list(SUPPORTED_METRIC_CLASSES)!r}, got {metric_class!r}."
        )
    return metric_class


def _normalize_output_class(value: Any) -> str:
    output_class = _normalize_identifier(value, field_name="output_class")
    if output_class not in SUPPORTED_OUTPUT_CLASSES:
        raise ValueError(
            f"output_class must be one of {list(SUPPORTED_OUTPUT_CLASSES)!r}, got {output_class!r}."
        )
    return output_class


def _normalize_output_kind(value: Any) -> str:
    output_kind = _normalize_identifier(value, field_name="output_kind")
    if output_kind not in SUPPORTED_OUTPUT_KINDS:
        raise ValueError(
            f"output_kind must be one of {list(SUPPORTED_OUTPUT_KINDS)!r}, got {output_kind!r}."
        )
    return output_kind


def _normalize_fairness_mode(value: Any) -> str:
    fairness_mode = _normalize_identifier(value, field_name="fairness_mode")
    if fairness_mode not in SUPPORTED_FAIRNESS_MODES:
        raise ValueError(
            f"fairness_mode must be one of {list(SUPPORTED_FAIRNESS_MODES)!r}, got {fairness_mode!r}."
        )
    return fairness_mode


def _normalize_scope_rule(value: Any) -> str:
    scope_rule = _normalize_identifier(value, field_name="scope_rule")
    if scope_rule not in SUPPORTED_SCOPE_RULES:
        raise ValueError(
            f"scope_rule must be one of {list(SUPPORTED_SCOPE_RULES)!r}, got {scope_rule!r}."
        )
    return scope_rule


def _normalize_source_artifact_class_list(payload: Any, *, field_name: str) -> list[str]:
    values = _normalize_identifier_list(payload, field_name=field_name, allow_empty=False)
    unknown_values = sorted(set(values) - set(SUPPORTED_SOURCE_ARTIFACT_CLASSES))
    if unknown_values:
        raise ValueError(
            f"{field_name} contains unsupported source artifact classes {unknown_values!r}."
        )
    return values


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


def _normalize_known_constant_list(
    payload: Any,
    *,
    field_name: str,
    supported_values: Sequence[str],
) -> list[str]:
    normalized = _normalize_nonempty_string_list(payload, field_name=field_name)
    if set(normalized) != set(supported_values):
        raise ValueError(
            f"{field_name} must contain exactly {list(supported_values)!r}, got {normalized!r}."
        )
    return list(sorted(supported_values))
