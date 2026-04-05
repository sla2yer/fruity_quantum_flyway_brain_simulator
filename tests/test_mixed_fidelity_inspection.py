from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.hybrid_morphology_contract import (
    POINT_NEURON_CLASS,
    SURFACE_NEURON_CLASS,
)
from flywire_wave.io_utils import write_json
from flywire_wave.mixed_fidelity_inspection import (
    build_mixed_fidelity_inspection_output_dir,
    execute_mixed_fidelity_inspection_workflow,
)
from flywire_wave.simulation_planning import resolve_manifest_mixed_fidelity_plan
from flywire_wave.stimulus_bundle import record_stimulus_bundle, resolve_stimulus_input
from simulation_planning_test_support import (
    _write_manifest_fixture,
    _write_simulation_fixture,
)


class MixedFidelityInspectionTest(unittest.TestCase):
    def test_mixed_fidelity_policy_normalization_is_deterministic_and_records_recommendations(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_policy_fixture(Path(tmp_dir_str))

            first = resolve_manifest_mixed_fidelity_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                arm_id="surface_wave_intact",
            )
            second = resolve_manifest_mixed_fidelity_plan(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                arm_id="surface_wave_intact",
            )

            self.assertEqual(first, second)
            self.assertEqual(
                first["assignment_policy"]["policy_version"],
                "mixed_fidelity_policy.v1",
            )
            self.assertEqual(
                first["assignment_policy"]["promotion_mode"],
                "recommend_from_policy",
            )
            self.assertEqual(
                first["policy_hook"]["promotion_recommendation_root_ids"],
                [303],
            )

            per_root = {
                int(item["root_id"]): item
                for item in first["per_root_assignments"]
            }
            self.assertEqual(
                per_root[303]["realized_morphology_class"],
                POINT_NEURON_CLASS,
            )
            self.assertEqual(
                per_root[303]["policy_evaluation"]["recommended_morphology_class"],
                SURFACE_NEURON_CLASS,
            )
            self.assertEqual(
                per_root[303]["policy_evaluation"]["matched_rule_ids"],
                ["promote_patch_dense_surrogate"],
            )
            self.assertTrue(
                per_root[303]["assignment_provenance"]["policy_evaluated"]
            )
            self.assertEqual(
                per_root[303]["approximation_route"]["policy_action"],
                "promote_from_realized",
            )

    def test_mixed_fidelity_inspection_workflow_is_deterministic_and_flags_promotion_review(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_policy_fixture(Path(tmp_dir_str))
            thresholds = {
                "root_mean_trace_mae": {
                    "warn": 1.0e-12,
                    "fail": 1.0e6,
                    "comparison": "max",
                    "blocking": False,
                },
                "root_peak_abs_error": {
                    "warn": 1.0e6,
                    "fail": 1.0e9,
                    "comparison": "max",
                    "blocking": False,
                },
                "root_final_abs_error": {
                    "warn": 1.0e6,
                    "fail": 1.0e9,
                    "comparison": "max",
                    "blocking": False,
                },
                "root_peak_time_delta_ms": {
                    "warn": 1.0e6,
                    "fail": 1.0e9,
                    "comparison": "max",
                    "blocking": False,
                },
                "shared_output_trace_mae": {
                    "warn": 1.0e6,
                    "fail": 1.0e9,
                    "comparison": "max",
                    "blocking": True,
                },
                "shared_output_peak_abs_error": {
                    "warn": 1.0e6,
                    "fail": 1.0e9,
                    "comparison": "max",
                    "blocking": True,
                },
            }
            output_dir = build_mixed_fidelity_inspection_output_dir(
                mixed_fidelity_inspection_dir=fixture["tmp_dir"] / "inspection_reports",
                experiment_id="milestone_1_demo_motion_patch",
                arm_id="surface_wave_intact",
                reference_roots=[
                    {
                        "root_id": 303,
                        "reference_morphology_class": "surface_neuron",
                        "reference_source": "policy_recommendation",
                    }
                ],
                thresholds=thresholds,
            )

            first = execute_mixed_fidelity_inspection_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                arm_id="surface_wave_intact",
                thresholds=thresholds,
                output_dir=output_dir,
            )
            report_path = Path(first["report_path"])
            summary_path = Path(first["summary_path"])
            report_bytes = report_path.read_bytes()
            summary_bytes = summary_path.read_bytes()

            second = execute_mixed_fidelity_inspection_workflow(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                arm_id="surface_wave_intact",
                thresholds=thresholds,
                output_dir=output_dir,
            )

            self.assertEqual(first, second)
            self.assertEqual(first["output_dir"], str(output_dir.resolve()))
            self.assertEqual(Path(second["report_path"]).read_bytes(), report_bytes)
            self.assertEqual(Path(second["summary_path"]).read_bytes(), summary_bytes)
            self.assertEqual(
                first["mixed_fidelity_plan"]["policy_hook"]["promotion_recommendation_root_ids"],
                [303],
            )
            self.assertEqual(first["reference_roots"][0]["reference_source"], "policy_recommendation")
            self.assertEqual(first["recommended_promotion_root_ids"], [303])
            self.assertEqual(first["review_root_ids"], [303])
            root_summary = first["root_summaries"][0]
            self.assertEqual(root_summary["root_id"], 303)
            self.assertEqual(root_summary["overall_status"], "review")
            self.assertTrue(root_summary["recommended_promotion"])
            self.assertEqual(
                root_summary["reference_morphology_class"],
                SURFACE_NEURON_CLASS,
            )
            detail = json.loads(Path(root_summary["detail_path"]).read_text(encoding="utf-8"))
            self.assertEqual(detail["policy_evaluation"]["matched_rule_ids"], ["promote_patch_dense_surrogate"])
            self.assertIn("root_mean_trace_mae", detail["metrics"])
            self.assertEqual(detail["checks"]["root_mean_trace_mae"]["status"], "review")


