from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
from .io_utils import (
    write_csv_rows,
    write_deterministic_npz,
    write_json,
    write_jsonl,
)
from .simulation_planning import (
    discover_simulation_run_plans,
    resolve_manifest_simulation_plan,
)
from .simulator_result_contract import (
    ASSET_STATUS_READY,
    BASELINE_MODEL_MODE,
    METADATA_JSON_KEY,
    METRIC_TABLE_COLUMNS,
    METRICS_TABLE_KEY,
    MODEL_DIAGNOSTIC_SCOPE,
    MODEL_ARTIFACTS_KEY,
    READOUT_TRACES_KEY,
    SHARED_COMPARISON_SCOPE,
    STATE_SUMMARY_KEY,
    SURFACE_WAVE_MODEL_MODE,
    WAVE_MODEL_EXTENSION_SCOPE,
    build_simulator_extension_artifact_record,
    build_simulator_result_bundle_metadata,
    build_simulator_result_bundle_paths,
    discover_simulator_result_bundle_paths,
    parse_simulator_result_bundle_metadata,
    write_simulator_result_bundle_metadata,
)
from .simulator_runtime import (
    SimulationLifecycleEvent,
    SimulationReadoutDefinition,
    SimulationReadoutTraces,
    SimulationRunResult,
    SimulationSnapshot,
    SimulationStateSummaryRow,
    build_simulation_run_blueprint,
)


SIMULATOR_MANIFEST_EXECUTION_VERSION = "simulator_manifest_execution.v1"
SIMULATOR_EXECUTION_PROVENANCE_FORMAT = "json_simulator_execution_provenance.v1"
SIMULATOR_EXECUTION_LOG_FORMAT = "jsonl_simulator_execution_events.v1"
SIMULATOR_UI_COMPARISON_PAYLOAD_FORMAT = "json_simulator_ui_comparison_payload.v1"
SURFACE_WAVE_SUMMARY_FORMAT = "json_surface_wave_execution_summary.v1"
SURFACE_WAVE_PATCH_TRACES_FORMAT = "npz_surface_wave_patch_traces.v1"
SURFACE_WAVE_COUPLING_EVENTS_FORMAT = "json_surface_wave_coupling_events.v1"

EXECUTION_PROVENANCE_ARTIFACT_ID = "execution_provenance"
STRUCTURED_LOG_ARTIFACT_ID = "structured_log"
UI_COMPARISON_PAYLOAD_ARTIFACT_ID = "ui_comparison_payload"
SURFACE_WAVE_SUMMARY_ARTIFACT_ID = "surface_wave_summary"
SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID = "surface_wave_patch_traces"
SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID = "surface_wave_coupling_events"

FINAL_ENDPOINT_WINDOW_ID = "finalized_endpoint"
DECLARED_TIMEBASE_WINDOW_ID = "declared_timebase"
SURFACE_WAVE_INPUT_BINDING_STRATEGY = SURFACE_WAVE_RUNTIME_SOURCE_INJECTION_STRATEGY
SUPPORTED_EXECUTABLE_MODEL_MODES = (
    BASELINE_MODEL_MODE,
    SURFACE_WAVE_MODEL_MODE,
)


