from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


COUPLING_BUNDLE_CONTRACT_VERSION = "coupling_bundle.v1"
COUPLING_BUNDLE_DESIGN_NOTE = "docs/coupling_bundle_design.md"
COUPLING_BUNDLE_DESIGN_NOTE_VERSION = "coupling_design_note.v1"

ASSET_STATUS_READY = "ready"
ASSET_STATUS_MISSING = "missing"
ASSET_STATUS_SKIPPED = "skipped"

POINT_TO_POINT_TOPOLOGY = "point_to_point"
PATCH_TO_PATCH_TOPOLOGY = "patch_to_patch"
DISTRIBUTED_PATCH_CLOUD_TOPOLOGY = "distributed_patch_cloud"
SUPPORTED_COUPLING_TOPOLOGY_FAMILIES = (
    POINT_TO_POINT_TOPOLOGY,
    PATCH_TO_PATCH_TOPOLOGY,
    DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
)
DEFAULT_COUPLING_TOPOLOGY_FAMILY = DISTRIBUTED_PATCH_CLOUD_TOPOLOGY

SURFACE_PATCH_CLOUD_MODE = "surface_patch_cloud"
SKELETON_SEGMENT_CLOUD_MODE = "skeleton_segment_cloud"
POINT_NEURON_LUMPED_MODE = "point_neuron_lumped"
SUPPORTED_FALLBACK_MODES = (
    SURFACE_PATCH_CLOUD_MODE,
    SKELETON_SEGMENT_CLOUD_MODE,
    POINT_NEURON_LUMPED_MODE,
)
DEFAULT_FALLBACK_HIERARCHY = [
    SURFACE_PATCH_CLOUD_MODE,
    SKELETON_SEGMENT_CLOUD_MODE,
    POINT_NEURON_LUMPED_MODE,
]

DEFAULT_SIGN_REPRESENTATION = "categorical_sign_with_signed_weight"
DEFAULT_DELAY_REPRESENTATION = "nonnegative_delay_ms_per_synapse_or_delay_bin"
DEFAULT_AGGREGATION_RULE = "sum_over_synapses_preserving_sign_and_delay_bins"
DEFAULT_MISSING_GEOMETRY_POLICY = "fallback_or_blocked_with_explicit_reason"

COUPLING_ASSEMBLY_CONFIG_VERSION = "coupling_assembly.v1"
COUPLING_DELAY_MODEL_CONFIG_VERSION = "coupling_delay_model.v1"

SEPARABLE_RANK_ONE_CLOUD_KERNEL = "separable_rank_one_cloud"
POINT_IMPULSE_KERNEL = "point_impulse"
SUPPORTED_COUPLING_KERNEL_FAMILIES = (
    SEPARABLE_RANK_ONE_CLOUD_KERNEL,
    POINT_IMPULSE_KERNEL,
)
DEFAULT_COUPLING_KERNEL_FAMILY = SEPARABLE_RANK_ONE_CLOUD_KERNEL

WEIGHT_SIGN_ONLY_REPRESENTATION = "weight_sign_only"
SUPPORTED_SIGN_REPRESENTATIONS = (
    DEFAULT_SIGN_REPRESENTATION,
    WEIGHT_SIGN_ONLY_REPRESENTATION,
)

CONSTANT_ZERO_DELAY_MODEL = "constant_zero_ms"
EUCLIDEAN_ANCHOR_DISTANCE_DELAY_MODEL = "euclidean_anchor_distance_over_velocity"
SUPPORTED_DELAY_MODELS = (
    CONSTANT_ZERO_DELAY_MODEL,
    EUCLIDEAN_ANCHOR_DISTANCE_DELAY_MODEL,
)
DEFAULT_DELAY_MODEL = CONSTANT_ZERO_DELAY_MODEL

COLLAPSE_DELAY_WITH_WEIGHTED_MEAN_AGGREGATION = (
    "sum_over_synapses_preserving_sign_with_weighted_mean_delay"
)
SUPPORTED_AGGREGATION_RULES = (
    DEFAULT_AGGREGATION_RULE,
    COLLAPSE_DELAY_WITH_WEIGHTED_MEAN_AGGREGATION,
)

SUM_TO_ONE_PER_COMPONENT_NORMALIZATION = "sum_to_one_per_component"
NO_CLOUD_NORMALIZATION = "none"
SUPPORTED_CLOUD_NORMALIZATIONS = (
    SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
    NO_CLOUD_NORMALIZATION,
)
DEFAULT_SOURCE_CLOUD_NORMALIZATION = SUM_TO_ONE_PER_COMPONENT_NORMALIZATION
DEFAULT_TARGET_CLOUD_NORMALIZATION = SUM_TO_ONE_PER_COMPONENT_NORMALIZATION

