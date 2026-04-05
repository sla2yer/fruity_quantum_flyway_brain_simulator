from __future__ import annotations

import copy
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .experiment_analysis_contract import (
    ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
    EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID,
    discover_experiment_analysis_bundle_paths,
    load_experiment_analysis_bundle_metadata,
    parse_experiment_analysis_bundle_metadata,
)
from .experiment_comparison_analysis import (
    EXPERIMENT_COMPARISON_SUMMARY_VERSION,
    execute_experiment_comparison_workflow,
)
from .io_utils import ensure_dir, write_json
from .shared_readout_analysis import SUPPORTED_SHARED_READOUT_ANALYSIS_METRIC_IDS
from .simulation_planning import resolve_manifest_simulation_plan
from .stimulus_contract import _normalize_identifier, _normalize_nonempty_string
from .task_decoder_analysis import SUPPORTED_TASK_DECODER_ANALYSIS_METRIC_IDS
from .validation_contract import (
    SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID,
    TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
    TASK_EFFECT_REPRODUCIBILITY_FAMILY_ID,
    TASK_SANITY_LAYER_ID,
    VALIDATION_STATUS_BLOCKED,
    VALIDATION_STATUS_BLOCKING,
    VALIDATION_STATUS_PASS,
    VALIDATION_STATUS_REVIEW,
    build_validation_bundle_metadata,
    build_validation_contract_reference,
    build_validation_plan_reference,
    write_validation_bundle_metadata,
)
from .validation_planning import (
    GEOMETRY_VARIANTS_SUITE_ID,
    NOISE_ROBUSTNESS_SUITE_ID,
    SIGN_DELAY_PERTURBATIONS_SUITE_ID,
    resolve_validation_plan,
)


TASK_VALIDATION_PLAN_VERSION = "task_validation_plan.v1"
TASK_VALIDATION_REPORT_VERSION = "task_validation_suite.v1"

_EPSILON = 1.0e-12
_ANGLE_TOLERANCE_DEG = 1.0e-6

DEFAULT_SPEED_CV_PASS = 0.10
DEFAULT_SPEED_CV_REVIEW = 0.35
DEFAULT_HEADING_STABILITY_PASS_DEG = 5.0
DEFAULT_HEADING_STABILITY_REVIEW_DEG = 20.0
DEFAULT_HEADING_DELTA_PASS_DEG = 10.0
DEFAULT_HEADING_DELTA_REVIEW_DEG = 30.0
DEFAULT_EFFECT_RATIO_PASS = 0.50
DEFAULT_EFFECT_RATIO_REVIEW = 0.25

_STATUS_RANK = {
    VALIDATION_STATUS_PASS: 0,
    VALIDATION_STATUS_REVIEW: 1,
    VALIDATION_STATUS_BLOCKED: 2,
    VALIDATION_STATUS_BLOCKING: 3,
}

_TASK_VALIDATOR_IDS = (
    SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID,
    TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
)
_DEFAULT_TASK_CRITERIA_BY_VALIDATOR = {
    SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID: (
        "validation_criteria.task_effect_reproducibility.shared_effect_reproducibility.v1"
    ),
    TASK_DECODER_ROBUSTNESS_VALIDATOR_ID: (
        "validation_criteria.task_effect_reproducibility.task_decoder_robustness.v1"
    ),
}
_HEADING_METRIC_IDS = frozenset(
    {
        "motion_vector_heading_deg",
        "optic_flow_heading_deg",
    }
)
_SPEED_METRIC_IDS = frozenset(
    {
        "motion_vector_speed_deg_per_s",
        "optic_flow_speed_deg_per_s",
    }
)
_RELEVANT_SHARED_NULL_TEST_IDS = (
    "geometry_shuffle_collapse",
    "seed_stability",
    "stronger_baseline_survival",
)
_EXTERNAL_TASK_PERTURBATION_SUITE_IDS = frozenset(
    {
        NOISE_ROBUSTNESS_SUITE_ID,
        SIGN_DELAY_PERTURBATIONS_SUITE_ID,
    }
)
_TASK_SUITE_KIND_BY_ID = {
    GEOMETRY_VARIANTS_SUITE_ID: "geometry_variant",
    NOISE_ROBUSTNESS_SUITE_ID: "noise_robustness",
    SIGN_DELAY_PERTURBATIONS_SUITE_ID: "sign_delay_perturbation",
}


@dataclass(frozen=True)
class _LoadedAnalysisInput:
    label: str
    experiment_id: str
    summary: dict[str, Any]
    bundle_metadata: dict[str, Any] | None = None
    summary_path: str | None = None
    ui_payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class _PerturbationAnalysisInput:
    suite_id: str
    variant_id: str
    analysis: _LoadedAnalysisInput


