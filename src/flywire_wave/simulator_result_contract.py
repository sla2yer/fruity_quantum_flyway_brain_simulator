from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .io_utils import write_json
from .stimulus_contract import (
    ASSET_STATUS_MISSING,
    ASSET_STATUS_READY,
    DEFAULT_HASH_ALGORITHM,
    DEFAULT_RNG_FAMILY,
    DEFAULT_TIME_UNIT,
    _normalize_asset_status,
    _normalize_float,
    _normalize_identifier,
    _normalize_json_mapping,
    _normalize_nonempty_string,
    _normalize_parameter_hash,
    _normalize_positive_float,
    _normalize_positive_int,
    _normalize_seed,
)


SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION = "simulator_result_bundle.v1"
SIMULATOR_RESULT_BUNDLE_DESIGN_NOTE = "docs/simulator_result_bundle_design.md"
SIMULATOR_RESULT_BUNDLE_DESIGN_NOTE_VERSION = "simulator_result_design_note.v1"

DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR = Path("data/processed/simulator_results")

BASELINE_MODEL_MODE = "baseline"
SURFACE_WAVE_MODEL_MODE = "surface_wave"
SUPPORTED_MODEL_MODES = (
    BASELINE_MODEL_MODE,
    SURFACE_WAVE_MODEL_MODE,
)

P0_BASELINE_FAMILY = "P0"
P1_BASELINE_FAMILY = "P1"
SUPPORTED_BASELINE_FAMILIES = (
    P0_BASELINE_FAMILY,
    P1_BASELINE_FAMILY,
)

FIXED_STEP_UNIFORM_SAMPLING_MODE = "fixed_step_uniform"
SUPPORTED_TIMEBASE_SAMPLING_MODES = (FIXED_STEP_UNIFORM_SAMPLING_MODE,)

METADATA_JSON_KEY = "metadata_json"
STATE_SUMMARY_KEY = "state_summary"
READOUT_TRACES_KEY = "readout_traces"
METRICS_TABLE_KEY = "metrics_table"
MODEL_ARTIFACTS_KEY = "model_artifacts"

CONTRACT_METADATA_SCOPE = "contract_metadata"
SHARED_COMPARISON_SCOPE = "shared_comparison"
MODEL_DIAGNOSTIC_SCOPE = "model_diagnostic"
WAVE_MODEL_EXTENSION_SCOPE = "wave_model_extension"
SUPPORTED_ARTIFACT_SCOPES = (
    CONTRACT_METADATA_SCOPE,
    SHARED_COMPARISON_SCOPE,
    MODEL_DIAGNOSTIC_SCOPE,
    WAVE_MODEL_EXTENSION_SCOPE,
)

DEFAULT_METADATA_FORMAT = "json_bundle_metadata.v1"
DEFAULT_STATE_SUMMARY_FORMAT = "json_state_summary_rows.v1"
DEFAULT_READOUT_TRACE_FORMAT = "npz_named_readout_traces.v1"
DEFAULT_METRICS_TABLE_FORMAT = "csv_metric_rows.v1"

STATE_SUMMARY_ROW_FIELDS = (
    "state_id",
    "scope",
    "summary_stat",
    "value",
    "units",
)
READOUT_TRACE_ARRAYS = (
    "time_ms",
    "readout_ids",
    "values",
)
METRIC_TABLE_COLUMNS = (
    "metric_id",
    "readout_id",
    "scope",
    "window_id",
    "statistic",
    "value",
    "units",
)

EXTENSION_ROOT_DIRECTORY_NAME = "extensions"
MIXED_MORPHOLOGY_INDEX_KEY = "mixed_morphology_index"
MIXED_MORPHOLOGY_INDEX_FORMAT = "json_mixed_morphology_index.v1"


@dataclass(frozen=True)
class SimulatorResultContractPaths:
    processed_simulator_results_dir: Path
    bundle_root_directory: Path


@dataclass(frozen=True)
class SimulatorResultBundlePaths:
    experiment_id: str
    arm_id: str
    run_spec_hash: str
    bundle_directory: Path
    extension_root_directory: Path
    metadata_json_path: Path
    state_summary_path: Path
    readout_traces_path: Path
    metrics_table_path: Path

    @property
    def bundle_id(self) -> str:
        return (
            f"{SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION}:"
            f"{self.experiment_id}:{self.arm_id}:{self.run_spec_hash}"
        )

    def asset_paths(self) -> dict[str, Path]:
        return {
            METADATA_JSON_KEY: self.metadata_json_path,
            STATE_SUMMARY_KEY: self.state_summary_path,
            READOUT_TRACES_KEY: self.readout_traces_path,
            METRICS_TABLE_KEY: self.metrics_table_path,
        }


def build_simulator_result_contract_paths(
    processed_simulator_results_dir: str | Path = DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
) -> SimulatorResultContractPaths:
    simulator_results_dir = Path(processed_simulator_results_dir).resolve()
    return SimulatorResultContractPaths(
        processed_simulator_results_dir=simulator_results_dir,
        bundle_root_directory=simulator_results_dir / "bundles",
    )


def build_simulator_result_bundle_paths(
    *,
    experiment_id: str,
    arm_id: str,
    run_spec_hash: str,
    processed_simulator_results_dir: str | Path = DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
) -> SimulatorResultBundlePaths:
    normalized_experiment_id = _normalize_identifier(
        experiment_id,
        field_name="manifest_reference.experiment_id",
    )
    normalized_arm_id = _normalize_identifier(arm_id, field_name="arm_reference.arm_id")
    normalized_run_spec_hash = _normalize_parameter_hash(run_spec_hash)
    contract_paths = build_simulator_result_contract_paths(processed_simulator_results_dir)
    bundle_directory = (
        contract_paths.bundle_root_directory
        / normalized_experiment_id
        / normalized_arm_id
        / normalized_run_spec_hash
    )
    return SimulatorResultBundlePaths(
        experiment_id=normalized_experiment_id,
        arm_id=normalized_arm_id,
        run_spec_hash=normalized_run_spec_hash,
        bundle_directory=bundle_directory,
        extension_root_directory=bundle_directory / EXTENSION_ROOT_DIRECTORY_NAME,
        metadata_json_path=bundle_directory / "simulator_result_bundle.json",
        state_summary_path=bundle_directory / "state_summary.json",
        readout_traces_path=bundle_directory / "readout_traces.npz",
        metrics_table_path=bundle_directory / "metrics.csv",
    )


def build_simulator_manifest_reference(
    *,
    experiment_id: str,
    manifest_path: str | Path,
    milestone: str,
    manifest_id: str | None = None,
    brief_version: str | None = None,
    hypothesis_version: str | None = None,
) -> dict[str, Any]:
    return parse_simulator_manifest_reference(
        {
            "experiment_id": experiment_id,
            "manifest_id": manifest_id if manifest_id is not None else experiment_id,
            "manifest_path": str(Path(manifest_path).resolve()),
            "milestone": milestone,
            "brief_version": brief_version,
            "hypothesis_version": hypothesis_version,
        }
    )


def build_simulator_arm_reference(
    *,
    arm_id: str,
    model_mode: str,
    baseline_family: str | None,
    comparison_tags: Sequence[str] | None = None,
) -> dict[str, Any]:
    return parse_simulator_arm_reference(
        {
            "arm_id": arm_id,
            "model_mode": model_mode,
            "baseline_family": baseline_family,
            "comparison_tags": list(comparison_tags or []),
        }
    )


def build_selected_asset_reference(
    *,
    asset_role: str,
    artifact_type: str,
    path: str | Path,
    contract_version: str | None = None,
    artifact_id: str | None = None,
    bundle_id: str | None = None,
) -> dict[str, Any]:
    return parse_selected_asset_reference(
        {
            "asset_role": asset_role,
            "artifact_type": artifact_type,
            "path": str(Path(path).resolve()),
            "contract_version": contract_version,
            "artifact_id": artifact_id,
            "bundle_id": bundle_id,
        }
    )


