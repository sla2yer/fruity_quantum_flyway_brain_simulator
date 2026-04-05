from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from unittest import mock
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.experiment_comparison_analysis import (
    EXPERIMENT_COMPARISON_SUMMARY_VERSION,
    execute_experiment_comparison_workflow,
)
from flywire_wave.experiment_analysis_contract import (
    ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
    COMPARISON_MATRICES_ARTIFACT_ID,
    OFFLINE_REPORT_INDEX_ARTIFACT_ID,
    OFFLINE_REPORT_SUMMARY_ARTIFACT_ID,
    VISUALIZATION_CATALOG_ARTIFACT_ID,
    discover_experiment_analysis_bundle_paths,
    load_experiment_analysis_bundle_metadata,
)
from flywire_wave.experiment_analysis_visualization import (
    generate_experiment_analysis_report,
)
from flywire_wave.io_utils import write_deterministic_npz, write_json
from flywire_wave.simulation_planning import (
    discover_simulation_run_plans,
    resolve_manifest_simulation_plan,
)
from flywire_wave.simulator_result_contract import (
    METRICS_TABLE_KEY,
    READOUT_TRACES_KEY,
    STATE_SUMMARY_KEY,
    build_selected_asset_reference,
    build_simulator_extension_artifact_record,
    build_simulator_result_bundle_metadata,
    build_simulator_result_bundle_paths,
    write_simulator_result_bundle_metadata,
)
from flywire_wave.stimulus_contract import (
    build_stimulus_bundle_metadata,
    load_stimulus_bundle_metadata,
    write_stimulus_bundle_metadata,
)
from test_simulation_planning import (
    _record_fixture_stimulus_bundle,
    _write_manifest_fixture,
    _write_simulation_fixture,
)


