from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .dashboard_session_contract import (
    SESSION_STATE_ARTIFACT_ID,
    discover_dashboard_session_bundle_paths,
)
from .dashboard_session_planning import package_dashboard_session
from .io_utils import write_json
from .showcase_player import (
    GUIDED_AUTOPLAY_MODE,
    PRESENTER_REHEARSAL_MODE,
    SHOWCASE_PLAYER_RUNTIME_VERSION,
    SUPPORTED_SHOWCASE_PLAYER_COMMANDS,
    SUPPORTED_SHOWCASE_PLAYER_MODES,
    build_showcase_player_context,
    build_showcase_player_state,
)
from .showcase_session_contract import (
    ACTIVE_VISUAL_SUBSET_STEP_ID,
    ACTIVITY_PROPAGATION_STEP_ID,
    APPROVED_WAVE_HIGHLIGHT_STEP_ID,
    DASHBOARD_SESSION_METADATA_ROLE_ID,
    DASHBOARD_SESSION_STATE_ROLE_ID,
    HERO_FRAME_EXPORT_TARGET_ROLE_ID,
    JSON_NARRATIVE_PRESET_CATALOG_FORMAT,
    JSON_SHOWCASE_EXPORT_MANIFEST_FORMAT,
    JSON_SHOWCASE_SCRIPT_FORMAT,
    JSON_SHOWCASE_STATE_FORMAT,
    METADATA_JSON_KEY,
    NARRATIVE_PRESET_CATALOG_ARTIFACT_ID,
    PRESENTATION_STATUS_BLOCKED,
    PRESENTATION_STATUS_PLANNED,
    PRESENTATION_STATUS_SCIENTIFIC_REVIEW_REQUIRED,
    SCRUB_TIME_CONTROL_ID,
    SCENE_CONTEXT_PRESET_ID,
    SCENE_SELECTION_STEP_ID,
    SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID,
    SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID,
    SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID,
    SHOWCASE_SESSION_CONTRACT_VERSION,
    STORYBOARD_EXPORT_TARGET_ROLE_ID,
    SUMMARY_ANALYSIS_STEP_ID,
    build_showcase_session_metadata,
    discover_showcase_export_target_roles,
    discover_showcase_session_bundle_paths,
    write_showcase_session_metadata,
)


DEFAULT_NARRATIVE_PRESET_LIBRARY_ID = "milestone16_rehearsal_preset_library.v1"

DEFAULT_ACTIVE_PANE_BY_STEP = {
    SCENE_SELECTION_STEP_ID: "scene",
    "fly_view_input": "scene",
    ACTIVE_VISUAL_SUBSET_STEP_ID: "circuit",
    ACTIVITY_PROPAGATION_STEP_ID: "time_series",
    "baseline_wave_comparison": "analysis",
    APPROVED_WAVE_HIGHLIGHT_STEP_ID: "analysis",
    SUMMARY_ANALYSIS_STEP_ID: "analysis",
}

DEFAULT_EXPORT_FILE_NAMES = {
    "showcase_state_json": "showcase_state_export.json",
    STORYBOARD_EXPORT_TARGET_ROLE_ID: "storyboard.json",
    HERO_FRAME_EXPORT_TARGET_ROLE_ID: "hero_frame.png",
    "scripted_clip_frames": "scripted_clip_frames",
    "review_manifest_json": "review_manifest.json",
}


