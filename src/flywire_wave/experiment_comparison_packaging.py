from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .experiment_analysis_contract import (
    ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
    COMPARISON_MATRICES_ARTIFACT_ID,
    EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID,
    NULL_TEST_TABLE_ARTIFACT_ID,
    OFFLINE_REPORT_INDEX_ARTIFACT_ID,
    OFFLINE_REPORT_SUMMARY_ARTIFACT_ID,
    TASK_SUMMARY_ROWS_ARTIFACT_ID,
    VISUALIZATION_CATALOG_ARTIFACT_ID,
    build_experiment_analysis_bundle_metadata,
    build_experiment_analysis_bundle_reference,
    discover_experiment_analysis_bundle_paths,
    write_experiment_analysis_bundle_metadata,
)
from .experiment_analysis_visualization import generate_experiment_analysis_report
from .experiment_comparison_common import (
    _normalize_analysis_plan,
    _normalize_bundle_set,
    _normalize_summary,
    _require_mapping,
)
from .io_utils import write_json
from .readout_analysis_contract import (
    ANALYSIS_UI_PAYLOAD_OUTPUT_ID,
    LATENCY_SHIFT_COMPARISON_OUTPUT_ID,
    MILESTONE_1_DECISION_PANEL_OUTPUT_ID,
    NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID,
    WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID,
    get_experiment_comparison_output_definition,
)
from .shared_readout_analysis import _rounded_float
from .wave_structure_analysis import (
    SURFACE_WAVE_PHASE_MAP_ARTIFACT_ID,
    SURFACE_WAVE_PHASE_MAP_FORMAT,
    SURFACE_WAVE_SUMMARY_ARTIFACT_ID,
)


def write_experiment_comparison_summary(
    summary: Mapping[str, Any],
    output_path: str | Path,
) -> Path:
    normalized_summary = _normalize_summary(summary)
    return write_json(normalized_summary, output_path)


