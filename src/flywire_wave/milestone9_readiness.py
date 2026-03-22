from __future__ import annotations

import copy
import csv
import hashlib
import json
import subprocess
import sys
import textwrap
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from .config import REPO_ROOT, load_config
from .geometry_contract import (
    COARSE_OPERATOR_KEY,
    FINE_OPERATOR_KEY,
    OPERATOR_METADATA_KEY,
    TRANSFER_OPERATORS_KEY,
    build_geometry_bundle_paths,
    build_geometry_manifest_record,
    default_asset_statuses,
    load_operator_bundle_metadata,
    write_geometry_manifest,
)
from .io_utils import ensure_dir, write_json, write_root_ids
from .manifests import load_json, load_yaml
from .mesh_pipeline import process_mesh_into_wave_assets
from .readiness_contract import (
    FOLLOW_ON_READINESS_KEY,
    READINESS_GATE_HOLD,
    READY_FOR_FOLLOW_ON_WORK_KEY,
)
from .simulation_planning import discover_simulation_run_plans, resolve_manifest_simulation_plan
from .simulator_execution import (
    EXECUTION_PROVENANCE_ARTIFACT_ID,
    STRUCTURED_LOG_ARTIFACT_ID,
    UI_COMPARISON_PAYLOAD_ARTIFACT_ID,
)
from .simulator_result_contract import (
    METADATA_JSON_KEY,
    METRIC_TABLE_COLUMNS,
    METRICS_TABLE_KEY,
    MODEL_ARTIFACTS_KEY,
    P0_BASELINE_FAMILY,
    P1_BASELINE_FAMILY,
    READOUT_TRACE_ARRAYS,
    READOUT_TRACES_KEY,
    SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION,
    SIMULATOR_RESULT_BUNDLE_DESIGN_NOTE,
    STATE_SUMMARY_KEY,
    discover_simulator_extension_artifacts,
    discover_simulator_result_bundle_paths,
    load_simulator_result_bundle_metadata,
)
from .stimulus_bundle import record_stimulus_bundle, resolve_stimulus_input
from .synapse_mapping import materialize_synapse_anchor_maps


MILESTONE9_READINESS_REPORT_VERSION = "milestone9_readiness.v1"

DEFAULT_FIXTURE_TEST_TARGETS = (
    "tests.test_manifest_validation",
    "tests.test_simulation_planning",
    "tests.test_simulator_runtime",
    "tests.test_baseline_families",
    "tests.test_baseline_execution",
    "tests.test_simulator_result_contract",
    "tests.test_simulator_execution",
    "tests.test_milestone9_readiness",
)

DEFAULT_DOCUMENTATION_SNIPPETS: dict[str, tuple[str, ...]] = {
    "README.md": (
        "make milestone9-readiness",
        "scripts/14_milestone9_readiness.py",
        "milestone_9_readiness.md",
        "milestone_9_readiness.json",
        "scripts/run_simulation.py",
    ),
    "docs/pipeline_notes.md": (
        "make milestone9-readiness",
        "scripts/14_milestone9_readiness.py",
        "milestone_9_readiness.md",
        "milestone_9_readiness.json",
        "scripts/run_simulation.py",
    ),
    "docs/simulator_result_bundle_design.md": (
        "make milestone9-readiness",
        "scripts/14_milestone9_readiness.py",
        "milestone_9_readiness.md",
        "milestone_9_readiness.json",
        "scripts/run_simulation.py",
    ),
}

DEFAULT_VERIFICATION_BASELINE_FAMILIES: dict[str, dict[str, Any]] = {
    P0_BASELINE_FAMILY: {
        "membrane_time_constant_ms": 12.5,
        "recurrent_gain": 0.9,
    },
    P1_BASELINE_FAMILY: {
        "membrane_time_constant_ms": 12.5,
        "synaptic_current_time_constant_ms": 10.0,
        "recurrent_gain": 1.0,
        "delay_handling": {
            "mode": "from_coupling_bundle",
            "max_supported_delay_steps": 8,
        },
    },
}

DEFAULT_VERIFICATION_READOUT_CATALOG = [
    {
        "readout_id": "shared_output_mean",
        "scope": "circuit_output",
        "aggregation": "mean_over_root_ids",
        "units": "activation_au",
        "value_semantics": "shared_downstream_activation",
        "description": "Shared downstream output mean for matched baseline-versus-wave comparisons.",
    },
    {
        "readout_id": "direction_selectivity_index",
        "scope": "comparison_panel",
        "aggregation": "identity",
        "units": "unitless",
        "value_semantics": "direction_selectivity_index",
        "description": "Derived comparison summary routed through metric tables and UI payloads.",
    },
]


def build_milestone9_readiness_paths(processed_simulator_results_dir: str | Path) -> dict[str, Path]:
    root = Path(processed_simulator_results_dir).resolve()
    report_dir = root / "readiness" / "milestone_9"
    return {
        "report_dir": report_dir,
        "markdown_path": report_dir / "milestone_9_readiness.md",
        "json_path": report_dir / "milestone_9_readiness.json",
        "commands_dir": report_dir / "commands",
        "generated_fixture_dir": report_dir / "generated_fixture",
    }


