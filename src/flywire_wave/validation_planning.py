from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .config import get_config_path, get_project_root, load_config
from .experiment_analysis_contract import (
    EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID,
    build_experiment_analysis_bundle_paths,
    build_experiment_analysis_bundle_reference,
    build_experiment_analysis_spec_hash,
    load_experiment_analysis_bundle_metadata,
    parse_experiment_analysis_bundle_metadata,
)
from .experiment_comparison_analysis import discover_experiment_bundle_set
from .hybrid_morphology_contract import (
    HYBRID_MORPHOLOGY_PROMOTION_ORDER,
    normalize_hybrid_morphology_class,
)
from .mixed_fidelity_inspection import build_mixed_fidelity_inspection_output_dir
from .operator_qa import build_operator_qa_output_dir
from .simulation_planning import (
    resolve_manifest_simulation_plan,
)
from .simulator_result_contract import SURFACE_WAVE_MODEL_MODE
from .stimulus_contract import (
    _normalize_float,
    _normalize_identifier,
    _normalize_nonempty_string,
    _normalize_positive_int,
)
from .surface_wave_inspection import (
    build_surface_wave_inspection_output_dir,
    load_surface_wave_sweep_spec,
    normalize_surface_wave_sweep_spec,
)
from .validation_contract import (
    CIRCUIT_RESPONSE_FAMILY_ID,
    COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID,
    EXPERIMENT_SHARED_ANALYSIS_SCOPE,
    GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID,
    MIXED_FIDELITY_INSPECTION_SCOPE,
    MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID,
    MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID,
    NUMERICAL_SANITY_LAYER_ID,
    OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID,
    OPERATOR_QA_REVIEW_SCOPE,
    SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID,
    SURFACE_WAVE_INSPECTION_SCOPE,
    SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
    TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
    TASK_EFFECT_REPRODUCIBILITY_FAMILY_ID,
    build_validation_bundle_metadata,
    build_validation_contract_reference,
    build_validation_ladder_contract_metadata,
    build_validation_plan_reference,
    parse_validation_ladder_contract_metadata,
)


VALIDATION_CONFIG_VERSION = "validation_config.v1"
VALIDATION_PLAN_VERSION = "validation_plan.v1"
VALIDATION_STABLE_LAYER_ORDERING = "contract_sequence_index"
VALIDATION_STABLE_BUNDLE_ORDERING = "arm_id_seed_condition_signature"
VALIDATION_STABLE_PERTURBATION_ORDERING = "suite_id_then_variant_id"
VALIDATION_STABLE_CRITERIA_ORDERING = "validator_id_ascending"

TIMESTEP_SWEEPS_SUITE_ID = "timestep_sweeps"
GEOMETRY_VARIANTS_SUITE_ID = "geometry_variants"
SIGN_DELAY_PERTURBATIONS_SUITE_ID = "sign_delay_perturbations"
NOISE_ROBUSTNESS_SUITE_ID = "noise_robustness"
VALIDATION_PERTURBATION_SUITE_ORDER = (
    TIMESTEP_SWEEPS_SUITE_ID,
    GEOMETRY_VARIANTS_SUITE_ID,
    SIGN_DELAY_PERTURBATIONS_SUITE_ID,
    NOISE_ROBUSTNESS_SUITE_ID,
)

SUPPORTED_SIGN_DELAY_VARIANT_IDS = (
    "as_recorded",
    "sign_inversion_probe",
    "zero_delay_probe",
    "delay_scale_half_probe",
)

ALLOWED_VALIDATION_CONFIG_KEYS = {
    "version",
    "active_layer_ids",
    "active_validator_family_ids",
    "active_validator_ids",
    "criteria_profiles",
    "perturbation_suites",
}
ALLOWED_CRITERIA_PROFILE_KEYS = {
    "layer_overrides",
    "validator_family_overrides",
    "validator_overrides",
}
ALLOWED_PERTURBATION_SUITE_KEYS = set(VALIDATION_PERTURBATION_SUITE_ORDER)
ALLOWED_TIMESTEP_SWEEP_KEYS = {
    "enabled",
    "sweep_spec_paths",
    "use_manifest_seed_sweep",
}
ALLOWED_GEOMETRY_VARIANT_KEYS = {
    "enabled",
    "variant_ids",
}
ALLOWED_SIGN_DELAY_KEYS = {
    "enabled",
    "variant_ids",
}
ALLOWED_NOISE_ROBUSTNESS_KEYS = {
    "enabled",
    "seed_values",
    "noise_levels",
}

VALIDATOR_COMPARISON_GROUP_KINDS = {
    GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID: {"geometry_ablation"},
    COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID: {
        "matched_surface_wave_vs_baseline",
        "baseline_strength_challenge",
    },
    MOTION_PATHWAY_ASYMMETRY_VALIDATOR_ID: {"matched_surface_wave_vs_baseline"},
    SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID: {
        "matched_surface_wave_vs_baseline",
        "geometry_ablation",
        "baseline_strength_challenge",
    },
    TASK_DECODER_ROBUSTNESS_VALIDATOR_ID: {
        "matched_surface_wave_vs_baseline",
        "geometry_ablation",
        "baseline_strength_challenge",
    },
}
VALIDATOR_SUITE_IDS = {
    SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID: {TIMESTEP_SWEEPS_SUITE_ID},
    GEOMETRY_DEPENDENCE_COLLAPSE_VALIDATOR_ID: {GEOMETRY_VARIANTS_SUITE_ID},
    COUPLING_SEMANTICS_CONTINUITY_VALIDATOR_ID: {SIGN_DELAY_PERTURBATIONS_SUITE_ID},
    SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID: {
        GEOMETRY_VARIANTS_SUITE_ID,
        NOISE_ROBUSTNESS_SUITE_ID,
    },
    TASK_DECODER_ROBUSTNESS_VALIDATOR_ID: {
        SIGN_DELAY_PERTURBATIONS_SUITE_ID,
        NOISE_ROBUSTNESS_SUITE_ID,
    },
}
EVIDENCE_SCOPE_ARTIFACT_KEYS = {
    OPERATOR_QA_REVIEW_SCOPE: "operator_qa",
    SURFACE_WAVE_INSPECTION_SCOPE: "surface_wave_inspection",
    MIXED_FIDELITY_INSPECTION_SCOPE: "mixed_fidelity_inspection",
    EXPERIMENT_SHARED_ANALYSIS_SCOPE: "experiment_analysis_bundle",
    "experiment_wave_diagnostics": "experiment_analysis_bundle",
    "experiment_null_tests": "experiment_analysis_bundle",
    "simulator_shared_readout": "simulator_result_bundles",
}


def normalize_validation_config(
    payload: Mapping[str, Any] | None,
    *,
    project_root: Path,
) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError("validation must be a mapping when provided.")
    unknown_keys = sorted(set(raw_payload) - ALLOWED_VALIDATION_CONFIG_KEYS)
    if unknown_keys:
        raise ValueError(
            "validation contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    version = _normalize_nonempty_string(
        raw_payload.get("version", VALIDATION_CONFIG_VERSION),
        field_name="validation.version",
    )
    if version != VALIDATION_CONFIG_VERSION:
        raise ValueError(
            f"validation.version must be {VALIDATION_CONFIG_VERSION!r}."
        )
    return {
        "version": version,
        "active_layer_ids": _normalize_identifier_list(
            raw_payload.get("active_layer_ids", []),
            field_name="validation.active_layer_ids",
            allow_empty=True,
        ),
        "active_validator_family_ids": _normalize_identifier_list(
            raw_payload.get("active_validator_family_ids", []),
            field_name="validation.active_validator_family_ids",
            allow_empty=True,
        ),
        "active_validator_ids": _normalize_identifier_list(
            raw_payload.get("active_validator_ids", []),
            field_name="validation.active_validator_ids",
            allow_empty=True,
        ),
        "criteria_profiles": _normalize_criteria_profile_overrides(
            raw_payload.get("criteria_profiles"),
        ),
        "perturbation_suites": _normalize_perturbation_suite_config(
            raw_payload.get("perturbation_suites"),
            project_root=project_root,
        ),
    }


