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

from flywire_wave.dashboard_scene_circuit import (
    load_dashboard_whole_brain_context,
    resolve_dashboard_scene_context,
)
from flywire_wave.dashboard_session_planning import (
    package_dashboard_session,
    resolve_dashboard_session_plan,
)
from flywire_wave.retinal_bundle import record_retinal_bundle
from flywire_wave.retinal_geometry import resolve_retinal_geometry_spec
from flywire_wave.retinal_sampling import AnalyticVisualFieldSource, project_visual_source
from flywire_wave.whole_brain_context_planning import (
    package_whole_brain_context_session,
    resolve_whole_brain_context_session_plan,
)

try:
    from test_dashboard_session_planning import _materialize_dashboard_fixture
except ModuleNotFoundError:
    from tests.test_dashboard_session_planning import _materialize_dashboard_fixture

try:
    from showcase_test_support import _materialize_packaged_showcase_fixture
except ModuleNotFoundError:
    from tests.showcase_test_support import _materialize_packaged_showcase_fixture

try:
    from test_whole_brain_context_planning import (
        _fixture_synapse_registry_reference,
        _write_context_review_metadata_fixture,
        _write_context_review_synapse_registry,
    )
except ModuleNotFoundError:
    from tests.test_whole_brain_context_planning import (
        _fixture_synapse_registry_reference,
        _write_context_review_metadata_fixture,
        _write_context_review_synapse_registry,
    )


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

    def test_dashboard_packages_whole_brain_context_bridge_with_overview_and_focus(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))
            context_package = _package_fixture_whole_brain_context(fixture, Path(tmp_dir_str))

            default_plan = resolve_dashboard_session_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
            )
            context_plan = resolve_dashboard_session_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                whole_brain_context_metadata_path=context_package["metadata_path"],
            )

            self.assertNotEqual(
                default_plan["dashboard_session"]["session_spec_hash"],
                context_plan["dashboard_session"]["session_spec_hash"],
            )

            whole_brain = context_plan["pane_inputs"]["circuit"]["whole_brain_context"]
            self.assertIn(whole_brain["availability"], {"available", "partial"})
            representation_by_id = {
                item["representation_id"]: item
                for item in whole_brain["representation_catalog"]
            }
            self.assertEqual(sorted(representation_by_id), ["focused", "overview"])
            self.assertEqual(
                representation_by_id["overview"]["availability"],
                "available",
            )
            self.assertEqual(
                representation_by_id["focused"]["availability"],
                "available",
            )
            self.assertEqual(
                representation_by_id["overview"]["summary"]["interaction_flow_count"],
                6,
            )
            self.assertIn(
                "bidirectional_context_graph",
                {
                    item["overlay_id"]
                    for item in representation_by_id["overview"][
                        "overlay_workflow_catalog"
                    ]
                },
            )
            self.assertTrue(
                {"cell_class", "neuropil"}.issubset(
                    {
                        item["metadata_facet_id"]
                        for item in representation_by_id["overview"][
                            "metadata_facet_group_catalog"
                        ]
                    }
                )
            )
            self.assertGreater(
                representation_by_id["focused"]["pathway_explanation_catalog"][0][
                    "card_count"
                ],
                0,
            )

            overview_styles = {
                str(item["style_variant"])
                for item in representation_by_id["overview"]["node_catalog"]
            }
            focused_styles = {
                str(item["style_variant"])
                for item in representation_by_id["focused"]["node_catalog"]
            }
            self.assertIn("active_selected", overview_styles)
            self.assertIn("context_only", overview_styles)
            self.assertTrue(
                "context_pathway_highlight" in focused_styles
                or "active_pathway_highlight" in focused_styles
            )

            context_only_node = next(
                item
                for item in representation_by_id["overview"]["node_catalog"]
                if str(item["style_variant"]) == "context_only"
            )
            self.assertIsNone(context_only_node["linked_selection"]["select"])
            self.assertEqual(
                context_only_node["linked_selection"]["hover"]["hovered_neuron_id"],
                context_only_node["root_id"],
            )

            active_node = next(
                item
                for item in representation_by_id["overview"]["node_catalog"]
                if str(item["style_variant"]) in {"active_selected", "active_pathway_highlight"}
            )
            self.assertEqual(
                active_node["linked_selection"]["select"]["selected_neuron_id"],
                active_node["root_id"],
            )

            packaged = package_dashboard_session(context_plan)
            html_text = Path(packaged["app_shell_path"]).read_text(encoding="utf-8")
            bootstrap = _extract_embedded_json(html_text, script_id="dashboard-app-bootstrap")
            self.assertEqual(
                bootstrap["circuit_context"]["whole_brain_context"]["representation_catalog"][0][
                    "representation_id"
                ],
                "overview",
            )
            self.assertTrue(
                str(bootstrap["links"]["whole_brain_context_metadata"]).endswith(
                    "whole_brain_context_session.json"
                )
            )
            self.assertTrue(
                str(bootstrap["links"]["whole_brain_context_view_payload"]).endswith(
                    "context_view_payload.json"
                )
            )

    def test_whole_brain_context_bridge_handles_oversized_and_missing_payloads_honestly(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))
            context_package = _package_fixture_whole_brain_context(fixture, Path(tmp_dir_str))

            oversized = load_dashboard_whole_brain_context(
                metadata_path=context_package["metadata_path"],
                selected_root_ids=[101, 202],
                max_overview_node_count=2,
                max_overview_edge_count=1,
            )
            oversized_overview = next(
                item
                for item in oversized["representation_catalog"]
                if item["representation_id"] == "overview"
            )
            self.assertEqual(oversized_overview["availability"], "summary_only")
            self.assertEqual(oversized_overview["node_catalog"], [])
            self.assertIn("render budget", str(oversized_overview["reason"]))

            Path(context_package["context_view_payload_path"]).unlink()
            unavailable = load_dashboard_whole_brain_context(
                metadata_path=context_package["metadata_path"],
                selected_root_ids=[101, 202],
            )
            self.assertEqual(unavailable["availability"], "unavailable")
            self.assertIn("payload", str(unavailable["reason"]).lower())
            self.assertTrue(
                all(
                    str(item["availability"]) == "unavailable"
                    for item in unavailable["representation_catalog"]
                )
            )


def _package_fixture_whole_brain_context(
    fixture: dict[str, object],
    tmp_dir: Path,
) -> dict[str, object]:
    _write_context_review_metadata_fixture(fixture["config_path"])
    synapse_registry_path = tmp_dir / "context_review_fixture" / "local_synapse_registry.csv"
    _write_context_review_synapse_registry(synapse_registry_path)
    plan = resolve_whole_brain_context_session_plan(
        config_path=fixture["config_path"],
        dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
        explicit_artifact_references=[
            _fixture_synapse_registry_reference(
                fixture["config_path"],
                path=synapse_registry_path,
            )
        ],
    )
    return package_whole_brain_context_session(plan)


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
