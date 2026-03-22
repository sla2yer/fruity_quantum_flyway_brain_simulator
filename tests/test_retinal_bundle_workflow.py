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

from flywire_wave.retinal_bundle import load_recorded_retinal_bundle


class RetinalBundleWorkflowTest(unittest.TestCase):
    def test_record_and_replay_stimulus_driven_retinal_bundle_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = _write_retinal_stimulus_config(tmp_dir)

            first_record = self._run_bundle_command(
                "record",
                "--config",
                str(config_path),
            )
            second_record = self._run_bundle_command(
                "record",
                "--config",
                str(config_path),
            )

            metadata_path = Path(first_record["retinal_bundle_metadata_path"])
            archive_path = Path(first_record["frame_archive_path"])
            self.assertTrue(metadata_path.exists())
            self.assertTrue(archive_path.exists())
            first_metadata_text = metadata_path.read_text(encoding="utf-8")
            first_archive_bytes = archive_path.read_bytes()
            self.assertEqual(
                first_record["retinal_bundle_metadata_path"],
                second_record["retinal_bundle_metadata_path"],
            )
            self.assertEqual(first_record["frame_archive_path"], second_record["frame_archive_path"])
            self.assertEqual(metadata_path.read_text(encoding="utf-8"), first_metadata_text)
            self.assertEqual(archive_path.read_bytes(), first_archive_bytes)

            expected_bundle_dir = (
                tmp_dir
                / "out"
                / "retinal"
                / "bundles"
                / "stimulus_bundle"
                / "translated_edge"
                / "simple_translated_edge"
                / first_record["source_reference"]["source_hash"]
                / first_record["retinal_spec_hash"]
            ).resolve()
            self.assertEqual(Path(first_record["bundle_directory"]), expected_bundle_dir)
            self.assertEqual(metadata_path, expected_bundle_dir / "retinal_input_bundle.json")
            self.assertEqual(archive_path, expected_bundle_dir / "retinal_frames.npz")
            self.assertEqual(first_record["source_reference"]["source_kind"], "stimulus_bundle")

            replay = load_recorded_retinal_bundle(metadata_path)
            self.assertEqual(
                replay.source_descriptor["source_metadata"]["lineage"]["upstream_source_kind"],
                "stimulus_bundle",
            )
            self.assertTrue(
                Path(
                    replay.source_descriptor["source_metadata"]["lineage"][
                        "upstream_bundle_metadata_path"
                    ]
                ).exists()
            )

            replay_summary = self._run_bundle_command(
                "replay",
                "--config",
                str(config_path),
                "--time-ms",
                "0.0",
                "--time-ms",
                "20.0",
                "--time-ms",
                "55.0",
            )
            self.assertEqual(
                [sample["frame_index"] for sample in replay_summary["requested_samples"]],
                [0, 2, 5],
            )
            self.assertEqual(
                replay_summary["source_lineage"]["upstream_bundle_id"],
                replay.source_descriptor["source_metadata"]["lineage"]["upstream_bundle_id"],
            )

    def test_record_and_replay_scene_driven_retinal_bundle_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            scene_path = _write_scene_entrypoint(tmp_dir)

            first_record = self._run_bundle_command(
                "record",
                "--scene",
                str(scene_path),
            )
            second_record = self._run_bundle_command(
                "record",
                "--scene",
                str(scene_path),
            )

            metadata_path = Path(first_record["retinal_bundle_metadata_path"])
            archive_path = Path(first_record["frame_archive_path"])
            self.assertTrue(metadata_path.exists())
            self.assertTrue(archive_path.exists())
            first_metadata_text = metadata_path.read_text(encoding="utf-8")
            first_archive_bytes = archive_path.read_bytes()
            self.assertEqual(
                first_record["retinal_bundle_metadata_path"],
                second_record["retinal_bundle_metadata_path"],
            )
            self.assertEqual(first_record["frame_archive_path"], second_record["frame_archive_path"])
            self.assertEqual(metadata_path.read_text(encoding="utf-8"), first_metadata_text)
            self.assertEqual(archive_path.read_bytes(), first_archive_bytes)

            expected_bundle_dir = (
                tmp_dir
                / "out"
                / "retinal"
                / "bundles"
                / "scene_description"
                / "analytic_panorama"
                / "yaw_gradient_panorama"
                / first_record["source_reference"]["source_hash"]
                / first_record["retinal_spec_hash"]
            ).resolve()
            self.assertEqual(Path(first_record["bundle_directory"]), expected_bundle_dir)
            self.assertEqual(first_record["source_reference"]["source_kind"], "scene_description")

            replay = load_recorded_retinal_bundle(metadata_path)
            self.assertEqual(
                replay.source_descriptor["source_metadata"]["lineage"]["scene_path"],
                str(scene_path.resolve()),
            )

            replay_summary = self._run_bundle_command(
                "replay",
                "--scene",
                str(scene_path),
                "--time-ms",
                "0.0",
                "--time-ms",
                "25.0",
                "--time-ms",
                "59.0",
            )
            self.assertEqual(
                [sample["frame_index"] for sample in replay_summary["requested_samples"]],
                [0, 1, 2],
            )
            mean_values = [sample["mean_irradiance"] for sample in replay_summary["requested_samples"]]
            self.assertNotEqual(mean_values[0], mean_values[-1])

    def _run_bundle_command(self, *args: str) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "12_retinal_bundle.py"), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(
                "12_retinal_bundle.py failed\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        return json.loads(result.stdout)


def _write_retinal_stimulus_config(tmp_dir: Path) -> Path:
    config_path = tmp_dir / "retinal_stimulus_config.yaml"
    config_path.write_text(
        textwrap.dedent(
            f"""
            paths:
              processed_stimulus_dir: {tmp_dir / "out" / "stimuli"}
              processed_retinal_dir: {tmp_dir / "out" / "retinal"}

            stimulus:
              stimulus_family: translated_edge
              stimulus_name: simple_translated_edge
              determinism:
                seed: 11
              stimulus_overrides:
                onset_ms: 0.0
                offset_ms: 80.0
                background_level: 0.2
                contrast: 0.6
                velocity_deg_per_s: 20.0
                edge_width_deg: 12.0

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
                acceptance_angle_deg: 0.5
                support_radius_deg: 1.0
                background_fill_value: 0.25
              body_pose:
                translation_world_mm: [0.0, 0.0, 0.0]
                yaw_pitch_roll_deg: [3.0, 0.0, 0.0]
              head_pose:
                translation_body_mm: [0.32, 0.0, 0.1]
                yaw_pitch_roll_deg: [4.0, 0.0, 0.0]
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return config_path


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
                duration_ms: 60.0
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
