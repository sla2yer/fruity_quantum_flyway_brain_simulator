from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.stimulus_bundle import (
    FRAME_CACHE_REPLAY_SOURCE,
    STIMULUS_FRAME_CACHE_VERSION,
    load_recorded_stimulus_bundle,
    resolve_stimulus_input,
)
from flywire_wave.stimulus_contract import load_stimulus_bundle_metadata
from flywire_wave.stimulus_generators import synthesize_stimulus


class StimulusBundleWorkflowTest(unittest.TestCase):
    def test_record_and_replay_script_generate_deterministic_bundle_cache_and_preview(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            config_path = _write_stimulus_bundle_config(tmp_dir)

            first_record = self._run_bundle_command(
                "record",
                "--config",
                str(config_path),
            )

            metadata_path = Path(first_record["stimulus_bundle_metadata_path"])
            frame_cache_path = Path(first_record["frame_cache_path"])
            preview_report_path = Path(first_record["preview_report_path"])
            preview_summary_path = Path(first_record["preview_summary_path"])
            preview_output_dir = Path(first_record["preview_output_dir"])

            self.assertTrue(metadata_path.exists())
            self.assertTrue(frame_cache_path.exists())
            self.assertTrue(preview_report_path.exists())
            self.assertTrue(preview_summary_path.exists())
            self.assertTrue(preview_output_dir.exists())

            expected_bundle_dir = (
                tmp_dir
                / "out"
                / "stimuli"
                / "bundles"
                / "translated_edge"
                / "simple_translated_edge"
                / first_record["parameter_hash"]
            ).resolve()
            self.assertEqual(Path(first_record["bundle_directory"]), expected_bundle_dir)
            self.assertEqual(metadata_path, expected_bundle_dir / "stimulus_bundle.json")
            self.assertEqual(frame_cache_path, expected_bundle_dir / "stimulus_frames.npz")
            self.assertEqual(preview_output_dir, expected_bundle_dir / "preview")
            self.assertEqual(preview_report_path, preview_output_dir / "index.html")
            self.assertEqual(preview_summary_path, preview_output_dir / "summary.json")

            first_metadata_text = metadata_path.read_text(encoding="utf-8")
            first_frame_cache_bytes = frame_cache_path.read_bytes()
            first_preview_html = preview_report_path.read_text(encoding="utf-8")
            first_preview_summary_text = preview_summary_path.read_text(encoding="utf-8")

            second_record = self._run_bundle_command(
                "record",
                "--config",
                str(config_path),
            )

            self.assertEqual(
                second_record["stimulus_bundle_metadata_path"],
                first_record["stimulus_bundle_metadata_path"],
            )
            self.assertEqual(second_record["frame_cache_path"], first_record["frame_cache_path"])
            self.assertEqual(
                second_record["preview_report_path"],
                first_record["preview_report_path"],
            )
            self.assertEqual(
                metadata_path.read_text(encoding="utf-8"),
                first_metadata_text,
            )
            self.assertEqual(frame_cache_path.read_bytes(), first_frame_cache_bytes)
            self.assertEqual(preview_report_path.read_text(encoding="utf-8"), first_preview_html)
            self.assertEqual(
                preview_summary_path.read_text(encoding="utf-8"),
                first_preview_summary_text,
            )

            metadata = load_stimulus_bundle_metadata(metadata_path)
            self.assertEqual(metadata["recording"]["frame_cache_version"], STIMULUS_FRAME_CACHE_VERSION)
            self.assertEqual(
                metadata["preview"]["selected_frame_indices"],
                [0, 5, 25, 44, 49],
            )
            self.assertEqual(
                metadata["preview"]["report_path"],
                str(preview_report_path.resolve()),
            )
            self.assertEqual(
                metadata["preview"]["summary_path"],
                str(preview_summary_path.resolve()),
            )

            replay = load_recorded_stimulus_bundle(metadata_path)
            self.assertEqual(replay.replay_source, FRAME_CACHE_REPLAY_SOURCE)
            resolved_input = resolve_stimulus_input(config_path=config_path)
            expected_render = synthesize_stimulus(resolved_input.resolved_stimulus)
            np.testing.assert_array_equal(replay.frames, expected_render.frames)
            np.testing.assert_allclose(replay.frame_times_ms, expected_render.frame_times_ms)

            replay_summary = self._run_bundle_command(
                "replay",
                "--bundle-metadata",
                str(metadata_path),
                "--time-ms",
                "0.0",
                "--time-ms",
                "50.0",
                "--time-ms",
                "449.9",
                "--time-ms",
                "490.0",
            )
            self.assertEqual(replay_summary["replay_source"], FRAME_CACHE_REPLAY_SOURCE)
            self.assertEqual(
                [sample["frame_index"] for sample in replay_summary["requested_samples"]],
                [0, 5, 44, 49],
            )
            self.assertEqual(
                replay_summary["preview_report_path"],
                str(preview_report_path.resolve()),
            )
            self.assertEqual(
                replay_summary["preview_summary_path"],
                str(preview_summary_path.resolve()),
            )

    def _run_bundle_command(self, *args: str) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "10_stimulus_bundle.py"), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(
                "10_stimulus_bundle.py failed\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        return json.loads(result.stdout)


def _write_stimulus_bundle_config(tmp_dir: Path) -> Path:
    config_path = tmp_dir / "stimulus_bundle_config.yaml"
    config_path.write_text(
        textwrap.dedent(
            f"""
            paths:
              processed_stimulus_dir: {tmp_dir / "out" / "stimuli"}

            stimulus:
              stimulus_family: moving_edge
              stimulus_name: simple_moving_edge
              determinism:
                seed: 17
              stimulus_overrides:
                background: 0.45
                speed_deg_per_s: 55.0
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return config_path


if __name__ == "__main__":
    unittest.main()
