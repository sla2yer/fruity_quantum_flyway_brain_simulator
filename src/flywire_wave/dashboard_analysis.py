from __future__ import annotations

import copy
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from .dashboard_replay import resolve_dashboard_time_series_view_model
from .dashboard_session_contract import (
    ANALYSIS_PANE_ID,
    PHASE_MAP_REFERENCE_OVERLAY_ID,
    PAIRED_READOUT_DELTA_OVERLAY_ID,
    REVIEWER_FINDINGS_OVERLAY_ID,
    SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    VALIDATION_STATUS_BADGES_OVERLAY_ID,
    WAVE_PATCH_ACTIVITY_OVERLAY_ID,
    build_dashboard_session_contract_metadata,
    discover_dashboard_export_targets,
    discover_dashboard_overlays,
)


DASHBOARD_ANALYSIS_CONTEXT_VERSION = "dashboard_analysis_context.v1"
DASHBOARD_ANALYSIS_VIEW_MODEL_VERSION = "dashboard_analysis_view_model.v1"

_SUPPORTED_ANALYSIS_OVERLAY_IDS = (
    SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    PAIRED_READOUT_DELTA_OVERLAY_ID,
    WAVE_PATCH_ACTIVITY_OVERLAY_ID,
    PHASE_MAP_REFERENCE_OVERLAY_ID,
    VALIDATION_STATUS_BADGES_OVERLAY_ID,
    REVIEWER_FINDINGS_OVERLAY_ID,
)


