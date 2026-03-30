from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dashboard_session_contract import DASHBOARD_SESSION_CONTRACT_VERSION
from .experiment_analysis_contract import EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION
from .experiment_suite_contract import EXPERIMENT_SUITE_CONTRACT_VERSION
from .io_utils import write_json
from .simulator_result_contract import DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR
from .stimulus_contract import (
    ASSET_STATUS_MISSING,
    ASSET_STATUS_READY,
    DEFAULT_HASH_ALGORITHM,
    _normalize_asset_status,
    _normalize_identifier,
    _normalize_json_mapping,
    _normalize_nonempty_string,
    _normalize_parameter_hash,
)
from .validation_contract import VALIDATION_LADDER_CONTRACT_VERSION


SHOWCASE_SESSION_CONTRACT_VERSION = "showcase_session.v1"
SHOWCASE_SESSION_DESIGN_NOTE = "docs/showcase_mode_design.md"
SHOWCASE_SESSION_DESIGN_NOTE_VERSION = "showcase_session_design_note.v1"

DEFAULT_SHOWCASE_SESSION_DIRECTORY_NAME = "showcase_sessions"
DEFAULT_SHOWCASE_EXPORT_DIRECTORY_NAME = "exports"

PRESENTATION_OWNER_JACK = "jack"
SCIENTIFIC_OWNER_GRANT = "grant"

METADATA_JSON_KEY = "metadata_json"
SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID = "showcase_script_payload"
SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID = "showcase_presentation_state"
NARRATIVE_PRESET_CATALOG_ARTIFACT_ID = "narrative_preset_catalog"
SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID = "showcase_export_manifest"

CONTRACT_METADATA_SCOPE = "contract_metadata"
DASHBOARD_CONTEXT_SCOPE = "dashboard_context"
SUITE_ROLLUP_SCOPE = "suite_rollup"
ANALYSIS_CONTEXT_SCOPE = "analysis_context"
VALIDATION_GUARDRAIL_SCOPE = "validation_guardrail"
NARRATIVE_PRESET_SCOPE = "narrative_preset"
SCRIPT_PLAYBACK_SCOPE = "script_playback"
PRESENTATION_STATE_SCOPE = "presentation_state"
EXPORT_SURFACE_SCOPE = "export_surface"

SUPPORTED_ARTIFACT_SCOPES = (
    CONTRACT_METADATA_SCOPE,
    DASHBOARD_CONTEXT_SCOPE,
    SUITE_ROLLUP_SCOPE,
    ANALYSIS_CONTEXT_SCOPE,
    VALIDATION_GUARDRAIL_SCOPE,
    NARRATIVE_PRESET_SCOPE,
    SCRIPT_PLAYBACK_SCOPE,
    PRESENTATION_STATE_SCOPE,
    EXPORT_SURFACE_SCOPE,
)

DASHBOARD_SESSION_SOURCE_KIND = "dashboard_session_package"
EXPERIMENT_SUITE_SOURCE_KIND = "experiment_suite_package"
EXPERIMENT_ANALYSIS_SOURCE_KIND = "experiment_analysis_bundle"
VALIDATION_BUNDLE_SOURCE_KIND = "validation_bundle"
SHOWCASE_SESSION_PACKAGE_SOURCE_KIND = "showcase_session_package"

SUPPORTED_ARTIFACT_SOURCE_KINDS = (
    DASHBOARD_SESSION_SOURCE_KIND,
    EXPERIMENT_SUITE_SOURCE_KIND,
    EXPERIMENT_ANALYSIS_SOURCE_KIND,
    VALIDATION_BUNDLE_SOURCE_KIND,
    SHOWCASE_SESSION_PACKAGE_SOURCE_KIND,
)

SCENE_SELECTION_STEP_ID = "scene_selection"
FLY_VIEW_INPUT_STEP_ID = "fly_view_input"
ACTIVE_VISUAL_SUBSET_STEP_ID = "active_visual_subset"
ACTIVITY_PROPAGATION_STEP_ID = "activity_propagation"
BASELINE_WAVE_COMPARISON_STEP_ID = "baseline_wave_comparison"
APPROVED_WAVE_HIGHLIGHT_STEP_ID = "approved_wave_highlight"
SUMMARY_ANALYSIS_STEP_ID = "summary_analysis"

SUPPORTED_SHOWCASE_STEP_IDS = (
    SCENE_SELECTION_STEP_ID,
    FLY_VIEW_INPUT_STEP_ID,
    ACTIVE_VISUAL_SUBSET_STEP_ID,
    ACTIVITY_PROPAGATION_STEP_ID,
    BASELINE_WAVE_COMPARISON_STEP_ID,
    APPROVED_WAVE_HIGHLIGHT_STEP_ID,
    SUMMARY_ANALYSIS_STEP_ID,
)

SCENE_CONTEXT_PRESET_ID = "scene_context"
RETINAL_INPUT_FOCUS_PRESET_ID = "retinal_input_focus"
SUBSET_CONTEXT_PRESET_ID = "subset_context"
PROPAGATION_REPLAY_PRESET_ID = "propagation_replay"
PAIRED_COMPARISON_PRESET_ID = "paired_comparison"
APPROVED_HIGHLIGHT_PRESET_ID = "approved_highlight"
HIGHLIGHT_FALLBACK_PRESET_ID = "highlight_fallback"
ANALYSIS_SUMMARY_PRESET_ID = "analysis_summary"

SUPPORTED_PRESET_IDS = (
    SCENE_CONTEXT_PRESET_ID,
    RETINAL_INPUT_FOCUS_PRESET_ID,
    SUBSET_CONTEXT_PRESET_ID,
    PROPAGATION_REPLAY_PRESET_ID,
    PAIRED_COMPARISON_PRESET_ID,
    APPROVED_HIGHLIGHT_PRESET_ID,
    HIGHLIGHT_FALLBACK_PRESET_ID,
    ANALYSIS_SUMMARY_PRESET_ID,
)

CAMERA_TRANSITION_CUE_KIND_ID = "camera_transition"
PLAYBACK_SCRUB_CUE_KIND_ID = "playback_scrub"
OVERLAY_REVEAL_CUE_KIND_ID = "overlay_reveal"
COMPARISON_SWAP_CUE_KIND_ID = "comparison_swap"
NARRATION_CALLOUT_CUE_KIND_ID = "narration_callout"
EXPORT_CAPTURE_CUE_KIND_ID = "export_capture"
FALLBACK_REDIRECT_CUE_KIND_ID = "fallback_redirect"

SUPPORTED_CUE_KIND_IDS = (
    CAMERA_TRANSITION_CUE_KIND_ID,
    PLAYBACK_SCRUB_CUE_KIND_ID,
    OVERLAY_REVEAL_CUE_KIND_ID,
    COMPARISON_SWAP_CUE_KIND_ID,
    NARRATION_CALLOUT_CUE_KIND_ID,
    EXPORT_CAPTURE_CUE_KIND_ID,
    FALLBACK_REDIRECT_CUE_KIND_ID,
)

STORY_CONTEXT_ANNOTATION_ID = "story_context"
INPUT_SAMPLING_ANNOTATION_ID = "input_sampling"
FAIRNESS_BOUNDARY_ANNOTATION_ID = "fairness_boundary"
SCIENTIFIC_GUARDRAIL_ANNOTATION_ID = "scientific_guardrail"
FALLBACK_NOTICE_ANNOTATION_ID = "fallback_notice"
EVIDENCE_CAPTION_ANNOTATION_ID = "evidence_caption"
OPERATOR_PROMPT_ANNOTATION_ID = "operator_prompt"

SUPPORTED_ANNOTATION_IDS = (
    STORY_CONTEXT_ANNOTATION_ID,
    INPUT_SAMPLING_ANNOTATION_ID,
    FAIRNESS_BOUNDARY_ANNOTATION_ID,
    SCIENTIFIC_GUARDRAIL_ANNOTATION_ID,
    FALLBACK_NOTICE_ANNOTATION_ID,
    EVIDENCE_CAPTION_ANNOTATION_ID,
    OPERATOR_PROMPT_ANNOTATION_ID,
)

SCENE_CONTEXT_EVIDENCE_ROLE_ID = "scene_context_evidence"
INPUT_CONTEXT_EVIDENCE_ROLE_ID = "input_context_evidence"
SUBSET_CONTEXT_EVIDENCE_ROLE_ID = "subset_context_evidence"
SHARED_COMPARISON_EVIDENCE_ROLE_ID = "shared_comparison_evidence"
SUITE_ROLLUP_EVIDENCE_ROLE_ID = "suite_rollup_evidence"
APPROVED_WAVE_HIGHLIGHT_EVIDENCE_ROLE_ID = "approved_wave_highlight_evidence"
VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID = "validation_guardrail_evidence"
SUMMARY_ANALYSIS_EVIDENCE_ROLE_ID = "summary_analysis_evidence"

SUPPORTED_EVIDENCE_ROLE_IDS = (
    SCENE_CONTEXT_EVIDENCE_ROLE_ID,
    INPUT_CONTEXT_EVIDENCE_ROLE_ID,
    SUBSET_CONTEXT_EVIDENCE_ROLE_ID,
    SHARED_COMPARISON_EVIDENCE_ROLE_ID,
    SUITE_ROLLUP_EVIDENCE_ROLE_ID,
    APPROVED_WAVE_HIGHLIGHT_EVIDENCE_ROLE_ID,
    VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
    SUMMARY_ANALYSIS_EVIDENCE_ROLE_ID,
)

START_SCRIPT_CONTROL_ID = "start_script"
PAUSE_SCRIPT_CONTROL_ID = "pause_script"
NEXT_STEP_CONTROL_ID = "next_step"
PREVIOUS_STEP_CONTROL_ID = "previous_step"
LOAD_PRESET_CONTROL_ID = "load_preset"
TOGGLE_COMPARISON_CONTROL_ID = "toggle_comparison"
SCRUB_TIME_CONTROL_ID = "scrub_time"
TRIGGER_EXPORT_CONTROL_ID = "trigger_export"

SUPPORTED_OPERATOR_CONTROL_IDS = (
    START_SCRIPT_CONTROL_ID,
    PAUSE_SCRIPT_CONTROL_ID,
    NEXT_STEP_CONTROL_ID,
    PREVIOUS_STEP_CONTROL_ID,
    LOAD_PRESET_CONTROL_ID,
    TOGGLE_COMPARISON_CONTROL_ID,
    SCRUB_TIME_CONTROL_ID,
    TRIGGER_EXPORT_CONTROL_ID,
)

STATE_EXPORT_TARGET_KIND = "state_export"
STORYBOARD_EXPORT_TARGET_KIND = "storyboard_export"
STILL_IMAGE_EXPORT_TARGET_KIND = "still_image_export"
REPLAY_EXPORT_TARGET_KIND = "replay_export"
REVIEW_MANIFEST_EXPORT_TARGET_KIND = "review_manifest_export"

SUPPORTED_EXPORT_TARGET_KINDS = (
    STATE_EXPORT_TARGET_KIND,
    STORYBOARD_EXPORT_TARGET_KIND,
    STILL_IMAGE_EXPORT_TARGET_KIND,
    REPLAY_EXPORT_TARGET_KIND,
    REVIEW_MANIFEST_EXPORT_TARGET_KIND,
)

SHOWCASE_STATE_EXPORT_TARGET_ROLE_ID = "showcase_state_json"
STORYBOARD_EXPORT_TARGET_ROLE_ID = "storyboard_json"
HERO_FRAME_EXPORT_TARGET_ROLE_ID = "hero_frame_png"
SCRIPTED_CLIP_EXPORT_TARGET_ROLE_ID = "scripted_clip_frames"
REVIEW_MANIFEST_EXPORT_TARGET_ROLE_ID = "review_manifest_json"

SUPPORTED_EXPORT_TARGET_ROLE_IDS = (
    SHOWCASE_STATE_EXPORT_TARGET_ROLE_ID,
    STORYBOARD_EXPORT_TARGET_ROLE_ID,
    HERO_FRAME_EXPORT_TARGET_ROLE_ID,
    SCRIPTED_CLIP_EXPORT_TARGET_ROLE_ID,
    REVIEW_MANIFEST_EXPORT_TARGET_ROLE_ID,
)

PRESENTATION_STATUS_PLANNED = "planned"
PRESENTATION_STATUS_READY = "ready"
PRESENTATION_STATUS_FALLBACK = "fallback"
PRESENTATION_STATUS_SCIENTIFIC_REVIEW_REQUIRED = "scientific_review_required"
PRESENTATION_STATUS_BLOCKED = "blocked"

SUPPORTED_PRESENTATION_STATUSES = (
    PRESENTATION_STATUS_PLANNED,
    PRESENTATION_STATUS_READY,
    PRESENTATION_STATUS_FALLBACK,
    PRESENTATION_STATUS_SCIENTIFIC_REVIEW_REQUIRED,
    PRESENTATION_STATUS_BLOCKED,
)

DASHBOARD_SESSION_METADATA_ROLE_ID = "dashboard_session_metadata"
DASHBOARD_SESSION_PAYLOAD_ROLE_ID = "dashboard_session_payload"
DASHBOARD_SESSION_STATE_ROLE_ID = "dashboard_session_state"
SUITE_SUMMARY_TABLE_ROLE_ID = "suite_summary_table"
SUITE_COMPARISON_PLOT_ROLE_ID = "suite_comparison_plot"
SUITE_REVIEW_ARTIFACT_ROLE_ID = "suite_review_artifact"
ANALYSIS_BUNDLE_METADATA_ROLE_ID = "analysis_bundle_metadata"
ANALYSIS_UI_PAYLOAD_ROLE_ID = "analysis_ui_payload"
ANALYSIS_OFFLINE_REPORT_ROLE_ID = "analysis_offline_report"
VALIDATION_BUNDLE_METADATA_ROLE_ID = "validation_bundle_metadata"
VALIDATION_SUMMARY_ROLE_ID = "validation_summary"
VALIDATION_FINDINGS_ROLE_ID = "validation_findings"
VALIDATION_REVIEW_HANDOFF_ROLE_ID = "validation_review_handoff"
NARRATIVE_PRESET_CATALOG_ROLE_ID = "narrative_preset_catalog"
SHOWCASE_SESSION_METADATA_ROLE_ID = "showcase_session_metadata"
SHOWCASE_SCRIPT_PAYLOAD_ROLE_ID = "showcase_script_payload"
SHOWCASE_PRESENTATION_STATE_ROLE_ID = "showcase_presentation_state"
SHOWCASE_EXPORT_MANIFEST_ROLE_ID = "showcase_export_manifest"

