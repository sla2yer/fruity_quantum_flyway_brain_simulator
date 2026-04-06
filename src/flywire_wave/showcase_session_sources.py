from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .dashboard_session_contract import (
    ANALYSIS_BUNDLE_METADATA_ROLE_ID as DASHBOARD_ANALYSIS_BUNDLE_METADATA_ROLE_ID,
    CIRCUIT_PANE_ID,
    DASHBOARD_SESSION_METADATA_ROLE_ID as DASHBOARD_METADATA_ROLE_ID,
    DASHBOARD_SESSION_PAYLOAD_ROLE_ID as DASHBOARD_PAYLOAD_ROLE_ID,
    DASHBOARD_SESSION_STATE_ROLE_ID as DASHBOARD_STATE_ROLE_ID,
    METADATA_JSON_KEY as DASHBOARD_METADATA_JSON_KEY,
    PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
    SCENE_PANE_ID,
    SESSION_PAYLOAD_ARTIFACT_ID,
    SESSION_STATE_ARTIFACT_ID,
    TIME_SERIES_PANE_ID,
    VALIDATION_BUNDLE_METADATA_ROLE_ID as DASHBOARD_VALIDATION_BUNDLE_METADATA_ROLE_ID,
    discover_dashboard_session_artifact_references,
    discover_dashboard_session_bundle_paths,
    load_dashboard_session_metadata,
)
from .dashboard_session_planning import resolve_dashboard_session_plan
from .experiment_analysis_contract import (
    ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
    METADATA_JSON_KEY as ANALYSIS_METADATA_JSON_KEY,
    OFFLINE_REPORT_INDEX_ARTIFACT_ID,
    discover_experiment_analysis_bundle_paths,
    load_experiment_analysis_bundle_metadata,
)
from .experiment_suite_contract import EXPERIMENT_SUITE_CONTRACT_VERSION
from .experiment_suite_packaging import (
    discover_experiment_suite_stage_artifacts,
    load_experiment_suite_package_metadata,
)
from .experiment_suite_reporting import generate_experiment_suite_review_report
from .review_surface_artifacts import (
    lift_packaged_artifact_references,
    merge_explicit_artifact_overrides,
    validate_packaged_dashboard_bundle_alignment,
)
from .showcase_session_contract import (
    ANALYSIS_BUNDLE_METADATA_ROLE_ID,
    ANALYSIS_OFFLINE_REPORT_ROLE_ID,
    ANALYSIS_UI_PAYLOAD_ROLE_ID,
    DASHBOARD_SESSION_METADATA_ROLE_ID,
    DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
    DASHBOARD_SESSION_SOURCE_KIND,
    DASHBOARD_SESSION_STATE_ROLE_ID,
    SUITE_COMPARISON_PLOT_ROLE_ID,
    SUITE_REVIEW_ARTIFACT_ROLE_ID,
    SUITE_ROLLUP_SCOPE,
    SUITE_SUMMARY_TABLE_ROLE_ID,
    VALIDATION_BUNDLE_METADATA_ROLE_ID,
    VALIDATION_FINDINGS_ROLE_ID,
    VALIDATION_GUARDRAIL_SCOPE,
    VALIDATION_REVIEW_HANDOFF_ROLE_ID,
    VALIDATION_SUMMARY_ROLE_ID,
    build_showcase_session_artifact_reference,
)
from .stimulus_contract import ASSET_STATUS_READY, _normalize_identifier
from .validation_contract import (
    METADATA_JSON_KEY as VALIDATION_METADATA_JSON_KEY,
    REVIEW_HANDOFF_ARTIFACT_ID,
    VALIDATION_LADDER_CONTRACT_VERSION,
    VALIDATION_SUMMARY_ARTIFACT_ID,
    VALIDATOR_FINDINGS_ARTIFACT_ID,
    discover_validation_bundle_paths,
    load_validation_bundle_metadata,
)


_SOURCE_MODE_MANIFEST = "manifest"
_SOURCE_MODE_EXPERIMENT = "experiment"
_SOURCE_MODE_DASHBOARD = "dashboard_session"
_SOURCE_MODE_SUITE = "suite_package"
_SOURCE_MODE_EXPLICIT = "explicit_artifact_inputs"


