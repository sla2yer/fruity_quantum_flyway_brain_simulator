from __future__ import annotations

import copy
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.baseline_execution import (
    INTACT_TOPOLOGY_CONDITION,
    RETINAL_BUNDLE_INPUT_SOURCE,
    SHUFFLED_TOPOLOGY_CONDITION,
    STABLE_CONTIGUOUS_MEAN_POOL,
    resolve_baseline_execution_plan_from_arm_plan,
)
from flywire_wave.geometry_contract import build_geometry_bundle_paths
from flywire_wave.mesh_pipeline import process_mesh_into_wave_assets
from flywire_wave.retinal_bundle import record_retinal_bundle
from flywire_wave.retinal_contract import (
    build_retinal_bundle_reference,
    load_retinal_bundle_metadata,
)
from flywire_wave.retinal_geometry import resolve_retinal_geometry_spec
from flywire_wave.retinal_sampling import AnalyticVisualFieldSource, project_visual_source
from flywire_wave.simulation_asset_resolution import ROOT_ASSET_RECORD_VERSION
from flywire_wave.simulation_planning import default_baseline_family_configs
from flywire_wave.simulator_result_contract import (
    P1_BASELINE_FAMILY,
    build_simulator_arm_reference,
    build_simulator_determinism,
    build_simulator_manifest_reference,
    build_simulator_readout_definition,
)
from flywire_wave.synapse_mapping import materialize_synapse_anchor_maps


