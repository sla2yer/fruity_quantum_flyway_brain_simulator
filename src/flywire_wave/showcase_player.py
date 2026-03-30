from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .dashboard_replay import build_dashboard_replay_state
from .dashboard_session_contract import (
    PLAYBACK_PAUSED,
    PLAYBACK_PLAYING,
    build_dashboard_global_interaction_state,
    build_dashboard_time_cursor,
)
from .io_utils import write_json
from .showcase_session_contract import (
    DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
    JSON_SHOWCASE_STATE_FORMAT,
    NARRATIVE_PRESET_CATALOG_ARTIFACT_ID,
    PRESENTATION_STATUS_BLOCKED,
    PRESENTATION_STATUS_SCIENTIFIC_REVIEW_REQUIRED,
    SCRUB_TIME_CONTROL_ID,
    SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID,
    SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID,
    SHOWCASE_SESSION_CONTRACT_VERSION,
    SUPPORTED_SHOWCASE_STEP_IDS,
    discover_showcase_session_artifact_references,
    discover_showcase_session_bundle_paths,
    load_showcase_session_metadata,
)
from .stimulus_contract import _normalize_identifier


SHOWCASE_PLAYER_RUNTIME_VERSION = "showcase_player_runtime.v1"

GUIDED_AUTOPLAY_MODE = "guided_autoplay"
PRESENTER_REHEARSAL_MODE = "presenter_rehearsal"
SUPPORTED_SHOWCASE_PLAYER_MODES = (
    GUIDED_AUTOPLAY_MODE,
    PRESENTER_REHEARSAL_MODE,
)

STATUS_COMMAND = "status"
PLAY_COMMAND = "play"
PAUSE_COMMAND = "pause"
RESUME_COMMAND = "resume"
SEEK_COMMAND = "seek"
NEXT_STEP_COMMAND = "next_step"
PREVIOUS_STEP_COMMAND = "previous_step"
JUMP_TO_STEP_COMMAND = "jump_to_step"
JUMP_TO_PRESET_COMMAND = "jump_to_preset"
RESET_COMMAND = "reset"

SUPPORTED_SHOWCASE_PLAYER_COMMANDS = (
    STATUS_COMMAND,
    PLAY_COMMAND,
    PAUSE_COMMAND,
    RESUME_COMMAND,
    SEEK_COMMAND,
    NEXT_STEP_COMMAND,
    PREVIOUS_STEP_COMMAND,
    JUMP_TO_STEP_COMMAND,
    JUMP_TO_PRESET_COMMAND,
    RESET_COMMAND,
)

_UNSUPPORTED_JUMP_STATUSES = {
    PRESENTATION_STATUS_BLOCKED,
    PRESENTATION_STATUS_SCIENTIFIC_REVIEW_REQUIRED,
}

_SUPPORTED_INTERACTION_PATCH_KEYS = {
    "selected_arm_pair",
    "selected_neuron_id",
    "selected_readout_id",
    "active_overlay_id",
    "comparison_mode",
    "time_cursor",
}


def build_showcase_player_context(
    *,
    showcase_session: Mapping[str, Any],
    showcase_script_payload: Mapping[str, Any],
    showcase_presentation_state: Mapping[str, Any],
    narrative_preset_catalog: Mapping[str, Any],
    dashboard_payload: Mapping[str, Any],
    showcase_session_metadata_path: str | Path | None = None,
    showcase_state_path: str | Path | None = None,
) -> dict[str, Any]:
    step_sequence = _normalize_mapping_sequence(
        showcase_script_payload.get("step_sequence", []),
        field_name="showcase_script_payload.step_sequence",
    )
    if not step_sequence:
        raise ValueError(
            "showcase_script_payload.step_sequence must contain at least one narrative step."
        )
    sequence_step_by_id = {
        str(item["step_id"]): copy.deepcopy(dict(item)) for item in step_sequence
    }
    if len(sequence_step_by_id) != len(step_sequence):
        raise ValueError("showcase_script_payload.step_sequence must not repeat step_id values.")
    session_steps = _normalize_mapping_sequence(
        showcase_session.get("showcase_steps", []),
        field_name="showcase_session.showcase_steps",
    )
    session_step_by_id = {
        str(item["step_id"]): copy.deepcopy(dict(item)) for item in session_steps
    }
    if len(session_step_by_id) != len(session_steps):
        raise ValueError("showcase_session.showcase_steps must not repeat step_id values.")
    if set(session_step_by_id) != set(sequence_step_by_id):
        raise ValueError(
            "showcase_session.showcase_steps must align exactly with "
            "showcase_script_payload.step_sequence."
        )
    step_by_id = {}
    for item in step_sequence:
        step_id = str(item["step_id"])
        merged = copy.deepcopy(dict(session_step_by_id[step_id]))
        merged.update(copy.deepcopy(dict(item)))
        step_by_id[step_id] = merged

    saved_presets = _normalize_mapping_sequence(
        narrative_preset_catalog.get("saved_presets", []),
        field_name="narrative_preset_catalog.saved_presets",
    )
    if not saved_presets:
        raise ValueError(
            "narrative_preset_catalog.saved_presets must contain at least one preset."
        )
    preset_by_id = {str(item["preset_id"]): copy.deepcopy(dict(item)) for item in saved_presets}
    if len(preset_by_id) != len(saved_presets):
        raise ValueError(
            "narrative_preset_catalog.saved_presets must not repeat preset_id values."
        )

    for step in step_sequence:
        preset_id = str(step["preset_id"])
        if preset_id not in preset_by_id:
            raise ValueError(
                f"showcase step {step['step_id']!r} references missing saved preset {preset_id!r}."
            )
        fallback_preset_id = step.get("fallback_preset_id")
        if fallback_preset_id is not None and str(fallback_preset_id) not in preset_by_id:
            raise ValueError(
                f"showcase step {step['step_id']!r} references missing fallback preset "
                f"{fallback_preset_id!r}."
            )
    artifact_reference_by_role = {
        str(item["artifact_role_id"]): copy.deepcopy(dict(item))
        for item in _normalize_mapping_sequence(
            showcase_session.get("artifact_references", []),
            field_name="showcase_session.artifact_references",
        )
    }

    base_dashboard_session_state = _require_mapping(
        showcase_presentation_state.get("base_dashboard_session_state"),
        field_name="showcase_presentation_state.base_dashboard_session_state",
        missing_message=(
            "showcase_presentation_state.base_dashboard_session_state must be present "
            "to initialize the scripted showcase player."
        ),
    )
    operator_defaults = _require_mapping(
        showcase_presentation_state.get("operator_defaults"),
        field_name="showcase_presentation_state.operator_defaults",
        missing_message=(
            "showcase_presentation_state.operator_defaults must be present to initialize "
            "the scripted showcase player."
        ),
    )
    replay_model = _require_mapping(
        dashboard_payload.get("pane_inputs", {})
        .get("time_series", {})
        .get("replay_model"),
        field_name="dashboard_session_payload.pane_inputs.time_series.replay_model",
        missing_message=(
            "Packaged dashboard payload is missing pane_inputs.time_series.replay_model, "
            "so the showcase player cannot synchronize replay state."
        ),
    )
    canonical_time_ms = list(replay_model.get("canonical_time_ms", []))
    if not canonical_time_ms:
        raise ValueError(
            "dashboard_session_payload.pane_inputs.time_series.replay_model.canonical_time_ms "
            "must contain at least one sample for scripted playback."
        )
    step_order = [str(item["step_id"]) for item in step_sequence]
    unsupported_steps = sorted(set(step_order) - set(SUPPORTED_SHOWCASE_STEP_IDS))
    if unsupported_steps:
        raise ValueError(
            f"showcase_script_payload.step_sequence contains unsupported step ids {unsupported_steps!r}."
        )
    return {
        "runtime_version": SHOWCASE_PLAYER_RUNTIME_VERSION,
        "showcase_session": copy.deepcopy(dict(showcase_session)),
        "showcase_script_payload": copy.deepcopy(dict(showcase_script_payload)),
        "showcase_presentation_state": copy.deepcopy(dict(showcase_presentation_state)),
        "narrative_preset_catalog": copy.deepcopy(dict(narrative_preset_catalog)),
        "dashboard_payload": copy.deepcopy(dict(dashboard_payload)),
        "showcase_session_metadata_path": (
            None
            if showcase_session_metadata_path is None
            else str(Path(showcase_session_metadata_path).resolve())
        ),
        "showcase_state_path": (
            None
            if showcase_state_path is None
            else str(Path(showcase_state_path).resolve())
        ),
        "step_order": step_order,
        "step_by_id": step_by_id,
        "step_index_by_id": {step_id: index for index, step_id in enumerate(step_order)},
        "preset_by_id": preset_by_id,
        "artifact_reference_by_role": artifact_reference_by_role,
        "base_dashboard_session_state": copy.deepcopy(dict(base_dashboard_session_state)),
        "operator_defaults": copy.deepcopy(dict(operator_defaults)),
        "replay_model": copy.deepcopy(dict(replay_model)),
        "canonical_time_ms": [float(value) for value in canonical_time_ms],
    }


