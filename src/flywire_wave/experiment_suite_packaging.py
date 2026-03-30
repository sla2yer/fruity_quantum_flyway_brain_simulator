from __future__ import annotations

import copy
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dashboard_session_contract import load_dashboard_session_metadata
from .experiment_analysis_contract import load_experiment_analysis_bundle_metadata
from .experiment_suite_contract import (
    ABLATION_VARIANT_LINEAGE_KIND,
    BASE_CONDITION_LINEAGE_KIND,
    DASHBOARD_SESSION_ROLE_ID,
    DASHBOARD_SESSION_SOURCE_KIND,
    EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
    EXPERIMENT_ANALYSIS_SOURCE_KIND,
    EXPERIMENT_SUITE_CONTRACT_VERSION,
    EXPERIMENT_SUITE_DESIGN_NOTE,
    EXPERIMENT_SUITE_DESIGN_NOTE_VERSION,
    SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
    SEED_REPLICATE_LINEAGE_KIND,
    SIMULATOR_RESULT_BUNDLE_ROLE_ID,
    SIMULATOR_RESULT_SOURCE_KIND,
    VALIDATION_BUNDLE_ROLE_ID,
    VALIDATION_BUNDLE_SOURCE_KIND,
    WORK_ITEM_STATUS_BLOCKED,
    WORK_ITEM_STATUS_FAILED,
    WORK_ITEM_STATUS_PARTIAL,
    WORK_ITEM_STATUS_PLANNED,
    WORK_ITEM_STATUS_RUNNING,
    WORK_ITEM_STATUS_SKIPPED,
    WORK_ITEM_STATUS_SUCCEEDED,
)
from .experiment_suite_planning import (
    EXPERIMENT_SUITE_PLAN_VERSION,
    STAGE_ANALYSIS,
    STAGE_DASHBOARD,
    STAGE_SIMULATION,
    STAGE_VALIDATION,
)
from .io_utils import ensure_dir, write_csv_rows, write_json
from .simulator_result_contract import (
    load_simulator_result_bundle_metadata,
)
from .stimulus_contract import (
    ASSET_STATUS_MISSING,
    ASSET_STATUS_READY,
    _normalize_asset_status,
    _normalize_identifier,
    _normalize_json_mapping,
    _normalize_nonempty_string,
)
from .validation_contract import load_validation_bundle_metadata
from .validation_reporting import load_validation_ladder_package_metadata


EXPERIMENT_SUITE_PACKAGE_CONTRACT_VERSION = "experiment_suite_package.v1"
EXPERIMENT_SUITE_RESULT_INDEX_FORMAT = "json_experiment_suite_result_index.v1"

DEFAULT_PACKAGE_DIRECTORY_NAME = "package"
DEFAULT_INDEX_DIRECTORY_NAME = "indexes"
DEFAULT_EXPORT_DIRECTORY_NAME = "exports"
DEFAULT_REPORT_DIRECTORY_NAME = "report"

METADATA_JSON_KEY = "metadata_json"
RESULT_INDEX_ARTIFACT_ID = "result_index"
CELL_INVENTORY_CSV_ARTIFACT_ID = "cell_inventory_csv"
STAGE_ARTIFACT_INVENTORY_CSV_ARTIFACT_ID = "stage_artifact_inventory_csv"
INVENTORY_REPORT_ARTIFACT_ID = "inventory_report"

PACKAGE_METADATA_SCOPE = "contract_metadata"
MACHINE_INDEX_SCOPE = "machine_index"
REVIEW_INVENTORY_SCOPE = "review_inventory"

SUMMARY_TABLE_CATEGORY = "summary_table"
COMPARISON_PLOT_CATEGORY = "comparison_plot"
REVIEW_ARTIFACT_CATEGORY = "review_artifact"
UI_ARTIFACT_CATEGORY = "ui_artifact"
TRACE_ARTIFACT_CATEGORY = "trace_artifact"
DIAGNOSTIC_ARTIFACT_CATEGORY = "diagnostic_artifact"
BUNDLE_METADATA_CATEGORY = "bundle_metadata"
BUNDLE_ARTIFACT_CATEGORY = "bundle_artifact"

_STAGE_ORDER = (
    STAGE_SIMULATION,
    STAGE_ANALYSIS,
    STAGE_VALIDATION,
    STAGE_DASHBOARD,
)
_STAGE_SOURCE_KIND = {
    STAGE_SIMULATION: SIMULATOR_RESULT_SOURCE_KIND,
    STAGE_ANALYSIS: EXPERIMENT_ANALYSIS_SOURCE_KIND,
    STAGE_VALIDATION: VALIDATION_BUNDLE_SOURCE_KIND,
    STAGE_DASHBOARD: DASHBOARD_SESSION_SOURCE_KIND,
}
_STAGE_ROLE_ID = {
    STAGE_SIMULATION: SIMULATOR_RESULT_BUNDLE_ROLE_ID,
    STAGE_ANALYSIS: EXPERIMENT_ANALYSIS_BUNDLE_ROLE_ID,
    STAGE_VALIDATION: VALIDATION_BUNDLE_ROLE_ID,
    STAGE_DASHBOARD: DASHBOARD_SESSION_ROLE_ID,
}
_CELL_STATUS_PRIORITY = {
    WORK_ITEM_STATUS_RUNNING: 0,
    WORK_ITEM_STATUS_FAILED: 1,
    WORK_ITEM_STATUS_PARTIAL: 2,
    WORK_ITEM_STATUS_BLOCKED: 3,
    WORK_ITEM_STATUS_PLANNED: 4,
    WORK_ITEM_STATUS_SKIPPED: 5,
    WORK_ITEM_STATUS_SUCCEEDED: 6,
}
_ARTIFACT_IDS = (
    METADATA_JSON_KEY,
    RESULT_INDEX_ARTIFACT_ID,
    CELL_INVENTORY_CSV_ARTIFACT_ID,
    STAGE_ARTIFACT_INVENTORY_CSV_ARTIFACT_ID,
    INVENTORY_REPORT_ARTIFACT_ID,
)
_ARTIFACT_FORMATS = {
    METADATA_JSON_KEY: "json_experiment_suite_package_metadata.v1",
    RESULT_INDEX_ARTIFACT_ID: EXPERIMENT_SUITE_RESULT_INDEX_FORMAT,
    CELL_INVENTORY_CSV_ARTIFACT_ID: "csv_experiment_suite_cell_inventory.v1",
    STAGE_ARTIFACT_INVENTORY_CSV_ARTIFACT_ID: (
        "csv_experiment_suite_stage_artifact_inventory.v1"
    ),
    INVENTORY_REPORT_ARTIFACT_ID: "md_experiment_suite_inventory_report.v1",
}
_ARTIFACT_SCOPES = {
    METADATA_JSON_KEY: PACKAGE_METADATA_SCOPE,
    RESULT_INDEX_ARTIFACT_ID: MACHINE_INDEX_SCOPE,
    CELL_INVENTORY_CSV_ARTIFACT_ID: REVIEW_INVENTORY_SCOPE,
    STAGE_ARTIFACT_INVENTORY_CSV_ARTIFACT_ID: REVIEW_INVENTORY_SCOPE,
    INVENTORY_REPORT_ARTIFACT_ID: REVIEW_INVENTORY_SCOPE,
}
_ARTIFACT_DESCRIPTIONS = {
    METADATA_JSON_KEY: "Authoritative suite-owned package anchor for Milestone 15 outputs.",
    RESULT_INDEX_ARTIFACT_ID: (
        "Machine-friendly suite result index keyed by suite-cell lineage, "
        "dimension values, ablation identity, and realized stage artifacts."
    ),
    CELL_INVENTORY_CSV_ARTIFACT_ID: (
        "Reviewer-friendly suite-cell inventory with stage statuses, dimensions, "
        "ablations, and linked simulation lineage."
    ),
    STAGE_ARTIFACT_INVENTORY_CSV_ARTIFACT_ID: (
        "Reviewer-friendly flat inventory of realized stage artifacts and bundle references."
    ),
    INVENTORY_REPORT_ARTIFACT_ID: (
        "Lightweight offline suite inventory report for quick Milestone 15 review."
    ),
}


@dataclass(frozen=True)
class ExperimentSuitePackagePaths:
    suite_root: Path
    package_directory: Path
    index_directory: Path
    export_directory: Path
    report_directory: Path
    metadata_json_path: Path
    result_index_path: Path
    cell_inventory_csv_path: Path
    stage_artifact_inventory_csv_path: Path
    inventory_report_path: Path

    def asset_paths(self) -> dict[str, Path]:
        return {
            METADATA_JSON_KEY: self.metadata_json_path,
            RESULT_INDEX_ARTIFACT_ID: self.result_index_path,
            CELL_INVENTORY_CSV_ARTIFACT_ID: self.cell_inventory_csv_path,
            STAGE_ARTIFACT_INVENTORY_CSV_ARTIFACT_ID: (
                self.stage_artifact_inventory_csv_path
            ),
            INVENTORY_REPORT_ARTIFACT_ID: self.inventory_report_path,
        }


