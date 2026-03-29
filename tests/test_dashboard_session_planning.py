from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.dashboard_session_contract import (
    ANALYSIS_PANE_ID,
    APP_SHELL_INDEX_ARTIFACT_ID,
    CIRCUIT_PANE_ID,
    METADATA_JSON_KEY,
    MORPHOLOGY_PANE_ID,
    PHASE_MAP_REFERENCE_OVERLAY_ID,
    SCENE_PANE_ID,
    SESSION_PAYLOAD_ARTIFACT_ID,
    SESSION_STATE_ARTIFACT_ID,
    TIME_SERIES_PANE_ID,
    discover_dashboard_session_bundle_paths,
    load_dashboard_session_metadata,
)
from flywire_wave.dashboard_session_planning import (
    package_dashboard_session,
    resolve_dashboard_session_plan,
)
from flywire_wave.experiment_analysis_contract import (
    ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
    discover_experiment_analysis_bundle_paths,
    load_experiment_analysis_bundle_metadata,
)
from flywire_wave.experiment_comparison_analysis import (
    discover_simulation_run_plans,
    execute_experiment_comparison_workflow,
)
from flywire_wave.geometry_contract import load_geometry_manifest, load_geometry_manifest_records
from flywire_wave.io_utils import write_deterministic_npz, write_json
from flywire_wave.simulation_planning import resolve_manifest_simulation_plan
from flywire_wave.simulator_result_contract import (
    METRICS_TABLE_KEY,
    READOUT_TRACES_KEY,
    STATE_SUMMARY_KEY,
    build_simulator_extension_artifact_record,
    build_simulator_result_bundle_paths,
    build_simulator_result_bundle_metadata,
    discover_simulator_result_bundle_paths,
    load_simulator_result_bundle_metadata,
    write_simulator_result_bundle_metadata,
)
from flywire_wave.validation_contract import (
    OFFLINE_REVIEW_REPORT_ARTIFACT_ID,
    REVIEW_HANDOFF_ARTIFACT_ID,
    VALIDATION_SUMMARY_ARTIFACT_ID,
    discover_validation_bundle_paths,
    load_validation_bundle_metadata,
    write_validation_bundle_metadata,
)
from flywire_wave.validation_planning import resolve_validation_plan

try:
    from test_experiment_comparison_analysis import (
        _load_default_stimulus_metadata,
        _materialize_condition_stimuli,
        _materialize_experiment_comparison_fixture,
        _materialize_simulator_bundles,
    )
except ModuleNotFoundError:
    from tests.test_experiment_comparison_analysis import (
        _load_default_stimulus_metadata,
        _materialize_condition_stimuli,
        _materialize_experiment_comparison_fixture,
        _materialize_simulator_bundles,
    )


EXPERIMENT_ID = "milestone_1_demo_motion_patch"
DEFAULT_BASELINE_ARM_ID = "baseline_p0_intact"
DEFAULT_WAVE_ARM_ID = "surface_wave_intact"
DEFAULT_SEED = 11
DEFAULT_CONDITION_IDS = ["on_polarity", "preferred_direction"]
DEFAULT_SELECTED_NEURON_ID = 101


