from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.simulator_result_contract import (
    build_selected_asset_reference,
    build_simulator_arm_reference,
    build_simulator_manifest_reference,
    build_simulator_readout_definition,
    build_simulator_result_bundle_metadata,
)
from flywire_wave.stimulus_contract import (
    build_stimulus_bundle_metadata,
    write_stimulus_bundle_metadata,
)
from flywire_wave.task_decoder_analysis import (
    READOUT_ANALYSIS_CONTRACT_VERSION,
    TASK_DECODER_INTERFACE_VERSION,
    compute_task_decoder_analysis,
    discover_task_decoder_definitions,
    get_task_decoder_definition,
)


FIXTURE_TIMEBASE = {
    "time_origin_ms": 0.0,
    "dt_ms": 10.0,
    "duration_ms": 70.0,
    "sample_count": 7,
}
FIXTURE_TIME_MS = np.asarray([0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0], dtype=np.float64)


class TaskDecoderAnalysisTest(unittest.TestCase):
    def test_decoder_catalog_explains_canonical_requirements(self) -> None:
        decoder_ids = [item["decoder_id"] for item in discover_task_decoder_definitions()]

        self.assertEqual(decoder_ids, ["motion_vector", "optic_flow"])
        motion_vector = get_task_decoder_definition("motion_vector")
        optic_flow = get_task_decoder_definition("optic_flow")

        self.assertEqual(
            motion_vector["supported_metric_ids"],
            [
                "motion_vector_heading_deg",
                "motion_vector_speed_deg_per_s",
            ],
        )
        self.assertIn(
            "matched preferred/null bundle pair",
            motion_vector["minimum_condition_structure"],
        )
        self.assertEqual(
            optic_flow["required_retinotopic_context_fields"],
            [
                "azimuth_axis_unit_vector",
                "center_azimuth_deg",
                "center_elevation_deg",
                "coordinate_frame",
                "elevation_axis_unit_vector",
            ],
        )

    def test_compute_task_decoder_analysis_emits_deterministic_small_patch_estimates(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            plan = _build_task_analysis_plan_fixture()
            bundle_records = [
                _build_bundle_record(
                    tmp_dir,
                    asset_suffix="preferred_on",
                    condition_ids=["preferred_direction", "on_polarity"],
                    direction_deg=0.0,
                    polarity="positive",
                    trace_values=[2.0, 2.0, 3.0, 7.0, 5.0, 4.0, 2.0],
                    include_patch_center=True,
                ),
                _build_bundle_record(
                    tmp_dir,
                    asset_suffix="null_on",
                    condition_ids=["null_direction", "on_polarity"],
                    direction_deg=180.0,
                    polarity="positive",
                    trace_values=[2.0, 2.0, 2.4, 3.0, 2.6, 2.2, 2.0],
                    include_patch_center=True,
                ),
                _build_bundle_record(
                    tmp_dir,
                    asset_suffix="preferred_off",
                    condition_ids=["preferred_direction", "off_polarity"],
                    direction_deg=0.0,
                    polarity="negative",
                    trace_values=[2.0, 2.0, 2.6, 4.0, 3.2, 2.5, 2.0],
                    include_patch_center=True,
                ),
                _build_bundle_record(
                    tmp_dir,
                    asset_suffix="null_off",
                    condition_ids=["null_direction", "off_polarity"],
                    direction_deg=180.0,
                    polarity="negative",
                    trace_values=[2.0, 2.0, 2.1, 2.5, 2.3, 2.0, 2.0],
                    include_patch_center=True,
                ),
            ]

            result = compute_task_decoder_analysis(
                analysis_plan=plan,
                bundle_records=bundle_records,
            )

            self.assertEqual(result["contract_version"], READOUT_ANALYSIS_CONTRACT_VERSION)
            self.assertEqual(
                result["task_decoder_interface_version"],
                TASK_DECODER_INTERFACE_VERSION,
            )
            self.assertEqual(
                result["supported_metric_ids"],
                [
                    "motion_vector_heading_deg",
                    "motion_vector_speed_deg_per_s",
                    "optic_flow_heading_deg",
                    "optic_flow_speed_deg_per_s",
                ],
            )
            self.assertEqual(result["skipped_recipes"], [])
            self.assertEqual(len(result["metric_rows"]), 4)

            values_by_metric = {
                row["metric_id"]: row["value"]
                for row in result["metric_rows"]
            }
            self.assertEqual(values_by_metric["motion_vector_heading_deg"], 0.0)
            self.assertAlmostEqual(
                values_by_metric["motion_vector_speed_deg_per_s"],
                29.117647058834,
                places=11,
            )
            self.assertEqual(values_by_metric["optic_flow_heading_deg"], 0.0)
            self.assertAlmostEqual(
                values_by_metric["optic_flow_speed_deg_per_s"],
                29.117647058834,
                places=11,
            )

            summary = result["decoder_summaries"][0]
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["task_context"]["preferred_direction_deg"], 0.0)
            self.assertEqual(summary["task_context"]["declared_speed_deg_per_s"], 45.0)
            self.assertEqual(summary["retinotopic_context"]["center_azimuth_deg"], 5.0)
            self.assertEqual(summary["retinotopic_context"]["center_elevation_deg"], -2.0)
            self.assertAlmostEqual(
                summary["derived_quantities"]["normalized_directional_support"],
                0.64705882353,
                places=11,
            )
            self.assertEqual(
                [item["pairing_key"] for item in summary["diagnostics"]["evidence_rows"]],
                ["off_polarity", "on_polarity"],
            )

    def test_compute_task_decoder_analysis_fails_without_retinotopic_context(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            plan = _build_task_analysis_plan_fixture(metric_ids=["optic_flow_heading_deg"])
            bundle_records = [
                _build_bundle_record(
                    tmp_dir,
                    asset_suffix="preferred",
                    condition_ids=["preferred_direction"],
                    direction_deg=0.0,
                    polarity="positive",
                    trace_values=[2.0, 2.0, 3.0, 7.0, 5.0, 4.0, 2.0],
                    include_patch_center=False,
                ),
                _build_bundle_record(
                    tmp_dir,
                    asset_suffix="null",
                    condition_ids=["null_direction"],
                    direction_deg=180.0,
                    polarity="positive",
                    trace_values=[2.0, 2.0, 2.4, 3.0, 2.6, 2.2, 2.0],
                    include_patch_center=False,
                ),
            ]

            with self.assertRaises(ValueError) as ctx:
                compute_task_decoder_analysis(
                    analysis_plan=plan,
                    bundle_records=bundle_records,
                )

            self.assertIn("retinotopic context", str(ctx.exception))
            self.assertIn("center_azimuth_deg", str(ctx.exception))


def _build_task_analysis_plan_fixture(
    *,
    metric_ids: list[str] | None = None,
) -> dict[str, object]:
    active_metric_ids = metric_ids or [
        "motion_vector_heading_deg",
        "motion_vector_speed_deg_per_s",
        "optic_flow_heading_deg",
        "optic_flow_speed_deg_per_s",
    ]
    window = {
        "window_id": "task_decoder_window",
        "start_ms": 10.0,
        "end_ms": 60.0,
        "description": "Fixture task-decoder window.",
    }
    recipes = [
        {
            "recipe_id": f"{metric_id}__shared_output_mean__task_decoder_window__task_decoder",
            "metric_id": metric_id,
            "window_id": window["window_id"],
            "active_readout_ids": ["shared_output_mean"],
            "condition_ids": [],
            "condition_pair_id": "preferred_vs_null",
        }
        for metric_id in active_metric_ids
    ]
    return {
        "plan_version": "readout_analysis_plan.v1",
        "condition_catalog": [
            {
                "condition_id": "preferred_direction",
                "display_name": "Preferred Direction",
                "parameter_name": "direction_deg",
                "value": 0.0,
            },
            {
                "condition_id": "null_direction",
                "display_name": "Null Direction",
                "parameter_name": "direction_deg",
                "value": 180.0,
            },
            {
                "condition_id": "on_polarity",
                "display_name": "ON Polarity",
                "parameter_name": "polarity",
                "value": "positive",
            },
            {
                "condition_id": "off_polarity",
                "display_name": "OFF Polarity",
                "parameter_name": "polarity",
                "value": "negative",
            },
        ],
        "condition_pair_catalog": [
            {
                "pair_id": "preferred_vs_null",
                "left_condition_id": "preferred_direction",
                "right_condition_id": "null_direction",
            }
        ],
        "analysis_window_catalog": [window],
        "metric_recipe_catalog": recipes,
    }


def _build_bundle_record(
    tmp_dir: Path,
    *,
    asset_suffix: str,
    condition_ids: list[str],
    direction_deg: float,
    polarity: str,
    trace_values: list[float],
    include_patch_center: bool,
) -> dict[str, object]:
    stimulus_metadata = _write_stimulus_fixture(
        tmp_dir,
        asset_suffix=asset_suffix,
        direction_deg=direction_deg,
        polarity=polarity,
        include_patch_center=include_patch_center,
    )
    manifest_path = tmp_dir / "fixture_manifest.yaml"
    if not manifest_path.exists():
        manifest_path.write_text("experiment_id: fixture\n", encoding="utf-8")

    bundle_metadata = build_simulator_result_bundle_metadata(
        manifest_reference=build_simulator_manifest_reference(
            experiment_id="fixture_task_decoder_analysis",
            manifest_path=manifest_path,
            milestone="milestone_12",
        ),
        arm_reference=build_simulator_arm_reference(
            arm_id="baseline_p0_intact",
            model_mode="baseline",
            baseline_family="P0",
        ),
        timebase=FIXTURE_TIMEBASE,
        selected_assets=[
            build_selected_asset_reference(
                asset_role="input_bundle",
                artifact_type="stimulus_bundle",
                path=Path(stimulus_metadata["assets"]["metadata_json"]["path"]),
                contract_version=stimulus_metadata["contract_version"],
                artifact_id=f"stimulus_bundle::{asset_suffix}",
                bundle_id=stimulus_metadata["bundle_id"],
            )
        ],
        readout_catalog=[
            build_simulator_readout_definition(
                readout_id="shared_output_mean",
                scope="circuit_output",
                aggregation="mean_over_root_ids",
                units="activation_au",
                value_semantics="shared_downstream_activation",
                description="Fixture shared output mean.",
            )
        ],
        processed_simulator_results_dir=tmp_dir / "simulator_results",
        seed=11,
    )
    return {
        "bundle_metadata": bundle_metadata,
        "condition_ids": list(condition_ids),
        "shared_readout_payload": {
            "time_ms": FIXTURE_TIME_MS.copy(),
            "readout_ids": ["shared_output_mean"],
            "values": np.asarray(trace_values, dtype=np.float64)[:, None],
        },
    }


def _write_stimulus_fixture(
    tmp_dir: Path,
    *,
    asset_suffix: str,
    direction_deg: float,
    polarity: str,
    include_patch_center: bool,
) -> dict[str, object]:
    parameter_snapshot = {
        "direction_deg": direction_deg,
        "velocity_deg_per_s": 45.0,
        "polarity": polarity,
        "contrast": 0.8,
        "onset_ms": 10.0,
        "offset_ms": 60.0,
        "edge_width_deg": 8.0,
        "phase_offset_deg": 0.0,
    }
    if include_patch_center:
        parameter_snapshot["center_azimuth_deg"] = 5.0
        parameter_snapshot["center_elevation_deg"] = -2.0
    stimulus_metadata = build_stimulus_bundle_metadata(
        stimulus_family="translated_edge",
        stimulus_name=f"fixture_edge_{asset_suffix}",
        parameter_snapshot=parameter_snapshot,
        seed=11,
        temporal_sampling={
            "dt_ms": 10.0,
            "duration_ms": 70.0,
            "frame_count": 7,
        },
        spatial_frame={
            "width_px": 12,
            "height_px": 6,
            "width_deg": 20.0,
            "height_deg": 10.0,
            "x_axis": "azimuth_deg_positive_right",
            "y_axis": "elevation_deg_positive_up",
            "origin": "aperture_center",
            "pixel_origin": "pixel_centers",
        },
        processed_stimulus_dir=tmp_dir / "stimuli",
    )
    write_stimulus_bundle_metadata(stimulus_metadata)
    return stimulus_metadata


if __name__ == "__main__":
    unittest.main()