class ExperimentComparisonWorkflowTest(unittest.TestCase):
    def test_fixture_workflow_discovers_bundle_set_aggregates_seeds_and_scores_milestone_panel(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _materialize_experiment_comparison_fixture(tmp_dir)

            first = execute_experiment_comparison_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                output_path=tmp_dir / "analysis_summary.json",
            )
            second = execute_experiment_comparison_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                output_path=tmp_dir / "analysis_summary.json",
            )

            self.assertEqual(first["summary_version"], EXPERIMENT_COMPARISON_SUMMARY_VERSION)
            self.assertEqual(first["summary_path"], second["summary_path"])
            self.assertEqual(first["task_scores"], second["task_scores"])
            self.assertEqual(first["packaged_analysis_bundle"], second["packaged_analysis_bundle"])
            self.assertTrue(Path(first["summary_path"]).exists())
            self.assertEqual(len(first["bundle_set"]["bundle_inventory"]), 48)

            task_score = next(
                item
                for item in first["task_scores"]
                if item["score_id"]
                == "geometry_sensitive_null_direction_suppression_effect__geometry_ablation__p0"
            )
            self.assertGreater(task_score["value"], 0.0)
            self.assertEqual(task_score["units"], "unitless")

            null_test_status = {
                item["null_test_id"]: item["status"] for item in first["null_test_results"]
            }
            self.assertEqual(null_test_status["geometry_shuffle_collapse"], "pass")
            self.assertEqual(null_test_status["stronger_baseline_survival"], "pass")
            self.assertEqual(null_test_status["seed_stability"], "pass")

            group_ids = [item["group_id"] for item in first["comparison_group_catalog"]]
            self.assertIn("matched_surface_wave_vs_p0__intact", group_ids)
            self.assertIn("geometry_ablation__p0", group_ids)
            self.assertIn("baseline_strength_challenge__intact", group_ids)

            decision_panel = first["milestone_1_decision_panel"]
            self.assertEqual(decision_panel["overall_status"], "pass")
            self.assertEqual(
                [item["status"] for item in decision_panel["decision_items"]],
                ["pass", "pass", "pass", "pass"],
            )

    def test_fixture_workflow_packages_analysis_bundle_with_ui_payload_and_phase_map_refs(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _materialize_experiment_comparison_fixture(tmp_dir)

            result = execute_experiment_comparison_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )

            packaged = result["packaged_analysis_bundle"]
            metadata_path = Path(packaged["metadata_path"]).resolve()
            metadata = load_experiment_analysis_bundle_metadata(metadata_path)
            discovered_paths = discover_experiment_analysis_bundle_paths(metadata)

            self.assertTrue(metadata_path.exists())
            self.assertEqual(
                discovered_paths[ANALYSIS_UI_PAYLOAD_ARTIFACT_ID],
                Path(packaged["analysis_ui_payload_path"]).resolve(),
            )
            self.assertEqual(
                discovered_paths[COMPARISON_MATRICES_ARTIFACT_ID],
                Path(packaged["comparison_matrices_path"]).resolve(),
            )
            self.assertEqual(
                discovered_paths[VISUALIZATION_CATALOG_ARTIFACT_ID],
                Path(packaged["visualization_catalog_path"]).resolve(),
            )
            self.assertEqual(
                discovered_paths[OFFLINE_REPORT_INDEX_ARTIFACT_ID],
                Path(packaged["report_path"]).resolve(),
            )
            self.assertEqual(
                discovered_paths[OFFLINE_REPORT_SUMMARY_ARTIFACT_ID],
                Path(packaged["report_summary_path"]).resolve(),
            )

            ui_payload = json.loads(
                Path(packaged["analysis_ui_payload_path"]).read_text(encoding="utf-8")
            )
            self.assertIn("task_summary_cards", ui_payload)
            self.assertIn("comparison_cards", ui_payload)
            self.assertIn("analysis_visualizations", ui_payload)
            self.assertGreater(len(ui_payload["task_summary_cards"]), 0)
            self.assertTrue(
                any(
                    item["output_id"] == "null_direction_suppression_comparison"
                    for item in ui_payload["comparison_cards"]
                )
            )
            self.assertEqual(
                ui_payload["shared_comparison"]["milestone_1_decision_panel"][
                    "overall_status"
                ],
                "pass",
            )

            visualization_catalog = json.loads(
                Path(packaged["visualization_catalog_path"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertGreater(len(visualization_catalog["phase_map_references"]), 0)
            self.assertEqual(
                visualization_catalog["offline_report"]["summary_path"],
                packaged["report_summary_path"],
            )

            report_html = Path(packaged["report_path"]).read_text(encoding="utf-8")
            self.assertIn("Task Summary Cards", report_html)
            self.assertIn("Null Tests", report_html)
            self.assertIn("null_direction_suppression_comparison", report_html)

    def test_packaged_analysis_bundle_can_regenerate_report_from_local_artifacts_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _materialize_experiment_comparison_fixture(tmp_dir)

            result = execute_experiment_comparison_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )
            packaged = result["packaged_analysis_bundle"]

            regenerated = generate_experiment_analysis_report(
                analysis_bundle_metadata_path=packaged["metadata_path"],
                output_dir=tmp_dir / "regenerated_analysis_report",
            )

            self.assertEqual(
                regenerated["bundle_id"],
                packaged["bundle_reference"]["bundle_id"],
            )
            self.assertTrue(Path(regenerated["report_path"]).exists())
            self.assertTrue(Path(regenerated["summary_path"]).exists())
            self.assertIn("no local server is required", regenerated["viewer_open_hint"])
            regenerated_html = Path(regenerated["report_path"]).read_text(
                encoding="utf-8"
            )
            self.assertIn("Milestone 12 Experiment Analysis Bundle", regenerated_html)
            self.assertIn("Wave Diagnostics", regenerated_html)

    def test_workflow_ignores_stray_bundle_metadata_copies_under_arm_directories(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _materialize_experiment_comparison_fixture(tmp_dir)

            canonical_metadata_path = Path(
                fixture["bundle_metadata_records"][0]["metadata_path"]
            ).resolve()
            stray_metadata_path = (
                canonical_metadata_path.parents[1]
                / "stale_duplicate_copy"
                / "simulator_result_bundle.json"
            ).resolve()
            stray_metadata_path.parent.mkdir(parents=True, exist_ok=True)
            stray_metadata_path.write_text(
                canonical_metadata_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            result = execute_experiment_comparison_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )

            self.assertEqual(len(result["bundle_set"]["bundle_inventory"]), 48)

    def test_workflow_fails_clearly_for_missing_condition_coverage(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _materialize_experiment_comparison_fixture(tmp_dir)
            missing_bundle_path = next(
                item["metadata_path"]
                for item in fixture["bundle_metadata_records"]
                if item["arm_id"] == "baseline_p0_intact"
                and item["seed"] == 17
                and item["condition_ids"] == ["null_direction", "off_polarity"]
            )
            missing_bundle_path.unlink()

            with self.assertRaises(ValueError) as ctx:
                execute_experiment_comparison_workflow(
                    manifest_path=fixture["manifest_path"],
                    config_path=fixture["config_path"],
                    schema_path=fixture["schema_path"],
                    design_lock_path=fixture["design_lock_path"],
                )

            self.assertIn("missing required condition coverage", str(ctx.exception))

    def test_workflow_fails_clearly_for_incomplete_seed_coverage(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _materialize_experiment_comparison_fixture(tmp_dir)
            for item in fixture["bundle_metadata_records"]:
                if item["arm_id"] == "surface_wave_intact" and item["seed"] == 17:
                    item["metadata_path"].unlink()

            with self.assertRaises(ValueError) as ctx:
                execute_experiment_comparison_workflow(
                    manifest_path=fixture["manifest_path"],
                    config_path=fixture["config_path"],
                    schema_path=fixture["schema_path"],
                    design_lock_path=fixture["design_lock_path"],
                )

            message = str(ctx.exception)
            self.assertIn("missing required condition coverage", message)
            self.assertIn("surface_wave_intact", message)
            self.assertIn("17", message)

    def test_workflow_fails_clearly_for_incompatible_readout_inventory(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _materialize_experiment_comparison_fixture(tmp_dir)
            config_payload = yaml.safe_load(
                fixture["config_path"].read_text(encoding="utf-8")
            )
            config_payload["simulation"]["readout_catalog"][0]["units"] = "arb_units"
            fixture["config_path"].write_text(
                yaml.safe_dump(config_payload, sort_keys=False),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError) as ctx:
                execute_experiment_comparison_workflow(
                    manifest_path=fixture["manifest_path"],
                    config_path=fixture["config_path"],
                    schema_path=fixture["schema_path"],
                    design_lock_path=fixture["design_lock_path"],
                )

            message = str(ctx.exception)
            self.assertIn("incompatible units", message)
            self.assertIn("shared_output_mean", message)

    def test_workflow_accepts_equivalent_config_materialized_at_a_different_path(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _materialize_experiment_comparison_fixture(tmp_dir)
            relocated_config_path = tmp_dir / "relocated_simulation_config.yaml"
            relocated_config_path.write_text(
                fixture["config_path"].read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            result = execute_experiment_comparison_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=relocated_config_path,
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )

            self.assertEqual(
                result["summary_version"],
                EXPERIMENT_COMPARISON_SUMMARY_VERSION,
            )
            self.assertGreater(len(result["bundle_set"]["bundle_inventory"]), 0)

    def test_workflow_accepts_pre_resolved_simulation_plan_without_replanning(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _materialize_experiment_comparison_fixture(tmp_dir)
            simulation_plan = resolve_manifest_simulation_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )

            with mock.patch(
                "flywire_wave.experiment_comparison_analysis.resolve_manifest_simulation_plan",
                side_effect=AssertionError("unexpected simulation plan re-resolution"),
            ), mock.patch(
                "flywire_wave.experiment_comparison_analysis.resolve_manifest_readout_analysis_plan",
                side_effect=AssertionError("unexpected readout analysis re-resolution"),
            ):
                result = execute_experiment_comparison_workflow(
                    manifest_path=fixture["manifest_path"],
                    config_path=fixture["config_path"],
                    schema_path=fixture["schema_path"],
                    design_lock_path=fixture["design_lock_path"],
                    simulation_plan=simulation_plan,
                )

            self.assertEqual(
                result["summary_version"],
                EXPERIMENT_COMPARISON_SUMMARY_VERSION,
            )


def _materialize_experiment_comparison_fixture(tmp_dir: Path) -> dict[str, Any]:
    schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
    design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"
    manifest_path = _write_manifest_fixture(
        tmp_dir,
        manifest_overrides={
            "seed_sweep": [11, 17],
        },
    )
    config_path = _write_simulation_fixture(
        tmp_dir,
        timebase_dt_ms=10.0,
        timebase_sample_count=7,
        analysis_config={
            "analysis_windows": {
                "shared_response_window": {
                    "start_ms": 10.0,
                    "end_ms": 60.0,
                    "description": "Fixture shared-response window.",
                },
                "task_decoder_window": {
                    "start_ms": 10.0,
                    "end_ms": 60.0,
                    "description": "Fixture task-decoder window.",
                },
                "wave_diagnostic_window": {
                    "start_ms": 10.0,
                    "end_ms": 60.0,
                    "description": "Fixture wave-diagnostic window.",
                },
            }
        },
    )
    _record_fixture_stimulus_bundle(
        manifest_path=manifest_path,
        processed_stimulus_dir=tmp_dir / "out" / "stimuli",
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    simulation_plan = resolve_manifest_simulation_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
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
    bundle_metadata_paths = _materialize_simulator_bundles(
        run_plans=run_plans,
        condition_stimuli=condition_stimuli,
    )
    return {
        "manifest_path": manifest_path,
        "config_path": config_path,
        "schema_path": schema_path,
        "design_lock_path": design_lock_path,
        "bundle_metadata_records": bundle_metadata_paths,
    }


def _load_default_stimulus_metadata(
    simulation_plan: Mapping[str, Any],
) -> dict[str, Any]:
    arm_plan = simulation_plan["arm_plans"][0]
    input_asset = next(
        item
        for item in arm_plan["selected_assets"]
        if str(item["asset_role"]) == "input_bundle"
        and str(item["artifact_type"]) == "stimulus_bundle"
    )
    return load_stimulus_bundle_metadata(Path(input_asset["path"]))


def _materialize_condition_stimuli(
    *,
    processed_stimulus_dir: Path,
    analysis_plan: Mapping[str, Any],
    default_stimulus_metadata: Mapping[str, Any],
) -> dict[tuple[str, ...], dict[str, Any]]:
    conditions_by_parameter: dict[str, list[dict[str, Any]]] = {}
    for item in analysis_plan["condition_catalog"]:
        conditions_by_parameter.setdefault(str(item["parameter_name"]), []).append(
            copy.deepcopy(dict(item))
        )
    for values in conditions_by_parameter.values():
        values.sort(key=lambda item: str(item["condition_id"]))

    combos: list[list[dict[str, Any]]] = [[]]
    for parameter_name in sorted(conditions_by_parameter):
        next_combos: list[list[dict[str, Any]]] = []
        for prefix in combos:
            for item in conditions_by_parameter[parameter_name]:
                next_combos.append([*prefix, copy.deepcopy(dict(item))])
        combos = next_combos

    metadata_by_signature: dict[tuple[str, ...], dict[str, Any]] = {}
    for combo in combos:
        condition_ids = tuple(sorted(str(item["condition_id"]) for item in combo))
        parameter_snapshot = copy.deepcopy(
            dict(default_stimulus_metadata["parameter_snapshot"])
        )
        for item in combo:
            parameter_snapshot[str(item["parameter_name"])] = copy.deepcopy(item["value"])
        stimulus_metadata = build_stimulus_bundle_metadata(
            stimulus_family=str(default_stimulus_metadata["stimulus_family"]),
            stimulus_name=str(default_stimulus_metadata["stimulus_name"]),
            parameter_snapshot=parameter_snapshot,
            seed=int(default_stimulus_metadata["determinism"]["seed"]),
            temporal_sampling=default_stimulus_metadata["temporal_sampling"],
            spatial_frame=default_stimulus_metadata["spatial_frame"],
            processed_stimulus_dir=processed_stimulus_dir,
            luminance_convention=default_stimulus_metadata["luminance_convention"],
            representation_family=str(default_stimulus_metadata["representation_family"]),
            rng_family=str(default_stimulus_metadata["determinism"]["rng_family"]),
        )
        write_stimulus_bundle_metadata(stimulus_metadata)
        metadata_by_signature[condition_ids] = stimulus_metadata
    return metadata_by_signature


def _materialize_simulator_bundles(
    *,
    run_plans: list[dict[str, Any]],
    condition_stimuli: Mapping[tuple[str, ...], Mapping[str, Any]],
) -> list[dict[str, Any]]:
    metadata_paths: list[dict[str, Any]] = []
    for run_plan in run_plans:
        for condition_ids, stimulus_metadata in condition_stimuli.items():
            selected_assets = _replace_input_bundle_asset(
                run_plan["selected_assets"],
                stimulus_metadata,
            )
            bundle_metadata = build_simulator_result_bundle_metadata(
                manifest_reference=run_plan["manifest_reference"],
                arm_reference=run_plan["arm_reference"],
                determinism=run_plan["determinism"],
                timebase=run_plan["runtime"]["timebase"],
                selected_assets=selected_assets,
                readout_catalog=run_plan["runtime"]["shared_readout_catalog"],
                processed_simulator_results_dir=run_plan["runtime"][
                    "processed_simulator_results_dir"
                ],
                state_summary_status="ready",
                readout_traces_status="ready",
                metrics_table_status="ready",
            )
            if str(run_plan["arm_reference"]["model_mode"]) == "surface_wave":
                bundle_paths = build_simulator_result_bundle_paths(
                    experiment_id=str(run_plan["manifest_reference"]["experiment_id"]),
                    arm_id=str(run_plan["arm_reference"]["arm_id"]),
                    run_spec_hash=str(bundle_metadata["run_spec_hash"]),
                    processed_simulator_results_dir=run_plan["runtime"][
                        "processed_simulator_results_dir"
                    ],
                )
                model_artifacts = [
                    build_simulator_extension_artifact_record(
                        bundle_paths=bundle_paths,
                        artifact_id="surface_wave_summary",
                        file_name="surface_wave_summary.json",
                        format="json_surface_wave_execution_summary.v1",
                        status="ready",
                        artifact_scope="wave_model_extension",
                        description="Fixture packaged surface-wave summary.",
                    ),
                    build_simulator_extension_artifact_record(
                        bundle_paths=bundle_paths,
                        artifact_id="surface_wave_phase_map",
                        file_name="surface_wave_phase_map.npz",
                        format="npz_surface_wave_phase_map.v1",
                        status="ready",
                        artifact_scope="wave_model_extension",
                        description="Fixture phase-map export for analysis packaging tests.",
                    ),
                ]
                bundle_metadata = build_simulator_result_bundle_metadata(
                    manifest_reference=run_plan["manifest_reference"],
                    arm_reference=run_plan["arm_reference"],
                    determinism=run_plan["determinism"],
                    timebase=run_plan["runtime"]["timebase"],
                    selected_assets=selected_assets,
                    readout_catalog=run_plan["runtime"]["shared_readout_catalog"],
                    processed_simulator_results_dir=run_plan["runtime"][
                        "processed_simulator_results_dir"
                    ],
                    state_summary_status="ready",
                    readout_traces_status="ready",
                    metrics_table_status="ready",
                    model_artifacts=model_artifacts,
                )
            metadata_path = write_simulator_result_bundle_metadata(bundle_metadata)
            _write_bundle_artifacts(
                bundle_metadata=bundle_metadata,
                trace_values=_bundle_trace_values(
                    arm_id=str(run_plan["arm_reference"]["arm_id"]),
                    seed=int(run_plan["determinism"]["seed"]),
                    condition_ids=condition_ids,
                ),
            )
            metadata_paths.append(
                {
                    "metadata_path": metadata_path,
                    "arm_id": str(run_plan["arm_reference"]["arm_id"]),
                    "seed": int(run_plan["determinism"]["seed"]),
                    "condition_ids": list(condition_ids),
                }
            )
    return metadata_paths


def _replace_input_bundle_asset(
    selected_assets: list[dict[str, Any]],
    stimulus_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    replaced: list[dict[str, Any]] = []
    for item in selected_assets:
        if (
            str(item["asset_role"]) == "input_bundle"
            and str(item["artifact_type"]) == "stimulus_bundle"
        ):
            replaced.append(
                build_selected_asset_reference(
                    asset_role=str(item["asset_role"]),
                    artifact_type="stimulus_bundle",
                    path=Path(stimulus_metadata["assets"]["metadata_json"]["path"]),
                    contract_version=str(stimulus_metadata["contract_version"]),
                    artifact_id=item.get("artifact_id"),
                    bundle_id=str(stimulus_metadata["bundle_id"]),
                )
            )
            continue
        replaced.append(copy.deepcopy(dict(item)))
    return replaced


def _write_bundle_artifacts(
    *,
    bundle_metadata: Mapping[str, Any],
    trace_values: np.ndarray,
) -> None:
    artifacts = bundle_metadata["artifacts"]
    timebase = bundle_metadata["timebase"]
    sample_count = int(timebase["sample_count"])
    dt_ms = float(timebase["dt_ms"])
    time_origin_ms = float(timebase["time_origin_ms"])
    time_ms = np.asarray(
        [time_origin_ms + index * dt_ms for index in range(sample_count)],
        dtype=np.float64,
    )
    readout_ids = np.asarray(
        [str(item["readout_id"]) for item in bundle_metadata["readout_catalog"]],
        dtype="<U64",
    )
    if trace_values.shape != (sample_count, len(readout_ids)):
        raise ValueError(
            f"trace_values must have shape {(sample_count, len(readout_ids))!r}, "
            f"got {trace_values.shape!r}."
        )
    state_summary_path = Path(artifacts[STATE_SUMMARY_KEY]["path"]).resolve()
    metrics_path = Path(artifacts[METRICS_TABLE_KEY]["path"]).resolve()
    readout_path = Path(artifacts[READOUT_TRACES_KEY]["path"]).resolve()
    write_json([], state_summary_path)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        "metric_id,readout_id,scope,window_id,statistic,value,units\n",
        encoding="utf-8",
    )
    write_deterministic_npz(
        {
            "time_ms": time_ms,
            "readout_ids": readout_ids,
            "values": np.asarray(trace_values, dtype=np.float64),
        },
        readout_path,
    )
    model_artifacts = {
        str(item["artifact_id"]): dict(item)
        for item in bundle_metadata["artifacts"].get("model_artifacts", [])
    }
    if "surface_wave_summary" in model_artifacts:
        write_json(
            {
                "format_version": "json_surface_wave_execution_summary.v1",
                "runtime_metadata_by_root": [
                    {
                        "root_id": 101,
                        "morphology_class": "surface_neuron",
                        "patch_count": 2,
                        "source_reference": {},
                    }
                ],
                "wave_specific_artifacts": {
                    "phase_map_artifact_id": "surface_wave_phase_map",
                },
            },
            Path(model_artifacts["surface_wave_summary"]["path"]).resolve(),
        )
    if "surface_wave_phase_map" in model_artifacts:
        phase_values = np.asarray(
            [
                [0.0, 0.4],
                [0.2, 0.6],
                [0.4, 0.8],
                [0.6, 1.0],
                [0.8, 1.2],
                [1.0, 1.4],
                [1.2, 1.6],
            ],
            dtype=np.float64,
        )
        write_deterministic_npz(
            {
                "substep_time_ms": time_ms,
                "root_ids": np.asarray([101], dtype=np.int64),
                "root_101_phase_rad": phase_values[:sample_count],
            },
            Path(model_artifacts["surface_wave_phase_map"]["path"]).resolve(),
        )


def _bundle_trace_values(
    *,
    arm_id: str,
    seed: int,
    condition_ids: tuple[str, ...],
) -> np.ndarray:
    base_peak_by_condition = {
        ("null_direction", "off_polarity"): 1.5,
        ("null_direction", "on_polarity"): 2.4,
        ("off_polarity", "preferred_direction"): 3.5,
        ("on_polarity", "preferred_direction"): 5.0,
    }
    arm_adjustments = {
        "baseline_p0_intact": {"preferred_delta": 0.0, "null_delta": 0.0, "peak_index": 2},
        "baseline_p0_shuffled": {"preferred_delta": 0.0, "null_delta": 0.0, "peak_index": 2},
        "surface_wave_intact": {"preferred_delta": 1.4, "null_delta": -1.0, "peak_index": 1},
        "surface_wave_shuffled": {"preferred_delta": 0.6, "null_delta": -0.3, "peak_index": 2},
        "baseline_p1_intact": {"preferred_delta": 0.6, "null_delta": -0.5, "peak_index": 2},
        "baseline_p1_shuffled": {"preferred_delta": 0.4, "null_delta": -0.2, "peak_index": 2},
    }
    normalized_condition_ids = tuple(sorted(condition_ids))
    base_peak = float(base_peak_by_condition[normalized_condition_ids])
    adjustment = arm_adjustments[arm_id]
    is_preferred = "preferred_direction" in set(normalized_condition_ids)
    adjusted_peak = base_peak + (
        float(adjustment["preferred_delta"]) if is_preferred else float(adjustment["null_delta"])
    )
    seed_offset = 0.1 if int(seed) == 17 else 0.0
    response = _response_profile(
        peak=max(0.5, adjusted_peak + seed_offset),
        peak_index=int(adjustment["peak_index"]),
    )
    values = np.asarray([2.0, *[2.0 + value for value in response]], dtype=np.float64)
    return values.reshape(-1, 1)


def _response_profile(*, peak: float, peak_index: int) -> list[float]:
    if peak_index == 1:
        return [0.0, peak, peak * 0.55, peak * 0.2, peak * 0.05, 0.0]
    if peak_index == 2:
        return [0.0, peak * 0.2, peak, peak * 0.55, peak * 0.12, 0.0]
    raise ValueError(f"Unsupported peak_index {peak_index!r}.")


if __name__ == "__main__":
    unittest.main()