def execute_milestone9_readiness_pass(
    *,
    config_path: str | Path,
    fixture_verification: Mapping[str, Any],
    python_executable: str = sys.executable,
    root_dir: str | Path = REPO_ROOT,
) -> dict[str, Any]:
    repo_root = Path(root_dir).resolve()
    cfg = load_config(config_path, project_root=repo_root)
    processed_stimulus_dir = Path(cfg["paths"]["processed_stimulus_dir"]).resolve()
    processed_retinal_dir = Path(cfg["paths"]["processed_retinal_dir"]).resolve()
    processed_simulator_results_dir = Path(cfg["paths"]["processed_simulator_results_dir"]).resolve()
    verification_cfg = dict(cfg.get("simulation_verification", {}))

    manifest_path = _resolve_repo_path(
        verification_cfg.get("manifest_path"),
        repo_root,
        default=repo_root / "manifests" / "examples" / "milestone_1_demo.yaml",
    )
    schema_path = _resolve_repo_path(
        verification_cfg.get("schema_path"),
        repo_root,
        default=repo_root / "schemas" / "milestone_1_experiment_manifest.schema.json",
    )
    design_lock_path = _resolve_repo_path(
        verification_cfg.get("design_lock_path"),
        repo_root,
        default=repo_root / "config" / "milestone_1_design_lock.yaml",
    )

    readiness_paths = build_milestone9_readiness_paths(processed_simulator_results_dir)
    report_dir = ensure_dir(readiness_paths["report_dir"])
    commands_dir = ensure_dir(readiness_paths["commands_dir"])
    generated_fixture_dir = ensure_dir(readiness_paths["generated_fixture_dir"])

    fixture = _materialize_verification_fixture(
        manifest_path=manifest_path,
        verification_cfg=verification_cfg,
        generated_fixture_dir=generated_fixture_dir,
        processed_stimulus_dir=processed_stimulus_dir,
        processed_retinal_dir=processed_retinal_dir,
        processed_simulator_results_dir=processed_simulator_results_dir,
    )
    manifest_plan_audit = _build_manifest_plan_audit(
        fixture=fixture,
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        commands_dir=commands_dir,
    )
    manifest_execution_audit = _execute_manifest_workflow_audit(
        fixture=fixture,
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        commands_dir=commands_dir,
        python_executable=python_executable,
        repo_root=repo_root,
        manifest_plan_audit=manifest_plan_audit,
    )
    documentation_audit = _audit_documentation(repo_root=repo_root)
    workflow_coverage = _build_workflow_coverage(
        fixture_verification=fixture_verification,
        manifest_plan_audit=manifest_plan_audit,
        manifest_execution_audit=manifest_execution_audit,
        documentation_audit=documentation_audit,
    )

    blocking_issues = (
        list(manifest_plan_audit["issues"])
        + list(manifest_execution_audit["issues"])
        + list(documentation_audit["issues"])
    )
    fixture_status = str(fixture_verification.get("status", "skipped"))

    if fixture_status != "pass" or blocking_issues or not all(workflow_coverage.values()):
        readiness_status = READINESS_GATE_HOLD
    else:
        readiness_status = "ready"

    remaining_risks = [
        "The readiness pass uses a deterministic two-neuron local fixture plus the shipped Milestone 1 manifest path. It proves contract integration, but it is not a biological calibration benchmark.",
        "The report verifies baseline bundles are comparison-ready for later wave-mode consumption, but it does not execute `surface_wave` itself because Milestone 10 remains downstream work.",
    ]

    summary = {
        "report_version": MILESTONE9_READINESS_REPORT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "config_path": str(Path(config_path).resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "schema_path": str(schema_path.resolve()),
        "design_lock_path": str(design_lock_path.resolve()),
        "processed_stimulus_dir": str(processed_stimulus_dir),
        "processed_retinal_dir": str(processed_retinal_dir),
        "processed_simulator_results_dir": str(processed_simulator_results_dir),
        "report_dir": str(report_dir.resolve()),
        "markdown_path": str(readiness_paths["markdown_path"].resolve()),
        "json_path": str(readiness_paths["json_path"].resolve()),
        "commands_dir": str(commands_dir.resolve()),
        "generated_fixture_dir": str(generated_fixture_dir.resolve()),
        "documented_verification_command": "make milestone9-readiness",
        "explicit_verification_command": "python scripts/14_milestone9_readiness.py --config config/milestone_9_verification.yaml",
        "fixture_verification": copy.deepcopy(dict(fixture_verification)),
        "generated_fixture": copy.deepcopy(fixture),
        "manifest_plan_audit": manifest_plan_audit,
        "manifest_execution_audit": manifest_execution_audit,
        "workflow_coverage": workflow_coverage,
        "documentation_audit": documentation_audit,
        "remaining_risks": remaining_risks,
        "follow_on_issues": [],
        FOLLOW_ON_READINESS_KEY: {
            "status": readiness_status,
            "local_baseline_gate": readiness_status,
            READY_FOR_FOLLOW_ON_WORK_KEY: bool(readiness_status != READINESS_GATE_HOLD),
            "ready_for_workstreams": [
                "surface_wave",
                "metrics",
                "ui_comparison",
            ],
        },
    }

    readiness_paths["markdown_path"].write_text(
        _render_milestone9_readiness_markdown(summary=summary),
        encoding="utf-8",
    )
    write_json(summary, readiness_paths["json_path"])
    return summary


def _materialize_verification_fixture(
    *,
    manifest_path: Path,
    verification_cfg: Mapping[str, Any],
    generated_fixture_dir: Path,
    processed_stimulus_dir: Path,
    processed_retinal_dir: Path,
    processed_simulator_results_dir: Path,
) -> dict[str, Any]:
    fixture_assets_dir = ensure_dir(generated_fixture_dir / "assets")
    subset_output_dir = ensure_dir(generated_fixture_dir / "subsets")
    manifest_payload = load_yaml(manifest_path)
    subset_name = str(manifest_payload["subset_name"])
    selected_root_ids = [101, 202]

    stimulus = resolve_stimulus_input(
        manifest_path=manifest_path,
        schema_path=_resolve_repo_path(
            verification_cfg.get("schema_path"),
            REPO_ROOT,
            default=REPO_ROOT / "schemas" / "milestone_1_experiment_manifest.schema.json",
        ),
        design_lock_path=_resolve_repo_path(
            verification_cfg.get("design_lock_path"),
            REPO_ROOT,
            default=REPO_ROOT / "config" / "milestone_1_design_lock.yaml",
        ),
        processed_stimulus_dir=processed_stimulus_dir,
    )
    record_stimulus_bundle(stimulus)

    selected_root_ids_path = generated_fixture_dir / "selected_root_ids.txt"
    write_root_ids(selected_root_ids, selected_root_ids_path)

    subset_manifest_path = subset_output_dir / subset_name / "subset_manifest.json"
    subset_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    subset_manifest_path.write_text(
        json.dumps(
            {
                "subset_manifest_version": "1",
                "preset_name": subset_name,
                "root_ids": selected_root_ids,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    geometry_manifest_path = generated_fixture_dir / "geometry_manifest.json"
    _write_execution_geometry_manifest(
        output_dir=fixture_assets_dir,
        manifest_path=geometry_manifest_path,
    )

    baseline_family_overrides = _deep_merge_mappings(
        DEFAULT_VERIFICATION_BASELINE_FAMILIES,
        verification_cfg.get("baseline_families"),
        field_name="simulation_verification.baseline_families",
    )
    config_payload = {
        "paths": {
            "selected_root_ids": str(selected_root_ids_path.resolve()),
            "subset_output_dir": str(subset_output_dir.resolve()),
            "manifest_json": str(geometry_manifest_path.resolve()),
            "processed_stimulus_dir": str(processed_stimulus_dir.resolve()),
            "processed_retinal_dir": str(processed_retinal_dir.resolve()),
            "processed_simulator_results_dir": str(processed_simulator_results_dir.resolve()),
        },
        "selection": {
            "active_preset": subset_name,
        },
        "simulation": {
            "input": {
                "source_kind": "stimulus_bundle",
                "require_recorded_bundle": True,
            },
            "readout_catalog": copy.deepcopy(DEFAULT_VERIFICATION_READOUT_CATALOG),
            "baseline_families": baseline_family_overrides,
        },
    }
    fixture_config_path = generated_fixture_dir / "simulation_fixture_config.yaml"
    fixture_config_path.write_text(
        yaml.safe_dump(config_payload, sort_keys=False),
        encoding="utf-8",
    )

    return {
        "fixture_config_path": str(fixture_config_path.resolve()),
        "selected_root_ids_path": str(selected_root_ids_path.resolve()),
        "subset_manifest_path": str(subset_manifest_path.resolve()),
        "geometry_manifest_path": str(geometry_manifest_path.resolve()),
        "fixture_assets_dir": str(fixture_assets_dir.resolve()),
        "processed_stimulus_dir": str(processed_stimulus_dir.resolve()),
        "processed_retinal_dir": str(processed_retinal_dir.resolve()),
        "processed_simulator_results_dir": str(processed_simulator_results_dir.resolve()),
        "selected_root_ids": list(selected_root_ids),
    }


def _build_manifest_plan_audit(
    *,
    fixture: Mapping[str, Any],
    manifest_path: Path,
    schema_path: Path,
    design_lock_path: Path,
    commands_dir: Path,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    plan = resolve_manifest_simulation_plan(
        manifest_path=manifest_path,
        config_path=fixture["fixture_config_path"],
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    baseline_run_plans = discover_simulation_run_plans(
        plan,
        model_mode="baseline",
    )
    baseline_seed_sweep = discover_simulation_run_plans(
        plan,
        model_mode="baseline",
        use_manifest_seed_sweep=True,
    )
    surface_wave_plans = discover_simulation_run_plans(
        plan,
        model_mode="surface_wave",
    )

    baseline_arm_ids = [item["arm_reference"]["arm_id"] for item in baseline_run_plans]
    baseline_families = sorted(
        {
            str(item["arm_reference"]["baseline_family"])
            for item in baseline_run_plans
        }
    )
    topology_conditions = sorted({str(item["topology_condition"]) for item in baseline_run_plans})
    shared_readout_ids = [
        item["readout_id"] for item in plan["runtime_config"]["simulation"]["shared_readout_catalog"]
    ]

    if baseline_families != [P0_BASELINE_FAMILY, P1_BASELINE_FAMILY]:
        issues.append(
            _issue(
                "blocking",
                f"Baseline manifest planning did not cover both P0 and P1 families: {baseline_families!r}.",
            )
        )
    if topology_conditions != ["intact", "shuffled"]:
        issues.append(
            _issue(
                "blocking",
                "Baseline manifest planning did not cover both intact and shuffled topology conditions.",
            )
        )
    if len(surface_wave_plans) < 1:
        issues.append(
            _issue(
                "blocking",
                "Representative manifest planning did not preserve any surface-wave arms for downstream reuse.",
            )
        )

    audit = {
        "overall_status": "pass" if not issues else "fail",
        "issues": issues,
        "manifest_arm_count": len(plan["arm_plans"]),
        "baseline_arm_count": len(baseline_run_plans),
        "surface_wave_arm_count": len(surface_wave_plans),
        "baseline_seed_sweep_run_count": len(baseline_seed_sweep),
        "baseline_arm_ids": baseline_arm_ids,
        "surface_wave_arm_ids": [item["arm_reference"]["arm_id"] for item in surface_wave_plans],
        "baseline_families": baseline_families,
        "topology_conditions": topology_conditions,
        "input_source_kind": str(baseline_run_plans[0]["input_reference"]["selected_input_kind"]),
        "selected_root_ids": list(baseline_run_plans[0]["selection"]["selected_root_ids"]),
        "shared_readout_ids": shared_readout_ids,
        "timebase": copy.deepcopy(baseline_run_plans[0]["runtime"]["timebase"]),
        "planned_result_bundles": {
            item["arm_reference"]["arm_id"]: {
                "bundle_id": item["result_bundle"]["reference"]["bundle_id"],
                "run_spec_hash": item["result_bundle"]["reference"]["run_spec_hash"],
            }
            for item in baseline_run_plans
        },
    }
    write_json(audit, commands_dir / "manifest_plan_audit.json")
    audit["plan"] = plan
    return audit


def _execute_manifest_workflow_audit(
    *,
    fixture: Mapping[str, Any],
    manifest_path: Path,
    schema_path: Path,
    design_lock_path: Path,
    commands_dir: Path,
    python_executable: str,
    repo_root: Path,
    manifest_plan_audit: Mapping[str, Any],
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    baseline_run_plans = {
        item["arm_reference"]["arm_id"]: item
        for item in discover_simulation_run_plans(
            manifest_plan_audit["plan"],
            model_mode="baseline",
        )
    }
    command = [
        python_executable,
        str(repo_root / "scripts" / "run_simulation.py"),
        "--config",
        str(fixture["fixture_config_path"]),
        "--manifest",
        str(manifest_path),
        "--schema",
        str(schema_path),
        "--design-lock",
        str(design_lock_path),
        "--model-mode",
        "baseline",
    ]

    first = _run_command(name="manifest_execution_first", command=command, cwd=repo_root)
    first_summary = dict(first.get("parsed_summary") or {})
    write_json(first, commands_dir / "manifest_execution_first.json")
    if first["status"] != "pass":
        issues.append(
            _issue("blocking", "The shipped baseline execution command failed on the representative manifest fixture.")
        )
        return {
            "overall_status": "fail",
            "issues": issues,
            "commands": {
                "first": first,
            },
        }

    first_hashes = _capture_executed_run_hashes(first_summary)
    second = _run_command(name="manifest_execution_second", command=command, cwd=repo_root)
    second_summary = dict(second.get("parsed_summary") or {})
    write_json(second, commands_dir / "manifest_execution_second.json")
    if second["status"] != "pass":
        issues.append(
            _issue("blocking", "The repeated baseline execution command failed, so output determinism could not be confirmed.")
        )
    summary_stable = first_summary == second_summary
    if not summary_stable:
        issues.append(
            _issue("blocking", "Repeated baseline execution produced different command summaries.")
        )
    file_hashes_stable = _compare_executed_run_hashes(first_hashes, second_summary)
    if not file_hashes_stable:
        issues.append(
            _issue("blocking", "Repeated baseline execution changed one or more result-bundle artifact bytes.")
        )

    per_arm_audits = {}
    for run_summary in first_summary.get("executed_runs", []):
        arm_id = str(run_summary["arm_id"])
        planned_arm = baseline_run_plans.get(arm_id)
        if planned_arm is None:
            issues.append(
                _issue("blocking", f"Executed baseline arm {arm_id!r} was not present in the planned baseline manifest run set.")
            )
            continue
        arm_audit = _audit_executed_run(
            run_summary=run_summary,
            planned_arm=planned_arm,
        )
        per_arm_audits[arm_id] = arm_audit
        issues.extend(arm_audit["issues"])

    audit = {
        "overall_status": "pass" if not issues else "fail",
        "issues": issues,
        "commands": {
            "first": first,
            "second": second,
        },
        "executed_run_count": int(first_summary.get("executed_run_count", 0)),
        "executed_arm_ids": list(first_summary.get("arm_order", [])),
        "summary_stable": summary_stable,
        "file_hashes_stable": file_hashes_stable,
        "first_run_hashes": first_hashes,
        "per_arm_audits": per_arm_audits,
    }
    write_json(audit, commands_dir / "manifest_execution_audit.json")
    return audit


def _audit_executed_run(
    *,
    run_summary: Mapping[str, Any],
    planned_arm: Mapping[str, Any],
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    metadata_path = Path(str(run_summary["metadata_path"])).resolve()
    metadata = load_simulator_result_bundle_metadata(metadata_path)
    result_paths = discover_simulator_result_bundle_paths(metadata)
    extension_artifacts = {
        item["artifact_id"]: item
        for item in discover_simulator_extension_artifacts(metadata)
    }
    state_summary_rows = json.loads(result_paths[STATE_SUMMARY_KEY].read_text(encoding="utf-8"))
    metrics_header, metrics_rows = _read_csv_rows(result_paths[METRICS_TABLE_KEY])
    ui_payload = load_json(extension_artifacts[UI_COMPARISON_PAYLOAD_ARTIFACT_ID]["path"])
    provenance = load_json(extension_artifacts[EXECUTION_PROVENANCE_ARTIFACT_ID]["path"])
    trace_summary = _load_trace_summary(result_paths[READOUT_TRACES_KEY])

    planned_bundle = planned_arm["result_bundle"]["reference"]
    if metadata["contract_version"] != SIMULATOR_RESULT_BUNDLE_CONTRACT_VERSION:
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} wrote an unexpected result-bundle contract version.")
        )
    if metadata["design_note"] != SIMULATOR_RESULT_BUNDLE_DESIGN_NOTE:
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} did not point back to the canonical simulator design note.")
        )
    if metadata["bundle_id"] != planned_bundle["bundle_id"]:
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} wrote a bundle_id that drifted from the manifest plan.")
        )
    if metadata["run_spec_hash"] != planned_bundle["run_spec_hash"]:
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} wrote a run_spec_hash that drifted from the manifest plan.")
        )
    if metrics_header != list(METRIC_TABLE_COLUMNS):
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} wrote metrics.csv with an unexpected column contract.")
        )
    expected_artifact_ids = {
        METADATA_JSON_KEY,
        STATE_SUMMARY_KEY,
        READOUT_TRACES_KEY,
        METRICS_TABLE_KEY,
        STRUCTURED_LOG_ARTIFACT_ID,
        EXECUTION_PROVENANCE_ARTIFACT_ID,
        UI_COMPARISON_PAYLOAD_ARTIFACT_ID,
    }
    actual_artifact_ids = {item["artifact_id"] for item in ui_payload["artifact_inventory"]}
    if actual_artifact_ids != expected_artifact_ids:
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} produced a UI payload with the wrong artifact inventory.")
        )
    if list(ui_payload["metric_payload"]["columns"]) != list(METRIC_TABLE_COLUMNS):
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} exposed a UI metric payload with the wrong shared metric columns.")
        )
    if ui_payload["trace_payload"]["path"] != str(result_paths[READOUT_TRACES_KEY]):
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} exposed a UI trace payload path that drifted from bundle discovery.")
        )
    if provenance["bundle_reference"]["bundle_id"] != metadata["bundle_id"]:
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} wrote provenance that drifted from the bundle metadata.")
        )
    run_blueprint_metadata = provenance["execution_plan"]["run_blueprint_metadata"]
    if run_blueprint_metadata["canonical_input"]["input_kind"] != planned_arm["input_reference"]["selected_input_kind"]:
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} lost the canonical input source identity between planning and execution.")
        )
    if run_blueprint_metadata["recurrent_coupling"]["topology_condition"] != planned_arm["topology_condition"]:
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} lost the planned topology condition in execution metadata.")
        )
    if int(run_blueprint_metadata["recurrent_coupling"]["component_count"]) <= 0:
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} resolved no recurrent coupling components.")
        )
    if trace_summary["array_names"] != sorted(READOUT_TRACE_ARRAYS):
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} wrote readout traces with the wrong archive arrays.")
        )
    if trace_summary["readout_ids"] != [
        item["readout_id"] for item in planned_arm["runtime"]["shared_readout_catalog"]
    ]:
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} wrote shared readout IDs that drifted from the manifest plan.")
        )

    state_ids = [str(row["state_id"]) for row in state_summary_rows]
    baseline_family = str(metadata["arm_reference"]["baseline_family"])
    has_synaptic_state = "circuit_synaptic_current_state" in state_ids
    if baseline_family == P0_BASELINE_FAMILY and has_synaptic_state:
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} exposed P1-only synaptic current state in a P0 bundle.")
        )
    if baseline_family == P1_BASELINE_FAMILY and not has_synaptic_state:
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} failed to expose P1 synaptic current state summaries.")
        )

    metric_ids = sorted({str(row["metric_id"]) for row in metrics_rows})
    required_metric_ids = {
        "final_endpoint_value",
        "sample_max_value",
        "sample_peak_time_ms",
    }
    if not required_metric_ids.issubset(metric_ids):
        issues.append(
            _issue("blocking", f"Run {run_summary['arm_id']!r} did not emit the expected comparison-ready metric rows.")
        )

    return {
        "overall_status": "pass" if not issues else "fail",
        "issues": issues,
        "bundle_id": metadata["bundle_id"],
        "run_spec_hash": metadata["run_spec_hash"],
        "baseline_family": baseline_family,
        "topology_condition": provenance["comparison_context"]["topology_condition"],
        "shared_readout_ids": trace_summary["readout_ids"],
        "metric_ids": metric_ids,
        "state_ids": state_ids,
        "metric_row_count": len(metrics_rows),
        "state_summary_row_count": len(state_summary_rows),
        "artifact_inventory_ids": sorted(actual_artifact_ids),
        "ui_view_ids": [
            item["output_id"] for item in ui_payload["declared_output_targets"]["views"]
        ],
        "timebase": copy.deepcopy(metadata["timebase"]),
        "canonical_input_kind": run_blueprint_metadata["canonical_input"]["input_kind"],
        "coupling_component_count": int(run_blueprint_metadata["recurrent_coupling"]["component_count"]),
        "has_synaptic_current_state": has_synaptic_state,
    }


