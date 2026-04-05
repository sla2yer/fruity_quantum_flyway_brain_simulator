from __future__ import annotations

import copy
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .config import get_config_path, get_project_root, load_config
from .geometry_contract import (
    CLAMPED_BOUNDARY_CONDITION_MODE,
    DEFAULT_BOUNDARY_CONDITION_MODE,
)
from .io_utils import ensure_dir, write_json
from .operator_qa import build_operator_qa_output_dir
from .simulation_planning import resolve_manifest_simulation_plan
from .surface_wave_execution import resolve_surface_wave_execution_plan_from_arm_plan
from .surface_wave_solver import (
    SURFACE_STATE_RESOLUTION,
    SingleNeuronSurfaceWaveSolver,
    SurfaceWaveOperatorBundle,
    SurfaceWaveState,
)
from .validation_contract import (
    NUMERICAL_SANITY_LAYER_ID,
    NUMERICAL_STABILITY_FAMILY_ID,
    OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID,
    SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
    VALIDATION_STATUS_BLOCKED,
    VALIDATION_STATUS_BLOCKING,
    VALIDATION_STATUS_PASS,
    VALIDATION_STATUS_REVIEW,
    build_validation_bundle_metadata,
    build_validation_contract_reference,
    build_validation_plan_reference,
    write_validation_bundle_metadata,
)
from .validation_planning import TIMESTEP_SWEEPS_SUITE_ID, normalize_validation_config


NUMERICAL_VALIDATION_PLAN_VERSION = "numerical_validation_plan.v1"
NUMERICAL_VALIDATION_REPORT_VERSION = "numerical_validation_suite.v1"

DEFAULT_TIMESTEP_SWEEP_FACTORS = (0.5, 0.9, 1.05)
DEFAULT_SHARED_STEP_COUNT = 8
DEFAULT_OPERATOR_SYMMETRY_WARN = 1.0e-8
DEFAULT_OPERATOR_SYMMETRY_FAIL = 1.0e-6
DEFAULT_OPERATOR_MIN_EIGENVALUE_WARN = -1.0e-8
DEFAULT_OPERATOR_MIN_EIGENVALUE_FAIL = -1.0e-6
DEFAULT_RUNTIME_DT_RATIO_WARN = 0.95
DEFAULT_RUNTIME_DT_RATIO_FAIL = 1.0
DEFAULT_TRANSFER_GALERKIN_WARN = 1.0e-4
DEFAULT_TRANSFER_GALERKIN_FAIL = 1.0e-2
DEFAULT_TRANSFER_CONSTANT_WARN = 1.0e-8
DEFAULT_TRANSFER_CONSTANT_FAIL = 1.0e-5
DEFAULT_ENERGY_GROWTH_WARN = 1.05
DEFAULT_ENERGY_GROWTH_FAIL = 1.25
DEFAULT_PEAK_GROWTH_WARN = 1.25
DEFAULT_PEAK_GROWTH_FAIL = 1.75
DEFAULT_BOUNDARY_CLAMP_WARN = 1.0e-10
DEFAULT_BOUNDARY_CLAMP_FAIL = 1.0e-8
DEFAULT_BOUNDARY_VARIANT_MIN_RELATIVE_DIFFERENCE = 1.0e-3
DEFAULT_RESOLUTION_SENSITIVITY_WARN = 0.25
DEFAULT_RESOLUTION_SENSITIVITY_FAIL = 0.75
_EPSILON = 1.0e-12

_STATUS_RANK = {
    VALIDATION_STATUS_PASS: 0,
    VALIDATION_STATUS_REVIEW: 1,
    VALIDATION_STATUS_BLOCKED: 2,
    VALIDATION_STATUS_BLOCKING: 3,
}

_DEFAULT_NUMERICAL_CRITERIA_BY_VALIDATOR = {
    OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID: (
        "validation_criteria.numerical_stability.operator_bundle_gate_alignment.v1"
    ),
    SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID: (
        "validation_criteria.numerical_stability.surface_wave_stability_envelope.v1"
    ),
}
@dataclass(frozen=True)
class NumericalValidationCase:
    case_id: str
    root_id: int
    surface_wave_model: Mapping[str, Any]
    reference_operator_bundle: SurfaceWaveOperatorBundle
    integration_timestep_ms: float | None = None
    shared_output_timestep_ms: float | None = None
    shared_step_count: int = DEFAULT_SHARED_STEP_COUNT
    arm_id: str | None = None
    source_label: str | None = None
    pulse_seed_vertex: int | None = None
    pulse_amplitude: float = 1.0
    pulse_support_radius_scale: float = 1.5
    timestep_sweep_factors: Sequence[float] = DEFAULT_TIMESTEP_SWEEP_FACTORS
    boundary_variant_bundles: Mapping[str, SurfaceWaveOperatorBundle] = field(
        default_factory=dict
    )
    coarse_operator_bundle: SurfaceWaveOperatorBundle | None = None
    operator_qa_summary: Mapping[str, Any] | None = None
    diagnostic_tags: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        case_id = str(self.case_id).strip()
        if not case_id:
            raise ValueError("numerical validation cases require a non-empty case_id.")
        if self.shared_step_count < 1:
            raise ValueError("shared_step_count must be positive.")
        if self.pulse_amplitude <= 0.0:
            raise ValueError("pulse_amplitude must be positive.")
        if self.pulse_support_radius_scale <= 0.0:
            raise ValueError("pulse_support_radius_scale must be positive.")
        if int(self.root_id) != int(self.reference_operator_bundle.root_id):
            raise ValueError(
                "numerical validation case root_id must match the reference operator bundle."
            )
        if self.coarse_operator_bundle is not None and (
            self.coarse_operator_bundle.surface_vertex_count < 1
        ):
            raise ValueError("coarse_operator_bundle must be non-empty when provided.")

    @property
    def normalized_timestep_sweep_factors(self) -> tuple[float, ...]:
        seen: list[float] = []
        for value in self.timestep_sweep_factors:
            factor = float(value)
            if factor <= 0.0:
                raise ValueError(
                    f"timestep_sweep_factors for case {self.case_id!r} must be positive."
                )
            if factor not in seen:
                seen.append(factor)
        return tuple(sorted(seen))

    def summary_mapping(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "arm_id": self.arm_id,
            "root_id": int(self.root_id),
            "source_label": self.source_label,
            "shared_step_count": int(self.shared_step_count),
            "integration_timestep_ms": self.integration_timestep_ms,
            "shared_output_timestep_ms": self.shared_output_timestep_ms,
            "timestep_sweep_factors": list(self.normalized_timestep_sweep_factors),
            "boundary_variant_ids": sorted(self.boundary_variant_bundles),
            "has_coarse_operator_bundle": self.coarse_operator_bundle is not None,
            "diagnostic_tags": copy.deepcopy(dict(self.diagnostic_tags)),
        }


@dataclass(frozen=True)
class _ProbeResult:
    integration_timestep_ms: float
    shared_output_timestep_ms: float
    max_supported_timestep_ms: float
    internal_substep_count: int
    energy_history: np.ndarray
    activation_peak_history: np.ndarray
    patch_activation_history: np.ndarray | None
    final_activation: np.ndarray
    final_patch_activation: np.ndarray | None
    boundary_activation_max_abs: float


