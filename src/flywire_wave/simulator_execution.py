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

from .baseline_execution import resolve_baseline_execution_plan_from_arm_plan
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
    SimulationRunResult,
)


SIMULATOR_MANIFEST_EXECUTION_VERSION = "simulator_manifest_execution.v1"
SIMULATOR_EXECUTION_PROVENANCE_FORMAT = "json_simulator_execution_provenance.v1"
SIMULATOR_EXECUTION_LOG_FORMAT = "jsonl_simulator_execution_events.v1"
SIMULATOR_UI_COMPARISON_PAYLOAD_FORMAT = "json_simulator_ui_comparison_payload.v1"

EXECUTION_PROVENANCE_ARTIFACT_ID = "execution_provenance"
STRUCTURED_LOG_ARTIFACT_ID = "structured_log"
UI_COMPARISON_PAYLOAD_ARTIFACT_ID = "ui_comparison_payload"

FINAL_ENDPOINT_WINDOW_ID = "finalized_endpoint"
DECLARED_TIMEBASE_WINDOW_ID = "declared_timebase"
SUPPORTED_EXECUTABLE_MODEL_MODES = (BASELINE_MODEL_MODE,)


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
        help="Simulator model mode to execute. Baseline is currently supported.",
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


def _build_ready_bundle_metadata(arm_plan: Mapping[str, Any]) -> dict[str, Any]:
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
    execution_artifacts = [
        build_simulator_extension_artifact_record(
            bundle_paths=bundle_paths,
            artifact_id=STRUCTURED_LOG_ARTIFACT_ID,
            file_name="structured_log.jsonl",
            format=SIMULATOR_EXECUTION_LOG_FORMAT,
            status=ASSET_STATUS_READY,
            artifact_scope=MODEL_DIAGNOSTIC_SCOPE,
            description="Deterministic lifecycle event log for local simulator replay audits.",
        ),
        build_simulator_extension_artifact_record(
            bundle_paths=bundle_paths,
            artifact_id=EXECUTION_PROVENANCE_ARTIFACT_ID,
            file_name="execution_provenance.json",
            format=SIMULATOR_EXECUTION_PROVENANCE_FORMAT,
            status=ASSET_STATUS_READY,
            artifact_scope=MODEL_DIAGNOSTIC_SCOPE,
            description="Stable provenance snapshot for the executed simulator arm and bundle.",
        ),
        build_simulator_extension_artifact_record(
            bundle_paths=bundle_paths,
            artifact_id=UI_COMPARISON_PAYLOAD_ARTIFACT_ID,
            file_name="ui_comparison_payload.json",
            format=SIMULATOR_UI_COMPARISON_PAYLOAD_FORMAT,
            status=ASSET_STATUS_READY,
            artifact_scope=SHARED_COMPARISON_SCOPE,
            description="UI-facing comparison handoff payload discovered from the result bundle inventory.",
        ),
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
) -> dict[str, Any]:
    runtime = _require_mapping(arm_plan.get("runtime"), field_name="arm_plan.runtime")
    return {
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


def _build_ui_comparison_payload(
    *,
    arm_plan: Mapping[str, Any],
    result: SimulationRunResult,
    bundle_metadata: Mapping[str, Any],
    metrics_rows: Sequence[Mapping[str, Any]],
    extension_paths: Mapping[str, Path],
) -> dict[str, Any]:
    result_paths = discover_simulator_result_bundle_paths(bundle_metadata)
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
            {
                "artifact_id": STRUCTURED_LOG_ARTIFACT_ID,
                "path": str(extension_paths[STRUCTURED_LOG_ARTIFACT_ID]),
                "format": SIMULATOR_EXECUTION_LOG_FORMAT,
                "artifact_scope": MODEL_DIAGNOSTIC_SCOPE,
            },
            {
                "artifact_id": EXECUTION_PROVENANCE_ARTIFACT_ID,
                "path": str(extension_paths[EXECUTION_PROVENANCE_ARTIFACT_ID]),
                "format": SIMULATOR_EXECUTION_PROVENANCE_FORMAT,
                "artifact_scope": MODEL_DIAGNOSTIC_SCOPE,
            },
            {
                "artifact_id": UI_COMPARISON_PAYLOAD_ARTIFACT_ID,
                "path": str(extension_paths[UI_COMPARISON_PAYLOAD_ARTIFACT_ID]),
                "format": SIMULATOR_UI_COMPARISON_PAYLOAD_FORMAT,
                "artifact_scope": SHARED_COMPARISON_SCOPE,
            },
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
