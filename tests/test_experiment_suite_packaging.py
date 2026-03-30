from __future__ import annotations

import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.experiment_suite_contract import (
    ABLATION_VARIANT_LINEAGE_KIND,
    BASE_CONDITION_LINEAGE_KIND,
    WORK_ITEM_STATUS_BLOCKED,
    WORK_ITEM_STATUS_FAILED,
    WORK_ITEM_STATUS_SUCCEEDED,
)
from flywire_wave.experiment_suite_execution import (
    DEFAULT_EXECUTION_STATE_FILENAME,
    execute_experiment_suite_plan,
    load_experiment_suite_execution_state,
)
from flywire_wave.experiment_suite_packaging import (
    CELL_INVENTORY_CSV_ARTIFACT_ID,
    INVENTORY_REPORT_ARTIFACT_ID,
    RESULT_INDEX_ARTIFACT_ID,
    STAGE_ARTIFACT_INVENTORY_CSV_ARTIFACT_ID,
    discover_experiment_suite_package_cells,
    discover_experiment_suite_package_paths,
    discover_experiment_suite_stage_artifacts,
    load_experiment_suite_package_metadata,
    load_experiment_suite_result_index,
    package_experiment_suite_outputs,
)
from flywire_wave.experiment_suite_planning import resolve_experiment_suite_plan
from flywire_wave.io_utils import write_json

try:
    from tests.test_experiment_suite_execution import _minimal_execution_suite_block
except ModuleNotFoundError:
    from test_experiment_suite_execution import (  # type: ignore[no-redef]
        _minimal_execution_suite_block,
    )

try:
    from tests.test_experiment_suite_planning import _write_suite_manifest_fixture
except ModuleNotFoundError:
    from test_experiment_suite_planning import (  # type: ignore[no-redef]
        _write_suite_manifest_fixture,
    )

try:
    from tests.test_simulation_planning import (
        _record_fixture_stimulus_bundle,
        _write_manifest_fixture,
        _write_simulation_fixture,
    )
except ModuleNotFoundError:
    from test_simulation_planning import (  # type: ignore[no-redef]
        _record_fixture_stimulus_bundle,
        _write_manifest_fixture,
        _write_simulation_fixture,
    )


