from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .dashboard_session_contract import (
    METADATA_JSON_KEY as DASHBOARD_METADATA_JSON_KEY,
    SESSION_PAYLOAD_ARTIFACT_ID,
    SESSION_STATE_ARTIFACT_ID,
    discover_dashboard_session_bundle_paths,
)
from .dashboard_session_planning import package_dashboard_session
from .io_utils import write_json
from .whole_brain_context_contract import (
    CONTEXT_QUERY_CATALOG_ARTIFACT_ID,
    CONTEXT_VIEW_PAYLOAD_ARTIFACT_ID,
    CONTEXT_VIEW_STATE_ARTIFACT_ID,
    DASHBOARD_SESSION_METADATA_ROLE_ID,
    DASHBOARD_SESSION_PAYLOAD_ROLE_ID,
    DASHBOARD_SESSION_STATE_ROLE_ID,
    JSON_CONTEXT_QUERY_CATALOG_FORMAT,
    JSON_CONTEXT_VIEW_PAYLOAD_FORMAT,
    JSON_CONTEXT_VIEW_STATE_FORMAT,
    METADATA_JSON_KEY,
    SHOWCASE_SESSION_METADATA_ROLE_ID,
    WHOLE_BRAIN_CONTEXT_SESSION_CONTRACT_VERSION,
    discover_whole_brain_context_session_bundle_paths,
    write_whole_brain_context_session_metadata,
)


def build_whole_brain_context_session_package_contents(
    *,
    plan_version: str,
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
        "context_query_catalog": _build_context_query_catalog(
            plan_version=plan_version,
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
        ),
        "context_view_payload": _build_context_view_payload(
            plan_version=plan_version,
            whole_brain_context_session=whole_brain_context_session,
            source_mode=source_mode,
            fixture_profile=fixture_profile,
            manifest_reference=manifest_reference,
            selection_context=selection_context,
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
        ),
        "context_view_state": _build_context_view_state(
            plan_version=plan_version,
            whole_brain_context_session=whole_brain_context_session,
            fixture_profile=fixture_profile,
            manifest_reference=manifest_reference,
            selection_context=selection_context,
            linked_sessions=linked_sessions,
            query_profile_resolution=query_profile_resolution,
            query_state=query_state,
            query_preset_library=query_preset_library,
        ),
        "output_locations": build_whole_brain_context_output_locations(
            whole_brain_context_session
        ),
    }


def package_whole_brain_context_session_bundle(
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_plan = _require_mapping(plan, field_name="plan")
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


def build_whole_brain_context_output_locations(
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


def _build_context_query_catalog(
    *,
    plan_version: str,
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
        "plan_version": str(plan_version),
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
    plan_version: str,
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
        "plan_version": str(plan_version),
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
    plan_version: str,
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
        "plan_version": str(plan_version),
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


def _artifact_reference_by_role(
    artifact_references: Sequence[Mapping[str, Any]],
    role_id: str,
) -> dict[str, Any] | None:
    for item in artifact_references:
        if str(item["artifact_role_id"]) == str(role_id):
            return copy.deepcopy(dict(item))
    return None


def _require_mapping(payload: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return copy.deepcopy(dict(payload))


__all__ = [
    "build_whole_brain_context_output_locations",
    "build_whole_brain_context_session_package_contents",
    "package_whole_brain_context_session_bundle",
]
