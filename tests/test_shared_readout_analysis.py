from __future__ import annotations

import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.readout_analysis_contract import READOUT_ANALYSIS_CONTRACT_VERSION
from flywire_wave.shared_readout_analysis import compute_shared_readout_analysis
from flywire_wave.simulator_result_contract import (
    build_selected_asset_reference,
    build_simulator_arm_reference,
    build_simulator_manifest_reference,
    build_simulator_readout_definition,
    build_simulator_result_bundle_metadata,
)


FIXTURE_TIMEBASE = {
    "time_origin_ms": 0.0,
    "dt_ms": 10.0,
    "duration_ms": 70.0,
    "sample_count": 7,
}
FIXTURE_TIME_MS = np.asarray([0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0], dtype=np.float64)


class SharedReadoutAnalysisTest(unittest.TestCase):
    def test_compute_shared_readout_analysis_emits_latency_and_selectivity_rows(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            plan = _build_analysis_plan_fixture()
            bundle_records = [
                _build_bundle_record(
                    tmp_dir,
                    asset_suffix="preferred_on",
                    condition_ids=["preferred_direction", "on_polarity"],
                    trace_values=[2.0, 2.0, 3.0, 7.0, 5.0, 4.0, 2.0],
                ),
                _build_bundle_record(
                    tmp_dir,
                    asset_suffix="null_on",
                    condition_ids=["null_direction", "on_polarity"],
                    trace_values=[2.0, 2.0, 2.4, 3.0, 2.6, 2.2, 2.0],
                ),
                _build_bundle_record(
                    tmp_dir,
                    asset_suffix="preferred_off",
                    condition_ids=["preferred_direction", "off_polarity"],
                    trace_values=[2.0, 2.0, 2.6, 4.0, 3.2, 2.5, 2.0],
                ),
                _build_bundle_record(
                    tmp_dir,
                    asset_suffix="null_off",
                    condition_ids=["null_direction", "off_polarity"],
                    trace_values=[2.0, 2.0, 2.1, 2.5, 2.3, 2.0, 2.0],
                ),
            ]

            result = compute_shared_readout_analysis(
                analysis_plan=plan,
                bundle_records=bundle_records,
            )

            self.assertEqual(result["contract_version"], READOUT_ANALYSIS_CONTRACT_VERSION)
            self.assertEqual(
                result["supported_metric_ids"],
                [
                    "direction_selectivity_index",
                    "null_direction_suppression_index",
                    "on_off_selectivity_index",
                    "response_latency_to_peak_ms",
                ],
            )
            self.assertEqual(result["skipped_recipes"], [])

            row_counts = Counter(row["metric_id"] for row in result["metric_rows"])
            self.assertEqual(row_counts["response_latency_to_peak_ms"], 4)
            self.assertEqual(row_counts["direction_selectivity_index"], 2)
            self.assertEqual(row_counts["null_direction_suppression_index"], 2)
            self.assertEqual(row_counts["on_off_selectivity_index"], 2)

            preferred_latency_row = next(
                row
                for row in result["metric_rows"]
                if row["metric_id"] == "response_latency_to_peak_ms"
                and row["condition_signature"] == "on_polarity__preferred_direction"
            )
            self.assertEqual(preferred_latency_row["value"], 20.0)
            self.assertEqual(preferred_latency_row["units"], "ms")

            direction_on_row = next(
                row
                for row in result["metric_rows"]
                if row["metric_id"] == "direction_selectivity_index"
                and row["pairing_key"] == "on_polarity"
            )
            self.assertAlmostEqual(direction_on_row["value"], 2.0 / 3.0, places=12)
            self.assertEqual(direction_on_row["units"], "unitless")

            suppression_on_row = next(
                row
                for row in result["metric_rows"]
                if row["metric_id"] == "null_direction_suppression_index"
                and row["pairing_key"] == "on_polarity"
            )
            self.assertAlmostEqual(suppression_on_row["value"], 2.0 / 3.0, places=12)
            self.assertEqual(suppression_on_row["units"], "unitless")

            on_off_preferred_row = next(
                row
                for row in result["metric_rows"]
                if row["metric_id"] == "on_off_selectivity_index"
                and row["pairing_key"] == "preferred_direction"
            )
            self.assertAlmostEqual(on_off_preferred_row["value"], 3.0 / 7.0, places=12)

            preferred_latency_summary = next(
                summary
                for summary in result["metric_summaries"]
                if summary["metric_id"] == "response_latency_to_peak_ms"
                and summary["condition_signature"] == "on_polarity__preferred_direction"
            )
            self.assertEqual(preferred_latency_summary["status"], "ok")
            self.assertEqual(preferred_latency_summary["response_summary"]["baseline_value"], 2.0)
            self.assertEqual(preferred_latency_summary["response_summary"]["peak_value"], 5.0)
            self.assertEqual(preferred_latency_summary["response_summary"]["onset_latency_ms"], 10.0)
            self.assertEqual(
                preferred_latency_summary["response_summary"]["positive_response_values"],
                [0.0, 1.0, 5.0, 3.0, 2.0, 0.0],
            )

            direction_on_summary = next(
                summary
                for summary in result["metric_summaries"]
                if summary["metric_id"] == "direction_selectivity_index"
                and summary["pairing_key"] == "on_polarity"
            )
            self.assertEqual(direction_on_summary["status"], "ok")
            self.assertEqual(
                direction_on_summary["left_response_summary"]["condition_signature"],
                "on_polarity__preferred_direction",
            )
            self.assertEqual(
                direction_on_summary["right_response_summary"]["condition_signature"],
                "null_direction__on_polarity",
            )
            self.assertAlmostEqual(direction_on_summary["value"], 2.0 / 3.0, places=12)

    def test_compute_shared_readout_analysis_marks_flat_latency_as_no_signal(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            plan = _build_analysis_plan_fixture(metric_ids=["response_latency_to_peak_ms"])
            bundle_record = _build_bundle_record(
                tmp_dir,
                asset_suffix="flat_preferred_on",
                condition_ids=["preferred_direction", "on_polarity"],
                trace_values=[3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0],
                include_inline_payload=False,
            )
            _write_payload_to_bundle_artifact(
                bundle_record["bundle_metadata"],
                trace_values=[3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0],
            )

            result = compute_shared_readout_analysis(
                analysis_plan=plan,
                bundle_records=[bundle_record],
            )

            self.assertEqual(result["metric_rows"], [])
            self.assertEqual(len(result["metric_summaries"]), 1)
            summary = result["metric_summaries"][0]
            self.assertEqual(summary["status"], "no_signal")
            self.assertIsNone(summary["value"])
            self.assertEqual(
                summary["response_summary"]["positive_response_values"],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            )

    def test_compute_shared_readout_analysis_marks_ambiguous_latency_onset(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            plan = _build_analysis_plan_fixture(metric_ids=["response_latency_to_peak_ms"])
            bundle_record = _build_bundle_record(
                tmp_dir,
                asset_suffix="ambiguous_preferred_on",
                condition_ids=["preferred_direction", "on_polarity"],
                trace_values=[0.0, 0.0, 0.3, 0.0, 0.8, 2.0, 0.0],
            )

            result = compute_shared_readout_analysis(
                analysis_plan=plan,
                bundle_records=[bundle_record],
            )

            self.assertEqual(result["metric_rows"], [])
            self.assertEqual(len(result["metric_summaries"]), 1)
            summary = result["metric_summaries"][0]
            self.assertEqual(summary["status"], "ambiguous_onset")
            self.assertIsNone(summary["value"])
            self.assertEqual(
                summary["response_summary"]["onset_segment_count_before_peak"],
                2,
            )
            self.assertEqual(summary["response_summary"]["peak_value"], 2.0)


def _build_analysis_plan_fixture(
    *,
    metric_ids: list[str] | None = None,
) -> dict[str, object]:
    active_metric_ids = metric_ids or [
        "response_latency_to_peak_ms",
        "direction_selectivity_index",
        "on_off_selectivity_index",
        "null_direction_suppression_index",
    ]
    window = {
        "window_id": "shared_response_window",
        "start_ms": 10.0,
        "end_ms": 60.0,
        "description": "Fixture shared-response window.",
    }
    recipes = []
    for metric_id in active_metric_ids:
        if metric_id == "response_latency_to_peak_ms":
            recipes.append(
                {
                    "recipe_id": "response_latency_to_peak_ms__shared_output_mean__shared_response_window__conditions",
                    "metric_id": metric_id,
                    "window_id": window["window_id"],
                    "active_readout_ids": ["shared_output_mean"],
                    "condition_ids": [
                        "preferred_direction",
                        "null_direction",
                        "on_polarity",
                        "off_polarity",
                    ],
                    "condition_pair_id": None,
                }
            )
            continue
        condition_pair_id = (
            "on_vs_off"
            if metric_id == "on_off_selectivity_index"
            else "preferred_vs_null"
        )
        recipes.append(
            {
                "recipe_id": (
                    f"{metric_id}__shared_output_mean__shared_response_window__"
                    f"{condition_pair_id}"
                ),
                "metric_id": metric_id,
                "window_id": window["window_id"],
                "active_readout_ids": ["shared_output_mean"],
                "condition_ids": [],
                "condition_pair_id": condition_pair_id,
            }
        )

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
            },
            {
                "pair_id": "on_vs_off",
                "left_condition_id": "on_polarity",
                "right_condition_id": "off_polarity",
            },
        ],
        "analysis_window_catalog": [window],
        "metric_recipe_catalog": recipes,
    }


