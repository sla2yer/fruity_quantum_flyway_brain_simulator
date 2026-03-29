from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.coupling_assembly import (
    ANCHOR_COLUMN_TYPES,
    CLOUD_COLUMN_TYPES,
    COMPONENT_COLUMN_TYPES,
    COMPONENT_SYNAPSE_COLUMN_TYPES,
    EdgeCouplingBundle,
)
from flywire_wave.coupling_contract import (
    DEFAULT_AGGREGATION_RULE,
    DEFAULT_DELAY_REPRESENTATION,
    DEFAULT_SIGN_REPRESENTATION,
    DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
    SEPARABLE_RANK_ONE_CLOUD_KERNEL,
    SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
    SURFACE_PATCH_CLOUD_MODE,
)
from flywire_wave.io_utils import write_deterministic_npz, write_json
from flywire_wave.simulation_planning import (
    discover_simulation_run_plans,
    resolve_manifest_readout_analysis_plan,
    resolve_manifest_simulation_plan,
)
from flywire_wave.simulator_result_contract import (
    METRICS_TABLE_KEY,
    READOUT_TRACES_KEY,
    STATE_SUMMARY_KEY,
    build_selected_asset_reference,
    build_simulator_arm_reference,
    build_simulator_manifest_reference,
    build_simulator_readout_definition,
    build_simulator_result_bundle_metadata,
    write_simulator_result_bundle_metadata,
)
from flywire_wave.stimulus_contract import (
    build_stimulus_bundle_metadata,
    load_stimulus_bundle_metadata,
    write_stimulus_bundle_metadata,
)
from flywire_wave.synapse_mapping import (
    EDGE_BUNDLE_COLUMN_TYPES,
    _write_edge_coupling_bundle_npz,
)
from flywire_wave.validation_circuit import (
    AggregationValidationCase,
    DelayValidationCase,
    MotionPathwayAsymmetryCase,
    SignValidationCase,
    execute_circuit_validation_workflow,
    run_circuit_validation_suite,
)

try:
    from test_simulation_planning import (
        _record_fixture_stimulus_bundle,
        _write_manifest_fixture,
        _write_simulation_fixture,
    )
except ModuleNotFoundError:
    from tests.test_simulation_planning import (
        _record_fixture_stimulus_bundle,
        _write_manifest_fixture,
        _write_simulation_fixture,
    )


FIXTURE_TIMEBASE = {
    "time_origin_ms": 0.0,
    "dt_ms": 10.0,
    "duration_ms": 70.0,
    "sample_count": 7,
}
FIXTURE_TIME_MS = np.asarray([0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0], dtype=np.float64)


class CircuitValidationSuiteTest(unittest.TestCase):
    def test_fixture_suite_emits_pass_and_fail_findings_for_delay_sign_aggregation_and_motion(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            simulator_results_dir = tmp_dir / "simulator_results"

            delay_edge_path = tmp_dir / "edges" / "delay_edge.npz"
            inhibitory_edge_path = tmp_dir / "edges" / "inhibitory_edge.npz"
            aggregation_edge_a_path = tmp_dir / "edges" / "aggregation_a.npz"
            aggregation_edge_b_path = tmp_dir / "edges" / "aggregation_b.npz"
            _write_fixture_edge_bundle(
                delay_edge_path,
                pre_root_id=101,
                post_root_id=202,
                signed_weight_total=1.0,
                delay_ms=2.0,
                sign_label="excitatory",
            )
            _write_fixture_edge_bundle(
                inhibitory_edge_path,
                pre_root_id=303,
                post_root_id=404,
                signed_weight_total=-1.0,
                delay_ms=0.0,
                sign_label="inhibitory",
            )
            _write_fixture_edge_bundle(
                aggregation_edge_a_path,
                pre_root_id=501,
                post_root_id=601,
                signed_weight_total=1.0,
                delay_ms=0.0,
                sign_label="excitatory",
            )
            _write_fixture_edge_bundle(
                aggregation_edge_b_path,
                pre_root_id=502,
                post_root_id=601,
                signed_weight_total=1.5,
                delay_ms=0.0,
                sign_label="excitatory",
            )

            probe_plan = _build_probe_analysis_plan(["probe_pulse"])
            aggregation_plan = _build_probe_analysis_plan(
                ["input_a", "input_b", "input_ab"]
            )
            motion_plan = _build_motion_analysis_plan("preferred_pathway_output")

            delay_pass_record = _build_inline_bundle_record(
                tmp_dir,
                asset_suffix="delay_pass",
                condition_ids=["probe_pulse"],
                readout_traces={
                    "source_readout": [2.0, 2.0, 4.5, 3.0, 2.2, 2.0, 2.0],
                    "target_readout": [2.0, 2.0, 2.1, 2.4, 5.0, 2.6, 2.0],
                },
                arm_id="delay_pass_arm",
                stimulus_family="translated_edge",
                stimulus_name="simple_translated_edge",
            )
            delay_fail_record = _build_inline_bundle_record(
                tmp_dir,
                asset_suffix="delay_fail",
                condition_ids=["probe_pulse"],
                readout_traces={
                    "source_readout": [2.0, 2.0, 4.5, 3.0, 2.2, 2.0, 2.0],
                    "target_readout": [2.0, 2.0, 4.0, 2.6, 2.2, 2.0, 2.0],
                },
                arm_id="delay_fail_arm",
                stimulus_family="translated_edge",
                stimulus_name="simple_translated_edge",
            )
            sign_pass_record = _build_inline_bundle_record(
                tmp_dir,
                asset_suffix="sign_pass",
                condition_ids=["probe_pulse"],
                readout_traces={
                    "target_readout": [2.0, 2.0, 1.7, 0.8, 1.4, 1.9, 2.0],
                },
                arm_id="sign_pass_arm",
                stimulus_family="translated_edge",
                stimulus_name="simple_translated_edge",
            )
            sign_fail_record = _build_inline_bundle_record(
                tmp_dir,
                asset_suffix="sign_fail",
                condition_ids=["probe_pulse"],
                readout_traces={
                    "target_readout": [2.0, 2.0, 2.3, 3.2, 2.4, 2.0, 2.0],
                },
                arm_id="sign_fail_arm",
                stimulus_family="translated_edge",
                stimulus_name="simple_translated_edge",
            )

            aggregation_pass_records = [
                _build_inline_bundle_record(
                    tmp_dir,
                    asset_suffix="aggregation_pass_a",
                    condition_ids=["input_a"],
                    readout_traces={"target_readout": [2.0, 2.0, 3.0, 2.4, 2.1, 2.0, 2.0]},
                    arm_id="aggregation_pass_arm",
                    stimulus_family="translated_edge",
                    stimulus_name="simple_translated_edge",
                ),
                _build_inline_bundle_record(
                    tmp_dir,
                    asset_suffix="aggregation_pass_b",
                    condition_ids=["input_b"],
                    readout_traces={"target_readout": [2.0, 2.0, 3.5, 2.6, 2.1, 2.0, 2.0]},
                    arm_id="aggregation_pass_arm",
                    stimulus_family="translated_edge",
                    stimulus_name="simple_translated_edge",
                ),
                _build_inline_bundle_record(
                    tmp_dir,
                    asset_suffix="aggregation_pass_ab",
                    condition_ids=["input_ab"],
                    readout_traces={"target_readout": [2.0, 2.0, 4.3, 3.0, 2.2, 2.0, 2.0]},
                    arm_id="aggregation_pass_arm",
                    stimulus_family="translated_edge",
                    stimulus_name="simple_translated_edge",
                ),
            ]
            aggregation_fail_records = [
                _build_inline_bundle_record(
                    tmp_dir,
                    asset_suffix="aggregation_fail_a",
                    condition_ids=["input_a"],
                    readout_traces={"target_readout": [2.0, 2.0, 3.0, 2.4, 2.1, 2.0, 2.0]},
                    arm_id="aggregation_fail_arm",
                    stimulus_family="translated_edge",
                    stimulus_name="simple_translated_edge",
                ),
                _build_inline_bundle_record(
                    tmp_dir,
                    asset_suffix="aggregation_fail_b",
                    condition_ids=["input_b"],
                    readout_traces={"target_readout": [2.0, 2.0, 3.5, 2.6, 2.1, 2.0, 2.0]},
                    arm_id="aggregation_fail_arm",
                    stimulus_family="translated_edge",
                    stimulus_name="simple_translated_edge",
                ),
                _build_inline_bundle_record(
                    tmp_dir,
                    asset_suffix="aggregation_fail_ab",
                    condition_ids=["input_ab"],
                    readout_traces={"target_readout": [2.0, 2.0, 2.6, 2.2, 2.1, 2.0, 2.0]},
                    arm_id="aggregation_fail_arm",
                    stimulus_family="translated_edge",
                    stimulus_name="simple_translated_edge",
                ),
            ]
            motion_records = [
                _build_inline_bundle_record(
                    tmp_dir,
                    asset_suffix="motion_preferred",
                    condition_ids=["preferred_direction"],
                    readout_traces={
                        "preferred_pathway_output": [2.0, 2.0, 6.0, 3.8, 2.4, 2.0, 2.0],
                    },
                    arm_id="motion_arm",
                    stimulus_family="moving_edge",
                    stimulus_name="simple_moving_edge",
                ),
                _build_inline_bundle_record(
                    tmp_dir,
                    asset_suffix="motion_null",
                    condition_ids=["null_direction"],
                    readout_traces={
                        "preferred_pathway_output": [2.0, 2.0, 2.8, 4.0, 2.6, 2.1, 2.0],
                    },
                    arm_id="motion_arm",
                    stimulus_family="moving_edge",
                    stimulus_name="simple_moving_edge",
                ),
            ]

            first = run_circuit_validation_suite(
                delay_cases=[
                    DelayValidationCase(
                        case_id="delay_pass_case",
                        motif_id="feedforward_delay_probe",
                        analysis_plan=probe_plan,
                        bundle_records=[delay_pass_record],
                        source_readout_id="source_readout",
                        target_readout_id="target_readout",
                        edge_bundle_paths=[delay_edge_path],
                    ),
                    DelayValidationCase(
                        case_id="delay_fail_case",
                        motif_id="feedforward_delay_probe",
                        analysis_plan=probe_plan,
                        bundle_records=[delay_fail_record],
                        source_readout_id="source_readout",
                        target_readout_id="target_readout",
                        edge_bundle_paths=[delay_edge_path],
                    ),
                ],
                sign_cases=[
                    SignValidationCase(
                        case_id="sign_pass_case",
                        motif_id="inhibitory_sign_probe",
                        analysis_plan=probe_plan,
                        bundle_records=[sign_pass_record],
                        target_readout_id="target_readout",
                        edge_bundle_paths=[inhibitory_edge_path],
                    ),
                    SignValidationCase(
                        case_id="sign_fail_case",
                        motif_id="inhibitory_sign_probe",
                        analysis_plan=probe_plan,
                        bundle_records=[sign_fail_record],
                        target_readout_id="target_readout",
                        edge_bundle_paths=[inhibitory_edge_path],
                    ),
                ],
                aggregation_cases=[
                    AggregationValidationCase(
                        case_id="aggregation_pass_case",
                        motif_id="two_input_sum_probe",
                        analysis_plan=aggregation_plan,
                        bundle_records=aggregation_pass_records,
                        target_readout_id="target_readout",
                        edge_bundle_paths=[aggregation_edge_a_path, aggregation_edge_b_path],
                        single_condition_sets={
                            "input_a": ["input_a"],
                            "input_b": ["input_b"],
                        },
                        combined_condition_ids=["input_ab"],
                    ),
                    AggregationValidationCase(
                        case_id="aggregation_fail_case",
                        motif_id="two_input_sum_probe",
                        analysis_plan=aggregation_plan,
                        bundle_records=aggregation_fail_records,
                        target_readout_id="target_readout",
                        edge_bundle_paths=[aggregation_edge_a_path, aggregation_edge_b_path],
                        single_condition_sets={
                            "input_a": ["input_a"],
                            "input_b": ["input_b"],
                        },
                        combined_condition_ids=["input_ab"],
                    ),
                ],
                motion_cases=[
                    MotionPathwayAsymmetryCase(
                        case_id="motion_asymmetry_case",
                        pathway_id="preferred_pathway_output",
                        analysis_plan=motion_plan,
                        bundle_records=motion_records,
                        readout_id="preferred_pathway_output",
                    )
                ],
                processed_simulator_results_dir=simulator_results_dir,
                experiment_id="fixture_circuit_suite",
            )
            second = run_circuit_validation_suite(
                delay_cases=[
                    DelayValidationCase(
                        case_id="delay_pass_case",
                        motif_id="feedforward_delay_probe",
                        analysis_plan=probe_plan,
                        bundle_records=[delay_pass_record],
                        source_readout_id="source_readout",
                        target_readout_id="target_readout",
                        edge_bundle_paths=[delay_edge_path],
                    ),
                    DelayValidationCase(
                        case_id="delay_fail_case",
                        motif_id="feedforward_delay_probe",
                        analysis_plan=probe_plan,
                        bundle_records=[delay_fail_record],
                        source_readout_id="source_readout",
                        target_readout_id="target_readout",
                        edge_bundle_paths=[delay_edge_path],
                    ),
                ],
                sign_cases=[
                    SignValidationCase(
                        case_id="sign_pass_case",
                        motif_id="inhibitory_sign_probe",
                        analysis_plan=probe_plan,
                        bundle_records=[sign_pass_record],
                        target_readout_id="target_readout",
                        edge_bundle_paths=[inhibitory_edge_path],
                    ),
                    SignValidationCase(
                        case_id="sign_fail_case",
                        motif_id="inhibitory_sign_probe",
                        analysis_plan=probe_plan,
                        bundle_records=[sign_fail_record],
                        target_readout_id="target_readout",
                        edge_bundle_paths=[inhibitory_edge_path],
                    ),
                ],
                aggregation_cases=[
                    AggregationValidationCase(
                        case_id="aggregation_pass_case",
                        motif_id="two_input_sum_probe",
                        analysis_plan=aggregation_plan,
                        bundle_records=aggregation_pass_records,
                        target_readout_id="target_readout",
                        edge_bundle_paths=[aggregation_edge_a_path, aggregation_edge_b_path],
                        single_condition_sets={
                            "input_a": ["input_a"],
                            "input_b": ["input_b"],
                        },
                        combined_condition_ids=["input_ab"],
                    ),
                    AggregationValidationCase(
                        case_id="aggregation_fail_case",
                        motif_id="two_input_sum_probe",
                        analysis_plan=aggregation_plan,
                        bundle_records=aggregation_fail_records,
                        target_readout_id="target_readout",
                        edge_bundle_paths=[aggregation_edge_a_path, aggregation_edge_b_path],
                        single_condition_sets={
                            "input_a": ["input_a"],
                            "input_b": ["input_b"],
                        },
                        combined_condition_ids=["input_ab"],
                    ),
                ],
                motion_cases=[
                    MotionPathwayAsymmetryCase(
                        case_id="motion_asymmetry_case",
                        pathway_id="preferred_pathway_output",
                        analysis_plan=motion_plan,
                        bundle_records=motion_records,
                        readout_id="preferred_pathway_output",
                    )
                ],
                processed_simulator_results_dir=simulator_results_dir,
                experiment_id="fixture_circuit_suite",
            )

            self.assertEqual(first["bundle_id"], second["bundle_id"])
            self.assertEqual(first["summary_path"], second["summary_path"])
            self.assertEqual(first["findings_path"], second["findings_path"])
            self.assertEqual(first["overall_status"], "blocking")
            self.assertEqual(
                first["validator_statuses"],
                {
                    "coupling_semantics_continuity": "blocking",
                    "motion_pathway_asymmetry": "pass",
                },
            )

            summary_path = Path(first["summary_path"]).resolve()
            findings_path = Path(first["findings_path"]).resolve()
            report_path = Path(first["report_path"]).resolve()
            self.assertTrue(summary_path.exists())
            self.assertTrue(findings_path.exists())
            self.assertTrue(report_path.exists())
            self.assertEqual(summary_path.read_bytes(), Path(second["summary_path"]).read_bytes())
            self.assertEqual(findings_path.read_bytes(), Path(second["findings_path"]).read_bytes())

            findings_payload = json.loads(findings_path.read_text(encoding="utf-8"))
            findings = _flatten_validator_findings(findings_payload["validator_findings"])
            finding_by_id = {
                item["finding_id"]: item
                for item in findings
            }

            self.assertEqual(
                finding_by_id[
                    "coupling_semantics_continuity:delay_pass_case:fixture_circuit::delay_pass_arm::seed_11:latency_delta_vs_weighted_component_delay"
                ]["status"],
                "pass",
            )
            self.assertEqual(
                finding_by_id[
                    "coupling_semantics_continuity:delay_fail_case:fixture_circuit::delay_fail_arm::seed_11:latency_delta_vs_weighted_component_delay"
                ]["status"],
                "blocking",
            )
            self.assertEqual(
                finding_by_id[
                    "coupling_semantics_continuity:sign_pass_case:fixture_circuit::sign_pass_arm::seed_11:signed_peak_polarity"
                ]["status"],
                "pass",
            )
            self.assertEqual(
                finding_by_id[
                    "coupling_semantics_continuity:sign_fail_case:fixture_circuit::sign_fail_arm::seed_11:signed_peak_polarity"
                ]["status"],
                "blocking",
            )
            self.assertEqual(
                finding_by_id[
                    "coupling_semantics_continuity:aggregation_pass_case:fixture_circuit::aggregation_pass_arm::seed_11:combined_vs_sum_of_single_inputs"
                ]["status"],
                "pass",
            )
            self.assertEqual(
                finding_by_id[
                    "coupling_semantics_continuity:aggregation_fail_case:fixture_circuit::aggregation_fail_arm::seed_11:combined_vs_sum_of_single_inputs"
                ]["status"],
                "blocking",
            )
            self.assertEqual(
                finding_by_id[
                    "motion_pathway_asymmetry:motion_asymmetry_case:fixture_circuit::motion_arm::seed_11:direction_selectivity_index"
                ]["status"],
                "pass",
            )
            self.assertEqual(
                finding_by_id[
                    "motion_pathway_asymmetry:motion_asymmetry_case:fixture_circuit::motion_arm::seed_11:preferred_vs_null_latency"
                ]["status"],
                "pass",
            )

            delay_fail_finding = finding_by_id[
                "coupling_semantics_continuity:delay_fail_case:fixture_circuit::delay_fail_arm::seed_11:latency_delta_vs_weighted_component_delay"
            ]
            self.assertIn("expected_relationship", delay_fail_finding)
            self.assertIn("observed_relationship", delay_fail_finding)
            self.assertIn("edge_families", delay_fail_finding["provenance"])
            self.assertIn(
                "actionable_diagnostic",
                delay_fail_finding["diagnostics"],
            )

    def test_workflow_builds_motion_cases_from_local_bundles_and_writes_validation_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _materialize_circuit_workflow_fixture(tmp_dir)

            first = execute_circuit_validation_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )
            second = execute_circuit_validation_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )

            self.assertEqual(first["bundle_id"], second["bundle_id"])
            self.assertEqual(first["summary_path"], second["summary_path"])
            self.assertEqual(first["findings_path"], second["findings_path"])
            self.assertEqual(first["overall_status"], "pass")
            self.assertEqual(
                first["validator_statuses"],
                {
                    "motion_pathway_asymmetry": "pass",
                },
            )

            summary_path = Path(first["summary_path"]).resolve()
            findings_path = Path(first["findings_path"]).resolve()
            self.assertTrue(summary_path.exists())
            self.assertTrue(findings_path.exists())
            self.assertEqual(summary_path.read_bytes(), Path(second["summary_path"]).read_bytes())
            self.assertEqual(findings_path.read_bytes(), Path(second["findings_path"]).read_bytes())

            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["overall_status"], "pass")
            self.assertEqual(summary_payload["active_layer_ids"], ["circuit_sanity"])
            self.assertEqual(len(summary_payload["case_summaries"]), 2)
            self.assertEqual(
                sorted(item["case_id"] for item in summary_payload["case_summaries"]),
                [
                    "baseline_p0_intact__preferred_pathway_output",
                    "surface_wave_intact__preferred_pathway_output",
                ],
            )

            findings_payload = json.loads(findings_path.read_text(encoding="utf-8"))
            findings = _flatten_validator_findings(findings_payload["validator_findings"])
            self.assertTrue(
                all(item["status"] == "pass" for item in findings)
            )

    def test_workflow_fails_clearly_when_requested_motion_readout_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _materialize_circuit_workflow_fixture(tmp_dir)

            with self.assertRaises(ValueError) as ctx:
                execute_circuit_validation_workflow(
                    manifest_path=fixture["manifest_path"],
                    config_path=fixture["config_path"],
                    schema_path=fixture["schema_path"],
                    design_lock_path=fixture["design_lock_path"],
                    pathway_readout_ids=["missing_readout"],
                )

            self.assertIn("missing_readout", str(ctx.exception))


def _flatten_validator_findings(
    payload: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    flattened: list[dict[str, object]] = []
    for validator_id in sorted(payload):
        flattened.extend(payload[validator_id])
    return flattened


def _build_probe_analysis_plan(condition_ids: list[str]) -> dict[str, object]:
    return {
        "plan_version": "readout_analysis_plan.v1",
        "condition_catalog": [
            {
                "condition_id": condition_id,
                "display_name": condition_id.replace("_", " ").title(),
                "parameter_name": "fixture_condition",
                "value": condition_id,
            }
            for condition_id in condition_ids
        ],
        "condition_pair_catalog": [],
        "analysis_window_catalog": [
            {
                "window_id": "shared_response_window",
                "start_ms": 10.0,
                "end_ms": 60.0,
                "description": "Fixture shared-response window.",
            }
        ],
        "metric_recipe_catalog": [],
    }


def _build_motion_analysis_plan(readout_id: str) -> dict[str, object]:
    return {
        "plan_version": "readout_analysis_plan.v1",
        "condition_catalog": [
            {
                "condition_id": "preferred_direction",
                "display_name": "Preferred Direction",
                "parameter_name": "direction_deg",
                "value": 0.0,
            },
            {
                "condition_id": "null_direction",
                "display_name": "Null Direction",
                "parameter_name": "direction_deg",
                "value": 180.0,
            },
        ],
        "condition_pair_catalog": [
            {
                "pair_id": "preferred_vs_null",
                "left_condition_id": "preferred_direction",
                "right_condition_id": "null_direction",
            }
        ],
        "analysis_window_catalog": [
            {
                "window_id": "shared_response_window",
                "start_ms": 10.0,
                "end_ms": 60.0,
                "description": "Fixture shared-response window.",
            }
        ],
        "metric_recipe_catalog": [
            {
                "recipe_id": f"response_latency_to_peak_ms__{readout_id}",
                "metric_id": "response_latency_to_peak_ms",
                "window_id": "shared_response_window",
                "active_readout_ids": [readout_id],
                "condition_ids": ["preferred_direction", "null_direction"],
                "condition_pair_id": None,
            },
            {
                "recipe_id": f"direction_selectivity_index__{readout_id}",
                "metric_id": "direction_selectivity_index",
                "window_id": "shared_response_window",
                "active_readout_ids": [readout_id],
                "condition_ids": [],
                "condition_pair_id": "preferred_vs_null",
            },
        ],
    }


def _build_inline_bundle_record(
    tmp_dir: Path,
    *,
    asset_suffix: str,
    condition_ids: list[str],
    readout_traces: dict[str, list[float]],
    arm_id: str,
    stimulus_family: str,
    stimulus_name: str,
    model_mode: str = "baseline",
    baseline_family: str | None = "P0",
    seed: int = 11,
) -> dict[str, object]:
    stimulus_metadata = _write_fixture_stimulus_metadata(
        tmp_dir,
        asset_suffix=asset_suffix,
        stimulus_family=stimulus_family,
        stimulus_name=stimulus_name,
    )
    readout_ids = list(readout_traces)
    values = np.column_stack(
        [np.asarray(readout_traces[readout_id], dtype=np.float64) for readout_id in readout_ids]
    )
    metadata = build_simulator_result_bundle_metadata(
        manifest_reference=build_simulator_manifest_reference(
            experiment_id="fixture_circuit",
            manifest_path=tmp_dir / "fixture_manifest.yaml",
            milestone="milestone_13",
        ),
        arm_reference=build_simulator_arm_reference(
            arm_id=arm_id,
            model_mode=model_mode,
            baseline_family=baseline_family,
        ),
        timebase=FIXTURE_TIMEBASE,
        selected_assets=[
            build_selected_asset_reference(
                asset_role="input_bundle",
                artifact_type="stimulus_bundle",
                path=Path(stimulus_metadata["assets"]["metadata_json"]["path"]),
                contract_version=str(stimulus_metadata["contract_version"]),
                artifact_id="stimulus_bundle",
                bundle_id=str(stimulus_metadata["bundle_id"]),
            )
        ],
        readout_catalog=[
            build_simulator_readout_definition(
                readout_id=readout_id,
                scope="circuit_output",
                aggregation="mean_over_root_ids",
                units="activation_au",
                value_semantics=f"{readout_id}_semantics",
                description=f"Fixture readout {readout_id}.",
            )
            for readout_id in readout_ids
        ],
        processed_simulator_results_dir=tmp_dir / "simulator_results",
        seed=seed,
    )
    return {
        "bundle_metadata": metadata,
        "condition_ids": list(condition_ids),
        "shared_readout_payload": {
            "time_ms": FIXTURE_TIME_MS,
            "readout_ids": tuple(readout_ids),
            "values": values,
        },
    }


def _write_fixture_edge_bundle(
    path: Path,
    *,
    pre_root_id: int,
    post_root_id: int,
    signed_weight_total: float,
    delay_ms: float,
    sign_label: str,
) -> None:
    source_anchor_table = pd.DataFrame.from_records(
        [
            {
                "anchor_table_index": 0,
                "root_id": pre_root_id,
                "anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "anchor_type": "surface_patch",
                "anchor_resolution": "coarse_patch",
                "anchor_index": 0,
                "anchor_x": 0.0,
                "anchor_y": 0.0,
                "anchor_z": 0.0,
            }
        ],
        columns=list(ANCHOR_COLUMN_TYPES),
    )
    target_anchor_table = pd.DataFrame.from_records(
        [
            {
                "anchor_table_index": 0,
                "root_id": post_root_id,
                "anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "anchor_type": "surface_patch",
                "anchor_resolution": "coarse_patch",
                "anchor_index": 0,
                "anchor_x": 1.0,
                "anchor_y": 0.0,
                "anchor_z": 0.0,
            }
        ],
        columns=list(ANCHOR_COLUMN_TYPES),
    )
    component_id = f"{pre_root_id}__to__{post_root_id}__component_0000"
    component_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "component_id": component_id,
                "pre_root_id": pre_root_id,
                "post_root_id": post_root_id,
                "topology_family": DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
                "kernel_family": SEPARABLE_RANK_ONE_CLOUD_KERNEL,
                "pre_anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "post_anchor_mode": SURFACE_PATCH_CLOUD_MODE,
                "sign_label": sign_label,
                "sign_polarity": 1 if signed_weight_total > 0.0 else -1,
                "sign_representation": DEFAULT_SIGN_REPRESENTATION,
                "delay_representation": DEFAULT_DELAY_REPRESENTATION,
                "delay_model": "fixture_delay_model",
                "delay_ms": delay_ms,
                "delay_bin_index": 0,
                "delay_bin_label": f"{delay_ms:.6f}",
                "delay_bin_start_ms": delay_ms,
                "delay_bin_end_ms": delay_ms,
                "aggregation_rule": DEFAULT_AGGREGATION_RULE,
                "source_anchor_count": 1,
                "target_anchor_count": 1,
                "synapse_count": 1,
                "signed_weight_total": signed_weight_total,
                "absolute_weight_total": abs(signed_weight_total),
                "confidence_sum": 1.0,
                "confidence_mean": 1.0,
                "source_cloud_normalization": SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
                "target_cloud_normalization": SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
                "source_normalization_total": 1.0,
                "target_normalization_total": 1.0,
            }
        ],
        columns=list(COMPONENT_COLUMN_TYPES),
    )
    source_cloud_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "anchor_table_index": 0,
                "cloud_weight": 1.0,
                "anchor_weight_total": 1.0,
                "supporting_synapse_count": 1,
            }
        ],
        columns=list(CLOUD_COLUMN_TYPES),
    )
    target_cloud_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "anchor_table_index": 0,
                "cloud_weight": 1.0,
                "anchor_weight_total": 1.0,
                "supporting_synapse_count": 1,
            }
        ],
        columns=list(CLOUD_COLUMN_TYPES),
    )
    component_synapse_table = pd.DataFrame.from_records(
        [
            {
                "component_index": 0,
                "synapse_row_id": f"{component_id}#0",
                "source_row_number": 1,
                "synapse_id": f"{component_id}#synapse",
                "sign_label": sign_label,
                "signed_weight": signed_weight_total,
                "absolute_weight": abs(signed_weight_total),
                "delay_ms": delay_ms,
                "delay_bin_index": 0,
                "delay_bin_label": f"{delay_ms:.6f}",
            }
        ],
        columns=list(COMPONENT_SYNAPSE_COLUMN_TYPES),
    )
    empty_synapse_table = pd.DataFrame(columns=list(EDGE_BUNDLE_COLUMN_TYPES))
    bundle = EdgeCouplingBundle(
        pre_root_id=pre_root_id,
        post_root_id=post_root_id,
        status="ready",
        topology_family=DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
        kernel_family=SEPARABLE_RANK_ONE_CLOUD_KERNEL,
        sign_representation=DEFAULT_SIGN_REPRESENTATION,
        delay_representation=DEFAULT_DELAY_REPRESENTATION,
        delay_model="fixture_delay_model",
        delay_model_parameters={
            "base_delay_ms": 0.0,
            "velocity_distance_units_per_ms": 1.0,
            "delay_bin_size_ms": 0.0,
        },
        aggregation_rule=DEFAULT_AGGREGATION_RULE,
        missing_geometry_policy="fixture_only",
        source_cloud_normalization=SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
        target_cloud_normalization=SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
        synapse_table=empty_synapse_table.copy(),
        component_table=component_table,
        blocked_synapse_table=empty_synapse_table.copy(),
        source_anchor_table=source_anchor_table,
        target_anchor_table=target_anchor_table,
        source_cloud_table=source_cloud_table,
        target_cloud_table=target_cloud_table,
        component_synapse_table=component_synapse_table,
    )
    _write_edge_coupling_bundle_npz(path=path, bundle=bundle)