def run_task_validation_suite(
    *,
    analysis_summary: Mapping[str, Any] | None = None,
    analysis_bundle_metadata: Mapping[str, Any] | None = None,
    analysis_bundle_metadata_path: str | Path | None = None,
    perturbation_analysis_bundle_specs: Sequence[Mapping[str, Any]] = (),
    validation_plan_reference: Mapping[str, Any] | None = None,
    bundle_metadata: Mapping[str, Any] | None = None,
    processed_simulator_results_dir: str | Path | None = None,
    experiment_id: str = "fixture_task_validation",
) -> dict[str, Any]:
    base_input = _load_analysis_input(
        label="base_analysis",
        analysis_summary=analysis_summary,
        analysis_bundle_metadata=analysis_bundle_metadata,
        analysis_bundle_metadata_path=analysis_bundle_metadata_path,
    )
    perturbation_inputs = _normalize_perturbation_analysis_inputs(
        perturbation_analysis_bundle_specs
    )
    resolved_plan_reference = _resolve_plan_reference(
        validation_plan_reference=validation_plan_reference,
        base_input=base_input,
        perturbation_inputs=perturbation_inputs,
        experiment_id=experiment_id,
    )
    resolved_bundle_metadata = _resolve_bundle_metadata(
        validation_plan_reference=resolved_plan_reference,
        bundle_metadata=bundle_metadata,
        processed_simulator_results_dir=processed_simulator_results_dir,
        experiment_id=base_input.experiment_id,
        base_input=base_input,
        perturbation_inputs=perturbation_inputs,
    )

    bundle_directory = Path(
        resolved_bundle_metadata["bundle_layout"]["bundle_directory"]
    ).resolve()
    report_directory = Path(
        resolved_bundle_metadata["bundle_layout"]["report_directory"]
    ).resolve()
    ensure_dir(bundle_directory)
    ensure_dir(report_directory)
    write_validation_bundle_metadata(resolved_bundle_metadata)

    active_validator_ids = [
        validator_id
        for validator_id in resolved_plan_reference["active_validator_ids"]
        if validator_id in _TASK_VALIDATOR_IDS
    ]
    if not active_validator_ids:
        raise ValueError(
            "Task validation requires at least one active task_sanity validator."
        )
    perturbation_expectations = _resolve_perturbation_expectations(
        validation_plan_reference=resolved_plan_reference,
        active_validator_ids=active_validator_ids,
        base_input=base_input,
        perturbation_inputs=perturbation_inputs,
    )
    analysis_inventory = _build_analysis_inventory(base_input)

    findings: list[dict[str, Any]] = []
    case_summaries: list[dict[str, Any]] = []

    if SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID in set(active_validator_ids):
        shared_findings = _evaluate_shared_effect_reproducibility(
            base_input=base_input,
            perturbation_inputs=perturbation_inputs,
            perturbation_expectations=perturbation_expectations,
        )
        findings.extend(shared_findings)
        case_summaries.append(
            _build_validator_case_summary(
                validator_id=SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID,
                validator_findings=shared_findings,
                analysis_inventory=analysis_inventory,
                perturbation_expectations=perturbation_expectations,
                base_input=base_input,
            )
        )

    if TASK_DECODER_ROBUSTNESS_VALIDATOR_ID in set(active_validator_ids):
        task_findings = _evaluate_task_decoder_robustness(
            base_input=base_input,
            perturbation_inputs=perturbation_inputs,
            perturbation_expectations=perturbation_expectations,
        )
        findings.extend(task_findings)
        case_summaries.append(
            _build_validator_case_summary(
                validator_id=TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
                validator_findings=task_findings,
                analysis_inventory=analysis_inventory,
                perturbation_expectations=perturbation_expectations,
                base_input=base_input,
            )
        )

    findings_by_validator = _group_findings_by_validator(findings)
    validator_summaries = _build_validator_summaries(findings_by_validator)
    layer_status = _worst_status(
        summary["status"] for summary in validator_summaries.values()
    )
    overall_status = layer_status
    status_counts = {
        VALIDATION_STATUS_PASS: sum(
            1 for item in findings if item["status"] == VALIDATION_STATUS_PASS
        ),
        VALIDATION_STATUS_REVIEW: sum(
            1 for item in findings if item["status"] == VALIDATION_STATUS_REVIEW
        ),
        VALIDATION_STATUS_BLOCKED: sum(
            1 for item in findings if item["status"] == VALIDATION_STATUS_BLOCKED
        ),
        VALIDATION_STATUS_BLOCKING: sum(
            1 for item in findings if item["status"] == VALIDATION_STATUS_BLOCKING
        ),
    }

    summary_payload = {
        "format_version": "json_validation_summary.v1",
        "report_version": TASK_VALIDATION_REPORT_VERSION,
        "bundle_id": str(resolved_bundle_metadata["bundle_id"]),
        "experiment_id": str(resolved_bundle_metadata["experiment_id"]),
        "validation_spec_hash": str(resolved_bundle_metadata["validation_spec_hash"]),
        "overall_status": overall_status,
        "active_layer_ids": [TASK_SANITY_LAYER_ID],
        "active_validator_family_ids": [TASK_EFFECT_REPRODUCIBILITY_FAMILY_ID],
        "active_validator_ids": list(active_validator_ids),
        "status_counts": status_counts,
        "layers": [
            {
                "layer_id": TASK_SANITY_LAYER_ID,
                "status": layer_status,
                "validator_families": [
                    {
                        "validator_family_id": TASK_EFFECT_REPRODUCIBILITY_FAMILY_ID,
                        "status": layer_status,
                        "validators": [
                            copy.deepcopy(validator_summaries[validator_id])
                            for validator_id in sorted(validator_summaries)
                        ],
                    }
                ],
            }
        ],
        "analysis_inventory": analysis_inventory,
        "perturbation_coverage": list(perturbation_expectations),
        "case_summaries": case_summaries,
        "artifact_paths": {
            artifact_id: str(record["path"])
            for artifact_id, record in resolved_bundle_metadata["artifacts"].items()
        },
        "source_analysis": {
            "label": base_input.label,
            "experiment_id": base_input.experiment_id,
            "summary_path": base_input.summary_path,
            "analysis_bundle_id": (
                None
                if base_input.bundle_metadata is None
                else str(base_input.bundle_metadata["bundle_id"])
            ),
        },
    }
    findings_payload = {
        "format_version": "json_validation_findings.v1",
        "report_version": TASK_VALIDATION_REPORT_VERSION,
        "bundle_id": str(resolved_bundle_metadata["bundle_id"]),
        "validator_findings": findings_by_validator,
    }
    review_handoff_payload = {
        "format_version": "json_validation_review_handoff.v1",
        "report_version": TASK_VALIDATION_REPORT_VERSION,
        "bundle_id": str(resolved_bundle_metadata["bundle_id"]),
        "review_owner": "grant",
        "review_status": VALIDATION_STATUS_REVIEW,
        "overall_status": overall_status,
        "open_finding_ids": [
            finding["finding_id"]
            for finding in findings
            if finding["status"] != VALIDATION_STATUS_PASS
        ],
        "validator_statuses": {
            validator_id: summary["status"]
            for validator_id, summary in validator_summaries.items()
        },
        "scientific_plausibility_decision": None,
        "reviewer_rationale": None,
        "follow_on_action": None,
    }
    report_markdown = _render_report_markdown(
        summary_payload=summary_payload,
        findings_by_validator=findings_by_validator,
    )

    summary_path = Path(
        resolved_bundle_metadata["artifacts"]["validation_summary"]["path"]
    ).resolve()
    findings_path = Path(
        resolved_bundle_metadata["artifacts"]["validator_findings"]["path"]
    ).resolve()
    review_handoff_path = Path(
        resolved_bundle_metadata["artifacts"]["review_handoff"]["path"]
    ).resolve()
    report_path = Path(
        resolved_bundle_metadata["artifacts"]["offline_review_report"]["path"]
    ).resolve()
    write_json(summary_payload, summary_path)
    write_json(findings_payload, findings_path)
    write_json(review_handoff_payload, review_handoff_path)
    report_path.write_text(report_markdown, encoding="utf-8")

    return {
        "report_version": TASK_VALIDATION_REPORT_VERSION,
        "bundle_id": str(resolved_bundle_metadata["bundle_id"]),
        "metadata_path": str(
            Path(resolved_bundle_metadata["artifacts"]["metadata_json"]["path"]).resolve()
        ),
        "output_dir": str(bundle_directory),
        "summary_path": str(summary_path),
        "findings_path": str(findings_path),
        "review_handoff_path": str(review_handoff_path),
        "report_path": str(report_path),
        "overall_status": overall_status,
        "validator_statuses": {
            validator_id: summary["status"]
            for validator_id, summary in validator_summaries.items()
        },
        "finding_count": len(findings),
        "case_count": len(case_summaries),
        "case_summaries": case_summaries,
    }


def execute_task_validation_workflow(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    analysis_bundle_metadata_path: str | Path | None = None,
    perturbation_analysis_bundle_specs: Sequence[Mapping[str, Any]] = (),
    validation_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_analysis_bundle_metadata_path = (
        None
        if analysis_bundle_metadata_path is None
        else Path(analysis_bundle_metadata_path).resolve()
    )
    if resolved_analysis_bundle_metadata_path is None:
        comparison = execute_experiment_comparison_workflow(
            manifest_path=manifest_path,
            config_path=config_path,
            schema_path=schema_path,
            design_lock_path=design_lock_path,
        )
        resolved_analysis_bundle_metadata_path = Path(
            comparison["packaged_analysis_bundle"]["metadata_path"]
        ).resolve()

    task_plan = _resolve_task_validation_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        analysis_bundle_metadata_path=resolved_analysis_bundle_metadata_path,
        validation_plan=validation_plan,
    )
    result = run_task_validation_suite(
        analysis_bundle_metadata_path=resolved_analysis_bundle_metadata_path,
        perturbation_analysis_bundle_specs=perturbation_analysis_bundle_specs,
        validation_plan_reference=task_plan["validation_plan_reference"],
        bundle_metadata=task_plan["validation_bundle"]["metadata"],
    )
    return {
        **result,
        "task_validation_plan": task_plan,
    }


