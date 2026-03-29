from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse as sp

from .config import get_config_path, get_project_root, load_config
from .hybrid_morphology_contract import SURFACE_NEURON_CLASS
from .io_utils import ensure_dir, write_json
from .mixed_fidelity_inspection import execute_mixed_fidelity_inspection_workflow
from .simulation_planning import (
    resolve_manifest_mixed_fidelity_plan,
    resolve_manifest_simulation_plan,
)
from .simulator_execution import execute_manifest_simulation
from .simulator_result_contract import (
    discover_simulator_root_morphology_metadata,
    load_simulator_result_bundle_metadata,
    load_simulator_root_state_payload,
    load_simulator_shared_readout_payload,
)
from .surface_wave_solver import SingleNeuronSurfaceWaveSolver, SurfaceWaveOperatorBundle
from .validation_contract import (
    GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID,
    MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID,
    MORPHOLOGY_DEPENDENCE_FAMILY_ID,
    MORPHOLOGY_SANITY_LAYER_ID,
    VALIDATION_STATUS_BLOCKED,
    VALIDATION_STATUS_BLOCKING,
    VALIDATION_STATUS_PASS,
    VALIDATION_STATUS_REVIEW,
    build_validation_bundle_metadata,
    build_validation_contract_reference,
    build_validation_plan_reference,
    write_validation_bundle_metadata,
)
from .validation_planning import GEOMETRY_VARIANTS_SUITE_ID, normalize_validation_config


MORPHOLOGY_VALIDATION_PLAN_VERSION = "morphology_validation_plan.v1"
MORPHOLOGY_VALIDATION_REPORT_VERSION = "morphology_validation_suite.v1"

DEFAULT_LOCAL_SHARED_STEP_COUNT = 8
DEFAULT_PULSE_THRESHOLD_FRACTION = 0.20
_EPSILON = 1.0e-12

BOTTLENECK_EFFECT_COMPARISON_KIND = "bottleneck_effect"
BRANCHING_EFFECT_COMPARISON_KIND = "branching_effect"
SIMPLIFICATION_SENSITIVITY_COMPARISON_KIND = "simplification_sensitivity"
PATCHIFICATION_SENSITIVITY_COMPARISON_KIND = "patchification_sensitivity"
SHAPE_DEPENDENT_PROPAGATION_COMPARISON_KIND = "shape_dependent_propagation"
SUPPORTED_LOCAL_COMPARISON_KINDS = (
    BOTTLENECK_EFFECT_COMPARISON_KIND,
    BRANCHING_EFFECT_COMPARISON_KIND,
    SIMPLIFICATION_SENSITIVITY_COMPARISON_KIND,
    PATCHIFICATION_SENSITIVITY_COMPARISON_KIND,
)

_STATUS_RANK = {
    VALIDATION_STATUS_PASS: 0,
    VALIDATION_STATUS_REVIEW: 1,
    VALIDATION_STATUS_BLOCKED: 2,
    VALIDATION_STATUS_BLOCKING: 3,
}

_DEFAULT_MORPHOLOGY_CRITERIA_BY_VALIDATOR = {
    MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID: (
        "validation_criteria.morphology_dependence.mixed_fidelity_surrogate_preservation.v1"
    ),
    GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID: (
        "validation_criteria.morphology_dependence.geometry_dependence_collapse.v1"
    ),
}

_DEFAULT_LOCAL_THRESHOLDS: dict[str, dict[str, dict[str, Any]]] = {
    BOTTLENECK_EFFECT_COMPARISON_KIND: {
        "distal_arrival_delay_delta_ms": {
            "warn": 0.10,
            "fail": 0.02,
            "comparison": "min",
            "description": (
                "A bottlenecked variant should delay distal propagation relative "
                "to the matched open variant."
            ),
        },
        "distal_peak_attenuation_fraction": {
            "warn": 0.05,
            "fail": 0.01,
            "comparison": "min",
            "description": (
                "A bottlenecked variant should attenuate distal peak activation."
            ),
        },
    },
    BRANCHING_EFFECT_COMPARISON_KIND: {
        "final_energy_drop_fraction": {
            "warn": 0.01,
            "fail": 0.001,
            "comparison": "min",
            "description": (
                "Descriptor-scaled branching should reduce retained energy when "
                "branch complexity is present."
            ),
        },
        "branching_sink_l2_delta": {
            "warn": 1.0e-8,
            "fail": 1.0e-10,
            "comparison": "min",
            "description": (
                "Branch-aware damping should create a non-zero branching sink term."
            ),
        },
    },
    SIMPLIFICATION_SENSITIVITY_COMPARISON_KIND: {
        "focus_patch_trace_mae": {
            "warn": 0.10,
            "fail": 0.30,
            "comparison": "max",
            "description": (
                "Simplification should not materially change the localized patch "
                "trace on the matched semantic patch set."
            ),
        },
        "focus_patch_peak_abs_error": {
            "warn": 0.15,
            "fail": 0.40,
            "comparison": "max",
            "description": (
                "Simplification should preserve peak magnitude closely enough for "
                "review-level propagation comparisons."
            ),
        },
    },
    PATCHIFICATION_SENSITIVITY_COMPARISON_KIND: {
        "focus_patch_trace_mae": {
            "warn": 0.08,
            "fail": 0.20,
            "comparison": "max",
            "description": (
                "Changing the patch decomposition should not wildly perturb the "
                "matched semantic patch-set trace."
            ),
        },
        "focus_patch_peak_abs_error": {
            "warn": 0.12,
            "fail": 0.30,
            "comparison": "max",
            "description": (
                "Patchification changes should keep coarse peak readout error bounded."
            ),
        },
    },
}

_DEFAULT_GEOMETRY_TRACE_THRESHOLDS = {
    "projection_trace_relative_l2": {
        "warn": 0.10,
        "fail": 0.02,
        "comparison": "min",
        "description": (
            "The geometry-targeted variant should measurably change the root-local "
            "projection trace."
        ),
    },
    "shared_output_trace_relative_l2": {
        "warn": 0.05,
        "fail": 0.01,
        "comparison": "min",
        "description": (
            "The geometry-targeted variant should measurably change the shared "
            "readout trace."
        ),
    },
}


@dataclass(frozen=True)
class MorphologyProbeVariant:
    variant_id: str
    display_name: str
    root_id: int
    operator_bundle: SurfaceWaveOperatorBundle
    surface_wave_model: Mapping[str, Any]
    integration_timestep_ms: float = 0.20
    shared_step_count: int = DEFAULT_LOCAL_SHARED_STEP_COUNT
    pulse_seed_vertex: int | None = None
    pulse_amplitude: float = 1.0
    pulse_support_radius_scale: float = 1.5
    patch_sets: Mapping[str, Sequence[int]] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    diagnostic_tags: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        variant_id = str(self.variant_id).strip()
        if not variant_id:
            raise ValueError("MorphologyProbeVariant requires a non-empty variant_id.")
        if int(self.root_id) != int(self.operator_bundle.root_id):
            raise ValueError(
                "MorphologyProbeVariant root_id must match the operator bundle root_id."
            )
        if self.shared_step_count < 1:
            raise ValueError("shared_step_count must be positive.")
        if self.pulse_amplitude <= 0.0:
            raise ValueError("pulse_amplitude must be positive.")
        if self.pulse_support_radius_scale <= 0.0:
            raise ValueError("pulse_support_radius_scale must be positive.")
        patch_count = _infer_patch_count(self.operator_bundle)
        for label, indices in dict(self.patch_sets).items():
            normalized_label = str(label).strip()
            if not normalized_label:
                raise ValueError("patch_sets keys must be non-empty strings.")
            normalized_indices = tuple(int(index) for index in indices)
            if not normalized_indices:
                raise ValueError(
                    f"patch_sets[{normalized_label!r}] must contain at least one patch index."
                )
            if patch_count is not None:
                for index in normalized_indices:
                    if index < 0 or index >= patch_count:
                        raise ValueError(
                            f"patch_sets[{normalized_label!r}] contains invalid patch "
                            f"index {index!r} for patch_count {patch_count!r}."
                        )

    def summary_mapping(self) -> dict[str, Any]:
        return {
            "variant_id": str(self.variant_id),
            "display_name": str(self.display_name),
            "root_id": int(self.root_id),
            "integration_timestep_ms": float(self.integration_timestep_ms),
            "shared_step_count": int(self.shared_step_count),
            "pulse_seed_vertex": self.pulse_seed_vertex,
            "patch_sets": {
                str(label): [int(index) for index in indices]
                for label, indices in sorted(self.patch_sets.items())
            },
            "provenance": copy.deepcopy(dict(self.provenance)),
            "diagnostic_tags": copy.deepcopy(dict(self.diagnostic_tags)),
        }