def _write_fixture_stimulus_metadata(
    tmp_dir: Path,
    *,
    asset_suffix: str,
    stimulus_family: str,
    stimulus_name: str,
    parameter_snapshot: dict[str, object] | None = None,
) -> dict[str, object]:
    stimulus_metadata = build_stimulus_bundle_metadata(
        stimulus_family=stimulus_family,
        stimulus_name=stimulus_name,
        parameter_snapshot={
            "fixture_id": asset_suffix,
            **(parameter_snapshot or {}),
        },
        seed=11,
        temporal_sampling={
            "dt_ms": 10.0,
            "fps": 100.0,
            "frame_count": 7,
            "duration_ms": 70.0,
        },
        spatial_frame={
            "width_px": 8,
            "height_px": 4,
            "width_deg": 80.0,
            "height_deg": 40.0,
        },
        processed_stimulus_dir=tmp_dir / "stimuli",
    )
    write_stimulus_bundle_metadata(stimulus_metadata)
    return stimulus_metadata


def _materialize_circuit_workflow_fixture(tmp_dir: Path) -> dict[str, Path]:
    output_dir = tmp_dir / "out"
    manifest_path = _write_manifest_fixture(
        tmp_dir,
        manifest_overrides={
            "seed_sweep": [11],
        },
    )
    schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
    design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"
    config_path = _write_simulation_fixture(
        tmp_dir,
        timebase_dt_ms=10.0,
        timebase_sample_count=7,
        readout_catalog=[
            {
                "readout_id": "shared_output_mean",
                "scope": "circuit_output",
                "aggregation": "mean_over_root_ids",
                "units": "activation_au",
                "value_semantics": "shared_downstream_activation",
                "description": "Shared output mean.",
            },
            {
                "readout_id": "preferred_pathway_output",
                "scope": "circuit_output",
                "aggregation": "mean_over_root_ids",
                "units": "activation_au",
                "value_semantics": "shared_downstream_activation",
                "description": "Preferred pathway output used for motion asymmetry validation.",
            },
        ],
        analysis_config={
            "active_readout_ids": [
                "shared_output_mean",
                "preferred_pathway_output",
            ],
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
    analysis_plan = resolve_manifest_readout_analysis_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    default_stimulus_metadata = _load_default_stimulus_metadata(simulation_plan)
    condition_stimuli = _materialize_condition_stimuli(
        processed_stimulus_dir=output_dir / "stimuli",
        analysis_plan=analysis_plan,
        default_stimulus_metadata=default_stimulus_metadata,
    )
    run_plans = discover_simulation_run_plans(
        simulation_plan,
        use_manifest_seed_sweep=True,
    )
    _materialize_workflow_bundles(
        run_plans=run_plans,
        condition_stimuli=condition_stimuli,
    )
    return {
        "manifest_path": manifest_path.resolve(),
        "config_path": config_path.resolve(),
        "schema_path": schema_path.resolve(),
        "design_lock_path": design_lock_path.resolve(),
    }


def _load_default_stimulus_metadata(
    simulation_plan: dict[str, object],
) -> dict[str, object]:
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
    analysis_plan: dict[str, object],
    default_stimulus_metadata: dict[str, object],
) -> dict[tuple[str, ...], dict[str, object]]:
    conditions_by_parameter: dict[str, list[dict[str, object]]] = {}
    for item in analysis_plan["condition_catalog"]:
        conditions_by_parameter.setdefault(str(item["parameter_name"]), []).append(
            dict(item)
        )
    for values in conditions_by_parameter.values():
        values.sort(key=lambda item: str(item["condition_id"]))

    combos: list[list[dict[str, object]]] = [[]]
    for parameter_name in sorted(conditions_by_parameter):
        next_combos: list[list[dict[str, object]]] = []
        for prefix in combos:
            for item in conditions_by_parameter[parameter_name]:
                next_combos.append([*prefix, dict(item)])
        combos = next_combos

    metadata_by_signature: dict[tuple[str, ...], dict[str, object]] = {}
    for combo in combos:
        condition_ids = tuple(sorted(str(item["condition_id"]) for item in combo))
        parameter_snapshot = dict(default_stimulus_metadata["parameter_snapshot"])
        for item in combo:
            parameter_snapshot[str(item["parameter_name"])] = item["value"]
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


def _materialize_workflow_bundles(
    *,
    run_plans: list[dict[str, object]],
    condition_stimuli: dict[tuple[str, ...], dict[str, object]],
) -> None:
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
            write_simulator_result_bundle_metadata(bundle_metadata)
            _write_bundle_artifacts(
                bundle_metadata=bundle_metadata,
                trace_matrix=_workflow_trace_matrix(
                    arm_id=str(run_plan["arm_reference"]["arm_id"]),
                    condition_ids=condition_ids,
                ),
            )


def _replace_input_bundle_asset(
    selected_assets: list[dict[str, object]],
    stimulus_metadata: dict[str, object],
) -> list[dict[str, object]]:
    replaced: list[dict[str, object]] = []
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
        replaced.append(dict(item))
    return replaced


def _write_bundle_artifacts(
    *,
    bundle_metadata: dict[str, object],
    trace_matrix: np.ndarray,
) -> None:
    artifacts = bundle_metadata["artifacts"]
    state_summary_path = Path(artifacts[STATE_SUMMARY_KEY]["path"]).resolve()
    metrics_path = Path(artifacts[METRICS_TABLE_KEY]["path"]).resolve()
    readout_path = Path(artifacts[READOUT_TRACES_KEY]["path"]).resolve()
    state_summary_path.parent.mkdir(parents=True, exist_ok=True)
    write_json([], state_summary_path)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        "metric_id,readout_id,scope,window_id,statistic,value,units\n",
        encoding="utf-8",
    )
    readout_ids = np.asarray(
        [str(item["readout_id"]) for item in bundle_metadata["readout_catalog"]],
        dtype="<U64",
    )
    write_deterministic_npz(
        {
            "time_ms": FIXTURE_TIME_MS,
            "readout_ids": readout_ids,
            "values": np.asarray(trace_matrix, dtype=np.float64),
        },
        readout_path,
    )