def _build_bundle_record(
    tmp_dir: Path,
    *,
    asset_suffix: str,
    condition_ids: list[str],
    trace_values: list[float],
    include_inline_payload: bool = True,
) -> dict[str, object]:
    manifest_path = tmp_dir / "fixture_manifest.yaml"
    if not manifest_path.exists():
        manifest_path.write_text("experiment_id: fixture\n", encoding="utf-8")

    metadata = build_simulator_result_bundle_metadata(
        manifest_reference=build_simulator_manifest_reference(
            experiment_id="fixture_shared_readout_analysis",
            manifest_path=manifest_path,
            milestone="milestone_1",
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
                path=tmp_dir / f"{asset_suffix}_stimulus_bundle.json",
                contract_version="stimulus_bundle.v1",
                artifact_id="stimulus_bundle",
                bundle_id=f"stimulus_bundle::{asset_suffix}",
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
    record: dict[str, object] = {
        "bundle_metadata": metadata,
        "condition_ids": list(condition_ids),
    }
    if include_inline_payload:
        record["shared_readout_payload"] = {
            "time_ms": FIXTURE_TIME_MS,
            "readout_ids": ("shared_output_mean",),
            "values": np.asarray(trace_values, dtype=np.float64).reshape(-1, 1),
        }
    return record


def _write_payload_to_bundle_artifact(
    bundle_metadata: dict[str, object],
    *,
    trace_values: list[float],
) -> None:
    readout_path = Path(
        str(bundle_metadata["artifacts"]["readout_traces"]["path"])  # type: ignore[index]
    )
    readout_path.parent.mkdir(parents=True, exist_ok=True)
    with readout_path.open("wb") as handle:
        np.savez(
            handle,
            time_ms=FIXTURE_TIME_MS,
            readout_ids=np.asarray(["shared_output_mean"]),
            values=np.asarray(trace_values, dtype=np.float64).reshape(-1, 1),
        )


if __name__ == "__main__":
    unittest.main()