def _materialize_policy_fixture(tmp_dir: Path) -> dict[str, Path]:
    manifest_path = _write_manifest_fixture(
        tmp_dir,
        surface_wave_fidelity_assignment={
            "default_morphology_class": "point_neuron",
            "root_overrides": [
                {"root_id": 101, "morphology_class": "surface_neuron"},
            ],
        },
    )
    config_path = _write_simulation_fixture(
        tmp_dir,
        root_specs=[
            {
                "root_id": 101,
                "project_role": "surface_simulated",
                "asset_profile": "surface",
            },
            {
                "root_id": 303,
                "project_role": "surface_simulated",
                "asset_profile": "surface",
            },
        ],
    )
    _rewrite_config_with_policy(config_path)
    _rewrite_descriptor_fixture(
        tmp_dir / "out" / "processed_graphs" / "303_descriptors.json",
        root_id=303,
        patch_count=4,
    )

    schema_path = ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json"
    design_lock_path = ROOT / "config" / "milestone_1_design_lock.yaml"
    resolved_input = resolve_stimulus_input(
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        processed_stimulus_dir=tmp_dir / "out" / "stimuli",
    )
    record_stimulus_bundle(resolved_input)
    _remove_selected_edges_for_roots(
        tmp_dir / "out" / "asset_manifest.json",
        root_ids=[101, 303],
    )
    return {
        "tmp_dir": tmp_dir,
        "manifest_path": manifest_path,
        "config_path": config_path,
        "schema_path": schema_path,
        "design_lock_path": design_lock_path,
    }


def _rewrite_config_with_policy(config_path: Path) -> None:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    surface_wave = payload["simulation"]["surface_wave"]
    surface_wave.setdefault("recovery", {})["mode"] = "disabled"
    surface_wave.setdefault("nonlinearity", {})["mode"] = "none"
    surface_wave.setdefault("anisotropy", {})["mode"] = "isotropic"
    surface_wave.setdefault("branching", {})["mode"] = "disabled"
    payload["simulation"]["mixed_fidelity"] = {
        "assignment_policy": {
            "promotion_mode": "recommend_from_policy",
            "demotion_mode": "disabled",
            "recommendation_rules": [
                {
                    "rule_id": "promote_patch_dense_surrogate",
                    "minimum_morphology_class": "surface_neuron",
                    "root_ids": [303],
                    "topology_conditions": ["intact"],
                    "arm_tags_any": ["surface_wave"],
                    "descriptor_thresholds": {
                        "patch_count": {
                            "gte": 2,
                        }
                    },
                }
            ],
        }
    }
    config_path.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )


def _rewrite_descriptor_fixture(
    descriptor_path: Path,
    *,
    root_id: int,
    patch_count: int,
) -> None:
    write_json(
        {
            "root_id": int(root_id),
            "descriptor_version": "geometry_descriptors.v1",
            "patch_count": int(patch_count),
            "n_vertices": 6,
            "n_faces": 4,
            "surface_graph_edge_count": 8,
            "derived_relations": {
                "simplified_to_raw_face_ratio": 0.5,
                "simplified_to_raw_vertex_ratio": 0.5,
            },
            "representations": {
                "coarse_patches": {
                    "max_patch_vertex_fraction": 0.4,
                    "singleton_patch_fraction": 0.0,
                },
                "skeleton": {
                    "available": True,
                    "node_count": 3,
                    "segment_count": 2,
                    "branch_point_count": 0,
                    "leaf_count": 2,
                    "total_cable_length": 2.0,
                },
            },
        },
        descriptor_path,
    )


def _remove_selected_edges_for_roots(
    manifest_path: Path,
    *,
    root_ids: list[int] | tuple[int, ...],
) -> None:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    normalized_root_ids = {int(root_id) for root_id in root_ids}
    for key, record in payload.items():
        if not isinstance(key, str) or not key.isdigit() or not isinstance(record, dict):
            continue
        coupling_bundle = record.get("coupling_bundle")
        if not isinstance(coupling_bundle, dict):
            continue
        edge_bundles = coupling_bundle.get("edge_bundles")
        if not isinstance(edge_bundles, list):
            continue
        coupling_bundle["edge_bundles"] = [
            edge_bundle
            for edge_bundle in edge_bundles
            if int(edge_bundle.get("pre_root_id", -1)) not in normalized_root_ids
            and int(edge_bundle.get("post_root_id", -1)) not in normalized_root_ids
        ]
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
