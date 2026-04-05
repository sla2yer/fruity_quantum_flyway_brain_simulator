from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flywire_wave.coupling_contract import (
    ASSET_STATUS_READY,
    build_coupling_bundle_metadata,
    build_edge_coupling_bundle_reference,
    build_root_coupling_bundle_paths,
)
from flywire_wave.geometry_contract import (
    COARSE_OPERATOR_KEY,
    FINE_OPERATOR_KEY,
    OPERATOR_METADATA_KEY,
    RAW_SKELETON_KEY,
    SIMPLIFIED_MESH_KEY,
    TRANSFER_OPERATORS_KEY,
    build_geometry_bundle_paths,
    build_geometry_manifest_record,
    build_operator_bundle_metadata,
    default_asset_statuses,
    write_geometry_manifest,
)
from flywire_wave.io_utils import write_deterministic_npz, write_json
from flywire_wave.selection import write_selected_root_roster, write_subset_manifest
from flywire_wave.stimulus_bundle import record_stimulus_bundle, resolve_stimulus_input
from flywire_wave.surface_operators import serialize_sparse_matrix


def _write_simulation_fixture(
    tmp_dir: Path,
    *,
    timebase_dt_ms: float | None = None,
    timebase_sample_count: int | None = None,
    root_specs: list[dict[str, object]] | None = None,
    readout_catalog: list[dict[str, object]] | None = None,
    analysis_config: dict[str, object] | None = None,
    experiment_suite_config: dict[str, object] | None = None,
    subset_name: str = "motion_minimal",
) -> Path:
    output_dir = tmp_dir / "out"
    normalized_root_specs = _normalize_root_specs(root_specs)
    selected_root_ids = [spec["root_id"] for spec in normalized_root_specs]
    selected_root_ids_path = output_dir / "selected_root_ids.txt"
    write_selected_root_roster(selected_root_ids, selected_root_ids_path)
    write_subset_manifest(
        subset_output_dir=output_dir / "subsets",
        preset_name=subset_name,
        root_ids=selected_root_ids,
    )

    _write_geometry_manifest(output_dir, root_specs=normalized_root_specs)

    config_path = tmp_dir / "simulation_config.yaml"
    config_payload: dict[str, object] = {
        "paths": {
            "selected_root_ids": str(selected_root_ids_path),
            "subset_output_dir": str(output_dir / "subsets"),
            "manifest_json": str(output_dir / "asset_manifest.json"),
            "processed_stimulus_dir": str(output_dir / "stimuli"),
            "processed_retinal_dir": str(output_dir / "retinal"),
            "processed_simulator_results_dir": str(output_dir / "simulator_results"),
        },
        "selection": {
            "active_preset": subset_name,
        },
        "simulation": {
            "input": {
                "source_kind": "stimulus_bundle",
                "require_recorded_bundle": True,
            },
            "readout_catalog": readout_catalog
            or [
                {
                    "readout_id": "shared_output_mean",
                    "scope": "circuit_output",
                    "aggregation": "mean_over_root_ids",
                    "units": "activation_au",
                    "value_semantics": "shared_downstream_activation",
                    "description": "Shared downstream output mean for matched comparisons.",
                },
                {
                    "readout_id": "direction_selectivity_index",
                    "scope": "comparison_panel",
                    "aggregation": "identity",
                    "units": "unitless",
                    "value_semantics": "direction_selectivity_index",
                    "description": "Shared direction-selectivity summary for matched comparisons.",
                },
            ],
            "baseline_families": {
                "P0": {
                    "membrane_time_constant_ms": 12.5,
                    "recurrent_gain": 0.9,
                },
                "P1": {
                    "membrane_time_constant_ms": 15.0,
                    "synaptic_current_time_constant_ms": 6.0,
                    "delay_handling": {
                        "mode": "from_coupling_bundle",
                        "max_supported_delay_steps": 32,
                    },
                },
            },
            "surface_wave": {
                "parameter_preset": "motion_patch_reference",
                "propagation": {
                    "wave_speed_sq_scale": 1.25,
                    "restoring_strength_per_ms2": 0.07,
                },
                "damping": {
                    "gamma_per_ms": 0.18,
                },
                "recovery": {
                    "mode": "activity_driven_first_order",
                    "time_constant_ms": 14.0,
                    "drive_gain": 0.3,
                    "coupling_strength_per_ms2": 0.12,
                },
                "nonlinearity": {
                    "mode": "tanh_soft_clip",
                    "activation_scale": 1.1,
                },
                "anisotropy": {
                    "mode": "operator_embedded",
                    "strength_scale": 1.05,
                },
            },
        },
    }
    if analysis_config is not None:
        config_payload["analysis"] = json.loads(json.dumps(analysis_config))
    if experiment_suite_config is not None:
        config_payload["experiment_suite"] = json.loads(
            json.dumps(experiment_suite_config)
        )
    if timebase_dt_ms is not None:
        config_payload["simulation"]["timebase"] = {
            "dt_ms": float(timebase_dt_ms),
        }
        if timebase_sample_count is not None:
            config_payload["simulation"]["timebase"]["sample_count"] = int(
                timebase_sample_count
            )
            config_payload["simulation"]["timebase"]["duration_ms"] = float(
                timebase_dt_ms * timebase_sample_count
            )
    config_path.write_text(
        yaml.safe_dump(config_payload, sort_keys=False),
        encoding="utf-8",
    )
    return config_path


