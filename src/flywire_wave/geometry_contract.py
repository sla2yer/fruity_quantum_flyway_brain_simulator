from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import write_json


GEOMETRY_ASSET_CONTRACT_VERSION = "geometry_bundle.v1"
OPERATOR_BUNDLE_CONTRACT_VERSION = "operator_bundle.v1"
OPERATOR_BUNDLE_DESIGN_NOTE = "docs/operator_bundle_design.md"

ASSET_STATUS_READY = "ready"
ASSET_STATUS_MISSING = "missing"
ASSET_STATUS_SKIPPED = "skipped"

FETCH_STATUS_FETCHED = "fetched"
FETCH_STATUS_CACHE_HIT = "cache_hit"
FETCH_STATUS_SKIPPED = "skipped"
FETCH_STATUS_FAILED = "failed"

RAW_MESH_KEY = "raw_mesh"
RAW_SKELETON_KEY = "raw_skeleton"
SIMPLIFIED_MESH_KEY = "simplified_mesh"
SURFACE_GRAPH_KEY = "surface_graph"
PATCH_GRAPH_KEY = "patch_graph"
DESCRIPTOR_SIDECAR_KEY = "descriptor_sidecar"
QA_SIDECAR_KEY = "qa_sidecar"
TRANSFER_OPERATORS_KEY = "transfer_operators"
OPERATOR_METADATA_KEY = "operator_metadata"

FINE_OPERATOR_KEY = "fine_operator"
COARSE_OPERATOR_KEY = "coarse_operator"

GEOMETRY_PROCESSED_ASSET_KEYS = (
    SIMPLIFIED_MESH_KEY,
    SURFACE_GRAPH_KEY,
    PATCH_GRAPH_KEY,
    DESCRIPTOR_SIDECAR_KEY,
    QA_SIDECAR_KEY,
)
PROCESSED_ASSET_KEYS = GEOMETRY_PROCESSED_ASSET_KEYS + (
    TRANSFER_OPERATORS_KEY,
    OPERATOR_METADATA_KEY,
)

DEFAULT_FINE_DISCRETIZATION_FAMILY = "triangle_mesh_cotangent_fem"
DEFAULT_MASS_TREATMENT = "lumped_mass"
DEFAULT_NORMALIZATION = "mass_normalized"
DEFAULT_BOUNDARY_CONDITION_MODE = "closed_surface_zero_flux"

FALLBACK_FINE_DISCRETIZATION_FAMILY = "surface_graph_uniform_laplacian"
FALLBACK_MASS_TREATMENT = "uniform_vertex_measure"
FALLBACK_NORMALIZATION = "symmetric_combinatorial"
FALLBACK_GEODESIC_NEIGHBORHOOD_MODE = "surface_graph_hops"
FALLBACK_TRANSFER_RESTRICTION = "uniform_patch_average"
FALLBACK_TRANSFER_PROLONGATION = "constant_on_patch"


@dataclass(frozen=True)
class GeometryBundlePaths:
    root_id: int
    raw_mesh_path: Path
    raw_skeleton_path: Path
    simplified_mesh_path: Path
    surface_graph_path: Path
    fine_operator_path: Path
    patch_graph_path: Path
    coarse_operator_path: Path
    descriptor_sidecar_path: Path
    qa_sidecar_path: Path
    transfer_operator_path: Path
    operator_metadata_path: Path
    legacy_meta_json_path: Path

    @property
    def root_label(self) -> str:
        return str(int(self.root_id))

    def asset_paths(self) -> dict[str, Path]:
        return {
            RAW_MESH_KEY: self.raw_mesh_path,
            RAW_SKELETON_KEY: self.raw_skeleton_path,
            SIMPLIFIED_MESH_KEY: self.simplified_mesh_path,
            SURFACE_GRAPH_KEY: self.surface_graph_path,
            PATCH_GRAPH_KEY: self.patch_graph_path,
            DESCRIPTOR_SIDECAR_KEY: self.descriptor_sidecar_path,
            QA_SIDECAR_KEY: self.qa_sidecar_path,
            TRANSFER_OPERATORS_KEY: self.transfer_operator_path,
            OPERATOR_METADATA_KEY: self.operator_metadata_path,
        }

    def operator_asset_paths(self) -> dict[str, Path]:
        return {
            FINE_OPERATOR_KEY: self.fine_operator_path,
            COARSE_OPERATOR_KEY: self.coarse_operator_path,
            TRANSFER_OPERATORS_KEY: self.transfer_operator_path,
            OPERATOR_METADATA_KEY: self.operator_metadata_path,
        }


