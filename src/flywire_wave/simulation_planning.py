from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse.linalg as spla

from .config import get_config_path, get_project_root, load_config
from .coupling_contract import (
    ASSET_STATUS_READY,
    COUPLING_INDEX_KEY,
    COUPLING_BUNDLE_CONTRACT_VERSION,
    DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
    INCOMING_ANCHOR_MAP_KEY,
    LOCAL_SYNAPSE_REGISTRY_KEY,
    OUTGOING_ANCHOR_MAP_KEY,
    POINT_NEURON_LUMPED_MODE,
    POINT_TO_POINT_TOPOLOGY,
    SKELETON_SEGMENT_CLOUD_MODE,
    SURFACE_PATCH_CLOUD_MODE,
    discover_coupling_bundle_paths,
    discover_edge_coupling_bundle_paths,
    parse_coupling_bundle_metadata,
)
from .experiment_ablation_transforms import (
    EXPERIMENT_SUITE_ABLATION_CONFIG_KEY,
    apply_experiment_ablation_to_arm_payload,
    apply_experiment_ablation_to_arm_plan,
    materialize_experiment_ablation_realization_for_seed,
    normalize_experiment_ablation_realization,
)
from .geometry_contract import (
    COARSE_OPERATOR_KEY,
    DESCRIPTOR_SIDECAR_KEY,
    FINE_OPERATOR_KEY,
    OPERATOR_BUNDLE_CONTRACT_VERSION,
    OPERATOR_METADATA_KEY,
    PATCH_GRAPH_KEY,
    QA_SIDECAR_KEY,
    RAW_MESH_KEY,
    RAW_SKELETON_KEY,
    SIMPLIFIED_MESH_KEY,
    SURFACE_GRAPH_KEY,
    TRANSFER_OPERATORS_KEY,
    discover_operator_bundle_paths,
    load_geometry_manifest,
    load_geometry_manifest_records,
    load_operator_bundle_metadata,
    parse_operator_bundle_metadata,
)
from .hybrid_morphology_contract import (
    HYBRID_MORPHOLOGY_PROMOTION_ORDER,
    POINT_NEURON_CLASS,
    SKELETON_NEURON_CLASS,
    SURFACE_NEURON_CLASS,
    build_hybrid_morphology_plan_metadata,
    normalize_hybrid_morphology_class,
)
from .manifests import (
    load_json,
    load_yaml,
    resolve_manifest_input_roots,
    validate_manifest_payload,
)
from .mixed_fidelity_policy import (
    build_mixed_fidelity_policy_hook_summary,
    evaluate_mixed_fidelity_policy,
    normalize_mixed_fidelity_assignment_policy,
)
from .readout_analysis_contract import (
    ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
    ANALYSIS_NULL_TEST_ROWS_ARTIFACT_CLASS,
    EXPERIMENT_BUNDLE_SET_ARTIFACT_CLASS,
    LATENCY_SHIFT_COMPARISON_OUTPUT_ID,
    MILESTONE_1_DECISION_PANEL_OUTPUT_ID,
    NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID,
    PER_SHARED_READOUT_CONDITION_PAIR_SCOPE,
    PER_SHARED_READOUT_CONDITION_WINDOW_SCOPE,
    PER_TASK_DECODER_WINDOW_SCOPE,
    PER_WAVE_ROOT_SET_WINDOW_SCOPE,
    PER_WAVE_ROOT_WINDOW_SCOPE,
    RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS,
    SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
    SHARED_READOUT_TRACES_ARTIFACT_CLASS,
    SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
    STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
    SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
    SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
    SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
    TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
    WAVE_DIAGNOSTIC_ROWS_ARTIFACT_CLASS,
    build_readout_analysis_contract_metadata,
    get_experiment_comparison_output_definition,
    get_readout_analysis_metric_definition,
    get_readout_analysis_null_test_hook,
)
from .retinal_contract import build_retinal_bundle_reference, load_retinal_bundle_metadata
from .retinal_workflow import resolve_retinal_bundle_input
from .selection import (
    build_subset_artifact_paths,
    load_subset_manifest,
    read_selected_root_roster,
    validate_subset_manifest_payload,
)
from .simulator_result_contract import (
    BASELINE_MODEL_MODE,
    P0_BASELINE_FAMILY,
    P1_BASELINE_FAMILY,
    SURFACE_WAVE_MODEL_MODE,
    build_selected_asset_reference,
    build_simulator_arm_reference,
    build_simulator_determinism,
    build_simulator_manifest_reference,
    build_simulator_readout_definition,
    build_simulator_result_bundle_metadata,
    build_simulator_result_bundle_reference,
    normalize_simulator_timebase,
    parse_simulator_readout_definition,
)
from .skeleton_runtime_assets import (
    SKELETON_RUNTIME_ASSET_KEY,
    build_skeleton_runtime_asset_paths,
    build_skeleton_runtime_asset_record,
)
from .stimulus_contract import (
    DEFAULT_RNG_FAMILY,
    DEFAULT_TIME_UNIT,
    build_stimulus_bundle_reference,
    load_stimulus_bundle_metadata,
    _normalize_float,
    _normalize_identifier,
    _normalize_nonempty_string,
    _normalize_positive_float,
    _normalize_positive_int,
)
from .surface_wave_contract import (
    DEFAULT_PROCESSED_SURFACE_WAVE_DIR,
    build_surface_wave_model_metadata,
    build_surface_wave_model_reference,
)
from .surface_operators import deserialize_sparse_matrix


SIMULATION_PLAN_VERSION = "simulation_plan.v1"
SIMULATION_RUNTIME_CONFIG_VERSION = "simulation_runtime.v1"
MIXED_FIDELITY_CONFIG_VERSION = "mixed_fidelity_config.v1"
MIXED_FIDELITY_PLAN_VERSION = "mixed_fidelity_plan.v1"
READOUT_ANALYSIS_CONFIG_VERSION = "readout_analysis_config.v1"
READOUT_ANALYSIS_PLAN_VERSION = "readout_analysis_plan.v1"

STIMULUS_BUNDLE_INPUT_SOURCE = "stimulus_bundle"
RETINAL_BUNDLE_INPUT_SOURCE = "retinal_bundle"
SUPPORTED_INPUT_SOURCE_KINDS = (
    STIMULUS_BUNDLE_INPUT_SOURCE,
    RETINAL_BUNDLE_INPUT_SOURCE,
)

DEFAULT_REQUIRE_RECORDED_INPUT_BUNDLE = False
DEFAULT_SEED_SCOPE = "all_stochastic_simulator_components"
DEFAULT_STABLE_ARM_ORDERING = "manifest_declaration_order"
DEFAULT_SEED_SWEEP_ORDERING = "manifest_declared_seed_order"
SHARED_READOUT_VALUE_SEMANTICS = "shared_downstream_activation"
DEFAULT_MIXED_FIDELITY_ASSIGNMENT_ORDERING = "selected_root_id_ascending"
REGISTRY_PROJECT_ROLE_ASSIGNMENT_SOURCE = "registry_project_role"
ARM_DEFAULT_CLASS_ASSIGNMENT_SOURCE = "arm_default_morphology_class"
ARM_ROOT_OVERRIDE_ASSIGNMENT_SOURCE = "arm_root_override"

SELECTED_ROOT_IDS_ASSET_ROLE = "selected_root_ids"
INPUT_BUNDLE_ASSET_ROLE = "input_bundle"
GEOMETRY_MANIFEST_ASSET_ROLE = "geometry_manifest"
COUPLING_REGISTRY_ASSET_ROLE = "coupling_synapse_registry"
MODEL_CONFIGURATION_ASSET_ROLE = "model_configuration"
SURFACE_WAVE_OPERATOR_INVENTORY_ASSET_ROLE = "surface_wave_operator_inventory"
ALLOWED_SIMULATION_CONFIG_KEYS = {
    "version",
    "input",
    "timebase",
    "readout_catalog",
    "baseline_families",
    "mixed_fidelity",
    "surface_wave",
    "determinism",
}
ALLOWED_INPUT_CONFIG_KEYS = {
    "source_kind",
    "require_recorded_bundle",
    "retinal_config_path",
}
ALLOWED_DETERMINISM_CONFIG_KEYS = {
    "rng_family",
    "seed_scope",
}
ALLOWED_MIXED_FIDELITY_CONFIG_KEYS = {
    "version",
    "assignment_policy",
}
ALLOWED_ANALYSIS_CONFIG_KEYS = {
    "version",
    "active_readout_ids",
    "active_metric_ids",
    "analysis_windows",
    "null_test_ids",
    "output_ids",
    "experiment_output_targets",
}
ALLOWED_ANALYSIS_WINDOW_KEYS = {
    "start_ms",
    "end_ms",
    "description",
}
ALLOWED_ANALYSIS_OUTPUT_TARGET_KEYS = {
    "output_id",
    "path",
}
ALLOWED_ARM_FIDELITY_ASSIGNMENT_KEYS = {
    "default_morphology_class",
    "root_overrides",
}
ALLOWED_ARM_FIDELITY_OVERRIDE_KEYS = {
    "root_id",
    "morphology_class",
}

_P0_ALLOWED_KEYS = {
    "membrane_time_constant_ms",
    "resting_potential",
    "input_gain",
    "recurrent_gain",
}
_P1_ALLOWED_KEYS = {
    "membrane_time_constant_ms",
    "synaptic_current_time_constant_ms",
    "resting_potential",
    "input_gain",
    "recurrent_gain",
    "delay_handling",
}
_P1_DELAY_ALLOWED_KEYS = {
    "mode",
    "max_supported_delay_steps",
}

SUPPORTED_SURFACE_WAVE_OPERATOR_FAMILIES = ("mass_normalized_surface_laplacian",)
SUPPORTED_SURFACE_WAVE_SHARED_TIMEBASE_MODES = (
    "fixed_step_uniform_shared_outputs",
)
SUPPORTED_SURFACE_WAVE_STABILITY_POLICIES = ("spectral_radius_cfl_bound",)
SUPPORTED_SURFACE_WAVE_SIGN_SEMANTICS = (
    "from_coupling_bundle_signed_weight",
)
SUPPORTED_SURFACE_WAVE_DELAY_SEMANTICS = (
    "from_coupling_bundle_delay_ms",
)
SUPPORTED_SURFACE_WAVE_AGGREGATION_SEMANTICS = (
    "sum_preserving_sign_and_delay_bins",
)
SUPPORTED_SURFACE_WAVE_SPATIAL_SUPPORT = ("postsynaptic_patch_cloud",)
SURFACE_WAVE_STATE_RESOLUTION = "fine_surface_vertices"
SURFACE_WAVE_COUPLING_ANCHOR_RESOLUTION = "surface_patch_cloud"
MIXED_FIDELITY_STATE_RESOLUTION = "per_root_morphology_class"
MIXED_FIDELITY_COUPLING_ANCHOR_RESOLUTION = "per_root_morphology_class"
SURFACE_WAVE_MAX_INTERNAL_SUBSTEPS_PER_OUTPUT_STEP = 256
SURFACE_WAVE_STABILITY_TOLERANCE_MS = 1.0e-9

FULL_TIMEBASE_WINDOW_ID = "full_timebase_window"
SHARED_RESPONSE_WINDOW_ID = "shared_response_window"
TASK_DECODER_WINDOW_ID = "task_decoder_window"
WAVE_DIAGNOSTIC_WINDOW_ID = "wave_diagnostic_window"
ANALYSIS_WINDOW_ORDER = (
    FULL_TIMEBASE_WINDOW_ID,
    SHARED_RESPONSE_WINDOW_ID,
    TASK_DECODER_WINDOW_ID,
    WAVE_DIAGNOSTIC_WINDOW_ID,
)

PREFERRED_DIRECTION_CONDITION_ID = "preferred_direction"
NULL_DIRECTION_CONDITION_ID = "null_direction"
ON_POLARITY_CONDITION_ID = "on_polarity"
OFF_POLARITY_CONDITION_ID = "off_polarity"

PREFERRED_VS_NULL_PAIR_ID = "preferred_vs_null"
ON_VS_OFF_PAIR_ID = "on_vs_off"

PER_RUN_SINGLE_SEED_RULE_ID = "per_run_single_seed"
MANIFEST_SEED_SWEEP_ROLLUP_RULE_ID = "manifest_seed_sweep_rollup"

MANIFEST_TO_ANALYSIS_OUTPUT_ID = {
    "latency_shift_comparison": LATENCY_SHIFT_COMPARISON_OUTPUT_ID,
    "milestone_decision_panel": MILESTONE_1_DECISION_PANEL_OUTPUT_ID,
    "null_direction_suppression_comparison": NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID,
}

SUCCESS_CRITERION_NULL_TEST_IDS = {
    "m1_geometry_dependence": ("geometry_shuffle_collapse",),
    "m1_seed_parameter_stability": ("seed_stability",),
    "m1_survives_stronger_baseline": ("stronger_baseline_survival",),
}

MANIFEST_TASK_METRIC_RECIPES = {
    "direction_selectivity_index": {
        "recipe_kind": "contract_metric",
        "resolved_metric_ids": ("direction_selectivity_index",),
        "required_condition_pair_ids": (PREFERRED_VS_NULL_PAIR_ID,),
        "comparison_group_kinds": ("matched_surface_wave_vs_baseline",),
    },
    "geometry_sensitive_null_direction_suppression_effect": {
        "recipe_kind": "geometry_sensitive_metric",
        "resolved_metric_ids": ("null_direction_suppression_index",),
        "required_condition_pair_ids": (PREFERRED_VS_NULL_PAIR_ID,),
        "comparison_group_kinds": (
            "matched_surface_wave_vs_baseline",
            "geometry_ablation",
        ),
    },
    "geometry_sensitive_shared_output_effect": {
        "recipe_kind": "geometry_sensitive_metric_family",
        "resolved_metric_ids": (
            "direction_selectivity_index",
            "null_direction_suppression_index",
            "response_latency_to_peak_ms",
        ),
        "required_condition_pair_ids": (PREFERRED_VS_NULL_PAIR_ID,),
        "comparison_group_kinds": (
            "matched_surface_wave_vs_baseline",
            "geometry_ablation",
        ),
    },
    "geometry_sensitive_shared_output_effect_across_seeds": {
        "recipe_kind": "seed_rolled_geometry_sensitive_metric_family",
        "resolved_metric_ids": (
            "direction_selectivity_index",
            "null_direction_suppression_index",
            "response_latency_to_peak_ms",
        ),
        "required_condition_pair_ids": (PREFERRED_VS_NULL_PAIR_ID,),
        "comparison_group_kinds": (
            "matched_surface_wave_vs_baseline",
            "geometry_ablation",
        ),
    },
    "response_latency_to_peak_ms": {
        "recipe_kind": "contract_metric",
        "resolved_metric_ids": ("response_latency_to_peak_ms",),
        "required_condition_pair_ids": (),
        "comparison_group_kinds": ("matched_surface_wave_vs_baseline",),
    },
}


def default_shared_readout_catalog() -> list[dict[str, Any]]:
    return [
        build_simulator_readout_definition(
            readout_id="shared_output_mean",
            scope="circuit_output",
            aggregation="mean_over_root_ids",
            units="activation_au",
            value_semantics="shared_downstream_activation",
            description=(
                "Shared downstream output mean for matched baseline-versus-wave "
                "manifest-arm comparisons."
            ),
        )
    ]


def default_baseline_family_configs() -> dict[str, dict[str, Any]]:
    return {
        P0_BASELINE_FAMILY: {
            "family": P0_BASELINE_FAMILY,
            "model_family": "passive_linear_single_compartment",
            "state_layout": "scalar_state_per_selected_root",
            "integration_scheme": "forward_euler",
            "readout_state": "membrane_state",
            "initial_state": "all_zero",
            "parameters": {
                "membrane_time_constant_ms": 10.0,
                "resting_potential": 0.0,
                "input_gain": 1.0,
                "recurrent_gain": 1.0,
            },
        },
        P1_BASELINE_FAMILY: {
            "family": P1_BASELINE_FAMILY,
            "model_family": "reduced_linear_with_synaptic_current",
            "state_layout": "membrane_state_and_synaptic_current_per_selected_root",
            "integration_scheme": "forward_euler",
            "readout_state": "membrane_state",
            "initial_state": "all_zero",
            "parameters": {
                "membrane_time_constant_ms": 10.0,
                "synaptic_current_time_constant_ms": 5.0,
                "resting_potential": 0.0,
                "input_gain": 1.0,
                "recurrent_gain": 1.0,
                "delay_handling": {
                    "mode": "from_coupling_bundle",
                    "max_supported_delay_steps": 64,
                },
            },
        },
    }


