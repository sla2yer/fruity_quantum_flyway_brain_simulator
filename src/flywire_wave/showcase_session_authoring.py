from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .dashboard_session_contract import (
    ANALYSIS_PANE_ID,
    APP_SHELL_INDEX_ARTIFACT_ID,
    CIRCUIT_PANE_ID,
    METADATA_JSON_KEY as DASHBOARD_METADATA_JSON_KEY,
    MORPHOLOGY_PANE_ID,
    PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
    PAIRED_READOUT_DELTA_OVERLAY_ID,
    PHASE_MAP_REFERENCE_OVERLAY_ID,
    REVIEWER_FINDINGS_OVERLAY_ID,
    SCENE_PANE_ID,
    SELECTED_SUBSET_HIGHLIGHT_OVERLAY_ID,
    SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    SINGLE_ARM_COMPARISON_MODE,
    STIMULUS_CONTEXT_FRAME_OVERLAY_ID,
    TIME_SERIES_PANE_ID,
    WAVE_PATCH_ACTIVITY_OVERLAY_ID,
    discover_dashboard_session_bundle_paths,
)
from .showcase_player import GUIDED_AUTOPLAY_MODE, PRESENTER_REHEARSAL_MODE
from .showcase_session_contract import (
    ACTIVE_VISUAL_SUBSET_STEP_ID,
    ACTIVITY_PROPAGATION_STEP_ID,
    ANALYSIS_OFFLINE_REPORT_ROLE_ID,
    ANALYSIS_SUMMARY_PRESET_ID,
    ANALYSIS_UI_PAYLOAD_ROLE_ID,
    APPROVED_HIGHLIGHT_PRESET_ID,
    APPROVED_WAVE_HIGHLIGHT_EVIDENCE_ROLE_ID,
    APPROVED_WAVE_HIGHLIGHT_STEP_ID,
    BASELINE_WAVE_COMPARISON_STEP_ID,
    CAMERA_TRANSITION_CUE_KIND_ID,
    DASHBOARD_SESSION_METADATA_ROLE_ID,
    DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
    DASHBOARD_SESSION_STATE_ROLE_ID,
    EVIDENCE_CAPTION_ANNOTATION_ID,
    FAIRNESS_BOUNDARY_ANNOTATION_ID,
    FALLBACK_NOTICE_ANNOTATION_ID,
    FALLBACK_REDIRECT_CUE_KIND_ID,
    FLY_VIEW_INPUT_STEP_ID,
    HERO_FRAME_EXPORT_TARGET_ROLE_ID,
    HIGHLIGHT_FALLBACK_PRESET_ID,
    INPUT_CONTEXT_EVIDENCE_ROLE_ID,
    INPUT_SAMPLING_ANNOTATION_ID,
    NARRATION_CALLOUT_CUE_KIND_ID,
    OVERLAY_REVEAL_CUE_KIND_ID,
    PAIRED_COMPARISON_PRESET_ID,
    PLAYBACK_SCRUB_CUE_KIND_ID,
    PRESENTATION_STATUS_BLOCKED,
    PRESENTATION_STATUS_FALLBACK,
    PRESENTATION_STATUS_PLANNED,
    PRESENTATION_STATUS_READY,
    PRESENTATION_STATUS_SCIENTIFIC_REVIEW_REQUIRED,
    PROPAGATION_REPLAY_PRESET_ID,
    REVIEW_MANIFEST_EXPORT_TARGET_ROLE_ID,
    RETINAL_INPUT_FOCUS_PRESET_ID,
    SHARED_COMPARISON_EVIDENCE_ROLE_ID,
    SCENE_CONTEXT_EVIDENCE_ROLE_ID,
    SCENE_CONTEXT_PRESET_ID,
    SCENE_SELECTION_STEP_ID,
    SCIENTIFIC_GUARDRAIL_ANNOTATION_ID,
    SCRIPTED_CLIP_EXPORT_TARGET_ROLE_ID,
    SHOWCASE_STATE_EXPORT_TARGET_ROLE_ID,
    STORYBOARD_EXPORT_TARGET_ROLE_ID,
    STORY_CONTEXT_ANNOTATION_ID,
    SUBSET_CONTEXT_EVIDENCE_ROLE_ID,
    SUBSET_CONTEXT_PRESET_ID,
    SUITE_ROLLUP_EVIDENCE_ROLE_ID,
    SUITE_SUMMARY_TABLE_ROLE_ID,
    SUMMARY_ANALYSIS_EVIDENCE_ROLE_ID,
    SUMMARY_ANALYSIS_STEP_ID,
    VALIDATION_FINDINGS_ROLE_ID,
    VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
    VALIDATION_REVIEW_HANDOFF_ROLE_ID,
    build_showcase_evidence_reference,
    build_showcase_narrative_annotation,
    build_showcase_saved_preset,
    build_showcase_step,
    discover_showcase_export_target_roles,
)
from .showcase_session_validation import (
    validate_highlight_locator,
    validate_presentation_state_patch,
)
from .stimulus_contract import _normalize_identifier, _normalize_nonempty_string


WHOLE_BRAIN_CONTEXT_HANDOFF_LINK_KIND = "whole_brain_context_handoff"
WHOLE_BRAIN_CONTEXT_SHOWCASE_HANDOFF_PRESET_ID = "showcase_handoff"

_PRESENTATION_STATUS_PRIORITY = {
    PRESENTATION_STATUS_BLOCKED: 0,
    PRESENTATION_STATUS_SCIENTIFIC_REVIEW_REQUIRED: 1,
    PRESENTATION_STATUS_FALLBACK: 2,
    PRESENTATION_STATUS_PLANNED: 3,
    PRESENTATION_STATUS_READY: 4,
}
_APPROVED_HIGHLIGHT_DECISIONS = {
    "approved",
    "approved_for_showcase",
    "scientifically_defensible",
    "ready_for_showcase",
}
_SHARED_COMPARISON_SCOPE_LABEL = "shared_comparison"
_WAVE_ONLY_DIAGNOSTIC_SCOPE_LABEL = "wave_only_diagnostic"
_SUMMARY_ANALYSIS_HEADLINE = "Small, causal, geometry-dependent computational effect."
_SUMMARY_ANALYSIS_SUBHEAD = (
    "Matched shared-comparison evidence first, wave-only diagnostic second, "
    "validation caveats explicit."
)
_DECISION_ITEM_DISPLAY_NAMES = {
    "m1_nonzero_shared_output_effect": "Matched shared output effect",
    "m1_geometry_dependence": "Geometry-dependent effect",
    "m1_survives_stronger_baseline": "Survives stronger baseline",
    "m1_seed_parameter_stability": "Stable across seeds and parameters",
}


