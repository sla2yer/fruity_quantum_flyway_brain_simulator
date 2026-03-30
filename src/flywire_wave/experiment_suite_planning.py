from __future__ import annotations

import copy
import hashlib
import itertools
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from .config import get_config_path, get_project_root, load_config
from .experiment_ablation_transforms import (
    build_experiment_ablation_realization,
    materialize_experiment_ablation_realization_for_seed,
)
from .dashboard_session_contract import DASHBOARD_SESSION_CONTRACT_VERSION
from .experiment_analysis_contract import EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION
from .experiment_suite_contract import (
    ABLATION_VARIANT_LINEAGE_KIND,
    ACTIVE_SUBSET_DIMENSION_ID,
    ALTERED_DELAY_ASSUMPTIONS_ABLATION_FAMILY_ID,
    ALTERED_SIGN_ASSUMPTIONS_ABLATION_FAMILY_ID,
    BASE_CONDITION_LINEAGE_KIND,
    COMPARISON_PLOT_ROLE_ID,
    COARSEN_GEOMETRY_ABLATION_FAMILY_ID,
    CONTRAST_LEVEL_DIMENSION_ID,
    COUPLING_MODE_DIMENSION_ID,
    DASHBOARD_SESSION_ROLE_ID,
    DASHBOARD_SESSION_SOURCE_KIND,
    EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
    EXPERIMENT_ANALYSIS_SOURCE_KIND,
    EXPERIMENT_MANIFEST_INPUT_ROLE_ID,
    EXPERIMENT_MANIFEST_SOURCE_KIND,
    EXPERIMENT_SUITE_CONTRACT_VERSION,
    FIDELITY_CLASS_DIMENSION_ID,
    MESH_RESOLUTION_DIMENSION_ID,
    MOTION_DIRECTION_DIMENSION_ID,
    MOTION_SPEED_DIMENSION_ID,
    NOISE_LEVEL_DIMENSION_ID,
    NO_LATERAL_COUPLING_ABLATION_FAMILY_ID,
    NO_WAVES_ABLATION_FAMILY_ID,
    REVIEW_ARTIFACT_ROLE_ID,
    SCENE_TYPE_DIMENSION_ID,
    SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
    SEED_REPLICATE_LINEAGE_KIND,
    SHUFFLE_MORPHOLOGY_ABLATION_FAMILY_ID,
    SHUFFLE_SYNAPSE_LOCATIONS_ABLATION_FAMILY_ID,
    SIMULATION_PLAN_ROLE_ID,
    SIMULATION_PLAN_SOURCE_KIND,
    SIMULATOR_RESULT_BUNDLE_ROLE_ID,
    SIMULATOR_RESULT_SOURCE_KIND,
    SOLVER_SETTINGS_DIMENSION_ID,
    SUMMARY_TABLE_ROLE_ID,
    SUITE_MANIFEST_INPUT_ROLE_ID,
    SUITE_MANIFEST_SOURCE_KIND,
    SUPPORTED_DIMENSION_IDS,
    SUPPORTED_WORK_ITEM_STATUSES,
    UPSTREAM_MANIFEST_ARTIFACT_SCOPE,
    UPSTREAM_PLAN_ARTIFACT_SCOPE,
    VALIDATION_BUNDLE_ROLE_ID,
    VALIDATION_BUNDLE_SOURCE_KIND,
    WAVE_KERNEL_DIMENSION_ID,
    WAVES_ONLY_SELECTED_CELL_CLASSES_ABLATION_FAMILY_ID,
    WORK_ITEM_STATUS_PLANNED,
    build_experiment_suite_ablation_reference,
    build_experiment_suite_artifact_reference,
    build_experiment_suite_cell_metadata,
    build_experiment_suite_contract_metadata,
    build_experiment_suite_dimension_assignment,
    build_experiment_suite_metadata,
    build_experiment_suite_work_item,
    get_experiment_suite_ablation_family_definition,
    get_experiment_suite_dimension_definition,
    parse_experiment_suite_contract_metadata,
)
from .simulation_planning import SIMULATION_PLAN_VERSION, resolve_manifest_simulation_plan
from .simulator_result_contract import (
    SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
    SURFACE_WAVE_MODEL_MODE,
)
from .stimulus_contract import (
    ASSET_STATUS_MISSING,
    _normalize_identifier,
    _normalize_json_mapping,
    _normalize_nonempty_string,
    _normalize_positive_int,
)
from .validation_contract import VALIDATION_LADDER_CONTRACT_VERSION


EXPERIMENT_SUITE_PLAN_VERSION = "experiment_suite_plan.v1"
EXPERIMENT_SUITE_CONFIG_VERSION = "experiment_suite_config.v1"
EXPERIMENT_SUITE_MANIFEST_FORMAT = "yaml_experiment_suite_manifest.v1"

STAGE_SIMULATION = "simulation"
STAGE_ANALYSIS = "analysis"
STAGE_VALIDATION = "validation"
STAGE_DASHBOARD = "dashboard"
DEFAULT_STAGE_ORDER = (
    STAGE_SIMULATION,
    STAGE_ANALYSIS,
    STAGE_VALIDATION,
    STAGE_DASHBOARD,
)
SUPPORTED_STAGE_IDS = DEFAULT_STAGE_ORDER

EXPANSION_MODE_CROSS_PRODUCT = "cross_product"
EXPANSION_MODE_LINKED = "linked"
SUPPORTED_EXPANSION_MODES = (
    EXPANSION_MODE_CROSS_PRODUCT,
    EXPANSION_MODE_LINKED,
)

SIMULATION_SEED_SOURCE_MANIFEST_SEED_SWEEP = "manifest_seed_sweep"
SIMULATION_SEED_SOURCE_MANIFEST_RANDOM_SEED = "manifest_random_seed"
SIMULATION_SEED_SOURCE_EXPLICIT = "explicit_values"
SUPPORTED_SIMULATION_SEED_SOURCES = (
    SIMULATION_SEED_SOURCE_MANIFEST_SEED_SWEEP,
    SIMULATION_SEED_SOURCE_MANIFEST_RANDOM_SEED,
    SIMULATION_SEED_SOURCE_EXPLICIT,
)

SEED_REUSE_SHARED_ACROSS_SUITE = "shared_across_suite"
SEED_REUSE_SHARED_WITHIN_BASE_CONDITION = "shared_within_base_condition"
SUPPORTED_SEED_REUSE_SCOPES = (
    SEED_REUSE_SHARED_ACROSS_SUITE,
    SEED_REUSE_SHARED_WITHIN_BASE_CONDITION,
)
DEFAULT_LINEAGE_SEED_STRIDE = 1000

PERTURBATION_SEED_MODE_NONE = "none"
PERTURBATION_SEED_MODE_DERIVED_OFFSET = "derived_offset"
PERTURBATION_SEED_MODE_FIXED_VALUE = "fixed_value"
SUPPORTED_PERTURBATION_SEED_MODES = (
    PERTURBATION_SEED_MODE_NONE,
    PERTURBATION_SEED_MODE_DERIVED_OFFSET,
    PERTURBATION_SEED_MODE_FIXED_VALUE,
)
DEFAULT_PERTURBATION_SEED_OFFSET = 100000
DEFAULT_ABLATION_SEED_STRIDE = 10000

ALLOWED_SUITE_CONFIG_KEYS = {
    "version",
    "enabled_stage_ids",
    "output_root",
    "seed_policy",
}
ALLOWED_SUITE_MANIFEST_KEYS = {
    "format",
    "experiment_manifest",
    "suite_id",
    "suite_label",
    "description",
    "enabled_stage_ids",
    "output_root",
    "dimensions",
    "seed_policy",
    "ablations",
}
ALLOWED_EXPERIMENT_REFERENCE_KEYS = {
    "path",
    "schema_path",
    "design_lock_path",
}
ALLOWED_SUITE_DIMENSIONS_KEYS = {
    "fixed",
    "sweep_axes",
}
ALLOWED_FIXED_DIMENSION_VALUE_KEYS = {
    "dimension_id",
    "value_id",
    "value_label",
    "parameter_snapshot",
    "manifest_overrides",
    "config_overrides",
    "notes",
}
ALLOWED_SWEEP_AXIS_KEYS = {
    "axis_id",
    "expansion_mode",
    "dimensions",
}
ALLOWED_SWEEP_DIMENSION_KEYS = {
    "dimension_id",
    "default_value_id",
    "values",
}
ALLOWED_SEED_POLICY_KEYS = {
    "simulation_seed_source",
    "simulation_seed_values",
    "reuse_scope",
    "lineage_seed_stride",
    "perturbation_seed_mode",
    "perturbation_seed_offset",
    "perturbation_fixed_value",
}
ALLOWED_ABLATION_KEYS = {
    "ablation_family_id",
    "variant_id",
    "display_name",
    "dimension_filters",
    "manifest_overrides",
    "config_overrides",
    "parameter_snapshot",
    "perturbation_seed_policy",
}
ALLOWED_PERTURBATION_POLICY_KEYS = {
    "mode",
    "offset",
    "fixed_value",
}

DEFAULT_SIMULATION_METADATA_FILENAME = "simulator_result_bundle.json"
DEFAULT_ANALYSIS_METADATA_FILENAME = "experiment_analysis_bundle.json"
DEFAULT_VALIDATION_METADATA_FILENAME = "validation_bundle.json"
DEFAULT_DASHBOARD_METADATA_FILENAME = "dashboard_session.json"
DEFAULT_SUITE_PLAN_FILENAME = "experiment_suite_plan.json"
DEFAULT_SUITE_METADATA_FILENAME = "experiment_suite.json"
DEFAULT_BASE_SIMULATION_PLAN_FILENAME = "base_simulation_plan.json"
DEFAULT_PATH_KEY_HASH_LENGTH = 16

ABLATION_VARIANT_IDS_BY_FAMILY = {
    NO_WAVES_ABLATION_FAMILY_ID: {"disabled"},
    WAVES_ONLY_SELECTED_CELL_CLASSES_ABLATION_FAMILY_ID: {"selected_subset_only"},
    NO_LATERAL_COUPLING_ABLATION_FAMILY_ID: {"disabled"},
    SHUFFLE_SYNAPSE_LOCATIONS_ABLATION_FAMILY_ID: {"shuffled"},
    SHUFFLE_MORPHOLOGY_ABLATION_FAMILY_ID: {"shuffled"},
    COARSEN_GEOMETRY_ABLATION_FAMILY_ID: {"coarse"},
    ALTERED_SIGN_ASSUMPTIONS_ABLATION_FAMILY_ID: {"sign_inversion_probe"},
    ALTERED_DELAY_ASSUMPTIONS_ABLATION_FAMILY_ID: {
        "zero_delay_probe",
        "delay_scale_half_probe",
    },
}

SURFACE_WAVE_DEPENDENT_DIMENSION_IDS = {
    WAVE_KERNEL_DIMENSION_ID,
    COUPLING_MODE_DIMENSION_ID,
    MESH_RESOLUTION_DIMENSION_ID,
    SOLVER_SETTINGS_DIMENSION_ID,
    FIDELITY_CLASS_DIMENSION_ID,
}
SURFACE_WAVE_DEPENDENT_ABLATION_IDS = {
    NO_WAVES_ABLATION_FAMILY_ID,
    WAVES_ONLY_SELECTED_CELL_CLASSES_ABLATION_FAMILY_ID,
    NO_LATERAL_COUPLING_ABLATION_FAMILY_ID,
    SHUFFLE_SYNAPSE_LOCATIONS_ABLATION_FAMILY_ID,
    SHUFFLE_MORPHOLOGY_ABLATION_FAMILY_ID,
    COARSEN_GEOMETRY_ABLATION_FAMILY_ID,
    ALTERED_SIGN_ASSUMPTIONS_ABLATION_FAMILY_ID,
    ALTERED_DELAY_ASSUMPTIONS_ABLATION_FAMILY_ID,
}
_MOTION_DIRECTION_KEYS = ("direction_deg", "drift_direction_deg", "rotation_direction")
_MOTION_SPEED_KEYS = (
    "velocity_deg_per_s",
    "speed_deg_per_s",
    "radial_speed_deg_per_s",
    "angular_speed_deg_per_s",
)
_NOISE_KEYS = ("noise_level", "noise_std", "input_noise_std")


def normalize_experiment_suite_config(
    payload: Mapping[str, Any] | None,
    *,
    project_root: Path,
) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError("experiment_suite must be a mapping when provided.")
    unknown_keys = sorted(set(raw_payload) - ALLOWED_SUITE_CONFIG_KEYS)
    if unknown_keys:
        raise ValueError(
            "experiment_suite contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    version = _normalize_nonempty_string(
        raw_payload.get("version", EXPERIMENT_SUITE_CONFIG_VERSION),
        field_name="experiment_suite.version",
    )
    if version != EXPERIMENT_SUITE_CONFIG_VERSION:
        raise ValueError(
            "experiment_suite.version must be "
            f"{EXPERIMENT_SUITE_CONFIG_VERSION!r}."
        )
    return {
        "version": version,
        "enabled_stage_ids": _normalize_stage_ids(
            raw_payload.get("enabled_stage_ids", list(DEFAULT_STAGE_ORDER)),
            field_name="experiment_suite.enabled_stage_ids",
        ),
        "output_root": _resolve_optional_project_path(
            raw_payload.get("output_root"),
            project_root=project_root,
            field_name="experiment_suite.output_root",
        ),
        "seed_policy": _normalize_seed_policy(
            raw_payload.get("seed_policy"),
            field_name="experiment_suite.seed_policy",
            allow_unspecified_simulation_source=True,
        ),
    }