class ExperimentSuitePackagingTest(unittest.TestCase):
    def test_fixture_workflow_packages_deterministic_inventory_for_successful_and_incomplete_cells(
        self,
    ) -> None:
        schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
        design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            manifest_path = _write_manifest_fixture(
                tmp_dir,
                manifest_overrides={"seed_sweep": [11], "random_seed": 11},
            )
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
                suite_block=_minimal_execution_suite_block(
                    output_root=tmp_dir / "out" / "suite_packaging"
                ),
            )
            plan = resolve_experiment_suite_plan(
                config_path=config_path,
                suite_manifest_path=suite_manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )
            failing_work_item_id = next(
                item["work_item_id"]
                for item in plan["work_item_catalog"]
                if item["stage_id"] == "simulation"
                and "__no_waves__disabled__seed_11" in item["suite_cell_id"]
            )

            summary = execute_experiment_suite_plan(
                plan,
                stage_executors={
                    "simulation": _fixture_packaging_stage_executor(
                        "simulation",
                        fail_work_item_id=failing_work_item_id,
                    ),
                    "analysis": _fixture_packaging_stage_executor("analysis"),
                    "validation": _fixture_packaging_stage_executor("validation"),
                    "dashboard": _fixture_packaging_stage_executor("dashboard"),
                },
            )

            self.assertEqual(summary["overall_status"], WORK_ITEM_STATUS_FAILED)
            package_summary = summary["package"]
            metadata_path = Path(package_summary["metadata_path"]).resolve()
            result_index_path = Path(package_summary["result_index_path"]).resolve()
            self.assertTrue(metadata_path.exists())
            self.assertTrue(result_index_path.exists())

            package_metadata = load_experiment_suite_package_metadata(metadata_path)
            result_index = load_experiment_suite_result_index(package_metadata)
            discovered_paths = discover_experiment_suite_package_paths(package_metadata)

            self.assertEqual(discovered_paths[RESULT_INDEX_ARTIFACT_ID], result_index_path)
            self.assertEqual(
                discovered_paths[CELL_INVENTORY_CSV_ARTIFACT_ID].name,
                "cell_inventory.csv",
            )
            self.assertEqual(
                discovered_paths[STAGE_ARTIFACT_INVENTORY_CSV_ARTIFACT_ID].name,
                "stage_artifacts.csv",
            )
            self.assertEqual(
                discovered_paths[INVENTORY_REPORT_ARTIFACT_ID].name,
                "inventory.md",
            )
            self.assertEqual(
                metadata_path,
                (
                    Path(plan["output_roots"]["suite_root"]).resolve()
                    / "package"
                    / "experiment_suite_package.json"
                ).resolve(),
            )
            self.assertEqual(
                result_index_path,
                (
                    Path(plan["output_roots"]["suite_root"]).resolve()
                    / "package"
                    / "indexes"
                    / "result_index.json"
                ).resolve(),
            )

            blocked_cells = discover_experiment_suite_package_cells(
                package_metadata,
                lineage_kind=ABLATION_VARIANT_LINEAGE_KIND,
                overall_status=WORK_ITEM_STATUS_BLOCKED,
            )
            succeeded_base_cells = discover_experiment_suite_package_cells(
                package_metadata,
                lineage_kind=BASE_CONDITION_LINEAGE_KIND,
                overall_status=WORK_ITEM_STATUS_SUCCEEDED,
            )

            self.assertEqual(len(blocked_cells), 1)
            self.assertEqual(len(succeeded_base_cells), 1)

            blocked_ablation = blocked_cells[0]
            successful_base = succeeded_base_cells[0]

            self.assertEqual(
                blocked_ablation["ablation_identity_ids"],
                ["no_waves:disabled"],
            )
            self.assertEqual(
                blocked_ablation["stage_records"][0]["stage_id"],
                "analysis",
            )
            self.assertEqual(
                blocked_ablation["stage_records"][0]["status"],
                WORK_ITEM_STATUS_BLOCKED,
            )
            planned_output_root = Path(
                blocked_ablation["stage_records"][0]["planned_output_root"]
            )
            self.assertEqual(planned_output_root.name, "analysis")
            self.assertTrue(planned_output_root.parent.name.startswith("cell_"))
            self.assertEqual(
                blocked_ablation["simulation_lineage_cells"][0]["overall_status"],
                WORK_ITEM_STATUS_FAILED,
            )
            self.assertEqual(
                blocked_ablation["simulation_lineage_cells"][0]["stage_records"][0]["status"],
                WORK_ITEM_STATUS_FAILED,
            )
            self.assertEqual(
                blocked_ablation["simulation_lineage_artifacts"],
                [],
            )

            self.assertEqual(
                successful_base["overall_status"],
                WORK_ITEM_STATUS_SUCCEEDED,
            )
            self.assertEqual(
                [
                    stage_record["status"] for stage_record in successful_base["stage_records"]
                ],
                [
                    WORK_ITEM_STATUS_SUCCEEDED,
                    WORK_ITEM_STATUS_SUCCEEDED,
                    WORK_ITEM_STATUS_SUCCEEDED,
                ],
            )
            self.assertEqual(
                successful_base["simulation_lineage_cells"][0]["overall_status"],
                WORK_ITEM_STATUS_SUCCEEDED,
            )
            self.assertEqual(
                len(successful_base["simulation_lineage_artifacts"]),
                14,
            )
            self.assertTrue(
                any(
                    Path(path).name == "analysis_report.html"
                    for path in successful_base["report_artifact_paths"]
                )
            )
            self.assertTrue(
                any(
                    artifact["artifact_id"] == "metrics_table"
                    for artifact in successful_base["simulation_lineage_artifacts"]
                )
            )

            review_artifacts = discover_experiment_suite_stage_artifacts(
                package_metadata,
                suite_cell_id=successful_base["suite_cell_id"],
                inventory_category="review_artifact",
            )
            summary_tables = discover_experiment_suite_stage_artifacts(
                package_metadata,
                suite_cell_id=successful_base["suite_cell_id"],
                inventory_category="summary_table",
            )
            self.assertTrue(
                any(Path(item["path"]).name == "analysis_report.html" for item in review_artifacts)
            )
            self.assertTrue(
                any(Path(item["path"]).name == "validation_report.md" for item in review_artifacts)
            )
            self.assertTrue(
                any(Path(item["path"]).name == "task_summary_rows.json" for item in summary_tables)
            )

            state_path = (
                Path(plan["output_roots"]["suite_root"]).resolve()
                / DEFAULT_EXECUTION_STATE_FILENAME
            )
            state = load_experiment_suite_execution_state(state_path)
            second_package = package_experiment_suite_outputs(plan, state=state)
            self.assertEqual(second_package["metadata_path"], package_summary["metadata_path"])
            self.assertEqual(second_package["result_index_path"], package_summary["result_index_path"])
            self.assertEqual(
                load_experiment_suite_result_index(second_package["result_index_path"]),
                result_index,
            )


