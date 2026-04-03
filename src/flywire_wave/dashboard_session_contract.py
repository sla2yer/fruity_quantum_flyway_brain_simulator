from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .experiment_analysis_contract import (
    ANALYSIS_UI_PAYLOAD_ARTIFACT_ID as EXPERIMENT_ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
    EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION,
    OFFLINE_REPORT_INDEX_ARTIFACT_ID as EXPERIMENT_ANALYSIS_OFFLINE_REPORT_ARTIFACT_ID,
)
from .io_utils import write_json
from .simulator_result_contract import (
    DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
    SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
    parse_simulator_manifest_reference,
)
from .stimulus_contract import (
    ASSET_STATUS_MISSING,
    ASSET_STATUS_READY,
    DEFAULT_HASH_ALGORITHM,
    _normalize_asset_status,
    _normalize_float,
    _normalize_identifier,
    _normalize_nonempty_string,
    _normalize_parameter_hash,
)
from .validation_contract import (
    OFFLINE_REVIEW_REPORT_ARTIFACT_ID as VALIDATION_OFFLINE_REPORT_ARTIFACT_ID,
    REVIEW_HANDOFF_ARTIFACT_ID as VALIDATION_REVIEW_HANDOFF_ARTIFACT_ID,
    VALIDATION_LADDER_CONTRACT_VERSION,
    VALIDATION_SUMMARY_ARTIFACT_ID,
)


DASHBOARD_SESSION_CONTRACT_VERSION = "dashboard_session.v1"
DASHBOARD_SESSION_DESIGN_NOTE = "docs/ui_dashboard_design.md"
DASHBOARD_SESSION_DESIGN_NOTE_VERSION = "dashboard_session_design_note.v1"

DEFAULT_DASHBOARD_SESSION_DIRECTORY_NAME = "dashboard_sessions"

SELF_CONTAINED_STATIC_APP_DELIVERY_MODEL = "self_contained_static_app"
STATIC_REPORT_BRIDGE_DELIVERY_MODEL = "static_report_bridge"
SUPPORTED_UI_DELIVERY_MODELS = (
    SELF_CONTAINED_STATIC_APP_DELIVERY_MODEL,
    STATIC_REPORT_BRIDGE_DELIVERY_MODEL,
)
DEFAULT_UI_DELIVERY_MODEL = SELF_CONTAINED_STATIC_APP_DELIVERY_MODEL

METADATA_JSON_KEY = "metadata_json"
SESSION_PAYLOAD_ARTIFACT_ID = "session_payload"
SESSION_STATE_ARTIFACT_ID = "session_state"
APP_SHELL_INDEX_ARTIFACT_ID = "app_shell_index"

CONTRACT_METADATA_SCOPE = "contract_metadata"
SESSION_PACKAGE_SCOPE = "session_package"
INTERACTION_STATE_SCOPE = "interaction_state"
APP_SHELL_SCOPE = "app_shell"

SIMULATOR_RESULT_SOURCE_KIND = "simulator_result_bundle"
EXPERIMENT_ANALYSIS_SOURCE_KIND = "experiment_analysis_bundle"
VALIDATION_BUNDLE_SOURCE_KIND = "validation_bundle"
DASHBOARD_SESSION_PACKAGE_SOURCE_KIND = "dashboard_session_package"
WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND = "whole_brain_context_session_package"
SUPPORTED_ARTIFACT_SOURCE_KINDS = (
    SIMULATOR_RESULT_SOURCE_KIND,
    EXPERIMENT_ANALYSIS_SOURCE_KIND,
    VALIDATION_BUNDLE_SOURCE_KIND,
    DASHBOARD_SESSION_PACKAGE_SOURCE_KIND,
    WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND,
)

SCENE_PANE_ID = "scene"
CIRCUIT_PANE_ID = "circuit"
MORPHOLOGY_PANE_ID = "morphology"
TIME_SERIES_PANE_ID = "time_series"
ANALYSIS_PANE_ID = "analysis"
SUPPORTED_PANE_IDS = (
    SCENE_PANE_ID,
    CIRCUIT_PANE_ID,
    MORPHOLOGY_PANE_ID,
    TIME_SERIES_PANE_ID,
    ANALYSIS_PANE_ID,
)

CONTEXT_OVERLAY_CATEGORY = "context"
SHARED_COMPARISON_OVERLAY_CATEGORY = "shared_comparison"
WAVE_ONLY_DIAGNOSTIC_OVERLAY_CATEGORY = "wave_only_diagnostic"
VALIDATION_EVIDENCE_OVERLAY_CATEGORY = "validation_evidence"
SHARED_COMPARISON_SCOPE = SHARED_COMPARISON_OVERLAY_CATEGORY
SUPPORTED_OVERLAY_CATEGORIES = (
    CONTEXT_OVERLAY_CATEGORY,
    SHARED_COMPARISON_OVERLAY_CATEGORY,
    WAVE_ONLY_DIAGNOSTIC_OVERLAY_CATEGORY,
    VALIDATION_EVIDENCE_OVERLAY_CATEGORY,
)

STIMULUS_CONTEXT_FRAME_OVERLAY_ID = "stimulus_context_frame"
SELECTED_SUBSET_HIGHLIGHT_OVERLAY_ID = "selected_subset_highlight"
SHARED_READOUT_ACTIVITY_OVERLAY_ID = "shared_readout_activity"
PAIRED_READOUT_DELTA_OVERLAY_ID = "paired_readout_delta"
WAVE_PATCH_ACTIVITY_OVERLAY_ID = "wave_patch_activity"
PHASE_MAP_REFERENCE_OVERLAY_ID = "phase_map_reference"
VALIDATION_STATUS_BADGES_OVERLAY_ID = "validation_status_badges"
REVIEWER_FINDINGS_OVERLAY_ID = "reviewer_findings"
SUPPORTED_OVERLAY_IDS = (
    STIMULUS_CONTEXT_FRAME_OVERLAY_ID,
    SELECTED_SUBSET_HIGHLIGHT_OVERLAY_ID,
    SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    PAIRED_READOUT_DELTA_OVERLAY_ID,
    WAVE_PATCH_ACTIVITY_OVERLAY_ID,
    PHASE_MAP_REFERENCE_OVERLAY_ID,
    VALIDATION_STATUS_BADGES_OVERLAY_ID,
    REVIEWER_FINDINGS_OVERLAY_ID,
)

SINGLE_ARM_COMPARISON_MODE = "single_arm"
PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE = "paired_baseline_vs_wave"
PAIRED_DELTA_COMPARISON_MODE = "paired_delta"
SUPPORTED_COMPARISON_MODES = (
    SINGLE_ARM_COMPARISON_MODE,
    PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
    PAIRED_DELTA_COMPARISON_MODE,
)
DEFAULT_COMPARISON_MODE = PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE
DEFAULT_ACTIVE_OVERLAY_ID = SHARED_READOUT_ACTIVITY_OVERLAY_ID

PLAYBACK_PAUSED = "paused"
PLAYBACK_PLAYING = "playing"
SUPPORTED_PLAYBACK_STATES = (
    PLAYBACK_PAUSED,
    PLAYBACK_PLAYING,
)
DEFAULT_PLAYBACK_STATE = PLAYBACK_PAUSED

SESSION_STATE_EXPORT_TARGET_ID = "session_state_json"
PANE_SNAPSHOT_EXPORT_TARGET_ID = "pane_snapshot_png"
METRICS_EXPORT_TARGET_ID = "metrics_json"
REPLAY_FRAME_SEQUENCE_EXPORT_TARGET_ID = "replay_frame_sequence"
SUPPORTED_EXPORT_TARGET_IDS = (
    SESSION_STATE_EXPORT_TARGET_ID,
    PANE_SNAPSHOT_EXPORT_TARGET_ID,
    METRICS_EXPORT_TARGET_ID,
    REPLAY_FRAME_SEQUENCE_EXPORT_TARGET_ID,
)
DEFAULT_EXPORT_TARGET_ID = SESSION_STATE_EXPORT_TARGET_ID

SESSION_STATE_EXPORT_KIND = "session_state"
STILL_IMAGE_EXPORT_KIND = "still_image"
METRICS_EXPORT_KIND = "metrics_export"
REPLAY_EXPORT_KIND = "replay_export"
SUPPORTED_EXPORT_TARGET_KINDS = (
    SESSION_STATE_EXPORT_KIND,
    STILL_IMAGE_EXPORT_KIND,
    METRICS_EXPORT_KIND,
    REPLAY_EXPORT_KIND,
)

BASELINE_BUNDLE_METADATA_ROLE_ID = "baseline_bundle_metadata"
BASELINE_UI_PAYLOAD_ROLE_ID = "baseline_ui_comparison_payload"
WAVE_BUNDLE_METADATA_ROLE_ID = "wave_bundle_metadata"
WAVE_UI_PAYLOAD_ROLE_ID = "wave_ui_comparison_payload"
ANALYSIS_BUNDLE_METADATA_ROLE_ID = "analysis_bundle_metadata"
ANALYSIS_UI_PAYLOAD_ROLE_ID = "analysis_ui_payload"
ANALYSIS_OFFLINE_REPORT_ROLE_ID = "analysis_offline_report"
VALIDATION_BUNDLE_METADATA_ROLE_ID = "validation_bundle_metadata"
VALIDATION_SUMMARY_ROLE_ID = "validation_summary"
VALIDATION_REVIEW_HANDOFF_ROLE_ID = "validation_review_handoff"
VALIDATION_OFFLINE_REPORT_ROLE_ID = "validation_offline_report"
WHOLE_BRAIN_CONTEXT_SESSION_METADATA_ROLE_ID = "whole_brain_context_session_metadata"
WHOLE_BRAIN_CONTEXT_VIEW_PAYLOAD_ROLE_ID = "context_view_payload"
WHOLE_BRAIN_CONTEXT_QUERY_CATALOG_ROLE_ID = "context_query_catalog"
WHOLE_BRAIN_CONTEXT_VIEW_STATE_ROLE_ID = "context_view_state"
DASHBOARD_SESSION_METADATA_ROLE_ID = "dashboard_session_metadata"
DASHBOARD_SESSION_PAYLOAD_ROLE_ID = "dashboard_session_payload"
DASHBOARD_SESSION_STATE_ROLE_ID = "dashboard_session_state"
DASHBOARD_APP_SHELL_ROLE_ID = "dashboard_app_shell"
SUPPORTED_ARTIFACT_ROLE_IDS = (
    BASELINE_BUNDLE_METADATA_ROLE_ID,
    BASELINE_UI_PAYLOAD_ROLE_ID,
    WAVE_BUNDLE_METADATA_ROLE_ID,
    WAVE_UI_PAYLOAD_ROLE_ID,
    ANALYSIS_BUNDLE_METADATA_ROLE_ID,
    ANALYSIS_UI_PAYLOAD_ROLE_ID,
    ANALYSIS_OFFLINE_REPORT_ROLE_ID,
    VALIDATION_BUNDLE_METADATA_ROLE_ID,
    VALIDATION_SUMMARY_ROLE_ID,
    VALIDATION_REVIEW_HANDOFF_ROLE_ID,
    VALIDATION_OFFLINE_REPORT_ROLE_ID,
    WHOLE_BRAIN_CONTEXT_SESSION_METADATA_ROLE_ID,
    WHOLE_BRAIN_CONTEXT_VIEW_PAYLOAD_ROLE_ID,
    WHOLE_BRAIN_CONTEXT_QUERY_CATALOG_ROLE_ID,
    WHOLE_BRAIN_CONTEXT_VIEW_STATE_ROLE_ID,
    DASHBOARD_SESSION_METADATA_ROLE_ID,
    DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
    DASHBOARD_SESSION_STATE_ROLE_ID,
    DASHBOARD_APP_SHELL_ROLE_ID,
)

REQUIRED_EXTERNAL_ARTIFACT_ROLE_IDS = (
    BASELINE_BUNDLE_METADATA_ROLE_ID,
    WAVE_BUNDLE_METADATA_ROLE_ID,
    ANALYSIS_BUNDLE_METADATA_ROLE_ID,
    ANALYSIS_UI_PAYLOAD_ROLE_ID,
    VALIDATION_BUNDLE_METADATA_ROLE_ID,
    VALIDATION_SUMMARY_ROLE_ID,
    VALIDATION_REVIEW_HANDOFF_ROLE_ID,
)
REQUIRED_LOCAL_ARTIFACT_ROLE_IDS = (
    DASHBOARD_SESSION_METADATA_ROLE_ID,
    DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
    DASHBOARD_SESSION_STATE_ROLE_ID,
    DASHBOARD_APP_SHELL_ROLE_ID,
)

SIMULATOR_UI_COMPARISON_PAYLOAD_ARTIFACT_ID = "ui_comparison_payload"

JSON_SESSION_PAYLOAD_FORMAT = "json_dashboard_session_payload.v1"
JSON_SESSION_STATE_FORMAT = "json_dashboard_session_state.v1"
HTML_APP_SHELL_FORMAT = "html_dashboard_app_shell.v1"

REQUIRED_UPSTREAM_CONTRACTS = (
    SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
    EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION,
    VALIDATION_LADDER_CONTRACT_VERSION,
)

_OVERLAY_CATEGORY_ORDER = {value: index for index, value in enumerate(SUPPORTED_OVERLAY_CATEGORIES)}
_OVERLAY_ID_ORDER = {value: index for index, value in enumerate(SUPPORTED_OVERLAY_IDS)}
_COMPARISON_MODE_ORDER = {value: index for index, value in enumerate(SUPPORTED_COMPARISON_MODES)}
_EXPORT_TARGET_ORDER = {value: index for index, value in enumerate(SUPPORTED_EXPORT_TARGET_IDS)}
_EXPORT_KIND_ORDER = {value: index for index, value in enumerate(SUPPORTED_EXPORT_TARGET_KINDS)}
_ARTIFACT_ROLE_ORDER = {value: index for index, value in enumerate(SUPPORTED_ARTIFACT_ROLE_IDS)}
_SOURCE_KIND_ORDER = {value: index for index, value in enumerate(SUPPORTED_ARTIFACT_SOURCE_KINDS)}
_PANE_ORDER = {value: index for index, value in enumerate(SUPPORTED_PANE_IDS)}


@dataclass(frozen=True)
class DashboardSessionBundlePaths:
    processed_simulator_results_dir: Path
    experiment_id: str
    session_spec_hash: str
    bundle_directory: Path
    app_directory: Path
    metadata_json_path: Path
    session_payload_path: Path
    session_state_path: Path
    app_shell_index_path: Path

    @property
    def bundle_id(self) -> str:
        return (
            f"{DASHBOARD_SESSION_CONTRACT_VERSION}:"
            f"{self.experiment_id}:{self.session_spec_hash}"
        )

    def asset_paths(self) -> dict[str, Path]:
        return {
            METADATA_JSON_KEY: self.metadata_json_path,
            SESSION_PAYLOAD_ARTIFACT_ID: self.session_payload_path,
            SESSION_STATE_ARTIFACT_ID: self.session_state_path,
            APP_SHELL_INDEX_ARTIFACT_ID: self.app_shell_index_path,
        }


