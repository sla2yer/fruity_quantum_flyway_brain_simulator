from __future__ import annotations

import copy
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from .config import load_config
from .registry import load_synapse_registry
from .whole_brain_context_contract import (
    ACTIVE_BOUNDARY_OVERLAY_ID,
    ACTIVE_INTERNAL_EDGE_ROLE_ID,
    ACTIVE_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
    ACTIVE_SELECTED_NODE_ROLE_ID,
    ACTIVE_SUBSET_CONTEXT_LAYER_ID,
    BOTH_METADATA_FACET_SCOPE,
    CONTEXT_INTERNAL_EDGE_ROLE_ID,
    CONTEXT_ONLY_NODE_ROLE_ID,
    CONTEXT_PATHWAY_HIGHLIGHT_NODE_ROLE_ID,
    CONTEXT_TO_ACTIVE_EDGE_ROLE_ID,
    DOWNSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
    DOWNSTREAM_CONTEXT_LAYER_ID,
    DOWNSTREAM_GRAPH_OVERLAY_ID,
    DOWNSTREAM_MODULE_CONTEXT_LAYER_ID,
    DOWNSTREAM_MODULE_REVIEW_QUERY_PROFILE_ID,
    DOWNSTREAM_MODULE_REVIEW_QUERY_FAMILY,
    INTERNAL_EDGE_DIRECTION_FAMILY,
    LOCAL_SHELL_QUERY_FAMILY,
    METADATA_FACET_BADGES_OVERLAY_ID,
    PATHWAY_HIGHLIGHT_CONTEXT_LAYER_ID,
    PATHWAY_HIGHLIGHT_EDGE_ROLE_ID,
    PATHWAY_HIGHLIGHT_OVERLAY_ID,
    PATHWAY_HIGHLIGHT_REVIEW_QUERY_PROFILE_ID,
    PATHWAY_REVIEW_QUERY_FAMILY,
    SUMMARY_EDGE_DIRECTION_FAMILY,
    UPSTREAM_CONNECTIVITY_CONTEXT_QUERY_PROFILE_ID,
    UPSTREAM_CONTEXT_LAYER_ID,
    UPSTREAM_CONTEXT_QUERY_FAMILY,
    UPSTREAM_GRAPH_OVERLAY_ID,
    ACTIVE_TO_CONTEXT_EDGE_ROLE_ID,
    BIDIRECTIONAL_CONTEXT_QUERY_FAMILY,
    DOWNSTREAM_CONTEXT_QUERY_FAMILY,
    DOWNSTREAM_MODULE_OVERLAY_ID,
    DOWNSTREAM_MODULE_SUMMARY_EDGE_ROLE_ID,
    get_whole_brain_context_query_profile_definition,
)


WHOLE_BRAIN_CONTEXT_QUERY_RESULT_VERSION = "whole_brain_context_query_result.v1"

SYNAPSE_COUNT_DESC_RANKING_POLICY = "synapse_count_desc"
WEIGHTED_SYNAPSE_DESC_RANKING_POLICY = "weighted_synapse_desc"
SUPPORTED_EDGE_RANKING_POLICIES = (
    SYNAPSE_COUNT_DESC_RANKING_POLICY,
    WEIGHTED_SYNAPSE_DESC_RANKING_POLICY,
)

TOP_RANKED_PATHWAY_EXTRACTION_MODE = "top_ranked_paths"
TARGETED_PATHWAY_EXTRACTION_MODE = "targeted_paths"
SUPPORTED_PATHWAY_EXTRACTION_MODES = (
    TOP_RANKED_PATHWAY_EXTRACTION_MODE,
    TARGETED_PATHWAY_EXTRACTION_MODE,
)

_DEFAULT_MAX_HOPS_BY_REDUCTION_PROFILE_ID = {
    "local_shell_compact": 0,
    "balanced_neighborhood": 2,
    "pathway_focus": 3,
    "downstream_module_collapsed": 2,
}

_NODE_RECORD_SORT_ORDER = {
    ACTIVE_SELECTED_NODE_ROLE_ID: 0,
    CONTEXT_ONLY_NODE_ROLE_ID: 1,
    ACTIVE_PATHWAY_HIGHLIGHT_NODE_ROLE_ID: 2,
    CONTEXT_PATHWAY_HIGHLIGHT_NODE_ROLE_ID: 3,
}

_EDGE_RECORD_SORT_ORDER = {
    ACTIVE_INTERNAL_EDGE_ROLE_ID: 0,
    ACTIVE_TO_CONTEXT_EDGE_ROLE_ID: 1,
    CONTEXT_TO_ACTIVE_EDGE_ROLE_ID: 2,
    CONTEXT_INTERNAL_EDGE_ROLE_ID: 3,
    PATHWAY_HIGHLIGHT_EDGE_ROLE_ID: 4,
    DOWNSTREAM_MODULE_SUMMARY_EDGE_ROLE_ID: 5,
}


class WholeBrainContextQueryError(ValueError):
    """Raised when a local Milestone 17 context query cannot be executed honestly."""