def build_experiment_suite_package_paths(
    *,
    suite_root: str | Path,
) -> ExperimentSuitePackagePaths:
    resolved_suite_root = Path(suite_root).resolve()
    package_directory = (
        resolved_suite_root / DEFAULT_PACKAGE_DIRECTORY_NAME
    ).resolve()
    index_directory = (package_directory / DEFAULT_INDEX_DIRECTORY_NAME).resolve()
    export_directory = (package_directory / DEFAULT_EXPORT_DIRECTORY_NAME).resolve()
    report_directory = (package_directory / DEFAULT_REPORT_DIRECTORY_NAME).resolve()
    return ExperimentSuitePackagePaths(
        suite_root=resolved_suite_root,
        package_directory=package_directory,
        index_directory=index_directory,
        export_directory=export_directory,
        report_directory=report_directory,
        metadata_json_path=package_directory / "experiment_suite_package.json",
        result_index_path=index_directory / "result_index.json",
        cell_inventory_csv_path=export_directory / "cell_inventory.csv",
        stage_artifact_inventory_csv_path=export_directory / "stage_artifacts.csv",
        inventory_report_path=report_directory / "inventory.md",
    )


def resolve_experiment_suite_package_metadata_path(
    *,
    suite_root: str | Path,
) -> Path:
    return build_experiment_suite_package_paths(
        suite_root=suite_root,
    ).metadata_json_path.resolve()