class DashboardSessionPlanningTest(unittest.TestCase):
    def test_manifest_resolution_is_deterministic_and_packages_session_bundle(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))

            first = resolve_dashboard_session_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )
            second = resolve_dashboard_session_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )

            self.assertEqual(first, second)
            self.assertEqual(
                list(first["pane_inputs"]),
                [
                    SCENE_PANE_ID,
                    CIRCUIT_PANE_ID,
                    MORPHOLOGY_PANE_ID,
                    TIME_SERIES_PANE_ID,
                    ANALYSIS_PANE_ID,
                ],
            )
            self.assertEqual(
                first["selected_bundle_pair"]["baseline"]["arm_id"],
                DEFAULT_BASELINE_ARM_ID,
            )
            self.assertEqual(
                first["selected_bundle_pair"]["wave"]["arm_id"],
                DEFAULT_WAVE_ARM_ID,
            )
            self.assertEqual(first["selected_bundle_pair"]["shared_seed"], DEFAULT_SEED)
            self.assertEqual(
                first["pane_inputs"][TIME_SERIES_PANE_ID]["selected_readout_id"],
                "shared_output_mean",
            )
            self.assertEqual(
                first["pane_inputs"][TIME_SERIES_PANE_ID]["context_version"],
                "dashboard_time_series_context.v1",
            )
            self.assertEqual(
                first["pane_inputs"][TIME_SERIES_PANE_ID]["replay_model"][
                    "shared_timebase_status"
                ]["availability"],
                "available",
            )
            self.assertEqual(
                first["dashboard_session_state"]["replay_state"]["comparison_mode"],
                "paired_baseline_vs_wave",
            )
            self.assertIn(
                PHASE_MAP_REFERENCE_OVERLAY_ID,
                first["overlay_catalog"]["available_overlay_ids"],
            )

            packaged = package_dashboard_session(first)
            metadata = load_dashboard_session_metadata(packaged["metadata_path"])
            bundle_paths = discover_dashboard_session_bundle_paths(metadata)

            self.assertEqual(metadata["bundle_id"], first["dashboard_session"]["bundle_id"])
            self.assertEqual(
                bundle_paths[METADATA_JSON_KEY],
                Path(packaged["metadata_path"]).resolve(),
            )
            self.assertEqual(
                bundle_paths[SESSION_PAYLOAD_ARTIFACT_ID],
                Path(packaged["session_payload_path"]).resolve(),
            )
            self.assertEqual(
                bundle_paths[SESSION_STATE_ARTIFACT_ID],
                Path(packaged["session_state_path"]).resolve(),
            )
            self.assertEqual(
                bundle_paths[APP_SHELL_INDEX_ARTIFACT_ID],
                Path(packaged["app_shell_path"]).resolve(),
            )
            self.assertTrue(
                str(Path(packaged["bundle_directory"]).resolve()).endswith(
                    f"/dashboard_sessions/{EXPERIMENT_ID}/{metadata['session_spec_hash']}"
                )
            )
            self.assertEqual(
                json.loads(
                    Path(packaged["session_payload_path"]).read_text(encoding="utf-8")
                )["selected_bundle_pair"]["shared_seed"],
                DEFAULT_SEED,
            )
            self.assertIn(
                "Milestone 14 Dashboard Session",
                Path(packaged["app_shell_path"]).read_text(encoding="utf-8"),
            )

    def test_experiment_and_explicit_inputs_converge_and_explicit_bundles_win_over_overrides(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))

            experiment_plan = resolve_dashboard_session_plan(
                experiment_id=EXPERIMENT_ID,
                config_path=fixture["config_path"],
                baseline_arm_id=DEFAULT_BASELINE_ARM_ID,
                wave_arm_id=DEFAULT_WAVE_ARM_ID,
                preferred_seed=DEFAULT_SEED,
                preferred_condition_ids=DEFAULT_CONDITION_IDS,
            )

            baseline_metadata = _load_bundle_metadata(
                fixture,
                arm_id=DEFAULT_BASELINE_ARM_ID,
            )
            wave_metadata = _load_bundle_metadata(
                fixture,
                arm_id=DEFAULT_WAVE_ARM_ID,
            )
            explicit_plan = resolve_dashboard_session_plan(
                config_path=fixture["config_path"],
                baseline_bundle_metadata=baseline_metadata,
                wave_bundle_metadata=wave_metadata,
                analysis_bundle_metadata=fixture["analysis_bundle_metadata"],
                validation_bundle_metadata=fixture["validation_bundle_metadata"],
                baseline_arm_id="baseline_p1_intact",
                wave_arm_id="surface_wave_shuffled",
                preferred_seed=17,
                preferred_condition_ids=["null_direction", "off_polarity"],
            )

            self.assertEqual(
                explicit_plan["selected_bundle_pair"]["baseline"]["bundle_id"],
                baseline_metadata["bundle_id"],
            )
            self.assertEqual(
                explicit_plan["selected_bundle_pair"]["wave"]["bundle_id"],
                wave_metadata["bundle_id"],
            )
            self.assertEqual(
                experiment_plan["dashboard_session"]["session_spec_hash"],
                explicit_plan["dashboard_session"]["session_spec_hash"],
            )
            self.assertEqual(
                experiment_plan["pane_inputs"],
                explicit_plan["pane_inputs"],
            )

    def test_planning_fails_clearly_for_missing_phase_map_overlay_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))

            analysis_paths = discover_experiment_analysis_bundle_paths(
                fixture["analysis_bundle_metadata"]
            )
            analysis_ui_payload = json.loads(
                analysis_paths[ANALYSIS_UI_PAYLOAD_ARTIFACT_ID].read_text(encoding="utf-8")
            )
            analysis_ui_payload["wave_only_diagnostics"]["diagnostic_cards"] = []
            analysis_ui_payload["wave_only_diagnostics"]["phase_map_references"] = []
            write_json(
                analysis_ui_payload,
                analysis_paths[ANALYSIS_UI_PAYLOAD_ARTIFACT_ID],
            )

            with self.assertRaises(ValueError) as ctx:
                resolve_dashboard_session_plan(
                    experiment_id=EXPERIMENT_ID,
                    config_path=fixture["config_path"],
                    baseline_arm_id=DEFAULT_BASELINE_ARM_ID,
                    wave_arm_id=DEFAULT_WAVE_ARM_ID,
                    preferred_seed=DEFAULT_SEED,
                    preferred_condition_ids=DEFAULT_CONDITION_IDS,
                    active_overlay_id=PHASE_MAP_REFERENCE_OVERLAY_ID,
                )

            self.assertIn(
                "requested wave-only diagnostics are absent",
                str(ctx.exception),
            )

    def test_planning_uses_surface_proxy_when_mesh_is_missing_but_wave_state_is_packaged(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))
            baseline_metadata = _load_bundle_metadata(
                fixture,
                arm_id=DEFAULT_BASELINE_ARM_ID,
            )
            geometry_manifest_path = _selected_asset_path(
                baseline_metadata,
                asset_role="geometry_manifest",
            )
            manifest_records = load_geometry_manifest_records(geometry_manifest_path)
            simplified_mesh_path = Path(
                manifest_records[str(DEFAULT_SELECTED_NEURON_ID)]["assets"]["simplified_mesh"]["path"]
            ).resolve()
            simplified_mesh_path.unlink()

            plan = resolve_dashboard_session_plan(
                experiment_id=EXPERIMENT_ID,
                config_path=fixture["config_path"],
                baseline_arm_id=DEFAULT_BASELINE_ARM_ID,
                wave_arm_id=DEFAULT_WAVE_ARM_ID,
                preferred_seed=DEFAULT_SEED,
                preferred_condition_ids=DEFAULT_CONDITION_IDS,
                selected_neuron_id=DEFAULT_SELECTED_NEURON_ID,
            )
            selected_root = next(
                item
                for item in plan["pane_inputs"][MORPHOLOGY_PANE_ID]["root_catalog"]
                if int(item["root_id"]) == DEFAULT_SELECTED_NEURON_ID
            )
            self.assertEqual(
                selected_root["preferred_representation"],
                "surface_patch_proxy",
            )

    def test_planning_fails_clearly_for_mismatched_shared_timebases(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))
            baseline_metadata = _load_bundle_metadata(
                fixture,
                arm_id=DEFAULT_BASELINE_ARM_ID,
            )
            wave_metadata = _load_bundle_metadata(
                fixture,
                arm_id=DEFAULT_WAVE_ARM_ID,
            )
            modified_wave_metadata = build_simulator_result_bundle_metadata(
                manifest_reference=wave_metadata["manifest_reference"],
                arm_reference=wave_metadata["arm_reference"],
                determinism=wave_metadata["determinism"],
                timebase={
                    **copy.deepcopy(dict(wave_metadata["timebase"])),
                    "dt_ms": 20.0,
                    "duration_ms": 140.0,
                },
                selected_assets=wave_metadata["selected_assets"],
                readout_catalog=wave_metadata["readout_catalog"],
                processed_simulator_results_dir=fixture["processed_simulator_results_dir"],
                state_summary_status="ready",
                readout_traces_status="ready",
                metrics_table_status="ready",
            )
            modified_wave_metadata_path = write_simulator_result_bundle_metadata(
                modified_wave_metadata
            )
            _copy_shared_bundle_artifacts(
                source_bundle=wave_metadata,
                target_bundle=modified_wave_metadata,
            )

            modified_analysis = copy.deepcopy(fixture["analysis_bundle_metadata"])
            _replace_bundle_inventory_entry(
                analysis_bundle_metadata=modified_analysis,
                old_bundle=wave_metadata,
                new_bundle=modified_wave_metadata,
                new_metadata_path=modified_wave_metadata_path,
            )
            modified_validation = copy.deepcopy(fixture["validation_bundle_metadata"])
            _replace_validation_evidence_bundle_id(
                validation_bundle_metadata=modified_validation,
                old_bundle_id=str(wave_metadata["bundle_id"]),
                new_bundle_id=str(modified_wave_metadata["bundle_id"]),
            )

            with self.assertRaises(ValueError) as ctx:
                resolve_dashboard_session_plan(
                    config_path=fixture["config_path"],
                    baseline_bundle_metadata=baseline_metadata,
                    wave_bundle_metadata=modified_wave_metadata,
                    analysis_bundle_metadata=modified_analysis,
                    validation_bundle_metadata=modified_validation,
                )

            self.assertIn(
                "share one canonical timebase",
                str(ctx.exception),
            )