LOCAL_SYNAPSE_REGISTRY_KEY = "local_synapse_registry"
INCOMING_ANCHOR_MAP_KEY = "incoming_anchor_map"
OUTGOING_ANCHOR_MAP_KEY = "outgoing_anchor_map"
COUPLING_INDEX_KEY = "coupling_index"

REQUIRED_COUPLING_ASSET_KEYS = (
    LOCAL_SYNAPSE_REGISTRY_KEY,
    INCOMING_ANCHOR_MAP_KEY,
    OUTGOING_ANCHOR_MAP_KEY,
    COUPLING_INDEX_KEY,
)


@dataclass(frozen=True)
class CouplingContractPaths:
    processed_coupling_dir: Path
    local_synapse_registry_path: Path
    root_asset_directory: Path
    edge_bundle_directory: Path


@dataclass(frozen=True)
class RootCouplingBundlePaths:
    root_id: int
    local_synapse_registry_path: Path
    incoming_anchor_map_path: Path
    outgoing_anchor_map_path: Path
    coupling_index_path: Path

    @property
    def root_label(self) -> str:
        return str(int(self.root_id))

    def asset_paths(self) -> dict[str, Path]:
        return {
            LOCAL_SYNAPSE_REGISTRY_KEY: self.local_synapse_registry_path,
            INCOMING_ANCHOR_MAP_KEY: self.incoming_anchor_map_path,
            OUTGOING_ANCHOR_MAP_KEY: self.outgoing_anchor_map_path,
            COUPLING_INDEX_KEY: self.coupling_index_path,
        }


def build_coupling_contract_paths(processed_coupling_dir: str | Path) -> CouplingContractPaths:
    coupling_dir = Path(processed_coupling_dir).resolve()
    return CouplingContractPaths(
        processed_coupling_dir=coupling_dir,
        local_synapse_registry_path=coupling_dir / "synapse_registry.csv",
        root_asset_directory=coupling_dir / "roots",
        edge_bundle_directory=coupling_dir / "edges",
    )


def build_root_coupling_bundle_paths(
    root_id: int,
    *,
    processed_coupling_dir: str | Path,
) -> RootCouplingBundlePaths:
    root_label = str(int(root_id))
    contract_paths = build_coupling_contract_paths(processed_coupling_dir)
    return RootCouplingBundlePaths(
        root_id=int(root_id),
        local_synapse_registry_path=contract_paths.local_synapse_registry_path,
        incoming_anchor_map_path=contract_paths.root_asset_directory / f"{root_label}_incoming_anchor_map.npz",
        outgoing_anchor_map_path=contract_paths.root_asset_directory / f"{root_label}_outgoing_anchor_map.npz",
        coupling_index_path=contract_paths.root_asset_directory / f"{root_label}_coupling_index.json",
    )


def build_edge_coupling_bundle_path(
    pre_root_id: int,
    post_root_id: int,
    *,
    processed_coupling_dir: str | Path,
) -> Path:
    contract_paths = build_coupling_contract_paths(processed_coupling_dir)
    return contract_paths.edge_bundle_directory / f"{int(pre_root_id)}__to__{int(post_root_id)}_coupling.npz"


def build_edge_coupling_bundle_reference(
    *,
    root_id: int,
    pre_root_id: int,
    post_root_id: int,
    processed_coupling_dir: str | Path,
    status: str = ASSET_STATUS_MISSING,
) -> dict[str, Any]:
    normalized_root_id = int(root_id)
    normalized_pre_root_id = int(pre_root_id)
    normalized_post_root_id = int(post_root_id)
    if normalized_root_id == normalized_pre_root_id:
        relation_to_root = "outgoing"
        peer_root_id = normalized_post_root_id
    elif normalized_root_id == normalized_post_root_id:
        relation_to_root = "incoming"
        peer_root_id = normalized_pre_root_id
    else:
        raise ValueError(
            "Root-local coupling bundle references must include edges where root_id "
            "matches either pre_root_id or post_root_id."
        )
    return {
        "pre_root_id": normalized_pre_root_id,
        "post_root_id": normalized_post_root_id,
        "peer_root_id": peer_root_id,
        "relation_to_root": relation_to_root,
        "path": str(
            build_edge_coupling_bundle_path(
                normalized_pre_root_id,
                normalized_post_root_id,
                processed_coupling_dir=processed_coupling_dir,
            )
        ),
        "status": str(status),
    }