def _fixture_packaging_stage_executor(
    stage_id: str,
    *,
    fail_work_item_id: str | None = None,
):
    def execute(context: dict[str, object]) -> dict[str, object]:
        work_item = context["work_item"]
        work_item_id = str(work_item["work_item_id"])
        if fail_work_item_id is not None and work_item_id == fail_work_item_id:
            raise RuntimeError(f"fixture failure for {work_item_id}")

        workspace_root = Path(str(context["workspace_root"])).resolve()
        stage_root = (workspace_root / "fixture_stage_outputs" / work_item_id).resolve()
        if stage_id == "simulation":
            return _write_fixture_simulation_outputs(
                stage_root=stage_root,
                work_item_id=work_item_id,
                suite_cell_id=str(work_item["suite_cell_id"]),
                artifact_role_id=str(work_item["artifact_role_ids"][0]),
            )
        if stage_id == "analysis":
            return _write_fixture_analysis_outputs(
                stage_root=stage_root,
                work_item_id=work_item_id,
                suite_cell_id=str(work_item["suite_cell_id"]),
                artifact_role_id=str(work_item["artifact_role_ids"][0]),
            )
        if stage_id == "validation":
            return _write_fixture_validation_outputs(
                stage_root=stage_root,
                work_item_id=work_item_id,
                suite_cell_id=str(work_item["suite_cell_id"]),
                artifact_role_id=str(work_item["artifact_role_ids"][0]),
            )
        if stage_id == "dashboard":
            return _write_fixture_dashboard_outputs(
                stage_root=stage_root,
                work_item_id=work_item_id,
                suite_cell_id=str(work_item["suite_cell_id"]),
                artifact_role_id=str(work_item["artifact_role_ids"][0]),
            )
        raise AssertionError(f"unexpected fixture stage {stage_id!r}")

    return execute