def build_simulator_readout_definition(
    *,
    readout_id: str,
    scope: str,
    aggregation: str,
    units: str,
    value_semantics: str,
    description: str | None = None,
) -> dict[str, Any]:
    return parse_simulator_readout_definition(
        {
            "readout_id": readout_id,
            "scope": scope,
            "aggregation": aggregation,
            "units": units,
            "value_semantics": value_semantics,
            "description": description,
        }
    )


def build_simulator_determinism(
    *,
    seed: int | str,
    rng_family: str = DEFAULT_RNG_FAMILY,
    seed_scope: str = "all_stochastic_simulator_components",
) -> dict[str, Any]:
    return _normalize_determinism_payload(
        {
            "seed": seed,
            "rng_family": rng_family,
            "seed_scope": seed_scope,
        }
    )


def build_simulator_extension_artifact_record(
    *,
    bundle_paths: SimulatorResultBundlePaths,
    artifact_id: str,
    file_name: str,
    format: str,
    status: str = ASSET_STATUS_MISSING,
    artifact_scope: str = MODEL_DIAGNOSTIC_SCOPE,
    description: str | None = None,
) -> dict[str, Any]:
    return parse_simulator_extension_artifact_record(
        {
            "artifact_id": artifact_id,
            "file_name": file_name,
            "path": str(bundle_paths.extension_root_directory / file_name),
            "format": format,
            "status": status,
            "artifact_scope": artifact_scope,
            "description": description,
        },
        extension_root_directory=bundle_paths.extension_root_directory,
        model_mode=None,
    )


def build_simulator_contract_manifest_metadata(
    *,
    processed_simulator_results_dir: str | Path = DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
) -> dict[str, Any]:
    contract_paths = build_simulator_result_contract_paths(processed_simulator_results_dir)
    return {
        "version": SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
        "design_note": SIMULATOR_RESULT_BUNDLE_DESIGN_NOTE,
        "design_note_version": SIMULATOR_RESULT_BUNDLE_DESIGN_NOTE_VERSION,
        "supported_model_modes": list(SUPPORTED_MODEL_MODES),
        "supported_baseline_families": list(SUPPORTED_BASELINE_FAMILIES),
        "default_time_unit": DEFAULT_TIME_UNIT,
        "supported_timebase_sampling_modes": list(SUPPORTED_TIMEBASE_SAMPLING_MODES),
        "shared_payload_contract": default_shared_payload_contract(),
        "bundle_root_directory": str(contract_paths.bundle_root_directory),
        "extension_root_directory_name": EXTENSION_ROOT_DIRECTORY_NAME,
        "shared_artifact_file_names": {
            METADATA_JSON_KEY: "simulator_result_bundle.json",
            STATE_SUMMARY_KEY: "state_summary.json",
            READOUT_TRACES_KEY: "readout_traces.npz",
            METRICS_TABLE_KEY: "metrics.csv",
        },
        "optional_bundle_fields": [MIXED_MORPHOLOGY_INDEX_KEY],
    }


