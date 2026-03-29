from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.dashboard_session_contract import (
    ANALYSIS_PANE_ID,
    BASELINE_BUNDLE_METADATA_ROLE_ID,
    BASELINE_UI_PAYLOAD_ROLE_ID,
    DASHBOARD_APP_SHELL_ROLE_ID,
    DASHBOARD_SESSION_CONTRACT_VERSION,
    DASHBOARD_SESSION_DESIGN_NOTE,
    DASHBOARD_SESSION_METADATA_ROLE_ID,
    DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
    DASHBOARD_SESSION_STATE_ROLE_ID,
    METADATA_JSON_KEY,
    METRICS_EXPORT_TARGET_ID,
    PANE_SNAPSHOT_EXPORT_TARGET_ID,
    PHASE_MAP_REFERENCE_OVERLAY_ID,
    SESSION_STATE_ARTIFACT_ID,
    SESSION_STATE_EXPORT_TARGET_ID,
    SHARED_COMPARISON_OVERLAY_CATEGORY,
    SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    TIME_SERIES_PANE_ID,
    VALIDATION_BUNDLE_METADATA_ROLE_ID,
    VALIDATION_OFFLINE_REPORT_ROLE_ID,
    VALIDATION_REVIEW_HANDOFF_ROLE_ID,
    VALIDATION_SUMMARY_ROLE_ID,
    WAVE_BUNDLE_METADATA_ROLE_ID,
    WAVE_UI_PAYLOAD_ROLE_ID,
    WAVE_ONLY_DIAGNOSTIC_OVERLAY_CATEGORY,
    WAVE_PATCH_ACTIVITY_OVERLAY_ID,
    build_dashboard_global_interaction_state,
    build_dashboard_selected_arm_pair_reference,
    build_dashboard_session_artifact_reference,
    build_dashboard_session_contract_metadata,
    build_dashboard_session_metadata,
    build_dashboard_time_cursor,
    discover_dashboard_artifact_hooks,
    discover_dashboard_export_targets,
    discover_dashboard_overlays,
    discover_dashboard_panes,
    discover_dashboard_session_artifact_references,
    discover_dashboard_session_bundle_paths,
    get_dashboard_overlay_definition,
    get_dashboard_pane_definition,
    load_dashboard_session_contract_metadata,
    load_dashboard_session_metadata,
    write_dashboard_session_contract_metadata,
    write_dashboard_session_metadata,
)
from flywire_wave.simulator_result_contract import build_simulator_manifest_reference