@dataclass(frozen=True)
class ExecutedSimulationArmSummary:
    arm_id: str
    bundle_id: str
    run_spec_hash: str
    bundle_directory: Path
    metadata_path: Path
    state_summary_path: Path
    readout_traces_path: Path
    metrics_table_path: Path
    structured_log_path: Path
    provenance_path: Path
    ui_payload_path: Path
    metric_row_count: int
    state_summary_row_count: int
    structured_log_event_count: int
    highlight_metrics: tuple[dict[str, Any], ...]

    def as_mapping(self) -> dict[str, Any]:
        return {
            "arm_id": self.arm_id,
            "bundle_id": self.bundle_id,
            "run_spec_hash": self.run_spec_hash,
            "bundle_directory": str(self.bundle_directory),
            "metadata_path": str(self.metadata_path),
            "state_summary_path": str(self.state_summary_path),
            "readout_traces_path": str(self.readout_traces_path),
            "metrics_table_path": str(self.metrics_table_path),
            "structured_log_path": str(self.structured_log_path),
            "provenance_path": str(self.provenance_path),
            "ui_payload_path": str(self.ui_payload_path),
            "metric_row_count": self.metric_row_count,
            "state_summary_row_count": self.state_summary_row_count,
            "structured_log_event_count": self.structured_log_event_count,
            "highlight_metrics": [copy.deepcopy(metric) for metric in self.highlight_metrics],
        }


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
) -> dict[str, Any]:
    normalized_model_mode = _normalize_model_mode(model_mode)
    plan = resolve_manifest_simulation_plan(
        manifest_path=manifest_path,
        config_path=config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
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
    parser = argparse.ArgumentParser(
        description=(
            "Resolve a manifest into runnable simulator arms, execute the supported "
            "model mode locally, and write deterministic result bundles."
        )
    )
    parser.add_argument("--config", required=True, help="Path to the runtime config YAML.")
    parser.add_argument("--manifest", required=True, help="Path to the experiment manifest YAML.")
    parser.add_argument("--schema", required=True, help="Path to the manifest schema JSON.")
    parser.add_argument(
        "--design-lock",
        required=True,
        help="Path to the authoritative design-lock YAML.",
    )
    parser.add_argument(
        "--model-mode",
        default=BASELINE_MODEL_MODE,
        help="Simulator model mode to execute. Supported: baseline, surface_wave.",
    )
    parser.add_argument("--arm-id", help="Optional manifest arm_id filter.")
    parser.add_argument(
        "--use-manifest-seed-sweep",
        action="store_true",
        help="Expand the manifest seed sweep into one deterministic run per seed.",
    )
    args = parser.parse_args(argv)

    summary = execute_manifest_simulation(
        manifest_path=args.manifest,
        config_path=args.config,
        schema_path=args.schema,
        design_lock_path=args.design_lock,
        model_mode=args.model_mode,
        arm_id=args.arm_id,
        use_manifest_seed_sweep=args.use_manifest_seed_sweep,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


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

    bundle_metadata = _build_ready_bundle_metadata(arm_plan)
    bundle_paths = discover_simulator_result_bundle_paths(bundle_metadata)
    extension_paths = _extension_artifact_paths(bundle_metadata)
    state_summary_rows = _sorted_state_summary_rows(result)
    metrics_rows = _build_metric_rows(result)
    provenance_payload = _build_execution_provenance(
        arm_plan=arm_plan,
        result=result,
        bundle_metadata=bundle_metadata,
        execution_request=execution_request,
        structured_log_event_count=len(recorder.records),
        metric_row_count=len(metrics_rows),
    )
    ui_payload = _build_ui_comparison_payload(
        arm_plan=arm_plan,
        result=result,
        bundle_metadata=bundle_metadata,
        metrics_rows=metrics_rows,
        extension_paths=extension_paths,
    )

    write_json(state_summary_rows, bundle_paths[STATE_SUMMARY_KEY])
    write_deterministic_npz(
        result.readout_traces.as_numpy_archive_payload(),
        bundle_paths[READOUT_TRACES_KEY],
    )
    write_csv_rows(
        fieldnames=METRIC_TABLE_COLUMNS,
        rows=metrics_rows,
        out_path=bundle_paths[METRICS_TABLE_KEY],
    )
    write_jsonl(recorder.records, extension_paths[STRUCTURED_LOG_ARTIFACT_ID])
    write_json(provenance_payload, extension_paths[EXECUTION_PROVENANCE_ARTIFACT_ID])
    write_json(ui_payload, extension_paths[UI_COMPARISON_PAYLOAD_ARTIFACT_ID])
    metadata_path = write_simulator_result_bundle_metadata(bundle_metadata)

    highlight_metrics = tuple(
        metric
        for metric in metrics_rows
        if metric["metric_id"] in {"final_endpoint_value", "sample_max_value", "sample_peak_time_ms"}
    )
    return ExecutedSimulationArmSummary(
        arm_id=str(bundle_metadata["arm_reference"]["arm_id"]),
        bundle_id=str(bundle_metadata["bundle_id"]),
        run_spec_hash=str(bundle_metadata["run_spec_hash"]),
        bundle_directory=Path(bundle_metadata["bundle_layout"]["bundle_directory"]).resolve(),
        metadata_path=metadata_path.resolve(),
        state_summary_path=bundle_paths[STATE_SUMMARY_KEY].resolve(),
        readout_traces_path=bundle_paths[READOUT_TRACES_KEY].resolve(),
        metrics_table_path=bundle_paths[METRICS_TABLE_KEY].resolve(),
        structured_log_path=extension_paths[STRUCTURED_LOG_ARTIFACT_ID].resolve(),
        provenance_path=extension_paths[EXECUTION_PROVENANCE_ARTIFACT_ID].resolve(),
        ui_payload_path=extension_paths[UI_COMPARISON_PAYLOAD_ARTIFACT_ID].resolve(),
        metric_row_count=len(metrics_rows),
        state_summary_row_count=len(state_summary_rows),
        structured_log_event_count=len(recorder.records),
        highlight_metrics=highlight_metrics,
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

    bundle_metadata = _build_ready_bundle_metadata(
        arm_plan,
        extra_artifact_specs=_surface_wave_artifact_specs(),
    )
    bundle_paths = discover_simulator_result_bundle_paths(bundle_metadata)
    extension_paths = _extension_artifact_paths(bundle_metadata)
    result = execution_payload["result"]
    state_summary_rows = execution_payload["state_summary_rows"]
    metrics_rows = _build_metric_rows(result)
    provenance_payload = _build_execution_provenance(
        arm_plan=arm_plan,
        result=result,
        bundle_metadata=bundle_metadata,
        execution_request=execution_request,
        structured_log_event_count=len(execution_payload["structured_log_records"]),
        metric_row_count=len(metrics_rows),
        model_execution=execution_payload["provenance_model_execution"],
    )
    ui_payload = _build_ui_comparison_payload(
        arm_plan=arm_plan,
        result=result,
        bundle_metadata=bundle_metadata,
        metrics_rows=metrics_rows,
        extension_paths=extension_paths,
    )

    write_json(state_summary_rows, bundle_paths[STATE_SUMMARY_KEY])
    write_deterministic_npz(
        result.readout_traces.as_numpy_archive_payload(),
        bundle_paths[READOUT_TRACES_KEY],
    )
    write_csv_rows(
        fieldnames=METRIC_TABLE_COLUMNS,
        rows=metrics_rows,
        out_path=bundle_paths[METRICS_TABLE_KEY],
    )
    write_jsonl(
        execution_payload["structured_log_records"],
        extension_paths[STRUCTURED_LOG_ARTIFACT_ID],
    )
    write_json(provenance_payload, extension_paths[EXECUTION_PROVENANCE_ARTIFACT_ID])
    write_json(ui_payload, extension_paths[UI_COMPARISON_PAYLOAD_ARTIFACT_ID])
    write_json(
        execution_payload["surface_wave_summary_payload"],
        extension_paths[SURFACE_WAVE_SUMMARY_ARTIFACT_ID],
    )
    write_deterministic_npz(
        execution_payload["surface_wave_patch_trace_payload"],
        extension_paths[SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID],
    )
    write_json(
        execution_payload["surface_wave_coupling_payload"],
        extension_paths[SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID],
    )
    metadata_path = write_simulator_result_bundle_metadata(bundle_metadata)

    highlight_metrics = tuple(
        metric
        for metric in metrics_rows
        if metric["metric_id"] in {"final_endpoint_value", "sample_max_value", "sample_peak_time_ms"}
    )
    return ExecutedSimulationArmSummary(
        arm_id=str(bundle_metadata["arm_reference"]["arm_id"]),
        bundle_id=str(bundle_metadata["bundle_id"]),
        run_spec_hash=str(bundle_metadata["run_spec_hash"]),
        bundle_directory=Path(bundle_metadata["bundle_layout"]["bundle_directory"]).resolve(),
        metadata_path=metadata_path.resolve(),
        state_summary_path=bundle_paths[STATE_SUMMARY_KEY].resolve(),
        readout_traces_path=bundle_paths[READOUT_TRACES_KEY].resolve(),
        metrics_table_path=bundle_paths[METRICS_TABLE_KEY].resolve(),
        structured_log_path=extension_paths[STRUCTURED_LOG_ARTIFACT_ID].resolve(),
        provenance_path=extension_paths[EXECUTION_PROVENANCE_ARTIFACT_ID].resolve(),
        ui_payload_path=extension_paths[UI_COMPARISON_PAYLOAD_ARTIFACT_ID].resolve(),
        metric_row_count=len(metrics_rows),
        state_summary_row_count=len(state_summary_rows),
        structured_log_event_count=len(execution_payload["structured_log_records"]),
        highlight_metrics=highlight_metrics,
    )


def _build_ready_bundle_metadata(
    arm_plan: Mapping[str, Any],
    *,
    extra_artifact_specs: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    base_metadata = _resolve_bundle_metadata(arm_plan)
    runtime = _require_mapping(arm_plan.get("runtime"), field_name="arm_plan.runtime")
    bundle_paths = build_simulator_result_bundle_paths(
        experiment_id=base_metadata["manifest_reference"]["experiment_id"],
        arm_id=base_metadata["arm_reference"]["arm_id"],
        run_spec_hash=base_metadata["run_spec_hash"],
        processed_simulator_results_dir=_resolve_processed_simulator_results_dir(
            runtime=runtime,
            base_metadata=base_metadata,
        ),
    )
    artifact_specs = list(_default_extension_artifact_specs()) + [
        copy.deepcopy(dict(spec))
        for spec in extra_artifact_specs
    ]
    execution_artifacts = [
        build_simulator_extension_artifact_record(
            bundle_paths=bundle_paths,
            artifact_id=spec["artifact_id"],
            file_name=spec["file_name"],
            format=spec["format"],
            status=spec.get("status", ASSET_STATUS_READY),
            artifact_scope=spec["artifact_scope"],
            description=spec["description"],
        )
        for spec in artifact_specs
    ]

    updated = copy.deepcopy(base_metadata)
    updated["artifacts"][STATE_SUMMARY_KEY]["status"] = ASSET_STATUS_READY
    updated["artifacts"][READOUT_TRACES_KEY]["status"] = ASSET_STATUS_READY
    updated["artifacts"][METRICS_TABLE_KEY]["status"] = ASSET_STATUS_READY
    updated["artifacts"][MODEL_ARTIFACTS_KEY] = _merge_model_artifacts(
        existing=updated["artifacts"].get(MODEL_ARTIFACTS_KEY, []),
        additions=execution_artifacts,
    )
    return parse_simulator_result_bundle_metadata(updated)


def _resolve_bundle_metadata(arm_plan: Mapping[str, Any]) -> dict[str, Any]:
    result_bundle = arm_plan.get("result_bundle")
    if isinstance(result_bundle, Mapping):
        metadata = result_bundle.get("metadata")
        if isinstance(metadata, Mapping):
            return parse_simulator_result_bundle_metadata(metadata)

    runtime = _require_mapping(arm_plan.get("runtime"), field_name="arm_plan.runtime")
    return build_simulator_result_bundle_metadata(
        manifest_reference=_require_mapping(
            arm_plan.get("manifest_reference"),
            field_name="arm_plan.manifest_reference",
        ),
        arm_reference=_require_mapping(
            arm_plan.get("arm_reference"),
            field_name="arm_plan.arm_reference",
        ),
        determinism=_require_mapping(
            arm_plan.get("determinism"),
            field_name="arm_plan.determinism",
        ),
        timebase=_require_mapping(runtime.get("timebase"), field_name="arm_plan.runtime.timebase"),
        selected_assets=_require_sequence(
            arm_plan.get("selected_assets"),
            field_name="arm_plan.selected_assets",
        ),
        readout_catalog=_require_sequence(
            runtime.get("shared_readout_catalog", runtime.get("readout_catalog")),
            field_name="arm_plan.runtime.shared_readout_catalog",
        ),
        processed_simulator_results_dir=_resolve_processed_simulator_results_dir(
            runtime=runtime,
            base_metadata=None,
        ),
    )


def _resolve_processed_simulator_results_dir(
    *,
    runtime: Mapping[str, Any],
    base_metadata: Mapping[str, Any] | None,
) -> Path:
    configured_dir = runtime.get("processed_simulator_results_dir")
    if isinstance(configured_dir, str) and configured_dir:
        return Path(configured_dir).resolve()
    if base_metadata is not None:
        bundle_directory = Path(base_metadata["bundle_layout"]["bundle_directory"]).resolve()
        return bundle_directory.parents[3]
    raise ValueError(
        "arm_plan.runtime.processed_simulator_results_dir is required when result_bundle metadata "
        "is not already available."
    )


def _merge_model_artifacts(
    *,
    existing: Sequence[Mapping[str, Any]],
    additions: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    merged = {
        str(item["artifact_id"]): copy.deepcopy(dict(item))
        for item in existing
        if isinstance(item, Mapping) and item.get("artifact_id") is not None
    }
    for item in additions:
        merged[str(item["artifact_id"])] = copy.deepcopy(dict(item))
    return [
        merged[artifact_id]
        for artifact_id in sorted(merged)
    ]


def _default_extension_artifact_specs() -> tuple[dict[str, Any], ...]:
    return (
        {
            "artifact_id": STRUCTURED_LOG_ARTIFACT_ID,
            "file_name": "structured_log.jsonl",
            "format": SIMULATOR_EXECUTION_LOG_FORMAT,
            "artifact_scope": MODEL_DIAGNOSTIC_SCOPE,
            "description": "Deterministic lifecycle event log for local simulator replay audits.",
        },
        {
            "artifact_id": EXECUTION_PROVENANCE_ARTIFACT_ID,
            "file_name": "execution_provenance.json",
            "format": SIMULATOR_EXECUTION_PROVENANCE_FORMAT,
            "artifact_scope": MODEL_DIAGNOSTIC_SCOPE,
            "description": "Stable provenance snapshot for the executed simulator arm and bundle.",
        },
        {
            "artifact_id": UI_COMPARISON_PAYLOAD_ARTIFACT_ID,
            "file_name": "ui_comparison_payload.json",
            "format": SIMULATOR_UI_COMPARISON_PAYLOAD_FORMAT,
            "artifact_scope": SHARED_COMPARISON_SCOPE,
            "description": "UI-facing comparison handoff payload discovered from the result bundle inventory.",
        },
    )


def _surface_wave_artifact_specs() -> tuple[dict[str, Any], ...]:
    return (
        {
            "artifact_id": SURFACE_WAVE_SUMMARY_ARTIFACT_ID,
            "file_name": "surface_wave_summary.json",
            "format": SURFACE_WAVE_SUMMARY_FORMAT,
            "artifact_scope": WAVE_MODEL_EXTENSION_SCOPE,
            "description": "Wave-specific execution summary with solver, input-binding, and morphology-state metadata.",
        },
        {
            "artifact_id": SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID,
            "file_name": "surface_wave_patch_traces.npz",
            "format": SURFACE_WAVE_PATCH_TRACES_FORMAT,
            "artifact_scope": WAVE_MODEL_EXTENSION_SCOPE,
            "description": "Morphology-resolved patch activation traces written on the internal wave-solver timebase.",
        },
        {
            "artifact_id": SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID,
            "file_name": "surface_wave_coupling_events.json",
            "format": SURFACE_WAVE_COUPLING_EVENTS_FORMAT,
            "artifact_scope": WAVE_MODEL_EXTENSION_SCOPE,
            "description": "Deterministic surface-wave coupling event history for morphology-resolved replay audits.",
        },
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
    final_state_summary_rows = [row.as_record() for row in final_state_summaries]
    return {
        "result": result,
        "state_summary_rows": final_state_summary_rows,
        "structured_log_records": _build_surface_wave_structured_log_records(
            wave_run=wave_run,
            run_blueprint=run_blueprint,
            drive_schedule=drive_schedule,
            state_summary_row_count=len(final_state_summary_rows),
        ),
        "surface_wave_summary_payload": _build_surface_wave_summary_payload(
            arm_plan=arm_plan,
            runtime=runtime,
            wave_run=wave_run,
            canonical_input_stream=canonical_input_stream,
            drive_schedule=drive_schedule,
            run_blueprint=run_blueprint,
            state_summary_rows=final_state_summary_rows,
        ),
        "surface_wave_patch_trace_payload": wave_run.export_projection_trace_payload(),
        "surface_wave_coupling_payload": {
            "format_version": SURFACE_WAVE_COUPLING_EVENTS_FORMAT,
            "workflow_version": SIMULATOR_MANIFEST_EXECUTION_VERSION,
            "event_count": len(wave_run.coupling_application_history),
            "events": [copy.deepcopy(item) for item in wave_run.coupling_application_history],
        },
        "provenance_model_execution": {
            "model_mode": SURFACE_WAVE_MODEL_MODE,
            "surface_wave_reference": copy.deepcopy(
                runtime.descriptor.model_metadata.get("surface_wave_reference")
            ),
            "hybrid_morphology": copy.deepcopy(
                runtime.descriptor.hybrid_morphology
            ),
            "morphology_runtime": runtime.descriptor.as_mapping(),
            "input_binding_strategy": SURFACE_WAVE_INPUT_BINDING_STRATEGY,
            "drive_schedule_hash": str(drive_schedule.drive_schedule_hash),
            "solver": copy.deepcopy(runtime.descriptor.solver_metadata),
            "coupling": copy.deepcopy(runtime.descriptor.coupling_metadata),
            "wave_specific_artifacts": [
                SURFACE_WAVE_SUMMARY_ARTIFACT_ID,
                SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID,
                SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID,
            ],
        },
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


def _build_surface_wave_trace_values(
    *,
    shared_readout_history: Sequence[Mapping[str, Any]],
    run_blueprint: Any,
    sample_count: int,
) -> np.ndarray:
    if len(shared_readout_history) < sample_count:
        raise ValueError("surface-wave shared_readout_history is shorter than the declared sample_count.")
    values = np.empty(
        (sample_count, len(run_blueprint.readout_catalog)),
        dtype=np.float64,
    )
    for sample_index in range(sample_count):
        values[sample_index, :] = _surface_wave_readout_values(
            summary=shared_readout_history[sample_index],
            readout_catalog=run_blueprint.readout_catalog,
        )
    return values


def _build_surface_wave_snapshot(
    *,
    lifecycle_stage: str,
    completed_steps: int,
    current_time_ms: float,
    wave_run: Any,
    summary: Mapping[str, Any],
    readout_catalog: Sequence[Any],
    state_summaries: Sequence[SimulationStateSummaryRow],
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


def _build_surface_wave_state_summaries(
    *,
    root_ids: Sequence[int],
    states_by_root: Mapping[int, Mapping[str, Any]],
    patch_state_by_root: Mapping[int, np.ndarray],
) -> tuple[SimulationStateSummaryRow, ...]:
    rows: list[SimulationStateSummaryRow] = []
    all_activation: list[np.ndarray] = []
    all_velocity: list[np.ndarray] = []
    all_patch_activation: list[np.ndarray] = []

    for root_id in root_ids:
        state_mapping = _require_mapping(
            states_by_root[int(root_id)],
            field_name=f"states_by_root[{root_id}]",
        )
        activation = np.asarray(state_mapping["activation"], dtype=np.float64)
        velocity = np.asarray(state_mapping["velocity"], dtype=np.float64)
        patch_activation = np.asarray(patch_state_by_root[int(root_id)], dtype=np.float64)
        all_activation.append(activation)
        all_velocity.append(velocity)
        all_patch_activation.append(patch_activation)

        rows.extend(
            [
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_surface_activation_state",
                    scope="root_state",
                    summary_stat="mean",
                    value=float(np.mean(activation)),
                    units="activation_au",
                ),
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_surface_activation_state",
                    scope="root_state",
                    summary_stat="min",
                    value=float(np.min(activation)),
                    units="activation_au",
                ),
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_surface_activation_state",
                    scope="root_state",
                    summary_stat="max",
                    value=float(np.max(activation)),
                    units="activation_au",
                ),
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_surface_velocity_state",
                    scope="root_state",
                    summary_stat="mean",
                    value=float(np.mean(velocity)),
                    units="activation_au_per_ms",
                ),
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_surface_velocity_state",
                    scope="root_state",
                    summary_stat="min",
                    value=float(np.min(velocity)),
                    units="activation_au_per_ms",
                ),
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_surface_velocity_state",
                    scope="root_state",
                    summary_stat="max",
                    value=float(np.max(velocity)),
                    units="activation_au_per_ms",
                ),
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_patch_activation_state",
                    scope="root_state",
                    summary_stat="mean",
                    value=float(np.mean(patch_activation)),
                    units="activation_au",
                ),
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_patch_activation_state",
                    scope="root_state",
                    summary_stat="min",
                    value=float(np.min(patch_activation)),
                    units="activation_au",
                ),
                _state_summary_row(
                    state_id=f"root_{int(root_id)}_patch_activation_state",
                    scope="root_state",
                    summary_stat="max",
                    value=float(np.max(patch_activation)),
                    units="activation_au",
                ),
            ]
        )

        recovery = state_mapping.get("recovery")
        if recovery is not None:
            recovery_values = np.asarray(recovery, dtype=np.float64)
            rows.extend(
                [
                    _state_summary_row(
                        state_id=f"root_{int(root_id)}_recovery_state",
                        scope="root_state",
                        summary_stat="mean",
                        value=float(np.mean(recovery_values)),
                        units="unitless",
                    ),
                    _state_summary_row(
                        state_id=f"root_{int(root_id)}_recovery_state",
                        scope="root_state",
                        summary_stat="max",
                        value=float(np.max(recovery_values)),
                        units="unitless",
                    ),
                ]
            )

    circuit_activation = np.concatenate(all_activation)
    circuit_velocity = np.concatenate(all_velocity)
    circuit_patch_activation = np.concatenate(all_patch_activation)
    rows.extend(
        [
            _state_summary_row(
                state_id="circuit_surface_activation_state",
                scope="circuit_state",
                summary_stat="mean",
                value=float(np.mean(circuit_activation)),
                units="activation_au",
            ),
            _state_summary_row(
                state_id="circuit_surface_activation_state",
                scope="circuit_state",
                summary_stat="min",
                value=float(np.min(circuit_activation)),
                units="activation_au",
            ),
            _state_summary_row(
                state_id="circuit_surface_activation_state",
                scope="circuit_state",
                summary_stat="max",
                value=float(np.max(circuit_activation)),
                units="activation_au",
            ),
            _state_summary_row(
                state_id="circuit_surface_velocity_state",
                scope="circuit_state",
                summary_stat="mean",
                value=float(np.mean(circuit_velocity)),
                units="activation_au_per_ms",
            ),
            _state_summary_row(
                state_id="circuit_surface_velocity_state",
                scope="circuit_state",
                summary_stat="min",
                value=float(np.min(circuit_velocity)),
                units="activation_au_per_ms",
            ),
            _state_summary_row(
                state_id="circuit_surface_velocity_state",
                scope="circuit_state",
                summary_stat="max",
                value=float(np.max(circuit_velocity)),
                units="activation_au_per_ms",
            ),
            _state_summary_row(
                state_id="circuit_patch_activation_state",
                scope="circuit_state",
                summary_stat="mean",
                value=float(np.mean(circuit_patch_activation)),
                units="activation_au",
            ),
            _state_summary_row(
                state_id="circuit_patch_activation_state",
                scope="circuit_state",
                summary_stat="min",
                value=float(np.min(circuit_patch_activation)),
                units="activation_au",
            ),
            _state_summary_row(
                state_id="circuit_patch_activation_state",
                scope="circuit_state",
                summary_stat="max",
                value=float(np.max(circuit_patch_activation)),
                units="activation_au",
            ),
        ]
    )
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.scope,
                row.state_id,
                row.summary_stat,
                row.units,
            ),
        )
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
    readout_values = wave_run.export_readout_values(
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


def _build_surface_wave_summary_payload(
    *,
    arm_plan: Mapping[str, Any],
    runtime: Any,
    wave_run: Any,
    canonical_input_stream: Any,
    drive_schedule: Any,
    run_blueprint: Any,
    state_summary_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "format_version": SURFACE_WAVE_SUMMARY_FORMAT,
        "workflow_version": SIMULATOR_MANIFEST_EXECUTION_VERSION,
        "manifest_reference": copy.deepcopy(run_blueprint.manifest_reference),
        "arm_reference": copy.deepcopy(run_blueprint.arm_reference),
        "bundle_reference": copy.deepcopy(run_blueprint.result_bundle_reference),
        "surface_wave_reference": copy.deepcopy(
            runtime.descriptor.model_metadata.get("surface_wave_reference")
        ),
        "hybrid_morphology": copy.deepcopy(runtime.descriptor.hybrid_morphology),
        "morphology_runtime": runtime.descriptor.as_mapping(),
        "canonical_input": {
            "input_kind": canonical_input_stream.input_kind,
            "bundle_id": canonical_input_stream.bundle_id,
            "metadata_path": str(canonical_input_stream.metadata_path),
            "replay_source": canonical_input_stream.replay_source,
            "unit_count": canonical_input_stream.unit_count,
            "binding_strategy": drive_schedule.strategy,
            "drive_schedule_hash": drive_schedule.drive_schedule_hash,
        },
        "input_binding": {
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
        "solver": {
            "integration_timestep_ms": float(
                runtime.descriptor.solver_metadata["integration_timestep_ms"]
            ),
            "shared_output_timestep_ms": float(
                runtime.descriptor.solver_metadata["shared_output_timestep_ms"]
            ),
            "internal_substep_count": int(
                runtime.descriptor.solver_metadata["internal_substep_count"]
            ),
            "substep_count": int(wave_run.substep_count),
            "shared_step_count": int(wave_run.shared_step_count),
        },
        "coupling": {
            **copy.deepcopy(runtime.descriptor.coupling_metadata),
            "coupling_event_count": len(wave_run.coupling_application_history),
        },
        "runtime_metadata_by_root": [copy.deepcopy(item) for item in wave_run.runtime_metadata_by_root],
        "final_state_overview": {
            "shared_output_mean": float(wave_run.shared_readout_history[-1]["shared_output_mean"]),
            "per_root_mean_activation": copy.deepcopy(
                wave_run.shared_readout_history[-1]["per_root_mean_activation"]
            ),
            "per_root_mean_velocity": copy.deepcopy(
                wave_run.shared_readout_history[-1]["per_root_mean_velocity"]
            ),
        },
        "wave_specific_artifacts": {
            "patch_traces_artifact_id": SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID,
            "coupling_events_artifact_id": SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID,
        },
        "state_summary_row_count": len(state_summary_rows),
    }


def _surface_wave_dynamic_state_vector(
    *,
    summary: Mapping[str, Any],
    root_ids: Sequence[int],
) -> np.ndarray:
    per_root_mean_activation = _require_mapping(
        summary.get("per_root_mean_activation"),
        field_name="surface_wave_summary.per_root_mean_activation",
    )
    return np.asarray(
        [
            float(per_root_mean_activation[str(int(root_id))])
            for root_id in root_ids
        ],
        dtype=np.float64,
    )


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


def _surface_wave_reference_from_arm_plan(
    arm_plan: Mapping[str, Any],
) -> dict[str, Any] | None:
    model_configuration = arm_plan.get("model_configuration")
    if isinstance(model_configuration, Mapping):
        reference = model_configuration.get("surface_wave_reference")
        if isinstance(reference, Mapping):
            return copy.deepcopy(dict(reference))
    return None


def _state_summary_row(
    *,
    state_id: str,
    scope: str,
    summary_stat: str,
    value: float,
    units: str,
) -> SimulationStateSummaryRow:
    return SimulationStateSummaryRow(
        state_id=state_id,
        scope=scope,
        summary_stat=summary_stat,
        value=float(value),
        units=units,
    )


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


def _build_execution_provenance(
    *,
    arm_plan: Mapping[str, Any],
    result: SimulationRunResult,
    bundle_metadata: Mapping[str, Any],
    execution_request: Mapping[str, Any],
    structured_log_event_count: int,
    metric_row_count: int,
    model_execution: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    runtime = _require_mapping(arm_plan.get("runtime"), field_name="arm_plan.runtime")
    payload = {
        "format_version": SIMULATOR_EXECUTION_PROVENANCE_FORMAT,
        "workflow_version": SIMULATOR_MANIFEST_EXECUTION_VERSION,
        "execution_request": copy.deepcopy(dict(execution_request)),
        "manifest_reference": copy.deepcopy(bundle_metadata["manifest_reference"]),
        "arm_reference": copy.deepcopy(bundle_metadata["arm_reference"]),
        "bundle_reference": {
            "bundle_id": bundle_metadata["bundle_id"],
            "run_spec_hash": bundle_metadata["run_spec_hash"],
            "bundle_directory": bundle_metadata["bundle_layout"]["bundle_directory"],
        },
        "determinism": copy.deepcopy(bundle_metadata["determinism"]),
        "timebase": copy.deepcopy(bundle_metadata["timebase"]),
        "selected_assets": copy.deepcopy(bundle_metadata["selected_assets"]),
        "comparison_context": {
            "topology_condition": arm_plan.get("topology_condition"),
            "morphology_condition": arm_plan.get("morphology_condition"),
            "primary_metric": arm_plan.get("primary_metric"),
            "companion_metrics": list(arm_plan.get("companion_metrics", [])),
            "must_show_outputs": list(arm_plan.get("must_show_outputs", [])),
            "comparison_tags": list(bundle_metadata["arm_reference"].get("comparison_tags", [])),
        },
        "execution_plan": {
            "seed": int(result.run_blueprint.determinism.seed),
            "selected_root_ids": list(result.run_blueprint.root_ids),
            "readout_ids": list(result.run_blueprint.readout_id_order),
            "arm_plan_hash": _stable_hash(_json_ready(arm_plan)),
            "run_blueprint_metadata": _json_ready(result.run_blueprint.metadata),
            "processed_simulator_results_dir": runtime.get("processed_simulator_results_dir"),
        },
        "artifact_counts": {
            "state_summary_row_count": len(result.state_summaries),
            "readout_sample_count": int(result.readout_traces.captured_sample_count),
            "metric_row_count": int(metric_row_count),
            "structured_log_event_count": int(structured_log_event_count),
        },
    }
    if model_execution is not None:
        payload["model_execution"] = _json_ready(model_execution)
    return payload


def _build_ui_comparison_payload(
    *,
    arm_plan: Mapping[str, Any],
    result: SimulationRunResult,
    bundle_metadata: Mapping[str, Any],
    metrics_rows: Sequence[Mapping[str, Any]],
    extension_paths: Mapping[str, Path],
) -> dict[str, Any]:
    result_paths = discover_simulator_result_bundle_paths(bundle_metadata)
    model_artifacts = sorted(
        [
            copy.deepcopy(dict(artifact))
            for artifact in bundle_metadata["artifacts"].get(MODEL_ARTIFACTS_KEY, [])
        ],
        key=lambda artifact: (
            str(artifact["artifact_scope"]),
            str(artifact["artifact_id"]),
            str(artifact["path"]),
        ),
    )
    readout_summaries = []
    for index, definition in enumerate(result.run_blueprint.readout_catalog):
        metric_cards = [
            copy.deepcopy(dict(row))
            for row in metrics_rows
            if str(row["readout_id"]) == definition.readout_id
        ]
        readout_summaries.append(
            {
                "readout_id": definition.readout_id,
                "trace_index": index,
                "scope": definition.scope,
                "aggregation": definition.aggregation,
                "units": definition.units,
                "value_semantics": definition.value_semantics,
                "description": definition.description,
                "sample_count": int(result.readout_traces.captured_sample_count),
                "sample_start_ms": float(result.readout_traces.time_ms[0]),
                "sample_end_ms": float(result.readout_traces.time_ms[-1]),
                "metric_cards": metric_cards,
            }
        )

    comparison_output_targets = _require_mapping(
        arm_plan.get("comparison_output_targets"),
        field_name="arm_plan.comparison_output_targets",
    )
    declared_views = [
        {
            "output_id": str(item["id"]),
            "target_path": str(item["path"]),
            "target_kind": "plot",
        }
        for item in comparison_output_targets.get("plots", [])
    ]
    declared_views.extend(
        [
            {
                "output_id": str(item["id"]),
                "target_path": str(item["path"]),
                "target_kind": "ui_state",
            }
            for item in comparison_output_targets.get("ui_states", [])
        ]
    )
    declared_views = sorted(
        declared_views,
        key=lambda item: (
            item["target_kind"],
            item["output_id"],
            item["target_path"],
        ),
    )

    return {
        "format_version": SIMULATOR_UI_COMPARISON_PAYLOAD_FORMAT,
        "workflow_version": SIMULATOR_MANIFEST_EXECUTION_VERSION,
        "bundle_reference": {
            "bundle_id": bundle_metadata["bundle_id"],
            "run_spec_hash": bundle_metadata["run_spec_hash"],
            "bundle_directory": bundle_metadata["bundle_layout"]["bundle_directory"],
        },
        "manifest_reference": copy.deepcopy(bundle_metadata["manifest_reference"]),
        "arm_reference": copy.deepcopy(bundle_metadata["arm_reference"]),
        "comparison_context": {
            "topology_condition": arm_plan.get("topology_condition"),
            "morphology_condition": arm_plan.get("morphology_condition"),
            "comparison_tags": list(bundle_metadata["arm_reference"].get("comparison_tags", [])),
            "primary_metric": arm_plan.get("primary_metric"),
            "companion_metrics": list(arm_plan.get("companion_metrics", [])),
            "must_show_outputs": list(arm_plan.get("must_show_outputs", [])),
        },
        "artifact_inventory": [
            {
                "artifact_id": METADATA_JSON_KEY,
                "path": str(result_paths[METADATA_JSON_KEY]),
                "format": bundle_metadata["artifacts"][METADATA_JSON_KEY]["format"],
                "artifact_scope": bundle_metadata["artifacts"][METADATA_JSON_KEY]["artifact_scope"],
            },
            {
                "artifact_id": STATE_SUMMARY_KEY,
                "path": str(result_paths[STATE_SUMMARY_KEY]),
                "format": bundle_metadata["artifacts"][STATE_SUMMARY_KEY]["format"],
                "artifact_scope": bundle_metadata["artifacts"][STATE_SUMMARY_KEY]["artifact_scope"],
            },
            {
                "artifact_id": READOUT_TRACES_KEY,
                "path": str(result_paths[READOUT_TRACES_KEY]),
                "format": bundle_metadata["artifacts"][READOUT_TRACES_KEY]["format"],
                "artifact_scope": bundle_metadata["artifacts"][READOUT_TRACES_KEY]["artifact_scope"],
            },
            {
                "artifact_id": METRICS_TABLE_KEY,
                "path": str(result_paths[METRICS_TABLE_KEY]),
                "format": bundle_metadata["artifacts"][METRICS_TABLE_KEY]["format"],
                "artifact_scope": bundle_metadata["artifacts"][METRICS_TABLE_KEY]["artifact_scope"],
            },
        ]
        + [
            {
                "artifact_id": str(artifact["artifact_id"]),
                "path": str(artifact["path"]),
                "format": str(artifact["format"]),
                "artifact_scope": str(artifact["artifact_scope"]),
            }
            for artifact in model_artifacts
        ],
        "trace_payload": {
            "path": str(result_paths[READOUT_TRACES_KEY]),
            "time_array": "time_ms",
            "readout_ids_array": "readout_ids",
            "values_array": "values",
        },
        "metric_payload": {
            "path": str(result_paths[METRICS_TABLE_KEY]),
            "columns": list(METRIC_TABLE_COLUMNS),
        },
        "state_summary_payload": {
            "path": str(result_paths[STATE_SUMMARY_KEY]),
            "row_count": len(result.state_summaries),
        },
        "readout_summaries": readout_summaries,
        "declared_output_targets": {
            "metrics_json": str(comparison_output_targets["metrics_json"]),
            "summary_table_csv": str(comparison_output_targets["summary_table_csv"]),
            "views": declared_views,
        },
    }


def _extension_artifact_paths(bundle_metadata: Mapping[str, Any]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for artifact in bundle_metadata["artifacts"][MODEL_ARTIFACTS_KEY]:
        paths[str(artifact["artifact_id"])] = Path(str(artifact["path"])).resolve()
    missing_artifacts = {
        STRUCTURED_LOG_ARTIFACT_ID,
        EXECUTION_PROVENANCE_ARTIFACT_ID,
        UI_COMPARISON_PAYLOAD_ARTIFACT_ID,
    } - set(paths)
    if missing_artifacts:
        raise ValueError(
            "Result bundle metadata is missing required execution artifacts: "
            f"{sorted(missing_artifacts)!r}."
        )
    return paths


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


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _json_ready(subvalue)
            for key, subvalue in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, np.ndarray):
        return _json_ready(value.tolist())
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, SimulationReadoutDefinition):
        return _json_ready(value.as_mapping())
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


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
    "SIMULATOR_EXECUTION_LOG_FORMAT",
    "SIMULATOR_EXECUTION_PROVENANCE_FORMAT",
    "SIMULATOR_MANIFEST_EXECUTION_VERSION",
    "SIMULATOR_UI_COMPARISON_PAYLOAD_FORMAT",
    "ExecutedSimulationArmSummary",
    "execute_manifest_simulation",
    "main",
]