def _materialize_dashboard_fixture(tmp_dir: Path) -> dict[str, Any]:
    fixture = _materialize_experiment_comparison_fixture(tmp_dir)
    _prepare_dashboard_geometry_fixture(fixture)
    shutil.rmtree(tmp_dir / "out" / "simulator_results" / "bundles", ignore_errors=True)

    simulation_plan = resolve_manifest_simulation_plan(
        manifest_path=fixture["manifest_path"],
        config_path=fixture["config_path"],
        schema_path=fixture["schema_path"],
        design_lock_path=fixture["design_lock_path"],
    )
    default_stimulus_metadata = _load_default_stimulus_metadata(simulation_plan)
    condition_stimuli = _materialize_condition_stimuli(
        processed_stimulus_dir=tmp_dir / "out" / "stimuli",
        analysis_plan=simulation_plan["readout_analysis_plan"],
        default_stimulus_metadata=default_stimulus_metadata,
    )
    run_plans = discover_simulation_run_plans(
        simulation_plan,
        use_manifest_seed_sweep=True,
    )
    fixture = {
        **fixture,
        "bundle_metadata_records": _materialize_simulator_bundles(
            run_plans=run_plans,
            condition_stimuli=condition_stimuli,
        ),
    }
    _augment_dashboard_wave_bundles(fixture)

    analysis_result = execute_experiment_comparison_workflow(
        manifest_path=fixture["manifest_path"],
        config_path=fixture["config_path"],
        schema_path=fixture["schema_path"],
        design_lock_path=fixture["design_lock_path"],
    )
    validation_plan = resolve_validation_plan(
        config_path=fixture["config_path"],
        simulation_plan=simulation_plan,
        analysis_plan=simulation_plan["readout_analysis_plan"],
        bundle_set=analysis_result["bundle_set"],
        analysis_bundle_metadata_path=analysis_result["packaged_analysis_bundle"][
            "metadata_path"
        ],
    )
    validation_metadata = validation_plan["validation_bundle"]["metadata"]
    _write_fixture_validation_bundle(validation_metadata)
    return {
        **fixture,
        "simulation_plan": simulation_plan,
        "analysis_result": analysis_result,
        "analysis_bundle_metadata": load_experiment_analysis_bundle_metadata(
            analysis_result["packaged_analysis_bundle"]["metadata_path"]
        ),
        "validation_bundle_metadata": load_validation_bundle_metadata(
            validation_metadata["artifacts"][METADATA_JSON_KEY]["path"]
        ),
        "processed_simulator_results_dir": str(
            Path(
                analysis_result["bundle_set"]["processed_simulator_results_dir"]
            ).resolve()
        ),
    }


