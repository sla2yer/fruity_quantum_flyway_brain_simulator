from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.showcase_session_contract import (
    ANALYSIS_UI_PAYLOAD_ROLE_ID,
    APPROVED_HIGHLIGHT_PRESET_ID,
    APPROVED_WAVE_HIGHLIGHT_STEP_ID,
    BASELINE_WAVE_COMPARISON_STEP_ID,
    CAMERA_TRANSITION_CUE_KIND_ID,
    DASHBOARD_SESSION_METADATA_ROLE_ID,
    DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
    DASHBOARD_SESSION_STATE_ROLE_ID,
    EVIDENCE_CAPTION_ANNOTATION_ID,
    FALLBACK_NOTICE_ANNOTATION_ID,
    FALLBACK_REDIRECT_CUE_KIND_ID,
    HERO_FRAME_EXPORT_TARGET_ROLE_ID,
    HIGHLIGHT_FALLBACK_PRESET_ID,
    METADATA_JSON_KEY,
    NARRATIVE_PRESET_CATALOG_ROLE_ID,
    PAUSE_SCRIPT_CONTROL_ID,
    REVIEW_MANIFEST_EXPORT_TARGET_ROLE_ID,
    SCIENTIFIC_GUARDRAIL_ANNOTATION_ID,
    SHOWCASE_EXPORT_MANIFEST_ROLE_ID,
    SHOWCASE_PRESENTATION_STATE_ROLE_ID,
    SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID,
    SHOWCASE_SCRIPT_PAYLOAD_ROLE_ID,
    SHOWCASE_SESSION_CONTRACT_VERSION,
    SHOWCASE_SESSION_DESIGN_NOTE,
    SHOWCASE_SESSION_METADATA_ROLE_ID,
    SHOWCASE_STATE_EXPORT_TARGET_ROLE_ID,
    STORYBOARD_EXPORT_TARGET_ROLE_ID,
    SUITE_COMPARISON_PLOT_ROLE_ID,
    SUITE_SUMMARY_TABLE_ROLE_ID,
    SUPPORTED_SHOWCASE_STEP_IDS,
    VALIDATION_FINDINGS_ROLE_ID,
    VALIDATION_REVIEW_HANDOFF_ROLE_ID,
    VALIDATION_SUMMARY_ROLE_ID,
    build_showcase_evidence_reference,
    build_showcase_narrative_annotation,
    build_showcase_saved_preset,
    build_showcase_session_artifact_reference,
    build_showcase_session_contract_metadata,
    build_showcase_session_metadata,
    build_showcase_step,
    discover_showcase_artifact_hooks,
    discover_showcase_export_target_roles,
    discover_showcase_preset_definitions,
    discover_showcase_saved_presets,
    discover_showcase_session_artifact_references,
    discover_showcase_session_bundle_paths,
    discover_showcase_step_definitions,
    discover_showcase_steps,
    get_showcase_step_definition,
    load_showcase_session_contract_metadata,
    load_showcase_session_metadata,
    write_showcase_session_contract_metadata,
    write_showcase_session_metadata,
)


def _humanize_identifier(identifier: str) -> str:
    return identifier.replace("_", " ").title()