@dataclass(frozen=True)
class MorphologyProbeComparisonCase:
    case_id: str
    comparison_kind: str
    reference_variant: MorphologyProbeVariant
    candidate_variant: MorphologyProbeVariant
    focus_patch_set_label: str | None = None
    localized_scope_label: str | None = None
    threshold_overrides: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    notes: str | None = None
    diagnostic_tags: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        case_id = str(self.case_id).strip()
        if not case_id:
            raise ValueError("MorphologyProbeComparisonCase requires a non-empty case_id.")
        if self.comparison_kind not in SUPPORTED_LOCAL_COMPARISON_KINDS:
            raise ValueError(
                "Unsupported morphology comparison_kind "
                f"{self.comparison_kind!r}."
            )
        if int(self.reference_variant.root_id) != int(self.candidate_variant.root_id):
            raise ValueError(
                "MorphologyProbeComparisonCase variants must target the same root_id."
            )
        if self.comparison_kind != BRANCHING_EFFECT_COMPARISON_KIND:
            focus_label = None if self.focus_patch_set_label is None else str(self.focus_patch_set_label)
            if not focus_label:
                raise ValueError(
                    f"{self.comparison_kind!r} comparisons require focus_patch_set_label."
                )
            if focus_label not in set(self.reference_variant.patch_sets):
                raise ValueError(
                    f"Reference variant is missing focus patch set {focus_label!r}."
                )
            if focus_label not in set(self.candidate_variant.patch_sets):
                raise ValueError(
                    f"Candidate variant is missing focus patch set {focus_label!r}."
                )

    @property
    def root_id(self) -> int:
        return int(self.reference_variant.root_id)

    @property
    def validator_id(self) -> str:
        return GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID

    def summary_mapping(self) -> dict[str, Any]:
        return {
            "case_id": str(self.case_id),
            "comparison_kind": str(self.comparison_kind),
            "root_id": int(self.root_id),
            "validator_id": self.validator_id,
            "reference_variant": self.reference_variant.summary_mapping(),
            "candidate_variant": self.candidate_variant.summary_mapping(),
            "focus_patch_set_label": self.focus_patch_set_label,
            "localized_scope_label": self.localized_scope_label,
            "notes": self.notes,
            "diagnostic_tags": copy.deepcopy(dict(self.diagnostic_tags)),
        }


@dataclass(frozen=True)
class GeometryTraceComparisonCase:
    case_id: str
    root_id: int
    reference_arm_id: str
    candidate_arm_id: str
    reference_metadata: Mapping[str, Any]
    candidate_metadata: Mapping[str, Any]
    threshold_overrides: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    notes: str | None = None
    diagnostic_tags: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        case_id = str(self.case_id).strip()
        if not case_id:
            raise ValueError("GeometryTraceComparisonCase requires a non-empty case_id.")

    @property
    def comparison_kind(self) -> str:
        return SHAPE_DEPENDENT_PROPAGATION_COMPARISON_KIND

    @property
    def validator_id(self) -> str:
        return GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID

    def summary_mapping(self) -> dict[str, Any]:
        return {
            "case_id": str(self.case_id),
            "comparison_kind": self.comparison_kind,
            "root_id": int(self.root_id),
            "validator_id": self.validator_id,
            "reference_arm_id": str(self.reference_arm_id),
            "candidate_arm_id": str(self.candidate_arm_id),
            "notes": self.notes,
            "diagnostic_tags": copy.deepcopy(dict(self.diagnostic_tags)),
        }


@dataclass(frozen=True)
class _VariantProbeResult:
    time_ms: np.ndarray
    patch_activation_history: np.ndarray
    energy_history: np.ndarray
    activation_peak_history: np.ndarray
    branching_sink_history: np.ndarray


