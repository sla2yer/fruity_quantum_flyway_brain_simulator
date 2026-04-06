from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.dashboard_session_contract import (
    SELECTED_SUBSET_HIGHLIGHT_OVERLAY_ID,
    SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    STIMULUS_CONTEXT_FRAME_OVERLAY_ID,
    load_dashboard_session_metadata,
)
from flywire_wave.io_utils import write_json
from flywire_wave.showcase_session_contract import (
    ACTIVE_VISUAL_SUBSET_STEP_ID,
    ACTIVITY_PROPAGATION_STEP_ID,
    ANALYSIS_UI_PAYLOAD_ROLE_ID,
    ANALYSIS_SUMMARY_PRESET_ID,
    APPROVED_HIGHLIGHT_PRESET_ID,
    APPROVED_WAVE_HIGHLIGHT_STEP_ID,
    BASELINE_WAVE_COMPARISON_STEP_ID,
    DASHBOARD_SESSION_METADATA_ROLE_ID,
    FLY_VIEW_INPUT_STEP_ID,
    HIGHLIGHT_FALLBACK_PRESET_ID,
    METADATA_JSON_KEY,
    PAIRED_COMPARISON_PRESET_ID,
    PROPAGATION_REPLAY_PRESET_ID,
    RETINAL_INPUT_FOCUS_PRESET_ID,
    SCENE_CONTEXT_PRESET_ID,
    SCENE_SELECTION_STEP_ID,
    SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID,
    SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID,
    SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID,
    SUBSET_CONTEXT_PRESET_ID,
    SUITE_SUMMARY_TABLE_ROLE_ID,
    SUMMARY_ANALYSIS_STEP_ID,
    VALIDATION_REVIEW_HANDOFF_ROLE_ID,
    discover_showcase_session_bundle_paths,
    load_showcase_session_metadata,
)
from flywire_wave.showcase_session_planning import (
    package_showcase_session,
    resolve_showcase_session_plan,
    SHOWCASE_FIXTURE_MODE_REHEARSAL,
)
from flywire_wave.validation_contract import (
    REVIEW_HANDOFF_ARTIFACT_ID,
    discover_validation_bundle_paths,
)

try:
    from tests.showcase_test_support import (
        DEFAULT_SEED,
        EXPERIMENT_ID,
        _approve_validation_highlight,
        _inject_dashboard_stage_artifact,
        _materialize_packaged_showcase_fixture,
    )
except ModuleNotFoundError:
    from showcase_test_support import (  # type: ignore[no-redef]
        DEFAULT_SEED,
        EXPERIMENT_ID,
        _approve_validation_highlight,
        _inject_dashboard_stage_artifact,
        _materialize_packaged_showcase_fixture,
    )


