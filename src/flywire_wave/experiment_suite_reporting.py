from __future__ import annotations

import html
import json
import math
import os
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .experiment_suite_aggregation import (
    SHARED_COMPARISON_SECTION_ID,
    VALIDATION_FINDINGS_SECTION_ID,
    WAVE_ONLY_DIAGNOSTICS_SECTION_ID,
    execute_experiment_suite_aggregation_workflow,
)
from .experiment_suite_contract import (
    COMPARISON_PLOT_ROLE_ID,
    COMPARISON_PLOT_SOURCE_KIND,
    PLOT_OUTPUT_ARTIFACT_SCOPE,
    REVIEW_ARTIFACT_ROLE_ID,
    REVIEW_ARTIFACT_SOURCE_KIND,
    REVIEW_OUTPUT_ARTIFACT_SCOPE,
    SUMMARY_OUTPUT_ARTIFACT_SCOPE,
    SUMMARY_TABLE_ROLE_ID,
    SUMMARY_TABLE_SOURCE_KIND,
)
from .experiment_suite_packaging import (
    COMPARISON_PLOT_CATEGORY,
    REVIEW_ARTIFACT_CATEGORY,
    SUMMARY_TABLE_CATEGORY,
    load_experiment_suite_package_metadata,
    load_experiment_suite_result_index,
    resolve_experiment_suite_package_metadata_path,
)
from .io_utils import ensure_dir, write_json
from .stimulus_contract import _normalize_identifier


EXPERIMENT_SUITE_REVIEW_REPORT_FORMAT = "experiment_suite_review_report.v1"
EXPERIMENT_SUITE_REVIEW_ARTIFACT_CATALOG_FORMAT = (
    "experiment_suite_review_artifact_catalog.v1"
)

DEFAULT_REVIEW_DIRECTORY_NAME = "suite_review"

REVIEW_INDEX_ARTIFACT_ID = "suite_review_index"
REVIEW_SUMMARY_ARTIFACT_ID = "suite_review_summary_json"
REVIEW_ARTIFACT_CATALOG_ID = "suite_review_artifact_catalog_json"

_SECTION_ORDER = (
    SHARED_COMPARISON_SECTION_ID,
    WAVE_ONLY_DIAGNOSTICS_SECTION_ID,
    VALIDATION_FINDINGS_SECTION_ID,
)
_SECTION_DISPLAY = {
    SHARED_COMPARISON_SECTION_ID: {
        "display_name": "Shared Comparison Metrics",
        "review_class": "fairness_critical_shared_comparison",
        "description": (
            "Fairness-critical baseline-versus-wave comparisons derived from packaged "
            "Milestone 12 experiment-analysis rollups."
        ),
        "html_class": "shared",
        "accent": "#0f5c63",
    },
    WAVE_ONLY_DIAGNOSTICS_SECTION_ID: {
        "display_name": "Wave-Only Diagnostics",
        "review_class": "wave_only_diagnostic",
        "description": (
            "Wave-only diagnostic signals kept separate from the fairness-critical "
            "shared-comparison surface."
        ),
        "html_class": "wave",
        "accent": "#8d5b17",
    },
    VALIDATION_FINDINGS_SECTION_ID: {
        "display_name": "Validation Findings",
        "review_class": "validation_finding",
        "description": (
            "Milestone 13 validation status and finding deltas, kept distinct from the "
            "shared-comparison and wave-diagnostic surfaces."
        ),
        "html_class": "validation",
        "accent": "#8b2f39",
    },
}
_PLOT_PALETTE = (
    "#0f5c63",
    "#a44a3f",
    "#6b7b33",
    "#7b4f9e",
    "#c27d00",
    "#1f4b99",
)
_PLOT_VALUE_DIGITS = 3
_PREVIEW_ROW_LIMIT = 12
_SUMMARY_TABLE_ARTIFACT_BY_SECTION = {
    SHARED_COMPARISON_SECTION_ID: "shared_comparison_summary_table",
    WAVE_ONLY_DIAGNOSTICS_SECTION_ID: "wave_diagnostic_summary_table",
    VALIDATION_FINDINGS_SECTION_ID: "validation_summary_table",
}
_TABLE_EXPORT_SPECS = {
    SHARED_COMPARISON_SECTION_ID: (
        {
            "artifact_id": "shared_comparison_cell_rollups",
            "workflow_key": "shared_cell_rows_path",
            "rows_key": "cell_rollup_rows",
            "display_name": "Shared Comparison Cell Rollups",
            "table_kind": "cell_rollup_rows",
        },
        {
            "artifact_id": "shared_comparison_paired_rows",
            "workflow_key": "shared_pair_rows_path",
            "rows_key": "paired_comparison_rows",
            "display_name": "Shared Comparison Paired Rows",
            "table_kind": "paired_comparison_rows",
        },
        {
            "artifact_id": "shared_comparison_summary_table",
            "workflow_key": "shared_summary_table_path",
            "rows_key": "summary_table_rows",
            "display_name": "Shared Comparison Summary Table",
            "table_kind": "summary_table_rows",
        },
    ),
    WAVE_ONLY_DIAGNOSTICS_SECTION_ID: (
        {
            "artifact_id": "wave_diagnostic_cell_rollups",
            "workflow_key": "wave_cell_rows_path",
            "rows_key": "cell_rollup_rows",
            "display_name": "Wave Diagnostic Cell Rollups",
            "table_kind": "cell_rollup_rows",
        },
        {
            "artifact_id": "wave_diagnostic_paired_rows",
            "workflow_key": "wave_pair_rows_path",
            "rows_key": "paired_comparison_rows",
            "display_name": "Wave Diagnostic Paired Rows",
            "table_kind": "paired_comparison_rows",
        },
        {
            "artifact_id": "wave_diagnostic_summary_table",
            "workflow_key": "wave_summary_table_path",
            "rows_key": "summary_table_rows",
            "display_name": "Wave Diagnostic Summary Table",
            "table_kind": "summary_table_rows",
        },
    ),
    VALIDATION_FINDINGS_SECTION_ID: (
        {
            "artifact_id": "validation_cell_summaries",
            "workflow_key": "validation_cell_rows_path",
            "rows_key": "cell_summary_rows",
            "display_name": "Validation Cell Summaries",
            "table_kind": "cell_summary_rows",
        },
        {
            "artifact_id": "validation_paired_rows",
            "workflow_key": "validation_pair_rows_path",
            "rows_key": "paired_comparison_rows",
            "display_name": "Validation Paired Rows",
            "table_kind": "paired_comparison_rows",
        },
        {
            "artifact_id": "validation_finding_rows",
            "workflow_key": "validation_finding_rows_path",
            "rows_key": "finding_rows",
            "display_name": "Validation Finding Rows",
            "table_kind": "finding_rows",
        },
        {
            "artifact_id": "validation_summary_table",
            "workflow_key": "validation_summary_table_path",
            "rows_key": "summary_table_rows",
            "display_name": "Validation Summary Table",
            "table_kind": "summary_table_rows",
        },
    ),
}


