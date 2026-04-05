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
    from .simulation_analysis_planning import build_readout_analysis_plan

    return build_readout_analysis_plan(
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
    from .simulation_asset_resolution import resolve_circuit_assets

    return resolve_circuit_assets(
        manifest=manifest,
        cfg=cfg,
        selection_reference=selection_reference,
    )


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
    from .simulation_runtime_planning import build_surface_wave_execution_plan

    return build_surface_wave_execution_plan(
        arm_reference=arm_reference,
        arm_payload=arm_payload,
        point_neuron_model_spec=point_neuron_model_spec,
        topology_condition=topology_condition,
        runtime_timebase=runtime_timebase,
        circuit_assets=circuit_assets,
        surface_wave_model=surface_wave_model,
        mixed_fidelity_config=mixed_fidelity_config,
    )


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
    from .simulation_runtime_planning import resolve_surface_wave_mixed_fidelity_plan

    return resolve_surface_wave_mixed_fidelity_plan(
        arm_id=arm_id,
        arm_payload=arm_payload,
        arm_reference=arm_reference,
        selected_root_assets=selected_root_assets,
        point_neuron_model_spec=point_neuron_model_spec,
        mixed_fidelity_config=mixed_fidelity_config,
        anisotropy_mode=anisotropy_mode,
        branching_mode=branching_mode,
    )


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
