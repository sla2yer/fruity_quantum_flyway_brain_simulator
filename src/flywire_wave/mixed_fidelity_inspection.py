from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from .config import load_config
from .hybrid_morphology_contract import (
    HYBRID_MORPHOLOGY_PROMOTION_ORDER,
    normalize_hybrid_morphology_class,
)
from .io_utils import ensure_dir, write_csv_rows, write_json
from .manifests import load_yaml
from .simulation_planning import resolve_manifest_mixed_fidelity_plan
from .simulator_execution import execute_manifest_simulation
from .simulator_result_contract import (
    load_simulator_result_bundle_metadata,
    load_simulator_root_state_payload,
    load_simulator_shared_readout_payload,
)
from .stimulus_contract import (
    _normalize_float,
    _normalize_identifier,
    _normalize_nonempty_string,
)


MIXED_FIDELITY_INSPECTION_REPORT_VERSION = "mixed_fidelity_inspection.v1"
DEFAULT_MIXED_FIDELITY_INSPECTION_DIR = Path("data/processed/mixed_fidelity_inspection")

STATUS_PASS = "pass"
STATUS_REVIEW = "review"
STATUS_BLOCKING = "blocking"
STATUS_BLOCKED = "blocked"
STATUS_PRIORITY = {
    STATUS_PASS: 0,
    STATUS_REVIEW: 1,
    STATUS_BLOCKING: 2,
    STATUS_BLOCKED: 3,
}

DEFAULT_MIXED_FIDELITY_INSPECTION_THRESHOLDS: dict[str, dict[str, Any]] = {
    "root_mean_trace_mae": {
        "warn": 0.10,
        "fail": 0.30,
        "comparison": "max",
        "blocking": False,
        "description": "The mean root-local activation trace should stay close to the higher-fidelity reference.",
    },
    "root_peak_abs_error": {
        "warn": 0.15,
        "fail": 0.45,
        "comparison": "max",
        "blocking": False,
        "description": "Root-local peak amplitude should stay close to the higher-fidelity reference.",
    },
    "root_final_abs_error": {
        "warn": 0.10,
        "fail": 0.30,
        "comparison": "max",
        "blocking": False,
        "description": "Final root-local activation should not drift materially from the higher-fidelity reference.",
    },
    "root_peak_time_delta_ms": {
        "warn": 1.0,
        "fail": 3.0,
        "comparison": "max",
        "blocking": False,
        "description": "Peak timing should remain aligned closely enough for later readout comparisons.",
    },
    "shared_output_trace_mae": {
        "warn": 0.05,
        "fail": 0.15,
        "comparison": "max",
        "blocking": True,
        "description": "Shared circuit output should stay close to the reference before downstream validation depends on it.",
    },
    "shared_output_peak_abs_error": {
        "warn": 0.10,
        "fail": 0.25,
        "comparison": "max",
        "blocking": True,
        "description": "Shared output peak should not diverge materially from the reference run.",
    },
}

ROOT_SUMMARY_FIELDNAMES = (
    "root_id",
    "cell_type",
    "realized_morphology_class",
    "reference_morphology_class",
    "reference_source",
    "overall_status",
    "review_deviation_count",
    "blocking_deviation_count",
    "recommended_promotion",
    "root_mean_trace_mae",
    "root_peak_abs_error",
    "root_final_abs_error",
    "root_peak_time_delta_ms",
    "shared_output_trace_mae",
    "shared_output_peak_abs_error",
    "detail_path",
)

REFERENCE_ROOT_SPEC_PATTERN = re.compile(r"^\s*(\d+)\s*[:=]\s*([A-Za-z0-9_-]+)\s*$")
_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def parse_mixed_fidelity_reference_root_spec(value: str) -> dict[str, Any]:
    match = REFERENCE_ROOT_SPEC_PATTERN.match(str(value))
    if match is None:
        raise ValueError(
            "Invalid mixed-fidelity reference root spec "
            f"{value!r}. Use '<root_id>:<reference_morphology_class>'."
        )
    return {
        "root_id": int(match.group(1)),
        "reference_morphology_class": normalize_hybrid_morphology_class(
            match.group(2),
            field_name="mixed_fidelity_inspection.reference_morphology_class",
        ),
    }


