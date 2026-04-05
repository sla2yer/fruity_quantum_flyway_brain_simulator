from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.whole_brain_context_contract import (
    CONTEXT_SUMMARY_ONLY_CLAIM_SCOPE,
    build_whole_brain_context_contract_metadata,
    build_whole_brain_context_query_state,
)
from flywire_wave.whole_brain_context_query import (
    WholeBrainContextQueryError,
    execute_whole_brain_context_query,
)


ACTIVE_ROOT_IDS = [101, 202]


class WholeBrainContextQueryTest(unittest.TestCase):
    def test_upstream_query_ranks_and_reduces_context_nodes_deterministically(self) -> None:
        fixture = _context_query_fixture()
        plan = _build_query_plan(
            query_profile_id="upstream_connectivity_context",
            reduction_profile_id="balanced_neighborhood",
        )

        result = execute_whole_brain_context_query(
            plan,
            synapse_registry=fixture["synapse_df"],
            node_metadata_registry=fixture["node_metadata_df"],
            reduction_controls={
                "max_hops": 2,
                "max_context_node_count": 3,
                "max_edge_count": 8,
            },
        )

        context_nodes = [
            int(item["root_id"])
            for item in result["overview_graph"]["node_records"]
            if str(item["node_role_id"]) == "context_only"
        ]
        context_to_active_edges = [
            (int(item["source_root_id"]), int(item["target_root_id"]))
            for item in result["overview_graph"]["edge_records"]
            if str(item["edge_role_id"]) == "context_to_active"
        ]
        highlighted_targets = [
            int(item["target_root_id"]) for item in result["pathway_highlights"]
        ]

        self.assertEqual(context_nodes, [303, 404, 606])
        self.assertNotIn(505, context_nodes)
        self.assertEqual(context_to_active_edges, [(303, 101), (404, 101), (606, 202)])
        self.assertEqual(highlighted_targets[:3], [303, 404, 606])
        self.assertEqual(result["execution_summary"]["status"], "available")

    def test_downstream_query_applies_neuropil_filter_and_budget(self) -> None:
        fixture = _context_query_fixture()
        plan = _build_query_plan(
            query_profile_id="downstream_connectivity_context",
            reduction_profile_id="balanced_neighborhood",
        )

        result = execute_whole_brain_context_query(
            plan,
            synapse_registry=fixture["synapse_df"],
            node_metadata_registry=fixture["node_metadata_df"],
            reduction_controls={
                "max_hops": 2,
                "max_context_node_count": 2,
                "max_edge_count": 8,
                "allowed_neuropils": ["LOP_R"],
            },
        )

        context_nodes = [
            int(item["root_id"])
            for item in result["overview_graph"]["node_records"]
            if str(item["node_role_id"]) == "context_only"
        ]

        self.assertEqual(context_nodes, [707, 808])
        self.assertNotIn(909, context_nodes)
        self.assertNotIn(910, context_nodes)
        self.assertEqual(
            result["input_sources"]["synapse_registry"]["filtered_by_neuropils"],
            ["lop_r"],
        )

    def test_pathway_review_builds_targeted_highlight_extract(self) -> None:
        fixture = _context_query_fixture()
        plan = _build_query_plan(
            query_profile_id="pathway_highlight_review",
            reduction_profile_id="pathway_focus",
        )

        result = execute_whole_brain_context_query(
            plan,
            synapse_registry=fixture["synapse_df"],
            node_metadata_registry=fixture["node_metadata_df"],
            reduction_controls={
                "max_hops": 2,
                "max_context_node_count": 8,
                "max_edge_count": 16,
                "pathway_target_root_ids": [909],
                "pathway_extraction_mode": "targeted_paths",
            },
        )

        self.assertEqual([item["target_root_id"] for item in result["pathway_highlights"]], [909])
        self.assertEqual(
            result["pathway_highlights"][0]["node_root_ids"],
            [101, 707, 909],
        )
        focused_root_ids = {
            int(item["root_id"]) for item in result["focused_subgraph"]["node_records"]
        }
        highlight_root_ids = {
            int(item["root_id"])
            for item in result["overview_graph"]["node_records"]
            if str(item["node_role_id"]).endswith("pathway_highlight")
        }

        self.assertTrue({101, 707, 909}.issubset(focused_root_ids))
        self.assertTrue({101, 707, 909}.issubset(highlight_root_ids))

    def test_bidirectional_query_packages_overlay_facet_and_pathway_explanation_metadata(
        self,
    ) -> None:
        fixture = _context_query_fixture()
        plan = _build_query_plan(
            query_profile_id="bidirectional_connectivity_context",
            reduction_profile_id="balanced_neighborhood",
        )

        result = execute_whole_brain_context_query(
            plan,
            synapse_registry=fixture["synapse_df"],
            node_metadata_registry=fixture["node_metadata_df"],
            reduction_controls={
                "max_hops": 2,
                "max_context_node_count": 8,
                "max_edge_count": 16,
            },
        )

        overview = result["overview_graph"]
        overlay_workflows = {
            item["overlay_id"]: item for item in overview["overlay_workflow_catalog"]
        }
        self.assertEqual(
            [item["overlay_id"] for item in overview["overlay_workflow_catalog"]],
            [
                "active_boundary",
                "upstream_graph",
                "downstream_graph",
                "bidirectional_context_graph",
                "pathway_highlight",
                "downstream_module",
                "metadata_facet_badges",
            ],
        )
        self.assertEqual(
            overlay_workflows["bidirectional_context_graph"]["availability"],
            "available",
        )
        self.assertTrue(
            {101, 202}.issubset(
                set(overlay_workflows["bidirectional_context_graph"]["visible_root_ids"])
            )
        )

        facet_groups = {
            item["metadata_facet_id"]: item
            for item in overview["metadata_facet_group_catalog"]
        }
        self.assertIn("cell_class", facet_groups)
        self.assertIn("neuropil", facet_groups)
        facet_filters = {
            item["filter_id"]: item for item in overview["metadata_facet_filter_catalog"]
        }
        optic_filter = facet_filters["facet_filter:cell_class:optic"]
        self.assertIn(303, optic_filter["matching_root_ids"])
        self.assertTrue({101, 202}.issubset(set(optic_filter["visible_root_ids"])))
        lop_filter = facet_filters["facet_filter:neuropil:lop_r"]
        self.assertTrue({101, 202}.issubset(set(lop_filter["visible_root_ids"])))
        self.assertGreater(lop_filter["matching_context_root_count"], 0)

        explanation_mode = overview["pathway_explanation_catalog"][0]
        self.assertEqual(
            explanation_mode["explanation_mode_id"],
            "active_to_context_pathwalk",
        )
        self.assertEqual(explanation_mode["availability"], "available")
        first_card = explanation_mode["cards"][0]
        self.assertEqual(first_card["review_direction"], "active_to_context")
        self.assertTrue(first_card["active_root_ids"])
        self.assertTrue(first_card["context_root_ids"])
        self.assertIn("context-only", first_card["caption"])
        self.assertTrue(
            any(
                item["metadata_facet_id"] in {"cell_class", "neuropil"}
                for item in first_card["facet_groupings"]
            )
        )

        self.assertEqual(
            [item["interaction_flow_id"] for item in overview["interaction_flow_catalog"]],
            [
                "interaction_flow:overlay:upstream_emphasis",
                "interaction_flow:overlay:downstream_emphasis",
                "interaction_flow:overlay:bidirectional_context",
                "interaction_flow:facet:cell_class",
                "interaction_flow:facet:neuropil",
                "interaction_flow:pathway:active_to_context",
            ],
        )
        self.assertEqual(overview["summary"]["interaction_flow_count"], 6)
        self.assertEqual(
            overview["reviewer_summary_cards"][0]["card_id"],
            "reviewer_card:boundary_summary",
        )

    def test_downstream_module_review_packages_simplified_module_labels_and_lineage(
        self,
    ) -> None:
        fixture = _context_query_fixture()
        plan = _build_query_plan(
            query_profile_id="downstream_module_review",
            reduction_profile_id="downstream_module_collapsed",
        )

        result = execute_whole_brain_context_query(
            plan,
            synapse_registry=fixture["synapse_df"],
            node_metadata_registry=fixture["node_metadata_df"],
            reduction_controls={
                "max_hops": 2,
                "max_context_node_count": 8,
                "max_edge_count": 16,
                "max_downstream_module_count": 2,
            },
        )

        self.assertTrue(result["overview_graph"]["downstream_module_records"])
        module = result["overview_graph"]["downstream_module_records"][0]

        self.assertEqual(
            module["summary_labels"]["claim_scope"],
            CONTEXT_SUMMARY_ONLY_CLAIM_SCOPE,
        )
        self.assertTrue(module["summary_labels"]["is_optional"])
        self.assertTrue(module["summary_labels"]["is_simplified"])
        self.assertTrue(module["summary_labels"]["is_context_oriented"])
        self.assertTrue(module["summary_labels"]["scientific_curation_required"])
        self.assertEqual(
            module["lineage"]["source_query_profile_id"],
            "downstream_module_review",
        )
        self.assertEqual(
            module["lineage"]["source_query_family"],
            "downstream_module_review",
        )
        self.assertTrue(module["lineage"]["active_anchor_root_ids"])
        self.assertTrue(
            set(module["lineage"]["active_anchor_root_ids"]).issubset({"101", "202"})
        )
        self.assertEqual(module["handoff_targets"], [])

    def test_query_fails_clearly_for_missing_required_inputs_and_unreachable_targets(self) -> None:
        fixture = _context_query_fixture()
        plan = _build_query_plan(
            query_profile_id="upstream_connectivity_context",
            reduction_profile_id="balanced_neighborhood",
        )

        with self.assertRaisesRegex(
            WholeBrainContextQueryError,
            "requires a local synapse registry",
        ):
            execute_whole_brain_context_query(plan)

        with self.assertRaisesRegex(
            WholeBrainContextQueryError,
            "requires a local node metadata registry",
        ):
            execute_whole_brain_context_query(
                plan,
                synapse_registry=fixture["synapse_df"],
                reduction_controls={"allowed_cell_classes": ["optic"]},
            )

        with self.assertRaisesRegex(
            WholeBrainContextQueryError,
            "pathway_target_root_ids",
        ):
            execute_whole_brain_context_query(
                _build_query_plan(
                    query_profile_id="pathway_highlight_review",
                    reduction_profile_id="pathway_focus",
                ),
                synapse_registry=fixture["synapse_df"],
                node_metadata_registry=fixture["node_metadata_df"],
                reduction_controls={
                    "max_context_node_count": 8,
                    "max_edge_count": 16,
                    "pathway_target_root_ids": [999],
                    "pathway_extraction_mode": "targeted_paths",
                },
            )

    def test_resolved_plan_and_packaged_payload_embed_query_execution(self) -> None:
        try:
            from tests.simulation_planning_test_support import _write_simulation_fixture
        except ModuleNotFoundError:
            from simulation_planning_test_support import _write_simulation_fixture  # type: ignore[no-redef]

        try:
            from tests.test_whole_brain_context_planning import (
                _fixture_synapse_registry_reference,
                _materialize_subset_bundle_from_config,
            )
        except ModuleNotFoundError:
            from test_whole_brain_context_planning import (  # type: ignore[no-redef]
                _fixture_synapse_registry_reference,
                _materialize_subset_bundle_from_config,
            )

        from flywire_wave.whole_brain_context_planning import (
            package_whole_brain_context_session,
            resolve_whole_brain_context_session_plan,
        )

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = _write_simulation_fixture(tmp_dir)
            _materialize_subset_bundle_from_config(
                config_path,
                subset_name="motion_minimal",
            )
            synapse_registry_path = tmp_dir / "out" / "processed_coupling" / "synapse_registry.csv"
            synapse_registry_path.parent.mkdir(parents=True, exist_ok=True)
            _write_synapse_registry_csv(_context_query_fixture()["synapse_df"], synapse_registry_path)

            plan = resolve_whole_brain_context_session_plan(
                config_path=config_path,
                subset_name="motion_minimal",
                query_profile_id="downstream_connectivity_context",
                explicit_artifact_references=[
                    _fixture_synapse_registry_reference(
                        config_path,
                        path=synapse_registry_path,
                    )
                ],
            )

            overview_graph = plan["query_execution"]["overview_graph"]
            distinct_root_count = int(overview_graph["summary"]["distinct_root_count"])
            active_root_count = len(plan["selection"]["selected_root_ids"])
            context_roles = {
                str(item["node_role_id"])
                for item in plan["whole_brain_context_session"]["representative_context"][
                    "node_records"
                ]
            }

            self.assertGreater(distinct_root_count, active_root_count)
            self.assertIn("context_only", context_roles)

            packaged = package_whole_brain_context_session(plan)
            payload = json.loads(
                Path(packaged["context_view_payload_path"]).read_text(encoding="utf-8")
            )
            self.assertIn("query_execution", payload)
            self.assertGreater(
                payload["query_execution"]["overview_graph"]["summary"]["distinct_root_count"],
                active_root_count,
            )


