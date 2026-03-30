from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from .experiment_suite_contract import (
    ABLATION_VARIANT_LINEAGE_KIND,
    BASE_CONDITION_LINEAGE_KIND,
    DASHBOARD_SESSION_ROLE_ID,
    EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
    SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
    SEED_REPLICATE_LINEAGE_KIND,
    SIMULATOR_RESULT_BUNDLE_ROLE_ID,
    VALIDATION_BUNDLE_ROLE_ID,
    WORK_ITEM_STATUS_BLOCKED,
    WORK_ITEM_STATUS_FAILED,
    WORK_ITEM_STATUS_PARTIAL,
    WORK_ITEM_STATUS_PLANNED,
    WORK_ITEM_STATUS_RUNNING,
    WORK_ITEM_STATUS_SKIPPED,
    WORK_ITEM_STATUS_SUCCEEDED,
    write_experiment_suite_metadata,
)
from .experiment_ablation_transforms import EXPERIMENT_SUITE_ABLATION_CONFIG_KEY
from .experiment_suite_packaging import (
    build_experiment_suite_package_paths,
    package_experiment_suite_outputs,
)
from .experiment_suite_planning import (
    DEFAULT_BASE_SIMULATION_PLAN_FILENAME,
    DEFAULT_SUITE_METADATA_FILENAME,
    DEFAULT_SUITE_PLAN_FILENAME,
    EXPERIMENT_SUITE_PLAN_VERSION,
    STAGE_ANALYSIS,
    STAGE_DASHBOARD,
    STAGE_SIMULATION,
    STAGE_VALIDATION,
    SUPPORTED_STAGE_IDS,
    resolve_experiment_suite_plan,
)
from .io_utils import ensure_dir, write_json
from .validation_contract import (
    CIRCUIT_SANITY_LAYER_ID,
    MORPHOLOGY_SANITY_LAYER_ID,
    NUMERICAL_SANITY_LAYER_ID,
    TASK_SANITY_LAYER_ID,
)


EXPERIMENT_SUITE_EXECUTION_VERSION = "experiment_suite_execution.v1"
EXPERIMENT_SUITE_EXECUTION_STATE_VERSION = "experiment_suite_execution_state.v1"
EXPERIMENT_SUITE_WORKFLOW_SUMMARY_VERSION = "experiment_suite_workflow_summary.v1"

DEFAULT_EXECUTION_STATE_FILENAME = "experiment_suite_execution_state.json"
DEFAULT_EXECUTION_INPUTS_DIRNAME = "execution_inputs"
DEFAULT_CELL_WORKSPACE_DIRNAME = "workspace"
DEFAULT_WORK_ITEM_INPUT_HASH_LENGTH = 16

_STAGE_SEQUENCE_INDEX = {
    stage_id: index for index, stage_id in enumerate(SUPPORTED_STAGE_IDS)
}
_SIMULATION_LINEAGE_PRIORITY = {
    SEED_REPLICATE_LINEAGE_KIND: 0,
    SEEDED_ABLATION_VARIANT_LINEAGE_KIND: 1,
}
_ANALYSIS_LINEAGE_PRIORITY = {
    BASE_CONDITION_LINEAGE_KIND: 0,
    ABLATION_VARIANT_LINEAGE_KIND: 1,
}
_SATISFIED_DEPENDENCY_STATUSES = {
    WORK_ITEM_STATUS_SUCCEEDED,
    WORK_ITEM_STATUS_SKIPPED,
}
_RETRYABLE_STATUSES = {
    WORK_ITEM_STATUS_PLANNED,
    WORK_ITEM_STATUS_RUNNING,
    WORK_ITEM_STATUS_BLOCKED,
    WORK_ITEM_STATUS_FAILED,
    WORK_ITEM_STATUS_PARTIAL,
}

StageExecutor = Callable[[Mapping[str, Any]], Mapping[str, Any]]


def execute_experiment_suite_workflow(
    *,
    config_path: str | Path,
    manifest_path: str | Path | None = None,
    suite_manifest_path: str | Path | None = None,
    schema_path: str | Path | None = None,
    design_lock_path: str | Path | None = None,
    contract_metadata: Mapping[str, Any] | None = None,
    dry_run: bool = False,
    fail_fast: bool = False,
    stage_executors: Mapping[str, StageExecutor] | None = None,
) -> dict[str, Any]:
    plan = resolve_experiment_suite_plan(
        config_path=config_path,
        manifest_path=manifest_path,
        suite_manifest_path=suite_manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        contract_metadata=contract_metadata,
    )
    return execute_experiment_suite_plan(
        plan,
        dry_run=dry_run,
        fail_fast=fail_fast,
        stage_executors=stage_executors,
    )


