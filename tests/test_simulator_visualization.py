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

from flywire_wave.simulator_execution import execute_manifest_simulation
from flywire_wave.simulator_visualization import generate_simulator_visualization_report

try:
    from test_simulator_execution import _materialize_execution_fixture
except ModuleNotFoundError:
    from tests.test_simulator_execution import _materialize_execution_fixture

try:
    from test_mixed_fidelity_inspection import (
        _remove_selected_edges_for_roots,
        _rewrite_descriptor_fixture,
    )
    from test_simulation_planning import (
        _write_manifest_fixture,
        _write_simulation_fixture,
    )
except ModuleNotFoundError:
    from tests.test_mixed_fidelity_inspection import (
        _remove_selected_edges_for_roots,
        _rewrite_descriptor_fixture,
    )
    from tests.test_simulation_planning import (
        _write_manifest_fixture,
        _write_simulation_fixture,
    )
from flywire_wave.stimulus_bundle import record_stimulus_bundle, resolve_stimulus_input


class SimulatorVisualizationReportTest(unittest.TestCase):
    def test_generate_visualization_report_writes_deterministic_html_for_baseline_and_wave_runs(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_execution_fixture(Path(tmp_dir_str))

            baseline_summary = execute_manifest_simulation(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                model_mode="baseline",
                arm_id="baseline_p0_intact",
            )
            surface_wave_summary = execute_manifest_simulation(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                model_mode="surface_wave",
                arm_id="surface_wave_intact",
            )
            metadata_paths = [
                baseline_summary["executed_runs"][0]["metadata_path"],
                surface_wave_summary["executed_runs"][0]["metadata_path"],
            ]

            first = generate_simulator_visualization_report(
                bundle_metadata_paths=metadata_paths,
            )
            second = generate_simulator_visualization_report(
                bundle_metadata_paths=list(reversed(metadata_paths)),
            )

            report_path = Path(first["report_path"])
            summary_path = Path(first["summary_path"])
            self.assertTrue(report_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertEqual(first, second)

            report_html = report_path.read_text(encoding="utf-8")
            self.assertIn("Simulator Result Viewer", report_html)
            self.assertIn("baseline_p0_intact", report_html)
            self.assertIn("surface_wave_intact", report_html)
            self.assertIn("signed log10 overlay", report_html)
            self.assertIn("Wave Detail: surface_wave_intact", report_html)
            self.assertIn("Peak timing:", report_html)
            self.assertIn("Log view needed:", report_html)
            self.assertIn("Runaway-scale response on this fixture.", report_html)

            persisted_summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted_summary["report_version"], first["report_version"])
            self.assertEqual(persisted_summary["bundle_count"], 2)
            self.assertEqual(
                [item["arm_id"] for item in persisted_summary["compared_bundles"]],
                ["baseline_p0_intact", "surface_wave_intact"],
            )

    def test_generate_visualization_report_renders_mixed_morphology_root_projections(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            fixture = _materialize_mixed_visualization_fixture(tmp_dir)
            mixed_summary = execute_manifest_simulation(
                manifest_path=fixture["manifest_path"],
                config_path=fixture["config_path"],
                schema_path=fixture["schema_path"],
                design_lock_path=fixture["design_lock_path"],
                model_mode="surface_wave",
                arm_id="surface_wave_intact",
            )
            metadata_path = mixed_summary["executed_runs"][0]["metadata_path"]

            report = generate_simulator_visualization_report(
                bundle_metadata_paths=[metadata_path],
            )
            report_html = Path(report["report_path"]).read_text(encoding="utf-8")
            persisted_summary = json.loads(
                Path(report["summary_path"]).read_text(encoding="utf-8")
            )

            self.assertIn("101:surface_neuron", report_html)
            self.assertIn("202:skeleton_neuron", report_html)
            self.assertIn("303:point_neuron", report_html)
            self.assertIn("Root 202 skeleton_neuron projection (normalized)", report_html)
            self.assertIn("Root 303 point_neuron projection (normalized)", report_html)
            self.assertEqual(persisted_summary["bundle_count"], 1)
            self.assertEqual(
                persisted_summary["compared_bundles"][0]["root_morphology_classes"],
                ["surface_neuron", "skeleton_neuron", "point_neuron"],
            )

def _materialize_mixed_visualization_fixture(tmp_dir: Path) -> dict[str, Path]:
    manifest_path = _write_manifest_fixture(
        tmp_dir,
        surface_wave_fidelity_assignment={
            "default_morphology_class": "point_neuron",
            "root_overrides": [
                {"root_id": 101, "morphology_class": "surface_neuron"},
                {"root_id": 202, "morphology_class": "skeleton_neuron"},
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
                "root_id": 202,
                "project_role": "skeleton_simulated",
                "asset_profile": "skeleton",
            },
            {
                "root_id": 303,
                "project_role": "surface_simulated",
                "asset_profile": "surface",
            },
        ],
    )
    _rewrite_mixed_visualization_config(config_path)
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
        root_ids=[101, 202, 303],
    )
    return {
        "manifest_path": manifest_path,
        "config_path": config_path,
        "schema_path": schema_path,
        "design_lock_path": design_lock_path,
    }


def _rewrite_mixed_visualization_config(config_path: Path) -> None:
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


if __name__ == "__main__":
    unittest.main()
