from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from typing import Any

from .coupling_contract import (
    POINT_NEURON_LUMPED_MODE,
    SKELETON_SEGMENT_CLOUD_MODE,
    SURFACE_PATCH_CLOUD_MODE,
)
from .hybrid_morphology_contract import (
    HYBRID_MORPHOLOGY_PROMOTION_ORDER,
    POINT_NEURON_CLASS,
    SKELETON_NEURON_CLASS,
    SURFACE_NEURON_CLASS,
    build_hybrid_morphology_plan_metadata,
    normalize_hybrid_morphology_class,
)
from .mixed_fidelity_policy import (
    build_mixed_fidelity_policy_hook_summary,
    evaluate_mixed_fidelity_policy,
)
from .simulation_asset_resolution import (
    build_approximation_route,
    build_assignment_provenance,
    build_local_asset_reference_map,
    load_mixed_fidelity_descriptor_payload,
    resolve_point_neuron_coupling_asset,
    resolve_skeleton_neuron_coupling_asset,
    resolve_skeleton_runtime_asset,
    resolve_surface_wave_coupling_asset,
    resolve_surface_wave_operator_asset,
    validate_required_local_assets,
)
from .simulation_planning import (
    ARM_DEFAULT_CLASS_ASSIGNMENT_SOURCE,
    ARM_ROOT_OVERRIDE_ASSIGNMENT_SOURCE,
    MIXED_FIDELITY_COUPLING_ANCHOR_RESOLUTION,
    MIXED_FIDELITY_PLAN_VERSION,
    MIXED_FIDELITY_STATE_RESOLUTION,
    REGISTRY_PROJECT_ROLE_ASSIGNMENT_SOURCE,
    SUPPORTED_SURFACE_WAVE_AGGREGATION_SEMANTICS,
    SUPPORTED_SURFACE_WAVE_DELAY_SEMANTICS,
    SUPPORTED_SURFACE_WAVE_OPERATOR_FAMILIES,
    SUPPORTED_SURFACE_WAVE_SHARED_TIMEBASE_MODES,
    SUPPORTED_SURFACE_WAVE_SIGN_SEMANTICS,
    SUPPORTED_SURFACE_WAVE_SPATIAL_SUPPORT,
    SUPPORTED_SURFACE_WAVE_STABILITY_POLICIES,
    SURFACE_WAVE_COUPLING_ANCHOR_RESOLUTION,
    SURFACE_WAVE_MAX_INTERNAL_SUBSTEPS_PER_OUTPUT_STEP,
    SURFACE_WAVE_STATE_RESOLUTION,
    SURFACE_WAVE_STABILITY_TOLERANCE_MS,
    _normalize_arm_fidelity_assignment,
    _normalize_float,
    _normalize_identifier,
    _normalize_mixed_fidelity_config,
    _normalize_nonempty_string,
    _normalize_positive_float,
    _optional_string_sequence,
    _require_mapping,
    _require_sequence,
)