class BaselineExecutionIntegrationTest(unittest.TestCase):
    def test_p1_execution_resolves_canonical_retinal_drive_and_delay_sensitive_recurrence(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            coupling_summary = _materialize_coupling_fixture(tmp_dir)
            retinal_summary = _record_fixture_retinal_bundle(tmp_dir)
            arm_plan = _build_fixture_arm_plan(
                coupling_summary=coupling_summary,
                retinal_metadata_path=Path(retinal_summary["retinal_bundle_metadata_path"]),
                topology_condition=INTACT_TOPOLOGY_CONDITION,
                seed=17,
            )

            resolved = resolve_baseline_execution_plan_from_arm_plan(arm_plan)
            self.assertEqual(resolved.canonical_input_stream.input_kind, RETINAL_BUNDLE_INPUT_SOURCE)
            self.assertEqual(resolved.drive_schedule.strategy, STABLE_CONTIGUOUS_MEAN_POOL)
            self.assertEqual(resolved.coupling_plan.max_delay_steps, 1)
            self.assertEqual(resolved.coupling_plan.topology_condition, INTACT_TOPOLOGY_CONDITION)
            self.assertEqual(
                resolved.run_blueprint.metadata["canonical_input"]["binding_strategy"],
                STABLE_CONTIGUOUS_MEAN_POOL,
            )

            first_run = resolved.build_run()
            first_run.initialize()
            first_step = first_run.step()
            second_step = first_run.step()
            third_step = first_run.step()
            fourth_step = first_run.step()
            result = first_run.finalize()

            np.testing.assert_allclose(first_step.recurrent_input, [0.0, 0.0, 0.0], atol=0.0, rtol=0.0)
            np.testing.assert_allclose(second_step.recurrent_input, [0.0, 0.0, 0.0], atol=0.0, rtol=0.0)
            self.assertGreater(float(np.linalg.norm(third_step.recurrent_input)), 0.0)
            self.assertGreater(float(np.linalg.norm(fourth_step.recurrent_input)), 0.0)

            repeat_result = resolve_baseline_execution_plan_from_arm_plan(arm_plan).run_to_completion()
            np.testing.assert_allclose(result.readout_traces.values, repeat_result.readout_traces.values)
            np.testing.assert_allclose(
                result.final_snapshot.dynamic_state,
                repeat_result.final_snapshot.dynamic_state,
            )

    def test_shuffled_topology_condition_rewires_targets_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            coupling_summary = _materialize_coupling_fixture(tmp_dir)
            retinal_summary = _record_fixture_retinal_bundle(tmp_dir)
            intact_arm = _build_fixture_arm_plan(
                coupling_summary=coupling_summary,
                retinal_metadata_path=Path(retinal_summary["retinal_bundle_metadata_path"]),
                topology_condition=INTACT_TOPOLOGY_CONDITION,
                seed=23,
            )
            shuffled_arm = copy.deepcopy(intact_arm)
            shuffled_arm["topology_condition"] = SHUFFLED_TOPOLOGY_CONDITION
            shuffled_arm["arm_reference"] = build_simulator_arm_reference(
                arm_id="baseline_fixture_shuffled",
                model_mode="baseline",
                baseline_family=P1_BASELINE_FAMILY,
                comparison_tags=["fixture", "shuffled"],
            )

            intact_plan = resolve_baseline_execution_plan_from_arm_plan(intact_arm)
            shuffled_plan = resolve_baseline_execution_plan_from_arm_plan(shuffled_arm)

            self.assertNotEqual(intact_plan.coupling_plan.coupling_hash, shuffled_plan.coupling_plan.coupling_hash)
            self.assertNotEqual(
                _flatten_target_indices(intact_plan),
                _flatten_target_indices(shuffled_plan),
            )
            intact_result = intact_plan.run_to_completion()
            shuffled_result = shuffled_plan.run_to_completion()
            self.assertFalse(
                np.allclose(
                    intact_result.final_snapshot.dynamic_state,
                    shuffled_result.final_snapshot.dynamic_state,
                    atol=0.0,
                    rtol=0.0,
                )
            )

    def test_missing_selected_coupling_bundle_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            coupling_summary = _materialize_coupling_fixture(tmp_dir)
            retinal_summary = _record_fixture_retinal_bundle(tmp_dir)
            arm_plan = _build_fixture_arm_plan(
                coupling_summary=coupling_summary,
                retinal_metadata_path=Path(retinal_summary["retinal_bundle_metadata_path"]),
                topology_condition=INTACT_TOPOLOGY_CONDITION,
                seed=31,
            )

            edge_path = Path(
                arm_plan["circuit_assets"]["selected_root_assets"][0]["asset_record"][
                    "coupling"
                ]["edge_bundle_records"][0]["path"]
            )
            edge_path.unlink()

            with self.assertRaises(ValueError) as ctx:
                resolve_baseline_execution_plan_from_arm_plan(arm_plan)
            self.assertIn("missing the coupling bundle required", str(ctx.exception))

    def test_unusable_input_timing_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            coupling_summary = _materialize_coupling_fixture(tmp_dir)
            retinal_summary = _record_fixture_retinal_bundle(tmp_dir)
            arm_plan = _build_fixture_arm_plan(
                coupling_summary=coupling_summary,
                retinal_metadata_path=Path(retinal_summary["retinal_bundle_metadata_path"]),
                topology_condition=INTACT_TOPOLOGY_CONDITION,
                seed=37,
            )
            arm_plan["runtime"]["timebase"] = {
                "time_origin_ms": 0.0,
                "dt_ms": 2.0,
                "duration_ms": 8.0,
                "sample_count": 4,
            }

            with self.assertRaises(ValueError) as ctx:
                resolve_baseline_execution_plan_from_arm_plan(arm_plan)
            self.assertIn("timing", str(ctx.exception))


def _build_fixture_arm_plan(
    *,
    coupling_summary: dict[str, object],
    retinal_metadata_path: Path,
    topology_condition: str,
    seed: int,
) -> dict[str, object]:
    family_spec = copy.deepcopy(default_baseline_family_configs()[P1_BASELINE_FAMILY])
    family_spec["parameters"]["membrane_time_constant_ms"] = 4.0
    family_spec["parameters"]["synaptic_current_time_constant_ms"] = 2.0
    family_spec["parameters"]["input_gain"] = 1.0
    family_spec["parameters"]["recurrent_gain"] = 1.0
    family_spec["parameters"]["delay_handling"]["max_supported_delay_steps"] = 4

    retinal_metadata = load_retinal_bundle_metadata(retinal_metadata_path)
    retinal_reference = build_retinal_bundle_reference(retinal_metadata)
    root_ids = [101, 202, 303]
    project_roles = {
        101: "surface_simulated",
        202: "skeleton_simulated",
        303: "point_simulated",
    }
    selected_root_assets = []
    for root_id in root_ids:
        bundle_metadata = coupling_summary["bundle_metadata_by_root"][root_id]
        selected_root_assets.append(
            {
                "root_id": root_id,
                "project_role": project_roles[root_id],
                "asset_record": {
                    "version": ROOT_ASSET_RECORD_VERSION,
                    "coupling": {
                        "bundle_metadata": copy.deepcopy(bundle_metadata),
                        "asset_records": {
                            asset_key: {
                                "path": str(Path(bundle_metadata["assets"][asset_key]["path"]).resolve()),
                                "status": str(bundle_metadata["assets"][asset_key]["status"]),
                                "exists": Path(bundle_metadata["assets"][asset_key]["path"]).exists(),
                            }
                            for asset_key in (
                                "local_synapse_registry",
                                "incoming_anchor_map",
                                "outgoing_anchor_map",
                                "coupling_index",
                            )
                        },
                        "edge_bundle_records": [
                            {
                                "pre_root_id": int(edge_bundle["pre_root_id"]),
                                "post_root_id": int(edge_bundle["post_root_id"]),
                                "peer_root_id": int(edge_bundle["peer_root_id"]),
                                "relation_to_root": str(edge_bundle["relation_to_root"]),
                                "path": str(Path(edge_bundle["path"]).resolve()),
                                "status": str(edge_bundle["status"]),
                                "exists": Path(edge_bundle["path"]).exists(),
                                "selected_peer": True,
                            }
                            for edge_bundle in bundle_metadata["edge_bundles"]
                            if int(edge_bundle["peer_root_id"]) in root_ids
                        ],
                    },
                },
            }
        )

    arm_id = "baseline_fixture_intact" if topology_condition == INTACT_TOPOLOGY_CONDITION else "baseline_fixture_shuffled"
    return {
        "manifest_reference": build_simulator_manifest_reference(
            experiment_id="baseline_execution_fixture",
            manifest_id="baseline_execution_fixture",
            manifest_path=ROOT / "manifests" / "examples" / "milestone_1_demo.yaml",
            milestone="milestone_9",
        ),
        "arm_reference": build_simulator_arm_reference(
            arm_id=arm_id,
            model_mode="baseline",
            baseline_family=P1_BASELINE_FAMILY,
            comparison_tags=["fixture", topology_condition],
        ),
        "topology_condition": topology_condition,
        "selection": {"selected_root_ids": root_ids},
        "input_reference": {
            "selected_input_kind": RETINAL_BUNDLE_INPUT_SOURCE,
            "selected_input_reference": retinal_reference,
            "selected_input_metadata_path": str(retinal_metadata_path.resolve()),
            "selected_input_metadata_exists": True,
            "resolution_source": "recorded_local_bundle",
        },
        "circuit_assets": {
            "local_synapse_registry_path": coupling_summary["synapse_registry_path"],
            "selected_root_assets": selected_root_assets,
            "circuit_asset_hash": "fixture_circuit_hash",
        },
        "runtime": {
            "config_version": "simulation_runtime.v1",
            "time_unit": "ms",
            "timebase": {
                "time_origin_ms": 0.0,
                "dt_ms": 1.0,
                "duration_ms": 4.0,
                "sample_count": 4,
            },
            "readout_catalog": [
                build_simulator_readout_definition(
                    readout_id="shared_output_mean",
                    scope="circuit_output",
                    aggregation="mean_over_root_ids",
                    units="activation_au",
                    value_semantics="shared_downstream_activation",
                )
            ],
        },
        "determinism": build_simulator_determinism(seed=seed),
        "model_configuration": {
            "model_mode": "baseline",
            "baseline_family": P1_BASELINE_FAMILY,
            "baseline_parameters": family_spec,
        },
    }


def _materialize_coupling_fixture(tmp_dir: Path) -> dict[str, object]:
    coupling_dir = tmp_dir / "processed_coupling"

    bundle_paths_101 = build_geometry_bundle_paths(
        101,
        meshes_raw_dir=tmp_dir / "meshes_raw",
        skeletons_raw_dir=tmp_dir / "skeletons_raw",
        processed_mesh_dir=tmp_dir / "processed_meshes",
        processed_graph_dir=tmp_dir / "processed_graphs",
    )
    _write_octahedron_mesh(bundle_paths_101.raw_mesh_path)
    process_mesh_into_wave_assets(
        root_id=101,
        bundle_paths=bundle_paths_101,
        simplify_target_faces=8,
        patch_hops=1,
        patch_vertex_cap=2,
        registry_metadata={"cell_type": "T5a", "project_role": "surface_simulated"},
    )

    bundle_paths_202 = build_geometry_bundle_paths(
        202,
        meshes_raw_dir=tmp_dir / "meshes_raw",
        skeletons_raw_dir=tmp_dir / "skeletons_raw",
        processed_mesh_dir=tmp_dir / "processed_meshes",
        processed_graph_dir=tmp_dir / "processed_graphs",
    )
    _write_stub_swc(bundle_paths_202.raw_skeleton_path)

    synapse_registry_path = coupling_dir / "synapse_registry.csv"
    _write_synapse_registry(synapse_registry_path)

    neuron_registry = pd.DataFrame(
        {
            "root_id": [101, 202, 303],
            "project_role": ["surface_simulated", "skeleton_simulated", "point_simulated"],
        }
    )
    return materialize_synapse_anchor_maps(
        root_ids=[101, 202, 303],
        processed_coupling_dir=coupling_dir,
        meshes_raw_dir=tmp_dir / "meshes_raw",
        skeletons_raw_dir=tmp_dir / "skeletons_raw",
        processed_mesh_dir=tmp_dir / "processed_meshes",
        processed_graph_dir=tmp_dir / "processed_graphs",
        neuron_registry=neuron_registry,
        synapse_registry_path=synapse_registry_path,
        coupling_assembly={
            "delay_model": {
                "mode": "constant_zero_ms",
                "base_delay_ms": 1.0,
                "velocity_distance_units_per_ms": 1.0,
                "delay_bin_size_ms": 0.0,
            }
        },
    )


def _record_fixture_retinal_bundle(tmp_dir: Path) -> dict[str, object]:
    retinal_geometry = resolve_retinal_geometry_spec(
        {
            "retinal_geometry": {
                "geometry_name": "fixture",
                "lattice": {
                    "ring_count": 1,
                },
                "eyes": {
                    "left": {
                        "optical_axis_head": [1.0, 0.0, 0.0],
                        "torsion_deg": 0.0,
                    },
                    "symmetry": {
                        "mode": "mirror_across_head_sagittal_plane",
                    },
                },
            }
        }
    )
    source = AnalyticVisualFieldSource(
        source_family="fixture_scene",
        source_name="temporal_steps",
        width_deg=240.0,
        height_deg=180.0,
        source_metadata={"scene_rule": "piecewise_constant_over_time"},
        field_sampler=_fixture_field_sampler,
    )
    projection = project_visual_source(
        retinal_geometry=retinal_geometry,
        visual_source=source,
        frame_times_ms=[0.0, 1.0, 2.0, 3.0],
        sampling_kernel={
            "acceptance_angle_deg": 1.5,
            "support_radius_deg": 3.0,
            "background_fill_value": 0.5,
        },
    )
    return record_retinal_bundle(
        projection_result=projection,
        processed_retinal_dir=tmp_dir / "retinal",
    )


def _fixture_field_sampler(
    time_ms: float,
    azimuth_deg: object,
    elevation_deg: object,
) -> float:
    del azimuth_deg, elevation_deg
    if time_ms < 1.0:
        return 0.75
    if time_ms < 2.0:
        return 0.25
    if time_ms < 3.0:
        return 0.50
    return 0.90


def _flatten_target_indices(plan) -> list[int]:
    targets: list[int] = []
    for delay_group in plan.coupling_plan.delay_groups:
        targets.extend(int(value) for value in delay_group.target_indices.tolist())
    return targets


def _write_synapse_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "synapse_row_id": "fixture.csv#1",
                "source_row_number": 1,
                "synapse_id": "edge-a",
                "pre_root_id": 202,
                "post_root_id": 101,
                "x": 0.0,
                "y": 0.5,
                "z": 0.5,
                "pre_x": 0.0,
                "pre_y": 1.0,
                "pre_z": 0.0,
                "post_x": 0.0,
                "post_y": 0.0,
                "post_z": 1.0,
                "neuropil": "LOP_R",
                "nt_type": "ACH",
                "sign": "excitatory",
                "confidence": 0.99,
                "weight": 1.0,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
            {
                "synapse_row_id": "fixture.csv#2",
                "source_row_number": 2,
                "synapse_id": "edge-b",
                "pre_root_id": 202,
                "post_root_id": 101,
                "x": np.nan,
                "y": np.nan,
                "z": np.nan,
                "pre_x": np.nan,
                "pre_y": np.nan,
                "pre_z": np.nan,
                "post_x": 1.0,
                "post_y": 0.0,
                "post_z": 0.0,
                "neuropil": "LOP_R",
                "nt_type": "ACH",
                "sign": "excitatory",
                "confidence": 0.75,
                "weight": 0.5,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
            {
                "synapse_row_id": "fixture.csv#3",
                "source_row_number": 3,
                "synapse_id": "edge-c",
                "pre_root_id": 101,
                "post_root_id": 303,
                "x": 5.0,
                "y": 5.0,
                "z": 5.0,
                "pre_x": 1.0,
                "pre_y": 0.0,
                "pre_z": 0.0,
                "post_x": np.nan,
                "post_y": np.nan,
                "post_z": np.nan,
                "neuropil": "ME_R",
                "nt_type": "GABA",
                "sign": "inhibitory",
                "confidence": 0.88,
                "weight": -1.0,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
        ]
    ).to_csv(path, index=False)


def _write_octahedron_mesh(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """
            ply
            format ascii 1.0
            element vertex 6
            property float x
            property float y
            property float z
            element face 8
            property list uchar int vertex_indices
            end_header
            0 0 1
            1 0 0
            0 1 0
            -1 0 0
            0 -1 0
            0 0 -1
            3 0 1 2
            3 0 2 3
            3 0 3 4
            3 0 4 1
            3 5 2 1
            3 5 3 2
            3 5 4 3
            3 5 1 4
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_stub_swc(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# stub skeleton",
                "1 1 0 0 1 1 -1",
                "2 3 1 0 0 1 1",
                "3 3 0 1 0 1 1",
                "4 3 0 0 -1 1 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