SUPPORTED_ARTIFACT_ROLE_IDS = (
    DASHBOARD_SESSION_METADATA_ROLE_ID,
    DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
    DASHBOARD_SESSION_STATE_ROLE_ID,
    SUITE_SUMMARY_TABLE_ROLE_ID,
    SUITE_COMPARISON_PLOT_ROLE_ID,
    SUITE_REVIEW_ARTIFACT_ROLE_ID,
    ANALYSIS_BUNDLE_METADATA_ROLE_ID,
    ANALYSIS_UI_PAYLOAD_ROLE_ID,
    ANALYSIS_OFFLINE_REPORT_ROLE_ID,
    VALIDATION_BUNDLE_METADATA_ROLE_ID,
    VALIDATION_SUMMARY_ROLE_ID,
    VALIDATION_FINDINGS_ROLE_ID,
    VALIDATION_REVIEW_HANDOFF_ROLE_ID,
    NARRATIVE_PRESET_CATALOG_ROLE_ID,
    SHOWCASE_SESSION_METADATA_ROLE_ID,
    SHOWCASE_SCRIPT_PAYLOAD_ROLE_ID,
    SHOWCASE_PRESENTATION_STATE_ROLE_ID,
    SHOWCASE_EXPORT_MANIFEST_ROLE_ID,
)

REQUIRED_EXTERNAL_ARTIFACT_ROLE_IDS = (
    DASHBOARD_SESSION_METADATA_ROLE_ID,
    DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
    DASHBOARD_SESSION_STATE_ROLE_ID,
    ANALYSIS_UI_PAYLOAD_ROLE_ID,
    VALIDATION_SUMMARY_ROLE_ID,
    VALIDATION_FINDINGS_ROLE_ID,
)

REQUIRED_LOCAL_ARTIFACT_ROLE_IDS = (
    NARRATIVE_PRESET_CATALOG_ROLE_ID,
    SHOWCASE_SESSION_METADATA_ROLE_ID,
    SHOWCASE_SCRIPT_PAYLOAD_ROLE_ID,
    SHOWCASE_PRESENTATION_STATE_ROLE_ID,
    SHOWCASE_EXPORT_MANIFEST_ROLE_ID,
)

DASHBOARD_SESSION_DISCOVERY_HOOK_ID = "dashboard_session_reference"
SUITE_COMPARISON_DISCOVERY_HOOK_ID = "suite_comparison_outputs"
ANALYSIS_BUNDLE_DISCOVERY_HOOK_ID = "analysis_bundle_reference"
VALIDATION_FINDINGS_DISCOVERY_HOOK_ID = "validation_findings_reference"
NARRATIVE_PRESET_DISCOVERY_HOOK_ID = "narrative_preset_catalog"
SHOWCASE_ARTIFACT_DISCOVERY_HOOK_ID = "showcase_artifact_catalog"
STABLE_STEP_ORDER_DISCOVERY_HOOK_ID = "stable_step_order"
HIGHLIGHT_FALLBACK_DISCOVERY_HOOK_ID = "highlight_fallback_path"

SUPPORTED_DISCOVERY_HOOK_IDS = (
    DASHBOARD_SESSION_DISCOVERY_HOOK_ID,
    SUITE_COMPARISON_DISCOVERY_HOOK_ID,
    ANALYSIS_BUNDLE_DISCOVERY_HOOK_ID,
    VALIDATION_FINDINGS_DISCOVERY_HOOK_ID,
    NARRATIVE_PRESET_DISCOVERY_HOOK_ID,
    SHOWCASE_ARTIFACT_DISCOVERY_HOOK_ID,
    STABLE_STEP_ORDER_DISCOVERY_HOOK_ID,
    HIGHLIGHT_FALLBACK_DISCOVERY_HOOK_ID,
)

JSON_SHOWCASE_SCRIPT_FORMAT = "json_showcase_script.v1"
JSON_SHOWCASE_STATE_FORMAT = "json_showcase_presentation_state.v1"
JSON_NARRATIVE_PRESET_CATALOG_FORMAT = "json_narrative_preset_catalog.v1"
JSON_SHOWCASE_EXPORT_MANIFEST_FORMAT = "json_showcase_export_manifest.v1"

COMPOSED_CONTRACTS = (
    DASHBOARD_SESSION_CONTRACT_VERSION,
    EXPERIMENT_SUITE_CONTRACT_VERSION,
    EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION,
    VALIDATION_LADDER_CONTRACT_VERSION,
)

DEFAULT_EXPORT_TARGET_ROLE_ID = SHOWCASE_STATE_EXPORT_TARGET_ROLE_ID

_STEP_ORDER = {value: index for index, value in enumerate(SUPPORTED_SHOWCASE_STEP_IDS)}
_PRESET_ORDER = {value: index for index, value in enumerate(SUPPORTED_PRESET_IDS)}
_CUE_KIND_ORDER = {value: index for index, value in enumerate(SUPPORTED_CUE_KIND_IDS)}
_ANNOTATION_ORDER = {value: index for index, value in enumerate(SUPPORTED_ANNOTATION_IDS)}
_EVIDENCE_ROLE_ORDER = {value: index for index, value in enumerate(SUPPORTED_EVIDENCE_ROLE_IDS)}
_CONTROL_ORDER = {value: index for index, value in enumerate(SUPPORTED_OPERATOR_CONTROL_IDS)}
_EXPORT_TARGET_ROLE_ORDER = {value: index for index, value in enumerate(SUPPORTED_EXPORT_TARGET_ROLE_IDS)}
_PRESENTATION_STATUS_ORDER = {value: index for index, value in enumerate(SUPPORTED_PRESENTATION_STATUSES)}
_ARTIFACT_ROLE_ORDER = {value: index for index, value in enumerate(SUPPORTED_ARTIFACT_ROLE_IDS)}
_SOURCE_KIND_ORDER = {value: index for index, value in enumerate(SUPPORTED_ARTIFACT_SOURCE_KINDS)}
_DISCOVERY_HOOK_ORDER = {value: index for index, value in enumerate(SUPPORTED_DISCOVERY_HOOK_IDS)}


@dataclass(frozen=True)
class ShowcaseSessionBundlePaths:
    processed_simulator_results_dir: Path
    experiment_id: str
    showcase_spec_hash: str
    bundle_directory: Path
    exports_directory: Path
    metadata_json_path: Path
    script_payload_path: Path
    presentation_state_path: Path
    preset_catalog_path: Path
    export_manifest_path: Path

    @property
    def bundle_id(self) -> str:
        return (
            f"{SHOWCASE_SESSION_CONTRACT_VERSION}:"
            f"{self.experiment_id}:{self.showcase_spec_hash}"
        )

    def asset_paths(self) -> dict[str, Path]:
        return {
            METADATA_JSON_KEY: self.metadata_json_path,
            SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID: self.script_payload_path,
            SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID: self.presentation_state_path,
            NARRATIVE_PRESET_CATALOG_ARTIFACT_ID: self.preset_catalog_path,
            SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID: self.export_manifest_path,
        }


def build_showcase_session_bundle_paths(
    *,
    experiment_id: str,
    showcase_spec_hash: str,
    processed_simulator_results_dir: str | Path = DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
) -> ShowcaseSessionBundlePaths:
    normalized_experiment_id = _normalize_identifier(
        experiment_id,
        field_name="experiment_id",
    )
    normalized_showcase_spec_hash = _normalize_parameter_hash(showcase_spec_hash)
    processed_dir = Path(processed_simulator_results_dir).resolve()
    bundle_directory = (
        processed_dir
        / DEFAULT_SHOWCASE_SESSION_DIRECTORY_NAME
        / normalized_experiment_id
        / normalized_showcase_spec_hash
    ).resolve()
    exports_directory = (bundle_directory / DEFAULT_SHOWCASE_EXPORT_DIRECTORY_NAME).resolve()
    return ShowcaseSessionBundlePaths(
        processed_simulator_results_dir=processed_dir,
        experiment_id=normalized_experiment_id,
        showcase_spec_hash=normalized_showcase_spec_hash,
        bundle_directory=bundle_directory,
        exports_directory=exports_directory,
        metadata_json_path=bundle_directory / "showcase_session.json",
        script_payload_path=bundle_directory / "showcase_script.json",
        presentation_state_path=bundle_directory / "showcase_state.json",
        preset_catalog_path=bundle_directory / "narrative_preset_catalog.json",
        export_manifest_path=exports_directory / "showcase_export_manifest.json",
    )


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


def _normalize_optional_string(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _normalize_nonempty_string(value, field_name=field_name)


def _normalize_optional_identifier(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _normalize_identifier(value, field_name=field_name)


def _normalize_nonempty_string_list(payload: Any, *, field_name: str) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of strings.")
    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(payload):
        normalized_item = _normalize_nonempty_string(
            item,
            field_name=f"{field_name}[{index}]",
        )
        if normalized_item not in seen:
            seen.add(normalized_item)
            normalized.append(normalized_item)
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


def _normalize_identifier_list(payload: Any, *, field_name: str) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of strings.")
    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(payload):
        normalized_item = _normalize_identifier(
            item,
            field_name=f"{field_name}[{index}]",
        )
        if normalized_item not in seen:
            seen.add(normalized_item)
            normalized.append(normalized_item)
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


def _normalize_known_value_list(
    payload: Any,
    *,
    field_name: str,
    supported_values: Sequence[str],
    allow_empty: bool,
) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of strings.")
    seen: set[str] = set()
    normalized_values: list[str] = []
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
    seen: set[str] = set()
    normalized_values: list[str] = []
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


def _normalize_step_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="step_id")
    if normalized not in SUPPORTED_SHOWCASE_STEP_IDS:
        raise ValueError(f"step_id must be one of {SUPPORTED_SHOWCASE_STEP_IDS!r}.")
    return normalized


def _normalize_preset_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="preset_id")
    if normalized not in SUPPORTED_PRESET_IDS:
        raise ValueError(f"preset_id must be one of {SUPPORTED_PRESET_IDS!r}.")
    return normalized


def _normalize_cue_kind_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="cue_kind_id")
    if normalized not in SUPPORTED_CUE_KIND_IDS:
        raise ValueError(f"cue_kind_id must be one of {SUPPORTED_CUE_KIND_IDS!r}.")
    return normalized


def _normalize_annotation_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="annotation_id")
    if normalized not in SUPPORTED_ANNOTATION_IDS:
        raise ValueError(f"annotation_id must be one of {SUPPORTED_ANNOTATION_IDS!r}.")
    return normalized


def _normalize_evidence_role_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="evidence_role_id")
    if normalized not in SUPPORTED_EVIDENCE_ROLE_IDS:
        raise ValueError(f"evidence_role_id must be one of {SUPPORTED_EVIDENCE_ROLE_IDS!r}.")
    return normalized


def _normalize_operator_control_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="operator_control_id")
    if normalized not in SUPPORTED_OPERATOR_CONTROL_IDS:
        raise ValueError(
            f"operator_control_id must be one of {SUPPORTED_OPERATOR_CONTROL_IDS!r}."
        )
    return normalized


def _normalize_export_target_kind(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="target_kind")
    if normalized not in SUPPORTED_EXPORT_TARGET_KINDS:
        raise ValueError(
            f"target_kind must be one of {SUPPORTED_EXPORT_TARGET_KINDS!r}."
        )
    return normalized


def _normalize_export_target_role_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="export_target_role_id")
    if normalized not in SUPPORTED_EXPORT_TARGET_ROLE_IDS:
        raise ValueError(
            f"export_target_role_id must be one of {SUPPORTED_EXPORT_TARGET_ROLE_IDS!r}."
        )
    return normalized


def _normalize_presentation_status(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="presentation_status")
    if normalized not in SUPPORTED_PRESENTATION_STATUSES:
        raise ValueError(
            f"presentation_status must be one of {SUPPORTED_PRESENTATION_STATUSES!r}."
        )
    return normalized


def _normalize_artifact_role_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="artifact_role_id")
    if normalized not in SUPPORTED_ARTIFACT_ROLE_IDS:
        raise ValueError(
            f"artifact_role_id must be one of {SUPPORTED_ARTIFACT_ROLE_IDS!r}."
        )
    return normalized


def _normalize_source_kind(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="source_kind")
    if normalized not in SUPPORTED_ARTIFACT_SOURCE_KINDS:
        raise ValueError(
            f"source_kind must be one of {SUPPORTED_ARTIFACT_SOURCE_KINDS!r}."
        )
    return normalized


def _normalize_artifact_scope(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="artifact_scope")
    if normalized not in SUPPORTED_ARTIFACT_SCOPES:
        raise ValueError(
            f"artifact_scope must be one of {SUPPORTED_ARTIFACT_SCOPES!r}."
        )
    return normalized


def _normalize_discovery_hook_id(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="hook_id")
    if normalized not in SUPPORTED_DISCOVERY_HOOK_IDS:
        raise ValueError(
            f"hook_id must be one of {SUPPORTED_DISCOVERY_HOOK_IDS!r}."
        )
    return normalized


def _normalize_optional_preset_id(value: Any) -> str | None:
    if value is None:
        return None
    return _normalize_preset_id(value)


def _normalize_optional_artifact_scope(value: Any) -> str | None:
    if value is None:
        return None
    return _normalize_artifact_scope(value)