def resolve_experiment_suite_plan(
    *,
    config_path: str | Path,
    manifest_path: str | Path | None = None,
    suite_manifest_path: str | Path | None = None,
    schema_path: str | Path | None = None,
    design_lock_path: str | Path | None = None,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if (manifest_path is None) == (suite_manifest_path is None):
        raise ValueError(
            "resolve_experiment_suite_plan requires exactly one of manifest_path or "
            "suite_manifest_path."
        )

    cfg = load_config(config_path)
    config_file = get_config_path(cfg)
    project_root = get_project_root(cfg)
    if config_file is None or project_root is None:
        raise ValueError("Loaded config is missing config metadata.")

    normalized_suite_config = normalize_experiment_suite_config(
        cfg.get("experiment_suite"),
        project_root=project_root,
    )
    normalized_contract = parse_experiment_suite_contract_metadata(
        contract_metadata
        if contract_metadata is not None
        else build_experiment_suite_contract_metadata()
    )
    source_context = _resolve_suite_source_context(
        manifest_path=manifest_path,
        suite_manifest_path=suite_manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        project_root=project_root,
    )
    normalized_suite_spec = _normalize_suite_spec(
        payload=source_context["suite_payload"],
        field_name=source_context["suite_field_name"],
        project_root=project_root,
        config_defaults=normalized_suite_config,
        source_kind=source_context["source_kind"],
    )
    base_manifest_payload = copy.deepcopy(dict(source_context["base_manifest_payload"]))
    sanitized_manifest_payload = _strip_suite_extension(base_manifest_payload)

    base_simulation_plan = _resolve_base_simulation_plan(
        sanitized_manifest_payload=sanitized_manifest_payload,
        manifest_path=source_context["base_manifest_path"],
        config_path=config_file,
        schema_path=source_context["schema_path"],
        design_lock_path=source_context["design_lock_path"],
    )
    contract_reference = {
        "contract_version": normalized_contract["contract_version"],
        "design_note": normalized_contract["design_note"],
        "design_note_version": normalized_contract["design_note_version"],
        "composed_contracts": list(normalized_contract["composed_contracts"]),
    }
    base_defaults = _derive_base_dimension_defaults(
        manifest_payload=sanitized_manifest_payload,
        cfg=cfg,
        simulation_plan=base_simulation_plan,
    )
    normalized_dimensions = _normalize_dimensions_spec(
        payload=normalized_suite_spec["dimensions"],
        field_name=f"{source_context['suite_field_name']}.dimensions",
        base_defaults=base_defaults,
        contract_metadata=normalized_contract,
    )
    _validate_suite_surface_wave_prerequisites(
        simulation_plan=base_simulation_plan,
        declared_dimension_ids=set(normalized_dimensions["declared_dimension_ids"]),
        ablation_declarations=normalized_suite_spec["ablations"],
    )
    _validate_active_subset_prerequisites(
        dimension_records=normalized_dimensions["dimension_records"],
        cfg=cfg,
    )

    output_roots = _resolve_suite_output_roots(
        cfg=cfg,
        suite_id=normalized_suite_spec["suite_id"],
        output_root_override=normalized_suite_spec["output_root"],
    )
    seed_policy = _resolve_seed_policy(
        suite_seed_policy=normalized_suite_spec["seed_policy"],
        manifest_payload=sanitized_manifest_payload,
    )
    base_conditions = _expand_base_conditions(
        normalized_dimensions=normalized_dimensions,
    )
    _validate_suite_ablation_declarations(
        ablations=normalized_suite_spec["ablations"],
        base_conditions=base_conditions,
        normalized_dimensions=normalized_dimensions,
        seed_policy=seed_policy,
    )
    stage_catalog = _build_stage_catalog(normalized_suite_spec["enabled_stage_ids"])

    detailed_cells, work_items, artifact_references = _build_suite_lineage(
        suite_id=normalized_suite_spec["suite_id"],
        base_conditions=base_conditions,
        ablations=normalized_suite_spec["ablations"],
        base_simulation_plan=base_simulation_plan,
        seed_policy=seed_policy,
        stage_catalog=stage_catalog,
        output_roots=output_roots,
        normalized_contract=normalized_contract,
    )
    upstream_references = _build_upstream_references(
        source_context=source_context,
        output_roots=output_roots,
    )
    suite_metadata = build_experiment_suite_metadata(
        suite_id=normalized_suite_spec["suite_id"],
        suite_label=normalized_suite_spec["suite_label"],
        upstream_references=upstream_references,
        suite_cells=[item["cell_metadata"] for item in detailed_cells],
        work_items=work_items,
        artifact_references=artifact_references,
        contract_metadata=normalized_contract,
    )
    suite_cell_order = [item["suite_cell_id"] for item in suite_metadata["suite_cells"]]
    work_item_order = [item["work_item_id"] for item in suite_metadata["work_items"]]
    artifact_order = [
        (
            item["artifact_role_id"],
            item["suite_cell_id"],
            item["work_item_id"],
            item["path"],
        )
        for item in suite_metadata["artifact_references"]
    ]
    detailed_cells = _sort_detailed_cells_to_metadata(
        detailed_cells,
        suite_cell_order=suite_cell_order,
    )
    detailed_work_items = _build_detailed_work_items(
        detailed_cells=detailed_cells,
        suite_metadata=suite_metadata,
    )
    detailed_artifact_references = _sort_detailed_artifact_references(
        detailed_cells=detailed_cells,
        suite_metadata=suite_metadata,
        artifact_order=artifact_order,
    )
    comparison_pairings = _build_comparison_pairings(
        detailed_cells=detailed_cells,
        base_simulation_plan=base_simulation_plan,
    )

    return {
        "plan_version": EXPERIMENT_SUITE_PLAN_VERSION,
        "contract_reference": contract_reference,
        "suite_source": {
            "source_kind": source_context["source_kind"],
            "suite_manifest_path": (
                None
                if source_context["suite_manifest_path"] is None
                else str(source_context["suite_manifest_path"])
            ),
            "experiment_manifest_path": str(source_context["base_manifest_path"]),
            "schema_path": str(source_context["schema_path"]),
            "design_lock_path": str(source_context["design_lock_path"]),
        },
        "config_reference": {
            "config_path": str(config_file.resolve()),
            "project_root": str(project_root.resolve()),
        },
        "manifest_reference": copy.deepcopy(dict(base_simulation_plan["manifest_reference"])),
        "suite_id": normalized_suite_spec["suite_id"],
        "suite_label": normalized_suite_spec["suite_label"],
        "description": normalized_suite_spec["description"],
        "suite_config": normalized_suite_config,
        "suite_spec": normalized_suite_spec,
        "base_simulation_plan": base_simulation_plan,
        "base_readout_analysis_plan": copy.deepcopy(
            dict(base_simulation_plan["readout_analysis_plan"])
        ),
        "active_dimensions": _build_active_dimensions_catalog(
            normalized_dimensions=normalized_dimensions,
        ),
        "sweep_axes": copy.deepcopy(normalized_dimensions["axes"]),
        "seed_policy": seed_policy,
        "ablation_declarations": copy.deepcopy(normalized_suite_spec["ablations"]),
        "stage_targets": stage_catalog,
        "output_roots": output_roots,
        "stable_suite_cell_ordering": (
            "contract_dimension_order_then_declared_axis_order_then_lineage_sequence"
        ),
        "stable_work_item_ordering": "suite_cell_then_stage_sequence",
        "stable_artifact_reference_ordering": "contract_role_then_suite_cell_then_work_item",
        "comparison_pairings": comparison_pairings,
        "suite_cells": copy.deepcopy(suite_metadata["suite_cells"]),
        "cell_catalog": detailed_cells,
        "work_items": copy.deepcopy(suite_metadata["work_items"]),
        "work_item_catalog": detailed_work_items,
        "planned_artifact_references": copy.deepcopy(suite_metadata["artifact_references"]),
        "artifact_reference_catalog": detailed_artifact_references,
        "upstream_references": copy.deepcopy(suite_metadata["upstream_references"]),
        "suite_metadata": suite_metadata,
    }


def _resolve_suite_source_context(
    *,
    manifest_path: str | Path | None,
    suite_manifest_path: str | Path | None,
    schema_path: str | Path | None,
    design_lock_path: str | Path | None,
    project_root: Path,
) -> dict[str, Any]:
    if suite_manifest_path is not None:
        suite_file = Path(suite_manifest_path).resolve()
        suite_payload = _load_yaml_mapping(
            suite_file,
            field_name="suite_manifest",
        )
        format_version = _normalize_nonempty_string(
            suite_payload.get("format"),
            field_name="suite_manifest.format",
        )
        if format_version != EXPERIMENT_SUITE_MANIFEST_FORMAT:
            raise ValueError(
                "suite_manifest.format must be "
                f"{EXPERIMENT_SUITE_MANIFEST_FORMAT!r}."
            )
        experiment_reference = _require_mapping(
            suite_payload.get("experiment_manifest"),
            field_name="suite_manifest.experiment_manifest",
        )
        unknown_keys = sorted(set(experiment_reference) - ALLOWED_EXPERIMENT_REFERENCE_KEYS)
        if unknown_keys:
            raise ValueError(
                "suite_manifest.experiment_manifest contains unsupported keys: "
                f"{unknown_keys!r}."
            )
        base_manifest_path = _resolve_relative_path(
            experiment_reference.get("path"),
            base_path=suite_file.parent,
            field_name="suite_manifest.experiment_manifest.path",
        )
        resolved_schema_path = _resolve_optional_relative_path(
            experiment_reference.get("schema_path"),
            fallback=schema_path,
            base_path=suite_file.parent,
            field_name="suite_manifest.experiment_manifest.schema_path",
        )
        resolved_design_lock_path = _resolve_optional_relative_path(
            experiment_reference.get("design_lock_path"),
            fallback=design_lock_path,
            base_path=suite_file.parent,
            field_name="suite_manifest.experiment_manifest.design_lock_path",
        )
        base_manifest_payload = _load_yaml_mapping(
            base_manifest_path,
            field_name="suite_manifest.experiment_manifest.path",
        )
        return {
            "source_kind": SUITE_MANIFEST_SOURCE_KIND,
            "suite_manifest_path": suite_file,
            "base_manifest_path": base_manifest_path,
            "schema_path": resolved_schema_path,
            "design_lock_path": resolved_design_lock_path,
            "base_manifest_payload": base_manifest_payload,
            "suite_payload": suite_payload,
            "suite_field_name": "suite_manifest",
        }

    experiment_file = Path(manifest_path).resolve()
    base_manifest_payload = _load_yaml_mapping(
        experiment_file,
        field_name="manifest",
    )
    suite_payload = _require_mapping(
        base_manifest_payload.get("suite"),
        field_name="manifest.suite",
    )
    if schema_path is None or design_lock_path is None:
        raise ValueError(
            "Embedded experiment-manifest suite planning requires schema_path and "
            "design_lock_path."
        )
    del project_root
    return {
        "source_kind": EXPERIMENT_MANIFEST_SOURCE_KIND,
        "suite_manifest_path": None,
        "base_manifest_path": experiment_file,
        "schema_path": Path(schema_path).resolve(),
        "design_lock_path": Path(design_lock_path).resolve(),
        "base_manifest_payload": base_manifest_payload,
        "suite_payload": suite_payload,
        "suite_field_name": "manifest.suite",
    }


def _normalize_suite_spec(
    *,
    payload: Mapping[str, Any],
    field_name: str,
    project_root: Path,
    config_defaults: Mapping[str, Any],
    source_kind: str,
) -> dict[str, Any]:
    raw_payload = dict(payload)
    allowed_keys = set(ALLOWED_SUITE_MANIFEST_KEYS)
    if source_kind == EXPERIMENT_MANIFEST_SOURCE_KIND:
        allowed_keys.discard("format")
        allowed_keys.discard("experiment_manifest")
    unknown_keys = sorted(set(raw_payload) - allowed_keys)
    if unknown_keys:
        raise ValueError(
            f"{field_name} contains unsupported keys: {unknown_keys!r}."
        )
    suite_id = _normalize_identifier(
        raw_payload.get("suite_id"),
        field_name=f"{field_name}.suite_id",
    )
    suite_label = _normalize_nonempty_string(
        raw_payload.get("suite_label"),
        field_name=f"{field_name}.suite_label",
    )
    enabled_stage_ids = (
        config_defaults["enabled_stage_ids"]
        if raw_payload.get("enabled_stage_ids") is None
        else _normalize_stage_ids(
            raw_payload.get("enabled_stage_ids"),
            field_name=f"{field_name}.enabled_stage_ids",
        )
    )
    output_root = (
        config_defaults["output_root"]
        if raw_payload.get("output_root") is None
        else _resolve_optional_project_path(
            raw_payload.get("output_root"),
            project_root=project_root,
            field_name=f"{field_name}.output_root",
        )
    )
    return {
        "suite_id": suite_id,
        "suite_label": suite_label,
        "description": _normalize_optional_nonempty_string(
            raw_payload.get("description"),
            field_name=f"{field_name}.description",
        ),
        "enabled_stage_ids": enabled_stage_ids,
        "output_root": output_root,
        "dimensions": _require_mapping(
            raw_payload.get("dimensions", {}),
            field_name=f"{field_name}.dimensions",
        ),
        "seed_policy": (
            copy.deepcopy(dict(config_defaults["seed_policy"]))
            if raw_payload.get("seed_policy") is None
            else _merge_seed_policy_overrides(
                base_policy=config_defaults["seed_policy"],
                override_policy=_normalize_seed_policy(
                    raw_payload.get("seed_policy"),
                    field_name=f"{field_name}.seed_policy",
                    allow_unspecified_simulation_source=True,
                ),
            )
        ),
        "ablations": _normalize_ablation_declarations(
            raw_payload.get("ablations", []),
            field_name=f"{field_name}.ablations",
        ),
    }


def _normalize_dimensions_spec(
    *,
    payload: Mapping[str, Any],
    field_name: str,
    base_defaults: Mapping[str, Any],
    contract_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    raw_payload = dict(payload)
    unknown_keys = sorted(set(raw_payload) - ALLOWED_SUITE_DIMENSIONS_KEYS)
    if unknown_keys:
        raise ValueError(
            f"{field_name} contains unsupported keys: {unknown_keys!r}."
        )

    fixed_values = _normalize_fixed_dimension_values(
        raw_payload.get("fixed", []),
        field_name=f"{field_name}.fixed",
        base_defaults=base_defaults,
        contract_metadata=contract_metadata,
    )
    axes = _normalize_sweep_axes(
        raw_payload.get("sweep_axes", []),
        field_name=f"{field_name}.sweep_axes",
        base_defaults=base_defaults,
        contract_metadata=contract_metadata,
    )

    declared_dimension_ids = [item["dimension_id"] for item in fixed_values]
    for axis in axes:
        declared_dimension_ids.extend(axis["dimension_ids"])
    duplicate_dimension_ids = sorted(
        {
            dimension_id
            for dimension_id in declared_dimension_ids
            if declared_dimension_ids.count(dimension_id) > 1
        }
    )
    if duplicate_dimension_ids:
        raise ValueError(
            "suite.dimensions declares duplicate dimension ids across fixed values and "
            f"sweep axes: {duplicate_dimension_ids!r}."
        )

    fixed_by_id = {item["dimension_id"]: item for item in fixed_values}
    axis_value_map: dict[str, dict[str, Any]] = {}
    for axis in axes:
        for dimension in axis["dimensions"]:
            axis_value_map[dimension["dimension_id"]] = copy.deepcopy(dict(dimension))

    dimension_records: list[dict[str, Any]] = []
    for dimension_id in SUPPORTED_DIMENSION_IDS:
        base_default = copy.deepcopy(dict(base_defaults[dimension_id]))
        declared_fixed = fixed_by_id.get(dimension_id)
        declared_axis = axis_value_map.get(dimension_id)
        if declared_fixed is not None:
            default_value = copy.deepcopy(dict(declared_fixed))
            default_source = "suite_fixed"
            active_values = [copy.deepcopy(dict(declared_fixed))]
            is_swept = False
            axis_id = None
            expansion_mode = None
        elif declared_axis is not None:
            default_value = next(
                copy.deepcopy(dict(value))
                for value in declared_axis["values"]
                if value["value_id"] == declared_axis["default_value_id"]
            )
            default_source = "suite_axis_default"
            active_values = [copy.deepcopy(dict(item)) for item in declared_axis["values"]]
            is_swept = True
            axis_id = str(declared_axis["axis_id"])
            expansion_mode = str(declared_axis["expansion_mode"])
        else:
            default_value = base_default
            default_source = "base_default"
            active_values = [copy.deepcopy(base_default)]
            is_swept = False
            axis_id = None
            expansion_mode = None

        _validate_dimension_value_effective_change(
            dimension_id=dimension_id,
            base_default=base_default,
            active_values=active_values,
            field_name=f"{field_name}.{dimension_id}",
        )
        dimension_records.append(
            {
                "dimension_id": dimension_id,
                "dimension_group": get_experiment_suite_dimension_definition(
                    dimension_id,
                    record=contract_metadata,
                )["dimension_group"],
                "default_value": default_value,
                "base_default": base_default,
                "default_source": default_source,
                "active_values": active_values,
                "is_swept": is_swept,
                "axis_id": axis_id,
                "expansion_mode": expansion_mode,
                "is_declared": declared_fixed is not None or declared_axis is not None,
            }
        )

    axis_rows = [
        copy.deepcopy(dict(axis))
        for axis in axes
    ]
    return {
        "dimension_records": dimension_records,
        "axes": axis_rows,
        "declared_dimension_ids": [
            item["dimension_id"] for item in dimension_records if item["is_declared"]
        ],
    }


def _normalize_fixed_dimension_values(
    payload: Any,
    *,
    field_name: str,
    base_defaults: Mapping[str, Any],
    contract_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a list when provided.")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        normalized.append(
            _normalize_dimension_value_declaration(
                item,
                field_name=f"{field_name}[{index}]",
                base_defaults=base_defaults,
                contract_metadata=contract_metadata,
            )
        )
    return normalized


def _normalize_sweep_axes(
    payload: Any,
    *,
    field_name: str,
    base_defaults: Mapping[str, Any],
    contract_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a list when provided.")
    normalized: list[dict[str, Any]] = []
    for axis_index, axis in enumerate(payload):
        axis_field_name = f"{field_name}[{axis_index}]"
        axis_mapping = _require_mapping(axis, field_name=axis_field_name)
        unknown_keys = sorted(set(axis_mapping) - ALLOWED_SWEEP_AXIS_KEYS)
        if unknown_keys:
            raise ValueError(
                f"{axis_field_name} contains unsupported keys {unknown_keys!r}."
            )
        expansion_mode = _normalize_identifier(
            axis_mapping.get("expansion_mode"),
            field_name=f"{axis_field_name}.expansion_mode",
        )
        if expansion_mode not in SUPPORTED_EXPANSION_MODES:
            raise ValueError(
                f"{axis_field_name}.expansion_mode must be one of "
                f"{list(SUPPORTED_EXPANSION_MODES)!r}, got {expansion_mode!r}."
            )
        dimension_specs = axis_mapping.get("dimensions")
        if not isinstance(dimension_specs, Sequence) or isinstance(
            dimension_specs,
            (str, bytes),
        ) or not dimension_specs:
            raise ValueError(f"{axis_field_name}.dimensions must be a non-empty list.")

        normalized_dimensions: list[dict[str, Any]] = []
        for dimension_index, dimension in enumerate(dimension_specs):
            dimension_field_name = f"{axis_field_name}.dimensions[{dimension_index}]"
            dimension_mapping = _require_mapping(dimension, field_name=dimension_field_name)
            unknown_dimension_keys = sorted(
                set(dimension_mapping) - ALLOWED_SWEEP_DIMENSION_KEYS
            )
            if unknown_dimension_keys:
                raise ValueError(
                    f"{dimension_field_name} contains unsupported keys "
                    f"{unknown_dimension_keys!r}."
                )
            dimension_id = _normalize_identifier(
                dimension_mapping.get("dimension_id"),
                field_name=f"{dimension_field_name}.dimension_id",
            )
            get_experiment_suite_dimension_definition(
                dimension_id,
                record=contract_metadata,
            )
            values_payload = dimension_mapping.get("values")
            if not isinstance(values_payload, Sequence) or isinstance(
                values_payload,
                (str, bytes),
            ) or not values_payload:
                raise ValueError(f"{dimension_field_name}.values must be a non-empty list.")
            values = [
                _normalize_dimension_value_declaration(
                    dict(value, dimension_id=dimension_id),
                    field_name=f"{dimension_field_name}.values[{value_index}]",
                    base_defaults=base_defaults,
                    contract_metadata=contract_metadata,
                )
                for value_index, value in enumerate(values_payload)
            ]
            value_ids = [item["value_id"] for item in values]
            duplicate_value_ids = sorted(
                {
                    value_id
                    for value_id in value_ids
                    if value_ids.count(value_id) > 1
                }
            )
            if duplicate_value_ids:
                raise ValueError(
                    f"{dimension_field_name}.values contains duplicate value ids "
                    f"{duplicate_value_ids!r}."
                )
            default_value_id = (
                values[0]["value_id"]
                if dimension_mapping.get("default_value_id") is None
                else _normalize_identifier(
                    dimension_mapping.get("default_value_id"),
                    field_name=f"{dimension_field_name}.default_value_id",
                )
            )
            if default_value_id not in {item["value_id"] for item in values}:
                raise ValueError(
                    f"{dimension_field_name}.default_value_id {default_value_id!r} must match "
                    "one of the declared values."
                )
            normalized_dimensions.append(
                {
                    "dimension_id": dimension_id,
                    "axis_id": _normalize_identifier(
                        axis_mapping.get("axis_id"),
                        field_name=f"{axis_field_name}.axis_id",
                    ),
                    "expansion_mode": expansion_mode,
                    "values": values,
                    "default_value_id": default_value_id,
                }
            )

        row_count = _resolve_axis_row_count(
            dimensions=normalized_dimensions,
            expansion_mode=expansion_mode,
            field_name=axis_field_name,
        )
        normalized.append(
            {
                "axis_id": _normalize_identifier(
                    axis_mapping.get("axis_id"),
                    field_name=f"{axis_field_name}.axis_id",
                ),
                "expansion_mode": expansion_mode,
                "dimensions": normalized_dimensions,
                "dimension_ids": [item["dimension_id"] for item in normalized_dimensions],
                "value_row_count": row_count,
                "value_rows": _build_axis_value_rows(
                    axis_id=_normalize_identifier(
                        axis_mapping.get("axis_id"),
                        field_name=f"{axis_field_name}.axis_id",
                    ),
                    dimensions=normalized_dimensions,
                    expansion_mode=expansion_mode,
                ),
            }
        )
    return normalized


def _normalize_ablation_declarations(
    payload: Any,
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a list when provided.")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        declaration_field_name = f"{field_name}[{index}]"
        mapping = _require_mapping(item, field_name=declaration_field_name)
        unknown_keys = sorted(set(mapping) - ALLOWED_ABLATION_KEYS)
        if unknown_keys:
            raise ValueError(
                f"{declaration_field_name} contains unsupported keys {unknown_keys!r}."
            )
        ablation_family_id = _normalize_identifier(
            mapping.get("ablation_family_id"),
            field_name=f"{declaration_field_name}.ablation_family_id",
        )
        family_definition = get_experiment_suite_ablation_family_definition(ablation_family_id)
        variant_id = _normalize_identifier(
            mapping.get("variant_id"),
            field_name=f"{declaration_field_name}.variant_id",
        )
        supported_variants = sorted(
            ABLATION_VARIANT_IDS_BY_FAMILY.get(ablation_family_id, set())
        )
        if supported_variants and variant_id not in set(supported_variants):
            raise ValueError(
                f"{declaration_field_name}.variant_id {variant_id!r} is not supported for "
                f"ablation_family_id {ablation_family_id!r}; supported variants: "
                f"{supported_variants!r}."
            )
        dimension_filters = _normalize_dimension_filters(
            mapping.get("dimension_filters", {}),
            field_name=f"{declaration_field_name}.dimension_filters",
        )
        if (
            ablation_family_id == WAVES_ONLY_SELECTED_CELL_CLASSES_ABLATION_FAMILY_ID
            and not _has_nonempty_collection(
                _normalize_optional_json_mapping(
                    mapping.get("parameter_snapshot"),
                    field_name=f"{declaration_field_name}.parameter_snapshot",
                ).get("target_cell_classes")
            )
        ):
            raise ValueError(
                f"{declaration_field_name} for ablation_family_id "
                f"{ablation_family_id!r} must declare parameter_snapshot.target_cell_classes."
            )
        normalized.append(
            {
                "ablation_family_id": ablation_family_id,
                "variant_id": variant_id,
                "display_name": _normalize_nonempty_string(
                    mapping.get(
                        "display_name",
                        family_definition["display_name"],
                    ),
                    field_name=f"{declaration_field_name}.display_name",
                ),
                "dimension_filters": dimension_filters,
                "manifest_overrides": _normalize_optional_json_mapping(
                    mapping.get("manifest_overrides"),
                    field_name=f"{declaration_field_name}.manifest_overrides",
                ),
                "config_overrides": _normalize_optional_json_mapping(
                    mapping.get("config_overrides"),
                    field_name=f"{declaration_field_name}.config_overrides",
                ),
                "parameter_snapshot": _normalize_optional_json_mapping(
                    mapping.get("parameter_snapshot"),
                    field_name=f"{declaration_field_name}.parameter_snapshot",
                ),
                "perturbation_seed_policy": _normalize_perturbation_seed_policy(
                    mapping.get("perturbation_seed_policy"),
                    field_name=f"{declaration_field_name}.perturbation_seed_policy",
                ),
                "uses_perturbation_seed": bool(
                    family_definition["uses_perturbation_seed"]
                ),
            }
        )
    return normalized


def _resolve_base_simulation_plan(
    *,
    sanitized_manifest_payload: Mapping[str, Any],
    manifest_path: Path,
    config_path: Path,
    schema_path: Path,
    design_lock_path: Path,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_path = Path(tmp_dir_str) / "suite_base_manifest.yaml"
        tmp_path.write_text(
            yaml.safe_dump(dict(sanitized_manifest_payload), sort_keys=False),
            encoding="utf-8",
        )
        resolved = resolve_manifest_simulation_plan(
            manifest_path=tmp_path,
            config_path=config_path,
            schema_path=schema_path,
            design_lock_path=design_lock_path,
        )
    return _rewrite_manifest_reference_paths(
        resolved,
        actual_manifest_path=manifest_path,
    )


def _derive_base_dimension_defaults(
    *,
    manifest_payload: Mapping[str, Any],
    cfg: Mapping[str, Any],
    simulation_plan: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    resolved_stimulus = _require_mapping(
        simulation_plan["arm_plans"][0]["resolved_stimulus"],
        field_name="simulation_plan.arm_plans[0].resolved_stimulus",
    )
    parameter_snapshot = _require_mapping(
        resolved_stimulus["parameter_snapshot"],
        field_name="resolved_stimulus.parameter_snapshot",
    )
    runtime_timebase = _require_mapping(
        simulation_plan["arm_plans"][0]["runtime"]["timebase"],
        field_name="simulation_plan.arm_plans[0].runtime.timebase",
    )
    surface_wave_plan = _first_surface_wave_arm(simulation_plan)

    defaults = {
        SCENE_TYPE_DIMENSION_ID: _build_base_default_dimension_value(
            dimension_id=SCENE_TYPE_DIMENSION_ID,
            value_id=str(resolved_stimulus["stimulus_name"]),
            value_label=str(resolved_stimulus["stimulus_name"]).replace("_", " ").title(),
            parameter_snapshot={
                "stimulus_family": resolved_stimulus["stimulus_family"],
                "stimulus_name": resolved_stimulus["stimulus_name"],
            },
        ),
        MOTION_DIRECTION_DIMENSION_ID: _build_base_default_dimension_value(
            dimension_id=MOTION_DIRECTION_DIMENSION_ID,
            value_id=_value_id_from_parameter(
                _lookup_first(parameter_snapshot, _MOTION_DIRECTION_KEYS, default="default")
            ),
            value_label=str(
                _lookup_first(parameter_snapshot, _MOTION_DIRECTION_KEYS, default="default")
            ),
            parameter_snapshot={
                "motion_direction": _lookup_first(
                    parameter_snapshot,
                    _MOTION_DIRECTION_KEYS,
                    default="default",
                )
            },
        ),
        MOTION_SPEED_DIMENSION_ID: _build_base_default_dimension_value(
            dimension_id=MOTION_SPEED_DIMENSION_ID,
            value_id=_value_id_from_parameter(
                _lookup_first(parameter_snapshot, _MOTION_SPEED_KEYS, default="default")
            ),
            value_label=str(
                _lookup_first(parameter_snapshot, _MOTION_SPEED_KEYS, default="default")
            ),
            parameter_snapshot={
                "motion_speed": _lookup_first(
                    parameter_snapshot,
                    _MOTION_SPEED_KEYS,
                    default="default",
                )
            },
        ),
        CONTRAST_LEVEL_DIMENSION_ID: _build_base_default_dimension_value(
            dimension_id=CONTRAST_LEVEL_DIMENSION_ID,
            value_id=_value_id_from_parameter(parameter_snapshot.get("contrast", "default")),
            value_label=str(parameter_snapshot.get("contrast", "default")),
            parameter_snapshot={"contrast": parameter_snapshot.get("contrast", "default")},
        ),
        NOISE_LEVEL_DIMENSION_ID: _build_base_default_dimension_value(
            dimension_id=NOISE_LEVEL_DIMENSION_ID,
            value_id=_value_id_from_parameter(
                _lookup_first(parameter_snapshot, _NOISE_KEYS, default=0.0)
            ),
            value_label=str(_lookup_first(parameter_snapshot, _NOISE_KEYS, default=0.0)),
            parameter_snapshot={"noise_level": _lookup_first(parameter_snapshot, _NOISE_KEYS, default=0.0)},
        ),
        ACTIVE_SUBSET_DIMENSION_ID: _build_base_default_dimension_value(
            dimension_id=ACTIVE_SUBSET_DIMENSION_ID,
            value_id=_normalize_identifier(
                manifest_payload.get(
                    "subset_name",
                    cfg.get("selection", {}).get("active_preset", "selected_roster"),
                ),
                field_name="base_defaults.active_subset.value_id",
            ),
            value_label=str(
                manifest_payload.get(
                    "subset_name",
                    cfg.get("selection", {}).get("active_preset", "selected_roster"),
                )
            ),
            manifest_overrides={
                "subset_name": manifest_payload.get(
                    "subset_name",
                    cfg.get("selection", {}).get("active_preset", "selected_roster"),
                )
            }
            if manifest_payload.get("subset_name") is not None
            else {},
            parameter_snapshot={
                "subset_name": manifest_payload.get(
                    "subset_name",
                    cfg.get("selection", {}).get("active_preset", "selected_roster"),
                )
            },
        ),
        WAVE_KERNEL_DIMENSION_ID: _build_base_default_dimension_value(
            dimension_id=WAVE_KERNEL_DIMENSION_ID,
            value_id=_normalize_identifier(
                cfg.get("simulation", {})
                .get("surface_wave", {})
                .get("parameter_preset", "not_configured"),
                field_name="base_defaults.wave_kernel.value_id",
            ),
            value_label=str(
                cfg.get("simulation", {})
                .get("surface_wave", {})
                .get("parameter_preset", "not_configured")
            ),
            parameter_snapshot={
                "parameter_preset": cfg.get("simulation", {})
                .get("surface_wave", {})
                .get("parameter_preset", "not_configured")
            },
            config_overrides={
                "simulation": {
                    "surface_wave": {
                        "parameter_preset": cfg.get("simulation", {})
                        .get("surface_wave", {})
                        .get("parameter_preset", "not_configured")
                    }
                }
            }
            if cfg.get("simulation", {}).get("surface_wave") is not None
            else {},
        ),
        COUPLING_MODE_DIMENSION_ID: _build_base_default_dimension_value(
            dimension_id=COUPLING_MODE_DIMENSION_ID,
            value_id=_normalize_identifier(
                cfg.get("meshing", {})
                .get("coupling_assembly", {})
                .get("topology_family", "not_configured"),
                field_name="base_defaults.coupling_mode.value_id",
            ),
            value_label=str(
                cfg.get("meshing", {})
                .get("coupling_assembly", {})
                .get("topology_family", "not_configured")
            ),
            parameter_snapshot={
                "topology_family": cfg.get("meshing", {})
                .get("coupling_assembly", {})
                .get("topology_family", "not_configured")
            },
            config_overrides={
                "meshing": {
                    "coupling_assembly": {
                        "topology_family": cfg.get("meshing", {})
                        .get("coupling_assembly", {})
                        .get("topology_family", "not_configured")
                    }
                }
            }
            if cfg.get("meshing", {}).get("coupling_assembly") is not None
            else {},
        ),
        MESH_RESOLUTION_DIMENSION_ID: _build_base_default_dimension_value(
            dimension_id=MESH_RESOLUTION_DIMENSION_ID,
            value_id="fine",
            value_label="Fine",
            parameter_snapshot={"resolution": "fine"},
        ),
        SOLVER_SETTINGS_DIMENSION_ID: _build_base_default_dimension_value(
            dimension_id=SOLVER_SETTINGS_DIMENSION_ID,
            value_id=_normalize_identifier(
                f"dt_{runtime_timebase['dt_ms']}_ms",
                field_name="base_defaults.solver_settings.value_id",
            ),
            value_label=f"dt {runtime_timebase['dt_ms']} ms",
            parameter_snapshot={
                "dt_ms": runtime_timebase["dt_ms"],
                "duration_ms": runtime_timebase["duration_ms"],
            },
            config_overrides={"simulation": {"timebase": dict(runtime_timebase)}},
        ),
        FIDELITY_CLASS_DIMENSION_ID: _build_base_default_dimension_value(
            dimension_id=FIDELITY_CLASS_DIMENSION_ID,
            value_id=_resolve_fidelity_default_value_id(surface_wave_plan),
            value_label=_resolve_fidelity_default_value_label(surface_wave_plan),
            parameter_snapshot=_resolve_fidelity_default_snapshot(surface_wave_plan),
        ),
    }
    return defaults


def _expand_base_conditions(
    *,
    normalized_dimensions: Mapping[str, Any],
) -> list[dict[str, Any]]:
    axes = list(normalized_dimensions["axes"])
    if not axes:
        axis_combinations = [()]
    else:
        axis_combinations = itertools.product(
            *[axis["value_rows"] for axis in axes]
        )
    dimension_records = {
        item["dimension_id"]: item
        for item in normalized_dimensions["dimension_records"]
    }
    declared_dimension_ids = [
        item["dimension_id"]
        for item in normalized_dimensions["dimension_records"]
        if item["is_declared"]
    ]
    declared_dimension_ids = [
        dimension_id
        for dimension_id in SUPPORTED_DIMENSION_IDS
        if dimension_id in set(declared_dimension_ids)
    ]

    base_conditions: list[dict[str, Any]] = []
    for combination_index, axis_rows in enumerate(axis_combinations):
        selected_values: dict[str, dict[str, Any]] = {}
        for dimension_id, record in dimension_records.items():
            selected_values[dimension_id] = copy.deepcopy(dict(record["default_value"]))
        axis_row_catalog: list[dict[str, Any]] = []
        for axis_row in axis_rows:
            axis_row_catalog.append(copy.deepcopy(dict(axis_row)))
            for assignment in axis_row["assignments"]:
                selected_values[assignment["dimension_id"]] = copy.deepcopy(dict(assignment))

        ordered_assignments = [
            build_experiment_suite_dimension_assignment(
                dimension_id=dimension_id,
                value_id=selected_values[dimension_id]["value_id"],
                value_label=selected_values[dimension_id]["value_label"],
                parameter_snapshot=selected_values[dimension_id]["parameter_snapshot"],
            )
            for dimension_id in SUPPORTED_DIMENSION_IDS
        ]
        manifest_overrides = _merge_dimension_overrides(
            values=selected_values.values(),
            override_key="manifest_overrides",
            field_name="base_condition.manifest_overrides",
        )
        config_overrides = _merge_dimension_overrides(
            values=selected_values.values(),
            override_key="config_overrides",
            field_name="base_condition.config_overrides",
        )
        base_condition_id = _build_base_condition_id(
            declared_dimension_ids=declared_dimension_ids,
            selected_values=selected_values,
            combination_index=combination_index,
        )
        display_name = _build_base_condition_display_name(
            declared_dimension_ids=declared_dimension_ids,
            selected_values=selected_values,
            combination_index=combination_index,
        )
        base_conditions.append(
            {
                "suite_cell_id": base_condition_id,
                "display_name": display_name,
                "lineage_kind": BASE_CONDITION_LINEAGE_KIND,
                "dimension_assignments": ordered_assignments,
                "selected_dimension_values": selected_values,
                "declared_dimension_ids": declared_dimension_ids,
                "axis_rows": axis_row_catalog,
                "manifest_overrides": manifest_overrides,
                "config_overrides": config_overrides,
            }
        )
    return base_conditions


def _resolve_seed_policy(
    *,
    suite_seed_policy: Mapping[str, Any],
    manifest_payload: Mapping[str, Any],
) -> dict[str, Any]:
    simulation_seed_source = suite_seed_policy["simulation_seed_source"]
    if simulation_seed_source is None:
        simulation_seed_source = (
            SIMULATION_SEED_SOURCE_MANIFEST_SEED_SWEEP
            if manifest_payload.get("seed_sweep")
            else SIMULATION_SEED_SOURCE_MANIFEST_RANDOM_SEED
        )
    if simulation_seed_source == SIMULATION_SEED_SOURCE_MANIFEST_SEED_SWEEP:
        seed_values = manifest_payload.get("seed_sweep")
        if not isinstance(seed_values, Sequence) or isinstance(seed_values, (str, bytes)) or not seed_values:
            raise ValueError(
                "suite.seed_policy.simulation_seed_source='manifest_seed_sweep' requires the "
                "base manifest to declare seed_sweep."
            )
        resolved_seed_values = [int(value) for value in seed_values]
    elif simulation_seed_source == SIMULATION_SEED_SOURCE_MANIFEST_RANDOM_SEED:
        resolved_seed_values = [int(manifest_payload["random_seed"])]
    else:
        explicit_values = suite_seed_policy["simulation_seed_values"]
        if not explicit_values:
            raise ValueError(
                "suite.seed_policy.simulation_seed_source='explicit_values' requires "
                "simulation_seed_values."
            )
        resolved_seed_values = [int(value) for value in explicit_values]

    if len(set(resolved_seed_values)) != len(resolved_seed_values):
        raise ValueError("suite.seed_policy resolved duplicate simulation seed values.")
    return {
        "simulation_seed_source": simulation_seed_source,
        "resolved_simulation_seed_values": resolved_seed_values,
        "reuse_scope": suite_seed_policy["reuse_scope"],
        "lineage_seed_stride": suite_seed_policy["lineage_seed_stride"],
        "perturbation_seed_mode": suite_seed_policy["perturbation_seed_mode"],
        "perturbation_seed_offset": suite_seed_policy["perturbation_seed_offset"],
        "perturbation_fixed_value": suite_seed_policy["perturbation_fixed_value"],
    }


def _build_suite_lineage(
    *,
    suite_id: str,
    base_conditions: Sequence[Mapping[str, Any]],
    ablations: Sequence[Mapping[str, Any]],
    base_simulation_plan: Mapping[str, Any],
    seed_policy: Mapping[str, Any],
    stage_catalog: Sequence[Mapping[str, Any]],
    output_roots: Mapping[str, Any],
    normalized_contract: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    del suite_id
    del normalized_contract
    detailed_cells: list[dict[str, Any]] = []
    work_items: list[dict[str, Any]] = []
    artifact_references: list[dict[str, Any]] = []

    base_condition_index_by_id = {
        str(item["suite_cell_id"]): index
        for index, item in enumerate(base_conditions)
    }

    for base_index, base_condition in enumerate(base_conditions):
        base_cell = _build_planned_cell(
            suite_cell_id=str(base_condition["suite_cell_id"]),
            display_name=str(base_condition["display_name"]),
            lineage_kind=BASE_CONDITION_LINEAGE_KIND,
            dimension_assignments=base_condition["dimension_assignments"],
            manifest_overrides=base_condition["manifest_overrides"],
            config_overrides=base_condition["config_overrides"],
            selected_dimension_values=base_condition["selected_dimension_values"],
            output_roots=output_roots,
        )
        detailed_cells.append(base_cell)
        _attach_non_simulation_stage_targets(
            cell_record=base_cell,
            stage_catalog=stage_catalog,
            work_items=work_items,
            artifact_references=artifact_references,
        )

        seed_replicates = _build_seed_replicates(
            parent_cell=base_cell,
            base_condition_index=base_index,
            seed_policy=seed_policy,
            output_roots=output_roots,
        )
        detailed_cells.extend(seed_replicates)
        for seed_cell in seed_replicates:
            _attach_simulation_stage_target(
                cell_record=seed_cell,
                work_items=work_items,
                artifact_references=artifact_references,
                stage_catalog=stage_catalog,
            )

    for ablation_index, declaration in enumerate(ablations):
        matched_base_conditions = [
            item
            for item in detailed_cells
            if item["lineage_kind"] == BASE_CONDITION_LINEAGE_KIND
            and _matches_dimension_filters(
                selected_dimension_values=item["selected_dimension_values"],
                dimension_filters=declaration["dimension_filters"],
            )
        ]
        for base_cell in matched_base_conditions:
            base_condition_index = base_condition_index_by_id[str(base_cell["suite_cell_id"])]
            perturbation_seed_policy = _resolve_ablation_seed_policy(
                global_seed_policy=seed_policy,
                declaration=declaration,
            )
            ablation_cell = _build_ablation_variant_cell(
                parent_cell=base_cell,
                declaration=declaration,
                output_roots=output_roots,
            )
            seed_lookup = {
                int(seed_cell["simulation_seed"]): _resolve_perturbation_seed_value(
                    simulation_seed=int(seed_cell["simulation_seed"]),
                    perturbation_seed_policy=perturbation_seed_policy,
                    ablation_index=ablation_index,
                    base_condition_index=base_condition_index,
                )
                for seed_cell in (
                    item
                    for item in detailed_cells
                    if item["lineage_kind"] == SEED_REPLICATE_LINEAGE_KIND
                    and item["parent_cell_id"] == base_cell["suite_cell_id"]
                )
                if seed_cell.get("simulation_seed") is not None
            }
            ablation_cell["ablation_realization"] = build_experiment_ablation_realization(
                base_cell=base_cell,
                declaration=declaration,
                base_simulation_plan=base_simulation_plan,
                perturbation_seed_by_simulation_seed=(
                    None
                    if not declaration["uses_perturbation_seed"]
                    else seed_lookup
                ),
            )
            detailed_cells.append(ablation_cell)
            _attach_non_simulation_stage_targets(
                cell_record=ablation_cell,
                stage_catalog=stage_catalog,
                work_items=work_items,
                artifact_references=artifact_references,
            )
            for seed_cell in (
                item
                for item in detailed_cells
                if item["lineage_kind"] == SEED_REPLICATE_LINEAGE_KIND
                and item["parent_cell_id"] == base_cell["suite_cell_id"]
            ):
                seeded_ablation = _build_seeded_ablation_variant_cell(
                    ablation_cell=ablation_cell,
                    seed_cell=seed_cell,
                    declaration=declaration,
                    perturbation_seed_policy=perturbation_seed_policy,
                    ablation_index=ablation_index,
                    base_condition_index=base_condition_index,
                    output_roots=output_roots,
                )
                seeded_ablation["ablation_realization"] = (
                    materialize_experiment_ablation_realization_for_seed(
                        _require_mapping(
                            ablation_cell.get("ablation_realization"),
                            field_name="ablation_cell.ablation_realization",
                        ),
                        simulation_seed=int(seed_cell["simulation_seed"]),
                    )
                )
                detailed_cells.append(seeded_ablation)
                _attach_simulation_stage_target(
                    cell_record=seeded_ablation,
                    work_items=work_items,
                    artifact_references=artifact_references,
                    stage_catalog=stage_catalog,
                )

    return detailed_cells, work_items, artifact_references


def _build_upstream_references(
    *,
    source_context: Mapping[str, Any],
    output_roots: Mapping[str, Any],
) -> list[dict[str, Any]]:
    references = [
        build_experiment_suite_artifact_reference(
            artifact_role_id=EXPERIMENT_MANIFEST_INPUT_ROLE_ID,
            source_kind=EXPERIMENT_MANIFEST_SOURCE_KIND,
            path=source_context["base_manifest_path"],
            format="yaml_experiment_manifest.v1",
            artifact_scope=UPSTREAM_MANIFEST_ARTIFACT_SCOPE,
            status="ready",
        ),
        build_experiment_suite_artifact_reference(
            artifact_role_id=SIMULATION_PLAN_ROLE_ID,
            source_kind=SIMULATION_PLAN_SOURCE_KIND,
            path=Path(output_roots["upstream_root"]) / DEFAULT_BASE_SIMULATION_PLAN_FILENAME,
            contract_version=SIMULATION_PLAN_VERSION,
            artifact_id="base_simulation_plan",
            format="json_simulation_plan.v1",
            artifact_scope=UPSTREAM_PLAN_ARTIFACT_SCOPE,
            status=ASSET_STATUS_MISSING,
        ),
    ]
    if source_context["suite_manifest_path"] is not None:
        references.append(
            build_experiment_suite_artifact_reference(
                artifact_role_id=SUITE_MANIFEST_INPUT_ROLE_ID,
                source_kind=SUITE_MANIFEST_SOURCE_KIND,
                path=source_context["suite_manifest_path"],
                format=EXPERIMENT_SUITE_MANIFEST_FORMAT,
                artifact_scope=UPSTREAM_MANIFEST_ARTIFACT_SCOPE,
                status="ready",
            )
        )
    else:
        references.append(
            build_experiment_suite_artifact_reference(
                artifact_role_id=SUITE_MANIFEST_INPUT_ROLE_ID,
                source_kind=SUITE_MANIFEST_SOURCE_KIND,
                path=source_context["base_manifest_path"],
                format="yaml_experiment_manifest_suite_extension.v1",
                artifact_scope=UPSTREAM_MANIFEST_ARTIFACT_SCOPE,
                status="ready",
            )
        )
    return references


def _build_active_dimensions_catalog(
    *,
    normalized_dimensions: Mapping[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in normalized_dimensions["dimension_records"]:
        records.append(
            {
                "dimension_id": item["dimension_id"],
                "dimension_group": item["dimension_group"],
                "is_declared": bool(item["is_declared"]),
                "is_swept": bool(item["is_swept"]),
                "axis_id": item["axis_id"],
                "expansion_mode": item["expansion_mode"],
                "default_source": item["default_source"],
                "default_value": copy.deepcopy(dict(item["default_value"])),
                "base_default": copy.deepcopy(dict(item["base_default"])),
                "active_value_ids": [value["value_id"] for value in item["active_values"]],
            }
        )
    return records


def _build_comparison_pairings(
    *,
    detailed_cells: Sequence[Mapping[str, Any]],
    base_simulation_plan: Mapping[str, Any],
) -> dict[str, Any]:
    seed_cells_by_parent: dict[str, list[dict[str, Any]]] = {}
    seeded_ablation_by_parent_and_seed: dict[tuple[str, int], list[dict[str, Any]]] = {}
    ablation_cells: list[dict[str, Any]] = []
    base_cells: list[dict[str, Any]] = []
    pairings: list[dict[str, Any]] = []

    for item in detailed_cells:
        lineage_kind = str(item["lineage_kind"])
        if lineage_kind == BASE_CONDITION_LINEAGE_KIND:
            base_cells.append(copy.deepcopy(dict(item)))
        elif lineage_kind == SEED_REPLICATE_LINEAGE_KIND:
            seed_cells_by_parent.setdefault(str(item["parent_cell_id"]), []).append(
                copy.deepcopy(dict(item))
            )
        elif lineage_kind == ABLATION_VARIANT_LINEAGE_KIND:
            ablation_cells.append(copy.deepcopy(dict(item)))
        elif lineage_kind == SEEDED_ABLATION_VARIANT_LINEAGE_KIND:
            seeded_ablation_by_parent_and_seed.setdefault(
                (str(item["parent_cell_id"]), int(item["simulation_seed"])),
                [],
            ).append(copy.deepcopy(dict(item)))

    for base_cell in sorted(base_cells, key=lambda item: str(item["suite_cell_id"])):
        base_id = str(base_cell["suite_cell_id"])
        pairings.append(
            {
                "pairing_id": f"{base_id}__seed_rollup",
                "pairing_kind": "seed_rollup",
                "base_suite_cell_id": base_id,
                "replicate_suite_cell_ids": [
                    item["suite_cell_id"]
                    for item in sorted(
                        seed_cells_by_parent.get(base_id, []),
                        key=lambda item: int(item["simulation_seed"]),
                    )
                ],
            }
        )

    for ablation_cell in sorted(ablation_cells, key=lambda item: str(item["suite_cell_id"])):
        base_id = str(ablation_cell["parent_cell_id"])
        ablation_id = str(ablation_cell["suite_cell_id"])
        pairings.append(
            {
                "pairing_id": f"{base_id}__vs__{ablation_id}",
                "pairing_kind": "ablation_vs_base",
                "base_suite_cell_id": base_id,
                "ablation_suite_cell_id": ablation_id,
                "ablation_family_ids": [
                    item["ablation_family_id"]
                    for item in ablation_cell["ablation_references"]
                ],
            }
        )
        for base_seed in sorted(
            seed_cells_by_parent.get(base_id, []),
            key=lambda item: int(item["simulation_seed"]),
        ):
            matched = seeded_ablation_by_parent_and_seed.get(
                (ablation_id, int(base_seed["simulation_seed"])),
                [],
            )
            for seeded_ablation in matched:
                pairings.append(
                    {
                        "pairing_id": (
                            f"{base_seed['suite_cell_id']}__vs__{seeded_ablation['suite_cell_id']}"
                        ),
                        "pairing_kind": "seed_matched_ablation_vs_base",
                        "base_suite_cell_id": str(base_seed["suite_cell_id"]),
                        "ablation_suite_cell_id": str(seeded_ablation["suite_cell_id"]),
                        "shared_simulation_seed": int(base_seed["simulation_seed"]),
                    }
                )

    return {
        "experiment_arm_pair_catalog": copy.deepcopy(
            base_simulation_plan["readout_analysis_plan"]["arm_pair_catalog"]
        ),
        "experiment_comparison_group_catalog": copy.deepcopy(
            base_simulation_plan["readout_analysis_plan"]["comparison_group_catalog"]
        ),
        "suite_cell_pairings": pairings,
    }


def _build_stage_catalog(enabled_stage_ids: Sequence[str]) -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    role_by_stage = {
        STAGE_SIMULATION: SIMULATOR_RESULT_BUNDLE_ROLE_ID,
        STAGE_ANALYSIS: EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
        STAGE_VALIDATION: VALIDATION_BUNDLE_ROLE_ID,
        STAGE_DASHBOARD: DASHBOARD_SESSION_ROLE_ID,
    }
    filename_by_stage = {
        STAGE_SIMULATION: DEFAULT_SIMULATION_METADATA_FILENAME,
        STAGE_ANALYSIS: DEFAULT_ANALYSIS_METADATA_FILENAME,
        STAGE_VALIDATION: DEFAULT_VALIDATION_METADATA_FILENAME,
        STAGE_DASHBOARD: DEFAULT_DASHBOARD_METADATA_FILENAME,
    }
    lineage_by_stage = {
        STAGE_SIMULATION: [SEED_REPLICATE_LINEAGE_KIND, SEEDED_ABLATION_VARIANT_LINEAGE_KIND],
        STAGE_ANALYSIS: [BASE_CONDITION_LINEAGE_KIND, ABLATION_VARIANT_LINEAGE_KIND],
        STAGE_VALIDATION: [BASE_CONDITION_LINEAGE_KIND, ABLATION_VARIANT_LINEAGE_KIND],
        STAGE_DASHBOARD: [BASE_CONDITION_LINEAGE_KIND, ABLATION_VARIANT_LINEAGE_KIND],
    }
    for stage_id in DEFAULT_STAGE_ORDER:
        if stage_id not in set(enabled_stage_ids):
            continue
        catalog.append(
            {
                "stage_id": stage_id,
                "artifact_role_id": role_by_stage[stage_id],
                "default_metadata_filename": filename_by_stage[stage_id],
                "target_lineage_kinds": list(lineage_by_stage[stage_id]),
            }
        )
    return catalog


def _resolve_suite_output_roots(
    *,
    cfg: Mapping[str, Any],
    suite_id: str,
    output_root_override: str | None,
) -> dict[str, Any]:
    base_root = (
        Path(output_root_override).resolve()
        if output_root_override is not None
        else Path(
            cfg["paths"].get(
                "processed_experiment_suites_dir",
                Path(cfg["paths"]["processed_simulator_results_dir"]).resolve()
                / "experiment_suites",
            )
        ).resolve()
        / suite_id
    )
    suite_root = base_root.resolve()
    return {
        "suite_root": str(suite_root),
        "cells_root": str((suite_root / "cells").resolve()),
        "upstream_root": str((suite_root / "upstream").resolve()),
        "suite_plan_path": str((suite_root / DEFAULT_SUITE_PLAN_FILENAME).resolve()),
        "suite_metadata_path": str((suite_root / DEFAULT_SUITE_METADATA_FILENAME).resolve()),
    }


def _validate_suite_surface_wave_prerequisites(
    *,
    simulation_plan: Mapping[str, Any],
    declared_dimension_ids: set[str],
    ablation_declarations: Sequence[Mapping[str, Any]],
) -> None:
    has_surface_wave_arm = _first_surface_wave_arm(simulation_plan) is not None
    required_dimensions = sorted(
        declared_dimension_ids & SURFACE_WAVE_DEPENDENT_DIMENSION_IDS
    )
    required_ablations = sorted(
        {
            item["ablation_family_id"]
            for item in ablation_declarations
            if item["ablation_family_id"] in SURFACE_WAVE_DEPENDENT_ABLATION_IDS
        }
    )
    if not has_surface_wave_arm and (required_dimensions or required_ablations):
        raise ValueError(
            "Suite planning requested surface-wave-dependent dimensions or ablations "
            f"{required_dimensions + required_ablations!r}, but the base manifest defines no "
            "surface_wave comparison arm."
        )


def _validate_active_subset_prerequisites(
    *,
    dimension_records: Sequence[Mapping[str, Any]],
    cfg: Mapping[str, Any],
) -> None:
    subset_output_dir = Path(cfg["paths"]["subset_output_dir"]).resolve()
    active_subset_record = next(
        item for item in dimension_records if item["dimension_id"] == ACTIVE_SUBSET_DIMENSION_ID
    )
    for value in active_subset_record["active_values"]:
        subset_name = value["manifest_overrides"].get("subset_name")
        if subset_name is None:
            subset_name = value["parameter_snapshot"].get("subset_name")
        if subset_name is None:
            subset_name = value["value_id"]
        safe_subset_name = str(
            _normalize_identifier(
                subset_name,
                field_name="active_subset.value_id",
            )
        )
        subset_manifest_path = (
            subset_output_dir / safe_subset_name / "subset_manifest.json"
        ).resolve()
        if not subset_manifest_path.exists():
            raise ValueError(
                f"active_subset value {value['value_id']!r} requires a local subset manifest at "
                f"{subset_manifest_path}, but it does not exist."
            )


def _validate_suite_ablation_declarations(
    *,
    ablations: Sequence[Mapping[str, Any]],
    base_conditions: Sequence[Mapping[str, Any]],
    normalized_dimensions: Mapping[str, Any],
    seed_policy: Mapping[str, Any],
) -> None:
    active_dimension_ids = {
        item["dimension_id"]
        for item in normalized_dimensions["dimension_records"]
        if item["is_declared"]
    }
    if (
        MESH_RESOLUTION_DIMENSION_ID in active_dimension_ids
        and len(
            next(
                item["active_values"]
                for item in normalized_dimensions["dimension_records"]
                if item["dimension_id"] == MESH_RESOLUTION_DIMENSION_ID
            )
        )
        > 1
        and any(
            item["ablation_family_id"] == COARSEN_GEOMETRY_ABLATION_FAMILY_ID
            for item in ablations
        )
    ):
        raise ValueError(
            "Declaring both a swept mesh_resolution dimension and the coarsen_geometry "
            "ablation would make geometry comparisons scientifically misleading."
        )

    for declaration in ablations:
        matched = [
            item
            for item in base_conditions
            if _matches_dimension_filters(
                selected_dimension_values=item["selected_dimension_values"],
                dimension_filters=declaration["dimension_filters"],
            )
        ]
        if not matched:
            raise ValueError(
                "Ablation declaration "
                f"{declaration['ablation_family_id']!r}/{declaration['variant_id']!r} does not "
                "match any base condition after suite expansion."
            )
        if declaration["uses_perturbation_seed"]:
            resolved_policy = _resolve_ablation_seed_policy(
                global_seed_policy=seed_policy,
                declaration=declaration,
            )
            if resolved_policy["mode"] == PERTURBATION_SEED_MODE_NONE:
                raise ValueError(
                    "suite.seed_policy.perturbation_seed_mode='none' cannot be used because "
                    f"ablation_family_id {declaration['ablation_family_id']!r} requires "
                    "separate perturbation seeds."
                )
        elif declaration["perturbation_seed_policy"] is not None:
            raise ValueError(
                "Ablation declaration "
                f"{declaration['ablation_family_id']!r} does not use perturbation seeds, "
                "so perturbation_seed_policy must be omitted."
            )


def _validate_dimension_value_effective_change(
    *,
    dimension_id: str,
    base_default: Mapping[str, Any],
    active_values: Sequence[Mapping[str, Any]],
    field_name: str,
) -> None:
    for value in active_values:
        differs_from_base = value["value_id"] != base_default["value_id"]
        has_effect = bool(value["manifest_overrides"]) or bool(value["config_overrides"]) or bool(
            value["parameter_snapshot"]
        )
        if differs_from_base and not has_effect:
            raise ValueError(
                f"{field_name} declares value_id {value['value_id']!r} for dimension "
                f"{dimension_id!r}, but it provides no manifest_overrides, config_overrides, "
                "or parameter_snapshot to explain the change."
            )


def _normalize_dimension_value_declaration(
    payload: Mapping[str, Any],
    *,
    field_name: str,
    base_defaults: Mapping[str, Any],
    contract_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    mapping = _require_mapping(payload, field_name=field_name)
    unknown_keys = sorted(set(mapping) - ALLOWED_FIXED_DIMENSION_VALUE_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name} contains unsupported keys {unknown_keys!r}.")
    dimension_id = _normalize_identifier(
        mapping.get("dimension_id"),
        field_name=f"{field_name}.dimension_id",
    )
    try:
        get_experiment_suite_dimension_definition(dimension_id, record=contract_metadata)
    except KeyError as exc:
        raise ValueError(
            f"{field_name}.dimension_id references unknown dimension id "
            f"{dimension_id!r}."
        ) from exc
    value_id = _normalize_identifier(
        mapping.get("value_id"),
        field_name=f"{field_name}.value_id",
    )
    return {
        "dimension_id": dimension_id,
        "value_id": value_id,
        "value_label": _normalize_nonempty_string(
            mapping.get("value_label", value_id.replace("_", " ").title()),
            field_name=f"{field_name}.value_label",
        ),
        "parameter_snapshot": _normalize_optional_json_mapping(
            mapping.get("parameter_snapshot"),
            field_name=f"{field_name}.parameter_snapshot",
        ),
        "manifest_overrides": _normalize_optional_json_mapping(
            mapping.get("manifest_overrides"),
            field_name=f"{field_name}.manifest_overrides",
        ),
        "config_overrides": _normalize_optional_json_mapping(
            mapping.get("config_overrides"),
            field_name=f"{field_name}.config_overrides",
        ),
        "notes": _normalize_optional_nonempty_string(
            mapping.get("notes"),
            field_name=f"{field_name}.notes",
        ),
        "base_default_value_id": base_defaults[dimension_id]["value_id"],
    }


def _normalize_seed_policy(
    payload: Any,
    *,
    field_name: str,
    allow_unspecified_simulation_source: bool,
) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping when provided.")
    unknown_keys = sorted(set(raw_payload) - ALLOWED_SEED_POLICY_KEYS)
    if unknown_keys:
        raise ValueError(
            f"{field_name} contains unsupported keys {unknown_keys!r}."
        )
    simulation_seed_source = raw_payload.get("simulation_seed_source")
    normalized_seed_source = (
        None
        if simulation_seed_source is None and allow_unspecified_simulation_source
        else _normalize_identifier(
            simulation_seed_source,
            field_name=f"{field_name}.simulation_seed_source",
        )
    )
    if normalized_seed_source is not None and normalized_seed_source not in set(
        SUPPORTED_SIMULATION_SEED_SOURCES
    ):
        raise ValueError(
            f"{field_name}.simulation_seed_source must be one of "
            f"{list(SUPPORTED_SIMULATION_SEED_SOURCES)!r}, got {normalized_seed_source!r}."
        )
    simulation_seed_values = raw_payload.get("simulation_seed_values")
    normalized_seed_values: list[int] | None = None
    if simulation_seed_values is not None:
        if not isinstance(simulation_seed_values, Sequence) or isinstance(
            simulation_seed_values,
            (str, bytes),
        ) or not simulation_seed_values:
            raise ValueError(
                f"{field_name}.simulation_seed_values must be a non-empty list when provided."
            )
        normalized_seed_values = [int(value) for value in simulation_seed_values]
    reuse_scope = _normalize_identifier(
        raw_payload.get("reuse_scope", SEED_REUSE_SHARED_ACROSS_SUITE),
        field_name=f"{field_name}.reuse_scope",
    )
    if reuse_scope not in set(SUPPORTED_SEED_REUSE_SCOPES):
        raise ValueError(
            f"{field_name}.reuse_scope must be one of {list(SUPPORTED_SEED_REUSE_SCOPES)!r}, "
            f"got {reuse_scope!r}."
        )
    lineage_seed_stride = int(
        raw_payload.get("lineage_seed_stride", DEFAULT_LINEAGE_SEED_STRIDE)
    )
    if lineage_seed_stride < 1:
        raise ValueError(f"{field_name}.lineage_seed_stride must be positive.")
    perturbation_seed_mode = _normalize_identifier(
        raw_payload.get("perturbation_seed_mode", PERTURBATION_SEED_MODE_DERIVED_OFFSET),
        field_name=f"{field_name}.perturbation_seed_mode",
    )
    if perturbation_seed_mode not in set(SUPPORTED_PERTURBATION_SEED_MODES):
        raise ValueError(
            f"{field_name}.perturbation_seed_mode must be one of "
            f"{list(SUPPORTED_PERTURBATION_SEED_MODES)!r}, got {perturbation_seed_mode!r}."
        )
    perturbation_seed_offset = int(
        raw_payload.get("perturbation_seed_offset", DEFAULT_PERTURBATION_SEED_OFFSET)
    )
    if perturbation_seed_offset < 0:
        raise ValueError(f"{field_name}.perturbation_seed_offset must be non-negative.")
    perturbation_fixed_value = raw_payload.get("perturbation_fixed_value")
    if perturbation_seed_mode == PERTURBATION_SEED_MODE_FIXED_VALUE:
        if perturbation_fixed_value is None:
            raise ValueError(
                f"{field_name}.perturbation_fixed_value is required when "
                "perturbation_seed_mode='fixed_value'."
            )
        perturbation_fixed_value = int(perturbation_fixed_value)
        if perturbation_fixed_value < 0:
            raise ValueError(f"{field_name}.perturbation_fixed_value must be non-negative.")
    elif perturbation_fixed_value is not None:
        raise ValueError(
            f"{field_name}.perturbation_fixed_value may only be provided when "
            "perturbation_seed_mode='fixed_value'."
        )
    return {
        "simulation_seed_source": normalized_seed_source,
        "simulation_seed_values": normalized_seed_values,
        "reuse_scope": reuse_scope,
        "lineage_seed_stride": lineage_seed_stride,
        "perturbation_seed_mode": perturbation_seed_mode,
        "perturbation_seed_offset": perturbation_seed_offset,
        "perturbation_fixed_value": perturbation_fixed_value,
    }


def _normalize_perturbation_seed_policy(
    payload: Any,
    *,
    field_name: str,
) -> dict[str, Any] | None:
    if payload is None:
        return None
    mapping = _require_mapping(payload, field_name=field_name)
    unknown_keys = sorted(set(mapping) - ALLOWED_PERTURBATION_POLICY_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name} contains unsupported keys {unknown_keys!r}.")
    mode = _normalize_identifier(mapping.get("mode"), field_name=f"{field_name}.mode")
    if mode not in set(SUPPORTED_PERTURBATION_SEED_MODES):
        raise ValueError(
            f"{field_name}.mode must be one of {list(SUPPORTED_PERTURBATION_SEED_MODES)!r}, "
            f"got {mode!r}."
        )
    offset = mapping.get("offset")
    fixed_value = mapping.get("fixed_value")
    if mode == PERTURBATION_SEED_MODE_DERIVED_OFFSET:
        if fixed_value is not None:
            raise ValueError(
                f"{field_name}.fixed_value may not be provided when mode='derived_offset'."
            )
        normalized_offset = (
            DEFAULT_PERTURBATION_SEED_OFFSET if offset is None else int(offset)
        )
        if normalized_offset < 0:
            raise ValueError(f"{field_name}.offset must be non-negative.")
        return {
            "mode": mode,
            "offset": normalized_offset,
            "fixed_value": None,
        }
    if mode == PERTURBATION_SEED_MODE_FIXED_VALUE:
        if offset is not None:
            raise ValueError(
                f"{field_name}.offset may not be provided when mode='fixed_value'."
            )
        if fixed_value is None:
            raise ValueError(f"{field_name}.fixed_value is required when mode='fixed_value'.")
        normalized_fixed_value = int(fixed_value)
        if normalized_fixed_value < 0:
            raise ValueError(f"{field_name}.fixed_value must be non-negative.")
        return {
            "mode": mode,
            "offset": None,
            "fixed_value": normalized_fixed_value,
        }
    if offset is not None or fixed_value is not None:
        raise ValueError(
            f"{field_name}.offset and fixed_value must be omitted when mode='none'."
        )
    return {
        "mode": mode,
        "offset": None,
        "fixed_value": None,
    }


def _resolve_ablation_seed_policy(
    *,
    global_seed_policy: Mapping[str, Any],
    declaration: Mapping[str, Any],
) -> dict[str, Any]:
    local_policy = declaration["perturbation_seed_policy"]
    if local_policy is None:
        return {
            "mode": global_seed_policy["perturbation_seed_mode"],
            "offset": global_seed_policy["perturbation_seed_offset"],
            "fixed_value": global_seed_policy["perturbation_fixed_value"],
        }
    return copy.deepcopy(dict(local_policy))


def _merge_seed_policy_overrides(
    *,
    base_policy: Mapping[str, Any],
    override_policy: Mapping[str, Any],
) -> dict[str, Any]:
    merged = copy.deepcopy(dict(base_policy))
    for key, value in override_policy.items():
        if value is not None:
            merged[key] = copy.deepcopy(value)
    return merged


def _normalize_dimension_filters(
    payload: Any,
    *,
    field_name: str,
) -> dict[str, list[str]]:
    mapping = _require_mapping(payload, field_name=field_name)
    normalized: dict[str, list[str]] = {}
    for raw_dimension_id, raw_values in sorted(mapping.items(), key=lambda item: str(item[0])):
        dimension_id = _normalize_identifier(
            raw_dimension_id,
            field_name=f"{field_name}.{raw_dimension_id}",
        )
        if dimension_id not in set(SUPPORTED_DIMENSION_IDS):
            raise ValueError(
                f"{field_name} references unknown dimension id {dimension_id!r}."
            )
        if not isinstance(raw_values, Sequence) or isinstance(raw_values, (str, bytes)) or not raw_values:
            raise ValueError(
                f"{field_name}.{dimension_id} must be a non-empty list of value ids."
            )
        value_ids = [
            _normalize_identifier(
                value,
                field_name=f"{field_name}.{dimension_id}[{index}]",
            )
            for index, value in enumerate(raw_values)
        ]
        normalized[dimension_id] = value_ids
    return normalized


def _build_base_default_dimension_value(
    *,
    dimension_id: str,
    value_id: Any,
    value_label: Any,
    parameter_snapshot: Mapping[str, Any] | None = None,
    manifest_overrides: Mapping[str, Any] | None = None,
    config_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "dimension_id": dimension_id,
        "value_id": _normalize_identifier(
            value_id,
            field_name=f"base_defaults.{dimension_id}.value_id",
        ),
        "value_label": _normalize_nonempty_string(
            value_label,
            field_name=f"base_defaults.{dimension_id}.value_label",
        ),
        "parameter_snapshot": _normalize_optional_json_mapping(
            parameter_snapshot,
            field_name=f"base_defaults.{dimension_id}.parameter_snapshot",
        ),
        "manifest_overrides": _normalize_optional_json_mapping(
            manifest_overrides,
            field_name=f"base_defaults.{dimension_id}.manifest_overrides",
        ),
        "config_overrides": _normalize_optional_json_mapping(
            config_overrides,
            field_name=f"base_defaults.{dimension_id}.config_overrides",
        ),
        "notes": None,
    }


def _build_axis_value_rows(
    *,
    axis_id: str,
    dimensions: Sequence[Mapping[str, Any]],
    expansion_mode: str,
) -> list[dict[str, Any]]:
    if expansion_mode == EXPANSION_MODE_LINKED:
        row_count = len(dimensions[0]["values"])
        rows = []
        for row_index in range(row_count):
            assignments = [
                copy.deepcopy(dict(dimension["values"][row_index]))
                for dimension in dimensions
            ]
            rows.append(
                {
                    "axis_id": axis_id,
                    "row_index": row_index,
                    "assignments": assignments,
                }
            )
        return rows

    value_product = itertools.product(
        *[dimension["values"] for dimension in dimensions]
    )
    rows: list[dict[str, Any]] = []
    for row_index, combo in enumerate(value_product):
        rows.append(
            {
                "axis_id": axis_id,
                "row_index": row_index,
                "assignments": [copy.deepcopy(dict(item)) for item in combo],
            }
        )
    return rows


def _resolve_axis_row_count(
    *,
    dimensions: Sequence[Mapping[str, Any]],
    expansion_mode: str,
    field_name: str,
) -> int:
    if expansion_mode == EXPANSION_MODE_LINKED:
        counts = {item["dimension_id"]: len(item["values"]) for item in dimensions}
        unique_counts = sorted(set(counts.values()))
        if len(unique_counts) != 1:
            raise ValueError(
                f"{field_name} uses linked expansion but dimension value counts differ: "
                f"{counts!r}."
            )
        return unique_counts[0]
    row_count = 1
    for item in dimensions:
        row_count *= len(item["values"])
    return row_count


def _merge_dimension_overrides(
    *,
    values: Sequence[Mapping[str, Any]],
    override_key: str,
    field_name: str,
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for value in values:
        merged = _merge_patch_mappings(
            merged,
            value[override_key],
            field_name=field_name,
        )
    return merged


def _merge_patch_mappings(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    field_name: str,
) -> dict[str, Any]:
    merged = copy.deepcopy(dict(left))
    for key, value in right.items():
        if key not in merged:
            merged[key] = copy.deepcopy(value)
            continue
        left_value = merged[key]
        if isinstance(left_value, Mapping) and isinstance(value, Mapping):
            merged[key] = _merge_patch_mappings(
                left_value,
                value,
                field_name=f"{field_name}.{key}",
            )
            continue
        if left_value != value:
            raise ValueError(
                f"{field_name} contains conflicting overrides for key {key!r}: "
                f"{left_value!r} != {value!r}."
            )
    return merged


def _build_base_condition_id(
    *,
    declared_dimension_ids: Sequence[str],
    selected_values: Mapping[str, Mapping[str, Any]],
    combination_index: int,
) -> str:
    if not declared_dimension_ids:
        return f"base_condition_{combination_index + 1:04d}"
    tokens = [
        f"{dimension_id}_{selected_values[dimension_id]['value_id']}"
        for dimension_id in declared_dimension_ids
    ]
    return _normalize_identifier(
        "__".join(tokens),
        field_name="base_condition.suite_cell_id",
    )


def _build_base_condition_display_name(
    *,
    declared_dimension_ids: Sequence[str],
    selected_values: Mapping[str, Mapping[str, Any]],
    combination_index: int,
) -> str:
    if not declared_dimension_ids:
        return f"Base Condition {combination_index + 1}"
    return " | ".join(
        f"{dimension_id}: {selected_values[dimension_id]['value_label']}"
        for dimension_id in declared_dimension_ids
    )


def _build_planned_cell(
    *,
    suite_cell_id: str,
    display_name: str,
    lineage_kind: str,
    dimension_assignments: Sequence[Mapping[str, Any]],
    manifest_overrides: Mapping[str, Any],
    config_overrides: Mapping[str, Any],
    selected_dimension_values: Mapping[str, Mapping[str, Any]],
    output_roots: Mapping[str, Any],
    parent_cell_id: str | None = None,
    root_cell_id: str | None = None,
    simulation_seed: int | None = None,
    ablation_references: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    cell_metadata = build_experiment_suite_cell_metadata(
        suite_cell_id=suite_cell_id,
        display_name=display_name,
        lineage_kind=lineage_kind,
        parent_cell_id=parent_cell_id,
        root_cell_id=root_cell_id,
        simulation_seed=simulation_seed,
        dimension_assignments=dimension_assignments,
        ablation_references=ablation_references,
    )
    cell_path_key = _build_suite_cell_path_key(cell_metadata["suite_cell_id"])
    cell_root = (Path(output_roots["cells_root"]) / cell_path_key).resolve()
    return {
        "suite_cell_id": cell_metadata["suite_cell_id"],
        "cell_path_key": cell_path_key,
        "display_name": cell_metadata["display_name"],
        "lineage_kind": cell_metadata["lineage_kind"],
        "parent_cell_id": cell_metadata["parent_cell_id"],
        "root_cell_id": cell_metadata["root_cell_id"],
        "simulation_seed": cell_metadata["simulation_seed"],
        "dimension_assignments": copy.deepcopy(cell_metadata["dimension_assignments"]),
        "selected_dimension_values": copy.deepcopy(selected_dimension_values),
        "ablation_references": copy.deepcopy(cell_metadata["ablation_references"]),
        "ablation_realization": None,
        "manifest_overrides": copy.deepcopy(dict(manifest_overrides)),
        "config_overrides": copy.deepcopy(dict(config_overrides)),
        "output_roots": {
            "cell_root": str(cell_root),
            "simulation_root": str((cell_root / STAGE_SIMULATION).resolve()),
            "analysis_root": str((cell_root / STAGE_ANALYSIS).resolve()),
            "validation_root": str((cell_root / STAGE_VALIDATION).resolve()),
            "dashboard_root": str((cell_root / STAGE_DASHBOARD).resolve()),
        },
        "stage_targets": [],
        "cell_metadata": cell_metadata,
    }


def _build_suite_cell_path_key(suite_cell_id: str) -> str:
    digest = hashlib.sha256(str(suite_cell_id).encode("utf-8")).hexdigest()
    return f"cell_{digest[:DEFAULT_PATH_KEY_HASH_LENGTH]}"


def _build_seed_replicates(
    *,
    parent_cell: Mapping[str, Any],
    base_condition_index: int,
    seed_policy: Mapping[str, Any],
    output_roots: Mapping[str, Any],
) -> list[dict[str, Any]]:
    resolved_seeds = list(seed_policy["resolved_simulation_seed_values"])
    if seed_policy["reuse_scope"] == SEED_REUSE_SHARED_WITHIN_BASE_CONDITION:
        seed_offset = base_condition_index * int(seed_policy["lineage_seed_stride"])
        resolved_seeds = [seed + seed_offset for seed in resolved_seeds]
    seed_cells: list[dict[str, Any]] = []
    for seed in resolved_seeds:
        suite_cell_id = _normalize_identifier(
            f"{parent_cell['suite_cell_id']}__seed_{seed}",
            field_name="seed_replicate.suite_cell_id",
        )
        seed_cells.append(
            _build_planned_cell(
                suite_cell_id=suite_cell_id,
                display_name=f"{parent_cell['display_name']} | seed {seed}",
                lineage_kind=SEED_REPLICATE_LINEAGE_KIND,
                parent_cell_id=str(parent_cell["suite_cell_id"]),
                root_cell_id=str(parent_cell["suite_cell_id"]),
                simulation_seed=int(seed),
                dimension_assignments=parent_cell["dimension_assignments"],
                selected_dimension_values=parent_cell["selected_dimension_values"],
                manifest_overrides=parent_cell["manifest_overrides"],
                config_overrides=parent_cell["config_overrides"],
                output_roots=output_roots,
            )
        )
    return seed_cells


def _build_ablation_variant_cell(
    *,
    parent_cell: Mapping[str, Any],
    declaration: Mapping[str, Any],
    output_roots: Mapping[str, Any],
) -> dict[str, Any]:
    suite_cell_id = _normalize_identifier(
        f"{parent_cell['suite_cell_id']}__{declaration['ablation_family_id']}__"
        f"{declaration['variant_id']}",
        field_name="ablation_variant.suite_cell_id",
    )
    manifest_overrides = _merge_patch_mappings(
        parent_cell["manifest_overrides"],
        declaration["manifest_overrides"],
        field_name="ablation_variant.manifest_overrides",
    )
    config_overrides = _merge_patch_mappings(
        parent_cell["config_overrides"],
        declaration["config_overrides"],
        field_name="ablation_variant.config_overrides",
    )
    return _build_planned_cell(
        suite_cell_id=suite_cell_id,
        display_name=f"{parent_cell['display_name']} | {declaration['display_name']}",
        lineage_kind=ABLATION_VARIANT_LINEAGE_KIND,
        parent_cell_id=str(parent_cell["suite_cell_id"]),
        root_cell_id=str(parent_cell["suite_cell_id"]),
        dimension_assignments=parent_cell["dimension_assignments"],
        selected_dimension_values=parent_cell["selected_dimension_values"],
        manifest_overrides=manifest_overrides,
        config_overrides=config_overrides,
        output_roots=output_roots,
        ablation_references=[
            build_experiment_suite_ablation_reference(
                ablation_family_id=declaration["ablation_family_id"],
                variant_id=declaration["variant_id"],
                display_name=declaration["display_name"],
                parameter_snapshot=declaration["parameter_snapshot"],
            )
        ],
    )


def _build_seeded_ablation_variant_cell(
    *,
    ablation_cell: Mapping[str, Any],
    seed_cell: Mapping[str, Any],
    declaration: Mapping[str, Any],
    perturbation_seed_policy: Mapping[str, Any],
    ablation_index: int,
    base_condition_index: int,
    output_roots: Mapping[str, Any],
) -> dict[str, Any]:
    simulation_seed = int(seed_cell["simulation_seed"])
    perturbation_seed = _resolve_perturbation_seed_value(
        simulation_seed=simulation_seed,
        perturbation_seed_policy=perturbation_seed_policy,
        ablation_index=ablation_index,
        base_condition_index=base_condition_index,
    )
    suite_cell_id = _normalize_identifier(
        f"{ablation_cell['suite_cell_id']}__seed_{simulation_seed}",
        field_name="seeded_ablation_variant.suite_cell_id",
    )
    return _build_planned_cell(
        suite_cell_id=suite_cell_id,
        display_name=f"{ablation_cell['display_name']} | seed {simulation_seed}",
        lineage_kind=SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
        parent_cell_id=str(ablation_cell["suite_cell_id"]),
        root_cell_id=str(ablation_cell["root_cell_id"]),
        simulation_seed=simulation_seed,
        dimension_assignments=ablation_cell["dimension_assignments"],
        selected_dimension_values=ablation_cell["selected_dimension_values"],
        manifest_overrides=ablation_cell["manifest_overrides"],
        config_overrides=ablation_cell["config_overrides"],
        output_roots=output_roots,
        ablation_references=[
            build_experiment_suite_ablation_reference(
                ablation_family_id=declaration["ablation_family_id"],
                variant_id=declaration["variant_id"],
                display_name=declaration["display_name"],
                parameter_snapshot=declaration["parameter_snapshot"],
                perturbation_seed=perturbation_seed,
            )
        ],
    )


def _resolve_perturbation_seed_value(
    *,
    simulation_seed: int,
    perturbation_seed_policy: Mapping[str, Any],
    ablation_index: int,
    base_condition_index: int,
) -> int | None:
    mode = str(perturbation_seed_policy["mode"])
    if mode == PERTURBATION_SEED_MODE_NONE:
        return None
    if mode == PERTURBATION_SEED_MODE_FIXED_VALUE:
        return int(perturbation_seed_policy["fixed_value"])
    return int(
        simulation_seed
        + int(perturbation_seed_policy["offset"])
        + (ablation_index * DEFAULT_ABLATION_SEED_STRIDE)
        + (base_condition_index * DEFAULT_LINEAGE_SEED_STRIDE)
    )


def _attach_simulation_stage_target(
    *,
    cell_record: dict[str, Any],
    work_items: list[dict[str, Any]],
    artifact_references: list[dict[str, Any]],
    stage_catalog: Sequence[Mapping[str, Any]],
) -> None:
    simulation_stage = next(
        (item for item in stage_catalog if item["stage_id"] == STAGE_SIMULATION),
        None,
    )
    if simulation_stage is None:
        return
    work_item = build_experiment_suite_work_item(
        work_item_id=f"{cell_record['suite_cell_id']}__{STAGE_SIMULATION}",
        suite_cell_id=cell_record["suite_cell_id"],
        stage_id=STAGE_SIMULATION,
        status=WORK_ITEM_STATUS_PLANNED,
        artifact_role_ids=[SIMULATOR_RESULT_BUNDLE_ROLE_ID],
    )
    work_items.append(work_item)
    metadata_path = Path(cell_record["output_roots"]["simulation_root"]) / DEFAULT_SIMULATION_METADATA_FILENAME
    artifact_references.append(
        build_experiment_suite_artifact_reference(
            artifact_role_id=SIMULATOR_RESULT_BUNDLE_ROLE_ID,
            source_kind=SIMULATOR_RESULT_SOURCE_KIND,
            path=metadata_path,
            contract_version=SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
            artifact_id="metadata_json",
            format="json_simulator_result_bundle_metadata.v1",
            suite_cell_id=cell_record["suite_cell_id"],
            work_item_id=work_item["work_item_id"],
            status=ASSET_STATUS_MISSING,
        )
    )
    cell_record["stage_targets"].append(
        {
            "stage_id": STAGE_SIMULATION,
            "artifact_role_id": SIMULATOR_RESULT_BUNDLE_ROLE_ID,
            "work_item_id": work_item["work_item_id"],
            "output_root": str(Path(cell_record["output_roots"]["simulation_root"]).resolve()),
            "metadata_path": str(metadata_path.resolve()),
        }
    )


def _attach_non_simulation_stage_targets(
    *,
    cell_record: dict[str, Any],
    stage_catalog: Sequence[Mapping[str, Any]],
    work_items: list[dict[str, Any]],
    artifact_references: list[dict[str, Any]],
) -> None:
    for stage in stage_catalog:
        if stage["stage_id"] == STAGE_SIMULATION:
            continue
        if cell_record["lineage_kind"] not in set(stage["target_lineage_kinds"]):
            continue
        stage_id = str(stage["stage_id"])
        role_id = str(stage["artifact_role_id"])
        work_item = build_experiment_suite_work_item(
            work_item_id=f"{cell_record['suite_cell_id']}__{stage_id}",
            suite_cell_id=cell_record["suite_cell_id"],
            stage_id=stage_id,
            status=WORK_ITEM_STATUS_PLANNED,
            artifact_role_ids=[role_id],
        )
        work_items.append(work_item)
        metadata_path = Path(cell_record["output_roots"][f"{stage_id}_root"]) / str(
            stage["default_metadata_filename"]
        )
        artifact_references.append(
            _build_stage_artifact_reference(
                stage_id=stage_id,
                role_id=role_id,
                metadata_path=metadata_path,
                suite_cell_id=cell_record["suite_cell_id"],
                work_item_id=work_item["work_item_id"],
            )
        )
        cell_record["stage_targets"].append(
            {
                "stage_id": stage_id,
                "artifact_role_id": role_id,
                "work_item_id": work_item["work_item_id"],
                "output_root": str(Path(cell_record["output_roots"][f"{stage_id}_root"]).resolve()),
                "metadata_path": str(metadata_path.resolve()),
            }
        )


def _build_stage_artifact_reference(
    *,
    stage_id: str,
    role_id: str,
    metadata_path: Path,
    suite_cell_id: str,
    work_item_id: str,
) -> dict[str, Any]:
    if stage_id == STAGE_ANALYSIS:
        return build_experiment_suite_artifact_reference(
            artifact_role_id=role_id,
            source_kind=EXPERIMENT_ANALYSIS_SOURCE_KIND,
            path=metadata_path,
            contract_version=EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION,
            artifact_id="metadata_json",
            format="json_experiment_analysis_bundle_metadata.v1",
            suite_cell_id=suite_cell_id,
            work_item_id=work_item_id,
            status=ASSET_STATUS_MISSING,
        )
    if stage_id == STAGE_VALIDATION:
        return build_experiment_suite_artifact_reference(
            artifact_role_id=role_id,
            source_kind=VALIDATION_BUNDLE_SOURCE_KIND,
            path=metadata_path,
            contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
            artifact_id="metadata_json",
            format="json_validation_bundle_metadata.v1",
            suite_cell_id=suite_cell_id,
            work_item_id=work_item_id,
            status=ASSET_STATUS_MISSING,
        )
    if stage_id == STAGE_DASHBOARD:
        return build_experiment_suite_artifact_reference(
            artifact_role_id=role_id,
            source_kind=DASHBOARD_SESSION_SOURCE_KIND,
            path=metadata_path,
            contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            artifact_id="metadata_json",
            format="json_dashboard_session_metadata.v1",
            suite_cell_id=suite_cell_id,
            work_item_id=work_item_id,
            status=ASSET_STATUS_MISSING,
        )
    raise ValueError(f"Unsupported stage_id {stage_id!r} for planned artifact reference.")


def _sort_detailed_cells_to_metadata(
    detailed_cells: Sequence[Mapping[str, Any]],
    *,
    suite_cell_order: Sequence[str],
) -> list[dict[str, Any]]:
    cells_by_id = {str(item["suite_cell_id"]): copy.deepcopy(dict(item)) for item in detailed_cells}
    return [cells_by_id[cell_id] for cell_id in suite_cell_order]


def _build_detailed_work_items(
    *,
    detailed_cells: Sequence[Mapping[str, Any]],
    suite_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    stage_targets_by_work_item: dict[str, dict[str, Any]] = {}
    for cell in detailed_cells:
        for stage_target in cell["stage_targets"]:
            stage_targets_by_work_item[str(stage_target["work_item_id"])] = {
                "suite_cell_id": str(cell["suite_cell_id"]),
                "stage_id": str(stage_target["stage_id"]),
                "artifact_role_id": str(stage_target["artifact_role_id"]),
                "output_root": str(stage_target["output_root"]),
                "metadata_path": str(stage_target["metadata_path"]),
            }
    detailed: list[dict[str, Any]] = []
    for item in suite_metadata["work_items"]:
        stage_target = stage_targets_by_work_item[str(item["work_item_id"])]
        detailed.append(
            {
                "work_item_id": str(item["work_item_id"]),
                "suite_cell_id": str(item["suite_cell_id"]),
                "stage_id": str(item["stage_id"]),
                "status": str(item["status"]),
                "artifact_role_ids": list(item["artifact_role_ids"]),
                "output_root": stage_target["output_root"],
                "metadata_path": stage_target["metadata_path"],
            }
        )
    return detailed


def _sort_detailed_artifact_references(
    *,
    detailed_cells: Sequence[Mapping[str, Any]],
    suite_metadata: Mapping[str, Any],
    artifact_order: Sequence[tuple[str, Any, Any, str]],
) -> list[dict[str, Any]]:
    del artifact_order
    references_by_path: dict[str, dict[str, Any]] = {}
    for cell in detailed_cells:
        for stage_target in cell["stage_targets"]:
            references_by_path[str(stage_target["metadata_path"])] = {
                "suite_cell_id": str(cell["suite_cell_id"]),
                "stage_id": str(stage_target["stage_id"]),
                "artifact_role_id": str(stage_target["artifact_role_id"]),
                "metadata_path": str(stage_target["metadata_path"]),
            }
    detailed: list[dict[str, Any]] = []
    for item in suite_metadata["artifact_references"]:
        resolved = references_by_path[str(item["path"])]
        detailed.append(
            {
                "artifact_role_id": str(item["artifact_role_id"]),
                "suite_cell_id": str(item["suite_cell_id"]),
                "work_item_id": str(item["work_item_id"]),
                "metadata_path": resolved["metadata_path"],
                "stage_id": resolved["stage_id"],
                "status": str(item["status"]),
            }
        )
    return detailed


def _rewrite_manifest_reference_paths(
    payload: Mapping[str, Any],
    *,
    actual_manifest_path: Path,
) -> dict[str, Any]:
    rewritten = copy.deepcopy(dict(payload))
    manifest_reference = rewritten.get("manifest_reference")
    if not isinstance(manifest_reference, Mapping):
        return rewritten
    actual_reference = copy.deepcopy(dict(manifest_reference))
    actual_reference["manifest_path"] = str(actual_manifest_path.resolve())

    def _rewrite(value: Any) -> Any:
        if isinstance(value, Mapping):
            result: dict[str, Any] = {}
            for key, child in value.items():
                if key == "manifest_reference" and isinstance(child, Mapping):
                    result[key] = copy.deepcopy(actual_reference)
                else:
                    result[key] = _rewrite(child)
            return result
        if isinstance(value, list):
            return [_rewrite(item) for item in value]
        return value

    return _rewrite(rewritten)


def _first_surface_wave_arm(plan: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for arm_plan in plan.get("arm_plans", []):
        arm_reference = arm_plan.get("arm_reference", {})
        if arm_reference.get("model_mode") == SURFACE_WAVE_MODEL_MODE:
            return arm_plan
    return None


def _resolve_fidelity_default_value_id(surface_wave_plan: Mapping[str, Any] | None) -> str:
    if surface_wave_plan is None:
        return "baseline_only"
    execution_plan = _require_mapping(
        surface_wave_plan["model_configuration"]["surface_wave_execution_plan"],
        field_name="surface_wave_execution_plan",
    )
    state_space = str(execution_plan["resolution"]["state_space"])
    if state_space == "fine_surface_vertices":
        return "surface_only"
    return "mixed_fidelity"


def _resolve_fidelity_default_value_label(surface_wave_plan: Mapping[str, Any] | None) -> str:
    value_id = _resolve_fidelity_default_value_id(surface_wave_plan)
    return value_id.replace("_", " ").title()


def _resolve_fidelity_default_snapshot(
    surface_wave_plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if surface_wave_plan is None:
        return {"fidelity_class": "baseline_only"}
    execution_plan = _require_mapping(
        surface_wave_plan["model_configuration"]["surface_wave_execution_plan"],
        field_name="surface_wave_execution_plan",
    )
    return {
        "state_space": execution_plan["resolution"]["state_space"],
        "operator_scope": execution_plan["selected_root_operator_assets_scope"],
    }


def _matches_dimension_filters(
    *,
    selected_dimension_values: Mapping[str, Mapping[str, Any]],
    dimension_filters: Mapping[str, Sequence[str]],
) -> bool:
    if not dimension_filters:
        return True
    for dimension_id, allowed_value_ids in dimension_filters.items():
        if selected_dimension_values[dimension_id]["value_id"] not in set(allowed_value_ids):
            return False
    return True


def _strip_suite_extension(payload: Mapping[str, Any]) -> dict[str, Any]:
    sanitized = copy.deepcopy(dict(payload))
    sanitized.pop("suite", None)
    return sanitized


def _load_yaml_mapping(path: Path, *, field_name: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} at {path} must be a mapping.")
    return dict(payload)


def _resolve_relative_path(
    raw_path: Any,
    *,
    base_path: Path,
    field_name: str,
) -> Path:
    path_str = _normalize_nonempty_string(raw_path, field_name=field_name)
    candidate = Path(path_str).expanduser()
    if not candidate.is_absolute():
        candidate = (base_path / candidate).resolve()
    return candidate.resolve()


def _resolve_optional_relative_path(
    raw_path: Any,
    *,
    fallback: str | Path | None,
    base_path: Path,
    field_name: str,
) -> Path:
    if raw_path is None:
        if fallback is None:
            raise ValueError(f"{field_name} is required.")
        return Path(fallback).resolve()
    return _resolve_relative_path(raw_path, base_path=base_path, field_name=field_name)


def _resolve_optional_project_path(
    raw_path: Any,
    *,
    project_root: Path,
    field_name: str,
) -> str | None:
    if raw_path is None:
        return None
    path_str = _normalize_nonempty_string(raw_path, field_name=field_name)
    candidate = Path(path_str).expanduser()
    if not candidate.is_absolute():
        candidate = (project_root / candidate).resolve()
    return str(candidate.resolve())


def _normalize_stage_ids(payload: Any, *, field_name: str) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)) or not payload:
        raise ValueError(f"{field_name} must be a non-empty list.")
    normalized = [
        _normalize_identifier(value, field_name=f"{field_name}[{index}]")
        for index, value in enumerate(payload)
    ]
    unknown = sorted(set(normalized) - set(SUPPORTED_STAGE_IDS))
    if unknown:
        raise ValueError(
            f"{field_name} references unsupported stage ids {unknown!r}; supported stage ids "
            f"are {list(SUPPORTED_STAGE_IDS)!r}."
        )
    return [stage_id for stage_id in SUPPORTED_STAGE_IDS if stage_id in set(normalized)]


def _require_mapping(payload: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return dict(payload)


def _normalize_optional_json_mapping(
    payload: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    if payload is None:
        return {}
    return _normalize_json_mapping(payload, field_name=field_name)


def _normalize_optional_nonempty_string(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _normalize_nonempty_string(value, field_name=field_name)


def _lookup_first(payload: Mapping[str, Any], keys: Sequence[str], *, default: Any) -> Any:
    for key in keys:
        if payload.get(key) is not None:
            return payload[key]
    return default


def _value_id_from_parameter(value: Any) -> str:
    return _normalize_identifier(str(value), field_name="dimension_value.parameter")


def _has_nonempty_collection(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and bool(value)