def build_coupling_contract_manifest_metadata(
    *,
    processed_coupling_dir: str | Path | None = None,
    coupling_bundle_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    local_synapse_registry_status = ASSET_STATUS_MISSING
    resolved_processed_coupling_dir = processed_coupling_dir
    if coupling_bundle_metadata is not None:
        normalized_bundle = parse_coupling_bundle_metadata(coupling_bundle_metadata)
        local_synapse_registry = dict(normalized_bundle["assets"][LOCAL_SYNAPSE_REGISTRY_KEY])
        resolved_processed_coupling_dir = Path(local_synapse_registry["path"]).resolve().parent
        local_synapse_registry_status = str(local_synapse_registry["status"])
    if resolved_processed_coupling_dir is None:
        raise ValueError(
            "processed_coupling_dir must be provided when coupling_bundle_metadata is unavailable."
        )

    contract_paths = build_coupling_contract_paths(resolved_processed_coupling_dir)
    return {
        "version": COUPLING_BUNDLE_CONTRACT_VERSION,
        "design_note": COUPLING_BUNDLE_DESIGN_NOTE,
        "design_note_version": COUPLING_BUNDLE_DESIGN_NOTE_VERSION,
        "coupling_assembly_config_version": COUPLING_ASSEMBLY_CONFIG_VERSION,
        "delay_model_config_version": COUPLING_DELAY_MODEL_CONFIG_VERSION,
        "default_topology_family": DEFAULT_COUPLING_TOPOLOGY_FAMILY,
        "supported_topology_families": list(SUPPORTED_COUPLING_TOPOLOGY_FAMILIES),
        "supported_fallback_modes": list(SUPPORTED_FALLBACK_MODES),
        "default_fallback_hierarchy": copy.deepcopy(DEFAULT_FALLBACK_HIERARCHY),
        "default_kernel_family": DEFAULT_COUPLING_KERNEL_FAMILY,
        "supported_kernel_families": list(SUPPORTED_COUPLING_KERNEL_FAMILIES),
        "default_sign_representation": DEFAULT_SIGN_REPRESENTATION,
        "supported_sign_representations": list(SUPPORTED_SIGN_REPRESENTATIONS),
        "default_delay_representation": DEFAULT_DELAY_REPRESENTATION,
        "default_delay_model": DEFAULT_DELAY_MODEL,
        "supported_delay_models": list(SUPPORTED_DELAY_MODELS),
        "default_aggregation_rule": DEFAULT_AGGREGATION_RULE,
        "supported_aggregation_rules": list(SUPPORTED_AGGREGATION_RULES),
        "default_missing_geometry_policy": DEFAULT_MISSING_GEOMETRY_POLICY,
        "default_source_cloud_normalization": DEFAULT_SOURCE_CLOUD_NORMALIZATION,
        "default_target_cloud_normalization": DEFAULT_TARGET_CLOUD_NORMALIZATION,
        "supported_cloud_normalizations": list(SUPPORTED_CLOUD_NORMALIZATIONS),
        "preferred_coupling_assembly": default_coupling_assembly_config(),
        "local_synapse_registry": {
            "path": str(contract_paths.local_synapse_registry_path),
            "status": local_synapse_registry_status,
        },
        "root_asset_directory": str(contract_paths.root_asset_directory),
        "edge_bundle_directory": str(contract_paths.edge_bundle_directory),
    }


def build_coupling_bundle_metadata(
    *,
    root_id: int,
    processed_coupling_dir: str | Path,
    local_synapse_registry_status: str = ASSET_STATUS_MISSING,
    incoming_anchor_map_status: str = ASSET_STATUS_MISSING,
    outgoing_anchor_map_status: str = ASSET_STATUS_MISSING,
    coupling_index_status: str = ASSET_STATUS_MISSING,
    edge_bundles: Sequence[Mapping[str, Any]] | None = None,
    topology_family: str = DEFAULT_COUPLING_TOPOLOGY_FAMILY,
    fallback_hierarchy: Sequence[str] | None = None,
    kernel_family: str = DEFAULT_COUPLING_KERNEL_FAMILY,
    sign_representation: str = DEFAULT_SIGN_REPRESENTATION,
    delay_representation: str = DEFAULT_DELAY_REPRESENTATION,
    delay_model: str = DEFAULT_DELAY_MODEL,
    delay_model_parameters: Mapping[str, Any] | None = None,
    aggregation_rule: str = DEFAULT_AGGREGATION_RULE,
    missing_geometry_policy: str = DEFAULT_MISSING_GEOMETRY_POLICY,
    source_cloud_normalization: str = DEFAULT_SOURCE_CLOUD_NORMALIZATION,
    target_cloud_normalization: str = DEFAULT_TARGET_CLOUD_NORMALIZATION,
    coupling_assembly: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_coupling_assembly = normalize_coupling_assembly_config(
        coupling_assembly
        if coupling_assembly is not None
        else {
            "topology_family": topology_family,
            "fallback_hierarchy": list(DEFAULT_FALLBACK_HIERARCHY if fallback_hierarchy is None else fallback_hierarchy),
            "kernel_family": kernel_family,
            "sign_representation": sign_representation,
            "delay_representation": delay_representation,
            "delay_model": {
                "mode": delay_model,
                **dict(delay_model_parameters or {}),
            },
            "aggregation_rule": aggregation_rule,
            "missing_geometry_policy": missing_geometry_policy,
            "source_cloud_normalization": source_cloud_normalization,
            "target_cloud_normalization": target_cloud_normalization,
        }
    )
    bundle_paths = build_root_coupling_bundle_paths(root_id, processed_coupling_dir=processed_coupling_dir)
    assets = {
        LOCAL_SYNAPSE_REGISTRY_KEY: {
            "path": str(bundle_paths.local_synapse_registry_path),
            "status": str(local_synapse_registry_status),
        },
        INCOMING_ANCHOR_MAP_KEY: {
            "path": str(bundle_paths.incoming_anchor_map_path),
            "status": str(incoming_anchor_map_status),
        },
        OUTGOING_ANCHOR_MAP_KEY: {
            "path": str(bundle_paths.outgoing_anchor_map_path),
            "status": str(outgoing_anchor_map_status),
        },
        COUPLING_INDEX_KEY: {
            "path": str(bundle_paths.coupling_index_path),
            "status": str(coupling_index_status),
        },
    }
    normalized_edge_bundles = _normalize_edge_bundles(edge_bundles)
    bundle_status = _bundle_status(
        [
            *(str(asset["status"]) for asset in assets.values()),
            *(str(edge_bundle["status"]) for edge_bundle in normalized_edge_bundles),
        ]
    )
    return {
        "contract_version": COUPLING_BUNDLE_CONTRACT_VERSION,
        "design_note": COUPLING_BUNDLE_DESIGN_NOTE,
        "design_note_version": COUPLING_BUNDLE_DESIGN_NOTE_VERSION,
        "status": bundle_status,
        "topology_family": normalized_coupling_assembly["topology_family"],
        "fallback_hierarchy": copy.deepcopy(normalized_coupling_assembly["fallback_hierarchy"]),
        "kernel_family": normalized_coupling_assembly["kernel_family"],
        "sign_representation": normalized_coupling_assembly["sign_representation"],
        "delay_representation": normalized_coupling_assembly["delay_representation"],
        "delay_model": normalized_coupling_assembly["delay_model"]["mode"],
        "delay_model_parameters": copy.deepcopy(
            {
                key: value
                for key, value in normalized_coupling_assembly["delay_model"].items()
                if key not in {"version", "mode"}
            }
        ),
        "aggregation_rule": normalized_coupling_assembly["aggregation_rule"],
        "missing_geometry_policy": normalized_coupling_assembly["missing_geometry_policy"],
        "source_cloud_normalization": normalized_coupling_assembly["source_cloud_normalization"],
        "target_cloud_normalization": normalized_coupling_assembly["target_cloud_normalization"],
        "assets": assets,
        "edge_bundles": normalized_edge_bundles,
    }


def default_coupling_assembly_config() -> dict[str, Any]:
    return {
        "version": COUPLING_ASSEMBLY_CONFIG_VERSION,
        "topology_family": DEFAULT_COUPLING_TOPOLOGY_FAMILY,
        "fallback_hierarchy": copy.deepcopy(DEFAULT_FALLBACK_HIERARCHY),
        "kernel_family": DEFAULT_COUPLING_KERNEL_FAMILY,
        "sign_representation": DEFAULT_SIGN_REPRESENTATION,
        "delay_representation": DEFAULT_DELAY_REPRESENTATION,
        "delay_model": {
            "version": COUPLING_DELAY_MODEL_CONFIG_VERSION,
            "mode": DEFAULT_DELAY_MODEL,
            "base_delay_ms": 0.0,
            "velocity_distance_units_per_ms": 1.0,
            "delay_bin_size_ms": 0.0,
        },
        "aggregation_rule": DEFAULT_AGGREGATION_RULE,
        "missing_geometry_policy": DEFAULT_MISSING_GEOMETRY_POLICY,
        "source_cloud_normalization": DEFAULT_SOURCE_CLOUD_NORMALIZATION,
        "target_cloud_normalization": DEFAULT_TARGET_CLOUD_NORMALIZATION,
    }


def normalize_coupling_assembly_config(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = default_coupling_assembly_config()
    if payload is None:
        return normalized
    if not isinstance(payload, Mapping):
        raise ValueError("coupling_assembly must be a mapping when provided.")

    version = str(payload.get("version", COUPLING_ASSEMBLY_CONFIG_VERSION))
    if version != COUPLING_ASSEMBLY_CONFIG_VERSION:
        raise ValueError(
            f"coupling_assembly.version must be {COUPLING_ASSEMBLY_CONFIG_VERSION!r}, got {version!r}."
        )
    normalized["version"] = version
    normalized["topology_family"] = _normalize_topology_family(
        payload.get("topology_family", DEFAULT_COUPLING_TOPOLOGY_FAMILY)
    )
    normalized["fallback_hierarchy"] = _normalize_fallback_hierarchy(payload.get("fallback_hierarchy"))

    kernel_family = str(payload.get("kernel_family", DEFAULT_COUPLING_KERNEL_FAMILY))
    if kernel_family not in SUPPORTED_COUPLING_KERNEL_FAMILIES:
        raise ValueError(
            "Unsupported coupling_assembly.kernel_family "
            f"{kernel_family!r}. Supported families: {list(SUPPORTED_COUPLING_KERNEL_FAMILIES)!r}."
        )
    normalized["kernel_family"] = kernel_family

    sign_representation = str(payload.get("sign_representation", DEFAULT_SIGN_REPRESENTATION))
    if sign_representation not in SUPPORTED_SIGN_REPRESENTATIONS:
        raise ValueError(
            "Unsupported coupling_assembly.sign_representation "
            f"{sign_representation!r}. Supported representations: {list(SUPPORTED_SIGN_REPRESENTATIONS)!r}."
        )
    normalized["sign_representation"] = sign_representation

    delay_representation = str(payload.get("delay_representation", DEFAULT_DELAY_REPRESENTATION))
    if delay_representation != DEFAULT_DELAY_REPRESENTATION:
        raise ValueError(
            "Unsupported coupling_assembly.delay_representation "
            f"{delay_representation!r}. Supported representations: {[DEFAULT_DELAY_REPRESENTATION]!r}."
        )
    normalized["delay_representation"] = delay_representation

    delay_model = payload.get("delay_model", {})
    if delay_model is None:
        delay_model = {}
    if not isinstance(delay_model, Mapping):
        raise ValueError("coupling_assembly.delay_model must be a mapping when provided.")
    delay_model_version = str(delay_model.get("version", COUPLING_DELAY_MODEL_CONFIG_VERSION))
    if delay_model_version != COUPLING_DELAY_MODEL_CONFIG_VERSION:
        raise ValueError(
            "coupling_assembly.delay_model.version must be "
            f"{COUPLING_DELAY_MODEL_CONFIG_VERSION!r}."
        )
    delay_model_mode = str(delay_model.get("mode", DEFAULT_DELAY_MODEL))
    if delay_model_mode not in SUPPORTED_DELAY_MODELS:
        raise ValueError(
            "Unsupported coupling_assembly.delay_model.mode "
            f"{delay_model_mode!r}. Supported models: {list(SUPPORTED_DELAY_MODELS)!r}."
        )
    base_delay_ms = _normalize_nonnegative_float(
        delay_model.get("base_delay_ms", normalized["delay_model"]["base_delay_ms"]),
        field_name="coupling_assembly.delay_model.base_delay_ms",
    )
    velocity_distance_units_per_ms = _normalize_positive_float(
        delay_model.get(
            "velocity_distance_units_per_ms",
            normalized["delay_model"]["velocity_distance_units_per_ms"],
        ),
        field_name="coupling_assembly.delay_model.velocity_distance_units_per_ms",
    )
    delay_bin_size_ms = _normalize_nonnegative_float(
        delay_model.get("delay_bin_size_ms", normalized["delay_model"]["delay_bin_size_ms"]),
        field_name="coupling_assembly.delay_model.delay_bin_size_ms",
    )
    normalized["delay_model"] = {
        "version": delay_model_version,
        "mode": delay_model_mode,
        "base_delay_ms": base_delay_ms,
        "velocity_distance_units_per_ms": velocity_distance_units_per_ms,
        "delay_bin_size_ms": delay_bin_size_ms,
    }

    aggregation_rule = str(payload.get("aggregation_rule", DEFAULT_AGGREGATION_RULE))
    if aggregation_rule not in SUPPORTED_AGGREGATION_RULES:
        raise ValueError(
            "Unsupported coupling_assembly.aggregation_rule "
            f"{aggregation_rule!r}. Supported rules: {list(SUPPORTED_AGGREGATION_RULES)!r}."
        )
    normalized["aggregation_rule"] = aggregation_rule

    missing_geometry_policy = str(payload.get("missing_geometry_policy", DEFAULT_MISSING_GEOMETRY_POLICY))
    if not missing_geometry_policy:
        raise ValueError("coupling_assembly.missing_geometry_policy must be a non-empty string.")
    normalized["missing_geometry_policy"] = missing_geometry_policy

    source_cloud_normalization = str(
        payload.get("source_cloud_normalization", DEFAULT_SOURCE_CLOUD_NORMALIZATION)
    )
    if source_cloud_normalization not in SUPPORTED_CLOUD_NORMALIZATIONS:
        raise ValueError(
            "Unsupported coupling_assembly.source_cloud_normalization "
            f"{source_cloud_normalization!r}. Supported values: {list(SUPPORTED_CLOUD_NORMALIZATIONS)!r}."
        )
    normalized["source_cloud_normalization"] = source_cloud_normalization

    target_cloud_normalization = str(
        payload.get("target_cloud_normalization", DEFAULT_TARGET_CLOUD_NORMALIZATION)
    )
    if target_cloud_normalization not in SUPPORTED_CLOUD_NORMALIZATIONS:
        raise ValueError(
            "Unsupported coupling_assembly.target_cloud_normalization "
            f"{target_cloud_normalization!r}. Supported values: {list(SUPPORTED_CLOUD_NORMALIZATIONS)!r}."
        )
    normalized["target_cloud_normalization"] = target_cloud_normalization

    return normalized


def parse_coupling_bundle_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Coupling bundle metadata must be a mapping.")

    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "design_note",
        "design_note_version",
        "status",
        "topology_family",
        "fallback_hierarchy",
        "kernel_family",
        "sign_representation",
        "delay_representation",
        "delay_model",
        "delay_model_parameters",
        "aggregation_rule",
        "missing_geometry_policy",
        "source_cloud_normalization",
        "target_cloud_normalization",
        "assets",
        "edge_bundles",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"Coupling bundle metadata is missing required fields: {missing_fields}")
    if normalized["contract_version"] != COUPLING_BUNDLE_CONTRACT_VERSION:
        raise ValueError(
            "Coupling bundle metadata contract_version does not match "
            f"{COUPLING_BUNDLE_CONTRACT_VERSION!r}."
        )

    normalized["topology_family"] = _normalize_topology_family(normalized["topology_family"])
    normalized["fallback_hierarchy"] = _normalize_fallback_hierarchy(normalized["fallback_hierarchy"])
    normalized["kernel_family"] = _normalize_kernel_family(normalized["kernel_family"])
    normalized["sign_representation"] = _normalize_sign_representation(normalized["sign_representation"])
    normalized["delay_representation"] = _normalize_delay_representation(normalized["delay_representation"])
    normalized["delay_model"] = _normalize_delay_model(normalized["delay_model"])
    delay_model_parameters = normalized.get("delay_model_parameters", {})
    if not isinstance(delay_model_parameters, Mapping):
        raise ValueError("Coupling bundle metadata delay_model_parameters must be a mapping.")
    normalized["delay_model_parameters"] = _normalize_delay_model_parameters(
        normalized["delay_model"],
        delay_model_parameters,
    )
    normalized["aggregation_rule"] = _normalize_aggregation_rule(normalized["aggregation_rule"])
    normalized["missing_geometry_policy"] = str(normalized["missing_geometry_policy"])
    normalized["source_cloud_normalization"] = _normalize_cloud_normalization(
        normalized["source_cloud_normalization"],
        field_name="source_cloud_normalization",
    )
    normalized["target_cloud_normalization"] = _normalize_cloud_normalization(
        normalized["target_cloud_normalization"],
        field_name="target_cloud_normalization",
    )
    if not isinstance(normalized["status"], str) or not str(normalized["status"]):
        raise ValueError("Coupling bundle metadata status must be a non-empty string.")

    assets = normalized["assets"]
    if not isinstance(assets, Mapping):
        raise ValueError("Coupling bundle metadata assets must be a mapping.")
    normalized_assets: dict[str, dict[str, str]] = {}
    for asset_key in REQUIRED_COUPLING_ASSET_KEYS:
        asset_record = assets.get(asset_key)
        if not isinstance(asset_record, Mapping):
            raise ValueError(f"Coupling bundle asset {asset_key!r} is missing from the metadata.")
        normalized_assets[asset_key] = _normalize_asset_record(asset_record, field_name=f"assets.{asset_key}")
    normalized["assets"] = normalized_assets
    normalized["edge_bundles"] = _normalize_edge_bundles(normalized["edge_bundles"])
    normalized["status"] = str(normalized["status"])
    return normalized


def discover_coupling_bundle_paths(record: Mapping[str, Any]) -> dict[str, Path]:
    coupling_bundle = record.get("coupling_bundle")
    if not isinstance(coupling_bundle, Mapping):
        raise ValueError("Manifest record does not contain a coupling_bundle mapping.")
    assets = coupling_bundle.get("assets")
    if not isinstance(assets, Mapping):
        raise ValueError("Manifest record coupling_bundle.assets is not a mapping.")

    discovered: dict[str, Path] = {}
    for asset_key in REQUIRED_COUPLING_ASSET_KEYS:
        asset_record = assets.get(asset_key)
        if not isinstance(asset_record, Mapping):
            raise ValueError(f"Coupling asset {asset_key!r} is missing from the manifest record.")
        asset_path = asset_record.get("path")
        if not isinstance(asset_path, str) or not asset_path:
            raise ValueError(f"Coupling asset {asset_key!r} is missing a usable path.")
        discovered[asset_key] = Path(asset_path)
    return discovered


def discover_edge_coupling_bundle_paths(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    coupling_bundle = record.get("coupling_bundle")
    if not isinstance(coupling_bundle, Mapping):
        raise ValueError("Manifest record does not contain a coupling_bundle mapping.")
    edge_bundles = coupling_bundle.get("edge_bundles")
    if not isinstance(edge_bundles, list):
        raise ValueError("Manifest record coupling_bundle.edge_bundles is not a list.")

    discovered: list[dict[str, Any]] = []
    for edge_bundle in _normalize_edge_bundles(edge_bundles):
        discovered.append(
            {
                "pre_root_id": int(edge_bundle["pre_root_id"]),
                "post_root_id": int(edge_bundle["post_root_id"]),
                "peer_root_id": int(edge_bundle["peer_root_id"]),
                "relation_to_root": str(edge_bundle["relation_to_root"]),
                "path": Path(str(edge_bundle["path"])),
                "status": str(edge_bundle["status"]),
            }
        )
    return discovered


def _normalize_topology_family(value: Any) -> str:
    topology_family = str(value)
    if topology_family not in SUPPORTED_COUPLING_TOPOLOGY_FAMILIES:
        raise ValueError(
            "Unsupported coupling topology family "
            f"{topology_family!r}. Supported families: {list(SUPPORTED_COUPLING_TOPOLOGY_FAMILIES)!r}."
    )
    return topology_family


def _normalize_kernel_family(value: Any) -> str:
    kernel_family = str(value)
    if kernel_family not in SUPPORTED_COUPLING_KERNEL_FAMILIES:
        raise ValueError(
            "Unsupported coupling kernel family "
            f"{kernel_family!r}. Supported families: {list(SUPPORTED_COUPLING_KERNEL_FAMILIES)!r}."
        )
    return kernel_family


def _normalize_sign_representation(value: Any) -> str:
    sign_representation = str(value)
    if sign_representation not in SUPPORTED_SIGN_REPRESENTATIONS:
        raise ValueError(
            "Unsupported sign representation "
            f"{sign_representation!r}. Supported representations: {list(SUPPORTED_SIGN_REPRESENTATIONS)!r}."
        )
    return sign_representation


def _normalize_delay_representation(value: Any) -> str:
    delay_representation = str(value)
    if delay_representation != DEFAULT_DELAY_REPRESENTATION:
        raise ValueError(
            "Unsupported delay representation "
            f"{delay_representation!r}. Supported representations: {[DEFAULT_DELAY_REPRESENTATION]!r}."
        )
    return delay_representation


def _normalize_delay_model(value: Any) -> str:
    delay_model = str(value)
    if delay_model not in SUPPORTED_DELAY_MODELS:
        raise ValueError(
            "Unsupported delay model "
            f"{delay_model!r}. Supported models: {list(SUPPORTED_DELAY_MODELS)!r}."
        )
    return delay_model


def _normalize_delay_model_parameters(
    delay_model: str,
    payload: Mapping[str, Any],
) -> dict[str, float]:
    default_delay_model = default_coupling_assembly_config()["delay_model"]
    parameters = {
        "base_delay_ms": _normalize_nonnegative_float(
            payload.get("base_delay_ms", default_delay_model["base_delay_ms"]),
            field_name="delay_model_parameters.base_delay_ms",
        ),
        "velocity_distance_units_per_ms": _normalize_positive_float(
            payload.get(
                "velocity_distance_units_per_ms",
                default_delay_model["velocity_distance_units_per_ms"],
            ),
            field_name="delay_model_parameters.velocity_distance_units_per_ms",
        ),
        "delay_bin_size_ms": _normalize_nonnegative_float(
            payload.get("delay_bin_size_ms", default_delay_model["delay_bin_size_ms"]),
            field_name="delay_model_parameters.delay_bin_size_ms",
        ),
    }
    if delay_model == CONSTANT_ZERO_DELAY_MODEL and parameters["base_delay_ms"] < 0.0:
        raise ValueError("delay_model_parameters.base_delay_ms must be non-negative.")
    return parameters


def _normalize_aggregation_rule(value: Any) -> str:
    aggregation_rule = str(value)
    if aggregation_rule not in SUPPORTED_AGGREGATION_RULES:
        raise ValueError(
            "Unsupported aggregation rule "
            f"{aggregation_rule!r}. Supported rules: {list(SUPPORTED_AGGREGATION_RULES)!r}."
        )
    return aggregation_rule


def _normalize_cloud_normalization(value: Any, *, field_name: str) -> str:
    normalization = str(value)
    if normalization not in SUPPORTED_CLOUD_NORMALIZATIONS:
        raise ValueError(
            f"Unsupported {field_name} {normalization!r}. "
            f"Supported values: {list(SUPPORTED_CLOUD_NORMALIZATIONS)!r}."
        )
    return normalization


def _normalize_fallback_hierarchy(value: Sequence[str] | None) -> list[str]:
    if isinstance(value, (str, bytes, bytearray)):
        raise ValueError("Coupling bundle fallback_hierarchy must be a sequence of fallback-mode strings.")
    hierarchy = list(DEFAULT_FALLBACK_HIERARCHY if value is None else value)
    if not hierarchy:
        raise ValueError("Coupling bundle fallback_hierarchy may not be empty.")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in hierarchy:
        mode = str(item)
        if mode not in SUPPORTED_FALLBACK_MODES:
            raise ValueError(
                f"Unsupported fallback mode {mode!r}. Supported modes: {list(SUPPORTED_FALLBACK_MODES)!r}."
            )
        if mode in seen:
            continue
        seen.add(mode)
        normalized.append(mode)
    return normalized


def _normalize_asset_record(asset_record: Mapping[str, Any], *, field_name: str) -> dict[str, str]:
    asset_path = asset_record.get("path")
    if not isinstance(asset_path, str) or not asset_path:
        raise ValueError(f"{field_name}.path must be a non-empty string.")
    asset_status = asset_record.get("status")
    if not isinstance(asset_status, str) or not asset_status:
        raise ValueError(f"{field_name}.status must be a non-empty string.")
    return {
        "path": asset_path,
        "status": asset_status,
    }


def _normalize_edge_bundles(edge_bundles: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    if edge_bundles is None:
        return []
    if isinstance(edge_bundles, (str, bytes, bytearray)) or not isinstance(edge_bundles, Sequence):
        raise ValueError("Coupling bundle edge_bundles must be a sequence of mappings.")

    normalized_edge_bundles: list[dict[str, Any]] = []
    for index, edge_bundle in enumerate(edge_bundles):
        if not isinstance(edge_bundle, Mapping):
            raise ValueError(f"Coupling bundle edge_bundles[{index}] must be a mapping.")
        path = edge_bundle.get("path")
        status = edge_bundle.get("status")
        relation_to_root = edge_bundle.get("relation_to_root")
        if not isinstance(path, str) or not path:
            raise ValueError(f"Coupling bundle edge_bundles[{index}].path must be a non-empty string.")
        if not isinstance(status, str) or not status:
            raise ValueError(f"Coupling bundle edge_bundles[{index}].status must be a non-empty string.")
        if not isinstance(relation_to_root, str) or not relation_to_root:
            raise ValueError(
                f"Coupling bundle edge_bundles[{index}].relation_to_root must be a non-empty string."
            )
        normalized_edge_bundles.append(
            {
                "pre_root_id": int(edge_bundle["pre_root_id"]),
                "post_root_id": int(edge_bundle["post_root_id"]),
                "peer_root_id": int(edge_bundle["peer_root_id"]),
                "relation_to_root": relation_to_root,
                "path": path,
                "status": status,
            }
        )
    normalized_edge_bundles.sort(
        key=lambda item: (
            int(item["pre_root_id"]),
            int(item["post_root_id"]),
            int(item["peer_root_id"]),
            str(item["relation_to_root"]),
            str(item["path"]),
        )
    )
    return normalized_edge_bundles


def _bundle_status(statuses: Sequence[str]) -> str:
    normalized_statuses = [str(status) for status in statuses if str(status)]
    if not normalized_statuses:
        return ASSET_STATUS_MISSING
    if all(status in {ASSET_STATUS_READY, ASSET_STATUS_SKIPPED} for status in normalized_statuses):
        return ASSET_STATUS_READY
    if any(status == ASSET_STATUS_READY for status in normalized_statuses):
        return "partial"
    if all(status == ASSET_STATUS_SKIPPED for status in normalized_statuses):
        return ASSET_STATUS_SKIPPED
    if any(status == ASSET_STATUS_SKIPPED for status in normalized_statuses) and all(
        status in {ASSET_STATUS_MISSING, ASSET_STATUS_SKIPPED} for status in normalized_statuses
    ):
        return ASSET_STATUS_MISSING
    return ASSET_STATUS_MISSING


def _normalize_nonnegative_float(value: Any, *, field_name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{field_name} must be finite and non-negative.")
    return number


def _normalize_positive_float(value: Any, *, field_name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(f"{field_name} must be finite and strictly positive.")
    return number
