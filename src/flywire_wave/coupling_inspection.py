from __future__ import annotations

import copy
import hashlib
import html
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import scipy.sparse as sp

from .coupling_contract import (
    SUM_TO_ONE_PER_COMPONENT_NORMALIZATION,
    build_coupling_contract_paths,
    build_edge_coupling_bundle_path,
    build_root_coupling_bundle_paths,
)
from .geometry_contract import build_geometry_bundle_paths
from .io_utils import ensure_dir, write_json
from .registry import load_synapse_registry
from .surface_operators import deserialize_sparse_matrix
from .synapse_mapping import (
    ANCHOR_TYPE_POINT_STATE,
    ANCHOR_TYPE_SKELETON_NODE,
    ANCHOR_TYPE_SURFACE_PATCH,
    MAPPING_STATUS_BLOCKED,
    QUALITY_STATUS_WARN,
    load_edge_coupling_bundle,
    lookup_inbound_synapses,
    lookup_outbound_synapses,
)


COUPLING_INSPECTION_REPORT_VERSION = "coupling_inspection.v1"
SVG_WIDTH = 360
SVG_HEIGHT = 280
SVG_PADDING = 18.0
ROTATION_Z_DEGREES = 38.0
ROTATION_X_DEGREES = -28.0
EPSILON = 1.0e-12
EDGE_SPEC_PATTERN = re.compile(r"^\s*(\d+)\s*(?::|,|->)\s*(\d+)\s*$")
REPORT_PALETTE = (
    "#0f766e",
    "#b91c1c",
    "#d97706",
    "#1d4ed8",
    "#7c3aed",
    "#0369a1",
    "#475569",
    "#0f172a",
)

DEFAULT_COUPLING_INSPECTION_THRESHOLDS: dict[str, dict[str, Any]] = {
    "pre_mapped_fraction": {
        "warn": 1.0,
        "fail": 0.75,
        "comparison": "min",
        "blocking": True,
        "description": "Presynaptic readout coverage should stay near complete for edge review.",
    },
    "post_mapped_fraction": {
        "warn": 1.0,
        "fail": 0.75,
        "comparison": "min",
        "blocking": True,
        "description": "Postsynaptic landing coverage should stay near complete for edge review.",
    },
    "pre_quality_warn_fraction": {
        "warn": 0.0,
        "fail": 0.25,
        "comparison": "max",
        "blocking": False,
        "description": "Large presynaptic anchor residuals should stay rare.",
    },
    "post_quality_warn_fraction": {
        "warn": 0.0,
        "fail": 0.25,
        "comparison": "max",
        "blocking": False,
        "description": "Large postsynaptic anchor residuals should stay rare.",
    },
    "pre_fallback_fraction": {
        "warn": 0.0,
        "fail": 0.50,
        "comparison": "max",
        "blocking": False,
        "description": "Frequent presynaptic fallback use weakens geometry trust for simulator handoff.",
    },
    "post_fallback_fraction": {
        "warn": 0.0,
        "fail": 0.50,
        "comparison": "max",
        "blocking": False,
        "description": "Frequent postsynaptic fallback use weakens geometry trust for simulator handoff.",
    },
    "registry_row_mismatch_count": {
        "warn": None,
        "fail": 0.0,
        "comparison": "max",
        "blocking": True,
        "description": "The edge bundle should reference the exact same synapse rows as the local registry slice.",
    },
    "outgoing_anchor_row_mismatch_count": {
        "warn": None,
        "fail": 0.0,
        "comparison": "max",
        "blocking": True,
        "description": "The presynaptic root-local outgoing map should contain the exact edge rows.",
    },
    "incoming_anchor_row_mismatch_count": {
        "warn": None,
        "fail": 0.0,
        "comparison": "max",
        "blocking": True,
        "description": "The postsynaptic root-local incoming map should contain the exact edge rows.",
    },
    "outgoing_anchor_field_mismatch_count": {
        "warn": None,
        "fail": 0.0,
        "comparison": "max",
        "blocking": True,
        "description": "Presynaptic edge rows should agree with the outgoing anchor map on status and anchor identity.",
    },
    "incoming_anchor_field_mismatch_count": {
        "warn": None,
        "fail": 0.0,
        "comparison": "max",
        "blocking": True,
        "description": "Postsynaptic edge rows should agree with the incoming anchor map on status and anchor identity.",
    },
    "component_membership_gap": {
        "warn": None,
        "fail": 0.0,
        "comparison": "max",
        "blocking": True,
        "description": "Usable synapses should each appear exactly once in the component-membership table.",
    },
    "source_cloud_unit_sum_residual_max": {
        "warn": 1.0e-6,
        "fail": 1.0e-4,
        "comparison": "max",
        "blocking": True,
        "description": "Source cloud weights should respect the declared normalization mode.",
    },
    "target_cloud_unit_sum_residual_max": {
        "warn": 1.0e-6,
        "fail": 1.0e-4,
        "comparison": "max",
        "blocking": True,
        "description": "Target cloud weights should respect the declared normalization mode.",
    },
    "signed_weight_residual_abs_max": {
        "warn": 1.0e-9,
        "fail": 1.0e-6,
        "comparison": "max",
        "blocking": True,
        "description": "Component signed-weight totals should match the summed per-synapse membership weights.",
    },
    "absolute_weight_residual_abs_max": {
        "warn": 1.0e-9,
        "fail": 1.0e-6,
        "comparison": "max",
        "blocking": True,
        "description": "Component absolute-weight totals should match the summed per-synapse membership weights.",
    },
    "negative_delay_count": {
        "warn": None,
        "fail": 0.0,
        "comparison": "max",
        "blocking": True,
        "description": "Delays must remain finite and non-negative in the shipped coupling bundle.",
    },
    "nan_delay_count": {
        "warn": None,
        "fail": 0.0,
        "comparison": "max",
        "blocking": True,
        "description": "Usable per-synapse delays should remain finite in the shipped coupling bundle.",
    },
}

_CORE_REQUIRED_INPUTS = (
    ("local_synapse_registry", "local_synapse_registry_path", "missing_local_synapse_registry"),
    ("edge_coupling_bundle", "edge_bundle_path", "missing_edge_coupling_bundle"),
    ("pre_outgoing_anchor_map", "pre_outgoing_anchor_map_path", "missing_pre_outgoing_anchor_map"),
    ("post_incoming_anchor_map", "post_incoming_anchor_map_path", "missing_post_incoming_anchor_map"),
)


@dataclass(frozen=True)
class ProjectionFrame:
    rotation: np.ndarray
    center: np.ndarray
    xy_min: np.ndarray
    xy_max: np.ndarray
    scale: float


@dataclass(frozen=True)
class RootVisualContext:
    root_id: int
    project_role: str
    cell_type: str
    patch_points: np.ndarray
    patch_edges: np.ndarray
    surface_points: np.ndarray
    surface_edges: np.ndarray
    skeleton_points: np.ndarray
    skeleton_edges: np.ndarray


def parse_edge_spec(value: str) -> tuple[int, int]:
    match = EDGE_SPEC_PATTERN.match(str(value))
    if match is None:
        raise ValueError(
            f"Invalid edge spec {value!r}. Use one of 'pre:post', 'pre,post', or 'pre->post'."
        )
    return int(match.group(1)), int(match.group(2))


def read_edge_specs(path: str | Path) -> list[tuple[int, int]]:
    edge_specs: list[tuple[int, int]] = []
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        edge_specs.append(parse_edge_spec(line))
    return edge_specs


def build_coupling_inspection_output_dir(
    coupling_inspection_dir: str | Path,
    edge_specs: Iterable[tuple[int, int]],
) -> Path:
    return Path(coupling_inspection_dir).resolve() / build_coupling_inspection_slug(edge_specs)


def build_coupling_inspection_slug(edge_specs: Iterable[tuple[int, int]]) -> str:
    normalized = _normalize_edge_specs(edge_specs)
    joined = "__".join(_edge_slug(pre_root_id, post_root_id) for pre_root_id, post_root_id in normalized)
    if len(joined) <= 80:
        return f"edges-{joined}"
    digest = hashlib.sha1(",".join(f"{pre}:{post}" for pre, post in normalized).encode("utf-8")).hexdigest()[:12]
    prefix = "__".join(_edge_slug(pre, post) for pre, post in normalized[:2])
    return f"edges-{prefix}-n{len(normalized)}-{digest}"