def package_experiment_suite_outputs(
    plan: Mapping[str, Any],
    *,
    state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_plan = _require_mapping(plan, field_name="plan")
    if str(normalized_plan.get("plan_version")) != EXPERIMENT_SUITE_PLAN_VERSION:
        raise ValueError(
            f"plan.plan_version must be {EXPERIMENT_SUITE_PLAN_VERSION!r}."
        )

    suite_root = Path(normalized_plan["output_roots"]["suite_root"]).resolve()
    package_paths = build_experiment_suite_package_paths(suite_root=suite_root)
    resolved_state = _resolve_state_snapshot(plan=normalized_plan, state=state)
    result_index = build_experiment_suite_result_index(
        normalized_plan,
        state=resolved_state,
    )
    package_metadata = build_experiment_suite_package_metadata(
        plan=normalized_plan,
        state=resolved_state,
        result_index=result_index,
        package_paths=package_paths,
    )

    ensure_dir(package_paths.package_directory)
    ensure_dir(package_paths.index_directory)
    ensure_dir(package_paths.export_directory)
    ensure_dir(package_paths.report_directory)
    write_json(result_index, package_paths.result_index_path)
    write_csv_rows(
        fieldnames=_cell_inventory_csv_fieldnames(),
        rows=_build_cell_inventory_csv_rows(result_index),
        out_path=package_paths.cell_inventory_csv_path,
    )
    write_csv_rows(
        fieldnames=_stage_artifact_inventory_csv_fieldnames(),
        rows=_build_stage_artifact_inventory_csv_rows(result_index),
        out_path=package_paths.stage_artifact_inventory_csv_path,
    )
    package_paths.inventory_report_path.write_text(
        _render_inventory_report(package_metadata=package_metadata, result_index=result_index),
        encoding="utf-8",
    )
    write_experiment_suite_package_metadata(
        package_metadata,
        package_paths.metadata_json_path,
    )

    return {
        "contract_version": EXPERIMENT_SUITE_PACKAGE_CONTRACT_VERSION,
        "suite_id": str(package_metadata["suite_reference"]["suite_id"]),
        "suite_spec_hash": str(package_metadata["suite_reference"]["suite_spec_hash"]),
        "overall_status": str(package_metadata["summary"]["overall_status"]),
        "package_directory": str(package_paths.package_directory),
        "metadata_path": str(package_paths.metadata_json_path),
        "result_index_path": str(package_paths.result_index_path),
        "cell_inventory_csv_path": str(package_paths.cell_inventory_csv_path),
        "stage_artifact_inventory_csv_path": str(
            package_paths.stage_artifact_inventory_csv_path
        ),
        "inventory_report_path": str(package_paths.inventory_report_path),
    }


def build_experiment_suite_result_index(
    plan: Mapping[str, Any],
    *,
    state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_plan = _require_mapping(plan, field_name="plan")
    resolved_state = _resolve_state_snapshot(plan=normalized_plan, state=state)
    stage_order = [
        str(item["stage_id"]) for item in normalized_plan["stage_targets"]
    ]
    cells = [
        copy.deepcopy(dict(item)) for item in normalized_plan["cell_catalog"]
    ]
    cell_index_by_id = {
        str(item["suite_cell_id"]): index for index, item in enumerate(cells)
    }
    state_records_by_id = {
        str(item["work_item_id"]): copy.deepcopy(dict(item))
        for item in resolved_state["work_items"]
    }
    stage_status_counts: dict[str, dict[str, int]] = {
        stage_id: {
            WORK_ITEM_STATUS_PLANNED: 0,
            WORK_ITEM_STATUS_RUNNING: 0,
            WORK_ITEM_STATUS_SUCCEEDED: 0,
            WORK_ITEM_STATUS_PARTIAL: 0,
            WORK_ITEM_STATUS_FAILED: 0,
            WORK_ITEM_STATUS_BLOCKED: 0,
            WORK_ITEM_STATUS_SKIPPED: 0,
        }
        for stage_id in stage_order
    }

    cell_records: list[dict[str, Any]] = []
    stage_artifacts: list[dict[str, Any]] = []
    for cell in cells:
        direct_stage_records: list[dict[str, Any]] = []
        for stage_target in sorted(
            list(cell["stage_targets"]),
            key=lambda item: (
                stage_order.index(str(item["stage_id"])),
                str(item["work_item_id"]),
            ),
        ):
            work_item_id = str(stage_target["work_item_id"])
            state_record = state_records_by_id.get(work_item_id)
            if state_record is None:
                state_record = _planned_state_record_for_target(stage_target)
            stage_record = _build_stage_record(
                stage_target=stage_target,
                state_record=state_record,
                suite_cell_id=str(cell["suite_cell_id"]),
                cell_index=cell_index_by_id[str(cell["suite_cell_id"])],
                stage_order=stage_order,
            )
            direct_stage_records.append(stage_record)
            stage_status_counts[str(stage_record["stage_id"])][
                str(stage_record["status"])
            ] += 1
            stage_artifacts.extend(copy.deepcopy(stage_record["artifacts"]))

        cell_records.append(
            {
                "suite_cell_id": str(cell["suite_cell_id"]),
                "display_name": str(cell["display_name"]),
                "lineage_kind": str(cell["lineage_kind"]),
                "parent_cell_id": (
                    None
                    if cell.get("parent_cell_id") is None
                    else str(cell["parent_cell_id"])
                ),
                "root_cell_id": (
                    None
                    if cell.get("root_cell_id") is None
                    else str(cell["root_cell_id"])
                ),
                "simulation_seed": (
                    None
                    if cell.get("simulation_seed") is None
                    else int(cell["simulation_seed"])
                ),
                "dimension_value_ids": _dimension_value_id_mapping(cell),
                "dimensions": copy.deepcopy(dict(cell["selected_dimension_values"])),
                "ablation_identity_ids": _ablation_identity_ids(cell),
                "ablations": copy.deepcopy(list(cell["ablation_references"])),
                "overall_status": _roll_up_cell_status(direct_stage_records),
                "stage_records": direct_stage_records,
            }
        )

    cell_records_by_id = {
        str(item["suite_cell_id"]): item for item in cell_records
    }
    for item in cell_records:
        simulation_lineage_cells = _build_simulation_lineage_cell_records(
            cell=item,
            cell_records_by_id=cell_records_by_id,
            cell_index_by_id=cell_index_by_id,
        )
        simulation_lineage_artifacts = [
            copy.deepcopy(dict(artifact))
            for lineage_cell in simulation_lineage_cells
            for stage_record in lineage_cell["stage_records"]
            if str(stage_record["stage_id"]) == STAGE_SIMULATION
            for artifact in stage_record["artifacts"]
        ]
        item["simulation_lineage_cells"] = simulation_lineage_cells
        item["simulation_lineage_artifacts"] = simulation_lineage_artifacts
        item["resolved_bundle_ids"] = sorted(
            {
                str(artifact["bundle_id"])
                for stage_record in item["stage_records"]
                for artifact in stage_record["artifacts"]
                if artifact.get("bundle_id") is not None
            }
            | {
                str(artifact["bundle_id"])
                for artifact in simulation_lineage_artifacts
                if artifact.get("bundle_id") is not None
            }
        )
        item["report_artifact_paths"] = sorted(
            {
                str(artifact["path"])
                for stage_record in item["stage_records"]
                for artifact in stage_record["artifacts"]
                if artifact["inventory_category"] == REVIEW_ARTIFACT_CATEGORY
            }
        )

    stage_artifacts = _sort_stage_artifacts(
        stage_artifacts,
        cell_index_by_id=cell_index_by_id,
        stage_order=stage_order,
    )
    cell_status_counts = _cell_status_counts(cell_records)
    return {
        "format_version": EXPERIMENT_SUITE_RESULT_INDEX_FORMAT,
        "suite_id": str(normalized_plan["suite_id"]),
        "suite_label": str(normalized_plan["suite_label"]),
        "suite_spec_hash": str(normalized_plan["suite_metadata"]["suite_spec_hash"]),
        "suite_root": str(Path(normalized_plan["output_roots"]["suite_root"]).resolve()),
        "suite_plan_path": str(
            Path(normalized_plan["output_roots"]["suite_plan_path"]).resolve()
        ),
        "suite_metadata_path": str(
            Path(normalized_plan["output_roots"]["suite_metadata_path"]).resolve()
        ),
        "state_path": str(Path(resolved_state["state_path"]).resolve()),
        "stage_order": list(stage_order),
        "overall_status": str(resolved_state["overall_status"]),
        "summary": {
            "suite_cell_count": len(cell_records),
            "work_item_count": len(resolved_state["work_items"]),
            "stage_artifact_count": len(stage_artifacts),
            "cell_status_counts": cell_status_counts,
            "stage_status_counts": stage_status_counts,
        },
        "cell_records": cell_records,
        "stage_artifacts": stage_artifacts,
    }


def build_experiment_suite_package_metadata(
    *,
    plan: Mapping[str, Any],
    state: Mapping[str, Any],
    result_index: Mapping[str, Any],
    package_paths: ExperimentSuitePackagePaths,
) -> dict[str, Any]:
    normalized_plan = _require_mapping(plan, field_name="plan")
    normalized_state = _require_mapping(state, field_name="state")
    normalized_result_index = _require_mapping(
        result_index,
        field_name="result_index",
    )
    return {
        "contract_version": EXPERIMENT_SUITE_PACKAGE_CONTRACT_VERSION,
        "design_note": EXPERIMENT_SUITE_DESIGN_NOTE,
        "design_note_version": EXPERIMENT_SUITE_DESIGN_NOTE_VERSION,
        "suite_reference": {
            "suite_id": str(normalized_plan["suite_id"]),
            "suite_label": str(normalized_plan["suite_label"]),
            "suite_spec_hash": str(normalized_plan["suite_metadata"]["suite_spec_hash"]),
            "suite_contract_version": EXPERIMENT_SUITE_CONTRACT_VERSION,
            "suite_root": str(Path(normalized_plan["output_roots"]["suite_root"]).resolve()),
            "suite_plan_path": str(
                Path(normalized_plan["output_roots"]["suite_plan_path"]).resolve()
            ),
            "suite_metadata_path": str(
                Path(normalized_plan["output_roots"]["suite_metadata_path"]).resolve()
            ),
            "state_path": str(Path(normalized_state["state_path"]).resolve()),
        },
        "package_layout": {
            "package_directory": str(package_paths.package_directory),
            "index_directory": str(package_paths.index_directory),
            "export_directory": str(package_paths.export_directory),
            "report_directory": str(package_paths.report_directory),
        },
        "artifacts": {
            artifact_id: _package_artifact_record(
                path=path,
                artifact_id=artifact_id,
            )
            for artifact_id, path in package_paths.asset_paths().items()
        },
        "summary": {
            "overall_status": str(normalized_result_index["overall_status"]),
            "suite_cell_count": int(normalized_result_index["summary"]["suite_cell_count"]),
            "work_item_count": int(normalized_result_index["summary"]["work_item_count"]),
            "stage_artifact_count": int(
                normalized_result_index["summary"]["stage_artifact_count"]
            ),
            "cell_status_counts": copy.deepcopy(
                dict(normalized_result_index["summary"]["cell_status_counts"])
            ),
            "stage_status_counts": copy.deepcopy(
                dict(normalized_result_index["summary"]["stage_status_counts"])
            ),
        },
        "stable_cell_ordering": str(
            normalized_plan["stable_suite_cell_ordering"]
        ),
        "stable_work_item_ordering": str(
            normalized_plan["stable_work_item_ordering"]
        ),
    }


def parse_experiment_suite_package_metadata(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("experiment_suite_package metadata must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "design_note",
        "design_note_version",
        "suite_reference",
        "package_layout",
        "artifacts",
        "summary",
        "stable_cell_ordering",
        "stable_work_item_ordering",
    )
    missing = [field for field in required_fields if field not in normalized]
    if missing:
        raise ValueError(
            "experiment_suite_package metadata is missing required fields: "
            f"{missing!r}."
        )
    contract_version = _normalize_nonempty_string(
        normalized["contract_version"],
        field_name="contract_version",
    )
    if contract_version != EXPERIMENT_SUITE_PACKAGE_CONTRACT_VERSION:
        raise ValueError(
            "experiment_suite_package contract_version must be "
            f"{EXPERIMENT_SUITE_PACKAGE_CONTRACT_VERSION!r}."
        )
    design_note = _normalize_nonempty_string(
        normalized["design_note"],
        field_name="design_note",
    )
    if design_note != EXPERIMENT_SUITE_DESIGN_NOTE:
        raise ValueError(
            f"design_note must be {EXPERIMENT_SUITE_DESIGN_NOTE!r}."
        )
    design_note_version = _normalize_nonempty_string(
        normalized["design_note_version"],
        field_name="design_note_version",
    )
    if design_note_version != EXPERIMENT_SUITE_DESIGN_NOTE_VERSION:
        raise ValueError(
            "design_note_version must be "
            f"{EXPERIMENT_SUITE_DESIGN_NOTE_VERSION!r}."
        )
    suite_reference = _normalize_suite_reference(normalized["suite_reference"])
    package_paths = build_experiment_suite_package_paths(
        suite_root=suite_reference["suite_root"],
    )
    package_layout = _normalize_package_layout(
        normalized["package_layout"],
        expected_paths=package_paths,
    )
    artifacts = _normalize_package_artifacts(
        normalized["artifacts"],
        expected_paths=package_paths.asset_paths(),
    )
    summary = _normalize_package_summary(normalized["summary"])
    return {
        "contract_version": contract_version,
        "design_note": design_note,
        "design_note_version": design_note_version,
        "suite_reference": suite_reference,
        "package_layout": package_layout,
        "artifacts": artifacts,
        "summary": summary,
        "stable_cell_ordering": _normalize_nonempty_string(
            normalized["stable_cell_ordering"],
            field_name="stable_cell_ordering",
        ),
        "stable_work_item_ordering": _normalize_nonempty_string(
            normalized["stable_work_item_ordering"],
            field_name="stable_work_item_ordering",
        ),
    }


def write_experiment_suite_package_metadata(
    package_metadata: Mapping[str, Any],
    output_path: str | Path | None = None,
) -> Path:
    normalized = parse_experiment_suite_package_metadata(package_metadata)
    target_path = (
        Path(output_path).resolve()
        if output_path is not None
        else Path(normalized["artifacts"][METADATA_JSON_KEY]["path"]).resolve()
    )
    return write_json(normalized, target_path)


def load_experiment_suite_package_metadata(
    metadata_path: str | Path,
) -> dict[str, Any]:
    with Path(metadata_path).resolve().open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_experiment_suite_package_metadata(payload)


def discover_experiment_suite_package_paths(
    record: Mapping[str, Any],
) -> dict[str, Path]:
    normalized = parse_experiment_suite_package_metadata(
        record.get("experiment_suite_package")
        if isinstance(record.get("experiment_suite_package"), Mapping)
        else record
    )
    return {
        artifact_id: Path(str(artifact["path"])).resolve()
        for artifact_id, artifact in normalized["artifacts"].items()
    }


def load_experiment_suite_result_index(
    record: Mapping[str, Any] | str | Path,
) -> dict[str, Any]:
    if isinstance(record, (str, Path)):
        with Path(record).resolve().open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    elif isinstance(record, Mapping):
        if "cell_records" in record and "stage_artifacts" in record:
            payload = record
        else:
            metadata = parse_experiment_suite_package_metadata(
                record.get("experiment_suite_package")
                if isinstance(record.get("experiment_suite_package"), Mapping)
                else record
            )
            with Path(
                metadata["artifacts"][RESULT_INDEX_ARTIFACT_ID]["path"]
            ).resolve().open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
    else:
        raise ValueError(
            "load_experiment_suite_result_index requires a mapping or path."
        )
    normalized = _require_mapping(payload, field_name="result_index")
    required_fields = (
        "format_version",
        "suite_id",
        "suite_label",
        "suite_spec_hash",
        "suite_root",
        "suite_plan_path",
        "suite_metadata_path",
        "state_path",
        "stage_order",
        "overall_status",
        "summary",
        "cell_records",
        "stage_artifacts",
    )
    missing = [field for field in required_fields if field not in normalized]
    if missing:
        raise ValueError(
            f"result_index is missing required fields {missing!r}."
        )
    if str(normalized["format_version"]) != EXPERIMENT_SUITE_RESULT_INDEX_FORMAT:
        raise ValueError(
            "result_index.format_version must be "
            f"{EXPERIMENT_SUITE_RESULT_INDEX_FORMAT!r}."
        )
    return copy.deepcopy(dict(normalized))


def discover_experiment_suite_package_cells(
    record: Mapping[str, Any] | str | Path,
    *,
    lineage_kind: str | None = None,
    overall_status: str | None = None,
    ablation_family_id: str | None = None,
    dimension_id: str | None = None,
    value_id: str | None = None,
    stage_id: str | None = None,
    stage_status: str | None = None,
) -> list[dict[str, Any]]:
    index = load_experiment_suite_result_index(record)
    normalized_lineage_kind = (
        None
        if lineage_kind is None
        else _normalize_identifier(lineage_kind, field_name="lineage_kind")
    )
    normalized_overall_status = (
        None
        if overall_status is None
        else _normalize_nonempty_string(
            overall_status,
            field_name="overall_status",
        )
    )
    normalized_ablation_family_id = (
        None
        if ablation_family_id is None
        else _normalize_identifier(
            ablation_family_id,
            field_name="ablation_family_id",
        )
    )
    normalized_dimension_id = (
        None
        if dimension_id is None
        else _normalize_identifier(dimension_id, field_name="dimension_id")
    )
    normalized_value_id = (
        None
        if value_id is None
        else _normalize_identifier(value_id, field_name="value_id")
    )
    normalized_stage_id = (
        None
        if stage_id is None
        else _normalize_identifier(stage_id, field_name="stage_id")
    )
    normalized_stage_status = (
        None
        if stage_status is None
        else _normalize_nonempty_string(stage_status, field_name="stage_status")
    )
    discovered: list[dict[str, Any]] = []
    for item in index["cell_records"]:
        if (
            normalized_lineage_kind is not None
            and str(item["lineage_kind"]) != normalized_lineage_kind
        ):
            continue
        if (
            normalized_overall_status is not None
            and str(item["overall_status"]) != normalized_overall_status
        ):
            continue
        if normalized_ablation_family_id is not None and normalized_ablation_family_id not in {
            str(entry["ablation_family_id"]) for entry in item["ablations"]
        }:
            continue
        if normalized_dimension_id is not None:
            if normalized_dimension_id not in set(item["dimension_value_ids"]):
                continue
            if (
                normalized_value_id is not None
                and str(item["dimension_value_ids"][normalized_dimension_id])
                != normalized_value_id
            ):
                continue
        if normalized_stage_id is not None:
            matches = [
                stage_record
                for stage_record in item["stage_records"]
                if str(stage_record["stage_id"]) == normalized_stage_id
            ]
            if not matches:
                continue
            if normalized_stage_status is not None and all(
                str(stage_record["status"]) != normalized_stage_status
                for stage_record in matches
            ):
                continue
        discovered.append(copy.deepcopy(dict(item)))
    return discovered


def discover_experiment_suite_stage_artifacts(
    record: Mapping[str, Any] | str | Path,
    *,
    suite_cell_id: str | None = None,
    stage_id: str | None = None,
    inventory_category: str | None = None,
    source_kind: str | None = None,
    artifact_id: str | None = None,
    stage_status: str | None = None,
) -> list[dict[str, Any]]:
    index = load_experiment_suite_result_index(record)
    normalized_suite_cell_id = (
        None
        if suite_cell_id is None
        else _normalize_identifier(suite_cell_id, field_name="suite_cell_id")
    )
    normalized_stage_id = (
        None
        if stage_id is None
        else _normalize_identifier(stage_id, field_name="stage_id")
    )
    normalized_category = (
        None
        if inventory_category is None
        else _normalize_identifier(
            inventory_category,
            field_name="inventory_category",
        )
    )
    normalized_source_kind = (
        None
        if source_kind is None
        else _normalize_identifier(source_kind, field_name="source_kind")
    )
    normalized_artifact_id = (
        None
        if artifact_id is None
        else _normalize_identifier(artifact_id, field_name="artifact_id")
    )
    normalized_stage_status = (
        None
        if stage_status is None
        else _normalize_nonempty_string(stage_status, field_name="stage_status")
    )
    discovered: list[dict[str, Any]] = []
    for item in index["stage_artifacts"]:
        if (
            normalized_suite_cell_id is not None
            and str(item["suite_cell_id"]) != normalized_suite_cell_id
        ):
            continue
        if normalized_stage_id is not None and str(item["stage_id"]) != normalized_stage_id:
            continue
        if (
            normalized_category is not None
            and str(item["inventory_category"]) != normalized_category
        ):
            continue
        if (
            normalized_source_kind is not None
            and str(item["source_kind"]) != normalized_source_kind
        ):
            continue
        if (
            normalized_artifact_id is not None
            and str(item["artifact_id"]) != normalized_artifact_id
        ):
            continue
        if (
            normalized_stage_status is not None
            and str(item["stage_status"]) != normalized_stage_status
        ):
            continue
        discovered.append(copy.deepcopy(dict(item)))
    return discovered


def _resolve_state_snapshot(
    *,
    plan: Mapping[str, Any],
    state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if state is not None:
        return _require_mapping(state, field_name="state")
    work_items = []
    for item in plan["work_item_catalog"]:
        work_items.append(
            {
                "work_item_id": str(item["work_item_id"]),
                "suite_cell_id": str(item["suite_cell_id"]),
                "stage_id": str(item["stage_id"]),
                "artifact_role_ids": list(item["artifact_role_ids"]),
                "workspace_root": str(
                    Path(plan["output_roots"]["cells_root"])
                    / str(item["suite_cell_id"])
                    / "workspace"
                ),
                "materialized_manifest_path": "",
                "materialized_config_path": "",
                "status": WORK_ITEM_STATUS_PLANNED,
                "status_detail": "No persisted execution state is available.",
                "attempt_count": 0,
                "attempts": [],
            }
        )
    return {
        "state_version": "experiment_suite_execution_state.v1",
        "suite_id": str(plan["suite_id"]),
        "suite_label": str(plan["suite_label"]),
        "suite_spec_hash": str(plan["suite_metadata"]["suite_spec_hash"]),
        "suite_root": str(Path(plan["output_roots"]["suite_root"]).resolve()),
        "state_path": str(
            (
                Path(plan["output_roots"]["suite_root"])
                / "experiment_suite_execution_state.json"
            ).resolve()
        ),
        "overall_status": WORK_ITEM_STATUS_PLANNED,
        "work_items": work_items,
    }


def _planned_state_record_for_target(stage_target: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "work_item_id": str(stage_target["work_item_id"]),
        "suite_cell_id": "",
        "stage_id": str(stage_target["stage_id"]),
        "artifact_role_ids": [str(stage_target["artifact_role_id"])],
        "workspace_root": "",
        "materialized_manifest_path": "",
        "materialized_config_path": "",
        "status": WORK_ITEM_STATUS_PLANNED,
        "status_detail": "No persisted execution state is available.",
        "attempt_count": 0,
        "attempts": [],
    }


def _build_stage_record(
    *,
    stage_target: Mapping[str, Any],
    state_record: Mapping[str, Any],
    suite_cell_id: str,
    cell_index: int,
    stage_order: Sequence[str],
) -> dict[str, Any]:
    latest_attempt = (
        copy.deepcopy(dict(state_record["attempts"][-1]))
        if state_record.get("attempts")
        else None
    )
    artifacts, resolution_errors = _resolve_stage_artifacts(
        stage_id=str(stage_target["stage_id"]),
        state_record=state_record,
        latest_attempt=latest_attempt,
        suite_cell_id=suite_cell_id,
        cell_index=cell_index,
        stage_order=stage_order,
    )
    return {
        "stage_id": str(stage_target["stage_id"]),
        "work_item_id": str(stage_target["work_item_id"]),
        "artifact_role_id": str(stage_target["artifact_role_id"]),
        "status": str(state_record["status"]),
        "status_detail": str(state_record.get("status_detail", "")),
        "attempt_count": int(state_record.get("attempt_count", 0)),
        "planned_output_root": str(stage_target["output_root"]),
        "planned_metadata_path": str(stage_target["metadata_path"]),
        "workspace_root": str(state_record.get("workspace_root", "")),
        "materialized_manifest_path": str(
            state_record.get("materialized_manifest_path", "")
        ),
        "materialized_config_path": str(
            state_record.get("materialized_config_path", "")
        ),
        "dependency_statuses": (
            []
            if latest_attempt is None
            else copy.deepcopy(list(latest_attempt.get("dependency_statuses", [])))
        ),
        "error": None if latest_attempt is None else copy.deepcopy(latest_attempt.get("error")),
        "artifact_resolution_errors": resolution_errors,
        "bundle_ids": sorted(
            {
                str(artifact["bundle_id"])
                for artifact in artifacts
                if artifact.get("bundle_id") is not None
            }
        ),
        "resolved_metadata_paths": sorted(
            {
                str(artifact["path"])
                for artifact in artifacts
                if str(artifact["artifact_id"]) == METADATA_JSON_KEY
            }
        ),
        "artifacts": artifacts,
    }


def _resolve_stage_artifacts(
    *,
    stage_id: str,
    state_record: Mapping[str, Any],
    latest_attempt: Mapping[str, Any] | None,
    suite_cell_id: str,
    cell_index: int,
    stage_order: Sequence[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    artifacts: list[dict[str, Any]] = []
    errors: list[str] = []
    summary = (
        {}
        if latest_attempt is None
        else _require_mapping(
            latest_attempt.get("result_summary", {}),
            field_name="latest_attempt.result_summary",
        )
    )

    if stage_id == STAGE_SIMULATION:
        for run in list(summary.get("executed_runs", [])):
            if not isinstance(run, Mapping):
                continue
            metadata_path = run.get("metadata_path")
            if isinstance(metadata_path, str) and metadata_path:
                loaded, load_errors = _load_simulator_bundle_artifacts(
                    metadata_path=metadata_path,
                    suite_cell_id=suite_cell_id,
                    stage_id=stage_id,
                    work_item_id=str(state_record["work_item_id"]),
                    stage_status=str(state_record["status"]),
                )
                artifacts.extend(loaded)
                errors.extend(load_errors)
    elif stage_id == STAGE_ANALYSIS:
        metadata_path = _summary_metadata_path(summary)
        if metadata_path is not None:
            loaded, load_errors = _load_analysis_bundle_artifacts(
                metadata_path=metadata_path,
                suite_cell_id=suite_cell_id,
                stage_id=stage_id,
                work_item_id=str(state_record["work_item_id"]),
                stage_status=str(state_record["status"]),
            )
            artifacts.extend(loaded)
            errors.extend(load_errors)
    elif stage_id == STAGE_VALIDATION:
        packaged = summary.get("packaged_validation_ladder")
        if isinstance(packaged, Mapping):
            metadata_path = _summary_metadata_path(packaged)
            if metadata_path is not None:
                loaded, load_errors = _load_validation_package_artifacts(
                    metadata_path=metadata_path,
                    suite_cell_id=suite_cell_id,
                    stage_id=stage_id,
                    work_item_id=str(state_record["work_item_id"]),
                    stage_status=str(state_record["status"]),
                )
                artifacts.extend(loaded)
                errors.extend(load_errors)
        layer_results = summary.get("layer_results", {})
        if isinstance(layer_results, Mapping):
            for layer_id in sorted(layer_results):
                layer_summary = layer_results[layer_id]
                if not isinstance(layer_summary, Mapping):
                    continue
                metadata_path = _summary_metadata_path(layer_summary)
                if metadata_path is None:
                    continue
                loaded, load_errors = _load_validation_bundle_artifacts(
                    metadata_path=metadata_path,
                    suite_cell_id=suite_cell_id,
                    stage_id=stage_id,
                    work_item_id=str(state_record["work_item_id"]),
                    stage_status=str(state_record["status"]),
                )
                artifacts.extend(loaded)
                errors.extend(load_errors)
    elif stage_id == STAGE_DASHBOARD:
        metadata_path = _summary_metadata_path(summary)
        if metadata_path is not None:
            loaded, load_errors = _load_dashboard_bundle_artifacts(
                metadata_path=metadata_path,
                suite_cell_id=suite_cell_id,
                stage_id=stage_id,
                work_item_id=str(state_record["work_item_id"]),
                stage_status=str(state_record["status"]),
            )
            artifacts.extend(loaded)
            errors.extend(load_errors)

    raw_artifacts = []
    if latest_attempt is not None:
        raw_artifacts = list(latest_attempt.get("downstream_artifacts", []))
    for raw_artifact in raw_artifacts:
        fallback = _fallback_stage_artifact(
            artifact=raw_artifact,
            suite_cell_id=suite_cell_id,
            stage_id=stage_id,
            work_item_id=str(state_record["work_item_id"]),
            stage_status=str(state_record["status"]),
        )
        if fallback is None:
            continue
        artifacts.append(fallback)

    deduped = _dedupe_stage_artifacts(artifacts)
    deduped = _sort_stage_artifacts(
        deduped,
        cell_index_by_id={suite_cell_id: cell_index},
        stage_order=stage_order,
    )
    return deduped, sorted(set(errors))


def _load_simulator_bundle_artifacts(
    *,
    metadata_path: str,
    suite_cell_id: str,
    stage_id: str,
    work_item_id: str,
    stage_status: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        metadata = load_simulator_result_bundle_metadata(metadata_path)
    except Exception as exc:
        return [], [f"simulator bundle load failed for {metadata_path}: {type(exc).__name__}: {exc}"]

    artifacts: list[dict[str, Any]] = []
    bundle_id = str(metadata["bundle_id"])
    contract_version = str(metadata["contract_version"])
    for artifact_id, record in metadata["artifacts"].items():
        if artifact_id == "model_artifacts":
            for model_artifact in record:
                artifacts.append(
                    _contract_stage_artifact(
                        suite_cell_id=suite_cell_id,
                        stage_id=stage_id,
                        work_item_id=work_item_id,
                        stage_status=stage_status,
                        source_kind=SIMULATOR_RESULT_SOURCE_KIND,
                        bundle_kind="simulator_result_bundle",
                        contract_version=contract_version,
                        bundle_id=bundle_id,
                        artifact_id=str(model_artifact["artifact_id"]),
                        path=model_artifact["path"],
                        format=model_artifact["format"],
                        artifact_scope=model_artifact["artifact_scope"],
                        status=model_artifact["status"],
                        description=model_artifact.get("description"),
                    )
                )
            continue
        if not isinstance(record, Mapping):
            continue
        artifacts.append(
            _contract_stage_artifact(
                suite_cell_id=suite_cell_id,
                stage_id=stage_id,
                work_item_id=work_item_id,
                stage_status=stage_status,
                source_kind=SIMULATOR_RESULT_SOURCE_KIND,
                bundle_kind="simulator_result_bundle",
                contract_version=contract_version,
                bundle_id=bundle_id,
                artifact_id=str(artifact_id),
                path=record["path"],
                format=record["format"],
                artifact_scope=record["artifact_scope"],
                status=record["status"],
                description=record.get("description"),
            )
        )
    return artifacts, []


def _load_analysis_bundle_artifacts(
    *,
    metadata_path: str,
    suite_cell_id: str,
    stage_id: str,
    work_item_id: str,
    stage_status: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        metadata = load_experiment_analysis_bundle_metadata(metadata_path)
    except Exception as exc:
        return [], [f"analysis bundle load failed for {metadata_path}: {type(exc).__name__}: {exc}"]
    return _bundle_artifacts_from_metadata(
        metadata=metadata,
        suite_cell_id=suite_cell_id,
        stage_id=stage_id,
        work_item_id=work_item_id,
        stage_status=stage_status,
        source_kind=EXPERIMENT_ANALYSIS_SOURCE_KIND,
        bundle_kind="experiment_analysis_bundle",
    )


def _load_validation_bundle_artifacts(
    *,
    metadata_path: str,
    suite_cell_id: str,
    stage_id: str,
    work_item_id: str,
    stage_status: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        metadata = load_validation_bundle_metadata(metadata_path)
    except Exception as exc:
        return [], [f"validation bundle load failed for {metadata_path}: {type(exc).__name__}: {exc}"]
    return _bundle_artifacts_from_metadata(
        metadata=metadata,
        suite_cell_id=suite_cell_id,
        stage_id=stage_id,
        work_item_id=work_item_id,
        stage_status=stage_status,
        source_kind=VALIDATION_BUNDLE_SOURCE_KIND,
        bundle_kind="validation_bundle",
    )


def _load_validation_package_artifacts(
    *,
    metadata_path: str,
    suite_cell_id: str,
    stage_id: str,
    work_item_id: str,
    stage_status: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        metadata = load_validation_ladder_package_metadata(metadata_path)
    except Exception as exc:
        return [], [f"validation package load failed for {metadata_path}: {type(exc).__name__}: {exc}"]
    return _bundle_artifacts_from_metadata(
        metadata=metadata,
        suite_cell_id=suite_cell_id,
        stage_id=stage_id,
        work_item_id=work_item_id,
        stage_status=stage_status,
        source_kind=VALIDATION_BUNDLE_SOURCE_KIND,
        bundle_kind="validation_ladder_package",
    )


def _load_dashboard_bundle_artifacts(
    *,
    metadata_path: str,
    suite_cell_id: str,
    stage_id: str,
    work_item_id: str,
    stage_status: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        metadata = load_dashboard_session_metadata(metadata_path)
    except Exception as exc:
        return [], [f"dashboard bundle load failed for {metadata_path}: {type(exc).__name__}: {exc}"]
    return _bundle_artifacts_from_metadata(
        metadata=metadata,
        suite_cell_id=suite_cell_id,
        stage_id=stage_id,
        work_item_id=work_item_id,
        stage_status=stage_status,
        source_kind=DASHBOARD_SESSION_SOURCE_KIND,
        bundle_kind="dashboard_session",
    )


def _bundle_artifacts_from_metadata(
    *,
    metadata: Mapping[str, Any],
    suite_cell_id: str,
    stage_id: str,
    work_item_id: str,
    stage_status: str,
    source_kind: str,
    bundle_kind: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    artifacts_payload = metadata.get("artifacts")
    if not isinstance(artifacts_payload, Mapping):
        return [], [f"{bundle_kind} metadata is missing an artifacts mapping."]
    bundle_id = None if metadata.get("bundle_id") is None else str(metadata["bundle_id"])
    contract_version = _normalize_nonempty_string(
        metadata["contract_version"],
        field_name="metadata.contract_version",
    )
    artifacts: list[dict[str, Any]] = []
    for artifact_id, record in artifacts_payload.items():
        if not isinstance(record, Mapping):
            continue
        artifacts.append(
            _contract_stage_artifact(
                suite_cell_id=suite_cell_id,
                stage_id=stage_id,
                work_item_id=work_item_id,
                stage_status=stage_status,
                source_kind=source_kind,
                bundle_kind=bundle_kind,
                contract_version=contract_version,
                bundle_id=bundle_id,
                artifact_id=str(artifact_id),
                path=record["path"],
                format=record["format"],
                artifact_scope=record["artifact_scope"],
                status=record["status"],
                description=record.get("description"),
            )
        )
    return artifacts, []


def _contract_stage_artifact(
    *,
    suite_cell_id: str,
    stage_id: str,
    work_item_id: str,
    stage_status: str,
    source_kind: str,
    bundle_kind: str,
    contract_version: str,
    bundle_id: str | None,
    artifact_id: str,
    path: str | Path,
    format: str,
    artifact_scope: str,
    status: str,
    description: str | None,
) -> dict[str, Any]:
    resolved_path = Path(path).resolve()
    return {
        "suite_cell_id": suite_cell_id,
        "stage_id": stage_id,
        "work_item_id": work_item_id,
        "stage_status": stage_status,
        "artifact_role_id": _STAGE_ROLE_ID[stage_id],
        "source_kind": source_kind,
        "bundle_kind": bundle_kind,
        "contract_version": contract_version,
        "bundle_id": bundle_id,
        "artifact_id": _normalize_identifier(
            artifact_id,
            field_name="artifact_id",
        ),
        "artifact_kind": _normalize_identifier(
            artifact_id,
            field_name="artifact_kind",
        ),
        "path": str(resolved_path),
        "exists": resolved_path.exists(),
        "status": _normalize_asset_status(status, field_name="status"),
        "format": _normalize_nonempty_string(format, field_name="format"),
        "artifact_scope": _normalize_identifier(
            artifact_scope,
            field_name="artifact_scope",
        ),
        "inventory_category": _inventory_category(
            artifact_id=str(artifact_id),
            artifact_kind=str(artifact_id),
            artifact_scope=str(artifact_scope),
            path=resolved_path,
        ),
        "description": (
            None
            if description is None
            else _normalize_nonempty_string(description, field_name="description")
        ),
    }


def _fallback_stage_artifact(
    *,
    artifact: Mapping[str, Any],
    suite_cell_id: str,
    stage_id: str,
    work_item_id: str,
    stage_status: str,
) -> dict[str, Any] | None:
    if not isinstance(artifact, Mapping):
        return None
    path = artifact.get("path")
    if not isinstance(path, str) or not path:
        return None
    resolved_path = Path(path).resolve()
    raw_role_id = artifact.get("artifact_role_id")
    artifact_role_id = (
        _STAGE_ROLE_ID[stage_id]
        if raw_role_id is None
        else _normalize_identifier(raw_role_id, field_name="artifact_role_id")
    )
    artifact_kind = _normalize_identifier(
        artifact.get("artifact_kind", "artifact"),
        field_name="artifact_kind",
    )
    artifact_id = _normalize_identifier(
        artifact.get("artifact_id", artifact_kind),
        field_name="artifact_id",
    )
    status = _normalize_asset_status(
        artifact.get("status", ASSET_STATUS_READY),
        field_name="status",
    )
    artifact_scope = _normalize_optional_identifier(
        artifact.get("artifact_scope"),
        field_name="artifact_scope",
    )
    return {
        "suite_cell_id": suite_cell_id,
        "stage_id": stage_id,
        "work_item_id": work_item_id,
        "stage_status": stage_status,
        "artifact_role_id": artifact_role_id,
        "source_kind": _STAGE_SOURCE_KIND[stage_id],
        "bundle_kind": f"{stage_id}_stage_output",
        "contract_version": _normalize_optional_nonempty_string(
            artifact.get("contract_version"),
            field_name="contract_version",
        ),
        "bundle_id": _normalize_optional_nonempty_string(
            artifact.get("bundle_id"),
            field_name="bundle_id",
        ),
        "artifact_id": artifact_id,
        "artifact_kind": artifact_kind,
        "path": str(resolved_path),
        "exists": resolved_path.exists(),
        "status": status,
        "format": _normalize_optional_nonempty_string(
            artifact.get("format"),
            field_name="format",
        ),
        "artifact_scope": artifact_scope,
        "inventory_category": _inventory_category(
            artifact_id=artifact_id,
            artifact_kind=artifact_kind,
            artifact_scope=artifact_scope,
            path=resolved_path,
        ),
        "description": _normalize_optional_nonempty_string(
            artifact.get("description"),
            field_name="description",
        ),
    }


def _dedupe_stage_artifacts(
    artifacts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str, str, str | None], dict[str, Any]] = {}
    for item in artifacts:
        key = (
            str(item["suite_cell_id"]),
            str(item["stage_id"]),
            str(item["path"]),
            None if item.get("artifact_id") is None else str(item["artifact_id"]),
        )
        existing = deduped.get(key)
        if existing is None or existing.get("contract_version") is None:
            deduped[key] = copy.deepcopy(dict(item))
    return list(deduped.values())


def _sort_stage_artifacts(
    artifacts: Sequence[Mapping[str, Any]],
    *,
    cell_index_by_id: Mapping[str, int],
    stage_order: Sequence[str],
) -> list[dict[str, Any]]:
    stage_index = {stage_id: index for index, stage_id in enumerate(stage_order)}
    return [
        copy.deepcopy(dict(item))
        for item in sorted(
            artifacts,
            key=lambda item: (
                int(cell_index_by_id.get(str(item["suite_cell_id"]), 999999)),
                int(stage_index.get(str(item["stage_id"]), 999999)),
                str(item.get("bundle_kind", "")),
                "" if item.get("bundle_id") is None else str(item["bundle_id"]),
                str(item.get("artifact_id", "")),
                str(item["path"]),
            ),
        )
    ]


def _build_simulation_lineage_cell_records(
    *,
    cell: Mapping[str, Any],
    cell_records_by_id: Mapping[str, Mapping[str, Any]],
    cell_index_by_id: Mapping[str, int],
) -> list[dict[str, Any]]:
    lineage_kind = str(cell["lineage_kind"])
    if lineage_kind in {
        SEED_REPLICATE_LINEAGE_KIND,
        SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
    }:
        return [copy.deepcopy(dict(cell))]
    simulation_lineage_kinds = {
        BASE_CONDITION_LINEAGE_KIND: SEED_REPLICATE_LINEAGE_KIND,
        ABLATION_VARIANT_LINEAGE_KIND: SEEDED_ABLATION_VARIANT_LINEAGE_KIND,
    }
    target_child_kind = simulation_lineage_kinds.get(lineage_kind)
    if target_child_kind is None:
        return []
    discovered = [
        copy.deepcopy(dict(candidate))
        for candidate in cell_records_by_id.values()
        if str(candidate.get("parent_cell_id")) == str(cell["suite_cell_id"])
        and str(candidate["lineage_kind"]) == target_child_kind
    ]
    return sorted(
        discovered,
        key=lambda item: (
            int(cell_index_by_id[str(item["suite_cell_id"])]),
            -1 if item.get("simulation_seed") is None else int(item["simulation_seed"]),
            str(item["suite_cell_id"]),
        ),
    )


def _dimension_value_id_mapping(cell: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(dimension_id): str(value["value_id"])
        for dimension_id, value in dict(cell["selected_dimension_values"]).items()
    }


def _ablation_identity_ids(cell: Mapping[str, Any]) -> list[str]:
    if not cell["ablation_references"]:
        return []
    identities = []
    for item in cell["ablation_references"]:
        identity = (
            f"{item['ablation_family_id']}:{item['variant_id']}"
            if item.get("perturbation_seed") is None
            else f"{item['ablation_family_id']}:{item['variant_id']}:{item['perturbation_seed']}"
        )
        identities.append(identity)
    return identities


def _roll_up_cell_status(stage_records: Sequence[Mapping[str, Any]]) -> str:
    if not stage_records:
        return WORK_ITEM_STATUS_PLANNED
    ordered = sorted(
        (str(item["status"]) for item in stage_records),
        key=lambda value: int(_CELL_STATUS_PRIORITY.get(value, 999)),
    )
    return ordered[0]


def _cell_status_counts(cell_records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in cell_records:
        counts[str(item["overall_status"])] += 1
    return {
        WORK_ITEM_STATUS_PLANNED: counts.get(WORK_ITEM_STATUS_PLANNED, 0),
        WORK_ITEM_STATUS_RUNNING: counts.get(WORK_ITEM_STATUS_RUNNING, 0),
        WORK_ITEM_STATUS_SUCCEEDED: counts.get(WORK_ITEM_STATUS_SUCCEEDED, 0),
        WORK_ITEM_STATUS_PARTIAL: counts.get(WORK_ITEM_STATUS_PARTIAL, 0),
        WORK_ITEM_STATUS_FAILED: counts.get(WORK_ITEM_STATUS_FAILED, 0),
        WORK_ITEM_STATUS_BLOCKED: counts.get(WORK_ITEM_STATUS_BLOCKED, 0),
        WORK_ITEM_STATUS_SKIPPED: counts.get(WORK_ITEM_STATUS_SKIPPED, 0),
    }


def _summary_metadata_path(summary: Mapping[str, Any]) -> str | None:
    metadata_path = summary.get("metadata_path")
    if isinstance(metadata_path, str) and metadata_path:
        return metadata_path
    return None


def _inventory_category(
    *,
    artifact_id: str,
    artifact_kind: str,
    artifact_scope: str | None,
    path: Path,
) -> str:
    token = " ".join(
        [
            artifact_id,
            artifact_kind,
            "" if artifact_scope is None else artifact_scope,
            path.name,
        ]
    ).lower()
    if "metadata" in token:
        return BUNDLE_METADATA_CATEGORY
    if "plot" in token or path.suffix.lower() in {".png", ".svg"}:
        return COMPARISON_PLOT_CATEGORY
    if "report" in token or path.suffix.lower() in {".html", ".md"}:
        return REVIEW_ARTIFACT_CATEGORY
    if "table" in token or "summary" in token or path.suffix.lower() == ".csv":
        return SUMMARY_TABLE_CATEGORY
    if "payload" in token or "session_state" in token:
        return UI_ARTIFACT_CATEGORY
    if "trace" in token or path.suffix.lower() == ".npz":
        return TRACE_ARTIFACT_CATEGORY
    if "log" in token or "provenance" in token or "diagnostic" in token:
        return DIAGNOSTIC_ARTIFACT_CATEGORY
    return BUNDLE_ARTIFACT_CATEGORY


def _package_artifact_record(
    *,
    path: Path,
    artifact_id: str,
) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "status": ASSET_STATUS_READY,
        "format": _ARTIFACT_FORMATS[artifact_id],
        "artifact_scope": _ARTIFACT_SCOPES[artifact_id],
        "description": _ARTIFACT_DESCRIPTIONS[artifact_id],
    }


def _normalize_suite_reference(payload: Any) -> dict[str, Any]:
    normalized = _normalize_json_mapping(payload, field_name="suite_reference")
    required_fields = (
        "suite_id",
        "suite_label",
        "suite_spec_hash",
        "suite_contract_version",
        "suite_root",
        "suite_plan_path",
        "suite_metadata_path",
        "state_path",
    )
    missing = [field for field in required_fields if field not in normalized]
    if missing:
        raise ValueError(f"suite_reference is missing fields {missing!r}.")
    return {
        "suite_id": _normalize_identifier(
            normalized["suite_id"],
            field_name="suite_reference.suite_id",
        ),
        "suite_label": _normalize_nonempty_string(
            normalized["suite_label"],
            field_name="suite_reference.suite_label",
        ),
        "suite_spec_hash": _normalize_nonempty_string(
            normalized["suite_spec_hash"],
            field_name="suite_reference.suite_spec_hash",
        ),
        "suite_contract_version": _normalize_nonempty_string(
            normalized["suite_contract_version"],
            field_name="suite_reference.suite_contract_version",
        ),
        "suite_root": str(Path(normalized["suite_root"]).resolve()),
        "suite_plan_path": str(Path(normalized["suite_plan_path"]).resolve()),
        "suite_metadata_path": str(Path(normalized["suite_metadata_path"]).resolve()),
        "state_path": str(Path(normalized["state_path"]).resolve()),
    }


def _normalize_package_layout(
    payload: Any,
    *,
    expected_paths: ExperimentSuitePackagePaths,
) -> dict[str, Any]:
    normalized = _normalize_json_mapping(payload, field_name="package_layout")
    required_fields = (
        "package_directory",
        "index_directory",
        "export_directory",
        "report_directory",
    )
    missing = [field for field in required_fields if field not in normalized]
    if missing:
        raise ValueError(f"package_layout is missing fields {missing!r}.")
    layout = {
        "package_directory": str(Path(normalized["package_directory"]).resolve()),
        "index_directory": str(Path(normalized["index_directory"]).resolve()),
        "export_directory": str(Path(normalized["export_directory"]).resolve()),
        "report_directory": str(Path(normalized["report_directory"]).resolve()),
    }
    if Path(layout["package_directory"]) != expected_paths.package_directory.resolve():
        raise ValueError("package_layout.package_directory must match the canonical package directory.")
    if Path(layout["index_directory"]) != expected_paths.index_directory.resolve():
        raise ValueError("package_layout.index_directory must match the canonical index directory.")
    if Path(layout["export_directory"]) != expected_paths.export_directory.resolve():
        raise ValueError("package_layout.export_directory must match the canonical export directory.")
    if Path(layout["report_directory"]) != expected_paths.report_directory.resolve():
        raise ValueError("package_layout.report_directory must match the canonical report directory.")
    return layout


def _normalize_package_artifacts(
    payload: Any,
    *,
    expected_paths: Mapping[str, Path],
) -> dict[str, Any]:
    normalized = _normalize_json_mapping(payload, field_name="artifacts")
    if set(normalized) != set(_ARTIFACT_IDS):
        raise ValueError(
            "artifacts must declare the canonical experiment_suite_package artifact ids."
        )
    artifacts: dict[str, Any] = {}
    for artifact_id in _ARTIFACT_IDS:
        record = _normalize_json_mapping(
            normalized[artifact_id],
            field_name=f"artifacts.{artifact_id}",
        )
        required_fields = ("path", "status", "format", "artifact_scope", "description")
        missing = [field for field in required_fields if field not in record]
        if missing:
            raise ValueError(f"artifacts.{artifact_id} is missing fields {missing!r}.")
        path = Path(record["path"]).resolve()
        if path != expected_paths[artifact_id].resolve():
            raise ValueError(f"artifacts.{artifact_id}.path must match the canonical package path.")
        artifacts[artifact_id] = {
            "path": str(path),
            "status": _normalize_asset_status(
                record["status"],
                field_name=f"artifacts.{artifact_id}.status",
            ),
            "format": _normalize_nonempty_string(
                record["format"],
                field_name=f"artifacts.{artifact_id}.format",
            ),
            "artifact_scope": _normalize_identifier(
                record["artifact_scope"],
                field_name=f"artifacts.{artifact_id}.artifact_scope",
            ),
            "description": _normalize_nonempty_string(
                record["description"],
                field_name=f"artifacts.{artifact_id}.description",
            ),
        }
    return artifacts


def _normalize_package_summary(payload: Any) -> dict[str, Any]:
    normalized = _normalize_json_mapping(payload, field_name="summary")
    required_fields = (
        "overall_status",
        "suite_cell_count",
        "work_item_count",
        "stage_artifact_count",
        "cell_status_counts",
        "stage_status_counts",
    )
    missing = [field for field in required_fields if field not in normalized]
    if missing:
        raise ValueError(f"summary is missing fields {missing!r}.")
    return {
        "overall_status": _normalize_nonempty_string(
            normalized["overall_status"],
            field_name="summary.overall_status",
        ),
        "suite_cell_count": int(normalized["suite_cell_count"]),
        "work_item_count": int(normalized["work_item_count"]),
        "stage_artifact_count": int(normalized["stage_artifact_count"]),
        "cell_status_counts": _normalize_json_mapping(
            normalized["cell_status_counts"],
            field_name="summary.cell_status_counts",
        ),
        "stage_status_counts": _normalize_json_mapping(
            normalized["stage_status_counts"],
            field_name="summary.stage_status_counts",
        ),
    }


def _cell_inventory_csv_fieldnames() -> list[str]:
    return [
        "suite_cell_id",
        "display_name",
        "lineage_kind",
        "overall_status",
        "simulation_seed",
        "parent_cell_id",
        "root_cell_id",
        "dimension_signature",
        "ablation_signature",
        "stage_statuses",
        "simulation_lineage_suite_cell_ids",
        "resolved_bundle_ids",
        "report_artifact_paths",
    ]


def _build_cell_inventory_csv_rows(
    result_index: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in result_index["cell_records"]:
        rows.append(
            {
                "suite_cell_id": str(item["suite_cell_id"]),
                "display_name": str(item["display_name"]),
                "lineage_kind": str(item["lineage_kind"]),
                "overall_status": str(item["overall_status"]),
                "simulation_seed": (
                    ""
                    if item.get("simulation_seed") is None
                    else int(item["simulation_seed"])
                ),
                "parent_cell_id": "" if item.get("parent_cell_id") is None else str(item["parent_cell_id"]),
                "root_cell_id": "" if item.get("root_cell_id") is None else str(item["root_cell_id"]),
                "dimension_signature": _dimension_signature(item),
                "ablation_signature": (
                    "base" if not item["ablation_identity_ids"] else ",".join(item["ablation_identity_ids"])
                ),
                "stage_statuses": ";".join(
                    f"{stage_record['stage_id']}={stage_record['status']}"
                    for stage_record in item["stage_records"]
                ),
                "simulation_lineage_suite_cell_ids": ",".join(
                    str(lineage["suite_cell_id"])
                    for lineage in item["simulation_lineage_cells"]
                ),
                "resolved_bundle_ids": ",".join(item["resolved_bundle_ids"]),
                "report_artifact_paths": ",".join(item["report_artifact_paths"]),
            }
        )
    return rows


def _stage_artifact_inventory_csv_fieldnames() -> list[str]:
    return [
        "suite_cell_id",
        "stage_id",
        "work_item_id",
        "stage_status",
        "artifact_role_id",
        "source_kind",
        "bundle_kind",
        "contract_version",
        "bundle_id",
        "artifact_id",
        "artifact_kind",
        "inventory_category",
        "artifact_scope",
        "status",
        "exists",
        "format",
        "path",
    ]


def _build_stage_artifact_inventory_csv_rows(
    result_index: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in result_index["stage_artifacts"]:
        rows.append(
            {
                "suite_cell_id": str(item["suite_cell_id"]),
                "stage_id": str(item["stage_id"]),
                "work_item_id": str(item["work_item_id"]),
                "stage_status": str(item["stage_status"]),
                "artifact_role_id": str(item["artifact_role_id"]),
                "source_kind": str(item["source_kind"]),
                "bundle_kind": str(item["bundle_kind"]),
                "contract_version": "" if item.get("contract_version") is None else str(item["contract_version"]),
                "bundle_id": "" if item.get("bundle_id") is None else str(item["bundle_id"]),
                "artifact_id": str(item["artifact_id"]),
                "artifact_kind": str(item["artifact_kind"]),
                "inventory_category": str(item["inventory_category"]),
                "artifact_scope": "" if item.get("artifact_scope") is None else str(item["artifact_scope"]),
                "status": str(item["status"]),
                "exists": bool(item["exists"]),
                "format": "" if item.get("format") is None else str(item["format"]),
                "path": str(item["path"]),
            }
        )
    return rows


def _dimension_signature(item: Mapping[str, Any]) -> str:
    return ";".join(
        f"{dimension_id}={value_id}"
        for dimension_id, value_id in sorted(
            dict(item["dimension_value_ids"]).items(),
            key=lambda pair: pair[0],
        )
    )


def _render_inventory_report(
    *,
    package_metadata: Mapping[str, Any],
    result_index: Mapping[str, Any],
) -> str:
    lines = [
        "# Experiment Suite Inventory",
        "",
        f"- suite_id: {package_metadata['suite_reference']['suite_id']}",
        f"- suite_label: {package_metadata['suite_reference']['suite_label']}",
        f"- suite_spec_hash: {package_metadata['suite_reference']['suite_spec_hash']}",
        f"- overall_status: {package_metadata['summary']['overall_status']}",
        f"- suite_cell_count: {package_metadata['summary']['suite_cell_count']}",
        f"- work_item_count: {package_metadata['summary']['work_item_count']}",
        f"- stage_artifact_count: {package_metadata['summary']['stage_artifact_count']}",
        "",
        "## Cell Statuses",
        "",
        "| suite_cell_id | lineage_kind | overall_status | ablations | dimensions |",
        "| --- | --- | --- | --- | --- |",
    ]
    for cell in result_index["cell_records"]:
        lines.append(
            "| {suite_cell_id} | {lineage_kind} | {overall_status} | {ablations} | {dimensions} |".format(
                suite_cell_id=cell["suite_cell_id"],
                lineage_kind=cell["lineage_kind"],
                overall_status=cell["overall_status"],
                ablations=(
                    "base"
                    if not cell["ablation_identity_ids"]
                    else ", ".join(cell["ablation_identity_ids"])
                ),
                dimensions=_dimension_signature(cell),
            )
        )
    lines.extend(
        [
            "",
            "## Stage Status Counts",
            "",
        ]
    )
    for stage_id in result_index["stage_order"]:
        counts = result_index["summary"]["stage_status_counts"][stage_id]
        lines.append(
            "- {stage_id}: planned={planned}, running={running}, succeeded={succeeded}, "
            "partial={partial}, failed={failed}, blocked={blocked}, skipped={skipped}".format(
                stage_id=stage_id,
                planned=counts.get(WORK_ITEM_STATUS_PLANNED, 0),
                running=counts.get(WORK_ITEM_STATUS_RUNNING, 0),
                succeeded=counts.get(WORK_ITEM_STATUS_SUCCEEDED, 0),
                partial=counts.get(WORK_ITEM_STATUS_PARTIAL, 0),
                failed=counts.get(WORK_ITEM_STATUS_FAILED, 0),
                blocked=counts.get(WORK_ITEM_STATUS_BLOCKED, 0),
                skipped=counts.get(WORK_ITEM_STATUS_SKIPPED, 0),
            )
        )
    return "\n".join(lines) + "\n"


def _normalize_optional_nonempty_string(
    payload: Any,
    *,
    field_name: str,
) -> str | None:
    if payload is None:
        return None
    return _normalize_nonempty_string(payload, field_name=field_name)


def _normalize_optional_identifier(
    payload: Any,
    *,
    field_name: str,
) -> str | None:
    if payload is None:
        return None
    return _normalize_identifier(payload, field_name=field_name)


def _require_mapping(payload: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return copy.deepcopy(dict(payload))


__all__ = [
    "CELL_INVENTORY_CSV_ARTIFACT_ID",
    "EXPERIMENT_SUITE_PACKAGE_CONTRACT_VERSION",
    "EXPERIMENT_SUITE_RESULT_INDEX_FORMAT",
    "ExperimentSuitePackagePaths",
    "INVENTORY_REPORT_ARTIFACT_ID",
    "METADATA_JSON_KEY",
    "RESULT_INDEX_ARTIFACT_ID",
    "STAGE_ARTIFACT_INVENTORY_CSV_ARTIFACT_ID",
    "build_experiment_suite_package_metadata",
    "build_experiment_suite_package_paths",
    "build_experiment_suite_result_index",
    "discover_experiment_suite_package_cells",
    "discover_experiment_suite_package_paths",
    "discover_experiment_suite_stage_artifacts",
    "load_experiment_suite_package_metadata",
    "load_experiment_suite_result_index",
    "package_experiment_suite_outputs",
    "resolve_experiment_suite_package_metadata_path",
    "write_experiment_suite_package_metadata",
]
