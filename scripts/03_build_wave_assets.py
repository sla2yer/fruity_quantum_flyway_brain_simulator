#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _startup import bootstrap_runtime

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


def _bootstrap_dependencies():
    import pandas as pd
    from tqdm import tqdm

    import flywire_wave.coupling_contract as coupling_contract
    import flywire_wave.geometry_contract as geometry_contract
    import flywire_wave.io_utils as io_utils
    import flywire_wave.mesh_pipeline as mesh_pipeline
    import flywire_wave.registry as registry_module
    import flywire_wave.synapse_mapping as synapse_mapping
    from flywire_wave.config import load_config

    return (
        pd,
        tqdm,
        load_config,
        coupling_contract,
        geometry_contract,
        io_utils,
        mesh_pipeline,
        registry_module,
        synapse_mapping,
    )


def _json_safe(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return str(value)


def _asset_statuses_for_attempt(
    *,
    bundle_paths: object,
    fetch_skeletons: bool,
    geometry_contract: object,
) -> dict[str, str]:
    asset_statuses = geometry_contract.default_asset_statuses(fetch_skeletons=fetch_skeletons)
    raw_mesh_path = getattr(bundle_paths, "raw_mesh_path")
    raw_skeleton_path = getattr(bundle_paths, "raw_skeleton_path")
    if Path(raw_mesh_path).exists():
        asset_statuses[geometry_contract.RAW_MESH_KEY] = geometry_contract.ASSET_STATUS_READY
    if Path(raw_skeleton_path).exists():
        asset_statuses[geometry_contract.RAW_SKELETON_KEY] = geometry_contract.ASSET_STATUS_READY
    return asset_statuses


def main() -> int:
    parser = argparse.ArgumentParser(description="Build simplified mesh + graph assets for wave simulation.")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the YAML config file. Relative paths inside config.paths resolve from the repository root.",
    )
    args = parser.parse_args()

    dependencies = bootstrap_runtime("assets", _bootstrap_dependencies)
    if dependencies is None:
        return 1
    (
        pd,
        progress,
        load_config,
        coupling_contract,
        geometry_contract,
        io_utils,
        mesh_pipeline,
        registry_module,
        synapse_mapping,
    ) = dependencies

    cfg = load_config(args.config)
    paths = cfg["paths"]
    meshing = dict(cfg["meshing"])
    meshing["operator_assembly"] = geometry_contract.normalize_operator_assembly_config(
        meshing.get("operator_assembly")
    )
    meshing["coupling_assembly"] = coupling_contract.normalize_coupling_assembly_config(
        meshing.get("coupling_assembly")
    )
    dataset = cfg["dataset"].get("flywire_dataset", "public")
    materialization_version = cfg["dataset"].get("materialization_version")
    registry_path = paths.get("neuron_registry_csv", "data/interim/registry/neuron_registry.csv")
    processed_coupling_dir = paths.get("processed_coupling_dir")

    root_ids = io_utils.read_root_ids(paths["selected_root_ids"])
    if not root_ids:
        raise RuntimeError("No root IDs found. Run scripts/01_select_subset.py first.")

    registry_df = registry_module.load_neuron_registry(registry_path)
    registry_module.validate_selected_root_ids(root_ids, registry_df, registry_path)

    registry = registry_df.set_index("root_id", drop=False)
    existing_records = geometry_contract.load_geometry_manifest_records(paths["manifest_json"])
    manifest_records: dict[int, dict[str, object]] = {}
    root_results: dict[int, dict[str, object]] = {}
    built_root_ids: list[int] = []
    skipped_root_ids: list[int] = []
    failed_root_ids: list[int] = []
    missing_raw_mesh_details: list[dict[str, object]] = []
    processing_failure_details: list[dict[str, object]] = []
    qa_warning_details: list[dict[str, object]] = []
    qa_failure_details: list[dict[str, object]] = []
    qa_blocking_failure_details: list[dict[str, object]] = []
    coupling_summary: dict[str, object] = {
        "overall_status": "missing",
        "reason": "coupling_mapping_not_attempted",
        "synapse_count": 0,
        "edge_count": 0,
        "root_summaries": {},
    }
    coupling_failed = False
    fetch_skeletons = bool(meshing.get("fetch_skeletons", True))
    for root_id in progress(root_ids, desc="Building wave assets"):
        bundle_paths = geometry_contract.build_geometry_bundle_paths(
            root_id,
            meshes_raw_dir=paths["meshes_raw_dir"],
            skeletons_raw_dir=paths["skeletons_raw_dir"],
            processed_mesh_dir=paths["processed_mesh_dir"],
            processed_graph_dir=paths["processed_graph_dir"],
        )
        asset_statuses = _asset_statuses_for_attempt(
            bundle_paths=bundle_paths,
            fetch_skeletons=fetch_skeletons,
            geometry_contract=geometry_contract,
        )
        existing_record = existing_records.get(bundle_paths.root_label, {})

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

        if not bundle_paths.raw_mesh_path.exists():
            root_result = {
                "status": "skipped",
                "reason": "missing_raw_mesh",
                "blocking": True,
                "asset_statuses": dict(asset_statuses),
                "input_errors": [
                    {
                        "code": "missing_raw_mesh",
                        "asset_key": geometry_contract.RAW_MESH_KEY,
                        "path": str(bundle_paths.raw_mesh_path),
                    }
                ],
                "errors": [],
            }
            manifest_record = geometry_contract.merge_geometry_manifest_record(
                existing_record,
                geometry_contract.build_geometry_manifest_record(
                    bundle_paths=bundle_paths,
                    asset_statuses=asset_statuses,
                    dataset_name=str(dataset),
                    materialization_version=materialization_version,
                    meshing_config_snapshot=meshing,
                    registry_metadata=registry_metadata,
                    raw_asset_provenance=existing_record.get("raw_asset_provenance"),
                    processed_coupling_dir=processed_coupling_dir,
                ),
            )
            manifest_record["build_result"] = root_result
            manifest_records[root_id] = manifest_record
            root_results[root_id] = root_result
            skipped_root_ids.append(int(root_id))
            missing_raw_mesh_details.append(
                {
                    "root_id": int(root_id),
                    "reason": "missing_raw_mesh",
                    "blocking": True,
                    "path": str(bundle_paths.raw_mesh_path),
                }
            )
            continue

        try:
            outputs = mesh_pipeline.process_mesh_into_wave_assets(
                root_id=root_id,
                bundle_paths=bundle_paths,
                simplify_target_faces=int(meshing.get("simplify_target_faces", 15000)),
                patch_hops=int(meshing.get("patch_hops", 6)),
                patch_vertex_cap=int(meshing.get("patch_vertex_cap", 2500)),
                fine_geodesic_hops=int(meshing.get("fine_geodesic_hops", 2)),
                fine_geodesic_vertex_cap=int(meshing.get("fine_geodesic_vertex_cap", 32)),
                operator_assembly=meshing.get("operator_assembly"),
                registry_metadata=registry_metadata,
                qa_thresholds=meshing.get("qa_thresholds"),
            )
        except Exception as exc:
            root_result = {
                "status": "failed",
                "reason": "processing_error",
                "blocking": True,
                "asset_statuses": dict(asset_statuses),
                "input_errors": [],
                "errors": [
                    {
                        "code": "processing_error",
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                ],
            }
            manifest_record = geometry_contract.merge_geometry_manifest_record(
                existing_record,
                geometry_contract.build_geometry_manifest_record(
                    bundle_paths=bundle_paths,
                    asset_statuses=asset_statuses,
                    dataset_name=str(dataset),
                    materialization_version=materialization_version,
                    meshing_config_snapshot=meshing,
                    registry_metadata=registry_metadata,
                    raw_asset_provenance=existing_record.get("raw_asset_provenance"),
                    processed_coupling_dir=processed_coupling_dir,
                ),
            )
            manifest_record["build_result"] = root_result
            manifest_records[root_id] = manifest_record
            root_results[root_id] = root_result
            failed_root_ids.append(int(root_id))
            processing_failure_details.append(
                {
                    "root_id": int(root_id),
                    "reason": "processing_error",
                    "blocking": True,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            continue

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
        asset_statuses.update(outputs["asset_statuses"])
        root_result = {
            "status": "built",
            "reason": "",
            "blocking": bool(qa_summary["blocking_failure_count"]),
            "asset_statuses": dict(asset_statuses),
            "input_errors": [],
            "errors": [],
            "qa_summary": dict(qa_summary),
        }
        manifest_record = geometry_contract.merge_geometry_manifest_record(
            existing_record,
            geometry_contract.build_geometry_manifest_record(
                bundle_paths=bundle_paths,
                asset_statuses=asset_statuses,
                dataset_name=str(dataset),
                materialization_version=materialization_version,
                meshing_config_snapshot=meshing,
                registry_metadata=registry_metadata,
                bundle_metadata=outputs["bundle_metadata"],
                raw_asset_provenance=existing_record.get("raw_asset_provenance"),
                operator_bundle_metadata=outputs["operator_bundle_metadata"],
                processed_coupling_dir=processed_coupling_dir,
            ),
        )
        manifest_record["build_result"] = root_result
        manifest_records[root_id] = manifest_record
        root_results[root_id] = root_result
        built_root_ids.append(int(root_id))

    try:
        mapping_summary = synapse_mapping.materialize_synapse_anchor_maps(
            root_ids=root_ids,
            processed_coupling_dir=processed_coupling_dir,
            meshes_raw_dir=paths["meshes_raw_dir"],
            skeletons_raw_dir=paths["skeletons_raw_dir"],
            processed_mesh_dir=paths["processed_mesh_dir"],
            processed_graph_dir=paths["processed_graph_dir"],
            neuron_registry=registry_df,
            coupling_assembly=meshing.get("coupling_assembly"),
        )
        for root_id, bundle_metadata in mapping_summary["bundle_metadata_by_root"].items():
            normalized_root_id = int(root_id)
            if normalized_root_id in manifest_records:
                manifest_records[normalized_root_id]["coupling_bundle"] = dict(bundle_metadata)
            if normalized_root_id in root_results:
                root_results[normalized_root_id]["coupling"] = dict(
                    mapping_summary["root_summaries"].get(normalized_root_id, {})
                )
                root_results[normalized_root_id]["coupling_bundle_status"] = str(bundle_metadata["status"])
        coupling_summary = {
            "overall_status": (
                "missing"
                if mapping_summary.get("reason") == "missing_local_synapse_registry"
                else "built"
            ),
            "reason": str(mapping_summary.get("reason", "")),
            "synapse_count": int(mapping_summary.get("synapse_count", 0)),
            "edge_count": int(mapping_summary.get("edge_count", 0)),
            "root_summaries": {
                str(root_id): summary
                for root_id, summary in sorted(mapping_summary.get("root_summaries", {}).items())
            },
        }
    except Exception as exc:
        coupling_failed = True
        coupling_summary = {
            "overall_status": "failed",
            "reason": "coupling_mapping_error",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "synapse_count": 0,
            "edge_count": 0,
            "root_summaries": {},
        }

    geometry_contract.write_geometry_manifest(
        manifest_path=paths["manifest_json"],
        bundle_records=manifest_records,
        dataset_name=str(dataset),
        materialization_version=materialization_version,
        meshing_config_snapshot=meshing,
        processed_coupling_dir=processed_coupling_dir,
    )
    qa_overall_status = "pass"
    if qa_failure_details:
        qa_overall_status = "fail"
    elif qa_warning_details:
        qa_overall_status = "warn"
    exit_code = 1 if (missing_raw_mesh_details or processing_failure_details or qa_blocking_failure_details or coupling_failed) else 0
    final_status = "fail" if exit_code else qa_overall_status
    blocking_root_ids = sorted(
        {
            *[item["root_id"] for item in missing_raw_mesh_details],
            *[item["root_id"] for item in processing_failure_details],
            *[item["root_id"] for item in qa_blocking_failure_details],
        }
    )
    summary = {
        "n_assets": len(manifest_records),
        "manifest": paths["manifest_json"],
        "registry": registry_path,
        "build": {
            "overall_status": "fail" if (missing_raw_mesh_details or processing_failure_details) else "pass",
            "requested_root_count": len(root_ids),
            "built_root_count": len(built_root_ids),
            "skipped_root_count": len(skipped_root_ids),
            "failed_root_count": len(failed_root_ids),
            "built_root_ids": built_root_ids,
            "skipped_root_ids": skipped_root_ids,
            "failed_root_ids": failed_root_ids,
            "blocking_root_ids": blocking_root_ids,
            "missing_raw_mesh_count": len(missing_raw_mesh_details),
            "missing_raw_mesh_root_ids": [item["root_id"] for item in missing_raw_mesh_details],
            "missing_raw_mesh_details": missing_raw_mesh_details,
            "processing_failure_count": len(processing_failure_details),
            "processing_failure_root_ids": [item["root_id"] for item in processing_failure_details],
            "processing_failure_details": processing_failure_details,
            "root_results": {str(root_id): result for root_id, result in sorted(root_results.items())},
        },
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
        "coupling": coupling_summary,
        "final_status": final_status,
        "exit_code": exit_code,
    }
    print(
        json.dumps(summary, indent=2)
    )
    if missing_raw_mesh_details:
        missing_roots = ", ".join(str(item["root_id"]) for item in missing_raw_mesh_details)
        print(
            "Missing raw meshes blocked root_ids="
            f"{missing_roots}. Run scripts/02_fetch_meshes.py or correct the selected-root subset, "
            "then rerun scripts/03_build_wave_assets.py.",
            file=sys.stderr,
        )
    if processing_failure_details:
        failed_roots = ", ".join(str(item["root_id"]) for item in processing_failure_details)
        print(
            "Wave asset builds hit per-root processing failures for root_ids="
            f"{failed_roots}. See the JSON summary for structured error details.",
            file=sys.stderr,
        )
    if coupling_failed:
        print(
            "Synapse-anchor mapping failed after geometry build. See the JSON summary for structured coupling "
            "error details.",
            file=sys.stderr,
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
