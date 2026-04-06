from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .dashboard_session_contract import DASHBOARD_SESSION_CONTRACT_VERSION
from .experiment_analysis_contract import EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION
from .io_utils import write_json
from .simulator_result_contract import SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION
from .stimulus_contract import (
    ASSET_STATUS_READY,
    DEFAULT_HASH_ALGORITHM,
    _normalize_asset_status,
    _normalize_identifier,
    _normalize_json_mapping,
    _normalize_nonempty_string,
)
from .validation_contract import VALIDATION_LADDER_CONTRACT_VERSION


EXPERIMENT_SUITE_CONTRACT_VERSION = "experiment_suite.v1"
EXPERIMENT_SUITE_DESIGN_NOTE = "docs/experiment_orchestration_design.md"
EXPERIMENT_SUITE_DESIGN_NOTE_VERSION = "experiment_suite_design_note.v1"
SIMULATION_PLAN_VERSION = "simulation_plan.v1"

ORCHESTRATION_OWNER_JACK = "jack"
SCIENTIFIC_OWNER_GRANT = "grant"

STIMULUS_CONTEXT_DIMENSION_GROUP = "stimulus_context"
STIMULUS_MOTION_DIMENSION_GROUP = "stimulus_motion"
STIMULUS_SIGNAL_DIMENSION_GROUP = "stimulus_signal"
CIRCUIT_SELECTION_DIMENSION_GROUP = "circuit_selection"
WAVE_MODEL_DIMENSION_GROUP = "wave_model"
GEOMETRY_FIDELITY_DIMENSION_GROUP = "geometry_fidelity"
RUNTIME_DIMENSION_GROUP = "runtime"

SCENE_TYPE_DIMENSION_ID = "scene_type"
MOTION_DIRECTION_DIMENSION_ID = "motion_direction"
MOTION_SPEED_DIMENSION_ID = "motion_speed"
CONTRAST_LEVEL_DIMENSION_ID = "contrast_level"
NOISE_LEVEL_DIMENSION_ID = "noise_level"
ACTIVE_SUBSET_DIMENSION_ID = "active_subset"
WAVE_KERNEL_DIMENSION_ID = "wave_kernel"
COUPLING_MODE_DIMENSION_ID = "coupling_mode"
MESH_RESOLUTION_DIMENSION_ID = "mesh_resolution"
SOLVER_SETTINGS_DIMENSION_ID = "solver_settings"
FIDELITY_CLASS_DIMENSION_ID = "fidelity_class"

SUPPORTED_DIMENSION_IDS = (
    SCENE_TYPE_DIMENSION_ID,
    MOTION_DIRECTION_DIMENSION_ID,
    MOTION_SPEED_DIMENSION_ID,
    CONTRAST_LEVEL_DIMENSION_ID,
    NOISE_LEVEL_DIMENSION_ID,
    ACTIVE_SUBSET_DIMENSION_ID,
    WAVE_KERNEL_DIMENSION_ID,
    COUPLING_MODE_DIMENSION_ID,
    MESH_RESOLUTION_DIMENSION_ID,
    SOLVER_SETTINGS_DIMENSION_ID,
    FIDELITY_CLASS_DIMENSION_ID,
)

NO_WAVES_ABLATION_FAMILY_ID = "no_waves"
WAVES_ONLY_SELECTED_CELL_CLASSES_ABLATION_FAMILY_ID = (
    "waves_only_selected_cell_classes"
)
NO_LATERAL_COUPLING_ABLATION_FAMILY_ID = "no_lateral_coupling"
SHUFFLE_SYNAPSE_LOCATIONS_ABLATION_FAMILY_ID = "shuffle_synapse_locations"
SHUFFLE_MORPHOLOGY_ABLATION_FAMILY_ID = "shuffle_morphology"
COARSEN_GEOMETRY_ABLATION_FAMILY_ID = "coarsen_geometry"
ALTERED_SIGN_ASSUMPTIONS_ABLATION_FAMILY_ID = "altered_sign_assumptions"
ALTERED_DELAY_ASSUMPTIONS_ABLATION_FAMILY_ID = "altered_delay_assumptions"

SUPPORTED_ABLATION_FAMILY_IDS = (
    NO_WAVES_ABLATION_FAMILY_ID,
    WAVES_ONLY_SELECTED_CELL_CLASSES_ABLATION_FAMILY_ID,
    NO_LATERAL_COUPLING_ABLATION_FAMILY_ID,
    SHUFFLE_SYNAPSE_LOCATIONS_ABLATION_FAMILY_ID,
    SHUFFLE_MORPHOLOGY_ABLATION_FAMILY_ID,
    COARSEN_GEOMETRY_ABLATION_FAMILY_ID,
    ALTERED_SIGN_ASSUMPTIONS_ABLATION_FAMILY_ID,
    ALTERED_DELAY_ASSUMPTIONS_ABLATION_FAMILY_ID,
)

BASE_CONDITION_LINEAGE_KIND = "base_condition"
SEED_REPLICATE_LINEAGE_KIND = "seed_replicate"
ABLATION_VARIANT_LINEAGE_KIND = "ablation_variant"
SEEDED_ABLATION_VARIANT_LINEAGE_KIND = "seeded_ablation_variant"

SUPPORTED_LINEAGE_KINDS = (
    BASE_CONDITION_LINEAGE_KIND,
    SEED_REPLICATE_LINEAGE_KIND,
    ABLATION_VARIANT_LINEAGE_KIND,
    SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
)

WORK_ITEM_STATUS_PLANNED = "planned"
WORK_ITEM_STATUS_READY = "ready"
WORK_ITEM_STATUS_RUNNING = "running"
WORK_ITEM_STATUS_SUCCEEDED = "succeeded"
WORK_ITEM_STATUS_PARTIAL = "partial"
WORK_ITEM_STATUS_FAILED = "failed"
WORK_ITEM_STATUS_BLOCKED = "blocked"
WORK_ITEM_STATUS_SKIPPED = "skipped"

SUPPORTED_WORK_ITEM_STATUSES = (
    WORK_ITEM_STATUS_PLANNED,
    WORK_ITEM_STATUS_READY,
    WORK_ITEM_STATUS_RUNNING,
    WORK_ITEM_STATUS_SUCCEEDED,
    WORK_ITEM_STATUS_PARTIAL,
    WORK_ITEM_STATUS_FAILED,
    WORK_ITEM_STATUS_BLOCKED,
    WORK_ITEM_STATUS_SKIPPED,
)

RESUMABLE_WORK_ITEM_STATUSES = (
    WORK_ITEM_STATUS_PLANNED,
    WORK_ITEM_STATUS_READY,
    WORK_ITEM_STATUS_RUNNING,
    WORK_ITEM_STATUS_PARTIAL,
    WORK_ITEM_STATUS_FAILED,
    WORK_ITEM_STATUS_BLOCKED,
)

WAITING_WORK_ITEM_STATUSES = (
    WORK_ITEM_STATUS_PLANNED,
    WORK_ITEM_STATUS_READY,
    WORK_ITEM_STATUS_BLOCKED,
)

SATISFIED_DEPENDENCY_WORK_ITEM_STATUSES = (
    WORK_ITEM_STATUS_SUCCEEDED,
    WORK_ITEM_STATUS_SKIPPED,
)

STAGE_EXECUTION_RESULT_WORK_ITEM_STATUSES = (
    WORK_ITEM_STATUS_SUCCEEDED,
    WORK_ITEM_STATUS_PARTIAL,
    WORK_ITEM_STATUS_FAILED,
    WORK_ITEM_STATUS_BLOCKED,
    WORK_ITEM_STATUS_SKIPPED,
)

WORK_ITEM_STATUS_ROLLUP_PRIORITY = (
    WORK_ITEM_STATUS_RUNNING,
    WORK_ITEM_STATUS_FAILED,
    WORK_ITEM_STATUS_PARTIAL,
    WORK_ITEM_STATUS_BLOCKED,
    WORK_ITEM_STATUS_READY,
    WORK_ITEM_STATUS_PLANNED,
    WORK_ITEM_STATUS_SKIPPED,
    WORK_ITEM_STATUS_SUCCEEDED,
)
_WORK_ITEM_STATUS_ROLLUP_INDEX = {
    status: index for index, status in enumerate(WORK_ITEM_STATUS_ROLLUP_PRIORITY)
}


def work_item_status_allows_resume(status: str) -> bool:
    return str(status) in set(RESUMABLE_WORK_ITEM_STATUSES)


def ordered_experiment_suite_work_item_status_counts(
    counts: Mapping[str, Any] | None = None,
) -> dict[str, int]:
    ordered = {
        status: 0 for status in SUPPORTED_WORK_ITEM_STATUSES
    }
    if counts is None:
        return ordered
    for raw_status, raw_count in counts.items():
        status = _normalize_identifier(
            raw_status,
            field_name="work_item_status_counts.status",
        )
        if status not in ordered:
            raise ValueError(
                f"Unsupported experiment-suite work-item status {status!r}."
            )
        ordered[status] = int(raw_count)
    return ordered


def roll_up_experiment_suite_work_item_statuses(
    statuses: Sequence[str],
    *,
    default_status: str = WORK_ITEM_STATUS_PLANNED,
) -> str:
    if default_status not in _WORK_ITEM_STATUS_ROLLUP_INDEX:
        raise ValueError(
            f"default_status must be one of {WORK_ITEM_STATUS_ROLLUP_PRIORITY!r}."
        )
    resolved_statuses = [str(item) for item in statuses]
    if not resolved_statuses:
        return default_status
    unknown = sorted(
        {status for status in resolved_statuses if status not in _WORK_ITEM_STATUS_ROLLUP_INDEX}
    )
    if unknown:
        raise ValueError(
            f"Unsupported experiment-suite work-item statuses {unknown!r}."
        )
    return min(
        resolved_statuses,
        key=lambda status: int(_WORK_ITEM_STATUS_ROLLUP_INDEX[status]),
    )

SUITE_MANIFEST_SOURCE_KIND = "suite_manifest"
EXPERIMENT_MANIFEST_SOURCE_KIND = "experiment_manifest"
SIMULATION_PLAN_SOURCE_KIND = "simulation_plan"
SIMULATOR_RESULT_SOURCE_KIND = "simulator_result_bundle"
EXPERIMENT_ANALYSIS_SOURCE_KIND = "experiment_analysis_bundle"
VALIDATION_BUNDLE_SOURCE_KIND = "validation_bundle"
DASHBOARD_SESSION_SOURCE_KIND = "dashboard_session"
SUMMARY_TABLE_SOURCE_KIND = "summary_table"
COMPARISON_PLOT_SOURCE_KIND = "comparison_plot"
REVIEW_ARTIFACT_SOURCE_KIND = "review_artifact"

SUPPORTED_ARTIFACT_SOURCE_KINDS = (
    SUITE_MANIFEST_SOURCE_KIND,
    EXPERIMENT_MANIFEST_SOURCE_KIND,
    SIMULATION_PLAN_SOURCE_KIND,
    SIMULATOR_RESULT_SOURCE_KIND,
    EXPERIMENT_ANALYSIS_SOURCE_KIND,
    VALIDATION_BUNDLE_SOURCE_KIND,
    DASHBOARD_SESSION_SOURCE_KIND,
    SUMMARY_TABLE_SOURCE_KIND,
    COMPARISON_PLOT_SOURCE_KIND,
    REVIEW_ARTIFACT_SOURCE_KIND,
)

UPSTREAM_MANIFEST_ARTIFACT_SCOPE = "upstream_manifest"
UPSTREAM_PLAN_ARTIFACT_SCOPE = "upstream_plan"
DOWNSTREAM_BUNDLE_ARTIFACT_SCOPE = "downstream_bundle"
SUMMARY_OUTPUT_ARTIFACT_SCOPE = "summary_output"
PLOT_OUTPUT_ARTIFACT_SCOPE = "plot_output"
REVIEW_OUTPUT_ARTIFACT_SCOPE = "review_output"

SUPPORTED_ARTIFACT_SCOPES = (
    UPSTREAM_MANIFEST_ARTIFACT_SCOPE,
    UPSTREAM_PLAN_ARTIFACT_SCOPE,
    DOWNSTREAM_BUNDLE_ARTIFACT_SCOPE,
    SUMMARY_OUTPUT_ARTIFACT_SCOPE,
    PLOT_OUTPUT_ARTIFACT_SCOPE,
    REVIEW_OUTPUT_ARTIFACT_SCOPE,
)

