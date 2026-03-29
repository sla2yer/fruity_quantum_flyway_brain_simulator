from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .config import get_config_path, get_project_root, load_config
from .experiment_analysis_contract import (
    build_experiment_analysis_bundle_reference,
    load_experiment_analysis_bundle_metadata,
)
from .experiment_comparison_analysis import discover_experiment_bundle_set
from .io_utils import ensure_dir, write_json
from .shared_readout_analysis import (
    _compute_window_response_summary,
    _normalize_analysis_plan,
    _normalize_bundle_record,
    _normalize_kernel_policy,
    _rounded_float,
    compute_shared_readout_analysis,
)
from .simulation_planning import (
    resolve_manifest_readout_analysis_plan,
    resolve_manifest_simulation_plan,
)
from .stimulus_contract import load_stimulus_bundle_metadata
from .synapse_mapping import load_edge_coupling_bundle
from .validation_contract import (
    CIRCUIT_RESPONSE_FAMILY_ID,
    CIRCUIT_SANITY_LAYER_ID,
    COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID,
    MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID,
    VALIDATION_STATUS_BLOCKED,
    VALIDATION_STATUS_BLOCKING,
    VALIDATION_STATUS_PASS,
    VALIDATION_STATUS_REVIEW,
    build_validation_bundle_metadata,
    build_validation_contract_reference,
    build_validation_plan_reference,
    write_validation_bundle_metadata,
)
from .validation_planning import normalize_validation_config


CIRCUIT_VALIDATION_PLAN_VERSION = "circuit_validation_plan.v1"
CIRCUIT_VALIDATION_REPORT_VERSION = "circuit_validation_suite.v1"

DEFAULT_DELAY_PASS_SLACK_MS = 0.25
DEFAULT_DELAY_REVIEW_SLACK_MS = 0.75
DEFAULT_SIGN_MINIMUM_ABS_PEAK = 1.0e-9
DEFAULT_AGGREGATION_PASS_RELATIVE_ERROR = 0.20
DEFAULT_AGGREGATION_REVIEW_RELATIVE_ERROR = 0.40
DEFAULT_AGGREGATION_MIN_SCALE = 1.0e-9
DEFAULT_MOTION_DSI_PASS_THRESHOLD = 0.10
DEFAULT_MOTION_DSI_REVIEW_THRESHOLD = 0.00
DEFAULT_PREFERRED_ADVANTAGE_PASS_MS = 0.0
DEFAULT_PREFERRED_ADVANTAGE_REVIEW_MS = -0.5
DEFAULT_CANONICAL_MOTION_FAMILIES = (
    "moving_edge",
    "translated_edge",
    "drifting_grating",
)

_STATUS_RANK = {
    VALIDATION_STATUS_PASS: 0,
    VALIDATION_STATUS_REVIEW: 1,
    VALIDATION_STATUS_BLOCKED: 2,
    VALIDATION_STATUS_BLOCKING: 3,
}

_DEFAULT_CIRCUIT_CRITERIA_BY_VALIDATOR = {
    COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID: (
        "validation_criteria.circuit_response.coupling_semantics_continuity.v1"
    ),
    MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID: (
        "validation_criteria.circuit_response.motion_pathway_asymmetry.v1"
    ),
}


@dataclass(frozen=True)
class DelayValidationCase:
    case_id: str
    motif_id: str
    analysis_plan: Mapping[str, Any]
    bundle_records: Sequence[Mapping[str, Any]]
    source_readout_id: str
    target_readout_id: str
    edge_bundle_paths: Sequence[str | Path]
    window_id: str = "shared_response_window"
    pass_slack_ms: float = DEFAULT_DELAY_PASS_SLACK_MS
    review_slack_ms: float = DEFAULT_DELAY_REVIEW_SLACK_MS
    notes: str | None = None
    diagnostic_tags: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_nonempty_case_id(self.case_id, case_kind="DelayValidationCase")
        _require_nonempty_string(self.motif_id, field_name="motif_id")
        _require_nonempty_string(
            self.source_readout_id,
            field_name=f"{self.case_id}.source_readout_id",
        )
        _require_nonempty_string(
            self.target_readout_id,
            field_name=f"{self.case_id}.target_readout_id",
        )
        _require_nonempty_string(self.window_id, field_name=f"{self.case_id}.window_id")
        _require_nonempty_bundle_records(self.bundle_records, field_name=f"{self.case_id}.bundle_records")
        _require_nonempty_paths(self.edge_bundle_paths, field_name=f"{self.case_id}.edge_bundle_paths")
        if float(self.pass_slack_ms) < 0.0:
            raise ValueError("DelayValidationCase.pass_slack_ms must be non-negative.")
        if float(self.review_slack_ms) < float(self.pass_slack_ms):
            raise ValueError(
                "DelayValidationCase.review_slack_ms must be greater than or equal to pass_slack_ms."
            )

    def summary_mapping(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_kind": "delay_structure",
            "motif_id": self.motif_id,
            "source_readout_id": self.source_readout_id,
            "target_readout_id": self.target_readout_id,
            "window_id": self.window_id,
            "edge_bundle_paths": [str(Path(path)) for path in self.edge_bundle_paths],
            "notes": self.notes,
            "diagnostic_tags": copy.deepcopy(dict(self.diagnostic_tags)),
        }


@dataclass(frozen=True)
class SignValidationCase:
    case_id: str
    motif_id: str
    analysis_plan: Mapping[str, Any]
    bundle_records: Sequence[Mapping[str, Any]]
    target_readout_id: str
    edge_bundle_paths: Sequence[str | Path]
    window_id: str = "shared_response_window"
    minimum_abs_peak: float = DEFAULT_SIGN_MINIMUM_ABS_PEAK
    notes: str | None = None
    diagnostic_tags: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_nonempty_case_id(self.case_id, case_kind="SignValidationCase")
        _require_nonempty_string(self.motif_id, field_name="motif_id")
        _require_nonempty_string(
            self.target_readout_id,
            field_name=f"{self.case_id}.target_readout_id",
        )
        _require_nonempty_string(self.window_id, field_name=f"{self.case_id}.window_id")
        _require_nonempty_bundle_records(self.bundle_records, field_name=f"{self.case_id}.bundle_records")
        _require_nonempty_paths(self.edge_bundle_paths, field_name=f"{self.case_id}.edge_bundle_paths")
        if float(self.minimum_abs_peak) <= 0.0:
            raise ValueError("SignValidationCase.minimum_abs_peak must be positive.")

    def summary_mapping(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_kind": "sign_behavior",
            "motif_id": self.motif_id,
            "target_readout_id": self.target_readout_id,
            "window_id": self.window_id,
            "edge_bundle_paths": [str(Path(path)) for path in self.edge_bundle_paths],
            "minimum_abs_peak": float(self.minimum_abs_peak),
            "notes": self.notes,
            "diagnostic_tags": copy.deepcopy(dict(self.diagnostic_tags)),
        }


@dataclass(frozen=True)
class AggregationValidationCase:
    case_id: str
    motif_id: str
    analysis_plan: Mapping[str, Any]
    bundle_records: Sequence[Mapping[str, Any]]
    target_readout_id: str
    edge_bundle_paths: Sequence[str | Path]
    single_condition_sets: Mapping[str, Sequence[str]]
    combined_condition_ids: Sequence[str]
    window_id: str = "shared_response_window"
    pass_relative_error: float = DEFAULT_AGGREGATION_PASS_RELATIVE_ERROR
    review_relative_error: float = DEFAULT_AGGREGATION_REVIEW_RELATIVE_ERROR
    minimum_expected_scale: float = DEFAULT_AGGREGATION_MIN_SCALE
    notes: str | None = None
    diagnostic_tags: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_nonempty_case_id(self.case_id, case_kind="AggregationValidationCase")
        _require_nonempty_string(self.motif_id, field_name="motif_id")
        _require_nonempty_string(
            self.target_readout_id,
            field_name=f"{self.case_id}.target_readout_id",
        )
        _require_nonempty_string(self.window_id, field_name=f"{self.case_id}.window_id")
        _require_nonempty_bundle_records(self.bundle_records, field_name=f"{self.case_id}.bundle_records")
        _require_nonempty_paths(self.edge_bundle_paths, field_name=f"{self.case_id}.edge_bundle_paths")
        if not isinstance(self.single_condition_sets, Mapping):
            raise ValueError("AggregationValidationCase.single_condition_sets must be a mapping.")
        if len(self.single_condition_sets) < 2:
            raise ValueError(
                "AggregationValidationCase requires at least two single-condition signatures."
            )
        for label, condition_ids in dict(self.single_condition_sets).items():
            _require_nonempty_string(label, field_name=f"{self.case_id}.single_condition_sets.label")
            _normalize_condition_ids(
                condition_ids,
                field_name=f"{self.case_id}.single_condition_sets[{label!r}]",
            )
        _normalize_condition_ids(
            self.combined_condition_ids,
            field_name=f"{self.case_id}.combined_condition_ids",
        )
        if float(self.pass_relative_error) < 0.0:
            raise ValueError("AggregationValidationCase.pass_relative_error must be non-negative.")
        if float(self.review_relative_error) < float(self.pass_relative_error):
            raise ValueError(
                "AggregationValidationCase.review_relative_error must be greater than or equal to pass_relative_error."
            )
        if float(self.minimum_expected_scale) <= 0.0:
            raise ValueError("AggregationValidationCase.minimum_expected_scale must be positive.")

    def summary_mapping(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_kind": "aggregation_behavior",
            "motif_id": self.motif_id,
            "target_readout_id": self.target_readout_id,
            "window_id": self.window_id,
            "edge_bundle_paths": [str(Path(path)) for path in self.edge_bundle_paths],
            "single_condition_sets": {
                str(label): list(_normalize_condition_ids(condition_ids, field_name="single_condition_sets"))
                for label, condition_ids in sorted(self.single_condition_sets.items())
            },
            "combined_condition_ids": list(
                _normalize_condition_ids(
                    self.combined_condition_ids,
                    field_name="combined_condition_ids",
                )
            ),
            "notes": self.notes,
            "diagnostic_tags": copy.deepcopy(dict(self.diagnostic_tags)),
        }