def assemble_showcase_session_outputs(
    *,
    showcase_session: Mapping[str, Any],
    dashboard_context: Mapping[str, Any],
    narrative_context: Mapping[str, Any],
    showcase_steps: Sequence[Mapping[str, Any]],
    saved_presets: Sequence[Mapping[str, Any]],
    showcase_fixture: Mapping[str, Any],
    contract_metadata: Mapping[str, Any],
    plan_version: str,
) -> dict[str, Any]:
    output_locations = _build_output_locations(
        showcase_session=showcase_session,
        contract_metadata=contract_metadata,
    )
    operator_defaults = _build_operator_defaults(
        showcase_steps=showcase_steps,
        dashboard_context=dashboard_context,
        showcase_session=showcase_session,
    )
    showcase_presentation_state_seed = _build_showcase_presentation_state(
        showcase_session=showcase_session,
        dashboard_context=dashboard_context,
        showcase_steps=showcase_steps,
        operator_defaults=operator_defaults,
        plan_version=plan_version,
    )
    showcase_script_payload = _build_showcase_script_payload(
        showcase_session=showcase_session,
        showcase_steps=showcase_steps,
        saved_presets=saved_presets,
        operator_defaults=operator_defaults,
        plan_version=plan_version,
    )
    narrative_preset_catalog = _build_narrative_preset_catalog(
        showcase_session=showcase_session,
        dashboard_context=dashboard_context,
        showcase_fixture=showcase_fixture,
        narrative_context=narrative_context,
        showcase_steps=showcase_steps,
        saved_presets=saved_presets,
    )
    showcase_player_context = build_showcase_player_context(
        showcase_session=showcase_session,
        showcase_script_payload=showcase_script_payload,
        showcase_presentation_state=showcase_presentation_state_seed,
        narrative_preset_catalog=narrative_preset_catalog,
        dashboard_payload=dashboard_context["payload"],
    )
    showcase_presentation_state = build_showcase_player_state(
        context=showcase_player_context,
        current_step_id=str(operator_defaults["current_step_id"]),
        current_preset_id=str(operator_defaults["current_preset_id"]),
        runtime_mode=_initial_showcase_runtime_mode(operator_defaults),
        visited_step_ids=[str(operator_defaults["current_step_id"])],
        completed_step_ids=[],
    )
    showcase_export_manifest = _build_showcase_export_manifest(
        showcase_session=showcase_session,
        output_locations=output_locations,
        contract_metadata=contract_metadata,
    )
    return {
        "operator_defaults": copy.deepcopy(dict(operator_defaults)),
        "output_locations": copy.deepcopy(dict(output_locations)),
        "showcase_presentation_state": copy.deepcopy(dict(showcase_presentation_state)),
        "showcase_script_payload": copy.deepcopy(dict(showcase_script_payload)),
        "narrative_preset_catalog": copy.deepcopy(dict(narrative_preset_catalog)),
        "showcase_export_manifest": copy.deepcopy(dict(showcase_export_manifest)),
    }


def package_showcase_session_plan(
    plan: Mapping[str, Any],
    *,
    plan_version: str,
) -> dict[str, Any]:
    normalized_plan = _require_mapping(plan, field_name="plan")
    if str(normalized_plan.get("plan_version")) != plan_version:
        raise ValueError(f"plan.plan_version must be {plan_version!r}.")

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

    upstream_dashboard_metadata_path = None
    for artifact_reference in showcase_session["artifact_references"]:
        if str(artifact_reference["artifact_role_id"]) == DASHBOARD_SESSION_METADATA_ROLE_ID:
            upstream_dashboard_metadata_path = str(
                Path(artifact_reference["path"]).resolve()
            )
            break

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
            str(dashboard_package["metadata_path"])
            if dashboard_package is not None
            else upstream_dashboard_metadata_path
        ),
        "output_locations": copy.deepcopy(dict(normalized_plan["output_locations"])),
    }


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
            dashboard_context["payload"]["pane_inputs"]["time_series"]["selected_readout_id"]
        ),
        "selected_neuron_id": dashboard_context["payload"]["pane_inputs"]["morphology"][
            "selected_neuron_id"
        ],
    }


def _initial_showcase_runtime_mode(operator_defaults: Mapping[str, Any]) -> str:
    rehearsal_mode = bool(operator_defaults.get("rehearsal_mode", True))
    auto_advance = bool(operator_defaults.get("auto_advance", False))
    if rehearsal_mode and not auto_advance:
        return PRESENTER_REHEARSAL_MODE
    return GUIDED_AUTOPLAY_MODE