SUITE_MANIFEST_INPUT_ROLE_ID = "suite_manifest_input"
EXPERIMENT_MANIFEST_INPUT_ROLE_ID = "experiment_manifest_input"
SIMULATION_PLAN_ROLE_ID = "simulation_plan"
SIMULATOR_RESULT_BUNDLE_ROLE_ID = "simulator_result_bundle"
EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID = "experiment_analysis_bundle"
VALIDATION_BUNDLE_ROLE_ID = "validation_bundle"
DASHBOARD_SESSION_ROLE_ID = "dashboard_session"
SUMMARY_TABLE_ROLE_ID = "summary_table"
COMPARISON_PLOT_ROLE_ID = "comparison_plot"
REVIEW_ARTIFACT_ROLE_ID = "review_artifact"

SUPPORTED_ARTIFACT_ROLE_IDS = (
    SUITE_MANIFEST_INPUT_ROLE_ID,
    EXPERIMENT_MANIFEST_INPUT_ROLE_ID,
    SIMULATION_PLAN_ROLE_ID,
    SIMULATOR_RESULT_BUNDLE_ROLE_ID,
    EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
    VALIDATION_BUNDLE_ROLE_ID,
    DASHBOARD_SESSION_ROLE_ID,
    SUMMARY_TABLE_ROLE_ID,
    COMPARISON_PLOT_ROLE_ID,
    REVIEW_ARTIFACT_ROLE_ID,
)

SUITE_SPEC_HASH_HOOK_ID = "suite_spec_hash"
SUITE_CELL_ID_HOOK_ID = "suite_cell_id"
PARENT_LINEAGE_REFERENCE_HOOK_ID = "parent_lineage_reference"
SIMULATION_SEED_SCOPE_HOOK_ID = "simulation_seed_scope"
ABLATION_SEED_SCOPE_HOOK_ID = "ablation_seed_scope"
ARTIFACT_REFERENCE_CATALOG_HOOK_ID = "artifact_reference_catalog"
STABLE_DISCOVERY_ORDER_HOOK_ID = "stable_discovery_order"

SUPPORTED_REPRODUCIBILITY_HOOK_IDS = (
    SUITE_SPEC_HASH_HOOK_ID,
    SUITE_CELL_ID_HOOK_ID,
    PARENT_LINEAGE_REFERENCE_HOOK_ID,
    SIMULATION_SEED_SCOPE_HOOK_ID,
    ABLATION_SEED_SCOPE_HOOK_ID,
    ARTIFACT_REFERENCE_CATALOG_HOOK_ID,
    STABLE_DISCOVERY_ORDER_HOOK_ID,
)

COMPOSED_CONTRACTS = (
    SIMULATION_PLAN_VERSION,
    SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
    EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION,
    VALIDATION_LADDER_CONTRACT_VERSION,
    DASHBOARD_SESSION_CONTRACT_VERSION,
)


def build_experiment_suite_dimension_definition(
    *,
    dimension_id: str,
    display_name: str,
    description: str,
    dimension_group: str,
    sequence_index: int,
    discovery_note: str,
) -> dict[str, Any]:
    return parse_experiment_suite_dimension_definition(
        {
            "dimension_id": dimension_id,
            "display_name": display_name,
            "description": description,
            "dimension_group": dimension_group,
            "sequence_index": int(sequence_index),
            "discovery_note": discovery_note,
        }
    )


def build_experiment_suite_ablation_family_definition(
    *,
    ablation_family_id: str,
    display_name: str,
    description: str,
    sequence_index: int,
    required: bool,
    uses_perturbation_seed: bool,
    discovery_note: str,
) -> dict[str, Any]:
    return parse_experiment_suite_ablation_family_definition(
        {
            "ablation_family_id": ablation_family_id,
            "display_name": display_name,
            "description": description,
            "sequence_index": int(sequence_index),
            "required": bool(required),
            "uses_perturbation_seed": bool(uses_perturbation_seed),
            "discovery_note": discovery_note,
        }
    )


def build_experiment_suite_lineage_definition(
    *,
    lineage_kind: str,
    display_name: str,
    description: str,
    sequence_index: int,
    requires_parent: bool,
    introduces_simulation_seed: bool,
    introduces_ablation_family: bool,
) -> dict[str, Any]:
    return parse_experiment_suite_lineage_definition(
        {
            "lineage_kind": lineage_kind,
            "display_name": display_name,
            "description": description,
            "sequence_index": int(sequence_index),
            "requires_parent": bool(requires_parent),
            "introduces_simulation_seed": bool(introduces_simulation_seed),
            "introduces_ablation_family": bool(introduces_ablation_family),
        }
    )


def build_experiment_suite_work_item_status_definition(
    *,
    status_id: str,
    display_name: str,
    description: str,
    sequence_index: int,
    resume_allowed: bool,
) -> dict[str, Any]:
    return parse_experiment_suite_work_item_status_definition(
        {
            "status_id": status_id,
            "display_name": display_name,
            "description": description,
            "sequence_index": int(sequence_index),
            "resume_allowed": bool(resume_allowed),
        }
    )


def build_experiment_suite_artifact_role_definition(
    *,
    artifact_role_id: str,
    display_name: str,
    description: str,
    source_kind: str,
    artifact_scope: str,
    sequence_index: int,
    discovery_note: str,
    required_contract_version: str | None = None,
) -> dict[str, Any]:
    return parse_experiment_suite_artifact_role_definition(
        {
            "artifact_role_id": artifact_role_id,
            "display_name": display_name,
            "description": description,
            "source_kind": source_kind,
            "artifact_scope": artifact_scope,
            "sequence_index": int(sequence_index),
            "discovery_note": discovery_note,
            "required_contract_version": required_contract_version,
        }
    )


def build_experiment_suite_reproducibility_hook_definition(
    *,
    hook_id: str,
    display_name: str,
    description: str,
    sequence_index: int,
) -> dict[str, Any]:
    return parse_experiment_suite_reproducibility_hook_definition(
        {
            "hook_id": hook_id,
            "display_name": display_name,
            "description": description,
            "sequence_index": int(sequence_index),
        }
    )