def build_dashboard_session_bundle_paths(
    *,
    experiment_id: str,
    session_spec_hash: str,
    processed_simulator_results_dir: str | Path = DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
) -> DashboardSessionBundlePaths:
    normalized_experiment_id = _normalize_identifier(
        experiment_id,
        field_name="experiment_id",
    )
    normalized_session_spec_hash = _normalize_parameter_hash(session_spec_hash)
    processed_dir = Path(processed_simulator_results_dir).resolve()
    bundle_directory = (
        processed_dir
        / DEFAULT_DASHBOARD_SESSION_DIRECTORY_NAME
        / normalized_experiment_id
        / normalized_session_spec_hash
    ).resolve()
    app_directory = (bundle_directory / "app").resolve()
    return DashboardSessionBundlePaths(
        processed_simulator_results_dir=processed_dir,
        experiment_id=normalized_experiment_id,
        session_spec_hash=normalized_session_spec_hash,
        bundle_directory=bundle_directory,
        app_directory=app_directory,
        metadata_json_path=bundle_directory / "dashboard_session.json",
        session_payload_path=bundle_directory / "dashboard_session_payload.json",
        session_state_path=bundle_directory / "session_state.json",
        app_shell_index_path=app_directory / "index.html",
    )


def resolve_dashboard_session_metadata_path(
    *,
    experiment_id: str,
    session_spec_hash: str,
    processed_simulator_results_dir: str | Path = DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
) -> Path:
    return build_dashboard_session_bundle_paths(
        experiment_id=experiment_id,
        session_spec_hash=session_spec_hash,
        processed_simulator_results_dir=processed_simulator_results_dir,
    ).metadata_json_path


def build_dashboard_pane_definition(
    *,
    pane_id: str,
    display_name: str,
    description: str,
    sequence_index: int,
    supports_time_cursor: bool,
    supports_neuron_selection: bool,
    supports_readout_selection: bool,
    supported_overlay_categories: Sequence[str],
    primary_artifact_role_ids: Sequence[str],
    default_overlay_id: str,
) -> dict[str, Any]:
    return parse_dashboard_pane_definition(
        {
            "pane_id": pane_id,
            "display_name": display_name,
            "description": description,
            "sequence_index": sequence_index,
            "supports_time_cursor": supports_time_cursor,
            "supports_neuron_selection": supports_neuron_selection,
            "supports_readout_selection": supports_readout_selection,
            "supported_overlay_categories": list(supported_overlay_categories),
            "primary_artifact_role_ids": list(primary_artifact_role_ids),
            "default_overlay_id": default_overlay_id,
        }
    )


def build_dashboard_overlay_definition(
    *,
    overlay_id: str,
    display_name: str,
    description: str,
    overlay_category: str,
    supported_pane_ids: Sequence[str],
    required_artifact_role_ids: Sequence[str],
    supported_comparison_modes: Sequence[str],
    fairness_note: str,
) -> dict[str, Any]:
    return parse_dashboard_overlay_definition(
        {
            "overlay_id": overlay_id,
            "display_name": display_name,
            "description": description,
            "overlay_category": overlay_category,
            "supported_pane_ids": list(supported_pane_ids),
            "required_artifact_role_ids": list(required_artifact_role_ids),
            "supported_comparison_modes": list(supported_comparison_modes),
            "fairness_note": fairness_note,
        }
    )


def build_dashboard_comparison_mode_definition(
    *,
    comparison_mode_id: str,
    display_name: str,
    description: str,
    required_arm_count: int,
    requires_shared_timebase: bool,
    allowed_overlay_categories: Sequence[str],
) -> dict[str, Any]:
    return parse_dashboard_comparison_mode_definition(
        {
            "comparison_mode_id": comparison_mode_id,
            "display_name": display_name,
            "description": description,
            "required_arm_count": required_arm_count,
            "requires_shared_timebase": requires_shared_timebase,
            "allowed_overlay_categories": list(allowed_overlay_categories),
        }
    )


def build_dashboard_export_target_definition(
    *,
    export_target_id: str,
    display_name: str,
    description: str,
    target_kind: str,
    supported_pane_ids: Sequence[str],
    requires_time_cursor: bool,
) -> dict[str, Any]:
    return parse_dashboard_export_target_definition(
        {
            "export_target_id": export_target_id,
            "display_name": display_name,
            "description": description,
            "target_kind": target_kind,
            "supported_pane_ids": list(supported_pane_ids),
            "requires_time_cursor": requires_time_cursor,
        }
    )


def build_dashboard_artifact_hook_definition(
    *,
    artifact_role_id: str,
    display_name: str,
    description: str,
    source_kind: str,
    required_contract_version: str,
    artifact_id: str,
    artifact_scope: str,
    supported_pane_ids: Sequence[str],
    discovery_note: str,
) -> dict[str, Any]:
    return parse_dashboard_artifact_hook_definition(
        {
            "artifact_role_id": artifact_role_id,
            "display_name": display_name,
            "description": description,
            "source_kind": source_kind,
            "required_contract_version": required_contract_version,
            "artifact_id": artifact_id,
            "artifact_scope": artifact_scope,
            "supported_pane_ids": list(supported_pane_ids),
            "discovery_note": discovery_note,
        }
    )


def build_dashboard_selected_arm_pair_reference(
    *,
    baseline_arm_id: str,
    wave_arm_id: str,
    active_arm_id: str | None = None,
) -> dict[str, Any]:
    return parse_dashboard_selected_arm_pair_reference(
        {
            "baseline_arm_id": baseline_arm_id,
            "wave_arm_id": wave_arm_id,
            "active_arm_id": wave_arm_id if active_arm_id is None else active_arm_id,
        }
    )


def build_dashboard_time_cursor(
    *,
    time_ms: float = 0.0,
    sample_index: int = 0,
    playback_state: str = DEFAULT_PLAYBACK_STATE,
) -> dict[str, Any]:
    return parse_dashboard_time_cursor(
        {
            "time_ms": time_ms,
            "sample_index": sample_index,
            "playback_state": playback_state,
        }
    )


