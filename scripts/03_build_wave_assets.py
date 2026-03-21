#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.config import load_config
from flywire_wave.geometry_contract import (
    build_geometry_bundle_paths,
    build_geometry_manifest_record,
    default_asset_statuses,
    load_geometry_manifest_records,
    merge_geometry_manifest_record,
    write_geometry_manifest,
)
from flywire_wave.io_utils import read_root_ids
from flywire_wave.mesh_pipeline import process_mesh_into_wave_assets
from flywire_wave.registry import load_neuron_registry, validate_selected_root_ids


def _json_safe(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build simplified mesh + graph assets for wave simulation.")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the YAML config file. Relative paths inside config.paths resolve from the repository root.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = cfg["paths"]
    meshing = cfg["meshing"]
    dataset = cfg["dataset"].get("flywire_dataset", "public")
    materialization_version = cfg["dataset"].get("materialization_version")
    registry_path = paths.get("neuron_registry_csv", "data/interim/registry/neuron_registry.csv")

    root_ids = read_root_ids(paths["selected_root_ids"])
    if not root_ids:
        raise RuntimeError("No root IDs found. Run scripts/01_select_subset.py first.")

    registry_df = load_neuron_registry(registry_path)
    validate_selected_root_ids(root_ids, registry_df, registry_path)

    registry = registry_df.set_index("root_id", drop=False)
    existing_records = load_geometry_manifest_records(paths["manifest_json"])
    manifest_records: dict[int, dict[str, object]] = {}
    qa_warning_details: list[dict[str, object]] = []
    qa_failure_details: list[dict[str, object]] = []
    qa_blocking_failure_details: list[dict[str, object]] = []
    fetch_skeletons = bool(meshing.get("fetch_skeletons", True))
    for root_id in tqdm(root_ids, desc="Building wave assets"):
        bundle_paths = build_geometry_bundle_paths(
            root_id,
            meshes_raw_dir=paths["meshes_raw_dir"],
            skeletons_raw_dir=paths["skeletons_raw_dir"],
            processed_mesh_dir=paths["processed_mesh_dir"],
            processed_graph_dir=paths["processed_graph_dir"],
        )
        if not bundle_paths.raw_mesh_path.exists():
            raise FileNotFoundError(f"Missing raw mesh for root_id={root_id}: {bundle_paths.raw_mesh_path}")

        registry_metadata: dict[str, object] = {}
        if int(root_id) in registry.index:
            row = registry.loc[int(root_id)]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            registry_metadata = {
                key: _json_safe(value)
                for key, value in row.to_dict().items()
                if not pd.isna(value)
            }

        outputs = process_mesh_into_wave_assets(
            root_id=root_id,
            bundle_paths=bundle_paths,
            simplify_target_faces=int(meshing.get("simplify_target_faces", 15000)),
            patch_hops=int(meshing.get("patch_hops", 6)),
            patch_vertex_cap=int(meshing.get("patch_vertex_cap", 2500)),
            fine_geodesic_hops=int(meshing.get("fine_geodesic_hops", 2)),
            fine_geodesic_vertex_cap=int(meshing.get("fine_geodesic_vertex_cap", 32)),
            registry_metadata=registry_metadata,
            qa_thresholds=meshing.get("qa_thresholds"),
        )
        qa_summary = outputs["qa_summary"]
        if qa_summary["warning_count"]:
            qa_warning_details.append(
                {
                    "root_id": int(root_id),
                    "checks": list(qa_summary["warning_checks"]),
                }
            )
        if qa_summary["failure_count"]:
            qa_failure_details.append(
                {
                    "root_id": int(root_id),
                    "checks": list(qa_summary["failure_checks"]),
                    "blocking": bool(qa_summary["blocking_failure_count"]),
                }
            )
        if qa_summary["blocking_failure_count"]:
            qa_blocking_failure_details.append(
                {
                    "root_id": int(root_id),
                    "checks": list(qa_summary["blocking_failure_checks"]),
                }
            )
        asset_statuses = default_asset_statuses(fetch_skeletons=fetch_skeletons)
        asset_statuses.update(outputs["asset_statuses"])
        existing_record = existing_records.get(bundle_paths.root_label, {})
        manifest_records[root_id] = merge_geometry_manifest_record(
            existing_record,
            build_geometry_manifest_record(
                bundle_paths=bundle_paths,
                asset_statuses=asset_statuses,
                dataset_name=str(dataset),
                materialization_version=materialization_version,
                meshing_config_snapshot=meshing,
                registry_metadata=registry_metadata,
                bundle_metadata=outputs["bundle_metadata"],
                raw_asset_provenance=existing_record.get("raw_asset_provenance"),
                operator_bundle_metadata=outputs["operator_bundle_metadata"],
            ),
        )

    write_geometry_manifest(
        manifest_path=paths["manifest_json"],
        bundle_records=manifest_records,
        dataset_name=str(dataset),
        materialization_version=materialization_version,
        meshing_config_snapshot=meshing,
    )
    qa_overall_status = "pass"
    if qa_failure_details:
        qa_overall_status = "fail"
    elif qa_warning_details:
        qa_overall_status = "warn"
    print(
        json.dumps(
            {
                "n_assets": len(manifest_records),
                "manifest": paths["manifest_json"],
                "registry": registry_path,
                "qa": {
                    "overall_status": qa_overall_status,
                    "downstream_usable": not bool(qa_blocking_failure_details),
                    "warning_asset_count": len(qa_warning_details),
                    "failure_asset_count": len(qa_failure_details),
                    "blocking_failure_asset_count": len(qa_blocking_failure_details),
                    "warning_root_ids": [item["root_id"] for item in qa_warning_details],
                    "failure_root_ids": [item["root_id"] for item in qa_failure_details],
                    "blocking_failure_root_ids": [item["root_id"] for item in qa_blocking_failure_details],
                    "warning_details": qa_warning_details,
                    "failure_details": qa_failure_details,
                    "blocking_failure_details": qa_blocking_failure_details,
                },
            },
            indent=2,
        )
    )
    if qa_blocking_failure_details:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
