from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


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
) -> dict[str, Any]:
    manifest = load_yaml(manifest_path)
    schema = load_json(schema_path)
    design_lock = load_yaml(design_lock_path)
    return validate_manifest_payload(
        manifest=manifest,
        schema=schema,
        design_lock=design_lock,
        manifest_path=manifest_path,
    )


def validate_manifest_payload(
    manifest: dict[str, Any],
    schema: dict[str, Any],
    design_lock: dict[str, Any],
    manifest_path: str | Path | None = None,
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

    return {
        "experiment_id": manifest["experiment_id"],
        "milestone": manifest["milestone"],
        "brief_version": manifest["brief_version"],
        "success_criteria_count": len(manifest["success_criteria_ids"]),
        "comparison_arm_count": len(manifest["comparison_arms"]),
        "must_show_output_count": len(manifest["must_show_outputs"]),
    }