def load_showcase_player_context(
    showcase_session_metadata_path: str | Path,
) -> dict[str, Any]:
    metadata_path = Path(showcase_session_metadata_path).resolve()
    showcase_session = load_showcase_session_metadata(metadata_path)
    bundle_paths = discover_showcase_session_bundle_paths(showcase_session)
    showcase_script_payload = _load_json_mapping(
        bundle_paths[SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID],
        field_name="showcase_script_payload",
    )
    showcase_presentation_state = _load_json_mapping(
        bundle_paths[SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID],
        field_name="showcase_presentation_state",
    )
    narrative_preset_catalog = _load_json_mapping(
        bundle_paths[NARRATIVE_PRESET_CATALOG_ARTIFACT_ID],
        field_name="narrative_preset_catalog",
    )
    dashboard_payload_path = _artifact_path_for_role(
        showcase_session,
        artifact_role_id=DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
    )
    dashboard_payload = _load_json_mapping(
        dashboard_payload_path,
        field_name="dashboard_session_payload",
    )
    return build_showcase_player_context(
        showcase_session=showcase_session,
        showcase_script_payload=showcase_script_payload,
        showcase_presentation_state=showcase_presentation_state,
        narrative_preset_catalog=narrative_preset_catalog,
        dashboard_payload=dashboard_payload,
        showcase_session_metadata_path=metadata_path,
        showcase_state_path=bundle_paths[SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID],
    )