def build_dashboard_global_interaction_state(
    *,
    selected_arm_pair: Mapping[str, Any],
    selected_neuron_id: str | int | None = None,
    selected_readout_id: str | None = None,
    active_overlay_id: str = DEFAULT_ACTIVE_OVERLAY_ID,
    comparison_mode: str = DEFAULT_COMPARISON_MODE,
    time_cursor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return parse_dashboard_global_interaction_state(
        {
            "selected_arm_pair": dict(selected_arm_pair),
            "selected_neuron_id": selected_neuron_id,
            "selected_readout_id": selected_readout_id,
            "active_overlay_id": active_overlay_id,
            "comparison_mode": comparison_mode,
            "time_cursor": (
                build_dashboard_time_cursor() if time_cursor is None else dict(time_cursor)
            ),
        }
    )


def build_dashboard_session_artifact_reference(
    *,
    artifact_role_id: str,
    source_kind: str,
    path: str | Path,
    contract_version: str,
    bundle_id: str,
    artifact_id: str,
    format: str | None = None,
    artifact_scope: str | None = None,
    status: str = ASSET_STATUS_READY,
) -> dict[str, Any]:
    return parse_dashboard_session_artifact_reference(
        {
            "artifact_role_id": artifact_role_id,
            "source_kind": source_kind,
            "path": str(Path(path).resolve()),
            "contract_version": contract_version,
            "bundle_id": bundle_id,
            "artifact_id": artifact_id,
            "format": format,
            "artifact_scope": artifact_scope,
            "status": status,
        }
    )


def build_dashboard_session_contract_metadata(
    *,
    pane_definitions: Sequence[Mapping[str, Any]] | None = None,
    overlay_definitions: Sequence[Mapping[str, Any]] | None = None,
    comparison_mode_definitions: Sequence[Mapping[str, Any]] | None = None,
    export_target_definitions: Sequence[Mapping[str, Any]] | None = None,
    artifact_hook_definitions: Sequence[Mapping[str, Any]] | None = None,
    default_ui_delivery_model: str = DEFAULT_UI_DELIVERY_MODEL,
) -> dict[str, Any]:
    payload = {
        "contract_version": DASHBOARD_SESSION_CONTRACT_VERSION,
        "design_note": DASHBOARD_SESSION_DESIGN_NOTE,
        "design_note_version": DASHBOARD_SESSION_DESIGN_NOTE_VERSION,
        "default_ui_delivery_model": default_ui_delivery_model,
        "supported_ui_delivery_models": list(SUPPORTED_UI_DELIVERY_MODELS),
        "required_upstream_contracts": list(REQUIRED_UPSTREAM_CONTRACTS),
        "supported_pane_ids": list(SUPPORTED_PANE_IDS),
        "supported_overlay_categories": list(SUPPORTED_OVERLAY_CATEGORIES),
        "supported_overlay_ids": list(SUPPORTED_OVERLAY_IDS),
        "supported_comparison_modes": list(SUPPORTED_COMPARISON_MODES),
        "supported_export_target_ids": list(SUPPORTED_EXPORT_TARGET_IDS),
        "supported_export_target_kinds": list(SUPPORTED_EXPORT_TARGET_KINDS),
        "supported_playback_states": list(SUPPORTED_PLAYBACK_STATES),
        "supported_artifact_source_kinds": list(SUPPORTED_ARTIFACT_SOURCE_KINDS),
        "supported_artifact_role_ids": list(SUPPORTED_ARTIFACT_ROLE_IDS),
        "default_overlay_id": DEFAULT_ACTIVE_OVERLAY_ID,
        "default_comparison_mode": DEFAULT_COMPARISON_MODE,
        "default_export_target_id": DEFAULT_EXPORT_TARGET_ID,
        "linked_selection_invariants": list(_default_linked_selection_invariants()),
        "fairness_boundary_invariants": list(_default_fairness_boundary_invariants()),
        "pane_catalog": list(
            pane_definitions if pane_definitions is not None else _default_pane_catalog()
        ),
        "overlay_catalog": list(
            overlay_definitions
            if overlay_definitions is not None
            else _default_overlay_catalog()
        ),
        "comparison_mode_catalog": list(
            comparison_mode_definitions
            if comparison_mode_definitions is not None
            else _default_comparison_mode_catalog()
        ),
        "export_target_catalog": list(
            export_target_definitions
            if export_target_definitions is not None
            else _default_export_target_catalog()
        ),
        "artifact_hook_catalog": list(
            artifact_hook_definitions
            if artifact_hook_definitions is not None
            else _default_artifact_hook_catalog()
        ),
    }
    return parse_dashboard_session_contract_metadata(payload)


def build_dashboard_session_spec_hash(
    *,
    manifest_reference: Mapping[str, Any],
    ui_delivery_model: str,
    global_interaction_state: Mapping[str, Any],
    enabled_export_target_ids: Sequence[str],
    artifact_references: Sequence[Mapping[str, Any]],
) -> str:
    identity_payload = _build_session_identity_payload(
        manifest_reference=manifest_reference,
        ui_delivery_model=ui_delivery_model,
        global_interaction_state=global_interaction_state,
        enabled_export_target_ids=enabled_export_target_ids,
        artifact_references=artifact_references,
    )
    serialized = json.dumps(
        identity_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_dashboard_session_metadata(
    *,
    manifest_reference: Mapping[str, Any],
    global_interaction_state: Mapping[str, Any],
    artifact_references: Sequence[Mapping[str, Any]],
    processed_simulator_results_dir: str | Path = DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
    enabled_export_target_ids: Sequence[str] | None = None,
    default_export_target_id: str = DEFAULT_EXPORT_TARGET_ID,
    ui_delivery_model: str = DEFAULT_UI_DELIVERY_MODEL,
    session_payload_status: str = ASSET_STATUS_MISSING,
    session_state_status: str = ASSET_STATUS_READY,
    app_shell_status: str = ASSET_STATUS_MISSING,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_contract = parse_dashboard_session_contract_metadata(
        contract_metadata
        if contract_metadata is not None
        else build_dashboard_session_contract_metadata()
    )
    normalized_manifest_reference = parse_simulator_manifest_reference(manifest_reference)
    normalized_global_state = _normalize_global_interaction_state_against_contract(
        global_interaction_state,
        contract_metadata=normalized_contract,
    )
    normalized_enabled_export_target_ids = _normalize_known_value_list(
        enabled_export_target_ids
        if enabled_export_target_ids is not None
        else normalized_contract["supported_export_target_ids"],
        field_name="enabled_export_target_ids",
        supported_values=SUPPORTED_EXPORT_TARGET_IDS,
        allow_empty=False,
    )
    normalized_default_export_target_id = _normalize_export_target_id(default_export_target_id)
    if normalized_default_export_target_id not in normalized_enabled_export_target_ids:
        raise ValueError(
            "default_export_target_id must be one of enabled_export_target_ids."
        )
    normalized_ui_delivery_model = _normalize_ui_delivery_model(ui_delivery_model)
    normalized_external_artifact_references = _normalize_artifact_reference_catalog(
        artifact_references,
        field_name="artifact_references",
    )
    _validate_artifact_references_against_contract(
        normalized_external_artifact_references,
        contract_metadata=normalized_contract,
        field_name="artifact_references",
    )

    session_spec_hash = build_dashboard_session_spec_hash(
        manifest_reference=normalized_manifest_reference,
        ui_delivery_model=normalized_ui_delivery_model,
        global_interaction_state=normalized_global_state,
        enabled_export_target_ids=normalized_enabled_export_target_ids,
        artifact_references=normalized_external_artifact_references,
    )
    bundle_paths = build_dashboard_session_bundle_paths(
        experiment_id=normalized_manifest_reference["experiment_id"],
        session_spec_hash=session_spec_hash,
        processed_simulator_results_dir=processed_simulator_results_dir,
    )
    artifacts = {
        METADATA_JSON_KEY: _artifact_record(
            path=bundle_paths.metadata_json_path,
            format="json_dashboard_session_metadata.v1",
            status=ASSET_STATUS_READY,
            artifact_scope=CONTRACT_METADATA_SCOPE,
            description="Authoritative Milestone 14 dashboard-session metadata.",
        ),
        SESSION_PAYLOAD_ARTIFACT_ID: _artifact_record(
            path=bundle_paths.session_payload_path,
            format=JSON_SESSION_PAYLOAD_FORMAT,
            status=session_payload_status,
            artifact_scope=SESSION_PACKAGE_SCOPE,
            description="Reserved packaged dashboard-session payload for the static application shell.",
        ),
        SESSION_STATE_ARTIFACT_ID: _artifact_record(
            path=bundle_paths.session_state_path,
            format=JSON_SESSION_STATE_FORMAT,
            status=session_state_status,
            artifact_scope=INTERACTION_STATE_SCOPE,
            description="Exportable serialized dashboard global interaction state for deterministic replay.",
        ),
        APP_SHELL_INDEX_ARTIFACT_ID: _artifact_record(
            path=bundle_paths.app_shell_index_path,
            format=HTML_APP_SHELL_FORMAT,
            status=app_shell_status,
            artifact_scope=APP_SHELL_SCOPE,
            description="Reserved offline app-shell entrypoint for the self-contained Milestone 14 dashboard.",
        ),
    }
    local_artifact_references = [
        build_dashboard_session_artifact_reference(
            artifact_role_id=DASHBOARD_SESSION_METADATA_ROLE_ID,
            source_kind=DASHBOARD_SESSION_PACKAGE_SOURCE_KIND,
            path=artifacts[METADATA_JSON_KEY]["path"],
            contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            bundle_id=bundle_paths.bundle_id,
            artifact_id=METADATA_JSON_KEY,
            format=artifacts[METADATA_JSON_KEY]["format"],
            artifact_scope=artifacts[METADATA_JSON_KEY]["artifact_scope"],
            status=artifacts[METADATA_JSON_KEY]["status"],
        ),
        build_dashboard_session_artifact_reference(
            artifact_role_id=DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
            source_kind=DASHBOARD_SESSION_PACKAGE_SOURCE_KIND,
            path=artifacts[SESSION_PAYLOAD_ARTIFACT_ID]["path"],
            contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            bundle_id=bundle_paths.bundle_id,
            artifact_id=SESSION_PAYLOAD_ARTIFACT_ID,
            format=artifacts[SESSION_PAYLOAD_ARTIFACT_ID]["format"],
            artifact_scope=artifacts[SESSION_PAYLOAD_ARTIFACT_ID]["artifact_scope"],
            status=artifacts[SESSION_PAYLOAD_ARTIFACT_ID]["status"],
        ),
        build_dashboard_session_artifact_reference(
            artifact_role_id=DASHBOARD_SESSION_STATE_ROLE_ID,
            source_kind=DASHBOARD_SESSION_PACKAGE_SOURCE_KIND,
            path=artifacts[SESSION_STATE_ARTIFACT_ID]["path"],
            contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            bundle_id=bundle_paths.bundle_id,
            artifact_id=SESSION_STATE_ARTIFACT_ID,
            format=artifacts[SESSION_STATE_ARTIFACT_ID]["format"],
            artifact_scope=artifacts[SESSION_STATE_ARTIFACT_ID]["artifact_scope"],
            status=artifacts[SESSION_STATE_ARTIFACT_ID]["status"],
        ),
        build_dashboard_session_artifact_reference(
            artifact_role_id=DASHBOARD_APP_SHELL_ROLE_ID,
            source_kind=DASHBOARD_SESSION_PACKAGE_SOURCE_KIND,
            path=artifacts[APP_SHELL_INDEX_ARTIFACT_ID]["path"],
            contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            bundle_id=bundle_paths.bundle_id,
            artifact_id=APP_SHELL_INDEX_ARTIFACT_ID,
            format=artifacts[APP_SHELL_INDEX_ARTIFACT_ID]["format"],
            artifact_scope=artifacts[APP_SHELL_INDEX_ARTIFACT_ID]["artifact_scope"],
            status=artifacts[APP_SHELL_INDEX_ARTIFACT_ID]["status"],
        ),
    ]

    return parse_dashboard_session_metadata(
        {
            "contract_version": DASHBOARD_SESSION_CONTRACT_VERSION,
            "design_note": DASHBOARD_SESSION_DESIGN_NOTE,
            "design_note_version": DASHBOARD_SESSION_DESIGN_NOTE_VERSION,
            "bundle_id": bundle_paths.bundle_id,
            "experiment_id": normalized_manifest_reference["experiment_id"],
            "session_spec_hash": session_spec_hash,
            "session_spec_hash_algorithm": DEFAULT_HASH_ALGORITHM,
            "ui_delivery_model": normalized_ui_delivery_model,
            "manifest_reference": normalized_manifest_reference,
            "global_interaction_state": normalized_global_state,
            "enabled_export_target_ids": normalized_enabled_export_target_ids,
            "default_export_target_id": normalized_default_export_target_id,
            "artifact_references": list(normalized_external_artifact_references)
            + list(local_artifact_references),
            "output_root_reference": {
                "processed_simulator_results_dir": str(
                    bundle_paths.processed_simulator_results_dir
                ),
            },
            "bundle_layout": {
                "bundle_directory": str(bundle_paths.bundle_directory),
                "app_directory": str(bundle_paths.app_directory),
            },
            "artifacts": artifacts,
        }
    )


def parse_dashboard_pane_definition(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("dashboard pane definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "pane_id",
        "display_name",
        "description",
        "sequence_index",
        "supports_time_cursor",
        "supports_neuron_selection",
        "supports_readout_selection",
        "supported_overlay_categories",
        "primary_artifact_role_ids",
        "default_overlay_id",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"dashboard pane definition is missing fields: {missing_fields!r}."
        )
    normalized["pane_id"] = _normalize_pane_id(normalized["pane_id"])
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="pane.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="pane.description",
    )
    normalized["sequence_index"] = _normalize_nonnegative_int(
        normalized["sequence_index"],
        field_name="pane.sequence_index",
    )
    normalized["supports_time_cursor"] = _normalize_boolean(
        normalized["supports_time_cursor"],
        field_name="pane.supports_time_cursor",
    )
    normalized["supports_neuron_selection"] = _normalize_boolean(
        normalized["supports_neuron_selection"],
        field_name="pane.supports_neuron_selection",
    )
    normalized["supports_readout_selection"] = _normalize_boolean(
        normalized["supports_readout_selection"],
        field_name="pane.supports_readout_selection",
    )
    normalized["supported_overlay_categories"] = _normalize_known_value_list(
        normalized["supported_overlay_categories"],
        field_name="pane.supported_overlay_categories",
        supported_values=SUPPORTED_OVERLAY_CATEGORIES,
        allow_empty=False,
    )
    normalized["primary_artifact_role_ids"] = _normalize_known_value_list(
        normalized["primary_artifact_role_ids"],
        field_name="pane.primary_artifact_role_ids",
        supported_values=SUPPORTED_ARTIFACT_ROLE_IDS,
        allow_empty=False,
    )
    normalized["default_overlay_id"] = _normalize_overlay_id(normalized["default_overlay_id"])
    return normalized


def parse_dashboard_overlay_definition(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("dashboard overlay definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "overlay_id",
        "display_name",
        "description",
        "overlay_category",
        "supported_pane_ids",
        "required_artifact_role_ids",
        "supported_comparison_modes",
        "fairness_note",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"dashboard overlay definition is missing fields: {missing_fields!r}."
        )
    normalized["overlay_id"] = _normalize_overlay_id(normalized["overlay_id"])
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="overlay.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="overlay.description",
    )
    normalized["overlay_category"] = _normalize_overlay_category(
        normalized["overlay_category"]
    )
    normalized["supported_pane_ids"] = _normalize_known_value_list(
        normalized["supported_pane_ids"],
        field_name="overlay.supported_pane_ids",
        supported_values=SUPPORTED_PANE_IDS,
        allow_empty=False,
    )
    normalized["required_artifact_role_ids"] = _normalize_known_value_list(
        normalized["required_artifact_role_ids"],
        field_name="overlay.required_artifact_role_ids",
        supported_values=SUPPORTED_ARTIFACT_ROLE_IDS,
        allow_empty=False,
    )
    normalized["supported_comparison_modes"] = _normalize_known_value_list(
        normalized["supported_comparison_modes"],
        field_name="overlay.supported_comparison_modes",
        supported_values=SUPPORTED_COMPARISON_MODES,
        allow_empty=False,
    )
    normalized["fairness_note"] = _normalize_nonempty_string(
        normalized["fairness_note"],
        field_name="overlay.fairness_note",
    )
    return normalized


def parse_dashboard_comparison_mode_definition(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("dashboard comparison-mode definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "comparison_mode_id",
        "display_name",
        "description",
        "required_arm_count",
        "requires_shared_timebase",
        "allowed_overlay_categories",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"dashboard comparison-mode definition is missing fields: {missing_fields!r}."
        )
    normalized["comparison_mode_id"] = _normalize_comparison_mode_id(
        normalized["comparison_mode_id"]
    )
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="comparison_mode.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="comparison_mode.description",
    )
    normalized["required_arm_count"] = _normalize_positive_int(
        normalized["required_arm_count"],
        field_name="comparison_mode.required_arm_count",
    )
    normalized["requires_shared_timebase"] = _normalize_boolean(
        normalized["requires_shared_timebase"],
        field_name="comparison_mode.requires_shared_timebase",
    )
    normalized["allowed_overlay_categories"] = _normalize_known_value_list(
        normalized["allowed_overlay_categories"],
        field_name="comparison_mode.allowed_overlay_categories",
        supported_values=SUPPORTED_OVERLAY_CATEGORIES,
        allow_empty=False,
    )
    return normalized


def parse_dashboard_export_target_definition(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("dashboard export-target definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "export_target_id",
        "display_name",
        "description",
        "target_kind",
        "supported_pane_ids",
        "requires_time_cursor",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"dashboard export-target definition is missing fields: {missing_fields!r}."
        )
    normalized["export_target_id"] = _normalize_export_target_id(
        normalized["export_target_id"]
    )
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="export_target.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="export_target.description",
    )
    normalized["target_kind"] = _normalize_export_target_kind(
        normalized["target_kind"]
    )
    normalized["supported_pane_ids"] = _normalize_known_value_list(
        normalized["supported_pane_ids"],
        field_name="export_target.supported_pane_ids",
        supported_values=SUPPORTED_PANE_IDS,
        allow_empty=False,
    )
    normalized["requires_time_cursor"] = _normalize_boolean(
        normalized["requires_time_cursor"],
        field_name="export_target.requires_time_cursor",
    )
    return normalized


def parse_dashboard_artifact_hook_definition(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("dashboard artifact-hook definitions must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "artifact_role_id",
        "display_name",
        "description",
        "source_kind",
        "required_contract_version",
        "artifact_id",
        "artifact_scope",
        "supported_pane_ids",
        "discovery_note",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"dashboard artifact-hook definition is missing fields: {missing_fields!r}."
        )
    normalized["artifact_role_id"] = _normalize_artifact_role_id(
        normalized["artifact_role_id"]
    )
    normalized["display_name"] = _normalize_nonempty_string(
        normalized["display_name"],
        field_name="artifact_hook.display_name",
    )
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name="artifact_hook.description",
    )
    normalized["source_kind"] = _normalize_source_kind(normalized["source_kind"])
    normalized["required_contract_version"] = _normalize_nonempty_string(
        normalized["required_contract_version"],
        field_name="artifact_hook.required_contract_version",
    )
    normalized["artifact_id"] = _normalize_identifier(
        normalized["artifact_id"],
        field_name="artifact_hook.artifact_id",
    )
    normalized["artifact_scope"] = _normalize_identifier(
        normalized["artifact_scope"],
        field_name="artifact_hook.artifact_scope",
    )
    normalized["supported_pane_ids"] = _normalize_known_value_list(
        normalized["supported_pane_ids"],
        field_name="artifact_hook.supported_pane_ids",
        supported_values=SUPPORTED_PANE_IDS,
        allow_empty=False,
    )
    normalized["discovery_note"] = _normalize_nonempty_string(
        normalized["discovery_note"],
        field_name="artifact_hook.discovery_note",
    )
    return normalized


def parse_dashboard_selected_arm_pair_reference(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("selected_arm_pair must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = ("baseline_arm_id", "wave_arm_id", "active_arm_id")
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"selected_arm_pair is missing fields: {missing_fields!r}.")
    normalized["baseline_arm_id"] = _normalize_identifier(
        normalized["baseline_arm_id"],
        field_name="selected_arm_pair.baseline_arm_id",
    )
    normalized["wave_arm_id"] = _normalize_identifier(
        normalized["wave_arm_id"],
        field_name="selected_arm_pair.wave_arm_id",
    )
    normalized["active_arm_id"] = _normalize_identifier(
        normalized["active_arm_id"],
        field_name="selected_arm_pair.active_arm_id",
    )
    if normalized["baseline_arm_id"] == normalized["wave_arm_id"]:
        raise ValueError("selected_arm_pair baseline_arm_id and wave_arm_id must differ.")
    if normalized["active_arm_id"] not in {
        normalized["baseline_arm_id"],
        normalized["wave_arm_id"],
    }:
        raise ValueError(
            "selected_arm_pair.active_arm_id must be either baseline_arm_id or wave_arm_id."
        )
    return normalized


def parse_dashboard_time_cursor(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("time_cursor must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = ("time_ms", "sample_index", "playback_state")
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"time_cursor is missing fields: {missing_fields!r}.")
    normalized["time_ms"] = _normalize_float(
        normalized["time_ms"],
        field_name="time_cursor.time_ms",
    )
    if not math.isfinite(normalized["time_ms"]):
        raise ValueError("time_cursor.time_ms must be finite.")
    normalized["sample_index"] = _normalize_nonnegative_int(
        normalized["sample_index"],
        field_name="time_cursor.sample_index",
    )
    normalized["playback_state"] = _normalize_playback_state(
        normalized["playback_state"]
    )
    return normalized


def parse_dashboard_global_interaction_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("dashboard global interaction state must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "selected_arm_pair",
        "selected_neuron_id",
        "selected_readout_id",
        "active_overlay_id",
        "comparison_mode",
        "time_cursor",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "dashboard global interaction state is missing fields: "
            f"{missing_fields!r}."
        )
    normalized["selected_arm_pair"] = parse_dashboard_selected_arm_pair_reference(
        normalized["selected_arm_pair"]
    )
    normalized["selected_neuron_id"] = _normalize_optional_identifier(
        normalized["selected_neuron_id"],
        field_name="global_interaction_state.selected_neuron_id",
    )
    normalized["selected_readout_id"] = _normalize_optional_identifier(
        normalized["selected_readout_id"],
        field_name="global_interaction_state.selected_readout_id",
    )
    normalized["active_overlay_id"] = _normalize_overlay_id(normalized["active_overlay_id"])
    normalized["comparison_mode"] = _normalize_comparison_mode_id(
        normalized["comparison_mode"]
    )
    normalized["time_cursor"] = parse_dashboard_time_cursor(normalized["time_cursor"])
    return normalized


def parse_dashboard_session_artifact_reference(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("dashboard session artifact references must be mappings.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "artifact_role_id",
        "source_kind",
        "path",
        "contract_version",
        "bundle_id",
        "artifact_id",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            f"dashboard session artifact reference is missing fields: {missing_fields!r}."
        )
    normalized["artifact_role_id"] = _normalize_artifact_role_id(
        normalized["artifact_role_id"]
    )
    normalized["source_kind"] = _normalize_source_kind(normalized["source_kind"])
    normalized["path"] = str(
        Path(
            _normalize_nonempty_string(
                normalized["path"],
                field_name="artifact_reference.path",
            )
        ).resolve()
    )
    normalized["contract_version"] = _normalize_nonempty_string(
        normalized["contract_version"],
        field_name="artifact_reference.contract_version",
    )
    normalized["bundle_id"] = _normalize_nonempty_string(
        normalized["bundle_id"],
        field_name="artifact_reference.bundle_id",
    )
    normalized["artifact_id"] = _normalize_identifier(
        normalized["artifact_id"],
        field_name="artifact_reference.artifact_id",
    )
    normalized["format"] = _normalize_optional_string(
        normalized.get("format"),
        field_name="artifact_reference.format",
    )
    normalized["artifact_scope"] = _normalize_optional_identifier(
        normalized.get("artifact_scope"),
        field_name="artifact_reference.artifact_scope",
    )
    normalized["status"] = _normalize_asset_status(
        normalized.get("status", ASSET_STATUS_READY),
        field_name="artifact_reference.status",
    )
    return normalized


def parse_dashboard_session_contract_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("dashboard session contract metadata must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "design_note",
        "design_note_version",
        "default_ui_delivery_model",
        "supported_ui_delivery_models",
        "required_upstream_contracts",
        "supported_pane_ids",
        "supported_overlay_categories",
        "supported_overlay_ids",
        "supported_comparison_modes",
        "supported_export_target_ids",
        "supported_export_target_kinds",
        "supported_playback_states",
        "supported_artifact_source_kinds",
        "supported_artifact_role_ids",
        "default_overlay_id",
        "default_comparison_mode",
        "default_export_target_id",
        "linked_selection_invariants",
        "fairness_boundary_invariants",
        "pane_catalog",
        "overlay_catalog",
        "comparison_mode_catalog",
        "export_target_catalog",
        "artifact_hook_catalog",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "dashboard session contract metadata is missing required fields: "
            f"{missing_fields!r}."
        )
    contract_version = _normalize_nonempty_string(
        normalized["contract_version"],
        field_name="contract_version",
    )
    if contract_version != DASHBOARD_SESSION_CONTRACT_VERSION:
        raise ValueError(
            "dashboard session contract_version must be "
            f"{DASHBOARD_SESSION_CONTRACT_VERSION!r}."
        )
    normalized["contract_version"] = contract_version
    design_note = _normalize_nonempty_string(
        normalized["design_note"],
        field_name="design_note",
    )
    if design_note != DASHBOARD_SESSION_DESIGN_NOTE:
        raise ValueError(f"design_note must be {DASHBOARD_SESSION_DESIGN_NOTE!r}.")
    normalized["design_note"] = design_note
    design_note_version = _normalize_nonempty_string(
        normalized["design_note_version"],
        field_name="design_note_version",
    )
    if design_note_version != DASHBOARD_SESSION_DESIGN_NOTE_VERSION:
        raise ValueError(
            "design_note_version must be "
            f"{DASHBOARD_SESSION_DESIGN_NOTE_VERSION!r}."
        )
    normalized["design_note_version"] = design_note_version
    normalized["default_ui_delivery_model"] = _normalize_ui_delivery_model(
        normalized["default_ui_delivery_model"]
    )
    normalized["supported_ui_delivery_models"] = _normalize_known_value_list(
        normalized["supported_ui_delivery_models"],
        field_name="supported_ui_delivery_models",
        supported_values=SUPPORTED_UI_DELIVERY_MODELS,
        allow_empty=False,
    )
    if normalized["default_ui_delivery_model"] not in normalized["supported_ui_delivery_models"]:
        raise ValueError(
            "default_ui_delivery_model must be present in supported_ui_delivery_models."
        )
    normalized["required_upstream_contracts"] = _normalize_known_string_list(
        normalized["required_upstream_contracts"],
        field_name="required_upstream_contracts",
        supported_values=REQUIRED_UPSTREAM_CONTRACTS,
        allow_empty=False,
    )
    normalized["supported_pane_ids"] = _normalize_known_value_list(
        normalized["supported_pane_ids"],
        field_name="supported_pane_ids",
        supported_values=SUPPORTED_PANE_IDS,
        allow_empty=False,
    )
    normalized["supported_overlay_categories"] = _normalize_known_value_list(
        normalized["supported_overlay_categories"],
        field_name="supported_overlay_categories",
        supported_values=SUPPORTED_OVERLAY_CATEGORIES,
        allow_empty=False,
    )
    normalized["supported_overlay_ids"] = _normalize_known_value_list(
        normalized["supported_overlay_ids"],
        field_name="supported_overlay_ids",
        supported_values=SUPPORTED_OVERLAY_IDS,
        allow_empty=False,
    )
    normalized["supported_comparison_modes"] = _normalize_known_value_list(
        normalized["supported_comparison_modes"],
        field_name="supported_comparison_modes",
        supported_values=SUPPORTED_COMPARISON_MODES,
        allow_empty=False,
    )
    normalized["supported_export_target_ids"] = _normalize_known_value_list(
        normalized["supported_export_target_ids"],
        field_name="supported_export_target_ids",
        supported_values=SUPPORTED_EXPORT_TARGET_IDS,
        allow_empty=False,
    )
    normalized["supported_export_target_kinds"] = _normalize_known_value_list(
        normalized["supported_export_target_kinds"],
        field_name="supported_export_target_kinds",
        supported_values=SUPPORTED_EXPORT_TARGET_KINDS,
        allow_empty=False,
    )
    normalized["supported_playback_states"] = _normalize_known_value_list(
        normalized["supported_playback_states"],
        field_name="supported_playback_states",
        supported_values=SUPPORTED_PLAYBACK_STATES,
        allow_empty=False,
    )
    normalized["supported_artifact_source_kinds"] = _normalize_known_value_list(
        normalized["supported_artifact_source_kinds"],
        field_name="supported_artifact_source_kinds",
        supported_values=SUPPORTED_ARTIFACT_SOURCE_KINDS,
        allow_empty=False,
    )
    normalized["supported_artifact_role_ids"] = _normalize_known_value_list(
        normalized["supported_artifact_role_ids"],
        field_name="supported_artifact_role_ids",
        supported_values=SUPPORTED_ARTIFACT_ROLE_IDS,
        allow_empty=False,
    )
    normalized["default_overlay_id"] = _normalize_overlay_id(normalized["default_overlay_id"])
    normalized["default_comparison_mode"] = _normalize_comparison_mode_id(
        normalized["default_comparison_mode"]
    )
    normalized["default_export_target_id"] = _normalize_export_target_id(
        normalized["default_export_target_id"]
    )
    normalized["linked_selection_invariants"] = _normalize_nonempty_string_list(
        normalized["linked_selection_invariants"],
        field_name="linked_selection_invariants",
    )
    normalized["fairness_boundary_invariants"] = _normalize_nonempty_string_list(
        normalized["fairness_boundary_invariants"],
        field_name="fairness_boundary_invariants",
    )
    normalized["pane_catalog"] = _normalize_pane_catalog(normalized["pane_catalog"])
    normalized["overlay_catalog"] = _normalize_overlay_catalog(normalized["overlay_catalog"])
    normalized["comparison_mode_catalog"] = _normalize_comparison_mode_catalog(
        normalized["comparison_mode_catalog"]
    )
    normalized["export_target_catalog"] = _normalize_export_target_catalog(
        normalized["export_target_catalog"]
    )
    normalized["artifact_hook_catalog"] = _normalize_artifact_hook_catalog(
        normalized["artifact_hook_catalog"]
    )

    pane_catalog_by_id = {item["pane_id"]: item for item in normalized["pane_catalog"]}
    overlay_catalog_by_id = {item["overlay_id"]: item for item in normalized["overlay_catalog"]}
    comparison_mode_catalog_by_id = {
        item["comparison_mode_id"]: item for item in normalized["comparison_mode_catalog"]
    }
    export_target_catalog_by_id = {
        item["export_target_id"]: item for item in normalized["export_target_catalog"]
    }
    artifact_hook_catalog_by_id = {
        item["artifact_role_id"]: item for item in normalized["artifact_hook_catalog"]
    }

    _ensure_catalog_ids_match(
        catalog_name="pane_catalog",
        actual_ids=set(pane_catalog_by_id),
        expected_ids=set(SUPPORTED_PANE_IDS),
    )
    _ensure_catalog_ids_match(
        catalog_name="overlay_catalog",
        actual_ids=set(overlay_catalog_by_id),
        expected_ids=set(SUPPORTED_OVERLAY_IDS),
    )
    _ensure_catalog_ids_match(
        catalog_name="comparison_mode_catalog",
        actual_ids=set(comparison_mode_catalog_by_id),
        expected_ids=set(SUPPORTED_COMPARISON_MODES),
    )
    _ensure_catalog_ids_match(
        catalog_name="export_target_catalog",
        actual_ids=set(export_target_catalog_by_id),
        expected_ids=set(SUPPORTED_EXPORT_TARGET_IDS),
    )
    _ensure_catalog_ids_match(
        catalog_name="artifact_hook_catalog",
        actual_ids=set(artifact_hook_catalog_by_id),
        expected_ids=set(SUPPORTED_ARTIFACT_ROLE_IDS),
    )

    sequence_indices = [item["sequence_index"] for item in normalized["pane_catalog"]]
    if len(sequence_indices) != len(set(sequence_indices)):
        raise ValueError("pane_catalog sequence_index values must be unique.")

    for pane in normalized["pane_catalog"]:
        if pane["default_overlay_id"] not in overlay_catalog_by_id:
            raise ValueError(
                f"pane_catalog entry {pane['pane_id']!r} references unknown default_overlay_id."
            )
        overlay_definition = overlay_catalog_by_id[pane["default_overlay_id"]]
        if overlay_definition["overlay_category"] not in pane["supported_overlay_categories"]:
            raise ValueError(
                f"pane_catalog entry {pane['pane_id']!r} default_overlay_id is not compatible with supported_overlay_categories."
            )
        missing_artifact_roles = sorted(
            set(pane["primary_artifact_role_ids"]) - set(artifact_hook_catalog_by_id)
        )
        if missing_artifact_roles:
            raise ValueError(
                f"pane_catalog entry {pane['pane_id']!r} references unknown artifact roles {missing_artifact_roles!r}."
            )

    for overlay in normalized["overlay_catalog"]:
        unknown_panes = sorted(set(overlay["supported_pane_ids"]) - set(pane_catalog_by_id))
        if unknown_panes:
            raise ValueError(
                f"overlay_catalog entry {overlay['overlay_id']!r} references unknown panes {unknown_panes!r}."
            )
        unknown_modes = sorted(
            set(overlay["supported_comparison_modes"]) - set(comparison_mode_catalog_by_id)
        )
        if unknown_modes:
            raise ValueError(
                f"overlay_catalog entry {overlay['overlay_id']!r} references unknown comparison modes {unknown_modes!r}."
            )
        unknown_roles = sorted(
            set(overlay["required_artifact_role_ids"]) - set(artifact_hook_catalog_by_id)
        )
        if unknown_roles:
            raise ValueError(
                f"overlay_catalog entry {overlay['overlay_id']!r} references unknown artifact roles {unknown_roles!r}."
            )
        for pane_id in overlay["supported_pane_ids"]:
            if overlay["overlay_category"] not in pane_catalog_by_id[pane_id]["supported_overlay_categories"]:
                raise ValueError(
                    f"overlay_catalog entry {overlay['overlay_id']!r} declares pane {pane_id!r} without matching overlay-category support."
                )

    for comparison_mode in normalized["comparison_mode_catalog"]:
        if comparison_mode["required_arm_count"] not in (1, 2):
            raise ValueError("comparison_mode.required_arm_count must be 1 or 2.")

    for export_target in normalized["export_target_catalog"]:
        unknown_panes = sorted(
            set(export_target["supported_pane_ids"]) - set(pane_catalog_by_id)
        )
        if unknown_panes:
            raise ValueError(
                f"export_target_catalog entry {export_target['export_target_id']!r} references unknown panes {unknown_panes!r}."
            )

    for hook in normalized["artifact_hook_catalog"]:
        unknown_panes = sorted(set(hook["supported_pane_ids"]) - set(pane_catalog_by_id))
        if unknown_panes:
            raise ValueError(
                f"artifact_hook_catalog entry {hook['artifact_role_id']!r} references unknown panes {unknown_panes!r}."
            )
    return normalized


def parse_dashboard_session_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("dashboard session metadata must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = (
        "contract_version",
        "design_note",
        "design_note_version",
        "bundle_id",
        "experiment_id",
        "session_spec_hash",
        "session_spec_hash_algorithm",
        "ui_delivery_model",
        "manifest_reference",
        "global_interaction_state",
        "enabled_export_target_ids",
        "default_export_target_id",
        "artifact_references",
        "output_root_reference",
        "bundle_layout",
        "artifacts",
    )
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(
            "dashboard session metadata is missing required fields: "
            f"{missing_fields!r}."
        )
    contract_metadata = build_dashboard_session_contract_metadata()
    hook_catalog_by_role = {
        item["artifact_role_id"]: item
        for item in contract_metadata["artifact_hook_catalog"]
    }

    contract_version = _normalize_nonempty_string(
        normalized["contract_version"],
        field_name="contract_version",
    )
    if contract_version != DASHBOARD_SESSION_CONTRACT_VERSION:
        raise ValueError(
            "dashboard session metadata contract_version must be "
            f"{DASHBOARD_SESSION_CONTRACT_VERSION!r}."
        )
    normalized["contract_version"] = contract_version
    design_note = _normalize_nonempty_string(
        normalized["design_note"],
        field_name="design_note",
    )
    if design_note != DASHBOARD_SESSION_DESIGN_NOTE:
        raise ValueError(f"design_note must be {DASHBOARD_SESSION_DESIGN_NOTE!r}.")
    normalized["design_note"] = design_note
    design_note_version = _normalize_nonempty_string(
        normalized["design_note_version"],
        field_name="design_note_version",
    )
    if design_note_version != DASHBOARD_SESSION_DESIGN_NOTE_VERSION:
        raise ValueError(
            "design_note_version must be "
            f"{DASHBOARD_SESSION_DESIGN_NOTE_VERSION!r}."
        )
    normalized["design_note_version"] = design_note_version
    normalized["experiment_id"] = _normalize_identifier(
        normalized["experiment_id"],
        field_name="experiment_id",
    )
    normalized["session_spec_hash"] = _normalize_parameter_hash(
        normalized["session_spec_hash"]
    )
    normalized["session_spec_hash_algorithm"] = _normalize_nonempty_string(
        normalized["session_spec_hash_algorithm"],
        field_name="session_spec_hash_algorithm",
    )
    if normalized["session_spec_hash_algorithm"] != DEFAULT_HASH_ALGORITHM:
        raise ValueError(
            "session_spec_hash_algorithm must be "
            f"{DEFAULT_HASH_ALGORITHM!r}."
        )
    normalized["ui_delivery_model"] = _normalize_ui_delivery_model(
        normalized["ui_delivery_model"]
    )
    normalized["manifest_reference"] = parse_simulator_manifest_reference(
        normalized["manifest_reference"]
    )
    if normalized["experiment_id"] != normalized["manifest_reference"]["experiment_id"]:
        raise ValueError("experiment_id must match manifest_reference.experiment_id.")
    normalized["global_interaction_state"] = _normalize_global_interaction_state_against_contract(
        normalized["global_interaction_state"],
        contract_metadata=contract_metadata,
    )
    normalized["enabled_export_target_ids"] = _normalize_known_value_list(
        normalized["enabled_export_target_ids"],
        field_name="enabled_export_target_ids",
        supported_values=SUPPORTED_EXPORT_TARGET_IDS,
        allow_empty=False,
    )
    normalized["default_export_target_id"] = _normalize_export_target_id(
        normalized["default_export_target_id"]
    )
    if normalized["default_export_target_id"] not in normalized["enabled_export_target_ids"]:
        raise ValueError(
            "default_export_target_id must be one of enabled_export_target_ids."
        )
    normalized["artifact_references"] = _normalize_artifact_reference_catalog(
        normalized["artifact_references"],
        field_name="artifact_references",
    )
    _validate_artifact_references_against_contract(
        normalized["artifact_references"],
        contract_metadata=contract_metadata,
        field_name="artifact_references",
    )

    bundle_id = _normalize_nonempty_string(
        normalized["bundle_id"],
        field_name="bundle_id",
    )
    expected_bundle_id = (
        f"{DASHBOARD_SESSION_CONTRACT_VERSION}:"
        f"{normalized['experiment_id']}:{normalized['session_spec_hash']}"
    )
    if bundle_id != expected_bundle_id:
        raise ValueError("bundle_id must match the canonical dashboard-session identity.")
    normalized["bundle_id"] = bundle_id

    external_artifact_references = [
        copy.deepcopy(item)
        for item in normalized["artifact_references"]
        if item["source_kind"] != DASHBOARD_SESSION_PACKAGE_SOURCE_KIND
    ]
    expected_hash = build_dashboard_session_spec_hash(
        manifest_reference=normalized["manifest_reference"],
        ui_delivery_model=normalized["ui_delivery_model"],
        global_interaction_state=normalized["global_interaction_state"],
        enabled_export_target_ids=normalized["enabled_export_target_ids"],
        artifact_references=external_artifact_references,
    )
    if normalized["session_spec_hash"] != expected_hash:
        raise ValueError("session_spec_hash does not match the normalized dashboard-session identity payload.")

    normalized["output_root_reference"] = _normalize_output_root_reference(
        normalized["output_root_reference"]
    )
    bundle_paths = build_dashboard_session_bundle_paths(
        experiment_id=normalized["experiment_id"],
        session_spec_hash=normalized["session_spec_hash"],
        processed_simulator_results_dir=normalized["output_root_reference"][
            "processed_simulator_results_dir"
        ],
    )
    normalized["bundle_layout"] = _normalize_bundle_layout(
        normalized["bundle_layout"],
        expected_bundle_directory=bundle_paths.bundle_directory,
        expected_app_directory=bundle_paths.app_directory,
    )
    normalized["artifacts"] = _normalize_dashboard_session_artifacts(
        normalized["artifacts"],
        bundle_paths=bundle_paths,
    )

    referenced_role_ids = {item["artifact_role_id"] for item in normalized["artifact_references"]}
    missing_required_external_roles = sorted(
        set(REQUIRED_EXTERNAL_ARTIFACT_ROLE_IDS) - referenced_role_ids
    )
    if missing_required_external_roles:
        raise ValueError(
            "dashboard session metadata is missing required external artifact roles "
            f"{missing_required_external_roles!r}."
        )
    missing_required_local_roles = sorted(set(REQUIRED_LOCAL_ARTIFACT_ROLE_IDS) - referenced_role_ids)
    if missing_required_local_roles:
        raise ValueError(
            "dashboard session metadata is missing required local artifact roles "
            f"{missing_required_local_roles!r}."
        )

    local_reference_by_role = {
        item["artifact_role_id"]: item
        for item in normalized["artifact_references"]
        if item["source_kind"] == DASHBOARD_SESSION_PACKAGE_SOURCE_KIND
    }
    expected_local_bindings = {
        DASHBOARD_SESSION_METADATA_ROLE_ID: METADATA_JSON_KEY,
        DASHBOARD_SESSION_PAYLOAD_ROLE_ID: SESSION_PAYLOAD_ARTIFACT_ID,
        DASHBOARD_SESSION_STATE_ROLE_ID: SESSION_STATE_ARTIFACT_ID,
        DASHBOARD_APP_SHELL_ROLE_ID: APP_SHELL_INDEX_ARTIFACT_ID,
    }
    for role_id, artifact_id in expected_local_bindings.items():
        local_reference = local_reference_by_role.get(role_id)
        if local_reference is None:
            raise ValueError(
                f"dashboard session metadata is missing local artifact reference {role_id!r}."
            )
        artifact_record = normalized["artifacts"][artifact_id]
        if local_reference["path"] != artifact_record["path"]:
            raise ValueError(
                f"local artifact reference {role_id!r} path must match artifacts[{artifact_id!r}]."
            )
        if local_reference["artifact_id"] != artifact_id:
            raise ValueError(
                f"local artifact reference {role_id!r} artifact_id must be {artifact_id!r}."
            )
        if local_reference["bundle_id"] != normalized["bundle_id"]:
            raise ValueError(
                f"local artifact reference {role_id!r} bundle_id must match dashboard session bundle_id."
            )
        if local_reference["contract_version"] != DASHBOARD_SESSION_CONTRACT_VERSION:
            raise ValueError(
                f"local artifact reference {role_id!r} must use contract_version {DASHBOARD_SESSION_CONTRACT_VERSION!r}."
            )

    selected_arm_pair = normalized["global_interaction_state"]["selected_arm_pair"]
    baseline_role = hook_catalog_by_role[BASELINE_BUNDLE_METADATA_ROLE_ID]
    wave_role = hook_catalog_by_role[WAVE_BUNDLE_METADATA_ROLE_ID]
    for role_id, expected_scope in (
        (BASELINE_BUNDLE_METADATA_ROLE_ID, baseline_role["artifact_scope"]),
        (WAVE_BUNDLE_METADATA_ROLE_ID, wave_role["artifact_scope"]),
    ):
        matching = [
            item for item in normalized["artifact_references"] if item["artifact_role_id"] == role_id
        ]
        if len(matching) != 1:
            raise ValueError(
                f"dashboard session metadata must include exactly one artifact reference for {role_id!r}."
            )
        if matching[0]["artifact_scope"] not in {expected_scope, None}:
            raise ValueError(
                f"artifact reference {role_id!r} must keep artifact_scope {expected_scope!r} when declared."
            )
    if selected_arm_pair["baseline_arm_id"] == selected_arm_pair["wave_arm_id"]:
        raise ValueError("global_interaction_state.selected_arm_pair must preserve distinct baseline and wave arms.")

    return normalized


def write_dashboard_session_contract_metadata(
    contract_metadata: Mapping[str, Any],
    metadata_path: str | Path,
) -> Path:
    normalized = parse_dashboard_session_contract_metadata(contract_metadata)
    return write_json(normalized, metadata_path)


def load_dashboard_session_contract_metadata(metadata_path: str | Path) -> dict[str, Any]:
    path = Path(metadata_path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_dashboard_session_contract_metadata(payload)


def write_dashboard_session_metadata(
    bundle_metadata: Mapping[str, Any],
    metadata_path: str | Path | None = None,
) -> Path:
    normalized = parse_dashboard_session_metadata(bundle_metadata)
    output_path = (
        Path(str(normalized["artifacts"][METADATA_JSON_KEY]["path"])).resolve()
        if metadata_path is None
        else Path(metadata_path)
    )
    return write_json(normalized, output_path)


def load_dashboard_session_metadata(metadata_path: str | Path) -> dict[str, Any]:
    path = Path(metadata_path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_dashboard_session_metadata(payload)


def discover_dashboard_panes(
    record: Mapping[str, Any],
    *,
    overlay_category: str | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_dashboard_session_contract_metadata(
        _extract_dashboard_contract_mapping(record)
    )
    normalized_overlay_category = (
        None if overlay_category is None else _normalize_overlay_category(overlay_category)
    )
    discovered: list[dict[str, Any]] = []
    for item in metadata["pane_catalog"]:
        if (
            normalized_overlay_category is not None
            and normalized_overlay_category not in item["supported_overlay_categories"]
        ):
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def discover_dashboard_overlays(
    record: Mapping[str, Any],
    *,
    pane_id: str | None = None,
    overlay_category: str | None = None,
    comparison_mode: str | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_dashboard_session_contract_metadata(
        _extract_dashboard_contract_mapping(record)
    )
    normalized_pane_id = None if pane_id is None else _normalize_pane_id(pane_id)
    normalized_overlay_category = (
        None if overlay_category is None else _normalize_overlay_category(overlay_category)
    )
    normalized_comparison_mode = (
        None if comparison_mode is None else _normalize_comparison_mode_id(comparison_mode)
    )
    discovered: list[dict[str, Any]] = []
    for item in metadata["overlay_catalog"]:
        if normalized_pane_id is not None and normalized_pane_id not in item["supported_pane_ids"]:
            continue
        if (
            normalized_overlay_category is not None
            and item["overlay_category"] != normalized_overlay_category
        ):
            continue
        if (
            normalized_comparison_mode is not None
            and normalized_comparison_mode not in item["supported_comparison_modes"]
        ):
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def discover_dashboard_export_targets(
    record: Mapping[str, Any],
    *,
    pane_id: str | None = None,
    target_kind: str | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_dashboard_session_contract_metadata(
        _extract_dashboard_contract_mapping(record)
    )
    normalized_pane_id = None if pane_id is None else _normalize_pane_id(pane_id)
    normalized_target_kind = (
        None if target_kind is None else _normalize_export_target_kind(target_kind)
    )
    discovered: list[dict[str, Any]] = []
    for item in metadata["export_target_catalog"]:
        if normalized_pane_id is not None and normalized_pane_id not in item["supported_pane_ids"]:
            continue
        if normalized_target_kind is not None and item["target_kind"] != normalized_target_kind:
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def discover_dashboard_artifact_hooks(
    record: Mapping[str, Any],
    *,
    source_kind: str | None = None,
    pane_id: str | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_dashboard_session_contract_metadata(
        _extract_dashboard_contract_mapping(record)
    )
    normalized_source_kind = None if source_kind is None else _normalize_source_kind(source_kind)
    normalized_pane_id = None if pane_id is None else _normalize_pane_id(pane_id)
    discovered: list[dict[str, Any]] = []
    for item in metadata["artifact_hook_catalog"]:
        if normalized_source_kind is not None and item["source_kind"] != normalized_source_kind:
            continue
        if normalized_pane_id is not None and normalized_pane_id not in item["supported_pane_ids"]:
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def get_dashboard_pane_definition(
    pane_id: str,
    *,
    record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_pane_id = _normalize_pane_id(pane_id)
    metadata = (
        build_dashboard_session_contract_metadata()
        if record is None
        else parse_dashboard_session_contract_metadata(_extract_dashboard_contract_mapping(record))
    )
    for item in metadata["pane_catalog"]:
        if item["pane_id"] == normalized_pane_id:
            return copy.deepcopy(item)
    raise ValueError(f"Unknown dashboard pane_id {normalized_pane_id!r}.")


def get_dashboard_overlay_definition(
    overlay_id: str,
    *,
    record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_overlay_id = _normalize_overlay_id(overlay_id)
    metadata = (
        build_dashboard_session_contract_metadata()
        if record is None
        else parse_dashboard_session_contract_metadata(_extract_dashboard_contract_mapping(record))
    )
    for item in metadata["overlay_catalog"]:
        if item["overlay_id"] == normalized_overlay_id:
            return copy.deepcopy(item)
    raise ValueError(f"Unknown dashboard overlay_id {normalized_overlay_id!r}.")


def discover_dashboard_session_bundle_paths(record: Mapping[str, Any]) -> dict[str, Path]:
    metadata = parse_dashboard_session_metadata(_extract_dashboard_session_mapping(record))
    return {
        artifact_id: Path(str(artifact["path"])).resolve()
        for artifact_id, artifact in metadata["artifacts"].items()
    }


def discover_dashboard_session_artifact_references(
    record: Mapping[str, Any],
    *,
    source_kind: str | None = None,
    artifact_role_id: str | None = None,
) -> list[dict[str, Any]]:
    metadata = parse_dashboard_session_metadata(_extract_dashboard_session_mapping(record))
    normalized_source_kind = None if source_kind is None else _normalize_source_kind(source_kind)
    normalized_artifact_role_id = (
        None if artifact_role_id is None else _normalize_artifact_role_id(artifact_role_id)
    )
    discovered: list[dict[str, Any]] = []
    for item in metadata["artifact_references"]:
        if normalized_source_kind is not None and item["source_kind"] != normalized_source_kind:
            continue
        if normalized_artifact_role_id is not None and item["artifact_role_id"] != normalized_artifact_role_id:
            continue
        discovered.append(copy.deepcopy(item))
    return discovered


def _default_pane_catalog() -> list[dict[str, Any]]:
    return [
        build_dashboard_pane_definition(
            pane_id=SCENE_PANE_ID,
            display_name="Scene",
            description="Stimulus or retinal context synchronized to the dashboard time cursor.",
            sequence_index=0,
            supports_time_cursor=True,
            supports_neuron_selection=False,
            supports_readout_selection=False,
            supported_overlay_categories=[
                CONTEXT_OVERLAY_CATEGORY,
                SHARED_COMPARISON_OVERLAY_CATEGORY,
            ],
            primary_artifact_role_ids=[
                BASELINE_BUNDLE_METADATA_ROLE_ID,
                WAVE_BUNDLE_METADATA_ROLE_ID,
            ],
            default_overlay_id=STIMULUS_CONTEXT_FRAME_OVERLAY_ID,
        ),
        build_dashboard_pane_definition(
            pane_id=CIRCUIT_PANE_ID,
            display_name="Circuit",
            description="Selected-circuit roster, connectivity context, optional whole-brain review bridge, and linked neuron inspection.",
            sequence_index=1,
            supports_time_cursor=True,
            supports_neuron_selection=True,
            supports_readout_selection=False,
            supported_overlay_categories=[
                CONTEXT_OVERLAY_CATEGORY,
                SHARED_COMPARISON_OVERLAY_CATEGORY,
                VALIDATION_EVIDENCE_OVERLAY_CATEGORY,
            ],
            primary_artifact_role_ids=[
                BASELINE_BUNDLE_METADATA_ROLE_ID,
                WAVE_BUNDLE_METADATA_ROLE_ID,
                VALIDATION_SUMMARY_ROLE_ID,
            ],
            default_overlay_id=SELECTED_SUBSET_HIGHLIGHT_OVERLAY_ID,
        ),
        build_dashboard_pane_definition(
            pane_id=MORPHOLOGY_PANE_ID,
            display_name="Morphology",
            description="Neuron geometry with synchronized activity overlays and mixed-fidelity inspection.",
            sequence_index=2,
            supports_time_cursor=True,
            supports_neuron_selection=True,
            supports_readout_selection=True,
            supported_overlay_categories=[
                CONTEXT_OVERLAY_CATEGORY,
                SHARED_COMPARISON_OVERLAY_CATEGORY,
                WAVE_ONLY_DIAGNOSTIC_OVERLAY_CATEGORY,
                VALIDATION_EVIDENCE_OVERLAY_CATEGORY,
            ],
            primary_artifact_role_ids=[
                BASELINE_BUNDLE_METADATA_ROLE_ID,
                WAVE_BUNDLE_METADATA_ROLE_ID,
                ANALYSIS_UI_PAYLOAD_ROLE_ID,
            ],
            default_overlay_id=SHARED_READOUT_ACTIVITY_OVERLAY_ID,
        ),
        build_dashboard_pane_definition(
            pane_id=TIME_SERIES_PANE_ID,
            display_name="Time Series",
            description="Shared readout traces, replay cursor, and paired comparison charts.",
            sequence_index=3,
            supports_time_cursor=True,
            supports_neuron_selection=True,
            supports_readout_selection=True,
            supported_overlay_categories=[
                SHARED_COMPARISON_OVERLAY_CATEGORY,
                WAVE_ONLY_DIAGNOSTIC_OVERLAY_CATEGORY,
            ],
            primary_artifact_role_ids=[
                BASELINE_BUNDLE_METADATA_ROLE_ID,
                WAVE_BUNDLE_METADATA_ROLE_ID,
                ANALYSIS_UI_PAYLOAD_ROLE_ID,
            ],
            default_overlay_id=SHARED_READOUT_ACTIVITY_OVERLAY_ID,
        ),
        build_dashboard_pane_definition(
            pane_id=ANALYSIS_PANE_ID,
            display_name="Analysis",
            description="Experiment analysis summaries, wave diagnostics, and reviewer-oriented validation evidence.",
            sequence_index=4,
            supports_time_cursor=True,
            supports_neuron_selection=True,
            supports_readout_selection=True,
            supported_overlay_categories=[
                SHARED_COMPARISON_OVERLAY_CATEGORY,
                WAVE_ONLY_DIAGNOSTIC_OVERLAY_CATEGORY,
                VALIDATION_EVIDENCE_OVERLAY_CATEGORY,
            ],
            primary_artifact_role_ids=[
                ANALYSIS_UI_PAYLOAD_ROLE_ID,
                VALIDATION_SUMMARY_ROLE_ID,
                VALIDATION_REVIEW_HANDOFF_ROLE_ID,
            ],
            default_overlay_id=PAIRED_READOUT_DELTA_OVERLAY_ID,
        ),
    ]


def _default_overlay_catalog() -> list[dict[str, Any]]:
    return [
        build_dashboard_overlay_definition(
            overlay_id=STIMULUS_CONTEXT_FRAME_OVERLAY_ID,
            display_name="Stimulus Context Frame",
            description="Context frame synchronized to the current time cursor for scene-oriented review.",
            overlay_category=CONTEXT_OVERLAY_CATEGORY,
            supported_pane_ids=[SCENE_PANE_ID],
            required_artifact_role_ids=[
                BASELINE_BUNDLE_METADATA_ROLE_ID,
                WAVE_BUNDLE_METADATA_ROLE_ID,
            ],
            supported_comparison_modes=list(SUPPORTED_COMPARISON_MODES),
            fairness_note="Context-only overlay. It informs interpretation but does not define the fair comparison surface.",
        ),
        build_dashboard_overlay_definition(
            overlay_id=SELECTED_SUBSET_HIGHLIGHT_OVERLAY_ID,
            display_name="Selected Subset Highlight",
            description="Highlights the active circuit subset and current neuron selection across structure-facing panes.",
            overlay_category=CONTEXT_OVERLAY_CATEGORY,
            supported_pane_ids=[CIRCUIT_PANE_ID, MORPHOLOGY_PANE_ID],
            required_artifact_role_ids=[
                BASELINE_BUNDLE_METADATA_ROLE_ID,
                WAVE_BUNDLE_METADATA_ROLE_ID,
            ],
            supported_comparison_modes=list(SUPPORTED_COMPARISON_MODES),
            fairness_note="Context-only overlay. It surfaces selection state without introducing new comparison semantics.",
        ),
        build_dashboard_overlay_definition(
            overlay_id=SHARED_READOUT_ACTIVITY_OVERLAY_ID,
            display_name="Shared Readout Activity",
            description="Uses the shared simulator readout surface and matched analysis payload for fair arm comparison.",
            overlay_category=SHARED_COMPARISON_OVERLAY_CATEGORY,
            supported_pane_ids=[MORPHOLOGY_PANE_ID, TIME_SERIES_PANE_ID, ANALYSIS_PANE_ID],
            required_artifact_role_ids=[
                BASELINE_BUNDLE_METADATA_ROLE_ID,
                WAVE_BUNDLE_METADATA_ROLE_ID,
                ANALYSIS_UI_PAYLOAD_ROLE_ID,
            ],
            supported_comparison_modes=list(SUPPORTED_COMPARISON_MODES),
            fairness_note="Fairness-critical shared-comparison overlay. It must stay anchored to simulator_result_bundle.v1 shared readout semantics.",
        ),
        build_dashboard_overlay_definition(
            overlay_id=PAIRED_READOUT_DELTA_OVERLAY_ID,
            display_name="Paired Readout Delta",
            description="Shows paired baseline-versus-wave deltas derived on the shared timebase and readout catalog.",
            overlay_category=SHARED_COMPARISON_OVERLAY_CATEGORY,
            supported_pane_ids=[TIME_SERIES_PANE_ID, ANALYSIS_PANE_ID],
            required_artifact_role_ids=[
                BASELINE_BUNDLE_METADATA_ROLE_ID,
                WAVE_BUNDLE_METADATA_ROLE_ID,
                ANALYSIS_UI_PAYLOAD_ROLE_ID,
            ],
            supported_comparison_modes=[
                PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
                PAIRED_DELTA_COMPARISON_MODE,
            ],
            fairness_note="Fairness-critical paired comparison overlay. It may be shown only when the paired arms share the simulator timebase.",
        ),
        build_dashboard_overlay_definition(
            overlay_id=WAVE_PATCH_ACTIVITY_OVERLAY_ID,
            display_name="Wave Patch Activity",
            description="Wave-only diagnostic overlay for morphology-resolved activity or summary cards.",
            overlay_category=WAVE_ONLY_DIAGNOSTIC_OVERLAY_CATEGORY,
            supported_pane_ids=[MORPHOLOGY_PANE_ID, ANALYSIS_PANE_ID],
            required_artifact_role_ids=[
                WAVE_BUNDLE_METADATA_ROLE_ID,
                ANALYSIS_UI_PAYLOAD_ROLE_ID,
            ],
            supported_comparison_modes=[
                SINGLE_ARM_COMPARISON_MODE,
                PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
            ],
            fairness_note="Wave-only diagnostic overlay. It may inform interpretation but must remain labeled as non-fairness-critical.",
        ),
        build_dashboard_overlay_definition(
            overlay_id=PHASE_MAP_REFERENCE_OVERLAY_ID,
            display_name="Phase Map Reference",
            description="References packaged phase-map or similar wave-only spatial diagnostics from experiment analysis outputs.",
            overlay_category=WAVE_ONLY_DIAGNOSTIC_OVERLAY_CATEGORY,
            supported_pane_ids=[ANALYSIS_PANE_ID],
            required_artifact_role_ids=[ANALYSIS_UI_PAYLOAD_ROLE_ID],
            supported_comparison_modes=[
                SINGLE_ARM_COMPARISON_MODE,
                PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
            ],
            fairness_note="Wave-only diagnostic overlay. It must not be collapsed into the shared comparison story.",
        ),
        build_dashboard_overlay_definition(
            overlay_id=VALIDATION_STATUS_BADGES_OVERLAY_ID,
            display_name="Validation Status Badges",
            description="Surface-level validation evidence keyed by the packaged machine summary.",
            overlay_category=VALIDATION_EVIDENCE_OVERLAY_CATEGORY,
            supported_pane_ids=[CIRCUIT_PANE_ID, ANALYSIS_PANE_ID],
            required_artifact_role_ids=[VALIDATION_SUMMARY_ROLE_ID],
            supported_comparison_modes=list(SUPPORTED_COMPARISON_MODES),
            fairness_note="Reviewer-oriented validation evidence. It must stay visually distinct from shared-comparison metrics and wave diagnostics.",
        ),
        build_dashboard_overlay_definition(
            overlay_id=REVIEWER_FINDINGS_OVERLAY_ID,
            display_name="Reviewer Findings",
            description="Shows Grant-facing review status and open validation findings without reclassifying them as metrics.",
            overlay_category=VALIDATION_EVIDENCE_OVERLAY_CATEGORY,
            supported_pane_ids=[ANALYSIS_PANE_ID],
            required_artifact_role_ids=[VALIDATION_REVIEW_HANDOFF_ROLE_ID],
            supported_comparison_modes=list(SUPPORTED_COMPARISON_MODES),
            fairness_note="Reviewer-oriented validation evidence. It represents plausibility review state rather than the fair comparison surface.",
        ),
    ]


def _default_comparison_mode_catalog() -> list[dict[str, Any]]:
    return [
        build_dashboard_comparison_mode_definition(
            comparison_mode_id=SINGLE_ARM_COMPARISON_MODE,
            display_name="Single Arm",
            description="Inspect one active arm at a time while preserving the paired arm reference for quick switching.",
            required_arm_count=1,
            requires_shared_timebase=False,
            allowed_overlay_categories=list(SUPPORTED_OVERLAY_CATEGORIES),
        ),
        build_dashboard_comparison_mode_definition(
            comparison_mode_id=PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
            display_name="Baseline Vs Wave",
            description="Use a baseline and wave arm together on the shared timebase for the primary Milestone 14 comparison view.",
            required_arm_count=2,
            requires_shared_timebase=True,
            allowed_overlay_categories=list(SUPPORTED_OVERLAY_CATEGORIES),
        ),
        build_dashboard_comparison_mode_definition(
            comparison_mode_id=PAIRED_DELTA_COMPARISON_MODE,
            display_name="Paired Delta",
            description="Show derived paired deltas for shared observables while leaving wave-only diagnostics out of the active overlay.",
            required_arm_count=2,
            requires_shared_timebase=True,
            allowed_overlay_categories=[
                CONTEXT_OVERLAY_CATEGORY,
                SHARED_COMPARISON_OVERLAY_CATEGORY,
                VALIDATION_EVIDENCE_OVERLAY_CATEGORY,
            ],
        ),
    ]


def _default_export_target_catalog() -> list[dict[str, Any]]:
    return [
        build_dashboard_export_target_definition(
            export_target_id=SESSION_STATE_EXPORT_TARGET_ID,
            display_name="Session State JSON",
            description="Serialized dashboard interaction state for deterministic reload and review.",
            target_kind=SESSION_STATE_EXPORT_KIND,
            supported_pane_ids=list(SUPPORTED_PANE_IDS),
            requires_time_cursor=True,
        ),
        build_dashboard_export_target_definition(
            export_target_id=PANE_SNAPSHOT_EXPORT_TARGET_ID,
            display_name="Pane Snapshot PNG",
            description="Still-image export of the currently active dashboard pane or composition.",
            target_kind=STILL_IMAGE_EXPORT_KIND,
            supported_pane_ids=list(SUPPORTED_PANE_IDS),
            requires_time_cursor=False,
        ),
        build_dashboard_export_target_definition(
            export_target_id=METRICS_EXPORT_TARGET_ID,
            display_name="Metrics JSON",
            description="Quantitative export for comparison-ready traces, cards, or other pane-local metrics.",
            target_kind=METRICS_EXPORT_KIND,
            supported_pane_ids=[TIME_SERIES_PANE_ID, ANALYSIS_PANE_ID],
            requires_time_cursor=False,
        ),
        build_dashboard_export_target_definition(
            export_target_id=REPLAY_FRAME_SEQUENCE_EXPORT_TARGET_ID,
            display_name="Replay Frame Sequence",
            description="Deterministic frame-sequence export for later encoding into replay media.",
            target_kind=REPLAY_EXPORT_KIND,
            supported_pane_ids=[SCENE_PANE_ID, MORPHOLOGY_PANE_ID, TIME_SERIES_PANE_ID],
            requires_time_cursor=True,
        ),
    ]


def _default_artifact_hook_catalog() -> list[dict[str, Any]]:
    return [
        build_dashboard_artifact_hook_definition(
            artifact_role_id=BASELINE_BUNDLE_METADATA_ROLE_ID,
            display_name="Baseline Bundle Metadata",
            description="Canonical simulator result metadata for the paired baseline arm.",
            source_kind=SIMULATOR_RESULT_SOURCE_KIND,
            required_contract_version=SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
            artifact_id=METADATA_JSON_KEY,
            artifact_scope=CONTRACT_METADATA_SCOPE,
            supported_pane_ids=list(SUPPORTED_PANE_IDS),
            discovery_note="Resolve from simulator_result_bundle.json so selected assets, readout catalog, and timebase remain the source of truth.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=BASELINE_UI_PAYLOAD_ROLE_ID,
            display_name="Baseline UI Payload",
            description="Optional simulator-side UI comparison payload for the paired baseline arm.",
            source_kind=SIMULATOR_RESULT_SOURCE_KIND,
            required_contract_version=SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
            artifact_id=SIMULATOR_UI_COMPARISON_PAYLOAD_ARTIFACT_ID,
            artifact_scope=SHARED_COMPARISON_SCOPE,
            supported_pane_ids=[
                SCENE_PANE_ID,
                CIRCUIT_PANE_ID,
                TIME_SERIES_PANE_ID,
                ANALYSIS_PANE_ID,
            ],
            discovery_note="Resolve through the simulator bundle extension inventory instead of guessing ui_comparison_payload.json.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=WAVE_BUNDLE_METADATA_ROLE_ID,
            display_name="Wave Bundle Metadata",
            description="Canonical simulator result metadata for the paired wave arm.",
            source_kind=SIMULATOR_RESULT_SOURCE_KIND,
            required_contract_version=SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
            artifact_id=METADATA_JSON_KEY,
            artifact_scope=CONTRACT_METADATA_SCOPE,
            supported_pane_ids=list(SUPPORTED_PANE_IDS),
            discovery_note="Resolve from simulator_result_bundle.json so wave-arm selected assets and shared timebase stay contract-backed.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=WAVE_UI_PAYLOAD_ROLE_ID,
            display_name="Wave UI Payload",
            description="Optional simulator-side UI comparison payload for the paired wave arm.",
            source_kind=SIMULATOR_RESULT_SOURCE_KIND,
            required_contract_version=SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
            artifact_id=SIMULATOR_UI_COMPARISON_PAYLOAD_ARTIFACT_ID,
            artifact_scope=SHARED_COMPARISON_SCOPE,
            supported_pane_ids=[
                SCENE_PANE_ID,
                CIRCUIT_PANE_ID,
                TIME_SERIES_PANE_ID,
                ANALYSIS_PANE_ID,
            ],
            discovery_note="Resolve through the simulator bundle extension inventory instead of bypassing metadata-backed discovery.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=ANALYSIS_BUNDLE_METADATA_ROLE_ID,
            display_name="Analysis Bundle Metadata",
            description="Experiment-level Milestone 12 packaged analysis metadata.",
            source_kind=EXPERIMENT_ANALYSIS_SOURCE_KIND,
            required_contract_version=EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION,
            artifact_id=METADATA_JSON_KEY,
            artifact_scope=CONTRACT_METADATA_SCOPE,
            supported_pane_ids=[MORPHOLOGY_PANE_ID, TIME_SERIES_PANE_ID, ANALYSIS_PANE_ID],
            discovery_note="Resolve from experiment_analysis_bundle.json so UI payloads and offline reports stay tied to one analysis package.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=ANALYSIS_UI_PAYLOAD_ROLE_ID,
            display_name="Analysis UI Payload",
            description="Packaged experiment-level UI handoff for shared comparison cards and wave diagnostics.",
            source_kind=EXPERIMENT_ANALYSIS_SOURCE_KIND,
            required_contract_version=EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION,
            artifact_id=EXPERIMENT_ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
            artifact_scope="ui_handoff",
            supported_pane_ids=[MORPHOLOGY_PANE_ID, TIME_SERIES_PANE_ID, ANALYSIS_PANE_ID],
            discovery_note="Resolve from the analysis bundle artifact inventory instead of hardcoded analysis_ui_payload.json paths.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=ANALYSIS_OFFLINE_REPORT_ROLE_ID,
            display_name="Analysis Offline Report",
            description="Self-contained Milestone 12 static analysis report retained for offline compatibility.",
            source_kind=EXPERIMENT_ANALYSIS_SOURCE_KIND,
            required_contract_version=EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION,
            artifact_id=EXPERIMENT_ANALYSIS_OFFLINE_REPORT_ARTIFACT_ID,
            artifact_scope="offline_review",
            supported_pane_ids=[ANALYSIS_PANE_ID],
            discovery_note="Keep this as a bridge target from the dashboard instead of re-embedding or mutating the report HTML.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=VALIDATION_BUNDLE_METADATA_ROLE_ID,
            display_name="Validation Bundle Metadata",
            description="Packaged Milestone 13 validation metadata for the current experiment review surface.",
            source_kind=VALIDATION_BUNDLE_SOURCE_KIND,
            required_contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
            artifact_id=METADATA_JSON_KEY,
            artifact_scope=CONTRACT_METADATA_SCOPE,
            supported_pane_ids=[CIRCUIT_PANE_ID, ANALYSIS_PANE_ID],
            discovery_note="Resolve from validation_bundle.json so machine summaries and reviewer handoffs stay package-scoped.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=VALIDATION_SUMMARY_ROLE_ID,
            display_name="Validation Summary",
            description="Machine-readable validation summary for badges, status chips, and audit rollups.",
            source_kind=VALIDATION_BUNDLE_SOURCE_KIND,
            required_contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
            artifact_id=VALIDATION_SUMMARY_ARTIFACT_ID,
            artifact_scope="machine_summary",
            supported_pane_ids=[CIRCUIT_PANE_ID, ANALYSIS_PANE_ID],
            discovery_note="Resolve through the validation bundle metadata so later dashboard code does not re-scan validation directories.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=VALIDATION_REVIEW_HANDOFF_ROLE_ID,
            display_name="Validation Review Handoff",
            description="Reviewer-owned validation handoff artifact for plausibility notes and open findings.",
            source_kind=VALIDATION_BUNDLE_SOURCE_KIND,
            required_contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
            artifact_id=VALIDATION_REVIEW_HANDOFF_ARTIFACT_ID,
            artifact_scope="review_handoff",
            supported_pane_ids=[ANALYSIS_PANE_ID],
            discovery_note="Resolve from the packaged validation bundle so reviewer evidence stays distinct from machine summary rows.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=VALIDATION_OFFLINE_REPORT_ROLE_ID,
            display_name="Validation Offline Report",
            description="Reviewer-oriented static validation report retained for offline compatibility.",
            source_kind=VALIDATION_BUNDLE_SOURCE_KIND,
            required_contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
            artifact_id=VALIDATION_OFFLINE_REPORT_ARTIFACT_ID,
            artifact_scope="offline_review",
            supported_pane_ids=[ANALYSIS_PANE_ID],
            discovery_note="Treat this as a bridge target from the dashboard instead of replacing the packaged offline report workflow.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=WHOLE_BRAIN_CONTEXT_SESSION_METADATA_ROLE_ID,
            display_name="Whole-Brain Context Metadata",
            description="Authoritative Milestone 17 whole-brain-context metadata linked into the dashboard circuit pane.",
            source_kind=WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND,
            required_contract_version="whole_brain_context_session.v1",
            artifact_id=METADATA_JSON_KEY,
            artifact_scope=CONTRACT_METADATA_SCOPE,
            supported_pane_ids=[CIRCUIT_PANE_ID],
            discovery_note="Resolve from whole_brain_context_session.json so the dashboard can trace richer context views back to one packaged Milestone 17 bundle.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=WHOLE_BRAIN_CONTEXT_VIEW_PAYLOAD_ROLE_ID,
            display_name="Whole-Brain Context View Payload",
            description="Packaged Milestone 17 context-view payload used to render overview and focused graph representations.",
            source_kind=WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND,
            required_contract_version="whole_brain_context_session.v1",
            artifact_id="context_view_payload",
            artifact_scope="context_view",
            supported_pane_ids=[CIRCUIT_PANE_ID],
            discovery_note="Resolve through whole_brain_context_session.v1 metadata instead of inventing dashboard-local graph JSON.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=WHOLE_BRAIN_CONTEXT_QUERY_CATALOG_ROLE_ID,
            display_name="Whole-Brain Context Query Catalog",
            description="Preset and query-catalog metadata that explains which richer whole-brain review views are packaged.",
            source_kind=WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND,
            required_contract_version="whole_brain_context_session.v1",
            artifact_id="context_query_catalog",
            artifact_scope="context_query",
            supported_pane_ids=[CIRCUIT_PANE_ID],
            discovery_note="Use the packaged query catalog to explain overview-versus-focused context views without re-scanning raw source files.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=WHOLE_BRAIN_CONTEXT_VIEW_STATE_ROLE_ID,
            display_name="Whole-Brain Context View State",
            description="Serialized Milestone 17 context-view state used for deterministic handoff into richer circuit inspection.",
            source_kind=WHOLE_BRAIN_CONTEXT_SESSION_SOURCE_KIND,
            required_contract_version="whole_brain_context_session.v1",
            artifact_id="context_view_state",
            artifact_scope="context_state",
            supported_pane_ids=[CIRCUIT_PANE_ID],
            discovery_note="Resolve the packaged view state through whole_brain_context_session.v1 metadata rather than dashboard-local heuristics.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=DASHBOARD_SESSION_METADATA_ROLE_ID,
            display_name="Dashboard Session Metadata",
            description="Authoritative metadata for the dashboard session package itself.",
            source_kind=DASHBOARD_SESSION_PACKAGE_SOURCE_KIND,
            required_contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            artifact_id=METADATA_JSON_KEY,
            artifact_scope=CONTRACT_METADATA_SCOPE,
            supported_pane_ids=list(SUPPORTED_PANE_IDS),
            discovery_note="Use the package metadata as the dashboard-owned discovery anchor for local Milestone 14 assets.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
            display_name="Dashboard Session Payload",
            description="Reserved packaged dashboard payload for later app-shell consumption.",
            source_kind=DASHBOARD_SESSION_PACKAGE_SOURCE_KIND,
            required_contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            artifact_id=SESSION_PAYLOAD_ARTIFACT_ID,
            artifact_scope=SESSION_PACKAGE_SCOPE,
            supported_pane_ids=list(SUPPORTED_PANE_IDS),
            discovery_note="Future app-shell code should resolve this payload from dashboard_session.v1 metadata instead of inventing script-local JSON names.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=DASHBOARD_SESSION_STATE_ROLE_ID,
            display_name="Dashboard Session State",
            description="Serialized exportable dashboard interaction state.",
            source_kind=DASHBOARD_SESSION_PACKAGE_SOURCE_KIND,
            required_contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            artifact_id=SESSION_STATE_ARTIFACT_ID,
            artifact_scope=INTERACTION_STATE_SCOPE,
            supported_pane_ids=list(SUPPORTED_PANE_IDS),
            discovery_note="Export and replay tools should resolve the serialized state through dashboard_session.v1 metadata.",
        ),
        build_dashboard_artifact_hook_definition(
            artifact_role_id=DASHBOARD_APP_SHELL_ROLE_ID,
            display_name="Dashboard App Shell",
            description="Offline application-shell entrypoint for the packaged dashboard.",
            source_kind=DASHBOARD_SESSION_PACKAGE_SOURCE_KIND,
            required_contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            artifact_id=APP_SHELL_INDEX_ARTIFACT_ID,
            artifact_scope=APP_SHELL_SCOPE,
            supported_pane_ids=list(SUPPORTED_PANE_IDS),
            discovery_note="The default delivery model is a self-contained static app; later launch tooling should still discover it from dashboard_session.v1 metadata.",
        ),
    ]


def _default_linked_selection_invariants() -> tuple[str, ...]:
    return (
        "selected_arm_pair is global state and determines the baseline-versus-wave pairing story for every pane.",
        "selected_neuron_id propagates from circuit inspection into morphology, time-series, and analysis views without renaming the root identity.",
        "selected_readout_id propagates on the shared simulator readout catalog instead of pane-local aliases.",
        "time_cursor is serialized as milliseconds plus sample index and is the single replay cursor for all time-aware panes.",
        "active_overlay_id is global session state and must always resolve through the contract-owned overlay catalog.",
    )


def _default_fairness_boundary_invariants() -> tuple[str, ...]:
    return (
        "shared_comparison overlays remain tied to simulator_result_bundle.v1 shared readouts and experiment_analysis_bundle.v1 shared-comparison summaries.",
        "wave_only_diagnostic overlays may depend on wave-specific artifacts, but they must remain visibly labeled as diagnostics rather than the fair comparison surface.",
        "validation_evidence overlays are reviewer-oriented evidence and may not be silently merged into shared comparison cards or wave diagnostics.",
        "whole-brain context bridges may widen structural context, but they may not relabel context-only nodes as active simulated neurons.",
        "offline reports remain bridge artifacts discovered from upstream package metadata rather than replacement data sources for the dashboard session.",
    )


def _build_session_identity_payload(
    *,
    manifest_reference: Mapping[str, Any],
    ui_delivery_model: str,
    global_interaction_state: Mapping[str, Any],
    enabled_export_target_ids: Sequence[str],
    artifact_references: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "manifest_reference": parse_simulator_manifest_reference(manifest_reference),
        "ui_delivery_model": _normalize_ui_delivery_model(ui_delivery_model),
        "global_interaction_state": _normalize_global_interaction_state_against_contract(
            global_interaction_state,
            contract_metadata=build_dashboard_session_contract_metadata(),
        ),
        "enabled_export_target_ids": _normalize_known_value_list(
            enabled_export_target_ids,
            field_name="enabled_export_target_ids",
            supported_values=SUPPORTED_EXPORT_TARGET_IDS,
            allow_empty=False,
        ),
        "artifact_references": _normalize_artifact_reference_catalog(
            artifact_references,
            field_name="artifact_references",
        ),
    }


def _artifact_record(
    *,
    path: str | Path,
    format: str,
    status: str,
    artifact_scope: str,
    description: str,
) -> dict[str, Any]:
    return {
        "path": str(Path(path).resolve()),
        "status": _normalize_asset_status(status, field_name="artifact.status"),
        "format": _normalize_nonempty_string(format, field_name="artifact.format"),
        "artifact_scope": _normalize_identifier(
            artifact_scope,
            field_name="artifact.artifact_scope",
        ),
        "description": _normalize_nonempty_string(
            description,
            field_name="artifact.description",
        ),
    }


def _normalize_output_root_reference(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("output_root_reference must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = ("processed_simulator_results_dir",)
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"output_root_reference is missing fields: {missing_fields!r}.")
    normalized["processed_simulator_results_dir"] = str(
        Path(
            _normalize_nonempty_string(
                normalized["processed_simulator_results_dir"],
                field_name="output_root_reference.processed_simulator_results_dir",
            )
        ).resolve()
    )
    return normalized


def _normalize_bundle_layout(
    payload: Mapping[str, Any],
    *,
    expected_bundle_directory: Path,
    expected_app_directory: Path,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("bundle_layout must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = ("bundle_directory", "app_directory")
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"bundle_layout is missing fields: {missing_fields!r}.")
    normalized["bundle_directory"] = str(
        Path(
            _normalize_nonempty_string(
                normalized["bundle_directory"],
                field_name="bundle_layout.bundle_directory",
            )
        ).resolve()
    )
    normalized["app_directory"] = str(
        Path(
            _normalize_nonempty_string(
                normalized["app_directory"],
                field_name="bundle_layout.app_directory",
            )
        ).resolve()
    )
    if normalized["bundle_directory"] != str(expected_bundle_directory.resolve()):
        raise ValueError("bundle_layout.bundle_directory does not match the canonical contract path.")
    if normalized["app_directory"] != str(expected_app_directory.resolve()):
        raise ValueError("bundle_layout.app_directory does not match the canonical contract path.")
    return normalized


def _normalize_dashboard_session_artifacts(
    payload: Mapping[str, Any],
    *,
    bundle_paths: DashboardSessionBundlePaths,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("artifacts must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_artifact_ids = (
        METADATA_JSON_KEY,
        SESSION_PAYLOAD_ARTIFACT_ID,
        SESSION_STATE_ARTIFACT_ID,
        APP_SHELL_INDEX_ARTIFACT_ID,
    )
    missing_fields = [field for field in required_artifact_ids if field not in normalized]
    if missing_fields:
        raise ValueError(f"artifacts is missing fields: {missing_fields!r}.")
    expected_records = {
        METADATA_JSON_KEY: (
            bundle_paths.metadata_json_path,
            "json_dashboard_session_metadata.v1",
            CONTRACT_METADATA_SCOPE,
        ),
        SESSION_PAYLOAD_ARTIFACT_ID: (
            bundle_paths.session_payload_path,
            JSON_SESSION_PAYLOAD_FORMAT,
            SESSION_PACKAGE_SCOPE,
        ),
        SESSION_STATE_ARTIFACT_ID: (
            bundle_paths.session_state_path,
            JSON_SESSION_STATE_FORMAT,
            INTERACTION_STATE_SCOPE,
        ),
        APP_SHELL_INDEX_ARTIFACT_ID: (
            bundle_paths.app_shell_index_path,
            HTML_APP_SHELL_FORMAT,
            APP_SHELL_SCOPE,
        ),
    }
    result: dict[str, Any] = {}
    for artifact_id in required_artifact_ids:
        result[artifact_id] = _normalize_dashboard_artifact_record(
            normalized[artifact_id],
            field_name=f"artifacts.{artifact_id}",
            expected_path=expected_records[artifact_id][0],
            expected_format=expected_records[artifact_id][1],
            expected_scope=expected_records[artifact_id][2],
        )
    return result


def _normalize_dashboard_artifact_record(
    payload: Mapping[str, Any],
    *,
    field_name: str,
    expected_path: Path,
    expected_format: str,
    expected_scope: str,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    normalized = copy.deepcopy(dict(payload))
    required_fields = ("path", "status", "format", "artifact_scope", "description")
    missing_fields = [field for field in required_fields if field not in normalized]
    if missing_fields:
        raise ValueError(f"{field_name} is missing fields: {missing_fields!r}.")
    normalized["path"] = str(
        Path(
            _normalize_nonempty_string(
                normalized["path"],
                field_name=f"{field_name}.path",
            )
        ).resolve()
    )
    if normalized["path"] != str(expected_path.resolve()):
        raise ValueError(f"{field_name}.path does not match the canonical bundle path.")
    normalized["status"] = _normalize_asset_status(
        normalized["status"],
        field_name=f"{field_name}.status",
    )
    normalized["format"] = _normalize_nonempty_string(
        normalized["format"],
        field_name=f"{field_name}.format",
    )
    if normalized["format"] != expected_format:
        raise ValueError(f"{field_name}.format must be {expected_format!r}.")
    normalized["artifact_scope"] = _normalize_identifier(
        normalized["artifact_scope"],
        field_name=f"{field_name}.artifact_scope",
    )
    if normalized["artifact_scope"] != expected_scope:
        raise ValueError(f"{field_name}.artifact_scope must be {expected_scope!r}.")
    normalized["description"] = _normalize_nonempty_string(
        normalized["description"],
        field_name=f"{field_name}.description",
    )
    return normalized


def _normalize_pane_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("pane_catalog must be a sequence of mappings.")
    result = [parse_dashboard_pane_definition(item) for item in payload]
    _ensure_unique_ids(result, key_name="pane_id", field_name="pane_catalog")
    return sorted(result, key=lambda item: (item["sequence_index"], item["pane_id"]))


def _normalize_overlay_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("overlay_catalog must be a sequence of mappings.")
    result = [parse_dashboard_overlay_definition(item) for item in payload]
    _ensure_unique_ids(result, key_name="overlay_id", field_name="overlay_catalog")
    return sorted(
        result,
        key=lambda item: (
            _OVERLAY_CATEGORY_ORDER[item["overlay_category"]],
            _OVERLAY_ID_ORDER[item["overlay_id"]],
        ),
    )


def _normalize_comparison_mode_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("comparison_mode_catalog must be a sequence of mappings.")
    result = [parse_dashboard_comparison_mode_definition(item) for item in payload]
    _ensure_unique_ids(
        result,
        key_name="comparison_mode_id",
        field_name="comparison_mode_catalog",
    )
    return sorted(
        result,
        key=lambda item: _COMPARISON_MODE_ORDER[item["comparison_mode_id"]],
    )


def _normalize_export_target_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("export_target_catalog must be a sequence of mappings.")
    result = [parse_dashboard_export_target_definition(item) for item in payload]
    _ensure_unique_ids(
        result,
        key_name="export_target_id",
        field_name="export_target_catalog",
    )
    return sorted(result, key=lambda item: _EXPORT_TARGET_ORDER[item["export_target_id"]])


def _normalize_artifact_hook_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("artifact_hook_catalog must be a sequence of mappings.")
    result = [parse_dashboard_artifact_hook_definition(item) for item in payload]
    _ensure_unique_ids(
        result,
        key_name="artifact_role_id",
        field_name="artifact_hook_catalog",
    )
    return sorted(result, key=lambda item: _ARTIFACT_ROLE_ORDER[item["artifact_role_id"]])


def _normalize_artifact_reference_catalog(
    payload: Any,
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of mappings.")
    result = [parse_dashboard_session_artifact_reference(item) for item in payload]
    _ensure_unique_artifact_bindings(result, field_name=field_name)
    return sorted(
        result,
        key=lambda item: (
            _SOURCE_KIND_ORDER[item["source_kind"]],
            _ARTIFACT_ROLE_ORDER[item["artifact_role_id"]],
            item["path"],
        ),
    )


def _validate_artifact_references_against_contract(
    artifact_references: Sequence[Mapping[str, Any]],
    *,
    contract_metadata: Mapping[str, Any],
    field_name: str,
) -> None:
    hook_catalog_by_role = {
        item["artifact_role_id"]: item
        for item in contract_metadata["artifact_hook_catalog"]
    }
    for index, reference in enumerate(artifact_references):
        hook = hook_catalog_by_role[reference["artifact_role_id"]]
        if reference["source_kind"] != hook["source_kind"]:
            raise ValueError(
                f"{field_name}[{index}] source_kind does not match artifact_hook_catalog."
            )
        if reference["contract_version"] != hook["required_contract_version"]:
            raise ValueError(
                f"{field_name}[{index}] contract_version does not match artifact_hook_catalog."
            )
        if reference["artifact_id"] != hook["artifact_id"]:
            raise ValueError(
                f"{field_name}[{index}] artifact_id does not match artifact_hook_catalog."
            )
        if (
            reference["artifact_scope"] is not None
            and reference["artifact_scope"] != hook["artifact_scope"]
        ):
            raise ValueError(
                f"{field_name}[{index}] artifact_scope does not match artifact_hook_catalog."
            )


def _normalize_global_interaction_state_against_contract(
    payload: Mapping[str, Any],
    *,
    contract_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = parse_dashboard_global_interaction_state(payload)
    overlay_catalog_by_id = {
        item["overlay_id"]: item for item in contract_metadata["overlay_catalog"]
    }
    comparison_mode_catalog_by_id = {
        item["comparison_mode_id"]: item for item in contract_metadata["comparison_mode_catalog"]
    }
    active_overlay = overlay_catalog_by_id[normalized["active_overlay_id"]]
    comparison_mode = comparison_mode_catalog_by_id[normalized["comparison_mode"]]
    if normalized["comparison_mode"] not in active_overlay["supported_comparison_modes"]:
        raise ValueError(
            "global_interaction_state.active_overlay_id is not supported by the selected comparison_mode."
        )
    if active_overlay["overlay_category"] not in comparison_mode["allowed_overlay_categories"]:
        raise ValueError(
            "global_interaction_state.active_overlay_id is not compatible with the selected comparison_mode."
        )
    if (
        comparison_mode["required_arm_count"] == 2
        and normalized["selected_arm_pair"]["baseline_arm_id"]
        == normalized["selected_arm_pair"]["wave_arm_id"]
    ):
        raise ValueError("Paired comparison modes require distinct baseline and wave arms.")
    return normalized


def _normalize_boolean(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} must be a boolean.")


def _normalize_nonnegative_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a non-negative integer.")
    if isinstance(value, int):
        integer = value
    elif isinstance(value, float) and math.isfinite(value) and value.is_integer():
        integer = int(value)
    else:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    if integer < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    return integer


def _normalize_positive_int(value: Any, *, field_name: str) -> int:
    integer = _normalize_nonnegative_int(value, field_name=field_name)
    if integer <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")
    return integer


def _normalize_optional_string(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _normalize_nonempty_string(value, field_name=field_name)


def _normalize_optional_identifier(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _normalize_identifier(value, field_name=field_name)


def _normalize_known_value_list(
    payload: Any,
    *,
    field_name: str,
    supported_values: Sequence[str],
    allow_empty: bool,
) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of strings.")
    normalized_values: list[str] = []
    seen: set[str] = set()
    supported_set = set(supported_values)
    for index, item in enumerate(payload):
        normalized_item = _normalize_identifier(
            item,
            field_name=f"{field_name}[{index}]",
        )
        if normalized_item not in supported_set:
            raise ValueError(
                f"{field_name}[{index}] must be one of {tuple(supported_values)!r}."
            )
        if normalized_item not in seen:
            seen.add(normalized_item)
            normalized_values.append(normalized_item)
    if not allow_empty and not normalized_values:
        raise ValueError(f"{field_name} must not be empty.")
    return [value for value in supported_values if value in seen]


def _normalize_known_string_list(
    payload: Any,
    *,
    field_name: str,
    supported_values: Sequence[str],
    allow_empty: bool,
) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of strings.")
    normalized_values: list[str] = []
    seen: set[str] = set()
    supported_set = set(supported_values)
    for index, item in enumerate(payload):
        normalized_item = _normalize_nonempty_string(
            item,
            field_name=f"{field_name}[{index}]",
        )
        if normalized_item not in supported_set:
            raise ValueError(
                f"{field_name}[{index}] must be one of {tuple(supported_values)!r}."
            )
        if normalized_item not in seen:
            seen.add(normalized_item)
            normalized_values.append(normalized_item)
    if not allow_empty and not normalized_values:
        raise ValueError(f"{field_name} must not be empty.")
    return [value for value in supported_values if value in seen]


def _normalize_nonempty_string_list(payload: Any, *, field_name: str) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of strings.")
    normalized_values: set[str] = set()
    for index, item in enumerate(payload):
        normalized_values.add(
            _normalize_nonempty_string(item, field_name=f"{field_name}[{index}]")
        )
    if not normalized_values:
        raise ValueError(f"{field_name} must not be empty.")
    return sorted(normalized_values)


def _normalize_ui_delivery_model(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="ui_delivery_model")
    if normalized not in SUPPORTED_UI_DELIVERY_MODELS:
        raise ValueError(
            f"ui_delivery_model must be one of {SUPPORTED_UI_DELIVERY_MODELS!r}."
        )
    return normalized


def _normalize_pane_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="pane_id")
    if normalized not in SUPPORTED_PANE_IDS:
        raise ValueError(f"pane_id must be one of {SUPPORTED_PANE_IDS!r}.")
    return normalized


def _normalize_overlay_category(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="overlay_category")
    if normalized not in SUPPORTED_OVERLAY_CATEGORIES:
        raise ValueError(
            f"overlay_category must be one of {SUPPORTED_OVERLAY_CATEGORIES!r}."
        )
    return normalized


def _normalize_overlay_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="overlay_id")
    if normalized not in SUPPORTED_OVERLAY_IDS:
        raise ValueError(f"overlay_id must be one of {SUPPORTED_OVERLAY_IDS!r}.")
    return normalized


def _normalize_comparison_mode_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="comparison_mode_id")
    if normalized not in SUPPORTED_COMPARISON_MODES:
        raise ValueError(
            f"comparison_mode_id must be one of {SUPPORTED_COMPARISON_MODES!r}."
        )
    return normalized


def _normalize_playback_state(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="playback_state")
    if normalized not in SUPPORTED_PLAYBACK_STATES:
        raise ValueError(
            f"playback_state must be one of {SUPPORTED_PLAYBACK_STATES!r}."
        )
    return normalized


def _normalize_export_target_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="export_target_id")
    if normalized not in SUPPORTED_EXPORT_TARGET_IDS:
        raise ValueError(
            f"export_target_id must be one of {SUPPORTED_EXPORT_TARGET_IDS!r}."
        )
    return normalized


def _normalize_export_target_kind(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="export_target.target_kind")
    if normalized not in SUPPORTED_EXPORT_TARGET_KINDS:
        raise ValueError(
            f"export_target.target_kind must be one of {SUPPORTED_EXPORT_TARGET_KINDS!r}."
        )
    return normalized


def _normalize_source_kind(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="artifact_reference.source_kind")
    if normalized not in SUPPORTED_ARTIFACT_SOURCE_KINDS:
        raise ValueError(
            f"artifact source kind must be one of {SUPPORTED_ARTIFACT_SOURCE_KINDS!r}."
        )
    return normalized


def _normalize_artifact_role_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="artifact_role_id")
    if normalized not in SUPPORTED_ARTIFACT_ROLE_IDS:
        raise ValueError(
            f"artifact_role_id must be one of {SUPPORTED_ARTIFACT_ROLE_IDS!r}."
        )
    return normalized


def _extract_dashboard_contract_mapping(record: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(record, Mapping):
        raise ValueError("dashboard contract record must be a mapping.")
    if isinstance(record.get("dashboard_session_contract"), Mapping):
        return record["dashboard_session_contract"]
    return record


def _extract_dashboard_session_mapping(record: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(record, Mapping):
        raise ValueError("dashboard session record must be a mapping.")
    if isinstance(record.get("dashboard_session"), Mapping):
        return record["dashboard_session"]
    return record


def _ensure_unique_ids(
    items: Sequence[Mapping[str, Any]],
    *,
    key_name: str,
    field_name: str,
) -> None:
    ids = [str(item[key_name]) for item in items]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        raise ValueError(f"{field_name} contains duplicate {key_name} values {duplicates!r}.")


def _ensure_unique_artifact_bindings(
    items: Sequence[Mapping[str, Any]],
    *,
    field_name: str,
) -> None:
    seen: set[tuple[str, str]] = set()
    duplicates: list[tuple[str, str]] = []
    for item in items:
        key = (str(item["source_kind"]), str(item["artifact_role_id"]))
        if key in seen:
            duplicates.append(key)
        seen.add(key)
    if duplicates:
        raise ValueError(f"{field_name} contains duplicate source_kind/artifact_role_id bindings {duplicates!r}.")


def _ensure_catalog_ids_match(
    *,
    catalog_name: str,
    actual_ids: set[str],
    expected_ids: set[str],
) -> None:
    if actual_ids != expected_ids:
        missing_ids = sorted(expected_ids - actual_ids)
        extra_ids = sorted(actual_ids - expected_ids)
        raise ValueError(
            f"{catalog_name} must contain the canonical v1 ids. Missing={missing_ids!r} extra={extra_ids!r}."
        )