def resolve_coupling_inspection_thresholds(
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    thresholds = copy.deepcopy(DEFAULT_COUPLING_INSPECTION_THRESHOLDS)
    if not overrides:
        return thresholds

    for metric_name, override in overrides.items():
        if isinstance(override, Mapping):
            thresholds.setdefault(metric_name, {})
            thresholds[metric_name].update(copy.deepcopy(dict(override)))
        else:
            thresholds.setdefault(metric_name, {})
            thresholds[metric_name]["fail"] = override
    return thresholds


def evaluate_coupling_inspection_metrics(
    *,
    metrics: Mapping[str, float],
    thresholds: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    resolved_thresholds = resolve_coupling_inspection_thresholds(thresholds)
    checks: dict[str, dict[str, Any]] = {}
    warning_count = 0
    failure_count = 0
    blocking_failure_count = 0

    for metric_name, value in sorted(metrics.items()):
        config = dict(resolved_thresholds.get(metric_name, {}))
        comparison = str(config.get("comparison", "max"))
        warn_threshold = config.get("warn")
        fail_threshold = config.get("fail")
        blocking = bool(config.get("blocking", False))

        status = "pass"
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            status = "fail"
            failure_count += 1
            if blocking:
                blocking_failure_count += 1
        elif comparison == "min":
            if fail_threshold is not None and numeric_value < float(fail_threshold):
                status = "fail"
                failure_count += 1
                if blocking:
                    blocking_failure_count += 1
            elif warn_threshold is not None and numeric_value < float(warn_threshold):
                status = "warn"
                warning_count += 1
        else:
            if fail_threshold is not None and numeric_value > float(fail_threshold):
                status = "fail"
                failure_count += 1
                if blocking:
                    blocking_failure_count += 1
            elif warn_threshold is not None and numeric_value > float(warn_threshold):
                status = "warn"
                warning_count += 1

        checks[metric_name] = {
            "status": status,
            "value": numeric_value,
            "warn_threshold": None if warn_threshold is None else float(warn_threshold),
            "fail_threshold": None if fail_threshold is None else float(fail_threshold),
            "comparison": comparison,
            "blocking": blocking,
            "description": str(config.get("description", "")),
        }

    if failure_count > 0:
        overall_status = "fail"
    elif warning_count > 0:
        overall_status = "warn"
    else:
        overall_status = "pass"

    return checks, {
        "overall_status": overall_status,
        "warning_count": warning_count,
        "failure_count": failure_count,
        "blocking_failure_count": blocking_failure_count,
    }


def generate_coupling_inspection_report(
    *,
    edge_specs: Iterable[tuple[int, int]],
    processed_coupling_dir: str | Path,
    meshes_raw_dir: str | Path,
    skeletons_raw_dir: str | Path,
    processed_mesh_dir: str | Path,
    processed_graph_dir: str | Path,
    coupling_inspection_dir: str | Path,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_edge_specs = _normalize_edge_specs(edge_specs)
    output_dir = build_coupling_inspection_output_dir(coupling_inspection_dir, normalized_edge_specs)
    ensure_dir(output_dir)

    contract_paths = build_coupling_contract_paths(processed_coupling_dir)
    registry_df = (
        load_synapse_registry(contract_paths.local_synapse_registry_path)
        if contract_paths.local_synapse_registry_path.exists()
        else None
    )
    resolved_thresholds = resolve_coupling_inspection_thresholds(thresholds)

    edge_entries = [
        _build_edge_entry(
            pre_root_id=pre_root_id,
            post_root_id=post_root_id,
            processed_coupling_dir=processed_coupling_dir,
            meshes_raw_dir=meshes_raw_dir,
            skeletons_raw_dir=skeletons_raw_dir,
            processed_mesh_dir=processed_mesh_dir,
            processed_graph_dir=processed_graph_dir,
            output_dir=output_dir,
            thresholds=resolved_thresholds,
            registry_df=registry_df,
        )
        for pre_root_id, post_root_id in normalized_edge_specs
    ]

    status_counts = {
        "pass": sum(1 for entry in edge_entries if entry["summary"]["overall_status"] == "pass"),
        "warn": sum(1 for entry in edge_entries if entry["summary"]["overall_status"] == "warn"),
        "fail": sum(1 for entry in edge_entries if entry["summary"]["overall_status"] == "fail"),
        "blocked": sum(1 for entry in edge_entries if entry["summary"]["overall_status"] == "blocked"),
    }
    if status_counts["blocked"] > 0:
        overall_status = "blocked"
    elif status_counts["fail"] > 0:
        overall_status = "fail"
    elif status_counts["warn"] > 0:
        overall_status = "warn"
    else:
        overall_status = "pass"

    report_path = (output_dir / "index.html").resolve()
    summary_path = (output_dir / "summary.json").resolve()
    markdown_path = (output_dir / "report.md").resolve()
    edge_specs_path = (output_dir / "edges.txt").resolve()

    summary = {
        "report_version": COUPLING_INSPECTION_REPORT_VERSION,
        "edge_count": len(normalized_edge_specs),
        "edges": [
            {
                "pre_root_id": int(pre_root_id),
                "post_root_id": int(post_root_id),
                "edge_label": _edge_label(pre_root_id, post_root_id),
            }
            for pre_root_id, post_root_id in normalized_edge_specs
        ],
        "output_dir": str(output_dir.resolve()),
        "report_path": str(report_path),
        "summary_path": str(summary_path),
        "markdown_path": str(markdown_path),
        "edge_specs_path": str(edge_specs_path),
        "overall_status": overall_status,
        "warning_count": sum(int(entry["summary"]["warning_count"]) for entry in edge_entries),
        "failure_count": sum(int(entry["summary"]["failure_count"]) for entry in edge_entries),
        "blocking_failure_count": sum(int(entry["summary"]["blocking_failure_count"]) for entry in edge_entries),
        "blocked_edge_count": status_counts["blocked"],
        "status_counts": status_counts,
        "edges_by_id": {
            str(entry["edge_label"]): _edge_summary_payload(entry)
            for entry in edge_entries
        },
    }

    report_path.write_text(_render_report_html(edge_entries=edge_entries, summary=summary), encoding="utf-8")
    markdown_path.write_text(_render_report_markdown(edge_entries=edge_entries, summary=summary), encoding="utf-8")
    write_json(summary, summary_path)
    edge_specs_path.write_text(
        "".join(f"{pre_root_id},{post_root_id}\n" for pre_root_id, post_root_id in normalized_edge_specs),
        encoding="utf-8",
    )
    return summary


def _edge_summary_payload(entry: Mapping[str, Any]) -> dict[str, Any]:
    summary = {
        "overall_status": str(entry["summary"]["overall_status"]),
        "warning_count": int(entry["summary"]["warning_count"]),
        "failure_count": int(entry["summary"]["failure_count"]),
        "blocking_failure_count": int(entry["summary"]["blocking_failure_count"]),
        "artifacts": dict(entry["artifacts"]),
    }
    if summary["overall_status"] == "blocked":
        summary["missing_prerequisite_count"] = int(entry["summary"].get("missing_prerequisite_count", 0))
        summary["missing_prerequisites"] = list(entry.get("missing_prerequisites", []))
        return summary

    summary.update(
        {
            "synapse_count": int(entry["edge_bundle_summary"]["synapse_count"]),
            "usable_synapse_count": int(entry["edge_bundle_summary"]["usable_synapse_count"]),
            "blocked_synapse_count": int(entry["edge_bundle_summary"]["blocked_synapse_count"]),
            "component_count": int(entry["aggregation_summary"]["component_count"]),
            "source_anchor_count": int(entry["aggregation_summary"]["source_anchor_count"]),
            "target_anchor_count": int(entry["aggregation_summary"]["target_anchor_count"]),
            "pre_mapped_fraction": float(entry["source_summary"]["mapped_fraction"]),
            "post_mapped_fraction": float(entry["target_summary"]["mapped_fraction"]),
            "qa_flags": list(entry["qa_flags"]),
        }
    )
    return summary


def _build_edge_entry(
    *,
    pre_root_id: int,
    post_root_id: int,
    processed_coupling_dir: str | Path,
    meshes_raw_dir: str | Path,
    skeletons_raw_dir: str | Path,
    processed_mesh_dir: str | Path,
    processed_graph_dir: str | Path,
    output_dir: Path,
    thresholds: Mapping[str, Any],
    registry_df: pd.DataFrame | None,
) -> dict[str, Any]:
    edge_label = _edge_label(pre_root_id, post_root_id)
    contract_paths = build_coupling_contract_paths(processed_coupling_dir)
    pre_root_paths = build_root_coupling_bundle_paths(pre_root_id, processed_coupling_dir=processed_coupling_dir)
    post_root_paths = build_root_coupling_bundle_paths(post_root_id, processed_coupling_dir=processed_coupling_dir)
    edge_bundle_path = build_edge_coupling_bundle_path(
        pre_root_id,
        post_root_id,
        processed_coupling_dir=processed_coupling_dir,
    )
    input_paths = {
        "local_synapse_registry_path": str(contract_paths.local_synapse_registry_path.resolve()),
        "edge_bundle_path": str(edge_bundle_path.resolve()),
        "pre_outgoing_anchor_map_path": str(pre_root_paths.outgoing_anchor_map_path.resolve()),
        "post_incoming_anchor_map_path": str(post_root_paths.incoming_anchor_map_path.resolve()),
    }
    missing_prerequisites = [
        _missing_prerequisite(
            asset_key=asset_key,
            path=str(Path(input_paths[path_key]).resolve()),
            reason=reason,
        )
        for asset_key, path_key, reason in _CORE_REQUIRED_INPUTS
        if not Path(input_paths[path_key]).exists()
    ]
    if missing_prerequisites:
        return _build_blocked_edge_entry(
            edge_label=edge_label,
            pre_root_id=pre_root_id,
            post_root_id=post_root_id,
            input_paths=input_paths,
            output_dir=output_dir,
            missing_prerequisites=missing_prerequisites,
        )

    edge_bundle = load_edge_coupling_bundle(edge_bundle_path)
    outgoing_anchor_map = lookup_outbound_synapses(
        pre_root_id,
        processed_coupling_dir=processed_coupling_dir,
        post_root_id=post_root_id,
    )
    incoming_anchor_map = lookup_inbound_synapses(
        post_root_id,
        processed_coupling_dir=processed_coupling_dir,
        pre_root_id=pre_root_id,
    )
    registry_edge = _filter_registry_edge_rows(
        registry_df,
        pre_root_id=pre_root_id,
        post_root_id=post_root_id,
    )

    source_context, source_context_summary, source_missing = _load_root_visual_context(
        root_id=pre_root_id,
        side_prefix="pre",
        synapse_table=edge_bundle.synapse_table,
        meshes_raw_dir=meshes_raw_dir,
        skeletons_raw_dir=skeletons_raw_dir,
        processed_mesh_dir=processed_mesh_dir,
        processed_graph_dir=processed_graph_dir,
    )
    target_context, target_context_summary, target_missing = _load_root_visual_context(
        root_id=post_root_id,
        side_prefix="post",
        synapse_table=edge_bundle.synapse_table,
        meshes_raw_dir=meshes_raw_dir,
        skeletons_raw_dir=skeletons_raw_dir,
        processed_mesh_dir=processed_mesh_dir,
        processed_graph_dir=processed_graph_dir,
    )
    missing_prerequisites = [*source_missing, *target_missing]
    if missing_prerequisites:
        input_paths.update(
            {
                "pre_patch_graph_path": str(
                    build_geometry_bundle_paths(
                        pre_root_id,
                        meshes_raw_dir=meshes_raw_dir,
                        skeletons_raw_dir=skeletons_raw_dir,
                        processed_mesh_dir=processed_mesh_dir,
                        processed_graph_dir=processed_graph_dir,
                    ).patch_graph_path.resolve()
                ),
                "post_patch_graph_path": str(
                    build_geometry_bundle_paths(
                        post_root_id,
                        meshes_raw_dir=meshes_raw_dir,
                        skeletons_raw_dir=skeletons_raw_dir,
                        processed_mesh_dir=processed_mesh_dir,
                        processed_graph_dir=processed_graph_dir,
                    ).patch_graph_path.resolve()
                ),
            }
        )
        return _build_blocked_edge_entry(
            edge_label=edge_label,
            pre_root_id=pre_root_id,
            post_root_id=post_root_id,
            input_paths=input_paths,
            output_dir=output_dir,
            missing_prerequisites=missing_prerequisites,
        )

    metrics = _build_edge_metrics(
        edge_bundle=edge_bundle,
        registry_edge=registry_edge,
        outgoing_anchor_map=outgoing_anchor_map,
        incoming_anchor_map=incoming_anchor_map,
    )
    checks, summary = evaluate_coupling_inspection_metrics(metrics=metrics, thresholds=thresholds)
    qa_flags = _build_qa_flags(checks)

    source_summary = _build_side_summary(edge_bundle.synapse_table, side_prefix="pre")
    target_summary = _build_side_summary(edge_bundle.synapse_table, side_prefix="post")
    edge_bundle_summary = _build_edge_bundle_summary(edge_bundle)
    aggregation_summary = _build_aggregation_summary(edge_bundle)
    delay_summary = _build_delay_summary(edge_bundle)
    sign_summary = _build_sign_summary(edge_bundle)

    artifact_paths = _write_edge_artifacts(
        edge_label=edge_label,
        output_dir=output_dir,
        source_context=source_context,
        target_context=target_context,
        edge_bundle=edge_bundle,
    )

    input_paths.update(
        {
            "pre_patch_graph_path": str(
                build_geometry_bundle_paths(
                    pre_root_id,
                    meshes_raw_dir=meshes_raw_dir,
                    skeletons_raw_dir=skeletons_raw_dir,
                    processed_mesh_dir=processed_mesh_dir,
                    processed_graph_dir=processed_graph_dir,
                ).patch_graph_path.resolve()
            ),
            "pre_surface_graph_path": str(
                build_geometry_bundle_paths(
                    pre_root_id,
                    meshes_raw_dir=meshes_raw_dir,
                    skeletons_raw_dir=skeletons_raw_dir,
                    processed_mesh_dir=processed_mesh_dir,
                    processed_graph_dir=processed_graph_dir,
                ).surface_graph_path.resolve()
            ),
            "pre_skeleton_path": str(
                build_geometry_bundle_paths(
                    pre_root_id,
                    meshes_raw_dir=meshes_raw_dir,
                    skeletons_raw_dir=skeletons_raw_dir,
                    processed_mesh_dir=processed_mesh_dir,
                    processed_graph_dir=processed_graph_dir,
                ).raw_skeleton_path.resolve()
            ),
            "post_patch_graph_path": str(
                build_geometry_bundle_paths(
                    post_root_id,
                    meshes_raw_dir=meshes_raw_dir,
                    skeletons_raw_dir=skeletons_raw_dir,
                    processed_mesh_dir=processed_mesh_dir,
                    processed_graph_dir=processed_graph_dir,
                ).patch_graph_path.resolve()
            ),
            "post_surface_graph_path": str(
                build_geometry_bundle_paths(
                    post_root_id,
                    meshes_raw_dir=meshes_raw_dir,
                    skeletons_raw_dir=skeletons_raw_dir,
                    processed_mesh_dir=processed_mesh_dir,
                    processed_graph_dir=processed_graph_dir,
                ).surface_graph_path.resolve()
            ),
            "post_skeleton_path": str(
                build_geometry_bundle_paths(
                    post_root_id,
                    meshes_raw_dir=meshes_raw_dir,
                    skeletons_raw_dir=skeletons_raw_dir,
                    processed_mesh_dir=processed_mesh_dir,
                    processed_graph_dir=processed_graph_dir,
                ).raw_skeleton_path.resolve()
            ),
        }
    )

    detail_payload = {
        "report_version": COUPLING_INSPECTION_REPORT_VERSION,
        "edge_label": edge_label,
        "pre_root_id": int(pre_root_id),
        "post_root_id": int(post_root_id),
        "input_paths": input_paths,
        "edge_bundle_summary": edge_bundle_summary,
        "source_summary": source_summary,
        "target_summary": target_summary,
        "aggregation_summary": aggregation_summary,
        "delay_summary": delay_summary,
        "sign_summary": sign_summary,
        "source_geometry": source_context_summary,
        "target_geometry": target_context_summary,
        "qa_flags": qa_flags,
        "metrics": metrics,
        "checks": checks,
        "summary": summary,
        "artifacts": artifact_paths,
        "component_table": _records(edge_bundle.component_table),
        "blocked_synapses": _records(edge_bundle.blocked_synapse_table),
    }

    detail_json_path = output_dir / f"{edge_label}_details.json"
    artifact_paths["details_json_path"] = str(detail_json_path.resolve())
    detail_payload["artifacts"] = artifact_paths
    write_json(detail_payload, detail_json_path)

    return {
        "edge_label": edge_label,
        "pre_root_id": int(pre_root_id),
        "post_root_id": int(post_root_id),
        "input_paths": input_paths,
        "edge_bundle_summary": edge_bundle_summary,
        "source_summary": source_summary,
        "target_summary": target_summary,
        "aggregation_summary": aggregation_summary,
        "delay_summary": delay_summary,
        "sign_summary": sign_summary,
        "source_geometry": source_context_summary,
        "target_geometry": target_context_summary,
        "qa_flags": qa_flags,
        "metrics": metrics,
        "checks": checks,
        "summary": summary,
        "artifacts": artifact_paths,
        "blocked_synapses": _records(edge_bundle.blocked_synapse_table),
        "component_table": _records(edge_bundle.component_table),
    }


def _build_blocked_edge_entry(
    *,
    edge_label: str,
    pre_root_id: int,
    post_root_id: int,
    input_paths: Mapping[str, str],
    output_dir: Path,
    missing_prerequisites: list[dict[str, str]],
) -> dict[str, Any]:
    detail_json_path = output_dir / f"{edge_label}_details.json"
    detail_payload = {
        "report_version": COUPLING_INSPECTION_REPORT_VERSION,
        "edge_label": edge_label,
        "pre_root_id": int(pre_root_id),
        "post_root_id": int(post_root_id),
        "input_paths": dict(input_paths),
        "missing_prerequisites": list(missing_prerequisites),
        "prerequisite_status": "missing",
        "metrics": {},
        "checks": {},
        "summary": {
            "overall_status": "blocked",
            "warning_count": 0,
            "failure_count": 0,
            "blocking_failure_count": 0,
            "missing_prerequisite_count": len(missing_prerequisites),
        },
        "artifacts": {
            "details_json_path": str(detail_json_path.resolve()),
        },
    }
    write_json(detail_payload, detail_json_path)
    return {
        "edge_label": edge_label,
        "pre_root_id": int(pre_root_id),
        "post_root_id": int(post_root_id),
        "input_paths": dict(input_paths),
        "metrics": {},
        "checks": {},
        "summary": detail_payload["summary"],
        "artifacts": dict(detail_payload["artifacts"]),
        "missing_prerequisites": list(missing_prerequisites),
    }


def _filter_registry_edge_rows(
    registry_df: pd.DataFrame | None,
    *,
    pre_root_id: int,
    post_root_id: int,
) -> pd.DataFrame:
    if registry_df is None:
        return pd.DataFrame()
    return (
        registry_df.loc[
            (registry_df["pre_root_id"] == int(pre_root_id))
            & (registry_df["post_root_id"] == int(post_root_id))
        ]
        .sort_values(["source_row_number", "synapse_row_id"], kind="mergesort")
        .reset_index(drop=True)
    )


def _build_edge_metrics(
    *,
    edge_bundle: Any,
    registry_edge: pd.DataFrame,
    outgoing_anchor_map: pd.DataFrame,
    incoming_anchor_map: pd.DataFrame,
) -> dict[str, float]:
    synapse_table = edge_bundle.synapse_table
    total_synapse_count = int(len(synapse_table))
    blocked_synapse_count = int(len(edge_bundle.blocked_synapse_table))
    expected_usable_synapse_count = max(total_synapse_count - blocked_synapse_count, 0)
    component_membership_count = int(edge_bundle.component_synapse_table["synapse_row_id"].nunique())

    metrics = {
        "pre_mapped_fraction": _fraction(
            int(np.count_nonzero(synapse_table["pre_mapping_status"] != MAPPING_STATUS_BLOCKED)),
            total_synapse_count,
        ),
        "post_mapped_fraction": _fraction(
            int(np.count_nonzero(synapse_table["post_mapping_status"] != MAPPING_STATUS_BLOCKED)),
            total_synapse_count,
        ),
        "pre_quality_warn_fraction": _fraction(
            int(np.count_nonzero(synapse_table["pre_quality_status"] == QUALITY_STATUS_WARN)),
            total_synapse_count,
        ),
        "post_quality_warn_fraction": _fraction(
            int(np.count_nonzero(synapse_table["post_quality_status"] == QUALITY_STATUS_WARN)),
            total_synapse_count,
        ),
        "pre_fallback_fraction": _fraction(
            int(np.count_nonzero(synapse_table["pre_fallback_used"].fillna(False).to_numpy(dtype=bool))),
            total_synapse_count,
        ),
        "post_fallback_fraction": _fraction(
            int(np.count_nonzero(synapse_table["post_fallback_used"].fillna(False).to_numpy(dtype=bool))),
            total_synapse_count,
        ),
        "registry_row_mismatch_count": float(
            _row_mismatch_count(synapse_table, registry_edge)
        ),
        "outgoing_anchor_row_mismatch_count": float(
            _row_mismatch_count(synapse_table, outgoing_anchor_map)
        ),
        "incoming_anchor_row_mismatch_count": float(
            _row_mismatch_count(synapse_table, incoming_anchor_map)
        ),
        "outgoing_anchor_field_mismatch_count": float(
            _anchor_field_mismatch_count(synapse_table, outgoing_anchor_map, side_prefix="pre")
        ),
        "incoming_anchor_field_mismatch_count": float(
            _anchor_field_mismatch_count(synapse_table, incoming_anchor_map, side_prefix="post")
        ),
        "component_membership_gap": float(abs(component_membership_count - expected_usable_synapse_count)),
        "source_cloud_unit_sum_residual_max": float(
            _cloud_unit_sum_residual_max(
                edge_bundle.source_cloud_table,
                edge_bundle.component_table,
                normalization=edge_bundle.source_cloud_normalization,
            )
        ),
        "target_cloud_unit_sum_residual_max": float(
            _cloud_unit_sum_residual_max(
                edge_bundle.target_cloud_table,
                edge_bundle.component_table,
                normalization=edge_bundle.target_cloud_normalization,
            )
        ),
        "signed_weight_residual_abs_max": float(
            _component_weight_residual(
                component_table=edge_bundle.component_table,
                component_synapse_table=edge_bundle.component_synapse_table,
                membership_column="signed_weight",
                component_total_column="signed_weight_total",
            )
        ),
        "absolute_weight_residual_abs_max": float(
            _component_weight_residual(
                component_table=edge_bundle.component_table,
                component_synapse_table=edge_bundle.component_synapse_table,
                membership_column="absolute_weight",
                component_total_column="absolute_weight_total",
            )
        ),
        "negative_delay_count": float(_delay_count(edge_bundle.component_synapse_table["delay_ms"], mode="negative")),
        "nan_delay_count": float(_delay_count(edge_bundle.component_synapse_table["delay_ms"], mode="nonfinite")),
    }
    return metrics


def _build_side_summary(synapse_table: pd.DataFrame, *, side_prefix: str) -> dict[str, Any]:
    total_synapse_count = int(len(synapse_table))
    mapping_status_counts = _count_values(synapse_table[f"{side_prefix}_mapping_status"])
    quality_status_counts = _count_values(synapse_table[f"{side_prefix}_quality_status"])
    fallback_count = int(
        np.count_nonzero(synapse_table[f"{side_prefix}_fallback_used"].fillna(False).to_numpy(dtype=bool))
    )
    mapped_count = total_synapse_count - int(mapping_status_counts.get(MAPPING_STATUS_BLOCKED, 0))
    return {
        "mapped_fraction": _fraction(mapped_count, total_synapse_count),
        "mapping_status_counts": mapping_status_counts,
        "quality_status_counts": quality_status_counts,
        "query_source_counts": _count_values(synapse_table[f"{side_prefix}_query_source"]),
        "anchor_mode_counts": _count_values(synapse_table[f"{side_prefix}_anchor_mode"]),
        "anchor_type_counts": _count_values(synapse_table[f"{side_prefix}_anchor_type"]),
        "fallback_count": fallback_count,
        "fallback_fraction": _fraction(fallback_count, total_synapse_count),
    }


def _build_edge_bundle_summary(edge_bundle: Any) -> dict[str, Any]:
    total_synapse_count = int(len(edge_bundle.synapse_table))
    blocked_synapse_count = int(len(edge_bundle.blocked_synapse_table))
    return {
        "status": str(edge_bundle.status),
        "topology_family": str(edge_bundle.topology_family),
        "kernel_family": str(edge_bundle.kernel_family),
        "aggregation_rule": str(edge_bundle.aggregation_rule),
        "delay_model": str(edge_bundle.delay_model),
        "delay_representation": str(edge_bundle.delay_representation),
        "sign_representation": str(edge_bundle.sign_representation),
        "missing_geometry_policy": str(edge_bundle.missing_geometry_policy),
        "source_cloud_normalization": str(edge_bundle.source_cloud_normalization),
        "target_cloud_normalization": str(edge_bundle.target_cloud_normalization),
        "synapse_count": total_synapse_count,
        "usable_synapse_count": max(total_synapse_count - blocked_synapse_count, 0),
        "blocked_synapse_count": blocked_synapse_count,
        "neuropil_counts": _count_values(edge_bundle.synapse_table["neuropil"]),
        "nt_type_counts": _count_values(edge_bundle.synapse_table["nt_type"]),
    }


def _build_aggregation_summary(edge_bundle: Any) -> dict[str, Any]:
    component_table = edge_bundle.component_table
    component_synapse_counts = component_table["synapse_count"].to_numpy(dtype=np.int64) if not component_table.empty else np.empty(0, dtype=np.int64)
    return {
        "component_count": int(len(component_table)),
        "source_anchor_count": int(len(edge_bundle.source_anchor_table)),
        "target_anchor_count": int(len(edge_bundle.target_anchor_table)),
        "max_synapses_per_component": int(component_synapse_counts.max()) if component_synapse_counts.size else 0,
        "mean_synapses_per_component": _safe_float(component_synapse_counts.mean() if component_synapse_counts.size else 0.0),
        "component_sign_counts": _count_values(component_table["sign_label"]) if not component_table.empty else {},
        "component_delay_bin_counts": _count_values(component_table["delay_bin_label"]) if not component_table.empty else {},
    }


def _build_delay_summary(edge_bundle: Any) -> dict[str, Any]:
    delay_values = (
        edge_bundle.component_synapse_table["delay_ms"].to_numpy(dtype=np.float64)
        if not edge_bundle.component_synapse_table.empty
        else np.empty(0, dtype=np.float64)
    )
    finite_delay_values = delay_values[np.isfinite(delay_values)]
    return {
        "delay_model": str(edge_bundle.delay_model),
        "delay_representation": str(edge_bundle.delay_representation),
        "delay_bin_labels": sorted(
            {
                str(value)
                for value in edge_bundle.component_table["delay_bin_label"].tolist()
                if str(value).strip()
            }
        ),
        "delay_min_ms": _safe_float(finite_delay_values.min() if finite_delay_values.size else float("nan")),
        "delay_max_ms": _safe_float(finite_delay_values.max() if finite_delay_values.size else float("nan")),
        "delay_mean_ms": _safe_float(finite_delay_values.mean() if finite_delay_values.size else float("nan")),
        "delay_model_parameters": {
            key: float(value)
            for key, value in edge_bundle.delay_model_parameters.items()
        },
    }


def _build_sign_summary(edge_bundle: Any) -> dict[str, Any]:
    return {
        "sign_representation": str(edge_bundle.sign_representation),
        "synapse_sign_counts": _count_values(edge_bundle.synapse_table["sign"]),
        "component_sign_counts": _count_values(edge_bundle.component_table["sign_label"]) if not edge_bundle.component_table.empty else {},
        "signed_weight_total": _safe_float(edge_bundle.component_table["signed_weight_total"].sum() if not edge_bundle.component_table.empty else 0.0),
        "absolute_weight_total": _safe_float(edge_bundle.component_table["absolute_weight_total"].sum() if not edge_bundle.component_table.empty else 0.0),
    }


def _build_qa_flags(checks: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups = [
        (
            "Presynaptic mapping",
            (
                "pre_mapped_fraction",
                "pre_quality_warn_fraction",
                "pre_fallback_fraction",
            ),
        ),
        (
            "Postsynaptic mapping",
            (
                "post_mapped_fraction",
                "post_quality_warn_fraction",
                "post_fallback_fraction",
            ),
        ),
        (
            "Artifact consistency",
            (
                "registry_row_mismatch_count",
                "outgoing_anchor_row_mismatch_count",
                "incoming_anchor_row_mismatch_count",
                "outgoing_anchor_field_mismatch_count",
                "incoming_anchor_field_mismatch_count",
                "component_membership_gap",
            ),
        ),
        (
            "Cloud normalization",
            (
                "source_cloud_unit_sum_residual_max",
                "target_cloud_unit_sum_residual_max",
            ),
        ),
        (
            "Weight conservation",
            (
                "signed_weight_residual_abs_max",
                "absolute_weight_residual_abs_max",
            ),
        ),
        (
            "Delay integrity",
            (
                "negative_delay_count",
                "nan_delay_count",
            ),
        ),
    ]
    flags: list[dict[str, Any]] = []
    for name, metric_names in groups:
        relevant_checks = [
            {"metric": metric_name, **dict(checks[metric_name])}
            for metric_name in metric_names
            if metric_name in checks
        ]
        if not relevant_checks:
            continue
        flags.append(
            {
                "name": name,
                "status": _worst_status(check["status"] for check in relevant_checks),
                "metrics": relevant_checks,
            }
        )
    return flags


def _load_root_visual_context(
    *,
    root_id: int,
    side_prefix: str,
    synapse_table: pd.DataFrame,
    meshes_raw_dir: str | Path,
    skeletons_raw_dir: str | Path,
    processed_mesh_dir: str | Path,
    processed_graph_dir: str | Path,
) -> tuple[RootVisualContext, dict[str, Any], list[dict[str, str]]]:
    bundle_paths = build_geometry_bundle_paths(
        root_id,
        meshes_raw_dir=meshes_raw_dir,
        skeletons_raw_dir=skeletons_raw_dir,
        processed_mesh_dir=processed_mesh_dir,
        processed_graph_dir=processed_graph_dir,
    )
    descriptor_payload = _load_json_if_exists(bundle_paths.descriptor_sidecar_path)
    registry_metadata = dict(descriptor_payload.get("registry_metadata", {})) if descriptor_payload else {}
    anchor_types = {
        str(value)
        for value in synapse_table[f"{side_prefix}_anchor_type"].tolist()
        if str(value).strip() and str(value) != "nan"
    }

    patch_points = np.empty((0, 3), dtype=np.float64)
    patch_edges = np.empty((0, 2), dtype=np.int32)
    surface_points = np.empty((0, 3), dtype=np.float64)
    surface_edges = np.empty((0, 2), dtype=np.int32)
    skeleton_points = np.empty((0, 3), dtype=np.float64)
    skeleton_edges = np.empty((0, 2), dtype=np.int32)
    missing_prerequisites: list[dict[str, str]] = []

    if ANCHOR_TYPE_SURFACE_PATCH in anchor_types:
        if bundle_paths.patch_graph_path.exists():
            patch_payload = _load_npz_payload(bundle_paths.patch_graph_path)
            patch_points = np.asarray(
                patch_payload.get("patch_centroids", np.empty((0, 3), dtype=np.float64)),
                dtype=np.float64,
            )
            patch_edges = _csr_edges(deserialize_sparse_matrix(patch_payload, prefix="adj"))
        else:
            missing_prerequisites.append(
                _missing_prerequisite(
                    asset_key=f"{side_prefix}_patch_graph",
                    path=str(bundle_paths.patch_graph_path.resolve()),
                    reason=f"missing_{side_prefix}_patch_graph_for_surface_anchor",
                )
            )
        if bundle_paths.surface_graph_path.exists():
            surface_payload = _load_npz_payload(bundle_paths.surface_graph_path)
            surface_points = np.asarray(
                surface_payload.get("vertices", np.empty((0, 3), dtype=np.float64)),
                dtype=np.float64,
            )
            surface_edges = _csr_edges(deserialize_sparse_matrix(surface_payload, prefix="adj"))

    if ANCHOR_TYPE_SKELETON_NODE in anchor_types:
        if bundle_paths.raw_skeleton_path.exists():
            skeleton_geometry = _load_skeleton_geometry(bundle_paths.raw_skeleton_path)
            skeleton_points = skeleton_geometry["points"]
            skeleton_edges = skeleton_geometry["edges"]
        else:
            missing_prerequisites.append(
                _missing_prerequisite(
                    asset_key=f"{side_prefix}_skeleton",
                    path=str(bundle_paths.raw_skeleton_path.resolve()),
                    reason=f"missing_{side_prefix}_skeleton_for_skeleton_anchor",
                )
            )

    context = RootVisualContext(
        root_id=int(root_id),
        project_role=str(registry_metadata.get("project_role", "unknown")),
        cell_type=str(registry_metadata.get("cell_type", "n/a")),
        patch_points=patch_points,
        patch_edges=patch_edges,
        surface_points=surface_points,
        surface_edges=surface_edges,
        skeleton_points=skeleton_points,
        skeleton_edges=skeleton_edges,
    )
    context_summary = {
        "root_id": int(root_id),
        "project_role": context.project_role,
        "cell_type": context.cell_type,
        "patch_count": int(context.patch_points.shape[0]),
        "surface_vertex_count": int(context.surface_points.shape[0]),
        "skeleton_node_count": int(context.skeleton_points.shape[0]),
        "used_anchor_types": sorted(anchor_types),
    }
    return context, context_summary, missing_prerequisites


def _write_edge_artifacts(
    *,
    edge_label: str,
    output_dir: Path,
    source_context: RootVisualContext,
    target_context: RootVisualContext,
    edge_bundle: Any,
) -> dict[str, str]:
    source_svg_path = output_dir / f"{edge_label}_source_readout.svg"
    target_svg_path = output_dir / f"{edge_label}_target_landing.svg"
    source_svg_path.write_text(
        _render_root_panel(
            context=source_context,
            synapse_table=edge_bundle.synapse_table,
            anchor_table=edge_bundle.source_anchor_table,
            cloud_table=edge_bundle.source_cloud_table,
            component_table=edge_bundle.component_table,
            side_prefix="pre",
            title=f"Presynaptic Readout {edge_label.replace('__to__', ' -> ')}",
        ),
        encoding="utf-8",
    )
    target_svg_path.write_text(
        _render_root_panel(
            context=target_context,
            synapse_table=edge_bundle.synapse_table,
            anchor_table=edge_bundle.target_anchor_table,
            cloud_table=edge_bundle.target_cloud_table,
            component_table=edge_bundle.component_table,
            side_prefix="post",
            title=f"Postsynaptic Landing {edge_label.replace('__to__', ' -> ')}",
        ),
        encoding="utf-8",
    )
    return {
        "source_svg_path": str(source_svg_path.resolve()),
        "target_svg_path": str(target_svg_path.resolve()),
    }


def _render_root_panel(
    *,
    context: RootVisualContext,
    synapse_table: pd.DataFrame,
    anchor_table: pd.DataFrame,
    cloud_table: pd.DataFrame,
    component_table: pd.DataFrame,
    side_prefix: str,
    title: str,
) -> str:
    query_points = synapse_table.loc[
        :,
        [f"{side_prefix}_query_x", f"{side_prefix}_query_y", f"{side_prefix}_query_z"],
    ].to_numpy(dtype=np.float64)
    anchor_points = anchor_table.loc[:, ["anchor_x", "anchor_y", "anchor_z"]].to_numpy(dtype=np.float64)
    mapped_lines = synapse_table.loc[
        :,
        [
            f"{side_prefix}_query_x",
            f"{side_prefix}_query_y",
            f"{side_prefix}_query_z",
            f"{side_prefix}_anchor_x",
            f"{side_prefix}_anchor_y",
            f"{side_prefix}_anchor_z",
            f"{side_prefix}_mapping_status",
        ],
    ].copy()
    anchor_emphasis = _aggregate_anchor_emphasis(
        anchor_table=anchor_table,
        cloud_table=cloud_table,
        component_table=component_table,
    )
    point_sets = [
        context.patch_points,
        context.surface_points,
        context.skeleton_points,
        _finite_rows(query_points),
        _finite_rows(anchor_points),
    ]
    if not any(points.size for points in point_sets):
        return _empty_svg(message=title)

    frame = _build_projection_frame(point_sets)
    elements: list[str] = []

    if context.surface_points.size and context.surface_edges.size:
        projected, _depth = _project_points(context.surface_points, frame)
        elements.append(
            _svg_edge_elements(
                projected,
                context.surface_edges,
                stroke="#e2e8f0",
                stroke_width=1.0,
                opacity=0.95,
            )
        )
    if context.patch_points.size and context.patch_edges.size:
        projected, _depth = _project_points(context.patch_points, frame)
        elements.append(
            _svg_edge_elements(
                projected,
                context.patch_edges,
                stroke="#cbd5e1",
                stroke_width=1.3,
                opacity=1.0,
            )
        )
    if context.skeleton_points.size and context.skeleton_edges.size:
        projected, _depth = _project_points(context.skeleton_points, frame)
        elements.append(
            _svg_edge_elements(
                projected,
                context.skeleton_edges,
                stroke="#94a3b8",
                stroke_width=1.6,
                opacity=0.98,
            )
        )

    elements.append(_svg_residual_lines(mapped_lines, frame=frame, side_prefix=side_prefix))
    elements.append(_svg_query_points(synapse_table, frame=frame, side_prefix=side_prefix))
    elements.append(_svg_anchor_points(anchor_emphasis, frame=frame))
    elements.append(
        f'<text x="{SVG_PADDING:.1f}" y="22" fill="#0f172a" font-size="14" '
        f'font-family="ui-monospace, SFMono-Regular, monospace">{html.escape(title)}</text>'
    )
    return _wrap_svg("".join(elements))


def _aggregate_anchor_emphasis(
    *,
    anchor_table: pd.DataFrame,
    cloud_table: pd.DataFrame,
    component_table: pd.DataFrame,
) -> pd.DataFrame:
    if anchor_table.empty:
        return anchor_table.copy()
    if cloud_table.empty or component_table.empty:
        out = anchor_table.copy()
        out["cloud_weight_total"] = 1.0
        out["signed_influence_total"] = 0.0
        out["supporting_synapse_count_total"] = 0
        return out

    joined = cloud_table.merge(
        component_table.loc[:, ["component_index", "signed_weight_total"]],
        on="component_index",
        how="left",
        validate="many_to_one",
    )
    joined["signed_influence"] = joined["cloud_weight"] * joined["signed_weight_total"]
    aggregated = (
        joined.groupby("anchor_table_index", sort=True, dropna=False)
        .agg(
            cloud_weight_total=("cloud_weight", "sum"),
            signed_influence_total=("signed_influence", "sum"),
            supporting_synapse_count_total=("supporting_synapse_count", "sum"),
        )
        .reset_index()
    )
    return anchor_table.merge(
        aggregated,
        on="anchor_table_index",
        how="left",
        validate="one_to_one",
    ).fillna(
        {
            "cloud_weight_total": 0.0,
            "signed_influence_total": 0.0,
            "supporting_synapse_count_total": 0,
        }
    )


def _svg_residual_lines(mapped_lines: pd.DataFrame, *, frame: ProjectionFrame, side_prefix: str) -> str:
    lines: list[str] = []
    for row in mapped_lines.itertuples(index=False):
        query = np.asarray(row[:3], dtype=np.float64)
        anchor = np.asarray(row[3:6], dtype=np.float64)
        if not (np.all(np.isfinite(query)) and np.all(np.isfinite(anchor))):
            continue
        query_projected, _ = _project_points(query.reshape(1, 3), frame)
        anchor_projected, _ = _project_points(anchor.reshape(1, 3), frame)
        status = str(row[6])
        stroke = {
            MAPPING_STATUS_BLOCKED: "#dc2626",
            "mapped_with_fallback": "#d97706",
        }.get(status, "#64748b")
        lines.append(
            f'<line x1="{query_projected[0, 0]:.3f}" y1="{query_projected[0, 1]:.3f}" '
            f'x2="{anchor_projected[0, 0]:.3f}" y2="{anchor_projected[0, 1]:.3f}" '
            f'stroke="{stroke}" stroke-width="0.85" opacity="0.70" />'
        )
    return "".join(lines)


def _svg_query_points(synapse_table: pd.DataFrame, *, frame: ProjectionFrame, side_prefix: str) -> str:
    if synapse_table.empty:
        return ""
    points = synapse_table.loc[
        :,
        [f"{side_prefix}_query_x", f"{side_prefix}_query_y", f"{side_prefix}_query_z"],
    ].to_numpy(dtype=np.float64)
    statuses = synapse_table[f"{side_prefix}_mapping_status"].astype(str).tolist()
    finite_mask = np.all(np.isfinite(points), axis=1)
    if not np.any(finite_mask):
        return ""
    filtered_points = points[finite_mask]
    projected, depth = _project_points(filtered_points, frame)
    filtered_statuses = [statuses[index] for index, keep in enumerate(finite_mask.tolist()) if keep]
    order = np.argsort(depth)
    circles: list[str] = []
    for local_index in order:
        status = filtered_statuses[int(local_index)]
        fill = {
            MAPPING_STATUS_BLOCKED: "#dc2626",
            "mapped_with_fallback": "#d97706",
        }.get(status, "#0f172a")
        point = projected[int(local_index)]
        circles.append(
            f'<circle cx="{point[0]:.3f}" cy="{point[1]:.3f}" r="3.1" fill="{fill}" '
            'stroke="#ffffff" stroke-width="0.65" opacity="0.95" />'
        )
    return "".join(circles)


def _svg_anchor_points(anchor_emphasis: pd.DataFrame, *, frame: ProjectionFrame) -> str:
    if anchor_emphasis.empty:
        return ""
    points = anchor_emphasis.loc[:, ["anchor_x", "anchor_y", "anchor_z"]].to_numpy(dtype=np.float64)
    finite_mask = np.all(np.isfinite(points), axis=1)
    if not np.any(finite_mask):
        return ""
    projected, depth = _project_points(points[finite_mask], frame)
    working = anchor_emphasis.loc[finite_mask].reset_index(drop=True)
    weight_values = working["cloud_weight_total"].to_numpy(dtype=np.float64)
    max_weight = float(np.max(weight_values)) if weight_values.size else 1.0
    order = np.argsort(depth)
    circles: list[str] = []
    for local_index in order:
        row = working.iloc[int(local_index)]
        normalized_weight = 0.0 if max_weight <= EPSILON else float(row["cloud_weight_total"]) / max_weight
        radius = 4.2 + 4.8 * math.sqrt(max(normalized_weight, 0.0))
        fill = _signed_color(float(row["signed_influence_total"]))
        stroke = _anchor_type_stroke(str(row.get("anchor_type", "")))
        point = projected[int(local_index)]
        circles.append(
            f'<circle cx="{point[0]:.3f}" cy="{point[1]:.3f}" r="{radius:.2f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.0" opacity="0.95" />'
        )
    return "".join(circles)


def _render_report_html(*, edge_entries: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    sections = "".join(_render_edge_html(entry) for entry in edge_entries)
    summary_grid = _render_summary_grid(
        [
            ("Status", summary["overall_status"]),
            ("Edges", str(summary["edge_count"])),
            ("Warnings", str(summary["warning_count"])),
            ("Failures", str(summary["failure_count"])),
            ("Blocked", str(summary["blocked_edge_count"])),
            ("Output", summary["output_dir"]),
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Offline Coupling Inspection Report</title>
  <style>
    body {{
      margin: 0;
      padding: 24px;
      font-family: ui-sans-serif, system-ui, sans-serif;
      background: #f8fafc;
      color: #0f172a;
    }}
    h1, h2, h3 {{
      margin: 0 0 10px 0;
    }}
    .lede {{
      margin: 6px 0 18px 0;
      color: #475569;
      max-width: 72rem;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 12px;
      margin: 0 0 18px 0;
    }}
    .summary-item, .edge-card {{
      background: #ffffff;
      border: 1px solid #dbe4f0;
      border-radius: 12px;
      padding: 14px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
    }}
    .edge-card {{
      margin-bottom: 18px;
    }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.03em;
      text-transform: uppercase;
    }}
    .badge-pass {{ background: #dcfce7; color: #166534; }}
    .badge-warn {{ background: #fef3c7; color: #92400e; }}
    .badge-fail, .badge-blocked {{ background: #fee2e2; color: #991b1b; }}
    .panel-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 14px;
      margin: 14px 0 0 0;
    }}
    figure {{
      margin: 0;
      background: #ffffff;
      border: 1px solid #dbe4f0;
      border-radius: 12px;
      padding: 10px;
    }}
    figcaption {{
      margin-top: 6px;
      font-size: 13px;
      color: #475569;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
      font-size: 13px;
    }}
    th, td {{
      padding: 7px 8px;
      border-top: 1px solid #e2e8f0;
      text-align: left;
      vertical-align: top;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, monospace;
      font-size: 12px;
      color: #0f172a;
    }}
    .muted {{
      color: #64748b;
    }}
    ul {{
      margin: 8px 0 0 18px;
    }}
  </style>
</head>
<body>
  <h1>Offline Coupling Inspection Report</h1>
  <p class="lede">This report reads only local coupling artifacts, anchor maps, and geometry bundles. It is meant for Milestone 7 edge review before simulator integration.</p>
  {summary_grid}
  {sections}
</body>
</html>
"""


def _render_edge_html(entry: Mapping[str, Any]) -> str:
    badge = _status_badge(str(entry["summary"]["overall_status"]))
    if entry["summary"]["overall_status"] == "blocked":
        missing_items = "".join(
            f"<li><code>{html.escape(item['asset_key'])}</code>: <code>{html.escape(item['path'])}</code></li>"
            for item in entry.get("missing_prerequisites", [])
        )
        return f"""
<section class="edge-card">
  <h2>Edge {html.escape(entry['edge_label'].replace('__to__', ' -> '))}</h2>
  {badge}
  <p class="lede">Required local artifacts were missing for this edge report.</p>
  <ul>{missing_items}</ul>
</section>
"""

    summary_grid = _render_summary_grid(
        [
            ("Status", str(entry["summary"]["overall_status"])),
            ("Synapses", str(entry["edge_bundle_summary"]["synapse_count"])),
            ("Usable", str(entry["edge_bundle_summary"]["usable_synapse_count"])),
            ("Blocked", str(entry["edge_bundle_summary"]["blocked_synapse_count"])),
            ("Components", str(entry["aggregation_summary"]["component_count"])),
            ("Delay model", str(entry["delay_summary"]["delay_model"])),
        ]
    )
    qa_rows = "".join(
        f"<tr><td>{html.escape(flag['name'])}</td><td>{_status_badge(flag['status'])}</td>"
        f"<td>{html.escape(_flag_reasons(flag))}</td></tr>"
        for flag in entry["qa_flags"]
    )
    blocked_rows = ""
    for item in entry.get("blocked_synapses", [])[:10]:
        blocked_rows += (
            f"<tr><td>{html.escape(str(item.get('synapse_id', '')))}</td>"
            f"<td>{html.escape(str(item.get('pre_blocked_reason') or item.get('post_blocked_reason') or 'n/a'))}</td></tr>"
        )
    blocked_table = (
        f"""
  <h3>Blocked Synapses</h3>
  <table>
    <thead><tr><th>Synapse</th><th>Reason</th></tr></thead>
    <tbody>{blocked_rows}</tbody>
  </table>
"""
        if blocked_rows
        else ""
    )
    component_rows = "".join(
        f"<tr><td>{int(item.get('component_index', 0))}</td>"
        f"<td>{html.escape(str(item.get('sign_label', '')))}</td>"
        f"<td>{html.escape(str(item.get('delay_bin_label', '')))}</td>"
        f"<td>{int(item.get('synapse_count', 0))}</td>"
        f"<td>{float(item.get('signed_weight_total', 0.0)):.3f}</td></tr>"
        for item in entry.get("component_table", [])[:8]
    )
    source_rows = _render_kv_rows(
        {
            "Mapped fraction": _format_ratio(entry["source_summary"]["mapped_fraction"]),
            "Mapping statuses": _format_counts(entry["source_summary"]["mapping_status_counts"]),
            "Quality statuses": _format_counts(entry["source_summary"]["quality_status_counts"]),
            "Anchor types": _format_counts(entry["source_summary"]["anchor_type_counts"]),
            "Fallback fraction": _format_ratio(entry["source_summary"]["fallback_fraction"]),
        }
    )
    target_rows = _render_kv_rows(
        {
            "Mapped fraction": _format_ratio(entry["target_summary"]["mapped_fraction"]),
            "Mapping statuses": _format_counts(entry["target_summary"]["mapping_status_counts"]),
            "Quality statuses": _format_counts(entry["target_summary"]["quality_status_counts"]),
            "Anchor types": _format_counts(entry["target_summary"]["anchor_type_counts"]),
            "Fallback fraction": _format_ratio(entry["target_summary"]["fallback_fraction"]),
        }
    )
    aggregate_rows = _render_kv_rows(
        {
            "Topology": entry["edge_bundle_summary"]["topology_family"],
            "Kernel": entry["edge_bundle_summary"]["kernel_family"],
            "Aggregation": entry["edge_bundle_summary"]["aggregation_rule"],
            "Neuropils": _format_counts(entry["edge_bundle_summary"]["neuropil_counts"]),
            "NT types": _format_counts(entry["edge_bundle_summary"]["nt_type_counts"]),
            "Delay span": _format_delay_span(entry["delay_summary"]),
            "Sign totals": _format_sign_summary(entry["sign_summary"]),
        }
    )
    return f"""
<section class="edge-card">
  <h2>Edge {html.escape(entry['edge_label'].replace('__to__', ' -> '))}</h2>
  {badge}
  {summary_grid}
  <h3>QA Flags</h3>
  <table>
    <thead><tr><th>Flag</th><th>Status</th><th>Notes</th></tr></thead>
    <tbody>{qa_rows}</tbody>
  </table>
  <div class="panel-grid">
    <figure>
      <img src="{html.escape(Path(entry['artifacts']['source_svg_path']).name)}" alt="Presynaptic readout" />
      <figcaption>Presynaptic readout geometry with query points, anchor residual lines, and aggregate cloud emphasis.</figcaption>
    </figure>
    <figure>
      <img src="{html.escape(Path(entry['artifacts']['target_svg_path']).name)}" alt="Postsynaptic landing" />
      <figcaption>Postsynaptic landing geometry with query points, anchor residual lines, and aggregate cloud emphasis.</figcaption>
    </figure>
  </div>
  <div class="panel-grid">
    <div class="summary-item">
      <h3>Presynaptic Summary</h3>
      <table><tbody>{source_rows}</tbody></table>
    </div>
    <div class="summary-item">
      <h3>Postsynaptic Summary</h3>
      <table><tbody>{target_rows}</tbody></table>
    </div>
    <div class="summary-item">
      <h3>Aggregation Summary</h3>
      <table><tbody>{aggregate_rows}</tbody></table>
    </div>
  </div>
  <h3>Components</h3>
  <table>
    <thead><tr><th>Index</th><th>Sign</th><th>Delay Bin</th><th>Synapses</th><th>Signed Weight</th></tr></thead>
    <tbody>{component_rows}</tbody>
  </table>
  {blocked_table}
  <p class="muted">Detail JSON: <code>{html.escape(entry['artifacts']['details_json_path'])}</code></p>
</section>
"""


def _render_report_markdown(*, edge_entries: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# Offline Coupling Inspection Report",
        "",
        "This report reads only local coupling artifacts, anchor maps, and geometry bundles.",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Edge count: `{summary['edge_count']}`",
        f"- Warning count: `{summary['warning_count']}`",
        f"- Failure count: `{summary['failure_count']}`",
        f"- Blocked edge count: `{summary['blocked_edge_count']}`",
        "",
    ]
    for entry in edge_entries:
        lines.extend(
            [
                f"## Edge `{entry['edge_label'].replace('__to__', ' -> ')}`",
                "",
                f"- Status: `{entry['summary']['overall_status']}`",
            ]
        )
        if entry["summary"]["overall_status"] == "blocked":
            lines.append(f"- Missing prerequisite count: `{entry['summary']['missing_prerequisite_count']}`")
            lines.append("")
            for item in entry.get("missing_prerequisites", []):
                lines.append(f"- Missing `{item['asset_key']}` at `{item['path']}`")
            lines.append("")
            continue
        lines.extend(
            [
                f"- Synapses: `{entry['edge_bundle_summary']['synapse_count']}`",
                f"- Usable synapses: `{entry['edge_bundle_summary']['usable_synapse_count']}`",
                f"- Blocked synapses: `{entry['edge_bundle_summary']['blocked_synapse_count']}`",
                f"- Components: `{entry['aggregation_summary']['component_count']}`",
                f"- Delay model: `{entry['delay_summary']['delay_model']}`",
                f"- Neuropils: `{_format_counts(entry['edge_bundle_summary']['neuropil_counts'])}`",
                "",
                "### QA Flags",
                "",
            ]
        )
        for flag in entry["qa_flags"]:
            lines.append(f"- `{flag['name']}`: `{flag['status']}` ({_flag_reasons(flag)})")
        lines.extend(
            [
                "",
                "### Visuals",
                "",
                f"![Presynaptic readout]({Path(entry['artifacts']['source_svg_path']).name})",
                "",
                f"![Postsynaptic landing]({Path(entry['artifacts']['target_svg_path']).name})",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_summary_grid(items: Sequence[tuple[str, str]]) -> str:
    return '<div class="summary-grid">' + "".join(
        f'<div class="summary-item"><strong>{html.escape(label)}</strong><br>'
        f'<span>{html.escape(value)}</span></div>'
        for label, value in items
    ) + "</div>"


def _render_kv_rows(mapping: Mapping[str, Any]) -> str:
    return "".join(
        f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>"
        for key, value in mapping.items()
    )


def _status_badge(status: str) -> str:
    return f'<span class="badge badge-{html.escape(status)}">{html.escape(status)}</span>'


def _flag_reasons(flag: Mapping[str, Any]) -> str:
    interesting = [
        metric
        for metric in flag.get("metrics", [])
        if metric["status"] != "pass"
    ]
    if not interesting:
        interesting = list(flag.get("metrics", []))[:1]
    parts = []
    for metric in interesting:
        parts.append(f"{metric['metric']}={_format_check_value(metric)}")
    return ", ".join(parts) if parts else "pass"


def _format_check_value(metric: Mapping[str, Any]) -> str:
    value = metric.get("value")
    if value is None:
        return "n/a"
    numeric_value = float(value)
    if numeric_value.is_integer():
        return str(int(numeric_value))
    return f"{numeric_value:.4g}"


def _format_counts(mapping: Mapping[str, int]) -> str:
    if not mapping:
        return "n/a"
    return ", ".join(f"{key}: {value}" for key, value in mapping.items())


def _format_ratio(value: float) -> str:
    return f"{float(value):.0%}"


def _format_delay_span(delay_summary: Mapping[str, Any]) -> str:
    if delay_summary.get("delay_min_ms") is None or delay_summary.get("delay_max_ms") is None:
        return "n/a"
    delay_min = delay_summary["delay_min_ms"]
    delay_max = delay_summary["delay_max_ms"]
    if delay_min is None or delay_max is None:
        return "n/a"
    return f"{delay_min:.3f}..{delay_max:.3f} ms"


def _format_sign_summary(sign_summary: Mapping[str, Any]) -> str:
    return (
        f"signed={float(sign_summary['signed_weight_total']):.3f}, "
        f"abs={float(sign_summary['absolute_weight_total']):.3f}"
    )


def _missing_prerequisite(*, asset_key: str, path: str, reason: str) -> dict[str, str]:
    return {
        "asset_key": str(asset_key),
        "path": str(Path(path).resolve()),
        "reason": str(reason),
    }


def _normalize_edge_specs(edge_specs: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    normalized = sorted({(int(pre_root_id), int(post_root_id)) for pre_root_id, post_root_id in edge_specs})
    if not normalized:
        raise ValueError("At least one edge spec is required for coupling inspection.")
    return normalized


def _edge_slug(pre_root_id: int, post_root_id: int) -> str:
    return f"{int(pre_root_id)}-to-{int(post_root_id)}"


def _edge_label(pre_root_id: int, post_root_id: int) -> str:
    return f"{int(pre_root_id)}__to__{int(post_root_id)}"


def _load_npz_payload(path: str | Path) -> dict[str, np.ndarray]:
    with np.load(Path(path), allow_pickle=False) as payload:
        return {key: payload[key] for key in payload.files}


def _load_json_if_exists(path: str | Path) -> dict[str, Any]:
    resolved = Path(path)
    if not resolved.exists():
        return {}
    return json.loads(resolved.read_text(encoding="utf-8"))


def _load_skeleton_geometry(path: str | Path) -> dict[str, np.ndarray]:
    rows: list[tuple[int, float, float, float, int]] = []
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 7:
            continue
        rows.append(
            (
                int(parts[0]),
                float(parts[2]),
                float(parts[3]),
                float(parts[4]),
                int(parts[6]),
            )
        )
    if not rows:
        return {
            "points": np.empty((0, 3), dtype=np.float64),
            "edges": np.empty((0, 2), dtype=np.int32),
        }
    node_ids = [row[0] for row in rows]
    index_by_node_id = {node_id: index for index, node_id in enumerate(node_ids)}
    points = np.asarray([[row[1], row[2], row[3]] for row in rows], dtype=np.float64)
    edges = [
        (index_by_node_id[row[0]], index_by_node_id[row[4]])
        for row in rows
        if row[4] in index_by_node_id
    ]
    return {
        "points": points,
        "edges": np.asarray(edges, dtype=np.int32) if edges else np.empty((0, 2), dtype=np.int32),
    }


def _row_mismatch_count(left: pd.DataFrame, right: pd.DataFrame) -> int:
    left_ids = {str(value) for value in left["synapse_row_id"].tolist()} if "synapse_row_id" in left else set()
    right_ids = {str(value) for value in right["synapse_row_id"].tolist()} if "synapse_row_id" in right else set()
    return len(left_ids.symmetric_difference(right_ids))


def _anchor_field_mismatch_count(edge_synapse_table: pd.DataFrame, anchor_map: pd.DataFrame, *, side_prefix: str) -> int:
    if edge_synapse_table.empty or anchor_map.empty:
        return 0
    left = edge_synapse_table.loc[
        :,
        [
            "synapse_row_id",
            f"{side_prefix}_query_source",
            f"{side_prefix}_mapping_status",
            f"{side_prefix}_quality_status",
            f"{side_prefix}_anchor_mode",
            f"{side_prefix}_anchor_type",
            f"{side_prefix}_anchor_index",
            f"{side_prefix}_anchor_x",
            f"{side_prefix}_anchor_y",
            f"{side_prefix}_anchor_z",
        ],
    ].copy()
    left = left.rename(
        columns={
            f"{side_prefix}_query_source": "query_source_edge",
            f"{side_prefix}_mapping_status": "mapping_status_edge",
            f"{side_prefix}_quality_status": "quality_status_edge",
            f"{side_prefix}_anchor_mode": "anchor_mode_edge",
            f"{side_prefix}_anchor_type": "anchor_type_edge",
            f"{side_prefix}_anchor_index": "anchor_index_edge",
            f"{side_prefix}_anchor_x": "anchor_x_edge",
            f"{side_prefix}_anchor_y": "anchor_y_edge",
            f"{side_prefix}_anchor_z": "anchor_z_edge",
        }
    )
    right = anchor_map.loc[
        :,
        [
            "synapse_row_id",
            "query_source",
            "mapping_status",
            "quality_status",
            "anchor_mode",
            "anchor_type",
            "anchor_index",
            "anchor_x",
            "anchor_y",
            "anchor_z",
        ],
    ].copy()
    right = right.rename(
        columns={
            "query_source": "query_source_map",
            "mapping_status": "mapping_status_map",
            "quality_status": "quality_status_map",
            "anchor_mode": "anchor_mode_map",
            "anchor_type": "anchor_type_map",
            "anchor_index": "anchor_index_map",
            "anchor_x": "anchor_x_map",
            "anchor_y": "anchor_y_map",
            "anchor_z": "anchor_z_map",
        }
    )
    joined = left.merge(right, on="synapse_row_id", how="inner")
    mismatched_synapse_ids: set[str] = set()
    field_pairs = (
        ("query_source_edge", "query_source_map"),
        ("mapping_status_edge", "mapping_status_map"),
        ("quality_status_edge", "quality_status_map"),
        ("anchor_mode_edge", "anchor_mode_map"),
        ("anchor_type_edge", "anchor_type_map"),
        ("anchor_index_edge", "anchor_index_map"),
        ("anchor_x_edge", "anchor_x_map"),
        ("anchor_y_edge", "anchor_y_map"),
        ("anchor_z_edge", "anchor_z_map"),
    )
    for left_name, right_name in field_pairs:
        mismatched_synapse_ids.update(
            joined.loc[
                ~joined.apply(
                    lambda row: _values_equal(row[left_name], row[right_name]),
                    axis=1,
                ),
                "synapse_row_id",
            ].astype(str).tolist()
        )
    return len(mismatched_synapse_ids)


def _values_equal(left: Any, right: Any) -> bool:
    if pd.isna(left) and pd.isna(right):
        return True
    if isinstance(left, (int, float, np.integer, np.floating)) or isinstance(
        right, (int, float, np.integer, np.floating)
    ):
        try:
            left_value = float(left)
            right_value = float(right)
        except (TypeError, ValueError):
            return str(left) == str(right)
        if not (math.isfinite(left_value) and math.isfinite(right_value)):
            return pd.isna(left) and pd.isna(right)
        return abs(left_value - right_value) <= 1.0e-9
    return str(left) == str(right)


def _cloud_unit_sum_residual_max(
    cloud_table: pd.DataFrame,
    component_table: pd.DataFrame,
    *,
    normalization: str,
) -> float:
    if normalization != SUM_TO_ONE_PER_COMPONENT_NORMALIZATION or component_table.empty:
        return 0.0
    if cloud_table.empty:
        return 1.0
    grouped = cloud_table.groupby("component_index", sort=True, dropna=False)["cloud_weight"].sum()
    residuals: list[float] = []
    for component_index in component_table["component_index"].tolist():
        residuals.append(abs(float(grouped.get(int(component_index), 0.0)) - 1.0))
    return max(residuals) if residuals else 0.0


def _component_weight_residual(
    *,
    component_table: pd.DataFrame,
    component_synapse_table: pd.DataFrame,
    membership_column: str,
    component_total_column: str,
) -> float:
    if component_table.empty:
        return 0.0
    grouped = (
        component_synapse_table.groupby("component_index", sort=True, dropna=False)[membership_column].sum()
        if not component_synapse_table.empty
        else pd.Series(dtype=float)
    )
    residuals: list[float] = []
    for row in component_table.itertuples(index=False):
        residuals.append(abs(float(grouped.get(int(row.component_index), 0.0)) - float(getattr(row, component_total_column))))
    return max(residuals) if residuals else 0.0


def _delay_count(series: pd.Series, *, mode: str) -> int:
    values = np.asarray(series.to_numpy(dtype=np.float64), dtype=np.float64)
    if mode == "negative":
        return int(np.count_nonzero(np.isfinite(values) & (values < -EPSILON)))
    return int(np.count_nonzero(~np.isfinite(values)))


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records = frame.to_dict(orient="records")
    return [_json_safe(record) for record in records]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    return value


def _count_values(series: pd.Series) -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw_value in series.tolist():
        if pd.isna(raw_value):
            continue
        value = str(raw_value).strip()
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _finite_rows(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3:
        return np.empty((0, 3), dtype=np.float64)
    mask = np.all(np.isfinite(points), axis=1)
    return points[mask]


def _safe_float(value: float) -> float | None:
    numeric_value = float(value)
    return None if not math.isfinite(numeric_value) else numeric_value


def _fraction(numerator: int, denominator: int) -> float:
    if int(denominator) <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def _worst_status(statuses: Iterable[str]) -> str:
    severity = {"pass": 0, "warn": 1, "fail": 2, "blocked": 3}
    normalized_statuses = [str(status) for status in statuses]
    if not normalized_statuses:
        return "pass"
    return max(normalized_statuses, key=lambda status: severity.get(status, 0))


def _build_projection_frame(point_sets: Iterable[np.ndarray]) -> ProjectionFrame:
    point_clouds = [np.asarray(points, dtype=np.float64) for points in point_sets if np.asarray(points).size > 0]
    if not point_clouds:
        raise ValueError("Projection frame requires at least one non-empty point set.")
    stacked = np.vstack(point_clouds)
    center = stacked.mean(axis=0)
    rotation = _rotation_matrix()
    rotated = (stacked - center[None, :]) @ rotation.T
    xy = rotated[:, :2]
    xy_min = xy.min(axis=0)
    xy_max = xy.max(axis=0)
    extent = np.maximum(xy_max - xy_min, 1.0)
    scale_x = max(float(SVG_WIDTH) - 2.0 * SVG_PADDING, 1.0) / float(extent[0])
    scale_y = max(float(SVG_HEIGHT) - 2.0 * SVG_PADDING, 1.0) / float(extent[1])
    return ProjectionFrame(
        rotation=rotation,
        center=center,
        xy_min=xy_min,
        xy_max=xy_max,
        scale=float(min(scale_x, scale_y)),
    )


def _rotation_matrix() -> np.ndarray:
    z_radians = math.radians(ROTATION_Z_DEGREES)
    x_radians = math.radians(ROTATION_X_DEGREES)
    rotate_z = np.asarray(
        [
            [math.cos(z_radians), -math.sin(z_radians), 0.0],
            [math.sin(z_radians), math.cos(z_radians), 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    rotate_x = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.0, math.cos(x_radians), -math.sin(x_radians)],
            [0.0, math.sin(x_radians), math.cos(x_radians)],
        ],
        dtype=np.float64,
    )
    return rotate_x @ rotate_z


def _project_points(points: np.ndarray, frame: ProjectionFrame) -> tuple[np.ndarray, np.ndarray]:
    rotated = (np.asarray(points, dtype=np.float64) - frame.center[None, :]) @ frame.rotation.T
    x = SVG_PADDING + (rotated[:, 0] - frame.xy_min[0]) * frame.scale
    y = SVG_HEIGHT - SVG_PADDING - (rotated[:, 1] - frame.xy_min[1]) * frame.scale
    return np.column_stack([x, y]), rotated[:, 2]


def _svg_edge_elements(
    projected: np.ndarray,
    edge_vertex_indices: np.ndarray,
    *,
    stroke: str,
    stroke_width: float,
    opacity: float,
) -> str:
    if edge_vertex_indices.size == 0:
        return ""
    lines: list[str] = []
    for i, j in np.asarray(edge_vertex_indices, dtype=np.int32):
        start = projected[int(i)]
        end = projected[int(j)]
        lines.append(
            f'<line x1="{start[0]:.3f}" y1="{start[1]:.3f}" x2="{end[0]:.3f}" y2="{end[1]:.3f}" '
            f'stroke="{stroke}" stroke-width="{stroke_width:.2f}" opacity="{opacity:.3f}" />'
        )
    return "".join(lines)


def _wrap_svg(body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" '
        f'viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}">'
        '<rect width="100%" height="100%" fill="#ffffff" />'
        f"{body}</svg>"
    )


def _empty_svg(*, message: str) -> str:
    return _wrap_svg(
        f'<text x="{SVG_WIDTH / 2:.1f}" y="{SVG_HEIGHT / 2:.1f}" text-anchor="middle" fill="#475569" '
        f'font-size="14" font-family="ui-monospace, SFMono-Regular, monospace">{html.escape(message)}</text>'
    )


def _csr_edges(matrix: sp.spmatrix) -> np.ndarray:
    csr = matrix.tocsr()
    rows: list[tuple[int, int]] = []
    for row_index in range(csr.shape[0]):
        start = int(csr.indptr[row_index])
        end = int(csr.indptr[row_index + 1])
        for col_index in csr.indices[start:end]:
            if row_index < int(col_index):
                rows.append((row_index, int(col_index)))
    if not rows:
        return np.empty((0, 2), dtype=np.int32)
    return np.asarray(rows, dtype=np.int32)


def _signed_color(value: float) -> str:
    if value > EPSILON:
        return "#0f766e"
    if value < -EPSILON:
        return "#b91c1c"
    return "#64748b"


def _anchor_type_stroke(anchor_type: str) -> str:
    return {
        ANCHOR_TYPE_SURFACE_PATCH: "#1d4ed8",
        ANCHOR_TYPE_SKELETON_NODE: "#7c3aed",
        ANCHOR_TYPE_POINT_STATE: "#0f172a",
    }.get(anchor_type, "#334155")