def build_experiment_suite_contract_metadata(
    *,
    dimension_definitions: Sequence[Mapping[str, Any]] | None = None,
    ablation_family_definitions: Sequence[Mapping[str, Any]] | None = None,
    lineage_definitions: Sequence[Mapping[str, Any]] | None = None,
    work_item_status_definitions: Sequence[Mapping[str, Any]] | None = None,
    artifact_role_definitions: Sequence[Mapping[str, Any]] | None = None,
    reproducibility_hook_definitions: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {
        "contract_version": EXPERIMENT_SUITE_CONTRACT_VERSION,
        "design_note": EXPERIMENT_SUITE_DESIGN_NOTE,
        "design_note_version": EXPERIMENT_SUITE_DESIGN_NOTE_VERSION,
        "composed_contracts": list(COMPOSED_CONTRACTS),
        "ownership_boundary": default_experiment_suite_ownership_boundary(),
        "lineage_invariants": list(_default_lineage_invariants()),
        "reproducibility_invariants": list(_default_reproducibility_invariants()),
        "dimension_catalog": list(
            dimension_definitions
            if dimension_definitions is not None
            else _default_dimension_catalog()
        ),
        "ablation_family_catalog": list(
            ablation_family_definitions
            if ablation_family_definitions is not None
            else _default_ablation_family_catalog()
        ),
        "lineage_catalog": list(
            lineage_definitions
            if lineage_definitions is not None
            else _default_lineage_catalog()
        ),
        "work_item_status_catalog": list(
            work_item_status_definitions
            if work_item_status_definitions is not None
            else _default_work_item_status_catalog()
        ),
        "artifact_role_catalog": list(
            artifact_role_definitions
            if artifact_role_definitions is not None
            else _default_artifact_role_catalog()
        ),
        "reproducibility_hook_catalog": list(
            reproducibility_hook_definitions
            if reproducibility_hook_definitions is not None
            else _default_reproducibility_hook_catalog()
        ),
    }
    return parse_experiment_suite_contract_metadata(payload)


def parse_experiment_suite_contract_metadata(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("experiment_suite contract metadata must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "design_note",
        "design_note_version",
        "composed_contracts",
        "ownership_boundary",
        "lineage_invariants",
        "reproducibility_invariants",
        "dimension_catalog",
        "ablation_family_catalog",
        "lineage_catalog",
        "work_item_status_catalog",
        "artifact_role_catalog",
        "reproducibility_hook_catalog",
    )
    missing = [field for field in required_fields if field not in normalized]
    if missing:
        raise ValueError(
            "experiment_suite contract metadata is missing required fields: "
            f"{missing!r}."
        )
    contract_version = _normalize_nonempty_string(
        normalized["contract_version"],
        field_name="contract_version",
    )
    if contract_version != EXPERIMENT_SUITE_CONTRACT_VERSION:
        raise ValueError(
            "experiment_suite contract_version must be "
            f"{EXPERIMENT_SUITE_CONTRACT_VERSION!r}."
        )
    design_note = _normalize_nonempty_string(
        normalized["design_note"],
        field_name="design_note",
    )
    if design_note != EXPERIMENT_SUITE_DESIGN_NOTE:
        raise ValueError(
            "experiment_suite design_note must be "
            f"{EXPERIMENT_SUITE_DESIGN_NOTE!r}."
        )
    design_note_version = _normalize_nonempty_string(
        normalized["design_note_version"],
        field_name="design_note_version",
    )
    if design_note_version != EXPERIMENT_SUITE_DESIGN_NOTE_VERSION:
        raise ValueError(
            "experiment_suite design_note_version must be "
            f"{EXPERIMENT_SUITE_DESIGN_NOTE_VERSION!r}."
        )
    composed_contracts = _normalize_nonempty_string_list(
        normalized["composed_contracts"],
        field_name="composed_contracts",
    )
    ownership_boundary = _normalize_ownership_boundary(
        normalized["ownership_boundary"]
    )
    lineage_invariants = _normalize_nonempty_string_list(
        normalized["lineage_invariants"],
        field_name="lineage_invariants",
    )
    reproducibility_invariants = _normalize_nonempty_string_list(
        normalized["reproducibility_invariants"],
        field_name="reproducibility_invariants",
    )
    dimension_catalog = _normalize_dimension_catalog(normalized["dimension_catalog"])
    ablation_family_catalog = _normalize_ablation_family_catalog(
        normalized["ablation_family_catalog"]
    )
    lineage_catalog = _normalize_lineage_catalog(normalized["lineage_catalog"])
    work_item_status_catalog = _normalize_work_item_status_catalog(
        normalized["work_item_status_catalog"]
    )
    artifact_role_catalog = _normalize_artifact_role_catalog(
        normalized["artifact_role_catalog"]
    )
    reproducibility_hook_catalog = _normalize_reproducibility_hook_catalog(
        normalized["reproducibility_hook_catalog"]
    )
    _require_exact_ids(
        [item["dimension_id"] for item in dimension_catalog],
        expected_ids=SUPPORTED_DIMENSION_IDS,
        field_name="dimension_catalog",
    )
    _require_exact_ids(
        [item["ablation_family_id"] for item in ablation_family_catalog],
        expected_ids=SUPPORTED_ABLATION_FAMILY_IDS,
        field_name="ablation_family_catalog",
    )
    _require_exact_ids(
        [item["lineage_kind"] for item in lineage_catalog],
        expected_ids=SUPPORTED_LINEAGE_KINDS,
        field_name="lineage_catalog",
    )
    _require_exact_ids(
        [item["status_id"] for item in work_item_status_catalog],
        expected_ids=SUPPORTED_WORK_ITEM_STATUSES,
        field_name="work_item_status_catalog",
    )
    _require_exact_ids(
        [item["artifact_role_id"] for item in artifact_role_catalog],
        expected_ids=SUPPORTED_ARTIFACT_ROLE_IDS,
        field_name="artifact_role_catalog",
    )
    _require_exact_ids(
        [item["source_kind"] for item in artifact_role_catalog],
        expected_ids=SUPPORTED_ARTIFACT_SOURCE_KINDS,
        field_name="artifact_role_catalog.source_kinds",
    )
    _require_exact_ids(
        [item["artifact_scope"] for item in artifact_role_catalog],
        expected_ids=SUPPORTED_ARTIFACT_SCOPES,
        field_name="artifact_role_catalog.artifact_scopes",
    )
    _require_exact_ids(
        [item["hook_id"] for item in reproducibility_hook_catalog],
        expected_ids=SUPPORTED_REPRODUCIBILITY_HOOK_IDS,
        field_name="reproducibility_hook_catalog",
    )
    _require_exact_strings(
        composed_contracts,
        expected_values=COMPOSED_CONTRACTS,
        field_name="composed_contracts",
    )

    return {
        "contract_version": contract_version,
        "design_note": design_note,
        "design_note_version": design_note_version,
        "composed_contracts": composed_contracts,
        "ownership_boundary": ownership_boundary,
        "lineage_invariants": lineage_invariants,
        "reproducibility_invariants": reproducibility_invariants,
        "supported_dimension_ids": [
            item["dimension_id"] for item in dimension_catalog
        ],
        "supported_ablation_family_ids": [
            item["ablation_family_id"] for item in ablation_family_catalog
        ],
        "required_ablation_family_ids": [
            item["ablation_family_id"]
            for item in ablation_family_catalog
            if item["required"]
        ],
        "supported_lineage_kinds": [
            item["lineage_kind"] for item in lineage_catalog
        ],
        "supported_work_item_statuses": [
            item["status_id"] for item in work_item_status_catalog
        ],
        "supported_artifact_role_ids": [
            item["artifact_role_id"] for item in artifact_role_catalog
        ],
        "supported_artifact_source_kinds": _unique_ordered(
            item["source_kind"] for item in artifact_role_catalog
        ),
        "supported_artifact_scopes": _unique_ordered(
            item["artifact_scope"] for item in artifact_role_catalog
        ),
        "supported_reproducibility_hook_ids": [
            item["hook_id"] for item in reproducibility_hook_catalog
        ],
        "dimension_catalog": dimension_catalog,
        "ablation_family_catalog": ablation_family_catalog,
        "lineage_catalog": lineage_catalog,
        "work_item_status_catalog": work_item_status_catalog,
        "artifact_role_catalog": artifact_role_catalog,
        "reproducibility_hook_catalog": reproducibility_hook_catalog,
    }


def write_experiment_suite_contract_metadata(
    contract_metadata: Mapping[str, Any],
    output_path: str | Path,
) -> Path:
    normalized = parse_experiment_suite_contract_metadata(contract_metadata)
    return write_json(normalized, Path(output_path).resolve())


def load_experiment_suite_contract_metadata(metadata_path: str | Path) -> dict[str, Any]:
    with Path(metadata_path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_experiment_suite_contract_metadata(payload)


def build_experiment_suite_dimension_assignment(
    *,
    dimension_id: str,
    value_id: str,
    value_label: str | None = None,
    parameter_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return parse_experiment_suite_dimension_assignment(
        {
            "dimension_id": dimension_id,
            "value_id": value_id,
            "value_label": value_label if value_label is not None else value_id,
            "parameter_snapshot": dict(parameter_snapshot or {}),
        }
    )


def parse_experiment_suite_dimension_assignment(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("suite dimension assignment must be a mapping.")
    if "dimension_id" not in payload or "value_id" not in payload:
        raise ValueError(
            "suite dimension assignment requires dimension_id and value_id."
        )
    normalized_value_id = _normalize_identifier(
        payload["value_id"],
        field_name="dimension_assignment.value_id",
    )
    return {
        "dimension_id": _normalize_identifier(
            payload["dimension_id"],
            field_name="dimension_assignment.dimension_id",
        ),
        "value_id": normalized_value_id,
        "value_label": _normalize_nonempty_string(
            payload.get("value_label", normalized_value_id),
            field_name="dimension_assignment.value_label",
        ),
        "parameter_snapshot": _normalize_json_mapping(
            payload.get("parameter_snapshot", {}),
            field_name="dimension_assignment.parameter_snapshot",
        ),
    }


def build_experiment_suite_ablation_reference(
    *,
    ablation_family_id: str,
    variant_id: str,
    display_name: str | None = None,
    parameter_snapshot: Mapping[str, Any] | None = None,
    perturbation_seed: int | None = None,
) -> dict[str, Any]:
    return parse_experiment_suite_ablation_reference(
        {
            "ablation_family_id": ablation_family_id,
            "variant_id": variant_id,
            "display_name": display_name if display_name is not None else variant_id,
            "parameter_snapshot": dict(parameter_snapshot or {}),
            "perturbation_seed": perturbation_seed,
        }
    )


def parse_experiment_suite_ablation_reference(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("suite ablation reference must be a mapping.")
    if "ablation_family_id" not in payload or "variant_id" not in payload:
        raise ValueError(
            "suite ablation reference requires ablation_family_id and variant_id."
        )
    normalized_variant_id = _normalize_identifier(
        payload["variant_id"],
        field_name="ablation_reference.variant_id",
    )
    return {
        "ablation_family_id": _normalize_identifier(
            payload["ablation_family_id"],
            field_name="ablation_reference.ablation_family_id",
        ),
        "variant_id": normalized_variant_id,
        "display_name": _normalize_nonempty_string(
            payload.get("display_name", normalized_variant_id),
            field_name="ablation_reference.display_name",
        ),
        "parameter_snapshot": _normalize_json_mapping(
            payload.get("parameter_snapshot", {}),
            field_name="ablation_reference.parameter_snapshot",
        ),
        "perturbation_seed": _normalize_optional_int(
            payload.get("perturbation_seed"),
            field_name="ablation_reference.perturbation_seed",
        ),
    }


def build_experiment_suite_cell_metadata(
    *,
    suite_cell_id: str,
    display_name: str,
    lineage_kind: str,
    dimension_assignments: Sequence[Mapping[str, Any]],
    ablation_references: Sequence[Mapping[str, Any]] | None = None,
    parent_cell_id: str | None = None,
    root_cell_id: str | None = None,
    simulation_seed: int | None = None,
) -> dict[str, Any]:
    payload = {
        "suite_cell_id": suite_cell_id,
        "display_name": display_name,
        "lineage_kind": lineage_kind,
        "dimension_assignments": list(dimension_assignments),
        "ablation_references": list(ablation_references or []),
        "parent_cell_id": parent_cell_id,
        "root_cell_id": root_cell_id,
        "simulation_seed": simulation_seed,
    }
    return parse_experiment_suite_cell_metadata(payload)


def parse_experiment_suite_cell_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("suite cell metadata must be a mapping.")
    required_fields = (
        "suite_cell_id",
        "display_name",
        "lineage_kind",
        "dimension_assignments",
    )
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(f"suite cell metadata is missing required fields: {missing!r}.")
    suite_cell_id = _normalize_identifier(
        payload["suite_cell_id"],
        field_name="suite_cell.suite_cell_id",
    )
    lineage_kind = _normalize_identifier(
        payload["lineage_kind"],
        field_name="suite_cell.lineage_kind",
    )
    parent_cell_id = _normalize_optional_identifier(
        payload.get("parent_cell_id"),
        field_name="suite_cell.parent_cell_id",
    )
    root_cell_id = _normalize_optional_identifier(
        payload.get("root_cell_id"),
        field_name="suite_cell.root_cell_id",
    )
    if root_cell_id is None:
        root_cell_id = suite_cell_id if parent_cell_id is None else None
    dimension_assignments = _normalize_dimension_assignment_catalog(
        payload["dimension_assignments"]
    )
    ablation_references = _normalize_ablation_reference_catalog(
        payload.get("ablation_references", [])
    )
    return {
        "suite_cell_id": suite_cell_id,
        "display_name": _normalize_nonempty_string(
            payload["display_name"],
            field_name="suite_cell.display_name",
        ),
        "lineage_kind": lineage_kind,
        "parent_cell_id": parent_cell_id,
        "root_cell_id": root_cell_id,
        "dimension_assignments": dimension_assignments,
        "ablation_references": ablation_references,
        "simulation_seed": _normalize_optional_int(
            payload.get("simulation_seed"),
            field_name="suite_cell.simulation_seed",
        ),
    }


def build_experiment_suite_work_item(
    *,
    work_item_id: str,
    suite_cell_id: str,
    stage_id: str,
    status: str,
    artifact_role_ids: Sequence[str],
    status_detail: str | None = None,
) -> dict[str, Any]:
    return parse_experiment_suite_work_item(
        {
            "work_item_id": work_item_id,
            "suite_cell_id": suite_cell_id,
            "stage_id": stage_id,
            "status": status,
            "artifact_role_ids": list(artifact_role_ids),
            "status_detail": status_detail,
        }
    )


def parse_experiment_suite_work_item(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("suite work item must be a mapping.")
    required_fields = (
        "work_item_id",
        "suite_cell_id",
        "stage_id",
        "status",
        "artifact_role_ids",
    )
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(f"suite work item is missing required fields: {missing!r}.")
    return {
        "work_item_id": _normalize_identifier(
            payload["work_item_id"],
            field_name="work_item.work_item_id",
        ),
        "suite_cell_id": _normalize_identifier(
            payload["suite_cell_id"],
            field_name="work_item.suite_cell_id",
        ),
        "stage_id": _normalize_identifier(
            payload["stage_id"],
            field_name="work_item.stage_id",
        ),
        "status": _normalize_identifier(
            payload["status"],
            field_name="work_item.status",
        ),
        "artifact_role_ids": _normalize_identifier_list(
            payload["artifact_role_ids"],
            field_name="work_item.artifact_role_ids",
        ),
        "status_detail": _normalize_optional_nonempty_string(
            payload.get("status_detail"),
            field_name="work_item.status_detail",
        ),
    }


def build_experiment_suite_artifact_reference(
    *,
    artifact_role_id: str,
    source_kind: str,
    path: str | Path,
    contract_version: str | None = None,
    bundle_id: str | None = None,
    artifact_id: str | None = None,
    format: str | None = None,
    artifact_scope: str | None = None,
    status: str = ASSET_STATUS_READY,
    suite_cell_id: str | None = None,
    work_item_id: str | None = None,
) -> dict[str, Any]:
    return parse_experiment_suite_artifact_reference(
        {
            "artifact_role_id": artifact_role_id,
            "source_kind": source_kind,
            "path": str(Path(path).resolve()),
            "contract_version": contract_version,
            "bundle_id": bundle_id,
            "artifact_id": artifact_id,
            "format": format,
            "artifact_scope": artifact_scope,
            "status": status,
            "suite_cell_id": suite_cell_id,
            "work_item_id": work_item_id,
        }
    )


def parse_experiment_suite_artifact_reference(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("suite artifact reference must be a mapping.")
    required_fields = ("artifact_role_id", "source_kind", "path", "status")
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(
            f"suite artifact reference is missing required fields: {missing!r}."
        )
    return {
        "artifact_role_id": _normalize_identifier(
            payload["artifact_role_id"],
            field_name="artifact_reference.artifact_role_id",
        ),
        "source_kind": _normalize_identifier(
            payload["source_kind"],
            field_name="artifact_reference.source_kind",
        ),
        "path": str(Path(payload["path"]).resolve()),
        "contract_version": _normalize_optional_nonempty_string(
            payload.get("contract_version"),
            field_name="artifact_reference.contract_version",
        ),
        "bundle_id": _normalize_optional_nonempty_string(
            payload.get("bundle_id"),
            field_name="artifact_reference.bundle_id",
        ),
        "artifact_id": _normalize_optional_identifier(
            payload.get("artifact_id"),
            field_name="artifact_reference.artifact_id",
        ),
        "format": _normalize_optional_nonempty_string(
            payload.get("format"),
            field_name="artifact_reference.format",
        ),
        "artifact_scope": _normalize_optional_identifier(
            payload.get("artifact_scope"),
            field_name="artifact_reference.artifact_scope",
        ),
        "status": _normalize_asset_status(
            payload.get("status"),
            field_name="artifact_reference.status",
        ),
        "suite_cell_id": _normalize_optional_identifier(
            payload.get("suite_cell_id"),
            field_name="artifact_reference.suite_cell_id",
        ),
        "work_item_id": _normalize_optional_identifier(
            payload.get("work_item_id"),
            field_name="artifact_reference.work_item_id",
        ),
    }


def build_experiment_suite_spec_hash(
    *,
    suite_id: str,
    upstream_references: Sequence[Mapping[str, Any]],
    suite_cells: Sequence[Mapping[str, Any]],
    work_items: Sequence[Mapping[str, Any]],
) -> str:
    identity_payload = _build_suite_identity_payload(
        suite_id=_normalize_identifier(suite_id, field_name="suite_id"),
        upstream_references=_normalize_artifact_reference_catalog(
            upstream_references,
            field_name="upstream_references",
        ),
        suite_cells=_normalize_suite_cell_catalog(suite_cells),
        work_items=_normalize_work_item_catalog(work_items),
    )
    serialized = json.dumps(
        identity_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_experiment_suite_metadata(
    *,
    suite_id: str,
    suite_label: str,
    upstream_references: Sequence[Mapping[str, Any]],
    suite_cells: Sequence[Mapping[str, Any]],
    work_items: Sequence[Mapping[str, Any]],
    artifact_references: Sequence[Mapping[str, Any]] | None = None,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_contract = parse_experiment_suite_contract_metadata(
        contract_metadata
        if contract_metadata is not None
        else build_experiment_suite_contract_metadata()
    )
    normalized_upstream_references = _normalize_artifact_reference_catalog(
        upstream_references,
        field_name="upstream_references",
    )
    normalized_suite_cells = _normalize_suite_cell_catalog(suite_cells)
    normalized_work_items = _normalize_work_item_catalog(work_items)
    normalized_artifact_references = _normalize_artifact_reference_catalog(
        artifact_references or [],
        field_name="artifact_references",
    )
    _validate_upstream_references_against_contract(
        normalized_upstream_references,
        contract_metadata=normalized_contract,
    )
    _validate_suite_cells_against_contract(
        normalized_suite_cells,
        contract_metadata=normalized_contract,
    )
    _validate_work_items_against_contract(
        normalized_work_items,
        suite_cells=normalized_suite_cells,
        contract_metadata=normalized_contract,
    )
    _validate_artifact_references_against_contract(
        normalized_artifact_references,
        contract_metadata=normalized_contract,
        allow_upstream_roles=False,
    )
    _validate_artifact_links(
        normalized_artifact_references,
        suite_cells=normalized_suite_cells,
        work_items=normalized_work_items,
    )
    normalized_upstream_references = _sort_artifact_references_to_contract(
        normalized_upstream_references,
        contract_metadata=normalized_contract,
    )
    normalized_suite_cells = _sort_suite_cells_to_contract(
        normalized_suite_cells,
        contract_metadata=normalized_contract,
    )
    normalized_work_items = _sort_work_items_to_contract(
        normalized_work_items,
        contract_metadata=normalized_contract,
    )
    normalized_artifact_references = _sort_artifact_references_to_contract(
        normalized_artifact_references,
        contract_metadata=normalized_contract,
    )

    suite_id_normalized = _normalize_identifier(suite_id, field_name="suite_id")
    suite_spec_hash = build_experiment_suite_spec_hash(
        suite_id=suite_id_normalized,
        upstream_references=normalized_upstream_references,
        suite_cells=normalized_suite_cells,
        work_items=normalized_work_items,
    )
    return {
        "contract_version": EXPERIMENT_SUITE_CONTRACT_VERSION,
        "design_note": EXPERIMENT_SUITE_DESIGN_NOTE,
        "design_note_version": EXPERIMENT_SUITE_DESIGN_NOTE_VERSION,
        "suite_id": suite_id_normalized,
        "suite_label": _normalize_nonempty_string(
            suite_label,
            field_name="suite_label",
        ),
        "suite_spec_hash": suite_spec_hash,
        "suite_spec_hash_algorithm": DEFAULT_HASH_ALGORITHM,
        "ownership_boundary": copy.deepcopy(normalized_contract["ownership_boundary"]),
        "reproducibility_hooks": [
            item["hook_id"] for item in normalized_contract["reproducibility_hook_catalog"]
        ],
        "composed_contracts": list(normalized_contract["composed_contracts"]),
        "upstream_references": normalized_upstream_references,
        "suite_cells": normalized_suite_cells,
        "work_items": normalized_work_items,
        "artifact_references": normalized_artifact_references,
    }


def parse_experiment_suite_metadata(
    payload: Mapping[str, Any],
    *,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("experiment_suite metadata must be a mapping.")
    required_fields = (
        "contract_version",
        "design_note",
        "design_note_version",
        "suite_id",
        "suite_label",
        "upstream_references",
        "suite_cells",
        "work_items",
        "artifact_references",
    )
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(
            f"experiment_suite metadata is missing required fields: {missing!r}."
        )
    contract_version = _normalize_nonempty_string(
        payload["contract_version"],
        field_name="contract_version",
    )
    if contract_version != EXPERIMENT_SUITE_CONTRACT_VERSION:
        raise ValueError(
            "experiment_suite contract_version must be "
            f"{EXPERIMENT_SUITE_CONTRACT_VERSION!r}."
        )
    design_note = _normalize_nonempty_string(
        payload["design_note"],
        field_name="design_note",
    )
    if design_note != EXPERIMENT_SUITE_DESIGN_NOTE:
        raise ValueError(
            "experiment_suite design_note must be "
            f"{EXPERIMENT_SUITE_DESIGN_NOTE!r}."
        )
    design_note_version = _normalize_nonempty_string(
        payload["design_note_version"],
        field_name="design_note_version",
    )
    if design_note_version != EXPERIMENT_SUITE_DESIGN_NOTE_VERSION:
        raise ValueError(
            "experiment_suite design_note_version must be "
            f"{EXPERIMENT_SUITE_DESIGN_NOTE_VERSION!r}."
        )
    return build_experiment_suite_metadata(
        suite_id=payload["suite_id"],
        suite_label=payload["suite_label"],
        upstream_references=payload["upstream_references"],
        suite_cells=payload["suite_cells"],
        work_items=payload["work_items"],
        artifact_references=payload["artifact_references"],
        contract_metadata=contract_metadata,
    )


def write_experiment_suite_metadata(
    suite_metadata: Mapping[str, Any],
    output_path: str | Path,
    *,
    contract_metadata: Mapping[str, Any] | None = None,
) -> Path:
    normalized = parse_experiment_suite_metadata(
        suite_metadata,
        contract_metadata=contract_metadata,
    )
    return write_json(normalized, Path(output_path).resolve())


def load_experiment_suite_metadata(
    metadata_path: str | Path,
    *,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    with Path(metadata_path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_experiment_suite_metadata(
        payload,
        contract_metadata=contract_metadata,
    )


def discover_experiment_suite_dimensions(
    record: Mapping[str, Any],
    *,
    dimension_group: str | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_experiment_suite_contract_metadata(
        _extract_experiment_suite_contract_mapping(record)
    )
    normalized_group = (
        None
        if dimension_group is None
        else _normalize_identifier(
            dimension_group,
            field_name="dimension_group",
        )
    )
    discovered: list[dict[str, Any]] = []
    for item in metadata["dimension_catalog"]:
        if normalized_group is not None and item["dimension_group"] != normalized_group:
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def discover_experiment_suite_ablation_families(
    record: Mapping[str, Any],
    *,
    required_only: bool | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_experiment_suite_contract_metadata(
        _extract_experiment_suite_contract_mapping(record)
    )
    discovered: list[dict[str, Any]] = []
    for item in metadata["ablation_family_catalog"]:
        if required_only is True and not item["required"]:
            continue
        if required_only is False and item["required"]:
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def discover_experiment_suite_lineage_kinds(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    metadata = parse_experiment_suite_contract_metadata(
        _extract_experiment_suite_contract_mapping(record)
    )
    return [copy.deepcopy(item) for item in metadata["lineage_catalog"]]


def discover_experiment_suite_work_item_statuses(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    metadata = parse_experiment_suite_contract_metadata(
        _extract_experiment_suite_contract_mapping(record)
    )
    return [copy.deepcopy(item) for item in metadata["work_item_status_catalog"]]


def discover_experiment_suite_artifact_roles(
    record: Mapping[str, Any],
    *,
    source_kind: str | None = None,
    artifact_scope: str | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_experiment_suite_contract_metadata(
        _extract_experiment_suite_contract_mapping(record)
    )
    normalized_source_kind = (
        None
        if source_kind is None
        else _normalize_identifier(source_kind, field_name="source_kind")
    )
    normalized_artifact_scope = (
        None
        if artifact_scope is None
        else _normalize_identifier(artifact_scope, field_name="artifact_scope")
    )
    discovered: list[dict[str, Any]] = []
    for item in metadata["artifact_role_catalog"]:
        if normalized_source_kind is not None and item["source_kind"] != normalized_source_kind:
            continue
        if (
            normalized_artifact_scope is not None
            and item["artifact_scope"] != normalized_artifact_scope
        ):
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def discover_experiment_suite_reproducibility_hooks(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    metadata = parse_experiment_suite_contract_metadata(
        _extract_experiment_suite_contract_mapping(record)
    )
    return [copy.deepcopy(item) for item in metadata["reproducibility_hook_catalog"]]


def get_experiment_suite_dimension_definition(
    dimension_id: str,
    *,
    record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_dimension_id = _normalize_identifier(
        dimension_id,
        field_name="dimension_id",
    )
    metadata = (
        build_experiment_suite_contract_metadata()
        if record is None
        else parse_experiment_suite_contract_metadata(
            _extract_experiment_suite_contract_mapping(record)
        )
    )
    for item in metadata["dimension_catalog"]:
        if item["dimension_id"] == normalized_dimension_id:
            return copy.deepcopy(item)
    raise KeyError(f"Unknown experiment suite dimension_id {normalized_dimension_id!r}.")


def get_experiment_suite_ablation_family_definition(
    ablation_family_id: str,
    *,
    record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_ablation_family_id = _normalize_identifier(
        ablation_family_id,
        field_name="ablation_family_id",
    )
    metadata = (
        build_experiment_suite_contract_metadata()
        if record is None
        else parse_experiment_suite_contract_metadata(
            _extract_experiment_suite_contract_mapping(record)
        )
    )
    for item in metadata["ablation_family_catalog"]:
        if item["ablation_family_id"] == normalized_ablation_family_id:
            return copy.deepcopy(item)
    raise KeyError(
        "Unknown experiment suite ablation_family_id "
        f"{normalized_ablation_family_id!r}."
    )


def discover_experiment_suite_cells(
    record: Mapping[str, Any],
    *,
    lineage_kind: str | None = None,
    ablation_family_id: str | None = None,
    dimension_id: str | None = None,
    value_id: str | None = None,
    contract_metadata: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_experiment_suite_metadata(
        _extract_experiment_suite_mapping(record),
        contract_metadata=contract_metadata,
    )
    normalized_lineage_kind = (
        None
        if lineage_kind is None
        else _normalize_identifier(lineage_kind, field_name="lineage_kind")
    )
    normalized_ablation_family_id = (
        None
        if ablation_family_id is None
        else _normalize_identifier(
            ablation_family_id,
            field_name="ablation_family_id",
        )
    )
    normalized_dimension_id = (
        None
        if dimension_id is None
        else _normalize_identifier(dimension_id, field_name="dimension_id")
    )
    normalized_value_id = (
        None
        if value_id is None
        else _normalize_identifier(value_id, field_name="value_id")
    )
    discovered: list[dict[str, Any]] = []
    for item in metadata["suite_cells"]:
        if normalized_lineage_kind is not None and item["lineage_kind"] != normalized_lineage_kind:
            continue
        if normalized_ablation_family_id is not None and normalized_ablation_family_id not in {
            entry["ablation_family_id"] for entry in item["ablation_references"]
        }:
            continue
        if normalized_dimension_id is not None:
            assignments = {
                entry["dimension_id"]: entry["value_id"]
                for entry in item["dimension_assignments"]
            }
            if normalized_dimension_id not in assignments:
                continue
            if (
                normalized_value_id is not None
                and assignments[normalized_dimension_id] != normalized_value_id
            ):
                continue
        discovered.append(copy.deepcopy(item))
    return discovered


def discover_experiment_suite_work_items(
    record: Mapping[str, Any],
    *,
    status: str | None = None,
    stage_id: str | None = None,
    suite_cell_id: str | None = None,
    contract_metadata: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_experiment_suite_metadata(
        _extract_experiment_suite_mapping(record),
        contract_metadata=contract_metadata,
    )
    normalized_status = (
        None if status is None else _normalize_identifier(status, field_name="status")
    )
    normalized_stage_id = (
        None
        if stage_id is None
        else _normalize_identifier(stage_id, field_name="stage_id")
    )
    normalized_suite_cell_id = (
        None
        if suite_cell_id is None
        else _normalize_identifier(suite_cell_id, field_name="suite_cell_id")
    )
    discovered: list[dict[str, Any]] = []
    for item in metadata["work_items"]:
        if normalized_status is not None and item["status"] != normalized_status:
            continue
        if normalized_stage_id is not None and item["stage_id"] != normalized_stage_id:
            continue
        if (
            normalized_suite_cell_id is not None
            and item["suite_cell_id"] != normalized_suite_cell_id
        ):
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def discover_experiment_suite_artifact_references(
    record: Mapping[str, Any],
    *,
    artifact_role_id: str | None = None,
    source_kind: str | None = None,
    suite_cell_id: str | None = None,
    include_upstream: bool = True,
    contract_metadata: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_experiment_suite_metadata(
        _extract_experiment_suite_mapping(record),
        contract_metadata=contract_metadata,
    )
    normalized_artifact_role_id = (
        None
        if artifact_role_id is None
        else _normalize_identifier(artifact_role_id, field_name="artifact_role_id")
    )
    normalized_source_kind = (
        None
        if source_kind is None
        else _normalize_identifier(source_kind, field_name="source_kind")
    )
    normalized_suite_cell_id = (
        None
        if suite_cell_id is None
        else _normalize_identifier(suite_cell_id, field_name="suite_cell_id")
    )
    all_references = list(metadata["artifact_references"])
    if include_upstream:
        all_references = list(metadata["upstream_references"]) + all_references
    discovered: list[dict[str, Any]] = []
    for item in all_references:
        if (
            normalized_artifact_role_id is not None
            and item["artifact_role_id"] != normalized_artifact_role_id
        ):
            continue
        if normalized_source_kind is not None and item["source_kind"] != normalized_source_kind:
            continue
        if (
            normalized_suite_cell_id is not None
            and item["suite_cell_id"] != normalized_suite_cell_id
        ):
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def default_experiment_suite_ownership_boundary() -> dict[str, Any]:
    return {
        "orchestration_owner": ORCHESTRATION_OWNER_JACK,
        "orchestration_responsibilities": [
            "suite_identity",
            "dimension_catalog",
            "artifact_roles",
            "lineage_semantics",
            "work_item_status_semantics",
            "deterministic_discovery",
            "reproducibility_hooks",
        ],
        "scientific_ablation_owner": SCIENTIFIC_OWNER_GRANT,
        "scientific_ablation_responsibilities": [
            "declared_ablation_families",
            "ablation_parameter_choices",
            "scientifically_meaningful_subset_selection",
            "scientific_interpretation_of_results",
        ],
        "boundary_rule": (
            "Jack owns the orchestration surface and deterministic mechanics; "
            "Grant owns which scientifically meaningful ablation families and "
            "parameterizations are declared through that surface."
        ),
    }


def parse_experiment_suite_dimension_definition(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("dimension definition must be a mapping.")
    required_fields = (
        "dimension_id",
        "display_name",
        "description",
        "dimension_group",
        "sequence_index",
        "discovery_note",
    )
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(f"dimension definition is missing required fields: {missing!r}.")
    return {
        "dimension_id": _normalize_identifier(
            payload["dimension_id"],
            field_name="dimension.dimension_id",
        ),
        "display_name": _normalize_nonempty_string(
            payload["display_name"],
            field_name="dimension.display_name",
        ),
        "description": _normalize_nonempty_string(
            payload["description"],
            field_name="dimension.description",
        ),
        "dimension_group": _normalize_identifier(
            payload["dimension_group"],
            field_name="dimension.dimension_group",
        ),
        "sequence_index": _normalize_int(
            payload["sequence_index"],
            field_name="dimension.sequence_index",
        ),
        "discovery_note": _normalize_nonempty_string(
            payload["discovery_note"],
            field_name="dimension.discovery_note",
        ),
    }


def parse_experiment_suite_ablation_family_definition(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("ablation family definition must be a mapping.")
    required_fields = (
        "ablation_family_id",
        "display_name",
        "description",
        "sequence_index",
        "required",
        "uses_perturbation_seed",
        "discovery_note",
    )
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(
            f"ablation family definition is missing required fields: {missing!r}."
        )
    return {
        "ablation_family_id": _normalize_identifier(
            payload["ablation_family_id"],
            field_name="ablation_family.ablation_family_id",
        ),
        "display_name": _normalize_nonempty_string(
            payload["display_name"],
            field_name="ablation_family.display_name",
        ),
        "description": _normalize_nonempty_string(
            payload["description"],
            field_name="ablation_family.description",
        ),
        "sequence_index": _normalize_int(
            payload["sequence_index"],
            field_name="ablation_family.sequence_index",
        ),
        "required": bool(payload["required"]),
        "uses_perturbation_seed": bool(payload["uses_perturbation_seed"]),
        "discovery_note": _normalize_nonempty_string(
            payload["discovery_note"],
            field_name="ablation_family.discovery_note",
        ),
    }


def parse_experiment_suite_lineage_definition(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("lineage definition must be a mapping.")
    required_fields = (
        "lineage_kind",
        "display_name",
        "description",
        "sequence_index",
        "requires_parent",
        "introduces_simulation_seed",
        "introduces_ablation_family",
    )
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(f"lineage definition is missing required fields: {missing!r}.")
    return {
        "lineage_kind": _normalize_identifier(
            payload["lineage_kind"],
            field_name="lineage.lineage_kind",
        ),
        "display_name": _normalize_nonempty_string(
            payload["display_name"],
            field_name="lineage.display_name",
        ),
        "description": _normalize_nonempty_string(
            payload["description"],
            field_name="lineage.description",
        ),
        "sequence_index": _normalize_int(
            payload["sequence_index"],
            field_name="lineage.sequence_index",
        ),
        "requires_parent": bool(payload["requires_parent"]),
        "introduces_simulation_seed": bool(payload["introduces_simulation_seed"]),
        "introduces_ablation_family": bool(payload["introduces_ablation_family"]),
    }


def parse_experiment_suite_work_item_status_definition(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("work item status definition must be a mapping.")
    required_fields = (
        "status_id",
        "display_name",
        "description",
        "sequence_index",
        "resume_allowed",
    )
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(
            f"work item status definition is missing required fields: {missing!r}."
        )
    return {
        "status_id": _normalize_identifier(
            payload["status_id"],
            field_name="work_item_status.status_id",
        ),
        "display_name": _normalize_nonempty_string(
            payload["display_name"],
            field_name="work_item_status.display_name",
        ),
        "description": _normalize_nonempty_string(
            payload["description"],
            field_name="work_item_status.description",
        ),
        "sequence_index": _normalize_int(
            payload["sequence_index"],
            field_name="work_item_status.sequence_index",
        ),
        "resume_allowed": bool(payload["resume_allowed"]),
    }


def parse_experiment_suite_artifact_role_definition(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("artifact role definition must be a mapping.")
    required_fields = (
        "artifact_role_id",
        "display_name",
        "description",
        "source_kind",
        "artifact_scope",
        "sequence_index",
        "discovery_note",
    )
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(
            f"artifact role definition is missing required fields: {missing!r}."
        )
    return {
        "artifact_role_id": _normalize_identifier(
            payload["artifact_role_id"],
            field_name="artifact_role.artifact_role_id",
        ),
        "display_name": _normalize_nonempty_string(
            payload["display_name"],
            field_name="artifact_role.display_name",
        ),
        "description": _normalize_nonempty_string(
            payload["description"],
            field_name="artifact_role.description",
        ),
        "source_kind": _normalize_identifier(
            payload["source_kind"],
            field_name="artifact_role.source_kind",
        ),
        "artifact_scope": _normalize_identifier(
            payload["artifact_scope"],
            field_name="artifact_role.artifact_scope",
        ),
        "sequence_index": _normalize_int(
            payload["sequence_index"],
            field_name="artifact_role.sequence_index",
        ),
        "discovery_note": _normalize_nonempty_string(
            payload["discovery_note"],
            field_name="artifact_role.discovery_note",
        ),
        "required_contract_version": _normalize_optional_nonempty_string(
            payload.get("required_contract_version"),
            field_name="artifact_role.required_contract_version",
        ),
    }


def parse_experiment_suite_reproducibility_hook_definition(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("reproducibility hook definition must be a mapping.")
    required_fields = ("hook_id", "display_name", "description", "sequence_index")
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(
            f"reproducibility hook definition is missing required fields: {missing!r}."
        )
    return {
        "hook_id": _normalize_identifier(
            payload["hook_id"],
            field_name="reproducibility_hook.hook_id",
        ),
        "display_name": _normalize_nonempty_string(
            payload["display_name"],
            field_name="reproducibility_hook.display_name",
        ),
        "description": _normalize_nonempty_string(
            payload["description"],
            field_name="reproducibility_hook.description",
        ),
        "sequence_index": _normalize_int(
            payload["sequence_index"],
            field_name="reproducibility_hook.sequence_index",
        ),
    }


def _default_dimension_catalog() -> list[dict[str, Any]]:
    return [
        build_experiment_suite_dimension_definition(
            dimension_id=SCENE_TYPE_DIMENSION_ID,
            display_name="Scene Type",
            description="The fixture-scene or world-scene family used to generate the experiment condition.",
            dimension_group=STIMULUS_CONTEXT_DIMENSION_GROUP,
            sequence_index=10,
            discovery_note="Resolve from the suite declaration or its linked experiment manifest inputs instead of directory-name conventions.",
        ),
        build_experiment_suite_dimension_definition(
            dimension_id=MOTION_DIRECTION_DIMENSION_ID,
            display_name="Motion Direction",
            description="The canonical motion-direction condition used for shared preferred-versus-null comparisons.",
            dimension_group=STIMULUS_MOTION_DIMENSION_GROUP,
            sequence_index=20,
            discovery_note="Keep direction identity on the suite cell rather than inferring it later from plot labels or readout-card captions.",
        ),
        build_experiment_suite_dimension_definition(
            dimension_id=MOTION_SPEED_DIMENSION_ID,
            display_name="Motion Speed",
            description="The stimulus motion-speed condition or equivalent temporal sweep axis for the cell.",
            dimension_group=STIMULUS_MOTION_DIMENSION_GROUP,
            sequence_index=30,
            discovery_note="Store speed as a first-class suite dimension so paired analyses do not need to reverse-engineer it from stimulus parameters.",
        ),
        build_experiment_suite_dimension_definition(
            dimension_id=CONTRAST_LEVEL_DIMENSION_ID,
            display_name="Contrast Level",
            description="The contrast regime or intensity condition tied to the suite cell.",
            dimension_group=STIMULUS_SIGNAL_DIMENSION_GROUP,
            sequence_index=40,
            discovery_note="Contrast belongs in the suite taxonomy even when it is realized through an upstream stimulus parameter bundle.",
        ),
        build_experiment_suite_dimension_definition(
            dimension_id=NOISE_LEVEL_DIMENSION_ID,
            display_name="Noise Level",
            description="The explicit stimulus or perturbation noise regime used for the condition.",
            dimension_group=STIMULUS_SIGNAL_DIMENSION_GROUP,
            sequence_index=50,
            discovery_note="Record the noise regime in normalized cell metadata instead of letting repeated seeds stand in for a missing dimension ID.",
        ),
        build_experiment_suite_dimension_definition(
            dimension_id=ACTIVE_SUBSET_DIMENSION_ID,
            display_name="Active Subset",
            description="The selected root-id subset, cohort, or circuit slice active for the suite cell.",
            dimension_group=CIRCUIT_SELECTION_DIMENSION_GROUP,
            sequence_index=60,
            discovery_note="Tie subset identity back to subset-selection outputs or manifest declarations rather than folder names.",
        ),
        build_experiment_suite_dimension_definition(
            dimension_id=WAVE_KERNEL_DIMENSION_ID,
            display_name="Wave Kernel",
            description="The wave-propagation kernel or surface-wave model family active for the suite cell.",
            dimension_group=WAVE_MODEL_DIMENSION_GROUP,
            sequence_index=70,
            discovery_note="Wave-kernel identity composes with simulation_plan.v1 and surface-wave metadata rather than replacing them.",
        ),
        build_experiment_suite_dimension_definition(
            dimension_id=COUPLING_MODE_DIMENSION_ID,
            display_name="Coupling Mode",
            description="The effective coupling-mode choice for the cell, including baseline or ablated lateral-coupling semantics.",
            dimension_group=WAVE_MODEL_DIMENSION_GROUP,
            sequence_index=80,
            discovery_note="Coupling-mode identity should point back to coupling_bundle.v1 or simulation-plan semantics instead of ad hoc shell flags.",
        ),
        build_experiment_suite_dimension_definition(
            dimension_id=MESH_RESOLUTION_DIMENSION_ID,
            display_name="Mesh Resolution",
            description="The geometry-resolution or surface-discretization regime used to materialize the cell.",
            dimension_group=GEOMETRY_FIDELITY_DIMENSION_GROUP,
            sequence_index=90,
            discovery_note="Geometry resolution is a suite dimension so coarse-versus-fine comparisons stay traceable to the same cell lineage.",
        ),
        build_experiment_suite_dimension_definition(
            dimension_id=SOLVER_SETTINGS_DIMENSION_ID,
            display_name="Solver Settings",
            description="The stable identifier for timestep, integrator, or other solver-configuration settings.",
            dimension_group=RUNTIME_DIMENSION_GROUP,
            sequence_index=100,
            discovery_note="Use one solver-settings dimension ID instead of scattering runtime knobs across free-form notes.",
        ),
        build_experiment_suite_dimension_definition(
            dimension_id=FIDELITY_CLASS_DIMENSION_ID,
            display_name="Fidelity Class",
            description="The mixed-fidelity or morphology-class assignment regime for the cell.",
            dimension_group=GEOMETRY_FIDELITY_DIMENSION_GROUP,
            sequence_index=110,
            discovery_note="Fidelity class composes with hybrid-morphology and simulator bundle contracts; it is not a new standalone simulator contract.",
        ),
    ]


def _default_ablation_family_catalog() -> list[dict[str, Any]]:
    return [
        build_experiment_suite_ablation_family_definition(
            ablation_family_id=NO_WAVES_ABLATION_FAMILY_ID,
            display_name="No Waves",
            description="Disable wave propagation while preserving the declared comparison surface and downstream readout semantics.",
            sequence_index=10,
            required=True,
            uses_perturbation_seed=False,
            discovery_note="Treat this as a first-class ablation family instead of an unnamed baseline fallback.",
        ),
        build_experiment_suite_ablation_family_definition(
            ablation_family_id=WAVES_ONLY_SELECTED_CELL_CLASSES_ABLATION_FAMILY_ID,
            display_name="Waves Only Selected Cell Classes",
            description="Restrict wave dynamics to an explicitly declared cell-class subset while leaving the rest on the declared comparison surface.",
            sequence_index=20,
            required=True,
            uses_perturbation_seed=False,
            discovery_note="Grant declares which cell classes are scientifically meaningful; Jack owns only the deterministic surface for that declaration.",
        ),
        build_experiment_suite_ablation_family_definition(
            ablation_family_id=NO_LATERAL_COUPLING_ABLATION_FAMILY_ID,
            display_name="No Lateral Coupling",
            description="Remove or bypass lateral coupling while keeping the same upstream selection and shared-readout surface.",
            sequence_index=30,
            required=True,
            uses_perturbation_seed=False,
            discovery_note="This family exists so later suite tooling does not encode coupling removal through opaque arm names.",
        ),
        build_experiment_suite_ablation_family_definition(
            ablation_family_id=SHUFFLE_SYNAPSE_LOCATIONS_ABLATION_FAMILY_ID,
            display_name="Shuffle Synapse Locations",
            description="Perturb synapse locations with deterministic shuffle mechanics that remain separate from the simulator seed.",
            sequence_index=40,
            required=True,
            uses_perturbation_seed=True,
            discovery_note="Keep perturbation seed lineage explicit so location shuffles remain auditable across reruns.",
        ),
        build_experiment_suite_ablation_family_definition(
            ablation_family_id=SHUFFLE_MORPHOLOGY_ABLATION_FAMILY_ID,
            display_name="Shuffle Morphology",
            description="Perturb morphology assignments or geometry correspondences under deterministic suite-owned lineage tracking.",
            sequence_index=50,
            required=True,
            uses_perturbation_seed=True,
            discovery_note="Morphology shuffles must stay labeled as ablations rather than hidden mixed-fidelity implementation details.",
        ),
        build_experiment_suite_ablation_family_definition(
            ablation_family_id=COARSEN_GEOMETRY_ABLATION_FAMILY_ID,
            display_name="Coarsen Geometry",
            description="Use a coarser geometry or reduced mesh regime as an explicit ablation family rather than an untracked runtime shortcut.",
            sequence_index=60,
            required=True,
            uses_perturbation_seed=False,
            discovery_note="Geometry coarsening is suite-visible because it changes the scientific comparison story even when the operator bundle stays deterministic.",
        ),
        build_experiment_suite_ablation_family_definition(
            ablation_family_id=ALTERED_SIGN_ASSUMPTIONS_ABLATION_FAMILY_ID,
            display_name="Altered Sign Assumptions",
            description="Alter sign assumptions through an explicit ablation family with declared parameters and preserved lineage.",
            sequence_index=70,
            required=True,
            uses_perturbation_seed=False,
            discovery_note="Sign changes are scientifically meaningful perturbations and therefore must be declared through the suite surface.",
        ),
        build_experiment_suite_ablation_family_definition(
            ablation_family_id=ALTERED_DELAY_ASSUMPTIONS_ABLATION_FAMILY_ID,
            display_name="Altered Delay Assumptions",
            description="Alter delay assumptions through an explicit ablation family with separate perturbation semantics from the simulator seed.",
            sequence_index=80,
            required=True,
            uses_perturbation_seed=False,
            discovery_note="Delay-assumption changes should remain distinct from solver settings and from shared timebase semantics.",
        ),
    ]


def _default_lineage_catalog() -> list[dict[str, Any]]:
    return [
        build_experiment_suite_lineage_definition(
            lineage_kind=BASE_CONDITION_LINEAGE_KIND,
            display_name="Base Condition",
            description="A root suite cell declared directly from the active dimension assignments with no parent lineage.",
            sequence_index=10,
            requires_parent=False,
            introduces_simulation_seed=False,
            introduces_ablation_family=False,
        ),
        build_experiment_suite_lineage_definition(
            lineage_kind=SEED_REPLICATE_LINEAGE_KIND,
            display_name="Seed Replicate",
            description="A child suite cell that reuses the parent's dimension assignments but introduces a simulator seed.",
            sequence_index=20,
            requires_parent=True,
            introduces_simulation_seed=True,
            introduces_ablation_family=False,
        ),
        build_experiment_suite_lineage_definition(
            lineage_kind=ABLATION_VARIANT_LINEAGE_KIND,
            display_name="Ablation Variant",
            description="A child suite cell that preserves the parent's dimension story while introducing one or more ablation families.",
            sequence_index=30,
            requires_parent=True,
            introduces_simulation_seed=False,
            introduces_ablation_family=True,
        ),
        build_experiment_suite_lineage_definition(
            lineage_kind=SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
            display_name="Seeded Ablation Variant",
            description="A child suite cell that introduces both a simulator seed and one or more ablation families on the same lineage path.",
            sequence_index=40,
            requires_parent=True,
            introduces_simulation_seed=True,
            introduces_ablation_family=True,
        ),
    ]


def _default_work_item_status_catalog() -> list[dict[str, Any]]:
    return [
        build_experiment_suite_work_item_status_definition(
            status_id=WORK_ITEM_STATUS_PLANNED,
            display_name="Planned",
            description="The suite work item exists in deterministic ordering but prerequisites have not been checked yet.",
            sequence_index=10,
            resume_allowed=work_item_status_allows_resume(WORK_ITEM_STATUS_PLANNED),
        ),
        build_experiment_suite_work_item_status_definition(
            status_id=WORK_ITEM_STATUS_READY,
            display_name="Ready",
            description="All declared prerequisites are available and the work item can be executed without reinterpretation.",
            sequence_index=20,
            resume_allowed=work_item_status_allows_resume(WORK_ITEM_STATUS_READY),
        ),
        build_experiment_suite_work_item_status_definition(
            status_id=WORK_ITEM_STATUS_RUNNING,
            display_name="Running",
            description="The work item has started and may emit partial local outputs, but completion has not yet been established.",
            sequence_index=30,
            resume_allowed=work_item_status_allows_resume(WORK_ITEM_STATUS_RUNNING),
        ),
        build_experiment_suite_work_item_status_definition(
            status_id=WORK_ITEM_STATUS_SUCCEEDED,
            display_name="Succeeded",
            description="The declared stage completed and the expected downstream artifacts were discovered without contract incompatibility.",
            sequence_index=40,
            resume_allowed=work_item_status_allows_resume(WORK_ITEM_STATUS_SUCCEEDED),
        ),
        build_experiment_suite_work_item_status_definition(
            status_id=WORK_ITEM_STATUS_PARTIAL,
            display_name="Partial",
            description="Some declared outputs were produced, but the stage is not yet complete enough to treat the work item as succeeded.",
            sequence_index=50,
            resume_allowed=work_item_status_allows_resume(WORK_ITEM_STATUS_PARTIAL),
        ),
        build_experiment_suite_work_item_status_definition(
            status_id=WORK_ITEM_STATUS_FAILED,
            display_name="Failed",
            description="Execution attempted the stage and produced a deterministic failure that must be addressed or explicitly retried.",
            sequence_index=60,
            resume_allowed=work_item_status_allows_resume(WORK_ITEM_STATUS_FAILED),
        ),
        build_experiment_suite_work_item_status_definition(
            status_id=WORK_ITEM_STATUS_BLOCKED,
            display_name="Blocked",
            description="Required upstream inputs or compatible prerequisites were unavailable, so the stage could not execute honestly.",
            sequence_index=70,
            resume_allowed=work_item_status_allows_resume(WORK_ITEM_STATUS_BLOCKED),
        ),
        build_experiment_suite_work_item_status_definition(
            status_id=WORK_ITEM_STATUS_SKIPPED,
            display_name="Skipped",
            description="The stage was intentionally not executed for this suite cell under the declared orchestration policy.",
            sequence_index=80,
            resume_allowed=work_item_status_allows_resume(WORK_ITEM_STATUS_SKIPPED),
        ),
    ]


def _default_artifact_role_catalog() -> list[dict[str, Any]]:
    return [
        build_experiment_suite_artifact_role_definition(
            artifact_role_id=SUITE_MANIFEST_INPUT_ROLE_ID,
            display_name="Suite Manifest Input",
            description="The suite-level manifest declaration that defines orchestration intent before expansion.",
            source_kind=SUITE_MANIFEST_SOURCE_KIND,
            artifact_scope=UPSTREAM_MANIFEST_ARTIFACT_SCOPE,
            sequence_index=10,
            discovery_note="Future suite runners should resolve the suite manifest through metadata-backed references instead of hardcoded command-line paths.",
        ),
        build_experiment_suite_artifact_role_definition(
            artifact_role_id=EXPERIMENT_MANIFEST_INPUT_ROLE_ID,
            display_name="Experiment Manifest Input",
            description="The experiment-manifest input that still owns per-experiment biological intent and baseline-versus-wave arm structure.",
            source_kind=EXPERIMENT_MANIFEST_SOURCE_KIND,
            artifact_scope=UPSTREAM_MANIFEST_ARTIFACT_SCOPE,
            sequence_index=20,
            discovery_note="The suite layer points at experiment-manifest inputs; it does not replace or mutate the manifest schema on its own.",
        ),
        build_experiment_suite_artifact_role_definition(
            artifact_role_id=SIMULATION_PLAN_ROLE_ID,
            display_name="Simulation Plan",
            description="The normalized Milestone 9 through 11 simulation plan derived from the suite's upstream manifest inputs.",
            source_kind=SIMULATION_PLAN_SOURCE_KIND,
            artifact_scope=UPSTREAM_PLAN_ARTIFACT_SCOPE,
            sequence_index=30,
            discovery_note="Resolve simulation planning through simulation_plan.v1 instead of introducing a second planning surface here.",
            required_contract_version=SIMULATION_PLAN_VERSION,
        ),
        build_experiment_suite_artifact_role_definition(
            artifact_role_id=SIMULATOR_RESULT_BUNDLE_ROLE_ID,
            display_name="Simulator Result Bundle",
            description="The per-arm simulator result bundle produced for one suite cell.",
            source_kind=SIMULATOR_RESULT_SOURCE_KIND,
            artifact_scope=DOWNSTREAM_BUNDLE_ARTIFACT_SCOPE,
            sequence_index=40,
            discovery_note="Use simulator_result_bundle.v1 metadata as the discovery anchor for per-run outputs tied to a suite cell.",
            required_contract_version=SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
        ),
        build_experiment_suite_artifact_role_definition(
            artifact_role_id=EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
            display_name="Experiment Analysis Bundle",
            description="The experiment-level packaged analysis output attached to one suite cell or comparison group.",
            source_kind=EXPERIMENT_ANALYSIS_SOURCE_KIND,
            artifact_scope=DOWNSTREAM_BUNDLE_ARTIFACT_SCOPE,
            sequence_index=50,
            discovery_note="Use experiment_analysis_bundle.v1 metadata instead of reparsing simulator bundle directories at the suite layer.",
            required_contract_version=EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION,
        ),
        build_experiment_suite_artifact_role_definition(
            artifact_role_id=VALIDATION_BUNDLE_ROLE_ID,
            display_name="Validation Bundle",
            description="The packaged validation ladder output attached to one suite cell or experiment review unit.",
            source_kind=VALIDATION_BUNDLE_SOURCE_KIND,
            artifact_scope=DOWNSTREAM_BUNDLE_ARTIFACT_SCOPE,
            sequence_index=60,
            discovery_note="Use validation_ladder.v1 metadata for machine findings and reviewer handoff discovery.",
            required_contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
        ),
        build_experiment_suite_artifact_role_definition(
            artifact_role_id=DASHBOARD_SESSION_ROLE_ID,
            display_name="Dashboard Session",
            description="The packaged dashboard-session output for one suite cell or paired review surface.",
            source_kind=DASHBOARD_SESSION_SOURCE_KIND,
            artifact_scope=DOWNSTREAM_BUNDLE_ARTIFACT_SCOPE,
            sequence_index=70,
            discovery_note="Use dashboard_session.v1 metadata to discover packaged session state and bridge artifacts.",
            required_contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
        ),
        build_experiment_suite_artifact_role_definition(
            artifact_role_id=SUMMARY_TABLE_ROLE_ID,
            display_name="Summary Table",
            description="A suite-level summary table export that aggregates or indexes experiment-level outputs.",
            source_kind=SUMMARY_TABLE_SOURCE_KIND,
            artifact_scope=SUMMARY_OUTPUT_ARTIFACT_SCOPE,
            sequence_index=80,
            discovery_note="Summary tables stay suite-owned outputs; they must point back to upstream bundle references rather than becoming a second source of truth.",
        ),
        build_experiment_suite_artifact_role_definition(
            artifact_role_id=COMPARISON_PLOT_ROLE_ID,
            display_name="Comparison Plot",
            description="A suite-level comparison plot or figure generated from packaged suite rollups or summaries.",
            source_kind=COMPARISON_PLOT_SOURCE_KIND,
            artifact_scope=PLOT_OUTPUT_ARTIFACT_SCOPE,
            sequence_index=90,
            discovery_note="Comparison plots remain review artifacts derived from metadata-backed tables and bundles, not hand-curated one-off images.",
        ),
        build_experiment_suite_artifact_role_definition(
            artifact_role_id=REVIEW_ARTIFACT_ROLE_ID,
            display_name="Review Artifact",
            description="A reviewer-facing note, report, or decision artifact tied back to one or more suite cells.",
            source_kind=REVIEW_ARTIFACT_SOURCE_KIND,
            artifact_scope=REVIEW_OUTPUT_ARTIFACT_SCOPE,
            sequence_index=100,
            discovery_note="Keep review artifacts discoverable from suite metadata while preserving the earlier milestone bundle boundaries.",
        ),
    ]


def _default_reproducibility_hook_catalog() -> list[dict[str, Any]]:
    return [
        build_experiment_suite_reproducibility_hook_definition(
            hook_id=SUITE_SPEC_HASH_HOOK_ID,
            display_name="Suite Spec Hash",
            description="A deterministic hash over normalized upstream references, suite cells, and work-item identities.",
            sequence_index=10,
        ),
        build_experiment_suite_reproducibility_hook_definition(
            hook_id=SUITE_CELL_ID_HOOK_ID,
            display_name="Suite Cell ID",
            description="A stable suite-cell identifier that is independent of output directory naming.",
            sequence_index=20,
        ),
        build_experiment_suite_reproducibility_hook_definition(
            hook_id=PARENT_LINEAGE_REFERENCE_HOOK_ID,
            display_name="Parent Lineage Reference",
            description="Explicit parent and root cell references so ablations and seed variants stay traceable across reruns.",
            sequence_index=30,
        ),
        build_experiment_suite_reproducibility_hook_definition(
            hook_id=SIMULATION_SEED_SCOPE_HOOK_ID,
            display_name="Simulation Seed Scope",
            description="The simulator seed attached to the suite cell for reproducible replay of stochastic simulation components.",
            sequence_index=40,
        ),
        build_experiment_suite_reproducibility_hook_definition(
            hook_id=ABLATION_SEED_SCOPE_HOOK_ID,
            display_name="Ablation Seed Scope",
            description="A perturbation seed that stays distinct from the simulator seed when an ablation family requires stochastic realization.",
            sequence_index=50,
        ),
        build_experiment_suite_reproducibility_hook_definition(
            hook_id=ARTIFACT_REFERENCE_CATALOG_HOOK_ID,
            display_name="Artifact Reference Catalog",
            description="The metadata-backed inventory that ties suite cells to upstream inputs and downstream artifacts without globbing.",
            sequence_index=60,
        ),
        build_experiment_suite_reproducibility_hook_definition(
            hook_id=STABLE_DISCOVERY_ORDER_HOOK_ID,
            display_name="Stable Discovery Order",
            description="Deterministic ordering rules for dimensions, ablations, suite cells, work items, and artifact references.",
            sequence_index=70,
        ),
    ]


def _default_lineage_invariants() -> tuple[str, ...]:
    return (
        "Every suite cell has one stable suite_cell_id that does not depend on result directory names.",
        "Every non-root suite cell carries both parent_cell_id and root_cell_id so base-condition lineage remains explicit.",
        "Dimension assignments stay attached to suite cells even when an upstream simulation plan or downstream result bundle exists.",
        "Ablation families remain explicit lineage changes instead of being hidden inside arm labels or shell flags.",
    )


def _default_reproducibility_invariants() -> tuple[str, ...]:
    return (
        "suite_spec_hash depends on normalized upstream references, suite-cell lineage, and work-item identity, not on downstream output paths.",
        "artifact discovery is metadata-backed; later tooling should not infer suite membership from ad hoc directory scans.",
        "simulation_seed and perturbation_seed are separate hooks so stochastic ablations remain auditable.",
        "earlier milestone contracts keep owning their own bundle discovery and fairness semantics; the suite layer only references them.",
    )


def _extract_experiment_suite_contract_mapping(record: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(record, Mapping):
        raise ValueError("experiment_suite contract record must be a mapping.")
    if isinstance(record.get("experiment_suite_contract"), Mapping):
        return record["experiment_suite_contract"]
    return record


def _extract_experiment_suite_mapping(record: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(record, Mapping):
        raise ValueError("experiment_suite record must be a mapping.")
    if isinstance(record.get("experiment_suite"), Mapping):
        return record["experiment_suite"]
    return record


def _build_suite_identity_payload(
    *,
    suite_id: str,
    upstream_references: Sequence[Mapping[str, Any]],
    suite_cells: Sequence[Mapping[str, Any]],
    work_items: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "suite_id": suite_id,
        "upstream_references": [
            {
                key: reference[key]
                for key in (
                    "artifact_role_id",
                    "source_kind",
                    "path",
                    "contract_version",
                    "bundle_id",
                    "artifact_id",
                    "format",
                    "artifact_scope",
                )
                if reference.get(key) is not None
            }
            for reference in upstream_references
        ],
        "suite_cells": [
            {
                "suite_cell_id": cell["suite_cell_id"],
                "lineage_kind": cell["lineage_kind"],
                "parent_cell_id": cell["parent_cell_id"],
                "root_cell_id": cell["root_cell_id"],
                "dimension_assignments": cell["dimension_assignments"],
                "ablation_references": cell["ablation_references"],
                "simulation_seed": cell["simulation_seed"],
            }
            for cell in suite_cells
        ],
        "work_items": [
            {
                "work_item_id": item["work_item_id"],
                "suite_cell_id": item["suite_cell_id"],
                "stage_id": item["stage_id"],
                "artifact_role_ids": item["artifact_role_ids"],
            }
            for item in work_items
        ],
    }


def _normalize_ownership_boundary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("ownership_boundary must be a mapping.")
    required_fields = (
        "orchestration_owner",
        "orchestration_responsibilities",
        "scientific_ablation_owner",
        "scientific_ablation_responsibilities",
        "boundary_rule",
    )
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(f"ownership_boundary is missing required fields: {missing!r}.")
    orchestration_owner = _normalize_identifier(
        payload["orchestration_owner"],
        field_name="ownership_boundary.orchestration_owner",
    )
    scientific_owner = _normalize_identifier(
        payload["scientific_ablation_owner"],
        field_name="ownership_boundary.scientific_ablation_owner",
    )
    if orchestration_owner != ORCHESTRATION_OWNER_JACK:
        raise ValueError(
            "ownership_boundary.orchestration_owner must be "
            f"{ORCHESTRATION_OWNER_JACK!r}."
        )
    if scientific_owner != SCIENTIFIC_OWNER_GRANT:
        raise ValueError(
            "ownership_boundary.scientific_ablation_owner must be "
            f"{SCIENTIFIC_OWNER_GRANT!r}."
        )
    return {
        "orchestration_owner": orchestration_owner,
        "orchestration_responsibilities": _normalize_identifier_list(
            payload["orchestration_responsibilities"],
            field_name="ownership_boundary.orchestration_responsibilities",
        ),
        "scientific_ablation_owner": scientific_owner,
        "scientific_ablation_responsibilities": _normalize_identifier_list(
            payload["scientific_ablation_responsibilities"],
            field_name="ownership_boundary.scientific_ablation_responsibilities",
        ),
        "boundary_rule": _normalize_nonempty_string(
            payload["boundary_rule"],
            field_name="ownership_boundary.boundary_rule",
        ),
    }


def _normalize_dimension_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("dimension_catalog must be a sequence.")
    normalized = [
        parse_experiment_suite_dimension_definition(item) for item in payload
    ]
    return _sorted_unique_catalog(
        normalized,
        id_key="dimension_id",
        field_name="dimension_catalog",
    )


def _normalize_ablation_family_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("ablation_family_catalog must be a sequence.")
    normalized = [
        parse_experiment_suite_ablation_family_definition(item) for item in payload
    ]
    return _sorted_unique_catalog(
        normalized,
        id_key="ablation_family_id",
        field_name="ablation_family_catalog",
    )


def _normalize_lineage_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("lineage_catalog must be a sequence.")
    normalized = [
        parse_experiment_suite_lineage_definition(item) for item in payload
    ]
    return _sorted_unique_catalog(
        normalized,
        id_key="lineage_kind",
        field_name="lineage_catalog",
    )


def _normalize_work_item_status_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("work_item_status_catalog must be a sequence.")
    normalized = [
        parse_experiment_suite_work_item_status_definition(item) for item in payload
    ]
    return _sorted_unique_catalog(
        normalized,
        id_key="status_id",
        field_name="work_item_status_catalog",
    )


def _normalize_artifact_role_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("artifact_role_catalog must be a sequence.")
    normalized = [
        parse_experiment_suite_artifact_role_definition(item) for item in payload
    ]
    return _sorted_unique_catalog(
        normalized,
        id_key="artifact_role_id",
        field_name="artifact_role_catalog",
    )


def _normalize_reproducibility_hook_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("reproducibility_hook_catalog must be a sequence.")
    normalized = [
        parse_experiment_suite_reproducibility_hook_definition(item)
        for item in payload
    ]
    return _sorted_unique_catalog(
        normalized,
        id_key="hook_id",
        field_name="reproducibility_hook_catalog",
    )


def _normalize_dimension_assignment_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("dimension_assignments must be a sequence.")
    normalized = [parse_experiment_suite_dimension_assignment(item) for item in payload]
    return _sorted_unique_pairs(
        normalized,
        key_fn=lambda item: item["dimension_id"],
        field_name="dimension_assignments",
        sort_key_fn=lambda item: (item["dimension_id"], item["value_id"]),
    )


def _normalize_ablation_reference_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("ablation_references must be a sequence.")
    normalized = [parse_experiment_suite_ablation_reference(item) for item in payload]
    return _sorted_unique_pairs(
        normalized,
        key_fn=lambda item: (item["ablation_family_id"], item["variant_id"]),
        field_name="ablation_references",
        sort_key_fn=lambda item: (item["ablation_family_id"], item["variant_id"]),
    )


def _normalize_suite_cell_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("suite_cells must be a sequence.")
    normalized = [parse_experiment_suite_cell_metadata(item) for item in payload]
    return _sorted_unique_pairs(
        normalized,
        key_fn=lambda item: item["suite_cell_id"],
        field_name="suite_cells",
        sort_key_fn=lambda item: (item["root_cell_id"] or "", item["suite_cell_id"]),
    )


def _normalize_work_item_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("work_items must be a sequence.")
    normalized = [parse_experiment_suite_work_item(item) for item in payload]
    return _sorted_unique_pairs(
        normalized,
        key_fn=lambda item: item["work_item_id"],
        field_name="work_items",
        sort_key_fn=lambda item: (item["suite_cell_id"], item["stage_id"], item["work_item_id"]),
    )


def _normalize_artifact_reference_catalog(
    payload: Any,
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence.")
    normalized = [parse_experiment_suite_artifact_reference(item) for item in payload]
    return _sorted_unique_pairs(
        normalized,
        key_fn=lambda item: (
            item["artifact_role_id"],
            item["path"],
            item["suite_cell_id"],
            item["work_item_id"],
            item["artifact_id"],
        ),
        field_name=field_name,
        sort_key_fn=lambda item: (
            item["artifact_role_id"],
            item["suite_cell_id"] or "",
            item["work_item_id"] or "",
            item["path"],
            item["artifact_id"] or "",
        ),
    )


def _validate_upstream_references_against_contract(
    references: Sequence[Mapping[str, Any]],
    *,
    contract_metadata: Mapping[str, Any],
) -> None:
    _validate_artifact_references_against_contract(
        references,
        contract_metadata=contract_metadata,
        allow_upstream_roles=True,
    )
    artifact_role_by_id = {
        item["artifact_role_id"]: item
        for item in contract_metadata["artifact_role_catalog"]
    }
    for item in references:
        artifact_scope = artifact_role_by_id[item["artifact_role_id"]]["artifact_scope"]
        if artifact_scope not in {
            UPSTREAM_MANIFEST_ARTIFACT_SCOPE,
            UPSTREAM_PLAN_ARTIFACT_SCOPE,
        }:
            raise ValueError(
                "upstream_references may contain only upstream manifest or "
                "upstream plan artifact roles."
            )


def _validate_suite_cells_against_contract(
    suite_cells: Sequence[Mapping[str, Any]],
    *,
    contract_metadata: Mapping[str, Any],
) -> None:
    supported_dimension_ids = set(contract_metadata["supported_dimension_ids"])
    supported_ablation_family_ids = set(contract_metadata["supported_ablation_family_ids"])
    lineage_by_kind = {
        item["lineage_kind"]: item for item in contract_metadata["lineage_catalog"]
    }
    known_cell_ids = {item["suite_cell_id"] for item in suite_cells}
    for item in suite_cells:
        if item["lineage_kind"] not in lineage_by_kind:
            raise ValueError(f"Unknown suite cell lineage_kind {item['lineage_kind']!r}.")
        lineage_definition = lineage_by_kind[item["lineage_kind"]]
        dimension_ids = set()
        for assignment in item["dimension_assignments"]:
            if assignment["dimension_id"] not in supported_dimension_ids:
                raise ValueError(
                    "suite cell contains unsupported dimension_id "
                    f"{assignment['dimension_id']!r}."
                )
            if assignment["dimension_id"] in dimension_ids:
                raise ValueError(
                    "suite cell may not repeat dimension_id "
                    f"{assignment['dimension_id']!r}."
                )
            dimension_ids.add(assignment["dimension_id"])
        if not dimension_ids:
            raise ValueError("suite cell must declare at least one dimension assignment.")
        for reference in item["ablation_references"]:
            if reference["ablation_family_id"] not in supported_ablation_family_ids:
                raise ValueError(
                    "suite cell contains unsupported ablation_family_id "
                    f"{reference['ablation_family_id']!r}."
                )
        if lineage_definition["requires_parent"]:
            if item["parent_cell_id"] is None:
                raise ValueError(
                    f"lineage kind {item['lineage_kind']!r} requires parent_cell_id."
                )
            if item["root_cell_id"] is None:
                raise ValueError(
                    f"lineage kind {item['lineage_kind']!r} requires root_cell_id."
                )
        else:
            if item["parent_cell_id"] is not None:
                raise ValueError(
                    f"lineage kind {item['lineage_kind']!r} may not declare parent_cell_id."
                )
            if item["root_cell_id"] != item["suite_cell_id"]:
                raise ValueError(
                    "base_condition suite cells must use suite_cell_id as root_cell_id."
                )
        if (
            not lineage_definition["introduces_ablation_family"]
            and item["ablation_references"]
        ):
            raise ValueError(
                f"lineage kind {item['lineage_kind']!r} may not declare ablation_references."
            )
        if (
            lineage_definition["introduces_ablation_family"]
            and not item["ablation_references"]
        ):
            raise ValueError(
                f"lineage kind {item['lineage_kind']!r} requires ablation_references."
            )
        if (
            lineage_definition["introduces_simulation_seed"]
            and item["simulation_seed"] is None
        ):
            raise ValueError(
                f"lineage kind {item['lineage_kind']!r} requires simulation_seed."
            )
        if (
            item["parent_cell_id"] is not None
            and item["parent_cell_id"] not in known_cell_ids
        ):
            raise ValueError(
                f"Unknown parent_cell_id {item['parent_cell_id']!r} in suite cell."
            )
        if item["root_cell_id"] is not None and item["root_cell_id"] not in known_cell_ids:
            raise ValueError(
                f"Unknown root_cell_id {item['root_cell_id']!r} in suite cell."
            )


def _validate_work_items_against_contract(
    work_items: Sequence[Mapping[str, Any]],
    *,
    suite_cells: Sequence[Mapping[str, Any]],
    contract_metadata: Mapping[str, Any],
) -> None:
    supported_statuses = set(contract_metadata["supported_work_item_statuses"])
    supported_role_ids = set(contract_metadata["supported_artifact_role_ids"])
    known_cell_ids = {item["suite_cell_id"] for item in suite_cells}
    for item in work_items:
        if item["suite_cell_id"] not in known_cell_ids:
            raise ValueError(
                f"work item references unknown suite_cell_id {item['suite_cell_id']!r}."
            )
        if item["status"] not in supported_statuses:
            raise ValueError(
                f"work item uses unsupported status {item['status']!r}."
            )
        for artifact_role_id in item["artifact_role_ids"]:
            if artifact_role_id not in supported_role_ids:
                raise ValueError(
                    "work item uses unsupported artifact_role_id "
                    f"{artifact_role_id!r}."
                )


def _validate_artifact_references_against_contract(
    references: Sequence[Mapping[str, Any]],
    *,
    contract_metadata: Mapping[str, Any],
    allow_upstream_roles: bool,
) -> None:
    role_by_id = {
        item["artifact_role_id"]: item for item in contract_metadata["artifact_role_catalog"]
    }
    for item in references:
        artifact_role_id = item["artifact_role_id"]
        if artifact_role_id not in role_by_id:
            raise ValueError(
                f"artifact reference uses unsupported artifact_role_id {artifact_role_id!r}."
            )
        role = role_by_id[artifact_role_id]
        if item["source_kind"] != role["source_kind"]:
            raise ValueError(
                "artifact reference source_kind must match the declared artifact role "
                f"for {artifact_role_id!r}."
            )
        if not allow_upstream_roles and role["artifact_scope"] in {
            UPSTREAM_MANIFEST_ARTIFACT_SCOPE,
            UPSTREAM_PLAN_ARTIFACT_SCOPE,
        }:
            raise ValueError(
                "artifact_references may not contain upstream manifest or "
                "simulation-plan roles."
            )
        required_contract_version = role["required_contract_version"]
        if required_contract_version is not None:
            if item["contract_version"] != required_contract_version:
                raise ValueError(
                    "artifact reference contract_version must match the required "
                    f"contract version for role {artifact_role_id!r}."
                )


def _validate_artifact_links(
    references: Sequence[Mapping[str, Any]],
    *,
    suite_cells: Sequence[Mapping[str, Any]],
    work_items: Sequence[Mapping[str, Any]],
) -> None:
    known_cell_ids = {item["suite_cell_id"] for item in suite_cells}
    known_work_item_ids = {item["work_item_id"] for item in work_items}
    for item in references:
        if item["suite_cell_id"] is not None and item["suite_cell_id"] not in known_cell_ids:
            raise ValueError(
                "artifact reference points at unknown suite_cell_id "
                f"{item['suite_cell_id']!r}."
            )
        if item["work_item_id"] is not None and item["work_item_id"] not in known_work_item_ids:
            raise ValueError(
                "artifact reference points at unknown work_item_id "
                f"{item['work_item_id']!r}."
            )


def _sort_suite_cells_to_contract(
    suite_cells: Sequence[Mapping[str, Any]],
    *,
    contract_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    dimension_order = {
        item["dimension_id"]: index
        for index, item in enumerate(contract_metadata["dimension_catalog"])
    }
    ablation_order = {
        item["ablation_family_id"]: index
        for index, item in enumerate(contract_metadata["ablation_family_catalog"])
    }
    ordered: list[dict[str, Any]] = []
    for item in suite_cells:
        copied = copy.deepcopy(dict(item))
        copied["dimension_assignments"] = sorted(
            copied["dimension_assignments"],
            key=lambda entry: (
                dimension_order[entry["dimension_id"]],
                entry["value_id"],
            ),
        )
        copied["ablation_references"] = sorted(
            copied["ablation_references"],
            key=lambda entry: (
                ablation_order[entry["ablation_family_id"]],
                entry["variant_id"],
            ),
        )
        ordered.append(copied)
    return sorted(
        ordered,
        key=lambda item: (
            item["root_cell_id"] or "",
            item["suite_cell_id"],
        ),
    )


def _sort_work_items_to_contract(
    work_items: Sequence[Mapping[str, Any]],
    *,
    contract_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    role_order = {
        item["artifact_role_id"]: index
        for index, item in enumerate(contract_metadata["artifact_role_catalog"])
    }
    ordered: list[dict[str, Any]] = []
    for item in work_items:
        copied = copy.deepcopy(dict(item))
        copied["artifact_role_ids"] = sorted(
            copied["artifact_role_ids"],
            key=lambda artifact_role_id: role_order[artifact_role_id],
        )
        ordered.append(copied)
    return sorted(
        ordered,
        key=lambda item: (
            item["suite_cell_id"],
            item["stage_id"],
            item["work_item_id"],
        ),
    )


def _sort_artifact_references_to_contract(
    references: Sequence[Mapping[str, Any]],
    *,
    contract_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    role_order = {
        item["artifact_role_id"]: index
        for index, item in enumerate(contract_metadata["artifact_role_catalog"])
    }
    return sorted(
        [copy.deepcopy(dict(item)) for item in references],
        key=lambda item: (
            role_order[item["artifact_role_id"]],
            item["suite_cell_id"] or "",
            item["work_item_id"] or "",
            item["path"],
            item["artifact_id"] or "",
        ),
    )


def _sorted_unique_catalog(
    items: Sequence[Mapping[str, Any]],
    *,
    id_key: str,
    field_name: str,
) -> list[dict[str, Any]]:
    return _sorted_unique_pairs(
        items,
        key_fn=lambda item: item[id_key],
        field_name=field_name,
        sort_key_fn=lambda item: (item["sequence_index"], item[id_key]),
    )


def _sorted_unique_pairs(
    items: Sequence[Mapping[str, Any]],
    *,
    key_fn: Any,
    field_name: str,
    sort_key_fn: Any,
) -> list[dict[str, Any]]:
    deduped: dict[Any, dict[str, Any]] = {}
    for item in items:
        key = key_fn(item)
        if key in deduped:
            raise ValueError(f"{field_name} contains duplicate entry {key!r}.")
        deduped[key] = copy.deepcopy(dict(item))
    return sorted(deduped.values(), key=sort_key_fn)


def _unique_ordered(values: Any) -> list[str]:
    return sorted({_normalize_nonempty_string(value, field_name="value") for value in values})


def _normalize_identifier_list(payload: Any, *, field_name: str) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence.")
    return sorted(
        {
            _normalize_identifier(value, field_name=field_name)
            for value in payload
        }
    )


def _normalize_nonempty_string_list(payload: Any, *, field_name: str) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence.")
    return sorted(
        {
            _normalize_nonempty_string(value, field_name=field_name)
            for value in payload
        }
    )


def _normalize_optional_identifier(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _normalize_identifier(value, field_name=field_name)


def _normalize_optional_nonempty_string(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _normalize_nonempty_string(value, field_name=field_name)


def _normalize_optional_int(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    normalized = _normalize_int(value, field_name=field_name)
    if normalized < 0:
        raise ValueError(f"{field_name} must be nonnegative.")
    return normalized


def _normalize_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")
    return int(value)


def _require_exact_ids(
    actual_ids: Sequence[str],
    *,
    expected_ids: Sequence[str],
    field_name: str,
) -> None:
    if set(actual_ids) != set(expected_ids):
        raise ValueError(
            f"{field_name} must contain exactly the canonical IDs for "
            f"{EXPERIMENT_SUITE_CONTRACT_VERSION}."
        )


def _require_exact_strings(
    actual_values: Sequence[str],
    *,
    expected_values: Sequence[str],
    field_name: str,
) -> None:
    if set(actual_values) != set(expected_values):
        raise ValueError(
            f"{field_name} must contain exactly the composed contract versions for "
            f"{EXPERIMENT_SUITE_CONTRACT_VERSION}."
        )
