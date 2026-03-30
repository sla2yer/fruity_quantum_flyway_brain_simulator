from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .experiment_suite_contract import (
    ALTERED_DELAY_ASSUMPTIONS_ABLATION_FAMILY_ID,
    ALTERED_SIGN_ASSUMPTIONS_ABLATION_FAMILY_ID,
    COARSEN_GEOMETRY_ABLATION_FAMILY_ID,
    NO_LATERAL_COUPLING_ABLATION_FAMILY_ID,
    NO_WAVES_ABLATION_FAMILY_ID,
    SHUFFLE_MORPHOLOGY_ABLATION_FAMILY_ID,
    SHUFFLE_SYNAPSE_LOCATIONS_ABLATION_FAMILY_ID,
    WAVES_ONLY_SELECTED_CELL_CLASSES_ABLATION_FAMILY_ID,
)
from .hybrid_morphology_contract import (
    POINT_NEURON_CLASS,
    SKELETON_NEURON_CLASS,
    SURFACE_NEURON_CLASS,
)
from .simulator_result_contract import SURFACE_WAVE_MODEL_MODE
from .stimulus_contract import (
    _normalize_identifier,
    _normalize_json_mapping,
    _normalize_nonempty_string,
)


EXPERIMENT_ABLATION_TRANSFORM_VERSION = "experiment_ablation_transform.v1"
EXPERIMENT_SUITE_ABLATION_CONFIG_KEY = "experiment_suite_ablation"

NO_WAVES_TRANSFORM_MODE = "demote_all_selected_roots_to_point_neuron"
WAVES_ONLY_SELECTED_CELL_CLASSES_TRANSFORM_MODE = (
    "point_default_except_selected_cell_classes"
)
NO_LATERAL_COUPLING_TRANSFORM_MODE = "drop_all_inter_root_coupling_edges"
SHUFFLE_SYNAPSE_LOCATIONS_TRANSFORM_MODE = "postsynaptic_patch_permutation"
SHUFFLE_MORPHOLOGY_TRANSFORM_MODE = "surface_operator_asset_permutation"
COARSEN_GEOMETRY_TRANSFORM_MODE = "demote_surface_roots_to_skeleton_neuron"
ALTERED_SIGN_TRANSFORM_MODE = "invert_all_coupling_signs"
ALTERED_DELAY_ZERO_TRANSFORM_MODE = "force_zero_delay_ms"
ALTERED_DELAY_SCALE_TRANSFORM_MODE = "scale_delay_ms"

_SURFACE_GEOMETRY_REQUIRED_KEYS = (
    "processed_surface_mesh",
    "fine_surface_operator",
    "coarse_patch_operator",
    "surface_transfer_operators",
    "surface_operator_metadata",
)
_SURFACE_GEOMETRY_OPTIONAL_KEYS = (
    "raw_mesh",
    "raw_swc_skeleton",
    "geometry_descriptors",
    "geometry_qa",
)
_SKELETON_REQUIRED_KEYS = ("raw_swc_skeleton",)


