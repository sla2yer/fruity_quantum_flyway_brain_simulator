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


class RetinalInspectionWorkflowTest(unittest.TestCase):
    def test_inspect_command_generates_deterministic_report_bundle(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            scene_path = _write_scene_entrypoint(tmp_dir)

            first_run = self._run_inspection("--scene", str(scene_path))
            second_run = self._run_inspection("--scene", str(scene_path))

            metadata_path = Path(first_run["retinal_bundle_metadata_path"])
            report_dir = metadata_path.parent / "inspection"
            index_path = report_dir / "index.html"
            summary_path = report_dir / "summary.json"
            markdown_path = report_dir / "report.md"
            coverage_path = report_dir / "coverage_layout.svg"

            self.assertTrue(index_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue(markdown_path.exists())
            self.assertTrue(coverage_path.exists())

            html_text = index_path.read_text(encoding="utf-8")
            self.assertIn("Offline Retinal Inspection", html_text)
            self.assertIn("Detector Coverage and Lattice Layout", html_text)
            self.assertIn("Representative Frames", html_text)

            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["report_version"], "retinal_inspection.v1")
            self.assertEqual(summary_payload["retinal_bundle_metadata_path"], str(metadata_path.resolve()))
            self.assertEqual(summary_payload["output_dir"], str(report_dir.resolve()))
            self.assertEqual(summary_payload["report_path"], str(index_path.resolve()))
            self.assertEqual(summary_payload["summary_path"], str(summary_path.resolve()))
            self.assertEqual(summary_payload["markdown_path"], str(markdown_path.resolve()))
            self.assertEqual(summary_payload["coverage_layout_svg_path"], str(coverage_path.resolve()))
            self.assertEqual(summary_payload["source_preview"]["source_kind"], "scene_description")
            self.assertTrue(summary_payload["source_preview"]["available"])
            self.assertEqual(summary_payload["coverage"]["overall_status"], "pass")
            self.assertEqual(summary_payload["qa"]["overall_status"], "pass")
            self.assertGreater(len(summary_payload["selected_frames"]), 0)
            self.assertEqual(first_run["selected_frame_indices"], second_run["selected_frame_indices"])
            self.assertEqual(first_run["output_dir"], second_run["output_dir"])
            self.assertEqual(first_run["report_path"], second_run["report_path"])
            self.assertTrue(first_run["bundle_materialized"])
            self.assertFalse(second_run["bundle_materialized"])

            check_names = {check["name"] for check in summary_payload["qa"]["checks"]}
            self.assertIn("detector_coverage", check_names)
            self.assertIn("frame_times", check_names)
            self.assertIn("detector_values_unit_interval", check_names)

            for frame_record in summary_payload["selected_frames"]:
                self.assertTrue(Path(frame_record["retinal_view_svg_path"]).exists())
                self.assertTrue(Path(frame_record["world_view_svg_path"]).exists())

            metadata_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertIn("inspection", metadata_payload)
            self.assertEqual(
                metadata_payload["inspection"]["report_path"],
                str(index_path.resolve()),
            )
            self.assertEqual(
                metadata_payload["inspection"]["overall_status"],
                "pass",
            )

    def _run_inspection(self, *args: str) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "12_retinal_bundle.py"), "inspect", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(
                "12_retinal_bundle.py inspect failed\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        return json.loads(result.stdout)


def _write_scene_entrypoint(tmp_dir: Path) -> Path:
    scene_path = tmp_dir / "fixture_scene.yaml"
    scene_path.write_text(
        textwrap.dedent(
            f"""
            paths:
              processed_retinal_dir: {tmp_dir / "out" / "retinal"}

            scene:
              scene_family: analytic_panorama
              scene_name: yaw_gradient_panorama
              temporal_sampling:
                time_origin_ms: 0.0
                dt_ms: 20.0
                duration_ms: 80.0
              scene_parameters:
                background_level: 0.45
                azimuth_gain_per_deg: 0.001
                elevation_gain_per_deg: 0.0005
                temporal_modulation_amplitude: 0.1
                temporal_frequency_hz: 2.0
                phase_deg: 15.0

            retinal_geometry:
              geometry_name: fixture
              eyes:
                left:
                  optical_axis_head: [1.0, 0.0, 0.0]
                  torsion_deg: 0.0
                symmetry:
                  mode: mirror_across_head_sagittal_plane

            retinal_recording:
              sampling_kernel:
                acceptance_angle_deg: 0.6
                support_radius_deg: 1.2
                background_fill_value: 0.3
              body_pose:
                translation_world_mm: [0.0, 0.0, 0.0]
                yaw_pitch_roll_deg: [8.0, 0.0, 0.0]
              head_pose:
                translation_body_mm: [0.32, 0.0, 0.1]
                yaw_pitch_roll_deg: [5.0, 0.0, 0.0]
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return scene_path


if __name__ == "__main__":
    unittest.main()