def package_experiment_analysis_bundle(
    *,
    summary: Mapping[str, Any],
    analysis_plan: Mapping[str, Any],
    bundle_set: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_summary = _normalize_summary(summary)
    normalized_analysis_plan = _normalize_analysis_plan(analysis_plan)
    normalized_bundle_set = _normalize_bundle_set(bundle_set)
    bundle_metadata = build_experiment_analysis_bundle_metadata(
        analysis_plan=normalized_analysis_plan,
        bundle_set=normalized_bundle_set,
    )
    metadata_path = write_experiment_analysis_bundle_metadata(bundle_metadata)
    bundle_paths = discover_experiment_analysis_bundle_paths(bundle_metadata)

    write_experiment_comparison_summary(
        normalized_summary,
        bundle_paths[EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID],
    )

    phase_map_references = _collect_phase_map_references(normalized_bundle_set)
    task_summary_export = _build_task_summary_export(
        summary=normalized_summary,
        bundle_metadata=bundle_metadata,
    )
    null_test_table_export = _build_null_test_table_export(
        summary=normalized_summary,
        bundle_metadata=bundle_metadata,
    )
    comparison_matrix_export = _build_comparison_matrix_export(
        summary=normalized_summary,
        bundle_metadata=bundle_metadata,
    )
    visualization_catalog = _build_visualization_catalog_export(
        bundle_metadata=bundle_metadata,
        phase_map_references=phase_map_references,
    )
    analysis_ui_payload = _build_analysis_ui_payload(
        summary=normalized_summary,
        bundle_metadata=bundle_metadata,
        phase_map_references=phase_map_references,
    )

    write_json(task_summary_export, bundle_paths[TASK_SUMMARY_ROWS_ARTIFACT_ID])
    write_json(null_test_table_export, bundle_paths[NULL_TEST_TABLE_ARTIFACT_ID])
    write_json(comparison_matrix_export, bundle_paths[COMPARISON_MATRICES_ARTIFACT_ID])
    write_json(visualization_catalog, bundle_paths[VISUALIZATION_CATALOG_ARTIFACT_ID])
    write_json(analysis_ui_payload, bundle_paths[ANALYSIS_UI_PAYLOAD_ARTIFACT_ID])

    report_summary = generate_experiment_analysis_report(
        analysis_bundle_metadata_path=metadata_path,
    )

    return {
        "bundle_reference": build_experiment_analysis_bundle_reference(bundle_metadata),
        "metadata_path": str(metadata_path),
        "bundle_directory": str(bundle_metadata["bundle_layout"]["bundle_directory"]),
        "packaged_summary_path": str(
            bundle_paths[EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID]
        ),
        "task_summary_path": str(bundle_paths[TASK_SUMMARY_ROWS_ARTIFACT_ID]),
        "null_test_table_path": str(bundle_paths[NULL_TEST_TABLE_ARTIFACT_ID]),
        "comparison_matrices_path": str(bundle_paths[COMPARISON_MATRICES_ARTIFACT_ID]),
        "visualization_catalog_path": str(bundle_paths[VISUALIZATION_CATALOG_ARTIFACT_ID]),
        "analysis_ui_payload_path": str(bundle_paths[ANALYSIS_UI_PAYLOAD_ARTIFACT_ID]),
        "report_path": str(bundle_paths[OFFLINE_REPORT_INDEX_ARTIFACT_ID]),
        "report_summary_path": str(bundle_paths[OFFLINE_REPORT_SUMMARY_ARTIFACT_ID]),
        "report_file_url": str(report_summary["report_file_url"]),
        "artifact_inventory": _analysis_artifact_inventory(bundle_metadata),
    }


def _build_task_summary_export(
    *,
    summary: Mapping[str, Any],
    bundle_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "format_version": str(
            bundle_metadata["artifacts"][TASK_SUMMARY_ROWS_ARTIFACT_ID]["format"]
        ),
        "bundle_reference": build_experiment_analysis_bundle_reference(bundle_metadata),
        "manifest_reference": copy.deepcopy(dict(summary["manifest_reference"])),
        "rows": [copy.deepcopy(dict(item)) for item in summary["task_scores"]],
        "families": [
            copy.deepcopy(dict(item)) for item in summary["task_score_families"]
        ],
    }


def _build_null_test_table_export(
    *,
    summary: Mapping[str, Any],
    bundle_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for result in summary["null_test_results"]:
        metric_outcomes = [
            copy.deepcopy(dict(item)) for item in result.get("metric_outcomes", [])
        ]
        if not metric_outcomes:
            rows.append(
                {
                    "null_test_id": str(result["null_test_id"]),
                    "display_name": str(result["display_name"]),
                    "overall_status": str(result["status"]),
                    "metric_id": None,
                    "group_id": None,
                    "metric_status": "unavailable",
                    "details": {},
                }
            )
            continue
        for outcome in metric_outcomes:
            rows.append(
                {
                    "null_test_id": str(result["null_test_id"]),
                    "display_name": str(result["display_name"]),
                    "overall_status": str(result["status"]),
                    "metric_id": outcome.get("metric_id"),
                    "group_id": outcome.get("group_id"),
                    "metric_status": str(outcome.get("status", "unavailable")),
                    "details": {
                        key: copy.deepcopy(value)
                        for key, value in outcome.items()
                        if key not in {"metric_id", "group_id", "status"}
                    },
                }
            )
    rows.sort(
        key=lambda item: (
            str(item["null_test_id"]),
            "" if item["group_id"] is None else str(item["group_id"]),
            "" if item["metric_id"] is None else str(item["metric_id"]),
        )
    )
    return {
        "format_version": str(
            bundle_metadata["artifacts"][NULL_TEST_TABLE_ARTIFACT_ID]["format"]
        ),
        "bundle_reference": build_experiment_analysis_bundle_reference(bundle_metadata),
        "rows": rows,
        "null_test_results": [
            copy.deepcopy(dict(item)) for item in summary["null_test_results"]
        ],
    }


def _build_comparison_matrix_export(
    *,
    summary: Mapping[str, Any],
    bundle_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    matrices = []
    shared_task_matrix = _build_shared_task_rollup_matrix(summary["group_metric_rollups"])
    if shared_task_matrix is not None:
        matrices.append(shared_task_matrix)
    wave_matrix = _build_wave_rollup_matrix(summary["wave_metric_rollups"])
    if wave_matrix is not None:
        matrices.append(wave_matrix)
    return {
        "format_version": str(
            bundle_metadata["artifacts"][COMPARISON_MATRICES_ARTIFACT_ID]["format"]
        ),
        "bundle_reference": build_experiment_analysis_bundle_reference(bundle_metadata),
        "matrices": matrices,
    }


def _build_shared_task_rollup_matrix(
    group_metric_rollups: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    if not group_metric_rollups:
        return None
    row_ids = sorted({str(item["group_id"]) for item in group_metric_rollups})
    row_records = {
        str(item["group_id"]): {
            "group_id": str(item["group_id"]),
            "group_kind": str(item["group_kind"]),
            "comparison_semantics": str(item["comparison_semantics"]),
            "baseline_family": item.get("baseline_family"),
            "topology_condition": item.get("topology_condition"),
        }
        for item in group_metric_rollups
    }
    column_keys = sorted(
        {
            (
                str(item["metric_id"]),
                str(item["readout_id"]),
                str(item["window_id"]),
                str(item["statistic"]),
            )
            for item in group_metric_rollups
        }
    )
    column_ids = [
        "__".join(part if part not in {"", "none"} else "na" for part in key)
        for key in column_keys
    ]
    column_records = [
        {
            "column_id": column_id,
            "metric_id": key[0],
            "readout_id": key[1],
            "window_id": key[2],
            "statistic": key[3],
            "units": str(
                next(
                    item["units"]
                    for item in group_metric_rollups
                    if (
                        str(item["metric_id"]),
                        str(item["readout_id"]),
                        str(item["window_id"]),
                        str(item["statistic"]),
                    )
                    == key
                )
            ),
        }
        for column_id, key in zip(column_ids, column_keys, strict=True)
    ]
    values: list[list[float | None]] = []
    for row_id in row_ids:
        row_values: list[float | None] = []
        for key in column_keys:
            match = next(
                (
                    item
                    for item in group_metric_rollups
                    if str(item["group_id"]) == row_id
                    and (
                        str(item["metric_id"]),
                        str(item["readout_id"]),
                        str(item["window_id"]),
                        str(item["statistic"]),
                    )
                    == key
                ),
                None,
            )
            row_values.append(
                None
                if match is None
                else _rounded_float(float(match["summary_statistics"]["mean"]))
            )
        values.append(row_values)
    return {
        "matrix_id": "shared_task_rollup_matrix",
        "scope_label": "shared_comparison",
        "value_semantics": "group_metric_rollup.summary_statistics.mean",
        "row_axis": {
            "label": "comparison_group_id",
            "ids": row_ids,
            "records": [row_records[row_id] for row_id in row_ids],
        },
        "column_axis": {
            "label": "metric_context_id",
            "ids": column_ids,
            "records": column_records,
        },
        "values": values,
    }


def _build_wave_rollup_matrix(
    wave_metric_rollups: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    if not wave_metric_rollups:
        return None
    row_ids = sorted({str(item["arm_id"]) for item in wave_metric_rollups})
    column_ids = sorted({str(item["metric_id"]) for item in wave_metric_rollups})
    values: list[list[float | None]] = []
    for row_id in row_ids:
        row_values: list[float | None] = []
        for metric_id in column_ids:
            match = next(
                (
                    item
                    for item in wave_metric_rollups
                    if str(item["arm_id"]) == row_id
                    and str(item["metric_id"]) == metric_id
                ),
                None,
            )
            row_values.append(
                None
                if match is None
                else _rounded_float(float(match["summary_statistics"]["mean"]))
            )
        values.append(row_values)
    return {
        "matrix_id": "wave_diagnostic_rollup_matrix",
        "scope_label": "wave_only_diagnostics",
        "value_semantics": "wave_metric_rollup.summary_statistics.mean",
        "row_axis": {
            "label": "arm_id",
            "ids": row_ids,
            "records": [{"arm_id": row_id} for row_id in row_ids],
        },
        "column_axis": {
            "label": "metric_id",
            "ids": column_ids,
            "records": [
                {
                    "metric_id": metric_id,
                    "units": str(
                        next(
                            item["units"]
                            for item in wave_metric_rollups
                            if str(item["metric_id"]) == metric_id
                        )
                    ),
                }
                for metric_id in column_ids
            ],
        },
        "values": values,
    }


def _build_visualization_catalog_export(
    *,
    bundle_metadata: Mapping[str, Any],
    phase_map_references: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    report_ref = _artifact_ref(bundle_metadata, OFFLINE_REPORT_INDEX_ARTIFACT_ID)
    report_summary_ref = _artifact_ref(bundle_metadata, OFFLINE_REPORT_SUMMARY_ARTIFACT_ID)
    report_ref["summary_artifact_id"] = OFFLINE_REPORT_SUMMARY_ARTIFACT_ID
    report_ref["summary_path"] = report_summary_ref["path"]
    report_ref["report_file_url"] = Path(str(report_ref["path"])).resolve().as_uri()
    return {
        "format_version": str(
            bundle_metadata["artifacts"][VISUALIZATION_CATALOG_ARTIFACT_ID]["format"]
        ),
        "bundle_reference": build_experiment_analysis_bundle_reference(bundle_metadata),
        "offline_report": report_ref,
        "comparison_matrices_artifact_id": COMPARISON_MATRICES_ARTIFACT_ID,
        "analysis_ui_payload_artifact_id": ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
        "phase_map_references": [
            copy.deepcopy(dict(item)) for item in phase_map_references
        ],
    }


def _build_analysis_ui_payload(
    *,
    summary: Mapping[str, Any],
    bundle_metadata: Mapping[str, Any],
    phase_map_references: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    task_summary_cards = _build_task_summary_cards(summary["task_scores"])
    comparison_cards = _build_comparison_cards(
        output_summaries=summary["output_summaries"],
        bundle_metadata=bundle_metadata,
    )
    null_test_cards = _build_null_test_cards(summary["null_test_results"])
    diagnostic_cards = _build_wave_diagnostic_cards(summary["wave_metric_rollups"])
    offline_report_ref = _artifact_ref(bundle_metadata, OFFLINE_REPORT_INDEX_ARTIFACT_ID)
    offline_report_ref["summary_artifact_id"] = OFFLINE_REPORT_SUMMARY_ARTIFACT_ID
    offline_report_ref["summary_path"] = _artifact_ref(
        bundle_metadata,
        OFFLINE_REPORT_SUMMARY_ARTIFACT_ID,
    )["path"]
    offline_report_ref["report_file_url"] = Path(
        str(offline_report_ref["path"])
    ).resolve().as_uri()
    return {
        "format_version": str(
            bundle_metadata["artifacts"][ANALYSIS_UI_PAYLOAD_ARTIFACT_ID]["format"]
        ),
        "bundle_reference": build_experiment_analysis_bundle_reference(bundle_metadata),
        "manifest_reference": copy.deepcopy(dict(summary["manifest_reference"])),
        "artifact_inventory": _analysis_artifact_inventory(bundle_metadata),
        "task_summary_cards": task_summary_cards,
        "comparison_cards": comparison_cards,
        "analysis_visualizations": {
            "offline_report": offline_report_ref,
            "visualization_catalog_artifact_id": VISUALIZATION_CATALOG_ARTIFACT_ID,
            "comparison_matrices_artifact_id": COMPARISON_MATRICES_ARTIFACT_ID,
            "phase_map_reference_count": len(phase_map_references),
        },
        "shared_comparison": {
            "task_summary_cards": [
                copy.deepcopy(dict(item))
                for item in task_summary_cards
                if str(item["scope_label"]) == "shared_comparison"
            ],
            "comparison_cards": [
                copy.deepcopy(dict(item))
                for item in comparison_cards
                if str(item["scope_label"]) == "shared_comparison"
            ],
            "null_test_cards": null_test_cards,
            "milestone_1_decision_panel": copy.deepcopy(
                dict(summary["milestone_1_decision_panel"])
            ),
        },
        "wave_only_diagnostics": {
            "comparison_cards": [
                copy.deepcopy(dict(item))
                for item in comparison_cards
                if str(item["scope_label"]) == "wave_only_diagnostics"
            ],
            "diagnostic_cards": diagnostic_cards,
            "phase_map_references": [
                copy.deepcopy(dict(item)) for item in phase_map_references
            ],
        },
        "mixed_scope": {
            "comparison_cards": [
                copy.deepcopy(dict(item))
                for item in comparison_cards
                if str(item["scope_label"]) == "mixed_scope"
            ]
        },
    }


def _build_task_summary_cards(
    task_scores: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    cards = [
        {
            "card_id": str(item["score_id"]),
            "requested_metric_id": str(item["requested_metric_id"]),
            "group_id": str(item["group_id"]),
            "recipe_kind": str(item["recipe_kind"]),
            "value": item["value"],
            "units": str(item["units"]),
            "effect_direction": str(item["effect_direction"]),
            "scope_label": "shared_comparison",
        }
        for item in task_scores
    ]
    cards.sort(key=lambda item: (str(item["requested_metric_id"]), str(item["group_id"])))
    return cards


def _build_comparison_cards(
    *,
    output_summaries: Sequence[Mapping[str, Any]],
    bundle_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for output_summary in output_summaries:
        output_id = str(output_summary["output_id"])
        if output_id == ANALYSIS_UI_PAYLOAD_OUTPUT_ID:
            continue
        definition = get_experiment_comparison_output_definition(output_id)
        cards.append(
            {
                "output_id": output_id,
                "display_name": str(definition["display_name"]),
                "output_kind": str(definition["output_kind"]),
                "fairness_mode": str(definition["fairness_mode"]),
                "scope_label": _scope_label_from_fairness_mode(
                    str(definition["fairness_mode"])
                ),
                "artifact_refs": _comparison_card_artifact_refs(
                    output_id=output_id,
                    bundle_metadata=bundle_metadata,
                ),
                "summary": _comparison_card_summary(output_summary),
            }
        )
    cards.sort(key=lambda item: str(item["output_id"]))
    return cards


def _build_null_test_cards(
    null_test_results: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    cards = [
        {
            "null_test_id": str(item["null_test_id"]),
            "display_name": str(item["display_name"]),
            "status": str(item["status"]),
            "pass_criterion": str(item["pass_criterion"]),
            "metric_outcome_count": len(item.get("metric_outcomes", [])),
        }
        for item in null_test_results
    ]
    cards.sort(key=lambda item: str(item["null_test_id"]))
    return cards


def _build_wave_diagnostic_cards(
    wave_metric_rollups: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    cards = [
        {
            "card_id": f"{item['arm_id']}__{item['metric_id']}",
            "arm_id": str(item["arm_id"]),
            "metric_id": str(item["metric_id"]),
            "mean_value": item["summary_statistics"]["mean"],
            "units": str(item["units"]),
            "seed_count": int(item["seed_count"]),
            "scope_label": "wave_only_diagnostics",
        }
        for item in wave_metric_rollups
    ]
    cards.sort(key=lambda item: (str(item["arm_id"]), str(item["metric_id"])))
    return cards


def _comparison_card_summary(output_summary: Mapping[str, Any]) -> dict[str, Any]:
    output_id = str(output_summary["output_id"])
    if output_id in {
        NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID,
        LATENCY_SHIFT_COMPARISON_OUTPUT_ID,
    }:
        metric_rollups = [
            copy.deepcopy(dict(item)) for item in output_summary.get("metric_rollups", [])
        ]
        return {
            "metric_rollup_count": len(metric_rollups),
            "group_ids": sorted({str(item["group_id"]) for item in metric_rollups}),
            "matrix_id": "shared_task_rollup_matrix",
        }
    if output_id == WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID:
        wave_rollups = [
            copy.deepcopy(dict(item))
            for item in output_summary.get("wave_metric_rollups", [])
        ]
        return {
            "wave_metric_rollup_count": len(wave_rollups),
            "metric_ids": sorted({str(item["metric_id"]) for item in wave_rollups}),
            "matrix_id": "wave_diagnostic_rollup_matrix",
        }
    if output_id == MILESTONE_1_DECISION_PANEL_OUTPUT_ID:
        return {
            "overall_status": str(output_summary.get("overall_status", "unknown")),
            "decision_item_statuses": [
                str(item.get("status", "unknown"))
                for item in output_summary.get("decision_items", [])
                if isinstance(item, Mapping)
            ],
        }
    return {
        "available_keys": sorted(str(key) for key in output_summary.keys()),
    }


def _comparison_card_artifact_refs(
    *,
    output_id: str,
    bundle_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    refs = [_artifact_ref(bundle_metadata, EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID)]
    if output_id in {
        NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID,
        LATENCY_SHIFT_COMPARISON_OUTPUT_ID,
        WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID,
    }:
        refs.append(_artifact_ref(bundle_metadata, COMPARISON_MATRICES_ARTIFACT_ID))
    if output_id == WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID:
        refs.append(_artifact_ref(bundle_metadata, VISUALIZATION_CATALOG_ARTIFACT_ID))
    return refs


def _analysis_artifact_inventory(
    bundle_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    inventory = []
    for artifact_id, artifact in sorted(bundle_metadata["artifacts"].items()):
        inventory.append(
            {
                "artifact_id": str(artifact_id),
                "path": str(artifact["path"]),
                "format": str(artifact["format"]),
                "artifact_scope": str(artifact["artifact_scope"]),
                "description": str(artifact["description"]),
            }
        )
    return inventory


def _artifact_ref(
    bundle_metadata: Mapping[str, Any],
    artifact_id: str,
) -> dict[str, Any]:
    artifact = _require_mapping(
        bundle_metadata["artifacts"].get(artifact_id),
        field_name=f"bundle_metadata.artifacts[{artifact_id}]",
    )
    return {
        "artifact_id": str(artifact_id),
        "path": str(artifact["path"]),
        "format": str(artifact["format"]),
        "artifact_scope": str(artifact["artifact_scope"]),
    }


def _scope_label_from_fairness_mode(fairness_mode: str) -> str:
    if fairness_mode == "shared_readout_only":
        return "shared_comparison"
    if fairness_mode == "wave_extension_allowed":
        return "wave_only_diagnostics"
    return "mixed_scope"


def _collect_phase_map_references(
    bundle_set: Mapping[str, Any],
) -> list[dict[str, Any]]:
    references = []
    for record in bundle_set["bundle_records"]:
        bundle_metadata = _require_mapping(
            record.get("bundle_metadata"),
            field_name="bundle_set.bundle_records.bundle_metadata",
        )
        phase_map_reference = _bundle_phase_map_reference(bundle_metadata)
        if phase_map_reference is not None:
            references.append(phase_map_reference)
    references.sort(
        key=lambda item: (
            str(item["arm_id"]),
            int(item["seed"]),
            str(item["artifact_id"]),
            str(item["path"]),
        )
    )
    return references


def _bundle_phase_map_reference(
    bundle_metadata: Mapping[str, Any],
) -> dict[str, Any] | None:
    if str(bundle_metadata["arm_reference"]["model_mode"]) != "surface_wave":
        return None
    model_artifacts = {
        str(item["artifact_id"]): copy.deepcopy(dict(item))
        for item in bundle_metadata["artifacts"].get("model_artifacts", [])
    }
    phase_map_artifact = _resolve_phase_map_artifact(model_artifacts)
    if phase_map_artifact is None:
        return None
    path = Path(str(phase_map_artifact["path"])).resolve()
    root_ids = _phase_map_root_ids(path) if path.exists() else []
    return {
        "bundle_id": str(bundle_metadata["bundle_id"]),
        "arm_id": str(bundle_metadata["arm_reference"]["arm_id"]),
        "seed": int(bundle_metadata["determinism"]["seed"]),
        "artifact_id": str(phase_map_artifact["artifact_id"]),
        "path": str(path),
        "format": str(phase_map_artifact["format"]),
        "root_ids": root_ids,
    }


def _resolve_phase_map_artifact(
    model_artifacts: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    summary_artifact = model_artifacts.get(SURFACE_WAVE_SUMMARY_ARTIFACT_ID)
    if summary_artifact is not None and str(summary_artifact.get("status")) == "ready":
        summary_path = Path(str(summary_artifact["path"])).resolve()
        if summary_path.exists():
            with summary_path.open("r", encoding="utf-8") as handle:
                summary_payload = json.load(handle)
            if isinstance(summary_payload, Mapping):
                wave_specific_artifacts = summary_payload.get("wave_specific_artifacts")
                if isinstance(wave_specific_artifacts, Mapping):
                    candidate_id = wave_specific_artifacts.get("phase_map_artifact_id")
                    if candidate_id is not None:
                        candidate = model_artifacts.get(str(candidate_id))
                        if (
                            candidate is not None
                            and str(candidate.get("status")) == "ready"
                        ):
                            return candidate
    direct = model_artifacts.get(SURFACE_WAVE_PHASE_MAP_ARTIFACT_ID)
    if direct is not None and str(direct.get("status")) == "ready":
        return direct
    for artifact in model_artifacts.values():
        if (
            str(artifact.get("status")) == "ready"
            and str(artifact.get("format")) == SURFACE_WAVE_PHASE_MAP_FORMAT
        ):
            return artifact
    return None


def _phase_map_root_ids(path: Path) -> list[int]:
    with np.load(path, allow_pickle=False) as payload:
        if "root_ids" not in payload.files:
            return []
        return sorted(int(item) for item in np.asarray(payload["root_ids"]).tolist())


__all__ = [
    "package_experiment_analysis_bundle",
    "write_experiment_comparison_summary",
]