def _build_showcase_presentation_state(
    *,
    showcase_session: Mapping[str, Any],
    dashboard_context: Mapping[str, Any],
    showcase_steps: Sequence[Mapping[str, Any]],
    operator_defaults: Mapping[str, Any],
    plan_version: str,
) -> dict[str, Any]:
    return {
        "format_version": JSON_SHOWCASE_STATE_FORMAT,
        "contract_version": SHOWCASE_SESSION_CONTRACT_VERSION,
        "plan_version": plan_version,
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
            dashboard_context["payload"]["pane_inputs"]["circuit"]["selected_root_ids"]
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
    plan_version: str,
) -> dict[str, Any]:
    initial_runtime_mode = _initial_showcase_runtime_mode(operator_defaults)
    return {
        "format_version": JSON_SHOWCASE_SCRIPT_FORMAT,
        "contract_version": SHOWCASE_SESSION_CONTRACT_VERSION,
        "plan_version": plan_version,
        "runtime_version": SHOWCASE_PLAYER_RUNTIME_VERSION,
        "bundle_reference": {
            "bundle_id": str(showcase_session["bundle_id"]),
            "showcase_spec_hash": str(showcase_session["showcase_spec_hash"]),
        },
        "showcase_id": str(showcase_session["showcase_id"]),
        "display_name": str(showcase_session["display_name"]),
        "presentation_status": str(showcase_session["presentation_status"]),
        "operator_defaults": copy.deepcopy(dict(operator_defaults)),
        "supported_runtime_modes": list(SUPPORTED_SHOWCASE_PLAYER_MODES),
        "supported_commands": list(SUPPORTED_SHOWCASE_PLAYER_COMMANDS),
        "step_order": [str(step["step_id"]) for step in showcase_steps],
        "initial_checkpoint": {
            "step_id": str(operator_defaults["current_step_id"]),
            "preset_id": str(operator_defaults["current_preset_id"]),
            "runtime_mode": initial_runtime_mode,
        },
        "step_sequence": [
            {
                "sequence_index": index,
                "step_id": str(step["step_id"]),
                "preset_id": str(step["preset_id"]),
                "cue_kind_id": str(step["cue_kind_id"]),
                "presentation_status": str(step["presentation_status"]),
                "fallback_preset_id": step.get("fallback_preset_id"),
                "operator_control_ids": list(step["operator_control_ids"]),
                "supports_seek": SCRUB_TIME_CONTROL_ID in step["operator_control_ids"],
                "supports_direct_jump": str(step["presentation_status"])
                not in {
                    PRESENTATION_STATUS_BLOCKED,
                    PRESENTATION_STATUS_SCIENTIFIC_REVIEW_REQUIRED,
                },
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
            for index, step in enumerate(showcase_steps)
        ],
        "saved_preset_ids": [str(item["preset_id"]) for item in saved_presets],
    }


def _build_narrative_preset_catalog(
    *,
    showcase_session: Mapping[str, Any],
    dashboard_context: Mapping[str, Any],
    showcase_fixture: Mapping[str, Any],
    narrative_context: Mapping[str, Any],
    showcase_steps: Sequence[Mapping[str, Any]],
    saved_presets: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    preset_discovery_order = [str(item["preset_id"]) for item in saved_presets]
    highlight_step = next(
        item
        for item in showcase_steps
        if str(item["step_id"]) == APPROVED_WAVE_HIGHLIGHT_STEP_ID
    )
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
        "preset_library_id": DEFAULT_NARRATIVE_PRESET_LIBRARY_ID,
        "fixture_profile": {
            "fixture_mode": str(showcase_fixture["fixture_mode"]),
            "keeps_readiness_fixtures_fast": bool(
                showcase_fixture["keeps_readiness_fixtures_fast"]
            ),
            "workflow_kind": str(showcase_fixture["workflow_kind"]),
        },
        "story_arc_preset_ids": copy.deepcopy(dict(showcase_fixture["story_arc_preset_ids"])),
        "preset_discovery_order": preset_discovery_order,
        "comparison_act": copy.deepcopy(dict(narrative_context["comparison_act"])),
        "highlight_metadata": copy.deepcopy(dict(narrative_context["highlight_selection"])),
        "highlight_presentation": copy.deepcopy(
            dict(narrative_context["highlight_presentation"])
        ),
        "summary_analysis_landing": copy.deepcopy(
            dict(narrative_context["summary_analysis_landing"])
        ),
        "highlight_step_evidence_references": copy.deepcopy(
            list(highlight_step["evidence_references"])
        ),
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


def _require_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return copy.deepcopy(dict(value))
