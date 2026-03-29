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

from flywire_wave.dashboard_scene_circuit import resolve_dashboard_scene_context
from flywire_wave.dashboard_session_planning import (
    package_dashboard_session,
    resolve_dashboard_session_plan,
)
from flywire_wave.retinal_bundle import record_retinal_bundle
from flywire_wave.retinal_geometry import resolve_retinal_geometry_spec
from flywire_wave.retinal_sampling import AnalyticVisualFieldSource, project_visual_source

try:
    from test_dashboard_session_planning import _materialize_dashboard_fixture
except ModuleNotFoundError:
    from tests.test_dashboard_session_planning import _materialize_dashboard_fixture


class DashboardSceneCircuitTest(unittest.TestCase):
    def test_dashboard_fixture_exposes_deterministic_scene_and_circuit_payloads(self) -> None:
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

            self.assertEqual(first["pane_inputs"]["scene"], second["pane_inputs"]["scene"])
            self.assertEqual(first["pane_inputs"]["circuit"], second["pane_inputs"]["circuit"])

            scene = first["pane_inputs"]["scene"]
            self.assertEqual(scene["render_status"], "available")
            self.assertEqual(scene["frame_discovery"]["replay_source"], "descriptor_regeneration")
            self.assertEqual(scene["frame_discovery"]["artifact_kind"], "descriptor_metadata")
            self.assertGreater(len(scene["replay_frames"]), 0)
            self.assertEqual(
                scene["replay_frames"][0]["encoding"],
                "base64_uint8_grayscale_row_major",
            )

            circuit = first["pane_inputs"]["circuit"]
            self.assertEqual(circuit["context_version"], "dashboard_circuit_context.v1")
            self.assertEqual(
                circuit["connectivity_context"]["network_summary"]["selected_root_count"],
                2,
            )
            self.assertEqual(
                circuit["connectivity_context"]["network_summary"]["edge_count"],
                2,
            )
            self.assertEqual(
                circuit["root_catalog"][0]["linked_selection"]["select"]["selected_neuron_id"],
                101,
            )
            self.assertEqual(
                circuit["root_catalog"][0]["linked_selection"]["hover"]["hovered_neuron_id"],
                101,
            )
            first_edge = circuit["connectivity_context"]["edge_catalog"][0]
            self.assertEqual(
                (first_edge["pre_root_id"], first_edge["post_root_id"]),
                (101, 202),
            )
            self.assertEqual(first_edge["synapse_count"], 1)
            self.assertTrue(first_edge["edge_bundle_exists"])

    def test_retinal_scene_context_reports_unavailable_archive_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            geometry = _build_forward_fixture_geometry()
            source = AnalyticVisualFieldSource(
                source_family="fixture_scene",
                source_name="constant_half",
                width_deg=240.0,
                height_deg=180.0,
                source_metadata={"scene_rule": "constant_scalar_field"},
                field_sampler=lambda time_ms, azimuth_deg, elevation_deg: 0.35,
            )
            projection = project_visual_source(
                retinal_geometry=geometry,
                visual_source=source,
                frame_times_ms=[0.0, 10.0, 20.0],
                sampling_kernel={
                    "acceptance_angle_deg": 1.5,
                    "support_radius_deg": 3.0,
                    "background_fill_value": 0.35,
                },
            )
            recorded = record_retinal_bundle(
                projection_result=projection,
                processed_retinal_dir=tmp_dir / "retinal",
            )
            metadata_path = Path(recorded["retinal_bundle_metadata_path"]).resolve()
            archive_path = Path(recorded["frame_archive_path"]).resolve()

            available = resolve_dashboard_scene_context(
                source_kind="retinal_bundle",
                metadata_path=metadata_path,
                selected_condition_ids=[],
            )
            self.assertEqual(available["render_status"], "available")
            self.assertEqual(available["frame_discovery"]["replay_source"], "frame_archive")
            self.assertEqual(len(available["replay_frames"]), 3)

            archive_path.unlink()
            unavailable = resolve_dashboard_scene_context(
                source_kind="retinal_bundle",
                metadata_path=metadata_path,
                selected_condition_ids=[],
            )
            self.assertEqual(unavailable["render_status"], "unavailable")
            self.assertEqual(unavailable["replay_frames"], [])
            self.assertIn(
                "missing",
                str(unavailable["frame_discovery"]["unavailable_reason"]).lower(),
            )

    def test_packaged_bootstrap_carries_scene_and_circuit_linkage(self) -> None:
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
            bootstrap = _extract_embedded_json(html_text, script_id="dashboard-app-bootstrap")

            self.assertEqual(
                bootstrap["state_model"]["transient_state_fields"],
                ["hovered_neuron_id", "hover_source_pane_id"],
            )
            self.assertEqual(bootstrap["scene_context"]["render_status"], "available")
            self.assertEqual(
                bootstrap["scene_context"]["frame_discovery"]["replay_source"],
                "descriptor_regeneration",
            )
            self.assertEqual(
                bootstrap["circuit_context"]["connectivity_context"]["node_catalog"][0][
                    "linked_selection"
                ]["hover"]["hovered_neuron_id"],
                101,
            )
            self.assertEqual(
                bootstrap["circuit_context"]["connectivity_context"]["node_catalog"][0][
                    "linked_selection"
                ]["select"]["selected_neuron_id"],
                101,
            )
            self.assertIn('data-pane-id="scene"', html_text)


def _build_forward_fixture_geometry():
    return resolve_retinal_geometry_spec(
        {
            "retinal_geometry": {
                "geometry_name": "fixture",
                "eyes": {
                    "left": {
                        "optical_axis_head": [1.0, 0.0, 0.0],
                        "torsion_deg": 0.0,
                    },
                    "symmetry": {
                        "mode": "mirror_across_head_sagittal_plane",
                    },
                },
            }
        }
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
