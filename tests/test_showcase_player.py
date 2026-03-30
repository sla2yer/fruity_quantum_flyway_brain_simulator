from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.io_utils import write_json
from flywire_wave.showcase_player import (
    GUIDED_AUTOPLAY_MODE,
    PRESENTER_REHEARSAL_MODE,
    SHOWCASE_PLAYER_RUNTIME_VERSION,
    apply_showcase_player_command,
    execute_showcase_player_command,
    load_showcase_player_context,
    resolve_showcase_player_state,
    write_showcase_player_state,
)
from flywire_wave.showcase_session_contract import (
    ACTIVITY_PROPAGATION_STEP_ID,
    ANALYSIS_SUMMARY_PRESET_ID,
    APPROVED_WAVE_HIGHLIGHT_STEP_ID,
    BASELINE_WAVE_COMPARISON_STEP_ID,
    SCENE_CONTEXT_PRESET_ID,
    SCENE_SELECTION_STEP_ID,
    SUMMARY_ANALYSIS_STEP_ID,
)
from flywire_wave.showcase_session_planning import (
    SHOWCASE_FIXTURE_MODE_REHEARSAL,
    package_showcase_session,
    resolve_showcase_session_plan,
)

try:
    from tests.test_showcase_session_planning import (
        _approve_validation_highlight,
        _materialize_packaged_showcase_fixture,
    )
except ModuleNotFoundError:
    from test_showcase_session_planning import (  # type: ignore[no-redef]
        _approve_validation_highlight,
        _materialize_packaged_showcase_fixture,
    )


