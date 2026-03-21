from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.geometry_contract import (
    build_geometry_bundle_paths,
    build_geometry_manifest_record,
    write_geometry_manifest,
)
from flywire_wave.milestone6_readiness import generate_milestone6_readiness_report
from flywire_wave.mesh_pipeline import process_mesh_into_wave_assets
from flywire_wave.operator_qa import generate_operator_qa_report


class Milestone6ReadinessReportTest(unittest.TestCase):
    def test_generate_readiness_report_writes_deterministic_paths(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            bundle_paths = build_geometry_bundle_paths(
                101,
                meshes_raw_dir=tmp_dir / "out" / "meshes_raw",
                skeletons_raw_dir=tmp_dir / "out" / "skeletons_raw",
                processed_mesh_dir=tmp_dir / "out" / "processed_meshes",
                processed_graph_dir=tmp_dir / "out" / "processed_graphs",
            )
            _write_octahedron_mesh(bundle_paths.raw_mesh_path)
            _write_stub_swc(bundle_paths.raw_skeleton_path)

            outputs = process_mesh_into_wave_assets(
                root_id=101,
                bundle_paths=bundle_paths,
                simplify_target_faces=8,
                patch_hops=1,
                patch_vertex_cap=2,
                registry_metadata={"cell_type": "T5a", "project_role": "surface_simulated"},
            )

            manifest_path = tmp_dir / "out" / "asset_manifest.json"
            meshing_config = {
                "fetch_skeletons": True,
                "patch_hops": 1,
                "patch_vertex_cap": 2,
                "operator_assembly": {
                    "version": "operator_assembly.v1",
                    "boundary_condition": {"mode": "closed_surface_zero_flux"},
                    "anisotropy": {"model": "isotropic"},
                },
                "transfer_restriction_mode": "lumped_mass_patch_average",
                "transfer_prolongation_mode": "constant_on_patch",
            }
            record = build_geometry_manifest_record(
                bundle_paths=bundle_paths,
                asset_statuses=outputs["asset_statuses"],
                dataset_name="public",
                materialization_version=783,
                meshing_config_snapshot=meshing_config,
                registry_metadata={"cell_type": "T5a", "project_role": "surface_simulated"},
                bundle_metadata=outputs["bundle_metadata"],
                operator_bundle_metadata=outputs["operator_bundle_metadata"],
            )
            write_geometry_manifest(
                manifest_path=manifest_path,
                bundle_records={101: record},
                dataset_name="public",
                materialization_version=783,
                meshing_config_snapshot=meshing_config,
            )

            summary = generate_operator_qa_report(
                root_ids=[101],
                meshes_raw_dir=bundle_paths.raw_mesh_path.parent,
                skeletons_raw_dir=bundle_paths.raw_skeleton_path.parent,
                processed_mesh_dir=bundle_paths.simplified_mesh_path.parent,
                processed_graph_dir=bundle_paths.surface_graph_path.parent,
                operator_qa_dir=tmp_dir / "out" / "operator_qa",
                pulse_step_count=8,
            )
            self.assertEqual(summary["root_ids"], [101])

            config_path = tmp_dir / "config.yaml"
            config_path.write_text("paths: {}\n", encoding="utf-8")

            report = generate_milestone6_readiness_report(
                config_path=config_path,
                manifest_path=manifest_path,
                operator_qa_dir=tmp_dir / "out" / "operator_qa",
                root_ids=[101],
                fixture_verification={"status": "pass", "command": "python -m unittest"},
                build_command={"status": "pass", "command": "scripts/03_build_wave_assets.py --config config.yaml"},
                operator_qa_command={"status": "pass", "command": "scripts/06_operator_qa.py --config config.yaml"},
            )

            report_dir = tmp_dir / "out" / "operator_qa" / "root-ids-101"
            markdown_path = report_dir / "milestone_6_readiness.md"
            json_path = report_dir / "milestone_6_readiness.json"

            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())
            self.assertEqual(report["report_dir"], str(report_dir.resolve()))
            self.assertEqual(report["markdown_path"], str(markdown_path.resolve()))
            self.assertEqual(report["json_path"], str(json_path.resolve()))
            self.assertEqual(report["contract_audit"]["geometry_assets_ready_root_count"], 1)
            self.assertEqual(report["contract_audit"]["operator_assets_ready_root_count"], 1)
            self.assertEqual(report["surface_simulated_root_count"], 1)
            self.assertEqual(report["follow_on_issues"], [])
            self.assertIn(report["milestone10_readiness"]["status"], {"ready", "review"})
            self.assertTrue(report["milestone10_readiness"]["ready_for_engine_work"])

            markdown_text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("Milestone 6 Readiness Report", markdown_text)
            self.assertIn("Readiness verdict", markdown_text)

            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["markdown_path"], report["markdown_path"])


def _write_octahedron_mesh(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """
            ply
            format ascii 1.0
            element vertex 6
            property float x
            property float y
            property float z
            element face 8
            property list uchar int vertex_indices
            end_header
            1 0 0
            -1 0 0
            0 1 0
            0 -1 0
            0 0 1
            0 0 -1
            3 0 2 4
            3 2 1 4
            3 1 3 4
            3 3 0 4
            3 2 0 5
            3 1 2 5
            3 3 1 5
            3 0 3 5
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_stub_swc(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """
            1 1 0.0 0.0 0.0 1.0 -1
            2 3 1.0 0.0 0.0 0.5 1
            3 3 0.0 1.0 0.0 0.5 1
            4 3 0.0 0.0 1.0 0.5 1
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
