from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import write_json
from .stimulus_contract import (
    ASSET_STATUS_READY,
    DEFAULT_HASH_ALGORITHM,
    _normalize_asset_status,
    _normalize_float,
    _normalize_identifier,
    _normalize_nonempty_string,
    _normalize_parameter_hash,
    _normalize_positive_float,
)


SURFACE_WAVE_MODEL_CONTRACT_VERSION = "surface_wave_model.v1"
SURFACE_WAVE_PARAMETER_SCHEMA_VERSION = "surface_wave_parameters.v1"
SURFACE_WAVE_MODEL_DESIGN_NOTE = "docs/surface_wave_model_design.md"
SURFACE_WAVE_MODEL_DESIGN_NOTE_VERSION = "surface_wave_design_note.v1"

DEFAULT_PROCESSED_SURFACE_WAVE_DIR = Path("data/processed/surface_wave_models")

ROADMAP_DAMPED_WAVE_MODEL_FAMILY = "damped_wave_system"
ROADMAP_DIFFUSION_FIELD_MODEL_FAMILY = "diffusion_like_neural_field"
ROADMAP_EXCITABLE_MEDIUM_MODEL_FAMILY = "excitable_medium"
ROADMAP_REACTION_DIFFUSION_MODEL_FAMILY = "reaction_diffusion_system"
ROADMAP_HYBRID_FIELD_READOUT_MODEL_FAMILY = "hybrid_field_readout_system"
ROADMAP_CANDIDATE_MODEL_FAMILIES = (
    ROADMAP_DAMPED_WAVE_MODEL_FAMILY,
    ROADMAP_DIFFUSION_FIELD_MODEL_FAMILY,
    ROADMAP_EXCITABLE_MEDIUM_MODEL_FAMILY,
    ROADMAP_REACTION_DIFFUSION_MODEL_FAMILY,
    ROADMAP_HYBRID_FIELD_READOUT_MODEL_FAMILY,
)
SELECTED_ROADMAP_MODEL_FAMILY = ROADMAP_HYBRID_FIELD_READOUT_MODEL_FAMILY

HYBRID_DAMPED_WAVE_RECOVERY_MODEL_FAMILY = "hybrid_damped_wave_recovery"
SUPPORTED_SURFACE_WAVE_MODEL_FAMILIES = (HYBRID_DAMPED_WAVE_RECOVERY_MODEL_FAMILY,)
DEFAULT_SURFACE_WAVE_MODEL_FAMILY = HYBRID_DAMPED_WAVE_RECOVERY_MODEL_FAMILY

SEMI_IMPLICIT_VELOCITY_SPLIT_SOLVER_FAMILY = "semi_implicit_velocity_split"
SUPPORTED_SURFACE_WAVE_SOLVER_FAMILIES = (SEMI_IMPLICIT_VELOCITY_SPLIT_SOLVER_FAMILY,)
DEFAULT_SURFACE_WAVE_SOLVER_FAMILY = SEMI_IMPLICIT_VELOCITY_SPLIT_SOLVER_FAMILY

LINEAR_VELOCITY_DAMPING_MODE = "linear_velocity_damping"
SUPPORTED_DAMPING_MODES = (LINEAR_VELOCITY_DAMPING_MODE,)
DEFAULT_DAMPING_MODE = LINEAR_VELOCITY_DAMPING_MODE

RECOVERY_DISABLED_MODE = "disabled"
ACTIVITY_DRIVEN_FIRST_ORDER_RECOVERY_MODE = "activity_driven_first_order"
POSITIVE_SURFACE_ACTIVATION_RECOVERY_DRIVE = "positive_surface_activation"
SUPPORTED_RECOVERY_MODES = (
    RECOVERY_DISABLED_MODE,
    ACTIVITY_DRIVEN_FIRST_ORDER_RECOVERY_MODE,
)
SUPPORTED_RECOVERY_DRIVE_SEMANTICS = (
    POSITIVE_SURFACE_ACTIVATION_RECOVERY_DRIVE,
)
DEFAULT_RECOVERY_MODE = RECOVERY_DISABLED_MODE

NONLINEARITY_DISABLED_MODE = "none"
TANH_SOFT_CLIP_NONLINEARITY_MODE = "tanh_soft_clip"
SUPPORTED_NONLINEARITY_MODES = (
    NONLINEARITY_DISABLED_MODE,
    TANH_SOFT_CLIP_NONLINEARITY_MODE,
)
DEFAULT_NONLINEARITY_MODE = NONLINEARITY_DISABLED_MODE

ISOTROPIC_ANISOTROPY_MODE = "isotropic"
OPERATOR_EMBEDDED_ANISOTROPY_MODE = "operator_embedded"
MILESTONE_6_OPERATOR_METADATA_SOURCE = "milestone_6_operator_metadata"
SUPPORTED_ANISOTROPY_MODES = (
    ISOTROPIC_ANISOTROPY_MODE,
    OPERATOR_EMBEDDED_ANISOTROPY_MODE,
)
SUPPORTED_ANISOTROPY_OPERATOR_SOURCES = (
    MILESTONE_6_OPERATOR_METADATA_SOURCE,
)
DEFAULT_ANISOTROPY_MODE = ISOTROPIC_ANISOTROPY_MODE

BRANCHING_DISABLED_MODE = "disabled"
DESCRIPTOR_SCALED_DAMPING_BRANCHING_MODE = "descriptor_scaled_damping"
GEOMETRY_DESCRIPTOR_BRANCHING_SOURCE = "geometry_descriptors"
EXTRA_LOCAL_DAMPING_BRANCHING_RESPONSE = "extra_local_damping"
SUPPORTED_BRANCHING_MODES = (
    BRANCHING_DISABLED_MODE,
    DESCRIPTOR_SCALED_DAMPING_BRANCHING_MODE,
)
SUPPORTED_BRANCHING_DESCRIPTOR_SOURCES = (
    GEOMETRY_DESCRIPTOR_BRANCHING_SOURCE,
)
SUPPORTED_BRANCHING_JUNCTION_RESPONSES = (
    EXTRA_LOCAL_DAMPING_BRANCHING_RESPONSE,
)
DEFAULT_BRANCHING_MODE = BRANCHING_DISABLED_MODE

COUPLING_ANCHOR_CURRENT_SOURCE_MODE = "coupling_anchor_current"
SUPPORTED_SYNAPTIC_SOURCE_MODES = (COUPLING_ANCHOR_CURRENT_SOURCE_MODE,)
DEFAULT_SYNAPTIC_SOURCE_MODE = COUPLING_ANCHOR_CURRENT_SOURCE_MODE