@dataclass(frozen=True)
class MotionPathwayAsymmetryCase:
    case_id: str
    pathway_id: str
    analysis_plan: Mapping[str, Any]
    bundle_records: Sequence[Mapping[str, Any]]
    readout_id: str
    condition_pair_id: str = "preferred_vs_null"
    preferred_condition_id: str = "preferred_direction"
    null_condition_id: str = "null_direction"
    window_id: str = "shared_response_window"
    allowed_stimulus_families: Sequence[str] = DEFAULT_CANONICAL_MOTION_FAMILIES
    dsi_pass_threshold: float = DEFAULT_MOTION_DSI_PASS_THRESHOLD
    dsi_review_threshold: float = DEFAULT_MOTION_DSI_REVIEW_THRESHOLD
    preferred_advantage_pass_ms: float = DEFAULT_PREFERRED_ADVANTAGE_PASS_MS
    preferred_advantage_review_ms: float = DEFAULT_PREFERRED_ADVANTAGE_REVIEW_MS
    notes: str | None = None
    diagnostic_tags: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_nonempty_case_id(self.case_id, case_kind="MotionPathwayAsymmetryCase")
        _require_nonempty_string(self.pathway_id, field_name="pathway_id")
        _require_nonempty_string(self.readout_id, field_name=f"{self.case_id}.readout_id")
        _require_nonempty_string(
            self.condition_pair_id,
            field_name=f"{self.case_id}.condition_pair_id",
        )
        _require_nonempty_string(
            self.preferred_condition_id,
            field_name=f"{self.case_id}.preferred_condition_id",
        )
        _require_nonempty_string(
            self.null_condition_id,
            field_name=f"{self.case_id}.null_condition_id",
        )
        _require_nonempty_string(self.window_id, field_name=f"{self.case_id}.window_id")
        _require_nonempty_bundle_records(self.bundle_records, field_name=f"{self.case_id}.bundle_records")
        _require_nonempty_string_sequence(
            self.allowed_stimulus_families,
            field_name=f"{self.case_id}.allowed_stimulus_families",
        )
        if float(self.dsi_review_threshold) > float(self.dsi_pass_threshold):
            raise ValueError(
                "MotionPathwayAsymmetryCase.dsi_review_threshold must be less than or equal to dsi_pass_threshold."
            )
        if float(self.preferred_advantage_review_ms) > float(
            self.preferred_advantage_pass_ms
        ):
            raise ValueError(
                "MotionPathwayAsymmetryCase.preferred_advantage_review_ms must be less than or equal to preferred_advantage_pass_ms."
            )

    def summary_mapping(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_kind": "motion_pathway_asymmetry",
            "pathway_id": self.pathway_id,
            "readout_id": self.readout_id,
            "condition_pair_id": self.condition_pair_id,
            "preferred_condition_id": self.preferred_condition_id,
            "null_condition_id": self.null_condition_id,
            "window_id": self.window_id,
            "allowed_stimulus_families": list(self.allowed_stimulus_families),
            "notes": self.notes,
            "diagnostic_tags": copy.deepcopy(dict(self.diagnostic_tags)),
        }


