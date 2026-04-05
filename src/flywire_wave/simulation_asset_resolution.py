from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse.linalg as spla

from .coupling_contract import (
    ASSET_STATUS_READY,
    COUPLING_INDEX_KEY,
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
from .geometry_contract import (
    COARSE_OPERATOR_KEY,
    DESCRIPTOR_SIDECAR_KEY,
    FINE_OPERATOR_KEY,
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
)
from .manifests import load_json
from .selection import build_subset_artifact_paths, load_subset_manifest, validate_subset_manifest_payload
from .simulation_planning import (
    _asset_record_reference,
    _normalize_float,
    _normalize_nonempty_string,
    _require_mapping,
    _require_sequence,
    _stable_hash,
)
from .skeleton_runtime_assets import (
    SKELETON_RUNTIME_ASSET_KEY,
    build_skeleton_runtime_asset_paths,
    build_skeleton_runtime_asset_record,
)
from .surface_operators import deserialize_sparse_matrix


def resolve_subset_manifest_reference(
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


def resolve_circuit_assets(
    *,
    manifest: Mapping[str, Any],
    cfg: Mapping[str, Any],
    selection_reference: Mapping[str, Any],
) -> dict[str, Any]:
    del manifest
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


def load_mixed_fidelity_descriptor_payload(
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


def build_assignment_provenance(
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


def build_approximation_route(
    *,
    registry_default_morphology_class: str,
    realized_morphology_class: str,
    policy_evaluation: Mapping[str, Any],
) -> dict[str, Any]:
    rank_delta = (
        morphology_class_rank(realized_morphology_class)
        - morphology_class_rank(registry_default_morphology_class)
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


def morphology_class_rank(value: str) -> int:
    return HYBRID_MORPHOLOGY_PROMOTION_ORDER.index(value)


def build_local_asset_reference_map(
    *,
    root_mapping: Mapping[str, Any],
    asset_keys: Sequence[Any],
) -> dict[str, Any]:
    return {
        str(asset_key): copy.deepcopy(
            resolve_local_asset_reference(
                root_mapping=root_mapping,
                asset_key=str(asset_key),
            )
        )
        for asset_key in asset_keys
    }


def resolve_local_asset_reference(
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
        return resolve_skeleton_runtime_asset_reference(
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
            for item in selected_peer_edge_bundles(root_mapping)
        ]
    raise ValueError(f"Unsupported local asset key {asset_key!r}.")


def validate_required_local_assets(
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


def selected_peer_edge_bundles(
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


def resolve_surface_wave_operator_asset(
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
        resolve_local_asset_reference(
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

    spectral_radius = estimate_surface_wave_operator_spectral_radius(
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


def resolve_skeleton_runtime_asset_reference(
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


def resolve_root_coupling_asset_record(
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
    selected_edge_bundle_paths = selected_peer_edge_bundles(root_mapping)
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


def resolve_surface_wave_coupling_asset(
    *,
    arm_id: str,
    root_mapping: Mapping[str, Any],
    hybrid_morphology: Mapping[str, Any],
) -> dict[str, Any]:
    asset = resolve_root_coupling_asset_record(
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


def resolve_skeleton_neuron_coupling_asset(
    *,
    arm_id: str,
    root_mapping: Mapping[str, Any],
    hybrid_morphology: Mapping[str, Any],
) -> dict[str, Any]:
    asset = resolve_root_coupling_asset_record(
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


def resolve_skeleton_runtime_asset(
    *,
    arm_id: str,
    root_mapping: Mapping[str, Any],
    hybrid_morphology: Mapping[str, Any],
) -> dict[str, Any]:
    asset = resolve_local_asset_reference(
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


def resolve_point_neuron_coupling_asset(
    *,
    arm_id: str,
    root_mapping: Mapping[str, Any],
    hybrid_morphology: Mapping[str, Any],
) -> dict[str, Any]:
    asset = resolve_root_coupling_asset_record(
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


def estimate_surface_wave_operator_spectral_radius(
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