def author_showcase_session_story(
    *,
    dashboard_context: Mapping[str, Any],
    analysis_context: Mapping[str, Any],
    validation_context: Mapping[str, Any],
    suite_context: Mapping[str, Any] | None,
    fixture_mode: str,
    saved_preset_overrides: Mapping[str, Mapping[str, Any]] | None,
    highlight_override: Mapping[str, Any] | None,
    enabled_export_target_role_ids: Sequence[str] | None,
    default_export_target_role_id: str,
    contract_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    narrative_context = build_narrative_context(
        dashboard_context=dashboard_context,
        analysis_context=analysis_context,
        validation_context=validation_context,
        suite_context=suite_context,
        highlight_override=highlight_override,
    )
    saved_presets = build_saved_presets(
        dashboard_context=dashboard_context,
        narrative_context=narrative_context,
        fixture_mode=fixture_mode,
        saved_preset_overrides=saved_preset_overrides,
    )
    showcase_steps = build_showcase_steps(
        narrative_context=narrative_context,
        suite_context=suite_context,
        enabled_export_target_role_ids=enabled_export_target_role_ids,
        default_export_target_role_id=default_export_target_role_id,
        contract_metadata=contract_metadata,
    )
    return {
        "narrative_context": narrative_context,
        "saved_presets": saved_presets,
        "showcase_steps": showcase_steps,
        "presentation_status": roll_up_presentation_status(showcase_steps),
        "showcase_fixture": build_showcase_fixture_profile(
            fixture_mode=fixture_mode,
            dashboard_context=dashboard_context,
            suite_context=suite_context,
            narrative_context=narrative_context,
        ),
    }


def build_narrative_context(
    *,
    dashboard_context: Mapping[str, Any],
    analysis_context: Mapping[str, Any],
    validation_context: Mapping[str, Any],
    suite_context: Mapping[str, Any] | None,
    highlight_override: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = dashboard_context["payload"]
    scene_context = _require_mapping(
        payload["pane_inputs"][SCENE_PANE_ID],
        field_name="dashboard_session_payload.pane_inputs.scene",
    )
    circuit_context = _require_mapping(
        payload["pane_inputs"][CIRCUIT_PANE_ID],
        field_name="dashboard_session_payload.pane_inputs.circuit",
    )
    morphology_context = _require_mapping(
        payload["pane_inputs"][MORPHOLOGY_PANE_ID],
        field_name="dashboard_session_payload.pane_inputs.morphology",
    )
    time_series_context = _require_mapping(
        payload["pane_inputs"][TIME_SERIES_PANE_ID],
        field_name="dashboard_session_payload.pane_inputs.time_series",
    )
    analysis_pane = _require_mapping(
        payload["pane_inputs"][ANALYSIS_PANE_ID],
        field_name="dashboard_session_payload.pane_inputs.analysis",
    )
    selected_pair = _require_mapping(
        payload["selected_bundle_pair"],
        field_name="dashboard_session_payload.selected_bundle_pair",
    )
    replay_model = _require_mapping(
        time_series_context["replay_model"],
        field_name="dashboard_session_payload.pane_inputs.time_series.replay_model",
    )
    highlight_selection = _resolve_highlight_selection(
        analysis_context=analysis_context,
        validation_context=validation_context,
        suite_context=suite_context,
        override=highlight_override,
    )
    comparison_act = _build_comparison_act(
        selected_pair=selected_pair,
        time_series_context=time_series_context,
        replay_model=replay_model,
        suite_context=suite_context,
    )
    closing_analysis_assets = {
        "analysis_ui_payload_path": str(analysis_context["ui_payload_path"]),
        "analysis_offline_report_path": analysis_context["offline_report_path"],
        "suite_summary_table_path": (
            None
            if suite_context is None or suite_context.get("summary_table_artifact") is None
            else str(suite_context["summary_table_artifact"]["path"])
        ),
        "suite_comparison_plot_path": (
            None
            if suite_context is None or suite_context.get("comparison_plot_artifact") is None
            else str(suite_context["comparison_plot_artifact"]["path"])
        ),
        "suite_review_artifact_path": (
            None
            if suite_context is None or suite_context.get("review_artifact") is None
            else str(suite_context["review_artifact"]["path"])
        ),
        "validation_summary_path": str(validation_context["summary_path"]),
        "validation_findings_path": str(validation_context["findings_path"]),
        "validation_review_handoff_path": validation_context["review_handoff_path"],
        "analysis_summary_locator": "shared_comparison.milestone_1_decision_panel",
    }
    analysis_summary_card = copy.deepcopy(
        analysis_pane["shared_comparison"]["milestone_1_decision_panel"]
    )
    highlight_presentation = _build_highlight_presentation(
        comparison_act=comparison_act,
        highlight_selection=highlight_selection,
    )
    summary_analysis_landing = _build_summary_analysis_landing(
        analysis_summary_card=analysis_summary_card,
        closing_analysis_assets=closing_analysis_assets,
        comparison_act=comparison_act,
        highlight_presentation=highlight_presentation,
    )
    return {
        "scene_choice": {
            "source_kind": str(scene_context["source_kind"]),
            "active_layer_id": str(scene_context["active_layer_id"]),
            "render_status": str(scene_context["render_status"]),
            "replay_frame_count": len(scene_context.get("replay_frames", [])),
        },
        "input_surface": {
            "surface_kind": _scene_surface_kind(scene_context),
            "active_layer_id": str(scene_context["active_layer_id"]),
            "source_kind": str(scene_context["source_kind"]),
        },
        "active_subset_focus_targets": {
            "selected_root_ids": list(circuit_context["selected_root_ids"]),
            "selected_neuron_id": morphology_context.get("selected_neuron_id"),
            "root_count": len(circuit_context["selected_root_ids"]),
        },
        "activity_propagation_views": {
            "available_overlay_ids": list(payload["overlay_catalog"]["available_overlay_ids"]),
            "selected_readout_id": str(time_series_context["selected_readout_id"]),
            "shared_timebase_status": copy.deepcopy(dict(replay_model["shared_timebase_status"])),
            "comparison_mode": str(
                dashboard_context["state"]["replay_state"]["comparison_mode"]
            ),
        },
        "approved_comparison_arms": {
            "baseline_arm_id": str(selected_pair["baseline"]["arm_id"]),
            "wave_arm_id": str(selected_pair["wave"]["arm_id"]),
            "baseline_bundle_id": str(selected_pair["baseline"]["bundle_id"]),
            "wave_bundle_id": str(selected_pair["wave"]["bundle_id"]),
            "shared_seed": int(selected_pair["shared_seed"]),
            "condition_ids": list(selected_pair["condition_ids"]),
            "selected_readout_id": str(time_series_context["selected_readout_id"]),
        },
        "comparison_act": comparison_act,
        "highlight_selection": highlight_selection,
        "highlight_presentation": highlight_presentation,
        "closing_analysis_assets": closing_analysis_assets,
        "summary_analysis_landing": summary_analysis_landing,
        "analysis_summary_card": analysis_summary_card,
    }


def _build_comparison_act(
    *,
    selected_pair: Mapping[str, Any],
    time_series_context: Mapping[str, Any],
    replay_model: Mapping[str, Any],
    suite_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    paired_status = _comparison_mode_status_by_id(
        replay_model,
        comparison_mode_id=PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
    )
    if str(paired_status.get("availability")) != "available":
        raise ValueError(
            "Showcase planning requires one paired baseline-versus-wave comparison mode "
            "for the comparison act, but dashboard replay reports "
            f"{paired_status!r}."
        )
    condition_signature = _normalize_identifier(
        "_".join(str(item) for item in selected_pair.get("condition_ids", []))
        or "all_conditions",
        field_name="comparison_act.condition_signature",
    )
    pairing_id = _normalize_identifier(
        (
            f"{selected_pair['baseline']['arm_id']}_"
            f"{selected_pair['wave']['arm_id']}_"
            f"{time_series_context['selected_readout_id']}_"
            f"seed_{selected_pair['shared_seed']}_"
            f"{condition_signature}"
        ),
        field_name="comparison_act.pairing_id",
    )
    support_references = [
        build_showcase_evidence_reference(
            evidence_role_id=SHARED_COMPARISON_EVIDENCE_ROLE_ID,
            artifact_role_id=ANALYSIS_UI_PAYLOAD_ROLE_ID,
            citation_label="Analysis shared-comparison payload",
            locator="shared_comparison",
        )
    ]
    if suite_context is not None and suite_context.get("summary_table_artifact") is not None:
        support_references.append(
            build_showcase_evidence_reference(
                evidence_role_id=SUITE_ROLLUP_EVIDENCE_ROLE_ID,
                artifact_role_id=SUITE_SUMMARY_TABLE_ROLE_ID,
                citation_label="Suite summary table",
                locator="shared_comparison_metrics.summary_table_rows",
                required=False,
            )
        )
    return {
        "view_id": "baseline_wave_comparison_view",
        "view_kind": "comparison_act",
        "display_name": "Matched Baseline vs Wave Comparison",
        "pairing_id": pairing_id,
        "comparison_mode": PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
        "content_scope_label": _SHARED_COMPARISON_SCOPE_LABEL,
        "stable_pairing_semantics": {
            "pairing_kind": "matched_shared_seed_condition_pair",
            "baseline_arm_id": str(selected_pair["baseline"]["arm_id"]),
            "wave_arm_id": str(selected_pair["wave"]["arm_id"]),
            "baseline_bundle_id": str(selected_pair["baseline"]["bundle_id"]),
            "wave_bundle_id": str(selected_pair["wave"]["bundle_id"]),
            "shared_seed": int(selected_pair["shared_seed"]),
            "condition_ids": [str(item) for item in selected_pair["condition_ids"]],
            "selected_readout_id": str(time_series_context["selected_readout_id"]),
            "shared_timebase_signature": str(replay_model["timebase_signature"]),
            "shared_timebase_status": copy.deepcopy(
                dict(replay_model["shared_timebase_status"])
            ),
            "comparison_mode_status": copy.deepcopy(dict(paired_status)),
        },
        "shared_surface": {
            "scope_label": _SHARED_COMPARISON_SCOPE_LABEL,
            "display_name": "Shared comparison",
            "comparison_mode": PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
            "selected_readout_id": str(time_series_context["selected_readout_id"]),
            "analysis_locator": "shared_comparison",
        },
        "wave_only_boundary": {
            "scope_label": _WAVE_ONLY_DIAGNOSTIC_SCOPE_LABEL,
            "display_name": "Wave-only diagnostics",
            "availability": "reserved_for_next_beat",
            "reason": (
                "Wave-only diagnostics stay outside the fairness-critical matched "
                "comparison beat."
            ),
        },
        "fairness_boundary": {
            "shared_comparison_label": "Shared comparison",
            "wave_only_label": "Wave-only diagnostic",
            "claim_rule": (
                "Only the shared-comparison surface supports direct baseline-versus-wave claims."
            ),
            "operator_note": (
                "Keep wave-only overlays and diagnostics visibly separate until the "
                "approved highlight beat."
            ),
        },
        "supporting_evidence_references": support_references,
    }


def _build_highlight_presentation(
    *,
    comparison_act: Mapping[str, Any],
    highlight_selection: Mapping[str, Any],
) -> dict[str, Any]:
    highlight_ready = (
        str(highlight_selection["presentation_status"]) == PRESENTATION_STATUS_READY
    )
    return {
        "view_id": (
            "approved_wave_highlight_view"
            if highlight_ready
            else "wave_highlight_fallback_view"
        ),
        "view_kind": (
            "wave_highlight_effect" if highlight_ready else "wave_highlight_caveat"
        ),
        "display_name": (
            "Wave-Only Highlight" if highlight_ready else "Wave-Only Highlight Caveat"
        ),
        "active_scope_label": (
            _WAVE_ONLY_DIAGNOSTIC_SCOPE_LABEL
            if highlight_ready
            else _SHARED_COMPARISON_SCOPE_LABEL
        ),
        "nominated_scope_label": _WAVE_ONLY_DIAGNOSTIC_SCOPE_LABEL,
        "presentation_status": str(highlight_selection["presentation_status"]),
        "phenomenon_id": str(highlight_selection["phenomenon_id"]),
        "citation_label": str(highlight_selection["citation_label"]),
        "comparison_reference": {
            "step_id": BASELINE_WAVE_COMPARISON_STEP_ID,
            "preset_id": PAIRED_COMPARISON_PRESET_ID,
            "pairing_id": str(comparison_act["pairing_id"]),
        },
        "fairness_boundary": {
            "shared_comparison_label": str(
                comparison_act["fairness_boundary"]["shared_comparison_label"]
            ),
            "wave_only_label": str(
                comparison_act["fairness_boundary"]["wave_only_label"]
            ),
            "claim_rule": (
                "Treat the highlight as a wave-only diagnostic rather than as the "
                "matched comparison itself."
            ),
        },
        "primary_evidence_reference": copy.deepcopy(
            dict(highlight_selection["primary_evidence_reference"])
        ),
        "supporting_evidence_references": [
            copy.deepcopy(dict(item))
            for item in highlight_selection.get("supporting_evidence_references", [])
        ],
        "guardrail_status": {
            "scientific_plausibility_decision": highlight_selection.get(
                "scientific_plausibility_decision"
            ),
            "review_status": highlight_selection.get("review_status"),
            "approved_for_showcase": bool(highlight_ready),
        },
        "caveat_text": (
            None
            if highlight_ready
            else str(highlight_selection["fallback_path"]["fallback_explanation"])
        ),
        "fallback_path": copy.deepcopy(dict(highlight_selection["fallback_path"])),
    }


def _build_summary_analysis_landing(
    *,
    analysis_summary_card: Mapping[str, Any],
    closing_analysis_assets: Mapping[str, Any],
    comparison_act: Mapping[str, Any],
    highlight_presentation: Mapping[str, Any],
) -> dict[str, Any]:
    decision_rows = []
    for index, item in enumerate(
        _normalize_mapping_sequence(
            analysis_summary_card.get("decision_items", []),
            field_name="analysis_summary_card.decision_items",
        )
    ):
        item_id = str(item["item_id"])
        decision_rows.append(
            {
                "claim_id": item_id,
                "display_name": _DECISION_ITEM_DISPLAY_NAMES.get(
                    item_id,
                    item_id.replace("_", " "),
                ),
                "status": str(item.get("status", "unavailable")),
                "supports_claim": str(item.get("status", "unavailable")) == "pass",
                "locator": (
                    "shared_comparison.milestone_1_decision_panel."
                    f"decision_items[{index}]"
                ),
            }
        )

    evidence_references = [
        build_showcase_evidence_reference(
            evidence_role_id=SUMMARY_ANALYSIS_EVIDENCE_ROLE_ID,
            artifact_role_id=(
                ANALYSIS_OFFLINE_REPORT_ROLE_ID
                if closing_analysis_assets["analysis_offline_report_path"]
                else ANALYSIS_UI_PAYLOAD_ROLE_ID
            ),
            citation_label=(
                "Analysis offline report"
                if closing_analysis_assets["analysis_offline_report_path"]
                else "Analysis UI payload"
            ),
            locator=str(closing_analysis_assets["analysis_summary_locator"]),
        )
    ]
    if closing_analysis_assets["suite_summary_table_path"] is not None:
        evidence_references.append(
            build_showcase_evidence_reference(
                evidence_role_id=SUITE_ROLLUP_EVIDENCE_ROLE_ID,
                artifact_role_id=SUITE_SUMMARY_TABLE_ROLE_ID,
                citation_label="Suite summary table",
                locator="shared_comparison_metrics.summary_table_rows",
            )
        )
    if closing_analysis_assets["validation_review_handoff_path"] is not None:
        evidence_references.append(
            build_showcase_evidence_reference(
                evidence_role_id=VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
                artifact_role_id=VALIDATION_REVIEW_HANDOFF_ROLE_ID,
                citation_label="Validation review handoff",
                locator="scientific_plausibility_decision",
                required=False,
            )
        )
    elif closing_analysis_assets["validation_findings_path"] is not None:
        evidence_references.append(
            build_showcase_evidence_reference(
                evidence_role_id=VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
                artifact_role_id=VALIDATION_FINDINGS_ROLE_ID,
                citation_label="Validation findings",
                locator="validator_findings",
                required=False,
            )
        )

    highlight_ready = (
        str(highlight_presentation["presentation_status"]) == PRESENTATION_STATUS_READY
    )
    return {
        "view_id": "summary_analysis_landing_view",
        "view_kind": "summary_analysis_landing",
        "display_name": "Summary Analysis Landing",
        "headline": _SUMMARY_ANALYSIS_HEADLINE,
        "subheadline": _SUMMARY_ANALYSIS_SUBHEAD,
        "analysis_overall_status": str(
            analysis_summary_card.get("overall_status", "unavailable")
        ),
        "newcomer_summary_lines": [
            (
                "Start from the matched shared-comparison surface on one readout and "
                "one shared timebase."
            ),
            (
                "Use the wave-only highlight as an explicitly labeled diagnostic."
                if highlight_ready
                else "Demote the wave-only highlight to a caveated note when approval is missing."
            ),
            (
                "Close on packaged analysis, suite, and validation artifacts rather "
                "than a disconnected summary slide."
            ),
        ],
        "comparison_anchor": {
            "pairing_id": str(comparison_act["pairing_id"]),
            "content_scope_label": str(comparison_act["content_scope_label"]),
            "selected_readout_id": str(
                comparison_act["stable_pairing_semantics"]["selected_readout_id"]
            ),
        },
        "highlight_outcome": {
            "presentation_status": str(highlight_presentation["presentation_status"]),
            "citation_label": str(highlight_presentation["citation_label"]),
            "active_scope_label": str(highlight_presentation["active_scope_label"]),
            "caveat_text": highlight_presentation.get("caveat_text"),
        },
        "claim_rows": decision_rows,
        "supporting_evidence_references": evidence_references,
        "linked_artifacts": copy.deepcopy(dict(closing_analysis_assets)),
    }


def _resolve_highlight_selection(
    *,
    analysis_context: Mapping[str, Any],
    validation_context: Mapping[str, Any],
    suite_context: Mapping[str, Any] | None,
    override: Mapping[str, Any] | None,
) -> dict[str, Any]:
    normalized_override = _normalize_highlight_override(override)
    ui_payload = _require_mapping(
        analysis_context["ui_payload"],
        field_name="analysis_ui_payload",
    )
    wave_only = _require_mapping(
        ui_payload.get("wave_only_diagnostics"),
        field_name="analysis_ui_payload.wave_only_diagnostics",
    )
    phase_refs = _normalize_mapping_sequence(
        wave_only.get("phase_map_references", []),
        field_name="analysis_ui_payload.wave_only_diagnostics.phase_map_references",
    )
    diagnostic_cards = _normalize_mapping_sequence(
        wave_only.get("diagnostic_cards", []),
        field_name="analysis_ui_payload.wave_only_diagnostics.diagnostic_cards",
    )
    if not phase_refs and not diagnostic_cards:
        raise ValueError(
            "Showcase planning requires at least one wave-only highlight candidate "
            "in analysis_ui_payload.wave_only_diagnostics."
        )

    review_handoff = _require_mapping(
        validation_context.get("review_handoff", {}),
        field_name="validation_review_handoff",
    )
    scientific_decision = (
        None
        if review_handoff.get("scientific_plausibility_decision") is None
        else str(review_handoff["scientific_plausibility_decision"])
    )
    review_status = (
        None
        if review_handoff.get("review_status") is None
        else str(review_handoff["review_status"])
    )
    approved = scientific_decision in _APPROVED_HIGHLIGHT_DECISIONS
    suite_support_references = _highlight_suite_support_references(suite_context)
    validation_support_references = _highlight_validation_support_references(
        validation_context
    )

    if normalized_override is not None:
        requested_role = str(normalized_override["artifact_role_id"])
        locator = normalized_override.get("locator")
        if requested_role == ANALYSIS_UI_PAYLOAD_ROLE_ID:
            validate_highlight_locator(
                locator=locator,
                phase_refs=phase_refs,
                diagnostic_cards=diagnostic_cards,
            )
        source_reference = _resolve_highlight_source_reference(
            artifact_role_id=requested_role,
            locator=locator,
            phase_refs=phase_refs,
            diagnostic_cards=diagnostic_cards,
        )
        if not approved:
            raise ValueError(
                "Showcase planning received a nominated highlight override, but "
                "validation review_handoff does not approve the highlight: "
                f"scientific_plausibility_decision={scientific_decision!r}, "
                f"review_status={review_status!r}."
            )
        return {
            "phenomenon_id": str(normalized_override["phenomenon_id"]),
            "artifact_role_id": requested_role,
            "locator": locator,
            "citation_label": str(normalized_override["citation_label"]),
            "presentation_status": PRESENTATION_STATUS_READY,
            "scientific_plausibility_decision": scientific_decision,
            "review_status": review_status,
            "fallback_reason": None,
            "source_reference": source_reference,
            "primary_evidence_reference": build_showcase_evidence_reference(
                evidence_role_id=APPROVED_WAVE_HIGHLIGHT_EVIDENCE_ROLE_ID,
                artifact_role_id=requested_role,
                citation_label=str(normalized_override["citation_label"]),
                locator=locator,
            ),
            "supporting_evidence_references": suite_support_references
            + validation_support_references,
            "fallback_path": _build_highlight_fallback_path(
                suite_support_references=suite_support_references,
                validation_support_references=validation_support_references,
                fallback_reason=(
                    "Redirect to the paired comparison if the nominated wave-only beat "
                    "cannot be shown honestly at rehearsal time."
                ),
            ),
        }

    if phase_refs:
        first_phase = phase_refs[0]
        candidate = {
            "phenomenon_id": _normalize_identifier(
                f"{first_phase.get('artifact_id', 'phase_map')}_{first_phase.get('arm_id', 'wave')}",
                field_name="phenomenon_id",
            ),
            "artifact_role_id": ANALYSIS_UI_PAYLOAD_ROLE_ID,
            "locator": "wave_only_diagnostics.phase_map_references[0]",
            "citation_label": "Wave phase-map reference",
            "source_reference": {
                "source_kind": "phase_map_reference",
                "bundle_id": str(first_phase.get("bundle_id", "")),
                "arm_id": str(first_phase.get("arm_id", "")),
                "seed": int(first_phase.get("seed", 0)),
                "artifact_id": str(first_phase.get("artifact_id", "")),
                "root_ids": [int(item) for item in first_phase.get("root_ids", [])],
                "path": str(first_phase.get("path", "")),
            },
        }
    else:
        first_card = diagnostic_cards[0]
        label = str(first_card.get("display_name", first_card.get("card_id", "wave_diagnostic")))
        candidate = {
            "phenomenon_id": _normalize_identifier(label, field_name="phenomenon_id"),
            "artifact_role_id": ANALYSIS_UI_PAYLOAD_ROLE_ID,
            "locator": "wave_only_diagnostics.diagnostic_cards[0]",
            "citation_label": label,
            "source_reference": {
                "source_kind": "diagnostic_card",
                "card_id": str(first_card.get("card_id", "")),
                "arm_id": str(first_card.get("arm_id", "")),
                "metric_id": str(first_card.get("metric_id", "")),
                "mean_value": first_card.get("mean_value"),
                "units": str(first_card.get("units", "")),
                "seed_count": int(first_card.get("seed_count", 0)),
            },
        }
    fallback_reason = (
        None
        if approved
        else "validation review_handoff has not approved the requested wave-only beat"
    )
    return {
        **candidate,
        "presentation_status": (
            PRESENTATION_STATUS_READY if approved else PRESENTATION_STATUS_FALLBACK
        ),
        "scientific_plausibility_decision": scientific_decision,
        "review_status": review_status,
        "fallback_reason": fallback_reason,
        "primary_evidence_reference": build_showcase_evidence_reference(
            evidence_role_id=APPROVED_WAVE_HIGHLIGHT_EVIDENCE_ROLE_ID,
            artifact_role_id=str(candidate["artifact_role_id"]),
            citation_label=str(candidate["citation_label"]),
            locator=(
                None if candidate.get("locator") is None else str(candidate["locator"])
            ),
        ),
        "supporting_evidence_references": suite_support_references
        + validation_support_references,
        "fallback_path": _build_highlight_fallback_path(
            suite_support_references=suite_support_references,
            validation_support_references=validation_support_references,
            fallback_reason=(
                str(fallback_reason)
                if fallback_reason is not None
                else "Redirect to the paired comparison if the preferred highlight is unavailable."
            ),
        ),
    }


def _build_dashboard_inspection_escape_hatch(
    *,
    dashboard_context: Mapping[str, Any],
) -> dict[str, Any]:
    dashboard_paths = discover_dashboard_session_bundle_paths(dashboard_context["metadata"])
    metadata_path = Path(dashboard_paths[DASHBOARD_METADATA_JSON_KEY]).resolve()
    app_shell_path = Path(dashboard_paths[APP_SHELL_INDEX_ARTIFACT_ID]).resolve()
    return {
        "available": True,
        "entrypoint_id": "open_underlying_dashboard",
        "entrypoint_kind": "dashboard_bundle",
        "dashboard_session_metadata_path": str(metadata_path),
        "dashboard_app_shell_path": str(app_shell_path),
        "open_command": (
            "python scripts/29_dashboard_shell.py open "
            f"--dashboard-session-metadata {metadata_path}"
        ),
    }


def _build_camera_choreography(
    *,
    sequence_id: str,
    focus_pane_id: str,
    anchor_id: str,
    framing_mode: str,
    transition_id: str,
    transition_kind: str,
    duration_ms: int,
    hold_duration_ms: int,
    easing: str,
    from_anchor_id: str,
    linked_pane_ids: Sequence[str],
    narration_lead_in_ms: int,
    annotation_stagger_ms: int,
    source_kind: str | None = None,
    active_layer_id: str | None = None,
    surface_kind: str | None = None,
    target_root_ids: Sequence[int] | None = None,
    recommended_sample_index: int | None = None,
    recommended_time_ms: float | None = None,
) -> dict[str, Any]:
    anchor: dict[str, Any] = {
        "anchor_id": str(anchor_id),
        "framing_mode": str(framing_mode),
        "focus_pane_id": str(focus_pane_id),
    }
    if source_kind is not None:
        anchor["source_kind"] = str(source_kind)
    if active_layer_id is not None:
        anchor["active_layer_id"] = str(active_layer_id)
    if surface_kind is not None:
        anchor["surface_kind"] = str(surface_kind)
    if target_root_ids is not None:
        anchor["target_root_ids"] = [int(root_id) for root_id in target_root_ids]

    timing: dict[str, Any] = {
        "narration_lead_in_ms": int(narration_lead_in_ms),
        "annotation_stagger_ms": int(annotation_stagger_ms),
    }
    if recommended_sample_index is not None:
        timing["recommended_sample_index"] = int(recommended_sample_index)
    if recommended_time_ms is not None:
        timing["recommended_time_ms"] = float(recommended_time_ms)

    return {
        "sequence_id": str(sequence_id),
        "anchor": anchor,
        "transition": {
            "transition_id": str(transition_id),
            "transition_kind": str(transition_kind),
            "duration_ms": int(duration_ms),
            "hold_duration_ms": int(hold_duration_ms),
            "easing": str(easing),
            "from_anchor_id": str(from_anchor_id),
            "to_anchor_id": str(anchor_id),
            "manual_override_required": False,
        },
        "timing": timing,
        "linked_pane_ids": [str(pane_id) for pane_id in linked_pane_ids],
    }


def _build_annotation_placement(
    *,
    annotation_id: str,
    pane_id: str,
    placement: str,
    alignment: str,
    delay_ms: int,
) -> dict[str, Any]:
    return {
        "annotation_id": str(annotation_id),
        "pane_id": str(pane_id),
        "placement": str(placement),
        "alignment": str(alignment),
        "delay_ms": int(delay_ms),
    }


def _build_annotation_layout(
    *,
    layout_id: str,
    focus_pane_id: str,
    placements: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "layout_id": str(layout_id),
        "focus_pane_id": str(focus_pane_id),
        "placements": [copy.deepcopy(dict(item)) for item in placements],
    }


def _build_presentation_link(
    *,
    link_id: str,
    link_kind: str,
    source_pane_id: str,
    target_pane_ids: Sequence[str],
    shared_context: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "link_id": str(link_id),
        "link_kind": str(link_kind),
        "source_pane_id": str(source_pane_id),
        "target_pane_ids": [str(pane_id) for pane_id in target_pane_ids],
        "shared_context": copy.deepcopy(dict(shared_context)),
    }


def _build_emphasis_state(
    *,
    emphasis_id: str,
    emphasis_kind: str,
    linked_pane_ids: Sequence[str],
    overlay_ids_by_pane: Mapping[str, Sequence[str]],
    focus_root_ids: Sequence[int] | None = None,
    selected_neuron_id: int | None = None,
    selected_readout_id: str | None = None,
    scene_surface: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "emphasis_id": str(emphasis_id),
        "emphasis_kind": str(emphasis_kind),
        "linked_pane_ids": [str(pane_id) for pane_id in linked_pane_ids],
        "overlay_ids_by_pane": {
            str(pane_id): [str(overlay_id) for overlay_id in overlay_ids]
            for pane_id, overlay_ids in overlay_ids_by_pane.items()
        },
    }
    if focus_root_ids is not None:
        payload["focus_root_ids"] = [int(root_id) for root_id in focus_root_ids]
    if selected_neuron_id is not None:
        payload["selected_neuron_id"] = int(selected_neuron_id)
    if selected_readout_id is not None:
        payload["selected_readout_id"] = str(selected_readout_id)
    if scene_surface is not None:
        payload["scene_surface"] = copy.deepcopy(dict(scene_surface))
    return payload


def _build_showcase_ui_state(
    *,
    mode_id: str,
    primary_pane_id: str,
    support_pane_ids: Sequence[str],
    inspection_escape_hatch: Mapping[str, Any],
    guided_variant: Mapping[str, Any],
    rehearsal_variant: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "mode_id": str(mode_id),
        "primary_pane_id": str(primary_pane_id),
        "support_pane_ids": [str(pane_id) for pane_id in support_pane_ids],
        "inspection_escape_hatch": copy.deepcopy(dict(inspection_escape_hatch)),
        "runtime_mode_variants": {
            GUIDED_AUTOPLAY_MODE: copy.deepcopy(dict(guided_variant)),
            PRESENTER_REHEARSAL_MODE: copy.deepcopy(dict(rehearsal_variant)),
        },
    }


def _normalize_saved_preset_overrides(
    payload: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError("saved_preset_overrides must be a mapping keyed by preset_id.")
    normalized: dict[str, dict[str, Any]] = {}
    for raw_preset_id, raw_override in payload.items():
        preset_id = _normalize_identifier(raw_preset_id, field_name="preset_id")
        if not isinstance(raw_override, Mapping):
            raise ValueError(
                f"saved_preset_overrides[{preset_id!r}] must be a mapping."
            )
        unsupported = set(raw_override) - {
            "display_name",
            "note",
            "presentation_status",
            "source_artifact_role_id",
            "presentation_state_patch",
        }
        if unsupported:
            raise ValueError(
                f"saved_preset_overrides[{preset_id!r}] contains unsupported keys {sorted(unsupported)!r}."
            )
        normalized[preset_id] = copy.deepcopy(dict(raw_override))
    return normalized


def _normalize_highlight_override(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if payload is None:
        return None
    if not isinstance(payload, Mapping):
        raise ValueError("highlight_override must be a mapping when provided.")
    unsupported = set(payload) - {
        "phenomenon_id",
        "artifact_role_id",
        "locator",
        "citation_label",
    }
    if unsupported:
        raise ValueError(
            f"highlight_override contains unsupported keys {sorted(unsupported)!r}."
        )
    if "phenomenon_id" not in payload:
        raise ValueError("highlight_override must include phenomenon_id.")
    return {
        "phenomenon_id": _normalize_identifier(
            payload["phenomenon_id"],
            field_name="highlight_override.phenomenon_id",
        ),
        "artifact_role_id": _normalize_identifier(
            payload.get("artifact_role_id", ANALYSIS_UI_PAYLOAD_ROLE_ID),
            field_name="highlight_override.artifact_role_id",
        ),
        "locator": (
            None
            if payload.get("locator") is None
            else _normalize_nonempty_string(
                payload["locator"],
                field_name="highlight_override.locator",
            )
        ),
        "citation_label": _normalize_nonempty_string(
            payload.get("citation_label", str(payload["phenomenon_id"])),
            field_name="highlight_override.citation_label",
        ),
    }


def build_saved_presets(
    *,
    dashboard_context: Mapping[str, Any],
    narrative_context: Mapping[str, Any],
    fixture_mode: str,
    saved_preset_overrides: Mapping[str, Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    payload = dashboard_context["payload"]
    state = dashboard_context["state"]
    selected_root_ids = list(
        payload["pane_inputs"][CIRCUIT_PANE_ID]["selected_root_ids"]
    )
    selected_neuron_id = payload["pane_inputs"][MORPHOLOGY_PANE_ID]["selected_neuron_id"]
    selected_readout_id = payload["pane_inputs"][TIME_SERIES_PANE_ID]["selected_readout_id"]
    available_overlays = set(payload["overlay_catalog"]["available_overlay_ids"])
    scene_context = payload["pane_inputs"][SCENE_PANE_ID]
    active_arm_pair = payload["global_interaction_state"]["selected_arm_pair"]
    replay_model = payload["pane_inputs"][TIME_SERIES_PANE_ID]["replay_model"]
    canonical_time_ms = [float(value) for value in replay_model.get("canonical_time_ms", [])]
    scene_surface = {
        "source_kind": str(scene_context["source_kind"]),
        "active_layer_id": str(scene_context["active_layer_id"]),
    }
    dashboard_escape_hatch = _build_dashboard_inspection_escape_hatch(
        dashboard_context=dashboard_context
    )
    selected_root_preview = selected_root_ids[:1]
    scene_overlay_id = (
        STIMULUS_CONTEXT_FRAME_OVERLAY_ID
        if STIMULUS_CONTEXT_FRAME_OVERLAY_ID in available_overlays
        else payload["global_interaction_state"]["active_overlay_id"]
    )
    subset_overlay_id = _preferred_overlay(
        available_overlays,
        SELECTED_SUBSET_HIGHLIGHT_OVERLAY_ID,
        SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    )
    propagation_overlay_id = _preferred_overlay(
        available_overlays,
        SHARED_READOUT_ACTIVITY_OVERLAY_ID,
        WAVE_PATCH_ACTIVITY_OVERLAY_ID,
    )
    comparison_overlay_id = _preferred_overlay(
        available_overlays,
        PAIRED_READOUT_DELTA_OVERLAY_ID,
        SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    )
    highlight_overlay_id = _preferred_overlay(
        available_overlays,
        PHASE_MAP_REFERENCE_OVERLAY_ID,
        WAVE_PATCH_ACTIVITY_OVERLAY_ID,
        SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    )
    summary_overlay_id = _preferred_overlay(
        available_overlays,
        REVIEWER_FINDINGS_OVERLAY_ID,
        SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    )
    recommended_propagation_sample_index = min(2, max(0, len(canonical_time_ms) - 1))
    recommended_propagation_time_ms = (
        canonical_time_ms[recommended_propagation_sample_index]
        if canonical_time_ms
        else 0.0
    )
    step_defaults = {
        SCENE_CONTEXT_PRESET_ID: {
            "step_id": SCENE_SELECTION_STEP_ID,
            "display_name": "Scene Context",
            "note": "Open on the chosen packaged scene surface.",
            "presentation_status": PRESENTATION_STATUS_READY,
            "presentation_state_patch": {
                "active_pane_id": SCENE_PANE_ID,
                "focus_root_ids": selected_root_preview,
                "scene_surface": copy.deepcopy(dict(scene_surface)),
                "rehearsal_metadata": {
                    "fixture_mode": fixture_mode,
                    "story_role": "scene_choice",
                    "camera_anchor": {
                        "anchor_id": "opening_scene_context",
                        "framing_mode": "wide_establishing",
                        "source_kind": str(scene_context["source_kind"]),
                        "active_layer_id": str(scene_context["active_layer_id"]),
                        "target_root_ids": selected_root_preview,
                    },
                    "camera_choreography": _build_camera_choreography(
                        sequence_id="scene_selection_opening",
                        focus_pane_id=SCENE_PANE_ID,
                        anchor_id="opening_scene_context",
                        framing_mode="wide_establishing",
                        transition_id="dashboard_context_to_opening_scene",
                        transition_kind="dolly_in",
                        duration_ms=900,
                        hold_duration_ms=1600,
                        easing="ease_in_out_cubic",
                        from_anchor_id="dashboard_default_context",
                        linked_pane_ids=[SCENE_PANE_ID, CIRCUIT_PANE_ID],
                        narration_lead_in_ms=120,
                        annotation_stagger_ms=240,
                        source_kind=str(scene_context["source_kind"]),
                        active_layer_id=str(scene_context["active_layer_id"]),
                        target_root_ids=selected_root_preview,
                    ),
                    "annotation_layout": _build_annotation_layout(
                        layout_id="scene_selection_annotations",
                        focus_pane_id=SCENE_PANE_ID,
                        placements=[
                            _build_annotation_placement(
                                annotation_id=STORY_CONTEXT_ANNOTATION_ID,
                                pane_id=SCENE_PANE_ID,
                                placement="hero_top_left",
                                alignment="start",
                                delay_ms=120,
                            ),
                            _build_annotation_placement(
                                annotation_id="operator_prompt",
                                pane_id=SCENE_PANE_ID,
                                placement="footer_right",
                                alignment="end",
                                delay_ms=780,
                            ),
                        ],
                    ),
                    "presentation_links": [
                        _build_presentation_link(
                            link_id="scene_choice_to_subset_preview",
                            link_kind="scene_context_bridge",
                            source_pane_id=SCENE_PANE_ID,
                            target_pane_ids=[SCENE_PANE_ID, CIRCUIT_PANE_ID],
                            shared_context={
                                **scene_surface,
                                "surface_kind": str(
                                    narrative_context["input_surface"]["surface_kind"]
                                ),
                                "focus_root_ids": selected_root_preview,
                                "root_count": int(
                                    narrative_context["active_subset_focus_targets"][
                                        "root_count"
                                    ]
                                ),
                            },
                        )
                    ],
                    "emphasis_state": _build_emphasis_state(
                        emphasis_id="scene_selection_context_frame",
                        emphasis_kind="scene_context",
                        linked_pane_ids=[SCENE_PANE_ID, CIRCUIT_PANE_ID],
                        overlay_ids_by_pane={SCENE_PANE_ID: [scene_overlay_id]},
                        focus_root_ids=selected_root_preview,
                        scene_surface=scene_surface,
                    ),
                    "showcase_ui_state": _build_showcase_ui_state(
                        mode_id="scene_selection_showcase",
                        primary_pane_id=SCENE_PANE_ID,
                        support_pane_ids=[CIRCUIT_PANE_ID],
                        inspection_escape_hatch=dashboard_escape_hatch,
                        guided_variant={
                            "chrome_treatment": "narrative_minimal",
                            "visible_control_groups": [
                                "story_header",
                                "story_annotations",
                                "playback_transport",
                                "inspection_escape_hatch",
                            ],
                            "suppressed_control_groups": [
                                "comparison_controls",
                                "overlay_controls",
                                "neuron_detail_controls",
                                "readout_detail_controls",
                                "time_scrub",
                            ],
                            "reorganized_control_groups": ["scene_context_controls"],
                            "inspection_panel_state": "collapsed",
                        },
                        rehearsal_variant={
                            "chrome_treatment": "scene_hero",
                            "visible_control_groups": [
                                "story_header",
                                "story_annotations",
                                "playback_transport",
                                "inspection_escape_hatch",
                                "inspection_drawer",
                            ],
                            "suppressed_control_groups": ["comparison_controls"],
                            "reorganized_control_groups": [
                                "scene_context_controls",
                                "overlay_controls",
                                "neuron_detail_controls",
                            ],
                            "inspection_panel_state": "peek",
                        },
                    ),
                },
                "dashboard_state_patch": {
                    "global_interaction_state": {
                        "active_overlay_id": scene_overlay_id,
                        "time_cursor": {"sample_index": 0, "time_ms": 0.0},
                    },
                    "replay_state": {
                        "active_overlay_id": scene_overlay_id,
                        "time_cursor": {"sample_index": 0, "time_ms": 0.0},
                    },
                },
            },
        },
        RETINAL_INPUT_FOCUS_PRESET_ID: {
            "step_id": FLY_VIEW_INPUT_STEP_ID,
            "display_name": "Retinal Input Focus",
            "note": "Pause on the packaged input surface before the circuit replay begins.",
            "presentation_status": PRESENTATION_STATUS_READY,
            "presentation_state_patch": {
                "active_pane_id": SCENE_PANE_ID,
                "focus_root_ids": selected_root_preview,
                "scene_surface": copy.deepcopy(dict(scene_surface)),
                "rehearsal_metadata": {
                    "fixture_mode": fixture_mode,
                    "story_role": "fly_view_framing",
                    "camera_anchor": {
                        "anchor_id": "retinal_input_hold",
                        "framing_mode": "input_surface_hold",
                        "surface_kind": str(narrative_context["input_surface"]["surface_kind"]),
                        "active_layer_id": str(scene_context["active_layer_id"]),
                    },
                    "camera_choreography": _build_camera_choreography(
                        sequence_id="scene_to_retinal_input",
                        focus_pane_id=SCENE_PANE_ID,
                        anchor_id="retinal_input_hold",
                        framing_mode="input_surface_hold",
                        transition_id="opening_scene_to_retinal_input",
                        transition_kind="rack_focus",
                        duration_ms=720,
                        hold_duration_ms=1500,
                        easing="ease_out_quart",
                        from_anchor_id="opening_scene_context",
                        linked_pane_ids=[SCENE_PANE_ID, TIME_SERIES_PANE_ID],
                        narration_lead_in_ms=100,
                        annotation_stagger_ms=220,
                        source_kind=str(scene_context["source_kind"]),
                        active_layer_id=str(scene_context["active_layer_id"]),
                        surface_kind=str(narrative_context["input_surface"]["surface_kind"]),
                        target_root_ids=selected_root_preview,
                    ),
                    "annotation_layout": _build_annotation_layout(
                        layout_id="retinal_input_focus_annotations",
                        focus_pane_id=SCENE_PANE_ID,
                        placements=[
                            _build_annotation_placement(
                                annotation_id=INPUT_SAMPLING_ANNOTATION_ID,
                                pane_id=SCENE_PANE_ID,
                                placement="hero_bottom_left",
                                alignment="start",
                                delay_ms=100,
                            ),
                            _build_annotation_placement(
                                annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID,
                                pane_id=SCENE_PANE_ID,
                                placement="footer_right",
                                alignment="end",
                                delay_ms=640,
                            ),
                        ],
                    ),
                    "presentation_links": [
                        _build_presentation_link(
                            link_id="scene_to_input_surface",
                            link_kind="shared_scene_surface",
                            source_pane_id=SCENE_PANE_ID,
                            target_pane_ids=[SCENE_PANE_ID, TIME_SERIES_PANE_ID],
                            shared_context={
                                **scene_surface,
                                "surface_kind": str(
                                    narrative_context["input_surface"]["surface_kind"]
                                ),
                                "focus_root_ids": selected_root_preview,
                            },
                        )
                    ],
                    "emphasis_state": _build_emphasis_state(
                        emphasis_id="retinal_input_focus_frame",
                        emphasis_kind="input_surface",
                        linked_pane_ids=[SCENE_PANE_ID, TIME_SERIES_PANE_ID],
                        overlay_ids_by_pane={SCENE_PANE_ID: [scene_overlay_id]},
                        focus_root_ids=selected_root_preview,
                        scene_surface=scene_surface,
                    ),
                    "showcase_ui_state": _build_showcase_ui_state(
                        mode_id="retinal_input_showcase",
                        primary_pane_id=SCENE_PANE_ID,
                        support_pane_ids=[TIME_SERIES_PANE_ID],
                        inspection_escape_hatch=dashboard_escape_hatch,
                        guided_variant={
                            "chrome_treatment": "input_focus",
                            "visible_control_groups": [
                                "story_header",
                                "story_annotations",
                                "playback_transport",
                                "time_scrub",
                                "inspection_escape_hatch",
                            ],
                            "suppressed_control_groups": [
                                "comparison_controls",
                                "overlay_controls",
                                "neuron_detail_controls",
                                "readout_detail_controls",
                            ],
                            "reorganized_control_groups": ["scene_context_controls"],
                            "inspection_panel_state": "collapsed",
                        },
                        rehearsal_variant={
                            "chrome_treatment": "input_focus_rehearsal",
                            "visible_control_groups": [
                                "story_header",
                                "story_annotations",
                                "playback_transport",
                                "time_scrub",
                                "inspection_escape_hatch",
                                "inspection_drawer",
                            ],
                            "suppressed_control_groups": ["comparison_controls"],
                            "reorganized_control_groups": [
                                "scene_context_controls",
                                "overlay_controls",
                            ],
                            "inspection_panel_state": "peek",
                        },
                    ),
                },
                "dashboard_state_patch": {
                    "global_interaction_state": {"active_overlay_id": scene_overlay_id},
                    "replay_state": {"active_overlay_id": scene_overlay_id},
                },
            },
        },
        SUBSET_CONTEXT_PRESET_ID: {
            "step_id": ACTIVE_VISUAL_SUBSET_STEP_ID,
            "display_name": "Subset Context",
            "note": "Expose the selected roots and current focus neuron.",
            "presentation_status": PRESENTATION_STATUS_READY,
            "presentation_state_patch": {
                "active_pane_id": CIRCUIT_PANE_ID,
                "focus_root_ids": selected_root_ids,
                "scene_surface": copy.deepcopy(dict(scene_surface)),
                "rehearsal_metadata": {
                    "fixture_mode": fixture_mode,
                    "story_role": "active_subset_emphasis",
                    "subset_focus": copy.deepcopy(
                        dict(narrative_context["active_subset_focus_targets"])
                    ),
                    "camera_anchor": {
                        "anchor_id": "active_subset_cluster",
                        "framing_mode": "cluster_focus",
                        "target_root_ids": selected_root_ids,
                    },
                    "camera_choreography": _build_camera_choreography(
                        sequence_id="retinal_input_to_subset_context",
                        focus_pane_id=CIRCUIT_PANE_ID,
                        anchor_id="active_subset_cluster",
                        framing_mode="cluster_focus",
                        transition_id="retinal_input_to_subset_cluster",
                        transition_kind="orbit_focus",
                        duration_ms=680,
                        hold_duration_ms=1500,
                        easing="ease_in_out_sine",
                        from_anchor_id="retinal_input_hold",
                        linked_pane_ids=[CIRCUIT_PANE_ID, MORPHOLOGY_PANE_ID],
                        narration_lead_in_ms=120,
                        annotation_stagger_ms=260,
                        target_root_ids=selected_root_ids,
                    ),
                    "annotation_layout": _build_annotation_layout(
                        layout_id="subset_context_annotations",
                        focus_pane_id=CIRCUIT_PANE_ID,
                        placements=[
                            _build_annotation_placement(
                                annotation_id=STORY_CONTEXT_ANNOTATION_ID,
                                pane_id=CIRCUIT_PANE_ID,
                                placement="hero_top_left",
                                alignment="start",
                                delay_ms=120,
                            ),
                            _build_annotation_placement(
                                annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID,
                                pane_id=MORPHOLOGY_PANE_ID,
                                placement="pane_footer",
                                alignment="end",
                                delay_ms=760,
                            ),
                        ],
                    ),
                    "presentation_links": [
                        _build_presentation_link(
                            link_id="input_surface_to_active_subset",
                            link_kind="subset_story_binding",
                            source_pane_id=SCENE_PANE_ID,
                            target_pane_ids=[CIRCUIT_PANE_ID, MORPHOLOGY_PANE_ID],
                            shared_context={
                                **scene_surface,
                                "surface_kind": str(
                                    narrative_context["input_surface"]["surface_kind"]
                                ),
                                "selected_root_ids": selected_root_ids,
                                "selected_neuron_id": selected_neuron_id,
                            },
                        )
                    ],
                    "emphasis_state": _build_emphasis_state(
                        emphasis_id="active_subset_selection",
                        emphasis_kind="subset_context",
                        linked_pane_ids=[CIRCUIT_PANE_ID, MORPHOLOGY_PANE_ID],
                        overlay_ids_by_pane={
                            CIRCUIT_PANE_ID: [subset_overlay_id],
                            MORPHOLOGY_PANE_ID: [subset_overlay_id],
                        },
                        focus_root_ids=selected_root_ids,
                        selected_neuron_id=selected_neuron_id,
                        scene_surface=scene_surface,
                    ),
                    "showcase_ui_state": _build_showcase_ui_state(
                        mode_id="subset_context_showcase",
                        primary_pane_id=CIRCUIT_PANE_ID,
                        support_pane_ids=[MORPHOLOGY_PANE_ID, SCENE_PANE_ID],
                        inspection_escape_hatch=dashboard_escape_hatch,
                        guided_variant={
                            "chrome_treatment": "subset_focus",
                            "visible_control_groups": [
                                "story_header",
                                "story_annotations",
                                "inspection_escape_hatch",
                            ],
                            "suppressed_control_groups": [
                                "comparison_controls",
                                "overlay_controls",
                                "playback_transport",
                                "readout_detail_controls",
                                "time_scrub",
                            ],
                            "reorganized_control_groups": ["subset_focus_controls"],
                            "inspection_panel_state": "collapsed",
                        },
                        rehearsal_variant={
                            "chrome_treatment": "subset_focus_rehearsal",
                            "visible_control_groups": [
                                "story_header",
                                "story_annotations",
                                "inspection_escape_hatch",
                                "inspection_drawer",
                            ],
                            "suppressed_control_groups": ["comparison_controls"],
                            "reorganized_control_groups": [
                                "subset_focus_controls",
                                "overlay_controls",
                                "neuron_detail_controls",
                            ],
                            "inspection_panel_state": "peek",
                        },
                    ),
                },
                "dashboard_state_patch": {
                    "global_interaction_state": {
                        "active_overlay_id": subset_overlay_id,
                        "selected_neuron_id": selected_neuron_id,
                    },
                    "replay_state": {
                        "active_overlay_id": subset_overlay_id,
                        "selected_neuron_id": selected_neuron_id,
                    },
                },
            },
        },
        PROPAGATION_REPLAY_PRESET_ID: {
            "step_id": ACTIVITY_PROPAGATION_STEP_ID,
            "display_name": "Propagation Replay",
            "note": "Use the shared replay cursor on the matched baseline-versus-wave surface.",
            "presentation_status": PRESENTATION_STATUS_READY,
            "presentation_state_patch": {
                "active_pane_id": TIME_SERIES_PANE_ID,
                "focus_root_ids": selected_root_preview,
                "scene_surface": copy.deepcopy(dict(scene_surface)),
                "rehearsal_metadata": {
                    "fixture_mode": fixture_mode,
                    "story_role": "propagation_view",
                    "propagation_view": copy.deepcopy(
                        dict(narrative_context["activity_propagation_views"])
                    ),
                    "camera_anchor": {
                        "anchor_id": "propagation_path_follow",
                        "framing_mode": "signal_follow",
                        "target_root_ids": selected_root_preview,
                    },
                    "camera_choreography": _build_camera_choreography(
                        sequence_id="subset_context_to_propagation",
                        focus_pane_id=TIME_SERIES_PANE_ID,
                        anchor_id="propagation_path_follow",
                        framing_mode="signal_follow",
                        transition_id="subset_cluster_to_propagation",
                        transition_kind="follow_signal",
                        duration_ms=760,
                        hold_duration_ms=1800,
                        easing="ease_in_out_quad",
                        from_anchor_id="active_subset_cluster",
                        linked_pane_ids=[
                            CIRCUIT_PANE_ID,
                            MORPHOLOGY_PANE_ID,
                            TIME_SERIES_PANE_ID,
                            ANALYSIS_PANE_ID,
                        ],
                        narration_lead_in_ms=140,
                        annotation_stagger_ms=240,
                        target_root_ids=selected_root_preview,
                        recommended_sample_index=recommended_propagation_sample_index,
                        recommended_time_ms=recommended_propagation_time_ms,
                    ),
                    "annotation_layout": _build_annotation_layout(
                        layout_id="propagation_replay_annotations",
                        focus_pane_id=TIME_SERIES_PANE_ID,
                        placements=[
                            _build_annotation_placement(
                                annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID,
                                pane_id=TIME_SERIES_PANE_ID,
                                placement="hero_top_left",
                                alignment="start",
                                delay_ms=140,
                            ),
                            _build_annotation_placement(
                                annotation_id=FAIRNESS_BOUNDARY_ANNOTATION_ID,
                                pane_id=ANALYSIS_PANE_ID,
                                placement="pane_footer",
                                alignment="end",
                                delay_ms=760,
                            ),
                        ],
                    ),
                    "presentation_links": [
                        _build_presentation_link(
                            link_id="subset_to_propagation_view",
                            link_kind="shared_replay_context",
                            source_pane_id=CIRCUIT_PANE_ID,
                            target_pane_ids=[
                                MORPHOLOGY_PANE_ID,
                                TIME_SERIES_PANE_ID,
                                ANALYSIS_PANE_ID,
                            ],
                            shared_context={
                                "selected_root_ids": selected_root_ids,
                                "selected_readout_id": str(selected_readout_id),
                                "comparison_mode": str(
                                    state["replay_state"]["comparison_mode"]
                                ),
                                "shared_timebase_status": copy.deepcopy(
                                    dict(
                                        narrative_context["activity_propagation_views"][
                                            "shared_timebase_status"
                                        ]
                                    )
                                ),
                            },
                        )
                    ],
                    "emphasis_state": _build_emphasis_state(
                        emphasis_id="propagation_replay_focus",
                        emphasis_kind="propagation_view",
                        linked_pane_ids=[
                            MORPHOLOGY_PANE_ID,
                            TIME_SERIES_PANE_ID,
                            ANALYSIS_PANE_ID,
                        ],
                        overlay_ids_by_pane={
                            MORPHOLOGY_PANE_ID: [propagation_overlay_id],
                            TIME_SERIES_PANE_ID: [propagation_overlay_id],
                            ANALYSIS_PANE_ID: [propagation_overlay_id],
                        },
                        focus_root_ids=selected_root_preview,
                        selected_readout_id=str(selected_readout_id),
                    ),
                    "showcase_ui_state": _build_showcase_ui_state(
                        mode_id="propagation_replay_showcase",
                        primary_pane_id=TIME_SERIES_PANE_ID,
                        support_pane_ids=[CIRCUIT_PANE_ID, ANALYSIS_PANE_ID],
                        inspection_escape_hatch=dashboard_escape_hatch,
                        guided_variant={
                            "chrome_treatment": "propagation_focus",
                            "visible_control_groups": [
                                "story_header",
                                "story_annotations",
                                "playback_transport",
                                "time_scrub",
                                "inspection_escape_hatch",
                            ],
                            "suppressed_control_groups": [
                                "comparison_controls",
                                "overlay_controls",
                                "neuron_detail_controls",
                            ],
                            "reorganized_control_groups": ["readout_detail_controls"],
                            "inspection_panel_state": "collapsed",
                        },
                        rehearsal_variant={
                            "chrome_treatment": "propagation_focus_rehearsal",
                            "visible_control_groups": [
                                "story_header",
                                "story_annotations",
                                "playback_transport",
                                "time_scrub",
                                "inspection_escape_hatch",
                                "inspection_drawer",
                            ],
                            "suppressed_control_groups": ["comparison_controls"],
                            "reorganized_control_groups": [
                                "overlay_controls",
                                "readout_detail_controls",
                                "neuron_detail_controls",
                            ],
                            "inspection_panel_state": "peek",
                        },
                    ),
                },
                "dashboard_state_patch": {
                    "global_interaction_state": {
                        "selected_readout_id": selected_readout_id,
                        "comparison_mode": state["replay_state"]["comparison_mode"],
                        "active_overlay_id": propagation_overlay_id,
                    },
                    "replay_state": {
                        "selected_readout_id": selected_readout_id,
                        "comparison_mode": state["replay_state"]["comparison_mode"],
                        "active_overlay_id": propagation_overlay_id,
                    },
                },
            },
        },
        PAIRED_COMPARISON_PRESET_ID: {
            "step_id": BASELINE_WAVE_COMPARISON_STEP_ID,
            "display_name": "Paired Comparison",
            "note": "Keep the fair paired baseline-versus-wave comparison visible.",
            "presentation_status": PRESENTATION_STATUS_READY,
            "presentation_state_patch": {
                "active_pane_id": ANALYSIS_PANE_ID,
                "focus_root_ids": selected_root_preview,
                "rehearsal_metadata": {
                    "fixture_mode": fixture_mode,
                    "story_role": "comparison_pairing",
                    "comparison_pairing": copy.deepcopy(
                        dict(narrative_context["approved_comparison_arms"])
                    ),
                    "comparison_act": copy.deepcopy(
                        dict(narrative_context["comparison_act"])
                    ),
                    "presentation_view": copy.deepcopy(
                        dict(narrative_context["comparison_act"])
                    ),
                    "fairness_boundary": copy.deepcopy(
                        dict(narrative_context["comparison_act"]["fairness_boundary"])
                    ),
                    "camera_anchor": {
                        "anchor_id": "paired_comparison_focus",
                        "framing_mode": "paired_analysis_focus",
                        "target_root_ids": selected_root_preview,
                    },
                    "camera_choreography": _build_camera_choreography(
                        sequence_id="propagation_to_paired_comparison",
                        focus_pane_id=ANALYSIS_PANE_ID,
                        anchor_id="paired_comparison_focus",
                        framing_mode="paired_analysis_focus",
                        transition_id="propagation_to_paired_comparison",
                        transition_kind="comparison_lock",
                        duration_ms=720,
                        hold_duration_ms=1650,
                        easing="ease_in_out_quad",
                        from_anchor_id="propagation_path_follow",
                        linked_pane_ids=[TIME_SERIES_PANE_ID, ANALYSIS_PANE_ID],
                        narration_lead_in_ms=120,
                        annotation_stagger_ms=220,
                        target_root_ids=selected_root_preview,
                        recommended_sample_index=recommended_propagation_sample_index,
                        recommended_time_ms=recommended_propagation_time_ms,
                    ),
                    "annotation_layout": _build_annotation_layout(
                        layout_id="paired_comparison_annotations",
                        focus_pane_id=ANALYSIS_PANE_ID,
                        placements=[
                            _build_annotation_placement(
                                annotation_id=FAIRNESS_BOUNDARY_ANNOTATION_ID,
                                pane_id=ANALYSIS_PANE_ID,
                                placement="hero_top_left",
                                alignment="start",
                                delay_ms=120,
                            ),
                            _build_annotation_placement(
                                annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID,
                                pane_id=TIME_SERIES_PANE_ID,
                                placement="pane_footer",
                                alignment="end",
                                delay_ms=680,
                            ),
                        ],
                    ),
                    "presentation_links": [
                        _build_presentation_link(
                            link_id="propagation_to_paired_comparison",
                            link_kind="matched_pair_bridge",
                            source_pane_id=TIME_SERIES_PANE_ID,
                            target_pane_ids=[ANALYSIS_PANE_ID, CIRCUIT_PANE_ID],
                            shared_context={
                                "pairing_id": str(
                                    narrative_context["comparison_act"]["pairing_id"]
                                ),
                                "selected_readout_id": str(selected_readout_id),
                                "shared_timebase_signature": str(
                                    narrative_context["comparison_act"][
                                        "stable_pairing_semantics"
                                    ]["shared_timebase_signature"]
                                ),
                                "content_scope_label": _SHARED_COMPARISON_SCOPE_LABEL,
                            },
                        )
                    ],
                    "emphasis_state": _build_emphasis_state(
                        emphasis_id="paired_comparison_focus",
                        emphasis_kind="comparison_act",
                        linked_pane_ids=[TIME_SERIES_PANE_ID, ANALYSIS_PANE_ID],
                        overlay_ids_by_pane={
                            TIME_SERIES_PANE_ID: [comparison_overlay_id],
                            ANALYSIS_PANE_ID: [comparison_overlay_id],
                        },
                        focus_root_ids=selected_root_preview,
                        selected_readout_id=str(selected_readout_id),
                    ),
                    "showcase_ui_state": _build_showcase_ui_state(
                        mode_id="paired_comparison_showcase",
                        primary_pane_id=ANALYSIS_PANE_ID,
                        support_pane_ids=[TIME_SERIES_PANE_ID, CIRCUIT_PANE_ID],
                        inspection_escape_hatch=dashboard_escape_hatch,
                        guided_variant={
                            "chrome_treatment": "paired_comparison_focus",
                            "visible_control_groups": [
                                "story_header",
                                "story_annotations",
                                "comparison_controls",
                                "playback_transport",
                                "time_scrub",
                                "inspection_escape_hatch",
                            ],
                            "suppressed_control_groups": [
                                "overlay_controls",
                                "neuron_detail_controls",
                            ],
                            "reorganized_control_groups": ["readout_detail_controls"],
                            "inspection_panel_state": "collapsed",
                        },
                        rehearsal_variant={
                            "chrome_treatment": "paired_comparison_focus_rehearsal",
                            "visible_control_groups": [
                                "story_header",
                                "story_annotations",
                                "comparison_controls",
                                "playback_transport",
                                "time_scrub",
                                "inspection_escape_hatch",
                                "inspection_drawer",
                            ],
                            "suppressed_control_groups": [],
                            "reorganized_control_groups": [
                                "overlay_controls",
                                "readout_detail_controls",
                                "neuron_detail_controls",
                            ],
                            "inspection_panel_state": "peek",
                        },
                    ),
                },
                "dashboard_state_patch": {
                    "global_interaction_state": {
                        "comparison_mode": PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
                        "selected_readout_id": selected_readout_id,
                        "active_overlay_id": comparison_overlay_id,
                    },
                    "replay_state": {
                        "comparison_mode": PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
                        "selected_readout_id": selected_readout_id,
                        "active_overlay_id": comparison_overlay_id,
                    },
                },
            },
        },
        APPROVED_HIGHLIGHT_PRESET_ID: {
            "step_id": APPROVED_WAVE_HIGHLIGHT_STEP_ID,
            "display_name": "Approved Highlight",
            "note": "Focus the wave-only phenomenon only on the approved single-arm view.",
            "presentation_status": str(
                narrative_context["highlight_selection"]["presentation_status"]
            ),
            "presentation_state_patch": {
                "active_pane_id": ANALYSIS_PANE_ID,
                "focus_root_ids": selected_root_ids[:1],
                "highlight_selection": copy.deepcopy(
                    dict(narrative_context["highlight_selection"])
                ),
                "rehearsal_metadata": {
                    "fixture_mode": fixture_mode,
                    "story_role": "highlight_phenomenon_reference",
                    "highlight_metadata": copy.deepcopy(
                        dict(narrative_context["highlight_selection"])
                    ),
                    "highlight_presentation": copy.deepcopy(
                        dict(narrative_context["highlight_presentation"])
                    ),
                    "presentation_view": copy.deepcopy(
                        dict(narrative_context["highlight_presentation"])
                    ),
                    "fairness_boundary": copy.deepcopy(
                        dict(narrative_context["highlight_presentation"]["fairness_boundary"])
                    ),
                    "camera_anchor": {
                        "anchor_id": "approved_wave_highlight_focus",
                        "framing_mode": "wave_only_focus",
                        "target_root_ids": selected_root_preview,
                    },
                    "camera_choreography": _build_camera_choreography(
                        sequence_id="paired_comparison_to_wave_highlight",
                        focus_pane_id=ANALYSIS_PANE_ID,
                        anchor_id="approved_wave_highlight_focus",
                        framing_mode="wave_only_focus",
                        transition_id="paired_comparison_to_wave_highlight",
                        transition_kind="single_arm_focus",
                        duration_ms=660,
                        hold_duration_ms=1550,
                        easing="ease_in_out_sine",
                        from_anchor_id="paired_comparison_focus",
                        linked_pane_ids=[TIME_SERIES_PANE_ID, ANALYSIS_PANE_ID],
                        narration_lead_in_ms=120,
                        annotation_stagger_ms=220,
                        target_root_ids=selected_root_preview,
                    ),
                    "annotation_layout": _build_annotation_layout(
                        layout_id="approved_wave_highlight_annotations",
                        focus_pane_id=ANALYSIS_PANE_ID,
                        placements=[
                            _build_annotation_placement(
                                annotation_id=SCIENTIFIC_GUARDRAIL_ANNOTATION_ID,
                                pane_id=ANALYSIS_PANE_ID,
                                placement="hero_top_left",
                                alignment="start",
                                delay_ms=120,
                            ),
                            _build_annotation_placement(
                                annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID,
                                pane_id=TIME_SERIES_PANE_ID,
                                placement="pane_footer",
                                alignment="end",
                                delay_ms=700,
                            ),
                        ],
                    ),
                    "presentation_links": [
                        _build_presentation_link(
                            link_id="paired_comparison_to_wave_highlight",
                            link_kind="wave_only_diagnostic_bridge",
                            source_pane_id=ANALYSIS_PANE_ID,
                            target_pane_ids=[TIME_SERIES_PANE_ID],
                            shared_context={
                                "pairing_id": str(
                                    narrative_context["comparison_act"]["pairing_id"]
                                ),
                                "phenomenon_id": str(
                                    narrative_context["highlight_selection"]["phenomenon_id"]
                                ),
                                "content_scope_label": str(
                                    narrative_context["highlight_presentation"][
                                        "active_scope_label"
                                    ]
                                ),
                            },
                        )
                    ],
                    "emphasis_state": _build_emphasis_state(
                        emphasis_id="approved_wave_highlight_focus",
                        emphasis_kind="wave_highlight",
                        linked_pane_ids=[TIME_SERIES_PANE_ID, ANALYSIS_PANE_ID],
                        overlay_ids_by_pane={
                            TIME_SERIES_PANE_ID: [highlight_overlay_id],
                            ANALYSIS_PANE_ID: [highlight_overlay_id],
                        },
                        focus_root_ids=selected_root_preview,
                        selected_readout_id=str(selected_readout_id),
                    ),
                    "showcase_ui_state": _build_showcase_ui_state(
                        mode_id="approved_wave_highlight_showcase",
                        primary_pane_id=ANALYSIS_PANE_ID,
                        support_pane_ids=[TIME_SERIES_PANE_ID, CIRCUIT_PANE_ID],
                        inspection_escape_hatch=dashboard_escape_hatch,
                        guided_variant={
                            "chrome_treatment": "wave_highlight_focus",
                            "visible_control_groups": [
                                "story_header",
                                "story_annotations",
                                "inspection_escape_hatch",
                            ],
                            "suppressed_control_groups": [
                                "comparison_controls",
                                "overlay_controls",
                                "playback_transport",
                                "time_scrub",
                                "readout_detail_controls",
                                "neuron_detail_controls",
                            ],
                            "reorganized_control_groups": [],
                            "inspection_panel_state": "collapsed",
                        },
                        rehearsal_variant={
                            "chrome_treatment": "wave_highlight_focus_rehearsal",
                            "visible_control_groups": [
                                "story_header",
                                "story_annotations",
                                "inspection_escape_hatch",
                                "inspection_drawer",
                            ],
                            "suppressed_control_groups": ["comparison_controls"],
                            "reorganized_control_groups": [
                                "overlay_controls",
                                "readout_detail_controls",
                            ],
                            "inspection_panel_state": "peek",
                        },
                    ),
                },
                "dashboard_state_patch": {
                    "global_interaction_state": {
                        "comparison_mode": SINGLE_ARM_COMPARISON_MODE,
                        "selected_arm_pair": {
                            "active_arm_id": str(active_arm_pair["wave_arm_id"]),
                        },
                        "selected_readout_id": selected_readout_id,
                        "active_overlay_id": highlight_overlay_id,
                    },
                    "replay_state": {
                        "comparison_mode": SINGLE_ARM_COMPARISON_MODE,
                        "selected_arm_pair": {
                            "active_arm_id": str(active_arm_pair["wave_arm_id"]),
                        },
                        "selected_readout_id": selected_readout_id,
                        "active_overlay_id": highlight_overlay_id,
                    },
                },
            },
        },
        HIGHLIGHT_FALLBACK_PRESET_ID: {
            "step_id": APPROVED_WAVE_HIGHLIGHT_STEP_ID,
            "display_name": "Highlight Fallback",
            "note": "Redirect to the fair comparison when the highlight cannot be shown honestly.",
            "presentation_status": PRESENTATION_STATUS_FALLBACK,
            "presentation_state_patch": {
                "active_pane_id": ANALYSIS_PANE_ID,
                "focus_root_ids": selected_root_preview,
                "highlight_selection": copy.deepcopy(
                    dict(narrative_context["highlight_selection"])
                ),
                "rehearsal_metadata": {
                    "fixture_mode": fixture_mode,
                    "story_role": "highlight_fallback",
                    "highlight_metadata": copy.deepcopy(
                        dict(narrative_context["highlight_selection"])
                    ),
                    "highlight_presentation": copy.deepcopy(
                        dict(narrative_context["highlight_presentation"])
                    ),
                    "presentation_view": copy.deepcopy(
                        dict(narrative_context["highlight_presentation"])
                    ),
                    "fairness_boundary": copy.deepcopy(
                        dict(narrative_context["highlight_presentation"]["fairness_boundary"])
                    ),
                    "camera_anchor": {
                        "anchor_id": "wave_highlight_fallback_return",
                        "framing_mode": "paired_return",
                        "target_root_ids": selected_root_preview,
                    },
                    "camera_choreography": _build_camera_choreography(
                        sequence_id="wave_highlight_fallback_return",
                        focus_pane_id=ANALYSIS_PANE_ID,
                        anchor_id="wave_highlight_fallback_return",
                        framing_mode="paired_return",
                        transition_id="wave_highlight_fallback_return",
                        transition_kind="fallback_return",
                        duration_ms=540,
                        hold_duration_ms=1500,
                        easing="ease_in_out_quad",
                        from_anchor_id="paired_comparison_focus",
                        linked_pane_ids=[TIME_SERIES_PANE_ID, ANALYSIS_PANE_ID],
                        narration_lead_in_ms=100,
                        annotation_stagger_ms=220,
                        target_root_ids=selected_root_preview,
                    ),
                    "annotation_layout": _build_annotation_layout(
                        layout_id="wave_highlight_fallback_annotations",
                        focus_pane_id=ANALYSIS_PANE_ID,
                        placements=[
                            _build_annotation_placement(
                                annotation_id=SCIENTIFIC_GUARDRAIL_ANNOTATION_ID,
                                pane_id=ANALYSIS_PANE_ID,
                                placement="hero_top_left",
                                alignment="start",
                                delay_ms=100,
                            ),
                            _build_annotation_placement(
                                annotation_id=FALLBACK_NOTICE_ANNOTATION_ID,
                                pane_id=ANALYSIS_PANE_ID,
                                placement="hero_bottom_left",
                                alignment="start",
                                delay_ms=620,
                            ),
                            _build_annotation_placement(
                                annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID,
                                pane_id=TIME_SERIES_PANE_ID,
                                placement="pane_footer",
                                alignment="end",
                                delay_ms=860,
                            ),
                        ],
                    ),
                    "presentation_links": [
                        _build_presentation_link(
                            link_id="wave_highlight_fallback_to_paired_comparison",
                            link_kind="highlight_fallback_return",
                            source_pane_id=ANALYSIS_PANE_ID,
                            target_pane_ids=[TIME_SERIES_PANE_ID],
                            shared_context={
                                "pairing_id": str(
                                    narrative_context["comparison_act"]["pairing_id"]
                                ),
                                "fallback_step_id": str(
                                    narrative_context["highlight_selection"][
                                        "fallback_path"
                                    ]["fallback_step_id"]
                                ),
                                "content_scope_label": _SHARED_COMPARISON_SCOPE_LABEL,
                            },
                        )
                    ],
                    "emphasis_state": _build_emphasis_state(
                        emphasis_id="wave_highlight_fallback_focus",
                        emphasis_kind="highlight_fallback",
                        linked_pane_ids=[TIME_SERIES_PANE_ID, ANALYSIS_PANE_ID],
                        overlay_ids_by_pane={
                            TIME_SERIES_PANE_ID: [comparison_overlay_id],
                            ANALYSIS_PANE_ID: [comparison_overlay_id],
                        },
                        focus_root_ids=selected_root_preview,
                        selected_readout_id=str(selected_readout_id),
                    ),
                    "showcase_ui_state": _build_showcase_ui_state(
                        mode_id="wave_highlight_fallback_showcase",
                        primary_pane_id=ANALYSIS_PANE_ID,
                        support_pane_ids=[TIME_SERIES_PANE_ID, CIRCUIT_PANE_ID],
                        inspection_escape_hatch=dashboard_escape_hatch,
                        guided_variant={
                            "chrome_treatment": "highlight_fallback",
                            "visible_control_groups": [
                                "story_header",
                                "story_annotations",
                                "comparison_controls",
                                "inspection_escape_hatch",
                            ],
                            "suppressed_control_groups": [
                                "overlay_controls",
                                "playback_transport",
                                "time_scrub",
                                "neuron_detail_controls",
                            ],
                            "reorganized_control_groups": ["readout_detail_controls"],
                            "inspection_panel_state": "collapsed",
                        },
                        rehearsal_variant={
                            "chrome_treatment": "highlight_fallback_rehearsal",
                            "visible_control_groups": [
                                "story_header",
                                "story_annotations",
                                "comparison_controls",
                                "inspection_escape_hatch",
                                "inspection_drawer",
                            ],
                            "suppressed_control_groups": [],
                            "reorganized_control_groups": [
                                "overlay_controls",
                                "readout_detail_controls",
                                "neuron_detail_controls",
                            ],
                            "inspection_panel_state": "peek",
                        },
                    ),
                },
                "dashboard_state_patch": {
                    "global_interaction_state": {
                        "comparison_mode": PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
                        "selected_readout_id": selected_readout_id,
                        "active_overlay_id": comparison_overlay_id,
                    },
                    "replay_state": {
                        "comparison_mode": PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
                        "selected_readout_id": selected_readout_id,
                        "active_overlay_id": comparison_overlay_id,
                    },
                },
            },
        },
        ANALYSIS_SUMMARY_PRESET_ID: {
            "step_id": SUMMARY_ANALYSIS_STEP_ID,
            "display_name": "Analysis Summary",
            "note": "Close on packaged analysis and review-facing evidence.",
            "presentation_status": PRESENTATION_STATUS_READY,
            "presentation_state_patch": {
                "active_pane_id": ANALYSIS_PANE_ID,
                "focus_root_ids": selected_root_preview,
                "rehearsal_metadata": {
                    "fixture_mode": fixture_mode,
                    "story_role": "final_analysis_landing",
                    "analysis_landing": {
                        "analysis_summary_locator": str(
                            narrative_context["closing_analysis_assets"][
                                "analysis_summary_locator"
                            ]
                        ),
                        "suite_summary_table_path": narrative_context[
                            "closing_analysis_assets"
                        ]["suite_summary_table_path"],
                        "suite_comparison_plot_path": narrative_context[
                            "closing_analysis_assets"
                        ]["suite_comparison_plot_path"],
                        "suite_review_artifact_path": narrative_context[
                            "closing_analysis_assets"
                        ]["suite_review_artifact_path"],
                        "validation_summary_path": narrative_context[
                            "closing_analysis_assets"
                        ]["validation_summary_path"],
                        "validation_findings_path": narrative_context[
                            "closing_analysis_assets"
                        ]["validation_findings_path"],
                        "validation_review_handoff_path": narrative_context[
                            "closing_analysis_assets"
                        ]["validation_review_handoff_path"],
                    },
                    "summary_analysis_landing": copy.deepcopy(
                        dict(narrative_context["summary_analysis_landing"])
                    ),
                    "presentation_view": copy.deepcopy(
                        dict(narrative_context["summary_analysis_landing"])
                    ),
                    "fairness_boundary": copy.deepcopy(
                        dict(narrative_context["comparison_act"]["fairness_boundary"])
                    ),
                    "camera_anchor": {
                        "anchor_id": "analysis_summary_close",
                        "framing_mode": "closing_analysis_focus",
                        "target_root_ids": selected_root_preview,
                    },
                    "camera_choreography": _build_camera_choreography(
                        sequence_id="wave_highlight_to_analysis_summary",
                        focus_pane_id=ANALYSIS_PANE_ID,
                        anchor_id="analysis_summary_close",
                        framing_mode="closing_analysis_focus",
                        transition_id="wave_highlight_to_analysis_summary",
                        transition_kind="summary_lock",
                        duration_ms=620,
                        hold_duration_ms=1800,
                        easing="ease_in_out_cubic",
                        from_anchor_id="approved_wave_highlight_focus",
                        linked_pane_ids=[TIME_SERIES_PANE_ID, ANALYSIS_PANE_ID],
                        narration_lead_in_ms=120,
                        annotation_stagger_ms=220,
                        target_root_ids=selected_root_preview,
                    ),
                    "annotation_layout": _build_annotation_layout(
                        layout_id="analysis_summary_annotations",
                        focus_pane_id=ANALYSIS_PANE_ID,
                        placements=[
                            _build_annotation_placement(
                                annotation_id=STORY_CONTEXT_ANNOTATION_ID,
                                pane_id=ANALYSIS_PANE_ID,
                                placement="hero_top_left",
                                alignment="start",
                                delay_ms=120,
                            ),
                            _build_annotation_placement(
                                annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID,
                                pane_id=ANALYSIS_PANE_ID,
                                placement="pane_footer",
                                alignment="end",
                                delay_ms=640,
                            ),
                        ],
                    ),
                    "presentation_links": [
                        _build_presentation_link(
                            link_id="analysis_summary_evidence_trace",
                            link_kind="summary_evidence_trace",
                            source_pane_id=ANALYSIS_PANE_ID,
                            target_pane_ids=[TIME_SERIES_PANE_ID, CIRCUIT_PANE_ID],
                            shared_context={
                                "pairing_id": str(
                                    narrative_context["comparison_act"]["pairing_id"]
                                ),
                                "highlight_status": str(
                                    narrative_context["highlight_presentation"][
                                        "presentation_status"
                                    ]
                                ),
                                "analysis_summary_locator": str(
                                    narrative_context["closing_analysis_assets"][
                                        "analysis_summary_locator"
                                    ]
                                ),
                            },
                        ),
                        _build_presentation_link(
                            link_id="analysis_summary_to_whole_brain_context",
                            link_kind=WHOLE_BRAIN_CONTEXT_HANDOFF_LINK_KIND,
                            source_pane_id=ANALYSIS_PANE_ID,
                            target_pane_ids=[ANALYSIS_PANE_ID, CIRCUIT_PANE_ID],
                            shared_context={
                                "target_contract_version": "whole_brain_context_session.v1",
                                "target_context_preset_id": WHOLE_BRAIN_CONTEXT_SHOWCASE_HANDOFF_PRESET_ID,
                                "discovery_note": (
                                    "Resolve the linked Milestone 17 context package and "
                                    "open its showcase_handoff preset instead of rebuilding "
                                    "context-query logic inside the showcase layer."
                                ),
                            },
                        ),
                    ],
                    "emphasis_state": _build_emphasis_state(
                        emphasis_id="analysis_summary_focus",
                        emphasis_kind="summary_analysis",
                        linked_pane_ids=[ANALYSIS_PANE_ID, TIME_SERIES_PANE_ID],
                        overlay_ids_by_pane={
                            ANALYSIS_PANE_ID: [summary_overlay_id],
                            TIME_SERIES_PANE_ID: [comparison_overlay_id],
                        },
                        focus_root_ids=selected_root_preview,
                        selected_readout_id=str(selected_readout_id),
                    ),
                    "showcase_ui_state": _build_showcase_ui_state(
                        mode_id="analysis_summary_showcase",
                        primary_pane_id=ANALYSIS_PANE_ID,
                        support_pane_ids=[TIME_SERIES_PANE_ID, CIRCUIT_PANE_ID],
                        inspection_escape_hatch=dashboard_escape_hatch,
                        guided_variant={
                            "chrome_treatment": "analysis_summary_focus",
                            "visible_control_groups": [
                                "story_header",
                                "story_annotations",
                                "inspection_escape_hatch",
                            ],
                            "suppressed_control_groups": [
                                "comparison_controls",
                                "overlay_controls",
                                "playback_transport",
                                "time_scrub",
                                "neuron_detail_controls",
                            ],
                            "reorganized_control_groups": ["readout_detail_controls"],
                            "inspection_panel_state": "collapsed",
                        },
                        rehearsal_variant={
                            "chrome_treatment": "analysis_summary_focus_rehearsal",
                            "visible_control_groups": [
                                "story_header",
                                "story_annotations",
                                "inspection_escape_hatch",
                                "inspection_drawer",
                            ],
                            "suppressed_control_groups": ["comparison_controls"],
                            "reorganized_control_groups": [
                                "overlay_controls",
                                "readout_detail_controls",
                                "neuron_detail_controls",
                            ],
                            "inspection_panel_state": "peek",
                        },
                    ),
                },
                "dashboard_state_patch": {
                    "global_interaction_state": {
                        "selected_readout_id": selected_readout_id,
                        "active_overlay_id": summary_overlay_id,
                    },
                    "replay_state": {
                        "selected_readout_id": selected_readout_id,
                        "active_overlay_id": summary_overlay_id,
                    },
                },
            },
        },
    }

    overrides = _normalize_saved_preset_overrides(saved_preset_overrides)
    presets: list[dict[str, Any]] = []
    for preset_id, default_record in step_defaults.items():
        override = overrides.get(preset_id, {})
        merged_patch = _deep_merge(
            default_record["presentation_state_patch"],
            override.get("presentation_state_patch", {}),
        )
        validate_presentation_state_patch(
            preset_id=preset_id,
            patch=merged_patch,
            dashboard_payload=payload,
        )
        presets.append(
            build_showcase_saved_preset(
                preset_id=preset_id,
                step_id=str(default_record["step_id"]),
                display_name=str(override.get("display_name", default_record["display_name"])),
                note=(
                    None
                    if override.get("note", default_record["note"]) is None
                    else str(override.get("note", default_record["note"]))
                ),
                presentation_status=str(
                    override.get("presentation_status", default_record["presentation_status"])
                ),
                source_artifact_role_id=str(
                    override.get("source_artifact_role_id", DASHBOARD_SESSION_STATE_ROLE_ID)
                ),
                presentation_state_patch=merged_patch,
            )
        )
    return presets


def build_showcase_steps(
    *,
    narrative_context: Mapping[str, Any],
    suite_context: Mapping[str, Any] | None,
    enabled_export_target_role_ids: Sequence[str] | None,
    default_export_target_role_id: str,
    contract_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    enabled_exports = set(
        enabled_export_target_role_ids
        if enabled_export_target_role_ids is not None
        else [
            item["export_target_role_id"]
            for item in discover_showcase_export_target_roles(contract_metadata)
        ]
    )
    if default_export_target_role_id not in enabled_exports:
        raise ValueError(
            "default_export_target_role_id must be enabled for the showcase session."
        )

    highlight_ready = (
        str(narrative_context["highlight_selection"]["presentation_status"])
        == PRESENTATION_STATUS_READY
    )
    suite_summary_available = (
        suite_context is not None and suite_context.get("summary_table_artifact") is not None
    )
    summary_evidence_role = SUITE_SUMMARY_TABLE_ROLE_ID if suite_summary_available else None
    highlight_preset_id = (
        APPROVED_HIGHLIGHT_PRESET_ID if highlight_ready else HIGHLIGHT_FALLBACK_PRESET_ID
    )
    highlight_cue_kind_id = (
        NARRATION_CALLOUT_CUE_KIND_ID if highlight_ready else FALLBACK_REDIRECT_CUE_KIND_ID
    )
    highlight_status = str(narrative_context["highlight_selection"]["presentation_status"])

    steps = [
        build_showcase_step(
            step_id=SCENE_SELECTION_STEP_ID,
            preset_id=SCENE_CONTEXT_PRESET_ID,
            cue_kind_id=CAMERA_TRANSITION_CUE_KIND_ID,
            presentation_status=PRESENTATION_STATUS_READY,
            narrative_annotations=[
                build_showcase_narrative_annotation(
                    annotation_id=STORY_CONTEXT_ANNOTATION_ID,
                    text="Open on the packaged visual scene that anchors the story.",
                    linked_evidence_role_ids=[SCENE_CONTEXT_EVIDENCE_ROLE_ID],
                ),
                build_showcase_narrative_annotation(
                    annotation_id="operator_prompt",
                    text="Load the opening preset before starting the sequence.",
                ),
            ],
            evidence_references=[
                build_showcase_evidence_reference(
                    evidence_role_id=SCENE_CONTEXT_EVIDENCE_ROLE_ID,
                    artifact_role_id=DASHBOARD_SESSION_METADATA_ROLE_ID,
                    citation_label="Dashboard session metadata",
                    locator="manifest_reference",
                ),
            ],
            operator_control_ids=["start_script", "load_preset"],
            export_target_role_ids=_step_exports(
                [HERO_FRAME_EXPORT_TARGET_ROLE_ID],
                enabled_exports=enabled_exports,
                step_id=SCENE_SELECTION_STEP_ID,
            ),
        ),
        build_showcase_step(
            step_id=FLY_VIEW_INPUT_STEP_ID,
            preset_id=RETINAL_INPUT_FOCUS_PRESET_ID,
            cue_kind_id=PLAYBACK_SCRUB_CUE_KIND_ID,
            presentation_status=PRESENTATION_STATUS_READY,
            narrative_annotations=[
                build_showcase_narrative_annotation(
                    annotation_id=INPUT_SAMPLING_ANNOTATION_ID,
                    text="Show the fly-view or sampled-input surface before switching to the circuit.",
                    linked_evidence_role_ids=[INPUT_CONTEXT_EVIDENCE_ROLE_ID],
                ),
                build_showcase_narrative_annotation(
                    annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID,
                    text="This beat reuses the packaged dashboard replay surface.",
                    linked_evidence_role_ids=[INPUT_CONTEXT_EVIDENCE_ROLE_ID],
                ),
            ],
            evidence_references=[
                build_showcase_evidence_reference(
                    evidence_role_id=INPUT_CONTEXT_EVIDENCE_ROLE_ID,
                    artifact_role_id=DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
                    citation_label="Dashboard session payload",
                    locator="pane_inputs.scene",
                ),
            ],
            operator_control_ids=["pause_script", "scrub_time"],
            export_target_role_ids=_step_exports(
                [HERO_FRAME_EXPORT_TARGET_ROLE_ID],
                enabled_exports=enabled_exports,
                step_id=FLY_VIEW_INPUT_STEP_ID,
            ),
        ),
        build_showcase_step(
            step_id=ACTIVE_VISUAL_SUBSET_STEP_ID,
            preset_id=SUBSET_CONTEXT_PRESET_ID,
            cue_kind_id=OVERLAY_REVEAL_CUE_KIND_ID,
            presentation_status=PRESENTATION_STATUS_READY,
            narrative_annotations=[
                build_showcase_narrative_annotation(
                    annotation_id=STORY_CONTEXT_ANNOTATION_ID,
                    text="Bring the active subset and focus neuron into view.",
                    linked_evidence_role_ids=[SUBSET_CONTEXT_EVIDENCE_ROLE_ID],
                ),
                build_showcase_narrative_annotation(
                    annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID,
                    text="Subset context stays anchored to the packaged dashboard state.",
                    linked_evidence_role_ids=[SUBSET_CONTEXT_EVIDENCE_ROLE_ID],
                ),
            ],
            evidence_references=[
                build_showcase_evidence_reference(
                    evidence_role_id=SUBSET_CONTEXT_EVIDENCE_ROLE_ID,
                    artifact_role_id=DASHBOARD_SESSION_STATE_ROLE_ID,
                    citation_label="Dashboard session state",
                    locator="global_interaction_state.selected_neuron_id",
                ),
            ],
            operator_control_ids=["load_preset", "next_step"],
            export_target_role_ids=_step_exports(
                [HERO_FRAME_EXPORT_TARGET_ROLE_ID],
                enabled_exports=enabled_exports,
                step_id=ACTIVE_VISUAL_SUBSET_STEP_ID,
            ),
        ),
        build_showcase_step(
            step_id=ACTIVITY_PROPAGATION_STEP_ID,
            preset_id=PROPAGATION_REPLAY_PRESET_ID,
            cue_kind_id=PLAYBACK_SCRUB_CUE_KIND_ID,
            presentation_status=PRESENTATION_STATUS_READY,
            narrative_annotations=[
                build_showcase_narrative_annotation(
                    annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID,
                    text="Replay on the matched shared-timebase surface.",
                    linked_evidence_role_ids=[SCENE_CONTEXT_EVIDENCE_ROLE_ID, INPUT_CONTEXT_EVIDENCE_ROLE_ID],
                ),
                build_showcase_narrative_annotation(
                    annotation_id=FAIRNESS_BOUNDARY_ANNOTATION_ID,
                    text="Keep this beat on the fair paired-comparison surface.",
                    linked_evidence_role_ids=[SUMMARY_ANALYSIS_EVIDENCE_ROLE_ID],
                ),
            ],
            evidence_references=[
                build_showcase_evidence_reference(
                    evidence_role_id="shared_comparison_evidence",
                    artifact_role_id=ANALYSIS_UI_PAYLOAD_ROLE_ID,
                    citation_label="Analysis UI payload",
                    locator="shared_comparison",
                ),
            ],
            operator_control_ids=["pause_script", "scrub_time"],
            export_target_role_ids=_step_exports(
                [SCRIPTED_CLIP_EXPORT_TARGET_ROLE_ID],
                enabled_exports=enabled_exports,
                step_id=ACTIVITY_PROPAGATION_STEP_ID,
            ),
        ),
        build_showcase_step(
            step_id=BASELINE_WAVE_COMPARISON_STEP_ID,
            preset_id=PAIRED_COMPARISON_PRESET_ID,
            cue_kind_id="comparison_swap",
            presentation_status=PRESENTATION_STATUS_READY,
            narrative_annotations=[
                build_showcase_narrative_annotation(
                    annotation_id=FAIRNESS_BOUNDARY_ANNOTATION_ID,
                    text=(
                        "This beat stays on the shared-comparison surface; "
                        "wave-only diagnostics remain separate."
                    ),
                    linked_evidence_role_ids=["shared_comparison_evidence"],
                ),
                build_showcase_narrative_annotation(
                    annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID,
                    text=(
                        "Pair the shared-comparison payload with suite rollups before "
                        "showing any wave-only diagnostic."
                        if suite_summary_available
                        else (
                            "Pair the shared-comparison payload with packaged experiment "
                            "analysis before any wave-only diagnostic."
                        )
                    ),
                    linked_evidence_role_ids=(
                        ["shared_comparison_evidence", SUITE_ROLLUP_EVIDENCE_ROLE_ID]
                        if suite_summary_available
                        else ["shared_comparison_evidence"]
                    ),
                ),
            ],
            evidence_references=[
                build_showcase_evidence_reference(
                    evidence_role_id="shared_comparison_evidence",
                    artifact_role_id=ANALYSIS_UI_PAYLOAD_ROLE_ID,
                    citation_label="Analysis shared-comparison payload",
                    locator="shared_comparison",
                ),
                *(
                    [
                        build_showcase_evidence_reference(
                            evidence_role_id=SUITE_ROLLUP_EVIDENCE_ROLE_ID,
                            artifact_role_id=SUITE_SUMMARY_TABLE_ROLE_ID,
                            citation_label="Suite summary table",
                            locator="shared_comparison_metrics.summary_table_rows",
                        )
                    ]
                    if summary_evidence_role is not None
                    else []
                ),
            ],
            operator_control_ids=["toggle_comparison", "pause_script"],
            export_target_role_ids=_step_exports(
                [HERO_FRAME_EXPORT_TARGET_ROLE_ID, STORYBOARD_EXPORT_TARGET_ROLE_ID],
                enabled_exports=enabled_exports,
                step_id=BASELINE_WAVE_COMPARISON_STEP_ID,
            ),
        ),
        build_showcase_step(
            step_id=APPROVED_WAVE_HIGHLIGHT_STEP_ID,
            preset_id=highlight_preset_id,
            cue_kind_id=highlight_cue_kind_id,
            presentation_status=highlight_status,
            narrative_annotations=_highlight_annotations(
                highlight_selection=narrative_context["highlight_selection"],
            ),
            evidence_references=[
                build_showcase_evidence_reference(
                    evidence_role_id=APPROVED_WAVE_HIGHLIGHT_EVIDENCE_ROLE_ID,
                    artifact_role_id=str(
                        narrative_context["highlight_selection"]["artifact_role_id"]
                    ),
                    citation_label=str(
                        narrative_context["highlight_selection"]["citation_label"]
                    ),
                    locator=narrative_context["highlight_selection"]["locator"],
                ),
                *(
                    [
                        build_showcase_evidence_reference(
                            evidence_role_id=SUITE_ROLLUP_EVIDENCE_ROLE_ID,
                            artifact_role_id=SUITE_SUMMARY_TABLE_ROLE_ID,
                            citation_label="Suite summary table",
                            locator="shared_comparison_metrics.summary_table_rows",
                            required=False,
                        )
                    ]
                    if summary_evidence_role is not None
                    else []
                ),
                build_showcase_evidence_reference(
                    evidence_role_id=VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
                    artifact_role_id=(
                        VALIDATION_REVIEW_HANDOFF_ROLE_ID
                        if narrative_context["highlight_selection"]
                        .get("supporting_evidence_references", [])
                        and any(
                            str(item.get("artifact_role_id"))
                            == VALIDATION_REVIEW_HANDOFF_ROLE_ID
                            for item in narrative_context["highlight_selection"][
                                "supporting_evidence_references"
                            ]
                        )
                        else VALIDATION_FINDINGS_ROLE_ID
                    ),
                    citation_label=(
                        "Validation review handoff"
                        if narrative_context["highlight_selection"]
                        .get("supporting_evidence_references", [])
                        and any(
                            str(item.get("artifact_role_id"))
                            == VALIDATION_REVIEW_HANDOFF_ROLE_ID
                            for item in narrative_context["highlight_selection"][
                                "supporting_evidence_references"
                            ]
                        )
                        else "Validation findings"
                    ),
                    locator=(
                        "scientific_plausibility_decision"
                        if narrative_context["highlight_selection"]
                        .get("supporting_evidence_references", [])
                        and any(
                            str(item.get("artifact_role_id"))
                            == VALIDATION_REVIEW_HANDOFF_ROLE_ID
                            for item in narrative_context["highlight_selection"][
                                "supporting_evidence_references"
                            ]
                        )
                        else "validator_findings"
                    ),
                ),
            ],
            operator_control_ids=["load_preset", "pause_script"],
            export_target_role_ids=_step_exports(
                [HERO_FRAME_EXPORT_TARGET_ROLE_ID, REVIEW_MANIFEST_EXPORT_TARGET_ROLE_ID],
                enabled_exports=enabled_exports,
                step_id=APPROVED_WAVE_HIGHLIGHT_STEP_ID,
            ),
            fallback_preset_id=HIGHLIGHT_FALLBACK_PRESET_ID,
        ),
        build_showcase_step(
            step_id=SUMMARY_ANALYSIS_STEP_ID,
            preset_id=ANALYSIS_SUMMARY_PRESET_ID,
            cue_kind_id="export_capture",
            presentation_status=PRESENTATION_STATUS_READY,
            narrative_annotations=[
                build_showcase_narrative_annotation(
                    annotation_id=STORY_CONTEXT_ANNOTATION_ID,
                    text=(
                        "Close on a newcomer-readable summary that stays anchored to "
                        "packaged evidence."
                    ),
                    linked_evidence_role_ids=[
                        SUMMARY_ANALYSIS_EVIDENCE_ROLE_ID,
                        VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
                    ],
                ),
                build_showcase_narrative_annotation(
                    annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID,
                    text=(
                        "Anchor the closing beat to analysis, suite, and validation outputs."
                        if suite_summary_available
                        else (
                            "Anchor the closing beat to packaged experiment analysis plus "
                            "validation evidence."
                        )
                    ),
                    linked_evidence_role_ids=(
                        [
                            SUMMARY_ANALYSIS_EVIDENCE_ROLE_ID,
                            SUITE_ROLLUP_EVIDENCE_ROLE_ID,
                            VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
                        ]
                        if suite_summary_available
                        else [
                            SUMMARY_ANALYSIS_EVIDENCE_ROLE_ID,
                            VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
                        ]
                    ),
                ),
            ],
            evidence_references=[
                build_showcase_evidence_reference(
                    evidence_role_id=SUMMARY_ANALYSIS_EVIDENCE_ROLE_ID,
                    artifact_role_id=(
                        ANALYSIS_OFFLINE_REPORT_ROLE_ID
                        if narrative_context["closing_analysis_assets"]["analysis_offline_report_path"]
                        else ANALYSIS_UI_PAYLOAD_ROLE_ID
                    ),
                    citation_label=(
                        "Analysis offline report"
                        if narrative_context["closing_analysis_assets"]["analysis_offline_report_path"]
                        else "Analysis UI payload"
                    ),
                    locator=narrative_context["closing_analysis_assets"]["analysis_summary_locator"],
                ),
                *(
                    [
                        build_showcase_evidence_reference(
                            evidence_role_id=SUITE_ROLLUP_EVIDENCE_ROLE_ID,
                            artifact_role_id=SUITE_SUMMARY_TABLE_ROLE_ID,
                            citation_label="Suite summary table",
                            locator="shared_comparison_metrics.summary_table_rows",
                        )
                    ]
                    if summary_evidence_role is not None
                    else []
                ),
                build_showcase_evidence_reference(
                    evidence_role_id=VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
                    artifact_role_id=(
                        VALIDATION_REVIEW_HANDOFF_ROLE_ID
                        if narrative_context["closing_analysis_assets"][
                            "validation_review_handoff_path"
                        ]
                        is not None
                        else VALIDATION_FINDINGS_ROLE_ID
                    ),
                    citation_label=(
                        "Validation review handoff"
                        if narrative_context["closing_analysis_assets"][
                            "validation_review_handoff_path"
                        ]
                        is not None
                        else "Validation findings"
                    ),
                    locator=(
                        "scientific_plausibility_decision"
                        if narrative_context["closing_analysis_assets"][
                            "validation_review_handoff_path"
                        ]
                        is not None
                        else "validator_findings"
                    ),
                    required=False,
                ),
            ],
            operator_control_ids=["trigger_export", "previous_step"],
            export_target_role_ids=_step_exports(
                [SHOWCASE_STATE_EXPORT_TARGET_ROLE_ID, REVIEW_MANIFEST_EXPORT_TARGET_ROLE_ID],
                enabled_exports=enabled_exports,
                step_id=SUMMARY_ANALYSIS_STEP_ID,
            ),
        ),
    ]
    return steps


def roll_up_presentation_status(
    showcase_steps: Sequence[Mapping[str, Any]],
) -> str:
    statuses = [str(item["presentation_status"]) for item in showcase_steps]
    return min(statuses, key=lambda item: _PRESENTATION_STATUS_PRIORITY[item])


def build_showcase_fixture_profile(
    *,
    fixture_mode: str,
    dashboard_context: Mapping[str, Any],
    suite_context: Mapping[str, Any] | None,
    narrative_context: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "fixture_mode": str(fixture_mode),
        "fixture_id": "milestone16_local_rehearsal",
        "display_name": "Milestone 16 Local Rehearsal",
        "workflow_kind": "local_showcase_rehearsal",
        "keeps_readiness_fixtures_fast": True,
        "uses_packaged_dashboard_session": True,
        "uses_packaged_suite_review": bool(
            suite_context is not None and suite_context.get("summary_table_artifact") is not None
        ),
        "dashboard_origin": str(dashboard_context["origin"]),
        "selected_root_count": int(
            narrative_context["active_subset_focus_targets"]["root_count"]
        ),
        "story_arc_preset_ids": _story_arc_preset_ids(),
    }


def _step_exports(
    export_target_role_ids: Sequence[str],
    *,
    enabled_exports: set[str],
    step_id: str,
) -> list[str]:
    selected = [role_id for role_id in export_target_role_ids if role_id in enabled_exports]
    if not selected:
        raise ValueError(
            f"Showcase step {step_id!r} has no enabled export targets after applying the session export configuration."
        )
    return selected


def _highlight_annotations(
    *,
    highlight_selection: Mapping[str, Any],
) -> list[dict[str, Any]]:
    highlight_ready = (
        str(highlight_selection["presentation_status"]) == PRESENTATION_STATUS_READY
    )
    annotations = [
        build_showcase_narrative_annotation(
            annotation_id=SCIENTIFIC_GUARDRAIL_ANNOTATION_ID,
            text=(
                f"Approved wave-only highlight: {highlight_selection['citation_label']}."
                if highlight_ready
                else "The requested wave-only highlight is not approved for display."
            ),
            linked_evidence_role_ids=[
                APPROVED_WAVE_HIGHLIGHT_EVIDENCE_ROLE_ID,
                VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
            ],
        ),
        build_showcase_narrative_annotation(
            annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID,
            text="Keep the highlight traceable to analysis, suite, and validation artifacts.",
            linked_evidence_role_ids=[
                APPROVED_WAVE_HIGHLIGHT_EVIDENCE_ROLE_ID,
                SUITE_ROLLUP_EVIDENCE_ROLE_ID,
                VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
            ],
        ),
    ]
    if not highlight_ready:
        annotations.append(
            build_showcase_narrative_annotation(
                annotation_id=FALLBACK_NOTICE_ANNOTATION_ID,
                text=str(highlight_selection["fallback_path"]["fallback_explanation"]),
            )
        )
    return annotations


def _highlight_suite_support_references(
    suite_context: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if suite_context is None or suite_context.get("summary_table_artifact") is None:
        return []
    return [
        build_showcase_evidence_reference(
            evidence_role_id=SUITE_ROLLUP_EVIDENCE_ROLE_ID,
            artifact_role_id=SUITE_SUMMARY_TABLE_ROLE_ID,
            citation_label="Suite summary table",
            locator="shared_comparison_metrics.summary_table_rows",
            required=False,
        )
    ]


def _highlight_validation_support_references(
    validation_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    references = [
        build_showcase_evidence_reference(
            evidence_role_id=VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
            artifact_role_id=VALIDATION_FINDINGS_ROLE_ID,
            citation_label="Validation findings",
            locator="validator_findings",
        )
    ]
    if validation_context.get("review_handoff_path") is not None:
        references.append(
            build_showcase_evidence_reference(
                evidence_role_id=VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
                artifact_role_id=VALIDATION_REVIEW_HANDOFF_ROLE_ID,
                citation_label="Validation review handoff",
                locator="scientific_plausibility_decision",
            )
        )
    return references


def _resolve_highlight_source_reference(
    *,
    artifact_role_id: str,
    locator: str | None,
    phase_refs: Sequence[Mapping[str, Any]],
    diagnostic_cards: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if (
        artifact_role_id == ANALYSIS_UI_PAYLOAD_ROLE_ID
        and locator == "wave_only_diagnostics.phase_map_references[0]"
        and phase_refs
    ):
        first_phase = phase_refs[0]
        return {
            "source_kind": "phase_map_reference",
            "bundle_id": str(first_phase.get("bundle_id", "")),
            "arm_id": str(first_phase.get("arm_id", "")),
            "seed": int(first_phase.get("seed", 0)),
            "artifact_id": str(first_phase.get("artifact_id", "")),
            "root_ids": [int(item) for item in first_phase.get("root_ids", [])],
            "path": str(first_phase.get("path", "")),
        }
    if (
        artifact_role_id == ANALYSIS_UI_PAYLOAD_ROLE_ID
        and locator == "wave_only_diagnostics.diagnostic_cards[0]"
        and diagnostic_cards
    ):
        first_card = diagnostic_cards[0]
        return {
            "source_kind": "diagnostic_card",
            "card_id": str(first_card.get("card_id", "")),
            "arm_id": str(first_card.get("arm_id", "")),
            "metric_id": str(first_card.get("metric_id", "")),
            "mean_value": first_card.get("mean_value"),
            "units": str(first_card.get("units", "")),
            "seed_count": int(first_card.get("seed_count", 0)),
        }
    return {
        "source_kind": "explicit_reference",
        "artifact_role_id": str(artifact_role_id),
        "locator": None if locator is None else str(locator),
    }


def _build_highlight_fallback_path(
    *,
    suite_support_references: Sequence[Mapping[str, Any]],
    validation_support_references: Sequence[Mapping[str, Any]],
    fallback_reason: str,
) -> dict[str, Any]:
    return {
        "fallback_step_id": BASELINE_WAVE_COMPARISON_STEP_ID,
        "fallback_preset_id": HIGHLIGHT_FALLBACK_PRESET_ID,
        "cue_kind_id": FALLBACK_REDIRECT_CUE_KIND_ID,
        "fallback_explanation": str(fallback_reason),
        "supporting_evidence_references": [
            build_showcase_evidence_reference(
                evidence_role_id=SHARED_COMPARISON_EVIDENCE_ROLE_ID,
                artifact_role_id=ANALYSIS_UI_PAYLOAD_ROLE_ID,
                citation_label="Analysis shared-comparison payload",
                locator="shared_comparison",
            ),
            *[copy.deepcopy(dict(item)) for item in suite_support_references],
            *[copy.deepcopy(dict(item)) for item in validation_support_references],
        ],
    }


def _story_arc_preset_ids() -> dict[str, str]:
    return {
        "scene_choice": SCENE_CONTEXT_PRESET_ID,
        "fly_view_framing": RETINAL_INPUT_FOCUS_PRESET_ID,
        "active_subset_emphasis": SUBSET_CONTEXT_PRESET_ID,
        "propagation_view": PROPAGATION_REPLAY_PRESET_ID,
        "comparison_pairing": PAIRED_COMPARISON_PRESET_ID,
        "highlight_phenomenon_reference": APPROVED_HIGHLIGHT_PRESET_ID,
        "highlight_fallback": HIGHLIGHT_FALLBACK_PRESET_ID,
        "final_analysis_landing": ANALYSIS_SUMMARY_PRESET_ID,
    }


def _scene_surface_kind(scene_context: Mapping[str, Any]) -> str:
    if str(scene_context["source_kind"]) == "retinal_bundle":
        return "retinal_input"
    return "fly_view"


def _preferred_overlay(available_overlays: set[str], *candidates: str) -> str:
    for candidate in candidates:
        if candidate in available_overlays:
            return candidate
    raise ValueError(
        f"Showcase planning could not find a supported overlay from candidates {candidates!r}."
    )


def _comparison_mode_status_by_id(
    replay_model: Mapping[str, Any],
    *,
    comparison_mode_id: str,
) -> dict[str, Any]:
    for item in _normalize_mapping_sequence(
        replay_model.get("comparison_mode_statuses", []),
        field_name=(
            "dashboard_session_payload.pane_inputs.time_series.replay_model."
            "comparison_mode_statuses"
        ),
    ):
        if str(item["comparison_mode_id"]) == comparison_mode_id:
            return item
    return {
        "comparison_mode_id": str(comparison_mode_id),
        "availability": "unavailable",
        "reason": "comparison_mode_statuses does not list the requested comparison mode",
    }


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, Mapping) and isinstance(override, Mapping):
        merged = {str(key): copy.deepcopy(value) for key, value in base.items()}
        for key, value in override.items():
            merged[str(key)] = _deep_merge(merged.get(str(key)), value)
        return merged
    return copy.deepcopy(override)


def _normalize_mapping_sequence(
    payload: Sequence[Mapping[str, Any]],
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of mappings.")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name}[{index}] must be a mapping.")
        result.append(copy.deepcopy(dict(item)))
    return result


def _require_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return copy.deepcopy(dict(value))
