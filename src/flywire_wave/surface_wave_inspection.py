from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse as sp
import yaml

from .baseline_execution import (
    build_drive_schedule_for_root_ids,
    load_canonical_input_stream_from_arm_plan,
)
from .config import load_config
from .io_utils import ensure_dir, write_csv_rows, write_deterministic_npz, write_json
from .simulation_planning import (
    _build_surface_wave_execution_plan,
    discover_simulation_run_plans,
    resolve_manifest_simulation_plan,
)
from .surface_wave_contract import (
    DEFAULT_PROCESSED_SURFACE_WAVE_DIR,
    build_surface_wave_model_metadata,
    build_surface_wave_model_reference,
    normalize_surface_wave_parameter_bundle,
    parse_surface_wave_model_metadata,
    write_surface_wave_model_metadata,
)
from .surface_wave_execution import resolve_surface_wave_execution_plan
from .surface_wave_solver import (
    SURFACE_STATE_RESOLUTION,
    SingleNeuronSurfaceWaveSolver,
    SurfaceWaveState,
)


SURFACE_WAVE_INSPECTION_REPORT_VERSION = "surface_wave_inspection.v1"
SURFACE_WAVE_SWEEP_SPEC_VERSION = "surface_wave_sweep.v1"
DEFAULT_SURFACE_WAVE_INSPECTION_DIR = Path("data/processed/surface_wave_inspection")
DEFAULT_REPRESENTATIVE_ROOT_LIMIT = 1
DEFAULT_MAX_ROOT_TRACE_SERIES = 4
DEFAULT_MAX_PATCH_TRACE_SERIES = 4
DEFAULT_DRIVE_EPSILON = 1.0e-12
DEFAULT_DYNAMIC_RANGE_EPSILON = 1.0e-6
DEFAULT_PULSE_ENERGY_GROWTH_WARN = 1.05
DEFAULT_PULSE_ENERGY_GROWTH_FAIL = 1.25
DEFAULT_PULSE_PEAK_GROWTH_WARN = 1.25
DEFAULT_PULSE_PEAK_GROWTH_FAIL = 1.75
DEFAULT_COUPLED_PEAK_TO_DRIVE_WARN = 25.0
DEFAULT_COUPLED_PEAK_TO_DRIVE_FAIL = 100.0

STATUS_PASS = "pass"
STATUS_WARN = "warn"
STATUS_FAIL = "fail"
STATUS_RANK = {
    STATUS_PASS: 0,
    STATUS_WARN: 1,
    STATUS_FAIL: 2,
}

RUN_SUMMARY_FIELDNAMES = (
    "run_id",
    "overall_status",
    "arm_id",
    "seed",
    "sweep_point_id",
    "parameter_preset",
    "parameter_hash",
    "shared_output_peak_abs",
    "shared_output_dynamic_range",
    "mean_abs_pairwise_root_correlation",
    "max_spatial_contrast",
    "pulse_energy_growth_factor_max",
    "pulse_activation_peak_growth_factor_max",
    "pulse_wavefront_speed_units_per_ms_max",
    "pulse_wavefront_detected_count",
    "coupling_event_count",
    "report_path",
    "summary_path",
)

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
_REPORT_PALETTE = (
    "#0f766e",
    "#b91c1c",
    "#1d4ed8",
    "#d97706",
    "#7c3aed",
    "#0369a1",
    "#475569",
    "#0f172a",
)


