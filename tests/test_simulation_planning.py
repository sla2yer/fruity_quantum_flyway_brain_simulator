from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.coupling_contract import (
    ASSET_STATUS_READY,
    build_coupling_bundle_metadata,
    build_edge_coupling_bundle_reference,
    build_root_coupling_bundle_paths,
)
from flywire_wave.geometry_contract import (
    build_geometry_bundle_paths,
    build_geometry_manifest_record,
    default_asset_statuses,
    write_geometry_manifest,
)
from flywire_wave.simulation_planning import (
    discover_simulation_run_plans,
    resolve_manifest_simulation_plan,
)
from flywire_wave.stimulus_bundle import record_stimulus_bundle, resolve_stimulus_input


class SimulationPlanningTest(unittest.TestCase):
    def test_manifest_plan_resolution_is_deterministic_and_discovers_seed_runs(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            manifest_path = ROOT / "manifests" / "examples" / "milestone_1_demo.yaml"
            schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
            design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"
            config_path = _write_simulation_fixture(tmp_dir)

            resolved_input = resolve_stimulus_input(
                manifest_path=manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
                processed_stimulus_dir=tmp_dir / "out" / "stimuli",
            )
            record_stimulus_bundle(resolved_input)

            first_plan = resolve_manifest_simulation_plan(
                manifest_path=manifest_path,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )
            second_plan = resolve_manifest_simulation_plan(
                manifest_path=manifest_path,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )

            self.assertEqual(first_plan, second_plan)
            self.assertEqual(
                first_plan["arm_order"],
                [
                    "baseline_p0_intact",
                    "surface_wave_intact",
                    "baseline_p0_shuffled",
                    "surface_wave_shuffled",
                    "baseline_p1_intact",
                    "baseline_p1_shuffled",
                ],
            )
            baseline_plan = first_plan["arm_plans"][0]
            self.assertEqual(baseline_plan["arm_reference"]["arm_id"], "baseline_p0_intact")
            self.assertEqual(baseline_plan["selection"]["selected_root_ids"], [101, 202])
            self.assertEqual(baseline_plan["input_reference"]["selected_input_kind"], "stimulus_bundle")
            self.assertTrue(baseline_plan["input_reference"]["selected_input_metadata_exists"])
            self.assertEqual(
                baseline_plan["input_reference"]["resolution_source"],
                "recorded_local_bundle",
            )
            self.assertEqual(
                baseline_plan["runtime"]["readout_catalog"][0]["readout_id"],
                "direction_selectivity_index",
            )
            self.assertEqual(
                baseline_plan["runtime"]["readout_catalog"][1]["readout_id"],
                "shared_output_mean",
            )
            self.assertEqual(
                baseline_plan["model_configuration"]["baseline_parameters"]["parameters"][
                    "membrane_time_constant_ms"
                ],
                12.5,
            )
            self.assertEqual(
                baseline_plan["runtime"]["timebase"]["dt_ms"],
                baseline_plan["resolved_stimulus"]["temporal_sampling"]["dt_ms"],
            )
            self.assertEqual(
                baseline_plan["runtime"]["timebase"]["duration_ms"],
                baseline_plan["resolved_stimulus"]["temporal_sampling"]["duration_ms"],
            )
            self.assertEqual(
                baseline_plan["selection"]["subset_manifest_reference"]["root_id_count"],
                2,
            )
            self.assertEqual(
                baseline_plan["seed_handling"]["seed_sweep"],
                [11, 17, 23],
            )
            self.assertEqual(
                len(baseline_plan["circuit_assets"]["circuit_asset_hash"]),
                64,
            )

            baseline_runs = discover_simulation_run_plans(
                first_plan,
                model_mode="baseline",
            )
            self.assertEqual(
                [item["arm_reference"]["arm_id"] for item in baseline_runs],
                [
                    "baseline_p0_intact",
                    "baseline_p0_shuffled",
                    "baseline_p1_intact",
                    "baseline_p1_shuffled",
                ],
            )

            seeded_runs = discover_simulation_run_plans(
                first_plan,
                arm_id="baseline_p0_intact",
                use_manifest_seed_sweep=True,
            )
            self.assertEqual(
                [item["seed_handling"]["default_seed"] for item in seeded_runs],
                [11, 17, 23],
            )
            self.assertEqual(
                len(
                    {
                        item["result_bundle"]["reference"]["run_spec_hash"]
                        for item in seeded_runs
                    }
                ),
                3,
            )

    def test_missing_coupling_asset_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            manifest_path = ROOT / "manifests" / "examples" / "milestone_1_demo.yaml"
            schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
            design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"
            config_path = _write_simulation_fixture(tmp_dir)

            resolved_input = resolve_stimulus_input(
                manifest_path=manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
                processed_stimulus_dir=tmp_dir / "out" / "stimuli",
            )
            record_stimulus_bundle(resolved_input)

            missing_asset = (
                tmp_dir
                / "out"
                / "processed_coupling"
                / "roots"
                / "101_incoming_anchor_map.npz"
            )
            missing_asset.unlink()

            with self.assertRaises(ValueError) as ctx:
                resolve_manifest_simulation_plan(
                    manifest_path=manifest_path,
                    config_path=config_path,
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
            self.assertIn("Selected root 101 is missing local coupling assets", str(ctx.exception))


def _write_simulation_fixture(tmp_dir: Path) -> Path:
    output_dir = tmp_dir / "out"
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
        )
        + "\n",
        encoding="utf-8",
    )

    _write_geometry_manifest(output_dir)

    config_path = tmp_dir / "simulation_config.yaml"
    config_path.write_text(
        textwrap.dedent(
            f"""
            paths:
              selected_root_ids: {selected_root_ids_path}
              subset_output_dir: {output_dir / "subsets"}
              manifest_json: {output_dir / "asset_manifest.json"}
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
                  description: Shared direction-selectivity summary for matched comparisons.
              baseline_families:
                P0:
                  membrane_time_constant_ms: 12.5
                  recurrent_gain: 0.9
                P1:
                  membrane_time_constant_ms: 15.0
                  synaptic_current_time_constant_ms: 6.0
                  delay_handling:
                    mode: from_coupling_bundle
                    max_supported_delay_steps: 32
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return config_path


def _write_geometry_manifest(output_dir: Path) -> None:
    coupling_dir = output_dir / "processed_coupling"
    local_synapse_registry_path = coupling_dir / "synapse_registry.csv"
    local_synapse_registry_path.parent.mkdir(parents=True, exist_ok=True)
    local_synapse_registry_path.write_text(
        "synapse_row_id,pre_root_id,post_root_id\nfixture-1,101,202\nfixture-2,202,101\n",
        encoding="utf-8",
    )

    coupling_paths_by_root = {
        root_id: build_root_coupling_bundle_paths(
            root_id,
            processed_coupling_dir=coupling_dir,
        )
        for root_id in [101, 202]
    }
    for root_id, bundle_paths in coupling_paths_by_root.items():
        _write_placeholder_file(bundle_paths.incoming_anchor_map_path)
        _write_placeholder_file(bundle_paths.outgoing_anchor_map_path)
        _write_placeholder_file(bundle_paths.coupling_index_path)

    edge_paths = [
        coupling_dir / "edges" / "101__to__202_coupling.npz",
        coupling_dir / "edges" / "202__to__101_coupling.npz",
    ]
    for edge_path in edge_paths:
        _write_placeholder_file(edge_path)

    bundle_records = {}
    for root_id in [101, 202]:
        bundle_paths = build_geometry_bundle_paths(
            root_id,
            meshes_raw_dir=output_dir / "meshes_raw",
            skeletons_raw_dir=output_dir / "skeletons_raw",
            processed_mesh_dir=output_dir / "processed_meshes",
            processed_graph_dir=output_dir / "processed_graphs",
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
                    pre_root_id=101,
                    post_root_id=202,
                    processed_coupling_dir=coupling_dir,
                    status=ASSET_STATUS_READY,
                ),
                build_edge_coupling_bundle_reference(
                    root_id=root_id,
                    pre_root_id=202,
                    post_root_id=101,
                    processed_coupling_dir=coupling_dir,
                    status=ASSET_STATUS_READY,
                ),
            ],
        )
        bundle_records[root_id] = build_geometry_manifest_record(
            bundle_paths=bundle_paths,
            asset_statuses=default_asset_statuses(fetch_skeletons=False),
            dataset_name="public",
            materialization_version=783,
            meshing_config_snapshot={"fetch_skeletons": False},
            registry_metadata={
                "cell_type": f"fixture_{root_id}",
                "project_role": "surface_simulated" if root_id == 101 else "point_simulated",
            },
            coupling_bundle_metadata=coupling_metadata,
            processed_coupling_dir=coupling_dir,
        )

    write_geometry_manifest(
        manifest_path=output_dir / "asset_manifest.json",
        bundle_records=bundle_records,
        dataset_name="public",
        materialization_version=783,
        meshing_config_snapshot={"fetch_skeletons": False},
        processed_coupling_dir=coupling_dir,
    )


def _write_placeholder_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")


if __name__ == "__main__":
    unittest.main()