def _prepare_dashboard_geometry_fixture(fixture: Mapping[str, Any]) -> None:
    baseline_metadata = _load_bundle_metadata(
        fixture,
        arm_id=DEFAULT_BASELINE_ARM_ID,
    )
    geometry_manifest_path = _selected_asset_path(
        baseline_metadata,
        asset_role="geometry_manifest",
    )
    manifest_payload = load_geometry_manifest(geometry_manifest_path)
    if not manifest_payload:
        raise AssertionError("Expected fixture geometry manifest to be present.")

    root_101 = dict(manifest_payload["101"])
    root_202 = dict(manifest_payload["202"])

    surface_mesh_path = Path(root_101["assets"]["simplified_mesh"]["path"]).resolve()
    _write_surface_mesh_fixture(surface_mesh_path)
    root_101["assets"]["simplified_mesh"]["status"] = "ready"

    raw_skeleton_path = Path(root_202["assets"]["raw_skeleton"]["path"]).resolve()
    _write_dashboard_skeleton_fixture(raw_skeleton_path)
    root_202["assets"]["raw_skeleton"]["status"] = "ready"

    manifest_payload["101"] = root_101
    manifest_payload["202"] = root_202
    write_json(manifest_payload, geometry_manifest_path)


def _augment_dashboard_wave_bundles(fixture: Mapping[str, Any]) -> None:
    for record in fixture["bundle_metadata_records"]:
        metadata = load_simulator_result_bundle_metadata(record["metadata_path"])
        if str(metadata["arm_reference"]["model_mode"]) != "surface_wave":
            continue
        _augment_wave_bundle_for_dashboard(metadata)


