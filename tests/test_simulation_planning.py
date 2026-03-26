from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import yaml

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
    COARSE_OPERATOR_KEY,
    FINE_OPERATOR_KEY,
    OPERATOR_METADATA_KEY,
    RAW_SKELETON_KEY,
    SIMPLIFIED_MESH_KEY,
    TRANSFER_OPERATORS_KEY,
    build_operator_bundle_metadata,
    build_geometry_bundle_paths,
    build_geometry_manifest_record,
    default_asset_statuses,
    write_geometry_manifest,
)
from flywire_wave.io_utils import write_deterministic_npz, write_json
from flywire_wave.hybrid_morphology_contract import (
    HYBRID_MORPHOLOGY_CONTRACT_VERSION,
    POINT_NEURON_CLASS,
    SKELETON_NEURON_CLASS,
    SURFACE_NEURON_CLASS,
)
from flywire_wave.skeleton_runtime_assets import (
    SKELETON_RUNTIME_ASSET_CONTRACT_VERSION,
    SKELETON_RUNTIME_ASSET_KEY,
)
from flywire_wave.simulation_planning import (
    discover_simulation_run_plans,
    resolve_manifest_mixed_fidelity_plan,
    resolve_manifest_readout_analysis_plan,
    resolve_manifest_simulation_plan,
)
from flywire_wave.stimulus_bundle import record_stimulus_bundle, resolve_stimulus_input
from flywire_wave.surface_wave_contract import (
    DEFAULT_SURFACE_WAVE_MODEL_FAMILY,
    SURFACE_WAVE_MODEL_CONTRACT_VERSION,
)
from flywire_wave.surface_operators import serialize_sparse_matrix


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
                [item["readout_id"] for item in baseline_plan["runtime"]["shared_readout_catalog"]],
                ["shared_output_mean"],
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
            surface_wave_plan = first_plan["arm_plans"][1]
            self.assertEqual(surface_wave_plan["arm_reference"]["arm_id"], "surface_wave_intact")
            self.assertEqual(
                surface_wave_plan["model_configuration"]["surface_wave_model"]["contract_version"],
                SURFACE_WAVE_MODEL_CONTRACT_VERSION,
            )
            self.assertEqual(
                surface_wave_plan["model_configuration"]["surface_wave_model"]["model_family"],
                DEFAULT_SURFACE_WAVE_MODEL_FAMILY,
            )
            self.assertEqual(
                surface_wave_plan["model_configuration"]["surface_wave_model"]["parameter_bundle"][
                    "parameter_preset"
                ],
                "motion_patch_reference",
            )
            self.assertEqual(
                surface_wave_plan["model_configuration"]["surface_wave_model"]["parameter_bundle"][
                    "damping"
                ]["gamma_per_ms"],
                0.18,
            )
            self.assertEqual(
                surface_wave_plan["model_configuration"]["surface_wave_reference"]["parameter_hash"],
                surface_wave_plan["model_configuration"]["surface_wave_model"]["parameter_hash"],
            )
            wave_execution = surface_wave_plan["model_configuration"]["surface_wave_execution_plan"]
            self.assertEqual(
                wave_execution["resolution"]["state_space"],
                "fine_surface_vertices",
            )
            self.assertEqual(
                wave_execution["resolution"]["coupling_anchor_resolution"],
                "surface_patch_cloud",
            )
            self.assertEqual(
                wave_execution["hybrid_morphology"]["contract_version"],
                HYBRID_MORPHOLOGY_CONTRACT_VERSION,
            )
            self.assertEqual(
                wave_execution["hybrid_morphology"]["discovered_morphology_classes"],
                [SURFACE_NEURON_CLASS],
            )
            self.assertEqual(
                wave_execution["selected_root_operator_assets"][0]["hybrid_morphology"][
                    "morphology_class"
                ],
                SURFACE_NEURON_CLASS,
            )
            self.assertEqual(
                wave_execution["selected_root_coupling_assets"][0]["hybrid_morphology"][
                    "morphology_class"
                ],
                SURFACE_NEURON_CLASS,
            )
            self.assertEqual(
                wave_execution["solver"]["shared_output_timestep_ms"],
                surface_wave_plan["runtime"]["timebase"]["dt_ms"],
            )
            self.assertGreater(
                wave_execution["solver"]["internal_substep_count"],
                1,
            )
            self.assertLess(
                wave_execution["solver"]["integration_timestep_ms"],
                wave_execution["solver"]["shared_output_timestep_ms"],
            )
            self.assertEqual(
                wave_execution["stability_guardrails"]["limiting_root_id"],
                101,
            )
            self.assertEqual(
                wave_execution["selected_root_operator_assets"][0]["root_id"],
                101,
            )
            self.assertEqual(
                wave_execution["selected_root_coupling_assets"][0]["topology_family"],
                "distributed_patch_cloud",
            )
            self.assertTrue(
                any(
                    item["asset_role"] == "surface_wave_operator_inventory"
                    for item in surface_wave_plan["selected_assets"]
                )
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

    def test_manifest_mixed_fidelity_plan_resolution_is_deterministic_and_records_per_root_assignments(self) -> None:
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
            schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
            design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"
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
                        "project_role": "surface_simulated",
                        "asset_profile": "point",
                    },
                ],
            )

            resolved_input = resolve_stimulus_input(
                manifest_path=manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
                processed_stimulus_dir=tmp_dir / "out" / "stimuli",
            )
            record_stimulus_bundle(resolved_input)

            first_mixed_plan = resolve_manifest_mixed_fidelity_plan(
                manifest_path=manifest_path,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
                arm_id="surface_wave_intact",
            )
            second_mixed_plan = resolve_manifest_mixed_fidelity_plan(
                manifest_path=manifest_path,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
                arm_id="surface_wave_intact",
            )

            self.assertEqual(first_mixed_plan, second_mixed_plan)
            self.assertEqual(
                first_mixed_plan["assignment_policy"]["default_source"],
                "registry_project_role",
            )
            self.assertEqual(
                first_mixed_plan["arm_overrides"]["default_morphology_class"],
                POINT_NEURON_CLASS,
            )
            self.assertEqual(
                first_mixed_plan["resolved_class_counts"],
                {
                    POINT_NEURON_CLASS: 1,
                    SKELETON_NEURON_CLASS: 1,
                    SURFACE_NEURON_CLASS: 1,
                },
            )
            per_root = {
                int(item["root_id"]): item
                for item in first_mixed_plan["per_root_assignments"]
            }
            self.assertEqual(
                per_root[101]["realized_morphology_class"],
                SURFACE_NEURON_CLASS,
            )
            self.assertEqual(
                per_root[202]["realized_morphology_class"],
                SKELETON_NEURON_CLASS,
            )
            self.assertEqual(
                per_root[303]["realized_morphology_class"],
                POINT_NEURON_CLASS,
            )
            self.assertEqual(
                per_root[101]["assignment_provenance"]["resolved_from"],
                "arm_root_override",
            )
            self.assertEqual(
                per_root[202]["assignment_provenance"]["resolved_from"],
                "arm_root_override",
            )
            self.assertEqual(
                per_root[303]["assignment_provenance"]["resolved_from"],
                "arm_default_morphology_class",
            )
            self.assertEqual(
                per_root[303]["registry_default_morphology_class"],
                SURFACE_NEURON_CLASS,
            )
            self.assertEqual(
                per_root[303]["approximation_route"]["relation_to_registry_default"],
                "demoted_from_registry_default",
            )
            self.assertTrue(
                per_root[101]["required_local_assets"]["processed_surface_mesh"]["exists"]
            )
            self.assertTrue(
                per_root[202]["required_local_assets"]["raw_swc_skeleton"]["exists"]
            )
            self.assertTrue(
                per_root[202]["required_local_assets"][SKELETON_RUNTIME_ASSET_KEY]["exists"]
            )
            self.assertEqual(
                per_root[202]["skeleton_runtime_asset"]["contract_version"],
                SKELETON_RUNTIME_ASSET_CONTRACT_VERSION,
            )
            self.assertIsNone(per_root[303]["surface_operator_asset"])
            self.assertEqual(
                per_root[202]["coupling_resolution"]["incoming_resolution"],
                "skeleton_node",
            )

            full_plan = resolve_manifest_simulation_plan(
                manifest_path=manifest_path,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )
            surface_wave_plan = next(
                arm_plan
                for arm_plan in full_plan["arm_plans"]
                if arm_plan["arm_reference"]["arm_id"] == "surface_wave_intact"
            )
            wave_execution = surface_wave_plan["model_configuration"]["surface_wave_execution_plan"]
            self.assertEqual(
                wave_execution["resolution"]["state_space"],
                "per_root_morphology_class",
            )
            self.assertEqual(
                wave_execution["selected_root_operator_assets_scope"],
                "surface_neuron_roots_only",
            )
            self.assertEqual(
                [item["root_id"] for item in wave_execution["selected_root_operator_assets"]],
                [101],
            )
            self.assertEqual(
                [item["root_id"] for item in wave_execution["selected_root_skeleton_assets"]],
                [202],
            )

    def test_manifest_readout_analysis_plan_resolution_is_deterministic_and_respects_manifest_precedence(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            manifest_path = ROOT / "manifests" / "examples" / "milestone_1_demo.yaml"
            schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
            design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"
            latency_override_path = tmp_dir / "out" / "analysis" / "latency_override.png"
            config_path = _write_simulation_fixture(
                tmp_dir,
                readout_catalog=[
                    {
                        "readout_id": "shared_output_peak",
                        "scope": "circuit_output",
                        "aggregation": "max_over_root_ids",
                        "units": "activation_au",
                        "value_semantics": "shared_downstream_activation",
                        "description": "Shared downstream output peak for matched comparisons.",
                    },
                    {
                        "readout_id": "direction_selectivity_index",
                        "scope": "comparison_panel",
                        "aggregation": "identity",
                        "units": "unitless",
                        "value_semantics": "direction_selectivity_index",
                        "description": "Shared direction-selectivity summary for matched comparisons.",
                    },
                    {
                        "readout_id": "shared_output_mean",
                        "scope": "circuit_output",
                        "aggregation": "mean_over_root_ids",
                        "units": "activation_au",
                        "value_semantics": "shared_downstream_activation",
                        "description": "Shared downstream output mean for matched comparisons.",
                    },
                ],
                analysis_config={
                    "active_readout_ids": [
                        "shared_output_peak",
                        "shared_output_mean",
                    ],
                    "active_metric_ids": [
                        "patch_activation_entropy_bits",
                    ],
                    "analysis_windows": {
                        "shared_response_window": {
                            "start_ms": 60.0,
                            "end_ms": 430.0,
                            "description": "Fixture override window.",
                        },
                    },
                    "experiment_output_targets": [
                        {
                            "output_id": "latency_shift_comparison",
                            "path": str(latency_override_path),
                        },
                    ],
                },
            )

            _record_fixture_stimulus_bundle(
                manifest_path=manifest_path,
                processed_stimulus_dir=tmp_dir / "out" / "stimuli",
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )

            first_plan = resolve_manifest_readout_analysis_plan(
                manifest_path=manifest_path,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )
            second_plan = resolve_manifest_readout_analysis_plan(
                manifest_path=manifest_path,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )
            simulation_plan = resolve_manifest_simulation_plan(
                manifest_path=manifest_path,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )

            self.assertEqual(first_plan, second_plan)
            self.assertEqual(first_plan, simulation_plan["readout_analysis_plan"])
            self.assertEqual(
                [item["readout_id"] for item in first_plan["active_shared_readouts"]],
                ["shared_output_mean", "shared_output_peak"],
            )
            shared_window = next(
                item
                for item in first_plan["analysis_window_catalog"]
                if item["window_id"] == "shared_response_window"
            )
            self.assertEqual(shared_window["start_ms"], 60.0)
            self.assertEqual(shared_window["end_ms"], 430.0)
            self.assertEqual(shared_window["description"], "Fixture override window.")
            self.assertIn("null_direction_suppression_index", first_plan["active_metric_ids"])
            self.assertIn("response_latency_to_peak_ms", first_plan["active_metric_ids"])
            self.assertIn("direction_selectivity_index", first_plan["active_metric_ids"])
            self.assertIn("on_off_selectivity_index", first_plan["active_metric_ids"])
            self.assertIn("patch_activation_entropy_bits", first_plan["active_metric_ids"])
            latency_target = next(
                item
                for item in first_plan["experiment_output_targets"]
                if item["output_id"] == "latency_shift_comparison"
            )
            self.assertNotEqual(latency_target["path"], str(latency_override_path))
            decision_panel_target = next(
                item
                for item in first_plan["experiment_output_targets"]
                if item["output_id"] == "milestone_decision_panel"
            )
            self.assertEqual(
                decision_panel_target["analysis_output_id"],
                "milestone_1_decision_panel",
            )
            self.assertEqual(
                [item["requested_metric_id"] for item in first_plan["manifest_metric_requests"]],
                [
                    "geometry_sensitive_null_direction_suppression_effect",
                    "response_latency_to_peak_ms",
                    "direction_selectivity_index",
                    "geometry_sensitive_shared_output_effect",
                ],
            )

    def test_manifest_readout_analysis_plan_fails_clearly_for_invalid_requests(self) -> None:
        schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
        design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"

        with self.subTest("unsupported_manifest_metric"):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                manifest_path = _write_manifest_fixture(
                    tmp_dir,
                    manifest_overrides={
                        "primary_metric": "unsupported_metric_request",
                    },
                )
                config_path = _write_simulation_fixture(tmp_dir)
                _record_fixture_stimulus_bundle(
                    manifest_path=manifest_path,
                    processed_stimulus_dir=tmp_dir / "out" / "stimuli",
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
                with self.assertRaises(ValueError) as ctx:
                    resolve_manifest_readout_analysis_plan(
                        manifest_path=manifest_path,
                        config_path=config_path,
                        schema_path=schema_path,
                        design_lock_path=design_lock_path,
                    )
                self.assertIn(
                    "unsupported analysis metric id 'unsupported_metric_request'",
                    str(ctx.exception),
                )

        with self.subTest("incompatible_condition_pairing"):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                manifest_path = _write_manifest_fixture(
                    tmp_dir,
                    manifest_overrides={
                        "stimulus_family": "flash",
                        "stimulus_name": "simple_flash",
                    },
                )
                config_path = _write_simulation_fixture(tmp_dir)
                _record_fixture_stimulus_bundle(
                    manifest_path=manifest_path,
                    processed_stimulus_dir=tmp_dir / "out" / "stimuli",
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
                with self.assertRaises(ValueError) as ctx:
                    resolve_manifest_readout_analysis_plan(
                        manifest_path=manifest_path,
                        config_path=config_path,
                        schema_path=schema_path,
                        design_lock_path=design_lock_path,
                    )
                self.assertIn(
                    "requires stimulus condition pair declarations ['preferred_vs_null']",
                    str(ctx.exception),
                )

        with self.subTest("missing_shared_readout_dependency"):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                manifest_path = ROOT / "manifests" / "examples" / "milestone_1_demo.yaml"
                config_path = _write_simulation_fixture(
                    tmp_dir,
                    analysis_config={
                        "active_readout_ids": [
                            "missing_shared_readout",
                        ],
                    },
                )
                _record_fixture_stimulus_bundle(
                    manifest_path=manifest_path,
                    processed_stimulus_dir=tmp_dir / "out" / "stimuli",
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
                with self.assertRaises(ValueError) as ctx:
                    resolve_manifest_readout_analysis_plan(
                        manifest_path=manifest_path,
                        config_path=config_path,
                        schema_path=schema_path,
                        design_lock_path=design_lock_path,
                    )
                self.assertIn(
                    "analysis.active_readout_ids references readout ids",
                    str(ctx.exception),
                )

        with self.subTest("unrealizable_baseline_challenge_output"):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                manifest_payload = yaml.safe_load(
                    (
                        ROOT / "manifests" / "examples" / "milestone_1_demo.yaml"
                    ).read_text(encoding="utf-8")
                )
                manifest_path = _write_manifest_fixture(
                    tmp_dir,
                    manifest_overrides={
                        "comparison_arms": [
                            arm
                            for arm in manifest_payload["comparison_arms"]
                            if arm.get("baseline_family") != "P1"
                        ],
                        "success_criteria_ids": [
                            criterion_id
                            for criterion_id in manifest_payload["success_criteria_ids"]
                            if criterion_id != "m1_survives_stronger_baseline"
                        ],
                    },
                )
                config_path = _write_simulation_fixture(tmp_dir)
                _record_fixture_stimulus_bundle(
                    manifest_path=manifest_path,
                    processed_stimulus_dir=tmp_dir / "out" / "stimuli",
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
                with self.assertRaises(ValueError) as ctx:
                    resolve_manifest_readout_analysis_plan(
                        manifest_path=manifest_path,
                        config_path=config_path,
                        schema_path=schema_path,
                        design_lock_path=design_lock_path,
                    )
                self.assertIn(
                    "baseline_challenge_comparison' cannot be realized",
                    str(ctx.exception),
                )

    def test_missing_skeleton_asset_fails_clearly_for_skeleton_assignment(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            manifest_path = _write_manifest_fixture(
                tmp_dir,
                surface_wave_fidelity_assignment={
                    "root_overrides": [
                        {"root_id": 202, "morphology_class": "skeleton_neuron"},
                    ],
                },
            )
            schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
            design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"
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
                        "project_role": "point_simulated",
                        "asset_profile": "point",
                    },
                ],
            )

            resolved_input = resolve_stimulus_input(
                manifest_path=manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
                processed_stimulus_dir=tmp_dir / "out" / "stimuli",
            )
            record_stimulus_bundle(resolved_input)

            with self.assertRaises(ValueError) as ctx:
                resolve_manifest_simulation_plan(
                    manifest_path=manifest_path,
                    config_path=config_path,
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
            self.assertIn("required local asset 'raw_swc_skeleton' is unavailable", str(ctx.exception))

    def test_incompatible_point_coupling_fails_clearly_for_point_assignment(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            manifest_path = ROOT / "manifests" / "examples" / "milestone_1_demo.yaml"
            schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
            design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"
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
                        "project_role": "point_simulated",
                        "asset_profile": "point",
                    },
                ],
            )

            resolved_input = resolve_stimulus_input(
                manifest_path=manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
                processed_stimulus_dir=tmp_dir / "out" / "stimuli",
            )
            record_stimulus_bundle(resolved_input)

            manifest_json_path = tmp_dir / "out" / "asset_manifest.json"
            manifest_payload = json.loads(manifest_json_path.read_text(encoding="utf-8"))
            manifest_payload["202"]["coupling_bundle"]["topology_family"] = "patch_to_patch"
            manifest_payload["202"]["coupling_bundle"]["fallback_hierarchy"] = [
                "surface_patch_cloud",
                "skeleton_segment_cloud",
            ]
            manifest_json_path.write_text(
                json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError) as ctx:
                resolve_manifest_simulation_plan(
                    manifest_path=manifest_path,
                    config_path=config_path,
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
            self.assertIn("does not support 'point_neuron_lumped' anchors", str(ctx.exception))

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

    def test_missing_operator_asset_fails_clearly(self) -> None:
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

            missing_operator = (
                tmp_dir
                / "out"
                / "processed_graphs"
                / "101_fine_operator.npz"
            )
            missing_operator.unlink()

            with self.assertRaises(ValueError) as ctx:
                resolve_manifest_simulation_plan(
                    manifest_path=manifest_path,
                    config_path=config_path,
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
            self.assertIn(
                "required local asset 'fine_surface_operator' is unavailable",
                str(ctx.exception),
            )

    def test_incompatible_surface_wave_coupling_topology_fails_clearly(self) -> None:
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

            manifest_json_path = tmp_dir / "out" / "asset_manifest.json"
            manifest_payload = json.loads(manifest_json_path.read_text(encoding="utf-8"))
            manifest_payload["101"]["coupling_bundle"]["topology_family"] = "point_to_point"
            manifest_payload["101"]["coupling_bundle"]["fallback_hierarchy"] = [
                "point_neuron_lumped"
            ]
            manifest_json_path.write_text(
                json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError) as ctx:
                resolve_manifest_simulation_plan(
                    manifest_path=manifest_path,
                    config_path=config_path,
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
            self.assertIn(
                "requires coupling topology_family 'distributed_patch_cloud'",
                str(ctx.exception),
            )

    def test_unstable_surface_wave_timebase_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            manifest_path = ROOT / "manifests" / "examples" / "milestone_1_demo.yaml"
            schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
            design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"
            config_path = _write_simulation_fixture(
                tmp_dir,
                timebase_dt_ms=250.0,
                timebase_sample_count=2,
            )

            resolved_input = resolve_stimulus_input(
                manifest_path=manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
                processed_stimulus_dir=tmp_dir / "out" / "stimuli",
            )
            record_stimulus_bundle(resolved_input)

            with self.assertRaises(ValueError) as ctx:
                resolve_manifest_simulation_plan(
                    manifest_path=manifest_path,
                    config_path=config_path,
                    schema_path=schema_path,
                    design_lock_path=design_lock_path,
                )
            self.assertIn(
                "requires 497 internal substeps",
                str(ctx.exception),
            )


def _write_simulation_fixture(
    tmp_dir: Path,
    *,
    timebase_dt_ms: float | None = None,
    timebase_sample_count: int | None = None,
    root_specs: list[dict[str, object]] | None = None,
    readout_catalog: list[dict[str, object]] | None = None,
    analysis_config: dict[str, object] | None = None,
) -> Path:
    output_dir = tmp_dir / "out"
    normalized_root_specs = _normalize_root_specs(root_specs)
    selected_root_ids = [spec["root_id"] for spec in normalized_root_specs]
    selected_root_ids_path = output_dir / "selected_root_ids.txt"
    selected_root_ids_path.parent.mkdir(parents=True, exist_ok=True)
    selected_root_ids_path.write_text(
        "".join(f"{root_id}\n" for root_id in selected_root_ids),
        encoding="utf-8",
    )

    subset_manifest_path = output_dir / "subsets" / "motion_minimal" / "subset_manifest.json"
    subset_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    subset_manifest_path.write_text(
        json.dumps(
            {
                "subset_manifest_version": "1",
                "preset_name": "motion_minimal",
                "root_ids": selected_root_ids,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
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
            "active_preset": "motion_minimal",
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


if __name__ == "__main__":
    unittest.main()