@dataclass(frozen=True)
class ExperimentSuiteReviewPaths:
    suite_root: Path
    review_directory: Path
    plot_directory: Path
    metadata_directory: Path
    catalog_directory: Path
    index_path: Path
    summary_path: Path
    artifact_catalog_path: Path


def build_experiment_suite_review_paths(
    *,
    suite_root: str | Path,
    output_dir: str | Path | None = None,
) -> ExperimentSuiteReviewPaths:
    resolved_suite_root = Path(suite_root).resolve()
    review_directory = (
        Path(output_dir).resolve()
        if output_dir is not None
        else (
            resolved_suite_root
            / "package"
            / "report"
            / DEFAULT_REVIEW_DIRECTORY_NAME
        ).resolve()
    )
    return ExperimentSuiteReviewPaths(
        suite_root=resolved_suite_root,
        review_directory=review_directory,
        plot_directory=(review_directory / "plots").resolve(),
        metadata_directory=(review_directory / "metadata").resolve(),
        catalog_directory=(review_directory / "catalog").resolve(),
        index_path=(review_directory / "index.html").resolve(),
        summary_path=(review_directory / "suite_review_summary.json").resolve(),
        artifact_catalog_path=(review_directory / "catalog" / "artifact_catalog.json").resolve(),
    )


