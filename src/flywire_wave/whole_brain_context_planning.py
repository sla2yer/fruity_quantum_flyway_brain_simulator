from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from .config import get_config_path, get_project_root, load_config
from .coupling_contract import (
    COUPLING_BUNDLE_CONTRACT_VERSION,
    LOCAL_SYNAPSE_REGISTRY_KEY,
    build_coupling_contract_paths,
)
from .dashboard_session_contract import (
    DASHBOARD_SESSION_CONTRACT_VERSION,
    METADATA_JSON_KEY as DASHBOARD_METADATA_JSON_KEY,
    SESSION_PAYLOAD_ARTIFACT_ID,
    SESSION_STATE_ARTIFACT_ID,
    discover_dashboard_session_bundle_paths,
    load_dashboard_session_metadata,
)
from .dashboard_session_planning import (
    package_dashboard_session,
    resolve_dashboard_session_plan,
)
from .io_utils import read_root_ids, write_json
from .manifests import load_yaml
from .registry import load_synapse_registry
from .selection import build_subset_artifact_paths
from .showcase_session_contract import (
    DASHBOARD_SESSION_METADATA_ROLE_ID as SHOWCASE_DASHBOARD_SESSION_METADATA_ROLE_ID,
    METADATA_JSON_KEY as SHOWCASE_METADATA_JSON_KEY,
    SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID,
    SHOWCASE_SESSION_CONTRACT_VERSION,
    discover_showcase_session_artifact_references,
    discover_showcase_session_bundle_paths,
    load_showcase_session_metadata,
)
from .simulator_result_contract import build_simulator_manifest_reference
from .stimulus_contract import (
    ASSET_STATUS_MISSING,
    ASSET_STATUS_READY,
    _normalize_identifier,
    _normalize_nonempty_string,
)
from .whole_brain_context_query import execute_whole_brain_context_query
from .whole_brain_context_contract import (
    ACTIVE_BOUNDARY_OVERLAY_ID,
    ACTIVE_SELECTED_NODE_ROLE_ID,
    ACTIVE_SUBSET_SHELL_QUERY_PROFILE_ID,
    ACTIVE_SUBSET_CONTEXT_LAYER_ID,
    ASSET_STATUS_READY as CONTEXT_ASSET_STATUS_READY,
    BALANCED_NEIGHBORHOOD_REDUCTION_PROFILE_ID,
    BIDIRECTIONAL_CONTEXT_GRAPH_OVERLAY_ID,
    BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
    CONTEXT_QUERY_CATALOG_ARTIFACT_ID,
    CONTEXT_QUERY_CATALOG_ROLE_ID,
    CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID,
    CONTEXT_VIEW_PAYLOAD_ROLE_ID,
    CONTEXT_VIEW_STATE_ARTIFACT_ID,
    CONTEXT_VIEW_STATE_ROLE_ID,
    DASHBOARD_CONTEXT_SCOPE,
    DASHBOARD_SESSION_METADATA_ROLE_ID,
    DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
    DASHBOARD_SESSION_SOURCE_KIND,
    DASHBOARD_SESSION_STATE_ROLE_ID,
    DEFAULT_DELIVERY_MODEL,
    DEFAULT_WHOLE_BRAIN_CONTEXT_SESSION_DIRECTORY_NAME,
    DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
    DOWNSTREAM_GRAPH_OVERLAY_ID,
    DOWNSTREAM_MODULE_COLLAPSED_REDUCTION_PROFILE_ID,
    DOWNSTREAM_MODULE_OVERLAY_ID,
    DOWNSTREAM_MODULE_REVIEW_QUERY_PROFILE_ID,
    DOWNSTREAM_MODULE_REVIEW_QUERY_FAMILY,
    JSON_CONTEXT_QUERY_CATALOG_FORMAT,
    JSON_CONTEXT_VIEW_PAYLOAD_FORMAT,
    JSON_CONTEXT_VIEW_STATE_FORMAT,
    LOCAL_CONNECTIVITY_SCOPE,
    LOCAL_CONNECTIVITY_SOURCE_KIND,
    METADATA_FACET_BADGES_OVERLAY_ID,
    METADATA_JSON_KEY,
    NODE_METADATA_FACET_SCOPE,
    PATHWAY_FOCUS_REDUCTION_PROFILE_ID,
    PATHWAY_HIGHLIGHT_OVERLAY_ID,
    PATHWAY_HIGHLIGHT_REVIEW_QUERY_PROFILE_ID,
    SELECTED_ROOT_IDS_ROLE_ID,
    SHOWCASE_CONTEXT_SCOPE,
    SHOWCASE_PRESENTATION_STATE_ROLE_ID,
    SHOWCASE_SESSION_METADATA_ROLE_ID,
    SHOWCASE_SESSION_SOURCE_KIND,
    SIMPLIFIED_READOUT_MODULE_ROLE_ID,
    SUBSET_MANIFEST_ROLE_ID,
    SUBSET_SELECTION_SCOPE,
    SUBSET_SELECTION_SOURCE_KIND,
    SUBSET_STATS_ROLE_ID,
    SYNAPSE_REGISTRY_ROLE_ID,
    UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
    UPSTREAM_GRAPH_OVERLAY_ID,
    WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
    WHOLE_BRAIN_CONTEXT_SESSION_METADATA_ROLE_ID,
    build_whole_brain_context_artifact_reference,
    build_whole_brain_context_contract_metadata,
    build_whole_brain_context_node_record,
    build_whole_brain_context_query_state,
    build_whole_brain_context_session_metadata,
    discover_whole_brain_context_metadata_facets,
    discover_whole_brain_context_query_profiles,
    discover_whole_brain_context_session_bundle_paths,
    write_whole_brain_context_session_metadata,
)


WHOLE_BRAIN_CONTEXT_SESSION_PLAN_VERSION = "whole_brain_context_session_plan.v1"
WHOLE_BRAIN_CONTEXT_SOURCE_MODE_MANIFEST = "manifest"
WHOLE_BRAIN_CONTEXT_SOURCE_MODE_SUBSET = "subset"
WHOLE_BRAIN_CONTEXT_SOURCE_MODE_DASHBOARD = "dashboard_session"
WHOLE_BRAIN_CONTEXT_SOURCE_MODE_SHOWCASE = "showcase_session"
WHOLE_BRAIN_CONTEXT_SOURCE_MODE_EXPLICIT = "explicit_artifact_inputs"

WHOLE_BRAIN_CONTEXT_FIXTURE_MODE_REVIEW = "milestone17_whole_brain_review"
SUPPORTED_WHOLE_BRAIN_CONTEXT_FIXTURE_MODES = (
    WHOLE_BRAIN_CONTEXT_FIXTURE_MODE_REVIEW,
)
DEFAULT_WHOLE_BRAIN_CONTEXT_FIXTURE_MODE = WHOLE_BRAIN_CONTEXT_FIXTURE_MODE_REVIEW
DEFAULT_CONTEXT_QUERY_PRESET_LIBRARY_ID = "milestone17_review_query_preset_library.v1"

OVERVIEW_CONTEXT_PRESET_ID = "overview_context"
UPSTREAM_HALO_PRESET_ID = "upstream_halo"
DOWNSTREAM_HALO_PRESET_ID = "downstream_halo"
PATHWAY_FOCUS_PRESET_ID = "pathway_focus"
DASHBOARD_HANDOFF_PRESET_ID = "dashboard_handoff"
SHOWCASE_HANDOFF_PRESET_ID = "showcase_handoff"

SUPPORTED_CONTEXT_QUERY_PRESET_IDS = (
    OVERVIEW_CONTEXT_PRESET_ID,
    UPSTREAM_HALO_PRESET_ID,
    DOWNSTREAM_HALO_PRESET_ID,
    PATHWAY_FOCUS_PRESET_ID,
    DASHBOARD_HANDOFF_PRESET_ID,
    SHOWCASE_HANDOFF_PRESET_ID,
)

_ACTIVE_QUERY_PRIORITY = (
    BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
    DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
    UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
    ACTIVE_SUBSET_SHELL_QUERY_PROFILE_ID,
    PATHWAY_HIGHLIGHT_REVIEW_QUERY_PROFILE_ID,
    DOWNSTREAM_MODULE_REVIEW_QUERY_PROFILE_ID,
)
_REVIEW_ONLY_QUERY_PROFILE_IDS = {
    PATHWAY_HIGHLIGHT_REVIEW_QUERY_PROFILE_ID,
    DOWNSTREAM_MODULE_REVIEW_QUERY_PROFILE_ID,
}
_SUPPORTED_PRIMARY_SOURCE_MODES = (
    WHOLE_BRAIN_CONTEXT_SOURCE_MODE_MANIFEST,
    WHOLE_BRAIN_CONTEXT_SOURCE_MODE_SUBSET,
    WHOLE_BRAIN_CONTEXT_SOURCE_MODE_DASHBOARD,
    WHOLE_BRAIN_CONTEXT_SOURCE_MODE_SHOWCASE,
    WHOLE_BRAIN_CONTEXT_SOURCE_MODE_EXPLICIT,
)


def resolve_manifest_whole_brain_context_session_plan(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    **overrides: Any,
) -> dict[str, Any]:
    return resolve_whole_brain_context_session_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        **overrides,
    )


