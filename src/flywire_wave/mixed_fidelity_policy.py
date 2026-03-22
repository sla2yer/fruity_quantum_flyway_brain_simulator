from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from .hybrid_morphology_contract import (
    HYBRID_MORPHOLOGY_PROMOTION_ORDER,
    normalize_hybrid_morphology_class,
)
from .stimulus_contract import (
    _normalize_float,
    _normalize_identifier,
    _normalize_nonempty_string,
)


MIXED_FIDELITY_POLICY_VERSION = "mixed_fidelity_policy.v1"
DEFAULT_MIXED_FIDELITY_DEFAULT_SOURCE = "registry_project_role"
RECOMMEND_FROM_POLICY_MODE = "recommend_from_policy"

SUPPORTED_MIXED_FIDELITY_DEFAULT_SOURCES = (
    DEFAULT_MIXED_FIDELITY_DEFAULT_SOURCE,
)
SUPPORTED_MIXED_FIDELITY_PROMOTION_MODES = (
    "disabled",
    RECOMMEND_FROM_POLICY_MODE,
)
SUPPORTED_MIXED_FIDELITY_DEMOTION_MODES = (
    "disabled",
    RECOMMEND_FROM_POLICY_MODE,
)
ALLOWED_MIXED_FIDELITY_POLICY_KEYS = {
    "policy_version",
    "default_source",
    "promotion_mode",
    "demotion_mode",
    "recommendation_rules",
}
ALLOWED_MIXED_FIDELITY_POLICY_RULE_KEYS = {
    "rule_id",
    "description",
    "minimum_morphology_class",
    "maximum_morphology_class",
    "root_ids",
    "cell_types",
    "topology_conditions",
    "morphology_conditions",
    "arm_tags_any",
    "descriptor_thresholds",
}
ALLOWED_DESCRIPTOR_THRESHOLD_KEYS = {
    "gte",
    "lte",
}


