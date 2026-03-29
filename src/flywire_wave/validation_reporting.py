from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import ensure_dir, write_csv_rows, write_json, write_jsonl
from .stimulus_contract import (
    DEFAULT_HASH_ALGORITHM,
    _normalize_identifier,
    _normalize_nonempty_string,
    _normalize_parameter_hash,
    _normalize_positive_int,
)
from .validation_contract import (
    METADATA_JSON_KEY as VALIDATION_METADATA_JSON_KEY,
    OFFLINE_REVIEW_REPORT_ARTIFACT_ID,
    REVIEW_HANDOFF_ARTIFACT_ID,
    SUPPORTED_VALIDATION_LAYER_IDS,
    VALIDATION_STATUS_BLOCKED,
    VALIDATION_STATUS_BLOCKING,
    VALIDATION_STATUS_PASS,
    VALIDATION_STATUS_REVIEW,
    VALIDATION_SUMMARY_ARTIFACT_ID,
    VALIDATOR_FINDINGS_ARTIFACT_ID,
    build_validation_ladder_contract_metadata,
    discover_validation_bundle_paths,
    discover_validation_layers,
    load_validation_bundle_metadata,
)


VALIDATION_LADDER_PACKAGE_CONTRACT_VERSION = "validation_ladder_package.v1"
VALIDATION_LADDER_PACKAGE_DESIGN_NOTE = "docs/validation_ladder_design.md"
VALIDATION_LADDER_PACKAGE_DESIGN_NOTE_VERSION = (
    "validation_ladder_package_design_note.v1"
)

DEFAULT_VALIDATION_LADDER_PACKAGE_DIRECTORY_NAME = "validation_ladder"
DEFAULT_REPORT_DIRECTORY_NAME = "report"
DEFAULT_EXPORT_DIRECTORY_NAME = "exports"
DEFAULT_REGRESSION_DIRECTORY_NAME = "regression"

METADATA_JSON_KEY = "metadata_json"
VALIDATION_LADDER_SUMMARY_ARTIFACT_ID = "validation_ladder_summary"
FINDING_ROWS_JSONL_ARTIFACT_ID = "finding_rows_jsonl"
FINDING_ROWS_CSV_ARTIFACT_ID = "finding_rows_csv"
REGRESSION_BASELINE_ARTIFACT_ID = "regression_baseline"
REGRESSION_SUMMARY_ARTIFACT_ID = "regression_summary"
OFFLINE_REVIEW_REPORT_ARTIFACT_ID = "offline_review_report"

VALIDATION_LADDER_SUMMARY_FORMAT = "json_validation_ladder_summary.v1"
FINDING_ROWS_JSONL_FORMAT = "jsonl_validation_ladder_finding_rows.v1"
FINDING_ROWS_CSV_FORMAT = "csv_validation_ladder_finding_rows.v1"
REGRESSION_BASELINE_FORMAT = "json_validation_ladder_regression_baseline.v1"
REGRESSION_SUMMARY_FORMAT = "json_validation_ladder_regression_summary.v1"
OFFLINE_REVIEW_REPORT_FORMAT = "md_validation_ladder_report.v1"

REGRESSION_STATUS_NOT_REQUESTED = "not_requested"

_STATUS_RANK = {
    VALIDATION_STATUS_PASS: 0,
    VALIDATION_STATUS_REVIEW: 1,
    VALIDATION_STATUS_BLOCKED: 2,
    VALIDATION_STATUS_BLOCKING: 3,
}
_TOP_LEVEL_ARTIFACT_FORMATS = {
    METADATA_JSON_KEY: "json_validation_ladder_package_metadata.v1",
    VALIDATION_LADDER_SUMMARY_ARTIFACT_ID: VALIDATION_LADDER_SUMMARY_FORMAT,
    FINDING_ROWS_JSONL_ARTIFACT_ID: FINDING_ROWS_JSONL_FORMAT,
    FINDING_ROWS_CSV_ARTIFACT_ID: FINDING_ROWS_CSV_FORMAT,
    REGRESSION_BASELINE_ARTIFACT_ID: REGRESSION_BASELINE_FORMAT,
    REGRESSION_SUMMARY_ARTIFACT_ID: REGRESSION_SUMMARY_FORMAT,
    OFFLINE_REVIEW_REPORT_ARTIFACT_ID: OFFLINE_REVIEW_REPORT_FORMAT,
}


@dataclass(frozen=True)
class ValidationLadderPackagePaths:
    processed_simulator_results_dir: Path
    experiment_id: str
    ladder_spec_hash: str
    bundle_directory: Path
    report_directory: Path
    export_directory: Path
    regression_directory: Path
    metadata_json_path: Path
    summary_json_path: Path
    finding_rows_jsonl_path: Path
    finding_rows_csv_path: Path
    regression_baseline_path: Path
    regression_summary_path: Path
    report_markdown_path: Path

    @property
    def bundle_id(self) -> str:
        return (
            f"{VALIDATION_LADDER_PACKAGE_CONTRACT_VERSION}:"
            f"{self.experiment_id}:{self.ladder_spec_hash}"
        )

    def asset_paths(self) -> dict[str, Path]:
        return {
            METADATA_JSON_KEY: self.metadata_json_path,
            VALIDATION_LADDER_SUMMARY_ARTIFACT_ID: self.summary_json_path,
            FINDING_ROWS_JSONL_ARTIFACT_ID: self.finding_rows_jsonl_path,
            FINDING_ROWS_CSV_ARTIFACT_ID: self.finding_rows_csv_path,
            REGRESSION_BASELINE_ARTIFACT_ID: self.regression_baseline_path,
            REGRESSION_SUMMARY_ARTIFACT_ID: self.regression_summary_path,
            OFFLINE_REVIEW_REPORT_ARTIFACT_ID: self.report_markdown_path,
        }


