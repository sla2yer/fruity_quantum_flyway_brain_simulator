from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .hybrid_morphology_runtime import (
    SURFACE_WAVE_MORPHOLOGY_RUNTIME_FAMILY,
    SURFACE_WAVE_RUNTIME_SOURCE_INJECTION_STRATEGY,
)
from .io_utils import (
    write_csv_rows,
    write_deterministic_npz,
    write_json,
    write_jsonl,
)
from .simulator_result_contract import (
    ASSET_STATUS_READY,
    METADATA_JSON_KEY,
    METRIC_TABLE_COLUMNS,
    METRICS_TABLE_KEY,
    MODEL_DIAGNOSTIC_SCOPE,
    MODEL_ARTIFACTS_KEY,
    MIXED_MORPHOLOGY_INDEX_FORMAT,
    MIXED_MORPHOLOGY_INDEX_KEY,
    READOUT_TRACES_KEY,
    SHARED_COMPARISON_SCOPE,
    STATE_SUMMARY_KEY,
    WAVE_MODEL_EXTENSION_SCOPE,
    build_simulator_extension_artifact_record,
    build_simulator_result_bundle_paths,
    discover_simulator_result_bundle_paths,
    parse_simulator_result_bundle_metadata,
    write_simulator_result_bundle_metadata,
)
from .simulator_runtime import SimulationReadoutDefinition, SimulationRunResult


SIMULATOR_EXECUTION_PROVENANCE_FORMAT = "json_simulator_execution_provenance.v1"
SIMULATOR_EXECUTION_LOG_FORMAT = "jsonl_simulator_execution_events.v1"
SIMULATOR_UI_COMPARISON_PAYLOAD_FORMAT = "json_simulator_ui_comparison_payload.v1"
SURFACE_WAVE_SUMMARY_FORMAT = "json_surface_wave_execution_summary.v1"
SURFACE_WAVE_PATCH_TRACES_FORMAT = "npz_surface_wave_patch_traces.v1"
SURFACE_WAVE_COUPLING_EVENTS_FORMAT = "json_surface_wave_coupling_events.v1"
MIXED_MORPHOLOGY_STATE_BUNDLE_FORMAT = "json_mixed_morphology_state_bundle.v1"

EXECUTION_PROVENANCE_ARTIFACT_ID = "execution_provenance"
STRUCTURED_LOG_ARTIFACT_ID = "structured_log"
UI_COMPARISON_PAYLOAD_ARTIFACT_ID = "ui_comparison_payload"
SURFACE_WAVE_SUMMARY_ARTIFACT_ID = "surface_wave_summary"
SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID = "surface_wave_patch_traces"
SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID = "surface_wave_coupling_events"
MIXED_MORPHOLOGY_STATE_BUNDLE_ARTIFACT_ID = "mixed_morphology_state_bundle"

FINAL_ENDPOINT_WINDOW_ID = "finalized_endpoint"
DECLARED_TIMEBASE_WINDOW_ID = "declared_timebase"
SURFACE_WAVE_INPUT_BINDING_STRATEGY = SURFACE_WAVE_RUNTIME_SOURCE_INJECTION_STRATEGY


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


@dataclass(frozen=True)
class SurfaceWaveExecutionArtifacts:
    surface_wave_summary_payload: dict[str, Any]
    surface_wave_patch_trace_payload: Mapping[str, np.ndarray]
    mixed_morphology_state_bundle_payload: dict[str, Any]
    surface_wave_coupling_payload: dict[str, Any]
    mixed_morphology_index: dict[str, Any]
    provenance_model_execution: dict[str, Any]


