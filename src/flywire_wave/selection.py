from __future__ import annotations

import re
import sys
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import networkx as nx
import pandas as pd

from .io_utils import ensure_dir, write_json, write_root_ids
from .registry import load_connectivity_registry, load_neuron_registry, materialize_synapse_registry


REPO_ROOT = Path(__file__).resolve().parents[2]
VENDORED_CODEX_ROOT = REPO_ROOT / "flywire_codex"
if VENDORED_CODEX_ROOT.exists() and str(VENDORED_CODEX_ROOT) not in sys.path:
    sys.path.insert(0, str(VENDORED_CODEX_ROOT))

try:
    from codex.data.brain_regions import lookup_neuropil_set
    from codex.utils.graph_algos import reachable_nodes
except Exception:  # pragma: no cover - fallback only matters when vendored Codex is unavailable.
    def lookup_neuropil_set(txt: str | None) -> set[str]:
        if not txt:
            return set()
        return {str(txt).strip().upper()}

    def reachable_nodes(
        sources: Iterable[int],
        neighbor_sets: dict[int, set[int]],
        stop_target: int | None = None,
        max_depth: int | None = None,
    ) -> dict[int, int]:
        depth = 0
        reached = {int(source): 0 for source in sources}
        frontier = set(reached)
        while frontier:
            if max_depth is not None and depth == max_depth:
                break
            if stop_target is not None and stop_target in frontier:
                break
            depth += 1
            next_frontier: set[int] = set()
            for node in frontier:
                next_frontier |= neighbor_sets.get(int(node), set())
            frontier = next_frontier - reached.keys()
            for node in frontier:
                reached[int(node)] = depth
        return reached


ROOT_ID_CANDIDATES = [
    "root_id",
    "pt_root_id",
    "id",
    "rootid",
]

SUPER_CLASS_CANDIDATES = [
    "super_class",
    "superclass",
    "class_super",
]

PROJECT_ROLE_CANDIDATES = [
    "project_role",
    "role_in_project",
]

CELL_TYPE_MATCH_COLUMNS = [
    "cell_type",
    "resolved_type",
    "primary_type",
    "visual_type",
    "sub_class",
    "class",
]

MULTI_VALUE_COLUMNS = [
    "additional_types",
    "neuropils",
    "input_neuropils",
    "output_neuropils",
]

SELECTION_RESERVED_KEYS = {
    "active_preset",
    "generate_all",
    "presets",
}

DEFAULT_SUBSET_OUTPUT_DIR = Path("data/interim/subsets")
DEFAULT_PREVIEW_EDGE_LIMIT = 18
SUBSET_INDEX_FILENAME = "subset_index.json"
ROOT_IDS_FILENAME = "root_ids.txt"
SELECTED_NEURONS_FILENAME = "selected_neurons.csv"
SUBSET_STATS_FILENAME = "subset_stats.json"
SUBSET_MANIFEST_FILENAME = "subset_manifest.json"
PREVIEW_FILENAME = "preview.md"
MANIFEST_COLUMNS = [
    "root_id",
    "cell_type",
    "resolved_type",
    "primary_type",
    "additional_types",
    "project_role",
    "super_class",
    "class",
    "sub_class",
    "flow",
    "side",
    "hemisphere",
    "column_id",
    "column_x",
    "column_y",
    "column_p",
    "column_q",
    "neuropils",
    "input_neuropils",
    "output_neuropils",
    "nt_type",
    "proofread_status",
]


@dataclass(frozen=True)
class SubsetArtifactPaths:
    preset_name: str
    artifact_dir: Path
    root_ids: Path
    selected_neurons_csv: Path
    stats_json: Path
    manifest_json: Path
    preview_markdown: Path


def build_subset_artifact_paths(
    base_dir: str | Path,
    preset_name: str,
) -> SubsetArtifactPaths:
    return _artifact_paths_for_preset(Path(base_dir), preset_name)


def _find_first_existing(df: pd.DataFrame, candidates: list[str]) -> str:
    lower_to_original = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in lower_to_original:
            return lower_to_original[candidate.lower()]
    raise KeyError(f"None of the candidate columns exist: {candidates}")


def load_classification_table(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Could not find classification CSV at {csv_path}. "
            "Download it from the Codex FAFB portal and place it there."
        )
    return pd.read_csv(csv_path)