def generate_experiment_suite_review_report(
    record: Mapping[str, Any] | str | Path,
    *,
    table_dimension_ids: Sequence[str] | None = None,
    aggregation_output_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    normalized_record, package_metadata_path, package_metadata = _resolve_report_record(
        record
    )
    result_index = load_experiment_suite_result_index(normalized_record)
    suite_root = Path(result_index["suite_root"]).resolve()
    if package_metadata_path is None:
        package_metadata_path = resolve_experiment_suite_package_metadata_path(
            suite_root=suite_root
        )
    if package_metadata is None and package_metadata_path.exists():
        package_metadata = load_experiment_suite_package_metadata(package_metadata_path)
    aggregation_result = execute_experiment_suite_aggregation_workflow(
        normalized_record,
        table_dimension_ids=table_dimension_ids,
        output_dir=aggregation_output_dir,
    )
    aggregation_summary = _load_json_mapping(
        aggregation_result["summary_path"],
        field_name="suite_aggregation_summary",
    )
    paths = build_experiment_suite_review_paths(
        suite_root=suite_root,
        output_dir=output_dir,
    )
    ensure_dir(paths.review_directory)
    ensure_dir(paths.plot_directory)
    ensure_dir(paths.metadata_directory)
    ensure_dir(paths.catalog_directory)

    paired_rows_by_section = {
        section_id: {
            str(row["pairing_id"]): dict(row)
            for row in _section_rows(
                aggregation_summary,
                section_id=section_id,
                rows_key="paired_comparison_rows",
            )
            if row.get("pairing_id") is not None
        }
        for section_id in _SECTION_ORDER
    }
    table_artifacts: list[dict[str, Any]] = []
    section_rows_preview: dict[str, list[dict[str, Any]]] = {}
    tables_by_id: dict[str, dict[str, Any]] = {}
    sections: list[dict[str, Any]] = []

    for section_id in _SECTION_ORDER:
        section_payload = aggregation_summary.get(section_id)
        if not isinstance(section_payload, Mapping):
            continue
        section_table_artifacts = _build_table_artifacts(
            section_id=section_id,
            section_payload=section_payload,
            aggregation_result=aggregation_result,
            review_directory=paths.review_directory,
            paired_rows_by_id=paired_rows_by_section.get(section_id, {}),
        )
        for artifact in section_table_artifacts:
            tables_by_id[str(artifact["artifact_id"])] = artifact
        table_artifacts.extend(section_table_artifacts)
        section_rows_preview[section_id] = [
            dict(row)
            for row in _section_rows(
                aggregation_summary,
                section_id=section_id,
                rows_key="summary_table_rows",
            )[:_PREVIEW_ROW_LIMIT]
        ]

    plot_artifacts: list[dict[str, Any]] = []
    for section_id in _SECTION_ORDER:
        section_payload = aggregation_summary.get(section_id)
        if not isinstance(section_payload, Mapping):
            continue
        section_plots = _build_plot_artifacts(
            section_id=section_id,
            section_payload=section_payload,
            review_paths=paths,
            review_directory=paths.review_directory,
            summary_table_artifact=tables_by_id.get(
                _SUMMARY_TABLE_ARTIFACT_BY_SECTION.get(section_id, "")
            ),
            paired_rows_by_id=paired_rows_by_section.get(section_id, {}),
            table_dimension_ids=aggregation_summary["table_dimensions"]["table_dimension_ids"],
        )
        plot_artifacts.extend(section_plots)

    linked_package_artifacts = _build_linked_package_artifacts(
        package_metadata=package_metadata,
        package_metadata_path=package_metadata_path,
        result_index=result_index,
        review_directory=paths.review_directory,
    )
    review_artifacts = _build_review_artifacts(paths, review_directory=paths.review_directory)
    artifact_catalog = {
        "format_version": EXPERIMENT_SUITE_REVIEW_ARTIFACT_CATALOG_FORMAT,
        "suite_reference": _suite_reference(
            result_index=result_index,
            package_metadata_path=package_metadata_path if package_metadata is not None else None,
        ),
        "aggregation_reference": {
            "summary_path": str(Path(aggregation_result["summary_path"]).resolve()),
            "output_directory": str(Path(aggregation_result["output_directory"]).resolve()),
            "table_dimension_ids": list(aggregation_result["table_dimension_ids"]),
        },
        "table_artifacts": table_artifacts,
        "plot_artifacts": plot_artifacts,
        "review_artifacts": review_artifacts,
        "linked_package_artifacts": linked_package_artifacts,
    }
    write_json(artifact_catalog, paths.artifact_catalog_path)

    for section_id in _SECTION_ORDER:
        section_payload = aggregation_summary.get(section_id)
        if not isinstance(section_payload, Mapping):
            continue
        display = _SECTION_DISPLAY[section_id]
        section_table_artifacts = [
            dict(item) for item in table_artifacts if str(item["section_id"]) == section_id
        ]
        section_plot_artifacts = [
            dict(item) for item in plot_artifacts if str(item["section_id"]) == section_id
        ]
        sections.append(
            {
                "section_id": section_id,
                "display_name": display["display_name"],
                "review_class": display["review_class"],
                "description": display["description"],
                "table_export_count": len(section_table_artifacts),
                "plot_count": len(section_plot_artifacts),
                "summary_table_row_count": len(
                    _section_rows(
                        aggregation_summary,
                        section_id=section_id,
                        rows_key="summary_table_rows",
                    )
                ),
                "table_artifact_ids": [
                    str(item["artifact_id"]) for item in section_table_artifacts
                ],
                "plot_artifact_ids": [
                    str(item["artifact_id"]) for item in section_plot_artifacts
                ],
            }
        )

    summary = {
        "format_version": EXPERIMENT_SUITE_REVIEW_REPORT_FORMAT,
        "suite_reference": _suite_reference(
            result_index=result_index,
            package_metadata_path=package_metadata_path if package_metadata is not None else None,
        ),
        "package_reference": {
            "package_metadata_path": (
                None if package_metadata is None else str(package_metadata_path.resolve())
            ),
            "result_index_path": (
                None
                if package_metadata is None
                else str(
                    Path(
                        package_metadata["artifacts"]["result_index"]["path"]
                    ).resolve()
                )
            ),
            "inventory_report_path": (
                None
                if package_metadata is None
                else str(
                    Path(
                        package_metadata["artifacts"]["inventory_report"]["path"]
                    ).resolve()
                )
            ),
        },
        "aggregation_reference": {
            "output_directory": str(Path(aggregation_result["output_directory"]).resolve()),
            "summary_path": str(Path(aggregation_result["summary_path"]).resolve()),
            "table_dimension_ids": list(aggregation_result["table_dimension_ids"]),
            "row_counts": dict(aggregation_result["row_counts"]),
        },
        "report_layout": {
            "output_directory": str(paths.review_directory),
            "index_path": str(paths.index_path),
            "summary_path": str(paths.summary_path),
            "artifact_catalog_path": str(paths.artifact_catalog_path),
            "report_file_url": paths.index_path.as_uri(),
        },
        "summary": {
            "section_count": len(sections),
            "table_artifact_count": len(table_artifacts),
            "plot_artifact_count": len(plot_artifacts),
            "review_artifact_count": len(review_artifacts),
            "linked_package_artifact_count": len(linked_package_artifacts),
        },
        "sections": sections,
        "viewer_open_hint": (
            "Open the generated suite review index.html directly in your browser; "
            "no local server is required."
        ),
    }
    paths.index_path.write_text(
        _render_review_html(
            summary=summary,
            sections=sections,
            table_artifacts=table_artifacts,
            plot_artifacts=plot_artifacts,
            review_artifacts=review_artifacts,
            linked_package_artifacts=linked_package_artifacts,
            section_rows_preview=section_rows_preview,
        ),
        encoding="utf-8",
    )
    write_json(summary, paths.summary_path)
    return summary


def _build_table_artifacts(
    *,
    section_id: str,
    section_payload: Mapping[str, Any],
    aggregation_result: Mapping[str, Any],
    review_directory: Path,
    paired_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for spec in _TABLE_EXPORT_SPECS[section_id]:
        path = Path(aggregation_result[spec["workflow_key"]]).resolve()
        rows = _section_rows(
            {"section": section_payload},
            section_id="section",
            rows_key=spec["rows_key"],
        )
        traceability = _collect_traceability(rows, paired_rows_by_id=paired_rows_by_id)
        artifacts.append(
            {
                "artifact_id": spec["artifact_id"],
                "display_name": spec["display_name"],
                "section_id": section_id,
                "category": SUMMARY_TABLE_CATEGORY,
                "artifact_role_id": SUMMARY_TABLE_ROLE_ID,
                "source_kind": SUMMARY_TABLE_SOURCE_KIND,
                "artifact_scope": SUMMARY_OUTPUT_ARTIFACT_SCOPE,
                "table_kind": spec["table_kind"],
                "path": str(path),
                "relative_path": _relative_path(path, start=review_directory),
                "row_count": len(rows),
                "traceability": traceability,
            }
        )
    return artifacts


def _build_plot_artifacts(
    *,
    section_id: str,
    section_payload: Mapping[str, Any],
    review_paths: ExperimentSuiteReviewPaths,
    review_directory: Path,
    summary_table_artifact: Mapping[str, Any] | None,
    paired_rows_by_id: Mapping[str, Mapping[str, Any]],
    table_dimension_ids: Sequence[str],
) -> list[dict[str, Any]]:
    grouped_rows = _group_plot_rows(section_id=section_id, section_payload=section_payload)
    artifacts: list[dict[str, Any]] = []
    for plot_key, rows in grouped_rows:
        plot_id = _plot_artifact_id(section_id=section_id, plot_key=plot_key)
        plot_title, plot_subtitle, value_key, value_label = _plot_labels(
            section_id=section_id,
            plot_key=plot_key,
        )
        plot_dir = ensure_dir(review_paths.plot_directory / section_id)
        metadata_dir = ensure_dir(review_paths.metadata_directory / section_id)
        svg_path = (plot_dir / f"{plot_id}.svg").resolve()
        metadata_path = (metadata_dir / f"{plot_id}.json").resolve()
        plot_payload = _plot_payload(
            rows=rows,
            value_key=value_key,
        )
        svg_path.write_text(
            _render_grouped_bar_svg(
                title=plot_title,
                subtitle=plot_subtitle,
                section_id=section_id,
                y_label=value_label,
                x_labels=plot_payload["x_labels"],
                series=plot_payload["series"],
            ),
            encoding="utf-8",
        )
        traceability = _collect_traceability(rows, paired_rows_by_id=paired_rows_by_id)
        metadata = {
            "artifact_id": plot_id,
            "display_name": plot_title,
            "subtitle": plot_subtitle,
            "section_id": section_id,
            "table_dimension_ids": list(table_dimension_ids),
            "source_table_artifact_id": (
                None
                if summary_table_artifact is None
                else str(summary_table_artifact["artifact_id"])
            ),
            "source_table_path": (
                None if summary_table_artifact is None else str(summary_table_artifact["path"])
            ),
            "relative_source_table_path": (
                None
                if summary_table_artifact is None
                else _relative_path(
                    Path(summary_table_artifact["path"]).resolve(),
                    start=review_directory,
                )
            ),
            "value_key": value_key,
            "value_label": value_label,
            "x_axis_labels": list(plot_payload["x_labels"]),
            "series_labels": [str(item["label"]) for item in plot_payload["series"]],
            "source_row_count": len(rows),
            "traceability": traceability,
        }
        write_json(metadata, metadata_path)
        artifacts.append(
            {
                "artifact_id": plot_id,
                "display_name": plot_title,
                "subtitle": plot_subtitle,
                "section_id": section_id,
                "category": COMPARISON_PLOT_CATEGORY,
                "artifact_role_id": COMPARISON_PLOT_ROLE_ID,
                "source_kind": COMPARISON_PLOT_SOURCE_KIND,
                "artifact_scope": PLOT_OUTPUT_ARTIFACT_SCOPE,
                "path": str(svg_path),
                "relative_path": _relative_path(svg_path, start=review_directory),
                "metadata_path": str(metadata_path),
                "relative_metadata_path": _relative_path(metadata_path, start=review_directory),
                "source_table_artifact_id": (
                    None
                    if summary_table_artifact is None
                    else str(summary_table_artifact["artifact_id"])
                ),
                "source_table_path": (
                    None if summary_table_artifact is None else str(summary_table_artifact["path"])
                ),
                "relative_source_table_path": (
                    None
                    if summary_table_artifact is None
                    else _relative_path(
                        Path(summary_table_artifact["path"]).resolve(),
                        start=review_directory,
                    )
                ),
                "source_row_count": len(rows),
                "x_axis_labels": list(plot_payload["x_labels"]),
                "series_labels": [str(item["label"]) for item in plot_payload["series"]],
                "traceability": traceability,
            }
        )
    return artifacts


def _build_linked_package_artifacts(
    *,
    package_metadata: Mapping[str, Any] | None,
    package_metadata_path: Path,
    result_index: Mapping[str, Any],
    review_directory: Path,
) -> list[dict[str, Any]]:
    linked = [
        {
            "artifact_id": "suite_plan",
            "display_name": "Suite Plan",
            "path": str(Path(result_index["suite_plan_path"]).resolve()),
            "relative_path": _relative_path(
                Path(result_index["suite_plan_path"]).resolve(),
                start=review_directory,
            ),
        },
        {
            "artifact_id": "suite_metadata",
            "display_name": "Suite Metadata",
            "path": str(Path(result_index["suite_metadata_path"]).resolve()),
            "relative_path": _relative_path(
                Path(result_index["suite_metadata_path"]).resolve(),
                start=review_directory,
            ),
        },
        {
            "artifact_id": "suite_state",
            "display_name": "Suite Execution State",
            "path": str(Path(result_index["state_path"]).resolve()),
            "relative_path": _relative_path(
                Path(result_index["state_path"]).resolve(),
                start=review_directory,
            ),
        },
    ]
    if package_metadata is None:
        linked.sort(key=lambda item: str(item["artifact_id"]))
        return linked
    linked.extend(
        [
            {
                "artifact_id": "suite_package_metadata",
                "display_name": "Suite Package Metadata",
                "path": str(package_metadata_path.resolve()),
                "relative_path": _relative_path(package_metadata_path.resolve(), start=review_directory),
            },
            {
                "artifact_id": "suite_inventory_report",
                "display_name": "Suite Inventory Report",
                "path": str(
                    Path(package_metadata["artifacts"]["inventory_report"]["path"]).resolve()
                ),
                "relative_path": _relative_path(
                    Path(package_metadata["artifacts"]["inventory_report"]["path"]).resolve(),
                    start=review_directory,
                ),
            },
            {
                "artifact_id": "suite_result_index_json",
                "display_name": "Suite Result Index JSON",
                "path": str(
                    Path(package_metadata["artifacts"]["result_index"]["path"]).resolve()
                ),
                "relative_path": _relative_path(
                    Path(package_metadata["artifacts"]["result_index"]["path"]).resolve(),
                    start=review_directory,
                ),
            },
        ]
    )
    linked.sort(key=lambda item: str(item["artifact_id"]))
    return linked


def _build_review_artifacts(
    paths: ExperimentSuiteReviewPaths,
    *,
    review_directory: Path,
) -> list[dict[str, Any]]:
    return [
        {
            "artifact_id": REVIEW_ARTIFACT_CATALOG_ID,
            "display_name": "Suite Review Artifact Catalog",
            "category": REVIEW_ARTIFACT_CATEGORY,
            "artifact_role_id": REVIEW_ARTIFACT_ROLE_ID,
            "source_kind": REVIEW_ARTIFACT_SOURCE_KIND,
            "artifact_scope": REVIEW_OUTPUT_ARTIFACT_SCOPE,
            "path": str(paths.artifact_catalog_path),
            "relative_path": _relative_path(paths.artifact_catalog_path, start=review_directory),
        },
        {
            "artifact_id": REVIEW_INDEX_ARTIFACT_ID,
            "display_name": "Suite Review Index",
            "category": REVIEW_ARTIFACT_CATEGORY,
            "artifact_role_id": REVIEW_ARTIFACT_ROLE_ID,
            "source_kind": REVIEW_ARTIFACT_SOURCE_KIND,
            "artifact_scope": REVIEW_OUTPUT_ARTIFACT_SCOPE,
            "path": str(paths.index_path),
            "relative_path": _relative_path(paths.index_path, start=review_directory),
        },
        {
            "artifact_id": REVIEW_SUMMARY_ARTIFACT_ID,
            "display_name": "Suite Review Summary JSON",
            "category": REVIEW_ARTIFACT_CATEGORY,
            "artifact_role_id": REVIEW_ARTIFACT_ROLE_ID,
            "source_kind": REVIEW_ARTIFACT_SOURCE_KIND,
            "artifact_scope": REVIEW_OUTPUT_ARTIFACT_SCOPE,
            "path": str(paths.summary_path),
            "relative_path": _relative_path(paths.summary_path, start=review_directory),
        },
    ]


def _suite_reference(
    *,
    result_index: Mapping[str, Any],
    package_metadata_path: Path | None,
) -> dict[str, Any]:
    return {
        "suite_id": str(result_index["suite_id"]),
        "suite_label": str(result_index["suite_label"]),
        "suite_spec_hash": str(result_index["suite_spec_hash"]),
        "suite_root": str(Path(result_index["suite_root"]).resolve()),
        "suite_plan_path": str(Path(result_index["suite_plan_path"]).resolve()),
        "suite_metadata_path": str(Path(result_index["suite_metadata_path"]).resolve()),
        "package_metadata_path": (
            None if package_metadata_path is None else str(package_metadata_path.resolve())
        ),
    }


def _section_rows(
    aggregation_summary: Mapping[str, Any],
    *,
    section_id: str,
    rows_key: str,
) -> list[dict[str, Any]]:
    section_payload = aggregation_summary.get(section_id)
    if not isinstance(section_payload, Mapping):
        return []
    rows = section_payload.get(rows_key, [])
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return []
    return [dict(item) for item in rows if isinstance(item, Mapping)]


def _collect_traceability(
    rows: Sequence[Mapping[str, Any]],
    *,
    paired_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    suite_cell_ids: set[str] = set()
    base_suite_cell_ids: set[str] = set()
    ablation_suite_cell_ids: set[str] = set()
    source_pairing_ids: set[str] = set()
    source_bundle_ids: set[str] = set()
    source_paths: set[str] = set()
    ablation_keys: set[str] = set()
    metric_ids: set[str] = set()
    dimension_slice_keys: set[str] = set()

    for row in rows:
        _add_if_present(suite_cell_ids, row.get("suite_cell_id"))
        _add_if_present(base_suite_cell_ids, row.get("base_suite_cell_id"))
        _add_if_present(ablation_suite_cell_ids, row.get("ablation_suite_cell_id"))
        _add_if_present(source_pairing_ids, row.get("pairing_id"))
        _add_if_present(ablation_keys, row.get("ablation_key"))
        _add_if_present(metric_ids, row.get("metric_id"))
        _add_if_present(dimension_slice_keys, row.get("dimension_slice_key"))

        for suite_cell_id in row.get("base_suite_cell_ids", []):
            _add_if_present(base_suite_cell_ids, suite_cell_id)
        for suite_cell_id in row.get("ablation_suite_cell_ids", []):
            _add_if_present(ablation_suite_cell_ids, suite_cell_id)
        for pairing_id in row.get("source_pairing_ids", []):
            _add_if_present(source_pairing_ids, pairing_id)
        for field_name in (
            "analysis_bundle_id",
            "validation_bundle_id",
            "base_source_bundle_id",
            "ablation_source_bundle_id",
        ):
            _add_if_present(source_bundle_ids, row.get(field_name))
        for field_name in (
            "analysis_summary_path",
            "validation_summary_path",
            "validation_finding_rows_path",
            "base_source_path",
            "ablation_source_path",
            "base_findings_path",
            "ablation_findings_path",
        ):
            _add_if_present(source_paths, row.get(field_name))

    for pairing_id in sorted(source_pairing_ids):
        paired_row = paired_rows_by_id.get(pairing_id)
        if paired_row is None:
            continue
        _add_if_present(base_suite_cell_ids, paired_row.get("base_suite_cell_id"))
        _add_if_present(ablation_suite_cell_ids, paired_row.get("ablation_suite_cell_id"))
        for field_name in (
            "base_source_bundle_id",
            "ablation_source_bundle_id",
        ):
            _add_if_present(source_bundle_ids, paired_row.get(field_name))
        for field_name in (
            "base_source_path",
            "ablation_source_path",
            "base_findings_path",
            "ablation_findings_path",
        ):
            _add_if_present(source_paths, paired_row.get(field_name))

    suite_cell_ids.update(base_suite_cell_ids)
    suite_cell_ids.update(ablation_suite_cell_ids)
    return {
        "suite_cell_ids": sorted(suite_cell_ids),
        "base_suite_cell_ids": sorted(base_suite_cell_ids),
        "ablation_suite_cell_ids": sorted(ablation_suite_cell_ids),
        "source_pairing_ids": sorted(source_pairing_ids),
        "source_bundle_ids": sorted(source_bundle_ids),
        "source_paths": sorted(source_paths),
        "ablation_keys": sorted(ablation_keys),
        "metric_ids": sorted(metric_ids),
        "dimension_slice_keys": sorted(dimension_slice_keys),
    }


def _group_plot_rows(
    *,
    section_id: str,
    section_payload: Mapping[str, Any],
) -> list[tuple[tuple[str, ...], list[dict[str, Any]]]]:
    rows = _section_rows(
        {"section": section_payload},
        section_id="section",
        rows_key="summary_table_rows",
    )
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    if section_id == SHARED_COMPARISON_SECTION_ID:
        for row in rows:
            grouped[
                (
                    str(row["group_id"]),
                    str(row["metric_id"]),
                    str(row["readout_id"]),
                    str(row["window_id"]),
                    str(row["statistic"]),
                )
            ].append(dict(row))
    elif section_id == WAVE_ONLY_DIAGNOSTICS_SECTION_ID:
        for row in rows:
            grouped[
                (
                    str(row["arm_id"]),
                    str(row["metric_id"]),
                )
            ].append(dict(row))
    elif section_id == VALIDATION_FINDINGS_SECTION_ID and rows:
        grouped[("finding_count_delta",)] = [dict(row) for row in rows]
    return [
        (key, sorted(items, key=lambda row: (str(row["dimension_slice_key"]), str(row["ablation_key"]))))
        for key, items in sorted(grouped.items())
    ]


def _plot_artifact_id(*, section_id: str, plot_key: Sequence[str]) -> str:
    joined = "__".join([section_id, *[str(item) for item in plot_key]])
    return _normalize_identifier(joined, field_name="plot_artifact_id")


def _plot_labels(
    *,
    section_id: str,
    plot_key: Sequence[str],
) -> tuple[str, str, str, str]:
    if section_id == SHARED_COMPARISON_SECTION_ID:
        group_id, metric_id, readout_id, window_id, statistic = plot_key
        return (
            f"Shared Comparison: {group_id} / {metric_id}",
            f"{readout_id} / {window_id} / {statistic}",
            "delta_mean",
            "Delta Mean",
        )
    if section_id == WAVE_ONLY_DIAGNOSTICS_SECTION_ID:
        arm_id, metric_id = plot_key
        return (
            f"Wave Diagnostics: {arm_id} / {metric_id}",
            "Across ablations and sweep slices",
            "delta_mean",
            "Delta Mean",
        )
    return (
        "Validation Findings",
        "Finding-count delta across ablations and sweep slices",
        "finding_count_delta",
        "Finding Count Delta",
    )


def _plot_payload(
    *,
    rows: Sequence[Mapping[str, Any]],
    value_key: str,
) -> dict[str, Any]:
    x_labels = sorted({str(row["dimension_slice_key"]) for row in rows})
    series_labels = sorted({str(row["ablation_key"]) for row in rows})
    value_lookup = {
        (str(row["dimension_slice_key"]), str(row["ablation_key"])): _plot_value(
            row=row,
            value_key=value_key,
        )
        for row in rows
    }
    series = []
    for series_label in series_labels:
        series.append(
            {
                "label": series_label,
                "values": [
                    value_lookup.get((x_label, series_label)) for x_label in x_labels
                ],
            }
        )
    return {
        "x_labels": x_labels,
        "series": series,
    }


def _plot_value(*, row: Mapping[str, Any], value_key: str) -> float | None:
    if value_key == "delta_mean":
        statistics = row.get("delta_mean_statistics")
        if isinstance(statistics, Mapping) and statistics.get("mean") is not None:
            return float(statistics["mean"])
        if row.get("delta_mean") is not None:
            return float(row["delta_mean"])
        return None
    if value_key == "finding_count_delta":
        statistics = row.get("finding_count_delta_statistics")
        if isinstance(statistics, Mapping) and statistics.get("mean") is not None:
            return float(statistics["mean"])
        if row.get("finding_count_delta") is not None:
            return float(row["finding_count_delta"])
        return None
    raise ValueError(f"Unsupported plot value_key {value_key!r}.")


def _render_grouped_bar_svg(
    *,
    title: str,
    subtitle: str,
    section_id: str,
    y_label: str,
    x_labels: Sequence[str],
    series: Sequence[Mapping[str, Any]],
) -> str:
    width = max(820, 220 + (len(x_labels) * 150))
    height = 520
    left = 92
    right = 32
    top = 86
    bottom = 118
    plot_width = width - left - right
    plot_height = height - top - bottom
    all_values = [
        float(value)
        for item in series
        for value in item["values"]
        if value is not None
    ]
    y_min, y_max = _value_bounds(all_values)
    grid_values = _grid_values(y_min=y_min, y_max=y_max, count=5)
    group_width = plot_width / max(len(x_labels), 1)
    series_count = max(len(series), 1)
    bar_band = group_width * 0.72
    bar_width = min(48.0, (bar_band / max(series_count, 1)) * 0.78)
    inner_gap = 8.0
    section_accent = _SECTION_DISPLAY[section_id]["accent"]

    def y_coord(value: float) -> float:
        if math.isclose(y_max, y_min):
            return top + (plot_height / 2.0)
        return top + ((y_max - value) / (y_max - y_min)) * plot_height

    zero_y = y_coord(0.0)
    parts = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        (
            f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" "
            f"height=\"{height}\" viewBox=\"0 0 {width} {height}\" role=\"img\" "
            f"aria-labelledby=\"title desc\">"
        ),
        f"<title id=\"title\">{html.escape(title)}</title>",
        f"<desc id=\"desc\">{html.escape(subtitle)}</desc>",
        "<style>",
        ".bg { fill: #fbf8f2; }",
        ".frame { fill: #fffdf8; stroke: #d8cfbf; stroke-width: 1; }",
        ".grid { stroke: #e7ddcf; stroke-width: 1; }",
        ".axis { stroke: #6d6257; stroke-width: 1.25; }",
        ".tick { fill: #5e544a; font: 12px Georgia, 'Times New Roman', serif; }",
        ".title { fill: #1d211f; font: 700 24px Georgia, 'Times New Roman', serif; }",
        ".subtitle { fill: #5d5b54; font: 14px Georgia, 'Times New Roman', serif; }",
        ".legend { fill: #2b302e; font: 12px Georgia, 'Times New Roman', serif; }",
        ".ylabel { fill: #2b302e; font: 13px Georgia, 'Times New Roman', serif; }",
        ".value { fill: #2d2a26; font: 11px Georgia, 'Times New Roman', serif; }",
        "</style>",
        f"<rect class=\"bg\" x=\"0\" y=\"0\" width=\"{width}\" height=\"{height}\" />",
        (
            f"<rect class=\"frame\" x=\"18\" y=\"18\" width=\"{width - 36}\" "
            f"height=\"{height - 36}\" rx=\"18\" />"
        ),
        f"<text class=\"title\" x=\"{left}\" y=\"44\">{html.escape(title)}</text>",
        f"<text class=\"subtitle\" x=\"{left}\" y=\"66\">{html.escape(subtitle)}</text>",
        (
            f"<text class=\"ylabel\" x=\"28\" y=\"{top - 18}\" "
            f"fill=\"{section_accent}\">{html.escape(y_label)}</text>"
        ),
    ]
    for grid_value in grid_values:
        y = y_coord(grid_value)
        parts.append(
            f"<line class=\"grid\" x1=\"{left}\" y1=\"{y:.2f}\" x2=\"{width - right}\" y2=\"{y:.2f}\" />"
        )
        parts.append(
            f"<text class=\"tick\" x=\"{left - 10}\" y=\"{y + 4:.2f}\" text-anchor=\"end\">{_format_value(grid_value)}</text>"
        )
    parts.append(
        f"<line class=\"axis\" x1=\"{left}\" y1=\"{zero_y:.2f}\" x2=\"{width - right}\" y2=\"{zero_y:.2f}\" />"
    )
    parts.append(
        f"<line class=\"axis\" x1=\"{left}\" y1=\"{top}\" x2=\"{left}\" y2=\"{top + plot_height}\" />"
    )

    legend_x = left
    legend_y = top + plot_height + 56
    for index, item in enumerate(series):
        color = _PLOT_PALETTE[index % len(_PLOT_PALETTE)]
        entry_x = legend_x + (index * 170)
        parts.append(
            f"<rect x=\"{entry_x}\" y=\"{legend_y - 11}\" width=\"16\" height=\"16\" rx=\"3\" fill=\"{color}\" />"
        )
        parts.append(
            f"<text class=\"legend\" x=\"{entry_x + 24}\" y=\"{legend_y + 2}\">{html.escape(str(item['label']))}</text>"
        )

    for x_index, x_label in enumerate(x_labels):
        group_left = left + (x_index * group_width) + ((group_width - bar_band) / 2.0)
        center_x = left + (x_index * group_width) + (group_width / 2.0)
        parts.append(
            f"<text class=\"tick\" x=\"{center_x:.2f}\" y=\"{top + plot_height + 70}\" text-anchor=\"end\" transform=\"rotate(-24 {center_x:.2f} {top + plot_height + 70})\">{html.escape(x_label)}</text>"
        )
        for series_index, item in enumerate(series):
            value = item["values"][x_index]
            if value is None:
                continue
            color = _PLOT_PALETTE[series_index % len(_PLOT_PALETTE)]
            x = group_left + (series_index * ((bar_band - inner_gap) / max(series_count, 1)))
            baseline = y_coord(0.0)
            top_y = y_coord(float(value))
            rect_y = min(baseline, top_y)
            rect_height = max(abs(baseline - top_y), 1.0)
            parts.append(
                (
                    f"<rect x=\"{x:.2f}\" y=\"{rect_y:.2f}\" width=\"{bar_width:.2f}\" "
                    f"height=\"{rect_height:.2f}\" rx=\"4\" fill=\"{color}\" opacity=\"0.92\" />"
                )
            )
            label_y = rect_y - 6 if value >= 0.0 else rect_y + rect_height + 14
            parts.append(
                f"<text class=\"value\" x=\"{x + (bar_width / 2.0):.2f}\" y=\"{label_y:.2f}\" text-anchor=\"middle\">{_format_value(value)}</text>"
            )

    parts.append("</svg>")
    return "\n".join(parts)


def _render_review_html(
    *,
    summary: Mapping[str, Any],
    sections: Sequence[Mapping[str, Any]],
    table_artifacts: Sequence[Mapping[str, Any]],
    plot_artifacts: Sequence[Mapping[str, Any]],
    review_artifacts: Sequence[Mapping[str, Any]],
    linked_package_artifacts: Sequence[Mapping[str, Any]],
    section_rows_preview: Mapping[str, Sequence[Mapping[str, Any]]],
) -> str:
    hero_facts = [
        ("Suite ID", summary["suite_reference"]["suite_id"]),
        ("Suite Label", summary["suite_reference"]["suite_label"]),
        ("Spec Hash", summary["suite_reference"]["suite_spec_hash"]),
        (
            "Table Dimensions",
            ", ".join(summary["aggregation_reference"]["table_dimension_ids"]),
        ),
        ("Table Exports", summary["summary"]["table_artifact_count"]),
        ("Comparison Plots", summary["summary"]["plot_artifact_count"]),
    ]
    section_nav = " ".join(
        [
            f"<a href=\"#{html.escape(str(item['section_id']))}\">{html.escape(str(item['display_name']))}</a>"
            for item in sections
        ]
    )
    return "\n".join(
        [
            "<!DOCTYPE html>",
            "<html lang=\"en\">",
            "<head>",
            "  <meta charset=\"utf-8\" />",
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />",
            "  <title>Milestone 15 Suite Review</title>",
            "  <style>",
            "    :root {",
            "      color-scheme: light;",
            "      --bg: #f7f2e8;",
            "      --card: #fffdf8;",
            "      --ink: #1f2522;",
            "      --muted: #5e625b;",
            "      --border: #d9d1c2;",
            "      --shared: #0f5c63;",
            "      --wave: #8d5b17;",
            "      --validation: #8b2f39;",
            "    }",
            "    * { box-sizing: border-box; }",
            "    body { margin: 0; font-family: Georgia, 'Times New Roman', serif; background: radial-gradient(circle at top left, #fefcf8 0%, var(--bg) 58%, #efe6d7 100%); color: var(--ink); }",
            "    main { max-width: 1220px; margin: 0 auto; padding: 28px 20px 44px; }",
            "    h1, h2, h3 { margin: 0; }",
            "    h1 { font-size: 2.4rem; line-height: 1.05; }",
            "    h2 { font-size: 1.35rem; margin-bottom: 10px; }",
            "    h3 { font-size: 1rem; }",
            "    p { margin: 0; line-height: 1.5; }",
            "    a { color: inherit; }",
            "    code { font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace; font-size: 0.92em; background: #f0eadf; padding: 0.06rem 0.28rem; border-radius: 0.32rem; }",
            "    .hero { padding: 24px; border-radius: 22px; border: 1px solid var(--border); background: linear-gradient(135deg, rgba(15,92,99,0.12), rgba(255,253,248,0.94) 58%); box-shadow: 0 18px 40px rgba(53, 46, 35, 0.08); }",
            "    .lede { margin-top: 12px; color: var(--muted); max-width: 80ch; }",
            "    .facts { margin-top: 18px; display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }",
            "    .fact { padding: 12px 14px; border-radius: 14px; border: 1px solid var(--border); background: rgba(255,255,255,0.76); }",
            "    .fact-label { display: block; text-transform: uppercase; letter-spacing: 0.06em; font-size: 0.78rem; color: var(--muted); margin-bottom: 4px; }",
            "    .fact-value { display: block; word-break: break-word; }",
            "    .nav { margin-top: 16px; display: flex; flex-wrap: wrap; gap: 10px; }",
            "    .nav a { text-decoration: none; padding: 8px 12px; border-radius: 999px; border: 1px solid var(--border); background: rgba(255,255,255,0.76); }",
            "    .panel { margin-top: 18px; padding: 20px; border-radius: 20px; border: 1px solid var(--border); background: var(--card); }",
            "    .section { margin-top: 24px; padding: 22px; border-radius: 20px; border: 1px solid var(--border); background: rgba(255,253,248,0.96); }",
            "    .section.shared { box-shadow: inset 0 0 0 1px rgba(15,92,99,0.08); }",
            "    .section.wave { box-shadow: inset 0 0 0 1px rgba(141,91,23,0.08); }",
            "    .section.validation { box-shadow: inset 0 0 0 1px rgba(139,47,57,0.08); }",
            "    .section-tag { display: inline-block; margin-bottom: 10px; padding: 6px 10px; border-radius: 999px; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; background: #f1ece2; color: var(--muted); }",
            "    .shared .section-tag { color: var(--shared); }",
            "    .wave .section-tag { color: var(--wave); }",
            "    .validation .section-tag { color: var(--validation); }",
            "    .meta-table, .preview-table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 0.94rem; }",
            "    th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid #eae1d4; vertical-align: top; }",
            "    th { color: var(--muted); font-size: 0.79rem; text-transform: uppercase; letter-spacing: 0.06em; }",
            "    .gallery { margin-top: 16px; display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }",
            "    .plot-card { padding: 14px; border-radius: 16px; border: 1px solid var(--border); background: #fff; }",
            "    .plot-card img { width: 100%; height: auto; border-radius: 12px; border: 1px solid #e7ddcf; background: #fff; }",
            "    .plot-meta { margin-top: 10px; color: var(--muted); font-size: 0.92rem; display: grid; gap: 4px; }",
            "    .artifact-links { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; }",
            "    .artifact-links a { text-decoration: none; padding: 7px 10px; border-radius: 999px; border: 1px solid var(--border); background: #faf6ee; }",
            "    .muted { color: var(--muted); }",
            "  </style>",
            "</head>",
            "<body>",
            "<main>",
            "  <section class=\"hero\">",
            "    <h1>Milestone 15 Suite Review</h1>",
            "    <p class=\"lede\">This static review surface is generated from the packaged suite inventory plus suite-level aggregation outputs. It does not reparse raw per-experiment directories. Shared comparisons, wave-only diagnostics, and validation findings remain visibly separated so reviewers can inspect fairness-critical content without mixing it with wave-specific or validation-only surfaces.</p>",
            "    <div class=\"facts\">",
            *[
                "      <div class=\"fact\"><span class=\"fact-label\">"
                + html.escape(str(label))
                + "</span><span class=\"fact-value\">"
                + html.escape(str(value))
                + "</span></div>"
                for label, value in hero_facts
            ],
            "    </div>",
            "    <div class=\"nav\">",
            f"      {section_nav}",
            "    </div>",
            "  </section>",
            _render_artifact_panel(
                title="Review Artifacts",
                artifacts=review_artifacts,
            ),
            _render_artifact_panel(
                title="Linked Package Anchors",
                artifacts=linked_package_artifacts,
            ),
            *[
                _render_section_html(
                    section=section,
                    table_artifacts=[
                        item
                        for item in table_artifacts
                        if str(item["section_id"]) == str(section["section_id"])
                    ],
                    plot_artifacts=[
                        item
                        for item in plot_artifacts
                        if str(item["section_id"]) == str(section["section_id"])
                    ],
                    preview_rows=section_rows_preview.get(str(section["section_id"]), []),
                )
                for section in sections
            ],
            "</main>",
            "</body>",
            "</html>",
        ]
    )


def _render_artifact_panel(
    *,
    title: str,
    artifacts: Sequence[Mapping[str, Any]],
) -> str:
    rows = []
    for artifact in artifacts:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(artifact['display_name']))}</td>"
            f"<td><a href=\"{html.escape(str(artifact['relative_path']))}\"><code>{html.escape(str(artifact['relative_path']))}</code></a></td>"
            "</tr>"
        )
    return (
        f"<section class=\"panel\"><h2>{html.escape(title)}</h2>"
        "<table class=\"meta-table\"><thead><tr><th>Artifact</th><th>Path</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></section>"
    )