def normalize_whole_brain_context_reduction_controls(
    reduction_profile: Mapping[str, Any],
    *,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    profile = _require_mapping(reduction_profile, field_name="reduction_profile")
    normalized = {
        "reduction_profile_id": _require_nonempty_identifier(
            profile.get("reduction_profile_id"),
            field_name="reduction_profile.reduction_profile_id",
        ),
        "max_hops": _coerce_nonnegative_int(
            profile.get(
                "max_hops",
                _DEFAULT_MAX_HOPS_BY_REDUCTION_PROFILE_ID.get(
                    str(profile.get("reduction_profile_id")),
                    2,
                ),
            ),
            field_name="reduction_profile.max_hops",
        ),
        "max_context_node_count": _coerce_nonnegative_int(
            profile.get("max_context_node_count", 0),
            field_name="reduction_profile.max_context_node_count",
        ),
        "max_edge_count": _coerce_nonnegative_int(
            profile.get("max_edge_count", 0),
            field_name="reduction_profile.max_edge_count",
        ),
        "max_pathway_highlight_count": _coerce_nonnegative_int(
            profile.get("max_pathway_highlight_count", 0),
            field_name="reduction_profile.max_pathway_highlight_count",
        ),
        "max_downstream_module_count": _coerce_nonnegative_int(
            profile.get("max_downstream_module_count", 0),
            field_name="reduction_profile.max_downstream_module_count",
        ),
        "preserve_active_subset": bool(profile.get("preserve_active_subset", True)),
        "edge_ranking_policy": _normalize_edge_ranking_policy(
            profile.get("edge_ranking_policy", SYNAPSE_COUNT_DESC_RANKING_POLICY),
            field_name="reduction_profile.edge_ranking_policy",
        ),
        "pathway_edge_ranking_policy": _normalize_edge_ranking_policy(
            profile.get(
                "pathway_edge_ranking_policy",
                profile.get("edge_ranking_policy", SYNAPSE_COUNT_DESC_RANKING_POLICY),
            ),
            field_name="reduction_profile.pathway_edge_ranking_policy",
        ),
        "pathway_extraction_mode": _normalize_pathway_extraction_mode(
            profile.get(
                "pathway_extraction_mode",
                TOP_RANKED_PATHWAY_EXTRACTION_MODE,
            ),
            field_name="reduction_profile.pathway_extraction_mode",
        ),
        "allowed_neuropils": _normalize_identifier_sequence(
            profile.get("allowed_neuropils", []),
            field_name="reduction_profile.allowed_neuropils",
        ),
        "allowed_cell_classes": _normalize_identifier_sequence(
            profile.get("allowed_cell_classes", []),
            field_name="reduction_profile.allowed_cell_classes",
        ),
        "pathway_target_root_ids": _normalize_root_id_sequence(
            profile.get("pathway_target_root_ids", []),
            field_name="reduction_profile.pathway_target_root_ids",
        ),
    }
    if overrides is None:
        return normalized
    raw_overrides = _require_mapping(overrides, field_name="reduction_controls")
    for field_name in (
        "max_hops",
        "max_context_node_count",
        "max_edge_count",
        "max_pathway_highlight_count",
        "max_downstream_module_count",
    ):
        if field_name in raw_overrides:
            normalized[field_name] = _coerce_nonnegative_int(
                raw_overrides[field_name],
                field_name=f"reduction_controls.{field_name}",
            )
    if "preserve_active_subset" in raw_overrides:
        normalized["preserve_active_subset"] = bool(
            raw_overrides["preserve_active_subset"]
        )
    if "edge_ranking_policy" in raw_overrides:
        normalized["edge_ranking_policy"] = _normalize_edge_ranking_policy(
            raw_overrides["edge_ranking_policy"],
            field_name="reduction_controls.edge_ranking_policy",
        )
    if "pathway_edge_ranking_policy" in raw_overrides:
        normalized["pathway_edge_ranking_policy"] = _normalize_edge_ranking_policy(
            raw_overrides["pathway_edge_ranking_policy"],
            field_name="reduction_controls.pathway_edge_ranking_policy",
        )
    if "pathway_extraction_mode" in raw_overrides:
        normalized["pathway_extraction_mode"] = _normalize_pathway_extraction_mode(
            raw_overrides["pathway_extraction_mode"],
            field_name="reduction_controls.pathway_extraction_mode",
        )
    if "allowed_neuropils" in raw_overrides:
        normalized["allowed_neuropils"] = _normalize_identifier_sequence(
            raw_overrides["allowed_neuropils"],
            field_name="reduction_controls.allowed_neuropils",
        )
    if "allowed_cell_classes" in raw_overrides:
        normalized["allowed_cell_classes"] = _normalize_identifier_sequence(
            raw_overrides["allowed_cell_classes"],
            field_name="reduction_controls.allowed_cell_classes",
        )
    if "pathway_target_root_ids" in raw_overrides:
        normalized["pathway_target_root_ids"] = _normalize_root_id_sequence(
            raw_overrides["pathway_target_root_ids"],
            field_name="reduction_controls.pathway_target_root_ids",
        )
    return normalized


def execute_whole_brain_context_query(
    plan: Mapping[str, Any],
    *,
    synapse_registry: str | Path | pd.DataFrame | Sequence[Mapping[str, Any]] | None = None,
    node_metadata_registry: str
    | Path
    | pd.DataFrame
    | Sequence[Mapping[str, Any]]
    | None = None,
    reduction_controls: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_plan = _require_mapping(plan, field_name="plan")
    selection = _require_mapping(normalized_plan.get("selection"), field_name="plan.selection")
    query_state = _require_mapping(
        normalized_plan.get("query_state"),
        field_name="plan.query_state",
    )
    query_profile_resolution = _require_mapping(
        normalized_plan.get("query_profile_resolution"),
        field_name="plan.query_profile_resolution",
    )
    reduction_profile = _require_mapping(
        normalized_plan.get("reduction_profile"),
        field_name="plan.reduction_profile",
    )
    query_profile_id = _require_nonempty_identifier(
        query_profile_resolution.get("active_query_profile_id", query_state.get("query_profile_id")),
        field_name="plan.query_profile_resolution.active_query_profile_id",
    )
    query_profile = get_whole_brain_context_query_profile_definition(query_profile_id)
    query_family = str(query_profile["query_family"])
    enabled_overlays = {
        _require_nonempty_identifier(value, field_name="plan.query_state.enabled_overlay_ids")
        for value in query_state.get("enabled_overlay_ids", [])
    }
    enabled_facets = {
        _require_nonempty_identifier(
            value,
            field_name="plan.query_state.enabled_metadata_facet_ids",
        )
        for value in query_state.get("enabled_metadata_facet_ids", [])
    }
    active_root_ids = _normalize_root_id_sequence(
        selection.get("selected_root_ids", []),
        field_name="plan.selection.selected_root_ids",
    )
    if not active_root_ids:
        raise WholeBrainContextQueryError(
            "Whole-brain context query execution requires at least one selected_root_id."
        )
    active_root_set = set(active_root_ids)
    active_anchor_records = _normalize_active_anchor_records(
        selection.get("active_anchor_records", []),
        active_root_ids=active_root_ids,
    )
    resolved_reduction_controls = normalize_whole_brain_context_reduction_controls(
        reduction_profile,
        overrides=reduction_controls,
    )

    synapse_df, synapse_source = _resolve_synapse_registry(
        normalized_plan,
        query_family=query_family,
        override=synapse_registry,
        reduction_controls=resolved_reduction_controls,
    )
    node_metadata_df, node_metadata_source = _resolve_node_metadata_registry(
        normalized_plan,
        override=node_metadata_registry,
    )
    metadata_by_root = _build_node_metadata_by_root(
        node_metadata_df=node_metadata_df,
        active_anchor_records=active_anchor_records,
    )
    aggregated_edges, incident_stats = _aggregate_synapse_edges(synapse_df)
    _enrich_metadata_from_incident_stats(
        metadata_by_root=metadata_by_root,
        incident_stats=incident_stats,
    )

    active_internal_edges = [
        edge
        for edge in aggregated_edges
        if edge["source_root_id"] in active_root_set
        and edge["target_root_id"] in active_root_set
    ]
    if query_family == LOCAL_SHELL_QUERY_FAMILY or synapse_df.empty:
        selected_context_root_ids: set[int] = set()
        selected_candidate_records: list[dict[str, Any]] = []
        selected_biological_edges = list(active_internal_edges)
        path_registry = {}
        focused_path_records: list[dict[str, Any]] = []
        highlight_path_records: list[dict[str, Any]] = []
        directional_membership: dict[int, set[str]] = {root_id: set() for root_id in active_root_ids}
        query_status = (
            "available" if query_family == LOCAL_SHELL_QUERY_FAMILY else "partial"
        )
        query_reason = (
            None
            if query_family == LOCAL_SHELL_QUERY_FAMILY
            else "No local synapse rows survived the declared filter set."
        )
    else:
        if (
            resolved_reduction_controls["allowed_cell_classes"]
            and node_metadata_df is None
        ):
            raise WholeBrainContextQueryError(
                "Whole-brain context query execution requires a local node metadata registry "
                "to apply allowed_cell_classes filters."
            )
        adjacency = _build_adjacency(aggregated_edges)
        traversal = _build_traversal_registry(
            active_root_ids=active_root_ids,
            active_root_set=active_root_set,
            adjacency=adjacency,
            query_family=query_family,
            reduction_controls=resolved_reduction_controls,
            metadata_by_root=metadata_by_root,
        )
        directional_membership = traversal["directional_membership"]
        selected_context_root_ids, selected_candidate_records, selected_required_edge_keys = (
            _select_context_candidates(
                traversal_registry=traversal["candidate_registry"],
                active_internal_edges=active_internal_edges,
                reduction_controls=resolved_reduction_controls,
                active_root_set=active_root_set,
            )
        )
        selected_biological_edges = _select_biological_edges(
            aggregated_edges=aggregated_edges,
            active_root_set=active_root_set,
            selected_context_root_ids=selected_context_root_ids,
            required_edge_keys=selected_required_edge_keys,
            reduction_controls=resolved_reduction_controls,
        )
        path_registry = traversal["path_registry"]
        highlight_path_records = _build_pathway_highlight_records(
            candidate_records=selected_candidate_records,
            path_registry=path_registry,
            reduction_controls=resolved_reduction_controls,
            query_family=query_family,
        )
        focused_path_records = (
            highlight_path_records
            if highlight_path_records
            else _default_focused_path_records(selected_candidate_records, path_registry)
        )
        query_status = "available" if selected_context_root_ids else "partial"
        query_reason = None if selected_context_root_ids else "No context roots fit the declared reduction budget."

    highlight_root_ids = {
        root_id
        for item in highlight_path_records
        for root_id in item["node_root_ids"]
    }
    highlight_edge_keys = {
        tuple(item)
        for record in highlight_path_records
        for item in record["edge_key_pairs"]
    }

    base_node_records = _build_base_node_records(
        active_root_ids=active_root_ids,
        active_root_set=active_root_set,
        selected_context_root_ids=selected_context_root_ids,
        active_anchor_records=active_anchor_records,
        metadata_by_root=metadata_by_root,
        enabled_overlays=enabled_overlays,
        enabled_facets=enabled_facets,
        directional_membership=directional_membership,
        path_registry=path_registry,
        highlight_root_ids=highlight_root_ids,
    )
    highlight_node_records = _build_highlight_node_records(
        highlight_root_ids=highlight_root_ids,
        active_root_set=active_root_set,
        metadata_by_root=metadata_by_root,
        enabled_overlays=enabled_overlays,
        enabled_facets=enabled_facets,
    )
    base_edge_records = _build_base_edge_records(
        selected_biological_edges=selected_biological_edges,
        active_root_set=active_root_set,
        enabled_overlays=enabled_overlays,
        directional_membership=directional_membership,
        highlight_edge_keys=highlight_edge_keys,
    )
    highlight_edge_records = _build_highlight_edge_records(
        selected_biological_edges=selected_biological_edges,
        highlight_edge_keys=highlight_edge_keys,
    )
    downstream_module_records = _build_downstream_module_records(
        plan=normalized_plan,
        metadata_by_root=metadata_by_root,
        selected_context_root_ids=selected_context_root_ids,
        directional_membership=directional_membership,
        reduction_controls=resolved_reduction_controls,
        enabled_overlays=enabled_overlays,
        enabled_facets=enabled_facets,
    )

    overview_node_records = _sort_node_records(base_node_records + highlight_node_records)
    overview_edge_records = _sort_edge_records(base_edge_records + highlight_edge_records)
    overview_graph = _build_graph_view(
        view_id="overview_graph",
        display_name="Overview Graph",
        description="Budgeted Milestone 17 neighborhood around the active subset.",
        node_records=overview_node_records,
        edge_records=overview_edge_records,
        downstream_module_records=downstream_module_records,
        highlight_path_records=highlight_path_records,
    )
    representative_context = {
        "node_records": copy.deepcopy(_sort_node_records(base_node_records)),
        "edge_records": copy.deepcopy(overview_edge_records),
        "downstream_module_records": copy.deepcopy(downstream_module_records),
    }
    focused_subgraph = _build_focused_subgraph(
        base_node_records=base_node_records,
        highlight_node_records=highlight_node_records,
        base_edge_records=base_edge_records,
        highlight_edge_records=highlight_edge_records,
        downstream_module_records=downstream_module_records,
        focused_path_records=focused_path_records,
    )
    summary = {
        "status": query_status,
        "reason": query_reason,
        "active_root_count": len(active_root_ids),
        "context_root_count": len(selected_context_root_ids),
        "overview_node_record_count": len(overview_node_records),
        "overview_edge_record_count": len(overview_edge_records),
        "highlight_path_count": len(highlight_path_records),
        "downstream_module_count": len(downstream_module_records),
        "synapse_row_count_considered": int(len(synapse_df)),
        "biological_edge_count_considered": int(len(aggregated_edges)),
        "context_candidate_count": int(
            0 if query_family == LOCAL_SHELL_QUERY_FAMILY else len(path_registry)
        ),
        "active_internal_edge_count": len(active_internal_edges),
    }
    return {
        "format_version": WHOLE_BRAIN_CONTEXT_QUERY_RESULT_VERSION,
        "query_profile_id": query_profile_id,
        "query_family": query_family,
        "reduction_controls": resolved_reduction_controls,
        "input_sources": {
            "synapse_registry": synapse_source,
            "node_metadata_registry": node_metadata_source,
        },
        "execution_summary": summary,
        "representative_context": representative_context,
        "overview_graph": overview_graph,
        "focused_subgraph": focused_subgraph,
        "pathway_highlights": highlight_path_records,
    }


def _resolve_synapse_registry(
    plan: Mapping[str, Any],
    *,
    query_family: str,
    override: str | Path | pd.DataFrame | Sequence[Mapping[str, Any]] | None,
    reduction_controls: Mapping[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    source = override
    source_path = None
    if source is None:
        registry_sources = plan.get("registry_sources")
        if isinstance(registry_sources, Mapping):
            synapse_source = registry_sources.get("synapse_registry")
            if isinstance(synapse_source, Mapping):
                source_path = synapse_source.get("path")
    if source is None and source_path is not None:
        source = source_path
    if source is None:
        if query_family == LOCAL_SHELL_QUERY_FAMILY:
            return (
                pd.DataFrame(columns=["pre_root_id", "post_root_id"]),
                {
                    "availability": "absent",
                    "path": None,
                    "reason": "local_shell_query_does_not_require_synapse_registry",
                },
            )
        raise WholeBrainContextQueryError(
            "Whole-brain context query execution requires a local synapse registry for "
            f"query_family {query_family!r}."
        )
    frame = _coerce_synapse_registry_frame(source)
    filtered = frame.copy()
    if reduction_controls["allowed_neuropils"]:
        neuropil_allow = {str(item).upper() for item in reduction_controls["allowed_neuropils"]}
        neuropil_series = (
            filtered["neuropil"].fillna("").astype("string").str.upper()
            if "neuropil" in filtered.columns
            else pd.Series("", index=filtered.index, dtype="string")
        )
        filtered = filtered.loc[neuropil_series.isin(neuropil_allow)].copy()
    return (
        filtered,
        {
            "availability": "available",
            "path": None if not isinstance(source, (str, Path)) else str(Path(source).resolve()),
            "row_count": int(len(filtered)),
            "filtered_by_neuropils": list(reduction_controls["allowed_neuropils"]),
        },
    )


def _resolve_node_metadata_registry(
    plan: Mapping[str, Any],
    *,
    override: str | Path | pd.DataFrame | Sequence[Mapping[str, Any]] | None,
) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    source = override
    if source is not None:
        frame = _coerce_node_metadata_frame(source)
        return (
            frame,
            {
                "availability": "available",
                "path": None if not isinstance(source, (str, Path)) else str(Path(source).resolve()),
                "row_count": int(len(frame)),
                "source_kind": "override",
            },
        )
    config_path = plan.get("config_path")
    if config_path is None:
        return (None, {"availability": "absent", "path": None, "source_kind": "none"})
    try:
        cfg = load_config(config_path)
    except Exception:
        return (None, {"availability": "absent", "path": None, "source_kind": "none"})
    paths_cfg = _require_mapping(cfg.get("paths", {}), field_name="config.paths")
    neuron_registry_path = _existing_path(paths_cfg.get("neuron_registry_csv"))
    if neuron_registry_path is not None:
        frame = _coerce_node_metadata_frame(neuron_registry_path)
        return (
            frame,
            {
                "availability": "available",
                "path": str(neuron_registry_path.resolve()),
                "row_count": int(len(frame)),
                "source_kind": "neuron_registry",
            },
        )
    merged = _load_raw_node_metadata(paths_cfg)
    if merged is None:
        return (None, {"availability": "absent", "path": None, "source_kind": "none"})
    return (
        merged,
        {
            "availability": "available",
            "path": merged.attrs.get("source_path"),
            "row_count": int(len(merged)),
            "source_kind": "raw_codex_metadata",
        },
    )


def _load_raw_node_metadata(paths_cfg: Mapping[str, Any]) -> pd.DataFrame | None:
    classification_path = _existing_path(paths_cfg.get("classification_csv"))
    if classification_path is None:
        return None
    classification = pd.read_csv(classification_path)
    if "root_id" not in classification.columns:
        raise WholeBrainContextQueryError(
            f"Raw node metadata at {classification_path} is missing a root_id column."
        )
    normalized = classification.copy()
    normalized["root_id"] = _coerce_root_id_series(normalized["root_id"], "classification.root_id")
    keep_columns = [
        column
        for column in (
            "root_id",
            "super_class",
            "class",
            "sub_class",
            "hemilineage",
            "side",
            "nerve",
        )
        if column in normalized.columns
    ]
    result = normalized.loc[:, keep_columns].drop_duplicates(subset=["root_id"]).copy()
    cell_type_path = _discover_optional_raw_metadata_path(
        paths_cfg,
        explicit_key="cell_types_csv",
        file_names=[
            "cell_types.csv",
            "cell_types.csv.gz",
            "consolidated_cell_types.csv",
            "consolidated_cell_types.csv.gz",
        ],
    )
    if cell_type_path is not None:
        cell_types = pd.read_csv(cell_type_path)
        if "root_id" in cell_types.columns:
            cell_types = cell_types.copy()
            cell_types["root_id"] = _coerce_root_id_series(
                cell_types["root_id"],
                "cell_types.root_id",
            )
            rename_map = {}
            if "primary_type" in cell_types.columns:
                rename_map["primary_type"] = "primary_type"
            if "additional_type(s)" in cell_types.columns:
                rename_map["additional_type(s)"] = "additional_types"
            cell_types = cell_types.rename(columns=rename_map)
            keep = [
                column
                for column in ("root_id", "primary_type", "additional_types")
                if column in cell_types.columns
            ]
            result = result.merge(
                cell_types.loc[:, keep].drop_duplicates(subset=["root_id"]),
                on="root_id",
                how="left",
            )
    nt_path = _discover_optional_raw_metadata_path(
        paths_cfg,
        explicit_key="neurotransmitter_predictions_csv",
        file_names=[
            "neurotransmitter_type_predictions.csv",
            "neurons.csv",
            "neurons.csv.gz",
        ],
    )
    if nt_path is not None:
        nt_df = pd.read_csv(nt_path)
        if "root_id" in nt_df.columns:
            nt_df = nt_df.copy()
            nt_df["root_id"] = _coerce_root_id_series(nt_df["root_id"], "nt_predictions.root_id")
            keep = [column for column in ("root_id", "nt_type") if column in nt_df.columns]
            result = result.merge(
                nt_df.loc[:, keep].drop_duplicates(subset=["root_id"]),
                on="root_id",
                how="left",
            )
    result.attrs["source_path"] = str(classification_path.resolve())
    return _coerce_node_metadata_frame(result)


def _discover_optional_raw_metadata_path(
    paths_cfg: Mapping[str, Any],
    *,
    explicit_key: str,
    file_names: Sequence[str],
) -> Path | None:
    explicit_path = _existing_path(paths_cfg.get(explicit_key))
    if explicit_path is not None:
        return explicit_path
    raw_dir = _existing_path(paths_cfg.get("codex_raw_dir"))
    if raw_dir is None:
        return None
    for file_name in file_names:
        candidate = raw_dir / file_name
        if candidate.exists():
            return candidate
    return None


def _coerce_synapse_registry_frame(
    source: str | Path | pd.DataFrame | Sequence[Mapping[str, Any]],
) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        df = source.copy()
    elif isinstance(source, (str, Path)):
        path = Path(source).resolve()
        try:
            df = load_synapse_registry(path)
        except Exception:
            df = pd.read_csv(path)
    elif isinstance(source, Sequence) and not isinstance(source, (str, bytes)):
        df = pd.DataFrame([copy.deepcopy(dict(item)) for item in source])
    else:
        raise WholeBrainContextQueryError(
            f"Unsupported synapse_registry source {type(source)!r}."
        )
    required_columns = ("pre_root_id", "post_root_id")
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise WholeBrainContextQueryError(
            "Whole-brain context synapse input is missing required columns "
            f"{missing!r}."
        )
    normalized = df.copy()
    normalized["pre_root_id"] = _coerce_root_id_series(
        normalized["pre_root_id"],
        "synapse_registry.pre_root_id",
    )
    normalized["post_root_id"] = _coerce_root_id_series(
        normalized["post_root_id"],
        "synapse_registry.post_root_id",
    )
    if "weight" not in normalized.columns:
        normalized["weight"] = 1.0
    normalized["weight"] = pd.to_numeric(normalized["weight"], errors="coerce").fillna(1.0)
    if "confidence" not in normalized.columns:
        normalized["confidence"] = pd.NA
    normalized["confidence"] = pd.to_numeric(normalized["confidence"], errors="coerce")
    if "neuropil" not in normalized.columns:
        normalized["neuropil"] = ""
    normalized["neuropil"] = normalized["neuropil"].fillna("").astype("string")
    if "nt_type" not in normalized.columns:
        normalized["nt_type"] = ""
    normalized["nt_type"] = normalized["nt_type"].fillna("").astype("string").str.upper()
    if "synapse_row_id" not in normalized.columns:
        normalized["synapse_row_id"] = [
            f"row-{index:06d}" for index in range(1, len(normalized) + 1)
        ]
    normalized["synapse_row_id"] = normalized["synapse_row_id"].fillna("").astype("string")
    if "source_row_number" not in normalized.columns:
        normalized["source_row_number"] = list(range(1, len(normalized) + 1))
    source_row_numbers = pd.to_numeric(
        normalized["source_row_number"],
        errors="coerce",
    )
    if source_row_numbers.isna().any():
        fallback_numbers = pd.Series(
            list(range(1, len(normalized) + 1)),
            index=normalized.index,
            dtype="int64",
        )
        source_row_numbers = source_row_numbers.where(
            ~source_row_numbers.isna(),
            fallback_numbers,
        )
    normalized["source_row_number"] = source_row_numbers.astype(int)
    normalized = normalized.sort_values(
        by=["pre_root_id", "post_root_id", "source_row_number", "synapse_row_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    return normalized


def _coerce_node_metadata_frame(
    source: str | Path | pd.DataFrame | Sequence[Mapping[str, Any]],
) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        df = source.copy()
    elif isinstance(source, (str, Path)):
        df = pd.read_csv(Path(source).resolve())
    elif isinstance(source, Sequence) and not isinstance(source, (str, bytes)):
        df = pd.DataFrame([copy.deepcopy(dict(item)) for item in source])
    else:
        raise WholeBrainContextQueryError(
            f"Unsupported node_metadata_registry source {type(source)!r}."
        )
    if "root_id" not in df.columns:
        raise WholeBrainContextQueryError(
            "Whole-brain context node metadata input is missing a root_id column."
        )
    normalized = df.copy()
    normalized["root_id"] = _coerce_root_id_series(normalized["root_id"], "node_metadata.root_id")
    rename_map = {
        "super class": "super_class",
        "additional_type(s)": "additional_types",
    }
    normalized = normalized.rename(columns=rename_map)
    for column in (
        "cell_type",
        "resolved_type",
        "primary_type",
        "additional_types",
        "project_role",
        "super_class",
        "class",
        "sub_class",
        "side",
        "hemisphere",
        "nt_type",
        "neuropils",
    ):
        if column not in normalized.columns:
            normalized[column] = pd.NA
        normalized[column] = normalized[column].astype("string")
    keep_columns = [
        "root_id",
        "cell_type",
        "resolved_type",
        "primary_type",
        "additional_types",
        "project_role",
        "super_class",
        "class",
        "sub_class",
        "side",
        "hemisphere",
        "nt_type",
        "neuropils",
    ]
    return normalized.loc[:, keep_columns].drop_duplicates(subset=["root_id"]).copy()


def _build_node_metadata_by_root(
    *,
    node_metadata_df: pd.DataFrame | None,
    active_anchor_records: Mapping[int, Mapping[str, Any]],
) -> dict[int, dict[str, Any]]:
    metadata_by_root: dict[int, dict[str, Any]] = {}
    if node_metadata_df is not None:
        for row in node_metadata_df.to_dict("records"):
            root_id = int(row["root_id"])
            metadata_by_root[root_id] = {
                key: _string_or_none(value)
                for key, value in row.items()
                if key != "root_id"
            }
    for root_id, anchor in active_anchor_records.items():
        merged = metadata_by_root.setdefault(root_id, {})
        for key, value in dict(anchor).items():
            if key == "root_id":
                continue
            if value is None:
                continue
            merged[key] = copy.deepcopy(value)
    return metadata_by_root


def _aggregate_synapse_edges(
    synapse_df: pd.DataFrame,
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    if synapse_df.empty:
        return [], {}
    incident_stats: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "incoming_synapse_count": 0,
            "outgoing_synapse_count": 0,
            "incident_synapse_count": 0,
            "neighbor_root_ids": set(),
            "neuropil_counter": Counter(),
            "nt_type_counter": Counter(),
        }
    )
    grouped = synapse_df.groupby(["pre_root_id", "post_root_id"], sort=True, dropna=False)
    aggregated_edges: list[dict[str, Any]] = []
    for (source_root_id, target_root_id), group in grouped:
        group_sorted = group.sort_values(
            by=["source_row_number", "synapse_row_id"],
            kind="mergesort",
        )
        neuropil_counter = Counter(
            value
            for value in group_sorted["neuropil"].fillna("").astype("string").tolist()
            if str(value)
        )
        nt_type_counter = Counter(
            value
            for value in group_sorted["nt_type"].fillna("").astype("string").tolist()
            if str(value)
        )
        synapse_count = int(len(group_sorted))
        total_weight = float(group_sorted["weight"].fillna(1.0).sum())
        mean_confidence = (
            None
            if group_sorted["confidence"].dropna().empty
            else float(group_sorted["confidence"].dropna().mean())
        )
        edge = {
            "source_root_id": int(source_root_id),
            "target_root_id": int(target_root_id),
            "edge_key": (int(source_root_id), int(target_root_id)),
            "synapse_count": synapse_count,
            "total_weight": total_weight,
            "mean_confidence": mean_confidence,
            "neuropils": sorted(str(item) for item in neuropil_counter),
            "dominant_neuropil": _dominant_counter_value(neuropil_counter),
            "nt_types": sorted(str(item) for item in nt_type_counter),
            "dominant_nt_type": _dominant_counter_value(nt_type_counter),
            "synapse_row_ids_preview": [
                str(item)
                for item in group_sorted["synapse_row_id"].tolist()[:8]
            ],
        }
        aggregated_edges.append(edge)
        incident_stats[int(source_root_id)]["outgoing_synapse_count"] += synapse_count
        incident_stats[int(source_root_id)]["incident_synapse_count"] += synapse_count
        incident_stats[int(source_root_id)]["neighbor_root_ids"].add(int(target_root_id))
        incident_stats[int(source_root_id)]["neuropil_counter"].update(neuropil_counter)
        incident_stats[int(source_root_id)]["nt_type_counter"].update(nt_type_counter)
        incident_stats[int(target_root_id)]["incoming_synapse_count"] += synapse_count
        incident_stats[int(target_root_id)]["incident_synapse_count"] += synapse_count
        incident_stats[int(target_root_id)]["neighbor_root_ids"].add(int(source_root_id))
        incident_stats[int(target_root_id)]["neuropil_counter"].update(neuropil_counter)
        incident_stats[int(target_root_id)]["nt_type_counter"].update(nt_type_counter)
    aggregated_edges.sort(
        key=lambda item: (
            int(item["source_root_id"]),
            int(item["target_root_id"]),
        )
    )
    return aggregated_edges, incident_stats


def _enrich_metadata_from_incident_stats(
    *,
    metadata_by_root: dict[int, dict[str, Any]],
    incident_stats: Mapping[int, Mapping[str, Any]],
) -> None:
    for root_id, stats in incident_stats.items():
        metadata = metadata_by_root.setdefault(int(root_id), {})
        dominant_neuropil = _dominant_counter_value(stats["neuropil_counter"])
        if dominant_neuropil is not None and not _string_or_none(metadata.get("neuropils")):
            metadata["neuropils"] = dominant_neuropil
        dominant_nt = _dominant_counter_value(stats["nt_type_counter"])
        if dominant_nt is not None and not _string_or_none(metadata.get("nt_type")):
            metadata["nt_type"] = dominant_nt


def _build_adjacency(
    aggregated_edges: Sequence[Mapping[str, Any]],
) -> dict[str, dict[int, list[dict[str, Any]]]]:
    outgoing: dict[int, list[dict[str, Any]]] = defaultdict(list)
    incoming: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for edge in aggregated_edges:
        normalized_edge = copy.deepcopy(dict(edge))
        outgoing[int(normalized_edge["source_root_id"])].append(normalized_edge)
        incoming[int(normalized_edge["target_root_id"])].append(normalized_edge)
    return {"outgoing": outgoing, "incoming": incoming}


def _build_traversal_registry(
    *,
    active_root_ids: Sequence[int],
    active_root_set: set[int],
    adjacency: Mapping[str, Mapping[int, Sequence[Mapping[str, Any]]]],
    query_family: str,
    reduction_controls: Mapping[str, Any],
    metadata_by_root: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    max_hops = int(reduction_controls["max_hops"])
    candidate_registry: dict[int, dict[str, Any]] = {}
    path_registry: dict[tuple[str, int], dict[str, Any]] = {}
    directional_membership: dict[int, set[str]] = {
        int(root_id): set() for root_id in active_root_ids
    }
    if max_hops <= 0:
        return {
            "candidate_registry": candidate_registry,
            "path_registry": path_registry,
            "directional_membership": directional_membership,
        }
    directions: list[str] = []
    if query_family in (UPSTREAM_CONTEXT_QUERY_FAMILY, PATHWAY_REVIEW_QUERY_FAMILY):
        directions.append("upstream")
    elif query_family == DOWNSTREAM_CONTEXT_QUERY_FAMILY:
        directions.append("downstream")
    elif query_family in (BIDIRECTIONAL_CONTEXT_QUERY_FAMILY, DOWNSTREAM_MODULE_REVIEW_QUERY_FAMILY):
        directions.extend(["upstream", "downstream"])
    else:
        directions = []
    if query_family == PATHWAY_REVIEW_QUERY_FAMILY:
        directions = ["upstream", "downstream"]
    for direction in directions:
        paths = _traverse_direction(
            direction=direction,
            active_root_ids=active_root_ids,
            active_root_set=active_root_set,
            adjacency=adjacency,
            max_hops=max_hops,
            metadata_by_root=metadata_by_root,
            allowed_cell_classes=set(reduction_controls["allowed_cell_classes"]),
            edge_ranking_policy=str(reduction_controls["edge_ranking_policy"]),
        )
        for root_id, path_record in paths.items():
            path_registry[(direction, int(root_id))] = copy.deepcopy(path_record)
            directional_membership.setdefault(int(root_id), set()).add(direction)
            candidate = candidate_registry.setdefault(
                int(root_id),
                {
                    "root_id": int(root_id),
                    "directions": set(),
                    "path_records": {},
                },
            )
            candidate["directions"].add(direction)
            candidate["path_records"][direction] = copy.deepcopy(path_record)
    for candidate in candidate_registry.values():
        candidate["ranking_path"] = _select_best_candidate_path(candidate["path_records"])
        ranking_path = candidate["ranking_path"]
        candidate["min_hop_count"] = int(ranking_path["hop_count"])
        candidate["direct_active_synapse_count"] = int(
            ranking_path["direct_active_synapse_count"]
        )
        candidate["path_synapse_count"] = int(ranking_path["path_synapse_count"])
        candidate["path_weight"] = float(ranking_path["path_weight"])
        candidate["ranking_key"] = (
            int(candidate["min_hop_count"]),
            -int(candidate["direct_active_synapse_count"]),
            -int(candidate["path_synapse_count"]),
            -float(candidate["path_weight"]),
            int(candidate["root_id"]),
        )
    return {
        "candidate_registry": candidate_registry,
        "path_registry": path_registry,
        "directional_membership": directional_membership,
    }


def _traverse_direction(
    *,
    direction: str,
    active_root_ids: Sequence[int],
    active_root_set: set[int],
    adjacency: Mapping[str, Mapping[int, Sequence[Mapping[str, Any]]]],
    max_hops: int,
    metadata_by_root: Mapping[int, Mapping[str, Any]],
    allowed_cell_classes: set[str],
    edge_ranking_policy: str,
) -> dict[int, dict[str, Any]]:
    frontier: dict[int, dict[str, Any]] = {
        int(root_id): {
            "direction": direction,
            "node_root_ids": [int(root_id)],
            "edge_keys": [],
            "path_synapse_count": 0,
            "path_weight": 0.0,
            "hop_count": 0,
            "active_anchor_root_id": int(root_id),
            "direct_active_synapse_count": 0,
        }
        for root_id in active_root_ids
    }
    best_paths: dict[int, dict[str, Any]] = {}
    adjacency_key = "incoming" if direction == "upstream" else "outgoing"
    for _hop in range(1, max_hops + 1):
        next_frontier: dict[int, dict[str, Any]] = {}
        for current_root_id in sorted(frontier):
            current_path = frontier[current_root_id]
            raw_edges = adjacency[adjacency_key].get(int(current_root_id), [])
            sorted_edges = sorted(
                (copy.deepcopy(dict(edge)) for edge in raw_edges),
                key=lambda item: _edge_sort_key(
                    item,
                    policy=edge_ranking_policy,
                ),
            )
            for edge in sorted_edges:
                next_root_id = (
                    int(edge["source_root_id"])
                    if direction == "upstream"
                    else int(edge["target_root_id"])
                )
                if next_root_id in active_root_set:
                    continue
                if next_root_id in current_path["node_root_ids"]:
                    continue
                if not _node_passes_cell_class_filter(
                    next_root_id,
                    metadata_by_root=metadata_by_root,
                    allowed_cell_classes=allowed_cell_classes,
                ):
                    continue
                candidate_path = _extend_path_record(
                    current_path=current_path,
                    edge=edge,
                    direction=direction,
                )
                existing_best = best_paths.get(next_root_id)
                if existing_best is not None and _path_sort_key(candidate_path) >= _path_sort_key(existing_best):
                    continue
                existing_next = next_frontier.get(next_root_id)
                if existing_next is not None and _path_sort_key(candidate_path) >= _path_sort_key(existing_next):
                    continue
                next_frontier[next_root_id] = candidate_path
                best_paths[next_root_id] = candidate_path
        frontier = next_frontier
        if not frontier:
            break
    return best_paths


def _extend_path_record(
    *,
    current_path: Mapping[str, Any],
    edge: Mapping[str, Any],
    direction: str,
) -> dict[str, Any]:
    if direction == "upstream":
        node_root_ids = [int(edge["source_root_id"]), *current_path["node_root_ids"]]
        edge_keys = [tuple(edge["edge_key"]), *current_path["edge_keys"]]
        active_anchor_root_id = int(current_path["active_anchor_root_id"])
        direct_active_synapse_count = (
            int(edge["synapse_count"])
            if len(current_path["edge_keys"]) == 0
            else int(current_path["direct_active_synapse_count"])
        )
    else:
        node_root_ids = [*current_path["node_root_ids"], int(edge["target_root_id"])]
        edge_keys = [*current_path["edge_keys"], tuple(edge["edge_key"])]
        active_anchor_root_id = int(current_path["active_anchor_root_id"])
        direct_active_synapse_count = (
            int(edge["synapse_count"])
            if len(current_path["edge_keys"]) == 0
            else int(current_path["direct_active_synapse_count"])
        )
    return {
        "direction": direction,
        "node_root_ids": node_root_ids,
        "edge_keys": edge_keys,
        "path_synapse_count": int(current_path["path_synapse_count"]) + int(edge["synapse_count"]),
        "path_weight": float(current_path["path_weight"]) + float(edge["total_weight"]),
        "hop_count": int(current_path["hop_count"]) + 1,
        "active_anchor_root_id": active_anchor_root_id,
        "direct_active_synapse_count": direct_active_synapse_count,
    }


def _path_sort_key(path_record: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        int(path_record["hop_count"]),
        -int(path_record["path_synapse_count"]),
        -float(path_record["path_weight"]),
        tuple(int(root_id) for root_id in path_record["node_root_ids"]),
    )


def _node_passes_cell_class_filter(
    root_id: int,
    *,
    metadata_by_root: Mapping[int, Mapping[str, Any]],
    allowed_cell_classes: set[str],
) -> bool:
    if not allowed_cell_classes:
        return True
    metadata = metadata_by_root.get(int(root_id), {})
    candidate_values = {
        _normalize_identifier_token(value)
        for value in (
            metadata.get("super_class"),
            metadata.get("class"),
            metadata.get("project_role"),
        )
        if _string_or_none(value) is not None
    }
    return bool(candidate_values & allowed_cell_classes)


def _select_best_candidate_path(
    path_records: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return copy.deepcopy(
        sorted(
            (dict(record) for record in path_records.values()),
            key=_path_sort_key,
        )[0]
    )


def _select_context_candidates(
    *,
    traversal_registry: Mapping[int, Mapping[str, Any]],
    active_internal_edges: Sequence[Mapping[str, Any]],
    reduction_controls: Mapping[str, Any],
    active_root_set: set[int],
) -> tuple[set[int], list[dict[str, Any]], set[tuple[int, int]]]:
    max_context_node_count = int(reduction_controls["max_context_node_count"])
    max_edge_count = int(reduction_controls["max_edge_count"])
    selected_context_root_ids: set[int] = set()
    selected_candidate_records: list[dict[str, Any]] = []
    required_edge_keys = {tuple(edge["edge_key"]) for edge in active_internal_edges}
    reserved_edge_count = len(required_edge_keys)
    remaining_edge_budget = max(0, max_edge_count - reserved_edge_count)
    candidate_records = sorted(
        (copy.deepcopy(dict(item)) for item in traversal_registry.values()),
        key=lambda item: item["ranking_key"],
    )
    for candidate in candidate_records:
        path = _require_mapping(candidate.get("ranking_path"), field_name="candidate.ranking_path")
        path_context_nodes = [
            int(root_id)
            for root_id in path["node_root_ids"]
            if int(root_id) not in active_root_set
        ]
        additional_nodes = [
            root_id for root_id in path_context_nodes if root_id not in selected_context_root_ids
        ]
        additional_edges = [
            tuple(edge_key)
            for edge_key in path["edge_keys"]
            if tuple(edge_key) not in required_edge_keys
        ]
        if len(selected_context_root_ids) + len(additional_nodes) > max_context_node_count:
            continue
        if len(additional_edges) > remaining_edge_budget:
            continue
        selected_context_root_ids.update(additional_nodes)
        required_edge_keys.update(additional_edges)
        remaining_edge_budget -= len(additional_edges)
        selected_candidate_records.append(candidate)
    return selected_context_root_ids, selected_candidate_records, required_edge_keys


def _select_biological_edges(
    *,
    aggregated_edges: Sequence[Mapping[str, Any]],
    active_root_set: set[int],
    selected_context_root_ids: set[int],
    required_edge_keys: set[tuple[int, int]],
    reduction_controls: Mapping[str, Any],
) -> list[dict[str, Any]]:
    available_nodes = set(active_root_set) | set(selected_context_root_ids)
    selected_edges_by_key: dict[tuple[int, int], dict[str, Any]] = {}
    all_candidate_edges: list[dict[str, Any]] = []
    for edge in aggregated_edges:
        source_root_id = int(edge["source_root_id"])
        target_root_id = int(edge["target_root_id"])
        if source_root_id not in available_nodes or target_root_id not in available_nodes:
            continue
        edge_key = tuple(edge["edge_key"])
        normalized_edge = copy.deepcopy(dict(edge))
        if edge_key in required_edge_keys or (
            source_root_id in active_root_set and target_root_id in active_root_set
        ):
            selected_edges_by_key[edge_key] = normalized_edge
        else:
            all_candidate_edges.append(normalized_edge)
    max_edge_count = int(reduction_controls["max_edge_count"])
    remaining = max(0, max_edge_count - len(selected_edges_by_key))
    optional_sorted = sorted(
        all_candidate_edges,
        key=lambda item: _edge_sort_key(
            item,
            policy=str(reduction_controls["edge_ranking_policy"]),
        ),
    )
    for edge in optional_sorted[:remaining]:
        selected_edges_by_key[tuple(edge["edge_key"])] = copy.deepcopy(dict(edge))
    return sorted(
        (copy.deepcopy(dict(item)) for item in selected_edges_by_key.values()),
        key=lambda item: _edge_sort_key(
            item,
            policy=str(reduction_controls["edge_ranking_policy"]),
        ),
    )


def _build_pathway_highlight_records(
    *,
    candidate_records: Sequence[Mapping[str, Any]],
    path_registry: Mapping[tuple[str, int], Mapping[str, Any]],
    reduction_controls: Mapping[str, Any],
    query_family: str,
) -> list[dict[str, Any]]:
    if not candidate_records:
        return []
    pathway_targets = set(
        _normalize_root_id_sequence(
            reduction_controls.get("pathway_target_root_ids", []),
            field_name="reduction_controls.pathway_target_root_ids",
        )
    )
    if pathway_targets:
        missing_targets = pathway_targets - {int(item["root_id"]) for item in candidate_records}
        if missing_targets:
            raise WholeBrainContextQueryError(
                "Requested pathway_target_root_ids are not reachable under the declared "
                f"query constraints: {sorted(missing_targets)!r}."
            )
    mode = str(reduction_controls["pathway_extraction_mode"])
    max_pathway_highlight_count = int(reduction_controls["max_pathway_highlight_count"])
    if max_pathway_highlight_count <= 0:
        return []
    selected_candidates: list[dict[str, Any]] = []
    ordered_candidates = sorted(
        (copy.deepcopy(dict(item)) for item in candidate_records),
        key=lambda item: item["ranking_key"],
    )
    if pathway_targets:
        selected_candidates = [
            item for item in ordered_candidates if int(item["root_id"]) in pathway_targets
        ]
    elif query_family == PATHWAY_REVIEW_QUERY_FAMILY or mode == TOP_RANKED_PATHWAY_EXTRACTION_MODE:
        selected_candidates = ordered_candidates
    elif mode == TARGETED_PATHWAY_EXTRACTION_MODE:
        selected_candidates = ordered_candidates
    else:
        selected_candidates = []
    records: list[dict[str, Any]] = []
    highlighted_context_roots: set[int] = set()
    for candidate in selected_candidates:
        path = _require_mapping(candidate.get("ranking_path"), field_name="candidate.ranking_path")
        context_roots_on_path = [
            int(root_id)
            for root_id in path["node_root_ids"]
            if int(root_id) != int(path["active_anchor_root_id"])
        ]
        additional_context_roots = [
            root_id
            for root_id in context_roots_on_path
            if root_id not in highlighted_context_roots
        ]
        if len(highlighted_context_roots) + len(additional_context_roots) > max_pathway_highlight_count:
            continue
        highlighted_context_roots.update(additional_context_roots)
        records.append(
            {
                "pathway_id": (
                    f"pathway:{path['direction']}:"
                    f"{int(path['active_anchor_root_id'])}:"
                    f"{int(candidate['root_id'])}"
                ),
                "direction": str(path["direction"]),
                "anchor_root_id": int(path["active_anchor_root_id"]),
                "target_root_id": int(candidate["root_id"]),
                "node_root_ids": [int(root_id) for root_id in path["node_root_ids"]],
                "edge_key_pairs": [list(item) for item in path["edge_keys"]],
                "edge_ids": [
                    _edge_id(
                        source_root_id=int(edge_key[0]),
                        target_root_id=int(edge_key[1]),
                        edge_role_id=PATHWAY_HIGHLIGHT_EDGE_ROLE_ID,
                    )
                    for edge_key in path["edge_keys"]
                ],
                "hop_count": int(path["hop_count"]),
                "path_synapse_count": int(path["path_synapse_count"]),
                "path_weight": float(path["path_weight"]),
                "ranking_key": list(candidate["ranking_key"]),
            }
        )
    return records


def _default_focused_path_records(
    candidate_records: Sequence[Mapping[str, Any]],
    path_registry: Mapping[tuple[str, int], Mapping[str, Any]],
) -> list[dict[str, Any]]:
    focused: list[dict[str, Any]] = []
    for candidate in sorted(
        (copy.deepcopy(dict(item)) for item in candidate_records),
        key=lambda item: item["ranking_key"],
    )[:3]:
        path = _require_mapping(candidate.get("ranking_path"), field_name="candidate.ranking_path")
        focused.append(
            {
                "pathway_id": (
                    f"focus:{path['direction']}:"
                    f"{int(path['active_anchor_root_id'])}:"
                    f"{int(candidate['root_id'])}"
                ),
                "direction": str(path["direction"]),
                "anchor_root_id": int(path["active_anchor_root_id"]),
                "target_root_id": int(candidate["root_id"]),
                "node_root_ids": [int(root_id) for root_id in path["node_root_ids"]],
                "edge_key_pairs": [list(item) for item in path["edge_keys"]],
                "edge_ids": [
                    _edge_id(
                        source_root_id=int(edge_key[0]),
                        target_root_id=int(edge_key[1]),
                        edge_role_id=PATHWAY_HIGHLIGHT_EDGE_ROLE_ID,
                    )
                    for edge_key in path["edge_keys"]
                ],
                "hop_count": int(path["hop_count"]),
                "path_synapse_count": int(path["path_synapse_count"]),
                "path_weight": float(path["path_weight"]),
            }
        )
    return focused


def _build_base_node_records(
    *,
    active_root_ids: Sequence[int],
    active_root_set: set[int],
    selected_context_root_ids: set[int],
    active_anchor_records: Mapping[int, Mapping[str, Any]],
    metadata_by_root: Mapping[int, Mapping[str, Any]],
    enabled_overlays: set[str],
    enabled_facets: set[str],
    directional_membership: Mapping[int, set[str]],
    path_registry: Mapping[tuple[str, int], Mapping[str, Any]],
    highlight_root_ids: set[int],
) -> list[dict[str, Any]]:
    context_root_ids = sorted(selected_context_root_ids)
    root_order = [int(root_id) for root_id in active_root_ids] + context_root_ids
    records: list[dict[str, Any]] = []
    for root_id in root_order:
        if root_id in active_root_set:
            node_role_id = ACTIVE_SELECTED_NODE_ROLE_ID
            context_layer_id = ACTIVE_SUBSET_CONTEXT_LAYER_ID
            boundary_status = "active"
        else:
            node_role_id = CONTEXT_ONLY_NODE_ROLE_ID
            context_layer_id = _primary_context_layer_for_root(
                root_id=root_id,
                directional_membership=directional_membership,
                path_registry=path_registry,
            )
            boundary_status = "context"
        direction_membership = sorted(directional_membership.get(int(root_id), set()))
        overlay_ids = [ACTIVE_BOUNDARY_OVERLAY_ID]
        if "upstream" in direction_membership and UPSTREAM_GRAPH_OVERLAY_ID in enabled_overlays:
            overlay_ids.append(UPSTREAM_GRAPH_OVERLAY_ID)
        if "downstream" in direction_membership and DOWNSTREAM_GRAPH_OVERLAY_ID in enabled_overlays:
            overlay_ids.append(DOWNSTREAM_GRAPH_OVERLAY_ID)
        if METADATA_FACET_BADGES_OVERLAY_ID in enabled_overlays:
            overlay_ids.append(METADATA_FACET_BADGES_OVERLAY_ID)
        metadata = metadata_by_root.get(int(root_id), {})
        nearest_hop_count = _nearest_hop_count(root_id=root_id, path_registry=path_registry)
        node_record = {
            "root_id": str(int(root_id)),
            "node_role_id": node_role_id,
            "context_layer_id": context_layer_id,
            "overlay_ids": overlay_ids,
            "metadata_facet_values": _node_metadata_facet_values(
                root_id=root_id,
                node_role_id=node_role_id,
                metadata=metadata,
                enabled_facets=enabled_facets,
                highlighted=root_id in highlight_root_ids,
                boundary_status=boundary_status,
            ),
            "display_label": _display_label(root_id=root_id, metadata=metadata),
            "node_id": _node_id(root_id=root_id, context_layer_id=context_layer_id),
            "boundary_status": boundary_status,
            "directional_context": direction_membership,
            "nearest_active_hop_count": nearest_hop_count,
            "is_active_selected": root_id in active_root_set,
            "is_context_only": root_id not in active_root_set,
            "secondary_context_layer_ids": _secondary_context_layers(
                root_id=root_id,
                directional_membership=directional_membership,
                primary_context_layer_id=context_layer_id,
            ),
            "anchor_record": (
                None
                if root_id not in active_anchor_records
                else copy.deepcopy(dict(active_anchor_records[root_id]))
            ),
        }
        records.append(node_record)
    return records


def _build_highlight_node_records(
    *,
    highlight_root_ids: set[int],
    active_root_set: set[int],
    metadata_by_root: Mapping[int, Mapping[str, Any]],
    enabled_overlays: set[str],
    enabled_facets: set[str],
) -> list[dict[str, Any]]:
    if not highlight_root_ids or PATHWAY_HIGHLIGHT_OVERLAY_ID not in enabled_overlays:
        return []
    overlay_ids = [ACTIVE_BOUNDARY_OVERLAY_ID, PATHWAY_HIGHLIGHT_OVERLAY_ID]
    if METADATA_FACET_BADGES_OVERLAY_ID in enabled_overlays:
        overlay_ids.append(METADATA_FACET_BADGES_OVERLAY_ID)
    records: list[dict[str, Any]] = []
    for root_id in sorted(highlight_root_ids):
        is_active = int(root_id) in active_root_set
        node_role_id = (
            ACTIVE_PATHWAY_HIGHLIGHT_NODE_ROLE_ID
            if is_active
            else CONTEXT_PATHWAY_HIGHLIGHT_NODE_ROLE_ID
        )
        metadata = metadata_by_root.get(int(root_id), {})
        records.append(
            {
                "root_id": str(int(root_id)),
                "node_role_id": node_role_id,
                "context_layer_id": PATHWAY_HIGHLIGHT_CONTEXT_LAYER_ID,
                "overlay_ids": overlay_ids,
                "metadata_facet_values": _node_metadata_facet_values(
                    root_id=root_id,
                    node_role_id=node_role_id,
                    metadata=metadata,
                    enabled_facets=enabled_facets,
                    highlighted=True,
                    boundary_status="active" if is_active else "context",
                ),
                "display_label": _display_label(root_id=root_id, metadata=metadata),
                "node_id": _node_id(
                    root_id=root_id,
                    context_layer_id=PATHWAY_HIGHLIGHT_CONTEXT_LAYER_ID,
                ),
                "boundary_status": "active" if is_active else "context",
                "directional_context": [],
                "nearest_active_hop_count": 0 if is_active else None,
                "is_active_selected": is_active,
                "is_context_only": not is_active,
            }
        )
    return records


def _build_base_edge_records(
    *,
    selected_biological_edges: Sequence[Mapping[str, Any]],
    active_root_set: set[int],
    enabled_overlays: set[str],
    directional_membership: Mapping[int, set[str]],
    highlight_edge_keys: set[tuple[int, int]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for edge in selected_biological_edges:
        source_root_id = int(edge["source_root_id"])
        target_root_id = int(edge["target_root_id"])
        edge_role_id = _biological_edge_role(
            source_root_id=source_root_id,
            target_root_id=target_root_id,
            active_root_set=active_root_set,
        )
        overlay_ids = [ACTIVE_BOUNDARY_OVERLAY_ID]
        direction_membership = sorted(
            directional_membership.get(source_root_id, set())
            | directional_membership.get(target_root_id, set())
        )
        if UPSTREAM_GRAPH_OVERLAY_ID in enabled_overlays and (
            edge_role_id == CONTEXT_TO_ACTIVE_EDGE_ROLE_ID or "upstream" in direction_membership
        ):
            overlay_ids.append(UPSTREAM_GRAPH_OVERLAY_ID)
        if DOWNSTREAM_GRAPH_OVERLAY_ID in enabled_overlays and (
            edge_role_id == ACTIVE_TO_CONTEXT_EDGE_ROLE_ID or "downstream" in direction_membership
        ):
            overlay_ids.append(DOWNSTREAM_GRAPH_OVERLAY_ID)
        records.append(
            {
                "source_root_id": str(source_root_id),
                "target_root_id": str(target_root_id),
                "edge_role_id": edge_role_id,
                "overlay_ids": overlay_ids,
                "weight": float(edge["total_weight"]),
                "edge_id": _edge_id(
                    source_root_id=source_root_id,
                    target_root_id=target_root_id,
                    edge_role_id=edge_role_id,
                ),
                "directional_context": direction_membership,
                "synapse_count": int(edge["synapse_count"]),
                "mean_confidence": _coerce_optional_float(edge.get("mean_confidence")),
                "neuropils": list(edge["neuropils"]),
                "dominant_neuropil": edge.get("dominant_neuropil"),
                "nt_types": list(edge["nt_types"]),
                "dominant_nt_type": edge.get("dominant_nt_type"),
                "highlighted": tuple(edge["edge_key"]) in highlight_edge_keys,
            }
        )
    return records


def _build_highlight_edge_records(
    *,
    selected_biological_edges: Sequence[Mapping[str, Any]],
    highlight_edge_keys: set[tuple[int, int]],
) -> list[dict[str, Any]]:
    edge_lookup = {
        tuple(edge["edge_key"]): copy.deepcopy(dict(edge))
        for edge in selected_biological_edges
    }
    records: list[dict[str, Any]] = []
    for edge_key in sorted(highlight_edge_keys):
        edge = edge_lookup.get(tuple(edge_key))
        if edge is None:
            continue
        records.append(
            {
                "source_root_id": str(int(edge["source_root_id"])),
                "target_root_id": str(int(edge["target_root_id"])),
                "edge_role_id": PATHWAY_HIGHLIGHT_EDGE_ROLE_ID,
                "overlay_ids": [PATHWAY_HIGHLIGHT_OVERLAY_ID],
                "weight": float(edge["total_weight"]),
                "edge_id": _edge_id(
                    source_root_id=int(edge["source_root_id"]),
                    target_root_id=int(edge["target_root_id"]),
                    edge_role_id=PATHWAY_HIGHLIGHT_EDGE_ROLE_ID,
                ),
                "directional_context": [],
                "synapse_count": int(edge["synapse_count"]),
                "mean_confidence": _coerce_optional_float(edge.get("mean_confidence")),
                "neuropils": list(edge["neuropils"]),
                "dominant_neuropil": edge.get("dominant_neuropil"),
                "nt_types": list(edge["nt_types"]),
                "dominant_nt_type": edge.get("dominant_nt_type"),
                "highlighted": True,
            }
        )
    return records


def _build_downstream_module_records(
    *,
    plan: Mapping[str, Any],
    metadata_by_root: Mapping[int, Mapping[str, Any]],
    selected_context_root_ids: set[int],
    directional_membership: Mapping[int, set[str]],
    reduction_controls: Mapping[str, Any],
    enabled_overlays: set[str],
    enabled_facets: set[str],
) -> list[dict[str, Any]]:
    requests = plan.get("downstream_module_requests")
    if not isinstance(requests, Sequence) or isinstance(requests, (str, bytes)):
        return []
    if DOWNSTREAM_MODULE_OVERLAY_ID not in enabled_overlays:
        return []
    downstream_context_roots = [
        int(root_id)
        for root_id in sorted(selected_context_root_ids)
        if "downstream" in directional_membership.get(int(root_id), set())
    ]
    if not downstream_context_roots:
        return []
    max_module_count = int(reduction_controls["max_downstream_module_count"])
    if max_module_count <= 0:
        return []
    records: list[dict[str, Any]] = []
    for request in requests:
        if len(records) >= max_module_count:
            break
        if not isinstance(request, Mapping):
            continue
        role_id = _require_nonempty_identifier(
            request.get("downstream_module_role_id"),
            field_name="downstream_module_request.downstream_module_role_id",
        )
        represented_root_ids = downstream_context_roots[: min(12, len(downstream_context_roots))]
        dominant_cell_class = _dominant_counter_value(
            Counter(
                _string_or_none(metadata_by_root.get(root_id, {}).get("super_class"))
                or _string_or_none(metadata_by_root.get(root_id, {}).get("class"))
                or _string_or_none(metadata_by_root.get(root_id, {}).get("project_role"))
                for root_id in represented_root_ids
            )
        )
        dominant_neuropil = _dominant_counter_value(
            Counter(
                _string_or_none(metadata_by_root.get(root_id, {}).get("neuropils"))
                for root_id in represented_root_ids
            )
        )
        metadata_values = {}
        if "cell_class" in enabled_facets and dominant_cell_class is not None:
            metadata_values["cell_class"] = dominant_cell_class
        if "neuropil" in enabled_facets and dominant_neuropil is not None:
            metadata_values["neuropil"] = dominant_neuropil
        if "pathway_relevance_status" in enabled_facets:
            metadata_values["pathway_relevance_status"] = "collapsed_downstream_module"
        records.append(
            {
                "module_id": f"module:{role_id}:{represented_root_ids[0]}",
                "downstream_module_role_id": role_id,
                "display_name": str(request.get("display_name") or role_id.replace("_", " ").title()),
                "description": (
                    f"Collapsed downstream review group representing {len(represented_root_ids)} "
                    "context roots."
                ),
                "represented_root_ids": [str(root_id) for root_id in represented_root_ids],
                "overlay_ids": [DOWNSTREAM_MODULE_OVERLAY_ID],
                "metadata_facet_values": metadata_values,
                "context_layer_id": DOWNSTREAM_MODULE_CONTEXT_LAYER_ID,
                "module_kind": "collapsed_context_summary",
            }
        )
    return records


def _build_graph_view(
    *,
    view_id: str,
    display_name: str,
    description: str,
    node_records: Sequence[Mapping[str, Any]],
    edge_records: Sequence[Mapping[str, Any]],
    downstream_module_records: Sequence[Mapping[str, Any]],
    highlight_path_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    root_ids = {
        str(item["root_id"])
        for item in node_records
        if str(item.get("node_role_id")) in {ACTIVE_SELECTED_NODE_ROLE_ID, CONTEXT_ONLY_NODE_ROLE_ID}
    }
    return {
        "view_id": view_id,
        "display_name": display_name,
        "description": description,
        "node_records": [copy.deepcopy(dict(item)) for item in node_records],
        "edge_records": [copy.deepcopy(dict(item)) for item in edge_records],
        "downstream_module_records": [
            copy.deepcopy(dict(item)) for item in downstream_module_records
        ],
        "summary": {
            "distinct_root_count": len(root_ids),
            "node_record_count": len(node_records),
            "edge_record_count": len(edge_records),
            "downstream_module_count": len(downstream_module_records),
            "pathway_highlight_count": len(highlight_path_records),
        },
    }


def _build_focused_subgraph(
    *,
    base_node_records: Sequence[Mapping[str, Any]],
    highlight_node_records: Sequence[Mapping[str, Any]],
    base_edge_records: Sequence[Mapping[str, Any]],
    highlight_edge_records: Sequence[Mapping[str, Any]],
    downstream_module_records: Sequence[Mapping[str, Any]],
    focused_path_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    focused_root_ids = {
        str(root_id)
        for record in focused_path_records
        for root_id in record["node_root_ids"]
    }
    focused_edge_ids = {
        str(edge_id)
        for record in focused_path_records
        for edge_id in record["edge_ids"]
    }
    node_records = [
        copy.deepcopy(dict(item))
        for item in [*base_node_records, *highlight_node_records]
        if str(item["root_id"]) in focused_root_ids
    ]
    edge_records = [
        copy.deepcopy(dict(item))
        for item in [*base_edge_records, *highlight_edge_records]
        if str(item["edge_id"]) in focused_edge_ids
        or (
            str(item["source_root_id"]) in focused_root_ids
            and str(item["target_root_id"]) in focused_root_ids
        )
    ]
    focused_downstream_modules = [
        copy.deepcopy(dict(item))
        for item in downstream_module_records
        if focused_root_ids & {str(root_id) for root_id in item["represented_root_ids"]}
    ]
    return _build_graph_view(
        view_id="focused_subgraph",
        display_name="Focused Subgraph",
        description="Compact path-preserving slice suitable for review cards and linked inspection.",
        node_records=_sort_node_records(node_records),
        edge_records=_sort_edge_records(edge_records),
        downstream_module_records=focused_downstream_modules,
        highlight_path_records=focused_path_records,
    )


def _node_metadata_facet_values(
    *,
    root_id: int,
    node_role_id: str,
    metadata: Mapping[str, Any],
    enabled_facets: set[str],
    highlighted: bool,
    boundary_status: str,
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    cell_class = (
        _string_or_none(metadata.get("super_class"))
        or _string_or_none(metadata.get("class"))
        or _string_or_none(metadata.get("project_role"))
    )
    cell_type = (
        _string_or_none(metadata.get("cell_type"))
        or _string_or_none(metadata.get("resolved_type"))
        or _string_or_none(metadata.get("primary_type"))
    )
    neuropils = _string_or_none(metadata.get("neuropils"))
    side = _string_or_none(metadata.get("side")) or _string_or_none(metadata.get("hemisphere"))
    nt_type = _string_or_none(metadata.get("nt_type"))
    if "cell_class" in enabled_facets and cell_class is not None:
        values["cell_class"] = cell_class
    if "cell_type" in enabled_facets and cell_type is not None:
        values["cell_type"] = cell_type
    if "neuropil" in enabled_facets and neuropils is not None:
        values["neuropil"] = neuropils
    if "side" in enabled_facets and side is not None:
        values["side"] = side
    if "nt_type" in enabled_facets and nt_type is not None:
        values["nt_type"] = nt_type
    if "selection_boundary_status" in enabled_facets:
        values["selection_boundary_status"] = node_role_id
    if "pathway_relevance_status" in enabled_facets:
        values["pathway_relevance_status"] = (
            "pathway_highlight" if highlighted else boundary_status
        )
    return values


def _display_label(*, root_id: int, metadata: Mapping[str, Any]) -> str:
    for key in ("cell_type", "resolved_type", "primary_type", "class", "project_role"):
        value = _string_or_none(metadata.get(key))
        if value is not None:
            return value
    return str(int(root_id))


def _biological_edge_role(
    *,
    source_root_id: int,
    target_root_id: int,
    active_root_set: set[int],
) -> str:
    if source_root_id in active_root_set and target_root_id in active_root_set:
        return ACTIVE_INTERNAL_EDGE_ROLE_ID
    if source_root_id in active_root_set:
        return ACTIVE_TO_CONTEXT_EDGE_ROLE_ID
    if target_root_id in active_root_set:
        return CONTEXT_TO_ACTIVE_EDGE_ROLE_ID
    return CONTEXT_INTERNAL_EDGE_ROLE_ID


def _edge_sort_key(edge: Mapping[str, Any], *, policy: str) -> tuple[Any, ...]:
    if policy == WEIGHTED_SYNAPSE_DESC_RANKING_POLICY:
        primary = (
            -float(edge.get("total_weight", 0.0)),
            -int(edge.get("synapse_count", 0)),
        )
    else:
        primary = (
            -int(edge.get("synapse_count", 0)),
            -float(edge.get("total_weight", 0.0)),
        )
    return (
        *primary,
        int(edge["source_root_id"]),
        int(edge["target_root_id"]),
    )


def _sort_node_records(
    node_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        (copy.deepcopy(dict(item)) for item in node_records),
        key=lambda item: (
            int(_NODE_RECORD_SORT_ORDER.get(str(item["node_role_id"]), 99)),
            str(item["context_layer_id"]),
            int(_coerce_nullable_int(item.get("nearest_active_hop_count")) or 0),
            int(item["root_id"]),
            str(item.get("node_id") or ""),
        ),
    )


def _sort_edge_records(
    edge_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        (copy.deepcopy(dict(item)) for item in edge_records),
        key=lambda item: (
            int(_EDGE_RECORD_SORT_ORDER.get(str(item["edge_role_id"]), 99)),
            -int(item.get("synapse_count", 0)),
            float(-(item.get("weight") or 0.0)),
            int(item["source_root_id"]),
            int(item["target_root_id"]),
            str(item.get("edge_id") or ""),
        ),
    )


def _primary_context_layer_for_root(
    *,
    root_id: int,
    directional_membership: Mapping[int, set[str]],
    path_registry: Mapping[tuple[str, int], Mapping[str, Any]],
) -> str:
    membership = directional_membership.get(int(root_id), set())
    if membership == {"upstream"}:
        return UPSTREAM_CONTEXT_LAYER_ID
    if membership == {"downstream"}:
        return DOWNSTREAM_CONTEXT_LAYER_ID
    if membership == {"upstream", "downstream"}:
        upstream_path = path_registry.get(("upstream", int(root_id)))
        downstream_path = path_registry.get(("downstream", int(root_id)))
        if upstream_path is None:
            return DOWNSTREAM_CONTEXT_LAYER_ID
        if downstream_path is None:
            return UPSTREAM_CONTEXT_LAYER_ID
        return (
            UPSTREAM_CONTEXT_LAYER_ID
            if _path_sort_key(upstream_path) <= _path_sort_key(downstream_path)
            else DOWNSTREAM_CONTEXT_LAYER_ID
        )
    return DOWNSTREAM_CONTEXT_LAYER_ID


def _secondary_context_layers(
    *,
    root_id: int,
    directional_membership: Mapping[int, set[str]],
    primary_context_layer_id: str,
) -> list[str]:
    membership = directional_membership.get(int(root_id), set())
    secondary: list[str] = []
    if "upstream" in membership and primary_context_layer_id != UPSTREAM_CONTEXT_LAYER_ID:
        secondary.append(UPSTREAM_CONTEXT_LAYER_ID)
    if "downstream" in membership and primary_context_layer_id != DOWNSTREAM_CONTEXT_LAYER_ID:
        secondary.append(DOWNSTREAM_CONTEXT_LAYER_ID)
    return secondary


def _nearest_hop_count(
    *,
    root_id: int,
    path_registry: Mapping[tuple[str, int], Mapping[str, Any]],
) -> int | None:
    hop_counts = [
        int(record["hop_count"])
        for (direction, candidate_root_id), record in path_registry.items()
        if int(candidate_root_id) == int(root_id)
    ]
    if not hop_counts:
        return None
    return min(hop_counts)


def _node_id(*, root_id: int, context_layer_id: str) -> str:
    return f"root:{int(root_id)}:{str(context_layer_id)}"


def _edge_id(
    *,
    source_root_id: int,
    target_root_id: int,
    edge_role_id: str,
) -> str:
    return f"edge:{int(source_root_id)}->{int(target_root_id)}:{str(edge_role_id)}"


def _normalize_active_anchor_records(
    payload: Any,
    *,
    active_root_ids: Sequence[int],
) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    root_id_set = {int(root_id) for root_id in active_root_ids}
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        for root_id in active_root_ids:
            result[int(root_id)] = {"root_id": int(root_id)}
        return result
    for item in payload:
        if not isinstance(item, Mapping) or item.get("root_id") is None:
            continue
        root_id = int(item["root_id"])
        if root_id not in root_id_set:
            continue
        result[root_id] = {key: copy.deepcopy(value) for key, value in dict(item).items()}
    for root_id in active_root_ids:
        result.setdefault(int(root_id), {"root_id": int(root_id)})
    return result


def _dominant_counter_value(counter: Counter[Any]) -> str | None:
    entries = [
        (str(key), int(value))
        for key, value in counter.items()
        if _string_or_none(key) is not None and int(value) > 0
    ]
    if not entries:
        return None
    entries.sort(key=lambda item: (-item[1], item[0]))
    return entries[0][0]


def _normalize_edge_ranking_policy(value: Any, *, field_name: str) -> str:
    normalized = _normalize_identifier_token(value)
    if normalized not in SUPPORTED_EDGE_RANKING_POLICIES:
        raise WholeBrainContextQueryError(
            f"{field_name} must be one of {SUPPORTED_EDGE_RANKING_POLICIES!r}."
        )
    return normalized


def _normalize_pathway_extraction_mode(value: Any, *, field_name: str) -> str:
    normalized = _normalize_identifier_token(value)
    if normalized not in SUPPORTED_PATHWAY_EXTRACTION_MODES:
        raise WholeBrainContextQueryError(
            f"{field_name} must be one of {SUPPORTED_PATHWAY_EXTRACTION_MODES!r}."
        )
    return normalized


def _normalize_root_id_sequence(payload: Any, *, field_name: str) -> list[int]:
    if payload is None:
        return []
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise WholeBrainContextQueryError(f"{field_name} must be a sequence of root IDs.")
    result = sorted({int(item) for item in payload})
    return result


def _normalize_identifier_sequence(payload: Any, *, field_name: str) -> list[str]:
    if payload is None:
        return []
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise WholeBrainContextQueryError(f"{field_name} must be a sequence.")
    normalized = {
        _normalize_identifier_token(item)
        for item in payload
        if _string_or_none(item) is not None
    }
    return sorted(normalized)


def _normalize_identifier_token(value: Any) -> str:
    text = _string_or_none(value)
    if text is None:
        raise WholeBrainContextQueryError("Identifier values must not be empty.")
    normalized = "".join(
        character.lower() if character.isalnum() else "_"
        for character in text.strip()
    )
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")


def _coerce_root_id_series(series: pd.Series, field_name: str) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isna().any():
        raise WholeBrainContextQueryError(
            f"{field_name} contains non-integer root IDs."
        )
    return numeric.astype(int)


def _coerce_nonnegative_int(value: Any, *, field_name: str) -> int:
    try:
        integer = int(value)
    except Exception as exc:  # pragma: no cover - defensive
        raise WholeBrainContextQueryError(f"{field_name} must be an integer.") from exc
    if integer < 0:
        raise WholeBrainContextQueryError(f"{field_name} must be nonnegative.")
    return integer


def _coerce_nullable_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _coerce_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:  # pragma: no cover - defensive
        pass
    try:
        return float(value)
    except Exception:  # pragma: no cover - defensive
        return None


def _require_nonempty_identifier(value: Any, *, field_name: str) -> str:
    normalized = _normalize_identifier_token(value)
    if not normalized:
        raise WholeBrainContextQueryError(f"{field_name} must not be empty.")
    return normalized


def _require_mapping(payload: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise WholeBrainContextQueryError(f"{field_name} must be a mapping.")
    return copy.deepcopy(dict(payload))


def _existing_path(value: Any) -> Path | None:
    if value is None:
        return None
    path = Path(value).resolve()
    if path.exists():
        return path
    return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "SUPPORTED_EDGE_RANKING_POLICIES",
    "SUPPORTED_PATHWAY_EXTRACTION_MODES",
    "TOP_RANKED_PATHWAY_EXTRACTION_MODE",
    "TARGETED_PATHWAY_EXTRACTION_MODE",
    "WEIGHTED_SYNAPSE_DESC_RANKING_POLICY",
    "WHOLE_BRAIN_CONTEXT_QUERY_RESULT_VERSION",
    "WholeBrainContextQueryError",
    "SYNAPSE_COUNT_DESC_RANKING_POLICY",
    "execute_whole_brain_context_query",
    "normalize_whole_brain_context_reduction_controls",
]