def resolve_mixed_fidelity_inspection_thresholds(
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    thresholds = copy.deepcopy(DEFAULT_MIXED_FIDELITY_INSPECTION_THRESHOLDS)
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


def evaluate_mixed_fidelity_inspection_metrics(
    *,
    metrics: Mapping[str, float],
    thresholds: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    resolved_thresholds = resolve_mixed_fidelity_inspection_thresholds(thresholds)
    checks: dict[str, dict[str, Any]] = {}
    review_deviation_count = 0
    blocking_deviation_count = 0
    for metric_name, metric_value in sorted(metrics.items()):
        threshold = copy.deepcopy(dict(resolved_thresholds.get(metric_name, {})))
        warn_threshold = threshold.get("warn")
        fail_threshold = threshold.get("fail")
        comparison = str(threshold.get("comparison", "max"))
        blocking = bool(threshold.get("blocking", False))
        status = STATUS_PASS
        if fail_threshold is not None and _threshold_crossed(
            comparison=comparison,
            value=float(metric_value),
            threshold=float(fail_threshold),
        ):
            if blocking:
                status = STATUS_BLOCKING
                blocking_deviation_count += 1
            else:
                status = STATUS_REVIEW
                review_deviation_count += 1
        elif warn_threshold is not None and _threshold_crossed(
            comparison=comparison,
            value=float(metric_value),
            threshold=float(warn_threshold),
        ):
            status = STATUS_REVIEW
            review_deviation_count += 1
        checks[metric_name] = {
            "metric_name": metric_name,
            "value": float(metric_value),
            "warn_threshold": warn_threshold,
            "fail_threshold": fail_threshold,
            "comparison": comparison,
            "blocking": blocking,
            "description": threshold.get("description"),
            "status": status,
        }
    overall_status = STATUS_PASS
    if blocking_deviation_count > 0:
        overall_status = STATUS_BLOCKING
    elif review_deviation_count > 0:
        overall_status = STATUS_REVIEW
    return checks, {
        "overall_status": overall_status,
        "review_deviation_count": review_deviation_count,
        "blocking_deviation_count": blocking_deviation_count,
    }


def build_mixed_fidelity_inspection_output_dir(
    *,
    mixed_fidelity_inspection_dir: str | Path,
    experiment_id: str,
    arm_id: str,
    reference_roots: Sequence[Mapping[str, Any]],
    thresholds: Mapping[str, Mapping[str, Any]] | None = None,
) -> Path:
    normalized_reference_roots = _normalize_reference_roots(reference_roots)
    normalized_thresholds = resolve_mixed_fidelity_inspection_thresholds(thresholds)
    payload_hash = hashlib.sha256(
        json.dumps(
            {
                "version": MIXED_FIDELITY_INSPECTION_REPORT_VERSION,
                "arm_id": _normalize_identifier(arm_id, field_name="arm_id"),
                "reference_roots": normalized_reference_roots,
                "thresholds": normalized_thresholds,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()[:12]
    experiment_slug = _slug(_normalize_identifier(experiment_id, field_name="experiment_id"))
    arm_slug = _slug(_normalize_identifier(arm_id, field_name="arm_id"))
    return (
        Path(mixed_fidelity_inspection_dir).resolve()
        / f"experiment-{experiment_slug}__arm-{arm_slug}__inspection-{payload_hash}"
    )


def execute_mixed_fidelity_inspection_workflow(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    arm_id: str,
    reference_root_specs: Sequence[str | Mapping[str, Any]] | None = None,
    thresholds: Mapping[str, Mapping[str, Any]] | None = None,
    output_dir: str | Path | None = None,
    simulation_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    mixed_fidelity_plan = resolve_manifest_mixed_fidelity_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        arm_id=arm_id,
        simulation_plan=simulation_plan,
    )
    manifest_payload = load_yaml(manifest_path)
    experiment_id = str(manifest_payload["experiment_id"])
    resolved_references = _resolve_reference_roots(
        mixed_fidelity_plan=mixed_fidelity_plan,
        reference_root_specs=reference_root_specs,
    )
    resolved_output_dir = (
        Path(output_dir).resolve()
        if output_dir is not None
        else build_mixed_fidelity_inspection_output_dir(
            mixed_fidelity_inspection_dir=load_config(config_path)["paths"][
                "mixed_fidelity_inspection_dir"
            ],
            experiment_id=experiment_id,
            arm_id=arm_id,
            reference_roots=resolved_references,
            thresholds=thresholds,
        )
    )
    ensure_dir(resolved_output_dir)
    details_dir = ensure_dir(resolved_output_dir / "details")
    variants_dir = ensure_dir(resolved_output_dir / "_reference_manifests")

    base_execution_summary = execute_manifest_simulation(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        model_mode="surface_wave",
        arm_id=arm_id,
        simulation_plan=simulation_plan,
    )
    if int(base_execution_summary["executed_run_count"]) != 1:
        raise ValueError(
            f"Mixed-fidelity inspection expected one executed base run for arm {arm_id!r}."
        )
    base_run_summary = dict(base_execution_summary["executed_runs"][0])
    base_metadata = load_simulator_result_bundle_metadata(base_run_summary["metadata_path"])

    per_root_assignments = [
        {
            "root_id": int(item["root_id"]),
            "cell_type": str(item["cell_type"]),
            "registry_default_morphology_class": str(
                item["registry_default_morphology_class"]
            ),
            "realized_morphology_class": str(item["realized_morphology_class"]),
            "approximation_route": copy.deepcopy(dict(item["approximation_route"])),
            "assignment_provenance": copy.deepcopy(dict(item["assignment_provenance"])),
            "policy_evaluation": copy.deepcopy(dict(item["policy_evaluation"])),
        }
        for item in mixed_fidelity_plan["per_root_assignments"]
    ]
    per_root_assignment_by_root = {
        int(item["root_id"]): item for item in per_root_assignments
    }

    root_summaries: list[dict[str, Any]] = []
    for reference_root in resolved_references:
        root_id = int(reference_root["root_id"])
        assignment = per_root_assignment_by_root[root_id]
        detail_path = (
            details_dir
            / (
                f"root_{root_id}__"
                f"{assignment['realized_morphology_class']}__to__"
                f"{reference_root['reference_morphology_class']}.json"
            )
        ).resolve()
        try:
            variant_manifest_path = _write_reference_manifest_variant(
                manifest_path=manifest_path,
                output_dir=variants_dir,
                arm_id=arm_id,
                root_id=root_id,
                reference_morphology_class=str(
                    reference_root["reference_morphology_class"]
                ),
            )
            reference_execution_summary = execute_manifest_simulation(
                manifest_path=variant_manifest_path,
                config_path=config_path,
                schema_path=schema_path,
                design_lock_path=design_lock_path,
                model_mode="surface_wave",
                arm_id=arm_id,
            )
            if int(reference_execution_summary["executed_run_count"]) != 1:
                raise ValueError(
                    "Mixed-fidelity reference inspection expected one executed reference run."
                )
            reference_run_summary = dict(reference_execution_summary["executed_runs"][0])
            reference_metadata = load_simulator_result_bundle_metadata(
                reference_run_summary["metadata_path"]
            )
            detail = _build_root_comparison_detail(
                root_id=root_id,
                assignment=assignment,
                reference_root=reference_root,
                base_metadata=base_metadata,
                base_run_summary=base_run_summary,
                reference_metadata=reference_metadata,
                reference_run_summary=reference_run_summary,
                variant_manifest_path=variant_manifest_path,
                thresholds=thresholds,
            )
        except Exception as exc:
            detail = _build_blocked_root_comparison_detail(
                root_id=root_id,
                assignment=assignment,
                reference_root=reference_root,
                detail_path=detail_path,
                error=exc,
            )
        write_json(detail, detail_path)
        detail["detail_path"] = str(detail_path)
        root_summaries.append(detail)

    root_summaries.sort(key=lambda item: int(item["root_id"]))
    status_counts = {
        STATUS_PASS: sum(1 for item in root_summaries if item["overall_status"] == STATUS_PASS),
        STATUS_REVIEW: sum(
            1 for item in root_summaries if item["overall_status"] == STATUS_REVIEW
        ),
        STATUS_BLOCKING: sum(
            1 for item in root_summaries if item["overall_status"] == STATUS_BLOCKING
        ),
        STATUS_BLOCKED: sum(
            1 for item in root_summaries if item["overall_status"] == STATUS_BLOCKED
        ),
    }
    overall_status = _worst_status(item["overall_status"] for item in root_summaries)
    roots_csv_path = write_csv_rows(
        fieldnames=ROOT_SUMMARY_FIELDNAMES,
        rows=[_flatten_root_summary(item) for item in root_summaries],
        out_path=resolved_output_dir / "roots.csv",
    ).resolve()
    summary_path = (resolved_output_dir / "summary.json").resolve()
    report_path = (resolved_output_dir / "report.md").resolve()
    summary = {
        "report_version": MIXED_FIDELITY_INSPECTION_REPORT_VERSION,
        "overall_status": overall_status,
        "status_counts": status_counts,
        "manifest_path": str(Path(manifest_path).resolve()),
        "config_path": str(Path(config_path).resolve()),
        "schema_path": str(Path(schema_path).resolve()),
        "design_lock_path": str(Path(design_lock_path).resolve()),
        "experiment_id": experiment_id,
        "arm_id": _normalize_identifier(arm_id, field_name="arm_id"),
        "output_dir": str(resolved_output_dir),
        "report_path": str(report_path),
        "summary_path": str(summary_path),
        "roots_csv_path": str(roots_csv_path),
        "base_run_summary": base_run_summary,
        "mixed_fidelity_plan": {
            "plan_version": str(mixed_fidelity_plan["plan_version"]),
            "assignment_policy": copy.deepcopy(
                dict(mixed_fidelity_plan["assignment_policy"])
            ),
            "policy_hook": copy.deepcopy(dict(mixed_fidelity_plan["policy_hook"])),
            "arm_overrides": copy.deepcopy(dict(mixed_fidelity_plan["arm_overrides"])),
            "resolved_class_counts": copy.deepcopy(
                dict(mixed_fidelity_plan["resolved_class_counts"])
            ),
            "per_root_assignments": per_root_assignments,
        },
        "reference_roots": _normalize_reference_roots(resolved_references),
        "thresholds": resolve_mixed_fidelity_inspection_thresholds(thresholds),
        "root_summaries": root_summaries,
        "acceptable_root_ids": sorted(
            int(item["root_id"])
            for item in root_summaries
            if item["overall_status"] == STATUS_PASS
        ),
        "review_root_ids": sorted(
            int(item["root_id"])
            for item in root_summaries
            if item["overall_status"] == STATUS_REVIEW
        ),
        "blocking_root_ids": sorted(
            int(item["root_id"])
            for item in root_summaries
            if item["overall_status"] == STATUS_BLOCKING
        ),
        "blocked_root_ids": sorted(
            int(item["root_id"])
            for item in root_summaries
            if item["overall_status"] == STATUS_BLOCKED
        ),
        "recommended_promotion_root_ids": sorted(
            int(item["root_id"])
            for item in root_summaries
            if bool(item.get("recommended_promotion"))
        ),
    }
    report_path.write_text(_render_mixed_fidelity_markdown(summary), encoding="utf-8")
    write_json(summary, summary_path)
    return summary


def _resolve_reference_roots(
    *,
    mixed_fidelity_plan: Mapping[str, Any],
    reference_root_specs: Sequence[str | Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    assignment_by_root = {
        int(item["root_id"]): item
        for item in mixed_fidelity_plan["per_root_assignments"]
    }
    resolved: dict[int, dict[str, Any]] = {}
    if reference_root_specs:
        for spec in reference_root_specs:
            normalized = _normalize_reference_root(spec)
            root_id = int(normalized["root_id"])
            if root_id not in assignment_by_root:
                raise ValueError(
                    f"Mixed-fidelity inspection requested unknown root_id {root_id!r}."
                )
            _validate_reference_root_higher_fidelity(
                assignment=assignment_by_root[root_id],
                reference_morphology_class=str(
                    normalized["reference_morphology_class"]
                ),
            )
            resolved[root_id] = {
                "root_id": root_id,
                "reference_morphology_class": str(
                    normalized["reference_morphology_class"]
                ),
                "reference_source": "explicit_reference_root",
            }
    if not resolved:
        for assignment in mixed_fidelity_plan["per_root_assignments"]:
            policy_evaluation = dict(assignment.get("policy_evaluation", {}))
            reference_class = policy_evaluation.get("recommended_morphology_class")
            if reference_class is None:
                continue
            if _morphology_class_rank(str(reference_class)) <= _morphology_class_rank(
                str(assignment["realized_morphology_class"])
            ):
                continue
            root_id = int(assignment["root_id"])
            resolved[root_id] = {
                "root_id": root_id,
                "reference_morphology_class": str(reference_class),
                "reference_source": "policy_recommendation",
            }
    if not resolved:
        for assignment in mixed_fidelity_plan["per_root_assignments"]:
            realized_class = str(assignment["realized_morphology_class"])
            next_reference_class = _next_higher_morphology_class(realized_class)
            if next_reference_class is None:
                continue
            root_id = int(assignment["root_id"])
            resolved[root_id] = {
                "root_id": root_id,
                "reference_morphology_class": next_reference_class,
                "reference_source": "default_next_higher_class",
            }
    return _normalize_reference_roots(resolved.values())


def _build_root_comparison_detail(
    *,
    root_id: int,
    assignment: Mapping[str, Any],
    reference_root: Mapping[str, Any],
    base_metadata: Mapping[str, Any],
    base_run_summary: Mapping[str, Any],
    reference_metadata: Mapping[str, Any],
    reference_run_summary: Mapping[str, Any],
    variant_manifest_path: Path,
    thresholds: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, Any]:
    base_root_payload = load_simulator_root_state_payload(base_metadata, root_id=root_id)
    reference_root_payload = load_simulator_root_state_payload(
        reference_metadata,
        root_id=root_id,
    )
    base_shared_payload = load_simulator_shared_readout_payload(base_metadata)
    reference_shared_payload = load_simulator_shared_readout_payload(reference_metadata)

    root_time_ms, surrogate_root_trace, reference_root_trace = _align_scalar_traces(
        time_ms_a=np.asarray(base_root_payload["projection_time_ms"], dtype=np.float64),
        values_a=_mean_projection_trace(base_root_payload["projection_trace"]),
        time_ms_b=np.asarray(reference_root_payload["projection_time_ms"], dtype=np.float64),
        values_b=_mean_projection_trace(reference_root_payload["projection_trace"]),
    )
    shared_time_ms, surrogate_shared_trace, reference_shared_trace = _align_scalar_traces(
        time_ms_a=np.asarray(base_shared_payload["time_ms"], dtype=np.float64),
        values_a=_select_shared_trace(base_shared_payload),
        time_ms_b=np.asarray(reference_shared_payload["time_ms"], dtype=np.float64),
        values_b=_select_shared_trace(reference_shared_payload),
    )

    metrics = {
        "root_mean_trace_mae": float(
            np.mean(np.abs(surrogate_root_trace - reference_root_trace))
        ),
        "root_peak_abs_error": float(
            abs(
                np.max(np.abs(surrogate_root_trace))
                - np.max(np.abs(reference_root_trace))
            )
        ),
        "root_final_abs_error": float(
            abs(surrogate_root_trace[-1] - reference_root_trace[-1])
        ),
        "root_peak_time_delta_ms": float(
            abs(
                root_time_ms[int(np.argmax(np.abs(surrogate_root_trace)))]
                - root_time_ms[int(np.argmax(np.abs(reference_root_trace)))]
            )
        ),
        "shared_output_trace_mae": float(
            np.mean(np.abs(surrogate_shared_trace - reference_shared_trace))
        ),
        "shared_output_peak_abs_error": float(
            abs(
                np.max(np.abs(surrogate_shared_trace))
                - np.max(np.abs(reference_shared_trace))
            )
        ),
    }
    checks, evaluation = evaluate_mixed_fidelity_inspection_metrics(
        metrics=metrics,
        thresholds=thresholds,
    )
    recommended_promotion = bool(
        evaluation["overall_status"] in {STATUS_REVIEW, STATUS_BLOCKING}
        and _morphology_class_rank(str(reference_root["reference_morphology_class"]))
        > _morphology_class_rank(str(assignment["realized_morphology_class"]))
    )
    return {
        "root_id": int(root_id),
        "cell_type": str(assignment["cell_type"]),
        "realized_morphology_class": str(assignment["realized_morphology_class"]),
        "reference_morphology_class": str(reference_root["reference_morphology_class"]),
        "reference_source": str(reference_root["reference_source"]),
        "overall_status": str(evaluation["overall_status"]),
        "review_deviation_count": int(evaluation["review_deviation_count"]),
        "blocking_deviation_count": int(evaluation["blocking_deviation_count"]),
        "recommended_promotion": recommended_promotion,
        "metrics": metrics,
        "checks": checks,
        "assignment_provenance": copy.deepcopy(dict(assignment["assignment_provenance"])),
        "approximation_route": copy.deepcopy(dict(assignment["approximation_route"])),
        "policy_evaluation": copy.deepcopy(dict(assignment["policy_evaluation"])),
        "base_run": {
            "metadata_path": str(base_run_summary["metadata_path"]),
            "bundle_id": str(base_metadata["bundle_id"]),
            "run_spec_hash": str(base_metadata["run_spec_hash"]),
        },
        "reference_run": {
            "metadata_path": str(reference_run_summary["metadata_path"]),
            "bundle_id": str(reference_metadata["bundle_id"]),
            "run_spec_hash": str(reference_metadata["run_spec_hash"]),
            "variant_manifest_path": str(variant_manifest_path.resolve()),
        },
        "comparison_trace_summary": {
            "root_time_sample_count": int(root_time_ms.shape[0]),
            "shared_time_sample_count": int(shared_time_ms.shape[0]),
            "root_time_start_ms": float(root_time_ms[0]),
            "root_time_end_ms": float(root_time_ms[-1]),
            "shared_time_start_ms": float(shared_time_ms[0]),
            "shared_time_end_ms": float(shared_time_ms[-1]),
        },
    }


def _build_blocked_root_comparison_detail(
    *,
    root_id: int,
    assignment: Mapping[str, Any],
    reference_root: Mapping[str, Any],
    detail_path: Path,
    error: Exception,
) -> dict[str, Any]:
    return {
        "root_id": int(root_id),
        "cell_type": str(assignment["cell_type"]),
        "realized_morphology_class": str(assignment["realized_morphology_class"]),
        "reference_morphology_class": str(reference_root["reference_morphology_class"]),
        "reference_source": str(reference_root["reference_source"]),
        "overall_status": STATUS_BLOCKED,
        "review_deviation_count": 0,
        "blocking_deviation_count": 0,
        "recommended_promotion": False,
        "metrics": {},
        "checks": {},
        "assignment_provenance": copy.deepcopy(dict(assignment["assignment_provenance"])),
        "approximation_route": copy.deepcopy(dict(assignment["approximation_route"])),
        "policy_evaluation": copy.deepcopy(dict(assignment["policy_evaluation"])),
        "detail_path": str(detail_path),
        "error": {
            "type": type(error).__name__,
            "message": str(error),
        },
    }


def _flatten_root_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    metrics = dict(summary.get("metrics", {}))
    return {
        "root_id": int(summary["root_id"]),
        "cell_type": str(summary["cell_type"]),
        "realized_morphology_class": str(summary["realized_morphology_class"]),
        "reference_morphology_class": str(summary["reference_morphology_class"]),
        "reference_source": str(summary["reference_source"]),
        "overall_status": str(summary["overall_status"]),
        "review_deviation_count": int(summary.get("review_deviation_count", 0)),
        "blocking_deviation_count": int(summary.get("blocking_deviation_count", 0)),
        "recommended_promotion": bool(summary.get("recommended_promotion", False)),
        "root_mean_trace_mae": metrics.get("root_mean_trace_mae"),
        "root_peak_abs_error": metrics.get("root_peak_abs_error"),
        "root_final_abs_error": metrics.get("root_final_abs_error"),
        "root_peak_time_delta_ms": metrics.get("root_peak_time_delta_ms"),
        "shared_output_trace_mae": metrics.get("shared_output_trace_mae"),
        "shared_output_peak_abs_error": metrics.get("shared_output_peak_abs_error"),
        "detail_path": str(summary.get("detail_path", "")),
    }


def _normalize_reference_root(
    value: str | Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(value, str):
        normalized = parse_mixed_fidelity_reference_root_spec(value)
    else:
        mapping = _require_mapping(value, field_name="reference_root")
        if "root_id" not in mapping:
            raise ValueError("reference_root requires root_id.")
        if "reference_morphology_class" not in mapping:
            raise ValueError("reference_root requires reference_morphology_class.")
        normalized = {
            "root_id": int(mapping["root_id"]),
            "reference_morphology_class": normalize_hybrid_morphology_class(
                mapping["reference_morphology_class"],
                field_name="reference_root.reference_morphology_class",
            ),
        }
        if mapping.get("reference_source") is not None:
            normalized["reference_source"] = _normalize_identifier(
                mapping["reference_source"],
                field_name="reference_root.reference_source",
            )
    return normalized


def _normalize_reference_roots(
    payload: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    normalized: dict[int, dict[str, Any]] = {}
    for item in payload:
        normalized_item = _normalize_reference_root(item)
        normalized[int(normalized_item["root_id"])] = {
            "root_id": int(normalized_item["root_id"]),
            "reference_morphology_class": str(
                normalized_item["reference_morphology_class"]
            ),
            "reference_source": str(
                normalized_item.get("reference_source", "explicit_reference_root")
            ),
        }
    return [normalized[root_id] for root_id in sorted(normalized)]


def _validate_reference_root_higher_fidelity(
    *,
    assignment: Mapping[str, Any],
    reference_morphology_class: str,
) -> None:
    realized_class = str(assignment["realized_morphology_class"])
    if _morphology_class_rank(reference_morphology_class) <= _morphology_class_rank(
        realized_class
    ):
        raise ValueError(
            "Mixed-fidelity inspection requires a higher-fidelity reference class "
            f"for root {int(assignment['root_id'])}, got "
            f"{reference_morphology_class!r} for realized class {realized_class!r}."
        )


def _write_reference_manifest_variant(
    *,
    manifest_path: str | Path,
    output_dir: Path,
    arm_id: str,
    root_id: int,
    reference_morphology_class: str,
) -> Path:
    manifest_payload = load_yaml(manifest_path)
    arm_found = False
    normalized_arm_id = _normalize_identifier(arm_id, field_name="arm_id")
    for arm in manifest_payload["comparison_arms"]:
        if _normalize_identifier(arm["arm_id"], field_name="arm.arm_id") != normalized_arm_id:
            continue
        arm_found = True
        fidelity_assignment = dict(arm.get("fidelity_assignment") or {})
        root_overrides = fidelity_assignment.get("root_overrides") or []
        normalized_overrides = {
            int(item["root_id"]): {
                "root_id": int(item["root_id"]),
                "morphology_class": str(item["morphology_class"]),
            }
            for item in root_overrides
        }
        normalized_overrides[int(root_id)] = {
            "root_id": int(root_id),
            "morphology_class": str(reference_morphology_class),
        }
        fidelity_assignment["root_overrides"] = [
            normalized_overrides[current_root_id]
            for current_root_id in sorted(normalized_overrides)
        ]
        arm["fidelity_assignment"] = fidelity_assignment
        break
    if not arm_found:
        raise ValueError(f"Manifest does not contain arm_id {normalized_arm_id!r}.")

    variant_path = (
        output_dir
        / (
            f"{normalized_arm_id}__root_{int(root_id)}__"
            f"reference_{reference_morphology_class}.yaml"
        )
    ).resolve()
    variant_path.write_text(
        yaml.safe_dump(manifest_payload, sort_keys=False),
        encoding="utf-8",
    )
    return variant_path


def _mean_projection_trace(payload: Any) -> np.ndarray:
    values = np.asarray(payload, dtype=np.float64)
    if values.ndim == 1:
        values = values.reshape(-1, 1)
    if values.ndim != 2:
        raise ValueError("Projection traces must be one- or two-dimensional.")
    return values.mean(axis=1)


def _select_shared_trace(payload: Mapping[str, Any]) -> np.ndarray:
    readout_ids = tuple(str(item) for item in payload["readout_ids"])
    try:
        readout_index = readout_ids.index("shared_output_mean")
    except ValueError:
        readout_index = 0
    values = np.asarray(payload["values"], dtype=np.float64)
    if values.ndim != 2:
        raise ValueError("Shared readout traces must be a two-dimensional matrix.")
    return values[:, readout_index]


def _align_scalar_traces(
    *,
    time_ms_a: np.ndarray,
    values_a: np.ndarray,
    time_ms_b: np.ndarray,
    values_b: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    grid = np.unique(
        np.concatenate(
            [
                np.asarray(time_ms_a, dtype=np.float64).ravel(),
                np.asarray(time_ms_b, dtype=np.float64).ravel(),
            ]
        )
    )
    if grid.size == 0:
        raise ValueError("Cannot align empty traces.")
    return (
        grid,
        _interpolate_scalar_trace(
            time_ms=np.asarray(time_ms_a, dtype=np.float64).ravel(),
            values=np.asarray(values_a, dtype=np.float64).ravel(),
            grid=grid,
        ),
        _interpolate_scalar_trace(
            time_ms=np.asarray(time_ms_b, dtype=np.float64).ravel(),
            values=np.asarray(values_b, dtype=np.float64).ravel(),
            grid=grid,
        ),
    )


def _interpolate_scalar_trace(
    *,
    time_ms: np.ndarray,
    values: np.ndarray,
    grid: np.ndarray,
) -> np.ndarray:
    if time_ms.size != values.size:
        raise ValueError("Scalar trace times and values must have the same length.")
    if time_ms.size == 0:
        raise ValueError("Scalar traces must contain at least one sample.")
    if time_ms.size == 1:
        return np.full(grid.shape, float(values[0]), dtype=np.float64)
    return np.interp(grid, time_ms, values)


def _threshold_crossed(
    *,
    comparison: str,
    value: float,
    threshold: float,
) -> bool:
    if comparison == "max":
        return float(value) > float(threshold)
    if comparison == "min":
        return float(value) < float(threshold)
    raise ValueError(f"Unsupported threshold comparison {comparison!r}.")


def _next_higher_morphology_class(morphology_class: str) -> str | None:
    rank = _morphology_class_rank(morphology_class)
    if rank >= len(HYBRID_MORPHOLOGY_PROMOTION_ORDER) - 1:
        return None
    return str(HYBRID_MORPHOLOGY_PROMOTION_ORDER[rank + 1])


def _morphology_class_rank(morphology_class: str) -> int:
    return HYBRID_MORPHOLOGY_PROMOTION_ORDER.index(
        normalize_hybrid_morphology_class(
            morphology_class,
            field_name="mixed_fidelity_inspection.morphology_class",
        )
    )


def _worst_status(statuses: Sequence[str] | Any) -> str:
    current = STATUS_PASS
    for status in statuses:
        normalized_status = str(status)
        if STATUS_PRIORITY[normalized_status] > STATUS_PRIORITY[current]:
            current = normalized_status
    return current


def _slug(value: str) -> str:
    slug = _SLUG_PATTERN.sub("-", str(value).lower()).strip("-")
    return slug or "value"


def _render_mixed_fidelity_markdown(summary: Mapping[str, Any]) -> str:
    root_summaries = list(summary["root_summaries"])
    policy_hook = dict(summary["mixed_fidelity_plan"]["policy_hook"])
    lines = [
        "# Mixed-Fidelity Inspection Report",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Experiment: `{summary['experiment_id']}`",
        f"- Arm: `{summary['arm_id']}`",
        f"- Base bundle: `{summary['base_run_summary']['metadata_path']}`",
        f"- Promotion policy targets: `{policy_hook['promotion_recommendation_root_ids']}`",
        f"- Demotion policy targets: `{policy_hook['demotion_recommendation_root_ids']}`",
        f"- Recommended promotion roots after comparison: `{summary['recommended_promotion_root_ids']}`",
        "",
        "## Root Reviews",
        "",
    ]
    if not root_summaries:
        lines.append("- No surrogate roots required comparison under the resolved policy.")
    else:
        for item in root_summaries:
            metrics = dict(item.get("metrics", {}))
            lines.extend(
                [
                    f"### Root `{item['root_id']}`",
                    "",
                    f"- Status: `{item['overall_status']}`",
                    f"- Realized class: `{item['realized_morphology_class']}`",
                    f"- Reference class: `{item['reference_morphology_class']}`",
                    f"- Reference source: `{item['reference_source']}`",
                    f"- Root mean-trace MAE: `{metrics.get('root_mean_trace_mae')}`",
                    f"- Shared-output MAE: `{metrics.get('shared_output_trace_mae')}`",
                    f"- Recommended promotion: `{item.get('recommended_promotion', False)}`",
                    f"- Detail JSON: `{item.get('detail_path', '')}`",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value