def build_geometry_bundle_paths(
    root_id: int,
    *,
    meshes_raw_dir: str | Path,
    skeletons_raw_dir: str | Path,
    processed_mesh_dir: str | Path,
    processed_graph_dir: str | Path,
) -> GeometryBundlePaths:
    root_label = str(int(root_id))
    raw_mesh_dir = Path(meshes_raw_dir).resolve()
    raw_skeleton_dir = Path(skeletons_raw_dir).resolve()
    mesh_dir = Path(processed_mesh_dir).resolve()
    graph_dir = Path(processed_graph_dir).resolve()
    return GeometryBundlePaths(
        root_id=int(root_id),
        raw_mesh_path=raw_mesh_dir / f"{root_label}.ply",
        raw_skeleton_path=raw_skeleton_dir / f"{root_label}.swc",
        simplified_mesh_path=mesh_dir / f"{root_label}.ply",
        surface_graph_path=graph_dir / f"{root_label}_graph.npz",
        fine_operator_path=graph_dir / f"{root_label}_fine_operator.npz",
        patch_graph_path=graph_dir / f"{root_label}_patch_graph.npz",
        coarse_operator_path=graph_dir / f"{root_label}_coarse_operator.npz",
        descriptor_sidecar_path=graph_dir / f"{root_label}_descriptors.json",
        qa_sidecar_path=graph_dir / f"{root_label}_qa.json",
        transfer_operator_path=graph_dir / f"{root_label}_transfer_operators.npz",
        operator_metadata_path=graph_dir / f"{root_label}_operator_metadata.json",
        legacy_meta_json_path=graph_dir / f"{root_label}_meta.json",
    )


def default_asset_statuses(*, fetch_skeletons: bool) -> dict[str, str]:
    return {
        RAW_MESH_KEY: ASSET_STATUS_MISSING,
        RAW_SKELETON_KEY: ASSET_STATUS_MISSING if fetch_skeletons else ASSET_STATUS_SKIPPED,
        SIMPLIFIED_MESH_KEY: ASSET_STATUS_MISSING,
        SURFACE_GRAPH_KEY: ASSET_STATUS_MISSING,
        PATCH_GRAPH_KEY: ASSET_STATUS_MISSING,
        DESCRIPTOR_SIDECAR_KEY: ASSET_STATUS_MISSING,
        QA_SIDECAR_KEY: ASSET_STATUS_MISSING,
        TRANSFER_OPERATORS_KEY: ASSET_STATUS_MISSING,
        OPERATOR_METADATA_KEY: ASSET_STATUS_MISSING,
    }


def manifest_asset_records(
    bundle_paths: GeometryBundlePaths,
    *,
    asset_statuses: dict[str, str],
) -> dict[str, dict[str, str]]:
    return {
        asset_key: {
            "path": str(path),
            "status": asset_statuses[asset_key],
        }
        for asset_key, path in bundle_paths.asset_paths().items()
    }


def manifest_artifact_sources(
    bundle_paths: GeometryBundlePaths,
    *,
    asset_statuses: dict[str, str],
) -> dict[str, dict[str, str]]:
    raw_mesh_status = str(asset_statuses.get(RAW_MESH_KEY, ASSET_STATUS_MISSING))
    raw_skeleton_status = str(asset_statuses.get(RAW_SKELETON_KEY, ASSET_STATUS_MISSING))
    asset_paths = bundle_paths.asset_paths()
    return {
        asset_key: {
            "path": str(asset_paths[asset_key]),
            "raw_mesh_path": str(bundle_paths.raw_mesh_path),
            "raw_mesh_status": raw_mesh_status,
            "raw_skeleton_path": str(bundle_paths.raw_skeleton_path),
            "raw_skeleton_status": raw_skeleton_status,
        }
        for asset_key in PROCESSED_ASSET_KEYS
    }


def build_operator_bundle_manifest_metadata() -> dict[str, Any]:
    return {
        "version": OPERATOR_BUNDLE_CONTRACT_VERSION,
        "design_note": OPERATOR_BUNDLE_DESIGN_NOTE,
        "preferred_discretization_family": DEFAULT_FINE_DISCRETIZATION_FAMILY,
        "preferred_mass_treatment": DEFAULT_MASS_TREATMENT,
        "preferred_normalization": DEFAULT_NORMALIZATION,
        "preferred_boundary_condition_mode": DEFAULT_BOUNDARY_CONDITION_MODE,
        "fallback_discretization_family": FALLBACK_FINE_DISCRETIZATION_FAMILY,
        "fallback_mass_treatment": FALLBACK_MASS_TREATMENT,
        "fallback_normalization": FALLBACK_NORMALIZATION,
    }


def build_operator_bundle_metadata(
    *,
    bundle_paths: GeometryBundlePaths,
    asset_statuses: Mapping[str, str],
    meshing_config_snapshot: Mapping[str, Any],
    bundle_metadata: Mapping[str, Any] | None = None,
    realized_operator_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    operator_asset_statuses = _operator_asset_statuses(asset_statuses)
    bundle_metadata = dict(bundle_metadata or {})
    realized_operator_metadata = dict(realized_operator_metadata or {})

    patch_hops = meshing_config_snapshot.get("patch_hops")
    patch_vertex_cap = meshing_config_snapshot.get("patch_vertex_cap")
    patch_generation_method = bundle_metadata.get("patch_generation_method")
    restriction_available = operator_asset_statuses[TRANSFER_OPERATORS_KEY] == ASSET_STATUS_READY
    fine_operator_available = operator_asset_statuses[FINE_OPERATOR_KEY] == ASSET_STATUS_READY
    coarse_operator_available = operator_asset_statuses[COARSE_OPERATOR_KEY] == ASSET_STATUS_READY
    realized_metadata_present = bool(realized_operator_metadata)
    restriction_mode = str(
        realized_operator_metadata.get(
            "transfer_restriction_mode",
            meshing_config_snapshot.get("transfer_restriction_mode", FALLBACK_TRANSFER_RESTRICTION),
        )
    )
    prolongation_mode = str(
        realized_operator_metadata.get(
            "transfer_prolongation_mode",
            meshing_config_snapshot.get("transfer_prolongation_mode", FALLBACK_TRANSFER_PROLONGATION),
        )
    )
    restriction_preserves_mass = bool(
        realized_operator_metadata.get("transfer_preserves_mass_or_area_totals", restriction_available)
    )
    normalized_state_transfer_available = bool(
        realized_operator_metadata.get("normalized_state_transfer_available", restriction_available)
    )

    fine_operator_path = (
        bundle_paths.fine_operator_path if fine_operator_available and realized_metadata_present else bundle_paths.surface_graph_path
    )
    fine_operator_asset = {
        "path": str(fine_operator_path),
        "status": operator_asset_statuses[FINE_OPERATOR_KEY],
    }
    if not (fine_operator_available and realized_metadata_present):
        fine_operator_asset.update(_operator_asset_alias(FINE_OPERATOR_KEY))

    coarse_operator_path = (
        bundle_paths.coarse_operator_path
        if coarse_operator_available and realized_metadata_present
        else bundle_paths.patch_graph_path
    )
    coarse_operator_asset = {
        "path": str(coarse_operator_path),
        "status": operator_asset_statuses[COARSE_OPERATOR_KEY],
    }
    if not (coarse_operator_available and realized_metadata_present):
        coarse_operator_asset.update(_operator_asset_alias(COARSE_OPERATOR_KEY))

    if realized_metadata_present:
        geodesic_neighborhood = copy.deepcopy(dict(realized_operator_metadata.get("geodesic_neighborhood", {})))
        geodesic_neighborhood["patch_hops"] = int(patch_hops) if patch_hops is not None else None
        geodesic_neighborhood["patch_vertex_cap"] = int(patch_vertex_cap) if patch_vertex_cap is not None else None
        geodesic_neighborhood["patch_generation_method"] = (
            str(patch_generation_method) if patch_generation_method is not None else ""
        )
        metadata = {
            "contract_version": OPERATOR_BUNDLE_CONTRACT_VERSION,
            "status": _bundle_status(operator_asset_statuses),
            "realization_mode": str(realized_operator_metadata["realization_mode"]),
            "preferred_discretization_family": str(
                realized_operator_metadata.get("preferred_discretization_family", DEFAULT_FINE_DISCRETIZATION_FAMILY)
            ),
            "discretization_family": str(
                realized_operator_metadata.get("discretization_family", DEFAULT_FINE_DISCRETIZATION_FAMILY)
            ),
            "mass_treatment": str(realized_operator_metadata.get("mass_treatment", DEFAULT_MASS_TREATMENT)),
            "normalization": str(realized_operator_metadata.get("normalization", DEFAULT_NORMALIZATION)),
            "boundary_condition_mode": str(
                realized_operator_metadata.get("boundary_condition_mode", DEFAULT_BOUNDARY_CONDITION_MODE)
            ),
            "fallback_policy": copy.deepcopy(
                dict(
                    realized_operator_metadata.get(
                        "fallback_policy",
                        {
                            "allowed": True,
                            "used": False,
                            "reason": "",
                            "fallback_discretization_family": FALLBACK_FINE_DISCRETIZATION_FAMILY,
                        },
                    )
                )
            ),
            "geodesic_neighborhood": geodesic_neighborhood,
            "transfer_operators": {
                "surface_to_patch_membership": {
                    "available": restriction_available,
                    "path": str(bundle_paths.transfer_operator_path),
                    "representation": "csr_membership_and_surface_to_patch",
                },
                "fine_to_coarse_restriction": {
                    "available": restriction_available,
                    "path": str(bundle_paths.transfer_operator_path),
                    "normalization": restriction_mode,
                    "conserves_constant_field": restriction_available,
                    "preserves_mass_or_area_totals": restriction_preserves_mass,
                },
                "coarse_to_fine_prolongation": {
                    "available": restriction_available,
                    "path": str(bundle_paths.transfer_operator_path),
                    "normalization": prolongation_mode,
                    "partition_of_unity": restriction_available,
                },
                "normalized_state_transfer": {
                    "available": normalized_state_transfer_available,
                    "path": str(bundle_paths.transfer_operator_path),
                    "normalization": "mass_normalized_patch_basis",
                    "adjoint_pair": normalized_state_transfer_available,
                },
                "fine_operator_available": fine_operator_available,
                "coarse_operator_available": coarse_operator_available,
            },
            "assets": {
                FINE_OPERATOR_KEY: fine_operator_asset,
                COARSE_OPERATOR_KEY: coarse_operator_asset,
                TRANSFER_OPERATORS_KEY: {
                    "path": str(bundle_paths.transfer_operator_path),
                    "status": operator_asset_statuses[TRANSFER_OPERATORS_KEY],
                },
                OPERATOR_METADATA_KEY: {
                    "path": str(bundle_paths.operator_metadata_path),
                    "status": operator_asset_statuses[OPERATOR_METADATA_KEY],
                },
            },
        }
        for extra_field in (
            "weighting_scheme",
            "operator_matrix_role",
            "stiffness_matrix_role",
            "mass_matrix_role",
            "coarse_discretization_family",
            "coarse_mass_treatment",
            "transfer_restriction_mode",
            "transfer_prolongation_mode",
            "transfer_preserves_mass_or_area_totals",
            "normalized_state_transfer_available",
            "coarse_operator_construction",
            "coarse_operator_quality_metrics",
            "orientation_convention",
            "matrix_properties",
            "supporting_geometry",
            "counts",
        ):
            if extra_field in realized_operator_metadata:
                metadata[extra_field] = copy.deepcopy(realized_operator_metadata[extra_field])
        return metadata

    return {
        "contract_version": OPERATOR_BUNDLE_CONTRACT_VERSION,
        "status": _bundle_status(operator_asset_statuses),
        "realization_mode": "graph_laplacian_fallback",
        "preferred_discretization_family": DEFAULT_FINE_DISCRETIZATION_FAMILY,
        "discretization_family": FALLBACK_FINE_DISCRETIZATION_FAMILY,
        "mass_treatment": FALLBACK_MASS_TREATMENT,
        "normalization": FALLBACK_NORMALIZATION,
        "boundary_condition_mode": DEFAULT_BOUNDARY_CONDITION_MODE,
        "fallback_policy": {
            "allowed": True,
            "reason": "cotangent_operators_not_serialized_in_milestone5_bundle",
            "fallback_discretization_family": FALLBACK_FINE_DISCRETIZATION_FAMILY,
        },
        "geodesic_neighborhood": {
            "mode": FALLBACK_GEODESIC_NEIGHBORHOOD_MODE,
            "patch_hops": int(patch_hops) if patch_hops is not None else None,
            "patch_vertex_cap": int(patch_vertex_cap) if patch_vertex_cap is not None else None,
            "patch_generation_method": (
                str(patch_generation_method) if patch_generation_method is not None else ""
            ),
        },
        "transfer_operators": {
            "surface_to_patch_membership": {
                "available": restriction_available,
                "path": str(bundle_paths.transfer_operator_path),
                "representation": "csr_membership_and_surface_to_patch",
            },
            "fine_to_coarse_restriction": {
                "available": restriction_available,
                "path": str(bundle_paths.transfer_operator_path),
                "normalization": FALLBACK_TRANSFER_RESTRICTION,
                "conserves_constant_field": restriction_available,
            },
            "coarse_to_fine_prolongation": {
                "available": restriction_available,
                "path": str(bundle_paths.transfer_operator_path),
                "normalization": FALLBACK_TRANSFER_PROLONGATION,
                "partition_of_unity": restriction_available,
            },
            "fine_operator_available": fine_operator_available,
            "coarse_operator_available": coarse_operator_available,
        },
        "assets": {
            FINE_OPERATOR_KEY: fine_operator_asset,
            COARSE_OPERATOR_KEY: coarse_operator_asset,
            TRANSFER_OPERATORS_KEY: {
                "path": str(bundle_paths.transfer_operator_path),
                "status": operator_asset_statuses[TRANSFER_OPERATORS_KEY],
            },
            OPERATOR_METADATA_KEY: {
                "path": str(bundle_paths.operator_metadata_path),
                "status": operator_asset_statuses[OPERATOR_METADATA_KEY],
            },
        },
    }


def parse_operator_bundle_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Operator bundle metadata must be a mapping.")

    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "status",
        "realization_mode",
        "preferred_discretization_family",
        "discretization_family",
        "mass_treatment",
        "normalization",
        "boundary_condition_mode",
        "fallback_policy",
        "geodesic_neighborhood",
        "transfer_operators",
        "assets",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"Operator bundle metadata is missing required fields: {missing_fields}")
    if normalized["contract_version"] != OPERATOR_BUNDLE_CONTRACT_VERSION:
        raise ValueError(
            "Operator bundle metadata contract_version does not match "
            f"{OPERATOR_BUNDLE_CONTRACT_VERSION!r}."
        )
    for field in ("fallback_policy", "geodesic_neighborhood", "transfer_operators", "assets"):
        if not isinstance(normalized[field], dict):
            raise ValueError(f"Operator bundle field {field!r} must be a mapping.")
    return normalized


def load_operator_bundle_metadata(metadata_path: str | Path) -> dict[str, Any]:
    path = Path(metadata_path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_operator_bundle_metadata(payload)


def discover_operator_bundle_paths(record: Mapping[str, Any]) -> dict[str, Path]:
    operator_bundle = record.get("operator_bundle")
    if not isinstance(operator_bundle, Mapping):
        raise ValueError("Manifest record does not contain an operator_bundle mapping.")
    assets = operator_bundle.get("assets")
    if not isinstance(assets, Mapping):
        raise ValueError("Manifest record operator_bundle.assets is not a mapping.")

    discovered: dict[str, Path] = {}
    for asset_key in (FINE_OPERATOR_KEY, COARSE_OPERATOR_KEY, TRANSFER_OPERATORS_KEY, OPERATOR_METADATA_KEY):
        asset_record = assets.get(asset_key)
        if not isinstance(asset_record, Mapping):
            raise ValueError(f"Operator asset {asset_key!r} is missing from the manifest record.")
        asset_path = asset_record.get("path")
        if not isinstance(asset_path, str) or not asset_path:
            raise ValueError(f"Operator asset {asset_key!r} is missing a usable path.")
        discovered[asset_key] = Path(asset_path)
    return discovered


def build_geometry_manifest_record(
    *,
    bundle_paths: GeometryBundlePaths,
    asset_statuses: dict[str, str],
    dataset_name: str,
    materialization_version: int | str | None,
    meshing_config_snapshot: dict[str, Any],
    registry_metadata: dict[str, Any] | None = None,
    bundle_metadata: dict[str, Any] | None = None,
    raw_asset_provenance: dict[str, Any] | None = None,
    operator_bundle_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry_metadata = dict(registry_metadata or {})
    record: dict[str, Any] = {
        "root_id": int(bundle_paths.root_id),
        "bundle_version": GEOMETRY_ASSET_CONTRACT_VERSION,
        "bundle_status": _bundle_status(asset_statuses),
        "assets": manifest_asset_records(bundle_paths, asset_statuses=asset_statuses),
        "artifact_sources": manifest_artifact_sources(bundle_paths, asset_statuses=asset_statuses),
        "build": {
            "flywire_dataset": str(dataset_name),
            "materialization_version": materialization_version,
            "meshing_config_snapshot": copy.deepcopy(meshing_config_snapshot),
        },
        "operator_bundle": (
            parse_operator_bundle_metadata(operator_bundle_metadata)
            if operator_bundle_metadata is not None
            else build_operator_bundle_metadata(
                bundle_paths=bundle_paths,
                asset_statuses=asset_statuses,
                meshing_config_snapshot=meshing_config_snapshot,
                bundle_metadata=bundle_metadata,
            )
        ),
        "registry_metadata": registry_metadata,
        "raw_mesh_path": str(bundle_paths.raw_mesh_path),
        "raw_skeleton_path": str(bundle_paths.raw_skeleton_path),
        "processed_mesh_path": str(bundle_paths.simplified_mesh_path),
        "processed_graph_path": str(bundle_paths.surface_graph_path),
        "surface_graph_path": str(bundle_paths.surface_graph_path),
        "patch_graph_path": str(bundle_paths.patch_graph_path),
        "transfer_operator_path": str(bundle_paths.transfer_operator_path),
        "operator_metadata_path": str(bundle_paths.operator_metadata_path),
        "descriptor_sidecar_path": str(bundle_paths.descriptor_sidecar_path),
        "qa_sidecar_path": str(bundle_paths.qa_sidecar_path),
        "meta_json_path": str(bundle_paths.legacy_meta_json_path),
        "cell_type": str(registry_metadata.get("cell_type", "")),
        "project_role": str(registry_metadata.get("project_role", "")),
        "snapshot_version": str(registry_metadata.get("snapshot_version", "")),
        "materialization_version": str(registry_metadata.get("materialization_version", "")),
    }
    if bundle_metadata:
        record["bundle_metadata"] = copy.deepcopy(bundle_metadata)
    if raw_asset_provenance:
        record["raw_asset_provenance"] = copy.deepcopy(raw_asset_provenance)
    return record


def build_geometry_manifest(
    *,
    bundle_records: dict[int | str, dict[str, Any]],
    dataset_name: str,
    materialization_version: int | str | None,
    meshing_config_snapshot: dict[str, Any],
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "_asset_contract_version": GEOMETRY_ASSET_CONTRACT_VERSION,
        "_dataset": {
            "flywire_dataset": str(dataset_name),
            "materialization_version": materialization_version,
        },
        "_meshing_config_snapshot": copy.deepcopy(meshing_config_snapshot),
        "_operator_contract_version": OPERATOR_BUNDLE_CONTRACT_VERSION,
        "_operator_contract": build_operator_bundle_manifest_metadata(),
    }
    for root_id, record in bundle_records.items():
        manifest[str(int(root_id))] = copy.deepcopy(record)
    return manifest


def write_geometry_manifest(
    *,
    manifest_path: str | Path,
    bundle_records: dict[int | str, dict[str, Any]],
    dataset_name: str,
    materialization_version: int | str | None,
    meshing_config_snapshot: dict[str, Any],
) -> Path:
    manifest = build_geometry_manifest(
        bundle_records=bundle_records,
        dataset_name=dataset_name,
        materialization_version=materialization_version,
        meshing_config_snapshot=meshing_config_snapshot,
    )
    return write_json(manifest, manifest_path)


def load_geometry_manifest(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Geometry manifest at {path} is not a mapping.")
    return payload


def load_geometry_manifest_records(manifest_path: str | Path) -> dict[str, dict[str, Any]]:
    payload = load_geometry_manifest(manifest_path)
    return {
        key: copy.deepcopy(value)
        for key, value in payload.items()
        if not str(key).startswith("_") and isinstance(value, dict)
    }


def merge_geometry_manifest_record(
    existing_record: dict[str, Any] | None,
    updated_record: dict[str, Any],
) -> dict[str, Any]:
    if existing_record is None:
        return copy.deepcopy(updated_record)

    merged = copy.deepcopy(existing_record)
    for key, value in updated_record.items():
        if key in {"assets", "build"} and isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = copy.deepcopy(merged[key])
            nested.update(copy.deepcopy(value))
            merged[key] = nested
            continue
        merged[key] = copy.deepcopy(value)

    assets = merged.get("assets", {})
    if isinstance(assets, dict):
        asset_statuses = {
            asset_key: str(asset_record.get("status", ASSET_STATUS_MISSING))
            for asset_key, asset_record in assets.items()
            if isinstance(asset_record, dict)
        }
        if asset_statuses:
            merged["bundle_status"] = _bundle_status(asset_statuses)
    return merged


def _operator_asset_statuses(asset_statuses: Mapping[str, str]) -> dict[str, str]:
    return {
        FINE_OPERATOR_KEY: str(
            asset_statuses.get(FINE_OPERATOR_KEY, asset_statuses.get(SURFACE_GRAPH_KEY, ASSET_STATUS_MISSING))
        ),
        COARSE_OPERATOR_KEY: str(
            asset_statuses.get(COARSE_OPERATOR_KEY, asset_statuses.get(PATCH_GRAPH_KEY, ASSET_STATUS_MISSING))
        ),
        TRANSFER_OPERATORS_KEY: str(asset_statuses.get(TRANSFER_OPERATORS_KEY, ASSET_STATUS_MISSING)),
        OPERATOR_METADATA_KEY: str(asset_statuses.get(OPERATOR_METADATA_KEY, ASSET_STATUS_MISSING)),
    }


def _operator_asset_alias(asset_key: str) -> dict[str, str]:
    if asset_key == FINE_OPERATOR_KEY:
        return {"legacy_alias": SURFACE_GRAPH_KEY}
    if asset_key == COARSE_OPERATOR_KEY:
        return {"legacy_alias": PATCH_GRAPH_KEY}
    return {}


def _bundle_status(asset_statuses: Mapping[str, str]) -> str:
    statuses = [str(status) for status in asset_statuses.values()]
    if statuses and all(status in {ASSET_STATUS_READY, ASSET_STATUS_SKIPPED} for status in statuses):
        return ASSET_STATUS_READY
    if any(status == ASSET_STATUS_READY for status in statuses):
        return "partial"
    if statuses and all(status == ASSET_STATUS_SKIPPED for status in statuses):
        return ASSET_STATUS_SKIPPED
    if statuses and any(status == ASSET_STATUS_SKIPPED for status in statuses):
        if all(status in {ASSET_STATUS_MISSING, ASSET_STATUS_SKIPPED} for status in statuses):
            return ASSET_STATUS_MISSING
    return ASSET_STATUS_MISSING