def load_selection_table(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Could not find selection table at {csv_path}.")
    return pd.read_csv(csv_path)


def select_visual_subset(
    df: pd.DataFrame,
    *,
    super_class: str | None = "visual_projection",
    super_classes: Iterable[str] | None = None,
    project_roles: Iterable[str] | None = None,
    limit: int = 12,
    sort_by: str = "root_id",
) -> pd.DataFrame:
    include_filters: dict[str, Any] = {}
    if super_classes is None:
        super_classes = [super_class] if super_class else []
    if super_classes:
        include_filters["super_classes"] = list(super_classes)
    if project_roles:
        include_filters["project_roles"] = list(project_roles)

    return apply_selection_spec(
        df,
        {
            "include": include_filters,
            "limit": limit,
            "sort_by": sort_by,
        },
    )


def apply_selection_spec(df: pd.DataFrame, spec: dict[str, Any]) -> pd.DataFrame:
    root_col = _find_first_existing(df, ROOT_ID_CANDIDATES)
    out = df.copy()

    include_filters = deepcopy(spec.get("include", {}))
    exclude_filters = deepcopy(spec.get("exclude", {}))
    out = _apply_filters(out, include_filters, mode="include")
    out = _apply_filters(out, exclude_filters, mode="exclude")
    out = _normalize_root_id_column(out, root_col)
    out = _sort_subset(out, sort_by=str(spec.get("sort_by", "root_id")))

    limit = _coerce_optional_int(spec.get("limit"))
    if limit is not None:
        out = out.head(limit)
    return out.reset_index(drop=True)


def extract_root_ids(df: pd.DataFrame) -> list[int]:
    root_col = _find_first_existing(df, ROOT_ID_CANDIDATES)
    return [int(x) for x in df[root_col].tolist()]


def generate_subsets_from_config(
    cfg: dict[str, Any],
    *,
    config_path: str | Path | None = None,
    preset_name: str | None = None,
    generate_all: bool = False,
) -> dict[str, Any]:
    paths_cfg = cfg.get("paths", {})
    selection_cfg = cfg.get("selection", {})

    registry_path = Path(paths_cfg.get("neuron_registry_csv", "data/interim/registry/neuron_registry.csv"))
    neuron_registry = load_neuron_registry(registry_path)

    connectivity_registry_path = Path(
        paths_cfg.get("connectivity_registry_csv", "data/interim/registry/connectivity_registry.csv")
    )
    if connectivity_registry_path.exists():
        connectivity_registry = load_connectivity_registry(connectivity_registry_path)
    else:
        connectivity_registry = pd.DataFrame(columns=["pre_root_id", "post_root_id", "neuropil", "syn_count"])

    presets, preset_order = _resolve_selection_presets(selection_cfg)
    active_preset = _resolve_active_preset(selection_cfg, presets, preset_order, preset_name)
    preset_names = _resolve_requested_preset_names(
        presets=presets,
        preset_order=preset_order,
        active_preset=active_preset,
        requested_preset=preset_name,
        generate_all=generate_all or bool(selection_cfg.get("generate_all")),
    )

    subset_output_dir = Path(paths_cfg.get("subset_output_dir", DEFAULT_SUBSET_OUTPUT_DIR))
    ensure_dir(subset_output_dir)

    artifact_summaries: list[dict[str, Any]] = []
    for name in preset_names:
        spec = deepcopy(presets[name])
        selected_df, stats_payload, manifest_payload, preview_markdown = build_subset_artifacts(
            neuron_registry=neuron_registry,
            connectivity_registry=connectivity_registry,
            preset_name=name,
            spec=spec,
            registry_path=registry_path,
            connectivity_registry_path=connectivity_registry_path if connectivity_registry_path.exists() else None,
            config_path=config_path,
        )

        artifact_paths = _artifact_paths_for_preset(subset_output_dir, name)
        _write_subset_outputs(
            selected_df=selected_df,
            stats_payload=stats_payload,
            manifest_payload=manifest_payload,
            preview_markdown=preview_markdown,
            artifact_paths=artifact_paths,
        )

        if name == active_preset:
            selected_root_ids_path = paths_cfg.get("selected_root_ids")
            if selected_root_ids_path:
                write_root_ids(extract_root_ids(selected_df), selected_root_ids_path)
            if "processed_coupling_dir" in paths_cfg or "synapse_source_csv" in paths_cfg:
                if selected_root_ids_path:
                    materialize_synapse_registry(
                        cfg,
                        root_ids_path=selected_root_ids_path,
                        scope_label=f"selection:{name}",
                    )
                else:
                    materialize_synapse_registry(
                        cfg,
                        root_ids=extract_root_ids(selected_df),
                        scope_label=f"selection:{name}",
                    )

        artifact_summaries.append(
            {
                "preset_name": name,
                "description": spec.get("description"),
                "root_id_count": int(len(selected_df)),
                "paths": {
                    "artifact_dir": str(artifact_paths.artifact_dir),
                    "root_ids": str(artifact_paths.root_ids),
                    "selected_neurons_csv": str(artifact_paths.selected_neurons_csv),
                    "stats_json": str(artifact_paths.stats_json),
                    "manifest_json": str(artifact_paths.manifest_json),
                    "preview_markdown": str(artifact_paths.preview_markdown),
                },
            }
        )

    index_payload = {
        "generated_at_utc": _now_utc_isoformat(),
        "config_path": str(config_path) if config_path is not None else None,
        "active_preset": active_preset,
        "generated_presets": artifact_summaries,
    }
    write_json(index_payload, subset_output_dir / SUBSET_INDEX_FILENAME)
    return index_payload


def build_subset_artifacts(
    *,
    neuron_registry: pd.DataFrame,
    connectivity_registry: pd.DataFrame,
    preset_name: str,
    spec: dict[str, Any],
    registry_path: str | Path,
    connectivity_registry_path: str | Path | None,
    config_path: str | Path | None,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any], str]:
    root_col = _find_first_existing(neuron_registry, ROOT_ID_CANDIDATES)
    sort_by = str(spec.get("sort_by", "root_id"))
    preview_edge_limit = _coerce_optional_int(spec.get("preview_edge_limit")) or DEFAULT_PREVIEW_EDGE_LIMIT
    max_neurons = _coerce_optional_int(spec.get("max_neurons") or spec.get("neuron_budget"))

    base_subset = apply_selection_spec(neuron_registry, spec)
    if max_neurons is not None and len(base_subset) > max_neurons:
        raise ValueError(
            f"Preset {preset_name!r} selected {len(base_subset)} neurons before graph expansion, "
            f"which exceeds max_neurons={max_neurons}."
        )

    selected_subset = base_subset.copy()
    relation_reports: list[dict[str, Any]] = []
    for relation in spec.get("relations", []):
        selected_subset, relation_report = _apply_relation_expansion(
            neuron_registry=neuron_registry,
            connectivity_registry=connectivity_registry,
            current_subset=selected_subset,
            base_subset=base_subset,
            relation=relation,
            max_neurons=max_neurons,
            sort_by=sort_by,
        )
        relation_reports.append(relation_report)

    selected_subset = _normalize_root_id_column(selected_subset, root_col)
    selected_subset = _sort_subset(selected_subset, sort_by=sort_by).reset_index(drop=True)

    selected_root_ids = set(extract_root_ids(selected_subset))
    selected_edges = _selected_connectivity(connectivity_registry, selected_root_ids)
    graph = _build_graph(selected_subset, selected_edges)
    boundary_stats = _boundary_partner_stats(
        selected_root_ids=selected_root_ids,
        connectivity_registry=connectivity_registry,
        neuron_registry=neuron_registry,
    )

    stats_payload = {
        "preset_name": preset_name,
        "description": spec.get("description"),
        "generated_at_utc": _now_utc_isoformat(),
        "selection": {
            "base_neuron_count": int(len(base_subset)),
            "final_neuron_count": int(len(selected_subset)),
            "max_neurons": max_neurons,
            "sort_by": sort_by,
            "preview_edge_limit": preview_edge_limit,
        },
        "counts": {
            "project_roles": _counts_for_column(selected_subset, "project_role"),
            "cell_types": _counts_for_column(selected_subset, "cell_type"),
            "super_classes": _counts_for_column(selected_subset, "super_class"),
            "sides": _counts_for_column(selected_subset, "side"),
            "neuropils": _split_value_counts(selected_subset.get("neuropils")),
            "column_ids": _unique_sorted_ints(selected_subset.get("column_id")),
        },
        "graph": {
            "internal_connection_rows": int(len(selected_edges)),
            "internal_connection_pairs": int(graph.number_of_edges()),
            "internal_synapse_count": int(selected_edges["syn_count"].sum()) if not selected_edges.empty else 0,
            "weak_component_count": int(nx.number_weakly_connected_components(graph)) if graph.number_of_nodes() else 0,
            "largest_weak_component_size": _largest_weak_component_size(graph),
            "density": float(nx.density(graph)) if graph.number_of_nodes() > 1 else 0.0,
            "top_outgoing_nodes": _top_weighted_degree_nodes(graph, selected_subset, direction="out"),
            "top_incoming_nodes": _top_weighted_degree_nodes(graph, selected_subset, direction="in"),
        },
        "boundary": boundary_stats,
        "relation_steps": relation_reports,
    }

    preview_markdown = _render_preview_markdown(
        preset_name=preset_name,
        description=str(spec.get("description", "") or ""),
        selected_subset=selected_subset,
        selected_edges=selected_edges,
        stats_payload=stats_payload,
        preview_edge_limit=preview_edge_limit,
    )

    manifest_payload = {
        "subset_manifest_version": "1",
        "generated_at_utc": _now_utc_isoformat(),
        "preset_name": preset_name,
        "description": spec.get("description"),
        "config_path": str(config_path) if config_path is not None else None,
        "registry_path": str(registry_path),
        "connectivity_registry_path": str(connectivity_registry_path) if connectivity_registry_path is not None else None,
        "selection_spec": _json_ready(spec),
        "summary": {
            "neuron_count": int(len(selected_subset)),
            "internal_connection_pairs": int(graph.number_of_edges()),
            "project_role_counts": stats_payload["counts"]["project_roles"],
            "cell_type_counts": stats_payload["counts"]["cell_types"],
        },
        "root_ids": extract_root_ids(selected_subset),
        "neurons": _df_to_records(selected_subset, MANIFEST_COLUMNS),
    }
    return selected_subset, stats_payload, manifest_payload, preview_markdown


