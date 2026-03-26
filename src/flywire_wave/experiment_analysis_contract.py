from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import write_json
from .stimulus_contract import (
    ASSET_STATUS_READY,
    DEFAULT_HASH_ALGORITHM,
    _normalize_asset_status,
    _normalize_identifier,
    _normalize_json_mapping,
    _normalize_nonempty_string,
    _normalize_parameter_hash,
)


EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION = "experiment_analysis_bundle.v1"
EXPERIMENT_ANALYSIS_BUNDLE_DESIGN_NOTE = "docs/experiment_analysis_bundle_design.md"
EXPERIMENT_ANALYSIS_BUNDLE_DESIGN_NOTE_VERSION = (
    "experiment_analysis_bundle_design_note.v1"
)

DEFAULT_ANALYSIS_DIRECTORY_NAME = "analysis"
DEFAULT_REPORT_DIRECTORY_NAME = "report"

METADATA_JSON_KEY = "metadata_json"
EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID = "experiment_comparison_summary"
TASK_SUMMARY_ROWS_ARTIFACT_ID = "task_summary_rows"
NULL_TEST_TABLE_ARTIFACT_ID = "null_test_table"
COMPARISON_MATRICES_ARTIFACT_ID = "comparison_matrices"
VISUALIZATION_CATALOG_ARTIFACT_ID = "visualization_catalog"
ANALYSIS_UI_PAYLOAD_ARTIFACT_ID = "analysis_ui_payload"
OFFLINE_REPORT_INDEX_ARTIFACT_ID = "offline_report_index"
OFFLINE_REPORT_SUMMARY_ARTIFACT_ID = "offline_report_summary"

CONTRACT_METADATA_SCOPE = "contract_metadata"
EXPERIMENT_SUMMARY_SCOPE = "experiment_summary"
UI_HANDOFF_SCOPE = "ui_handoff"
OFFLINE_REVIEW_SCOPE = "offline_review"

SUMMARY_JSON_FORMAT = "json_experiment_comparison_summary.v1"
TASK_SUMMARY_JSON_FORMAT = "json_experiment_task_summary_rows.v1"
NULL_TEST_TABLE_JSON_FORMAT = "json_experiment_null_test_table.v1"
COMPARISON_MATRICES_JSON_FORMAT = "json_experiment_comparison_matrices.v1"
VISUALIZATION_CATALOG_JSON_FORMAT = "json_experiment_visualization_catalog.v1"
ANALYSIS_UI_PAYLOAD_JSON_FORMAT = "json_experiment_analysis_ui_payload.v1"
OFFLINE_REPORT_INDEX_FORMAT = "html_experiment_analysis_report.v1"
OFFLINE_REPORT_SUMMARY_FORMAT = "json_experiment_analysis_report_summary.v1"


@dataclass(frozen=True)
class ExperimentAnalysisBundlePaths:
    processed_simulator_results_dir: Path
    experiment_id: str
    analysis_spec_hash: str
    bundle_directory: Path
    report_directory: Path
    metadata_json_path: Path
    comparison_summary_path: Path
    task_summary_rows_path: Path
    null_test_table_path: Path
    comparison_matrices_path: Path
    visualization_catalog_path: Path
    analysis_ui_payload_path: Path
    report_index_path: Path
    report_summary_path: Path

    @property
    def bundle_id(self) -> str:
        return (
            f"{EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION}:"
            f"{self.experiment_id}:{self.analysis_spec_hash}"
        )

    def asset_paths(self) -> dict[str, Path]:
        return {
            METADATA_JSON_KEY: self.metadata_json_path,
            EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID: self.comparison_summary_path,
            TASK_SUMMARY_ROWS_ARTIFACT_ID: self.task_summary_rows_path,
            NULL_TEST_TABLE_ARTIFACT_ID: self.null_test_table_path,
            COMPARISON_MATRICES_ARTIFACT_ID: self.comparison_matrices_path,
            VISUALIZATION_CATALOG_ARTIFACT_ID: self.visualization_catalog_path,
            ANALYSIS_UI_PAYLOAD_ARTIFACT_ID: self.analysis_ui_payload_path,
            OFFLINE_REPORT_INDEX_ARTIFACT_ID: self.report_index_path,
            OFFLINE_REPORT_SUMMARY_ARTIFACT_ID: self.report_summary_path,
        }