def package_simulation_result(
    *,
    workflow_version: str,
    arm_plan: Mapping[str, Any],
    execution_request: Mapping[str, Any],
    result: SimulationRunResult,
    state_summary_rows: Sequence[Mapping[str, Any]],
    metrics_rows: Sequence[Mapping[str, Any]],
    structured_log_records: Sequence[Mapping[str, Any]],
    model_execution: Mapping[str, Any] | None = None,
    surface_wave_artifacts: SurfaceWaveExecutionArtifacts | None = None,
) -> ExecutedSimulationArmSummary:
    extra_artifact_specs = (
        _surface_wave_artifact_specs()
        if surface_wave_artifacts is not None
        else ()
    )
    bundle_metadata = _build_ready_bundle_metadata(
        arm_plan,
        extra_artifact_specs=extra_artifact_specs,
    )
    if surface_wave_artifacts is not None:
        bundle_metadata = _attach_mixed_morphology_index(
            bundle_metadata,
            mixed_morphology_index=surface_wave_artifacts.mixed_morphology_index,
        )

    bundle_paths = discover_simulator_result_bundle_paths(bundle_metadata)
    extension_paths = _extension_artifact_paths(bundle_metadata)
    structured_log_event_count = len(structured_log_records)
    provenance_payload = _build_execution_provenance(
        workflow_version=workflow_version,
        arm_plan=arm_plan,
        result=result,
        bundle_metadata=bundle_metadata,
        execution_request=execution_request,
        structured_log_event_count=structured_log_event_count,
        metric_row_count=len(metrics_rows),
        model_execution=model_execution,
    )
    ui_payload = _build_ui_comparison_payload(
        workflow_version=workflow_version,
        arm_plan=arm_plan,
        result=result,
        bundle_metadata=bundle_metadata,
        metrics_rows=metrics_rows,
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
    write_jsonl(structured_log_records, extension_paths[STRUCTURED_LOG_ARTIFACT_ID])
    write_json(provenance_payload, extension_paths[EXECUTION_PROVENANCE_ARTIFACT_ID])
    write_json(ui_payload, extension_paths[UI_COMPARISON_PAYLOAD_ARTIFACT_ID])

    if surface_wave_artifacts is not None:
        write_json(
            surface_wave_artifacts.surface_wave_summary_payload,
            extension_paths[SURFACE_WAVE_SUMMARY_ARTIFACT_ID],
        )
        write_deterministic_npz(
            surface_wave_artifacts.surface_wave_patch_trace_payload,
            extension_paths[SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID],
        )
        write_json(
            surface_wave_artifacts.surface_wave_coupling_payload,
            extension_paths[SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID],
        )
        write_json(
            surface_wave_artifacts.mixed_morphology_state_bundle_payload,
            extension_paths[MIXED_MORPHOLOGY_STATE_BUNDLE_ARTIFACT_ID],
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
        structured_log_event_count=structured_log_event_count,
        highlight_metrics=highlight_metrics,
    )


def build_surface_wave_execution_artifacts(
    *,
    workflow_version: str,
    arm_plan: Mapping[str, Any],
    runtime: Any,
    wave_run: Any,
    canonical_input_stream: Any,
    drive_schedule: Any,
    run_blueprint: Any,
    result: SimulationRunResult,
    state_summary_rows: Sequence[Mapping[str, Any]],
) -> SurfaceWaveExecutionArtifacts:
    return SurfaceWaveExecutionArtifacts(
        surface_wave_summary_payload=_build_surface_wave_summary_payload(
            workflow_version=workflow_version,
            runtime=runtime,
            wave_run=wave_run,
            canonical_input_stream=canonical_input_stream,
            drive_schedule=drive_schedule,
            run_blueprint=run_blueprint,
            state_summary_rows=state_summary_rows,
        ),
        surface_wave_patch_trace_payload=wave_run.export_projection_trace_payload(),
        mixed_morphology_state_bundle_payload=_build_mixed_morphology_state_bundle_payload(
            workflow_version=workflow_version,
            runtime=runtime,
            wave_run=wave_run,
            run_blueprint=run_blueprint,
        ),
        surface_wave_coupling_payload={
            "format_version": SURFACE_WAVE_COUPLING_EVENTS_FORMAT,
            "workflow_version": workflow_version,
            "event_count": len(wave_run.coupling_application_history),
            "events": [copy.deepcopy(item) for item in wave_run.coupling_application_history],
        },
        mixed_morphology_index=_build_mixed_morphology_index(
            result=result,
            wave_run=wave_run,
            runtime=runtime,
            state_summary_rows=state_summary_rows,
        ),
        provenance_model_execution={
            "model_mode": str(run_blueprint.arm_reference["model_mode"]),
            "surface_wave_reference": copy.deepcopy(
                runtime.descriptor.model_metadata.get("surface_wave_reference")
            ),
            "hybrid_morphology": copy.deepcopy(runtime.descriptor.hybrid_morphology),
            "morphology_runtime": runtime.descriptor.as_mapping(),
            "input_binding_strategy": SURFACE_WAVE_INPUT_BINDING_STRATEGY,
            "drive_schedule_hash": str(drive_schedule.drive_schedule_hash),
            "solver": copy.deepcopy(runtime.descriptor.solver_metadata),
            "coupling": copy.deepcopy(runtime.descriptor.coupling_metadata),
            "wave_specific_artifacts": [
                SURFACE_WAVE_SUMMARY_ARTIFACT_ID,
                SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID,
                MIXED_MORPHOLOGY_STATE_BUNDLE_ARTIFACT_ID,
                SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID,
            ],
        },
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


def _attach_mixed_morphology_index(
    bundle_metadata: Mapping[str, Any],
    *,
    mixed_morphology_index: Mapping[str, Any],
) -> dict[str, Any]:
    updated = copy.deepcopy(dict(bundle_metadata))
    updated[MIXED_MORPHOLOGY_INDEX_KEY] = copy.deepcopy(dict(mixed_morphology_index))
    return parse_simulator_result_bundle_metadata(updated)


def _resolve_bundle_metadata(arm_plan: Mapping[str, Any]) -> dict[str, Any]:
    result_bundle = _require_mapping(
        arm_plan.get("result_bundle"),
        field_name="arm_plan.result_bundle",
    )
    metadata = result_bundle.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError(
            "arm_plan.result_bundle.metadata is required for manifest execution packaging."
        )
    return parse_simulator_result_bundle_metadata(metadata)


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
            "artifact_id": MIXED_MORPHOLOGY_STATE_BUNDLE_ARTIFACT_ID,
            "file_name": "mixed_morphology_state_bundle.json",
            "format": MIXED_MORPHOLOGY_STATE_BUNDLE_FORMAT,
            "artifact_scope": WAVE_MODEL_EXTENSION_SCOPE,
            "description": "Fidelity-agnostic per-root state exports and runtime metadata for mixed morphology runs.",
        },
        {
            "artifact_id": SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID,
            "file_name": "surface_wave_coupling_events.json",
            "format": SURFACE_WAVE_COUPLING_EVENTS_FORMAT,
            "artifact_scope": WAVE_MODEL_EXTENSION_SCOPE,
            "description": "Deterministic surface-wave coupling event history for morphology-resolved replay audits.",
        },
    )