def resolve_circuit_validation_plan(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    analysis_bundle_metadata_path: str | Path | None = None,
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
    if analysis_bundle_metadata_path is None:
        packaged_analysis_bundle = None
        analysis_summary = None
        loaded_analysis_bundle_metadata = None
    else:
        packaged_analysis_bundle = None
        analysis_summary = None
        loaded_analysis_bundle_metadata = load_experiment_analysis_bundle_metadata(
            analysis_bundle_metadata_path
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
    active_validator_ids = _resolve_active_circuit_validator_ids(validation_config)
    criteria_assignments = _resolve_circuit_criteria_assignments(
        validation_config=validation_config,
        active_validator_ids=active_validator_ids,
    )
    target_arm_ids = sorted(
        {
            str(item["arm_id"])
            for item in bundle_set["bundle_inventory"]
        }
    )
    comparison_group_ids = (
        []
        if analysis_summary is None
        else [
            str(item["group_id"])
            for item in analysis_summary["comparison_group_catalog"]
        ]
    )
    plan_reference = build_validation_plan_reference(
        experiment_id=str(simulation_plan["manifest_reference"]["experiment_id"]),
        contract_reference=build_validation_contract_reference(),
        active_layer_ids=[CIRCUIT_SANITY_LAYER_ID],
        active_validator_family_ids=[CIRCUIT_RESPONSE_FAMILY_ID],
        active_validator_ids=active_validator_ids,
        criteria_profile_references=[
            item["criteria_profile_reference"] for item in criteria_assignments
        ],
        evidence_bundle_references=(
            {}
            if loaded_analysis_bundle_metadata is None
            else {
                "experiment_analysis_bundle": build_experiment_analysis_bundle_reference(
                    loaded_analysis_bundle_metadata
                )
            }
        ),
        target_arm_ids=target_arm_ids,
        comparison_group_ids=comparison_group_ids,
        criteria_profile_assignments=[
            {
                "validator_id": item["validator_id"],
                "criteria_profile_reference": item["criteria_profile_reference"],
            }
            for item in criteria_assignments
        ],
        plan_version=CIRCUIT_VALIDATION_PLAN_VERSION,
    )
    bundle_metadata = build_validation_bundle_metadata(
        validation_plan_reference=plan_reference,
        processed_simulator_results_dir=cfg["paths"]["processed_simulator_results_dir"],
    )
    return {
        "plan_version": CIRCUIT_VALIDATION_PLAN_VERSION,
        "manifest_reference": copy.deepcopy(dict(simulation_plan["manifest_reference"])),
        "validation_config": validation_config,
        "config_reference": {
            "config_path": str(config_file.resolve()),
            "project_root": str(project_root.resolve()),
        },
        "active_layer_ids": [CIRCUIT_SANITY_LAYER_ID],
        "active_validator_family_ids": [CIRCUIT_RESPONSE_FAMILY_ID],
        "active_validator_ids": list(active_validator_ids),
        "criteria_profile_assignments": criteria_assignments,
        "target_arm_ids": target_arm_ids,
        "analysis_plan": copy.deepcopy(dict(analysis_plan)),
        "bundle_set": copy.deepcopy(dict(bundle_set)),
        "analysis_bundle": {
            "metadata": (
                None
                if loaded_analysis_bundle_metadata is None
                else copy.deepcopy(loaded_analysis_bundle_metadata)
            ),
            "reference": (
                None
                if loaded_analysis_bundle_metadata is None
                else build_experiment_analysis_bundle_reference(
                    loaded_analysis_bundle_metadata
                )
            ),
            "packaged_analysis_bundle": packaged_analysis_bundle,
        },
        "analysis_summary": (
            None if analysis_summary is None else copy.deepcopy(dict(analysis_summary))
        ),
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


def build_motion_pathway_asymmetry_cases_from_bundle_set(
    *,
    analysis_plan: Mapping[str, Any],
    bundle_set: Mapping[str, Any],
    readout_ids: Sequence[str],
    arm_ids: Sequence[str] | None = None,
    condition_pair_id: str = "preferred_vs_null",
    preferred_condition_id: str = "preferred_direction",
    null_condition_id: str = "null_direction",
) -> list[MotionPathwayAsymmetryCase]:
    normalized_readout_ids = _require_nonempty_string_sequence(
        readout_ids,
        field_name="readout_ids",
    )
    bundle_records_payload = bundle_set.get("bundle_records")
    if not isinstance(bundle_records_payload, Sequence) or isinstance(
        bundle_records_payload,
        (str, bytes),
    ):
        raise ValueError("bundle_set.bundle_records must be a sequence.")
    records_by_arm_id: dict[str, list[Mapping[str, Any]]] = {}
    for record in bundle_records_payload:
        if not isinstance(record, Mapping):
            raise ValueError("bundle_set.bundle_records entries must be mappings.")
        metadata = dict(record["bundle_metadata"])
        arm_id = str(metadata["arm_reference"]["arm_id"])
        records_by_arm_id.setdefault(arm_id, []).append(copy.deepcopy(dict(record)))

    selected_arm_ids = (
        _resolve_canonical_motion_arm_ids(
            analysis_plan=analysis_plan,
            bundle_set=bundle_set,
        )
        if arm_ids is None
        else _require_nonempty_string_sequence(arm_ids, field_name="arm_ids")
    )
    missing_arm_ids = [
        arm_id
        for arm_id in selected_arm_ids
        if arm_id not in records_by_arm_id
    ]
    if missing_arm_ids:
        raise ValueError(
            "Circuit validation could not resolve bundle records for canonical motion "
            f"arm_ids {missing_arm_ids!r}; available arm_ids are {sorted(records_by_arm_id)!r}."
        )

    cases: list[MotionPathwayAsymmetryCase] = []
    for arm_id in selected_arm_ids:
        arm_records = sorted(
            records_by_arm_id[arm_id],
            key=lambda item: (
                int(item["bundle_metadata"]["determinism"]["seed"]),
                tuple(sorted(item["condition_ids"])),
            ),
        )
        available_readout_ids = {
            str(entry["readout_id"])
            for entry in arm_records[0]["bundle_metadata"]["readout_catalog"]
        }
        for readout_id in normalized_readout_ids:
            if readout_id not in available_readout_ids:
                raise ValueError(
                    f"Arm {arm_id!r} does not expose readout_id {readout_id!r}; "
                    f"available ids are {sorted(available_readout_ids)!r}."
                )
            cases.append(
                MotionPathwayAsymmetryCase(
                    case_id=f"{arm_id}__{readout_id}",
                    pathway_id=f"{arm_id}:{readout_id}",
                    analysis_plan=analysis_plan,
                    bundle_records=arm_records,
                    readout_id=readout_id,
                    condition_pair_id=condition_pair_id,
                    preferred_condition_id=preferred_condition_id,
                    null_condition_id=null_condition_id,
                    notes=(
                        "Manifest-discovered motion pathway asymmetry case built from "
                        f"arm {arm_id!r}."
                    ),
                )
            )
    return cases


def _resolve_canonical_motion_arm_ids(
    *,
    analysis_plan: Mapping[str, Any],
    bundle_set: Mapping[str, Any],
) -> list[str]:
    pair_catalog_payload = analysis_plan.get("arm_pair_catalog")
    if not isinstance(pair_catalog_payload, Sequence) or isinstance(
        pair_catalog_payload,
        (str, bytes),
    ):
        raise ValueError(
            "analysis_plan.arm_pair_catalog must be a list to derive canonical motion "
            "pathway cases; provide explicit arm_ids otherwise."
        )
    normalized_pairs: list[dict[str, Any]] = []
    for index, item in enumerate(pair_catalog_payload):
        if not isinstance(item, Mapping):
            raise ValueError(
                f"analysis_plan.arm_pair_catalog[{index}] must be a mapping."
            )
        normalized_pairs.append(dict(item))
    if not normalized_pairs:
        raise ValueError(
            "analysis_plan.arm_pair_catalog is empty; provide explicit arm_ids to build "
            "motion pathway asymmetry cases."
        )
    canonical_pair = next(
        (
            item
            for item in normalized_pairs
            if str(item.get("baseline_family") or "") == "P0"
            and str(item.get("topology_condition") or "") == "intact"
        ),
        normalized_pairs[0],
    )
    arm_ids = _require_nonempty_string_sequence(
        canonical_pair.get("arm_ids"),
        field_name="analysis_plan.arm_pair_catalog[*].arm_ids",
    )
    bundle_inventory_payload = bundle_set.get("bundle_inventory")
    if not isinstance(bundle_inventory_payload, Sequence) or isinstance(
        bundle_inventory_payload,
        (str, bytes),
    ):
        raise ValueError("bundle_set.bundle_inventory must be a sequence.")
    available_arm_ids = {
        str(item["arm_id"])
        for item in bundle_inventory_payload
        if isinstance(item, Mapping) and item.get("arm_id") is not None
    }
    missing_arm_ids = [
        arm_id
        for arm_id in arm_ids
        if arm_id not in available_arm_ids
    ]
    if missing_arm_ids:
        raise ValueError(
            "Canonical motion arm_ids declared by analysis_plan.arm_pair_catalog are not "
            f"present in bundle_set.bundle_inventory: {missing_arm_ids!r}."
        )
    return arm_ids


def run_circuit_validation_suite(
    *,
    delay_cases: Sequence[DelayValidationCase] = (),
    sign_cases: Sequence[SignValidationCase] = (),
    aggregation_cases: Sequence[AggregationValidationCase] = (),
    motion_cases: Sequence[MotionPathwayAsymmetryCase] = (),
    validation_plan_reference: Mapping[str, Any] | None = None,
    bundle_metadata: Mapping[str, Any] | None = None,
    processed_simulator_results_dir: str | Path | None = None,
    experiment_id: str = "fixture_circuit_validation",
) -> dict[str, Any]:
    normalized_delay_cases = _normalize_typed_cases(
        delay_cases,
        expected_type=DelayValidationCase,
        field_name="delay_cases",
    )
    normalized_sign_cases = _normalize_typed_cases(
        sign_cases,
        expected_type=SignValidationCase,
        field_name="sign_cases",
    )
    normalized_aggregation_cases = _normalize_typed_cases(
        aggregation_cases,
        expected_type=AggregationValidationCase,
        field_name="aggregation_cases",
    )
    normalized_motion_cases = _normalize_typed_cases(
        motion_cases,
        expected_type=MotionPathwayAsymmetryCase,
        field_name="motion_cases",
    )
    if not (
        normalized_delay_cases
        or normalized_sign_cases
        or normalized_aggregation_cases
        or normalized_motion_cases
    ):
        raise ValueError(
            "Circuit validation requires at least one delay, sign, aggregation, or motion case."
        )

    resolved_bundle_metadata = _resolve_bundle_metadata(
        validation_plan_reference=validation_plan_reference,
        bundle_metadata=bundle_metadata,
        processed_simulator_results_dir=processed_simulator_results_dir,
        experiment_id=experiment_id,
        delay_cases=normalized_delay_cases,
        sign_cases=normalized_sign_cases,
        aggregation_cases=normalized_aggregation_cases,
        motion_cases=normalized_motion_cases,
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

    for case in normalized_delay_cases:
        case_findings = _evaluate_delay_case(case)
        findings.extend(case_findings)
        case_summaries.append(_build_case_summary(case.summary_mapping(), case_findings))
    for case in normalized_sign_cases:
        case_findings = _evaluate_sign_case(case)
        findings.extend(case_findings)
        case_summaries.append(_build_case_summary(case.summary_mapping(), case_findings))
    for case in normalized_aggregation_cases:
        case_findings = _evaluate_aggregation_case(case)
        findings.extend(case_findings)
        case_summaries.append(_build_case_summary(case.summary_mapping(), case_findings))
    for case in normalized_motion_cases:
        case_findings = _evaluate_motion_case(case)
        findings.extend(case_findings)
        case_summaries.append(_build_case_summary(case.summary_mapping(), case_findings))

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
        "report_version": CIRCUIT_VALIDATION_REPORT_VERSION,
        "bundle_id": str(resolved_bundle_metadata["bundle_id"]),
        "experiment_id": str(resolved_bundle_metadata["experiment_id"]),
        "validation_spec_hash": str(resolved_bundle_metadata["validation_spec_hash"]),
        "overall_status": overall_status,
        "active_layer_ids": [CIRCUIT_SANITY_LAYER_ID],
        "active_validator_family_ids": [CIRCUIT_RESPONSE_FAMILY_ID],
        "active_validator_ids": sorted(findings_by_validator),
        "status_counts": status_counts,
        "layers": [
            {
                "layer_id": CIRCUIT_SANITY_LAYER_ID,
                "status": layer_status,
                "validator_families": [
                    {
                        "validator_family_id": CIRCUIT_RESPONSE_FAMILY_ID,
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
        "report_version": CIRCUIT_VALIDATION_REPORT_VERSION,
        "bundle_id": str(resolved_bundle_metadata["bundle_id"]),
        "validator_findings": findings_by_validator,
    }
    review_handoff_payload = {
        "format_version": "json_validation_review_handoff.v1",
        "report_version": CIRCUIT_VALIDATION_REPORT_VERSION,
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
        "report_version": CIRCUIT_VALIDATION_REPORT_VERSION,
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


def execute_circuit_validation_workflow(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    pathway_readout_ids: Sequence[str] | None = None,
    delay_cases: Sequence[DelayValidationCase] = (),
    sign_cases: Sequence[SignValidationCase] = (),
    aggregation_cases: Sequence[AggregationValidationCase] = (),
    analysis_bundle_metadata_path: str | Path | None = None,
) -> dict[str, Any]:
    plan = resolve_circuit_validation_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        analysis_bundle_metadata_path=analysis_bundle_metadata_path,
    )

    motion_cases: list[MotionPathwayAsymmetryCase] = []
    if MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID in set(plan["active_validator_ids"]):
        resolved_pathway_readout_ids = _resolve_pathway_readout_ids(
            analysis_plan=plan["analysis_plan"],
            bundle_set=plan["bundle_set"],
            pathway_readout_ids=pathway_readout_ids,
        )
        motion_cases = build_motion_pathway_asymmetry_cases_from_bundle_set(
            analysis_plan=plan["analysis_plan"],
            bundle_set=plan["bundle_set"],
            readout_ids=resolved_pathway_readout_ids,
        )
    if not motion_cases and not delay_cases and not sign_cases and not aggregation_cases:
        raise ValueError(
            "Circuit validation workflow resolved no actionable cases. Provide "
            "pathway_readout_ids and/or explicit delay/sign/aggregation cases."
        )

    result = run_circuit_validation_suite(
        delay_cases=delay_cases,
        sign_cases=sign_cases,
        aggregation_cases=aggregation_cases,
        motion_cases=motion_cases,
        validation_plan_reference=plan["validation_plan_reference"],
        bundle_metadata=plan["validation_bundle"]["metadata"],
    )
    return {
        **result,
        "circuit_validation_plan": plan,
    }


def _resolve_pathway_readout_ids(
    *,
    analysis_plan: Mapping[str, Any],
    bundle_set: Mapping[str, Any],
    pathway_readout_ids: Sequence[str] | None,
) -> list[str]:
    if pathway_readout_ids is not None:
        return _require_nonempty_string_sequence(
            pathway_readout_ids,
            field_name="pathway_readout_ids",
        )

    derived: list[str] = []
    active_shared_readouts = analysis_plan.get("active_shared_readouts")
    if isinstance(active_shared_readouts, Sequence) and not isinstance(
        active_shared_readouts,
        (str, bytes),
    ):
        for item in active_shared_readouts:
            if not isinstance(item, Mapping):
                continue
            readout_id = item.get("readout_id")
            if readout_id is None:
                continue
            normalized = str(readout_id).strip()
            if normalized and normalized not in derived:
                derived.append(normalized)
    if derived:
        return _prefer_motion_specific_readout_ids(derived)

    bundle_records = bundle_set.get("bundle_records")
    if isinstance(bundle_records, Sequence) and not isinstance(
        bundle_records,
        (str, bytes),
    ):
        for record in bundle_records:
            if not isinstance(record, Mapping):
                continue
            bundle_metadata = record.get("bundle_metadata")
            if not isinstance(bundle_metadata, Mapping):
                continue
            readout_catalog = bundle_metadata.get("readout_catalog")
            if not isinstance(readout_catalog, Sequence) or isinstance(
                readout_catalog,
                (str, bytes),
            ):
                continue
            for entry in readout_catalog:
                if not isinstance(entry, Mapping):
                    continue
                if str(entry.get("scope") or "").strip() != "circuit_output":
                    continue
                readout_id = entry.get("readout_id")
                if readout_id is None:
                    continue
                normalized = str(readout_id).strip()
                if normalized and normalized not in derived:
                    derived.append(normalized)
            if derived:
                return _prefer_motion_specific_readout_ids(derived)

    raise ValueError(
        "Circuit validation workflow could not derive default pathway_readout_ids "
        "from the manifest analysis plan or local bundle inventory. Provide at "
        "least one explicit pathway_readout_id."
    )


def _prefer_motion_specific_readout_ids(readout_ids: Sequence[str]) -> list[str]:
    normalized = [
        str(readout_id).strip()
        for readout_id in readout_ids
        if str(readout_id).strip()
    ]
    if len(normalized) <= 1:
        return normalized
    preferred = [
        readout_id
        for readout_id in normalized
        if readout_id != "shared_output_mean"
    ]
    return preferred or normalized


def _normalize_typed_cases(
    cases: Sequence[Any],
    *,
    expected_type: type[Any],
    field_name: str,
) -> list[Any]:
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence.")
    normalized: list[Any] = []
    seen_case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, expected_type):
            raise ValueError(
                f"{field_name} must contain {expected_type.__name__} instances."
            )
        if case.case_id in seen_case_ids:
            raise ValueError(f"Duplicate case_id {case.case_id!r} in {field_name}.")
        seen_case_ids.add(case.case_id)
        normalized.append(case)
    return sorted(normalized, key=lambda item: item.case_id)


def _resolve_bundle_metadata(
    *,
    validation_plan_reference: Mapping[str, Any] | None,
    bundle_metadata: Mapping[str, Any] | None,
    processed_simulator_results_dir: str | Path | None,
    experiment_id: str,
    delay_cases: Sequence[DelayValidationCase],
    sign_cases: Sequence[SignValidationCase],
    aggregation_cases: Sequence[AggregationValidationCase],
    motion_cases: Sequence[MotionPathwayAsymmetryCase],
) -> dict[str, Any]:
    if bundle_metadata is not None:
        return copy.deepcopy(dict(bundle_metadata))
    if validation_plan_reference is not None:
        if processed_simulator_results_dir is not None:
            return build_validation_bundle_metadata(
                validation_plan_reference=validation_plan_reference,
                processed_simulator_results_dir=processed_simulator_results_dir,
            )
        return build_validation_bundle_metadata(
            validation_plan_reference=validation_plan_reference,
        )
    if processed_simulator_results_dir is None:
        raise ValueError(
            "processed_simulator_results_dir is required when validation_plan_reference is unavailable."
        )
    inferred_validator_ids = _infer_active_validator_ids(
        delay_cases=delay_cases,
        sign_cases=sign_cases,
        aggregation_cases=aggregation_cases,
        motion_cases=motion_cases,
    )
    plan_reference = build_validation_plan_reference(
        experiment_id=experiment_id,
        contract_reference=build_validation_contract_reference(),
        active_layer_ids=[CIRCUIT_SANITY_LAYER_ID],
        active_validator_family_ids=[CIRCUIT_RESPONSE_FAMILY_ID],
        active_validator_ids=inferred_validator_ids,
        criteria_profile_references=[
            _DEFAULT_CIRCUIT_CRITERIA_BY_VALIDATOR[validator_id]
            for validator_id in inferred_validator_ids
        ],
        criteria_profile_assignments=[
            {
                "validator_id": validator_id,
                "criteria_profile_reference": _DEFAULT_CIRCUIT_CRITERIA_BY_VALIDATOR[
                    validator_id
                ],
            }
            for validator_id in inferred_validator_ids
        ],
        plan_version=CIRCUIT_VALIDATION_PLAN_VERSION,
    )
    return build_validation_bundle_metadata(
        validation_plan_reference=plan_reference,
        processed_simulator_results_dir=processed_simulator_results_dir,
    )


def _infer_active_validator_ids(
    *,
    delay_cases: Sequence[DelayValidationCase],
    sign_cases: Sequence[SignValidationCase],
    aggregation_cases: Sequence[AggregationValidationCase],
    motion_cases: Sequence[MotionPathwayAsymmetryCase],
) -> list[str]:
    active: list[str] = []
    if delay_cases or sign_cases or aggregation_cases:
        active.append(COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID)
    if motion_cases:
        active.append(MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID)
    return active


def _evaluate_delay_case(case: DelayValidationCase) -> list[dict[str, Any]]:
    analysis_context = _build_analysis_context(
        analysis_plan=case.analysis_plan,
        bundle_records=case.bundle_records,
    )
    window = _resolve_window_reference(case.analysis_plan, case.window_id)
    policy = _normalize_kernel_policy(None)
    edge_diagnostics = _load_edge_family_diagnostics(case.edge_bundle_paths)
    expected_delay_ms = float(edge_diagnostics["weighted_mean_delay_ms"])
    findings: list[dict[str, Any]] = []
    for bundle in analysis_context["bundle_records"]:
        source_summary = _compute_window_response_summary(
            bundle=bundle,
            readout_id=case.source_readout_id,
            window=window,
            policy=policy,
        )
        target_summary = _compute_window_response_summary(
            bundle=bundle,
            readout_id=case.target_readout_id,
            window=window,
            policy=policy,
        )
        finding_suffix = (
            f"{bundle['analysis_group_id']}:latency_delta_vs_weighted_component_delay"
        )
        if source_summary["signal_classification"] != "ok" or target_summary["signal_classification"] != "ok":
            findings.append(
                _build_finding(
                    validator_id=COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID,
                    case_id=case.case_id,
                    check_kind="delay_structure",
                    finding_suffix=finding_suffix,
                    status=VALIDATION_STATUS_BLOCKED,
                    motif_or_pathway_id=case.motif_id,
                    expected_relationship=(
                        "Both source and target readouts should produce a usable latency "
                        "measurement inside the declared analysis window."
                    ),
                    observed_relationship=(
                        f"Source status={source_summary['signal_classification']!r}, "
                        f"target status={target_summary['signal_classification']!r}."
                    ),
                    provenance=_bundle_level_provenance(
                        bundle=bundle,
                        extra={"edge_families": edge_diagnostics["edge_families"]},
                    ),
                    diagnostics={
                        "source_response_summary": source_summary,
                        "target_response_summary": target_summary,
                        "actionable_diagnostic": (
                            "Increase deterministic drive strength or inspect the selected "
                            "edge family and readout bindings; latency cannot be judged "
                            "without a stable source and target response."
                        ),
                    },
                    measured_value=None,
                    units="ms",
                )
            )
            continue
        observed_delta_ms = float(target_summary["peak_latency_ms"]) - float(
            source_summary["peak_latency_ms"]
        )
        status = _classify_min_threshold(
            observed_value=observed_delta_ms,
            pass_threshold=expected_delay_ms - float(case.pass_slack_ms),
            review_threshold=expected_delay_ms - float(case.review_slack_ms),
        )
        findings.append(
            _build_finding(
                validator_id=COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID,
                case_id=case.case_id,
                check_kind="delay_structure",
                finding_suffix=finding_suffix,
                status=status,
                motif_or_pathway_id=case.motif_id,
                expected_relationship=(
                    f"Target latency should lag the source by roughly the weighted component "
                    f"delay ({_rounded_float(expected_delay_ms)} ms) implied by the selected "
                    "Milestone 7 edge family."
                ),
                observed_relationship=(
                    f"Observed target-source latency delta is "
                    f"{_rounded_float(observed_delta_ms)} ms."
                ),
                provenance=_bundle_level_provenance(
                    bundle=bundle,
                    extra={"edge_families": edge_diagnostics["edge_families"]},
                ),
                diagnostics={
                    "expected_weighted_component_delay_ms": _rounded_float(
                        expected_delay_ms
                    ),
                    "source_peak_latency_ms": source_summary["peak_latency_ms"],
                    "target_peak_latency_ms": target_summary["peak_latency_ms"],
                    "delay_slack_ms": {
                        "pass": _rounded_float(float(case.pass_slack_ms)),
                        "review": _rounded_float(float(case.review_slack_ms)),
                    },
                    "actionable_diagnostic": (
                        "Inspect the listed edge families if the target is leading the "
                        "source or if the observed lag collapsed below the quantized "
                        "component delay."
                    ),
                },
                measured_value=_rounded_float(observed_delta_ms),
                units="ms",
            )
        )
    return findings


def _evaluate_sign_case(case: SignValidationCase) -> list[dict[str, Any]]:
    analysis_context = _build_analysis_context(
        analysis_plan=case.analysis_plan,
        bundle_records=case.bundle_records,
    )
    window = _resolve_window_reference(case.analysis_plan, case.window_id)
    policy = _normalize_kernel_policy(None)
    edge_diagnostics = _load_edge_family_diagnostics(case.edge_bundle_paths)
    expected_sign = int(edge_diagnostics["net_sign"])
    if expected_sign == 0:
        raise ValueError(
            f"SignValidationCase {case.case_id!r} resolved a zero net sign from the "
            "selected edge families; expected an excitatory or inhibitory probe."
        )
    findings: list[dict[str, Any]] = []
    for bundle in analysis_context["bundle_records"]:
        response_summary = _compute_signed_window_response_summary(
            bundle=bundle,
            readout_id=case.target_readout_id,
            window=window,
            policy=policy,
        )
        signed_peak_value = float(response_summary["signed_peak_value"])
        amplitude = abs(signed_peak_value)
        finding_suffix = f"{bundle['analysis_group_id']}:signed_peak_polarity"
        if amplitude < float(case.minimum_abs_peak):
            findings.append(
                _build_finding(
                    validator_id=COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID,
                    case_id=case.case_id,
                    check_kind="sign_behavior",
                    finding_suffix=finding_suffix,
                    status=VALIDATION_STATUS_BLOCKED,
                    motif_or_pathway_id=case.motif_id,
                    expected_relationship=(
                        "The driven target readout should produce a non-trivial signed "
                        "deviation so the net coupling sign can be checked."
                    ),
                    observed_relationship=(
                        f"Absolute signed peak was only {_rounded_float(amplitude)}."
                    ),
                    provenance=_bundle_level_provenance(
                        bundle=bundle,
                        extra={"edge_families": edge_diagnostics["edge_families"]},
                    ),
                    diagnostics={
                        "expected_net_sign": "excitatory" if expected_sign > 0 else "inhibitory",
                        "signed_response_summary": response_summary,
                        "actionable_diagnostic": (
                            "Inspect the stimulus amplitude, readout binding, or selected "
                            "edge family; the response is too small to distinguish a sign flip "
                            "from a no-signal case."
                        ),
                    },
                    measured_value=_rounded_float(signed_peak_value),
                    units=str(response_summary["readout_units"]),
                )
            )
            continue
        observed_sign = 1 if signed_peak_value > 0.0 else -1
        status = (
            VALIDATION_STATUS_PASS
            if observed_sign == expected_sign
            else VALIDATION_STATUS_BLOCKING
        )
        findings.append(
            _build_finding(
                validator_id=COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID,
                case_id=case.case_id,
                check_kind="sign_behavior",
                finding_suffix=finding_suffix,
                status=status,
                motif_or_pathway_id=case.motif_id,
                expected_relationship=(
                    f"Observed target deflection should stay "
                    f"{'positive' if expected_sign > 0 else 'negative'} because the "
                    "selected edge family has the same net signed weight."
                ),
                observed_relationship=(
                    f"Observed signed peak was {_rounded_float(signed_peak_value)} "
                    f"({response_summary['signed_peak_label']})."
                ),
                provenance=_bundle_level_provenance(
                    bundle=bundle,
                    extra={"edge_families": edge_diagnostics["edge_families"]},
                ),
                diagnostics={
                    "expected_net_signed_weight": _rounded_float(
                        float(edge_diagnostics["net_signed_weight"])
                    ),
                    "signed_response_summary": response_summary,
                    "actionable_diagnostic": (
                        "Inspect the listed edge family and runtime coupling route; the "
                        "observed readout polarity contradicts the Milestone 7 signed-weight "
                        "semantics."
                    ),
                },
                measured_value=_rounded_float(signed_peak_value),
                units=str(response_summary["readout_units"]),
            )
        )
    return findings


def _evaluate_aggregation_case(case: AggregationValidationCase) -> list[dict[str, Any]]:
    analysis_context = _build_analysis_context(
        analysis_plan=case.analysis_plan,
        bundle_records=case.bundle_records,
    )
    window = _resolve_window_reference(case.analysis_plan, case.window_id)
    policy = _normalize_kernel_policy(None)
    edge_diagnostics = _load_edge_family_diagnostics(case.edge_bundle_paths)
    if not edge_diagnostics["aggregation_rules"]:
        raise ValueError(
            f"AggregationValidationCase {case.case_id!r} did not resolve any aggregation rules."
        )
    unsupported_rules = [
        rule
        for rule in edge_diagnostics["aggregation_rules"]
        if rule != "sum_over_synapses_preserving_sign_and_delay_bins"
    ]
    if unsupported_rules:
        raise ValueError(
            f"AggregationValidationCase {case.case_id!r} expected the Milestone 7 "
            "summation rule but resolved incompatible rules "
            f"{sorted(set(unsupported_rules))!r}."
        )
    single_signatures = {
        str(label): tuple(
            _normalize_condition_ids(
                condition_ids,
                field_name=f"{case.case_id}.single_condition_sets[{label!r}]",
            )
        )
        for label, condition_ids in sorted(case.single_condition_sets.items())
    }
    combined_signature = tuple(
        _normalize_condition_ids(
            case.combined_condition_ids,
            field_name=f"{case.case_id}.combined_condition_ids",
        )
    )

    bundle_by_group_and_signature: dict[tuple[str, tuple[str, ...]], Mapping[str, Any]] = {}
    for bundle in analysis_context["bundle_records"]:
        signature = tuple(bundle["condition_ids"])
        key = (str(bundle["analysis_group_id"]), signature)
        if key in bundle_by_group_and_signature:
            raise ValueError(
                f"AggregationValidationCase {case.case_id!r} found duplicate bundle coverage "
                f"for analysis_group_id {bundle['analysis_group_id']!r} and condition_ids "
                f"{signature!r}."
            )
        bundle_by_group_and_signature[key] = bundle

    required_signatures = [*single_signatures.values(), combined_signature]
    available_signatures = {
        signature for (_group_id, signature) in bundle_by_group_and_signature
    }
    missing_signatures = [
        signature for signature in required_signatures if signature not in available_signatures
    ]
    if missing_signatures:
        raise ValueError(
            f"AggregationValidationCase {case.case_id!r} is missing required condition "
            f"coverage for signatures {missing_signatures!r}."
        )

    findings: list[dict[str, Any]] = []
    group_ids = sorted(
        {
            analysis_group_id
            for analysis_group_id, _signature in bundle_by_group_and_signature
        }
    )
    for analysis_group_id in group_ids:
        bundles_for_group = {
            signature: bundle_by_group_and_signature[(analysis_group_id, signature)]
            for signature in required_signatures
            if (analysis_group_id, signature) in bundle_by_group_and_signature
        }
        if len(bundles_for_group) != len(required_signatures):
            findings.append(
                _build_finding(
                    validator_id=COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID,
                    case_id=case.case_id,
                    check_kind="aggregation_behavior",
                    finding_suffix=f"{analysis_group_id}:combined_vs_sum_of_single_inputs",
                    status=VALIDATION_STATUS_BLOCKED,
                    motif_or_pathway_id=case.motif_id,
                    expected_relationship=(
                        "Each analysis group should include all declared single-input and "
                        "combined-input conditions before aggregation is judged."
                    ),
                    observed_relationship=(
                        f"Analysis group {analysis_group_id!r} provided only "
                        f"{sorted(tuple(signature) for signature in bundles_for_group)!r}."
                    ),
                    provenance={
                        "analysis_group_id": analysis_group_id,
                        "edge_families": edge_diagnostics["edge_families"],
                    },
                    diagnostics={
                        "required_condition_signatures": [list(item) for item in required_signatures],
                        "actionable_diagnostic": (
                            "Rebuild the local deterministic motif bundle so each seed and arm "
                            "covers every declared single-input and combined-input condition."
                        ),
                    },
                    measured_value=None,
                    units="relative_error",
                )
            )
            continue

        single_values: dict[str, float] = {}
        response_summaries: dict[str, Any] = {}
        blocked_reason: str | None = None
        for label, signature in single_signatures.items():
            summary = _compute_signed_window_response_summary(
                bundle=bundles_for_group[signature],
                readout_id=case.target_readout_id,
                window=window,
                policy=policy,
            )
            response_summaries[f"single::{label}"] = summary
            if abs(float(summary["signed_peak_value"])) < float(case.minimum_expected_scale):
                blocked_reason = (
                    f"single condition {label!r} produced only "
                    f"{summary['signed_peak_value']!r}."
                )
                break
            single_values[label] = float(summary["signed_peak_value"])
        combined_summary = _compute_signed_window_response_summary(
            bundle=bundles_for_group[combined_signature],
            readout_id=case.target_readout_id,
            window=window,
            policy=policy,
        )
        response_summaries["combined"] = combined_summary
        if blocked_reason is not None:
            findings.append(
                _build_finding(
                    validator_id=COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID,
                    case_id=case.case_id,
                    check_kind="aggregation_behavior",
                    finding_suffix=f"{analysis_group_id}:combined_vs_sum_of_single_inputs",
                    status=VALIDATION_STATUS_BLOCKED,
                    motif_or_pathway_id=case.motif_id,
                    expected_relationship=(
                        "Single-input motif probes should each produce a measurable signed "
                        "peak so the combined-input summation rule can be tested."
                    ),
                    observed_relationship=blocked_reason,
                    provenance={
                        "analysis_group_id": analysis_group_id,
                        "edge_families": edge_diagnostics["edge_families"],
                    },
                    diagnostics={
                        "response_summaries": response_summaries,
                        "actionable_diagnostic": (
                            "Increase the local deterministic motif drive or inspect the "
                            "readout binding; aggregation cannot be judged when one input has "
                            "no measurable contribution."
                        ),
                    },
                    measured_value=None,
                    units="relative_error",
                )
            )
            continue
        expected_combined = float(sum(single_values.values()))
        observed_combined = float(combined_summary["signed_peak_value"])
        scale = max(abs(expected_combined), float(case.minimum_expected_scale))
        relative_error = abs(observed_combined - expected_combined) / scale
        status = _classify_max_threshold(
            observed_value=relative_error,
            pass_threshold=float(case.pass_relative_error),
            review_threshold=float(case.review_relative_error),
        )
        findings.append(
            _build_finding(
                validator_id=COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID,
                case_id=case.case_id,
                check_kind="aggregation_behavior",
                finding_suffix=f"{analysis_group_id}:combined_vs_sum_of_single_inputs",
                status=status,
                motif_or_pathway_id=case.motif_id,
                expected_relationship=(
                    "Combined-input response should approximate the sum of the single-input "
                    "responses because the selected edge families preserve sign and delay bins "
                    "before summation."
                ),
                observed_relationship=(
                    f"Combined signed peak was {_rounded_float(observed_combined)} versus "
                    f"expected additive total {_rounded_float(expected_combined)}."
                ),
                provenance={
                    "analysis_group_id": analysis_group_id,
                    "edge_families": edge_diagnostics["edge_families"],
                },
                diagnostics={
                    "single_input_signed_peaks": {
                        label: _rounded_float(value)
                        for label, value in single_values.items()
                    },
                    "observed_combined_signed_peak": _rounded_float(observed_combined),
                    "expected_combined_signed_peak": _rounded_float(expected_combined),
                    "relative_error": _rounded_float(relative_error),
                    "response_summaries": response_summaries,
                    "actionable_diagnostic": (
                        "Inspect delay-bin grouping or runtime accumulation if the combined "
                        "response is no longer close to the sum of the declared single-input "
                        "motifs."
                    ),
                },
                measured_value=_rounded_float(relative_error),
                units="relative_error",
            )
        )
    return findings


def _evaluate_motion_case(case: MotionPathwayAsymmetryCase) -> list[dict[str, Any]]:
    _validate_motion_stimulus_prerequisites(case.bundle_records, case.allowed_stimulus_families)
    analysis_result = compute_shared_readout_analysis(
        analysis_plan=case.analysis_plan,
        bundle_records=case.bundle_records,
    )
    metric_summaries = [
        copy.deepcopy(dict(item))
        for item in analysis_result["metric_summaries"]
    ]
    dsi_by_group_id = {
        str(item["analysis_group_id"]): item
        for item in metric_summaries
        if str(item["metric_id"]) == "direction_selectivity_index"
        and str(item["readout_id"]) == case.readout_id
        and str(item.get("condition_pair_id") or "") == case.condition_pair_id
    }
    preferred_latency_by_group_id = {
        str(item["analysis_group_id"]): item
        for item in metric_summaries
        if str(item["metric_id"]) == "response_latency_to_peak_ms"
        and str(item["readout_id"]) == case.readout_id
        and case.preferred_condition_id in set(item["condition_ids"])
    }
    null_latency_by_group_id = {
        str(item["analysis_group_id"]): item
        for item in metric_summaries
        if str(item["metric_id"]) == "response_latency_to_peak_ms"
        and str(item["readout_id"]) == case.readout_id
        and case.null_condition_id in set(item["condition_ids"])
    }
    analysis_group_ids = sorted(
        set(dsi_by_group_id)
        | set(preferred_latency_by_group_id)
        | set(null_latency_by_group_id)
    )
    if not analysis_group_ids:
        raise ValueError(
            f"MotionPathwayAsymmetryCase {case.case_id!r} did not resolve any shared-readout "
            "analysis summaries for the requested readout and condition pair."
        )

    findings: list[dict[str, Any]] = []
    for analysis_group_id in analysis_group_ids:
        dsi_summary = dsi_by_group_id.get(analysis_group_id)
        preferred_latency = preferred_latency_by_group_id.get(analysis_group_id)
        null_latency = null_latency_by_group_id.get(analysis_group_id)
        provenance = {
            "analysis_group_id": analysis_group_id,
            "pathway_id": case.pathway_id,
            "readout_id": case.readout_id,
            "condition_pair_id": case.condition_pair_id,
        }
        if dsi_summary is None:
            findings.append(
                _build_finding(
                    validator_id=MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID,
                    case_id=case.case_id,
                    check_kind="motion_selectivity_index",
                    finding_suffix=f"{analysis_group_id}:direction_selectivity_index",
                    status=VALIDATION_STATUS_BLOCKED,
                    motif_or_pathway_id=case.pathway_id,
                    expected_relationship=(
                        "The Milestone 12 shared-readout analysis should produce a "
                        "direction_selectivity_index summary for the requested readout."
                    ),
                    observed_relationship=(
                        f"No direction_selectivity_index summary was found for "
                        f"analysis_group_id {analysis_group_id!r}."
                    ),
                    provenance=provenance,
                    diagnostics={
                        "available_metric_summaries": [
                            {
                                "metric_id": item["metric_id"],
                                "analysis_group_id": item["analysis_group_id"],
                                "readout_id": item["readout_id"],
                                "condition_pair_id": item.get("condition_pair_id"),
                                "status": item["status"],
                            }
                            for item in metric_summaries
                            if str(item["analysis_group_id"]) == analysis_group_id
                        ],
                        "actionable_diagnostic": (
                            "Verify that the requested readout is active in the Milestone 12 "
                            "analysis plan and that preferred/null bundles exist for this arm."
                        ),
                    },
                    measured_value=None,
                    units="unitless",
                )
            )
        else:
            dsi_value = dsi_summary["value"]
            if dsi_value is None:
                findings.append(
                    _build_finding(
                        validator_id=MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID,
                        case_id=case.case_id,
                        check_kind="motion_selectivity_index",
                        finding_suffix=f"{analysis_group_id}:direction_selectivity_index",
                        status=VALIDATION_STATUS_BLOCKED,
                        motif_or_pathway_id=case.pathway_id,
                        expected_relationship=(
                            "Preferred-versus-null motion should produce a usable selectivity "
                            "index on the declared pathway readout."
                        ),
                        observed_relationship=(
                            f"Direction-selectivity summary status was {dsi_summary['status']!r}."
                        ),
                        provenance=provenance,
                        diagnostics={
                            "dsi_summary": dsi_summary,
                            "actionable_diagnostic": (
                                "Inspect the preferred/null stimulus bundles or the pathway "
                                "readout binding; the shared-readout layer reported an unusable "
                                "selectivity comparison."
                            ),
                        },
                        measured_value=None,
                        units="unitless",
                    )
                )
            else:
                status = _classify_min_threshold(
                    observed_value=float(dsi_value),
                    pass_threshold=float(case.dsi_pass_threshold),
                    review_threshold=float(case.dsi_review_threshold),
                )
                findings.append(
                    _build_finding(
                        validator_id=MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID,
                        case_id=case.case_id,
                        check_kind="motion_selectivity_index",
                        finding_suffix=f"{analysis_group_id}:direction_selectivity_index",
                        status=status,
                        motif_or_pathway_id=case.pathway_id,
                        expected_relationship=(
                            f"Preferred motion should outrun null motion on readout "
                            f"{case.readout_id!r}, yielding a positive direction_selectivity_index."
                        ),
                        observed_relationship=(
                            f"Observed direction_selectivity_index was {_rounded_float(float(dsi_value))}."
                        ),
                        provenance=provenance,
                        diagnostics={
                            "dsi_summary": dsi_summary,
                            "dsi_thresholds": {
                                "pass": _rounded_float(float(case.dsi_pass_threshold)),
                                "review": _rounded_float(float(case.dsi_review_threshold)),
                            },
                            "actionable_diagnostic": (
                                "Inspect the preferred/null stimulus parameterization or the "
                                "pathway readout if direction selectivity collapsed toward zero."
                            ),
                        },
                        measured_value=_rounded_float(float(dsi_value)),
                        units="unitless",
                    )
                )

        if preferred_latency is None or null_latency is None:
            findings.append(
                _build_finding(
                    validator_id=MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID,
                    case_id=case.case_id,
                    check_kind="preferred_latency_advantage",
                    finding_suffix=f"{analysis_group_id}:preferred_vs_null_latency",
                    status=VALIDATION_STATUS_BLOCKED,
                    motif_or_pathway_id=case.pathway_id,
                    expected_relationship=(
                        "Preferred and null conditions should each yield a usable latency "
                        "summary so pathway asymmetry can be inspected."
                    ),
                    observed_relationship=(
                        f"preferred_summary_present={preferred_latency is not None}, "
                        f"null_summary_present={null_latency is not None}."
                    ),
                    provenance=provenance,
                    diagnostics={
                        "preferred_latency_summary": preferred_latency,
                        "null_latency_summary": null_latency,
                        "actionable_diagnostic": (
                            "Inspect the condition catalog and readout bindings; latency "
                            "ordering cannot be checked without both preferred and null summaries."
                        ),
                    },
                    measured_value=None,
                    units="ms",
                )
            )
            continue
        preferred_value = preferred_latency.get("value")
        null_value = null_latency.get("value")
        if preferred_value is None or null_value is None:
            findings.append(
                _build_finding(
                    validator_id=MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID,
                    case_id=case.case_id,
                    check_kind="preferred_latency_advantage",
                    finding_suffix=f"{analysis_group_id}:preferred_vs_null_latency",
                    status=VALIDATION_STATUS_BLOCKED,
                    motif_or_pathway_id=case.pathway_id,
                    expected_relationship=(
                        "Preferred and null conditions should both provide usable latency values."
                    ),
                    observed_relationship=(
                        f"preferred_status={preferred_latency['status']!r}, "
                        f"null_status={null_latency['status']!r}."
                    ),
                    provenance=provenance,
                    diagnostics={
                        "preferred_latency_summary": preferred_latency,
                        "null_latency_summary": null_latency,
                        "actionable_diagnostic": (
                            "Inspect the shared-readout traces if one pathway condition fell "
                            "below the latency detection threshold."
                        ),
                    },
                    measured_value=None,
                    units="ms",
                )
            )
            continue
        preferred_advantage_ms = float(null_value) - float(preferred_value)
        status = _classify_min_threshold(
            observed_value=preferred_advantage_ms,
            pass_threshold=float(case.preferred_advantage_pass_ms),
            review_threshold=float(case.preferred_advantage_review_ms),
        )
        findings.append(
            _build_finding(
                validator_id=MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID,
                case_id=case.case_id,
                check_kind="preferred_latency_advantage",
                finding_suffix=f"{analysis_group_id}:preferred_vs_null_latency",
                status=status,
                motif_or_pathway_id=case.pathway_id,
                expected_relationship=(
                    "Preferred motion should arrive no later than null motion on the same "
                    "pathway readout."
                ),
                observed_relationship=(
                    f"Null-preferred latency delta was {_rounded_float(preferred_advantage_ms)} ms."
                ),
                provenance=provenance,
                diagnostics={
                    "preferred_latency_summary": preferred_latency,
                    "null_latency_summary": null_latency,
                    "preferred_advantage_thresholds_ms": {
                        "pass": _rounded_float(float(case.preferred_advantage_pass_ms)),
                        "review": _rounded_float(float(case.preferred_advantage_review_ms)),
                    },
                    "actionable_diagnostic": (
                        "Inspect pathway timing, condition labeling, or direction handling if "
                        "preferred motion no longer leads or ties the null condition."
                    ),
                },
                measured_value=_rounded_float(preferred_advantage_ms),
                units="ms",
            )
        )
    return findings


def _build_analysis_context(
    *,
    analysis_plan: Mapping[str, Any],
    bundle_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    normalized_plan = _normalize_analysis_plan(analysis_plan)
    normalized_bundles = [
        _normalize_bundle_record(
            record,
            condition_ids_by_id=normalized_plan["condition_ids_by_id"],
        )
        for record in bundle_records
    ]
    return {
        "analysis_plan": normalized_plan,
        "bundle_records": sorted(
            normalized_bundles,
            key=lambda item: (
                str(item["analysis_group_id"]),
                tuple(item["condition_ids"]),
                str(item["bundle_id"]),
            ),
        ),
    }


def _resolve_window_reference(
    analysis_plan: Mapping[str, Any],
    window_id: str,
) -> dict[str, Any]:
    analysis_windows = analysis_plan.get("analysis_window_catalog")
    if not isinstance(analysis_windows, Sequence) or isinstance(
        analysis_windows,
        (str, bytes),
    ):
        raise ValueError("analysis_plan.analysis_window_catalog must be a sequence.")
    for item in analysis_windows:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("window_id")) != window_id:
            continue
        return {
            "window_id": str(item["window_id"]),
            "start_ms": float(item["start_ms"]),
            "end_ms": float(item["end_ms"]),
            "description": str(item.get("description", window_id)),
        }
    raise ValueError(f"analysis_plan does not define window_id {window_id!r}.")


def _compute_signed_window_response_summary(
    *,
    bundle: Mapping[str, Any],
    readout_id: str,
    window: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    summary = _compute_window_response_summary(
        bundle=bundle,
        readout_id=readout_id,
        window=window,
        policy=policy,
    )
    baseline_subtracted = np.asarray(
        summary["baseline_subtracted_values"],
        dtype=np.float64,
    )
    window_time_ms = np.asarray(summary["window_time_ms"], dtype=np.float64)
    if baseline_subtracted.size == 0:
        signed_peak_index = 0
        signed_peak_value = 0.0
        signed_peak_time_ms = float(window["start_ms"])
    else:
        signed_peak_index = int(np.argmax(np.abs(baseline_subtracted)))
        signed_peak_value = float(baseline_subtracted[signed_peak_index])
        signed_peak_time_ms = float(window_time_ms[signed_peak_index])
    return {
        **summary,
        "signed_peak_value": _rounded_float(signed_peak_value),
        "signed_peak_time_ms": _rounded_float(signed_peak_time_ms),
        "signed_peak_latency_ms": _rounded_float(
            signed_peak_time_ms - float(window["start_ms"])
        ),
        "signed_peak_label": (
            "positive"
            if signed_peak_value > 0.0
            else "negative"
            if signed_peak_value < 0.0
            else "zero"
        ),
    }


def _load_edge_family_diagnostics(
    edge_bundle_paths: Sequence[str | Path],
) -> dict[str, Any]:
    edge_families: list[dict[str, Any]] = []
    weighted_delay_numerator = 0.0
    weighted_delay_denominator = 0.0
    net_signed_weight = 0.0
    aggregation_rules: list[str] = []
    for raw_path in edge_bundle_paths:
        path = Path(raw_path).resolve()
        if not path.exists():
            raise ValueError(f"Required coupling bundle does not exist: {path}.")
        bundle = load_edge_coupling_bundle(path)
        component_table = bundle.component_table.sort_values(
            ["component_index", "component_id"],
            kind="mergesort",
        ).reset_index(drop=True)
        component_records: list[dict[str, Any]] = []
        for row in component_table.itertuples(index=False):
            weight_magnitude = abs(float(row.signed_weight_total))
            weighted_delay_numerator += float(row.delay_ms) * weight_magnitude
            weighted_delay_denominator += weight_magnitude
            net_signed_weight += float(row.signed_weight_total)
            component_records.append(
                {
                    "component_id": str(row.component_id),
                    "delay_ms": _rounded_float(float(row.delay_ms)),
                    "sign_label": str(row.sign_label),
                    "signed_weight_total": _rounded_float(float(row.signed_weight_total)),
                    "synapse_count": int(row.synapse_count),
                }
            )
        aggregation_rules.append(str(bundle.aggregation_rule))
        edge_families.append(
            {
                "bundle_path": str(path),
                "pre_root_id": int(bundle.pre_root_id),
                "post_root_id": int(bundle.post_root_id),
                "status": str(bundle.status),
                "aggregation_rule": str(bundle.aggregation_rule),
                "delay_model": str(bundle.delay_model),
                "net_signed_weight": _rounded_float(
                    float(component_table["signed_weight_total"].sum())
                )
                if not component_table.empty
                else 0.0,
                "component_count": int(len(component_table)),
                "components": component_records,
            }
        )
    weighted_mean_delay_ms = (
        weighted_delay_numerator / weighted_delay_denominator
        if weighted_delay_denominator > 0.0
        else 0.0
    )
    net_sign = 1 if net_signed_weight > 0.0 else -1 if net_signed_weight < 0.0 else 0
    return {
        "edge_families": edge_families,
        "weighted_mean_delay_ms": _rounded_float(float(weighted_mean_delay_ms)),
        "net_signed_weight": _rounded_float(float(net_signed_weight)),
        "net_sign": int(net_sign),
        "aggregation_rules": sorted(set(aggregation_rules)),
    }


def _validate_motion_stimulus_prerequisites(
    bundle_records: Sequence[Mapping[str, Any]],
    allowed_families: Sequence[str],
) -> None:
    normalized_allowed = set(str(item) for item in allowed_families)
    discovered_families: set[str] = set()
    for record in bundle_records:
        metadata = dict(record["bundle_metadata"])
        stimulus_metadata = _load_bundle_stimulus_metadata(metadata)
        discovered_families.add(str(stimulus_metadata["stimulus_family"]))
    unsupported = sorted(discovered_families - normalized_allowed)
    if unsupported:
        raise ValueError(
            "Motion-pathway asymmetry requires canonical motion stimuli, but bundle "
            f"records used unsupported stimulus families {unsupported!r}."
        )


def _load_bundle_stimulus_metadata(
    bundle_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    selected_assets = bundle_metadata.get("selected_assets")
    if not isinstance(selected_assets, Sequence) or isinstance(
        selected_assets,
        (str, bytes),
    ):
        raise ValueError("simulator bundle selected_assets must be a sequence.")
    for item in selected_assets:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("asset_role")) != "input_bundle":
            continue
        if str(item.get("artifact_type")) != "stimulus_bundle":
            continue
        return load_stimulus_bundle_metadata(item["path"])
    raise ValueError(
        f"Simulator bundle {bundle_metadata.get('bundle_id')!r} is missing an input stimulus bundle asset."
    )


def _build_finding(
    *,
    validator_id: str,
    case_id: str,
    check_kind: str,
    finding_suffix: str,
    status: str,
    motif_or_pathway_id: str,
    expected_relationship: str,
    observed_relationship: str,
    provenance: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    measured_value: float | None,
    units: str,
) -> dict[str, Any]:
    return {
        "finding_id": f"{validator_id}:{case_id}:{finding_suffix}",
        "validator_id": validator_id,
        "case_id": case_id,
        "check_kind": check_kind,
        "status": status,
        "motif_or_pathway_id": motif_or_pathway_id,
        "expected_relationship": expected_relationship,
        "observed_relationship": observed_relationship,
        "measured_value": measured_value,
        "units": units,
        "provenance": copy.deepcopy(dict(provenance)),
        "diagnostics": copy.deepcopy(dict(diagnostics)),
    }


def _bundle_level_provenance(
    *,
    bundle: Mapping[str, Any],
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "bundle_id": str(bundle["bundle_id"]),
        "analysis_group_id": str(bundle["analysis_group_id"]),
        "arm_id": str(bundle["arm_id"]),
        "model_mode": str(bundle["model_mode"]),
        "baseline_family": bundle["baseline_family"],
        "seed": int(bundle["seed"]),
        "condition_ids": list(bundle["condition_ids"]),
        "condition_signature": str(bundle["condition_signature"]),
    }
    if extra is not None:
        payload.update(copy.deepcopy(dict(extra)))
    return payload


def _build_case_summary(
    case_definition: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        **copy.deepcopy(dict(case_definition)),
        "status": _worst_status(str(item["status"]) for item in findings),
        "finding_count": len(findings),
        "finding_ids": [str(item["finding_id"]) for item in findings],
        "status_counts": {
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
        },
    }


def _group_findings_by_validator(
    findings: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in findings:
        grouped.setdefault(str(item["validator_id"]), []).append(copy.deepcopy(dict(item)))
    return {
        validator_id: sorted(
            validator_findings,
            key=lambda finding: str(finding["finding_id"]),
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
                str(item["status"]) for item in validator_findings
            ),
            "finding_count": len(validator_findings),
            "case_count": len({str(item["case_id"]) for item in validator_findings}),
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
        "# Circuit Validation Report",
        "",
        f"- Bundle ID: `{summary_payload['bundle_id']}`",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Case count: `{len(summary_payload['case_summaries'])}`",
        "",
        "## Validators",
        "",
    ]
    validator_summaries = summary_payload["layers"][0]["validator_families"][0]["validators"]
    for item in validator_summaries:
        lines.append(
            f"- `{item['validator_id']}`: `{item['status']}` "
            f"({item['finding_count']} findings across {item['case_count']} cases)"
        )
    for validator_id, findings in findings_by_validator.items():
        lines.extend(["", f"## {validator_id}", ""])
        for finding in findings:
            lines.append(
                f"- `{finding['status']}` `{finding['finding_id']}`: {finding['observed_relationship']}"
            )
            lines.append(f"  expected: {finding['expected_relationship']}")
            action = dict(finding["diagnostics"]).get("actionable_diagnostic")
            if action:
                lines.append(f"  action: {action}")
    lines.append("")
    return "\n".join(lines)


def _resolve_active_circuit_validator_ids(
    validation_config: Mapping[str, Any],
) -> list[str]:
    circuit_validator_ids = [
        COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID,
        MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID,
    ]
    requested_validator_ids = list(validation_config["active_validator_ids"])
    if requested_validator_ids:
        active = [
            validator_id
            for validator_id in circuit_validator_ids
            if validator_id in set(requested_validator_ids)
        ]
        if not active:
            raise ValueError(
                "validation.active_validator_ids excludes the circuit validators "
                "required by the circuit validation workflow."
            )
        return active
    requested_family_ids = list(validation_config["active_validator_family_ids"])
    if requested_family_ids and CIRCUIT_RESPONSE_FAMILY_ID not in set(requested_family_ids):
        raise ValueError(
            "validation.active_validator_family_ids excludes circuit_response, so "
            "the circuit validation workflow has no active validators to execute."
        )
    return circuit_validator_ids


def _resolve_circuit_criteria_assignments(
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
        elif CIRCUIT_RESPONSE_FAMILY_ID in family_overrides:
            reference = family_overrides[CIRCUIT_RESPONSE_FAMILY_ID]
            source = "validator_family_override"
        elif CIRCUIT_SANITY_LAYER_ID in layer_overrides:
            reference = layer_overrides[CIRCUIT_SANITY_LAYER_ID]
            source = "layer_override"
        else:
            reference = _DEFAULT_CIRCUIT_CRITERIA_BY_VALIDATOR[validator_id]
            source = "validator_contract_default"
        assignments.append(
            {
                "validator_id": validator_id,
                "criteria_profile_reference": str(reference),
                "criteria_profile_source": source,
            }
        )
    return sorted(assignments, key=lambda item: item["validator_id"])


def _classify_min_threshold(
    *,
    observed_value: float,
    pass_threshold: float,
    review_threshold: float,
) -> str:
    if observed_value >= pass_threshold:
        return VALIDATION_STATUS_PASS
    if observed_value >= review_threshold:
        return VALIDATION_STATUS_REVIEW
    return VALIDATION_STATUS_BLOCKING


def _classify_max_threshold(
    *,
    observed_value: float,
    pass_threshold: float,
    review_threshold: float,
) -> str:
    if observed_value <= pass_threshold:
        return VALIDATION_STATUS_PASS
    if observed_value <= review_threshold:
        return VALIDATION_STATUS_REVIEW
    return VALIDATION_STATUS_BLOCKING


def _worst_status(statuses: Sequence[str] | Any) -> str:
    normalized = [str(status) for status in statuses]
    if not normalized:
        return VALIDATION_STATUS_BLOCKED
    return max(
        normalized,
        key=lambda item: _STATUS_RANK.get(item, _STATUS_RANK[VALIDATION_STATUS_BLOCKING]),
    )


def _require_nonempty_case_id(value: str, *, case_kind: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{case_kind} requires a non-empty case_id.")


def _require_nonempty_string(value: Any, *, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return normalized


def _require_nonempty_bundle_records(
    bundle_records: Sequence[Mapping[str, Any]],
    *,
    field_name: str,
) -> None:
    if not isinstance(bundle_records, Sequence) or isinstance(
        bundle_records,
        (str, bytes),
    ):
        raise ValueError(f"{field_name} must be a sequence of bundle records.")
    if not bundle_records:
        raise ValueError(f"{field_name} must not be empty.")


def _require_nonempty_paths(
    paths: Sequence[str | Path],
    *,
    field_name: str,
) -> None:
    if not isinstance(paths, Sequence) or isinstance(paths, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of paths.")
    if not paths:
        raise ValueError(f"{field_name} must not be empty.")
    for path in paths:
        if not str(path).strip():
            raise ValueError(f"{field_name} contains an empty path.")


def _require_nonempty_string_sequence(
    values: Sequence[Any],
    *,
    field_name: str,
) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of strings.")
    normalized = [str(item).strip() for item in values]
    if not normalized or any(not item for item in normalized):
        raise ValueError(f"{field_name} must contain at least one non-empty string.")
    return normalized


def _normalize_condition_ids(
    condition_ids: Sequence[Any],
    *,
    field_name: str,
) -> list[str]:
    return sorted(_require_nonempty_string_sequence(condition_ids, field_name=field_name))


__all__ = [
    "AggregationValidationCase",
    "CIRCUIT_VALIDATION_PLAN_VERSION",
    "CIRCUIT_VALIDATION_REPORT_VERSION",
    "DelayValidationCase",
    "MotionPathwayAsymmetryCase",
    "SignValidationCase",
    "build_motion_pathway_asymmetry_cases_from_bundle_set",
    "execute_circuit_validation_workflow",
    "resolve_circuit_validation_plan",
    "run_circuit_validation_suite",
]
