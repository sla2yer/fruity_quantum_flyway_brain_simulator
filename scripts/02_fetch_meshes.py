#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

from _startup import bootstrap_runtime

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


def _bootstrap_dependencies():
    from dotenv import load_dotenv
    from tqdm import tqdm

    import flywire_wave.geometry_contract as geometry_contract
    import flywire_wave.io_utils as io_utils
    import flywire_wave.mesh_pipeline as mesh_pipeline
    import flywire_wave.registry as registry_module
    from flywire_wave.auth import ensure_flywire_secret
    from flywire_wave.config import load_config

    return (
        load_dotenv,
        tqdm,
        ensure_flywire_secret,
        load_config,
        geometry_contract,
        io_utils,
        mesh_pipeline,
        registry_module,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch per-neuron FlyWire meshes/skeletons.")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the YAML config file. Relative paths inside config.paths resolve from the repository root.",
    )
    parser.add_argument(
        "--refetch-meshes",
        action="store_true",
        help="Ignore healthy cached raw meshes and fetch them again.",
    )
    parser.add_argument(
        "--refetch-skeletons",
        action="store_true",
        help="Ignore healthy cached skeletons and fetch them again.",
    )
    parser.add_argument(
        "--require-skeletons",
        action="store_true",
        help="Treat skeleton download failures as fatal for this run.",
    )
    args = parser.parse_args()

    dependencies = bootstrap_runtime("meshes", _bootstrap_dependencies)
    if dependencies is None:
        return 1
    (
        load_dotenv,
        progress,
        ensure_flywire_secret,
        load_config,
        geometry_contract,
        io_utils,
        mesh_pipeline,
        registry_module,
    ) = dependencies

    load_dotenv(ROOT / ".env")
    token = os.getenv("FLYWIRE_TOKEN", "").strip()

    cfg = load_config(args.config)
    paths = cfg["paths"]
    meshing = dict(cfg["meshing"])
    if args.refetch_meshes:
        meshing["refetch_meshes"] = True
    if args.refetch_skeletons:
        meshing["refetch_skeletons"] = True
    if args.require_skeletons:
        meshing["require_skeletons"] = True
    dataset = cfg["dataset"].get("flywire_dataset", "public")
    materialization_version = cfg["dataset"].get("materialization_version")
    registry_path = paths.get("neuron_registry_csv", "data/interim/registry/neuron_registry.csv")
    fetch_skeletons = bool(meshing.get("fetch_skeletons", True))
    refetch_meshes = bool(meshing.get("refetch_meshes", False))
    refetch_skeletons = bool(meshing.get("refetch_skeletons", False))
    require_skeletons = bool(meshing.get("require_skeletons", False))

    if require_skeletons and not fetch_skeletons:
        raise ValueError("meshing.require_skeletons cannot be true when meshing.fetch_skeletons is false.")

    if token:
        try:
            token_sync = ensure_flywire_secret(token)
            if token_sync == "updated":
                print("Synced FLYWIRE_TOKEN into local FlyWire secret storage for fafbseg.")
        except Exception as exc:
            raise RuntimeError("Could not set FlyWire token for fafbseg.") from exc

    root_ids = io_utils.read_root_ids(paths["selected_root_ids"])
    if not root_ids:
        raise RuntimeError("No root IDs found. Run scripts/01_select_subset.py first.")

    registry = registry_module.load_neuron_registry(registry_path)
    registry_module.validate_selected_root_ids(root_ids, registry, registry_path)

    print(f"Fetching {len(root_ids)} neurons validated against {registry_path}.")

    existing_records = geometry_contract.load_geometry_manifest_records(paths["manifest_json"])
    manifest_records: dict[int, dict[str, object]] = {}
    failures: list[str] = []
    fetch_status_counts = {
        geometry_contract.RAW_MESH_KEY: Counter(),
        geometry_contract.RAW_SKELETON_KEY: Counter(),
    }
    for root_id in progress(root_ids, desc="Fetching meshes"):
        bundle_paths = geometry_contract.build_geometry_bundle_paths(
            root_id,
            meshes_raw_dir=paths["meshes_raw_dir"],
            skeletons_raw_dir=paths["skeletons_raw_dir"],
            processed_mesh_dir=paths["processed_mesh_dir"],
            processed_graph_dir=paths["processed_graph_dir"],
        )
        asset_statuses = geometry_contract.default_asset_statuses(fetch_skeletons=fetch_skeletons)
        raw_asset_provenance: dict[str, object] = {}
        try:
            fetch_outputs = mesh_pipeline.fetch_mesh_and_optional_skeleton(
                root_id=root_id,
                bundle_paths=bundle_paths,
                flywire_dataset=dataset,
                fetch_skeletons=fetch_skeletons,
                refetch_mesh=refetch_meshes,
                refetch_skeleton=refetch_skeletons,
                require_skeletons=require_skeletons,
            )
            asset_statuses.update(fetch_outputs["asset_statuses"])
            raw_asset_provenance = dict(fetch_outputs["raw_asset_provenance"])
        except mesh_pipeline.RawAssetFetchError as exc:
            asset_statuses.update(exc.asset_statuses)
            raw_asset_provenance = dict(exc.raw_asset_provenance)
            failures.append(str(exc))

        new_record = geometry_contract.build_geometry_manifest_record(
            bundle_paths=bundle_paths,
            asset_statuses=asset_statuses,
            dataset_name=str(dataset),
            materialization_version=materialization_version,
            meshing_config_snapshot=meshing,
            raw_asset_provenance=raw_asset_provenance,
        )
        manifest_records[root_id] = geometry_contract.merge_geometry_manifest_record(
            existing_records.get(bundle_paths.root_label),
            new_record,
        )

        for asset_key in (geometry_contract.RAW_MESH_KEY, geometry_contract.RAW_SKELETON_KEY):
            asset_provenance = raw_asset_provenance.get(asset_key, {})
            fetch_status = str(asset_provenance.get("fetch_status", geometry_contract.FETCH_STATUS_FAILED))
            fetch_status_counts[asset_key][fetch_status] += 1

    geometry_contract.write_geometry_manifest(
        manifest_path=paths["manifest_json"],
        bundle_records=manifest_records,
        dataset_name=str(dataset),
        materialization_version=materialization_version,
        meshing_config_snapshot=meshing,
    )
    print(
        json.dumps(
            {
                "n_assets": len(manifest_records),
                "manifest": paths["manifest_json"],
                "mesh_fetch_status_counts": dict(fetch_status_counts[geometry_contract.RAW_MESH_KEY]),
                "skeleton_fetch_status_counts": dict(fetch_status_counts[geometry_contract.RAW_SKELETON_KEY]),
                "failure_count": len(failures),
            },
            indent=2,
        )
    )
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