def _resolve_task_validation_plan(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    analysis_bundle_metadata_path: str | Path,
    validation_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_plan = (
        copy.deepcopy(dict(validation_plan))
        if isinstance(validation_plan, Mapping)
        else resolve_validation_plan(
            config_path=config_path,
            simulation_plan=resolve_manifest_simulation_plan(
                manifest_path=manifest_path,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            ),
            analysis_bundle_metadata_path=analysis_bundle_metadata_path,
        )
    )
    analysis_bundle_metadata = load_experiment_analysis_bundle_metadata(
        analysis_bundle_metadata_path
    )
    criteria_assignments = [
        copy.deepcopy(dict(item))
        for item in resolved_plan["criteria_profile_assignments"]
        if str(item["validator_id"]) in set(_TASK_VALIDATOR_IDS)
    ]
    active_validator_ids = [
        str(validator_id)
        for validator_id in resolved_plan["active_validator_ids"]
        if str(validator_id) in set(_TASK_VALIDATOR_IDS)
    ]
    if not active_validator_ids:
        raise ValueError(
            "Resolved validation configuration does not activate the task_sanity layer."
        )
    task_comparison_groups = [
        copy.deepcopy(dict(item)) for item in resolved_plan["comparison_groups"]
    ]
    task_suites = [
        copy.deepcopy(dict(item))
        for item in resolved_plan["perturbation_suites"]
        if bool(item.get("enabled"))
        and set(item["target_validator_ids"]) & set(active_validator_ids)
    ]
    source_plan_reference = copy.deepcopy(dict(resolved_plan["validation_plan_reference"]))
    task_plan_reference = build_validation_plan_reference(
        experiment_id=str(resolved_plan["manifest_reference"]["experiment_id"]),
        contract_reference=copy.deepcopy(
            dict(source_plan_reference["contract_reference"])
        ),
        active_layer_ids=[TASK_SANITY_LAYER_ID],
        active_validator_family_ids=[TASK_EFFECT_REPRODUCIBILITY_FAMILY_ID],
        active_validator_ids=active_validator_ids,
        criteria_profile_references=[
            str(item["criteria_profile_reference"]) for item in criteria_assignments
        ],
        evidence_bundle_references=copy.deepcopy(
            dict(source_plan_reference["evidence_bundle_references"])
        ),
        target_arm_ids=list(source_plan_reference["target_arm_ids"]),
        comparison_group_ids=[str(item["group_id"]) for item in task_comparison_groups],
        criteria_profile_assignments=[
            {
                "validator_id": str(item["validator_id"]),
                "criteria_profile_reference": str(
                    item["criteria_profile_reference"]
                ),
            }
            for item in criteria_assignments
        ],
        perturbation_suite_references=[
            {
                "suite_id": str(item["suite_id"]),
                "suite_kind": str(item["suite_kind"]),
                "target_layer_ids": [TASK_SANITY_LAYER_ID],
                "target_validator_ids": [
                    validator_id
                    for validator_id in item["target_validator_ids"]
                    if validator_id in set(active_validator_ids)
                ],
                "variant_ids": [
                    str(variant["variant_id"]) for variant in item["variants"]
                ],
            }
            for item in task_suites
        ],
        plan_version=TASK_VALIDATION_PLAN_VERSION,
    )
    bundle_metadata = build_validation_bundle_metadata(
        validation_plan_reference=task_plan_reference,
        processed_simulator_results_dir=analysis_bundle_metadata["bundle_set_reference"][
            "processed_simulator_results_dir"
        ],
    )
    bundle_directory = Path(bundle_metadata["bundle_layout"]["bundle_directory"]).resolve()
    return {
        "plan_version": TASK_VALIDATION_PLAN_VERSION,
        "manifest_reference": copy.deepcopy(dict(resolved_plan["manifest_reference"])),
        "active_layer_ids": [TASK_SANITY_LAYER_ID],
        "active_validator_family_ids": [TASK_EFFECT_REPRODUCIBILITY_FAMILY_ID],
        "active_validator_ids": active_validator_ids,
        "criteria_profile_assignments": criteria_assignments,
        "comparison_groups": task_comparison_groups,
        "perturbation_suites": task_suites,
        "target_artifact_references": {
            "experiment_analysis_bundle": copy.deepcopy(
                dict(resolved_plan["target_artifact_references"]["experiment_analysis_bundle"])
            ),
        },
        "source_validation_plan_reference": source_plan_reference,
        "validation_plan_reference": task_plan_reference,
        "validation_bundle": {
            "bundle_id": str(bundle_metadata["bundle_id"]),
            "validation_spec_hash": str(bundle_metadata["validation_spec_hash"]),
            "metadata": copy.deepcopy(bundle_metadata),
        },
        "output_locations": {
            "bundle_directory": str(bundle_directory),
            "report_directory": str(
                Path(bundle_metadata["bundle_layout"]["report_directory"]).resolve()
            ),
            "artifacts": copy.deepcopy(dict(bundle_metadata["artifacts"])),
        },
    }


def _load_analysis_input(
    *,
    label: str,
    analysis_summary: Mapping[str, Any] | None = None,
    analysis_bundle_metadata: Mapping[str, Any] | None = None,
    analysis_bundle_metadata_path: str | Path | None = None,
) -> _LoadedAnalysisInput:
    provided_count = sum(
        value is not None
        for value in (
            analysis_summary,
            analysis_bundle_metadata,
            analysis_bundle_metadata_path,
        )
    )
    if provided_count != 1:
        raise ValueError(
            "Exactly one of analysis_summary, analysis_bundle_metadata, or "
            "analysis_bundle_metadata_path must be provided."
        )
    if analysis_summary is not None:
        summary = _normalize_summary_payload(analysis_summary)
        experiment_id = _normalize_identifier(
            summary["manifest_reference"]["experiment_id"],
            field_name="summary.manifest_reference.experiment_id",
        )
        return _LoadedAnalysisInput(
            label=label,
            experiment_id=experiment_id,
            summary=summary,
        )
    metadata = (
        load_experiment_analysis_bundle_metadata(analysis_bundle_metadata_path)
        if analysis_bundle_metadata is None
        else parse_experiment_analysis_bundle_metadata(analysis_bundle_metadata)
    )
    paths = discover_experiment_analysis_bundle_paths(metadata)
    summary_path = paths[EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID]
    if not summary_path.exists():
        raise ValueError(
            f"Experiment-analysis bundle {metadata['bundle_id']!r} is missing "
            f"{EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID!r} at {summary_path}."
        )
    summary = _load_json_mapping(summary_path)
    ui_payload = None
    ui_path = paths.get(ANALYSIS_UI_PAYLOAD_ARTIFACT_ID)
    if ui_path is not None and ui_path.exists():
        ui_payload = _load_json_mapping(ui_path)
    return _LoadedAnalysisInput(
        label=label,
        experiment_id=str(metadata["experiment_id"]),
        summary=_normalize_summary_payload(summary),
        bundle_metadata=copy.deepcopy(dict(metadata)),
        summary_path=str(summary_path.resolve()),
        ui_payload=ui_payload,
    )


def _normalize_perturbation_analysis_inputs(
    payload: Sequence[Mapping[str, Any]],
) -> list[_PerturbationAnalysisInput]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(
            "perturbation_analysis_bundle_specs must be a sequence of mappings."
        )
    normalized: list[_PerturbationAnalysisInput] = []
    seen_keys: set[tuple[str, str]] = set()
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError(
                "perturbation_analysis_bundle_specs items must be mappings."
            )
        suite_id = _normalize_identifier(
            item.get("suite_id"),
            field_name=(
                f"perturbation_analysis_bundle_specs[{index}].suite_id"
            ),
        )
        variant_id = _normalize_identifier(
            item.get("variant_id"),
            field_name=(
                f"perturbation_analysis_bundle_specs[{index}].variant_id"
            ),
        )
        key = (suite_id, variant_id)
        if key in seen_keys:
            raise ValueError(
                "perturbation_analysis_bundle_specs must not contain duplicate "
                f"suite_id/variant_id pairs, got {key!r}."
            )
        seen_keys.add(key)
        analysis = _load_analysis_input(
            label=f"{suite_id}:{variant_id}",
            analysis_summary=item.get("analysis_summary"),
            analysis_bundle_metadata=item.get("analysis_bundle_metadata"),
            analysis_bundle_metadata_path=item.get("analysis_bundle_metadata_path"),
        )
        normalized.append(
            _PerturbationAnalysisInput(
                suite_id=suite_id,
                variant_id=variant_id,
                analysis=analysis,
            )
        )
    return sorted(normalized, key=lambda item: (item.suite_id, item.variant_id))


def _normalize_summary_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Experiment-analysis summary payload must be a mapping.")
    summary_version = _normalize_nonempty_string(
        payload.get("summary_version"),
        field_name="summary.summary_version",
    )
    if summary_version != EXPERIMENT_COMPARISON_SUMMARY_VERSION:
        raise ValueError(
            f"summary.summary_version must be {EXPERIMENT_COMPARISON_SUMMARY_VERSION!r}."
        )
    required_fields = (
        "manifest_reference",
        "bundle_set",
        "analysis_results",
        "comparison_group_catalog",
        "group_metric_seed_rows",
        "group_metric_rollups",
        "null_test_results",
        "task_scores",
        "wave_metric_rollups",
    )
    missing_fields = [field for field in required_fields if field not in payload]
    if missing_fields:
        raise ValueError(
            "Experiment-analysis summary is missing required fields "
            f"{missing_fields!r}."
        )
    normalized = copy.deepcopy(dict(payload))
    if not isinstance(normalized["analysis_results"], Mapping):
        raise ValueError("summary.analysis_results must be a mapping.")
    return normalized


def _resolve_plan_reference(
    *,
    validation_plan_reference: Mapping[str, Any] | None,
    base_input: _LoadedAnalysisInput,
    perturbation_inputs: Sequence[_PerturbationAnalysisInput],
    experiment_id: str,
) -> dict[str, Any]:
    if validation_plan_reference is not None:
        return copy.deepcopy(dict(validation_plan_reference))
    return _default_plan_reference(
        base_input=base_input,
        perturbation_inputs=perturbation_inputs,
        experiment_id=experiment_id,
    )


def _resolve_bundle_metadata(
    *,
    validation_plan_reference: Mapping[str, Any],
    bundle_metadata: Mapping[str, Any] | None,
    processed_simulator_results_dir: str | Path | None,
    experiment_id: str,
    base_input: _LoadedAnalysisInput,
    perturbation_inputs: Sequence[_PerturbationAnalysisInput],
) -> dict[str, Any]:
    if bundle_metadata is not None:
        return copy.deepcopy(dict(bundle_metadata))
    resolved_root = (
        processed_simulator_results_dir
        if processed_simulator_results_dir is not None
        else _default_processed_results_dir(
            base_input=base_input,
            perturbation_inputs=perturbation_inputs,
        )
    )
    del experiment_id
    return build_validation_bundle_metadata(
        validation_plan_reference=validation_plan_reference,
        processed_simulator_results_dir=resolved_root,
    )


def _default_plan_reference(
    *,
    base_input: _LoadedAnalysisInput,
    perturbation_inputs: Sequence[_PerturbationAnalysisInput],
    experiment_id: str,
) -> dict[str, Any]:
    summary = base_input.summary
    active_validator_ids = _infer_active_validator_ids(summary)
    criteria_assignments = [
        {
            "validator_id": validator_id,
            "criteria_profile_reference": _DEFAULT_TASK_CRITERIA_BY_VALIDATOR[
                validator_id
            ],
        }
        for validator_id in active_validator_ids
    ]
    suite_refs: list[dict[str, Any]] = []
    grouped_inputs = _group_perturbation_inputs(perturbation_inputs)
    for suite_id, variants in sorted(grouped_inputs.items()):
        suite_refs.append(
            {
                "suite_id": suite_id,
                "suite_kind": _TASK_SUITE_KIND_BY_ID.get(
                    suite_id,
                    "task_perturbation_bundle",
                ),
                "target_layer_ids": [TASK_SANITY_LAYER_ID],
                "target_validator_ids": [
                    validator_id
                    for validator_id in active_validator_ids
                    if validator_id in _validators_targeted_by_suite(suite_id)
                ],
                "variant_ids": [item.variant_id for item in variants],
            }
        )
    return build_validation_plan_reference(
        experiment_id=base_input.experiment_id or experiment_id,
        contract_reference=build_validation_contract_reference(),
        active_layer_ids=[TASK_SANITY_LAYER_ID],
        active_validator_family_ids=[TASK_EFFECT_REPRODUCIBILITY_FAMILY_ID],
        active_validator_ids=active_validator_ids,
        criteria_profile_references=[
            item["criteria_profile_reference"] for item in criteria_assignments
        ],
        evidence_bundle_references={},
        target_arm_ids=sorted(summary["bundle_set"]["expected_arm_ids"]),
        comparison_group_ids=[
            str(item["group_id"]) for item in summary["comparison_group_catalog"]
        ],
        criteria_profile_assignments=criteria_assignments,
        perturbation_suite_references=suite_refs,
        plan_version=TASK_VALIDATION_PLAN_VERSION,
    )


def _infer_active_validator_ids(summary: Mapping[str, Any]) -> list[str]:
    active: list[str] = []
    shared_rollups = _shared_group_rollups(summary)
    if shared_rollups or _null_test_results_by_id(summary):
        active.append(SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID)
    task_rows = _task_metric_rows(summary)
    if task_rows:
        active.append(TASK_DECODER_ROBUSTNESS_VALIDATOR_ID)
    return active


def _default_processed_results_dir(
    *,
    base_input: _LoadedAnalysisInput,
    perturbation_inputs: Sequence[_PerturbationAnalysisInput],
) -> Path:
    candidates: list[Path] = []
    for item in (base_input, *[spec.analysis for spec in perturbation_inputs]):
        if item.bundle_metadata is None:
            continue
        candidates.append(
            Path(
                item.bundle_metadata["bundle_set_reference"][
                    "processed_simulator_results_dir"
                ]
            ).resolve()
        )
    if candidates:
        return candidates[0]
    return Path("data/processed/simulator_results").resolve()


def _build_analysis_inventory(base_input: _LoadedAnalysisInput) -> dict[str, Any]:
    summary = base_input.summary
    shared_rollups = _shared_group_rollups(summary)
    task_rollups = _task_group_rollups(summary)
    task_rows = _task_metric_rows(summary)
    decoder_summaries = _task_decoder_summaries(summary)
    wave_rollups = [
        copy.deepcopy(dict(item)) for item in summary.get("wave_metric_rollups", [])
    ]
    ui_has_shared = (
        isinstance(base_input.ui_payload, Mapping)
        and isinstance(base_input.ui_payload.get("shared_comparison"), Mapping)
    )
    ui_has_wave = (
        isinstance(base_input.ui_payload, Mapping)
        and isinstance(base_input.ui_payload.get("wave_only_diagnostics"), Mapping)
    )
    if wave_rollups:
        ui_scope_status = (
            VALIDATION_STATUS_PASS
            if ui_has_shared and ui_has_wave
            else VALIDATION_STATUS_BLOCKING
        )
    else:
        ui_scope_status = (
            VALIDATION_STATUS_PASS if ui_has_shared else VALIDATION_STATUS_REVIEW
        )
    return {
        "shared_comparison": {
            "group_metric_rollup_count": len(shared_rollups),
            "null_test_count": len(_null_test_results_by_id(summary)),
        },
        "task_decoder": {
            "metric_row_count": len(task_rows),
            "group_metric_rollup_count": len(task_rollups),
            "decoder_summary_count": len(decoder_summaries),
            "decoder_ids": sorted(
                {str(item["decoder_id"]) for item in decoder_summaries}
            ),
        },
        "wave_only_diagnostics": {
            "group_metric_rollup_count": len(wave_rollups),
        },
        "ui_scope_separation": {
            "status": ui_scope_status,
            "has_shared_comparison_section": bool(ui_has_shared),
            "has_wave_only_diagnostics_section": bool(ui_has_wave),
        },
    }


def _resolve_perturbation_expectations(
    *,
    validation_plan_reference: Mapping[str, Any],
    active_validator_ids: Sequence[str],
    base_input: _LoadedAnalysisInput,
    perturbation_inputs: Sequence[_PerturbationAnalysisInput],
) -> list[dict[str, Any]]:
    suite_refs = [
        copy.deepcopy(dict(item))
        for item in validation_plan_reference.get("perturbation_suite_references", [])
        if set(item.get("target_validator_ids", [])) & set(active_validator_ids)
    ]
    provided_by_suite = _group_perturbation_inputs(perturbation_inputs)
    expectations: list[dict[str, Any]] = []
    for suite in suite_refs:
        suite_id = str(suite["suite_id"])
        expected_variant_ids = sorted(str(item) for item in suite.get("variant_ids", []))
        provided_variant_ids = sorted(
            item.variant_id for item in provided_by_suite.get(suite_id, [])
        )
        if suite_id in _EXTERNAL_TASK_PERTURBATION_SUITE_IDS:
            missing_variant_ids = sorted(
                set(expected_variant_ids) - set(provided_variant_ids)
            )
            if missing_variant_ids:
                raise ValueError(
                    f"Task validation requires perturbation coverage for suite_id "
                    f"{suite_id!r}; missing variant_ids {missing_variant_ids!r}."
                )
            status = VALIDATION_STATUS_PASS
            coverage_mode = "external_analysis_bundles"
        else:
            _validate_builtin_suite_coverage(
                suite_id=suite_id,
                expected_variant_ids=expected_variant_ids,
                base_input=base_input,
            )
            missing_variant_ids = []
            status = VALIDATION_STATUS_PASS
            coverage_mode = "embedded_in_base_analysis"
        expectations.append(
            {
                "suite_id": suite_id,
                "suite_kind": str(suite["suite_kind"]),
                "target_validator_ids": list(suite.get("target_validator_ids", [])),
                "expected_variant_ids": expected_variant_ids,
                "provided_variant_ids": provided_variant_ids,
                "missing_variant_ids": missing_variant_ids,
                "coverage_mode": coverage_mode,
                "status": status,
            }
        )
    return expectations


def _validate_builtin_suite_coverage(
    *,
    suite_id: str,
    expected_variant_ids: Sequence[str],
    base_input: _LoadedAnalysisInput,
) -> None:
    if suite_id != GEOMETRY_VARIANTS_SUITE_ID:
        return
    geometry_groups = [
        item
        for item in base_input.summary["comparison_group_catalog"]
        if str(item["group_kind"]) == "geometry_ablation"
    ]
    if not geometry_groups:
        raise ValueError(
            "Task validation requires geometry_ablation comparison groups to satisfy "
            "the built-in geometry_variants perturbation suite."
        )
    del expected_variant_ids


def _evaluate_shared_effect_reproducibility(
    *,
    base_input: _LoadedAnalysisInput,
    perturbation_inputs: Sequence[_PerturbationAnalysisInput],
    perturbation_expectations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    summary = base_input.summary
    group_by_id = _comparison_groups_by_id(summary)
    rollups = _shared_group_rollups(summary)
    if not rollups:
        raise ValueError(
            "Task validation requires shared-readout experiment rollups for "
            "shared_effect_reproducibility."
        )
    findings: list[dict[str, Any]] = []

    inventory = _build_analysis_inventory(base_input)
    findings.append(
        _finding(
            validator_id=SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID,
            finding_id=(
                "shared_effect_reproducibility:ui_scope_separation"
            ),
            status=str(inventory["ui_scope_separation"]["status"]),
            case_id="shared_effect_reproducibility",
            summary={
                "has_shared_comparison_section": bool(
                    inventory["ui_scope_separation"][
                        "has_shared_comparison_section"
                    ]
                ),
                "has_wave_only_diagnostics_section": bool(
                    inventory["ui_scope_separation"][
                        "has_wave_only_diagnostics_section"
                    ]
                ),
            },
        )
    )

    for rollup in rollups:
        expected_seeds = _expected_seeds_for_group(
            summary=summary,
            group_id=str(rollup["group_id"]),
            group_by_id=group_by_id,
        )
        observed_seeds = [int(seed) for seed in rollup.get("seeds", [])]
        if observed_seeds != expected_seeds:
            raise ValueError(
                f"Shared-effect rollup {rollup['group_id']!r}/{rollup['metric_id']!r} "
                f"is missing required seed coverage; expected {expected_seeds!r}, "
                f"got {observed_seeds!r}."
            )
        status = (
            VALIDATION_STATUS_PASS
            if bool(rollup["sign_consistency"])
            else VALIDATION_STATUS_BLOCKING
        )
        if (
            status == VALIDATION_STATUS_PASS
            and str(rollup["group_kind"]) == "geometry_ablation"
            and _is_zero_effect(float(rollup["summary_statistics"]["mean"]))
        ):
            status = VALIDATION_STATUS_BLOCKING
        findings.append(
            _finding(
                validator_id=SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID,
                finding_id=(
                    "shared_effect_reproducibility:"
                    f"{rollup['group_id']}:{rollup['metric_id']}:seed_and_effect_consistency"
                ),
                status=status,
                case_id=f"{rollup['group_id']}::{rollup['metric_id']}",
                summary={
                    "group_kind": str(rollup["group_kind"]),
                    "effect_direction": str(rollup["effect_direction"]),
                    "mean": rollup["summary_statistics"]["mean"],
                    "seed_count": int(rollup["seed_count"]),
                    "sign_consistency": bool(rollup["sign_consistency"]),
                },
            )
        )

    null_tests_by_id = _null_test_results_by_id(summary)
    for null_test_id in _RELEVANT_SHARED_NULL_TEST_IDS:
        result = null_tests_by_id.get(null_test_id)
        if result is None:
            raise ValueError(
                f"Task validation requires null_test_id {null_test_id!r} in the "
                "experiment-analysis summary."
            )
        findings.append(
            _finding(
                validator_id=SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID,
                finding_id=(
                    "shared_effect_reproducibility:null_test:" f"{null_test_id}"
                ),
                status=_status_from_null_test(str(result["status"])),
                case_id=null_test_id,
                summary={
                    "status": str(result["status"]),
                    "metric_outcome_count": len(result.get("metric_outcomes", [])),
                },
            )
        )

    for expectation in perturbation_expectations:
        suite_id = str(expectation["suite_id"])
        if suite_id not in _EXTERNAL_TASK_PERTURBATION_SUITE_IDS:
            continue
        if (
            SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID
            not in set(expectation["target_validator_ids"])
        ):
            continue
        for perturbation in perturbation_inputs:
            if perturbation.suite_id != suite_id:
                continue
            variant_rollups = _shared_group_rollups(perturbation.analysis.summary)
            variant_by_key = {
                (str(item["group_id"]), str(item["metric_id"])): item
                for item in variant_rollups
            }
            for base_rollup in rollups:
                key = (str(base_rollup["group_id"]), str(base_rollup["metric_id"]))
                variant_rollup = variant_by_key.get(key)
                if variant_rollup is None:
                    raise ValueError(
                        "Perturbation analysis "
                        f"{perturbation.suite_id}:{perturbation.variant_id} is missing "
                        f"shared rollup {key!r} required for task validation."
                    )
                expected_seeds = _expected_seeds_for_group(
                    summary=summary,
                    group_id=str(base_rollup["group_id"]),
                    group_by_id=group_by_id,
                )
                observed_variant_seeds = [
                    int(seed) for seed in variant_rollup.get("seeds", [])
                ]
                if observed_variant_seeds != expected_seeds:
                    raise ValueError(
                        "Perturbation analysis "
                        f"{perturbation.suite_id}:{perturbation.variant_id} is missing "
                        f"required shared seed coverage for {key!r}; expected "
                        f"{expected_seeds!r}, got {observed_variant_seeds!r}."
                    )
                findings.append(
                    _finding(
                        validator_id=SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID,
                        finding_id=(
                            "shared_effect_reproducibility:"
                            f"{perturbation.suite_id}:{perturbation.variant_id}:"
                            f"{base_rollup['group_id']}:{base_rollup['metric_id']}:"
                            "perturbation_consistency"
                        ),
                        status=_status_for_effect_preservation(
                            base_value=float(base_rollup["summary_statistics"]["mean"]),
                            variant_value=float(
                                variant_rollup["summary_statistics"]["mean"]
                            ),
                        ),
                        case_id=f"{perturbation.suite_id}::{perturbation.variant_id}",
                        summary={
                            "group_id": str(base_rollup["group_id"]),
                            "metric_id": str(base_rollup["metric_id"]),
                            "base_mean": base_rollup["summary_statistics"]["mean"],
                            "variant_mean": variant_rollup["summary_statistics"]["mean"],
                        },
                    )
                )

    return findings


def _evaluate_task_decoder_robustness(
    *,
    base_input: _LoadedAnalysisInput,
    perturbation_inputs: Sequence[_PerturbationAnalysisInput],
    perturbation_expectations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    summary = base_input.summary
    task_rows = _task_metric_rows(summary)
    task_rollups = _task_group_rollups(summary)
    decoder_summaries = _task_decoder_summaries(summary)
    if not task_rows or not task_rollups or not decoder_summaries:
        raise ValueError(
            "Task validation requires task-decoder metric rows, group rollups, and "
            "decoder summaries for task_decoder_robustness."
        )

    findings: list[dict[str, Any]] = []
    expected_seeds_by_arm = {
        str(arm_id): [int(seed) for seed in seeds]
        for arm_id, seeds in summary["bundle_set"]["expected_seeds_by_arm_id"].items()
    }

    for decoder_summary in decoder_summaries:
        findings.append(
            _finding(
                validator_id=TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
                finding_id=(
                    "task_decoder_robustness:"
                    f"{decoder_summary['arm_id']}:{decoder_summary['decoder_id']}:"
                    "decoder_status"
                ),
                status=(
                    VALIDATION_STATUS_PASS
                    if str(decoder_summary["status"]) == "ok"
                    else VALIDATION_STATUS_BLOCKING
                ),
                case_id=f"{decoder_summary['arm_id']}::{decoder_summary['decoder_id']}",
                summary={
                    "status": str(decoder_summary["status"]),
                    "seed": int(decoder_summary["seed"]),
                    "readout_id": str(decoder_summary["readout_id"]),
                },
            )
        )

    rows_by_arm_metric = _task_rows_by_arm_metric(task_rows)
    for (arm_id, metric_id), rows in sorted(rows_by_arm_metric.items()):
        expected_seeds = expected_seeds_by_arm.get(arm_id)
        if expected_seeds is None:
            raise ValueError(
                f"Task metric rows reference unexpected arm_id {arm_id!r}."
            )
        observed_seeds = [int(item["seed"]) for item in rows]
        if observed_seeds != expected_seeds:
            raise ValueError(
                f"Task-decoder metric {metric_id!r} for arm_id {arm_id!r} is missing "
                f"required seed coverage; expected {expected_seeds!r}, got "
                f"{observed_seeds!r}."
            )
        values = [float(item["value"]) for item in rows]
        if metric_id in _HEADING_METRIC_IDS:
            deviation = _max_heading_deviation_deg(values)
            status = _status_for_limit(
                value=deviation,
                pass_limit=DEFAULT_HEADING_STABILITY_PASS_DEG,
                review_limit=DEFAULT_HEADING_STABILITY_REVIEW_DEG,
            )
            diagnostic_value = deviation
        else:
            diagnostic_value = _coefficient_of_variation(values)
            status = _status_for_limit(
                value=diagnostic_value,
                pass_limit=DEFAULT_SPEED_CV_PASS,
                review_limit=DEFAULT_SPEED_CV_REVIEW,
            )
        findings.append(
            _finding(
                validator_id=TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
                finding_id=(
                    "task_decoder_robustness:"
                    f"{arm_id}:{metric_id}:seed_stability"
                ),
                status=status,
                case_id=f"{arm_id}::{metric_id}",
                summary={
                    "seeds": observed_seeds,
                    "values": [_rounded_float(value) for value in values],
                    "diagnostic_value": _rounded_float(diagnostic_value),
                },
            )
        )

    group_by_id = _comparison_groups_by_id(summary)
    for rollup in task_rollups:
        expected_seeds = _expected_seeds_for_group(
            summary=summary,
            group_id=str(rollup["group_id"]),
            group_by_id=group_by_id,
        )
        observed_seeds = [int(seed) for seed in rollup.get("seeds", [])]
        if observed_seeds != expected_seeds:
            raise ValueError(
                f"Task-decoder rollup {rollup['group_id']!r}/{rollup['metric_id']!r} "
                f"is missing required seed coverage; expected {expected_seeds!r}, got "
                f"{observed_seeds!r}."
            )
        mean_value = float(rollup["summary_statistics"]["mean"])
        if str(rollup["metric_id"]) in _HEADING_METRIC_IDS:
            status = _status_for_limit(
                value=_heading_delta_deg(mean_value, 0.0),
                pass_limit=DEFAULT_HEADING_STABILITY_PASS_DEG,
                review_limit=DEFAULT_HEADING_STABILITY_REVIEW_DEG,
            )
        else:
            status = (
                VALIDATION_STATUS_PASS
                if bool(rollup["sign_consistency"]) and not _is_zero_effect(mean_value)
                else VALIDATION_STATUS_BLOCKING
            )
        findings.append(
            _finding(
                validator_id=TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
                finding_id=(
                    "task_decoder_robustness:"
                    f"{rollup['group_id']}:{rollup['metric_id']}:comparison_consistency"
                ),
                status=status,
                case_id=f"{rollup['group_id']}::{rollup['metric_id']}",
                summary={
                    "group_kind": str(rollup["group_kind"]),
                    "mean": rollup["summary_statistics"]["mean"],
                    "sign_consistency": bool(rollup["sign_consistency"]),
                },
            )
        )

    for expectation in perturbation_expectations:
        suite_id = str(expectation["suite_id"])
        if suite_id not in _EXTERNAL_TASK_PERTURBATION_SUITE_IDS:
            continue
        if TASK_DECODER_ROBUSTNESS_VALIDATOR_ID not in set(
            expectation["target_validator_ids"]
        ):
            continue
        for perturbation in perturbation_inputs:
            if perturbation.suite_id != suite_id:
                continue
            variant_task_rows = _task_metric_rows(perturbation.analysis.summary)
            variant_task_rollups = _task_group_rollups(perturbation.analysis.summary)
            if not variant_task_rows or not variant_task_rollups:
                raise ValueError(
                    "Perturbation analysis "
                    f"{perturbation.suite_id}:{perturbation.variant_id} is missing "
                    "task-decoder inventory required for robustness checks."
                )
            variant_rows_by_arm_metric = _task_rows_by_arm_metric(variant_task_rows)
            for (arm_id, metric_id), base_rows in sorted(rows_by_arm_metric.items()):
                variant_rows = variant_rows_by_arm_metric.get((arm_id, metric_id))
                if variant_rows is None:
                    raise ValueError(
                        "Perturbation analysis "
                        f"{perturbation.suite_id}:{perturbation.variant_id} is missing "
                        f"task metric rows for arm_id {arm_id!r} metric_id {metric_id!r}."
                    )
                expected_variant_seeds = expected_seeds_by_arm.get(arm_id)
                if expected_variant_seeds is None:
                    raise ValueError(
                        f"Task metric rows reference unexpected arm_id {arm_id!r}."
                    )
                observed_variant_seeds = [
                    int(item["seed"]) for item in variant_rows
                ]
                if observed_variant_seeds != expected_variant_seeds:
                    raise ValueError(
                        "Perturbation analysis "
                        f"{perturbation.suite_id}:{perturbation.variant_id} is missing "
                        f"required task seed coverage for arm_id {arm_id!r} metric_id "
                        f"{metric_id!r}; expected {expected_variant_seeds!r}, got "
                        f"{observed_variant_seeds!r}."
                    )
                base_mean = _mean([float(item["value"]) for item in base_rows])
                variant_mean = _mean([float(item["value"]) for item in variant_rows])
                if metric_id in _HEADING_METRIC_IDS:
                    status = _status_for_limit(
                        value=_heading_delta_deg(base_mean, variant_mean),
                        pass_limit=DEFAULT_HEADING_DELTA_PASS_DEG,
                        review_limit=DEFAULT_HEADING_DELTA_REVIEW_DEG,
                    )
                else:
                    status = _status_for_effect_preservation(
                        base_value=base_mean,
                        variant_value=variant_mean,
                    )
                findings.append(
                    _finding(
                        validator_id=TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
                        finding_id=(
                            "task_decoder_robustness:"
                            f"{perturbation.suite_id}:{perturbation.variant_id}:"
                            f"{arm_id}:{metric_id}:perturbation_consistency"
                        ),
                        status=status,
                        case_id=f"{perturbation.suite_id}::{perturbation.variant_id}",
                        summary={
                            "arm_id": arm_id,
                            "metric_id": metric_id,
                            "base_mean": _rounded_float(base_mean),
                            "variant_mean": _rounded_float(variant_mean),
                        },
                    )
                )
            variant_rollups_by_key = {
                (str(item["group_id"]), str(item["metric_id"])): item
                for item in variant_task_rollups
            }
            for base_rollup in task_rollups:
                key = (str(base_rollup["group_id"]), str(base_rollup["metric_id"]))
                variant_rollup = variant_rollups_by_key.get(key)
                if variant_rollup is None:
                    raise ValueError(
                        "Perturbation analysis "
                        f"{perturbation.suite_id}:{perturbation.variant_id} is missing "
                        f"task rollup {key!r} required for robustness checks."
                    )
                expected_seeds = _expected_seeds_for_group(
                    summary=summary,
                    group_id=str(base_rollup["group_id"]),
                    group_by_id=group_by_id,
                )
                observed_variant_seeds = [
                    int(seed) for seed in variant_rollup.get("seeds", [])
                ]
                if observed_variant_seeds != expected_seeds:
                    raise ValueError(
                        "Perturbation analysis "
                        f"{perturbation.suite_id}:{perturbation.variant_id} is missing "
                        f"required task rollup seed coverage for {key!r}; expected "
                        f"{expected_seeds!r}, got {observed_variant_seeds!r}."
                    )
                base_mean = float(base_rollup["summary_statistics"]["mean"])
                variant_mean = float(variant_rollup["summary_statistics"]["mean"])
                if str(base_rollup["metric_id"]) in _HEADING_METRIC_IDS:
                    status = _status_for_limit(
                        value=_heading_delta_deg(base_mean, variant_mean),
                        pass_limit=DEFAULT_HEADING_DELTA_PASS_DEG,
                        review_limit=DEFAULT_HEADING_DELTA_REVIEW_DEG,
                    )
                else:
                    status = _status_for_effect_preservation(
                        base_value=base_mean,
                        variant_value=variant_mean,
                    )
                findings.append(
                    _finding(
                        validator_id=TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
                        finding_id=(
                            "task_decoder_robustness:"
                            f"{perturbation.suite_id}:{perturbation.variant_id}:"
                            f"{base_rollup['group_id']}:{base_rollup['metric_id']}:"
                            "group_perturbation_consistency"
                        ),
                        status=status,
                        case_id=f"{perturbation.suite_id}::{perturbation.variant_id}",
                        summary={
                            "group_id": str(base_rollup["group_id"]),
                            "metric_id": str(base_rollup["metric_id"]),
                            "base_mean": _rounded_float(base_mean),
                            "variant_mean": _rounded_float(variant_mean),
                        },
                    )
                )

    return findings


def _build_validator_case_summary(
    *,
    validator_id: str,
    validator_findings: Sequence[Mapping[str, Any]],
    analysis_inventory: Mapping[str, Any],
    perturbation_expectations: Sequence[Mapping[str, Any]],
    base_input: _LoadedAnalysisInput,
) -> dict[str, Any]:
    return {
        "case_id": validator_id,
        "case_kind": "validator_scope",
        "validator_id": validator_id,
        "status": _worst_status(
            str(item["status"]) for item in validator_findings
        ),
        "finding_count": len(validator_findings),
        "analysis_inventory": copy.deepcopy(dict(analysis_inventory)),
        "perturbation_coverage": [
            copy.deepcopy(dict(item))
            for item in perturbation_expectations
            if validator_id in set(item["target_validator_ids"])
        ],
        "base_analysis_bundle_id": (
            None
            if base_input.bundle_metadata is None
            else str(base_input.bundle_metadata["bundle_id"])
        ),
    }


def _comparison_groups_by_id(summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item["group_id"]): copy.deepcopy(dict(item))
        for item in summary["comparison_group_catalog"]
    }


def _expected_seeds_for_group(
    *,
    summary: Mapping[str, Any],
    group_id: str,
    group_by_id: Mapping[str, Mapping[str, Any]],
) -> list[int]:
    group = group_by_id.get(group_id)
    if group is None:
        raise ValueError(f"Unknown comparison group_id {group_id!r}.")
    if group.get("arm_ids"):
        seeds_by_arm = summary["bundle_set"]["expected_seeds_by_arm_id"]
        seed_sets = [
            [int(seed) for seed in seeds_by_arm[str(arm_id)]]
            for arm_id in group["arm_ids"]
        ]
        first = seed_sets[0]
        for item in seed_sets[1:]:
            if item != first:
                raise ValueError(
                    f"Comparison group {group_id!r} mixes incompatible seed inventories."
                )
        return list(first)
    component_group_ids = group.get("component_group_ids", [])
    if component_group_ids:
        component_seed_sets = [
            _expected_seeds_for_group(
                summary=summary,
                group_id=str(component_group_id),
                group_by_id=group_by_id,
            )
            for component_group_id in component_group_ids
        ]
        first = component_seed_sets[0]
        for item in component_seed_sets[1:]:
            if item != first:
                raise ValueError(
                    f"Comparison group {group_id!r} resolves component groups with "
                    "incompatible seed inventories."
                )
        return list(first)
    raise ValueError(
        f"Comparison group {group_id!r} does not expose arm_ids or component_group_ids."
    )


def _shared_group_rollups(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        copy.deepcopy(dict(item))
        for item in summary.get("group_metric_rollups", [])
        if str(item["metric_id"]) in SUPPORTED_SHARED_READOUT_ANALYSIS_METRIC_IDS
    ]


def _task_group_rollups(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        copy.deepcopy(dict(item))
        for item in summary.get("group_metric_rollups", [])
        if str(item["metric_id"]) in SUPPORTED_TASK_DECODER_ANALYSIS_METRIC_IDS
    ]


def _task_metric_rows(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    analysis_results = summary["analysis_results"]
    task_result = analysis_results.get("task_decoder_analysis", {})
    if not isinstance(task_result, Mapping):
        raise ValueError("summary.analysis_results.task_decoder_analysis must be a mapping.")
    metric_rows = task_result.get("metric_rows", [])
    if not isinstance(metric_rows, Sequence) or isinstance(metric_rows, (str, bytes)):
        raise ValueError(
            "summary.analysis_results.task_decoder_analysis.metric_rows must be a sequence."
        )
    return [copy.deepcopy(dict(item)) for item in metric_rows]


def _task_decoder_summaries(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    analysis_results = summary["analysis_results"]
    task_result = analysis_results.get("task_decoder_analysis", {})
    if not isinstance(task_result, Mapping):
        raise ValueError("summary.analysis_results.task_decoder_analysis must be a mapping.")
    decoder_summaries = task_result.get("decoder_summaries", [])
    if not isinstance(decoder_summaries, Sequence) or isinstance(
        decoder_summaries,
        (str, bytes),
    ):
        raise ValueError(
            "summary.analysis_results.task_decoder_analysis.decoder_summaries must "
            "be a sequence."
        )
    return [copy.deepcopy(dict(item)) for item in decoder_summaries]


def _null_test_results_by_id(summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item["null_test_id"]): copy.deepcopy(dict(item))
        for item in summary.get("null_test_results", [])
    }


def _task_rows_by_arm_metric(
    metric_rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in metric_rows:
        grouped.setdefault(
            (str(item["arm_id"]), str(item["metric_id"])),
            [],
        ).append(copy.deepcopy(dict(item)))
    for rows in grouped.values():
        rows.sort(key=lambda item: int(item["seed"]))
    return grouped


def _group_perturbation_inputs(
    perturbation_inputs: Sequence[_PerturbationAnalysisInput],
) -> dict[str, list[_PerturbationAnalysisInput]]:
    grouped: dict[str, list[_PerturbationAnalysisInput]] = {}
    for item in perturbation_inputs:
        grouped.setdefault(item.suite_id, []).append(item)
    return {
        suite_id: sorted(items, key=lambda item: item.variant_id)
        for suite_id, items in grouped.items()
    }


def _validators_targeted_by_suite(suite_id: str) -> set[str]:
    if suite_id == GEOMETRY_VARIANTS_SUITE_ID:
        return {SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID}
    if suite_id in _EXTERNAL_TASK_PERTURBATION_SUITE_IDS:
        return set(_TASK_VALIDATOR_IDS)
    return set(_TASK_VALIDATOR_IDS)


def _status_from_null_test(status: str) -> str:
    if status == "pass":
        return VALIDATION_STATUS_PASS
    if status == "unavailable":
        return VALIDATION_STATUS_BLOCKED
    return VALIDATION_STATUS_BLOCKING


def _status_for_effect_preservation(*, base_value: float, variant_value: float) -> str:
    if _is_zero_effect(base_value):
        return (
            VALIDATION_STATUS_PASS
            if _is_zero_effect(variant_value)
            else VALIDATION_STATUS_REVIEW
        )
    if _value_sign(base_value) != _value_sign(variant_value):
        return VALIDATION_STATUS_BLOCKING
    ratio = abs(float(variant_value)) / max(abs(float(base_value)), _EPSILON)
    if ratio >= DEFAULT_EFFECT_RATIO_PASS:
        return VALIDATION_STATUS_PASS
    if ratio >= DEFAULT_EFFECT_RATIO_REVIEW:
        return VALIDATION_STATUS_REVIEW
    return VALIDATION_STATUS_BLOCKING


def _status_for_limit(
    *,
    value: float,
    pass_limit: float,
    review_limit: float,
) -> str:
    if value <= pass_limit + _EPSILON:
        return VALIDATION_STATUS_PASS
    if value <= review_limit + _EPSILON:
        return VALIDATION_STATUS_REVIEW
    return VALIDATION_STATUS_BLOCKING


def _coefficient_of_variation(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("coefficient_of_variation requires at least one value.")
    mean_value = abs(_mean(values))
    if mean_value <= _EPSILON:
        return 0.0 if max(abs(value) for value in values) <= _EPSILON else math.inf
    variance = sum((float(value) - _mean(values)) ** 2 for value in values) / len(values)
    return math.sqrt(variance) / mean_value


def _max_heading_deviation_deg(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("max_heading_deviation_deg requires at least one value.")
    mean_heading = _circular_mean_deg(values)
    return max(_heading_delta_deg(mean_heading, float(value)) for value in values)


def _circular_mean_deg(values: Sequence[float]) -> float:
    radians = [math.radians(float(value)) for value in values]
    mean_x = sum(math.cos(value) for value in radians) / len(radians)
    mean_y = sum(math.sin(value) for value in radians) / len(radians)
    if abs(mean_x) <= _EPSILON and abs(mean_y) <= _EPSILON:
        return 0.0
    return _normalize_angle_deg(math.degrees(math.atan2(mean_y, mean_x)))


def _heading_delta_deg(left: float, right: float) -> float:
    delta = (float(left) - float(right) + 180.0) % 360.0 - 180.0
    return abs(delta)


def _normalize_angle_deg(value: float) -> float:
    normalized = float(value) % 360.0
    if normalized > 180.0:
        normalized -= 360.0
    if abs(normalized) <= _ANGLE_TOLERANCE_DEG:
        return 0.0
    return normalized


def _value_sign(value: float) -> str:
    if _is_zero_effect(value):
        return "zero"
    return "positive" if float(value) > 0.0 else "negative"


def _is_zero_effect(value: float) -> bool:
    return abs(float(value)) <= _EPSILON


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("mean requires at least one value.")
    return sum(float(value) for value in values) / len(values)


def _group_findings_by_validator(
    findings: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in findings:
        grouped.setdefault(str(item["validator_id"]), []).append(copy.deepcopy(dict(item)))
    for entries in grouped.values():
        entries.sort(key=lambda item: str(item["finding_id"]))
    return grouped


def _build_validator_summaries(
    findings_by_validator: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for validator_id, findings in findings_by_validator.items():
        summaries[str(validator_id)] = {
            "validator_id": str(validator_id),
            "status": _worst_status(str(item["status"]) for item in findings),
            "finding_count": len(findings),
            "status_counts": {
                VALIDATION_STATUS_PASS: sum(
                    1
                    for item in findings
                    if str(item["status"]) == VALIDATION_STATUS_PASS
                ),
                VALIDATION_STATUS_REVIEW: sum(
                    1
                    for item in findings
                    if str(item["status"]) == VALIDATION_STATUS_REVIEW
                ),
                VALIDATION_STATUS_BLOCKED: sum(
                    1
                    for item in findings
                    if str(item["status"]) == VALIDATION_STATUS_BLOCKED
                ),
                VALIDATION_STATUS_BLOCKING: sum(
                    1
                    for item in findings
                    if str(item["status"]) == VALIDATION_STATUS_BLOCKING
                ),
            },
        }
    return summaries


def _worst_status(statuses: Sequence[str] | Any) -> str:
    ordered = [
        str(status)
        for status in statuses
        if str(status) in _STATUS_RANK
    ]
    if not ordered:
        return VALIDATION_STATUS_BLOCKED
    return max(ordered, key=lambda item: _STATUS_RANK[item])


def _finding(
    *,
    validator_id: str,
    finding_id: str,
    status: str,
    case_id: str,
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "validator_id": validator_id,
        "finding_id": finding_id,
        "status": status,
        "case_id": case_id,
        "summary": copy.deepcopy(dict(summary)),
    }


def _render_report_markdown(
    *,
    summary_payload: Mapping[str, Any],
    findings_by_validator: Mapping[str, Sequence[Mapping[str, Any]]],
) -> str:
    lines = [
        "# Task Validation Report",
        "",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Experiment id: `{summary_payload['experiment_id']}`",
        f"- Bundle id: `{summary_payload['bundle_id']}`",
        "",
        "## Analysis Inventory",
        "",
        "- Shared comparison rollups: "
        f"`{summary_payload['analysis_inventory']['shared_comparison']['group_metric_rollup_count']}`",
        "- Task decoder metric rows: "
        f"`{summary_payload['analysis_inventory']['task_decoder']['metric_row_count']}`",
        "- Task decoder rollups: "
        f"`{summary_payload['analysis_inventory']['task_decoder']['group_metric_rollup_count']}`",
        "- Wave-only diagnostic rollups: "
        f"`{summary_payload['analysis_inventory']['wave_only_diagnostics']['group_metric_rollup_count']}`",
        "- UI scope separation: "
        f"`{summary_payload['analysis_inventory']['ui_scope_separation']['status']}`",
        "",
        "## Perturbation Coverage",
        "",
    ]
    if summary_payload["perturbation_coverage"]:
        for item in summary_payload["perturbation_coverage"]:
            lines.append(
                "- "
                f"`{item['suite_id']}` `{item['status']}` expected="
                f"`{item['expected_variant_ids']}` provided=`{item['provided_variant_ids']}`"
            )
    else:
        lines.append("- No declared perturbation suites were active for task validation.")
    lines.append("")
    lines.append("## Validator Findings")
    lines.append("")
    for validator_id in sorted(findings_by_validator):
        lines.append(f"### `{validator_id}`")
        lines.append("")
        for finding in findings_by_validator[validator_id]:
            lines.append(
                "- "
                f"`{finding['status']}` `{finding['finding_id']}` "
                f"{json.dumps(finding['summary'], sort_keys=True)}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _rounded_float(value: float) -> float:
    return round(float(value), 12)


def _load_json_mapping(path: str | Path) -> dict[str, Any]:
    with Path(path).resolve().open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"JSON payload at {path} must be a mapping.")
    return copy.deepcopy(dict(payload))


__all__ = [
    "TASK_VALIDATION_PLAN_VERSION",
    "TASK_VALIDATION_REPORT_VERSION",
    "execute_task_validation_workflow",
    "run_task_validation_suite",
]
