from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.simulator_result_contract import (
    ASSET_STATUS_MISSING,
    ASSET_STATUS_READY,
    METADATA_JSON_KEY,
    METRICS_TABLE_KEY,
    MODEL_DIAGNOSTIC_SCOPE,
    P0_BASELINE_FAMILY,
    READOUT_TRACES_KEY,
    SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
    SIMULATOR_RESULT_BUNDLE_DESIGN_NOTE,
    STATE_SUMMARY_KEY,
    build_selected_asset_reference,
    build_simulator_arm_reference,
    build_simulator_contract_manifest_metadata,
    build_simulator_extension_artifact_record,
    build_simulator_manifest_reference,
    build_simulator_readout_definition,
    build_simulator_result_bundle_metadata,
    build_simulator_result_bundle_paths,
    discover_simulator_extension_artifacts,
    discover_simulator_result_bundle_paths,
    load_simulator_result_bundle_metadata,
    resolve_simulator_result_bundle_metadata_path,
    write_simulator_result_bundle_metadata,
)


class SimulatorResultContractTest(unittest.TestCase):
    def test_bundle_paths_are_deterministic(self) -> None:
        run_spec_hash = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        bundle_paths = build_simulator_result_bundle_paths(
            experiment_id="Milestone_1_Demo_Motion_Patch",
            arm_id="Baseline_P0_Intact",
            run_spec_hash=run_spec_hash,
            processed_simulator_results_dir=ROOT / "data" / "processed" / "simulator_results",
        )

        expected_bundle_directory = (
            ROOT
            / "data"
            / "processed"
            / "simulator_results"
            / "bundles"
            / "milestone_1_demo_motion_patch"
            / "baseline_p0_intact"
            / run_spec_hash
        ).resolve()
        self.assertEqual(bundle_paths.bundle_directory, expected_bundle_directory)
        self.assertEqual(
            bundle_paths.metadata_json_path,
            expected_bundle_directory / "simulator_result_bundle.json",
        )
        self.assertEqual(
            bundle_paths.state_summary_path,
            expected_bundle_directory / "state_summary.json",
        )
        self.assertEqual(
            bundle_paths.readout_traces_path,
            expected_bundle_directory / "readout_traces.npz",
        )
        self.assertEqual(bundle_paths.metrics_table_path, expected_bundle_directory / "metrics.csv")
        self.assertEqual(
            bundle_paths.bundle_id,
            (
                "simulator_result_bundle.v1:"
                "milestone_1_demo_motion_patch:baseline_p0_intact:"
                f"{run_spec_hash}"
            ),
        )

    def test_fixture_baseline_metadata_serializes_deterministically_and_discovers_bundle(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            simulator_results_dir = Path(tmp_dir_str) / "simulator_results"
            manifest_reference = build_simulator_manifest_reference(
                experiment_id="milestone_1_demo_motion_patch",
                manifest_id="milestone_1_demo_motion_patch",
                manifest_path=ROOT / "manifests/examples/milestone_1_demo.yaml",
                milestone="milestone_1",
                brief_version="milestone_1_brief.v1",
                hypothesis_version="milestone_1_hypothesis.v1",
            )
            arm_reference = build_simulator_arm_reference(
                arm_id="baseline_p0_intact",
                model_mode="baseline",
                baseline_family=P0_BASELINE_FAMILY,
                comparison_tags=["intact", "canonical_baseline"],
            )
            timebase = {
                "dt_ms": 0.5,
                "duration_ms": 10.0,
                "sample_count": 20,
                "time_origin_ms": 0.0,
            }
            selected_assets_a = [
                build_selected_asset_reference(
                    asset_role="retinal_bundle",
                    artifact_type="retinal_input_bundle",
                    path=simulator_results_dir / "fixtures/retinal_input_bundle.json",
                    contract_version="retinal_input_bundle.v1",
                    artifact_id="fixture_retinal_bundle",
                    bundle_id="retinal_input_bundle.v1:fixture_retinal_bundle",
                ),
                build_selected_asset_reference(
                    asset_role="geometry_manifest",
                    artifact_type="geometry_bundle_manifest",
                    path=simulator_results_dir / "fixtures/geometry_manifest.json",
                    contract_version="geometry_bundle.v1",
                    artifact_id="fixture_geometry_manifest",
                    bundle_id=None,
                ),
                build_selected_asset_reference(
                    asset_role="stimulus_bundle",
                    artifact_type="stimulus_bundle",
                    path=simulator_results_dir / "fixtures/stimulus_bundle.json",
                    contract_version="stimulus_bundle.v1",
                    artifact_id="fixture_stimulus_bundle",
                    bundle_id="stimulus_bundle.v1:translated_edge:simple_translated_edge:fixture",
                ),
                build_selected_asset_reference(
                    asset_role="coupling_manifest",
                    artifact_type="coupling_manifest",
                    path=simulator_results_dir / "fixtures/coupling_manifest.json",
                    contract_version="coupling_bundle.v1",
                    artifact_id="fixture_coupling_manifest",
                    bundle_id=None,
                ),
            ]
            readout_catalog_a = [
                build_simulator_readout_definition(
                    readout_id="shared_output_mean",
                    scope="circuit_output",
                    aggregation="mean_over_root_ids",
                    units="activation_au",
                    value_semantics="shared_downstream_activation",
                    description="Shared downstream output mean for matched baseline-versus-wave comparison.",
                ),
                build_simulator_readout_definition(
                    readout_id="direction_selectivity_index",
                    scope="comparison_panel",
                    aggregation="identity",
                    units="unitless",
                    value_semantics="direction_selectivity_index",
                    description="Shared direction selectivity trace used for the challenge-baseline comparison.",
                ),
            ]

            seed_metadata = build_simulator_result_bundle_metadata(
                manifest_reference=manifest_reference,
                arm_reference=arm_reference,
                timebase=timebase,
                seed=17,
                selected_assets=selected_assets_a,
                readout_catalog=readout_catalog_a,
                processed_simulator_results_dir=simulator_results_dir,
                state_summary_status=ASSET_STATUS_READY,
                readout_traces_status=ASSET_STATUS_READY,
                metrics_table_status=ASSET_STATUS_READY,
            )
            bundle_paths = build_simulator_result_bundle_paths(
                experiment_id=manifest_reference["experiment_id"],
                arm_id=arm_reference["arm_id"],
                run_spec_hash=seed_metadata["run_spec_hash"],
                processed_simulator_results_dir=simulator_results_dir,
            )
            diagnostic_artifact = build_simulator_extension_artifact_record(
                bundle_paths=bundle_paths,
                artifact_id="solver_diagnostics",
                file_name="solver_diagnostics.json",
                format="json_solver_diagnostics.v1",
                status=ASSET_STATUS_MISSING,
                artifact_scope=MODEL_DIAGNOSTIC_SCOPE,
                description="Optional baseline-side solver diagnostics that are not comparison-ready outputs.",
            )

            metadata_a = build_simulator_result_bundle_metadata(
                manifest_reference=manifest_reference,
                arm_reference=arm_reference,
                timebase=timebase,
                seed=17,
                selected_assets=selected_assets_a,
                readout_catalog=readout_catalog_a,
                processed_simulator_results_dir=simulator_results_dir,
                state_summary_status=ASSET_STATUS_READY,
                readout_traces_status=ASSET_STATUS_READY,
                metrics_table_status=ASSET_STATUS_READY,
                model_artifacts=[diagnostic_artifact],
            )
            metadata_b = build_simulator_result_bundle_metadata(
                manifest_reference=manifest_reference,
                arm_reference=arm_reference,
                timebase=timebase,
                seed=17,
                selected_assets=list(reversed(selected_assets_a)),
                readout_catalog=list(reversed(readout_catalog_a)),
                processed_simulator_results_dir=simulator_results_dir,
                state_summary_status=ASSET_STATUS_READY,
                readout_traces_status=ASSET_STATUS_READY,
                metrics_table_status=ASSET_STATUS_READY,
                model_artifacts=[diagnostic_artifact],
            )
            contract_manifest_metadata = build_simulator_contract_manifest_metadata(
                processed_simulator_results_dir=simulator_results_dir
            )

            self.assertEqual(metadata_a, metadata_b)
            self.assertEqual(
                metadata_a["contract_version"],
                SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
            )
            self.assertEqual(metadata_a["design_note"], SIMULATOR_RESULT_BUNDLE_DESIGN_NOTE)
            self.assertEqual(metadata_a["arm_reference"]["model_mode"], "baseline")
            self.assertEqual(metadata_a["arm_reference"]["baseline_family"], P0_BASELINE_FAMILY)
            self.assertEqual(metadata_a["determinism"]["seed"], 17)
            self.assertEqual(metadata_a["timebase"]["sample_count"], 20)
            self.assertEqual(metadata_a["timebase"]["duration_ms"], 10.0)
            self.assertEqual(
                [item["asset_role"] for item in metadata_a["selected_assets"]],
                [
                    "coupling_manifest",
                    "geometry_manifest",
                    "retinal_bundle",
                    "stimulus_bundle",
                ],
            )
            self.assertEqual(
                [item["readout_id"] for item in metadata_a["readout_catalog"]],
                [
                    "direction_selectivity_index",
                    "shared_output_mean",
                ],
            )
            self.assertEqual(
                metadata_a["shared_payload_contract"][STATE_SUMMARY_KEY]["format"],
                "json_state_summary_rows.v1",
            )
            self.assertEqual(
                metadata_a["shared_payload_contract"][READOUT_TRACES_KEY]["required_arrays"],
                ["time_ms", "readout_ids", "values"],
            )
            self.assertEqual(
                metadata_a["shared_payload_contract"][METRICS_TABLE_KEY]["required_columns"],
                [
                    "metric_id",
                    "readout_id",
                    "scope",
                    "window_id",
                    "statistic",
                    "value",
                    "units",
                ],
            )
            self.assertEqual(
                metadata_a["artifacts"][METADATA_JSON_KEY]["path"],
                str(bundle_paths.metadata_json_path),
            )
            self.assertEqual(
                metadata_a["artifacts"][STATE_SUMMARY_KEY]["path"],
                str(bundle_paths.state_summary_path),
            )
            self.assertEqual(
                metadata_a["artifacts"][READOUT_TRACES_KEY]["path"],
                str(bundle_paths.readout_traces_path),
            )
            self.assertEqual(
                metadata_a["artifacts"][METRICS_TABLE_KEY]["path"],
                str(bundle_paths.metrics_table_path),
            )
            self.assertEqual(contract_manifest_metadata["version"], SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION)
            self.assertEqual(contract_manifest_metadata["design_note"], SIMULATOR_RESULT_BUNDLE_DESIGN_NOTE)
            self.assertEqual(
                contract_manifest_metadata["shared_artifact_file_names"][METRICS_TABLE_KEY],
                "metrics.csv",
            )
            self.assertEqual(
                Path(contract_manifest_metadata["bundle_root_directory"]),
                (simulator_results_dir / "bundles").resolve(),
            )

            metadata_path = write_simulator_result_bundle_metadata(metadata_a)
            loaded_metadata = load_simulator_result_bundle_metadata(metadata_path)
            discovered_paths = discover_simulator_result_bundle_paths(metadata_a)
            nested_discovered_paths = discover_simulator_result_bundle_paths(
                {"simulator_result_bundle": metadata_a}
            )
            discovered_model_artifacts = discover_simulator_extension_artifacts(metadata_a)

            self.assertEqual(loaded_metadata, metadata_a)
            self.assertEqual(discovered_paths[METADATA_JSON_KEY], metadata_path.resolve())
            self.assertEqual(
                discovered_paths[STATE_SUMMARY_KEY],
                Path(metadata_a["artifacts"][STATE_SUMMARY_KEY]["path"]).resolve(),
            )
            self.assertEqual(
                discovered_paths[READOUT_TRACES_KEY],
                Path(metadata_a["artifacts"][READOUT_TRACES_KEY]["path"]).resolve(),
            )
            self.assertEqual(
                discovered_paths[METRICS_TABLE_KEY],
                Path(metadata_a["artifacts"][METRICS_TABLE_KEY]["path"]).resolve(),
            )
            self.assertEqual(nested_discovered_paths, discovered_paths)
            self.assertEqual(
                discovered_model_artifacts,
                [
                    {
                        "artifact_id": "solver_diagnostics",
                        "path": bundle_paths.extension_root_directory / "solver_diagnostics.json",
                        "format": "json_solver_diagnostics.v1",
                        "artifact_scope": MODEL_DIAGNOSTIC_SCOPE,
                    }
                ],
            )

            resolved_metadata_path = resolve_simulator_result_bundle_metadata_path(
                manifest_reference=manifest_reference,
                arm_reference=arm_reference,
                timebase=timebase,
                seed=17,
                selected_assets=list(reversed(selected_assets_a)),
                readout_catalog=list(reversed(readout_catalog_a)),
                processed_simulator_results_dir=simulator_results_dir,
            )
            self.assertEqual(resolved_metadata_path, metadata_path.resolve())

            serialized = json.dumps(metadata_a, indent=2, sort_keys=True)
            self.assertEqual(metadata_path.read_text(encoding="utf-8"), serialized)


if __name__ == "__main__":
    unittest.main()