def _write_fixture_simulation_outputs(
    *,
    stage_root: Path,
    work_item_id: str,
    suite_cell_id: str,
    artifact_role_id: str,
) -> dict[str, object]:
    downstream_artifacts: list[dict[str, object]] = []
    executed_runs: list[dict[str, object]] = []
    for arm_id in ("baseline_fixture", "surface_wave_fixture"):
        run_hash = hashlib.sha256(f"{work_item_id}:{arm_id}".encode("utf-8")).hexdigest()
        run_root = stage_root / arm_id
        metadata_path = run_root / "simulator_result_bundle.json"
        readout_traces_path = run_root / "readout_traces.npz"
        metrics_table_path = run_root / "metrics.csv"
        state_summary_path = run_root / "state_summary.json"
        structured_log_path = run_root / "structured_log.jsonl"
        provenance_path = run_root / "execution_provenance.json"
        ui_payload_path = run_root / "ui_comparison_payload.json"

        _write_fixture_json(
            metadata_path,
            {
                "contract_version": "fixture_simulator_result_bundle.v1",
                "bundle_id": f"simulator_result_bundle.v1:{suite_cell_id}:{arm_id}:{run_hash}",
                "suite_cell_id": suite_cell_id,
                "arm_id": arm_id,
            },
        )
        _write_fixture_text(readout_traces_path, "fixture traces\n")
        _write_fixture_text(metrics_table_path, "metric_id,value\nshared_response,1.0\n")
        _write_fixture_json(state_summary_path, {"stage": "simulation", "arm_id": arm_id})
        _write_fixture_text(structured_log_path, "{\"event\":\"step\"}\n")
        _write_fixture_json(provenance_path, {"source": "fixture"})
        _write_fixture_json(ui_payload_path, {"view": "fixture"})

        bundle_id = f"simulator_result_bundle.v1:{suite_cell_id}:{arm_id}:{run_hash}"
        executed_runs.append(
            {
                "bundle_id": bundle_id,
                "arm_id": arm_id,
                "run_spec_hash": run_hash,
                "metadata_path": str(metadata_path.resolve()),
                "readout_traces_path": str(readout_traces_path.resolve()),
                "metrics_table_path": str(metrics_table_path.resolve()),
                "state_summary_path": str(state_summary_path.resolve()),
                "structured_log_path": str(structured_log_path.resolve()),
                "provenance_path": str(provenance_path.resolve()),
                "ui_payload_path": str(ui_payload_path.resolve()),
            }
        )
        downstream_artifacts.extend(
            [
                _fixture_artifact(
                    artifact_role_id=artifact_role_id,
                    artifact_kind="metadata_json",
                    path=metadata_path,
                    contract_version="simulator_result_bundle.v1",
                    bundle_id=bundle_id,
                    format="json_fixture_simulator_metadata.v1",
                ),
                _fixture_artifact(
                    artifact_role_id=artifact_role_id,
                    artifact_kind="readout_traces",
                    path=readout_traces_path,
                    contract_version="simulator_result_bundle.v1",
                    bundle_id=bundle_id,
                    format="npz_fixture_readout_traces.v1",
                ),
                _fixture_artifact(
                    artifact_role_id=artifact_role_id,
                    artifact_kind="metrics_table",
                    path=metrics_table_path,
                    contract_version="simulator_result_bundle.v1",
                    bundle_id=bundle_id,
                    format="csv_fixture_metrics_table.v1",
                ),
                _fixture_artifact(
                    artifact_role_id=artifact_role_id,
                    artifact_kind="state_summary",
                    path=state_summary_path,
                    contract_version="simulator_result_bundle.v1",
                    bundle_id=bundle_id,
                    format="json_fixture_state_summary.v1",
                ),
                _fixture_artifact(
                    artifact_role_id=artifact_role_id,
                    artifact_kind="structured_log",
                    path=structured_log_path,
                    contract_version="simulator_result_bundle.v1",
                    bundle_id=bundle_id,
                    format="jsonl_fixture_structured_log.v1",
                ),
                _fixture_artifact(
                    artifact_role_id=artifact_role_id,
                    artifact_kind="execution_provenance",
                    path=provenance_path,
                    contract_version="simulator_result_bundle.v1",
                    bundle_id=bundle_id,
                    format="json_fixture_execution_provenance.v1",
                ),
                _fixture_artifact(
                    artifact_role_id=artifact_role_id,
                    artifact_kind="ui_comparison_payload",
                    path=ui_payload_path,
                    contract_version="simulator_result_bundle.v1",
                    bundle_id=bundle_id,
                    format="json_fixture_ui_payload.v1",
                ),
            ]
        )

    return {
        "status": WORK_ITEM_STATUS_SUCCEEDED,
        "status_detail": "fixture simulation stage completed",
        "summary": {
            "executed_run_count": len(executed_runs),
            "executed_runs": executed_runs,
        },
        "downstream_artifacts": downstream_artifacts,
    }