def _build_query_plan(
    *,
    query_profile_id: str,
    reduction_profile_id: str,
) -> dict[str, Any]:
    contract = build_whole_brain_context_contract_metadata()
    query_state = build_whole_brain_context_query_state(
        query_profile_id=query_profile_id,
        default_reduction_profile_id=reduction_profile_id,
        contract_metadata=contract,
    )
    reduction_profile = next(
        item
        for item in contract["reduction_profile_catalog"]
        if str(item["reduction_profile_id"]) == reduction_profile_id
    )
    return {
        "plan_version": "whole_brain_context_session_plan.v1",
        "config_path": str(ROOT / "tests" / "fixtures" / "missing_context_query_config.yaml"),
        "selection": {
            "selected_root_ids": list(ACTIVE_ROOT_IDS),
            "active_anchor_records": [
                {"root_id": 101, "cell_type": "T4a", "super_class": "optic", "side": "R"},
                {"root_id": 202, "cell_type": "T5a", "super_class": "optic", "side": "R"},
            ],
        },
        "registry_sources": {},
        "query_profile_resolution": {
            "active_query_profile_id": query_profile_id,
            "selected_query_profile_ids": [query_profile_id],
            "available_query_profile_ids": [query_profile_id],
        },
        "query_state": query_state,
        "reduction_profile": reduction_profile,
        "metadata_facet_requests": [],
        "downstream_module_requests": [
            {
                "downstream_module_role_id": "simplified_readout_module",
                "display_name": "Simplified Readout Module",
                "default_context_layer_id": "downstream_module",
                "allows_aggregated_readout": True,
                "requires_scientific_curation": True,
            }
        ],
    }