SURFACE_ACTIVATION_STATE_ID = "surface_activation"
SURFACE_VELOCITY_STATE_ID = "surface_velocity"
RECOVERY_STATE_ID = "recovery_state"
DEFAULT_SURFACE_WAVE_STATE_LAYOUT = "surface_activation_velocity_optional_recovery"
DEFAULT_SURFACE_WAVE_READOUT_STATE = SURFACE_ACTIVATION_STATE_ID
DEFAULT_SURFACE_WAVE_PARAMETER_PRESET = "milestone_10_default"

METADATA_JSON_KEY = "metadata_json"

_TOP_LEVEL_ALLOWED_KEYS = {
    "parameter_preset",
    "solver",
    "propagation",
    "damping",
    "recovery",
    "synaptic_source",
    "nonlinearity",
    "anisotropy",
    "branching",
}
_SOLVER_ALLOWED_KEYS = {
    "family",
    "shared_timebase_mode",
    "stability_policy",
    "cfl_safety_factor",
}
_PROPAGATION_ALLOWED_KEYS = {
    "operator_family",
    "wave_speed_sq_scale",
    "restoring_strength_per_ms2",
}
_DAMPING_ALLOWED_KEYS = {
    "mode",
    "gamma_per_ms",
}
_RECOVERY_ALLOWED_KEYS = {
    "mode",
    "time_constant_ms",
    "drive_gain",
    "coupling_strength_per_ms2",
    "baseline",
    "drive_semantics",
}
_SYNAPTIC_SOURCE_ALLOWED_KEYS = {
    "mode",
    "injection_target_state",
    "readout_state",
    "sign_semantics",
    "delay_semantics",
    "aggregation_semantics",
    "spatial_support",
    "normalization",
}
_NONLINEARITY_ALLOWED_KEYS = {
    "mode",
    "activation_scale",
}
_ANISOTROPY_ALLOWED_KEYS = {
    "mode",
    "operator_source",
    "strength_scale",
}
_BRANCHING_ALLOWED_KEYS = {
    "mode",
    "descriptor_source",
    "gain",
    "junction_response",
}


@dataclass(frozen=True)
class SurfaceWaveContractPaths:
    processed_surface_wave_dir: Path
    bundle_root_directory: Path


@dataclass(frozen=True)
class SurfaceWaveModelPaths:
    model_family: str
    parameter_hash: str
    bundle_directory: Path
    metadata_json_path: Path

    @property
    def bundle_id(self) -> str:
        return (
            f"{SURFACE_WAVE_MODEL_CONTRACT_VERSION}:"
            f"{self.model_family}:{self.parameter_hash}"
        )

    def asset_paths(self) -> dict[str, Path]:
        return {
            METADATA_JSON_KEY: self.metadata_json_path,
        }


def build_surface_wave_contract_paths(
    processed_surface_wave_dir: str | Path = DEFAULT_PROCESSED_SURFACE_WAVE_DIR,
) -> SurfaceWaveContractPaths:
    surface_wave_dir = Path(processed_surface_wave_dir).resolve()
    return SurfaceWaveContractPaths(
        processed_surface_wave_dir=surface_wave_dir,
        bundle_root_directory=surface_wave_dir / "bundles",
    )


def build_surface_wave_model_paths(
    *,
    model_family: str = DEFAULT_SURFACE_WAVE_MODEL_FAMILY,
    processed_surface_wave_dir: str | Path = DEFAULT_PROCESSED_SURFACE_WAVE_DIR,
    parameter_hash: str | None = None,
    parameter_bundle: Mapping[str, Any] | None = None,
) -> SurfaceWaveModelPaths:
    normalized_model_family = _normalize_surface_wave_model_family(model_family)
    resolved_parameter_hash = _resolve_surface_wave_parameter_hash(
        model_family=normalized_model_family,
        parameter_hash=parameter_hash,
        parameter_bundle=parameter_bundle,
    )
    contract_paths = build_surface_wave_contract_paths(processed_surface_wave_dir)
    bundle_directory = (
        contract_paths.bundle_root_directory
        / normalized_model_family
        / resolved_parameter_hash
    )
    return SurfaceWaveModelPaths(
        model_family=normalized_model_family,
        parameter_hash=resolved_parameter_hash,
        bundle_directory=bundle_directory,
        metadata_json_path=bundle_directory / "surface_wave_model.json",
    )


def build_surface_wave_contract_manifest_metadata(
    *,
    processed_surface_wave_dir: str | Path = DEFAULT_PROCESSED_SURFACE_WAVE_DIR,
) -> dict[str, Any]:
    contract_paths = build_surface_wave_contract_paths(processed_surface_wave_dir)
    return {
        "version": SURFACE_WAVE_MODEL_CONTRACT_VERSION,
        "parameter_schema_version": SURFACE_WAVE_PARAMETER_SCHEMA_VERSION,
        "design_note": SURFACE_WAVE_MODEL_DESIGN_NOTE,
        "design_note_version": SURFACE_WAVE_MODEL_DESIGN_NOTE_VERSION,
        "recognized_roadmap_model_families": list(ROADMAP_CANDIDATE_MODEL_FAMILIES),
        "selected_roadmap_model_family": SELECTED_ROADMAP_MODEL_FAMILY,
        "default_model_family": DEFAULT_SURFACE_WAVE_MODEL_FAMILY,
        "supported_model_families": list(SUPPORTED_SURFACE_WAVE_MODEL_FAMILIES),
        "default_state_layout": DEFAULT_SURFACE_WAVE_STATE_LAYOUT,
        "default_readout_state": DEFAULT_SURFACE_WAVE_READOUT_STATE,
        "default_solver_family": DEFAULT_SURFACE_WAVE_SOLVER_FAMILY,
        "supported_solver_families": list(SUPPORTED_SURFACE_WAVE_SOLVER_FAMILIES),
        "default_damping_mode": DEFAULT_DAMPING_MODE,
        "supported_damping_modes": list(SUPPORTED_DAMPING_MODES),
        "default_recovery_mode": DEFAULT_RECOVERY_MODE,
        "supported_recovery_modes": list(SUPPORTED_RECOVERY_MODES),
        "default_nonlinearity_mode": DEFAULT_NONLINEARITY_MODE,
        "supported_nonlinearity_modes": list(SUPPORTED_NONLINEARITY_MODES),
        "default_anisotropy_mode": DEFAULT_ANISOTROPY_MODE,
        "supported_anisotropy_modes": list(SUPPORTED_ANISOTROPY_MODES),
        "default_branching_mode": DEFAULT_BRANCHING_MODE,
        "supported_branching_modes": list(SUPPORTED_BRANCHING_MODES),
        "default_synaptic_source_mode": DEFAULT_SYNAPTIC_SOURCE_MODE,
        "supported_synaptic_source_modes": list(SUPPORTED_SYNAPTIC_SOURCE_MODES),
        "default_parameter_preset": DEFAULT_SURFACE_WAVE_PARAMETER_PRESET,
        "default_state_variables": default_surface_wave_state_variables(),
        "bundle_root_directory": str(contract_paths.bundle_root_directory),
    }