def _mutate_contract_fixture(metadata: dict[str, object], *, reverse: bool) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    for field_name, id_key in (
        ("step_catalog", "step_id"),
        ("preset_catalog", "preset_id"),
        ("cue_kind_catalog", "cue_kind_id"),
        ("annotation_catalog", "annotation_id"),
        ("evidence_role_catalog", "evidence_role_id"),
        ("operator_control_catalog", "operator_control_id"),
        ("export_target_role_catalog", "export_target_role_id"),
        ("presentation_status_catalog", "status_id"),
        ("artifact_hook_catalog", "artifact_role_id"),
        ("discovery_hook_catalog", "hook_id"),
    ):
        entries: list[dict[str, object]] = []
        for item in metadata[field_name]:
            mutated = copy.deepcopy(item)
            mutated[id_key] = _humanize_identifier(str(mutated[id_key]))
            for sequence_key in (
                "required_annotation_ids",
                "required_evidence_role_ids",
                "required_operator_control_ids",
                "default_export_target_role_ids",
                "supported_step_ids",
                "artifact_role_ids",
                "required_evidence_role_ids",
            ):
                if sequence_key in mutated:
                    mutated[sequence_key] = [
                        _humanize_identifier(str(value)) for value in mutated[sequence_key]
                    ]
            if "default_preset_id" in mutated:
                mutated["default_preset_id"] = _humanize_identifier(str(mutated["default_preset_id"]))
            if "default_cue_kind_id" in mutated:
                mutated["default_cue_kind_id"] = _humanize_identifier(str(mutated["default_cue_kind_id"]))
            if "fallback_preset_id" in mutated and mutated["fallback_preset_id"] is not None:
                mutated["fallback_preset_id"] = _humanize_identifier(str(mutated["fallback_preset_id"]))
            if "source_kind" in mutated:
                mutated["source_kind"] = _humanize_identifier(str(mutated["source_kind"]))
            if "artifact_scope" in mutated:
                mutated["artifact_scope"] = _humanize_identifier(str(mutated["artifact_scope"]))
            if "target_kind" in mutated:
                mutated["target_kind"] = _humanize_identifier(str(mutated["target_kind"]))
            entries.append(mutated)
        if reverse:
            entries.reverse()
        result[field_name] = entries
    return {
        "step_definitions": result["step_catalog"],
        "preset_definitions": result["preset_catalog"],
        "cue_kind_definitions": result["cue_kind_catalog"],
        "annotation_definitions": result["annotation_catalog"],
        "evidence_role_definitions": result["evidence_role_catalog"],
        "operator_control_definitions": result["operator_control_catalog"],
        "export_target_role_definitions": result["export_target_role_catalog"],
        "presentation_status_definitions": result["presentation_status_catalog"],
        "artifact_hook_definitions": result["artifact_hook_catalog"],
        "discovery_hook_definitions": result["discovery_hook_catalog"],
    }