def _build_workflow_coverage(
    *,
    fixture_verification: Mapping[str, Any],
    manifest_plan_audit: Mapping[str, Any],
    manifest_execution_audit: Mapping[str, Any],
    documentation_audit: Mapping[str, Any],
) -> dict[str, bool]:
    per_arm_audits = dict(manifest_execution_audit.get("per_arm_audits", {}))
    families = {audit["baseline_family"] for audit in per_arm_audits.values()}
    topology_conditions = {audit["topology_condition"] for audit in per_arm_audits.values()}
    shared_readout_sets = {tuple(audit["shared_readout_ids"]) for audit in per_arm_audits.values()}
    timebase_signatures = {
        json.dumps(audit["timebase"], sort_keys=True)
        for audit in per_arm_audits.values()
    }

    return {
        "focused_fixture_suite_passed": str(fixture_verification.get("status", "")) == "pass",
        "manifest_planning_compatible": str(manifest_plan_audit.get("overall_status", "fail")) == "pass",
        "runtime_execution_compatible": str(manifest_execution_audit.get("overall_status", "fail")) == "pass",
        "surface_wave_manifest_reuse_ready": int(manifest_plan_audit.get("surface_wave_arm_count", 0)) >= 1,
        "baseline_family_coverage_complete": families == {P0_BASELINE_FAMILY, P1_BASELINE_FAMILY},
        "topology_coverage_complete": topology_conditions == {"intact", "shuffled"},
        "coupling_and_input_contract_compatible": all(
            audit["canonical_input_kind"] == "stimulus_bundle"
            and int(audit["coupling_component_count"]) > 0
            for audit in per_arm_audits.values()
        ),
        "result_bundle_contract_compatible": all(
            METADATA_JSON_KEY in audit["artifact_inventory_ids"]
            and READOUT_TRACES_KEY in audit["artifact_inventory_ids"]
            and METRICS_TABLE_KEY in audit["artifact_inventory_ids"]
            for audit in per_arm_audits.values()
        ),
        "logging_and_metrics_compatible": all(
            STRUCTURED_LOG_ARTIFACT_ID in audit["artifact_inventory_ids"]
            and EXECUTION_PROVENANCE_ARTIFACT_ID in audit["artifact_inventory_ids"]
            and "final_endpoint_value" in audit["metric_ids"]
            for audit in per_arm_audits.values()
        ),
        "ui_payload_compatible": all(
            UI_COMPARISON_PAYLOAD_ARTIFACT_ID in audit["artifact_inventory_ids"]
            and "surface_vs_baseline_split_view" in audit["ui_view_ids"]
            for audit in per_arm_audits.values()
        ),
        "comparison_surface_aligned": len(shared_readout_sets) == 1 and len(timebase_signatures) == 1,
        "determinism_compatible": bool(manifest_execution_audit.get("summary_stable"))
        and bool(manifest_execution_audit.get("file_hashes_stable")),
        "documentation_compatible": str(documentation_audit.get("overall_status", "fail")) == "pass",
    }