class DashboardSessionContractTest(unittest.TestCase):
    def test_default_contract_exposes_milestone14_taxonomy(self) -> None:
        metadata = build_dashboard_session_contract_metadata()

        self.assertEqual(metadata["contract_version"], DASHBOARD_SESSION_CONTRACT_VERSION)
        self.assertEqual(metadata["design_note"], DASHBOARD_SESSION_DESIGN_NOTE)
        self.assertEqual(
            [item["pane_id"] for item in discover_dashboard_panes(metadata)],
            [
                "scene",
                "circuit",
                "morphology",
                "time_series",
                "analysis",
            ],
        )
        self.assertEqual(
            [
                item["pane_id"]
                for item in discover_dashboard_panes(
                    metadata,
                    overlay_category="Wave Only Diagnostic",
                )
            ],
            [
                "morphology",
                "time_series",
                "analysis",
            ],
        )
        self.assertEqual(
            [
                item["overlay_id"]
                for item in discover_dashboard_overlays(
                    metadata,
                    pane_id="Analysis",
                    overlay_category="Wave Only Diagnostic",
                )
            ],
            [
                WAVE_PATCH_ACTIVITY_OVERLAY_ID,
                PHASE_MAP_REFERENCE_OVERLAY_ID,
            ],
        )
        self.assertEqual(
            get_dashboard_pane_definition("Time Series", record=metadata)["pane_id"],
            TIME_SERIES_PANE_ID,
        )
        self.assertEqual(
            get_dashboard_overlay_definition(
                "Shared Readout Activity",
                record=metadata,
            )["overlay_category"],
            SHARED_COMPARISON_OVERLAY_CATEGORY,
        )
        self.assertEqual(
            [
                item["artifact_role_id"]
                for item in discover_dashboard_artifact_hooks(
                    metadata,
                    source_kind="Validation Bundle",
                )
            ],
            [
                VALIDATION_BUNDLE_METADATA_ROLE_ID,
                VALIDATION_SUMMARY_ROLE_ID,
                VALIDATION_REVIEW_HANDOFF_ROLE_ID,
                VALIDATION_OFFLINE_REPORT_ROLE_ID,
            ],
        )
        self.assertEqual(
            [
                item["export_target_id"]
                for item in discover_dashboard_export_targets(
                    metadata,
                    pane_id=ANALYSIS_PANE_ID,
                )
            ],
            [
                SESSION_STATE_EXPORT_TARGET_ID,
                PANE_SNAPSHOT_EXPORT_TARGET_ID,
                METRICS_EXPORT_TARGET_ID,
            ],
        )

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            metadata_path = Path(tmp_dir_str) / "dashboard_contract.json"
            written_path = write_dashboard_session_contract_metadata(metadata, metadata_path)
            self.assertEqual(load_dashboard_session_contract_metadata(written_path), metadata)

    def test_fixture_session_metadata_serializes_deterministically_and_discovers_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            temp_root = Path(tmp_dir_str)
            simulator_results_dir = temp_root / "simulator_results"
            manifest_reference = build_simulator_manifest_reference(
                experiment_id="milestone_1_demo_motion_patch",
                manifest_id="milestone_1_demo_motion_patch",
                manifest_path=ROOT / "manifests/examples/milestone_1_demo.yaml",
                milestone="milestone_14",
                brief_version="milestone_1_brief.v1",
                hypothesis_version="milestone_1_hypothesis.v1",
            )

            external_artifact_refs = [
                build_dashboard_session_artifact_reference(
                    artifact_role_id="Baseline Bundle Metadata",
                    source_kind="Simulator Result Bundle",
                    path=temp_root / "bundles/baseline/simulator_result_bundle.json",
                    contract_version="simulator_result_bundle.v1",
                    bundle_id=(
                        "simulator_result_bundle.v1:"
                        "milestone_1_demo_motion_patch:baseline_p0_intact:"
                        + ("0" * 64)
                    ),
                    artifact_id="metadata_json",
                    artifact_scope="contract_metadata",
                ),
                build_dashboard_session_artifact_reference(
                    artifact_role_id="Baseline UI Comparison Payload",
                    source_kind="Simulator Result Bundle",
                    path=temp_root / "bundles/baseline/ui_comparison_payload.json",
                    contract_version="simulator_result_bundle.v1",
                    bundle_id=(
                        "simulator_result_bundle.v1:"
                        "milestone_1_demo_motion_patch:baseline_p0_intact:"
                        + ("0" * 64)
                    ),
                    artifact_id="ui_comparison_payload",
                    artifact_scope="shared_comparison",
                ),
                build_dashboard_session_artifact_reference(
                    artifact_role_id="Wave Bundle Metadata",
                    source_kind="Simulator Result Bundle",
                    path=temp_root / "bundles/wave/simulator_result_bundle.json",
                    contract_version="simulator_result_bundle.v1",
                    bundle_id=(
                        "simulator_result_bundle.v1:"
                        "milestone_1_demo_motion_patch:surface_wave_intact:"
                        + ("1" * 64)
                    ),
                    artifact_id="metadata_json",
                    artifact_scope="contract_metadata",
                ),
                build_dashboard_session_artifact_reference(
                    artifact_role_id="Wave UI Comparison Payload",
                    source_kind="Simulator Result Bundle",
                    path=temp_root / "bundles/wave/ui_comparison_payload.json",
                    contract_version="simulator_result_bundle.v1",
                    bundle_id=(
                        "simulator_result_bundle.v1:"
                        "milestone_1_demo_motion_patch:surface_wave_intact:"
                        + ("1" * 64)
                    ),
                    artifact_id="ui_comparison_payload",
                    artifact_scope="shared_comparison",
                ),
                build_dashboard_session_artifact_reference(
                    artifact_role_id="Analysis Bundle Metadata",
                    source_kind="Experiment Analysis Bundle",
                    path=temp_root / "analysis/experiment_analysis_bundle.json",
                    contract_version="experiment_analysis_bundle.v1",
                    bundle_id=(
                        "experiment_analysis_bundle.v1:"
                        "milestone_1_demo_motion_patch:"
                        + ("2" * 64)
                    ),
                    artifact_id="metadata_json",
                    artifact_scope="contract_metadata",
                ),
                build_dashboard_session_artifact_reference(
                    artifact_role_id="Analysis UI Payload",
                    source_kind="Experiment Analysis Bundle",
                    path=temp_root / "analysis/analysis_ui_payload.json",
                    contract_version="experiment_analysis_bundle.v1",
                    bundle_id=(
                        "experiment_analysis_bundle.v1:"
                        "milestone_1_demo_motion_patch:"
                        + ("2" * 64)
                    ),
                    artifact_id="analysis_ui_payload",
                    artifact_scope="ui_handoff",
                ),
                build_dashboard_session_artifact_reference(
                    artifact_role_id="Validation Bundle Metadata",
                    source_kind="Validation Bundle",
                    path=temp_root / "validation/validation_bundle.json",
                    contract_version="validation_ladder.v1",
                    bundle_id=(
                        "validation_ladder.v1:"
                        "milestone_1_demo_motion_patch:"
                        + ("3" * 64)
                    ),
                    artifact_id="metadata_json",
                    artifact_scope="contract_metadata",
                ),
                build_dashboard_session_artifact_reference(
                    artifact_role_id="Validation Summary",
                    source_kind="Validation Bundle",
                    path=temp_root / "validation/validation_summary.json",
                    contract_version="validation_ladder.v1",
                    bundle_id=(
                        "validation_ladder.v1:"
                        "milestone_1_demo_motion_patch:"
                        + ("3" * 64)
                    ),
                    artifact_id="validation_summary",
                    artifact_scope="machine_summary",
                ),
                build_dashboard_session_artifact_reference(
                    artifact_role_id="Validation Review Handoff",
                    source_kind="Validation Bundle",
                    path=temp_root / "validation/review_handoff.json",
                    contract_version="validation_ladder.v1",
                    bundle_id=(
                        "validation_ladder.v1:"
                        "milestone_1_demo_motion_patch:"
                        + ("3" * 64)
                    ),
                    artifact_id="review_handoff",
                    artifact_scope="review_handoff",
                ),
            ]

            global_interaction_state_a = build_dashboard_global_interaction_state(
                selected_arm_pair=build_dashboard_selected_arm_pair_reference(
                    baseline_arm_id="baseline_p0_intact",
                    wave_arm_id="surface_wave_intact",
                    active_arm_id="surface_wave_intact",
                ),
                selected_neuron_id="720575940123456789",
                selected_readout_id="shared_output_mean",
                active_overlay_id=SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                comparison_mode="paired_baseline_vs_wave",
                time_cursor=build_dashboard_time_cursor(
                    time_ms=12.5,
                    sample_index=25,
                    playback_state="paused",
                ),
            )
            global_interaction_state_b = {
                "selected_arm_pair": {
                    "baseline_arm_id": "Baseline P0 Intact",
                    "wave_arm_id": "Surface Wave Intact",
                    "active_arm_id": "Surface Wave Intact",
                },
                "selected_neuron_id": "720575940123456789",
                "selected_readout_id": "Shared Output Mean",
                "active_overlay_id": "Shared Readout Activity",
                "comparison_mode": "Paired Baseline Vs Wave",
                "time_cursor": {
                    "time_ms": 12.5,
                    "sample_index": 25,
                    "playback_state": "Paused",
                },
            }

            metadata_a = build_dashboard_session_metadata(
                manifest_reference=manifest_reference,
                global_interaction_state=global_interaction_state_a,
                artifact_references=external_artifact_refs,
                processed_simulator_results_dir=simulator_results_dir,
                enabled_export_target_ids=[
                    SESSION_STATE_EXPORT_TARGET_ID,
                    PANE_SNAPSHOT_EXPORT_TARGET_ID,
                    METRICS_EXPORT_TARGET_ID,
                ],
                default_export_target_id="Session State JSON",
            )
            metadata_b = build_dashboard_session_metadata(
                manifest_reference=manifest_reference,
                global_interaction_state=global_interaction_state_b,
                artifact_references=list(reversed(external_artifact_refs)),
                processed_simulator_results_dir=simulator_results_dir,
                enabled_export_target_ids=[
                    "Metrics JSON",
                    "Session State JSON",
                    "Pane Snapshot PNG",
                ],
                default_export_target_id=SESSION_STATE_EXPORT_TARGET_ID,
            )

            self.assertEqual(metadata_a, metadata_b)
            self.assertEqual(metadata_a["contract_version"], DASHBOARD_SESSION_CONTRACT_VERSION)
            self.assertEqual(
                metadata_a["global_interaction_state"]["active_overlay_id"],
                SHARED_READOUT_ACTIVITY_OVERLAY_ID,
            )
            self.assertEqual(
                metadata_a["enabled_export_target_ids"],
                [
                    SESSION_STATE_EXPORT_TARGET_ID,
                    PANE_SNAPSHOT_EXPORT_TARGET_ID,
                    METRICS_EXPORT_TARGET_ID,
                ],
            )
            self.assertEqual(
                [
                    item["artifact_role_id"]
                    for item in discover_dashboard_session_artifact_references(
                        metadata_a,
                        source_kind="Simulator Result Bundle",
                    )
                ],
                [
                    BASELINE_BUNDLE_METADATA_ROLE_ID,
                    BASELINE_UI_PAYLOAD_ROLE_ID,
                    WAVE_BUNDLE_METADATA_ROLE_ID,
                    WAVE_UI_PAYLOAD_ROLE_ID,
                ],
            )
            self.assertEqual(
                [
                    item["artifact_role_id"]
                    for item in discover_dashboard_session_artifact_references(
                        metadata_a,
                        source_kind="Dashboard Session Package",
                    )
                ],
                [
                    DASHBOARD_SESSION_METADATA_ROLE_ID,
                    DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
                    DASHBOARD_SESSION_STATE_ROLE_ID,
                    DASHBOARD_APP_SHELL_ROLE_ID,
                ],
            )
            discovered_bundle_paths = discover_dashboard_session_bundle_paths(metadata_a)
            self.assertEqual(discovered_bundle_paths[METADATA_JSON_KEY].name, "dashboard_session.json")
            self.assertEqual(discovered_bundle_paths[SESSION_STATE_ARTIFACT_ID].name, "session_state.json")

            written_path = write_dashboard_session_metadata(metadata_a)
            self.assertEqual(written_path, discovered_bundle_paths[METADATA_JSON_KEY])
            self.assertEqual(load_dashboard_session_metadata(written_path), metadata_a)
