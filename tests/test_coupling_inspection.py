from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.geometry_contract import build_geometry_bundle_paths
from flywire_wave.mesh_pipeline import process_mesh_into_wave_assets
from flywire_wave.synapse_mapping import materialize_synapse_anchor_maps


class CouplingInspectionScriptTest(unittest.TestCase):
    def test_coupling_inspection_script_generates_deterministic_report_bundle(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            _materialize_fixture(tmp_dir)
            config_path = _write_coupling_inspection_config(tmp_dir)

            first_run = self._run_coupling_inspection(config_path)
            second_run = self._run_coupling_inspection(config_path)

            report_dir = tmp_dir / "out" / "coupling_inspection" / "edges-202-to-101"
            index_path = report_dir / "index.html"
            summary_path = report_dir / "summary.json"
            markdown_path = report_dir / "report.md"
            edge_specs_path = report_dir / "edges.txt"
            detail_json_path = report_dir / "202__to__101_details.json"
            source_svg_path = report_dir / "202__to__101_source_readout.svg"
            target_svg_path = report_dir / "202__to__101_target_landing.svg"

            self.assertTrue(index_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue(markdown_path.exists())
            self.assertTrue(edge_specs_path.exists())
            self.assertTrue(detail_json_path.exists())
            self.assertTrue(source_svg_path.exists())
            self.assertTrue(target_svg_path.exists())

            html_text = index_path.read_text(encoding="utf-8")
            self.assertIn("Offline Coupling Inspection Report", html_text)
            self.assertIn("Edge 202 -&gt; 101", html_text)
            self.assertIn("Presynaptic Summary", html_text)
            self.assertIn("Postsynaptic Summary", html_text)
            self.assertIn("Aggregation Summary", html_text)
            self.assertIn("Blocked Synapses", html_text)

            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["edge_count"], 1)
            self.assertEqual(
                summary_payload["edges"],
                [
                    {
                        "pre_root_id": 202,
                        "post_root_id": 101,
                        "edge_label": "202__to__101",
                    }
                ],
            )
            self.assertEqual(summary_payload["overall_status"], "warn")
            self.assertEqual(summary_payload["blocked_edge_count"], 0)
            self.assertEqual(summary_payload["output_dir"], str(report_dir.resolve()))
            self.assertEqual(summary_payload["report_path"], str(index_path.resolve()))
            self.assertEqual(summary_payload["summary_path"], str(summary_path.resolve()))
            self.assertEqual(summary_payload["markdown_path"], str(markdown_path.resolve()))
            self.assertEqual(summary_payload["edge_specs_path"], str(edge_specs_path.resolve()))

            edge_summary = summary_payload["edges_by_id"]["202__to__101"]
            self.assertEqual(edge_summary["overall_status"], "warn")
            self.assertEqual(edge_summary["synapse_count"], 5)
            self.assertEqual(edge_summary["usable_synapse_count"], 4)
            self.assertEqual(edge_summary["blocked_synapse_count"], 1)
            self.assertEqual(edge_summary["component_count"], 2)
            self.assertAlmostEqual(edge_summary["pre_mapped_fraction"], 0.8, places=7)
            self.assertAlmostEqual(edge_summary["post_mapped_fraction"], 1.0, places=7)
            self.assertEqual(
                edge_summary["artifacts"]["source_svg_path"],
                str(source_svg_path.resolve()),
            )
            self.assertEqual(
                edge_summary["artifacts"]["target_svg_path"],
                str(target_svg_path.resolve()),
            )

            detail_payload = json.loads(detail_json_path.read_text(encoding="utf-8"))
            self.assertEqual(detail_payload["edge_label"], "202__to__101")
            self.assertEqual(detail_payload["summary"]["overall_status"], "warn")
            self.assertEqual(detail_payload["edge_bundle_summary"]["synapse_count"], 5)
            self.assertEqual(detail_payload["edge_bundle_summary"]["usable_synapse_count"], 4)
            self.assertEqual(detail_payload["edge_bundle_summary"]["blocked_synapse_count"], 1)
            self.assertEqual(detail_payload["aggregation_summary"]["component_count"], 2)
            self.assertEqual(
                detail_payload["delay_summary"]["delay_model"],
                "euclidean_anchor_distance_over_velocity",
            )
            self.assertEqual(detail_payload["sign_summary"]["synapse_sign_counts"]["excitatory"], 4)
            self.assertEqual(detail_payload["sign_summary"]["synapse_sign_counts"]["inhibitory"], 1)
            self.assertEqual(detail_payload["source_geometry"]["skeleton_node_count"], 4)
            self.assertGreater(detail_payload["target_geometry"]["patch_count"], 0)
            self.assertEqual(
                detail_payload["artifacts"]["details_json_path"],
                str(detail_json_path.resolve()),
            )
            self.assertEqual(
                detail_payload["artifacts"]["source_svg_path"],
                str(source_svg_path.resolve()),
            )
            self.assertEqual(
                detail_payload["artifacts"]["target_svg_path"],
                str(target_svg_path.resolve()),
            )
            self.assertEqual(detail_payload["blocked_synapses"][0]["synapse_id"], "edge-e")

            qa_flags = {item["name"]: item["status"] for item in detail_payload["qa_flags"]}
            self.assertEqual(qa_flags["Presynaptic mapping"], "warn")
            self.assertEqual(qa_flags["Artifact consistency"], "pass")
            self.assertEqual(qa_flags["Delay integrity"], "pass")

            self.assertEqual(first_run["output_dir"], second_run["output_dir"])
            self.assertEqual(first_run["report_path"], second_run["report_path"])

    def _run_coupling_inspection(self, config_path: Path) -> dict[str, object]:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "08_coupling_inspection.py"),
                "--config",
                str(config_path),
                "--edge",
                "202:101",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(
                "08_coupling_inspection.py failed\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        return json.loads(result.stdout)


def _materialize_fixture(base_dir: Path) -> None:
    bundle_paths_101 = build_geometry_bundle_paths(
        101,
        meshes_raw_dir=base_dir / "out" / "meshes_raw",
        skeletons_raw_dir=base_dir / "out" / "skeletons_raw",
        processed_mesh_dir=base_dir / "out" / "processed_meshes",
        processed_graph_dir=base_dir / "out" / "processed_graphs",
    )
    _write_octahedron_mesh(bundle_paths_101.raw_mesh_path)
    process_mesh_into_wave_assets(
        root_id=101,
        bundle_paths=bundle_paths_101,
        simplify_target_faces=8,
        patch_hops=1,
        patch_vertex_cap=2,
        registry_metadata={"cell_type": "T5a", "project_role": "surface_simulated"},
    )

    bundle_paths_202 = build_geometry_bundle_paths(
        202,
        meshes_raw_dir=base_dir / "out" / "meshes_raw",
        skeletons_raw_dir=base_dir / "out" / "skeletons_raw",
        processed_mesh_dir=base_dir / "out" / "processed_meshes",
        processed_graph_dir=base_dir / "out" / "processed_graphs",
    )
    _write_stub_swc(bundle_paths_202.raw_skeleton_path)

    coupling_dir = base_dir / "out" / "processed_coupling"
    _write_synapse_registry(coupling_dir / "synapse_registry.csv")
    neuron_registry = pd.DataFrame(
        {
            "root_id": [101, 202],
            "project_role": ["surface_simulated", "skeleton_simulated"],
        }
    )
    summary = materialize_synapse_anchor_maps(
        root_ids=[101, 202],
        processed_coupling_dir=coupling_dir,
        meshes_raw_dir=base_dir / "out" / "meshes_raw",
        skeletons_raw_dir=base_dir / "out" / "skeletons_raw",
        processed_mesh_dir=base_dir / "out" / "processed_meshes",
        processed_graph_dir=base_dir / "out" / "processed_graphs",
        neuron_registry=neuron_registry,
        synapse_registry_path=coupling_dir / "synapse_registry.csv",
        coupling_assembly={
            "kernel_family": "separable_rank_one_cloud",
            "delay_model": {
                "mode": "euclidean_anchor_distance_over_velocity",
                "base_delay_ms": 0.25,
                "velocity_distance_units_per_ms": 2.0,
                "delay_bin_size_ms": 10.0,
            },
        },
    )
    assert summary["edge_count"] == 1


def _write_coupling_inspection_config(tmp_dir: Path) -> Path:
    config_path = tmp_dir / "config.yaml"
    config_path.write_text(
        textwrap.dedent(
            f"""
            paths:
              meshes_raw_dir: {tmp_dir / "out" / "meshes_raw"}
              skeletons_raw_dir: {tmp_dir / "out" / "skeletons_raw"}
              processed_mesh_dir: {tmp_dir / "out" / "processed_meshes"}
              processed_graph_dir: {tmp_dir / "out" / "processed_graphs"}
              processed_coupling_dir: {tmp_dir / "out" / "processed_coupling"}
              coupling_inspection_dir: {tmp_dir / "out" / "coupling_inspection"}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return config_path


def _write_synapse_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "synapse_row_id": "fixture.csv#1",
                "source_row_number": 1,
                "synapse_id": "edge-a",
                "pre_root_id": 202,
                "post_root_id": 101,
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "pre_x": 1.0,
                "pre_y": 0.0,
                "pre_z": 0.0,
                "post_x": 0.0,
                "post_y": 0.0,
                "post_z": 1.0,
                "neuropil": "LOP_R",
                "nt_type": "ACH",
                "sign": "excitatory",
                "confidence": 0.99,
                "weight": 1.0,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
            {
                "synapse_row_id": "fixture.csv#2",
                "source_row_number": 2,
                "synapse_id": "edge-b",
                "pre_root_id": 202,
                "post_root_id": 101,
                "x": 0.0,
                "y": 0.2,
                "z": 0.0,
                "pre_x": 0.0,
                "pre_y": 1.0,
                "pre_z": 0.0,
                "post_x": 1.0,
                "post_y": 0.0,
                "post_z": 0.0,
                "neuropil": "LOP_R",
                "nt_type": "ACH",
                "sign": "excitatory",
                "confidence": 0.95,
                "weight": 0.5,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
            {
                "synapse_row_id": "fixture.csv#3",
                "source_row_number": 3,
                "synapse_id": "edge-c",
                "pre_root_id": 202,
                "post_root_id": 101,
                "x": 0.0,
                "y": -0.2,
                "z": 0.0,
                "pre_x": 0.0,
                "pre_y": 0.0,
                "pre_z": -1.0,
                "post_x": 0.0,
                "post_y": 1.0,
                "post_z": 0.0,
                "neuropil": "LOP_R",
                "nt_type": "ACH",
                "sign": "excitatory",
                "confidence": 0.9,
                "weight": 0.25,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
            {
                "synapse_row_id": "fixture.csv#4",
                "source_row_number": 4,
                "synapse_id": "edge-d",
                "pre_root_id": 202,
                "post_root_id": 101,
                "x": 0.1,
                "y": 0.0,
                "z": 0.0,
                "pre_x": 1.0,
                "pre_y": 0.0,
                "pre_z": 0.0,
                "post_x": -1.0,
                "post_y": 0.0,
                "post_z": 0.0,
                "neuropil": "LOP_R",
                "nt_type": "GABA",
                "sign": "inhibitory",
                "confidence": 0.85,
                "weight": -0.75,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
            {
                "synapse_row_id": "fixture.csv#5",
                "source_row_number": 5,
                "synapse_id": "edge-e",
                "pre_root_id": 202,
                "post_root_id": 101,
                "x": np.nan,
                "y": np.nan,
                "z": np.nan,
                "pre_x": np.nan,
                "pre_y": np.nan,
                "pre_z": np.nan,
                "post_x": 0.0,
                "post_y": -1.0,
                "post_z": 0.0,
                "neuropil": "LOP_R",
                "nt_type": "ACH",
                "sign": "excitatory",
                "confidence": 0.7,
                "weight": 0.4,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
        ]
    ).to_csv(path, index=False)


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
            0 0 1
            1 0 0
            0 1 0
            -1 0 0
            0 -1 0
            0 0 -1
            3 0 1 2
            3 0 2 3
            3 0 3 4
            3 0 4 1
            3 5 2 1
            3 5 3 2
            3 5 4 3
            3 5 1 4
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_stub_swc(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# stub skeleton",
                "1 1 0 0 1 1 -1",
                "2 3 1 0 0 1 1",
                "3 3 0 1 0 1 1",
                "4 3 0 0 -1 1 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