def _resolve_selection_presets(selection_cfg: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    presets_cfg = selection_cfg.get("presets")
    if not presets_cfg:
        legacy_spec = _legacy_selection_spec(selection_cfg)
        return {"default": legacy_spec}, ["default"]

    if not isinstance(presets_cfg, dict):
        raise ValueError("selection.presets must be a mapping of preset names to selection specs.")

    defaults = {
        key: deepcopy(value)
        for key, value in selection_cfg.items()
        if key not in SELECTION_RESERVED_KEYS and value is not None
    }

    resolved: dict[str, dict[str, Any]] = {}
    order = list(presets_cfg.keys())
    for preset_name in order:
        resolved[preset_name] = _resolve_named_preset(
            preset_name=preset_name,
            presets_cfg=presets_cfg,
            defaults=defaults,
            resolution_stack=[],
        )
    return resolved, order


def _resolve_named_preset(
    *,
    preset_name: str,
    presets_cfg: dict[str, Any],
    defaults: dict[str, Any],
    resolution_stack: list[str],
) -> dict[str, Any]:
    if preset_name not in presets_cfg:
        raise ValueError(f"Unknown subset preset {preset_name!r}.")
    if preset_name in resolution_stack:
        cycle = " -> ".join([*resolution_stack, preset_name])
        raise ValueError(f"Cyclic selection preset inheritance detected: {cycle}")

    raw_preset = presets_cfg[preset_name]
    if not isinstance(raw_preset, dict):
        raise ValueError(f"selection.presets.{preset_name} must be a mapping.")

    resolved = deepcopy(defaults)
    parent_name = raw_preset.get("extends")
    if parent_name:
        parent_resolved = _resolve_named_preset(
            preset_name=str(parent_name),
            presets_cfg=presets_cfg,
            defaults=defaults,
            resolution_stack=[*resolution_stack, preset_name],
        )
        resolved = _deep_merge_specs(resolved, parent_resolved)

    raw_without_extends = {key: deepcopy(value) for key, value in raw_preset.items() if key != "extends"}
    resolved = _deep_merge_specs(resolved, raw_without_extends)
    return _normalize_selection_spec(resolved)


def _resolve_active_preset(
    selection_cfg: dict[str, Any],
    presets: dict[str, dict[str, Any]],
    preset_order: list[str],
    requested_preset: str | None,
) -> str:
    if requested_preset:
        if requested_preset not in presets:
            raise ValueError(f"Unknown subset preset {requested_preset!r}.")
        return requested_preset

    active_preset = selection_cfg.get("active_preset")
    if active_preset:
        if active_preset not in presets:
            raise ValueError(f"selection.active_preset references unknown preset {active_preset!r}.")
        return str(active_preset)
    return preset_order[0]


def _resolve_requested_preset_names(
    *,
    presets: dict[str, dict[str, Any]],
    preset_order: list[str],
    active_preset: str,
    requested_preset: str | None,
    generate_all: bool,
) -> list[str]:
    if requested_preset:
        return [requested_preset]
    if generate_all:
        return preset_order
    return [active_preset]


def _legacy_selection_spec(selection_cfg: dict[str, Any]) -> dict[str, Any]:
    include_filters: dict[str, Any] = {}
    super_classes = selection_cfg.get("super_classes")
    if super_classes is None:
        super_class = selection_cfg.get("super_class")
        super_classes = [super_class] if super_class else []
    if super_classes:
        include_filters["super_classes"] = list(super_classes)
    if selection_cfg.get("project_roles"):
        include_filters["project_roles"] = list(selection_cfg["project_roles"])
    if selection_cfg.get("cell_types"):
        include_filters["cell_types"] = list(selection_cfg["cell_types"])
    if selection_cfg.get("neuropils"):
        include_filters["neuropils"] = list(selection_cfg["neuropils"])
    if selection_cfg.get("column_ids"):
        include_filters["column_ids"] = list(selection_cfg["column_ids"])

    spec = {
        "description": selection_cfg.get("description", "Legacy single subset selection"),
        "include": include_filters,
        "exclude": deepcopy(selection_cfg.get("exclude", {})),
        "sort_by": selection_cfg.get("sort_by", "root_id"),
        "limit": selection_cfg.get("limit", 12),
        "preview_edge_limit": selection_cfg.get("preview_edge_limit", DEFAULT_PREVIEW_EDGE_LIMIT),
    }
    return _normalize_selection_spec(spec)


def _normalize_selection_spec(spec: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(spec)
    normalized.setdefault("include", {})
    normalized.setdefault("exclude", {})
    normalized.setdefault("relations", [])
    normalized.setdefault("sort_by", "root_id")
    normalized.setdefault("preview_edge_limit", DEFAULT_PREVIEW_EDGE_LIMIT)
    return normalized


def _deep_merge_specs(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if key not in merged:
            merged[key] = deepcopy(value)
            continue
        if isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge_specs(merged[key], value)
            continue
        if key == "relations" and isinstance(merged[key], list) and isinstance(value, list):
            merged[key] = [*deepcopy(merged[key]), *deepcopy(value)]
            continue
        merged[key] = deepcopy(value)
    return merged


def _artifact_paths_for_preset(base_dir: Path, preset_name: str) -> SubsetArtifactPaths:
    safe_name = re.sub(r"[^0-9A-Za-z._-]+", "_", preset_name).strip("_") or "default"
    artifact_dir = ensure_dir(base_dir / safe_name)
    return SubsetArtifactPaths(
        preset_name=preset_name,
        artifact_dir=artifact_dir,
        root_ids=artifact_dir / ROOT_IDS_FILENAME,
        selected_neurons_csv=artifact_dir / SELECTED_NEURONS_FILENAME,
        stats_json=artifact_dir / SUBSET_STATS_FILENAME,
        manifest_json=artifact_dir / SUBSET_MANIFEST_FILENAME,
        preview_markdown=artifact_dir / PREVIEW_FILENAME,
    )


def _write_subset_outputs(
    *,
    selected_df: pd.DataFrame,
    stats_payload: dict[str, Any],
    manifest_payload: dict[str, Any],
    preview_markdown: str,
    artifact_paths: SubsetArtifactPaths,
) -> None:
    write_root_ids(extract_root_ids(selected_df), artifact_paths.root_ids)
    selected_df.to_csv(artifact_paths.selected_neurons_csv, index=False)
    write_json(stats_payload, artifact_paths.stats_json)
    write_json(manifest_payload, artifact_paths.manifest_json)
    artifact_paths.preview_markdown.write_text(preview_markdown, encoding="utf-8")


def _apply_relation_expansion(
    *,
    neuron_registry: pd.DataFrame,
    connectivity_registry: pd.DataFrame,
    current_subset: pd.DataFrame,
    base_subset: pd.DataFrame,
    relation: dict[str, Any],
    max_neurons: int | None,
    sort_by: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if connectivity_registry.empty:
        relation_name = relation.get("name", relation.get("direction", "relation"))
        raise FileNotFoundError(
            f"Subset relation {relation_name!r} requires a connectivity registry. "
            "Run `make registry` with connections input available first."
        )

    direction = str(relation.get("direction", "downstream")).strip().lower()
    if direction not in {"upstream", "downstream", "both"}:
        raise ValueError(f"Unsupported relation direction {direction!r}.")

    hops = _coerce_optional_int(relation.get("hops")) or 1
    min_syn_count = _coerce_optional_int(relation.get("min_syn_count")) or 1
    max_added = _coerce_optional_int(relation.get("max_added"))
    relation_name = str(relation.get("name", direction))

    seed_source = str(relation.get("seed_from", "current")).strip().lower()
    if seed_source == "current":
        seed_frame = current_subset
    elif seed_source == "base":
        seed_frame = base_subset
    elif seed_source == "registry":
        seed_frame = neuron_registry
    else:
        raise ValueError(f"Unsupported relation seed_from {seed_source!r}.")

    seed_filters = deepcopy(relation.get("seed", {}))
    seed_frame = _apply_filters(seed_frame, seed_filters, mode="include")
    seed_frame = _normalize_root_id_column(seed_frame, _find_first_existing(seed_frame, ROOT_ID_CANDIDATES))
    seed_ids = extract_root_ids(seed_frame)
    if not seed_ids:
        report = {
            "name": relation_name,
            "direction": direction,
            "seed_count": 0,
            "reachable_count": 0,
            "candidate_count": 0,
            "added_count": 0,
            "added_root_ids": [],
            "reason": "seed selection produced no neurons",
        }
        return current_subset.copy(), report

    neighbor_sets = _neighbor_sets(connectivity_registry, direction=direction, min_syn_count=min_syn_count)
    reachable = reachable_nodes(sources=seed_ids, neighbor_sets=neighbor_sets, max_depth=hops)
    selected_root_ids = set(extract_root_ids(current_subset))
    reachable_ids = {int(root_id) for root_id, depth in reachable.items() if depth > 0}
    candidate_ids = reachable_ids - selected_root_ids

    candidate_subset = neuron_registry[neuron_registry["root_id"].isin(candidate_ids)].copy()
    candidate_subset = _apply_filters(candidate_subset, deepcopy(relation.get("include", {})), mode="include")
    candidate_subset = _apply_filters(candidate_subset, deepcopy(relation.get("exclude", {})), mode="exclude")

    if candidate_subset.empty:
        report = {
            "name": relation_name,
            "direction": direction,
            "seed_count": int(len(seed_ids)),
            "reachable_count": int(len(reachable_ids)),
            "candidate_count": 0,
            "added_count": 0,
            "added_root_ids": [],
            "hops": hops,
            "min_syn_count": min_syn_count,
            "max_added": max_added,
        }
        return current_subset.copy(), report

    candidate_subset["relation_distance"] = candidate_subset["root_id"].map(lambda rid: int(reachable.get(int(rid), hops + 1)))
    support_by_root = _relation_support_scores(
        connectivity_registry=connectivity_registry,
        seed_ids=set(seed_ids),
        candidate_ids=set(extract_root_ids(candidate_subset)),
        direction=direction,
    )
    candidate_subset["relation_support_synapses"] = candidate_subset["root_id"].map(
        lambda rid: int(support_by_root.get(int(rid), 0))
    )

    candidate_subset = _sort_subset(
        candidate_subset,
        sort_by=sort_by,
        extra_sort_columns=[
            ("relation_distance", True),
            ("relation_support_synapses", False),
        ],
    )

    room_remaining = None if max_neurons is None else max(0, max_neurons - len(current_subset))
    take_count = len(candidate_subset)
    if max_added is not None:
        take_count = min(take_count, max_added)
    if room_remaining is not None:
        take_count = min(take_count, room_remaining)

    added_subset = candidate_subset.head(take_count).copy()
    if added_subset.empty:
        report = {
            "name": relation_name,
            "direction": direction,
            "seed_count": int(len(seed_ids)),
            "reachable_count": int(len(reachable_ids)),
            "candidate_count": int(len(candidate_subset)),
            "added_count": 0,
            "added_root_ids": [],
            "hops": hops,
            "min_syn_count": min_syn_count,
            "max_added": max_added,
            "room_remaining": room_remaining,
        }
        return current_subset.copy(), report

    next_subset = pd.concat([current_subset, added_subset.drop(columns=["relation_distance", "relation_support_synapses"])], ignore_index=True)
    next_subset = next_subset.drop_duplicates(subset=["root_id"], keep="first").reset_index(drop=True)

    report = {
        "name": relation_name,
        "direction": direction,
        "seed_count": int(len(seed_ids)),
        "seed_root_ids": seed_ids,
        "reachable_count": int(len(reachable_ids)),
        "candidate_count": int(len(candidate_subset)),
        "added_count": int(len(added_subset)),
        "added_root_ids": extract_root_ids(added_subset),
        "hops": hops,
        "min_syn_count": min_syn_count,
        "max_added": max_added,
        "room_remaining": room_remaining,
    }
    return next_subset, report


def _apply_filters(df: pd.DataFrame, filters: dict[str, Any], *, mode: str) -> pd.DataFrame:
    if not filters:
        return df.copy()

    masks: list[pd.Series] = []
    for key, value in filters.items():
        if _is_empty_filter_value(value):
            continue
        masks.append(_mask_for_filter(df, key, value))

    if not masks:
        return df.copy()

    if mode == "include":
        combined_mask = pd.Series(True, index=df.index)
        for mask in masks:
            combined_mask = combined_mask & mask
    elif mode == "exclude":
        combined_mask = pd.Series(False, index=df.index)
        for mask in masks:
            combined_mask = combined_mask | mask
        combined_mask = ~combined_mask
    else:
        raise ValueError(f"Unknown filter mode {mode!r}.")

    return df.loc[combined_mask].copy()


def _mask_for_filter(df: pd.DataFrame, key: str, value: Any) -> pd.Series:
    root_col = _find_first_existing(df, ROOT_ID_CANDIDATES)
    normalized_key = str(key).strip().lower()

    if normalized_key == "root_ids":
        allowed = {int(item) for item in _normalized_int_values(value)}
        return df[root_col].isin(allowed)

    if normalized_key == "cell_types":
        allowed = _normalized_text_values(value)
        mask = _mask_across_columns(df, CELL_TYPE_MATCH_COLUMNS, allowed)
        if "additional_types" in df.columns:
            mask = mask | _mask_delimited_contains(df["additional_types"], allowed)
        return mask

    if normalized_key == "resolved_types":
        return _mask_across_columns(df, ["resolved_type"], _normalized_text_values(value))

    if normalized_key == "project_roles":
        return _mask_across_columns(df, PROJECT_ROLE_CANDIDATES, _normalized_text_values(value))

    if normalized_key == "super_classes":
        return _mask_across_columns(df, SUPER_CLASS_CANDIDATES, _normalized_text_values(value))

    if normalized_key == "classes":
        return _mask_across_columns(df, ["class"], _normalized_text_values(value))

    if normalized_key == "sub_classes":
        return _mask_across_columns(df, ["sub_class"], _normalized_text_values(value))

    if normalized_key in {"sides", "hemispheres"}:
        return _mask_across_columns(df, ["side", "hemisphere"], _normalized_text_values(value))

    if normalized_key == "neuropils":
        return _mask_delimited_contains(df[_require_column(df, "neuropils")], _expanded_neuropil_terms(value))

    if normalized_key == "input_neuropils":
        return _mask_delimited_contains(df[_require_column(df, "input_neuropils")], _expanded_neuropil_terms(value))

    if normalized_key == "output_neuropils":
        return _mask_delimited_contains(df[_require_column(df, "output_neuropils")], _expanded_neuropil_terms(value))

    if normalized_key == "column_ids":
        return _mask_numeric_exact(df[_require_column(df, "column_id")], _normalized_int_values(value))

    if normalized_key.endswith("_range"):
        column_name = normalized_key.removesuffix("_range")
        return _mask_numeric_range(df[_require_column(df, column_name)], value)

    raise ValueError(f"Unsupported selection filter key {key!r}.")


def _neighbor_sets(connectivity_registry: pd.DataFrame, *, direction: str, min_syn_count: int) -> dict[int, set[int]]:
    filtered = connectivity_registry[connectivity_registry["syn_count"] >= min_syn_count].copy()
    if filtered.empty:
        return {}

    if direction == "downstream":
        src_col = "pre_root_id"
        dst_col = "post_root_id"
    elif direction == "upstream":
        src_col = "post_root_id"
        dst_col = "pre_root_id"
    elif direction == "both":
        downstream = _neighbor_sets(connectivity_registry, direction="downstream", min_syn_count=min_syn_count)
        upstream = _neighbor_sets(connectivity_registry, direction="upstream", min_syn_count=min_syn_count)
        merged = {key: set(values) for key, values in downstream.items()}
        for key, values in upstream.items():
            merged.setdefault(key, set()).update(values)
        return merged
    else:  # pragma: no cover - protected by caller.
        raise ValueError(f"Unsupported direction {direction!r}.")

    neighbor_map: dict[int, set[int]] = {}
    for row in filtered.itertuples(index=False):
        source = int(getattr(row, src_col))
        target = int(getattr(row, dst_col))
        neighbor_map.setdefault(source, set()).add(target)
    return neighbor_map


def _relation_support_scores(
    *,
    connectivity_registry: pd.DataFrame,
    seed_ids: set[int],
    candidate_ids: set[int],
    direction: str,
) -> dict[int, int]:
    scores: Counter[int] = Counter()
    if not seed_ids or not candidate_ids:
        return {}

    if direction in {"downstream", "both"}:
        edges = connectivity_registry[
            connectivity_registry["pre_root_id"].isin(seed_ids) & connectivity_registry["post_root_id"].isin(candidate_ids)
        ]
        if not edges.empty:
            grouped = edges.groupby("post_root_id")["syn_count"].sum()
            for root_id, syn_count in grouped.items():
                scores[int(root_id)] += int(syn_count)

    if direction in {"upstream", "both"}:
        edges = connectivity_registry[
            connectivity_registry["post_root_id"].isin(seed_ids) & connectivity_registry["pre_root_id"].isin(candidate_ids)
        ]
        if not edges.empty:
            grouped = edges.groupby("pre_root_id")["syn_count"].sum()
            for root_id, syn_count in grouped.items():
                scores[int(root_id)] += int(syn_count)

    return dict(scores)


def _selected_connectivity(connectivity_registry: pd.DataFrame, selected_root_ids: set[int]) -> pd.DataFrame:
    if connectivity_registry.empty or not selected_root_ids:
        return pd.DataFrame(columns=connectivity_registry.columns)
    mask = connectivity_registry["pre_root_id"].isin(selected_root_ids) & connectivity_registry["post_root_id"].isin(selected_root_ids)
    return connectivity_registry.loc[mask].copy().reset_index(drop=True)


def _build_graph(selected_subset: pd.DataFrame, selected_edges: pd.DataFrame) -> nx.DiGraph:
    graph = nx.DiGraph()
    for root_id in extract_root_ids(selected_subset):
        graph.add_node(int(root_id))

    if selected_edges.empty:
        return graph

    grouped = (
        selected_edges.groupby(["pre_root_id", "post_root_id"], dropna=False)
        .agg(
            syn_count=("syn_count", "sum"),
            neuropil=("neuropil", lambda values: _join_unique_text(values)),
        )
        .reset_index()
    )
    for row in grouped.itertuples(index=False):
        graph.add_edge(
            int(row.pre_root_id),
            int(row.post_root_id),
            syn_count=int(row.syn_count),
            neuropil=str(row.neuropil or ""),
        )
    return graph


def _boundary_partner_stats(
    *,
    selected_root_ids: set[int],
    connectivity_registry: pd.DataFrame,
    neuron_registry: pd.DataFrame,
) -> dict[str, Any]:
    if connectivity_registry.empty or not selected_root_ids:
        return {
            "incoming_connection_rows": 0,
            "outgoing_connection_rows": 0,
            "incoming_synapse_count": 0,
            "outgoing_synapse_count": 0,
            "top_incoming_partners": [],
            "top_outgoing_partners": [],
        }

    incoming = connectivity_registry[
        connectivity_registry["post_root_id"].isin(selected_root_ids) & ~connectivity_registry["pre_root_id"].isin(selected_root_ids)
    ].copy()
    outgoing = connectivity_registry[
        connectivity_registry["pre_root_id"].isin(selected_root_ids) & ~connectivity_registry["post_root_id"].isin(selected_root_ids)
    ].copy()

    return {
        "incoming_connection_rows": int(len(incoming)),
        "outgoing_connection_rows": int(len(outgoing)),
        "incoming_synapse_count": int(incoming["syn_count"].sum()) if not incoming.empty else 0,
        "outgoing_synapse_count": int(outgoing["syn_count"].sum()) if not outgoing.empty else 0,
        "top_incoming_partners": _top_boundary_partners(
            incoming,
            partner_column="pre_root_id",
            neuron_registry=neuron_registry,
        ),
        "top_outgoing_partners": _top_boundary_partners(
            outgoing,
            partner_column="post_root_id",
            neuron_registry=neuron_registry,
        ),
    }


def _top_boundary_partners(
    edges: pd.DataFrame,
    *,
    partner_column: str,
    neuron_registry: pd.DataFrame,
    limit: int = 8,
) -> list[dict[str, Any]]:
    if edges.empty:
        return []

    grouped = edges.groupby(partner_column)["syn_count"].sum().sort_values(ascending=False).head(limit)
    lookup = neuron_registry.set_index("root_id") if "root_id" in neuron_registry.columns else None
    partners: list[dict[str, Any]] = []
    for root_id, syn_count in grouped.items():
        cell_type = None
        project_role = None
        if lookup is not None and int(root_id) in lookup.index:
            row = lookup.loc[int(root_id)]
            cell_type = _json_ready(row.get("cell_type"))
            project_role = _json_ready(row.get("project_role"))
        partners.append(
            {
                "root_id": int(root_id),
                "syn_count": int(syn_count),
                "cell_type": cell_type,
                "project_role": project_role,
            }
        )
    return partners


def _top_weighted_degree_nodes(
    graph: nx.DiGraph,
    selected_subset: pd.DataFrame,
    *,
    direction: str,
    limit: int = 8,
) -> list[dict[str, Any]]:
    if not graph.number_of_nodes():
        return []

    if direction == "out":
        degree_items = graph.out_degree(weight="syn_count")
    elif direction == "in":
        degree_items = graph.in_degree(weight="syn_count")
    else:  # pragma: no cover - protected by caller.
        raise ValueError(f"Unsupported degree direction {direction!r}.")

    lookup = selected_subset.set_index("root_id")
    ranked = sorted(((int(node), int(weight)) for node, weight in degree_items), key=lambda item: (-item[1], item[0]))
    results: list[dict[str, Any]] = []
    for node, weight in ranked[:limit]:
        row = lookup.loc[node]
        results.append(
            {
                "root_id": int(node),
                "syn_count": int(weight),
                "cell_type": _json_ready(row.get("cell_type")),
                "project_role": _json_ready(row.get("project_role")),
            }
        )
    return results


def _render_preview_markdown(
    *,
    preset_name: str,
    description: str,
    selected_subset: pd.DataFrame,
    selected_edges: pd.DataFrame,
    stats_payload: dict[str, Any],
    preview_edge_limit: int,
) -> str:
    selected_count = len(selected_subset)
    edge_rows = (
        selected_edges.groupby(["pre_root_id", "post_root_id"], dropna=False)
        .agg(
            syn_count=("syn_count", "sum"),
            neuropil=("neuropil", lambda values: _join_unique_text(values)),
        )
        .reset_index()
        .sort_values(["syn_count", "pre_root_id", "post_root_id"], ascending=[False, True, True])
        .head(preview_edge_limit)
    )
    lookup = selected_subset.set_index("root_id")

    lines = [
        f"# Subset Preview: {preset_name}",
        "",
        description or "No description provided.",
        "",
        f"- Selected neurons: {selected_count}",
        f"- Internal directed pairs: {stats_payload['graph']['internal_connection_pairs']}",
        f"- Internal synapses: {stats_payload['graph']['internal_synapse_count']}",
        "",
        "## Role counts",
    ]
    role_counts = stats_payload["counts"]["project_roles"]
    if role_counts:
        for role, count in role_counts.items():
            lines.append(f"- `{role}`: {count}")
    else:
        lines.append("- No roles present in subset")

    lines.extend(["", "## Preview graph"])
    if edge_rows.empty:
        lines.append("No internal connectivity edges were found inside this subset.")
        return "\n".join(lines) + "\n"

    lines.extend(["```mermaid", "graph LR"])
    preview_nodes = set(edge_rows["pre_root_id"]).union(set(edge_rows["post_root_id"]))
    for root_id in sorted(preview_nodes):
        if int(root_id) not in lookup.index:
            continue
        row = lookup.loc[int(root_id)]
        label = _mermaid_label(root_id=int(root_id), cell_type=row.get("cell_type"), role=row.get("project_role"))
        lines.append(f'    n{int(root_id)}["{label}"]')

    for row in edge_rows.itertuples(index=False):
        syn_label = int(row.syn_count)
        neuropil = f" {row.neuropil}" if row.neuropil else ""
        lines.append(f"    n{int(row.pre_root_id)} -->|{syn_label}{neuropil}| n{int(row.post_root_id)}")
    lines.extend(["```", "", "## Top cell types"])

    cell_type_counts = stats_payload["counts"]["cell_types"]
    if cell_type_counts:
        for cell_type, count in list(cell_type_counts.items())[:8]:
            lines.append(f"- `{cell_type}`: {count}")
    else:
        lines.append("- No typed neurons in subset")

    return "\n".join(lines) + "\n"


def _sort_subset(
    df: pd.DataFrame,
    *,
    sort_by: str,
    extra_sort_columns: list[tuple[str, bool]] | None = None,
) -> pd.DataFrame:
    root_col = _find_first_existing(df, ROOT_ID_CANDIDATES)
    sort_columns: list[str] = []
    ascending: list[bool] = []

    for column_name, direction_ascending in extra_sort_columns or []:
        if column_name in df.columns:
            sort_columns.append(column_name)
            ascending.append(direction_ascending)

    candidate_sort_column = root_col if sort_by == "root_id" else sort_by
    if candidate_sort_column in df.columns:
        sort_columns.append(candidate_sort_column)
        ascending.append(True)
    elif root_col not in sort_columns:
        sort_columns.append(root_col)
        ascending.append(True)

    if not sort_columns:
        return df.copy()
    return df.sort_values(sort_columns, ascending=ascending, kind="mergesort")


def _mask_across_columns(df: pd.DataFrame, columns: list[str], allowed_values: set[str]) -> pd.Series:
    if not allowed_values:
        return pd.Series(True, index=df.index)

    available_columns = [column for column in columns if column in df.columns]
    if not available_columns:
        raise ValueError(f"Selection requires one of the columns {columns}, but none were present.")

    mask = pd.Series(False, index=df.index)
    for column in available_columns:
        normalized = df[column].fillna("").astype(str).str.strip().str.lower()
        mask = mask | normalized.isin(allowed_values)
    return mask


def _mask_delimited_contains(series: pd.Series, allowed_values: set[str]) -> pd.Series:
    if not allowed_values:
        return pd.Series(True, index=series.index)
    normalized_values = {value.lower() for value in allowed_values}
    return series.fillna("").astype(str).apply(
        lambda raw: any(token.lower() in normalized_values for token in _split_multi_value(raw))
    )


def _mask_numeric_exact(series: pd.Series, allowed_values: list[int]) -> pd.Series:
    if not allowed_values:
        return pd.Series(True, index=series.index)
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.isin([int(value) for value in allowed_values])


def _mask_numeric_range(series: pd.Series, range_value: Any) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    lower_bound, upper_bound = _coerce_range(range_value)
    mask = pd.Series(True, index=series.index)
    if lower_bound is not None:
        mask = mask & numeric.ge(lower_bound)
    if upper_bound is not None:
        mask = mask & numeric.le(upper_bound)
    return mask.fillna(False)


def _counts_for_column(df: pd.DataFrame, column_name: str) -> dict[str, int]:
    if column_name not in df.columns:
        return {}
    counter = Counter(
        str(value).strip()
        for value in df[column_name].tolist()
        if pd.notna(value) and str(value).strip()
    )
    return {key: int(counter[key]) for key in sorted(counter, key=lambda item: (-counter[item], item))}


def _split_value_counts(series: pd.Series | None) -> dict[str, int]:
    if series is None:
        return {}
    counter: Counter[str] = Counter()
    for raw_value in series.fillna("").astype(str):
        counter.update(token for token in _split_multi_value(raw_value) if token)
    return {key: int(counter[key]) for key in sorted(counter, key=lambda item: (-counter[item], item))}


def _unique_sorted_ints(series: pd.Series | None) -> list[int]:
    if series is None:
        return []
    numeric = pd.to_numeric(series, errors="coerce").dropna().astype(int)
    return sorted({int(value) for value in numeric.tolist()})


def _largest_weak_component_size(graph: nx.DiGraph) -> int:
    if not graph.number_of_nodes():
        return 0
    return max((len(component) for component in nx.weakly_connected_components(graph)), default=0)


def _normalize_root_id_column(df: pd.DataFrame, root_col: str) -> pd.DataFrame:
    out = df.copy()
    out[root_col] = pd.to_numeric(out[root_col], errors="coerce")
    out = out.dropna(subset=[root_col]).copy()
    out[root_col] = out[root_col].astype("int64")
    out = out.drop_duplicates(subset=[root_col], keep="first")
    return out


def _normalized_text_values(value: Any) -> set[str]:
    return {str(item).strip().lower() for item in _as_list(value) if str(item).strip()}


def _expanded_neuropil_terms(value: Any) -> set[str]:
    expanded: set[str] = set()
    for item in _as_list(value):
        text = str(item).strip()
        if not text:
            continue
        matches = lookup_neuropil_set(text) or set()
        if matches:
            expanded.update(match.lower() for match in matches)
        else:
            expanded.add(text.lower())
    return expanded


def _normalized_int_values(value: Any) -> list[int]:
    normalized: list[int] = []
    for item in _as_list(value):
        if item is None or str(item).strip() == "":
            continue
        normalized.append(int(item))
    return normalized


def _coerce_range(value: Any) -> tuple[float | None, float | None]:
    if isinstance(value, dict):
        lower = value.get("min")
        upper = value.get("max")
    elif isinstance(value, (list, tuple)):
        if len(value) != 2:
            raise ValueError(f"Range filters must contain exactly two values, got {value!r}.")
        lower, upper = value
    else:
        raise ValueError(f"Range filters must be a [min, max] list or mapping, got {value!r}.")

    return (
        None if lower in (None, "") else float(lower),
        None if upper in (None, "") else float(upper),
    )


def _require_column(df: pd.DataFrame, column_name: str) -> str:
    if column_name not in df.columns:
        raise ValueError(f"Selection requires column {column_name!r}, but it is not present in the registry.")
    return column_name


def _coerce_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if value is pd.NA:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return int(value)


def _is_empty_filter_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, set, dict)) and not value:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _split_multi_value(raw_value: str) -> list[str]:
    return [token.strip() for token in re.split(r"[;,|]", str(raw_value)) if token.strip()]


def _join_unique_text(values: Iterable[Any]) -> str:
    items: list[str] = []
    for value in values:
        if pd.isna(value):
            continue
        items.extend(_split_multi_value(str(value)))
    return ";".join(sorted(dict.fromkeys(items)))


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return sorted(value)
    return [value]


def _mermaid_label(*, root_id: int, cell_type: Any, role: Any) -> str:
    cell_label = str(cell_type).strip() if cell_type is not None and str(cell_type).strip() else "untyped"
    role_label = str(role).strip() if role is not None and str(role).strip() else "unassigned"
    label = f"{root_id} {cell_label} [{role_label}]"
    return label.replace('"', "'")


def _df_to_records(df: pd.DataFrame, columns: list[str]) -> list[dict[str, Any]]:
    present_columns = [column for column in columns if column in df.columns]
    records: list[dict[str, Any]] = []
    for row in df.loc[:, present_columns].to_dict(orient="records"):
        records.append({key: _json_ready(value) for key, value in row.items()})
    return records


def _json_ready(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _now_utc_isoformat() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
