from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from .dashboard_session_contract import (
    ANALYSIS_PANE_ID,
    CIRCUIT_PANE_ID,
    MORPHOLOGY_PANE_ID,
    SCENE_PANE_ID,
    TIME_SERIES_PANE_ID,
)
from .showcase_player import SUPPORTED_SHOWCASE_PLAYER_MODES


_SUPPORTED_PANE_IDS = (
    SCENE_PANE_ID,
    CIRCUIT_PANE_ID,
    MORPHOLOGY_PANE_ID,
    TIME_SERIES_PANE_ID,
    ANALYSIS_PANE_ID,
)
_SHOWCASE_CONTROL_GROUP_IDS = (
    "comparison_controls",
    "inspection_drawer",
    "inspection_escape_hatch",
    "neuron_detail_controls",
    "overlay_controls",
    "playback_transport",
    "readout_detail_controls",
    "scene_context_controls",
    "story_annotations",
    "story_header",
    "subset_focus_controls",
    "time_scrub",
)


def validate_highlight_locator(
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


def validate_presentation_state_patch(
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
        "rehearsal_metadata",
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

    if "rehearsal_metadata" in patch:
        validate_rehearsal_metadata(
            preset_id=preset_id,
            metadata=_require_mapping(
                patch["rehearsal_metadata"],
                field_name=f"saved_presets[{preset_id!r}].rehearsal_metadata",
            ),
            dashboard_payload=dashboard_payload,
        )

    dashboard_state_patch = patch.get("dashboard_state_patch")
    if isinstance(dashboard_state_patch, Mapping):
        validate_dashboard_state_patch(
            preset_id=preset_id,
            patch=dashboard_state_patch,
            dashboard_payload=dashboard_payload,
        )


def validate_rehearsal_metadata(
    *,
    preset_id: str,
    metadata: Mapping[str, Any],
    dashboard_payload: Mapping[str, Any],
) -> None:
    valid_layers = {
        str(item["layer_id"])
        for item in dashboard_payload["pane_inputs"][SCENE_PANE_ID]["render_layers"]
    }
    selected_root_ids = {
        int(root_id)
        for root_id in dashboard_payload["pane_inputs"][CIRCUIT_PANE_ID]["selected_root_ids"]
    }
    available_overlays = set(dashboard_payload["overlay_catalog"]["available_overlay_ids"])
    selected_readout_id = str(
        dashboard_payload["pane_inputs"][TIME_SERIES_PANE_ID]["selected_readout_id"]
    )
    sample_count = len(
        dashboard_payload["pane_inputs"][TIME_SERIES_PANE_ID]["replay_model"].get(
            "canonical_time_ms",
            [],
        )
    )

    camera_anchor = metadata.get("camera_anchor")
    if camera_anchor is not None:
        _require_mapping(
            camera_anchor,
            field_name=f"saved_presets[{preset_id!r}].rehearsal_metadata.camera_anchor",
        )

    camera_choreography = metadata.get("camera_choreography")
    if camera_choreography is not None:
        record = _require_mapping(
            camera_choreography,
            field_name=f"saved_presets[{preset_id!r}].rehearsal_metadata.camera_choreography",
        )
        anchor = _require_mapping(
            record.get("anchor"),
            field_name=(
                f"saved_presets[{preset_id!r}].rehearsal_metadata.camera_choreography.anchor"
            ),
        )
        if str(anchor["focus_pane_id"]) not in _SUPPORTED_PANE_IDS:
            raise ValueError(
                f"saved preset {preset_id!r} camera_choreography.focus_pane_id "
                f"{anchor['focus_pane_id']!r} is unsupported."
            )
        if (
            anchor.get("active_layer_id") is not None
            and str(anchor["active_layer_id"]) not in valid_layers
        ):
            raise ValueError(
                f"saved preset {preset_id!r} camera_choreography.anchor.active_layer_id "
                f"{anchor['active_layer_id']!r} is unavailable."
            )
        if anchor.get("target_root_ids") is not None:
            missing = sorted(
                int(root_id)
                for root_id in anchor["target_root_ids"]
                if int(root_id) not in selected_root_ids
            )
            if missing:
                raise ValueError(
                    f"saved preset {preset_id!r} camera_choreography.anchor.target_root_ids "
                    f"references unavailable roots {missing!r}."
                )
        transition = _require_mapping(
            record.get("transition"),
            field_name=(
                f"saved_presets[{preset_id!r}].rehearsal_metadata.camera_choreography.transition"
            ),
        )
        for field_name in ("duration_ms", "hold_duration_ms"):
            value = transition.get(field_name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(
                    f"saved preset {preset_id!r} camera_choreography.transition.{field_name} "
                    "must be a non-negative integer."
                )
        linked_pane_ids = record.get("linked_pane_ids", [])
        if not isinstance(linked_pane_ids, Sequence) or isinstance(
            linked_pane_ids, (str, bytes)
        ):
            raise ValueError(
                f"saved preset {preset_id!r} camera_choreography.linked_pane_ids "
                "must be a sequence."
            )
        for pane_id in linked_pane_ids:
            if str(pane_id) not in _SUPPORTED_PANE_IDS:
                raise ValueError(
                    f"saved preset {preset_id!r} camera_choreography.linked_pane_ids "
                    f"references unsupported pane {pane_id!r}."
                )
        timing = _require_mapping(
            record.get("timing"),
            field_name=(
                f"saved_presets[{preset_id!r}].rehearsal_metadata.camera_choreography.timing"
            ),
        )
        for field_name in ("narration_lead_in_ms", "annotation_stagger_ms"):
            value = timing.get(field_name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(
                    f"saved preset {preset_id!r} camera_choreography.timing.{field_name} "
                    "must be a non-negative integer."
                )
        if timing.get("recommended_sample_index") is not None:
            sample_index = timing["recommended_sample_index"]
            if (
                not isinstance(sample_index, int)
                or sample_index < 0
                or sample_index >= max(sample_count, 1)
            ):
                raise ValueError(
                    f"saved preset {preset_id!r} camera_choreography.timing.recommended_sample_index "
                    "must fit within the packaged replay timebase."
                )

    annotation_layout = metadata.get("annotation_layout")
    if annotation_layout is not None:
        record = _require_mapping(
            annotation_layout,
            field_name=f"saved_presets[{preset_id!r}].rehearsal_metadata.annotation_layout",
        )
        if str(record["focus_pane_id"]) not in _SUPPORTED_PANE_IDS:
            raise ValueError(
                f"saved preset {preset_id!r} annotation_layout.focus_pane_id "
                f"{record['focus_pane_id']!r} is unsupported."
            )
        placements = record.get("placements", [])
        if not isinstance(placements, Sequence) or isinstance(placements, (str, bytes)):
            raise ValueError(
                f"saved preset {preset_id!r} annotation_layout.placements must be a sequence."
            )
        for index, placement in enumerate(placements):
            record_item = _require_mapping(
                placement,
                field_name=(
                    f"saved_presets[{preset_id!r}].rehearsal_metadata.annotation_layout.placements[{index}]"
                ),
            )
            if str(record_item["pane_id"]) not in _SUPPORTED_PANE_IDS:
                raise ValueError(
                    f"saved preset {preset_id!r} annotation placement pane_id "
                    f"{record_item['pane_id']!r} is unsupported."
                )
            if (
                not isinstance(record_item.get("delay_ms"), int)
                or int(record_item["delay_ms"]) < 0
            ):
                raise ValueError(
                    f"saved preset {preset_id!r} annotation placement delay_ms must be a non-negative integer."
                )

    presentation_links = metadata.get("presentation_links")
    if presentation_links is not None:
        if not isinstance(presentation_links, Sequence) or isinstance(
            presentation_links, (str, bytes)
        ):
            raise ValueError(
                f"saved preset {preset_id!r} rehearsal_metadata.presentation_links must be a sequence."
            )
        for index, item in enumerate(presentation_links):
            record = _require_mapping(
                item,
                field_name=(
                    f"saved_presets[{preset_id!r}].rehearsal_metadata.presentation_links[{index}]"
                ),
            )
            if str(record["source_pane_id"]) not in _SUPPORTED_PANE_IDS:
                raise ValueError(
                    f"saved preset {preset_id!r} presentation link source_pane_id "
                    f"{record['source_pane_id']!r} is unsupported."
                )
            target_pane_ids = record.get("target_pane_ids", [])
            if not isinstance(target_pane_ids, Sequence) or isinstance(
                target_pane_ids, (str, bytes)
            ):
                raise ValueError(
                    f"saved preset {preset_id!r} presentation link target_pane_ids must be a sequence."
                )
            for pane_id in target_pane_ids:
                if str(pane_id) not in _SUPPORTED_PANE_IDS:
                    raise ValueError(
                        f"saved preset {preset_id!r} presentation link target_pane_ids "
                        f"references unsupported pane {pane_id!r}."
                    )
            _require_mapping(
                record.get("shared_context"),
                field_name=(
                    f"saved_presets[{preset_id!r}].rehearsal_metadata.presentation_links[{index}].shared_context"
                ),
            )

    emphasis_state = metadata.get("emphasis_state")
    if emphasis_state is not None:
        record = _require_mapping(
            emphasis_state,
            field_name=f"saved_presets[{preset_id!r}].rehearsal_metadata.emphasis_state",
        )
        linked_pane_ids = record.get("linked_pane_ids", [])
        if not isinstance(linked_pane_ids, Sequence) or isinstance(
            linked_pane_ids, (str, bytes)
        ):
            raise ValueError(
                f"saved preset {preset_id!r} emphasis_state.linked_pane_ids must be a sequence."
            )
        for pane_id in linked_pane_ids:
            if str(pane_id) not in _SUPPORTED_PANE_IDS:
                raise ValueError(
                    f"saved preset {preset_id!r} emphasis_state.linked_pane_ids "
                    f"references unsupported pane {pane_id!r}."
                )
        overlay_ids_by_pane = _require_mapping(
            record.get("overlay_ids_by_pane"),
            field_name=(
                f"saved_presets[{preset_id!r}].rehearsal_metadata.emphasis_state.overlay_ids_by_pane"
            ),
        )
        for pane_id, overlay_ids in overlay_ids_by_pane.items():
            if str(pane_id) not in _SUPPORTED_PANE_IDS:
                raise ValueError(
                    f"saved preset {preset_id!r} emphasis_state.overlay_ids_by_pane "
                    f"references unsupported pane {pane_id!r}."
                )
            if not isinstance(overlay_ids, Sequence) or isinstance(overlay_ids, (str, bytes)):
                raise ValueError(
                    f"saved preset {preset_id!r} emphasis_state.overlay_ids_by_pane[{pane_id!r}] "
                    "must be a sequence."
                )
            for overlay_id in overlay_ids:
                if str(overlay_id) not in available_overlays:
                    raise ValueError(
                        f"saved preset {preset_id!r} emphasis_state.overlay_ids_by_pane "
                        f"references unavailable overlay {overlay_id!r}."
                    )
        if record.get("focus_root_ids") is not None:
            missing = sorted(
                int(root_id)
                for root_id in record["focus_root_ids"]
                if int(root_id) not in selected_root_ids
            )
            if missing:
                raise ValueError(
                    f"saved preset {preset_id!r} emphasis_state.focus_root_ids "
                    f"references unavailable roots {missing!r}."
                )
        if (
            record.get("selected_neuron_id") is not None
            and int(record["selected_neuron_id"]) not in selected_root_ids
        ):
            raise ValueError(
                f"saved preset {preset_id!r} emphasis_state.selected_neuron_id "
                f"{record['selected_neuron_id']!r} is unavailable."
            )
        if (
            record.get("selected_readout_id") is not None
            and str(record["selected_readout_id"]) != selected_readout_id
        ):
            raise ValueError(
                f"saved preset {preset_id!r} emphasis_state.selected_readout_id "
                f"{record['selected_readout_id']!r} is unavailable."
            )

    showcase_ui_state = metadata.get("showcase_ui_state")
    if showcase_ui_state is not None:
        record = _require_mapping(
            showcase_ui_state,
            field_name=f"saved_presets[{preset_id!r}].rehearsal_metadata.showcase_ui_state",
        )
        if str(record["primary_pane_id"]) not in _SUPPORTED_PANE_IDS:
            raise ValueError(
                f"saved preset {preset_id!r} showcase_ui_state.primary_pane_id "
                f"{record['primary_pane_id']!r} is unsupported."
            )
        support_pane_ids = record.get("support_pane_ids", [])
        if not isinstance(support_pane_ids, Sequence) or isinstance(
            support_pane_ids, (str, bytes)
        ):
            raise ValueError(
                f"saved preset {preset_id!r} showcase_ui_state.support_pane_ids must be a sequence."
            )
        for pane_id in support_pane_ids:
            if str(pane_id) not in _SUPPORTED_PANE_IDS:
                raise ValueError(
                    f"saved preset {preset_id!r} showcase_ui_state.support_pane_ids "
                    f"references unsupported pane {pane_id!r}."
                )
        escape_hatch = _require_mapping(
            record.get("inspection_escape_hatch"),
            field_name=(
                f"saved_presets[{preset_id!r}].rehearsal_metadata.showcase_ui_state.inspection_escape_hatch"
            ),
        )
        if not bool(escape_hatch.get("available")):
            raise ValueError(
                f"saved preset {preset_id!r} showcase_ui_state must keep an available inspection escape hatch."
            )
        for path_field in ("dashboard_session_metadata_path", "dashboard_app_shell_path"):
            if not escape_hatch.get(path_field):
                raise ValueError(
                    f"saved preset {preset_id!r} showcase_ui_state.inspection_escape_hatch "
                    f"is missing {path_field!r}."
                )
        variants = _require_mapping(
            record.get("runtime_mode_variants"),
            field_name=(
                f"saved_presets[{preset_id!r}].rehearsal_metadata.showcase_ui_state.runtime_mode_variants"
            ),
        )
        unsupported_modes = set(variants) - set(SUPPORTED_SHOWCASE_PLAYER_MODES)
        if unsupported_modes:
            raise ValueError(
                f"saved preset {preset_id!r} showcase_ui_state.runtime_mode_variants "
                f"references unsupported runtime modes {sorted(unsupported_modes)!r}."
            )
        for runtime_mode, variant in variants.items():
            record_variant = _require_mapping(
                variant,
                field_name=(
                    "saved_presets"
                    f"[{preset_id!r}].rehearsal_metadata.showcase_ui_state.runtime_mode_variants[{runtime_mode!r}]"
                ),
            )
            for field_name in (
                "visible_control_groups",
                "suppressed_control_groups",
                "reorganized_control_groups",
            ):
                control_groups = record_variant.get(field_name, [])
                if not isinstance(control_groups, Sequence) or isinstance(
                    control_groups, (str, bytes)
                ):
                    raise ValueError(
                        f"saved preset {preset_id!r} showcase_ui_state {field_name} must be a sequence."
                    )
                unsupported_groups = sorted(
                    str(value)
                    for value in control_groups
                    if str(value) not in _SHOWCASE_CONTROL_GROUP_IDS
                )
                if unsupported_groups:
                    raise ValueError(
                        f"saved preset {preset_id!r} showcase_ui_state {field_name} "
                        f"references unsupported control groups {unsupported_groups!r}."
                    )


def validate_dashboard_state_patch(
    *,
    preset_id: str,
    patch: Mapping[str, Any],
    dashboard_payload: Mapping[str, Any],
) -> None:
    available_overlays = set(dashboard_payload["overlay_catalog"]["available_overlay_ids"])
    allowed_comparison_modes = {
        str(item["comparison_mode_id"])
        for item in dashboard_payload["pane_inputs"][TIME_SERIES_PANE_ID]["replay_model"][
            "comparison_mode_statuses"
        ]
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
        if (
            "selected_neuron_id" in state_patch
            and int(state_patch["selected_neuron_id"]) not in selected_root_ids
        ):
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
                field_name=(
                    f"saved_presets[{preset_id!r}].dashboard_state_patch.{state_key}.selected_arm_pair"
                ),
            )
            if (
                "active_arm_id" in pair_patch
                and str(pair_patch["active_arm_id"]) not in valid_arm_ids
            ):
                raise ValueError(
                    f"saved preset {preset_id!r} references unavailable active_arm_id "
                    f"{pair_patch['active_arm_id']!r}."
                )


def _require_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return copy.deepcopy(dict(value))