def _write_manifest_fixture(
    tmp_dir: Path,
    *,
    surface_wave_fidelity_assignment: dict[str, object] | None = None,
    manifest_overrides: dict[str, object] | None = None,
) -> Path:
    manifest_payload = yaml.safe_load(
        (
            ROOT / "manifests" / "examples" / "milestone_1_demo.yaml"
        ).read_text(encoding="utf-8")
    )
    if surface_wave_fidelity_assignment is not None:
        for arm in manifest_payload["comparison_arms"]:
            if arm["model_mode"] == "surface_wave":
                arm["fidelity_assignment"] = json.loads(
                    json.dumps(surface_wave_fidelity_assignment)
                )
    if manifest_overrides is not None:
        for key, value in manifest_overrides.items():
            manifest_payload[key] = json.loads(json.dumps(value))
    manifest_path = tmp_dir / "fixture_manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(manifest_payload, sort_keys=False),
        encoding="utf-8",
    )
    return manifest_path


def _record_fixture_stimulus_bundle(
    *,
    manifest_path: Path,
    processed_stimulus_dir: Path,
    schema_path: Path,
    design_lock_path: Path,
) -> None:
    resolved_input = resolve_stimulus_input(
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        processed_stimulus_dir=processed_stimulus_dir,
    )
    record_stimulus_bundle(resolved_input)


def _default_root_specs() -> list[dict[str, object]]:
    return [
        {
            "root_id": 101,
            "cell_type": "fixture_101",
            "project_role": "surface_simulated",
            "asset_profile": "surface",
        },
        {
            "root_id": 202,
            "cell_type": "fixture_202",
            "project_role": "surface_simulated",
            "asset_profile": "surface",
        },
    ]


def _normalize_root_specs(
    root_specs: list[dict[str, object]] | None,
) -> list[dict[str, object]]:
    resolved_specs = root_specs or _default_root_specs()
    normalized: list[dict[str, object]] = []
    seen_root_ids: set[int] = set()
    for item in resolved_specs:
        root_id = int(item["root_id"])
        if root_id in seen_root_ids:
            raise ValueError(f"Duplicate root_id in fixture specs: {root_id}")
        seen_root_ids.add(root_id)
        normalized.append(
            {
                "root_id": root_id,
                "cell_type": str(item.get("cell_type", f"fixture_{root_id}")),
                "project_role": str(item.get("project_role", "surface_simulated")),
                "asset_profile": str(item.get("asset_profile", "surface")),
            }
        )
    normalized.sort(key=lambda item: int(item["root_id"]))
    return normalized


