from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse.linalg as spla

from .config import get_config_path, get_project_root, load_config
from .coupling_contract import (
    ASSET_STATUS_READY,
    COUPLING_BUNDLE_CONTRACT_VERSION,
    DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
    INCOMING_ANCHOR_MAP_KEY,
    LOCAL_SYNAPSE_REGISTRY_KEY,
    OUTGOING_ANCHOR_MAP_KEY,
    SURFACE_PATCH_CLOUD_MODE,
    discover_coupling_bundle_paths,
    discover_edge_coupling_bundle_paths,
    parse_coupling_bundle_metadata,
)
from .geometry_contract import (
    COARSE_OPERATOR_KEY,
    FINE_OPERATOR_KEY,
    OPERATOR_BUNDLE_CONTRACT_VERSION,
    OPERATOR_METADATA_KEY,
    TRANSFER_OPERATORS_KEY,
    discover_operator_bundle_paths,
    load_geometry_manifest,
    load_geometry_manifest_records,
    load_operator_bundle_metadata,
    parse_operator_bundle_metadata,
)
from .io_utils import read_root_ids
from .manifests import (
    load_json,
    load_yaml,
    validate_manifest_payload,
)
from .retinal_contract import build_retinal_bundle_reference, load_retinal_bundle_metadata
from .retinal_workflow import resolve_retinal_bundle_input
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

SELECTED_ROOT_IDS_ASSET_ROLE = "selected_root_ids"
INPUT_BUNDLE_ASSET_ROLE = "input_bundle"
GEOMETRY_MANIFEST_ASSET_ROLE = "geometry_manifest"
COUPLING_REGISTRY_ASSET_ROLE = "coupling_synapse_registry"
MODEL_CONFIGURATION_ASSET_ROLE = "model_configuration"
SURFACE_WAVE_OPERATOR_INVENTORY_ASSET_ROLE = "surface_wave_operator_inventory"