def build_experiment_ablation_realization(
    *,
    base_cell: Mapping[str, Any],
    declaration: Mapping[str, Any],
    base_simulation_plan: Mapping[str, Any],
    perturbation_seed: int | None = None,
    perturbation_seed_by_simulation_seed: Mapping[int, int] | None = None,
) -> dict[str, Any]:
    normalized_base_cell = _require_mapping(base_cell, field_name="base_cell")
    normalized_declaration = _require_mapping(
        declaration,
        field_name="declaration",
    )
    normalized_plan = _require_mapping(
        base_simulation_plan,
        field_name="base_simulation_plan",
    )
    ablation_family_id = _normalize_identifier(
        normalized_declaration.get("ablation_family_id"),
        field_name="declaration.ablation_family_id",
    )
    variant_id = _normalize_identifier(
        normalized_declaration.get("variant_id"),
        field_name="declaration.variant_id",
    )
    display_name = _normalize_nonempty_string(
        normalized_declaration.get("display_name", variant_id),
        field_name="declaration.display_name",
    )
    parameter_snapshot = _normalize_json_mapping(
        normalized_declaration.get("parameter_snapshot", {}),
        field_name="declaration.parameter_snapshot",
    )
    target_wave_arms = _collect_target_surface_wave_arms(normalized_plan)
    surface_context = _build_surface_wave_context(target_wave_arms)
    normalized_seed = (
        None
        if perturbation_seed is None
        else _normalize_positive_or_zero_int(
            perturbation_seed,
            field_name="perturbation_seed",
        )
    )
    normalized_seed_map = _normalize_perturbation_seed_map(
        perturbation_seed_by_simulation_seed,
        field_name="perturbation_seed_by_simulation_seed",
    )

    realization = {
        "transform_version": EXPERIMENT_ABLATION_TRANSFORM_VERSION,
        "source_suite_cell_id": _normalize_identifier(
            normalized_base_cell.get("suite_cell_id"),
            field_name="base_cell.suite_cell_id",
        ),
        "source_lineage_kind": _normalize_identifier(
            normalized_base_cell.get("lineage_kind", "base_condition"),
            field_name="base_cell.lineage_kind",
        ),
        "ablation_family_id": ablation_family_id,
        "variant_id": variant_id,
        "display_name": display_name,
        "transform_id": _normalize_identifier(
            f"{ablation_family_id}__{variant_id}",
            field_name="transform_id",
        ),
        "parameter_snapshot": parameter_snapshot,
        "target_model_mode": SURFACE_WAVE_MODEL_MODE,
        "target_arm_ids": [
            str(item["arm_reference"]["arm_id"]) for item in target_wave_arms
        ],
        "target_root_ids": list(surface_context["root_ids"]),
        "target_root_cell_types": copy.deepcopy(surface_context["cell_type_by_root"]),
        "perturbation_seed": normalized_seed,
        "perturbation_seed_by_simulation_seed": normalized_seed_map,
        "perturbed_inputs": [],
        "validated_prerequisites": [],
        "realization_policy": {},
    }

    if ablation_family_id == NO_WAVES_ABLATION_FAMILY_ID:
        realization["perturbed_inputs"] = [
            "comparison_arms[*].fidelity_assignment",
            "arm_plans[*].model_configuration.surface_wave_execution_plan.mixed_fidelity",
        ]
        realization["validated_prerequisites"] = [
            f"{len(target_wave_arms)} surface-wave comparison arms are available for demotion.",
            f"{len(surface_context['root_ids'])} selected roots will be demoted to point-neuron dynamics.",
        ]
        realization["realization_policy"] = {
            "mode": NO_WAVES_TRANSFORM_MODE,
            "default_morphology_class": POINT_NEURON_CLASS,
        }
        return normalize_experiment_ablation_realization(realization)

    if ablation_family_id == WAVES_ONLY_SELECTED_CELL_CLASSES_ABLATION_FAMILY_ID:
        target_cell_classes = _normalize_nonempty_identifier_list(
            parameter_snapshot.get("target_cell_classes"),
            field_name="parameter_snapshot.target_cell_classes",
        )
        preserved_root_classes = _resolve_preserved_root_classes(
            surface_context=surface_context,
            target_cell_classes=target_cell_classes,
        )
        realization["perturbed_inputs"] = [
            "comparison_arms[*].fidelity_assignment",
            "arm_plans[*].model_configuration.surface_wave_execution_plan.mixed_fidelity",
        ]
        realization["validated_prerequisites"] = [
            "Selected-root cell-class metadata is available for waves-only targeting.",
            f"{len(preserved_root_classes)} selected roots match the requested cell classes.",
        ]
        realization["realization_policy"] = {
            "mode": WAVES_ONLY_SELECTED_CELL_CLASSES_TRANSFORM_MODE,
            "target_cell_classes": target_cell_classes,
            "default_morphology_class": POINT_NEURON_CLASS,
            "preserved_root_morphology_classes": preserved_root_classes,
        }
        return normalize_experiment_ablation_realization(realization)

    if ablation_family_id == NO_LATERAL_COUPLING_ABLATION_FAMILY_ID:
        edge_count = _count_unique_inter_root_edges(surface_context)
        if edge_count < 1:
            raise ValueError(
                "no_lateral_coupling could not be realized because the base surface-wave "
                "plan does not expose any inter-root coupling edges."
            )
        realization["perturbed_inputs"] = [
            "arm_plans[*].model_configuration.surface_wave_execution_plan.selected_root_coupling_assets",
            "arm_plans[*].model_configuration.surface_wave_execution_plan.mixed_fidelity.per_root_assignments[*].coupling_asset",
        ]
        realization["validated_prerequisites"] = [
            f"{edge_count} inter-root coupling edges are available for deterministic removal.",
        ]
        realization["realization_policy"] = {
            "mode": NO_LATERAL_COUPLING_TRANSFORM_MODE,
            "removed_inter_root_edge_count": edge_count,
        }
        return normalize_experiment_ablation_realization(realization)

    if ablation_family_id == SHUFFLE_SYNAPSE_LOCATIONS_ABLATION_FAMILY_ID:
        seed_or_map = _require_perturbation_seed_support(
            perturbation_seed=normalized_seed,
            perturbation_seed_by_simulation_seed=normalized_seed_map,
            field_name="shuffle_synapse_locations",
        )
        patch_count_by_root = _surface_patch_count_by_root(surface_context)
        realization["perturbed_inputs"] = [
            "comparison_arms[*].topology_condition",
            "arm_plans[*].model_configuration.surface_wave_execution_plan.ablation_transform",
            "surface_wave_execution.target_patch_permutations",
        ]
        realization["validated_prerequisites"] = [
            f"{len(patch_count_by_root)} surface roots expose coarse-patch geometry for synapse shuffling.",
            seed_or_map,
        ]
        realization["realization_policy"] = {
            "mode": SHUFFLE_SYNAPSE_LOCATIONS_TRANSFORM_MODE,
            "morphology_condition": "shuffled_synapse_landing_geometry",
            "patch_count_by_root": patch_count_by_root,
        }
        return normalize_experiment_ablation_realization(realization)

    if ablation_family_id == SHUFFLE_MORPHOLOGY_ABLATION_FAMILY_ID:
        seed_or_map = _require_perturbation_seed_support(
            perturbation_seed=normalized_seed,
            perturbation_seed_by_simulation_seed=normalized_seed_map,
            field_name="shuffle_morphology",
        )
        compatible_surface_roots = _compatible_surface_operator_roots(surface_context)
        realization["perturbed_inputs"] = [
            "arm_plans[*].model_configuration.surface_wave_execution_plan.selected_root_operator_assets",
            "arm_plans[*].model_configuration.surface_wave_execution_plan.mixed_fidelity.per_root_assignments[*].surface_operator_asset",
            "arm_plans[*].model_configuration.surface_wave_execution_plan.mixed_fidelity.per_root_assignments[*].required_local_assets",
            "arm_plans[*].model_configuration.surface_wave_execution_plan.mixed_fidelity.per_root_assignments[*].optional_local_assets",
        ]
        realization["validated_prerequisites"] = [
            f"{len(compatible_surface_roots)} compatible surface roots are available for geometry-only permutation.",
            seed_or_map,
        ]
        realization["realization_policy"] = {
            "mode": SHUFFLE_MORPHOLOGY_TRANSFORM_MODE,
            "compatible_surface_root_ids": compatible_surface_roots,
        }
        return normalize_experiment_ablation_realization(realization)

    if ablation_family_id == COARSEN_GEOMETRY_ABLATION_FAMILY_ID:
        coarsened_root_ids = _surface_roots_with_skeleton_variants(surface_context)
        realization["perturbed_inputs"] = [
            "comparison_arms[*].fidelity_assignment",
            "arm_plans[*].model_configuration.surface_wave_execution_plan.mixed_fidelity",
            "arm_plans[*].model_configuration.surface_wave_execution_plan.selected_root_skeleton_assets",
        ]
        realization["validated_prerequisites"] = [
            f"{len(coarsened_root_ids)} surface roots expose raw-skeleton variants for deterministic coarsening.",
        ]
        realization["realization_policy"] = {
            "mode": COARSEN_GEOMETRY_TRANSFORM_MODE,
            "coarsened_morphology_class": SKELETON_NEURON_CLASS,
            "coarsened_root_ids": coarsened_root_ids,
        }
        return normalize_experiment_ablation_realization(realization)

    if ablation_family_id == ALTERED_SIGN_ASSUMPTIONS_ABLATION_FAMILY_ID:
        _validate_sign_parameter_snapshot(parameter_snapshot)
        realization["perturbed_inputs"] = [
            "surface_wave_execution.coupling_components[*].signed_weight_total",
            "hybrid_morphology_runtime.coupling_components[*].signed_weight_total",
        ]
        realization["validated_prerequisites"] = [
            "The first altered-sign family is intentionally bounded to the sign-inversion probe.",
        ]
        realization["realization_policy"] = {
            "mode": ALTERED_SIGN_TRANSFORM_MODE,
            "sign_probe_mode": "sign_inversion_probe",
        }
        return normalize_experiment_ablation_realization(realization)

    if ablation_family_id == ALTERED_DELAY_ASSUMPTIONS_ABLATION_FAMILY_ID:
        realization["perturbed_inputs"] = [
            "surface_wave_execution.coupling_components[*].delay_ms",
            "hybrid_morphology_runtime.coupling_components[*].delay_ms",
        ]
        if variant_id == "zero_delay_probe":
            _validate_zero_delay_parameter_snapshot(parameter_snapshot)
            realization["validated_prerequisites"] = [
                "The first altered-delay family supports an explicit zero-delay probe.",
            ]
            realization["realization_policy"] = {
                "mode": ALTERED_DELAY_ZERO_TRANSFORM_MODE,
                "delay_probe_mode": "zero_delay_probe",
            }
            return normalize_experiment_ablation_realization(realization)
        if variant_id == "delay_scale_half_probe":
            _validate_delay_scale_parameter_snapshot(parameter_snapshot)
            realization["validated_prerequisites"] = [
                "The first altered-delay family supports only the fixed half-delay scaling probe.",
            ]
            realization["realization_policy"] = {
                "mode": ALTERED_DELAY_SCALE_TRANSFORM_MODE,
                "delay_probe_mode": "delay_scale_half_probe",
                "scale_factor": 0.5,
            }
            return normalize_experiment_ablation_realization(realization)
        raise ValueError(
            "Unsupported altered-delay ablation variant "
            f"{variant_id!r}. Supported variants: ['delay_scale_half_probe', 'zero_delay_probe']."
        )

    raise ValueError(
        f"Unsupported ablation_family_id {ablation_family_id!r} for canonical realization."
    )