def default_surface_wave_state_variables(
    model_family: str = DEFAULT_SURFACE_WAVE_MODEL_FAMILY,
) -> list[dict[str, Any]]:
    normalized_model_family = _normalize_surface_wave_model_family(model_family)
    if normalized_model_family != HYBRID_DAMPED_WAVE_RECOVERY_MODEL_FAMILY:
        raise ValueError(
            f"Unsupported surface-wave model family {normalized_model_family!r}."
        )
    return [
        {
            "state_id": SURFACE_ACTIVATION_STATE_ID,
            "symbol": "u",
            "units": "activation_au",
            "kind": "distributed_surface_field",
            "description": (
                "Primary morphology-bound activation field that later shared readouts "
                "sample and summarize."
            ),
            "enabled_by_default": True,
        },
        {
            "state_id": SURFACE_VELOCITY_STATE_ID,
            "symbol": "v",
            "units": "activation_au_per_ms",
            "kind": "distributed_surface_auxiliary",
            "description": (
                "Time derivative of the primary surface activation used by the "
                "damped-wave stepping scheme."
            ),
            "enabled_by_default": True,
        },
        {
            "state_id": RECOVERY_STATE_ID,
            "symbol": "r",
            "units": "unitless",
            "kind": "distributed_optional_auxiliary",
            "description": (
                "Optional refractory or recovery budget that can add a delayed local "
                "sink without changing the shared readout state."
            ),
            "enabled_by_default": False,
        },
    ]


def default_surface_wave_parameter_bundle(
    model_family: str = DEFAULT_SURFACE_WAVE_MODEL_FAMILY,
) -> dict[str, Any]:
    normalized_model_family = _normalize_surface_wave_model_family(model_family)
    if normalized_model_family != HYBRID_DAMPED_WAVE_RECOVERY_MODEL_FAMILY:
        raise ValueError(
            f"Unsupported surface-wave model family {normalized_model_family!r}."
        )
    return {
        "parameter_preset": DEFAULT_SURFACE_WAVE_PARAMETER_PRESET,
        "solver": {
            "family": DEFAULT_SURFACE_WAVE_SOLVER_FAMILY,
            "shared_timebase_mode": "fixed_step_uniform_shared_outputs",
            "stability_policy": "spectral_radius_cfl_bound",
            "cfl_safety_factor": 0.5,
        },
        "propagation": {
            "operator_family": "mass_normalized_surface_laplacian",
            "wave_speed_sq_scale": 1.0,
            "restoring_strength_per_ms2": 0.05,
        },
        "damping": {
            "mode": DEFAULT_DAMPING_MODE,
            "gamma_per_ms": 0.2,
        },
        "recovery": {
            "mode": DEFAULT_RECOVERY_MODE,
            "time_constant_ms": 12.0,
            "drive_gain": 0.25,
            "coupling_strength_per_ms2": 0.1,
            "baseline": 0.0,
            "drive_semantics": POSITIVE_SURFACE_ACTIVATION_RECOVERY_DRIVE,
        },
        "synaptic_source": {
            "mode": DEFAULT_SYNAPTIC_SOURCE_MODE,
            "injection_target_state": SURFACE_VELOCITY_STATE_ID,
            "readout_state": SURFACE_ACTIVATION_STATE_ID,
            "sign_semantics": "from_coupling_bundle_signed_weight",
            "delay_semantics": "from_coupling_bundle_delay_ms",
            "aggregation_semantics": "sum_preserving_sign_and_delay_bins",
            "spatial_support": "postsynaptic_patch_cloud",
            "normalization": "preserve_total_signed_weight",
        },
        "nonlinearity": {
            "mode": DEFAULT_NONLINEARITY_MODE,
            "activation_scale": 1.0,
        },
        "anisotropy": {
            "mode": DEFAULT_ANISOTROPY_MODE,
            "operator_source": MILESTONE_6_OPERATOR_METADATA_SOURCE,
            "strength_scale": 1.0,
        },
        "branching": {
            "mode": DEFAULT_BRANCHING_MODE,
            "descriptor_source": GEOMETRY_DESCRIPTOR_BRANCHING_SOURCE,
            "gain": 0.0,
            "junction_response": EXTRA_LOCAL_DAMPING_BRANCHING_RESPONSE,
        },
    }


def normalize_surface_wave_parameter_bundle(
    payload: Mapping[str, Any] | None,
    *,
    model_family: str = DEFAULT_SURFACE_WAVE_MODEL_FAMILY,
) -> dict[str, Any]:
    normalized_model_family = _normalize_surface_wave_model_family(model_family)
    defaults = default_surface_wave_parameter_bundle(normalized_model_family)
    raw_payload = dict(payload or {})
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError("surface_wave must be a mapping when provided.")
    unknown_keys = sorted(set(raw_payload) - _TOP_LEVEL_ALLOWED_KEYS)
    if unknown_keys:
        raise ValueError(
            "surface_wave contains unsupported keys: "
            f"{unknown_keys!r}."
        )

    normalized = copy.deepcopy(defaults)
    if "parameter_preset" in raw_payload:
        normalized["parameter_preset"] = _normalize_identifier(
            raw_payload["parameter_preset"],
            field_name="surface_wave.parameter_preset",
        )
    if "solver" in raw_payload:
        normalized["solver"] = _normalize_surface_wave_solver(raw_payload["solver"])
    if "propagation" in raw_payload:
        normalized["propagation"] = _normalize_surface_wave_propagation(
            raw_payload["propagation"]
        )
    if "damping" in raw_payload:
        normalized["damping"] = _normalize_surface_wave_damping(raw_payload["damping"])
    if "recovery" in raw_payload:
        normalized["recovery"] = _normalize_surface_wave_recovery(raw_payload["recovery"])
    if "synaptic_source" in raw_payload:
        normalized["synaptic_source"] = _normalize_surface_wave_synaptic_source(
            raw_payload["synaptic_source"]
        )
    if "nonlinearity" in raw_payload:
        normalized["nonlinearity"] = _normalize_surface_wave_nonlinearity(
            raw_payload["nonlinearity"]
        )
    if "anisotropy" in raw_payload:
        normalized["anisotropy"] = _normalize_surface_wave_anisotropy(raw_payload["anisotropy"])
    if "branching" in raw_payload:
        normalized["branching"] = _normalize_surface_wave_branching(raw_payload["branching"])
    _validate_surface_wave_parameter_bundle(normalized)
    return normalized