def _write_fixture_analysis_outputs(
    *,
    stage_root: Path,
    work_item_id: str,
    suite_cell_id: str,
    artifact_role_id: str,
) -> dict[str, object]:
    bundle_hash = hashlib.sha256(f"{work_item_id}:analysis".encode("utf-8")).hexdigest()
    bundle_id = f"experiment_analysis_bundle.v1:{suite_cell_id}:{bundle_hash}"
    report_root = stage_root / "report"

    metadata_path = stage_root / "experiment_analysis_bundle.json"
    comparison_summary_path = stage_root / "experiment_comparison_summary.json"
    task_summary_rows_path = stage_root / "task_summary_rows.json"
    null_test_table_path = stage_root / "null_test_table.json"
    comparison_matrices_path = stage_root / "comparison_matrices.json"
    visualization_catalog_path = stage_root / "visualization_catalog.json"
    analysis_ui_payload_path = stage_root / "analysis_ui_payload.json"
    report_path = report_root / "analysis_report.html"
    report_summary_path = report_root / "summary.json"

    _write_fixture_json(metadata_path, {"bundle_id": bundle_id, "suite_cell_id": suite_cell_id})
    _write_fixture_json(comparison_summary_path, {"kind": "comparison_summary"})
    _write_fixture_json(task_summary_rows_path, {"kind": "task_summary_rows"})
    _write_fixture_json(null_test_table_path, {"kind": "null_test_table"})
    _write_fixture_json(comparison_matrices_path, {"kind": "comparison_matrices"})
    _write_fixture_json(visualization_catalog_path, {"kind": "visualization_catalog"})
    _write_fixture_json(analysis_ui_payload_path, {"kind": "analysis_ui_payload"})
    _write_fixture_text(report_path, "<html><body>fixture analysis report</body></html>\n")
    _write_fixture_json(report_summary_path, {"kind": "report_summary"})

    return {
        "status": WORK_ITEM_STATUS_SUCCEEDED,
        "status_detail": "fixture analysis stage completed",
        "summary": {
            "metadata_path": str(metadata_path.resolve()),
            "bundle_id": bundle_id,
            "bundle_directory": str(stage_root.resolve()),
            "report_path": str(report_path.resolve()),
        },
        "downstream_artifacts": [
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="metadata_json",
                path=metadata_path,
                contract_version="experiment_analysis_bundle.v1",
                bundle_id=bundle_id,
                format="json_fixture_analysis_metadata.v1",
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="experiment_comparison_summary",
                path=comparison_summary_path,
                contract_version="experiment_analysis_bundle.v1",
                bundle_id=bundle_id,
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="task_summary_rows",
                path=task_summary_rows_path,
                contract_version="experiment_analysis_bundle.v1",
                bundle_id=bundle_id,
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="null_test_table",
                path=null_test_table_path,
                contract_version="experiment_analysis_bundle.v1",
                bundle_id=bundle_id,
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="comparison_matrices",
                path=comparison_matrices_path,
                contract_version="experiment_analysis_bundle.v1",
                bundle_id=bundle_id,
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="visualization_catalog",
                path=visualization_catalog_path,
                contract_version="experiment_analysis_bundle.v1",
                bundle_id=bundle_id,
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="analysis_ui_payload",
                path=analysis_ui_payload_path,
                contract_version="experiment_analysis_bundle.v1",
                bundle_id=bundle_id,
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="offline_report_index",
                path=report_path,
                contract_version="experiment_analysis_bundle.v1",
                bundle_id=bundle_id,
                format="html_fixture_analysis_report.v1",
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="offline_report_summary",
                path=report_summary_path,
                contract_version="experiment_analysis_bundle.v1",
                bundle_id=bundle_id,
            ),
        ],
    }


