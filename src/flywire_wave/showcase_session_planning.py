from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .config import get_config_path, get_project_root, load_config
from .showcase_session_authoring import author_showcase_session_story
from .showcase_session_contract import (
    DEFAULT_EXPORT_TARGET_ROLE_ID,
    build_showcase_session_contract_metadata,
    build_showcase_session_metadata,
    parse_showcase_session_contract_metadata,
)
from .showcase_session_packaging import (
    assemble_showcase_session_outputs,
    package_showcase_session_plan,
)
from .showcase_session_sources import (
    build_showcase_upstream_artifact_references,
    resolve_showcase_session_sources,
)
from .simulator_result_contract import DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR
from .stimulus_contract import ASSET_STATUS_READY, _normalize_identifier


SHOWCASE_SESSION_PLAN_VERSION = "showcase_session_plan.v1"
SHOWCASE_SESSION_SOURCE_MODE_MANIFEST = "manifest"
SHOWCASE_SESSION_SOURCE_MODE_EXPERIMENT = "experiment"
SHOWCASE_SESSION_SOURCE_MODE_DASHBOARD = "dashboard_session"
SHOWCASE_SESSION_SOURCE_MODE_SUITE = "suite_package"
SHOWCASE_SESSION_SOURCE_MODE_EXPLICIT = "explicit_artifact_inputs"

DEFAULT_SHOWCASE_ID = "milestone_16_showcase"
DEFAULT_SHOWCASE_DISPLAY_NAME = "Milestone 16 Showcase"
SHOWCASE_FIXTURE_MODE_REHEARSAL = "milestone16_rehearsal"
SUPPORTED_SHOWCASE_FIXTURE_MODES = (SHOWCASE_FIXTURE_MODE_REHEARSAL,)
DEFAULT_SHOWCASE_FIXTURE_MODE = SHOWCASE_FIXTURE_MODE_REHEARSAL


def resolve_manifest_showcase_session_plan(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    **overrides: Any,
) -> dict[str, Any]:
    return resolve_showcase_session_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        **overrides,
    )


