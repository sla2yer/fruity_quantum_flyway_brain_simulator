from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.dashboard_replay import (
    build_dashboard_replay_model,
    resolve_dashboard_time_series_view_model,
)
from flywire_wave.dashboard_session_planning import resolve_dashboard_session_plan

try:
    from test_dashboard_session_planning import _materialize_dashboard_fixture
except ModuleNotFoundError:
    from tests.test_dashboard_session_planning import _materialize_dashboard_fixture


class DashboardReplayTest(unittest.TestCase):
    def test_fixture_time_series_context_carries_canonical_replay_and_fairness_boundary(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))
            plan = resolve_dashboard_session_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )

            time_series = plan["pane_inputs"]["time_series"]

            self.assertEqual(
                time_series["context_version"],
                "dashboard_time_series_context.v1",
            )
            self.assertEqual(
                time_series["replay_model"]["format_version"],
                "dashboard_replay_model.v1",
            )
            self.assertEqual(
                time_series["replay_model"]["shared_timebase_status"]["availability"],
                "available",
            )
            self.assertEqual(
                time_series["shared_trace_catalog"][0]["scope_label"],
                "shared_comparison",
            )
            self.assertEqual(
                time_series["selection_catalog"][0]["wave_diagnostic"]["scope_label"],
                "wave_only_diagnostic",
            )
            self.assertTrue(
                time_series["selection_catalog"][1]["wave_diagnostic"][
                    "aligned_to_shared_timebase"
                ]
            )
            self.assertEqual(
                time_series["replay_model"]["comparison_mode_statuses"],
                [
                    {
                        "comparison_mode_id": "single_arm",
                        "availability": "available",
                        "reason": None,
                    },
                    {
                        "comparison_mode_id": "paired_baseline_vs_wave",
                        "availability": "available",
                        "reason": None,
                    },
                    {
                        "comparison_mode_id": "paired_delta",
                        "availability": "available",
                        "reason": None,
                    },
                ],
            )

    def test_fixture_view_model_tracks_cursor_and_comparison_modes(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))
            plan = resolve_dashboard_session_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )
            time_series = plan["pane_inputs"]["time_series"]

            paired = resolve_dashboard_time_series_view_model(
                time_series,
                selected_neuron_id=202,
                selected_readout_id="shared_output_mean",
                comparison_mode="paired_baseline_vs_wave",
                active_arm_id="surface_wave_intact",
                sample_index=2,
            )
            self.assertEqual(
                [item["series_id"] for item in paired["shared_comparison"]["chart_series"]],
                ["baseline", "wave"],
            )
            self.assertGreater(
                paired["shared_comparison"]["wave_value"],
                paired["shared_comparison"]["baseline_value"],
            )
            self.assertEqual(
                paired["wave_diagnostic"]["scope_label"],
                "wave_only_diagnostic",
            )
            self.assertEqual(
                paired["cursor"]["time_ms"],
                time_series["replay_model"]["canonical_time_ms"][2],
            )

            delta = resolve_dashboard_time_series_view_model(
                time_series,
                selected_neuron_id=202,
                selected_readout_id="shared_output_mean",
                comparison_mode="paired_delta",
                active_arm_id="surface_wave_intact",
                sample_index=2,
            )
            self.assertEqual(
                [item["series_id"] for item in delta["shared_comparison"]["chart_series"]],
                ["delta"],
            )
            self.assertIn(
                "does not absorb wave-only diagnostics",
                delta["shared_comparison"]["fairness_note"],
            )

            single_arm = resolve_dashboard_time_series_view_model(
                time_series,
                selected_neuron_id=101,
                selected_readout_id="shared_output_mean",
                comparison_mode="single_arm",
                active_arm_id="baseline_p0_intact",
                sample_index=2,
            )
            self.assertEqual(
                [item["series_id"] for item in single_arm["shared_comparison"]["chart_series"]],
                ["baseline"],
            )
            self.assertEqual(
                single_arm["selected_root"]["root_id"],
                101,
            )

    def test_replay_state_serialization_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))

            first = resolve_dashboard_session_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )
            second = resolve_dashboard_session_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )

            self.assertEqual(
                first["dashboard_session_state"]["replay_state"],
                second["dashboard_session_state"]["replay_state"],
            )
            self.assertEqual(
                first["dashboard_session_state"]["replay_state"]["comparison_mode"],
                "paired_baseline_vs_wave",
            )
            self.assertEqual(
                first["dashboard_session_state"]["replay_state"]["time_cursor"]["sample_index"],
                0,
            )
            self.assertEqual(
                first["dashboard_session_state"]["replay_state"]["timebase_signature"],
                first["pane_inputs"]["time_series"]["replay_model"]["timebase_signature"],
            )

    def test_view_model_fails_clearly_for_incompatible_shared_timebase_requests(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))
            plan = resolve_dashboard_session_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )
            time_series = copy.deepcopy(plan["pane_inputs"]["time_series"])
            invalid_replay_model = build_dashboard_replay_model(
                baseline_arm_id="baseline_p0_intact",
                wave_arm_id="surface_wave_intact",
                baseline_timebase=time_series["timebase"],
                wave_timebase={
                    **copy.deepcopy(dict(time_series["timebase"])),
                    "dt_ms": 20.0,
                    "duration_ms": 140.0,
                },
            )
            time_series["replay_model"] = invalid_replay_model

            with self.assertRaises(ValueError) as ctx:
                resolve_dashboard_time_series_view_model(
                    time_series,
                    selected_neuron_id=101,
                    selected_readout_id="shared_output_mean",
                    comparison_mode="paired_baseline_vs_wave",
                    active_arm_id="surface_wave_intact",
                    sample_index=1,
                )

            self.assertIn(
                "canonical shared timebase",
                str(ctx.exception),
            )


if __name__ == "__main__":
    unittest.main()