def resolve_whole_brain_context_session_plan(
    *,
    config_path: str | Path,
    manifest_path: str | Path | None = None,
    schema_path: str | Path | None = None,
    design_lock_path: str | Path | None = None,
    subset_name: str | None = None,
    selection_preset: str | None = None,
    subset_manifest_path: str | Path | None = None,
    dashboard_session_metadata: Mapping[str, Any] | None = None,
    dashboard_session_metadata_path: str | Path | None = None,
    showcase_session_metadata: Mapping[str, Any] | None = None,
    showcase_session_metadata_path: str | Path | None = None,
    explicit_artifact_references: Sequence[Mapping[str, Any]] | None = None,
    experiment_id: str | None = None,
    query_profile_id: str | None = None,
    query_profile_ids: Sequence[str] | None = None,
    fixture_mode: str | None = None,
    default_overlay_id: str | None = None,
    reduction_profile_id: str | None = None,
    enabled_overlay_ids: Sequence[str] | None = None,
    enabled_metadata_facet_ids: Sequence[str] | None = None,
    requested_downstream_module_role_ids: Sequence[str] | None = None,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = load_config(config_path)
    config_file = get_config_path(cfg)
    project_root = get_project_root(cfg)
    if config_file is None or project_root is None:
        raise ValueError("Loaded config is missing config metadata.")

    normalized_contract = copy.deepcopy(
        dict(
            build_whole_brain_context_contract_metadata()
            if contract_metadata is None
            else contract_metadata
        )
    )
    raw_explicit_artifacts = _normalize_raw_explicit_artifact_references(
        explicit_artifact_references
    )
    source_mode = _resolve_source_mode(
        cfg=cfg,
        manifest_path=manifest_path,
        subset_name=subset_name,
        selection_preset=selection_preset,
        subset_manifest_path=subset_manifest_path,
        dashboard_session_metadata=dashboard_session_metadata,
        dashboard_session_metadata_path=dashboard_session_metadata_path,
        showcase_session_metadata=showcase_session_metadata,
        showcase_session_metadata_path=showcase_session_metadata_path,
        raw_explicit_artifacts=raw_explicit_artifacts,
    )
    source_context = _resolve_source_context(
        cfg=cfg,
        config_path=config_path,
        source_mode=source_mode,
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        subset_name=subset_name,
        selection_preset=selection_preset,
        subset_manifest_path=subset_manifest_path,
        dashboard_session_metadata=dashboard_session_metadata,
        dashboard_session_metadata_path=dashboard_session_metadata_path,
        showcase_session_metadata=showcase_session_metadata,
        showcase_session_metadata_path=showcase_session_metadata_path,
        raw_explicit_artifacts=raw_explicit_artifacts,
        experiment_id=experiment_id,
    )
    discovered_artifact_references = _build_discovered_artifact_references(
        source_context=source_context,
    )
    merged_artifact_references = _merge_explicit_artifact_overrides(
        discovered_artifact_references,
        raw_explicit_artifacts=raw_explicit_artifacts,
        contract_metadata=normalized_contract,
    )
    planned_artifact_paths = _planned_artifact_paths(source_context)
    artifact_references_by_role = {
        str(item["artifact_role_id"]): copy.deepcopy(dict(item))
        for item in merged_artifact_references
    }
    _validate_resolved_artifact_alignment(
        selection_context=source_context["selection_context"],
        source_context=source_context,
        artifact_references_by_role=artifact_references_by_role,
        raw_explicit_artifacts=raw_explicit_artifacts,
        planned_artifact_paths=planned_artifact_paths,
    )
    resolved_selection_context = _apply_artifact_overrides_to_selection_context(
        source_context["selection_context"],
        artifact_references_by_role=artifact_references_by_role,
    )
    registry_sources = _build_registry_sources(
        selection_context=resolved_selection_context,
        artifact_references_by_role=artifact_references_by_role,
        planned_artifact_paths=planned_artifact_paths,
    )
    query_profile_resolution = _resolve_query_profile_selection(
        contract_metadata=normalized_contract,
        artifact_references_by_role=artifact_references_by_role,
        planned_artifact_paths=planned_artifact_paths,
        requested_active_query_profile_id=query_profile_id,
        requested_query_profile_ids=query_profile_ids,
    )
    query_state = build_whole_brain_context_query_state(
        query_profile_id=query_profile_resolution["active_query_profile_id"],
        default_overlay_id=default_overlay_id,
        default_reduction_profile_id=reduction_profile_id,
        enabled_overlay_ids=enabled_overlay_ids,
        enabled_metadata_facet_ids=enabled_metadata_facet_ids,
        contract_metadata=normalized_contract,
    )
    reduction_profile = _catalog_item_by_id(
        normalized_contract["reduction_profile_catalog"],
        key_name="reduction_profile_id",
        identifier=query_state["default_reduction_profile_id"],
    )
    metadata_facet_requests = _build_metadata_facet_requests(
        contract_metadata=normalized_contract,
        query_state=query_state,
    )
    downstream_module_requests = _resolve_downstream_module_requests(
        contract_metadata=normalized_contract,
        requested_downstream_module_role_ids=requested_downstream_module_role_ids,
        selected_query_profile_ids=query_profile_resolution["selected_query_profile_ids"],
        active_query_profile_id=query_profile_resolution["active_query_profile_id"],
    )
    labeling_rules = _build_labeling_rules(
        selected_root_ids=resolved_selection_context["selected_root_ids"],
    )
    query_execution = execute_whole_brain_context_query(
        _build_query_execution_input(
            config_path=str(config_file.resolve()),
            selection_context=resolved_selection_context,
            registry_sources=registry_sources,
            query_profile_resolution=query_profile_resolution,
            query_state=query_state,
            reduction_profile=reduction_profile,
            metadata_facet_requests=metadata_facet_requests,
            downstream_module_requests=downstream_module_requests,
        )
    )
    representative_context = copy.deepcopy(dict(query_execution["representative_context"]))
    whole_brain_context_session = build_whole_brain_context_session_metadata(
        experiment_id=source_context["experiment_id"],
        artifact_references=merged_artifact_references,
        representative_context=representative_context,
        query_state=query_state,
        processed_simulator_results_dir=cfg["paths"]["processed_simulator_results_dir"],
        delivery_model=DEFAULT_DELIVERY_MODEL,
        context_view_payload_status=CONTEXT_ASSET_STATUS_READY,
        context_query_catalog_status=CONTEXT_ASSET_STATUS_READY,
        context_view_state_status=CONTEXT_ASSET_STATUS_READY,
        contract_metadata=normalized_contract,
    )
    linked_sessions = _build_linked_sessions(
        source_context=source_context,
        artifact_references_by_role=artifact_references_by_role,
        planned_artifact_paths=planned_artifact_paths,
    )
    fixture_profile = _build_fixture_profile(
        source_mode=source_mode,
        requested_fixture_mode=fixture_mode,
        linked_sessions=linked_sessions,
    )
    query_preset_library = _build_query_preset_library(
        config_path=str(config_file.resolve()),
        contract_metadata=normalized_contract,
        selection_context=resolved_selection_context,
        registry_sources=registry_sources,
        query_profile_resolution=query_profile_resolution,
        query_state=query_state,
        reduction_profile=reduction_profile,
        metadata_facet_requests=metadata_facet_requests,
        downstream_module_requests=downstream_module_requests,
        linked_sessions=linked_sessions,
        fixture_profile=fixture_profile,
    )
    output_locations = _build_output_locations(whole_brain_context_session)
    context_query_catalog = _build_context_query_catalog(
        whole_brain_context_session=whole_brain_context_session,
        source_mode=source_mode,
        fixture_profile=fixture_profile,
        query_profile_resolution=query_profile_resolution,
        query_state=query_state,
        reduction_profile=reduction_profile,
        metadata_facet_requests=metadata_facet_requests,
        downstream_module_requests=downstream_module_requests,
        query_execution=query_execution,
        query_preset_library=query_preset_library,
    )
    context_view_payload = _build_context_view_payload(
        whole_brain_context_session=whole_brain_context_session,
        source_mode=source_mode,
        fixture_profile=fixture_profile,
        manifest_reference=source_context["manifest_reference"],
        selection_context=resolved_selection_context,
        registry_sources=registry_sources,
        linked_sessions=linked_sessions,
        query_profile_resolution=query_profile_resolution,
        query_state=query_state,
        reduction_profile=reduction_profile,
        metadata_facet_requests=metadata_facet_requests,
        downstream_module_requests=downstream_module_requests,
        labeling_rules=labeling_rules,
        query_execution=query_execution,
        query_preset_library=query_preset_library,
    )
    context_view_state = _build_context_view_state(
        whole_brain_context_session=whole_brain_context_session,
        fixture_profile=fixture_profile,
        manifest_reference=source_context["manifest_reference"],
        selection_context=resolved_selection_context,
        linked_sessions=linked_sessions,
        query_profile_resolution=query_profile_resolution,
        query_state=query_state,
        query_preset_library=query_preset_library,
    )
    return {
        "plan_version": WHOLE_BRAIN_CONTEXT_SESSION_PLAN_VERSION,
        "source_mode": source_mode,
        "fixture_mode": str(fixture_profile["fixture_mode"]),
        "config_path": str(config_file.resolve()),
        "project_root": str(project_root.resolve()),
        "experiment_id": source_context["experiment_id"],
        "manifest_reference": copy.deepcopy(source_context["manifest_reference"]),
        "selection": copy.deepcopy(resolved_selection_context),
        "registry_sources": copy.deepcopy(registry_sources),
        "linked_sessions": copy.deepcopy(linked_sessions),
        "fixture_profile": copy.deepcopy(fixture_profile),
        "query_profile_resolution": copy.deepcopy(query_profile_resolution),
        "query_state": copy.deepcopy(query_state),
        "reduction_profile": copy.deepcopy(reduction_profile),
        "metadata_facet_requests": copy.deepcopy(metadata_facet_requests),
        "downstream_module_requests": copy.deepcopy(downstream_module_requests),
        "labeling_rules": copy.deepcopy(labeling_rules),
        "query_execution": copy.deepcopy(query_execution),
        "query_preset_library": copy.deepcopy(query_preset_library),
        "upstream_artifact_references": copy.deepcopy(merged_artifact_references),
        "whole_brain_context_session": copy.deepcopy(whole_brain_context_session),
        "context_view_payload": copy.deepcopy(context_view_payload),
        "context_query_catalog": copy.deepcopy(context_query_catalog),
        "context_view_state": copy.deepcopy(context_view_state),
        "output_locations": copy.deepcopy(output_locations),
        "dashboard_session_plan": copy.deepcopy(source_context.get("dashboard_session_plan")),
        "source_notes": copy.deepcopy(source_context.get("source_notes", {})),
    }


def package_whole_brain_context_session(plan: Mapping[str, Any]) -> dict[str, Any]:
    normalized_plan = _require_mapping(plan, field_name="plan")
    if str(normalized_plan.get("plan_version")) != WHOLE_BRAIN_CONTEXT_SESSION_PLAN_VERSION:
        raise ValueError(
            f"plan.plan_version must be {WHOLE_BRAIN_CONTEXT_SESSION_PLAN_VERSION!r}."
        )
    dashboard_plan = normalized_plan.get("dashboard_session_plan")
    linked_dashboard_package = None
    planned_dashboard_paths = _planned_artifact_paths(normalized_plan).get(
        DASHBOARD_SESSION_METADATA_ROLE_ID
    )
    linked_dashboard_ref = _artifact_reference_by_role(
        normalized_plan["upstream_artifact_references"],
        DASHBOARD_SESSION_METADATA_ROLE_ID,
    )
    if (
        isinstance(dashboard_plan, Mapping)
        and planned_dashboard_paths is not None
        and linked_dashboard_ref is not None
        and str(Path(linked_dashboard_ref["path"]).resolve())
        == str(Path(planned_dashboard_paths).resolve())
    ):
        linked_dashboard_package = package_dashboard_session(dashboard_plan)

    whole_brain_context_session = _require_mapping(
        normalized_plan.get("whole_brain_context_session"),
        field_name="plan.whole_brain_context_session",
    )
    context_view_payload = _require_mapping(
        normalized_plan.get("context_view_payload"),
        field_name="plan.context_view_payload",
    )
    context_query_catalog = _require_mapping(
        normalized_plan.get("context_query_catalog"),
        field_name="plan.context_query_catalog",
    )
    context_view_state = _require_mapping(
        normalized_plan.get("context_view_state"),
        field_name="plan.context_view_state",
    )

    metadata_path = write_whole_brain_context_session_metadata(whole_brain_context_session)
    bundle_paths = discover_whole_brain_context_session_bundle_paths(
        whole_brain_context_session
    )
    write_json(context_view_payload, bundle_paths[CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID])
    write_json(context_query_catalog, bundle_paths[CONTEXT_QUERY_CATALOG_ARTIFACT_ID])
    write_json(context_view_state, bundle_paths[CONTEXT_VIEW_STATE_ARTIFACT_ID])

    linked_dashboard_metadata_path = None
    if linked_dashboard_package is not None:
        linked_dashboard_metadata_path = str(
            Path(linked_dashboard_package["metadata_path"]).resolve()
        )
    elif linked_dashboard_ref is not None:
        linked_dashboard_metadata_path = str(Path(linked_dashboard_ref["path"]).resolve())

    linked_showcase_ref = _artifact_reference_by_role(
        normalized_plan["upstream_artifact_references"],
        SHOWCASE_SESSION_METADATA_ROLE_ID,
    )
    return {
        "bundle_id": str(whole_brain_context_session["bundle_id"]),
        "metadata_path": str(metadata_path.resolve()),
        "context_view_payload_path": str(
            bundle_paths[CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID].resolve()
        ),
        "context_query_catalog_path": str(
            bundle_paths[CONTEXT_QUERY_CATALOG_ARTIFACT_ID].resolve()
        ),
        "context_view_state_path": str(
            bundle_paths[CONTEXT_VIEW_STATE_ARTIFACT_ID].resolve()
        ),
        "bundle_directory": str(
            Path(whole_brain_context_session["bundle_layout"]["bundle_directory"]).resolve()
        ),
        "linked_dashboard_metadata_path": linked_dashboard_metadata_path,
        "linked_showcase_metadata_path": (
            None
            if linked_showcase_ref is None
            else str(Path(linked_showcase_ref["path"]).resolve())
        ),
        "output_locations": copy.deepcopy(dict(normalized_plan["output_locations"])),
    }


def discover_whole_brain_context_query_presets(
    record: Mapping[str, Any],
    *,
    availability: str | None = "available",
) -> list[dict[str, Any]]:
    catalog = _extract_context_query_catalog_mapping(record)
    if availability is None:
        normalized_availability = None
    else:
        normalized_availability = _normalize_identifier(
            availability,
            field_name="availability",
        )
        if normalized_availability not in {"available", "unavailable"}:
            raise ValueError("availability must be 'available', 'unavailable', or None.")
    available_presets = {
        str(item["preset_id"]): copy.deepcopy(dict(item))
        for item in catalog.get("available_query_presets", [])
        if isinstance(item, Mapping)
    }
    unavailable_presets = {
        str(item["preset_id"]): copy.deepcopy(dict(item))
        for item in catalog.get("unavailable_query_presets", [])
        if isinstance(item, Mapping)
    }
    discovery_order = list(
        catalog.get("preset_discovery_order", SUPPORTED_CONTEXT_QUERY_PRESET_IDS)
    )
    discovered: list[dict[str, Any]] = []
    for preset_id in discovery_order:
        if normalized_availability in {None, "available"} and preset_id in available_presets:
            discovered.append(copy.deepcopy(available_presets[preset_id]))
        if (
            normalized_availability in {None, "unavailable"}
            and preset_id in unavailable_presets
        ):
            discovered.append(copy.deepcopy(unavailable_presets[preset_id]))
    return discovered


def _resolve_source_mode(
    *,
    cfg: Mapping[str, Any],
    manifest_path: str | Path | None,
    subset_name: str | None,
    selection_preset: str | None,
    subset_manifest_path: str | Path | None,
    dashboard_session_metadata: Mapping[str, Any] | None,
    dashboard_session_metadata_path: str | Path | None,
    showcase_session_metadata: Mapping[str, Any] | None,
    showcase_session_metadata_path: str | Path | None,
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
) -> str:
    subset_requested = any(
        item is not None for item in (subset_name, selection_preset, subset_manifest_path)
    )
    dashboard_requested = (
        dashboard_session_metadata is not None or dashboard_session_metadata_path is not None
    )
    showcase_requested = (
        showcase_session_metadata is not None or showcase_session_metadata_path is not None
    )
    primary_sources = [
        mode
        for mode, enabled in (
            (WHOLE_BRAIN_CONTEXT_SOURCE_MODE_MANIFEST, manifest_path is not None),
            (WHOLE_BRAIN_CONTEXT_SOURCE_MODE_SUBSET, subset_requested),
            (WHOLE_BRAIN_CONTEXT_SOURCE_MODE_DASHBOARD, dashboard_requested),
            (WHOLE_BRAIN_CONTEXT_SOURCE_MODE_SHOWCASE, showcase_requested),
        )
        if enabled
    ]
    if len(primary_sources) > 1:
        raise ValueError(
            "Whole-brain context planning requires exactly one primary source input, "
            f"got {primary_sources!r}."
        )
    if primary_sources:
        return primary_sources[0]
    if raw_explicit_artifacts:
        return WHOLE_BRAIN_CONTEXT_SOURCE_MODE_EXPLICIT
    active_preset = _normalize_optional_identifier(
        cfg.get("selection", {}).get("active_preset"),
        field_name="config.selection.active_preset",
    )
    if active_preset is not None:
        return WHOLE_BRAIN_CONTEXT_SOURCE_MODE_SUBSET
    raise ValueError(
        "Whole-brain context planning requires one of manifest_path, subset_name, "
        "dashboard_session_metadata_path, showcase_session_metadata_path, or "
        "explicit_artifact_references."
    )


def _resolve_source_context(
    *,
    cfg: Mapping[str, Any],
    config_path: str | Path,
    source_mode: str,
    manifest_path: str | Path | None,
    schema_path: str | Path | None,
    design_lock_path: str | Path | None,
    subset_name: str | None,
    selection_preset: str | None,
    subset_manifest_path: str | Path | None,
    dashboard_session_metadata: Mapping[str, Any] | None,
    dashboard_session_metadata_path: str | Path | None,
    showcase_session_metadata: Mapping[str, Any] | None,
    showcase_session_metadata_path: str | Path | None,
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    experiment_id: str | None,
) -> dict[str, Any]:
    if source_mode == WHOLE_BRAIN_CONTEXT_SOURCE_MODE_MANIFEST:
        return _resolve_manifest_source_context(
            cfg=cfg,
            config_path=config_path,
            manifest_path=_require_nonempty_path(manifest_path, field_name="manifest_path"),
            schema_path=schema_path,
            design_lock_path=design_lock_path,
        )
    if source_mode == WHOLE_BRAIN_CONTEXT_SOURCE_MODE_SUBSET:
        return _resolve_subset_source_context(
            cfg=cfg,
            subset_name=subset_name,
            selection_preset=selection_preset,
            subset_manifest_path=subset_manifest_path,
            experiment_id=experiment_id,
        )
    if source_mode == WHOLE_BRAIN_CONTEXT_SOURCE_MODE_DASHBOARD:
        return _resolve_dashboard_source_context(
            cfg=cfg,
            dashboard_session_metadata=dashboard_session_metadata,
            dashboard_session_metadata_path=dashboard_session_metadata_path,
        )
    if source_mode == WHOLE_BRAIN_CONTEXT_SOURCE_MODE_SHOWCASE:
        return _resolve_showcase_source_context(
            cfg=cfg,
            showcase_session_metadata=showcase_session_metadata,
            showcase_session_metadata_path=showcase_session_metadata_path,
        )
    if source_mode == WHOLE_BRAIN_CONTEXT_SOURCE_MODE_EXPLICIT:
        return _resolve_explicit_source_context(
            cfg=cfg,
            raw_explicit_artifacts=raw_explicit_artifacts,
            experiment_id=experiment_id,
        )
    raise ValueError(f"Unsupported whole-brain context source mode {source_mode!r}.")


def _resolve_manifest_source_context(
    *,
    cfg: Mapping[str, Any],
    config_path: str | Path,
    manifest_path: str | Path,
    schema_path: str | Path | None,
    design_lock_path: str | Path | None,
) -> dict[str, Any]:
    manifest_file = Path(manifest_path).resolve()
    manifest_payload = load_yaml(manifest_file)
    manifest_reference = _build_manifest_reference(manifest_file, manifest_payload)
    selection_context = _resolve_selection_from_manifest_payload(
        cfg=cfg,
        manifest_path=manifest_file,
        manifest_payload=manifest_payload,
    )
    dashboard_session_plan = None
    dashboard_context = None
    source_notes: dict[str, Any] = {}
    if schema_path is not None and design_lock_path is not None:
        try:
            dashboard_session_plan = resolve_dashboard_session_plan(
                manifest_path=manifest_file,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
            )
            dashboard_context = _planned_dashboard_context(dashboard_session_plan)
        except (FileNotFoundError, ValueError) as exc:
            source_notes["dashboard_resolution_unavailable_reason"] = str(exc)
    elif manifest_payload.get("experiment_id") is not None:
        source_notes["dashboard_resolution_unavailable_reason"] = (
            "Manifest source did not receive schema_path and design_lock_path, so "
            "no linked dashboard session was planned."
        )
    return {
        "source_mode": WHOLE_BRAIN_CONTEXT_SOURCE_MODE_MANIFEST,
        "experiment_id": str(manifest_reference["experiment_id"]),
        "manifest_reference": manifest_reference,
        "selection_context": selection_context,
        "dashboard_context": dashboard_context,
        "dashboard_session_plan": dashboard_session_plan,
        "showcase_context": None,
        "synapse_registry_path": str(
            build_coupling_contract_paths(cfg["paths"]["processed_coupling_dir"]).local_synapse_registry_path
        ),
        "source_notes": source_notes,
    }


def _resolve_subset_source_context(
    *,
    cfg: Mapping[str, Any],
    subset_name: str | None,
    selection_preset: str | None,
    subset_manifest_path: str | Path | None,
    experiment_id: str | None,
) -> dict[str, Any]:
    resolved_subset_name = (
        _normalize_optional_identifier(subset_name, field_name="subset_name")
        or _normalize_optional_identifier(
            selection_preset,
            field_name="selection_preset",
        )
        or _normalize_optional_identifier(
            cfg.get("selection", {}).get("active_preset"),
            field_name="config.selection.active_preset",
        )
    )
    if resolved_subset_name is None and subset_manifest_path is None:
        raise ValueError(
            "Subset-driven whole-brain context planning requires subset_name, "
            "selection_preset, subset_manifest_path, or config.selection.active_preset."
        )
    if subset_manifest_path is not None and resolved_subset_name is None:
        resolved_subset_name = _normalize_identifier(
            Path(subset_manifest_path).resolve().parent.name,
            field_name="subset_manifest_path.parent",
        )
    subset_artifact_paths = build_subset_artifact_paths(
        cfg["paths"]["subset_output_dir"],
        _require_nonempty_string(resolved_subset_name, field_name="subset_name"),
    )
    selection_context = _resolve_selection_context(
        selected_root_ids_path=subset_artifact_paths.root_ids,
        subset_name=resolved_subset_name,
        circuit_name=None,
        selection_preset=_normalize_optional_identifier(
            cfg.get("selection", {}).get("active_preset"),
            field_name="config.selection.active_preset",
        ),
        subset_manifest_path=(
            Path(subset_manifest_path).resolve()
            if subset_manifest_path is not None
            else subset_artifact_paths.manifest_json.resolve()
        ),
        subset_stats_path=subset_artifact_paths.stats_json.resolve(),
    )
    resolved_experiment_id = (
        _normalize_optional_identifier(experiment_id, field_name="experiment_id")
        or f"subset_context_{resolved_subset_name}"
    )
    return {
        "source_mode": WHOLE_BRAIN_CONTEXT_SOURCE_MODE_SUBSET,
        "experiment_id": resolved_experiment_id,
        "manifest_reference": None,
        "selection_context": selection_context,
        "dashboard_context": None,
        "dashboard_session_plan": None,
        "showcase_context": None,
        "synapse_registry_path": str(
            build_coupling_contract_paths(cfg["paths"]["processed_coupling_dir"]).local_synapse_registry_path
        ),
        "source_notes": {},
    }


def _resolve_dashboard_source_context(
    *,
    cfg: Mapping[str, Any],
    dashboard_session_metadata: Mapping[str, Any] | None,
    dashboard_session_metadata_path: str | Path | None,
) -> dict[str, Any]:
    metadata = (
        load_dashboard_session_metadata(dashboard_session_metadata_path)
        if dashboard_session_metadata_path is not None
        else _load_dashboard_metadata_from_mapping(dashboard_session_metadata)
    )
    dashboard_context = _packaged_dashboard_context(metadata)
    manifest_reference = copy.deepcopy(dict(metadata["manifest_reference"]))
    manifest_path = Path(str(manifest_reference["manifest_path"])).resolve()
    selection_context = _resolve_selection_from_manifest_payload(
        cfg=cfg,
        manifest_path=manifest_path,
        manifest_payload=load_yaml(manifest_path),
    )
    dashboard_selected_root_ids = _dashboard_selected_root_ids(dashboard_context["payload"])
    if dashboard_selected_root_ids != selection_context["selected_root_ids"]:
        raise ValueError(
            "Dashboard session selected_root_ids do not match the locally resolved "
            f"active subset: {dashboard_selected_root_ids!r} != "
            f"{selection_context['selected_root_ids']!r}."
        )
    return {
        "source_mode": WHOLE_BRAIN_CONTEXT_SOURCE_MODE_DASHBOARD,
        "experiment_id": str(metadata["experiment_id"]),
        "manifest_reference": manifest_reference,
        "selection_context": selection_context,
        "dashboard_context": dashboard_context,
        "dashboard_session_plan": None,
        "showcase_context": None,
        "synapse_registry_path": str(
            dashboard_context["payload"]["selection"]["local_synapse_registry_path"]
        ),
        "source_notes": {},
    }


def _resolve_showcase_source_context(
    *,
    cfg: Mapping[str, Any],
    showcase_session_metadata: Mapping[str, Any] | None,
    showcase_session_metadata_path: str | Path | None,
) -> dict[str, Any]:
    metadata = (
        load_showcase_session_metadata(showcase_session_metadata_path)
        if showcase_session_metadata_path is not None
        else _load_showcase_metadata_from_mapping(showcase_session_metadata)
    )
    showcase_context = _packaged_showcase_context(metadata)
    dashboard_refs = discover_showcase_session_artifact_references(
        metadata,
        artifact_role_id=SHOWCASE_DASHBOARD_SESSION_METADATA_ROLE_ID,
    )
    if len(dashboard_refs) != 1:
        raise ValueError(
            "Showcase session selected subset cannot be traced back to local context "
            "inputs because it does not expose exactly one dashboard-session "
            "metadata reference."
        )
    dashboard_metadata = load_dashboard_session_metadata(
        Path(dashboard_refs[0]["path"]).resolve()
    )
    dashboard_context = _packaged_dashboard_context(dashboard_metadata)
    manifest_reference = copy.deepcopy(dict(dashboard_metadata["manifest_reference"]))
    manifest_path = Path(str(manifest_reference["manifest_path"])).resolve()
    selection_context = _resolve_selection_from_manifest_payload(
        cfg=cfg,
        manifest_path=manifest_path,
        manifest_payload=load_yaml(manifest_path),
    )
    dashboard_selected_root_ids = _dashboard_selected_root_ids(dashboard_context["payload"])
    if dashboard_selected_root_ids != selection_context["selected_root_ids"]:
        raise ValueError(
            "Showcase-linked dashboard session selected_root_ids do not match the "
            "locally resolved active subset."
        )
    showcase_focus_root_ids = _showcase_focus_root_ids(showcase_context["state"])
    selected_root_ids = {int(root_id) for root_id in selection_context["selected_root_ids"]}
    unexpected_focus_root_ids = sorted(
        set(showcase_focus_root_ids) - selected_root_ids
    )
    if unexpected_focus_root_ids:
        raise ValueError(
            "Showcase session focus_root_ids include roots outside the locally "
            f"resolved active subset: {unexpected_focus_root_ids!r}."
        )
    return {
        "source_mode": WHOLE_BRAIN_CONTEXT_SOURCE_MODE_SHOWCASE,
        "experiment_id": str(metadata["experiment_id"]),
        "manifest_reference": manifest_reference,
        "selection_context": selection_context,
        "dashboard_context": dashboard_context,
        "dashboard_session_plan": None,
        "showcase_context": showcase_context,
        "synapse_registry_path": str(
            dashboard_context["payload"]["selection"]["local_synapse_registry_path"]
        ),
        "source_notes": {},
    }


def _resolve_explicit_source_context(
    *,
    cfg: Mapping[str, Any],
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    experiment_id: str | None,
) -> dict[str, Any]:
    if SHOWCASE_SESSION_METADATA_ROLE_ID in raw_explicit_artifacts:
        return _resolve_showcase_source_context(
            cfg=cfg,
            showcase_session_metadata=None,
            showcase_session_metadata_path=raw_explicit_artifacts[
                SHOWCASE_SESSION_METADATA_ROLE_ID
            ]["path"],
        )
    if DASHBOARD_SESSION_METADATA_ROLE_ID in raw_explicit_artifacts:
        return _resolve_dashboard_source_context(
            cfg=cfg,
            dashboard_session_metadata=None,
            dashboard_session_metadata_path=raw_explicit_artifacts[
                DASHBOARD_SESSION_METADATA_ROLE_ID
            ]["path"],
        )
    selected_root_ids_ref = raw_explicit_artifacts.get(SELECTED_ROOT_IDS_ROLE_ID)
    subset_manifest_ref = raw_explicit_artifacts.get(SUBSET_MANIFEST_ROLE_ID)
    subset_stats_ref = raw_explicit_artifacts.get(SUBSET_STATS_ROLE_ID)
    if selected_root_ids_ref is None:
        raise ValueError(
            "Explicit whole-brain context planning requires a selected_root_ids "
            "artifact reference to resolve the active subset."
        )
    subset_name = (
        None
        if subset_manifest_ref is None
        else _normalize_identifier(
            Path(subset_manifest_ref["path"]).resolve().parent.name,
            field_name="subset_manifest_path.parent",
        )
    )
    selection_context = _resolve_selection_context(
        selected_root_ids_path=Path(selected_root_ids_ref["path"]).resolve(),
        subset_name=subset_name,
        circuit_name=None,
        selection_preset=None,
        subset_manifest_path=(
            None
            if subset_manifest_ref is None
            else Path(subset_manifest_ref["path"]).resolve()
        ),
        subset_stats_path=(
            None
            if subset_stats_ref is None
            else Path(subset_stats_ref["path"]).resolve()
        ),
    )
    resolved_experiment_id = (
        _normalize_optional_identifier(experiment_id, field_name="experiment_id")
        or (
            f"subset_context_{subset_name}"
            if subset_name is not None
            else "explicit_context_session"
        )
    )
    synapse_ref = raw_explicit_artifacts.get(SYNAPSE_REGISTRY_ROLE_ID)
    return {
        "source_mode": WHOLE_BRAIN_CONTEXT_SOURCE_MODE_EXPLICIT,
        "experiment_id": resolved_experiment_id,
        "manifest_reference": None,
        "selection_context": selection_context,
        "dashboard_context": None,
        "dashboard_session_plan": None,
        "showcase_context": None,
        "synapse_registry_path": (
            str(Path(synapse_ref["path"]).resolve())
            if synapse_ref is not None
            else str(
                build_coupling_contract_paths(
                    cfg["paths"]["processed_coupling_dir"]
                ).local_synapse_registry_path
            )
        ),
        "source_notes": {},
    }


def _resolve_selection_from_manifest_payload(
    *,
    cfg: Mapping[str, Any],
    manifest_path: Path,
    manifest_payload: Mapping[str, Any],
) -> dict[str, Any]:
    selected_root_ids_path = Path(cfg["paths"]["selected_root_ids"]).resolve()
    selection_cfg = _require_mapping(cfg.get("selection", {}), field_name="config.selection")
    active_preset = _normalize_optional_identifier(
        selection_cfg.get("active_preset"),
        field_name="config.selection.active_preset",
    )
    subset_name = _normalize_optional_identifier(
        manifest_payload.get("subset_name"),
        field_name="manifest.subset_name",
    )
    circuit_name = _normalize_optional_identifier(
        manifest_payload.get("circuit_name"),
        field_name="manifest.circuit_name",
    )
    if subset_name is not None and active_preset is not None and subset_name != active_preset:
        raise ValueError(
            "Manifest subset_name and config selection.active_preset disagree: "
            f"{subset_name!r} != {active_preset!r}."
        )
    subset_manifest_candidate = None
    subset_stats_candidate = None
    selected_root_candidate = selected_root_ids_path
    if subset_name is not None:
        artifact_paths = build_subset_artifact_paths(cfg["paths"]["subset_output_dir"], subset_name)
        subset_manifest_candidate = artifact_paths.manifest_json.resolve()
        subset_stats_candidate = artifact_paths.stats_json.resolve()
        if artifact_paths.root_ids.exists():
            config_root_ids = _read_and_validate_root_ids(selected_root_ids_path)
            subset_root_ids = _read_and_validate_root_ids(artifact_paths.root_ids)
            if subset_root_ids != config_root_ids:
                raise ValueError(
                    "Subset root_ids.txt does not match config paths.selected_root_ids for "
                    f"manifest {manifest_path}."
                )
            selected_root_candidate = artifact_paths.root_ids.resolve()
    return _resolve_selection_context(
        selected_root_ids_path=selected_root_candidate,
        subset_name=subset_name,
        circuit_name=circuit_name,
        selection_preset=active_preset,
        subset_manifest_path=subset_manifest_candidate,
        subset_stats_path=subset_stats_candidate,
    )


def _resolve_selection_context(
    *,
    selected_root_ids_path: Path,
    subset_name: str | None,
    circuit_name: str | None,
    selection_preset: str | None,
    subset_manifest_path: Path | None,
    subset_stats_path: Path | None,
) -> dict[str, Any]:
    normalized_root_ids = _read_and_validate_root_ids(selected_root_ids_path)
    subset_manifest_payload = _optional_load_json_mapping(subset_manifest_path)
    if subset_manifest_payload is not None:
        manifest_root_ids = _extract_subset_manifest_root_ids(
            subset_manifest_payload,
            field_name="subset_manifest.root_ids",
        )
        if manifest_root_ids != normalized_root_ids:
            raise ValueError(
                "Subset manifest root_ids do not match the resolved active-root roster."
            )
    subset_stats_payload = _optional_load_json_mapping(subset_stats_path)
    if subset_stats_payload is not None:
        final_neuron_count = (
            _require_mapping(
                subset_stats_payload.get("selection", {}),
                field_name="subset_stats.selection",
            ).get("final_neuron_count")
        )
        if final_neuron_count is not None and int(final_neuron_count) != len(normalized_root_ids):
            raise ValueError(
                "Subset stats final_neuron_count does not match the resolved active-root roster."
            )
    resolved_subset_name = subset_name
    if resolved_subset_name is None and subset_manifest_payload is not None:
        resolved_subset_name = _normalize_optional_identifier(
            subset_manifest_payload.get("preset_name"),
            field_name="subset_manifest.preset_name",
        )
    if resolved_subset_name is None and subset_manifest_path is not None:
        resolved_subset_name = _normalize_identifier(
            subset_manifest_path.resolve().parent.name,
            field_name="subset_manifest_path.parent",
        )
    bundle_anchor = resolved_subset_name or circuit_name or "active_subset"
    return {
        "identity_kind": "subset" if resolved_subset_name is not None else "circuit",
        "subset_name": resolved_subset_name,
        "circuit_name": circuit_name,
        "selection_preset": selection_preset,
        "selected_root_ids_path": str(selected_root_ids_path.resolve()),
        "selected_root_ids": list(normalized_root_ids),
        "selected_root_count": len(normalized_root_ids),
        "selected_root_ids_hash": _stable_hash(normalized_root_ids),
        "subset_bundle_id": f"{SUBSET_SELECTION_SOURCE_KIND}:{bundle_anchor}",
        "subset_manifest_path": (
            None
            if subset_manifest_path is None
            else str(subset_manifest_path.resolve())
        ),
        "subset_manifest_exists": (
            False if subset_manifest_path is None else subset_manifest_path.exists()
        ),
        "subset_stats_path": (
            None if subset_stats_path is None else str(subset_stats_path.resolve())
        ),
        "subset_stats_exists": (
            False if subset_stats_path is None else subset_stats_path.exists()
        ),
        "active_anchor_records": _build_active_anchor_records(
            normalized_root_ids,
            subset_manifest_payload,
        ),
    }


def _planned_dashboard_context(plan: Mapping[str, Any]) -> dict[str, Any]:
    normalized_plan = _require_mapping(plan, field_name="dashboard_session_plan")
    return {
        "origin": "planned",
        "metadata": _require_mapping(
            normalized_plan["dashboard_session"],
            field_name="dashboard_session_plan.dashboard_session",
        ),
        "payload": _require_mapping(
            normalized_plan["dashboard_session_payload"],
            field_name="dashboard_session_plan.dashboard_session_payload",
        ),
        "state": _require_mapping(
            normalized_plan["dashboard_session_state"],
            field_name="dashboard_session_plan.dashboard_session_state",
        ),
    }


def _packaged_dashboard_context(metadata: Mapping[str, Any]) -> dict[str, Any]:
    normalized_metadata = load_dashboard_session_metadata(
        Path(metadata["artifacts"][DASHBOARD_METADATA_JSON_KEY]["path"]).resolve()
    )
    bundle_paths = discover_dashboard_session_bundle_paths(normalized_metadata)
    payload = _load_json_mapping(
        bundle_paths[SESSION_PAYLOAD_ARTIFACT_ID],
        field_name="dashboard_session_payload",
    )
    state = _load_json_mapping(
        bundle_paths[SESSION_STATE_ARTIFACT_ID],
        field_name="dashboard_session_state",
    )
    if str(normalized_metadata["bundle_id"]) != str(payload["bundle_reference"]["bundle_id"]):
        raise ValueError("dashboard_session metadata and payload must reference the same bundle_id.")
    if str(normalized_metadata["bundle_id"]) != str(state["bundle_reference"]["bundle_id"]):
        raise ValueError("dashboard_session metadata and state must reference the same bundle_id.")
    return {
        "origin": "packaged",
        "metadata": normalized_metadata,
        "payload": payload,
        "state": state,
    }


def _packaged_showcase_context(metadata: Mapping[str, Any]) -> dict[str, Any]:
    normalized_metadata = load_showcase_session_metadata(
        Path(metadata["artifacts"][SHOWCASE_METADATA_JSON_KEY]["path"]).resolve()
    )
    bundle_paths = discover_showcase_session_bundle_paths(normalized_metadata)
    state = _load_json_mapping(
        bundle_paths[SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID],
        field_name="showcase_presentation_state",
    )
    if str(normalized_metadata["bundle_id"]) != str(state["bundle_reference"]["bundle_id"]):
        raise ValueError("showcase_session metadata and state must reference the same bundle_id.")
    return {
        "origin": "packaged",
        "metadata": normalized_metadata,
        "state": state,
    }


def _build_discovered_artifact_references(
    *,
    source_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    selection = _require_mapping(
        source_context["selection_context"],
        field_name="source_context.selection_context",
    )
    discovered = [
        build_whole_brain_context_artifact_reference(
            artifact_role_id=SELECTED_ROOT_IDS_ROLE_ID,
            source_kind=SUBSET_SELECTION_SOURCE_KIND,
            path=selection["selected_root_ids_path"],
            contract_version=None,
            bundle_id=str(selection["subset_bundle_id"]),
            artifact_id="root_ids",
            artifact_scope=SUBSET_SELECTION_SCOPE,
            status=_status_from_known_path(selection["selected_root_ids_path"]),
        )
    ]
    if selection.get("subset_manifest_path") is not None:
        discovered.append(
            build_whole_brain_context_artifact_reference(
                artifact_role_id=SUBSET_MANIFEST_ROLE_ID,
                source_kind=SUBSET_SELECTION_SOURCE_KIND,
                path=selection["subset_manifest_path"],
                contract_version=None,
                bundle_id=str(selection["subset_bundle_id"]),
                artifact_id="subset_manifest",
                artifact_scope=SUBSET_SELECTION_SCOPE,
                status=_status_from_known_path(selection["subset_manifest_path"]),
            )
        )
    if selection.get("subset_stats_path") is not None:
        discovered.append(
            build_whole_brain_context_artifact_reference(
                artifact_role_id=SUBSET_STATS_ROLE_ID,
                source_kind=SUBSET_SELECTION_SOURCE_KIND,
                path=selection["subset_stats_path"],
                contract_version=None,
                bundle_id=str(selection["subset_bundle_id"]),
                artifact_id="subset_stats",
                artifact_scope=SUBSET_SELECTION_SCOPE,
                status=_status_from_known_path(selection["subset_stats_path"]),
            )
        )
    synapse_registry_path = _normalize_optional_path_string(
        source_context.get("synapse_registry_path")
    )
    if synapse_registry_path is not None:
        discovered.append(
            build_whole_brain_context_artifact_reference(
                artifact_role_id=SYNAPSE_REGISTRY_ROLE_ID,
                source_kind=LOCAL_CONNECTIVITY_SOURCE_KIND,
                path=synapse_registry_path,
                contract_version=COUPLING_BUNDLE_CONTRACT_VERSION,
                bundle_id=_connectivity_bundle_id(synapse_registry_path),
                artifact_id=LOCAL_SYNAPSE_REGISTRY_KEY,
                artifact_scope=LOCAL_CONNECTIVITY_SCOPE,
                status=_status_from_known_path(synapse_registry_path),
            )
        )
    dashboard_context = source_context.get("dashboard_context")
    if isinstance(dashboard_context, Mapping):
        discovered.extend(_dashboard_artifact_references(dashboard_context))
    showcase_context = source_context.get("showcase_context")
    if isinstance(showcase_context, Mapping):
        discovered.extend(_showcase_artifact_references(showcase_context))
    return discovered


def _dashboard_artifact_references(
    dashboard_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    metadata = _require_mapping(
        dashboard_context["metadata"],
        field_name="dashboard_context.metadata",
    )
    bundle_paths = discover_dashboard_session_bundle_paths(metadata)
    return [
        build_whole_brain_context_artifact_reference(
            artifact_role_id=DASHBOARD_SESSION_METADATA_ROLE_ID,
            source_kind=DASHBOARD_SESSION_SOURCE_KIND,
            path=bundle_paths[DASHBOARD_METADATA_JSON_KEY],
            contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            bundle_id=str(metadata["bundle_id"]),
            artifact_id=DASHBOARD_METADATA_JSON_KEY,
            format=str(metadata["artifacts"][DASHBOARD_METADATA_JSON_KEY]["format"]),
            artifact_scope=DASHBOARD_CONTEXT_SCOPE,
            status=str(metadata["artifacts"][DASHBOARD_METADATA_JSON_KEY]["status"]),
        ),
        build_whole_brain_context_artifact_reference(
            artifact_role_id=DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
            source_kind=DASHBOARD_SESSION_SOURCE_KIND,
            path=bundle_paths[SESSION_PAYLOAD_ARTIFACT_ID],
            contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            bundle_id=str(metadata["bundle_id"]),
            artifact_id=SESSION_PAYLOAD_ARTIFACT_ID,
            format=str(metadata["artifacts"][SESSION_PAYLOAD_ARTIFACT_ID]["format"]),
            artifact_scope=DASHBOARD_CONTEXT_SCOPE,
            status=str(metadata["artifacts"][SESSION_PAYLOAD_ARTIFACT_ID]["status"]),
        ),
        build_whole_brain_context_artifact_reference(
            artifact_role_id=DASHBOARD_SESSION_STATE_ROLE_ID,
            source_kind=DASHBOARD_SESSION_SOURCE_KIND,
            path=bundle_paths[SESSION_STATE_ARTIFACT_ID],
            contract_version=DASHBOARD_SESSION_CONTRACT_VERSION,
            bundle_id=str(metadata["bundle_id"]),
            artifact_id=SESSION_STATE_ARTIFACT_ID,
            format=str(metadata["artifacts"][SESSION_STATE_ARTIFACT_ID]["format"]),
            artifact_scope=DASHBOARD_CONTEXT_SCOPE,
            status=str(metadata["artifacts"][SESSION_STATE_ARTIFACT_ID]["status"]),
        ),
    ]


def _showcase_artifact_references(
    showcase_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    metadata = _require_mapping(
        showcase_context["metadata"],
        field_name="showcase_context.metadata",
    )
    bundle_paths = discover_showcase_session_bundle_paths(metadata)
    return [
        build_whole_brain_context_artifact_reference(
            artifact_role_id=SHOWCASE_SESSION_METADATA_ROLE_ID,
            source_kind=SHOWCASE_SESSION_SOURCE_KIND,
            path=bundle_paths[SHOWCASE_METADATA_JSON_KEY],
            contract_version=SHOWCASE_SESSION_CONTRACT_VERSION,
            bundle_id=str(metadata["bundle_id"]),
            artifact_id=SHOWCASE_METADATA_JSON_KEY,
            format=str(metadata["artifacts"][SHOWCASE_METADATA_JSON_KEY]["format"]),
            artifact_scope=SHOWCASE_CONTEXT_SCOPE,
            status=str(metadata["artifacts"][SHOWCASE_METADATA_JSON_KEY]["status"]),
        ),
        build_whole_brain_context_artifact_reference(
            artifact_role_id=SHOWCASE_PRESENTATION_STATE_ROLE_ID,
            source_kind=SHOWCASE_SESSION_SOURCE_KIND,
            path=bundle_paths[SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID],
            contract_version=SHOWCASE_SESSION_CONTRACT_VERSION,
            bundle_id=str(metadata["bundle_id"]),
            artifact_id=SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID,
            format=str(
                metadata["artifacts"][SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID]["format"]
            ),
            artifact_scope=SHOWCASE_CONTEXT_SCOPE,
            status=str(
                metadata["artifacts"][SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID]["status"]
            ),
        ),
    ]


def _merge_explicit_artifact_overrides(
    discovered: Sequence[Mapping[str, Any]],
    *,
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    contract_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    hooks = {
        str(item["artifact_role_id"]): dict(item)
        for item in contract_metadata["artifact_hook_catalog"]
    }
    merged = {
        str(item["artifact_role_id"]): copy.deepcopy(dict(item)) for item in discovered
    }
    for role_id, raw in raw_explicit_artifacts.items():
        base = merged.get(role_id, {})
        hook = hooks.get(role_id)
        if hook is None:
            raise ValueError(
                f"explicit_artifact_references contains unsupported artifact_role_id {role_id!r}."
            )
        resolved_path = raw.get("path", base["path"])
        resolved_status = raw.get("status")
        if resolved_status is None:
            if "path" in raw:
                resolved_status = _status_from_known_path(resolved_path)
            else:
                resolved_status = base.get("status", ASSET_STATUS_READY)
        merged[role_id] = build_whole_brain_context_artifact_reference(
            artifact_role_id=role_id,
            source_kind=str(raw.get("source_kind", base.get("source_kind", hook["source_kind"]))),
            path=resolved_path,
            contract_version=(
                hook["required_contract_version"]
                if raw.get("contract_version", base.get("contract_version")) is None
                else str(raw.get("contract_version", base.get("contract_version")))
            ),
            bundle_id=str(raw.get("bundle_id", base.get("bundle_id", f"explicit:{role_id}"))),
            artifact_id=str(raw.get("artifact_id", base.get("artifact_id", hook["artifact_id"]))),
            format=(
                None
                if raw.get("format", base.get("format")) is None
                else str(raw.get("format", base.get("format")))
            ),
            artifact_scope=str(
                raw.get("artifact_scope", base.get("artifact_scope", hook["artifact_scope"]))
            ),
            status=str(resolved_status),
        )
    return list(merged.values())


def _validate_resolved_artifact_alignment(
    *,
    selection_context: Mapping[str, Any],
    source_context: Mapping[str, Any],
    artifact_references_by_role: Mapping[str, Mapping[str, Any]],
    raw_explicit_artifacts: Mapping[str, Mapping[str, Any]],
    planned_artifact_paths: Mapping[str, str],
) -> None:
    _validate_selected_root_ids_reference(
        artifact_references_by_role.get(SELECTED_ROOT_IDS_ROLE_ID),
        selection_context=selection_context,
        must_exist=True,
    )
    subset_manifest_required = (
        SUBSET_MANIFEST_ROLE_ID in raw_explicit_artifacts
        or bool(selection_context.get("subset_manifest_path"))
    )
    _validate_subset_manifest_reference(
        artifact_references_by_role.get(SUBSET_MANIFEST_ROLE_ID),
        selection_context=selection_context,
        required=subset_manifest_required,
    )
    _validate_subset_stats_reference(
        artifact_references_by_role.get(SUBSET_STATS_ROLE_ID),
        selection_context=selection_context,
        required=SUBSET_STATS_ROLE_ID in raw_explicit_artifacts,
    )
    _validate_synapse_registry_reference(
        artifact_references_by_role.get(SYNAPSE_REGISTRY_ROLE_ID),
        selection_context=selection_context,
        required=SYNAPSE_REGISTRY_ROLE_ID in raw_explicit_artifacts,
    )
    if source_context.get("dashboard_context") is not None or DASHBOARD_SESSION_METADATA_ROLE_ID in raw_explicit_artifacts:
        _validate_dashboard_reference_alignment(
            metadata_ref=artifact_references_by_role.get(DASHBOARD_SESSION_METADATA_ROLE_ID),
            payload_ref=artifact_references_by_role.get(DASHBOARD_SESSION_PAYLOAD_ROLE_ID),
            state_ref=artifact_references_by_role.get(DASHBOARD_SESSION_STATE_ROLE_ID),
            selection_context=selection_context,
            source_context=source_context,
            planned_artifact_paths=planned_artifact_paths,
        )
    if source_context.get("showcase_context") is not None or SHOWCASE_SESSION_METADATA_ROLE_ID in raw_explicit_artifacts:
        _validate_showcase_reference_alignment(
            metadata_ref=artifact_references_by_role.get(SHOWCASE_SESSION_METADATA_ROLE_ID),
            state_ref=artifact_references_by_role.get(SHOWCASE_PRESENTATION_STATE_ROLE_ID),
            selection_context=selection_context,
            source_context=source_context,
            planned_artifact_paths=planned_artifact_paths,
        )


def _validate_selected_root_ids_reference(
    reference: Mapping[str, Any] | None,
    *,
    selection_context: Mapping[str, Any],
    must_exist: bool,
) -> None:
    if reference is None:
        if must_exist:
            raise ValueError(
                "Whole-brain context planning requires a selected_root_ids artifact reference."
            )
        return
    path = Path(str(reference["path"])).resolve()
    if not path.exists():
        raise ValueError(f"Selected-root roster is missing at {path}.")
    if _read_and_validate_root_ids(path) != list(selection_context["selected_root_ids"]):
        raise ValueError(
            "Selected-root roster does not match the resolved active subset."
        )


def _validate_subset_manifest_reference(
    reference: Mapping[str, Any] | None,
    *,
    selection_context: Mapping[str, Any],
    required: bool,
) -> None:
    if reference is None:
        if required:
            raise ValueError(
                "Whole-brain context planning requires a subset_manifest artifact reference."
            )
        return
    path = Path(str(reference["path"])).resolve()
    if not path.exists():
        if required:
            raise ValueError(f"Subset manifest is missing at {path}.")
        return
    payload = _load_json_mapping(path, field_name="subset_manifest")
    manifest_root_ids = _extract_subset_manifest_root_ids(
        payload,
        field_name="subset_manifest.root_ids",
    )
    if manifest_root_ids != list(selection_context["selected_root_ids"]):
        raise ValueError(
            "Subset manifest root_ids do not match the resolved active subset."
        )


def _validate_subset_stats_reference(
    reference: Mapping[str, Any] | None,
    *,
    selection_context: Mapping[str, Any],
    required: bool,
) -> None:
    if reference is None:
        if required:
            raise ValueError(
                "Whole-brain context planning requires a subset_stats artifact reference."
            )
        return
    path = Path(str(reference["path"])).resolve()
    if not path.exists():
        if required:
            raise ValueError(f"Subset stats are missing at {path}.")
        return
    payload = _load_json_mapping(path, field_name="subset_stats")
    selection_summary = _require_mapping(
        payload.get("selection", {}),
        field_name="subset_stats.selection",
    )
    final_neuron_count = selection_summary.get("final_neuron_count")
    if final_neuron_count is not None and int(final_neuron_count) != int(
        selection_context["selected_root_count"]
    ):
        raise ValueError(
            "Subset stats final_neuron_count does not match the resolved active subset."
        )


def _validate_synapse_registry_reference(
    reference: Mapping[str, Any] | None,
    *,
    selection_context: Mapping[str, Any],
    required: bool,
) -> None:
    if reference is None:
        if required:
            raise ValueError(
                "Whole-brain context planning requires a synapse_registry artifact reference."
            )
        return
    path = Path(str(reference["path"])).resolve()
    if not path.exists():
        if required:
            raise ValueError(f"Local synapse registry is missing at {path}.")
        return
    _build_synapse_evidence_summary(
        path=path,
        selected_root_ids=selection_context["selected_root_ids"],
    )


def _validate_dashboard_reference_alignment(
    *,
    metadata_ref: Mapping[str, Any] | None,
    payload_ref: Mapping[str, Any] | None,
    state_ref: Mapping[str, Any] | None,
    selection_context: Mapping[str, Any],
    source_context: Mapping[str, Any],
    planned_artifact_paths: Mapping[str, str],
) -> None:
    if metadata_ref is None or payload_ref is None or state_ref is None:
        raise ValueError(
            "Whole-brain context planning requires dashboard metadata, payload, and state references."
        )
    metadata, payload, state = _dashboard_records_for_reference_resolution(
        source_context=source_context,
        metadata_ref=metadata_ref,
        payload_ref=payload_ref,
        state_ref=state_ref,
        planned_artifact_paths=planned_artifact_paths,
    )
    if _dashboard_selected_root_ids(payload) != list(selection_context["selected_root_ids"]):
        raise ValueError(
            "Dashboard session selected_root_ids do not match the resolved active subset."
        )
    if str(metadata["bundle_id"]) != str(state["bundle_reference"]["bundle_id"]):
        raise ValueError("dashboard_session metadata and state must reference the same bundle_id.")


def _validate_showcase_reference_alignment(
    *,
    metadata_ref: Mapping[str, Any] | None,
    state_ref: Mapping[str, Any] | None,
    selection_context: Mapping[str, Any],
    source_context: Mapping[str, Any],
    planned_artifact_paths: Mapping[str, str],
) -> None:
    if metadata_ref is None or state_ref is None:
        raise ValueError(
            "Whole-brain context planning requires showcase metadata and presentation-state references."
        )
    metadata, state = _showcase_records_for_reference_resolution(
        source_context=source_context,
        metadata_ref=metadata_ref,
        state_ref=state_ref,
        planned_artifact_paths=planned_artifact_paths,
    )
    selected_root_ids = {int(root_id) for root_id in selection_context["selected_root_ids"]}
    unexpected_focus_root_ids = sorted(
        set(_showcase_focus_root_ids(state)) - selected_root_ids
    )
    if unexpected_focus_root_ids:
        raise ValueError(
            "Showcase session focus_root_ids include roots outside the resolved "
            f"active subset: {unexpected_focus_root_ids!r}."
        )


def _apply_artifact_overrides_to_selection_context(
    selection_context: Mapping[str, Any],
    *,
    artifact_references_by_role: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    resolved = copy.deepcopy(dict(selection_context))
    root_ref = artifact_references_by_role.get(SELECTED_ROOT_IDS_ROLE_ID)
    if root_ref is not None:
        resolved["selected_root_ids_path"] = str(Path(root_ref["path"]).resolve())
        resolved["subset_bundle_id"] = str(root_ref["bundle_id"])
    manifest_ref = artifact_references_by_role.get(SUBSET_MANIFEST_ROLE_ID)
    if manifest_ref is not None:
        resolved["subset_manifest_path"] = str(Path(manifest_ref["path"]).resolve())
        resolved["subset_manifest_exists"] = Path(manifest_ref["path"]).resolve().exists()
    stats_ref = artifact_references_by_role.get(SUBSET_STATS_ROLE_ID)
    if stats_ref is not None:
        resolved["subset_stats_path"] = str(Path(stats_ref["path"]).resolve())
        resolved["subset_stats_exists"] = Path(stats_ref["path"]).resolve().exists()
    return resolved


def _build_registry_sources(
    *,
    selection_context: Mapping[str, Any],
    artifact_references_by_role: Mapping[str, Mapping[str, Any]],
    planned_artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    selected_root_ref = _require_mapping(
        artifact_references_by_role[SELECTED_ROOT_IDS_ROLE_ID],
        field_name="artifact_references.selected_root_ids",
    )
    subset_manifest_ref = artifact_references_by_role.get(SUBSET_MANIFEST_ROLE_ID)
    subset_stats_ref = artifact_references_by_role.get(SUBSET_STATS_ROLE_ID)
    synapse_ref = artifact_references_by_role.get(SYNAPSE_REGISTRY_ROLE_ID)
    synapse_summary = None
    if synapse_ref is not None and _artifact_is_materialized(synapse_ref, planned_artifact_paths):
        synapse_summary = _build_synapse_evidence_summary(
            path=Path(str(synapse_ref["path"])).resolve(),
            selected_root_ids=selection_context["selected_root_ids"],
        )
    return {
        "selected_root_ids": _artifact_source_summary(selected_root_ref, planned_artifact_paths),
        "subset_manifest": (
            None
            if subset_manifest_ref is None
            else _artifact_source_summary(subset_manifest_ref, planned_artifact_paths)
        ),
        "subset_stats": (
            None
            if subset_stats_ref is None
            else _artifact_source_summary(subset_stats_ref, planned_artifact_paths)
        ),
        "synapse_registry": (
            None
            if synapse_ref is None
            else {
                **_artifact_source_summary(synapse_ref, planned_artifact_paths),
                "evidence_summary": synapse_summary,
            }
        ),
        "active_anchor_root_ids": list(selection_context["selected_root_ids"]),
        "active_anchor_root_count": int(selection_context["selected_root_count"]),
    }


def _resolve_query_profile_selection(
    *,
    contract_metadata: Mapping[str, Any],
    artifact_references_by_role: Mapping[str, Mapping[str, Any]],
    planned_artifact_paths: Mapping[str, str],
    requested_active_query_profile_id: str | None,
    requested_query_profile_ids: Sequence[str] | None,
) -> dict[str, Any]:
    available_profiles: list[dict[str, Any]] = []
    unavailable_profiles: list[dict[str, Any]] = []
    for definition in discover_whole_brain_context_query_profiles(contract_metadata):
        missing_roles = [
            str(role_id)
            for role_id in definition["required_artifact_role_ids"]
            if not _artifact_role_is_available(
                role_id,
                artifact_references_by_role=artifact_references_by_role,
                planned_artifact_paths=planned_artifact_paths,
            )
        ]
        record = {
            "query_profile_id": str(definition["query_profile_id"]),
            "display_name": str(definition["display_name"]),
            "query_family": str(definition["query_family"]),
            "required_artifact_role_ids": list(definition["required_artifact_role_ids"]),
            "default_overlay_id": str(definition["default_overlay_id"]),
            "default_reduction_profile_id": str(
                definition["default_reduction_profile_id"]
            ),
            "scientific_curation_required": bool(
                definition["scientific_curation_required"]
            ),
            "availability": "available" if not missing_roles else "unavailable",
            "missing_artifact_role_ids": missing_roles,
        }
        if missing_roles:
            unavailable_profiles.append(record)
        else:
            available_profiles.append(record)
    if not available_profiles:
        missing_summary = {
            item["query_profile_id"]: item["missing_artifact_role_ids"]
            for item in unavailable_profiles
        }
        raise ValueError(
            "Whole-brain context planning could not activate any query profile from "
            f"the resolved artifacts: {missing_summary!r}."
        )
    available_query_profile_ids = [
        str(item["query_profile_id"]) for item in available_profiles
    ]
    active_query_profile_id = (
        _normalize_optional_identifier(
            requested_active_query_profile_id,
            field_name="query_profile_id",
        )
        or _default_active_query_profile(available_query_profile_ids)
    )
    if active_query_profile_id not in available_query_profile_ids:
        reason = next(
            (
                item["missing_artifact_role_ids"]
                for item in unavailable_profiles
                if str(item["query_profile_id"]) == active_query_profile_id
            ),
            None,
        )
        raise ValueError(
            "Requested whole-brain context query_profile_id "
            f"{active_query_profile_id!r} is unavailable because required artifact "
            f"roles are missing: {reason!r}."
        )
    selected_query_profile_ids = _normalize_requested_query_profiles(
        requested_query_profile_ids=requested_query_profile_ids,
        active_query_profile_id=active_query_profile_id,
        available_query_profile_ids=available_query_profile_ids,
    )
    _validate_query_profile_combination(selected_query_profile_ids)
    return {
        "active_query_profile_id": active_query_profile_id,
        "selected_query_profile_ids": selected_query_profile_ids,
        "available_query_profile_ids": available_query_profile_ids,
        "available_query_profiles": available_profiles,
        "unavailable_query_profiles": unavailable_profiles,
    }


def _build_metadata_facet_requests(
    *,
    contract_metadata: Mapping[str, Any],
    query_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    enabled = set(query_state["enabled_metadata_facet_ids"])
    requests: list[dict[str, Any]] = []
    for definition in discover_whole_brain_context_metadata_facets(contract_metadata):
        facet_id = str(definition["metadata_facet_id"])
        if facet_id not in enabled:
            continue
        requests.append(
            {
                "metadata_facet_id": facet_id,
                "display_name": str(definition["display_name"]),
                "facet_scope": str(definition["facet_scope"]),
                "default_enabled": bool(definition["default_enabled"]),
                "enabled": True,
            }
        )
    return requests


def _resolve_downstream_module_requests(
    *,
    contract_metadata: Mapping[str, Any],
    requested_downstream_module_role_ids: Sequence[str] | None,
    selected_query_profile_ids: Sequence[str],
    active_query_profile_id: str,
) -> list[dict[str, Any]]:
    if requested_downstream_module_role_ids is None:
        normalized_requested = (
            [SIMPLIFIED_READOUT_MODULE_ROLE_ID]
            if active_query_profile_id == DOWNSTREAM_MODULE_REVIEW_QUERY_PROFILE_ID
            else []
        )
    else:
        normalized_requested = _normalize_identifier_sequence(
            requested_downstream_module_role_ids,
            field_name="requested_downstream_module_role_ids",
        )
    if (
        normalized_requested
        and DOWNSTREAM_MODULE_REVIEW_QUERY_PROFILE_ID not in set(selected_query_profile_ids)
    ):
        raise ValueError(
            "requested_downstream_module_role_ids requires the whole-brain context "
            "query profile 'downstream_module_review'."
        )
    requests: list[dict[str, Any]] = []
    for definition in contract_metadata["downstream_module_role_catalog"]:
        role_id = str(definition["downstream_module_role_id"])
        if role_id not in normalized_requested:
            continue
        requests.append(
            {
                "downstream_module_role_id": role_id,
                "display_name": str(definition["display_name"]),
                "default_context_layer_id": str(definition["default_context_layer_id"]),
                "allows_aggregated_readout": bool(definition["allows_aggregated_readout"]),
                "requires_scientific_curation": bool(
                    definition["requires_scientific_curation"]
                ),
            }
        )
    return requests


def _build_labeling_rules(*, selected_root_ids: Sequence[int]) -> dict[str, Any]:
    return {
        "active_root_ids": [int(root_id) for root_id in selected_root_ids],
        "active_node_role_ids": ["active_selected", "active_pathway_highlight"],
        "context_node_role_ids": ["context_only", "context_pathway_highlight"],
        "active_boundary_status": "active",
        "context_boundary_status": "context",
        "pathway_highlight_preserves_boundary_status": True,
        "downstream_modules_are_summary_objects": True,
        "truthfulness_rules": [
            "Active-selected nodes must trace back to subset-selection artifacts.",
            "Context-only nodes remain outside the active subset even when emphasized.",
            "Pathway highlights may elevate attention, but they do not change active-versus-context identity.",
            "Downstream modules are optional summaries rather than neuron-level observations.",
        ],
    }


def _build_query_execution_input(
    *,
    config_path: str,
    selection_context: Mapping[str, Any],
    registry_sources: Mapping[str, Any],
    query_profile_resolution: Mapping[str, Any],
    query_state: Mapping[str, Any],
    reduction_profile: Mapping[str, Any],
    metadata_facet_requests: Sequence[Mapping[str, Any]],
    downstream_module_requests: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "plan_version": WHOLE_BRAIN_CONTEXT_SESSION_PLAN_VERSION,
        "config_path": str(Path(config_path).resolve()),
        "selection": copy.deepcopy(dict(selection_context)),
        "registry_sources": copy.deepcopy(dict(registry_sources)),
        "query_profile_resolution": copy.deepcopy(dict(query_profile_resolution)),
        "query_state": copy.deepcopy(dict(query_state)),
        "reduction_profile": copy.deepcopy(dict(reduction_profile)),
        "metadata_facet_requests": [
            copy.deepcopy(dict(item)) for item in metadata_facet_requests
        ],
        "downstream_module_requests": [
            copy.deepcopy(dict(item)) for item in downstream_module_requests
        ],
    }


def _build_fixture_profile(
    *,
    source_mode: str,
    requested_fixture_mode: str | None,
    linked_sessions: Mapping[str, Any],
) -> dict[str, Any]:
    resolved_fixture_mode = _resolve_fixture_mode(requested_fixture_mode)
    compact_gate = {
        "surface_kind": "manifest" if source_mode == WHOLE_BRAIN_CONTEXT_SOURCE_MODE_MANIFEST else "subset_selection",
        "artifact_role_id": SUBSET_MANIFEST_ROLE_ID,
        "bundle_id": None,
    }
    if source_mode in {
        WHOLE_BRAIN_CONTEXT_SOURCE_MODE_SUBSET,
        WHOLE_BRAIN_CONTEXT_SOURCE_MODE_EXPLICIT,
    }:
        compact_gate = {
            "surface_kind": "subset_selection",
            "artifact_role_id": SELECTED_ROOT_IDS_ROLE_ID,
            "bundle_id": None,
        }
    if "dashboard" in linked_sessions:
        compact_gate = {
            "surface_kind": "dashboard_session",
            "artifact_role_id": DASHBOARD_SESSION_METADATA_ROLE_ID,
            "bundle_id": str(linked_sessions["dashboard"]["bundle_id"]),
        }
    if "showcase" in linked_sessions:
        compact_gate = {
            "surface_kind": "showcase_session",
            "artifact_role_id": SHOWCASE_SESSION_METADATA_ROLE_ID,
            "bundle_id": str(linked_sessions["showcase"]["bundle_id"]),
        }
    return {
        "fixture_mode": resolved_fixture_mode,
        "keeps_readiness_fixtures_fast": True,
        "workflow_kind": "local_whole_brain_context_review",
        "source_mode": source_mode,
        "compact_gate": compact_gate,
    }


def _resolve_fixture_mode(value: str | None) -> str:
    if value is None:
        return DEFAULT_WHOLE_BRAIN_CONTEXT_FIXTURE_MODE
    normalized = _normalize_identifier(value, field_name="fixture_mode")
    if normalized not in set(SUPPORTED_WHOLE_BRAIN_CONTEXT_FIXTURE_MODES):
        raise ValueError(
            "fixture_mode must be one of "
            f"{SUPPORTED_WHOLE_BRAIN_CONTEXT_FIXTURE_MODES!r}."
        )
    return normalized


def _build_query_preset_library(
    *,
    config_path: str,
    contract_metadata: Mapping[str, Any],
    selection_context: Mapping[str, Any],
    registry_sources: Mapping[str, Any],
    query_profile_resolution: Mapping[str, Any],
    query_state: Mapping[str, Any],
    reduction_profile: Mapping[str, Any],
    metadata_facet_requests: Sequence[Mapping[str, Any]],
    downstream_module_requests: Sequence[Mapping[str, Any]],
    linked_sessions: Mapping[str, Any],
    fixture_profile: Mapping[str, Any],
) -> dict[str, Any]:
    query_profiles_by_id = {
        str(item["query_profile_id"]): copy.deepcopy(dict(item))
        for item in discover_whole_brain_context_query_profiles(contract_metadata)
    }
    available_profile_ids = set(query_profile_resolution["available_query_profile_ids"])
    available_presets: list[dict[str, Any]] = []
    unavailable_presets: list[dict[str, Any]] = []
    preset_payloads: dict[str, dict[str, Any]] = {}
    enabled_metadata_facet_ids = list(query_state["enabled_metadata_facet_ids"])
    for sequence_index, blueprint in enumerate(_query_preset_blueprints()):
        preset_id = str(blueprint["preset_id"])
        required_linked_session_kind = blueprint.get("required_linked_session_kind")
        if (
            required_linked_session_kind is not None
            and required_linked_session_kind not in linked_sessions
        ):
            unavailable_presets.append(
                _build_unavailable_query_preset_record(
                    blueprint=blueprint,
                    sequence_index=sequence_index,
                    reason=(
                        f"Requires a linked {required_linked_session_kind}_session review surface."
                    ),
                )
            )
            continue
        resolved_query_profile_id = next(
            (
                profile_id
                for profile_id in blueprint["preferred_query_profile_ids"]
                if profile_id in available_profile_ids
            ),
            None,
        )
        if resolved_query_profile_id is None:
            unavailable_presets.append(
                _build_unavailable_query_preset_record(
                    blueprint=blueprint,
                    sequence_index=sequence_index,
                    reason=(
                        "Required query profiles are unavailable for the resolved artifact set: "
                        f"{list(blueprint['preferred_query_profile_ids'])!r}."
                    ),
                )
            )
            continue
        query_profile = query_profiles_by_id[resolved_query_profile_id]
        enabled_overlay_ids = [
            overlay_id
            for overlay_id in blueprint["preferred_overlay_ids"]
            if overlay_id in set(query_profile["supported_overlay_ids"])
        ]
        if not enabled_overlay_ids:
            enabled_overlay_ids = list(query_profile["supported_overlay_ids"])
        default_overlay_id = (
            str(blueprint["default_overlay_id"])
            if str(blueprint["default_overlay_id"]) in enabled_overlay_ids
            else str(query_profile["default_overlay_id"])
        )
        if default_overlay_id not in enabled_overlay_ids:
            default_overlay_id = str(enabled_overlay_ids[0])
        preset_query_state = build_whole_brain_context_query_state(
            query_profile_id=resolved_query_profile_id,
            default_overlay_id=default_overlay_id,
            default_reduction_profile_id=str(
                blueprint["default_reduction_profile_id"]
            ),
            enabled_overlay_ids=enabled_overlay_ids,
            enabled_metadata_facet_ids=enabled_metadata_facet_ids,
            contract_metadata=contract_metadata,
        )
        preset_reduction_profile = _catalog_item_by_id(
            contract_metadata["reduction_profile_catalog"],
            key_name="reduction_profile_id",
            identifier=preset_query_state["default_reduction_profile_id"],
        )
        preset_query_profile_resolution = {
            "active_query_profile_id": resolved_query_profile_id,
            "selected_query_profile_ids": [resolved_query_profile_id],
            "available_query_profile_ids": list(
                query_profile_resolution["available_query_profile_ids"]
            ),
        }
        preset_execution = execute_whole_brain_context_query(
            _build_query_execution_input(
                config_path=config_path,
                selection_context=selection_context,
                registry_sources=registry_sources,
                query_profile_resolution=preset_query_profile_resolution,
                query_state=preset_query_state,
                reduction_profile=preset_reduction_profile,
                metadata_facet_requests=metadata_facet_requests,
                downstream_module_requests=downstream_module_requests,
            ),
            reduction_controls=copy.deepcopy(
                dict(blueprint.get("reduction_controls_patch", {}))
            ),
        )
        if (
            blueprint.get("requires_pathway_highlight", False)
            and not preset_execution["pathway_highlights"]
        ):
            unavailable_presets.append(
                _build_unavailable_query_preset_record(
                    blueprint=blueprint,
                    sequence_index=sequence_index,
                    reason="No deterministic pathway highlight survived the packaged query budget.",
                )
            )
            continue
        preset_payloads[preset_id] = _build_query_preset_payload(
            blueprint=blueprint,
            preset_query_state=preset_query_state,
            preset_reduction_profile=preset_reduction_profile,
            preset_execution=preset_execution,
        )
        available_presets.append(
            _build_query_preset_record(
                blueprint=blueprint,
                sequence_index=sequence_index,
                query_profile=query_profile,
                preset_query_state=preset_query_state,
                preset_execution=preset_execution,
                linked_sessions=linked_sessions,
            )
        )
    active_preset_id = _resolve_active_query_preset_id(
        active_query_profile_id=str(
            query_profile_resolution["active_query_profile_id"]
        ),
        available_presets=available_presets,
    )
    return {
        "preset_library_id": DEFAULT_CONTEXT_QUERY_PRESET_LIBRARY_ID,
        "fixture_profile": copy.deepcopy(dict(fixture_profile)),
        "active_preset_id": active_preset_id,
        "available_preset_ids": [
            str(item["preset_id"]) for item in available_presets
        ],
        "preset_discovery_order": list(SUPPORTED_CONTEXT_QUERY_PRESET_IDS),
        "available_query_presets": [copy.deepcopy(dict(item)) for item in available_presets],
        "unavailable_query_presets": [
            copy.deepcopy(dict(item)) for item in unavailable_presets
        ],
        "handoff_preset_ids": {
            "dashboard": (
                DASHBOARD_HANDOFF_PRESET_ID
                if any(
                    str(item["preset_id"]) == DASHBOARD_HANDOFF_PRESET_ID
                    for item in available_presets
                )
                else None
            ),
            "showcase": (
                SHOWCASE_HANDOFF_PRESET_ID
                if any(
                    str(item["preset_id"]) == SHOWCASE_HANDOFF_PRESET_ID
                    for item in available_presets
                )
                else None
            ),
        },
        "preset_payloads_by_id": copy.deepcopy(preset_payloads),
    }


def _query_preset_blueprints() -> list[dict[str, Any]]:
    return [
        {
            "preset_id": OVERVIEW_CONTEXT_PRESET_ID,
            "display_name": "Whole-Brain Overview",
            "description": "Default richer Milestone 17 review landing for the active subset plus a broader deterministic neighborhood.",
            "preferred_query_profile_ids": [
                BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                ACTIVE_SUBSET_SHELL_QUERY_PROFILE_ID,
            ],
            "preferred_overlay_ids": [
                ACTIVE_BOUNDARY_OVERLAY_ID,
                BIDIRECTIONAL_CONTEXT_GRAPH_OVERLAY_ID,
                UPSTREAM_GRAPH_OVERLAY_ID,
                DOWNSTREAM_GRAPH_OVERLAY_ID,
                PATHWAY_HIGHLIGHT_OVERLAY_ID,
                DOWNSTREAM_MODULE_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            "default_overlay_id": BIDIRECTIONAL_CONTEXT_GRAPH_OVERLAY_ID,
            "default_reduction_profile_id": BALANCED_NEIGHBORHOOD_REDUCTION_PROFILE_ID,
            "reduction_controls_patch": {},
            "primary_graph_view_id": "overview_graph",
            "required_linked_session_kind": None,
            "requires_pathway_highlight": False,
            "discovery_note": "Use this preset to compare the compact upstream gate against the richer packaged context graph.",
        },
        {
            "preset_id": UPSTREAM_HALO_PRESET_ID,
            "display_name": "Upstream Halo",
            "description": "Directional incoming-context review surface around the active subset.",
            "preferred_query_profile_ids": [
                UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
            ],
            "preferred_overlay_ids": [
                ACTIVE_BOUNDARY_OVERLAY_ID,
                UPSTREAM_GRAPH_OVERLAY_ID,
                PATHWAY_HIGHLIGHT_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            "default_overlay_id": UPSTREAM_GRAPH_OVERLAY_ID,
            "default_reduction_profile_id": BALANCED_NEIGHBORHOOD_REDUCTION_PROFILE_ID,
            "reduction_controls_patch": {},
            "primary_graph_view_id": "overview_graph",
            "required_linked_session_kind": None,
            "requires_pathway_highlight": False,
            "discovery_note": "Use this preset to review context-only nodes that feed into the active subset.",
        },
        {
            "preset_id": DOWNSTREAM_HALO_PRESET_ID,
            "display_name": "Downstream Halo",
            "description": "Directional outgoing-context review surface around the active subset.",
            "preferred_query_profile_ids": [
                DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
            ],
            "preferred_overlay_ids": [
                ACTIVE_BOUNDARY_OVERLAY_ID,
                DOWNSTREAM_GRAPH_OVERLAY_ID,
                DOWNSTREAM_MODULE_OVERLAY_ID,
                PATHWAY_HIGHLIGHT_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            "default_overlay_id": DOWNSTREAM_GRAPH_OVERLAY_ID,
            "default_reduction_profile_id": DOWNSTREAM_MODULE_COLLAPSED_REDUCTION_PROFILE_ID,
            "reduction_controls_patch": {},
            "primary_graph_view_id": "overview_graph",
            "required_linked_session_kind": None,
            "requires_pathway_highlight": False,
            "discovery_note": "Use this preset to review outgoing context breadth without relabeling it as active simulator state.",
        },
        {
            "preset_id": PATHWAY_FOCUS_PRESET_ID,
            "display_name": "Pathway Focus",
            "description": "Focused pathway review surface for one deterministic highlighted context path.",
            "preferred_query_profile_ids": [
                PATHWAY_HIGHLIGHT_REVIEW_QUERY_PROFILE_ID,
            ],
            "preferred_overlay_ids": [
                ACTIVE_BOUNDARY_OVERLAY_ID,
                PATHWAY_HIGHLIGHT_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            "default_overlay_id": PATHWAY_HIGHLIGHT_OVERLAY_ID,
            "default_reduction_profile_id": PATHWAY_FOCUS_REDUCTION_PROFILE_ID,
            "reduction_controls_patch": {},
            "primary_graph_view_id": "focused_subgraph",
            "required_linked_session_kind": None,
            "requires_pathway_highlight": True,
            "discovery_note": "Use this preset for the first local pathway-focused Milestone 17 review case.",
        },
        {
            "preset_id": DASHBOARD_HANDOFF_PRESET_ID,
            "display_name": "Dashboard Handoff",
            "description": "Bridge the compact dashboard gate into the richer whole-brain review package.",
            "preferred_query_profile_ids": [
                BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                ACTIVE_SUBSET_SHELL_QUERY_PROFILE_ID,
            ],
            "preferred_overlay_ids": [
                ACTIVE_BOUNDARY_OVERLAY_ID,
                BIDIRECTIONAL_CONTEXT_GRAPH_OVERLAY_ID,
                UPSTREAM_GRAPH_OVERLAY_ID,
                DOWNSTREAM_GRAPH_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            "default_overlay_id": BIDIRECTIONAL_CONTEXT_GRAPH_OVERLAY_ID,
            "default_reduction_profile_id": BALANCED_NEIGHBORHOOD_REDUCTION_PROFILE_ID,
            "reduction_controls_patch": {},
            "primary_graph_view_id": "overview_graph",
            "required_linked_session_kind": "dashboard",
            "requires_pathway_highlight": False,
            "discovery_note": "Use this preset when reviewing the packaged dashboard session as the fast readiness gate before opening broader context.",
        },
        {
            "preset_id": SHOWCASE_HANDOFF_PRESET_ID,
            "display_name": "Showcase Handoff",
            "description": "Bridge the compact showcase rehearsal surface into a richer whole-brain review state.",
            "preferred_query_profile_ids": [
                PATHWAY_HIGHLIGHT_REVIEW_QUERY_PROFILE_ID,
                DOWNSTREAM_MODULE_REVIEW_QUERY_PROFILE_ID,
                BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
                DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
            ],
            "preferred_overlay_ids": [
                ACTIVE_BOUNDARY_OVERLAY_ID,
                PATHWAY_HIGHLIGHT_OVERLAY_ID,
                DOWNSTREAM_GRAPH_OVERLAY_ID,
                DOWNSTREAM_MODULE_OVERLAY_ID,
                METADATA_FACET_BADGES_OVERLAY_ID,
            ],
            "default_overlay_id": PATHWAY_HIGHLIGHT_OVERLAY_ID,
            "default_reduction_profile_id": PATHWAY_FOCUS_REDUCTION_PROFILE_ID,
            "reduction_controls_patch": {},
            "primary_graph_view_id": "focused_subgraph",
            "required_linked_session_kind": "showcase",
            "requires_pathway_highlight": False,
            "discovery_note": "Use this preset for review handoff from the compact showcase surface into broader context and pathway emphasis.",
        },
    ]


def _build_query_preset_payload(
    *,
    blueprint: Mapping[str, Any],
    preset_query_state: Mapping[str, Any],
    preset_reduction_profile: Mapping[str, Any],
    preset_execution: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "preset_id": str(blueprint["preset_id"]),
        "display_name": str(blueprint["display_name"]),
        "query_profile_id": str(preset_execution["query_profile_id"]),
        "query_family": str(preset_execution["query_family"]),
        "query_state": copy.deepcopy(dict(preset_query_state)),
        "reduction_profile": copy.deepcopy(dict(preset_reduction_profile)),
        "reduction_controls": copy.deepcopy(dict(preset_execution["reduction_controls"])),
        "execution_summary": copy.deepcopy(dict(preset_execution["execution_summary"])),
        "overview_graph": copy.deepcopy(dict(preset_execution["overview_graph"])),
        "focused_subgraph": copy.deepcopy(dict(preset_execution["focused_subgraph"])),
        "pathway_highlights": [
            copy.deepcopy(dict(item)) for item in preset_execution["pathway_highlights"]
        ],
    }


def _build_query_preset_record(
    *,
    blueprint: Mapping[str, Any],
    sequence_index: int,
    query_profile: Mapping[str, Any],
    preset_query_state: Mapping[str, Any],
    preset_execution: Mapping[str, Any],
    linked_sessions: Mapping[str, Any],
) -> dict[str, Any]:
    preset_id = str(blueprint["preset_id"])
    primary_graph_view_id = _query_preset_primary_graph_view_id(
        blueprint=blueprint,
        preset_execution=preset_execution,
    )
    pathway_reference = {
        "artifact_role_id": CONTEXT_VIEW_PAYLOAD_ROLE_ID,
        "payload_path": f"query_preset_payloads.{preset_id}.pathway_highlights",
        "highlight_count": len(preset_execution["pathway_highlights"]),
    }
    if preset_execution["pathway_highlights"]:
        pathway_reference["primary_pathway_id"] = str(
            preset_execution["pathway_highlights"][0]["pathway_id"]
        )
    return {
        "preset_id": preset_id,
        "display_name": str(blueprint["display_name"]),
        "description": str(blueprint["description"]),
        "sequence_index": sequence_index,
        "availability": "available",
        "query_profile_id": str(query_profile["query_profile_id"]),
        "query_family": str(query_profile["query_family"]),
        "default_overlay_id": str(preset_query_state["default_overlay_id"]),
        "enabled_overlay_ids": list(preset_query_state["enabled_overlay_ids"]),
        "default_reduction_profile_id": str(
            preset_query_state["default_reduction_profile_id"]
        ),
        "execution_summary": copy.deepcopy(
            dict(preset_execution["execution_summary"])
        ),
        "primary_graph_view_id": primary_graph_view_id,
        "graph_payload_references": {
            "primary_graph": _build_graph_payload_reference(
                preset_id=preset_id,
                graph_view_id=primary_graph_view_id,
            ),
            "overview_graph": _build_graph_payload_reference(
                preset_id=preset_id,
                graph_view_id="overview_graph",
            ),
            "focused_subgraph": _build_graph_payload_reference(
                preset_id=preset_id,
                graph_view_id="focused_subgraph",
            ),
            "pathway_highlights": pathway_reference,
        },
        "linked_session_target": _build_linked_session_target(
            blueprint=blueprint,
            linked_sessions=linked_sessions,
        ),
        "scientific_curation_required": bool(
            query_profile["scientific_curation_required"]
        ),
        "discovery_note": str(blueprint["discovery_note"]),
    }


def _build_unavailable_query_preset_record(
    *,
    blueprint: Mapping[str, Any],
    sequence_index: int,
    reason: str,
) -> dict[str, Any]:
    return {
        "preset_id": str(blueprint["preset_id"]),
        "display_name": str(blueprint["display_name"]),
        "description": str(blueprint["description"]),
        "sequence_index": sequence_index,
        "availability": "unavailable",
        "preferred_query_profile_ids": list(blueprint["preferred_query_profile_ids"]),
        "required_linked_session_kind": blueprint.get("required_linked_session_kind"),
        "unavailable_reason": str(reason),
    }


def _resolve_active_query_preset_id(
    *,
    active_query_profile_id: str,
    available_presets: Sequence[Mapping[str, Any]],
) -> str | None:
    available_by_id = {
        str(item["preset_id"]): copy.deepcopy(dict(item)) for item in available_presets
    }
    preferred_by_profile = {
        ACTIVE_SUBSET_SHELL_QUERY_PROFILE_ID: [OVERVIEW_CONTEXT_PRESET_ID],
        UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID: [UPSTREAM_HALO_PRESET_ID],
        DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID: [DOWNSTREAM_HALO_PRESET_ID],
        BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID: [
            OVERVIEW_CONTEXT_PRESET_ID,
            DASHBOARD_HANDOFF_PRESET_ID,
        ],
        PATHWAY_HIGHLIGHT_REVIEW_QUERY_PROFILE_ID: [
            PATHWAY_FOCUS_PRESET_ID,
            SHOWCASE_HANDOFF_PRESET_ID,
        ],
        DOWNSTREAM_MODULE_REVIEW_QUERY_PROFILE_ID: [
            SHOWCASE_HANDOFF_PRESET_ID,
            DOWNSTREAM_HALO_PRESET_ID,
        ],
    }
    for preset_id in preferred_by_profile.get(active_query_profile_id, []):
        if (
            preset_id in available_by_id
            and str(available_by_id[preset_id]["query_profile_id"])
            == active_query_profile_id
        ):
            return preset_id
    for item in available_presets:
        if str(item["query_profile_id"]) == active_query_profile_id:
            return str(item["preset_id"])
    if available_presets:
        return str(available_presets[0]["preset_id"])
    return None


def _build_graph_payload_reference(*, preset_id: str, graph_view_id: str) -> dict[str, Any]:
    return {
        "artifact_role_id": CONTEXT_VIEW_PAYLOAD_ROLE_ID,
        "payload_path": f"query_preset_payloads.{preset_id}.{graph_view_id}",
        "view_id": graph_view_id,
    }


def _query_preset_primary_graph_view_id(
    *,
    blueprint: Mapping[str, Any],
    preset_execution: Mapping[str, Any],
) -> str:
    preferred_graph_view_id = str(blueprint["primary_graph_view_id"])
    if (
        preferred_graph_view_id == "focused_subgraph"
        and not preset_execution["pathway_highlights"]
    ):
        return "overview_graph"
    return preferred_graph_view_id


def _build_linked_session_target(
    *,
    blueprint: Mapping[str, Any],
    linked_sessions: Mapping[str, Any],
) -> dict[str, Any] | None:
    required_linked_session_kind = blueprint.get("required_linked_session_kind")
    if required_linked_session_kind is None:
        return None
    linked_session = linked_sessions.get(str(required_linked_session_kind))
    if not isinstance(linked_session, Mapping):
        return None
    artifact_role_id = (
        SHOWCASE_SESSION_METADATA_ROLE_ID
        if str(required_linked_session_kind) == "showcase"
        else DASHBOARD_SESSION_METADATA_ROLE_ID
    )
    return {
        "session_kind": str(required_linked_session_kind),
        "artifact_role_id": artifact_role_id,
        "bundle_id": str(linked_session["bundle_id"]),
        "metadata_path": str(linked_session["metadata_path"]),
    }


def _build_context_query_catalog(
    *,
    whole_brain_context_session: Mapping[str, Any],
    source_mode: str,
    fixture_profile: Mapping[str, Any],
    query_profile_resolution: Mapping[str, Any],
    query_state: Mapping[str, Any],
    reduction_profile: Mapping[str, Any],
    metadata_facet_requests: Sequence[Mapping[str, Any]],
    downstream_module_requests: Sequence[Mapping[str, Any]],
    query_execution: Mapping[str, Any],
    query_preset_library: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "format_version": JSON_CONTEXT_QUERY_CATALOG_FORMAT,
        "contract_version": WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
        "plan_version": WHOLE_BRAIN_CONTEXT_SESSION_PLAN_VERSION,
        "bundle_reference": {
            "bundle_id": str(whole_brain_context_session["bundle_id"]),
            "context_spec_hash": str(whole_brain_context_session["context_spec_hash"]),
        },
        "source_mode": source_mode,
        "fixture_profile": copy.deepcopy(dict(fixture_profile)),
        "preset_library_id": str(query_preset_library["preset_library_id"]),
        "active_preset_id": query_preset_library["active_preset_id"],
        "available_preset_ids": list(query_preset_library["available_preset_ids"]),
        "preset_discovery_order": list(query_preset_library["preset_discovery_order"]),
        "handoff_preset_ids": copy.deepcopy(
            dict(query_preset_library["handoff_preset_ids"])
        ),
        "active_query_profile_id": str(query_profile_resolution["active_query_profile_id"]),
        "selected_query_profile_ids": list(query_profile_resolution["selected_query_profile_ids"]),
        "available_query_profile_ids": list(query_profile_resolution["available_query_profile_ids"]),
        "query_state": copy.deepcopy(dict(query_state)),
        "reduction_profile": copy.deepcopy(dict(reduction_profile)),
        "metadata_facet_requests": [copy.deepcopy(dict(item)) for item in metadata_facet_requests],
        "downstream_module_requests": [
            copy.deepcopy(dict(item)) for item in downstream_module_requests
        ],
        "reduction_controls": copy.deepcopy(
            dict(query_execution["reduction_controls"])
        ),
        "execution_summary": copy.deepcopy(
            dict(query_execution["execution_summary"])
        ),
        "available_query_profiles": [
            copy.deepcopy(dict(item))
            for item in query_profile_resolution["available_query_profiles"]
        ],
        "unavailable_query_profiles": [
            copy.deepcopy(dict(item))
            for item in query_profile_resolution["unavailable_query_profiles"]
        ],
        "available_query_presets": [
            copy.deepcopy(dict(item))
            for item in query_preset_library["available_query_presets"]
        ],
        "unavailable_query_presets": [
            copy.deepcopy(dict(item))
            for item in query_preset_library["unavailable_query_presets"]
        ],
    }


def _build_context_view_payload(
    *,
    whole_brain_context_session: Mapping[str, Any],
    source_mode: str,
    fixture_profile: Mapping[str, Any],
    manifest_reference: Mapping[str, Any] | None,
    selection_context: Mapping[str, Any],
    registry_sources: Mapping[str, Any],
    linked_sessions: Mapping[str, Any],
    query_profile_resolution: Mapping[str, Any],
    query_state: Mapping[str, Any],
    reduction_profile: Mapping[str, Any],
    metadata_facet_requests: Sequence[Mapping[str, Any]],
    downstream_module_requests: Sequence[Mapping[str, Any]],
    labeling_rules: Mapping[str, Any],
    query_execution: Mapping[str, Any],
    query_preset_library: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "format_version": JSON_CONTEXT_VIEW_PAYLOAD_FORMAT,
        "contract_version": WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
        "plan_version": WHOLE_BRAIN_CONTEXT_SESSION_PLAN_VERSION,
        "bundle_reference": {
            "bundle_id": str(whole_brain_context_session["bundle_id"]),
            "context_spec_hash": str(whole_brain_context_session["context_spec_hash"]),
            "bundle_directory": str(
                whole_brain_context_session["bundle_layout"]["bundle_directory"]
            ),
        },
        "source_mode": source_mode,
        "fixture_profile": copy.deepcopy(dict(fixture_profile)),
        "experiment_id": str(whole_brain_context_session["experiment_id"]),
        "manifest_reference": (
            None if manifest_reference is None else copy.deepcopy(dict(manifest_reference))
        ),
        "selection": copy.deepcopy(dict(selection_context)),
        "registry_sources": copy.deepcopy(dict(registry_sources)),
        "linked_sessions": copy.deepcopy(dict(linked_sessions)),
        "query_profile_resolution": copy.deepcopy(dict(query_profile_resolution)),
        "query_state": copy.deepcopy(dict(query_state)),
        "reduction_profile": copy.deepcopy(dict(reduction_profile)),
        "metadata_facet_requests": [copy.deepcopy(dict(item)) for item in metadata_facet_requests],
        "downstream_module_requests": [
            copy.deepcopy(dict(item)) for item in downstream_module_requests
        ],
        "labeling_rules": copy.deepcopy(dict(labeling_rules)),
        "query_execution": copy.deepcopy(dict(query_execution)),
        "active_preset_id": query_preset_library["active_preset_id"],
        "query_preset_payloads": copy.deepcopy(
            dict(query_preset_library["preset_payloads_by_id"])
        ),
        "representative_context": copy.deepcopy(
            dict(whole_brain_context_session["representative_context"])
        ),
        "artifact_inventory": [
            copy.deepcopy(dict(item))
            for item in whole_brain_context_session["artifact_references"]
        ],
    }


def _build_context_view_state(
    *,
    whole_brain_context_session: Mapping[str, Any],
    fixture_profile: Mapping[str, Any],
    manifest_reference: Mapping[str, Any] | None,
    selection_context: Mapping[str, Any],
    linked_sessions: Mapping[str, Any],
    query_profile_resolution: Mapping[str, Any],
    query_state: Mapping[str, Any],
    query_preset_library: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "format_version": JSON_CONTEXT_VIEW_STATE_FORMAT,
        "contract_version": WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
        "plan_version": WHOLE_BRAIN_CONTEXT_SESSION_PLAN_VERSION,
        "bundle_reference": {
            "bundle_id": str(whole_brain_context_session["bundle_id"]),
            "context_spec_hash": str(whole_brain_context_session["context_spec_hash"]),
        },
        "manifest_reference": (
            None if manifest_reference is None else copy.deepcopy(dict(manifest_reference))
        ),
        "active_query_profile_id": str(query_profile_resolution["active_query_profile_id"]),
        "selected_query_profile_ids": list(query_profile_resolution["selected_query_profile_ids"]),
        "fixture_profile": copy.deepcopy(dict(fixture_profile)),
        "active_preset_id": query_preset_library["active_preset_id"],
        "available_preset_ids": list(query_preset_library["available_preset_ids"]),
        "preset_discovery_order": list(query_preset_library["preset_discovery_order"]),
        "default_overlay_id": str(query_state["default_overlay_id"]),
        "enabled_overlay_ids": list(query_state["enabled_overlay_ids"]),
        "enabled_metadata_facet_ids": list(query_state["enabled_metadata_facet_ids"]),
        "default_reduction_profile_id": str(query_state["default_reduction_profile_id"]),
        "focus_root_ids": list(selection_context["selected_root_ids"]),
        "linked_dashboard": copy.deepcopy(dict(linked_sessions.get("dashboard") or {})),
        "linked_showcase": copy.deepcopy(dict(linked_sessions.get("showcase") or {})),
    }


def _extract_context_query_catalog_mapping(record: Mapping[str, Any]) -> dict[str, Any]:
    mapping = _require_mapping(record, field_name="record")
    if "context_query_catalog" in mapping:
        return _require_mapping(
            mapping["context_query_catalog"],
            field_name="record.context_query_catalog",
        )
    return mapping


def _build_linked_sessions(
    *,
    source_context: Mapping[str, Any],
    artifact_references_by_role: Mapping[str, Mapping[str, Any]],
    planned_artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    linked: dict[str, Any] = {}
    dashboard_ref = artifact_references_by_role.get(DASHBOARD_SESSION_METADATA_ROLE_ID)
    if dashboard_ref is not None:
        payload_ref = artifact_references_by_role.get(DASHBOARD_SESSION_PAYLOAD_ROLE_ID)
        state_ref = artifact_references_by_role.get(DASHBOARD_SESSION_STATE_ROLE_ID)
        metadata, payload, _state = _dashboard_records_for_reference_resolution(
            source_context=source_context,
            metadata_ref=dashboard_ref,
            payload_ref=payload_ref,
            state_ref=state_ref,
            planned_artifact_paths=planned_artifact_paths,
        )
        linked["dashboard"] = {
            "bundle_id": str(metadata["bundle_id"]),
            "metadata_path": str(Path(dashboard_ref["path"]).resolve()),
            "payload_path": (
                None
                if payload_ref is None
                else str(Path(payload_ref["path"]).resolve())
            ),
            "state_path": (
                None
                if state_ref is None
                else str(Path(state_ref["path"]).resolve())
            ),
            "origin": (
                "planned"
                if (
                    source_context.get("dashboard_context") is not None
                    and _reference_matches_planned_path(
                        dashboard_ref,
                        role_id=DASHBOARD_SESSION_METADATA_ROLE_ID,
                        planned_artifact_paths=planned_artifact_paths,
                    )
                )
                else "packaged"
            ),
            "selected_root_ids": (
                [] if payload is None else _dashboard_selected_root_ids(payload)
            ),
        }
    showcase_ref = artifact_references_by_role.get(SHOWCASE_SESSION_METADATA_ROLE_ID)
    if showcase_ref is not None:
        state_ref = artifact_references_by_role.get(SHOWCASE_PRESENTATION_STATE_ROLE_ID)
        metadata, state = _showcase_records_for_reference_resolution(
            source_context=source_context,
            metadata_ref=showcase_ref,
            state_ref=state_ref,
            planned_artifact_paths=planned_artifact_paths,
        )
        linked["showcase"] = {
            "bundle_id": str(metadata["bundle_id"]),
            "metadata_path": str(Path(showcase_ref["path"]).resolve()),
            "presentation_state_path": (
                None
                if state_ref is None
                else str(Path(state_ref["path"]).resolve())
            ),
            "focus_root_ids": [] if state is None else _showcase_focus_root_ids(state),
        }
    return linked


def _build_output_locations(
    whole_brain_context_session: Mapping[str, Any],
) -> dict[str, Any]:
    bundle_paths = discover_whole_brain_context_session_bundle_paths(
        whole_brain_context_session
    )
    return {
        "bundle_directory": str(
            Path(whole_brain_context_session["bundle_layout"]["bundle_directory"]).resolve()
        ),
        "metadata_path": str(bundle_paths[METADATA_JSON_KEY].resolve()),
        "context_view_payload_path": str(
            bundle_paths[CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID].resolve()
        ),
        "context_query_catalog_path": str(
            bundle_paths[CONTEXT_QUERY_CATALOG_ARTIFACT_ID].resolve()
        ),
        "context_view_state_path": str(
            bundle_paths[CONTEXT_VIEW_STATE_ARTIFACT_ID].resolve()
        ),
    }


def _planned_artifact_paths(record: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    dashboard_plan = record.get("dashboard_session_plan")
    if isinstance(dashboard_plan, Mapping):
        dashboard_session = _require_mapping(
            dashboard_plan.get("dashboard_session"),
            field_name="dashboard_session_plan.dashboard_session",
        )
        bundle_paths = discover_dashboard_session_bundle_paths(dashboard_session)
        result[DASHBOARD_SESSION_METADATA_ROLE_ID] = str(
            bundle_paths[DASHBOARD_METADATA_JSON_KEY].resolve()
        )
        result[DASHBOARD_SESSION_PAYLOAD_ROLE_ID] = str(
            bundle_paths[SESSION_PAYLOAD_ARTIFACT_ID].resolve()
        )
        result[DASHBOARD_SESSION_STATE_ROLE_ID] = str(
            bundle_paths[SESSION_STATE_ARTIFACT_ID].resolve()
        )
    return result


def _artifact_is_materialized(
    reference: Mapping[str, Any],
    planned_artifact_paths: Mapping[str, str],
) -> bool:
    path = str(Path(reference["path"]).resolve())
    if (
        str(reference["artifact_role_id"]) in planned_artifact_paths
        and path == str(Path(planned_artifact_paths[str(reference["artifact_role_id"])]).resolve())
    ):
        return True
    return Path(path).exists()


def _artifact_role_is_available(
    role_id: str,
    *,
    artifact_references_by_role: Mapping[str, Mapping[str, Any]],
    planned_artifact_paths: Mapping[str, str],
) -> bool:
    reference = artifact_references_by_role.get(str(role_id))
    if reference is None or str(reference.get("status")) != ASSET_STATUS_READY:
        return False
    return _artifact_is_materialized(reference, planned_artifact_paths)


def _artifact_source_summary(
    reference: Mapping[str, Any],
    planned_artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    path = Path(str(reference["path"])).resolve()
    return {
        "artifact_role_id": str(reference["artifact_role_id"]),
        "source_kind": str(reference["source_kind"]),
        "bundle_id": str(reference["bundle_id"]),
        "artifact_id": str(reference["artifact_id"]),
        "path": str(path),
        "status": str(reference["status"]),
        "exists": _artifact_is_materialized(reference, planned_artifact_paths),
    }


def _build_synapse_evidence_summary(
    *,
    path: Path,
    selected_root_ids: Sequence[int],
) -> dict[str, Any]:
    synapse_registry = _load_synapse_evidence_registry(path)
    selected_root_set = {int(root_id) for root_id in selected_root_ids}
    touching = synapse_registry[
        synapse_registry["pre_root_id"].isin(selected_root_set)
        | synapse_registry["post_root_id"].isin(selected_root_set)
    ].copy()
    if touching.empty:
        raise ValueError(
            "Local synapse registry does not contain any synapse evidence touching the "
            f"resolved active subset at {path}."
        )
    internal = touching[
        touching["pre_root_id"].isin(selected_root_set)
        & touching["post_root_id"].isin(selected_root_set)
    ]
    outgoing = touching[
        touching["pre_root_id"].isin(selected_root_set)
        & ~touching["post_root_id"].isin(selected_root_set)
    ]
    incoming = touching[
        ~touching["pre_root_id"].isin(selected_root_set)
        & touching["post_root_id"].isin(selected_root_set)
    ]
    context_root_ids = set(int(root_id) for root_id in outgoing["post_root_id"].tolist())
    context_root_ids |= set(int(root_id) for root_id in incoming["pre_root_id"].tolist())
    return {
        "synapse_row_count": int(len(synapse_registry)),
        "touching_active_subset_row_count": int(len(touching)),
        "selected_to_selected_row_count": int(len(internal)),
        "selected_to_context_row_count": int(len(outgoing)),
        "context_to_selected_row_count": int(len(incoming)),
        "context_neighbor_root_count": int(len(context_root_ids)),
        "context_neighbor_root_ids_preview": sorted(context_root_ids)[:12],
    }


def _load_synapse_evidence_registry(path: Path) -> pd.DataFrame:
    try:
        return load_synapse_registry(path)
    except ValueError as exc:
        df = pd.read_csv(path)
        required_columns = ["pre_root_id", "post_root_id"]
        missing_columns = [
            column for column in required_columns if column not in df.columns
        ]
        if missing_columns:
            raise ValueError(
                "Local synapse registry is incompatible with whole-brain context "
                f"planning at {path}: missing required columns {missing_columns!r}."
            ) from exc
        normalized = df.loc[:, required_columns].copy()
        for column in required_columns:
            numeric = pd.to_numeric(normalized[column], errors="coerce")
            if numeric.isna().any():
                raise ValueError(
                    "Local synapse registry is incompatible with whole-brain context "
                    f"planning at {path}: column {column!r} contains non-integer values."
                ) from exc
            normalized[column] = numeric.astype(int)
        return normalized


def _default_active_query_profile(available_query_profile_ids: Sequence[str]) -> str:
    for candidate in _ACTIVE_QUERY_PRIORITY:
        if candidate in set(available_query_profile_ids):
            return candidate
    return str(available_query_profile_ids[0])


def _normalize_requested_query_profiles(
    *,
    requested_query_profile_ids: Sequence[str] | None,
    active_query_profile_id: str,
    available_query_profile_ids: Sequence[str],
) -> list[str]:
    available_set = set(available_query_profile_ids)
    if requested_query_profile_ids is None:
        return [active_query_profile_id]
    normalized = _normalize_identifier_sequence(
        requested_query_profile_ids,
        field_name="query_profile_ids",
    )
    if active_query_profile_id not in normalized:
        normalized = [active_query_profile_id, *normalized]
    selected = [profile_id for profile_id in available_query_profile_ids if profile_id in set(normalized)]
    missing = [profile_id for profile_id in normalized if profile_id not in available_set]
    if missing:
        raise ValueError(
            "Requested whole-brain context query_profile_ids include unavailable profiles "
            f"{missing!r}."
        )
    return selected


def _validate_query_profile_combination(query_profile_ids: Sequence[str]) -> None:
    profile_set = set(query_profile_ids)
    if len(profile_set) <= 1:
        return
    if ACTIVE_SUBSET_SHELL_QUERY_PROFILE_ID in profile_set:
        raise ValueError(
            "Unsupported whole-brain-context query-profile combination: "
            "'active_subset_shell' must be requested alone."
        )
    if BIDIRECTIONAL_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID in profile_set and (
        "upstream_connectivity_context" in profile_set
        or DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID in profile_set
    ):
        raise ValueError(
            "Unsupported whole-brain-context query-profile combination: "
            "'bidirectional_connectivity_context' cannot be combined with directional "
            "connectivity profiles."
        )
    if profile_set & _REVIEW_ONLY_QUERY_PROFILE_IDS:
        raise ValueError(
            "Unsupported whole-brain-context query-profile combination: review-focused "
            "profiles must be requested alone in v1."
        )


def _build_manifest_reference(
    manifest_path: Path,
    manifest_payload: Mapping[str, Any],
) -> dict[str, Any]:
    return build_simulator_manifest_reference(
        experiment_id=_normalize_identifier(
            manifest_payload["experiment_id"],
            field_name="manifest.experiment_id",
        ),
        manifest_path=manifest_path,
        milestone=_normalize_identifier(
            manifest_payload["milestone"],
            field_name="manifest.milestone",
        ),
        manifest_id=_normalize_identifier(
            manifest_payload.get("experiment_id"),
            field_name="manifest.experiment_id",
        ),
        brief_version=_normalize_optional_identifier(
            manifest_payload.get("brief_version"),
            field_name="manifest.brief_version",
        ),
        hypothesis_version=_normalize_optional_identifier(
            manifest_payload.get("hypothesis_version"),
            field_name="manifest.hypothesis_version",
        ),
    )


def _build_active_anchor_records(
    root_ids: Sequence[int],
    subset_manifest_payload: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if subset_manifest_payload is None:
        return [{"root_id": int(root_id)} for root_id in root_ids]
    neurons = subset_manifest_payload.get("neurons")
    if not isinstance(neurons, Sequence) or isinstance(neurons, (str, bytes)):
        return [{"root_id": int(root_id)} for root_id in root_ids]
    records_by_root: dict[int, dict[str, Any]] = {}
    for item in neurons:
        if not isinstance(item, Mapping) or item.get("root_id") is None:
            continue
        root_id = int(item["root_id"])
        records_by_root[root_id] = {
            key: copy.deepcopy(value) for key, value in dict(item).items()
        }
    return [
        records_by_root.get(int(root_id), {"root_id": int(root_id)})
        for root_id in root_ids
    ]


def _anchor_metadata_facet_values(
    anchor_record: Mapping[str, Any],
    *,
    enabled_metadata_facet_ids: set[str],
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if "cell_class" in enabled_metadata_facet_ids:
        values["cell_class"] = (
            anchor_record.get("super_class")
            or anchor_record.get("class")
            or anchor_record.get("project_role")
            or ""
        )
    if "cell_type" in enabled_metadata_facet_ids:
        values["cell_type"] = (
            anchor_record.get("cell_type")
            or anchor_record.get("resolved_type")
            or anchor_record.get("primary_type")
            or ""
        )
    if "neuropil" in enabled_metadata_facet_ids:
        values["neuropil"] = anchor_record.get("neuropils") or ""
    if "side" in enabled_metadata_facet_ids:
        values["side"] = anchor_record.get("side") or anchor_record.get("hemisphere") or ""
    if "nt_type" in enabled_metadata_facet_ids:
        values["nt_type"] = anchor_record.get("nt_type") or ""
    if "selection_boundary_status" in enabled_metadata_facet_ids:
        values["selection_boundary_status"] = "active_selected"
    if "pathway_relevance_status" in enabled_metadata_facet_ids:
        values["pathway_relevance_status"] = "active_selected"
    return {
        key: value for key, value in values.items() if value not in {None, ""}
    }


def _dashboard_records_for_reference_resolution(
    *,
    source_context: Mapping[str, Any],
    metadata_ref: Mapping[str, Any],
    payload_ref: Mapping[str, Any] | None,
    state_ref: Mapping[str, Any] | None,
    planned_artifact_paths: Mapping[str, str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if payload_ref is None or state_ref is None:
        raise ValueError(
            "Whole-brain context planning requires dashboard metadata, payload, and state references."
        )
    dashboard_context = source_context.get("dashboard_context")
    if (
        isinstance(dashboard_context, Mapping)
        and str(dashboard_context.get("origin")) == "planned"
        and _reference_matches_planned_path(
            metadata_ref,
            role_id=DASHBOARD_SESSION_METADATA_ROLE_ID,
            planned_artifact_paths=planned_artifact_paths,
        )
        and _reference_matches_planned_path(
            payload_ref,
            role_id=DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
            planned_artifact_paths=planned_artifact_paths,
        )
        and _reference_matches_planned_path(
            state_ref,
            role_id=DASHBOARD_SESSION_STATE_ROLE_ID,
            planned_artifact_paths=planned_artifact_paths,
        )
    ):
        return (
            _require_mapping(dashboard_context["metadata"], field_name="dashboard_context.metadata"),
            _require_mapping(dashboard_context["payload"], field_name="dashboard_context.payload"),
            _require_mapping(dashboard_context["state"], field_name="dashboard_context.state"),
        )
    metadata = _load_dashboard_metadata_reference(
        metadata_ref,
        planned_artifact_paths=planned_artifact_paths,
    )
    payload = _load_json_mapping(
        Path(str(payload_ref["path"])).resolve(),
        field_name="dashboard_session_payload",
    )
    state = _load_json_mapping(
        Path(str(state_ref["path"])).resolve(),
        field_name="dashboard_session_state",
    )
    if str(metadata["bundle_id"]) != str(payload["bundle_reference"]["bundle_id"]):
        raise ValueError("dashboard_session metadata and payload must reference the same bundle_id.")
    if str(metadata["bundle_id"]) != str(state["bundle_reference"]["bundle_id"]):
        raise ValueError("dashboard_session metadata and state must reference the same bundle_id.")
    return metadata, payload, state


def _showcase_records_for_reference_resolution(
    *,
    source_context: Mapping[str, Any],
    metadata_ref: Mapping[str, Any],
    state_ref: Mapping[str, Any] | None,
    planned_artifact_paths: Mapping[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if state_ref is None:
        raise ValueError(
            "Whole-brain context planning requires showcase metadata and presentation-state references."
        )
    showcase_context = source_context.get("showcase_context")
    if isinstance(showcase_context, Mapping):
        metadata = _require_mapping(showcase_context["metadata"], field_name="showcase_context.metadata")
        state = _require_mapping(showcase_context["state"], field_name="showcase_context.state")
        if (
            str(Path(metadata_ref["path"]).resolve())
            == str(
                discover_showcase_session_bundle_paths(metadata)[SHOWCASE_METADATA_JSON_KEY].resolve()
            )
            and str(Path(state_ref["path"]).resolve())
            == str(
                discover_showcase_session_bundle_paths(metadata)[
                    SHOWCASE_PRESENTATION_STATE_ARTIFACT_ID
                ].resolve()
            )
        ):
            return metadata, state
    metadata = _load_showcase_metadata_reference(
        metadata_ref,
        planned_artifact_paths=planned_artifact_paths,
    )
    state = _load_showcase_state_reference(
        state_ref,
        metadata=metadata,
        planned_artifact_paths=planned_artifact_paths,
    )
    return metadata, state


def _reference_matches_planned_path(
    reference: Mapping[str, Any],
    *,
    role_id: str,
    planned_artifact_paths: Mapping[str, str],
) -> bool:
    planned_path = planned_artifact_paths.get(role_id)
    if planned_path is None:
        return False
    return str(Path(reference["path"]).resolve()) == str(Path(planned_path).resolve())


def _load_dashboard_metadata_reference(
    reference: Mapping[str, Any],
    *,
    planned_artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    path = Path(str(reference["path"])).resolve()
    if not path.exists():
        planned_path = planned_artifact_paths.get(DASHBOARD_SESSION_METADATA_ROLE_ID)
        if planned_path is None or path != Path(planned_path).resolve():
            raise ValueError(f"Dashboard session metadata is missing at {path}.")
    return load_dashboard_session_metadata(path)


def _load_dashboard_payload_reference(
    reference: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    planned_artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    path = Path(str(reference["path"])).resolve()
    if not path.exists():
        planned_path = planned_artifact_paths.get(DASHBOARD_SESSION_PAYLOAD_ROLE_ID)
        if planned_path is None or path != Path(planned_path).resolve():
            raise ValueError(f"Dashboard session payload is missing at {path}.")
        return _require_mapping(
            _require_mapping(metadata, field_name="dashboard_session").get("artifacts", {}),
            field_name="dashboard_session.artifacts",
        ) and _require_mapping(
            _load_planned_dashboard_payload(metadata, path),
            field_name="dashboard_session_payload",
        )
    payload = _load_json_mapping(path, field_name="dashboard_session_payload")
    if str(metadata["bundle_id"]) != str(payload["bundle_reference"]["bundle_id"]):
        raise ValueError("dashboard_session metadata and payload must reference the same bundle_id.")
    return payload


def _load_dashboard_state_reference(
    reference: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    planned_artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    path = Path(str(reference["path"])).resolve()
    if not path.exists():
        planned_path = planned_artifact_paths.get(DASHBOARD_SESSION_STATE_ROLE_ID)
        if planned_path is None or path != Path(planned_path).resolve():
            raise ValueError(f"Dashboard session state is missing at {path}.")
        return _load_planned_dashboard_state(metadata, path)
    state = _load_json_mapping(path, field_name="dashboard_session_state")
    if str(metadata["bundle_id"]) != str(state["bundle_reference"]["bundle_id"]):
        raise ValueError("dashboard_session metadata and state must reference the same bundle_id.")
    return state


def _load_showcase_metadata_reference(
    reference: Mapping[str, Any],
    *,
    planned_artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    del planned_artifact_paths
    path = Path(str(reference["path"])).resolve()
    if not path.exists():
        raise ValueError(f"Showcase session metadata is missing at {path}.")
    return load_showcase_session_metadata(path)


def _load_showcase_state_reference(
    reference: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    planned_artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    del metadata, planned_artifact_paths
    path = Path(str(reference["path"])).resolve()
    if not path.exists():
        raise ValueError(f"Showcase presentation state is missing at {path}.")
    return _load_json_mapping(path, field_name="showcase_presentation_state")


def _load_planned_dashboard_payload(
    metadata: Mapping[str, Any],
    path: Path,
) -> dict[str, Any]:
    del path
    bundle_paths = discover_dashboard_session_bundle_paths(metadata)
    return _load_json_mapping(
        bundle_paths[SESSION_PAYLOAD_ARTIFACT_ID],
        field_name="dashboard_session_payload",
    )


def _load_planned_dashboard_state(
    metadata: Mapping[str, Any],
    path: Path,
) -> dict[str, Any]:
    del path
    bundle_paths = discover_dashboard_session_bundle_paths(metadata)
    return _load_json_mapping(
        bundle_paths[SESSION_STATE_ARTIFACT_ID],
        field_name="dashboard_session_state",
    )


def _dashboard_selected_root_ids(payload: Mapping[str, Any]) -> list[int]:
    selection = _require_mapping(
        payload.get("selection", {}),
        field_name="dashboard_session_payload.selection",
    )
    root_ids = selection.get("selected_root_ids")
    if not isinstance(root_ids, Sequence) or isinstance(root_ids, (str, bytes)):
        raise ValueError(
            "dashboard_session_payload.selection.selected_root_ids must be a sequence."
        )
    return sorted({int(root_id) for root_id in root_ids})


def _showcase_focus_root_ids(state: Mapping[str, Any]) -> list[int]:
    root_ids = state.get("focus_root_ids")
    if not isinstance(root_ids, Sequence) or isinstance(root_ids, (str, bytes)):
        raise ValueError(
            "showcase_presentation_state.focus_root_ids must be a sequence."
        )
    return sorted({int(root_id) for root_id in root_ids})


def _artifact_reference_by_role(
    artifact_references: Sequence[Mapping[str, Any]],
    role_id: str,
) -> dict[str, Any] | None:
    for item in artifact_references:
        if str(item["artifact_role_id"]) == str(role_id):
            return copy.deepcopy(dict(item))
    return None


def _catalog_item_by_id(
    catalog: Sequence[Mapping[str, Any]],
    *,
    key_name: str,
    identifier: str,
) -> dict[str, Any]:
    for item in catalog:
        if str(item[key_name]) == str(identifier):
            return copy.deepcopy(dict(item))
    raise ValueError(f"Could not find {key_name}={identifier!r} in contract catalog.")


def _extract_subset_manifest_root_ids(
    payload: Mapping[str, Any],
    *,
    field_name: str,
) -> list[int]:
    raw_root_ids = payload.get("root_ids")
    if not isinstance(raw_root_ids, Sequence) or isinstance(raw_root_ids, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of root IDs.")
    normalized = sorted({int(root_id) for root_id in raw_root_ids})
    if not normalized:
        raise ValueError(f"{field_name} must contain at least one root ID.")
    return normalized


def _read_and_validate_root_ids(path: Path) -> list[int]:
    if not path.exists():
        raise ValueError(f"Selected-root roster is missing at {path}.")
    root_ids = sorted(int(root_id) for root_id in read_root_ids(path))
    if not root_ids:
        raise ValueError(f"Selected-root roster at {path} is empty.")
    if len(set(root_ids)) != len(root_ids):
        raise ValueError(
            f"Selected-root roster at {path} contains duplicate root IDs."
        )
    return root_ids


def _connectivity_bundle_id(path: str | Path) -> str:
    resolved = str(Path(path).resolve())
    return f"{LOCAL_CONNECTIVITY_SOURCE_KIND}:{_stable_hash({'path': resolved})[:16]}"


def _status_from_known_path(path: str | Path) -> str:
    return ASSET_STATUS_READY if Path(path).resolve().exists() else ASSET_STATUS_MISSING


def _stable_hash(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _normalize_raw_explicit_artifact_references(
    payload: Sequence[Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if payload is None:
        return {}
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("explicit_artifact_references must be a sequence of mappings.")
    normalized: dict[str, dict[str, Any]] = {}
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
        if role_id in normalized:
            raise ValueError(
                "explicit_artifact_references must not contain duplicate artifact_role_id "
                f"{role_id!r}."
            )
        normalized[role_id] = {
            key: copy.deepcopy(value) for key, value in dict(item).items()
        }
    return normalized


def _normalize_identifier_sequence(
    payload: Sequence[Any],
    *,
    field_name: str,
) -> list[str]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of identifiers.")
    normalized = {
        _normalize_identifier(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(payload)
    }
    return sorted(normalized)


def _normalize_optional_identifier(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _normalize_identifier(value, field_name=field_name)


def _normalize_optional_path_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(Path(_normalize_nonempty_string(value, field_name="path")).resolve())


def _require_mapping(payload: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return copy.deepcopy(dict(payload))


def _require_nonempty_string(value: Any, *, field_name: str) -> str:
    return _normalize_nonempty_string(value, field_name=field_name)


def _require_nonempty_path(value: Any, *, field_name: str) -> Path:
    return Path(_normalize_nonempty_string(value, field_name=field_name)).resolve()


def _load_json_mapping(path: str | Path, *, field_name: str) -> dict[str, Any]:
    file_path = Path(path).resolve()
    if not file_path.exists():
        raise ValueError(f"{field_name} is missing at {file_path}.")
    with file_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a JSON object.")
    return copy.deepcopy(dict(payload))


def _optional_load_json_mapping(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    resolved = path.resolve()
    if not resolved.exists():
        return None
    return _load_json_mapping(resolved, field_name=str(resolved))


def _load_dashboard_metadata_from_mapping(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if payload is None:
        raise ValueError("dashboard_session_metadata is required.")
    metadata_path = _require_mapping(payload, field_name="dashboard_session_metadata")["artifacts"][
        DASHBOARD_METADATA_JSON_KEY
    ]["path"]
    return load_dashboard_session_metadata(Path(str(metadata_path)).resolve())


def _load_showcase_metadata_from_mapping(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if payload is None:
        raise ValueError("showcase_session_metadata is required.")
    metadata_path = _require_mapping(payload, field_name="showcase_session_metadata")["artifacts"][
        SHOWCASE_METADATA_JSON_KEY
    ]["path"]
    return load_showcase_session_metadata(Path(str(metadata_path)).resolve())
