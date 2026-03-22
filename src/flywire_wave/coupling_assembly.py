from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .coupling_contract import (
    ASSET_STATUS_READY,
    COLLAPSE_DELAY_WITH_WEIGHTED_MEAN_AGGREGATION,
    CONSTANT_ZERO_DELAY_MODEL,
    DEFAULT_AGGREGATION_RULE,
    DEFAULT_DELAY_REPRESENTATION,
    DEFAULT_MISSING_GEOMETRY_POLICY,
    DEFAULT_SIGN_REPRESENTATION,
    DISTRIBUTED_PATCH_CLOUD_TOPOLOGY,
    EUCLIDEAN_ANCHOR_DISTANCE_DELAY_MODEL,
    NO_CLOUD_NORMALIZATION,
    normalize_coupling_assembly_config,
)


EDGE_COUPLING_BUNDLE_VERSION = "edge_coupling_bundle.v1"

COMPONENT_COLUMN_TYPES: dict[str, str] = {
    "component_index": "int",
    "component_id": "string",
    "pre_root_id": "int",
    "post_root_id": "int",
    "topology_family": "string",
    "kernel_family": "string",
    "pre_anchor_mode": "string",
    "post_anchor_mode": "string",
    "sign_label": "string",
    "sign_polarity": "int",
    "sign_representation": "string",
    "delay_representation": "string",
    "delay_model": "string",
    "delay_ms": "float",
    "delay_bin_index": "int",
    "delay_bin_label": "string",
    "delay_bin_start_ms": "float",
    "delay_bin_end_ms": "float",
    "aggregation_rule": "string",
    "source_anchor_count": "int",
    "target_anchor_count": "int",
    "synapse_count": "int",
    "signed_weight_total": "float",
    "absolute_weight_total": "float",
    "confidence_sum": "float",
    "confidence_mean": "float",
    "source_cloud_normalization": "string",
    "target_cloud_normalization": "string",
    "source_normalization_total": "float",
    "target_normalization_total": "float",
}

ANCHOR_COLUMN_TYPES: dict[str, str] = {
    "anchor_table_index": "int",
    "root_id": "int",
    "anchor_mode": "string",
    "anchor_type": "string",
    "anchor_resolution": "string",
    "anchor_index": "int",
    "anchor_x": "float",
    "anchor_y": "float",
    "anchor_z": "float",
}

CLOUD_COLUMN_TYPES: dict[str, str] = {
    "component_index": "int",
    "anchor_table_index": "int",
    "cloud_weight": "float",
    "anchor_weight_total": "float",
    "supporting_synapse_count": "int",
}

COMPONENT_SYNAPSE_COLUMN_TYPES: dict[str, str] = {
    "component_index": "int",
    "synapse_row_id": "string",
    "source_row_number": "int",
    "synapse_id": "string",
    "sign_label": "string",
    "signed_weight": "float",
    "absolute_weight": "float",
    "delay_ms": "float",
    "delay_bin_index": "int",
    "delay_bin_label": "string",
}


@dataclass(frozen=True)
class EdgeCouplingBundle:
    pre_root_id: int
    post_root_id: int
    status: str
    topology_family: str
    kernel_family: str
    sign_representation: str
    delay_representation: str
    delay_model: str
    delay_model_parameters: dict[str, float]
    aggregation_rule: str
    missing_geometry_policy: str
    source_cloud_normalization: str
    target_cloud_normalization: str
    synapse_table: pd.DataFrame
    component_table: pd.DataFrame
    blocked_synapse_table: pd.DataFrame
    source_anchor_table: pd.DataFrame
    target_anchor_table: pd.DataFrame
    source_cloud_table: pd.DataFrame
    target_cloud_table: pd.DataFrame
    component_synapse_table: pd.DataFrame