def build_dashboard_analysis_context(
    *,
    analysis_context: Mapping[str, Any],
    validation_context: Mapping[str, Any],
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    analysis = _require_mapping(analysis_context, field_name="analysis_context")
    validation = _require_mapping(validation_context, field_name="validation_context")
    normalized_contract = (
        build_dashboard_session_contract_metadata()
        if contract_metadata is None
        else _require_mapping(contract_metadata, field_name="contract_metadata")
    )

    analysis_ui_payload = _require_mapping(
        analysis.get("analysis_ui_payload", {}),
        field_name="analysis_context.analysis_ui_payload",
    )
    comparison_summary = _require_mapping(
        analysis.get("comparison_summary", {}),
        field_name="analysis_context.comparison_summary",
    )
    comparison_matrices = _require_mapping(
        analysis.get("comparison_matrices", {"matrices": []}),
        field_name="analysis_context.comparison_matrices",
    )
    visualization_catalog = _require_mapping(
        analysis.get("visualization_catalog", {"phase_map_references": []}),
        field_name="analysis_context.visualization_catalog",
    )
    validation_summary = _require_mapping(
        validation.get("summary", {}),
        field_name="validation_context.summary",
    )
    review_handoff = _require_mapping(
        validation.get("review_handoff", {}),
        field_name="validation_context.review_handoff",
    )
    validator_findings = _require_mapping(
        validation.get("findings", {"validator_findings": {}}),
        field_name="validation_context.findings",
    )

    shared_scope = _require_mapping(
        analysis_ui_payload.get("shared_comparison", {}),
        field_name="analysis_ui_payload.shared_comparison",
    )
    wave_scope = _require_mapping(
        analysis_ui_payload.get("wave_only_diagnostics", {}),
        field_name="analysis_ui_payload.wave_only_diagnostics",
    )
    mixed_scope = _require_mapping(
        analysis_ui_payload.get("mixed_scope", {}),
        field_name="analysis_ui_payload.mixed_scope",
    )
    analysis_visualizations = _require_mapping(
        analysis_ui_payload.get("analysis_visualizations", {}),
        field_name="analysis_ui_payload.analysis_visualizations",
    )

    matrix_views = _normalize_matrix_views(
        comparison_matrices.get("matrices", []),
        field_name="analysis_context.comparison_matrices.matrices",
    )
    shared_matrices = [
        copy.deepcopy(item)
        for item in matrix_views
        if str(item["scope_label"]) == "shared_comparison"
    ]
    wave_matrices = [
        copy.deepcopy(item)
        for item in matrix_views
        if str(item["scope_label"]) == "wave_only_diagnostics"
    ]

    task_summary_cards = _normalize_mapping_sequence(
        shared_scope.get(
            "task_summary_cards",
            analysis_ui_payload.get("task_summary_cards", []),
        ),
        field_name="analysis_ui_payload.shared_comparison.task_summary_cards",
    )
    shared_comparison_cards = _normalize_mapping_sequence(
        shared_scope.get("comparison_cards", []),
        field_name="analysis_ui_payload.shared_comparison.comparison_cards",
    )
    null_test_cards = _normalize_mapping_sequence(
        shared_scope.get("null_test_cards", []),
        field_name="analysis_ui_payload.shared_comparison.null_test_cards",
    )
    diagnostic_cards = _normalize_mapping_sequence(
        wave_scope.get("diagnostic_cards", []),
        field_name="analysis_ui_payload.wave_only_diagnostics.diagnostic_cards",
    )
    wave_comparison_cards = _normalize_mapping_sequence(
        wave_scope.get("comparison_cards", []),
        field_name="analysis_ui_payload.wave_only_diagnostics.comparison_cards",
    )
    mixed_comparison_cards = _normalize_mapping_sequence(
        mixed_scope.get("comparison_cards", []),
        field_name="analysis_ui_payload.mixed_scope.comparison_cards",
    )
    phase_map_references = _normalize_mapping_sequence(
        wave_scope.get(
            "phase_map_references",
            visualization_catalog.get("phase_map_references", []),
        ),
        field_name="analysis_ui_payload.wave_only_diagnostics.phase_map_references",
    )
    validator_summaries = _validator_summaries(
        validation_summary=validation_summary,
        review_handoff=review_handoff,
        validator_findings=validator_findings,
    )
    flattened_findings = _flatten_validator_findings(validator_findings)
    open_finding_ids = {
        str(item)
        for item in review_handoff.get("open_finding_ids", [])
    }

    overlay_catalog = [
        {
            "overlay_id": str(item["overlay_id"]),
            "display_name": str(item["display_name"]),
            "description": str(item["description"]),
            "overlay_category": str(item["overlay_category"]),
            "supported_comparison_modes": list(item["supported_comparison_modes"]),
        }
        for item in discover_dashboard_overlays(
            normalized_contract,
            pane_id=ANALYSIS_PANE_ID,
        )
    ]
    overlay_catalog.sort(
        key=lambda item: (
            str(item["overlay_category"]),
            str(item["overlay_id"]),
        )
    )
    export_target_catalog = [
        {
            "export_target_id": str(item["export_target_id"]),
            "display_name": str(item["display_name"]),
            "description": str(item["description"]),
            "target_kind": str(item["target_kind"]),
            "requires_time_cursor": bool(item["requires_time_cursor"]),
        }
        for item in discover_dashboard_export_targets(
            normalized_contract,
            pane_id=ANALYSIS_PANE_ID,
        )
    ]

    return {
        "pane_id": ANALYSIS_PANE_ID,
        "context_version": DASHBOARD_ANALYSIS_CONTEXT_VERSION,
        "bundle_id": str(analysis["bundle_id"]),
        "metadata_path": str(analysis["metadata_path"]),
        "analysis_ui_payload_path": str(analysis["analysis_ui_payload_path"]),
        "comparison_summary_path": str(analysis["comparison_summary_path"]),
        "comparison_summary_exists": bool(analysis["comparison_summary_exists"]),
        "comparison_matrices_path": str(analysis["comparison_matrices_path"]),
        "comparison_matrices_exists": bool(analysis["comparison_matrices_exists"]),
        "visualization_catalog_path": str(analysis["visualization_catalog_path"]),
        "visualization_catalog_exists": bool(analysis["visualization_catalog_exists"]),
        "offline_report_path": str(analysis["offline_report_path"]),
        "offline_report_exists": bool(analysis["offline_report_exists"]),
        "analysis_ui_payload": copy.deepcopy(dict(analysis_ui_payload)),
        "comparison_summary": copy.deepcopy(dict(comparison_summary)),
        "comparison_matrices": copy.deepcopy(dict(comparison_matrices)),
        "visualization_catalog": copy.deepcopy(dict(visualization_catalog)),
        "analysis_visualizations": copy.deepcopy(dict(analysis_visualizations)),
        "shared_comparison": {
            "task_summary_cards": task_summary_cards,
            "comparison_cards": shared_comparison_cards,
            "null_test_cards": null_test_cards,
            "matrix_views": shared_matrices,
            "milestone_1_decision_panel": copy.deepcopy(
                _require_mapping(
                    shared_scope.get("milestone_1_decision_panel", {}),
                    field_name="analysis_ui_payload.shared_comparison.milestone_1_decision_panel",
                )
            ),
            "ablation_summaries": _collect_ablation_summaries(
                task_summary_cards=task_summary_cards,
                comparison_cards=shared_comparison_cards,
                matrix_views=shared_matrices,
            ),
        },
        "wave_only_diagnostics": {
            "comparison_cards": wave_comparison_cards,
            "diagnostic_cards": diagnostic_cards,
            "phase_map_references": phase_map_references,
            "matrix_views": wave_matrices,
        },
        "mixed_scope": {
            "comparison_cards": mixed_comparison_cards,
        },
        "validation_evidence": {
            "summary_path": str(validation["summary_path"]),
            "findings_path": str(validation["findings_path"]),
            "review_handoff_path": str(validation["review_handoff_path"]),
            "offline_report_path": str(validation["offline_report_path"]),
            "offline_report_exists": bool(validation["offline_report_exists"]),
            "status_card": {
                "overall_status": str(validation_summary.get("overall_status", "unknown")),
                "review_status": str(review_handoff.get("review_status", "unknown")),
                "open_finding_count": len(open_finding_ids),
                "active_validator_count": len(validator_summaries),
                "layer_count": len(validation_summary.get("layer_summaries", [])),
            },
            "layer_summaries": _normalize_mapping_sequence(
                validation_summary.get("layer_summaries", []),
                field_name="validation_context.summary.layer_summaries",
            ),
            "review_handoff": copy.deepcopy(dict(review_handoff)),
            "validator_summaries": validator_summaries,
            "validator_findings": copy.deepcopy(dict(validator_findings)),
            "open_findings": [
                copy.deepcopy(item)
                for item in flattened_findings
                if str(item["finding_id"]) in open_finding_ids
            ],
            "finding_count": len(flattened_findings),
        },
        "analysis_overlay_catalog": {
            "entries": overlay_catalog,
            "supported_overlay_ids": [
                str(item["overlay_id"]) for item in overlay_catalog
            ],
        },
        "export_target_catalog": export_target_catalog,
        "supported_export_target_ids": [
            str(item["export_target_id"]) for item in export_target_catalog
        ],
        "phase_map_reference_count": len(phase_map_references),
        "wave_diagnostic_card_count": len(diagnostic_cards),
        "validation": {
            "overall_status": str(validation_summary.get("overall_status", "unknown")),
            "review_status": str(review_handoff.get("review_status", "unknown")),
            "open_finding_count": len(open_finding_ids),
        },
        "summary_counts": {
            "task_summary_card_count": len(task_summary_cards),
            "shared_comparison_card_count": len(shared_comparison_cards),
            "wave_comparison_card_count": len(wave_comparison_cards),
            "null_test_card_count": len(null_test_cards),
            "diagnostic_card_count": len(diagnostic_cards),
            "matrix_view_count": len(matrix_views),
            "validator_summary_count": len(validator_summaries),
            "finding_count": len(flattened_findings),
        },
    }


def resolve_dashboard_analysis_view_model(
    analysis_context: Mapping[str, Any],
    *,
    time_series_context: Mapping[str, Any],
    selected_neuron_id: int,
    selected_readout_id: str,
    comparison_mode: str,
    active_arm_id: str,
    active_overlay_id: str,
    sample_index: int,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    context = _require_mapping(analysis_context, field_name="analysis_context")
    normalized_contract = (
        build_dashboard_session_contract_metadata()
        if contract_metadata is None
        else _require_mapping(contract_metadata, field_name="contract_metadata")
    )
    overlay_catalog = _analysis_overlay_catalog(
        analysis_context=context,
        comparison_mode=comparison_mode,
        selected_neuron_id=selected_neuron_id,
        contract_metadata=normalized_contract,
    )
    time_series_view: dict[str, Any] | None = None
    time_series_error: str | None = None
    try:
        time_series_view = resolve_dashboard_time_series_view_model(
            time_series_context,
            selected_neuron_id=int(selected_neuron_id),
            selected_readout_id=str(selected_readout_id),
            comparison_mode=str(comparison_mode),
            active_arm_id=str(active_arm_id),
            sample_index=int(sample_index),
        )
    except ValueError as exc:
        time_series_error = str(exc)
    active_overlay_state = _resolve_analysis_overlay_state(
        analysis_context=context,
        overlay_catalog=overlay_catalog,
        active_overlay_id=str(active_overlay_id),
        selected_neuron_id=int(selected_neuron_id),
        time_series_view=time_series_view,
        time_series_error=time_series_error,
    )
    return {
        "format_version": DASHBOARD_ANALYSIS_VIEW_MODEL_VERSION,
        "selected_neuron_id": int(selected_neuron_id),
        "selected_readout_id": str(selected_readout_id),
        "comparison_mode": str(comparison_mode),
        "active_arm_id": str(active_arm_id),
        "sample_index": int(sample_index),
        "overlay_catalog": overlay_catalog,
        "active_overlay": active_overlay_state,
        "linked_comparison": (
            None
            if time_series_view is None
            else {
                "cursor": copy.deepcopy(dict(time_series_view["cursor"])),
                "shared_comparison": copy.deepcopy(
                    dict(time_series_view["shared_comparison"])
                ),
                "wave_diagnostic": copy.deepcopy(
                    dict(time_series_view["wave_diagnostic"])
                ),
            }
        ),
        "time_series_error": time_series_error,
        "shared_comparison": copy.deepcopy(
            _require_mapping(
                context.get("shared_comparison", {}),
                field_name="analysis_context.shared_comparison",
            )
        ),
        "wave_only_diagnostics": copy.deepcopy(
            _require_mapping(
                context.get("wave_only_diagnostics", {}),
                field_name="analysis_context.wave_only_diagnostics",
            )
        ),
        "validation_evidence": copy.deepcopy(
            _require_mapping(
                context.get("validation_evidence", {}),
                field_name="analysis_context.validation_evidence",
            )
        ),
        "export_target_catalog": copy.deepcopy(
            _normalize_mapping_sequence(
                context.get("export_target_catalog", []),
                field_name="analysis_context.export_target_catalog",
            )
        ),
    }


def _analysis_overlay_catalog(
    *,
    analysis_context: Mapping[str, Any],
    comparison_mode: str,
    selected_neuron_id: int,
    contract_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    supported_by_id = {
        str(item["overlay_id"]): copy.deepcopy(dict(item))
        for item in discover_dashboard_overlays(
            contract_metadata,
            pane_id=ANALYSIS_PANE_ID,
        )
    }
    for overlay in discover_dashboard_overlays(
        contract_metadata,
        pane_id=ANALYSIS_PANE_ID,
    ):
        overlay_id = str(overlay["overlay_id"])
        reason = None
        if str(comparison_mode) not in overlay["supported_comparison_modes"]:
            reason = (
                "not supported by comparison mode "
                f"{comparison_mode!r}"
            )
        elif overlay_id == SHARED_READOUT_ACTIVITY_OVERLAY_ID:
            if int(
                _require_mapping(
                    analysis_context.get("summary_counts", {}),
                    field_name="analysis_context.summary_counts",
                ).get("task_summary_card_count", 0)
            ) < 1 and int(analysis_context["summary_counts"].get("shared_comparison_card_count", 0)) < 1:
                reason = "shared comparison summaries are absent from the packaged analysis payload"
        elif overlay_id == PAIRED_READOUT_DELTA_OVERLAY_ID:
            if int(analysis_context["summary_counts"].get("matrix_view_count", 0)) < 1:
                reason = "matrix-like comparison views are absent from the packaged analysis payload"
        elif overlay_id == WAVE_PATCH_ACTIVITY_OVERLAY_ID:
            if int(analysis_context.get("wave_diagnostic_card_count", 0)) < 1:
                reason = "requested wave-only diagnostics are absent from the packaged analysis payload"
        elif overlay_id == PHASE_MAP_REFERENCE_OVERLAY_ID:
            if int(analysis_context.get("phase_map_reference_count", 0)) < 1:
                reason = "requested phase-map references are absent from the packaged analysis payload"
        elif overlay_id == VALIDATION_STATUS_BADGES_OVERLAY_ID:
            status_card = _require_mapping(
                _require_mapping(
                    analysis_context.get("validation_evidence", {}),
                    field_name="analysis_context.validation_evidence",
                ).get("status_card", {}),
                field_name="analysis_context.validation_evidence.status_card",
            )
            if not str(status_card.get("overall_status", "")).strip():
                reason = "validation summary is missing overall_status"
        elif overlay_id == REVIEWER_FINDINGS_OVERLAY_ID:
            review_handoff = _require_mapping(
                _require_mapping(
                    analysis_context.get("validation_evidence", {}),
                    field_name="analysis_context.validation_evidence",
                ).get("review_handoff", {}),
                field_name="analysis_context.validation_evidence.review_handoff",
            )
            if not review_handoff:
                reason = "validation review handoff is empty"
        entry = {
            "overlay_id": overlay_id,
            "display_name": str(overlay["display_name"]),
            "description": str(overlay["description"]),
            "overlay_category": str(overlay["overlay_category"]),
            "supported_comparison_modes": list(overlay["supported_comparison_modes"]),
            "availability": "available" if reason is None else "unavailable",
            "reason": reason,
        }
        if overlay_id == PHASE_MAP_REFERENCE_OVERLAY_ID:
            matches = _matching_phase_map_references(
                analysis_context=analysis_context,
                selected_neuron_id=int(selected_neuron_id),
            )
            entry["matching_phase_map_count"] = len(matches)
        entries.append(entry)
    entries.sort(
        key=lambda item: (
            str(item["overlay_category"]),
            str(item["overlay_id"]),
        )
    )
    return entries


def _resolve_analysis_overlay_state(
    *,
    analysis_context: Mapping[str, Any],
    overlay_catalog: Sequence[Mapping[str, Any]],
    active_overlay_id: str,
    selected_neuron_id: int,
    time_series_view: Mapping[str, Any] | None,
    time_series_error: str | None,
) -> dict[str, Any]:
    overlay_id = str(active_overlay_id)
    overlay_entry = next(
        (
            _require_mapping(item, field_name="overlay_catalog[]")
            for item in overlay_catalog
            if str(_require_mapping(item, field_name="overlay_catalog[]")["overlay_id"])
            == overlay_id
        ),
        None,
    )
    if overlay_entry is None or overlay_id not in _SUPPORTED_ANALYSIS_OVERLAY_IDS:
        return {
            "overlay_id": overlay_id,
            "availability": "inapplicable",
            "reason": "This overlay is owned by another pane.",
            "scope_label": "other_pane_only",
        }
    if str(overlay_entry["availability"]) != "available":
        return {
            "overlay_id": overlay_id,
            "availability": str(overlay_entry["availability"]),
            "reason": overlay_entry.get("reason"),
            "scope_label": str(overlay_entry["overlay_category"]),
        }
    if overlay_id in {
        SHARED_READOUT_ACTIVITY_OVERLAY_ID,
        PAIRED_READOUT_DELTA_OVERLAY_ID,
    }:
        if time_series_view is None:
            return {
                "overlay_id": overlay_id,
                "availability": "unavailable",
                "reason": time_series_error or "shared readout replay state is unavailable",
                "scope_label": str(overlay_entry["overlay_category"]),
            }
        shared = _require_mapping(
            time_series_view.get("shared_comparison", {}),
            field_name="time_series_view.shared_comparison",
        )
        return {
            "overlay_id": overlay_id,
            "availability": "available",
            "reason": None,
            "scope_label": str(overlay_entry["overlay_category"]),
            "baseline_value": float(shared["baseline_value"]),
            "wave_value": float(shared["wave_value"]),
            "delta_value": float(shared["delta_value"]),
            "readout_id": str(shared["readout_id"]),
            "display_name": str(shared["display_name"]),
            "units": str(shared["units"]),
            "fairness_note": str(shared["fairness_note"]),
            "cursor": copy.deepcopy(dict(time_series_view["cursor"])),
        }
    if overlay_id == WAVE_PATCH_ACTIVITY_OVERLAY_ID:
        diagnostics = _normalize_mapping_sequence(
            _require_mapping(
                analysis_context.get("wave_only_diagnostics", {}),
                field_name="analysis_context.wave_only_diagnostics",
            ).get("diagnostic_cards", []),
            field_name="analysis_context.wave_only_diagnostics.diagnostic_cards",
        )
        return {
            "overlay_id": overlay_id,
            "availability": "available",
            "reason": None,
            "scope_label": str(overlay_entry["overlay_category"]),
            "diagnostic_card_count": len(diagnostics),
            "metric_ids": sorted(
                {
                    str(item.get("metric_id", ""))
                    for item in diagnostics
                    if str(item.get("metric_id", "")).strip()
                }
            ),
        }
    if overlay_id == PHASE_MAP_REFERENCE_OVERLAY_ID:
        matches = _matching_phase_map_references(
            analysis_context=analysis_context,
            selected_neuron_id=int(selected_neuron_id),
        )
        return {
            "overlay_id": overlay_id,
            "availability": "available",
            "reason": None,
            "scope_label": str(overlay_entry["overlay_category"]),
            "matching_phase_map_count": len(matches),
            "phase_map_reference_count": int(analysis_context["phase_map_reference_count"]),
            "phase_map_references": matches,
        }
    if overlay_id == VALIDATION_STATUS_BADGES_OVERLAY_ID:
        validation_evidence = _require_mapping(
            analysis_context.get("validation_evidence", {}),
            field_name="analysis_context.validation_evidence",
        )
        return {
            "overlay_id": overlay_id,
            "availability": "available",
            "reason": None,
            "scope_label": str(overlay_entry["overlay_category"]),
            "status_card": copy.deepcopy(
                _require_mapping(
                    validation_evidence.get("status_card", {}),
                    field_name="analysis_context.validation_evidence.status_card",
                )
            ),
            "layer_summaries": copy.deepcopy(
                _normalize_mapping_sequence(
                    validation_evidence.get("layer_summaries", []),
                    field_name="analysis_context.validation_evidence.layer_summaries",
                )
            ),
        }
    validation_evidence = _require_mapping(
        analysis_context.get("validation_evidence", {}),
        field_name="analysis_context.validation_evidence",
    )
    return {
        "overlay_id": overlay_id,
        "availability": "available",
        "reason": None,
        "scope_label": str(overlay_entry["overlay_category"]),
        "review_handoff": copy.deepcopy(
            _require_mapping(
                validation_evidence.get("review_handoff", {}),
                field_name="analysis_context.validation_evidence.review_handoff",
            )
        ),
        "open_findings": copy.deepcopy(
            _normalize_mapping_sequence(
                validation_evidence.get("open_findings", []),
                field_name="analysis_context.validation_evidence.open_findings",
            )
        ),
        "validator_summaries": copy.deepcopy(
            _normalize_mapping_sequence(
                validation_evidence.get("validator_summaries", []),
                field_name="analysis_context.validation_evidence.validator_summaries",
            )
        ),
    }


def _matching_phase_map_references(
    *,
    analysis_context: Mapping[str, Any],
    selected_neuron_id: int,
) -> list[dict[str, Any]]:
    phase_map_references = _normalize_mapping_sequence(
        _require_mapping(
            analysis_context.get("wave_only_diagnostics", {}),
            field_name="analysis_context.wave_only_diagnostics",
        ).get("phase_map_references", []),
        field_name="analysis_context.wave_only_diagnostics.phase_map_references",
    )
    matches: list[dict[str, Any]] = []
    for item in phase_map_references:
        root_ids = [
            int(root_id)
            for root_id in item.get("root_ids", [])
        ]
        if root_ids and int(selected_neuron_id) not in root_ids:
            continue
        matches.append(copy.deepcopy(item))
    return matches


def _collect_ablation_summaries(
    *,
    task_summary_cards: Sequence[Mapping[str, Any]],
    comparison_cards: Sequence[Mapping[str, Any]],
    matrix_views: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for card in task_summary_cards:
        group_id = str(card.get("group_id", ""))
        if "ablation" not in group_id:
            continue
        record = grouped.setdefault(
            group_id,
            {
                "group_id": group_id,
                "task_card_ids": [],
                "requested_metric_ids": [],
                "comparison_output_ids": [],
                "matrix_ids": [],
                "score_values": [],
                "derivation_note": (
                    "Derived from packaged Milestone 12 analysis rows whose group_id "
                    "contains 'ablation'."
                ),
            },
        )
        record["task_card_ids"].append(str(card.get("card_id", "")))
        record["requested_metric_ids"].append(str(card.get("requested_metric_id", "")))
        value = card.get("value")
        if isinstance(value, (int, float)):
            record["score_values"].append(float(value))
    for card in comparison_cards:
        summary = _require_mapping(
            card.get("summary", {}),
            field_name="comparison_card.summary",
        )
        group_ids = [
            str(group_id)
            for group_id in summary.get("group_ids", [])
        ]
        for group_id in group_ids:
            if "ablation" not in group_id:
                continue
            record = grouped.setdefault(
                group_id,
                {
                    "group_id": group_id,
                    "task_card_ids": [],
                    "requested_metric_ids": [],
                    "comparison_output_ids": [],
                    "matrix_ids": [],
                    "score_values": [],
                    "derivation_note": (
                        "Derived from packaged Milestone 12 analysis rows whose group_id "
                        "contains 'ablation'."
                    ),
                },
            )
            record["comparison_output_ids"].append(str(card.get("output_id", "")))
    for matrix in matrix_views:
        row_axis = _require_mapping(
            matrix.get("row_axis", {}),
            field_name="matrix.row_axis",
        )
        for record in _normalize_mapping_sequence(
            row_axis.get("records", []),
            field_name="matrix.row_axis.records",
        ):
            group_id = str(record.get("group_id", ""))
            if "ablation" not in group_id:
                continue
            ablation = grouped.setdefault(
                group_id,
                {
                    "group_id": group_id,
                    "task_card_ids": [],
                    "requested_metric_ids": [],
                    "comparison_output_ids": [],
                    "matrix_ids": [],
                    "score_values": [],
                    "derivation_note": (
                        "Derived from packaged Milestone 12 analysis rows whose group_id "
                        "contains 'ablation'."
                    ),
                },
            )
            ablation["matrix_ids"].append(str(matrix.get("matrix_id", "")))
    normalized: list[dict[str, Any]] = []
    for group_id, record in sorted(grouped.items()):
        score_values = [float(value) for value in record["score_values"]]
        normalized.append(
            {
                "group_id": group_id,
                "task_card_count": len(record["task_card_ids"]),
                "comparison_card_count": len(record["comparison_output_ids"]),
                "matrix_count": len(record["matrix_ids"]),
                "requested_metric_ids": sorted(
                    {
                        item
                        for item in record["requested_metric_ids"]
                        if item
                    }
                ),
                "comparison_output_ids": sorted(
                    {
                        item
                        for item in record["comparison_output_ids"]
                        if item
                    }
                ),
                "matrix_ids": sorted(
                    {
                        item
                        for item in record["matrix_ids"]
                        if item
                    }
                ),
                "mean_task_score": (
                    None
                    if not score_values
                    else round(sum(score_values) / float(len(score_values)), 12)
                ),
                "derivation_note": record["derivation_note"],
            }
        )
    return normalized


def _normalize_matrix_views(
    payload: Any,
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    matrices = _normalize_mapping_sequence(payload, field_name=field_name)
    normalized: list[dict[str, Any]] = []
    for matrix in matrices:
        values = matrix.get("values", [])
        numeric_values = [
            float(cell)
            for row in values
            if isinstance(row, Sequence)
            for cell in row
            if isinstance(cell, (int, float))
        ]
        normalized_matrix = copy.deepcopy(dict(matrix))
        normalized_matrix["row_count"] = len(
            _require_mapping(
                matrix.get("row_axis", {}),
                field_name=f"{field_name}[].row_axis",
            ).get("ids", [])
        )
        normalized_matrix["column_count"] = len(
            _require_mapping(
                matrix.get("column_axis", {}),
                field_name=f"{field_name}[].column_axis",
            ).get("ids", [])
        )
        normalized_matrix["present_value_count"] = len(numeric_values)
        normalized_matrix["value_range"] = (
            []
            if not numeric_values
            else [min(numeric_values), max(numeric_values)]
        )
        normalized.append(normalized_matrix)
    normalized.sort(key=lambda item: (str(item.get("scope_label", "")), str(item.get("matrix_id", ""))))
    return normalized


def _validator_summaries(
    *,
    validation_summary: Mapping[str, Any],
    review_handoff: Mapping[str, Any],
    validator_findings: Mapping[str, Any],
) -> list[dict[str, Any]]:
    findings_by_validator = _require_mapping(
        validator_findings.get("validator_findings", {}),
        field_name="validator_findings.validator_findings",
    )
    review_statuses = _require_mapping(
        review_handoff.get("validator_statuses", {}),
        field_name="review_handoff.validator_statuses",
    )
    layer_lookup: dict[str, str] = {}
    for layer in _normalize_mapping_sequence(
        validation_summary.get("layer_summaries", []),
        field_name="validation_summary.layer_summaries",
    ):
        for validator_id in layer.get("active_validator_ids", []):
            layer_lookup[str(validator_id)] = str(layer.get("layer_id", ""))
    summaries: list[dict[str, Any]] = []
    validator_ids = sorted(
        {
            *[str(item) for item in findings_by_validator.keys()],
            *[str(item) for item in review_statuses.keys()],
        }
    )
    for validator_id in validator_ids:
        findings = _normalize_mapping_sequence(
            findings_by_validator.get(validator_id, []),
            field_name=f"validator_findings.validator_findings[{validator_id}]",
        )
        status_counts: dict[str, int] = defaultdict(int)
        for finding in findings:
            status_counts[str(finding.get("status", "unknown"))] += 1
        summaries.append(
            {
                "validator_id": validator_id,
                "layer_id": layer_lookup.get(validator_id),
                "finding_count": len(findings),
                "review_status": review_statuses.get(validator_id),
                "status_counts": dict(sorted(status_counts.items())),
            }
        )
    return summaries


def _flatten_validator_findings(
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    grouped = _require_mapping(
        payload.get("validator_findings", {}),
        field_name="validator_findings.validator_findings",
    )
    flattened: list[dict[str, Any]] = []
    for validator_id in sorted(str(item) for item in grouped.keys()):
        for finding in _normalize_mapping_sequence(
            grouped.get(validator_id, []),
            field_name=f"validator_findings.validator_findings[{validator_id}]",
        ):
            flattened.append(
                {
                    "validator_id": validator_id,
                    "finding_id": str(finding.get("finding_id", "")),
                    "status": str(finding.get("status", "unknown")),
                    "case_id": finding.get("case_id"),
                    "summary": finding.get("summary"),
                    "details": {
                        key: copy.deepcopy(value)
                        for key, value in finding.items()
                        if key not in {"finding_id", "status", "case_id", "summary"}
                    },
                }
            )
    flattened.sort(
        key=lambda item: (
            str(item["validator_id"]),
            str(item["finding_id"]),
        )
    )
    return flattened


def _normalize_mapping_sequence(
    payload: Any,
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence of mappings.")
    normalized: list[dict[str, Any]] = []
    for item in payload:
        normalized.append(copy.deepcopy(dict(_require_mapping(item, field_name=f"{field_name}[]"))))
    return normalized


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value


__all__ = [
    "DASHBOARD_ANALYSIS_CONTEXT_VERSION",
    "DASHBOARD_ANALYSIS_VIEW_MODEL_VERSION",
    "build_dashboard_analysis_context",
    "resolve_dashboard_analysis_view_model",
]
