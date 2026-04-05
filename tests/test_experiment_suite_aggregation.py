from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.experiment_suite_aggregation import (
    compute_experiment_suite_aggregation,
    execute_experiment_suite_aggregation_workflow,
)
from flywire_wave.experiment_suite_contract import WORK_ITEM_STATUS_SUCCEEDED
from flywire_wave.experiment_suite_packaging import load_experiment_suite_package_metadata
from flywire_wave.experiment_suite_packaging import load_experiment_suite_result_index
from flywire_wave.experiment_suite_packaging import package_experiment_suite_outputs
from flywire_wave.experiment_suite_planning import resolve_experiment_suite_plan
from flywire_wave.io_utils import write_json, write_jsonl

try:
    from tests.test_experiment_suite_planning import (
        _base_suite_block,
        _write_suite_manifest_fixture,
    )
except ModuleNotFoundError:
    from test_experiment_suite_planning import (  # type: ignore[no-redef]
        _base_suite_block,
        _write_suite_manifest_fixture,
    )

try:
    from tests.simulation_planning_test_support import (
        _record_fixture_stimulus_bundle,
        _write_manifest_fixture,
        _write_simulation_fixture,
    )
except ModuleNotFoundError:
    from simulation_planning_test_support import (  # type: ignore[no-redef]
        _record_fixture_stimulus_bundle,
        _write_manifest_fixture,
        _write_simulation_fixture,
    )


