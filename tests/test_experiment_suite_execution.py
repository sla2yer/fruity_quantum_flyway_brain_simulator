from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.experiment_suite_contract import (
    ABLATION_VARIANT_LINEAGE_KIND,
    BASE_CONDITION_LINEAGE_KIND,
    SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
    SEED_REPLICATE_LINEAGE_KIND,
    WORK_ITEM_STATUS_BLOCKED,
    WORK_ITEM_STATUS_FAILED,
    WORK_ITEM_STATUS_SUCCEEDED,
)
from flywire_wave.experiment_suite_execution import (
    DEFAULT_EXECUTION_STATE_FILENAME,
    _build_materialized_manifest_payload,
    build_experiment_suite_execution_schedule,
    execute_experiment_suite_plan,
    load_experiment_suite_execution_state,
)
from flywire_wave.experiment_suite_planning import resolve_experiment_suite_plan
from flywire_wave.io_utils import write_json

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


class ExperimentSuiteExecutionTest(unittest.TestCase):
    def test_dry_run_and_resume_preserve_stable_schedule_and_status_state(self) -> None:
        schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
        design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            manifest_path = _write_manifest_fixture(
                tmp_dir,
                manifest_overrides={"seed_sweep": [11, 17], "random_seed": 11},
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
                    output_root=tmp_dir / "out" / "suite_execution"
                ),
            )
            plan = resolve_experiment_suite_plan(
                config_path=config_path,
                suite_manifest_path=suite_manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )

            schedule = build_experiment_suite_execution_schedule(plan)
            work_item_order = [item["work_item_id"] for item in schedule["schedule"]]
            stage_ids = [item["stage_id"] for item in schedule["schedule"]]
            self.assertEqual(
                stage_ids,
                ["simulation", "simulation", "simulation", "simulation"]
                + ["analysis", "analysis"]
                + ["validation", "validation"]
                + ["dashboard", "dashboard"],
            )

            cells_by_id = {
                item["suite_cell_id"]: item for item in plan["cell_catalog"]
            }
            simulation_lineages = [
                cells_by_id[item["suite_cell_id"]]["lineage_kind"]
                for item in schedule["schedule"][:4]
            ]
            self.assertEqual(
                simulation_lineages,
                [
                    SEED_REPLICATE_LINEAGE_KIND,
                    SEED_REPLICATE_LINEAGE_KIND,
                    SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
                    SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
                ],
            )
            self.assertEqual(
                [
                    cells_by_id[item["suite_cell_id"]]["simulation_seed"]
                    for item in schedule["schedule"][:4]
                ],
                [11, 17, 11, 17],
            )
            self.assertEqual(
                [
                    cells_by_id[item["suite_cell_id"]]["lineage_kind"]
                    for item in schedule["schedule"][4:6]
                ],
                [BASE_CONDITION_LINEAGE_KIND, ABLATION_VARIANT_LINEAGE_KIND],
            )

            state_path = (
                Path(plan["output_roots"]["suite_root"]) / DEFAULT_EXECUTION_STATE_FILENAME
            ).resolve()
            stage_call_log: list[str] = []
            failure_state = {"fired": False}
            failed_work_item_id = schedule["schedule"][3]["work_item_id"]

            stage_executors = {
                "simulation": _fixture_stage_executor(
                    "simulation",
                    call_log=stage_call_log,
                    failure_state=failure_state,
                    fail_once_work_item_id=failed_work_item_id,
                ),
                "analysis": _fixture_stage_executor(
                    "analysis",
                    call_log=stage_call_log,
                ),
                "validation": _fixture_stage_executor(
                    "validation",
                    call_log=stage_call_log,
                ),
                "dashboard": _fixture_stage_executor(
                    "dashboard",
                    call_log=stage_call_log,
                ),
            }

            dry_run = execute_experiment_suite_plan(
                plan,
                dry_run=True,
                stage_executors=stage_executors,
            )
            self.assertFalse(state_path.exists())
            self.assertEqual(dry_run["work_item_order"], work_item_order)
            self.assertTrue(all(item["action"] == "would_execute" for item in dry_run["schedule"]))

            first_run = execute_experiment_suite_plan(
                plan,
                stage_executors=stage_executors,
            )
            self.assertEqual(first_run["overall_status"], WORK_ITEM_STATUS_FAILED)
            self.assertTrue(state_path.exists())

            first_state = load_experiment_suite_execution_state(state_path)
            records_by_id = {
                item["work_item_id"]: item for item in first_state["work_items"]
            }
            self.assertEqual(
                records_by_id[failed_work_item_id]["status"],
                WORK_ITEM_STATUS_FAILED,
            )
            self.assertIn(
                failed_work_item_id,
                records_by_id[schedule["schedule"][5]["work_item_id"]]["status_detail"],
            )
            self.assertEqual(
                records_by_id[schedule["schedule"][5]["work_item_id"]]["status"],
                WORK_ITEM_STATUS_BLOCKED,
            )
            self.assertEqual(first_state["status_counts"][WORK_ITEM_STATUS_SUCCEEDED], 6)
            self.assertEqual(first_state["status_counts"][WORK_ITEM_STATUS_FAILED], 1)
            self.assertEqual(first_state["status_counts"][WORK_ITEM_STATUS_BLOCKED], 3)
            self.assertEqual(
                records_by_id[schedule["schedule"][4]["work_item_id"]]["attempt_count"],
                1,
            )
            self.assertEqual(
                records_by_id[schedule["schedule"][5]["work_item_id"]]["attempt_count"],
                1,
            )
            self.assertTrue(
                Path(records_by_id[schedule["schedule"][0]["work_item_id"]]["materialized_manifest_path"]).exists()
            )
            self.assertTrue(
                Path(records_by_id[schedule["schedule"][0]["work_item_id"]]["materialized_config_path"]).exists()
            )

            stage_call_log.clear()
            second_run = execute_experiment_suite_plan(
                plan,
                stage_executors=stage_executors,
            )
            self.assertEqual(second_run["overall_status"], WORK_ITEM_STATUS_SUCCEEDED)
            second_state = load_experiment_suite_execution_state(state_path)
            records_by_id = {
                item["work_item_id"]: item for item in second_state["work_items"]
            }
            self.assertTrue(
                all(
                    item["status"] == WORK_ITEM_STATUS_SUCCEEDED
                    for item in second_state["work_items"]
                )
            )
            self.assertEqual(
                records_by_id[failed_work_item_id]["attempt_count"],
                2,
            )
            self.assertEqual(
                records_by_id[schedule["schedule"][4]["work_item_id"]]["attempt_count"],
                1,
            )
            self.assertEqual(
                records_by_id[schedule["schedule"][5]["work_item_id"]]["attempt_count"],
                2,
            )
            self.assertEqual(
                stage_call_log,
                [
                    failed_work_item_id,
                    schedule["schedule"][5]["work_item_id"],
                    schedule["schedule"][7]["work_item_id"],
                    schedule["schedule"][9]["work_item_id"],
                ],
            )

    def test_materialized_manifests_push_suite_seed_lineage_into_comparison_arms(self) -> None:
        schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
        design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            manifest_path = _write_manifest_fixture(
                tmp_dir,
                manifest_overrides={"seed_sweep": [11, 17], "random_seed": 11},
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
                    output_root=tmp_dir / "out" / "suite_execution"
                ),
            )
            plan = resolve_experiment_suite_plan(
                config_path=config_path,
                suite_manifest_path=suite_manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )
            schedule = build_experiment_suite_execution_schedule(plan)

            seed_entry = next(
                item
                for item in schedule["schedule"]
                if item["stage_id"] == "simulation"
                and item["suite_cell_id"].endswith("__seed_17")
                and "__no_waves__disabled__" not in item["suite_cell_id"]
            )
            seed_manifest = _build_materialized_manifest_payload(
                plan=plan,
                schedule_entry=seed_entry,
            )
            self.assertEqual(seed_manifest["seed_sweep"], [17])
            self.assertEqual(seed_manifest["random_seed"], 17)
            self.assertTrue(
                all(arm["random_seed"] == 17 for arm in seed_manifest["comparison_arms"])
            )

            base_entry = next(
                item
                for item in schedule["schedule"]
                if item["stage_id"] == "analysis"
                and "__no_waves__disabled__" not in item["suite_cell_id"]
            )
            base_manifest = _build_materialized_manifest_payload(
                plan=plan,
                schedule_entry=base_entry,
            )
            self.assertEqual(base_manifest["seed_sweep"], [11, 17])
            self.assertEqual(base_manifest["random_seed"], 11)
            self.assertTrue(
                all(arm["random_seed"] == 11 for arm in base_manifest["comparison_arms"])
            )

    def test_stage_context_reuses_one_resolved_simulation_plan_per_suite_cell(self) -> None:
        schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
        design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            manifest_path = _write_manifest_fixture(
                tmp_dir,
                manifest_overrides={"seed_sweep": [11, 17], "random_seed": 11},
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
                    output_root=tmp_dir / "out" / "suite_execution"
                ),
            )
            plan = resolve_experiment_suite_plan(
                config_path=config_path,
                suite_manifest_path=suite_manifest_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )
            schedule = build_experiment_suite_execution_schedule(plan)
            simulation_plan_ids: dict[tuple[str, str], int] = {}

            def stage_executor(stage_id: str):
                def execute(context: dict[str, object]) -> dict[str, object]:
                    work_item = dict(context["work_item"])
                    suite_cell_id = str(work_item["suite_cell_id"])
                    if stage_id in {"simulation", "analysis", "validation"}:
                        simulation_plan_ids[(suite_cell_id, stage_id)] = id(
                            context["simulation_plan"]
                        )
                    artifact_path = (
                        Path(str(context["workspace_root"]))
                        / "fixture_stage_outputs"
                        / f"{work_item['work_item_id']}.json"
                    ).resolve()
                    write_json(
                        {
                            "stage_id": stage_id,
                            "suite_cell_id": suite_cell_id,
                            "work_item_id": str(work_item["work_item_id"]),
                        },
                        artifact_path,
                    )
                    summary: dict[str, object] = {
                        "metadata_path": str(artifact_path),
                    }
                    if stage_id == "validation":
                        summary["dashboard_validation_bundle_metadata_path"] = str(
                            artifact_path
                        )
                    return {
                        "status": WORK_ITEM_STATUS_SUCCEEDED,
                        "status_detail": f"{stage_id} complete",
                        "summary": summary,
                        "downstream_artifacts": [
                            {
                                "path": str(artifact_path),
                                "artifact_role_id": str(work_item["artifact_role_ids"][0]),
                                "artifact_kind": f"{stage_id}_metadata",
                                "status": "ready",
                            }
                        ],
                    }

                return execute

            import flywire_wave.simulation_planning as simulation_planning

            original_resolve = simulation_planning.resolve_manifest_simulation_plan
            resolve_calls: list[tuple[str, str]] = []

            def counting_resolve(*args, **kwargs):
                resolve_calls.append(
                    (
                        str(Path(kwargs["manifest_path"]).resolve()),
                        str(Path(kwargs["config_path"]).resolve()),
                    )
                )
                return original_resolve(*args, **kwargs)

            with mock.patch(
                "flywire_wave.simulation_planning.resolve_manifest_simulation_plan",
                side_effect=counting_resolve,
            ):
                execute_experiment_suite_plan(
                    plan,
                    stage_executors={
                        "simulation": stage_executor("simulation"),
                        "analysis": stage_executor("analysis"),
                        "validation": stage_executor("validation"),
                        "dashboard": stage_executor("dashboard"),
                    },
                )

            expected_resolve_count = len(
                {
                    str(entry["suite_cell_id"])
                    for entry in schedule["schedule"]
                    if entry["stage_id"] in {"simulation", "analysis", "validation"}
                }
            )
            self.assertEqual(len(resolve_calls), expected_resolve_count)

            for suite_cell_id in {
                str(entry["suite_cell_id"])
                for entry in schedule["schedule"]
                if entry["stage_id"] == "analysis"
            }:
                self.assertEqual(
                    simulation_plan_ids[(suite_cell_id, "analysis")],
                    simulation_plan_ids[(suite_cell_id, "validation")],
                )


