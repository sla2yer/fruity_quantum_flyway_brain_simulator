from __future__ import annotations

import copy
import itertools
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .experiment_comparison_common import (
    _CONDITION_VALUE_TOLERANCE,
    _IGNORED_SELECTED_ASSET_ROLES,
    _PATH_RELAXED_SELECTED_ASSET_ROLES,
    _condition_signature,
    _normalize_analysis_plan,
    _normalize_simulation_plan,
    _require_mapping,
)
from .readout_analysis_contract import WAVE_ONLY_DIAGNOSTIC_CLASS
from .simulation_planning import discover_simulation_run_plans
from .simulator_result_contract import (
    load_simulator_result_bundle_metadata,
    lookup_simulator_result_bundle_metadata_path,
    parse_simulator_readout_definition,
    parse_simulator_result_bundle_metadata,
    resolve_simulator_result_bundle_metadata_path,
)
from .stimulus_contract import (
    _normalize_float,
    _normalize_identifier,
    _normalize_nonempty_string,
    load_stimulus_bundle_metadata,
    resolve_stimulus_bundle_metadata_path,
)
def discover_experiment_bundle_set(
    *,
    simulation_plan: Mapping[str, Any],
    analysis_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_simulation_plan = _normalize_simulation_plan(simulation_plan)
    normalized_analysis_plan = _normalize_analysis_plan(
        analysis_plan or normalized_simulation_plan["readout_analysis_plan"]
    )
    manifest_reference = _require_mapping(
        normalized_simulation_plan.get("manifest_reference"),
        field_name="simulation_plan.manifest_reference",
    )
    experiment_id = _normalize_identifier(
        manifest_reference.get("experiment_id"),
        field_name="simulation_plan.manifest_reference.experiment_id",
    )
    arm_ids = [
        _normalize_identifier(arm_id, field_name="simulation_plan.arm_order")
        for arm_id in normalized_simulation_plan["arm_order"]
    ]
    per_seed_run_plans = discover_simulation_run_plans(
        normalized_simulation_plan,
        use_manifest_seed_sweep=True,
    )
    canonical_arm_plans = {
        str(item["arm_reference"]["arm_id"]): copy.deepcopy(dict(item))
        for item in normalized_simulation_plan["arm_plans"]
    }
    expected_seeds_by_arm_id: dict[str, list[int]] = {}
    for item in per_seed_run_plans:
        arm_id = str(item["arm_reference"]["arm_id"])
        expected_seeds_by_arm_id.setdefault(arm_id, []).append(
            int(item["determinism"]["seed"])
        )
    expected_seeds_by_arm_id = {
        arm_id: sorted(set(seeds))
        for arm_id, seeds in expected_seeds_by_arm_id.items()
    }
    processed_simulator_results_dir = Path(
        _require_mapping(
            normalized_simulation_plan["arm_plans"][0]["runtime"],
            field_name="simulation_plan.arm_plans[0].runtime",
        )["processed_simulator_results_dir"]
    ).resolve()
    condition_groups = _condition_groups_from_plan(normalized_analysis_plan)
    requires_condition_labels = _plan_requires_condition_labels(normalized_analysis_plan)
    expected_condition_signatures = _expected_condition_signatures(
        condition_groups if requires_condition_labels else {}
    )
    expected_signature_keys = {
        tuple(signature["condition_ids"])
        for signature in expected_condition_signatures
    }
    expected_condition_variants = _expected_condition_variants(
        condition_groups=condition_groups,
        requires_condition_labels=requires_condition_labels,
    )

    bundle_records: list[dict[str, Any]] = []
    bundle_inventory: list[dict[str, Any]] = []
    seen_bundle_keys: set[tuple[str, int, tuple[str, ...]]] = set()

    for run_plan in per_seed_run_plans:
        arm_id = str(run_plan["arm_reference"]["arm_id"])
        arm_plan = canonical_arm_plans.get(arm_id)
        if arm_id not in set(arm_ids) or arm_plan is None:
            raise ValueError(
                f"Simulation plan is missing canonical arm plan metadata for arm_id {arm_id!r}."
            )
        expected_seeds = expected_seeds_by_arm_id.get(arm_id, [])
        for condition_variant in expected_condition_variants:
            metadata_path = _resolve_expected_simulator_bundle_metadata_path(
                run_plan=run_plan,
                parameter_overrides=condition_variant["parameter_overrides"],
            )
            if metadata_path is None:
                continue
            metadata = load_simulator_result_bundle_metadata(metadata_path)
            _validate_bundle_against_arm_plan(
                bundle_metadata=metadata,
                arm_plan=arm_plan,
                analysis_plan=normalized_analysis_plan,
                experiment_id=experiment_id,
            )
            seed = int(metadata["determinism"]["seed"])
            if seed not in set(expected_seeds):
                raise ValueError(
                    f"Discovered simulator bundle {metadata['bundle_id']!r} uses seed {seed!r}, "
                    f"but the normalized simulation plan expects seeds {expected_seeds!r} for "
                    f"arm_id {arm_id!r}."
                )
            inferred = _infer_bundle_conditions(
                bundle_metadata=metadata,
                condition_groups=condition_groups,
                requires_condition_labels=requires_condition_labels,
            )
            condition_ids = list(inferred["condition_ids"])
            condition_key = tuple(condition_ids)
            if requires_condition_labels and condition_key not in expected_signature_keys:
                raise ValueError(
                    f"Discovered simulator bundle {metadata['bundle_id']!r} maps to unexpected "
                    f"condition_ids {condition_ids!r}; expected one of "
                    f"{sorted(expected_signature_keys)!r} from the normalized analysis plan."
                )
            bundle_key = (arm_id, seed, condition_key)
            if bundle_key in seen_bundle_keys:
                raise ValueError(
                    f"Experiment bundle discovery found duplicate coverage for arm_id {arm_id!r}, "
                    f"seed {seed!r}, and condition_ids {condition_ids!r}."
                )
            seen_bundle_keys.add(bundle_key)
            bundle_records.append(
                {
                    "bundle_metadata": metadata,
                    "bundle_metadata_path": str(metadata_path.resolve()),
                    "condition_ids": condition_ids,
                }
            )
            bundle_inventory.append(
                {
                    "bundle_id": str(metadata["bundle_id"]),
                    "metadata_path": str(metadata_path.resolve()),
                    "arm_id": arm_id,
                    "model_mode": str(metadata["arm_reference"]["model_mode"]),
                    "baseline_family": metadata["arm_reference"]["baseline_family"],
                    "seed": seed,
                    "condition_ids": condition_ids,
                    "condition_signature": _condition_signature(condition_ids),
                    "stimulus_family": inferred["stimulus_family"],
                    "stimulus_name": inferred["stimulus_name"],
                    "parameter_snapshot": inferred["parameter_snapshot"],
                    "available_readout_ids": [
                        str(item["readout_id"]) for item in metadata["readout_catalog"]
                    ],
                }
            )

    _validate_bundle_coverage(
        bundle_inventory=bundle_inventory,
        arm_ids=arm_ids,
        expected_seeds_by_arm_id=expected_seeds_by_arm_id,
        expected_condition_signatures=expected_condition_signatures,
        requires_condition_labels=requires_condition_labels,
    )
    bundle_inventory.sort(
        key=lambda item: (
            str(item["arm_id"]),
            int(item["seed"]),
            str(item["condition_signature"]),
            str(item["bundle_id"]),
        )
    )
    bundle_records.sort(
        key=lambda item: (
            str(item["bundle_metadata"]["arm_reference"]["arm_id"]),
            int(item["bundle_metadata"]["determinism"]["seed"]),
            _condition_signature(item["condition_ids"]),
            str(item["bundle_metadata"]["bundle_id"]),
        )
    )
    return {
        "bundle_set_version": "experiment_bundle_set.v1",
        "experiment_id": experiment_id,
        "processed_simulator_results_dir": str(processed_simulator_results_dir),
        "expected_arm_ids": arm_ids,
        "expected_seeds_by_arm_id": expected_seeds_by_arm_id,
        "expected_condition_signatures": expected_condition_signatures,
        "bundle_inventory": bundle_inventory,
        "bundle_records": bundle_records,
    }


def _validate_bundle_against_arm_plan(
    *,
    bundle_metadata: Mapping[str, Any],
    arm_plan: Mapping[str, Any],
    analysis_plan: Mapping[str, Any],
    experiment_id: str,
) -> None:
    normalized_metadata = parse_simulator_result_bundle_metadata(bundle_metadata)
    expected_arm_id = str(arm_plan["arm_reference"]["arm_id"])
    discovered_experiment_id = str(normalized_metadata["manifest_reference"]["experiment_id"])
    if discovered_experiment_id != experiment_id:
        raise ValueError(
            f"Discovered bundle {normalized_metadata['bundle_id']!r} belongs to experiment "
            f"{discovered_experiment_id!r}, expected {experiment_id!r}."
        )
    if str(normalized_metadata["arm_reference"]["arm_id"]) != expected_arm_id:
        raise ValueError(
            f"Discovered bundle {normalized_metadata['bundle_id']!r} belongs to arm_id "
            f"{normalized_metadata['arm_reference']['arm_id']!r}, expected {expected_arm_id!r}."
        )
    if str(normalized_metadata["arm_reference"]["model_mode"]) != str(
        arm_plan["arm_reference"]["model_mode"]
    ):
        raise ValueError(
            f"Discovered bundle {normalized_metadata['bundle_id']!r} has model_mode "
            f"{normalized_metadata['arm_reference']['model_mode']!r}, expected "
            f"{arm_plan['arm_reference']['model_mode']!r}."
        )
    if normalized_metadata["arm_reference"]["baseline_family"] != arm_plan["arm_reference"]["baseline_family"]:
        raise ValueError(
            f"Discovered bundle {normalized_metadata['bundle_id']!r} has baseline_family "
            f"{normalized_metadata['arm_reference']['baseline_family']!r}, expected "
            f"{arm_plan['arm_reference']['baseline_family']!r}."
        )
    if dict(normalized_metadata["timebase"]) != dict(arm_plan["runtime"]["timebase"]):
        raise ValueError(
            f"Discovered bundle {normalized_metadata['bundle_id']!r} has an incompatible "
            "timebase relative to the normalized simulation plan."
        )
    _validate_bundle_selected_assets(normalized_metadata, arm_plan)
    _validate_bundle_readout_inventory(
        bundle_metadata=normalized_metadata,
        analysis_plan=analysis_plan,
    )


def _validate_bundle_selected_assets(
    bundle_metadata: Mapping[str, Any],
    arm_plan: Mapping[str, Any],
) -> None:
    expected_assets = [
        _selected_asset_identity(item)
        for item in arm_plan["selected_assets"]
        if str(item["asset_role"]) not in _IGNORED_SELECTED_ASSET_ROLES
    ]
    discovered_assets = [
        _selected_asset_identity(item)
        for item in bundle_metadata["selected_assets"]
        if str(item["asset_role"]) not in _IGNORED_SELECTED_ASSET_ROLES
    ]
    if expected_assets != discovered_assets:
        raise ValueError(
            f"Discovered bundle {bundle_metadata['bundle_id']!r} does not match the "
            "normalized non-input selected-asset inventory for its arm plan."
        )


def _selected_asset_identity(
    asset: Mapping[str, Any],
) -> tuple[str, str, str, str | None, str | None]:
    resolved_path = str(Path(asset["path"]).resolve())
    if str(asset["asset_role"]) in _PATH_RELAXED_SELECTED_ASSET_ROLES:
        resolved_path = ""
    return (
        str(asset["asset_role"]),
        str(asset["artifact_type"]),
        resolved_path,
        asset["artifact_id"],
        asset["bundle_id"],
    )


def _validate_bundle_readout_inventory(
    *,
    bundle_metadata: Mapping[str, Any],
    analysis_plan: Mapping[str, Any],
) -> None:
    readout_catalog_by_id = {
        str(item["readout_id"]): parse_simulator_readout_definition(item)
        for item in bundle_metadata["readout_catalog"]
    }
    for active_readout in analysis_plan["active_shared_readouts"]:
        readout_id = str(active_readout["readout_id"])
        discovered = readout_catalog_by_id.get(readout_id)
        if discovered is None:
            raise ValueError(
                f"Discovered bundle {bundle_metadata['bundle_id']!r} is missing active "
                f"shared readout_id {readout_id!r} required by the normalized analysis plan."
            )
        for field_name in (
            "aggregation",
            "scope",
            "units",
            "value_semantics",
        ):
            if str(discovered[field_name]) != str(active_readout[field_name]):
                raise ValueError(
                    f"Discovered bundle {bundle_metadata['bundle_id']!r} exposes readout_id "
                    f"{readout_id!r} with incompatible {field_name} "
                    f"{discovered[field_name]!r}; expected {active_readout[field_name]!r}."
                )


def _condition_groups_from_plan(
    analysis_plan: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in analysis_plan["condition_catalog"]:
        parameter_name = _normalize_identifier(
            item["parameter_name"],
            field_name="analysis_plan.condition_catalog.parameter_name",
        )
        groups.setdefault(parameter_name, []).append(copy.deepcopy(dict(item)))
    for values in groups.values():
        values.sort(key=lambda item: str(item["condition_id"]))
    return dict(sorted(groups.items()))


def _plan_requires_condition_labels(analysis_plan: Mapping[str, Any]) -> bool:
    for metric_definition in analysis_plan["active_metric_definitions"]:
        if str(metric_definition["metric_class"]) == WAVE_ONLY_DIAGNOSTIC_CLASS:
            continue
        return True
    return False


def _expected_condition_signatures(
    condition_groups: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    if not condition_groups:
        return [{"condition_ids": [], "condition_signature": "unlabeled"}]
    grouped_condition_ids = [
        [str(item["condition_id"]) for item in group]
        for _, group in sorted(condition_groups.items())
    ]
    signatures = []
    for combo in itertools.product(*grouped_condition_ids):
        condition_ids = sorted(str(item) for item in combo)
        signatures.append(
            {
                "condition_ids": condition_ids,
                "condition_signature": _condition_signature(condition_ids),
            }
        )
    signatures.sort(key=lambda item: str(item["condition_signature"]))
    return signatures


def _expected_condition_variants(
    *,
    condition_groups: Mapping[str, Sequence[Mapping[str, Any]]],
    requires_condition_labels: bool,
) -> list[dict[str, Any]]:
    if not requires_condition_labels or not condition_groups:
        return [{"condition_ids": [], "parameter_overrides": {}}]
    variants: list[dict[str, Any]] = [
        {
            "condition_ids": [],
            "parameter_overrides": {},
        }
    ]
    for parameter_name, candidates in sorted(condition_groups.items()):
        next_variants: list[dict[str, Any]] = []
        for variant in variants:
            for candidate in candidates:
                next_variants.append(
                    {
                        "condition_ids": sorted(
                            [
                                *variant["condition_ids"],
                                str(candidate["condition_id"]),
                            ]
                        ),
                        "parameter_overrides": {
                            **variant["parameter_overrides"],
                            parameter_name: copy.deepcopy(candidate["value"]),
                        },
                    }
                )
        variants = next_variants
    variants.sort(
        key=lambda item: (
            _condition_signature(item["condition_ids"]),
            tuple(item["condition_ids"]),
        )
    )
    return variants


def _resolve_expected_simulator_bundle_metadata_path(
    *,
    run_plan: Mapping[str, Any],
    parameter_overrides: Mapping[str, Any],
) -> Path | None:
    selected_assets = [copy.deepcopy(dict(item)) for item in run_plan["selected_assets"]]
    if parameter_overrides:
        selected_assets = _selected_assets_with_condition_stimulus(
            selected_assets=selected_assets,
            parameter_overrides=parameter_overrides,
        )
    exact_path = resolve_simulator_result_bundle_metadata_path(
        manifest_reference=run_plan["manifest_reference"],
        arm_reference=run_plan["arm_reference"],
        determinism=run_plan["determinism"],
        timebase=run_plan["runtime"]["timebase"],
        selected_assets=selected_assets,
        readout_catalog=run_plan["runtime"]["shared_readout_catalog"],
        processed_simulator_results_dir=run_plan["runtime"][
            "processed_simulator_results_dir"
        ],
    )
    if exact_path.exists():
        return exact_path
    return lookup_simulator_result_bundle_metadata_path(
        manifest_reference=run_plan["manifest_reference"],
        arm_reference=run_plan["arm_reference"],
        determinism=run_plan["determinism"],
        timebase=run_plan["runtime"]["timebase"],
        selected_assets=selected_assets,
        readout_catalog=run_plan["runtime"]["shared_readout_catalog"],
        processed_simulator_results_dir=run_plan["runtime"][
            "processed_simulator_results_dir"
        ],
        path_relaxed_asset_roles=("model_configuration",),
    )


def _selected_assets_with_condition_stimulus(
    *,
    selected_assets: Sequence[Mapping[str, Any]],
    parameter_overrides: Mapping[str, Any],
) -> list[dict[str, Any]]:
    replaced_assets: list[dict[str, Any]] = []
    base_stimulus_asset: dict[str, Any] | None = None
    for item in selected_assets:
        record = copy.deepcopy(dict(item))
        if (
            str(record["asset_role"]) == "input_bundle"
            and str(record["artifact_type"]) == "stimulus_bundle"
        ):
            base_stimulus_asset = record
        replaced_assets.append(record)
    if base_stimulus_asset is None:
        raise ValueError(
            "Experiment bundle discovery requires an input_bundle stimulus_bundle asset "
            "to resolve condition-specific simulator bundles."
        )
    base_stimulus_metadata = load_stimulus_bundle_metadata(Path(base_stimulus_asset["path"]))
    parameter_snapshot = copy.deepcopy(dict(base_stimulus_metadata["parameter_snapshot"]))
    parameter_snapshot.update(
        {str(key): copy.deepcopy(value) for key, value in parameter_overrides.items()}
    )
    processed_stimulus_dir = Path(
        base_stimulus_metadata["assets"]["metadata_json"]["path"]
    ).resolve().parents[4]
    condition_stimulus_metadata_path = resolve_stimulus_bundle_metadata_path(
        stimulus_family=str(base_stimulus_metadata["stimulus_family"]),
        stimulus_name=str(base_stimulus_metadata["stimulus_name"]),
        processed_stimulus_dir=processed_stimulus_dir,
        parameter_snapshot=parameter_snapshot,
        seed=int(base_stimulus_metadata["determinism"]["seed"]),
        temporal_sampling=base_stimulus_metadata["temporal_sampling"],
        spatial_frame=base_stimulus_metadata["spatial_frame"],
        luminance_convention=base_stimulus_metadata["luminance_convention"],
        rng_family=str(base_stimulus_metadata["determinism"]["rng_family"]),
    )
    if not condition_stimulus_metadata_path.exists():
        raise ValueError(
            "Experiment bundle discovery could not resolve the condition stimulus bundle "
            f"metadata at {condition_stimulus_metadata_path}."
        )
    condition_stimulus_metadata = load_stimulus_bundle_metadata(
        condition_stimulus_metadata_path
    )
    for item in replaced_assets:
        if (
            str(item["asset_role"]) == "input_bundle"
            and str(item["artifact_type"]) == "stimulus_bundle"
        ):
            item["bundle_id"] = str(condition_stimulus_metadata["bundle_id"])
            item["path"] = str(condition_stimulus_metadata_path.resolve())
            break
    return replaced_assets


def _infer_bundle_conditions(
    *,
    bundle_metadata: Mapping[str, Any],
    condition_groups: Mapping[str, Sequence[Mapping[str, Any]]],
    requires_condition_labels: bool,
) -> dict[str, Any]:
    stimulus_asset = _find_input_asset(bundle_metadata, artifact_type="stimulus_bundle")
    if stimulus_asset is None:
        if requires_condition_labels:
            raise ValueError(
                f"Discovered bundle {bundle_metadata['bundle_id']!r} is missing its selected "
                "stimulus bundle metadata, so the workflow cannot infer analysis condition labels."
            )
        return {
            "condition_ids": [],
            "stimulus_family": None,
            "stimulus_name": None,
            "parameter_snapshot": None,
        }
    stimulus_metadata = load_stimulus_bundle_metadata(Path(stimulus_asset["path"]))
    parameter_snapshot = copy.deepcopy(dict(stimulus_metadata["parameter_snapshot"]))
    condition_ids: list[str] = []
    for parameter_name, candidates in sorted(condition_groups.items()):
        if parameter_name not in parameter_snapshot:
            raise ValueError(
                f"Stimulus bundle {stimulus_metadata['bundle_id']!r} for simulator bundle "
                f"{bundle_metadata['bundle_id']!r} is missing parameter {parameter_name!r} "
                "required by the normalized analysis condition catalog."
            )
        observed_value = parameter_snapshot[parameter_name]
        matched_condition_ids = [
            str(item["condition_id"])
            for item in candidates
            if _condition_value_matches(
                observed_value=observed_value,
                expected_value=item["value"],
            )
        ]
        if len(matched_condition_ids) != 1:
            raise ValueError(
                f"Stimulus bundle {stimulus_metadata['bundle_id']!r} for simulator bundle "
                f"{bundle_metadata['bundle_id']!r} matched condition ids "
                f"{matched_condition_ids!r} for parameter {parameter_name!r}; expected exactly one."
            )
        condition_ids.append(matched_condition_ids[0])
    return {
        "condition_ids": sorted(condition_ids),
        "stimulus_family": str(stimulus_metadata["stimulus_family"]),
        "stimulus_name": str(stimulus_metadata["stimulus_name"]),
        "parameter_snapshot": parameter_snapshot,
    }


def _condition_value_matches(*, observed_value: Any, expected_value: Any) -> bool:
    if isinstance(expected_value, str):
        return _normalize_identifier(
            observed_value,
            field_name="stimulus.parameter_snapshot.value",
        ) == _normalize_identifier(
            expected_value,
            field_name="analysis_plan.condition_catalog.value",
        )
    observed_float = _normalize_float(
        observed_value,
        field_name="stimulus.parameter_snapshot.value",
    )
    expected_float = _normalize_float(
        expected_value,
        field_name="analysis_plan.condition_catalog.value",
    )
    return math.isclose(
        float(observed_float),
        float(expected_float),
        rel_tol=0.0,
        abs_tol=_CONDITION_VALUE_TOLERANCE,
    )


def _find_input_asset(
    bundle_metadata: Mapping[str, Any],
    *,
    artifact_type: str,
) -> dict[str, Any] | None:
    normalized_artifact_type = _normalize_nonempty_string(
        artifact_type,
        field_name="artifact_type",
    )
    for item in bundle_metadata["selected_assets"]:
        if (
            str(item["asset_role"]) == "input_bundle"
            and str(item["artifact_type"]) == normalized_artifact_type
        ):
            return copy.deepcopy(dict(item))
    return None


def _validate_bundle_coverage(
    *,
    bundle_inventory: Sequence[Mapping[str, Any]],
    arm_ids: Sequence[str],
    expected_seeds_by_arm_id: Mapping[str, Sequence[int]],
    expected_condition_signatures: Sequence[Mapping[str, Any]],
    requires_condition_labels: bool,
) -> None:
    expected_condition_keys = [
        tuple(item["condition_ids"]) for item in expected_condition_signatures
    ]
    inventory_by_arm_seed: dict[tuple[str, int], set[tuple[str, ...]]] = {}
    for item in bundle_inventory:
        key = (str(item["arm_id"]), int(item["seed"]))
        inventory_by_arm_seed.setdefault(key, set()).add(tuple(item["condition_ids"]))
    for arm_id in arm_ids:
        expected_seeds = expected_seeds_by_arm_id.get(arm_id, [])
        for seed in expected_seeds:
            seen_conditions = inventory_by_arm_seed.get((arm_id, int(seed)), set())
            if requires_condition_labels:
                missing_conditions = [
                    list(condition_ids)
                    for condition_ids in expected_condition_keys
                    if condition_ids not in seen_conditions
                ]
                if missing_conditions:
                    raise ValueError(
                        f"Experiment bundle set is missing required condition coverage for "
                        f"arm_id {arm_id!r}, seed {seed!r}: {missing_conditions!r}."
                    )
            elif not seen_conditions:
                raise ValueError(
                    f"Experiment bundle set is missing any bundle coverage for arm_id {arm_id!r}, "
                    f"seed {seed!r}."
                )


__all__ = ["discover_experiment_bundle_set"]