def build_surface_wave_parameter_hash(
    *,
    model_family: str = DEFAULT_SURFACE_WAVE_MODEL_FAMILY,
    parameter_bundle: Mapping[str, Any],
) -> str:
    normalized_model_family = _normalize_surface_wave_model_family(model_family)
    normalized_parameters = normalize_surface_wave_parameter_bundle(
        parameter_bundle,
        model_family=normalized_model_family,
    )
    reproducibility_payload = {
        "contract_version": SURFACE_WAVE_MODEL_CONTRACT_VERSION,
        "parameter_schema_version": SURFACE_WAVE_PARAMETER_SCHEMA_VERSION,
        "model_family": normalized_model_family,
        "state_variables": default_surface_wave_state_variables(normalized_model_family),
        "parameters": {
            key: copy.deepcopy(value)
            for key, value in normalized_parameters.items()
            if key != "parameter_preset"
        },
    }
    serialized = json.dumps(
        reproducibility_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_surface_wave_model_metadata(
    *,
    model_family: str = DEFAULT_SURFACE_WAVE_MODEL_FAMILY,
    processed_surface_wave_dir: str | Path = DEFAULT_PROCESSED_SURFACE_WAVE_DIR,
    parameter_bundle: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_model_family = _normalize_surface_wave_model_family(model_family)
    normalized_parameter_bundle = normalize_surface_wave_parameter_bundle(
        parameter_bundle,
        model_family=normalized_model_family,
    )
    parameter_hash = build_surface_wave_parameter_hash(
        model_family=normalized_model_family,
        parameter_bundle=normalized_parameter_bundle,
    )
    model_paths = build_surface_wave_model_paths(
        model_family=normalized_model_family,
        processed_surface_wave_dir=processed_surface_wave_dir,
        parameter_hash=parameter_hash,
    )
    state_variables = default_surface_wave_state_variables(normalized_model_family)
    return {
        "contract_version": SURFACE_WAVE_MODEL_CONTRACT_VERSION,
        "parameter_schema_version": SURFACE_WAVE_PARAMETER_SCHEMA_VERSION,
        "design_note": SURFACE_WAVE_MODEL_DESIGN_NOTE,
        "design_note_version": SURFACE_WAVE_MODEL_DESIGN_NOTE_VERSION,
        "bundle_id": model_paths.bundle_id,
        "roadmap_model_family": SELECTED_ROADMAP_MODEL_FAMILY,
        "model_family": normalized_model_family,
        "state_layout": DEFAULT_SURFACE_WAVE_STATE_LAYOUT,
        "readout_state": DEFAULT_SURFACE_WAVE_READOUT_STATE,
        "state_variables": state_variables,
        "parameter_preset": normalized_parameter_bundle["parameter_preset"],
        "parameter_hash": parameter_hash,
        "parameter_hash_algorithm": DEFAULT_HASH_ALGORITHM,
        "solver_family": normalized_parameter_bundle["solver"]["family"],
        "recovery_mode": normalized_parameter_bundle["recovery"]["mode"],
        "nonlinearity_mode": normalized_parameter_bundle["nonlinearity"]["mode"],
        "anisotropy_mode": normalized_parameter_bundle["anisotropy"]["mode"],
        "branching_mode": normalized_parameter_bundle["branching"]["mode"],
        "synaptic_source_mode": normalized_parameter_bundle["synaptic_source"]["mode"],
        "parameter_bundle": normalized_parameter_bundle,
        "assets": {
            METADATA_JSON_KEY: {
                "path": str(model_paths.metadata_json_path),
                "status": ASSET_STATUS_READY,
            }
        },
    }


def build_surface_wave_model_reference(bundle_metadata: Mapping[str, Any]) -> dict[str, Any]:
    normalized = parse_surface_wave_model_metadata(bundle_metadata)
    return {
        "contract_version": normalized["contract_version"],
        "model_family": normalized["model_family"],
        "parameter_hash": normalized["parameter_hash"],
        "bundle_id": normalized["bundle_id"],
    }


def parse_surface_wave_model_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Surface-wave model metadata must be a mapping.")

    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "parameter_schema_version",
        "design_note",
        "design_note_version",
        "bundle_id",
        "roadmap_model_family",
        "model_family",
        "state_layout",
        "readout_state",
        "state_variables",
        "parameter_preset",
        "parameter_hash",
        "parameter_hash_algorithm",
        "solver_family",
        "recovery_mode",
        "nonlinearity_mode",
        "anisotropy_mode",
        "branching_mode",
        "synaptic_source_mode",
        "parameter_bundle",
        "assets",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "Surface-wave model metadata is missing required fields: "
            f"{missing_fields}"
        )
    if normalized["contract_version"] != SURFACE_WAVE_MODEL_CONTRACT_VERSION:
        raise ValueError(
            "Surface-wave model metadata contract_version does not match "
            f"{SURFACE_WAVE_MODEL_CONTRACT_VERSION!r}."
        )
    if normalized["parameter_schema_version"] != SURFACE_WAVE_PARAMETER_SCHEMA_VERSION:
        raise ValueError(
            "Surface-wave model metadata parameter_schema_version does not match "
            f"{SURFACE_WAVE_PARAMETER_SCHEMA_VERSION!r}."
        )
    roadmap_model_family = _normalize_identifier(
        normalized["roadmap_model_family"],
        field_name="roadmap_model_family",
    )
    if roadmap_model_family != SELECTED_ROADMAP_MODEL_FAMILY:
        raise ValueError(
            "Surface-wave model metadata roadmap_model_family must be "
            f"{SELECTED_ROADMAP_MODEL_FAMILY!r}."
        )
    normalized["roadmap_model_family"] = roadmap_model_family
    normalized["model_family"] = _normalize_surface_wave_model_family(normalized["model_family"])
    normalized["state_layout"] = _normalize_nonempty_string(
        normalized["state_layout"],
        field_name="state_layout",
    )
    if normalized["state_layout"] != DEFAULT_SURFACE_WAVE_STATE_LAYOUT:
        raise ValueError(
            "Unsupported surface-wave state_layout "
            f"{normalized['state_layout']!r}."
        )
    normalized["readout_state"] = _normalize_nonempty_string(
        normalized["readout_state"],
        field_name="readout_state",
    )
    if normalized["readout_state"] != DEFAULT_SURFACE_WAVE_READOUT_STATE:
        raise ValueError(
            "Unsupported surface-wave readout_state "
            f"{normalized['readout_state']!r}."
        )
    normalized["state_variables"] = _normalize_surface_wave_state_variables_payload(
        normalized["state_variables"],
        model_family=normalized["model_family"],
    )
    normalized["parameter_preset"] = _normalize_identifier(
        normalized["parameter_preset"],
        field_name="parameter_preset",
    )
    normalized["parameter_hash"] = _normalize_parameter_hash(normalized["parameter_hash"])
    normalized["parameter_hash_algorithm"] = _normalize_nonempty_string(
        normalized["parameter_hash_algorithm"],
        field_name="parameter_hash_algorithm",
    )
    if normalized["parameter_hash_algorithm"] != DEFAULT_HASH_ALGORITHM:
        raise ValueError(
            "Unsupported surface-wave parameter_hash_algorithm "
            f"{normalized['parameter_hash_algorithm']!r}."
        )
    normalized["solver_family"] = _normalize_solver_family(normalized["solver_family"])
    normalized["recovery_mode"] = _normalize_recovery_mode(normalized["recovery_mode"])
    normalized["nonlinearity_mode"] = _normalize_nonlinearity_mode(
        normalized["nonlinearity_mode"]
    )
    normalized["anisotropy_mode"] = _normalize_anisotropy_mode(normalized["anisotropy_mode"])
    normalized["branching_mode"] = _normalize_branching_mode(normalized["branching_mode"])
    normalized["synaptic_source_mode"] = _normalize_synaptic_source_mode(
        normalized["synaptic_source_mode"]
    )
    normalized["parameter_bundle"] = normalize_surface_wave_parameter_bundle(
        normalized["parameter_bundle"],
        model_family=normalized["model_family"],
    )
    normalized["assets"] = _normalize_surface_wave_assets(normalized["assets"])

    expected_parameter_hash = build_surface_wave_parameter_hash(
        model_family=normalized["model_family"],
        parameter_bundle=normalized["parameter_bundle"],
    )
    if normalized["parameter_hash"] != expected_parameter_hash:
        raise ValueError(
            "Surface-wave model metadata parameter_hash does not match the "
            "canonical normalized parameter bundle."
        )
    expected_bundle_id = (
        f"{SURFACE_WAVE_MODEL_CONTRACT_VERSION}:"
        f"{normalized['model_family']}:{normalized['parameter_hash']}"
    )
    if normalized["bundle_id"] != expected_bundle_id:
        raise ValueError(
            "Surface-wave model metadata bundle_id does not match the canonical "
            "family/hash tuple."
        )
    if normalized["solver_family"] != normalized["parameter_bundle"]["solver"]["family"]:
        raise ValueError("solver_family must match parameter_bundle.solver.family.")
    if normalized["recovery_mode"] != normalized["parameter_bundle"]["recovery"]["mode"]:
        raise ValueError("recovery_mode must match parameter_bundle.recovery.mode.")
    if normalized["nonlinearity_mode"] != normalized["parameter_bundle"]["nonlinearity"]["mode"]:
        raise ValueError(
            "nonlinearity_mode must match parameter_bundle.nonlinearity.mode."
        )
    if normalized["anisotropy_mode"] != normalized["parameter_bundle"]["anisotropy"]["mode"]:
        raise ValueError("anisotropy_mode must match parameter_bundle.anisotropy.mode.")
    if normalized["branching_mode"] != normalized["parameter_bundle"]["branching"]["mode"]:
        raise ValueError("branching_mode must match parameter_bundle.branching.mode.")
    if normalized["synaptic_source_mode"] != normalized["parameter_bundle"]["synaptic_source"]["mode"]:
        raise ValueError(
            "synaptic_source_mode must match parameter_bundle.synaptic_source.mode."
        )
    return normalized


def load_surface_wave_model_metadata(metadata_path: str | Path) -> dict[str, Any]:
    path = Path(metadata_path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_surface_wave_model_metadata(payload)


def write_surface_wave_model_metadata(
    bundle_metadata: Mapping[str, Any],
    metadata_path: str | Path | None = None,
) -> Path:
    normalized = parse_surface_wave_model_metadata(bundle_metadata)
    output_path = (
        Path(metadata_path).resolve()
        if metadata_path is not None
        else Path(normalized["assets"][METADATA_JSON_KEY]["path"]).resolve()
    )
    return write_json(normalized, output_path)


def discover_surface_wave_model_paths(record: Mapping[str, Any]) -> dict[str, Path]:
    surface_wave_model = _extract_surface_wave_model_mapping(record)
    assets = surface_wave_model.get("assets")
    if not isinstance(assets, Mapping):
        raise ValueError("Surface-wave model assets must be a mapping.")
    asset_record = assets.get(METADATA_JSON_KEY)
    if not isinstance(asset_record, Mapping):
        raise ValueError("Surface-wave model metadata asset is missing.")
    asset_path = asset_record.get("path")
    if not isinstance(asset_path, str) or not asset_path:
        raise ValueError("Surface-wave model metadata asset is missing a usable path.")
    return {
        METADATA_JSON_KEY: Path(asset_path).resolve(),
    }


def resolve_surface_wave_model_metadata_path(
    *,
    model_family: str = DEFAULT_SURFACE_WAVE_MODEL_FAMILY,
    processed_surface_wave_dir: str | Path = DEFAULT_PROCESSED_SURFACE_WAVE_DIR,
    parameter_hash: str | None = None,
    parameter_bundle: Mapping[str, Any] | None = None,
) -> Path:
    model_paths = build_surface_wave_model_paths(
        model_family=model_family,
        processed_surface_wave_dir=processed_surface_wave_dir,
        parameter_hash=parameter_hash,
        parameter_bundle=parameter_bundle,
    )
    return model_paths.metadata_json_path


def _extract_surface_wave_model_mapping(record: Mapping[str, Any]) -> Mapping[str, Any]:
    surface_wave_model = record.get("surface_wave_model")
    if isinstance(surface_wave_model, Mapping):
        return surface_wave_model
    return record


def _resolve_surface_wave_parameter_hash(
    *,
    model_family: str,
    parameter_hash: str | None,
    parameter_bundle: Mapping[str, Any] | None,
) -> str:
    if parameter_hash is not None:
        return _normalize_parameter_hash(parameter_hash)
    if parameter_bundle is None:
        raise ValueError(
            "parameter_hash was not provided and parameter_bundle is required to compute it."
        )
    return build_surface_wave_parameter_hash(
        model_family=model_family,
        parameter_bundle=parameter_bundle,
    )


def _normalize_surface_wave_solver(payload: Any) -> dict[str, Any]:
    defaults = copy.deepcopy(default_surface_wave_parameter_bundle()["solver"])
    if not isinstance(payload, Mapping):
        raise ValueError("surface_wave.solver must be a mapping when provided.")
    raw_payload = dict(payload)
    unknown_keys = sorted(set(raw_payload) - _SOLVER_ALLOWED_KEYS)
    if unknown_keys:
        raise ValueError(
            "surface_wave.solver contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    if "family" in raw_payload:
        defaults["family"] = _normalize_solver_family(raw_payload["family"])
    if "shared_timebase_mode" in raw_payload:
        defaults["shared_timebase_mode"] = _normalize_nonempty_string(
            raw_payload["shared_timebase_mode"],
            field_name="surface_wave.solver.shared_timebase_mode",
        )
    if "stability_policy" in raw_payload:
        defaults["stability_policy"] = _normalize_nonempty_string(
            raw_payload["stability_policy"],
            field_name="surface_wave.solver.stability_policy",
        )
    if "cfl_safety_factor" in raw_payload:
        defaults["cfl_safety_factor"] = _normalize_unit_interval_positive(
            raw_payload["cfl_safety_factor"],
            field_name="surface_wave.solver.cfl_safety_factor",
        )
    return defaults


def _normalize_surface_wave_propagation(payload: Any) -> dict[str, Any]:
    defaults = copy.deepcopy(default_surface_wave_parameter_bundle()["propagation"])
    if not isinstance(payload, Mapping):
        raise ValueError("surface_wave.propagation must be a mapping when provided.")
    raw_payload = dict(payload)
    unknown_keys = sorted(set(raw_payload) - _PROPAGATION_ALLOWED_KEYS)
    if unknown_keys:
        raise ValueError(
            "surface_wave.propagation contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    if "operator_family" in raw_payload:
        defaults["operator_family"] = _normalize_identifier(
            raw_payload["operator_family"],
            field_name="surface_wave.propagation.operator_family",
        )
    if "wave_speed_sq_scale" in raw_payload:
        defaults["wave_speed_sq_scale"] = _normalize_positive_float(
            raw_payload["wave_speed_sq_scale"],
            field_name="surface_wave.propagation.wave_speed_sq_scale",
        )
    if "restoring_strength_per_ms2" in raw_payload:
        defaults["restoring_strength_per_ms2"] = _normalize_nonnegative_float(
            raw_payload["restoring_strength_per_ms2"],
            field_name="surface_wave.propagation.restoring_strength_per_ms2",
        )
    return defaults


def _normalize_surface_wave_damping(payload: Any) -> dict[str, Any]:
    defaults = copy.deepcopy(default_surface_wave_parameter_bundle()["damping"])
    if not isinstance(payload, Mapping):
        raise ValueError("surface_wave.damping must be a mapping when provided.")
    raw_payload = dict(payload)
    unknown_keys = sorted(set(raw_payload) - _DAMPING_ALLOWED_KEYS)
    if unknown_keys:
        raise ValueError(
            "surface_wave.damping contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    if "mode" in raw_payload:
        defaults["mode"] = _normalize_damping_mode(raw_payload["mode"])
    if "gamma_per_ms" in raw_payload:
        defaults["gamma_per_ms"] = _normalize_nonnegative_float(
            raw_payload["gamma_per_ms"],
            field_name="surface_wave.damping.gamma_per_ms",
        )
    return defaults


def _normalize_surface_wave_recovery(payload: Any) -> dict[str, Any]:
    defaults = copy.deepcopy(default_surface_wave_parameter_bundle()["recovery"])
    if not isinstance(payload, Mapping):
        raise ValueError("surface_wave.recovery must be a mapping when provided.")
    raw_payload = dict(payload)
    unknown_keys = sorted(set(raw_payload) - _RECOVERY_ALLOWED_KEYS)
    if unknown_keys:
        raise ValueError(
            "surface_wave.recovery contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    if "mode" in raw_payload:
        defaults["mode"] = _normalize_recovery_mode(raw_payload["mode"])
    if "time_constant_ms" in raw_payload:
        defaults["time_constant_ms"] = _normalize_positive_float(
            raw_payload["time_constant_ms"],
            field_name="surface_wave.recovery.time_constant_ms",
        )
    if "drive_gain" in raw_payload:
        defaults["drive_gain"] = _normalize_nonnegative_float(
            raw_payload["drive_gain"],
            field_name="surface_wave.recovery.drive_gain",
        )
    if "coupling_strength_per_ms2" in raw_payload:
        defaults["coupling_strength_per_ms2"] = _normalize_nonnegative_float(
            raw_payload["coupling_strength_per_ms2"],
            field_name="surface_wave.recovery.coupling_strength_per_ms2",
        )
    if "baseline" in raw_payload:
        defaults["baseline"] = _normalize_float(
            raw_payload["baseline"],
            field_name="surface_wave.recovery.baseline",
        )
    if "drive_semantics" in raw_payload:
        defaults["drive_semantics"] = _normalize_nonempty_string(
            raw_payload["drive_semantics"],
            field_name="surface_wave.recovery.drive_semantics",
        )
    if defaults["drive_semantics"] not in SUPPORTED_RECOVERY_DRIVE_SEMANTICS:
        raise ValueError(
            "surface_wave.recovery.drive_semantics must be one of "
            f"{list(SUPPORTED_RECOVERY_DRIVE_SEMANTICS)!r}, got "
            f"{defaults['drive_semantics']!r}."
        )
    if defaults["mode"] == RECOVERY_DISABLED_MODE:
        defaults["coupling_strength_per_ms2"] = 0.0
        defaults["drive_gain"] = 0.0
    return defaults


def _normalize_surface_wave_synaptic_source(payload: Any) -> dict[str, Any]:
    defaults = copy.deepcopy(default_surface_wave_parameter_bundle()["synaptic_source"])
    if not isinstance(payload, Mapping):
        raise ValueError("surface_wave.synaptic_source must be a mapping when provided.")
    raw_payload = dict(payload)
    unknown_keys = sorted(set(raw_payload) - _SYNAPTIC_SOURCE_ALLOWED_KEYS)
    if unknown_keys:
        raise ValueError(
            "surface_wave.synaptic_source contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    if "mode" in raw_payload:
        defaults["mode"] = _normalize_synaptic_source_mode(raw_payload["mode"])
    for field_name in (
        "injection_target_state",
        "readout_state",
        "sign_semantics",
        "delay_semantics",
        "aggregation_semantics",
        "spatial_support",
        "normalization",
    ):
        if field_name in raw_payload:
            defaults[field_name] = _normalize_nonempty_string(
                raw_payload[field_name],
                field_name=f"surface_wave.synaptic_source.{field_name}",
            )
    if defaults["injection_target_state"] != SURFACE_VELOCITY_STATE_ID:
        raise ValueError(
            "surface_wave.synaptic_source.injection_target_state must be "
            f"{SURFACE_VELOCITY_STATE_ID!r}."
        )
    if defaults["readout_state"] != SURFACE_ACTIVATION_STATE_ID:
        raise ValueError(
            "surface_wave.synaptic_source.readout_state must be "
            f"{SURFACE_ACTIVATION_STATE_ID!r}."
        )
    return defaults


def _normalize_surface_wave_nonlinearity(payload: Any) -> dict[str, Any]:
    defaults = copy.deepcopy(default_surface_wave_parameter_bundle()["nonlinearity"])
    if not isinstance(payload, Mapping):
        raise ValueError("surface_wave.nonlinearity must be a mapping when provided.")
    raw_payload = dict(payload)
    unknown_keys = sorted(set(raw_payload) - _NONLINEARITY_ALLOWED_KEYS)
    if unknown_keys:
        raise ValueError(
            "surface_wave.nonlinearity contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    if "mode" in raw_payload:
        defaults["mode"] = _normalize_nonlinearity_mode(raw_payload["mode"])
    if "activation_scale" in raw_payload:
        defaults["activation_scale"] = _normalize_positive_float(
            raw_payload["activation_scale"],
            field_name="surface_wave.nonlinearity.activation_scale",
        )
    return defaults


def _normalize_surface_wave_anisotropy(payload: Any) -> dict[str, Any]:
    defaults = copy.deepcopy(default_surface_wave_parameter_bundle()["anisotropy"])
    if not isinstance(payload, Mapping):
        raise ValueError("surface_wave.anisotropy must be a mapping when provided.")
    raw_payload = dict(payload)
    unknown_keys = sorted(set(raw_payload) - _ANISOTROPY_ALLOWED_KEYS)
    if unknown_keys:
        raise ValueError(
            "surface_wave.anisotropy contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    if "mode" in raw_payload:
        defaults["mode"] = _normalize_anisotropy_mode(raw_payload["mode"])
    if "operator_source" in raw_payload:
        defaults["operator_source"] = _normalize_nonempty_string(
            raw_payload["operator_source"],
            field_name="surface_wave.anisotropy.operator_source",
        )
    if defaults["operator_source"] not in SUPPORTED_ANISOTROPY_OPERATOR_SOURCES:
        raise ValueError(
            "surface_wave.anisotropy.operator_source must be one of "
            f"{list(SUPPORTED_ANISOTROPY_OPERATOR_SOURCES)!r}, got "
            f"{defaults['operator_source']!r}."
        )
    if "strength_scale" in raw_payload:
        defaults["strength_scale"] = _normalize_positive_float(
            raw_payload["strength_scale"],
            field_name="surface_wave.anisotropy.strength_scale",
        )
    if defaults["mode"] == ISOTROPIC_ANISOTROPY_MODE:
        defaults["strength_scale"] = 1.0
    return defaults


def _normalize_surface_wave_branching(payload: Any) -> dict[str, Any]:
    defaults = copy.deepcopy(default_surface_wave_parameter_bundle()["branching"])
    if not isinstance(payload, Mapping):
        raise ValueError("surface_wave.branching must be a mapping when provided.")
    raw_payload = dict(payload)
    unknown_keys = sorted(set(raw_payload) - _BRANCHING_ALLOWED_KEYS)
    if unknown_keys:
        raise ValueError(
            "surface_wave.branching contains unsupported keys: "
            f"{unknown_keys!r}."
        )
    if "mode" in raw_payload:
        defaults["mode"] = _normalize_branching_mode(raw_payload["mode"])
    if "descriptor_source" in raw_payload:
        defaults["descriptor_source"] = _normalize_nonempty_string(
            raw_payload["descriptor_source"],
            field_name="surface_wave.branching.descriptor_source",
        )
    if defaults["descriptor_source"] not in SUPPORTED_BRANCHING_DESCRIPTOR_SOURCES:
        raise ValueError(
            "surface_wave.branching.descriptor_source must be one of "
            f"{list(SUPPORTED_BRANCHING_DESCRIPTOR_SOURCES)!r}, got "
            f"{defaults['descriptor_source']!r}."
        )
    if "gain" in raw_payload:
        defaults["gain"] = _normalize_nonnegative_float(
            raw_payload["gain"],
            field_name="surface_wave.branching.gain",
        )
    if "junction_response" in raw_payload:
        defaults["junction_response"] = _normalize_nonempty_string(
            raw_payload["junction_response"],
            field_name="surface_wave.branching.junction_response",
        )
    if defaults["junction_response"] not in SUPPORTED_BRANCHING_JUNCTION_RESPONSES:
        raise ValueError(
            "surface_wave.branching.junction_response must be one of "
            f"{list(SUPPORTED_BRANCHING_JUNCTION_RESPONSES)!r}, got "
            f"{defaults['junction_response']!r}."
        )
    if defaults["mode"] == BRANCHING_DISABLED_MODE:
        defaults["gain"] = 0.0
    return defaults


def _validate_surface_wave_parameter_bundle(parameter_bundle: Mapping[str, Any]) -> None:
    recovery = dict(parameter_bundle["recovery"])
    if recovery["mode"] != RECOVERY_DISABLED_MODE:
        if float(recovery["drive_gain"]) <= 0.0:
            raise ValueError(
                "surface_wave.recovery.drive_gain must be positive when "
                "surface_wave.recovery.mode is enabled."
            )
        if float(recovery["coupling_strength_per_ms2"]) <= 0.0:
            raise ValueError(
                "surface_wave.recovery.coupling_strength_per_ms2 must be positive "
                "when surface_wave.recovery.mode is enabled."
            )
        if float(recovery["baseline"]) < 0.0:
            raise ValueError(
                "surface_wave.recovery.baseline must be non-negative when "
                "surface_wave.recovery.mode is enabled."
            )

    branching = dict(parameter_bundle["branching"])
    if branching["mode"] != BRANCHING_DISABLED_MODE and float(branching["gain"]) <= 0.0:
        raise ValueError(
            "surface_wave.branching.gain must be positive when "
            "surface_wave.branching.mode is enabled."
        )


def _normalize_surface_wave_state_variables_payload(
    payload: Any,
    *,
    model_family: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("state_variables must be a list.")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError("state_variables entries must be mappings.")
        normalized.append(
            {
                "state_id": _normalize_identifier(
                    item.get("state_id"),
                    field_name=f"state_variables[{index}].state_id",
                ),
                "symbol": _normalize_nonempty_string(
                    item.get("symbol"),
                    field_name=f"state_variables[{index}].symbol",
                ),
                "units": _normalize_nonempty_string(
                    item.get("units"),
                    field_name=f"state_variables[{index}].units",
                ),
                "kind": _normalize_nonempty_string(
                    item.get("kind"),
                    field_name=f"state_variables[{index}].kind",
                ),
                "description": _normalize_nonempty_string(
                    item.get("description"),
                    field_name=f"state_variables[{index}].description",
                ),
                "enabled_by_default": bool(item.get("enabled_by_default")),
            }
        )
    expected = default_surface_wave_state_variables(model_family)
    if normalized != expected:
        raise ValueError(
            "state_variables does not match the canonical state-variable catalog "
            f"for model_family {model_family!r}."
        )
    return normalized


def _normalize_surface_wave_assets(payload: Any) -> dict[str, dict[str, str]]:
    if not isinstance(payload, Mapping):
        raise ValueError("assets must be a mapping.")
    asset_record = payload.get(METADATA_JSON_KEY)
    if not isinstance(asset_record, Mapping):
        raise ValueError("assets.metadata_json must be a mapping.")
    asset_path = asset_record.get("path")
    if not isinstance(asset_path, str) or not asset_path:
        raise ValueError("assets.metadata_json.path must be a usable path.")
    return {
        METADATA_JSON_KEY: {
            "path": str(Path(asset_path).resolve()),
            "status": _normalize_asset_status(
                asset_record.get("status"),
                field_name="assets.metadata_json.status",
            ),
        }
    }


def _normalize_surface_wave_model_family(value: Any) -> str:
    model_family = _normalize_identifier(value, field_name="model_family")
    if model_family not in SUPPORTED_SURFACE_WAVE_MODEL_FAMILIES:
        raise ValueError(
            "Unsupported surface-wave model_family "
            f"{model_family!r}. Supported families: {list(SUPPORTED_SURFACE_WAVE_MODEL_FAMILIES)!r}."
        )
    return model_family


def _normalize_solver_family(value: Any) -> str:
    solver_family = _normalize_identifier(value, field_name="solver_family")
    if solver_family not in SUPPORTED_SURFACE_WAVE_SOLVER_FAMILIES:
        raise ValueError(
            "Unsupported surface-wave solver family "
            f"{solver_family!r}. Supported families: {list(SUPPORTED_SURFACE_WAVE_SOLVER_FAMILIES)!r}."
        )
    return solver_family


def _normalize_damping_mode(value: Any) -> str:
    mode = _normalize_identifier(value, field_name="damping.mode")
    if mode not in SUPPORTED_DAMPING_MODES:
        raise ValueError(
            "Unsupported surface-wave damping.mode "
            f"{mode!r}. Supported modes: {list(SUPPORTED_DAMPING_MODES)!r}."
        )
    return mode


def _normalize_recovery_mode(value: Any) -> str:
    mode = _normalize_identifier(value, field_name="recovery.mode")
    if mode not in SUPPORTED_RECOVERY_MODES:
        raise ValueError(
            "Unsupported surface-wave recovery.mode "
            f"{mode!r}. Supported modes: {list(SUPPORTED_RECOVERY_MODES)!r}."
        )
    return mode


def _normalize_nonlinearity_mode(value: Any) -> str:
    mode = _normalize_identifier(value, field_name="nonlinearity.mode")
    if mode not in SUPPORTED_NONLINEARITY_MODES:
        raise ValueError(
            "Unsupported surface-wave nonlinearity.mode "
            f"{mode!r}. Supported modes: {list(SUPPORTED_NONLINEARITY_MODES)!r}."
        )
    return mode


def _normalize_anisotropy_mode(value: Any) -> str:
    mode = _normalize_identifier(value, field_name="anisotropy.mode")
    if mode not in SUPPORTED_ANISOTROPY_MODES:
        raise ValueError(
            "Unsupported surface-wave anisotropy.mode "
            f"{mode!r}. Supported modes: {list(SUPPORTED_ANISOTROPY_MODES)!r}."
        )
    return mode


def _normalize_branching_mode(value: Any) -> str:
    mode = _normalize_identifier(value, field_name="branching.mode")
    if mode not in SUPPORTED_BRANCHING_MODES:
        raise ValueError(
            "Unsupported surface-wave branching.mode "
            f"{mode!r}. Supported modes: {list(SUPPORTED_BRANCHING_MODES)!r}."
        )
    return mode


def _normalize_synaptic_source_mode(value: Any) -> str:
    mode = _normalize_identifier(value, field_name="synaptic_source.mode")
    if mode not in SUPPORTED_SYNAPTIC_SOURCE_MODES:
        raise ValueError(
            "Unsupported surface-wave synaptic_source.mode "
            f"{mode!r}. Supported modes: {list(SUPPORTED_SYNAPTIC_SOURCE_MODES)!r}."
        )
    return mode


def _normalize_unit_interval_positive(value: Any, *, field_name: str) -> float:
    normalized = _normalize_positive_float(value, field_name=field_name)
    if normalized > 1.0:
        raise ValueError(f"{field_name} must be less than or equal to 1.0.")
    return normalized


def _normalize_nonnegative_float(value: Any, *, field_name: str) -> float:
    normalized = _normalize_float(value, field_name=field_name)
    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized
