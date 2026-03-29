from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.experiment_analysis_contract import (
    ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
    EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID,
    build_experiment_analysis_bundle_metadata,
    discover_experiment_analysis_bundle_paths,
    write_experiment_analysis_bundle_metadata,
)
from flywire_wave.experiment_comparison_analysis import (
    compute_experiment_comparison_summary,
    discover_experiment_bundle_set,
)
from flywire_wave.io_utils import write_json
from flywire_wave.readout_analysis_contract import get_readout_analysis_metric_definition
from flywire_wave.shared_readout_analysis import (
    SUPPORTED_SHARED_READOUT_ANALYSIS_METRIC_IDS,
)
from flywire_wave.simulation_planning import (
    resolve_manifest_readout_analysis_plan,
    resolve_manifest_simulation_plan,
)
from flywire_wave.validation_contract import (
    SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID,
    TASK_DECODER_ROBUSTNESS_VALIDATOR_ID,
    VALIDATION_STATUS_BLOCKING,
    VALIDATION_STATUS_PASS,
)
from flywire_wave.validation_planning import NOISE_ROBUSTNESS_SUITE_ID
from flywire_wave.validation_task import (
    execute_task_validation_workflow,
)

try:
    from test_experiment_comparison_analysis import (
        _materialize_experiment_comparison_fixture,
    )
except ModuleNotFoundError:
    from tests.test_experiment_comparison_analysis import (
        _materialize_experiment_comparison_fixture,
    )


TASK_METRIC_IDS = [
    "motion_vector_heading_deg",
    "motion_vector_speed_deg_per_s",
    "optic_flow_heading_deg",
    "optic_flow_speed_deg_per_s",
]
HEADING_METRIC_IDS = {
    "motion_vector_heading_deg",
    "optic_flow_heading_deg",
}
SPEED_METRIC_IDS = {
    "motion_vector_speed_deg_per_s",
    "optic_flow_speed_deg_per_s",
}
TASK_VALIDATION_CONFIG = {
    "active_layer_ids": ["task_sanity"],
    "perturbation_suites": {
        "noise_robustness": {
            "enabled": True,
            "seed_values": [11],
            "noise_levels": [0.0, 0.1],
        },
        "sign_delay_perturbations": {
            "enabled": False,
        },
        "timestep_sweeps": {
            "enabled": False,
        },
    },
}