def resolve_numerical_validation_plan(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    arm_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    simulation_plan = resolve_manifest_simulation_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    cfg = load_config(config_path)
    config_file = get_config_path(cfg)
    project_root = get_project_root(cfg)
    if config_file is None or project_root is None:
        raise ValueError("Loaded config is missing config metadata.")
    validation_config = normalize_validation_config(
        cfg.get("validation"),
        project_root=project_root,
    )
    target_arm_ids = _resolve_target_surface_wave_arm_ids(
        simulation_plan=simulation_plan,
        validation_config=validation_config,
        arm_ids=arm_ids,
    )
    active_validator_ids = _resolve_active_numerical_validator_ids(validation_config)
    criteria_assignments = _resolve_numerical_criteria_assignments(
        validation_config=validation_config,
        active_validator_ids=active_validator_ids,
    )
    timestep_suite = _build_timestep_suite_reference(
        validation_config=validation_config,
        active_validator_ids=active_validator_ids,
    )
    plan_reference = build_validation_plan_reference(
        experiment_id=str(simulation_plan["manifest_reference"]["experiment_id"]),
        contract_reference=build_validation_contract_reference(),
        active_layer_ids=[NUMERICAL_SANITY_LAYER_ID],
        active_validator_family_ids=[NUMERICAL_STABILITY_FAMILY_ID],
        active_validator_ids=active_validator_ids,
        criteria_profile_references=[
            item["criteria_profile_reference"] for item in criteria_assignments
        ],
        criteria_profile_assignments=[
            {
                "validator_id": item["validator_id"],
                "criteria_profile_reference": item["criteria_profile_reference"],
            }
            for item in criteria_assignments
        ],
        evidence_bundle_references={},
        target_arm_ids=target_arm_ids,
        comparison_group_ids=[],
        perturbation_suite_references=(
            [] if timestep_suite is None else [timestep_suite]
        ),
        plan_version=NUMERICAL_VALIDATION_PLAN_VERSION,
    )
    bundle_metadata = build_validation_bundle_metadata(
        validation_plan_reference=plan_reference,
        processed_simulator_results_dir=cfg["paths"]["processed_simulator_results_dir"],
    )
    return {
        "plan_version": NUMERICAL_VALIDATION_PLAN_VERSION,
        "manifest_reference": copy.deepcopy(dict(simulation_plan["manifest_reference"])),
        "validation_config": validation_config,
        "config_reference": {
            "config_path": str(config_file.resolve()),
            "project_root": str(project_root.resolve()),
        },
        "active_layer_ids": [NUMERICAL_SANITY_LAYER_ID],
        "active_validator_family_ids": [NUMERICAL_STABILITY_FAMILY_ID],
        "active_validator_ids": list(active_validator_ids),
        "criteria_profile_assignments": criteria_assignments,
        "perturbation_suites": (
            [] if timestep_suite is None else [copy.deepcopy(timestep_suite)]
        ),
        "target_arm_ids": target_arm_ids,
        "validation_plan_reference": plan_reference,
        "validation_bundle": {
            "bundle_id": str(bundle_metadata["bundle_id"]),
            "validation_spec_hash": str(bundle_metadata["validation_spec_hash"]),
            "metadata": copy.deepcopy(bundle_metadata),
        },
        "output_locations": {
            "bundle_directory": str(
                Path(bundle_metadata["bundle_layout"]["bundle_directory"]).resolve()
            ),
            "report_directory": str(
                Path(bundle_metadata["bundle_layout"]["report_directory"]).resolve()
            ),
            "artifacts": copy.deepcopy(dict(bundle_metadata["artifacts"])),
        },
    }


def _build_numerical_validation_plan_from_context(
    *,
    validation_plan: Mapping[str, Any],
    simulation_plan: Mapping[str, Any],
    arm_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(validation_plan, Mapping):
        raise ValueError("validation_plan must be a mapping.")
    if not isinstance(simulation_plan, Mapping):
        raise ValueError("simulation_plan must be a mapping.")

    validation_config = copy.deepcopy(dict(validation_plan["validation_config"]))
    config_reference = copy.deepcopy(dict(validation_plan["config_reference"]))
    source_plan_reference = copy.deepcopy(dict(validation_plan["validation_plan_reference"]))
    target_arm_ids = _resolve_target_surface_wave_arm_ids(
        simulation_plan=simulation_plan,
        validation_config=validation_config,
        arm_ids=arm_ids,
    )
    active_validator_ids = [
        validator_id
        for validator_id in validation_plan["active_validator_ids"]
        if validator_id
        in {
            OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID,
            SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
        }
    ]
    if not active_validator_ids:
        raise ValueError(
            "Resolved validation configuration does not activate the numerical_sanity layer."
        )
    criteria_assignments = [
        copy.deepcopy(dict(item))
        for item in validation_plan["criteria_profile_assignments"]
        if str(item["validator_id"]) in set(active_validator_ids)
    ]
    timestep_suite = _build_timestep_suite_reference(
        validation_config=validation_config,
        active_validator_ids=active_validator_ids,
    )
    plan_reference = build_validation_plan_reference(
        experiment_id=str(simulation_plan["manifest_reference"]["experiment_id"]),
        contract_reference=copy.deepcopy(
            dict(source_plan_reference["contract_reference"])
        ),
        active_layer_ids=[NUMERICAL_SANITY_LAYER_ID],
        active_validator_family_ids=[NUMERICAL_STABILITY_FAMILY_ID],
        active_validator_ids=active_validator_ids,
        criteria_profile_references=[
            item["criteria_profile_reference"] for item in criteria_assignments
        ],
        criteria_profile_assignments=[
            {
                "validator_id": item["validator_id"],
                "criteria_profile_reference": item["criteria_profile_reference"],
            }
            for item in criteria_assignments
        ],
        evidence_bundle_references={},
        target_arm_ids=target_arm_ids,
        comparison_group_ids=[],
        perturbation_suite_references=(
            [] if timestep_suite is None else [copy.deepcopy(timestep_suite)]
        ),
        plan_version=NUMERICAL_VALIDATION_PLAN_VERSION,
    )
    bundle_metadata = build_validation_bundle_metadata(
        validation_plan_reference=plan_reference,
        processed_simulator_results_dir=validation_plan["validation_bundle"]["metadata"][
            "output_root_reference"
        ]["processed_simulator_results_dir"],
    )
    return {
        "plan_version": NUMERICAL_VALIDATION_PLAN_VERSION,
        "manifest_reference": copy.deepcopy(
            dict(simulation_plan["manifest_reference"])
        ),
        "validation_config": validation_config,
        "config_reference": config_reference,
        "active_layer_ids": [NUMERICAL_SANITY_LAYER_ID],
        "active_validator_family_ids": [NUMERICAL_STABILITY_FAMILY_ID],
        "active_validator_ids": list(active_validator_ids),
        "criteria_profile_assignments": criteria_assignments,
        "perturbation_suites": (
            [] if timestep_suite is None else [copy.deepcopy(timestep_suite)]
        ),
        "target_arm_ids": target_arm_ids,
        "validation_plan_reference": plan_reference,
        "validation_bundle": {
            "bundle_id": str(bundle_metadata["bundle_id"]),
            "validation_spec_hash": str(bundle_metadata["validation_spec_hash"]),
            "metadata": copy.deepcopy(bundle_metadata),
        },
        "output_locations": {
            "bundle_directory": str(
                Path(bundle_metadata["bundle_layout"]["bundle_directory"]).resolve()
            ),
            "report_directory": str(
                Path(bundle_metadata["bundle_layout"]["report_directory"]).resolve()
            ),
            "artifacts": copy.deepcopy(dict(bundle_metadata["artifacts"])),
        },
    }


def run_numerical_validation_suite(
    cases: Sequence[NumericalValidationCase],
    *,
    validation_plan_reference: Mapping[str, Any] | None = None,
    bundle_metadata: Mapping[str, Any] | None = None,
    processed_simulator_results_dir: str | Path | None = None,
    experiment_id: str = "fixture_numerical_validation",
) -> dict[str, Any]:
    normalized_cases = _normalize_cases(cases)
    resolved_bundle_metadata = _resolve_bundle_metadata(
        validation_plan_reference=validation_plan_reference,
        bundle_metadata=bundle_metadata,
        processed_simulator_results_dir=processed_simulator_results_dir,
        experiment_id=experiment_id,
        cases=normalized_cases,
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

    findings: list[dict[str, Any]] = []
    case_summaries: list[dict[str, Any]] = []
    for case in normalized_cases:
        case_findings = _evaluate_case(case)
        findings.extend(case_findings)
        case_summaries.append(_build_case_summary(case, case_findings))

    findings_by_validator = _group_findings_by_validator(findings)
    validator_summaries = _build_validator_summaries(findings_by_validator)
    layer_status = _worst_status(
        summary["status"] for summary in validator_summaries.values()
    )
    overall_status = layer_status
    status_counts = {
        VALIDATION_STATUS_PASS: sum(1 for item in findings if item["status"] == VALIDATION_STATUS_PASS),
        VALIDATION_STATUS_REVIEW: sum(1 for item in findings if item["status"] == VALIDATION_STATUS_REVIEW),
        VALIDATION_STATUS_BLOCKED: sum(1 for item in findings if item["status"] == VALIDATION_STATUS_BLOCKED),
        VALIDATION_STATUS_BLOCKING: sum(1 for item in findings if item["status"] == VALIDATION_STATUS_BLOCKING),
    }

    summary_payload = {
        "format_version": "json_validation_summary.v1",
        "report_version": NUMERICAL_VALIDATION_REPORT_VERSION,
        "bundle_id": str(resolved_bundle_metadata["bundle_id"]),
        "experiment_id": str(resolved_bundle_metadata["experiment_id"]),
        "validation_spec_hash": str(resolved_bundle_metadata["validation_spec_hash"]),
        "overall_status": overall_status,
        "active_layer_ids": [NUMERICAL_SANITY_LAYER_ID],
        "active_validator_family_ids": [NUMERICAL_STABILITY_FAMILY_ID],
        "active_validator_ids": sorted(findings_by_validator),
        "status_counts": status_counts,
        "layers": [
            {
                "layer_id": NUMERICAL_SANITY_LAYER_ID,
                "status": layer_status,
                "validator_families": [
                    {
                        "validator_family_id": NUMERICAL_STABILITY_FAMILY_ID,
                        "status": layer_status,
                        "validators": [
                            copy.deepcopy(validator_summaries[validator_id])
                            for validator_id in sorted(validator_summaries)
                        ],
                    }
                ],
            }
        ],
        "case_summaries": case_summaries,
        "artifact_paths": {
            artifact_id: str(record["path"])
            for artifact_id, record in resolved_bundle_metadata["artifacts"].items()
        },
    }
    findings_payload = {
        "format_version": "json_validation_findings.v1",
        "report_version": NUMERICAL_VALIDATION_REPORT_VERSION,
        "bundle_id": str(resolved_bundle_metadata["bundle_id"]),
        "validator_findings": findings_by_validator,
    }
    review_handoff_payload = {
        "format_version": "json_validation_review_handoff.v1",
        "report_version": NUMERICAL_VALIDATION_REPORT_VERSION,
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
        "report_version": NUMERICAL_VALIDATION_REPORT_VERSION,
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
        "case_count": len(normalized_cases),
        "case_summaries": case_summaries,
    }


def execute_numerical_validation_workflow(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    arm_ids: Sequence[str] | None = None,
    simulation_plan: Mapping[str, Any] | None = None,
    validation_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_simulation_plan = (
        simulation_plan
        if isinstance(simulation_plan, Mapping)
        else resolve_manifest_simulation_plan(
            manifest_path=manifest_path,
            config_path=config_path,
            schema_path=schema_path,
            design_lock_path=design_lock_path,
        )
    )
    plan = (
        _build_numerical_validation_plan_from_context(
            validation_plan=validation_plan,
            simulation_plan=resolved_simulation_plan,
            arm_ids=arm_ids,
        )
        if isinstance(validation_plan, Mapping)
        else resolve_numerical_validation_plan(
            manifest_path=manifest_path,
            config_path=config_path,
            schema_path=schema_path,
            design_lock_path=design_lock_path,
            arm_ids=arm_ids,
        )
    )
    cfg = load_config(config_path)
    cases = _build_cases_from_simulation_plan(
        simulation_plan=resolved_simulation_plan,
        target_arm_ids=plan["target_arm_ids"],
        timestep_sweep_factors=_plan_timestep_sweep_factors(plan),
        operator_qa_dir=cfg["paths"]["operator_qa_dir"],
    )
    result = run_numerical_validation_suite(
        cases,
        validation_plan_reference=plan["validation_plan_reference"],
        bundle_metadata=plan["validation_bundle"]["metadata"],
    )
    return {
        **result,
        "numerical_validation_plan": plan,
    }


def _normalize_cases(
    cases: Sequence[NumericalValidationCase],
) -> list[NumericalValidationCase]:
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
        raise ValueError("cases must be a sequence of NumericalValidationCase instances.")
    normalized: list[NumericalValidationCase] = []
    seen_case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, NumericalValidationCase):
            raise ValueError("cases must contain NumericalValidationCase instances.")
        if case.case_id in seen_case_ids:
            raise ValueError(f"Duplicate numerical validation case_id {case.case_id!r}.")
        seen_case_ids.add(case.case_id)
        normalized.append(case)
    return sorted(normalized, key=lambda item: (item.arm_id or "", item.case_id))


def _resolve_bundle_metadata(
    *,
    validation_plan_reference: Mapping[str, Any] | None,
    bundle_metadata: Mapping[str, Any] | None,
    processed_simulator_results_dir: str | Path | None,
    experiment_id: str,
    cases: Sequence[NumericalValidationCase],
) -> dict[str, Any]:
    if bundle_metadata is not None:
        return copy.deepcopy(dict(bundle_metadata))
    if validation_plan_reference is None:
        validation_plan_reference = _default_plan_reference_for_cases(
            experiment_id=experiment_id,
            cases=cases,
        )
    return build_validation_bundle_metadata(
        validation_plan_reference=validation_plan_reference,
        processed_simulator_results_dir=(
            processed_simulator_results_dir
            if processed_simulator_results_dir is not None
            else Path("data/processed/simulator_results")
        ),
    )


def _default_plan_reference_for_cases(
    *,
    experiment_id: str,
    cases: Sequence[NumericalValidationCase],
) -> dict[str, Any]:
    active_validator_ids = [
        OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID,
        SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
    ]
    criteria_assignments = [
        {
            "validator_id": validator_id,
            "criteria_profile_reference": _DEFAULT_NUMERICAL_CRITERIA_BY_VALIDATOR[
                validator_id
            ],
        }
        for validator_id in active_validator_ids
    ]
    sweep_variant_ids = sorted(
        {
            _dt_variant_id(factor)
            for case in cases
            for factor in case.normalized_timestep_sweep_factors
        }
    )
    return build_validation_plan_reference(
        experiment_id=experiment_id,
        contract_reference=build_validation_contract_reference(),
        active_layer_ids=[NUMERICAL_SANITY_LAYER_ID],
        active_validator_family_ids=[NUMERICAL_STABILITY_FAMILY_ID],
        active_validator_ids=active_validator_ids,
        criteria_profile_references=[
            item["criteria_profile_reference"] for item in criteria_assignments
        ],
        evidence_bundle_references={},
        target_arm_ids=sorted(
            {
                str(case.arm_id)
                for case in cases
                if case.arm_id is not None and str(case.arm_id).strip()
            }
        ),
        comparison_group_ids=[],
        criteria_profile_assignments=criteria_assignments,
        perturbation_suite_references=(
            []
            if not sweep_variant_ids
            else [
                {
                    "suite_id": TIMESTEP_SWEEPS_SUITE_ID,
                    "suite_kind": "timestep_stability_factors",
                    "target_layer_ids": [NUMERICAL_SANITY_LAYER_ID],
                    "target_validator_ids": [
                        SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID
                    ],
                    "variant_ids": sweep_variant_ids,
                }
            ]
        ),
        plan_version=NUMERICAL_VALIDATION_PLAN_VERSION,
    )


def _resolve_target_surface_wave_arm_ids(
    *,
    simulation_plan: Mapping[str, Any],
    validation_config: Mapping[str, Any],
    arm_ids: Sequence[str] | None,
) -> list[str]:
    surface_wave_arm_ids = [
        str(arm_plan["arm_reference"]["arm_id"])
        for arm_plan in simulation_plan["arm_plans"]
        if str(arm_plan["arm_reference"]["model_mode"]) == "surface_wave"
    ]
    if not surface_wave_arm_ids:
        raise ValueError("No surface-wave arms were available for numerical validation.")
    requested_arm_ids = (
        sorted({str(arm_id) for arm_id in arm_ids})
        if arm_ids
        else list(surface_wave_arm_ids)
    )
    unknown_arm_ids = sorted(set(requested_arm_ids) - set(surface_wave_arm_ids))
    if unknown_arm_ids:
        raise ValueError(
            "Requested arm_ids are not available as local surface-wave arms: "
            f"{unknown_arm_ids!r}."
        )
    active_layer_ids = list(validation_config["active_layer_ids"])
    if active_layer_ids and NUMERICAL_SANITY_LAYER_ID not in set(active_layer_ids):
        raise ValueError(
            "validation.active_layer_ids excludes numerical_sanity, so the numerical "
            "validation workflow has no active layer to execute."
        )
    return requested_arm_ids


def _resolve_active_numerical_validator_ids(
    validation_config: Mapping[str, Any],
) -> list[str]:
    numeric_validator_ids = [
        OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID,
        SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
    ]
    requested_validator_ids = list(validation_config["active_validator_ids"])
    if requested_validator_ids:
        active = [
            validator_id
            for validator_id in numeric_validator_ids
            if validator_id in set(requested_validator_ids)
        ]
        if not active:
            raise ValueError(
                "validation.active_validator_ids excludes the numerical validators "
                "required by the numerical validation workflow."
            )
        return active
    requested_family_ids = list(validation_config["active_validator_family_ids"])
    if requested_family_ids and NUMERICAL_STABILITY_FAMILY_ID not in set(
        requested_family_ids
    ):
        raise ValueError(
            "validation.active_validator_family_ids excludes numerical_stability, so "
            "the numerical validation workflow has no active validators to execute."
        )
    return numeric_validator_ids


def _resolve_numerical_criteria_assignments(
    *,
    validation_config: Mapping[str, Any],
    active_validator_ids: Sequence[str],
) -> list[dict[str, Any]]:
    overrides = validation_config["criteria_profiles"]
    layer_overrides = dict(overrides["layer_overrides"])
    family_overrides = dict(overrides["validator_family_overrides"])
    validator_overrides = dict(overrides["validator_overrides"])
    assignments: list[dict[str, Any]] = []
    for validator_id in active_validator_ids:
        if validator_id in validator_overrides:
            reference = validator_overrides[validator_id]
            source = "validator_override"
        elif NUMERICAL_STABILITY_FAMILY_ID in family_overrides:
            reference = family_overrides[NUMERICAL_STABILITY_FAMILY_ID]
            source = "validator_family_override"
        elif NUMERICAL_SANITY_LAYER_ID in layer_overrides:
            reference = layer_overrides[NUMERICAL_SANITY_LAYER_ID]
            source = "layer_override"
        else:
            reference = _DEFAULT_NUMERICAL_CRITERIA_BY_VALIDATOR[validator_id]
            source = "validator_contract_default"
        assignments.append(
            {
                "validator_id": validator_id,
                "criteria_profile_reference": str(reference),
                "criteria_profile_source": source,
            }
        )
    return sorted(assignments, key=lambda item: item["validator_id"])


def _build_timestep_suite_reference(
    *,
    validation_config: Mapping[str, Any],
    active_validator_ids: Sequence[str],
) -> dict[str, Any] | None:
    if SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID not in set(active_validator_ids):
        return None
    suite_config = validation_config["perturbation_suites"][TIMESTEP_SWEEPS_SUITE_ID]
    if not suite_config["enabled"]:
        return None
    return {
        "suite_id": TIMESTEP_SWEEPS_SUITE_ID,
        "suite_kind": "timestep_stability_factors",
        "target_layer_ids": [NUMERICAL_SANITY_LAYER_ID],
        "target_validator_ids": [SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID],
        "variant_ids": [_dt_variant_id(factor) for factor in DEFAULT_TIMESTEP_SWEEP_FACTORS],
    }


def _plan_timestep_sweep_factors(plan: Mapping[str, Any]) -> tuple[float, ...]:
    if not plan.get("perturbation_suites"):
        return ()
    return tuple(DEFAULT_TIMESTEP_SWEEP_FACTORS)


def _build_cases_from_simulation_plan(
    *,
    simulation_plan: Mapping[str, Any],
    target_arm_ids: Sequence[str],
    timestep_sweep_factors: Sequence[float],
    operator_qa_dir: str | Path,
) -> list[NumericalValidationCase]:
    target_arm_id_set = set(target_arm_ids)
    operator_qa_summary_by_root = _load_operator_qa_root_summaries(
        operator_qa_dir=operator_qa_dir,
        simulation_plan=simulation_plan,
    )
    cases: list[NumericalValidationCase] = []
    for arm_plan in simulation_plan["arm_plans"]:
        arm_id = str(arm_plan["arm_reference"]["arm_id"])
        if arm_id not in target_arm_id_set:
            continue
        if str(arm_plan["arm_reference"]["model_mode"]) != "surface_wave":
            continue
        resolved = resolve_surface_wave_execution_plan_from_arm_plan(arm_plan)
        for bundle in resolved.operator_bundles:
            coarse_bundle = _build_coarse_resolution_bundle(bundle)
            cases.append(
                NumericalValidationCase(
                    case_id=f"{arm_id}__root_{int(bundle.root_id)}",
                    arm_id=arm_id,
                    root_id=int(bundle.root_id),
                    surface_wave_model=copy.deepcopy(resolved.surface_wave_model),
                    reference_operator_bundle=bundle,
                    integration_timestep_ms=float(resolved.integration_timestep_ms),
                    shared_output_timestep_ms=float(resolved.shared_output_timestep_ms),
                    shared_step_count=min(
                        int(resolved.timebase.sample_count),
                        DEFAULT_SHARED_STEP_COUNT,
                    ),
                    timestep_sweep_factors=tuple(timestep_sweep_factors),
                    coarse_operator_bundle=coarse_bundle,
                    operator_qa_summary=operator_qa_summary_by_root.get(int(bundle.root_id)),
                    source_label="surface_wave_execution_plan",
                    diagnostic_tags={
                        "topology_condition": str(resolved.surface_wave_execution_plan["topology_condition"]),
                        "bundle_source_kind": str(bundle.source_reference.get("source_kind", "unknown")),
                    },
                )
            )
    if not cases:
        raise ValueError("No executable numerical validation cases were built.")
    return cases


def _load_operator_qa_root_summaries(
    *,
    operator_qa_dir: str | Path,
    simulation_plan: Mapping[str, Any],
) -> dict[int, dict[str, Any]]:
    selected_root_ids = list(
        simulation_plan["arm_plans"][0]["selection"]["selected_root_ids"]
    )
    summary_path = (
        build_operator_qa_output_dir(operator_qa_dir, selected_root_ids).resolve()
        / "summary.json"
    )
    if not summary_path.exists():
        return {}
    with summary_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    roots = payload.get("roots", {})
    if not isinstance(roots, Mapping):
        return {}
    return {
        int(root_id): copy.deepcopy(dict(root_summary))
        for root_id, root_summary in roots.items()
        if isinstance(root_summary, Mapping)
    }


def _build_coarse_resolution_bundle(
    bundle: SurfaceWaveOperatorBundle,
) -> SurfaceWaveOperatorBundle | None:
    if bundle.coarse_operator is None:
        return None
    patch_count = int(bundle.coarse_operator.shape[0])
    if patch_count < 1:
        return None
    patch_mass = (
        np.asarray(bundle.patch_mass_diagonal, dtype=np.float64)
        if bundle.patch_mass_diagonal is not None
        else np.ones(patch_count, dtype=np.float64)
    )
    return SurfaceWaveOperatorBundle.from_fixture(
        root_id=int(bundle.root_id),
        surface_operator=bundle.coarse_operator,
        mass_diagonal=patch_mass,
        boundary_condition_mode=DEFAULT_BOUNDARY_CONDITION_MODE,
        fixture_name=f"coarse_resolution_variant_{int(bundle.root_id)}",
    )


def _evaluate_case(case: NumericalValidationCase) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    findings.extend(_evaluate_operator_bundle_gate_alignment(case))
    findings.extend(_evaluate_surface_wave_stability_envelope(case))
    return sorted(
        findings,
        key=lambda item: (item["validator_id"], item["finding_id"]),
    )


def _evaluate_operator_bundle_gate_alignment(
    case: NumericalValidationCase,
) -> list[dict[str, Any]]:
    bundle = case.reference_operator_bundle
    findings: list[dict[str, Any]] = []

    if case.operator_qa_summary is not None:
        gate = str(case.operator_qa_summary.get("operator_readiness_gate", "review"))
        status = (
            VALIDATION_STATUS_PASS
            if gate == "go"
            else VALIDATION_STATUS_REVIEW
            if gate == "review"
            else VALIDATION_STATUS_BLOCKING
        )
        findings.append(
            _finding_record(
                validator_id=OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID,
                case=case,
                metric_id="operator_qa_gate",
                measured_quantity="operator_readiness_gate",
                measured_value=gate,
                comparison_basis={
                    "kind": "enum_membership",
                    "expected_values": ["go", "review"],
                },
                status=status,
                diagnostic_metadata=copy.deepcopy(dict(case.operator_qa_summary)),
            )
        )

    symmetry_residual = _symmetry_residual_inf(bundle.surface_operator)
    findings.append(
        _threshold_finding(
            validator_id=OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID,
            case=case,
            metric_id="surface_operator_symmetry_residual_inf",
            measured_quantity="surface_operator_symmetry_residual_inf",
            measured_value=symmetry_residual,
            warn=DEFAULT_OPERATOR_SYMMETRY_WARN,
            fail=DEFAULT_OPERATOR_SYMMETRY_FAIL,
            comparison="max",
            diagnostic_metadata={
                "surface_vertex_count": int(bundle.surface_vertex_count),
                "boundary_condition_mode": str(bundle.boundary_condition_mode),
            },
        )
    )

    if symmetry_residual <= DEFAULT_OPERATOR_SYMMETRY_FAIL:
        min_eigenvalue = _smallest_eigenvalue(bundle.surface_operator)
        findings.append(
            _threshold_finding(
                validator_id=OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID,
                case=case,
                metric_id="surface_operator_smallest_eigenvalue",
                measured_quantity="surface_operator_smallest_eigenvalue",
                measured_value=min_eigenvalue,
                warn=DEFAULT_OPERATOR_MIN_EIGENVALUE_WARN,
                fail=DEFAULT_OPERATOR_MIN_EIGENVALUE_FAIL,
                comparison="min",
                diagnostic_metadata={
                    "spectral_check": "positive_semidefinite_lower_bound",
                },
            )
        )
    else:
        findings.append(
            _finding_record(
                validator_id=OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID,
                case=case,
                metric_id="surface_operator_smallest_eigenvalue",
                measured_quantity="surface_operator_smallest_eigenvalue",
                measured_value=None,
                comparison_basis={
                    "kind": "blocked_by_prerequisite",
                    "required_metric_id": "surface_operator_symmetry_residual_inf",
                },
                status=VALIDATION_STATUS_BLOCKED,
                diagnostic_metadata={
                    "reason": "smallest-eigenvalue check requires a symmetric operator.",
                },
            )
        )

    runtime_solver = _instantiate_solver(
        case=case,
        operator_bundle=bundle,
        integration_timestep_ms=case.integration_timestep_ms,
        shared_output_timestep_ms=case.shared_output_timestep_ms,
    )
    max_supported_dt = float(
        runtime_solver.runtime_metadata.max_supported_integration_timestep_ms
    )
    current_dt = float(runtime_solver.runtime_metadata.integration_timestep_ms)
    dt_ratio = 0.0 if math.isinf(max_supported_dt) else current_dt / max_supported_dt
    findings.append(
        _threshold_finding(
            validator_id=OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID,
            case=case,
            metric_id="runtime_timestep_ratio_to_spectral_bound",
            measured_quantity="runtime_timestep_ratio_to_spectral_bound",
            measured_value=dt_ratio,
            warn=DEFAULT_RUNTIME_DT_RATIO_WARN,
            fail=DEFAULT_RUNTIME_DT_RATIO_FAIL,
            comparison="max",
            diagnostic_metadata={
                "integration_timestep_ms": current_dt,
                "max_supported_timestep_ms": max_supported_dt,
            },
        )
    )

    if bundle.coarse_operator is not None and (
        bundle.restriction is not None and bundle.prolongation is not None
    ):
        galerkin_residual = _coarse_galerkin_residual_relative(bundle)
        findings.append(
            _threshold_finding(
                validator_id=OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID,
                case=case,
                metric_id="coarse_galerkin_operator_residual_relative",
                measured_quantity="coarse_galerkin_operator_residual_relative",
                measured_value=galerkin_residual,
                warn=DEFAULT_TRANSFER_GALERKIN_WARN,
                fail=DEFAULT_TRANSFER_GALERKIN_FAIL,
                comparison="max",
                diagnostic_metadata={
                    "patch_count": int(bundle.patch_count or 0),
                },
            )
        )
        constant_residual = _transfer_constant_preservation_residual_inf(bundle)
        findings.append(
            _threshold_finding(
                validator_id=OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID,
                case=case,
                metric_id="transfer_constant_preservation_residual_inf",
                measured_quantity="transfer_constant_preservation_residual_inf",
                measured_value=constant_residual,
                warn=DEFAULT_TRANSFER_CONSTANT_WARN,
                fail=DEFAULT_TRANSFER_CONSTANT_FAIL,
                comparison="max",
                diagnostic_metadata={
                    "patch_count": int(bundle.patch_count or 0),
                },
            )
        )
    return findings


def _evaluate_surface_wave_stability_envelope(
    case: NumericalValidationCase,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    reference_solver = _instantiate_solver(
        case=case,
        operator_bundle=case.reference_operator_bundle,
        integration_timestep_ms=case.integration_timestep_ms,
        shared_output_timestep_ms=case.shared_output_timestep_ms,
    )
    max_supported_dt = float(
        reference_solver.runtime_metadata.max_supported_integration_timestep_ms
    )
    timestep_factors = case.normalized_timestep_sweep_factors
    for factor in timestep_factors:
        variant_id = _dt_variant_id(factor)
        dt_ms = (
            float(factor)
            if math.isinf(max_supported_dt)
            else float(factor) * max_supported_dt
        )
        try:
            probe = _run_localized_pulse_probe(
                case=case,
                operator_bundle=case.reference_operator_bundle,
                integration_timestep_ms=dt_ms,
                shared_output_timestep_ms=max(
                    float(case.shared_output_timestep_ms or dt_ms),
                    dt_ms,
                ),
            )
        except ValueError as exc:
            findings.append(
                _finding_record(
                    validator_id=SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
                    case=case,
                    metric_id="timestep_sweep_execution",
                    measured_quantity="timestep_sweep_execution",
                    measured_value="solver_initialization_failed",
                    comparison_basis={
                        "kind": "runtime_stability_guard",
                        "expected_max_ratio": 1.0,
                    },
                    status=VALIDATION_STATUS_BLOCKING,
                    variant_id=variant_id,
                    diagnostic_metadata={
                        "dt_ratio": float(factor),
                        "integration_timestep_ms": dt_ms,
                        "max_supported_timestep_ms": max_supported_dt,
                        "error": str(exc),
                    },
                )
            )
            continue
        energy_growth = _growth_factor(probe.energy_history)
        peak_growth = _growth_factor(probe.activation_peak_history)
        findings.append(
            _threshold_finding(
                validator_id=SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
                case=case,
                metric_id="energy_growth_factor",
                measured_quantity="pulse_energy_growth_factor",
                measured_value=energy_growth,
                warn=DEFAULT_ENERGY_GROWTH_WARN,
                fail=DEFAULT_ENERGY_GROWTH_FAIL,
                comparison="max",
                variant_id=variant_id,
                diagnostic_metadata={
                    "dt_ratio": float(factor),
                    "integration_timestep_ms": float(probe.integration_timestep_ms),
                    "max_supported_timestep_ms": float(probe.max_supported_timestep_ms),
                },
            )
        )
        findings.append(
            _threshold_finding(
                validator_id=SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
                case=case,
                metric_id="activation_peak_growth_factor",
                measured_quantity="pulse_activation_peak_growth_factor",
                measured_value=peak_growth,
                warn=DEFAULT_PEAK_GROWTH_WARN,
                fail=DEFAULT_PEAK_GROWTH_FAIL,
                comparison="max",
                variant_id=variant_id,
                diagnostic_metadata={
                    "dt_ratio": float(factor),
                    "integration_timestep_ms": float(probe.integration_timestep_ms),
                    "max_supported_timestep_ms": float(probe.max_supported_timestep_ms),
                },
            )
        )

    findings.extend(_boundary_behavior_findings(case))
    findings.extend(_resolution_sensitivity_findings(case))
    return findings


def _boundary_behavior_findings(
    case: NumericalValidationCase,
) -> list[dict[str, Any]]:
    if len(case.boundary_variant_bundles) < 2:
        return []
    variants = {
        variant_id: _run_localized_pulse_probe(
            case=case,
            operator_bundle=bundle,
            integration_timestep_ms=case.integration_timestep_ms,
            shared_output_timestep_ms=case.shared_output_timestep_ms,
        )
        for variant_id, bundle in sorted(case.boundary_variant_bundles.items())
    }
    findings: list[dict[str, Any]] = []
    for variant_id, bundle in sorted(case.boundary_variant_bundles.items()):
        if bundle.boundary_condition_mode != CLAMPED_BOUNDARY_CONDITION_MODE:
            continue
        findings.append(
            _threshold_finding(
                validator_id=SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
                case=case,
                metric_id="boundary_vertex_activation_max_abs",
                measured_quantity="boundary_vertex_activation_max_abs",
                measured_value=float(variants[variant_id].boundary_activation_max_abs),
                warn=DEFAULT_BOUNDARY_CLAMP_WARN,
                fail=DEFAULT_BOUNDARY_CLAMP_FAIL,
                comparison="max",
                variant_id=variant_id,
                diagnostic_metadata={
                    "boundary_condition_mode": str(bundle.boundary_condition_mode),
                    "boundary_vertex_count": int(
                        np.count_nonzero(bundle.boundary_vertex_mask)
                    ),
                },
            )
        )
    reference_variant_id = "zero_flux" if "zero_flux" in variants else sorted(variants)[0]
    for variant_id in sorted(variants):
        if variant_id == reference_variant_id:
            continue
        reference_final = variants[reference_variant_id].final_activation
        variant_final = variants[variant_id].final_activation
        relative_difference = _relative_l2_difference(reference_final, variant_final)
        findings.append(
            _finding_record(
                validator_id=SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
                case=case,
                metric_id="boundary_variant_final_activation_relative_l2",
                measured_quantity="boundary_variant_final_activation_relative_l2",
                measured_value=relative_difference,
                comparison_basis={
                    "kind": "lower_bound",
                    "expected_min": DEFAULT_BOUNDARY_VARIANT_MIN_RELATIVE_DIFFERENCE,
                    "reference_variant_id": reference_variant_id,
                },
                status=(
                    VALIDATION_STATUS_PASS
                    if relative_difference
                    >= DEFAULT_BOUNDARY_VARIANT_MIN_RELATIVE_DIFFERENCE
                    else VALIDATION_STATUS_REVIEW
                ),
                variant_id=f"{reference_variant_id}_vs_{variant_id}",
                diagnostic_metadata={
                    "reference_variant_id": reference_variant_id,
                    "variant_id": variant_id,
                },
            )
        )
    return findings


def _resolution_sensitivity_findings(
    case: NumericalValidationCase,
) -> list[dict[str, Any]]:
    if case.coarse_operator_bundle is None:
        return []
    if not case.reference_operator_bundle.supports_patch_projection:
        return []
    fine_probe = _run_localized_pulse_probe(
        case=case,
        operator_bundle=case.reference_operator_bundle,
        integration_timestep_ms=case.integration_timestep_ms,
        shared_output_timestep_ms=case.shared_output_timestep_ms,
    )
    if fine_probe.patch_activation_history is None or fine_probe.final_patch_activation is None:
        return []
    initial_patch_state = SurfaceWaveState(
        resolution=SURFACE_STATE_RESOLUTION,
        activation=np.asarray(
            fine_probe.patch_activation_history[0],
            dtype=np.float64,
        ),
        velocity=np.zeros_like(
            np.asarray(fine_probe.patch_activation_history[0], dtype=np.float64)
        ),
    )
    coarse_probe = _run_explicit_state_probe(
        case=case,
        operator_bundle=case.coarse_operator_bundle,
        integration_timestep_ms=case.integration_timestep_ms,
        shared_output_timestep_ms=case.shared_output_timestep_ms,
        initial_state=initial_patch_state,
    )
    if coarse_probe.patch_activation_history is not None:
        raise AssertionError("coarse resolution probes should not expose a nested patch history.")
    final_error = _relative_l2_difference(
        fine_probe.final_patch_activation,
        coarse_probe.final_activation,
    )
    step_count = min(
        fine_probe.patch_activation_history.shape[0],
        coarse_probe.energy_history.shape[0],
    )
    max_error = 0.0
    for index in range(step_count):
        max_error = max(
            max_error,
            _relative_l2_difference(
                fine_probe.patch_activation_history[index],
                coarse_probe.final_activation
                if index >= coarse_probe.energy_history.shape[0]
                else _coarse_history_state(
                    case=case,
                    operator_bundle=case.coarse_operator_bundle,
                    integration_timestep_ms=case.integration_timestep_ms,
                    shared_output_timestep_ms=case.shared_output_timestep_ms,
                    initial_state=initial_patch_state,
                    target_step_index=index,
                ),
            ),
        )
    return [
        _threshold_finding(
            validator_id=SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
            case=case,
            metric_id="coarse_vs_fine_final_patch_relative_l2",
            measured_quantity="coarse_vs_fine_final_patch_relative_l2",
            measured_value=final_error,
            warn=DEFAULT_RESOLUTION_SENSITIVITY_WARN,
            fail=DEFAULT_RESOLUTION_SENSITIVITY_FAIL,
            comparison="max",
            diagnostic_metadata={
                "reference_resolution": "fine_projected_to_patch",
                "comparison_resolution": "coarse_operator",
            },
        ),
        _threshold_finding(
            validator_id=SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
            case=case,
            metric_id="coarse_vs_fine_max_patch_relative_l2",
            measured_quantity="coarse_vs_fine_max_patch_relative_l2",
            measured_value=max_error,
            warn=DEFAULT_RESOLUTION_SENSITIVITY_WARN,
            fail=DEFAULT_RESOLUTION_SENSITIVITY_FAIL,
            comparison="max",
            diagnostic_metadata={
                "reference_resolution": "fine_projected_to_patch",
                "comparison_resolution": "coarse_operator",
            },
        ),
    ]


def _coarse_history_state(
    *,
    case: NumericalValidationCase,
    operator_bundle: SurfaceWaveOperatorBundle,
    integration_timestep_ms: float | None,
    shared_output_timestep_ms: float | None,
    initial_state: SurfaceWaveState,
    target_step_index: int,
) -> np.ndarray:
    solver = _instantiate_solver(
        case=case,
        operator_bundle=operator_bundle,
        integration_timestep_ms=integration_timestep_ms,
        shared_output_timestep_ms=shared_output_timestep_ms,
    )
    solver.initialize_state(initial_state)
    if target_step_index == 0:
        return solver.state.activation.copy()
    for _ in range(target_step_index):
        solver.step()
    return solver.state.activation.copy()


def _run_localized_pulse_probe(
    *,
    case: NumericalValidationCase,
    operator_bundle: SurfaceWaveOperatorBundle,
    integration_timestep_ms: float | None,
    shared_output_timestep_ms: float | None,
) -> _ProbeResult:
    solver = _instantiate_solver(
        case=case,
        operator_bundle=operator_bundle,
        integration_timestep_ms=integration_timestep_ms,
        shared_output_timestep_ms=shared_output_timestep_ms,
    )
    initial_snapshot = solver.initialize_localized_pulse(
        seed_vertex=case.pulse_seed_vertex,
        amplitude=case.pulse_amplitude,
        support_radius_scale=case.pulse_support_radius_scale,
    )
    return _collect_probe_result(
        solver=solver,
        operator_bundle=operator_bundle,
        case=case,
        initial_snapshot=initial_snapshot,
    )


def _run_explicit_state_probe(
    *,
    case: NumericalValidationCase,
    operator_bundle: SurfaceWaveOperatorBundle,
    integration_timestep_ms: float | None,
    shared_output_timestep_ms: float | None,
    initial_state: SurfaceWaveState,
) -> _ProbeResult:
    solver = _instantiate_solver(
        case=case,
        operator_bundle=operator_bundle,
        integration_timestep_ms=integration_timestep_ms,
        shared_output_timestep_ms=shared_output_timestep_ms,
    )
    initial_snapshot = solver.initialize_state(initial_state)
    return _collect_probe_result(
        solver=solver,
        operator_bundle=operator_bundle,
        case=case,
        initial_snapshot=initial_snapshot,
    )


def _collect_probe_result(
    *,
    solver: SingleNeuronSurfaceWaveSolver,
    operator_bundle: SurfaceWaveOperatorBundle,
    case: NumericalValidationCase,
    initial_snapshot: Any,
) -> _ProbeResult:
    energy_history = [float(initial_snapshot.diagnostics.energy)]
    activation_peak_history = [
        float(initial_snapshot.diagnostics.activation_peak_abs)
    ]
    patch_history: list[np.ndarray] | None = None
    if operator_bundle.supports_patch_projection and operator_bundle.patch_count is not None:
        patch_history = [solver.current_patch_state().activation.copy()]
    boundary_max = 0.0
    if np.any(operator_bundle.boundary_vertex_mask):
        boundary_max = float(
            np.max(
                np.abs(
                    np.asarray(
                        initial_snapshot.state.activation[
                            operator_bundle.boundary_vertex_mask
                        ],
                        dtype=np.float64,
                    )
                )
            )
        )
    step_count = int(case.shared_step_count) * int(
        solver.runtime_metadata.internal_substep_count
    )
    for _ in range(step_count):
        snapshot = solver.step()
        energy_history.append(float(snapshot.diagnostics.energy))
        activation_peak_history.append(
            float(snapshot.diagnostics.activation_peak_abs)
        )
        if patch_history is not None:
            patch_history.append(solver.current_patch_state().activation.copy())
        if np.any(operator_bundle.boundary_vertex_mask):
            boundary_max = max(
                boundary_max,
                float(
                    np.max(
                        np.abs(
                            np.asarray(
                                snapshot.state.activation[
                                    operator_bundle.boundary_vertex_mask
                                ],
                                dtype=np.float64,
                            )
                        )
                    )
                ),
            )
    final_result = solver.finalize()
    return _ProbeResult(
        integration_timestep_ms=float(solver.runtime_metadata.integration_timestep_ms),
        shared_output_timestep_ms=float(
            solver.runtime_metadata.shared_output_timestep_ms
        ),
        max_supported_timestep_ms=float(
            solver.runtime_metadata.max_supported_integration_timestep_ms
        ),
        internal_substep_count=int(solver.runtime_metadata.internal_substep_count),
        energy_history=np.asarray(energy_history, dtype=np.float64),
        activation_peak_history=np.asarray(
            activation_peak_history,
            dtype=np.float64,
        ),
        patch_activation_history=(
            None
            if patch_history is None
            else np.asarray(patch_history, dtype=np.float64)
        ),
        final_activation=np.asarray(
            final_result.final_snapshot.state.activation,
            dtype=np.float64,
        ),
        final_patch_activation=(
            None
            if patch_history is None
            else np.asarray(patch_history[-1], dtype=np.float64)
        ),
        boundary_activation_max_abs=float(boundary_max),
    )


def _instantiate_solver(
    *,
    case: NumericalValidationCase,
    operator_bundle: SurfaceWaveOperatorBundle,
    integration_timestep_ms: float | None,
    shared_output_timestep_ms: float | None,
) -> SingleNeuronSurfaceWaveSolver:
    return SingleNeuronSurfaceWaveSolver(
        operator_bundle=operator_bundle,
        surface_wave_model=case.surface_wave_model,
        integration_timestep_ms=integration_timestep_ms,
        shared_output_timestep_ms=shared_output_timestep_ms,
    )


def _build_case_summary(
    case: NumericalValidationCase,
    findings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        **case.summary_mapping(),
        "overall_status": _worst_status(item["status"] for item in findings),
        "finding_ids": sorted(str(item["finding_id"]) for item in findings),
    }


def _group_findings_by_validator(
    findings: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for finding in findings:
        grouped.setdefault(str(finding["validator_id"]), []).append(
            copy.deepcopy(dict(finding))
        )
    return {
        validator_id: sorted(
            validator_findings,
            key=lambda item: item["finding_id"],
        )
        for validator_id, validator_findings in sorted(grouped.items())
    }


def _build_validator_summaries(
    findings_by_validator: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for validator_id, validator_findings in findings_by_validator.items():
        summaries[str(validator_id)] = {
            "validator_id": str(validator_id),
            "status": _worst_status(
                item["status"] for item in validator_findings
            ),
            "finding_count": len(validator_findings),
            "case_count": len(
                {str(item["case_id"]) for item in validator_findings}
            ),
            "status_counts": {
                VALIDATION_STATUS_PASS: sum(
                    1
                    for item in validator_findings
                    if item["status"] == VALIDATION_STATUS_PASS
                ),
                VALIDATION_STATUS_REVIEW: sum(
                    1
                    for item in validator_findings
                    if item["status"] == VALIDATION_STATUS_REVIEW
                ),
                VALIDATION_STATUS_BLOCKED: sum(
                    1
                    for item in validator_findings
                    if item["status"] == VALIDATION_STATUS_BLOCKED
                ),
                VALIDATION_STATUS_BLOCKING: sum(
                    1
                    for item in validator_findings
                    if item["status"] == VALIDATION_STATUS_BLOCKING
                ),
            },
        }
    return summaries


def _render_report_markdown(
    *,
    summary_payload: Mapping[str, Any],
    findings_by_validator: Mapping[str, Sequence[Mapping[str, Any]]],
) -> str:
    lines = [
        "# Numerical Validation Report",
        "",
        f"- Bundle ID: `{summary_payload['bundle_id']}`",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Case count: `{len(summary_payload['case_summaries'])}`",
        "",
        "## Validators",
        "",
        "| Validator | Status | Findings | Cases |",
        "| --- | --- | ---: | ---: |",
    ]
    validator_lookup = {
        item["validator_id"]: item
        for item in summary_payload["layers"][0]["validator_families"][0]["validators"]
    }
    for validator_id in sorted(findings_by_validator):
        summary = validator_lookup[validator_id]
        lines.append(
            f"| `{validator_id}` | `{summary['status']}` | {summary['finding_count']} | {summary['case_count']} |"
        )
    lines.extend(["", "## Findings", ""])
    for validator_id in sorted(findings_by_validator):
        lines.append(f"### `{validator_id}`")
        lines.append("")
        for finding in findings_by_validator[validator_id]:
            lines.append(
                f"- `{finding['status']}` `{finding['finding_id']}`: "
                f"`{finding['measured_quantity']}` = `{finding['measured_value']}` "
                f"for case `{finding['case_id']}`."
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _finding_record(
    *,
    validator_id: str,
    case: NumericalValidationCase,
    metric_id: str,
    measured_quantity: str,
    measured_value: Any,
    comparison_basis: Mapping[str, Any],
    status: str,
    diagnostic_metadata: Mapping[str, Any],
    variant_id: str | None = None,
) -> dict[str, Any]:
    finding_id = (
        f"{validator_id}:{case.case_id}:{metric_id}"
        if variant_id is None
        else f"{validator_id}:{case.case_id}:{variant_id}:{metric_id}"
    )
    return {
        "finding_id": finding_id,
        "validator_id": validator_id,
        "validator_family_id": NUMERICAL_STABILITY_FAMILY_ID,
        "layer_id": NUMERICAL_SANITY_LAYER_ID,
        "case_id": case.case_id,
        "arm_id": case.arm_id,
        "root_id": int(case.root_id),
        "variant_id": variant_id,
        "measured_quantity": measured_quantity,
        "measured_value": measured_value,
        "comparison_basis": copy.deepcopy(dict(comparison_basis)),
        "status": status,
        "diagnostic_metadata": copy.deepcopy(dict(diagnostic_metadata)),
    }


def _threshold_finding(
    *,
    validator_id: str,
    case: NumericalValidationCase,
    metric_id: str,
    measured_quantity: str,
    measured_value: float,
    warn: float,
    fail: float,
    comparison: str,
    diagnostic_metadata: Mapping[str, Any],
    variant_id: str | None = None,
) -> dict[str, Any]:
    status = _threshold_status(
        value=float(measured_value),
        warn=float(warn),
        fail=float(fail),
        comparison=comparison,
    )
    return _finding_record(
        validator_id=validator_id,
        case=case,
        metric_id=metric_id,
        measured_quantity=measured_quantity,
        measured_value=float(measured_value),
        comparison_basis={
            "kind": "threshold",
            "comparison": comparison,
            "warn": float(warn),
            "fail": float(fail),
        },
        status=status,
        diagnostic_metadata=diagnostic_metadata,
        variant_id=variant_id,
    )


def _threshold_status(
    *,
    value: float,
    warn: float,
    fail: float,
    comparison: str,
) -> str:
    if comparison == "max":
        if value > fail + _EPSILON:
            return VALIDATION_STATUS_BLOCKING
        if value > warn + _EPSILON:
            return VALIDATION_STATUS_REVIEW
        return VALIDATION_STATUS_PASS
    if value < fail - _EPSILON:
        return VALIDATION_STATUS_BLOCKING
    if value < warn - _EPSILON:
        return VALIDATION_STATUS_REVIEW
    return VALIDATION_STATUS_PASS


def _dt_variant_id(factor: float) -> str:
    return f"dt_ratio_{int(round(float(factor) * 100)):03d}"


def _worst_status(statuses: Sequence[str] | Any) -> str:
    resolved = list(statuses)
    if not resolved:
        return VALIDATION_STATUS_PASS
    return max(resolved, key=lambda item: _STATUS_RANK[str(item)])


def _growth_factor(values: np.ndarray) -> float:
    array = np.asarray(values, dtype=np.float64)
    initial = max(abs(float(array[0])), _EPSILON)
    return float(np.max(array) / initial)


def _relative_l2_difference(reference: np.ndarray, candidate: np.ndarray) -> float:
    ref = np.asarray(reference, dtype=np.float64)
    other = np.asarray(candidate, dtype=np.float64)
    return float(
        np.linalg.norm(ref - other) / max(np.linalg.norm(ref), _EPSILON)
    )


def _symmetry_residual_inf(matrix: sp.spmatrix) -> float:
    csr = matrix.tocsr().astype(np.float64)
    residual = (csr - csr.transpose()).tocsr()
    if residual.nnz == 0:
        return 0.0
    return float(np.max(np.abs(residual.data)))


def _smallest_eigenvalue(matrix: sp.spmatrix) -> float:
    csr = matrix.tocsr().astype(np.float64)
    if csr.shape[0] <= 8:
        return float(np.min(np.linalg.eigvalsh(csr.toarray())))
    return float(
        spla.eigsh(csr, k=1, which="SA", return_eigenvectors=False)[0]
    )


def _coarse_galerkin_residual_relative(bundle: SurfaceWaveOperatorBundle) -> float:
    assert bundle.coarse_operator is not None
    assert bundle.restriction is not None
    assert bundle.prolongation is not None
    residual = (
        bundle.restriction @ bundle.surface_operator @ bundle.prolongation
        - bundle.coarse_operator
    ).tocsr()
    numerator = (
        0.0 if residual.nnz == 0 else float(np.max(np.abs(residual.data)))
    )
    denominator = max(
        1.0,
        0.0
        if bundle.coarse_operator.nnz == 0
        else float(np.max(np.abs(bundle.coarse_operator.data))),
    )
    return numerator / denominator


def _transfer_constant_preservation_residual_inf(
    bundle: SurfaceWaveOperatorBundle,
) -> float:
    assert bundle.restriction is not None
    assert bundle.prolongation is not None
    surface_constant = np.ones(bundle.surface_vertex_count, dtype=np.float64)
    patch_count = int(bundle.patch_count or 0)
    patch_constant = np.ones(patch_count, dtype=np.float64)
    restrict_residual = np.asarray(
        bundle.restriction @ surface_constant,
        dtype=np.float64,
    ) - patch_constant
    prolong_residual = np.asarray(
        bundle.prolongation @ patch_constant,
        dtype=np.float64,
    ) - surface_constant
    return float(
        max(
            np.max(np.abs(restrict_residual)),
            np.max(np.abs(prolong_residual)),
        )
    )


__all__ = [
    "NUMERICAL_VALIDATION_PLAN_VERSION",
    "NUMERICAL_VALIDATION_REPORT_VERSION",
    "NumericalValidationCase",
    "execute_numerical_validation_workflow",
    "resolve_numerical_validation_plan",
    "run_numerical_validation_suite",
]