def build_showcase_player_state(
    *,
    context: Mapping[str, Any],
    current_step_id: str | None = None,
    current_preset_id: str | None = None,
    runtime_mode: str = PRESENTER_REHEARSAL_MODE,
    playback_state: str = PLAYBACK_PAUSED,
    visited_step_ids: Sequence[str] | None = None,
    completed_step_ids: Sequence[str] | None = None,
    replay_sample_index: int | None = None,
    last_action: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_mode = _normalize_runtime_mode(runtime_mode)
    normalized_playback_state = _normalize_playback_state(playback_state)
    step_id, preset_id = _resolve_step_and_preset(
        context,
        step_id=current_step_id,
        preset_id=current_preset_id,
        command=RESET_COMMAND,
    )
    step = copy.deepcopy(dict(context["step_by_id"][step_id]))
    preset = copy.deepcopy(dict(context["preset_by_id"][preset_id]))
    step_index = int(context["step_index_by_id"][step_id])
    completed = _resolve_completed_step_ids(
        context,
        completed_step_ids=completed_step_ids,
        current_step_index=step_index,
    )
    visited = _resolve_visited_step_ids(
        context,
        visited_step_ids=visited_step_ids,
        current_step_id=step_id,
    )
    resolved_dashboard_session_state = _build_resolved_dashboard_session_state(
        context=context,
        dashboard_state_patch=preset.get("presentation_state_patch", {}).get(
            "dashboard_state_patch",
            {},
        ),
        replay_sample_index=replay_sample_index,
        playback_state=normalized_playback_state,
    )
    replay_cursor = copy.deepcopy(
        dict(resolved_dashboard_session_state["replay_state"]["time_cursor"])
    )
    replay_cursor["timebase_signature"] = str(
        resolved_dashboard_session_state["replay_state"]["timebase_signature"]
    )
    patch = _require_mapping(
        preset.get("presentation_state_patch"),
        field_name=f"saved_preset[{preset_id!r}].presentation_state_patch",
    )
    rehearsal_metadata = (
        {}
        if patch.get("rehearsal_metadata") is None
        else copy.deepcopy(dict(patch["rehearsal_metadata"]))
    )
    annotation_layout = _resolve_annotation_layout(
        step=step,
        rehearsal_metadata=rehearsal_metadata,
    )
    showcase_seed = _require_mapping(
        context.get("showcase_presentation_state"),
        field_name="context.showcase_presentation_state",
    )
    state = {
        "format_version": str(
            showcase_seed.get("format_version", JSON_SHOWCASE_STATE_FORMAT)
        ),
        "contract_version": str(
            showcase_seed.get("contract_version", SHOWCASE_SESSION_CONTRACT_VERSION)
        ),
        "plan_version": showcase_seed.get("plan_version"),
        "runtime_version": SHOWCASE_PLAYER_RUNTIME_VERSION,
        "bundle_reference": copy.deepcopy(dict(showcase_seed["bundle_reference"])),
        "manifest_reference": copy.deepcopy(dict(showcase_seed["manifest_reference"])),
        "presentation_status": str(showcase_seed["presentation_status"]),
        "available_step_ids": list(context["step_order"]),
        "available_preset_ids": sorted(context["preset_by_id"]),
        "current_step_id": step_id,
        "current_step_index": step_index,
        "current_preset_id": preset_id,
        "cue_kind_id": str(step["cue_kind_id"]),
        "fallback_preset_id": step.get("fallback_preset_id"),
        "active_pane_id": str(patch.get("active_pane_id", showcase_seed["active_pane_id"])),
        "focus_root_ids": _normalize_int_list(
            patch.get("focus_root_ids", showcase_seed.get("focus_root_ids", [])),
            field_name="focus_root_ids",
        ),
        "scene_surface": (
            None
            if patch.get("scene_surface") is None
            else copy.deepcopy(dict(patch["scene_surface"]))
        ),
        "highlight_selection": (
            None
            if patch.get("highlight_selection") is None
            else copy.deepcopy(dict(patch["highlight_selection"]))
        ),
        "rehearsal_metadata": rehearsal_metadata,
        "presentation_view": _resolve_presentation_view(rehearsal_metadata),
        "fairness_boundary": _resolve_fairness_boundary(rehearsal_metadata),
        "comparison_act": _resolve_named_story_state(
            rehearsal_metadata,
            key="comparison_act",
        ),
        "highlight_presentation": _resolve_named_story_state(
            rehearsal_metadata,
            key="highlight_presentation",
        ),
        "summary_analysis_landing": _resolve_named_story_state(
            rehearsal_metadata,
            key="summary_analysis_landing",
        ),
        "camera_choreography": _resolve_camera_choreography(rehearsal_metadata),
        "annotation_layout": annotation_layout,
        "narrative_annotations": _resolve_narrative_annotations(
            step=step,
            annotation_layout=annotation_layout,
        ),
        "evidence_hooks": _resolve_evidence_hooks(
            step=step,
            artifact_reference_by_role=context["artifact_reference_by_role"],
        ),
        "presentation_links": _resolve_presentation_links(rehearsal_metadata),
        "emphasis_state": _resolve_emphasis_state(rehearsal_metadata),
        "showcase_ui_state": _resolve_showcase_ui_state(
            rehearsal_metadata,
            runtime_mode=normalized_mode,
        ),
        "dashboard_state_source": copy.deepcopy(
            dict(showcase_seed["dashboard_state_source"])
        ),
        "base_dashboard_session_state": copy.deepcopy(
            dict(context["base_dashboard_session_state"])
        ),
        "operator_defaults": copy.deepcopy(dict(context["operator_defaults"])),
        "step_statuses": copy.deepcopy(dict(showcase_seed["step_statuses"])),
        "runtime_mode": normalized_mode,
        "sequence_state": {
            "playback_state": normalized_playback_state,
            "auto_advance": normalized_mode == GUIDED_AUTOPLAY_MODE,
            "visited_step_ids": visited,
            "completed_step_ids": completed,
            "next_step_id": _step_id_for_index(context, step_index + 1),
            "previous_step_id": _step_id_for_index(context, step_index - 1),
            "end_of_sequence": step_index == len(context["step_order"]) - 1,
            "resume_step_id": step_id,
            "resume_preset_id": preset_id,
            "last_action": (
                {"command": "initialize", "resume_label": f"{step_id}:{preset_id}"}
                if last_action is None
                else copy.deepcopy(dict(last_action))
            ),
        },
        "checkpoint": {
            "step_id": step_id,
            "preset_id": preset_id,
            "resume_label": f"{step_id}:{preset_id}",
        },
        "resolved_dashboard_session_state": resolved_dashboard_session_state,
        "replay_cursor_state": replay_cursor,
    }
    return state


def _resolve_camera_choreography(
    rehearsal_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    camera = rehearsal_metadata.get("camera_choreography")
    if isinstance(camera, Mapping):
        return copy.deepcopy(dict(camera))
    anchor = rehearsal_metadata.get("camera_anchor")
    if isinstance(anchor, Mapping):
        return {
            "anchor": copy.deepcopy(dict(anchor)),
            "transition": None,
            "linked_pane_ids": [],
            "timing": {},
        }
    return {}


def _resolve_annotation_layout(
    *,
    step: Mapping[str, Any],
    rehearsal_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    layout = rehearsal_metadata.get("annotation_layout")
    if not isinstance(layout, Mapping):
        return {}
    resolved = copy.deepcopy(dict(layout))
    placements = resolved.get("placements", [])
    if not isinstance(placements, Sequence) or isinstance(placements, (str, bytes)):
        raise ValueError("annotation_layout.placements must be a sequence.")
    valid_annotation_ids = {
        str(item["annotation_id"]) for item in step.get("narrative_annotations", [])
    }
    for placement in placements:
        if not isinstance(placement, Mapping):
            raise ValueError("annotation_layout placements must be mappings.")
        annotation_id = str(placement.get("annotation_id"))
        if annotation_id not in valid_annotation_ids:
            raise ValueError(
                f"annotation_layout references annotation_id {annotation_id!r} "
                f"outside the current step annotations {sorted(valid_annotation_ids)!r}."
            )
    return resolved


def _resolve_narrative_annotations(
    *,
    step: Mapping[str, Any],
    annotation_layout: Mapping[str, Any],
) -> list[dict[str, Any]]:
    annotations = _normalize_mapping_sequence(
        step.get("narrative_annotations", []),
        field_name="step.narrative_annotations",
    )
    placements = annotation_layout.get("placements", [])
    placement_by_id = {
        str(item["annotation_id"]): copy.deepcopy(dict(item))
        for item in placements
        if isinstance(item, Mapping)
    }
    for annotation in annotations:
        annotation["placement"] = placement_by_id.get(str(annotation["annotation_id"]))
    return annotations


def _resolve_presentation_links(
    rehearsal_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    links = rehearsal_metadata.get("presentation_links")
    if not isinstance(links, Sequence) or isinstance(links, (str, bytes)):
        return []
    return [copy.deepcopy(dict(item)) for item in links if isinstance(item, Mapping)]


def _resolve_emphasis_state(
    rehearsal_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    emphasis_state = rehearsal_metadata.get("emphasis_state")
    if not isinstance(emphasis_state, Mapping):
        return {}
    return copy.deepcopy(dict(emphasis_state))


def _resolve_showcase_ui_state(
    rehearsal_metadata: Mapping[str, Any],
    *,
    runtime_mode: str,
) -> dict[str, Any]:
    showcase_ui_state = rehearsal_metadata.get("showcase_ui_state")
    if not isinstance(showcase_ui_state, Mapping):
        return {}
    base = {
        key: copy.deepcopy(value)
        for key, value in dict(showcase_ui_state).items()
        if key != "runtime_mode_variants"
    }
    variants = showcase_ui_state.get("runtime_mode_variants", {})
    if isinstance(variants, Mapping) and isinstance(variants.get(runtime_mode), Mapping):
        base = _merge_json_objects(base, dict(variants[runtime_mode]))
    base["runtime_mode"] = str(runtime_mode)
    return base


def _resolve_presentation_view(
    rehearsal_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    presentation_view = rehearsal_metadata.get("presentation_view")
    if not isinstance(presentation_view, Mapping):
        return {}
    return copy.deepcopy(dict(presentation_view))


def _resolve_fairness_boundary(
    rehearsal_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    fairness_boundary = rehearsal_metadata.get("fairness_boundary")
    if not isinstance(fairness_boundary, Mapping):
        return {}
    return copy.deepcopy(dict(fairness_boundary))


def _resolve_named_story_state(
    rehearsal_metadata: Mapping[str, Any],
    *,
    key: str,
) -> dict[str, Any]:
    value = rehearsal_metadata.get(key)
    if not isinstance(value, Mapping):
        return {}
    return copy.deepcopy(dict(value))


def _resolve_evidence_hooks(
    *,
    step: Mapping[str, Any],
    artifact_reference_by_role: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    hooks = []
    for reference in _normalize_mapping_sequence(
        step.get("evidence_references", []),
        field_name="step.evidence_references",
    ):
        artifact_role_id = str(reference["artifact_role_id"])
        artifact = artifact_reference_by_role.get(artifact_role_id)
        resolved = copy.deepcopy(dict(reference))
        if artifact is None:
            resolved["artifact"] = None
            resolved["source_path"] = None
            resolved["source_kind"] = None
            resolved["bundle_id"] = None
            resolved["path_exists"] = False
        else:
            resolved["artifact"] = copy.deepcopy(dict(artifact))
            resolved["source_path"] = str(artifact["path"])
            resolved["source_kind"] = str(artifact["source_kind"])
            resolved["bundle_id"] = str(artifact["bundle_id"])
            resolved["path_exists"] = Path(str(artifact["path"])).resolve().exists()
        hooks.append(resolved)
    return hooks


def resolve_showcase_player_state(
    context: Mapping[str, Any],
    *,
    serialized_state: Mapping[str, Any] | None = None,
    serialized_state_path: str | Path | None = None,
    runtime_mode: str | None = None,
    current_step_id: str | None = None,
    current_preset_id: str | None = None,
) -> dict[str, Any]:
    state_payload = serialized_state
    if serialized_state_path is not None:
        state_payload = _load_json_mapping(
            serialized_state_path,
            field_name="showcase_player_state",
        )
    if state_payload is None:
        seed_state = _require_mapping(
            context.get("showcase_presentation_state"),
            field_name="context.showcase_presentation_state",
        )
        state_payload = seed_state
    sequence_state = _require_mapping(
        state_payload.get("sequence_state", {}),
        field_name="showcase_player_state.sequence_state",
        allow_empty=True,
    )
    replay_cursor_state = _require_mapping(
        state_payload.get("replay_cursor_state", {}),
        field_name="showcase_player_state.replay_cursor_state",
        allow_empty=True,
    )
    return build_showcase_player_state(
        context=context,
        current_step_id=(
            current_step_id
            if current_step_id is not None
            else (
                None
                if state_payload.get("current_step_id") is None
                else str(state_payload["current_step_id"])
            )
        ),
        current_preset_id=(
            current_preset_id
            if current_preset_id is not None
            else (
                None
                if state_payload.get("current_preset_id") is None
                else str(state_payload["current_preset_id"])
            )
        ),
        runtime_mode=(
            runtime_mode
            if runtime_mode is not None
            else str(
                state_payload.get(
                    "runtime_mode",
                    context["operator_defaults"].get("rehearsal_mode", True)
                    and PRESENTER_REHEARSAL_MODE
                    or GUIDED_AUTOPLAY_MODE,
                )
            )
        ),
        playback_state=str(
            sequence_state.get(
                "playback_state",
                replay_cursor_state.get("playback_state", PLAYBACK_PAUSED),
            )
        ),
        visited_step_ids=list(sequence_state.get("visited_step_ids", [])),
        completed_step_ids=list(sequence_state.get("completed_step_ids", [])),
        replay_sample_index=(
            None
            if replay_cursor_state.get("sample_index") is None
            else int(replay_cursor_state["sample_index"])
        ),
        last_action=(
            None
            if sequence_state.get("last_action") is None
            else dict(sequence_state["last_action"])
        ),
    )


def apply_showcase_player_command(
    context: Mapping[str, Any],
    *,
    command: str,
    state: Mapping[str, Any] | None = None,
    runtime_mode: str | None = None,
    step_id: str | None = None,
    preset_id: str | None = None,
    replay_sample_index: int | None = None,
    advance_steps: int | None = None,
    until_end: bool = False,
) -> dict[str, Any]:
    normalized_command = _normalize_player_command(command)
    normalized_state = resolve_showcase_player_state(
        context,
        serialized_state=state,
        runtime_mode=runtime_mode,
    )
    if normalized_command == STATUS_COMMAND:
        return normalized_state

    current_step_id = str(normalized_state["current_step_id"])
    current_preset_id = str(normalized_state["current_preset_id"])
    current_step_index = int(normalized_state["current_step_index"])
    current_sample_index = int(normalized_state["replay_cursor_state"]["sample_index"])
    visited = list(normalized_state["sequence_state"]["visited_step_ids"])
    runtime_mode_value = (
        str(normalized_state["runtime_mode"])
        if runtime_mode is None
        else _normalize_runtime_mode(runtime_mode)
    )

    if normalized_command == PAUSE_COMMAND:
        return build_showcase_player_state(
            context=context,
            current_step_id=current_step_id,
            current_preset_id=current_preset_id,
            runtime_mode=runtime_mode_value,
            playback_state=PLAYBACK_PAUSED,
            visited_step_ids=visited,
            completed_step_ids=normalized_state["sequence_state"]["completed_step_ids"],
            replay_sample_index=current_sample_index,
            last_action={
                "command": PAUSE_COMMAND,
                "step_id": current_step_id,
                "preset_id": current_preset_id,
            },
        )

    if normalized_command == SEEK_COMMAND:
        _require_step_supports_seek(context, current_step_id)
        if replay_sample_index is None:
            raise ValueError("seek requires replay_sample_index.")
        return build_showcase_player_state(
            context=context,
            current_step_id=current_step_id,
            current_preset_id=current_preset_id,
            runtime_mode=runtime_mode_value,
            playback_state=PLAYBACK_PAUSED,
            visited_step_ids=visited,
            completed_step_ids=normalized_state["sequence_state"]["completed_step_ids"],
            replay_sample_index=_normalize_replay_sample_index(
                context,
                replay_sample_index,
            ),
            last_action={
                "command": SEEK_COMMAND,
                "step_id": current_step_id,
                "preset_id": current_preset_id,
                "sample_index": int(replay_sample_index),
            },
        )

    if normalized_command in {PLAY_COMMAND, RESUME_COMMAND}:
        return _play_showcase_player(
            context,
            state=normalized_state,
            command=normalized_command,
            runtime_mode=runtime_mode_value,
            advance_steps=advance_steps,
            until_end=until_end,
        )

    if normalized_command == NEXT_STEP_COMMAND:
        target_step_index = min(len(context["step_order"]) - 1, current_step_index + 1)
        target_step_id = _jumpable_step_id_for_index(
            context,
            target_step_index,
            command=NEXT_STEP_COMMAND,
        )
        target_preset_id = str(context["step_by_id"][target_step_id]["preset_id"])
        return _jump_to_target(
            context,
            state=normalized_state,
            command=NEXT_STEP_COMMAND,
            target_step_id=target_step_id,
            target_preset_id=target_preset_id,
        )

    if normalized_command == PREVIOUS_STEP_COMMAND:
        target_step_index = max(0, current_step_index - 1)
        target_step_id = _jumpable_step_id_for_index(
            context,
            target_step_index,
            command=PREVIOUS_STEP_COMMAND,
        )
        target_preset_id = str(context["step_by_id"][target_step_id]["preset_id"])
        return _jump_to_target(
            context,
            state=normalized_state,
            command=PREVIOUS_STEP_COMMAND,
            target_step_id=target_step_id,
            target_preset_id=target_preset_id,
        )

    if normalized_command == JUMP_TO_STEP_COMMAND:
        if step_id is None:
            raise ValueError("jump_to_step requires step_id.")
        target_step_id = _normalize_identifier(step_id, field_name="step_id")
        target_preset_id = str(
            context["step_by_id"].get(target_step_id, {}).get("preset_id", "")
        )
        if not target_preset_id:
            raise ValueError(
                f"Unsupported step jump target {target_step_id!r}. "
                f"Supported step ids: {context['step_order']!r}."
            )
        return _jump_to_target(
            context,
            state=normalized_state,
            command=JUMP_TO_STEP_COMMAND,
            target_step_id=target_step_id,
            target_preset_id=target_preset_id,
        )

    if normalized_command == JUMP_TO_PRESET_COMMAND:
        if preset_id is None:
            raise ValueError("jump_to_preset requires preset_id.")
        normalized_preset_id = _normalize_identifier(preset_id, field_name="preset_id")
        preset_record = context["preset_by_id"].get(normalized_preset_id)
        if preset_record is None:
            raise ValueError(
                f"Unsupported preset jump target {normalized_preset_id!r}. "
                f"Supported preset ids: {sorted(context['preset_by_id'])!r}."
            )
        return _jump_to_target(
            context,
            state=normalized_state,
            command=JUMP_TO_PRESET_COMMAND,
            target_step_id=str(preset_record["step_id"]),
            target_preset_id=normalized_preset_id,
        )

    if normalized_command == RESET_COMMAND:
        target_step_id, target_preset_id = _resolve_step_and_preset(
            context,
            step_id=step_id,
            preset_id=preset_id,
            command=RESET_COMMAND,
        )
        return build_showcase_player_state(
            context=context,
            current_step_id=target_step_id,
            current_preset_id=target_preset_id,
            runtime_mode=runtime_mode_value,
            playback_state=PLAYBACK_PAUSED,
            visited_step_ids=[target_step_id],
            completed_step_ids=[],
            last_action={
                "command": RESET_COMMAND,
                "step_id": target_step_id,
                "preset_id": target_preset_id,
            },
        )

    raise ValueError(
        f"Unsupported showcase player command {normalized_command!r}. "
        f"Supported commands: {SUPPORTED_SHOWCASE_PLAYER_COMMANDS!r}."
    )


def execute_showcase_player_command(
    *,
    showcase_session_metadata_path: str | Path,
    command: str,
    serialized_state_path: str | Path | None = None,
    state_output_path: str | Path | None = None,
    runtime_mode: str | None = None,
    step_id: str | None = None,
    preset_id: str | None = None,
    replay_sample_index: int | None = None,
    advance_steps: int | None = None,
    until_end: bool = False,
) -> dict[str, Any]:
    context = load_showcase_player_context(showcase_session_metadata_path)
    normalized_command = _normalize_player_command(command)
    state_payload = None
    if serialized_state_path is not None:
        state_payload = _load_json_mapping(
            serialized_state_path,
            field_name="showcase_player_state",
        )
    updated_state = apply_showcase_player_command(
        context,
        command=normalized_command,
        state=state_payload,
        runtime_mode=runtime_mode,
        step_id=step_id,
        preset_id=preset_id,
        replay_sample_index=replay_sample_index,
        advance_steps=advance_steps,
        until_end=until_end,
    )
    output_path = None
    state_written = False
    if (
        normalized_command != STATUS_COMMAND
        or serialized_state_path is not None
        or state_output_path is not None
    ):
        output_path = (
            Path(state_output_path).resolve()
            if state_output_path is not None
            else (
                Path(serialized_state_path).resolve()
                if serialized_state_path is not None
                else _default_showcase_state_path(context)
            )
        )
        write_showcase_player_state(updated_state, output_path)
        state_written = True
    return {
        "command": normalized_command,
        "metadata_path": str(Path(showcase_session_metadata_path).resolve()),
        "state_path": (
            str(output_path)
            if output_path is not None
            else str(_default_showcase_state_path(context))
        ),
        "state_written": state_written,
        "current_step_id": str(updated_state["current_step_id"]),
        "current_preset_id": str(updated_state["current_preset_id"]),
        "runtime_mode": str(updated_state["runtime_mode"]),
        "cue_kind_id": str(updated_state["cue_kind_id"]),
        "playback_state": str(updated_state["sequence_state"]["playback_state"]),
        "sample_index": int(updated_state["replay_cursor_state"]["sample_index"]),
        "time_ms": float(updated_state["replay_cursor_state"]["time_ms"]),
        "camera_anchor_id": updated_state.get("camera_choreography", {})
        .get("anchor", {})
        .get("anchor_id"),
        "showcase_ui_mode_id": updated_state.get("showcase_ui_state", {}).get("mode_id"),
        "presentation_view_kind": updated_state.get("presentation_view", {}).get(
            "view_kind"
        ),
        "content_scope_label": updated_state.get("presentation_view", {}).get(
            "content_scope_label",
            updated_state.get("presentation_view", {}).get("active_scope_label"),
        ),
        "evidence_hook_count": len(updated_state.get("evidence_hooks", [])),
        "next_step_id": updated_state["sequence_state"]["next_step_id"],
        "previous_step_id": updated_state["sequence_state"]["previous_step_id"],
        "resume_label": str(updated_state["checkpoint"]["resume_label"]),
        "visited_step_ids": list(updated_state["sequence_state"]["visited_step_ids"]),
        "completed_step_ids": list(
            updated_state["sequence_state"]["completed_step_ids"]
        ),
    }


def write_showcase_player_state(
    state: Mapping[str, Any],
    path: str | Path,
) -> Path:
    return write_json(copy.deepcopy(dict(state)), path)


def _play_showcase_player(
    context: Mapping[str, Any],
    *,
    state: Mapping[str, Any],
    command: str,
    runtime_mode: str,
    advance_steps: int | None,
    until_end: bool,
) -> dict[str, Any]:
    current_step_index = int(state["current_step_index"])
    current_step_id = str(state["current_step_id"])
    current_preset_id = str(state["current_preset_id"])
    current_sample_index = int(state["replay_cursor_state"]["sample_index"])
    target_step_index = current_step_index
    auto_advance = runtime_mode == GUIDED_AUTOPLAY_MODE
    if until_end:
        target_step_index = len(context["step_order"]) - 1
    elif advance_steps is not None:
        target_step_index = min(
            len(context["step_order"]) - 1,
            current_step_index + _normalize_nonnegative_int(
                advance_steps,
                field_name="advance_steps",
            ),
        )
    elif auto_advance and current_step_index < len(context["step_order"]) - 1:
        target_step_index = current_step_index + 1

    target_step_id = _jumpable_step_id_for_index(
        context,
        target_step_index,
        command=command,
    )
    target_preset_id = (
        current_preset_id
        if target_step_index == current_step_index
        else str(context["step_by_id"][target_step_id]["preset_id"])
    )
    playback_state = (
        PLAYBACK_PAUSED
        if target_step_index == len(context["step_order"]) - 1 and target_step_index != current_step_index
        else PLAYBACK_PLAYING
    )
    visited = list(state["sequence_state"]["visited_step_ids"])
    if target_step_index > current_step_index:
        for step_position in range(current_step_index + 1, target_step_index + 1):
            step_value = str(context["step_order"][step_position])
            if step_value not in visited:
                visited.append(step_value)
    elif target_step_id not in visited:
        visited.append(target_step_id)

    return build_showcase_player_state(
        context=context,
        current_step_id=target_step_id,
        current_preset_id=target_preset_id,
        runtime_mode=runtime_mode,
        playback_state=playback_state,
        visited_step_ids=visited,
        completed_step_ids=context["step_order"][:target_step_index],
        replay_sample_index=(
            current_sample_index if target_step_index == current_step_index else None
        ),
        last_action={
            "command": command,
            "step_id": target_step_id,
            "preset_id": target_preset_id,
            "advanced_step_count": max(0, target_step_index - current_step_index),
            "until_end": bool(until_end),
            "runtime_mode": runtime_mode,
        },
    )


def _jump_to_target(
    context: Mapping[str, Any],
    *,
    state: Mapping[str, Any],
    command: str,
    target_step_id: str,
    target_preset_id: str,
) -> dict[str, Any]:
    _require_jumpable_step(context, target_step_id, command=command)
    current_step_index = int(state["current_step_index"])
    target_step_index = int(context["step_index_by_id"][target_step_id])
    visited = list(state["sequence_state"]["visited_step_ids"])
    if target_step_id not in visited:
        visited.append(target_step_id)
    return build_showcase_player_state(
        context=context,
        current_step_id=target_step_id,
        current_preset_id=target_preset_id,
        runtime_mode=str(state["runtime_mode"]),
        playback_state=PLAYBACK_PAUSED,
        visited_step_ids=visited,
        completed_step_ids=context["step_order"][:target_step_index],
        last_action={
            "command": command,
            "step_id": target_step_id,
            "preset_id": target_preset_id,
            "skipped_step_count": abs(target_step_index - current_step_index),
        },
    )


def _build_resolved_dashboard_session_state(
    *,
    context: Mapping[str, Any],
    dashboard_state_patch: Mapping[str, Any] | None,
    replay_sample_index: int | None,
    playback_state: str,
) -> dict[str, Any]:
    base_state = copy.deepcopy(dict(context["base_dashboard_session_state"]))
    patch = _require_mapping(
        dashboard_state_patch or {},
        field_name="dashboard_state_patch",
        allow_empty=True,
    )
    merged_global_patch = _merge_interaction_patches(
        patch.get("global_interaction_state"),
        patch.get("replay_state"),
    )
    base_global_state = _require_mapping(
        base_state.get("global_interaction_state"),
        field_name="base_dashboard_session_state.global_interaction_state",
    )
    selected_arm_pair = copy.deepcopy(dict(base_global_state["selected_arm_pair"]))
    if "selected_arm_pair" in merged_global_patch:
        selected_arm_pair.update(
            copy.deepcopy(dict(merged_global_patch["selected_arm_pair"]))
        )
    current_time_cursor = copy.deepcopy(dict(base_global_state["time_cursor"]))
    if "time_cursor" in merged_global_patch:
        current_time_cursor.update(copy.deepcopy(dict(merged_global_patch["time_cursor"])))
    sample_index = (
        int(current_time_cursor["sample_index"])
        if replay_sample_index is None
        else _normalize_replay_sample_index(context, replay_sample_index)
    )
    canonical_time_ms = context["canonical_time_ms"]
    time_cursor = build_dashboard_time_cursor(
        time_ms=float(canonical_time_ms[sample_index]),
        sample_index=sample_index,
        playback_state=playback_state,
    )
    global_interaction_state = build_dashboard_global_interaction_state(
        selected_arm_pair=selected_arm_pair,
        selected_neuron_id=merged_global_patch.get(
            "selected_neuron_id",
            base_global_state.get("selected_neuron_id"),
        ),
        selected_readout_id=merged_global_patch.get(
            "selected_readout_id",
            base_global_state.get("selected_readout_id"),
        ),
        active_overlay_id=merged_global_patch.get(
            "active_overlay_id",
            base_global_state.get("active_overlay_id"),
        ),
        comparison_mode=merged_global_patch.get(
            "comparison_mode",
            base_global_state.get("comparison_mode"),
        ),
        time_cursor=time_cursor,
    )
    base_state["global_interaction_state"] = global_interaction_state
    base_state["replay_state"] = build_dashboard_replay_state(
        global_interaction_state=global_interaction_state,
        replay_model=context["replay_model"],
    )
    return base_state


def _artifact_path_for_role(
    showcase_session: Mapping[str, Any],
    *,
    artifact_role_id: str,
) -> Path:
    matches = discover_showcase_session_artifact_references(
        showcase_session,
        artifact_role_id=artifact_role_id,
    )
    if not matches:
        raise ValueError(
            f"Showcase session is missing required artifact reference {artifact_role_id!r}."
        )
    if len(matches) > 1:
        raise ValueError(
            f"Showcase session exposes multiple artifact references for {artifact_role_id!r}; "
            "the scripted player requires one deterministic path."
        )
    return Path(matches[0]["path"]).resolve()


def _default_showcase_state_path(context: Mapping[str, Any]) -> Path:
    configured = context.get("showcase_state_path")
    if configured is None:
        raise ValueError("Showcase player context is missing showcase_state_path.")
    return Path(str(configured)).resolve()


def _step_id_for_index(context: Mapping[str, Any], index: int) -> str | None:
    if index < 0 or index >= len(context["step_order"]):
        return None
    return str(context["step_order"][index])


def _jumpable_step_id_for_index(
    context: Mapping[str, Any],
    index: int,
    *,
    command: str,
) -> str:
    step_id = _step_id_for_index(context, index)
    if step_id is None:
        raise ValueError(
            f"Command {command!r} cannot resolve a step at position {index}."
        )
    _require_jumpable_step(context, step_id, command=command)
    return step_id


def _require_jumpable_step(
    context: Mapping[str, Any],
    step_id: str,
    *,
    command: str,
) -> None:
    normalized_step_id = _normalize_identifier(step_id, field_name="step_id")
    step = context["step_by_id"].get(normalized_step_id)
    if step is None:
        raise ValueError(
            f"Unsupported step jump target {normalized_step_id!r}. "
            f"Supported step ids: {context['step_order']!r}."
        )
    if str(step["presentation_status"]) in _UNSUPPORTED_JUMP_STATUSES:
        raise ValueError(
            f"Command {command!r} cannot jump to step {normalized_step_id!r} because its "
            f"presentation_status is {step['presentation_status']!r}."
        )


def _require_step_supports_seek(
    context: Mapping[str, Any],
    step_id: str,
) -> None:
    step = context["step_by_id"][step_id]
    if SCRUB_TIME_CONTROL_ID not in step["operator_control_ids"]:
        raise ValueError(
            f"Step {step_id!r} does not support seek; choose one of the replay beats "
            "that exposes the scrub_time operator control."
        )


def _resolve_step_and_preset(
    context: Mapping[str, Any],
    *,
    step_id: str | None,
    preset_id: str | None,
    command: str,
) -> tuple[str, str]:
    operator_defaults = context["operator_defaults"]
    normalized_step_id = (
        None
        if step_id is None
        else _normalize_identifier(step_id, field_name="step_id")
    )
    normalized_preset_id = (
        None
        if preset_id is None
        else _normalize_identifier(preset_id, field_name="preset_id")
    )
    if normalized_step_id is None and normalized_preset_id is None:
        normalized_step_id = str(operator_defaults["current_step_id"])
        normalized_preset_id = str(operator_defaults["current_preset_id"])
    elif normalized_step_id is None:
        preset = context["preset_by_id"].get(normalized_preset_id)
        if preset is None:
            raise ValueError(
                f"Unsupported preset jump target {normalized_preset_id!r}. "
                f"Supported preset ids: {sorted(context['preset_by_id'])!r}."
            )
        normalized_step_id = str(preset["step_id"])
    elif normalized_preset_id is None:
        step = context["step_by_id"].get(normalized_step_id)
        if step is None:
            raise ValueError(
                f"Unsupported step jump target {normalized_step_id!r}. "
                f"Supported step ids: {context['step_order']!r}."
            )
        normalized_preset_id = str(step["preset_id"])

    step = context["step_by_id"].get(normalized_step_id)
    if step is None:
        raise ValueError(
            f"Unsupported step jump target {normalized_step_id!r}. "
            f"Supported step ids: {context['step_order']!r}."
        )
    preset = context["preset_by_id"].get(normalized_preset_id)
    if preset is None:
        raise ValueError(
            f"Unsupported preset jump target {normalized_preset_id!r}. "
            f"Supported preset ids: {sorted(context['preset_by_id'])!r}."
        )
    if str(preset["step_id"]) != normalized_step_id:
        raise ValueError(
            f"Command {command!r} cannot combine step {normalized_step_id!r} with preset "
            f"{normalized_preset_id!r}; that preset belongs to step {preset['step_id']!r}."
        )
    return normalized_step_id, normalized_preset_id


def _merge_interaction_patches(
    global_patch: Any,
    replay_patch: Any,
) -> dict[str, Any]:
    left = _require_mapping(
        global_patch or {},
        field_name="dashboard_state_patch.global_interaction_state",
        allow_empty=True,
    )
    right = _require_mapping(
        replay_patch or {},
        field_name="dashboard_state_patch.replay_state",
        allow_empty=True,
    )
    unsupported = (set(left) | set(right)) - _SUPPORTED_INTERACTION_PATCH_KEYS
    if unsupported:
        raise ValueError(
            "dashboard_state_patch may only modify "
            f"{sorted(_SUPPORTED_INTERACTION_PATCH_KEYS)!r}; got {sorted(unsupported)!r}."
        )
    merged: dict[str, Any] = {}
    for key in sorted(set(left) | set(right)):
        left_value = left.get(key)
        right_value = right.get(key)
        if left_value is None:
            merged[key] = copy.deepcopy(right_value)
            continue
        if right_value is None:
            merged[key] = copy.deepcopy(left_value)
            continue
        if isinstance(left_value, Mapping) and isinstance(right_value, Mapping):
            merged[key] = _merge_mapping_values(
                left_value,
                right_value,
                field_name=f"dashboard_state_patch.{key}",
            )
            continue
        if left_value != right_value:
            raise ValueError(
                "dashboard_state_patch.global_interaction_state and "
                f"dashboard_state_patch.replay_state disagree on {key!r}: "
                f"{left_value!r} != {right_value!r}."
            )
        merged[key] = copy.deepcopy(left_value)
    return merged


def _merge_mapping_values(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    field_name: str,
) -> dict[str, Any]:
    merged = copy.deepcopy(dict(left))
    for key, value in right.items():
        if key in merged and merged[key] != value:
            raise ValueError(
                f"{field_name} disagrees on nested field {key!r}: {merged[key]!r} != {value!r}."
            )
        merged[key] = copy.deepcopy(value)
    return merged


def _merge_json_objects(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, Any]:
    merged = copy.deepcopy(dict(left))
    for key, value in right.items():
        if isinstance(merged.get(key), Mapping) and isinstance(value, Mapping):
            merged[str(key)] = _merge_json_objects(
                copy.deepcopy(dict(merged[str(key)])),
                dict(value),
            )
            continue
        merged[str(key)] = copy.deepcopy(value)
    return merged


def _resolve_completed_step_ids(
    context: Mapping[str, Any],
    *,
    completed_step_ids: Sequence[str] | None,
    current_step_index: int,
) -> list[str]:
    if completed_step_ids is None:
        return list(context["step_order"][:current_step_index])
    normalized = _normalize_step_id_sequence(
        completed_step_ids,
        field_name="completed_step_ids",
    )
    allowed = set(context["step_order"][:current_step_index])
    filtered = [step_id for step_id in normalized if step_id in allowed]
    return filtered


def _resolve_visited_step_ids(
    context: Mapping[str, Any],
    *,
    visited_step_ids: Sequence[str] | None,
    current_step_id: str,
) -> list[str]:
    normalized = (
        [current_step_id]
        if visited_step_ids is None
        else _normalize_step_id_sequence(
            visited_step_ids,
            field_name="visited_step_ids",
        )
    )
    if current_step_id not in normalized:
        normalized.append(current_step_id)
    return normalized


def _normalize_step_id_sequence(
    payload: Sequence[Any],
    *,
    field_name: str,
) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence.")
    result: list[str] = []
    for index, raw_value in enumerate(payload):
        step_id = _normalize_identifier(raw_value, field_name=f"{field_name}[{index}]")
        if step_id not in SUPPORTED_SHOWCASE_STEP_IDS:
            raise ValueError(
                f"{field_name}[{index}]={step_id!r} is not a supported showcase step id."
            )
        if step_id not in result:
            result.append(step_id)
    return result


def _normalize_runtime_mode(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="runtime_mode")
    if normalized not in SUPPORTED_SHOWCASE_PLAYER_MODES:
        raise ValueError(
            f"runtime_mode must be one of {SUPPORTED_SHOWCASE_PLAYER_MODES!r}."
        )
    return normalized


def _normalize_player_command(value: Any) -> str:
    normalized = _normalize_identifier(
        str(value).replace("-", "_"),
        field_name="command",
    )
    if normalized not in SUPPORTED_SHOWCASE_PLAYER_COMMANDS:
        raise ValueError(
            f"command must be one of {SUPPORTED_SHOWCASE_PLAYER_COMMANDS!r}."
        )
    return normalized


def _normalize_playback_state(value: Any) -> str:
    normalized = str(value)
    if normalized not in {PLAYBACK_PAUSED, PLAYBACK_PLAYING}:
        raise ValueError(
            f"playback_state must be one of {(PLAYBACK_PAUSED, PLAYBACK_PLAYING)!r}."
        )
    return normalized


def _normalize_replay_sample_index(context: Mapping[str, Any], value: Any) -> int:
    sample_index = _normalize_nonnegative_int(value, field_name="replay_sample_index")
    if sample_index >= len(context["canonical_time_ms"]):
        raise ValueError(
            "replay_sample_index must fit within the packaged dashboard shared timebase; "
            f"got {sample_index}, max {len(context['canonical_time_ms']) - 1}."
        )
    return sample_index


def _normalize_nonnegative_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a non-negative integer.")
    if isinstance(value, int):
        normalized = value
    elif isinstance(value, float) and float(value).is_integer():
        normalized = int(value)
    else:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    if normalized < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    return normalized


def _normalize_int_list(payload: Any, *, field_name: str) -> list[int]:
    if payload is None:
        return []
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of integers.")
    return [int(value) for value in payload]


def _normalize_mapping_sequence(payload: Any, *, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of mappings.")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name}[{index}] must be a mapping.")
        result.append(copy.deepcopy(dict(item)))
    return result


def _load_json_mapping(path: str | Path, *, field_name: str) -> dict[str, Any]:
    resolved_path = Path(path).resolve()
    if not resolved_path.exists():
        raise ValueError(f"{field_name} path {resolved_path} does not exist.")
    with resolved_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} at {resolved_path} must deserialize to a mapping.")
    return copy.deepcopy(dict(payload))


def _require_mapping(
    value: Any,
    *,
    field_name: str,
    allow_empty: bool = False,
    missing_message: str | None = None,
) -> dict[str, Any]:
    if value is None:
        raise ValueError(missing_message or f"{field_name} must be a mapping.")
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    if not allow_empty and not value:
        raise ValueError(missing_message or f"{field_name} must not be empty.")
    return copy.deepcopy(dict(value))