class ExperimentSuiteAggregationTest(unittest.TestCase):
    def test_workflow_computes_deterministic_sectioned_rollups_and_collapsed_tables(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            package_metadata_path = _materialize_packaged_suite_fixture(tmp_dir)

            first = compute_experiment_suite_aggregation(
                package_metadata_path,
                table_dimension_ids=["motion_direction"],
            )
            second = compute_experiment_suite_aggregation(
                package_metadata_path,
                table_dimension_ids=["motion_direction"],
            )

            self.assertEqual(first, second)
            self.assertEqual(first["format_version"], "experiment_suite_aggregation.v1")
            self.assertEqual(
                first["table_dimensions"]["table_dimension_ids"],
                ["motion_direction"],
            )

            shared = first["shared_comparison_metrics"]
            wave = first["wave_only_diagnostics"]
            validation = first["validation_findings"]

            self.assertGreater(len(shared["cell_rollup_rows"]), 0)
            self.assertGreater(len(shared["paired_comparison_rows"]), 0)
            self.assertGreater(len(shared["summary_table_rows"]), 0)
            self.assertGreater(len(wave["cell_rollup_rows"]), 0)
            self.assertGreater(len(wave["paired_comparison_rows"]), 0)
            self.assertGreater(len(validation["cell_summary_rows"]), 0)
            self.assertGreater(len(validation["finding_rows"]), 0)
            self.assertGreater(len(validation["summary_table_rows"]), 0)

            sample_shared_pair = next(
                row
                for row in shared["paired_comparison_rows"]
                if row["ablation_key"] == "no_waves:disabled"
                and row["group_id"] == "matched_surface_wave_vs_p0__intact"
                and row["metric_id"] == "null_direction_suppression_index"
            )
            self.assertEqual(sample_shared_pair["section_id"], "shared_comparison_metrics")
            self.assertEqual(sample_shared_pair["delta_mean"], -0.08)
            self.assertEqual(sample_shared_pair["expected_seeds"], [4011, 4017, 4023])

            sample_wave_pair = next(
                row
                for row in wave["paired_comparison_rows"]
                if row["ablation_key"] == "no_waves:disabled"
                and row["arm_id"] == "surface_wave_intact"
                and row["metric_id"] == "wavefront_alignment_score"
            )
            self.assertEqual(sample_wave_pair["section_id"], "wave_only_diagnostics")
            self.assertEqual(sample_wave_pair["delta_mean"], -0.25)

            shared_summary_row = next(
                row
                for row in shared["summary_table_rows"]
                if row["ablation_key"] == "no_waves:disabled"
                and row["dimension_slice_key"] == "motion_direction=preferred"
                and row["group_id"] == "matched_surface_wave_vs_p0__intact"
                and row["metric_id"] == "null_direction_suppression_index"
            )
            self.assertEqual(shared_summary_row["source_row_count"], 4)
            self.assertEqual(
                shared_summary_row["collapse_rule_id"],
                "deterministic_mean_of_source_rows",
            )
            self.assertEqual(
                shared_summary_row["delta_mean_statistics"]["mean"],
                -0.08,
            )

            validation_summary_row = next(
                row
                for row in validation["summary_table_rows"]
                if row["ablation_key"] == "no_waves:disabled"
                and row["dimension_slice_key"] == "motion_direction=preferred"
            )
            self.assertEqual(validation_summary_row["source_row_count"], 4)
            self.assertEqual(
                validation_summary_row["status_transition_counts"],
                {"pass->review": 4},
            )
            self.assertEqual(
                validation_summary_row["finding_count_delta_statistics"]["mean"],
                1.0,
            )

            written = execute_experiment_suite_aggregation_workflow(
                package_metadata_path,
                table_dimension_ids=["motion_direction"],
            )
            self.assertTrue(Path(written["summary_path"]).exists())
            self.assertTrue(Path(written["shared_pair_rows_path"]).exists())
            self.assertTrue(Path(written["wave_summary_table_path"]).exists())
            self.assertTrue(Path(written["validation_finding_rows_path"]).exists())

    def test_workflow_fails_clearly_when_required_ablation_rollup_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            package_metadata_path = _materialize_packaged_suite_fixture(tmp_dir)
            result_index = load_experiment_suite_result_index(
                load_experiment_suite_package_metadata(package_metadata_path)
            )
            target_summary_path = _analysis_summary_path_for_ablation(
                result_index,
                ablation_key="no_waves:disabled",
            )
            payload = json.loads(target_summary_path.read_text(encoding="utf-8"))
            payload["group_metric_rollups"] = [
                row
                for row in payload["group_metric_rollups"]
                if not (
                    row["group_id"] == "matched_surface_wave_vs_p0__intact"
                    and row["metric_id"] == "null_direction_suppression_index"
                )
            ]
            write_json(payload, target_summary_path)

            with self.assertRaises(ValueError) as ctx:
                compute_experiment_suite_aggregation(
                    package_metadata_path,
                    table_dimension_ids=["motion_direction"],
                )

            message = str(ctx.exception)
            self.assertIn("missing key", message)
            self.assertIn("matched_surface_wave_vs_p0__intact", message)
            self.assertIn("no_waves", message)

    def test_workflow_fails_clearly_for_incomplete_seed_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            package_metadata_path = _materialize_packaged_suite_fixture(tmp_dir)
            result_index = load_experiment_suite_result_index(
                load_experiment_suite_package_metadata(package_metadata_path)
            )
            target_summary_path = _analysis_summary_path_for_ablation(
                result_index,
                ablation_key="no_waves:disabled",
            )
            payload = json.loads(target_summary_path.read_text(encoding="utf-8"))
            target_rollup = next(
                row
                for row in payload["group_metric_rollups"]
                if row["group_id"] == "matched_surface_wave_vs_p0__intact"
                and row["metric_id"] == "null_direction_suppression_index"
            )
            target_rollup["seeds"] = [11, 17]
            target_rollup["seed_count"] = 2
            write_json(payload, target_summary_path)

            with self.assertRaises(ValueError) as ctx:
                compute_experiment_suite_aggregation(
                    package_metadata_path,
                    table_dimension_ids=["motion_direction"],
                )

            message = str(ctx.exception)
            self.assertIn("complete seed coverage", message)
            self.assertIn("expected [4011, 4017, 4023]", message)
            self.assertIn("got [11, 17]", message)


def _materialize_packaged_suite_fixture(tmp_dir: Path) -> Path:
    schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
    design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"
    manifest_path = _write_manifest_fixture(tmp_dir)
    config_path = _write_simulation_fixture(tmp_dir)
    _record_fixture_stimulus_bundle(
        manifest_path=manifest_path,
        processed_stimulus_dir=tmp_dir / "out" / "stimuli",
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    suite_manifest_path = _write_suite_manifest_fixture(
        tmp_dir=tmp_dir,
        manifest_path=manifest_path,
        suite_block=_base_suite_block(
            output_root=tmp_dir / "o",
            enabled_stage_ids=["simulation", "analysis", "validation"],
        ),
    )
    plan = resolve_experiment_suite_plan(
        config_path=config_path,
        suite_manifest_path=suite_manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    suite_root = Path(plan["output_roots"]["suite_root"]).resolve()
    write_json(plan, Path(plan["output_roots"]["suite_plan_path"]).resolve())
    write_json(plan["suite_metadata"], Path(plan["output_roots"]["suite_metadata_path"]).resolve())
    state_path = suite_root / "experiment_suite_execution_state.json"
    work_items = []
    cells_by_id = {str(item["suite_cell_id"]): dict(item) for item in plan["cell_catalog"]}
    for index, work_item in enumerate(plan["work_item_catalog"]):
        suite_cell = cells_by_id[str(work_item["suite_cell_id"])]
        if str(work_item["stage_id"]) == "simulation":
            result = _fixture_simulation_result(
                suite_cell=suite_cell,
                work_item=work_item,
                tmp_dir=tmp_dir,
                index=index,
            )
        elif str(work_item["stage_id"]) == "analysis":
            result = _fixture_analysis_result(
                suite_cell=suite_cell,
                work_item=work_item,
                plan=plan,
                tmp_dir=tmp_dir,
                index=index,
            )
        elif str(work_item["stage_id"]) == "validation":
            result = _fixture_validation_result(
                suite_cell=suite_cell,
                work_item=work_item,
                tmp_dir=tmp_dir,
                index=index,
            )
        else:
            raise AssertionError(f"unexpected stage_id {work_item['stage_id']!r}")
        work_items.append(
            {
                "work_item_id": str(work_item["work_item_id"]),
                "suite_cell_id": str(work_item["suite_cell_id"]),
                "stage_id": str(work_item["stage_id"]),
                "artifact_role_ids": list(work_item["artifact_role_ids"]),
                "workspace_root": str((tmp_dir / "ws" / f"w{index}").resolve()),
                "materialized_manifest_path": "",
                "materialized_config_path": "",
                "status": WORK_ITEM_STATUS_SUCCEEDED,
                "status_detail": str(result["status_detail"]),
                "attempt_count": 1,
                "attempts": [
                    {
                        "decision": "fixture_execute",
                        "dependency_statuses": [],
                        "downstream_artifacts": list(result["downstream_artifacts"]),
                        "error": None,
                        "result_summary": dict(result["summary"]),
                        "status": WORK_ITEM_STATUS_SUCCEEDED,
                        "status_detail": str(result["status_detail"]),
                    }
                ],
            }
        )
    state = {
        "state_version": "experiment_suite_execution_state.v1",
        "suite_id": str(plan["suite_id"]),
        "suite_label": str(plan["suite_label"]),
        "suite_spec_hash": str(plan["suite_metadata"]["suite_spec_hash"]),
        "suite_root": str(suite_root),
        "state_path": str(state_path.resolve()),
        "overall_status": WORK_ITEM_STATUS_SUCCEEDED,
        "work_items": work_items,
    }
    write_json(state, state_path)
    summary = package_experiment_suite_outputs(
        plan,
        state=state,
    )
    return Path(summary["metadata_path"]).resolve()


def _fixture_simulation_result(
    *,
    suite_cell: dict[str, Any],
    work_item: dict[str, Any],
    tmp_dir: Path,
    index: int,
) -> dict[str, Any]:
    stage_root = (tmp_dir / "fx" / f"w{index}" / "simulation").resolve()
    marker_path = stage_root / "simulation_marker.json"
    write_json(
        {
            "work_item_id": str(work_item["work_item_id"]),
            "suite_cell_id": str(suite_cell["suite_cell_id"]),
        },
        marker_path,
    )
    return {
        "status_detail": "fixture simulation stage completed",
        "summary": {"executed_runs": []},
        "downstream_artifacts": [
            _fixture_artifact(
                artifact_role_id=str(work_item["artifact_role_ids"][0]),
                artifact_id="simulation_marker",
                path=marker_path,
            )
        ],
    }


def _fixture_analysis_result(
    *,
    suite_cell: dict[str, Any],
    work_item: dict[str, Any],
    plan: dict[str, Any],
    tmp_dir: Path,
    index: int,
) -> dict[str, Any]:
    stage_root = (tmp_dir / "fx" / f"w{index}" / "analysis").resolve()
    summary_path = stage_root / "experiment_comparison_summary.json"
    expected_seeds = _review_cell_expected_seeds(
        plan=plan,
        suite_cell_id=str(suite_cell["suite_cell_id"]),
    )
    write_json(
        _analysis_summary_payload(suite_cell=suite_cell, expected_seeds=expected_seeds),
        summary_path,
    )
    return {
        "status_detail": "fixture analysis stage completed",
        "summary": {},
        "downstream_artifacts": [
            _fixture_artifact(
                artifact_role_id=str(work_item["artifact_role_ids"][0]),
                artifact_id="experiment_comparison_summary",
                path=summary_path,
                bundle_id=f"fixture_analysis:{suite_cell['suite_cell_id']}",
            )
        ],
    }


def _fixture_validation_result(
    *,
    suite_cell: dict[str, Any],
    work_item: dict[str, Any],
    tmp_dir: Path,
    index: int,
) -> dict[str, Any]:
    stage_root = (tmp_dir / "fx" / f"w{index}" / "validation").resolve()
    summary_path = stage_root / "validation_ladder_summary.json"
    findings_path = stage_root / "finding_rows.jsonl"
    summary_payload, finding_rows = _validation_payloads(suite_cell=suite_cell)
    write_json(summary_payload, summary_path)
    write_jsonl(finding_rows, findings_path)
    return {
        "status_detail": "fixture validation stage completed",
        "summary": {},
        "downstream_artifacts": [
            _fixture_artifact(
                artifact_role_id=str(work_item["artifact_role_ids"][0]),
                artifact_id="validation_ladder_summary",
                path=summary_path,
                bundle_id=f"fixture_validation:{suite_cell['suite_cell_id']}",
            ),
            _fixture_artifact(
                artifact_role_id=str(work_item["artifact_role_ids"][0]),
                artifact_id="finding_rows_jsonl",
                path=findings_path,
                bundle_id=f"fixture_validation:{suite_cell['suite_cell_id']}",
            ),
        ],
    }


def _fixture_artifact(
    *,
    artifact_role_id: str,
    artifact_id: str,
    path: Path,
    bundle_id: str | None = None,
) -> dict[str, object]:
    return {
        "artifact_role_id": artifact_role_id,
        "artifact_id": artifact_id,
        "artifact_kind": artifact_id,
        "path": str(path.resolve()),
        "status": "ready",
        "bundle_id": bundle_id,
        "format": f"fixture_{artifact_id}.v1",
    }


def _review_cell_expected_seeds(*, plan: dict[str, Any], suite_cell_id: str) -> list[int]:
    return sorted(
        int(item["simulation_seed"])
        for item in plan["cell_catalog"]
        if item.get("parent_cell_id") == suite_cell_id
        and item.get("simulation_seed") is not None
    )


def _analysis_summary_payload(
    *,
    suite_cell: dict[str, Any],
    expected_seeds: list[int],
) -> dict[str, Any]:
    direction = suite_cell["selected_dimension_values"]["motion_direction"]["value_id"]
    speed = suite_cell["selected_dimension_values"]["motion_speed"]["value_id"]
    contrast = suite_cell["selected_dimension_values"]["contrast_level"]["value_id"]
    noise = suite_cell["selected_dimension_values"]["noise_level"]["value_id"]
    ablation_family = (
        None
        if not suite_cell["ablation_references"]
        else str(suite_cell["ablation_references"][0]["ablation_family_id"])
    )

    direction_bonus = {"null": 0.03, "preferred": 0.12}[direction]
    speed_bonus = {"slow": 0.01, "fast": 0.05}[speed]
    contrast_bonus = {"low_contrast": -0.01, "high_contrast": 0.04}[contrast]
    noise_bonus = {"high_noise": -0.02, "low_noise": 0.02}[noise]
    base_level = 0.2 + direction_bonus + speed_bonus + contrast_bonus + noise_bonus
    shared_penalty = {"no_waves": -0.08, "shuffle_morphology": -0.03, None: 0.0}[ablation_family]
    latency_penalty = {"no_waves": 2.0, "shuffle_morphology": 0.75, None: 0.0}[ablation_family]
    wave_penalty = {"no_waves": -0.25, "shuffle_morphology": -0.12, None: 0.0}[ablation_family]

    group_specs = [
        (
            "matched_surface_wave_vs_p0__intact",
            "matched_surface_wave_vs_baseline",
            "surface_wave_minus_p0",
            0.06,
        ),
        (
            "geometry_ablation__p0",
            "geometry_ablation",
            "intact_minus_shuffled",
            0.03,
        ),
    ]
    metric_specs = [
        ("null_direction_suppression_index", "unitless"),
        ("response_latency_to_peak_ms", "ms"),
    ]
    group_metric_rollups: list[dict[str, Any]] = []
    for group_id, group_kind, comparison_semantics, group_bonus in group_specs:
        for metric_id, units in metric_specs:
            if metric_id == "null_direction_suppression_index":
                seed_values = [
                    base_level + group_bonus + shared_penalty + (offset * 0.002)
                    for offset in (-1, 0, 1)
                ]
                statistic = "normalized_peak_selectivity_index"
            else:
                seed_values = [
                    -6.0 - (direction_bonus * 5.0) - (speed_bonus * 3.0) + latency_penalty + (offset * 0.25)
                    for offset in (-1, 0, 1)
                ]
                statistic = "latency_to_peak_ms"
            group_metric_rollups.append(
                {
                    "group_id": group_id,
                    "group_kind": group_kind,
                    "comparison_semantics": comparison_semantics,
                    "metric_id": metric_id,
                    "readout_id": "shared_output_mean",
                    "window_id": "shared_response_window",
                    "statistic": statistic,
                    "units": units,
                    "seed_aggregation_rule_id": "manifest_seed_sweep_rollup",
                    "seed_count": len(expected_seeds),
                    "seeds": list(expected_seeds),
                    "summary_statistics": _summary_statistics(seed_values),
                    "sign_consistency": True,
                    "effect_direction": "positive" if np_mean(seed_values) >= 0.0 else "negative",
                    "baseline_family": None,
                    "topology_condition": "intact",
                }
            )

    wave_metric_rollups: list[dict[str, Any]] = []
    for metric_id, base_value in (
        ("wavefront_alignment_score", 0.75 + direction_bonus),
        ("phase_locking_index", 0.55 + speed_bonus),
    ):
        seed_values = [
            base_value + wave_penalty + (offset * 0.01) for offset in (-1, 0, 1)
        ]
        wave_metric_rollups.append(
            {
                "arm_id": "surface_wave_intact",
                "metric_id": metric_id,
                "seed_count": len(expected_seeds),
                "seeds": list(expected_seeds),
                "units": "unitless",
                "summary_statistics": _summary_statistics(seed_values),
            }
        )

    return {
        "summary_version": "fixture_suite_analysis.v1",
        "comparison_group_catalog": [
            {"group_id": group_id, "group_kind": group_kind}
            for group_id, group_kind, _, _ in group_specs
        ],
        "group_metric_rollups": group_metric_rollups,
        "wave_metric_rollups": wave_metric_rollups,
    }


def _validation_payloads(*, suite_cell: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ablation_family = (
        None
        if not suite_cell["ablation_references"]
        else str(suite_cell["ablation_references"][0]["ablation_family_id"])
    )
    overall_status = "review" if ablation_family == "no_waves" else "pass"
    finding_rows = [
        {
            "layer_id": "numerical_sanity",
            "layer_sequence_index": 0,
            "layer_bundle_id": f"fixture_layer:{suite_cell['suite_cell_id']}:numerical",
            "validator_id": "stability_envelope",
            "finding_id": f"{suite_cell['suite_cell_id']}::numerical",
            "status": "pass",
            "case_id": "numerical_case",
            "validator_family_id": "numerics",
            "arm_id": "surface_wave_intact",
            "root_id": "",
            "variant_id": "",
            "measured_quantity": "stability_margin",
            "measured_value": 0.95,
            "summary_json": {"status": "pass"},
            "comparison_basis_json": {"basis": "fixture"},
            "diagnostic_metadata_json": {"source": "fixture"},
        },
        {
            "layer_id": "task_sanity",
            "layer_sequence_index": 3,
            "layer_bundle_id": f"fixture_layer:{suite_cell['suite_cell_id']}:task",
            "validator_id": "shared_effect_reproducibility",
            "finding_id": f"{suite_cell['suite_cell_id']}::task",
            "status": "review" if ablation_family == "no_waves" else "pass",
            "case_id": "task_case",
            "validator_family_id": "task",
            "arm_id": "surface_wave_intact",
            "root_id": "",
            "variant_id": (
                ""
                if not suite_cell["ablation_references"]
                else str(suite_cell["ablation_references"][0]["variant_id"])
            ),
            "measured_quantity": "shared_effect_delta",
            "measured_value": -0.08 if ablation_family == "no_waves" else -0.03 if ablation_family == "shuffle_morphology" else 0.0,
            "summary_json": {"status": overall_status},
            "comparison_basis_json": {"basis": "base_vs_ablation"},
            "diagnostic_metadata_json": {"source": "fixture"},
        },
    ]
    if ablation_family == "no_waves":
        finding_rows.append(
            {
                "layer_id": "task_sanity",
                "layer_sequence_index": 3,
                "layer_bundle_id": f"fixture_layer:{suite_cell['suite_cell_id']}:task",
                "validator_id": "wave_diagnostic_presence",
                "finding_id": f"{suite_cell['suite_cell_id']}::wave",
                "status": "review",
                "case_id": "wave_case",
                "validator_family_id": "task",
                "arm_id": "surface_wave_intact",
                "root_id": "",
                "variant_id": "disabled",
                "measured_quantity": "wavefront_alignment_score",
                "measured_value": 0.5,
                "summary_json": {"status": "review"},
                "comparison_basis_json": {"basis": "wave diagnostics"},
                "diagnostic_metadata_json": {"source": "fixture"},
            }
        )

    layer_statuses = {
        "numerical_sanity": "pass",
        "task_sanity": overall_status,
    }
    validator_statuses = {
        "stability_envelope": "pass",
        "shared_effect_reproducibility": overall_status,
    }
    if ablation_family == "no_waves":
        validator_statuses["wave_diagnostic_presence"] = "review"
    return (
        {
            "overall_status": overall_status,
            "finding_count": len(finding_rows),
            "case_count": 2,
            "layer_statuses": layer_statuses,
            "validator_statuses": validator_statuses,
        },
        finding_rows,
    )


def _summary_statistics(values: list[float]) -> dict[str, float]:
    ordered = sorted(float(value) for value in values)
    mean_value = np_mean(ordered)
    median_value = ordered[len(ordered) // 2]
    if len(ordered) % 2 == 0:
        median_value = (ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]) / 2.0
    variance = sum((value - mean_value) ** 2 for value in ordered) / len(ordered)
    return {
        "mean": round(mean_value, 12),
        "median": round(median_value, 12),
        "min": round(min(ordered), 12),
        "max": round(max(ordered), 12),
        "std": round(variance**0.5, 12),
    }


def np_mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _analysis_summary_path_for_ablation(
    result_index: dict[str, Any],
    *,
    ablation_key: str,
) -> Path:
    target_cell = next(
        cell
        for cell in result_index["cell_records"]
        if list(cell["ablation_identity_ids"]) == [ablation_key]
    )
    stage_record = next(
        stage for stage in target_cell["stage_records"] if stage["stage_id"] == "analysis"
    )
    artifact = next(
        item
        for item in stage_record["artifacts"]
        if item["artifact_id"] == "experiment_comparison_summary"
    )
    return Path(artifact["path"]).resolve()


if __name__ == "__main__":
    unittest.main()