def assemble_edge_coupling_bundle(
    edge_table: pd.DataFrame,
    *,
    coupling_assembly: Mapping[str, Any] | None = None,
) -> EdgeCouplingBundle:
    normalized_coupling_assembly = normalize_coupling_assembly_config(coupling_assembly)
    if edge_table.empty:
        raise ValueError("edge_table must contain at least one mapped synapse row.")

    normalized_edge_table = edge_table.sort_values(
        ["source_row_number", "synapse_row_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    pre_root_ids = sorted({int(value) for value in normalized_edge_table["pre_root_id"].tolist()})
    post_root_ids = sorted({int(value) for value in normalized_edge_table["post_root_id"].tolist()})
    if len(pre_root_ids) != 1 or len(post_root_ids) != 1:
        raise ValueError("Edge coupling bundles must be assembled from one biological edge at a time.")
    pre_root_id = pre_root_ids[0]
    post_root_id = post_root_ids[0]

    semantic_records: list[dict[str, Any]] = []
    for row in normalized_edge_table.itertuples(index=False):
        semantic_records.append(
            _resolve_synapse_semantics(
                row=row,
                normalized_coupling_assembly=normalized_coupling_assembly,
            )
        )
    semantic_table = pd.DataFrame.from_records(semantic_records)

    usable_mask = semantic_table["coupling_status"] == "usable"
    usable_semantics = semantic_table.loc[usable_mask].reset_index(drop=True)
    blocked_synapses = normalized_edge_table.loc[~usable_mask].reset_index(drop=True)

    component_table = pd.DataFrame(columns=list(COMPONENT_COLUMN_TYPES))
    source_anchor_table = pd.DataFrame(columns=list(ANCHOR_COLUMN_TYPES))
    target_anchor_table = pd.DataFrame(columns=list(ANCHOR_COLUMN_TYPES))
    source_cloud_table = pd.DataFrame(columns=list(CLOUD_COLUMN_TYPES))
    target_cloud_table = pd.DataFrame(columns=list(CLOUD_COLUMN_TYPES))
    component_synapse_table = pd.DataFrame(columns=list(COMPONENT_SYNAPSE_COLUMN_TYPES))

    if not usable_semantics.empty:
        component_rows: list[dict[str, Any]] = []
        source_cloud_rows: list[dict[str, Any]] = []
        target_cloud_rows: list[dict[str, Any]] = []
        component_synapse_rows: list[dict[str, Any]] = []
        source_anchor_rows: list[dict[str, Any]] = []
        target_anchor_rows: list[dict[str, Any]] = []
        source_anchor_index_by_key: dict[tuple[Any, ...], int] = {}
        target_anchor_index_by_key: dict[tuple[Any, ...], int] = {}

        group_columns = _grouping_columns(
            topology_family=str(normalized_coupling_assembly["topology_family"]),
            aggregation_rule=str(normalized_coupling_assembly["aggregation_rule"]),
        )
        grouped = usable_semantics.groupby(group_columns, sort=True, dropna=False)
        for component_index, (_group_key, group_df) in enumerate(grouped):
            ordered_group = group_df.sort_values(
                ["source_row_number", "synapse_row_id"],
                kind="mergesort",
            ).reset_index(drop=True)
            component_id = f"{pre_root_id}__to__{post_root_id}__component_{component_index:04d}"
            source_weights = _aggregate_anchor_weights(
                ordered_group,
                key_column="pre_anchor_key",
                weight_column="absolute_weight",
            )
            target_weights = _aggregate_anchor_weights(
                ordered_group,
                key_column="post_anchor_key",
                weight_column="absolute_weight",
            )
            normalized_source_weights = _normalize_cloud_weights(
                source_weights,
                normalization=str(normalized_coupling_assembly["source_cloud_normalization"]),
            )
            normalized_target_weights = _normalize_cloud_weights(
                target_weights,
                normalization=str(normalized_coupling_assembly["target_cloud_normalization"]),
            )

            for anchor_key in sorted(source_weights):
                if anchor_key not in source_anchor_index_by_key:
                    anchor_table_index = len(source_anchor_index_by_key)
                    source_anchor_index_by_key[anchor_key] = anchor_table_index
                    source_anchor_rows.append(_anchor_row(anchor_key, anchor_table_index=anchor_table_index))
                source_cloud_rows.append(
                    {
                        "component_index": component_index,
                        "anchor_table_index": source_anchor_index_by_key[anchor_key],
                        "cloud_weight": normalized_source_weights[anchor_key]["cloud_weight"],
                        "anchor_weight_total": source_weights[anchor_key]["anchor_weight_total"],
                        "supporting_synapse_count": source_weights[anchor_key]["supporting_synapse_count"],
                    }
                )
            for anchor_key in sorted(target_weights):
                if anchor_key not in target_anchor_index_by_key:
                    anchor_table_index = len(target_anchor_index_by_key)
                    target_anchor_index_by_key[anchor_key] = anchor_table_index
                    target_anchor_rows.append(_anchor_row(anchor_key, anchor_table_index=anchor_table_index))
                target_cloud_rows.append(
                    {
                        "component_index": component_index,
                        "anchor_table_index": target_anchor_index_by_key[anchor_key],
                        "cloud_weight": normalized_target_weights[anchor_key]["cloud_weight"],
                        "anchor_weight_total": target_weights[anchor_key]["anchor_weight_total"],
                        "supporting_synapse_count": target_weights[anchor_key]["supporting_synapse_count"],
                    }
                )

            delay_summary = _summarize_component_delay(
                ordered_group,
                aggregation_rule=str(normalized_coupling_assembly["aggregation_rule"]),
            )
            signed_weight_total = float(ordered_group["signed_weight"].sum())
            absolute_weight_total = float(ordered_group["absolute_weight"].sum())
            confidence_values = ordered_group["confidence_value"].to_numpy(dtype=np.float64)
            confidence_sum = float(np.nansum(confidence_values))
            finite_confidences = confidence_values[np.isfinite(confidence_values)]
            confidence_mean = float(np.mean(finite_confidences)) if finite_confidences.size else float("nan")

            component_rows.append(
                {
                    "component_index": component_index,
                    "component_id": component_id,
                    "pre_root_id": pre_root_id,
                    "post_root_id": post_root_id,
                    "topology_family": str(normalized_coupling_assembly["topology_family"]),
                    "kernel_family": str(normalized_coupling_assembly["kernel_family"]),
                    "pre_anchor_mode": str(ordered_group["pre_anchor_mode"].iloc[0]),
                    "post_anchor_mode": str(ordered_group["post_anchor_mode"].iloc[0]),
                    "sign_label": str(ordered_group["sign_label"].iloc[0]),
                    "sign_polarity": int(ordered_group["sign_polarity"].iloc[0]),
                    "sign_representation": str(normalized_coupling_assembly["sign_representation"]),
                    "delay_representation": DEFAULT_DELAY_REPRESENTATION,
                    "delay_model": str(normalized_coupling_assembly["delay_model"]["mode"]),
                    "delay_ms": delay_summary["delay_ms"],
                    "delay_bin_index": delay_summary["delay_bin_index"],
                    "delay_bin_label": delay_summary["delay_bin_label"],
                    "delay_bin_start_ms": delay_summary["delay_bin_start_ms"],
                    "delay_bin_end_ms": delay_summary["delay_bin_end_ms"],
                    "aggregation_rule": str(normalized_coupling_assembly["aggregation_rule"]),
                    "source_anchor_count": len(source_weights),
                    "target_anchor_count": len(target_weights),
                    "synapse_count": int(len(ordered_group)),
                    "signed_weight_total": signed_weight_total,
                    "absolute_weight_total": absolute_weight_total,
                    "confidence_sum": confidence_sum,
                    "confidence_mean": confidence_mean,
                    "source_cloud_normalization": str(normalized_coupling_assembly["source_cloud_normalization"]),
                    "target_cloud_normalization": str(normalized_coupling_assembly["target_cloud_normalization"]),
                    "source_normalization_total": float(
                        sum(item["anchor_weight_total"] for item in source_weights.values())
                    ),
                    "target_normalization_total": float(
                        sum(item["anchor_weight_total"] for item in target_weights.values())
                    ),
                }
            )
            for row in ordered_group.itertuples(index=False):
                component_synapse_rows.append(
                    {
                        "component_index": component_index,
                        "synapse_row_id": str(row.synapse_row_id),
                        "source_row_number": int(row.source_row_number),
                        "synapse_id": str(row.synapse_id),
                        "sign_label": str(row.sign_label),
                        "signed_weight": float(row.signed_weight),
                        "absolute_weight": float(row.absolute_weight),
                        "delay_ms": float(row.delay_ms),
                        "delay_bin_index": int(row.delay_bin_index),
                        "delay_bin_label": str(row.delay_bin_label),
                    }
                )

        component_table = pd.DataFrame.from_records(component_rows, columns=list(COMPONENT_COLUMN_TYPES))
        source_anchor_table = pd.DataFrame.from_records(source_anchor_rows, columns=list(ANCHOR_COLUMN_TYPES))
        target_anchor_table = pd.DataFrame.from_records(target_anchor_rows, columns=list(ANCHOR_COLUMN_TYPES))
        source_cloud_table = pd.DataFrame.from_records(source_cloud_rows, columns=list(CLOUD_COLUMN_TYPES))
        target_cloud_table = pd.DataFrame.from_records(target_cloud_rows, columns=list(CLOUD_COLUMN_TYPES))
        component_synapse_table = pd.DataFrame.from_records(
            component_synapse_rows,
            columns=list(COMPONENT_SYNAPSE_COLUMN_TYPES),
        )

    status = ASSET_STATUS_READY
    if not blocked_synapses.empty:
        status = "partial"
    elif _has_quality_warnings(normalized_edge_table):
        status = "partial"

    return EdgeCouplingBundle(
        pre_root_id=pre_root_id,
        post_root_id=post_root_id,
        status=status,
        topology_family=str(normalized_coupling_assembly["topology_family"]),
        kernel_family=str(normalized_coupling_assembly["kernel_family"]),
        sign_representation=str(normalized_coupling_assembly["sign_representation"]),
        delay_representation=DEFAULT_DELAY_REPRESENTATION,
        delay_model=str(normalized_coupling_assembly["delay_model"]["mode"]),
        delay_model_parameters={
            "base_delay_ms": float(normalized_coupling_assembly["delay_model"]["base_delay_ms"]),
            "velocity_distance_units_per_ms": float(
                normalized_coupling_assembly["delay_model"]["velocity_distance_units_per_ms"]
            ),
            "delay_bin_size_ms": float(normalized_coupling_assembly["delay_model"]["delay_bin_size_ms"]),
        },
        aggregation_rule=str(normalized_coupling_assembly["aggregation_rule"]),
        missing_geometry_policy=str(normalized_coupling_assembly["missing_geometry_policy"]),
        source_cloud_normalization=str(normalized_coupling_assembly["source_cloud_normalization"]),
        target_cloud_normalization=str(normalized_coupling_assembly["target_cloud_normalization"]),
        synapse_table=normalized_edge_table,
        component_table=component_table,
        blocked_synapse_table=blocked_synapses,
        source_anchor_table=source_anchor_table,
        target_anchor_table=target_anchor_table,
        source_cloud_table=source_cloud_table,
        target_cloud_table=target_cloud_table,
        component_synapse_table=component_synapse_table,
    )


def _resolve_synapse_semantics(
    *,
    row: Any,
    normalized_coupling_assembly: Mapping[str, Any],
) -> dict[str, Any]:
    if str(getattr(row, "pre_mapping_status", "")) == "blocked":
        return _blocked_semantic_record(row, blocked_reason=str(getattr(row, "pre_blocked_reason", "")))
    if str(getattr(row, "post_mapping_status", "")) == "blocked":
        return _blocked_semantic_record(row, blocked_reason=str(getattr(row, "post_blocked_reason", "")))

    sign_label, sign_polarity, signed_weight = _resolve_sign_semantics(
        row=row,
        sign_representation=str(normalized_coupling_assembly["sign_representation"]),
    )
    delay_ms = _resolve_delay_ms(
        row=row,
        delay_model=str(normalized_coupling_assembly["delay_model"]["mode"]),
        delay_model_parameters=normalized_coupling_assembly["delay_model"],
    )
    delay_bin_index, delay_bin_label, delay_bin_start_ms, delay_bin_end_ms = _resolve_delay_bin(
        delay_ms=delay_ms,
        aggregation_rule=str(normalized_coupling_assembly["aggregation_rule"]),
        delay_bin_size_ms=float(normalized_coupling_assembly["delay_model"]["delay_bin_size_ms"]),
    )

    return {
        "synapse_row_id": str(getattr(row, "synapse_row_id")),
        "source_row_number": int(getattr(row, "source_row_number")),
        "synapse_id": str(getattr(row, "synapse_id", "")),
        "coupling_status": "usable",
        "coupling_blocked_reason": "",
        "sign_label": sign_label,
        "sign_polarity": int(sign_polarity),
        "signed_weight": float(signed_weight),
        "absolute_weight": float(abs(signed_weight)),
        "confidence_value": _finite_or_nan(getattr(row, "confidence", float("nan"))),
        "delay_ms": float(delay_ms),
        "delay_bin_index": int(delay_bin_index),
        "delay_bin_label": delay_bin_label,
        "delay_bin_start_ms": float(delay_bin_start_ms),
        "delay_bin_end_ms": float(delay_bin_end_ms),
        "pre_anchor_mode": str(getattr(row, "pre_anchor_mode", "")),
        "post_anchor_mode": str(getattr(row, "post_anchor_mode", "")),
        "pre_anchor_key": _anchor_key(row, prefix="pre_", root_id=int(getattr(row, "pre_root_id"))),
        "post_anchor_key": _anchor_key(row, prefix="post_", root_id=int(getattr(row, "post_root_id"))),
    }


def _blocked_semantic_record(row: Any, *, blocked_reason: str) -> dict[str, Any]:
    return {
        "synapse_row_id": str(getattr(row, "synapse_row_id")),
        "source_row_number": int(getattr(row, "source_row_number")),
        "synapse_id": str(getattr(row, "synapse_id", "")),
        "coupling_status": "blocked",
        "coupling_blocked_reason": blocked_reason,
        "sign_label": "unknown",
        "sign_polarity": 0,
        "signed_weight": float("nan"),
        "absolute_weight": float("nan"),
        "confidence_value": _finite_or_nan(getattr(row, "confidence", float("nan"))),
        "delay_ms": float("nan"),
        "delay_bin_index": -1,
        "delay_bin_label": "",
        "delay_bin_start_ms": float("nan"),
        "delay_bin_end_ms": float("nan"),
        "pre_anchor_mode": str(getattr(row, "pre_anchor_mode", "")),
        "post_anchor_mode": str(getattr(row, "post_anchor_mode", "")),
        "pre_anchor_key": (),
        "post_anchor_key": (),
    }


def _resolve_sign_semantics(
    *,
    row: Any,
    sign_representation: str,
) -> tuple[str, int, float]:
    raw_sign = str(getattr(row, "sign", "") or "").strip().lower()
    weight = _finite_or_nan(getattr(row, "weight", float("nan")))
    if sign_representation == DEFAULT_SIGN_REPRESENTATION:
        label = _canonical_sign_label(raw_sign)
        if label == "unknown" and math.isfinite(weight):
            label = "excitatory" if weight > 0.0 else "inhibitory" if weight < 0.0 else "unknown"
        if math.isfinite(weight):
            signed_weight = weight
        elif label == "excitatory":
            signed_weight = 1.0
        elif label == "inhibitory":
            signed_weight = -1.0
        else:
            signed_weight = 0.0
        polarity = 1 if signed_weight > 0.0 else -1 if signed_weight < 0.0 else 0
        if label == "unknown" and polarity == 1:
            label = "excitatory"
        elif label == "unknown" and polarity == -1:
            label = "inhibitory"
        return label, polarity, signed_weight

    if math.isfinite(weight):
        polarity = 1 if weight > 0.0 else -1 if weight < 0.0 else 0
        label = "excitatory" if polarity > 0 else "inhibitory" if polarity < 0 else "unknown"
        return label, polarity, weight
    return "unknown", 0, 0.0


def _canonical_sign_label(raw_sign: str) -> str:
    if raw_sign in {"", "nan", "none", "unknown", "unk"}:
        return "unknown"
    if raw_sign in {"excitatory", "exc", "positive", "+"}:
        return "excitatory"
    if raw_sign in {"inhibitory", "inh", "negative", "-"}:
        return "inhibitory"
    if raw_sign in {"modulatory", "mod"}:
        return "modulatory"
    return raw_sign


def _resolve_delay_ms(
    *,
    row: Any,
    delay_model: str,
    delay_model_parameters: Mapping[str, Any],
) -> float:
    base_delay_ms = float(delay_model_parameters["base_delay_ms"])
    if delay_model == CONSTANT_ZERO_DELAY_MODEL:
        return base_delay_ms

    if delay_model == EUCLIDEAN_ANCHOR_DISTANCE_DELAY_MODEL:
        pre_anchor = np.asarray(
            [
                float(getattr(row, "pre_anchor_x")),
                float(getattr(row, "pre_anchor_y")),
                float(getattr(row, "pre_anchor_z")),
            ],
            dtype=np.float64,
        )
        post_anchor = np.asarray(
            [
                float(getattr(row, "post_anchor_x")),
                float(getattr(row, "post_anchor_y")),
                float(getattr(row, "post_anchor_z")),
            ],
            dtype=np.float64,
        )
        if not np.all(np.isfinite(pre_anchor)) or not np.all(np.isfinite(post_anchor)):
            raise ValueError("Distance-based delay model requires finite anchor coordinates.")
        velocity = float(delay_model_parameters["velocity_distance_units_per_ms"])
        return base_delay_ms + float(np.linalg.norm(pre_anchor - post_anchor)) / velocity

    raise ValueError(f"Unsupported delay model {delay_model!r}.")


def _resolve_delay_bin(
    *,
    delay_ms: float,
    aggregation_rule: str,
    delay_bin_size_ms: float,
) -> tuple[int, str, float, float]:
    if aggregation_rule == COLLAPSE_DELAY_WITH_WEIGHTED_MEAN_AGGREGATION:
        return 0, "weighted_mean_collapsed", float("nan"), float("nan")
    if delay_bin_size_ms > 0.0:
        delay_bin_index = int(math.floor((delay_ms + 1.0e-12) / delay_bin_size_ms))
        delay_bin_start_ms = float(delay_bin_index * delay_bin_size_ms)
        delay_bin_end_ms = float(delay_bin_start_ms + delay_bin_size_ms)
        delay_bin_label = f"{delay_bin_start_ms:.6f}-{delay_bin_end_ms:.6f}"
        return delay_bin_index, delay_bin_label, delay_bin_start_ms, delay_bin_end_ms
    return 0, f"{delay_ms:.9f}", float(delay_ms), float(delay_ms)


def _grouping_columns(*, topology_family: str, aggregation_rule: str) -> list[str]:
    columns = [
        "sign_label",
        "pre_anchor_mode",
        "post_anchor_mode",
    ]
    if aggregation_rule == DEFAULT_AGGREGATION_RULE:
        columns.extend(["delay_bin_index", "delay_bin_label"])
    if topology_family != DISTRIBUTED_PATCH_CLOUD_TOPOLOGY:
        columns.extend(["pre_anchor_key", "post_anchor_key"])
    return columns


def _aggregate_anchor_weights(
    group_df: pd.DataFrame,
    *,
    key_column: str,
    weight_column: str,
) -> dict[tuple[Any, ...], dict[str, Any]]:
    aggregated: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in group_df.itertuples(index=False):
        anchor_key = getattr(row, key_column)
        if not anchor_key:
            continue
        record = aggregated.setdefault(
            anchor_key,
            {"anchor_weight_total": 0.0, "supporting_synapse_count": 0},
        )
        record["anchor_weight_total"] += float(getattr(row, weight_column))
        record["supporting_synapse_count"] += 1
    return aggregated


def _normalize_cloud_weights(
    weights: Mapping[tuple[Any, ...], Mapping[str, Any]],
    *,
    normalization: str,
) -> dict[tuple[Any, ...], dict[str, float]]:
    totals = {
        anchor_key: float(record["anchor_weight_total"])
        for anchor_key, record in weights.items()
    }
    if not totals:
        return {}
    if normalization == NO_CLOUD_NORMALIZATION:
        return {
            anchor_key: {"cloud_weight": weight}
            for anchor_key, weight in totals.items()
        }
    total_weight = float(sum(totals.values()))
    if total_weight > 0.0:
        return {
            anchor_key: {"cloud_weight": weight / total_weight}
            for anchor_key, weight in totals.items()
        }
    uniform_weight = 1.0 / float(len(totals))
    return {
        anchor_key: {"cloud_weight": uniform_weight}
        for anchor_key in totals
    }


def _summarize_component_delay(
    group_df: pd.DataFrame,
    *,
    aggregation_rule: str,
) -> dict[str, Any]:
    if aggregation_rule == COLLAPSE_DELAY_WITH_WEIGHTED_MEAN_AGGREGATION:
        weights = group_df["absolute_weight"].to_numpy(dtype=np.float64)
        delays = group_df["delay_ms"].to_numpy(dtype=np.float64)
        finite_mask = np.isfinite(delays)
        if not finite_mask.any():
            return {
                "delay_ms": float("nan"),
                "delay_bin_index": 0,
                "delay_bin_label": "weighted_mean_collapsed",
                "delay_bin_start_ms": float("nan"),
                "delay_bin_end_ms": float("nan"),
            }
        finite_weights = weights[finite_mask]
        finite_delays = delays[finite_mask]
        total_weight = float(finite_weights.sum())
        if total_weight > 0.0:
            delay_ms = float(np.dot(finite_delays, finite_weights) / total_weight)
        else:
            delay_ms = float(np.mean(finite_delays))
        return {
            "delay_ms": delay_ms,
            "delay_bin_index": 0,
            "delay_bin_label": "weighted_mean_collapsed",
            "delay_bin_start_ms": float("nan"),
            "delay_bin_end_ms": float("nan"),
        }

    first_row = group_df.iloc[0]
    weights = group_df["absolute_weight"].to_numpy(dtype=np.float64)
    delays = group_df["delay_ms"].to_numpy(dtype=np.float64)
    total_weight = float(weights.sum())
    delay_ms = float(np.dot(delays, weights) / total_weight) if total_weight > 0.0 else float(np.mean(delays))
    return {
        "delay_ms": delay_ms,
        "delay_bin_index": int(first_row["delay_bin_index"]),
        "delay_bin_label": str(first_row["delay_bin_label"]),
        "delay_bin_start_ms": float(first_row["delay_bin_start_ms"]),
        "delay_bin_end_ms": float(first_row["delay_bin_end_ms"]),
    }


def _anchor_key(row: Any, *, prefix: str, root_id: int) -> tuple[Any, ...]:
    return (
        int(root_id),
        str(getattr(row, f"{prefix}anchor_mode")),
        str(getattr(row, f"{prefix}anchor_type")),
        str(getattr(row, f"{prefix}anchor_resolution")),
        int(getattr(row, f"{prefix}anchor_index")),
        float(getattr(row, f"{prefix}anchor_x")),
        float(getattr(row, f"{prefix}anchor_y")),
        float(getattr(row, f"{prefix}anchor_z")),
    )


def _anchor_row(anchor_key: tuple[Any, ...], *, anchor_table_index: int) -> dict[str, Any]:
    return {
        "anchor_table_index": int(anchor_table_index),
        "root_id": int(anchor_key[0]),
        "anchor_mode": str(anchor_key[1]),
        "anchor_type": str(anchor_key[2]),
        "anchor_resolution": str(anchor_key[3]),
        "anchor_index": int(anchor_key[4]),
        "anchor_x": float(anchor_key[5]),
        "anchor_y": float(anchor_key[6]),
        "anchor_z": float(anchor_key[7]),
    }


def _finite_or_nan(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number if math.isfinite(number) else float("nan")


def _has_quality_warnings(edge_table: pd.DataFrame) -> bool:
    if edge_table.empty:
        return False
    for column in ["pre_quality_status", "post_quality_status"]:
        if column in edge_table.columns and any(str(value) == "warn" for value in edge_table[column].tolist()):
            return True
    return False
