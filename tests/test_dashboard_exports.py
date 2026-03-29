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

from flywire_wave.dashboard_exports import execute_dashboard_export
from flywire_wave.dashboard_session_contract import (
    ANALYSIS_PANE_ID,
    METRICS_EXPORT_TARGET_ID,
    PANE_SNAPSHOT_EXPORT_TARGET_ID,
    PHASE_MAP_REFERENCE_OVERLAY_ID,
    REPLAY_FRAME_SEQUENCE_EXPORT_TARGET_ID,
    REVIEWER_FINDINGS_OVERLAY_ID,
    SCENE_PANE_ID,
)
from flywire_wave.dashboard_session_planning import (
    package_dashboard_session,
    resolve_dashboard_session_plan,
)

try:
    from test_dashboard_session_planning import _materialize_dashboard_fixture
except ModuleNotFoundError:
    from tests.test_dashboard_session_planning import _materialize_dashboard_fixture


class DashboardExportsTest(unittest.TestCase):
    def test_fixture_exports_are_deterministic_and_discoverable(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_dashboard_fixture(Path(tmp_dir_str))
            plan = resolve_dashboard_session_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )
            packaged = package_dashboard_session(plan)
            metadata_path = Path(packaged["metadata_path"]).resolve()

            snapshot_first = execute_dashboard_export(
                dashboard_session_metadata_path=metadata_path,
                export_target_id=PANE_SNAPSHOT_EXPORT_TARGET_ID,
                pane_id=ANALYSIS_PANE_ID,
                active_overlay_id=PHASE_MAP_REFERENCE_OVERLAY_ID,
                sample_index=3,
            )
            snapshot_second = execute_dashboard_export(
                dashboard_session_metadata_path=metadata_path,
                export_target_id=PANE_SNAPSHOT_EXPORT_TARGET_ID,
                pane_id=ANALYSIS_PANE_ID,
                active_overlay_id=PHASE_MAP_REFERENCE_OVERLAY_ID,
                sample_index=3,
            )
            self.assertEqual(
                snapshot_first["metadata_path"],
                snapshot_second["metadata_path"],
            )
            self.assertEqual(
                snapshot_first["artifact_inventory"],
                snapshot_second["artifact_inventory"],
            )
            snapshot_png = Path(snapshot_first["artifact_inventory"][0]["path"]).resolve()
            self.assertTrue(snapshot_png.exists())
            self.assertGreater(snapshot_png.stat().st_size, 0)

            metrics_first = execute_dashboard_export(
                dashboard_session_metadata_path=metadata_path,
                export_target_id=METRICS_EXPORT_TARGET_ID,
                pane_id=ANALYSIS_PANE_ID,
                active_overlay_id=REVIEWER_FINDINGS_OVERLAY_ID,
                sample_index=2,
            )
            metrics_second = execute_dashboard_export(
                dashboard_session_metadata_path=metadata_path,
                export_target_id=METRICS_EXPORT_TARGET_ID,
                pane_id=ANALYSIS_PANE_ID,
                active_overlay_id=REVIEWER_FINDINGS_OVERLAY_ID,
                sample_index=2,
            )
            self.assertEqual(
                metrics_first["metadata_path"],
                metrics_second["metadata_path"],
            )
            metrics_json = Path(metrics_first["artifact_inventory"][0]["path"]).resolve()
            self.assertTrue(metrics_json.exists())
            metrics_payload = json.loads(metrics_json.read_text(encoding="utf-8"))
            self.assertEqual(
                metrics_payload["summary"]["active_overlay_id"],
                REVIEWER_FINDINGS_OVERLAY_ID,
            )
            self.assertEqual(
                metrics_payload["summary"]["open_finding_count"],
                1,
            )
            self.assertGreater(
                metrics_payload["summary"]["phase_map_reference_count"],
                0,
            )
            self.assertEqual(
                metrics_first["summary"],
                metrics_payload["summary"],
            )

            replay_first = execute_dashboard_export(
                dashboard_session_metadata_path=metadata_path,
                export_target_id=REPLAY_FRAME_SEQUENCE_EXPORT_TARGET_ID,
                pane_id=SCENE_PANE_ID,
            )
            replay_second = execute_dashboard_export(
                dashboard_session_metadata_path=metadata_path,
                export_target_id=REPLAY_FRAME_SEQUENCE_EXPORT_TARGET_ID,
                pane_id=SCENE_PANE_ID,
            )
            self.assertEqual(
                replay_first["metadata_path"],
                replay_second["metadata_path"],
            )
            replay_manifest = Path(replay_first["artifact_inventory"][0]["path"]).resolve()
            self.assertTrue(replay_manifest.exists())
            replay_payload = json.loads(replay_manifest.read_text(encoding="utf-8"))
            self.assertGreater(replay_payload["frame_count"], 0)
            self.assertEqual(
                replay_payload["frame_count"],
                replay_first["summary"]["frame_count"],
            )
            first_frame = Path(replay_payload["frame_records"][0]["path"]).resolve()
            self.assertTrue(first_frame.exists())
            self.assertGreater(first_frame.stat().st_size, 0)

            metadata_payload = json.loads(
                Path(metrics_first["metadata_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(
                metadata_payload["export_target"]["export_target_id"],
                METRICS_EXPORT_TARGET_ID,
            )
            self.assertEqual(
                metadata_payload["summary"]["open_finding_count"],
                1,
            )


if __name__ == "__main__":
    unittest.main()
