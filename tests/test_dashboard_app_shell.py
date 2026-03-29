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

from flywire_wave.dashboard_session_contract import (
    ANALYSIS_PANE_ID,
    CIRCUIT_PANE_ID,
    MORPHOLOGY_PANE_ID,
    SCENE_PANE_ID,
    SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    TIME_SERIES_PANE_ID,
)
from flywire_wave.dashboard_session_planning import (
    package_dashboard_session,
    resolve_dashboard_session_plan,
)

try:
    from test_dashboard_session_planning import _materialize_dashboard_fixture
except ModuleNotFoundError:
    from tests.test_dashboard_session_planning import _materialize_dashboard_fixture


class DashboardAppShellTest(unittest.TestCase):
    def test_packaged_dashboard_shell_writes_stable_assets_and_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))
            plan = resolve_dashboard_session_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )

            packaged_first = package_dashboard_session(plan)
            packaged_second = package_dashboard_session(plan)

            self.assertEqual(
                Path(packaged_first["style_asset_path"]).name,
                Path(packaged_second["style_asset_path"]).name,
            )
            self.assertEqual(
                Path(packaged_first["script_asset_path"]).name,
                Path(packaged_second["script_asset_path"]).name,
            )
            self.assertRegex(
                Path(packaged_first["style_asset_path"]).name,
                r"^dashboard_shell\.[0-9a-f]{12}\.css$",
            )
            self.assertRegex(
                Path(packaged_first["script_asset_path"]).name,
                r"^dashboard_shell\.[0-9a-f]{12}\.js$",
            )

            asset_manifest = json.loads(
                Path(packaged_first["asset_manifest_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(
                asset_manifest["bundle_reference"]["bundle_id"],
                packaged_first["bundle_id"],
            )
            self.assertEqual(
                asset_manifest["assets"]["style"]["file_name"],
                Path(packaged_first["style_asset_path"]).name,
            )
            self.assertEqual(
                asset_manifest["assets"]["script"]["file_name"],
                Path(packaged_first["script_asset_path"]).name,
            )
            self.assertEqual(
                asset_manifest,
                json.loads(
                    Path(packaged_second["asset_manifest_path"]).read_text(encoding="utf-8")
                ),
            )

            html_text = Path(packaged_first["app_shell_path"]).read_text(encoding="utf-8")
            for pane_id in (
                SCENE_PANE_ID,
                CIRCUIT_PANE_ID,
                MORPHOLOGY_PANE_ID,
                TIME_SERIES_PANE_ID,
                ANALYSIS_PANE_ID,
            ):
                self.assertIn(f'data-pane-id="{pane_id}"', html_text)

            bootstrap = _extract_embedded_json(
                html_text,
                script_id="dashboard-app-bootstrap",
            )
            self.assertEqual(
                [item["pane_id"] for item in bootstrap["pane_catalog"]],
                [
                    SCENE_PANE_ID,
                    CIRCUIT_PANE_ID,
                    MORPHOLOGY_PANE_ID,
                    TIME_SERIES_PANE_ID,
                    ANALYSIS_PANE_ID,
                ],
            )
            self.assertEqual(
                bootstrap["state_model"]["owned_state_fields"],
                [
                    "selected_arm_pair",
                    "selected_neuron_id",
                    "selected_readout_id",
                    "active_overlay_id",
                    "comparison_mode",
                    "time_cursor",
                ],
            )
            self.assertEqual(
                bootstrap["state_model"]["serialized_state_fields"],
                ["global_interaction_state", "replay_state"],
            )
            self.assertEqual(
                bootstrap["overlay_catalog"]["active_overlay_id"],
                SHARED_READOUT_ACTIVITY_OVERLAY_ID,
            )
            self.assertEqual(
                bootstrap["global_interaction_state"]["time_cursor"]["playback_state"],
                "paused",
            )
            self.assertEqual(
                bootstrap["replay_model"]["shared_timebase_status"]["availability"],
                "available",
            )
            self.assertEqual(
                bootstrap["replay_state"]["comparison_mode"],
                "paired_baseline_vs_wave",
            )
            self.assertEqual(
                bootstrap["time_series_context"]["shared_trace_catalog"][0]["scope_label"],
                "shared_comparison",
            )
            self.assertEqual(
                bootstrap["links"]["dashboard_session_payload"],
                "../dashboard_session_payload.json",
            )
            self.assertIn(
                "analysis_offline_report",
                bootstrap["links"],
            )
            self.assertEqual(
                packaged_first["app_shell_file_url"],
                Path(packaged_first["app_shell_path"]).resolve().as_uri(),
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