def resolve_morphology_validation_plan(
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
    active_validator_ids = _resolve_active_morphology_validator_ids(validation_config)
    criteria_assignments = _resolve_morphology_criteria_assignments(
        validation_config=validation_config,
        active_validator_ids=active_validator_ids,
    )
    geometry_variant_ids = _resolve_geometry_variant_ids(
        simulation_plan=simulation_plan,
        validation_config=validation_config,
        active_validator_ids=active_validator_ids,
    )
    plan_reference = build_validation_plan_reference(
        experiment_id=str(simulation_plan["manifest_reference"]["experiment_id"]),
        contract_reference=build_validation_contract_reference(),
        active_layer_ids=[MORPHOLOGY_SANITY_LAYER_ID],
        active_validator_family_ids=[MORPHOLOGY_DEPENDENCE_FAMILY_ID],
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
            []
            if not geometry_variant_ids
            else [
                {
                    "suite_id": GEOMETRY_VARIANTS_SUITE_ID,
                    "suite_kind": "geometry_variant_pairing",
                    "target_layer_ids": [MORPHOLOGY_SANITY_LAYER_ID],
                    "target_validator_ids": [GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID],
                    "variant_ids": list(geometry_variant_ids),
                }
            ]
        ),
        plan_version=MORPHOLOGY_VALIDATION_PLAN_VERSION,
    )
    bundle_metadata = build_validation_bundle_metadata(
        validation_plan_reference=plan_reference,
        processed_simulator_results_dir=cfg["paths"]["processed_simulator_results_dir"],
    )
    return {
        "plan_version": MORPHOLOGY_VALIDATION_PLAN_VERSION,
        "manifest_reference": copy.deepcopy(dict(simulation_plan["manifest_reference"])),
        "validation_config": validation_config,
        "config_reference": {
            "config_path": str(config_file.resolve()),
            "project_root": str(project_root.resolve()),
        },
        "active_layer_ids": [MORPHOLOGY_SANITY_LAYER_ID],
        "active_validator_family_ids": [MORPHOLOGY_DEPENDENCE_FAMILY_ID],
        "active_validator_ids": list(active_validator_ids),
        "criteria_profile_assignments": criteria_assignments,
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


def run_morphology_validation_suite(
    *,
    probe_cases: Sequence[MorphologyProbeComparisonCase] = (),
    geometry_trace_cases: Sequence[GeometryTraceComparisonCase] = (),
    mixed_fidelity_summaries: Sequence[Mapping[str, Any]] = (),
    validation_plan_reference: Mapping[str, Any] | None = None,
    bundle_metadata: Mapping[str, Any] | None = None,
    processed_simulator_results_dir: str | Path | None = None,
    experiment_id: str = "fixture_morphology_validation",
) -> dict[str, Any]:
    normalized_probe_cases = _normalize_probe_cases(probe_cases)
    normalized_geometry_cases = _normalize_geometry_trace_cases(geometry_trace_cases)
    normalized_mixed_summaries = [
        copy.deepcopy(dict(item)) for item in mixed_fidelity_summaries
    ]
    if not normalized_probe_cases and not normalized_geometry_cases and not normalized_mixed_summaries:
        raise ValueError("Morphology validation requires at least one comparison case or mixed-fidelity summary.")

    resolved_bundle_metadata = _resolve_bundle_metadata(
        validation_plan_reference=validation_plan_reference,
        bundle_metadata=bundle_metadata,
        processed_simulator_results_dir=processed_simulator_results_dir,
        experiment_id=experiment_id,
        probe_cases=normalized_probe_cases,
        geometry_trace_cases=normalized_geometry_cases,
        mixed_fidelity_summaries=normalized_mixed_summaries,
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
    for case in normalized_probe_cases:
        case_findings = _evaluate_probe_case(case)
        findings.extend(case_findings)
        case_summaries.append(_build_case_summary(case.summary_mapping(), case_findings))
    for case in normalized_geometry_cases:
        case_findings = _evaluate_geometry_trace_case(case)
        findings.extend(case_findings)
        case_summaries.append(_build_case_summary(case.summary_mapping(), case_findings))
    for summary in normalized_mixed_summaries:
        mixed_findings, mixed_case_summaries = _evaluate_mixed_fidelity_summary(summary)
        findings.extend(mixed_findings)
        case_summaries.extend(mixed_case_summaries)

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
        "report_version": MORPHOLOGY_VALIDATION_REPORT_VERSION,
        "bundle_id": str(resolved_bundle_metadata["bundle_id"]),
        "experiment_id": str(resolved_bundle_metadata["experiment_id"]),
        "validation_spec_hash": str(resolved_bundle_metadata["validation_spec_hash"]),
        "overall_status": overall_status,
        "active_layer_ids": [MORPHOLOGY_SANITY_LAYER_ID],
        "active_validator_family_ids": [MORPHOLOGY_DEPENDENCE_FAMILY_ID],
        "active_validator_ids": sorted(findings_by_validator),
        "status_counts": status_counts,
        "layers": [
            {
                "layer_id": MORPHOLOGY_SANITY_LAYER_ID,
                "status": layer_status,
                "validator_families": [
                    {
                        "validator_family_id": MORPHOLOGY_DEPENDENCE_FAMILY_ID,
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
        "report_version": MORPHOLOGY_VALIDATION_REPORT_VERSION,
        "bundle_id": str(resolved_bundle_metadata["bundle_id"]),
        "validator_findings": findings_by_validator,
    }
    review_handoff_payload = {
        "format_version": "json_validation_review_handoff.v1",
        "report_version": MORPHOLOGY_VALIDATION_REPORT_VERSION,
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
        "report_version": MORPHOLOGY_VALIDATION_REPORT_VERSION,
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


def execute_morphology_validation_workflow(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    arm_ids: Sequence[str] | None = None,
    reference_root_specs: Sequence[str | Mapping[str, Any]] | None = None,
    mixed_fidelity_thresholds: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    plan = resolve_morphology_validation_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        arm_ids=arm_ids,
    )
    simulation_plan = resolve_manifest_simulation_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    target_arm_ids = set(plan["target_arm_ids"])
    target_arm_plans = [
        copy.deepcopy(dict(arm_plan))
        for arm_plan in simulation_plan["arm_plans"]
        if str(arm_plan["arm_reference"]["arm_id"]) in target_arm_ids
        and str(arm_plan["arm_reference"]["model_mode"]) == "surface_wave"
    ]

    geometry_trace_cases: list[GeometryTraceComparisonCase] = []
    if GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID in set(plan["active_validator_ids"]):
        geometry_trace_cases = _build_geometry_trace_cases_from_manifest(
            manifest_path=manifest_path,
            config_path=config_path,
            schema_path=schema_path,
            design_lock_path=design_lock_path,
            arm_plans=target_arm_plans,
        )

    mixed_fidelity_summaries: list[dict[str, Any]] = []
    if MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID in set(plan["active_validator_ids"]):
        for arm_plan in target_arm_plans:
            arm_id = str(arm_plan["arm_reference"]["arm_id"])
            resolved_reference_root_specs = (
                list(reference_root_specs)
                if reference_root_specs is not None
                else _derive_policy_reference_root_specs(
                    manifest_path=manifest_path,
                    config_path=config_path,
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                    arm_id=arm_id,
                )
            )
            if not resolved_reference_root_specs:
                continue
            summary = execute_mixed_fidelity_inspection_workflow(
                manifest_path=manifest_path,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
                arm_id=arm_id,
                reference_root_specs=resolved_reference_root_specs,
                thresholds=mixed_fidelity_thresholds,
            )
            mixed_fidelity_summaries.append(summary)

    if not geometry_trace_cases and not mixed_fidelity_summaries:
        raise ValueError(
            "Morphology validation resolved no actionable comparison cases. "
            "Provide an intact/shuffled surface-wave pair or explicit "
            "mixed-fidelity reference_root_specs."
        )

    result = run_morphology_validation_suite(
        geometry_trace_cases=geometry_trace_cases,
        mixed_fidelity_summaries=mixed_fidelity_summaries,
        validation_plan_reference=plan["validation_plan_reference"],
        bundle_metadata=plan["validation_bundle"]["metadata"],
    )
    return {
        **result,
        "morphology_validation_plan": plan,
    }


def _normalize_probe_cases(
    cases: Sequence[MorphologyProbeComparisonCase],
) -> list[MorphologyProbeComparisonCase]:
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
        raise ValueError("probe_cases must be a sequence of MorphologyProbeComparisonCase instances.")
    normalized: list[MorphologyProbeComparisonCase] = []
    seen_case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, MorphologyProbeComparisonCase):
            raise ValueError(
                "probe_cases must contain MorphologyProbeComparisonCase instances."
            )
        if case.case_id in seen_case_ids:
            raise ValueError(f"Duplicate probe case_id {case.case_id!r}.")
        seen_case_ids.add(case.case_id)
        normalized.append(case)
    return sorted(normalized, key=lambda item: item.case_id)


def _normalize_geometry_trace_cases(
    cases: Sequence[GeometryTraceComparisonCase],
) -> list[GeometryTraceComparisonCase]:
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
        raise ValueError("geometry_trace_cases must be a sequence of GeometryTraceComparisonCase instances.")
    normalized: list[GeometryTraceComparisonCase] = []
    seen_case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, GeometryTraceComparisonCase):
            raise ValueError(
                "geometry_trace_cases must contain GeometryTraceComparisonCase instances."
            )
        if case.case_id in seen_case_ids:
            raise ValueError(f"Duplicate geometry trace case_id {case.case_id!r}.")
        seen_case_ids.add(case.case_id)
        normalized.append(case)
    return sorted(normalized, key=lambda item: item.case_id)


def _resolve_bundle_metadata(
    *,
    validation_plan_reference: Mapping[str, Any] | None,
    bundle_metadata: Mapping[str, Any] | None,
    processed_simulator_results_dir: str | Path | None,
    experiment_id: str,
    probe_cases: Sequence[MorphologyProbeComparisonCase],
    geometry_trace_cases: Sequence[GeometryTraceComparisonCase],
    mixed_fidelity_summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if bundle_metadata is not None:
        return copy.deepcopy(dict(bundle_metadata))
    if validation_plan_reference is None:
        validation_plan_reference = _default_plan_reference_for_suite(
            experiment_id=experiment_id,
            probe_cases=probe_cases,
            geometry_trace_cases=geometry_trace_cases,
            mixed_fidelity_summaries=mixed_fidelity_summaries,
        )
    return build_validation_bundle_metadata(
        validation_plan_reference=validation_plan_reference,
        processed_simulator_results_dir=(
            processed_simulator_results_dir
            if processed_simulator_results_dir is not None
            else Path("data/processed/simulator_results")
        ),
    )


def _default_plan_reference_for_suite(
    *,
    experiment_id: str,
    probe_cases: Sequence[MorphologyProbeComparisonCase],
    geometry_trace_cases: Sequence[GeometryTraceComparisonCase],
    mixed_fidelity_summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    active_validator_ids: list[str] = []
    if probe_cases or geometry_trace_cases:
        active_validator_ids.append(GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID)
    if mixed_fidelity_summaries:
        active_validator_ids.append(MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID)
    criteria_assignments = [
        {
            "validator_id": validator_id,
            "criteria_profile_reference": _DEFAULT_MORPHOLOGY_CRITERIA_BY_VALIDATOR[
                validator_id
            ],
        }
        for validator_id in active_validator_ids
    ]
    target_arm_ids = sorted(
        {
            str(case.reference_arm_id)
            for case in geometry_trace_cases
        }
        | {
            str(case.candidate_arm_id)
            for case in geometry_trace_cases
        }
        | {
            str(summary.get("arm_id"))
            for summary in mixed_fidelity_summaries
            if summary.get("arm_id") is not None
        }
    )
    variant_ids = sorted(
        {
            str(case.reference_variant.variant_id)
            for case in probe_cases
        }
        | {
            str(case.candidate_variant.variant_id)
            for case in probe_cases
        }
    )
    return build_validation_plan_reference(
        experiment_id=experiment_id,
        contract_reference=build_validation_contract_reference(),
        active_layer_ids=[MORPHOLOGY_SANITY_LAYER_ID],
        active_validator_family_ids=[MORPHOLOGY_DEPENDENCE_FAMILY_ID],
        active_validator_ids=active_validator_ids,
        criteria_profile_references=[
            item["criteria_profile_reference"] for item in criteria_assignments
        ],
        evidence_bundle_references={},
        target_arm_ids=target_arm_ids,
        comparison_group_ids=[],
        criteria_profile_assignments=criteria_assignments,
        perturbation_suite_references=(
            []
            if not variant_ids
            else [
                {
                    "suite_id": GEOMETRY_VARIANTS_SUITE_ID,
                    "suite_kind": "local_morphology_variants",
                    "target_layer_ids": [MORPHOLOGY_SANITY_LAYER_ID],
                    "target_validator_ids": [GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID],
                    "variant_ids": variant_ids,
                }
            ]
        ),
        plan_version=MORPHOLOGY_VALIDATION_PLAN_VERSION,
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
        raise ValueError("No surface-wave arms were available for morphology validation.")
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
    if active_layer_ids and MORPHOLOGY_SANITY_LAYER_ID not in set(active_layer_ids):
        raise ValueError(
            "validation.active_layer_ids excludes morphology_sanity, so the morphology "
            "validation workflow has no active layer to execute."
        )
    return requested_arm_ids


def _resolve_active_morphology_validator_ids(
    validation_config: Mapping[str, Any],
) -> list[str]:
    morphology_validator_ids = [
        MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID,
        GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID,
    ]
    requested_validator_ids = list(validation_config["active_validator_ids"])
    if requested_validator_ids:
        active = [
            validator_id
            for validator_id in morphology_validator_ids
            if validator_id in set(requested_validator_ids)
        ]
        if not active:
            raise ValueError(
                "validation.active_validator_ids excludes the morphology validators "
                "required by the morphology validation workflow."
            )
        return active
    requested_family_ids = list(validation_config["active_validator_family_ids"])
    if requested_family_ids and MORPHOLOGY_DEPENDENCE_FAMILY_ID not in set(
        requested_family_ids
    ):
        raise ValueError(
            "validation.active_validator_family_ids excludes morphology_dependence, so "
            "the morphology validation workflow has no active validators to execute."
        )
    return morphology_validator_ids


def _resolve_morphology_criteria_assignments(
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
        elif MORPHOLOGY_DEPENDENCE_FAMILY_ID in family_overrides:
            reference = family_overrides[MORPHOLOGY_DEPENDENCE_FAMILY_ID]
            source = "validator_family_override"
        elif MORPHOLOGY_SANITY_LAYER_ID in layer_overrides:
            reference = layer_overrides[MORPHOLOGY_SANITY_LAYER_ID]
            source = "layer_override"
        else:
            reference = _DEFAULT_MORPHOLOGY_CRITERIA_BY_VALIDATOR[validator_id]
            source = "validator_contract_default"
        assignments.append(
            {
                "validator_id": validator_id,
                "criteria_profile_reference": str(reference),
                "criteria_profile_source": source,
            }
        )
    return sorted(assignments, key=lambda item: item["validator_id"])


def _derive_policy_reference_root_specs(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    arm_id: str,
) -> list[dict[str, Any]]:
    mixed_fidelity_plan = resolve_manifest_mixed_fidelity_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        arm_id=arm_id,
    )
    resolved: dict[int, dict[str, Any]] = {}
    for assignment in mixed_fidelity_plan["per_root_assignments"]:
        policy_evaluation = dict(assignment.get("policy_evaluation", {}))
        if not bool(policy_evaluation.get("promotion_recommended")):
            continue
        reference_class = policy_evaluation.get("recommended_morphology_class")
        if reference_class is None:
            continue
        root_id = int(assignment["root_id"])
        resolved[root_id] = {
            "root_id": root_id,
            "reference_morphology_class": str(reference_class),
            "reference_source": "policy_recommendation",
        }
    return [resolved[root_id] for root_id in sorted(resolved)]


def _resolve_geometry_variant_ids(
    *,
    simulation_plan: Mapping[str, Any],
    validation_config: Mapping[str, Any],
    active_validator_ids: Sequence[str],
) -> list[str]:
    if GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID not in set(active_validator_ids):
        return []
    suite_config = validation_config["perturbation_suites"][GEOMETRY_VARIANTS_SUITE_ID]
    if not bool(suite_config["enabled"]):
        return []
    configured_variant_ids = list(suite_config["variant_ids"])
    if configured_variant_ids:
        return configured_variant_ids
    discovered = {
        str(arm_plan.get("topology_condition", ""))
        for arm_plan in simulation_plan["arm_plans"]
        if str(arm_plan["arm_reference"]["model_mode"]) == "surface_wave"
        and str(arm_plan.get("topology_condition", "")).strip()
    }
    ordering = {"intact": 0, "shuffled": 1}
    return sorted(discovered, key=lambda item: (ordering.get(item, 99), item))


def _build_geometry_trace_cases_from_manifest(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    arm_plans: Sequence[Mapping[str, Any]],
) -> list[GeometryTraceComparisonCase]:
    arm_plan_by_topology = {
        str(arm_plan.get("topology_condition")): arm_plan
        for arm_plan in arm_plans
        if str(arm_plan.get("topology_condition", "")).strip()
    }
    intact_plan = arm_plan_by_topology.get("intact")
    shuffled_plan = arm_plan_by_topology.get("shuffled")
    if intact_plan is None or shuffled_plan is None:
        return []
    intact_metadata = _load_or_execute_arm_metadata(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        arm_plan=intact_plan,
    )
    shuffled_metadata = _load_or_execute_arm_metadata(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        arm_plan=shuffled_plan,
    )
    intact_root_records = {
        int(item["root_id"]): item
        for item in discover_simulator_root_morphology_metadata(intact_metadata)
    }
    shuffled_root_records = {
        int(item["root_id"]): item
        for item in discover_simulator_root_morphology_metadata(shuffled_metadata)
    }
    comparable_surface_root_ids = sorted(
        root_id
        for root_id, record in intact_root_records.items()
        if root_id in shuffled_root_records
        and str(record.get("morphology_class")) == SURFACE_NEURON_CLASS
        and str(shuffled_root_records[root_id].get("morphology_class"))
        == SURFACE_NEURON_CLASS
    )
    return [
        GeometryTraceComparisonCase(
            case_id=(
                f"{intact_plan['arm_reference']['arm_id']}__vs__"
                f"{shuffled_plan['arm_reference']['arm_id']}__root_{int(root_id)}"
            ),
            root_id=int(root_id),
            reference_arm_id=str(intact_plan["arm_reference"]["arm_id"]),
            candidate_arm_id=str(shuffled_plan["arm_reference"]["arm_id"]),
            reference_metadata=intact_metadata,
            candidate_metadata=shuffled_metadata,
            notes="Matched intact-versus-shuffled surface-wave arm comparison.",
            diagnostic_tags={
                "topology_reference": "intact",
                "topology_candidate": "shuffled",
            },
        )
        for root_id in comparable_surface_root_ids
    ]


def _load_or_execute_arm_metadata(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    arm_plan: Mapping[str, Any],
) -> dict[str, Any]:
    result_bundle = dict(arm_plan["result_bundle"])
    metadata = copy.deepcopy(dict(result_bundle["metadata"]))
    metadata_path = Path(metadata["artifacts"]["metadata_json"]["path"]).resolve()
    if metadata_path.exists():
        return load_simulator_result_bundle_metadata(metadata_path)
    arm_id = str(arm_plan["arm_reference"]["arm_id"])
    execution_summary = execute_manifest_simulation(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        model_mode="surface_wave",
        arm_id=arm_id,
    )
    if int(execution_summary["executed_run_count"]) != 1:
        raise ValueError(
            f"Morphology validation expected one executed run for arm {arm_id!r}."
        )
    run_summary = dict(execution_summary["executed_runs"][0])
    return load_simulator_result_bundle_metadata(run_summary["metadata_path"])


def _evaluate_probe_case(
    case: MorphologyProbeComparisonCase,
) -> list[dict[str, Any]]:
    reference_probe = _run_local_variant_probe(case.reference_variant)
    candidate_probe = _run_local_variant_probe(case.candidate_variant)
    thresholds = _resolve_local_thresholds(
        comparison_kind=case.comparison_kind,
        overrides=case.threshold_overrides,
    )
    if case.comparison_kind == BOTTLENECK_EFFECT_COMPARISON_KIND:
        return _evaluate_bottleneck_case(
            case=case,
            reference_probe=reference_probe,
            candidate_probe=candidate_probe,
            thresholds=thresholds,
        )
    if case.comparison_kind == BRANCHING_EFFECT_COMPARISON_KIND:
        return _evaluate_branching_case(
            case=case,
            reference_probe=reference_probe,
            candidate_probe=candidate_probe,
            thresholds=thresholds,
        )
    return _evaluate_sensitivity_case(
        case=case,
        reference_probe=reference_probe,
        candidate_probe=candidate_probe,
        thresholds=thresholds,
    )


def _run_local_variant_probe(
    variant: MorphologyProbeVariant,
) -> _VariantProbeResult:
    solver = SingleNeuronSurfaceWaveSolver(
        operator_bundle=variant.operator_bundle,
        surface_wave_model=variant.surface_wave_model,
        integration_timestep_ms=variant.integration_timestep_ms,
    )
    initial_snapshot = solver.initialize_localized_pulse(
        seed_vertex=variant.pulse_seed_vertex,
        amplitude=variant.pulse_amplitude,
        support_radius_scale=variant.pulse_support_radius_scale,
    )
    time_ms = [float(initial_snapshot.time_ms)]
    patch_history = [
        _project_surface_activation_to_patch(
            variant.operator_bundle,
            np.asarray(initial_snapshot.state.activation, dtype=np.float64),
        )
    ]
    energy_history = [float(initial_snapshot.diagnostics.energy)]
    peak_history = [float(initial_snapshot.diagnostics.activation_peak_abs)]
    branching_sink_history = [float(initial_snapshot.diagnostics.branching_sink_l2)]
    for _ in range(int(variant.shared_step_count)):
        snapshot = solver.step()
        time_ms.append(float(snapshot.time_ms))
        patch_history.append(
            _project_surface_activation_to_patch(
                variant.operator_bundle,
                np.asarray(snapshot.state.activation, dtype=np.float64),
            )
        )
        energy_history.append(float(snapshot.diagnostics.energy))
        peak_history.append(float(snapshot.diagnostics.activation_peak_abs))
        branching_sink_history.append(float(snapshot.diagnostics.branching_sink_l2))
    return _VariantProbeResult(
        time_ms=np.asarray(time_ms, dtype=np.float64),
        patch_activation_history=np.asarray(patch_history, dtype=np.float64),
        energy_history=np.asarray(energy_history, dtype=np.float64),
        activation_peak_history=np.asarray(peak_history, dtype=np.float64),
        branching_sink_history=np.asarray(branching_sink_history, dtype=np.float64),
    )


def _evaluate_bottleneck_case(
    *,
    case: MorphologyProbeComparisonCase,
    reference_probe: _VariantProbeResult,
    candidate_probe: _VariantProbeResult,
    thresholds: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    focus_label = str(case.focus_patch_set_label)
    reference_trace = _semantic_patch_trace(reference_probe, case.reference_variant, focus_label)
    candidate_trace = _semantic_patch_trace(candidate_probe, case.candidate_variant, focus_label)
    reference_peak = float(np.max(np.abs(reference_trace)))
    candidate_peak = float(np.max(np.abs(candidate_trace)))
    reference_arrival = _first_crossing_time_ms(
        reference_probe.time_ms,
        reference_trace,
    )
    candidate_arrival = _first_crossing_time_ms(
        candidate_probe.time_ms,
        candidate_trace,
    )
    diagnostics = _local_case_diagnostics(
        case=case,
        focus_label=focus_label,
        reference_trace=reference_trace,
        candidate_trace=candidate_trace,
    )
    findings: list[dict[str, Any]] = []
    if reference_arrival is None or candidate_arrival is None:
        findings.append(
            _probe_finding_record(
                case=case,
                metric_id="distal_arrival_delay_delta_ms",
                measured_quantity="distal_arrival_delay_delta_ms",
                measured_value=None,
                comparison_basis={
                    "kind": "blocked_by_missing_arrival",
                    "focus_patch_set_label": focus_label,
                },
                status=VALIDATION_STATUS_BLOCKED,
                diagnostic_metadata={
                    **diagnostics,
                    "reference_arrival_ms": reference_arrival,
                    "candidate_arrival_ms": candidate_arrival,
                },
            )
        )
    else:
        findings.append(
            _probe_threshold_finding(
                case=case,
                metric_id="distal_arrival_delay_delta_ms",
                measured_quantity="distal_arrival_delay_delta_ms",
                measured_value=float(candidate_arrival - reference_arrival),
                threshold=dict(thresholds["distal_arrival_delay_delta_ms"]),
                diagnostic_metadata={
                    **diagnostics,
                    "reference_arrival_ms": float(reference_arrival),
                    "candidate_arrival_ms": float(candidate_arrival),
                },
            )
        )
    attenuation_fraction = 0.0
    if reference_peak > _EPSILON:
        attenuation_fraction = float(1.0 - candidate_peak / reference_peak)
    findings.append(
        _probe_threshold_finding(
            case=case,
            metric_id="distal_peak_attenuation_fraction",
            measured_quantity="distal_peak_attenuation_fraction",
            measured_value=attenuation_fraction,
            threshold=dict(thresholds["distal_peak_attenuation_fraction"]),
            diagnostic_metadata={
                **diagnostics,
                "reference_peak_abs": reference_peak,
                "candidate_peak_abs": candidate_peak,
            },
        )
    )
    return sorted(findings, key=lambda item: item["finding_id"])


def _evaluate_branching_case(
    *,
    case: MorphologyProbeComparisonCase,
    reference_probe: _VariantProbeResult,
    candidate_probe: _VariantProbeResult,
    thresholds: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    reference_energy = float(reference_probe.energy_history[-1])
    candidate_energy = float(candidate_probe.energy_history[-1])
    energy_drop_fraction = 0.0
    if reference_energy > _EPSILON:
        energy_drop_fraction = float(1.0 - candidate_energy / reference_energy)
    diagnostics = {
        "reference_variant": case.reference_variant.summary_mapping(),
        "candidate_variant": case.candidate_variant.summary_mapping(),
        "reference_final_energy": reference_energy,
        "candidate_final_energy": candidate_energy,
        "reference_final_branching_sink_l2": float(reference_probe.branching_sink_history[-1]),
        "candidate_final_branching_sink_l2": float(candidate_probe.branching_sink_history[-1]),
        "localized_scope_label": case.localized_scope_label,
        "diagnostic_tags": copy.deepcopy(dict(case.diagnostic_tags)),
    }
    return sorted(
        [
            _probe_threshold_finding(
                case=case,
                metric_id="final_energy_drop_fraction",
                measured_quantity="final_energy_drop_fraction",
                measured_value=energy_drop_fraction,
                threshold=dict(thresholds["final_energy_drop_fraction"]),
                diagnostic_metadata=diagnostics,
            ),
            _probe_threshold_finding(
                case=case,
                metric_id="branching_sink_l2_delta",
                measured_quantity="branching_sink_l2_delta",
                measured_value=float(
                    candidate_probe.branching_sink_history[-1]
                    - reference_probe.branching_sink_history[-1]
                ),
                threshold=dict(thresholds["branching_sink_l2_delta"]),
                diagnostic_metadata=diagnostics,
            ),
        ],
        key=lambda item: item["finding_id"],
    )


def _evaluate_sensitivity_case(
    *,
    case: MorphologyProbeComparisonCase,
    reference_probe: _VariantProbeResult,
    candidate_probe: _VariantProbeResult,
    thresholds: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    focus_label = str(case.focus_patch_set_label)
    reference_trace = _semantic_patch_trace(reference_probe, case.reference_variant, focus_label)
    candidate_trace = _semantic_patch_trace(candidate_probe, case.candidate_variant, focus_label)
    diagnostics = _local_case_diagnostics(
        case=case,
        focus_label=focus_label,
        reference_trace=reference_trace,
        candidate_trace=candidate_trace,
    )
    return sorted(
        [
            _probe_threshold_finding(
                case=case,
                metric_id="focus_patch_trace_mae",
                measured_quantity="focus_patch_trace_mae",
                measured_value=float(np.mean(np.abs(reference_trace - candidate_trace))),
                threshold=dict(thresholds["focus_patch_trace_mae"]),
                diagnostic_metadata=diagnostics,
            ),
            _probe_threshold_finding(
                case=case,
                metric_id="focus_patch_peak_abs_error",
                measured_quantity="focus_patch_peak_abs_error",
                measured_value=float(
                    abs(
                        np.max(np.abs(reference_trace))
                        - np.max(np.abs(candidate_trace))
                    )
                ),
                threshold=dict(thresholds["focus_patch_peak_abs_error"]),
                diagnostic_metadata=diagnostics,
            ),
        ],
        key=lambda item: item["finding_id"],
    )


def _evaluate_geometry_trace_case(
    case: GeometryTraceComparisonCase,
) -> list[dict[str, Any]]:
    thresholds = copy.deepcopy(_DEFAULT_GEOMETRY_TRACE_THRESHOLDS)
    for metric_name, override in dict(case.threshold_overrides).items():
        if isinstance(override, Mapping):
            thresholds.setdefault(metric_name, {})
            thresholds[metric_name].update(copy.deepcopy(dict(override)))
    reference_root_payload = load_simulator_root_state_payload(
        case.reference_metadata,
        root_id=int(case.root_id),
    )
    candidate_root_payload = load_simulator_root_state_payload(
        case.candidate_metadata,
        root_id=int(case.root_id),
    )
    reference_shared_payload = load_simulator_shared_readout_payload(case.reference_metadata)
    candidate_shared_payload = load_simulator_shared_readout_payload(case.candidate_metadata)

    projection_time_ms, reference_projection, candidate_projection = _align_series(
        time_ms_a=np.asarray(reference_root_payload["projection_time_ms"], dtype=np.float64),
        values_a=np.mean(np.asarray(reference_root_payload["projection_trace"], dtype=np.float64), axis=1),
        time_ms_b=np.asarray(candidate_root_payload["projection_time_ms"], dtype=np.float64),
        values_b=np.mean(np.asarray(candidate_root_payload["projection_trace"], dtype=np.float64), axis=1),
    )
    shared_time_ms, reference_shared, candidate_shared = _align_series(
        time_ms_a=np.asarray(reference_shared_payload["time_ms"], dtype=np.float64),
        values_a=_select_first_shared_trace(reference_shared_payload),
        time_ms_b=np.asarray(candidate_shared_payload["time_ms"], dtype=np.float64),
        values_b=_select_first_shared_trace(candidate_shared_payload),
    )
    diagnostics = {
        "reference_arm_id": str(case.reference_arm_id),
        "candidate_arm_id": str(case.candidate_arm_id),
        "reference_bundle_id": str(case.reference_metadata["bundle_id"]),
        "candidate_bundle_id": str(case.candidate_metadata["bundle_id"]),
        "reference_morphology_class": str(reference_root_payload["morphology_class"]),
        "candidate_morphology_class": str(candidate_root_payload["morphology_class"]),
        "projection_time_sample_count": int(projection_time_ms.shape[0]),
        "shared_time_sample_count": int(shared_time_ms.shape[0]),
        "projection_peak_abs_reference": float(np.max(np.abs(reference_projection))),
        "projection_peak_abs_candidate": float(np.max(np.abs(candidate_projection))),
        "shared_peak_abs_reference": float(np.max(np.abs(reference_shared))),
        "shared_peak_abs_candidate": float(np.max(np.abs(candidate_shared))),
        "diagnostic_tags": copy.deepcopy(dict(case.diagnostic_tags)),
    }
    return sorted(
        [
            _geometry_threshold_finding(
                case=case,
                metric_id="projection_trace_relative_l2",
                measured_quantity="projection_trace_relative_l2",
                measured_value=_relative_l2_difference(
                    reference_projection,
                    candidate_projection,
                ),
                threshold=dict(thresholds["projection_trace_relative_l2"]),
                diagnostic_metadata=diagnostics,
            ),
            _geometry_threshold_finding(
                case=case,
                metric_id="shared_output_trace_relative_l2",
                measured_quantity="shared_output_trace_relative_l2",
                measured_value=_relative_l2_difference(
                    reference_shared,
                    candidate_shared,
                ),
                threshold=dict(thresholds["shared_output_trace_relative_l2"]),
                diagnostic_metadata=diagnostics,
            ),
        ],
        key=lambda item: item["finding_id"],
    )


def _evaluate_mixed_fidelity_summary(
    summary: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    root_summaries = [
        copy.deepcopy(dict(item)) for item in summary.get("root_summaries", [])
    ]
    findings: list[dict[str, Any]] = []
    case_summaries: list[dict[str, Any]] = []
    arm_id = str(summary.get("arm_id", "unknown_arm"))
    for root_summary in root_summaries:
        root_id = int(root_summary["root_id"])
        case_id = f"{arm_id}__root_{root_id}"
        checks = {
            str(metric_name): copy.deepcopy(dict(check))
            for metric_name, check in dict(root_summary.get("checks", {})).items()
        }
        if not checks and str(root_summary.get("overall_status")) == VALIDATION_STATUS_BLOCKED:
            findings.append(
                _mixed_fidelity_finding_record(
                    case_id=case_id,
                    arm_id=arm_id,
                    root_summary=root_summary,
                    metric_id="mixed_fidelity_reference_execution",
                    measured_quantity="mixed_fidelity_reference_execution",
                    measured_value=None,
                    comparison_basis={"kind": "blocked_reference_execution"},
                    status=VALIDATION_STATUS_BLOCKED,
                    diagnostic_metadata={
                        "reference_source": root_summary.get("reference_source"),
                        "error": copy.deepcopy(dict(root_summary.get("error", {}))),
                    },
                    variant_id=str(root_summary.get("reference_morphology_class")),
                )
            )
        for metric_name, check in sorted(checks.items()):
            findings.append(
                _mixed_fidelity_finding_record(
                    case_id=case_id,
                    arm_id=arm_id,
                    root_summary=root_summary,
                    metric_id=metric_name,
                    measured_quantity=metric_name,
                    measured_value=check.get("value"),
                    comparison_basis={
                        "kind": "threshold",
                        "comparison": str(check.get("comparison", "max")),
                        "warn": check.get("warn_threshold"),
                        "fail": check.get("fail_threshold"),
                    },
                    status=str(check.get("status", VALIDATION_STATUS_PASS)),
                    diagnostic_metadata={
                        "reference_source": root_summary.get("reference_source"),
                        "realized_morphology_class": root_summary.get("realized_morphology_class"),
                        "reference_morphology_class": root_summary.get("reference_morphology_class"),
                        "recommended_promotion": bool(root_summary.get("recommended_promotion")),
                        "assignment_provenance": copy.deepcopy(
                            dict(root_summary.get("assignment_provenance", {}))
                        ),
                        "approximation_route": copy.deepcopy(
                            dict(root_summary.get("approximation_route", {}))
                        ),
                        "policy_evaluation": copy.deepcopy(
                            dict(root_summary.get("policy_evaluation", {}))
                        ),
                    },
                    variant_id=str(root_summary.get("reference_morphology_class")),
                )
            )
        case_summaries.append(
            {
                "case_id": case_id,
                "comparison_kind": "mixed_fidelity_surrogate_preservation",
                "root_id": root_id,
                "arm_id": arm_id,
                "validator_id": MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID,
                "overall_status": str(root_summary.get("overall_status", VALIDATION_STATUS_PASS)),
                "finding_ids": sorted(
                    finding["finding_id"]
                    for finding in findings
                    if str(finding["case_id"]) == case_id
                ),
                "reference_source": root_summary.get("reference_source"),
                "realized_morphology_class": root_summary.get("realized_morphology_class"),
                "reference_morphology_class": root_summary.get("reference_morphology_class"),
                "recommended_promotion": bool(root_summary.get("recommended_promotion")),
            }
        )
    return findings, case_summaries


def _resolve_local_thresholds(
    *,
    comparison_kind: str,
    overrides: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    thresholds = copy.deepcopy(_DEFAULT_LOCAL_THRESHOLDS[comparison_kind])
    for metric_name, override in dict(overrides).items():
        if isinstance(override, Mapping):
            thresholds.setdefault(metric_name, {})
            thresholds[metric_name].update(copy.deepcopy(dict(override)))
        else:
            thresholds.setdefault(metric_name, {})
            thresholds[metric_name]["fail"] = override
    return thresholds


def _local_case_diagnostics(
    *,
    case: MorphologyProbeComparisonCase,
    focus_label: str,
    reference_trace: np.ndarray,
    candidate_trace: np.ndarray,
) -> dict[str, Any]:
    return {
        "comparison_kind": case.comparison_kind,
        "focus_patch_set_label": focus_label,
        "reference_variant": case.reference_variant.summary_mapping(),
        "candidate_variant": case.candidate_variant.summary_mapping(),
        "reference_focus_patch_indices": [
            int(index) for index in case.reference_variant.patch_sets[focus_label]
        ],
        "candidate_focus_patch_indices": [
            int(index) for index in case.candidate_variant.patch_sets[focus_label]
        ],
        "reference_focus_peak_abs": float(np.max(np.abs(reference_trace))),
        "candidate_focus_peak_abs": float(np.max(np.abs(candidate_trace))),
        "localized_scope_label": case.localized_scope_label,
        "diagnostic_tags": copy.deepcopy(dict(case.diagnostic_tags)),
    }


def _semantic_patch_trace(
    probe: _VariantProbeResult,
    variant: MorphologyProbeVariant,
    label: str,
) -> np.ndarray:
    indices = np.asarray(variant.patch_sets[label], dtype=np.int32)
    history = np.asarray(probe.patch_activation_history[:, indices], dtype=np.float64)
    if history.ndim == 1:
        return history
    return np.mean(history, axis=1)


def _first_crossing_time_ms(
    time_ms: np.ndarray,
    trace: np.ndarray,
    *,
    threshold_fraction: float = DEFAULT_PULSE_THRESHOLD_FRACTION,
) -> float | None:
    values = np.abs(np.asarray(trace, dtype=np.float64))
    threshold = max(float(np.max(values)) * float(threshold_fraction), _EPSILON)
    crossings = np.flatnonzero(values >= threshold)
    if crossings.size == 0:
        return None
    return float(np.asarray(time_ms, dtype=np.float64)[int(crossings[0])])


def _project_surface_activation_to_patch(
    bundle: SurfaceWaveOperatorBundle,
    activation: np.ndarray,
) -> np.ndarray:
    vector = np.asarray(activation, dtype=np.float64)
    if bundle.restriction is not None:
        return np.asarray(bundle.restriction @ vector, dtype=np.float64)
    if bundle.surface_to_patch is None:
        return vector.copy()
    surface_to_patch = np.asarray(bundle.surface_to_patch, dtype=np.int64)
    patch_count = int(np.max(surface_to_patch)) + 1
    patch_values = np.zeros(patch_count, dtype=np.float64)
    weights = (
        np.asarray(bundle.mass_diagonal, dtype=np.float64)
        if bundle.mass_diagonal is not None
        else np.ones(vector.shape[0], dtype=np.float64)
    )
    for patch_index in range(patch_count):
        mask = surface_to_patch == patch_index
        total_weight = float(np.sum(weights[mask]))
        if total_weight <= _EPSILON:
            patch_values[patch_index] = 0.0
        else:
            patch_values[patch_index] = float(
                np.sum(vector[mask] * weights[mask]) / total_weight
            )
    return patch_values


def _infer_patch_count(bundle: SurfaceWaveOperatorBundle) -> int | None:
    if bundle.patch_count is not None:
        return int(bundle.patch_count)
    if bundle.restriction is not None:
        return int(bundle.restriction.shape[0])
    if bundle.surface_to_patch is not None and np.asarray(bundle.surface_to_patch).size:
        return int(np.max(np.asarray(bundle.surface_to_patch, dtype=np.int64))) + 1
    return None


def _align_series(
    *,
    time_ms_a: np.ndarray,
    values_a: np.ndarray,
    time_ms_b: np.ndarray,
    values_b: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    first_time = float(max(np.min(time_ms_a), np.min(time_ms_b)))
    last_time = float(min(np.max(time_ms_a), np.max(time_ms_b)))
    if last_time < first_time:
        raise ValueError("Trace time ranges do not overlap.")
    common_time = np.unique(
        np.concatenate(
            [
                np.asarray(time_ms_a, dtype=np.float64),
                np.asarray(time_ms_b, dtype=np.float64),
            ]
        )
    )
    common_time = common_time[
        (common_time >= first_time - _EPSILON) & (common_time <= last_time + _EPSILON)
    ]
    if common_time.size < 2:
        common_time = np.asarray([first_time, last_time], dtype=np.float64)
    return (
        np.asarray(common_time, dtype=np.float64),
        np.interp(common_time, time_ms_a, np.asarray(values_a, dtype=np.float64)),
        np.interp(common_time, time_ms_b, np.asarray(values_b, dtype=np.float64)),
    )


def _select_first_shared_trace(payload: Mapping[str, Any]) -> np.ndarray:
    values = np.asarray(payload["values"], dtype=np.float64)
    if values.ndim != 2 or values.shape[1] < 1:
        raise ValueError("Shared readout payload does not contain a usable 2D values array.")
    return values[:, 0]


def _build_case_summary(
    base_summary: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        **copy.deepcopy(dict(base_summary)),
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
        validator_id: sorted(validator_findings, key=lambda item: item["finding_id"])
        for validator_id, validator_findings in sorted(grouped.items())
    }


def _build_validator_summaries(
    findings_by_validator: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for validator_id, validator_findings in findings_by_validator.items():
        summaries[str(validator_id)] = {
            "validator_id": str(validator_id),
            "status": _worst_status(item["status"] for item in validator_findings),
            "finding_count": len(validator_findings),
            "case_count": len({str(item["case_id"]) for item in validator_findings}),
            "status_counts": {
                VALIDATION_STATUS_PASS: sum(
                    1 for item in validator_findings if item["status"] == VALIDATION_STATUS_PASS
                ),
                VALIDATION_STATUS_REVIEW: sum(
                    1 for item in validator_findings if item["status"] == VALIDATION_STATUS_REVIEW
                ),
                VALIDATION_STATUS_BLOCKED: sum(
                    1 for item in validator_findings if item["status"] == VALIDATION_STATUS_BLOCKED
                ),
                VALIDATION_STATUS_BLOCKING: sum(
                    1 for item in validator_findings if item["status"] == VALIDATION_STATUS_BLOCKING
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
        "# Morphology Validation Report",
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


def _probe_finding_record(
    *,
    case: MorphologyProbeComparisonCase,
    metric_id: str,
    measured_quantity: str,
    measured_value: Any,
    comparison_basis: Mapping[str, Any],
    status: str,
    diagnostic_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "finding_id": f"{case.validator_id}:{case.case_id}:{metric_id}",
        "validator_id": case.validator_id,
        "validator_family_id": MORPHOLOGY_DEPENDENCE_FAMILY_ID,
        "layer_id": MORPHOLOGY_SANITY_LAYER_ID,
        "case_id": str(case.case_id),
        "arm_id": None,
        "root_id": int(case.root_id),
        "variant_id": str(case.candidate_variant.variant_id),
        "comparison_kind": str(case.comparison_kind),
        "measured_quantity": measured_quantity,
        "measured_value": measured_value,
        "comparison_basis": copy.deepcopy(dict(comparison_basis)),
        "status": str(status),
        "diagnostic_metadata": copy.deepcopy(dict(diagnostic_metadata)),
    }


def _probe_threshold_finding(
    *,
    case: MorphologyProbeComparisonCase,
    metric_id: str,
    measured_quantity: str,
    measured_value: float,
    threshold: Mapping[str, Any],
    diagnostic_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    comparison = str(threshold.get("comparison", "max"))
    warn = float(threshold["warn"])
    fail = float(threshold["fail"])
    return _probe_finding_record(
        case=case,
        metric_id=metric_id,
        measured_quantity=measured_quantity,
        measured_value=float(measured_value),
        comparison_basis={
            "kind": "threshold",
            "comparison": comparison,
            "warn": warn,
            "fail": fail,
            "description": threshold.get("description"),
        },
        status=_threshold_status(
            value=float(measured_value),
            warn=warn,
            fail=fail,
            comparison=comparison,
        ),
        diagnostic_metadata=diagnostic_metadata,
    )


def _geometry_threshold_finding(
    *,
    case: GeometryTraceComparisonCase,
    metric_id: str,
    measured_quantity: str,
    measured_value: float,
    threshold: Mapping[str, Any],
    diagnostic_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    comparison = str(threshold.get("comparison", "max"))
    warn = float(threshold["warn"])
    fail = float(threshold["fail"])
    return {
        "finding_id": f"{case.validator_id}:{case.case_id}:{metric_id}",
        "validator_id": case.validator_id,
        "validator_family_id": MORPHOLOGY_DEPENDENCE_FAMILY_ID,
        "layer_id": MORPHOLOGY_SANITY_LAYER_ID,
        "case_id": str(case.case_id),
        "arm_id": str(case.reference_arm_id),
        "root_id": int(case.root_id),
        "variant_id": str(case.candidate_arm_id),
        "comparison_kind": case.comparison_kind,
        "measured_quantity": measured_quantity,
        "measured_value": float(measured_value),
        "comparison_basis": {
            "kind": "threshold",
            "comparison": comparison,
            "warn": warn,
            "fail": fail,
            "description": threshold.get("description"),
        },
        "status": _threshold_status(
            value=float(measured_value),
            warn=warn,
            fail=fail,
            comparison=comparison,
        ),
        "diagnostic_metadata": copy.deepcopy(dict(diagnostic_metadata)),
    }


def _mixed_fidelity_finding_record(
    *,
    case_id: str,
    arm_id: str,
    root_summary: Mapping[str, Any],
    metric_id: str,
    measured_quantity: str,
    measured_value: Any,
    comparison_basis: Mapping[str, Any],
    status: str,
    diagnostic_metadata: Mapping[str, Any],
    variant_id: str | None,
) -> dict[str, Any]:
    return {
        "finding_id": (
            f"{MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID}:"
            f"{case_id}:{metric_id}"
            if variant_id is None
            else f"{MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID}:{case_id}:{variant_id}:{metric_id}"
        ),
        "validator_id": MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID,
        "validator_family_id": MORPHOLOGY_DEPENDENCE_FAMILY_ID,
        "layer_id": MORPHOLOGY_SANITY_LAYER_ID,
        "case_id": str(case_id),
        "arm_id": str(arm_id),
        "root_id": int(root_summary["root_id"]),
        "variant_id": variant_id,
        "comparison_kind": "mixed_fidelity_surrogate_preservation",
        "measured_quantity": measured_quantity,
        "measured_value": measured_value,
        "comparison_basis": copy.deepcopy(dict(comparison_basis)),
        "status": str(status),
        "diagnostic_metadata": copy.deepcopy(dict(diagnostic_metadata)),
    }


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


def _relative_l2_difference(reference: np.ndarray, candidate: np.ndarray) -> float:
    ref = np.asarray(reference, dtype=np.float64)
    other = np.asarray(candidate, dtype=np.float64)
    return float(np.linalg.norm(ref - other) / max(np.linalg.norm(ref), _EPSILON))


def _worst_status(statuses: Sequence[str] | Any) -> str:
    resolved = list(statuses)
    if not resolved:
        return VALIDATION_STATUS_PASS
    return max(resolved, key=lambda item: _STATUS_RANK[str(item)])