def build_surface_wave_execution_plan(
    *,
    arm_reference: Mapping[str, Any],
    arm_payload: Mapping[str, Any] | None = None,
    point_neuron_model_spec: Mapping[str, Any],
    topology_condition: str,
    runtime_timebase: Mapping[str, Any],
    circuit_assets: Mapping[str, Any],
    surface_wave_model: Mapping[str, Any],
    mixed_fidelity_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    arm_id = str(arm_reference["arm_id"])
    parameter_bundle = _require_mapping(
        surface_wave_model.get("parameter_bundle"),
        field_name="surface_wave_model.parameter_bundle",
    )
    solver = _require_mapping(
        parameter_bundle.get("solver"),
        field_name="surface_wave_model.parameter_bundle.solver",
    )
    propagation = _require_mapping(
        parameter_bundle.get("propagation"),
        field_name="surface_wave_model.parameter_bundle.propagation",
    )
    recovery = _require_mapping(
        parameter_bundle.get("recovery"),
        field_name="surface_wave_model.parameter_bundle.recovery",
    )
    synaptic_source = _require_mapping(
        parameter_bundle.get("synaptic_source"),
        field_name="surface_wave_model.parameter_bundle.synaptic_source",
    )
    anisotropy = _require_mapping(
        parameter_bundle.get("anisotropy"),
        field_name="surface_wave_model.parameter_bundle.anisotropy",
    )
    branching = _require_mapping(
        parameter_bundle.get("branching"),
        field_name="surface_wave_model.parameter_bundle.branching",
    )

    solver_family = _normalize_nonempty_string(
        solver.get("family"),
        field_name="surface_wave_model.parameter_bundle.solver.family",
    )
    if solver_family != surface_wave_model["solver_family"]:
        raise ValueError(
            f"surface_wave arm {arm_id!r} solver.family drifted from the normalized "
            "surface_wave model metadata."
        )
    shared_timebase_mode = _normalize_nonempty_string(
        solver.get("shared_timebase_mode"),
        field_name="surface_wave_model.parameter_bundle.solver.shared_timebase_mode",
    )
    if shared_timebase_mode not in SUPPORTED_SURFACE_WAVE_SHARED_TIMEBASE_MODES:
        raise ValueError(
            f"surface_wave arm {arm_id!r} only supports solver.shared_timebase_mode "
            f"{list(SUPPORTED_SURFACE_WAVE_SHARED_TIMEBASE_MODES)!r}, got "
            f"{shared_timebase_mode!r}."
        )
    stability_policy = _normalize_nonempty_string(
        solver.get("stability_policy"),
        field_name="surface_wave_model.parameter_bundle.solver.stability_policy",
    )
    if stability_policy not in SUPPORTED_SURFACE_WAVE_STABILITY_POLICIES:
        raise ValueError(
            f"surface_wave arm {arm_id!r} only supports solver.stability_policy "
            f"{list(SUPPORTED_SURFACE_WAVE_STABILITY_POLICIES)!r}, got "
            f"{stability_policy!r}."
        )
    cfl_safety_factor = _normalize_positive_float(
        solver.get("cfl_safety_factor"),
        field_name="surface_wave_model.parameter_bundle.solver.cfl_safety_factor",
    )

    operator_family = _normalize_identifier(
        propagation.get("operator_family"),
        field_name="surface_wave_model.parameter_bundle.propagation.operator_family",
    )
    if operator_family not in SUPPORTED_SURFACE_WAVE_OPERATOR_FAMILIES:
        raise ValueError(
            f"surface_wave arm {arm_id!r} only supports propagation.operator_family "
            f"{list(SUPPORTED_SURFACE_WAVE_OPERATOR_FAMILIES)!r}, got {operator_family!r}."
        )
    wave_speed_sq_scale = _normalize_positive_float(
        propagation.get("wave_speed_sq_scale"),
        field_name="surface_wave_model.parameter_bundle.propagation.wave_speed_sq_scale",
    )
    restoring_strength_per_ms2 = _normalize_float(
        propagation.get("restoring_strength_per_ms2"),
        field_name=(
            "surface_wave_model.parameter_bundle.propagation.restoring_strength_per_ms2"
        ),
    )
    if restoring_strength_per_ms2 < 0.0:
        raise ValueError(
            "surface_wave_model.parameter_bundle.propagation.restoring_strength_per_ms2 "
            "must be non-negative."
        )
    recovery_coupling_strength_per_ms2 = _normalize_float(
        recovery.get("coupling_strength_per_ms2"),
        field_name=(
            "surface_wave_model.parameter_bundle.recovery.coupling_strength_per_ms2"
        ),
    )
    if recovery_coupling_strength_per_ms2 < 0.0:
        raise ValueError(
            "surface_wave_model.parameter_bundle.recovery.coupling_strength_per_ms2 "
            "must be non-negative."
        )

    sign_semantics = _normalize_nonempty_string(
        synaptic_source.get("sign_semantics"),
        field_name="surface_wave_model.parameter_bundle.synaptic_source.sign_semantics",
    )
    if sign_semantics not in SUPPORTED_SURFACE_WAVE_SIGN_SEMANTICS:
        raise ValueError(
            f"surface_wave arm {arm_id!r} only supports synaptic_source.sign_semantics "
            f"{list(SUPPORTED_SURFACE_WAVE_SIGN_SEMANTICS)!r}, got {sign_semantics!r}."
        )
    delay_semantics = _normalize_nonempty_string(
        synaptic_source.get("delay_semantics"),
        field_name="surface_wave_model.parameter_bundle.synaptic_source.delay_semantics",
    )
    if delay_semantics not in SUPPORTED_SURFACE_WAVE_DELAY_SEMANTICS:
        raise ValueError(
            f"surface_wave arm {arm_id!r} only supports synaptic_source.delay_semantics "
            f"{list(SUPPORTED_SURFACE_WAVE_DELAY_SEMANTICS)!r}, got {delay_semantics!r}."
        )
    aggregation_semantics = _normalize_nonempty_string(
        synaptic_source.get("aggregation_semantics"),
        field_name=(
            "surface_wave_model.parameter_bundle.synaptic_source.aggregation_semantics"
        ),
    )
    if aggregation_semantics not in SUPPORTED_SURFACE_WAVE_AGGREGATION_SEMANTICS:
        raise ValueError(
            f"surface_wave arm {arm_id!r} only supports "
            "synaptic_source.aggregation_semantics "
            f"{list(SUPPORTED_SURFACE_WAVE_AGGREGATION_SEMANTICS)!r}, got "
            f"{aggregation_semantics!r}."
        )
    spatial_support = _normalize_nonempty_string(
        synaptic_source.get("spatial_support"),
        field_name="surface_wave_model.parameter_bundle.synaptic_source.spatial_support",
    )
    if spatial_support not in SUPPORTED_SURFACE_WAVE_SPATIAL_SUPPORT:
        raise ValueError(
            f"surface_wave arm {arm_id!r} only supports synaptic_source.spatial_support "
            f"{list(SUPPORTED_SURFACE_WAVE_SPATIAL_SUPPORT)!r}, got {spatial_support!r}."
        )

    selected_root_assets = _require_sequence(
        circuit_assets.get("selected_root_assets"),
        field_name="circuit_assets.selected_root_assets",
    )
    mixed_fidelity_resolution = resolve_surface_wave_mixed_fidelity_plan(
        arm_id=arm_id,
        arm_payload={} if arm_payload is None else arm_payload,
        arm_reference=arm_reference,
        selected_root_assets=selected_root_assets,
        point_neuron_model_spec=point_neuron_model_spec,
        mixed_fidelity_config=(
            _normalize_mixed_fidelity_config(None)
            if mixed_fidelity_config is None
            else mixed_fidelity_config
        ),
        anisotropy_mode=_normalize_identifier(
            anisotropy.get("mode"),
            field_name="surface_wave_model.parameter_bundle.anisotropy.mode",
        ),
        branching_mode=_normalize_identifier(
            branching.get("mode"),
            field_name="surface_wave_model.parameter_bundle.branching.mode",
        ),
    )
    hybrid_morphology = mixed_fidelity_resolution["hybrid_morphology"]
    selected_root_operator_assets = mixed_fidelity_resolution[
        "selected_root_operator_assets"
    ]
    selected_root_coupling_assets = mixed_fidelity_resolution[
        "selected_root_coupling_assets"
    ]
    selected_root_skeleton_assets = mixed_fidelity_resolution[
        "selected_root_skeleton_assets"
    ]
    mixed_fidelity = mixed_fidelity_resolution["mixed_fidelity"]

    stability_guardrails = _build_surface_wave_stability_guardrails(
        arm_id=arm_id,
        runtime_timebase=runtime_timebase,
        cfl_safety_factor=cfl_safety_factor,
        wave_speed_sq_scale=wave_speed_sq_scale,
        restoring_strength_per_ms2=restoring_strength_per_ms2,
        recovery_coupling_strength_per_ms2=recovery_coupling_strength_per_ms2,
        operator_assets=selected_root_operator_assets,
    )
    all_surface_roots = (
        hybrid_morphology["discovered_morphology_classes"] == [SURFACE_NEURON_CLASS]
    )

    return {
        "topology_condition": topology_condition,
        "operator_inventory_hash": str(circuit_assets["operator_asset_hash"]),
        "coupling_inventory_hash": str(circuit_assets["circuit_asset_hash"]),
        "resolution": {
            "operator_family": operator_family,
            "state_space": (
                SURFACE_WAVE_STATE_RESOLUTION
                if all_surface_roots
                else MIXED_FIDELITY_STATE_RESOLUTION
            ),
            "coupling_anchor_resolution": (
                SURFACE_WAVE_COUPLING_ANCHOR_RESOLUTION
                if all_surface_roots
                else MIXED_FIDELITY_COUPLING_ANCHOR_RESOLUTION
            ),
            "synaptic_spatial_support": spatial_support,
            "transfer_operator_required": bool(selected_root_operator_assets),
            "transfer_operator_requirement_scope": (
                "all_selected_roots"
                if all_surface_roots
                else "surface_neuron_roots_only"
            ),
        },
        "hybrid_morphology": hybrid_morphology,
        "mixed_fidelity": mixed_fidelity,
        "solver": {
            "family": solver_family,
            "shared_timebase_mode": shared_timebase_mode,
            "stability_policy": stability_policy,
            "cfl_safety_factor": cfl_safety_factor,
            "shared_output_timestep_ms": float(runtime_timebase["dt_ms"]),
            "integration_timestep_ms": stability_guardrails["integration_timestep_ms"],
            "internal_substep_count": stability_guardrails["required_internal_substep_count"],
            "max_internal_substeps_per_output_step": (
                SURFACE_WAVE_MAX_INTERNAL_SUBSTEPS_PER_OUTPUT_STEP
            ),
        },
        "selected_root_operator_assets_scope": (
            "all_selected_roots"
            if all_surface_roots
            else "surface_neuron_roots_only"
        ),
        "selected_root_operator_assets": selected_root_operator_assets,
        "selected_root_coupling_assets_scope": (
            "all_selected_roots"
            if all_surface_roots
            else "surface_neuron_roots_only"
        ),
        "selected_root_coupling_assets": selected_root_coupling_assets,
        "selected_root_skeleton_assets_scope": (
            "skeleton_neuron_roots_only"
            if selected_root_skeleton_assets
            else "none"
        ),
        "selected_root_skeleton_assets": selected_root_skeleton_assets,
        "stability_guardrails": stability_guardrails,
    }


def resolve_surface_wave_mixed_fidelity_plan(
    *,
    arm_id: str,
    arm_payload: Mapping[str, Any],
    arm_reference: Mapping[str, Any],
    selected_root_assets: Sequence[Mapping[str, Any]],
    point_neuron_model_spec: Mapping[str, Any],
    mixed_fidelity_config: Mapping[str, Any],
    anisotropy_mode: str,
    branching_mode: str,
) -> dict[str, Any]:
    normalized_config = _require_mapping(
        mixed_fidelity_config,
        field_name="simulation.mixed_fidelity",
    )
    assignment_policy = _require_mapping(
        normalized_config.get("assignment_policy"),
        field_name="simulation.mixed_fidelity.assignment_policy",
    )
    arm_fidelity_assignment = _normalize_arm_fidelity_assignment(
        arm_payload.get("fidelity_assignment"),
        field_name=f"surface_wave arm {arm_id!r} fidelity_assignment",
    )
    selected_root_ids = [
        int(
            _require_mapping(
                item,
                field_name=f"surface_wave arm {arm_id!r} selected_root_assets",
            )["root_id"]
        )
        for item in selected_root_assets
    ]
    unknown_override_roots = sorted(
        set(arm_fidelity_assignment["root_overrides_by_root"]) - set(selected_root_ids)
    )
    if unknown_override_roots:
        raise ValueError(
            f"surface_wave arm {arm_id!r} fidelity_assignment.root_overrides "
            f"references unselected roots {unknown_override_roots!r}."
        )

    registry_default_class_by_root: dict[int, str] = {}
    resolved_source_by_root: dict[int, str] = {}
    root_records: list[dict[str, Any]] = []
    for index, root_asset in enumerate(selected_root_assets):
        root_mapping = _require_mapping(
            root_asset,
            field_name=f"circuit_assets.selected_root_assets[{index}]",
        )
        root_id = int(root_mapping["root_id"])
        registry_default_class = normalize_hybrid_morphology_class(
            root_mapping.get("project_role"),
            field_name=f"circuit_assets.selected_root_assets[{index}].project_role",
        )
        registry_default_class_by_root[root_id] = registry_default_class
        root_override = arm_fidelity_assignment["root_overrides_by_root"].get(root_id)
        default_override = arm_fidelity_assignment["default_morphology_class"]
        if root_override is not None:
            realized_class = root_override
            resolved_from = ARM_ROOT_OVERRIDE_ASSIGNMENT_SOURCE
        elif default_override is not None:
            realized_class = default_override
            resolved_from = ARM_DEFAULT_CLASS_ASSIGNMENT_SOURCE
        else:
            realized_class = registry_default_class
            resolved_from = REGISTRY_PROJECT_ROLE_ASSIGNMENT_SOURCE
        resolved_source_by_root[root_id] = resolved_from
        root_records.append(
            {
                "root_id": root_id,
                "cell_type": str(root_mapping.get("cell_type", "")),
                "morphology_class": realized_class,
            }
        )

    hybrid_morphology = build_hybrid_morphology_plan_metadata(
        root_records=root_records,
        model_mode=str(arm_reference["model_mode"]),
    )
    hybrid_morphology_by_root = {
        int(item["root_id"]): item
        for item in hybrid_morphology["per_root_class_metadata"]
    }

    per_root_assignments: list[dict[str, Any]] = []
    policy_evaluations: list[dict[str, Any]] = []
    surface_operator_assets: list[dict[str, Any]] = []
    surface_coupling_assets: list[dict[str, Any]] = []
    skeleton_runtime_assets: list[dict[str, Any]] = []
    class_counts = {
        class_name: 0
        for class_name in HYBRID_MORPHOLOGY_PROMOTION_ORDER
    }
    for index, root_asset in enumerate(selected_root_assets):
        root_mapping = _require_mapping(
            root_asset,
            field_name=f"circuit_assets.selected_root_assets[{index}]",
        )
        root_id = int(root_mapping["root_id"])
        hybrid_record = copy.deepcopy(hybrid_morphology_by_root[root_id])
        morphology_class = str(hybrid_record["morphology_class"])
        class_counts[morphology_class] += 1

        required_local_assets = build_local_asset_reference_map(
            root_mapping=root_mapping,
            asset_keys=hybrid_record["required_local_assets"],
        )
        optional_local_assets = build_local_asset_reference_map(
            root_mapping=root_mapping,
            asset_keys=hybrid_record["optional_local_assets"],
        )
        validate_required_local_assets(
            arm_id=arm_id,
            root_id=root_id,
            morphology_class=morphology_class,
            asset_references=required_local_assets,
        )

        operator_asset = None
        skeleton_runtime_asset = None
        if morphology_class == SURFACE_NEURON_CLASS:
            operator_asset = resolve_surface_wave_operator_asset(
                arm_id=arm_id,
                root_mapping=root_mapping,
                anisotropy_mode=anisotropy_mode,
                branching_mode=branching_mode,
                hybrid_morphology=hybrid_record,
            )
            coupling_asset = resolve_surface_wave_coupling_asset(
                arm_id=arm_id,
                root_mapping=root_mapping,
                hybrid_morphology=hybrid_record,
            )
            surface_operator_assets.append(copy.deepcopy(operator_asset))
            surface_coupling_assets.append(copy.deepcopy(coupling_asset))
            realized_anchor_mode = SURFACE_PATCH_CLOUD_MODE
        elif morphology_class == SKELETON_NEURON_CLASS:
            coupling_asset = resolve_skeleton_neuron_coupling_asset(
                arm_id=arm_id,
                root_mapping=root_mapping,
                hybrid_morphology=hybrid_record,
            )
            skeleton_runtime_asset = resolve_skeleton_runtime_asset(
                arm_id=arm_id,
                root_mapping=root_mapping,
                hybrid_morphology=hybrid_record,
            )
            skeleton_runtime_assets.append(
                {
                    **copy.deepcopy(skeleton_runtime_asset),
                    "hybrid_morphology": copy.deepcopy(hybrid_record),
                    "selected_edge_bundle_paths": copy.deepcopy(
                        coupling_asset["selected_edge_bundle_paths"]
                    ),
                }
            )
            realized_anchor_mode = SKELETON_SEGMENT_CLOUD_MODE
        else:
            coupling_asset = resolve_point_neuron_coupling_asset(
                arm_id=arm_id,
                root_mapping=root_mapping,
                hybrid_morphology=hybrid_record,
            )
            realized_anchor_mode = POINT_NEURON_LUMPED_MODE
        policy_evaluation = evaluate_mixed_fidelity_policy(
            root_id=root_id,
            cell_type=str(root_mapping.get("cell_type", "")),
            realized_morphology_class=morphology_class,
            assignment_policy=assignment_policy,
            descriptor_payload=load_mixed_fidelity_descriptor_payload(root_mapping),
            arm_id=arm_id,
            topology_condition=(
                None
                if arm_payload.get("topology_condition") is None
                else str(arm_payload["topology_condition"])
            ),
            morphology_condition=(
                None
                if arm_payload.get("morphology_condition") is None
                else str(arm_payload["morphology_condition"])
            ),
            arm_tags=_optional_string_sequence(arm_payload.get("tags")),
        )
        policy_evaluations.append(copy.deepcopy(policy_evaluation))

        per_root_assignments.append(
            {
                "root_id": root_id,
                "cell_type": str(root_mapping.get("cell_type", "")),
                "source_project_role": str(root_mapping.get("project_role", "")),
                "canonical_project_role": str(hybrid_record["canonical_project_role"]),
                "registry_default_morphology_class": registry_default_class_by_root[root_id],
                "realized_morphology_class": morphology_class,
                "assignment_provenance": build_assignment_provenance(
                    registry_default_morphology_class=registry_default_class_by_root[
                        root_id
                    ],
                    arm_default_morphology_class=arm_fidelity_assignment[
                        "default_morphology_class"
                    ],
                    arm_root_override_morphology_class=arm_fidelity_assignment[
                        "root_overrides_by_root"
                    ].get(root_id),
                    assignment_policy=assignment_policy,
                    policy_evaluation=policy_evaluation,
                    resolved_from=resolved_source_by_root[root_id],
                ),
                "approximation_route": build_approximation_route(
                    registry_default_morphology_class=registry_default_class_by_root[
                        root_id
                    ],
                    realized_morphology_class=morphology_class,
                    policy_evaluation=policy_evaluation,
                ),
                "policy_evaluation": policy_evaluation,
                "state_resolution": copy.deepcopy(
                    hybrid_record["realized_state_space"]
                ),
                "readout_surface": copy.deepcopy(hybrid_record["readout_surface"]),
                "coupling_resolution": {
                    **copy.deepcopy(hybrid_record["coupling_anchor_resolution"]),
                    "realized_anchor_mode": realized_anchor_mode,
                    "topology_family": str(coupling_asset["topology_family"]),
                    "fallback_hierarchy": copy.deepcopy(
                        coupling_asset["fallback_hierarchy"]
                    ),
                },
                "required_local_assets": required_local_assets,
                "optional_local_assets": optional_local_assets,
                "surface_operator_asset": (
                    None if operator_asset is None else copy.deepcopy(operator_asset)
                ),
                "skeleton_runtime_asset": (
                    None
                    if skeleton_runtime_asset is None
                    else copy.deepcopy(skeleton_runtime_asset)
                ),
                "coupling_asset": copy.deepcopy(coupling_asset),
            }
        )
    policy_hook = build_mixed_fidelity_policy_hook_summary(
        assignment_policy=assignment_policy,
        policy_evaluations=policy_evaluations,
    )

    return {
        "hybrid_morphology": hybrid_morphology,
        "mixed_fidelity": {
            "plan_version": MIXED_FIDELITY_PLAN_VERSION,
            "assignment_ordering": normalized_config["assignment_ordering"],
            "assignment_policy": copy.deepcopy(assignment_policy),
            "policy_hook": policy_hook,
            "point_neuron_model_spec": copy.deepcopy(
                _require_mapping(
                    point_neuron_model_spec,
                    field_name="simulation.baseline_families.P0",
                )
            ),
            "arm_overrides": {
                "default_morphology_class": arm_fidelity_assignment[
                    "default_morphology_class"
                ],
                "root_overrides": copy.deepcopy(
                    arm_fidelity_assignment["root_overrides"]
                ),
            },
            "resolved_class_counts": {
                class_name: int(class_counts[class_name])
                for class_name in HYBRID_MORPHOLOGY_PROMOTION_ORDER
                if class_counts[class_name] > 0
            },
            "per_root_assignments": per_root_assignments,
        },
        "selected_root_operator_assets": surface_operator_assets,
        "selected_root_coupling_assets": surface_coupling_assets,
        "selected_root_skeleton_assets": skeleton_runtime_assets,
    }


def _build_surface_wave_stability_guardrails(
    *,
    arm_id: str,
    runtime_timebase: Mapping[str, Any],
    cfl_safety_factor: float,
    wave_speed_sq_scale: float,
    restoring_strength_per_ms2: float,
    recovery_coupling_strength_per_ms2: float,
    operator_assets: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    shared_output_timestep_ms = _normalize_positive_float(
        runtime_timebase.get("dt_ms"),
        field_name="runtime.timebase.dt_ms",
    )
    if not operator_assets:
        return {
            "status": "not_applicable_no_surface_roots",
            "shared_output_timestep_ms": shared_output_timestep_ms,
            "integration_timestep_ms": shared_output_timestep_ms,
            "required_internal_substep_count": 1,
            "max_internal_substeps_per_output_step": (
                SURFACE_WAVE_MAX_INTERNAL_SUBSTEPS_PER_OUTPUT_STEP
            ),
            "max_supported_integration_timestep_ms": math.inf,
            "limiting_root_id": None,
            "per_root": [],
        }
    per_root = []
    for operator_asset in operator_assets:
        root_id = int(operator_asset["root_id"])
        spectral_radius = _normalize_float(
            operator_asset.get("spectral_radius"),
            field_name=f"surface_wave_operator_assets[{root_id}].spectral_radius",
        )
        if spectral_radius < 0.0:
            raise ValueError(
                f"surface_wave arm {arm_id!r} produced a negative operator spectral "
                f"radius for root {root_id}: {spectral_radius!r}."
            )
        angular_frequency_sq_bound = (
            wave_speed_sq_scale * spectral_radius
            + restoring_strength_per_ms2
            + recovery_coupling_strength_per_ms2
        )
        max_supported_dt_ms = (
            math.inf
            if angular_frequency_sq_bound <= 0.0
            else (2.0 * cfl_safety_factor) / math.sqrt(angular_frequency_sq_bound)
        )
        per_root.append(
            {
                "root_id": root_id,
                "spectral_radius": spectral_radius,
                "angular_frequency_sq_bound_per_ms2": angular_frequency_sq_bound,
                "max_supported_integration_timestep_ms": max_supported_dt_ms,
            }
        )
    limiting_root = min(
        per_root,
        key=lambda item: float(item["max_supported_integration_timestep_ms"]),
    )
    max_supported_integration_timestep_ms = float(
        limiting_root["max_supported_integration_timestep_ms"]
    )
    required_internal_substep_count = (
        1
        if math.isinf(max_supported_integration_timestep_ms)
        else max(
            1,
            int(
                math.ceil(
                    shared_output_timestep_ms / max_supported_integration_timestep_ms
                )
            ),
        )
    )
    if required_internal_substep_count > SURFACE_WAVE_MAX_INTERNAL_SUBSTEPS_PER_OUTPUT_STEP:
        raise ValueError(
            f"surface_wave arm {arm_id!r} requires "
            f"{required_internal_substep_count} internal substeps at shared output "
            f"dt_ms {shared_output_timestep_ms}, but the planner only supports up to "
            f"{SURFACE_WAVE_MAX_INTERNAL_SUBSTEPS_PER_OUTPUT_STEP}. The limiting root "
            f"is {limiting_root['root_id']} with max_supported_integration_timestep_ms "
            f"{max_supported_integration_timestep_ms:.6f}."
        )
    integration_timestep_ms = (
        shared_output_timestep_ms / float(required_internal_substep_count)
    )
    if (
        integration_timestep_ms
        > max_supported_integration_timestep_ms + SURFACE_WAVE_STABILITY_TOLERANCE_MS
    ):
        raise ValueError(
            f"surface_wave arm {arm_id!r} resolved integration dt_ms "
            f"{integration_timestep_ms:.6f} above the conservative spectral bound "
            f"{max_supported_integration_timestep_ms:.6f} for limiting root "
            f"{limiting_root['root_id']}."
        )
    return {
        "status": "pass",
        "shared_output_timestep_ms": shared_output_timestep_ms,
        "integration_timestep_ms": integration_timestep_ms,
        "required_internal_substep_count": required_internal_substep_count,
        "max_internal_substeps_per_output_step": (
            SURFACE_WAVE_MAX_INTERNAL_SUBSTEPS_PER_OUTPUT_STEP
        ),
        "max_supported_integration_timestep_ms": max_supported_integration_timestep_ms,
        "limiting_root_id": int(limiting_root["root_id"]),
        "per_root": per_root,
    }