def _write_fixture_validation_outputs(
    *,
    stage_root: Path,
    work_item_id: str,
    suite_cell_id: str,
    artifact_role_id: str,
) -> dict[str, object]:
    numerical_metadata_path = stage_root / "numerical_sanity" / "validation_bundle.json"
    numerical_summary_path = stage_root / "numerical_sanity" / "validation_summary.json"
    numerical_report_path = stage_root / "numerical_sanity" / "report" / "validation_report.md"
    task_metadata_path = stage_root / "task_sanity" / "validation_bundle.json"
    task_summary_path = stage_root / "task_sanity" / "validation_summary.json"
    task_report_path = stage_root / "task_sanity" / "report" / "validation_report.md"
    package_metadata_path = stage_root / "package" / "validation_ladder_package.json"
    package_summary_path = stage_root / "package" / "validation_ladder_summary.json"
    package_report_path = stage_root / "package" / "report" / "validation_report.md"
    finding_rows_csv_path = stage_root / "package" / "exports" / "finding_rows.csv"

    _write_fixture_json(numerical_metadata_path, {"layer_id": "numerical_sanity"})
    _write_fixture_json(numerical_summary_path, {"status": "pass"})
    _write_fixture_text(numerical_report_path, "numerical fixture report\n")
    _write_fixture_json(task_metadata_path, {"layer_id": "task_sanity"})
    _write_fixture_json(task_summary_path, {"status": "review"})
    _write_fixture_text(task_report_path, "task fixture report\n")
    _write_fixture_json(package_metadata_path, {"bundle_id": f"validation_ladder_package.v1:{suite_cell_id}:{hashlib.sha256(work_item_id.encode('utf-8')).hexdigest()}"})
    _write_fixture_json(package_summary_path, {"overall_status": "review"})
    _write_fixture_text(package_report_path, "packaged validation report\n")
    _write_fixture_text(
        finding_rows_csv_path,
        "layer_id,status\nnumerical_sanity,pass\ntask_sanity,review\n",
    )

    numerical_bundle_id = f"validation_ladder.v1:{suite_cell_id}:numerical"
    task_bundle_id = f"validation_ladder.v1:{suite_cell_id}:task"
    package_bundle_id = (
        f"validation_ladder_package.v1:{suite_cell_id}:"
        f"{hashlib.sha256(f'{work_item_id}:package'.encode('utf-8')).hexdigest()}"
    )
    return {
        "status": WORK_ITEM_STATUS_SUCCEEDED,
        "status_detail": "fixture validation stage completed",
        "summary": {
            "layer_results": {
                "numerical_sanity": {
                    "metadata_path": str(numerical_metadata_path.resolve()),
                    "bundle_id": numerical_bundle_id,
                },
                "task_sanity": {
                    "metadata_path": str(task_metadata_path.resolve()),
                    "bundle_id": task_bundle_id,
                },
            },
            "packaged_validation_ladder": {
                "metadata_path": str(package_metadata_path.resolve()),
                "bundle_id": package_bundle_id,
                "summary_path": str(package_summary_path.resolve()),
                "report_path": str(package_report_path.resolve()),
            },
            "dashboard_validation_bundle_metadata_path": str(task_metadata_path.resolve()),
        },
        "downstream_artifacts": [
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="metadata_json",
                path=numerical_metadata_path,
                contract_version="validation_ladder.v1",
                bundle_id=numerical_bundle_id,
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="validation_summary",
                path=numerical_summary_path,
                contract_version="validation_ladder.v1",
                bundle_id=numerical_bundle_id,
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="offline_review_report",
                path=numerical_report_path,
                contract_version="validation_ladder.v1",
                bundle_id=numerical_bundle_id,
                format="md_fixture_validation_report.v1",
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="metadata_json",
                path=task_metadata_path,
                contract_version="validation_ladder.v1",
                bundle_id=task_bundle_id,
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="validation_summary",
                path=task_summary_path,
                contract_version="validation_ladder.v1",
                bundle_id=task_bundle_id,
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="offline_review_report",
                path=task_report_path,
                contract_version="validation_ladder.v1",
                bundle_id=task_bundle_id,
                format="md_fixture_validation_report.v1",
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="metadata_json",
                path=package_metadata_path,
                contract_version="validation_ladder_package.v1",
                bundle_id=package_bundle_id,
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="validation_ladder_summary",
                path=package_summary_path,
                contract_version="validation_ladder_package.v1",
                bundle_id=package_bundle_id,
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="finding_rows_csv",
                path=finding_rows_csv_path,
                contract_version="validation_ladder_package.v1",
                bundle_id=package_bundle_id,
                format="csv_fixture_validation_findings.v1",
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="offline_review_report",
                path=package_report_path,
                contract_version="validation_ladder_package.v1",
                bundle_id=package_bundle_id,
                format="md_fixture_validation_package_report.v1",
            ),
        ],
    }