def _augment_wave_bundle_for_dashboard(bundle_metadata: Mapping[str, Any]) -> None:
    bundle_paths = discover_simulator_result_bundle_paths(bundle_metadata)
    bundle_layout_paths = build_simulator_result_bundle_paths(
        experiment_id=str(bundle_metadata["manifest_reference"]["experiment_id"]),
        arm_id=str(bundle_metadata["arm_reference"]["arm_id"]),
        run_spec_hash=str(bundle_metadata["run_spec_hash"]),
        processed_simulator_results_dir=Path(
            bundle_metadata["bundle_layout"]["bundle_directory"]
        ).resolve().parents[3],
    )
    extension_root_directory = Path(
        bundle_metadata["bundle_layout"]["extension_root_directory"]
    ).resolve()
    model_artifacts = [
        copy.deepcopy(dict(item))
        for item in bundle_metadata["artifacts"].get("model_artifacts", [])
    ]
    existing_artifact_ids = {
        str(item["artifact_id"])
        for item in model_artifacts
    }
    if "surface_wave_patch_traces" not in existing_artifact_ids:
        model_artifacts.append(
            build_simulator_extension_artifact_record(
                bundle_paths=bundle_layout_paths,
                artifact_id="surface_wave_patch_traces",
                file_name="surface_wave_patch_traces.npz",
                format="npz_surface_wave_patch_traces.v1",
                status="ready",
                artifact_scope="shared_comparison",
                description="Fixture mixed-fidelity projection traces for the dashboard morphology pane.",
            )
        )
    if "mixed_morphology_state_bundle" not in existing_artifact_ids:
        model_artifacts.append(
            build_simulator_extension_artifact_record(
                bundle_paths=bundle_layout_paths,
                artifact_id="mixed_morphology_state_bundle",
                file_name="mixed_morphology_state_bundle.json",
                format="json_mixed_morphology_state_bundle.v1",
                status="ready",
                artifact_scope="model_diagnostic",
                description="Fixture mixed-fidelity state exports for the dashboard morphology pane.",
            )
        )

    mixed_morphology_index = {
        "format_version": "json_mixed_morphology_index.v1",
        "state_bundle_artifact_id": "mixed_morphology_state_bundle",
        "projection_artifact_id": "surface_wave_patch_traces",
        "shared_state_summary_artifact_id": "state_summary",
        "shared_readout_traces_artifact_id": "readout_traces",
        "roots": [
            {
                "root_id": 101,
                "morphology_class": "surface_neuron",
                "state_bundle_root_key": "101",
                "runtime_metadata_root_key": "101",
                "state_summary_ids": ["root_101_surface_activation_state"],
                "projection_time_array": "shared_time_ms",
                "projection_trace_array": "root_101_patch_activation",
                "projection_semantics": "surface_patch_activation",
                "shared_readout_ids": ["shared_output_mean"],
            },
            {
                "root_id": 202,
                "morphology_class": "skeleton_neuron",
                "state_bundle_root_key": "202",
                "runtime_metadata_root_key": "202",
                "state_summary_ids": ["root_202_skeleton_activation_state"],
                "projection_time_array": "shared_time_ms",
                "projection_trace_array": "root_202_skeleton_activation",
                "projection_semantics": "skeleton_projection_activation",
                "shared_readout_ids": ["shared_output_mean"],
            },
        ],
    }
    rewritten_metadata = build_simulator_result_bundle_metadata(
        manifest_reference=bundle_metadata["manifest_reference"],
        arm_reference=bundle_metadata["arm_reference"],
        determinism=bundle_metadata["determinism"],
        timebase=bundle_metadata["timebase"],
        selected_assets=[
            copy.deepcopy(dict(item))
            for item in bundle_metadata["selected_assets"]
        ],
        readout_catalog=bundle_metadata["readout_catalog"],
        processed_simulator_results_dir=Path(
            bundle_metadata["bundle_layout"]["bundle_directory"]
        ).resolve().parents[3],
        state_summary_status="ready",
        readout_traces_status="ready",
        metrics_table_status="ready",
        model_artifacts=model_artifacts,
        mixed_morphology_index=mixed_morphology_index,
    )
    write_simulator_result_bundle_metadata(rewritten_metadata)

    with np.load(bundle_paths[READOUT_TRACES_KEY], allow_pickle=False) as payload:
        time_ms = np.asarray(payload["time_ms"], dtype=np.float64)
    sample_count = int(time_ms.shape[0])
    patch_trace = np.column_stack(
        [
            np.linspace(0.05, 0.75, sample_count, dtype=np.float64),
            np.linspace(0.15, 0.55, sample_count, dtype=np.float64),
        ]
    )
    skeleton_trace = np.column_stack(
        [
            np.linspace(0.0, 0.35, sample_count, dtype=np.float64),
            np.linspace(0.05, 0.45, sample_count, dtype=np.float64),
            np.linspace(0.1, 0.55, sample_count, dtype=np.float64),
        ]
    )
    write_json(
        [
            {
                "state_id": "root_101_surface_activation_state",
                "scope": "root_state",
                "summary_stat": "mean",
                "value": float(np.mean(patch_trace[-1])),
                "units": "activation_au",
            },
            {
                "state_id": "root_202_skeleton_activation_state",
                "scope": "root_state",
                "summary_stat": "mean",
                "value": float(np.mean(skeleton_trace[-1])),
                "units": "activation_au",
            },
        ],
        bundle_paths[STATE_SUMMARY_KEY],
    )
    write_deterministic_npz(
        {
            "shared_time_ms": time_ms,
            "root_ids": np.asarray([101, 202], dtype=np.int64),
            "root_101_patch_activation": patch_trace,
            "root_202_skeleton_activation": skeleton_trace,
        },
        extension_root_directory / "surface_wave_patch_traces.npz",
    )
    write_json(
        {
            "format_version": "json_mixed_morphology_state_bundle.v1",
            "runtime_metadata_by_root": {
                "101": {
                    "root_id": 101,
                    "morphology_class": "surface_neuron",
                    "patch_count": 2,
                },
                "202": {
                    "root_id": 202,
                    "morphology_class": "skeleton_neuron",
                    "node_count": 3,
                },
            },
            "initial_state_exports_by_root": {
                "101": {"activation": [0.0, 0.0], "velocity": [0.0, 0.0]},
                "202": {"activation": [0.0, 0.0, 0.0], "velocity": [0.0, 0.0, 0.0]},
            },
            "final_state_exports_by_root": {
                "101": {
                    "activation": patch_trace[-1].astype(np.float64).tolist(),
                    "velocity": [0.0, 0.0],
                },
                "202": {
                    "activation": skeleton_trace[-1].astype(np.float64).tolist(),
                    "velocity": [0.0, 0.0, 0.0],
                },
            },
        },
        extension_root_directory / "mixed_morphology_state_bundle.json",
    )
    summary_artifact = next(
        (
            dict(item)
            for item in model_artifacts
            if str(item["artifact_id"]) == "surface_wave_summary"
        ),
        None,
    )
    if summary_artifact is not None:
        write_json(
            {
                "format_version": "json_surface_wave_execution_summary.v1",
                "runtime_metadata_by_root": [
                    {
                        "root_id": 101,
                        "morphology_class": "surface_neuron",
                        "patch_count": 2,
                        "source_reference": {},
                    },
                    {
                        "root_id": 202,
                        "morphology_class": "skeleton_neuron",
                        "node_count": 3,
                        "source_reference": {},
                    },
                ],
                "wave_specific_artifacts": {
                    "phase_map_artifact_id": "surface_wave_phase_map",
                    "patch_traces_artifact_id": "surface_wave_patch_traces",
                },
            },
            Path(summary_artifact["path"]).resolve(),
        )