def resolve_manifest_validation_plan(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    simulation_plan = resolve_manifest_simulation_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    return resolve_validation_plan(
        config_path=config_path,
        simulation_plan=simulation_plan,
        contract_metadata=contract_metadata,
    )


def resolve_validation_plan(
    *,
    config_path: str | Path,
    simulation_plan: Mapping[str, Any] | None = None,
    analysis_plan: Mapping[str, Any] | None = None,
    bundle_set: Mapping[str, Any] | None = None,
    analysis_bundle_metadata: Mapping[str, Any] | None = None,
    analysis_bundle_metadata_path: str | Path | None = None,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = load_config(config_path)
    config_file = get_config_path(cfg)
    project_root = get_project_root(cfg)
    if config_file is None or project_root is None:
        raise ValueError("Loaded config is missing config metadata.")
    normalized_config = normalize_validation_config(
        cfg.get("validation"),
        project_root=project_root,
    )
    normalized_contract = parse_validation_ladder_contract_metadata(
        contract_metadata
        if contract_metadata is not None
        else build_validation_ladder_contract_metadata()
    )
    resolved_simulation_plan = _resolve_simulation_plan(simulation_plan)
    resolved_analysis_plan = _resolve_analysis_plan(
        analysis_plan=analysis_plan,
        simulation_plan=resolved_simulation_plan,
    )
    selection = _resolve_validation_selection(
        validation_config=normalized_config,
        contract_metadata=normalized_contract,
    )
    requires_result_bundles = _selection_requires_upstream_contract(
        selection=selection,
        contract_name="simulator_result_bundle.v1",
    )
    requires_analysis_bundle = _selection_requires_upstream_contract(
        selection=selection,
        contract_name="experiment_analysis_bundle.v1",
    )
    resolved_bundle_set = _resolve_bundle_set(
        bundle_set=bundle_set,
        simulation_plan=resolved_simulation_plan,
        analysis_plan=resolved_analysis_plan,
        require_result_bundles=requires_result_bundles,
    )
    resolved_analysis_bundle = _resolve_analysis_bundle_metadata(
        analysis_bundle_metadata=analysis_bundle_metadata,
        analysis_bundle_metadata_path=analysis_bundle_metadata_path,
        analysis_plan=resolved_analysis_plan,
        bundle_set=resolved_bundle_set,
        require_analysis_bundle=requires_analysis_bundle,
    )
    comparison_groups = _build_comparison_groups(resolved_analysis_plan)
    seed_aggregation_rules = [
        copy.deepcopy(dict(item))
        for item in resolved_analysis_plan.get("seed_aggregation_rules", [])
    ]
    criteria_assignments = _resolve_criteria_profile_assignments(
        validation_config=normalized_config,
        selection=selection,
        contract_metadata=normalized_contract,
    )
    perturbation_suites = _resolve_perturbation_suites(
        cfg=cfg,
        simulation_plan=resolved_simulation_plan,
        bundle_set=resolved_bundle_set,
        selection=selection,
        validation_config=normalized_config,
        comparison_groups=comparison_groups,
    )
    target_artifact_references = _build_target_artifact_references(
        cfg=cfg,
        simulation_plan=resolved_simulation_plan,
        bundle_set=resolved_bundle_set,
        analysis_bundle_metadata=resolved_analysis_bundle,
        selection=selection,
        perturbation_suites=perturbation_suites,
    )
    plan_reference = build_validation_plan_reference(
        experiment_id=str(resolved_simulation_plan["manifest_reference"]["experiment_id"]),
        contract_reference=build_validation_contract_reference(normalized_contract),
        active_layer_ids=selection["active_layer_ids"],
        active_validator_family_ids=selection["active_validator_family_ids"],
        active_validator_ids=selection["active_validator_ids"],
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
        evidence_bundle_references=_build_evidence_bundle_references(
            bundle_set=resolved_bundle_set,
            analysis_bundle_metadata=resolved_analysis_bundle,
        ),
        target_arm_ids=(
            []
            if resolved_bundle_set is None
            else list(resolved_bundle_set["expected_arm_ids"])
        ),
        comparison_group_ids=[item["group_id"] for item in comparison_groups],
        perturbation_suite_references=[
            {
                "suite_id": item["suite_id"],
                "suite_kind": item["suite_kind"],
                "target_layer_ids": item["target_layer_ids"],
                "target_validator_ids": item["target_validator_ids"],
                "variant_ids": [variant["variant_id"] for variant in item["variants"]],
            }
            for item in perturbation_suites
        ],
        plan_version=VALIDATION_PLAN_VERSION,
    )
    bundle_metadata = build_validation_bundle_metadata(
        validation_plan_reference=plan_reference,
        processed_simulator_results_dir=cfg["paths"]["processed_simulator_results_dir"],
        contract_metadata=normalized_contract,
    )
    bundle_directory = Path(bundle_metadata["bundle_layout"]["bundle_directory"]).resolve()
    _attach_validation_output_locations(
        perturbation_suites=perturbation_suites,
        bundle_directory=bundle_directory,
    )
    group_arm_ids = _resolve_group_arm_ids(comparison_groups)
    active_layers = _build_active_layer_records(
        selection=selection,
        criteria_assignments=criteria_assignments,
        perturbation_suites=perturbation_suites,
        bundle_set=resolved_bundle_set,
        comparison_groups=comparison_groups,
        group_arm_ids=group_arm_ids,
    )
    return {
        "plan_version": VALIDATION_PLAN_VERSION,
        "manifest_reference": copy.deepcopy(
            dict(resolved_simulation_plan["manifest_reference"])
        ),
        "contract_reference": copy.deepcopy(dict(plan_reference["contract_reference"])),
        "validation_config": normalized_config,
        "config_reference": {
            "config_path": str(config_file.resolve()),
            "project_root": str(project_root.resolve()),
        },
        "stable_layer_ordering": VALIDATION_STABLE_LAYER_ORDERING,
        "stable_bundle_ordering": VALIDATION_STABLE_BUNDLE_ORDERING,
        "stable_perturbation_ordering": VALIDATION_STABLE_PERTURBATION_ORDERING,
        "stable_criteria_ordering": VALIDATION_STABLE_CRITERIA_ORDERING,
        "active_layer_ids": list(selection["active_layer_ids"]),
        "active_validator_family_ids": list(selection["active_validator_family_ids"]),
        "active_validator_ids": list(selection["active_validator_ids"]),
        "active_layers": active_layers,
        "criteria_profile_assignments": criteria_assignments,
        "criteria_profile_references": list(plan_reference["criteria_profile_references"]),
        "seed_aggregation_rules": seed_aggregation_rules,
        "comparison_groups": comparison_groups,
        "perturbation_suites": perturbation_suites,
        "target_artifact_references": target_artifact_references,
        "validation_plan_reference": plan_reference,
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


def _resolve_simulation_plan(plan: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(plan, Mapping):
        raise ValueError(
            "resolve_validation_plan requires a normalized simulation_plan or the "
            "manifest wrapper entrypoint."
        )
    return copy.deepcopy(dict(plan))


def _resolve_analysis_plan(
    *,
    analysis_plan: Mapping[str, Any] | None,
    simulation_plan: Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(analysis_plan, Mapping):
        return copy.deepcopy(dict(analysis_plan))
    embedded = simulation_plan.get("readout_analysis_plan")
    if not isinstance(embedded, Mapping):
        raise ValueError(
            "simulation_plan is missing readout_analysis_plan required for validation planning."
        )
    return copy.deepcopy(dict(embedded))


def _resolve_bundle_set(
    *,
    bundle_set: Mapping[str, Any] | None,
    simulation_plan: Mapping[str, Any],
    analysis_plan: Mapping[str, Any],
    require_result_bundles: bool,
) -> dict[str, Any] | None:
    if isinstance(bundle_set, Mapping):
        return copy.deepcopy(dict(bundle_set))
    if not require_result_bundles:
        return None
    try:
        return discover_experiment_bundle_set(
            simulation_plan=simulation_plan,
            analysis_plan=analysis_plan,
        )
    except ValueError as exc:
        raise ValueError(
            f"Validation planning could not resolve local simulator bundle coverage: {exc}"
        ) from exc


def _resolve_analysis_bundle_metadata(
    *,
    analysis_bundle_metadata: Mapping[str, Any] | None,
    analysis_bundle_metadata_path: str | Path | None,
    analysis_plan: Mapping[str, Any],
    bundle_set: Mapping[str, Any] | None,
    require_analysis_bundle: bool,
) -> dict[str, Any] | None:
    if isinstance(analysis_bundle_metadata, Mapping):
        return parse_experiment_analysis_bundle_metadata(analysis_bundle_metadata)
    if analysis_bundle_metadata_path is not None:
        return load_experiment_analysis_bundle_metadata(analysis_bundle_metadata_path)
    if not require_analysis_bundle:
        return None
    if not isinstance(bundle_set, Mapping):
        raise ValueError(
            "Validation planning requires a local experiment_analysis_bundle but the "
            "bundle_set prerequisite was not resolved."
        )
    expected_paths = build_experiment_analysis_bundle_paths(
        experiment_id=str(analysis_plan["manifest_reference"]["experiment_id"]),
        analysis_spec_hash=build_experiment_analysis_spec_hash(analysis_plan),
        processed_simulator_results_dir=str(bundle_set["processed_simulator_results_dir"]),
    )
    metadata_path = expected_paths.metadata_json_path.resolve()
    if not metadata_path.exists():
        raise ValueError(
            "Validation planning requires a local experiment_analysis_bundle for the "
            f"active validators, but metadata was not found at {metadata_path}."
        )
    return load_experiment_analysis_bundle_metadata(metadata_path)


def _resolve_validation_selection(
    *,
    validation_config: Mapping[str, Any],
    contract_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    layers = [copy.deepcopy(dict(item)) for item in contract_metadata["layer_catalog"]]
    families = [
        copy.deepcopy(dict(item))
        for item in contract_metadata["validator_family_catalog"]
    ]
    validators = [
        copy.deepcopy(dict(item))
        for item in contract_metadata["validator_catalog"]
    ]
    layer_by_id = {item["layer_id"]: item for item in layers}
    family_by_id = {item["validator_family_id"]: item for item in families}
    validator_by_id = {item["validator_id"]: item for item in validators}

    active_layer_ids = list(validation_config["active_layer_ids"]) or [
        item["layer_id"] for item in layers
    ]
    unknown_layer_ids = sorted(set(active_layer_ids) - set(layer_by_id))
    if unknown_layer_ids:
        raise ValueError(
            f"validation.active_layer_ids references unknown layer ids {unknown_layer_ids!r}."
        )
    active_layer_ids = [item["layer_id"] for item in layers if item["layer_id"] in set(active_layer_ids)]

    candidate_family_ids = [
        item["validator_family_id"]
        for item in families
        if item["layer_id"] in set(active_layer_ids)
    ]
    requested_family_ids = list(validation_config["active_validator_family_ids"])
    if requested_family_ids:
        unknown_family_ids = sorted(set(requested_family_ids) - set(family_by_id))
        if unknown_family_ids:
            raise ValueError(
                "validation.active_validator_family_ids references unknown validator family "
                f"ids {unknown_family_ids!r}."
            )
        disallowed_family_ids = sorted(
            set(requested_family_ids) - set(candidate_family_ids)
        )
        if disallowed_family_ids:
            raise ValueError(
                "validation.active_validator_family_ids references families outside the "
                f"active layers: {disallowed_family_ids!r}."
            )
        active_family_ids = [
            family_id
            for family_id in candidate_family_ids
            if family_id in set(requested_family_ids)
        ]
    else:
        active_family_ids = list(candidate_family_ids)

    candidate_validator_ids = [
        item["validator_id"]
        for item in validators
        if item["validator_family_id"] in set(active_family_ids)
    ]
    requested_validator_ids = list(validation_config["active_validator_ids"])
    if requested_validator_ids:
        unknown_validator_ids = sorted(
            set(requested_validator_ids) - set(validator_by_id)
        )
        if unknown_validator_ids:
            raise ValueError(
                "validation.active_validator_ids references unknown validator ids "
                f"{unknown_validator_ids!r}."
            )
        disallowed_validator_ids = sorted(
            set(requested_validator_ids) - set(candidate_validator_ids)
        )
        if disallowed_validator_ids:
            raise ValueError(
                "validation.active_validator_ids references validators outside the active "
                f"layer/family selection: {disallowed_validator_ids!r}."
            )
        active_validator_ids = [
            validator_id
            for validator_id in candidate_validator_ids
            if validator_id in set(requested_validator_ids)
        ]
    else:
        active_validator_ids = list(candidate_validator_ids)
    if not active_validator_ids:
        raise ValueError("Validation planning requires at least one active validator.")

    active_family_ids = [
        family_id
        for family_id in active_family_ids
        if any(
            validator_by_id[validator_id]["validator_family_id"] == family_id
            for validator_id in active_validator_ids
        )
    ]
    active_layer_ids = [
        layer_id
        for layer_id in active_layer_ids
        if any(
            family_by_id[family_id]["layer_id"] == layer_id
            for family_id in active_family_ids
        )
    ]
    return {
        "active_layer_ids": active_layer_ids,
        "active_validator_family_ids": active_family_ids,
        "active_validator_ids": active_validator_ids,
        "layer_by_id": layer_by_id,
        "family_by_id": family_by_id,
        "validator_by_id": validator_by_id,
    }


def _selection_requires_upstream_contract(
    *,
    selection: Mapping[str, Any],
    contract_name: str,
) -> bool:
    validator_by_id = selection["validator_by_id"]
    return any(
        contract_name in set(validator_by_id[validator_id]["required_upstream_contracts"])
        for validator_id in selection["active_validator_ids"]
    )


def _resolve_criteria_profile_assignments(
    *,
    validation_config: Mapping[str, Any],
    selection: Mapping[str, Any],
    contract_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    overrides = validation_config["criteria_profiles"]
    layer_by_id = selection["layer_by_id"]
    family_by_id = selection["family_by_id"]
    validator_by_id = selection["validator_by_id"]
    allowed_profiles = {
        item["criteria_profile_reference"]
        for item in contract_metadata["validator_catalog"]
    } | {
        item["default_criteria_profile_reference"]
        for item in contract_metadata["validator_family_catalog"]
    }
    _validate_override_mapping_keys(
        overrides["layer_overrides"],
        known_ids=set(layer_by_id),
        field_name="validation.criteria_profiles.layer_overrides",
    )
    _validate_override_mapping_keys(
        overrides["validator_family_overrides"],
        known_ids=set(family_by_id),
        field_name="validation.criteria_profiles.validator_family_overrides",
    )
    _validate_override_mapping_keys(
        overrides["validator_overrides"],
        known_ids=set(validator_by_id),
        field_name="validation.criteria_profiles.validator_overrides",
    )
    for field_name, mapping in (
        ("validation.criteria_profiles.layer_overrides", overrides["layer_overrides"]),
        (
            "validation.criteria_profiles.validator_family_overrides",
            overrides["validator_family_overrides"],
        ),
        (
            "validation.criteria_profiles.validator_overrides",
            overrides["validator_overrides"],
        ),
    ):
        unknown_profiles = sorted(set(mapping.values()) - allowed_profiles)
        if unknown_profiles:
            raise ValueError(
                f"{field_name} references unknown criteria_profile identifiers "
                f"{unknown_profiles!r}."
            )

    assignments: list[dict[str, Any]] = []
    for validator_id in selection["active_validator_ids"]:
        validator = validator_by_id[validator_id]
        family = family_by_id[validator["validator_family_id"]]
        layer_id = family["layer_id"]
        if validator_id in overrides["validator_overrides"]:
            criteria_profile_reference = overrides["validator_overrides"][validator_id]
            source = "validator_override"
        elif family["validator_family_id"] in overrides["validator_family_overrides"]:
            criteria_profile_reference = overrides["validator_family_overrides"][
                family["validator_family_id"]
            ]
            source = "validator_family_override"
        elif layer_id in overrides["layer_overrides"]:
            criteria_profile_reference = overrides["layer_overrides"][layer_id]
            source = "layer_override"
        else:
            criteria_profile_reference = validator["criteria_profile_reference"]
            source = "validator_contract_default"
        assignments.append(
            {
                "validator_id": validator_id,
                "validator_family_id": validator["validator_family_id"],
                "layer_id": layer_id,
                "criteria_profile_reference": str(criteria_profile_reference),
                "criteria_profile_source": source,
                "validator_default_criteria_profile_reference": str(
                    validator["criteria_profile_reference"]
                ),
                "validator_family_default_criteria_profile_reference": str(
                    family["default_criteria_profile_reference"]
                ),
            }
        )
    return assignments


def _build_comparison_groups(
    analysis_plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    groups = [
        copy.deepcopy(dict(item))
        for item in analysis_plan.get("arm_pair_catalog", [])
    ] + [
        copy.deepcopy(dict(item))
        for item in analysis_plan.get("comparison_group_catalog", [])
    ]
    groups.sort(key=lambda item: str(item["group_id"]))
    return groups


def _resolve_perturbation_suites(
    *,
    cfg: Mapping[str, Any],
    simulation_plan: Mapping[str, Any],
    bundle_set: Mapping[str, Any] | None,
    selection: Mapping[str, Any],
    validation_config: Mapping[str, Any],
    comparison_groups: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    suites: list[dict[str, Any]] = []
    surface_wave_arm_plans = [
        copy.deepcopy(dict(arm_plan))
        for arm_plan in simulation_plan["arm_plans"]
        if str(arm_plan["arm_reference"]["model_mode"]) == SURFACE_WAVE_MODEL_MODE
    ]
    comparison_group_by_kind = _group_ids_by_kind(comparison_groups)
    available_geometry_variants = _available_geometry_variants(
        simulation_plan["arm_plans"]
    )
    target_bundle_inventory = (
        []
        if bundle_set is None
        else [copy.deepcopy(dict(item)) for item in bundle_set["bundle_inventory"]]
    )

    timestep_config = validation_config["perturbation_suites"][TIMESTEP_SWEEPS_SUITE_ID]
    timestep_variants = _build_timestep_sweep_variants(
        cfg=cfg,
        surface_wave_arm_plans=surface_wave_arm_plans,
        suite_config=timestep_config,
        simulation_plan=simulation_plan,
    )
    timestep_target_validator_ids = _target_validator_ids_for_suite(
        selection=selection,
        suite_id=TIMESTEP_SWEEPS_SUITE_ID,
    )
    suites.append(
        {
            "suite_id": TIMESTEP_SWEEPS_SUITE_ID,
            "suite_kind": "timestep_sweep",
            "enabled": bool(timestep_config["enabled"]),
            "target_layer_ids": _target_layer_ids_for_validator_ids(
                selection=selection,
                validator_ids=timestep_target_validator_ids,
                fallback_layer_ids=[NUMERICAL_SANITY_LAYER_ID],
            ),
            "target_validator_ids": timestep_target_validator_ids,
            "comparison_group_ids": [],
            "variants": timestep_variants,
        }
    )

    geometry_config = validation_config["perturbation_suites"][GEOMETRY_VARIANTS_SUITE_ID]
    geometry_variants = _build_geometry_variant_records(
        suite_config=geometry_config,
        available_variants=available_geometry_variants,
        target_bundle_inventory=target_bundle_inventory,
        comparison_group_by_kind=comparison_group_by_kind,
    )
    geometry_target_validator_ids = _target_validator_ids_for_suite(
        selection=selection,
        suite_id=GEOMETRY_VARIANTS_SUITE_ID,
    )
    suites.append(
        {
            "suite_id": GEOMETRY_VARIANTS_SUITE_ID,
            "suite_kind": "geometry_variant",
            "enabled": bool(geometry_config["enabled"]),
            "target_layer_ids": _target_layer_ids_for_validator_ids(
                selection=selection,
                validator_ids=geometry_target_validator_ids,
            ),
            "target_validator_ids": geometry_target_validator_ids,
            "comparison_group_ids": sorted(
                set(comparison_group_by_kind.get("geometry_ablation", []))
            ),
            "variants": geometry_variants,
        }
    )

    sign_delay_config = validation_config["perturbation_suites"][
        SIGN_DELAY_PERTURBATIONS_SUITE_ID
    ]
    sign_delay_variants = _build_sign_delay_variant_records(sign_delay_config)
    sign_delay_target_validator_ids = _target_validator_ids_for_suite(
        selection=selection,
        suite_id=SIGN_DELAY_PERTURBATIONS_SUITE_ID,
    )
    suites.append(
        {
            "suite_id": SIGN_DELAY_PERTURBATIONS_SUITE_ID,
            "suite_kind": "sign_delay_perturbation",
            "enabled": bool(sign_delay_config["enabled"]),
            "target_layer_ids": _target_layer_ids_for_validator_ids(
                selection=selection,
                validator_ids=sign_delay_target_validator_ids,
            ),
            "target_validator_ids": sign_delay_target_validator_ids,
            "comparison_group_ids": sorted(
                set(
                    comparison_group_by_kind.get("matched_surface_wave_vs_baseline", [])
                )
            ),
            "variants": sign_delay_variants,
        }
    )

    noise_config = validation_config["perturbation_suites"][NOISE_ROBUSTNESS_SUITE_ID]
    noise_variants = _build_noise_robustness_variants(
        suite_config=noise_config,
        bundle_set=bundle_set,
        simulation_plan=simulation_plan,
    )
    noise_target_validator_ids = _target_validator_ids_for_suite(
        selection=selection,
        suite_id=NOISE_ROBUSTNESS_SUITE_ID,
    )
    suites.append(
        {
            "suite_id": NOISE_ROBUSTNESS_SUITE_ID,
            "suite_kind": "noise_robustness",
            "enabled": bool(noise_config["enabled"]),
            "target_layer_ids": _target_layer_ids_for_validator_ids(
                selection=selection,
                validator_ids=noise_target_validator_ids,
            ),
            "target_validator_ids": noise_target_validator_ids,
            "comparison_group_ids": sorted(
                set(
                    comparison_group_by_kind.get("matched_surface_wave_vs_baseline", [])
                )
                | set(comparison_group_by_kind.get("baseline_strength_challenge", []))
            ),
            "variants": noise_variants,
        }
    )
    return suites


def _build_target_artifact_references(
    *,
    cfg: Mapping[str, Any],
    simulation_plan: Mapping[str, Any],
    bundle_set: Mapping[str, Any] | None,
    analysis_bundle_metadata: Mapping[str, Any] | None,
    selection: Mapping[str, Any],
    perturbation_suites: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    artifact_references: dict[str, Any] = {}
    active_validator_ids = set(selection["active_validator_ids"])
    if OPERATOR_BUNDLE_GATE_ALIGNMENT_VALIDATOR_ID in active_validator_ids:
        selected_root_ids = list(
            simulation_plan["arm_plans"][0]["selection"]["selected_root_ids"]
        )
        operator_output_dir = build_operator_qa_output_dir(
            cfg["paths"]["operator_qa_dir"],
            selected_root_ids,
        ).resolve()
        artifact_references["operator_qa"] = {
            "root_ids": [int(root_id) for root_id in selected_root_ids],
            "output_dir": str(operator_output_dir),
            "summary_path": str((operator_output_dir / "summary.json").resolve()),
            "report_path": str((operator_output_dir / "report.md").resolve()),
        }
    if bundle_set is not None:
        artifact_references["simulator_result_bundles"] = [
            copy.deepcopy(dict(item)) for item in bundle_set["bundle_inventory"]
        ]
    if analysis_bundle_metadata is not None:
        metadata = parse_experiment_analysis_bundle_metadata(analysis_bundle_metadata)
        artifact_references["experiment_analysis_bundle"] = {
            "bundle_reference": build_experiment_analysis_bundle_reference(metadata),
            "metadata_path": str(
                Path(metadata["artifacts"]["metadata_json"]["path"]).resolve()
            ),
            "summary_path": str(
                Path(
                    metadata["artifacts"][EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID]["path"]
                ).resolve()
            ),
        }
    if any(
        suite["suite_id"] == TIMESTEP_SWEEPS_SUITE_ID and suite["enabled"]
        for suite in perturbation_suites
    ):
        artifact_references["surface_wave_inspection"] = [
            {
                "variant_id": variant["variant_id"],
                "arm_id": variant["arm_id"],
                "expected_output_dir": variant["upstream_expected_output_dir"],
                "expected_summary_path": variant["upstream_expected_summary_path"],
                "expected_report_path": variant["upstream_expected_report_path"],
            }
            for suite in perturbation_suites
            if suite["suite_id"] == TIMESTEP_SWEEPS_SUITE_ID
            for variant in suite["variants"]
        ]
    if MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID in active_validator_ids:
        mixed_targets: list[dict[str, Any]] = []
        for arm_plan in simulation_plan["arm_plans"]:
            if str(arm_plan["arm_reference"]["model_mode"]) != SURFACE_WAVE_MODEL_MODE:
                continue
            mixed_fidelity_plan = _require_mapping(
                _require_mapping(
                    arm_plan["model_configuration"]["surface_wave_execution_plan"],
                    field_name="arm_plan.model_configuration.surface_wave_execution_plan",
                )["mixed_fidelity"],
                field_name="surface_wave_execution_plan.mixed_fidelity",
            )
            reference_roots = _resolve_default_mixed_fidelity_reference_roots(
                mixed_fidelity_plan
            )
            output_dir = build_mixed_fidelity_inspection_output_dir(
                mixed_fidelity_inspection_dir=cfg["paths"]["mixed_fidelity_inspection_dir"],
                experiment_id=str(simulation_plan["manifest_reference"]["experiment_id"]),
                arm_id=str(arm_plan["arm_reference"]["arm_id"]),
                reference_roots=reference_roots,
            ).resolve()
            mixed_targets.append(
                {
                    "arm_id": str(arm_plan["arm_reference"]["arm_id"]),
                    "reference_roots": reference_roots,
                    "expected_output_dir": str(output_dir),
                    "expected_summary_path": str((output_dir / "summary.json").resolve()),
                    "expected_report_path": str((output_dir / "report.md").resolve()),
                }
            )
        artifact_references["mixed_fidelity_inspection"] = mixed_targets
    return artifact_references


def _build_evidence_bundle_references(
    *,
    bundle_set: Mapping[str, Any] | None,
    analysis_bundle_metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    references: dict[str, Any] = {}
    if bundle_set is not None:
        references["simulator_result_bundle"] = {
            "bundle_ids": [
                str(item["bundle_id"]) for item in bundle_set["bundle_inventory"]
            ]
        }
    if analysis_bundle_metadata is not None:
        references["experiment_analysis_bundle"] = build_experiment_analysis_bundle_reference(
            analysis_bundle_metadata
        )
    return references


def _attach_validation_output_locations(
    *,
    perturbation_suites: Sequence[dict[str, Any]],
    bundle_directory: Path,
) -> None:
    for suite in perturbation_suites:
        suite_root = (bundle_directory / "perturbations" / suite["suite_id"]).resolve()
        suite["validation_output_directory"] = str(suite_root)
        for variant in suite["variants"]:
            variant_output_dir = (suite_root / variant["variant_id"]).resolve()
            variant["validation_output_directory"] = str(variant_output_dir)


def _build_active_layer_records(
    *,
    selection: Mapping[str, Any],
    criteria_assignments: Sequence[Mapping[str, Any]],
    perturbation_suites: Sequence[Mapping[str, Any]],
    bundle_set: Mapping[str, Any] | None,
    comparison_groups: Sequence[Mapping[str, Any]],
    group_arm_ids: Mapping[str, list[str]],
) -> list[dict[str, Any]]:
    bundle_ids_by_arm_id = _bundle_ids_by_arm_id(bundle_set)
    criteria_by_validator_id = {
        str(item["validator_id"]): copy.deepcopy(dict(item))
        for item in criteria_assignments
    }
    comparison_group_ids_by_validator = _comparison_group_ids_by_validator(
        selection["active_validator_ids"],
        comparison_groups,
    )
    suite_ids_by_validator = _suite_ids_by_validator(perturbation_suites)
    layer_records: list[dict[str, Any]] = []
    family_by_id = selection["family_by_id"]
    validator_by_id = selection["validator_by_id"]
    for layer_id in selection["active_layer_ids"]:
        layer = copy.deepcopy(dict(selection["layer_by_id"][layer_id]))
        family_records: list[dict[str, Any]] = []
        for family_id in selection["active_validator_family_ids"]:
            family = family_by_id[family_id]
            if family["layer_id"] != layer_id:
                continue
            validator_records: list[dict[str, Any]] = []
            for validator_id in selection["active_validator_ids"]:
                validator = validator_by_id[validator_id]
                if validator["validator_family_id"] != family_id:
                    continue
                comparison_group_ids = list(
                    comparison_group_ids_by_validator.get(validator_id, [])
                )
                target_arm_ids = _target_arm_ids_for_validator(
                    validator_id=validator_id,
                    comparison_group_ids=comparison_group_ids,
                    group_arm_ids=group_arm_ids,
                    bundle_set=bundle_set,
                )
                target_bundle_ids = sorted(
                    {
                        bundle_id
                        for arm_id in target_arm_ids
                        for bundle_id in bundle_ids_by_arm_id.get(arm_id, [])
                    }
                )
                validator_records.append(
                    {
                        **copy.deepcopy(dict(validator)),
                        **copy.deepcopy(dict(criteria_by_validator_id[validator_id])),
                        "comparison_group_ids": comparison_group_ids,
                        "perturbation_suite_ids": list(
                            suite_ids_by_validator.get(validator_id, [])
                        ),
                        "target_arm_ids": target_arm_ids,
                        "target_result_bundle_ids": target_bundle_ids,
                        "target_artifact_keys": sorted(
                            {
                                EVIDENCE_SCOPE_ARTIFACT_KEYS.get(scope_id, scope_id)
                                for scope_id in validator["required_evidence_scope_ids"]
                            }
                        ),
                    }
                )
            family_records.append(
                {
                    **copy.deepcopy(dict(family)),
                    "validators": validator_records,
                }
            )
        layer_records.append(
            {
                **layer,
                "validator_families": family_records,
            }
        )
    return layer_records


def _comparison_group_ids_by_validator(
    active_validator_ids: Sequence[str],
    comparison_groups: Sequence[Mapping[str, Any]],
) -> dict[str, list[str]]:
    groups_by_kind = _group_ids_by_kind(comparison_groups)
    resolved: dict[str, list[str]] = {}
    for validator_id in active_validator_ids:
        requested_kinds = VALIDATOR_COMPARISON_GROUP_KINDS.get(validator_id, set())
        group_ids: list[str] = []
        for group_kind in sorted(requested_kinds):
            group_ids.extend(groups_by_kind.get(group_kind, []))
        resolved[validator_id] = sorted(set(group_ids))
    return resolved


def _suite_ids_by_validator(
    perturbation_suites: Sequence[Mapping[str, Any]],
) -> dict[str, list[str]]:
    resolved: dict[str, list[str]] = {}
    for suite in perturbation_suites:
        for validator_id in suite["target_validator_ids"]:
            resolved.setdefault(str(validator_id), []).append(str(suite["suite_id"]))
    return {
        validator_id: sorted(set(suite_ids))
        for validator_id, suite_ids in resolved.items()
    }


def _target_validator_ids_for_suite(
    *,
    selection: Mapping[str, Any],
    suite_id: str,
) -> list[str]:
    return [
        validator_id
        for validator_id in selection["active_validator_ids"]
        if suite_id in set(VALIDATOR_SUITE_IDS.get(validator_id, set()))
    ]


def _target_layer_ids_for_validator_ids(
    *,
    selection: Mapping[str, Any],
    validator_ids: Sequence[str],
    fallback_layer_ids: Sequence[str] | None = None,
) -> list[str]:
    if not validator_ids:
        return [str(layer_id) for layer_id in (fallback_layer_ids or [])]
    layer_order = {layer_id: index for index, layer_id in enumerate(selection["active_layer_ids"])}
    layer_ids = {
        selection["family_by_id"][
            selection["validator_by_id"][validator_id]["validator_family_id"]
        ]["layer_id"]
        for validator_id in validator_ids
    }
    return sorted(
        layer_ids,
        key=lambda item: (layer_order.get(item, 10_000), str(item)),
    )


def _target_arm_ids_for_validator(
    *,
    validator_id: str,
    comparison_group_ids: Sequence[str],
    group_arm_ids: Mapping[str, Sequence[str]],
    bundle_set: Mapping[str, Any] | None,
) -> list[str]:
    if validator_id in {
        SURFACE_WAVE_STABILITY_ENVELOPE_VALIDATOR_ID,
        MIXED_FIDELITY_SURROGATE_PRESERVATION_VALIDATOR_ID,
    }:
        if bundle_set is None:
            return []
        return sorted(
            {
                str(item["arm_id"])
                for item in bundle_set["bundle_inventory"]
                if str(item["model_mode"]) == SURFACE_WAVE_MODEL_MODE
            }
        )
    if comparison_group_ids:
        return sorted(
            {
                arm_id
                for group_id in comparison_group_ids
                for arm_id in group_arm_ids.get(group_id, [])
            }
        )
    if bundle_set is None:
        return []
    return sorted({str(item["arm_id"]) for item in bundle_set["bundle_inventory"]})


def _build_timestep_sweep_variants(
    *,
    cfg: Mapping[str, Any],
    surface_wave_arm_plans: Sequence[Mapping[str, Any]],
    suite_config: Mapping[str, Any],
    simulation_plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not suite_config["enabled"]:
        return []
    variants: list[dict[str, Any]] = []
    for arm_plan in surface_wave_arm_plans:
        arm_id = str(arm_plan["arm_reference"]["arm_id"])
        sweep_specs = (
            [
                {
                    "label": "base_timebase",
                    "path": None,
                    "spec": normalize_surface_wave_sweep_spec(None),
                }
            ]
            if not suite_config["sweep_spec_paths"]
            else [
                {
                    "label": _normalize_identifier(Path(path).stem, field_name="sweep_spec_path"),
                    "path": str(Path(path).resolve()),
                    "spec": load_surface_wave_sweep_spec(path),
                }
                for path in suite_config["sweep_spec_paths"]
            ]
        )
        for item in sweep_specs:
            spec = copy.deepcopy(dict(item["spec"]))
            if suite_config["use_manifest_seed_sweep"]:
                manifest_seed_sweep = list(simulation_plan.get("seed_sweep", []))
                if not manifest_seed_sweep:
                    raise ValueError(
                        "validation.perturbation_suites.timestep_sweeps.use_manifest_seed_sweep "
                        "requires a non-empty manifest seed_sweep."
                    )
                resolved_seed_values = [int(seed) for seed in manifest_seed_sweep]
                seed_source = "manifest_seed_sweep"
            elif spec.get("seed_values") is not None:
                resolved_seed_values = [int(seed) for seed in spec["seed_values"]]
                seed_source = "sweep_spec"
            else:
                resolved_seed_values = [int(arm_plan["determinism"]["seed"])]
                seed_source = "arm_default_seed"
            output_dir = build_surface_wave_inspection_output_dir(
                surface_wave_inspection_dir=cfg["paths"]["surface_wave_inspection_dir"],
                arm_plans=[arm_plan],
                sweep_spec=spec,
            ).resolve()
            variants.append(
                {
                    "variant_id": f"{arm_id}__{item['label']}",
                    "arm_id": arm_id,
                    "resolved_seed_values": resolved_seed_values,
                    "seed_source": seed_source,
                    "sweep_spec_label": str(item["label"]),
                    "sweep_spec_path": item["path"],
                    "use_manifest_seed_sweep": bool(
                        suite_config["use_manifest_seed_sweep"]
                    ),
                    "sweep_spec": spec,
                    "upstream_expected_output_dir": str(output_dir),
                    "upstream_expected_summary_path": str(
                        (output_dir / "summary.json").resolve()
                    ),
                    "upstream_expected_report_path": str(
                        (output_dir / "report.md").resolve()
                    ),
                }
            )
    variants.sort(key=lambda item: (item["arm_id"], item["variant_id"]))
    return variants


def _build_geometry_variant_records(
    *,
    suite_config: Mapping[str, Any],
    available_variants: Sequence[str],
    target_bundle_inventory: Sequence[Mapping[str, Any]],
    comparison_group_by_kind: Mapping[str, Sequence[str]],
) -> list[dict[str, Any]]:
    if not suite_config["enabled"]:
        return []
    selected_variants = list(suite_config["variant_ids"]) or list(available_variants)
    unsupported = sorted(set(selected_variants) - set(available_variants))
    if unsupported:
        raise ValueError(
            "validation.perturbation_suites.geometry_variants.variant_ids requests "
            f"unsupported geometry variants {unsupported!r}; available variants are "
            f"{list(available_variants)!r}."
        )
    variants: list[dict[str, Any]] = []
    for variant_id in selected_variants:
        matching_bundles = [
            {
                "bundle_id": str(item["bundle_id"]),
                "arm_id": str(item["arm_id"]),
                "seed": int(item["seed"]),
                "condition_signature": str(item["condition_signature"]),
            }
            for item in target_bundle_inventory
            if str(item.get("arm_id", "")).endswith(f"_{variant_id}")
            or str(item.get("arm_id", "")).endswith(f"__{variant_id}")
            or str(item.get("arm_id", "")).split("_")[-1] == variant_id
        ]
        variants.append(
            {
                "variant_id": str(variant_id),
                "bundle_targets": matching_bundles,
                "comparison_group_ids": list(
                    comparison_group_by_kind.get("geometry_ablation", [])
                ),
            }
        )
    variants.sort(key=lambda item: item["variant_id"])
    return variants


def _build_sign_delay_variant_records(
    suite_config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not suite_config["enabled"]:
        return []
    selected_variants = list(suite_config["variant_ids"]) or list(
        SUPPORTED_SIGN_DELAY_VARIANT_IDS
    )
    unsupported = sorted(set(selected_variants) - set(SUPPORTED_SIGN_DELAY_VARIANT_IDS))
    if unsupported:
        raise ValueError(
            "validation.perturbation_suites.sign_delay_perturbations.variant_ids "
            f"references unsupported variants {unsupported!r}; expected one of "
            f"{list(SUPPORTED_SIGN_DELAY_VARIANT_IDS)!r}."
        )
    descriptions = {
        "as_recorded": "Milestone 7 sign and delay semantics exactly as recorded.",
        "sign_inversion_probe": "Invert coupling sign while preserving delay bins.",
        "zero_delay_probe": "Collapse delays to zero while preserving coupling sign.",
        "delay_scale_half_probe": "Scale all declared delays by 0.5 while preserving sign.",
    }
    return [
        {
            "variant_id": str(variant_id),
            "description": descriptions[str(variant_id)],
        }
        for variant_id in selected_variants
    ]


def _build_noise_robustness_variants(
    *,
    suite_config: Mapping[str, Any],
    bundle_set: Mapping[str, Any] | None,
    simulation_plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not suite_config["enabled"]:
        return []
    available_seed_values = _available_seed_values(bundle_set, simulation_plan)
    requested_seed_values = (
        list(suite_config["seed_values"])
        if suite_config["seed_values"]
        else list(available_seed_values)
    )
    missing_seed_values = sorted(set(requested_seed_values) - set(available_seed_values))
    if missing_seed_values:
        raise ValueError(
            "validation.perturbation_suites.noise_robustness.seed_values requests "
            f"seeds without complete local bundle coverage {missing_seed_values!r}; "
            f"available seeds are {list(available_seed_values)!r}."
        )
    variants: list[dict[str, Any]] = []
    for seed in requested_seed_values:
        for noise_level in suite_config["noise_levels"]:
            variants.append(
                {
                    "variant_id": _noise_variant_id(seed=seed, noise_level=noise_level),
                    "seed": int(seed),
                    "noise_level": float(noise_level),
                }
            )
    variants.sort(key=lambda item: (int(item["seed"]), float(item["noise_level"])))
    return variants


def _available_seed_values(
    bundle_set: Mapping[str, Any] | None,
    simulation_plan: Mapping[str, Any],
) -> list[int]:
    if bundle_set is not None:
        seed_values = {
            int(seed)
            for seeds in bundle_set["expected_seeds_by_arm_id"].values()
            for seed in seeds
        }
        if seed_values:
            return sorted(seed_values)
    manifest_seed_sweep = [int(seed) for seed in simulation_plan.get("seed_sweep", [])]
    if manifest_seed_sweep:
        return sorted(set(manifest_seed_sweep))
    return sorted(
        {
            int(arm_plan["determinism"]["seed"])
            for arm_plan in simulation_plan["arm_plans"]
        }
    )


def _available_geometry_variants(arm_plans: Sequence[Mapping[str, Any]]) -> list[str]:
    seen: list[str] = []
    for arm_plan in arm_plans:
        topology_condition = _normalize_identifier(
            arm_plan["topology_condition"],
            field_name="arm_plan.topology_condition",
        )
        if topology_condition not in seen:
            seen.append(topology_condition)
    return seen


def _resolve_group_arm_ids(
    comparison_groups: Sequence[Mapping[str, Any]],
) -> dict[str, list[str]]:
    groups_by_id = {
        str(item["group_id"]): copy.deepcopy(dict(item))
        for item in comparison_groups
    }
    resolved: dict[str, list[str]] = {}

    def _resolve(group_id: str) -> list[str]:
        if group_id in resolved:
            return resolved[group_id]
        group = groups_by_id[group_id]
        if "arm_ids" in group:
            arm_ids = sorted(
                {
                    _normalize_identifier(arm_id, field_name="comparison_group.arm_ids")
                    for arm_id in group.get("arm_ids", [])
                }
            )
        else:
            arm_ids = sorted(
                {
                    arm_id
                    for component_group_id in group.get("component_group_ids", [])
                    for arm_id in _resolve(str(component_group_id))
                }
            )
        resolved[group_id] = arm_ids
        return arm_ids

    for group_id in sorted(groups_by_id):
        _resolve(group_id)
    return resolved


def _bundle_ids_by_arm_id(
    bundle_set: Mapping[str, Any] | None,
) -> dict[str, list[str]]:
    if bundle_set is None:
        return {}
    bundle_ids_by_arm_id: dict[str, list[str]] = {}
    for item in bundle_set["bundle_inventory"]:
        bundle_ids_by_arm_id.setdefault(str(item["arm_id"]), []).append(
            str(item["bundle_id"])
        )
    return {
        arm_id: sorted(set(bundle_ids))
        for arm_id, bundle_ids in bundle_ids_by_arm_id.items()
    }


def _resolve_default_mixed_fidelity_reference_roots(
    mixed_fidelity_plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    assignments = [
        copy.deepcopy(dict(item))
        for item in mixed_fidelity_plan.get("per_root_assignments", [])
    ]
    resolved: dict[int, dict[str, Any]] = {}
    for assignment in assignments:
        policy_evaluation = dict(assignment.get("policy_evaluation", {}))
        recommended = policy_evaluation.get("recommended_morphology_class")
        if recommended is None:
            continue
        realized_class = str(assignment["realized_morphology_class"])
        normalized_recommended = normalize_hybrid_morphology_class(
            recommended,
            field_name="mixed_fidelity.reference_roots.recommended_morphology_class",
        )
        if _morphology_class_rank(normalized_recommended) <= _morphology_class_rank(
            realized_class
        ):
            continue
        root_id = int(assignment["root_id"])
        resolved[root_id] = {
            "root_id": root_id,
            "reference_morphology_class": normalized_recommended,
            "reference_source": "policy_recommendation",
        }
    if not resolved:
        for assignment in assignments:
            realized_class = str(assignment["realized_morphology_class"])
            next_class = _next_higher_morphology_class(realized_class)
            if next_class is None:
                continue
            root_id = int(assignment["root_id"])
            resolved[root_id] = {
                "root_id": root_id,
                "reference_morphology_class": next_class,
                "reference_source": "default_next_higher_class",
            }
    return [resolved[root_id] for root_id in sorted(resolved)]


def _next_higher_morphology_class(morphology_class: str) -> str | None:
    normalized = normalize_hybrid_morphology_class(
        morphology_class,
        field_name="morphology_class",
    )
    current_index = HYBRID_MORPHOLOGY_PROMOTION_ORDER.index(normalized)
    if current_index >= len(HYBRID_MORPHOLOGY_PROMOTION_ORDER) - 1:
        return None
    return str(HYBRID_MORPHOLOGY_PROMOTION_ORDER[current_index + 1])


def _morphology_class_rank(morphology_class: str) -> int:
    return HYBRID_MORPHOLOGY_PROMOTION_ORDER.index(
        normalize_hybrid_morphology_class(
            morphology_class,
            field_name="morphology_class",
        )
    )


def _group_ids_by_kind(
    comparison_groups: Sequence[Mapping[str, Any]],
) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for item in comparison_groups:
        grouped.setdefault(str(item["group_kind"]), []).append(str(item["group_id"]))
    return {kind: sorted(set(group_ids)) for kind, group_ids in grouped.items()}


def _normalize_criteria_profile_overrides(payload: Any) -> dict[str, dict[str, str]]:
    raw_payload = dict(payload or {})
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError("validation.criteria_profiles must be a mapping when provided.")
    unknown_keys = sorted(set(raw_payload) - ALLOWED_CRITERIA_PROFILE_KEYS)
    if unknown_keys:
        raise ValueError(
            "validation.criteria_profiles contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    return {
        "layer_overrides": _normalize_string_override_mapping(
            raw_payload.get("layer_overrides"),
            field_name="validation.criteria_profiles.layer_overrides",
        ),
        "validator_family_overrides": _normalize_string_override_mapping(
            raw_payload.get("validator_family_overrides"),
            field_name="validation.criteria_profiles.validator_family_overrides",
        ),
        "validator_overrides": _normalize_string_override_mapping(
            raw_payload.get("validator_overrides"),
            field_name="validation.criteria_profiles.validator_overrides",
        ),
    }


def _normalize_perturbation_suite_config(
    payload: Any,
    *,
    project_root: Path,
) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError(
            "validation.perturbation_suites must be a mapping when provided."
        )
    unknown_keys = sorted(set(raw_payload) - ALLOWED_PERTURBATION_SUITE_KEYS)
    if unknown_keys:
        raise ValueError(
            "validation.perturbation_suites contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    return {
        TIMESTEP_SWEEPS_SUITE_ID: _normalize_timestep_sweep_config(
            raw_payload.get(TIMESTEP_SWEEPS_SUITE_ID),
            project_root=project_root,
        ),
        GEOMETRY_VARIANTS_SUITE_ID: _normalize_geometry_variant_config(
            raw_payload.get(GEOMETRY_VARIANTS_SUITE_ID),
        ),
        SIGN_DELAY_PERTURBATIONS_SUITE_ID: _normalize_sign_delay_config(
            raw_payload.get(SIGN_DELAY_PERTURBATIONS_SUITE_ID),
        ),
        NOISE_ROBUSTNESS_SUITE_ID: _normalize_noise_robustness_config(
            raw_payload.get(NOISE_ROBUSTNESS_SUITE_ID),
        ),
    }


def _normalize_timestep_sweep_config(
    payload: Any,
    *,
    project_root: Path,
) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError(
            "validation.perturbation_suites.timestep_sweeps must be a mapping when provided."
        )
    unknown_keys = sorted(set(raw_payload) - ALLOWED_TIMESTEP_SWEEP_KEYS)
    if unknown_keys:
        raise ValueError(
            "validation.perturbation_suites.timestep_sweeps contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    sweep_spec_paths: list[str] = []
    for index, path in enumerate(raw_payload.get("sweep_spec_paths", [])):
        sweep_spec_paths.append(
            str(
                _resolve_project_path(
                    _normalize_nonempty_string(
                        path,
                        field_name=(
                            "validation.perturbation_suites.timestep_sweeps"
                            f".sweep_spec_paths[{index}]"
                        ),
                    ),
                    project_root=project_root,
                )
            )
        )
    return {
        "enabled": _normalize_bool(
            raw_payload.get("enabled", True),
            field_name="validation.perturbation_suites.timestep_sweeps.enabled",
        ),
        "sweep_spec_paths": sorted(set(sweep_spec_paths)),
        "use_manifest_seed_sweep": _normalize_bool(
            raw_payload.get("use_manifest_seed_sweep", False),
            field_name=(
                "validation.perturbation_suites.timestep_sweeps.use_manifest_seed_sweep"
            ),
        ),
    }


def _normalize_geometry_variant_config(payload: Any) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError(
            "validation.perturbation_suites.geometry_variants must be a mapping when provided."
        )
    unknown_keys = sorted(set(raw_payload) - ALLOWED_GEOMETRY_VARIANT_KEYS)
    if unknown_keys:
        raise ValueError(
            "validation.perturbation_suites.geometry_variants contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    return {
        "enabled": _normalize_bool(
            raw_payload.get("enabled", True),
            field_name="validation.perturbation_suites.geometry_variants.enabled",
        ),
        "variant_ids": _normalize_identifier_list(
            raw_payload.get("variant_ids", []),
            field_name="validation.perturbation_suites.geometry_variants.variant_ids",
            allow_empty=True,
        ),
    }


def _normalize_sign_delay_config(payload: Any) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError(
            "validation.perturbation_suites.sign_delay_perturbations must be a mapping when provided."
        )
    unknown_keys = sorted(set(raw_payload) - ALLOWED_SIGN_DELAY_KEYS)
    if unknown_keys:
        raise ValueError(
            "validation.perturbation_suites.sign_delay_perturbations contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    return {
        "enabled": _normalize_bool(
            raw_payload.get("enabled", False),
            field_name="validation.perturbation_suites.sign_delay_perturbations.enabled",
        ),
        "variant_ids": _normalize_identifier_list(
            raw_payload.get("variant_ids", []),
            field_name="validation.perturbation_suites.sign_delay_perturbations.variant_ids",
            allow_empty=True,
        ),
    }


def _normalize_noise_robustness_config(payload: Any) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError(
            "validation.perturbation_suites.noise_robustness must be a mapping when provided."
        )
    unknown_keys = sorted(set(raw_payload) - ALLOWED_NOISE_ROBUSTNESS_KEYS)
    if unknown_keys:
        raise ValueError(
            "validation.perturbation_suites.noise_robustness contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    return {
        "enabled": _normalize_bool(
            raw_payload.get("enabled", True),
            field_name="validation.perturbation_suites.noise_robustness.enabled",
        ),
        "seed_values": _normalize_seed_values(
            raw_payload.get("seed_values", []),
            field_name="validation.perturbation_suites.noise_robustness.seed_values",
        ),
        "noise_levels": _normalize_noise_levels(
            raw_payload.get("noise_levels", [0.0]),
            field_name="validation.perturbation_suites.noise_robustness.noise_levels",
        ),
    }


def _normalize_string_override_mapping(
    payload: Any,
    *,
    field_name: str,
) -> dict[str, str]:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping when provided.")
    normalized: dict[str, str] = {}
    for raw_key, raw_value in payload.items():
        normalized[_normalize_identifier(raw_key, field_name=field_name)] = _normalize_nonempty_string(
            raw_value,
            field_name=field_name,
        )
    return dict(sorted(normalized.items()))


def _validate_override_mapping_keys(
    mapping: Mapping[str, str],
    *,
    known_ids: set[str],
    field_name: str,
) -> None:
    unknown_ids = sorted(set(mapping) - set(known_ids))
    if unknown_ids:
        raise ValueError(
            f"{field_name} references unknown identifiers {unknown_ids!r}."
        )


def _normalize_bool(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} must be a boolean.")


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


def _normalize_seed_values(payload: Any, *, field_name: str) -> list[int]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence.")
    normalized = sorted(
        {
            _normalize_positive_int(int(value), field_name=field_name)
            for value in payload
        }
    )
    return normalized


def _normalize_noise_levels(payload: Any, *, field_name: str) -> list[float]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence.")
    normalized = sorted(
        {
            round(
                _normalize_float(value, field_name=field_name),
                6,
            )
            for value in payload
        }
    )
    for value in normalized:
        if float(value) < 0.0:
            raise ValueError(f"{field_name} must contain non-negative values.")
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


def _resolve_project_path(path: str | Path, *, project_root: Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()


def _noise_variant_id(*, seed: int, noise_level: float) -> str:
    noise_text = str(noise_level).replace(".", "p")
    return f"seed_{int(seed)}__noise_{noise_text}"


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value
