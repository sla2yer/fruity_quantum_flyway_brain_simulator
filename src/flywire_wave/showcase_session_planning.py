from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .config import get_config_path, get_project_root, load_config
from .dashboard_session_contract import (
    ANALYSIS_BUNDLE_METADATA_ROLE_ID as DASHBOARD_ANALYSIS_BUNDLE_METADATA_ROLE_ID,
    ANALYSIS_PANE_ID,
    CIRCUIT_PANE_ID,
    DASHBOARD_SESSION_CONTRACT_VERSION,
    DASHBOARD_SESSION_METADATA_ROLE_ID as DASHBOARD_METADATA_ROLE_ID,
    DASHBOARD_SESSION_PAYLOAD_ROLE_ID as DASHBOARD_PAYLOAD_ROLE_ID,
    DASHBOARD_SESSION_STATE_ROLE_ID as DASHBOARD_STATE_ROLE_ID,
    METADATA_JSON_KEY as DASHBOARD_METADATA_JSON_KEY,
    MORPHOLOGY_PANE_ID,
    PAIRED_READOUT_DELTA_OVERLAY_ID,
    PHASE_MAP_REFERENCE_OVERLAY_ID,
    REVIEWER_FINDINGS_OVERLAY_ID,
    SCENE_PANE_ID,
    SESSION_PAYLOAD_ARTIFACT_ID,
    SESSION_STATE_ARTIFACT_ID,
    SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    STIMULUS_CONTEXT_FRAME_OVERLAY_ID,
    TIME_SERIES_PANE_ID,
    VALIDATION_BUNDLE_METADATA_ROLE_ID as DASHBOARD_VALIDATION_BUNDLE_METADATA_ROLE_ID,
    VALIDATION_REVIEW_HANDOFF_ROLE_ID as DASHBOARD_VALIDATION_REVIEW_HANDOFF_ROLE_ID,
    WAVE_PATCH_ACTIVITY_OVERLAY_ID,
    discover_dashboard_session_artifact_references,
    discover_dashboard_session_bundle_paths,
    load_dashboard_session_metadata,
)
from .dashboard_session_planning import (
    package_dashboard_session,
    resolve_dashboard_session_plan,
)
from .experiment_analysis_contract import (
    ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
    METADATA_JSON_KEY as ANALYSIS_METADATA_JSON_KEY,
    OFFLINE_REPORT_INDEX_ARTIFACT_ID,
    discover_experiment_analysis_bundle_paths,
    load_experiment_analysis_bundle_metadata,
)
from .experiment_suite_contract import EXPERIMENT_SUITE_CONTRACT_VERSION
from .experiment_suite_packaging import (
    discover_experiment_suite_package_cells,
    discover_experiment_suite_stage_artifacts,
    load_experiment_suite_package_metadata,
    load_experiment_suite_result_index,
)
from .experiment_suite_reporting import (
    generate_experiment_suite_review_report,
)
from .io_utils import write_json
from .showcase_session_contract import (
    ANALYSIS_BUNDLE_METADATA_ROLE_ID,
    ANALYSIS_OFFLINE_REPORT_ROLE_ID,
    ANALYSIS_UI_PAYLOAD_ROLE_ID,
    APPROVED_HIGHLIGHT_PRESET_ID,
    APPROVED_WAVE_HIGHLIGHT_EVIDENCE_ROLE_ID,
    APPROVED_WAVE_HIGHLIGHT_STEP_ID,
    BASELINE_WAVE_COMPARISON_STEP_ID,
    CAMERA_TRANSITION_CUE_KIND_ID,
    CONTRACT_METADATA_SCOPE,
    DASHBOARD_CONTEXT_SCOPE,
    DASHBOARD_SESSION_METADATA_ROLE_ID,
    DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
    DASHBOARD_SESSION_SOURCE_KIND,
    DASHBOARD_SESSION_STATE_ROLE_ID,
    DEFAULT_EXPORT_TARGET_ROLE_ID,
    EVIDENCE_CAPTION_ANNOTATION_ID,
    EXPORT_SURFACE_SCOPE,
    FALLBACK_NOTICE_ANNOTATION_ID,
    FALLBACK_REDIRECT_CUE_KIND_ID,
    FAIRNESS_BOUNDARY_ANNOTATION_ID,
    FLY_VIEW_INPUT_STEP_ID,
    HIGHLIGHT_FALLBACK_PRESET_ID,
    HERO_FRAME_EXPORT_TARGET_ROLE_ID,
    INPUT_CONTEXT_EVIDENCE_ROLE_ID,
    INPUT_SAMPLING_ANNOTATION_ID,
    JSON_NARRATIVE_PRESET_CATALOG_FORMAT,
    JSON_SHOWCASE_EXPORT_MANIFEST_FORMAT,
    JSON_SHOWCASE_SCRIPT_FORMAT,
    JSON_SHOWCASE_STATE_FORMAT,
    METADATA_JSON_KEY,
    NARRATIVE_PRESET_CATALOG_ARTIFACT_ID,
    NARRATIVE_PRESET_CATALOG_ROLE_ID,
    NARRATIVE_PRESET_SCOPE,
    NARRATION_CALLOUT_CUE_KIND_ID,
    OVERLAY_REVEAL_CUE_KIND_ID,
    PAIRED_COMPARISON_PRESET_ID,
    PLAYBACK_SCRUB_CUE_KIND_ID,
    PRESENTATION_STATE_SCOPE,
    PRESENTATION_STATUS_BLOCKED,
    PRESENTATION_STATUS_FALLBACK,
    PRESENTATION_STATUS_PLANNED,
    PRESENTATION_STATUS_READY,
    PRESENTATION_STATUS_SCIENTIFIC_REVIEW_REQUIRED,
    REVIEW_MANIFEST_EXPORT_TARGET_ROLE_ID,
    SCENE_CONTEXT_EVIDENCE_ROLE_ID,
    SCENE_CONTEXT_PRESET_ID,
    SCENE_SELECTION_STEP_ID,
    SCIENTIFIC_GUARDRAIL_ANNOTATION_ID,
    SCRIPT_PLAYBACK_SCOPE,
    SCRIPTED_CLIP_EXPORT_TARGET_ROLE_ID,
    SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID,
    SHOWCASE_EXPORT_MANIFEST_ROLE_ID,
    SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID,
    SHOWCASE_PRESENTATION_STATE_ROLE_ID,
    SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID,
    SHOWCASE_SCRIPT_PAYLOAD_ROLE_ID,
    SHOWCASE_SESSION_CONTRACT_VERSION,
    SHOWCASE_SESSION_METADATA_ROLE_ID,
    SHOWCASE_SESSION_PACKAGE_SOURCE_KIND,
    SHOWCASE_STATE_EXPORT_TARGET_ROLE_ID,
    STORYBOARD_EXPORT_TARGET_ROLE_ID,
    STORY_CONTEXT_ANNOTATION_ID,
    SUBSET_CONTEXT_EVIDENCE_ROLE_ID,
    SUBSET_CONTEXT_PRESET_ID,
    SUITE_COMPARISON_PLOT_ROLE_ID,
    SUITE_REVIEW_ARTIFACT_ROLE_ID,
    SUITE_ROLLUP_EVIDENCE_ROLE_ID,
    SUITE_ROLLUP_SCOPE,
    SUITE_SUMMARY_TABLE_ROLE_ID,
    SUMMARY_ANALYSIS_EVIDENCE_ROLE_ID,
    SUMMARY_ANALYSIS_STEP_ID,
    SUMMARY_ANALYSIS_PRESET_ID,
    VALIDATION_BUNDLE_METADATA_ROLE_ID,
    VALIDATION_FINDINGS_ROLE_ID,
    VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
    VALIDATION_GUARDRAIL_SCOPE,
    VALIDATION_REVIEW_HANDOFF_ROLE_ID,
    VALIDATION_SUMMARY_ROLE_ID,
    build_showcase_evidence_reference,
    build_showcase_narrative_annotation,
    build_showcase_saved_preset,
    build_showcase_session_artifact_reference,
    build_showcase_session_bundle_paths,
    build_showcase_session_contract_metadata,
    build_showcase_session_metadata,
    build_showcase_step,
    discover_showcase_export_target_roles,
    write_showcase_session_metadata,
)
from .simulator_result_contract import DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR
from .stimulus_contract import (
    ASSET_STATUS_READY,
    _normalize_identifier,
    _normalize_nonempty_string,
)
from .validation_contract import (
    METADATA_JSON_KEY as VALIDATION_METADATA_JSON_KEY,
    REVIEW_HANDOFF_ARTIFACT_ID,
    VALIDATION_LADDER_CONTRACT_VERSION,
    VALIDATION_SUMMARY_ARTIFACT_ID,
    VALIDATOR_FINDINGS_ARTIFACT_ID,
    discover_validation_bundle_paths,
    load_validation_bundle_metadata,
)


SHOWCASE_SESSION_PLAN_VERSION = "showcase_session_plan.v1"
SHOWCASE_SESSION_SOURCE_MODE_MANIFEST = "manifest"
SHOWCASE_SESSION_SOURCE_MODE_EXPERIMENT = "experiment"
SHOWCASE_SESSION_SOURCE_MODE_DASHBOARD = "dashboard_session"
SHOWCASE_SESSION_SOURCE_MODE_SUITE = "suite_package"
SHOWCASE_SESSION_SOURCE_MODE_EXPLICIT = "explicit_artifact_inputs"

DEFAULT_SHOWCASE_ID = "milestone_16_showcase"
DEFAULT_SHOWCASE_DISPLAY_NAME = "Milestone 16 Showcase"

DEFAULT_ACTIVE_PANE_BY_STEP = {
    SCENE_SELECTION_STEP_ID: SCENE_PANE_ID,
    FLY_VIEW_INPUT_STEP_ID: SCENE_PANE_ID,
    "active_visual_subset": CIRCUIT_PANE_ID,
    "activity_propagation": TIME_SERIES_PANE_ID,
    BASELINE_WAVE_COMPARISON_STEP_ID: ANALYSIS_PANE_ID,
    APPROVED_WAVE_HIGHLIGHT_STEP_ID: ANALYSIS_PANE_ID,
    SUMMARY_ANALYSIS_STEP_ID: ANALYSIS_PANE_ID,
}