def materialize_experiment_ablation_realization_for_seed(
    realization: Mapping[str, Any],
    *,
    simulation_seed: int,
) -> dict[str, Any]:
    normalized = normalize_experiment_ablation_realization(realization)
    resolved = copy.deepcopy(normalized)
    if resolved["perturbation_seed"] is None:
        seed_map = dict(resolved["perturbation_seed_by_simulation_seed"])
        if seed_map:
            if int(simulation_seed) not in seed_map:
                raise ValueError(
                    "Ablation transform "
                    f"{resolved['transform_id']!r} is missing a perturbation seed for "
                    f"simulation_seed {simulation_seed}."
                )
            resolved["perturbation_seed"] = int(seed_map[int(simulation_seed)])
    perturbation_seed = resolved["perturbation_seed"]
    if perturbation_seed is None:
        return resolved

    policy = copy.deepcopy(dict(resolved["realization_policy"]))
    if policy["mode"] == SHUFFLE_SYNAPSE_LOCATIONS_TRANSFORM_MODE:
        patch_count_by_root = {
            int(root_id): int(count)
            for root_id, count in policy["patch_count_by_root"].items()
        }
        policy["precomputed_target_patch_permutations"] = _build_patch_permutations(
            patch_count_by_root=patch_count_by_root,
            perturbation_seed=int(perturbation_seed),
        )
    elif policy["mode"] == SHUFFLE_MORPHOLOGY_TRANSFORM_MODE:
        compatible_surface_root_ids = [
            int(root_id) for root_id in policy["compatible_surface_root_ids"]
        ]
        policy["operator_asset_donor_root_by_target_root"] = (
            _build_surface_operator_permutation(
                compatible_surface_root_ids=compatible_surface_root_ids,
                perturbation_seed=int(perturbation_seed),
            )
        )
    resolved["realization_policy"] = policy
    return normalize_experiment_ablation_realization(resolved)