def _build_execution_provenance(
    *,
    workflow_version: str,
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
        "workflow_version": workflow_version,
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
    workflow_version: str,
    arm_plan: Mapping[str, Any],
    result: SimulationRunResult,
    bundle_metadata: Mapping[str, Any],
    metrics_rows: Sequence[Mapping[str, Any]],
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
        "workflow_version": workflow_version,
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


def _build_surface_wave_summary_payload(
    *,
    workflow_version: str,
    runtime: Any,
    wave_run: Any,
    canonical_input_stream: Any,
    drive_schedule: Any,
    run_blueprint: Any,
    state_summary_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "format_version": SURFACE_WAVE_SUMMARY_FORMAT,
        "workflow_version": workflow_version,
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
            "mixed_state_bundle_artifact_id": MIXED_MORPHOLOGY_STATE_BUNDLE_ARTIFACT_ID,
            "coupling_events_artifact_id": SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID,
        },
        "state_summary_row_count": len(state_summary_rows),
    }


def _build_mixed_morphology_state_bundle_payload(
    *,
    workflow_version: str,
    runtime: Any,
    wave_run: Any,
    run_blueprint: Any,
) -> dict[str, Any]:
    runtime_metadata_by_root = {
        str(int(item["root_id"])): copy.deepcopy(dict(item))
        for item in wave_run.runtime_metadata_by_root
    }
    return {
        "format_version": MIXED_MORPHOLOGY_STATE_BUNDLE_FORMAT,
        "workflow_version": workflow_version,
        "manifest_reference": copy.deepcopy(run_blueprint.manifest_reference),
        "arm_reference": copy.deepcopy(run_blueprint.arm_reference),
        "bundle_reference": copy.deepcopy(run_blueprint.result_bundle_reference),
        "surface_wave_reference": copy.deepcopy(
            runtime.descriptor.model_metadata.get("surface_wave_reference")
        ),
        "hybrid_morphology": copy.deepcopy(runtime.descriptor.hybrid_morphology),
        "morphology_runtime": runtime.descriptor.as_mapping(),
        "root_ids": [int(root_id) for root_id in wave_run.root_ids],
        "runtime_metadata_by_root": runtime_metadata_by_root,
        "initial_state_exports_by_root": {
            str(int(root_id)): copy.deepcopy(state_mapping)
            for root_id, state_mapping in sorted(
                wave_run.initial_state_exports_by_root.items()
            )
        },
        "final_state_exports_by_root": {
            str(int(root_id)): copy.deepcopy(state_mapping)
            for root_id, state_mapping in sorted(
                wave_run.final_state_exports_by_root.items()
            )
        },
    }