def resolve_showcase_session_sources(
    *,
    config_path: str | Path,
    manifest_path: str | Path | None,
    schema_path: str | Path | None,
    design_lock_path: str | Path | None,
    experiment_id: str | None,
    dashboard_session_metadata: Mapping[str, Any] | None,
    dashboard_session_metadata_path: str | Path | None,
    suite_package_metadata: Mapping[str, Any] | None,
    suite_package_metadata_path: str | Path | None,
    suite_review_summary: Mapping[str, Any] | None,
    suite_review_summary_path: str | Path | None,
    explicit_artifact_references: Sequence[Mapping[str, Any]] | None,
    table_dimension_ids: Sequence[str] | None,
    requested_highlight: bool,
) -> dict[str, Any]:
    source_mode = _resolve_source_mode(
        manifest_path=manifest_path,
        experiment_id=experiment_id,
        dashboard_session_metadata=dashboard_session_metadata,
        dashboard_session_metadata_path=dashboard_session_metadata_path,
        suite_package_metadata=suite_package_metadata,
        suite_package_metadata_path=suite_package_metadata_path,
        suite_review_summary=suite_review_summary,
        suite_review_summary_path=suite_review_summary_path,
        explicit_artifact_references=explicit_artifact_references,
    )
    raw_explicit_artifacts = _normalize_raw_explicit_artifact_references(
        explicit_artifact_references
    )
    suite_context = _resolve_suite_context(
        suite_package_metadata=suite_package_metadata,
        suite_package_metadata_path=suite_package_metadata_path,
        suite_review_summary=suite_review_summary,
        suite_review_summary_path=suite_review_summary_path,
        table_dimension_ids=table_dimension_ids,
        raw_explicit_artifacts=raw_explicit_artifacts,
    )
    resolved_experiment_id = _resolve_experiment_id(
        manifest_path=manifest_path,
        experiment_id=experiment_id,
        suite_context=suite_context,
        raw_explicit_artifacts=raw_explicit_artifacts,
    )
    dashboard_context = _resolve_dashboard_context(
        config_path=config_path,
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        experiment_id=resolved_experiment_id,
        dashboard_session_metadata=dashboard_session_metadata,
        dashboard_session_metadata_path=dashboard_session_metadata_path,
        raw_explicit_artifacts=raw_explicit_artifacts,
        suite_context=suite_context,
    )
    resolved_experiment_id = str(dashboard_context["metadata"]["experiment_id"])
    _validate_experiment_alignment(
        experiment_id=resolved_experiment_id,
        source_mode=source_mode,
        suite_context=suite_context,
    )
    analysis_context = _resolve_analysis_context(
        dashboard_metadata=dashboard_context["metadata"],
        raw_explicit_artifacts=raw_explicit_artifacts,
    )
    validation_context = _resolve_validation_context(
        dashboard_metadata=dashboard_context["metadata"],
        raw_explicit_artifacts=raw_explicit_artifacts,
        requested_highlight=requested_highlight,
    )
    return {
        "source_mode": source_mode,
        "resolved_experiment_id": resolved_experiment_id,
        "raw_explicit_artifacts": raw_explicit_artifacts,
        "suite_context": suite_context,
        "dashboard_context": dashboard_context,
        "analysis_context": analysis_context,
        "validation_context": validation_context,
    }