def _audit_documentation(*, repo_root: Path) -> dict[str, Any]:
    audits: dict[str, Any] = {}
    issues: list[dict[str, str]] = []

    for relative_path, required_snippets in DEFAULT_DOCUMENTATION_SNIPPETS.items():
        doc_path = repo_root / relative_path
        missing_snippets: list[str] = []
        if not doc_path.exists():
            missing_snippets = list(required_snippets)
            issues.append(
                _issue(
                    "blocking",
                    f"{relative_path} is missing, so the Milestone 9 readiness workflow is not documented there.",
                )
            )
            audits[relative_path] = {
                "status": "fail",
                "path": str(doc_path.resolve()),
                "missing_snippets": missing_snippets,
            }
            continue

        content = doc_path.read_text(encoding="utf-8")
        missing_snippets = [snippet for snippet in required_snippets if snippet not in content]
        if missing_snippets:
            issues.append(
                _issue(
                    "blocking",
                    f"{relative_path} is missing the Milestone 9 readiness snippets {missing_snippets!r}.",
                )
            )
        audits[relative_path] = {
            "status": "pass" if not missing_snippets else "fail",
            "path": str(doc_path.resolve()),
            "missing_snippets": missing_snippets,
        }

    return {
        "overall_status": "pass" if not issues else "fail",
        "files": audits,
        "issues": issues,
    }


