from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.hybrid_morphology_contract import (
    HYBRID_MORPHOLOGY_CONTRACT_VERSION,
    POINT_NEURON_CLASS,
    SKELETON_NEURON_CLASS,
    SURFACE_NEURON_CLASS,
    build_hybrid_morphology_plan_metadata,
    discover_hybrid_morphology_classes,
    normalize_hybrid_morphology_root_metadata,
    parse_hybrid_morphology_plan_metadata,
)
from flywire_wave.skeleton_runtime_assets import SKELETON_RUNTIME_ASSET_KEY


class HybridMorphologyContractTest(unittest.TestCase):
    def test_fixture_hybrid_metadata_normalizes_deterministically_and_discovers_classes(self) -> None:
        fixture_a = [
            {
                "root_id": 303,
                "project_role": "point_simulated",
                "cell_type": "Mi1",
            },
            {
                "root_id": 101,
                "project_role": "surface_simulated",
                "cell_type": "T4a",
            },
            {
                "root_id": 202,
                "morphology_class": "Skeleton Neuron",
                "cell_type": "TmY5a",
            },
        ]
        fixture_b = [
            {
                "root_id": 202,
                "project_role": "skeleton_simulated",
                "morphology_class": "skeleton_neuron",
                "cell_type": "TmY5a",
            },
            {
                "root_id": 101,
                "morphology_class": "surface-neuron",
                "cell_type": "T4a",
            },
            {
                "root_id": 303,
                "morphology_class": "Point Neuron",
                "project_role": "point_simulated",
                "cell_type": "Mi1",
            },
        ]

        metadata_a = build_hybrid_morphology_plan_metadata(root_records=fixture_a)
        metadata_b = build_hybrid_morphology_plan_metadata(root_records=fixture_b)
        reparsed = parse_hybrid_morphology_plan_metadata(metadata_a)

        self.assertEqual(metadata_a, metadata_b)
        self.assertEqual(reparsed, metadata_a)
        self.assertEqual(
            metadata_a["contract_version"],
            HYBRID_MORPHOLOGY_CONTRACT_VERSION,
        )
        self.assertEqual(
            metadata_a["planner_integration"]["field_name"],
            "surface_wave_execution_plan.hybrid_morphology",
        )
        self.assertEqual(
            metadata_a["discovered_morphology_classes"],
            [
                POINT_NEURON_CLASS,
                SKELETON_NEURON_CLASS,
                SURFACE_NEURON_CLASS,
            ],
        )
        self.assertEqual(
            discover_hybrid_morphology_classes(
                [
                    {"project_role": "surface_simulated"},
                    {"morphology_class": "point_neuron"},
                    {"project_role": "skeleton_simulated"},
                    {"morphology_class": "surface_neuron"},
                ]
            ),
            [
                POINT_NEURON_CLASS,
                SKELETON_NEURON_CLASS,
                SURFACE_NEURON_CLASS,
            ],
        )

        normalized_root = normalize_hybrid_morphology_root_metadata(
            {
                "root_id": 202,
                "project_role": "skeleton_simulated",
                "cell_type": "TmY5a",
            }
        )
        self.assertEqual(normalized_root["morphology_class"], SKELETON_NEURON_CLASS)
        self.assertEqual(
            normalized_root["coupling_anchor_resolution"]["incoming_resolution"],
            "skeleton_node",
        )
        self.assertEqual(
            normalized_root["readout_surface"]["local_readout_surface"],
            "skeleton_anchor_cloud",
        )
        self.assertIn(
            SKELETON_RUNTIME_ASSET_KEY,
            normalized_root["required_local_assets"],
        )

        per_root = {
            int(item["root_id"]): item
            for item in metadata_a["per_root_class_metadata"]
        }
        self.assertEqual(per_root[101]["morphology_class"], SURFACE_NEURON_CLASS)
        self.assertEqual(per_root[202]["morphology_class"], SKELETON_NEURON_CLASS)
        self.assertEqual(per_root[303]["morphology_class"], POINT_NEURON_CLASS)
        self.assertEqual(
            per_root[101]["realized_state_space"]["state_space_kind"],
            "distributed_surface_field",
        )
        self.assertEqual(
            per_root[303]["readout_surface"]["local_readout_surface"],
            "root_state_scalar",
        )
        self.assertEqual(
            per_root[303]["serialization_requirements"]["planner_record_fields"],
            ["root_id", "morphology_class", "source_project_role", "promotion_rank"],
        )

        route_ids = {
            item["route_id"]
            for item in metadata_a["allowed_cross_class_coupling_routes"]
        }
        self.assertIn("surface_neuron_to_point_neuron", route_ids)
        self.assertIn("point_neuron_to_surface_neuron", route_ids)

        serialized_a = json.dumps(metadata_a, indent=2, sort_keys=True)
        serialized_b = json.dumps(metadata_b, indent=2, sort_keys=True)
        self.assertEqual(serialized_a, serialized_b)