def _ensure_unique_ids(
    items: Sequence[Mapping[str, Any]],
    *,
    key_name: str,
    field_name: str,
) -> None:
    seen: set[str] = set()
    for index, item in enumerate(items):
        key = str(item[key_name])
        if key in seen:
            raise ValueError(f"{field_name}[{index}] duplicates {key_name}={key!r}.")
        seen.add(key)


def _ensure_unique_artifact_bindings(
    items: Sequence[Mapping[str, Any]],
    *,
    field_name: str,
) -> None:
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(items):
        key = (str(item["source_kind"]), str(item["artifact_role_id"]))
        if key in seen:
            raise ValueError(
                f"{field_name}[{index}] duplicates source_kind/artifact_role_id binding {key!r}."
            )
        seen.add(key)


def _require_exact_ids(
    actual_ids: Sequence[str],
    *,
    expected_ids: Sequence[str],
    field_name: str,
) -> None:
    if set(actual_ids) != set(expected_ids):
        raise ValueError(
            f"{field_name} must contain exactly {list(expected_ids)!r}; got {list(actual_ids)!r}."
        )


def _unique_ordered(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def default_showcase_session_ownership_boundary() -> dict[str, Any]:
    return {
        "presentation_owner": PRESENTATION_OWNER_JACK,
        "presentation_responsibilities": [
            "scripted_playback_mechanics",
            "saved_preset_identity",
            "camera_transitions",
            "polished_ui_state",
            "operator_controls",
            "export_surfaces",
            "deterministic_showcase_packaging",
        ],
        "scientific_owner": SCIENTIFIC_OWNER_GRANT,
        "scientific_responsibilities": [
            "approved_scientific_comparison_selection",
            "approved_wave_highlight_selection",
            "scientific_claim_scope",
            "highlight_guardrail_review",
        ],
        "boundary_rule": (
            "Jack owns scripted presentation mechanics and export surfaces; "
            "Grant owns which scientific comparison and wave-specific "
            "phenomenon are approved for the highlighted story beat."
        ),
    }


def default_showcase_scientific_guardrail_policy() -> dict[str, Any]:
    return {
        "presentation_owner": PRESENTATION_OWNER_JACK,
        "scientific_owner": SCIENTIFIC_OWNER_GRANT,
        "guardrail_step_id": APPROVED_WAVE_HIGHLIGHT_STEP_ID,
        "fallback_step_id": BASELINE_WAVE_COMPARISON_STEP_ID,
        "fallback_preset_id": HIGHLIGHT_FALLBACK_PRESET_ID,
        "required_evidence_role_ids": [
            APPROVED_WAVE_HIGHLIGHT_EVIDENCE_ROLE_ID,
            VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID,
        ],
        "boundary_rule": (
            "If the requested highlight is unavailable, unapproved, or not "
            "scientifically defensible, the showcase must fall back to the "
            "paired-comparison beat and visibly label the missing highlight."
        ),
    }


def _default_presentation_invariants() -> list[str]:
    return [
        "The showcase flow always uses the same seven stable step ids in the same order.",
        "Saved preset ids, cue kinds, operator controls, and export target roles stay contract-owned rather than script-local.",
        "Showcase sessions compose with dashboard_session.v1 and later milestone bundle metadata instead of mutating those earlier contracts.",
        "Showcase-session serialization stays deterministic across reordered but equivalent fixture inputs.",
    ]


def _default_scientific_guardrail_invariants() -> list[str]:
    return [
        "The baseline-versus-wave comparison beat remains the fairness boundary for direct arm-versus-arm claims.",
        "The highlighted wave-only beat may only use Grant-approved evidence and must stay explicitly labeled as a wave-specific story beat.",
        "Validation findings remain separate guardrail evidence and do not become substitute highlight metrics.",
        "If the requested highlight is unavailable, the session must surface a fallback notice instead of fabricating a substitute effect.",
    ]


def _default_step_catalog() -> list[dict[str, Any]]:
    return [
        {
            "step_id": SCENE_SELECTION_STEP_ID,
            "display_name": "Scene Selection",
            "description": "Choose the visual scene and orient the audience to the planned story before replay begins.",
            "sequence_index": 10,
            "default_preset_id": SCENE_CONTEXT_PRESET_ID,
            "default_cue_kind_id": CAMERA_TRANSITION_CUE_KIND_ID,
            "required_annotation_ids": [STORY_CONTEXT_ANNOTATION_ID, OPERATOR_PROMPT_ANNOTATION_ID],
            "required_evidence_role_ids": [SCENE_CONTEXT_EVIDENCE_ROLE_ID],
            "required_operator_control_ids": [START_SCRIPT_CONTROL_ID, LOAD_PRESET_CONTROL_ID],
            "default_export_target_role_ids": [HERO_FRAME_EXPORT_TARGET_ROLE_ID],
            "scientific_approval_required": False,
            "fallback_preset_id": None,
        },
        {
            "step_id": FLY_VIEW_INPUT_STEP_ID,
            "display_name": "Fly-View Input",
            "description": "Show the fly-view or sampled retinal input that drives the later dynamics.",
            "sequence_index": 20,
            "default_preset_id": RETINAL_INPUT_FOCUS_PRESET_ID,
            "default_cue_kind_id": PLAYBACK_SCRUB_CUE_KIND_ID,
            "required_annotation_ids": [INPUT_SAMPLING_ANNOTATION_ID, EVIDENCE_CAPTION_ANNOTATION_ID],
            "required_evidence_role_ids": [INPUT_CONTEXT_EVIDENCE_ROLE_ID],
            "required_operator_control_ids": [PAUSE_SCRIPT_CONTROL_ID, SCRUB_TIME_CONTROL_ID],
            "default_export_target_role_ids": [HERO_FRAME_EXPORT_TARGET_ROLE_ID],
            "scientific_approval_required": False,
            "fallback_preset_id": None,
        },
        {
            "step_id": ACTIVE_VISUAL_SUBSET_STEP_ID,
            "display_name": "Active Visual Subset",
            "description": "Expose the active visual subset and current circuit focus before wave-specific interpretation starts.",
            "sequence_index": 30,
            "default_preset_id": SUBSET_CONTEXT_PRESET_ID,
            "default_cue_kind_id": OVERLAY_REVEAL_CUE_KIND_ID,
            "required_annotation_ids": [STORY_CONTEXT_ANNOTATION_ID, EVIDENCE_CAPTION_ANNOTATION_ID],
            "required_evidence_role_ids": [SUBSET_CONTEXT_EVIDENCE_ROLE_ID],
            "required_operator_control_ids": [LOAD_PRESET_CONTROL_ID, NEXT_STEP_CONTROL_ID],
            "default_export_target_role_ids": [HERO_FRAME_EXPORT_TARGET_ROLE_ID],
            "scientific_approval_required": False,
            "fallback_preset_id": None,
        },
        {
            "step_id": ACTIVITY_PROPAGATION_STEP_ID,
            "display_name": "Activity Propagation",
            "description": "Replay propagation through the selected circuit with deterministic time control and visible context.",
            "sequence_index": 40,
            "default_preset_id": PROPAGATION_REPLAY_PRESET_ID,
            "default_cue_kind_id": PLAYBACK_SCRUB_CUE_KIND_ID,
            "required_annotation_ids": [EVIDENCE_CAPTION_ANNOTATION_ID, FAIRNESS_BOUNDARY_ANNOTATION_ID],
            "required_evidence_role_ids": [SHARED_COMPARISON_EVIDENCE_ROLE_ID],
            "required_operator_control_ids": [PAUSE_SCRIPT_CONTROL_ID, SCRUB_TIME_CONTROL_ID],
            "default_export_target_role_ids": [SCRIPTED_CLIP_EXPORT_TARGET_ROLE_ID],
            "scientific_approval_required": False,
            "fallback_preset_id": None,
        },
        {
            "step_id": BASELINE_WAVE_COMPARISON_STEP_ID,
            "display_name": "Baseline Vs Wave Comparison",
            "description": "Show the fair paired comparison that anchors later claims about the wave model.",
            "sequence_index": 50,
            "default_preset_id": PAIRED_COMPARISON_PRESET_ID,
            "default_cue_kind_id": COMPARISON_SWAP_CUE_KIND_ID,
            "required_annotation_ids": [FAIRNESS_BOUNDARY_ANNOTATION_ID, EVIDENCE_CAPTION_ANNOTATION_ID],
            "required_evidence_role_ids": [SHARED_COMPARISON_EVIDENCE_ROLE_ID, SUITE_ROLLUP_EVIDENCE_ROLE_ID],
            "required_operator_control_ids": [TOGGLE_COMPARISON_CONTROL_ID, PAUSE_SCRIPT_CONTROL_ID],
            "default_export_target_role_ids": [HERO_FRAME_EXPORT_TARGET_ROLE_ID, STORYBOARD_EXPORT_TARGET_ROLE_ID],
            "scientific_approval_required": False,
            "fallback_preset_id": None,
        },
        {
            "step_id": APPROVED_WAVE_HIGHLIGHT_STEP_ID,
            "display_name": "Approved Wave Highlight",
            "description": "Highlight one Grant-approved wave-specific phenomenon only when the effect remains scientifically defensible.",
            "sequence_index": 60,
            "default_preset_id": APPROVED_HIGHLIGHT_PRESET_ID,
            "default_cue_kind_id": NARRATION_CALLOUT_CUE_KIND_ID,
            "required_annotation_ids": [SCIENTIFIC_GUARDRAIL_ANNOTATION_ID, EVIDENCE_CAPTION_ANNOTATION_ID],
            "required_evidence_role_ids": [APPROVED_WAVE_HIGHLIGHT_EVIDENCE_ROLE_ID, VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID],
            "required_operator_control_ids": [LOAD_PRESET_CONTROL_ID, PAUSE_SCRIPT_CONTROL_ID],
            "default_export_target_role_ids": [HERO_FRAME_EXPORT_TARGET_ROLE_ID, REVIEW_MANIFEST_EXPORT_TARGET_ROLE_ID],
            "scientific_approval_required": True,
            "fallback_preset_id": HIGHLIGHT_FALLBACK_PRESET_ID,
        },
        {
            "step_id": SUMMARY_ANALYSIS_STEP_ID,
            "display_name": "Summary Analysis",
            "description": "Land the story on packaged comparison summaries and reviewer-facing takeaways rather than ad hoc screenshots.",
            "sequence_index": 70,
            "default_preset_id": ANALYSIS_SUMMARY_PRESET_ID,
            "default_cue_kind_id": EXPORT_CAPTURE_CUE_KIND_ID,
            "required_annotation_ids": [STORY_CONTEXT_ANNOTATION_ID, EVIDENCE_CAPTION_ANNOTATION_ID],
            "required_evidence_role_ids": [SUMMARY_ANALYSIS_EVIDENCE_ROLE_ID, SUITE_ROLLUP_EVIDENCE_ROLE_ID],
            "required_operator_control_ids": [TRIGGER_EXPORT_CONTROL_ID, PREVIOUS_STEP_CONTROL_ID],
            "default_export_target_role_ids": [SHOWCASE_STATE_EXPORT_TARGET_ROLE_ID, REVIEW_MANIFEST_EXPORT_TARGET_ROLE_ID],
            "scientific_approval_required": False,
            "fallback_preset_id": None,
        },
    ]


def _default_preset_catalog() -> list[dict[str, Any]]:
    return [
        {"preset_id": SCENE_CONTEXT_PRESET_ID, "display_name": "Scene Context", "description": "Opening preset that frames the chosen scene and initial camera position.", "sequence_index": 10, "supported_step_ids": [SCENE_SELECTION_STEP_ID], "discovery_note": "This preset composes with dashboard-session state to frame the opening context beat.", "fallback_only": False},
        {"preset_id": RETINAL_INPUT_FOCUS_PRESET_ID, "display_name": "Retinal Input Focus", "description": "Preset that emphasizes fly-view or sampled-input playback for the input beat.", "sequence_index": 20, "supported_step_ids": [FLY_VIEW_INPUT_STEP_ID], "discovery_note": "Use the packaged dashboard replay surface rather than bespoke media files for input playback.", "fallback_only": False},
        {"preset_id": SUBSET_CONTEXT_PRESET_ID, "display_name": "Subset Context", "description": "Preset that reveals the active visual subset and selection-linked circuit state.", "sequence_index": 30, "supported_step_ids": [ACTIVE_VISUAL_SUBSET_STEP_ID], "discovery_note": "The subset preset stays anchored to dashboard-session selection state instead of ad hoc neuron lists.", "fallback_only": False},
        {"preset_id": PROPAGATION_REPLAY_PRESET_ID, "display_name": "Propagation Replay", "description": "Replay-oriented preset for the activity-propagation beat.", "sequence_index": 40, "supported_step_ids": [ACTIVITY_PROPAGATION_STEP_ID], "discovery_note": "Propagation playback relies on dashboard-session replay semantics so scripted time control stays deterministic.", "fallback_only": False},
        {"preset_id": PAIRED_COMPARISON_PRESET_ID, "display_name": "Paired Comparison", "description": "Preset that foregrounds the matched baseline-versus-wave comparison without hiding the baseline arm.", "sequence_index": 50, "supported_step_ids": [BASELINE_WAVE_COMPARISON_STEP_ID], "discovery_note": "This preset is the fairness anchor for later Milestone 16 claims.", "fallback_only": False},
        {"preset_id": APPROVED_HIGHLIGHT_PRESET_ID, "display_name": "Approved Highlight", "description": "Preset reserved for the Grant-approved wave-specific phenomenon when the highlight is available.", "sequence_index": 60, "supported_step_ids": [APPROVED_WAVE_HIGHLIGHT_STEP_ID], "discovery_note": "Only use this preset when the highlight beat remains scientifically approved and validation-backed.", "fallback_only": False},
        {"preset_id": HIGHLIGHT_FALLBACK_PRESET_ID, "display_name": "Highlight Fallback", "description": "Fallback preset that visibly redirects the narrative when the requested highlight is unavailable or unapproved.", "sequence_index": 70, "supported_step_ids": [APPROVED_WAVE_HIGHLIGHT_STEP_ID], "discovery_note": "This preset preserves the storyline without fabricating a wave-only effect.", "fallback_only": True},
        {"preset_id": ANALYSIS_SUMMARY_PRESET_ID, "display_name": "Analysis Summary", "description": "Closing preset for the packaged summary-analysis beat and reviewer-facing exports.", "sequence_index": 80, "supported_step_ids": [SUMMARY_ANALYSIS_STEP_ID], "discovery_note": "The summary preset should point at packaged suite and analysis outputs instead of one-off screenshots.", "fallback_only": False},
    ]


def _default_cue_kind_catalog() -> list[dict[str, Any]]:
    return [
        {"cue_kind_id": CAMERA_TRANSITION_CUE_KIND_ID, "display_name": "Camera Transition", "description": "Move the view between saved presets or story beats without changing the underlying scientific payload.", "sequence_index": 10},
        {"cue_kind_id": PLAYBACK_SCRUB_CUE_KIND_ID, "display_name": "Playback Scrub", "description": "Advance or pause the shared replay cursor through deterministic input or activity playback.", "sequence_index": 20},
        {"cue_kind_id": OVERLAY_REVEAL_CUE_KIND_ID, "display_name": "Overlay Reveal", "description": "Reveal subset or context overlays tied to packaged dashboard state.", "sequence_index": 30},
        {"cue_kind_id": COMPARISON_SWAP_CUE_KIND_ID, "display_name": "Comparison Swap", "description": "Toggle or foreground a paired comparison mode on the fair baseline-versus-wave surface.", "sequence_index": 40},
        {"cue_kind_id": NARRATION_CALLOUT_CUE_KIND_ID, "display_name": "Narration Callout", "description": "Pause on a specific evidence-backed beat and attach narrative annotation text.", "sequence_index": 50},
        {"cue_kind_id": EXPORT_CAPTURE_CUE_KIND_ID, "display_name": "Export Capture", "description": "Trigger a deterministic export or summary capture at the end of a beat.", "sequence_index": 60},
        {"cue_kind_id": FALLBACK_REDIRECT_CUE_KIND_ID, "display_name": "Fallback Redirect", "description": "Visibly redirect the story to the fallback preset when a requested highlight is unavailable.", "sequence_index": 70},
    ]


def _default_annotation_catalog() -> list[dict[str, Any]]:
    return [
        {"annotation_id": STORY_CONTEXT_ANNOTATION_ID, "display_name": "Story Context", "description": "High-level narration that explains why the current beat exists in the seven-step story.", "sequence_index": 10},
        {"annotation_id": INPUT_SAMPLING_ANNOTATION_ID, "display_name": "Input Sampling", "description": "Narration that explains how the fly-view or sampled input maps onto the packaged replay surface.", "sequence_index": 20},
        {"annotation_id": FAIRNESS_BOUNDARY_ANNOTATION_ID, "display_name": "Fairness Boundary", "description": "Narration that marks the scientifically fair comparison surface and warns against over-claiming.", "sequence_index": 30},
        {"annotation_id": SCIENTIFIC_GUARDRAIL_ANNOTATION_ID, "display_name": "Scientific Guardrail", "description": "Narration that states the guardrail on the highlighted wave-only claim.", "sequence_index": 40},
        {"annotation_id": FALLBACK_NOTICE_ANNOTATION_ID, "display_name": "Fallback Notice", "description": "Narration that explicitly explains why the requested highlight is not being shown.", "sequence_index": 50},
        {"annotation_id": EVIDENCE_CAPTION_ANNOTATION_ID, "display_name": "Evidence Caption", "description": "Short evidence caption linked to one or more packaged artifacts.", "sequence_index": 60},
        {"annotation_id": OPERATOR_PROMPT_ANNOTATION_ID, "display_name": "Operator Prompt", "description": "Short operator-facing prompt used to coordinate scripted playback and pause points.", "sequence_index": 70},
    ]


def _default_evidence_role_catalog() -> list[dict[str, Any]]:
    return [
        {"evidence_role_id": SCENE_CONTEXT_EVIDENCE_ROLE_ID, "display_name": "Scene Context Evidence", "description": "Dashboard-session evidence that identifies the chosen visual scene and opening context.", "sequence_index": 10, "artifact_role_ids": [DASHBOARD_SESSION_METADATA_ROLE_ID, DASHBOARD_SESSION_PAYLOAD_ROLE_ID], "discovery_note": "Resolve scene-context evidence through dashboard-session metadata and payload artifacts instead of hidden UI state."},
        {"evidence_role_id": INPUT_CONTEXT_EVIDENCE_ROLE_ID, "display_name": "Input Context Evidence", "description": "Dashboard-session evidence for fly-view or sampled-input playback on the shared replay surface.", "sequence_index": 20, "artifact_role_ids": [DASHBOARD_SESSION_PAYLOAD_ROLE_ID, DASHBOARD_SESSION_STATE_ROLE_ID], "discovery_note": "The input beat should reuse the packaged dashboard replay surface rather than independent media exports."},
        {"evidence_role_id": SUBSET_CONTEXT_EVIDENCE_ROLE_ID, "display_name": "Subset Context Evidence", "description": "Dashboard-session evidence for the active visual subset and current circuit selection.", "sequence_index": 30, "artifact_role_ids": [DASHBOARD_SESSION_METADATA_ROLE_ID, DASHBOARD_SESSION_STATE_ROLE_ID], "discovery_note": "Active-subset context remains dashboard-owned and discoverable through session metadata-backed state."},
        {"evidence_role_id": SHARED_COMPARISON_EVIDENCE_ROLE_ID, "display_name": "Shared Comparison Evidence", "description": "Fair comparison evidence packaged on the dashboard and analysis shared-comparison surfaces.", "sequence_index": 40, "artifact_role_ids": [DASHBOARD_SESSION_PAYLOAD_ROLE_ID, ANALYSIS_UI_PAYLOAD_ROLE_ID], "discovery_note": "Use shared comparison evidence for any arm-versus-arm claim instead of wave-only diagnostics."},
        {"evidence_role_id": SUITE_ROLLUP_EVIDENCE_ROLE_ID, "display_name": "Suite Rollup Evidence", "description": "Suite-level summary tables or comparison plots that reinforce the polished story with deterministic rollups.", "sequence_index": 50, "artifact_role_ids": [SUITE_SUMMARY_TABLE_ROLE_ID, SUITE_COMPARISON_PLOT_ROLE_ID], "discovery_note": "Suite rollups are supportive context and stay discoverable through experiment_suite.v1 artifact references."},
        {"evidence_role_id": APPROVED_WAVE_HIGHLIGHT_EVIDENCE_ROLE_ID, "display_name": "Approved Wave Highlight Evidence", "description": "Wave-specific evidence approved for the dedicated highlight beat.", "sequence_index": 60, "artifact_role_ids": [ANALYSIS_UI_PAYLOAD_ROLE_ID, ANALYSIS_OFFLINE_REPORT_ROLE_ID], "discovery_note": "Only Grant-approved wave-specific evidence may populate the dedicated highlight beat."},
        {"evidence_role_id": VALIDATION_GUARDRAIL_EVIDENCE_ROLE_ID, "display_name": "Validation Guardrail Evidence", "description": "Milestone 13 validation findings that bound what the highlight beat is allowed to claim.", "sequence_index": 70, "artifact_role_ids": [VALIDATION_SUMMARY_ROLE_ID, VALIDATION_FINDINGS_ROLE_ID, VALIDATION_REVIEW_HANDOFF_ROLE_ID], "discovery_note": "Validation findings are guardrails on the highlight beat, not hidden implementation details."},
        {"evidence_role_id": SUMMARY_ANALYSIS_EVIDENCE_ROLE_ID, "display_name": "Summary Analysis Evidence", "description": "Packaged analysis outputs used for the closing summary beat.", "sequence_index": 80, "artifact_role_ids": [ANALYSIS_BUNDLE_METADATA_ROLE_ID, ANALYSIS_UI_PAYLOAD_ROLE_ID, ANALYSIS_OFFLINE_REPORT_ROLE_ID], "discovery_note": "The closing summary should land on packaged Milestone 12 analysis outputs rather than ad hoc slides."},
    ]


def _default_operator_control_catalog() -> list[dict[str, Any]]:
    return [
        {"operator_control_id": START_SCRIPT_CONTROL_ID, "display_name": "Start Script", "description": "Begin the scripted showcase sequence from the opening beat.", "sequence_index": 10, "requires_time_cursor": False, "requires_loaded_preset": False},
        {"operator_control_id": PAUSE_SCRIPT_CONTROL_ID, "display_name": "Pause Script", "description": "Pause the scripted sequence at a deterministic story beat or cue.", "sequence_index": 20, "requires_time_cursor": False, "requires_loaded_preset": False},
        {"operator_control_id": NEXT_STEP_CONTROL_ID, "display_name": "Next Step", "description": "Advance to the next stable showcase beat without changing the story order.", "sequence_index": 30, "requires_time_cursor": False, "requires_loaded_preset": True},
        {"operator_control_id": PREVIOUS_STEP_CONTROL_ID, "display_name": "Previous Step", "description": "Return to the previous stable showcase beat for clarification or re-export.", "sequence_index": 40, "requires_time_cursor": False, "requires_loaded_preset": True},
        {"operator_control_id": LOAD_PRESET_CONTROL_ID, "display_name": "Load Preset", "description": "Apply one saved narrative preset without inventing a new story-state identity.", "sequence_index": 50, "requires_time_cursor": False, "requires_loaded_preset": False},
        {"operator_control_id": TOGGLE_COMPARISON_CONTROL_ID, "display_name": "Toggle Comparison", "description": "Switch between allowed comparison views on the fair paired-comparison beat.", "sequence_index": 60, "requires_time_cursor": False, "requires_loaded_preset": True},
        {"operator_control_id": SCRUB_TIME_CONTROL_ID, "display_name": "Scrub Time", "description": "Scrub the shared replay cursor while preserving dashboard-session replay semantics.", "sequence_index": 70, "requires_time_cursor": True, "requires_loaded_preset": True},
        {"operator_control_id": TRIGGER_EXPORT_CONTROL_ID, "display_name": "Trigger Export", "description": "Trigger a deterministic showcase-owned export surface.", "sequence_index": 80, "requires_time_cursor": False, "requires_loaded_preset": True},
    ]


def _default_export_target_role_catalog() -> list[dict[str, Any]]:
    return [
        {"export_target_role_id": SHOWCASE_STATE_EXPORT_TARGET_ROLE_ID, "display_name": "Showcase State JSON", "description": "Machine-readable serialized showcase presentation state.", "sequence_index": 10, "target_kind": STATE_EXPORT_TARGET_KIND, "discovery_note": "This export captures showcase-owned state without duplicating upstream bundle payloads."},
        {"export_target_role_id": STORYBOARD_EXPORT_TARGET_ROLE_ID, "display_name": "Storyboard JSON", "description": "Narrative storyboard summary keyed by the stable seven-step vocabulary.", "sequence_index": 20, "target_kind": STORYBOARD_EXPORT_TARGET_KIND, "discovery_note": "Storyboard exports should cite step ids, preset ids, and evidence roles directly."},
        {"export_target_role_id": HERO_FRAME_EXPORT_TARGET_ROLE_ID, "display_name": "Hero Frame PNG", "description": "Single-frame still export for a polished story beat.", "sequence_index": 30, "target_kind": STILL_IMAGE_EXPORT_TARGET_KIND, "discovery_note": "Still-image exports remain downstream showcase-owned artifacts referenced by the export manifest."},
        {"export_target_role_id": SCRIPTED_CLIP_EXPORT_TARGET_ROLE_ID, "display_name": "Scripted Clip Frames", "description": "Frame-sequence export for one scripted replay clip.", "sequence_index": 40, "target_kind": REPLAY_EXPORT_TARGET_KIND, "discovery_note": "Clip exports should stay deterministic and traceable to the packaged showcase script payload."},
        {"export_target_role_id": REVIEW_MANIFEST_EXPORT_TARGET_ROLE_ID, "display_name": "Review Manifest JSON", "description": "Review-oriented export index that ties the highlighted story back to evidence and guardrails.", "sequence_index": 50, "target_kind": REVIEW_MANIFEST_EXPORT_TARGET_KIND, "discovery_note": "The review-manifest export must point back to package-owned evidence references rather than copied metrics."},
    ]


def _default_presentation_status_catalog() -> list[dict[str, Any]]:
    return [
        {"status_id": PRESENTATION_STATUS_PLANNED, "display_name": "Planned", "description": "The showcase beat or preset is defined but not yet ready for polished presentation.", "sequence_index": 10, "export_allowed": False},
        {"status_id": PRESENTATION_STATUS_READY, "display_name": "Ready", "description": "The beat is presentation-ready under the approved story and evidence configuration.", "sequence_index": 20, "export_allowed": True},
        {"status_id": PRESENTATION_STATUS_FALLBACK, "display_name": "Fallback", "description": "The beat is active only in its declared fallback form because the requested highlight is unavailable or unapproved.", "sequence_index": 30, "export_allowed": True},
        {"status_id": PRESENTATION_STATUS_SCIENTIFIC_REVIEW_REQUIRED, "display_name": "Scientific Review Required", "description": "The beat exists mechanically but may not be presented as approved science until Grant signs off.", "sequence_index": 40, "export_allowed": False},
        {"status_id": PRESENTATION_STATUS_BLOCKED, "display_name": "Blocked", "description": "Required evidence or compatible presentation inputs are missing, so the beat cannot be shown honestly.", "sequence_index": 50, "export_allowed": False},
    ]


def _default_artifact_hook_catalog() -> list[dict[str, Any]]:
    return [
        {"artifact_role_id": DASHBOARD_SESSION_METADATA_ROLE_ID, "display_name": "Dashboard Session Metadata", "description": "Authoritative dashboard-session discovery anchor used as the upstream showcase context surface.", "source_kind": DASHBOARD_SESSION_SOURCE_KIND, "required_contract_version": DASHBOARD_SESSION_CONTRACT_VERSION, "artifact_id": METADATA_JSON_KEY, "artifact_scope": DASHBOARD_CONTEXT_SCOPE, "discovery_note": "Use dashboard_session.v1 metadata rather than local browser state dumps to discover the upstream session."},
        {"artifact_role_id": DASHBOARD_SESSION_PAYLOAD_ROLE_ID, "display_name": "Dashboard Session Payload", "description": "Packaged dashboard-session payload used for scripted replay and pane composition.", "source_kind": DASHBOARD_SESSION_SOURCE_KIND, "required_contract_version": DASHBOARD_SESSION_CONTRACT_VERSION, "artifact_id": "session_payload", "artifact_scope": DASHBOARD_CONTEXT_SCOPE, "discovery_note": "The showcase composes with the packaged dashboard payload instead of reverse-engineering raw simulator artifacts."},
        {"artifact_role_id": DASHBOARD_SESSION_STATE_ROLE_ID, "display_name": "Dashboard Session State", "description": "Serialized dashboard-session interaction state used as the base for saved narrative presets.", "source_kind": DASHBOARD_SESSION_SOURCE_KIND, "required_contract_version": DASHBOARD_SESSION_CONTRACT_VERSION, "artifact_id": "session_state", "artifact_scope": DASHBOARD_CONTEXT_SCOPE, "discovery_note": "Saved narrative presets should patch the packaged dashboard session state rather than inventing a second state schema."},
        {"artifact_role_id": SUITE_SUMMARY_TABLE_ROLE_ID, "display_name": "Suite Summary Table", "description": "Suite-level summary table output used as supporting comparison evidence.", "source_kind": EXPERIMENT_SUITE_SOURCE_KIND, "required_contract_version": EXPERIMENT_SUITE_CONTRACT_VERSION, "artifact_id": "summary_table", "artifact_scope": SUITE_ROLLUP_SCOPE, "discovery_note": "Use experiment_suite.v1 artifact references to discover deterministic suite rollups."},
        {"artifact_role_id": SUITE_COMPARISON_PLOT_ROLE_ID, "display_name": "Suite Comparison Plot", "description": "Suite-level comparison plot used as supporting visual evidence for the polished story.", "source_kind": EXPERIMENT_SUITE_SOURCE_KIND, "required_contract_version": EXPERIMENT_SUITE_CONTRACT_VERSION, "artifact_id": "comparison_plot", "artifact_scope": SUITE_ROLLUP_SCOPE, "discovery_note": "Comparison plots remain suite-owned artifacts rather than copied showcase images."},
        {"artifact_role_id": SUITE_REVIEW_ARTIFACT_ROLE_ID, "display_name": "Suite Review Artifact", "description": "Suite-level review artifact that can capture supporting narrative decisions or reviewer notes.", "source_kind": EXPERIMENT_SUITE_SOURCE_KIND, "required_contract_version": EXPERIMENT_SUITE_CONTRACT_VERSION, "artifact_id": "review_artifact", "artifact_scope": SUITE_ROLLUP_SCOPE, "discovery_note": "Review artifacts may support the story, but they remain subordinate to the stable showcase taxonomy."},
        {"artifact_role_id": ANALYSIS_BUNDLE_METADATA_ROLE_ID, "display_name": "Analysis Bundle Metadata", "description": "Authoritative experiment-analysis bundle metadata for the summary and highlight beats.", "source_kind": EXPERIMENT_ANALYSIS_SOURCE_KIND, "required_contract_version": EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION, "artifact_id": METADATA_JSON_KEY, "artifact_scope": ANALYSIS_CONTEXT_SCOPE, "discovery_note": "Use experiment_analysis_bundle.v1 metadata to locate packaged analysis outputs."},
        {"artifact_role_id": ANALYSIS_UI_PAYLOAD_ROLE_ID, "display_name": "Analysis UI Payload", "description": "Packaged Milestone 12 analysis payload used by the fair comparison and summary beats.", "source_kind": EXPERIMENT_ANALYSIS_SOURCE_KIND, "required_contract_version": EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION, "artifact_id": "analysis_ui_payload", "artifact_scope": ANALYSIS_CONTEXT_SCOPE, "discovery_note": "The polished story should cite packaged analysis payloads instead of notebook-local summaries."},
        {"artifact_role_id": ANALYSIS_OFFLINE_REPORT_ROLE_ID, "display_name": "Analysis Offline Report", "description": "Static offline Milestone 12 report used as a bridge artifact for review.", "source_kind": EXPERIMENT_ANALYSIS_SOURCE_KIND, "required_contract_version": EXPERIMENT_ANALYSIS_BUNDLE_CONTRACT_VERSION, "artifact_id": "offline_report_index", "artifact_scope": ANALYSIS_CONTEXT_SCOPE, "discovery_note": "The analysis report remains a bridge artifact, not the source of truth for showcase identity."},
        {"artifact_role_id": VALIDATION_BUNDLE_METADATA_ROLE_ID, "display_name": "Validation Bundle Metadata", "description": "Authoritative validation bundle metadata used to discover guardrail findings.", "source_kind": VALIDATION_BUNDLE_SOURCE_KIND, "required_contract_version": VALIDATION_LADDER_CONTRACT_VERSION, "artifact_id": METADATA_JSON_KEY, "artifact_scope": VALIDATION_GUARDRAIL_SCOPE, "discovery_note": "Resolve validation evidence through metadata-backed bundle discovery."},
        {"artifact_role_id": VALIDATION_SUMMARY_ROLE_ID, "display_name": "Validation Summary", "description": "Packaged validation summary used as one guardrail input for the wave highlight beat.", "source_kind": VALIDATION_BUNDLE_SOURCE_KIND, "required_contract_version": VALIDATION_LADDER_CONTRACT_VERSION, "artifact_id": "validation_summary", "artifact_scope": VALIDATION_GUARDRAIL_SCOPE, "discovery_note": "Use validation summaries to bound claims before the highlight beat is approved."},
        {"artifact_role_id": VALIDATION_FINDINGS_ROLE_ID, "display_name": "Validation Findings", "description": "Packaged validation findings used as explicit scientific guardrails on the highlight beat.", "source_kind": VALIDATION_BUNDLE_SOURCE_KIND, "required_contract_version": VALIDATION_LADDER_CONTRACT_VERSION, "artifact_id": "validator_findings", "artifact_scope": VALIDATION_GUARDRAIL_SCOPE, "discovery_note": "Validation findings are required discovery hooks for scientifically defensible highlight approval."},
        {"artifact_role_id": VALIDATION_REVIEW_HANDOFF_ROLE_ID, "display_name": "Validation Review Handoff", "description": "Packaged reviewer handoff artifact that records remaining scientific review state.", "source_kind": VALIDATION_BUNDLE_SOURCE_KIND, "required_contract_version": VALIDATION_LADDER_CONTRACT_VERSION, "artifact_id": "review_handoff", "artifact_scope": VALIDATION_GUARDRAIL_SCOPE, "discovery_note": "The showcase may read reviewer handoff state, but it may not replace it with script-local approval flags."},
        {"artifact_role_id": NARRATIVE_PRESET_CATALOG_ROLE_ID, "display_name": "Narrative Preset Catalog", "description": "Saved narrative preset catalog owned by the showcase-session package itself.", "source_kind": SHOWCASE_SESSION_PACKAGE_SOURCE_KIND, "required_contract_version": SHOWCASE_SESSION_CONTRACT_VERSION, "artifact_id": NARRATIVE_PRESET_CATALOG_ARTIFACT_ID, "artifact_scope": NARRATIVE_PRESET_SCOPE, "discovery_note": "Saved narrative presets are showcase-owned artifacts and should remain discoverable from showcase_session.v1 metadata."},
        {"artifact_role_id": SHOWCASE_SESSION_METADATA_ROLE_ID, "display_name": "Showcase Session Metadata", "description": "Authoritative showcase-session metadata and bundle discovery anchor.", "source_kind": SHOWCASE_SESSION_PACKAGE_SOURCE_KIND, "required_contract_version": SHOWCASE_SESSION_CONTRACT_VERSION, "artifact_id": METADATA_JSON_KEY, "artifact_scope": CONTRACT_METADATA_SCOPE, "discovery_note": "Use showcase_session.v1 metadata as the single discovery anchor for the polished demo surface."},
        {"artifact_role_id": SHOWCASE_SCRIPT_PAYLOAD_ROLE_ID, "display_name": "Showcase Script Payload", "description": "Reserved scripted showcase payload that later playback tooling will own.", "source_kind": SHOWCASE_SESSION_PACKAGE_SOURCE_KIND, "required_contract_version": SHOWCASE_SESSION_CONTRACT_VERSION, "artifact_id": SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID, "artifact_scope": SCRIPT_PLAYBACK_SCOPE, "discovery_note": "Script payload identity stays library-owned even before the full playback engine lands."},
        {"artifact_role_id": SHOWCASE_PRESENTATION_STATE_ROLE_ID, "display_name": "Showcase Presentation State", "description": "Serialized showcase-owned presentation state built on top of dashboard-session state.", "source_kind": SHOWCASE_SESSION_PACKAGE_SOURCE_KIND, "required_contract_version": SHOWCASE_SESSION_CONTRACT_VERSION, "artifact_id": SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID, "artifact_scope": PRESENTATION_STATE_SCOPE, "discovery_note": "Presentation state should remain separate from upstream dashboard state while still composing with it deterministically."},
        {"artifact_role_id": SHOWCASE_EXPORT_MANIFEST_ROLE_ID, "display_name": "Showcase Export Manifest", "description": "Reserved export manifest that discovers showcase-owned visual outputs and review surfaces.", "source_kind": SHOWCASE_SESSION_PACKAGE_SOURCE_KIND, "required_contract_version": SHOWCASE_SESSION_CONTRACT_VERSION, "artifact_id": SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID, "artifact_scope": EXPORT_SURFACE_SCOPE, "discovery_note": "Downstream showcase visuals should be discoverable through one export manifest instead of scattered scripts."},
    ]


def _default_discovery_hook_catalog() -> list[dict[str, Any]]:
    return [
        {"hook_id": DASHBOARD_SESSION_DISCOVERY_HOOK_ID, "display_name": "Dashboard Session Reference", "description": "Deterministic reference from showcase metadata back to one packaged dashboard session.", "sequence_index": 10},
        {"hook_id": SUITE_COMPARISON_DISCOVERY_HOOK_ID, "display_name": "Suite Comparison Outputs", "description": "Deterministic reference to suite-level summary tables, plots, and review artifacts.", "sequence_index": 20},
        {"hook_id": ANALYSIS_BUNDLE_DISCOVERY_HOOK_ID, "display_name": "Analysis Bundle Reference", "description": "Deterministic reference to packaged Milestone 12 analysis outputs.", "sequence_index": 30},
        {"hook_id": VALIDATION_FINDINGS_DISCOVERY_HOOK_ID, "display_name": "Validation Findings Reference", "description": "Deterministic reference to packaged Milestone 13 validation findings and handoff state.", "sequence_index": 40},
        {"hook_id": NARRATIVE_PRESET_DISCOVERY_HOOK_ID, "display_name": "Narrative Preset Catalog", "description": "Deterministic reference to saved narrative presets owned by the showcase session.", "sequence_index": 50},
        {"hook_id": SHOWCASE_ARTIFACT_DISCOVERY_HOOK_ID, "display_name": "Showcase Artifact Catalog", "description": "Deterministic reference to showcase-owned script, state, and export-manifest artifacts.", "sequence_index": 60},
        {"hook_id": STABLE_STEP_ORDER_DISCOVERY_HOOK_ID, "display_name": "Stable Step Order", "description": "Deterministic reference to the frozen seven-step showcase order.", "sequence_index": 70},
        {"hook_id": HIGHLIGHT_FALLBACK_DISCOVERY_HOOK_ID, "display_name": "Highlight Fallback Path", "description": "Deterministic reference to the fallback preset and step used when the highlight is unavailable.", "sequence_index": 80},
    ]


def _normalize_showcase_ownership_boundary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("ownership_boundary must be a mapping.")
    return {
        "presentation_owner": _normalize_identifier(
            payload["presentation_owner"],
            field_name="ownership_boundary.presentation_owner",
        ),
        "presentation_responsibilities": _normalize_identifier_list(
            payload["presentation_responsibilities"],
            field_name="ownership_boundary.presentation_responsibilities",
        ),
        "scientific_owner": _normalize_identifier(
            payload["scientific_owner"],
            field_name="ownership_boundary.scientific_owner",
        ),
        "scientific_responsibilities": _normalize_identifier_list(
            payload["scientific_responsibilities"],
            field_name="ownership_boundary.scientific_responsibilities",
        ),
        "boundary_rule": _normalize_nonempty_string(
            payload["boundary_rule"],
            field_name="ownership_boundary.boundary_rule",
        ),
    }


def _normalize_scientific_guardrail_policy(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("scientific_guardrail_policy must be a mapping.")
    return {
        "presentation_owner": _normalize_identifier(
            payload["presentation_owner"],
            field_name="scientific_guardrail_policy.presentation_owner",
        ),
        "scientific_owner": _normalize_identifier(
            payload["scientific_owner"],
            field_name="scientific_guardrail_policy.scientific_owner",
        ),
        "guardrail_step_id": _normalize_step_id(payload["guardrail_step_id"]),
        "fallback_step_id": _normalize_step_id(payload["fallback_step_id"]),
        "fallback_preset_id": _normalize_preset_id(payload["fallback_preset_id"]),
        "required_evidence_role_ids": _normalize_known_value_list(
            payload["required_evidence_role_ids"],
            field_name="scientific_guardrail_policy.required_evidence_role_ids",
            supported_values=SUPPORTED_EVIDENCE_ROLE_IDS,
            allow_empty=False,
        ),
        "boundary_rule": _normalize_nonempty_string(
            payload["boundary_rule"],
            field_name="scientific_guardrail_policy.boundary_rule",
        ),
    }


def _normalize_step_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("step_catalog must be a sequence.")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError(f"step_catalog[{index}] must be a mapping.")
        normalized.append(
            {
                "step_id": _normalize_step_id(item["step_id"]),
                "display_name": _normalize_nonempty_string(item["display_name"], field_name=f"step_catalog[{index}].display_name"),
                "description": _normalize_nonempty_string(item["description"], field_name=f"step_catalog[{index}].description"),
                "sequence_index": _normalize_nonnegative_int(item["sequence_index"], field_name=f"step_catalog[{index}].sequence_index"),
                "default_preset_id": _normalize_preset_id(item["default_preset_id"]),
                "default_cue_kind_id": _normalize_cue_kind_id(item["default_cue_kind_id"]),
                "required_annotation_ids": _normalize_known_value_list(item["required_annotation_ids"], field_name=f"step_catalog[{index}].required_annotation_ids", supported_values=SUPPORTED_ANNOTATION_IDS, allow_empty=False),
                "required_evidence_role_ids": _normalize_known_value_list(item["required_evidence_role_ids"], field_name=f"step_catalog[{index}].required_evidence_role_ids", supported_values=SUPPORTED_EVIDENCE_ROLE_IDS, allow_empty=False),
                "required_operator_control_ids": _normalize_known_value_list(item["required_operator_control_ids"], field_name=f"step_catalog[{index}].required_operator_control_ids", supported_values=SUPPORTED_OPERATOR_CONTROL_IDS, allow_empty=False),
                "default_export_target_role_ids": _normalize_known_value_list(item["default_export_target_role_ids"], field_name=f"step_catalog[{index}].default_export_target_role_ids", supported_values=SUPPORTED_EXPORT_TARGET_ROLE_IDS, allow_empty=False),
                "scientific_approval_required": _normalize_boolean(item["scientific_approval_required"], field_name=f"step_catalog[{index}].scientific_approval_required"),
                "fallback_preset_id": _normalize_optional_preset_id(item.get("fallback_preset_id")),
            }
        )
    _ensure_unique_ids(normalized, key_name="step_id", field_name="step_catalog")
    return sorted(normalized, key=lambda item: _STEP_ORDER[item["step_id"]])


def _normalize_preset_catalog(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("preset_catalog must be a sequence.")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError(f"preset_catalog[{index}] must be a mapping.")
        normalized.append(
            {
                "preset_id": _normalize_preset_id(item["preset_id"]),
                "display_name": _normalize_nonempty_string(item["display_name"], field_name=f"preset_catalog[{index}].display_name"),
                "description": _normalize_nonempty_string(item["description"], field_name=f"preset_catalog[{index}].description"),
                "sequence_index": _normalize_nonnegative_int(item["sequence_index"], field_name=f"preset_catalog[{index}].sequence_index"),
                "supported_step_ids": _normalize_known_value_list(item["supported_step_ids"], field_name=f"preset_catalog[{index}].supported_step_ids", supported_values=SUPPORTED_SHOWCASE_STEP_IDS, allow_empty=False),
                "discovery_note": _normalize_nonempty_string(item["discovery_note"], field_name=f"preset_catalog[{index}].discovery_note"),
                "fallback_only": _normalize_boolean(item["fallback_only"], field_name=f"preset_catalog[{index}].fallback_only"),
            }
        )
    _ensure_unique_ids(normalized, key_name="preset_id", field_name="preset_catalog")
    return sorted(normalized, key=lambda item: _PRESET_ORDER[item["preset_id"]])


def _normalize_simple_catalog(
    payload: Any,
    *,
    field_name: str,
    id_key: str,
    normalizer,
    order: Mapping[str, int],
    extra_fields: Mapping[str, tuple[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence.")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name}[{index}] must be a mapping.")
        normalized_id = normalizer(item[id_key])
        record = {
            id_key: normalized_id,
            "display_name": _normalize_nonempty_string(item["display_name"], field_name=f"{field_name}[{index}].display_name"),
            "description": _normalize_nonempty_string(item["description"], field_name=f"{field_name}[{index}].description"),
            "sequence_index": _normalize_nonnegative_int(
                item.get("sequence_index", order[normalized_id]),
                field_name=f"{field_name}[{index}].sequence_index",
            ),
        }
        for extra_key, (kind, supported) in extra_fields.items():
            if kind == "bool":
                record[extra_key] = _normalize_boolean(item[extra_key], field_name=f"{field_name}[{index}].{extra_key}")
            elif kind == "identifier_list":
                record[extra_key] = _normalize_known_value_list(item[extra_key], field_name=f"{field_name}[{index}].{extra_key}", supported_values=supported, allow_empty=False)
            elif kind == "identifier":
                record[extra_key] = _normalize_identifier(item[extra_key], field_name=f"{field_name}[{index}].{extra_key}")
            elif kind == "target_kind":
                record[extra_key] = _normalize_export_target_kind(item[extra_key])
            elif kind == "string":
                record[extra_key] = _normalize_nonempty_string(item[extra_key], field_name=f"{field_name}[{index}].{extra_key}")
            elif kind == "artifact_scope":
                record[extra_key] = _normalize_artifact_scope(item[extra_key])
            elif kind == "source_kind":
                record[extra_key] = _normalize_source_kind(item[extra_key])
            elif kind == "contract_string":
                record[extra_key] = _normalize_nonempty_string(item[extra_key], field_name=f"{field_name}[{index}].{extra_key}")
            else:
                raise ValueError(f"Unsupported catalog field kind {kind!r}.")
        normalized.append(record)
    _ensure_unique_ids(normalized, key_name=id_key, field_name=field_name)
    return sorted(normalized, key=lambda item: order[item[id_key]])


def _normalize_artifact_hook_catalog(payload: Any) -> list[dict[str, Any]]:
    return _normalize_simple_catalog(
        payload,
        field_name="artifact_hook_catalog",
        id_key="artifact_role_id",
        normalizer=_normalize_artifact_role_id,
        order=_ARTIFACT_ROLE_ORDER,
        extra_fields={
            "source_kind": ("source_kind", None),
            "required_contract_version": ("contract_string", None),
            "artifact_id": ("identifier", None),
            "artifact_scope": ("artifact_scope", None),
            "discovery_note": ("string", None),
        },
    )


def _normalize_discovery_hook_catalog(payload: Any) -> list[dict[str, Any]]:
    return _normalize_simple_catalog(
        payload,
        field_name="discovery_hook_catalog",
        id_key="hook_id",
        normalizer=_normalize_discovery_hook_id,
        order=_DISCOVERY_HOOK_ORDER,
        extra_fields={},
    )


def build_showcase_session_contract_metadata(
    *,
    step_definitions: Sequence[Mapping[str, Any]] | None = None,
    preset_definitions: Sequence[Mapping[str, Any]] | None = None,
    cue_kind_definitions: Sequence[Mapping[str, Any]] | None = None,
    annotation_definitions: Sequence[Mapping[str, Any]] | None = None,
    evidence_role_definitions: Sequence[Mapping[str, Any]] | None = None,
    operator_control_definitions: Sequence[Mapping[str, Any]] | None = None,
    export_target_role_definitions: Sequence[Mapping[str, Any]] | None = None,
    presentation_status_definitions: Sequence[Mapping[str, Any]] | None = None,
    artifact_hook_definitions: Sequence[Mapping[str, Any]] | None = None,
    discovery_hook_definitions: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {
        "contract_version": SHOWCASE_SESSION_CONTRACT_VERSION,
        "design_note": SHOWCASE_SESSION_DESIGN_NOTE,
        "design_note_version": SHOWCASE_SESSION_DESIGN_NOTE_VERSION,
        "composed_contracts": list(COMPOSED_CONTRACTS),
        "ownership_boundary": default_showcase_session_ownership_boundary(),
        "scientific_guardrail_policy": default_showcase_scientific_guardrail_policy(),
        "presentation_invariants": list(_default_presentation_invariants()),
        "scientific_guardrail_invariants": list(_default_scientific_guardrail_invariants()),
        "step_catalog": list(step_definitions if step_definitions is not None else _default_step_catalog()),
        "preset_catalog": list(preset_definitions if preset_definitions is not None else _default_preset_catalog()),
        "cue_kind_catalog": list(cue_kind_definitions if cue_kind_definitions is not None else _default_cue_kind_catalog()),
        "annotation_catalog": list(annotation_definitions if annotation_definitions is not None else _default_annotation_catalog()),
        "evidence_role_catalog": list(evidence_role_definitions if evidence_role_definitions is not None else _default_evidence_role_catalog()),
        "operator_control_catalog": list(operator_control_definitions if operator_control_definitions is not None else _default_operator_control_catalog()),
        "export_target_role_catalog": list(export_target_role_definitions if export_target_role_definitions is not None else _default_export_target_role_catalog()),
        "presentation_status_catalog": list(presentation_status_definitions if presentation_status_definitions is not None else _default_presentation_status_catalog()),
        "artifact_hook_catalog": list(artifact_hook_definitions if artifact_hook_definitions is not None else _default_artifact_hook_catalog()),
        "discovery_hook_catalog": list(discovery_hook_definitions if discovery_hook_definitions is not None else _default_discovery_hook_catalog()),
    }
    return parse_showcase_session_contract_metadata(payload)


def parse_showcase_session_contract_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("showcase session contract metadata must be a mapping.")
    step_catalog = _normalize_step_catalog(payload["step_catalog"])
    preset_catalog = _normalize_preset_catalog(payload["preset_catalog"])
    cue_kind_catalog = _normalize_simple_catalog(
        payload["cue_kind_catalog"],
        field_name="cue_kind_catalog",
        id_key="cue_kind_id",
        normalizer=_normalize_cue_kind_id,
        order=_CUE_KIND_ORDER,
        extra_fields={},
    )
    annotation_catalog = _normalize_simple_catalog(
        payload["annotation_catalog"],
        field_name="annotation_catalog",
        id_key="annotation_id",
        normalizer=_normalize_annotation_id,
        order=_ANNOTATION_ORDER,
        extra_fields={},
    )
    evidence_role_catalog = _normalize_simple_catalog(
        payload["evidence_role_catalog"],
        field_name="evidence_role_catalog",
        id_key="evidence_role_id",
        normalizer=_normalize_evidence_role_id,
        order=_EVIDENCE_ROLE_ORDER,
        extra_fields={
            "artifact_role_ids": ("identifier_list", SUPPORTED_ARTIFACT_ROLE_IDS),
            "discovery_note": ("string", None),
        },
    )
    operator_control_catalog = _normalize_simple_catalog(
        payload["operator_control_catalog"],
        field_name="operator_control_catalog",
        id_key="operator_control_id",
        normalizer=_normalize_operator_control_id,
        order=_CONTROL_ORDER,
        extra_fields={
            "requires_time_cursor": ("bool", None),
            "requires_loaded_preset": ("bool", None),
        },
    )
    export_target_role_catalog = _normalize_simple_catalog(
        payload["export_target_role_catalog"],
        field_name="export_target_role_catalog",
        id_key="export_target_role_id",
        normalizer=_normalize_export_target_role_id,
        order=_EXPORT_TARGET_ROLE_ORDER,
        extra_fields={
            "target_kind": ("target_kind", None),
            "discovery_note": ("string", None),
        },
    )
    presentation_status_catalog = _normalize_simple_catalog(
        payload["presentation_status_catalog"],
        field_name="presentation_status_catalog",
        id_key="status_id",
        normalizer=_normalize_presentation_status,
        order=_PRESENTATION_STATUS_ORDER,
        extra_fields={"export_allowed": ("bool", None)},
    )
    artifact_hook_catalog = _normalize_artifact_hook_catalog(payload["artifact_hook_catalog"])
    discovery_hook_catalog = _normalize_discovery_hook_catalog(payload["discovery_hook_catalog"])
    _require_exact_ids([item["step_id"] for item in step_catalog], expected_ids=SUPPORTED_SHOWCASE_STEP_IDS, field_name="step_catalog")
    _require_exact_ids([item["preset_id"] for item in preset_catalog], expected_ids=SUPPORTED_PRESET_IDS, field_name="preset_catalog")
    _require_exact_ids([item["cue_kind_id"] for item in cue_kind_catalog], expected_ids=SUPPORTED_CUE_KIND_IDS, field_name="cue_kind_catalog")
    _require_exact_ids([item["annotation_id"] for item in annotation_catalog], expected_ids=SUPPORTED_ANNOTATION_IDS, field_name="annotation_catalog")
    _require_exact_ids([item["evidence_role_id"] for item in evidence_role_catalog], expected_ids=SUPPORTED_EVIDENCE_ROLE_IDS, field_name="evidence_role_catalog")
    _require_exact_ids([item["operator_control_id"] for item in operator_control_catalog], expected_ids=SUPPORTED_OPERATOR_CONTROL_IDS, field_name="operator_control_catalog")
    _require_exact_ids([item["export_target_role_id"] for item in export_target_role_catalog], expected_ids=SUPPORTED_EXPORT_TARGET_ROLE_IDS, field_name="export_target_role_catalog")
    _require_exact_ids([item["status_id"] for item in presentation_status_catalog], expected_ids=SUPPORTED_PRESENTATION_STATUSES, field_name="presentation_status_catalog")
    _require_exact_ids([item["artifact_role_id"] for item in artifact_hook_catalog], expected_ids=SUPPORTED_ARTIFACT_ROLE_IDS, field_name="artifact_hook_catalog")
    _require_exact_ids([item["hook_id"] for item in discovery_hook_catalog], expected_ids=SUPPORTED_DISCOVERY_HOOK_IDS, field_name="discovery_hook_catalog")
    return {
        "contract_version": _normalize_nonempty_string(payload["contract_version"], field_name="contract_version"),
        "design_note": _normalize_nonempty_string(payload["design_note"], field_name="design_note"),
        "design_note_version": _normalize_nonempty_string(payload["design_note_version"], field_name="design_note_version"),
        "composed_contracts": _normalize_known_string_list(payload["composed_contracts"], field_name="composed_contracts", supported_values=COMPOSED_CONTRACTS, allow_empty=False),
        "ownership_boundary": _normalize_showcase_ownership_boundary(payload["ownership_boundary"]),
        "scientific_guardrail_policy": _normalize_scientific_guardrail_policy(payload["scientific_guardrail_policy"]),
        "presentation_invariants": _normalize_nonempty_string_list(payload["presentation_invariants"], field_name="presentation_invariants"),
        "scientific_guardrail_invariants": _normalize_nonempty_string_list(payload["scientific_guardrail_invariants"], field_name="scientific_guardrail_invariants"),
        "supported_showcase_step_ids": [item["step_id"] for item in step_catalog],
        "supported_preset_ids": [item["preset_id"] for item in preset_catalog],
        "supported_cue_kind_ids": [item["cue_kind_id"] for item in cue_kind_catalog],
        "supported_annotation_ids": [item["annotation_id"] for item in annotation_catalog],
        "supported_evidence_role_ids": [item["evidence_role_id"] for item in evidence_role_catalog],
        "supported_operator_control_ids": [item["operator_control_id"] for item in operator_control_catalog],
        "supported_export_target_role_ids": [item["export_target_role_id"] for item in export_target_role_catalog],
        "supported_presentation_statuses": [item["status_id"] for item in presentation_status_catalog],
        "supported_artifact_role_ids": [item["artifact_role_id"] for item in artifact_hook_catalog],
        "supported_discovery_hook_ids": [item["hook_id"] for item in discovery_hook_catalog],
        "default_export_target_role_id": DEFAULT_EXPORT_TARGET_ROLE_ID,
        "step_catalog": step_catalog,
        "preset_catalog": preset_catalog,
        "cue_kind_catalog": cue_kind_catalog,
        "annotation_catalog": annotation_catalog,
        "evidence_role_catalog": evidence_role_catalog,
        "operator_control_catalog": operator_control_catalog,
        "export_target_role_catalog": export_target_role_catalog,
        "presentation_status_catalog": presentation_status_catalog,
        "artifact_hook_catalog": artifact_hook_catalog,
        "discovery_hook_catalog": discovery_hook_catalog,
    }


def write_showcase_session_contract_metadata(
    contract_metadata: Mapping[str, Any],
    output_path: str | Path,
) -> Path:
    return write_json(
        parse_showcase_session_contract_metadata(contract_metadata),
        Path(output_path).resolve(),
    )


def load_showcase_session_contract_metadata(metadata_path: str | Path) -> dict[str, Any]:
    with Path(metadata_path).open("r", encoding="utf-8") as handle:
        return parse_showcase_session_contract_metadata(json.load(handle))


def build_showcase_narrative_annotation(
    *,
    annotation_id: str,
    text: str,
    linked_evidence_role_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "annotation_id": _normalize_annotation_id(annotation_id),
        "text": _normalize_nonempty_string(text, field_name="text"),
        "linked_evidence_role_ids": _normalize_known_value_list(
            linked_evidence_role_ids or [],
            field_name="linked_evidence_role_ids",
            supported_values=SUPPORTED_EVIDENCE_ROLE_IDS,
            allow_empty=True,
        ),
    }


def build_showcase_evidence_reference(
    *,
    evidence_role_id: str,
    artifact_role_id: str,
    citation_label: str,
    locator: str | None = None,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "evidence_role_id": _normalize_evidence_role_id(evidence_role_id),
        "artifact_role_id": _normalize_artifact_role_id(artifact_role_id),
        "citation_label": _normalize_nonempty_string(citation_label, field_name="citation_label"),
        "locator": _normalize_optional_string(locator, field_name="locator"),
        "required": _normalize_boolean(required, field_name="required"),
    }


def build_showcase_saved_preset(
    *,
    preset_id: str,
    step_id: str,
    presentation_status: str = PRESENTATION_STATUS_READY,
    source_artifact_role_id: str = DASHBOARD_SESSION_STATE_ROLE_ID,
    presentation_state_patch: Mapping[str, Any] | None = None,
    display_name: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    normalized_preset_id = _normalize_preset_id(preset_id)
    return {
        "preset_id": normalized_preset_id,
        "step_id": _normalize_step_id(step_id),
        "presentation_status": _normalize_presentation_status(presentation_status),
        "source_artifact_role_id": _normalize_artifact_role_id(source_artifact_role_id),
        "presentation_state_patch": _normalize_json_mapping(
            presentation_state_patch or {},
            field_name="presentation_state_patch",
        ),
        "display_name": _normalize_nonempty_string(
            display_name or normalized_preset_id,
            field_name="display_name",
        ),
        "note": _normalize_optional_string(note, field_name="note"),
    }


def build_showcase_step(
    *,
    step_id: str,
    preset_id: str,
    cue_kind_id: str,
    presentation_status: str,
    narrative_annotations: Sequence[Mapping[str, Any]],
    evidence_references: Sequence[Mapping[str, Any]],
    operator_control_ids: Sequence[str],
    export_target_role_ids: Sequence[str],
    fallback_preset_id: str | None = None,
) -> dict[str, Any]:
    return {
        "step_id": _normalize_step_id(step_id),
        "preset_id": _normalize_preset_id(preset_id),
        "cue_kind_id": _normalize_cue_kind_id(cue_kind_id),
        "presentation_status": _normalize_presentation_status(presentation_status),
        "narrative_annotations": [build_showcase_narrative_annotation(**item) if "text" in item else item for item in narrative_annotations],
        "evidence_references": [build_showcase_evidence_reference(**item) if "citation_label" in item else item for item in evidence_references],
        "operator_control_ids": _normalize_known_value_list(operator_control_ids, field_name="operator_control_ids", supported_values=SUPPORTED_OPERATOR_CONTROL_IDS, allow_empty=False),
        "export_target_role_ids": _normalize_known_value_list(export_target_role_ids, field_name="export_target_role_ids", supported_values=SUPPORTED_EXPORT_TARGET_ROLE_IDS, allow_empty=False),
        "fallback_preset_id": _normalize_optional_preset_id(fallback_preset_id),
    }


def build_showcase_session_artifact_reference(
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
    return {
        "artifact_role_id": _normalize_artifact_role_id(artifact_role_id),
        "source_kind": _normalize_source_kind(source_kind),
        "path": str(Path(path).resolve()),
        "contract_version": _normalize_nonempty_string(contract_version, field_name="contract_version"),
        "bundle_id": _normalize_nonempty_string(bundle_id, field_name="bundle_id"),
        "artifact_id": _normalize_identifier(artifact_id, field_name="artifact_id"),
        "format": _normalize_optional_string(format, field_name="format"),
        "artifact_scope": _normalize_optional_artifact_scope(artifact_scope),
        "status": _normalize_asset_status(status, field_name="status"),
    }


def _normalize_narrative_annotations(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("narrative_annotations must be a sequence.")
    normalized = [build_showcase_narrative_annotation(**dict(item)) for item in payload]
    _ensure_unique_ids(normalized, key_name="annotation_id", field_name="narrative_annotations")
    return sorted(normalized, key=lambda item: _ANNOTATION_ORDER[item["annotation_id"]])


def _normalize_evidence_references(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("evidence_references must be a sequence.")
    normalized = [build_showcase_evidence_reference(**dict(item)) for item in payload]
    _ensure_unique_ids(normalized, key_name="evidence_role_id", field_name="evidence_references")
    return sorted(normalized, key=lambda item: _EVIDENCE_ROLE_ORDER[item["evidence_role_id"]])


def _normalize_saved_presets(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("saved_presets must be a sequence.")
    normalized = [build_showcase_saved_preset(**dict(item)) for item in payload]
    _ensure_unique_ids(normalized, key_name="preset_id", field_name="saved_presets")
    return sorted(normalized, key=lambda item: (_STEP_ORDER[item["step_id"]], _PRESET_ORDER[item["preset_id"]]))


def _normalize_showcase_steps(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("showcase_steps must be a sequence.")
    normalized: list[dict[str, Any]] = []
    for item in payload:
        record = dict(item)
        record["narrative_annotations"] = _normalize_narrative_annotations(record["narrative_annotations"])
        record["evidence_references"] = _normalize_evidence_references(record["evidence_references"])
        normalized.append(build_showcase_step(**record))
    _ensure_unique_ids(normalized, key_name="step_id", field_name="showcase_steps")
    return sorted(normalized, key=lambda item: _STEP_ORDER[item["step_id"]])


def _normalize_artifact_references(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("artifact_references must be a sequence.")
    normalized = [build_showcase_session_artifact_reference(**dict(item)) for item in payload]
    _ensure_unique_artifact_bindings(normalized, field_name="artifact_references")
    return sorted(
        normalized,
        key=lambda item: (
            _SOURCE_KIND_ORDER[item["source_kind"]],
            _ARTIFACT_ROLE_ORDER[item["artifact_role_id"]],
            item["path"],
        ),
    )


def build_showcase_session_spec_hash(
    *,
    experiment_id: str,
    showcase_id: str,
    display_name: str,
    presentation_status: str,
    enabled_export_target_role_ids: Sequence[str],
    artifact_references: Sequence[Mapping[str, Any]],
    saved_presets: Sequence[Mapping[str, Any]],
    showcase_steps: Sequence[Mapping[str, Any]],
) -> str:
    payload = {
        "experiment_id": _normalize_identifier(experiment_id, field_name="experiment_id"),
        "showcase_id": _normalize_identifier(showcase_id, field_name="showcase_id"),
        "display_name": _normalize_nonempty_string(display_name, field_name="display_name"),
        "presentation_status": _normalize_presentation_status(presentation_status),
        "enabled_export_target_role_ids": _normalize_known_value_list(enabled_export_target_role_ids, field_name="enabled_export_target_role_ids", supported_values=SUPPORTED_EXPORT_TARGET_ROLE_IDS, allow_empty=False),
        "artifact_references": _normalize_artifact_references(artifact_references),
        "saved_presets": _normalize_saved_presets(saved_presets),
        "showcase_steps": _normalize_showcase_steps(showcase_steps),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _artifact_record(*, path: str | Path, format: str, status: str, artifact_scope: str, description: str) -> dict[str, Any]:
    return {
        "path": str(Path(path).resolve()),
        "format": _normalize_nonempty_string(format, field_name="format"),
        "status": _normalize_asset_status(status, field_name="status"),
        "artifact_scope": _normalize_artifact_scope(artifact_scope),
        "description": _normalize_nonempty_string(description, field_name="description"),
    }


def build_showcase_session_metadata(
    *,
    experiment_id: str,
    showcase_id: str,
    display_name: str,
    artifact_references: Sequence[Mapping[str, Any]],
    saved_presets: Sequence[Mapping[str, Any]],
    showcase_steps: Sequence[Mapping[str, Any]],
    processed_simulator_results_dir: str | Path = DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
    presentation_status: str = PRESENTATION_STATUS_READY,
    enabled_export_target_role_ids: Sequence[str] | None = None,
    default_export_target_role_id: str = DEFAULT_EXPORT_TARGET_ROLE_ID,
    showcase_script_payload_status: str = ASSET_STATUS_MISSING,
    showcase_presentation_state_status: str = ASSET_STATUS_READY,
    narrative_preset_catalog_status: str = ASSET_STATUS_READY,
    showcase_export_manifest_status: str = ASSET_STATUS_MISSING,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_contract = parse_showcase_session_contract_metadata(
        contract_metadata if contract_metadata is not None else build_showcase_session_contract_metadata()
    )
    normalized_artifact_references = _normalize_artifact_references(artifact_references)
    normalized_saved_presets = _normalize_saved_presets(saved_presets)
    normalized_showcase_steps = _normalize_showcase_steps(showcase_steps)
    enabled_exports = _normalize_known_value_list(
        enabled_export_target_role_ids if enabled_export_target_role_ids is not None else normalized_contract["supported_export_target_role_ids"],
        field_name="enabled_export_target_role_ids",
        supported_values=SUPPORTED_EXPORT_TARGET_ROLE_IDS,
        allow_empty=False,
    )
    default_export = _normalize_export_target_role_id(default_export_target_role_id)
    spec_hash = build_showcase_session_spec_hash(
        experiment_id=experiment_id,
        showcase_id=showcase_id,
        display_name=display_name,
        presentation_status=presentation_status,
        enabled_export_target_role_ids=enabled_exports,
        artifact_references=normalized_artifact_references,
        saved_presets=normalized_saved_presets,
        showcase_steps=normalized_showcase_steps,
    )
    bundle_paths = build_showcase_session_bundle_paths(
        experiment_id=experiment_id,
        showcase_spec_hash=spec_hash,
        processed_simulator_results_dir=processed_simulator_results_dir,
    )
    artifacts = {
        METADATA_JSON_KEY: _artifact_record(path=bundle_paths.metadata_json_path, format="json_showcase_session_metadata.v1", status=ASSET_STATUS_READY, artifact_scope=CONTRACT_METADATA_SCOPE, description="Authoritative Milestone 16 showcase-session metadata."),
        SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID: _artifact_record(path=bundle_paths.script_payload_path, format=JSON_SHOWCASE_SCRIPT_FORMAT, status=showcase_script_payload_status, artifact_scope=SCRIPT_PLAYBACK_SCOPE, description="Reserved scripted showcase payload."),
        SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID: _artifact_record(path=bundle_paths.presentation_state_path, format=JSON_SHOWCASE_STATE_FORMAT, status=showcase_presentation_state_status, artifact_scope=PRESENTATION_STATE_SCOPE, description="Exportable serialized showcase presentation state."),
        NARRATIVE_PRESET_CATALOG_ARTIFACT_ID: _artifact_record(path=bundle_paths.preset_catalog_path, format=JSON_NARRATIVE_PRESET_CATALOG_FORMAT, status=narrative_preset_catalog_status, artifact_scope=NARRATIVE_PRESET_SCOPE, description="Saved narrative preset catalog."),
        SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID: _artifact_record(path=bundle_paths.export_manifest_path, format=JSON_SHOWCASE_EXPORT_MANIFEST_FORMAT, status=showcase_export_manifest_status, artifact_scope=EXPORT_SURFACE_SCOPE, description="Reserved showcase export-manifest discovery anchor."),
    }
    local_refs = [
        build_showcase_session_artifact_reference(artifact_role_id=SHOWCASE_SESSION_METADATA_ROLE_ID, source_kind=SHOWCASE_SESSION_PACKAGE_SOURCE_KIND, path=artifacts[METADATA_JSON_KEY]["path"], contract_version=SHOWCASE_SESSION_CONTRACT_VERSION, bundle_id=bundle_paths.bundle_id, artifact_id=METADATA_JSON_KEY, format=artifacts[METADATA_JSON_KEY]["format"], artifact_scope=artifacts[METADATA_JSON_KEY]["artifact_scope"], status=artifacts[METADATA_JSON_KEY]["status"]),
        build_showcase_session_artifact_reference(artifact_role_id=SHOWCASE_SCRIPT_PAYLOAD_ROLE_ID, source_kind=SHOWCASE_SESSION_PACKAGE_SOURCE_KIND, path=artifacts[SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID]["path"], contract_version=SHOWCASE_SESSION_CONTRACT_VERSION, bundle_id=bundle_paths.bundle_id, artifact_id=SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID, format=artifacts[SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID]["format"], artifact_scope=artifacts[SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID]["artifact_scope"], status=artifacts[SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID]["status"]),
        build_showcase_session_artifact_reference(artifact_role_id=SHOWCASE_PRESENTATION_STATE_ROLE_ID, source_kind=SHOWCASE_SESSION_PACKAGE_SOURCE_KIND, path=artifacts[SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID]["path"], contract_version=SHOWCASE_SESSION_CONTRACT_VERSION, bundle_id=bundle_paths.bundle_id, artifact_id=SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID, format=artifacts[SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID]["format"], artifact_scope=artifacts[SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID]["artifact_scope"], status=artifacts[SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID]["status"]),
        build_showcase_session_artifact_reference(artifact_role_id=NARRATIVE_PRESET_CATALOG_ROLE_ID, source_kind=SHOWCASE_SESSION_PACKAGE_SOURCE_KIND, path=artifacts[NARRATIVE_PRESET_CATALOG_ARTIFACT_ID]["path"], contract_version=SHOWCASE_SESSION_CONTRACT_VERSION, bundle_id=bundle_paths.bundle_id, artifact_id=NARRATIVE_PRESET_CATALOG_ARTIFACT_ID, format=artifacts[NARRATIVE_PRESET_CATALOG_ARTIFACT_ID]["format"], artifact_scope=artifacts[NARRATIVE_PRESET_CATALOG_ARTIFACT_ID]["artifact_scope"], status=artifacts[NARRATIVE_PRESET_CATALOG_ARTIFACT_ID]["status"]),
        build_showcase_session_artifact_reference(artifact_role_id=SHOWCASE_EXPORT_MANIFEST_ROLE_ID, source_kind=SHOWCASE_SESSION_PACKAGE_SOURCE_KIND, path=artifacts[SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID]["path"], contract_version=SHOWCASE_SESSION_CONTRACT_VERSION, bundle_id=bundle_paths.bundle_id, artifact_id=SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID, format=artifacts[SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID]["format"], artifact_scope=artifacts[SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID]["artifact_scope"], status=artifacts[SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID]["status"]),
    ]
    return parse_showcase_session_metadata(
        {
            "contract_version": SHOWCASE_SESSION_CONTRACT_VERSION,
            "design_note": SHOWCASE_SESSION_DESIGN_NOTE,
            "design_note_version": SHOWCASE_SESSION_DESIGN_NOTE_VERSION,
            "bundle_id": bundle_paths.bundle_id,
            "experiment_id": _normalize_identifier(experiment_id, field_name="experiment_id"),
            "showcase_id": _normalize_identifier(showcase_id, field_name="showcase_id"),
            "display_name": _normalize_nonempty_string(display_name, field_name="display_name"),
            "showcase_spec_hash": spec_hash,
            "showcase_spec_hash_algorithm": DEFAULT_HASH_ALGORITHM,
            "presentation_status": _normalize_presentation_status(presentation_status),
            "enabled_export_target_role_ids": enabled_exports,
            "default_export_target_role_id": default_export,
            "artifact_references": list(normalized_artifact_references) + local_refs,
            "saved_presets": normalized_saved_presets,
            "showcase_steps": normalized_showcase_steps,
            "output_root_reference": {"processed_simulator_results_dir": str(bundle_paths.processed_simulator_results_dir)},
            "bundle_layout": {"bundle_directory": str(bundle_paths.bundle_directory), "exports_directory": str(bundle_paths.exports_directory)},
            "artifacts": artifacts,
        },
        contract_metadata=normalized_contract,
    )


def parse_showcase_session_metadata(
    payload: Mapping[str, Any],
    *,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_contract = parse_showcase_session_contract_metadata(
        contract_metadata if contract_metadata is not None else build_showcase_session_contract_metadata()
    )
    normalized_artifact_references = _normalize_artifact_references(payload["artifact_references"])
    artifact_roles = {item["artifact_role_id"] for item in normalized_artifact_references}
    for role_id in REQUIRED_EXTERNAL_ARTIFACT_ROLE_IDS + REQUIRED_LOCAL_ARTIFACT_ROLE_IDS:
        if role_id not in artifact_roles:
            raise ValueError(f"showcase session metadata is missing required artifact role {role_id!r}.")
    normalized_saved_presets = _normalize_saved_presets(payload["saved_presets"])
    normalized_showcase_steps = _normalize_showcase_steps(payload["showcase_steps"])
    _require_exact_ids([item["step_id"] for item in normalized_showcase_steps], expected_ids=SUPPORTED_SHOWCASE_STEP_IDS, field_name="showcase_steps")
    return {
        "contract_version": _normalize_nonempty_string(payload["contract_version"], field_name="contract_version"),
        "design_note": _normalize_nonempty_string(payload["design_note"], field_name="design_note"),
        "design_note_version": _normalize_nonempty_string(payload["design_note_version"], field_name="design_note_version"),
        "bundle_id": _normalize_nonempty_string(payload["bundle_id"], field_name="bundle_id"),
        "experiment_id": _normalize_identifier(payload["experiment_id"], field_name="experiment_id"),
        "showcase_id": _normalize_identifier(payload["showcase_id"], field_name="showcase_id"),
        "display_name": _normalize_nonempty_string(payload["display_name"], field_name="display_name"),
        "showcase_spec_hash": _normalize_parameter_hash(payload["showcase_spec_hash"]),
        "showcase_spec_hash_algorithm": _normalize_nonempty_string(payload["showcase_spec_hash_algorithm"], field_name="showcase_spec_hash_algorithm"),
        "presentation_status": _normalize_presentation_status(payload["presentation_status"]),
        "enabled_export_target_role_ids": _normalize_known_value_list(payload["enabled_export_target_role_ids"], field_name="enabled_export_target_role_ids", supported_values=SUPPORTED_EXPORT_TARGET_ROLE_IDS, allow_empty=False),
        "default_export_target_role_id": _normalize_export_target_role_id(payload["default_export_target_role_id"]),
        "artifact_references": normalized_artifact_references,
        "saved_presets": normalized_saved_presets,
        "showcase_steps": normalized_showcase_steps,
        "output_root_reference": {"processed_simulator_results_dir": str(Path(payload["output_root_reference"]["processed_simulator_results_dir"]).resolve())},
        "bundle_layout": {"bundle_directory": str(Path(payload["bundle_layout"]["bundle_directory"]).resolve()), "exports_directory": str(Path(payload["bundle_layout"]["exports_directory"]).resolve())},
        "artifacts": copy.deepcopy(dict(payload["artifacts"])),
        "contract_metadata": normalized_contract,
    }


def write_showcase_session_metadata(
    bundle_metadata: Mapping[str, Any],
    metadata_path: str | Path | None = None,
    *,
    contract_metadata: Mapping[str, Any] | None = None,
) -> Path:
    normalized = parse_showcase_session_metadata(bundle_metadata, contract_metadata=contract_metadata)
    output_path = Path(metadata_path) if metadata_path is not None else Path(normalized["artifacts"][METADATA_JSON_KEY]["path"])
    return write_json(normalized, output_path.resolve())


def load_showcase_session_metadata(
    metadata_path: str | Path,
    *,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    with Path(metadata_path).open("r", encoding="utf-8") as handle:
        return parse_showcase_session_metadata(json.load(handle), contract_metadata=contract_metadata)


def discover_showcase_step_definitions(record: Mapping[str, Any], *, scientific_approval_required: bool | None = None) -> list[dict[str, Any]]:
    metadata = parse_showcase_session_contract_metadata(record)
    result = []
    for item in metadata["step_catalog"]:
        if scientific_approval_required is not None and item["scientific_approval_required"] != scientific_approval_required:
            continue
        result.append(copy.deepcopy(item))
    return result


def discover_showcase_preset_definitions(record: Mapping[str, Any], *, step_id: str | None = None) -> list[dict[str, Any]]:
    metadata = parse_showcase_session_contract_metadata(record)
    normalized_step_id = None if step_id is None else _normalize_step_id(step_id)
    result = []
    for item in metadata["preset_catalog"]:
        if normalized_step_id is not None and normalized_step_id not in item["supported_step_ids"]:
            continue
        result.append(copy.deepcopy(item))
    return result


def discover_showcase_export_target_roles(record: Mapping[str, Any], *, target_kind: str | None = None) -> list[dict[str, Any]]:
    metadata = parse_showcase_session_contract_metadata(record)
    normalized_target_kind = None if target_kind is None else _normalize_export_target_kind(target_kind)
    return [copy.deepcopy(item) for item in metadata["export_target_role_catalog"] if normalized_target_kind is None or item["target_kind"] == normalized_target_kind]


def discover_showcase_artifact_hooks(record: Mapping[str, Any], *, source_kind: str | None = None, artifact_scope: str | None = None) -> list[dict[str, Any]]:
    metadata = parse_showcase_session_contract_metadata(record)
    normalized_source_kind = None if source_kind is None else _normalize_source_kind(source_kind)
    normalized_artifact_scope = None if artifact_scope is None else _normalize_artifact_scope(artifact_scope)
    result = []
    for item in metadata["artifact_hook_catalog"]:
        if normalized_source_kind is not None and item["source_kind"] != normalized_source_kind:
            continue
        if normalized_artifact_scope is not None and item["artifact_scope"] != normalized_artifact_scope:
            continue
        result.append(copy.deepcopy(item))
    return result


def get_showcase_step_definition(step_id: str, *, record: Mapping[str, Any] | None = None) -> dict[str, Any]:
    metadata = build_showcase_session_contract_metadata() if record is None else parse_showcase_session_contract_metadata(record)
    normalized_step_id = _normalize_step_id(step_id)
    for item in metadata["step_catalog"]:
        if item["step_id"] == normalized_step_id:
            return copy.deepcopy(item)
    raise KeyError(f"Unknown showcase step definition {normalized_step_id!r}.")


def get_showcase_preset_definition(preset_id: str, *, record: Mapping[str, Any] | None = None) -> dict[str, Any]:
    metadata = build_showcase_session_contract_metadata() if record is None else parse_showcase_session_contract_metadata(record)
    normalized_preset_id = _normalize_preset_id(preset_id)
    for item in metadata["preset_catalog"]:
        if item["preset_id"] == normalized_preset_id:
            return copy.deepcopy(item)
    raise KeyError(f"Unknown showcase preset definition {normalized_preset_id!r}.")


def discover_showcase_steps(record: Mapping[str, Any], *, presentation_status: str | None = None, cue_kind_id: str | None = None) -> list[dict[str, Any]]:
    metadata = parse_showcase_session_metadata(record)
    normalized_status = None if presentation_status is None else _normalize_presentation_status(presentation_status)
    normalized_cue = None if cue_kind_id is None else _normalize_cue_kind_id(cue_kind_id)
    result = []
    for item in metadata["showcase_steps"]:
        if normalized_status is not None and item["presentation_status"] != normalized_status:
            continue
        if normalized_cue is not None and item["cue_kind_id"] != normalized_cue:
            continue
        result.append(copy.deepcopy(item))
    return result


def discover_showcase_saved_presets(record: Mapping[str, Any], *, step_id: str | None = None) -> list[dict[str, Any]]:
    metadata = parse_showcase_session_metadata(record)
    normalized_step_id = None if step_id is None else _normalize_step_id(step_id)
    return [copy.deepcopy(item) for item in metadata["saved_presets"] if normalized_step_id is None or item["step_id"] == normalized_step_id]


def discover_showcase_session_bundle_paths(record: Mapping[str, Any]) -> dict[str, Path]:
    metadata = parse_showcase_session_metadata(record)
    return {artifact_id: Path(artifact["path"]).resolve() for artifact_id, artifact in metadata["artifacts"].items()}


def discover_showcase_session_artifact_references(record: Mapping[str, Any], *, source_kind: str | None = None, artifact_role_id: str | None = None) -> list[dict[str, Any]]:
    metadata = parse_showcase_session_metadata(record)
    normalized_source_kind = None if source_kind is None else _normalize_source_kind(source_kind)
    normalized_artifact_role_id = None if artifact_role_id is None else _normalize_artifact_role_id(artifact_role_id)
    result = []
    for item in metadata["artifact_references"]:
        if normalized_source_kind is not None and item["source_kind"] != normalized_source_kind:
            continue
        if normalized_artifact_role_id is not None and item["artifact_role_id"] != normalized_artifact_role_id:
            continue
        result.append(copy.deepcopy(item))
    return result