def resolve_showcase_session_plan(
    *,
    config_path: str | Path,
    manifest_path: str | Path | None = None,
    schema_path: str | Path | None = None,
    design_lock_path: str | Path | None = None,
    experiment_id: str | None = None,
    dashboard_session_metadata: Mapping[str, Any] | None = None,
    dashboard_session_metadata_path: str | Path | None = None,
    suite_package_metadata: Mapping[str, Any] | None = None,
    suite_package_metadata_path: str | Path | None = None,
    suite_review_summary: Mapping[str, Any] | None = None,
    suite_review_summary_path: str | Path | None = None,
    explicit_artifact_references: Sequence[Mapping[str, Any]] | None = None,
    showcase_id: str = DEFAULT_SHOWCASE_ID,
    display_name: str = DEFAULT_SHOWCASE_DISPLAY_NAME,
    fixture_mode: str = DEFAULT_SHOWCASE_FIXTURE_MODE,
    table_dimension_ids: Sequence[str] | None = None,
    saved_preset_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    highlight_override: Mapping[str, Any] | None = None,
    enabled_export_target_role_ids: Sequence[str] | None = None,
    default_export_target_role_id: str = DEFAULT_EXPORT_TARGET_ROLE_ID,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = load_config(config_path)
    config_file = get_config_path(cfg)
    project_root = get_project_root(cfg)
    if config_file is None or project_root is None:
        raise ValueError("Loaded config is missing config metadata.")

    normalized_fixture_mode = _normalize_fixture_mode(fixture_mode)
    normalized_contract = parse_showcase_session_contract_metadata(
        contract_metadata
        if contract_metadata is not None
        else build_showcase_session_contract_metadata()
    )
    processed_dir = Path(
        cfg["paths"].get(
            "processed_simulator_results_dir",
            DEFAULT_PROCESSED_SIMULATOR_RESULTS_DIR,
        )
    ).resolve()

    sources = resolve_showcase_session_sources(
        config_path=config_path,
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        experiment_id=experiment_id,
        dashboard_session_metadata=dashboard_session_metadata,
        dashboard_session_metadata_path=dashboard_session_metadata_path,
        suite_package_metadata=suite_package_metadata,
        suite_package_metadata_path=suite_package_metadata_path,
        suite_review_summary=suite_review_summary,
        suite_review_summary_path=suite_review_summary_path,
        explicit_artifact_references=explicit_artifact_references,
        table_dimension_ids=table_dimension_ids,
        requested_highlight=highlight_override is not None,
    )
    authored = author_showcase_session_story(
        dashboard_context=sources["dashboard_context"],
        analysis_context=sources["analysis_context"],
        validation_context=sources["validation_context"],
        suite_context=sources["suite_context"],
        fixture_mode=normalized_fixture_mode,
        saved_preset_overrides=saved_preset_overrides,
        highlight_override=highlight_override,
        enabled_export_target_role_ids=enabled_export_target_role_ids,
        default_export_target_role_id=default_export_target_role_id,
        contract_metadata=normalized_contract,
    )
    external_artifact_references = build_showcase_upstream_artifact_references(
        dashboard_context=sources["dashboard_context"],
        analysis_context=sources["analysis_context"],
        validation_context=sources["validation_context"],
        suite_context=sources["suite_context"],
        raw_explicit_artifacts=sources["raw_explicit_artifacts"],
        contract_metadata=normalized_contract,
    )
    showcase_session = build_showcase_session_metadata(
        experiment_id=str(sources["resolved_experiment_id"]),
        showcase_id=showcase_id,
        display_name=display_name,
        artifact_references=external_artifact_references,
        saved_presets=authored["saved_presets"],
        showcase_steps=authored["showcase_steps"],
        processed_simulator_results_dir=processed_dir,
        presentation_status=str(authored["presentation_status"]),
        enabled_export_target_role_ids=enabled_export_target_role_ids,
        default_export_target_role_id=default_export_target_role_id,
        showcase_script_payload_status=ASSET_STATUS_READY,
        showcase_presentation_state_status=ASSET_STATUS_READY,
        narrative_preset_catalog_status=ASSET_STATUS_READY,
        showcase_export_manifest_status=ASSET_STATUS_READY,
        contract_metadata=normalized_contract,
    )
    assembled = assemble_showcase_session_outputs(
        showcase_session=showcase_session,
        dashboard_context=sources["dashboard_context"],
        narrative_context=authored["narrative_context"],
        showcase_steps=authored["showcase_steps"],
        saved_presets=authored["saved_presets"],
        showcase_fixture=authored["showcase_fixture"],
        contract_metadata=normalized_contract,
        plan_version=SHOWCASE_SESSION_PLAN_VERSION,
    )

    return {
        "plan_version": SHOWCASE_SESSION_PLAN_VERSION,
        "source_mode": str(sources["source_mode"]),
        "fixture_mode": normalized_fixture_mode,
        "manifest_reference": copy.deepcopy(
            dict(sources["dashboard_context"]["metadata"]["manifest_reference"])
        ),
        "config_reference": {
            "config_path": str(Path(config_file).resolve()),
            "project_root": str(Path(project_root).resolve()),
        },
        "scene_choice": copy.deepcopy(authored["narrative_context"]["scene_choice"]),
        "input_surface": copy.deepcopy(authored["narrative_context"]["input_surface"]),
        "active_subset_focus_targets": copy.deepcopy(
            authored["narrative_context"]["active_subset_focus_targets"]
        ),
        "activity_propagation_views": copy.deepcopy(
            authored["narrative_context"]["activity_propagation_views"]
        ),
        "approved_comparison_arms": copy.deepcopy(
            authored["narrative_context"]["approved_comparison_arms"]
        ),
        "comparison_act": copy.deepcopy(authored["narrative_context"]["comparison_act"]),
        "highlight_selection": copy.deepcopy(
            authored["narrative_context"]["highlight_selection"]
        ),
        "highlight_presentation": copy.deepcopy(
            authored["narrative_context"]["highlight_presentation"]
        ),
        "closing_analysis_assets": copy.deepcopy(
            authored["narrative_context"]["closing_analysis_assets"]
        ),
        "summary_analysis_landing": copy.deepcopy(
            authored["narrative_context"]["summary_analysis_landing"]
        ),
        "operator_defaults": copy.deepcopy(assembled["operator_defaults"]),
        "upstream_artifact_references": copy.deepcopy(external_artifact_references),
        "saved_presets": copy.deepcopy(authored["saved_presets"]),
        "narrative_step_sequence": copy.deepcopy(authored["showcase_steps"]),
        "dashboard_session_plan": (
            None
            if sources["dashboard_context"]["plan"] is None
            else copy.deepcopy(sources["dashboard_context"]["plan"])
        ),
        "suite_evidence": copy.deepcopy(sources["suite_context"]),
        "showcase_session": copy.deepcopy(showcase_session),
        "showcase_script_payload": copy.deepcopy(assembled["showcase_script_payload"]),
        "showcase_presentation_state": copy.deepcopy(
            assembled["showcase_presentation_state"]
        ),
        "narrative_preset_catalog": copy.deepcopy(assembled["narrative_preset_catalog"]),
        "showcase_export_manifest": copy.deepcopy(assembled["showcase_export_manifest"]),
        "showcase_fixture": copy.deepcopy(authored["showcase_fixture"]),
        "output_locations": copy.deepcopy(assembled["output_locations"]),
    }


def package_showcase_session(plan: Mapping[str, Any]) -> dict[str, Any]:
    return package_showcase_session_plan(
        plan,
        plan_version=SHOWCASE_SESSION_PLAN_VERSION,
    )


def _normalize_fixture_mode(value: Any) -> str:
    normalized = _normalize_identifier(value, field_name="fixture_mode")
    if normalized not in SUPPORTED_SHOWCASE_FIXTURE_MODES:
        raise ValueError(
            f"fixture_mode must be one of {SUPPORTED_SHOWCASE_FIXTURE_MODES!r}."
        )
    return normalized
