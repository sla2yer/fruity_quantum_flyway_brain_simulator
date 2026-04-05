from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import write_json
from .simulator_result_contract import DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR
from .stimulus_contract import (
    ASSET_STATUS_READY,
    DEFAULT_HASH_ALGORITHM,
    _normalize_identifier,
    _normalize_json_mapping,
    _normalize_nonempty_string,
    _normalize_parameter_hash,
)


VALIDATION_LADDER_CONTRACT_VERSION = "validation_ladder.v1"
VALIDATION_LADDER_DESIGN_NOTE = "docs/validation_ladder_design.md"
VALIDATION_LADDER_DESIGN_NOTE_VERSION = "validation_ladder_design_note.v1"

DEFAULT_VALIDATION_DIRECTORY_NAME = "validation"
DEFAULT_REPORT_DIRECTORY_NAME = "report"

METADATA_JSON_KEY = "metadata_json"
VALIDATION_SUMMARY_ARTIFACT_ID = "validation_summary"
VALIDATOR_FINDINGS_ARTIFACT_ID = "validator_findings"
REVIEW_HANDOFF_ARTIFACT_ID = "review_handoff"
OFFLINE_REVIEW_REPORT_ARTIFACT_ID = "offline_review_report"

CONTRACT_METADATA_SCOPE = "contract_metadata"
MACHINE_SUMMARY_SCOPE = "machine_summary"
MACHINE_FINDINGS_SCOPE = "machine_findings"
REVIEW_HANDOFF_SCOPE = "review_handoff"
OFFLINE_REVIEW_SCOPE = "offline_review"
SUPPORTED_ARTIFACT_SCOPES = (
    CONTRACT_METADATA_SCOPE,
    MACHINE_SUMMARY_SCOPE,
    MACHINE_FINDINGS_SCOPE,
    REVIEW_HANDOFF_SCOPE,
    OFFLINE_REVIEW_SCOPE,
)

VALIDATION_STATUS_PASS = "pass"
VALIDATION_STATUS_REVIEW = "review"
VALIDATION_STATUS_BLOCKING = "blocking"
VALIDATION_STATUS_BLOCKED = "blocked"
SUPPORTED_VALIDATION_RESULT_STATUSES = (
    VALIDATION_STATUS_PASS,
    VALIDATION_STATUS_REVIEW,
    VALIDATION_STATUS_BLOCKING,
    VALIDATION_STATUS_BLOCKED,
)

NUMERICAL_SANITY_LAYER_ID = "numerical_sanity"
MORPHOLOGY_SANITY_LAYER_ID = "morphology_sanity"
CIRCUIT_SANITY_LAYER_ID = "circuit_sanity"
TASK_SANITY_LAYER_ID = "task_sanity"
SUPPORTED_VALIDATION_LAYER_IDS = (
    NUMERICAL_SANITY_LAYER_ID,
    MORPHOLOGY_SANITY_LAYER_ID,
    CIRCUIT_SANITY_LAYER_ID,
    TASK_SANITY_LAYER_ID,
)

NUMERICAL_STABILITY_FAMILY_ID = "numerical_stability"
MORPHOLOGY_DEPENDENCE_FAMILY_ID = "morphology_dependence"
CIRCUIT_RESPONSE_FAMILY_ID = "circuit_response"
TASK_EFFECT_REPRODUCIBILITY_FAMILY_ID = "task_effect_reproducibility"
SUPPORTED_VALIDATOR_FAMILY_IDS = (
    NUMERICAL_STABILITY_FAMILY_ID,
    MORPHOLOGY_DEPENDENCE_FAMILY_ID,
    CIRCUIT_RESPONSE_FAMILY_ID,
    TASK_EFFECT_REPRODUCIBILITY_FAMILY_ID,
)

OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID = "operator_bundle_gate_alignment"
SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID = "surface_wave_stability_envelope"
MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID = (
    "mixed_fidelity_surrogate_preservation"
)
GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID = "geometry_dependence_collapse"
COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID = "coupling_semantics_continuity"
MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID = "motion_pathway_asymmetry"
SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID = "shared_effect_reproducibility"
TASK_DECODER_ROBUSTNESS_VALIDATOR_ID = "task_decoder_robustness"
SUPPORTED_VALIDATOR_IDS = (
    OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID,
    SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
    MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID,
    GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID,
    COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID,
    MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID,
    SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID,
    TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
)

OPERATOR_QA_REVIEW_SCOPE = "operator_qa_review"
SURFACE_WAVE_INSPECTION_SCOPE = "surface_wave_inspection"
MIXED_FIDELITY_INSPECTION_SCOPE = "mixed_fidelity_inspection"
SIMULATOR_SHARED_READOUT_SCOPE = "simulator_shared_readout"
EXPERIMENT_SHARED_ANALYSIS_SCOPE = "experiment_shared_analysis"
EXPERIMENT_WAVE_DIAGNOSTIC_SCOPE = "experiment_wave_diagnostics"
EXPERIMENT_NULL_TEST_SCOPE = "experiment_null_tests"
SUPPORTED_EVIDENCE_SCOPE_IDS = (
    OPERATOR_QA_REVIEW_SCOPE,
    SURFACE_WAVE_INSPECTION_SCOPE,
    MIXED_FIDELITY_INSPECTION_SCOPE,
    SIMULATOR_SHARED_READOUT_SCOPE,
    EXPERIMENT_SHARED_ANALYSIS_SCOPE,
    EXPERIMENT_WAVE_DIAGNOSTIC_SCOPE,
    EXPERIMENT_NULL_TEST_SCOPE,
)

REVIEW_OWNER_GRANT = "grant"
SUPPORTED_REVIEW_OWNERS = (REVIEW_OWNER_GRANT,)

SUMMARY_JSON_FORMAT = "json_validation_summary.v1"
FINDINGS_JSON_FORMAT = "json_validation_findings.v1"
HANDOFF_JSON_FORMAT = "json_validation_review_handoff.v1"
OFFLINE_REPORT_MARKDOWN_FORMAT = "md_validation_report.v1"


@dataclass(frozen=True)
class ValidationBundlePaths:
    processed_simulator_results_dir: Path
    experiment_id: str
    validation_spec_hash: str
    bundle_directory: Path
    report_directory: Path
    metadata_json_path: Path
    summary_json_path: Path
    findings_json_path: Path
    review_handoff_json_path: Path
    report_markdown_path: Path

    @property
    def bundle_id(self) -> str:
        return (
            f"{VALIDATION_LADDER_CONTRACT_VERSION}:"
            f"{self.experiment_id}:{self.validation_spec_hash}"
        )

    def asset_paths(self) -> dict[str, Path]:
        return {
            METADATA_JSON_KEY: self.metadata_json_path,
            VALIDATION_SUMMARY_ARTIFACT_ID: self.summary_json_path,
            VALIDATOR_FINDINGS_ARTIFACT_ID: self.findings_json_path,
            REVIEW_HANDOFF_ARTIFACT_ID: self.review_handoff_json_path,
            OFFLINE_REVIEW_REPORT_ARTIFACT_ID: self.report_markdown_path,
        }


def build_validation_bundle_paths(
    *,
    experiment_id: str,
    validation_spec_hash: str,
    processed_simulator_results_dir: str | Path = DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
) -> ValidationBundlePaths:
    normalized_experiment_id = _normalize_identifier(
        experiment_id,
        field_name="experiment_id",
    )
    normalized_validation_spec_hash = _normalize_parameter_hash(validation_spec_hash)
    processed_dir = Path(processed_simulator_results_dir).resolve()
    bundle_directory = (
        processed_dir
        / DEFAULT_VALIDATION_DIRECTORY_NAME
        / normalized_experiment_id
        / normalized_validation_spec_hash
    ).resolve()
    report_directory = (bundle_directory / DEFAULT_REPORT_DIRECTORY_NAME).resolve()
    return ValidationBundlePaths(
        processed_simulator_results_dir=processed_dir,
        experiment_id=normalized_experiment_id,
        validation_spec_hash=normalized_validation_spec_hash,
        bundle_directory=bundle_directory,
        report_directory=report_directory,
        metadata_json_path=bundle_directory / "validation_bundle.json",
        summary_json_path=bundle_directory / "validation_summary.json",
        findings_json_path=bundle_directory / "validator_findings.json",
        review_handoff_json_path=bundle_directory / "review_handoff.json",
        report_markdown_path=report_directory / "validation_report.md",
    )


def build_validation_evidence_scope_definition(
    *,
    evidence_scope_id: str,
    display_name: str,
    description: str,
    required_upstream_contracts: Sequence[str],
    discovery_note: str,
) -> dict[str, Any]:
    return parse_validation_evidence_scope_definition(
        {
            "evidence_scope_id": evidence_scope_id,
            "display_name": display_name,
            "description": description,
            "required_upstream_contracts": list(required_upstream_contracts),
            "discovery_note": discovery_note,
        }
    )


def build_validation_layer_definition(
    *,
    layer_id: str,
    display_name: str,
    description: str,
    sequence_index: int,
    validator_family_ids: Sequence[str],
    required_upstream_contracts: Sequence[str],
) -> dict[str, Any]:
    return parse_validation_layer_definition(
        {
            "layer_id": layer_id,
            "display_name": display_name,
            "description": description,
            "sequence_index": int(sequence_index),
            "validator_family_ids": list(validator_family_ids),
            "required_upstream_contracts": list(required_upstream_contracts),
        }
    )


def build_validation_validator_family_definition(
    *,
    validator_family_id: str,
    layer_id: str,
    display_name: str,
    description: str,
    validator_ids: Sequence[str],
    required_evidence_scope_ids: Sequence[str],
    required_upstream_contracts: Sequence[str],
    default_criteria_profile_reference: str,
) -> dict[str, Any]:
    return parse_validation_validator_family_definition(
        {
            "validator_family_id": validator_family_id,
            "layer_id": layer_id,
            "display_name": display_name,
            "description": description,
            "validator_ids": list(validator_ids),
            "required_evidence_scope_ids": list(required_evidence_scope_ids),
            "required_upstream_contracts": list(required_upstream_contracts),
            "default_criteria_profile_reference": default_criteria_profile_reference,
        }
    )


def build_validation_validator_definition(
    *,
    validator_id: str,
    validator_family_id: str,
    display_name: str,
    description: str,
    required_evidence_scope_ids: Sequence[str],
    required_upstream_contracts: Sequence[str],
    criteria_profile_reference: str,
    supported_result_statuses: Sequence[str],
) -> dict[str, Any]:
    return parse_validation_validator_definition(
        {
            "validator_id": validator_id,
            "validator_family_id": validator_family_id,
            "display_name": display_name,
            "description": description,
            "required_evidence_scope_ids": list(required_evidence_scope_ids),
            "required_upstream_contracts": list(required_upstream_contracts),
            "criteria_profile_reference": criteria_profile_reference,
            "supported_result_statuses": list(supported_result_statuses),
        }
    )