def _workflow_trace_matrix(
    *,
    arm_id: str,
    condition_ids: tuple[str, ...],
) -> np.ndarray:
    shared_trace = _experiment_style_shared_trace(
        arm_id=arm_id,
        condition_ids=condition_ids,
    )
    pathway_trace = _experiment_style_pathway_trace(
        arm_id=arm_id,
        condition_ids=condition_ids,
    )
    return np.column_stack([shared_trace, pathway_trace])


def _response_trace(peak: float, peak_index: int) -> np.ndarray:
    if peak_index == 1:
        values = [2.0, 2.0 + peak, 2.0 + peak * 0.55, 2.0 + peak * 0.20, 2.1, 2.0, 2.0]
    else:
        values = [2.0, 2.0, 2.0 + peak * 0.2, 2.0 + peak, 2.0 + peak * 0.35, 2.1, 2.0]
    return np.asarray(values, dtype=np.float64)


def _experiment_style_shared_trace(
    *,
    arm_id: str,
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
    response = _response_profile(
        peak=max(0.5, adjusted_peak),
        peak_index=int(adjustment["peak_index"]),
    )
    return np.asarray([2.0, *[2.0 + value for value in response]], dtype=np.float64)


def _experiment_style_pathway_trace(
    *,
    arm_id: str,
    condition_ids: tuple[str, ...],
) -> np.ndarray:
    base_peak_by_condition = {
        ("null_direction", "off_polarity"): 2.0,
        ("null_direction", "on_polarity"): 2.6,
        ("off_polarity", "preferred_direction"): 4.4,
        ("on_polarity", "preferred_direction"): 6.2,
    }
    arm_adjustments = {
        "baseline_p0_intact": {"preferred_delta": 0.5, "null_delta": -0.2, "peak_index": 2},
        "baseline_p0_shuffled": {"preferred_delta": 0.2, "null_delta": -0.05, "peak_index": 2},
        "surface_wave_intact": {"preferred_delta": 1.8, "null_delta": -1.1, "peak_index": 1},
        "surface_wave_shuffled": {"preferred_delta": 0.7, "null_delta": -0.3, "peak_index": 2},
        "baseline_p1_intact": {"preferred_delta": 0.8, "null_delta": -0.4, "peak_index": 2},
        "baseline_p1_shuffled": {"preferred_delta": 0.5, "null_delta": -0.15, "peak_index": 2},
    }
    normalized_condition_ids = tuple(sorted(condition_ids))
    base_peak = float(base_peak_by_condition[normalized_condition_ids])
    adjustment = arm_adjustments[arm_id]
    is_preferred = "preferred_direction" in set(normalized_condition_ids)
    adjusted_peak = base_peak + (
        float(adjustment["preferred_delta"]) if is_preferred else float(adjustment["null_delta"])
    )
    response = _response_profile(
        peak=max(0.6, adjusted_peak),
        peak_index=int(adjustment["peak_index"]),
    )
    return np.asarray([2.0, *[2.0 + value for value in response]], dtype=np.float64)


def _response_profile(*, peak: float, peak_index: int) -> list[float]:
    if peak_index == 1:
        return [0.0, 0.0, 0.0, 0.0, peak, peak * 0.55]
    if peak_index == 2:
        return [0.0, 0.0, 0.0, 0.0, peak * 0.25, peak]
    raise ValueError(f"Unsupported peak_index {peak_index!r}.")


if __name__ == "__main__":
    unittest.main()
