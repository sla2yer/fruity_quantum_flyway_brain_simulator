from __future__ import annotations

import html
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.dashboard_analysis import resolve_dashboard_analysis_view_model
from flywire_wave.dashboard_session_contract import (
    ANALYSIS_PANE_ID,
    METRICS_EXPORT_TARGET_ID,
    PHASE_MAP_REFERENCE_OVERLAY_ID,
    REVIEWER_FINDINGS_OVERLAY_ID,
)
from flywire_wave.dashboard_session_planning import (
    package_dashboard_session,
    resolve_dashboard_session_plan,
)

try:
    from test_dashboard_session_planning import _materialize_dashboard_fixture
except ModuleNotFoundError:
    from tests.test_dashboard_session_planning import _materialize_dashboard_fixture


class DashboardAnalysisTest(unittest.TestCase):
    def test_fixture_analysis_context_surfaces_packaged_cards_matrices_and_validation(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))
            plan = resolve_dashboard_session_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )

            analysis = plan["pane_inputs"][ANALYSIS_PANE_ID]

            self.assertEqual(
                analysis["context_version"],
                "dashboard_analysis_context.v1",
            )
            self.assertGreater(
                analysis["summary_counts"]["task_summary_card_count"],
                0,
            )
            self.assertGreater(
                analysis["summary_counts"]["matrix_view_count"],
                0,
            )
            self.assertGreater(
                analysis["summary_counts"]["validator_summary_count"],
                0,
            )
            self.assertEqual(
                analysis["validation"]["review_status"],
                "review",
            )
            self.assertIn(
                "shared_task_rollup_matrix",
                [
                    item["matrix_id"]
                    for item in analysis["shared_comparison"]["matrix_views"]
                ],
            )
            self.assertGreater(
                len(analysis["wave_only_diagnostics"]["phase_map_references"]),
                0,
            )
            self.assertEqual(
                analysis["supported_export_target_ids"],
                [
                    "session_state_json",
                    "pane_snapshot_png",
                    "metrics_json",
                ],
            )

    def test_view_model_normalizes_shared_wave_validation_and_inapplicable_overlays(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))
            plan = resolve_dashboard_session_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )
            analysis = plan["pane_inputs"][ANALYSIS_PANE_ID]
            time_series = plan["pane_inputs"]["time_series"]

            shared_view = resolve_dashboard_analysis_view_model(
                analysis,
                time_series_context=time_series,
                selected_neuron_id=101,
                selected_readout_id="shared_output_mean",
                comparison_mode="paired_baseline_vs_wave",
                active_arm_id="surface_wave_intact",
                active_overlay_id="shared_readout_activity",
                sample_index=2,
            )
            self.assertEqual(
                shared_view["active_overlay"]["availability"],
                "available",
            )
            self.assertEqual(
                shared_view["active_overlay"]["scope_label"],
                "shared_comparison",
            )
            self.assertGreater(
                shared_view["active_overlay"]["wave_value"],
                shared_view["active_overlay"]["baseline_value"],
            )

            reviewer_view = resolve_dashboard_analysis_view_model(
                analysis,
                time_series_context=time_series,
                selected_neuron_id=101,
                selected_readout_id="shared_output_mean",
                comparison_mode="paired_baseline_vs_wave",
                active_arm_id="surface_wave_intact",
                active_overlay_id=REVIEWER_FINDINGS_OVERLAY_ID,
                sample_index=2,
            )
            self.assertEqual(
                reviewer_view["active_overlay"]["scope_label"],
                "validation_evidence",
            )
            self.assertEqual(
                len(reviewer_view["active_overlay"]["open_findings"]),
                1,
            )

            phase_map_view = resolve_dashboard_analysis_view_model(
                analysis,
                time_series_context=time_series,
                selected_neuron_id=101,
                selected_readout_id="shared_output_mean",
                comparison_mode="paired_baseline_vs_wave",
                active_arm_id="surface_wave_intact",
                active_overlay_id=PHASE_MAP_REFERENCE_OVERLAY_ID,
                sample_index=2,
            )
            self.assertEqual(
                phase_map_view["active_overlay"]["scope_label"],
                "wave_only_diagnostic",
            )
            self.assertGreaterEqual(
                phase_map_view["active_overlay"]["matching_phase_map_count"],
                1,
            )

            inapplicable_view = resolve_dashboard_analysis_view_model(
                analysis,
                time_series_context=time_series,
                selected_neuron_id=101,
                selected_readout_id="shared_output_mean",
                comparison_mode="paired_baseline_vs_wave",
                active_arm_id="surface_wave_intact",
                active_overlay_id="selected_subset_highlight",
                sample_index=2,
            )
            self.assertEqual(
                inapplicable_view["active_overlay"]["availability"],
                "inapplicable",
            )
            self.assertIn(
                "another pane",
                str(inapplicable_view["active_overlay"]["reason"]).lower(),
            )

    def test_packaged_bootstrap_embeds_rich_analysis_context_and_export_catalog(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))
            plan = resolve_dashboard_session_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )

            packaged = package_dashboard_session(plan)
            html_text = Path(packaged["app_shell_path"]).read_text(encoding="utf-8")
            bootstrap = _extract_embedded_json(
                html_text,
                script_id="dashboard-app-bootstrap",
            )

            self.assertGreater(
                len(bootstrap["analysis_context"]["shared_comparison"]["task_summary_cards"]),
                0,
            )
            self.assertGreater(
                len(bootstrap["analysis_context"]["validation_evidence"]["validator_summaries"]),
                0,
            )
            self.assertIn(
                METRICS_EXPORT_TARGET_ID,
                [
                    item["export_target_id"]
                    for item in bootstrap["export_target_catalog"]
                ],
            )


def _extract_embedded_json(html_text: str, *, script_id: str) -> dict[str, object]:
    match = re.search(
        rf'<script id="{re.escape(script_id)}" type="application/json">(.*?)</script>',
        html_text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"Could not find JSON script tag {script_id!r}.")
    return json.loads(html.unescape(match.group(1)))


if __name__ == "__main__":
    unittest.main()