class ShowcasePlayerTest(unittest.TestCase):
    def test_packaged_showcase_player_drives_controls_and_resume_state_deterministically(
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
            )
            packaged = package_showcase_session(plan)
            context = load_showcase_player_context(packaged["metadata_path"])
            initial_state = resolve_showcase_player_state(context)
            script_payload = json.loads(
                Path(packaged["showcase_script_path"]).read_text(encoding="utf-8")
            )

            self.assertEqual(
                initial_state["runtime_version"],
                SHOWCASE_PLAYER_RUNTIME_VERSION,
            )
            self.assertEqual(
                initial_state["available_step_ids"],
                [
                    "scene_selection",
                    "fly_view_input",
                    "active_visual_subset",
                    "activity_propagation",
                    "baseline_wave_comparison",
                    "approved_wave_highlight",
                    "summary_analysis",
                ],
            )
            self.assertEqual(initial_state["current_step_id"], SCENE_SELECTION_STEP_ID)
            self.assertEqual(initial_state["current_preset_id"], SCENE_CONTEXT_PRESET_ID)
            self.assertEqual(
                initial_state["sequence_state"]["playback_state"],
                "paused",
            )
            self.assertFalse(initial_state["sequence_state"]["auto_advance"])
            self.assertEqual(
                script_payload["initial_checkpoint"],
                {
                    "step_id": "scene_selection",
                    "preset_id": "scene_context",
                    "runtime_mode": PRESENTER_REHEARSAL_MODE,
                },
            )
            self.assertIn("resume", script_payload["supported_commands"])
            self.assertIn(GUIDED_AUTOPLAY_MODE, script_payload["supported_runtime_modes"])

            propagation_state = apply_showcase_player_command(
                context,
                command="jump_to_step",
                state=initial_state,
                step_id=ACTIVITY_PROPAGATION_STEP_ID,
            )
            seeked_state = apply_showcase_player_command(
                context,
                command="seek",
                state=propagation_state,
                replay_sample_index=2,
            )
            self.assertEqual(seeked_state["current_step_id"], ACTIVITY_PROPAGATION_STEP_ID)
            self.assertEqual(seeked_state["replay_cursor_state"]["sample_index"], 2)
            self.assertEqual(
                seeked_state["resolved_dashboard_session_state"]["global_interaction_state"][
                    "time_cursor"
                ]["sample_index"],
                2,
            )
            self.assertEqual(
                seeked_state["resolved_dashboard_session_state"]["replay_state"][
                    "time_cursor"
                ]["sample_index"],
                2,
            )
            self.assertEqual(
                seeked_state["resolved_dashboard_session_state"]["global_interaction_state"][
                    "comparison_mode"
                ],
                seeked_state["resolved_dashboard_session_state"]["replay_state"][
                    "comparison_mode"
                ],
            )

            resumed_locally = apply_showcase_player_command(
                context,
                command="resume",
                state=seeked_state,
                runtime_mode=PRESENTER_REHEARSAL_MODE,
            )
            self.assertEqual(
                resumed_locally["current_step_id"],
                ACTIVITY_PROPAGATION_STEP_ID,
            )
            self.assertEqual(
                resumed_locally["sequence_state"]["playback_state"],
                "playing",
            )
            self.assertEqual(resumed_locally["replay_cursor_state"]["sample_index"], 2)

            checkpoint_path = Path(tmp_dir_str) / "resume_state.json"
            write_showcase_player_state(seeked_state, checkpoint_path)
            resume_result = execute_showcase_player_command(
                showcase_session_metadata_path=packaged["metadata_path"],
                command="resume",
                serialized_state_path=checkpoint_path,
                runtime_mode=GUIDED_AUTOPLAY_MODE,
                advance_steps=2,
            )
            resumed_from_disk = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            self.assertEqual(
                resume_result["current_step_id"],
                APPROVED_WAVE_HIGHLIGHT_STEP_ID,
            )
            self.assertEqual(
                resumed_from_disk["current_step_id"],
                APPROVED_WAVE_HIGHLIGHT_STEP_ID,
            )
            self.assertEqual(
                resumed_from_disk["runtime_mode"],
                GUIDED_AUTOPLAY_MODE,
            )
            self.assertEqual(
                resumed_from_disk["sequence_state"]["completed_step_ids"],
                [
                    "scene_selection",
                    "fly_view_input",
                    "active_visual_subset",
                    "activity_propagation",
                    "baseline_wave_comparison",
                ],
            )
            self.assertEqual(
                resumed_from_disk["sequence_state"]["visited_step_ids"],
                [
                    "scene_selection",
                    "activity_propagation",
                    "baseline_wave_comparison",
                    "approved_wave_highlight",
                ],
            )

            final_result = execute_showcase_player_command(
                showcase_session_metadata_path=packaged["metadata_path"],
                command="play",
                serialized_state_path=checkpoint_path,
                runtime_mode=GUIDED_AUTOPLAY_MODE,
                until_end=True,
            )
            final_state = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            self.assertEqual(final_result["current_step_id"], SUMMARY_ANALYSIS_STEP_ID)
            self.assertEqual(final_state["current_step_id"], SUMMARY_ANALYSIS_STEP_ID)
            self.assertEqual(
                final_state["sequence_state"]["playback_state"],
                "paused",
            )
            self.assertEqual(
                final_state["sequence_state"]["previous_step_id"],
                APPROVED_WAVE_HIGHLIGHT_STEP_ID,
            )
            self.assertTrue(final_state["sequence_state"]["end_of_sequence"])

            summary_preset_state = apply_showcase_player_command(
                context,
                command="jump_to_preset",
                state=initial_state,
                preset_id=ANALYSIS_SUMMARY_PRESET_ID,
            )
            self.assertEqual(summary_preset_state["current_step_id"], SUMMARY_ANALYSIS_STEP_ID)
            self.assertEqual(
                summary_preset_state["current_preset_id"],
                ANALYSIS_SUMMARY_PRESET_ID,
            )

            reset_state = apply_showcase_player_command(
                context,
                command="reset",
                state=final_state,
            )
            self.assertEqual(reset_state["current_step_id"], SCENE_SELECTION_STEP_ID)
            self.assertEqual(reset_state["current_preset_id"], SCENE_CONTEXT_PRESET_ID)
            self.assertEqual(
                reset_state["sequence_state"]["visited_step_ids"],
                [SCENE_SELECTION_STEP_ID],
            )

    def test_player_fails_clearly_for_unsupported_step_jump_and_incomplete_state(
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
            packaged = package_showcase_session(plan)
            context = load_showcase_player_context(packaged["metadata_path"])

            with self.assertRaises(ValueError) as jump_ctx:
                apply_showcase_player_command(
                    context,
                    command="jump_to_step",
                    step_id="unsupported_step",
                )

            self.assertIn("Unsupported step jump target", str(jump_ctx.exception))

            showcase_state_path = Path(packaged["showcase_state_path"]).resolve()
            broken_state = json.loads(showcase_state_path.read_text(encoding="utf-8"))
            broken_state.pop("base_dashboard_session_state", None)
            write_json(broken_state, showcase_state_path)

            with self.assertRaises(ValueError) as state_ctx:
                load_showcase_player_context(packaged["metadata_path"])

            self.assertIn(
                "base_dashboard_session_state must be present",
                str(state_ctx.exception),
            )


if __name__ == "__main__":
    unittest.main()