def build_validation_ladder_package_paths(
    *,
    experiment_id: str,
    ladder_spec_hash: str,
    processed_simulator_results_dir: str | Path,
) -> ValidationLadderPackagePaths:
    normalized_experiment_id = _normalize_identifier(
        experiment_id,
        field_name="experiment_id",
    )
    normalized_ladder_spec_hash = _normalize_parameter_hash(ladder_spec_hash)
    processed_dir = Path(processed_simulator_results_dir).resolve()
    bundle_directory = (
        processed_dir
        / DEFAULT_VALIDATION_LADDER_PACKAGE_DIRECTORY_NAME
        / normalized_experiment_id
        / normalized_ladder_spec_hash
    ).resolve()
    report_directory = (bundle_directory / DEFAULT_REPORT_DIRECTORY_NAME).resolve()
    export_directory = (bundle_directory / DEFAULT_EXPORT_DIRECTORY_NAME).resolve()
    regression_directory = (
        bundle_directory / DEFAULT_REGRESSION_DIRECTORY_NAME
    ).resolve()
    return ValidationLadderPackagePaths(
        processed_simulator_results_dir=processed_dir,
        experiment_id=normalized_experiment_id,
        ladder_spec_hash=normalized_ladder_spec_hash,
        bundle_directory=bundle_directory,
        report_directory=report_directory,
        export_directory=export_directory,
        regression_directory=regression_directory,
        metadata_json_path=bundle_directory / "validation_ladder_package.json",
        summary_json_path=bundle_directory / "validation_ladder_summary.json",
        finding_rows_jsonl_path=export_directory / "finding_rows.jsonl",
        finding_rows_csv_path=export_directory / "finding_rows.csv",
        regression_baseline_path=regression_directory / "baseline_reference.json",
        regression_summary_path=regression_directory / "regression_summary.json",
        report_markdown_path=report_directory / "validation_ladder_report.md",
    )


