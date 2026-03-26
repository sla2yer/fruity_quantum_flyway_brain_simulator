from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.readout_analysis_contract import (
    ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
    EXPERIMENT_BUNDLE_SET_ARTIFACT_CLASS,
    LOCKED_READOUT_STOP_POINT,
    MIXED_SCOPE_LABELED_FAIRNESS_MODE,
    MOTION_DECODER_SUMMARY_OUTPUT_ID,
    MILESTONE_1_SHARED_EFFECTS_TASK_FAMILY,
    NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID,
    PER_EXPERIMENT_MANIFEST_SCOPE,
    PER_SHARED_READOUT_CONDITION_WINDOW_SCOPE,
    PER_TASK_DECODER_WINDOW_SCOPE,
    PER_WAVE_ROOT_WINDOW_SCOPE,
    READOUT_ANALYSIS_CONTRACT_VERSION,
    READOUT_ANALYSIS_DESIGN_NOTE,
    SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
    SHARED_READOUT_METRIC_CLASS,
    SHARED_READOUT_ONLY_FAIRNESS_MODE,
    SHARED_READOUT_TRACES_ARTIFACT_CLASS,
    SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
    STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
    SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
    SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
    TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
    UI_PAYLOAD_OUTPUT_KIND,
    WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID,
    WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE,
    WAVE_ONLY_DIAGNOSTIC_CLASS,
    build_experiment_comparison_output_definition,
    build_readout_analysis_contract_metadata,
    build_readout_analysis_metric_definition,
    build_readout_analysis_null_test_hook,
    build_readout_analysis_task_family_definition,
    discover_experiment_comparison_output_definitions,
    discover_readout_analysis_metric_definitions,
    discover_readout_analysis_null_test_hooks,
    discover_readout_analysis_task_families,
    get_experiment_comparison_output_definition,
    get_readout_analysis_metric_definition,
    load_readout_analysis_contract_metadata,
    write_readout_analysis_contract_metadata,
)