def _render_section_html(
    *,
    section: Mapping[str, Any],
    table_artifacts: Sequence[Mapping[str, Any]],
    plot_artifacts: Sequence[Mapping[str, Any]],
    preview_rows: Sequence[Mapping[str, Any]],
) -> str:
    section_id = str(section["section_id"])
    display = _SECTION_DISPLAY[section_id]
    table_rows = "".join(
        [
            "<tr>"
            f"<td>{html.escape(str(item['display_name']))}</td>"
            f"<td>{int(item['row_count'])}</td>"
            f"<td><a href=\"{html.escape(str(item['relative_path']))}\"><code>{html.escape(str(item['relative_path']))}</code></a></td>"
            "</tr>"
            for item in table_artifacts
        ]
    )
    gallery = (
        "<p class=\"muted\">No comparison plots were generated for this section.</p>"
        if not plot_artifacts
        else "<div class=\"gallery\">"
        + "".join([_render_plot_card(item) for item in plot_artifacts])
        + "</div>"
    )
    return (
        f"<section id=\"{html.escape(section_id)}\" class=\"section {html.escape(display['html_class'])}\">"
        f"<span class=\"section-tag\">{html.escape(str(section['review_class']))}</span>"
        f"<h2>{html.escape(str(section['display_name']))}</h2>"
        f"<p class=\"muted\">{html.escape(str(section['description']))}</p>"
        "<table class=\"meta-table\"><thead><tr><th>Table Export</th><th>Rows</th><th>Path</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table>"
        "<h3 style=\"margin-top:18px;\">Comparison Plots</h3>"
        f"{gallery}"
        "<h3 style=\"margin-top:18px;\">Summary Table Preview</h3>"
        f"{_render_preview_table(section_id=section_id, rows=preview_rows)}"
        "</section>"
    )


