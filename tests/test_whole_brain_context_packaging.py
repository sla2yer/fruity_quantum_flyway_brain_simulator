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

from flywire_wave.showcase_session_planning import (
    package_showcase_session,
    resolve_showcase_session_plan,
)
from flywire_wave.whole_brain_context_planning import (
    DASHBOARD_HANDOFF_PRESET_ID,
    DEFAULT_CONTEXT_QUERY_PRESET_LIBRARY_ID,
    DOWNSTREAM_HALO_PRESET_ID,
    OVERVIEW_CONTEXT_PRESET_ID,
    PATHWAY_FOCUS_PRESET_ID,
    SHOWCASE_HANDOFF_PRESET_ID,
    UPSTREAM_HALO_PRESET_ID,
    WHOLE_BRAIN_CONTEXT_FIXTURE_MODE_REVIEW,
    discover_whole_brain_context_query_presets,
    package_whole_brain_context_session,
    resolve_whole_brain_context_session_plan,
)

try:
    from tests.showcase_test_support import (
        _materialize_packaged_showcase_fixture,
    )
except ModuleNotFoundError:
    from showcase_test_support import (  # type: ignore[no-redef]
        _materialize_packaged_showcase_fixture,
    )

try:
    from tests.test_whole_brain_context_planning import (
        _fixture_synapse_registry_reference,
        _write_context_review_metadata_fixture,
        _write_context_review_synapse_registry,
    )
except ModuleNotFoundError:
    from test_whole_brain_context_planning import (  # type: ignore[no-redef]
        _fixture_synapse_registry_reference,
        _write_context_review_metadata_fixture,
        _write_context_review_synapse_registry,
    )