def _write_fixture_dashboard_outputs(
    *,
    stage_root: Path,
    work_item_id: str,
    suite_cell_id: str,
    artifact_role_id: str,
) -> dict[str, object]:
    bundle_hash = hashlib.sha256(f"{work_item_id}:dashboard".encode("utf-8")).hexdigest()
    bundle_id = f"dashboard_session.v1:{suite_cell_id}:{bundle_hash}"
    metadata_path = stage_root / "dashboard_session.json"
    payload_path = stage_root / "dashboard_session_payload.json"
    state_path = stage_root / "session_state.json"
    app_shell_path = stage_root / "app" / "index.html"

    _write_fixture_json(metadata_path, {"bundle_id": bundle_id})
    _write_fixture_json(payload_path, {"kind": "dashboard_payload"})
    _write_fixture_json(state_path, {"kind": "dashboard_state"})
    _write_fixture_text(app_shell_path, "<html><body>fixture dashboard</body></html>\n")

    return {
        "status": WORK_ITEM_STATUS_SUCCEEDED,
        "status_detail": "fixture dashboard stage completed",
        "summary": {
            "metadata_path": str(metadata_path.resolve()),
            "bundle_id": bundle_id,
            "app_shell_path": str(app_shell_path.resolve()),
        },
        "downstream_artifacts": [
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="metadata_json",
                path=metadata_path,
                contract_version="dashboard_session.v1",
                bundle_id=bundle_id,
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="session_payload",
                path=payload_path,
                contract_version="dashboard_session.v1",
                bundle_id=bundle_id,
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="session_state",
                path=state_path,
                contract_version="dashboard_session.v1",
                bundle_id=bundle_id,
            ),
            _fixture_artifact(
                artifact_role_id=artifact_role_id,
                artifact_kind="app_shell_index",
                path=app_shell_path,
                contract_version="dashboard_session.v1",
                bundle_id=bundle_id,
                format="html_fixture_dashboard_shell.v1",
            ),
        ],
    }


def _fixture_artifact(
    *,
    artifact_role_id: str,
    artifact_kind: str,
    path: Path,
    contract_version: str,
    bundle_id: str,
    format: str | None = None,
) -> dict[str, object]:
    return {
        "artifact_role_id": artifact_role_id,
        "artifact_kind": artifact_kind,
        "artifact_id": artifact_kind,
        "path": str(path.resolve()),
        "status": "ready",
        "contract_version": contract_version,
        "bundle_id": bundle_id,
        "format": (
            f"fixture_{artifact_kind}.v1"
            if format is None
            else format
        ),
    }


def _write_fixture_json(path: Path, payload: dict[str, object]) -> None:
    write_json(copy.deepcopy(payload), path)


def _write_fixture_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
