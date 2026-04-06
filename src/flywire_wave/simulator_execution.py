from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .baseline_execution import (
    build_drive_schedule_for_root_ids,
    load_canonical_input_stream_from_arm_plan,
    resolve_baseline_execution_plan_from_arm_plan,
)
from .hybrid_morphology_runtime import (
    SURFACE_WAVE_RUNTIME_SOURCE_INJECTION_STRATEGY,
    resolve_morphology_runtime_from_arm_plan,
    run_morphology_runtime_shared_schedule,
)
from .simulation_planning import (
    discover_simulation_run_plans,
    resolve_manifest_simulation_plan,
)
from .simulator_packaging import (
    DECLARED_TIMEBASE_WINDOW_ID,
    EXECUTION_PROVENANCE_ARTIFACT_ID,
    FINAL_ENDPOINT_WINDOW_ID,
    MIXED_MORPHOLOGY_STATE_BUNDLE_ARTIFACT_ID,
    SIMULATOR_EXECUTION_LOG_FORMAT,
    SIMULATOR_EXECUTION_PROVENANCE_FORMAT,
    SIMULATOR_UI_COMPARISON_PAYLOAD_FORMAT,
    STRUCTURED_LOG_ARTIFACT_ID,
    SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID,
    SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID,
    SURFACE_WAVE_SUMMARY_ARTIFACT_ID,
    UI_COMPARISON_PAYLOAD_ARTIFACT_ID,
    ExecutedSimulationArmSummary,
    build_surface_wave_execution_artifacts,
    package_simulation_result,
)
from .simulator_result_contract import (
    BASELINE_MODEL_MODE,
    SURFACE_WAVE_MODEL_MODE,
)
from .simulator_runtime import (
    SimulationLifecycleEvent,
    SimulationReadoutTraces,
    SimulationRunResult,
    SimulationSnapshot,
    build_simulation_run_blueprint,
)


SIMULATOR_MANIFEST_EXECUTION_VERSION = "simulator_manifest_execution.v1"
SURFACE_WAVE_INPUT_BINDING_STRATEGY = SURFACE_WAVE_RUNTIME_SOURCE_INJECTION_STRATEGY
SUPPORTED_EXECUTABLE_MODEL_MODES = (
    BASELINE_MODEL_MODE,
    SURFACE_WAVE_MODEL_MODE,
)


class _StructuredEventRecorder:
    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def record(self, event: SimulationLifecycleEvent) -> None:
        snapshot = event.snapshot
        self._records.append(
            {
                "event_index": len(self._records),
                "event_type": event.event_type,
                "completed_steps": int(event.context.completed_steps),
                "current_time_ms": float(event.context.current_time_ms),
                "dt_ms": float(event.context.dt_ms),
                "sample_count": int(event.context.sample_count),
                "readout_values": snapshot.readout_mapping(),
                "dynamic_state_min": float(np.min(snapshot.dynamic_state)),
                "dynamic_state_max": float(np.max(snapshot.dynamic_state)),
                "dynamic_state_mean": float(np.mean(snapshot.dynamic_state)),
                "exogenous_drive_l2": float(np.linalg.norm(snapshot.exogenous_drive)),
                "recurrent_input_l2": float(np.linalg.norm(snapshot.recurrent_input)),
                "state_summary_row_count": len(snapshot.state_summaries),
            }
        )

    @property
    def records(self) -> list[dict[str, Any]]:
        return [copy.deepcopy(record) for record in self._records]