def build_simulator_run_spec_hash(
    *,
    manifest_reference: Mapping[str, Any],
    arm_reference: Mapping[str, Any],
    determinism: Mapping[str, Any] | None = None,
    seed: int | str | None = None,
    rng_family: str = DEFAULT_RNG_FAMILY,
    seed_scope: str = "all_stochastic_simulator_components",
    timebase: Mapping[str, Any],
    selected_assets: Sequence[Mapping[str, Any]],
    readout_catalog: Sequence[Mapping[str, Any]],
) -> str:
    normalized_manifest_reference = parse_simulator_manifest_reference(manifest_reference)
    normalized_arm_reference = parse_simulator_arm_reference(arm_reference)
    normalized_determinism = _resolve_determinism(
        determinism=determinism,
        seed=seed,
        rng_family=rng_family,
        seed_scope=seed_scope,
    )
    normalized_timebase = normalize_simulator_timebase(timebase)
    normalized_selected_assets = _normalize_selected_assets(selected_assets)
    normalized_readout_catalog = _normalize_readout_catalog(readout_catalog)
    reproducibility_payload = {
        "manifest_reference": {
            "experiment_id": normalized_manifest_reference["experiment_id"],
            "manifest_id": normalized_manifest_reference["manifest_id"],
            "milestone": normalized_manifest_reference["milestone"],
            "brief_version": normalized_manifest_reference["brief_version"],
            "hypothesis_version": normalized_manifest_reference["hypothesis_version"],
        },
        "arm_reference": {
            "arm_id": normalized_arm_reference["arm_id"],
            "model_mode": normalized_arm_reference["model_mode"],
            "baseline_family": normalized_arm_reference["baseline_family"],
        },
        "determinism": normalized_determinism,
        "timebase": normalized_timebase,
        "selected_assets": normalized_selected_assets,
        "readout_catalog": normalized_readout_catalog,
    }
    serialized = json.dumps(
        reproducibility_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_simulator_result_bundle_metadata(
    *,
    manifest_reference: Mapping[str, Any],
    arm_reference: Mapping[str, Any],
    timebase: Mapping[str, Any],
    selected_assets: Sequence[Mapping[str, Any]],
    readout_catalog: Sequence[Mapping[str, Any]],
    processed_simulator_results_dir: str | Path = DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
    determinism: Mapping[str, Any] | None = None,
    seed: int | str | None = None,
    rng_family: str = DEFAULT_RNG_FAMILY,
    seed_scope: str = "all_stochastic_simulator_components",
    state_summary_status: str = ASSET_STATUS_MISSING,
    readout_traces_status: str = ASSET_STATUS_MISSING,
    metrics_table_status: str = ASSET_STATUS_MISSING,
    model_artifacts: Sequence[Mapping[str, Any]] | None = None,
    mixed_morphology_index: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_manifest_reference = parse_simulator_manifest_reference(manifest_reference)
    normalized_arm_reference = parse_simulator_arm_reference(arm_reference)
    normalized_determinism = _resolve_determinism(
        determinism=determinism,
        seed=seed,
        rng_family=rng_family,
        seed_scope=seed_scope,
    )
    normalized_timebase = normalize_simulator_timebase(timebase)
    normalized_selected_assets = _normalize_selected_assets(selected_assets)
    normalized_readout_catalog = _normalize_readout_catalog(readout_catalog)
    run_spec_hash = build_simulator_run_spec_hash(
        manifest_reference=normalized_manifest_reference,
        arm_reference=normalized_arm_reference,
        determinism=normalized_determinism,
        timebase=normalized_timebase,
        selected_assets=normalized_selected_assets,
        readout_catalog=normalized_readout_catalog,
    )
    bundle_paths = build_simulator_result_bundle_paths(
        experiment_id=normalized_manifest_reference["experiment_id"],
        arm_id=normalized_arm_reference["arm_id"],
        run_spec_hash=run_spec_hash,
        processed_simulator_results_dir=processed_simulator_results_dir,
    )
    normalized_model_artifacts = _normalize_model_artifact_records(
        model_artifacts or [],
        extension_root_directory=bundle_paths.extension_root_directory,
        model_mode=normalized_arm_reference["model_mode"],
    )
    shared_payload_contract = default_shared_payload_contract()
    payload = {
        "contract_version": SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
        "design_note": SIMULATOR_RESULT_BUNDLE_DESIGN_NOTE,
        "design_note_version": SIMULATOR_RESULT_BUNDLE_DESIGN_NOTE_VERSION,
        "bundle_id": bundle_paths.bundle_id,
        "manifest_reference": normalized_manifest_reference,
        "arm_reference": normalized_arm_reference,
        "run_spec_hash": run_spec_hash,
        "run_spec_hash_algorithm": DEFAULT_HASH_ALGORITHM,
        "bundle_layout": {
            "bundle_directory": str(bundle_paths.bundle_directory),
            "extension_root_directory": str(bundle_paths.extension_root_directory),
        },
        "determinism": normalized_determinism,
        "timebase": normalized_timebase,
        "selected_assets": normalized_selected_assets,
        "readout_catalog": normalized_readout_catalog,
        "shared_payload_contract": shared_payload_contract,
        "artifacts": {
            METADATA_JSON_KEY: {
                "path": str(bundle_paths.metadata_json_path),
                "status": ASSET_STATUS_READY,
                "format": DEFAULT_METADATA_FORMAT,
                "artifact_scope": CONTRACT_METADATA_SCOPE,
            },
            STATE_SUMMARY_KEY: {
                "path": str(bundle_paths.state_summary_path),
                "status": _normalize_asset_status(
                    state_summary_status,
                    field_name="state_summary_status",
                ),
                "format": shared_payload_contract[STATE_SUMMARY_KEY]["format"],
                "artifact_scope": SHARED_COMPARISON_SCOPE,
            },
            READOUT_TRACES_KEY: {
                "path": str(bundle_paths.readout_traces_path),
                "status": _normalize_asset_status(
                    readout_traces_status,
                    field_name="readout_traces_status",
                ),
                "format": shared_payload_contract[READOUT_TRACES_KEY]["format"],
                "artifact_scope": SHARED_COMPARISON_SCOPE,
            },
            METRICS_TABLE_KEY: {
                "path": str(bundle_paths.metrics_table_path),
                "status": _normalize_asset_status(
                    metrics_table_status,
                    field_name="metrics_table_status",
                ),
                "format": shared_payload_contract[METRICS_TABLE_KEY]["format"],
                "artifact_scope": SHARED_COMPARISON_SCOPE,
            },
            MODEL_ARTIFACTS_KEY: normalized_model_artifacts,
        },
    }
    if mixed_morphology_index is not None:
        payload[MIXED_MORPHOLOGY_INDEX_KEY] = copy.deepcopy(
            _normalize_mixed_morphology_index(
                mixed_morphology_index,
                artifacts=payload["artifacts"],
                readout_catalog=normalized_readout_catalog,
            )
        )
    return payload


def build_simulator_result_bundle_reference(bundle_metadata: Mapping[str, Any]) -> dict[str, Any]:
    normalized = parse_simulator_result_bundle_metadata(bundle_metadata)
    return {
        "contract_version": normalized["contract_version"],
        "experiment_id": normalized["manifest_reference"]["experiment_id"],
        "arm_id": normalized["arm_reference"]["arm_id"],
        "model_mode": normalized["arm_reference"]["model_mode"],
        "baseline_family": normalized["arm_reference"]["baseline_family"],
        "run_spec_hash": normalized["run_spec_hash"],
        "bundle_id": normalized["bundle_id"],
    }


def parse_simulator_manifest_reference(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("manifest_reference must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = ("experiment_id", "manifest_id", "manifest_path", "milestone")
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"manifest_reference is missing required fields: {missing_fields}")
    normalized["experiment_id"] = _normalize_identifier(
        normalized["experiment_id"],
        field_name="manifest_reference.experiment_id",
    )
    normalized["manifest_id"] = _normalize_identifier(
        normalized["manifest_id"],
        field_name="manifest_reference.manifest_id",
    )
    normalized["manifest_path"] = str(
        Path(
            _normalize_nonempty_string(
                normalized["manifest_path"],
                field_name="manifest_reference.manifest_path",
            )
        ).resolve()
    )
    normalized["milestone"] = _normalize_identifier(
        normalized["milestone"],
        field_name="manifest_reference.milestone",
    )
    normalized["brief_version"] = _normalize_optional_string(
        normalized.get("brief_version"),
        field_name="manifest_reference.brief_version",
    )
    normalized["hypothesis_version"] = _normalize_optional_string(
        normalized.get("hypothesis_version"),
        field_name="manifest_reference.hypothesis_version",
    )
    return normalized


def parse_simulator_arm_reference(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("arm_reference must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = ("arm_id", "model_mode", "baseline_family", "comparison_tags")
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"arm_reference is missing required fields: {missing_fields}")
    normalized["arm_id"] = _normalize_identifier(
        normalized["arm_id"],
        field_name="arm_reference.arm_id",
    )
    normalized["model_mode"] = _normalize_model_mode(normalized["model_mode"])
    normalized["baseline_family"] = _normalize_baseline_family(
        normalized["baseline_family"],
        model_mode=normalized["model_mode"],
    )
    normalized["comparison_tags"] = _normalize_comparison_tags(normalized["comparison_tags"])
    return normalized


def parse_selected_asset_reference(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("selected_assets entries must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = ("asset_role", "artifact_type", "path", "contract_version", "artifact_id", "bundle_id")
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"selected asset reference is missing required fields: {missing_fields}")
    normalized["asset_role"] = _normalize_identifier(
        normalized["asset_role"],
        field_name="selected_assets.asset_role",
    )
    normalized["artifact_type"] = _normalize_nonempty_string(
        normalized["artifact_type"],
        field_name="selected_assets.artifact_type",
    )
    normalized["path"] = str(
        Path(
            _normalize_nonempty_string(
                normalized["path"],
                field_name="selected_assets.path",
            )
        ).resolve()
    )
    normalized["contract_version"] = _normalize_optional_string(
        normalized.get("contract_version"),
        field_name="selected_assets.contract_version",
    )
    normalized["artifact_id"] = _normalize_optional_string(
        normalized.get("artifact_id"),
        field_name="selected_assets.artifact_id",
    )
    normalized["bundle_id"] = _normalize_optional_string(
        normalized.get("bundle_id"),
        field_name="selected_assets.bundle_id",
    )
    return normalized


def parse_simulator_readout_definition(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("readout_catalog entries must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "readout_id",
        "scope",
        "aggregation",
        "units",
        "value_semantics",
        "description",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"readout_catalog entry is missing required fields: {missing_fields}")
    normalized["readout_id"] = _normalize_identifier(
        normalized["readout_id"],
        field_name="readout_catalog.readout_id",
    )
    normalized["scope"] = _normalize_identifier(
        normalized["scope"],
        field_name="readout_catalog.scope",
    )
    normalized["aggregation"] = _normalize_identifier(
        normalized["aggregation"],
        field_name="readout_catalog.aggregation",
    )
    normalized["units"] = _normalize_nonempty_string(
        normalized["units"],
        field_name="readout_catalog.units",
    )
    normalized["value_semantics"] = _normalize_nonempty_string(
        normalized["value_semantics"],
        field_name="readout_catalog.value_semantics",
    )
    normalized["description"] = _normalize_optional_string(
        normalized.get("description"),
        field_name="readout_catalog.description",
    )
    return normalized


def parse_simulator_extension_artifact_record(
    payload: Mapping[str, Any],
    *,
    extension_root_directory: str | Path,
    model_mode: str | None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("model_artifacts entries must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = ("artifact_id", "file_name", "path", "format", "status", "artifact_scope", "description")
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"model_artifacts entry is missing required fields: {missing_fields}")
    normalized["artifact_id"] = _normalize_identifier(
        normalized["artifact_id"],
        field_name="model_artifacts.artifact_id",
    )
    normalized["file_name"] = _normalize_extension_file_name(
        normalized["file_name"],
        field_name="model_artifacts.file_name",
    )
    normalized["path"] = str(
        Path(
            _normalize_nonempty_string(
                normalized["path"],
                field_name="model_artifacts.path",
            )
        ).resolve()
    )
    normalized["format"] = _normalize_nonempty_string(
        normalized["format"],
        field_name="model_artifacts.format",
    )
    normalized["status"] = _normalize_asset_status(
        normalized["status"],
        field_name="model_artifacts.status",
    )
    normalized["artifact_scope"] = _normalize_artifact_scope(
        normalized["artifact_scope"],
        field_name="model_artifacts.artifact_scope",
    )
    normalized["description"] = _normalize_optional_string(
        normalized.get("description"),
        field_name="model_artifacts.description",
    )

    extension_root = Path(extension_root_directory).resolve()
    expected_path = (extension_root / normalized["file_name"]).resolve()
    if Path(normalized["path"]).resolve() != expected_path:
        raise ValueError(
            "model_artifacts paths must live under the canonical bundle extension directory."
        )
    if normalized["artifact_scope"] == CONTRACT_METADATA_SCOPE:
        raise ValueError(
            "model_artifacts entries may not use the contract_metadata scope."
        )
    if model_mode == BASELINE_MODEL_MODE and normalized["artifact_scope"] == WAVE_MODEL_EXTENSION_SCOPE:
        raise ValueError("Baseline bundles may not declare wave_model_extension artifacts.")
    return normalized


def parse_simulator_result_bundle_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Simulator result bundle metadata must be a mapping.")

    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "design_note",
        "design_note_version",
        "bundle_id",
        "manifest_reference",
        "arm_reference",
        "run_spec_hash",
        "run_spec_hash_algorithm",
        "bundle_layout",
        "determinism",
        "timebase",
        "selected_assets",
        "readout_catalog",
        "shared_payload_contract",
        "artifacts",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "Simulator result bundle metadata is missing required fields: "
            f"{missing_fields}"
        )
    if normalized["contract_version"] != SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION:
        raise ValueError(
            "Simulator result bundle metadata contract_version does not match "
            f"{SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION!r}."
        )
    normalized["manifest_reference"] = parse_simulator_manifest_reference(
        normalized["manifest_reference"]
    )
    normalized["arm_reference"] = parse_simulator_arm_reference(normalized["arm_reference"])
    normalized["run_spec_hash"] = _normalize_parameter_hash(normalized["run_spec_hash"])
    normalized["run_spec_hash_algorithm"] = _normalize_nonempty_string(
        normalized["run_spec_hash_algorithm"],
        field_name="run_spec_hash_algorithm",
    )
    if normalized["run_spec_hash_algorithm"] != DEFAULT_HASH_ALGORITHM:
        raise ValueError(
            "Unsupported run_spec_hash_algorithm "
            f"{normalized['run_spec_hash_algorithm']!r}."
        )
    normalized["bundle_layout"] = _normalize_bundle_layout(
        normalized["bundle_layout"],
        experiment_id=normalized["manifest_reference"]["experiment_id"],
        arm_id=normalized["arm_reference"]["arm_id"],
        run_spec_hash=normalized["run_spec_hash"],
    )
    normalized["determinism"] = _normalize_determinism_payload(normalized["determinism"])
    normalized["timebase"] = normalize_simulator_timebase(normalized["timebase"])
    normalized["selected_assets"] = _normalize_selected_assets(normalized["selected_assets"])
    normalized["readout_catalog"] = _normalize_readout_catalog(normalized["readout_catalog"])
    normalized["shared_payload_contract"] = _normalize_shared_payload_contract(
        normalized["shared_payload_contract"]
    )
    normalized["artifacts"] = _normalize_artifact_inventory(
        normalized["artifacts"],
        bundle_layout=normalized["bundle_layout"],
        arm_reference=normalized["arm_reference"],
        shared_payload_contract=normalized["shared_payload_contract"],
    )
    mixed_morphology_index = normalized.get(MIXED_MORPHOLOGY_INDEX_KEY)
    if mixed_morphology_index is not None:
        normalized[MIXED_MORPHOLOGY_INDEX_KEY] = _normalize_mixed_morphology_index(
            mixed_morphology_index,
            artifacts=normalized["artifacts"],
            readout_catalog=normalized["readout_catalog"],
        )

    expected_bundle_id = (
        f"{SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION}:"
        f"{normalized['manifest_reference']['experiment_id']}:"
        f"{normalized['arm_reference']['arm_id']}:"
        f"{normalized['run_spec_hash']}"
    )
    if normalized["bundle_id"] != expected_bundle_id:
        raise ValueError(
            "Simulator result bundle metadata bundle_id does not match the canonical "
            "experiment/arm/run-spec tuple."
        )

    expected_run_spec_hash = build_simulator_run_spec_hash(
        manifest_reference=normalized["manifest_reference"],
        arm_reference=normalized["arm_reference"],
        determinism=normalized["determinism"],
        timebase=normalized["timebase"],
        selected_assets=normalized["selected_assets"],
        readout_catalog=normalized["readout_catalog"],
    )
    if normalized["run_spec_hash"] != expected_run_spec_hash:
        raise ValueError(
            "Simulator result bundle metadata run_spec_hash does not match the normalized "
            "reproducibility payload."
        )
    return normalized


def load_simulator_result_bundle_metadata(metadata_path: str | Path) -> dict[str, Any]:
    path = Path(metadata_path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_simulator_result_bundle_metadata(payload)


def write_simulator_result_bundle_metadata(
    bundle_metadata: Mapping[str, Any],
    metadata_path: str | Path | None = None,
) -> Path:
    normalized = parse_simulator_result_bundle_metadata(bundle_metadata)
    output_path = (
        Path(metadata_path).resolve()
        if metadata_path is not None
        else Path(normalized["artifacts"][METADATA_JSON_KEY]["path"]).resolve()
    )
    return write_json(normalized, output_path)


def discover_simulator_result_bundle_paths(record: Mapping[str, Any]) -> dict[str, Path]:
    simulator_bundle = _extract_simulator_bundle_mapping(record)
    assets = simulator_bundle.get("artifacts")
    if not isinstance(assets, Mapping):
        raise ValueError("Simulator result bundle artifacts must be a mapping.")

    discovered: dict[str, Path] = {}
    for asset_key in (METADATA_JSON_KEY, STATE_SUMMARY_KEY, READOUT_TRACES_KEY, METRICS_TABLE_KEY):
        asset_record = assets.get(asset_key)
        if not isinstance(asset_record, Mapping):
            raise ValueError(
                f"Simulator result artifact {asset_key!r} is missing from bundle metadata."
            )
        asset_path = asset_record.get("path")
        if not isinstance(asset_path, str) or not asset_path:
            raise ValueError(
                f"Simulator result artifact {asset_key!r} is missing a usable path."
            )
        discovered[asset_key] = Path(asset_path)
    return discovered


def discover_simulator_extension_artifacts(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    simulator_bundle = _extract_simulator_bundle_mapping(record)
    artifacts = simulator_bundle.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ValueError("Simulator result bundle artifacts must be a mapping.")
    model_artifacts = artifacts.get(MODEL_ARTIFACTS_KEY)
    if not isinstance(model_artifacts, list):
        raise ValueError("Simulator result bundle model_artifacts must be a list.")
    discovered: list[dict[str, Any]] = []
    for artifact in model_artifacts:
        if not isinstance(artifact, Mapping):
            raise ValueError("Simulator result bundle model_artifact entries must be mappings.")
        artifact_id = artifact.get("artifact_id")
        artifact_path = artifact.get("path")
        artifact_format = artifact.get("format")
        artifact_scope = artifact.get("artifact_scope")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ValueError("Simulator result bundle model_artifact is missing artifact_id.")
        if not isinstance(artifact_path, str) or not artifact_path:
            raise ValueError("Simulator result bundle model_artifact is missing a usable path.")
        if not isinstance(artifact_format, str) or not artifact_format:
            raise ValueError("Simulator result bundle model_artifact is missing format.")
        if not isinstance(artifact_scope, str) or not artifact_scope:
            raise ValueError("Simulator result bundle model_artifact is missing artifact_scope.")
        discovered.append(
            {
                "artifact_id": artifact_id,
                "path": Path(artifact_path),
                "format": artifact_format,
                "artifact_scope": artifact_scope,
            }
        )
    return discovered


def discover_simulator_root_morphology_metadata(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    simulator_bundle = parse_simulator_result_bundle_metadata(
        _extract_simulator_bundle_mapping(record)
    )
    mixed_morphology_index = _require_mixed_morphology_index(simulator_bundle)
    return [
        copy.deepcopy(dict(item))
        for item in mixed_morphology_index["roots"]
    ]


def load_simulator_shared_readout_payload(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    simulator_bundle = parse_simulator_result_bundle_metadata(
        _extract_simulator_bundle_mapping(record)
    )
    readout_path = discover_simulator_result_bundle_paths(simulator_bundle)[
        READOUT_TRACES_KEY
    ].resolve()
    with np.load(readout_path, allow_pickle=False) as payload:
        missing_arrays = [
            array_name
            for array_name in READOUT_TRACE_ARRAYS
            if array_name not in payload.files
        ]
        if missing_arrays:
            raise ValueError(
                "Shared readout trace payload is missing required arrays: "
                f"{missing_arrays!r}."
            )
        return {
            "path": readout_path,
            "time_ms": np.asarray(payload["time_ms"], dtype=np.float64),
            "readout_ids": tuple(str(item) for item in payload["readout_ids"].tolist()),
            "values": np.asarray(payload["values"], dtype=np.float64),
        }


def load_simulator_root_state_payload(
    record: Mapping[str, Any],
    *,
    root_id: int,
) -> dict[str, Any]:
    simulator_bundle = parse_simulator_result_bundle_metadata(
        _extract_simulator_bundle_mapping(record)
    )
    mixed_morphology_index = _require_mixed_morphology_index(simulator_bundle)
    root_record = _mixed_morphology_root_record(
        mixed_morphology_index,
        root_id=int(root_id),
    )
    state_bundle_payload = _load_mixed_morphology_state_bundle(
        simulator_bundle,
        artifact_id=str(mixed_morphology_index["state_bundle_artifact_id"]),
    )
    state_summary_path = discover_simulator_result_bundle_paths(simulator_bundle)[
        STATE_SUMMARY_KEY
    ].resolve()
    with state_summary_path.open("r", encoding="utf-8") as handle:
        state_summary_rows = json.load(handle)
    if not isinstance(state_summary_rows, list):
        raise ValueError("state_summary payload must be a list of row mappings.")

    extension_paths = {
        item["artifact_id"]: Path(item["path"]).resolve()
        for item in discover_simulator_extension_artifacts(simulator_bundle)
    }
    projection_path = extension_paths[str(mixed_morphology_index["projection_artifact_id"])]
    with np.load(projection_path, allow_pickle=False) as projection_payload:
        projection_time_array = str(root_record["projection_time_array"])
        projection_trace_array = str(root_record["projection_trace_array"])
        if projection_time_array not in projection_payload.files:
            raise ValueError(
                "Projection trace payload is missing time array "
                f"{projection_time_array!r}."
            )
        if projection_trace_array not in projection_payload.files:
            raise ValueError(
                "Projection trace payload is missing root array "
                f"{projection_trace_array!r}."
            )
        projection_time_ms = np.asarray(
            projection_payload[projection_time_array],
            dtype=np.float64,
        )
        projection_trace = np.asarray(
            projection_payload[projection_trace_array],
            dtype=np.float64,
        )

    root_key = str(root_record["state_bundle_root_key"])
    runtime_metadata_key = str(root_record["runtime_metadata_root_key"])
    return {
        "root_id": int(root_record["root_id"]),
        "morphology_class": str(root_record["morphology_class"]),
        "runtime_metadata": copy.deepcopy(
            _require_mapping(
                _require_mapping(
                    state_bundle_payload["runtime_metadata_by_root"],
                    field_name="mixed_morphology_state_bundle.runtime_metadata_by_root",
                )[runtime_metadata_key],
                field_name=(
                    "mixed_morphology_state_bundle.runtime_metadata_by_root."
                    f"{runtime_metadata_key}"
                ),
            )
        ),
        "initial_state_export": copy.deepcopy(
            _require_mapping(
                _require_mapping(
                    state_bundle_payload["initial_state_exports_by_root"],
                    field_name="mixed_morphology_state_bundle.initial_state_exports_by_root",
                )[root_key],
                field_name=(
                    "mixed_morphology_state_bundle.initial_state_exports_by_root."
                    f"{root_key}"
                ),
            )
        ),
        "final_state_export": copy.deepcopy(
            _require_mapping(
                _require_mapping(
                    state_bundle_payload["final_state_exports_by_root"],
                    field_name="mixed_morphology_state_bundle.final_state_exports_by_root",
                )[root_key],
                field_name=(
                    "mixed_morphology_state_bundle.final_state_exports_by_root."
                    f"{root_key}"
                ),
            )
        ),
        "state_summary_rows": [
            copy.deepcopy(dict(item))
            for item in state_summary_rows
            if isinstance(item, Mapping)
            and str(item.get("state_id")) in set(root_record["state_summary_ids"])
        ],
        "projection_time_ms": projection_time_ms,
        "projection_trace": projection_trace,
        "projection_semantics": str(root_record["projection_semantics"]),
        "shared_readout_ids": list(root_record["shared_readout_ids"]),
    }


def resolve_simulator_result_bundle_metadata_path(
    *,
    manifest_reference: Mapping[str, Any],
    arm_reference: Mapping[str, Any],
    timebase: Mapping[str, Any],
    selected_assets: Sequence[Mapping[str, Any]],
    readout_catalog: Sequence[Mapping[str, Any]],
    processed_simulator_results_dir: str | Path = DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
    determinism: Mapping[str, Any] | None = None,
    seed: int | str | None = None,
    rng_family: str = DEFAULT_RNG_FAMILY,
    seed_scope: str = "all_stochastic_simulator_components",
) -> Path:
    normalized_manifest_reference = parse_simulator_manifest_reference(manifest_reference)
    normalized_arm_reference = parse_simulator_arm_reference(arm_reference)
    run_spec_hash = build_simulator_run_spec_hash(
        manifest_reference=normalized_manifest_reference,
        arm_reference=normalized_arm_reference,
        determinism=determinism,
        seed=seed,
        rng_family=rng_family,
        seed_scope=seed_scope,
        timebase=timebase,
        selected_assets=selected_assets,
        readout_catalog=readout_catalog,
    )
    bundle_paths = build_simulator_result_bundle_paths(
        experiment_id=normalized_manifest_reference["experiment_id"],
        arm_id=normalized_arm_reference["arm_id"],
        run_spec_hash=run_spec_hash,
        processed_simulator_results_dir=processed_simulator_results_dir,
    )
    return bundle_paths.metadata_json_path.resolve()


def default_shared_payload_contract() -> dict[str, Any]:
    return {
        STATE_SUMMARY_KEY: {
            "format": DEFAULT_STATE_SUMMARY_FORMAT,
            "row_fields": list(STATE_SUMMARY_ROW_FIELDS),
        },
        READOUT_TRACES_KEY: {
            "format": DEFAULT_READOUT_TRACE_FORMAT,
            "required_arrays": list(READOUT_TRACE_ARRAYS),
        },
        METRICS_TABLE_KEY: {
            "format": DEFAULT_METRICS_TABLE_FORMAT,
            "required_columns": list(METRIC_TABLE_COLUMNS),
        },
    }


def normalize_simulator_timebase(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("timebase must be a mapping.")
    dt_ms = _normalize_positive_float(payload.get("dt_ms"), field_name="timebase.dt_ms")
    duration_ms = _normalize_positive_float(
        payload.get("duration_ms"),
        field_name="timebase.duration_ms",
    )
    time_origin_ms = _normalize_float(
        payload.get("time_origin_ms", 0.0),
        field_name="timebase.time_origin_ms",
    )
    sampling_mode = _normalize_nonempty_string(
        payload.get("sampling_mode", FIXED_STEP_UNIFORM_SAMPLING_MODE),
        field_name="timebase.sampling_mode",
    )
    if sampling_mode not in SUPPORTED_TIMEBASE_SAMPLING_MODES:
        raise ValueError(
            "Unsupported timebase.sampling_mode "
            f"{sampling_mode!r}. Supported modes: {list(SUPPORTED_TIMEBASE_SAMPLING_MODES)!r}."
        )
    sample_count = payload.get("sample_count")
    if sample_count is None:
        inferred_sample_count = duration_ms / dt_ms
        rounded = int(round(inferred_sample_count))
        if not math.isclose(inferred_sample_count, rounded, rel_tol=0.0, abs_tol=1.0e-9):
            raise ValueError(
                "timebase.duration_ms must be an integer multiple of timebase.dt_ms when "
                "timebase.sample_count is omitted."
            )
        sample_count = rounded
    normalized_sample_count = _normalize_positive_int(
        sample_count,
        field_name="timebase.sample_count",
    )
    expected_duration = normalized_sample_count * dt_ms
    if not math.isclose(expected_duration, duration_ms, rel_tol=0.0, abs_tol=1.0e-9):
        raise ValueError(
            "timebase.sample_count * timebase.dt_ms must equal timebase.duration_ms."
        )
    return {
        "time_unit": DEFAULT_TIME_UNIT,
        "time_origin_ms": time_origin_ms,
        "dt_ms": dt_ms,
        "duration_ms": duration_ms,
        "sample_count": normalized_sample_count,
        "sampling_mode": sampling_mode,
    }


def _resolve_determinism(
    *,
    determinism: Mapping[str, Any] | None,
    seed: int | str | None,
    rng_family: str,
    seed_scope: str,
) -> dict[str, Any]:
    if determinism is not None:
        return _normalize_determinism_payload(determinism)
    if seed is None:
        raise ValueError("seed is required when determinism is not provided.")
    return build_simulator_determinism(
        seed=seed,
        rng_family=rng_family,
        seed_scope=seed_scope,
    )


def _normalize_bundle_layout(
    payload: Mapping[str, Any],
    *,
    experiment_id: str,
    arm_id: str,
    run_spec_hash: str,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("bundle_layout must be a mapping.")
    bundle_directory = Path(
        _normalize_nonempty_string(
            payload.get("bundle_directory"),
            field_name="bundle_layout.bundle_directory",
        )
    ).resolve()
    extension_root_directory = Path(
        _normalize_nonempty_string(
            payload.get("extension_root_directory"),
            field_name="bundle_layout.extension_root_directory",
        )
    ).resolve()
    if bundle_directory.name != run_spec_hash:
        raise ValueError("bundle_layout.bundle_directory must end with the run_spec_hash.")
    if bundle_directory.parent.name != arm_id:
        raise ValueError("bundle_layout.bundle_directory must encode the canonical arm_id parent.")
    if bundle_directory.parent.parent.name != experiment_id:
        raise ValueError(
            "bundle_layout.bundle_directory must encode the canonical experiment_id parent."
        )
    if bundle_directory.parent.parent.parent.name != "bundles":
        raise ValueError(
            "bundle_layout.bundle_directory must live under the contract-owned bundles directory."
        )
    expected_extension_root_directory = (bundle_directory / EXTENSION_ROOT_DIRECTORY_NAME).resolve()
    if extension_root_directory != expected_extension_root_directory:
        raise ValueError(
            "bundle_layout.extension_root_directory must match the canonical bundle extension path."
        )
    return {
        "bundle_directory": str(bundle_directory),
        "extension_root_directory": str(extension_root_directory),
    }


def _normalize_determinism_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("determinism must be a mapping.")
    return {
        "seed": _normalize_seed(payload.get("seed")),
        "rng_family": _normalize_nonempty_string(
            payload.get("rng_family", DEFAULT_RNG_FAMILY),
            field_name="determinism.rng_family",
        ),
        "seed_scope": _normalize_nonempty_string(
            payload.get("seed_scope", "all_stochastic_simulator_components"),
            field_name="determinism.seed_scope",
        ),
    }


def _normalize_shared_payload_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    defaults = default_shared_payload_contract()
    normalized = _normalize_json_mapping(payload, field_name="shared_payload_contract")
    expected = _normalize_json_mapping(defaults, field_name="shared_payload_contract")
    if normalized != expected:
        raise ValueError(
            "shared_payload_contract must match the canonical shared comparison payload "
            f"definition for {SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION!r}."
        )
    return defaults


def _normalize_artifact_inventory(
    payload: Mapping[str, Any],
    *,
    bundle_layout: Mapping[str, Any],
    arm_reference: Mapping[str, Any],
    shared_payload_contract: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("artifacts must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        METADATA_JSON_KEY,
        STATE_SUMMARY_KEY,
        READOUT_TRACES_KEY,
        METRICS_TABLE_KEY,
        MODEL_ARTIFACTS_KEY,
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"artifacts is missing required fields: {missing_fields}")
    bundle_directory = Path(bundle_layout["bundle_directory"]).resolve()
    extension_root_directory = Path(bundle_layout["extension_root_directory"]).resolve()
    return {
        METADATA_JSON_KEY: _normalize_fixed_artifact_record(
            normalized[METADATA_JSON_KEY],
            field_name=f"artifacts.{METADATA_JSON_KEY}",
            expected_path=bundle_directory / "simulator_result_bundle.json",
            expected_format=DEFAULT_METADATA_FORMAT,
            expected_scope=CONTRACT_METADATA_SCOPE,
            expected_status=ASSET_STATUS_READY,
        ),
        STATE_SUMMARY_KEY: _normalize_fixed_artifact_record(
            normalized[STATE_SUMMARY_KEY],
            field_name=f"artifacts.{STATE_SUMMARY_KEY}",
            expected_path=bundle_directory / "state_summary.json",
            expected_format=str(shared_payload_contract[STATE_SUMMARY_KEY]["format"]),
            expected_scope=SHARED_COMPARISON_SCOPE,
        ),
        READOUT_TRACES_KEY: _normalize_fixed_artifact_record(
            normalized[READOUT_TRACES_KEY],
            field_name=f"artifacts.{READOUT_TRACES_KEY}",
            expected_path=bundle_directory / "readout_traces.npz",
            expected_format=str(shared_payload_contract[READOUT_TRACES_KEY]["format"]),
            expected_scope=SHARED_COMPARISON_SCOPE,
        ),
        METRICS_TABLE_KEY: _normalize_fixed_artifact_record(
            normalized[METRICS_TABLE_KEY],
            field_name=f"artifacts.{METRICS_TABLE_KEY}",
            expected_path=bundle_directory / "metrics.csv",
            expected_format=str(shared_payload_contract[METRICS_TABLE_KEY]["format"]),
            expected_scope=SHARED_COMPARISON_SCOPE,
        ),
        MODEL_ARTIFACTS_KEY: _normalize_model_artifact_records(
            normalized[MODEL_ARTIFACTS_KEY],
            extension_root_directory=extension_root_directory,
            model_mode=str(arm_reference["model_mode"]),
        ),
    }


def _normalize_fixed_artifact_record(
    payload: Mapping[str, Any],
    *,
    field_name: str,
    expected_path: Path,
    expected_format: str,
    expected_scope: str,
    expected_status: str | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    normalized_path = Path(
        _normalize_nonempty_string(payload.get("path"), field_name=f"{field_name}.path")
    ).resolve()
    if normalized_path != expected_path.resolve():
        raise ValueError(f"{field_name}.path must match the canonical bundle layout.")
    normalized_status = _normalize_asset_status(
        payload.get("status"),
        field_name=f"{field_name}.status",
    )
    if expected_status is not None and normalized_status != expected_status:
        raise ValueError(f"{field_name}.status must be {expected_status!r}.")
    normalized_format = _normalize_nonempty_string(
        payload.get("format"),
        field_name=f"{field_name}.format",
    )
    if normalized_format != expected_format:
        raise ValueError(f"{field_name}.format must be {expected_format!r}.")
    normalized_artifact_scope = _normalize_artifact_scope(
        payload.get("artifact_scope"),
        field_name=f"{field_name}.artifact_scope",
    )
    if normalized_artifact_scope != expected_scope:
        raise ValueError(f"{field_name}.artifact_scope must be {expected_scope!r}.")
    return {
        "path": str(normalized_path),
        "status": normalized_status,
        "format": normalized_format,
        "artifact_scope": normalized_artifact_scope,
    }


def _normalize_model_artifact_records(
    payload: Sequence[Mapping[str, Any]],
    *,
    extension_root_directory: str | Path,
    model_mode: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("model_artifacts must be a list.")
    normalized = [
        parse_simulator_extension_artifact_record(
            item,
            extension_root_directory=extension_root_directory,
            model_mode=model_mode,
        )
        for item in payload
    ]
    sorted_records = sorted(
        normalized,
        key=lambda item: (
            item["artifact_id"],
            item["file_name"],
            item["artifact_scope"],
            item["path"],
        ),
    )
    seen_ids: set[str] = set()
    for item in sorted_records:
        artifact_id = str(item["artifact_id"])
        if artifact_id in seen_ids:
            raise ValueError(f"model_artifacts contains duplicate artifact_id {artifact_id!r}.")
        seen_ids.add(artifact_id)
    return sorted_records


def _normalize_mixed_morphology_index(
    payload: Mapping[str, Any],
    *,
    artifacts: Mapping[str, Any],
    readout_catalog: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{MIXED_MORPHOLOGY_INDEX_KEY} must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "format_version",
        "state_bundle_artifact_id",
        "projection_artifact_id",
        "shared_state_summary_artifact_id",
        "shared_readout_traces_artifact_id",
        "roots",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"{MIXED_MORPHOLOGY_INDEX_KEY} is missing required fields: {missing_fields!r}."
        )
    format_version = _normalize_nonempty_string(
        normalized["format_version"],
        field_name=f"{MIXED_MORPHOLOGY_INDEX_KEY}.format_version",
    )
    if format_version != MIXED_MORPHOLOGY_INDEX_FORMAT:
        raise ValueError(
            f"{MIXED_MORPHOLOGY_INDEX_KEY}.format_version must be "
            f"{MIXED_MORPHOLOGY_INDEX_FORMAT!r}."
        )
    state_bundle_artifact_id = _normalize_identifier(
        normalized["state_bundle_artifact_id"],
        field_name=f"{MIXED_MORPHOLOGY_INDEX_KEY}.state_bundle_artifact_id",
    )
    projection_artifact_id = _normalize_identifier(
        normalized["projection_artifact_id"],
        field_name=f"{MIXED_MORPHOLOGY_INDEX_KEY}.projection_artifact_id",
    )
    shared_state_summary_artifact_id = _normalize_identifier(
        normalized["shared_state_summary_artifact_id"],
        field_name=(
            f"{MIXED_MORPHOLOGY_INDEX_KEY}.shared_state_summary_artifact_id"
        ),
    )
    shared_readout_traces_artifact_id = _normalize_identifier(
        normalized["shared_readout_traces_artifact_id"],
        field_name=(
            f"{MIXED_MORPHOLOGY_INDEX_KEY}.shared_readout_traces_artifact_id"
        ),
    )
    if shared_state_summary_artifact_id != STATE_SUMMARY_KEY:
        raise ValueError(
            f"{MIXED_MORPHOLOGY_INDEX_KEY}.shared_state_summary_artifact_id must be "
            f"{STATE_SUMMARY_KEY!r}."
        )
    if shared_readout_traces_artifact_id != READOUT_TRACES_KEY:
        raise ValueError(
            f"{MIXED_MORPHOLOGY_INDEX_KEY}.shared_readout_traces_artifact_id must be "
            f"{READOUT_TRACES_KEY!r}."
        )
    available_extension_ids = {
        str(item["artifact_id"])
        for item in artifacts.get(MODEL_ARTIFACTS_KEY, [])
        if isinstance(item, Mapping)
    }
    for artifact_id in (state_bundle_artifact_id, projection_artifact_id):
        if artifact_id not in available_extension_ids:
            raise ValueError(
                f"{MIXED_MORPHOLOGY_INDEX_KEY} references unknown model artifact_id "
                f"{artifact_id!r}."
            )
    roots_payload = normalized["roots"]
    if not isinstance(roots_payload, Sequence) or isinstance(roots_payload, (str, bytes)):
        raise ValueError(f"{MIXED_MORPHOLOGY_INDEX_KEY}.roots must be a list.")
    readout_ids = {
        str(item["readout_id"])
        for item in readout_catalog
    }
    roots = [
        _normalize_mixed_morphology_root_record(
            item,
            readout_ids=readout_ids,
        )
        for item in roots_payload
    ]
    seen_root_ids: set[int] = set()
    for item in roots:
        root_id = int(item["root_id"])
        if root_id in seen_root_ids:
            raise ValueError(
                f"{MIXED_MORPHOLOGY_INDEX_KEY}.roots contains duplicate root_id {root_id!r}."
            )
        seen_root_ids.add(root_id)
    return {
        "format_version": format_version,
        "state_bundle_artifact_id": state_bundle_artifact_id,
        "projection_artifact_id": projection_artifact_id,
        "shared_state_summary_artifact_id": shared_state_summary_artifact_id,
        "shared_readout_traces_artifact_id": shared_readout_traces_artifact_id,
        "roots": sorted(roots, key=lambda item: (int(item["root_id"]), str(item["morphology_class"]))),
    }


def _normalize_mixed_morphology_root_record(
    payload: Mapping[str, Any],
    *,
    readout_ids: set[str],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{MIXED_MORPHOLOGY_INDEX_KEY}.roots entries must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "root_id",
        "morphology_class",
        "state_bundle_root_key",
        "runtime_metadata_root_key",
        "state_summary_ids",
        "projection_time_array",
        "projection_trace_array",
        "projection_semantics",
        "shared_readout_ids",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"{MIXED_MORPHOLOGY_INDEX_KEY}.roots entry is missing required fields: "
            f"{missing_fields!r}."
        )
    root_id = _normalize_positive_int(
        normalized["root_id"],
        field_name=f"{MIXED_MORPHOLOGY_INDEX_KEY}.roots.root_id",
    )
    morphology_class = _normalize_nonempty_string(
        normalized["morphology_class"],
        field_name=f"{MIXED_MORPHOLOGY_INDEX_KEY}.roots.morphology_class",
    )
    state_bundle_root_key = _normalize_nonempty_string(
        normalized["state_bundle_root_key"],
        field_name=f"{MIXED_MORPHOLOGY_INDEX_KEY}.roots.state_bundle_root_key",
    )
    runtime_metadata_root_key = _normalize_nonempty_string(
        normalized["runtime_metadata_root_key"],
        field_name=(
            f"{MIXED_MORPHOLOGY_INDEX_KEY}.roots.runtime_metadata_root_key"
        ),
    )
    state_summary_ids_payload = normalized["state_summary_ids"]
    if not isinstance(state_summary_ids_payload, Sequence) or isinstance(
        state_summary_ids_payload,
        (str, bytes),
    ):
        raise ValueError(
            f"{MIXED_MORPHOLOGY_INDEX_KEY}.roots.state_summary_ids must be a list."
        )
    state_summary_ids = [
        _normalize_nonempty_string(
            item,
            field_name=f"{MIXED_MORPHOLOGY_INDEX_KEY}.roots.state_summary_ids[{index}]",
        )
        for index, item in enumerate(state_summary_ids_payload)
    ]
    projection_time_array = _normalize_nonempty_string(
        normalized["projection_time_array"],
        field_name=f"{MIXED_MORPHOLOGY_INDEX_KEY}.roots.projection_time_array",
    )
    projection_trace_array = _normalize_nonempty_string(
        normalized["projection_trace_array"],
        field_name=f"{MIXED_MORPHOLOGY_INDEX_KEY}.roots.projection_trace_array",
    )
    projection_semantics = _normalize_nonempty_string(
        normalized["projection_semantics"],
        field_name=f"{MIXED_MORPHOLOGY_INDEX_KEY}.roots.projection_semantics",
    )
    shared_readout_ids_payload = normalized["shared_readout_ids"]
    if not isinstance(shared_readout_ids_payload, Sequence) or isinstance(
        shared_readout_ids_payload,
        (str, bytes),
    ):
        raise ValueError(
            f"{MIXED_MORPHOLOGY_INDEX_KEY}.roots.shared_readout_ids must be a list."
        )
    shared_readout_ids = [
        _normalize_identifier(
            item,
            field_name=f"{MIXED_MORPHOLOGY_INDEX_KEY}.roots.shared_readout_ids[{index}]",
        )
        for index, item in enumerate(shared_readout_ids_payload)
    ]
    unknown_readout_ids = sorted(set(shared_readout_ids) - set(readout_ids))
    if unknown_readout_ids:
        raise ValueError(
            f"{MIXED_MORPHOLOGY_INDEX_KEY}.roots.shared_readout_ids references "
            f"unknown readout IDs {unknown_readout_ids!r}."
        )
    return {
        "root_id": int(root_id),
        "morphology_class": morphology_class,
        "state_bundle_root_key": state_bundle_root_key,
        "runtime_metadata_root_key": runtime_metadata_root_key,
        "state_summary_ids": sorted(set(state_summary_ids)),
        "projection_time_array": projection_time_array,
        "projection_trace_array": projection_trace_array,
        "projection_semantics": projection_semantics,
        "shared_readout_ids": sorted(set(shared_readout_ids)),
    }


def _require_mixed_morphology_index(
    simulator_bundle: Mapping[str, Any],
) -> Mapping[str, Any]:
    mixed_morphology_index = simulator_bundle.get(MIXED_MORPHOLOGY_INDEX_KEY)
    if not isinstance(mixed_morphology_index, Mapping):
        raise ValueError(
            "Simulator result bundle metadata does not declare a mixed morphology index."
        )
    return mixed_morphology_index


def _mixed_morphology_root_record(
    mixed_morphology_index: Mapping[str, Any],
    *,
    root_id: int,
) -> Mapping[str, Any]:
    roots = mixed_morphology_index.get("roots")
    if not isinstance(roots, Sequence):
        raise ValueError("mixed morphology index roots must be a sequence.")
    for item in roots:
        if isinstance(item, Mapping) and int(item.get("root_id", -1)) == int(root_id):
            return item
    raise ValueError(f"Mixed morphology index does not contain root_id {root_id!r}.")


def _load_mixed_morphology_state_bundle(
    simulator_bundle: Mapping[str, Any],
    *,
    artifact_id: str,
) -> dict[str, Any]:
    extension_paths = {
        item["artifact_id"]: Path(item["path"]).resolve()
        for item in discover_simulator_extension_artifacts(simulator_bundle)
    }
    state_bundle_path = extension_paths.get(str(artifact_id))
    if state_bundle_path is None:
        raise ValueError(
            f"Simulator result bundle is missing mixed morphology artifact {artifact_id!r}."
        )
    with state_bundle_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError("Mixed morphology state bundle payload must be a mapping.")
    return copy.deepcopy(dict(payload))


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value


def _normalize_selected_assets(payload: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("selected_assets must be a list.")
    normalized = [parse_selected_asset_reference(item) for item in payload]
    if not normalized:
        raise ValueError("selected_assets must contain at least one referenced input artifact.")
    sorted_records = sorted(
        normalized,
        key=lambda item: (
            item["asset_role"],
            item["artifact_type"],
            item["artifact_id"] or "",
            item["bundle_id"] or "",
            item["path"],
        ),
    )
    seen_roles: set[str] = set()
    for item in sorted_records:
        asset_role = str(item["asset_role"])
        if asset_role in seen_roles:
            raise ValueError(f"selected_assets contains duplicate asset_role {asset_role!r}.")
        seen_roles.add(asset_role)
    return sorted_records


def _normalize_readout_catalog(payload: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("readout_catalog must be a list.")
    normalized = [parse_simulator_readout_definition(item) for item in payload]
    if not normalized:
        raise ValueError("readout_catalog must contain at least one shared readout definition.")
    sorted_records = sorted(
        normalized,
        key=lambda item: (
            item["readout_id"],
            item["scope"],
            item["aggregation"],
        ),
    )
    seen_readouts: set[str] = set()
    for item in sorted_records:
        readout_id = str(item["readout_id"])
        if readout_id in seen_readouts:
            raise ValueError(f"readout_catalog contains duplicate readout_id {readout_id!r}.")
        seen_readouts.add(readout_id)
    return sorted_records


def _extract_simulator_bundle_mapping(record: Mapping[str, Any]) -> Mapping[str, Any]:
    simulator_bundle = record.get("simulator_result_bundle")
    if isinstance(simulator_bundle, Mapping):
        return simulator_bundle
    return record


def _normalize_model_mode(value: Any) -> str:
    model_mode = _normalize_nonempty_string(value, field_name="arm_reference.model_mode")
    if model_mode not in SUPPORTED_MODEL_MODES:
        raise ValueError(
            "Unsupported arm_reference.model_mode "
            f"{model_mode!r}. Supported modes: {list(SUPPORTED_MODEL_MODES)!r}."
        )
    return model_mode


def _normalize_baseline_family(value: Any, *, model_mode: str) -> str | None:
    if model_mode == SURFACE_WAVE_MODEL_MODE:
        if value is None:
            return None
        raise ValueError("surface_wave arm_reference.baseline_family must be null.")
    baseline_family = _normalize_nonempty_string(
        value,
        field_name="arm_reference.baseline_family",
    )
    if baseline_family not in SUPPORTED_BASELINE_FAMILIES:
        raise ValueError(
            "Unsupported arm_reference.baseline_family "
            f"{baseline_family!r}. Supported families: {list(SUPPORTED_BASELINE_FAMILIES)!r}."
        )
    return baseline_family


def _normalize_comparison_tags(payload: Any) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("arm_reference.comparison_tags must be a list.")
    normalized = [
        _normalize_identifier(value, field_name=f"arm_reference.comparison_tags[{index}]")
        for index, value in enumerate(payload)
    ]
    return sorted(set(normalized))


def _normalize_artifact_scope(value: Any, *, field_name: str) -> str:
    artifact_scope = _normalize_nonempty_string(value, field_name=field_name)
    if artifact_scope not in SUPPORTED_ARTIFACT_SCOPES:
        raise ValueError(
            f"{field_name} must be one of {list(SUPPORTED_ARTIFACT_SCOPES)!r}, got {artifact_scope!r}."
        )
    return artifact_scope


def _normalize_extension_file_name(value: Any, *, field_name: str) -> str:
    file_name = _normalize_nonempty_string(value, field_name=field_name)
    path = Path(file_name)
    if path.name != file_name or file_name in {".", ".."}:
        raise ValueError(f"{field_name} must be a plain file name under the extension directory.")
    return file_name


def _normalize_optional_string(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _normalize_nonempty_string(value, field_name=field_name)