class TaskValidationWorkflowTest(unittest.TestCase):
    def test_fixture_workflow_is_deterministic_and_reports_pass_for_noise_robustness(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _prepare_task_validation_fixture(tmp_dir)

            first = execute_task_validation_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                analysis_bundle_metadata_path=fixture["base_bundle"]["metadata_path"],
                perturbation_analysis_bundle_specs=fixture["pass_noise_specs"],
            )
            second = execute_task_validation_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                analysis_bundle_metadata_path=fixture["base_bundle"]["metadata_path"],
                perturbation_analysis_bundle_specs=fixture["pass_noise_specs"],
            )

            self.assertEqual(first["overall_status"], VALIDATION_STATUS_PASS)
            self.assertEqual(first["overall_status"], second["overall_status"])
            self.assertEqual(first["validator_statuses"], second["validator_statuses"])
            self.assertEqual(first["case_summaries"], second["case_summaries"])
            self.assertEqual(
                first["validator_statuses"],
                {
                    SHARED_EFFECT_REPRODUCIBILITY_VALIDATOR_ID: VALIDATION_STATUS_PASS,
                    TASK_DECODER_ROBUSTNESS_VALIDATOR_ID: VALIDATION_STATUS_PASS,
                },
            )

            summary_payload = json.loads(
                Path(first["summary_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(summary_payload["overall_status"], VALIDATION_STATUS_PASS)
            self.assertEqual(
                summary_payload["analysis_inventory"]["ui_scope_separation"]["status"],
                VALIDATION_STATUS_PASS,
            )
            coverage_by_suite = {
                item["suite_id"]: item for item in summary_payload["perturbation_coverage"]
            }
            self.assertEqual(
                coverage_by_suite["geometry_variants"]["coverage_mode"],
                "embedded_in_base_analysis",
            )
            self.assertEqual(
                coverage_by_suite[NOISE_ROBUSTNESS_SUITE_ID]["provided_variant_ids"],
                ["seed_11__noise_0p0", "seed_11__noise_0p1"],
            )
            self.assertEqual(
                coverage_by_suite[NOISE_ROBUSTNESS_SUITE_ID]["status"],
                VALIDATION_STATUS_PASS,
            )

            findings_payload = json.loads(
                Path(first["findings_path"]).read_text(encoding="utf-8")
            )
            task_findings = findings_payload["validator_findings"][
                TASK_DECODER_ROBUSTNESS_VALIDATOR_ID
            ]
            self.assertTrue(
                any(
                    item["finding_id"].endswith(":seed_stability")
                    and item["status"] == VALIDATION_STATUS_PASS
                    for item in task_findings
                )
            )
            self.assertTrue(
                any(
                    "noise_robustness:seed_11__noise_0p1" in item["finding_id"]
                    and item["status"] == VALIDATION_STATUS_PASS
                    for item in task_findings
                )
            )

    def test_workflow_fails_clearly_for_missing_noise_variant_coverage(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _prepare_task_validation_fixture(tmp_dir)

            with self.assertRaises(ValueError) as ctx:
                execute_task_validation_workflow(
                    manifest_path=fixture["manifest_path"],
                    config_path=fixture["config_path"],
                    schema_path=fixture["schema_path"],
                    design_lock_path=fixture["design_lock_path"],
                    analysis_bundle_metadata_path=fixture["base_bundle"]["metadata_path"],
                    perturbation_analysis_bundle_specs=fixture["pass_noise_specs"][:1],
                )
            self.assertIn("missing variant_ids ['seed_11__noise_0p1']", str(ctx.exception))

    def test_workflow_fails_clearly_for_missing_task_seed_coverage(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _prepare_task_validation_fixture(tmp_dir)

            with self.assertRaises(ValueError) as ctx:
                execute_task_validation_workflow(
                    manifest_path=fixture["manifest_path"],
                    config_path=fixture["config_path"],
                    schema_path=fixture["schema_path"],
                    design_lock_path=fixture["design_lock_path"],
                    analysis_bundle_metadata_path=fixture["missing_seed_bundle"][
                        "metadata_path"
                    ],
                    perturbation_analysis_bundle_specs=fixture["pass_noise_specs"],
                )
            self.assertIn("missing required seed coverage", str(ctx.exception))

    def test_workflow_marks_contradictory_perturbation_as_blocking(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _prepare_task_validation_fixture(tmp_dir)

            result = execute_task_validation_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                analysis_bundle_metadata_path=fixture["base_bundle"]["metadata_path"],
                perturbation_analysis_bundle_specs=fixture["contradictory_noise_specs"],
            )

            self.assertEqual(result["overall_status"], VALIDATION_STATUS_BLOCKING)
            self.assertEqual(
                result["validator_statuses"][TASK_DECODER_ROBUSTNESS_VALIDATOR_ID],
                VALIDATION_STATUS_BLOCKING,
            )

    def test_workflow_fails_clearly_for_missing_task_decoder_inventory(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _prepare_task_validation_fixture(tmp_dir)

            with self.assertRaises(ValueError) as ctx:
                execute_task_validation_workflow(
                    manifest_path=fixture["manifest_path"],
                    config_path=fixture["config_path"],
                    schema_path=fixture["schema_path"],
                    design_lock_path=fixture["design_lock_path"],
                    analysis_bundle_metadata_path=fixture["base_bundle"]["metadata_path"],
                    perturbation_analysis_bundle_specs=fixture["missing_inventory_specs"],
                )
            self.assertIn("task-decoder inventory required", str(ctx.exception))


def _prepare_task_validation_fixture(tmp_dir: Path) -> dict[str, Any]:
    comparison_fixture = _materialize_experiment_comparison_fixture(tmp_dir)
    _write_validation_config(
        comparison_fixture["config_path"],
        TASK_VALIDATION_CONFIG,
    )

    simulation_plan = resolve_manifest_simulation_plan(
        manifest_path=comparison_fixture["manifest_path"],
        config_path=comparison_fixture["config_path"],
        schema_path=comparison_fixture["schema_path"],
        design_lock_path=comparison_fixture["design_lock_path"],
    )
    analysis_plan = _augment_analysis_plan_with_task_metrics(
        resolve_manifest_readout_analysis_plan(
            manifest_path=comparison_fixture["manifest_path"],
            config_path=comparison_fixture["config_path"],
            schema_path=comparison_fixture["schema_path"],
            design_lock_path=comparison_fixture["design_lock_path"],
        )
    )
    bundle_set = discover_experiment_bundle_set(
        simulation_plan=simulation_plan,
        analysis_plan=analysis_plan,
    )
    base_summary = compute_experiment_comparison_summary(
        analysis_plan=analysis_plan,
        bundle_set=bundle_set,
    )

    base_bundle = _write_analysis_bundle_fixture(
        tmp_dir=tmp_dir,
        label="base",
        analysis_plan=analysis_plan,
        bundle_set=bundle_set,
        summary=base_summary,
    )
    noise_identity_bundle = _write_analysis_bundle_fixture(
        tmp_dir=tmp_dir,
        label="noise_seed11_level0",
        analysis_plan=analysis_plan,
        bundle_set=bundle_set,
        summary=copy.deepcopy(base_summary),
    )
    noise_pass_bundle = _write_analysis_bundle_fixture(
        tmp_dir=tmp_dir,
        label="noise_seed11_level0p1",
        analysis_plan=analysis_plan,
        bundle_set=bundle_set,
        summary=_build_perturbed_summary(
            base_summary,
            shared_scale=0.9,
            speed_scale=0.85,
            heading_delta_deg=4.0,
        ),
    )
    contradictory_noise_bundle = _write_analysis_bundle_fixture(
        tmp_dir=tmp_dir,
        label="noise_seed11_level0p1_contradictory",
        analysis_plan=analysis_plan,
        bundle_set=bundle_set,
        summary=_build_perturbed_summary(
            base_summary,
            shared_scale=-0.75,
            speed_scale=-0.75,
            heading_delta_deg=170.0,
        ),
    )
    missing_inventory_bundle = _write_analysis_bundle_fixture(
        tmp_dir=tmp_dir,
        label="noise_seed11_level0p1_missing_inventory",
        analysis_plan=analysis_plan,
        bundle_set=bundle_set,
        summary=_drop_task_inventory(base_summary),
    )
    missing_seed_bundle = _write_analysis_bundle_fixture(
        tmp_dir=tmp_dir,
        label="base_missing_seed",
        analysis_plan=analysis_plan,
        bundle_set=bundle_set,
        summary=_drop_task_seed_coverage(
            base_summary,
            arm_id="surface_wave_intact",
            metric_id="motion_vector_speed_deg_per_s",
            seed=17,
        ),
    )

    return {
        **comparison_fixture,
        "base_bundle": base_bundle,
        "pass_noise_specs": [
            {
                "suite_id": NOISE_ROBUSTNESS_SUITE_ID,
                "variant_id": "seed_11__noise_0p0",
                "analysis_bundle_metadata_path": noise_identity_bundle["metadata_path"],
            },
            {
                "suite_id": NOISE_ROBUSTNESS_SUITE_ID,
                "variant_id": "seed_11__noise_0p1",
                "analysis_bundle_metadata_path": noise_pass_bundle["metadata_path"],
            },
        ],
        "contradictory_noise_specs": [
            {
                "suite_id": NOISE_ROBUSTNESS_SUITE_ID,
                "variant_id": "seed_11__noise_0p0",
                "analysis_bundle_metadata_path": noise_identity_bundle["metadata_path"],
            },
            {
                "suite_id": NOISE_ROBUSTNESS_SUITE_ID,
                "variant_id": "seed_11__noise_0p1",
                "analysis_bundle_metadata_path": contradictory_noise_bundle[
                    "metadata_path"
                ],
            },
        ],
        "missing_inventory_specs": [
            {
                "suite_id": NOISE_ROBUSTNESS_SUITE_ID,
                "variant_id": "seed_11__noise_0p0",
                "analysis_bundle_metadata_path": noise_identity_bundle["metadata_path"],
            },
            {
                "suite_id": NOISE_ROBUSTNESS_SUITE_ID,
                "variant_id": "seed_11__noise_0p1",
                "analysis_bundle_metadata_path": missing_inventory_bundle[
                    "metadata_path"
                ],
            },
        ],
        "missing_seed_bundle": missing_seed_bundle,
    }


def _write_validation_config(
    config_path: Path,
    validation_config: Mapping[str, Any],
) -> None:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    payload["validation"] = copy.deepcopy(dict(validation_config))
    config_path.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )


def _augment_analysis_plan_with_task_metrics(
    analysis_plan: Mapping[str, Any],
) -> dict[str, Any]:
    plan = copy.deepcopy(dict(analysis_plan))
    for metric_id in TASK_METRIC_IDS:
        if metric_id in set(plan["active_metric_ids"]):
            continue
        plan["active_metric_ids"].append(metric_id)
        plan["active_metric_definitions"].append(
            get_readout_analysis_metric_definition(metric_id)
        )
        recipe_id = (
            f"{metric_id}__shared_output_mean__task_decoder_window__task_decoder"
        )
        plan["metric_recipe_catalog"].append(
            {
                "recipe_id": recipe_id,
                "metric_id": metric_id,
                "window_id": "task_decoder_window",
                "active_readout_ids": ["shared_output_mean"],
                "condition_ids": [],
                "condition_pair_id": "preferred_vs_null",
            }
        )
        plan["manifest_metric_requests"].append(
            {
                "requested_metric_id": metric_id,
                "request_role": "companion",
                "request_order": len(plan["manifest_metric_requests"]),
                "recipe_kind": "contract_metric",
                "resolved_metric_ids": [metric_id],
                "metric_recipe_ids": [recipe_id],
                "comparison_group_ids": [
                    item["group_id"] for item in plan["arm_pair_catalog"]
                ],
                "condition_pair_ids": ["preferred_vs_null"],
                "seed_aggregation_rule_id": "per_run_single_seed",
            }
        )
    return plan


def _write_analysis_bundle_fixture(
    *,
    tmp_dir: Path,
    label: str,
    analysis_plan: Mapping[str, Any],
    bundle_set: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    bundle_set_for_output = copy.deepcopy(dict(bundle_set))
    bundle_set_for_output["processed_simulator_results_dir"] = str(
        (tmp_dir / "analysis_fixture_outputs" / label).resolve()
    )
    metadata = build_experiment_analysis_bundle_metadata(
        analysis_plan=analysis_plan,
        bundle_set=bundle_set_for_output,
    )
    metadata_path = write_experiment_analysis_bundle_metadata(metadata)
    paths = discover_experiment_analysis_bundle_paths(metadata)
    write_json(summary, paths[EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID])
    write_json(
        _build_analysis_ui_payload_fixture(summary),
        paths[ANALYSIS_UI_PAYLOAD_ARTIFACT_ID],
    )
    return {
        "metadata": metadata,
        "metadata_path": str(Path(metadata_path).resolve()),
    }


def _build_analysis_ui_payload_fixture(summary: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "format_version": "json_experiment_analysis_ui_payload.v1",
        "manifest_reference": copy.deepcopy(dict(summary["manifest_reference"])),
        "shared_comparison": {
            "task_summary_cards": [],
            "comparison_cards": [],
            "null_test_cards": [],
            "milestone_1_decision_panel": copy.deepcopy(
                dict(summary["milestone_1_decision_panel"])
            ),
        },
        "wave_only_diagnostics": {
            "comparison_cards": [],
            "diagnostic_cards": [],
            "phase_map_references": [],
        },
        "mixed_scope": {
            "comparison_cards": [],
        },
    }


def _build_perturbed_summary(
    base_summary: Mapping[str, Any],
    *,
    shared_scale: float,
    speed_scale: float,
    heading_delta_deg: float,
) -> dict[str, Any]:
    summary = copy.deepcopy(dict(base_summary))

    for item in summary["analysis_results"]["task_decoder_analysis"]["metric_rows"]:
        metric_id = str(item["metric_id"])
        value = float(item["value"])
        if metric_id in HEADING_METRIC_IDS:
            item["value"] = round(value + heading_delta_deg, 12)
        elif metric_id in SPEED_METRIC_IDS:
            item["value"] = round(value * speed_scale, 12)

    for rollup in summary["group_metric_rollups"]:
        metric_id = str(rollup["metric_id"])
        mean_value = float(rollup["summary_statistics"]["mean"])
        if metric_id in HEADING_METRIC_IDS:
            rollup["summary_statistics"]["mean"] = round(
                mean_value + heading_delta_deg,
                12,
            )
        elif metric_id in SPEED_METRIC_IDS:
            rollup["summary_statistics"]["mean"] = round(mean_value * speed_scale, 12)
        elif metric_id in SUPPORTED_SHARED_READOUT_ANALYSIS_METRIC_IDS:
            rollup["summary_statistics"]["mean"] = round(
                mean_value * shared_scale,
                12,
            )
    return summary


def _drop_task_seed_coverage(
    base_summary: Mapping[str, Any],
    *,
    arm_id: str,
    metric_id: str,
    seed: int,
) -> dict[str, Any]:
    summary = copy.deepcopy(dict(base_summary))
    metric_rows = summary["analysis_results"]["task_decoder_analysis"]["metric_rows"]
    summary["analysis_results"]["task_decoder_analysis"]["metric_rows"] = [
        copy.deepcopy(dict(item))
        for item in metric_rows
        if not (
            str(item["arm_id"]) == arm_id
            and str(item["metric_id"]) == metric_id
            and int(item["seed"]) == int(seed)
        )
    ]
    return summary


def _drop_task_inventory(base_summary: Mapping[str, Any]) -> dict[str, Any]:
    summary = copy.deepcopy(dict(base_summary))
    summary["analysis_results"]["task_decoder_analysis"]["metric_rows"] = []
    summary["group_metric_rollups"] = [
        copy.deepcopy(dict(item))
        for item in summary["group_metric_rollups"]
        if str(item["metric_id"]) not in set(TASK_METRIC_IDS)
    ]
    return summary


if __name__ == "__main__":
    unittest.main()