def build_validation_ladder_contract_metadata(
    *,
    evidence_scopes: Sequence[Mapping[str, Any]] | None = None,
    layer_definitions: Sequence[Mapping[str, Any]] | None = None,
    validator_family_definitions: Sequence[Mapping[str, Any]] | None = None,
    validator_definitions: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {
        "contract_version": VALIDATION_LADDER_CONTRACT_VERSION,
        "design_note": VALIDATION_LADDER_DESIGN_NOTE,
        "design_note_version": VALIDATION_LADDER_DESIGN_NOTE_VERSION,
        "supported_result_statuses": list(SUPPORTED_VALIDATION_RESULT_STATUSES),
        "result_status_semantics": default_validation_result_status_semantics(),
        "criteria_handoff": default_validation_criteria_handoff(),
        "artifact_catalog": default_validation_artifact_catalog(),
        "evidence_scope_catalog": list(
            evidence_scopes
            if evidence_scopes is not None
            else _default_validation_evidence_scope_catalog()
        ),
        "layer_catalog": list(
            layer_definitions
            if layer_definitions is not None
            else _default_validation_layer_catalog()
        ),
        "validator_family_catalog": list(
            validator_family_definitions
            if validator_family_definitions is not None
            else _default_validation_validator_family_catalog()
        ),
        "validator_catalog": list(
            validator_definitions
            if validator_definitions is not None
            else _default_validation_validator_catalog()
        ),
    }
    return parse_validation_ladder_contract_metadata(payload)


def build_validation_contract_reference(
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = parse_validation_ladder_contract_metadata(
        contract_metadata
        if contract_metadata is not None
        else build_validation_ladder_contract_metadata()
    )
    return {
        "contract_version": normalized["contract_version"],
        "design_note": normalized["design_note"],
        "design_note_version": normalized["design_note_version"],
    }


def build_validation_plan_reference(
    *,
    experiment_id: str,
    contract_reference: Mapping[str, Any] | None = None,
    active_layer_ids: Sequence[str],
    active_validator_family_ids: Sequence[str],
    active_validator_ids: Sequence[str],
    criteria_profile_references: Sequence[str],
    evidence_bundle_references: Mapping[str, Any] | None = None,
    target_arm_ids: Sequence[str] | None = None,
    comparison_group_ids: Sequence[str] | None = None,
    criteria_profile_assignments: Sequence[Mapping[str, Any]] | None = None,
    perturbation_suite_references: Sequence[Mapping[str, Any]] | None = None,
    plan_version: str = "validation_plan.v1",
) -> dict[str, Any]:
    return parse_validation_plan_reference(
        {
            "experiment_id": experiment_id,
            "plan_version": plan_version,
            "contract_reference": (
                build_validation_contract_reference()
                if contract_reference is None
                else contract_reference
            ),
            "active_layer_ids": list(active_layer_ids),
            "active_validator_family_ids": list(active_validator_family_ids),
            "active_validator_ids": list(active_validator_ids),
            "criteria_profile_references": list(criteria_profile_references),
            "evidence_bundle_references": dict(evidence_bundle_references or {}),
            "target_arm_ids": list(target_arm_ids or []),
            "comparison_group_ids": list(comparison_group_ids or []),
            "criteria_profile_assignments": list(criteria_profile_assignments or []),
            "perturbation_suite_references": list(perturbation_suite_references or []),
        }
    )


def build_validation_spec_hash(validation_plan_reference: Mapping[str, Any]) -> str:
    normalized = parse_validation_plan_reference(validation_plan_reference)
    serialized = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_validation_bundle_metadata(
    *,
    validation_plan_reference: Mapping[str, Any],
    processed_simulator_results_dir: str | Path = DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_contract = parse_validation_ladder_contract_metadata(
        contract_metadata
        if contract_metadata is not None
        else build_validation_ladder_contract_metadata()
    )
    normalized_plan = parse_validation_plan_reference(validation_plan_reference)
    _validate_validation_plan_against_contract(
        validation_plan_reference=normalized_plan,
        contract_metadata=normalized_contract,
    )
    validation_spec_hash = build_validation_spec_hash(normalized_plan)
    bundle_paths = build_validation_bundle_paths(
        experiment_id=normalized_plan["experiment_id"],
        validation_spec_hash=validation_spec_hash,
        processed_simulator_results_dir=processed_simulator_results_dir,
    )
    return {
        "contract_version": VALIDATION_LADDER_CONTRACT_VERSION,
        "design_note": VALIDATION_LADDER_DESIGN_NOTE,
        "design_note_version": VALIDATION_LADDER_DESIGN_NOTE_VERSION,
        "bundle_id": bundle_paths.bundle_id,
        "experiment_id": normalized_plan["experiment_id"],
        "validation_spec_hash": validation_spec_hash,
        "validation_spec_hash_algorithm": DEFAULT_HASH_ALGORITHM,
        "validation_plan_reference": normalized_plan,
        "output_root_reference": {
            "processed_simulator_results_dir": str(
                bundle_paths.processed_simulator_results_dir
            ),
        },
        "bundle_layout": {
            "bundle_directory": str(bundle_paths.bundle_directory),
            "report_directory": str(bundle_paths.report_directory),
        },
        "artifacts": {
            METADATA_JSON_KEY: _artifact_record(
                path=bundle_paths.metadata_json_path,
                format="json_validation_bundle_metadata.v1",
                artifact_scope=CONTRACT_METADATA_SCOPE,
                description="Authoritative Milestone 13 validation bundle metadata.",
            ),
            VALIDATION_SUMMARY_ARTIFACT_ID: _artifact_record(
                path=bundle_paths.summary_json_path,
                format=SUMMARY_JSON_FORMAT,
                artifact_scope=MACHINE_SUMMARY_SCOPE,
                description="Layer- and validator-level Milestone 13 validation summary.",
            ),
            VALIDATOR_FINDINGS_ARTIFACT_ID: _artifact_record(
                path=bundle_paths.findings_json_path,
                format=FINDINGS_JSON_FORMAT,
                artifact_scope=MACHINE_FINDINGS_SCOPE,
                description="Machine-checkable validator findings keyed by stable validator_id.",
            ),
            REVIEW_HANDOFF_ARTIFACT_ID: _artifact_record(
                path=bundle_paths.review_handoff_json_path,
                format=HANDOFF_JSON_FORMAT,
                artifact_scope=REVIEW_HANDOFF_SCOPE,
                description="Grant-owned scientific plausibility handoff artifact populated after machine diagnostics.",
            ),
            OFFLINE_REVIEW_REPORT_ARTIFACT_ID: _artifact_record(
                path=bundle_paths.report_markdown_path,
                format=OFFLINE_REPORT_MARKDOWN_FORMAT,
                artifact_scope=OFFLINE_REVIEW_SCOPE,
                description="Offline reviewer-oriented Markdown report for the validation run.",
            ),
        },
    }


def build_validation_bundle_reference(
    bundle_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = parse_validation_bundle_metadata(bundle_metadata)
    return {
        "contract_version": normalized["contract_version"],
        "bundle_id": normalized["bundle_id"],
        "experiment_id": normalized["experiment_id"],
        "validation_spec_hash": normalized["validation_spec_hash"],
    }


def parse_validation_evidence_scope_definition(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("validation evidence scope definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "evidence_scope_id",
        "display_name",
        "description",
        "required_upstream_contracts",
        "discovery_note",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"validation evidence scope definition is missing fields: {missing_fields!r}."
        )
    normalized["evidence_scope_id"] = _normalize_evidence_scope_id(
        normalized["evidence_scope_id"]
    )
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="evidence_scope.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="evidence_scope.description",
    )
    normalized["required_upstream_contracts"] = _normalize_nonempty_string_list(
        normalized["required_upstream_contracts"],
        field_name="evidence_scope.required_upstream_contracts",
        allow_empty=False,
    )
    normalized["discovery_note"] = _normalize_nonempty_string(
        normalized["discovery_note"],
        field_name="evidence_scope.discovery_note",
    )
    return normalized


def parse_validation_layer_definition(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("validation layer definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "layer_id",
        "display_name",
        "description",
        "sequence_index",
        "validator_family_ids",
        "required_upstream_contracts",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"validation layer definition is missing fields: {missing_fields!r}."
        )
    normalized["layer_id"] = _normalize_layer_id(normalized["layer_id"])
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="layer.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="layer.description",
    )
    normalized["sequence_index"] = _normalize_positive_int(
        normalized["sequence_index"],
        field_name="layer.sequence_index",
    )
    normalized["validator_family_ids"] = _normalize_identifier_list(
        normalized["validator_family_ids"],
        field_name="layer.validator_family_ids",
        allow_empty=False,
    )
    normalized["required_upstream_contracts"] = _normalize_nonempty_string_list(
        normalized["required_upstream_contracts"],
        field_name="layer.required_upstream_contracts",
        allow_empty=False,
    )
    return normalized


def parse_validation_validator_family_definition(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("validation validator family definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "validator_family_id",
        "layer_id",
        "display_name",
        "description",
        "validator_ids",
        "required_evidence_scope_ids",
        "required_upstream_contracts",
        "default_criteria_profile_reference",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "validation validator family definition is missing fields: "
            f"{missing_fields!r}."
        )
    normalized["validator_family_id"] = _normalize_identifier(
        normalized["validator_family_id"],
        field_name="validator_family.validator_family_id",
    )
    normalized["layer_id"] = _normalize_layer_id(normalized["layer_id"])
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="validator_family.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="validator_family.description",
    )
    normalized["validator_ids"] = _normalize_identifier_list(
        normalized["validator_ids"],
        field_name="validator_family.validator_ids",
        allow_empty=False,
    )
    normalized["required_evidence_scope_ids"] = _normalize_evidence_scope_id_list(
        normalized["required_evidence_scope_ids"],
        field_name="validator_family.required_evidence_scope_ids",
        allow_empty=False,
    )
    normalized["required_upstream_contracts"] = _normalize_nonempty_string_list(
        normalized["required_upstream_contracts"],
        field_name="validator_family.required_upstream_contracts",
        allow_empty=False,
    )
    normalized["default_criteria_profile_reference"] = _normalize_nonempty_string(
        normalized["default_criteria_profile_reference"],
        field_name="validator_family.default_criteria_profile_reference",
    )
    return normalized


def parse_validation_validator_definition(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("validation validator definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "validator_id",
        "validator_family_id",
        "display_name",
        "description",
        "required_evidence_scope_ids",
        "required_upstream_contracts",
        "criteria_profile_reference",
        "supported_result_statuses",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"validation validator definition is missing fields: {missing_fields!r}."
        )
    normalized["validator_id"] = _normalize_identifier(
        normalized["validator_id"],
        field_name="validator.validator_id",
    )
    normalized["validator_family_id"] = _normalize_identifier(
        normalized["validator_family_id"],
        field_name="validator.validator_family_id",
    )
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="validator.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="validator.description",
    )
    normalized["required_evidence_scope_ids"] = _normalize_evidence_scope_id_list(
        normalized["required_evidence_scope_ids"],
        field_name="validator.required_evidence_scope_ids",
        allow_empty=False,
    )
    normalized["required_upstream_contracts"] = _normalize_nonempty_string_list(
        normalized["required_upstream_contracts"],
        field_name="validator.required_upstream_contracts",
        allow_empty=False,
    )
    normalized["criteria_profile_reference"] = _normalize_nonempty_string(
        normalized["criteria_profile_reference"],
        field_name="validator.criteria_profile_reference",
    )
    normalized["supported_result_statuses"] = _normalize_result_status_list(
        normalized["supported_result_statuses"],
        field_name="validator.supported_result_statuses",
        allow_empty=False,
    )
    return normalized


def parse_validation_ladder_contract_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("validation ladder contract metadata must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "design_note",
        "design_note_version",
        "supported_result_statuses",
        "result_status_semantics",
        "criteria_handoff",
        "artifact_catalog",
        "evidence_scope_catalog",
        "layer_catalog",
        "validator_family_catalog",
        "validator_catalog",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "validation ladder contract metadata is missing required fields: "
            f"{missing_fields!r}."
        )
    contract_version = _normalize_nonempty_string(
        normalized["contract_version"],
        field_name="contract_version",
    )
    if contract_version != VALIDATION_LADDER_CONTRACT_VERSION:
        raise ValueError(
            "validation ladder contract_version must be "
            f"{VALIDATION_LADDER_CONTRACT_VERSION!r}."
        )
    design_note = _normalize_nonempty_string(
        normalized["design_note"],
        field_name="design_note",
    )
    if design_note != VALIDATION_LADDER_DESIGN_NOTE:
        raise ValueError(f"design_note must be {VALIDATION_LADDER_DESIGN_NOTE!r}.")
    design_note_version = _normalize_nonempty_string(
        normalized["design_note_version"],
        field_name="design_note_version",
    )
    if design_note_version != VALIDATION_LADDER_DESIGN_NOTE_VERSION:
        raise ValueError(
            "design_note_version must be "
            f"{VALIDATION_LADDER_DESIGN_NOTE_VERSION!r}."
        )
    normalized["supported_result_statuses"] = _normalize_result_status_list(
        normalized["supported_result_statuses"],
        field_name="supported_result_statuses",
        allow_empty=False,
    )
    if tuple(normalized["supported_result_statuses"]) != SUPPORTED_VALIDATION_RESULT_STATUSES:
        raise ValueError(
            "supported_result_statuses must match the canonical validation status vocabulary."
        )
    normalized["result_status_semantics"] = _normalize_result_status_semantics(
        normalized["result_status_semantics"]
    )
    normalized["criteria_handoff"] = _normalize_criteria_handoff(
        normalized["criteria_handoff"]
    )
    normalized["artifact_catalog"] = _normalize_artifact_catalog(
        normalized["artifact_catalog"]
    )
    normalized["evidence_scope_catalog"] = _normalize_evidence_scope_catalog(
        normalized["evidence_scope_catalog"]
    )
    normalized["layer_catalog"] = _normalize_layer_catalog(normalized["layer_catalog"])
    normalized["validator_family_catalog"] = _normalize_validator_family_catalog(
        normalized["validator_family_catalog"]
    )
    normalized["validator_catalog"] = _normalize_validator_catalog(
        normalized["validator_catalog"]
    )

    evidence_scope_ids = {
        item["evidence_scope_id"] for item in normalized["evidence_scope_catalog"]
    }
    layer_ids = {item["layer_id"] for item in normalized["layer_catalog"]}
    family_ids = {
        item["validator_family_id"] for item in normalized["validator_family_catalog"]
    }
    family_by_id = {
        item["validator_family_id"]: item
        for item in normalized["validator_family_catalog"]
    }
    validator_by_id = {
        item["validator_id"]: item for item in normalized["validator_catalog"]
    }

    if evidence_scope_ids != set(SUPPORTED_EVIDENCE_SCOPE_IDS):
        raise ValueError(
            "validation ladder contract must declare the canonical evidence scope ids."
        )
    if layer_ids != set(SUPPORTED_VALIDATION_LAYER_IDS):
        raise ValueError(
            "validation ladder contract must declare the four canonical Milestone 13 layer ids."
        )
    if family_ids != set(SUPPORTED_VALIDATOR_FAMILY_IDS):
        raise ValueError(
            "validation ladder contract must declare the first canonical Milestone 13 validator family ids."
        )
    if set(validator_by_id) != set(SUPPORTED_VALIDATOR_IDS):
        raise ValueError(
            "validation ladder contract must declare the first canonical Milestone 13 validator ids."
        )

    for layer in normalized["layer_catalog"]:
        unknown_family_ids = sorted(
            set(layer["validator_family_ids"]) - set(family_by_id)
        )
        if unknown_family_ids:
            raise ValueError(
                f"layer {layer['layer_id']!r} references unknown validator_family_ids {unknown_family_ids!r}."
            )

    for family in normalized["validator_family_catalog"]:
        if family["layer_id"] not in layer_ids:
            raise ValueError(
                f"validator_family {family['validator_family_id']!r} references unknown layer_id {family['layer_id']!r}."
            )
        layer = next(
            item for item in normalized["layer_catalog"] if item["layer_id"] == family["layer_id"]
        )
        if family["validator_family_id"] not in set(layer["validator_family_ids"]):
            raise ValueError(
                "validator_family "
                f"{family['validator_family_id']!r} must be listed in layer {family['layer_id']!r}."
            )
        unknown_validator_ids = sorted(
            set(family["validator_ids"]) - set(validator_by_id)
        )
        if unknown_validator_ids:
            raise ValueError(
                "validator_family "
                f"{family['validator_family_id']!r} references unknown validator_ids {unknown_validator_ids!r}."
            )
        unknown_scope_ids = sorted(
            set(family["required_evidence_scope_ids"]) - evidence_scope_ids
        )
        if unknown_scope_ids:
            raise ValueError(
                "validator_family "
                f"{family['validator_family_id']!r} references unknown evidence scopes {unknown_scope_ids!r}."
            )

    for validator in normalized["validator_catalog"]:
        family_id = validator["validator_family_id"]
        if family_id not in family_by_id:
            raise ValueError(
                f"validator {validator['validator_id']!r} references unknown validator_family_id {family_id!r}."
            )
        family = family_by_id[family_id]
        if validator["validator_id"] not in set(family["validator_ids"]):
            raise ValueError(
                f"validator {validator['validator_id']!r} must be listed in validator_family {family_id!r}."
            )
        unknown_scope_ids = sorted(
            set(validator["required_evidence_scope_ids"]) - evidence_scope_ids
        )
        if unknown_scope_ids:
            raise ValueError(
                f"validator {validator['validator_id']!r} references unknown evidence scopes {unknown_scope_ids!r}."
            )

    return {
        "contract_version": contract_version,
        "design_note": design_note,
        "design_note_version": design_note_version,
        "supported_result_statuses": normalized["supported_result_statuses"],
        "result_status_semantics": normalized["result_status_semantics"],
        "criteria_handoff": normalized["criteria_handoff"],
        "artifact_catalog": normalized["artifact_catalog"],
        "evidence_scope_catalog": normalized["evidence_scope_catalog"],
        "layer_catalog": normalized["layer_catalog"],
        "validator_family_catalog": normalized["validator_family_catalog"],
        "validator_catalog": normalized["validator_catalog"],
    }


def parse_validation_plan_reference(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("validation plan reference must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "experiment_id",
        "plan_version",
        "contract_reference",
        "active_layer_ids",
        "active_validator_family_ids",
        "active_validator_ids",
        "criteria_profile_references",
        "evidence_bundle_references",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"validation plan reference is missing required fields {missing_fields!r}."
        )
    normalized["experiment_id"] = _normalize_identifier(
        normalized["experiment_id"],
        field_name="validation_plan.experiment_id",
    )
    normalized["plan_version"] = _normalize_nonempty_string(
        normalized["plan_version"],
        field_name="validation_plan.plan_version",
    )
    normalized["contract_reference"] = _normalize_contract_reference(
        normalized["contract_reference"]
    )
    normalized["active_layer_ids"] = _normalize_layer_id_list(
        normalized["active_layer_ids"],
        field_name="validation_plan.active_layer_ids",
        allow_empty=False,
    )
    normalized["active_validator_family_ids"] = _normalize_identifier_list(
        normalized["active_validator_family_ids"],
        field_name="validation_plan.active_validator_family_ids",
        allow_empty=False,
    )
    normalized["active_validator_ids"] = _normalize_identifier_list(
        normalized["active_validator_ids"],
        field_name="validation_plan.active_validator_ids",
        allow_empty=False,
    )
    normalized["criteria_profile_references"] = _normalize_nonempty_string_list(
        normalized["criteria_profile_references"],
        field_name="validation_plan.criteria_profile_references",
        allow_empty=False,
    )
    normalized["evidence_bundle_references"] = _normalize_json_mapping(
        normalized["evidence_bundle_references"],
        field_name="validation_plan.evidence_bundle_references",
    )
    normalized["target_arm_ids"] = _normalize_identifier_list(
        normalized.get("target_arm_ids", []),
        field_name="validation_plan.target_arm_ids",
        allow_empty=True,
    )
    normalized["comparison_group_ids"] = _normalize_identifier_list(
        normalized.get("comparison_group_ids", []),
        field_name="validation_plan.comparison_group_ids",
        allow_empty=True,
    )
    normalized["criteria_profile_assignments"] = _normalize_criteria_profile_assignments(
        normalized.get("criteria_profile_assignments", []),
    )
    normalized["perturbation_suite_references"] = _normalize_perturbation_suite_references(
        normalized.get("perturbation_suite_references", []),
    )
    return normalized


def parse_validation_bundle_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("validation bundle metadata must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "design_note",
        "design_note_version",
        "bundle_id",
        "experiment_id",
        "validation_spec_hash",
        "validation_spec_hash_algorithm",
        "validation_plan_reference",
        "output_root_reference",
        "bundle_layout",
        "artifacts",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"validation bundle metadata is missing required fields {missing_fields!r}."
        )
    contract_version = _normalize_nonempty_string(
        normalized["contract_version"],
        field_name="contract_version",
    )
    if contract_version != VALIDATION_LADDER_CONTRACT_VERSION:
        raise ValueError(
            "validation bundle metadata contract_version must be "
            f"{VALIDATION_LADDER_CONTRACT_VERSION!r}."
        )
    design_note = _normalize_nonempty_string(
        normalized["design_note"],
        field_name="design_note",
    )
    if design_note != VALIDATION_LADDER_DESIGN_NOTE:
        raise ValueError(f"design_note must be {VALIDATION_LADDER_DESIGN_NOTE!r}.")
    design_note_version = _normalize_nonempty_string(
        normalized["design_note_version"],
        field_name="design_note_version",
    )
    if design_note_version != VALIDATION_LADDER_DESIGN_NOTE_VERSION:
        raise ValueError(
            "design_note_version must be "
            f"{VALIDATION_LADDER_DESIGN_NOTE_VERSION!r}."
        )
    experiment_id = _normalize_identifier(
        normalized["experiment_id"],
        field_name="experiment_id",
    )
    validation_spec_hash = _normalize_parameter_hash(
        normalized["validation_spec_hash"]
    )
    bundle_id = _normalize_nonempty_string(
        normalized["bundle_id"],
        field_name="bundle_id",
    )
    expected_bundle_id = (
        f"{VALIDATION_LADDER_CONTRACT_VERSION}:{experiment_id}:{validation_spec_hash}"
    )
    if bundle_id != expected_bundle_id:
        raise ValueError(
            "bundle_id must match the canonical validation bundle identity."
        )
    hash_algorithm = _normalize_nonempty_string(
        normalized["validation_spec_hash_algorithm"],
        field_name="validation_spec_hash_algorithm",
    )
    if hash_algorithm != DEFAULT_HASH_ALGORITHM:
        raise ValueError(
            f"validation_spec_hash_algorithm must be {DEFAULT_HASH_ALGORITHM!r}."
        )
    validation_plan_reference = parse_validation_plan_reference(
        normalized["validation_plan_reference"]
    )
    if validation_plan_reference["experiment_id"] != experiment_id:
        raise ValueError(
            "validation_plan_reference.experiment_id must match experiment_id."
        )
    output_root_reference = _normalize_output_root_reference(
        normalized["output_root_reference"]
    )
    bundle_paths = build_validation_bundle_paths(
        experiment_id=experiment_id,
        validation_spec_hash=validation_spec_hash,
        processed_simulator_results_dir=output_root_reference[
            "processed_simulator_results_dir"
        ],
    )
    bundle_layout = _normalize_bundle_layout(
        normalized["bundle_layout"],
        expected_bundle_paths=bundle_paths,
    )
    artifacts = _normalize_bundle_artifacts(
        normalized["artifacts"],
        expected_paths=bundle_paths.asset_paths(),
    )
    return {
        "contract_version": contract_version,
        "design_note": design_note,
        "design_note_version": design_note_version,
        "bundle_id": bundle_id,
        "experiment_id": experiment_id,
        "validation_spec_hash": validation_spec_hash,
        "validation_spec_hash_algorithm": hash_algorithm,
        "validation_plan_reference": validation_plan_reference,
        "output_root_reference": output_root_reference,
        "bundle_layout": bundle_layout,
        "artifacts": artifacts,
    }


def write_validation_ladder_contract_metadata(
    contract_metadata: Mapping[str, Any],
    metadata_path: str | Path,
) -> Path:
    normalized = parse_validation_ladder_contract_metadata(contract_metadata)
    return write_json(normalized, metadata_path)


def load_validation_ladder_contract_metadata(metadata_path: str | Path) -> dict[str, Any]:
    with Path(metadata_path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_validation_ladder_contract_metadata(payload)


def write_validation_bundle_metadata(
    bundle_metadata: Mapping[str, Any],
    output_path: str | Path | None = None,
) -> Path:
    normalized = parse_validation_bundle_metadata(bundle_metadata)
    target_path = (
        Path(output_path).resolve()
        if output_path is not None
        else Path(normalized["artifacts"][METADATA_JSON_KEY]["path"]).resolve()
    )
    return write_json(normalized, target_path)


def load_validation_bundle_metadata(metadata_path: str | Path) -> dict[str, Any]:
    with Path(metadata_path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_validation_bundle_metadata(payload)


def resolve_validation_bundle_metadata_path(
    *,
    processed_simulator_results_dir: str | Path,
    validation_plan_reference: Mapping[str, Any] | None = None,
    bundle_reference: Mapping[str, Any] | None = None,
) -> Path:
    experiment_id, validation_spec_hash = _resolve_validation_bundle_identity(
        validation_plan_reference=validation_plan_reference,
        bundle_reference=bundle_reference,
    )
    bundle_paths = build_validation_bundle_paths(
        experiment_id=experiment_id,
        validation_spec_hash=validation_spec_hash,
        processed_simulator_results_dir=processed_simulator_results_dir,
    )
    return bundle_paths.metadata_json_path.resolve()


def lookup_validation_bundle_metadata_path(
    *,
    processed_simulator_results_dir: str | Path,
    validation_plan_reference: Mapping[str, Any] | None = None,
    bundle_reference: Mapping[str, Any] | None = None,
    experiment_id: str | None = None,
    analysis_bundle_reference: Mapping[str, Any] | None = None,
    simulator_result_bundle_ids: Sequence[str] | None = None,
    target_arm_ids: Sequence[str] | None = None,
) -> Path:
    if validation_plan_reference is not None or bundle_reference is not None:
        metadata_path = resolve_validation_bundle_metadata_path(
            processed_simulator_results_dir=processed_simulator_results_dir,
            validation_plan_reference=validation_plan_reference,
            bundle_reference=bundle_reference,
        )
        if metadata_path.exists():
            return metadata_path
        raise ValueError(
            "validation_bundle metadata was not found at the canonical contract path "
            f"{metadata_path}."
        )

    normalized_experiment_id = _normalize_identifier(
        experiment_id,
        field_name="experiment_id",
    )
    validation_root = (
        Path(processed_simulator_results_dir).resolve()
        / DEFAULT_VALIDATION_DIRECTORY_NAME
        / normalized_experiment_id
    ).resolve()
    candidate_paths = sorted(validation_root.glob("*/validation_bundle.json"))
    if not candidate_paths:
        raise ValueError(
            "validation_bundle lookup requires local bundle metadata for "
            f"experiment_id {normalized_experiment_id!r} under {validation_root}."
        )

    requested_analysis_bundle_id = _normalize_optional_bundle_id(
        analysis_bundle_reference,
        field_name="analysis_bundle_reference",
    )
    requested_simulator_bundle_ids = _normalize_bundle_id_filters(
        simulator_result_bundle_ids,
        field_name="simulator_result_bundle_ids",
    )
    requested_target_arm_ids = _normalize_identifier_sequence(
        target_arm_ids,
        field_name="target_arm_ids",
    )

    matches: list[dict[str, Any]] = []
    for path in candidate_paths:
        metadata = load_validation_bundle_metadata(path)
        plan_reference = metadata["validation_plan_reference"]
        evidence_refs = plan_reference.get("evidence_bundle_references", {})
        if requested_analysis_bundle_id is not None:
            analysis_ref = evidence_refs.get("experiment_analysis_bundle")
            if (
                not isinstance(analysis_ref, Mapping)
                or _normalize_optional_bundle_id(
                    analysis_ref,
                    field_name="validation_plan_reference.evidence_bundle_references.experiment_analysis_bundle",
                )
                != requested_analysis_bundle_id
            ):
                continue
        if requested_simulator_bundle_ids:
            simulator_ref = _normalize_json_mapping(
                evidence_refs.get("simulator_result_bundle", {}),
                field_name="validation_plan_reference.evidence_bundle_references.simulator_result_bundle",
            )
            available_bundle_ids = _normalize_bundle_id_filters(
                simulator_ref.get("bundle_ids"),
                field_name="validation_plan_reference.evidence_bundle_references.simulator_result_bundle.bundle_ids",
            )
            if not requested_simulator_bundle_ids.issubset(available_bundle_ids):
                continue
        if requested_target_arm_ids:
            available_target_arm_ids = _normalize_identifier_sequence(
                plan_reference.get("target_arm_ids", []),
                field_name="validation_plan_reference.target_arm_ids",
            )
            if available_target_arm_ids and not requested_target_arm_ids.issubset(
                available_target_arm_ids
            ):
                continue
        matches.append(metadata)

    if not matches:
        filter_descriptions: list[str] = []
        if requested_analysis_bundle_id is not None:
            filter_descriptions.append(
                f"analysis bundle_id {requested_analysis_bundle_id!r}"
            )
        if requested_simulator_bundle_ids:
            filter_descriptions.append(
                f"simulator bundle_ids {sorted(requested_simulator_bundle_ids)!r}"
            )
        if requested_target_arm_ids:
            filter_descriptions.append(
                f"target_arm_ids {sorted(requested_target_arm_ids)!r}"
            )
        suffix = "" if not filter_descriptions else " matching " + " and ".join(filter_descriptions)
        raise ValueError(
            "validation_bundle lookup could not find bundle metadata "
            f"for experiment_id {normalized_experiment_id!r}{suffix}."
        )
    if len(matches) > 1:
        raise ValueError(
            "validation_bundle lookup found multiple bundle metadata candidates "
            f"for experiment_id {normalized_experiment_id!r}. Pass an explicit metadata path "
            "or contract identity to disambiguate."
        )
    return Path(matches[0]["artifacts"][METADATA_JSON_KEY]["path"]).resolve()


def lookup_validation_bundle_metadata(
    *,
    processed_simulator_results_dir: str | Path,
    validation_plan_reference: Mapping[str, Any] | None = None,
    bundle_reference: Mapping[str, Any] | None = None,
    experiment_id: str | None = None,
    analysis_bundle_reference: Mapping[str, Any] | None = None,
    simulator_result_bundle_ids: Sequence[str] | None = None,
    target_arm_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    metadata_path = lookup_validation_bundle_metadata_path(
        processed_simulator_results_dir=processed_simulator_results_dir,
        validation_plan_reference=validation_plan_reference,
        bundle_reference=bundle_reference,
        experiment_id=experiment_id,
        analysis_bundle_reference=analysis_bundle_reference,
        simulator_result_bundle_ids=simulator_result_bundle_ids,
        target_arm_ids=target_arm_ids,
    )
    return load_validation_bundle_metadata(metadata_path)


def discover_validation_evidence_scopes(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    metadata = parse_validation_ladder_contract_metadata(
        _extract_validation_contract_mapping(record)
    )
    return [copy.deepcopy(item) for item in metadata["evidence_scope_catalog"]]


def discover_validation_layers(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    metadata = parse_validation_ladder_contract_metadata(
        _extract_validation_contract_mapping(record)
    )
    return [copy.deepcopy(item) for item in metadata["layer_catalog"]]


def discover_validation_validator_families(
    record: Mapping[str, Any],
    *,
    layer_id: str | None = None,
    evidence_scope_id: str | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_validation_ladder_contract_metadata(
        _extract_validation_contract_mapping(record)
    )
    normalized_layer_id = None if layer_id is None else _normalize_layer_id(layer_id)
    normalized_scope_id = (
        None if evidence_scope_id is None else _normalize_evidence_scope_id(evidence_scope_id)
    )
    discovered: list[dict[str, Any]] = []
    for item in metadata["validator_family_catalog"]:
        if normalized_layer_id is not None and item["layer_id"] != normalized_layer_id:
            continue
        if (
            normalized_scope_id is not None
            and normalized_scope_id not in set(item["required_evidence_scope_ids"])
        ):
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def discover_validation_validator_definitions(
    record: Mapping[str, Any],
    *,
    layer_id: str | None = None,
    validator_family_id: str | None = None,
    evidence_scope_id: str | None = None,
    criteria_profile_reference: str | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_validation_ladder_contract_metadata(
        _extract_validation_contract_mapping(record)
    )
    family_by_id = {
        item["validator_family_id"]: item for item in metadata["validator_family_catalog"]
    }
    normalized_layer_id = None if layer_id is None else _normalize_layer_id(layer_id)
    normalized_family_id = (
        None
        if validator_family_id is None
        else _normalize_identifier(
            validator_family_id,
            field_name="validator_family_id",
        )
    )
    normalized_scope_id = (
        None if evidence_scope_id is None else _normalize_evidence_scope_id(evidence_scope_id)
    )
    normalized_profile_reference = (
        None
        if criteria_profile_reference is None
        else _normalize_nonempty_string(
            criteria_profile_reference,
            field_name="criteria_profile_reference",
        )
    )
    discovered: list[dict[str, Any]] = []
    for item in metadata["validator_catalog"]:
        family = family_by_id[item["validator_family_id"]]
        if normalized_layer_id is not None and family["layer_id"] != normalized_layer_id:
            continue
        if normalized_family_id is not None and item["validator_family_id"] != normalized_family_id:
            continue
        if (
            normalized_scope_id is not None
            and normalized_scope_id not in set(item["required_evidence_scope_ids"])
        ):
            continue
        if (
            normalized_profile_reference is not None
            and item["criteria_profile_reference"] != normalized_profile_reference
        ):
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def get_validation_validator_definition(
    validator_id: str,
    *,
    record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_validator_id = _normalize_identifier(
        validator_id,
        field_name="validator_id",
    )
    metadata = parse_validation_ladder_contract_metadata(
        _extract_validation_contract_mapping(
            record if record is not None else build_validation_ladder_contract_metadata()
        )
    )
    for item in metadata["validator_catalog"]:
        if item["validator_id"] == normalized_validator_id:
            return copy.deepcopy(item)
    raise KeyError(f"Unknown validation validator_id {normalized_validator_id!r}.")


def discover_validation_bundle_paths(record: Mapping[str, Any]) -> dict[str, Path]:
    normalized = parse_validation_bundle_metadata(
        record.get("validation_bundle")
        if isinstance(record.get("validation_bundle"), Mapping)
        else record
    )
    return {
        artifact_id: Path(str(artifact["path"])).resolve()
        for artifact_id, artifact in normalized["artifacts"].items()
    }


def default_validation_result_status_semantics() -> dict[str, str]:
    return {
        VALIDATION_STATUS_PASS: (
            "All machine-checkable diagnostics satisfied the active criteria profile "
            "on the declared evidence scopes."
        ),
        VALIDATION_STATUS_REVIEW: (
            "The validator produced stable machine findings, but Grant review is "
            "required before treating the result as scientifically plausible or sufficient."
        ),
        VALIDATION_STATUS_BLOCKING: (
            "A blocking contract invariant or criteria threshold was violated, so "
            "the validation run is not comparable until the issue is addressed."
        ),
        VALIDATION_STATUS_BLOCKED: (
            "Required local evidence was missing, incompatible, or undiscoverable, "
            "so the validator could not complete."
        ),
    }


def default_validation_criteria_handoff() -> dict[str, Any]:
    return {
        "machine_findings_rule": (
            "Validators may emit findings only from contract-declared evidence "
            "scopes, upstream contract surfaces, and criteria-profile references."
        ),
        "machine_findings_stop_at": "scientific_plausibility_handoff",
        "machine_findings_may_not_assert": [
            "biological_plausibility",
            "claim_acceptance",
            "scientific_sufficiency",
        ],
        "review_owner": REVIEW_OWNER_GRANT,
        "review_status": VALIDATION_STATUS_REVIEW,
        "review_artifact_id": REVIEW_HANDOFF_ARTIFACT_ID,
        "required_reviewer_fields": [
            "scientific_plausibility_decision",
            "reviewer_rationale",
            "follow_on_action",
        ],
    }


def default_validation_artifact_catalog() -> dict[str, Any]:
    return {
        METADATA_JSON_KEY: {
            "artifact_scope": CONTRACT_METADATA_SCOPE,
            "format": "json_validation_bundle_metadata.v1",
            "relative_path": "validation_bundle.json",
            "description": "Authoritative validation bundle metadata.",
        },
        VALIDATION_SUMMARY_ARTIFACT_ID: {
            "artifact_scope": MACHINE_SUMMARY_SCOPE,
            "format": SUMMARY_JSON_FORMAT,
            "relative_path": "validation_summary.json",
            "description": "Machine-readable validation summary for layers and validators.",
        },
        VALIDATOR_FINDINGS_ARTIFACT_ID: {
            "artifact_scope": MACHINE_FINDINGS_SCOPE,
            "format": FINDINGS_JSON_FORMAT,
            "relative_path": "validator_findings.json",
            "description": "Stable validator findings keyed by validator_id.",
        },
        REVIEW_HANDOFF_ARTIFACT_ID: {
            "artifact_scope": REVIEW_HANDOFF_SCOPE,
            "format": HANDOFF_JSON_FORMAT,
            "relative_path": "review_handoff.json",
            "description": "Grant-owned scientific plausibility handoff payload.",
        },
        OFFLINE_REVIEW_REPORT_ARTIFACT_ID: {
            "artifact_scope": OFFLINE_REVIEW_SCOPE,
            "format": OFFLINE_REPORT_MARKDOWN_FORMAT,
            "relative_path": "report/validation_report.md",
            "description": "Offline Markdown validation report.",
        },
    }


def _default_validation_evidence_scope_catalog() -> list[dict[str, Any]]:
    return [
        build_validation_evidence_scope_definition(
            evidence_scope_id=OPERATOR_QA_REVIEW_SCOPE,
            display_name="Operator QA Review",
            description=(
                "Milestone 6 operator QA and readiness artifacts that define the "
                "numerical baseline for later validation work."
            ),
            required_upstream_contracts=["geometry_bundle.v1"],
            discovery_note=(
                "Resolve operator QA summaries and readiness gates from the "
                "geometry/operator bundle workflow instead of recomputing ad hoc metrics."
            ),
        ),
        build_validation_evidence_scope_definition(
            evidence_scope_id=SURFACE_WAVE_INSPECTION_SCOPE,
            display_name="Surface-Wave Inspection",
            description=(
                "Milestone 10 inspection summaries and local sweep diagnostics for "
                "surface-wave stability and suspicious numerical behavior."
            ),
            required_upstream_contracts=[
                "surface_wave_model.v1",
                "simulator_result_bundle.v1",
            ],
            discovery_note=(
                "Use the contract-backed Milestone 10 inspection outputs and "
                "simulator-result artifacts rather than raw console logs."
            ),
        ),
        build_validation_evidence_scope_definition(
            evidence_scope_id=MIXED_FIDELITY_INSPECTION_SCOPE,
            display_name="Mixed-Fidelity Inspection",
            description=(
                "Milestone 11 surrogate-versus-reference inspection summaries for "
                "promotion, demotion, and approximation drift review."
            ),
            required_upstream_contracts=[
                "hybrid_morphology.v1",
                "simulator_result_bundle.v1",
            ],
            discovery_note=(
                "Resolve mixed-fidelity inspection artifacts from the Milestone 11 "
                "inspection workflow instead of inventing validator-local surrogate comparisons."
            ),
        ),
        build_validation_evidence_scope_definition(
            evidence_scope_id=SIMULATOR_SHARED_READOUT_SCOPE,
            display_name="Simulator Shared Readout",
            description=(
                "Milestone 9 shared comparison surface from simulator_result_bundle.v1."
            ),
            required_upstream_contracts=["simulator_result_bundle.v1"],
            discovery_note=(
                "Read only the contract-owned shared readout catalog, timebase, and "
                "trace artifacts from simulator_result_bundle.v1."
            ),
        ),
        build_validation_evidence_scope_definition(
            evidence_scope_id=EXPERIMENT_SHARED_ANALYSIS_SCOPE,
            display_name="Experiment Shared Analysis",
            description=(
                "Milestone 12 shared-comparison metrics and packaged analysis outputs "
                "that stay on the locked T4a/T5a readout boundary."
            ),
            required_upstream_contracts=[
                "readout_analysis.v1",
                "experiment_analysis_bundle.v1",
            ],
            discovery_note=(
                "Use the packaged Milestone 12 experiment-analysis bundle instead of "
                "recomputing task-layer metrics from scratch."
            ),
        ),
        build_validation_evidence_scope_definition(
            evidence_scope_id=EXPERIMENT_WAVE_DIAGNOSTIC_SCOPE,
            display_name="Experiment Wave Diagnostics",
            description=(
                "Milestone 12 wave-only morphology diagnostics packaged alongside the "
                "fair shared comparison outputs."
            ),
            required_upstream_contracts=[
                "readout_analysis.v1",
                "experiment_analysis_bundle.v1",
            ],
            discovery_note=(
                "Consume only the explicitly labeled wave-diagnostic outputs from the "
                "experiment-analysis bundle."
            ),
        ),
        build_validation_evidence_scope_definition(
            evidence_scope_id=EXPERIMENT_NULL_TEST_SCOPE,
            display_name="Experiment Null Tests",
            description=(
                "Milestone 12 null-test outputs that quantify geometry shuffles, "
                "baseline challenges, and other perturbation checks."
            ),
            required_upstream_contracts=[
                "readout_analysis.v1",
                "experiment_analysis_bundle.v1",
            ],
            discovery_note=(
                "Reuse the packaged null-test table and decision surfaces from "
                "experiment_analysis_bundle.v1."
            ),
        ),
    ]


def _default_validation_layer_catalog() -> list[dict[str, Any]]:
    return [
        build_validation_layer_definition(
            layer_id=NUMERICAL_SANITY_LAYER_ID,
            display_name="Numerical Sanity",
            description=(
                "Numerical sanity starts from Milestone 6 operator QA and "
                "Milestone 10 surface-wave inspection rather than validator-local probes."
            ),
            sequence_index=10,
            validator_family_ids=[NUMERICAL_STABILITY_FAMILY_ID],
            required_upstream_contracts=[
                "geometry_bundle.v1",
                "surface_wave_model.v1",
                "simulator_result_bundle.v1",
            ],
        ),
        build_validation_layer_definition(
            layer_id=MORPHOLOGY_SANITY_LAYER_ID,
            display_name="Morphology Sanity",
            description=(
                "Morphology sanity checks geometry dependence and mixed-fidelity "
                "surrogate behavior without moving off the contract-owned simulator and analysis surfaces."
            ),
            sequence_index=20,
            validator_family_ids=[MORPHOLOGY_DEPENDENCE_FAMILY_ID],
            required_upstream_contracts=[
                "hybrid_morphology.v1",
                "simulator_result_bundle.v1",
                "experiment_analysis_bundle.v1",
            ],
        ),
        build_validation_layer_definition(
            layer_id=CIRCUIT_SANITY_LAYER_ID,
            display_name="Circuit Sanity",
            description=(
                "Circuit sanity checks sign, delay, aggregation, and pathway-level "
                "response patterns on the shared result surface."
            ),
            sequence_index=30,
            validator_family_ids=[CIRCUIT_RESPONSE_FAMILY_ID],
            required_upstream_contracts=[
                "coupling_bundle.v1",
                "simulator_result_bundle.v1",
                "readout_analysis.v1",
                "experiment_analysis_bundle.v1",
            ],
        ),
        build_validation_layer_definition(
            layer_id=TASK_SANITY_LAYER_ID,
            display_name="Task Sanity",
            description=(
                "Task sanity checks the reproducibility and perturbation behavior "
                "of the shared-effect and task-layer outputs already packaged by Milestone 12."
            ),
            sequence_index=40,
            validator_family_ids=[TASK_EFFECT_REPRODUCIBILITY_FAMILY_ID],
            required_upstream_contracts=[
                "simulator_result_bundle.v1",
                "readout_analysis.v1",
                "experiment_analysis_bundle.v1",
            ],
        ),
    ]


def _default_validation_validator_family_catalog() -> list[dict[str, Any]]:
    return [
        build_validation_validator_family_definition(
            validator_family_id=NUMERICAL_STABILITY_FAMILY_ID,
            layer_id=NUMERICAL_SANITY_LAYER_ID,
            display_name="Numerical Stability",
            description=(
                "First Milestone 13 numerical family: reuse operator QA and surface-wave "
                "inspection signals as the canonical numerical validation baseline."
            ),
            validator_ids=[
                "operator_bundle_gate_alignment",
                "surface_wave_stability_envelope",
            ],
            required_evidence_scope_ids=[
                OPERATOR_QA_REVIEW_SCOPE,
                SURFACE_WAVE_INSPECTION_SCOPE,
            ],
            required_upstream_contracts=[
                "geometry_bundle.v1",
                "surface_wave_model.v1",
                "simulator_result_bundle.v1",
            ],
            default_criteria_profile_reference=(
                "validation_criteria.numerical_stability.default_local_review.v1"
            ),
        ),
        build_validation_validator_family_definition(
            validator_family_id=MORPHOLOGY_DEPENDENCE_FAMILY_ID,
            layer_id=MORPHOLOGY_SANITY_LAYER_ID,
            display_name="Morphology Dependence",
            description=(
                "First Milestone 13 morphology family: preserve mixed-fidelity "
                "surrogate expectations and geometry-dependent collapse semantics."
            ),
            validator_ids=[
                "mixed_fidelity_surrogate_preservation",
                "geometry_dependence_collapse",
            ],
            required_evidence_scope_ids=[
                MIXED_FIDELITY_INSPECTION_SCOPE,
                EXPERIMENT_SHARED_ANALYSIS_SCOPE,
                EXPERIMENT_WAVE_DIAGNOSTIC_SCOPE,
                EXPERIMENT_NULL_TEST_SCOPE,
            ],
            required_upstream_contracts=[
                "hybrid_morphology.v1",
                "simulator_result_bundle.v1",
                "readout_analysis.v1",
                "experiment_analysis_bundle.v1",
            ],
            default_criteria_profile_reference=(
                "validation_criteria.morphology_dependence.default_local_review.v1"
            ),
        ),
        build_validation_validator_family_definition(
            validator_family_id=CIRCUIT_RESPONSE_FAMILY_ID,
            layer_id=CIRCUIT_SANITY_LAYER_ID,
            display_name="Circuit Response",
            description=(
                "First Milestone 13 circuit family: keep validation on the existing "
                "coupling semantics and shared-readout comparison surface."
            ),
            validator_ids=[
                "coupling_semantics_continuity",
                "motion_pathway_asymmetry",
            ],
            required_evidence_scope_ids=[
                SIMULATOR_SHARED_READOUT_SCOPE,
                EXPERIMENT_SHARED_ANALYSIS_SCOPE,
            ],
            required_upstream_contracts=[
                "coupling_bundle.v1",
                "simulator_result_bundle.v1",
                "readout_analysis.v1",
                "experiment_analysis_bundle.v1",
            ],
            default_criteria_profile_reference=(
                "validation_criteria.circuit_response.default_local_review.v1"
            ),
        ),
        build_validation_validator_family_definition(
            validator_family_id=TASK_EFFECT_REPRODUCIBILITY_FAMILY_ID,
            layer_id=TASK_SANITY_LAYER_ID,
            display_name="Task Effect Reproducibility",
            description=(
                "First Milestone 13 task family: keep task claims tied to the "
                "Milestone 12 shared-effect ladder and declared null tests."
            ),
            validator_ids=[
                "shared_effect_reproducibility",
                "task_decoder_robustness",
            ],
            required_evidence_scope_ids=[
                EXPERIMENT_SHARED_ANALYSIS_SCOPE,
                EXPERIMENT_NULL_TEST_SCOPE,
            ],
            required_upstream_contracts=[
                "simulator_result_bundle.v1",
                "readout_analysis.v1",
                "experiment_analysis_bundle.v1",
            ],
            default_criteria_profile_reference=(
                "validation_criteria.task_effect_reproducibility.default_local_review.v1"
            ),
        ),
    ]


def _default_validation_validator_catalog() -> list[dict[str, Any]]:
    return [
        build_validation_validator_definition(
            validator_id="operator_bundle_gate_alignment",
            validator_family_id=NUMERICAL_STABILITY_FAMILY_ID,
            display_name="Operator Bundle Gate Alignment",
            description=(
                "Reuses the Milestone 6 operator QA gate so the validation ladder "
                "inherits the same numerical baseline instead of bypassing it."
            ),
            required_evidence_scope_ids=[OPERATOR_QA_REVIEW_SCOPE],
            required_upstream_contracts=["geometry_bundle.v1"],
            criteria_profile_reference=(
                "validation_criteria.numerical_stability.operator_bundle_gate_alignment.v1"
            ),
            supported_result_statuses=SUPPORTED_VALIDATION_RESULT_STATUSES,
        ),
        build_validation_validator_definition(
            validator_id="surface_wave_stability_envelope",
            validator_family_id=NUMERICAL_STABILITY_FAMILY_ID,
            display_name="Surface-Wave Stability Envelope",
            description=(
                "Checks local surface-wave stability and suspicious numerical "
                "behavior using the Milestone 10 inspection and simulator-result surfaces."
            ),
            required_evidence_scope_ids=[
                SURFACE_WAVE_INSPECTION_SCOPE,
                SIMULATOR_SHARED_READOUT_SCOPE,
            ],
            required_upstream_contracts=[
                "surface_wave_model.v1",
                "simulator_result_bundle.v1",
            ],
            criteria_profile_reference=(
                "validation_criteria.numerical_stability.surface_wave_stability_envelope.v1"
            ),
            supported_result_statuses=SUPPORTED_VALIDATION_RESULT_STATUSES,
        ),
        build_validation_validator_definition(
            validator_id="mixed_fidelity_surrogate_preservation",
            validator_family_id=MORPHOLOGY_DEPENDENCE_FAMILY_ID,
            display_name="Mixed-Fidelity Surrogate Preservation",
            description=(
                "Uses Milestone 11 surrogate-versus-reference inspection outputs to "
                "decide whether a lower-fidelity morphology class remains usable."
            ),
            required_evidence_scope_ids=[MIXED_FIDELITY_INSPECTION_SCOPE],
            required_upstream_contracts=[
                "hybrid_morphology.v1",
                "simulator_result_bundle.v1",
            ],
            criteria_profile_reference=(
                "validation_criteria.morphology_dependence.mixed_fidelity_surrogate_preservation.v1"
            ),
            supported_result_statuses=SUPPORTED_VALIDATION_RESULT_STATUSES,
        ),
        build_validation_validator_definition(
            validator_id="geometry_dependence_collapse",
            validator_family_id=MORPHOLOGY_DEPENDENCE_FAMILY_ID,
            display_name="Geometry Dependence Collapse",
            description=(
                "Checks whether morphology- or geometry-targeted perturbations shrink "
                "the claimed effect while preserving the locked readout boundary."
            ),
            required_evidence_scope_ids=[
                EXPERIMENT_SHARED_ANALYSIS_SCOPE,
                EXPERIMENT_WAVE_DIAGNOSTIC_SCOPE,
                EXPERIMENT_NULL_TEST_SCOPE,
            ],
            required_upstream_contracts=[
                "readout_analysis.v1",
                "experiment_analysis_bundle.v1",
            ],
            criteria_profile_reference=(
                "validation_criteria.morphology_dependence.geometry_dependence_collapse.v1"
            ),
            supported_result_statuses=SUPPORTED_VALIDATION_RESULT_STATUSES,
        ),
        build_validation_validator_definition(
            validator_id="coupling_semantics_continuity",
            validator_family_id=CIRCUIT_RESPONSE_FAMILY_ID,
            display_name="Coupling Semantics Continuity",
            description=(
                "Checks sign, delay, aggregation, and shared-readout continuity "
                "without inventing validator-local circuit semantics."
            ),
            required_evidence_scope_ids=[
                SIMULATOR_SHARED_READOUT_SCOPE,
                EXPERIMENT_SHARED_ANALYSIS_SCOPE,
            ],
            required_upstream_contracts=[
                "coupling_bundle.v1",
                "simulator_result_bundle.v1",
                "experiment_analysis_bundle.v1",
            ],
            criteria_profile_reference=(
                "validation_criteria.circuit_response.coupling_semantics_continuity.v1"
            ),
            supported_result_statuses=SUPPORTED_VALIDATION_RESULT_STATUSES,
        ),
        build_validation_validator_definition(
            validator_id="motion_pathway_asymmetry",
            validator_family_id=CIRCUIT_RESPONSE_FAMILY_ID,
            display_name="Motion Pathway Asymmetry",
            description=(
                "Checks pathway-level asymmetry under matched motion stimuli on the "
                "shared comparison surface."
            ),
            required_evidence_scope_ids=[
                SIMULATOR_SHARED_READOUT_SCOPE,
                EXPERIMENT_SHARED_ANALYSIS_SCOPE,
            ],
            required_upstream_contracts=[
                "simulator_result_bundle.v1",
                "readout_analysis.v1",
                "experiment_analysis_bundle.v1",
            ],
            criteria_profile_reference=(
                "validation_criteria.circuit_response.motion_pathway_asymmetry.v1"
            ),
            supported_result_statuses=SUPPORTED_VALIDATION_RESULT_STATUSES,
        ),
        build_validation_validator_definition(
            validator_id="shared_effect_reproducibility",
            validator_family_id=TASK_EFFECT_REPRODUCIBILITY_FAMILY_ID,
            display_name="Shared Effect Reproducibility",
            description=(
                "Checks that the Milestone 1 shared-effect ladder survives seed "
                "sweeps and stronger-baseline challenges."
            ),
            required_evidence_scope_ids=[
                EXPERIMENT_SHARED_ANALYSIS_SCOPE,
                EXPERIMENT_NULL_TEST_SCOPE,
            ],
            required_upstream_contracts=[
                "readout_analysis.v1",
                "experiment_analysis_bundle.v1",
            ],
            criteria_profile_reference=(
                "validation_criteria.task_effect_reproducibility.shared_effect_reproducibility.v1"
            ),
            supported_result_statuses=SUPPORTED_VALIDATION_RESULT_STATUSES,
        ),
        build_validation_validator_definition(
            validator_id="task_decoder_robustness",
            validator_family_id=TASK_EFFECT_REPRODUCIBILITY_FAMILY_ID,
            display_name="Task Decoder Robustness",
            description=(
                "Checks that task-layer decoder behavior remains bounded by the "
                "shared readout surface and responds coherently to declared perturbations."
            ),
            required_evidence_scope_ids=[
                EXPERIMENT_SHARED_ANALYSIS_SCOPE,
                EXPERIMENT_NULL_TEST_SCOPE,
            ],
            required_upstream_contracts=[
                "readout_analysis.v1",
                "experiment_analysis_bundle.v1",
            ],
            criteria_profile_reference=(
                "validation_criteria.task_effect_reproducibility.task_decoder_robustness.v1"
            ),
            supported_result_statuses=SUPPORTED_VALIDATION_RESULT_STATUSES,
        ),
    ]


def _extract_validation_contract_mapping(record: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(record, Mapping):
        raise ValueError("validation contract record must be a mapping.")
    if isinstance(record.get("validation_ladder_contract"), Mapping):
        return record["validation_ladder_contract"]
    return record


def _artifact_record(
    *,
    path: Path,
    format: str,
    artifact_scope: str,
    description: str,
) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "status": ASSET_STATUS_READY,
        "format": format,
        "artifact_scope": artifact_scope,
        "description": description,
    }


def _normalize_evidence_scope_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("evidence_scope_catalog must be a sequence.")
    normalized = [
        parse_validation_evidence_scope_definition(item) for item in payload
    ]
    return _sorted_unique_catalog(
        normalized,
        id_key="evidence_scope_id",
        field_name="evidence_scope_catalog",
    )


def _normalize_layer_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("layer_catalog must be a sequence.")
    normalized = [parse_validation_layer_definition(item) for item in payload]
    deduped = _sorted_unique_catalog(
        normalized,
        id_key="layer_id",
        field_name="layer_catalog",
    )
    return sorted(
        deduped,
        key=lambda item: (int(item["sequence_index"]), str(item["layer_id"])),
    )


def _normalize_validator_family_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("validator_family_catalog must be a sequence.")
    normalized = [
        parse_validation_validator_family_definition(item) for item in payload
    ]
    return _sorted_unique_catalog(
        normalized,
        id_key="validator_family_id",
        field_name="validator_family_catalog",
    )


def _normalize_validator_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("validator_catalog must be a sequence.")
    normalized = [parse_validation_validator_definition(item) for item in payload]
    return _sorted_unique_catalog(
        normalized,
        id_key="validator_id",
        field_name="validator_catalog",
    )


def _normalize_result_status_semantics(payload: Any) -> dict[str, Any]:
    normalized = _normalize_json_mapping(
        payload,
        field_name="result_status_semantics",
    )
    if set(normalized) != set(SUPPORTED_VALIDATION_RESULT_STATUSES):
        raise ValueError(
            "result_status_semantics must declare every canonical validation status."
        )
    return {
        status: _normalize_nonempty_string(
            normalized[status],
            field_name=f"result_status_semantics.{status}",
        )
        for status in SUPPORTED_VALIDATION_RESULT_STATUSES
    }


def _normalize_criteria_handoff(payload: Any) -> dict[str, Any]:
    normalized = _normalize_json_mapping(
        payload,
        field_name="criteria_handoff",
    )
    required_fields = (
        "machine_findings_rule",
        "machine_findings_stop_at",
        "machine_findings_may_not_assert",
        "review_owner",
        "review_status",
        "review_artifact_id",
        "required_reviewer_fields",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"criteria_handoff is missing required fields {missing_fields!r}."
        )
    review_owner = _normalize_nonempty_string(
        normalized["review_owner"],
        field_name="criteria_handoff.review_owner",
    ).lower()
    if review_owner not in SUPPORTED_REVIEW_OWNERS:
        raise ValueError(
            f"criteria_handoff.review_owner must be one of {list(SUPPORTED_REVIEW_OWNERS)!r}."
        )
    review_status = _normalize_result_status(
        normalized["review_status"],
        field_name="criteria_handoff.review_status",
    )
    if review_status != VALIDATION_STATUS_REVIEW:
        raise ValueError(
            f"criteria_handoff.review_status must be {VALIDATION_STATUS_REVIEW!r}."
        )
    review_artifact_id = _normalize_identifier(
        normalized["review_artifact_id"],
        field_name="criteria_handoff.review_artifact_id",
    )
    if review_artifact_id != REVIEW_HANDOFF_ARTIFACT_ID:
        raise ValueError(
            f"criteria_handoff.review_artifact_id must be {REVIEW_HANDOFF_ARTIFACT_ID!r}."
        )
    return {
        "machine_findings_rule": _normalize_nonempty_string(
            normalized["machine_findings_rule"],
            field_name="criteria_handoff.machine_findings_rule",
        ),
        "machine_findings_stop_at": _normalize_nonempty_string(
            normalized["machine_findings_stop_at"],
            field_name="criteria_handoff.machine_findings_stop_at",
        ),
        "machine_findings_may_not_assert": _normalize_nonempty_string_list(
            normalized["machine_findings_may_not_assert"],
            field_name="criteria_handoff.machine_findings_may_not_assert",
            allow_empty=False,
        ),
        "review_owner": review_owner,
        "review_status": review_status,
        "review_artifact_id": review_artifact_id,
        "required_reviewer_fields": _normalize_identifier_list(
            normalized["required_reviewer_fields"],
            field_name="criteria_handoff.required_reviewer_fields",
            allow_empty=False,
        ),
    }


def _normalize_artifact_catalog(payload: Any) -> dict[str, Any]:
    normalized = _normalize_json_mapping(
        payload,
        field_name="artifact_catalog",
    )
    expected = default_validation_artifact_catalog()
    if set(normalized) != set(expected):
        raise ValueError("artifact_catalog must declare the canonical validation artifact ids.")
    artifact_catalog: dict[str, Any] = {}
    for artifact_id, expected_record in expected.items():
        record = _normalize_json_mapping(
            normalized[artifact_id],
            field_name=f"artifact_catalog.{artifact_id}",
        )
        required_fields = ("artifact_scope", "format", "relative_path", "description")
        missing_fields = [field for field in required_fields if field not in record]
        if missing_fields:
            raise ValueError(
                f"artifact_catalog.{artifact_id} is missing fields {missing_fields!r}."
            )
        artifact_scope = _normalize_nonempty_string(
            record["artifact_scope"],
            field_name=f"artifact_catalog.{artifact_id}.artifact_scope",
        )
        if artifact_scope != expected_record["artifact_scope"]:
            raise ValueError(
                f"artifact_catalog.{artifact_id}.artifact_scope must be {expected_record['artifact_scope']!r}."
            )
        artifact_format = _normalize_nonempty_string(
            record["format"],
            field_name=f"artifact_catalog.{artifact_id}.format",
        )
        if artifact_format != expected_record["format"]:
            raise ValueError(
                f"artifact_catalog.{artifact_id}.format must be {expected_record['format']!r}."
            )
        relative_path = _normalize_nonempty_string(
            record["relative_path"],
            field_name=f"artifact_catalog.{artifact_id}.relative_path",
        )
        if relative_path != expected_record["relative_path"]:
            raise ValueError(
                f"artifact_catalog.{artifact_id}.relative_path must be {expected_record['relative_path']!r}."
            )
        artifact_catalog[artifact_id] = {
            "artifact_scope": artifact_scope,
            "format": artifact_format,
            "relative_path": relative_path,
            "description": _normalize_nonempty_string(
                record["description"],
                field_name=f"artifact_catalog.{artifact_id}.description",
            ),
        }
    return artifact_catalog


def _normalize_contract_reference(payload: Any) -> dict[str, Any]:
    normalized = _normalize_json_mapping(
        payload,
        field_name="validation_plan.contract_reference",
    )
    required_fields = ("contract_version", "design_note", "design_note_version")
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"validation_plan.contract_reference is missing fields {missing_fields!r}."
        )
    contract_version = _normalize_nonempty_string(
        normalized["contract_version"],
        field_name="validation_plan.contract_reference.contract_version",
    )
    if contract_version != VALIDATION_LADDER_CONTRACT_VERSION:
        raise ValueError(
            "validation_plan.contract_reference.contract_version must be "
            f"{VALIDATION_LADDER_CONTRACT_VERSION!r}."
        )
    design_note = _normalize_nonempty_string(
        normalized["design_note"],
        field_name="validation_plan.contract_reference.design_note",
    )
    if design_note != VALIDATION_LADDER_DESIGN_NOTE:
        raise ValueError(
            "validation_plan.contract_reference.design_note must be "
            f"{VALIDATION_LADDER_DESIGN_NOTE!r}."
        )
    design_note_version = _normalize_nonempty_string(
        normalized["design_note_version"],
        field_name="validation_plan.contract_reference.design_note_version",
    )
    if design_note_version != VALIDATION_LADDER_DESIGN_NOTE_VERSION:
        raise ValueError(
            "validation_plan.contract_reference.design_note_version must be "
            f"{VALIDATION_LADDER_DESIGN_NOTE_VERSION!r}."
        )
    return {
        "contract_version": contract_version,
        "design_note": design_note,
        "design_note_version": design_note_version,
    }


def _normalize_criteria_profile_assignments(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError(
            "validation_plan.criteria_profile_assignments must be a sequence."
        )
    normalized: list[dict[str, Any]] = []
    seen_validator_ids: set[str] = set()
    for index, item in enumerate(payload):
        record = _normalize_json_mapping(
            item,
            field_name=f"validation_plan.criteria_profile_assignments[{index}]",
        )
        required_fields = (
            "validator_id",
            "criteria_profile_reference",
        )
        missing_fields = [field for field in required_fields if field not in record]
        if missing_fields:
            raise ValueError(
                "validation_plan.criteria_profile_assignments item is missing fields "
                f"{missing_fields!r}."
            )
        validator_id = _normalize_identifier(
            record["validator_id"],
            field_name=(
                f"validation_plan.criteria_profile_assignments[{index}].validator_id"
            ),
        )
        if validator_id in seen_validator_ids:
            raise ValueError(
                "validation_plan.criteria_profile_assignments must not contain duplicate "
                f"validator_id {validator_id!r}."
            )
        seen_validator_ids.add(validator_id)
        normalized.append(
            {
                "validator_id": validator_id,
                "criteria_profile_reference": _normalize_nonempty_string(
                    record["criteria_profile_reference"],
                    field_name=(
                        "validation_plan.criteria_profile_assignments"
                        f"[{index}].criteria_profile_reference"
                    ),
                ),
            }
        )
    return sorted(normalized, key=lambda item: item["validator_id"])


def _normalize_perturbation_suite_references(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError(
            "validation_plan.perturbation_suite_references must be a sequence."
        )
    normalized: list[dict[str, Any]] = []
    seen_suite_ids: set[str] = set()
    for index, item in enumerate(payload):
        record = _normalize_json_mapping(
            item,
            field_name=f"validation_plan.perturbation_suite_references[{index}]",
        )
        required_fields = (
            "suite_id",
            "suite_kind",
            "target_layer_ids",
            "target_validator_ids",
            "variant_ids",
        )
        missing_fields = [field for field in required_fields if field not in record]
        if missing_fields:
            raise ValueError(
                "validation_plan.perturbation_suite_references item is missing fields "
                f"{missing_fields!r}."
            )
        suite_id = _normalize_identifier(
            record["suite_id"],
            field_name=(
                f"validation_plan.perturbation_suite_references[{index}].suite_id"
            ),
        )
        if suite_id in seen_suite_ids:
            raise ValueError(
                "validation_plan.perturbation_suite_references must not contain duplicate "
                f"suite_id {suite_id!r}."
            )
        seen_suite_ids.add(suite_id)
        normalized.append(
            {
                "suite_id": suite_id,
                "suite_kind": _normalize_nonempty_string(
                    record["suite_kind"],
                    field_name=(
                        "validation_plan.perturbation_suite_references"
                        f"[{index}].suite_kind"
                    ),
                ),
                "target_layer_ids": _normalize_layer_id_list(
                    record["target_layer_ids"],
                    field_name=(
                        "validation_plan.perturbation_suite_references"
                        f"[{index}].target_layer_ids"
                    ),
                    allow_empty=True,
                ),
                "target_validator_ids": _normalize_identifier_list(
                    record["target_validator_ids"],
                    field_name=(
                        "validation_plan.perturbation_suite_references"
                        f"[{index}].target_validator_ids"
                    ),
                    allow_empty=True,
                ),
                "variant_ids": _normalize_identifier_list(
                    record["variant_ids"],
                    field_name=(
                        "validation_plan.perturbation_suite_references"
                        f"[{index}].variant_ids"
                    ),
                    allow_empty=True,
                ),
            }
        )
    return sorted(normalized, key=lambda item: item["suite_id"])


def _resolve_validation_bundle_identity(
    *,
    validation_plan_reference: Mapping[str, Any] | None,
    bundle_reference: Mapping[str, Any] | None,
) -> tuple[str, str]:
    if validation_plan_reference is not None:
        normalized_plan = parse_validation_plan_reference(validation_plan_reference)
        return (
            normalized_plan["experiment_id"],
            build_validation_spec_hash(normalized_plan),
        )
    if bundle_reference is not None:
        normalized_reference = _normalize_validation_bundle_reference(bundle_reference)
        return (
            normalized_reference["experiment_id"],
            normalized_reference["validation_spec_hash"],
        )
    raise ValueError(
        "validation_bundle lookup requires validation_plan_reference or bundle_reference."
    )


def _normalize_validation_bundle_reference(
    payload: Any,
) -> dict[str, str]:
    if not isinstance(payload, Mapping):
        raise ValueError("bundle_reference must be a mapping.")
    contract_version = _normalize_nonempty_string(
        payload.get("contract_version"),
        field_name="bundle_reference.contract_version",
    )
    if contract_version != VALIDATION_LADDER_CONTRACT_VERSION:
        raise ValueError(
            "bundle_reference.contract_version must be "
            f"{VALIDATION_LADDER_CONTRACT_VERSION!r}."
        )
    experiment_id = _normalize_identifier(
        payload.get("experiment_id"),
        field_name="bundle_reference.experiment_id",
    )
    validation_spec_hash = _normalize_parameter_hash(
        payload.get("validation_spec_hash")
    )
    bundle_id = _normalize_nonempty_string(
        payload.get("bundle_id"),
        field_name="bundle_reference.bundle_id",
    )
    expected_bundle_id = (
        f"{VALIDATION_LADDER_CONTRACT_VERSION}:"
        f"{experiment_id}:{validation_spec_hash}"
    )
    if bundle_id != expected_bundle_id:
        raise ValueError(
            "bundle_reference.bundle_id must match the canonical validation bundle identity."
        )
    return {
        "contract_version": contract_version,
        "bundle_id": bundle_id,
        "experiment_id": experiment_id,
        "validation_spec_hash": validation_spec_hash,
    }


def _normalize_optional_bundle_id(
    payload: Mapping[str, Any] | None,
    *,
    field_name: str,
) -> str | None:
    if payload is None:
        return None
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    bundle_id = payload.get("bundle_id")
    if bundle_id in {None, ""}:
        return None
    return _normalize_nonempty_string(bundle_id, field_name=f"{field_name}.bundle_id")


def _normalize_bundle_id_filters(
    payload: Sequence[str] | None,
    *,
    field_name: str,
) -> set[str]:
    if payload is None:
        return set()
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence.")
    return {
        _normalize_nonempty_string(item, field_name=field_name)
        for item in payload
    }


def _normalize_identifier_sequence(
    payload: Sequence[str] | None,
    *,
    field_name: str,
) -> set[str]:
    if payload is None:
        return set()
    return set(
        _normalize_identifier_list(
            payload,
            field_name=field_name,
            allow_empty=True,
        )
    )


def _normalize_output_root_reference(payload: Any) -> dict[str, Any]:
    normalized = _normalize_json_mapping(
        payload,
        field_name="output_root_reference",
    )
    if "processed_simulator_results_dir" not in normalized:
        raise ValueError(
            "output_root_reference must declare processed_simulator_results_dir."
        )
    processed_dir = Path(
        _normalize_nonempty_string(
            normalized["processed_simulator_results_dir"],
            field_name="output_root_reference.processed_simulator_results_dir",
        )
    ).resolve()
    return {
        "processed_simulator_results_dir": str(processed_dir),
    }


def _normalize_bundle_layout(
    payload: Any,
    *,
    expected_bundle_paths: ValidationBundlePaths,
) -> dict[str, Any]:
    normalized = _normalize_json_mapping(
        payload,
        field_name="bundle_layout",
    )
    required_fields = ("bundle_directory", "report_directory")
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"bundle_layout is missing fields {missing_fields!r}.")
    bundle_directory = Path(
        _normalize_nonempty_string(
            normalized["bundle_directory"],
            field_name="bundle_layout.bundle_directory",
        )
    ).resolve()
    report_directory = Path(
        _normalize_nonempty_string(
            normalized["report_directory"],
            field_name="bundle_layout.report_directory",
        )
    ).resolve()
    if bundle_directory != expected_bundle_paths.bundle_directory:
        raise ValueError(
            "bundle_layout.bundle_directory must match the canonical validation bundle path."
        )
    if report_directory != expected_bundle_paths.report_directory:
        raise ValueError(
            "bundle_layout.report_directory must match the canonical validation report path."
        )
    return {
        "bundle_directory": str(bundle_directory),
        "report_directory": str(report_directory),
    }


def _normalize_bundle_artifacts(
    payload: Any,
    *,
    expected_paths: Mapping[str, Path],
) -> dict[str, Any]:
    normalized = _normalize_json_mapping(payload, field_name="artifacts")
    expected_catalog = default_validation_artifact_catalog()
    if set(normalized) != set(expected_catalog):
        raise ValueError("artifacts must declare the canonical validation artifact ids.")
    artifacts: dict[str, Any] = {}
    for artifact_id, expected_record in expected_catalog.items():
        record = _normalize_json_mapping(
            normalized[artifact_id],
            field_name=f"artifacts.{artifact_id}",
        )
        required_fields = ("path", "status", "format", "artifact_scope", "description")
        missing_fields = [field for field in required_fields if field not in record]
        if missing_fields:
            raise ValueError(
                f"artifacts.{artifact_id} is missing fields {missing_fields!r}."
            )
        path = Path(
            _normalize_nonempty_string(
                record["path"],
                field_name=f"artifacts.{artifact_id}.path",
            )
        ).resolve()
        if path != expected_paths[artifact_id].resolve():
            raise ValueError(
                f"artifacts.{artifact_id}.path must match the canonical validation output path."
            )
        status = _normalize_nonempty_string(
            record["status"],
            field_name=f"artifacts.{artifact_id}.status",
        )
        if status != ASSET_STATUS_READY:
            raise ValueError(
                f"artifacts.{artifact_id}.status must be {ASSET_STATUS_READY!r}."
            )
        artifact_format = _normalize_nonempty_string(
            record["format"],
            field_name=f"artifacts.{artifact_id}.format",
        )
        if artifact_format != expected_record["format"]:
            raise ValueError(
                f"artifacts.{artifact_id}.format must be {expected_record['format']!r}."
            )
        artifact_scope = _normalize_nonempty_string(
            record["artifact_scope"],
            field_name=f"artifacts.{artifact_id}.artifact_scope",
        )
        if artifact_scope != expected_record["artifact_scope"]:
            raise ValueError(
                f"artifacts.{artifact_id}.artifact_scope must be {expected_record['artifact_scope']!r}."
            )
        artifacts[artifact_id] = {
            "path": str(path),
            "status": status,
            "format": artifact_format,
            "artifact_scope": artifact_scope,
            "description": _normalize_nonempty_string(
                record["description"],
                field_name=f"artifacts.{artifact_id}.description",
            ),
        }
    return artifacts


def _validate_validation_plan_against_contract(
    *,
    validation_plan_reference: Mapping[str, Any],
    contract_metadata: Mapping[str, Any],
) -> None:
    layer_ids = {
        item["layer_id"] for item in contract_metadata["layer_catalog"]
    }
    family_ids = {
        item["validator_family_id"]
        for item in contract_metadata["validator_family_catalog"]
    }
    validator_ids = {
        item["validator_id"] for item in contract_metadata["validator_catalog"]
    }
    criteria_profile_references = {
        item["criteria_profile_reference"]
        for item in contract_metadata["validator_catalog"]
    } | {
        item["default_criteria_profile_reference"]
        for item in contract_metadata["validator_family_catalog"]
    }
    unknown_layer_ids = sorted(
        set(validation_plan_reference["active_layer_ids"]) - layer_ids
    )
    if unknown_layer_ids:
        raise ValueError(
            f"validation_plan_reference references unknown layer ids {unknown_layer_ids!r}."
        )
    unknown_family_ids = sorted(
        set(validation_plan_reference["active_validator_family_ids"]) - family_ids
    )
    if unknown_family_ids:
        raise ValueError(
            "validation_plan_reference references unknown validator family ids "
            f"{unknown_family_ids!r}."
        )
    unknown_validator_ids = sorted(
        set(validation_plan_reference["active_validator_ids"]) - validator_ids
    )
    if unknown_validator_ids:
        raise ValueError(
            f"validation_plan_reference references unknown validator ids {unknown_validator_ids!r}."
        )
    unknown_profile_references = sorted(
        set(validation_plan_reference["criteria_profile_references"])
        - criteria_profile_references
    )
    if unknown_profile_references:
        raise ValueError(
            "validation_plan_reference references unknown criteria_profile_references "
            f"{unknown_profile_references!r}."
        )
    assignments = validation_plan_reference.get("criteria_profile_assignments", [])
    if isinstance(assignments, Sequence) and not isinstance(
        assignments,
        (str, bytes, bytearray),
    ):
        unknown_assignment_validator_ids = sorted(
            {
                str(item["validator_id"])
                for item in assignments
                if str(item["validator_id"])
                not in set(validation_plan_reference["active_validator_ids"])
            }
        )
        if unknown_assignment_validator_ids:
            raise ValueError(
                "validation_plan_reference.criteria_profile_assignments references "
                "validator ids that are not active in the plan: "
                f"{unknown_assignment_validator_ids!r}."
            )
        unknown_assignment_profiles = sorted(
            {
                str(item["criteria_profile_reference"])
                for item in assignments
                if str(item["criteria_profile_reference"]) not in criteria_profile_references
            }
        )
        if unknown_assignment_profiles:
            raise ValueError(
                "validation_plan_reference.criteria_profile_assignments references "
                "unknown criteria_profile_references "
                f"{unknown_assignment_profiles!r}."
            )


def _sorted_unique_catalog(
    catalog: Sequence[dict[str, Any]],
    *,
    id_key: str,
    field_name: str,
) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for item in catalog:
        item_id = str(item[id_key])
        if item_id in deduped:
            raise ValueError(f"{field_name} contains duplicate id {item_id!r}.")
        deduped[item_id] = item
    return [copy.deepcopy(deduped[key]) for key in sorted(deduped)]


def _normalize_layer_id(value: Any) -> str:
    layer_id = _normalize_identifier(value, field_name="layer_id")
    if layer_id not in SUPPORTED_VALIDATION_LAYER_IDS:
        raise ValueError(
            f"layer_id must be one of {list(SUPPORTED_VALIDATION_LAYER_IDS)!r}, got {layer_id!r}."
        )
    return layer_id


def _normalize_layer_id_list(
    payload: Any,
    *,
    field_name: str,
    allow_empty: bool,
) -> list[str]:
    values = _normalize_identifier_list(
        payload,
        field_name=field_name,
        allow_empty=allow_empty,
    )
    return [_normalize_layer_id(item) for item in values]


def _normalize_evidence_scope_id(value: Any) -> str:
    scope_id = _normalize_identifier(value, field_name="evidence_scope_id")
    if scope_id not in SUPPORTED_EVIDENCE_SCOPE_IDS:
        raise ValueError(
            f"evidence_scope_id must be one of {list(SUPPORTED_EVIDENCE_SCOPE_IDS)!r}, got {scope_id!r}."
        )
    return scope_id


def _normalize_evidence_scope_id_list(
    payload: Any,
    *,
    field_name: str,
    allow_empty: bool,
) -> list[str]:
    values = _normalize_identifier_list(
        payload,
        field_name=field_name,
        allow_empty=allow_empty,
    )
    return [_normalize_evidence_scope_id(item) for item in values]


def _normalize_result_status(value: Any, *, field_name: str) -> str:
    normalized = _normalize_nonempty_string(value, field_name=field_name)
    if normalized not in SUPPORTED_VALIDATION_RESULT_STATUSES:
        raise ValueError(
            f"{field_name} must be one of {list(SUPPORTED_VALIDATION_RESULT_STATUSES)!r}."
        )
    return normalized


def _normalize_result_status_list(
    payload: Any,
    *,
    field_name: str,
    allow_empty: bool,
) -> list[str]:
    values = _normalize_nonempty_string_list(
        payload,
        field_name=field_name,
        allow_empty=allow_empty,
    )
    normalized = [
        _normalize_result_status(item, field_name=field_name) for item in values
    ]
    unique = sorted(set(normalized), key=lambda item: SUPPORTED_VALIDATION_RESULT_STATUSES.index(item))
    if not allow_empty and not unique:
        raise ValueError(f"{field_name} must not be empty.")
    return unique


def _normalize_identifier_list(
    payload: Any,
    *,
    field_name: str,
    allow_empty: bool,
) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence.")
    normalized = sorted(
        {
            _normalize_identifier(item, field_name=field_name)
            for item in payload
        }
    )
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


def _normalize_nonempty_string_list(
    payload: Any,
    *,
    field_name: str,
    allow_empty: bool,
) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence.")
    normalized = sorted(
        {
            _normalize_nonempty_string(item, field_name=field_name)
            for item in payload
        }
    )
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


def _normalize_positive_int(value: Any, *, field_name: str) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc
    if normalized <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized
