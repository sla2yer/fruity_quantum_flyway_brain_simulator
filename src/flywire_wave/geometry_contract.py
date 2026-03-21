from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import write_json


GEOMETRY_ASSET_CONTRACT_VERSION = "geometry_bundle.v1"
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
PROCESSED_ASSET_KEYS = (
    SIMPLIFIED_MESH_KEY,
    SURFACE_GRAPH_KEY,
    PATCH_GRAPH_KEY,
    DESCRIPTOR_SIDECAR_KEY,
    QA_SIDECAR_KEY,
)


@dataclass(frozen=True)
class GeometryBundlePaths:
    root_id: int
    raw_mesh_path: Path
    raw_skeleton_path: Path
    simplified_mesh_path: Path
    surface_graph_path: Path
    patch_graph_path: Path
    descriptor_sidecar_path: Path
    qa_sidecar_path: Path
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
        patch_graph_path=graph_dir / f"{root_label}_patch_graph.npz",
        descriptor_sidecar_path=graph_dir / f"{root_label}_descriptors.json",
        qa_sidecar_path=graph_dir / f"{root_label}_qa.json",
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
        "registry_metadata": registry_metadata,
        "raw_mesh_path": str(bundle_paths.raw_mesh_path),
        "raw_skeleton_path": str(bundle_paths.raw_skeleton_path),
        "processed_mesh_path": str(bundle_paths.simplified_mesh_path),
        "processed_graph_path": str(bundle_paths.surface_graph_path),
        "surface_graph_path": str(bundle_paths.surface_graph_path),
        "patch_graph_path": str(bundle_paths.patch_graph_path),
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


def _bundle_status(asset_statuses: dict[str, str]) -> str:
    required_assets = (
        RAW_MESH_KEY,
        SIMPLIFIED_MESH_KEY,
        SURFACE_GRAPH_KEY,
        PATCH_GRAPH_KEY,
        DESCRIPTOR_SIDECAR_KEY,
        QA_SIDECAR_KEY,
    )
    if all(asset_statuses[key] == ASSET_STATUS_READY for key in required_assets):
        skeleton_status = asset_statuses.get(RAW_SKELETON_KEY, ASSET_STATUS_SKIPPED)
        if skeleton_status in {ASSET_STATUS_READY, ASSET_STATUS_SKIPPED}:
            return ASSET_STATUS_READY
    if any(status == ASSET_STATUS_READY for status in asset_statuses.values()):
        return "partial"
    return ASSET_STATUS_MISSING