def _resolve_repo_path(value: Any, repo_root: Path, *, default: Path) -> Path:
    if value is None:
        return default.resolve()
    candidate = Path(str(value)).expanduser()
    if not candidate.is_absolute():
        candidate = (repo_root / candidate).resolve()
    return candidate.resolve()


def _run_command(*, name: str, command: list[str], cwd: Path) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    payload: dict[str, Any] = {
        "name": name,
        "status": "pass" if result.returncode == 0 else "fail",
        "command": " ".join(command),
        "returncode": int(result.returncode),
    }
    parsed_summary = _parse_json_from_command_output(result.stdout)
    if parsed_summary is not None:
        payload["parsed_summary"] = parsed_summary
    return payload


def _parse_json_from_command_output(stdout: str) -> dict[str, Any] | None:
    stripped = stdout.strip()
    if not stripped:
        return None
    start = stripped.find("{")
    if start < 0:
        return None
    candidate = stripped[start:]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _capture_executed_run_hashes(summary: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    hashes: dict[str, dict[str, str]] = {}
    for run in summary.get("executed_runs", []):
        arm_id = str(run["arm_id"])
        paths = {
            "metadata_json": Path(str(run["metadata_path"])),
            "state_summary": Path(str(run["state_summary_path"])),
            "readout_traces": Path(str(run["readout_traces_path"])),
            "metrics_table": Path(str(run["metrics_table_path"])),
            "structured_log": Path(str(run["structured_log_path"])),
            "execution_provenance": Path(str(run["provenance_path"])),
            "ui_comparison_payload": Path(str(run["ui_payload_path"])),
        }
        hashes[arm_id] = {
            label: _hash_file(path)
            for label, path in paths.items()
        }
    return hashes


def _compare_executed_run_hashes(
    expected_hashes: Mapping[str, Mapping[str, str]],
    summary: Mapping[str, Any],
) -> bool:
    actual_hashes = _capture_executed_run_hashes(summary)
    return actual_hashes == expected_hashes


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return header, rows


def _load_trace_summary(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as archive:
        array_names = sorted(str(key) for key in archive.files)
        readout_ids = [
            str(item)
            for item in archive["readout_ids"].tolist()
        ]
        time_ms = [float(item) for item in archive["time_ms"].tolist()]
    return {
        "array_names": array_names,
        "readout_ids": readout_ids,
        "sample_count": len(time_ms),
        "sample_start_ms": time_ms[0],
        "sample_end_ms": time_ms[-1],
    }


def _issue(severity: str, message: str) -> dict[str, str]:
    return {
        "severity": str(severity),
        "message": str(message),
    }


def _deep_merge_mappings(
    base: Mapping[str, Any],
    override: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    merged = copy.deepcopy(dict(base))
    if override is None:
        return merged
    if not isinstance(override, Mapping):
        raise ValueError(f"{field_name} must be a mapping when provided.")
    for key, value in override.items():
        if key in merged and isinstance(merged[key], Mapping):
            if not isinstance(value, Mapping):
                raise ValueError(f"{field_name}.{key} must be a mapping when overriding a mapping value.")
            merged[key] = _deep_merge_mappings(
                merged[key],
                value,
                field_name=f"{field_name}.{key}",
            )
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _write_execution_geometry_manifest(*, output_dir: Path, manifest_path: Path) -> None:
    meshes_raw_dir = output_dir / "meshes_raw"
    skeletons_raw_dir = output_dir / "skeletons_raw"
    processed_mesh_dir = output_dir / "processed_meshes"
    processed_graph_dir = output_dir / "processed_graphs"
    processed_coupling_dir = output_dir / "processed_coupling"

    bundle_paths_101 = build_geometry_bundle_paths(
        101,
        meshes_raw_dir=meshes_raw_dir,
        skeletons_raw_dir=skeletons_raw_dir,
        processed_mesh_dir=processed_mesh_dir,
        processed_graph_dir=processed_graph_dir,
    )
    _write_octahedron_mesh(bundle_paths_101.raw_mesh_path)
    process_mesh_into_wave_assets(
        root_id=101,
        bundle_paths=bundle_paths_101,
        simplify_target_faces=8,
        patch_hops=1,
        patch_vertex_cap=2,
        registry_metadata={"cell_type": "T4a", "project_role": "surface_simulated"},
    )

    bundle_paths_202 = build_geometry_bundle_paths(
        202,
        meshes_raw_dir=meshes_raw_dir,
        skeletons_raw_dir=skeletons_raw_dir,
        processed_mesh_dir=processed_mesh_dir,
        processed_graph_dir=processed_graph_dir,
    )
    _write_octahedron_mesh(bundle_paths_202.raw_mesh_path)
    process_mesh_into_wave_assets(
        root_id=202,
        bundle_paths=bundle_paths_202,
        simplify_target_faces=8,
        patch_hops=1,
        patch_vertex_cap=2,
        registry_metadata={"cell_type": "T5a", "project_role": "surface_simulated"},
    )

    synapse_registry_path = processed_coupling_dir / "synapse_registry.csv"
    _write_execution_synapse_registry(synapse_registry_path)
    coupling_summary = materialize_synapse_anchor_maps(
        root_ids=[101, 202],
        processed_coupling_dir=processed_coupling_dir,
        meshes_raw_dir=meshes_raw_dir,
        skeletons_raw_dir=skeletons_raw_dir,
        processed_mesh_dir=processed_mesh_dir,
        processed_graph_dir=processed_graph_dir,
        neuron_registry=pd.DataFrame(
            {
                "root_id": [101, 202],
                "project_role": ["surface_simulated", "surface_simulated"],
            }
        ),
        synapse_registry_path=synapse_registry_path,
        coupling_assembly={
            "delay_model": {
                "mode": "constant_zero_ms",
                "base_delay_ms": 0.0,
                "velocity_distance_units_per_ms": 1.0,
                "delay_bin_size_ms": 0.0,
            }
        },
    )

    bundle_records = {
        101: build_geometry_manifest_record(
            bundle_paths=bundle_paths_101,
            asset_statuses=_surface_ready_asset_statuses(),
            dataset_name="flywire_fafb_public",
            materialization_version=783,
            meshing_config_snapshot=_meshing_config_snapshot(),
            registry_metadata={
                "cell_type": "T4a",
                "project_role": "surface_simulated",
                "materialization_version": "783",
                "snapshot_version": "783",
            },
            operator_bundle_metadata=load_operator_bundle_metadata(
                bundle_paths_101.operator_metadata_path
            ),
            processed_coupling_dir=processed_coupling_dir,
            coupling_bundle_metadata=coupling_summary["bundle_metadata_by_root"][101],
        ),
        202: build_geometry_manifest_record(
            bundle_paths=bundle_paths_202,
            asset_statuses=_surface_ready_asset_statuses(),
            dataset_name="flywire_fafb_public",
            materialization_version=783,
            meshing_config_snapshot=_meshing_config_snapshot(),
            registry_metadata={
                "cell_type": "T5a",
                "project_role": "surface_simulated",
                "materialization_version": "783",
                "snapshot_version": "783",
            },
            operator_bundle_metadata=load_operator_bundle_metadata(
                bundle_paths_202.operator_metadata_path
            ),
            processed_coupling_dir=processed_coupling_dir,
            coupling_bundle_metadata=coupling_summary["bundle_metadata_by_root"][202],
        ),
    }
    write_geometry_manifest(
        manifest_path=manifest_path,
        bundle_records=bundle_records,
        dataset_name="flywire_fafb_public",
        materialization_version=783,
        meshing_config_snapshot=_meshing_config_snapshot(),
        processed_coupling_dir=processed_coupling_dir,
    )


def _meshing_config_snapshot() -> dict[str, object]:
    return {
        "operator_assembly": {
            "version": "operator_assembly.v1",
            "boundary_condition": {"mode": "closed_surface_zero_flux"},
            "anisotropy": {"model": "isotropic"},
        }
    }


def _surface_ready_asset_statuses() -> dict[str, str]:
    asset_statuses = default_asset_statuses(fetch_skeletons=False)
    asset_statuses.update(
        {
            FINE_OPERATOR_KEY: "ready",
            COARSE_OPERATOR_KEY: "ready",
            TRANSFER_OPERATORS_KEY: "ready",
            OPERATOR_METADATA_KEY: "ready",
        }
    )
    return asset_statuses


def _write_execution_synapse_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "synapse_row_id": "fixture.csv#1",
                "source_row_number": 1,
                "synapse_id": "edge-a",
                "pre_root_id": 202,
                "post_root_id": 101,
                "x": 0.0,
                "y": 0.5,
                "z": 0.5,
                "pre_x": 0.0,
                "pre_y": 1.0,
                "pre_z": 0.0,
                "post_x": 0.0,
                "post_y": 0.0,
                "post_z": 1.0,
                "neuropil": "LOP_R",
                "nt_type": "ACH",
                "sign": "excitatory",
                "confidence": 0.99,
                "weight": 1.0,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
            {
                "synapse_row_id": "fixture.csv#2",
                "source_row_number": 2,
                "synapse_id": "edge-b",
                "pre_root_id": 101,
                "post_root_id": 202,
                "x": 1.0,
                "y": 0.0,
                "z": 0.0,
                "pre_x": 0.0,
                "pre_y": 0.0,
                "pre_z": 1.0,
                "post_x": 0.0,
                "post_y": 1.0,
                "post_z": 0.0,
                "neuropil": "ME_R",
                "nt_type": "ACH",
                "sign": "excitatory",
                "confidence": 0.95,
                "weight": 0.5,
                "snapshot_version": "783",
                "materialization_version": "783",
                "source_file": "fixture.csv",
            },
        ]
    ).to_csv(path, index=False)


def _write_octahedron_mesh(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """
            ply
            format ascii 1.0
            element vertex 6
            property float x
            property float y
            property float z
            element face 8
            property list uchar int vertex_indices
            end_header
            0 0 1
            1 0 0
            0 1 0
            -1 0 0
            0 -1 0
            0 0 -1
            3 0 1 2
            3 0 2 3
            3 0 3 4
            3 0 4 1
            3 5 2 1
            3 5 3 2
            3 5 4 3
            3 5 1 4
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_stub_swc(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "1 1 0 0 0 1 -1\n2 3 0 1 0 1 1\n",
        encoding="utf-8",
    )


def _render_milestone9_readiness_markdown(*, summary: Mapping[str, Any]) -> str:
    readiness = dict(summary[FOLLOW_ON_READINESS_KEY])
    plan_audit = dict(summary["manifest_plan_audit"])
    execution_audit = dict(summary["manifest_execution_audit"])
    documentation_audit = dict(summary["documentation_audit"])
    workflow_coverage = dict(summary["workflow_coverage"])
    per_arm_audits = dict(execution_audit.get("per_arm_audits", {}))

    lines = [
        "# Milestone 9 Readiness Report",
        "",
        "## Verdict",
        "",
        f"- Readiness verdict: `{readiness['status']}`",
        f"- Local baseline gate: `{readiness['local_baseline_gate']}`",
        f"- Ready for downstream surface-wave, metrics, and UI comparison work: `{readiness[READY_FOR_FOLLOW_ON_WORK_KEY]}`",
        f"- Verification command: `{summary['documented_verification_command']}`",
        f"- Explicit command: `{summary['explicit_verification_command']}`",
        "",
        "## Verification Surface",
        "",
        f"- Focused fixture suite: `{summary['fixture_verification'].get('status', '')}`",
        f"- Representative manifest path: `{summary['manifest_path']}`",
        f"- Planned baseline arms: `{plan_audit['baseline_arm_count']}`",
        f"- Planned surface-wave arms preserved for later reuse: `{plan_audit['surface_wave_arm_count']}`",
        f"- Baseline seed-sweep run count discoverable from the same manifest: `{plan_audit['baseline_seed_sweep_run_count']}`",
        f"- Executed baseline arms: `{execution_audit.get('executed_run_count', 0)}`",
        f"- Repeated command summary stable: `{execution_audit.get('summary_stable', False)}`",
        f"- Repeated bundle bytes stable: `{execution_audit.get('file_hashes_stable', False)}`",
        f"- Documentation audit: `{documentation_audit['overall_status']}`",
        "",
        "## Workflow Coverage",
        "",
    ]

    for key, value in workflow_coverage.items():
        lines.append(f"- {key.replace('_', ' ')}: `{value}`")

    lines.extend(
        [
            "",
            "## Per-Arm Bundle Audits",
            "",
        ]
    )
    for arm_id, audit in per_arm_audits.items():
        lines.extend(
            [
                f"### {arm_id}",
                "",
                f"- Overall status: `{audit['overall_status']}`",
                f"- Baseline family: `{audit['baseline_family']}`",
                f"- Topology condition: `{audit['topology_condition']}`",
                f"- Shared readout IDs: `{audit['shared_readout_ids']}`",
                f"- Metric IDs: `{audit['metric_ids']}`",
                f"- State summary rows: `{audit['state_summary_row_count']}`",
                f"- Metric row count: `{audit['metric_row_count']}`",
                f"- Synaptic current state present: `{audit['has_synaptic_current_state']}`",
            ]
        )
        if audit["issues"]:
            lines.append("- Issues:")
            for issue in audit["issues"]:
                lines.append(f"  - `{issue['severity']}`: {issue['message']}")
        lines.append("")

    lines.extend(
        [
            "## Remaining Risks",
            "",
        ]
    )
    for risk in summary["remaining_risks"]:
        lines.append(f"- {risk}")

    lines.extend(
        [
            "",
            "## Deferred Follow-On Issues",
            "",
        ]
    )
    if summary["follow_on_issues"]:
        for issue in summary["follow_on_issues"]:
            lines.append(f"- `{issue['ticket_id']}`: {issue['title']}")
            lines.append(f"  Reproduction: {issue['reproduction']}")
    else:
        lines.append("- None.")

    return "\n".join(lines).rstrip() + "\n"