class ShowcaseSessionPlanningTest(unittest.TestCase):
    def test_packaged_dashboard_and_suite_inputs_resolve_deterministic_showcase_bundle(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))

            first = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                suite_review_summary_path=fixture["suite_review_summary_path"],
                table_dimension_ids=["motion_direction"],
                saved_preset_overrides={
                    PAIRED_COMPARISON_PRESET_ID: {
                        "display_name": "Paired Fairness",
                        "presentation_state_patch": {
                            "dashboard_state_patch": {
                                "global_interaction_state": {
                                    "active_overlay_id": SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                                },
                                "replay_state": {
                                    "active_overlay_id": SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                                },
                            },
                        },
                    },
                },
            )
            second = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                suite_review_summary_path=fixture["suite_review_summary_path"],
                table_dimension_ids=["motion_direction"],
                saved_preset_overrides={
                    PAIRED_COMPARISON_PRESET_ID: {
                        "display_name": "Paired Fairness",
                        "presentation_state_patch": {
                            "dashboard_state_patch": {
                                "global_interaction_state": {
                                    "active_overlay_id": SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                                },
                                "replay_state": {
                                    "active_overlay_id": SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                                },
                            },
                        },
                    },
                },
            )

            self.assertEqual(first, second)
            self.assertEqual(first["source_mode"], "dashboard_session")
            self.assertEqual(
                [item["step_id"] for item in first["narrative_step_sequence"]],
                [
                    SCENE_SELECTION_STEP_ID,
                    FLY_VIEW_INPUT_STEP_ID,
                    ACTIVE_VISUAL_SUBSET_STEP_ID,
                    ACTIVITY_PROPAGATION_STEP_ID,
                    BASELINE_WAVE_COMPARISON_STEP_ID,
                    APPROVED_WAVE_HIGHLIGHT_STEP_ID,
                    SUMMARY_ANALYSIS_STEP_ID,
                ],
            )
            self.assertEqual(
                _saved_preset(first, PAIRED_COMPARISON_PRESET_ID)["display_name"],
                "Paired Fairness",
            )
            self.assertEqual(
                first["closing_analysis_assets"]["suite_summary_table_path"],
                str(fixture["suite_summary_table_path"]),
            )
            self.assertEqual(
                first["output_locations"]["metadata_path"],
                first["showcase_session"]["artifacts"][METADATA_JSON_KEY]["path"],
            )

            packaged = package_showcase_session(first)
            metadata = load_showcase_session_metadata(packaged["metadata_path"])
            bundle_paths = discover_showcase_session_bundle_paths(metadata)

            self.assertEqual(metadata["bundle_id"], first["showcase_session"]["bundle_id"])
            self.assertEqual(
                bundle_paths[METADATA_JSON_KEY],
                Path(packaged["metadata_path"]).resolve(),
            )
            self.assertEqual(
                bundle_paths[SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID],
                Path(packaged["showcase_script_path"]).resolve(),
            )
            self.assertEqual(
                bundle_paths[SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID],
                Path(packaged["showcase_state_path"]).resolve(),
            )
            self.assertEqual(
                bundle_paths[SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID],
                Path(packaged["showcase_export_manifest_path"]).resolve(),
            )
            self.assertEqual(
                packaged["upstream_dashboard_metadata_path"],
                str(fixture["dashboard_metadata_path"]),
            )
            self.assertEqual(packaged["output_locations"], first["output_locations"])
            self.assertTrue(
                str(Path(packaged["bundle_directory"]).resolve()).endswith(
                    f"/showcase_sessions/{EXPERIMENT_ID}/{metadata['showcase_spec_hash']}"
                )
            )
            export_manifest = json.loads(
                Path(packaged["showcase_export_manifest_path"]).read_text(encoding="utf-8")
            )
            export_paths = {
                item["export_target_role_id"]: item["path"]
                for item in export_manifest["export_targets"]
            }
            self.assertEqual(
                export_paths,
                first["output_locations"]["export_target_paths"],
            )

    def test_suite_package_source_mode_discovers_dashboard_stage_artifact(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))
            _inject_dashboard_stage_artifact(
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                dashboard_metadata_path=fixture["dashboard_metadata_path"],
            )

            plan = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                table_dimension_ids=["motion_direction"],
            )

            self.assertEqual(plan["source_mode"], "suite_package")
            self.assertIsNone(plan["dashboard_session_plan"])
            self.assertEqual(
                next(
                    item["path"]
                    for item in plan["upstream_artifact_references"]
                    if item["artifact_role_id"] == DASHBOARD_SESSION_METADATA_ROLE_ID
                ),
                str(fixture["dashboard_metadata_path"]),
            )
            self.assertEqual(
                plan["closing_analysis_assets"]["suite_summary_table_path"],
                str(fixture["suite_summary_table_path"]),
            )

    def test_explicit_artifact_inputs_preserve_suite_evidence_and_highlight_override(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))
            _approve_validation_highlight(fixture)

            baseline_plan = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                suite_review_summary_path=fixture["suite_review_summary_path"],
                table_dimension_ids=["motion_direction"],
            )
            explicit_plan = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                explicit_artifact_references=baseline_plan["upstream_artifact_references"],
                highlight_override={
                    "phenomenon_id": "phase_alignment_focus",
                    "locator": "wave_only_diagnostics.phase_map_references[0]",
                    "citation_label": "Approved phase alignment",
                },
            )

            self.assertEqual(explicit_plan["source_mode"], "explicit_artifact_inputs")
            self.assertEqual(
                explicit_plan["closing_analysis_assets"]["suite_summary_table_path"],
                baseline_plan["closing_analysis_assets"]["suite_summary_table_path"],
            )
            self.assertEqual(
                explicit_plan["highlight_selection"]["phenomenon_id"],
                "phase_alignment_focus",
            )
            self.assertEqual(
                explicit_plan["highlight_selection"]["citation_label"],
                "Approved phase alignment",
            )
            self.assertEqual(
                explicit_plan["highlight_selection"]["presentation_status"],
                "ready",
            )
            self.assertEqual(
                _showcase_step(explicit_plan, APPROVED_WAVE_HIGHLIGHT_STEP_ID)["preset_id"],
                APPROVED_HIGHLIGHT_PRESET_ID,
            )
            self.assertEqual(
                _saved_preset(explicit_plan, ANALYSIS_SUMMARY_PRESET_ID)["step_id"],
                SUMMARY_ANALYSIS_STEP_ID,
            )

    def test_rehearsal_fixture_packages_curated_preset_library_and_evidence_backed_highlight(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))
            _approve_validation_highlight(fixture)

            plan = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                suite_review_summary_path=fixture["suite_review_summary_path"],
                table_dimension_ids=["motion_direction"],
                fixture_mode=SHOWCASE_FIXTURE_MODE_REHEARSAL,
                highlight_override={
                    "phenomenon_id": "phase_alignment_focus",
                    "locator": "wave_only_diagnostics.phase_map_references[0]",
                    "citation_label": "Approved phase alignment",
                },
            )
            packaged = package_showcase_session(plan)
            catalog = json.loads(
                Path(packaged["narrative_preset_catalog_path"]).read_text(encoding="utf-8")
            )

            self.assertEqual(plan["fixture_mode"], SHOWCASE_FIXTURE_MODE_REHEARSAL)
            self.assertTrue(plan["showcase_fixture"]["keeps_readiness_fixtures_fast"])
            self.assertEqual(
                catalog["fixture_profile"]["fixture_mode"],
                SHOWCASE_FIXTURE_MODE_REHEARSAL,
            )
            self.assertEqual(
                catalog["story_arc_preset_ids"],
                {
                    "scene_choice": "scene_context",
                    "fly_view_framing": "retinal_input_focus",
                    "active_subset_emphasis": "subset_context",
                    "propagation_view": "propagation_replay",
                    "comparison_pairing": "paired_comparison",
                    "highlight_phenomenon_reference": "approved_highlight",
                    "highlight_fallback": "highlight_fallback",
                    "final_analysis_landing": "analysis_summary",
                },
            )
            self.assertEqual(
                catalog["preset_discovery_order"],
                [
                    "scene_context",
                    "retinal_input_focus",
                    "subset_context",
                    "propagation_replay",
                    "paired_comparison",
                    "approved_highlight",
                    "highlight_fallback",
                    "analysis_summary",
                ],
            )
            self.assertEqual(
                [item["preset_id"] for item in catalog["saved_presets"]],
                catalog["preset_discovery_order"],
            )

            approved_preset = next(
                item
                for item in catalog["saved_presets"]
                if item["preset_id"] == APPROVED_HIGHLIGHT_PRESET_ID
            )
            self.assertEqual(
                approved_preset["presentation_state_patch"]["rehearsal_metadata"][
                    "story_role"
                ],
                "highlight_phenomenon_reference",
            )
            self.assertEqual(
                catalog["highlight_metadata"]["phenomenon_id"],
                "phase_alignment_focus",
            )
            self.assertEqual(
                catalog["highlight_metadata"]["fallback_path"]["fallback_preset_id"],
                HIGHLIGHT_FALLBACK_PRESET_ID,
            )
            self.assertEqual(
                catalog["highlight_metadata"]["fallback_path"]["fallback_step_id"],
                BASELINE_WAVE_COMPARISON_STEP_ID,
            )
            support_roles = {
                item["artifact_role_id"]
                for item in catalog["highlight_metadata"]["supporting_evidence_references"]
            }
            self.assertIn(SUITE_SUMMARY_TABLE_ROLE_ID, support_roles)
            self.assertIn(VALIDATION_REVIEW_HANDOFF_ROLE_ID, support_roles)

            highlight_step = _showcase_step(plan, APPROVED_WAVE_HIGHLIGHT_STEP_ID)
            self.assertEqual(
                {
                    item["artifact_role_id"]
                    for item in highlight_step["evidence_references"]
                },
                {
                    ANALYSIS_UI_PAYLOAD_ROLE_ID,
                    SUITE_SUMMARY_TABLE_ROLE_ID,
                    VALIDATION_REVIEW_HANDOFF_ROLE_ID,
                },
            )
            self.assertEqual(
                catalog["highlight_step_evidence_references"],
                highlight_step["evidence_references"],
            )
            self.assertEqual(
                catalog["comparison_act"]["view_kind"],
                "comparison_act",
            )
            self.assertEqual(
                catalog["comparison_act"]["content_scope_label"],
                "shared_comparison",
            )
            self.assertEqual(
                catalog["comparison_act"]["stable_pairing_semantics"]["shared_seed"],
                DEFAULT_SEED,
            )
            self.assertEqual(
                catalog["highlight_presentation"]["view_kind"],
                "wave_highlight_effect",
            )
            self.assertEqual(
                catalog["highlight_presentation"]["active_scope_label"],
                "wave_only_diagnostic",
            )
            self.assertEqual(
                catalog["summary_analysis_landing"]["view_kind"],
                "summary_analysis_landing",
            )
            self.assertEqual(
                catalog["summary_analysis_landing"]["headline"],
                "Small, causal, geometry-dependent computational effect.",
            )
            self.assertEqual(
                plan["summary_analysis_landing"]["highlight_outcome"][
                    "presentation_status"
                ],
                "ready",
            )

    def test_analysis_summary_preset_records_whole_brain_context_handoff(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))

            plan = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                suite_review_summary_path=fixture["suite_review_summary_path"],
                table_dimension_ids=["motion_direction"],
                fixture_mode=SHOWCASE_FIXTURE_MODE_REHEARSAL,
            )
            packaged = package_showcase_session(plan)
            catalog = json.loads(
                Path(packaged["narrative_preset_catalog_path"]).read_text(encoding="utf-8")
            )
            analysis_summary_preset = next(
                item
                for item in catalog["saved_presets"]
                if item["preset_id"] == ANALYSIS_SUMMARY_PRESET_ID
            )
            handoff_links = [
                item
                for item in analysis_summary_preset["presentation_state_patch"][
                    "rehearsal_metadata"
                ]["presentation_links"]
                if item["link_kind"] == "whole_brain_context_handoff"
            ]

            self.assertEqual(len(handoff_links), 1)
            self.assertEqual(
                handoff_links[0]["shared_context"]["target_contract_version"],
                "whole_brain_context_session.v1",
            )
            self.assertEqual(
                handoff_links[0]["shared_context"]["target_context_preset_id"],
                "showcase_handoff",
            )

    def test_unapproved_highlight_demotes_to_caveated_fallback_story_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))

            plan = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                suite_review_summary_path=fixture["suite_review_summary_path"],
                table_dimension_ids=["motion_direction"],
                fixture_mode=SHOWCASE_FIXTURE_MODE_REHEARSAL,
            )

            self.assertEqual(plan["highlight_selection"]["presentation_status"], "fallback")
            self.assertEqual(
                plan["highlight_presentation"]["view_kind"],
                "wave_highlight_caveat",
            )
            self.assertEqual(
                plan["highlight_presentation"]["active_scope_label"],
                "shared_comparison",
            )
            self.assertIn(
                "not approved",
                str(plan["highlight_presentation"]["caveat_text"]),
            )
            self.assertEqual(
                _showcase_step(plan, APPROVED_WAVE_HIGHLIGHT_STEP_ID)["preset_id"],
                HIGHLIGHT_FALLBACK_PRESET_ID,
            )
            self.assertEqual(
                plan["summary_analysis_landing"]["highlight_outcome"][
                    "presentation_status"
                ],
                "fallback",
            )
            self.assertIn(
                "Demote the wave-only highlight",
                plan["summary_analysis_landing"]["newcomer_summary_lines"][1],
            )

    def test_early_story_presets_capture_deterministic_choreography_and_ui_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))

            plan = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                suite_review_summary_path=fixture["suite_review_summary_path"],
                table_dimension_ids=["motion_direction"],
                fixture_mode=SHOWCASE_FIXTURE_MODE_REHEARSAL,
            )

            scene_preset = _saved_preset(plan, SCENE_CONTEXT_PRESET_ID)
            input_preset = _saved_preset(plan, RETINAL_INPUT_FOCUS_PRESET_ID)
            subset_preset = _saved_preset(plan, SUBSET_CONTEXT_PRESET_ID)
            propagation_preset = _saved_preset(plan, PROPAGATION_REPLAY_PRESET_ID)

            scene_metadata = scene_preset["presentation_state_patch"]["rehearsal_metadata"]
            self.assertEqual(
                scene_metadata["camera_choreography"]["transition"]["to_anchor_id"],
                "opening_scene_context",
            )
            self.assertEqual(
                scene_metadata["annotation_layout"]["placements"][0]["annotation_id"],
                "story_context",
            )
            self.assertEqual(
                scene_metadata["emphasis_state"]["overlay_ids_by_pane"]["scene"],
                [STIMULUS_CONTEXT_FRAME_OVERLAY_ID],
            )
            self.assertEqual(
                scene_metadata["showcase_ui_state"]["inspection_escape_hatch"][
                    "dashboard_app_shell_path"
                ],
                str(Path(fixture["dashboard_package"]["app_shell_path"]).resolve()),
            )

            input_metadata = input_preset["presentation_state_patch"]["rehearsal_metadata"]
            self.assertEqual(
                input_metadata["presentation_links"][0]["link_kind"],
                "shared_scene_surface",
            )
            self.assertEqual(
                input_metadata["presentation_links"][0]["shared_context"][
                    "active_layer_id"
                ],
                plan["scene_choice"]["active_layer_id"],
            )

            subset_metadata = subset_preset["presentation_state_patch"]["rehearsal_metadata"]
            self.assertEqual(
                subset_metadata["camera_choreography"]["anchor"]["anchor_id"],
                "active_subset_cluster",
            )
            self.assertEqual(
                subset_metadata["emphasis_state"]["overlay_ids_by_pane"]["circuit"],
                [SELECTED_SUBSET_HIGHLIGHT_OVERLAY_ID],
            )
            self.assertEqual(
                subset_metadata["presentation_links"][0]["shared_context"][
                    "selected_root_ids"
                ],
                plan["active_subset_focus_targets"]["selected_root_ids"],
            )

            propagation_metadata = propagation_preset["presentation_state_patch"][
                "rehearsal_metadata"
            ]
            self.assertEqual(
                propagation_metadata["camera_choreography"]["timing"][
                    "recommended_sample_index"
                ],
                2,
            )
            self.assertEqual(
                propagation_metadata["emphasis_state"]["overlay_ids_by_pane"][
                    "time_series"
                ],
                [SHARED_READOUT_ACTIVITY_OVERLAY_ID],
            )
            self.assertEqual(
                sorted(
                    propagation_metadata["showcase_ui_state"]["runtime_mode_variants"]
                ),
                ["guided_autoplay", "presenter_rehearsal"],
            )

    def test_planning_fails_clearly_for_unsupported_preset_overlay_and_missing_highlight_review(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))

            with self.assertRaises(ValueError) as overlay_ctx:
                resolve_showcase_session_plan(
                    config_path=fixture["config_path"],
                    dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                    saved_preset_overrides={
                        PAIRED_COMPARISON_PRESET_ID: {
                            "presentation_state_patch": {
                                "dashboard_state_patch": {
                                    "global_interaction_state": {
                                        "active_overlay_id": "unsupported_overlay",
                                    },
                                },
                            },
                        },
                    },
                )

            self.assertIn("references unavailable overlay", str(overlay_ctx.exception))

            review_handoff_path = discover_validation_bundle_paths(
                fixture["validation_bundle_metadata"]
            )[REVIEW_HANDOFF_ARTIFACT_ID]
            review_handoff_path.unlink()

            with self.assertRaises(ValueError) as highlight_ctx:
                resolve_showcase_session_plan(
                    config_path=fixture["config_path"],
                    dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                    highlight_override={
                        "phenomenon_id": "phase_alignment_focus",
                        "locator": "wave_only_diagnostics.phase_map_references[0]",
                        "citation_label": "Approved phase alignment",
                    },
                )

            self.assertIn(
                "validation review_handoff artifact is unavailable",
                str(highlight_ctx.exception),
            )

    def test_planning_fails_clearly_for_showcase_pair_loss_and_timebase_loss(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))

            dashboard_payload_path = Path(
                fixture["dashboard_package"]["session_payload_path"]
            ).resolve()
            payload = json.loads(dashboard_payload_path.read_text(encoding="utf-8"))
            payload["selected_bundle_pair"]["wave"]["arm_id"] = payload[
                "selected_bundle_pair"
            ]["baseline"]["arm_id"]
            write_json(payload, dashboard_payload_path)

            with self.assertRaises(ValueError) as pair_ctx:
                resolve_showcase_session_plan(
                    config_path=fixture["config_path"],
                    dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                    suite_package_metadata_path=fixture["suite_package_metadata_path"],
                    suite_review_summary_path=fixture["suite_review_summary_path"],
                )

            self.assertIn(
                "distinct baseline-versus-wave arm pair",
                str(pair_ctx.exception),
            )

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))

            dashboard_payload_path = Path(
                fixture["dashboard_package"]["session_payload_path"]
            ).resolve()
            payload = json.loads(dashboard_payload_path.read_text(encoding="utf-8"))
            payload["pane_inputs"]["time_series"]["replay_model"][
                "shared_timebase_status"
            ] = {
                "availability": "unavailable",
                "reason": "fixture removed the shared timebase for showcase validation",
            }
            for status in payload["pane_inputs"]["time_series"]["replay_model"][
                "comparison_mode_statuses"
            ]:
                if status["comparison_mode_id"] == "paired_baseline_vs_wave":
                    status["availability"] = "unavailable"
                    status["reason"] = "shared timebase unavailable"
            write_json(payload, dashboard_payload_path)

            with self.assertRaises(ValueError) as timebase_ctx:
                resolve_showcase_session_plan(
                    config_path=fixture["config_path"],
                    dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                    suite_package_metadata_path=fixture["suite_package_metadata_path"],
                    suite_review_summary_path=fixture["suite_review_summary_path"],
                )

            self.assertIn(
                "shared baseline-versus-wave timebase",
                str(timebase_ctx.exception),
            )

    def test_planning_fails_clearly_for_dashboard_state_bundle_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))

            dashboard_state_path = Path(
                fixture["dashboard_package"]["session_state_path"]
            ).resolve()
            state = json.loads(dashboard_state_path.read_text(encoding="utf-8"))
            state["bundle_reference"]["bundle_id"] = "dashboard_session.v1:fixture:mismatch"
            write_json(state, dashboard_state_path)

            with self.assertRaises(ValueError) as mismatch_ctx:
                resolve_showcase_session_plan(
                    config_path=fixture["config_path"],
                    dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                    suite_package_metadata_path=fixture["suite_package_metadata_path"],
                    suite_review_summary_path=fixture["suite_review_summary_path"],
                )

            self.assertIn(
                "dashboard_session metadata and state must reference the same bundle_id",
                str(mismatch_ctx.exception),
            )


def _saved_preset(plan: dict[str, Any], preset_id: str) -> dict[str, Any]:
    return next(item for item in plan["saved_presets"] if item["preset_id"] == preset_id)


def _showcase_step(plan: dict[str, Any], step_id: str) -> dict[str, Any]:
    return next(item for item in plan["narrative_step_sequence"] if item["step_id"] == step_id)