def _write_fixture_validation_bundle(bundle_metadata: Mapping[str, Any]) -> None:
    write_validation_bundle_metadata(bundle_metadata)
    bundle_paths = discover_validation_bundle_paths(bundle_metadata)
    write_json(
        {
            "format_version": "json_validation_summary.v1",
            "bundle_id": str(bundle_metadata["bundle_id"]),
            "overall_status": "pass",
            "layer_summaries": [
                {
                    "layer_id": "numerical_sanity",
                    "overall_status": "pass",
                    "active_validator_ids": [
                        "surface_wave_stability_envelope",
                    ],
                },
                {
                    "layer_id": "task_sanity",
                    "overall_status": "review",
                    "active_validator_ids": [
                        "shared_effect_reproducibility",
                        "task_decoder_robustness",
                    ],
                },
            ],
        },
        bundle_paths[VALIDATION_SUMMARY_ARTIFACT_ID],
    )
    write_json(
        {
            "format_version": "json_validation_findings.v1",
            "bundle_id": str(bundle_metadata["bundle_id"]),
            "validator_findings": {
                "shared_effect_reproducibility": [
                    {
                        "finding_id": "shared_effect_reproducibility__delta_review",
                        "status": "review",
                        "case_id": "paired_delta_fixture",
                        "summary": "Paired delta effect is present but should stay under reviewer scrutiny.",
                    }
                ],
                "task_decoder_robustness": [
                    {
                        "finding_id": "task_decoder_robustness__phase_alignment_note",
                        "status": "pass",
                        "case_id": "phase_alignment_fixture",
                        "summary": "Decoder remains stable under the packaged phase-alignment fixture.",
                    }
                ],
            },
        },
        bundle_paths["validator_findings"],
    )
    write_json(
        {
            "format_version": "json_validation_review_handoff.v1",
            "bundle_id": str(bundle_metadata["bundle_id"]),
            "review_owner": "grant",
            "review_status": "review",
            "overall_status": "pass",
            "open_finding_ids": [
                "shared_effect_reproducibility__delta_review",
            ],
            "validator_statuses": {
                "shared_effect_reproducibility": "review",
                "task_decoder_robustness": "pass",
            },
            "scientific_plausibility_decision": "needs_follow_up",
            "reviewer_rationale": "Fixture keeps one open follow-up so the dashboard can surface reviewer-facing evidence.",
            "follow_on_action": "inspect_shared_delta_cards",
        },
        bundle_paths[REVIEW_HANDOFF_ARTIFACT_ID],
    )
    report_path = bundle_paths[OFFLINE_REVIEW_REPORT_ARTIFACT_ID]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("fixture validation report\n", encoding="utf-8")


