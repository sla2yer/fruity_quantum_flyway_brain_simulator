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


class GeometryPreviewScriptTest(unittest.TestCase):
    def test_preview_script_generates_deterministic_html_report(self) -> None:
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
            process_mesh_into_wave_assets(
                root_id=101,
                bundle_paths=bundle_paths,
                simplify_target_faces=8,
                patch_hops=1,
                patch_vertex_cap=2,
                registry_metadata={"cell_type": "T5a", "project_role": "surface_simulated"},
            )

            config_path = _write_preview_config(tmp_dir)

            first_run = self._run_preview(config_path)
            second_run = self._run_preview(config_path)

            preview_dir = tmp_dir / "out" / "previews" / "root-ids-101"
            index_path = preview_dir / "index.html"
            summary_path = preview_dir / "summary.json"
            root_ids_path = preview_dir / "root_ids.txt"

            self.assertTrue(index_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue(root_ids_path.exists())

            html_text = index_path.read_text(encoding="utf-8")
            self.assertIn("Offline Geometry Preview", html_text)
            self.assertIn("Raw Mesh", html_text)
            self.assertIn("Simplified Mesh", html_text)
            self.assertIn("Skeleton", html_text)
            self.assertIn("Surface Graph", html_text)
            self.assertIn("Patch Graph", html_text)
            self.assertIn("Root 101", html_text)

            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["root_ids"], [101])
            self.assertEqual(summary_payload["output_dir"], str(preview_dir.resolve()))
            self.assertEqual(summary_payload["report_path"], str(index_path.resolve()))
            self.assertEqual(summary_payload["summary_path"], str(summary_path.resolve()))
            self.assertEqual(summary_payload["root_ids_path"], str(root_ids_path.resolve()))
            self.assertIn(summary_payload["roots"]["101"]["qa_overall_status"], {"pass", "warn"})
            self.assertTrue(summary_payload["roots"]["101"]["skeleton_available"])

            self.assertEqual(first_run["output_dir"], second_run["output_dir"])
            self.assertEqual(first_run["report_path"], second_run["report_path"])

    def _run_preview(self, config_path: Path) -> dict[str, object]:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "05_preview_geometry.py"),
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
                "05_preview_geometry.py failed\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        return json.loads(result.stdout)


def _write_preview_config(tmp_dir: Path) -> Path:
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
              geometry_preview_dir: {tmp_dir / "out" / "previews"}
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


def _write_stub_swc(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """
            1 1 0 0 0 1 -1
            2 3 1 0 0 1 1
            3 3 0 1 0 1 1
            4 3 0 0 1 1 1
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