SUBSET_MANIFEST_FILENAME = "subset_manifest.json"
ALLOWED_SIMULATION_CONFIG_KEYS = {
    "version",
    "input",
    "timebase",
    "readout_catalog",
    "baseline_families",
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
SURFACE_WAVE_MAX_INTERNAL_SUBSTEPS_PER_OUTPUT_STEP = 256
SURFACE_WAVE_STABILITY_TOLERANCE_MS = 1.0e-9


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

    manifest_payload = load_yaml(manifest_file)
    schema_payload = load_json(schema_file)
    design_lock_payload = load_yaml(design_lock_file)
    manifest_summary = validate_manifest_payload(
        manifest=copy.deepcopy(manifest_payload),
        schema=schema_payload,
        design_lock=design_lock_payload,
        manifest_path=manifest_file,
        processed_stimulus_dir=cfg["paths"]["processed_stimulus_dir"],
    )

    runtime_config = normalize_simulation_runtime_config(
        cfg.get("simulation"),
        default_timebase=_default_timebase_from_manifest_summary(manifest_summary),
        project_root=project_root,
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
        processed_stimulus_dir=Path(cfg["paths"]["processed_stimulus_dir"]),
        processed_retinal_dir=Path(cfg["paths"]["processed_retinal_dir"]),
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
        arm_reference = build_simulator_arm_reference(
            arm_id=arm["arm_id"],
            model_mode=arm["model_mode"],
            baseline_family=arm["baseline_family"],
            comparison_tags=arm.get("tags"),
        )
        seed_handling = _resolve_arm_seed_handling(
            arm=arm,
            arm_index=arm_index,
            manifest_random_seed=manifest_payload["random_seed"],
            seed_sweep=seed_sweep,
        )
        determinism = build_simulator_determinism(
            seed=seed_handling["default_seed"],
            rng_family=runtime_config["determinism"]["rng_family"],
            seed_scope=runtime_config["determinism"]["seed_scope"],
        )
        topology_condition = _normalize_identifier(
            arm["topology_condition"],
            field_name=f"comparison_arms[{arm_index}].topology_condition",
        )
        morphology_condition = _normalize_identifier(
            arm["morphology_condition"],
            field_name=f"comparison_arms[{arm_index}].morphology_condition",
        )
        model_configuration = _build_model_configuration(
            arm_reference=arm_reference,
            runtime_config=runtime_config,
            circuit_assets=circuit_assets,
            topology_condition=topology_condition,
        )
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
        arm_plans.append(
            {
                "plan_version": SIMULATION_PLAN_VERSION,
                "arm_index": arm_index,
                "manifest_reference": copy.deepcopy(manifest_reference),
                "arm_reference": copy.deepcopy(arm_reference),
                "topology_condition": topology_condition,
                "morphology_condition": morphology_condition,
                "notes": _normalize_nonempty_string(
                    arm["notes"],
                    field_name=f"comparison_arms[{arm_index}].notes",
                ),
                "tags": _normalize_identifier_list(
                    arm.get("tags"),
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
                "selected_assets": copy.deepcopy(result_bundle_metadata["selected_assets"]),
                "result_bundle": {
                    "reference": result_bundle_reference,
                    "metadata": result_bundle_metadata,
                },
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
    }


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
    root_ids = read_root_ids(selected_root_ids_path)
    if not root_ids:
        raise ValueError(
            f"Selected-root roster at {selected_root_ids_path} is empty."
        )
    normalized_root_ids = sorted(int(root_id) for root_id in root_ids)
    if len(set(normalized_root_ids)) != len(normalized_root_ids):
        raise ValueError(
            f"Selected-root roster at {selected_root_ids_path} contains duplicate root IDs."
        )

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
    normalized_subset_name = _normalize_identifier(
        subset_name,
        field_name="manifest.subset_name",
    )
    safe_subset_name = re.sub(r"[^0-9A-Za-z._-]+", "_", normalized_subset_name).strip("_") or "default"
    subset_manifest_path = (subset_output_dir / safe_subset_name / SUBSET_MANIFEST_FILENAME).resolve()
    if not subset_manifest_path.exists():
        return None
    subset_manifest = load_json(subset_manifest_path)
    manifest_root_ids = subset_manifest.get("root_ids")
    if not isinstance(manifest_root_ids, list):
        raise ValueError(
            f"Subset manifest at {subset_manifest_path} is missing the root_ids list."
        )
    normalized_manifest_root_ids = sorted(int(root_id) for root_id in manifest_root_ids)
    if normalized_manifest_root_ids != expected_root_ids:
        raise ValueError(
            "Subset manifest root_ids do not match the selected-root roster: "
            f"{subset_manifest_path}."
        )
    return {
        "subset_manifest_path": str(subset_manifest_path),
        "subset_manifest_version": str(subset_manifest.get("subset_manifest_version", "")),
        "root_id_count": len(normalized_manifest_root_ids),
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
        operator_bundle = parse_operator_bundle_metadata(record.get("operator_bundle", {}))
        operator_paths = {
            asset_key: str(Path(asset_path).resolve())
            for asset_key, asset_path in discover_operator_bundle_paths(record).items()
        }
        missing_ready_operator_assets = [
            asset_key
            for asset_key, asset_record in operator_bundle["assets"].items()
            if str(asset_record["status"]) == ASSET_STATUS_READY
            and not Path(str(asset_record["path"])).exists()
        ]
        if missing_ready_operator_assets:
            raise ValueError(
                f"Selected root {root_id} is missing ready operator assets "
                f"{missing_ready_operator_assets!r} under {geometry_manifest_path}."
            )
        coupling_bundle = parse_coupling_bundle_metadata(record.get("coupling_bundle", {}))
        if coupling_bundle["status"] != ASSET_STATUS_READY:
            raise ValueError(
                f"Selected root {root_id} has coupling_bundle status "
                f"{coupling_bundle['status']!r}, expected 'ready'."
            )
        bundle_paths = discover_coupling_bundle_paths(record)
        missing_required_assets = [
            asset_key
            for asset_key, asset_path in bundle_paths.items()
            if not Path(asset_path).exists()
        ]
        if missing_required_assets:
            raise ValueError(
                f"Selected root {root_id} is missing local coupling assets "
                f"{missing_required_assets!r} under {geometry_manifest_path}."
            )
        edge_bundles = discover_edge_coupling_bundle_paths(record)
        missing_edge_paths = [
            str(edge_bundle["path"])
            for edge_bundle in edge_bundles
            if str(edge_bundle["status"]) == ASSET_STATUS_READY
            and not Path(edge_bundle["path"]).exists()
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
                "operator_bundle_status": str(operator_bundle["status"]),
                "required_operator_assets": operator_paths,
                "descriptor_sidecar_path": str(
                    Path(str(record.get("descriptor_sidecar_path", ""))).resolve()
                ),
                "qa_sidecar_path": str(
                    Path(str(record.get("qa_sidecar_path", ""))).resolve()
                ),
                "coupling_bundle_status": str(coupling_bundle["status"]),
                "required_coupling_assets": {
                    LOCAL_SYNAPSE_REGISTRY_KEY: str(bundle_paths[LOCAL_SYNAPSE_REGISTRY_KEY]),
                    INCOMING_ANCHOR_MAP_KEY: str(bundle_paths[INCOMING_ANCHOR_MAP_KEY]),
                    OUTGOING_ANCHOR_MAP_KEY: str(bundle_paths[OUTGOING_ANCHOR_MAP_KEY]),
                    "coupling_index": str(bundle_paths["coupling_index"]),
                },
                "edge_bundle_paths": [
                    {
                        "pre_root_id": int(edge_bundle["pre_root_id"]),
                        "post_root_id": int(edge_bundle["post_root_id"]),
                        "peer_root_id": int(edge_bundle["peer_root_id"]),
                        "relation_to_root": str(edge_bundle["relation_to_root"]),
                        "path": str(Path(edge_bundle["path"]).resolve()),
                        "status": str(edge_bundle["status"]),
                        "selected_peer": int(edge_bundle["peer_root_id"]) in selected_root_set,
                    }
                    for edge_bundle in edge_bundles
                ],
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
            topology_condition=topology_condition,
            runtime_timebase=runtime_config["timebase"],
            circuit_assets=circuit_assets,
            surface_wave_model=surface_wave_model,
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
        artifact_payload = {
            "model_mode": model_mode,
            "surface_wave_reference": model_configuration["surface_wave_reference"],
            "surface_wave_model": model_configuration["surface_wave_model"],
        }
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
    topology_condition: str,
    runtime_timebase: Mapping[str, Any],
    circuit_assets: Mapping[str, Any],
    surface_wave_model: Mapping[str, Any],
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

    selected_root_operator_assets = _resolve_surface_wave_operator_assets(
        arm_id=arm_id,
        selected_root_assets=_require_sequence(
            circuit_assets.get("selected_root_assets"),
            field_name="circuit_assets.selected_root_assets",
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
    selected_root_coupling_assets = _resolve_surface_wave_coupling_assets(
        arm_id=arm_id,
        selected_root_assets=_require_sequence(
            circuit_assets.get("selected_root_assets"),
            field_name="circuit_assets.selected_root_assets",
        ),
    )

    stability_guardrails = _build_surface_wave_stability_guardrails(
        arm_id=arm_id,
        runtime_timebase=runtime_timebase,
        cfl_safety_factor=cfl_safety_factor,
        wave_speed_sq_scale=wave_speed_sq_scale,
        restoring_strength_per_ms2=restoring_strength_per_ms2,
        recovery_coupling_strength_per_ms2=recovery_coupling_strength_per_ms2,
        operator_assets=selected_root_operator_assets,
    )

    return {
        "topology_condition": topology_condition,
        "operator_inventory_hash": str(circuit_assets["operator_asset_hash"]),
        "coupling_inventory_hash": str(circuit_assets["circuit_asset_hash"]),
        "resolution": {
            "operator_family": operator_family,
            "state_space": SURFACE_WAVE_STATE_RESOLUTION,
            "coupling_anchor_resolution": SURFACE_WAVE_COUPLING_ANCHOR_RESOLUTION,
            "synaptic_spatial_support": spatial_support,
            "transfer_operator_required": True,
        },
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
        "selected_root_operator_assets": selected_root_operator_assets,
        "selected_root_coupling_assets": selected_root_coupling_assets,
        "stability_guardrails": stability_guardrails,
    }


def _resolve_surface_wave_operator_assets(
    *,
    arm_id: str,
    selected_root_assets: Sequence[Mapping[str, Any]],
    anisotropy_mode: str,
    branching_mode: str,
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for index, root_asset in enumerate(selected_root_assets):
        root_mapping = _require_mapping(
            root_asset,
            field_name=f"circuit_assets.selected_root_assets[{index}]",
        )
        root_id = int(root_mapping["root_id"])
        operator_bundle = _require_mapping(
            root_mapping.get("operator_bundle"),
            field_name=(
                f"circuit_assets.selected_root_assets[{index}].operator_bundle"
            ),
        )
        operator_status = _normalize_nonempty_string(
            root_mapping.get("operator_bundle_status", operator_bundle.get("status")),
            field_name=(
                f"circuit_assets.selected_root_assets[{index}].operator_bundle_status"
            ),
        )
        if operator_status != ASSET_STATUS_READY:
            raise ValueError(
                f"surface_wave arm {arm_id!r} requires ready operator bundles for "
                f"selected root {root_id}, found status {operator_status!r}."
            )
        operator_paths = _require_mapping(
            root_mapping.get("required_operator_assets"),
            field_name=(
                f"circuit_assets.selected_root_assets[{index}].required_operator_assets"
            ),
        )
        missing_operator_paths = [
            asset_key
            for asset_key in (
                FINE_OPERATOR_KEY,
                TRANSFER_OPERATORS_KEY,
                OPERATOR_METADATA_KEY,
            )
            if not Path(
                _normalize_nonempty_string(
                    operator_paths.get(asset_key),
                    field_name=(
                        "circuit_assets.selected_root_assets"
                        f"[{index}].required_operator_assets.{asset_key}"
                    ),
                )
            ).exists()
        ]
        if missing_operator_paths:
            raise ValueError(
                f"surface_wave arm {arm_id!r} is missing local operator assets "
                f"{missing_operator_paths!r} for selected root {root_id}."
            )

        metadata_path = Path(str(operator_paths[OPERATOR_METADATA_KEY])).resolve()
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

        descriptor_sidecar_path = Path(
            _normalize_nonempty_string(
                root_mapping.get("descriptor_sidecar_path"),
                field_name=(
                    f"circuit_assets.selected_root_assets[{index}].descriptor_sidecar_path"
                ),
            )
        ).resolve()
        if branching_mode != "disabled" and not descriptor_sidecar_path.exists():
            raise ValueError(
                f"surface_wave arm {arm_id!r} requested branching.mode {branching_mode!r} "
                f"but root {root_id} is missing geometry descriptors at "
                f"{descriptor_sidecar_path}."
            )

        spectral_radius = _estimate_surface_wave_operator_spectral_radius(
            operator_path=Path(str(operator_paths[FINE_OPERATOR_KEY])).resolve(),
            arm_id=arm_id,
            root_id=root_id,
        )
        resolved.append(
            {
                "root_id": root_id,
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
                "fine_operator_path": str(Path(str(operator_paths[FINE_OPERATOR_KEY])).resolve()),
                "coarse_operator_path": str(
                    Path(str(operator_paths[COARSE_OPERATOR_KEY])).resolve()
                ),
                "transfer_operator_path": str(
                    Path(str(operator_paths[TRANSFER_OPERATORS_KEY])).resolve()
                ),
                "operator_metadata_path": str(metadata_path),
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
            }
        )
    return resolved


def _resolve_surface_wave_coupling_assets(
    *,
    arm_id: str,
    selected_root_assets: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for index, root_asset in enumerate(selected_root_assets):
        root_mapping = _require_mapping(
            root_asset,
            field_name=f"circuit_assets.selected_root_assets[{index}]",
        )
        root_id = int(root_mapping["root_id"])
        coupling_bundle = _require_mapping(
            root_mapping.get("coupling_bundle"),
            field_name=(
                f"circuit_assets.selected_root_assets[{index}].coupling_bundle"
            ),
        )
        topology_family = _normalize_nonempty_string(
            coupling_bundle.get("topology_family"),
            field_name=f"coupling_bundle[{root_id}].topology_family",
        )
        fallback_hierarchy = [
            _normalize_nonempty_string(
                item,
                field_name=f"coupling_bundle[{root_id}].fallback_hierarchy[{edge_index}]",
            )
            for edge_index, item in enumerate(
                _require_sequence(
                    coupling_bundle.get("fallback_hierarchy"),
                    field_name=f"coupling_bundle[{root_id}].fallback_hierarchy",
                )
            )
        ]
        if topology_family != DISTRIBUTED_PATCH_CLOUD_TOPOLOGY or (
            not fallback_hierarchy or fallback_hierarchy[0] != SURFACE_PATCH_CLOUD_MODE
        ):
            raise ValueError(
                f"surface_wave arm {arm_id!r} requires coupling topology_family "
                f"{DISTRIBUTED_PATCH_CLOUD_TOPOLOGY!r} with leading fallback "
                f"{SURFACE_PATCH_CLOUD_MODE!r}, but root {root_id} declares "
                f"topology_family {topology_family!r} and fallback_hierarchy "
                f"{fallback_hierarchy!r}."
            )
        selected_edge_bundle_paths = [
            copy.deepcopy(edge_bundle)
            for edge_bundle in _require_sequence(
                root_mapping.get("edge_bundle_paths"),
                field_name=(
                    f"circuit_assets.selected_root_assets[{index}].edge_bundle_paths"
                ),
            )
            if bool(_require_mapping(edge_bundle, field_name="edge_bundle").get("selected_peer"))
        ]
        blocked_selected_edges = [
            str(edge_bundle["path"])
            for edge_bundle in selected_edge_bundle_paths
            if str(edge_bundle["status"]) != ASSET_STATUS_READY
        ]
        if blocked_selected_edges:
            raise ValueError(
                f"surface_wave arm {arm_id!r} requires ready edge coupling bundles "
                f"for selected peers of root {root_id}, but found non-ready entries "
                f"{blocked_selected_edges!r}."
            )

        required_coupling_assets = _require_mapping(
            root_mapping.get("required_coupling_assets"),
            field_name=(
                f"circuit_assets.selected_root_assets[{index}].required_coupling_assets"
            ),
        )
        resolved.append(
            {
                "root_id": root_id,
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
                    Path(str(required_coupling_assets[LOCAL_SYNAPSE_REGISTRY_KEY])).resolve()
                ),
                "incoming_anchor_map_path": str(
                    Path(str(required_coupling_assets[INCOMING_ANCHOR_MAP_KEY])).resolve()
                ),
                "outgoing_anchor_map_path": str(
                    Path(str(required_coupling_assets[OUTGOING_ANCHOR_MAP_KEY])).resolve()
                ),
                "coupling_index_path": str(
                    Path(str(required_coupling_assets["coupling_index"])).resolve()
                ),
                "selected_edge_bundle_paths": selected_edge_bundle_paths,
            }
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