def _render_plot_card(plot: Mapping[str, Any]) -> str:
    traceability = plot.get("traceability", {})
    return (
        "<article class=\"plot-card\">"
        f"<h3>{html.escape(str(plot['display_name']))}</h3>"
        f"<p class=\"muted\">{html.escape(str(plot.get('subtitle', '')))}</p>"
        f"<img src=\"{html.escape(str(plot['relative_path']))}\" alt=\"{html.escape(str(plot['display_name']))}\" />"
        "<div class=\"plot-meta\">"
        f"<div>Source rows: {int(plot['source_row_count'])}</div>"
        f"<div>Dimension slices: {len(plot.get('x_axis_labels', []))}</div>"
        f"<div>Ablations: {', '.join(html.escape(str(item)) for item in plot.get('series_labels', []))}</div>"
        f"<div>Source pairings: {len(traceability.get('source_pairing_ids', []))}</div>"
        "</div>"
        "<div class=\"artifact-links\">"
        f"<a href=\"{html.escape(str(plot['relative_path']))}\">Open Plot</a>"
        f"<a href=\"{html.escape(str(plot['relative_metadata_path']))}\">Plot Metadata</a>"
        + (
            ""
            if not plot.get("relative_source_table_path")
            else f"<a href=\"{html.escape(str(plot['relative_source_table_path']))}\">Summary Table CSV</a>"
        )
        + "</div>"
        "</article>"
    )