def _write_surface_mesh_fixture(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "ply",
                "format ascii 1.0",
                "element vertex 4",
                "property float x",
                "property float y",
                "property float z",
                "element face 2",
                "property list uchar int vertex_indices",
                "end_header",
                "0.0 0.0 0.0",
                "1.0 0.0 0.1",
                "1.0 1.0 0.0",
                "0.0 1.0 -0.1",
                "3 0 1 2",
                "3 0 2 3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_dashboard_skeleton_fixture(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "1 1 0.0 0.0 0.0 1.0 -1",
                "2 3 0.9 0.4 0.0 0.5 1",
                "3 3 1.8 0.9 0.0 0.5 2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _bundle_record(
    fixture: Mapping[str, Any],
    *,
    arm_id: str,
    seed: int = DEFAULT_SEED,
    condition_ids: list[str] | None = None,
) -> Mapping[str, Any]:
    expected_condition_ids = condition_ids or DEFAULT_CONDITION_IDS
    return next(
        item
        for item in fixture["bundle_metadata_records"]
        if str(item["arm_id"]) == arm_id
        and int(item["seed"]) == seed
        and list(item["condition_ids"]) == expected_condition_ids
    )


def _load_bundle_metadata(
    fixture: Mapping[str, Any],
    *,
    arm_id: str,
    seed: int = DEFAULT_SEED,
    condition_ids: list[str] | None = None,
) -> dict[str, Any]:
    return load_simulator_result_bundle_metadata(
        _bundle_record(
            fixture,
            arm_id=arm_id,
            seed=seed,
            condition_ids=condition_ids,
        )["metadata_path"]
    )


