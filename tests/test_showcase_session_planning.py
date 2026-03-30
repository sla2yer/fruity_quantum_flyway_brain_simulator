from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

from flywire_wave.dashboard_session_contract import (
    SHARED_READOUT_ACTIVITY_OVERLAY_ID,
    load_dashboard_session_metadata,
)
from flywire_wave.dashboard_session_planning import (
    package_dashboard_session,
    resolve_dashboard_session_plan,
)
from flywire_wave.experiment_suite_packaging import (
    load_experiment_suite_package_metadata,
    load_experiment_suite_result_index,
)
from flywire_wave.experiment_suite_reporting import (
    generate_experiment_suite_review_report,
)
from flywire_wave.io_utils import write_json
from flywire_wave.showcase_session_contract import (
    ACTIVE_VISUAL_SUBSET_STEP_ID,
    ACTIVITY_PROPAGATION_STEP_ID,
    ANALYSIS_UI_PAYLOAD_ROLE_ID,
    ANALYSIS_SUMMARY_PRESET_ID,
    APPROVED_HIGHLIGHT_PRESET_ID,
    APPROVED_WAVE_HIGHLIGHT_STEP_ID,
    BASELINE_WAVE_COMPARISON_STEP_ID,
    DASHBOARD_SESSION_METADATA_ROLE_ID,
    FLY_VIEW_INPUT_STEP_ID,
    HIGHLIGHT_FALLBACK_PRESET_ID,
    METADATA_JSON_KEY,
    PAIRED_COMPARISON_PRESET_ID,
    SCENE_SELECTION_STEP_ID,
    SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID,
    SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID,
    SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID,
    SUITE_SUMMARY_TABLE_ROLE_ID,
    SUMMARY_ANALYSIS_STEP_ID,
    VALIDATION_REVIEW_HANDOFF_ROLE_ID,
    discover_showcase_session_bundle_paths,
    load_showcase_session_metadata,
)
from flywire_wave.showcase_session_planning import (
    package_showcase_session,
    resolve_showcase_session_plan,
    SHOWCASE_FIXTURE_MODE_REHEARSAL,
)
from flywire_wave.validation_contract import (
    REVIEW_HANDOFF_ARTIFACT_ID,
    discover_validation_bundle_paths,
)

try:
    from tests.test_dashboard_session_planning import (
        DEFAULT_BASELINE_ARM_ID,
        DEFAULT_CONDITION_IDS,
        DEFAULT_SEED,
        DEFAULT_WAVE_ARM_ID,
        EXPERIMENT_ID,
        _materialize_dashboard_fixture,
    )
except ModuleNotFoundError:
    from test_dashboard_session_planning import (  # type: ignore[no-redef]
        DEFAULT_BASELINE_ARM_ID,
        DEFAULT_CONDITION_IDS,
        DEFAULT_SEED,
        DEFAULT_WAVE_ARM_ID,
        EXPERIMENT_ID,
        _materialize_dashboard_fixture,
    )

try:
    from tests.test_experiment_suite_aggregation import (
        _materialize_packaged_suite_fixture,
    )
except ModuleNotFoundError:
    from test_experiment_suite_aggregation import (  # type: ignore[no-redef]
        _materialize_packaged_suite_fixture,
    )