def default_simulation_runtime_config(
    *,
    default_timebase: Mapping[str, Any],
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    return normalize_simulation_runtime_config(
        {},
        default_timebase=default_timebase,
        project_root=project_root,
    )


def normalize_simulation_runtime_config(
    payload: Mapping[str, Any] | None,
    *,
    default_timebase: Mapping[str, Any],
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    unknown_top_level_keys = sorted(set(raw_payload) - ALLOWED_SIMULATION_CONFIG_KEYS)
    if unknown_top_level_keys:
        raise ValueError(
            "simulation contains unsupported keys: "
            f"{unknown_top_level_keys!r}."
        )

    resolved_project_root = _resolve_project_root(project_root)
    version = raw_payload.get("version", SIMULATION_RUNTIME_CONFIG_VERSION)
    normalized_version = _normalize_nonempty_string(version, field_name="simulation.version")
    if normalized_version != SIMULATION_RUNTIME_CONFIG_VERSION:
        raise ValueError(
            "simulation.version must be "
            f"{SIMULATION_RUNTIME_CONFIG_VERSION!r}."
        )

    normalized_timebase = _normalize_runtime_timebase(
        raw_payload.get("timebase"),
        default_timebase=default_timebase,
    )
    normalized_input = _normalize_input_config(
        raw_payload.get("input"),
        project_root=resolved_project_root,
    )
    normalized_determinism = _normalize_runtime_determinism(raw_payload.get("determinism"))
    normalized_readout_catalog = _normalize_readout_catalog(
        raw_payload.get("readout_catalog")
    )
    normalized_shared_readout_catalog = _normalize_shared_readout_catalog(
        normalized_readout_catalog
    )
    normalized_baseline_families = _normalize_baseline_family_configs(
        raw_payload.get("baseline_families")
    )
    normalized_mixed_fidelity = _normalize_mixed_fidelity_config(
        raw_payload.get("mixed_fidelity")
    )
    normalized_surface_wave_model = build_surface_wave_model_metadata(
        processed_surface_wave_dir=resolved_project_root / DEFAULT_PROCESSED_SURFACE_WAVE_DIR,
        parameter_bundle=raw_payload.get("surface_wave"),
    )

    return {
        "version": normalized_version,
        "time_unit": DEFAULT_TIME_UNIT,
        "timebase": normalized_timebase,
        "input": normalized_input,
        "determinism": normalized_determinism,
        "readout_catalog": normalized_readout_catalog,
        "shared_readout_catalog": normalized_shared_readout_catalog,
        "baseline_families": normalized_baseline_families,
        "mixed_fidelity": normalized_mixed_fidelity,
        "surface_wave_model": normalized_surface_wave_model,
    }


def resolve_manifest_simulation_plan(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
) -> dict[str, Any]:
    manifest_file = Path(manifest_path).resolve()
    schema_file = Path(schema_path).resolve()
    design_lock_file = Path(design_lock_path).resolve()

    cfg = load_config(config_path)
    config_file = get_config_path(cfg)
    project_root = get_project_root(cfg)
    if config_file is None:
        raise ValueError("Loaded config is missing config metadata.")
    if project_root is None:
        raise ValueError("Loaded config is missing project-root metadata.")
    resolved_input_roots = resolve_manifest_input_roots(
        processed_stimulus_dir=cfg["paths"]["processed_stimulus_dir"],
        processed_retinal_dir=cfg["paths"]["processed_retinal_dir"],
    )

    manifest_payload = load_yaml(manifest_file)
    schema_payload = load_json(schema_file)
    design_lock_payload = load_yaml(design_lock_file)
    manifest_summary = validate_manifest_payload(
        manifest=copy.deepcopy(manifest_payload),
        schema=schema_payload,
        design_lock=design_lock_payload,
        manifest_path=manifest_file,
        processed_stimulus_dir=resolved_input_roots.processed_stimulus_dir,
    )

    runtime_config = normalize_simulation_runtime_config(
        cfg.get("simulation"),
        default_timebase=_default_timebase_from_manifest_summary(manifest_summary),
        project_root=project_root,
    )
    configured_ablation_realization = (
        None
        if cfg.get(EXPERIMENT_SUITE_ABLATION_CONFIG_KEY) is None
        else normalize_experiment_ablation_realization(
            _require_mapping(
                cfg.get(EXPERIMENT_SUITE_ABLATION_CONFIG_KEY),
                field_name=EXPERIMENT_SUITE_ABLATION_CONFIG_KEY,
            )
        )
    )
    selection_reference = _resolve_selection_reference(
        manifest=manifest_payload,
        cfg=cfg,
    )
    input_reference = _resolve_input_reference(
        manifest_path=manifest_file,
        manifest_payload=manifest_payload,
        manifest_summary=manifest_summary,
        runtime_config=runtime_config,
        schema_path=schema_file,
        design_lock_path=design_lock_file,
        processed_stimulus_dir=resolved_input_roots.processed_stimulus_dir,
        processed_retinal_dir=resolved_input_roots.processed_retinal_dir,
    )
    circuit_assets = _resolve_circuit_assets(
        manifest=manifest_payload,
        cfg=cfg,
        selection_reference=selection_reference,
    )
    manifest_reference = build_simulator_manifest_reference(
        experiment_id=manifest_payload["experiment_id"],
        manifest_id=manifest_payload["experiment_id"],
        manifest_path=manifest_file,
        milestone=manifest_payload["milestone"],
        brief_version=manifest_payload.get("brief_version"),
        hypothesis_version=manifest_payload.get("hypothesis_version"),
    )
    output_targets = _resolve_output_targets(
        output_bundle=manifest_payload["output_bundle"],
        project_root=project_root,
    )
    seed_sweep = _normalize_seed_sweep(manifest_payload.get("seed_sweep"))

    arm_plans: list[dict[str, Any]] = []
    for arm_index, arm in enumerate(manifest_payload["comparison_arms"]):
        resolved_arm_payload = copy.deepcopy(dict(arm))
        seed_handling = _resolve_arm_seed_handling(
            arm=resolved_arm_payload,
            arm_index=arm_index,
            manifest_random_seed=manifest_payload["random_seed"],
            seed_sweep=seed_sweep,
        )
        materialized_ablation_realization = (
            None
            if configured_ablation_realization is None
            else materialize_experiment_ablation_realization_for_seed(
                configured_ablation_realization,
                simulation_seed=int(seed_handling["default_seed"]),
            )
        )
        if materialized_ablation_realization is not None:
            resolved_arm_payload = apply_experiment_ablation_to_arm_payload(
                arm_payload=resolved_arm_payload,
                realization=materialized_ablation_realization,
            )
        arm_reference = build_simulator_arm_reference(
            arm_id=resolved_arm_payload["arm_id"],
            model_mode=resolved_arm_payload["model_mode"],
            baseline_family=resolved_arm_payload["baseline_family"],
            comparison_tags=resolved_arm_payload.get("tags"),
        )
        determinism = build_simulator_determinism(
            seed=seed_handling["default_seed"],
            rng_family=runtime_config["determinism"]["rng_family"],
            seed_scope=runtime_config["determinism"]["seed_scope"],
        )
        topology_condition = _normalize_identifier(
            resolved_arm_payload["topology_condition"],
            field_name=f"comparison_arms[{arm_index}].topology_condition",
        )
        morphology_condition = _normalize_identifier(
            resolved_arm_payload["morphology_condition"],
            field_name=f"comparison_arms[{arm_index}].morphology_condition",
        )
        model_configuration = _build_model_configuration(
            arm_reference=arm_reference,
            arm_payload=resolved_arm_payload,
            runtime_config=runtime_config,
            circuit_assets=circuit_assets,
            topology_condition=topology_condition,
        )
        arm_plan = {
            "plan_version": SIMULATION_PLAN_VERSION,
            "arm_index": arm_index,
            "manifest_reference": copy.deepcopy(manifest_reference),
            "arm_reference": copy.deepcopy(arm_reference),
            "topology_condition": topology_condition,
            "morphology_condition": morphology_condition,
            "notes": _normalize_nonempty_string(
                resolved_arm_payload["notes"],
                field_name=f"comparison_arms[{arm_index}].notes",
            ),
            "tags": _normalize_identifier_list(
                resolved_arm_payload.get("tags"),
                field_name=f"comparison_arms[{arm_index}].tags",
            ),
            "selection": copy.deepcopy(selection_reference),
            "input_reference": copy.deepcopy(input_reference),
            "stimulus_reference": copy.deepcopy(
                manifest_summary["stimulus_bundle_reference"]
            ),
            "resolved_stimulus": copy.deepcopy(manifest_summary["resolved_stimulus"]),
            "retinal_input_reference": copy.deepcopy(
                input_reference.get("retinal_bundle_reference")
            ),
            "circuit_assets": copy.deepcopy(circuit_assets),
            "runtime": {
                "config_version": runtime_config["version"],
                "time_unit": runtime_config["time_unit"],
                "timebase": copy.deepcopy(runtime_config["timebase"]),
                "readout_catalog": copy.deepcopy(runtime_config["readout_catalog"]),
                "shared_readout_catalog": copy.deepcopy(
                    runtime_config["shared_readout_catalog"]
                ),
                "determinism_defaults": copy.deepcopy(runtime_config["determinism"]),
                "processed_simulator_results_dir": str(
                    Path(cfg["paths"]["processed_simulator_results_dir"]).resolve()
                ),
            },
            "seed_handling": seed_handling,
            "determinism": determinism,
            "model_configuration": model_configuration,
            "comparison_output_targets": copy.deepcopy(output_targets),
            "must_show_outputs": list(manifest_payload["must_show_outputs"]),
            "primary_metric": _normalize_identifier(
                manifest_payload["primary_metric"],
                field_name="manifest.primary_metric",
            ),
            "companion_metrics": _normalize_identifier_list(
                manifest_payload.get("companion_metrics"),
                field_name="manifest.companion_metrics",
            ),
        }
        if materialized_ablation_realization is not None:
            arm_plan = apply_experiment_ablation_to_arm_plan(
                arm_plan=arm_plan,
                realization=materialized_ablation_realization,
            )
            model_configuration = copy.deepcopy(dict(arm_plan["model_configuration"]))
        selected_assets = _build_selected_assets(
            selection_reference=selection_reference,
            input_reference=input_reference,
            circuit_assets=circuit_assets,
            arm_reference=arm_reference,
            model_configuration=model_configuration,
            config_path=config_file.resolve(),
        )
        result_bundle_metadata = build_simulator_result_bundle_metadata(
            manifest_reference=manifest_reference,
            arm_reference=arm_reference,
            determinism=determinism,
            timebase=runtime_config["timebase"],
            selected_assets=selected_assets,
            readout_catalog=runtime_config["shared_readout_catalog"],
            processed_simulator_results_dir=cfg["paths"]["processed_simulator_results_dir"],
        )
        result_bundle_reference = build_simulator_result_bundle_reference(
            result_bundle_metadata
        )
        arm_plan["selected_assets"] = copy.deepcopy(result_bundle_metadata["selected_assets"])
        arm_plan["result_bundle"] = {
            "reference": result_bundle_reference,
            "metadata": result_bundle_metadata,
        }
        arm_plans.append(arm_plan)

    readout_analysis_plan = _build_readout_analysis_plan(
        manifest_payload=manifest_payload,
        manifest_summary=manifest_summary,
        cfg=cfg,
        project_root=project_root,
        manifest_reference=manifest_reference,
        runtime_config=runtime_config,
        arm_plans=arm_plans,
        output_targets=output_targets,
        seed_sweep=seed_sweep,
    )

    return {
        "plan_version": SIMULATION_PLAN_VERSION,
        "manifest_reference": manifest_reference,
        "runtime_config": {
            "config_path": str(config_file.resolve()),
            "project_root": str(project_root.resolve()),
            "simulation": copy.deepcopy(runtime_config),
        },
        "seed_sweep": seed_sweep,
        "seed_sweep_ordering": DEFAULT_SEED_SWEEP_ORDERING,
        "stable_arm_ordering": DEFAULT_STABLE_ARM_ORDERING,
        "arm_order": [plan["arm_reference"]["arm_id"] for plan in arm_plans],
        "arm_plans": arm_plans,
        "readout_analysis_plan": readout_analysis_plan,
    }


def resolve_manifest_readout_analysis_plan(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
) -> dict[str, Any]:
    simulation_plan = resolve_manifest_simulation_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    return copy.deepcopy(
        _require_mapping(
            simulation_plan.get("readout_analysis_plan"),
            field_name="simulation_plan.readout_analysis_plan",
        )
    )


def _build_readout_analysis_plan(
    *,
    manifest_payload: Mapping[str, Any],
    manifest_summary: Mapping[str, Any],
    cfg: Mapping[str, Any],
    project_root: Path,
    manifest_reference: Mapping[str, Any],
    runtime_config: Mapping[str, Any],
    arm_plans: Sequence[Mapping[str, Any]],
    output_targets: Mapping[str, Any],
    seed_sweep: Sequence[int],
) -> dict[str, Any]:
    analysis_contract = build_readout_analysis_contract_metadata()
    normalized_analysis_config = _normalize_readout_analysis_config(
        cfg.get("analysis"),
        project_root=project_root,
        timebase=runtime_config["timebase"],
        resolved_stimulus=manifest_summary["resolved_stimulus"],
    )
    active_shared_readouts = _resolve_active_shared_readouts(
        runtime_config["shared_readout_catalog"],
        requested_readout_ids=normalized_analysis_config["active_readout_ids"],
    )
    condition_catalog, condition_pair_catalog = _resolve_analysis_condition_catalog(
        manifest_summary["resolved_stimulus"]
    )
    analysis_window_catalog = _build_analysis_window_catalog(
        timebase=runtime_config["timebase"],
        resolved_stimulus=manifest_summary["resolved_stimulus"],
        overrides=normalized_analysis_config["analysis_windows"],
    )
    arm_pair_catalog = _build_analysis_arm_pair_catalog(arm_plans)
    comparison_group_catalog = _build_analysis_comparison_group_catalog(arm_pair_catalog)
    seed_aggregation_rules = _build_seed_aggregation_rules(seed_sweep)
    experiment_output_targets = _build_experiment_output_targets(
        manifest_payload=manifest_payload,
        output_targets=output_targets,
        requested_output_ids=normalized_analysis_config["output_ids"],
        configured_output_targets=normalized_analysis_config["experiment_output_targets"],
        project_root=project_root,
        comparison_group_catalog=comparison_group_catalog,
        arm_pair_catalog=arm_pair_catalog,
        analysis_contract=analysis_contract,
    )
    selection = _resolve_active_analysis_selection(
        manifest_payload=manifest_payload,
        analysis_contract=analysis_contract,
        requested_metric_ids=normalized_analysis_config["active_metric_ids"],
        requested_null_test_ids=normalized_analysis_config["null_test_ids"],
        experiment_output_targets=experiment_output_targets,
    )
    base_artifact_classes = _resolve_base_analysis_artifact_classes(
        cfg=cfg,
        arm_plans=arm_plans,
    )
    _validate_active_analysis_metrics(
        active_metric_ids=selection["active_metric_ids"],
        analysis_contract=analysis_contract,
        active_shared_readouts=active_shared_readouts,
        condition_pair_catalog=condition_pair_catalog,
        base_artifact_classes=base_artifact_classes,
    )
    metric_recipe_catalog = _build_metric_recipe_catalog(
        active_metric_ids=selection["active_metric_ids"],
        analysis_contract=analysis_contract,
        active_shared_readouts=active_shared_readouts,
        analysis_window_catalog=analysis_window_catalog,
        condition_catalog=condition_catalog,
        condition_pair_catalog=condition_pair_catalog,
        arm_plans=arm_plans,
    )
    available_artifact_classes = _resolve_available_analysis_artifact_classes(
        base_artifact_classes=base_artifact_classes,
        active_metric_ids=selection["active_metric_ids"],
        active_null_test_ids=selection["active_null_test_ids"],
        analysis_contract=analysis_contract,
    )
    null_test_declarations = _build_null_test_declarations(
        active_null_test_ids=selection["active_null_test_ids"],
        analysis_contract=analysis_contract,
        available_artifact_classes=available_artifact_classes,
        condition_pair_catalog=condition_pair_catalog,
        comparison_group_catalog=comparison_group_catalog,
        metric_recipe_catalog=metric_recipe_catalog,
        seed_aggregation_rules=seed_aggregation_rules,
    )
    _validate_experiment_output_targets(
        experiment_output_targets=experiment_output_targets,
        active_metric_ids=selection["active_metric_ids"],
        available_artifact_classes=available_artifact_classes,
        comparison_group_catalog=comparison_group_catalog,
        arm_pair_catalog=arm_pair_catalog,
        active_shared_readouts=active_shared_readouts,
        analysis_contract=analysis_contract,
    )
    manifest_metric_requests = _build_manifest_metric_request_catalog(
        manifest_payload=manifest_payload,
        analysis_contract=analysis_contract,
        metric_recipe_catalog=metric_recipe_catalog,
        comparison_group_catalog=comparison_group_catalog,
        arm_pair_catalog=arm_pair_catalog,
        seed_aggregation_rules=seed_aggregation_rules,
    )
    active_metric_definitions = [
        get_readout_analysis_metric_definition(metric_id, record=analysis_contract)
        for metric_id in selection["active_metric_ids"]
    ]
    active_output_definitions = [
        get_experiment_comparison_output_definition(output_id, record=analysis_contract)
        for output_id in selection["active_output_ids"]
    ]
    return {
        "plan_version": READOUT_ANALYSIS_PLAN_VERSION,
        "manifest_reference": copy.deepcopy(dict(manifest_reference)),
        "contract_reference": {
            "contract_version": analysis_contract["contract_version"],
            "design_note": analysis_contract["design_note"],
            "design_note_version": analysis_contract["design_note_version"],
            "locked_readout_stop_point": analysis_contract["locked_readout_stop_point"],
        },
        "analysis_config": copy.deepcopy(normalized_analysis_config),
        "active_shared_readout_ordering": "readout_id_ascending",
        "active_shared_readouts": active_shared_readouts,
        "condition_catalog": condition_catalog,
        "condition_pair_catalog": condition_pair_catalog,
        "analysis_window_catalog": analysis_window_catalog,
        "arm_pair_catalog": arm_pair_catalog,
        "comparison_group_catalog": comparison_group_catalog,
        "seed_aggregation_rules": seed_aggregation_rules,
        "active_metric_ids": list(selection["active_metric_ids"]),
        "active_metric_definitions": active_metric_definitions,
        "active_output_ids": list(selection["active_output_ids"]),
        "active_output_definitions": active_output_definitions,
        "active_null_test_ids": list(selection["active_null_test_ids"]),
        "manifest_metric_requests": manifest_metric_requests,
        "metric_recipe_catalog": metric_recipe_catalog,
        "null_test_declarations": null_test_declarations,
        "analysis_artifact_classes": sorted(available_artifact_classes),
        "per_run_output_targets": _build_per_run_analysis_output_targets(arm_plans),
        "experiment_output_targets": experiment_output_targets,
    }


def _normalize_readout_analysis_config(
    payload: Any,
    *,
    project_root: Path,
    timebase: Mapping[str, Any],
    resolved_stimulus: Mapping[str, Any],
) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError("analysis must be a mapping when provided.")
    unknown_keys = sorted(set(raw_payload) - ALLOWED_ANALYSIS_CONFIG_KEYS)
    if unknown_keys:
        raise ValueError(
            "analysis contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    version = _normalize_nonempty_string(
        raw_payload.get("version", READOUT_ANALYSIS_CONFIG_VERSION),
        field_name="analysis.version",
    )
    if version != READOUT_ANALYSIS_CONFIG_VERSION:
        raise ValueError(
            "analysis.version must be "
            f"{READOUT_ANALYSIS_CONFIG_VERSION!r}."
        )
    analysis_windows = _normalize_analysis_window_overrides(
        raw_payload.get("analysis_windows"),
        timebase=timebase,
        resolved_stimulus=resolved_stimulus,
    )
    experiment_output_targets = _normalize_analysis_output_targets(
        raw_payload.get("experiment_output_targets"),
        project_root=project_root,
    )
    requested_output_ids = set(
        _normalize_identifier_list(
            raw_payload.get("output_ids"),
            field_name="analysis.output_ids",
        )
    )
    requested_output_ids.update(
        item["output_id"]
        for item in experiment_output_targets
    )
    return {
        "version": version,
        "active_readout_ids": _normalize_identifier_list(
            raw_payload.get("active_readout_ids"),
            field_name="analysis.active_readout_ids",
        ),
        "active_metric_ids": _normalize_identifier_list(
            raw_payload.get("active_metric_ids"),
            field_name="analysis.active_metric_ids",
        ),
        "analysis_windows": analysis_windows,
        "null_test_ids": _normalize_identifier_list(
            raw_payload.get("null_test_ids"),
            field_name="analysis.null_test_ids",
        ),
        "output_ids": sorted(requested_output_ids),
        "experiment_output_targets": experiment_output_targets,
    }


def _normalize_analysis_window_overrides(
    payload: Any,
    *,
    timebase: Mapping[str, Any],
    resolved_stimulus: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError("analysis.analysis_windows must be a mapping when provided.")
    default_windows = {
        item["window_id"]: item
        for item in _build_analysis_window_catalog(
            timebase=timebase,
            resolved_stimulus=resolved_stimulus,
            overrides={},
        )
    }
    overrides: dict[str, dict[str, Any]] = {}
    for window_id, record in dict(payload).items():
        normalized_window_id = _normalize_identifier(
            window_id,
            field_name="analysis.analysis_windows.window_id",
        )
        if normalized_window_id not in default_windows:
            raise ValueError(
                "analysis.analysis_windows may only override known window ids, got "
                f"{normalized_window_id!r}."
            )
        if not isinstance(record, Mapping):
            raise ValueError(
                f"analysis.analysis_windows.{normalized_window_id} must be a mapping."
            )
        raw_record = dict(record)
        unknown_keys = sorted(set(raw_record) - ALLOWED_ANALYSIS_WINDOW_KEYS)
        if unknown_keys:
            raise ValueError(
                f"analysis.analysis_windows.{normalized_window_id} contains unsupported keys: "
                f"{unknown_keys!r}."
            )
        merged = copy.deepcopy(default_windows[normalized_window_id])
        if "start_ms" in raw_record:
            merged["start_ms"] = _normalize_float(
                raw_record["start_ms"],
                field_name=f"analysis.analysis_windows.{normalized_window_id}.start_ms",
            )
        if "end_ms" in raw_record:
            merged["end_ms"] = _normalize_float(
                raw_record["end_ms"],
                field_name=f"analysis.analysis_windows.{normalized_window_id}.end_ms",
            )
        if "description" in raw_record:
            merged["description"] = _normalize_nonempty_string(
                raw_record["description"],
                field_name=f"analysis.analysis_windows.{normalized_window_id}.description",
            )
        overrides[normalized_window_id] = merged
    return overrides


def _normalize_analysis_output_targets(
    payload: Any,
    *,
    project_root: Path,
) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("analysis.experiment_output_targets must be a list when provided.")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError(
                f"analysis.experiment_output_targets[{index}] must be a mapping."
            )
        raw_item = dict(item)
        unknown_keys = sorted(set(raw_item) - ALLOWED_ANALYSIS_OUTPUT_TARGET_KEYS)
        if unknown_keys:
            raise ValueError(
                "analysis.experiment_output_targets contains unsupported keys: "
                f"{unknown_keys!r}."
            )
        normalized.append(
            {
                "output_id": _normalize_identifier(
                    raw_item.get("output_id"),
                    field_name=f"analysis.experiment_output_targets[{index}].output_id",
                ),
                "path": str(
                    _resolve_project_path(
                        _normalize_nonempty_string(
                            raw_item.get("path"),
                            field_name=f"analysis.experiment_output_targets[{index}].path",
                        ),
                        project_root,
                    )
                ),
            }
        )
    normalized.sort(key=lambda item: (item["output_id"], item["path"]))
    seen_output_ids: set[str] = set()
    for item in normalized:
        if item["output_id"] in seen_output_ids:
            raise ValueError(
                "analysis.experiment_output_targets contains duplicate output_id "
                f"{item['output_id']!r}."
            )
        seen_output_ids.add(item["output_id"])
    return normalized


def _build_analysis_window_catalog(
    *,
    timebase: Mapping[str, Any],
    resolved_stimulus: Mapping[str, Any],
    overrides: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    normalized_timebase = normalize_simulator_timebase(timebase)
    time_origin_ms = float(normalized_timebase["time_origin_ms"])
    end_ms = time_origin_ms + float(normalized_timebase["duration_ms"])
    parameter_snapshot = _require_mapping(
        resolved_stimulus.get("parameter_snapshot"),
        field_name="resolved_stimulus.parameter_snapshot",
    )
    stimulus_onset_ms = float(parameter_snapshot.get("onset_ms", time_origin_ms))
    stimulus_offset_ms = float(parameter_snapshot.get("offset_ms", end_ms))
    clamped_onset_ms = max(time_origin_ms, min(end_ms, stimulus_onset_ms))
    clamped_offset_ms = max(clamped_onset_ms, min(end_ms, stimulus_offset_ms))
    defaults = {
        FULL_TIMEBASE_WINDOW_ID: {
            "window_id": FULL_TIMEBASE_WINDOW_ID,
            "start_ms": time_origin_ms,
            "end_ms": end_ms,
            "description": "Entire declared simulator timebase window.",
            "source": "simulation.timebase",
        },
        SHARED_RESPONSE_WINDOW_ID: {
            "window_id": SHARED_RESPONSE_WINDOW_ID,
            "start_ms": clamped_onset_ms,
            "end_ms": clamped_offset_ms,
            "description": "Shared response window derived from the declared stimulus onset/offset.",
            "source": "resolved_stimulus.parameter_snapshot",
        },
        TASK_DECODER_WINDOW_ID: {
            "window_id": TASK_DECODER_WINDOW_ID,
            "start_ms": clamped_onset_ms,
            "end_ms": clamped_offset_ms,
            "description": "Task-decoder window derived from the declared stimulus onset/offset.",
            "source": "resolved_stimulus.parameter_snapshot",
        },
        WAVE_DIAGNOSTIC_WINDOW_ID: {
            "window_id": WAVE_DIAGNOSTIC_WINDOW_ID,
            "start_ms": clamped_onset_ms,
            "end_ms": clamped_offset_ms,
            "description": "Wave-diagnostic window derived from the declared stimulus onset/offset.",
            "source": "resolved_stimulus.parameter_snapshot",
        },
    }
    windows: list[dict[str, Any]] = []
    for window_id in ANALYSIS_WINDOW_ORDER:
        merged = copy.deepcopy(defaults[window_id])
        if window_id in overrides:
            merged.update(copy.deepcopy(dict(overrides[window_id])))
            merged["window_id"] = window_id
        if float(merged["end_ms"]) <= float(merged["start_ms"]):
            raise ValueError(
                f"analysis window {window_id!r} must have end_ms greater than start_ms."
            )
        windows.append(merged)
    return windows


def _resolve_analysis_condition_catalog(
    resolved_stimulus: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    parameter_snapshot = _require_mapping(
        resolved_stimulus.get("parameter_snapshot"),
        field_name="resolved_stimulus.parameter_snapshot",
    )
    conditions: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    direction_context = _resolve_direction_condition_context(parameter_snapshot)
    if direction_context is not None:
        conditions.extend(
            [
                {
                    "condition_id": PREFERRED_DIRECTION_CONDITION_ID,
                    "display_name": "Preferred Direction",
                    "parameter_name": direction_context["parameter_name"],
                    "value": direction_context["preferred_value"],
                },
                {
                    "condition_id": NULL_DIRECTION_CONDITION_ID,
                    "display_name": "Null Direction",
                    "parameter_name": direction_context["parameter_name"],
                    "value": direction_context["null_value"],
                },
            ]
        )
        pairs.append(
            {
                "pair_id": PREFERRED_VS_NULL_PAIR_ID,
                "pair_kind": "direction_opposition",
                "left_condition_id": PREFERRED_DIRECTION_CONDITION_ID,
                "right_condition_id": NULL_DIRECTION_CONDITION_ID,
                "description": "Preferred-versus-null directional pairing derived from the declared stimulus direction parameter.",
            }
        )
    if "polarity" in parameter_snapshot:
        conditions.extend(
            [
                {
                    "condition_id": ON_POLARITY_CONDITION_ID,
                    "display_name": "ON Polarity",
                    "parameter_name": "polarity",
                    "value": "positive",
                },
                {
                    "condition_id": OFF_POLARITY_CONDITION_ID,
                    "display_name": "OFF Polarity",
                    "parameter_name": "polarity",
                    "value": "negative",
                },
            ]
        )
        pairs.append(
            {
                "pair_id": ON_VS_OFF_PAIR_ID,
                "pair_kind": "polarity_opposition",
                "left_condition_id": ON_POLARITY_CONDITION_ID,
                "right_condition_id": OFF_POLARITY_CONDITION_ID,
                "description": "ON-versus-OFF polarity pairing derived from the declared stimulus polarity semantics.",
            }
        )
    return conditions, pairs


def _resolve_direction_condition_context(
    parameter_snapshot: Mapping[str, Any],
) -> dict[str, Any] | None:
    if "direction_deg" in parameter_snapshot:
        preferred_value = float(parameter_snapshot["direction_deg"])
        return {
            "parameter_name": "direction_deg",
            "preferred_value": preferred_value,
            "null_value": round((preferred_value + 180.0) % 360.0, 6),
        }
    if "drift_direction_deg" in parameter_snapshot:
        preferred_value = float(parameter_snapshot["drift_direction_deg"])
        return {
            "parameter_name": "drift_direction_deg",
            "preferred_value": preferred_value,
            "null_value": round((preferred_value + 180.0) % 360.0, 6),
        }
    if "rotation_direction" in parameter_snapshot:
        preferred_value = _normalize_identifier(
            parameter_snapshot["rotation_direction"],
            field_name="resolved_stimulus.parameter_snapshot.rotation_direction",
        )
        if preferred_value == "clockwise":
            null_value = "counterclockwise"
        elif preferred_value == "counterclockwise":
            null_value = "clockwise"
        else:
            raise ValueError(
                "resolved_stimulus.parameter_snapshot.rotation_direction must be "
                "'clockwise' or 'counterclockwise'."
            )
        return {
            "parameter_name": "rotation_direction",
            "preferred_value": preferred_value,
            "null_value": null_value,
        }
    return None


def _resolve_active_shared_readouts(
    shared_readout_catalog: Sequence[Mapping[str, Any]],
    *,
    requested_readout_ids: Sequence[str],
) -> list[dict[str, Any]]:
    catalog_by_id = {
        str(item["readout_id"]): copy.deepcopy(dict(item))
        for item in shared_readout_catalog
    }
    if requested_readout_ids:
        missing_readout_ids = sorted(
            set(requested_readout_ids) - set(catalog_by_id)
        )
        if missing_readout_ids:
            raise ValueError(
                "analysis.active_readout_ids references readout ids that are not present "
                f"in simulation.shared_readout_catalog: {missing_readout_ids!r}."
            )
        resolved = [catalog_by_id[readout_id] for readout_id in requested_readout_ids]
    else:
        resolved = [
            copy.deepcopy(dict(item))
            for item in shared_readout_catalog
        ]
    if not resolved:
        raise ValueError(
            "The readout-analysis plan requires at least one active shared readout."
        )
    resolved.sort(key=lambda item: item["readout_id"])
    return resolved


def _build_analysis_arm_pair_catalog(
    arm_plans: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    wave_by_topology: dict[str, Mapping[str, Any]] = {}
    baseline_by_family_and_topology: dict[tuple[str, str], Mapping[str, Any]] = {}
    topology_conditions: set[str] = set()
    for arm_plan in arm_plans:
        arm_reference = _require_mapping(
            arm_plan.get("arm_reference"),
            field_name="arm_plan.arm_reference",
        )
        topology_condition = _normalize_identifier(
            arm_plan.get("topology_condition"),
            field_name="arm_plan.topology_condition",
        )
        topology_conditions.add(topology_condition)
        model_mode = _normalize_identifier(
            arm_reference.get("model_mode"),
            field_name="arm_plan.arm_reference.model_mode",
        )
        if model_mode == SURFACE_WAVE_MODEL_MODE:
            wave_by_topology[topology_condition] = arm_plan
            continue
        baseline_family = arm_reference.get("baseline_family")
        if baseline_family is None:
            continue
        normalized_family = _normalize_nonempty_string(
            baseline_family,
            field_name="arm_plan.arm_reference.baseline_family",
        )
        baseline_by_family_and_topology[(normalized_family, topology_condition)] = arm_plan

    records: list[dict[str, Any]] = []
    for baseline_family in (P0_BASELINE_FAMILY, P1_BASELINE_FAMILY):
        for topology_condition in sorted(topology_conditions, key=_topology_sort_key):
            baseline_arm = baseline_by_family_and_topology.get((baseline_family, topology_condition))
            wave_arm = wave_by_topology.get(topology_condition)
            if baseline_arm is None or wave_arm is None:
                continue
            baseline_arm_id = str(
                _require_mapping(
                    baseline_arm.get("arm_reference"),
                    field_name="baseline_arm.arm_reference",
                )["arm_id"]
            )
            surface_wave_arm_id = str(
                _require_mapping(
                    wave_arm.get("arm_reference"),
                    field_name="wave_arm.arm_reference",
                )["arm_id"]
            )
            records.append(
                {
                    "group_id": (
                        f"matched_surface_wave_vs_{baseline_family.lower()}__"
                        f"{topology_condition}"
                    ),
                    "group_kind": "matched_surface_wave_vs_baseline",
                    "baseline_family": baseline_family,
                    "topology_condition": topology_condition,
                    "baseline_arm_id": baseline_arm_id,
                    "surface_wave_arm_id": surface_wave_arm_id,
                    "arm_ids": [baseline_arm_id, surface_wave_arm_id],
                    "comparison_semantics": "surface_wave_minus_baseline",
                }
            )
    return records


def _build_analysis_comparison_group_catalog(
    arm_pair_catalog: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    pairs_by_family_and_topology = {
        (
            str(item["baseline_family"]),
            str(item["topology_condition"]),
        ): item
        for item in arm_pair_catalog
    }
    records: list[dict[str, Any]] = []
    for baseline_family in (P0_BASELINE_FAMILY, P1_BASELINE_FAMILY):
        intact_pair = pairs_by_family_and_topology.get((baseline_family, "intact"))
        shuffled_pair = pairs_by_family_and_topology.get((baseline_family, "shuffled"))
        if intact_pair is not None and shuffled_pair is not None:
            records.append(
                {
                    "group_id": f"geometry_ablation__{baseline_family.lower()}",
                    "group_kind": "geometry_ablation",
                    "baseline_family": baseline_family,
                    "component_group_ids": [
                        str(intact_pair["group_id"]),
                        str(shuffled_pair["group_id"]),
                    ],
                    "comparison_semantics": "intact_gap_minus_shuffled_gap",
                }
            )
    topologies = {
        str(item["topology_condition"])
        for item in arm_pair_catalog
    }
    for topology_condition in sorted(topologies, key=_topology_sort_key):
        p0_pair = pairs_by_family_and_topology.get((P0_BASELINE_FAMILY, topology_condition))
        p1_pair = pairs_by_family_and_topology.get((P1_BASELINE_FAMILY, topology_condition))
        if p0_pair is not None and p1_pair is not None:
            records.append(
                {
                    "group_id": f"baseline_strength_challenge__{topology_condition}",
                    "group_kind": "baseline_strength_challenge",
                    "topology_condition": topology_condition,
                    "component_group_ids": [
                        str(p0_pair["group_id"]),
                        str(p1_pair["group_id"]),
                    ],
                    "comparison_semantics": "p1_survival_against_canonical_p0_reference",
                }
            )
    return records


def _build_seed_aggregation_rules(seed_sweep: Sequence[int]) -> list[dict[str, Any]]:
    rules = [
        {
            "rule_id": PER_RUN_SINGLE_SEED_RULE_ID,
            "aggregation_scope": "single_run",
            "summary_statistics": ["identity"],
            "seed_count": 1,
            "seed_ordering": DEFAULT_SEED_SWEEP_ORDERING,
        }
    ]
    if seed_sweep:
        rules.append(
            {
                "rule_id": MANIFEST_SEED_SWEEP_ROLLUP_RULE_ID,
                "aggregation_scope": "arm_metric_across_seed_sweep",
                "seed_sweep": [int(seed) for seed in seed_sweep],
                "seed_count": len(seed_sweep),
                "summary_statistics": ["mean", "median", "min", "max", "std"],
                "seed_ordering": DEFAULT_SEED_SWEEP_ORDERING,
            }
        )
    return rules


def _build_experiment_output_targets(
    *,
    manifest_payload: Mapping[str, Any],
    output_targets: Mapping[str, Any],
    requested_output_ids: Sequence[str],
    configured_output_targets: Sequence[Mapping[str, Any]],
    project_root: Path,
    comparison_group_catalog: Sequence[Mapping[str, Any]],
    arm_pair_catalog: Sequence[Mapping[str, Any]],
    analysis_contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    del project_root
    del comparison_group_catalog
    del arm_pair_catalog
    declared_targets: dict[str, dict[str, Any]] = {}
    for plot in output_targets.get("plots", []):
        declared_targets[str(plot["id"])] = {
            "path": str(plot["path"]),
            "declared_output_kind": "plot",
        }
    for state in output_targets.get("ui_states", []):
        declared_targets[str(state["id"])] = {
            "path": str(state["path"]),
            "declared_output_kind": "ui_state",
        }

    records: list[dict[str, Any]] = []
    seen_analysis_output_ids: set[str] = set()
    for output_id in manifest_payload.get("must_show_outputs", []):
        normalized_output_id = _normalize_identifier(
            output_id,
            field_name="manifest.must_show_outputs",
        )
        target = declared_targets.get(normalized_output_id)
        if target is None:
            raise ValueError(
                f"Manifest must_show_output {normalized_output_id!r} is missing from the resolved output bundle."
            )
        analysis_output_id = MANIFEST_TO_ANALYSIS_OUTPUT_ID.get(normalized_output_id)
        record = {
            "output_id": normalized_output_id,
            "analysis_output_id": analysis_output_id,
            "path": target["path"],
            "source": "manifest.output_bundle",
            "declared_output_kind": target["declared_output_kind"],
        }
        if analysis_output_id is not None:
            output_definition = get_experiment_comparison_output_definition(
                analysis_output_id,
                record=analysis_contract,
            )
            record["output_kind"] = output_definition["output_kind"]
            record["scope_rule"] = output_definition["scope_rule"]
            record["required_metric_ids"] = list(output_definition["required_metric_ids"])
            record["required_source_artifact_classes"] = list(
                output_definition["required_source_artifact_classes"]
            )
            seen_analysis_output_ids.add(analysis_output_id)
        else:
            record["output_kind"] = target["declared_output_kind"]
            record["scope_rule"] = "manifest_declared_output"
            record["required_metric_ids"] = _manifest_only_output_required_metric_ids(
                normalized_output_id
            )
            record["required_source_artifact_classes"] = []
        records.append(record)

    configured_by_output_id = {
        str(item["output_id"]): dict(item)
        for item in configured_output_targets
    }
    for output_id in sorted(set(requested_output_ids)):
        if output_id in seen_analysis_output_ids:
            continue
        configured_target = configured_by_output_id.get(output_id)
        path = configured_target["path"] if configured_target is not None else None
        output_definition = get_experiment_comparison_output_definition(
            output_id,
            record=analysis_contract,
        )
        records.append(
            {
                "output_id": output_id,
                "analysis_output_id": output_id,
                "path": path,
                "source": (
                    "analysis.experiment_output_targets"
                    if configured_target is not None
                    else "analysis.output_ids"
                ),
                "declared_output_kind": output_definition["output_kind"],
                "output_kind": output_definition["output_kind"],
                "scope_rule": output_definition["scope_rule"],
                "required_metric_ids": list(output_definition["required_metric_ids"]),
                "required_source_artifact_classes": list(
                    output_definition["required_source_artifact_classes"]
                ),
            }
        )
    return records


def _resolve_active_analysis_selection(
    *,
    manifest_payload: Mapping[str, Any],
    analysis_contract: Mapping[str, Any],
    requested_metric_ids: Sequence[str],
    requested_null_test_ids: Sequence[str],
    experiment_output_targets: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    manifest_metric_requests = [
        _normalize_manifest_metric_request(
            manifest_payload["primary_metric"],
            field_name="manifest.primary_metric",
            analysis_contract=analysis_contract,
        ),
        *[
            _normalize_manifest_metric_request(
                metric_id,
                field_name=f"manifest.companion_metrics[{index}]",
                analysis_contract=analysis_contract,
            )
            for index, metric_id in enumerate(manifest_payload.get("companion_metrics", []))
        ],
    ]
    active_metric_ids = set(requested_metric_ids)
    active_null_test_ids = set(requested_null_test_ids)
    active_output_ids: set[str] = set()

    for request in manifest_metric_requests:
        active_metric_ids.update(request["resolved_metric_ids"])
    for target in experiment_output_targets:
        analysis_output_id = target.get("analysis_output_id")
        if analysis_output_id is None:
            continue
        normalized_output_id = _normalize_identifier(
            analysis_output_id,
            field_name="experiment_output_targets.analysis_output_id",
        )
        active_output_ids.add(normalized_output_id)
        output_definition = get_experiment_comparison_output_definition(
            normalized_output_id,
            record=analysis_contract,
        )
        active_metric_ids.update(output_definition["required_metric_ids"])
    for success_criterion_id in manifest_payload.get("success_criteria_ids", []):
        normalized_success_id = _normalize_identifier(
            success_criterion_id,
            field_name="manifest.success_criteria_ids",
        )
        active_null_test_ids.update(
            SUCCESS_CRITERION_NULL_TEST_IDS.get(normalized_success_id, ())
        )

    changed = True
    while changed:
        changed = False
        for null_test_id in list(active_null_test_ids):
            null_test_definition = get_readout_analysis_null_test_hook(
                null_test_id,
                record=analysis_contract,
            )
            new_metric_ids = set(null_test_definition["required_metric_ids"]) - active_metric_ids
            if new_metric_ids:
                active_metric_ids.update(new_metric_ids)
                changed = True

    return {
        "manifest_metric_requests": manifest_metric_requests,
        "active_metric_ids": sorted(active_metric_ids),
        "active_null_test_ids": sorted(active_null_test_ids),
        "active_output_ids": sorted(active_output_ids),
    }


def _resolve_base_analysis_artifact_classes(
    *,
    cfg: Mapping[str, Any],
    arm_plans: Sequence[Mapping[str, Any]],
) -> set[str]:
    artifact_classes = {
        SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
        SHARED_READOUT_TRACES_ARTIFACT_CLASS,
        SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
        STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
        TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
    }
    if len(arm_plans) > 1:
        artifact_classes.add(EXPERIMENT_BUNDLE_SET_ARTIFACT_CLASS)
    if any(
        str(_require_mapping(arm_plan["arm_reference"], field_name="arm_reference")["model_mode"])
        == SURFACE_WAVE_MODEL_MODE
        for arm_plan in arm_plans
    ):
        artifact_classes.update(
            {
                SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
                SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
                SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
            }
        )
    if cfg.get("retinal_geometry") is not None or any(
        arm_plan.get("retinal_input_reference") is not None
        for arm_plan in arm_plans
    ):
        artifact_classes.add(RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS)
    return artifact_classes


def _resolve_available_analysis_artifact_classes(
    *,
    base_artifact_classes: set[str],
    active_metric_ids: Sequence[str],
    active_null_test_ids: Sequence[str],
    analysis_contract: Mapping[str, Any],
) -> set[str]:
    artifact_classes = set(base_artifact_classes)
    if active_metric_ids:
        artifact_classes.add(ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS)
    if active_null_test_ids:
        artifact_classes.add(ANALYSIS_NULL_TEST_ROWS_ARTIFACT_CLASS)
    if any(
        get_readout_analysis_metric_definition(metric_id, record=analysis_contract)["metric_class"]
        == "wave_only_diagnostic"
        for metric_id in active_metric_ids
    ):
        artifact_classes.add(WAVE_DIAGNOSTIC_ROWS_ARTIFACT_CLASS)
    return artifact_classes


def _validate_active_analysis_metrics(
    *,
    active_metric_ids: Sequence[str],
    analysis_contract: Mapping[str, Any],
    active_shared_readouts: Sequence[Mapping[str, Any]],
    condition_pair_catalog: Sequence[Mapping[str, Any]],
    base_artifact_classes: set[str],
) -> None:
    available_pair_ids = {str(item["pair_id"]) for item in condition_pair_catalog}
    for metric_id in active_metric_ids:
        metric_definition = get_readout_analysis_metric_definition(
            metric_id,
            record=analysis_contract,
        )
        missing_artifact_classes = sorted(
            set(metric_definition["required_source_artifact_classes"]) - set(base_artifact_classes)
        )
        if missing_artifact_classes:
            raise ValueError(
                f"Readout-analysis metric {metric_id!r} cannot be realized from local artifacts; "
                f"missing source artifact classes {missing_artifact_classes!r}."
            )
        if (
            SHARED_READOUT_CATALOG_ARTIFACT_CLASS in metric_definition["required_source_artifact_classes"]
            or SHARED_READOUT_TRACES_ARTIFACT_CLASS
            in metric_definition["required_source_artifact_classes"]
        ) and not active_shared_readouts:
            raise ValueError(
                f"Readout-analysis metric {metric_id!r} requires at least one active shared readout."
            )
        missing_pair_ids = sorted(
            set(_required_condition_pair_ids_for_metric(metric_definition)) - available_pair_ids
        )
        if missing_pair_ids:
            raise ValueError(
                f"Readout-analysis metric {metric_id!r} requires stimulus condition pair "
                f"declarations {missing_pair_ids!r}, but the resolved stimulus does not support them."
            )


def _build_metric_recipe_catalog(
    *,
    active_metric_ids: Sequence[str],
    analysis_contract: Mapping[str, Any],
    active_shared_readouts: Sequence[Mapping[str, Any]],
    analysis_window_catalog: Sequence[Mapping[str, Any]],
    condition_catalog: Sequence[Mapping[str, Any]],
    condition_pair_catalog: Sequence[Mapping[str, Any]],
    arm_plans: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    windows_by_id = {
        str(item["window_id"]): item
        for item in analysis_window_catalog
    }
    available_pair_ids = {str(item["pair_id"]) for item in condition_pair_catalog}
    condition_ids = [str(item["condition_id"]) for item in condition_catalog]
    wave_root_ids = _eligible_wave_root_ids(arm_plans)
    records: list[dict[str, Any]] = []
    for metric_id in active_metric_ids:
        metric_definition = get_readout_analysis_metric_definition(
            metric_id,
            record=analysis_contract,
        )
        scope_rule = str(metric_definition["scope_rule"])
        window_id = _analysis_window_id_for_scope(scope_rule)
        recipe_base = {
            "metric_id": metric_id,
            "task_family_id": metric_definition["task_family_id"],
            "metric_class": metric_definition["metric_class"],
            "scope_rule": scope_rule,
            "window_id": window_id,
            "window_reference": copy.deepcopy(windows_by_id[window_id]),
            "required_source_artifact_classes": list(
                metric_definition["required_source_artifact_classes"]
            ),
        }
        if scope_rule == PER_SHARED_READOUT_CONDITION_PAIR_SCOPE:
            for readout in active_shared_readouts:
                for pair_id in _required_condition_pair_ids_for_metric(metric_definition):
                    if pair_id not in available_pair_ids:
                        continue
                    records.append(
                        {
                            **copy.deepcopy(recipe_base),
                            "recipe_id": _build_metric_recipe_id(
                                metric_id,
                                readout_id=str(readout["readout_id"]),
                                window_id=window_id,
                                suffix=pair_id,
                            ),
                            "active_readout_ids": [str(readout["readout_id"])],
                            "condition_ids": [],
                            "condition_pair_id": pair_id,
                            "eligible_root_ids": [],
                        }
                    )
        elif scope_rule == PER_SHARED_READOUT_CONDITION_WINDOW_SCOPE:
            for readout in active_shared_readouts:
                records.append(
                    {
                        **copy.deepcopy(recipe_base),
                        "recipe_id": _build_metric_recipe_id(
                            metric_id,
                            readout_id=str(readout["readout_id"]),
                            window_id=window_id,
                            suffix="conditions",
                        ),
                        "active_readout_ids": [str(readout["readout_id"])],
                        "condition_ids": list(condition_ids),
                        "condition_pair_id": None,
                        "eligible_root_ids": [],
                    }
                )
        elif scope_rule == PER_TASK_DECODER_WINDOW_SCOPE:
            for readout in active_shared_readouts:
                records.append(
                    {
                        **copy.deepcopy(recipe_base),
                        "recipe_id": _build_metric_recipe_id(
                            metric_id,
                            readout_id=str(readout["readout_id"]),
                            window_id=window_id,
                            suffix="task_decoder",
                        ),
                        "active_readout_ids": [str(readout["readout_id"])],
                        "condition_ids": [],
                        "condition_pair_id": (
                            PREFERRED_VS_NULL_PAIR_ID
                            if PREFERRED_VS_NULL_PAIR_ID in available_pair_ids
                            else None
                        ),
                        "eligible_root_ids": [],
                    }
                )
        elif scope_rule in {PER_WAVE_ROOT_WINDOW_SCOPE, PER_WAVE_ROOT_SET_WINDOW_SCOPE}:
            records.append(
                {
                    **copy.deepcopy(recipe_base),
                    "recipe_id": _build_metric_recipe_id(
                        metric_id,
                        readout_id="wave",
                        window_id=window_id,
                        suffix="wave_scope",
                    ),
                    "active_readout_ids": [],
                    "condition_ids": [],
                    "condition_pair_id": None,
                    "eligible_root_ids": list(wave_root_ids),
                }
            )
        else:
            records.append(
                {
                    **copy.deepcopy(recipe_base),
                    "recipe_id": _build_metric_recipe_id(
                        metric_id,
                        readout_id="global",
                        window_id=window_id,
                        suffix="global",
                    ),
                    "active_readout_ids": [],
                    "condition_ids": [],
                    "condition_pair_id": None,
                    "eligible_root_ids": [],
                }
            )
    records.sort(key=lambda item: item["recipe_id"])
    return records


def _build_null_test_declarations(
    *,
    active_null_test_ids: Sequence[str],
    analysis_contract: Mapping[str, Any],
    available_artifact_classes: set[str],
    condition_pair_catalog: Sequence[Mapping[str, Any]],
    comparison_group_catalog: Sequence[Mapping[str, Any]],
    metric_recipe_catalog: Sequence[Mapping[str, Any]],
    seed_aggregation_rules: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    available_pair_ids = {str(item["pair_id"]) for item in condition_pair_catalog}
    available_group_ids_by_kind: dict[str, list[str]] = {}
    for item in comparison_group_catalog:
        available_group_ids_by_kind.setdefault(str(item["group_kind"]), []).append(
            str(item["group_id"])
        )
    seed_rule_ids = {
        str(item["rule_id"])
        for item in seed_aggregation_rules
    }
    recipe_ids_by_metric: dict[str, list[str]] = {}
    for recipe in metric_recipe_catalog:
        recipe_ids_by_metric.setdefault(str(recipe["metric_id"]), []).append(
            str(recipe["recipe_id"])
        )

    records: list[dict[str, Any]] = []
    for null_test_id in active_null_test_ids:
        null_test_definition = get_readout_analysis_null_test_hook(
            null_test_id,
            record=analysis_contract,
        )
        missing_artifact_classes = sorted(
            set(null_test_definition["required_source_artifact_classes"])
            - set(available_artifact_classes)
        )
        if missing_artifact_classes:
            raise ValueError(
                f"Readout-analysis null test {null_test_id!r} cannot be realized from local artifacts; "
                f"missing source artifact classes {missing_artifact_classes!r}."
            )
        required_pair_ids = _required_condition_pair_ids_for_null_test(null_test_id)
        missing_pair_ids = sorted(set(required_pair_ids) - available_pair_ids)
        if missing_pair_ids:
            raise ValueError(
                f"Readout-analysis null test {null_test_id!r} requires condition pair "
                f"declarations {missing_pair_ids!r}, but the resolved stimulus does not support them."
            )
        comparison_group_ids = _required_comparison_group_ids_for_null_test(
            null_test_id,
            available_group_ids_by_kind,
        )
        if null_test_id == "seed_stability" and MANIFEST_SEED_SWEEP_ROLLUP_RULE_ID not in seed_rule_ids:
            raise ValueError(
                "Readout-analysis null test 'seed_stability' requires a declared manifest seed_sweep."
            )
        records.append(
            {
                **copy.deepcopy(null_test_definition),
                "comparison_group_ids": comparison_group_ids,
                "condition_pair_ids": required_pair_ids,
                "metric_recipe_ids": [
                    recipe_id
                    for metric_id in null_test_definition["required_metric_ids"]
                    for recipe_id in recipe_ids_by_metric.get(str(metric_id), [])
                ],
                "seed_aggregation_rule_id": (
                    MANIFEST_SEED_SWEEP_ROLLUP_RULE_ID
                    if null_test_id == "seed_stability"
                    else PER_RUN_SINGLE_SEED_RULE_ID
                ),
            }
        )
    records.sort(key=lambda item: item["null_test_id"])
    return records


def _validate_experiment_output_targets(
    *,
    experiment_output_targets: Sequence[Mapping[str, Any]],
    active_metric_ids: Sequence[str],
    available_artifact_classes: set[str],
    comparison_group_catalog: Sequence[Mapping[str, Any]],
    arm_pair_catalog: Sequence[Mapping[str, Any]],
    active_shared_readouts: Sequence[Mapping[str, Any]],
    analysis_contract: Mapping[str, Any],
) -> None:
    available_group_kinds = {
        str(item["group_kind"])
        for item in comparison_group_catalog
    }
    has_matched_pairs = bool(arm_pair_catalog)
    for target in experiment_output_targets:
        output_id = str(target["output_id"])
        analysis_output_id = target.get("analysis_output_id")
        if analysis_output_id is not None:
            normalized_analysis_output_id = _normalize_identifier(
                analysis_output_id,
                field_name="experiment_output_targets.analysis_output_id",
            )
            if target.get("path") in (None, ""):
                raise ValueError(
                    f"Readout-analysis output {normalized_analysis_output_id!r} was requested "
                    "but no experiment output target path was declared."
                )
            output_definition = get_experiment_comparison_output_definition(
                normalized_analysis_output_id,
                record=analysis_contract,
            )
            missing_artifact_classes = sorted(
                set(output_definition["required_source_artifact_classes"])
                - set(available_artifact_classes)
            )
            if missing_artifact_classes:
                raise ValueError(
                    f"Readout-analysis output {normalized_analysis_output_id!r} cannot be realized "
                    f"from local artifacts; missing source artifact classes {missing_artifact_classes!r}."
                )
            missing_metric_ids = sorted(
                set(output_definition["required_metric_ids"]) - set(active_metric_ids)
            )
            if missing_metric_ids:
                raise ValueError(
                    f"Readout-analysis output {normalized_analysis_output_id!r} requires metric ids "
                    f"{missing_metric_ids!r} that are not active in the normalized analysis plan."
                )
            continue

        if output_id in {"shared_output_trace_overlay", "surface_vs_baseline_split_view"} and not has_matched_pairs:
            raise ValueError(
                f"Manifest output {output_id!r} cannot be realized because no matched baseline-versus-surface_wave arm pair exists."
            )
        if output_id == "shared_output_trace_overlay" and not active_shared_readouts:
            raise ValueError(
                "Manifest output 'shared_output_trace_overlay' requires at least one active shared readout."
            )
        if output_id == "topology_ablation_comparison" and "geometry_ablation" not in available_group_kinds:
            raise ValueError(
                "Manifest output 'topology_ablation_comparison' cannot be realized because no geometry-ablation comparison group exists."
            )
        if output_id == "baseline_challenge_comparison" and "baseline_strength_challenge" not in available_group_kinds:
            raise ValueError(
                "Manifest output 'baseline_challenge_comparison' cannot be realized because no baseline-strength challenge comparison group exists."
            )


def _build_manifest_metric_request_catalog(
    *,
    manifest_payload: Mapping[str, Any],
    analysis_contract: Mapping[str, Any],
    metric_recipe_catalog: Sequence[Mapping[str, Any]],
    comparison_group_catalog: Sequence[Mapping[str, Any]],
    arm_pair_catalog: Sequence[Mapping[str, Any]],
    seed_aggregation_rules: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    available_pair_ids = {
        str(recipe["condition_pair_id"])
        for recipe in metric_recipe_catalog
        if recipe.get("condition_pair_id") is not None
    }
    recipe_ids_by_metric: dict[str, list[str]] = {}
    for recipe in metric_recipe_catalog:
        recipe_ids_by_metric.setdefault(str(recipe["metric_id"]), []).append(
            str(recipe["recipe_id"])
        )
    comparison_groups_by_kind: dict[str, list[str]] = {}
    for item in comparison_group_catalog:
        comparison_groups_by_kind.setdefault(str(item["group_kind"]), []).append(
            str(item["group_id"])
        )
    matched_pair_ids = [str(item["group_id"]) for item in arm_pair_catalog]
    seed_rule_ids = {
        str(item["rule_id"])
        for item in seed_aggregation_rules
    }

    requests = [
        ("primary", manifest_payload["primary_metric"]),
        *[
            ("companion", metric_id)
            for metric_id in manifest_payload.get("companion_metrics", [])
        ],
    ]
    records: list[dict[str, Any]] = []
    for request_index, (request_role, requested_metric_id) in enumerate(requests):
        request = _normalize_manifest_metric_request(
            requested_metric_id,
            field_name=f"manifest.{request_role}_metric",
            analysis_contract=analysis_contract,
        )
        missing_pair_ids = sorted(
            set(request["required_condition_pair_ids"]) - available_pair_ids
        )
        if missing_pair_ids:
            raise ValueError(
                f"Manifest metric request {request['requested_metric_id']!r} requires condition pair "
                f"declarations {missing_pair_ids!r}, but the resolved stimulus does not support them."
            )
        comparison_group_ids = []
        for group_kind in request["comparison_group_kinds"]:
            if group_kind == "matched_surface_wave_vs_baseline":
                comparison_group_ids.extend(matched_pair_ids)
            else:
                comparison_group_ids.extend(comparison_groups_by_kind.get(group_kind, []))
        comparison_group_ids = sorted(set(comparison_group_ids))
        if not comparison_group_ids:
            raise ValueError(
                f"Manifest metric request {request['requested_metric_id']!r} does not have any compatible comparison groups in the normalized analysis plan."
            )
        seed_rule_id = (
            MANIFEST_SEED_SWEEP_ROLLUP_RULE_ID
            if request["recipe_kind"] == "seed_rolled_geometry_sensitive_metric_family"
            else PER_RUN_SINGLE_SEED_RULE_ID
        )
        if seed_rule_id == MANIFEST_SEED_SWEEP_ROLLUP_RULE_ID and seed_rule_id not in seed_rule_ids:
            raise ValueError(
                f"Manifest metric request {request['requested_metric_id']!r} requires a declared manifest seed_sweep."
            )
        records.append(
            {
                "requested_metric_id": request["requested_metric_id"],
                "request_role": request_role,
                "request_order": request_index,
                "recipe_kind": request["recipe_kind"],
                "resolved_metric_ids": list(request["resolved_metric_ids"]),
                "metric_recipe_ids": [
                    recipe_id
                    for metric_id in request["resolved_metric_ids"]
                    for recipe_id in recipe_ids_by_metric.get(metric_id, [])
                ],
                "comparison_group_ids": comparison_group_ids,
                "condition_pair_ids": list(request["required_condition_pair_ids"]),
                "seed_aggregation_rule_id": seed_rule_id,
            }
        )
    return records


def _build_per_run_analysis_output_targets(
    arm_plans: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for arm_plan in arm_plans:
        arm_reference = _require_mapping(
            arm_plan.get("arm_reference"),
            field_name="arm_plan.arm_reference",
        )
        bundle_metadata = _require_mapping(
            _require_mapping(
                arm_plan.get("result_bundle"),
                field_name="arm_plan.result_bundle",
            ).get("metadata"),
            field_name="arm_plan.result_bundle.metadata",
        )
        artifacts = _require_mapping(
            bundle_metadata.get("artifacts"),
            field_name="arm_plan.result_bundle.metadata.artifacts",
        )
        artifact_ids = ("metadata_json", "state_summary", "readout_traces", "metrics_table")
        records.append(
            {
                "arm_id": str(arm_reference["arm_id"]),
                "model_mode": str(arm_reference["model_mode"]),
                "bundle_id": str(bundle_metadata["bundle_id"]),
                "artifact_targets": [
                    {
                        "artifact_id": artifact_id,
                        "path": str(_require_mapping(artifacts[artifact_id], field_name=f"artifacts.{artifact_id}")["path"]),
                        "status": str(_require_mapping(artifacts[artifact_id], field_name=f"artifacts.{artifact_id}")["status"]),
                        "artifact_scope": str(_require_mapping(artifacts[artifact_id], field_name=f"artifacts.{artifact_id}")["artifact_scope"]),
                    }
                    for artifact_id in artifact_ids
                ],
            }
        )
    return records


def _normalize_manifest_metric_request(
    requested_metric_id: Any,
    *,
    field_name: str,
    analysis_contract: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_metric_id = _normalize_identifier(
        requested_metric_id,
        field_name=field_name,
    )
    recipe = MANIFEST_TASK_METRIC_RECIPES.get(normalized_metric_id)
    if recipe is not None:
        return {
            "requested_metric_id": normalized_metric_id,
            "recipe_kind": str(recipe["recipe_kind"]),
            "resolved_metric_ids": [str(item) for item in recipe["resolved_metric_ids"]],
            "required_condition_pair_ids": [
                str(item) for item in recipe["required_condition_pair_ids"]
            ],
            "comparison_group_kinds": [str(item) for item in recipe["comparison_group_kinds"]],
        }
    try:
        metric_definition = get_readout_analysis_metric_definition(
            normalized_metric_id,
            record=analysis_contract,
        )
    except ValueError as exc:
        raise ValueError(
            f"Manifest requested unsupported analysis metric id {normalized_metric_id!r}."
        ) from exc
    return {
        "requested_metric_id": normalized_metric_id,
        "recipe_kind": "contract_metric",
        "resolved_metric_ids": [normalized_metric_id],
        "required_condition_pair_ids": _required_condition_pair_ids_for_metric(metric_definition),
        "comparison_group_kinds": ["matched_surface_wave_vs_baseline"],
    }


def _required_condition_pair_ids_for_metric(
    metric_definition: Mapping[str, Any],
) -> list[str]:
    metric_id = str(metric_definition["metric_id"])
    if metric_id in {
        "direction_selectivity_index",
        "motion_vector_heading_deg",
        "motion_vector_speed_deg_per_s",
        "null_direction_suppression_index",
        "optic_flow_heading_deg",
        "optic_flow_speed_deg_per_s",
    }:
        return [PREFERRED_VS_NULL_PAIR_ID]
    if metric_id == "on_off_selectivity_index":
        return [ON_VS_OFF_PAIR_ID]
    return []


def _required_condition_pair_ids_for_null_test(null_test_id: str) -> list[str]:
    if null_test_id == "direction_label_swap":
        return [PREFERRED_VS_NULL_PAIR_ID]
    if null_test_id == "polarity_label_swap":
        return [ON_VS_OFF_PAIR_ID]
    return []


def _required_comparison_group_ids_for_null_test(
    null_test_id: str,
    available_group_ids_by_kind: Mapping[str, Sequence[str]],
) -> list[str]:
    if null_test_id == "geometry_shuffle_collapse":
        group_ids = list(available_group_ids_by_kind.get("geometry_ablation", []))
        if not group_ids:
            raise ValueError(
                "Readout-analysis null test 'geometry_shuffle_collapse' requires a geometry-ablation comparison group."
            )
        return group_ids
    if null_test_id == "stronger_baseline_survival":
        group_ids = list(available_group_ids_by_kind.get("baseline_strength_challenge", []))
        if not group_ids:
            raise ValueError(
                "Readout-analysis null test 'stronger_baseline_survival' requires a baseline-strength challenge comparison group."
            )
        return group_ids
    if null_test_id == "seed_stability":
        return list(available_group_ids_by_kind.get("geometry_ablation", []))
    return []


def _analysis_window_id_for_scope(scope_rule: str) -> str:
    if scope_rule in {
        PER_SHARED_READOUT_CONDITION_PAIR_SCOPE,
        PER_SHARED_READOUT_CONDITION_WINDOW_SCOPE,
    }:
        return SHARED_RESPONSE_WINDOW_ID
    if scope_rule == PER_TASK_DECODER_WINDOW_SCOPE:
        return TASK_DECODER_WINDOW_ID
    if scope_rule in {
        PER_WAVE_ROOT_SET_WINDOW_SCOPE,
        PER_WAVE_ROOT_WINDOW_SCOPE,
    }:
        return WAVE_DIAGNOSTIC_WINDOW_ID
    return FULL_TIMEBASE_WINDOW_ID


def _build_metric_recipe_id(
    metric_id: str,
    *,
    readout_id: str,
    window_id: str,
    suffix: str,
) -> str:
    return f"{metric_id}__{readout_id}__{window_id}__{suffix}"


def _eligible_wave_root_ids(arm_plans: Sequence[Mapping[str, Any]]) -> list[int]:
    root_ids: set[int] = set()
    for arm_plan in arm_plans:
        arm_reference = _require_mapping(
            arm_plan.get("arm_reference"),
            field_name="arm_plan.arm_reference",
        )
        if str(arm_reference["model_mode"]) != SURFACE_WAVE_MODEL_MODE:
            continue
        model_configuration = _require_mapping(
            arm_plan.get("model_configuration"),
            field_name="arm_plan.model_configuration",
        )
        execution_plan = model_configuration.get("surface_wave_execution_plan")
        if not isinstance(execution_plan, Mapping):
            continue
        for item in execution_plan.get("selected_root_operator_assets", []):
            if not isinstance(item, Mapping):
                continue
            root_ids.add(int(item["root_id"]))
    return sorted(root_ids)


def _manifest_only_output_required_metric_ids(output_id: str) -> list[str]:
    if output_id == "baseline_challenge_comparison":
        return [
            "null_direction_suppression_index",
            "response_latency_to_peak_ms",
        ]
    if output_id == "topology_ablation_comparison":
        return [
            "direction_selectivity_index",
            "null_direction_suppression_index",
            "response_latency_to_peak_ms",
        ]
    if output_id == "shared_output_trace_overlay":
        return ["null_direction_suppression_index"]
    return []


def _topology_sort_key(value: str) -> tuple[int, str]:
    if value == "intact":
        return (0, value)
    if value == "shuffled":
        return (1, value)
    return (2, value)


def discover_simulation_run_plans(
    plan: Mapping[str, Any],
    *,
    arm_id: str | None = None,
    model_mode: str | None = None,
    baseline_family: str | None = None,
    topology_condition: str | None = None,
    use_manifest_seed_sweep: bool = False,
) -> list[dict[str, Any]]:
    arm_plans = _extract_arm_plans(plan)
    requested_arm_id = (
        _normalize_identifier(arm_id, field_name="arm_id")
        if arm_id is not None
        else None
    )
    requested_model_mode = (
        _normalize_identifier(model_mode, field_name="model_mode")
        if model_mode is not None
        else None
    )
    requested_baseline_family = (
        _normalize_identifier(baseline_family, field_name="baseline_family")
        if baseline_family is not None
        else None
    )
    requested_topology_condition = (
        _normalize_identifier(topology_condition, field_name="topology_condition")
        if topology_condition is not None
        else None
    )

    filtered = []
    for arm_plan in arm_plans:
        arm_reference = arm_plan["arm_reference"]
        if requested_arm_id is not None and arm_reference["arm_id"] != requested_arm_id:
            continue
        if requested_model_mode is not None and arm_reference["model_mode"] != requested_model_mode:
            continue
        if requested_baseline_family is not None and (
            arm_reference["baseline_family"] != requested_baseline_family
        ):
            continue
        if requested_topology_condition is not None and (
            arm_plan["topology_condition"] != requested_topology_condition
        ):
            continue
        filtered.append(copy.deepcopy(arm_plan))

    if not use_manifest_seed_sweep:
        return filtered

    seed_sweep = _extract_seed_sweep(plan)
    if not seed_sweep:
        return filtered

    expanded: list[dict[str, Any]] = []
    for arm_plan in filtered:
        for seed in seed_sweep:
            expanded.append(_expand_arm_plan_for_seed(arm_plan, seed))
    return expanded


def resolve_simulation_arm_plan(plan: Mapping[str, Any], arm_id: str) -> dict[str, Any]:
    requested_arm_id = _normalize_identifier(arm_id, field_name="arm_id")
    matches = discover_simulation_run_plans(plan, arm_id=requested_arm_id)
    if not matches:
        raise ValueError(f"Simulation plan does not contain arm_id {requested_arm_id!r}.")
    return matches[0]


def resolve_manifest_mixed_fidelity_plan(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    arm_id: str,
    simulation_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    arm_plan = resolve_simulation_arm_plan(
        (
            _require_mapping(simulation_plan, field_name="simulation_plan")
            if simulation_plan is not None
            else resolve_manifest_simulation_plan(
                manifest_path=manifest_path,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )
        ),
        arm_id=arm_id,
    )
    arm_reference = _require_mapping(
        arm_plan.get("arm_reference"),
        field_name="arm_plan.arm_reference",
    )
    if str(arm_reference["model_mode"]) != SURFACE_WAVE_MODEL_MODE:
        raise ValueError(
            "Mixed-fidelity planning only applies to surface_wave arms, got "
            f"{arm_reference['model_mode']!r} for arm {arm_reference['arm_id']!r}."
        )
    model_configuration = _require_mapping(
        arm_plan.get("model_configuration"),
        field_name="arm_plan.model_configuration",
    )
    execution_plan = _require_mapping(
        model_configuration.get("surface_wave_execution_plan"),
        field_name="arm_plan.model_configuration.surface_wave_execution_plan",
    )
    return copy.deepcopy(
        _require_mapping(
            execution_plan.get("mixed_fidelity"),
            field_name="surface_wave_execution_plan.mixed_fidelity",
        )
    )


def _normalize_runtime_timebase(
    payload: Mapping[str, Any] | None,
    *,
    default_timebase: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(default_timebase)
    if payload is not None:
        if not isinstance(payload, Mapping):
            raise ValueError("simulation.timebase must be a mapping when provided.")
        merged.update(dict(payload))
    return normalize_simulator_timebase(merged)


def _normalize_input_config(
    payload: Mapping[str, Any] | None,
    *,
    project_root: Path,
) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    unknown_keys = sorted(set(raw_payload) - ALLOWED_INPUT_CONFIG_KEYS)
    if unknown_keys:
        raise ValueError(
            "simulation.input contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    source_kind = _normalize_nonempty_string(
        raw_payload.get("source_kind", STIMULUS_BUNDLE_INPUT_SOURCE),
        field_name="simulation.input.source_kind",
    )
    if source_kind not in SUPPORTED_INPUT_SOURCE_KINDS:
        raise ValueError(
            "simulation.input.source_kind must be one of "
            f"{list(SUPPORTED_INPUT_SOURCE_KINDS)!r}, got {source_kind!r}."
        )
    require_recorded_bundle = _normalize_bool(
        raw_payload.get(
            "require_recorded_bundle",
            DEFAULT_REQUIRE_RECORDED_INPUT_BUNDLE,
        ),
        field_name="simulation.input.require_recorded_bundle",
    )
    retinal_config_path = raw_payload.get("retinal_config_path")
    if retinal_config_path is not None:
        retinal_config_path = str(_resolve_project_path(retinal_config_path, project_root))

    if source_kind == STIMULUS_BUNDLE_INPUT_SOURCE and retinal_config_path is not None:
        raise ValueError(
            "simulation.input.retinal_config_path may only be set when "
            "simulation.input.source_kind is 'retinal_bundle'."
        )
    if source_kind == RETINAL_BUNDLE_INPUT_SOURCE and retinal_config_path is None:
        raise ValueError(
            "simulation.input.retinal_config_path is required when "
            "simulation.input.source_kind is 'retinal_bundle'."
        )
    if source_kind == RETINAL_BUNDLE_INPUT_SOURCE and not require_recorded_bundle:
        raise ValueError(
            "simulation.input.require_recorded_bundle must be true for "
            "'retinal_bundle' input planning."
        )

    return {
        "source_kind": source_kind,
        "require_recorded_bundle": require_recorded_bundle,
        "retinal_config_path": retinal_config_path,
    }


def _normalize_mixed_fidelity_config(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    unknown_keys = sorted(set(raw_payload) - ALLOWED_MIXED_FIDELITY_CONFIG_KEYS)
    if unknown_keys:
        raise ValueError(
            "simulation.mixed_fidelity contains unsupported keys: "
            f"{unknown_keys!r}."
        )

    version = _normalize_nonempty_string(
        raw_payload.get("version", MIXED_FIDELITY_CONFIG_VERSION),
        field_name="simulation.mixed_fidelity.version",
    )
    if version != MIXED_FIDELITY_CONFIG_VERSION:
        raise ValueError(
            "simulation.mixed_fidelity.version must be "
            f"{MIXED_FIDELITY_CONFIG_VERSION!r}."
        )

    assignment_policy_payload = raw_payload.get("assignment_policy")
    if assignment_policy_payload is None:
        assignment_policy_payload = {}
    if not isinstance(assignment_policy_payload, Mapping):
        raise ValueError(
            "simulation.mixed_fidelity.assignment_policy must be a mapping when "
            "provided."
        )
    assignment_policy = normalize_mixed_fidelity_assignment_policy(
        assignment_policy_payload
    )

    return {
        "version": version,
        "assignment_ordering": DEFAULT_MIXED_FIDELITY_ASSIGNMENT_ORDERING,
        "assignment_policy": assignment_policy,
    }


def _normalize_runtime_determinism(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    unknown_keys = sorted(set(raw_payload) - ALLOWED_DETERMINISM_CONFIG_KEYS)
    if unknown_keys:
        raise ValueError(
            "simulation.determinism contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    return {
        "rng_family": _normalize_nonempty_string(
            raw_payload.get("rng_family", DEFAULT_RNG_FAMILY),
            field_name="simulation.determinism.rng_family",
        ),
        "seed_scope": _normalize_nonempty_string(
            raw_payload.get("seed_scope", DEFAULT_SEED_SCOPE),
            field_name="simulation.determinism.seed_scope",
        ),
    }


def _normalize_readout_catalog(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        normalized = default_shared_readout_catalog()
    else:
        if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
            raise ValueError("simulation.readout_catalog must be a list when provided.")
        normalized = [
            parse_simulator_readout_definition(item)
            for item in payload
        ]
    sorted_catalog = sorted(
        normalized,
        key=lambda item: (
            item["readout_id"],
            item["scope"],
            item["aggregation"],
        ),
    )
    seen_ids: set[str] = set()
    for readout in sorted_catalog:
        readout_id = str(readout["readout_id"])
        if readout_id in seen_ids:
            raise ValueError(
                f"simulation.readout_catalog contains duplicate readout_id {readout_id!r}."
            )
        seen_ids.add(readout_id)
    return sorted_catalog


def _normalize_shared_readout_catalog(
    readout_catalog: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    shared_readouts = [
        copy.deepcopy(dict(readout))
        for readout in readout_catalog
        if str(readout.get("value_semantics")) == SHARED_READOUT_VALUE_SEMANTICS
    ]
    if not shared_readouts:
        raise ValueError(
            "simulation.readout_catalog must contain at least one shared readout with "
            f"value_semantics {SHARED_READOUT_VALUE_SEMANTICS!r}."
        )
    return shared_readouts


def _normalize_baseline_family_configs(payload: Any) -> dict[str, dict[str, Any]]:
    defaults = default_baseline_family_configs()
    raw_payload = dict(payload or {})
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError("simulation.baseline_families must be a mapping when provided.")
    unknown_keys = sorted(set(raw_payload) - {P0_BASELINE_FAMILY, P1_BASELINE_FAMILY})
    if unknown_keys:
        raise ValueError(
            "simulation.baseline_families contains unsupported families: "
            f"{unknown_keys!r}."
        )

    normalized = copy.deepcopy(defaults)
    normalized[P0_BASELINE_FAMILY] = _normalize_p0_config(raw_payload.get(P0_BASELINE_FAMILY))
    normalized[P1_BASELINE_FAMILY] = _normalize_p1_config(raw_payload.get(P1_BASELINE_FAMILY))
    return normalized


def _normalize_p0_config(payload: Any) -> dict[str, Any]:
    defaults = default_baseline_family_configs()[P0_BASELINE_FAMILY]
    parameters = copy.deepcopy(defaults["parameters"])
    raw_payload = dict(payload or {})
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError("simulation.baseline_families.P0 must be a mapping when provided.")
    unknown_keys = sorted(set(raw_payload) - _P0_ALLOWED_KEYS)
    if unknown_keys:
        raise ValueError(
            "simulation.baseline_families.P0 contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    if "membrane_time_constant_ms" in raw_payload:
        parameters["membrane_time_constant_ms"] = _normalize_positive_float(
            raw_payload["membrane_time_constant_ms"],
            field_name="simulation.baseline_families.P0.membrane_time_constant_ms",
        )
    if "resting_potential" in raw_payload:
        parameters["resting_potential"] = _normalize_float(
            raw_payload["resting_potential"],
            field_name="simulation.baseline_families.P0.resting_potential",
        )
    if "input_gain" in raw_payload:
        parameters["input_gain"] = _normalize_float(
            raw_payload["input_gain"],
            field_name="simulation.baseline_families.P0.input_gain",
        )
    if "recurrent_gain" in raw_payload:
        parameters["recurrent_gain"] = _normalize_float(
            raw_payload["recurrent_gain"],
            field_name="simulation.baseline_families.P0.recurrent_gain",
        )
    normalized = copy.deepcopy(defaults)
    normalized["parameters"] = parameters
    return normalized


def _normalize_p1_config(payload: Any) -> dict[str, Any]:
    defaults = default_baseline_family_configs()[P1_BASELINE_FAMILY]
    parameters = copy.deepcopy(defaults["parameters"])
    raw_payload = dict(payload or {})
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError("simulation.baseline_families.P1 must be a mapping when provided.")
    unknown_keys = sorted(set(raw_payload) - _P1_ALLOWED_KEYS)
    if unknown_keys:
        raise ValueError(
            "simulation.baseline_families.P1 contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    if "membrane_time_constant_ms" in raw_payload:
        parameters["membrane_time_constant_ms"] = _normalize_positive_float(
            raw_payload["membrane_time_constant_ms"],
            field_name="simulation.baseline_families.P1.membrane_time_constant_ms",
        )
    if "synaptic_current_time_constant_ms" in raw_payload:
        parameters["synaptic_current_time_constant_ms"] = _normalize_positive_float(
            raw_payload["synaptic_current_time_constant_ms"],
            field_name="simulation.baseline_families.P1.synaptic_current_time_constant_ms",
        )
    if "resting_potential" in raw_payload:
        parameters["resting_potential"] = _normalize_float(
            raw_payload["resting_potential"],
            field_name="simulation.baseline_families.P1.resting_potential",
        )
    if "input_gain" in raw_payload:
        parameters["input_gain"] = _normalize_float(
            raw_payload["input_gain"],
            field_name="simulation.baseline_families.P1.input_gain",
        )
    if "recurrent_gain" in raw_payload:
        parameters["recurrent_gain"] = _normalize_float(
            raw_payload["recurrent_gain"],
            field_name="simulation.baseline_families.P1.recurrent_gain",
        )
    if "delay_handling" in raw_payload:
        parameters["delay_handling"] = _normalize_p1_delay_handling(
            raw_payload["delay_handling"]
        )
    normalized = copy.deepcopy(defaults)
    normalized["parameters"] = parameters
    return normalized


def _normalize_p1_delay_handling(payload: Any) -> dict[str, Any]:
    defaults = copy.deepcopy(
        default_baseline_family_configs()[P1_BASELINE_FAMILY]["parameters"]["delay_handling"]
    )
    if not isinstance(payload, Mapping):
        raise ValueError(
            "simulation.baseline_families.P1.delay_handling must be a mapping when provided."
        )
    raw_payload = dict(payload)
    unknown_keys = sorted(set(raw_payload) - _P1_DELAY_ALLOWED_KEYS)
    if unknown_keys:
        raise ValueError(
            "simulation.baseline_families.P1.delay_handling contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    if "mode" in raw_payload:
        defaults["mode"] = _normalize_identifier(
            raw_payload["mode"],
            field_name="simulation.baseline_families.P1.delay_handling.mode",
        )
    if "max_supported_delay_steps" in raw_payload:
        defaults["max_supported_delay_steps"] = _normalize_positive_int(
            raw_payload["max_supported_delay_steps"],
            field_name="simulation.baseline_families.P1.delay_handling.max_supported_delay_steps",
        )
    return defaults


def _normalize_arm_fidelity_assignment(
    payload: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    if payload is None:
        return {
            "default_morphology_class": None,
            "root_overrides": [],
            "root_overrides_by_root": {},
        }
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping when provided.")

    raw_payload = dict(payload)
    unknown_keys = sorted(set(raw_payload) - ALLOWED_ARM_FIDELITY_ASSIGNMENT_KEYS)
    if unknown_keys:
        raise ValueError(
            f"{field_name} contains unsupported keys: {unknown_keys!r}."
        )

    default_morphology_class = None
    if raw_payload.get("default_morphology_class") is not None:
        default_morphology_class = normalize_hybrid_morphology_class(
            raw_payload["default_morphology_class"],
            field_name=f"{field_name}.default_morphology_class",
        )

    root_overrides_payload = raw_payload.get("root_overrides", ())
    if root_overrides_payload is None:
        root_overrides_payload = ()
    root_overrides: list[dict[str, Any]] = []
    root_overrides_by_root: dict[int, str] = {}
    for index, item in enumerate(
        _require_sequence(
            root_overrides_payload,
            field_name=f"{field_name}.root_overrides",
        )
    ):
        override = _require_mapping(
            item,
            field_name=f"{field_name}.root_overrides[{index}]",
        )
        override_unknown_keys = sorted(
            set(override) - ALLOWED_ARM_FIDELITY_OVERRIDE_KEYS
        )
        if override_unknown_keys:
            raise ValueError(
                f"{field_name}.root_overrides[{index}] contains unsupported keys: "
                f"{override_unknown_keys!r}."
            )
        if "root_id" not in override:
            raise ValueError(
                f"{field_name}.root_overrides[{index}] requires root_id."
            )
        if "morphology_class" not in override:
            raise ValueError(
                f"{field_name}.root_overrides[{index}] requires morphology_class."
            )
        root_id = int(override["root_id"])
        if root_id in root_overrides_by_root:
            raise ValueError(
                f"{field_name}.root_overrides contains duplicate root_id {root_id}."
            )
        morphology_class = normalize_hybrid_morphology_class(
            override["morphology_class"],
            field_name=f"{field_name}.root_overrides[{index}].morphology_class",
        )
        root_overrides_by_root[root_id] = morphology_class
        root_overrides.append(
            {
                "root_id": root_id,
                "morphology_class": morphology_class,
            }
        )
    root_overrides.sort(key=lambda item: int(item["root_id"]))
    return {
        "default_morphology_class": default_morphology_class,
        "root_overrides": root_overrides,
        "root_overrides_by_root": root_overrides_by_root,
    }


def _resolve_selection_reference(
    *,
    manifest: Mapping[str, Any],
    cfg: Mapping[str, Any],
) -> dict[str, Any]:
    selected_root_ids_path = Path(cfg["paths"]["selected_root_ids"]).resolve()
    if not selected_root_ids_path.exists():
        raise ValueError(
            f"Selected-root roster is missing at {selected_root_ids_path}."
        )
    root_ids = read_selected_root_roster(
        selected_root_ids_path,
        require_nonempty=True,
        require_unique=True,
        field_name=f"Selected-root roster at {selected_root_ids_path}",
    )
    normalized_root_ids = sorted(int(root_id) for root_id in root_ids)

    subset_name = manifest.get("subset_name")
    circuit_name = manifest.get("circuit_name")
    selection_cfg = dict(cfg.get("selection", {}))
    active_preset = selection_cfg.get("active_preset")
    if subset_name is not None and active_preset is not None:
        normalized_subset_name = _normalize_identifier(
            subset_name,
            field_name="manifest.subset_name",
        )
        normalized_active_preset = _normalize_identifier(
            active_preset,
            field_name="config.selection.active_preset",
        )
        if normalized_subset_name != normalized_active_preset:
            raise ValueError(
                "Manifest subset_name and config selection.active_preset disagree: "
                f"{normalized_subset_name!r} != {normalized_active_preset!r}."
            )

    subset_manifest_reference = _resolve_subset_manifest_reference(
        subset_name=subset_name,
        subset_output_dir=Path(cfg["paths"]["subset_output_dir"]).resolve(),
        expected_root_ids=normalized_root_ids,
    )
    root_id_roster_hash = _stable_hash(normalized_root_ids)

    return {
        "identity_kind": "subset" if subset_name is not None else "circuit",
        "subset_name": (
            _normalize_identifier(subset_name, field_name="manifest.subset_name")
            if subset_name is not None
            else None
        ),
        "circuit_name": (
            _normalize_identifier(circuit_name, field_name="manifest.circuit_name")
            if circuit_name is not None
            else None
        ),
        "selection_preset": (
            _normalize_identifier(active_preset, field_name="config.selection.active_preset")
            if active_preset is not None
            else None
        ),
        "selected_root_ids_path": str(selected_root_ids_path),
        "selected_root_ids": normalized_root_ids,
        "selected_root_count": len(normalized_root_ids),
        "selected_root_ids_hash": root_id_roster_hash,
        "subset_manifest_reference": subset_manifest_reference,
    }


def _resolve_subset_manifest_reference(
    *,
    subset_name: Any,
    subset_output_dir: Path,
    expected_root_ids: list[int],
) -> dict[str, Any] | None:
    if subset_name is None:
        return None
    subset_artifact_paths = build_subset_artifact_paths(
        subset_output_dir,
        str(subset_name),
    )
    subset_manifest_path = subset_artifact_paths.manifest_json.resolve()
    if not subset_manifest_path.exists():
        return None
    subset_manifest = load_subset_manifest(subset_manifest_path)
    manifest_validation = validate_subset_manifest_payload(
        subset_manifest,
        preset_name=str(subset_name),
        expected_root_ids=expected_root_ids,
        field_name=f"Subset manifest at {subset_manifest_path}",
    )
    return {
        "subset_manifest_path": str(subset_manifest_path),
        "subset_manifest_version": manifest_validation["subset_manifest_version"],
        "root_id_count": manifest_validation["root_id_count"],
    }


def _resolve_input_reference(
    *,
    manifest_path: Path,
    manifest_payload: Mapping[str, Any],
    manifest_summary: Mapping[str, Any],
    runtime_config: Mapping[str, Any],
    schema_path: Path,
    design_lock_path: Path,
    processed_stimulus_dir: Path,
    processed_retinal_dir: Path,
) -> dict[str, Any]:
    source_kind = str(runtime_config["input"]["source_kind"])
    require_recorded_bundle = bool(runtime_config["input"]["require_recorded_bundle"])
    stimulus_metadata_path = Path(
        str(manifest_summary["stimulus_bundle_metadata_path"])
    ).resolve()
    stimulus_bundle_exists = stimulus_metadata_path.exists()
    predicted_stimulus_reference = build_stimulus_bundle_reference(
        manifest_summary["stimulus_bundle"]
    )
    recorded_stimulus_reference = None
    if stimulus_bundle_exists:
        recorded_stimulus_reference = build_stimulus_bundle_reference(
            load_stimulus_bundle_metadata(stimulus_metadata_path)
        )
        if recorded_stimulus_reference != predicted_stimulus_reference:
            raise ValueError(
                "Recorded stimulus bundle metadata does not match the manifest-resolved "
                f"bundle reference at {stimulus_metadata_path}."
            )

    input_reference: dict[str, Any] = {
        "source_kind": source_kind,
        "require_recorded_bundle": require_recorded_bundle,
        "stimulus_bundle_reference": (
            recorded_stimulus_reference
            if recorded_stimulus_reference is not None
            else predicted_stimulus_reference
        ),
        "stimulus_bundle_metadata_path": str(stimulus_metadata_path),
        "stimulus_bundle_metadata_exists": stimulus_bundle_exists,
    }

    if source_kind == STIMULUS_BUNDLE_INPUT_SOURCE:
        if require_recorded_bundle and not stimulus_bundle_exists:
            raise ValueError(
                "simulation.input.source_kind='stimulus_bundle' requires a recorded local "
                f"bundle, but {stimulus_metadata_path} does not exist."
            )
        selected_reference = (
            recorded_stimulus_reference
            if recorded_stimulus_reference is not None
            else predicted_stimulus_reference
        )
        input_reference.update(
            {
                "selected_input_kind": STIMULUS_BUNDLE_INPUT_SOURCE,
                "selected_input_reference": copy.deepcopy(selected_reference),
                "selected_input_metadata_path": str(stimulus_metadata_path),
                "selected_input_metadata_exists": stimulus_bundle_exists,
                "resolution_source": (
                    "recorded_local_bundle"
                    if stimulus_bundle_exists
                    else "predicted_manifest_bundle"
                ),
            }
        )
        return input_reference

    retinal_config_path = runtime_config["input"]["retinal_config_path"]
    assert retinal_config_path is not None
    resolved_retinal_input = resolve_retinal_bundle_input(
        manifest_path=manifest_path,
        retinal_config_path=retinal_config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        processed_stimulus_dir=processed_stimulus_dir,
        processed_retinal_dir=processed_retinal_dir,
    )
    retinal_metadata_path = resolved_retinal_input.retinal_bundle_metadata_path.resolve()
    if not retinal_metadata_path.exists():
        raise ValueError(
            "simulation.input.source_kind='retinal_bundle' requires a recorded local "
            f"bundle, but {retinal_metadata_path} does not exist."
        )
    retinal_bundle_reference = build_retinal_bundle_reference(
        load_retinal_bundle_metadata(retinal_metadata_path)
    )
    input_reference.update(
        {
            "retinal_bundle_reference": retinal_bundle_reference,
            "retinal_bundle_metadata_path": str(retinal_metadata_path),
            "retinal_bundle_metadata_exists": True,
            "retinal_config_path": str(Path(retinal_config_path).resolve()),
            "selected_input_kind": RETINAL_BUNDLE_INPUT_SOURCE,
            "selected_input_reference": copy.deepcopy(retinal_bundle_reference),
            "selected_input_metadata_path": str(retinal_metadata_path),
            "selected_input_metadata_exists": True,
            "resolution_source": "recorded_local_bundle",
            "source_lineage": copy.deepcopy(resolved_retinal_input.source_lineage),
        }
    )
    return input_reference


def _resolve_circuit_assets(
    *,
    manifest: Mapping[str, Any],
    cfg: Mapping[str, Any],
    selection_reference: Mapping[str, Any],
) -> dict[str, Any]:
    geometry_manifest_path = Path(cfg["paths"]["manifest_json"]).resolve()
    if not geometry_manifest_path.exists():
        raise ValueError(f"Geometry manifest is missing at {geometry_manifest_path}.")
    geometry_manifest_payload = load_geometry_manifest(geometry_manifest_path)
    geometry_manifest_records = load_geometry_manifest_records(geometry_manifest_path)
    if not geometry_manifest_records:
        raise ValueError(
            f"Geometry manifest at {geometry_manifest_path} does not contain any root records."
        )

    selected_root_ids = [int(root_id) for root_id in selection_reference["selected_root_ids"]]
    missing_roots = [
        root_id
        for root_id in selected_root_ids
        if str(root_id) not in geometry_manifest_records
    ]
    if missing_roots:
        raise ValueError(
            "Geometry manifest is missing selected roots required by the manifest plan: "
            f"{missing_roots!r}."
        )

    coupling_contract = geometry_manifest_payload.get("_coupling_contract")
    if not isinstance(coupling_contract, Mapping):
        raise ValueError(
            f"Geometry manifest at {geometry_manifest_path} is missing _coupling_contract metadata."
        )
    local_synapse_registry = coupling_contract.get("local_synapse_registry")
    if not isinstance(local_synapse_registry, Mapping):
        raise ValueError(
            f"Geometry manifest at {geometry_manifest_path} is missing coupling local_synapse_registry metadata."
        )
    local_synapse_registry_path = Path(
        _normalize_nonempty_string(
            local_synapse_registry.get("path"),
            field_name="_coupling_contract.local_synapse_registry.path",
        )
    ).resolve()
    local_synapse_registry_status = _normalize_nonempty_string(
        local_synapse_registry.get("status"),
        field_name="_coupling_contract.local_synapse_registry.status",
    )
    if local_synapse_registry_status != ASSET_STATUS_READY:
        raise ValueError(
            "Geometry manifest coupling local_synapse_registry is not ready: "
            f"{local_synapse_registry_status!r}."
        )
    if not local_synapse_registry_path.exists():
        raise ValueError(
            "Geometry manifest coupling local_synapse_registry path does not exist: "
            f"{local_synapse_registry_path}."
        )

    per_root_assets = []
    selected_root_set = set(selected_root_ids)
    for root_id in selected_root_ids:
        record = geometry_manifest_records[str(root_id)]
        geometry_asset_records = {
            asset_key: _asset_record_reference(
                _require_mapping(
                    _require_mapping(
                        record.get("assets"),
                        field_name=f"geometry_manifest[{root_id}].assets",
                    ).get(asset_key),
                    field_name=f"geometry_manifest[{root_id}].assets.{asset_key}",
                ),
                field_name=f"geometry_manifest[{root_id}].assets.{asset_key}",
            )
            for asset_key in (
                RAW_MESH_KEY,
                RAW_SKELETON_KEY,
                SIMPLIFIED_MESH_KEY,
                SURFACE_GRAPH_KEY,
                PATCH_GRAPH_KEY,
                DESCRIPTOR_SIDECAR_KEY,
                QA_SIDECAR_KEY,
            )
        }
        operator_bundle = parse_operator_bundle_metadata(record.get("operator_bundle", {}))
        operator_paths = discover_operator_bundle_paths(record)
        operator_asset_records = {
            asset_key: _asset_record_reference(
                {
                    "path": str(Path(asset_path).resolve()),
                    "status": str(operator_bundle["assets"][asset_key]["status"]),
                },
                field_name=(
                    f"geometry_manifest[{root_id}].operator_bundle.assets.{asset_key}"
                ),
            )
            for asset_key, asset_path in operator_paths.items()
        }
        coupling_bundle = parse_coupling_bundle_metadata(record.get("coupling_bundle", {}))
        if coupling_bundle["status"] != ASSET_STATUS_READY:
            raise ValueError(
                f"Selected root {root_id} has coupling_bundle status "
                f"{coupling_bundle['status']!r}, expected 'ready'."
            )
        bundle_paths = discover_coupling_bundle_paths(record)
        coupling_asset_records = {
            asset_key: _asset_record_reference(
                {
                    "path": str(Path(asset_path).resolve()),
                    "status": str(coupling_bundle["assets"][asset_key]["status"]),
                },
                field_name=(
                    f"geometry_manifest[{root_id}].coupling_bundle.assets.{asset_key}"
                ),
            )
            for asset_key, asset_path in bundle_paths.items()
        }
        missing_required_assets = [
            asset_key
            for asset_key, asset_record in coupling_asset_records.items()
            if not bool(asset_record["exists"])
        ]
        if missing_required_assets:
            raise ValueError(
                f"Selected root {root_id} is missing local coupling assets "
                f"{missing_required_assets!r} under {geometry_manifest_path}."
            )
        edge_bundles = discover_edge_coupling_bundle_paths(record)
        edge_bundle_records = [
            {
                "pre_root_id": int(edge_bundle["pre_root_id"]),
                "post_root_id": int(edge_bundle["post_root_id"]),
                "peer_root_id": int(edge_bundle["peer_root_id"]),
                "relation_to_root": str(edge_bundle["relation_to_root"]),
                "path": str(Path(edge_bundle["path"]).resolve()),
                "status": str(edge_bundle["status"]),
                "exists": Path(edge_bundle["path"]).exists(),
                "selected_peer": int(edge_bundle["peer_root_id"]) in selected_root_set,
            }
            for edge_bundle in edge_bundles
        ]
        missing_edge_paths = [
            str(edge_bundle["path"])
            for edge_bundle in edge_bundle_records
            if str(edge_bundle["status"]) == ASSET_STATUS_READY
            and not bool(edge_bundle["exists"])
        ]
        if missing_edge_paths:
            raise ValueError(
                f"Selected root {root_id} is missing ready edge coupling bundles "
                f"{missing_edge_paths!r}."
            )
        per_root_assets.append(
            {
                "root_id": root_id,
                "cell_type": str(record.get("cell_type", "")),
                "project_role": str(record.get("project_role", "")),
                "geometry_asset_records": geometry_asset_records,
                "operator_bundle_status": str(operator_bundle["status"]),
                "operator_asset_records": operator_asset_records,
                "required_operator_assets": {
                    asset_key: str(operator_asset_records[asset_key]["path"])
                    for asset_key in operator_asset_records
                },
                "descriptor_sidecar_path": str(
                    Path(str(record.get("descriptor_sidecar_path", ""))).resolve()
                ),
                "qa_sidecar_path": str(
                    Path(str(record.get("qa_sidecar_path", ""))).resolve()
                ),
                "coupling_bundle_status": str(coupling_bundle["status"]),
                "coupling_asset_records": coupling_asset_records,
                "required_coupling_assets": {
                    LOCAL_SYNAPSE_REGISTRY_KEY: str(
                        coupling_asset_records[LOCAL_SYNAPSE_REGISTRY_KEY]["path"]
                    ),
                    INCOMING_ANCHOR_MAP_KEY: str(
                        coupling_asset_records[INCOMING_ANCHOR_MAP_KEY]["path"]
                    ),
                    OUTGOING_ANCHOR_MAP_KEY: str(
                        coupling_asset_records[OUTGOING_ANCHOR_MAP_KEY]["path"]
                    ),
                    COUPLING_INDEX_KEY: str(
                        coupling_asset_records[COUPLING_INDEX_KEY]["path"]
                    ),
                },
                "edge_bundle_paths": edge_bundle_records,
                "operator_bundle": operator_bundle,
                "coupling_bundle": coupling_bundle,
            }
        )

    circuit_asset_hash = _stable_hash(
        {
            "geometry_manifest_path": str(geometry_manifest_path),
            "geometry_contract_version": geometry_manifest_payload.get("_asset_contract_version"),
            "coupling_contract_version": geometry_manifest_payload.get("_coupling_contract_version"),
            "coupling_contract": coupling_contract,
            "selected_root_assets": [
                {
                    "root_id": item["root_id"],
                    "cell_type": item["cell_type"],
                    "project_role": item["project_role"],
                    "coupling_bundle": item["coupling_bundle"],
                }
                for item in per_root_assets
            ],
        }
    )
    operator_asset_hash = _stable_hash(
        {
            "geometry_manifest_path": str(geometry_manifest_path),
            "geometry_contract_version": geometry_manifest_payload.get("_asset_contract_version"),
            "operator_contract_version": geometry_manifest_payload.get("_operator_contract_version"),
            "selected_root_assets": [
                {
                    "root_id": item["root_id"],
                    "cell_type": item["cell_type"],
                    "project_role": item["project_role"],
                    "operator_bundle": item["operator_bundle"],
                }
                for item in per_root_assets
            ],
        }
    )
    return {
        "selection_identity_kind": selection_reference["identity_kind"],
        "geometry_manifest_path": str(geometry_manifest_path),
        "geometry_contract_version": str(
            geometry_manifest_payload.get("_asset_contract_version", "")
        ),
        "operator_contract_version": str(
            geometry_manifest_payload.get("_operator_contract_version", "")
        ),
        "coupling_contract_version": str(
            geometry_manifest_payload.get("_coupling_contract_version", "")
        ),
        "local_synapse_registry_path": str(local_synapse_registry_path),
        "local_synapse_registry_status": local_synapse_registry_status,
        "circuit_asset_hash": circuit_asset_hash,
        "operator_asset_hash": operator_asset_hash,
        "selected_root_assets": per_root_assets,
    }


def _resolve_output_targets(
    *,
    output_bundle: Mapping[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    plots = []
    for plot in output_bundle.get("plots", []):
        plots.append(
            {
                "id": _normalize_identifier(plot["id"], field_name="output_bundle.plots.id"),
                "path": str(_resolve_project_path(plot["path"], project_root)),
            }
        )
    ui_states = []
    for state in output_bundle.get("ui_states", []):
        ui_states.append(
            {
                "id": _normalize_identifier(state["id"], field_name="output_bundle.ui_states.id"),
                "path": str(_resolve_project_path(state["path"], project_root)),
            }
        )
    return {
        "metrics_json": str(_resolve_project_path(output_bundle["metrics_json"], project_root)),
        "summary_table_csv": str(
            _resolve_project_path(output_bundle["summary_table_csv"], project_root)
        ),
        "plots": plots,
        "ui_states": ui_states,
    }


def _resolve_arm_seed_handling(
    *,
    arm: Mapping[str, Any],
    arm_index: int,
    manifest_random_seed: int,
    seed_sweep: list[int],
) -> dict[str, Any]:
    arm_seed = arm.get("random_seed")
    if arm_seed is None:
        default_seed = int(manifest_random_seed)
        seed_source = "manifest.random_seed"
    else:
        default_seed = int(arm_seed)
        seed_source = f"comparison_arms[{arm_index}].random_seed"
    return {
        "default_seed": default_seed,
        "default_seed_source": seed_source,
        "manifest_random_seed": int(manifest_random_seed),
        "seed_sweep": list(seed_sweep),
        "seed_sweep_ordering": DEFAULT_SEED_SWEEP_ORDERING,
    }


def _build_model_configuration(
    *,
    arm_reference: Mapping[str, Any],
    arm_payload: Mapping[str, Any],
    runtime_config: Mapping[str, Any],
    circuit_assets: Mapping[str, Any],
    topology_condition: str,
) -> dict[str, Any]:
    model_mode = str(arm_reference["model_mode"])
    baseline_family = arm_reference.get("baseline_family")
    if model_mode == BASELINE_MODEL_MODE:
        assert isinstance(baseline_family, str)
        return {
            "model_mode": model_mode,
            "baseline_family": baseline_family,
            "baseline_parameters": copy.deepcopy(
                runtime_config["baseline_families"][baseline_family]
            ),
        }
    surface_wave_model = copy.deepcopy(runtime_config["surface_wave_model"])
    return {
        "model_mode": model_mode,
        "baseline_family": None,
        "baseline_parameters": None,
        "surface_wave_model": surface_wave_model,
        "surface_wave_reference": build_surface_wave_model_reference(surface_wave_model),
        "surface_wave_execution_plan": _build_surface_wave_execution_plan(
            arm_reference=arm_reference,
            arm_payload=arm_payload,
            point_neuron_model_spec=runtime_config["baseline_families"][P0_BASELINE_FAMILY],
            topology_condition=topology_condition,
            runtime_timebase=runtime_config["timebase"],
            circuit_assets=circuit_assets,
            surface_wave_model=surface_wave_model,
            mixed_fidelity_config=runtime_config["mixed_fidelity"],
        ),
    }


def _build_selected_assets(
    *,
    selection_reference: Mapping[str, Any],
    input_reference: Mapping[str, Any],
    circuit_assets: Mapping[str, Any],
    arm_reference: Mapping[str, Any],
    model_configuration: Mapping[str, Any],
    config_path: Path,
) -> list[dict[str, Any]]:
    selected_input_reference = input_reference["selected_input_reference"]
    selected_input_kind = str(input_reference["selected_input_kind"])
    selected_assets = [
        build_selected_asset_reference(
            asset_role=SELECTED_ROOT_IDS_ASSET_ROLE,
            artifact_type="root_id_roster",
            path=selection_reference["selected_root_ids_path"],
            contract_version=None,
            artifact_id=f"root_id_roster:{selection_reference['selected_root_ids_hash']}",
            bundle_id=None,
        ),
        build_selected_asset_reference(
            asset_role=INPUT_BUNDLE_ASSET_ROLE,
            artifact_type=selected_input_kind,
            path=input_reference["selected_input_metadata_path"],
            contract_version=selected_input_reference["contract_version"],
            artifact_id=selected_input_reference["bundle_id"],
            bundle_id=selected_input_reference["bundle_id"],
        ),
        build_selected_asset_reference(
            asset_role=GEOMETRY_MANIFEST_ASSET_ROLE,
            artifact_type="geometry_bundle_manifest",
            path=circuit_assets["geometry_manifest_path"],
            contract_version=circuit_assets["geometry_contract_version"],
            artifact_id=f"geometry_manifest:{circuit_assets['circuit_asset_hash']}",
            bundle_id=None,
        ),
        build_selected_asset_reference(
            asset_role=COUPLING_REGISTRY_ASSET_ROLE,
            artifact_type="synapse_registry_csv",
            path=circuit_assets["local_synapse_registry_path"],
            contract_version=circuit_assets["coupling_contract_version"],
            artifact_id=f"coupling_synapse_registry:{circuit_assets['circuit_asset_hash']}",
            bundle_id=None,
        ),
        _build_model_configuration_asset_reference(
            arm_reference=arm_reference,
            model_configuration=model_configuration,
            config_path=config_path,
        ),
    ]
    if str(arm_reference["model_mode"]) == SURFACE_WAVE_MODEL_MODE:
        selected_assets.append(
            build_selected_asset_reference(
                asset_role=SURFACE_WAVE_OPERATOR_INVENTORY_ASSET_ROLE,
                artifact_type="surface_wave_operator_inventory",
                path=circuit_assets["geometry_manifest_path"],
                contract_version=circuit_assets["operator_contract_version"],
                artifact_id=(
                    f"surface_wave_operator_inventory:{circuit_assets['operator_asset_hash']}"
                ),
                bundle_id=None,
            )
        )
    return selected_assets


def _build_model_configuration_asset_reference(
    *,
    arm_reference: Mapping[str, Any],
    model_configuration: Mapping[str, Any],
    config_path: Path,
) -> dict[str, Any]:
    model_mode = str(arm_reference["model_mode"])
    if model_mode == BASELINE_MODEL_MODE:
        artifact_type = "baseline_model_configuration"
        artifact_payload = {
            "model_mode": model_mode,
            "baseline_family": arm_reference["baseline_family"],
            "baseline_parameters": model_configuration["baseline_parameters"],
        }
    else:
        artifact_type = "surface_wave_model_configuration"
        surface_wave_execution_plan = _require_mapping(
            model_configuration.get("surface_wave_execution_plan"),
            field_name="model_configuration.surface_wave_execution_plan",
        )
        artifact_payload = {
            "model_mode": model_mode,
            "surface_wave_reference": model_configuration["surface_wave_reference"],
            "surface_wave_model": model_configuration["surface_wave_model"],
            "topology_condition": surface_wave_execution_plan["topology_condition"],
            "resolution": copy.deepcopy(surface_wave_execution_plan["resolution"]),
            "hybrid_morphology": copy.deepcopy(
                surface_wave_execution_plan["hybrid_morphology"]
            ),
            "mixed_fidelity": copy.deepcopy(
                surface_wave_execution_plan["mixed_fidelity"]
            ),
        }
        if isinstance(model_configuration.get("ablation_transform"), Mapping):
            artifact_payload["ablation_transform"] = copy.deepcopy(
                dict(
                    _require_mapping(
                        model_configuration.get("ablation_transform"),
                        field_name="model_configuration.ablation_transform",
                    )
                )
            )
    return build_selected_asset_reference(
        asset_role=MODEL_CONFIGURATION_ASSET_ROLE,
        artifact_type=artifact_type,
        path=config_path,
        contract_version=SIMULATION_RUNTIME_CONFIG_VERSION,
        artifact_id=f"{artifact_type}:{_stable_hash(artifact_payload)}",
        bundle_id=None,
    )


def _build_surface_wave_execution_plan(
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
    mixed_fidelity_resolution = _resolve_surface_wave_mixed_fidelity_plan(
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


def _resolve_surface_wave_mixed_fidelity_plan(
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

        required_local_assets = _build_local_asset_reference_map(
            root_mapping=root_mapping,
            asset_keys=hybrid_record["required_local_assets"],
        )
        optional_local_assets = _build_local_asset_reference_map(
            root_mapping=root_mapping,
            asset_keys=hybrid_record["optional_local_assets"],
        )
        _validate_required_local_assets(
            arm_id=arm_id,
            root_id=root_id,
            morphology_class=morphology_class,
            asset_references=required_local_assets,
        )

        operator_asset = None
        skeleton_runtime_asset = None
        if morphology_class == SURFACE_NEURON_CLASS:
            operator_asset = _resolve_surface_wave_operator_asset(
                arm_id=arm_id,
                root_mapping=root_mapping,
                anisotropy_mode=anisotropy_mode,
                branching_mode=branching_mode,
                hybrid_morphology=hybrid_record,
            )
            coupling_asset = _resolve_surface_wave_coupling_asset(
                arm_id=arm_id,
                root_mapping=root_mapping,
                hybrid_morphology=hybrid_record,
            )
            surface_operator_assets.append(copy.deepcopy(operator_asset))
            surface_coupling_assets.append(copy.deepcopy(coupling_asset))
            realized_anchor_mode = SURFACE_PATCH_CLOUD_MODE
        elif morphology_class == SKELETON_NEURON_CLASS:
            coupling_asset = _resolve_skeleton_neuron_coupling_asset(
                arm_id=arm_id,
                root_mapping=root_mapping,
                hybrid_morphology=hybrid_record,
            )
            skeleton_runtime_asset = _resolve_skeleton_runtime_asset(
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
            coupling_asset = _resolve_point_neuron_coupling_asset(
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
            descriptor_payload=_load_mixed_fidelity_descriptor_payload(root_mapping),
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
                "assignment_provenance": _build_assignment_provenance(
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
                "approximation_route": _build_approximation_route(
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


def _load_mixed_fidelity_descriptor_payload(
    root_mapping: Mapping[str, Any],
) -> dict[str, Any] | None:
    descriptor_sidecar_path = root_mapping.get("descriptor_sidecar_path")
    if descriptor_sidecar_path is None:
        return None
    descriptor_path = Path(str(descriptor_sidecar_path)).resolve()
    if not descriptor_path.exists():
        return None
    descriptor_payload = load_json(descriptor_path)
    return copy.deepcopy(descriptor_payload)


def _build_assignment_provenance(
    *,
    registry_default_morphology_class: str,
    arm_default_morphology_class: str | None,
    arm_root_override_morphology_class: str | None,
    assignment_policy: Mapping[str, Any],
    policy_evaluation: Mapping[str, Any],
    resolved_from: str,
) -> dict[str, Any]:
    return {
        "default_source": str(assignment_policy["default_source"]),
        "registry_default_morphology_class": registry_default_morphology_class,
        "arm_default_morphology_class": arm_default_morphology_class,
        "arm_root_override_morphology_class": arm_root_override_morphology_class,
        "promotion_mode": str(assignment_policy["promotion_mode"]),
        "demotion_mode": str(assignment_policy["demotion_mode"]),
        "policy_applied": False,
        "policy_evaluated": True,
        "policy_recommended_morphology_class": str(
            policy_evaluation["recommended_morphology_class"]
        ),
        "policy_recommendation_relation": str(
            policy_evaluation["recommended_relation_to_realized"]
        ),
        "resolved_from": resolved_from,
    }


def _build_approximation_route(
    *,
    registry_default_morphology_class: str,
    realized_morphology_class: str,
    policy_evaluation: Mapping[str, Any],
) -> dict[str, Any]:
    rank_delta = (
        _morphology_class_rank(realized_morphology_class)
        - _morphology_class_rank(registry_default_morphology_class)
    )
    if rank_delta == 0:
        relation = "same_as_registry_default"
    elif rank_delta > 0:
        relation = "promoted_from_registry_default"
    else:
        relation = "demoted_from_registry_default"
    return {
        "route_id": (
            f"{registry_default_morphology_class}_to_"
            f"{realized_morphology_class}"
        ),
        "registry_default_morphology_class": registry_default_morphology_class,
        "realized_morphology_class": realized_morphology_class,
        "relation_to_registry_default": relation,
        "promotion_rank_delta": rank_delta,
        "policy_action": str(policy_evaluation["recommended_relation_to_realized"]),
        "policy_recommended_morphology_class": str(
            policy_evaluation["recommended_morphology_class"]
        ),
    }


def _morphology_class_rank(value: str) -> int:
    return HYBRID_MORPHOLOGY_PROMOTION_ORDER.index(value)


def _build_local_asset_reference_map(
    *,
    root_mapping: Mapping[str, Any],
    asset_keys: Sequence[Any],
) -> dict[str, Any]:
    return {
        str(asset_key): copy.deepcopy(
            _resolve_local_asset_reference(
                root_mapping=root_mapping,
                asset_key=str(asset_key),
            )
        )
        for asset_key in asset_keys
    }


def _resolve_local_asset_reference(
    *,
    root_mapping: Mapping[str, Any],
    asset_key: str,
) -> Any:
    geometry_asset_records = _require_mapping(
        root_mapping.get("geometry_asset_records"),
        field_name="selected_root_asset.geometry_asset_records",
    )
    operator_asset_records = _require_mapping(
        root_mapping.get("operator_asset_records"),
        field_name="selected_root_asset.operator_asset_records",
    )
    coupling_asset_records = _require_mapping(
        root_mapping.get("coupling_asset_records"),
        field_name="selected_root_asset.coupling_asset_records",
    )
    if asset_key == "raw_mesh":
        return _require_mapping(
            geometry_asset_records[RAW_MESH_KEY],
            field_name="selected_root_asset.raw_mesh",
        )
    if asset_key == "raw_swc_skeleton":
        return _require_mapping(
            geometry_asset_records[RAW_SKELETON_KEY],
            field_name="selected_root_asset.raw_skeleton",
        )
    if asset_key == SKELETON_RUNTIME_ASSET_KEY:
        return _resolve_skeleton_runtime_asset_reference(
            root_mapping=root_mapping,
        )
    if asset_key == "processed_surface_mesh":
        return _require_mapping(
            geometry_asset_records[SIMPLIFIED_MESH_KEY],
            field_name="selected_root_asset.processed_surface_mesh",
        )
    if asset_key == "geometry_descriptors":
        return _require_mapping(
            geometry_asset_records[DESCRIPTOR_SIDECAR_KEY],
            field_name="selected_root_asset.geometry_descriptors",
        )
    if asset_key == "geometry_qa":
        return _require_mapping(
            geometry_asset_records[QA_SIDECAR_KEY],
            field_name="selected_root_asset.geometry_qa",
        )
    if asset_key == "fine_surface_operator":
        return _require_mapping(
            operator_asset_records[FINE_OPERATOR_KEY],
            field_name="selected_root_asset.fine_surface_operator",
        )
    if asset_key == "coarse_patch_operator":
        return _require_mapping(
            operator_asset_records[COARSE_OPERATOR_KEY],
            field_name="selected_root_asset.coarse_patch_operator",
        )
    if asset_key == "surface_transfer_operators":
        return _require_mapping(
            operator_asset_records[TRANSFER_OPERATORS_KEY],
            field_name="selected_root_asset.surface_transfer_operators",
        )
    if asset_key == "surface_operator_metadata":
        return _require_mapping(
            operator_asset_records[OPERATOR_METADATA_KEY],
            field_name="selected_root_asset.surface_operator_metadata",
        )
    if asset_key == "root_local_synapse_registry":
        return _require_mapping(
            coupling_asset_records[LOCAL_SYNAPSE_REGISTRY_KEY],
            field_name="selected_root_asset.root_local_synapse_registry",
        )
    if asset_key == "incoming_anchor_map":
        return _require_mapping(
            coupling_asset_records[INCOMING_ANCHOR_MAP_KEY],
            field_name="selected_root_asset.incoming_anchor_map",
        )
    if asset_key == "outgoing_anchor_map":
        return _require_mapping(
            coupling_asset_records[OUTGOING_ANCHOR_MAP_KEY],
            field_name="selected_root_asset.outgoing_anchor_map",
        )
    if asset_key == "root_coupling_index":
        return _require_mapping(
            coupling_asset_records[COUPLING_INDEX_KEY],
            field_name="selected_root_asset.root_coupling_index",
        )
    if asset_key == "selected_edge_coupling_bundles":
        return [
            copy.deepcopy(item)
            for item in _selected_peer_edge_bundles(root_mapping)
        ]
    raise ValueError(f"Unsupported local asset key {asset_key!r}.")


def _validate_required_local_assets(
    *,
    arm_id: str,
    root_id: int,
    morphology_class: str,
    asset_references: Mapping[str, Any],
) -> None:
    for asset_key, asset_reference in asset_references.items():
        if asset_key == "selected_edge_coupling_bundles":
            missing_paths = [
                str(item["path"])
                for item in _require_sequence(
                    asset_reference,
                    field_name=(
                        f"surface_wave arm {arm_id!r} required "
                        f"selected_edge_coupling_bundles"
                    ),
                )
                if str(item["status"]) != ASSET_STATUS_READY or not bool(item["exists"])
            ]
            if missing_paths:
                raise ValueError(
                    f"surface_wave arm {arm_id!r} requested morphology_class "
                    f"{morphology_class!r} for root {root_id}, but selected edge "
                    f"coupling bundles are unavailable at {missing_paths!r}."
                )
            continue
        asset_record = _require_mapping(
            asset_reference,
            field_name=(
                f"surface_wave arm {arm_id!r} required local asset {asset_key!r}"
            ),
        )
        if str(asset_record["status"]) != ASSET_STATUS_READY or not bool(
            asset_record["exists"]
        ):
            raise ValueError(
                f"surface_wave arm {arm_id!r} requested morphology_class "
                f"{morphology_class!r} for root {root_id}, but required local asset "
                f"{asset_key!r} is unavailable at {asset_record['path']} with status "
                f"{asset_record['status']!r}."
            )


def _selected_peer_edge_bundles(
    root_mapping: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [
        copy.deepcopy(_require_mapping(item, field_name="edge_bundle_paths"))
        for item in _require_sequence(
            root_mapping.get("edge_bundle_paths"),
            field_name="selected_root_asset.edge_bundle_paths",
        )
        if bool(_require_mapping(item, field_name="edge_bundle_paths").get("selected_peer"))
    ]


def _resolve_surface_wave_operator_asset(
    *,
    arm_id: str,
    root_mapping: Mapping[str, Any],
    anisotropy_mode: str,
    branching_mode: str,
    hybrid_morphology: Mapping[str, Any],
) -> dict[str, Any]:
    root_id = int(root_mapping["root_id"])
    operator_bundle = _require_mapping(
        root_mapping.get("operator_bundle"),
        field_name=f"circuit_assets.selected_root_assets[{root_id}].operator_bundle",
    )
    operator_status = _normalize_nonempty_string(
        root_mapping.get("operator_bundle_status", operator_bundle.get("status")),
        field_name=f"circuit_assets.selected_root_assets[{root_id}].operator_bundle_status",
    )
    if operator_status != ASSET_STATUS_READY:
        raise ValueError(
            f"surface_wave arm {arm_id!r} requires ready operator bundles for "
            f"selected root {root_id}, found status {operator_status!r}."
        )
    operator_asset_records = _require_mapping(
        root_mapping.get("operator_asset_records"),
        field_name=f"circuit_assets.selected_root_assets[{root_id}].operator_asset_records",
    )
    missing_operator_paths = [
        asset_key
        for asset_key in (
            FINE_OPERATOR_KEY,
            COARSE_OPERATOR_KEY,
            TRANSFER_OPERATORS_KEY,
            OPERATOR_METADATA_KEY,
        )
        if not bool(
            _require_mapping(
                operator_asset_records.get(asset_key),
                field_name=(
                    f"circuit_assets.selected_root_assets[{root_id}]."
                    f"operator_asset_records.{asset_key}"
                ),
            ).get("exists")
        )
    ]
    if missing_operator_paths:
        raise ValueError(
            f"surface_wave arm {arm_id!r} is missing local operator assets "
            f"{missing_operator_paths!r} for selected root {root_id}."
        )

    metadata_path = Path(
        str(
            _require_mapping(
                operator_asset_records[OPERATOR_METADATA_KEY],
                field_name=f"operator_asset_records[{root_id}].operator_metadata",
            )["path"]
        )
    ).resolve()
    loaded_operator_metadata = load_operator_bundle_metadata(metadata_path)
    if loaded_operator_metadata != dict(operator_bundle):
        raise ValueError(
            f"surface_wave arm {arm_id!r} found operator metadata drift for root "
            f"{root_id}: manifest record does not match {metadata_path}."
        )

    normalization = _normalize_nonempty_string(
        operator_bundle.get("normalization"),
        field_name=f"operator_bundle[{root_id}].normalization",
    )
    if normalization != "mass_normalized":
        raise ValueError(
            f"surface_wave arm {arm_id!r} requires mass_normalized operators, but "
            f"root {root_id} exposes normalization {normalization!r}."
        )
    transfer_operators = _require_mapping(
        operator_bundle.get("transfer_operators"),
        field_name=f"operator_bundle[{root_id}].transfer_operators",
    )
    surface_membership = _require_mapping(
        transfer_operators.get("surface_to_patch_membership"),
        field_name=(
            f"operator_bundle[{root_id}].transfer_operators.surface_to_patch_membership"
        ),
    )
    fine_to_coarse = _require_mapping(
        transfer_operators.get("fine_to_coarse_restriction"),
        field_name=(
            f"operator_bundle[{root_id}].transfer_operators.fine_to_coarse_restriction"
        ),
    )
    if not bool(surface_membership.get("available")) or not bool(
        fine_to_coarse.get("available")
    ):
        raise ValueError(
            f"surface_wave arm {arm_id!r} requires surface-to-patch transfer "
            f"operators for root {root_id}, but the operator bundle does not "
            "expose them as available."
        )

    anisotropy_model = _normalize_nonempty_string(
        operator_bundle.get("anisotropy_model"),
        field_name=f"operator_bundle[{root_id}].anisotropy_model",
    )
    if anisotropy_mode == "operator_embedded" and anisotropy_model == "isotropic":
        raise ValueError(
            f"surface_wave arm {arm_id!r} requested anisotropy.mode "
            "'operator_embedded' but root "
            f"{root_id} operator bundle only exposes anisotropy_model 'isotropic'."
        )

    descriptor_sidecar = _require_mapping(
        _resolve_local_asset_reference(
            root_mapping=root_mapping,
            asset_key="geometry_descriptors",
        ),
        field_name=f"surface_wave arm {arm_id!r} geometry_descriptors",
    )
    descriptor_sidecar_path = Path(str(descriptor_sidecar["path"])).resolve()
    if branching_mode != "disabled" and not descriptor_sidecar_path.exists():
        raise ValueError(
            f"surface_wave arm {arm_id!r} requested branching.mode {branching_mode!r} "
            f"but root {root_id} is missing geometry descriptors at "
            f"{descriptor_sidecar_path}."
        )

    spectral_radius = _estimate_surface_wave_operator_spectral_radius(
        operator_path=Path(
            str(
                _require_mapping(
                    operator_asset_records[FINE_OPERATOR_KEY],
                    field_name=f"operator_asset_records[{root_id}].fine_operator",
                )["path"]
            )
        ).resolve(),
        arm_id=arm_id,
        root_id=root_id,
    )
    return {
        "root_id": root_id,
        "hybrid_morphology": copy.deepcopy(hybrid_morphology),
        "operator_bundle_status": operator_status,
        "preferred_discretization_family": str(
            operator_bundle["preferred_discretization_family"]
        ),
        "discretization_family": str(operator_bundle["discretization_family"]),
        "mass_treatment": str(operator_bundle["mass_treatment"]),
        "normalization": normalization,
        "boundary_condition_mode": str(operator_bundle["boundary_condition_mode"]),
        "anisotropy_model": anisotropy_model,
        "fallback_policy": copy.deepcopy(operator_bundle["fallback_policy"]),
        "fine_operator_path": str(
            Path(str(operator_asset_records[FINE_OPERATOR_KEY]["path"])).resolve()
        ),
        "coarse_operator_path": str(
            Path(str(operator_asset_records[COARSE_OPERATOR_KEY]["path"])).resolve()
        ),
        "transfer_operator_path": str(
            Path(str(operator_asset_records[TRANSFER_OPERATORS_KEY]["path"])).resolve()
        ),
        "operator_metadata_path": str(metadata_path),
        "operator_metadata": copy.deepcopy(loaded_operator_metadata),
        "descriptor_sidecar_path": str(descriptor_sidecar_path),
        "surface_to_patch_membership_available": True,
        "fine_to_coarse_restriction_available": True,
        "coarse_to_fine_prolongation_available": bool(
            _require_mapping(
                transfer_operators.get("coarse_to_fine_prolongation"),
                field_name=(
                    "operator_bundle"
                    f"[{root_id}].transfer_operators.coarse_to_fine_prolongation"
                ),
            ).get("available")
        ),
        "normalized_state_transfer_available": bool(
            _require_mapping(
                transfer_operators.get("normalized_state_transfer"),
                field_name=(
                    "operator_bundle"
                    f"[{root_id}].transfer_operators.normalized_state_transfer"
                ),
            ).get("available")
        ),
        "spectral_radius": spectral_radius,
        "stability_metadata": {
            "spectral_radius": spectral_radius,
            "source": "simulation_planning",
        },
    }


def _resolve_skeleton_runtime_asset_reference(
    *,
    root_mapping: Mapping[str, Any],
) -> dict[str, Any]:
    geometry_asset_records = _require_mapping(
        root_mapping.get("geometry_asset_records"),
        field_name="selected_root_asset.geometry_asset_records",
    )
    raw_skeleton_record = _require_mapping(
        geometry_asset_records[RAW_SKELETON_KEY],
        field_name="selected_root_asset.raw_skeleton",
    )
    root_id = int(root_mapping["root_id"])
    processed_graph_dir = Path(
        str(
            _require_mapping(
                geometry_asset_records[DESCRIPTOR_SIDECAR_KEY],
                field_name="selected_root_asset.geometry_descriptors",
            )["path"]
        )
    ).resolve().parent
    if str(raw_skeleton_record["status"]) != ASSET_STATUS_READY or not bool(
        raw_skeleton_record["exists"]
    ):
        paths = build_skeleton_runtime_asset_paths(
            root_id,
            processed_graph_dir=processed_graph_dir,
        )
        return {
            "root_id": root_id,
            "contract_version": None,
            "approximation_family": None,
            "graph_operator_family": None,
            "state_layout": None,
            "projection_surface": None,
            "projection_layout": None,
            "source_injection_strategy": None,
            "raw_skeleton_path": str(Path(str(raw_skeleton_record["path"])).resolve()),
            "data_path": str(paths.data_path),
            "metadata_path": str(paths.metadata_path),
            "path": str(paths.metadata_path),
            "status": str(raw_skeleton_record["status"]),
            "exists": bool(paths.metadata_path.exists()),
            "asset_hash": None,
            "node_count": 0,
            "edge_count": 0,
            "branch_point_count": 0,
            "leaf_count": 0,
            "readout_semantics": {},
            "operator": {},
        }
    return build_skeleton_runtime_asset_record(
        root_id=root_id,
        raw_skeleton_path=raw_skeleton_record["path"],
        processed_graph_dir=processed_graph_dir,
    )


def _resolve_root_coupling_asset_record(
    *,
    arm_id: str,
    root_mapping: Mapping[str, Any],
    hybrid_morphology: Mapping[str, Any],
) -> dict[str, Any]:
    root_id = int(root_mapping["root_id"])
    coupling_bundle = _require_mapping(
        root_mapping.get("coupling_bundle"),
        field_name=f"circuit_assets.selected_root_assets[{root_id}].coupling_bundle",
    )
    topology_family = _normalize_nonempty_string(
        coupling_bundle.get("topology_family"),
        field_name=f"coupling_bundle[{root_id}].topology_family",
    )
    fallback_hierarchy = [
        _normalize_nonempty_string(
            item,
            field_name=f"coupling_bundle[{root_id}].fallback_hierarchy[{index}]",
        )
        for index, item in enumerate(
            _require_sequence(
                coupling_bundle.get("fallback_hierarchy"),
                field_name=f"coupling_bundle[{root_id}].fallback_hierarchy",
            )
        )
    ]
    selected_edge_bundle_paths = _selected_peer_edge_bundles(root_mapping)
    blocked_selected_edges = [
        str(edge_bundle["path"])
        for edge_bundle in selected_edge_bundle_paths
        if str(edge_bundle["status"]) != ASSET_STATUS_READY or not bool(edge_bundle["exists"])
    ]
    if blocked_selected_edges:
        raise ValueError(
            f"surface_wave arm {arm_id!r} requires ready edge coupling bundles "
            f"for selected peers of root {root_id}, but found non-ready entries "
            f"{blocked_selected_edges!r}."
        )

    coupling_asset_records = _require_mapping(
        root_mapping.get("coupling_asset_records"),
        field_name=f"circuit_assets.selected_root_assets[{root_id}].coupling_asset_records",
    )
    return {
        "root_id": root_id,
        "hybrid_morphology": copy.deepcopy(hybrid_morphology),
        "topology_family": topology_family,
        "fallback_hierarchy": fallback_hierarchy,
        "kernel_family": str(coupling_bundle["kernel_family"]),
        "sign_representation": str(coupling_bundle["sign_representation"]),
        "delay_representation": str(coupling_bundle["delay_representation"]),
        "delay_model": str(coupling_bundle["delay_model"]),
        "aggregation_rule": str(coupling_bundle["aggregation_rule"]),
        "missing_geometry_policy": str(coupling_bundle["missing_geometry_policy"]),
        "source_cloud_normalization": str(
            coupling_bundle["source_cloud_normalization"]
        ),
        "target_cloud_normalization": str(
            coupling_bundle["target_cloud_normalization"]
        ),
        "local_synapse_registry_path": str(
            Path(
                str(coupling_asset_records[LOCAL_SYNAPSE_REGISTRY_KEY]["path"])
            ).resolve()
        ),
        "incoming_anchor_map_path": str(
            Path(str(coupling_asset_records[INCOMING_ANCHOR_MAP_KEY]["path"])).resolve()
        ),
        "outgoing_anchor_map_path": str(
            Path(str(coupling_asset_records[OUTGOING_ANCHOR_MAP_KEY]["path"])).resolve()
        ),
        "coupling_index_path": str(
            Path(str(coupling_asset_records[COUPLING_INDEX_KEY]["path"])).resolve()
        ),
        "selected_edge_bundle_paths": selected_edge_bundle_paths,
    }


def _resolve_surface_wave_coupling_asset(
    *,
    arm_id: str,
    root_mapping: Mapping[str, Any],
    hybrid_morphology: Mapping[str, Any],
) -> dict[str, Any]:
    asset = _resolve_root_coupling_asset_record(
        arm_id=arm_id,
        root_mapping=root_mapping,
        hybrid_morphology=hybrid_morphology,
    )
    root_id = int(root_mapping["root_id"])
    if asset["topology_family"] != DISTRIBUTED_PATCH_CLOUD_TOPOLOGY or (
        not asset["fallback_hierarchy"]
        or asset["fallback_hierarchy"][0] != SURFACE_PATCH_CLOUD_MODE
    ):
        raise ValueError(
            f"surface_wave arm {arm_id!r} requires coupling topology_family "
            f"{DISTRIBUTED_PATCH_CLOUD_TOPOLOGY!r} with leading fallback "
            f"{SURFACE_PATCH_CLOUD_MODE!r}, but root {root_id} declares "
            f"topology_family {asset['topology_family']!r} and fallback_hierarchy "
            f"{asset['fallback_hierarchy']!r}."
        )
    return asset


def _resolve_skeleton_neuron_coupling_asset(
    *,
    arm_id: str,
    root_mapping: Mapping[str, Any],
    hybrid_morphology: Mapping[str, Any],
) -> dict[str, Any]:
    asset = _resolve_root_coupling_asset_record(
        arm_id=arm_id,
        root_mapping=root_mapping,
        hybrid_morphology=hybrid_morphology,
    )
    root_id = int(root_mapping["root_id"])
    if SKELETON_SEGMENT_CLOUD_MODE not in asset["fallback_hierarchy"]:
        raise ValueError(
            f"surface_wave arm {arm_id!r} requested morphology_class "
            f"{SKELETON_NEURON_CLASS!r} for root {root_id}, but coupling_bundle "
            f"fallback_hierarchy {asset['fallback_hierarchy']!r} does not expose "
            f"{SKELETON_SEGMENT_CLOUD_MODE!r}."
        )
    return asset


def _resolve_skeleton_runtime_asset(
    *,
    arm_id: str,
    root_mapping: Mapping[str, Any],
    hybrid_morphology: Mapping[str, Any],
) -> dict[str, Any]:
    asset = _resolve_local_asset_reference(
        root_mapping=root_mapping,
        asset_key=SKELETON_RUNTIME_ASSET_KEY,
    )
    if str(asset["status"]) != ASSET_STATUS_READY or not bool(asset["exists"]):
        raise ValueError(
            f"surface_wave arm {arm_id!r} requested morphology_class "
            f"{SKELETON_NEURON_CLASS!r} for root {int(root_mapping['root_id'])}, but "
            f"required local asset {SKELETON_RUNTIME_ASSET_KEY!r} is unavailable at "
            f"{asset['path']} with status {asset['status']!r}."
        )
    return {
        **copy.deepcopy(asset),
        "hybrid_morphology": copy.deepcopy(hybrid_morphology),
    }


def _resolve_point_neuron_coupling_asset(
    *,
    arm_id: str,
    root_mapping: Mapping[str, Any],
    hybrid_morphology: Mapping[str, Any],
) -> dict[str, Any]:
    asset = _resolve_root_coupling_asset_record(
        arm_id=arm_id,
        root_mapping=root_mapping,
        hybrid_morphology=hybrid_morphology,
    )
    root_id = int(root_mapping["root_id"])
    if (
        asset["topology_family"] != POINT_TO_POINT_TOPOLOGY
        and POINT_NEURON_LUMPED_MODE not in asset["fallback_hierarchy"]
    ):
        raise ValueError(
            f"surface_wave arm {arm_id!r} requested morphology_class "
            f"{POINT_NEURON_CLASS!r} for root {root_id}, but coupling_bundle "
            f"topology_family {asset['topology_family']!r} with fallback_hierarchy "
            f"{asset['fallback_hierarchy']!r} does not support "
            f"{POINT_NEURON_LUMPED_MODE!r} anchors."
        )
    return asset


def _resolve_surface_wave_operator_assets(
    *,
    arm_id: str,
    selected_root_assets: Sequence[Mapping[str, Any]],
    anisotropy_mode: str,
    branching_mode: str,
    hybrid_morphology_by_root: Mapping[int, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for index, root_asset in enumerate(selected_root_assets):
        root_mapping = _require_mapping(
            root_asset,
            field_name=f"circuit_assets.selected_root_assets[{index}]",
        )
        root_id = int(root_mapping["root_id"])
        resolved.append(
            _resolve_surface_wave_operator_asset(
                arm_id=arm_id,
                root_mapping=root_mapping,
                anisotropy_mode=anisotropy_mode,
                branching_mode=branching_mode,
                hybrid_morphology=hybrid_morphology_by_root[root_id],
            )
        )
    return resolved


def _resolve_surface_wave_coupling_assets(
    *,
    arm_id: str,
    selected_root_assets: Sequence[Mapping[str, Any]],
    hybrid_morphology_by_root: Mapping[int, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for index, root_asset in enumerate(selected_root_assets):
        root_mapping = _require_mapping(
            root_asset,
            field_name=f"circuit_assets.selected_root_assets[{index}]",
        )
        root_id = int(root_mapping["root_id"])
        resolved.append(
            _resolve_surface_wave_coupling_asset(
                arm_id=arm_id,
                root_mapping=root_mapping,
                hybrid_morphology=hybrid_morphology_by_root[root_id],
            )
        )
    return resolved


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


def _estimate_surface_wave_operator_spectral_radius(
    *,
    operator_path: Path,
    arm_id: str,
    root_id: int,
) -> float:
    try:
        with np.load(operator_path, allow_pickle=False) as payload:
            arrays = {
                key: payload[key]
                for key in payload.files
            }
    except Exception as exc:  # pragma: no cover - exercised through ValueError surface
        raise ValueError(
            f"surface_wave arm {arm_id!r} could not load the fine operator for root "
            f"{root_id} from {operator_path}: {exc}."
        ) from exc
    try:
        operator_matrix = deserialize_sparse_matrix(arrays, prefix="operator")
    except Exception as exc:  # pragma: no cover - exercised through ValueError surface
        raise ValueError(
            f"surface_wave arm {arm_id!r} found an unreadable fine operator payload "
            f"for root {root_id} at {operator_path}: {exc}."
        ) from exc
    if operator_matrix.shape[0] != operator_matrix.shape[1] or operator_matrix.shape[0] < 1:
        raise ValueError(
            f"surface_wave arm {arm_id!r} requires a square non-empty fine operator "
            f"for root {root_id}, got shape {operator_matrix.shape!r}."
        )
    if operator_matrix.shape[0] <= 4:
        eigenvalues = np.linalg.eigvalsh(operator_matrix.toarray())
        spectral_radius = float(np.max(eigenvalues))
    else:
        spectral_radius = float(
            spla.eigsh(
                operator_matrix.astype(np.float64),
                k=1,
                which="LA",
                return_eigenvectors=False,
            )[0]
        )
    if not math.isfinite(spectral_radius):
        raise ValueError(
            f"surface_wave arm {arm_id!r} produced a non-finite operator spectral "
            f"radius for root {root_id} from {operator_path}."
        )
    return round(max(0.0, spectral_radius), 12)


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value


def _require_sequence(value: Any, *, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field_name} must be a list.")
    return value


def _optional_string_sequence(value: Any) -> list[str]:
    if value is None:
        return []
    return [str(item) for item in _require_sequence(value, field_name="value")]


def _asset_record_reference(
    value: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    record = _require_mapping(value, field_name=field_name)
    path = Path(
        _normalize_nonempty_string(
            record.get("path"),
            field_name=f"{field_name}.path",
        )
    ).resolve()
    status = _normalize_nonempty_string(
        record.get("status"),
        field_name=f"{field_name}.status",
    )
    return {
        "path": str(path),
        "status": status,
        "exists": bool(path.exists()),
    }


def _extract_arm_plans(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(plan, Mapping):
        raise ValueError("plan must be a mapping.")
    arm_plans = plan.get("arm_plans")
    if not isinstance(arm_plans, list):
        raise ValueError("plan.arm_plans must be a list.")
    return [
        copy.deepcopy(arm_plan)
        for arm_plan in arm_plans
        if isinstance(arm_plan, Mapping)
    ]


def _extract_seed_sweep(plan: Mapping[str, Any]) -> list[int]:
    seed_sweep = plan.get("seed_sweep")
    return _normalize_seed_sweep(seed_sweep)


def _expand_arm_plan_for_seed(arm_plan: Mapping[str, Any], seed: int) -> dict[str, Any]:
    expanded = copy.deepcopy(dict(arm_plan))
    runtime = dict(expanded["runtime"])
    result_bundle = dict(expanded["result_bundle"])
    result_bundle_metadata = build_simulator_result_bundle_metadata(
        manifest_reference=expanded["manifest_reference"],
        arm_reference=expanded["arm_reference"],
        seed=seed,
        rng_family=runtime["determinism_defaults"]["rng_family"],
        seed_scope=runtime["determinism_defaults"]["seed_scope"],
        timebase=runtime["timebase"],
        selected_assets=expanded["selected_assets"],
        readout_catalog=runtime.get("shared_readout_catalog", runtime["readout_catalog"]),
        processed_simulator_results_dir=runtime["processed_simulator_results_dir"],
    )
    result_bundle_reference = build_simulator_result_bundle_reference(result_bundle_metadata)
    expanded["seed_handling"]["default_seed"] = int(seed)
    expanded["seed_handling"]["default_seed_source"] = "manifest.seed_sweep"
    expanded["determinism"] = build_simulator_determinism(
        seed=seed,
        rng_family=runtime["determinism_defaults"]["rng_family"],
        seed_scope=runtime["determinism_defaults"]["seed_scope"],
    )
    result_bundle["metadata"] = result_bundle_metadata
    result_bundle["reference"] = result_bundle_reference
    expanded["result_bundle"] = result_bundle
    return expanded


def _default_timebase_from_manifest_summary(
    manifest_summary: Mapping[str, Any],
) -> dict[str, Any]:
    resolved_stimulus = dict(manifest_summary["resolved_stimulus"])
    temporal_sampling = dict(resolved_stimulus["temporal_sampling"])
    return {
        "dt_ms": temporal_sampling["dt_ms"],
        "duration_ms": temporal_sampling["duration_ms"],
        "time_origin_ms": temporal_sampling.get("time_origin_ms", 0.0),
        "sample_count": temporal_sampling.get("frame_count"),
    }


def _normalize_seed_sweep(payload: Any) -> list[int]:
    if payload is None:
        return []
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("seed_sweep must be a list when provided.")
    normalized = [int(value) for value in payload]
    if len(set(normalized)) != len(normalized):
        raise ValueError("seed_sweep contains duplicate values.")
    return normalized


def _normalize_identifier_list(payload: Any, *, field_name: str) -> list[str]:
    if payload is None:
        return []
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a list when provided.")
    normalized = [
        _normalize_identifier(value, field_name=f"{field_name}[{index}]")
        for index, value in enumerate(payload)
    ]
    return sorted(set(normalized))


def _normalize_bool(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} must be a boolean.")


def _resolve_project_root(project_root: str | Path | None) -> Path:
    if project_root is None:
        return Path.cwd().resolve()
    return Path(project_root).resolve()


def _resolve_project_path(path: str | Path, project_root: Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()


def _stable_hash(payload: Any) -> str:
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