def build_experiment_analysis_bundle_paths(
    *,
    experiment_id: str,
    analysis_spec_hash: str,
    processed_simulator_results_dir: str | Path,
) -> ExperimentAnalysisBundlePaths:
    normalized_experiment_id = _normalize_identifier(
        experiment_id,
        field_name="experiment_id",
    )
    normalized_analysis_spec_hash = _normalize_parameter_hash(analysis_spec_hash)
    processed_dir = Path(processed_simulator_results_dir).resolve()
    bundle_directory = (
        processed_dir
        / DEFAULT_ANALYSIS_DIRECTORY_NAME
        / normalized_experiment_id
        / normalized_analysis_spec_hash
    ).resolve()
    report_directory = (bundle_directory / DEFAULT_REPORT_DIRECTORY_NAME).resolve()
    return ExperimentAnalysisBundlePaths(
        processed_simulator_results_dir=processed_dir,
        experiment_id=normalized_experiment_id,
        analysis_spec_hash=normalized_analysis_spec_hash,
        bundle_directory=bundle_directory,
        report_directory=report_directory,
        metadata_json_path=bundle_directory / "experiment_analysis_bundle.json",
        comparison_summary_path=bundle_directory / "experiment_comparison_summary.json",
        task_summary_rows_path=bundle_directory / "task_summary_rows.json",
        null_test_table_path=bundle_directory / "null_test_table.json",
        comparison_matrices_path=bundle_directory / "comparison_matrices.json",
        visualization_catalog_path=bundle_directory / "visualization_catalog.json",
        analysis_ui_payload_path=bundle_directory / "analysis_ui_payload.json",
        report_index_path=report_directory / "index.html",
        report_summary_path=report_directory / "summary.json",
    )