class ShowcaseSessionPlanningTest(unittest.TestCase):
    def test_packaged_dashboard_and_suite_inputs_resolve_deterministic_showcase_bundle(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))

            first = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                suite_review_summary_path=fixture["suite_review_summary_path"],
                table_dimension_ids=["motion_direction"],
                saved_preset_overrides={
                    PAIRED_COMPARISON_PRESET_ID: {
                        "display_name": "Paired Fairness",
                        "presentation_state_patch": {
                            "dashboard_state_patch": {
                                "global_interaction_state": {
                                    "active_overlay_id": SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                                },
                                "replay_state": {
                                    "active_overlay_id": SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                                },
                            },
                        },
                    },
                },
            )
            second = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                suite_review_summary_path=fixture["suite_review_summary_path"],
                table_dimension_ids=["motion_direction"],
                saved_preset_overrides={
                    PAIRED_COMPARISON_PRESET_ID: {
                        "display_name": "Paired Fairness",
                        "presentation_state_patch": {
                            "dashboard_state_patch": {
                                "global_interaction_state": {
                                    "active_overlay_id": SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                                },
                                "replay_state": {
                                    "active_overlay_id": SHARED_READOUT_ACTIVITY_OVERLAY_ID,
                                },
                            },
                        },
                    },
                },
            )

            self.assertEqual(first, second)
            self.assertEqual(first["source_mode"], "dashboard_session")
            self.assertEqual(
                [item["step_id"] for item in first["narrative_step_sequence"]],
                [
                    SCENE_SELECTION_STEP_ID,
                    FLY_VIEW_INPUT_STEP_ID,
                    ACTIVE_VISUAL_SUBSET_STEP_ID,
                    ACTIVITY_PROPAGATION_STEP_ID,
                    BASELINE_WAVE_COMPARISON_STEP_ID,
                    APPROVED_WAVE_HIGHLIGHT_STEP_ID,
                    SUMMARY_ANALYSIS_STEP_ID,
                ],
            )
            self.assertEqual(
                _saved_preset(first, PAIRED_COMPARISON_PRESET_ID)["display_name"],
                "Paired Fairness",
            )
            self.assertEqual(
                first["closing_analysis_assets"]["suite_summary_table_path"],
                str(fixture["suite_summary_table_path"]),
            )
            self.assertEqual(
                first["output_locations"]["metadata_path"],
                first["showcase_session"]["artifacts"][METADATA_JSON_KEY]["path"],
            )

            packaged = package_showcase_session(first)
            metadata = load_showcase_session_metadata(packaged["metadata_path"])
            bundle_paths = discover_showcase_session_bundle_paths(metadata)

            self.assertEqual(metadata["bundle_id"], first["showcase_session"]["bundle_id"])
            self.assertEqual(
                bundle_paths[METADATA_JSON_KEY],
                Path(packaged["metadata_path"]).resolve(),
            )
            self.assertEqual(
                bundle_paths[SHOWCASE_SCRIPT_PAYLOAD_ARTIFACT_ID],
                Path(packaged["showcase_script_path"]).resolve(),
            )
            self.assertEqual(
                bundle_paths[SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID],
                Path(packaged["showcase_state_path"]).resolve(),
            )
            self.assertEqual(
                bundle_paths[SHOWCASE_EXPORT_MANIFEST_ARTIFACT_ID],
                Path(packaged["showcase_export_manifest_path"]).resolve(),
            )
            self.assertEqual(
                packaged["upstream_dashboard_metadata_path"],
                str(fixture["dashboard_metadata_path"]),
            )
            self.assertEqual(packaged["output_locations"], first["output_locations"])
            self.assertTrue(
                str(Path(packaged["bundle_directory"]).resolve()).endswith(
                    f"/showcase_sessions/{EXPERIMENT_ID}/{metadata['showcase_spec_hash']}"
                )
            )
            export_manifest = json.loads(
                Path(packaged["showcase_export_manifest_path"]).read_text(encoding="utf-8")
            )
            export_paths = {
                item["export_target_role_id"]: item["path"]
                for item in export_manifest["export_targets"]
            }
            self.assertEqual(
                export_paths,
                first["output_locations"]["export_target_paths"],
            )

    def test_suite_package_source_mode_discovers_dashboard_stage_artifact(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))
            _inject_dashboard_stage_artifact(
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                dashboard_metadata_path=fixture["dashboard_metadata_path"],
            )

            plan = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                table_dimension_ids=["motion_direction"],
            )

            self.assertEqual(plan["source_mode"], "suite_package")
            self.assertIsNone(plan["dashboard_session_plan"])
            self.assertEqual(
                next(
                    item["path"]
                    for item in plan["upstream_artifact_references"]
                    if item["artifact_role_id"] == DASHBOARD_SESSION_METADATA_ROLE_ID
                ),
                str(fixture["dashboard_metadata_path"]),
            )
            self.assertEqual(
                plan["closing_analysis_assets"]["suite_summary_table_path"],
                str(fixture["suite_summary_table_path"]),
            )

    def test_explicit_artifact_inputs_preserve_suite_evidence_and_highlight_override(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))
            _approve_validation_highlight(fixture)

            baseline_plan = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                suite_review_summary_path=fixture["suite_review_summary_path"],
                table_dimension_ids=["motion_direction"],
            )
            explicit_plan = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                explicit_artifact_references=baseline_plan["upstream_artifact_references"],
                highlight_override={
                    "phenomenon_id": "phase_alignment_focus",
                    "locator": "wave_only_diagnostics.phase_map_references[0]",
                    "citation_label": "Approved phase alignment",
                },
            )

            self.assertEqual(explicit_plan["source_mode"], "explicit_artifact_inputs")
            self.assertEqual(
                explicit_plan["closing_analysis_assets"]["suite_summary_table_path"],
                baseline_plan["closing_analysis_assets"]["suite_summary_table_path"],
            )
            self.assertEqual(
                explicit_plan["highlight_selection"]["phenomenon_id"],
                "phase_alignment_focus",
            )
            self.assertEqual(
                explicit_plan["highlight_selection"]["citation_label"],
                "Approved phase alignment",
            )
            self.assertEqual(
                explicit_plan["highlight_selection"]["presentation_status"],
                "ready",
            )
            self.assertEqual(
                _showcase_step(explicit_plan, APPROVED_WAVE_HIGHLIGHT_STEP_ID)["preset_id"],
                APPROVED_HIGHLIGHT_PRESET_ID,
            )
            self.assertEqual(
                _saved_preset(explicit_plan, ANALYSIS_SUMMARY_PRESET_ID)["step_id"],
                SUMMARY_ANALYSIS_STEP_ID,
            )

    def test_rehearsal_fixture_packages_curated_preset_library_and_evidence_backed_highlight(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))
            _approve_validation_highlight(fixture)

            plan = resolve_showcase_session_plan(
                config_path=fixture["config_path"],
                dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                suite_package_metadata_path=fixture["suite_package_metadata_path"],
                suite_review_summary_path=fixture["suite_review_summary_path"],
                table_dimension_ids=["motion_direction"],
                fixture_mode=SHOWCASE_FIXTURE_MODE_REHEARSAL,
                highlight_override={
                    "phenomenon_id": "phase_alignment_focus",
                    "locator": "wave_only_diagnostics.phase_map_references[0]",
                    "citation_label": "Approved phase alignment",
                },
            )
            packaged = package_showcase_session(plan)
            catalog = json.loads(
                Path(packaged["narrative_preset_catalog_path"]).read_text(encoding="utf-8")
            )

            self.assertEqual(plan["fixture_mode"], SHOWCASE_FIXTURE_MODE_REHEARSAL)
            self.assertTrue(plan["showcase_fixture"]["keeps_readiness_fixtures_fast"])
            self.assertEqual(
                catalog["fixture_profile"]["fixture_mode"],
                SHOWCASE_FIXTURE_MODE_REHEARSAL,
            )
            self.assertEqual(
                catalog["story_arc_preset_ids"],
                {
                    "scene_choice": "scene_context",
                    "fly_view_framing": "retinal_input_focus",
                    "active_subset_emphasis": "subset_context",
                    "propagation_view": "propagation_replay",
                    "comparison_pairing": "paired_comparison",
                    "highlight_phenomenon_reference": "approved_highlight",
                    "highlight_fallback": "highlight_fallback",
                    "final_analysis_landing": "analysis_summary",
                },
            )
            self.assertEqual(
                catalog["preset_discovery_order"],
                [
                    "scene_context",
                    "retinal_input_focus",
                    "subset_context",
                    "propagation_replay",
                    "paired_comparison",
                    "approved_highlight",
                    "highlight_fallback",
                    "analysis_summary",
                ],
            )
            self.assertEqual(
                [item["preset_id"] for item in catalog["saved_presets"]],
                catalog["preset_discovery_order"],
            )

            approved_preset = next(
                item
                for item in catalog["saved_presets"]
                if item["preset_id"] == APPROVED_HIGHLIGHT_PRESET_ID
            )
            self.assertEqual(
                approved_preset["presentation_state_patch"]["rehearsal_metadata"][
                    "story_role"
                ],
                "highlight_phenomenon_reference",
            )
            self.assertEqual(
                catalog["highlight_metadata"]["phenomenon_id"],
                "phase_alignment_focus",
            )
            self.assertEqual(
                catalog["highlight_metadata"]["fallback_path"]["fallback_preset_id"],
                HIGHLIGHT_FALLBACK_PRESET_ID,
            )
            self.assertEqual(
                catalog["highlight_metadata"]["fallback_path"]["fallback_step_id"],
                BASELINE_WAVE_COMPARISON_STEP_ID,
            )
            support_roles = {
                item["artifact_role_id"]
                for item in catalog["highlight_metadata"]["supporting_evidence_references"]
            }
            self.assertIn(SUITE_SUMMARY_TABLE_ROLE_ID, support_roles)
            self.assertIn(VALIDATION_REVIEW_HANDOFF_ROLE_ID, support_roles)

            highlight_step = _showcase_step(plan, APPROVED_WAVE_HIGHLIGHT_STEP_ID)
            self.assertEqual(
                {
                    item["artifact_role_id"]
                    for item in highlight_step["evidence_references"]
                },
                {
                    ANALYSIS_UI_PAYLOAD_ROLE_ID,
                    SUITE_SUMMARY_TABLE_ROLE_ID,
                    VALIDATION_REVIEW_HANDOFF_ROLE_ID,
                },
            )
            self.assertEqual(
                catalog["highlight_step_evidence_references"],
                highlight_step["evidence_references"],
            )

    def test_planning_fails_clearly_for_unsupported_preset_overlay_and_missing_highlight_review(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir_str:
            fixture = _materialize_packaged_showcase_fixture(Path(tmp_dir_str))

            with self.assertRaises(ValueError) as overlay_ctx:
                resolve_showcase_session_plan(
                    config_path=fixture["config_path"],
                    dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                    saved_preset_overrides={
                        PAIRED_COMPARISON_PRESET_ID: {
                            "presentation_state_patch": {
                                "dashboard_state_patch": {
                                    "global_interaction_state": {
                                        "active_overlay_id": "unsupported_overlay",
                                    },
                                },
                            },
                        },
                    },
                )

            self.assertIn("references unavailable overlay", str(overlay_ctx.exception))

            review_handoff_path = discover_validation_bundle_paths(
                fixture["validation_bundle_metadata"]
            )[REVIEW_HANDOFF_ARTIFACT_ID]
            review_handoff_path.unlink()

            with self.assertRaises(ValueError) as highlight_ctx:
                resolve_showcase_session_plan(
                    config_path=fixture["config_path"],
                    dashboard_session_metadata_path=fixture["dashboard_metadata_path"],
                    highlight_override={
                        "phenomenon_id": "phase_alignment_focus",
                        "locator": "wave_only_diagnostics.phase_map_references[0]",
                        "citation_label": "Approved phase alignment",
                    },
                )

            self.assertIn(
                "validation review_handoff artifact is unavailable",
                str(highlight_ctx.exception),
            )


def _materialize_packaged_showcase_fixture(tmp_dir: Path) -> dict[str, Any]:
    dashboard_root = tmp_dir / "dashboard_fixture"
    dashboard_root.mkdir(parents=True, exist_ok=True)
    dashboard_fixture = _materialize_dashboard_fixture(dashboard_root)
    dashboard_plan = resolve_dashboard_session_plan(
        experiment_id=EXPERIMENT_ID,
        config_path=dashboard_fixture["config_path"],
        baseline_arm_id=DEFAULT_BASELINE_ARM_ID,
        wave_arm_id=DEFAULT_WAVE_ARM_ID,
        preferred_seed=DEFAULT_SEED,
        preferred_condition_ids=DEFAULT_CONDITION_IDS,
    )
    dashboard_package = package_dashboard_session(dashboard_plan)
    dashboard_metadata_path = Path(dashboard_package["metadata_path"]).resolve()

    suite_root = tmp_dir / "suite_fixture"
    suite_root.mkdir(parents=True, exist_ok=True)
    suite_package_metadata_path = _materialize_packaged_suite_fixture(suite_root)
    suite_review_summary = generate_experiment_suite_review_report(
        suite_package_metadata_path,
        table_dimension_ids=["motion_direction"],
    )
    suite_summary_table_path = Path(
        next(
            item["path"]
            for item in json.loads(
                Path(suite_review_summary["report_layout"]["artifact_catalog_path"]).read_text(
                    encoding="utf-8"
                )
            )["table_artifacts"]
            if item["artifact_id"] == "shared_comparison_summary_table"
        )
    ).resolve()

    return {
        **dashboard_fixture,
        "dashboard_plan": dashboard_plan,
        "dashboard_package": dashboard_package,
        "dashboard_metadata_path": dashboard_metadata_path,
        "suite_package_metadata_path": Path(suite_package_metadata_path).resolve(),
        "suite_review_summary_path": Path(
            suite_review_summary["report_layout"]["summary_path"]
        ).resolve(),
        "suite_summary_table_path": suite_summary_table_path,
    }


def _inject_dashboard_stage_artifact(
    *,
    suite_package_metadata_path: Path,
    dashboard_metadata_path: Path,
) -> None:
    package_metadata = load_experiment_suite_package_metadata(suite_package_metadata_path)
    result_index = load_experiment_suite_result_index(package_metadata)
    dashboard_metadata = load_dashboard_session_metadata(dashboard_metadata_path)
    result_index["stage_artifacts"] = [
        item
        for item in result_index["stage_artifacts"]
        if not (
            str(item.get("stage_id")) == "dashboard"
            and str(item.get("artifact_id")) == "metadata_json"
        )
    ]
    result_index["stage_artifacts"].append(
        {
            "suite_cell_id": str(result_index["cell_records"][0]["suite_cell_id"]),
            "stage_id": "dashboard",
            "work_item_id": "fixture_dashboard_stage",
            "stage_status": "succeeded",
            "artifact_role_id": "dashboard_session",
            "source_kind": "dashboard_session_package",
            "bundle_kind": "dashboard_session",
            "contract_version": "dashboard_session.v1",
            "bundle_id": str(dashboard_metadata["bundle_id"]),
            "artifact_id": "metadata_json",
            "artifact_kind": "metadata_json",
            "inventory_category": "bundle_metadata",
            "artifact_scope": "session_package",
            "status": "ready",
            "exists": True,
            "format": "json_dashboard_session_metadata.v1",
            "path": str(dashboard_metadata_path.resolve()),
        }
    )
    result_index_path = Path(package_metadata["artifacts"]["result_index"]["path"]).resolve()
    write_json(result_index, result_index_path)


def _approve_validation_highlight(fixture: dict[str, Any]) -> None:
    review_handoff_path = discover_validation_bundle_paths(
        fixture["validation_bundle_metadata"]
    )[REVIEW_HANDOFF_ARTIFACT_ID]
    payload = json.loads(review_handoff_path.read_text(encoding="utf-8"))
    payload["scientific_plausibility_decision"] = "approved_for_showcase"
    payload["review_status"] = "approved"
    payload["reviewer_rationale"] = "Fixture approves the wave-only beat for showcase coverage."
    write_json(payload, review_handoff_path)


def _saved_preset(plan: dict[str, Any], preset_id: str) -> dict[str, Any]:
    return next(item for item in plan["saved_presets"] if item["preset_id"] == preset_id)


def _showcase_step(plan: dict[str, Any], step_id: str) -> dict[str, Any]:
    return next(item for item in plan["narrative_step_sequence"] if item["step_id"] == step_id)