def _minimal_execution_suite_block(*, output_root: Path) -> dict[str, object]:
    block = copy.deepcopy(
        _base_suite_block(
            output_root=output_root,
            enabled_stage_ids=["simulation", "analysis", "validation", "dashboard"],
        )
    )
    block["dimensions"]["sweep_axes"] = []
    block["ablations"] = [
        {
            "ablation_family_id": "no_waves",
            "variant_id": "disabled",
            "display_name": "No Waves",
            "parameter_snapshot": {"mode": "disable_surface_wave"},
        }
    ]
    return block


def _fixture_stage_executor(
    stage_id: str,
    *,
    call_log: list[str],
    failure_state: dict[str, bool] | None = None,
    fail_once_work_item_id: str | None = None,
):
    def execute(context: dict[str, object]) -> dict[str, object]:
        work_item = context["work_item"]
        work_item_id = str(work_item["work_item_id"])
        call_log.append(work_item_id)
        if (
            fail_once_work_item_id is not None
            and work_item_id == fail_once_work_item_id
            and failure_state is not None
            and not failure_state["fired"]
        ):
            failure_state["fired"] = True
            raise RuntimeError(f"fixture failure for {work_item_id}")

        artifact_path = (
            Path(str(context["workspace_root"]))
            / "fixture_stage_outputs"
            / f"{work_item_id}.json"
        ).resolve()
        write_json(
            {
                "stage_id": stage_id,
                "suite_cell_id": str(work_item["suite_cell_id"]),
                "work_item_id": work_item_id,
            },
            artifact_path,
        )
        summary: dict[str, object] = {
            "metadata_path": str(artifact_path),
            "work_item_id": work_item_id,
        }
        if stage_id == "validation":
            summary["dashboard_validation_bundle_metadata_path"] = str(artifact_path)
        return {
            "status": WORK_ITEM_STATUS_SUCCEEDED,
            "status_detail": f"fixture {stage_id} execution completed",
            "summary": summary,
            "downstream_artifacts": [
                {
                    "path": str(artifact_path),
                    "artifact_role_id": str(work_item["artifact_role_ids"][0]),
                    "artifact_kind": f"fixture_{stage_id}_metadata",
                    "status": "ready",
                }
            ],
        }

    return execute


if __name__ == "__main__":
    unittest.main()