def _build_mixed_morphology_index(
    *,
    result: SimulationRunResult,
    wave_run: Any,
    runtime: Any,
    state_summary_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    readout_ids = [
        definition.readout_id
        for definition in result.run_blueprint.readout_catalog
    ]
    root_records = []
    for item in wave_run.runtime_metadata_by_root:
        root_mapping = _require_mapping(
            item,
            field_name="wave_run.runtime_metadata_by_root",
        )
        root_id = int(root_mapping["root_id"])
        morphology_class = str(root_mapping["morphology_class"])
        root_records.append(
            {
                "root_id": root_id,
                "morphology_class": morphology_class,
                "state_bundle_root_key": str(root_id),
                "runtime_metadata_root_key": str(root_id),
                "state_summary_ids": _root_state_summary_ids(
                    root_id=root_id,
                    state_summary_rows=state_summary_rows,
                ),
                "projection_time_array": _projection_time_array_name(runtime=runtime),
                "projection_trace_array": _projection_trace_array_name(
                    root_id=root_id,
                    morphology_class=morphology_class,
                    runtime=runtime,
                ),
                "projection_semantics": _projection_semantics(
                    morphology_class=morphology_class,
                ),
                "shared_readout_ids": list(readout_ids),
            }
        )
    return {
        "format_version": MIXED_MORPHOLOGY_INDEX_FORMAT,
        "state_bundle_artifact_id": MIXED_MORPHOLOGY_STATE_BUNDLE_ARTIFACT_ID,
        "projection_artifact_id": SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID,
        "shared_state_summary_artifact_id": STATE_SUMMARY_KEY,
        "shared_readout_traces_artifact_id": READOUT_TRACES_KEY,
        "roots": root_records,
    }


def _root_state_summary_ids(
    *,
    root_id: int,
    state_summary_rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    state_ids = {
        str(row["state_id"])
        for row in state_summary_rows
        if isinstance(row, Mapping)
        and str(row.get("scope")) == "root_state"
        and str(row.get("state_id", "")).startswith(f"root_{int(root_id)}_")
    }
    return sorted(state_ids)


def _projection_time_array_name(
    *,
    runtime: Any,
) -> str:
    if str(runtime.descriptor.runtime_family) == SURFACE_WAVE_MORPHOLOGY_RUNTIME_FAMILY:
        return "substep_time_ms"
    return "shared_time_ms"


def _projection_trace_array_name(
    *,
    root_id: int,
    morphology_class: str,
    runtime: Any,
) -> str:
    if str(runtime.descriptor.runtime_family) == SURFACE_WAVE_MORPHOLOGY_RUNTIME_FAMILY:
        return f"root_{int(root_id)}_patch_activation"
    if morphology_class == "surface_neuron":
        return f"root_{int(root_id)}_patch_activation"
    if morphology_class == "skeleton_neuron":
        return f"root_{int(root_id)}_skeleton_activation"
    return f"root_{int(root_id)}_point_activation"


def _projection_semantics(
    *,
    morphology_class: str,
) -> str:
    if morphology_class == "surface_neuron":
        return "surface_patch_activation"
    if morphology_class == "skeleton_neuron":
        return "skeleton_projection_activation"
    return "point_projection_activation"


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


__all__ = [
    "DECLARED_TIMEBASE_WINDOW_ID",
    "EXECUTION_PROVENANCE_ARTIFACT_ID",
    "ExecutedSimulationArmSummary",
    "FINAL_ENDPOINT_WINDOW_ID",
    "MIXED_MORPHOLOGY_STATE_BUNDLE_ARTIFACT_ID",
    "MIXED_MORPHOLOGY_STATE_BUNDLE_FORMAT",
    "SIMULATOR_EXECUTION_LOG_FORMAT",
    "SIMULATOR_EXECUTION_PROVENANCE_FORMAT",
    "SIMULATOR_UI_COMPARISON_PAYLOAD_FORMAT",
    "STRUCTURED_LOG_ARTIFACT_ID",
    "SURFACE_WAVE_COUPLING_EVENTS_ARTIFACT_ID",
    "SURFACE_WAVE_COUPLING_EVENTS_FORMAT",
    "SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID",
    "SURFACE_WAVE_PATCH_TRACES_FORMAT",
    "SURFACE_WAVE_SUMMARY_ARTIFACT_ID",
    "SURFACE_WAVE_SUMMARY_FORMAT",
    "SurfaceWaveExecutionArtifacts",
    "UI_COMPARISON_PAYLOAD_ARTIFACT_ID",
    "build_surface_wave_execution_artifacts",
    "package_simulation_result",
]
