from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .config import get_config_path, load_config
from .retinal_contract import DEFAULT_PROCESSED_RETINAL_DIR
from .retinal_geometry import ResolvedRetinalGeometry, resolve_retinal_geometry_spec
from .stimulus_contract import DEFAULT_PROCESSED_STIMULUS_DIR
from .stimulus_registry import ResolvedStimulusSpec, resolve_stimulus_spec

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ManifestInputRoots:
    config_path: Path | None
    processed_stimulus_dir: Path
    processed_retinal_dir: Path


def load_yaml(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"YAML at {file_path} is not a mapping.")
    return data


def load_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"JSON at {file_path} is not an object.")
    return data


def validate_manifest(
    manifest_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    *,
    config_path: str | Path | None = None,
    processed_stimulus_dir: str | Path | None = None,
) -> dict[str, Any]:
    manifest = load_yaml(manifest_path)
    schema = load_json(schema_path)
    design_lock = load_yaml(design_lock_path)
    return validate_manifest_payload(
        manifest=manifest,
        schema=schema,
        design_lock=design_lock,
        manifest_path=manifest_path,
        config_path=config_path,
        processed_stimulus_dir=processed_stimulus_dir,
    )


def validate_manifest_payload(
    manifest: dict[str, Any],
    schema: dict[str, Any],
    design_lock: dict[str, Any],
    manifest_path: str | Path | None = None,
    *,
    config_path: str | Path | None = None,
    processed_stimulus_dir: str | Path | None = None,
) -> dict[str, Any]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(manifest), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(f"{'/'.join(str(part) for part in err.absolute_path) or '<root>'}: {err.message}" for err in errors)
        raise ValueError(f"Schema validation failed for {manifest_path or 'manifest'}: {details}")

    metadata = design_lock.get("metadata", {})
    if manifest["milestone"] != metadata.get("milestone_id"):
        raise ValueError("Manifest milestone does not match the Milestone 1 design-lock metadata.")
    if manifest["brief_version"] != metadata.get("brief_version"):
        raise ValueError("Manifest brief_version does not match the locked brief version.")
    if manifest["hypothesis_version"] != metadata.get("hypothesis_version"):
        raise ValueError("Manifest hypothesis_version does not match the locked hypothesis version.")

    criteria_catalog = {item["id"]: item for item in design_lock.get("success_criteria", [])}
    unknown_criteria = sorted(set(manifest["success_criteria_ids"]) - set(criteria_catalog))
    if unknown_criteria:
        raise ValueError(f"Manifest references unknown success criteria IDs: {unknown_criteria}")

    required_output_catalog = {item["id"]: item for item in design_lock.get("must_show_outputs", [])}
    unknown_outputs = sorted(set(manifest["must_show_outputs"]) - set(required_output_catalog))
    if unknown_outputs:
        raise ValueError(f"Manifest references unknown must-show outputs: {unknown_outputs}")

    declared_outputs = {
        *(item["id"] for item in manifest["output_bundle"]["plots"]),
        *(item["id"] for item in manifest["output_bundle"]["ui_states"]),
    }
    missing_outputs = sorted(set(manifest["must_show_outputs"]) - declared_outputs)
    if missing_outputs:
        raise ValueError(f"Manifest must_show_outputs are missing from output_bundle: {missing_outputs}")

    arm_ids = {arm["arm_id"] for arm in manifest["comparison_arms"]}
    if len(arm_ids) != len(manifest["comparison_arms"]):
        raise ValueError("Manifest comparison_arms contain duplicate arm_id values.")

    has_p1 = any(arm["baseline_family"] == "P1" for arm in manifest["comparison_arms"])
    if "m1_survives_stronger_baseline" in manifest["success_criteria_ids"] and not has_p1:
        raise ValueError("Manifest claims survival against P1 but defines no P1 comparison arm.")

    try:
        _validate_manifest_stimulus_declaration(manifest)
        resolved_stimulus = resolve_manifest_stimulus(manifest)
    except ValueError as exc:
        raise ValueError(f"Manifest stimulus is invalid: {exc}") from exc

    resolved_input_roots = resolve_manifest_input_roots(
        config_path=config_path,
        processed_stimulus_dir=processed_stimulus_dir,
    )
    resolved_processed_stimulus_dir = resolved_input_roots.processed_stimulus_dir
    stimulus_contract = resolved_stimulus.build_contract_metadata(
        processed_stimulus_dir=resolved_processed_stimulus_dir
    )
    stimulus_bundle = resolved_stimulus.build_bundle_metadata(
        processed_stimulus_dir=resolved_processed_stimulus_dir
    )
    stimulus_bundle_reference = resolved_stimulus.build_bundle_reference(
        processed_stimulus_dir=resolved_processed_stimulus_dir
    )
    stimulus_bundle_metadata_path = resolved_stimulus.resolve_bundle_metadata_path(
        processed_stimulus_dir=resolved_processed_stimulus_dir
    )

    return {
        "experiment_id": manifest["experiment_id"],
        "milestone": manifest["milestone"],
        "brief_version": manifest["brief_version"],
        "success_criteria_count": len(manifest["success_criteria_ids"]),
        "comparison_arm_count": len(manifest["comparison_arms"]),
        "must_show_output_count": len(manifest["must_show_outputs"]),
        "resolved_stimulus_family": resolved_stimulus.stimulus_family,
        "resolved_stimulus_name": resolved_stimulus.stimulus_name,
        "resolved_stimulus_parameter_hash": resolved_stimulus.stimulus_spec["parameter_hash"],
        "stimulus_contract_version": stimulus_bundle_reference["contract_version"],
        "stimulus_bundle_id": stimulus_bundle_reference["bundle_id"],
        "stimulus_bundle_metadata_path": stimulus_bundle_metadata_path,
        "resolved_stimulus": resolved_stimulus.stimulus_spec,
        "stimulus_registry_entry": resolved_stimulus.registry_entry,
        "stimulus_contract": stimulus_contract,
        "stimulus_bundle": stimulus_bundle,
        "stimulus_bundle_reference": stimulus_bundle_reference,
    }