def _selected_asset_path(
    bundle_metadata: Mapping[str, Any],
    *,
    asset_role: str,
) -> Path:
    return Path(
        next(
            item["path"]
            for item in bundle_metadata["selected_assets"]
            if str(item["asset_role"]) == asset_role
        )
    ).resolve()


def _copy_shared_bundle_artifacts(
    *,
    source_bundle: Mapping[str, Any],
    target_bundle: Mapping[str, Any],
) -> None:
    source_paths = discover_simulator_result_bundle_paths(source_bundle)
    target_paths = discover_simulator_result_bundle_paths(target_bundle)
    for artifact_id in (STATE_SUMMARY_KEY, READOUT_TRACES_KEY, METRICS_TABLE_KEY):
        target_paths[artifact_id].parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(
            source_paths[artifact_id].resolve(),
            target_paths[artifact_id].resolve(),
        )


def _replace_bundle_inventory_entry(
    *,
    analysis_bundle_metadata: dict[str, Any],
    old_bundle: Mapping[str, Any],
    new_bundle: Mapping[str, Any],
    new_metadata_path: Path,
) -> None:
    for item in analysis_bundle_metadata["bundle_set_reference"]["bundle_inventory"]:
        if str(item["bundle_id"]) != str(old_bundle["bundle_id"]):
            continue
        item["bundle_id"] = str(new_bundle["bundle_id"])
        item["metadata_path"] = str(Path(new_metadata_path).resolve())
        break
    else:
        raise AssertionError("Expected wave bundle inventory entry was not found.")


def _replace_validation_evidence_bundle_id(
    *,
    validation_bundle_metadata: dict[str, Any],
    old_bundle_id: str,
    new_bundle_id: str,
) -> None:
    evidence_bundle_ids = validation_bundle_metadata["validation_plan_reference"][
        "evidence_bundle_references"
    ]["simulator_result_bundle"]["bundle_ids"]
    for index, bundle_id in enumerate(evidence_bundle_ids):
        if str(bundle_id) != old_bundle_id:
            continue
        evidence_bundle_ids[index] = str(new_bundle_id)
        break
    else:
        raise AssertionError("Expected validation evidence bundle_id was not found.")


if __name__ == "__main__":
    unittest.main()