def build_experiment_analysis_spec_hash(
    analysis_plan: Mapping[str, Any],
) -> str:
    identity_payload = _normalize_analysis_plan_identity_payload(analysis_plan)
    serialized = json.dumps(
        identity_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_experiment_analysis_bundle_metadata(
    *,
    analysis_plan: Mapping[str, Any],
    bundle_set: Mapping[str, Any],
) -> dict[str, Any]:
    manifest_reference = _normalize_manifest_reference(
        analysis_plan.get("manifest_reference"),
        field_name="analysis_plan.manifest_reference",
    )
    processed_simulator_results_dir = _normalize_nonempty_string(
        bundle_set.get("processed_simulator_results_dir"),
        field_name="bundle_set.processed_simulator_results_dir",
    )
    analysis_spec_hash = build_experiment_analysis_spec_hash(analysis_plan)
    paths = build_experiment_analysis_bundle_paths(
        experiment_id=manifest_reference["experiment_id"],
        analysis_spec_hash=analysis_spec_hash,
        processed_simulator_results_dir=processed_simulator_results_dir,
    )
    return {
        "contract_version": EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION,
        "design_note": EXPERIMENT_ANALYSIS_BUNDLE_DESIGN_NOTE,
        "design_note_version": EXPERIMENT_ANALYSIS_BUNDLE_DESIGN_NOTE_VERSION,
        "bundle_id": paths.bundle_id,
        "experiment_id": manifest_reference["experiment_id"],
        "analysis_spec_hash": analysis_spec_hash,
        "analysis_spec_hash_algorithm": DEFAULT_HASH_ALGORITHM,
        "manifest_reference": manifest_reference,
        "analysis_plan_reference": _build_analysis_plan_reference(analysis_plan),
        "bundle_set_reference": _build_bundle_set_reference(bundle_set),
        "bundle_layout": {
            "bundle_directory": str(paths.bundle_directory),
            "report_directory": str(paths.report_directory),
        },
        "artifacts": {
            METADATA_JSON_KEY: _artifact_record(
                path=paths.metadata_json_path,
                format="json_experiment_analysis_bundle_metadata.v1",
                artifact_scope=CONTRACT_METADATA_SCOPE,
                description="Authoritative experiment-level Milestone 12 analysis bundle metadata.",
            ),
            EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID: _artifact_record(
                path=paths.comparison_summary_path,
                format=SUMMARY_JSON_FORMAT,
                artifact_scope=EXPERIMENT_SUMMARY_SCOPE,
                description="Full experiment comparison summary packaged from local simulator bundles.",
            ),
            TASK_SUMMARY_ROWS_ARTIFACT_ID: _artifact_record(
                path=paths.task_summary_rows_path,
                format=TASK_SUMMARY_JSON_FORMAT,
                artifact_scope=EXPERIMENT_SUMMARY_SCOPE,
                description="Stable task-summary export for requested metrics and score families.",
            ),
            NULL_TEST_TABLE_ARTIFACT_ID: _artifact_record(
                path=paths.null_test_table_path,
                format=NULL_TEST_TABLE_JSON_FORMAT,
                artifact_scope=EXPERIMENT_SUMMARY_SCOPE,
                description="Stable null-test table export flattened for later review and UI handoff.",
            ),
            COMPARISON_MATRICES_ARTIFACT_ID: _artifact_record(
                path=paths.comparison_matrices_path,
                format=COMPARISON_MATRICES_JSON_FORMAT,
                artifact_scope=EXPERIMENT_SUMMARY_SCOPE,
                description="Heatmap-like matrix export for shared/task comparison rollups and wave diagnostics.",
            ),
            VISUALIZATION_CATALOG_ARTIFACT_ID: _artifact_record(
                path=paths.visualization_catalog_path,
                format=VISUALIZATION_CATALOG_JSON_FORMAT,
                artifact_scope=UI_HANDOFF_SCOPE,
                description="Catalog of packaged visualization references, including offline report and phase maps.",
            ),
            ANALYSIS_UI_PAYLOAD_ARTIFACT_ID: _artifact_record(
                path=paths.analysis_ui_payload_path,
                format=ANALYSIS_UI_PAYLOAD_JSON_FORMAT,
                artifact_scope=UI_HANDOFF_SCOPE,
                description="UI-facing experiment analysis payload with task cards, comparison cards, and visualization references.",
            ),
            OFFLINE_REPORT_INDEX_ARTIFACT_ID: _artifact_record(
                path=paths.report_index_path,
                format=OFFLINE_REPORT_INDEX_FORMAT,
                artifact_scope=OFFLINE_REVIEW_SCOPE,
                description="Static offline HTML report for packaged Milestone 12 outputs.",
            ),
            OFFLINE_REPORT_SUMMARY_ARTIFACT_ID: _artifact_record(
                path=paths.report_summary_path,
                format=OFFLINE_REPORT_SUMMARY_FORMAT,
                artifact_scope=OFFLINE_REVIEW_SCOPE,
                description="Machine-readable summary for the packaged offline Milestone 12 report.",
            ),
        },
    }


def build_experiment_analysis_bundle_reference(
    bundle_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = parse_experiment_analysis_bundle_metadata(bundle_metadata)
    return {
        "contract_version": normalized["contract_version"],
        "bundle_id": normalized["bundle_id"],
        "experiment_id": normalized["experiment_id"],
        "analysis_spec_hash": normalized["analysis_spec_hash"],
    }


def parse_experiment_analysis_bundle_metadata(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("experiment_analysis_bundle metadata must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "design_note",
        "design_note_version",
        "bundle_id",
        "experiment_id",
        "analysis_spec_hash",
        "analysis_spec_hash_algorithm",
        "manifest_reference",
        "analysis_plan_reference",
        "bundle_set_reference",
        "bundle_layout",
        "artifacts",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "experiment_analysis_bundle metadata is missing required fields "
            f"{missing_fields!r}."
        )
    contract_version = _normalize_nonempty_string(
        normalized["contract_version"],
        field_name="contract_version",
    )
    if contract_version != EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION:
        raise ValueError(
            "experiment_analysis_bundle contract_version must be "
            f"{EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION!r}."
        )
    design_note = _normalize_nonempty_string(
        normalized["design_note"],
        field_name="design_note",
    )
    if design_note != EXPERIMENT_ANALYSIS_BUNDLE_DESIGN_NOTE:
        raise ValueError(
            f"design_note must be {EXPERIMENT_ANALYSIS_BUNDLE_DESIGN_NOTE!r}."
        )
    design_note_version = _normalize_nonempty_string(
        normalized["design_note_version"],
        field_name="design_note_version",
    )
    if design_note_version != EXPERIMENT_ANALYSIS_BUNDLE_DESIGN_NOTE_VERSION:
        raise ValueError(
            "design_note_version must be "
            f"{EXPERIMENT_ANALYSIS_BUNDLE_DESIGN_NOTE_VERSION!r}."
        )
    experiment_id = _normalize_identifier(
        normalized["experiment_id"],
        field_name="experiment_id",
    )
    analysis_spec_hash = _normalize_parameter_hash(normalized["analysis_spec_hash"])
    bundle_id = _normalize_nonempty_string(
        normalized["bundle_id"],
        field_name="bundle_id",
    )
    expected_bundle_id = (
        f"{EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION}:{experiment_id}:{analysis_spec_hash}"
    )
    if bundle_id != expected_bundle_id:
        raise ValueError(
            "bundle_id must match the canonical experiment-analysis bundle identity."
        )
    hash_algorithm = _normalize_nonempty_string(
        normalized["analysis_spec_hash_algorithm"],
        field_name="analysis_spec_hash_algorithm",
    )
    if hash_algorithm != DEFAULT_HASH_ALGORITHM:
        raise ValueError(
            f"analysis_spec_hash_algorithm must be {DEFAULT_HASH_ALGORITHM!r}."
        )
    manifest_reference = _normalize_manifest_reference(
        normalized["manifest_reference"],
        field_name="manifest_reference",
    )
    if manifest_reference["experiment_id"] != experiment_id:
        raise ValueError(
            "manifest_reference.experiment_id must match experiment_id."
        )
    analysis_plan_reference = _normalize_analysis_plan_reference(
        normalized["analysis_plan_reference"]
    )
    bundle_set_reference = _normalize_bundle_set_reference(
        normalized["bundle_set_reference"]
    )
    if bundle_set_reference["experiment_id"] != experiment_id:
        raise ValueError(
            "bundle_set_reference.experiment_id must match experiment_id."
        )
    bundle_layout = _normalize_bundle_layout(
        normalized["bundle_layout"],
        experiment_id=experiment_id,
        analysis_spec_hash=analysis_spec_hash,
    )
    artifact_paths = build_experiment_analysis_bundle_paths(
        experiment_id=experiment_id,
        analysis_spec_hash=analysis_spec_hash,
        processed_simulator_results_dir=bundle_set_reference[
            "processed_simulator_results_dir"
        ],
    ).asset_paths()
    artifacts = _normalize_artifacts(
        normalized["artifacts"],
        artifact_paths=artifact_paths,
    )
    return {
        "contract_version": contract_version,
        "design_note": design_note,
        "design_note_version": design_note_version,
        "bundle_id": bundle_id,
        "experiment_id": experiment_id,
        "analysis_spec_hash": analysis_spec_hash,
        "analysis_spec_hash_algorithm": hash_algorithm,
        "manifest_reference": manifest_reference,
        "analysis_plan_reference": analysis_plan_reference,
        "bundle_set_reference": bundle_set_reference,
        "bundle_layout": bundle_layout,
        "artifacts": artifacts,
    }


def write_experiment_analysis_bundle_metadata(
    bundle_metadata: Mapping[str, Any],
    output_path: str | Path | None = None,
) -> Path:
    normalized = parse_experiment_analysis_bundle_metadata(bundle_metadata)
    target_path = (
        Path(output_path).resolve()
        if output_path is not None
        else Path(normalized["artifacts"][METADATA_JSON_KEY]["path"]).resolve()
    )
    return write_json(normalized, target_path)


def load_experiment_analysis_bundle_metadata(
    metadata_path: str | Path,
) -> dict[str, Any]:
    with Path(metadata_path).resolve().open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError("experiment_analysis_bundle metadata JSON must be a mapping.")
    return parse_experiment_analysis_bundle_metadata(payload)


def discover_experiment_analysis_bundle_paths(
    record: Mapping[str, Any],
) -> dict[str, Path]:
    normalized = parse_experiment_analysis_bundle_metadata(
        record.get("experiment_analysis_bundle")
        if isinstance(record.get("experiment_analysis_bundle"), Mapping)
        else record
    )
    return {
        artifact_id: Path(str(artifact["path"])).resolve()
        for artifact_id, artifact in normalized["artifacts"].items()
    }


def _artifact_record(
    *,
    path: Path,
    format: str,
    artifact_scope: str,
    description: str,
) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "status": ASSET_STATUS_READY,
        "format": format,
        "artifact_scope": artifact_scope,
        "description": description,
    }


def _normalize_manifest_reference(
    payload: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    normalized = _normalize_json_mapping(payload, field_name=field_name)
    if "experiment_id" not in normalized:
        raise ValueError(f"{field_name} must declare experiment_id.")
    normalized["experiment_id"] = _normalize_identifier(
        normalized["experiment_id"],
        field_name=f"{field_name}.experiment_id",
    )
    return normalized


def _build_analysis_plan_reference(
    analysis_plan: Mapping[str, Any],
) -> dict[str, Any]:
    required_fields = (
        "plan_version",
        "contract_reference",
        "active_metric_ids",
        "active_output_ids",
        "active_null_test_ids",
        "active_shared_readouts",
        "manifest_metric_requests",
    )
    missing_fields = [field for field in required_fields if field not in analysis_plan]
    if missing_fields:
        raise ValueError(
            f"analysis_plan is missing required fields {missing_fields!r}."
        )
    return {
        "plan_version": _normalize_nonempty_string(
            analysis_plan["plan_version"],
            field_name="analysis_plan.plan_version",
        ),
        "contract_reference": _normalize_json_mapping(
            analysis_plan["contract_reference"],
            field_name="analysis_plan.contract_reference",
        ),
        "active_metric_ids": [
            _normalize_identifier(
                item,
                field_name="analysis_plan.active_metric_ids",
            )
            for item in analysis_plan["active_metric_ids"]
        ],
        "active_output_ids": [
            _normalize_identifier(
                item,
                field_name="analysis_plan.active_output_ids",
            )
            for item in analysis_plan["active_output_ids"]
        ],
        "active_null_test_ids": [
            _normalize_identifier(
                item,
                field_name="analysis_plan.active_null_test_ids",
            )
            for item in analysis_plan["active_null_test_ids"]
        ],
        "active_shared_readouts": _normalize_json_mapping(
            {"items": analysis_plan["active_shared_readouts"]},
            field_name="analysis_plan.active_shared_readouts",
        )["items"],
        "manifest_metric_requests": _normalize_json_mapping(
            {"items": analysis_plan["manifest_metric_requests"]},
            field_name="analysis_plan.manifest_metric_requests",
        )["items"],
    }


def _normalize_analysis_plan_reference(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("analysis_plan_reference must be a mapping.")
    return _build_analysis_plan_reference(payload)


def _build_bundle_set_reference(bundle_set: Mapping[str, Any]) -> dict[str, Any]:
    required_fields = (
        "bundle_set_version",
        "experiment_id",
        "processed_simulator_results_dir",
        "expected_arm_ids",
        "expected_seeds_by_arm_id",
        "expected_condition_signatures",
        "bundle_inventory",
    )
    missing_fields = [field for field in required_fields if field not in bundle_set]
    if missing_fields:
        raise ValueError(
            f"bundle_set is missing required fields {missing_fields!r}."
        )
    return {
        "bundle_set_version": _normalize_nonempty_string(
            bundle_set["bundle_set_version"],
            field_name="bundle_set.bundle_set_version",
        ),
        "experiment_id": _normalize_identifier(
            bundle_set["experiment_id"],
            field_name="bundle_set.experiment_id",
        ),
        "processed_simulator_results_dir": str(
            Path(
                _normalize_nonempty_string(
                    bundle_set["processed_simulator_results_dir"],
                    field_name="bundle_set.processed_simulator_results_dir",
                )
            ).resolve()
        ),
        "expected_arm_ids": [
            _normalize_identifier(item, field_name="bundle_set.expected_arm_ids")
            for item in bundle_set["expected_arm_ids"]
        ],
        "expected_seeds_by_arm_id": _normalize_json_mapping(
            bundle_set["expected_seeds_by_arm_id"],
            field_name="bundle_set.expected_seeds_by_arm_id",
        ),
        "expected_condition_signatures": _normalize_json_mapping(
            {"items": bundle_set["expected_condition_signatures"]},
            field_name="bundle_set.expected_condition_signatures",
        )["items"],
        "bundle_inventory": _normalize_json_mapping(
            {"items": bundle_set["bundle_inventory"]},
            field_name="bundle_set.bundle_inventory",
        )["items"],
    }


def _normalize_bundle_set_reference(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("bundle_set_reference must be a mapping.")
    return _build_bundle_set_reference(payload)


def _normalize_analysis_plan_identity_payload(
    analysis_plan: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(analysis_plan, Mapping):
        raise ValueError("analysis_plan must be a mapping.")
    required_fields = (
        "plan_version",
        "manifest_reference",
        "contract_reference",
        "analysis_config",
        "active_shared_readouts",
        "condition_catalog",
        "condition_pair_catalog",
        "analysis_window_catalog",
        "arm_pair_catalog",
        "comparison_group_catalog",
        "seed_aggregation_rules",
        "active_metric_ids",
        "active_output_ids",
        "active_null_test_ids",
        "manifest_metric_requests",
        "metric_recipe_catalog",
    )
    missing_fields = [field for field in required_fields if field not in analysis_plan]
    if missing_fields:
        raise ValueError(
            f"analysis_plan is missing required fields {missing_fields!r}."
        )
    identity = {
        "plan_version": analysis_plan["plan_version"],
        "manifest_reference": analysis_plan["manifest_reference"],
        "contract_reference": analysis_plan["contract_reference"],
        "analysis_config": copy.deepcopy(dict(analysis_plan["analysis_config"])),
        "active_shared_readouts": analysis_plan["active_shared_readouts"],
        "condition_catalog": analysis_plan["condition_catalog"],
        "condition_pair_catalog": analysis_plan["condition_pair_catalog"],
        "analysis_window_catalog": analysis_plan["analysis_window_catalog"],
        "arm_pair_catalog": analysis_plan["arm_pair_catalog"],
        "comparison_group_catalog": analysis_plan["comparison_group_catalog"],
        "seed_aggregation_rules": analysis_plan["seed_aggregation_rules"],
        "active_metric_ids": analysis_plan["active_metric_ids"],
        "active_output_ids": analysis_plan["active_output_ids"],
        "active_null_test_ids": analysis_plan["active_null_test_ids"],
        "manifest_metric_requests": analysis_plan["manifest_metric_requests"],
        "metric_recipe_catalog": analysis_plan["metric_recipe_catalog"],
    }
    analysis_config = copy.deepcopy(dict(identity["analysis_config"]))
    analysis_config.pop("experiment_output_targets", None)
    identity["analysis_config"] = analysis_config
    return _normalize_json_mapping(identity, field_name="analysis_plan_identity")


def _normalize_bundle_layout(
    payload: Any,
    *,
    experiment_id: str,
    analysis_spec_hash: str,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("bundle_layout must be a mapping.")
    bundle_directory = Path(
        _normalize_nonempty_string(
            payload.get("bundle_directory"),
            field_name="bundle_layout.bundle_directory",
        )
    ).resolve()
    report_directory = Path(
        _normalize_nonempty_string(
            payload.get("report_directory"),
            field_name="bundle_layout.report_directory",
        )
    ).resolve()
    if bundle_directory.name != analysis_spec_hash:
        raise ValueError(
            "bundle_layout.bundle_directory must end with analysis_spec_hash."
        )
    if bundle_directory.parent.name != experiment_id:
        raise ValueError(
            "bundle_layout.bundle_directory must encode the canonical experiment_id parent."
        )
    if bundle_directory.parent.parent.name != DEFAULT_ANALYSIS_DIRECTORY_NAME:
        raise ValueError(
            "bundle_layout.bundle_directory must live under the contract-owned analysis directory."
        )
    expected_report_directory = (bundle_directory / DEFAULT_REPORT_DIRECTORY_NAME).resolve()
    if report_directory != expected_report_directory:
        raise ValueError(
            "bundle_layout.report_directory must match the canonical report directory."
        )
    return {
        "bundle_directory": str(bundle_directory),
        "report_directory": str(report_directory),
    }


def _normalize_artifacts(
    payload: Any,
    *,
    artifact_paths: Mapping[str, Path],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("artifacts must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_artifact_ids = tuple(artifact_paths.keys())
    missing_fields = [
        artifact_id for artifact_id in required_artifact_ids if artifact_id not in normalized
    ]
    if missing_fields:
        raise ValueError(f"artifacts is missing required entries {missing_fields!r}.")
    expected_specs = {
        METADATA_JSON_KEY: (
            "json_experiment_analysis_bundle_metadata.v1",
            CONTRACT_METADATA_SCOPE,
        ),
        EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID: (
            SUMMARY_JSON_FORMAT,
            EXPERIMENT_SUMMARY_SCOPE,
        ),
        TASK_SUMMARY_ROWS_ARTIFACT_ID: (
            TASK_SUMMARY_JSON_FORMAT,
            EXPERIMENT_SUMMARY_SCOPE,
        ),
        NULL_TEST_TABLE_ARTIFACT_ID: (
            NULL_TEST_TABLE_JSON_FORMAT,
            EXPERIMENT_SUMMARY_SCOPE,
        ),
        COMPARISON_MATRICES_ARTIFACT_ID: (
            COMPARISON_MATRICES_JSON_FORMAT,
            EXPERIMENT_SUMMARY_SCOPE,
        ),
        VISUALIZATION_CATALOG_ARTIFACT_ID: (
            VISUALIZATION_CATALOG_JSON_FORMAT,
            UI_HANDOFF_SCOPE,
        ),
        ANALYSIS_UI_PAYLOAD_ARTIFACT_ID: (
            ANALYSIS_UI_PAYLOAD_JSON_FORMAT,
            UI_HANDOFF_SCOPE,
        ),
        OFFLINE_REPORT_INDEX_ARTIFACT_ID: (
            OFFLINE_REPORT_INDEX_FORMAT,
            OFFLINE_REVIEW_SCOPE,
        ),
        OFFLINE_REPORT_SUMMARY_ARTIFACT_ID: (
            OFFLINE_REPORT_SUMMARY_FORMAT,
            OFFLINE_REVIEW_SCOPE,
        ),
    }
    return {
        artifact_id: _normalize_artifact_record(
            normalized[artifact_id],
            field_name=f"artifacts.{artifact_id}",
            expected_path=artifact_paths[artifact_id],
            expected_format=expected_specs[artifact_id][0],
            expected_scope=expected_specs[artifact_id][1],
        )
        for artifact_id in required_artifact_ids
    }


def _normalize_artifact_record(
    payload: Any,
    *,
    field_name: str,
    expected_path: Path,
    expected_format: str,
    expected_scope: str,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    path = Path(
        _normalize_nonempty_string(
            payload.get("path"),
            field_name=f"{field_name}.path",
        )
    ).resolve()
    if path != expected_path.resolve():
        raise ValueError(f"{field_name}.path must match the canonical bundle layout.")
    status = _normalize_asset_status(
        payload.get("status"),
        field_name=f"{field_name}.status",
    )
    if status != ASSET_STATUS_READY:
        raise ValueError(f"{field_name}.status must be {ASSET_STATUS_READY!r}.")
    format_name = _normalize_nonempty_string(
        payload.get("format"),
        field_name=f"{field_name}.format",
    )
    if format_name != expected_format:
        raise ValueError(f"{field_name}.format must be {expected_format!r}.")
    artifact_scope = _normalize_nonempty_string(
        payload.get("artifact_scope"),
        field_name=f"{field_name}.artifact_scope",
    )
    if artifact_scope != expected_scope:
        raise ValueError(f"{field_name}.artifact_scope must be {expected_scope!r}.")
    description = _normalize_nonempty_string(
        payload.get("description"),
        field_name=f"{field_name}.description",
    )
    return {
        "path": str(path),
        "status": status,
        "format": format_name,
        "artifact_scope": artifact_scope,
        "description": description,
    }


__all__ = [
    "ANALYSIS_UI_PAYLOAD_ARTIFACT_ID",
    "COMPARISON_MATRICES_ARTIFACT_ID",
    "DEFAULT_ANALYSIS_DIRECTORY_NAME",
    "EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION",
    "EXPERIMENT_ANALYSIS_BUNDLE_DESIGN_NOTE",
    "EXPERIMENT_ANALYSIS_BUNDLE_DESIGN_NOTE_VERSION",
    "EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID",
    "METADATA_JSON_KEY",
    "NULL_TEST_TABLE_ARTIFACT_ID",
    "OFFLINE_REPORT_INDEX_ARTIFACT_ID",
    "OFFLINE_REPORT_SUMMARY_ARTIFACT_ID",
    "TASK_SUMMARY_ROWS_ARTIFACT_ID",
    "VISUALIZATION_CATALOG_ARTIFACT_ID",
    "ExperimentAnalysisBundlePaths",
    "build_experiment_analysis_bundle_metadata",
    "build_experiment_analysis_bundle_paths",
    "build_experiment_analysis_bundle_reference",
    "build_experiment_analysis_spec_hash",
    "discover_experiment_analysis_bundle_paths",
    "load_experiment_analysis_bundle_metadata",
    "parse_experiment_analysis_bundle_metadata",
    "write_experiment_analysis_bundle_metadata",
]
