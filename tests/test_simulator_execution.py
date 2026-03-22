from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.geometry_contract import (
    COARSE_OPERATOR_KEY,
    FINE_OPERATOR_KEY,
    OPERATOR_METADATA_KEY,
    SIMPLIFIED_MESH_KEY,
    TRANSFER_OPERATORS_KEY,
    build_geometry_bundle_paths,
    build_geometry_manifest_record,
    default_asset_statuses,
    load_operator_bundle_metadata,
    write_geometry_manifest,
)
from flywire_wave.hybrid_morphology_contract import (
    HYBRID_MORPHOLOGY_CONTRACT_VERSION,
    SURFACE_NEURON_CLASS,
)
from flywire_wave.hybrid_morphology_runtime import (
    MORPHOLOGY_CLASS_RUNTIME_INTERFACE_VERSION,
)
from flywire_wave.manifests import load_json
from flywire_wave.mesh_pipeline import process_mesh_into_wave_assets
from flywire_wave.simulation_planning import resolve_manifest_simulation_plan
from flywire_wave.simulator_result_contract import (
    METRICS_TABLE_KEY,
    READOUT_TRACES_KEY,
    STATE_SUMMARY_KEY,
    discover_simulator_extension_artifacts,
    discover_simulator_root_morphology_metadata,
    discover_simulator_result_bundle_paths,
    load_simulator_root_state_payload,
    load_simulator_result_bundle_metadata,
    load_simulator_shared_readout_payload,
)
from flywire_wave.simulator_execution import execute_manifest_simulation
from flywire_wave.stimulus_bundle import record_stimulus_bundle, resolve_stimulus_input
from flywire_wave.synapse_mapping import materialize_synapse_anchor_maps
from test_simulation_planning import (
    _write_manifest_fixture,
    _write_simulation_fixture,
)


