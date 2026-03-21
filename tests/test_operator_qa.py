from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.geometry_contract import build_geometry_bundle_paths
from flywire_wave.mesh_pipeline import process_mesh_into_wave_assets


class OperatorQAScriptTest(unittest.TestCase):
    def test_operator_qa_script_generates_deterministic_report_bundle(self) -> None:
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
            process_mesh_into_wave_assets(
                root_id=101,
                bundle_paths=bundle_paths,
                simplify_target_faces=8,
                patch_hops=1,
                patch_vertex_cap=2,
                registry_metadata={"cell_type": "T5a", "project_role": "surface_simulated"},
            )

            config_path = _write_operator_qa_config(tmp_dir)

            first_run = self._run_operator_qa(config_path)
            second_run = self._run_operator_qa(config_path)

            report_dir = tmp_dir / "out" / "operator_qa" / "root-ids-101"
            index_path = report_dir / "index.html"
            summary_path = report_dir / "summary.json"
            markdown_path = report_dir / "report.md"
            root_ids_path = report_dir / "root_ids.txt"
            detail_json_path = report_dir / "101_details.json"
            svg_paths = [
                report_dir / "101_pulse_initial.svg",
                report_dir / "101_boundary_mask.svg",
                report_dir / "101_patch_decomposition.svg",
                report_dir / "101_fine_pulse_final.svg",
                report_dir / "101_coarse_pulse_final.svg",
                report_dir / "101_coarse_reconstruction.svg",
                report_dir / "101_reconstruction_error.svg",
            ]

            self.assertTrue(index_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue(markdown_path.exists())
            self.assertTrue(root_ids_path.exists())
            self.assertTrue(detail_json_path.exists())
            for svg_path in svg_paths:
                self.assertTrue(svg_path.exists(), msg=f"missing QA panel {svg_path.name}")

            html_text = index_path.read_text(encoding="utf-8")
            self.assertIn("Offline Operator QA Report", html_text)
            self.assertIn("Pulse Initialization", html_text)
            self.assertIn("Boundary Mask", html_text)
            self.assertIn("Patch Decomposition", html_text)
            self.assertIn("Fine Pulse After Smoke Evolution", html_text)
            self.assertIn("Coarse Reconstruction On Fine Surface", html_text)
            self.assertIn("Reconstruction Error", html_text)

            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["root_ids"], [101])
            self.assertEqual(summary_payload["output_dir"], str(report_dir.resolve()))
            self.assertEqual(summary_payload["report_path"], str(index_path.resolve()))
            self.assertEqual(summary_payload["summary_path"], str(summary_path.resolve()))
            self.assertEqual(summary_payload["markdown_path"], str(markdown_path.resolve()))
            self.assertEqual(summary_payload["root_ids_path"], str(root_ids_path.resolve()))
            self.assertIn(summary_payload["overall_status"], {"pass", "warn"})
            self.assertIn(summary_payload["milestone10_gate"], {"go", "review"})
            root_summary = summary_payload["roots"]["101"]
            self.assertIn(root_summary["overall_status"], {"pass", "warn"})
            self.assertIn(root_summary["milestone10_gate"], {"go", "review"})
            self.assertTrue(root_summary["milestone10_engine_ready"])
            self.assertEqual(root_summary["pulse_step_count"], 8)
            self.assertEqual(root_summary["boundary_vertex_count"], 0)
            self.assertIn("pulse_fine_energy_increase_relative", root_summary["key_metrics"])

            detail_payload = json.loads(detail_json_path.read_text(encoding="utf-8"))
            self.assertEqual(detail_payload["root_id"], 101)
            self.assertEqual(detail_payload["summary"]["overall_status"], root_summary["overall_status"])
            self.assertEqual(detail_payload["summary"]["milestone10_gate"], root_summary["milestone10_gate"])
            self.assertEqual(detail_payload["pulse"]["seed_patch"], 0)
            self.assertEqual(detail_payload["pulse"]["step_count"], 8)
            self.assertIn("fine_operator_symmetry_residual_inf", detail_payload["metrics"])
            self.assertIn("pulse_fine_mass_relative_drift", detail_payload["metrics"])
            self.assertIn(
                "pulse_final_fine_vs_prolongated_coarse_residual_relative",
                detail_payload["metrics"],
            )
            self.assertEqual(
                detail_payload["artifacts"]["pulse_initial_svg_path"],
                str((report_dir / "101_pulse_initial.svg").resolve()),
            )
            self.assertEqual(
                detail_payload["artifacts"]["details_json_path"],
                str(detail_json_path.resolve()),
            )

            self.assertEqual(first_run["output_dir"], second_run["output_dir"])
            self.assertEqual(first_run["report_path"], second_run["report_path"])

    def _run_operator_qa(self, config_path: Path) -> dict[str, object]:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "06_operator_qa.py"),
                "--config",
                str(config_path),
                "--root-id",
                "101",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(
                "06_operator_qa.py failed\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        return json.loads(result.stdout)


def _write_operator_qa_config(tmp_dir: Path) -> Path:
    config_path = tmp_dir / "config.yaml"
    config_path.write_text(
        textwrap.dedent(
            f"""
            paths:
              selected_root_ids: {tmp_dir / "out" / "root_ids.txt"}
              meshes_raw_dir: {tmp_dir / "out" / "meshes_raw"}
              skeletons_raw_dir: {tmp_dir / "out" / "skeletons_raw"}
              processed_mesh_dir: {tmp_dir / "out" / "processed_meshes"}
              processed_graph_dir: {tmp_dir / "out" / "processed_graphs"}
              operator_qa_dir: {tmp_dir / "out" / "operator_qa"}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_dir / "out").mkdir(exist_ok=True)
    (tmp_dir / "out" / "root_ids.txt").write_text("101\n", encoding="utf-8")
    return config_path


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


if __name__ == "__main__":
    unittest.main()