def normalize_mixed_fidelity_assignment_policy(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    unknown_keys = sorted(set(raw_payload) - ALLOWED_MIXED_FIDELITY_POLICY_KEYS)
    if unknown_keys:
        raise ValueError(
            "simulation.mixed_fidelity.assignment_policy contains unsupported "
            f"keys: {unknown_keys!r}."
        )

    policy_version = _normalize_nonempty_string(
        raw_payload.get("policy_version", MIXED_FIDELITY_POLICY_VERSION),
        field_name="simulation.mixed_fidelity.assignment_policy.policy_version",
    )
    if policy_version != MIXED_FIDELITY_POLICY_VERSION:
        raise ValueError(
            "simulation.mixed_fidelity.assignment_policy.policy_version must be "
            f"{MIXED_FIDELITY_POLICY_VERSION!r}."
        )

    default_source = _normalize_identifier(
        raw_payload.get(
            "default_source",
            DEFAULT_MIXED_FIDELITY_DEFAULT_SOURCE,
        ),
        field_name="simulation.mixed_fidelity.assignment_policy.default_source",
    )
    if default_source not in SUPPORTED_MIXED_FIDELITY_DEFAULT_SOURCES:
        raise ValueError(
            "simulation.mixed_fidelity.assignment_policy.default_source must be "
            f"one of {list(SUPPORTED_MIXED_FIDELITY_DEFAULT_SOURCES)!r}, got "
            f"{default_source!r}."
        )

    promotion_mode = _normalize_identifier(
        raw_payload.get("promotion_mode", "disabled"),
        field_name="simulation.mixed_fidelity.assignment_policy.promotion_mode",
    )
    if promotion_mode not in SUPPORTED_MIXED_FIDELITY_PROMOTION_MODES:
        raise ValueError(
            "simulation.mixed_fidelity.assignment_policy.promotion_mode must be "
            f"one of {list(SUPPORTED_MIXED_FIDELITY_PROMOTION_MODES)!r}, got "
            f"{promotion_mode!r}."
        )

    demotion_mode = _normalize_identifier(
        raw_payload.get("demotion_mode", "disabled"),
        field_name="simulation.mixed_fidelity.assignment_policy.demotion_mode",
    )
    if demotion_mode not in SUPPORTED_MIXED_FIDELITY_DEMOTION_MODES:
        raise ValueError(
            "simulation.mixed_fidelity.assignment_policy.demotion_mode must be "
            f"one of {list(SUPPORTED_MIXED_FIDELITY_DEMOTION_MODES)!r}, got "
            f"{demotion_mode!r}."
        )

    recommendation_rules_payload = raw_payload.get("recommendation_rules", ())
    if recommendation_rules_payload is None:
        recommendation_rules_payload = ()
    normalized_rules = [
        _normalize_policy_rule(
            item,
            field_name=(
                "simulation.mixed_fidelity.assignment_policy."
                f"recommendation_rules[{index}]"
            ),
        )
        for index, item in enumerate(
            _require_sequence(
                recommendation_rules_payload,
                field_name=(
                    "simulation.mixed_fidelity.assignment_policy.recommendation_rules"
                ),
            )
        )
    ]
    seen_rule_ids: set[str] = set()
    for rule in normalized_rules:
        rule_id = str(rule["rule_id"])
        if rule_id in seen_rule_ids:
            raise ValueError(
                "simulation.mixed_fidelity.assignment_policy.recommendation_rules "
                f"contains duplicate rule_id {rule_id!r}."
            )
        seen_rule_ids.add(rule_id)

    return {
        "policy_version": policy_version,
        "default_source": default_source,
        "promotion_mode": promotion_mode,
        "demotion_mode": demotion_mode,
        "recommendation_rules": normalized_rules,
    }


def extract_mixed_fidelity_descriptor_metrics(
    descriptor_payload: Mapping[str, Any] | None,
) -> dict[str, float]:
    if not isinstance(descriptor_payload, Mapping):
        return {}

    metrics: dict[str, float] = {}
    _maybe_add_numeric(metrics, "patch_count", descriptor_payload.get("patch_count"))
    _maybe_add_numeric(metrics, "surface_vertex_count", descriptor_payload.get("n_vertices"))
    _maybe_add_numeric(metrics, "surface_face_count", descriptor_payload.get("n_faces"))
    _maybe_add_numeric(
        metrics,
        "surface_graph_edge_count",
        descriptor_payload.get("surface_graph_edge_count"),
    )
    _maybe_add_numeric(
        metrics,
        "simplified_to_raw_face_ratio",
        _mapping_get(descriptor_payload, "derived_relations", "simplified_to_raw_face_ratio"),
    )
    _maybe_add_numeric(
        metrics,
        "simplified_to_raw_vertex_ratio",
        _mapping_get(descriptor_payload, "derived_relations", "simplified_to_raw_vertex_ratio"),
    )
    _maybe_add_numeric(
        metrics,
        "coarse_max_patch_vertex_fraction",
        _mapping_get(
            descriptor_payload,
            "representations",
            "coarse_patches",
            "max_patch_vertex_fraction",
        ),
    )
    _maybe_add_numeric(
        metrics,
        "coarse_singleton_patch_fraction",
        _mapping_get(
            descriptor_payload,
            "representations",
            "coarse_patches",
            "singleton_patch_fraction",
        ),
    )

    skeleton_summary = _mapping_get(descriptor_payload, "representations", "skeleton")
    if isinstance(skeleton_summary, Mapping):
        metrics["skeleton_available"] = 1.0 if bool(skeleton_summary.get("available")) else 0.0
        _maybe_add_numeric(metrics, "skeleton_node_count", skeleton_summary.get("node_count"))
        _maybe_add_numeric(
            metrics,
            "skeleton_segment_count",
            skeleton_summary.get("segment_count"),
        )
        _maybe_add_numeric(
            metrics,
            "skeleton_branch_point_count",
            skeleton_summary.get("branch_point_count"),
        )
        _maybe_add_numeric(metrics, "skeleton_leaf_count", skeleton_summary.get("leaf_count"))
        _maybe_add_numeric(
            metrics,
            "skeleton_total_cable_length",
            skeleton_summary.get("total_cable_length"),
        )

    return {
        metric_name: float(metric_value)
        for metric_name, metric_value in sorted(metrics.items())
    }


def evaluate_mixed_fidelity_policy(
    *,
    root_id: int,
    cell_type: str,
    realized_morphology_class: str,
    assignment_policy: Mapping[str, Any],
    descriptor_payload: Mapping[str, Any] | None,
    arm_id: str,
    topology_condition: str | None,
    morphology_condition: str | None,
    arm_tags: Sequence[str] | None,
) -> dict[str, Any]:
    normalized_policy = normalize_mixed_fidelity_assignment_policy(assignment_policy)
    descriptor_metrics = extract_mixed_fidelity_descriptor_metrics(descriptor_payload)
    normalized_cell_type = str(cell_type)
    normalized_topology_condition = _normalize_optional_identifier(
        topology_condition,
        field_name=f"mixed_fidelity_policy.root[{int(root_id)}].topology_condition",
    )
    normalized_morphology_condition = _normalize_optional_identifier(
        morphology_condition,
        field_name=f"mixed_fidelity_policy.root[{int(root_id)}].morphology_condition",
    )
    normalized_arm_tags = sorted(
        {
            _normalize_identifier(
                tag,
                field_name=f"mixed_fidelity_policy.root[{int(root_id)}].arm_tags",
            )
            for tag in (arm_tags or ())
        }
    )

    matched_rules: list[dict[str, Any]] = []
    minimum_rule_candidates: list[dict[str, Any]] = []
    maximum_rule_candidates: list[dict[str, Any]] = []
    for rule in normalized_policy["recommendation_rules"]:
        if not _policy_rule_matches(
            rule,
            root_id=int(root_id),
            cell_type=normalized_cell_type,
            topology_condition=normalized_topology_condition,
            morphology_condition=normalized_morphology_condition,
            arm_tags=normalized_arm_tags,
            descriptor_metrics=descriptor_metrics,
        ):
            continue
        matched_rule = {
            "rule_id": str(rule["rule_id"]),
            "description": rule["description"],
            "minimum_morphology_class": rule["minimum_morphology_class"],
            "maximum_morphology_class": rule["maximum_morphology_class"],
            "matched_descriptor_metrics": {
                metric_name: float(descriptor_metrics[metric_name])
                for metric_name in rule["descriptor_thresholds"]
                if metric_name in descriptor_metrics
            },
        }
        matched_rules.append(matched_rule)
        if rule["minimum_morphology_class"] is not None:
            minimum_rule_candidates.append(matched_rule)
        if rule["maximum_morphology_class"] is not None:
            maximum_rule_candidates.append(matched_rule)

    realized_rank = _morphology_class_rank(realized_morphology_class)
    minimum_rank_candidates = (
        [
            _morphology_class_rank(str(item["minimum_morphology_class"]))
            for item in minimum_rule_candidates
        ]
        if str(normalized_policy["promotion_mode"]) == RECOMMEND_FROM_POLICY_MODE
        else []
    )
    maximum_rank_candidates = (
        [
            _morphology_class_rank(str(item["maximum_morphology_class"]))
            for item in maximum_rule_candidates
        ]
        if str(normalized_policy["demotion_mode"]) == RECOMMEND_FROM_POLICY_MODE
        else []
    )
    if minimum_rank_candidates and maximum_rank_candidates:
        if max(minimum_rank_candidates) > min(maximum_rank_candidates):
            raise ValueError(
                "Mixed-fidelity policy rules conflict for root "
                f"{int(root_id)}: minimum recommendation "
                f"{_rank_to_morphology_class(max(minimum_rank_candidates))!r} exceeds "
                f"maximum recommendation "
                f"{_rank_to_morphology_class(min(maximum_rank_candidates))!r}."
            )

    recommended_rank = realized_rank
    if minimum_rank_candidates:
        recommended_rank = max(recommended_rank, max(minimum_rank_candidates))
    if maximum_rank_candidates:
        recommended_rank = min(recommended_rank, min(maximum_rank_candidates))
    recommended_morphology_class = _rank_to_morphology_class(recommended_rank)
    if recommended_rank == realized_rank:
        recommendation_relation = "same_as_realized"
    elif recommended_rank > realized_rank:
        recommendation_relation = "promote_from_realized"
    else:
        recommendation_relation = "demote_from_realized"

    return {
        "policy_version": MIXED_FIDELITY_POLICY_VERSION,
        "root_id": int(root_id),
        "arm_id": _normalize_identifier(
            arm_id,
            field_name=f"mixed_fidelity_policy.root[{int(root_id)}].arm_id",
        ),
        "realized_morphology_class": realized_morphology_class,
        "recommended_morphology_class": recommended_morphology_class,
        "recommended_relation_to_realized": recommendation_relation,
        "promotion_mode": str(normalized_policy["promotion_mode"]),
        "demotion_mode": str(normalized_policy["demotion_mode"]),
        "promotion_recommended": recommendation_relation == "promote_from_realized",
        "demotion_recommended": recommendation_relation == "demote_from_realized",
        "review_required": recommendation_relation != "same_as_realized",
        "matched_rule_ids": [str(item["rule_id"]) for item in matched_rules],
        "matched_rules": matched_rules,
        "descriptor_metrics": descriptor_metrics,
        "manifest_context": {
            "cell_type": normalized_cell_type,
            "topology_condition": normalized_topology_condition,
            "morphology_condition": normalized_morphology_condition,
            "arm_tags": normalized_arm_tags,
        },
    }


def build_mixed_fidelity_policy_hook_summary(
    *,
    assignment_policy: Mapping[str, Any],
    policy_evaluations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    normalized_policy = normalize_mixed_fidelity_assignment_policy(assignment_policy)
    normalized_evaluations = [
        _require_mapping(
            item,
            field_name="mixed_fidelity.policy_evaluations",
        )
        for item in policy_evaluations
    ]
    promotion_root_ids = sorted(
        int(item["root_id"])
        for item in normalized_evaluations
        if bool(item.get("promotion_recommended"))
    )
    demotion_root_ids = sorted(
        int(item["root_id"])
        for item in normalized_evaluations
        if bool(item.get("demotion_recommended"))
    )
    review_root_ids = sorted(
        int(item["root_id"])
        for item in normalized_evaluations
        if bool(item.get("review_required"))
    )
    preserve_root_ids = sorted(
        int(item["root_id"])
        for item in normalized_evaluations
        if str(item.get("recommended_relation_to_realized")) == "same_as_realized"
    )
    return {
        "policy_version": MIXED_FIDELITY_POLICY_VERSION,
        "default_source": str(normalized_policy["default_source"]),
        "promotion_mode": str(normalized_policy["promotion_mode"]),
        "demotion_mode": str(normalized_policy["demotion_mode"]),
        "recommendation_rule_count": len(normalized_policy["recommendation_rules"]),
        "recommendation_rule_ids": [
            str(item["rule_id"]) for item in normalized_policy["recommendation_rules"]
        ],
        "evaluated_root_count": len(normalized_evaluations),
        "promotion_recommendation_root_ids": promotion_root_ids,
        "demotion_recommendation_root_ids": demotion_root_ids,
        "review_root_ids": review_root_ids,
        "preserve_root_ids": preserve_root_ids,
    }


def _normalize_policy_rule(
    payload: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    rule = _require_mapping(payload, field_name=field_name)
    unknown_keys = sorted(set(rule) - ALLOWED_MIXED_FIDELITY_POLICY_RULE_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name} contains unsupported keys: {unknown_keys!r}.")

    rule_id = _normalize_identifier(
        rule.get("rule_id"),
        field_name=f"{field_name}.rule_id",
    )
    minimum_morphology_class = None
    if rule.get("minimum_morphology_class") is not None:
        minimum_morphology_class = normalize_hybrid_morphology_class(
            rule["minimum_morphology_class"],
            field_name=f"{field_name}.minimum_morphology_class",
        )
    maximum_morphology_class = None
    if rule.get("maximum_morphology_class") is not None:
        maximum_morphology_class = normalize_hybrid_morphology_class(
            rule["maximum_morphology_class"],
            field_name=f"{field_name}.maximum_morphology_class",
        )
    if minimum_morphology_class is None and maximum_morphology_class is None:
        raise ValueError(
            f"{field_name} must define minimum_morphology_class or maximum_morphology_class."
        )
    description = (
        None
        if rule.get("description") is None
        else _normalize_nonempty_string(
            rule["description"],
            field_name=f"{field_name}.description",
        )
    )
    root_ids = sorted(
        {
            int(root_id)
            for root_id in _optional_sequence(
                rule.get("root_ids"),
                field_name=f"{field_name}.root_ids",
            )
        }
    )
    cell_types = sorted(
        {
            _normalize_nonempty_string(
                cell_type,
                field_name=f"{field_name}.cell_types",
            )
            for cell_type in _optional_sequence(
                rule.get("cell_types"),
                field_name=f"{field_name}.cell_types",
            )
        }
    )
    topology_conditions = sorted(
        {
            _normalize_identifier(
                topology_condition,
                field_name=f"{field_name}.topology_conditions",
            )
            for topology_condition in _optional_sequence(
                rule.get("topology_conditions"),
                field_name=f"{field_name}.topology_conditions",
            )
        }
    )
    morphology_conditions = sorted(
        {
            _normalize_identifier(
                morphology_condition,
                field_name=f"{field_name}.morphology_conditions",
            )
            for morphology_condition in _optional_sequence(
                rule.get("morphology_conditions"),
                field_name=f"{field_name}.morphology_conditions",
            )
        }
    )
    arm_tags_any = sorted(
        {
            _normalize_identifier(
                tag,
                field_name=f"{field_name}.arm_tags_any",
            )
            for tag in _optional_sequence(
                rule.get("arm_tags_any"),
                field_name=f"{field_name}.arm_tags_any",
            )
        }
    )
    descriptor_thresholds_payload = rule.get("descriptor_thresholds")
    descriptor_thresholds: dict[str, dict[str, float | None]] = {}
    if descriptor_thresholds_payload is not None:
        descriptor_thresholds_mapping = _require_mapping(
            descriptor_thresholds_payload,
            field_name=f"{field_name}.descriptor_thresholds",
        )
        for metric_name, threshold_payload in sorted(descriptor_thresholds_mapping.items()):
            normalized_metric_name = _normalize_identifier(
                metric_name,
                field_name=f"{field_name}.descriptor_thresholds.metric_name",
            )
            threshold_mapping = _require_mapping(
                threshold_payload,
                field_name=(
                    f"{field_name}.descriptor_thresholds.{normalized_metric_name}"
                ),
            )
            unknown_threshold_keys = sorted(
                set(threshold_mapping) - ALLOWED_DESCRIPTOR_THRESHOLD_KEYS
            )
            if unknown_threshold_keys:
                raise ValueError(
                    f"{field_name}.descriptor_thresholds.{normalized_metric_name} "
                    f"contains unsupported keys: {unknown_threshold_keys!r}."
                )
            gte = threshold_mapping.get("gte")
            lte = threshold_mapping.get("lte")
            if gte is None and lte is None:
                raise ValueError(
                    f"{field_name}.descriptor_thresholds.{normalized_metric_name} "
                    "must define gte or lte."
                )
            normalized_gte = (
                None
                if gte is None
                else _normalize_float(
                    gte,
                    field_name=(
                        f"{field_name}.descriptor_thresholds."
                        f"{normalized_metric_name}.gte"
                    ),
                )
            )
            normalized_lte = (
                None
                if lte is None
                else _normalize_float(
                    lte,
                    field_name=(
                        f"{field_name}.descriptor_thresholds."
                        f"{normalized_metric_name}.lte"
                    ),
                )
            )
            if (
                normalized_gte is not None
                and normalized_lte is not None
                and normalized_gte > normalized_lte
            ):
                raise ValueError(
                    f"{field_name}.descriptor_thresholds.{normalized_metric_name} "
                    "requires gte <= lte."
                )
            descriptor_thresholds[normalized_metric_name] = {
                "gte": normalized_gte,
                "lte": normalized_lte,
            }

    return {
        "rule_id": rule_id,
        "description": description,
        "minimum_morphology_class": minimum_morphology_class,
        "maximum_morphology_class": maximum_morphology_class,
        "root_ids": root_ids,
        "cell_types": cell_types,
        "topology_conditions": topology_conditions,
        "morphology_conditions": morphology_conditions,
        "arm_tags_any": arm_tags_any,
        "descriptor_thresholds": descriptor_thresholds,
    }


def _policy_rule_matches(
    rule: Mapping[str, Any],
    *,
    root_id: int,
    cell_type: str,
    topology_condition: str | None,
    morphology_condition: str | None,
    arm_tags: Sequence[str],
    descriptor_metrics: Mapping[str, float],
) -> bool:
    if rule["root_ids"] and int(root_id) not in set(rule["root_ids"]):
        return False
    if rule["cell_types"] and str(cell_type) not in set(rule["cell_types"]):
        return False
    if rule["topology_conditions"] and str(topology_condition) not in set(
        rule["topology_conditions"]
    ):
        return False
    if rule["morphology_conditions"] and str(morphology_condition) not in set(
        rule["morphology_conditions"]
    ):
        return False
    if rule["arm_tags_any"] and not (set(arm_tags) & set(rule["arm_tags_any"])):
        return False
    for metric_name, bounds in rule["descriptor_thresholds"].items():
        if metric_name not in descriptor_metrics:
            return False
        metric_value = float(descriptor_metrics[metric_name])
        if bounds["gte"] is not None and metric_value < float(bounds["gte"]):
            return False
        if bounds["lte"] is not None and metric_value > float(bounds["lte"]):
            return False
    return True


def _mapping_get(payload: Any, *keys: str) -> Any:
    current = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _maybe_add_numeric(target: dict[str, float], key: str, value: Any) -> None:
    if value is None:
        return
    try:
        target[str(key)] = float(value)
    except (TypeError, ValueError):
        return


def _normalize_optional_identifier(
    value: Any,
    *,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    return _normalize_identifier(value, field_name=field_name)


def _optional_sequence(
    value: Any,
    *,
    field_name: str,
) -> Sequence[Any]:
    if value is None:
        return ()
    return _require_sequence(value, field_name=field_name)


def _morphology_class_rank(morphology_class: str) -> int:
    normalized = normalize_hybrid_morphology_class(
        morphology_class,
        field_name="mixed_fidelity_policy.morphology_class",
    )
    return HYBRID_MORPHOLOGY_PROMOTION_ORDER.index(normalized)


def _rank_to_morphology_class(rank: int) -> str:
    normalized_rank = int(rank)
    if normalized_rank < 0 or normalized_rank >= len(HYBRID_MORPHOLOGY_PROMOTION_ORDER):
        raise ValueError(f"Invalid mixed-fidelity morphology rank {normalized_rank!r}.")
    return str(HYBRID_MORPHOLOGY_PROMOTION_ORDER[normalized_rank])


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value


def _require_sequence(value: Any, *, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field_name} must be a list.")
    return value