def build_validation_ladder_package_spec_hash(
    layer_bundle_entries: Sequence[Mapping[str, Any]],
) -> str:
    identity_payload = [
        {
            "layer_id": str(entry["layer_id"]),
            "layer_sequence_index": int(entry["layer_sequence_index"]),
            "validation_bundle_id": str(entry["validation_bundle_id"]),
            "validation_spec_hash": str(entry["validation_spec_hash"]),
        }
        for entry in sorted(
            layer_bundle_entries,
            key=lambda item: (
                int(item["layer_sequence_index"]),
                str(item["layer_id"]),
                str(item["validation_bundle_id"]),
            ),
        )
    ]
    serialized = json.dumps(
        identity_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_validation_ladder_package_metadata(
    *,
    layer_bundle_entries: Sequence[Mapping[str, Any]],
    processed_simulator_results_dir: str | Path,
) -> dict[str, Any]:
    normalized_entries = _normalize_layer_bundle_entries(
        layer_bundle_entries,
        allow_missing_artifacts=False,
    )
    if not normalized_entries:
        raise ValueError(
            "Validation ladder packaging requires at least one layer bundle entry."
        )
    experiment_ids = {str(entry["experiment_id"]) for entry in normalized_entries}
    if len(experiment_ids) != 1:
        raise ValueError(
            "Validation ladder packaging requires all layer bundles to share one experiment_id."
        )
    experiment_id = next(iter(experiment_ids))
    ladder_spec_hash = build_validation_ladder_package_spec_hash(normalized_entries)
    paths = build_validation_ladder_package_paths(
        experiment_id=experiment_id,
        ladder_spec_hash=ladder_spec_hash,
        processed_simulator_results_dir=processed_simulator_results_dir,
    )
    return {
        "contract_version": VALIDATION_LADDER_PACKAGE_CONTRACT_VERSION,
        "design_note": VALIDATION_LADDER_PACKAGE_DESIGN_NOTE,
        "design_note_version": VALIDATION_LADDER_PACKAGE_DESIGN_NOTE_VERSION,
        "bundle_id": paths.bundle_id,
        "experiment_id": experiment_id,
        "ladder_spec_hash": ladder_spec_hash,
        "ladder_spec_hash_algorithm": DEFAULT_HASH_ALGORITHM,
        "output_root_reference": {
            "processed_simulator_results_dir": str(paths.processed_simulator_results_dir),
        },
        "bundle_layout": {
            "bundle_directory": str(paths.bundle_directory),
            "report_directory": str(paths.report_directory),
            "export_directory": str(paths.export_directory),
            "regression_directory": str(paths.regression_directory),
        },
        "artifacts": {
            artifact_id: _artifact_record(
                path=path,
                format=_TOP_LEVEL_ARTIFACT_FORMATS[artifact_id],
                description=_artifact_description(artifact_id),
            )
            for artifact_id, path in paths.asset_paths().items()
        },
        "layer_bundles": normalized_entries,
    }


def parse_validation_ladder_package_metadata(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("validation ladder package metadata must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "design_note",
        "design_note_version",
        "bundle_id",
        "experiment_id",
        "ladder_spec_hash",
        "ladder_spec_hash_algorithm",
        "output_root_reference",
        "bundle_layout",
        "artifacts",
        "layer_bundles",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "validation ladder package metadata is missing required fields "
            f"{missing_fields!r}."
        )
    contract_version = _normalize_nonempty_string(
        normalized["contract_version"],
        field_name="contract_version",
    )
    if contract_version != VALIDATION_LADDER_PACKAGE_CONTRACT_VERSION:
        raise ValueError(
            "validation ladder package contract_version must be "
            f"{VALIDATION_LADDER_PACKAGE_CONTRACT_VERSION!r}."
        )
    design_note = _normalize_nonempty_string(
        normalized["design_note"],
        field_name="design_note",
    )
    if design_note != VALIDATION_LADDER_PACKAGE_DESIGN_NOTE:
        raise ValueError(
            f"design_note must be {VALIDATION_LADDER_PACKAGE_DESIGN_NOTE!r}."
        )
    design_note_version = _normalize_nonempty_string(
        normalized["design_note_version"],
        field_name="design_note_version",
    )
    if design_note_version != VALIDATION_LADDER_PACKAGE_DESIGN_NOTE_VERSION:
        raise ValueError(
            "design_note_version must be "
            f"{VALIDATION_LADDER_PACKAGE_DESIGN_NOTE_VERSION!r}."
        )
    experiment_id = _normalize_identifier(
        normalized["experiment_id"],
        field_name="experiment_id",
    )
    ladder_spec_hash = _normalize_parameter_hash(normalized["ladder_spec_hash"])
    bundle_id = _normalize_nonempty_string(
        normalized["bundle_id"],
        field_name="bundle_id",
    )
    expected_bundle_id = (
        f"{VALIDATION_LADDER_PACKAGE_CONTRACT_VERSION}:{experiment_id}:{ladder_spec_hash}"
    )
    if bundle_id != expected_bundle_id:
        raise ValueError(
            "bundle_id must match the canonical validation ladder package identity."
        )
    hash_algorithm = _normalize_nonempty_string(
        normalized["ladder_spec_hash_algorithm"],
        field_name="ladder_spec_hash_algorithm",
    )
    if hash_algorithm != DEFAULT_HASH_ALGORITHM:
        raise ValueError(
            f"ladder_spec_hash_algorithm must be {DEFAULT_HASH_ALGORITHM!r}."
        )
    output_root_reference = _normalize_output_root_reference(
        normalized["output_root_reference"]
    )
    paths = build_validation_ladder_package_paths(
        experiment_id=experiment_id,
        ladder_spec_hash=ladder_spec_hash,
        processed_simulator_results_dir=output_root_reference[
            "processed_simulator_results_dir"
        ],
    )
    bundle_layout = _normalize_bundle_layout(
        normalized["bundle_layout"],
        expected_paths=paths,
    )
    artifacts = _normalize_artifacts(
        normalized["artifacts"],
        expected_paths=paths.asset_paths(),
    )
    layer_bundles = _normalize_layer_bundle_entries(
        normalized["layer_bundles"],
        allow_missing_artifacts=True,
    )
    return {
        "contract_version": contract_version,
        "design_note": design_note,
        "design_note_version": design_note_version,
        "bundle_id": bundle_id,
        "experiment_id": experiment_id,
        "ladder_spec_hash": ladder_spec_hash,
        "ladder_spec_hash_algorithm": hash_algorithm,
        "output_root_reference": output_root_reference,
        "bundle_layout": bundle_layout,
        "artifacts": artifacts,
        "layer_bundles": layer_bundles,
    }


def write_validation_ladder_package_metadata(
    package_metadata: Mapping[str, Any],
    output_path: str | Path | None = None,
) -> Path:
    normalized = parse_validation_ladder_package_metadata(package_metadata)
    target_path = (
        Path(output_path).resolve()
        if output_path is not None
        else Path(normalized["artifacts"][METADATA_JSON_KEY]["path"]).resolve()
    )
    return write_json(normalized, target_path)


def load_validation_ladder_package_metadata(
    metadata_path: str | Path,
) -> dict[str, Any]:
    with Path(metadata_path).resolve().open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_validation_ladder_package_metadata(payload)


def discover_validation_ladder_package_paths(
    record: Mapping[str, Any],
) -> dict[str, Path]:
    normalized = parse_validation_ladder_package_metadata(
        record.get("validation_ladder_package")
        if isinstance(record.get("validation_ladder_package"), Mapping)
        else record
    )
    return {
        artifact_id: Path(str(artifact["path"])).resolve()
        for artifact_id, artifact in normalized["artifacts"].items()
    }


def discover_validation_ladder_layer_artifacts(
    record: Mapping[str, Any],
    *,
    layer_id: str | None = None,
) -> dict[str, dict[str, Path]] | dict[str, Path]:
    normalized = parse_validation_ladder_package_metadata(
        record.get("validation_ladder_package")
        if isinstance(record.get("validation_ladder_package"), Mapping)
        else record
    )
    layer_mapping = {
        str(entry["layer_id"]): {
            artifact_id: Path(str(path)).resolve()
            for artifact_id, path in entry["artifact_paths"].items()
        }
        for entry in normalized["layer_bundles"]
    }
    if layer_id is None:
        return layer_mapping
    normalized_layer_id = _normalize_identifier(layer_id, field_name="layer_id")
    if normalized_layer_id not in layer_mapping:
        raise KeyError(f"Unknown layer_id {normalized_layer_id!r}.")
    return layer_mapping[normalized_layer_id]


def write_validation_ladder_regression_baseline(
    summary_payload: Mapping[str, Any],
    output_path: str | Path,
) -> Path:
    snapshot = build_validation_ladder_regression_baseline(summary_payload)
    return write_json(snapshot, output_path)


def build_validation_ladder_regression_baseline(
    summary_payload: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "format_version": REGRESSION_BASELINE_FORMAT,
        "experiment_id": _normalize_identifier(
            summary_payload.get("experiment_id"),
            field_name="summary_payload.experiment_id",
        ),
        "overall_status": _normalize_status(
            summary_payload.get("overall_status"),
            field_name="summary_payload.overall_status",
        ),
        "layer_ids": [
            _normalize_identifier(layer_id, field_name="summary_payload.layer_ids")
            for layer_id in summary_payload.get("present_layer_ids", [])
        ],
        "layer_statuses": {
            _normalize_identifier(layer_id, field_name="layer_statuses.layer_id"): _normalize_status(
                status,
                field_name=f"layer_statuses[{layer_id!r}]",
            )
            for layer_id, status in dict(
                summary_payload.get("layer_statuses", {})
            ).items()
        },
        "validator_statuses": {
            _normalize_identifier(
                validator_id,
                field_name="validator_statuses.validator_id",
            ): _normalize_status(
                status,
                field_name=f"validator_statuses[{validator_id!r}]",
            )
            for validator_id, status in dict(
                summary_payload.get("validator_statuses", {})
            ).items()
        },
        "finding_count": _normalize_nonnegative_int(
            summary_payload.get("finding_count"),
            field_name="summary_payload.finding_count",
        ),
        "case_count": _normalize_nonnegative_int(
            summary_payload.get("case_count"),
            field_name="summary_payload.case_count",
        ),
        "status_counts": _normalize_status_counts(
            summary_payload.get("status_counts"),
            field_name="summary_payload.status_counts",
        ),
    }


def load_validation_ladder_regression_baseline(
    baseline_path: str | Path,
) -> dict[str, Any]:
    with Path(baseline_path).resolve().open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_validation_ladder_regression_baseline(payload)


def parse_validation_ladder_regression_baseline(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("validation ladder regression baseline must be a mapping.")
    required_fields = (
        "format_version",
        "experiment_id",
        "overall_status",
        "layer_ids",
        "layer_statuses",
        "validator_statuses",
        "finding_count",
        "case_count",
        "status_counts",
    )
    missing_fields = [field for field in required_fields if field not in payload]
    if missing_fields:
        raise ValueError(
            "validation ladder regression baseline is missing required fields "
            f"{missing_fields!r}."
        )
    format_version = _normalize_nonempty_string(
        payload.get("format_version"),
        field_name="format_version",
    )
    if format_version != REGRESSION_BASELINE_FORMAT:
        raise ValueError(
            f"validation ladder regression baseline format_version must be {REGRESSION_BASELINE_FORMAT!r}."
        )
    return {
        "format_version": format_version,
        "experiment_id": _normalize_identifier(
            payload.get("experiment_id"),
            field_name="experiment_id",
        ),
        "overall_status": _normalize_status(
            payload.get("overall_status"),
            field_name="overall_status",
        ),
        "layer_ids": [
            _normalize_identifier(layer_id, field_name="layer_ids")
            for layer_id in payload.get("layer_ids", [])
        ],
        "layer_statuses": {
            _normalize_identifier(layer_id, field_name="layer_statuses.layer_id"): _normalize_status(
                status,
                field_name=f"layer_statuses[{layer_id!r}]",
            )
            for layer_id, status in dict(payload.get("layer_statuses", {})).items()
        },
        "validator_statuses": {
            _normalize_identifier(
                validator_id,
                field_name="validator_statuses.validator_id",
            ): _normalize_status(
                status,
                field_name=f"validator_statuses[{validator_id!r}]",
            )
            for validator_id, status in dict(payload.get("validator_statuses", {})).items()
        },
        "finding_count": _normalize_nonnegative_int(
            payload.get("finding_count"),
            field_name="finding_count",
        ),
        "case_count": _normalize_nonnegative_int(
            payload.get("case_count"),
            field_name="case_count",
        ),
        "status_counts": _normalize_status_counts(
            payload.get("status_counts"),
            field_name="status_counts",
        ),
    }


def package_validation_ladder_outputs(
    *,
    layer_bundle_metadata_paths: Sequence[str | Path],
    processed_simulator_results_dir: str | Path | None = None,
    baseline_path: str | Path | None = None,
    require_layer_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    layer_records = _load_layer_bundle_records(layer_bundle_metadata_paths)
    if not layer_records:
        raise ValueError(
            "Validation ladder packaging requires at least one layer_bundle_metadata path."
        )
    if require_layer_ids is not None:
        expected_layer_ids = {
            _normalize_identifier(layer_id, field_name="require_layer_ids")
            for layer_id in require_layer_ids
        }
        discovered_layer_ids = {str(record["layer_id"]) for record in layer_records}
        missing_layer_ids = sorted(expected_layer_ids - discovered_layer_ids)
        if missing_layer_ids:
            raise ValueError(
                "Validation ladder packaging is missing required layer bundles "
                f"{missing_layer_ids!r}."
            )
    resolved_root = (
        Path(processed_simulator_results_dir).resolve()
        if processed_simulator_results_dir is not None
        else Path(
            layer_records[0]["bundle_metadata"]["output_root_reference"][
                "processed_simulator_results_dir"
            ]
        ).resolve()
    )
    package_metadata = build_validation_ladder_package_metadata(
        layer_bundle_entries=[
            _build_layer_bundle_entry(record) for record in layer_records
        ],
        processed_simulator_results_dir=resolved_root,
    )
    package_paths = discover_validation_ladder_package_paths(package_metadata)
    ensure_dir(package_metadata["bundle_layout"]["bundle_directory"])
    ensure_dir(package_metadata["bundle_layout"]["report_directory"])
    ensure_dir(package_metadata["bundle_layout"]["export_directory"])
    ensure_dir(package_metadata["bundle_layout"]["regression_directory"])

    finding_rows = _build_finding_rows(layer_records)
    summary_payload = _build_validation_ladder_summary(
        package_metadata=package_metadata,
        layer_records=layer_records,
        finding_rows=finding_rows,
    )
    baseline_payload = (
        {
            "format_version": REGRESSION_BASELINE_FORMAT,
            "baseline_status": REGRESSION_STATUS_NOT_REQUESTED,
        }
        if baseline_path is None
        else load_validation_ladder_regression_baseline(baseline_path)
    )
    regression_summary = _build_regression_summary(
        summary_payload=summary_payload,
        baseline_payload=baseline_payload,
        baseline_path=baseline_path,
    )
    report_markdown = _render_validation_ladder_report(
        summary_payload=summary_payload,
        regression_summary=regression_summary,
    )

    write_json(summary_payload, package_paths[VALIDATION_LADDER_SUMMARY_ARTIFACT_ID])
    write_jsonl(finding_rows, package_paths[FINDING_ROWS_JSONL_ARTIFACT_ID])
    write_csv_rows(
        fieldnames=[
            "layer_id",
            "layer_sequence_index",
            "layer_bundle_id",
            "validator_id",
            "finding_id",
            "status",
            "case_id",
            "validator_family_id",
            "arm_id",
            "root_id",
            "variant_id",
            "measured_quantity",
            "measured_value",
            "summary_json",
            "comparison_basis_json",
            "diagnostic_metadata_json",
        ],
        rows=finding_rows,
        out_path=package_paths[FINDING_ROWS_CSV_ARTIFACT_ID],
    )
    write_json(baseline_payload, package_paths[REGRESSION_BASELINE_ARTIFACT_ID])
    write_json(regression_summary, package_paths[REGRESSION_SUMMARY_ARTIFACT_ID])
    package_paths[OFFLINE_REVIEW_REPORT_ARTIFACT_ID].write_text(
        report_markdown,
        encoding="utf-8",
    )
    write_validation_ladder_package_metadata(package_metadata)

    return {
        "bundle_id": str(package_metadata["bundle_id"]),
        "metadata_path": str(package_paths[METADATA_JSON_KEY]),
        "summary_path": str(package_paths[VALIDATION_LADDER_SUMMARY_ARTIFACT_ID]),
        "finding_rows_jsonl_path": str(package_paths[FINDING_ROWS_JSONL_ARTIFACT_ID]),
        "finding_rows_csv_path": str(package_paths[FINDING_ROWS_CSV_ARTIFACT_ID]),
        "regression_baseline_path": str(
            package_paths[REGRESSION_BASELINE_ARTIFACT_ID]
        ),
        "regression_summary_path": str(package_paths[REGRESSION_SUMMARY_ARTIFACT_ID]),
        "report_path": str(package_paths[OFFLINE_REVIEW_REPORT_ARTIFACT_ID]),
        "overall_status": str(summary_payload["overall_status"]),
        "regression_status": str(regression_summary["status"]),
        "layer_statuses": copy.deepcopy(dict(summary_payload["layer_statuses"])),
        "validator_statuses": copy.deepcopy(
            dict(summary_payload["validator_statuses"])
        ),
        "finding_count": int(summary_payload["finding_count"]),
        "case_count": int(summary_payload["case_count"]),
    }


def _load_layer_bundle_records(
    layer_bundle_metadata_paths: Sequence[str | Path],
) -> list[dict[str, Any]]:
    if not isinstance(layer_bundle_metadata_paths, Sequence) or isinstance(
        layer_bundle_metadata_paths,
        (str, bytes),
    ):
        raise ValueError(
            "layer_bundle_metadata_paths must be a sequence of validation_bundle.json paths."
        )
    layer_sequence_index_by_id = _layer_sequence_index_by_id()
    records: list[dict[str, Any]] = []
    seen_layer_ids: set[str] = set()
    for index, metadata_path in enumerate(layer_bundle_metadata_paths):
        resolved_metadata_path = Path(metadata_path).resolve()
        bundle_metadata = load_validation_bundle_metadata(resolved_metadata_path)
        artifact_paths = discover_validation_bundle_paths(bundle_metadata)
        summary_payload = _load_json_mapping(artifact_paths[VALIDATION_SUMMARY_ARTIFACT_ID])
        findings_payload = _load_json_mapping(artifact_paths[VALIDATOR_FINDINGS_ARTIFACT_ID])
        review_handoff_payload = _load_json_mapping(artifact_paths[REVIEW_HANDOFF_ARTIFACT_ID])
        layer_id = _infer_single_layer_id(
            summary_payload=summary_payload,
            bundle_metadata=bundle_metadata,
        )
        if layer_id in seen_layer_ids:
            raise ValueError(
                f"Duplicate layer bundle supplied for layer_id {layer_id!r}."
            )
        seen_layer_ids.add(layer_id)
        if layer_id not in layer_sequence_index_by_id:
            raise ValueError(
                f"Unsupported layer_id {layer_id!r} discovered while packaging validation ladder outputs."
            )
        validator_statuses = _validator_statuses_from_summary(summary_payload)
        finding_count = sum(
            len(entries)
            for entries in dict(findings_payload.get("validator_findings", {})).values()
        )
        records.append(
            {
                "input_order": index,
                "layer_id": layer_id,
                "layer_sequence_index": layer_sequence_index_by_id[layer_id],
                "bundle_metadata": bundle_metadata,
                "metadata_path": str(resolved_metadata_path),
                "artifact_paths": {
                    artifact_id: str(path.resolve())
                    for artifact_id, path in artifact_paths.items()
                },
                "summary_payload": summary_payload,
                "findings_payload": findings_payload,
                "review_handoff_payload": review_handoff_payload,
                "overall_status": str(summary_payload["overall_status"]),
                "validator_statuses": validator_statuses,
                "finding_count": finding_count,
                "case_count": len(summary_payload.get("case_summaries", [])),
            }
        )
    return sorted(
        records,
        key=lambda item: (
            int(item["layer_sequence_index"]),
            str(item["layer_id"]),
            int(item["input_order"]),
        ),
    )


def _build_layer_bundle_entry(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "layer_id": str(record["layer_id"]),
        "layer_sequence_index": int(record["layer_sequence_index"]),
        "experiment_id": str(record["bundle_metadata"]["experiment_id"]),
        "validation_bundle_id": str(record["bundle_metadata"]["bundle_id"]),
        "validation_spec_hash": str(record["bundle_metadata"]["validation_spec_hash"]),
        "metadata_path": str(record["metadata_path"]),
        "artifact_paths": copy.deepcopy(dict(record["artifact_paths"])),
        "overall_status": str(record["overall_status"]),
        "validator_statuses": copy.deepcopy(dict(record["validator_statuses"])),
        "finding_count": int(record["finding_count"]),
        "case_count": int(record["case_count"]),
    }


def _build_validation_ladder_summary(
    *,
    package_metadata: Mapping[str, Any],
    layer_records: Sequence[Mapping[str, Any]],
    finding_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    layer_statuses = {
        str(record["layer_id"]): str(record["overall_status"]) for record in layer_records
    }
    validator_statuses: dict[str, str] = {}
    for record in layer_records:
        for validator_id, status in dict(record["validator_statuses"]).items():
            validator_statuses[str(validator_id)] = str(status)
    overall_status = _worst_status(layer_statuses.values())
    status_counts = _aggregate_status_counts(finding_rows)
    contract_layer_ids = [str(item["layer_id"]) for item in discover_validation_layers(
        build_validation_ladder_contract_metadata()
    )]
    present_layer_ids = [str(record["layer_id"]) for record in layer_records]
    missing_layer_ids = [
        layer_id for layer_id in contract_layer_ids if layer_id not in set(present_layer_ids)
    ]
    return {
        "format_version": VALIDATION_LADDER_SUMMARY_FORMAT,
        "contract_version": VALIDATION_LADDER_PACKAGE_CONTRACT_VERSION,
        "bundle_id": str(package_metadata["bundle_id"]),
        "experiment_id": str(package_metadata["experiment_id"]),
        "ladder_spec_hash": str(package_metadata["ladder_spec_hash"]),
        "overall_status": overall_status,
        "layer_count": len(layer_records),
        "validator_count": len(validator_statuses),
        "finding_count": len(finding_rows),
        "case_count": sum(int(record["case_count"]) for record in layer_records),
        "status_counts": status_counts,
        "present_layer_ids": present_layer_ids,
        "missing_layer_ids": missing_layer_ids,
        "layer_statuses": layer_statuses,
        "validator_statuses": validator_statuses,
        "layers": [
            {
                "layer_id": str(record["layer_id"]),
                "layer_sequence_index": int(record["layer_sequence_index"]),
                "validation_bundle_id": str(record["bundle_metadata"]["bundle_id"]),
                "validation_spec_hash": str(
                    record["bundle_metadata"]["validation_spec_hash"]
                ),
                "overall_status": str(record["overall_status"]),
                "validator_statuses": copy.deepcopy(dict(record["validator_statuses"])),
                "finding_count": int(record["finding_count"]),
                "case_count": int(record["case_count"]),
                "artifact_paths": copy.deepcopy(dict(record["artifact_paths"])),
                "summary_path": str(record["artifact_paths"][VALIDATION_SUMMARY_ARTIFACT_ID]),
                "findings_path": str(
                    record["artifact_paths"][VALIDATOR_FINDINGS_ARTIFACT_ID]
                ),
                "review_handoff_path": str(
                    record["artifact_paths"][REVIEW_HANDOFF_ARTIFACT_ID]
                ),
                "report_path": str(
                    record["artifact_paths"][OFFLINE_REVIEW_REPORT_ARTIFACT_ID]
                ),
            }
            for record in layer_records
        ],
        "artifact_paths": {
            artifact_id: str(artifact["path"])
            for artifact_id, artifact in package_metadata["artifacts"].items()
        },
    }


def _build_finding_rows(
    layer_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in layer_records:
        validator_findings = dict(
            record["findings_payload"].get("validator_findings", {})
        )
        for validator_id in sorted(validator_findings):
            for finding in list(validator_findings[validator_id]):
                row = {
                    "layer_id": str(record["layer_id"]),
                    "layer_sequence_index": int(record["layer_sequence_index"]),
                    "layer_bundle_id": str(record["bundle_metadata"]["bundle_id"]),
                    "validator_id": str(validator_id),
                    "finding_id": str(finding.get("finding_id")),
                    "status": str(finding.get("status")),
                    "case_id": str(finding.get("case_id", "")),
                    "validator_family_id": str(
                        finding.get("validator_family_id", "")
                    ),
                    "arm_id": _optional_scalar(finding.get("arm_id")),
                    "root_id": _optional_scalar(finding.get("root_id")),
                    "variant_id": _optional_scalar(finding.get("variant_id")),
                    "measured_quantity": _optional_scalar(
                        finding.get("measured_quantity")
                    ),
                    "measured_value": _optional_scalar(finding.get("measured_value")),
                    "summary_json": _json_or_empty(finding.get("summary")),
                    "comparison_basis_json": _json_or_empty(
                        finding.get("comparison_basis")
                    ),
                    "diagnostic_metadata_json": _json_or_empty(
                        finding.get("diagnostic_metadata")
                    ),
                }
                rows.append(row)
    rows.sort(
        key=lambda item: (
            int(item["layer_sequence_index"]),
            str(item["validator_id"]),
            str(item["finding_id"]),
        )
    )
    return rows


def _build_regression_summary(
    *,
    summary_payload: Mapping[str, Any],
    baseline_payload: Mapping[str, Any],
    baseline_path: str | Path | None,
) -> dict[str, Any]:
    current_snapshot = build_validation_ladder_regression_baseline(summary_payload)
    requested = baseline_path is not None
    if not requested:
        return {
            "format_version": REGRESSION_SUMMARY_FORMAT,
            "status": REGRESSION_STATUS_NOT_REQUESTED,
            "baseline_requested": False,
            "baseline_source_path": None,
            "baseline_snapshot": None,
            "current_snapshot": current_snapshot,
            "mismatches": [],
        }
    expected_snapshot = parse_validation_ladder_regression_baseline(baseline_payload)
    mismatches: list[dict[str, Any]] = []
    for field in (
        "experiment_id",
        "overall_status",
        "layer_ids",
        "layer_statuses",
        "validator_statuses",
        "finding_count",
        "case_count",
        "status_counts",
    ):
        if current_snapshot[field] != expected_snapshot[field]:
            mismatches.append(
                {
                    "field": field,
                    "expected": copy.deepcopy(expected_snapshot[field]),
                    "actual": copy.deepcopy(current_snapshot[field]),
                }
            )
    return {
        "format_version": REGRESSION_SUMMARY_FORMAT,
        "status": VALIDATION_STATUS_PASS if not mismatches else VALIDATION_STATUS_BLOCKING,
        "baseline_requested": True,
        "baseline_source_path": str(Path(baseline_path).resolve()),
        "baseline_snapshot": expected_snapshot,
        "current_snapshot": current_snapshot,
        "mismatches": mismatches,
    }


def _render_validation_ladder_report(
    *,
    summary_payload: Mapping[str, Any],
    regression_summary: Mapping[str, Any],
) -> str:
    lines = [
        "# Validation Ladder Report",
        "",
        f"- Overall status: `{summary_payload['overall_status']}`",
        f"- Experiment id: `{summary_payload['experiment_id']}`",
        f"- Package bundle id: `{summary_payload['bundle_id']}`",
        f"- Regression status: `{regression_summary['status']}`",
        "",
        "## Aggregate Summary",
        "",
        f"- Layers present: `{summary_payload['present_layer_ids']}`",
        f"- Missing layers: `{summary_payload['missing_layer_ids']}`",
        f"- Validator count: `{summary_payload['validator_count']}`",
        f"- Finding count: `{summary_payload['finding_count']}`",
        f"- Case count: `{summary_payload['case_count']}`",
        f"- Finding status counts: `{summary_payload['status_counts']}`",
        "",
        "## Layer Bundles",
        "",
    ]
    for layer in summary_payload["layers"]:
        lines.extend(
            [
                f"### `{layer['layer_id']}`",
                "",
                f"- Status: `{layer['overall_status']}`",
                f"- Bundle: `{layer['validation_bundle_id']}`",
                f"- Finding count: `{layer['finding_count']}`",
                f"- Case count: `{layer['case_count']}`",
                f"- Validator statuses: `{layer['validator_statuses']}`",
                f"- Summary path: `{layer['summary_path']}`",
                f"- Findings path: `{layer['findings_path']}`",
                f"- Review handoff path: `{layer['review_handoff_path']}`",
                f"- Report path: `{layer['report_path']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Notebook Exports",
            "",
            f"- JSONL rows: `{summary_payload['artifact_paths'][FINDING_ROWS_JSONL_ARTIFACT_ID]}`",
            f"- CSV rows: `{summary_payload['artifact_paths'][FINDING_ROWS_CSV_ARTIFACT_ID]}`",
            "",
            "## Regression",
            "",
            f"- Baseline reference: `{summary_payload['artifact_paths'][REGRESSION_BASELINE_ARTIFACT_ID]}`",
            f"- Regression summary: `{summary_payload['artifact_paths'][REGRESSION_SUMMARY_ARTIFACT_ID]}`",
        ]
    )
    if regression_summary["mismatches"]:
        lines.extend(["", "### Mismatches", ""])
        for mismatch in regression_summary["mismatches"]:
            lines.append(
                "- "
                f"`{mismatch['field']}` expected="
                f"`{json.dumps(mismatch['expected'], sort_keys=True)}` actual="
                f"`{json.dumps(mismatch['actual'], sort_keys=True)}`"
            )
    return "\n".join(lines).rstrip() + "\n"


def _layer_sequence_index_by_id() -> dict[str, int]:
    return {
        str(item["layer_id"]): int(item["sequence_index"])
        for item in discover_validation_layers(build_validation_ladder_contract_metadata())
    }


def _infer_single_layer_id(
    *,
    summary_payload: Mapping[str, Any],
    bundle_metadata: Mapping[str, Any],
) -> str:
    layer_ids = [
        _normalize_identifier(layer_id, field_name="active_layer_ids")
        for layer_id in summary_payload.get(
            "active_layer_ids",
            bundle_metadata.get("validation_plan_reference", {}).get(
                "active_layer_ids",
                [],
            ),
        )
    ]
    if len(layer_ids) != 1:
        raise ValueError(
            "Validation ladder packaging expects one active_layer_id per layer bundle."
        )
    return layer_ids[0]


def _validator_statuses_from_summary(
    summary_payload: Mapping[str, Any],
) -> dict[str, str]:
    validator_statuses: dict[str, str] = {}
    for layer in list(summary_payload.get("layers", [])):
        for family in list(layer.get("validator_families", [])):
            for validator in list(family.get("validators", [])):
                validator_statuses[
                    _normalize_identifier(
                        validator.get("validator_id"),
                        field_name="validator.validator_id",
                    )
                ] = _normalize_status(
                    validator.get("status"),
                    field_name=f"validator[{validator.get('validator_id')!r}].status",
                )
    return validator_statuses


def _aggregate_status_counts(
    finding_rows: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    return {
        VALIDATION_STATUS_PASS: sum(
            1 for row in finding_rows if str(row["status"]) == VALIDATION_STATUS_PASS
        ),
        VALIDATION_STATUS_REVIEW: sum(
            1
            for row in finding_rows
            if str(row["status"]) == VALIDATION_STATUS_REVIEW
        ),
        VALIDATION_STATUS_BLOCKED: sum(
            1
            for row in finding_rows
            if str(row["status"]) == VALIDATION_STATUS_BLOCKED
        ),
        VALIDATION_STATUS_BLOCKING: sum(
            1
            for row in finding_rows
            if str(row["status"]) == VALIDATION_STATUS_BLOCKING
        ),
    }


def _worst_status(statuses: Sequence[str] | Any) -> str:
    ordered = [
        str(status)
        for status in statuses
        if str(status) in _STATUS_RANK
    ]
    if not ordered:
        return VALIDATION_STATUS_BLOCKED
    return max(ordered, key=lambda item: _STATUS_RANK[item])


def _artifact_record(*, path: str | Path, format: str, description: str) -> dict[str, Any]:
    return {
        "path": str(Path(path).resolve()),
        "format": format,
        "description": description,
    }


def _artifact_description(artifact_id: str) -> str:
    descriptions = {
        METADATA_JSON_KEY: "Authoritative packaged validation-ladder metadata.",
        VALIDATION_LADDER_SUMMARY_ARTIFACT_ID: "Aggregate layer and validator gate summary for packaged Milestone 13 outputs.",
        FINDING_ROWS_JSONL_ARTIFACT_ID: "Notebook-friendly JSONL export flattened across packaged validation findings.",
        FINDING_ROWS_CSV_ARTIFACT_ID: "Notebook-friendly CSV export flattened across packaged validation findings.",
        REGRESSION_BASELINE_ARTIFACT_ID: "Resolved regression baseline snapshot used for packaged ladder comparison, or a stub when no baseline was requested.",
        REGRESSION_SUMMARY_ARTIFACT_ID: "Comparison of the packaged ladder summary against the requested regression baseline snapshot.",
        OFFLINE_REVIEW_REPORT_ARTIFACT_ID: "Offline Markdown report that summarizes packaged Milestone 13 layer outputs and regression results.",
    }
    return descriptions[artifact_id]


def _normalize_output_root_reference(payload: Any) -> dict[str, str]:
    if not isinstance(payload, Mapping):
        raise ValueError("output_root_reference must be a mapping.")
    processed_dir = Path(
        _normalize_nonempty_string(
            payload.get("processed_simulator_results_dir"),
            field_name="output_root_reference.processed_simulator_results_dir",
        )
    ).resolve()
    return {
        "processed_simulator_results_dir": str(processed_dir),
    }


def _normalize_bundle_layout(
    payload: Any,
    *,
    expected_paths: ValidationLadderPackagePaths,
) -> dict[str, str]:
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
    export_directory = Path(
        _normalize_nonempty_string(
            payload.get("export_directory"),
            field_name="bundle_layout.export_directory",
        )
    ).resolve()
    regression_directory = Path(
        _normalize_nonempty_string(
            payload.get("regression_directory"),
            field_name="bundle_layout.regression_directory",
        )
    ).resolve()
    if bundle_directory != expected_paths.bundle_directory:
        raise ValueError("bundle_layout.bundle_directory must match the canonical package directory.")
    if report_directory != expected_paths.report_directory:
        raise ValueError("bundle_layout.report_directory must match the canonical report directory.")
    if export_directory != expected_paths.export_directory:
        raise ValueError("bundle_layout.export_directory must match the canonical export directory.")
    if regression_directory != expected_paths.regression_directory:
        raise ValueError(
            "bundle_layout.regression_directory must match the canonical regression directory."
        )
    return {
        "bundle_directory": str(bundle_directory),
        "report_directory": str(report_directory),
        "export_directory": str(export_directory),
        "regression_directory": str(regression_directory),
    }


def _normalize_artifacts(
    payload: Any,
    *,
    expected_paths: Mapping[str, Path],
) -> dict[str, dict[str, str]]:
    if not isinstance(payload, Mapping):
        raise ValueError("artifacts must be a mapping.")
    unknown_keys = sorted(set(payload) - set(expected_paths))
    missing_keys = sorted(set(expected_paths) - set(payload))
    if unknown_keys or missing_keys:
        raise ValueError(
            "artifacts must declare the canonical validation ladder package artifact ids."
        )
    normalized: dict[str, dict[str, str]] = {}
    for artifact_id, expected_path in expected_paths.items():
        artifact = payload.get(artifact_id)
        if not isinstance(artifact, Mapping):
            raise ValueError(f"artifacts[{artifact_id!r}] must be a mapping.")
        path = Path(
            _normalize_nonempty_string(
                artifact.get("path"),
                field_name=f"artifacts.{artifact_id}.path",
            )
        ).resolve()
        if path != expected_path.resolve():
            raise ValueError(
                f"artifacts.{artifact_id}.path must match the canonical packaged output path."
            )
        format_version = _normalize_nonempty_string(
            artifact.get("format"),
            field_name=f"artifacts.{artifact_id}.format",
        )
        if format_version != _TOP_LEVEL_ARTIFACT_FORMATS[artifact_id]:
            raise ValueError(
                f"artifacts.{artifact_id}.format must be {_TOP_LEVEL_ARTIFACT_FORMATS[artifact_id]!r}."
            )
        normalized[artifact_id] = {
            "path": str(path),
            "format": format_version,
            "description": _normalize_nonempty_string(
                artifact.get("description"),
                field_name=f"artifacts.{artifact_id}.description",
            ),
        }
    return normalized


def _normalize_layer_bundle_entries(
    payload: Any,
    *,
    allow_missing_artifacts: bool,
) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("layer_bundles must be a sequence.")
    sequence_index_by_id = _layer_sequence_index_by_id()
    normalized: list[dict[str, Any]] = []
    seen_layer_ids: set[str] = set()
    for index, entry in enumerate(payload):
        if not isinstance(entry, Mapping):
            raise ValueError(f"layer_bundles[{index}] must be a mapping.")
        layer_id = _normalize_identifier(
            entry.get("layer_id"),
            field_name=f"layer_bundles[{index}].layer_id",
        )
        if layer_id not in set(SUPPORTED_VALIDATION_LAYER_IDS):
            raise ValueError(f"Unsupported layer_id {layer_id!r}.")
        if layer_id in seen_layer_ids:
            raise ValueError(f"Duplicate layer_id {layer_id!r} in layer_bundles.")
        seen_layer_ids.add(layer_id)
        layer_sequence_index = _normalize_positive_int(
            entry.get("layer_sequence_index"),
            field_name=f"layer_bundles[{index}].layer_sequence_index",
        )
        if layer_sequence_index != sequence_index_by_id[layer_id]:
            raise ValueError(
                f"layer_bundles[{index}].layer_sequence_index must match the contract sequence index."
            )
        artifact_paths_payload = entry.get("artifact_paths")
        if not isinstance(artifact_paths_payload, Mapping):
            raise ValueError(
                f"layer_bundles[{index}].artifact_paths must be a mapping."
            )
        required_layer_artifacts = {
            VALIDATION_METADATA_JSON_KEY,
            VALIDATION_SUMMARY_ARTIFACT_ID,
            VALIDATOR_FINDINGS_ARTIFACT_ID,
            REVIEW_HANDOFF_ARTIFACT_ID,
            OFFLINE_REVIEW_REPORT_ARTIFACT_ID,
        }
        if required_layer_artifacts - set(artifact_paths_payload):
            raise ValueError(
                f"layer_bundles[{index}].artifact_paths must contain the canonical validation artifact ids."
            )
        artifact_paths = {
            str(artifact_id): str(
                Path(
                    _normalize_nonempty_string(
                        artifact_paths_payload.get(artifact_id),
                        field_name=(
                            f"layer_bundles[{index}].artifact_paths[{artifact_id!r}]"
                        ),
                    )
                ).resolve()
            )
            for artifact_id in sorted(required_layer_artifacts)
        }
        if not allow_missing_artifacts:
            for artifact_id, path in artifact_paths.items():
                if not Path(path).exists():
                    raise ValueError(
                        f"layer_bundles[{index}] is missing required artifact {artifact_id!r} at {path}."
                    )
        validator_statuses_payload = entry.get("validator_statuses")
        if not isinstance(validator_statuses_payload, Mapping):
            raise ValueError(
                f"layer_bundles[{index}].validator_statuses must be a mapping."
            )
        normalized.append(
            {
                "layer_id": layer_id,
                "layer_sequence_index": layer_sequence_index,
                "experiment_id": _normalize_identifier(
                    entry.get("experiment_id"),
                    field_name=f"layer_bundles[{index}].experiment_id",
                ),
                "validation_bundle_id": _normalize_nonempty_string(
                    entry.get("validation_bundle_id"),
                    field_name=f"layer_bundles[{index}].validation_bundle_id",
                ),
                "validation_spec_hash": _normalize_parameter_hash(
                    entry.get("validation_spec_hash")
                ),
                "metadata_path": str(
                    Path(
                        _normalize_nonempty_string(
                            entry.get("metadata_path"),
                            field_name=f"layer_bundles[{index}].metadata_path",
                        )
                    ).resolve()
                ),
                "artifact_paths": artifact_paths,
                "overall_status": _normalize_status(
                    entry.get("overall_status"),
                    field_name=f"layer_bundles[{index}].overall_status",
                ),
                "validator_statuses": {
                    _normalize_identifier(
                        validator_id,
                        field_name=(
                            f"layer_bundles[{index}].validator_statuses.validator_id"
                        ),
                    ): _normalize_status(
                        status,
                        field_name=(
                            f"layer_bundles[{index}].validator_statuses[{validator_id!r}]"
                        ),
                    )
                    for validator_id, status in validator_statuses_payload.items()
                },
                "finding_count": _normalize_nonnegative_int(
                    entry.get("finding_count"),
                    field_name=f"layer_bundles[{index}].finding_count",
                ),
                "case_count": _normalize_nonnegative_int(
                    entry.get("case_count"),
                    field_name=f"layer_bundles[{index}].case_count",
                ),
            }
        )
    normalized.sort(
        key=lambda item: (
            int(item["layer_sequence_index"]),
            str(item["layer_id"]),
            str(item["validation_bundle_id"]),
        )
    )
    return normalized


def _normalize_status(value: Any, *, field_name: str) -> str:
    normalized = _normalize_nonempty_string(value, field_name=field_name)
    if normalized == REGRESSION_STATUS_NOT_REQUESTED:
        return normalized
    if normalized not in _STATUS_RANK:
        raise ValueError(
            f"{field_name} must be one of {sorted(_STATUS_RANK)!r} or "
            f"{REGRESSION_STATUS_NOT_REQUESTED!r}."
        )
    return normalized


def _normalize_status_counts(payload: Any, *, field_name: str) -> dict[str, int]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    normalized = {
        status: _normalize_nonnegative_int(
            payload.get(status, 0),
            field_name=f"{field_name}.{status}",
        )
        for status in (
            VALIDATION_STATUS_PASS,
            VALIDATION_STATUS_REVIEW,
            VALIDATION_STATUS_BLOCKED,
            VALIDATION_STATUS_BLOCKING,
        )
    }
    return normalized


def _normalize_nonnegative_int(value: Any, *, field_name: str) -> int:
    normalized = _normalize_positive_int(
        1 if value is None else int(value) + 1,
        field_name=field_name,
    )
    return normalized - 1


def _load_json_mapping(path: str | Path) -> dict[str, Any]:
    with Path(path).resolve().open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"JSON payload at {path} must be a mapping.")
    return copy.deepcopy(dict(payload))


def _optional_scalar(value: Any) -> str | int | float | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float)):
        return value
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _json_or_empty(value: Any) -> str:
    if value in (None, ""):
        return ""
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


__all__ = [
    "FINDING_ROWS_CSV_ARTIFACT_ID",
    "FINDING_ROWS_JSONL_ARTIFACT_ID",
    "METADATA_JSON_KEY",
    "OFFLINE_REVIEW_REPORT_ARTIFACT_ID",
    "REGRESSION_BASELINE_ARTIFACT_ID",
    "REGRESSION_SUMMARY_ARTIFACT_ID",
    "VALIDATION_LADDER_PACKAGE_CONTRACT_VERSION",
    "VALIDATION_LADDER_SUMMARY_ARTIFACT_ID",
    "build_validation_ladder_package_metadata",
    "build_validation_ladder_package_paths",
    "build_validation_ladder_package_spec_hash",
    "build_validation_ladder_regression_baseline",
    "discover_validation_ladder_layer_artifacts",
    "discover_validation_ladder_package_paths",
    "load_validation_ladder_package_metadata",
    "load_validation_ladder_regression_baseline",
    "package_validation_ladder_outputs",
    "parse_validation_ladder_package_metadata",
    "parse_validation_ladder_regression_baseline",
    "write_validation_ladder_package_metadata",
    "write_validation_ladder_regression_baseline",
]