def _render_preview_table(
    *,
    section_id: str,
    rows: Sequence[Mapping[str, Any]],
) -> str:
    if not rows:
        return "<p class=\"muted\">No summary rows available.</p>"
    if section_id == VALIDATION_FINDINGS_SECTION_ID:
        headers = [
            ("dimension_slice_key", "Dimension Slice"),
            ("ablation_key", "Ablation"),
            ("worst_ablation_status", "Worst Status"),
            ("finding_count_delta_statistics", "Finding Delta Mean"),
            ("source_row_count", "Rows"),
        ]
    elif section_id == WAVE_ONLY_DIAGNOSTICS_SECTION_ID:
        headers = [
            ("dimension_slice_key", "Dimension Slice"),
            ("ablation_key", "Ablation"),
            ("arm_id", "Arm"),
            ("metric_id", "Metric"),
            ("delta_mean_statistics", "Delta Mean"),
            ("source_row_count", "Rows"),
        ]
    else:
        headers = [
            ("dimension_slice_key", "Dimension Slice"),
            ("ablation_key", "Ablation"),
            ("group_id", "Group"),
            ("metric_id", "Metric"),
            ("delta_mean_statistics", "Delta Mean"),
            ("source_row_count", "Rows"),
        ]
    head_html = "".join(
        [f"<th>{html.escape(label)}</th>" for _, label in headers]
    )
    body_rows = []
    for row in rows:
        cells = []
        for key, _ in headers:
            value = row.get(key)
            if isinstance(value, Mapping) and value.get("mean") is not None:
                cell_value = _format_value(float(value["mean"]))
            else:
                cell_value = "" if value is None else str(value)
            cells.append(f"<td>{html.escape(cell_value)}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return (
        "<table class=\"preview-table\"><thead><tr>"
        f"{head_html}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
    )