class ShowcaseSessionContractTest(unittest.TestCase):
    def test_default_contract_serializes_deterministically_and_exposes_taxonomy(self) -> None:
        default_metadata = build_showcase_session_contract_metadata()
        mutated_metadata = build_showcase_session_contract_metadata(
            **_mutate_contract_fixture(default_metadata, reverse=True)
        )

        self.assertEqual(default_metadata, mutated_metadata)
        self.assertEqual(default_metadata["contract_version"], SHOWCASE_SESSION_CONTRACT_VERSION)
        self.assertEqual(default_metadata["design_note"], SHOWCASE_SESSION_DESIGN_NOTE)
        self.assertEqual(
            [item["step_id"] for item in discover_showcase_step_definitions(default_metadata)],
            list(SUPPORTED_SHOWCASE_STEP_IDS),
        )
        self.assertEqual(
            [
                item["preset_id"]
                for item in discover_showcase_preset_definitions(
                    default_metadata,
                    step_id="Approved Wave Highlight",
                )
            ],
            [APPROVED_HIGHLIGHT_PRESET_ID, HIGHLIGHT_FALLBACK_PRESET_ID],
        )
        self.assertEqual(
            get_showcase_step_definition(
                "Approved Wave Highlight",
                record=default_metadata,
            )["fallback_preset_id"],
            HIGHLIGHT_FALLBACK_PRESET_ID,
        )
        self.assertEqual(
            [
                item["artifact_role_id"]
                for item in discover_showcase_artifact_hooks(
                    default_metadata,
                    source_kind="Validation Bundle",
                )
            ],
            [
                "validation_bundle_metadata",
                VALIDATION_SUMMARY_ROLE_ID,
                VALIDATION_FINDINGS_ROLE_ID,
                VALIDATION_REVIEW_HANDOFF_ROLE_ID,
            ],
        )
        self.assertEqual(
            [
                item["export_target_role_id"]
                for item in discover_showcase_export_target_roles(
                    default_metadata,
                    target_kind="Still Image Export",
                )
            ],
            [HERO_FRAME_EXPORT_TARGET_ROLE_ID],
        )

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            metadata_path = Path(tmp_dir_str) / "showcase_contract.json"
            written_path = write_showcase_session_contract_metadata(
                default_metadata,
                metadata_path,
            )
            self.assertEqual(
                load_showcase_session_contract_metadata(written_path),
                default_metadata,
            )

    def test_fixture_showcase_metadata_serializes_deterministically_and_discovers_steps(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            temp_root = Path(tmp_dir_str)
            results_dir = temp_root / "results"

            external_refs_a = [
                build_showcase_session_artifact_reference(
                    artifact_role_id=DASHBOARD_SESSION_METADATA_ROLE_ID,
                    source_kind="dashboard_session_package",
                    path=temp_root / "dashboard/dashboard_session.json",
                    contract_version="dashboard_session.v1",
                    bundle_id="dashboard_session.v1:demo:" + ("0" * 64),
                    artifact_id="metadata_json",
                    artifact_scope="dashboard_context",
                ),
                build_showcase_session_artifact_reference(
                    artifact_role_id=DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
                    source_kind="dashboard_session_package",
                    path=temp_root / "dashboard/dashboard_session_payload.json",
                    contract_version="dashboard_session.v1",
                    bundle_id="dashboard_session.v1:demo:" + ("0" * 64),
                    artifact_id="session_payload",
                    artifact_scope="dashboard_context",
                ),
                build_showcase_session_artifact_reference(
                    artifact_role_id=DASHBOARD_SESSION_STATE_ROLE_ID,
                    source_kind="dashboard_session_package",
                    path=temp_root / "dashboard/session_state.json",
                    contract_version="dashboard_session.v1",
                    bundle_id="dashboard_session.v1:demo:" + ("0" * 64),
                    artifact_id="session_state",
                    artifact_scope="dashboard_context",
                ),
                build_showcase_session_artifact_reference(
                    artifact_role_id=SUITE_SUMMARY_TABLE_ROLE_ID,
                    source_kind="experiment_suite_package",
                    path=temp_root / "suite/summary_table.csv",
                    contract_version="experiment_suite.v1",
                    bundle_id="experiment_suite.v1:demo:" + ("1" * 64),
                    artifact_id="summary_table",
                    artifact_scope="suite_rollup",
                ),
                build_showcase_session_artifact_reference(
                    artifact_role_id=SUITE_COMPARISON_PLOT_ROLE_ID,
                    source_kind="experiment_suite_package",
                    path=temp_root / "suite/comparison_plot.svg",
                    contract_version="experiment_suite.v1",
                    bundle_id="experiment_suite.v1:demo:" + ("1" * 64),
                    artifact_id="comparison_plot",
                    artifact_scope="suite_rollup",
                ),
                build_showcase_session_artifact_reference(
                    artifact_role_id=ANALYSIS_UI_PAYLOAD_ROLE_ID,
                    source_kind="experiment_analysis_bundle",
                    path=temp_root / "analysis/analysis_ui_payload.json",
                    contract_version="experiment_analysis_bundle.v1",
                    bundle_id="experiment_analysis_bundle.v1:demo:" + ("2" * 64),
                    artifact_id="analysis_ui_payload",
                    artifact_scope="analysis_context",
                ),
                build_showcase_session_artifact_reference(
                    artifact_role_id=VALIDATION_SUMMARY_ROLE_ID,
                    source_kind="validation_bundle",
                    path=temp_root / "validation/validation_summary.json",
                    contract_version="validation_ladder.v1",
                    bundle_id="validation_ladder.v1:demo:" + ("3" * 64),
                    artifact_id="validation_summary",
                    artifact_scope="validation_guardrail",
                ),
                build_showcase_session_artifact_reference(
                    artifact_role_id=VALIDATION_FINDINGS_ROLE_ID,
                    source_kind="validation_bundle",
                    path=temp_root / "validation/validator_findings.json",
                    contract_version="validation_ladder.v1",
                    bundle_id="validation_ladder.v1:demo:" + ("3" * 64),
                    artifact_id="validator_findings",
                    artifact_scope="validation_guardrail",
                ),
                build_showcase_session_artifact_reference(
                    artifact_role_id=VALIDATION_REVIEW_HANDOFF_ROLE_ID,
                    source_kind="validation_bundle",
                    path=temp_root / "validation/review_handoff.json",
                    contract_version="validation_ladder.v1",
                    bundle_id="validation_ladder.v1:demo:" + ("3" * 64),
                    artifact_id="review_handoff",
                    artifact_scope="validation_guardrail",
                ),
            ]

            saved_presets_a = [
                build_showcase_saved_preset(preset_id="scene_context", step_id="scene_selection", presentation_state_patch={"camera": "wide"}),
                build_showcase_saved_preset(preset_id="retinal_input_focus", step_id="fly_view_input", presentation_state_patch={"time_ms": 10.0}),
                build_showcase_saved_preset(preset_id="subset_context", step_id="active_visual_subset", presentation_state_patch={"pane": "circuit"}),
                build_showcase_saved_preset(preset_id="propagation_replay", step_id="activity_propagation", presentation_state_patch={"playback": "paused"}),
                build_showcase_saved_preset(preset_id="paired_comparison", step_id="baseline_wave_comparison", presentation_state_patch={"comparison": "paired"}),
                build_showcase_saved_preset(preset_id="approved_highlight", step_id="approved_wave_highlight", presentation_state_patch={"highlight": "approved"}),
                build_showcase_saved_preset(preset_id="highlight_fallback", step_id="approved_wave_highlight", presentation_status="fallback", presentation_state_patch={"highlight": "fallback"}),
                build_showcase_saved_preset(preset_id="analysis_summary", step_id="summary_analysis", presentation_state_patch={"pane": "analysis"}),
            ]

            steps_a = [
                build_showcase_step(
                    step_id="scene_selection",
                    preset_id="scene_context",
                    cue_kind_id=CAMERA_TRANSITION_CUE_KIND_ID,
                    presentation_status="ready",
                    narrative_annotations=[
                        build_showcase_narrative_annotation(annotation_id="story_context", text="Open on the chosen scene."),
                        build_showcase_narrative_annotation(annotation_id="operator_prompt", text="Start the scripted sequence."),
                    ],
                    evidence_references=[
                        build_showcase_evidence_reference(evidence_role_id="scene_context_evidence", artifact_role_id=DASHBOARD_SESSION_METADATA_ROLE_ID, citation_label="Dashboard metadata"),
                    ],
                    operator_control_ids=["start_script", "load_preset"],
                    export_target_role_ids=["hero_frame_png"],
                ),
                build_showcase_step(
                    step_id="fly_view_input",
                    preset_id="retinal_input_focus",
                    cue_kind_id="playback_scrub",
                    presentation_status="ready",
                    narrative_annotations=[
                        build_showcase_narrative_annotation(annotation_id="input_sampling", text="Show the fly-view input."),
                        build_showcase_narrative_annotation(annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID, text="Cite the packaged replay surface."),
                    ],
                    evidence_references=[
                        build_showcase_evidence_reference(evidence_role_id="input_context_evidence", artifact_role_id=DASHBOARD_SESSION_PAYLOAD_ROLE_ID, citation_label="Dashboard payload"),
                    ],
                    operator_control_ids=["pause_script", "scrub_time"],
                    export_target_role_ids=["hero_frame_png"],
                ),
                build_showcase_step(
                    step_id="active_visual_subset",
                    preset_id="subset_context",
                    cue_kind_id="overlay_reveal",
                    presentation_status="ready",
                    narrative_annotations=[
                        build_showcase_narrative_annotation(annotation_id="story_context", text="Show the active circuit."),
                        build_showcase_narrative_annotation(annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID, text="Subset context is dashboard-owned."),
                    ],
                    evidence_references=[
                        build_showcase_evidence_reference(evidence_role_id="subset_context_evidence", artifact_role_id=DASHBOARD_SESSION_STATE_ROLE_ID, citation_label="Session state"),
                    ],
                    operator_control_ids=["load_preset", "next_step"],
                    export_target_role_ids=["hero_frame_png"],
                ),
                build_showcase_step(
                    step_id="activity_propagation",
                    preset_id="propagation_replay",
                    cue_kind_id="playback_scrub",
                    presentation_status="ready",
                    narrative_annotations=[
                        build_showcase_narrative_annotation(annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID, text="Propagation uses shared replay."),
                        build_showcase_narrative_annotation(annotation_id="fairness_boundary", text="Still stay on the fair comparison surface."),
                    ],
                    evidence_references=[
                        build_showcase_evidence_reference(evidence_role_id="shared_comparison_evidence", artifact_role_id=ANALYSIS_UI_PAYLOAD_ROLE_ID, citation_label="Analysis payload"),
                    ],
                    operator_control_ids=["pause_script", "scrub_time"],
                    export_target_role_ids=["scripted_clip_frames"],
                ),
                build_showcase_step(
                    step_id="baseline_wave_comparison",
                    preset_id="paired_comparison",
                    cue_kind_id="comparison_swap",
                    presentation_status="ready",
                    narrative_annotations=[
                        build_showcase_narrative_annotation(annotation_id="fairness_boundary", text="This is the fair baseline-vs-wave surface."),
                        build_showcase_narrative_annotation(annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID, text="Use paired comparison plus suite rollup context."),
                    ],
                    evidence_references=[
                        build_showcase_evidence_reference(evidence_role_id="shared_comparison_evidence", artifact_role_id=ANALYSIS_UI_PAYLOAD_ROLE_ID, citation_label="Analysis comparison"),
                        build_showcase_evidence_reference(evidence_role_id="suite_rollup_evidence", artifact_role_id=SUITE_SUMMARY_TABLE_ROLE_ID, citation_label="Suite rollup"),
                    ],
                    operator_control_ids=["toggle_comparison", "pause_script"],
                    export_target_role_ids=["hero_frame_png", STORYBOARD_EXPORT_TARGET_ROLE_ID],
                ),
                build_showcase_step(
                    step_id=APPROVED_WAVE_HIGHLIGHT_STEP_ID,
                    preset_id=HIGHLIGHT_FALLBACK_PRESET_ID,
                    cue_kind_id=FALLBACK_REDIRECT_CUE_KIND_ID,
                    presentation_status="fallback",
                    narrative_annotations=[
                        build_showcase_narrative_annotation(annotation_id=SCIENTIFIC_GUARDRAIL_ANNOTATION_ID, text="The requested highlight is not approved for display."),
                        build_showcase_narrative_annotation(annotation_id=FALLBACK_NOTICE_ANNOTATION_ID, text="Fall back to the paired comparison story."),
                        build_showcase_narrative_annotation(annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID, text="Use validation as the guardrail."),
                    ],
                    evidence_references=[
                        build_showcase_evidence_reference(evidence_role_id="approved_wave_highlight_evidence", artifact_role_id=ANALYSIS_UI_PAYLOAD_ROLE_ID, citation_label="Wave highlight candidate"),
                        build_showcase_evidence_reference(evidence_role_id="validation_guardrail_evidence", artifact_role_id=VALIDATION_FINDINGS_ROLE_ID, citation_label="Validation findings"),
                    ],
                    operator_control_ids=["load_preset", PAUSE_SCRIPT_CONTROL_ID],
                    export_target_role_ids=[HERO_FRAME_EXPORT_TARGET_ROLE_ID, REVIEW_MANIFEST_EXPORT_TARGET_ROLE_ID],
                    fallback_preset_id=HIGHLIGHT_FALLBACK_PRESET_ID,
                ),
                build_showcase_step(
                    step_id="summary_analysis",
                    preset_id="analysis_summary",
                    cue_kind_id="export_capture",
                    presentation_status="ready",
                    narrative_annotations=[
                        build_showcase_narrative_annotation(annotation_id="story_context", text="Close on packaged analysis."),
                        build_showcase_narrative_annotation(annotation_id=EVIDENCE_CAPTION_ANNOTATION_ID, text="Anchor to suite and analysis outputs."),
                    ],
                    evidence_references=[
                        build_showcase_evidence_reference(evidence_role_id="summary_analysis_evidence", artifact_role_id=ANALYSIS_UI_PAYLOAD_ROLE_ID, citation_label="Summary payload"),
                        build_showcase_evidence_reference(evidence_role_id="suite_rollup_evidence", artifact_role_id=SUITE_COMPARISON_PLOT_ROLE_ID, citation_label="Suite plot"),
                    ],
                    operator_control_ids=["trigger_export", "previous_step"],
                    export_target_role_ids=[SHOWCASE_STATE_EXPORT_TARGET_ROLE_ID, REVIEW_MANIFEST_EXPORT_TARGET_ROLE_ID],
                ),
            ]

            external_refs_b = []
            for item in reversed(external_refs_a):
                mutated = copy.deepcopy(item)
                mutated["artifact_role_id"] = _humanize_identifier(str(mutated["artifact_role_id"]))
                mutated["source_kind"] = _humanize_identifier(str(mutated["source_kind"]))
                mutated["artifact_id"] = _humanize_identifier(str(mutated["artifact_id"]))
                if mutated["artifact_scope"] is not None:
                    mutated["artifact_scope"] = _humanize_identifier(str(mutated["artifact_scope"]))
                external_refs_b.append(mutated)

            saved_presets_b = []
            for item in reversed(saved_presets_a):
                mutated = copy.deepcopy(item)
                mutated["preset_id"] = _humanize_identifier(str(mutated["preset_id"]))
                mutated["step_id"] = _humanize_identifier(str(mutated["step_id"]))
                mutated["presentation_status"] = _humanize_identifier(str(mutated["presentation_status"]))
                mutated["source_artifact_role_id"] = _humanize_identifier(str(mutated["source_artifact_role_id"]))
                saved_presets_b.append(mutated)

            steps_b = []
            for item in reversed(steps_a):
                mutated = copy.deepcopy(item)
                mutated["step_id"] = _humanize_identifier(str(mutated["step_id"]))
                mutated["preset_id"] = _humanize_identifier(str(mutated["preset_id"]))
                mutated["cue_kind_id"] = _humanize_identifier(str(mutated["cue_kind_id"]))
                mutated["presentation_status"] = _humanize_identifier(str(mutated["presentation_status"]))
                if mutated["fallback_preset_id"] is not None:
                    mutated["fallback_preset_id"] = _humanize_identifier(str(mutated["fallback_preset_id"]))
                for annotation in mutated["narrative_annotations"]:
                    annotation["annotation_id"] = _humanize_identifier(str(annotation["annotation_id"]))
                    annotation["linked_evidence_role_ids"] = [
                        _humanize_identifier(str(value))
                        for value in annotation["linked_evidence_role_ids"]
                    ]
                for evidence in mutated["evidence_references"]:
                    evidence["evidence_role_id"] = _humanize_identifier(str(evidence["evidence_role_id"]))
                    evidence["artifact_role_id"] = _humanize_identifier(str(evidence["artifact_role_id"]))
                mutated["operator_control_ids"] = [
                    _humanize_identifier(str(value)) for value in mutated["operator_control_ids"]
                ]
                mutated["export_target_role_ids"] = [
                    _humanize_identifier(str(value)) for value in mutated["export_target_role_ids"]
                ]
                steps_b.append(mutated)

            metadata_a = build_showcase_session_metadata(
                experiment_id="milestone_16_demo",
                showcase_id="milestone_16_story",
                display_name="Milestone 16 Story",
                artifact_references=external_refs_a,
                saved_presets=saved_presets_a,
                showcase_steps=steps_a,
                processed_simulator_results_dir=results_dir,
                presentation_status="fallback",
                enabled_export_target_role_ids=[
                    SHOWCASE_STATE_EXPORT_TARGET_ROLE_ID,
                    HERO_FRAME_EXPORT_TARGET_ROLE_ID,
                    STORYBOARD_EXPORT_TARGET_ROLE_ID,
                    REVIEW_MANIFEST_EXPORT_TARGET_ROLE_ID,
                ],
                default_export_target_role_id="Showcase State Json",
            )
            metadata_b = build_showcase_session_metadata(
                experiment_id="Milestone 16 Demo",
                showcase_id="Milestone 16 Story",
                display_name="Milestone 16 Story",
                artifact_references=external_refs_b,
                saved_presets=saved_presets_b,
                showcase_steps=steps_b,
                processed_simulator_results_dir=results_dir,
                presentation_status="Fallback",
                enabled_export_target_role_ids=[
                    "Review Manifest Json",
                    "Showcase State Json",
                    "Hero Frame Png",
                    "Storyboard Json",
                ],
                default_export_target_role_id=SHOWCASE_STATE_EXPORT_TARGET_ROLE_ID,
            )

            self.assertEqual(metadata_a, metadata_b)
            self.assertEqual(
                [item["step_id"] for item in discover_showcase_steps(metadata_a)],
                list(SUPPORTED_SHOWCASE_STEP_IDS),
            )
            self.assertEqual(
                [item["step_id"] for item in discover_showcase_steps(metadata_a, presentation_status="Fallback")],
                [APPROVED_WAVE_HIGHLIGHT_STEP_ID],
            )
            self.assertEqual(
                [
                    item["preset_id"]
                    for item in discover_showcase_saved_presets(
                        metadata_a,
                        step_id="Approved Wave Highlight",
                    )
                ],
                [APPROVED_HIGHLIGHT_PRESET_ID, HIGHLIGHT_FALLBACK_PRESET_ID],
            )
            self.assertEqual(
                [
                    item["artifact_role_id"]
                    for item in discover_showcase_session_artifact_references(
                        metadata_a,
                        source_kind="Showcase Session Package",
                    )
                ],
                [
                    NARRATIVE_PRESET_CATALOG_ROLE_ID,
                    SHOWCASE_SESSION_METADATA_ROLE_ID,
                    SHOWCASE_SCRIPT_PAYLOAD_ROLE_ID,
                    SHOWCASE_PRESENTATION_STATE_ROLE_ID,
                    SHOWCASE_EXPORT_MANIFEST_ROLE_ID,
                ],
            )

            discovered_paths = discover_showcase_session_bundle_paths(metadata_a)
            self.assertEqual(discovered_paths[METADATA_JSON_KEY].name, "showcase_session.json")
            self.assertEqual(
                discovered_paths[SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID].name,
                "showcase_script.json",
            )

            written_path = write_showcase_session_metadata(metadata_a)
            self.assertEqual(load_showcase_session_metadata(written_path), metadata_a)