def _context_query_fixture() -> dict[str, pd.DataFrame]:
    synapse_rows: list[dict[str, Any]] = []
    synapse_rows.extend(_synapse_rows(303, 101, 5, "ME_R", "ACH", 1.0))
    synapse_rows.extend(_synapse_rows(404, 101, 4, "LO_R", "GABA", 2.5))
    synapse_rows.extend(_synapse_rows(505, 303, 6, "ME_R", "ACH", 1.0))
    synapse_rows.extend(_synapse_rows(606, 202, 3, "LO_R", "GLUT", 1.0))
    synapse_rows.extend(_synapse_rows(101, 707, 7, "LOP_R", "ACH", 1.0))
    synapse_rows.extend(_synapse_rows(202, 808, 5, "LOP_R", "GLUT", 2.4))
    synapse_rows.extend(_synapse_rows(707, 909, 6, "PLP_R", "ACH", 1.0))
    synapse_rows.extend(_synapse_rows(202, 910, 2, "AME_R", "GABA", 1.0))
    synapse_rows.extend(_synapse_rows(101, 202, 2, "LOP_R", "ACH", 1.0))
    synapse_rows.extend(_synapse_rows(202, 101, 1, "LOP_R", "GLUT", 1.0))

    node_metadata_df = pd.DataFrame(
        [
            {"root_id": 101, "cell_type": "T4a", "super_class": "optic", "class": "t4", "side": "R", "nt_type": "ACH"},
            {"root_id": 202, "cell_type": "T5a", "super_class": "optic", "class": "t5", "side": "R", "nt_type": "GLUT"},
            {"root_id": 303, "cell_type": "Mi1", "super_class": "optic", "class": "mi", "side": "R", "nt_type": "ACH"},
            {"root_id": 404, "cell_type": "Tm3", "super_class": "visual_projection", "class": "tm", "side": "R", "nt_type": "GABA"},
            {"root_id": 505, "cell_type": "L1", "super_class": "optic", "class": "lamina", "side": "R", "nt_type": "ACH"},
            {"root_id": 606, "cell_type": "C2", "super_class": "visual_projection", "class": "centrifugal", "side": "R", "nt_type": "GLUT"},
            {"root_id": 707, "cell_type": "LPLC1", "super_class": "visual_projection", "class": "readout", "side": "R", "nt_type": "ACH"},
            {"root_id": 808, "cell_type": "DNp", "super_class": "descending", "class": "readout", "side": "R", "nt_type": "GLUT"},
            {"root_id": 909, "cell_type": "PFL3", "super_class": "central", "class": "bridge", "side": "R", "nt_type": "ACH"},
            {"root_id": 910, "cell_type": "AOTU", "super_class": "accessory", "class": "offpath", "side": "R", "nt_type": "GABA"},
        ]
    )
    return {
        "synapse_df": pd.DataFrame(synapse_rows),
        "node_metadata_df": node_metadata_df,
    }


def _synapse_rows(
    pre_root_id: int,
    post_root_id: int,
    count: int,
    neuropil: str,
    nt_type: str,
    weight: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(count):
        rows.append(
            {
                "synapse_row_id": f"{pre_root_id}->{post_root_id}:{index + 1}",
                "source_row_number": index + 1,
                "pre_root_id": int(pre_root_id),
                "post_root_id": int(post_root_id),
                "neuropil": str(neuropil),
                "nt_type": str(nt_type),
                "weight": float(weight),
                "confidence": 0.9,
            }
        )
    return rows


def _write_synapse_registry_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


if __name__ == "__main__":
    unittest.main()