def _write_geometry_manifest(
    output_dir: Path,
    *,
    root_specs: list[dict[str, object]] | None = None,
) -> None:
    normalized_root_specs = _normalize_root_specs(root_specs)
    root_ids = [int(item["root_id"]) for item in normalized_root_specs]
    coupling_dir = output_dir / "processed_coupling"
    local_synapse_registry_path = coupling_dir / "synapse_registry.csv"
    local_synapse_registry_path.parent.mkdir(parents=True, exist_ok=True)
    local_synapse_registry_path.write_text(
        "\n".join(
            [
                "synapse_row_id,pre_root_id,post_root_id",
                *[
                    f"fixture-{index},{pre_root_id},{post_root_id}"
                    for index, (pre_root_id, post_root_id) in enumerate(
                        [
                            (pre_root_id, post_root_id)
                            for pre_root_id in root_ids
                            for post_root_id in root_ids
                            if pre_root_id != post_root_id
                        ],
                        start=1,
                    )
                ],
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    coupling_paths_by_root = {
        root_id: build_root_coupling_bundle_paths(
            root_id,
            processed_coupling_dir=coupling_dir,
        )
        for root_id in root_ids
    }
    for root_id, bundle_paths in coupling_paths_by_root.items():
        _write_placeholder_file(bundle_paths.incoming_anchor_map_path)
        _write_placeholder_file(bundle_paths.outgoing_anchor_map_path)
        _write_placeholder_file(bundle_paths.coupling_index_path)

    edge_paths = [
        coupling_dir / "edges" / f"{pre_root_id}__to__{post_root_id}_coupling.npz"
        for pre_root_id in root_ids
        for post_root_id in root_ids
        if pre_root_id != post_root_id
    ]
    for edge_path in edge_paths:
        _write_placeholder_file(edge_path)

    bundle_records = {}
    for spec in normalized_root_specs:
        root_id = int(spec["root_id"])
        asset_profile = str(spec["asset_profile"])
        asset_statuses = _asset_statuses_for_profile(asset_profile)
        bundle_paths = build_geometry_bundle_paths(
            root_id,
            meshes_raw_dir=output_dir / "meshes_raw",
            skeletons_raw_dir=output_dir / "skeletons_raw",
            processed_mesh_dir=output_dir / "processed_meshes",
            processed_graph_dir=output_dir / "processed_graphs",
        )
        if asset_statuses[SIMPLIFIED_MESH_KEY] == ASSET_STATUS_READY:
            _write_placeholder_file(bundle_paths.simplified_mesh_path)
        if asset_statuses[RAW_SKELETON_KEY] == ASSET_STATUS_READY:
            _write_skeleton_fixture(bundle_paths.raw_skeleton_path)
        operator_bundle_metadata = _write_fixture_operator_bundle(
            bundle_paths=bundle_paths,
            root_id=root_id,
            asset_statuses=asset_statuses,
            asset_profile=asset_profile,
        )
        coupling_metadata = build_coupling_bundle_metadata(
            root_id=root_id,
            processed_coupling_dir=coupling_dir,
            local_synapse_registry_status=ASSET_STATUS_READY,
            incoming_anchor_map_status=ASSET_STATUS_READY,
            outgoing_anchor_map_status=ASSET_STATUS_READY,
            coupling_index_status=ASSET_STATUS_READY,
            edge_bundles=[
                build_edge_coupling_bundle_reference(
                    root_id=root_id,
                    pre_root_id=pre_root_id,
                    post_root_id=post_root_id,
                    processed_coupling_dir=coupling_dir,
                    status=ASSET_STATUS_READY,
                )
                for pre_root_id in root_ids
                for post_root_id in root_ids
                if pre_root_id != post_root_id
                and root_id in (pre_root_id, post_root_id)
            ],
        )
        bundle_records[root_id] = build_geometry_manifest_record(
            bundle_paths=bundle_paths,
            asset_statuses=asset_statuses,
            dataset_name="public",
            materialization_version=783,
            meshing_config_snapshot=_meshing_config_snapshot(),
            registry_metadata={
                "cell_type": str(spec["cell_type"]),
                "project_role": str(spec["project_role"]),
            },
            operator_bundle_metadata=operator_bundle_metadata,
            coupling_bundle_metadata=coupling_metadata,
            processed_coupling_dir=coupling_dir,
        )

    write_geometry_manifest(
        manifest_path=output_dir / "asset_manifest.json",
        bundle_records=bundle_records,
        dataset_name="public",
        materialization_version=783,
        meshing_config_snapshot=_meshing_config_snapshot(),
        processed_coupling_dir=coupling_dir,
    )


def _surface_ready_asset_statuses() -> dict[str, str]:
    return _asset_statuses_for_profile("surface")


def _asset_statuses_for_profile(asset_profile: str) -> dict[str, str]:
    normalized_profile = str(asset_profile)
    if normalized_profile == "surface":
        asset_statuses = default_asset_statuses(fetch_skeletons=False)
        asset_statuses.update(
            {
                SIMPLIFIED_MESH_KEY: ASSET_STATUS_READY,
                FINE_OPERATOR_KEY: ASSET_STATUS_READY,
                COARSE_OPERATOR_KEY: ASSET_STATUS_READY,
                TRANSFER_OPERATORS_KEY: ASSET_STATUS_READY,
                OPERATOR_METADATA_KEY: ASSET_STATUS_READY,
            }
        )
        return asset_statuses
    if normalized_profile == "skeleton":
        asset_statuses = default_asset_statuses(fetch_skeletons=True)
        asset_statuses.update(
            {
                RAW_SKELETON_KEY: ASSET_STATUS_READY,
            }
        )
        return asset_statuses
    if normalized_profile == "point":
        return default_asset_statuses(fetch_skeletons=False)
    raise ValueError(f"Unsupported fixture asset_profile {asset_profile!r}.")


def _meshing_config_snapshot() -> dict[str, object]:
    return {
        "fetch_skeletons": False,
        "operator_assembly": {
            "version": "operator_assembly.v1",
            "boundary_condition": {
                "version": "boundary_condition.v1",
                "mode": "closed_surface_zero_flux",
            },
            "anisotropy": {
                "version": "anisotropy.v1",
                "model": "local_tangent_diagonal",
                "default_tensor": [1.2, 0.8],
            },
        },
    }


def _write_fixture_operator_bundle(
    *,
    bundle_paths: object,
    root_id: int,
    asset_statuses: dict[str, str],
    asset_profile: str,
) -> dict[str, object]:
    if asset_profile != "surface":
        return build_operator_bundle_metadata(
            bundle_paths=bundle_paths,
            asset_statuses=asset_statuses,
            meshing_config_snapshot=_meshing_config_snapshot(),
        )

    fine_operator = sp.csr_matrix(
        [
            [1.0, -1.0, 0.0],
            [-1.0, 2.0, -1.0],
            [0.0, -1.0, 1.0],
        ],
        dtype=np.float64,
    )
    write_deterministic_npz(
        {
            "root_id": np.asarray([root_id], dtype=np.int64),
            **{
                f"operator_{key}": value
                for key, value in serialize_sparse_matrix(fine_operator).items()
            },
        },
        bundle_paths.fine_operator_path,
    )
    coarse_operator = sp.csr_matrix(
        [
            [1.0, -1.0],
            [-1.0, 1.0],
        ],
        dtype=np.float64,
    )
    write_deterministic_npz(
        {
            "root_id": np.asarray([root_id], dtype=np.int64),
            **{
                f"operator_{key}": value
                for key, value in serialize_sparse_matrix(coarse_operator).items()
            },
        },
        bundle_paths.coarse_operator_path,
    )
    restriction = sp.csr_matrix(
        [
            [1.0, 0.0, 0.0],
            [0.0, 0.5, 0.5],
        ],
        dtype=np.float64,
    )
    prolongation = sp.csr_matrix(
        [
            [1.0, 0.0],
            [0.0, 1.0],
            [0.0, 1.0],
        ],
        dtype=np.float64,
    )
    write_deterministic_npz(
        {
            "root_id": np.asarray([root_id], dtype=np.int64),
            **{
                f"restriction_{key}": value
                for key, value in serialize_sparse_matrix(restriction).items()
            },
            **{
                f"prolongation_{key}": value
                for key, value in serialize_sparse_matrix(prolongation).items()
            },
            **{
                f"normalized_restriction_{key}": value
                for key, value in serialize_sparse_matrix(restriction).items()
            },
            **{
                f"normalized_prolongation_{key}": value
                for key, value in serialize_sparse_matrix(prolongation).items()
            },
        },
        bundle_paths.transfer_operator_path,
    )
    write_json({"descriptor_version": 1, "root_id": root_id}, bundle_paths.descriptor_sidecar_path)
    write_json({"qa_version": 1, "root_id": root_id}, bundle_paths.qa_sidecar_path)

    operator_bundle_metadata = build_operator_bundle_metadata(
        bundle_paths=bundle_paths,
        asset_statuses=asset_statuses,
        meshing_config_snapshot=_meshing_config_snapshot(),
        realized_operator_metadata={
            "realization_mode": "fixture_mass_normalized_surface_operator",
            "operator_assembly": _meshing_config_snapshot()["operator_assembly"],
            "preferred_discretization_family": "triangle_mesh_cotangent_fem",
            "discretization_family": "triangle_mesh_cotangent_fem",
            "mass_treatment": "lumped_mass",
            "normalization": "mass_normalized",
            "boundary_condition_mode": "closed_surface_zero_flux",
            "anisotropy_model": "local_tangent_diagonal",
            "fallback_policy": {
                "allowed": False,
                "used": False,
                "reason": "",
                "fallback_discretization_family": "triangle_mesh_cotangent_fem",
            },
            "geodesic_neighborhood": {
                "mode": "fixture_patch_neighbors",
            },
            "transfer_restriction_mode": "mass_weighted_patch_average",
            "transfer_prolongation_mode": "constant_on_patch",
            "transfer_preserves_mass_or_area_totals": True,
            "normalized_state_transfer_available": True,
        },
    )
    write_json(operator_bundle_metadata, bundle_paths.operator_metadata_path)
    return operator_bundle_metadata


def _write_skeleton_fixture(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "1 1 0.0 0.0 0.0 1.0 -1",
                "2 3 1.0 0.0 0.0 0.5 1",
                "3 3 2.0 0.0 0.0 0.5 2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_placeholder_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")