class SimulatorExecutionSmokeTest(unittest.TestCase):
    def test_cli_executes_baseline_manifest_arm_and_writes_deterministic_bundle(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_execution_fixture(Path(tmp_dir_str))
            command = [
                sys.executable,
                str(ROOT / "scripts" / "run_simulation.py"),
                "--config",
                str(fixture["config_path"]),
                "--manifest",
                str(fixture["manifest_path"]),
                "--schema",
                str(fixture["schema_path"]),
                "--design-lock",
                str(fixture["design_lock_path"]),
                "--model-mode",
                "baseline",
                "--arm-id",
                "baseline_p0_intact",
            ]
            first = subprocess.run(
                command,
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            first_summary = json.loads(first.stdout)
            self.assertEqual(first_summary["executed_run_count"], 1)

            run_summary = first_summary["executed_runs"][0]
            metadata_path = Path(run_summary["metadata_path"])
            metadata = load_simulator_result_bundle_metadata(metadata_path)
            discovered_paths = discover_simulator_result_bundle_paths(metadata)
            discovered_extensions = discover_simulator_extension_artifacts(metadata)
            extension_paths = {
                item["artifact_id"]: Path(item["path"])
                for item in discovered_extensions
            }
            ui_payload_path = extension_paths["ui_comparison_payload"]
            structured_log_path = extension_paths["structured_log"]
            provenance_path = extension_paths["execution_provenance"]

            self.assertEqual(metadata["arm_reference"]["arm_id"], "baseline_p0_intact")
            self.assertEqual(metadata["arm_reference"]["model_mode"], "baseline")
            self.assertEqual(metadata["arm_reference"]["baseline_family"], "P0")
            self.assertEqual(
                [item["readout_id"] for item in metadata["readout_catalog"]],
                ["shared_output_mean"],
            )

            with Path(discovered_paths[STATE_SUMMARY_KEY]).open("r", encoding="utf-8") as handle:
                state_summary_rows = json.load(handle)
            self.assertIsInstance(state_summary_rows, list)
            self.assertTrue(any(row["state_id"] == "circuit_membrane_state" for row in state_summary_rows))

            metrics_table = Path(discovered_paths[METRICS_TABLE_KEY]).read_text(encoding="utf-8")
            self.assertIn("metric_id,readout_id,scope,window_id,statistic,value,units", metrics_table)
            self.assertIn("shared_output_mean", metrics_table)
            self.assertIn("final_endpoint_value", metrics_table)

            ui_payload = load_json(ui_payload_path)
            self.assertEqual(
                ui_payload["format_version"],
                "json_simulator_ui_comparison_payload.v1",
            )
            self.assertEqual(
                ui_payload["trace_payload"]["path"],
                str(discovered_paths[READOUT_TRACES_KEY]),
            )
            self.assertEqual(
                [item["readout_id"] for item in ui_payload["readout_summaries"]],
                ["shared_output_mean"],
            )
            self.assertEqual(
                ui_payload["declared_output_targets"]["metrics_json"],
                str(fixture["metrics_json_path"]),
            )
            self.assertTrue(
                any(item["output_id"] == "surface_vs_baseline_split_view" for item in ui_payload["declared_output_targets"]["views"])
            )

            provenance_payload = load_json(provenance_path)
            self.assertEqual(
                provenance_payload["workflow_version"],
                "simulator_manifest_execution.v1",
            )
            self.assertEqual(
                provenance_payload["artifact_counts"]["metric_row_count"],
                run_summary["metric_row_count"],
            )
            self.assertGreater(run_summary["structured_log_event_count"], 0)
            self.assertIn('"event_type":"initialized"', structured_log_path.read_text(encoding="utf-8"))

            compared_files = [
                metadata_path,
                Path(run_summary["state_summary_path"]),
                Path(run_summary["readout_traces_path"]),
                Path(run_summary["metrics_table_path"]),
                structured_log_path,
                provenance_path,
                ui_payload_path,
            ]
            first_run_bytes = {
                str(path): path.read_bytes()
                for path in compared_files
            }

            second = subprocess.run(
                command,
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            second_summary = json.loads(second.stdout)
            self.assertEqual(first_summary, second_summary)
            for path in compared_files:
                self.assertEqual(path.read_bytes(), first_run_bytes[str(path)])

            plan = resolve_manifest_simulation_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )
            planned_bundle_id = (
                plan["arm_plans"][0]["result_bundle"]["reference"]["bundle_id"]
            )
            self.assertEqual(planned_bundle_id, metadata["bundle_id"])

    def test_cli_executes_surface_wave_manifest_arm_and_writes_wave_extensions(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_execution_fixture(Path(tmp_dir_str))
            command = [
                sys.executable,
                str(ROOT / "scripts" / "run_simulation.py"),
                "--config",
                str(fixture["config_path"]),
                "--manifest",
                str(fixture["manifest_path"]),
                "--schema",
                str(fixture["schema_path"]),
                "--design-lock",
                str(fixture["design_lock_path"]),
                "--model-mode",
                "surface_wave",
                "--arm-id",
                "surface_wave_intact",
            ]
            first = subprocess.run(
                command,
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            first_summary = json.loads(first.stdout)
            self.assertEqual(first_summary["executed_run_count"], 1)

            run_summary = first_summary["executed_runs"][0]
            metadata_path = Path(run_summary["metadata_path"])
            metadata = load_simulator_result_bundle_metadata(metadata_path)
            discovered_paths = discover_simulator_result_bundle_paths(metadata)
            discovered_extensions = discover_simulator_extension_artifacts(metadata)
            extension_records = {
                item["artifact_id"]: item
                for item in discovered_extensions
            }
            extension_paths = {
                artifact_id: Path(record["path"])
                for artifact_id, record in extension_records.items()
            }

            self.assertEqual(metadata["arm_reference"]["arm_id"], "surface_wave_intact")
            self.assertEqual(metadata["arm_reference"]["model_mode"], "surface_wave")
            self.assertIsNone(metadata["arm_reference"]["baseline_family"])
            self.assertEqual(
                [item["readout_id"] for item in metadata["readout_catalog"]],
                ["shared_output_mean"],
            )
            self.assertEqual(
                extension_records["surface_wave_summary"]["artifact_scope"],
                "wave_model_extension",
            )
            self.assertEqual(
                extension_records["surface_wave_patch_traces"]["format"],
                "npz_surface_wave_patch_traces.v1",
            )
            self.assertEqual(
                extension_records["surface_wave_coupling_events"]["artifact_scope"],
                "wave_model_extension",
            )

            with Path(discovered_paths[STATE_SUMMARY_KEY]).open("r", encoding="utf-8") as handle:
                state_summary_rows = json.load(handle)
            self.assertTrue(
                any(row["state_id"] == "circuit_surface_activation_state" for row in state_summary_rows)
            )
            self.assertTrue(
                any(row["state_id"] == "root_101_patch_activation_state" for row in state_summary_rows)
            )

            ui_payload = load_json(extension_paths["ui_comparison_payload"])
            self.assertEqual(
                ui_payload["format_version"],
                "json_simulator_ui_comparison_payload.v1",
            )
            self.assertEqual(
                ui_payload["trace_payload"]["path"],
                str(discovered_paths[READOUT_TRACES_KEY]),
            )
            self.assertTrue(
                {"surface_wave_summary", "surface_wave_patch_traces", "surface_wave_coupling_events"}
                <= {item["artifact_id"] for item in ui_payload["artifact_inventory"]}
            )

            wave_summary = load_json(extension_paths["surface_wave_summary"])
            self.assertEqual(
                wave_summary["format_version"],
                "json_surface_wave_execution_summary.v1",
            )
            self.assertEqual(
                wave_summary["hybrid_morphology"]["contract_version"],
                HYBRID_MORPHOLOGY_CONTRACT_VERSION,
            )
            self.assertEqual(
                wave_summary["hybrid_morphology"]["discovered_morphology_classes"],
                [SURFACE_NEURON_CLASS],
            )
            self.assertEqual(
                wave_summary["morphology_runtime"]["interface_version"],
                MORPHOLOGY_CLASS_RUNTIME_INTERFACE_VERSION,
            )
            self.assertEqual(
                wave_summary["input_binding"]["injection_strategy"],
                "uniform_surface_fill_from_shared_root_schedule",
            )
            self.assertEqual(
                wave_summary["wave_specific_artifacts"]["patch_traces_artifact_id"],
                "surface_wave_patch_traces",
            )

            provenance_payload = load_json(extension_paths["execution_provenance"])
            self.assertEqual(
                provenance_payload["model_execution"]["hybrid_morphology"]["contract_version"],
                HYBRID_MORPHOLOGY_CONTRACT_VERSION,
            )
            self.assertEqual(
                provenance_payload["model_execution"]["hybrid_morphology"][
                    "discovered_morphology_classes"
                ],
                [SURFACE_NEURON_CLASS],
            )
            self.assertEqual(
                provenance_payload["model_execution"]["morphology_runtime"][
                    "interface_version"
                ],
                MORPHOLOGY_CLASS_RUNTIME_INTERFACE_VERSION,
            )

            coupling_payload = load_json(extension_paths["surface_wave_coupling_events"])
            self.assertEqual(
                coupling_payload["format_version"],
                "json_surface_wave_coupling_events.v1",
            )
            self.assertGreaterEqual(coupling_payload["event_count"], 0)

            with np.load(extension_paths["surface_wave_patch_traces"], allow_pickle=False) as patch_traces:
                self.assertIn("substep_time_ms", patch_traces.files)
                self.assertIn("root_101_patch_activation", patch_traces.files)
                self.assertIn("root_202_patch_activation", patch_traces.files)
                self.assertGreater(patch_traces["root_101_patch_activation"].shape[0], 1)

            compared_files = [
                metadata_path,
                Path(run_summary["state_summary_path"]),
                Path(run_summary["readout_traces_path"]),
                Path(run_summary["metrics_table_path"]),
                extension_paths["structured_log"],
                extension_paths["execution_provenance"],
                extension_paths["ui_comparison_payload"],
                extension_paths["surface_wave_summary"],
                extension_paths["surface_wave_patch_traces"],
                extension_paths["surface_wave_coupling_events"],
            ]
            first_run_bytes = {
                str(path): path.read_bytes()
                for path in compared_files
            }

            second = subprocess.run(
                command,
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            second_summary = json.loads(second.stdout)
            self.assertEqual(first_summary, second_summary)
            for path in compared_files:
                self.assertEqual(path.read_bytes(), first_run_bytes[str(path)])

            plan = resolve_manifest_simulation_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )
            planned_bundle_id = next(
                arm_plan["result_bundle"]["reference"]["bundle_id"]
                for arm_plan in plan["arm_plans"]
                if arm_plan["arm_reference"]["arm_id"] == "surface_wave_intact"
            )
            self.assertEqual(planned_bundle_id, metadata["bundle_id"])

    def test_execute_manifest_simulation_writes_deterministic_mixed_morphology_bundle(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            manifest_path = _write_manifest_fixture(
                tmp_dir,
                surface_wave_fidelity_assignment={
                    "default_morphology_class": "point_neuron",
                    "root_overrides": [
                        {"root_id": 101, "morphology_class": "surface_neuron"},
                        {"root_id": 202, "morphology_class": "skeleton_neuron"},
                    ],
                },
            )
            config_path = _write_simulation_fixture(
                tmp_dir,
                root_specs=[
                    {
                        "root_id": 101,
                        "project_role": "surface_simulated",
                        "asset_profile": "surface",
                    },
                    {
                        "root_id": 202,
                        "project_role": "skeleton_simulated",
                        "asset_profile": "skeleton",
                    },
                    {
                        "root_id": 303,
                        "project_role": "point_simulated",
                        "asset_profile": "point",
                    },
                ],
            )
            _rewrite_skeleton_compatible_surface_wave_config(config_path)
            schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
            design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"
            resolved_input = resolve_stimulus_input(
                manifest_path=manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
                processed_stimulus_dir=tmp_dir / "out" / "stimuli",
            )
            record_stimulus_bundle(resolved_input)
            _remove_selected_edges_for_roots(
                tmp_dir / "out" / "asset_manifest.json",
                root_ids=[202, 303],
            )

            first = execute_manifest_simulation(
                manifest_path=manifest_path,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
                model_mode="surface_wave",
                arm_id="surface_wave_intact",
            )
            second = execute_manifest_simulation(
                manifest_path=manifest_path,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
                model_mode="surface_wave",
                arm_id="surface_wave_intact",
            )

            self.assertEqual(first, second)
            self.assertEqual(first["executed_run_count"], 1)

            first_run_summary = first["executed_runs"][0]
            metadata_path = Path(first_run_summary["metadata_path"])
            metadata = load_simulator_result_bundle_metadata(metadata_path)
            discovered_paths = discover_simulator_result_bundle_paths(metadata)
            discovered_extensions = discover_simulator_extension_artifacts(metadata)
            extension_paths = {
                item["artifact_id"]: Path(item["path"]).resolve()
                for item in discovered_extensions
            }
            compared_files = [
                metadata_path,
                Path(first_run_summary["state_summary_path"]),
                Path(first_run_summary["readout_traces_path"]),
                Path(first_run_summary["metrics_table_path"]),
                extension_paths["structured_log"],
                extension_paths["execution_provenance"],
                extension_paths["ui_comparison_payload"],
                extension_paths["surface_wave_summary"],
                extension_paths["surface_wave_patch_traces"],
                extension_paths["mixed_morphology_state_bundle"],
                extension_paths["surface_wave_coupling_events"],
            ]
            first_run_bytes = {str(path): path.read_bytes() for path in compared_files}

            second_run_summary = second["executed_runs"][0]
            second_metadata = load_simulator_result_bundle_metadata(
                Path(second_run_summary["metadata_path"])
            )
            second_discovered_paths = discover_simulator_result_bundle_paths(second_metadata)
            second_root_metadata = discover_simulator_root_morphology_metadata(second_metadata)
            shared_readout_payload = load_simulator_shared_readout_payload(second_metadata)
            point_state_payload = load_simulator_root_state_payload(second_metadata, root_id=303)

            self.assertEqual(
                [item["morphology_class"] for item in second_root_metadata],
                ["surface_neuron", "skeleton_neuron", "point_neuron"],
            )
            self.assertEqual(
                point_state_payload["morphology_class"],
                "point_neuron",
            )
            self.assertEqual(
                point_state_payload["runtime_metadata"]["baseline_family"],
                "P0",
            )
            self.assertEqual(
                point_state_payload["state_summary_rows"][0]["state_id"],
                "root_303_point_activation_state",
            )
            self.assertEqual(
                tuple(shared_readout_payload["readout_ids"]),
                ("shared_output_mean",),
            )
            self.assertEqual(
                point_state_payload["projection_trace"].shape[1],
                1,
            )
            self.assertIn("mixed_morphology_state_bundle", extension_paths)
            self.assertIn("surface_wave_patch_traces", extension_paths)
            self.assertTrue(
                any(
                    row["state_id"] == "root_303_point_activation_state"
                    for row in json.loads(
                        Path(second_discovered_paths[STATE_SUMMARY_KEY]).read_text(
                            encoding="utf-8"
                        )
                    )
                )
            )
            for path in compared_files:
                self.assertEqual(path.read_bytes(), first_run_bytes[str(path)])


def _materialize_execution_fixture(tmp_dir: Path) -> dict[str, Path]:
    output_dir = tmp_dir / "out"
    manifest_path = ROOT / "manifests" / "examples" / "milestone_1_demo.yaml"
    schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
    design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"

    stimulus = resolve_stimulus_input(
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        processed_stimulus_dir=output_dir / "stimuli",
    )
    record_stimulus_bundle(stimulus)

    selected_root_ids_path = output_dir / "selected_root_ids.txt"
    selected_root_ids_path.parent.mkdir(parents=True, exist_ok=True)
    selected_root_ids_path.write_text("101\n202\n", encoding="utf-8")

    subset_manifest_path = output_dir / "subsets" / "motion_minimal" / "subset_manifest.json"
    subset_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    subset_manifest_path.write_text(
        json.dumps(
            {
                "subset_manifest_version": "1",
                "preset_name": "motion_minimal",
                "root_ids": [101, 202],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    geometry_manifest_path = output_dir / "asset_manifest.json"
    _write_execution_geometry_manifest(output_dir, geometry_manifest_path)

    metrics_json_path = (ROOT / "outputs" / "milestone_1" / "milestone_1_demo_motion_patch" / "metrics" / "summary_metrics.json").resolve()
    config_path = tmp_dir / "simulation_config.yaml"
    config_path.write_text(
        textwrap.dedent(
            f"""
            paths:
              selected_root_ids: {selected_root_ids_path}
              subset_output_dir: {output_dir / "subsets"}
              manifest_json: {geometry_manifest_path}
              processed_stimulus_dir: {output_dir / "stimuli"}
              processed_retinal_dir: {output_dir / "retinal"}
              processed_simulator_results_dir: {output_dir / "simulator_results"}
            selection:
              active_preset: motion_minimal
            simulation:
              input:
                source_kind: stimulus_bundle
                require_recorded_bundle: true
              readout_catalog:
                - readout_id: shared_output_mean
                  scope: circuit_output
                  aggregation: mean_over_root_ids
                  units: activation_au
                  value_semantics: shared_downstream_activation
                  description: Shared downstream output mean for matched comparisons.
                - readout_id: direction_selectivity_index
                  scope: comparison_panel
                  aggregation: identity
                  units: unitless
                  value_semantics: direction_selectivity_index
                  description: Derived comparison summary routed through metric tables and UI payloads.
              baseline_families:
                P0:
                  membrane_time_constant_ms: 12.5
                  recurrent_gain: 0.9
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return {
        "config_path": config_path.resolve(),
        "manifest_path": manifest_path.resolve(),
        "schema_path": schema_path.resolve(),
        "design_lock_path": design_lock_path.resolve(),
        "metrics_json_path": metrics_json_path,
    }


def _write_execution_geometry_manifest(output_dir: Path, manifest_path: Path) -> None:
    meshes_raw_dir = output_dir / "meshes_raw"
    skeletons_raw_dir = output_dir / "skeletons_raw"
    processed_mesh_dir = output_dir / "processed_meshes"
    processed_graph_dir = output_dir / "processed_graphs"
    processed_coupling_dir = output_dir / "processed_coupling"

    bundle_paths_101 = build_geometry_bundle_paths(
        101,
        meshes_raw_dir=meshes_raw_dir,
        skeletons_raw_dir=skeletons_raw_dir,
        processed_mesh_dir=processed_mesh_dir,
        processed_graph_dir=processed_graph_dir,
    )
    _write_octahedron_mesh(bundle_paths_101.raw_mesh_path)
    process_mesh_into_wave_assets(
        root_id=101,
        bundle_paths=bundle_paths_101,
        simplify_target_faces=8,
        patch_hops=1,
        patch_vertex_cap=2,
        registry_metadata={"cell_type": "T4a", "project_role": "surface_simulated"},
    )

    bundle_paths_202 = build_geometry_bundle_paths(
        202,
        meshes_raw_dir=meshes_raw_dir,
        skeletons_raw_dir=skeletons_raw_dir,
        processed_mesh_dir=processed_mesh_dir,
        processed_graph_dir=processed_graph_dir,
    )
    _write_octahedron_mesh(bundle_paths_202.raw_mesh_path)
    process_mesh_into_wave_assets(
        root_id=202,
        bundle_paths=bundle_paths_202,
        simplify_target_faces=8,
        patch_hops=1,
        patch_vertex_cap=2,
        registry_metadata={"cell_type": "T5a", "project_role": "surface_simulated"},
    )

    synapse_registry_path = processed_coupling_dir / "synapse_registry.csv"
    _write_execution_synapse_registry(synapse_registry_path)
    coupling_summary = materialize_synapse_anchor_maps(
        root_ids=[101, 202],
        processed_coupling_dir=processed_coupling_dir,
        meshes_raw_dir=meshes_raw_dir,
        skeletons_raw_dir=skeletons_raw_dir,
        processed_mesh_dir=processed_mesh_dir,
        processed_graph_dir=processed_graph_dir,
        neuron_registry=pd.DataFrame(
            {
                "root_id": [101, 202],
                "project_role": ["surface_simulated", "surface_simulated"],
            }
        ),
        synapse_registry_path=synapse_registry_path,
        coupling_assembly={
            "delay_model": {
                "mode": "constant_zero_ms",
                "base_delay_ms": 0.0,
                "velocity_distance_units_per_ms": 1.0,
                "delay_bin_size_ms": 0.0,
            }
        },
    )

    bundle_records = {
        101: build_geometry_manifest_record(
            bundle_paths=bundle_paths_101,
            asset_statuses=_surface_ready_asset_statuses(),
            dataset_name="flywire_fafb_public",
            materialization_version=783,
            meshing_config_snapshot=_meshing_config_snapshot(),
            registry_metadata={
                "cell_type": "T4a",
                "project_role": "surface_simulated",
                "materialization_version": "783",
                "snapshot_version": "783",
            },
            operator_bundle_metadata=load_operator_bundle_metadata(
                bundle_paths_101.operator_metadata_path
            ),
            processed_coupling_dir=processed_coupling_dir,
            coupling_bundle_metadata=coupling_summary["bundle_metadata_by_root"][101],
        ),
        202: build_geometry_manifest_record(
            bundle_paths=bundle_paths_202,
            asset_statuses=_surface_ready_asset_statuses(),
            dataset_name="flywire_fafb_public",
            materialization_version=783,
            meshing_config_snapshot=_meshing_config_snapshot(),
            registry_metadata={
                "cell_type": "T5a",
                "project_role": "surface_simulated",
                "materialization_version": "783",
                "snapshot_version": "783",
            },
            operator_bundle_metadata=load_operator_bundle_metadata(
                bundle_paths_202.operator_metadata_path
            ),
            processed_coupling_dir=processed_coupling_dir,
            coupling_bundle_metadata=coupling_summary["bundle_metadata_by_root"][202],
        ),
    }
    write_geometry_manifest(
        manifest_path=manifest_path,
        bundle_records=bundle_records,
        dataset_name="flywire_fafb_public",
        materialization_version=783,
        meshing_config_snapshot=_meshing_config_snapshot(),
        processed_coupling_dir=processed_coupling_dir,
    )


def _meshing_config_snapshot() -> dict[str, object]:
    return {
        "operator_assembly": {
            "version": "operator_assembly.v1",
            "boundary_condition": {"mode": "closed_surface_zero_flux"},
            "anisotropy": {"model": "isotropic"},
        }
    }


def _surface_ready_asset_statuses() -> dict[str, str]:
    asset_statuses = default_asset_statuses(fetch_skeletons=False)
    asset_statuses.update(
        {
            SIMPLIFIED_MESH_KEY: "ready",
            FINE_OPERATOR_KEY: "ready",
            COARSE_OPERATOR_KEY: "ready",
            TRANSFER_OPERATORS_KEY: "ready",
            OPERATOR_METADATA_KEY: "ready",
        }
    )
    return asset_statuses


def _write_execution_synapse_registry(path: Path) -> None:
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
                "pre_root_id": 101,
                "post_root_id": 202,
                "x": 1.0,
                "y": 0.0,
                "z": 0.0,
                "pre_x": 0.0,
                "pre_y": 0.0,
                "pre_z": 1.0,
                "post_x": 0.0,
                "post_y": 1.0,
                "post_z": 0.0,
                "neuropil": "ME_R",
                "nt_type": "ACH",
                "sign": "excitatory",
                "confidence": 0.95,
                "weight": 0.5,
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
        "1 1 0 0 0 1 -1\n2 3 0 1 0 1 1\n",
        encoding="utf-8",
    )


def _remove_selected_edges_for_roots(
    manifest_path: Path,
    *,
    root_ids: list[int] | tuple[int, ...],
) -> None:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    normalized_root_ids = {int(root_id) for root_id in root_ids}
    for key, record in payload.items():
        if not isinstance(key, str) or not key.isdigit() or not isinstance(record, dict):
            continue
        coupling_bundle = record.get("coupling_bundle")
        if not isinstance(coupling_bundle, dict):
            continue
        edge_bundles = coupling_bundle.get("edge_bundles")
        if not isinstance(edge_bundles, list):
            continue
        coupling_bundle["edge_bundles"] = [
            edge_bundle
            for edge_bundle in edge_bundles
            if int(edge_bundle.get("pre_root_id", -1)) not in normalized_root_ids
            and int(edge_bundle.get("post_root_id", -1)) not in normalized_root_ids
        ]
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _rewrite_skeleton_compatible_surface_wave_config(config_path: Path) -> None:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    surface_wave = payload["simulation"]["surface_wave"]
    surface_wave.setdefault("recovery", {})["mode"] = "disabled"
    surface_wave.setdefault("nonlinearity", {})["mode"] = "none"
    surface_wave.setdefault("anisotropy", {})["mode"] = "isotropic"
    surface_wave.setdefault("branching", {})["mode"] = "disabled"
    config_path.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