def normalize_experiment_ablation_realization(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    mapping = _require_mapping(payload, field_name="experiment_suite_ablation")
    return {
        "transform_version": _normalize_nonempty_string(
            mapping.get("transform_version", EXPERIMENT_ABLATION_TRANSFORM_VERSION),
            field_name="experiment_suite_ablation.transform_version",
        ),
        "source_suite_cell_id": _normalize_identifier(
            mapping.get("source_suite_cell_id"),
            field_name="experiment_suite_ablation.source_suite_cell_id",
        ),
        "source_lineage_kind": _normalize_identifier(
            mapping.get("source_lineage_kind", "base_condition"),
            field_name="experiment_suite_ablation.source_lineage_kind",
        ),
        "ablation_family_id": _normalize_identifier(
            mapping.get("ablation_family_id"),
            field_name="experiment_suite_ablation.ablation_family_id",
        ),
        "variant_id": _normalize_identifier(
            mapping.get("variant_id"),
            field_name="experiment_suite_ablation.variant_id",
        ),
        "display_name": _normalize_nonempty_string(
            mapping.get("display_name"),
            field_name="experiment_suite_ablation.display_name",
        ),
        "transform_id": _normalize_identifier(
            mapping.get("transform_id"),
            field_name="experiment_suite_ablation.transform_id",
        ),
        "parameter_snapshot": _normalize_json_mapping(
            mapping.get("parameter_snapshot", {}),
            field_name="experiment_suite_ablation.parameter_snapshot",
        ),
        "target_model_mode": _normalize_identifier(
            mapping.get("target_model_mode", SURFACE_WAVE_MODEL_MODE),
            field_name="experiment_suite_ablation.target_model_mode",
        ),
        "target_arm_ids": _normalize_identifier_list(
            mapping.get("target_arm_ids", ()),
            field_name="experiment_suite_ablation.target_arm_ids",
        ),
        "target_root_ids": _normalize_int_list(
            mapping.get("target_root_ids", ()),
            field_name="experiment_suite_ablation.target_root_ids",
        ),
        "target_root_cell_types": _normalize_optional_string_map(
            mapping.get("target_root_cell_types", {}),
            field_name="experiment_suite_ablation.target_root_cell_types",
        ),
        "perturbation_seed": _normalize_optional_nonnegative_int(
            mapping.get("perturbation_seed"),
            field_name="experiment_suite_ablation.perturbation_seed",
        ),
        "perturbation_seed_by_simulation_seed": _normalize_perturbation_seed_map(
            mapping.get("perturbation_seed_by_simulation_seed"),
            field_name="experiment_suite_ablation.perturbation_seed_by_simulation_seed",
        ),
        "perturbed_inputs": _normalize_nonempty_string_list(
            mapping.get("perturbed_inputs", ()),
            field_name="experiment_suite_ablation.perturbed_inputs",
        ),
        "validated_prerequisites": _normalize_nonempty_string_list(
            mapping.get("validated_prerequisites", ()),
            field_name="experiment_suite_ablation.validated_prerequisites",
        ),
        "realization_policy": _normalize_json_mapping(
            mapping.get("realization_policy", {}),
            field_name="experiment_suite_ablation.realization_policy",
        ),
    }


def apply_experiment_ablation_to_arm_payload(
    *,
    arm_payload: Mapping[str, Any],
    realization: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_arm = _require_mapping(arm_payload, field_name="arm_payload")
    normalized_realization = normalize_experiment_ablation_realization(realization)
    if not _is_target_surface_wave_arm(
        arm_id=normalized_arm.get("arm_id"),
        model_mode=normalized_arm.get("model_mode"),
        realization=normalized_realization,
    ):
        return copy.deepcopy(dict(normalized_arm))

    mutated = copy.deepcopy(dict(normalized_arm))
    policy = dict(normalized_realization["realization_policy"])
    mode = str(policy["mode"])
    if mode == NO_WAVES_TRANSFORM_MODE:
        mutated["fidelity_assignment"] = {
            "default_morphology_class": POINT_NEURON_CLASS,
            "root_overrides": [],
        }
    elif mode == WAVES_ONLY_SELECTED_CELL_CLASSES_TRANSFORM_MODE:
        preserved_root_morphology_classes = _normalize_string_map(
            policy.get("preserved_root_morphology_classes", {}),
            field_name="realization_policy.preserved_root_morphology_classes",
        )
        mutated["fidelity_assignment"] = {
            "default_morphology_class": POINT_NEURON_CLASS,
            "root_overrides": [
                {
                    "root_id": int(root_id),
                    "morphology_class": str(morphology_class),
                }
                for root_id, morphology_class in sorted(
                    ((int(root_id), value) for root_id, value in preserved_root_morphology_classes.items()),
                    key=lambda item: item[0],
                )
            ],
        }
    elif mode == COARSEN_GEOMETRY_TRANSFORM_MODE:
        mutated["fidelity_assignment"] = {
            "root_overrides": [
                {
                    "root_id": int(root_id),
                    "morphology_class": SKELETON_NEURON_CLASS,
                }
                for root_id in _normalize_int_list(
                    policy.get("coarsened_root_ids", ()),
                    field_name="realization_policy.coarsened_root_ids",
                )
            ]
        }
    elif mode == SHUFFLE_SYNAPSE_LOCATIONS_TRANSFORM_MODE:
        mutated["topology_condition"] = "shuffled"
        mutated["morphology_condition"] = str(
            policy.get("morphology_condition", "shuffled_synapse_landing_geometry")
        )
    return mutated


def apply_experiment_ablation_to_arm_plan(
    *,
    arm_plan: Mapping[str, Any],
    realization: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_arm_plan = _require_mapping(arm_plan, field_name="arm_plan")
    materialized_realization = normalize_experiment_ablation_realization(realization)
    arm_reference = _require_mapping(
        normalized_arm_plan.get("arm_reference"),
        field_name="arm_plan.arm_reference",
    )
    if not _is_target_surface_wave_arm(
        arm_id=arm_reference.get("arm_id"),
        model_mode=arm_reference.get("model_mode"),
        realization=materialized_realization,
    ):
        return copy.deepcopy(dict(normalized_arm_plan))

    mutated = copy.deepcopy(dict(normalized_arm_plan))
    model_configuration = _require_mapping(
        mutated.get("model_configuration"),
        field_name="arm_plan.model_configuration",
    )
    execution_plan = _require_mapping(
        model_configuration.get("surface_wave_execution_plan"),
        field_name="arm_plan.model_configuration.surface_wave_execution_plan",
    )
    mutated_execution_plan = copy.deepcopy(dict(execution_plan))
    policy = dict(materialized_realization["realization_policy"])
    mode = str(policy["mode"])

    if mode == NO_LATERAL_COUPLING_TRANSFORM_MODE:
        _drop_inter_root_coupling_edges(mutated_execution_plan)
    elif mode == SHUFFLE_MORPHOLOGY_TRANSFORM_MODE:
        _apply_surface_operator_asset_permutation(
            mutated_execution_plan,
            donor_root_by_target_root=_normalize_int_map(
                policy.get("operator_asset_donor_root_by_target_root", {}),
                field_name="realization_policy.operator_asset_donor_root_by_target_root",
            ),
        )

    mutated_execution_plan["ablation_transform"] = copy.deepcopy(
        materialized_realization
    )
    model_configuration["surface_wave_execution_plan"] = mutated_execution_plan
    model_configuration["ablation_transform"] = copy.deepcopy(
        materialized_realization
    )
    mutated["model_configuration"] = model_configuration
    mutated["ablation_transform"] = copy.deepcopy(materialized_realization)
    return mutated


def apply_experiment_ablation_coupling_perturbation(
    realization: Mapping[str, Any] | None,
    *,
    sign_label: str,
    signed_weight_total: float,
    delay_ms: float,
) -> tuple[str, float, float]:
    if realization is None:
        return sign_label, float(signed_weight_total), float(delay_ms)
    normalized = normalize_experiment_ablation_realization(realization)
    mode = str(normalized["realization_policy"].get("mode", ""))
    if mode == ALTERED_SIGN_TRANSFORM_MODE:
        return (
            _invert_sign_label(sign_label),
            float(-signed_weight_total),
            float(delay_ms),
        )
    if mode == ALTERED_DELAY_ZERO_TRANSFORM_MODE:
        return sign_label, float(signed_weight_total), 0.0
    if mode == ALTERED_DELAY_SCALE_TRANSFORM_MODE:
        scale_factor = float(
            normalized["realization_policy"].get("scale_factor", 0.5)
        )
        return sign_label, float(signed_weight_total), float(delay_ms) * scale_factor
    return sign_label, float(signed_weight_total), float(delay_ms)


def resolve_experiment_ablation_patch_permutations(
    realization: Mapping[str, Any] | None,
) -> dict[int, tuple[int, ...]] | None:
    if realization is None:
        return None
    normalized = normalize_experiment_ablation_realization(realization)
    policy = dict(normalized["realization_policy"])
    if policy.get("mode") != SHUFFLE_SYNAPSE_LOCATIONS_TRANSFORM_MODE:
        return None
    permutations = policy.get("precomputed_target_patch_permutations")
    if not isinstance(permutations, Mapping) or not permutations:
        return None
    return {
        int(root_id): tuple(
            int(value)
            for value in _normalize_int_list(
                values,
                field_name=f"realization_policy.precomputed_target_patch_permutations[{root_id}]",
            )
        )
        for root_id, values in sorted(permutations.items(), key=lambda item: int(item[0]))
    }


def _collect_target_surface_wave_arms(
    plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    arm_plans = _require_sequence(plan.get("arm_plans"), field_name="plan.arm_plans")
    wave_arms = [
        copy.deepcopy(dict(arm))
        for arm in arm_plans
        if _require_mapping(arm, field_name="arm_plan")["arm_reference"]["model_mode"]
        == SURFACE_WAVE_MODEL_MODE
    ]
    if not wave_arms:
        raise ValueError(
            "Canonical ablation transforms require at least one surface-wave arm in the base simulation plan."
        )
    return wave_arms


def _build_surface_wave_context(
    wave_arms: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    first_arm = _require_mapping(wave_arms[0], field_name="wave_arms[0]")
    selection = _require_mapping(
        first_arm.get("selection"),
        field_name="wave_arm.selection",
    )
    selected_root_ids = tuple(
        int(root_id)
        for root_id in _normalize_int_list(
            selection.get("selected_root_ids", ()),
            field_name="wave_arm.selection.selected_root_ids",
        )
    )
    execution_plan = _require_mapping(
        _require_mapping(
            first_arm.get("model_configuration"),
            field_name="wave_arm.model_configuration",
        ).get("surface_wave_execution_plan"),
        field_name="wave_arm.model_configuration.surface_wave_execution_plan",
    )
    mixed_fidelity = _require_mapping(
        execution_plan.get("mixed_fidelity"),
        field_name="wave_arm.surface_wave_execution_plan.mixed_fidelity",
    )
    per_root_assignments = _require_sequence(
        mixed_fidelity.get("per_root_assignments"),
        field_name="wave_arm.surface_wave_execution_plan.mixed_fidelity.per_root_assignments",
    )
    assignment_by_root = {
        int(_require_mapping(item, field_name="per_root_assignment")["root_id"]): copy.deepcopy(
            dict(_require_mapping(item, field_name="per_root_assignment"))
        )
        for item in per_root_assignments
    }
    circuit_assets = _require_mapping(
        first_arm.get("circuit_assets"),
        field_name="wave_arm.circuit_assets",
    )
    selected_root_assets = _require_sequence(
        circuit_assets.get("selected_root_assets"),
        field_name="wave_arm.circuit_assets.selected_root_assets",
    )
    cell_type_by_root: dict[int, str] = {}
    for item in selected_root_assets:
        mapping = _require_mapping(item, field_name="selected_root_asset")
        root_id = int(mapping["root_id"])
        raw_cell_type = str(mapping.get("cell_type", "")).strip()
        cell_type_by_root[root_id] = (
            ""
            if not raw_cell_type
            else _normalize_identifier(
                raw_cell_type,
                field_name=f"selected_root_assets[{root_id}].cell_type",
            )
        )
    return {
        "root_ids": selected_root_ids,
        "assignment_by_root": assignment_by_root,
        "cell_type_by_root": {
            int(root_id): cell_type_by_root.get(int(root_id), "")
            for root_id in selected_root_ids
        },
    }


def _resolve_preserved_root_classes(
    *,
    surface_context: Mapping[str, Any],
    target_cell_classes: Sequence[str],
) -> dict[str, str]:
    assignment_by_root = _require_mapping(
        surface_context.get("assignment_by_root"),
        field_name="surface_context.assignment_by_root",
    )
    cell_type_by_root = _normalize_optional_string_map(
        surface_context.get("cell_type_by_root", {}),
        field_name="surface_context.cell_type_by_root",
    )
    target_cell_class_set = {str(item) for item in target_cell_classes}
    preserved: dict[str, str] = {}
    missing_cell_type_roots = [
        int(root_id)
        for root_id, cell_type in cell_type_by_root.items()
        if not str(cell_type).strip()
    ]
    if missing_cell_type_roots:
        raise ValueError(
            "waves_only_selected_cell_classes requires cell-type assignments for all selected roots; "
            f"missing cell types for roots {missing_cell_type_roots!r}."
        )
    for root_id, cell_type in sorted(
        ((int(root_id), cell_type) for root_id, cell_type in cell_type_by_root.items()),
        key=lambda item: item[0],
    ):
        if str(cell_type) not in target_cell_class_set:
            continue
        assignment = _require_mapping(
            assignment_by_root.get(root_id),
            field_name=f"surface_context.assignment_by_root[{root_id}]",
        )
        preserved[str(root_id)] = _normalize_identifier(
            assignment.get("realized_morphology_class"),
            field_name=f"per_root_assignment[{root_id}].realized_morphology_class",
        )
    if not preserved:
        raise ValueError(
            "waves_only_selected_cell_classes could not be realized because no selected roots "
            f"match target_cell_classes {list(target_cell_classes)!r}."
        )
    return preserved


def _count_unique_inter_root_edges(surface_context: Mapping[str, Any]) -> int:
    assignment_by_root = _require_mapping(
        surface_context.get("assignment_by_root"),
        field_name="surface_context.assignment_by_root",
    )
    edges: set[tuple[int, int]] = set()
    for root_id, assignment in assignment_by_root.items():
        coupling_asset = _require_mapping(
            _require_mapping(assignment, field_name="per_root_assignment").get("coupling_asset"),
            field_name=f"per_root_assignment[{root_id}].coupling_asset",
        )
        for edge_bundle in _require_sequence(
            coupling_asset.get("selected_edge_bundle_paths", ()),
            field_name=f"coupling_asset[{root_id}].selected_edge_bundle_paths",
        ):
            normalized_edge = _require_mapping(edge_bundle, field_name="selected_edge_bundle")
            pre_root_id = int(normalized_edge["pre_root_id"])
            post_root_id = int(normalized_edge["post_root_id"])
            if pre_root_id != post_root_id:
                edges.add((pre_root_id, post_root_id))
    return len(edges)


def _surface_patch_count_by_root(surface_context: Mapping[str, Any]) -> dict[str, int]:
    assignment_by_root = _require_mapping(
        surface_context.get("assignment_by_root"),
        field_name="surface_context.assignment_by_root",
    )
    patch_counts: dict[str, int] = {}
    surface_root_ids: list[int] = []
    for root_id, assignment in sorted(
        ((int(root_id), value) for root_id, value in assignment_by_root.items()),
        key=lambda item: item[0],
    ):
        normalized_assignment = _require_mapping(
            assignment,
            field_name=f"per_root_assignment[{root_id}]",
        )
        if str(normalized_assignment.get("realized_morphology_class")) != SURFACE_NEURON_CLASS:
            continue
        surface_operator_asset = _require_mapping(
            normalized_assignment.get("surface_operator_asset"),
            field_name=f"per_root_assignment[{root_id}].surface_operator_asset",
        )
        coarse_operator_path = Path(
            _normalize_nonempty_string(
                surface_operator_asset.get("coarse_operator_path"),
                field_name=f"surface_operator_asset[{root_id}].coarse_operator_path",
            )
        ).resolve()
        if not coarse_operator_path.exists():
            raise ValueError(
                "shuffle_synapse_locations requires ready coarse operator assets; "
                f"root {root_id} is missing {coarse_operator_path}."
            )
        with np.load(coarse_operator_path) as payload:
            shape = np.asarray(payload["operator_shape"], dtype=np.int64)
        if shape.size != 2 or int(shape[0]) < 1:
            raise ValueError(
                f"shuffle_synapse_locations found unusable coarse operator shape {shape.tolist()!r} "
                f"for root {root_id}."
            )
        patch_counts[str(root_id)] = int(shape[0])
        surface_root_ids.append(root_id)
    if not patch_counts:
        raise ValueError(
            "shuffle_synapse_locations requires at least one surface-neuron root with coarse operator assets."
        )
    return patch_counts


def _compatible_surface_operator_roots(
    surface_context: Mapping[str, Any],
) -> list[int]:
    patch_count_by_root = _surface_patch_count_by_root(surface_context)
    compatible_roots = [
        int(root_id)
        for root_id, _ in sorted(
            patch_count_by_root.items(),
            key=lambda item: int(item[0]),
        )
    ]
    if len(compatible_roots) < 2:
        raise ValueError(
            "shuffle_morphology requires at least two compatible surface-neuron roots with "
            "operator assets that can be permuted."
        )
    reference_patch_count = int(patch_count_by_root[str(compatible_roots[0])])
    mismatched = [
        root_id
        for root_id in compatible_roots
        if int(patch_count_by_root[str(root_id)]) != reference_patch_count
    ]
    if mismatched:
        raise ValueError(
            "shuffle_morphology currently supports only surface roots with the same coarse patch count; "
            f"mismatched roots: {mismatched!r}."
        )
    return compatible_roots


def _surface_roots_with_skeleton_variants(
    surface_context: Mapping[str, Any],
) -> list[int]:
    assignment_by_root = _require_mapping(
        surface_context.get("assignment_by_root"),
        field_name="surface_context.assignment_by_root",
    )
    eligible_roots: list[int] = []
    missing_roots: list[int] = []
    for root_id, assignment in sorted(
        ((int(root_id), value) for root_id, value in assignment_by_root.items()),
        key=lambda item: item[0],
    ):
        normalized_assignment = _require_mapping(
            assignment,
            field_name=f"per_root_assignment[{root_id}]",
        )
        if str(normalized_assignment.get("realized_morphology_class")) != SURFACE_NEURON_CLASS:
            continue
        optional_assets = _require_mapping(
            normalized_assignment.get("optional_local_assets"),
            field_name=f"per_root_assignment[{root_id}].optional_local_assets",
        )
        raw_skeleton = _require_mapping(
            optional_assets.get("raw_swc_skeleton"),
            field_name=f"per_root_assignment[{root_id}].optional_local_assets.raw_swc_skeleton",
        )
        path = Path(
            _normalize_nonempty_string(
                raw_skeleton.get("path"),
                field_name=f"raw_swc_skeleton[{root_id}].path",
            )
        ).resolve()
        if str(raw_skeleton.get("status")) == "ready" and path.exists():
            eligible_roots.append(root_id)
        else:
            missing_roots.append(root_id)
    if not eligible_roots:
        raise ValueError(
            "coarsen_geometry could not be realized because no surface-neuron roots expose ready "
            "raw skeleton variants."
        )
    if missing_roots:
        raise ValueError(
            "coarsen_geometry requires raw skeleton variants for every targeted surface root; "
            f"missing variants for roots {missing_roots!r}."
        )
    return eligible_roots


def _validate_sign_parameter_snapshot(parameter_snapshot: Mapping[str, Any]) -> None:
    requested_mode = parameter_snapshot.get("sign_mode")
    if requested_mode is None:
        return
    normalized_mode = _normalize_identifier(
        requested_mode,
        field_name="parameter_snapshot.sign_mode",
    )
    if normalized_mode != "sign_inversion_probe":
        raise ValueError(
            "altered_sign_assumptions currently supports only sign_mode='sign_inversion_probe'."
        )


def _validate_zero_delay_parameter_snapshot(parameter_snapshot: Mapping[str, Any]) -> None:
    requested_mode = parameter_snapshot.get("delay_mode")
    if requested_mode is None:
        return
    normalized_mode = _normalize_identifier(
        requested_mode,
        field_name="parameter_snapshot.delay_mode",
    )
    if normalized_mode != "zero_delay_probe":
        raise ValueError(
            "altered_delay_assumptions zero_delay_probe currently supports only delay_mode='zero_delay_probe'."
        )


def _validate_delay_scale_parameter_snapshot(parameter_snapshot: Mapping[str, Any]) -> None:
    requested_mode = parameter_snapshot.get("delay_mode")
    if requested_mode is not None:
        normalized_mode = _normalize_identifier(
            requested_mode,
            field_name="parameter_snapshot.delay_mode",
        )
        if normalized_mode != "delay_scale_half_probe":
            raise ValueError(
                "altered_delay_assumptions delay_scale_half_probe currently supports only "
                "delay_mode='delay_scale_half_probe'."
            )
    requested_factor = parameter_snapshot.get("delay_scale_factor")
    if requested_factor is None:
        return
    factor = float(requested_factor)
    if abs(factor - 0.5) > 1.0e-12:
        raise ValueError(
            "altered_delay_assumptions delay_scale_half_probe currently supports only "
            "delay_scale_factor=0.5."
        )


def _require_perturbation_seed_support(
    *,
    perturbation_seed: int | None,
    perturbation_seed_by_simulation_seed: Mapping[int, int] | None,
    field_name: str,
) -> str:
    if perturbation_seed is not None:
        return f"Using explicit perturbation seed {perturbation_seed}."
    if perturbation_seed_by_simulation_seed:
        return (
            "Using a simulation-seed-indexed perturbation policy with explicit "
            f"ablation seeds for {len(perturbation_seed_by_simulation_seed)} seed values."
        )
    raise ValueError(
        f"{field_name} requires either perturbation_seed or perturbation_seed_by_simulation_seed."
    )


def _build_patch_permutations(
    *,
    patch_count_by_root: Mapping[int, int],
    perturbation_seed: int,
) -> dict[str, list[int]]:
    rng = np.random.Generator(np.random.PCG64(int(perturbation_seed)))
    permutations: dict[str, list[int]] = {}
    for root_id, patch_count in sorted(
        ((int(root_id), int(count)) for root_id, count in patch_count_by_root.items()),
        key=lambda item: item[0],
    ):
        permutation = np.asarray(rng.permutation(int(patch_count)), dtype=np.int64)
        if int(patch_count) > 1 and np.array_equal(
            permutation,
            np.arange(int(patch_count), dtype=np.int64),
        ):
            permutation = np.roll(permutation, 1)
        permutations[str(root_id)] = permutation.astype(np.int64).tolist()
    return permutations


def _build_surface_operator_permutation(
    *,
    compatible_surface_root_ids: Sequence[int],
    perturbation_seed: int,
) -> dict[str, int]:
    ordered_roots = [int(root_id) for root_id in compatible_surface_root_ids]
    if len(ordered_roots) < 2:
        raise ValueError(
            "surface-operator permutation requires at least two compatible surface roots."
        )
    rng = np.random.Generator(np.random.PCG64(int(perturbation_seed)))
    permutation = np.asarray(rng.permutation(len(ordered_roots)), dtype=np.int64)
    if len(ordered_roots) > 1 and np.array_equal(
        permutation,
        np.arange(len(ordered_roots), dtype=np.int64),
    ):
        permutation = np.roll(permutation, 1)
    return {
        str(target_root): int(ordered_roots[int(permutation[index])])
        for index, target_root in enumerate(ordered_roots)
    }


def _drop_inter_root_coupling_edges(execution_plan: dict[str, Any]) -> None:
    for asset in execution_plan.get("selected_root_coupling_assets", []):
        asset["selected_edge_bundle_paths"] = []
    mixed_fidelity = execution_plan.get("mixed_fidelity")
    if not isinstance(mixed_fidelity, Mapping):
        return
    for assignment in mixed_fidelity.get("per_root_assignments", []):
        if not isinstance(assignment, Mapping):
            continue
        coupling_asset = assignment.get("coupling_asset")
        if isinstance(coupling_asset, Mapping):
            coupling_asset["selected_edge_bundle_paths"] = []


def _apply_surface_operator_asset_permutation(
    execution_plan: dict[str, Any],
    *,
    donor_root_by_target_root: Mapping[int, int],
) -> None:
    if not donor_root_by_target_root:
        return
    selected_root_operator_assets = _require_sequence(
        execution_plan.get("selected_root_operator_assets"),
        field_name="surface_wave_execution_plan.selected_root_operator_assets",
    )
    operator_asset_by_root = {
        int(_require_mapping(asset, field_name="surface_operator_asset")["root_id"]): copy.deepcopy(
            dict(_require_mapping(asset, field_name="surface_operator_asset"))
        )
        for asset in selected_root_operator_assets
    }
    mixed_fidelity = _require_mapping(
        execution_plan.get("mixed_fidelity"),
        field_name="surface_wave_execution_plan.mixed_fidelity",
    )
    assignments = _require_sequence(
        mixed_fidelity.get("per_root_assignments"),
        field_name="surface_wave_execution_plan.mixed_fidelity.per_root_assignments",
    )
    assignment_by_root = {
        int(_require_mapping(item, field_name="per_root_assignment")["root_id"]): copy.deepcopy(
            dict(_require_mapping(item, field_name="per_root_assignment"))
        )
        for item in assignments
    }

    updated_operator_assets: list[dict[str, Any]] = []
    for root_id, asset in sorted(operator_asset_by_root.items()):
        donor_root_id = int(donor_root_by_target_root.get(root_id, root_id))
        donor_asset = copy.deepcopy(
            _require_mapping(
                operator_asset_by_root.get(donor_root_id),
                field_name=f"operator_asset_by_root[{donor_root_id}]",
            )
        )
        donor_asset["root_id"] = int(root_id)
        donor_asset["hybrid_morphology"] = copy.deepcopy(asset.get("hybrid_morphology"))
        updated_operator_assets.append(donor_asset)
    execution_plan["selected_root_operator_assets"] = updated_operator_assets

    updated_assignments: list[dict[str, Any]] = []
    for root_id, assignment in sorted(assignment_by_root.items()):
        donor_root_id = int(donor_root_by_target_root.get(root_id, root_id))
        donor_assignment = _require_mapping(
            assignment_by_root.get(donor_root_id),
            field_name=f"assignment_by_root[{donor_root_id}]",
        )
        updated_assignment = copy.deepcopy(dict(assignment))
        updated_assignment["surface_operator_asset"] = copy.deepcopy(
            updated_operator_assets[
                next(
                    index
                    for index, item in enumerate(updated_operator_assets)
                    if int(item["root_id"]) == int(root_id)
                )
            ]
        )
        donor_required_assets = _require_mapping(
            donor_assignment.get("required_local_assets"),
            field_name=f"assignment_by_root[{donor_root_id}].required_local_assets",
        )
        donor_optional_assets = _require_mapping(
            donor_assignment.get("optional_local_assets"),
            field_name=f"assignment_by_root[{donor_root_id}].optional_local_assets",
        )
        required_assets = _require_mapping(
            updated_assignment.get("required_local_assets"),
            field_name=f"assignment_by_root[{root_id}].required_local_assets",
        )
        optional_assets = _require_mapping(
            updated_assignment.get("optional_local_assets"),
            field_name=f"assignment_by_root[{root_id}].optional_local_assets",
        )
        for asset_key in _SURFACE_GEOMETRY_REQUIRED_KEYS:
            required_assets[asset_key] = copy.deepcopy(
                donor_required_assets[asset_key]
            )
        for asset_key in _SURFACE_GEOMETRY_OPTIONAL_KEYS:
            if asset_key in donor_optional_assets:
                optional_assets[asset_key] = copy.deepcopy(
                    donor_optional_assets[asset_key]
                )
        updated_assignment["required_local_assets"] = required_assets
        updated_assignment["optional_local_assets"] = optional_assets
        updated_assignments.append(updated_assignment)
    mixed_fidelity["per_root_assignments"] = updated_assignments
    execution_plan["mixed_fidelity"] = mixed_fidelity


def _is_target_surface_wave_arm(
    *,
    arm_id: Any,
    model_mode: Any,
    realization: Mapping[str, Any],
) -> bool:
    normalized_model_mode = _normalize_identifier(
        model_mode,
        field_name="arm.model_mode",
    )
    if normalized_model_mode != SURFACE_WAVE_MODEL_MODE:
        return False
    normalized_arm_id = _normalize_identifier(arm_id, field_name="arm.arm_id")
    return normalized_arm_id in set(realization["target_arm_ids"])


def _invert_sign_label(sign_label: str) -> str:
    normalized = _normalize_identifier(sign_label, field_name="sign_label")
    if normalized == "excitatory":
        return "inhibitory"
    if normalized == "inhibitory":
        return "excitatory"
    return _normalize_identifier(
        f"inverted_{normalized}",
        field_name="inverted_sign_label",
    )


def _require_mapping(payload: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return dict(payload)


def _require_sequence(payload: Any, *, field_name: str) -> list[Any]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence.")
    return list(payload)


def _normalize_identifier_list(payload: Any, *, field_name: str) -> list[str]:
    items = _require_sequence(payload, field_name=field_name)
    normalized = [
        _normalize_identifier(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(items)
    ]
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} contains duplicate values.")
    return normalized


def _normalize_int_list(payload: Any, *, field_name: str) -> list[int]:
    items = _require_sequence(payload, field_name=field_name)
    normalized = [_normalize_positive_or_zero_int(item, field_name=f"{field_name}[{index}]") for index, item in enumerate(items)]
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} contains duplicate values.")
    return normalized


def _normalize_nonempty_identifier_list(payload: Any, *, field_name: str) -> list[str]:
    normalized = _normalize_identifier_list(payload, field_name=field_name)
    if not normalized:
        raise ValueError(f"{field_name} must contain at least one value.")
    return normalized


def _normalize_nonempty_string_list(payload: Any, *, field_name: str) -> list[str]:
    items = _require_sequence(payload, field_name=field_name)
    return [
        _normalize_nonempty_string(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(items)
    ]


def _normalize_positive_or_zero_int(value: Any, *, field_name: str) -> int:
    normalized = int(value)
    if normalized < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def _normalize_optional_nonnegative_int(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    return _normalize_positive_or_zero_int(value, field_name=field_name)


def _normalize_string_map(payload: Any, *, field_name: str) -> dict[int, str]:
    mapping = _require_mapping(payload, field_name=field_name)
    return {
        int(root_id): _normalize_nonempty_string(
            value,
            field_name=f"{field_name}[{root_id}]",
        )
        for root_id, value in sorted(mapping.items(), key=lambda item: int(item[0]))
    }


def _normalize_optional_string_map(payload: Any, *, field_name: str) -> dict[int, str]:
    mapping = _require_mapping(payload, field_name=field_name)
    normalized: dict[int, str] = {}
    for root_id, value in sorted(mapping.items(), key=lambda item: int(item[0])):
        text = str(value).strip()
        normalized[int(root_id)] = text
    return normalized


def _normalize_int_map(payload: Any, *, field_name: str) -> dict[int, int]:
    mapping = _require_mapping(payload, field_name=field_name)
    return {
        int(key): _normalize_positive_or_zero_int(
            value,
            field_name=f"{field_name}[{key}]",
        )
        for key, value in sorted(mapping.items(), key=lambda item: int(item[0]))
    }


def _normalize_perturbation_seed_map(
    payload: Any,
    *,
    field_name: str,
) -> dict[int, int]:
    if payload is None:
        return {}
    mapping = _require_mapping(payload, field_name=field_name)
    normalized = {
        _normalize_positive_or_zero_int(key, field_name=f"{field_name}.key"): _normalize_positive_or_zero_int(
            value,
            field_name=f"{field_name}[{key}]",
        )
        for key, value in mapping.items()
    }
    if len(normalized) != len(mapping):
        raise ValueError(f"{field_name} contains duplicate simulation-seed keys.")
    return {
        int(key): int(value)
        for key, value in sorted(normalized.items(), key=lambda item: item[0])
    }