def _relative_path(path: Path, *, start: Path) -> str:
    return os.path.relpath(str(path.resolve()), start=str(start.resolve()))


def _resolve_report_record(
    record: Mapping[str, Any] | str | Path,
) -> tuple[Mapping[str, Any] | str | Path, Path | None, dict[str, Any] | None]:
    if isinstance(record, (str, Path)):
        resolved = Path(record).resolve()
        try:
            package_metadata = load_experiment_suite_package_metadata(resolved)
        except ValueError:
            return resolved, None, None
        return package_metadata, resolved, package_metadata
    return record, None, None


def _load_json_mapping(path: str | Path, *, field_name: str) -> dict[str, Any]:
    with Path(path).resolve().open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return dict(payload)


def _add_if_present(target: set[str], value: Any) -> None:
    if value is None:
        return
    text = str(value)
    if text:
        target.add(text)


def _value_bounds(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        return (-1.0, 1.0)
    min_value = min(values)
    max_value = max(values)
    if math.isclose(min_value, max_value):
        padding = max(abs(min_value) * 0.15, 1.0)
        return (min_value - padding, max_value + padding)
    padding = max((max_value - min_value) * 0.12, 0.2)
    return (min(min_value - padding, 0.0), max(max_value + padding, 0.0))


def _grid_values(*, y_min: float, y_max: float, count: int) -> list[float]:
    if count <= 1:
        return [y_min]
    step = (y_max - y_min) / float(count - 1)
    return [y_min + (step * index) for index in range(count)]


def _format_value(value: float) -> str:
    return f"{float(value):.{_PLOT_VALUE_DIGITS}f}"