def resolve_manifest_stimulus(manifest: Mapping[str, Any]) -> ResolvedStimulusSpec:
    if not isinstance(manifest, Mapping):
        raise ValueError("manifest must be a mapping.")
    return resolve_stimulus_spec(manifest)


def resolve_manifest_retinal_geometry(manifest: Mapping[str, Any]) -> ResolvedRetinalGeometry:
    if not isinstance(manifest, Mapping):
        raise ValueError("manifest must be a mapping.")
    return resolve_retinal_geometry_spec(manifest)


def resolve_manifest_input_roots(
    *,
    config_path: str | Path | None = None,
    processed_stimulus_dir: str | Path | None = None,
    processed_retinal_dir: str | Path | None = None,
) -> ManifestInputRoots:
    resolved_config_path: Path | None = None
    configured_paths: Mapping[str, Any] = {}
    if config_path is not None:
        cfg = load_config(config_path)
        resolved_config_path = get_config_path(cfg)
        if resolved_config_path is None:
            raise ValueError("Loaded config is missing config metadata.")
        configured_paths = cfg["paths"]

    return ManifestInputRoots(
        config_path=resolved_config_path,
        processed_stimulus_dir=_resolve_processed_bundle_root(
            explicit_path=processed_stimulus_dir,
            configured_path=configured_paths.get("processed_stimulus_dir"),
            default_path=DEFAULT_PROCESSED_STIMULUS_DIR,
        ),
        processed_retinal_dir=_resolve_processed_bundle_root(
            explicit_path=processed_retinal_dir,
            configured_path=configured_paths.get("processed_retinal_dir"),
            default_path=DEFAULT_PROCESSED_RETINAL_DIR,
        ),
    )


def _resolve_processed_bundle_root(
    *,
    explicit_path: str | Path | None,
    configured_path: Any,
    default_path: Path,
) -> Path:
    if explicit_path is not None:
        return Path(explicit_path).resolve()
    if configured_path is not None:
        return Path(configured_path).resolve()
    return (REPO_ROOT / default_path).resolve()


def _validate_manifest_stimulus_declaration(manifest: Mapping[str, Any]) -> None:
    nested_stimulus = manifest.get("stimulus")
    if nested_stimulus is None:
        return
    if not isinstance(nested_stimulus, Mapping):
        raise ValueError("stimulus must be a mapping when provided.")

    nested_has_family = nested_stimulus.get("stimulus_family") is not None
    nested_has_name = nested_stimulus.get("stimulus_name") is not None
    if nested_has_family != nested_has_name:
        raise ValueError(
            "stimulus.stimulus_family and stimulus.stimulus_name must either both be provided "
            "or both be omitted."
        )

    top_level_seed = manifest.get("random_seed")
    determinism = nested_stimulus.get("determinism")
    if isinstance(determinism, Mapping) and determinism.get("seed") is not None and top_level_seed is not None:
        if int(determinism["seed"]) != int(top_level_seed):
            raise ValueError("stimulus.determinism.seed must match the top-level random_seed.")

    if nested_has_family and nested_has_name:
        top_level_reference = resolve_stimulus_spec(
            stimulus_family=manifest.get("stimulus_family"),
            stimulus_name=manifest.get("stimulus_name"),
        )
        nested_reference = resolve_stimulus_spec(stimulus=nested_stimulus)
        if (
            top_level_reference.stimulus_family != nested_reference.stimulus_family
            or top_level_reference.stimulus_name != nested_reference.stimulus_name
        ):
            raise ValueError(
                "stimulus.stimulus_family/stimulus_name must resolve to the same canonical "
                "stimulus as the top-level stimulus_family/stimulus_name fields."
            )