def execute_experiment_suite_plan(
    plan: Mapping[str, Any],
    *,
    dry_run: bool = False,
    fail_fast: bool = False,
    stage_executors: Mapping[str, StageExecutor] | None = None,
) -> dict[str, Any]:
    normalized_plan = _require_mapping(plan, field_name="plan")
    if str(normalized_plan.get("plan_version")) != EXPERIMENT_SUITE_PLAN_VERSION:
        raise ValueError(
            f"plan.plan_version must be {EXPERIMENT_SUITE_PLAN_VERSION!r}."
        )

    schedule = build_experiment_suite_execution_schedule(normalized_plan)
    suite_root = Path(normalized_plan["output_roots"]["suite_root"]).resolve()
    state_path = suite_root / DEFAULT_EXECUTION_STATE_FILENAME
    existing_state = (
        load_experiment_suite_execution_state(state_path)
        if state_path.exists()
        else None
    )
    if existing_state is not None:
        _validate_execution_state_against_plan(
            existing_state=existing_state,
            plan=normalized_plan,
            schedule=schedule,
        )

    if dry_run:
        return _build_dry_run_summary(
            plan=normalized_plan,
            schedule=schedule,
            existing_state=existing_state,
            state_path=state_path,
        )

    state = _initialize_execution_state(
        plan=normalized_plan,
        schedule=schedule,
        state_path=state_path,
        existing_state=existing_state,
    )
    _persist_suite_execution_inputs(
        plan=normalized_plan,
        schedule=schedule,
        state=state,
    )
    input_preflight = _prepare_materialized_input_bundles(
        plan=normalized_plan,
        schedule=schedule,
    )

    executors = dict(_default_stage_executors())
    if stage_executors is not None:
        executors.update(stage_executors)

    state_records_by_id = {
        str(item["work_item_id"]): item for item in state["work_items"]
    }
    schedule_results: list[dict[str, Any]] = []
    for entry in schedule["schedule"]:
        record = state_records_by_id[str(entry["work_item_id"])]
        decision = _resolve_execution_decision(
            schedule_entry=entry,
            state_records_by_id=state_records_by_id,
        )
        if decision["action"] in {"skip_succeeded", "skip_skipped"}:
            schedule_results.append(
                {
                    "work_item_id": str(entry["work_item_id"]),
                    "suite_cell_id": str(entry["suite_cell_id"]),
                    "stage_id": str(entry["stage_id"]),
                    "action": decision["action"],
                    "status": str(record["status"]),
                }
            )
            continue

        if decision["action"] == "blocked":
            blocking_snapshot = copy.deepcopy(decision["blocking_dependencies"])
            new_detail = _blocked_status_detail(blocking_snapshot)
            if (
                str(record["status"]) != WORK_ITEM_STATUS_BLOCKED
                or str(record["status_detail"]) != new_detail
            ):
                _append_attempt(
                    record=record,
                    status=WORK_ITEM_STATUS_BLOCKED,
                    status_detail=new_detail,
                    decision="blocked_by_dependencies",
                    suite_cell_identity=copy.deepcopy(entry["suite_cell_identity"]),
                    workspace_owner_cell_id=str(entry["workspace_owner_cell_id"]),
                    workspace_root=str(entry["workspace_root"]),
                    materialized_manifest_path=str(entry["materialized_manifest_path"]),
                    materialized_config_path=str(entry["materialized_config_path"]),
                    dependency_statuses=blocking_snapshot,
                    upstream_artifacts=_build_upstream_artifact_snapshot(
                        schedule_entry=entry,
                        state_records_by_id=state_records_by_id,
                    ),
                    downstream_artifacts=[],
                    result_summary={},
                    error=None,
                )
                _refresh_state_rollups(state)
                write_json(state, state_path)
            schedule_results.append(
                {
                    "work_item_id": str(entry["work_item_id"]),
                    "suite_cell_id": str(entry["suite_cell_id"]),
                    "stage_id": str(entry["stage_id"]),
                    "action": "blocked",
                    "status": WORK_ITEM_STATUS_BLOCKED,
                }
            )
            continue

        executor = executors.get(str(entry["stage_id"]))
        if executor is None:
            raise ValueError(
                f"No stage executor is registered for stage_id {entry['stage_id']!r}."
            )

        materialized = _materialize_work_item_inputs(
            plan=normalized_plan,
            schedule_entry=entry,
            write_files=True,
        )
        attempt_index = int(record["attempt_count"]) + 1
        running_attempt = {
            "attempt_index": attempt_index,
            "decision": "executing",
            "status": WORK_ITEM_STATUS_RUNNING,
            "status_detail": "Stage execution started.",
            "suite_cell_identity": copy.deepcopy(entry["suite_cell_identity"]),
            "workspace_owner_cell_id": str(entry["workspace_owner_cell_id"]),
            "workspace_root": str(entry["workspace_root"]),
            "materialized_manifest_path": str(materialized["manifest_path"]),
            "materialized_config_path": str(materialized["config_path"]),
            "dependency_statuses": _dependency_status_snapshot(
                entry["dependency_work_item_ids"],
                state_records_by_id=state_records_by_id,
            ),
            "upstream_artifacts": _build_upstream_artifact_snapshot(
                schedule_entry=entry,
                state_records_by_id=state_records_by_id,
            ),
            "downstream_artifacts": [],
            "result_summary": {},
            "error": None,
        }
        record["attempt_count"] = attempt_index
        record["status"] = WORK_ITEM_STATUS_RUNNING
        record["status_detail"] = "Stage execution started."
        record["attempts"].append(running_attempt)
        _refresh_state_rollups(state)
        write_json(state, state_path)

        try:
            execution_context = _build_stage_execution_context(
                plan=normalized_plan,
                schedule_entry=entry,
                state_records_by_id=state_records_by_id,
                materialized=materialized,
            )
            raw_result = executor(execution_context)
            result = _normalize_stage_execution_result(
                raw_result,
                default_role_id=_primary_artifact_role_id(entry),
            )
            final_status = str(result["status"])
            final_detail = str(result["status_detail"])
            downstream_artifacts = _resolved_artifact_paths(
                result["downstream_artifacts"]
            )
            if (
                final_status == WORK_ITEM_STATUS_SUCCEEDED
                and not _all_ready_artifacts_exist(downstream_artifacts)
            ):
                final_status = WORK_ITEM_STATUS_PARTIAL
                final_detail = (
                    "Stage executor reported success, but one or more downstream "
                    "artifacts are missing."
                )
            running_attempt["decision"] = "executed"
            running_attempt["status"] = final_status
            running_attempt["status_detail"] = final_detail
            running_attempt["downstream_artifacts"] = downstream_artifacts
            running_attempt["result_summary"] = copy.deepcopy(result["summary"])
            record["status"] = final_status
            record["status_detail"] = final_detail
        except Exception as exc:
            running_attempt["decision"] = "executed"
            running_attempt["status"] = WORK_ITEM_STATUS_FAILED
            running_attempt["status_detail"] = (
                f"Stage execution raised {type(exc).__name__}: {exc}"
            )
            running_attempt["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            record["status"] = WORK_ITEM_STATUS_FAILED
            record["status_detail"] = str(running_attempt["status_detail"])
            _refresh_state_rollups(state)
            write_json(state, state_path)
            schedule_results.append(
                {
                    "work_item_id": str(entry["work_item_id"]),
                    "suite_cell_id": str(entry["suite_cell_id"]),
                    "stage_id": str(entry["stage_id"]),
                    "action": "executed",
                    "status": WORK_ITEM_STATUS_FAILED,
                }
            )
            if fail_fast:
                break
            continue

        _refresh_state_rollups(state)
        write_json(state, state_path)
        schedule_results.append(
            {
                "work_item_id": str(entry["work_item_id"]),
                "suite_cell_id": str(entry["suite_cell_id"]),
                "stage_id": str(entry["stage_id"]),
                "action": "executed",
                "status": str(record["status"]),
            }
        )
        if fail_fast and str(record["status"]) in {
            WORK_ITEM_STATUS_FAILED,
            WORK_ITEM_STATUS_PARTIAL,
        }:
            break

    _refresh_state_rollups(state)
    write_json(state, state_path)
    package_summary = package_experiment_suite_outputs(
        normalized_plan,
        state=state,
    )
    return {
        "workflow_version": EXPERIMENT_SUITE_WORKFLOW_SUMMARY_VERSION,
        "execution_version": EXPERIMENT_SUITE_EXECUTION_VERSION,
        "dry_run": False,
        "suite_id": str(state["suite_id"]),
        "suite_spec_hash": str(state["suite_spec_hash"]),
        "state_path": str(state_path),
        "input_preflight": input_preflight,
        "overall_status": str(state["overall_status"]),
        "status_counts": copy.deepcopy(dict(state["status_counts"])),
        "work_item_order": list(state["work_item_order"]),
        "schedule": schedule_results,
        "package": package_summary,
    }


def build_experiment_suite_execution_schedule(
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_plan = _require_mapping(plan, field_name="plan")
    if str(normalized_plan.get("plan_version")) != EXPERIMENT_SUITE_PLAN_VERSION:
        raise ValueError(
            f"plan.plan_version must be {EXPERIMENT_SUITE_PLAN_VERSION!r}."
        )

    suite_root = Path(normalized_plan["output_roots"]["suite_root"]).resolve()
    stage_order = [
        str(item["stage_id"]) for item in normalized_plan["stage_targets"]
    ]
    cell_catalog = [
        copy.deepcopy(dict(item)) for item in normalized_plan["cell_catalog"]
    ]
    work_item_catalog = [
        copy.deepcopy(dict(item)) for item in normalized_plan["work_item_catalog"]
    ]
    cells_by_id = {str(item["suite_cell_id"]): item for item in cell_catalog}
    base_cells = [
        item
        for item in cell_catalog
        if str(item["lineage_kind"]) == BASE_CONDITION_LINEAGE_KIND
    ]
    root_index_by_id = {
        str(item["suite_cell_id"]): index for index, item in enumerate(base_cells)
    }
    cell_index_by_id = {
        str(item["suite_cell_id"]): index for index, item in enumerate(cell_catalog)
    }
    child_cells_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in cell_catalog:
        parent_cell_id = item.get("parent_cell_id")
        if parent_cell_id is not None:
            child_cells_by_parent[str(parent_cell_id)].append(item)
    for child_cells in child_cells_by_parent.values():
        child_cells.sort(
            key=lambda item: (
                int(
                    _ANALYSIS_LINEAGE_PRIORITY.get(
                        str(item["lineage_kind"]),
                        _SIMULATION_LINEAGE_PRIORITY.get(str(item["lineage_kind"]), 99),
                    )
                ),
                -1 if item.get("simulation_seed") is None else int(item["simulation_seed"]),
                str(item["suite_cell_id"]),
            )
        )

    work_item_id_by_cell_stage = {
        (str(item["suite_cell_id"]), str(item["stage_id"])): str(item["work_item_id"])
        for item in work_item_catalog
    }
    schedule_entries: list[dict[str, Any]] = []
    for item in work_item_catalog:
        suite_cell_id = str(item["suite_cell_id"])
        stage_id = str(item["stage_id"])
        cell = cells_by_id[suite_cell_id]
        workspace_owner_cell_id = _workspace_owner_cell_id(cell)
        workspace_owner = cells_by_id[workspace_owner_cell_id]
        materialized_path_key = _build_work_item_input_path_key(
            work_item_id=str(item["work_item_id"]),
            stage_id=stage_id,
        )
        materialized_root = (
            suite_root
            / DEFAULT_EXECUTION_INPUTS_DIRNAME
            / materialized_path_key
        ).resolve()
        workspace_root = (
            Path(workspace_owner["output_roots"]["cell_root"])
            / DEFAULT_CELL_WORKSPACE_DIRNAME
        ).resolve()
        dependency_work_item_ids = _dependency_work_item_ids(
            suite_cell_id=suite_cell_id,
            stage_id=stage_id,
            stage_order=stage_order,
            cells_by_id=cells_by_id,
            child_cells_by_parent=child_cells_by_parent,
            work_item_id_by_cell_stage=work_item_id_by_cell_stage,
        )
        root_cell_id = str(workspace_owner["root_cell_id"] or workspace_owner["suite_cell_id"])
        root_index = int(root_index_by_id[root_cell_id])
        owner_lineage_priority = int(
            _ANALYSIS_LINEAGE_PRIORITY.get(str(workspace_owner["lineage_kind"]), 99)
        )
        schedule_entries.append(
            {
                "work_item_id": str(item["work_item_id"]),
                "suite_cell_id": suite_cell_id,
                "stage_id": stage_id,
                "artifact_role_ids": list(item["artifact_role_ids"]),
                "workspace_owner_cell_id": workspace_owner_cell_id,
                "workspace_root": str(workspace_root),
                "dependency_work_item_ids": dependency_work_item_ids,
                "materialized_path_key": materialized_path_key,
                "materialized_manifest_path": str((materialized_root / "manifest.yaml").resolve()),
                "materialized_config_path": str((materialized_root / "config.yaml").resolve()),
                "suite_cell_identity": _suite_cell_identity(cell),
                "_sort_key": (
                    int(_STAGE_SEQUENCE_INDEX[stage_id]),
                    root_index,
                    owner_lineage_priority,
                    int(cell_index_by_id[workspace_owner_cell_id]),
                    int(
                        _SIMULATION_LINEAGE_PRIORITY.get(
                            str(cell["lineage_kind"]),
                            _ANALYSIS_LINEAGE_PRIORITY.get(str(cell["lineage_kind"]), 99),
                        )
                    ),
                    -1 if cell.get("simulation_seed") is None else int(cell["simulation_seed"]),
                    int(cell_index_by_id[suite_cell_id]),
                    str(item["work_item_id"]),
                ),
            }
        )

    schedule_entries.sort(key=lambda item: item["_sort_key"])
    ordered_entries: list[dict[str, Any]] = []
    for index, item in enumerate(schedule_entries):
        cleaned = copy.deepcopy(dict(item))
        cleaned.pop("_sort_key", None)
        cleaned["execution_order_index"] = index
        ordered_entries.append(cleaned)

    return {
        "schedule_version": EXPERIMENT_SUITE_EXECUTION_VERSION,
        "suite_id": str(normalized_plan["suite_id"]),
        "suite_spec_hash": str(normalized_plan["suite_metadata"]["suite_spec_hash"]),
        "stage_order": stage_order,
        "stable_schedule_ordering": (
            "stage_sequence_then_root_cell_then_owner_cell_then_seed"
        ),
        "work_item_order": [
            str(item["work_item_id"]) for item in ordered_entries
        ],
        "schedule": ordered_entries,
    }


def load_experiment_suite_execution_state(
    state_path: str | Path,
) -> dict[str, Any]:
    resolved_path = Path(state_path).resolve()
    with resolved_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    normalized = _require_mapping(
        payload,
        field_name="experiment_suite_execution_state",
    )
    if (
        str(normalized.get("state_version"))
        != EXPERIMENT_SUITE_EXECUTION_STATE_VERSION
    ):
        raise ValueError(
            "experiment_suite execution state uses unsupported state_version "
            f"{normalized.get('state_version')!r}."
        )
    return copy.deepcopy(dict(normalized))


def _default_stage_executors() -> dict[str, StageExecutor]:
    return {
        STAGE_SIMULATION: _execute_simulation_stage,
        STAGE_ANALYSIS: _execute_analysis_stage,
        STAGE_VALIDATION: _execute_validation_stage,
        STAGE_DASHBOARD: _execute_dashboard_stage,
    }


def _execute_simulation_stage(context: Mapping[str, Any]) -> dict[str, Any]:
    from .simulation_planning import resolve_manifest_simulation_plan
    from .simulator_execution import execute_manifest_simulation

    simulation_plan = resolve_manifest_simulation_plan(
        manifest_path=context["manifest_path"],
        config_path=context["config_path"],
        schema_path=context["schema_path"],
        design_lock_path=context["design_lock_path"],
    )
    arm_plans_by_id = {
        str(item["arm_reference"]["arm_id"]): item for item in simulation_plan["arm_plans"]
    }
    model_modes: list[str] = []
    for arm_id in simulation_plan["arm_order"]:
        arm_plan = arm_plans_by_id[str(arm_id)]
        model_mode = str(arm_plan["arm_reference"]["model_mode"])
        if model_mode not in model_modes:
            model_modes.append(model_mode)

    downstream_artifacts: list[dict[str, Any]] = []
    executed_runs = []
    for model_mode in model_modes:
        result = execute_manifest_simulation(
            manifest_path=context["manifest_path"],
            config_path=context["config_path"],
            schema_path=context["schema_path"],
            design_lock_path=context["design_lock_path"],
            model_mode=model_mode,
            use_manifest_seed_sweep=False,
        )
        for run in result["executed_runs"]:
            executed_runs.append(copy.deepcopy(dict(run)))
            downstream_artifacts.extend(
                [
                    _artifact_record(
                        path=run["metadata_path"],
                        artifact_role_id=SIMULATOR_RESULT_BUNDLE_ROLE_ID,
                        artifact_kind="simulator_result_bundle_metadata",
                        bundle_id=run["bundle_id"],
                        arm_id=run["arm_id"],
                        run_spec_hash=run["run_spec_hash"],
                    ),
                    _artifact_record(
                        path=run["readout_traces_path"],
                        artifact_role_id=SIMULATOR_RESULT_BUNDLE_ROLE_ID,
                        artifact_kind="simulator_readout_traces",
                        bundle_id=run["bundle_id"],
                        arm_id=run["arm_id"],
                    ),
                    _artifact_record(
                        path=run["metrics_table_path"],
                        artifact_role_id=SIMULATOR_RESULT_BUNDLE_ROLE_ID,
                        artifact_kind="simulator_metrics_table",
                        bundle_id=run["bundle_id"],
                        arm_id=run["arm_id"],
                    ),
                    _artifact_record(
                        path=run["state_summary_path"],
                        artifact_role_id=SIMULATOR_RESULT_BUNDLE_ROLE_ID,
                        artifact_kind="simulator_state_summary",
                        bundle_id=run["bundle_id"],
                        arm_id=run["arm_id"],
                    ),
                    _artifact_record(
                        path=run["structured_log_path"],
                        artifact_role_id=SIMULATOR_RESULT_BUNDLE_ROLE_ID,
                        artifact_kind="simulator_structured_log",
                        bundle_id=run["bundle_id"],
                        arm_id=run["arm_id"],
                    ),
                    _artifact_record(
                        path=run["provenance_path"],
                        artifact_role_id=SIMULATOR_RESULT_BUNDLE_ROLE_ID,
                        artifact_kind="simulator_execution_provenance",
                        bundle_id=run["bundle_id"],
                        arm_id=run["arm_id"],
                    ),
                    _artifact_record(
                        path=run["ui_payload_path"],
                        artifact_role_id=SIMULATOR_RESULT_BUNDLE_ROLE_ID,
                        artifact_kind="simulator_ui_payload",
                        bundle_id=run["bundle_id"],
                        arm_id=run["arm_id"],
                    ),
                ]
            )
    return {
        "status": WORK_ITEM_STATUS_SUCCEEDED,
        "status_detail": (
            f"Executed {len(executed_runs)} simulator arm runs for "
            f"work_item_id {context['work_item']['work_item_id']}."
        ),
        "summary": {
            "executed_run_count": len(executed_runs),
            "model_modes": model_modes,
            "executed_runs": executed_runs,
        },
        "downstream_artifacts": downstream_artifacts,
    }


def _execute_analysis_stage(context: Mapping[str, Any]) -> dict[str, Any]:
    from .experiment_comparison_analysis import execute_experiment_comparison_workflow

    result = execute_experiment_comparison_workflow(
        manifest_path=context["manifest_path"],
        config_path=context["config_path"],
        schema_path=context["schema_path"],
        design_lock_path=context["design_lock_path"],
    )
    packaged = copy.deepcopy(dict(result["packaged_analysis_bundle"]))
    downstream_artifacts = [
        _artifact_record(
            path=packaged["metadata_path"],
            artifact_role_id=EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
            artifact_kind="experiment_analysis_bundle_metadata",
            bundle_id=packaged["bundle_reference"]["bundle_id"],
        ),
        _artifact_record(
            path=packaged["packaged_summary_path"],
            artifact_role_id=EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
            artifact_kind="experiment_comparison_summary",
            bundle_id=packaged["bundle_reference"]["bundle_id"],
        ),
        _artifact_record(
            path=packaged["task_summary_path"],
            artifact_role_id=EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
            artifact_kind="task_summary_rows",
            bundle_id=packaged["bundle_reference"]["bundle_id"],
        ),
        _artifact_record(
            path=packaged["null_test_table_path"],
            artifact_role_id=EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
            artifact_kind="null_test_table",
            bundle_id=packaged["bundle_reference"]["bundle_id"],
        ),
        _artifact_record(
            path=packaged["comparison_matrices_path"],
            artifact_role_id=EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
            artifact_kind="comparison_matrices",
            bundle_id=packaged["bundle_reference"]["bundle_id"],
        ),
        _artifact_record(
            path=packaged["visualization_catalog_path"],
            artifact_role_id=EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
            artifact_kind="visualization_catalog",
            bundle_id=packaged["bundle_reference"]["bundle_id"],
        ),
        _artifact_record(
            path=packaged["analysis_ui_payload_path"],
            artifact_role_id=EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
            artifact_kind="analysis_ui_payload",
            bundle_id=packaged["bundle_reference"]["bundle_id"],
        ),
        _artifact_record(
            path=packaged["report_path"],
            artifact_role_id=EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
            artifact_kind="offline_report_index",
            bundle_id=packaged["bundle_reference"]["bundle_id"],
        ),
        _artifact_record(
            path=packaged["report_summary_path"],
            artifact_role_id=EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
            artifact_kind="offline_report_summary",
            bundle_id=packaged["bundle_reference"]["bundle_id"],
        ),
    ]
    return {
        "status": WORK_ITEM_STATUS_SUCCEEDED,
        "status_detail": (
            "Packaged experiment-level comparison analysis for the suite cell."
        ),
        "summary": {
            "metadata_path": packaged["metadata_path"],
            "bundle_id": packaged["bundle_reference"]["bundle_id"],
            "bundle_directory": packaged["bundle_directory"],
            "report_path": packaged["report_path"],
        },
        "downstream_artifacts": downstream_artifacts,
    }


def _execute_validation_stage(context: Mapping[str, Any]) -> dict[str, Any]:
    from .simulation_planning import resolve_manifest_simulation_plan
    from .validation_circuit import execute_circuit_validation_workflow
    from .validation_morphology import execute_morphology_validation_workflow
    from .validation_numerics import execute_numerical_validation_workflow
    from .validation_planning import resolve_validation_plan
    from .validation_reporting import package_validation_ladder_outputs
    from .validation_task import execute_task_validation_workflow

    analysis_summary = _dependency_result_summary(context, STAGE_ANALYSIS)
    analysis_metadata_path = _summary_metadata_path(analysis_summary)
    simulation_plan = resolve_manifest_simulation_plan(
        manifest_path=context["manifest_path"],
        config_path=context["config_path"],
        schema_path=context["schema_path"],
        design_lock_path=context["design_lock_path"],
    )
    validation_plan = resolve_validation_plan(
        config_path=context["config_path"],
        simulation_plan=simulation_plan,
        analysis_bundle_metadata_path=analysis_metadata_path,
    )
    active_layer_ids = list(validation_plan["validation_plan_reference"]["active_layer_ids"])
    layer_results: dict[str, dict[str, Any]] = {}
    layer_metadata_paths: list[str] = []
    downstream_artifacts: list[dict[str, Any]] = []

    if NUMERICAL_SANITY_LAYER_ID in set(active_layer_ids):
        numerical = execute_numerical_validation_workflow(
            manifest_path=context["manifest_path"],
            config_path=context["config_path"],
            schema_path=context["schema_path"],
            design_lock_path=context["design_lock_path"],
        )
        layer_results[NUMERICAL_SANITY_LAYER_ID] = copy.deepcopy(dict(numerical))
        layer_metadata_paths.append(str(numerical["metadata_path"]))
        downstream_artifacts.append(
            _artifact_record(
                path=numerical["metadata_path"],
                artifact_role_id=VALIDATION_BUNDLE_ROLE_ID,
                artifact_kind="validation_layer_metadata",
                layer_id=NUMERICAL_SANITY_LAYER_ID,
                bundle_id=numerical["bundle_id"],
            )
        )

    if MORPHOLOGY_SANITY_LAYER_ID in set(active_layer_ids):
        morphology = execute_morphology_validation_workflow(
            manifest_path=context["manifest_path"],
            config_path=context["config_path"],
            schema_path=context["schema_path"],
            design_lock_path=context["design_lock_path"],
        )
        layer_results[MORPHOLOGY_SANITY_LAYER_ID] = copy.deepcopy(dict(morphology))
        layer_metadata_paths.append(str(morphology["metadata_path"]))
        downstream_artifacts.append(
            _artifact_record(
                path=morphology["metadata_path"],
                artifact_role_id=VALIDATION_BUNDLE_ROLE_ID,
                artifact_kind="validation_layer_metadata",
                layer_id=MORPHOLOGY_SANITY_LAYER_ID,
                bundle_id=morphology["bundle_id"],
            )
        )

    if CIRCUIT_SANITY_LAYER_ID in set(active_layer_ids):
        circuit = execute_circuit_validation_workflow(
            manifest_path=context["manifest_path"],
            config_path=context["config_path"],
            schema_path=context["schema_path"],
            design_lock_path=context["design_lock_path"],
            analysis_bundle_metadata_path=analysis_metadata_path,
        )
        layer_results[CIRCUIT_SANITY_LAYER_ID] = copy.deepcopy(dict(circuit))
        layer_metadata_paths.append(str(circuit["metadata_path"]))
        downstream_artifacts.append(
            _artifact_record(
                path=circuit["metadata_path"],
                artifact_role_id=VALIDATION_BUNDLE_ROLE_ID,
                artifact_kind="validation_layer_metadata",
                layer_id=CIRCUIT_SANITY_LAYER_ID,
                bundle_id=circuit["bundle_id"],
            )
        )

    if TASK_SANITY_LAYER_ID in set(active_layer_ids):
        task = execute_task_validation_workflow(
            manifest_path=context["manifest_path"],
            config_path=context["config_path"],
            schema_path=context["schema_path"],
            design_lock_path=context["design_lock_path"],
            analysis_bundle_metadata_path=analysis_metadata_path,
        )
        layer_results[TASK_SANITY_LAYER_ID] = copy.deepcopy(dict(task))
        layer_metadata_paths.append(str(task["metadata_path"]))
        downstream_artifacts.append(
            _artifact_record(
                path=task["metadata_path"],
                artifact_role_id=VALIDATION_BUNDLE_ROLE_ID,
                artifact_kind="validation_layer_metadata",
                layer_id=TASK_SANITY_LAYER_ID,
                bundle_id=task["bundle_id"],
            )
        )

    if not layer_metadata_paths:
        return {
            "status": WORK_ITEM_STATUS_SKIPPED,
            "status_detail": "No active validation layers were selected for this suite cell.",
            "summary": {
                "layer_results": {},
                "dashboard_validation_bundle_metadata_path": None,
            },
            "downstream_artifacts": [],
        }

    packaged = package_validation_ladder_outputs(
        layer_bundle_metadata_paths=layer_metadata_paths,
        processed_simulator_results_dir=context["workspace_root"],
    )
    downstream_artifacts.extend(
        [
            _artifact_record(
                path=packaged["metadata_path"],
                artifact_role_id=VALIDATION_BUNDLE_ROLE_ID,
                artifact_kind="validation_ladder_package_metadata",
            ),
            _artifact_record(
                path=packaged["summary_path"],
                artifact_role_id=VALIDATION_BUNDLE_ROLE_ID,
                artifact_kind="validation_ladder_summary",
            ),
            _artifact_record(
                path=packaged["report_path"],
                artifact_role_id=VALIDATION_BUNDLE_ROLE_ID,
                artifact_kind="validation_ladder_report",
            ),
        ]
    )
    preferred_dashboard_metadata_path = (
        layer_results.get(TASK_SANITY_LAYER_ID, next(iter(layer_results.values()))).get(
            "metadata_path"
        )
    )
    return {
        "status": WORK_ITEM_STATUS_SUCCEEDED,
        "status_detail": (
            f"Executed {len(layer_results)} validation layer workflows and packaged "
            "a validation ladder bundle."
        ),
        "summary": {
            "layer_results": layer_results,
            "packaged_validation_ladder": copy.deepcopy(dict(packaged)),
            "dashboard_validation_bundle_metadata_path": preferred_dashboard_metadata_path,
        },
        "downstream_artifacts": downstream_artifacts,
    }


def _execute_dashboard_stage(context: Mapping[str, Any]) -> dict[str, Any]:
    from .dashboard_session_planning import (
        package_dashboard_session,
        resolve_dashboard_session_plan,
    )

    analysis_summary = _dependency_result_summary(context, STAGE_ANALYSIS)
    validation_summary = _dependency_result_summary(context, STAGE_VALIDATION)
    dashboard_plan = resolve_dashboard_session_plan(
        config_path=context["config_path"],
        manifest_path=context["manifest_path"],
        schema_path=context["schema_path"],
        design_lock_path=context["design_lock_path"],
        analysis_bundle_metadata_path=_summary_metadata_path(analysis_summary),
        validation_bundle_metadata_path=_dashboard_validation_metadata_path(
            validation_summary
        ),
    )
    packaged = package_dashboard_session(dashboard_plan)
    return {
        "status": WORK_ITEM_STATUS_SUCCEEDED,
        "status_detail": "Packaged the dashboard session for the suite cell.",
        "summary": {
            "metadata_path": packaged["metadata_path"],
            "bundle_id": packaged["bundle_id"],
            "app_shell_path": packaged["app_shell_path"],
        },
        "downstream_artifacts": [
            _artifact_record(
                path=packaged["metadata_path"],
                artifact_role_id=DASHBOARD_SESSION_ROLE_ID,
                artifact_kind="dashboard_session_metadata",
                bundle_id=packaged["bundle_id"],
            ),
            _artifact_record(
                path=packaged["session_payload_path"],
                artifact_role_id=DASHBOARD_SESSION_ROLE_ID,
                artifact_kind="dashboard_session_payload",
                bundle_id=packaged["bundle_id"],
            ),
            _artifact_record(
                path=packaged["session_state_path"],
                artifact_role_id=DASHBOARD_SESSION_ROLE_ID,
                artifact_kind="dashboard_session_state",
                bundle_id=packaged["bundle_id"],
            ),
            _artifact_record(
                path=packaged["app_shell_path"],
                artifact_role_id=DASHBOARD_SESSION_ROLE_ID,
                artifact_kind="dashboard_app_shell",
                bundle_id=packaged["bundle_id"],
            ),
        ],
    }


def _build_stage_execution_context(
    *,
    plan: Mapping[str, Any],
    schedule_entry: Mapping[str, Any],
    state_records_by_id: Mapping[str, Mapping[str, Any]],
    materialized: Mapping[str, Any],
) -> dict[str, Any]:
    dependency_records = [
        copy.deepcopy(dict(state_records_by_id[work_item_id]))
        for work_item_id in schedule_entry["dependency_work_item_ids"]
    ]
    cells_by_id = {
        str(item["suite_cell_id"]): copy.deepcopy(dict(item))
        for item in plan["cell_catalog"]
    }
    return {
        "execution_version": EXPERIMENT_SUITE_EXECUTION_VERSION,
        "plan": copy.deepcopy(dict(plan)),
        "work_item": {
            "work_item_id": str(schedule_entry["work_item_id"]),
            "suite_cell_id": str(schedule_entry["suite_cell_id"]),
            "stage_id": str(schedule_entry["stage_id"]),
            "artifact_role_ids": list(schedule_entry["artifact_role_ids"]),
            "execution_order_index": int(schedule_entry["execution_order_index"]),
        },
        "suite_cell": copy.deepcopy(cells_by_id[str(schedule_entry["suite_cell_id"])]),
        "workspace_owner_cell": copy.deepcopy(
            cells_by_id[str(schedule_entry["workspace_owner_cell_id"])]
        ),
        "workspace_root": str(schedule_entry["workspace_root"]),
        "manifest_path": str(materialized["manifest_path"]),
        "config_path": str(materialized["config_path"]),
        "schema_path": str(plan["suite_source"]["schema_path"]),
        "design_lock_path": str(plan["suite_source"]["design_lock_path"]),
        "dependency_records": dependency_records,
    }


def _persist_suite_execution_inputs(
    *,
    plan: Mapping[str, Any],
    schedule: Mapping[str, Any],
    state: Mapping[str, Any],
) -> None:
    suite_root = Path(plan["output_roots"]["suite_root"]).resolve()
    write_json(plan, suite_root / DEFAULT_SUITE_PLAN_FILENAME)
    write_experiment_suite_metadata(
        plan["suite_metadata"],
        suite_root / DEFAULT_SUITE_METADATA_FILENAME,
    )
    upstream_root = Path(plan["output_roots"]["upstream_root"]).resolve()
    write_json(
        plan["base_simulation_plan"],
        upstream_root / DEFAULT_BASE_SIMULATION_PLAN_FILENAME,
    )
    write_json(state, suite_root / DEFAULT_EXECUTION_STATE_FILENAME)
    inputs_root = suite_root / DEFAULT_EXECUTION_INPUTS_DIRNAME
    ensure_dir(inputs_root)
    for entry in schedule["schedule"]:
        _materialize_work_item_inputs(
            plan=plan,
            schedule_entry=entry,
            write_files=True,
        )


def _materialize_work_item_inputs(
    *,
    plan: Mapping[str, Any],
    schedule_entry: Mapping[str, Any],
    write_files: bool,
) -> dict[str, Any]:
    manifest_payload = _build_materialized_manifest_payload(
        plan=plan,
        schedule_entry=schedule_entry,
    )
    config_payload = _build_materialized_config_payload(
        plan=plan,
        schedule_entry=schedule_entry,
    )
    manifest_path = Path(schedule_entry["materialized_manifest_path"]).resolve()
    config_path = Path(schedule_entry["materialized_config_path"]).resolve()
    if write_files:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            yaml.safe_dump(manifest_payload, sort_keys=False),
            encoding="utf-8",
        )
        config_path.write_text(
            yaml.safe_dump(config_payload, sort_keys=False),
            encoding="utf-8",
        )
    return {
        "manifest_path": manifest_path,
        "config_path": config_path,
    }


def _prepare_materialized_input_bundles(
    *,
    plan: Mapping[str, Any],
    schedule: Mapping[str, Any],
) -> dict[str, Any]:
    from .stimulus_bundle import record_stimulus_bundle, resolve_stimulus_input

    bundle_records: list[dict[str, Any]] = []
    seen_bundle_paths: set[str] = set()
    schema_path = Path(plan["suite_source"]["schema_path"]).resolve()
    design_lock_path = Path(plan["suite_source"]["design_lock_path"]).resolve()

    for entry in schedule["schedule"]:
        config_payload = _load_yaml_mapping_file(
            Path(entry["materialized_config_path"]).resolve()
        )
        config_paths = _require_mapping(
            config_payload.get("paths", {}),
            field_name="config.paths",
        )
        resolved_input = resolve_stimulus_input(
            manifest_path=Path(entry["materialized_manifest_path"]).resolve(),
            schema_path=schema_path,
            design_lock_path=design_lock_path,
            processed_stimulus_dir=config_paths.get("processed_stimulus_dir"),
        )
        bundle_metadata_path = str(resolved_input.bundle_metadata_path.resolve())
        if bundle_metadata_path in seen_bundle_paths:
            continue
        seen_bundle_paths.add(bundle_metadata_path)
        if resolved_input.bundle_metadata_path.exists():
            bundle_records.append(
                {
                    "status": "cached",
                    "bundle_metadata_path": bundle_metadata_path,
                    "source_manifest_path": str(resolved_input.source_path.resolve()),
                }
            )
            continue
        recorded = record_stimulus_bundle(resolved_input)
        bundle_records.append(
            {
                "status": "recorded",
                "bundle_metadata_path": bundle_metadata_path,
                "source_manifest_path": str(resolved_input.source_path.resolve()),
                "bundle_directory": str(Path(recorded["bundle_directory"]).resolve()),
                "parameter_hash": str(recorded["parameter_hash"]),
            }
        )

    return {
        "bundle_count": len(bundle_records),
        "recorded_count": sum(
            1 for item in bundle_records if item["status"] == "recorded"
        ),
        "cached_count": sum(
            1 for item in bundle_records if item["status"] == "cached"
        ),
        "bundles": bundle_records,
    }


def _build_materialized_manifest_payload(
    *,
    plan: Mapping[str, Any],
    schedule_entry: Mapping[str, Any],
) -> dict[str, Any]:
    manifest_path = Path(plan["suite_source"]["experiment_manifest_path"]).resolve()
    base_manifest_payload = _load_yaml_mapping_file(manifest_path)
    base_manifest_payload.pop("suite", None)
    cells_by_id = {
        str(item["suite_cell_id"]): copy.deepcopy(dict(item))
        for item in plan["cell_catalog"]
    }
    cell = cells_by_id[str(schedule_entry["suite_cell_id"])]
    merged = _deep_merge(base_manifest_payload, cell["manifest_overrides"])
    lineage_kind = str(cell["lineage_kind"])
    if lineage_kind in {
        SEED_REPLICATE_LINEAGE_KIND,
        SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
    }:
        resolved_seed = int(cell["simulation_seed"])
        merged["seed_sweep"] = [resolved_seed]
        merged["random_seed"] = resolved_seed
        _rewrite_manifest_arm_random_seeds(merged, seed_value=resolved_seed)
        return merged

    child_seeds = [
        int(item["simulation_seed"])
        for item in plan["cell_catalog"]
        if item.get("parent_cell_id") == cell["suite_cell_id"]
        and item.get("simulation_seed") is not None
    ]
    if child_seeds:
        merged["seed_sweep"] = sorted(child_seeds)
        merged["random_seed"] = int(sorted(child_seeds)[0])
        _rewrite_manifest_arm_random_seeds(
            merged,
            seed_value=int(sorted(child_seeds)[0]),
        )
    return merged


def _rewrite_manifest_arm_random_seeds(
    manifest_payload: dict[str, Any],
    *,
    seed_value: int,
) -> None:
    comparison_arms = manifest_payload.get("comparison_arms")
    if not isinstance(comparison_arms, list):
        return
    for arm in comparison_arms:
        if isinstance(arm, dict):
            arm["random_seed"] = int(seed_value)


def _build_materialized_config_payload(
    *,
    plan: Mapping[str, Any],
    schedule_entry: Mapping[str, Any],
) -> dict[str, Any]:
    config_path = Path(plan["config_reference"]["config_path"]).resolve()
    base_config_payload = _load_yaml_mapping_file(config_path)
    cells_by_id = {
        str(item["suite_cell_id"]): copy.deepcopy(dict(item))
        for item in plan["cell_catalog"]
    }
    cell = cells_by_id[str(schedule_entry["suite_cell_id"])]
    merged = _deep_merge(base_config_payload, cell["config_overrides"])
    paths = dict(merged.get("paths") or {})
    workspace_root = Path(schedule_entry["workspace_root"]).resolve()
    paths["processed_simulator_results_dir"] = str(workspace_root)
    paths["operator_qa_dir"] = str((workspace_root / "operator_qa").resolve())
    paths["surface_wave_inspection_dir"] = str(
        (workspace_root / "surface_wave_inspection").resolve()
    )
    paths["mixed_fidelity_inspection_dir"] = str(
        (workspace_root / "mixed_fidelity_inspection").resolve()
    )
    paths.setdefault(
        "processed_experiment_suites_dir",
        str(Path(plan["output_roots"]["suite_root"]).resolve()),
    )
    merged["paths"] = paths
    if cell.get("ablation_realization") is not None:
        merged[EXPERIMENT_SUITE_ABLATION_CONFIG_KEY] = copy.deepcopy(
            dict(_require_mapping(
                cell["ablation_realization"],
                field_name="cell.ablation_realization",
            ))
        )
    else:
        merged.pop(EXPERIMENT_SUITE_ABLATION_CONFIG_KEY, None)
    return merged


def _resolve_execution_decision(
    *,
    schedule_entry: Mapping[str, Any],
    state_records_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    record = state_records_by_id[str(schedule_entry["work_item_id"])]
    status = str(record["status"])
    if status == WORK_ITEM_STATUS_SUCCEEDED:
        return {"action": "skip_succeeded", "blocking_dependencies": []}
    if status == WORK_ITEM_STATUS_SKIPPED:
        return {"action": "skip_skipped", "blocking_dependencies": []}
    dependency_statuses = _dependency_status_snapshot(
        schedule_entry["dependency_work_item_ids"],
        state_records_by_id=state_records_by_id,
    )
    blocking = [
        item
        for item in dependency_statuses
        if item["status"] not in _SATISFIED_DEPENDENCY_STATUSES
    ]
    if blocking:
        return {"action": "blocked", "blocking_dependencies": blocking}
    if status not in _RETRYABLE_STATUSES:
        raise ValueError(
            f"Unsupported orchestration status {status!r} for work_item_id "
            f"{schedule_entry['work_item_id']!r}."
        )
    return {"action": "execute", "blocking_dependencies": []}


def _append_attempt(
    *,
    record: dict[str, Any],
    status: str,
    status_detail: str,
    decision: str,
    suite_cell_identity: Mapping[str, Any],
    workspace_owner_cell_id: str,
    workspace_root: str,
    materialized_manifest_path: str,
    materialized_config_path: str,
    dependency_statuses: Sequence[Mapping[str, Any]],
    upstream_artifacts: Sequence[Mapping[str, Any]],
    downstream_artifacts: Sequence[Mapping[str, Any]],
    result_summary: Mapping[str, Any],
    error: Mapping[str, Any] | None,
) -> None:
    next_attempt = int(record["attempt_count"]) + 1
    record["attempt_count"] = next_attempt
    record["status"] = status
    record["status_detail"] = status_detail
    record["attempts"].append(
        {
            "attempt_index": next_attempt,
            "decision": decision,
            "status": status,
            "status_detail": status_detail,
            "suite_cell_identity": copy.deepcopy(dict(suite_cell_identity)),
            "workspace_owner_cell_id": workspace_owner_cell_id,
            "workspace_root": workspace_root,
            "materialized_manifest_path": materialized_manifest_path,
            "materialized_config_path": materialized_config_path,
            "dependency_statuses": [copy.deepcopy(dict(item)) for item in dependency_statuses],
            "upstream_artifacts": [copy.deepcopy(dict(item)) for item in upstream_artifacts],
            "downstream_artifacts": [copy.deepcopy(dict(item)) for item in downstream_artifacts],
            "result_summary": copy.deepcopy(dict(result_summary)),
            "error": None if error is None else copy.deepcopy(dict(error)),
        }
    )


def _initialize_execution_state(
    *,
    plan: Mapping[str, Any],
    schedule: Mapping[str, Any],
    state_path: Path,
    existing_state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if existing_state is not None:
        return copy.deepcopy(dict(existing_state))

    work_items = []
    for entry in schedule["schedule"]:
        work_items.append(
            {
                "work_item_id": str(entry["work_item_id"]),
                "suite_cell_id": str(entry["suite_cell_id"]),
                "stage_id": str(entry["stage_id"]),
                "execution_order_index": int(entry["execution_order_index"]),
                "artifact_role_ids": list(entry["artifact_role_ids"]),
                "dependency_work_item_ids": list(entry["dependency_work_item_ids"]),
                "workspace_owner_cell_id": str(entry["workspace_owner_cell_id"]),
                "workspace_root": str(entry["workspace_root"]),
                "materialized_manifest_path": str(entry["materialized_manifest_path"]),
                "materialized_config_path": str(entry["materialized_config_path"]),
                "suite_cell_identity": copy.deepcopy(entry["suite_cell_identity"]),
                "status": WORK_ITEM_STATUS_PLANNED,
                "status_detail": "Awaiting deterministic schedule execution.",
                "attempt_count": 0,
                "attempts": [],
            }
        )
    state = {
        "workflow_version": EXPERIMENT_SUITE_EXECUTION_VERSION,
        "state_version": EXPERIMENT_SUITE_EXECUTION_STATE_VERSION,
        "summary_version": EXPERIMENT_SUITE_WORKFLOW_SUMMARY_VERSION,
        "suite_id": str(plan["suite_id"]),
        "suite_label": str(plan["suite_label"]),
        "suite_spec_hash": str(plan["suite_metadata"]["suite_spec_hash"]),
        "suite_spec_hash_algorithm": str(
            plan["suite_metadata"]["suite_spec_hash_algorithm"]
        ),
        "suite_root": str(Path(plan["output_roots"]["suite_root"]).resolve()),
        "state_path": str(state_path.resolve()),
        "suite_plan_path": str(
            (Path(plan["output_roots"]["suite_root"]) / DEFAULT_SUITE_PLAN_FILENAME).resolve()
        ),
        "suite_metadata_path": str(
            (Path(plan["output_roots"]["suite_root"]) / DEFAULT_SUITE_METADATA_FILENAME).resolve()
        ),
        "base_simulation_plan_path": str(
            (
                Path(plan["output_roots"]["upstream_root"])
                / DEFAULT_BASE_SIMULATION_PLAN_FILENAME
            ).resolve()
        ),
        "stable_schedule_ordering": str(schedule["stable_schedule_ordering"]),
        "stage_order": list(schedule["stage_order"]),
        "work_item_order": list(schedule["work_item_order"]),
        "overall_status": WORK_ITEM_STATUS_PLANNED,
        "status_counts": {},
        "work_items": work_items,
    }
    _refresh_state_rollups(state)
    return state


def _refresh_state_rollups(state: dict[str, Any]) -> None:
    counts: dict[str, int] = defaultdict(int)
    for item in state["work_items"]:
        counts[str(item["status"])] += 1
    ordered_counts = {
        WORK_ITEM_STATUS_PLANNED: counts.get(WORK_ITEM_STATUS_PLANNED, 0),
        WORK_ITEM_STATUS_RUNNING: counts.get(WORK_ITEM_STATUS_RUNNING, 0),
        WORK_ITEM_STATUS_SUCCEEDED: counts.get(WORK_ITEM_STATUS_SUCCEEDED, 0),
        WORK_ITEM_STATUS_PARTIAL: counts.get(WORK_ITEM_STATUS_PARTIAL, 0),
        WORK_ITEM_STATUS_FAILED: counts.get(WORK_ITEM_STATUS_FAILED, 0),
        WORK_ITEM_STATUS_BLOCKED: counts.get(WORK_ITEM_STATUS_BLOCKED, 0),
        WORK_ITEM_STATUS_SKIPPED: counts.get(WORK_ITEM_STATUS_SKIPPED, 0),
    }
    state["status_counts"] = ordered_counts
    if ordered_counts[WORK_ITEM_STATUS_RUNNING] > 0:
        state["overall_status"] = WORK_ITEM_STATUS_RUNNING
    elif ordered_counts[WORK_ITEM_STATUS_FAILED] > 0:
        state["overall_status"] = WORK_ITEM_STATUS_FAILED
    elif ordered_counts[WORK_ITEM_STATUS_PARTIAL] > 0:
        state["overall_status"] = WORK_ITEM_STATUS_PARTIAL
    elif ordered_counts[WORK_ITEM_STATUS_BLOCKED] > 0:
        state["overall_status"] = WORK_ITEM_STATUS_BLOCKED
    elif ordered_counts[WORK_ITEM_STATUS_PLANNED] > 0:
        state["overall_status"] = WORK_ITEM_STATUS_PARTIAL
    else:
        state["overall_status"] = WORK_ITEM_STATUS_SUCCEEDED


def _validate_execution_state_against_plan(
    *,
    existing_state: Mapping[str, Any],
    plan: Mapping[str, Any],
    schedule: Mapping[str, Any],
) -> None:
    if str(existing_state["suite_id"]) != str(plan["suite_id"]):
        raise ValueError(
            "Existing experiment suite execution state belongs to a different suite_id."
        )
    if str(existing_state["suite_spec_hash"]) != str(plan["suite_metadata"]["suite_spec_hash"]):
        raise ValueError(
            "Existing experiment suite execution state belongs to a different suite_spec_hash."
        )
    if list(existing_state["work_item_order"]) != list(schedule["work_item_order"]):
        raise ValueError(
            "Existing experiment suite execution state does not match the normalized "
            "work-item ordering of the current suite plan."
        )


def _dependency_work_item_ids(
    *,
    suite_cell_id: str,
    stage_id: str,
    stage_order: Sequence[str],
    cells_by_id: Mapping[str, Mapping[str, Any]],
    child_cells_by_parent: Mapping[str, Sequence[Mapping[str, Any]]],
    work_item_id_by_cell_stage: Mapping[tuple[str, str], str],
) -> list[str]:
    if stage_id == STAGE_SIMULATION:
        return []
    if stage_id == STAGE_ANALYSIS:
        dependencies = []
        for child_cell in child_cells_by_parent.get(suite_cell_id, []):
            if str(child_cell["lineage_kind"]) not in {
                SEED_REPLICATE_LINEAGE_KIND,
                SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
            }:
                continue
            dependency_id = work_item_id_by_cell_stage.get(
                (str(child_cell["suite_cell_id"]), STAGE_SIMULATION)
            )
            if dependency_id is not None:
                dependencies.append(dependency_id)
        return dependencies
    if stage_id == STAGE_VALIDATION:
        if STAGE_ANALYSIS not in set(stage_order):
            return []
        dependency_id = work_item_id_by_cell_stage.get((suite_cell_id, STAGE_ANALYSIS))
        return [] if dependency_id is None else [dependency_id]
    if stage_id == STAGE_DASHBOARD:
        dependencies: list[str] = []
        if STAGE_ANALYSIS in set(stage_order):
            analysis_id = work_item_id_by_cell_stage.get((suite_cell_id, STAGE_ANALYSIS))
            if analysis_id is not None:
                dependencies.append(analysis_id)
        if STAGE_VALIDATION in set(stage_order):
            validation_id = work_item_id_by_cell_stage.get((suite_cell_id, STAGE_VALIDATION))
            if validation_id is not None:
                dependencies.append(validation_id)
        return dependencies
    raise ValueError(f"Unsupported stage_id {stage_id!r}.")


def _workspace_owner_cell_id(cell: Mapping[str, Any]) -> str:
    if str(cell["lineage_kind"]) in {
        SEED_REPLICATE_LINEAGE_KIND,
        SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
    }:
        parent_cell_id = cell.get("parent_cell_id")
        if parent_cell_id is None:
            raise ValueError(
                f"Simulation lineage cell {cell['suite_cell_id']!r} is missing parent_cell_id."
            )
        return str(parent_cell_id)
    return str(cell["suite_cell_id"])


def _build_work_item_input_path_key(*, work_item_id: str, stage_id: str) -> str:
    digest = hashlib.sha256(str(work_item_id).encode("utf-8")).hexdigest()
    return f"{stage_id}_{digest[:DEFAULT_WORK_ITEM_INPUT_HASH_LENGTH]}"


def _suite_cell_identity(cell: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "suite_cell_id": str(cell["suite_cell_id"]),
        "display_name": str(cell["display_name"]),
        "lineage_kind": str(cell["lineage_kind"]),
        "parent_cell_id": None if cell.get("parent_cell_id") is None else str(cell["parent_cell_id"]),
        "root_cell_id": None if cell.get("root_cell_id") is None else str(cell["root_cell_id"]),
        "simulation_seed": (
            None if cell.get("simulation_seed") is None else int(cell["simulation_seed"])
        ),
        "dimension_assignments": copy.deepcopy(list(cell["dimension_assignments"])),
        "ablation_references": copy.deepcopy(list(cell["ablation_references"])),
        "ablation_realization": copy.deepcopy(cell.get("ablation_realization")),
    }


def _dependency_status_snapshot(
    dependency_work_item_ids: Sequence[str],
    *,
    state_records_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "work_item_id": str(work_item_id),
            "stage_id": str(state_records_by_id[str(work_item_id)]["stage_id"]),
            "status": str(state_records_by_id[str(work_item_id)]["status"]),
        }
        for work_item_id in dependency_work_item_ids
    ]


def _build_upstream_artifact_snapshot(
    *,
    schedule_entry: Mapping[str, Any],
    state_records_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    upstream = [
        {
            "artifact_kind": "materialized_manifest",
            "path": str(schedule_entry["materialized_manifest_path"]),
        },
        {
            "artifact_kind": "materialized_config",
            "path": str(schedule_entry["materialized_config_path"]),
        },
    ]
    for dependency_id in schedule_entry["dependency_work_item_ids"]:
        dependency_record = state_records_by_id[str(dependency_id)]
        if not dependency_record["attempts"]:
            continue
        last_attempt = dependency_record["attempts"][-1]
        for artifact in last_attempt.get("downstream_artifacts", []):
            upstream.append(copy.deepcopy(dict(artifact)))
    return upstream


def _normalize_stage_execution_result(
    raw_result: Mapping[str, Any] | None,
    *,
    default_role_id: str | None,
) -> dict[str, Any]:
    result = dict(raw_result or {})
    status = str(result.get("status", WORK_ITEM_STATUS_SUCCEEDED))
    if status not in {
        WORK_ITEM_STATUS_SUCCEEDED,
        WORK_ITEM_STATUS_PARTIAL,
        WORK_ITEM_STATUS_FAILED,
        WORK_ITEM_STATUS_BLOCKED,
        WORK_ITEM_STATUS_SKIPPED,
    }:
        raise ValueError(
            f"Stage executor returned unsupported orchestration status {status!r}."
        )
    downstream_artifacts = result.get("downstream_artifacts", [])
    if not isinstance(downstream_artifacts, Sequence) or isinstance(
        downstream_artifacts,
        (str, bytes),
    ):
        raise ValueError("stage_result.downstream_artifacts must be a sequence when provided.")
    normalized_artifacts = []
    for artifact in downstream_artifacts:
        normalized_artifacts.append(
            _resolved_artifact_record(
                artifact,
                default_role_id=default_role_id,
            )
        )
    summary = result.get("summary") or {}
    if not isinstance(summary, Mapping):
        raise ValueError("stage_result.summary must be a mapping when provided.")
    return {
        "status": status,
        "status_detail": str(
            result.get("status_detail", "Stage executor completed without detail.")
        ),
        "summary": copy.deepcopy(dict(summary)),
        "downstream_artifacts": normalized_artifacts,
    }


def _primary_artifact_role_id(schedule_entry: Mapping[str, Any]) -> str | None:
    role_ids = list(schedule_entry["artifact_role_ids"])
    return None if not role_ids else str(role_ids[0])


def _resolved_artifact_paths(
    artifacts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [_resolved_artifact_record(item, default_role_id=None) for item in artifacts]


def _resolved_artifact_record(
    artifact: Mapping[str, Any],
    *,
    default_role_id: str | None,
) -> dict[str, Any]:
    mapping = _require_mapping(artifact, field_name="artifact")
    path = Path(mapping["path"]).resolve()
    record = {
        "path": str(path),
        "artifact_role_id": (
            default_role_id
            if mapping.get("artifact_role_id") is None
            else str(mapping["artifact_role_id"])
        ),
        "artifact_kind": str(mapping.get("artifact_kind", "artifact")),
        "status": str(mapping.get("status", "ready")),
    }
    for key, value in mapping.items():
        if key in {"path", "artifact_role_id", "artifact_kind", "status"}:
            continue
        record[key] = copy.deepcopy(value)
    return record


def _artifact_record(
    *,
    path: str | Path,
    artifact_role_id: str | None,
    artifact_kind: str,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "path": str(Path(path).resolve()),
        "artifact_role_id": artifact_role_id,
        "artifact_kind": artifact_kind,
        "status": "ready",
    }
    payload.update(copy.deepcopy(extra))
    return payload


def _all_ready_artifacts_exist(artifacts: Sequence[Mapping[str, Any]]) -> bool:
    for artifact in artifacts:
        if str(artifact.get("status", "ready")) != "ready":
            continue
        if not Path(str(artifact["path"])).exists():
            return False
    return True


def _blocked_status_detail(
    blocking_dependencies: Sequence[Mapping[str, Any]],
) -> str:
    return (
        "Blocked by unfinished dependencies: "
        + ", ".join(
            f"{item['work_item_id']}={item['status']}"
            for item in blocking_dependencies
        )
    )


def _build_dry_run_summary(
    *,
    plan: Mapping[str, Any],
    schedule: Mapping[str, Any],
    existing_state: Mapping[str, Any] | None,
    state_path: Path,
) -> dict[str, Any]:
    package_paths = build_experiment_suite_package_paths(
        suite_root=Path(plan["output_roots"]["suite_root"]).resolve()
    )
    state_records_by_id = (
        {}
        if existing_state is None
        else {str(item["work_item_id"]): item for item in existing_state["work_items"]}
    )
    schedule_preview = []
    action_counts: dict[str, int] = defaultdict(int)
    for entry in schedule["schedule"]:
        decision = (
            {"action": "execute", "blocking_dependencies": []}
            if not state_records_by_id
            else _resolve_execution_decision(
                schedule_entry=entry,
                state_records_by_id=state_records_by_id,
            )
        )
        action = str(decision["action"])
        if action == "execute":
            action = "would_execute"
        elif action == "blocked":
            action = "would_block"
        action_counts[action] += 1
        schedule_preview.append(
            {
                "work_item_id": str(entry["work_item_id"]),
                "suite_cell_id": str(entry["suite_cell_id"]),
                "stage_id": str(entry["stage_id"]),
                "execution_order_index": int(entry["execution_order_index"]),
                "dependency_work_item_ids": list(entry["dependency_work_item_ids"]),
                "action": action,
                "workspace_root": str(entry["workspace_root"]),
                "materialized_manifest_path": str(entry["materialized_manifest_path"]),
                "materialized_config_path": str(entry["materialized_config_path"]),
            }
        )
    return {
        "workflow_version": EXPERIMENT_SUITE_WORKFLOW_SUMMARY_VERSION,
        "execution_version": EXPERIMENT_SUITE_EXECUTION_VERSION,
        "dry_run": True,
        "suite_id": str(plan["suite_id"]),
        "suite_spec_hash": str(plan["suite_metadata"]["suite_spec_hash"]),
        "predicted_state_path": str(state_path.resolve()),
        "predicted_package_metadata_path": str(package_paths.metadata_json_path.resolve()),
        "predicted_result_index_path": str(package_paths.result_index_path.resolve()),
        "stage_order": list(schedule["stage_order"]),
        "work_item_order": list(schedule["work_item_order"]),
        "action_counts": dict(sorted(action_counts.items())),
        "schedule": schedule_preview,
    }


def _dependency_result_summary(
    context: Mapping[str, Any],
    stage_id: str,
) -> Mapping[str, Any] | None:
    for dependency_record in context["dependency_records"]:
        if str(dependency_record["stage_id"]) != stage_id:
            continue
        attempts = dependency_record.get("attempts", [])
        if not attempts:
            return None
        return attempts[-1].get("result_summary")
    return None


def _summary_metadata_path(summary: Mapping[str, Any] | None) -> str | None:
    if summary is None:
        return None
    metadata_path = summary.get("metadata_path")
    if isinstance(metadata_path, str) and metadata_path:
        return metadata_path
    return None


def _dashboard_validation_metadata_path(
    validation_summary: Mapping[str, Any] | None,
) -> str | None:
    if validation_summary is None:
        return None
    preferred = validation_summary.get("dashboard_validation_bundle_metadata_path")
    if isinstance(preferred, str) and preferred:
        return preferred
    return _summary_metadata_path(validation_summary)


def _load_yaml_mapping_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    return _require_mapping(payload, field_name=str(path))


def _deep_merge(base: Any, patch: Any) -> Any:
    if isinstance(base, Mapping) and isinstance(patch, Mapping):
        merged = {str(key): copy.deepcopy(value) for key, value in base.items()}
        for key, value in patch.items():
            if key in merged:
                merged[str(key)] = _deep_merge(merged[str(key)], value)
            else:
                merged[str(key)] = copy.deepcopy(value)
        return merged
    return copy.deepcopy(patch)


def _require_mapping(payload: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return copy.deepcopy(dict(payload))


__all__ = [
    "DEFAULT_EXECUTION_STATE_FILENAME",
    "EXPERIMENT_SUITE_EXECUTION_STATE_VERSION",
    "EXPERIMENT_SUITE_EXECUTION_VERSION",
    "EXPERIMENT_SUITE_WORKFLOW_SUMMARY_VERSION",
    "build_experiment_suite_execution_schedule",
    "execute_experiment_suite_plan",
    "execute_experiment_suite_workflow",
    "load_experiment_suite_execution_state",
]