def build_showcase_upstream_artifact_references(
    *,
    dashboard_context: Mapping[str, Any],
    analysis_context: Mapping[str, Any],
    validation_context: Mapping[str, Any],
    suite_context: Mapping[str, Any] | None,
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    contract_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    dashboard_metadata = dashboard_context["metadata"]
    dashboard_paths = discover_dashboard_session_bundle_paths(dashboard_metadata)
    discovered: list[dict[str, Any]] = lift_packaged_artifact_references(
        metadata=dashboard_metadata,
        bundle_paths=dashboard_paths,
        contract_metadata=contract_metadata,
        source_kind=DASHBOARD_SESSION_SOURCE_KIND,
        build_artifact_reference=build_showcase_session_artifact_reference,
    )

    analysis_metadata = analysis_context["metadata"]
    analysis_paths = analysis_context["bundle_paths"]
    discovered.extend(
        [
            build_showcase_session_artifact_reference(
                artifact_role_id=ANALYSIS_BUNDLE_METADATA_ROLE_ID,
                source_kind="experiment_analysis_bundle",
                path=analysis_paths[ANALYSIS_METADATA_JSON_KEY],
                contract_version=str(analysis_metadata["contract_version"]),
                bundle_id=str(analysis_metadata["bundle_id"]),
                artifact_id=ANALYSIS_METADATA_JSON_KEY,
                format=str(analysis_metadata["artifacts"][ANALYSIS_METADATA_JSON_KEY]["format"]),
                artifact_scope="analysis_context",
                status=str(analysis_metadata["artifacts"][ANALYSIS_METADATA_JSON_KEY]["status"]),
            ),
            build_showcase_session_artifact_reference(
                artifact_role_id=ANALYSIS_UI_PAYLOAD_ROLE_ID,
                source_kind="experiment_analysis_bundle",
                path=analysis_context["ui_payload_path"],
                contract_version=str(analysis_metadata["contract_version"]),
                bundle_id=str(analysis_metadata["bundle_id"]),
                artifact_id=ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
                format=str(
                    analysis_metadata["artifacts"][ANALYSIS_UI_PAYLOAD_ARTIFACT_ID]["format"]
                ),
                artifact_scope="analysis_context",
                status=str(
                    analysis_metadata["artifacts"][ANALYSIS_UI_PAYLOAD_ARTIFACT_ID]["status"]
                ),
            ),
        ]
    )
    if analysis_context["offline_report_path"] is not None:
        discovered.append(
            build_showcase_session_artifact_reference(
                artifact_role_id=ANALYSIS_OFFLINE_REPORT_ROLE_ID,
                source_kind="experiment_analysis_bundle",
                path=analysis_context["offline_report_path"],
                contract_version=str(analysis_metadata["contract_version"]),
                bundle_id=str(analysis_metadata["bundle_id"]),
                artifact_id=OFFLINE_REPORT_INDEX_ARTIFACT_ID,
                format=str(
                    analysis_metadata["artifacts"][OFFLINE_REPORT_INDEX_ARTIFACT_ID]["format"]
                ),
                artifact_scope="analysis_context",
                status=str(
                    analysis_metadata["artifacts"][OFFLINE_REPORT_INDEX_ARTIFACT_ID]["status"]
                ),
            )
        )

    validation_metadata = validation_context["metadata"]
    validation_paths = validation_context["bundle_paths"]
    discovered.extend(
        [
            build_showcase_session_artifact_reference(
                artifact_role_id=VALIDATION_BUNDLE_METADATA_ROLE_ID,
                source_kind="validation_bundle",
                path=validation_paths[VALIDATION_METADATA_JSON_KEY],
                contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
                bundle_id=str(validation_metadata["bundle_id"]),
                artifact_id=VALIDATION_METADATA_JSON_KEY,
                format=str(validation_metadata["artifacts"][VALIDATION_METADATA_JSON_KEY]["format"]),
                artifact_scope=VALIDATION_GUARDRAIL_SCOPE,
                status=str(validation_metadata["artifacts"][VALIDATION_METADATA_JSON_KEY]["status"]),
            ),
            build_showcase_session_artifact_reference(
                artifact_role_id=VALIDATION_SUMMARY_ROLE_ID,
                source_kind="validation_bundle",
                path=validation_context["summary_path"],
                contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
                bundle_id=str(validation_metadata["bundle_id"]),
                artifact_id=VALIDATION_SUMMARY_ARTIFACT_ID,
                format=str(
                    validation_metadata["artifacts"][VALIDATION_SUMMARY_ARTIFACT_ID]["format"]
                ),
                artifact_scope=VALIDATION_GUARDRAIL_SCOPE,
                status=str(
                    validation_metadata["artifacts"][VALIDATION_SUMMARY_ARTIFACT_ID]["status"]
                ),
            ),
            build_showcase_session_artifact_reference(
                artifact_role_id=VALIDATION_FINDINGS_ROLE_ID,
                source_kind="validation_bundle",
                path=validation_context["findings_path"],
                contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
                bundle_id=str(validation_metadata["bundle_id"]),
                artifact_id=VALIDATOR_FINDINGS_ARTIFACT_ID,
                format=str(
                    validation_metadata["artifacts"][VALIDATOR_FINDINGS_ARTIFACT_ID]["format"]
                ),
                artifact_scope=VALIDATION_GUARDRAIL_SCOPE,
                status=str(
                    validation_metadata["artifacts"][VALIDATOR_FINDINGS_ARTIFACT_ID]["status"]
                ),
            ),
        ]
    )
    if validation_context["review_handoff_path"] is not None:
        discovered.append(
            build_showcase_session_artifact_reference(
                artifact_role_id=VALIDATION_REVIEW_HANDOFF_ROLE_ID,
                source_kind="validation_bundle",
                path=validation_context["review_handoff_path"],
                contract_version=VALIDATION_LADDER_CONTRACT_VERSION,
                bundle_id=str(validation_metadata["bundle_id"]),
                artifact_id=REVIEW_HANDOFF_ARTIFACT_ID,
                format=str(validation_metadata["artifacts"][REVIEW_HANDOFF_ARTIFACT_ID]["format"]),
                artifact_scope=VALIDATION_GUARDRAIL_SCOPE,
                status=str(validation_metadata["artifacts"][REVIEW_HANDOFF_ARTIFACT_ID]["status"]),
            )
        )

    if suite_context is not None and suite_context.get("summary_table_artifact") is not None:
        summary_table = suite_context["summary_table_artifact"]
        suite_bundle_id = _suite_bundle_id(suite_context)
        discovered.append(
            build_showcase_session_artifact_reference(
                artifact_role_id=SUITE_SUMMARY_TABLE_ROLE_ID,
                source_kind="experiment_suite_package",
                path=summary_table["path"],
                contract_version=EXPERIMENT_SUITE_CONTRACT_VERSION,
                bundle_id=suite_bundle_id,
                artifact_id=str(summary_table["artifact_id"]),
                format="csv_experiment_suite_summary_table.v1",
                artifact_scope=SUITE_ROLLUP_SCOPE,
            )
        )
    if suite_context is not None and suite_context.get("comparison_plot_artifact") is not None:
        comparison_plot = suite_context["comparison_plot_artifact"]
        discovered.append(
            build_showcase_session_artifact_reference(
                artifact_role_id=SUITE_COMPARISON_PLOT_ROLE_ID,
                source_kind="experiment_suite_package",
                path=comparison_plot["path"],
                contract_version=EXPERIMENT_SUITE_CONTRACT_VERSION,
                bundle_id=_suite_bundle_id(suite_context),
                artifact_id=str(comparison_plot["artifact_id"]),
                format="svg_experiment_suite_comparison_plot.v1",
                artifact_scope=SUITE_ROLLUP_SCOPE,
            )
        )
    if suite_context is not None and suite_context.get("review_artifact") is not None:
        review_artifact = suite_context["review_artifact"]
        discovered.append(
            build_showcase_session_artifact_reference(
                artifact_role_id=SUITE_REVIEW_ARTIFACT_ROLE_ID,
                source_kind="experiment_suite_package",
                path=review_artifact["path"],
                contract_version=EXPERIMENT_SUITE_CONTRACT_VERSION,
                bundle_id=_suite_bundle_id(suite_context),
                artifact_id=str(review_artifact["artifact_id"]),
                format="json_experiment_suite_review_artifact.v1",
                artifact_scope=SUITE_ROLLUP_SCOPE,
            )
        )
    return _merge_explicit_artifact_overrides(
        discovered,
        raw_explicit_artifacts=raw_explicit_artifacts,
        contract_metadata=contract_metadata,
    )


def _resolve_source_mode(
    *,
    manifest_path: str | Path | None,
    experiment_id: str | None,
    dashboard_session_metadata: Mapping[str, Any] | None,
    dashboard_session_metadata_path: str | Path | None,
    suite_package_metadata: Mapping[str, Any] | None,
    suite_package_metadata_path: str | Path | None,
    suite_review_summary: Mapping[str, Any] | None,
    suite_review_summary_path: str | Path | None,
    explicit_artifact_references: Sequence[Mapping[str, Any]] | None,
) -> str:
    if manifest_path is not None:
        return _SOURCE_MODE_MANIFEST
    if experiment_id is not None:
        return _SOURCE_MODE_EXPERIMENT
    if dashboard_session_metadata is not None or dashboard_session_metadata_path is not None:
        return _SOURCE_MODE_DASHBOARD
    if (
        suite_package_metadata is not None
        or suite_package_metadata_path is not None
        or suite_review_summary is not None
        or suite_review_summary_path is not None
    ):
        return _SOURCE_MODE_SUITE
    if explicit_artifact_references:
        return _SOURCE_MODE_EXPLICIT
    raise ValueError(
        "Showcase session planning requires one of manifest_path, experiment_id, "
        "dashboard_session_metadata, suite package/report inputs, or explicit_artifact_references."
    )


def _resolve_experiment_id(
    *,
    manifest_path: str | Path | None,
    experiment_id: str | None,
    suite_context: Mapping[str, Any] | None,
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
) -> str | None:
    candidates: set[str] = set()
    if experiment_id is not None:
        candidates.add(_normalize_identifier(experiment_id, field_name="experiment_id"))
    if suite_context and suite_context.get("experiment_id") is not None:
        candidates.add(str(suite_context["experiment_id"]))
    dashboard_metadata_ref = raw_explicit_artifacts.get(DASHBOARD_SESSION_METADATA_ROLE_ID)
    if dashboard_metadata_ref is not None:
        metadata = load_dashboard_session_metadata(
            Path(dashboard_metadata_ref["path"]).resolve()
        )
        candidates.add(str(metadata["experiment_id"]))
    if manifest_path is not None and not candidates:
        return None
    if len(candidates) > 1:
        raise ValueError(
            "Showcase planning received conflicting experiment identifiers "
            f"{sorted(candidates)!r}."
        )
    return next(iter(candidates), None)


def _resolve_dashboard_context(
    *,
    config_path: str | Path,
    manifest_path: str | Path | None,
    schema_path: str | Path | None,
    design_lock_path: str | Path | None,
    experiment_id: str | None,
    dashboard_session_metadata: Mapping[str, Any] | None,
    dashboard_session_metadata_path: str | Path | None,
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    suite_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if dashboard_session_metadata is not None or dashboard_session_metadata_path is not None:
        metadata = (
            load_dashboard_session_metadata(dashboard_session_metadata_path)
            if dashboard_session_metadata_path is not None
            else load_dashboard_session_metadata(
                Path(
                    str(
                        dashboard_session_metadata["artifacts"][DASHBOARD_METADATA_JSON_KEY]["path"]
                    )
                )
            )
        )
        return _packaged_dashboard_context(
            metadata,
            raw_explicit_artifacts=raw_explicit_artifacts,
            plan=None,
        )

    dashboard_metadata_ref = raw_explicit_artifacts.get(DASHBOARD_SESSION_METADATA_ROLE_ID)
    if dashboard_metadata_ref is not None:
        metadata = load_dashboard_session_metadata(Path(dashboard_metadata_ref["path"]).resolve())
        return _packaged_dashboard_context(
            metadata,
            raw_explicit_artifacts=raw_explicit_artifacts,
            plan=None,
        )

    if suite_context and suite_context.get("package_metadata") is not None:
        dashboard_from_suite = _discover_dashboard_metadata_from_suite_package(
            suite_context["package_metadata"]
        )
        if dashboard_from_suite is not None:
            return _packaged_dashboard_context(
                dashboard_from_suite,
                raw_explicit_artifacts=raw_explicit_artifacts,
                plan=None,
            )

    if manifest_path is None and experiment_id is None and suite_context is not None:
        experiment_id = (
            None
            if suite_context.get("experiment_id") is None
            else str(suite_context["experiment_id"])
        )

    if manifest_path is not None:
        if schema_path is None or design_lock_path is None:
            raise ValueError(
                "Manifest-driven showcase planning requires schema_path and design_lock_path."
            )
        dashboard_plan = resolve_dashboard_session_plan(
            manifest_path=manifest_path,
            config_path=config_path,
            schema_path=schema_path,
            design_lock_path=design_lock_path,
        )
        return _planned_dashboard_context(dashboard_plan)

    if experiment_id is not None:
        dashboard_plan = resolve_dashboard_session_plan(
            experiment_id=experiment_id,
            config_path=config_path,
        )
        return _planned_dashboard_context(dashboard_plan)

    raise ValueError(
        "Showcase planning could not resolve one dashboard session context. "
        "Pass dashboard_session_metadata, manifest_path, experiment_id, or a suite package "
        "with a discoverable dashboard stage."
    )


def _packaged_dashboard_context(
    metadata: Mapping[str, Any],
    *,
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    normalized_metadata = load_dashboard_session_metadata(
        Path(str(metadata["artifacts"][DASHBOARD_METADATA_JSON_KEY]["path"])).resolve()
    )
    bundle_paths = discover_dashboard_session_bundle_paths(normalized_metadata)
    payload_path = _explicit_or_default_path(
        raw_explicit_artifacts,
        role_id=DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
        default_path=bundle_paths[SESSION_PAYLOAD_ARTIFACT_ID],
    )
    state_path = _explicit_or_default_path(
        raw_explicit_artifacts,
        role_id=DASHBOARD_SESSION_STATE_ROLE_ID,
        default_path=bundle_paths[SESSION_STATE_ARTIFACT_ID],
    )
    payload = _load_json_mapping(payload_path, field_name="dashboard_session_payload")
    state = _load_json_mapping(state_path, field_name="dashboard_session_state")
    _validate_dashboard_payload(metadata=normalized_metadata, payload=payload, state=state)
    return {
        "origin": "packaged",
        "metadata": normalized_metadata,
        "payload": payload,
        "state": state,
        "plan": plan,
    }


def _planned_dashboard_context(plan: Mapping[str, Any]) -> dict[str, Any]:
    normalized_plan = _require_mapping(plan, field_name="dashboard_session_plan")
    metadata = _require_mapping(
        normalized_plan.get("dashboard_session"),
        field_name="dashboard_session_plan.dashboard_session",
    )
    payload = _require_mapping(
        normalized_plan.get("dashboard_session_payload"),
        field_name="dashboard_session_plan.dashboard_session_payload",
    )
    state = _require_mapping(
        normalized_plan.get("dashboard_session_state"),
        field_name="dashboard_session_plan.dashboard_session_state",
    )
    _validate_dashboard_payload(metadata=metadata, payload=payload, state=state)
    return {
        "origin": "planned",
        "metadata": copy.deepcopy(dict(metadata)),
        "payload": copy.deepcopy(dict(payload)),
        "state": copy.deepcopy(dict(state)),
        "plan": copy.deepcopy(dict(normalized_plan)),
    }


def _validate_dashboard_payload(
    *,
    metadata: Mapping[str, Any],
    payload: Mapping[str, Any],
    state: Mapping[str, Any],
) -> None:
    selected_pair = _require_mapping(
        payload.get("selected_bundle_pair"),
        field_name="dashboard_session_payload.selected_bundle_pair",
    )
    baseline = _require_mapping(
        selected_pair.get("baseline"),
        field_name="dashboard_session_payload.selected_bundle_pair.baseline",
    )
    wave = _require_mapping(
        selected_pair.get("wave"),
        field_name="dashboard_session_payload.selected_bundle_pair.wave",
    )
    if str(baseline["arm_id"]) == str(wave["arm_id"]):
        raise ValueError(
            "Showcase planning requires one distinct baseline-versus-wave arm pair."
        )

    scene_context = _require_mapping(
        payload.get("pane_inputs", {}).get(SCENE_PANE_ID),
        field_name="dashboard_session_payload.pane_inputs.scene",
    )
    if str(scene_context.get("render_status")) != "available":
        reason = _require_mapping(
            scene_context.get("frame_discovery", {}),
            field_name="dashboard_session_payload.pane_inputs.scene.frame_discovery",
        ).get("unavailable_reason", "scene render layer is unavailable")
        raise ValueError(
            "Showcase planning requires a packaged fly-view or sampled-input surface; "
            f"dashboard scene render_status is {scene_context.get('render_status')!r}: {reason}."
        )

    time_series_context = _require_mapping(
        payload.get("pane_inputs", {}).get(TIME_SERIES_PANE_ID),
        field_name="dashboard_session_payload.pane_inputs.time_series",
    )
    replay_model = _require_mapping(
        time_series_context.get("replay_model"),
        field_name="dashboard_session_payload.pane_inputs.time_series.replay_model",
    )
    shared_timebase_status = _require_mapping(
        replay_model.get("shared_timebase_status"),
        field_name=(
            "dashboard_session_payload.pane_inputs.time_series.replay_model."
            "shared_timebase_status"
        ),
    )
    if str(shared_timebase_status.get("availability")) != "available":
        raise ValueError(
            "Showcase planning requires a shared baseline-versus-wave timebase, but "
            f"dashboard replay reports {shared_timebase_status!r}."
        )
    paired_status = _comparison_mode_status_by_id(
        replay_model,
        comparison_mode_id=PAIRED_BASELINE_VS_WAVE_COMPARISON_MODE,
    )
    if str(paired_status.get("availability")) != "available":
        raise ValueError(
            "Showcase planning requires one available paired baseline-versus-wave "
            "comparison mode, but dashboard replay reports "
            f"{paired_status!r}."
        )

    circuit_context = _require_mapping(
        payload.get("pane_inputs", {}).get(CIRCUIT_PANE_ID),
        field_name="dashboard_session_payload.pane_inputs.circuit",
    )
    selected_root_ids = list(circuit_context.get("selected_root_ids", []))
    if not selected_root_ids:
        raise ValueError(
            "Showcase planning requires at least one selected root in the dashboard circuit context."
        )

    validate_packaged_dashboard_bundle_alignment(
        metadata=metadata,
        payload=payload,
        state=state,
    )


def _resolve_analysis_context(
    *,
    dashboard_metadata: Mapping[str, Any],
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    metadata = _load_upstream_bundle_metadata_from_dashboard(
        dashboard_metadata=dashboard_metadata,
        dashboard_role_id=DASHBOARD_ANALYSIS_BUNDLE_METADATA_ROLE_ID,
        explicit_metadata_path=raw_explicit_artifacts.get(ANALYSIS_BUNDLE_METADATA_ROLE_ID, {}).get("path"),
        loader=load_experiment_analysis_bundle_metadata,
    )
    bundle_paths = discover_experiment_analysis_bundle_paths(metadata)
    ui_payload_path = _explicit_or_default_path(
        raw_explicit_artifacts,
        role_id=ANALYSIS_UI_PAYLOAD_ROLE_ID,
        default_path=bundle_paths[ANALYSIS_UI_PAYLOAD_ARTIFACT_ID],
    )
    ui_payload = _load_json_mapping(ui_payload_path, field_name="analysis_ui_payload")
    offline_report_path = (
        None
        if not Path(bundle_paths[OFFLINE_REPORT_INDEX_ARTIFACT_ID]).resolve().exists()
        else _explicit_or_default_path(
            raw_explicit_artifacts,
            role_id=ANALYSIS_OFFLINE_REPORT_ROLE_ID,
            default_path=bundle_paths[OFFLINE_REPORT_INDEX_ARTIFACT_ID],
        )
    )
    return {
        "metadata": metadata,
        "ui_payload": ui_payload,
        "bundle_paths": bundle_paths,
        "ui_payload_path": str(ui_payload_path),
        "offline_report_path": (
            None if offline_report_path is None else str(Path(offline_report_path).resolve())
        ),
    }


def _resolve_validation_context(
    *,
    dashboard_metadata: Mapping[str, Any],
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    requested_highlight: bool,
) -> dict[str, Any]:
    metadata = _load_upstream_bundle_metadata_from_dashboard(
        dashboard_metadata=dashboard_metadata,
        dashboard_role_id=DASHBOARD_VALIDATION_BUNDLE_METADATA_ROLE_ID,
        explicit_metadata_path=raw_explicit_artifacts.get(VALIDATION_BUNDLE_METADATA_ROLE_ID, {}).get("path"),
        loader=load_validation_bundle_metadata,
    )
    bundle_paths = discover_validation_bundle_paths(metadata)
    summary_path = _explicit_or_default_path(
        raw_explicit_artifacts,
        role_id=VALIDATION_SUMMARY_ROLE_ID,
        default_path=bundle_paths[VALIDATION_SUMMARY_ARTIFACT_ID],
    )
    findings_path = _explicit_or_default_path(
        raw_explicit_artifacts,
        role_id=VALIDATION_FINDINGS_ROLE_ID,
        default_path=bundle_paths[VALIDATOR_FINDINGS_ARTIFACT_ID],
    )
    review_handoff_default = (
        None
        if not Path(bundle_paths[REVIEW_HANDOFF_ARTIFACT_ID]).resolve().exists()
        else bundle_paths[REVIEW_HANDOFF_ARTIFACT_ID]
    )
    review_handoff_path = (
        None
        if review_handoff_default is None
        else _explicit_or_default_path(
            raw_explicit_artifacts,
            role_id=VALIDATION_REVIEW_HANDOFF_ROLE_ID,
            default_path=review_handoff_default,
        )
    )
    summary = _load_json_mapping(summary_path, field_name="validation_summary")
    findings = _load_json_mapping(findings_path, field_name="validation_findings")
    review_handoff = (
        {}
        if review_handoff_path is None
        else _load_json_mapping(review_handoff_path, field_name="validation_review_handoff")
    )
    if not findings.get("validator_findings"):
        raise ValueError(
            "Showcase planning requires non-empty validation findings for the highlight guardrail."
        )
    if requested_highlight and review_handoff_path is None:
        raise ValueError(
            "Showcase planning received a nominated highlight, but the validation review_handoff artifact is unavailable."
        )
    return {
        "metadata": metadata,
        "summary": summary,
        "findings": findings,
        "review_handoff": review_handoff,
        "bundle_paths": bundle_paths,
        "summary_path": str(summary_path),
        "findings_path": str(findings_path),
        "review_handoff_path": (
            None if review_handoff_path is None else str(Path(review_handoff_path).resolve())
        ),
    }


def _resolve_suite_context(
    *,
    suite_package_metadata: Mapping[str, Any] | None,
    suite_package_metadata_path: str | Path | None,
    suite_review_summary: Mapping[str, Any] | None,
    suite_review_summary_path: str | Path | None,
    table_dimension_ids: Sequence[str] | None,
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any] | None:
    package_metadata = None
    package_metadata_path_value = None
    if suite_package_metadata is not None:
        package_metadata = load_experiment_suite_package_metadata(
            Path(str(suite_package_metadata["artifacts"]["metadata_json"]["path"])).resolve()
        )
        package_metadata_path_value = Path(
            package_metadata["artifacts"]["metadata_json"]["path"]
        ).resolve()
    elif suite_package_metadata_path is not None:
        package_metadata = load_experiment_suite_package_metadata(
            Path(suite_package_metadata_path).resolve()
        )
        package_metadata_path_value = Path(suite_package_metadata_path).resolve()

    review_summary_value = None
    if suite_review_summary is not None:
        review_summary_value = copy.deepcopy(dict(suite_review_summary))
    elif suite_review_summary_path is not None:
        review_summary_value = _load_json_mapping(
            suite_review_summary_path,
            field_name="suite_review_summary",
        )

    if package_metadata is None and review_summary_value is None:
        explicit_summary_table = _explicit_suite_artifact(
            raw_explicit_artifacts,
            role_id=SUITE_SUMMARY_TABLE_ROLE_ID,
            default_artifact_id="summary_table",
            default_section_id="shared_comparison_metrics",
        )
        explicit_comparison_plot = _explicit_suite_artifact(
            raw_explicit_artifacts,
            role_id=SUITE_COMPARISON_PLOT_ROLE_ID,
            default_artifact_id="comparison_plot",
            default_section_id="shared_comparison_metrics",
        )
        explicit_review_artifact = _explicit_suite_artifact(
            raw_explicit_artifacts,
            role_id=SUITE_REVIEW_ARTIFACT_ROLE_ID,
            default_artifact_id="review_artifact",
            default_section_id=None,
        )
        if not any(
            artifact is not None
            for artifact in (
                explicit_summary_table,
                explicit_comparison_plot,
                explicit_review_artifact,
            )
        ):
            return None
        return {
            "experiment_id": None,
            "package_metadata": None,
            "package_metadata_path": None,
            "review_summary": None,
            "suite_plan_path": None,
            "suite_plan": {},
            "artifact_catalog_path": None,
            "artifact_catalog": {},
            "summary_table_artifact": explicit_summary_table,
            "comparison_plot_artifact": explicit_comparison_plot,
            "review_artifact": explicit_review_artifact,
        }

    if review_summary_value is None:
        review_summary_value = generate_experiment_suite_review_report(
            package_metadata_path_value
            if package_metadata_path_value is not None
            else package_metadata,
            table_dimension_ids=table_dimension_ids,
        )

    suite_plan_path = Path(review_summary_value["suite_reference"]["suite_plan_path"]).resolve()
    suite_plan = _load_json_mapping(suite_plan_path, field_name="suite_plan")
    artifact_catalog_path = Path(
        review_summary_value["report_layout"]["artifact_catalog_path"]
    ).resolve()
    artifact_catalog = _load_json_mapping(
        artifact_catalog_path,
        field_name="suite_review_artifact_catalog",
    )
    summary_table_artifact = _select_suite_artifact(
        artifact_catalog.get("table_artifacts", []),
        preferred_artifact_id="shared_comparison_summary_table",
        preferred_section_id="shared_comparison_metrics",
    )
    comparison_plot_artifact = _select_suite_artifact(
        artifact_catalog.get("plot_artifacts", []),
        preferred_artifact_id=None,
        preferred_section_id="shared_comparison_metrics",
    )
    review_artifact = _select_suite_artifact(
        artifact_catalog.get("review_artifacts", []),
        preferred_artifact_id="suite_review_summary_json",
        preferred_section_id=None,
    )

    experiment_id = None
    manifest_reference = suite_plan.get("manifest_reference")
    if isinstance(manifest_reference, Mapping):
        experiment_id = str(manifest_reference.get("experiment_id", "")) or None
    return {
        "experiment_id": experiment_id,
        "package_metadata": (
            None if package_metadata is None else copy.deepcopy(dict(package_metadata))
        ),
        "package_metadata_path": (
            None if package_metadata_path_value is None else str(package_metadata_path_value)
        ),
        "review_summary": copy.deepcopy(dict(review_summary_value)),
        "suite_plan_path": str(suite_plan_path),
        "suite_plan": suite_plan,
        "artifact_catalog_path": str(artifact_catalog_path),
        "artifact_catalog": artifact_catalog,
        "summary_table_artifact": summary_table_artifact,
        "comparison_plot_artifact": comparison_plot_artifact,
        "review_artifact": review_artifact,
    }


def _explicit_suite_artifact(
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    *,
    role_id: str,
    default_artifact_id: str,
    default_section_id: str | None,
) -> dict[str, Any] | None:
    artifact = raw_explicit_artifacts.get(role_id)
    if artifact is None:
        return None
    return {
        "artifact_id": str(artifact.get("artifact_id", default_artifact_id)),
        "section_id": default_section_id,
        "path": str(Path(artifact["path"]).resolve()),
    }


def _validate_experiment_alignment(
    *,
    experiment_id: str,
    source_mode: str,
    suite_context: Mapping[str, Any] | None,
) -> None:
    if suite_context is None or suite_context.get("experiment_id") in {None, ""}:
        return
    suite_experiment_id = str(suite_context["experiment_id"])
    if suite_experiment_id != experiment_id:
        raise ValueError(
            "Showcase planning received suite evidence for experiment_id "
            f"{suite_experiment_id!r}, but the resolved dashboard session uses {experiment_id!r} "
            f"(source_mode={source_mode!r})."
        )


def _comparison_mode_status_by_id(
    replay_model: Mapping[str, Any],
    *,
    comparison_mode_id: str,
) -> dict[str, Any]:
    for item in _normalize_mapping_sequence(
        replay_model.get("comparison_mode_statuses", []),
        field_name=(
            "dashboard_session_payload.pane_inputs.time_series.replay_model."
            "comparison_mode_statuses"
        ),
    ):
        if str(item["comparison_mode_id"]) == comparison_mode_id:
            return item
    return {
        "comparison_mode_id": str(comparison_mode_id),
        "availability": "unavailable",
        "reason": "comparison_mode_statuses does not list the requested comparison mode",
    }


def _merge_explicit_artifact_overrides(
    discovered: Sequence[Mapping[str, Any]],
    *,
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    contract_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return merge_explicit_artifact_overrides(
        discovered,
        raw_explicit_artifacts=raw_explicit_artifacts,
        contract_metadata=contract_metadata,
        build_artifact_reference=build_showcase_session_artifact_reference,
        resolve_status=_showcase_override_status,
    )


def _showcase_override_status(
    role_id: str,
    raw: Mapping[str, Any],
    base: Mapping[str, Any],
    hook: Mapping[str, Any],
    resolved_path: str,
) -> str:
    del role_id, hook, resolved_path
    return str(raw.get("status", base.get("status", ASSET_STATUS_READY)))


def _discover_dashboard_metadata_from_suite_package(
    package_metadata: Mapping[str, Any],
) -> dict[str, Any] | None:
    artifacts = discover_experiment_suite_stage_artifacts(
        package_metadata,
        stage_id="dashboard",
        artifact_id="metadata_json",
    )
    if not artifacts:
        return None
    if len(artifacts) > 1:
        raise ValueError(
            "Showcase planning found multiple dashboard-session metadata artifacts in the suite package. "
            "Pass dashboard_session_metadata_path explicitly to disambiguate."
        )
    return load_dashboard_session_metadata(Path(artifacts[0]["path"]).resolve())


def _suite_bundle_id(suite_context: Mapping[str, Any]) -> str:
    package_metadata = suite_context.get("package_metadata")
    if not isinstance(package_metadata, Mapping):
        return "experiment_suite.v1:unknown:unknown"
    suite_reference = _require_mapping(
        package_metadata["suite_reference"],
        field_name="suite_package_metadata.suite_reference",
    )
    return (
        f"{EXPERIMENT_SUITE_CONTRACT_VERSION}:"
        f"{suite_reference['suite_id']}:"
        f"{suite_reference['suite_spec_hash']}"
    )


def _normalize_raw_explicit_artifact_references(
    payload: Sequence[Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if payload is None:
        return {}
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("explicit_artifact_references must be a sequence of mappings.")
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError(f"explicit_artifact_references[{index}] must be a mapping.")
        if "artifact_role_id" not in item or "path" not in item:
            raise ValueError(
                f"explicit_artifact_references[{index}] must include artifact_role_id and path."
            )
        role_id = _normalize_identifier(
            item["artifact_role_id"],
            field_name=f"explicit_artifact_references[{index}].artifact_role_id",
        )
        if role_id in result:
            raise ValueError(
                "explicit_artifact_references must not contain duplicate artifact_role_id "
                f"{role_id!r}."
            )
        result[role_id] = {
            key: copy.deepcopy(value) for key, value in dict(item).items()
        }
    return result


def _load_upstream_bundle_metadata_from_dashboard(
    *,
    dashboard_metadata: Mapping[str, Any],
    dashboard_role_id: str,
    explicit_metadata_path: str | None,
    loader: Any,
) -> dict[str, Any]:
    if explicit_metadata_path is not None:
        return loader(Path(explicit_metadata_path).resolve())
    refs = discover_dashboard_session_artifact_references(
        dashboard_metadata,
        artifact_role_id=dashboard_role_id,
    )
    if len(refs) != 1:
        raise ValueError(
            f"dashboard_session metadata must include exactly one artifact reference for {dashboard_role_id!r}."
        )
    return loader(Path(refs[0]["path"]).resolve())


def _explicit_or_default_path(
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    *,
    role_id: str,
    default_path: str | Path,
) -> Path:
    raw = raw_explicit_artifacts.get(role_id)
    if raw is None:
        return Path(default_path).resolve()
    return Path(raw["path"]).resolve()


def _select_suite_artifact(
    items: Sequence[Mapping[str, Any]],
    *,
    preferred_artifact_id: str | None,
    preferred_section_id: str | None,
) -> dict[str, Any] | None:
    normalized = _normalize_mapping_sequence(items, field_name="suite_artifacts")
    if not normalized:
        return None
    candidates = normalized
    if preferred_artifact_id is not None:
        exact = [
            dict(item)
            for item in normalized
            if str(item.get("artifact_id")) == preferred_artifact_id
        ]
        if exact:
            return exact[0]
    if preferred_section_id is not None:
        section_matches = [
            dict(item)
            for item in normalized
            if str(item.get("section_id")) == preferred_section_id
        ]
        if section_matches:
            candidates = section_matches
    candidates.sort(
        key=lambda item: (
            "" if item.get("section_id") is None else str(item["section_id"]),
            str(item["artifact_id"]),
        )
    )
    return candidates[0]


def _normalize_mapping_sequence(
    payload: Sequence[Mapping[str, Any]],
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of mappings.")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name}[{index}] must be a mapping.")
        result.append(copy.deepcopy(dict(item)))
    return result


def _load_json_mapping(path: str | Path, *, field_name: str) -> dict[str, Any]:
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise ValueError(f"{field_name} is missing required local artifact {resolved}.")
    with resolved.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must deserialize to a mapping.")
    return copy.deepcopy(dict(payload))


def _require_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return copy.deepcopy(dict(value))
