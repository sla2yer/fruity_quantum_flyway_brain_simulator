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

from flywire_wave.showcase_session_contract import ANALYSIS_SUMMARY_PRESET_ID
from flywire_wave.showcase_session_planning import (
    package_showcase_session,
    resolve_showcase_session_plan,
)
from flywire_wave.whole_brain_context_contract import (
    CONTEXT_SUMMARY_ONLY_CLAIM_SCOPE,
)
from flywire_wave.whole_brain_context_planning import (
    DASHBOARD_HANDOFF_PRESET_ID,
    SHOWCASE_HANDOFF_PRESET_ID,
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


class WholeBrainContextSessionQueryTest(unittest.TestCase):
    def test_showcase_review_query_artifacts_include_handoff_enriched_module_lineage(
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
            showcase_catalog = json.loads(
                Path(showcase_package["narrative_preset_catalog_path"]).read_text(
                    encoding="utf-8"
                )
            )
            analysis_summary_preset = next(
                item
                for item in showcase_catalog["saved_presets"]
                if item["preset_id"] == ANALYSIS_SUMMARY_PRESET_ID
            )
            analysis_links = [
                item
                for item in analysis_summary_preset["presentation_state_patch"][
                    "rehearsal_metadata"
                ]["presentation_links"]
                if item["link_kind"] == "whole_brain_context_handoff"
            ]

            self.assertEqual(len(analysis_links), 1)
            self.assertEqual(
                analysis_links[0]["shared_context"]["target_context_preset_id"],
                SHOWCASE_HANDOFF_PRESET_ID,
            )

            plan = resolve_whole_brain_context_session_plan(
                config_path=fixture["config_path"],
                showcase_session_metadata_path=showcase_package["metadata_path"],
                query_profile_id="downstream_module_review",
                query_profile_ids=["downstream_module_review"],
                requested_downstream_module_role_ids=["simplified_readout_module"],
                explicit_artifact_references=[
                    _fixture_synapse_registry_reference(
                        fixture["config_path"],
                        path=synapse_registry_path,
                    )
                ],
            )

            modules = plan["query_execution"]["overview_graph"]["downstream_module_records"]
            self.assertTrue(modules)
            module = modules[0]

            self.assertEqual(
                module["downstream_module_role_id"],
                "simplified_readout_module",
            )
            self.assertTrue(module["summary_labels"]["is_optional"])
            self.assertTrue(module["summary_labels"]["is_simplified"])
            self.assertTrue(module["summary_labels"]["is_context_oriented"])
            self.assertEqual(
                module["summary_labels"]["claim_scope"],
                CONTEXT_SUMMARY_ONLY_CLAIM_SCOPE,
            )
            self.assertIn(
                "not a new simulated biological claim",
                module["summary_labels"]["truthfulness_note"],
            )
            self.assertEqual(
                module["lineage"]["source_query_profile_id"],
                "downstream_module_review",
            )
            self.assertEqual(
                module["lineage"]["source_query_family"],
                "downstream_module_review",
            )

            active_anchor_root_ids = {
                int(root_id) for root_id in module["lineage"]["active_anchor_root_ids"]
            }
            self.assertTrue(active_anchor_root_ids)
            self.assertTrue(
                active_anchor_root_ids.issubset(
                    set(plan["selection"]["selected_root_ids"])
                )
            )

            handoff_targets = {
                (
                    item["linked_session_kind"],
                    item["source_preset_id"],
                    item["target_preset_id"],
                    item["target_payload_path"],
                )
                for item in module["handoff_targets"]
            }
            self.assertIn(
                (
                    "dashboard",
                    None,
                    DASHBOARD_HANDOFF_PRESET_ID,
                    f"query_preset_payloads.{DASHBOARD_HANDOFF_PRESET_ID}.overview_graph",
                ),
                handoff_targets,
            )
            self.assertIn(
                (
                    "showcase",
                    ANALYSIS_SUMMARY_PRESET_ID,
                    SHOWCASE_HANDOFF_PRESET_ID,
                    f"query_preset_payloads.{SHOWCASE_HANDOFF_PRESET_ID}.focused_subgraph",
                ),
                handoff_targets,
            )

            available_presets = {
                item["preset_id"]: item
                for item in plan["query_preset_library"]["available_query_presets"]
            }
            self.assertEqual(
                available_presets[SHOWCASE_HANDOFF_PRESET_ID]["linked_session_target"][
                    "source_preset_ids"
                ],
                [ANALYSIS_SUMMARY_PRESET_ID],
            )