class ReadoutAnalysisContractTest(unittest.TestCase):
    def test_default_contract_exposes_milestone12_taxonomy(self) -> None:
        metadata = build_readout_analysis_contract_metadata()

        self.assertEqual(metadata["contract_version"], READOUT_ANALYSIS_CONTRACT_VERSION)
        self.assertEqual(metadata["design_note"], READOUT_ANALYSIS_DESIGN_NOTE)
        self.assertEqual(metadata["locked_readout_stop_point"], LOCKED_READOUT_STOP_POINT)
        self.assertIn("simulator_result_bundle.v1", metadata["required_upstream_contracts"])
        self.assertIn("surface_wave_model.v1", metadata["required_upstream_contracts"])
        self.assertEqual(
            [item["metric_id"] for item in discover_readout_analysis_metric_definitions(metadata, metric_class=SHARED_READOUT_METRIC_CLASS)],
            [
                "direction_selectivity_index",
                "null_direction_suppression_index",
                "on_off_selectivity_index",
                "response_latency_to_peak_ms",
            ],
        )
        self.assertEqual(
            [item["metric_id"] for item in discover_readout_analysis_metric_definitions(metadata, metric_class=WAVE_ONLY_DIAGNOSTIC_CLASS)],
            [
                "patch_activation_entropy_bits",
                "phase_gradient_dispersion_rad_per_patch",
                "phase_gradient_mean_rad_per_patch",
                "synchrony_coherence_index",
                "wavefront_curvature_inv_patch",
                "wavefront_speed_patch_per_ms",
            ],
        )
        self.assertEqual(
            get_readout_analysis_metric_definition("response_latency_to_peak_ms", record=metadata)["units"],
            "ms",
        )
        self.assertEqual(
            get_experiment_comparison_output_definition(
                WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID,
                record=metadata,
            )["fairness_mode"],
            WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE,
        )
        self.assertEqual(
            get_experiment_comparison_output_definition(
                NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID,
                record=metadata,
            )["fairness_mode"],
            SHARED_READOUT_ONLY_FAIRNESS_MODE,
        )
        self.assertEqual(
            discover_readout_analysis_task_families(metadata, fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE)[0]["task_family_id"],
            MILESTONE_1_SHARED_EFFECTS_TASK_FAMILY,
        )
        self.assertEqual(
            [item["null_test_id"] for item in discover_readout_analysis_null_test_hooks(metadata, task_family_id=MILESTONE_1_SHARED_EFFECTS_TASK_FAMILY)],
            [
                "geometry_shuffle_collapse",
                "polarity_label_swap",
                "seed_stability",
                "stronger_baseline_survival",
            ],
        )
        self.assertIn(MOTION_DECODER_SUMMARY_OUTPUT_ID, metadata["ui_facing_output_ids"])
        self.assertIn(WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID, metadata["ui_facing_output_ids"])

    def test_fixture_contract_serializes_deterministically_and_discovers_definitions(self) -> None:
        normalized_shared_metric = build_readout_analysis_metric_definition(
            metric_id="Fixture Shared Latency MS",
            metric_class="Shared Readout Metric",
            task_family_id="Fixture Shared Effects",
            display_name="Fixture Shared Latency",
            description="Fixture latency metric on the shared readout surface.",
            units="ms",
            scope_rule=PER_SHARED_READOUT_CONDITION_WINDOW_SCOPE,
            required_source_artifact_classes=[
                STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
                SHARED_READOUT_TRACES_ARTIFACT_CLASS,
                SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
            ],
            fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            fairness_note="Shared-only fixture latency metric.",
            interpretation="Fixture latency interpretation.",
        )
        self.assertEqual(normalized_shared_metric["metric_id"], "fixture_shared_latency_ms")
        self.assertEqual(normalized_shared_metric["metric_class"], SHARED_READOUT_METRIC_CLASS)
        self.assertEqual(
            normalized_shared_metric["required_source_artifact_classes"],
            [
                SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
                SHARED_READOUT_TRACES_ARTIFACT_CLASS,
                SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
            ],
        )

        metric_definitions_a = [
            {
                "metric_id": "Fixture Shared Latency MS",
                "metric_class": "Shared Readout Metric",
                "task_family_id": "Fixture Shared Effects",
                "display_name": "Fixture Shared Latency",
                "description": "Fixture latency metric on the shared readout surface.",
                "units": "ms",
                "scope_rule": PER_SHARED_READOUT_CONDITION_WINDOW_SCOPE,
                "required_source_artifact_classes": [
                    STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
                    SHARED_READOUT_TRACES_ARTIFACT_CLASS,
                    SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
                    SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                ],
                "fairness_mode": SHARED_READOUT_ONLY_FAIRNESS_MODE,
                "fairness_note": "Shared-only fixture latency metric.",
                "interpretation": "Fixture latency interpretation.",
            },
            {
                "metric_id": "Fixture Motion Heading Deg",
                "metric_class": "Derived Task Metric",
                "task_family_id": "Fixture Motion Decoder",
                "display_name": "Fixture Motion Heading",
                "description": "Fixture heading decoder metric.",
                "units": "deg",
                "scope_rule": PER_TASK_DECODER_WINDOW_SCOPE,
                "required_source_artifact_classes": [
                    SHARED_READOUT_CATALOG_ARTIFACT_CLASS,
                    SHARED_READOUT_TRACES_ARTIFACT_CLASS,
                    SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                    STIMULUS_CONDITION_METADATA_ARTIFACT_CLASS,
                    TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
                ],
                "fairness_mode": SHARED_READOUT_ONLY_FAIRNESS_MODE,
                "fairness_note": "Shared-only fixture decoder metric.",
                "interpretation": "Fixture heading interpretation.",
            },
            {
                "metric_id": "Fixture Wave Entropy Bits",
                "metric_class": "Wave Only Diagnostic",
                "task_family_id": "Fixture Wave Diagnostics",
                "display_name": "Fixture Wave Entropy",
                "description": "Fixture wave diagnostic metric.",
                "units": "bits",
                "scope_rule": PER_WAVE_ROOT_WINDOW_SCOPE,
                "required_source_artifact_classes": [
                    SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
                    SIMULATOR_BUNDLE_METADATA_ARTIFACT_CLASS,
                    SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
                ],
                "fairness_mode": WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE,
                "fairness_note": "Wave-only fixture diagnostic.",
                "interpretation": "Fixture wave interpretation.",
            },
        ]
        metric_definitions_b = list(reversed(metric_definitions_a))

        output_definitions_a = [
            build_experiment_comparison_output_definition(
                output_id="Fixture Comparison Panel",
                task_family_id="Fixture Outputs",
                output_kind="comparison_summary",
                display_name="Fixture Comparison Panel",
                description="Fixture shared-comparison panel.",
                scope_rule=PER_EXPERIMENT_MANIFEST_SCOPE,
                required_metric_ids=[
                    "fixture_motion_heading_deg",
                    "fixture_shared_latency_ms",
                ],
                required_source_artifact_classes=[
                    ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
                    EXPERIMENT_BUNDLE_SET_ARTIFACT_CLASS,
                ],
                fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
                fairness_note="Fixture comparison output stays on the shared metric surface.",
            ),
            build_experiment_comparison_output_definition(
                output_id="Fixture UI Payload",
                task_family_id="Fixture Outputs",
                output_kind=UI_PAYLOAD_OUTPUT_KIND,
                display_name="Fixture UI Payload",
                description="Fixture mixed-scope UI payload.",
                scope_rule=PER_EXPERIMENT_MANIFEST_SCOPE,
                required_metric_ids=[
                    "fixture_wave_entropy_bits",
                    "fixture_shared_latency_ms",
                ],
                required_source_artifact_classes=[
                    ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
                    SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
                ],
                fairness_mode=MIXED_SCOPE_LABELED_FAIRNESS_MODE,
                fairness_note="Fixture UI payload keeps shared and wave-only sections labeled.",
            ),
        ]
        output_definitions_b = list(reversed(output_definitions_a))

        task_families_a = [
            build_readout_analysis_task_family_definition(
                task_family_id="Fixture Shared Effects",
                display_name="Fixture Shared Effects",
                description="Fixture shared-effect family.",
                metric_ids=["fixture_shared_latency_ms"],
                output_ids=[],
                null_test_hook_ids=["fixture_seed_stability"],
                fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            ),
            build_readout_analysis_task_family_definition(
                task_family_id="Fixture Motion Decoder",
                display_name="Fixture Motion Decoder",
                description="Fixture motion-decoder family.",
                metric_ids=["fixture_motion_heading_deg"],
                output_ids=[],
                null_test_hook_ids=["fixture_direction_label_swap"],
                fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
            ),
            build_readout_analysis_task_family_definition(
                task_family_id="Fixture Wave Diagnostics",
                display_name="Fixture Wave Diagnostics",
                description="Fixture wave family.",
                metric_ids=["fixture_wave_entropy_bits"],
                output_ids=[],
                null_test_hook_ids=["fixture_wave_guard"],
                fairness_mode=WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE,
            ),
            build_readout_analysis_task_family_definition(
                task_family_id="Fixture Outputs",
                display_name="Fixture Outputs",
                description="Fixture experiment outputs.",
                metric_ids=[],
                output_ids=["fixture_comparison_panel", "fixture_ui_payload"],
                null_test_hook_ids=[],
                fairness_mode=MIXED_SCOPE_LABELED_FAIRNESS_MODE,
            ),
        ]
        task_families_b = list(reversed(task_families_a))

        null_test_hooks_a = [
            build_readout_analysis_null_test_hook(
                null_test_id="Fixture Seed Stability",
                task_family_id="Fixture Shared Effects",
                display_name="Fixture Seed Stability",
                description="Fixture seed stability hook.",
                required_metric_ids=["fixture_shared_latency_ms"],
                required_source_artifact_classes=[
                    ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
                    EXPERIMENT_BUNDLE_SET_ARTIFACT_CLASS,
                ],
                fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
                pass_criterion="Fixture shared latency stays stable across seeds.",
            ),
            build_readout_analysis_null_test_hook(
                null_test_id="Fixture Direction Label Swap",
                task_family_id="Fixture Motion Decoder",
                display_name="Fixture Direction Label Swap",
                description="Fixture direction label swap hook.",
                required_metric_ids=["fixture_motion_heading_deg"],
                required_source_artifact_classes=[
                    ANALYSIS_METRIC_ROWS_ARTIFACT_CLASS,
                    TASK_CONTEXT_METADATA_ARTIFACT_CLASS,
                ],
                fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE,
                pass_criterion="Fixture decoder should move under label swaps.",
            ),
            build_readout_analysis_null_test_hook(
                null_test_id="Fixture Wave Guard",
                task_family_id="Fixture Wave Diagnostics",
                display_name="Fixture Wave Guard",
                description="Fixture wave artifact guard.",
                required_metric_ids=["fixture_wave_entropy_bits"],
                required_source_artifact_classes=[
                    SURFACE_WAVE_PATCH_TRACES_ARTIFACT_CLASS,
                    SURFACE_WAVE_SUMMARY_ARTIFACT_CLASS,
                ],
                fairness_mode=WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE,
                pass_criterion="Fixture wave diagnostics require wave artifacts.",
            ),
        ]
        null_test_hooks_b = list(reversed(null_test_hooks_a))

        metadata_a = build_readout_analysis_contract_metadata(
            metric_definitions=metric_definitions_a,
            output_definitions=output_definitions_a,
            task_families=task_families_a,
            null_test_hooks=null_test_hooks_a,
        )
        metadata_b = build_readout_analysis_contract_metadata(
            metric_definitions=metric_definitions_b,
            output_definitions=output_definitions_b,
            task_families=task_families_b,
            null_test_hooks=null_test_hooks_b,
        )

        self.assertEqual(metadata_a, metadata_b)
        self.assertEqual(
            [item["metric_id"] for item in metadata_a["metric_catalog"]],
            [
                "fixture_motion_heading_deg",
                "fixture_shared_latency_ms",
                "fixture_wave_entropy_bits",
            ],
        )
        self.assertEqual(
            [item["output_id"] for item in metadata_a["output_catalog"]],
            ["fixture_comparison_panel", "fixture_ui_payload"],
        )
        self.assertEqual(
            metadata_a["ui_facing_output_ids"],
            ["fixture_comparison_panel", "fixture_ui_payload"],
        )
        self.assertEqual(
            [item["task_family_id"] for item in discover_readout_analysis_task_families(metadata_a)],
            [
                "fixture_motion_decoder",
                "fixture_outputs",
                "fixture_shared_effects",
                "fixture_wave_diagnostics",
            ],
        )
        self.assertEqual(
            [item["metric_id"] for item in discover_readout_analysis_metric_definitions({"readout_analysis_contract": metadata_a}, metric_class=WAVE_ONLY_DIAGNOSTIC_CLASS)],
            ["fixture_wave_entropy_bits"],
        )
        self.assertEqual(
            [item["output_id"] for item in discover_experiment_comparison_output_definitions(metadata_a, fairness_mode=SHARED_READOUT_ONLY_FAIRNESS_MODE)],
            ["fixture_comparison_panel"],
        )
        self.assertEqual(
            [item["null_test_id"] for item in discover_readout_analysis_null_test_hooks(metadata_a, fairness_mode=WAVE_EXTENSION_ALLOWED_FAIRNESS_MODE)],
            ["fixture_wave_guard"],
        )
        self.assertEqual(
            get_readout_analysis_metric_definition("Fixture Motion Heading Deg", record=metadata_a)["task_family_id"],
            "fixture_motion_decoder",
        )
        self.assertEqual(
            get_experiment_comparison_output_definition("Fixture UI Payload", record=metadata_a)["fairness_mode"],
            MIXED_SCOPE_LABELED_FAIRNESS_MODE,
        )

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            metadata_path = Path(tmp_dir_str) / "readout_analysis_contract.json"
            written_path = write_readout_analysis_contract_metadata(metadata_a, metadata_path)
            loaded = load_readout_analysis_contract_metadata(written_path)

            self.assertEqual(loaded, metadata_a)
            serialized = json.dumps(metadata_a, indent=2, sort_keys=True)
            self.assertEqual(written_path.read_text(encoding="utf-8"), serialized)


if __name__ == "__main__":
    unittest.main()