class WholeBrainContextPackagingTest(unittest.TestCase):
    def test_showcase_review_fixture_packages_query_presets_with_stable_payload_refs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))
            _write_context_review_metadata_fixture(fixture["config_path"])
            synapse_registry_path = (
                Path(tmp_dir_str) / "context_review_fixture" / "local_synapse_registry.csv"
            )
            _write_context_review_synapse_registry(synapse_registry_path)

            showcase_plan = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                suite_review_summary_path=fixture["suite_review_summary_path"],
                table_dimension_ids=["motion_direction"],
            )
            showcase_package = package_showcase_session(showcase_plan)

            plan = resolve_whole_brain_context_session_plan(
                config_path=fixture["config_path"],
                showcase_session_metadata_path=showcase_package["metadata_path"],
                explicit_artifact_references=[
                    _fixture_synapse_registry_reference(
                        fixture["config_path"],
                        path=synapse_registry_path,
                    )
                ],
            )

            self.assertEqual(
                plan["fixture_mode"],
                WHOLE_BRAIN_CONTEXT_FIXTURE_MODE_REVIEW,
            )
            self.assertEqual(
                plan["fixture_profile"]["compact_gate"]["surface_kind"],
                "showcase_session",
            )

            packaged = package_whole_brain_context_session(plan)
            catalog = json.loads(
                Path(packaged["context_query_catalog_path"]).read_text(encoding="utf-8")
            )
            payload = json.loads(
                Path(packaged["context_view_payload_path"]).read_text(encoding="utf-8")
            )
            state = json.loads(
                Path(packaged["context_view_state_path"]).read_text(encoding="utf-8")
            )

            self.assertEqual(
                catalog["preset_library_id"],
                DEFAULT_CONTEXT_QUERY_PRESET_LIBRARY_ID,
            )
            self.assertEqual(
                catalog["fixture_profile"]["fixture_mode"],
                WHOLE_BRAIN_CONTEXT_FIXTURE_MODE_REVIEW,
            )
            self.assertEqual(
                catalog["active_preset_id"],
                OVERVIEW_CONTEXT_PRESET_ID,
            )
            self.assertEqual(
                discover_whole_brain_context_query_presets(catalog),
                discover_whole_brain_context_query_presets(plan),
            )
            self.assertEqual(
                [item["preset_id"] for item in discover_whole_brain_context_query_presets(catalog)],
                [
                    OVERVIEW_CONTEXT_PRESET_ID,
                    UPSTREAM_HALO_PRESET_ID,
                    DOWNSTREAM_HALO_PRESET_ID,
                    PATHWAY_FOCUS_PRESET_ID,
                    DASHBOARD_HANDOFF_PRESET_ID,
                    SHOWCASE_HANDOFF_PRESET_ID,
                ],
            )
            self.assertEqual(
                catalog["available_preset_ids"],
                [item["preset_id"] for item in discover_whole_brain_context_query_presets(catalog)],
            )
            self.assertEqual(
                state["active_preset_id"],
                catalog["active_preset_id"],
            )
            self.assertEqual(
                state["preset_discovery_order"],
                catalog["preset_discovery_order"],
            )

            available_presets = {
                item["preset_id"]: item for item in catalog["available_query_presets"]
            }
            overview_ref = available_presets[OVERVIEW_CONTEXT_PRESET_ID][
                "graph_payload_references"
            ]["primary_graph"]
            pathway_ref = available_presets[PATHWAY_FOCUS_PRESET_ID][
                "graph_payload_references"
            ]["primary_graph"]
            self.assertEqual(
                overview_ref["payload_path"],
                f"query_preset_payloads.{OVERVIEW_CONTEXT_PRESET_ID}.overview_graph",
            )
            self.assertEqual(
                pathway_ref["payload_path"],
                f"query_preset_payloads.{PATHWAY_FOCUS_PRESET_ID}.focused_subgraph",
            )
            self.assertEqual(
                available_presets[DASHBOARD_HANDOFF_PRESET_ID]["linked_session_target"][
                    "artifact_role_id"
                ],
                "dashboard_session_metadata",
            )
            self.assertEqual(
                available_presets[SHOWCASE_HANDOFF_PRESET_ID]["linked_session_target"][
                    "artifact_role_id"
                ],
                "showcase_session_metadata",
            )

            overview_payload = payload["query_preset_payloads"][OVERVIEW_CONTEXT_PRESET_ID]
            upstream_payload = payload["query_preset_payloads"][UPSTREAM_HALO_PRESET_ID]
            downstream_payload = payload["query_preset_payloads"][DOWNSTREAM_HALO_PRESET_ID]
            pathway_payload = payload["query_preset_payloads"][PATHWAY_FOCUS_PRESET_ID]
            active_root_count = len(plan["selection"]["selected_root_ids"])

            self.assertGreater(
                overview_payload["overview_graph"]["summary"]["distinct_root_count"],
                active_root_count,
            )
            self.assertTrue(
                any(
                    item["node_role_id"] == "context_only"
                    and "upstream_graph" in item["overlay_ids"]
                    for item in upstream_payload["overview_graph"]["node_records"]
                )
            )
            self.assertTrue(
                any(
                    "downstream_graph" in item["overlay_ids"]
                    for item in downstream_payload["overview_graph"]["edge_records"]
                )
            )
            self.assertTrue(pathway_payload["pathway_highlights"])
            self.assertEqual(
                pathway_payload["focused_subgraph"]["view_id"],
                "focused_subgraph",
            )
            self.assertGreater(
                pathway_payload["focused_subgraph"]["summary"]["pathway_highlight_count"],
                0,
            )
            self.assertEqual(
                overview_payload["query_state"]["default_overlay_id"],
                "bidirectional_context_graph",
            )
            overview_overlay_ids = [
                item["overlay_id"]
                for item in overview_payload["overview_graph"]["overlay_workflow_catalog"]
            ]
            self.assertIn("bidirectional_context_graph", overview_overlay_ids)
            self.assertEqual(
                [
                    item["interaction_flow_id"]
                    for item in overview_payload["overview_graph"]["interaction_flow_catalog"]
                ],
                [
                    "interaction_flow:overlay:upstream_emphasis",
                    "interaction_flow:overlay:downstream_emphasis",
                    "interaction_flow:overlay:bidirectional_context",
                    "interaction_flow:facet:cell_class",
                    "interaction_flow:facet:neuropil",
                    "interaction_flow:pathway:active_to_context",
                ],
            )
            overview_facet_groups = {
                item["metadata_facet_id"]
                for item in overview_payload["overview_graph"]["metadata_facet_group_catalog"]
            }
            self.assertTrue({"cell_class", "neuropil"}.issubset(overview_facet_groups))
            overview_filters = {
                item["filter_id"]: item
                for item in overview_payload["overview_graph"]["metadata_facet_filter_catalog"]
            }
            self.assertTrue(
                set(plan["selection"]["selected_root_ids"]).issubset(
                    set(overview_filters["facet_filter:neuropil:lop_r"]["visible_root_ids"])
                )
            )
            pathway_mode = pathway_payload["focused_subgraph"]["pathway_explanation_catalog"][0]
            self.assertEqual(
                pathway_mode["explanation_mode_id"],
                "active_to_context_pathwalk",
            )
            self.assertGreater(pathway_mode["card_count"], 0)
            self.assertIn(
                "context-only",
                pathway_mode["cards"][0]["caption"],
            )