def load_surface_wave_sweep_spec(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    return normalize_surface_wave_sweep_spec(payload)


def normalize_surface_wave_sweep_spec(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    if payload is not None and not isinstance(payload, Mapping):
        raise ValueError("surface-wave sweep spec must be a mapping when provided.")
    unknown_keys = sorted(
        set(raw_payload)
        - {"version", "parameter_sets", "grid", "seed_values", "representative_root_limit"}
    )
    if unknown_keys:
        raise ValueError(
            "surface-wave sweep spec contains unsupported keys: "
            f"{unknown_keys!r}."
        )

    version = str(raw_payload.get("version", SURFACE_WAVE_SWEEP_SPEC_VERSION)).strip()
    if version != SURFACE_WAVE_SWEEP_SPEC_VERSION:
        raise ValueError(
            f"surface-wave sweep spec version must be {SURFACE_WAVE_SWEEP_SPEC_VERSION!r}."
        )

    representative_root_limit = int(
        raw_payload.get("representative_root_limit", DEFAULT_REPRESENTATIVE_ROOT_LIMIT)
    )
    if representative_root_limit < 1:
        raise ValueError("representative_root_limit must be positive.")

    seed_values = raw_payload.get("seed_values")
    normalized_seed_values: list[int] | None = None
    if seed_values is not None:
        if not isinstance(seed_values, Sequence) or isinstance(seed_values, (str, bytes)):
            raise ValueError("seed_values must be a list when provided.")
        normalized_seed_values = []
        for index, value in enumerate(seed_values):
            normalized_value = int(value)
            if normalized_value < 0:
                raise ValueError(f"seed_values[{index}] must be non-negative.")
            normalized_seed_values.append(normalized_value)
        if not normalized_seed_values:
            raise ValueError("seed_values must contain at least one seed when provided.")

    parameter_sets = raw_payload.get("parameter_sets")
    normalized_parameter_sets: list[dict[str, Any]] = []
    if parameter_sets is not None:
        if not isinstance(parameter_sets, Sequence) or isinstance(parameter_sets, (str, bytes)):
            raise ValueError("parameter_sets must be a list when provided.")
        for index, item in enumerate(parameter_sets):
            if not isinstance(item, Mapping):
                raise ValueError(f"parameter_sets[{index}] must be a mapping.")
            parameter_bundle = item.get("parameter_bundle", {})
            if not isinstance(parameter_bundle, Mapping):
                raise ValueError(
                    f"parameter_sets[{index}].parameter_bundle must be a mapping."
                )
            sweep_point_id = item.get("sweep_point_id")
            label = item.get("label")
            normalized_parameter_sets.append(
                {
                    "sweep_point_id": (
                        None
                        if sweep_point_id is None
                        else _normalize_nonempty_string(
                            sweep_point_id,
                            field_name=f"parameter_sets[{index}].sweep_point_id",
                        )
                    ),
                    "label": None if label is None else str(label).strip(),
                    "parameter_bundle": copy.deepcopy(dict(parameter_bundle)),
                }
            )

    grid = raw_payload.get("grid")
    normalized_grid: dict[str, Any] | None = None
    if grid is not None:
        if not isinstance(grid, Mapping):
            raise ValueError("grid must be a mapping when provided.")
        unknown_grid_keys = sorted(set(grid) - {"sweep_id", "base_parameter_bundle", "axes"})
        if unknown_grid_keys:
            raise ValueError(
                f"surface-wave sweep grid contains unsupported keys {unknown_grid_keys!r}."
            )
        axes = grid.get("axes")
        if not isinstance(axes, Sequence) or isinstance(axes, (str, bytes)) or not axes:
            raise ValueError("grid.axes must be a non-empty list.")
        normalized_axes: list[dict[str, Any]] = []
        for axis_index, axis in enumerate(axes):
            if not isinstance(axis, Mapping):
                raise ValueError(f"grid.axes[{axis_index}] must be a mapping.")
            unknown_axis_keys = sorted(set(axis) - {"key", "label", "values"})
            if unknown_axis_keys:
                raise ValueError(
                    f"grid.axes[{axis_index}] contains unsupported keys {unknown_axis_keys!r}."
                )
            key = str(axis.get("key", "")).strip()
            if not key:
                raise ValueError(f"grid.axes[{axis_index}].key must be non-empty.")
            values = axis.get("values")
            if not isinstance(values, Sequence) or isinstance(values, (str, bytes)) or not values:
                raise ValueError(f"grid.axes[{axis_index}].values must be a non-empty list.")
            normalized_axes.append(
                {
                    "key": key,
                    "label": None if axis.get("label") is None else str(axis["label"]).strip(),
                    "values": [copy.deepcopy(value) for value in values],
                }
            )
        base_parameter_bundle = grid.get("base_parameter_bundle", {})
        if not isinstance(base_parameter_bundle, Mapping):
            raise ValueError("grid.base_parameter_bundle must be a mapping when provided.")
        normalized_grid = {
            "sweep_id": _normalize_nonempty_string(
                grid.get("sweep_id", "grid"),
                field_name="grid.sweep_id",
            ),
            "base_parameter_bundle": copy.deepcopy(dict(base_parameter_bundle)),
            "axes": normalized_axes,
        }

    return {
        "version": SURFACE_WAVE_SWEEP_SPEC_VERSION,
        "representative_root_limit": representative_root_limit,
        "seed_values": normalized_seed_values,
        "parameter_sets": normalized_parameter_sets,
        "grid": normalized_grid,
    }


def generate_surface_wave_inspection_report(
    arm_plans: Sequence[Mapping[str, Any]],
    *,
    sweep_spec: Mapping[str, Any] | None = None,
    surface_wave_inspection_dir: str | Path = DEFAULT_SURFACE_WAVE_INSPECTION_DIR,
) -> dict[str, Any]:
    normalized_arm_plans = _normalize_surface_wave_arm_plans(arm_plans)
    normalized_spec = normalize_surface_wave_sweep_spec(sweep_spec)
    output_dir = build_surface_wave_inspection_output_dir(
        surface_wave_inspection_dir=surface_wave_inspection_dir,
        arm_plans=normalized_arm_plans,
        sweep_spec=normalized_spec,
    )
    ensure_dir(output_dir)
    runs_dir = ensure_dir(output_dir / "runs")

    run_summaries: list[dict[str, Any]] = []
    for arm_plan in normalized_arm_plans:
        arm_reference = _require_mapping(
            arm_plan.get("arm_reference"),
            field_name="arm_plan.arm_reference",
        )
        base_model = _require_mapping(
            _require_mapping(
                arm_plan.get("model_configuration"),
                field_name="arm_plan.model_configuration",
            ).get("surface_wave_model"),
            field_name="arm_plan.model_configuration.surface_wave_model",
        )
        processed_surface_wave_dir = _derive_processed_surface_wave_dir(base_model)
        canonical_input_stream = load_canonical_input_stream_from_arm_plan(arm_plan)
        root_ids = _selected_root_ids_from_arm_plan(arm_plan)
        drive_schedule = build_drive_schedule_for_root_ids(
            root_ids=root_ids,
            canonical_input_stream=canonical_input_stream,
        )
        sweep_points = _expand_surface_wave_sweep_points(
            base_parameter_bundle=_require_mapping(
                base_model.get("parameter_bundle"),
                field_name="surface_wave_model.parameter_bundle",
            ),
            processed_surface_wave_dir=processed_surface_wave_dir,
            sweep_spec=normalized_spec,
        )
        seed_values = _resolve_seed_values(arm_plan=arm_plan, sweep_spec=normalized_spec)

        for sweep_point in sweep_points:
            model_metadata_path = write_surface_wave_model_metadata(
                sweep_point["surface_wave_model"]
            ).resolve()
            for seed in seed_values:
                run_summary = _execute_sweep_run(
                    arm_plan=arm_plan,
                    arm_reference=arm_reference,
                    root_ids=root_ids,
                    canonical_input_stream=canonical_input_stream,
                    drive_schedule=drive_schedule,
                    sweep_point=sweep_point,
                    seed=int(seed),
                    seed_source=(
                        "sweep_spec"
                        if normalized_spec.get("seed_values") is not None
                        else "arm_plan"
                    ),
                    runs_dir=runs_dir,
                    representative_root_limit=int(
                        normalized_spec["representative_root_limit"]
                    ),
                    model_metadata_path=model_metadata_path,
                )
                run_summaries.append(run_summary)

    status_counts = {
        STATUS_PASS: sum(1 for item in run_summaries if item["overall_status"] == STATUS_PASS),
        STATUS_WARN: sum(1 for item in run_summaries if item["overall_status"] == STATUS_WARN),
        STATUS_FAIL: sum(1 for item in run_summaries if item["overall_status"] == STATUS_FAIL),
    }
    overall_status = _worst_status(item["overall_status"] for item in run_summaries)
    runs_csv_path = write_csv_rows(
        fieldnames=RUN_SUMMARY_FIELDNAMES,
        rows=[_flatten_run_summary_for_csv(item) for item in run_summaries],
        out_path=output_dir / "runs.csv",
    ).resolve()
    report_path = (output_dir / "report.md").resolve()
    summary_path = (output_dir / "summary.json").resolve()

    summary = {
        "report_version": SURFACE_WAVE_INSPECTION_REPORT_VERSION,
        "sweep_spec_version": SURFACE_WAVE_SWEEP_SPEC_VERSION,
        "output_dir": str(output_dir.resolve()),
        "summary_path": str(summary_path),
        "report_path": str(report_path),
        "runs_csv_path": str(runs_csv_path),
        "overall_status": overall_status,
        "status_counts": status_counts,
        "run_count": len(run_summaries),
        "manifest_reference": copy.deepcopy(
            _require_mapping(
                normalized_arm_plans[0].get("manifest_reference"),
                field_name="arm_plans[0].manifest_reference",
            )
        ),
        "arm_order": [
            str(
                _require_mapping(
                    item.get("arm_reference"),
                    field_name="arm_plan.arm_reference",
                )["arm_id"]
            )
            for item in normalized_arm_plans
        ],
        "sweep_spec": copy.deepcopy(normalized_spec),
        "run_summaries": [copy.deepcopy(item) for item in run_summaries],
    }

    report_path.write_text(_render_top_level_markdown(summary), encoding="utf-8")
    write_json(summary, summary_path)
    return summary


def execute_surface_wave_inspection_workflow(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    arm_ids: Sequence[str] | None = None,
    use_manifest_seed_sweep: bool = False,
    sweep_spec_path: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    plan = resolve_manifest_simulation_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    arm_plans = discover_simulation_run_plans(
        plan,
        model_mode="surface_wave",
        use_manifest_seed_sweep=use_manifest_seed_sweep,
    )
    if arm_ids:
        normalized_arm_ids = {
            _normalize_identifier(arm_id, field_name="arm_ids") for arm_id in arm_ids
        }
        arm_plans = [
            arm_plan
            for arm_plan in arm_plans
            if str(
                _require_mapping(
                    arm_plan.get("arm_reference"),
                    field_name="arm_plan.arm_reference",
                )["arm_id"]
            )
            in normalized_arm_ids
        ]
    if not arm_plans:
        raise ValueError("No surface-wave arm plans matched the inspection request.")

    resolved_output_dir = (
        Path(output_dir).resolve()
        if output_dir is not None
        else _resolve_surface_wave_inspection_dir_from_plan(plan)
    )
    sweep_spec = (
        load_surface_wave_sweep_spec(sweep_spec_path)
        if sweep_spec_path is not None
        else normalize_surface_wave_sweep_spec(None)
    )
    return generate_surface_wave_inspection_report(
        arm_plans,
        sweep_spec=sweep_spec,
        surface_wave_inspection_dir=resolved_output_dir,
    )


def build_surface_wave_inspection_output_dir(
    *,
    surface_wave_inspection_dir: str | Path,
    arm_plans: Sequence[Mapping[str, Any]],
    sweep_spec: Mapping[str, Any],
) -> Path:
    arm_references = [
        _require_mapping(plan.get("arm_reference"), field_name="arm_plan.arm_reference")
        for plan in arm_plans
    ]
    manifest_reference = _require_mapping(
        arm_plans[0].get("manifest_reference"),
        field_name="arm_plans[0].manifest_reference",
    )
    arm_ids = [str(reference["arm_id"]) for reference in arm_references]
    slug = _build_surface_wave_inspection_slug(
        experiment_id=str(manifest_reference["experiment_id"]),
        arm_ids=arm_ids,
        sweep_spec=sweep_spec,
    )
    return Path(surface_wave_inspection_dir).resolve() / slug


def _normalize_surface_wave_arm_plans(
    arm_plans: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not arm_plans:
        raise ValueError("surface-wave inspection requires at least one arm plan.")
    normalized: list[dict[str, Any]] = []
    for index, arm_plan in enumerate(arm_plans):
        mapping = _require_mapping(arm_plan, field_name=f"arm_plans[{index}]")
        arm_reference = _require_mapping(
            mapping.get("arm_reference"),
            field_name=f"arm_plans[{index}].arm_reference",
        )
        if str(arm_reference.get("model_mode")) != "surface_wave":
            raise ValueError(
                "surface-wave inspection only accepts arm plans with "
                "arm_reference.model_mode == 'surface_wave'."
            )
        normalized.append(copy.deepcopy(dict(mapping)))
    return normalized


def _expand_surface_wave_sweep_points(
    *,
    base_parameter_bundle: Mapping[str, Any],
    processed_surface_wave_dir: Path,
    sweep_spec: Mapping[str, Any],
) -> list[dict[str, Any]]:
    base_bundle = normalize_surface_wave_parameter_bundle(base_parameter_bundle)
    points: list[dict[str, Any]] = []

    parameter_sets = _require_sequence(
        sweep_spec.get("parameter_sets", []),
        field_name="sweep_spec.parameter_sets",
    )
    for index, item in enumerate(parameter_sets):
        mapping = _require_mapping(
            item,
            field_name=f"sweep_spec.parameter_sets[{index}]",
        )
        merged_bundle = _deep_merge_mapping(
            base_bundle,
            _require_mapping(
                mapping.get("parameter_bundle"),
                field_name=f"sweep_spec.parameter_sets[{index}].parameter_bundle",
            ),
        )
        sweep_point_id = str(mapping.get("sweep_point_id") or f"preset-{index:03d}")
        label = mapping.get("label") or sweep_point_id
        points.append(
            _build_sweep_point(
                sweep_point_id=sweep_point_id,
                label=str(label),
                source="parameter_set",
                parameter_bundle=merged_bundle,
                varied_parameters={},
                processed_surface_wave_dir=processed_surface_wave_dir,
            )
        )

    grid = sweep_spec.get("grid")
    if isinstance(grid, Mapping):
        grid_mapping = _require_mapping(grid, field_name="sweep_spec.grid")
        grid_base_bundle = _deep_merge_mapping(
            base_bundle,
            _require_mapping(
                grid_mapping.get("base_parameter_bundle", {}),
                field_name="sweep_spec.grid.base_parameter_bundle",
            ),
        )
        axes = _require_sequence(grid_mapping.get("axes"), field_name="sweep_spec.grid.axes")
        axis_mappings = [
            _require_mapping(axis, field_name=f"sweep_spec.grid.axes[{axis_index}]")
            for axis_index, axis in enumerate(axes)
        ]
        grid_values = [
            _require_sequence(
                axis_mapping.get("values"),
                field_name=f"sweep_spec.grid.axes[{axis_index}].values",
            )
            for axis_index, axis_mapping in enumerate(axis_mappings)
        ]
        for index, combination in enumerate(itertools.product(*grid_values)):
            merged_bundle = copy.deepcopy(grid_base_bundle)
            varied_parameters: dict[str, Any] = {}
            label_parts: list[str] = []
            for axis_mapping, value in zip(axis_mappings, combination):
                key = str(axis_mapping["key"])
                _set_nested_mapping_value(merged_bundle, key, copy.deepcopy(value))
                varied_parameters[key] = copy.deepcopy(value)
                axis_label = str(axis_mapping.get("label") or key)
                label_parts.append(f"{axis_label}={value!r}")
            grid_id = str(grid_mapping["sweep_id"])
            points.append(
                _build_sweep_point(
                    sweep_point_id=f"{grid_id}-{index:03d}",
                    label=", ".join(label_parts) if label_parts else grid_id,
                    source="grid",
                    parameter_bundle=merged_bundle,
                    varied_parameters=varied_parameters,
                    processed_surface_wave_dir=processed_surface_wave_dir,
                )
            )

    if points:
        return points
    return [
        _build_sweep_point(
            sweep_point_id="base-000",
            label="base parameter bundle",
            source="base",
            parameter_bundle=base_bundle,
            varied_parameters={},
            processed_surface_wave_dir=processed_surface_wave_dir,
        )
    ]


def _build_sweep_point(
    *,
    sweep_point_id: str,
    label: str,
    source: str,
    parameter_bundle: Mapping[str, Any],
    varied_parameters: Mapping[str, Any],
    processed_surface_wave_dir: Path,
) -> dict[str, Any]:
    surface_wave_model = build_surface_wave_model_metadata(
        processed_surface_wave_dir=processed_surface_wave_dir,
        parameter_bundle=parameter_bundle,
    )
    return {
        "sweep_point_id": _normalize_nonempty_string(
            sweep_point_id,
            field_name="sweep_point_id",
        ),
        "label": str(label).strip(),
        "source": source,
        "varied_parameters": copy.deepcopy(dict(varied_parameters)),
        "surface_wave_model": surface_wave_model,
    }


def _resolve_seed_values(
    *,
    arm_plan: Mapping[str, Any],
    sweep_spec: Mapping[str, Any],
) -> list[int]:
    explicit_seed_values = sweep_spec.get("seed_values")
    if explicit_seed_values is not None:
        return [int(value) for value in explicit_seed_values]
    determinism = _require_mapping(
        arm_plan.get("determinism"),
        field_name="arm_plan.determinism",
    )
    return [int(determinism["seed"])]


def _execute_sweep_run(
    *,
    arm_plan: Mapping[str, Any],
    arm_reference: Mapping[str, Any],
    root_ids: Sequence[int],
    canonical_input_stream: Any,
    drive_schedule: Any,
    sweep_point: Mapping[str, Any],
    seed: int,
    seed_source: str,
    runs_dir: Path,
    representative_root_limit: int,
    model_metadata_path: Path,
) -> dict[str, Any]:
    surface_wave_model = _require_mapping(
        sweep_point.get("surface_wave_model"),
        field_name="sweep_point.surface_wave_model",
    )
    parameter_bundle = _require_mapping(
        surface_wave_model.get("parameter_bundle"),
        field_name="sweep_point.surface_wave_model.parameter_bundle",
    )
    run_id = _build_run_id(
        arm_id=str(arm_reference["arm_id"]),
        seed=seed,
        sweep_point_id=str(sweep_point["sweep_point_id"]),
        parameter_hash=str(surface_wave_model["parameter_hash"]),
    )
    run_dir = ensure_dir(runs_dir / run_id)
    summary_path = (run_dir / "summary.json").resolve()
    report_path = (run_dir / "report.md").resolve()

    base_summary = {
        "run_id": run_id,
        "overall_status": STATUS_FAIL,
        "arm_reference": copy.deepcopy(dict(arm_reference)),
        "topology_condition": str(arm_plan["topology_condition"]),
        "seed_context": {
            "seed": int(seed),
            "seed_source": str(seed_source),
            "rng_family": str(
                _require_mapping(
                    arm_plan.get("determinism"),
                    field_name="arm_plan.determinism",
                )["rng_family"]
            ),
            "seed_scope": str(
                _require_mapping(
                    arm_plan.get("determinism"),
                    field_name="arm_plan.determinism",
                )["seed_scope"]
            ),
        },
        "parameter_context": {
            "sweep_point_id": str(sweep_point["sweep_point_id"]),
            "label": str(sweep_point["label"]),
            "source": str(sweep_point["source"]),
            "parameter_preset": str(surface_wave_model["parameter_preset"]),
            "parameter_hash": str(surface_wave_model["parameter_hash"]),
            "model_bundle_id": str(surface_wave_model["bundle_id"]),
            "model_metadata_path": str(model_metadata_path),
            "varied_parameters": copy.deepcopy(
                _require_mapping(
                    sweep_point.get("varied_parameters", {}),
                    field_name="sweep_point.varied_parameters",
                )
            ),
            "parameter_bundle": copy.deepcopy(dict(parameter_bundle)),
        },
        "artifacts": {
            "run_dir": str(run_dir),
            "summary_path": str(summary_path),
            "report_path": str(report_path),
        },
    }

    try:
        resolved = _resolve_swept_execution_plan(
            arm_plan=arm_plan,
            surface_wave_model=surface_wave_model,
            seed=seed,
        )
        coupled = _run_coupled_execution(
            resolved=resolved,
            drive_schedule=drive_schedule,
        )
        pulse_probes = _run_pulse_probes(
            resolved=resolved,
            representative_root_limit=representative_root_limit,
        )
        diagnostics = _build_diagnostics(
            resolved=resolved,
            drive_schedule=drive_schedule,
            coupled=coupled,
            pulse_probes=pulse_probes,
        )
        artifacts = _write_success_artifacts(
            run_dir=run_dir,
            run_id=run_id,
            base_summary=base_summary,
            canonical_input_stream=canonical_input_stream,
            drive_schedule=drive_schedule,
            resolved=resolved,
            coupled=coupled,
            pulse_probes=pulse_probes,
            diagnostics=diagnostics,
        )
        run_summary = {
            **base_summary,
            "overall_status": diagnostics["overall_status"],
            "canonical_input": {
                "input_kind": canonical_input_stream.input_kind,
                "bundle_id": canonical_input_stream.bundle_id,
                "metadata_path": str(canonical_input_stream.metadata_path),
                "replay_source": canonical_input_stream.replay_source,
                "unit_count": int(canonical_input_stream.unit_count),
                "drive_schedule_hash": str(drive_schedule.drive_schedule_hash),
            },
            "solver": {
                "integration_timestep_ms": float(resolved.integration_timestep_ms),
                "shared_output_timestep_ms": float(resolved.shared_output_timestep_ms),
                "internal_substep_count": int(resolved.internal_substep_count),
                "shared_step_count": int(resolved.timebase.sample_count),
                "root_ids": [int(root_id) for root_id in resolved.root_ids],
            },
            "coupling": {
                "component_count": int(resolved.coupling_plan.component_count),
                "max_delay_steps": int(resolved.coupling_plan.max_delay_steps),
                "topology_condition": resolved.coupling_plan.topology_condition,
                "shuffle_scope": resolved.coupling_plan.shuffle_scope,
                "coupling_hash": resolved.coupling_plan.coupling_hash,
            },
            "metrics": diagnostics["metrics"],
            "diagnostics": diagnostics["diagnostics"],
            "artifacts": artifacts,
        }
    except Exception as exc:
        run_summary = {
            **base_summary,
            "overall_status": STATUS_FAIL,
            "metrics": {},
            "diagnostics": {
                "overall_status": STATUS_FAIL,
                "check_counts": {STATUS_PASS: 0, STATUS_WARN: 0, STATUS_FAIL: 1},
                "checks": [
                    {
                        "check_id": "execution_completed",
                        "status": STATUS_FAIL,
                        "description": (
                            "The sweep point should resolve and execute without raising an exception."
                        ),
                        "value": {"error": str(exc)},
                    }
                ],
            },
            "execution_error": str(exc),
        }

    report_path.write_text(_render_run_markdown(run_summary), encoding="utf-8")
    write_json(run_summary, summary_path)
    return run_summary


def _resolve_swept_execution_plan(
    *,
    arm_plan: Mapping[str, Any],
    surface_wave_model: Mapping[str, Any],
    seed: int,
) -> Any:
    runtime = _require_mapping(arm_plan.get("runtime"), field_name="arm_plan.runtime")
    determinism = copy.deepcopy(
        _require_mapping(arm_plan.get("determinism"), field_name="arm_plan.determinism")
    )
    determinism["seed"] = int(seed)
    surface_wave_execution_plan = _build_surface_wave_execution_plan(
        arm_reference=_require_mapping(
            arm_plan.get("arm_reference"),
            field_name="arm_plan.arm_reference",
        ),
        topology_condition=str(arm_plan["topology_condition"]),
        runtime_timebase=_require_mapping(
            runtime.get("timebase"),
            field_name="arm_plan.runtime.timebase",
        ),
        circuit_assets=_require_mapping(
            arm_plan.get("circuit_assets"),
            field_name="arm_plan.circuit_assets",
        ),
        surface_wave_model=surface_wave_model,
    )
    arm_plan_snapshot = copy.deepcopy(dict(arm_plan))
    arm_plan_snapshot["determinism"] = determinism
    arm_plan_snapshot.setdefault("model_configuration", {})
    arm_plan_snapshot["model_configuration"]["surface_wave_model"] = copy.deepcopy(
        dict(surface_wave_model)
    )
    arm_plan_snapshot["model_configuration"]["surface_wave_reference"] = (
        build_surface_wave_model_reference(surface_wave_model)
    )
    arm_plan_snapshot["model_configuration"]["surface_wave_execution_plan"] = copy.deepcopy(
        surface_wave_execution_plan
    )
    return resolve_surface_wave_execution_plan(
        surface_wave_model=surface_wave_model,
        surface_wave_execution_plan=surface_wave_execution_plan,
        root_ids=_selected_root_ids_from_arm_plan(arm_plan),
        timebase=_require_mapping(
            runtime.get("timebase"),
            field_name="arm_plan.runtime.timebase",
        ),
        determinism=determinism,
        arm_plan=arm_plan_snapshot,
    )


def _run_coupled_execution(
    *,
    resolved: Any,
    drive_schedule: Any,
) -> dict[str, Any]:
    circuit = resolved.build_circuit()
    circuit.initialize_zero()
    vertex_count_by_root = {
        int(bundle.root_id): int(bundle.surface_vertex_count)
        for bundle in resolved.operator_bundles
    }
    for step_index in range(int(resolved.timebase.sample_count)):
        drive_vector = np.asarray(drive_schedule.drive_values[step_index], dtype=np.float64)
        surface_drives_by_root = {
            int(root_id): np.full(
                vertex_count_by_root[int(root_id)],
                float(drive_vector[root_index]),
                dtype=np.float64,
            )
            for root_index, root_id in enumerate(resolved.root_ids)
        }
        circuit.step_shared(surface_drives_by_root=surface_drives_by_root)
    wave_run = circuit.finalize()

    shared_history = [
        copy.deepcopy(item)
        for item in wave_run.shared_readout_history
        if item["lifecycle_stage"] in {"initialized", "step_completed"}
    ]
    shared_time_ms = np.asarray(
        [float(item["time_ms"]) for item in shared_history],
        dtype=np.float64,
    )
    shared_output_mean = np.asarray(
        [float(item["shared_output_mean"]) for item in shared_history],
        dtype=np.float64,
    )
    per_root_mean_activation = {
        int(root_id): np.asarray(
            [
                float(item["per_root_mean_activation"][str(int(root_id))])
                for item in shared_history
            ],
            dtype=np.float64,
        )
        for root_id in resolved.root_ids
    }
    shared_patch_history_by_root = {
        int(root_id): np.asarray(
            wave_run.patch_readout_history_by_root[int(root_id)][
                :: int(resolved.internal_substep_count)
            ],
            dtype=np.float64,
        )
        for root_id in resolved.root_ids
    }
    patch_peak_abs = max(
        float(np.max(np.abs(history)))
        for history in wave_run.patch_readout_history_by_root.values()
    )
    max_spatial_contrast = max(
        float(np.max(np.ptp(history, axis=1)))
        for history in shared_patch_history_by_root.values()
    )
    mean_abs_pairwise_root_correlation = _mean_abs_pairwise_root_correlation(
        per_root_mean_activation
    )
    return {
        "wave_run": wave_run,
        "shared_time_ms": shared_time_ms,
        "shared_output_mean": shared_output_mean,
        "per_root_mean_activation": per_root_mean_activation,
        "shared_patch_history_by_root": shared_patch_history_by_root,
        "coupling_event_count": len(wave_run.coupling_application_history),
        "patch_peak_abs": patch_peak_abs,
        "max_spatial_contrast": max_spatial_contrast,
        "mean_abs_pairwise_root_correlation": mean_abs_pairwise_root_correlation,
    }


def _run_pulse_probes(
    *,
    resolved: Any,
    representative_root_limit: int,
) -> list[dict[str, Any]]:
    probe_root_ids = [int(root_id) for root_id in resolved.root_ids[:representative_root_limit]]
    probes: list[dict[str, Any]] = []
    for root_id in probe_root_ids:
        operator_bundle = next(
            bundle for bundle in resolved.operator_bundles if int(bundle.root_id) == root_id
        )
        (
            solver,
            initial_snapshot,
            probe_initialization_mode,
            probe_seed_vertex,
        ) = _initialize_pulse_probe_solver(
            operator_bundle=operator_bundle,
            resolved=resolved,
        )
        patch_history = [solver.current_patch_state().activation.copy()]
        time_ms = [0.0]
        activation_peak_abs = [float(initial_snapshot.diagnostics.activation_peak_abs)]
        energy = [float(initial_snapshot.diagnostics.energy)]
        for _ in range(int(resolved.timebase.sample_count) * int(resolved.internal_substep_count)):
            snapshot = solver.step()
            time_ms.append(float(snapshot.time_ms))
            patch_history.append(solver.current_patch_state().activation.copy())
            activation_peak_abs.append(float(snapshot.diagnostics.activation_peak_abs))
            energy.append(float(snapshot.diagnostics.energy))
        result = solver.finalize()
        patch_history_array = np.asarray(patch_history, dtype=np.float64)
        time_ms_array = np.asarray(time_ms, dtype=np.float64)
        activation_peak_abs_array = np.asarray(activation_peak_abs, dtype=np.float64)
        energy_array = np.asarray(energy, dtype=np.float64)
        wavefront = _estimate_patch_wavefront_speed(
            operator_bundle=operator_bundle,
            patch_activation_history=patch_history_array,
            time_ms=time_ms_array,
            seed_patch=int(np.argmax(np.abs(patch_history_array[0]))),
        )
        probes.append(
            {
                "root_id": int(root_id),
                "seed_vertex": int(probe_seed_vertex),
                "probe_initialization_mode": probe_initialization_mode,
                "patch_activation_history": patch_history_array,
                "time_ms": time_ms_array,
                "activation_peak_abs": activation_peak_abs_array,
                "energy": energy_array,
                "energy_growth_factor": float(
                    np.max(energy_array)
                    / max(abs(float(energy_array[0])), DEFAULT_DRIVE_EPSILON)
                ),
                "activation_peak_growth_factor": float(
                    np.max(activation_peak_abs_array)
                    / max(float(activation_peak_abs_array[0]), DEFAULT_DRIVE_EPSILON)
                ),
                "energy_decay_ratio": float(
                    energy_array[-1]
                    / max(abs(float(energy_array[0])), DEFAULT_DRIVE_EPSILON)
                ),
                "activation_peak_final_ratio": float(
                    activation_peak_abs_array[-1]
                    / max(float(activation_peak_abs_array[0]), DEFAULT_DRIVE_EPSILON)
                ),
                "wavefront": wavefront,
            }
        )
    return probes


def _initialize_pulse_probe_solver(
    *,
    operator_bundle: Any,
    resolved: Any,
) -> tuple[SingleNeuronSurfaceWaveSolver, Any, str, int]:
    localized_solver = SingleNeuronSurfaceWaveSolver(
        operator_bundle=operator_bundle,
        surface_wave_model=resolved.surface_wave_model,
        integration_timestep_ms=resolved.integration_timestep_ms,
        shared_output_timestep_ms=resolved.shared_output_timestep_ms,
    )
    localized_initial_snapshot = localized_solver.initialize_localized_pulse()
    localized_patch_activation = localized_solver.current_patch_state().activation.copy()
    localized_seed_vertex = int(operator_bundle.select_default_seed_vertex())
    if not _pulse_probe_initial_patch_support_is_too_broad(
        localized_patch_activation
    ):
        return (
            localized_solver,
            localized_initial_snapshot,
            "localized_pulse",
            int(localized_seed_vertex),
        )

    onehot_solver = SingleNeuronSurfaceWaveSolver(
        operator_bundle=operator_bundle,
        surface_wave_model=resolved.surface_wave_model,
        integration_timestep_ms=resolved.integration_timestep_ms,
        shared_output_timestep_ms=resolved.shared_output_timestep_ms,
    )
    activation = np.zeros(
        operator_bundle.surface_vertex_count,
        dtype=np.float64,
    )
    activation[int(localized_seed_vertex)] = 1.0
    initial_snapshot = onehot_solver.initialize_state(
        SurfaceWaveState(
            resolution=SURFACE_STATE_RESOLUTION,
            activation=activation,
            velocity=np.zeros_like(activation),
            recovery=None,
        )
    )
    return onehot_solver, initial_snapshot, "single_vertex_seed", int(localized_seed_vertex)


def _pulse_probe_initial_patch_support_is_too_broad(
    patch_activation: np.ndarray,
) -> bool:
    patch_values = np.asarray(patch_activation, dtype=np.float64)
    if patch_values.size <= 1:
        return False
    seed_patch = int(np.argmax(np.abs(patch_values)))
    threshold = max(
        float(np.max(np.abs(patch_values))) * 0.25,
        DEFAULT_DYNAMIC_RANGE_EPSILON,
    )
    initially_active_nonseed_count = sum(
        1
        for patch_index, value in enumerate(np.abs(patch_values))
        if patch_index != seed_patch and float(value) >= threshold
    )
    return initially_active_nonseed_count >= patch_values.shape[0] - 1


def _estimate_patch_wavefront_speed(
    *,
    operator_bundle: Any,
    patch_activation_history: np.ndarray,
    time_ms: np.ndarray,
    seed_patch: int,
) -> dict[str, Any]:
    coarse_operator = operator_bundle.coarse_operator
    if coarse_operator is None:
        return {
            "detected": False,
            "detection_mode": "coarse_operator_unavailable",
            "distance_degenerate": False,
            "speed_units_per_ms": None,
            "distance_units": "patch_hops",
            "fit_r2": None,
            "arrival_count": 0,
            "threshold": None,
        }
    adjacency = coarse_operator.tocoo()
    mask = adjacency.row != adjacency.col
    graph = sp.csr_matrix(
        (
            np.ones(int(np.count_nonzero(mask)), dtype=np.float64),
            (adjacency.row[mask], adjacency.col[mask]),
        ),
        shape=coarse_operator.shape,
    )
    distances = sp.csgraph.dijkstra(graph, directed=False, indices=int(seed_patch))
    threshold = max(
        float(np.max(np.abs(patch_activation_history[0]))) * 0.25,
        float(np.max(np.abs(patch_activation_history))) * 0.05,
        DEFAULT_DYNAMIC_RANGE_EPSILON,
    )
    arrival_times: list[float] = []
    arrival_distances: list[float] = []
    for patch_index, distance in enumerate(np.asarray(distances, dtype=np.float64)):
        if patch_index == seed_patch or not np.isfinite(distance) or distance <= 0.0:
            continue
        crossings = np.flatnonzero(
            np.abs(patch_activation_history[:, patch_index]) >= threshold
        )
        if crossings.size == 0:
            continue
        arrival_time_ms = float(time_ms[int(crossings[0])])
        if arrival_time_ms <= 0.0:
            continue
        arrival_times.append(arrival_time_ms)
        arrival_distances.append(float(distance))
    if len(arrival_times) < 2:
        return {
            "detected": False,
            "detection_mode": "insufficient_arrivals",
            "distance_degenerate": False,
            "speed_units_per_ms": None,
            "distance_units": "patch_hops",
            "fit_r2": None,
            "arrival_count": len(arrival_times),
            "threshold": float(threshold),
        }
    x = np.asarray(arrival_times, dtype=np.float64)
    y = np.asarray(arrival_distances, dtype=np.float64)
    if np.allclose(y, y[0]):
        return {
            "detected": True,
            "detection_mode": "equal_distance_arrivals",
            "distance_degenerate": True,
            "speed_units_per_ms": None,
            "distance_units": "patch_hops",
            "fit_r2": None,
            "arrival_count": len(arrival_times),
            "threshold": float(threshold),
        }
    if np.allclose(x, x[0]):
        return {
            "detected": False,
            "detection_mode": "simultaneous_arrivals",
            "distance_degenerate": False,
            "speed_units_per_ms": None,
            "distance_units": "patch_hops",
            "fit_r2": None,
            "arrival_count": len(arrival_times),
            "threshold": float(threshold),
        }
    slope, intercept = np.polyfit(x, y, deg=1)
    if not np.isfinite(slope) or float(slope) <= 0.0:
        return {
            "detected": False,
            "detection_mode": "nonpositive_speed_fit",
            "distance_degenerate": False,
            "speed_units_per_ms": None,
            "distance_units": "patch_hops",
            "fit_r2": None,
            "arrival_count": len(arrival_times),
            "threshold": float(threshold),
        }
    predicted = slope * x + intercept
    residual_sum = float(np.sum((y - predicted) ** 2))
    centered_sum = float(np.sum((y - np.mean(y)) ** 2))
    fit_r2 = None if centered_sum <= 0.0 else float(1.0 - residual_sum / centered_sum)
    return {
        "detected": True,
        "detection_mode": "speed_fit",
        "distance_degenerate": False,
        "speed_units_per_ms": float(slope),
        "distance_units": "patch_hops",
        "fit_r2": fit_r2,
        "arrival_count": len(arrival_times),
        "threshold": float(threshold),
    }


def _build_diagnostics(
    *,
    resolved: Any,
    drive_schedule: Any,
    coupled: Mapping[str, Any],
    pulse_probes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    drive_peak_abs = float(np.max(np.abs(drive_schedule.drive_values)))
    shared_trace = np.asarray(coupled["shared_output_mean"], dtype=np.float64)
    shared_output_peak_abs = float(np.max(np.abs(shared_trace)))
    shared_output_dynamic_range = float(np.ptp(shared_trace))
    max_spatial_contrast = float(coupled["max_spatial_contrast"])
    pulse_energy_growth_factor_max = max(
        float(probe["energy_growth_factor"]) for probe in pulse_probes
    )
    pulse_activation_peak_growth_factor_max = max(
        float(probe["activation_peak_growth_factor"]) for probe in pulse_probes
    )
    pulse_wavefront_speed_units_per_ms_max = _max_optional_float(
        probe["wavefront"]["speed_units_per_ms"] for probe in pulse_probes
    )
    pulse_wavefront_detected_count = sum(
        1
        for probe in pulse_probes
        if bool(probe["wavefront"].get("detected"))
    )
    checks = [
        _check_record(
            check_id="coupled_values_finite",
            status=(
                STATUS_PASS
                if _coupled_values_are_finite(coupled)
                else STATUS_FAIL
            ),
            description="Coupled run traces and patch histories should remain finite.",
            value={"finite": _coupled_values_are_finite(coupled)},
        ),
        _check_record(
            check_id="pulse_values_finite",
            status=(
                STATUS_PASS
                if _pulse_values_are_finite(pulse_probes)
                else STATUS_FAIL
            ),
            description="Representative single-neuron pulse probes should remain finite.",
            value={"finite": _pulse_values_are_finite(pulse_probes)},
        ),
        _threshold_check(
            check_id="pulse_energy_growth_factor",
            value=pulse_energy_growth_factor_max,
            warn=DEFAULT_PULSE_ENERGY_GROWTH_WARN,
            fail=DEFAULT_PULSE_ENERGY_GROWTH_FAIL,
            comparison="max",
            description=(
                "Undriven pulse probes should not show large energy growth after initialization."
            ),
        ),
        _threshold_check(
            check_id="pulse_activation_peak_growth_factor",
            value=pulse_activation_peak_growth_factor_max,
            warn=DEFAULT_PULSE_PEAK_GROWTH_WARN,
            fail=DEFAULT_PULSE_PEAK_GROWTH_FAIL,
            comparison="max",
            description=(
                "Undriven pulse probes should not amplify the initial activation peak excessively."
            ),
        ),
        _check_record(
            check_id="pulse_wavefront_detected",
            status=(
                STATUS_PASS
                if pulse_wavefront_detected_count >= 1
                else STATUS_WARN
            ),
            description="At least one representative pulse probe should show a detectable propagating front.",
            value={"detected_count": int(pulse_wavefront_detected_count)},
        ),
        _check_record(
            check_id="coupled_dynamic_range",
            status=(
                STATUS_PASS
                if drive_peak_abs <= DEFAULT_DRIVE_EPSILON
                or shared_output_dynamic_range >= DEFAULT_DYNAMIC_RANGE_EPSILON
                else STATUS_WARN
            ),
            description="Driven coupled runs should show non-trivial shared-output variation over time.",
            value={
                "shared_output_dynamic_range": float(shared_output_dynamic_range),
                "drive_peak_abs": float(drive_peak_abs),
            },
        ),
        _check_record(
            check_id="coupled_spatial_contrast",
            status=(
                STATUS_PASS
                if drive_peak_abs <= DEFAULT_DRIVE_EPSILON
                or max_spatial_contrast >= DEFAULT_DYNAMIC_RANGE_EPSILON
                else STATUS_WARN
            ),
            description="Driven coupled runs should retain some morphology-resolved spatial contrast.",
            value={
                "max_spatial_contrast": float(max_spatial_contrast),
                "drive_peak_abs": float(drive_peak_abs),
            },
        ),
        _check_record(
            check_id="coupled_coupling_events_present",
            status=(
                STATUS_PASS
                if int(resolved.coupling_plan.component_count) == 0
                or int(resolved.timebase.sample_count) == 0
                or int(coupled["coupling_event_count"]) > 0
                or int(resolved.coupling_plan.max_delay_steps) >= int(
                    resolved.timebase.sample_count * resolved.internal_substep_count
                )
                else STATUS_WARN
            ),
            description="Resolvable coupling components should eventually emit coupling events within the run horizon.",
            value={
                "component_count": int(resolved.coupling_plan.component_count),
                "coupling_event_count": int(coupled["coupling_event_count"]),
                "max_delay_steps": int(resolved.coupling_plan.max_delay_steps),
                "substep_count": int(
                    resolved.timebase.sample_count * resolved.internal_substep_count
                ),
            },
        ),
    ]
    peak_to_drive_ratio = None
    if drive_peak_abs > DEFAULT_DRIVE_EPSILON:
        peak_to_drive_ratio = float(coupled["patch_peak_abs"]) / drive_peak_abs
        checks.append(
            _threshold_check(
                check_id="coupled_peak_to_drive_ratio",
                value=peak_to_drive_ratio,
                warn=DEFAULT_COUPLED_PEAK_TO_DRIVE_WARN,
                fail=DEFAULT_COUPLED_PEAK_TO_DRIVE_FAIL,
                comparison="max",
                description=(
                    "Coupled patch activations should not dwarf the manifest drive by an implausible ratio."
                ),
            )
        )
    overall_status = _worst_status(check["status"] for check in checks)
    return {
        "overall_status": overall_status,
        "metrics": {
            "shared_output_peak_abs": shared_output_peak_abs,
            "shared_output_peak_time_ms": float(
                coupled["shared_time_ms"][int(np.argmax(np.abs(shared_trace)))]
            ),
            "shared_output_dynamic_range": shared_output_dynamic_range,
            "drive_peak_abs": drive_peak_abs,
            "mean_abs_pairwise_root_correlation": coupled[
                "mean_abs_pairwise_root_correlation"
            ],
            "max_spatial_contrast": max_spatial_contrast,
            "coupling_event_count": int(coupled["coupling_event_count"]),
            "pulse_energy_growth_factor_max": pulse_energy_growth_factor_max,
            "pulse_activation_peak_growth_factor_max": pulse_activation_peak_growth_factor_max,
            "pulse_wavefront_speed_units_per_ms_max": pulse_wavefront_speed_units_per_ms_max,
            "pulse_wavefront_detected_count": int(pulse_wavefront_detected_count),
            "coupled_peak_to_drive_ratio": peak_to_drive_ratio,
        },
        "diagnostics": {
            "overall_status": overall_status,
            "check_counts": {
                STATUS_PASS: sum(1 for item in checks if item["status"] == STATUS_PASS),
                STATUS_WARN: sum(1 for item in checks if item["status"] == STATUS_WARN),
                STATUS_FAIL: sum(1 for item in checks if item["status"] == STATUS_FAIL),
            },
            "checks": checks,
        },
    }


def _write_success_artifacts(
    *,
    run_dir: Path,
    run_id: str,
    base_summary: Mapping[str, Any],
    canonical_input_stream: Any,
    drive_schedule: Any,
    resolved: Any,
    coupled: Mapping[str, Any],
    pulse_probes: Sequence[Mapping[str, Any]],
    diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    shared_svg_path = (run_dir / "coupled_shared_trace.svg").resolve()
    shared_svg_path.write_text(
        _render_line_chart_svg(
            title=f"{run_id}: coupled shared output and root means",
            x_label="time (ms)",
            y_label="activation (au)",
            series=_coupled_shared_chart_series(coupled),
        ),
        encoding="utf-8",
    )
    representative_root_id = int(pulse_probes[0]["root_id"])
    coupled_patch_svg_path = (run_dir / f"root_{representative_root_id}_coupled_patch_trace.svg").resolve()
    coupled_patch_svg_path.write_text(
        _render_line_chart_svg(
            title=f"{run_id}: root {representative_root_id} coupled patch activation",
            x_label="time (ms)",
            y_label="activation (au)",
            series=_patch_trace_series(
                time_ms=np.asarray(coupled["shared_time_ms"], dtype=np.float64),
                patch_history=np.asarray(
                    coupled["shared_patch_history_by_root"][representative_root_id],
                    dtype=np.float64,
                ),
                prefix="patch",
            ),
        ),
        encoding="utf-8",
    )
    pulse_svg_path = (run_dir / f"root_{representative_root_id}_pulse_probe.svg").resolve()
    pulse_svg_path.write_text(
        _render_line_chart_svg(
            title=f"{run_id}: root {representative_root_id} isolated pulse diagnostics",
            x_label="time (ms)",
            y_label="value",
            series=[
                {
                    "label": "activation_peak_abs",
                    "x": np.asarray(pulse_probes[0]["time_ms"], dtype=np.float64),
                    "y": np.asarray(pulse_probes[0]["activation_peak_abs"], dtype=np.float64),
                    "color": _REPORT_PALETTE[0],
                },
                {
                    "label": "energy",
                    "x": np.asarray(pulse_probes[0]["time_ms"], dtype=np.float64),
                    "y": np.asarray(pulse_probes[0]["energy"], dtype=np.float64),
                    "color": _REPORT_PALETTE[1],
                },
            ],
        ),
        encoding="utf-8",
    )
    pulse_patch_svg_path = (run_dir / f"root_{representative_root_id}_pulse_patch_trace.svg").resolve()
    pulse_patch_svg_path.write_text(
        _render_line_chart_svg(
            title=f"{run_id}: root {representative_root_id} isolated pulse patch activation",
            x_label="time (ms)",
            y_label="activation (au)",
            series=_patch_trace_series(
                time_ms=np.asarray(pulse_probes[0]["time_ms"], dtype=np.float64),
                patch_history=np.asarray(
                    pulse_probes[0]["patch_activation_history"],
                    dtype=np.float64,
                ),
                prefix="patch",
            ),
        ),
        encoding="utf-8",
    )

    traces_payload = {
        "coupled_time_ms": np.asarray(coupled["shared_time_ms"], dtype=np.float64),
        "coupled_shared_output_mean": np.asarray(
            coupled["shared_output_mean"],
            dtype=np.float64,
        ),
        "drive_values": np.asarray(drive_schedule.drive_values, dtype=np.float64),
        "input_time_ms": np.asarray(canonical_input_stream.time_ms, dtype=np.float64),
        "root_ids": np.asarray(resolved.root_ids, dtype=np.int64),
    }
    for root_id, values in coupled["per_root_mean_activation"].items():
        traces_payload[f"root_{int(root_id)}_coupled_mean_activation"] = np.asarray(
            values,
            dtype=np.float64,
        )
        traces_payload[f"root_{int(root_id)}_coupled_patch_activation"] = np.asarray(
            coupled["shared_patch_history_by_root"][int(root_id)],
            dtype=np.float64,
        )
    for probe in pulse_probes:
        root_id = int(probe["root_id"])
        traces_payload[f"root_{root_id}_pulse_time_ms"] = np.asarray(
            probe["time_ms"],
            dtype=np.float64,
        )
        traces_payload[f"root_{root_id}_pulse_patch_activation"] = np.asarray(
            probe["patch_activation_history"],
            dtype=np.float64,
        )
        traces_payload[f"root_{root_id}_pulse_energy"] = np.asarray(
            probe["energy"],
            dtype=np.float64,
        )
        traces_payload[f"root_{root_id}_pulse_activation_peak_abs"] = np.asarray(
            probe["activation_peak_abs"],
            dtype=np.float64,
        )
    traces_path = write_deterministic_npz(
        traces_payload,
        run_dir / "traces.npz",
    ).resolve()

    artifacts = copy.deepcopy(dict(base_summary["artifacts"]))
    artifacts.update(
        {
            "traces_path": str(traces_path),
            "coupled_shared_trace_svg_path": str(shared_svg_path),
            "coupled_patch_trace_svg_path": str(coupled_patch_svg_path),
            "pulse_probe_svg_path": str(pulse_svg_path),
            "pulse_patch_trace_svg_path": str(pulse_patch_svg_path),
        }
    )
    return artifacts


def _render_top_level_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Surface-Wave Sweep Report",
        "",
        f"- Overall status: `{summary['overall_status']}`",
        f"- Run count: `{summary['run_count']}`",
        f"- Pass / warn / fail: `{summary['status_counts'][STATUS_PASS]}` / "
        f"`{summary['status_counts'][STATUS_WARN]}` / "
        f"`{summary['status_counts'][STATUS_FAIL]}`",
        f"- Output directory: `{summary['output_dir']}`",
        "",
        "## Sweep Configuration",
        "",
        "```json",
        json.dumps(summary["sweep_spec"], indent=2, sort_keys=True),
        "```",
        "",
        "## Runs",
        "",
        "| Run | Status | Arm | Seed | Sweep point | Shared peak | Pulse energy growth | Report |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | --- |",
    ]
    for run_summary in summary["run_summaries"]:
        metrics = run_summary.get("metrics", {})
        relative_report = Path(run_summary["artifacts"]["report_path"]).resolve().relative_to(
            Path(summary["output_dir"]).resolve()
        )
        lines.append(
            "| "
            f"`{run_summary['run_id']}` | "
            f"`{run_summary['overall_status']}` | "
            f"`{run_summary['arm_reference']['arm_id']}` | "
            f"{run_summary['seed_context']['seed']} | "
            f"`{run_summary['parameter_context']['sweep_point_id']}` | "
            f"{_format_metric(metrics.get('shared_output_peak_abs'))} | "
            f"{_format_metric(metrics.get('pulse_energy_growth_factor_max'))} | "
            f"[report]({relative_report.as_posix()}) |"
        )
    lines.extend(["", "## Notes", ""])
    lines.append(
        "Each run directory contains a deterministic `summary.json`, `report.md`, "
        "`traces.npz`, and lightweight SVG trace panels for offline review."
    )
    return "\n".join(lines) + "\n"


def _render_run_markdown(run_summary: Mapping[str, Any]) -> str:
    artifacts = run_summary.get("artifacts", {})
    metrics = run_summary.get("metrics", {})
    diagnostics = run_summary.get("diagnostics", {})
    lines = [
        f"# Surface-Wave Run {run_summary['run_id']}",
        "",
        f"- Status: `{run_summary['overall_status']}`",
        f"- Arm: `{run_summary['arm_reference']['arm_id']}`",
        f"- Seed: `{run_summary['seed_context']['seed']}`",
        f"- Sweep point: `{run_summary['parameter_context']['sweep_point_id']}`",
        f"- Parameter preset: `{run_summary['parameter_context']['parameter_preset']}`",
        f"- Parameter hash: `{run_summary['parameter_context']['parameter_hash']}`",
        "",
    ]
    if run_summary.get("execution_error"):
        lines.extend(
            [
                "## Execution Error",
                "",
                f"`{run_summary['execution_error']}`",
                "",
            ]
        )
    if metrics:
        lines.extend(
            [
                "## Metrics",
                "",
                f"- Shared output peak abs: `{_format_metric(metrics.get('shared_output_peak_abs'))}`",
                f"- Shared output dynamic range: `{_format_metric(metrics.get('shared_output_dynamic_range'))}`",
                f"- Mean abs pairwise root correlation: `{_format_metric(metrics.get('mean_abs_pairwise_root_correlation'))}`",
                f"- Max spatial contrast: `{_format_metric(metrics.get('max_spatial_contrast'))}`",
                f"- Pulse energy growth factor max: `{_format_metric(metrics.get('pulse_energy_growth_factor_max'))}`",
                f"- Pulse peak growth factor max: `{_format_metric(metrics.get('pulse_activation_peak_growth_factor_max'))}`",
                f"- Pulse wavefront speed max: `{_format_metric(metrics.get('pulse_wavefront_speed_units_per_ms_max'))}`",
                f"- Coupling event count: `{metrics.get('coupling_event_count')}`",
                "",
            ]
        )
    checks = diagnostics.get("checks", [])
    if checks:
        lines.extend(
            [
                "## Checks",
                "",
                "| Check | Status | Description |",
                "| --- | --- | --- |",
            ]
        )
        for check in checks:
            lines.append(
                f"| `{check['check_id']}` | `{check['status']}` | {check['description']} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Parameter Bundle",
            "",
            "```json",
            json.dumps(run_summary["parameter_context"]["parameter_bundle"], indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    if "coupled_shared_trace_svg_path" in artifacts:
        lines.extend(
            [
                "## Representative Readouts",
                "",
                f"Coupled shared trace: ![]({Path(artifacts['coupled_shared_trace_svg_path']).name})",
                "",
                f"Coupled patch trace: ![]({Path(artifacts['coupled_patch_trace_svg_path']).name})",
                "",
                f"Pulse diagnostics: ![]({Path(artifacts['pulse_probe_svg_path']).name})",
                "",
                f"Pulse patch trace: ![]({Path(artifacts['pulse_patch_trace_svg_path']).name})",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def _coupled_shared_chart_series(coupled: Mapping[str, Any]) -> list[dict[str, Any]]:
    series = [
        {
            "label": "shared_output_mean",
            "x": np.asarray(coupled["shared_time_ms"], dtype=np.float64),
            "y": np.asarray(coupled["shared_output_mean"], dtype=np.float64),
            "color": _REPORT_PALETTE[0],
        }
    ]
    root_series = sorted(
        coupled["per_root_mean_activation"].items(),
        key=lambda item: int(item[0]),
    )[:DEFAULT_MAX_ROOT_TRACE_SERIES]
    for series_index, (root_id, values) in enumerate(root_series, start=1):
        series.append(
            {
                "label": f"root_{int(root_id)}_mean_activation",
                "x": np.asarray(coupled["shared_time_ms"], dtype=np.float64),
                "y": np.asarray(values, dtype=np.float64),
                "color": _REPORT_PALETTE[series_index % len(_REPORT_PALETTE)],
            }
        )
    return series


def _patch_trace_series(
    *,
    time_ms: np.ndarray,
    patch_history: np.ndarray,
    prefix: str,
) -> list[dict[str, Any]]:
    if patch_history.ndim != 2 or patch_history.size == 0:
        return []
    patch_scores = np.max(np.abs(patch_history), axis=0)
    patch_order = np.argsort(-patch_scores, kind="mergesort")[:DEFAULT_MAX_PATCH_TRACE_SERIES]
    series: list[dict[str, Any]] = []
    for series_index, patch_index in enumerate(patch_order):
        series.append(
            {
                "label": f"{prefix}_{int(patch_index)}",
                "x": np.asarray(time_ms, dtype=np.float64),
                "y": np.asarray(patch_history[:, int(patch_index)], dtype=np.float64),
                "color": _REPORT_PALETTE[series_index % len(_REPORT_PALETTE)],
            }
        )
    return series


def _render_line_chart_svg(
    *,
    title: str,
    x_label: str,
    y_label: str,
    series: Sequence[Mapping[str, Any]],
    width: int = 760,
    height: int = 340,
) -> str:
    chart_series = [
        {
            "label": str(item["label"]),
            "x": np.asarray(item["x"], dtype=np.float64),
            "y": np.asarray(item["y"], dtype=np.float64),
            "color": str(item.get("color", _REPORT_PALETTE[0])),
        }
        for item in series
        if np.asarray(item["x"]).size > 0 and np.asarray(item["y"]).size > 0
    ]
    if not chart_series:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
            '<text x="16" y="24" font-family="monospace" font-size="14">No data</text>'
            "</svg>"
        )

    padding_left = 66.0
    padding_right = 18.0
    padding_top = 30.0
    padding_bottom = 46.0
    legend_height = 18.0 * len(chart_series)
    plot_left = padding_left
    plot_top = padding_top
    plot_width = float(width) - padding_left - padding_right
    plot_height = float(height) - padding_top - padding_bottom - legend_height

    all_x = np.concatenate([item["x"] for item in chart_series])
    all_y = np.concatenate([item["y"] for item in chart_series])
    finite_mask = np.isfinite(all_x) & np.isfinite(all_y)
    if not np.any(finite_mask):
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
            '<text x="16" y="24" font-family="monospace" font-size="14">No finite data</text>'
            "</svg>"
        )

    x_min = float(np.min(all_x[np.isfinite(all_x)]))
    x_max = float(np.max(all_x[np.isfinite(all_x)]))
    y_min = float(np.min(all_y[np.isfinite(all_y)]))
    y_max = float(np.max(all_y[np.isfinite(all_y)]))
    if math.isclose(x_min, x_max):
        x_min -= 0.5
        x_max += 0.5
    if math.isclose(y_min, y_max):
        delta = 0.5 if math.isclose(y_min, 0.0) else abs(y_min) * 0.1
        y_min -= delta
        y_max += delta

    def project_x(value: float) -> float:
        return plot_left + (value - x_min) / (x_max - x_min) * plot_width

    def project_y(value: float) -> float:
        return plot_top + plot_height - (value - y_min) / (y_max - y_min) * plot_height

    x_ticks = np.linspace(x_min, x_max, num=5)
    y_ticks = np.linspace(y_min, y_max, num=5)
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        (
            f'<text x="{plot_left:.1f}" y="18" font-family="monospace" '
            f'font-size="14" fill="#0f172a">{_escape_xml(title)}</text>'
        ),
        (
            f'<rect x="{plot_left:.1f}" y="{plot_top:.1f}" width="{plot_width:.1f}" '
            f'height="{plot_height:.1f}" fill="#f8fafc" stroke="#cbd5e1"/>'
        ),
    ]
    for tick in x_ticks:
        x = project_x(float(tick))
        svg_lines.extend(
            [
                (
                    f'<line x1="{x:.1f}" y1="{plot_top + plot_height:.1f}" '
                    f'x2="{x:.1f}" y2="{plot_top + plot_height + 6:.1f}" '
                    'stroke="#94a3b8" stroke-width="1"/>'
                ),
                (
                    f'<text x="{x:.1f}" y="{plot_top + plot_height + 20:.1f}" '
                    'text-anchor="middle" font-family="monospace" font-size="11" '
                    f'fill="#334155">{tick:.3g}</text>'
                ),
            ]
        )
    for tick in y_ticks:
        y = project_y(float(tick))
        svg_lines.extend(
            [
                (
                    f'<line x1="{plot_left - 6:.1f}" y1="{y:.1f}" '
                    f'x2="{plot_left:.1f}" y2="{y:.1f}" stroke="#94a3b8" stroke-width="1"/>'
                ),
                (
                    f'<text x="{plot_left - 10:.1f}" y="{y + 4:.1f}" text-anchor="end" '
                    'font-family="monospace" font-size="11" fill="#334155">'
                    f"{tick:.3g}</text>"
                ),
            ]
        )
    for item in chart_series:
        finite = np.isfinite(item["x"]) & np.isfinite(item["y"])
        if not np.any(finite):
            continue
        points = " ".join(
            f"{project_x(float(x_value)):.2f},{project_y(float(y_value)):.2f}"
            for x_value, y_value in zip(item["x"][finite], item["y"][finite], strict=True)
        )
        svg_lines.append(
            f'<polyline fill="none" stroke="{item["color"]}" stroke-width="2" '
            f'points="{points}"/>'
        )
    legend_y = plot_top + plot_height + 30.0
    for index, item in enumerate(chart_series):
        y = legend_y + 18.0 * index
        svg_lines.extend(
            [
                (
                    f'<line x1="{plot_left:.1f}" y1="{y:.1f}" x2="{plot_left + 20.0:.1f}" '
                    f'y2="{y:.1f}" stroke="{item["color"]}" stroke-width="3"/>'
                ),
                (
                    f'<text x="{plot_left + 28.0:.1f}" y="{y + 4.0:.1f}" '
                    'font-family="monospace" font-size="11" fill="#0f172a">'
                    f"{_escape_xml(item['label'])}</text>"
                ),
            ]
        )
    svg_lines.extend(
        [
            (
                f'<text x="{plot_left + plot_width / 2.0:.1f}" y="{height - 8:.1f}" '
                'text-anchor="middle" font-family="monospace" font-size="12" '
                f'fill="#334155">{_escape_xml(x_label)}</text>'
            ),
            (
                f'<text x="16" y="{plot_top + plot_height / 2.0:.1f}" '
                'font-family="monospace" font-size="12" fill="#334155" '
                'transform="rotate(-90 16 '
                f'{plot_top + plot_height / 2.0:.1f})">{_escape_xml(y_label)}</text>'
            ),
            "</svg>",
        ]
    )
    return "\n".join(svg_lines)


def _flatten_run_summary_for_csv(run_summary: Mapping[str, Any]) -> dict[str, Any]:
    metrics = run_summary.get("metrics", {})
    return {
        "run_id": run_summary["run_id"],
        "overall_status": run_summary["overall_status"],
        "arm_id": run_summary["arm_reference"]["arm_id"],
        "seed": run_summary["seed_context"]["seed"],
        "sweep_point_id": run_summary["parameter_context"]["sweep_point_id"],
        "parameter_preset": run_summary["parameter_context"]["parameter_preset"],
        "parameter_hash": run_summary["parameter_context"]["parameter_hash"],
        "shared_output_peak_abs": metrics.get("shared_output_peak_abs"),
        "shared_output_dynamic_range": metrics.get("shared_output_dynamic_range"),
        "mean_abs_pairwise_root_correlation": metrics.get(
            "mean_abs_pairwise_root_correlation"
        ),
        "max_spatial_contrast": metrics.get("max_spatial_contrast"),
        "pulse_energy_growth_factor_max": metrics.get("pulse_energy_growth_factor_max"),
        "pulse_activation_peak_growth_factor_max": metrics.get(
            "pulse_activation_peak_growth_factor_max"
        ),
        "pulse_wavefront_speed_units_per_ms_max": metrics.get(
            "pulse_wavefront_speed_units_per_ms_max"
        ),
        "pulse_wavefront_detected_count": metrics.get("pulse_wavefront_detected_count"),
        "coupling_event_count": metrics.get("coupling_event_count"),
        "report_path": run_summary["artifacts"]["report_path"],
        "summary_path": run_summary["artifacts"]["summary_path"],
    }


def _build_surface_wave_inspection_slug(
    *,
    experiment_id: str,
    arm_ids: Sequence[str],
    sweep_spec: Mapping[str, Any],
) -> str:
    arm_slug = _joined_slug(arm_ids, prefix="arms")
    signature = {
        "report_version": SURFACE_WAVE_INSPECTION_REPORT_VERSION,
        "experiment_id": experiment_id,
        "arm_ids": list(arm_ids),
        "sweep_spec": copy.deepcopy(dict(sweep_spec)),
    }
    digest = hashlib.sha1(
        json.dumps(signature, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
    ).hexdigest()[:12]
    return f"experiment-{_slugify(experiment_id)}__{arm_slug}__sweep-{digest}"


def _resolve_surface_wave_inspection_dir_from_plan(plan: Mapping[str, Any]) -> Path:
    runtime_config = _require_mapping(plan.get("runtime_config"), field_name="plan.runtime_config")
    config_path = runtime_config.get("config_path")
    if config_path is None:
        return (Path.cwd() / DEFAULT_SURFACE_WAVE_INSPECTION_DIR).resolve()
    cfg = load_config(config_path)
    return Path(cfg["paths"]["surface_wave_inspection_dir"]).resolve()


def _derive_processed_surface_wave_dir(surface_wave_model: Mapping[str, Any]) -> Path:
    normalized = parse_surface_wave_model_metadata(surface_wave_model)
    metadata_path = Path(
        _require_mapping(
            normalized.get("assets"),
            field_name="surface_wave_model.assets",
        )["metadata_json"]["path"]
    ).expanduser()
    if not metadata_path.is_absolute():
        metadata_path = (Path.cwd() / metadata_path).resolve()
    if len(metadata_path.parents) >= 4:
        return metadata_path.parents[3]
    return (Path.cwd() / DEFAULT_PROCESSED_SURFACE_WAVE_DIR).resolve()


def _selected_root_ids_from_arm_plan(arm_plan: Mapping[str, Any]) -> list[int]:
    selection = _require_mapping(arm_plan.get("selection"), field_name="arm_plan.selection")
    root_ids = _require_sequence(
        selection.get("selected_root_ids"),
        field_name="arm_plan.selection.selected_root_ids",
    )
    return [int(root_id) for root_id in root_ids]


def _require_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return dict(value)


def _require_sequence(value: Any, *, field_name: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence.")
    return list(value)


def _normalize_identifier(value: Any, *, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty.")
    normalized = _SLUG_PATTERN.sub("_", text.lower()).strip("_")
    if not normalized:
        raise ValueError(f"{field_name} must contain at least one identifier character.")
    return normalized


def _normalize_nonempty_string(value: Any, *, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty.")
    return text


def _deep_merge_mapping(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge_mapping(
                _require_mapping(merged[key], field_name=f"base[{key!r}]"),
                value,
            )
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _set_nested_mapping_value(payload: Mapping[str, Any], dotted_key: str, value: Any) -> None:
    parts = [part for part in dotted_key.split(".") if part]
    if not parts:
        raise ValueError("Grid axis key must contain at least one path component.")
    owner = payload
    for part in parts[:-1]:
        next_value = owner.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            owner[part] = next_value
        owner = next_value
    owner[parts[-1]] = value


def _build_run_id(*, arm_id: str, seed: int, sweep_point_id: str, parameter_hash: str) -> str:
    return (
        f"{_slugify(arm_id)}__seed-{int(seed):05d}__"
        f"{_slugify(sweep_point_id)}__param-{parameter_hash[:12]}"
    )


def _slugify(value: str) -> str:
    normalized = _SLUG_PATTERN.sub("-", value.lower()).strip("-")
    return normalized or "value"


def _joined_slug(values: Sequence[str], *, prefix: str) -> str:
    joined = "__".join(_slugify(value) for value in values)
    if len(joined) <= 72:
        return f"{prefix}-{joined}"
    digest = hashlib.sha1(",".join(values).encode("utf-8")).hexdigest()[:12]
    head = "__".join(_slugify(value) for value in values[:2])
    return f"{prefix}-{head}-n{len(values)}-{digest}"


def _worst_status(statuses: Sequence[str] | Any) -> str:
    worst = STATUS_PASS
    for status in statuses:
        if STATUS_RANK[str(status)] > STATUS_RANK[worst]:
            worst = str(status)
    return worst


def _check_record(
    *,
    check_id: str,
    status: str,
    description: str,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "description": description,
        "value": copy.deepcopy(dict(value)),
    }


def _threshold_check(
    *,
    check_id: str,
    value: float | None,
    warn: float,
    fail: float,
    comparison: str,
    description: str,
) -> dict[str, Any]:
    if value is None or not np.isfinite(float(value)):
        status = STATUS_FAIL
    elif comparison == "max":
        if float(value) >= float(fail):
            status = STATUS_FAIL
        elif float(value) >= float(warn):
            status = STATUS_WARN
        else:
            status = STATUS_PASS
    else:
        if float(value) <= float(fail):
            status = STATUS_FAIL
        elif float(value) <= float(warn):
            status = STATUS_WARN
        else:
            status = STATUS_PASS
    return _check_record(
        check_id=check_id,
        status=status,
        description=description,
        value={"value": value, "warn": warn, "fail": fail, "comparison": comparison},
    )


def _mean_abs_pairwise_root_correlation(
    per_root_mean_activation: Mapping[int, np.ndarray],
) -> float | None:
    values = [np.asarray(item, dtype=np.float64) for _, item in sorted(per_root_mean_activation.items())]
    valid = [item for item in values if item.size >= 2 and np.std(item) > DEFAULT_DRIVE_EPSILON]
    if len(valid) < 2:
        return None
    correlations: list[float] = []
    for first_index, first in enumerate(valid):
        for second in valid[first_index + 1 :]:
            correlation = np.corrcoef(first, second)[0, 1]
            if np.isfinite(correlation):
                correlations.append(abs(float(correlation)))
    if not correlations:
        return None
    return float(np.mean(correlations))


def _coupled_values_are_finite(coupled: Mapping[str, Any]) -> bool:
    if not np.all(np.isfinite(np.asarray(coupled["shared_time_ms"], dtype=np.float64))):
        return False
    if not np.all(np.isfinite(np.asarray(coupled["shared_output_mean"], dtype=np.float64))):
        return False
    for values in coupled["per_root_mean_activation"].values():
        if not np.all(np.isfinite(np.asarray(values, dtype=np.float64))):
            return False
    for history in coupled["shared_patch_history_by_root"].values():
        if not np.all(np.isfinite(np.asarray(history, dtype=np.float64))):
            return False
    return True


def _pulse_values_are_finite(pulse_probes: Sequence[Mapping[str, Any]]) -> bool:
    for probe in pulse_probes:
        for key in ("time_ms", "patch_activation_history", "activation_peak_abs", "energy"):
            if not np.all(np.isfinite(np.asarray(probe[key], dtype=np.float64))):
                return False
    return True


def _max_optional_float(values: Any) -> float | None:
    finite = [float(value) for value in values if value is not None and np.isfinite(float(value))]
    if not finite:
        return None
    return float(max(finite))


def _format_metric(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    numeric = float(value)
    if not np.isfinite(numeric):
        return str(value)
    return f"{numeric:.6g}"


def _escape_xml(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


__all__ = [
    "DEFAULT_SURFACE_WAVE_INSPECTION_DIR",
    "SURFACE_WAVE_INSPECTION_REPORT_VERSION",
    "SURFACE_WAVE_SWEEP_SPEC_VERSION",
    "build_surface_wave_inspection_output_dir",
    "execute_surface_wave_inspection_workflow",
    "generate_surface_wave_inspection_report",
    "load_surface_wave_sweep_spec",
    "normalize_surface_wave_sweep_spec",
]