DEFAULT_EXPORT_FILE_NAMES = {
    SHOWCASE_STATE_EXPORT_TARGET_ROLE_ID: "showcase_state_export.json",
    STORYBOARD_EXPORT_TARGET_ROLE_ID: "storyboard.json",
    HERO_FRAME_EXPORT_TARGET_ROLE_ID: "hero_frame.png",
    SCRIPTED_CLIP_EXPORT_TARGET_ROLE_ID: "scripted_clip_frames",
    REVIEW_MANIFEST_EXPORT_TARGET_ROLE_ID: "review_manifest.json",
}

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
_SUPPORTED_PANE_IDS = (
    SCENE_PANE_ID,
    CIRCUIT_PANE_ID,
    MORPHOLOGY_PANE_ID,
    TIME_SERIES_PANE_ID,
    ANALYSIS_PANE_ID,
)


def resolve_manifest_showcase_session_plan(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    **overrides: Any,
) -> dict[str, Any]:
    return resolve_showcase_session_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        **overrides,
    )


def resolve_showcase_session_plan(
    *,
    config_path: str | Path,
    manifest_path: str | Path | None = None,
    schema_path: str | Path | None = None,
    design_lock_path: str | Path | None = None,
    experiment_id: str | None = None,
    dashboard_session_metadata: Mapping[str, Any] | None = None,
    dashboard_session_metadata_path: str | Path | None = None,
    suite_package_metadata: Mapping[str, Any] | None = None,
    suite_package_metadata_path: str | Path | None = None,
    suite_review_summary: Mapping[str, Any] | None = None,
    suite_review_summary_path: str | Path | None = None,
    explicit_artifact_references: Sequence[Mapping[str, Any]] | None = None,
    showcase_id: str = DEFAULT_SHOWCASE_ID,
    display_name: str = DEFAULT_SHOWCASE_DISPLAY_NAME,
    table_dimension_ids: Sequence[str] | None = None,
    saved_preset_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    highlight_override: Mapping[str, Any] | None = None,
    enabled_export_target_role_ids: Sequence[str] | None = None,
    default_export_target_role_id: str = DEFAULT_EXPORT_TARGET_ROLE_ID,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = load_config(config_path)
    config_file = get_config_path(cfg)
    project_root = get_project_root(cfg)
    if config_file is None or project_root is None:
        raise ValueError("Loaded config is missing config metadata.")

    normalized_contract = (
        build_showcase_session_contract_metadata()
        if contract_metadata is None
        else _require_mapping(contract_metadata, field_name="contract_metadata")
    )
    processed_dir = Path(
        cfg["paths"].get(
            "processed_simulator_results_dir",
            DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
        )
    ).resolve()
    source_mode = _resolve_source_mode(
        manifest_path=manifest_path,
        experiment_id=experiment_id,
        dashboard_session_metadata=dashboard_session_metadata,
        dashboard_session_metadata_path=dashboard_session_metadata_path,
        suite_package_metadata=suite_package_metadata,
        suite_package_metadata_path=suite_package_metadata_path,
        suite_review_summary=suite_review_summary,
        suite_review_summary_path=suite_review_summary_path,
        explicit_artifact_references=explicit_artifact_references,
    )
    raw_explicit_artifacts = _normalize_raw_explicit_artifact_references(
        explicit_artifact_references
    )

    suite_context = _resolve_suite_context(
        suite_package_metadata=suite_package_metadata,
        suite_package_metadata_path=suite_package_metadata_path,
        suite_review_summary=suite_review_summary,
        suite_review_summary_path=suite_review_summary_path,
        table_dimension_ids=table_dimension_ids,
    )
    resolved_experiment_id = _resolve_experiment_id(
        manifest_path=manifest_path,
        experiment_id=experiment_id,
        suite_context=suite_context,
        raw_explicit_artifacts=raw_explicit_artifacts,
    )
    dashboard_context = _resolve_dashboard_context(
        config_path=config_path,
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        experiment_id=resolved_experiment_id,
        dashboard_session_metadata=dashboard_session_metadata,
        dashboard_session_metadata_path=dashboard_session_metadata_path,
        raw_explicit_artifacts=raw_explicit_artifacts,
        suite_context=suite_context,
    )
    resolved_experiment_id = str(dashboard_context["metadata"]["experiment_id"])
    _validate_experiment_alignment(
        experiment_id=resolved_experiment_id,
        source_mode=source_mode,
        suite_context=suite_context,
    )

    analysis_context = _resolve_analysis_context(
        dashboard_metadata=dashboard_context["metadata"],
        raw_explicit_artifacts=raw_explicit_artifacts,
    )
    validation_context = _resolve_validation_context(
        dashboard_metadata=dashboard_context["metadata"],
        raw_explicit_artifacts=raw_explicit_artifacts,
        requested_highlight=highlight_override is not None,
    )
    narrative_context = _build_narrative_context(
        dashboard_context=dashboard_context,
        analysis_context=analysis_context,
        validation_context=validation_context,
        suite_context=suite_context,
        highlight_override=highlight_override,
    )
    saved_presets = _build_saved_presets(
        dashboard_context=dashboard_context,
        narrative_context=narrative_context,
        saved_preset_overrides=saved_preset_overrides,
    )
    showcase_steps = _build_showcase_steps(
        narrative_context=narrative_context,
        suite_context=suite_context,
        enabled_export_target_role_ids=enabled_export_target_role_ids,
        default_export_target_role_id=default_export_target_role_id,
        contract_metadata=normalized_contract,
    )
    presentation_status = _roll_up_presentation_status(showcase_steps)
    external_artifact_references = _build_external_artifact_references(
        dashboard_context=dashboard_context,
        analysis_context=analysis_context,
        validation_context=validation_context,
        suite_context=suite_context,
        raw_explicit_artifacts=raw_explicit_artifacts,
        contract_metadata=normalized_contract,
    )
    showcase_session = build_showcase_session_metadata(
        experiment_id=resolved_experiment_id,
        showcase_id=showcase_id,
        display_name=display_name,
        artifact_references=external_artifact_references,
        saved_presets=saved_presets,
        showcase_steps=showcase_steps,
        processed_simulator_results_dir=processed_dir,
        presentation_status=presentation_status,
        enabled_export_target_role_ids=enabled_export_target_role_ids,
        default_export_target_role_id=default_export_target_role_id,
        showcase_script_payload_status=ASSET_STATUS_READY,
        showcase_presentation_state_status=ASSET_STATUS_READY,
        narrative_preset_catalog_status=ASSET_STATUS_READY,
        showcase_export_manifest_status=ASSET_STATUS_READY,
        contract_metadata=normalized_contract,
    )
    output_locations = _build_output_locations(
        showcase_session=showcase_session,
        contract_metadata=normalized_contract,
    )
    operator_defaults = _build_operator_defaults(
        showcase_steps=showcase_steps,
        dashboard_context=dashboard_context,
        showcase_session=showcase_session,
    )
    showcase_presentation_state = _build_showcase_presentation_state(
        showcase_session=showcase_session,
        dashboard_context=dashboard_context,
        showcase_steps=showcase_steps,
        operator_defaults=operator_defaults,
    )
    showcase_script_payload = _build_showcase_script_payload(
        showcase_session=showcase_session,
        showcase_steps=showcase_steps,
        saved_presets=saved_presets,
        operator_defaults=operator_defaults,
    )
    narrative_preset_catalog = _build_narrative_preset_catalog(
        showcase_session=showcase_session,
        dashboard_context=dashboard_context,
        saved_presets=saved_presets,
    )
    showcase_export_manifest = _build_showcase_export_manifest(
        showcase_session=showcase_session,
        output_locations=output_locations,
        contract_metadata=normalized_contract,
    )

    return {
        "plan_version": SHOWCASE_SESSION_PLAN_VERSION,
        "source_mode": source_mode,
        "manifest_reference": copy.deepcopy(
            dict(dashboard_context["metadata"]["manifest_reference"])
        ),
        "config_reference": {
            "config_path": str(Path(config_file).resolve()),
            "project_root": str(Path(project_root).resolve()),
        },
        "scene_choice": copy.deepcopy(narrative_context["scene_choice"]),
        "input_surface": copy.deepcopy(narrative_context["input_surface"]),
        "active_subset_focus_targets": copy.deepcopy(
            narrative_context["active_subset_focus_targets"]
        ),
        "activity_propagation_views": copy.deepcopy(
            narrative_context["activity_propagation_views"]
        ),
        "approved_comparison_arms": copy.deepcopy(
            narrative_context["approved_comparison_arms"]
        ),
        "highlight_selection": copy.deepcopy(narrative_context["highlight_selection"]),
        "closing_analysis_assets": copy.deepcopy(
            narrative_context["closing_analysis_assets"]
        ),
        "operator_defaults": copy.deepcopy(operator_defaults),
        "upstream_artifact_references": copy.deepcopy(external_artifact_references),
        "saved_presets": copy.deepcopy(saved_presets),
        "narrative_step_sequence": copy.deepcopy(showcase_steps),
        "dashboard_session_plan": (
            None
            if dashboard_context["plan"] is None
            else copy.deepcopy(dashboard_context["plan"])
        ),
        "suite_evidence": copy.deepcopy(suite_context),
        "showcase_session": copy.deepcopy(showcase_session),
        "showcase_script_payload": copy.deepcopy(showcase_script_payload),
        "showcase_presentation_state": copy.deepcopy(showcase_presentation_state),
        "narrative_preset_catalog": copy.deepcopy(narrative_preset_catalog),
        "showcase_export_manifest": copy.deepcopy(showcase_export_manifest),
        "output_locations": copy.deepcopy(output_locations),
    }


def package_showcase_session(plan: Mapping[str, Any]) -> dict[str, Any]:
    normalized_plan = _require_mapping(plan, field_name="plan")
    if str(normalized_plan.get("plan_version")) != SHOWCASE_SESSION_PLAN_VERSION:
        raise ValueError(
            f"plan.plan_version must be {SHOWCASE_SESSION_PLAN_VERSION!r}."
        )

    dashboard_plan = normalized_plan.get("dashboard_session_plan")
    dashboard_package = None
    if isinstance(dashboard_plan, Mapping):
        dashboard_package = package_dashboard_session(dashboard_plan)

    showcase_session = _require_mapping(
        normalized_plan.get("showcase_session"),
        field_name="plan.showcase_session",
    )
    showcase_script_payload = _require_mapping(
        normalized_plan.get("showcase_script_payload"),
        field_name="plan.showcase_script_payload",
    )
    showcase_presentation_state = _require_mapping(
        normalized_plan.get("showcase_presentation_state"),
        field_name="plan.showcase_presentation_state",
    )
    narrative_preset_catalog = _require_mapping(
        normalized_plan.get("narrative_preset_catalog"),
        field_name="plan.narrative_preset_catalog",
    )
    showcase_export_manifest = _require_mapping(
        normalized_plan.get("showcase_export_manifest"),
        field_name="plan.showcase_export_manifest",
    )

    metadata_path = write_showcase_session_metadata(showcase_session)
    bundle_paths = discover_showcase_session_bundle_paths(showcase_session)
    write_json(showcase_script_payload, bundle_paths[SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID])
    write_json(
        showcase_presentation_state,
        bundle_paths[SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID],
    )
    write_json(
        narrative_preset_catalog,
        bundle_paths[NARRATIVE_PRESET_CATALOG_ARTIFACT_ID],
    )
    write_json(
        showcase_export_manifest,
        bundle_paths[SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID],
    )
    return {
        "bundle_id": str(showcase_session["bundle_id"]),
        "metadata_path": str(metadata_path.resolve()),
        "showcase_script_path": str(
            bundle_paths[SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID].resolve()
        ),
        "showcase_state_path": str(
            bundle_paths[SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID].resolve()
        ),
        "narrative_preset_catalog_path": str(
            bundle_paths[NARRATIVE_PRESET_CATALOG_ARTIFACT_ID].resolve()
        ),
        "showcase_export_manifest_path": str(
            bundle_paths[SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID].resolve()
        ),
        "bundle_directory": str(
            Path(showcase_session["bundle_layout"]["bundle_directory"]).resolve()
        ),
        "upstream_dashboard_metadata_path": (
            None if dashboard_package is None else str(dashboard_package["metadata_path"])
        ),
    }


def _resolve_source_mode(
    *,
    manifest_path: str | Path | None,
    experiment_id: str | None,
    dashboard_session_metadata: Mapping[str, Any] | None,
    dashboard_session_metadata_path: str | Path | None,
    suite_package_metadata: Mapping[str, Any] | None,
    suite_package_metadata_path: str | Path | None,
    suite_review_summary: Mapping[str, Any] | None,
    suite_review_summary_path: str | Path | None,
    explicit_artifact_references: Sequence[Mapping[str, Any]] | None,
) -> str:
    if manifest_path is not None:
        return SHOWCASE_SESSION_SOURCE_MODE_MANIFEST
    if experiment_id is not None:
        return SHOWCASE_SESSION_SOURCE_MODE_EXPERIMENT
    if dashboard_session_metadata is not None or dashboard_session_metadata_path is not None:
        return SHOWCASE_SESSION_SOURCE_MODE_DASHBOARD
    if (
        suite_package_metadata is not None
        or suite_package_metadata_path is not None
        or suite_review_summary is not None
        or suite_review_summary_path is not None
    ):
        return SHOWCASE_SESSION_SOURCE_MODE_SUITE
    if explicit_artifact_references:
        return SHOWCASE_SESSION_SOURCE_MODE_EXPLICIT
    raise ValueError(
        "Showcase session planning requires one of manifest_path, experiment_id, "
        "dashboard_session_metadata, suite package/report inputs, or explicit_artifact_references."
    )


def _resolve_experiment_id(
    *,
    manifest_path: str | Path | None,
    experiment_id: str | None,
    suite_context: Mapping[str, Any] | None,
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
) -> str | None:
    candidates: set[str] = set()
    if experiment_id is not None:
        candidates.add(_normalize_identifier(experiment_id, field_name="experiment_id"))
    if suite_context and suite_context.get("experiment_id") is not None:
        candidates.add(str(suite_context["experiment_id"]))
    dashboard_metadata_ref = raw_explicit_artifacts.get(DASHBOARD_SESSION_METADATA_ROLE_ID)
    if dashboard_metadata_ref is not None:
        metadata = load_dashboard_session_metadata(
            Path(dashboard_metadata_ref["path"]).resolve()
        )
        candidates.add(str(metadata["experiment_id"]))
    if manifest_path is not None and not candidates:
        return None
    if len(candidates) > 1:
        raise ValueError(
            "Showcase planning received conflicting experiment identifiers "
            f"{sorted(candidates)!r}."
        )
    return next(iter(candidates), None)


def _resolve_dashboard_context(
    *,
    config_path: str | Path,
    manifest_path: str | Path | None,
    schema_path: str | Path | None,
    design_lock_path: str | Path | None,
    experiment_id: str | None,
    dashboard_session_metadata: Mapping[str, Any] | None,
    dashboard_session_metadata_path: str | Path | None,
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    suite_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if dashboard_session_metadata is not None or dashboard_session_metadata_path is not None:
        metadata = (
            load_dashboard_session_metadata(dashboard_session_metadata_path)
            if dashboard_session_metadata_path is not None
            else load_dashboard_session_metadata(
                Path(str(dashboard_session_metadata["artifacts"][DASHBOARD_METADATA_JSON_KEY]["path"]))
            )
        )
        return _packaged_dashboard_context(
            metadata,
            raw_explicit_artifacts=raw_explicit_artifacts,
            plan=None,
        )

    dashboard_metadata_ref = raw_explicit_artifacts.get(DASHBOARD_SESSION_METADATA_ROLE_ID)
    if dashboard_metadata_ref is not None:
        metadata = load_dashboard_session_metadata(Path(dashboard_metadata_ref["path"]).resolve())
        return _packaged_dashboard_context(
            metadata,
            raw_explicit_artifacts=raw_explicit_artifacts,
            plan=None,
        )

    if suite_context and suite_context.get("package_metadata") is not None:
        dashboard_from_suite = _discover_dashboard_metadata_from_suite_package(
            suite_context["package_metadata"]
        )
        if dashboard_from_suite is not None:
            return _packaged_dashboard_context(
                dashboard_from_suite,
                raw_explicit_artifacts=raw_explicit_artifacts,
                plan=None,
            )

    if manifest_path is None and experiment_id is None and suite_context is not None:
        experiment_id = (
            None if suite_context.get("experiment_id") is None else str(suite_context["experiment_id"])
        )

    if manifest_path is not None:
        if schema_path is None or design_lock_path is None:
            raise ValueError(
                "Manifest-driven showcase planning requires schema_path and design_lock_path."
            )
        dashboard_plan = resolve_dashboard_session_plan(
            manifest_path=manifest_path,
            config_path=config_path,
            schema_path=schema_path,
            design_lock_path=design_lock_path,
        )
        return _planned_dashboard_context(dashboard_plan)

    if experiment_id is not None:
        dashboard_plan = resolve_dashboard_session_plan(
            experiment_id=experiment_id,
            config_path=config_path,
        )
        return _planned_dashboard_context(dashboard_plan)

    raise ValueError(
        "Showcase planning could not resolve one dashboard session context. "
        "Pass dashboard_session_metadata, manifest_path, experiment_id, or a suite package "
        "with a discoverable dashboard stage."
    )


def _packaged_dashboard_context(
    metadata: Mapping[str, Any],
    *,
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    normalized_metadata = load_dashboard_session_metadata(
        Path(str(metadata["artifacts"][DASHBOARD_METADATA_JSON_KEY]["path"])).resolve()
    )
    bundle_paths = discover_dashboard_session_bundle_paths(normalized_metadata)
    payload_path = _explicit_or_default_path(
        raw_explicit_artifacts,
        role_id=DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
        default_path=bundle_paths[SESSION_PAYLOAD_ARTIFACT_ID],
    )
    state_path = _explicit_or_default_path(
        raw_explicit_artifacts,
        role_id=DASHBOARD_SESSION_STATE_ROLE_ID,
        default_path=bundle_paths[SESSION_STATE_ARTIFACT_ID],
    )
    payload = _load_json_mapping(
        payload_path,
        field_name="dashboard_session_payload",
    )
    state = _load_json_mapping(
        state_path,
        field_name="dashboard_session_state",
    )
    _validate_dashboard_payload(metadata=normalized_metadata, payload=payload, state=state)
    return {
        "origin": "packaged",
        "metadata": normalized_metadata,
        "payload": payload,
        "state": state,
        "plan": plan,
    }


def _planned_dashboard_context(plan: Mapping[str, Any]) -> dict[str, Any]:
    normalized_plan = _require_mapping(plan, field_name="dashboard_session_plan")
    metadata = _require_mapping(
        normalized_plan.get("dashboard_session"),
        field_name="dashboard_session_plan.dashboard_session",
    )
    payload = _require_mapping(
        normalized_plan.get("dashboard_session_payload"),
        field_name="dashboard_session_plan.dashboard_session_payload",
    )
    state = _require_mapping(
        normalized_plan.get("dashboard_session_state"),
        field_name="dashboard_session_plan.dashboard_session_state",
    )
    _validate_dashboard_payload(metadata=metadata, payload=payload, state=state)
    return {
        "origin": "planned",
        "metadata": copy.deepcopy(dict(metadata)),
        "payload": copy.deepcopy(dict(payload)),
        "state": copy.deepcopy(dict(state)),
        "plan": copy.deepcopy(dict(normalized_plan)),
    }


def _validate_dashboard_payload(
    *,
    metadata: Mapping[str, Any],
    payload: Mapping[str, Any],
    state: Mapping[str, Any],
) -> None:
    selected_pair = _require_mapping(
        payload.get("selected_bundle_pair"),
        field_name="dashboard_session_payload.selected_bundle_pair",
    )
    baseline = _require_mapping(
        selected_pair.get("baseline"),
        field_name="dashboard_session_payload.selected_bundle_pair.baseline",
    )
    wave = _require_mapping(
        selected_pair.get("wave"),
        field_name="dashboard_session_payload.selected_bundle_pair.wave",
    )
    if str(baseline["arm_id"]) == str(wave["arm_id"]):
        raise ValueError(
            "Showcase planning requires one distinct baseline-versus-wave arm pair."
        )

    scene_context = _require_mapping(
        payload.get("pane_inputs", {}).get(SCENE_PANE_ID),
        field_name="dashboard_session_payload.pane_inputs.scene",
    )
    if str(scene_context.get("render_status")) != "available":
        reason = _require_mapping(
            scene_context.get("frame_discovery", {}),
            field_name="dashboard_session_payload.pane_inputs.scene.frame_discovery",
        ).get("unavailable_reason", "scene render layer is unavailable")
        raise ValueError(
            "Showcase planning requires a packaged fly-view or sampled-input surface; "
            f"dashboard scene render_status is {scene_context.get('render_status')!r}: {reason}."
        )

    time_series_context = _require_mapping(
        payload.get("pane_inputs", {}).get(TIME_SERIES_PANE_ID),
        field_name="dashboard_session_payload.pane_inputs.time_series",
    )
    replay_model = _require_mapping(
        time_series_context.get("replay_model"),
        field_name="dashboard_session_payload.pane_inputs.time_series.replay_model",
    )
    shared_timebase_status = _require_mapping(
        replay_model.get("shared_timebase_status"),
        field_name="dashboard_session_payload.pane_inputs.time_series.replay_model.shared_timebase_status",
    )
    if str(shared_timebase_status.get("availability")) != "available":
        raise ValueError(
            "Showcase planning requires a shared baseline-versus-wave timebase, but "
            f"dashboard replay reports {shared_timebase_status!r}."
        )

    circuit_context = _require_mapping(
        payload.get("pane_inputs", {}).get(CIRCUIT_PANE_ID),
        field_name="dashboard_session_payload.pane_inputs.circuit",
    )
    selected_root_ids = list(circuit_context.get("selected_root_ids", []))
    if not selected_root_ids:
        raise ValueError(
            "Showcase planning requires at least one selected root in the dashboard circuit context."
        )

    if str(metadata["bundle_id"]) != str(payload["bundle_reference"]["bundle_id"]):
        raise ValueError(
            "dashboard_session metadata and payload must reference the same bundle_id."
        )
    if str(metadata["bundle_id"]) != str(state["bundle_reference"]["bundle_id"]):
        raise ValueError(
            "dashboard_session metadata and state must reference the same bundle_id."
        )


def _resolve_analysis_context(
    *,
    dashboard_metadata: Mapping[str, Any],
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    metadata = _load_upstream_bundle_metadata_from_dashboard(
        dashboard_metadata=dashboard_metadata,
        dashboard_role_id=DASHBOARD_ANALYSIS_BUNDLE_METADATA_ROLE_ID,
        explicit_metadata_path=raw_explicit_artifacts.get(ANALYSIS_BUNDLE_METADATA_ROLE_ID, {}).get("path"),
        loader=load_experiment_analysis_bundle_metadata,
    )
    bundle_paths = discover_experiment_analysis_bundle_paths(metadata)
    ui_payload_path = _explicit_or_default_path(
        raw_explicit_artifacts,
        role_id=ANALYSIS_UI_PAYLOAD_ROLE_ID,
        default_path=bundle_paths[ANALYSIS_UI_PAYLOAD_ARTIFACT_ID],
    )
    ui_payload = _load_json_mapping(ui_payload_path, field_name="analysis_ui_payload")
    offline_report_path = (
        None
        if not Path(bundle_paths[OFFLINE_REPORT_INDEX_ARTIFACT_ID]).resolve().exists()
        else _explicit_or_default_path(
            raw_explicit_artifacts,
            role_id=ANALYSIS_OFFLINE_REPORT_ROLE_ID,
            default_path=bundle_paths[OFFLINE_REPORT_INDEX_ARTIFACT_ID],
        )
    )
    return {
        "metadata": metadata,
        "ui_payload": ui_payload,
        "bundle_paths": bundle_paths,
        "ui_payload_path": str(ui_payload_path),
        "offline_report_path": (
            None if offline_report_path is None else str(Path(offline_report_path).resolve())
        ),
    }


def _resolve_validation_context(
    *,
    dashboard_metadata: Mapping[str, Any],
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    requested_highlight: bool,
) -> dict[str, Any]:
    metadata = _load_upstream_bundle_metadata_from_dashboard(
        dashboard_metadata=dashboard_metadata,
        dashboard_role_id=DASHBOARD_VALIDATION_BUNDLE_METADATA_ROLE_ID,
        explicit_metadata_path=raw_explicit_artifacts.get(VALIDATION_BUNDLE_METADATA_ROLE_ID, {}).get("path"),
        loader=load_validation_bundle_metadata,
    )
    bundle_paths = discover_validation_bundle_paths(metadata)
    summary_path = _explicit_or_default_path(
        raw_explicit_artifacts,
        role_id=VALIDATION_SUMMARY_ROLE_ID,
        default_path=bundle_paths[VALIDATION_SUMMARY_ARTIFACT_ID],
    )
    findings_path = _explicit_or_default_path(
        raw_explicit_artifacts,
        role_id=VALIDATION_FINDINGS_ROLE_ID,
        default_path=bundle_paths[VALIDATOR_FINDINGS_ARTIFACT_ID],
    )
    review_handoff_default = (
        None
        if not Path(bundle_paths[REVIEW_HANDOFF_ARTIFACT_ID]).resolve().exists()
        else bundle_paths[REVIEW_HANDOFF_ARTIFACT_ID]
    )
    review_handoff_path = (
        None
        if review_handoff_default is None
        else _explicit_or_default_path(
            raw_explicit_artifacts,
            role_id=VALIDATION_REVIEW_HANDOFF_ROLE_ID,
            default_path=review_handoff_default,
        )
    )
    summary = _load_json_mapping(summary_path, field_name="validation_summary")
    findings = _load_json_mapping(findings_path, field_name="validation_findings")
    review_handoff = (
        {}
        if review_handoff_path is None
        else _load_json_mapping(review_handoff_path, field_name="validation_review_handoff")
    )
    if not findings.get("validator_findings"):
        raise ValueError(
            "Showcase planning requires non-empty validation findings for the highlight guardrail."
        )
    if requested_highlight and review_handoff_path is None:
        raise ValueError(
            "Showcase planning received a nominated highlight, but the validation review_handoff artifact is unavailable."
        )
    return {
        "metadata": metadata,
        "summary": summary,
        "findings": findings,
        "review_handoff": review_handoff,
        "bundle_paths": bundle_paths,
        "summary_path": str(summary_path),
        "findings_path": str(findings_path),
        "review_handoff_path": (
            None if review_handoff_path is None else str(Path(review_handoff_path).resolve())
        ),
    }


def _resolve_suite_context(
    *,
    suite_package_metadata: Mapping[str, Any] | None,
    suite_package_metadata_path: str | Path | None,
    suite_review_summary: Mapping[str, Any] | None,
    suite_review_summary_path: str | Path | None,
    table_dimension_ids: Sequence[str] | None,
) -> dict[str, Any] | None:
    package_metadata = None
    package_metadata_path_value = None
    if suite_package_metadata is not None:
        package_metadata = load_experiment_suite_package_metadata(
            Path(str(suite_package_metadata["artifacts"]["metadata_json"]["path"])).resolve()
        )
        package_metadata_path_value = Path(
            package_metadata["artifacts"]["metadata_json"]["path"]
        ).resolve()
    elif suite_package_metadata_path is not None:
        package_metadata = load_experiment_suite_package_metadata(
            Path(suite_package_metadata_path).resolve()
        )
        package_metadata_path_value = Path(suite_package_metadata_path).resolve()

    review_summary_value = None
    if suite_review_summary is not None:
        review_summary_value = copy.deepcopy(dict(suite_review_summary))
    elif suite_review_summary_path is not None:
        review_summary_value = _load_json_mapping(
            suite_review_summary_path,
            field_name="suite_review_summary",
        )

    if package_metadata is None and review_summary_value is None:
        return None

    if review_summary_value is None:
        review_summary_value = generate_experiment_suite_review_report(
            package_metadata_path_value if package_metadata_path_value is not None else package_metadata,
            table_dimension_ids=table_dimension_ids,
        )

    suite_plan_path = Path(
        review_summary_value["suite_reference"]["suite_plan_path"]
    ).resolve()
    suite_plan = _load_json_mapping(suite_plan_path, field_name="suite_plan")
    artifact_catalog_path = Path(
        review_summary_value["report_layout"]["artifact_catalog_path"]
    ).resolve()
    artifact_catalog = _load_json_mapping(
        artifact_catalog_path,
        field_name="suite_review_artifact_catalog",
    )
    summary_table_artifact = _select_suite_artifact(
        artifact_catalog.get("table_artifacts", []),
        preferred_artifact_id="shared_comparison_summary_table",
        preferred_section_id="shared_comparison_metrics",
    )
    comparison_plot_artifact = _select_suite_artifact(
        artifact_catalog.get("plot_artifacts", []),
        preferred_artifact_id=None,
        preferred_section_id="shared_comparison_metrics",
    )
    review_artifact = _select_suite_artifact(
        artifact_catalog.get("review_artifacts", []),
        preferred_artifact_id="suite_review_summary_json",
        preferred_section_id=None,
    )

    experiment_id = None
    manifest_reference = suite_plan.get("manifest_reference")
    if isinstance(manifest_reference, Mapping):
        experiment_id = str(manifest_reference.get("experiment_id", "")) or None
    return {
        "experiment_id": experiment_id,
        "package_metadata": (
            None if package_metadata is None else copy.deepcopy(dict(package_metadata))
        ),
        "package_metadata_path": (
            None if package_metadata_path_value is None else str(package_metadata_path_value)
        ),
        "review_summary": copy.deepcopy(dict(review_summary_value)),
        "suite_plan_path": str(suite_plan_path),
        "suite_plan": suite_plan,
        "artifact_catalog_path": str(artifact_catalog_path),
        "artifact_catalog": artifact_catalog,
        "summary_table_artifact": summary_table_artifact,
        "comparison_plot_artifact": comparison_plot_artifact,
        "review_artifact": review_artifact,
    }


def _validate_experiment_alignment(
    *,
    experiment_id: str,
    source_mode: str,
    suite_context: Mapping[str, Any] | None,
) -> None:
    if suite_context is None or suite_context.get("experiment_id") in {None, ""}:
        return
    suite_experiment_id = str(suite_context["experiment_id"])
    if suite_experiment_id != experiment_id:
        raise ValueError(
            "Showcase planning received suite evidence for experiment_id "
            f"{suite_experiment_id!r}, but the resolved dashboard session uses {experiment_id!r} "
            f"(source_mode={source_mode!r})."
        )


def _build_narrative_context(
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
        override=highlight_override,
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
        "highlight_selection": highlight_selection,
        "closing_analysis_assets": {
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
            "analysis_summary_locator": "shared_comparison.milestone_1_decision_panel",
        },
        "analysis_summary_card": copy.deepcopy(
            analysis_pane["shared_comparison"]["milestone_1_decision_panel"]
        ),
    }


def _resolve_highlight_selection(
    *,
    analysis_context: Mapping[str, Any],
    validation_context: Mapping[str, Any],
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

    if normalized_override is not None:
        requested_role = str(normalized_override["artifact_role_id"])
        locator = normalized_override.get("locator")
        if requested_role == ANALYSIS_UI_PAYLOAD_ROLE_ID:
            _validate_highlight_locator(
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
        }
    else:
        first_card = diagnostic_cards[0]
        label = str(first_card.get("display_name", first_card.get("card_id", "wave_diagnostic")))
        candidate = {
            "phenomenon_id": _normalize_identifier(label, field_name="phenomenon_id"),
            "artifact_role_id": ANALYSIS_UI_PAYLOAD_ROLE_ID,
            "locator": "wave_only_diagnostics.diagnostic_cards[0]",
            "citation_label": label,
        }
    return {
        **candidate,
        "presentation_status": (
            PRESENTATION_STATUS_READY if approved else PRESENTATION_STATUS_FALLBACK
        ),
        "scientific_plausibility_decision": scientific_decision,
        "review_status": review_status,
        "fallback_reason": (
            None
            if approved
            else "validation review_handoff has not approved the requested wave-only beat"
        ),
    }


def _build_saved_presets(
    *,
    dashboard_context: Mapping[str, Any],
    narrative_context: Mapping[str, Any],
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
    step_defaults = {
        SCENE_CONTEXT_PRESET_ID: {
            "step_id": SCENE_SELECTION_STEP_ID,
            "display_name": "Scene Context",
            "note": "Open on the chosen packaged scene surface.",
            "presentation_status": PRESENTATION_STATUS_READY,
            "presentation_state_patch": {
                "active_pane_id": SCENE_PANE_ID,
                "focus_root_ids": selected_root_ids[:1],
                "scene_surface": {
                    "source_kind": str(scene_context["source_kind"]),
                    "active_layer_id": str(scene_context["active_layer_id"]),
                },
                "dashboard_state_patch": {
                    "global_interaction_state": {
                        "time_cursor": {"sample_index": 0, "time_ms": 0.0},
                    },
                    "replay_state": {
                        "time_cursor": {"sample_index": 0, "time_ms": 0.0},
                    },
                },
            },
        },
        "retinal_input_focus": {
            "step_id": FLY_VIEW_INPUT_STEP_ID,
            "display_name": "Retinal Input Focus",
            "note": "Pause on the packaged input surface before the circuit replay begins.",
            "presentation_status": PRESENTATION_STATUS_READY,
            "presentation_state_patch": {
                "active_pane_id": SCENE_PANE_ID,
                "scene_surface": {
                    "source_kind": str(scene_context["source_kind"]),
                    "active_layer_id": str(scene_context["active_layer_id"]),
                },
                "dashboard_state_patch": {
                    "global_interaction_state": {
                        "active_overlay_id": (
                            STIMULUS_CONTEXT_FRAME_OVERLAY_ID
                            if STIMULUS_CONTEXT_FRAME_OVERLAY_ID in available_overlays
                            else payload["global_interaction_state"]["active_overlay_id"]
                        ),
                    },
                    "replay_state": {
                        "active_overlay_id": (
                            STIMULUS_CONTEXT_FRAME_OVERLAY_ID
                            if STIMULUS_CONTEXT_FRAME_OVERLAY_ID in available_overlays
                            else state["replay_state"]["active_overlay_id"]
                        ),
                    },
                },
            },
        },
        SUBSET_CONTEXT_PRESET_ID: {
            "step_id": "active_visual_subset",
            "display_name": "Subset Context",
            "note": "Expose the selected roots and current focus neuron.",
            "presentation_status": PRESENTATION_STATUS_READY,
            "presentation_state_patch": {
                "active_pane_id": CIRCUIT_PANE_ID,
                "focus_root_ids": selected_root_ids,
                "dashboard_state_patch": {
                    "global_interaction_state": {
                        "selected_neuron_id": selected_neuron_id,
                    },
                    "replay_state": {
                        "selected_neuron_id": selected_neuron_id,
                    },
                },
            },
        },
        "propagation_replay": {
            "step_id": "activity_propagation",
            "display_name": "Propagation Replay",
            "note": "Use the shared replay cursor on the matched baseline-versus-wave surface.",
            "presentation_status": PRESENTATION_STATUS_READY,
            "presentation_state_patch": {
                "active_pane_id": TIME_SERIES_PANE_ID,
                "focus_root_ids": selected_root_ids[:1],
                "dashboard_state_patch": {
                    "global_interaction_state": {
                        "selected_readout_id": selected_readout_id,
                        "comparison_mode": state["replay_state"]["comparison_mode"],
                        "active_overlay_id": _preferred_overlay(
                            available_overlays,
                            WAVE_PATCH_ACTIVITY_OVERLAY_ID,
                            SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                        ),
                    },
                    "replay_state": {
                        "selected_readout_id": selected_readout_id,
                        "comparison_mode": state["replay_state"]["comparison_mode"],
                        "active_overlay_id": _preferred_overlay(
                            available_overlays,
                            WAVE_PATCH_ACTIVITY_OVERLAY_ID,
                            SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                        ),
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
                "dashboard_state_patch": {
                    "global_interaction_state": {
                        "comparison_mode": "paired_baseline_vs_wave",
                        "active_overlay_id": _preferred_overlay(
                            available_overlays,
                            PAIRED_READOUT_DELTA_OVERLAY_ID,
                            SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                        ),
                    },
                    "replay_state": {
                        "comparison_mode": "paired_baseline_vs_wave",
                        "active_overlay_id": _preferred_overlay(
                            available_overlays,
                            PAIRED_READOUT_DELTA_OVERLAY_ID,
                            SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                        ),
                    },
                },
            },
        },
        APPROVED_HIGHLIGHT_PRESET_ID: {
            "step_id": APPROVED_WAVE_HIGHLIGHT_STEP_ID,
            "display_name": "Approved Highlight",
            "note": "Focus the wave-only phenomenon only on the approved single-arm view.",
            "presentation_status": str(narrative_context["highlight_selection"]["presentation_status"]),
            "presentation_state_patch": {
                "active_pane_id": ANALYSIS_PANE_ID,
                "focus_root_ids": selected_root_ids[:1],
                "highlight_selection": copy.deepcopy(
                    dict(narrative_context["highlight_selection"])
                ),
                "dashboard_state_patch": {
                    "global_interaction_state": {
                        "comparison_mode": "single_arm",
                        "selected_arm_pair": {
                            "active_arm_id": str(active_arm_pair["wave_arm_id"]),
                        },
                        "active_overlay_id": _preferred_overlay(
                            available_overlays,
                            PHASE_MAP_REFERENCE_OVERLAY_ID,
                            WAVE_PATCH_ACTIVITY_OVERLAY_ID,
                            SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                        ),
                    },
                    "replay_state": {
                        "comparison_mode": "single_arm",
                        "selected_arm_pair": {
                            "active_arm_id": str(active_arm_pair["wave_arm_id"]),
                        },
                        "active_overlay_id": _preferred_overlay(
                            available_overlays,
                            PHASE_MAP_REFERENCE_OVERLAY_ID,
                            WAVE_PATCH_ACTIVITY_OVERLAY_ID,
                            SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                        ),
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
                "highlight_selection": copy.deepcopy(
                    dict(narrative_context["highlight_selection"])
                ),
                "dashboard_state_patch": {
                    "global_interaction_state": {
                        "comparison_mode": "paired_baseline_vs_wave",
                        "active_overlay_id": _preferred_overlay(
                            available_overlays,
                            PAIRED_READOUT_DELTA_OVERLAY_ID,
                            SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                        ),
                    },
                    "replay_state": {
                        "comparison_mode": "paired_baseline_vs_wave",
                        "active_overlay_id": _preferred_overlay(
                            available_overlays,
                            PAIRED_READOUT_DELTA_OVERLAY_ID,
                            SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                        ),
                    },
                },
            },
        },
        SUMMARY_ANALYSIS_PRESET_ID: {
            "step_id": SUMMARY_ANALYSIS_STEP_ID,
            "display_name": "Analysis Summary",
            "note": "Close on packaged analysis and review-facing evidence.",
            "presentation_status": PRESENTATION_STATUS_READY,
            "presentation_state_patch": {
                "active_pane_id": ANALYSIS_PANE_ID,
                "dashboard_state_patch": {
                    "global_interaction_state": {
                        "active_overlay_id": _preferred_overlay(
                            available_overlays,
                            REVIEWER_FINDINGS_OVERLAY_ID,
                            SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                        ),
                    },
                    "replay_state": {
                        "active_overlay_id": _preferred_overlay(
                            available_overlays,
                            REVIEWER_FINDINGS_OVERLAY_ID,
                            SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                        ),
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
        _validate_presentation_state_patch(
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


def _build_showcase_steps(
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
            preset_id="retinal_input_focus",
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
            step_id="active_visual_subset",
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
                step_id="active_visual_subset",
            ),
        ),
        build_showcase_step(
            step_id="activity_propagation",
            preset_id="propagation_replay",
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
                step_id="activity_propagation",
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
                    text="This is the fair baseline-versus-wave comparison beat.",
                    linked_evidence_role_ids=["shared_comparison_evidence"],
                ),
                build_showcase_narrative_annotation(
                    annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID,
                    text=(
                        "Pair the shared-comparison payload with suite rollups."
                        if suite_summary_available
                        else "Pair the shared-comparison payload with packaged experiment analysis."
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
                highlight_ready=highlight_ready,
            ),
            evidence_references=[
                build_showcase_evidence_reference(
                    evidence_role_id=APPROVED_WAVE_HIGHLIGHT_EVIDENCE_ROLE_ID,
                    artifact_role_id=ANALYSIS_UI_PAYLOAD_ROLE_ID,
                    citation_label=str(
                        narrative_context["highlight_selection"]["citation_label"]
                    ),
                    locator=narrative_context["highlight_selection"]["locator"],
                ),
                build_showcase_evidence_reference(
                    evidence_role_id=VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
                    artifact_role_id=VALIDATION_FINDINGS_ROLE_ID,
                    citation_label="Validation findings",
                    locator="validator_findings",
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
            preset_id=SUMMARY_ANALYSIS_PRESET_ID,
            cue_kind_id="export_capture",
            presentation_status=PRESENTATION_STATUS_READY,
            narrative_annotations=[
                build_showcase_narrative_annotation(
                    annotation_id=STORY_CONTEXT_ANNOTATION_ID,
                    text="Close on the packaged analysis and review-facing summary.",
                    linked_evidence_role_ids=[SUMMARY_ANALYSIS_EVIDENCE_ROLE_ID],
                ),
                build_showcase_narrative_annotation(
                    annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID,
                    text=(
                        "Anchor the closing beat to analysis and suite outputs."
                        if suite_summary_available
                        else "Anchor the closing beat to packaged experiment analysis."
                    ),
                    linked_evidence_role_ids=(
                        [SUMMARY_ANALYSIS_EVIDENCE_ROLE_ID, SUITE_ROLLUP_EVIDENCE_ROLE_ID]
                        if suite_summary_available
                        else [SUMMARY_ANALYSIS_EVIDENCE_ROLE_ID]
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


def _build_external_artifact_references(
    *,
    dashboard_context: Mapping[str, Any],
    analysis_context: Mapping[str, Any],
    validation_context: Mapping[str, Any],
    suite_context: Mapping[str, Any] | None,
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    contract_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    dashboard_metadata = dashboard_context["metadata"]
    dashboard_paths = discover_dashboard_session_bundle_paths(dashboard_metadata)
    discovered: list[dict[str, Any]] = [
        build_showcase_session_artifact_reference(
            artifact_role_id=DASHBOARD_SESSION_METADATA_ROLE_ID,
            source_kind=DASHBOARD_SESSION_SOURCE_KIND,
            path=dashboard_paths[DASHBOARD_METADATA_JSON_KEY],
            contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            bundle_id=str(dashboard_metadata["bundle_id"]),
            artifact_id=DASHBOARD_METADATA_JSON_KEY,
            format=str(dashboard_metadata["artifacts"][DASHBOARD_METADATA_JSON_KEY]["format"]),
            artifact_scope=DASHBOARD_CONTEXT_SCOPE,
            status=str(dashboard_metadata["artifacts"][DASHBOARD_METADATA_JSON_KEY]["status"]),
        ),
        build_showcase_session_artifact_reference(
            artifact_role_id=DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
            source_kind=DASHBOARD_SESSION_SOURCE_KIND,
            path=dashboard_paths[SESSION_PAYLOAD_ARTIFACT_ID],
            contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            bundle_id=str(dashboard_metadata["bundle_id"]),
            artifact_id=SESSION_PAYLOAD_ARTIFACT_ID,
            format=str(dashboard_metadata["artifacts"][SESSION_PAYLOAD_ARTIFACT_ID]["format"]),
            artifact_scope=DASHBOARD_CONTEXT_SCOPE,
            status=str(dashboard_metadata["artifacts"][SESSION_PAYLOAD_ARTIFACT_ID]["status"]),
        ),
        build_showcase_session_artifact_reference(
            artifact_role_id=DASHBOARD_SESSION_STATE_ROLE_ID,
            source_kind=DASHBOARD_SESSION_SOURCE_KIND,
            path=dashboard_paths[SESSION_STATE_ARTIFACT_ID],
            contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            bundle_id=str(dashboard_metadata["bundle_id"]),
            artifact_id=SESSION_STATE_ARTIFACT_ID,
            format=str(dashboard_metadata["artifacts"][SESSION_STATE_ARTIFACT_ID]["format"]),
            artifact_scope=DASHBOARD_CONTEXT_SCOPE,
            status=str(dashboard_metadata["artifacts"][SESSION_STATE_ARTIFACT_ID]["status"]),
        ),
    ]
    analysis_metadata = analysis_context["metadata"]
    analysis_paths = analysis_context["bundle_paths"]
    discovered.extend(
        [
            build_showcase_session_artifact_reference(
                artifact_role_id=ANALYSIS_BUNDLE_METADATA_ROLE_ID,
                source_kind="experiment_analysis_bundle",
                path=analysis_paths[ANALYSIS_METADATA_JSON_KEY],
                contract_version=str(analysis_metadata["contract_version"]),
                bundle_id=str(analysis_metadata["bundle_id"]),
                artifact_id=ANALYSIS_METADATA_JSON_KEY,
                format=str(analysis_metadata["artifacts"][ANALYSIS_METADATA_JSON_KEY]["format"]),
                artifact_scope="analysis_context",
                status=str(analysis_metadata["artifacts"][ANALYSIS_METADATA_JSON_KEY]["status"]),
            ),
            build_showcase_session_artifact_reference(
                artifact_role_id=ANALYSIS_UI_PAYLOAD_ROLE_ID,
                source_kind="experiment_analysis_bundle",
                path=analysis_context["ui_payload_path"],
                contract_version=str(analysis_metadata["contract_version"]),
                bundle_id=str(analysis_metadata["bundle_id"]),
                artifact_id=ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
                format=str(analysis_metadata["artifacts"][ANALYSIS_UI_PAYLOAD_ARTIFACT_ID]["format"]),
                artifact_scope="analysis_context",
                status=str(analysis_metadata["artifacts"][ANALYSIS_UI_PAYLOAD_ARTIFACT_ID]["status"]),
            ),
        ]
    )
    if analysis_context["offline_report_path"] is not None:
        discovered.append(
            build_showcase_session_artifact_reference(
                artifact_role_id=ANALYSIS_OFFLINE_REPORT_ROLE_ID,
                source_kind="experiment_analysis_bundle",
                path=analysis_context["offline_report_path"],
                contract_version=str(analysis_metadata["contract_version"]),
                bundle_id=str(analysis_metadata["bundle_id"]),
                artifact_id=OFFLINE_REPORT_INDEX_ARTIFACT_ID,
                format=str(analysis_metadata["artifacts"][OFFLINE_REPORT_INDEX_ARTIFACT_ID]["format"]),
                artifact_scope="analysis_context",
                status=str(analysis_metadata["artifacts"][OFFLINE_REPORT_INDEX_ARTIFACT_ID]["status"]),
            )
        )

    validation_metadata = validation_context["metadata"]
    validation_paths = validation_context["bundle_paths"]
    discovered.extend(
        [
            build_showcase_session_artifact_reference(
                artifact_role_id=VALIDATION_BUNDLE_METADATA_ROLE_ID,
                source_kind="validation_bundle",
                path=validation_paths[VALIDATION_METADATA_JSON_KEY],
                contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
                bundle_id=str(validation_metadata["bundle_id"]),
                artifact_id=VALIDATION_METADATA_JSON_KEY,
                format=str(validation_metadata["artifacts"][VALIDATION_METADATA_JSON_KEY]["format"]),
                artifact_scope=VALIDATION_GUARDRAIL_SCOPE,
                status=str(validation_metadata["artifacts"][VALIDATION_METADATA_JSON_KEY]["status"]),
            ),
            build_showcase_session_artifact_reference(
                artifact_role_id=VALIDATION_SUMMARY_ROLE_ID,
                source_kind="validation_bundle",
                path=validation_context["summary_path"],
                contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
                bundle_id=str(validation_metadata["bundle_id"]),
                artifact_id=VALIDATION_SUMMARY_ARTIFACT_ID,
                format=str(validation_metadata["artifacts"][VALIDATION_SUMMARY_ARTIFACT_ID]["format"]),
                artifact_scope=VALIDATION_GUARDRAIL_SCOPE,
                status=str(validation_metadata["artifacts"][VALIDATION_SUMMARY_ARTIFACT_ID]["status"]),
            ),
            build_showcase_session_artifact_reference(
                artifact_role_id=VALIDATION_FINDINGS_ROLE_ID,
                source_kind="validation_bundle",
                path=validation_context["findings_path"],
                contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
                bundle_id=str(validation_metadata["bundle_id"]),
                artifact_id=VALIDATOR_FINDINGS_ARTIFACT_ID,
                format=str(validation_metadata["artifacts"][VALIDATOR_FINDINGS_ARTIFACT_ID]["format"]),
                artifact_scope=VALIDATION_GUARDRAIL_SCOPE,
                status=str(validation_metadata["artifacts"][VALIDATOR_FINDINGS_ARTIFACT_ID]["status"]),
            ),
        ]
    )
    if validation_context["review_handoff_path"] is not None:
        discovered.append(
            build_showcase_session_artifact_reference(
                artifact_role_id=VALIDATION_REVIEW_HANDOFF_ROLE_ID,
                source_kind="validation_bundle",
                path=validation_context["review_handoff_path"],
                contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
                bundle_id=str(validation_metadata["bundle_id"]),
                artifact_id=REVIEW_HANDOFF_ARTIFACT_ID,
                format=str(validation_metadata["artifacts"][REVIEW_HANDOFF_ARTIFACT_ID]["format"]),
                artifact_scope=VALIDATION_GUARDRAIL_SCOPE,
                status=str(validation_metadata["artifacts"][REVIEW_HANDOFF_ARTIFACT_ID]["status"]),
            )
        )

    if suite_context is not None and suite_context.get("summary_table_artifact") is not None:
        summary_table = suite_context["summary_table_artifact"]
        suite_bundle_id = _suite_bundle_id(suite_context)
        discovered.append(
            build_showcase_session_artifact_reference(
                artifact_role_id=SUITE_SUMMARY_TABLE_ROLE_ID,
                source_kind="experiment_suite_package",
                path=summary_table["path"],
                contract_version=EXPERIMENT_SUITE_CONTRACT_VERSION,
                bundle_id=suite_bundle_id,
                artifact_id=str(summary_table["artifact_id"]),
                format="csv_experiment_suite_summary_table.v1",
                artifact_scope=SUITE_ROLLUP_SCOPE,
            )
        )
    if suite_context is not None and suite_context.get("comparison_plot_artifact") is not None:
        comparison_plot = suite_context["comparison_plot_artifact"]
        discovered.append(
            build_showcase_session_artifact_reference(
                artifact_role_id=SUITE_COMPARISON_PLOT_ROLE_ID,
                source_kind="experiment_suite_package",
                path=comparison_plot["path"],
                contract_version=EXPERIMENT_SUITE_CONTRACT_VERSION,
                bundle_id=_suite_bundle_id(suite_context),
                artifact_id=str(comparison_plot["artifact_id"]),
                format="svg_experiment_suite_comparison_plot.v1",
                artifact_scope=SUITE_ROLLUP_SCOPE,
            )
        )
    if suite_context is not None and suite_context.get("review_artifact") is not None:
        review_artifact = suite_context["review_artifact"]
        discovered.append(
            build_showcase_session_artifact_reference(
                artifact_role_id=SUITE_REVIEW_ARTIFACT_ROLE_ID,
                source_kind="experiment_suite_package",
                path=review_artifact["path"],
                contract_version=EXPERIMENT_SUITE_CONTRACT_VERSION,
                bundle_id=_suite_bundle_id(suite_context),
                artifact_id=str(review_artifact["artifact_id"]),
                format="json_experiment_suite_review_artifact.v1",
                artifact_scope=SUITE_ROLLUP_SCOPE,
            )
        )
    return _merge_explicit_artifact_overrides(
        discovered,
        raw_explicit_artifacts=raw_explicit_artifacts,
        contract_metadata=contract_metadata,
    )


def _build_operator_defaults(
    *,
    showcase_steps: Sequence[Mapping[str, Any]],
    dashboard_context: Mapping[str, Any],
    showcase_session: Mapping[str, Any],
) -> dict[str, Any]:
    first_step = dict(showcase_steps[0])
    return {
        "current_step_id": str(first_step["step_id"]),
        "current_preset_id": str(first_step["preset_id"]),
        "auto_advance": False,
        "rehearsal_mode": True,
        "default_export_target_role_id": str(showcase_session["default_export_target_role_id"]),
        "selected_readout_id": str(
            dashboard_context["payload"]["pane_inputs"][TIME_SERIES_PANE_ID]["selected_readout_id"]
        ),
        "selected_neuron_id": dashboard_context["payload"]["pane_inputs"][MORPHOLOGY_PANE_ID]["selected_neuron_id"],
    }


def _build_showcase_presentation_state(
    *,
    showcase_session: Mapping[str, Any],
    dashboard_context: Mapping[str, Any],
    showcase_steps: Sequence[Mapping[str, Any]],
    operator_defaults: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "format_version": JSON_SHOWCASE_STATE_FORMAT,
        "contract_version": SHOWCASE_SESSION_CONTRACT_VERSION,
        "plan_version": SHOWCASE_SESSION_PLAN_VERSION,
        "bundle_reference": {
            "bundle_id": str(showcase_session["bundle_id"]),
            "showcase_spec_hash": str(showcase_session["showcase_spec_hash"]),
        },
        "manifest_reference": copy.deepcopy(
            dict(dashboard_context["metadata"]["manifest_reference"])
        ),
        "presentation_status": str(showcase_session["presentation_status"]),
        "current_step_id": str(operator_defaults["current_step_id"]),
        "current_preset_id": str(operator_defaults["current_preset_id"]),
        "active_pane_id": DEFAULT_ACTIVE_PANE_BY_STEP[str(operator_defaults["current_step_id"])],
        "focus_root_ids": list(
            dashboard_context["payload"]["pane_inputs"][CIRCUIT_PANE_ID]["selected_root_ids"]
        ),
        "dashboard_state_source": {
            "artifact_role_id": DASHBOARD_SESSION_STATE_ROLE_ID,
            "bundle_id": str(dashboard_context["metadata"]["bundle_id"]),
            "state_path": str(
                discover_dashboard_session_bundle_paths(dashboard_context["metadata"])[
                    SESSION_STATE_ARTIFACT_ID
                ]
            ),
        },
        "base_dashboard_session_state": copy.deepcopy(dict(dashboard_context["state"])),
        "operator_defaults": copy.deepcopy(dict(operator_defaults)),
        "step_statuses": {
            str(step["step_id"]): str(step["presentation_status"]) for step in showcase_steps
        },
    }


def _build_showcase_script_payload(
    *,
    showcase_session: Mapping[str, Any],
    showcase_steps: Sequence[Mapping[str, Any]],
    saved_presets: Sequence[Mapping[str, Any]],
    operator_defaults: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "format_version": JSON_SHOWCASE_SCRIPT_FORMAT,
        "contract_version": SHOWCASE_SESSION_CONTRACT_VERSION,
        "plan_version": SHOWCASE_SESSION_PLAN_VERSION,
        "bundle_reference": {
            "bundle_id": str(showcase_session["bundle_id"]),
            "showcase_spec_hash": str(showcase_session["showcase_spec_hash"]),
        },
        "showcase_id": str(showcase_session["showcase_id"]),
        "display_name": str(showcase_session["display_name"]),
        "presentation_status": str(showcase_session["presentation_status"]),
        "operator_defaults": copy.deepcopy(dict(operator_defaults)),
        "step_sequence": [
            {
                "step_id": str(step["step_id"]),
                "preset_id": str(step["preset_id"]),
                "cue_kind_id": str(step["cue_kind_id"]),
                "presentation_status": str(step["presentation_status"]),
                "fallback_preset_id": step.get("fallback_preset_id"),
                "operator_control_ids": list(step["operator_control_ids"]),
                "export_target_role_ids": list(step["export_target_role_ids"]),
                "annotation_ids": [
                    str(annotation["annotation_id"])
                    for annotation in step["narrative_annotations"]
                ],
                "evidence_role_ids": [
                    str(reference["evidence_role_id"])
                    for reference in step["evidence_references"]
                ],
            }
            for step in showcase_steps
        ],
        "saved_preset_ids": [str(item["preset_id"]) for item in saved_presets],
    }


def _build_narrative_preset_catalog(
    *,
    showcase_session: Mapping[str, Any],
    dashboard_context: Mapping[str, Any],
    saved_presets: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "format_version": JSON_NARRATIVE_PRESET_CATALOG_FORMAT,
        "contract_version": SHOWCASE_SESSION_CONTRACT_VERSION,
        "bundle_reference": {
            "bundle_id": str(showcase_session["bundle_id"]),
            "showcase_spec_hash": str(showcase_session["showcase_spec_hash"]),
        },
        "dashboard_state_source": {
            "artifact_role_id": DASHBOARD_SESSION_STATE_ROLE_ID,
            "bundle_id": str(dashboard_context["metadata"]["bundle_id"]),
        },
        "saved_presets": [copy.deepcopy(dict(item)) for item in saved_presets],
    }


def _build_showcase_export_manifest(
    *,
    showcase_session: Mapping[str, Any],
    output_locations: Mapping[str, Any],
    contract_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    role_definitions = {
        str(item["export_target_role_id"]): dict(item)
        for item in discover_showcase_export_target_roles(contract_metadata)
    }
    export_targets = []
    for role_id in showcase_session["enabled_export_target_role_ids"]:
        definition = role_definitions[str(role_id)]
        path = output_locations["export_target_paths"][str(role_id)]
        export_targets.append(
            {
                "export_target_role_id": str(role_id),
                "target_kind": str(definition["target_kind"]),
                "path": str(path),
                "status": PRESENTATION_STATUS_PLANNED,
            }
        )
    return {
        "format_version": JSON_SHOWCASE_EXPORT_MANIFEST_FORMAT,
        "contract_version": SHOWCASE_SESSION_CONTRACT_VERSION,
        "bundle_reference": {
            "bundle_id": str(showcase_session["bundle_id"]),
            "showcase_spec_hash": str(showcase_session["showcase_spec_hash"]),
        },
        "default_export_target_role_id": str(showcase_session["default_export_target_role_id"]),
        "export_targets": export_targets,
    }


def _build_output_locations(
    *,
    showcase_session: Mapping[str, Any],
    contract_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    bundle_paths = discover_showcase_session_bundle_paths(showcase_session)
    bundle_directory = Path(showcase_session["bundle_layout"]["bundle_directory"]).resolve()
    exports_directory = Path(showcase_session["bundle_layout"]["exports_directory"]).resolve()
    role_definitions = {
        str(item["export_target_role_id"]): dict(item)
        for item in discover_showcase_export_target_roles(contract_metadata)
    }
    export_target_paths: dict[str, str] = {}
    for role_id in showcase_session["enabled_export_target_role_ids"]:
        file_name = DEFAULT_EXPORT_FILE_NAMES[str(role_id)]
        target_path = (exports_directory / file_name).resolve()
        export_target_paths[str(role_id)] = str(target_path)
    return {
        "bundle_directory": str(bundle_directory),
        "exports_directory": str(exports_directory),
        "metadata_path": str(bundle_paths[METADATA_JSON_KEY].resolve()),
        "showcase_script_path": str(
            bundle_paths[SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID].resolve()
        ),
        "showcase_state_path": str(
            bundle_paths[SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID].resolve()
        ),
        "narrative_preset_catalog_path": str(
            bundle_paths[NARRATIVE_PRESET_CATALOG_ARTIFACT_ID].resolve()
        ),
        "showcase_export_manifest_path": str(
            bundle_paths[SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID].resolve()
        ),
        "export_target_paths": export_target_paths,
        "export_target_kinds": {
            str(role_id): str(role_definitions[str(role_id)]["target_kind"])
            for role_id in showcase_session["enabled_export_target_role_ids"]
        },
    }


def _merge_explicit_artifact_overrides(
    discovered: Sequence[Mapping[str, Any]],
    *,
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    contract_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    hooks = {
        str(item["artifact_role_id"]): dict(item)
        for item in contract_metadata["artifact_hook_catalog"]
    }
    merged = {
        str(item["artifact_role_id"]): copy.deepcopy(dict(item)) for item in discovered
    }
    for role_id, raw in raw_explicit_artifacts.items():
        base = merged.get(role_id, {})
        hook = hooks[role_id]
        merged[role_id] = build_showcase_session_artifact_reference(
            artifact_role_id=role_id,
            source_kind=str(raw.get("source_kind", base.get("source_kind", hook["source_kind"]))),
            path=raw.get("path", base["path"]),
            contract_version=str(
                raw.get(
                    "contract_version",
                    base.get("contract_version", hook["required_contract_version"]),
                )
            ),
            bundle_id=str(raw.get("bundle_id", base.get("bundle_id", f"explicit:{role_id}"))),
            artifact_id=str(raw.get("artifact_id", base.get("artifact_id", hook["artifact_id"]))),
            format=(
                None
                if raw.get("format", base.get("format")) is None
                else str(raw.get("format", base.get("format")))
            ),
            artifact_scope=str(
                raw.get("artifact_scope", base.get("artifact_scope", hook["artifact_scope"]))
            ),
            status=str(raw.get("status", base.get("status", ASSET_STATUS_READY))),
        )
    return list(merged.values())


def _discover_dashboard_metadata_from_suite_package(
    package_metadata: Mapping[str, Any],
) -> dict[str, Any] | None:
    artifacts = discover_experiment_suite_stage_artifacts(
        package_metadata,
        stage_id="dashboard",
        artifact_id="metadata_json",
    )
    if not artifacts:
        return None
    if len(artifacts) > 1:
        raise ValueError(
            "Showcase planning found multiple dashboard-session metadata artifacts in the suite package. "
            "Pass dashboard_session_metadata_path explicitly to disambiguate."
        )
    return load_dashboard_session_metadata(Path(artifacts[0]["path"]).resolve())


def _suite_bundle_id(suite_context: Mapping[str, Any]) -> str:
    package_metadata = suite_context.get("package_metadata")
    if not isinstance(package_metadata, Mapping):
        return "experiment_suite.v1:unknown:unknown"
    suite_reference = _require_mapping(
        package_metadata["suite_reference"],
        field_name="suite_package_metadata.suite_reference",
    )
    return (
        f"{EXPERIMENT_SUITE_CONTRACT_VERSION}:"
        f"{suite_reference['suite_id']}:"
        f"{suite_reference['suite_spec_hash']}"
    )


def _normalize_raw_explicit_artifact_references(
    payload: Sequence[Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if payload is None:
        return {}
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("explicit_artifact_references must be a sequence of mappings.")
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError(
                f"explicit_artifact_references[{index}] must be a mapping."
            )
        if "artifact_role_id" not in item or "path" not in item:
            raise ValueError(
                f"explicit_artifact_references[{index}] must include artifact_role_id and path."
            )
        role_id = _normalize_identifier(
            item["artifact_role_id"],
            field_name=f"explicit_artifact_references[{index}].artifact_role_id",
        )
        if role_id in result:
            raise ValueError(
                "explicit_artifact_references must not contain duplicate artifact_role_id "
                f"{role_id!r}."
            )
        result[role_id] = {
            key: copy.deepcopy(value) for key, value in dict(item).items()
        }
    return result


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


def _validate_highlight_locator(
    *,
    locator: str | None,
    phase_refs: Sequence[Mapping[str, Any]],
    diagnostic_cards: Sequence[Mapping[str, Any]],
) -> None:
    if locator is None:
        return
    supported = {
        "wave_only_diagnostics.phase_map_references[0]": bool(phase_refs),
        "wave_only_diagnostics.diagnostic_cards[0]": bool(diagnostic_cards),
    }
    if locator not in supported or not supported[locator]:
        raise ValueError(
            "highlight_override.locator must reference one available wave-only diagnostic; "
            f"got {locator!r}."
        )


def _validate_presentation_state_patch(
    *,
    preset_id: str,
    patch: Mapping[str, Any],
    dashboard_payload: Mapping[str, Any],
) -> None:
    supported_keys = {
        "active_pane_id",
        "focus_root_ids",
        "scene_surface",
        "highlight_selection",
        "dashboard_state_patch",
    }
    unsupported = set(patch) - supported_keys
    if unsupported:
        raise ValueError(
            f"saved preset {preset_id!r} references unsupported presentation_state_patch keys {sorted(unsupported)!r}."
        )
    if "active_pane_id" in patch and str(patch["active_pane_id"]) not in _SUPPORTED_PANE_IDS:
        raise ValueError(
            f"saved preset {preset_id!r} active_pane_id {patch['active_pane_id']!r} is unsupported."
        )

    selected_root_ids = {
        int(root_id)
        for root_id in dashboard_payload["pane_inputs"][CIRCUIT_PANE_ID]["selected_root_ids"]
    }
    if "focus_root_ids" in patch:
        focus_root_ids = [int(root_id) for root_id in patch["focus_root_ids"]]
        missing = sorted(set(focus_root_ids) - selected_root_ids)
        if missing:
            raise ValueError(
                f"saved preset {preset_id!r} references unavailable geometry roots {missing!r}."
            )

    if "scene_surface" in patch:
        surface = _require_mapping(
            patch["scene_surface"],
            field_name=f"saved_presets[{preset_id!r}].scene_surface",
        )
        valid_layers = {
            str(item["layer_id"])
            for item in dashboard_payload["pane_inputs"][SCENE_PANE_ID]["render_layers"]
        }
        if str(surface["active_layer_id"]) not in valid_layers:
            raise ValueError(
                f"saved preset {preset_id!r} references unavailable scene layer "
                f"{surface['active_layer_id']!r}."
            )

    dashboard_state_patch = patch.get("dashboard_state_patch")
    if isinstance(dashboard_state_patch, Mapping):
        _validate_dashboard_state_patch(
            preset_id=preset_id,
            patch=dashboard_state_patch,
            dashboard_payload=dashboard_payload,
        )


def _validate_dashboard_state_patch(
    *,
    preset_id: str,
    patch: Mapping[str, Any],
    dashboard_payload: Mapping[str, Any],
) -> None:
    available_overlays = set(dashboard_payload["overlay_catalog"]["available_overlay_ids"])
    allowed_comparison_modes = {
        str(item["comparison_mode_id"])
        for item in dashboard_payload["pane_inputs"][TIME_SERIES_PANE_ID]["replay_model"]["comparison_mode_statuses"]
        if str(item["availability"]) == "available"
    }
    selected_root_ids = {
        int(root_id)
        for root_id in dashboard_payload["pane_inputs"][CIRCUIT_PANE_ID]["selected_root_ids"]
    }
    selected_readout_id = str(
        dashboard_payload["pane_inputs"][TIME_SERIES_PANE_ID]["selected_readout_id"]
    )
    selected_pair = _require_mapping(
        dashboard_payload["global_interaction_state"]["selected_arm_pair"],
        field_name="dashboard_session_payload.global_interaction_state.selected_arm_pair",
    )
    valid_arm_ids = {
        str(selected_pair["baseline_arm_id"]),
        str(selected_pair["wave_arm_id"]),
    }
    for state_key in ("global_interaction_state", "replay_state"):
        state_patch = patch.get(state_key)
        if not isinstance(state_patch, Mapping):
            continue
        if (
            "active_overlay_id" in state_patch
            and str(state_patch["active_overlay_id"]) not in available_overlays
        ):
            raise ValueError(
                f"saved preset {preset_id!r} references unavailable overlay "
                f"{state_patch['active_overlay_id']!r}."
            )
        if (
            "comparison_mode" in state_patch
            and str(state_patch["comparison_mode"]) not in allowed_comparison_modes
        ):
            raise ValueError(
                f"saved preset {preset_id!r} references unavailable comparison_mode "
                f"{state_patch['comparison_mode']!r}."
            )
        if "selected_neuron_id" in state_patch and int(state_patch["selected_neuron_id"]) not in selected_root_ids:
            raise ValueError(
                f"saved preset {preset_id!r} references unavailable selected_neuron_id "
                f"{state_patch['selected_neuron_id']!r}."
            )
        if (
            "selected_readout_id" in state_patch
            and str(state_patch["selected_readout_id"]) != selected_readout_id
        ):
            raise ValueError(
                f"saved preset {preset_id!r} references unavailable selected_readout_id "
                f"{state_patch['selected_readout_id']!r}."
            )
        if "selected_arm_pair" in state_patch:
            pair_patch = _require_mapping(
                state_patch["selected_arm_pair"],
                field_name=f"saved_presets[{preset_id!r}].dashboard_state_patch.{state_key}.selected_arm_pair",
            )
            if (
                "active_arm_id" in pair_patch
                and str(pair_patch["active_arm_id"]) not in valid_arm_ids
            ):
                raise ValueError(
                    f"saved preset {preset_id!r} references unavailable active_arm_id "
                    f"{pair_patch['active_arm_id']!r}."
                )


def _roll_up_presentation_status(
    showcase_steps: Sequence[Mapping[str, Any]],
) -> str:
    statuses = [str(item["presentation_status"]) for item in showcase_steps]
    return min(statuses, key=lambda item: _PRESENTATION_STATUS_PRIORITY[item])


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


def _highlight_annotations(*, highlight_ready: bool) -> list[dict[str, Any]]:
    annotations = [
        build_showcase_narrative_annotation(
            annotation_id=SCIENTIFIC_GUARDRAIL_ANNOTATION_ID,
            text=(
                "This wave-only beat is validation-backed and approved."
                if highlight_ready
                else "The requested highlight is not approved for display."
            ),
            linked_evidence_role_ids=[
                APPROVED_WAVE_HIGHLIGHT_EVIDENCE_ROLE_ID,
                VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
            ],
        ),
        build_showcase_narrative_annotation(
            annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID,
            text="Keep the highlight traceable to analysis and validation artifacts.",
            linked_evidence_role_ids=[
                APPROVED_WAVE_HIGHLIGHT_EVIDENCE_ROLE_ID,
                VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
            ],
        ),
    ]
    if not highlight_ready:
        annotations.append(
            build_showcase_narrative_annotation(
                annotation_id=FALLBACK_NOTICE_ANNOTATION_ID,
                text="Fall back to the paired comparison rather than fabricating a substitute wave-only effect.",
            )
        )
    return annotations


def _select_suite_artifact(
    items: Sequence[Mapping[str, Any]],
    *,
    preferred_artifact_id: str | None,
    preferred_section_id: str | None,
) -> dict[str, Any] | None:
    normalized = _normalize_mapping_sequence(items, field_name="suite_artifacts")
    if not normalized:
        return None
    candidates = normalized
    if preferred_artifact_id is not None:
        exact = [
            dict(item)
            for item in normalized
            if str(item.get("artifact_id")) == preferred_artifact_id
        ]
        if exact:
            return exact[0]
    if preferred_section_id is not None:
        section_matches = [
            dict(item)
            for item in normalized
            if str(item.get("section_id")) == preferred_section_id
        ]
        if section_matches:
            candidates = section_matches
    candidates.sort(
        key=lambda item: (
            "" if item.get("section_id") is None else str(item["section_id"]),
            str(item["artifact_id"]),
        )
    )
    return candidates[0]


def _load_upstream_bundle_metadata_from_dashboard(
    *,
    dashboard_metadata: Mapping[str, Any],
    dashboard_role_id: str,
    explicit_metadata_path: str | None,
    loader,
) -> dict[str, Any]:
    if explicit_metadata_path is not None:
        return loader(Path(explicit_metadata_path).resolve())
    refs = discover_dashboard_session_artifact_references(
        dashboard_metadata,
        artifact_role_id=dashboard_role_id,
    )
    if len(refs) != 1:
        raise ValueError(
            f"dashboard_session metadata must include exactly one artifact reference for {dashboard_role_id!r}."
        )
    return loader(Path(refs[0]["path"]).resolve())


def _explicit_or_default_path(
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    *,
    role_id: str,
    default_path: str | Path,
) -> Path:
    raw = raw_explicit_artifacts.get(role_id)
    if raw is None:
        return Path(default_path).resolve()
    return Path(raw["path"]).resolve()


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


def _load_json_mapping(path: str | Path, *, field_name: str) -> dict[str, Any]:
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise ValueError(f"{field_name} is missing required local artifact {resolved}.")
    with resolved.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must deserialize to a mapping.")
    return copy.deepcopy(dict(payload))


def _require_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return copy.deepcopy(dict(value))