def execute_manifest_simulation(
    *,
    manifest_path: str | Path,
    config_path: str | Path,
    schema_path: str | Path,
    design_lock_path: str | Path,
    model_mode: str = BASELINE_MODEL_MODE,
    arm_id: str | None = None,
    use_manifest_seed_sweep: bool = False,
    simulation_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_model_mode = _normalize_model_mode(model_mode)
    plan = (
        _require_mapping(simulation_plan, field_name="simulation_plan")
        if simulation_plan is not None
        else resolve_manifest_simulation_plan(
            manifest_path=manifest_path,
            config_path=config_path,
            schema_path=schema_path,
            design_lock_path=design_lock_path,
        )
    )
    arm_plans = discover_simulation_run_plans(
        plan,
        arm_id=arm_id,
        model_mode=normalized_model_mode,
        use_manifest_seed_sweep=use_manifest_seed_sweep,
    )
    if not arm_plans:
        raise ValueError(
            f"No runnable simulator arms were discovered for model_mode {normalized_model_mode!r}."
        )

    execution_request = {
        "entrypoint": "scripts/run_simulation.py",
        "workflow_version": SIMULATOR_MANIFEST_EXECUTION_VERSION,
        "manifest_path": str(Path(manifest_path).resolve()),
        "config_path": str(Path(config_path).resolve()),
        "schema_path": str(Path(schema_path).resolve()),
        "design_lock_path": str(Path(design_lock_path).resolve()),
        "model_mode": normalized_model_mode,
        "arm_id": arm_id,
        "use_manifest_seed_sweep": bool(use_manifest_seed_sweep),
    }

    executed_runs = [
        _execute_arm_plan(
            arm_plan,
            execution_request=execution_request,
        ).as_mapping()
        for arm_plan in arm_plans
    ]
    return {
        "workflow_version": SIMULATOR_MANIFEST_EXECUTION_VERSION,
        "model_mode": normalized_model_mode,
        "manifest_reference": copy.deepcopy(plan["manifest_reference"]),
        "arm_order": [
            arm_plan["arm_reference"]["arm_id"]
            for arm_plan in arm_plans
        ],
        "executed_run_count": len(executed_runs),
        "executed_runs": executed_runs,
    }


def main(argv: Sequence[str] | None = None) -> int:
    from .simulator_cli import main as cli_main

    return cli_main(argv)


def _execute_arm_plan(
    arm_plan: Mapping[str, Any],
    *,
    execution_request: Mapping[str, Any],
) -> ExecutedSimulationArmSummary:
    arm_reference = _require_mapping(
        arm_plan.get("arm_reference"),
        field_name="arm_plan.arm_reference",
    )
    model_mode = _normalize_model_mode(arm_reference.get("model_mode"))
    if model_mode == BASELINE_MODEL_MODE:
        return _execute_baseline_arm_plan(
            arm_plan,
            execution_request=execution_request,
        )
    if model_mode == SURFACE_WAVE_MODEL_MODE:
        return _execute_surface_wave_arm_plan(
            arm_plan,
            execution_request=execution_request,
        )
    raise ValueError(f"Unsupported executable model_mode {model_mode!r}.")


def _execute_baseline_arm_plan(
    arm_plan: Mapping[str, Any],
    *,
    execution_request: Mapping[str, Any],
) -> ExecutedSimulationArmSummary:
    resolved = resolve_baseline_execution_plan_from_arm_plan(arm_plan)
    recorder = _StructuredEventRecorder()
    result = resolved.run_to_completion(hooks=[recorder.record])
    structured_log_records = recorder.records
    return package_simulation_result(
        workflow_version=SIMULATOR_MANIFEST_EXECUTION_VERSION,
        arm_plan=arm_plan,
        execution_request=execution_request,
        result=result,
        state_summary_rows=_sorted_state_summary_rows(result),
        metrics_rows=_build_metric_rows(result),
        structured_log_records=structured_log_records,
    )


def _execute_surface_wave_arm_plan(
    arm_plan: Mapping[str, Any],
    *,
    execution_request: Mapping[str, Any],
) -> ExecutedSimulationArmSummary:
    runtime = resolve_morphology_runtime_from_arm_plan(arm_plan)
    canonical_input_stream = load_canonical_input_stream_from_arm_plan(arm_plan)
    drive_schedule = build_drive_schedule_for_root_ids(
        root_ids=runtime.root_ids,
        canonical_input_stream=canonical_input_stream,
    )
    execution_payload = _run_surface_wave_manifest_execution(
        arm_plan=arm_plan,
        runtime=runtime,
        canonical_input_stream=canonical_input_stream,
        drive_schedule=drive_schedule,
    )
    result = execution_payload["result"]
    surface_wave_artifacts = execution_payload["surface_wave_artifacts"]
    return package_simulation_result(
        workflow_version=SIMULATOR_MANIFEST_EXECUTION_VERSION,
        arm_plan=arm_plan,
        execution_request=execution_request,
        result=result,
        state_summary_rows=execution_payload["state_summary_rows"],
        metrics_rows=_build_metric_rows(result),
        structured_log_records=execution_payload["structured_log_records"],
        model_execution=surface_wave_artifacts.provenance_model_execution,
        surface_wave_artifacts=surface_wave_artifacts,
    )


def _run_surface_wave_manifest_execution(
    *,
    arm_plan: Mapping[str, Any],
    runtime: Any,
    canonical_input_stream: Any,
    drive_schedule: Any,
) -> dict[str, Any]:
    last_drive_vector, wave_run = run_morphology_runtime_shared_schedule(
        runtime,
        drive_values=drive_schedule.drive_values,
    )
    run_blueprint = _build_surface_wave_run_blueprint(
        arm_plan=arm_plan,
        runtime=runtime,
        canonical_input_stream=canonical_input_stream,
        drive_schedule=drive_schedule,
    )
    initial_state_summaries = wave_run.export_state_summaries(
        state_stage="initial",
    )
    final_state_summaries = wave_run.export_state_summaries(
        state_stage="final",
    )
    shared_trace_values = wave_run.export_readout_trace_values(
        readout_catalog=run_blueprint.readout_catalog,
        sample_count=int(runtime.timebase.sample_count),
    )
    final_snapshot = _build_surface_wave_snapshot(
        lifecycle_stage="finalized",
        completed_steps=int(runtime.timebase.sample_count),
        current_time_ms=float(
            runtime.timebase.time_ms_after_steps(runtime.timebase.sample_count)
        ),
        wave_run=wave_run,
        summary=wave_run.shared_readout_history[-1],
        readout_catalog=run_blueprint.readout_catalog,
        state_summaries=final_state_summaries,
        exogenous_drive=last_drive_vector,
        recurrent_input=np.zeros(len(runtime.root_ids), dtype=np.float64),
        dt_ms=float(runtime.timebase.dt_ms),
    )
    result = SimulationRunResult(
        runtime_version=str(runtime.execution_version),
        run_blueprint=run_blueprint,
        initial_snapshot=_build_surface_wave_snapshot(
            lifecycle_stage="initialized",
            completed_steps=0,
            current_time_ms=float(runtime.timebase.time_origin_ms),
            wave_run=wave_run,
            summary=wave_run.shared_readout_history[0],
            readout_catalog=run_blueprint.readout_catalog,
            state_summaries=initial_state_summaries,
            exogenous_drive=np.zeros(len(runtime.root_ids), dtype=np.float64),
            recurrent_input=np.zeros(len(runtime.root_ids), dtype=np.float64),
            dt_ms=float(runtime.timebase.dt_ms),
        ),
        final_snapshot=final_snapshot,
        readout_traces=SimulationReadoutTraces(
            time_ms=np.asarray(runtime.timebase.sample_times_ms(), dtype=np.float64),
            readout_ids=run_blueprint.readout_id_order,
            values=shared_trace_values,
            captured_sample_count=int(runtime.timebase.sample_count),
        ),
    )
    state_summary_rows = [row.as_record() for row in final_state_summaries]
    return {
        "result": result,
        "state_summary_rows": state_summary_rows,
        "structured_log_records": _build_surface_wave_structured_log_records(
            wave_run=wave_run,
            run_blueprint=run_blueprint,
            drive_schedule=drive_schedule,
            state_summary_row_count=len(state_summary_rows),
        ),
        "surface_wave_artifacts": build_surface_wave_execution_artifacts(
            workflow_version=SIMULATOR_MANIFEST_EXECUTION_VERSION,
            arm_plan=arm_plan,
            runtime=runtime,
            wave_run=wave_run,
            canonical_input_stream=canonical_input_stream,
            drive_schedule=drive_schedule,
            run_blueprint=run_blueprint,
            result=result,
            state_summary_rows=state_summary_rows,
        ),
    }


def _build_surface_wave_run_blueprint(
    *,
    arm_plan: Mapping[str, Any],
    runtime: Any,
    canonical_input_stream: Any,
    drive_schedule: Any,
) -> Any:
    runtime_config = _require_mapping(arm_plan.get("runtime"), field_name="arm_plan.runtime")
    selection = _require_mapping(arm_plan.get("selection"), field_name="arm_plan.selection")
    result_bundle_reference: Mapping[str, Any] | None = None
    result_bundle = arm_plan.get("result_bundle")
    if isinstance(result_bundle, Mapping):
        reference = result_bundle.get("reference")
        if isinstance(reference, Mapping):
            result_bundle_reference = reference
    metadata = {
        "execution_version": str(runtime.execution_version),
        "runtime_config_version": runtime_config.get("config_version"),
        "time_unit": runtime_config.get("time_unit"),
        "selected_root_ids_hash": _stable_hash(list(selection.get("selected_root_ids", []))),
        "canonical_input": {
            "input_kind": canonical_input_stream.input_kind,
            "bundle_id": canonical_input_stream.bundle_id,
            "metadata_path": str(canonical_input_stream.metadata_path),
            "replay_source": canonical_input_stream.replay_source,
            "unit_count": canonical_input_stream.unit_count,
            "neutral_value": canonical_input_stream.neutral_value,
            "binding_strategy": drive_schedule.strategy,
            "drive_schedule_hash": drive_schedule.drive_schedule_hash,
        },
        "surface_wave_input_binding": {
            "injection_strategy": SURFACE_WAVE_INPUT_BINDING_STRATEGY,
            "shared_output_timestep_ms": float(
                runtime.descriptor.solver_metadata["shared_output_timestep_ms"]
            ),
            "integration_timestep_ms": float(
                runtime.descriptor.solver_metadata["integration_timestep_ms"]
            ),
            "internal_substep_count": int(
                runtime.descriptor.solver_metadata["internal_substep_count"]
            ),
        },
        "surface_wave_model": {
            "model_family": runtime.descriptor.model_metadata["model_family"],
            "parameter_hash": runtime.descriptor.model_metadata["parameter_hash"],
            "solver_family": runtime.descriptor.model_metadata["solver_family"],
            "surface_wave_reference": copy.deepcopy(
                runtime.descriptor.model_metadata.get("surface_wave_reference")
            ),
        },
        "surface_wave_hybrid_morphology": copy.deepcopy(runtime.descriptor.hybrid_morphology),
        "recurrent_coupling": copy.deepcopy(runtime.descriptor.coupling_metadata),
        "morphology_runtime": runtime.descriptor.as_mapping(),
    }
    return build_simulation_run_blueprint(
        manifest_reference=_require_mapping(
            arm_plan.get("manifest_reference"),
            field_name="arm_plan.manifest_reference",
        ),
        arm_reference=_require_mapping(
            arm_plan.get("arm_reference"),
            field_name="arm_plan.arm_reference",
        ),
        root_ids=runtime.root_ids,
        timebase=runtime.timebase,
        determinism=_require_mapping(
            arm_plan.get("determinism"),
            field_name="arm_plan.determinism",
        ),
        readout_catalog=_require_sequence(
            runtime_config.get("shared_readout_catalog", runtime_config.get("readout_catalog")),
            field_name="arm_plan.runtime.shared_readout_catalog",
        ),
        result_bundle_reference=result_bundle_reference,
        metadata=metadata,
    )


def _build_surface_wave_snapshot(
    *,
    lifecycle_stage: str,
    completed_steps: int,
    current_time_ms: float,
    wave_run: Any,
    summary: Mapping[str, Any],
    readout_catalog: Sequence[Any],
    state_summaries: Sequence[Any],
    exogenous_drive: np.ndarray,
    recurrent_input: np.ndarray,
    dt_ms: float,
) -> SimulationSnapshot:
    dynamic_state = wave_run.export_dynamic_state_vector(summary=summary)
    readout_values = wave_run.export_readout_values(
        summary=summary,
        readout_catalog=readout_catalog,
    )
    return SimulationSnapshot(
        lifecycle_stage=lifecycle_stage,
        completed_steps=int(completed_steps),
        current_time_ms=float(current_time_ms),
        dt_ms=float(dt_ms),
        root_ids=tuple(int(root_id) for root_id in wave_run.root_ids),
        dynamic_state=dynamic_state,
        exogenous_drive=np.asarray(exogenous_drive, dtype=np.float64),
        recurrent_input=np.asarray(recurrent_input, dtype=np.float64),
        readout_state=dynamic_state.copy(),
        readout_ids=tuple(definition.readout_id for definition in readout_catalog),
        readout_values=readout_values,
        state_summaries=tuple(state_summaries),
    )


def _build_surface_wave_structured_log_records(
    *,
    wave_run: Any,
    run_blueprint: Any,
    drive_schedule: Any,
    state_summary_row_count: int,
) -> list[dict[str, Any]]:
    zero_drive = np.zeros(len(run_blueprint.root_ids), dtype=np.float64)
    records = [
        _surface_wave_structured_log_record(
            event_index=0,
            event_type="initialized",
            wave_run=wave_run,
            summary=wave_run.shared_readout_history[0],
            readout_catalog=run_blueprint.readout_catalog,
            drive_vector=zero_drive,
            sample_count=int(run_blueprint.timebase.sample_count),
            dt_ms=float(run_blueprint.timebase.dt_ms),
            state_summary_row_count=state_summary_row_count,
        )
    ]
    for step_index in range(int(run_blueprint.timebase.sample_count)):
        records.append(
            _surface_wave_structured_log_record(
                event_index=len(records),
                event_type="step_completed",
                wave_run=wave_run,
                summary=wave_run.shared_readout_history[step_index + 1],
                readout_catalog=run_blueprint.readout_catalog,
                drive_vector=np.asarray(
                    drive_schedule.drive_values[step_index],
                    dtype=np.float64,
                ),
                sample_count=int(run_blueprint.timebase.sample_count),
                dt_ms=float(run_blueprint.timebase.dt_ms),
                state_summary_row_count=state_summary_row_count,
            )
        )
    records.append(
        _surface_wave_structured_log_record(
            event_index=len(records),
            event_type="finalized",
            wave_run=wave_run,
            summary=wave_run.shared_readout_history[-1],
            readout_catalog=run_blueprint.readout_catalog,
            drive_vector=(
                np.asarray(drive_schedule.drive_values[-1], dtype=np.float64)
                if int(run_blueprint.timebase.sample_count) > 0
                else zero_drive
            ),
            sample_count=int(run_blueprint.timebase.sample_count),
            dt_ms=float(run_blueprint.timebase.dt_ms),
            state_summary_row_count=state_summary_row_count,
        )
    )
    return records


def _surface_wave_structured_log_record(
    *,
    event_index: int,
    event_type: str,
    wave_run: Any,
    summary: Mapping[str, Any],
    readout_catalog: Sequence[Any],
    drive_vector: np.ndarray,
    sample_count: int,
    dt_ms: float,
    state_summary_row_count: int,
) -> dict[str, Any]:
    dynamic_state = wave_run.export_dynamic_state_vector(summary=summary)
    readout_values = _surface_wave_readout_values(
        summary=summary,
        readout_catalog=readout_catalog,
    )
    return {
        "event_index": int(event_index),
        "event_type": event_type,
        "completed_steps": int(summary.get("shared_step_index", 0)),
        "current_time_ms": float(summary["time_ms"]),
        "dt_ms": float(dt_ms),
        "sample_count": int(sample_count),
        "readout_values": {
            definition.readout_id: float(readout_values[index])
            for index, definition in enumerate(readout_catalog)
        },
        "dynamic_state_min": float(np.min(dynamic_state)),
        "dynamic_state_max": float(np.max(dynamic_state)),
        "dynamic_state_mean": float(np.mean(dynamic_state)),
        "exogenous_drive_l2": float(np.linalg.norm(drive_vector)),
        "recurrent_input_l2": 0.0,
        "state_summary_row_count": int(state_summary_row_count),
    }


def _surface_wave_readout_values(
    *,
    summary: Mapping[str, Any],
    readout_catalog: Sequence[Any],
) -> np.ndarray:
    shared_output_mean = float(summary["shared_output_mean"])
    values = []
    for definition in readout_catalog:
        if str(definition.value_semantics) != "shared_downstream_activation":
            raise ValueError(
                "surface-wave manifest execution only supports shared readouts with "
                "value_semantics 'shared_downstream_activation'."
            )
        values.append(shared_output_mean)
    return np.asarray(values, dtype=np.float64)


def _sorted_state_summary_rows(result: SimulationRunResult) -> list[dict[str, Any]]:
    return sorted(
        result.final_snapshot.state_summary_records(),
        key=lambda row: (
            str(row["scope"]),
            str(row["state_id"]),
            str(row["summary_stat"]),
            str(row["units"]),
        ),
    )


def _build_metric_rows(result: SimulationRunResult) -> list[dict[str, Any]]:
    readout_catalog = {
        definition.readout_id: definition
        for definition in result.run_blueprint.readout_catalog
    }
    final_readout_values = result.final_snapshot.readout_mapping()
    trace_time_ms = np.asarray(result.readout_traces.time_ms, dtype=np.float64)
    trace_values = np.asarray(result.readout_traces.values, dtype=np.float64)

    rows: list[dict[str, Any]] = []
    for readout_index, readout_id in enumerate(result.readout_traces.readout_ids):
        definition = readout_catalog[readout_id]
        samples = trace_values[:, readout_index]
        peak_index = int(np.argmax(samples))
        rows.extend(
            [
                _metric_row(
                    metric_id="final_endpoint_value",
                    readout_id=readout_id,
                    scope=str(definition.scope),
                    window_id=FINAL_ENDPOINT_WINDOW_ID,
                    statistic="final",
                    value=float(final_readout_values[readout_id]),
                    units=str(definition.units),
                ),
                _metric_row(
                    metric_id="sample_mean_value",
                    readout_id=readout_id,
                    scope=str(definition.scope),
                    window_id=DECLARED_TIMEBASE_WINDOW_ID,
                    statistic="mean",
                    value=float(np.mean(samples)),
                    units=str(definition.units),
                ),
                _metric_row(
                    metric_id="sample_max_value",
                    readout_id=readout_id,
                    scope=str(definition.scope),
                    window_id=DECLARED_TIMEBASE_WINDOW_ID,
                    statistic="max",
                    value=float(np.max(samples)),
                    units=str(definition.units),
                ),
                _metric_row(
                    metric_id="sample_min_value",
                    readout_id=readout_id,
                    scope=str(definition.scope),
                    window_id=DECLARED_TIMEBASE_WINDOW_ID,
                    statistic="min",
                    value=float(np.min(samples)),
                    units=str(definition.units),
                ),
                _metric_row(
                    metric_id="sample_peak_time_ms",
                    readout_id=readout_id,
                    scope=str(definition.scope),
                    window_id=DECLARED_TIMEBASE_WINDOW_ID,
                    statistic="argmax_time_ms",
                    value=float(trace_time_ms[peak_index]),
                    units="ms",
                ),
            ]
        )
    return sorted(
        rows,
        key=lambda row: (
            str(row["readout_id"]),
            str(row["metric_id"]),
            str(row["window_id"]),
            str(row["statistic"]),
        ),
    )


def _metric_row(
    *,
    metric_id: str,
    readout_id: str,
    scope: str,
    window_id: str,
    statistic: str,
    value: float,
    units: str,
) -> dict[str, Any]:
    return {
        "metric_id": metric_id,
        "readout_id": readout_id,
        "scope": scope,
        "window_id": window_id,
        "statistic": statistic,
        "value": float(value),
        "units": units,
    }


def _normalize_model_mode(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("model_mode must be a non-empty string.")
    normalized = value.strip()
    if normalized not in SUPPORTED_EXECUTABLE_MODEL_MODES:
        raise ValueError(
            "Unsupported executable model_mode "
            f"{normalized!r}. Supported modes: {list(SUPPORTED_EXECUTABLE_MODEL_MODES)!r}."
        )
    return normalized


def _stable_hash(payload: Any) -> str:
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return value


def _require_sequence(value: Any, *, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence.")
    return value


__all__ = [
    "EXECUTION_PROVENANCE_ARTIFACT_ID",
    "ExecutedSimulationArmSummary",
    "MIXED_MORPHOLOGY_STATE_BUNDLE_ARTIFACT_ID",
    "SIMULATOR_EXECUTION_LOG_FORMAT",
    "SIMULATOR_EXECUTION_PROVENANCE_FORMAT",
    "SIMULATOR_MANIFEST_EXECUTION_VERSION",
    "SIMULATOR_UI_COMPARISON_PAYLOAD_FORMAT",
    "STRUCTURED_LOG_ARTIFACT_ID",
    "SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID",
    "SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID",
    "SURFACE_WAVE_SUMMARY_ARTIFACT_ID",
    "UI_COMPARISON_PAYLOAD_ARTIFACT_ID",
    "execute_manifest_simulation",
    "main",
]
