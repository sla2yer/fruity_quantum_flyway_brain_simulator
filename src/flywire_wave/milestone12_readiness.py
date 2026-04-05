from __future__ import annotations

import copy
import json
import sys
import textwrap
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse as sp
import yaml

from .config import REPO_ROOT, load_config
from .coupling_contract import (
    ASSET_STATUS_READY,
    build_coupling_bundle_metadata,
    build_edge_coupling_bundle_reference,
    build_root_coupling_bundle_paths,
)
from .experiment_analysis_contract import (
    ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
    COMPARISON_MATRICES_ARTIFACT_ID,
    EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID,
    METADATA_JSON_KEY as ANALYSIS_BUNDLE_METADATA_JSON_KEY,
    NULL_TEST_TABLE_ARTIFACT_ID,
    OFFLINE_REPORT_INDEX_ARTIFACT_ID,
    OFFLINE_REPORT_SUMMARY_ARTIFACT_ID,
    TASK_SUMMARY_ROWS_ARTIFACT_ID,
    VISUALIZATION_CATALOG_ARTIFACT_ID,
    discover_experiment_analysis_bundle_paths,
    load_experiment_analysis_bundle_metadata,
)
from .geometry_contract import (
    COARSE_OPERATOR_KEY,
    FINE_OPERATOR_KEY,
    OPERATOR_METADATA_KEY,
    RAW_SKELETON_KEY,
    SIMPLIFIED_MESH_KEY,
    TRANSFER_OPERATORS_KEY,
    build_geometry_bundle_paths,
    build_geometry_manifest_record,
    build_operator_bundle_metadata,
    default_asset_statuses,
    write_geometry_manifest,
)
from .io_utils import ensure_dir, write_deterministic_npz, write_json
from .milestone9_readiness import _hash_file, _issue, _resolve_repo_path, _run_command
from .readiness_contract import (
    FOLLOW_ON_READINESS_KEY,
    READINESS_GATE_HOLD,
    READINESS_GATE_REVIEW,
    READY_FOR_FOLLOW_ON_WORK_KEY,
)
from .readout_analysis_contract import (
    ANALYSIS_UI_PAYLOAD_OUTPUT_ID,
    LATENCY_SHIFT_COMPARISON_OUTPUT_ID,
    MILESTONE_1_DECISION_PANEL_OUTPUT_ID,
    MOTION_DECODER_SUMMARY_OUTPUT_ID,
    NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID,
    RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS,
    SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
    WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID,
)
from .shared_readout_analysis import SUPPORTED_SHARED_READOUT_ANALYSIS_METRIC_IDS
from .simulation_planning import (
    discover_simulation_run_plans,
    resolve_manifest_readout_analysis_plan,
    resolve_manifest_simulation_plan,
)
from .simulator_result_contract import (
    METADATA_JSON_KEY,
    METRICS_TABLE_KEY,
    READOUT_TRACES_KEY,
    STATE_SUMMARY_KEY,
    build_selected_asset_reference,
    build_simulator_extension_artifact_record,
    build_simulator_result_bundle_metadata,
    build_simulator_result_bundle_paths,
    write_simulator_result_bundle_metadata,
)
from .stimulus_bundle import record_stimulus_bundle, resolve_stimulus_input
from .stimulus_contract import (
    build_stimulus_bundle_metadata,
    load_stimulus_bundle_metadata,
    write_stimulus_bundle_metadata,
)
from .surface_operators import serialize_sparse_matrix
from .task_decoder_analysis import SUPPORTED_TASK_DECODER_ANALYSIS_METRIC_IDS
from .selection import write_selected_root_roster, write_subset_manifest
from .wave_structure_analysis import (
    SUPPORTED_WAVE_STRUCTURE_METRIC_IDS,
    SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID,
    SURFACE_WAVE_PHASE_MAP_ARTIFACT_ID,
    SURFACE_WAVE_PHASE_MAP_FORMAT,
    SURFACE_WAVE_SUMMARY_ARTIFACT_ID,
)


MILESTONE12_READINESS_REPORT_VERSION = "milestone12_readiness.v1"

DEFAULT_FIXTURE_TEST_TARGETS = (
    "tests.test_manifest_validation",
    "tests.test_simulation_planning",
    "tests.test_readout_analysis_contract",
    "tests.test_shared_readout_analysis",
    "tests.test_task_decoder_analysis",
    "tests.test_wave_structure_analysis",
    "tests.test_experiment_comparison_analysis",
    "tests.test_milestone12_readiness",
)

DEFAULT_DOCUMENTATION_SNIPPETS: dict[str, tuple[str, ...]] = {
    "README.md": (
        "make milestone12-readiness",
        "scripts/22_milestone12_readiness.py",
        "scripts/20_experiment_comparison_analysis.py",
        "scripts/21_visualize_experiment_analysis.py",
        "milestone_12_readiness.md",
        "milestone_12_readiness.json",
        "no local server is required",
    ),
    "docs/pipeline_notes.md": (
        "make milestone12-readiness",
        "scripts/22_milestone12_readiness.py",
        "scripts/20_experiment_comparison_analysis.py",
        "scripts/21_visualize_experiment_analysis.py",
        "milestone_12_readiness.md",
        "milestone_12_readiness.json",
        "no local server is required",
    ),
    "docs/experiment_analysis_bundle_design.md": (
        "make milestone12-readiness",
        "scripts/22_milestone12_readiness.py",
        "scripts/20_experiment_comparison_analysis.py",
        "scripts/21_visualize_experiment_analysis.py",
        "milestone_12_readiness.md",
        "milestone_12_readiness.json",
    ),
}

DEFAULT_ANALYSIS_ACTIVE_METRIC_IDS = (
    "null_direction_suppression_index",
    "response_latency_to_peak_ms",
    "direction_selectivity_index",
    "on_off_selectivity_index",
    "motion_vector_heading_deg",
    "motion_vector_speed_deg_per_s",
    "optic_flow_heading_deg",
    "optic_flow_speed_deg_per_s",
    "synchrony_coherence_index",
    "phase_gradient_mean_rad_per_patch",
    "phase_gradient_dispersion_rad_per_patch",
    "wavefront_speed_patch_per_ms",
    "wavefront_curvature_inv_patch",
    "patch_activation_entropy_bits",
)

DEFAULT_ANALYSIS_OUTPUT_IDS = (
    ANALYSIS_UI_PAYLOAD_OUTPUT_ID,
    MOTION_DECODER_SUMMARY_OUTPUT_ID,
    WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID,
)

DEFAULT_ANALYSIS_WINDOW_OVERRIDES = {
    "shared_response_window": {
        "start_ms": 10.0,
        "end_ms": 60.0,
        "description": "Milestone 12 shared-response verification window.",
    },
    "task_decoder_window": {
        "start_ms": 10.0,
        "end_ms": 60.0,
        "description": "Milestone 12 task-decoder verification window.",
    },
    "wave_diagnostic_window": {
        "start_ms": 10.0,
        "end_ms": 60.0,
        "description": "Milestone 12 wave-diagnostic verification window.",
    },
}

DEFAULT_RETINAL_GEOMETRY = {
    "geometry_family": "ommatidial_lattice",
    "geometry_name": "fixture",
    "eyes": {
        "left": {
            "center_head_mm": [0.17, 0.28, 0.04],
            "optical_axis_head": [0.25881904510252074, 0.9659258262890683, 0.0],
            "torsion_deg": 3.0,
        }
    },
}

EXPECTED_COMPARISON_GROUP_IDS = (
    "geometry_ablation__p0",
    "baseline_strength_challenge__intact",
)

EXPECTED_ARM_PAIR_IDS = (
    "matched_surface_wave_vs_p0__intact",
    "matched_surface_wave_vs_p1__intact",
)

EXPECTED_NULL_TEST_IDS = (
    "geometry_shuffle_collapse",
    "seed_stability",
    "stronger_baseline_survival",
)

REQUIRED_ANALYSIS_OUTPUT_IDS = {
    ANALYSIS_UI_PAYLOAD_OUTPUT_ID,
    LATENCY_SHIFT_COMPARISON_OUTPUT_ID,
    MILESTONE_1_DECISION_PANEL_OUTPUT_ID,
    MOTION_DECODER_SUMMARY_OUTPUT_ID,
    NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID,
    WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID,
}

REQUIRED_ANALYSIS_UI_SECTIONS = (
    "artifact_inventory",
    "task_summary_cards",
    "comparison_cards",
    "analysis_visualizations",
    "shared_comparison",
    "wave_only_diagnostics",
    "mixed_scope",
)

REQUIRED_ANALYSIS_BUNDLE_ARTIFACT_IDS = {
    ANALYSIS_BUNDLE_METADATA_JSON_KEY,
    EXPERIMENT_COMPARISON_SUMMARY_ARTIFACT_ID,
    TASK_SUMMARY_ROWS_ARTIFACT_ID,
    NULL_TEST_TABLE_ARTIFACT_ID,
    COMPARISON_MATRICES_ARTIFACT_ID,
    VISUALIZATION_CATALOG_ARTIFACT_ID,
    ANALYSIS_UI_PAYLOAD_ARTIFACT_ID,
    OFFLINE_REPORT_INDEX_ARTIFACT_ID,
    OFFLINE_REPORT_SUMMARY_ARTIFACT_ID,
}


def build_milestone12_readiness_paths(
    processed_simulator_results_dir: str | Path,
) -> dict[str, Path]:
    root = Path(processed_simulator_results_dir).resolve()
    report_dir = root / "readiness" / "milestone_12"
    return {
        "report_dir": report_dir,
        "markdown_path": report_dir / "milestone_12_readiness.md",
        "json_path": report_dir / "milestone_12_readiness.json",
        "commands_dir": report_dir / "commands",
        "generated_fixture_dir": report_dir / "generated_fixture",
        "visualization_dir": report_dir / "visualization",
    }


def execute_milestone12_readiness_pass(
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
    processed_simulator_results_dir = Path(
        cfg["paths"]["processed_simulator_results_dir"]
    ).resolve()
    verification_cfg = dict(cfg.get("simulation_verification", {}))

    source_manifest_path = _resolve_repo_path(
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

    readiness_paths = build_milestone12_readiness_paths(processed_simulator_results_dir)
    report_dir = ensure_dir(readiness_paths["report_dir"])
    commands_dir = ensure_dir(readiness_paths["commands_dir"])
    generated_fixture_dir = ensure_dir(readiness_paths["generated_fixture_dir"])
    visualization_dir = ensure_dir(readiness_paths["visualization_dir"])

    fixture = _materialize_verification_fixture(
        source_manifest_path=source_manifest_path,
        generated_fixture_dir=generated_fixture_dir,
        processed_stimulus_dir=processed_stimulus_dir,
        processed_retinal_dir=processed_retinal_dir,
        processed_simulator_results_dir=processed_simulator_results_dir,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    analysis_plan_audit = _build_analysis_plan_audit(
        fixture=fixture,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        commands_dir=commands_dir,
    )
    comparison_workflow_audit = _execute_comparison_workflow_audit(
        fixture=fixture,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        commands_dir=commands_dir,
        python_executable=python_executable,
        repo_root=repo_root,
    )
    packaged_export_audit = _audit_packaged_exports(
        comparison_workflow_audit=comparison_workflow_audit,
        commands_dir=commands_dir,
    )
    visualization_audit = _execute_visualization_audit(
        comparison_workflow_audit=comparison_workflow_audit,
        commands_dir=commands_dir,
        python_executable=python_executable,
        repo_root=repo_root,
        output_dir=visualization_dir,
    )
    documentation_audit = _audit_documentation(repo_root=repo_root)
    workflow_coverage = _build_workflow_coverage(
        fixture_verification=fixture_verification,
        analysis_plan_audit=analysis_plan_audit,
        comparison_workflow_audit=comparison_workflow_audit,
        packaged_export_audit=packaged_export_audit,
        visualization_audit=visualization_audit,
        documentation_audit=documentation_audit,
    )

    all_issues = (
        list(analysis_plan_audit["issues"])
        + list(comparison_workflow_audit["issues"])
        + list(packaged_export_audit["issues"])
        + list(visualization_audit["issues"])
        + list(documentation_audit["issues"])
    )
    blocking_issues = [
        issue for issue in all_issues if str(issue.get("severity", "")) == "blocking"
    ]
    review_issues = [
        issue for issue in all_issues if str(issue.get("severity", "")) == "review"
    ]
    if (
        str(fixture_verification.get("status", "")) != "pass"
        or blocking_issues
        or not all(workflow_coverage.values())
    ):
        readiness_status = READINESS_GATE_HOLD
    elif review_issues:
        readiness_status = READINESS_GATE_REVIEW
    else:
        readiness_status = "ready"

    remaining_risks = [
        {
            "risk_id": "M12-RISK-001",
            "category": "scientific",
            "severity": "non_blocking",
            "summary": (
                "This readiness pass proves deterministic contract integration on one synthetic "
                "Milestone 1-style fixture. It does not establish biological calibration, task "
                "generalization, or quantitative acceptance thresholds for later validation work."
            ),
            "guidance": (
                "Milestone 13 should treat this as the contract baseline, then add numerical and "
                "biological checks before making stronger scientific claims."
            ),
        },
        {
            "risk_id": "M12-RISK-002",
            "category": "engineering",
            "severity": "non_blocking",
            "summary": (
                "The readiness fixture exercises one representative manifest, one shared readout, "
                "and one local patch context. It does not yet stress larger bundle inventories, "
                "richer readout catalogs, or dashboard-scale browsing behavior."
            ),
            "guidance": (
                "Milestone 14 should preserve contract-based discovery and add one broader "
                "multi-readout fixture before hard-coding dashboard assumptions."
            ),
        },
    ]
    follow_on_issues = [
        {
            "ticket_id": "FW-M12-FOLLOW-001",
            "severity": "non_blocking",
            "title": "Add one broader Milestone 12 fixture with multiple shared readouts and more than one local patch center.",
            "summary": (
                "The shipped readiness pass now proves the canonical Milestone 12 workflow on a "
                "deterministic fixture, but it still centers on one shared readout channel and one "
                "retinotopic patch context."
            ),
            "reproduction": (
                "Run `make milestone12-readiness`, inspect "
                f"`{fixture['fixture_config_path']}`, and compare the analysis-plan audit plus the "
                "packaged UI payload. The current fixture covers the full contract surface, but it "
                "does not yet stress multi-readout dashboard composition."
            ),
        },
        {
            "ticket_id": "FW-M12-FOLLOW-002",
            "severity": "non_blocking",
            "title": "Extend Milestone 13 validation to put quantitative thresholds on task-decoder and wave-diagnostic outputs.",
            "summary": (
                "Milestone 12 readiness now verifies that the task layer is quantitative and "
                "discoverable, but the pass still uses synthetic fixture traces rather than a "
                "numerically or biologically anchored validation ladder."
            ),
            "reproduction": (
                "Run `make milestone12-readiness`, then inspect the markdown report under "
                f"`{readiness_paths['markdown_path']}`. The report shows task-decoder outputs, "
                "wave diagnostics, null tests, and packaged exports are wired together, but it "
                "does not declare domain-specific acceptance thresholds."
            ),
        },
    ]

    visualization_report_path = str(visualization_audit.get("report_path", ""))
    visualization_report_file_url = str(visualization_audit.get("report_file_url", ""))
    visualization_open_hint = str(visualization_audit.get("viewer_open_hint", ""))
    verification_commands = [
        "make milestone12-readiness",
        (
            "python scripts/20_experiment_comparison_analysis.py "
            f"--config {fixture['fixture_config_path']} "
            f"--manifest {fixture['fixture_manifest_path']} "
            f"--schema {schema_path} "
            f"--design-lock {design_lock_path} "
            f"--output {fixture['analysis_summary_output_path']}"
        ),
        (
            "python scripts/21_visualize_experiment_analysis.py "
            f"--analysis-bundle {comparison_workflow_audit.get('analysis_bundle_metadata_path', '')} "
            f"--output-dir {visualization_dir}"
        ),
    ]

    summary = {
        "report_version": MILESTONE12_READINESS_REPORT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "report_dir": str(report_dir.resolve()),
        "markdown_path": str(readiness_paths["markdown_path"].resolve()),
        "json_path": str(readiness_paths["json_path"].resolve()),
        "commands_dir": str(commands_dir.resolve()),
        "generated_fixture_dir": str(generated_fixture_dir.resolve()),
        "source_manifest_path": str(source_manifest_path.resolve()),
        "schema_path": str(schema_path.resolve()),
        "design_lock_path": str(design_lock_path.resolve()),
        "fixture_manifest_path": fixture["fixture_manifest_path"],
        "fixture_config_path": fixture["fixture_config_path"],
        "fixture_assets_dir": fixture["fixture_assets_dir"],
        "analysis_summary_output_path": fixture["analysis_summary_output_path"],
        "visualization_report_path": visualization_report_path,
        "visualization_report_file_url": visualization_report_file_url,
        "visualization_open_hint": visualization_open_hint,
        "fixture": fixture,
        "fixture_verification": copy.deepcopy(dict(fixture_verification)),
        "analysis_plan_audit": analysis_plan_audit,
        "comparison_workflow_audit": comparison_workflow_audit,
        "packaged_export_audit": packaged_export_audit,
        "visualization_audit": visualization_audit,
        "documentation_audit": documentation_audit,
        "workflow_coverage": workflow_coverage,
        "remaining_risks": remaining_risks,
        "follow_on_issues": follow_on_issues,
        "documented_verification_command": "make milestone12-readiness",
        "explicit_verification_command": (
            "python scripts/22_milestone12_readiness.py "
            "--config config/milestone_12_verification.yaml"
        ),
        "verification_command_sequence": verification_commands,
        "readiness_scope_note": (
            "The shipped readiness pass exercises analysis-plan resolution, shared-readout "
            "kernels, task decoders, wave diagnostics, experiment-level comparison "
            "orchestration, packaged exports, and UI-payload discovery on deterministic "
            "local fixture bundles. It proves software-contract coherence, not biological "
            "validation."
        ),
        FOLLOW_ON_READINESS_KEY: {
            "status": readiness_status,
            READY_FOR_FOLLOW_ON_WORK_KEY: bool(readiness_status != READINESS_GATE_HOLD),
            "ready_for_milestones": (
                ["milestone_13_validation_ladder", "milestone_14_dashboard"]
                if readiness_status != READINESS_GATE_HOLD
                else []
            ),
            "local_analysis_gate": readiness_status,
        },
    }

    readiness_paths["markdown_path"].write_text(
        _render_milestone12_readiness_markdown(summary=summary),
        encoding="utf-8",
    )
    write_json(summary, readiness_paths["json_path"])
    return summary


def _materialize_verification_fixture(
    *,
    source_manifest_path: Path,
    generated_fixture_dir: Path,
    processed_stimulus_dir: Path,
    processed_retinal_dir: Path,
    processed_simulator_results_dir: Path,
    schema_path: Path,
    design_lock_path: Path,
) -> dict[str, Any]:
    fixture_assets_dir = ensure_dir(generated_fixture_dir / "fixture_assets")
    fixture_manifest_path = (generated_fixture_dir / "fixture_manifest.yaml").resolve()
    fixture_config_path = (generated_fixture_dir / "simulation_fixture_config.yaml").resolve()
    analysis_summary_output_path = (generated_fixture_dir / "analysis_summary.json").resolve()

    manifest_payload = yaml.safe_load(source_manifest_path.read_text(encoding="utf-8"))
    subset_name = str(manifest_payload["subset_name"])
    fixture_manifest_path.write_text(
        yaml.safe_dump(manifest_payload, sort_keys=False),
        encoding="utf-8",
    )
    _write_simulation_fixture(
        config_path=fixture_config_path,
        fixture_assets_dir=fixture_assets_dir,
        processed_stimulus_dir=processed_stimulus_dir,
        processed_retinal_dir=processed_retinal_dir,
        processed_simulator_results_dir=processed_simulator_results_dir,
        subset_name=subset_name,
    )
    _record_fixture_stimulus_bundle(
        manifest_path=fixture_manifest_path,
        processed_stimulus_dir=processed_stimulus_dir,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    simulation_plan = resolve_manifest_simulation_plan(
        manifest_path=fixture_manifest_path,
        config_path=fixture_config_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    default_stimulus_metadata = _load_default_stimulus_metadata(simulation_plan)
    condition_stimuli = _materialize_condition_stimuli(
        processed_stimulus_dir=processed_stimulus_dir,
        analysis_plan=simulation_plan["readout_analysis_plan"],
        default_stimulus_metadata=default_stimulus_metadata,
    )
    run_plans = discover_simulation_run_plans(
        simulation_plan,
        use_manifest_seed_sweep=True,
    )
    bundle_metadata_records = _materialize_simulator_bundles(
        run_plans=run_plans,
        condition_stimuli=condition_stimuli,
    )
    seed_values = sorted(
        {
            int(item["seed"])
            for item in bundle_metadata_records
        }
    )
    return {
        "fixture_manifest_path": str(fixture_manifest_path),
        "fixture_config_path": str(fixture_config_path),
        "fixture_assets_dir": str(fixture_assets_dir.resolve()),
        "analysis_summary_output_path": str(analysis_summary_output_path),
        "bundle_inventory_count": len(bundle_metadata_records),
        "condition_signature_count": len(condition_stimuli),
        "arm_count": len(simulation_plan["arm_plans"]),
        "seed_values": seed_values,
        "bundle_metadata_records": [
            {
                "metadata_path": str(item["metadata_path"]),
                "arm_id": str(item["arm_id"]),
                "seed": int(item["seed"]),
                "condition_ids": list(item["condition_ids"]),
            }
            for item in bundle_metadata_records
        ],
    }


def _write_simulation_fixture(
    *,
    config_path: Path,
    fixture_assets_dir: Path,
    processed_stimulus_dir: Path,
    processed_retinal_dir: Path,
    processed_simulator_results_dir: Path,
    root_specs: list[dict[str, object]] | None = None,
    subset_name: str = "motion_minimal",
) -> None:
    normalized_root_specs = _normalize_root_specs(root_specs)
    analysis_output_dir = fixture_assets_dir / "analysis_outputs"
    selected_root_ids = [spec["root_id"] for spec in normalized_root_specs]
    selected_root_ids_path = fixture_assets_dir / "selected_root_ids.txt"
    write_selected_root_roster(selected_root_ids, selected_root_ids_path)

    write_subset_manifest(
        subset_output_dir=fixture_assets_dir / "subsets",
        preset_name=subset_name,
        root_ids=selected_root_ids,
    )

    _write_geometry_manifest_fixture(fixture_assets_dir, root_specs=normalized_root_specs)

    config_payload: dict[str, object] = {
        "paths": {
            "selected_root_ids": str(selected_root_ids_path),
            "subset_output_dir": str(fixture_assets_dir / "subsets"),
            "manifest_json": str(fixture_assets_dir / "asset_manifest.json"),
            "processed_stimulus_dir": str(processed_stimulus_dir),
            "processed_retinal_dir": str(processed_retinal_dir),
            "processed_simulator_results_dir": str(processed_simulator_results_dir),
        },
        "selection": {
            "active_preset": subset_name,
        },
        "simulation": {
            "input": {
                "source_kind": "stimulus_bundle",
                "require_recorded_bundle": True,
            },
            "readout_catalog": [
                {
                    "readout_id": "shared_output_mean",
                    "scope": "circuit_output",
                    "aggregation": "mean_over_root_ids",
                    "units": "activation_au",
                    "value_semantics": "shared_downstream_activation",
                    "description": "Shared downstream output mean for matched comparisons.",
                },
                {
                    "readout_id": "direction_selectivity_index",
                    "scope": "comparison_panel",
                    "aggregation": "identity",
                    "units": "unitless",
                    "value_semantics": "direction_selectivity_index",
                    "description": "Shared direction-selectivity summary for matched comparisons.",
                },
            ],
            "baseline_families": {
                "P0": {
                    "membrane_time_constant_ms": 12.5,
                    "recurrent_gain": 0.9,
                },
                "P1": {
                    "membrane_time_constant_ms": 15.0,
                    "synaptic_current_time_constant_ms": 6.0,
                    "delay_handling": {
                        "mode": "from_coupling_bundle",
                        "max_supported_delay_steps": 32,
                    },
                },
            },
            "surface_wave": {
                "parameter_preset": "motion_patch_reference",
                "propagation": {
                    "wave_speed_sq_scale": 1.25,
                    "restoring_strength_per_ms2": 0.07,
                },
                "damping": {
                    "gamma_per_ms": 0.18,
                },
                "recovery": {
                    "mode": "activity_driven_first_order",
                    "time_constant_ms": 14.0,
                    "drive_gain": 0.3,
                    "coupling_strength_per_ms2": 0.12,
                },
                "nonlinearity": {
                    "mode": "tanh_soft_clip",
                    "activation_scale": 1.1,
                },
                "anisotropy": {
                    "mode": "operator_embedded",
                    "strength_scale": 1.05,
                },
            },
            "timebase": {
                "dt_ms": 10.0,
                "sample_count": 7,
                "duration_ms": 70.0,
            },
        },
        "analysis": {
            "active_metric_ids": list(DEFAULT_ANALYSIS_ACTIVE_METRIC_IDS),
            "output_ids": list(DEFAULT_ANALYSIS_OUTPUT_IDS),
            "analysis_windows": copy.deepcopy(DEFAULT_ANALYSIS_WINDOW_OVERRIDES),
            "experiment_output_targets": [
                {
                    "output_id": ANALYSIS_UI_PAYLOAD_OUTPUT_ID,
                    "path": str(analysis_output_dir / "analysis_ui_payload.json"),
                },
                {
                    "output_id": MOTION_DECODER_SUMMARY_OUTPUT_ID,
                    "path": str(analysis_output_dir / "motion_decoder_summary.json"),
                },
                {
                    "output_id": WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID,
                    "path": str(analysis_output_dir / "wave_diagnostic_summary.json"),
                },
            ],
        },
        "retinal_geometry": copy.deepcopy(DEFAULT_RETINAL_GEOMETRY),
    }
    config_path.write_text(
        yaml.safe_dump(config_payload, sort_keys=False),
        encoding="utf-8",
    )


def _record_fixture_stimulus_bundle(
    *,
    manifest_path: Path,
    processed_stimulus_dir: Path,
    schema_path: Path,
    design_lock_path: Path,
) -> None:
    resolved_input = resolve_stimulus_input(
        manifest_path=manifest_path,
        schema_path=schema_path,
        design_lock_path=design_lock_path,
        processed_stimulus_dir=processed_stimulus_dir,
    )
    record_stimulus_bundle(resolved_input)


def _load_default_stimulus_metadata(
    simulation_plan: Mapping[str, Any],
) -> dict[str, Any]:
    arm_plan = simulation_plan["arm_plans"][0]
    input_asset = next(
        item
        for item in arm_plan["selected_assets"]
        if str(item["asset_role"]) == "input_bundle"
        and str(item["artifact_type"]) == "stimulus_bundle"
    )
    return load_stimulus_bundle_metadata(Path(input_asset["path"]))


def _materialize_condition_stimuli(
    *,
    processed_stimulus_dir: Path,
    analysis_plan: Mapping[str, Any],
    default_stimulus_metadata: Mapping[str, Any],
) -> dict[tuple[str, ...], dict[str, Any]]:
    conditions_by_parameter: dict[str, list[dict[str, Any]]] = {}
    for item in analysis_plan["condition_catalog"]:
        conditions_by_parameter.setdefault(str(item["parameter_name"]), []).append(
            copy.deepcopy(dict(item))
        )
    for values in conditions_by_parameter.values():
        values.sort(key=lambda item: str(item["condition_id"]))

    combos: list[list[dict[str, Any]]] = [[]]
    for parameter_name in sorted(conditions_by_parameter):
        next_combos: list[list[dict[str, Any]]] = []
        for prefix in combos:
            for item in conditions_by_parameter[parameter_name]:
                next_combos.append([*prefix, copy.deepcopy(dict(item))])
        combos = next_combos

    metadata_by_signature: dict[tuple[str, ...], dict[str, Any]] = {}
    for combo in combos:
        condition_ids = tuple(sorted(str(item["condition_id"]) for item in combo))
        parameter_snapshot = copy.deepcopy(
            dict(default_stimulus_metadata["parameter_snapshot"])
        )
        parameter_snapshot.setdefault("center_azimuth_deg", 5.0)
        parameter_snapshot.setdefault("center_elevation_deg", -2.0)
        parameter_snapshot.setdefault("velocity_deg_per_s", 45.0)
        for item in combo:
            parameter_snapshot[str(item["parameter_name"])] = copy.deepcopy(
                item["value"]
            )
        stimulus_metadata = build_stimulus_bundle_metadata(
            stimulus_family=str(default_stimulus_metadata["stimulus_family"]),
            stimulus_name=str(default_stimulus_metadata["stimulus_name"]),
            parameter_snapshot=parameter_snapshot,
            seed=int(default_stimulus_metadata["determinism"]["seed"]),
            temporal_sampling=default_stimulus_metadata["temporal_sampling"],
            spatial_frame=default_stimulus_metadata["spatial_frame"],
            processed_stimulus_dir=processed_stimulus_dir,
            luminance_convention=default_stimulus_metadata["luminance_convention"],
            representation_family=str(default_stimulus_metadata["representation_family"]),
            rng_family=str(default_stimulus_metadata["determinism"]["rng_family"]),
        )
        write_stimulus_bundle_metadata(stimulus_metadata)
        metadata_by_signature[condition_ids] = stimulus_metadata
    return metadata_by_signature


def _materialize_simulator_bundles(
    *,
    run_plans: list[dict[str, Any]],
    condition_stimuli: Mapping[tuple[str, ...], Mapping[str, Any]],
) -> list[dict[str, Any]]:
    metadata_paths: list[dict[str, Any]] = []
    for run_plan in run_plans:
        for condition_ids, stimulus_metadata in condition_stimuli.items():
            selected_assets = _replace_input_bundle_asset(
                run_plan["selected_assets"],
                stimulus_metadata,
            )
            bundle_metadata = build_simulator_result_bundle_metadata(
                manifest_reference=run_plan["manifest_reference"],
                arm_reference=run_plan["arm_reference"],
                determinism=run_plan["determinism"],
                timebase=run_plan["runtime"]["timebase"],
                selected_assets=selected_assets,
                readout_catalog=run_plan["runtime"]["shared_readout_catalog"],
                processed_simulator_results_dir=run_plan["runtime"][
                    "processed_simulator_results_dir"
                ],
                state_summary_status="ready",
                readout_traces_status="ready",
                metrics_table_status="ready",
            )
            if str(run_plan["arm_reference"]["model_mode"]) == "surface_wave":
                bundle_paths = build_simulator_result_bundle_paths(
                    experiment_id=str(run_plan["manifest_reference"]["experiment_id"]),
                    arm_id=str(run_plan["arm_reference"]["arm_id"]),
                    run_spec_hash=str(bundle_metadata["run_spec_hash"]),
                    processed_simulator_results_dir=run_plan["runtime"][
                        "processed_simulator_results_dir"
                    ],
                )
                model_artifacts = [
                    build_simulator_extension_artifact_record(
                        bundle_paths=bundle_paths,
                        artifact_id=SURFACE_WAVE_SUMMARY_ARTIFACT_ID,
                        file_name="surface_wave_summary.json",
                        format="json_surface_wave_execution_summary.v1",
                        status="ready",
                        artifact_scope="wave_model_extension",
                        description="Fixture packaged surface-wave summary.",
                    ),
                    build_simulator_extension_artifact_record(
                        bundle_paths=bundle_paths,
                        artifact_id=SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID,
                        file_name="surface_wave_patch_traces.npz",
                        format="npz_surface_wave_patch_traces.v1",
                        status="ready",
                        artifact_scope="wave_model_extension",
                        description="Fixture patch-trace export for Milestone 12 readiness.",
                    ),
                    build_simulator_extension_artifact_record(
                        bundle_paths=bundle_paths,
                        artifact_id=SURFACE_WAVE_PHASE_MAP_ARTIFACT_ID,
                        file_name="surface_wave_phase_map.npz",
                        format=SURFACE_WAVE_PHASE_MAP_FORMAT,
                        status="ready",
                        artifact_scope="wave_model_extension",
                        description="Fixture phase-map export for Milestone 12 readiness.",
                    ),
                ]
                bundle_metadata = build_simulator_result_bundle_metadata(
                    manifest_reference=run_plan["manifest_reference"],
                    arm_reference=run_plan["arm_reference"],
                    determinism=run_plan["determinism"],
                    timebase=run_plan["runtime"]["timebase"],
                    selected_assets=selected_assets,
                    readout_catalog=run_plan["runtime"]["shared_readout_catalog"],
                    processed_simulator_results_dir=run_plan["runtime"][
                        "processed_simulator_results_dir"
                    ],
                    state_summary_status="ready",
                    readout_traces_status="ready",
                    metrics_table_status="ready",
                    model_artifacts=model_artifacts,
                )
            metadata_path = write_simulator_result_bundle_metadata(bundle_metadata)
            _write_bundle_artifacts(
                bundle_metadata=bundle_metadata,
                trace_values=_bundle_trace_values(
                    arm_id=str(run_plan["arm_reference"]["arm_id"]),
                    seed=int(run_plan["determinism"]["seed"]),
                    condition_ids=condition_ids,
                ),
            )
            metadata_paths.append(
                {
                    "metadata_path": metadata_path,
                    "arm_id": str(run_plan["arm_reference"]["arm_id"]),
                    "seed": int(run_plan["determinism"]["seed"]),
                    "condition_ids": list(condition_ids),
                }
            )
    return metadata_paths


def _replace_input_bundle_asset(
    selected_assets: list[dict[str, Any]],
    stimulus_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    replaced: list[dict[str, Any]] = []
    for item in selected_assets:
        if (
            str(item["asset_role"]) == "input_bundle"
            and str(item["artifact_type"]) == "stimulus_bundle"
        ):
            replaced.append(
                build_selected_asset_reference(
                    asset_role=str(item["asset_role"]),
                    artifact_type="stimulus_bundle",
                    path=Path(stimulus_metadata["assets"]["metadata_json"]["path"]),
                    contract_version=str(stimulus_metadata["contract_version"]),
                    artifact_id=item.get("artifact_id"),
                    bundle_id=str(stimulus_metadata["bundle_id"]),
                )
            )
            continue
        replaced.append(copy.deepcopy(dict(item)))
    return replaced


def _write_bundle_artifacts(
    *,
    bundle_metadata: Mapping[str, Any],
    trace_values: np.ndarray,
) -> None:
    artifacts = bundle_metadata["artifacts"]
    timebase = bundle_metadata["timebase"]
    sample_count = int(timebase["sample_count"])
    dt_ms = float(timebase["dt_ms"])
    time_origin_ms = float(timebase["time_origin_ms"])
    time_ms = np.asarray(
        [time_origin_ms + index * dt_ms for index in range(sample_count)],
        dtype=np.float64,
    )
    readout_ids = np.asarray(
        [str(item["readout_id"]) for item in bundle_metadata["readout_catalog"]],
        dtype="<U64",
    )
    if trace_values.shape != (sample_count, len(readout_ids)):
        raise ValueError(
            f"trace_values must have shape {(sample_count, len(readout_ids))!r}, "
            f"got {trace_values.shape!r}."
        )
    state_summary_path = Path(artifacts[STATE_SUMMARY_KEY]["path"]).resolve()
    metrics_path = Path(artifacts[METRICS_TABLE_KEY]["path"]).resolve()
    readout_path = Path(artifacts[READOUT_TRACES_KEY]["path"]).resolve()
    write_json([], state_summary_path)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        "metric_id,readout_id,scope,window_id,statistic,value,units\n",
        encoding="utf-8",
    )
    write_deterministic_npz(
        {
            "time_ms": time_ms,
            "readout_ids": readout_ids,
            "values": np.asarray(trace_values, dtype=np.float64),
        },
        readout_path,
    )
    model_artifacts = {
        str(item["artifact_id"]): dict(item)
        for item in bundle_metadata["artifacts"].get("model_artifacts", [])
    }
    if SURFACE_WAVE_SUMMARY_ARTIFACT_ID in model_artifacts:
        write_json(
            {
                "format_version": "json_surface_wave_execution_summary.v1",
                "runtime_metadata_by_root": [
                    {
                        "root_id": 101,
                        "morphology_class": "surface_neuron",
                        "patch_count": 2,
                        "source_reference": {},
                    },
                    {
                        "root_id": 202,
                        "morphology_class": "surface_neuron",
                        "patch_count": 2,
                        "source_reference": {},
                    },
                ],
                "wave_specific_artifacts": {
                    "patch_traces_artifact_id": SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID,
                    "phase_map_artifact_id": SURFACE_WAVE_PHASE_MAP_ARTIFACT_ID,
                },
            },
            Path(model_artifacts[SURFACE_WAVE_SUMMARY_ARTIFACT_ID]["path"]).resolve(),
        )
    if SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID in model_artifacts:
        patch_root_101 = np.asarray(
            [
                [0.12, 0.18],
                [0.18, 0.34],
                [0.36, 0.68],
                [0.72, 1.04],
                [0.58, 0.82],
                [0.24, 0.42],
                [0.12, 0.18],
            ],
            dtype=np.float64,
        )[:sample_count]
        patch_root_202 = np.asarray(
            [
                [0.08, 0.14],
                [0.14, 0.24],
                [0.26, 0.44],
                [0.44, 0.72],
                [0.38, 0.56],
                [0.18, 0.28],
                [0.08, 0.14],
            ],
            dtype=np.float64,
        )[:sample_count]
        write_deterministic_npz(
            {
                "substep_time_ms": time_ms,
                "root_101_patch_activation": patch_root_101,
                "root_202_patch_activation": patch_root_202,
            },
            Path(model_artifacts[SURFACE_WAVE_PATCH_TRACES_ARTIFACT_ID]["path"]).resolve(),
        )
    if SURFACE_WAVE_PHASE_MAP_ARTIFACT_ID in model_artifacts:
        phase_root_101 = np.asarray(
            [
                [0.0, 0.4],
                [0.2, 0.6],
                [0.4, 0.8],
                [0.6, 1.0],
                [0.8, 1.2],
                [1.0, 1.4],
                [1.2, 1.6],
            ],
            dtype=np.float64,
        )[:sample_count]
        phase_root_202 = np.asarray(
            [
                [0.1, 0.45],
                [0.3, 0.65],
                [0.5, 0.85],
                [0.7, 1.05],
                [0.9, 1.25],
                [1.1, 1.45],
                [1.3, 1.65],
            ],
            dtype=np.float64,
        )[:sample_count]
        write_deterministic_npz(
            {
                "substep_time_ms": time_ms,
                "root_ids": np.asarray([101, 202], dtype=np.int64),
                "root_101_phase_rad": phase_root_101,
                "root_202_phase_rad": phase_root_202,
            },
            Path(model_artifacts[SURFACE_WAVE_PHASE_MAP_ARTIFACT_ID]["path"]).resolve(),
        )


def _bundle_trace_values(
    *,
    arm_id: str,
    seed: int,
    condition_ids: tuple[str, ...],
) -> np.ndarray:
    base_peak_by_condition = {
        ("null_direction", "off_polarity"): 1.5,
        ("null_direction", "on_polarity"): 2.4,
        ("off_polarity", "preferred_direction"): 3.5,
        ("on_polarity", "preferred_direction"): 5.0,
    }
    arm_adjustments = {
        "baseline_p0_intact": {"preferred_delta": 0.0, "null_delta": 0.0, "peak_index": 2},
        "baseline_p0_shuffled": {"preferred_delta": 0.0, "null_delta": 0.0, "peak_index": 2},
        "surface_wave_intact": {"preferred_delta": 1.4, "null_delta": -1.0, "peak_index": 1},
        "surface_wave_shuffled": {"preferred_delta": 0.6, "null_delta": -0.3, "peak_index": 2},
        "baseline_p1_intact": {"preferred_delta": 0.6, "null_delta": -0.5, "peak_index": 2},
        "baseline_p1_shuffled": {"preferred_delta": 0.4, "null_delta": -0.2, "peak_index": 2},
    }
    seed_offsets = {
        11: 0.0,
        17: 0.1,
        23: 0.2,
    }
    normalized_condition_ids = tuple(sorted(condition_ids))
    base_peak = float(base_peak_by_condition[normalized_condition_ids])
    adjustment = arm_adjustments[arm_id]
    is_preferred = "preferred_direction" in set(normalized_condition_ids)
    adjusted_peak = base_peak + (
        float(adjustment["preferred_delta"])
        if is_preferred
        else float(adjustment["null_delta"])
    )
    response = _response_profile(
        peak=max(0.5, adjusted_peak + float(seed_offsets.get(int(seed), 0.0))),
        peak_index=int(adjustment["peak_index"]),
    )
    values = np.asarray([2.0, *[2.0 + value for value in response]], dtype=np.float64)
    return values.reshape(-1, 1)


def _response_profile(*, peak: float, peak_index: int) -> list[float]:
    if peak_index == 1:
        return [0.0, peak, peak * 0.55, peak * 0.2, peak * 0.05, 0.0]
    if peak_index == 2:
        return [0.0, peak * 0.2, peak, peak * 0.55, peak * 0.12, 0.0]
    raise ValueError(f"Unsupported peak_index {peak_index!r}.")


def _build_analysis_plan_audit(
    *,
    fixture: Mapping[str, Any],
    schema_path: Path,
    design_lock_path: Path,
    commands_dir: Path,
) -> dict[str, Any]:
    simulation_plan = resolve_manifest_simulation_plan(
        manifest_path=fixture["fixture_manifest_path"],
        config_path=fixture["fixture_config_path"],
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )
    analysis_plan = resolve_manifest_readout_analysis_plan(
        manifest_path=fixture["fixture_manifest_path"],
        config_path=fixture["fixture_config_path"],
        schema_path=schema_path,
        design_lock_path=design_lock_path,
    )

    active_metric_ids = list(analysis_plan["active_metric_ids"])
    active_output_ids = list(analysis_plan["active_output_ids"])
    shared_metric_ids = sorted(
        set(active_metric_ids) & set(SUPPORTED_SHARED_READOUT_ANALYSIS_METRIC_IDS)
    )
    task_metric_ids = sorted(
        set(active_metric_ids) & set(SUPPORTED_TASK_DECODER_ANALYSIS_METRIC_IDS)
    )
    wave_metric_ids = sorted(
        set(active_metric_ids) & set(SUPPORTED_WAVE_STRUCTURE_METRIC_IDS)
    )
    active_output_id_set = set(active_output_ids)
    issues: list[dict[str, str]] = []
    if not shared_metric_ids:
        issues.append(
            _issue(
                "blocking",
                "The Milestone 12 analysis plan did not activate any shared-readout metrics.",
            )
        )
    if not task_metric_ids:
        issues.append(
            _issue(
                "blocking",
                "The Milestone 12 analysis plan did not activate any task-decoder metrics.",
            )
        )
    if not wave_metric_ids:
        issues.append(
            _issue(
                "blocking",
                "The Milestone 12 analysis plan did not activate any wave-only diagnostic metrics.",
            )
        )
    missing_output_ids = sorted(REQUIRED_ANALYSIS_OUTPUT_IDS - active_output_id_set)
    if missing_output_ids:
        issues.append(
            _issue(
                "blocking",
                f"The Milestone 12 analysis plan is missing required output ids {missing_output_ids!r}.",
            )
        )
    artifact_classes = set(analysis_plan["analysis_artifact_classes"])
    for required_class in (
        RETINOTOPIC_CONTEXT_METADATA_ARTIFACT_CLASS,
        SURFACE_WAVE_PHASE_MAP_ARTIFACT_CLASS,
    ):
        if required_class not in artifact_classes:
            issues.append(
                _issue(
                    "blocking",
                    f"The Milestone 12 analysis plan is missing required artifact class {required_class!r}.",
                )
            )
    comparison_group_ids = [
        str(item["group_id"]) for item in analysis_plan["comparison_group_catalog"]
    ]
    for group_id in EXPECTED_COMPARISON_GROUP_IDS:
        if group_id not in comparison_group_ids:
            issues.append(
                _issue(
                    "blocking",
                    f"The normalized analysis plan is missing expected comparison group {group_id!r}.",
                )
            )
    arm_pair_ids = [
        str(item["group_id"]) for item in analysis_plan["arm_pair_catalog"]
    ]
    for group_id in EXPECTED_ARM_PAIR_IDS:
        if group_id not in arm_pair_ids:
            issues.append(
                _issue(
                    "blocking",
                    f"The normalized analysis plan is missing expected arm-pair group {group_id!r}.",
                )
            )
    null_test_ids = [
        str(item["null_test_id"]) for item in analysis_plan["null_test_declarations"]
    ]
    for null_test_id in EXPECTED_NULL_TEST_IDS:
        if null_test_id not in null_test_ids:
            issues.append(
                _issue(
                    "blocking",
                    f"The normalized analysis plan is missing expected null test {null_test_id!r}.",
                )
            )

    audit = {
        "overall_status": _overall_status_from_issues(issues),
        "plan_version": str(analysis_plan["plan_version"]),
        "manifest_experiment_id": str(analysis_plan["manifest_reference"]["experiment_id"]),
        "arm_count": len(simulation_plan["arm_plans"]),
        "seed_values": sorted(
            {
                int(item["determinism"]["seed"])
                for item in discover_simulation_run_plans(
                    simulation_plan,
                    use_manifest_seed_sweep=True,
                )
            }
        ),
        "active_readout_ids": [
            str(item["readout_id"]) for item in analysis_plan["active_shared_readouts"]
        ],
        "active_metric_ids": active_metric_ids,
        "shared_metric_ids": shared_metric_ids,
        "task_metric_ids": task_metric_ids,
        "wave_metric_ids": wave_metric_ids,
        "active_output_ids": active_output_ids,
        "analysis_artifact_classes": sorted(artifact_classes),
        "arm_pair_ids": arm_pair_ids,
        "comparison_group_ids": comparison_group_ids,
        "null_test_ids": null_test_ids,
        "experiment_output_target_ids": [
            str(item["analysis_output_id"] or item["output_id"])
            for item in analysis_plan["experiment_output_targets"]
        ],
        "issues": issues,
    }
    write_json(audit, commands_dir / "analysis_plan_audit.json")
    return audit


def _execute_comparison_workflow_audit(
    *,
    fixture: Mapping[str, Any],
    schema_path: Path,
    design_lock_path: Path,
    commands_dir: Path,
    python_executable: str,
    repo_root: Path,
) -> dict[str, Any]:
    command = [
        python_executable,
        "scripts/20_experiment_comparison_analysis.py",
        "--config",
        str(fixture["fixture_config_path"]),
        "--manifest",
        str(fixture["fixture_manifest_path"]),
        "--schema",
        str(schema_path),
        "--design-lock",
        str(design_lock_path),
        "--output",
        str(fixture["analysis_summary_output_path"]),
    ]
    first = _run_command(name="comparison_workflow_first", command=command, cwd=repo_root)
    second = _run_command(name="comparison_workflow_second", command=command, cwd=repo_root)
    write_json(first, commands_dir / "comparison_workflow_first.json")
    write_json(second, commands_dir / "comparison_workflow_second.json")

    issues: list[dict[str, str]] = []
    first_summary = _parsed_summary_payload(first)
    second_summary = _parsed_summary_payload(second)
    if str(first.get("status")) != "pass":
        issues.append(
            _issue(
                "blocking",
                "The first Milestone 12 comparison workflow command did not complete successfully.",
            )
        )
    if str(second.get("status")) != "pass":
        issues.append(
            _issue(
                "blocking",
                "The second Milestone 12 comparison workflow command did not complete successfully.",
            )
        )
    if first_summary is None or second_summary is None:
        issues.append(
            _issue(
                "blocking",
                "The Milestone 12 comparison workflow did not emit a machine-readable JSON summary.",
            )
        )
    if issues:
        audit = {
            "overall_status": "fail",
            "command": " ".join(command),
            "issues": issues,
        }
        write_json(audit, commands_dir / "comparison_workflow_audit.json")
        return audit

    summary_path = Path(str(fixture["analysis_summary_output_path"])).resolve()
    if not summary_path.exists():
        issues.append(
            _issue(
                "blocking",
                f"The Milestone 12 comparison workflow did not write {summary_path}.",
            )
        )
    written_summary = _load_json_mapping(summary_path) if summary_path.exists() else {}
    packaged = _require_mapping(
        first_summary.get("packaged_analysis_bundle"),
        field_name="comparison_workflow.packaged_analysis_bundle",
    )
    analysis_bundle_metadata_path = Path(str(packaged["metadata_path"])).resolve()
    if not analysis_bundle_metadata_path.exists():
        issues.append(
            _issue(
                "blocking",
                "The Milestone 12 comparison workflow did not produce experiment analysis bundle metadata.",
            )
        )

    if first_summary["summary_version"] != second_summary["summary_version"]:
        issues.append(
            _issue(
                "blocking",
                "Repeated Milestone 12 comparison workflow runs disagreed on summary_version.",
            )
        )
    summary_stable = _comparison_summary_fingerprint(first_summary) == _comparison_summary_fingerprint(
        second_summary
    )
    if not summary_stable:
        issues.append(
            _issue(
                "blocking",
                "Repeated Milestone 12 comparison workflow runs produced different quantitative summaries.",
            )
        )
    artifact_hashes = _capture_analysis_artifact_hashes(first_summary)
    artifact_hashes_stable = artifact_hashes == _capture_analysis_artifact_hashes(second_summary)
    if not artifact_hashes_stable:
        issues.append(
            _issue(
                "blocking",
                "Repeated Milestone 12 comparison workflow runs produced non-deterministic packaged analysis artifacts.",
            )
        )

    shared_rows = list(first_summary["analysis_results"]["shared_readout_analysis"]["metric_rows"])
    task_rows = list(first_summary["analysis_results"]["task_decoder_analysis"]["metric_rows"])
    wave_rows = list(first_summary["analysis_results"]["wave_diagnostic_analysis"]["metric_rows"])
    if not shared_rows:
        issues.append(
            _issue(
                "blocking",
                "The Milestone 12 comparison workflow did not produce any shared-readout analysis rows.",
            )
        )
    if not task_rows:
        issues.append(
            _issue(
                "blocking",
                "The Milestone 12 comparison workflow did not produce any task-decoder analysis rows.",
            )
        )
    if not wave_rows:
        issues.append(
            _issue(
                "blocking",
                "The Milestone 12 comparison workflow did not produce any wave-diagnostic analysis rows.",
            )
        )
    null_test_status_by_id = {
        str(item["null_test_id"]): str(item["status"])
        for item in first_summary["null_test_results"]
    }
    if not all(
        null_test_status_by_id.get(null_test_id) == "pass"
        for null_test_id in EXPECTED_NULL_TEST_IDS
    ):
        issues.append(
            _issue(
                "blocking",
                "The Milestone 12 readiness fixture did not pass the expected null tests.",
            )
        )
    if str(first_summary["milestone_1_decision_panel"]["overall_status"]) != "pass":
        issues.append(
            _issue(
                "blocking",
                "The Milestone 12 readiness fixture did not pass the packaged Milestone 1 decision panel.",
            )
        )

    output_summaries_by_id = {
        str(item["output_id"]): dict(item)
        for item in first_summary["output_summaries"]
    }
    missing_output_summaries = sorted(
        REQUIRED_ANALYSIS_OUTPUT_IDS - set(output_summaries_by_id)
    )
    if missing_output_summaries:
        issues.append(
            _issue(
                "blocking",
                f"The Milestone 12 comparison workflow is missing output summaries {missing_output_summaries!r}.",
            )
        )
    quantitative_comparison_verified = bool(
        first_summary["comparison_detail_rows"]
        and first_summary["group_metric_rollups"]
        and output_summaries_by_id.get(NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID, {}).get(
            "metric_rollups"
        )
        and output_summaries_by_id.get(LATENCY_SHIFT_COMPARISON_OUTPUT_ID, {}).get(
            "metric_rollups"
        )
    )
    if not quantitative_comparison_verified:
        issues.append(
            _issue(
                "blocking",
                "The Milestone 12 comparison workflow did not produce quantitative baseline-versus-wave comparison rollups.",
            )
        )
    if written_summary and written_summary.get("summary_version") != first_summary["summary_version"]:
        issues.append(
            _issue(
                "blocking",
                "The explicit Milestone 12 summary output drifted from the command summary payload.",
            )
        )

    audit = {
        "overall_status": _overall_status_from_issues(issues),
        "command": " ".join(command),
        "summary_path": str(summary_path),
        "analysis_bundle_metadata_path": str(analysis_bundle_metadata_path),
        "analysis_bundle_directory": str(packaged["bundle_directory"]),
        "packaged_report_path": str(packaged["report_path"]),
        "packaged_report_summary_path": str(packaged["report_summary_path"]),
        "summary_stable": summary_stable,
        "artifact_hashes_stable": artifact_hashes_stable,
        "bundle_inventory_count": len(first_summary["bundle_set"]["bundle_inventory"]),
        "shared_metric_row_count": len(shared_rows),
        "task_metric_row_count": len(task_rows),
        "wave_metric_row_count": len(wave_rows),
        "shared_metric_ids_with_rows": sorted({str(item["metric_id"]) for item in shared_rows}),
        "task_metric_ids_with_rows": sorted({str(item["metric_id"]) for item in task_rows}),
        "wave_metric_ids_with_rows": sorted({str(item["metric_id"]) for item in wave_rows}),
        "comparison_group_ids": [
            str(item["group_id"]) for item in first_summary["comparison_group_catalog"]
        ],
        "null_test_status_by_id": null_test_status_by_id,
        "decision_panel_status": str(
            first_summary["milestone_1_decision_panel"]["overall_status"]
        ),
        "quantitative_comparison_verified": quantitative_comparison_verified,
        "issues": issues,
    }
    write_json(audit, commands_dir / "comparison_workflow_audit.json")
    return audit


def _audit_packaged_exports(
    *,
    comparison_workflow_audit: Mapping[str, Any],
    commands_dir: Path,
) -> dict[str, Any]:
    metadata_path_value = comparison_workflow_audit.get("analysis_bundle_metadata_path")
    issues: list[dict[str, str]] = []
    if not metadata_path_value:
        audit = {
            "overall_status": "fail",
            "issues": [
                _issue(
                    "blocking",
                    "The packaged-export audit could not start because the comparison workflow did not produce analysis bundle metadata.",
                )
            ],
        }
        write_json(audit, commands_dir / "packaged_export_audit.json")
        return audit

    metadata_path = Path(str(metadata_path_value)).resolve()
    metadata = load_experiment_analysis_bundle_metadata(metadata_path)
    discovered_paths = discover_experiment_analysis_bundle_paths(metadata)
    discovered_artifact_ids = set(discovered_paths)
    missing_artifact_ids = sorted(REQUIRED_ANALYSIS_BUNDLE_ARTIFACT_IDS - discovered_artifact_ids)
    if missing_artifact_ids:
        issues.append(
            _issue(
                "blocking",
                f"The packaged Milestone 12 analysis bundle is missing required artifacts {missing_artifact_ids!r}.",
            )
        )
    missing_files = [
        artifact_id
        for artifact_id, path in discovered_paths.items()
        if artifact_id in REQUIRED_ANALYSIS_BUNDLE_ARTIFACT_IDS and not Path(path).exists()
    ]
    if missing_files:
        issues.append(
            _issue(
                "blocking",
                f"The packaged Milestone 12 analysis bundle has missing artifact files {missing_files!r}.",
            )
        )

    ui_payload = _load_json_mapping(discovered_paths[ANALYSIS_UI_PAYLOAD_ARTIFACT_ID])
    comparison_matrices = _load_json_mapping(discovered_paths[COMPARISON_MATRICES_ARTIFACT_ID])
    visualization_catalog = _load_json_mapping(discovered_paths[VISUALIZATION_CATALOG_ARTIFACT_ID])

    missing_ui_sections = [
        section for section in REQUIRED_ANALYSIS_UI_SECTIONS if section not in ui_payload
    ]
    if missing_ui_sections:
        issues.append(
            _issue(
                "blocking",
                f"The analysis UI payload is missing required sections {missing_ui_sections!r}.",
            )
        )
    phase_map_references = list(visualization_catalog.get("phase_map_references", []))
    if not phase_map_references:
        issues.append(
            _issue(
                "blocking",
                "The packaged visualization catalog did not preserve any phase-map references.",
            )
        )
    matrix_ids = [
        str(item["matrix_id"])
        for item in comparison_matrices.get("matrices", [])
        if isinstance(item, Mapping)
    ]
    if "shared_task_rollup_matrix" not in matrix_ids:
        issues.append(
            _issue(
                "blocking",
                "The packaged comparison matrices are missing the shared task rollup matrix.",
            )
        )
    if "wave_diagnostic_rollup_matrix" not in matrix_ids:
        issues.append(
            _issue(
                "blocking",
                "The packaged comparison matrices are missing the wave diagnostic rollup matrix.",
            )
        )
    comparison_card_output_ids = [
        str(item["output_id"])
        for item in ui_payload.get("comparison_cards", [])
        if isinstance(item, Mapping)
    ]
    for output_id in (
        NULL_DIRECTION_SUPPRESSION_COMPARISON_OUTPUT_ID,
        LATENCY_SHIFT_COMPARISON_OUTPUT_ID,
        MOTION_DECODER_SUMMARY_OUTPUT_ID,
        WAVE_DIAGNOSTIC_SUMMARY_OUTPUT_ID,
    ):
        if output_id not in comparison_card_output_ids:
            issues.append(
                _issue(
                    "blocking",
                    f"The packaged UI payload is missing comparison card output_id {output_id!r}.",
                )
            )
    offline_report_ref = _require_mapping(
        _require_mapping(
            ui_payload.get("analysis_visualizations"),
            field_name="analysis_ui_payload.analysis_visualizations",
        ).get("offline_report"),
        field_name="analysis_ui_payload.analysis_visualizations.offline_report",
    )
    if str(offline_report_ref["path"]) != str(
        Path(discovered_paths[OFFLINE_REPORT_INDEX_ARTIFACT_ID]).resolve()
    ):
        issues.append(
            _issue(
                "blocking",
                "The packaged UI payload offline report reference drifted from the bundle discovery path.",
            )
        )

    audit = {
        "overall_status": _overall_status_from_issues(issues),
        "metadata_path": str(metadata_path),
        "bundle_directory": str(metadata["bundle_layout"]["bundle_directory"]),
        "artifact_ids": sorted(discovered_artifact_ids),
        "comparison_card_output_ids": comparison_card_output_ids,
        "comparison_matrix_ids": matrix_ids,
        "phase_map_reference_count": len(phase_map_references),
        "analysis_ui_payload_path": str(discovered_paths[ANALYSIS_UI_PAYLOAD_ARTIFACT_ID]),
        "visualization_catalog_path": str(discovered_paths[VISUALIZATION_CATALOG_ARTIFACT_ID]),
        "offline_report_path": str(discovered_paths[OFFLINE_REPORT_INDEX_ARTIFACT_ID]),
        "issues": issues,
    }
    write_json(audit, commands_dir / "packaged_export_audit.json")
    return audit


def _execute_visualization_audit(
    *,
    comparison_workflow_audit: Mapping[str, Any],
    commands_dir: Path,
    python_executable: str,
    repo_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    metadata_path_value = comparison_workflow_audit.get("analysis_bundle_metadata_path")
    issues: list[dict[str, str]] = []
    if not metadata_path_value:
        audit = {
            "overall_status": "fail",
            "issues": [
                _issue(
                    "blocking",
                    "The visualization audit could not start because the comparison workflow did not produce analysis bundle metadata.",
                )
            ],
        }
        write_json(audit, commands_dir / "visualization_audit.json")
        return audit

    command = [
        python_executable,
        "scripts/21_visualize_experiment_analysis.py",
        "--analysis-bundle",
        str(metadata_path_value),
        "--output-dir",
        str(output_dir),
    ]
    first = _run_command(name="visualization_first", command=command, cwd=repo_root)
    second = _run_command(name="visualization_second", command=command, cwd=repo_root)
    write_json(first, commands_dir / "visualization_first.json")
    write_json(second, commands_dir / "visualization_second.json")

    first_summary = _parsed_summary_payload(first)
    second_summary = _parsed_summary_payload(second)
    if str(first.get("status")) != "pass":
        issues.append(
            _issue(
                "blocking",
                "The first Milestone 12 visualization regeneration command did not complete successfully.",
            )
        )
    if str(second.get("status")) != "pass":
        issues.append(
            _issue(
                "blocking",
                "The second Milestone 12 visualization regeneration command did not complete successfully.",
            )
        )
    if first_summary is None or second_summary is None:
        issues.append(
            _issue(
                "blocking",
                "The Milestone 12 visualization command did not emit a machine-readable JSON summary.",
            )
        )
    if issues:
        audit = {
            "overall_status": "fail",
            "command": " ".join(command),
            "issues": issues,
        }
        write_json(audit, commands_dir / "visualization_audit.json")
        return audit

    summary_stable = first_summary == second_summary
    report_path = Path(str(first_summary["report_path"])).resolve()
    summary_path = Path(str(first_summary["summary_path"])).resolve()
    artifact_hashes_stable = _capture_visualization_hashes(first_summary) == _capture_visualization_hashes(
        second_summary
    )
    if not summary_stable:
        issues.append(
            _issue(
                "blocking",
                "Repeated Milestone 12 visualization regenerations produced different summary payloads.",
            )
        )
    if not artifact_hashes_stable:
        issues.append(
            _issue(
                "blocking",
                "Repeated Milestone 12 visualization regenerations produced non-deterministic report artifacts.",
            )
        )
    if "no local server is required" not in str(first_summary.get("viewer_open_hint", "")):
        issues.append(
            _issue(
                "blocking",
                "The Milestone 12 visualization summary did not preserve the static-viewer open hint.",
            )
        )

    audit = {
        "overall_status": _overall_status_from_issues(issues),
        "command": " ".join(command),
        "report_path": str(report_path),
        "report_file_url": str(first_summary["report_file_url"]),
        "summary_path": str(summary_path),
        "summary_stable": summary_stable,
        "artifact_hashes_stable": artifact_hashes_stable,
        "comparison_card_ids": list(first_summary["comparison_card_ids"]),
        "matrix_ids": list(first_summary["matrix_ids"]),
        "phase_map_reference_count": int(first_summary["phase_map_reference_count"]),
        "decision_panel_status": str(first_summary["decision_panel_status"]),
        "viewer_open_hint": str(first_summary["viewer_open_hint"]),
        "issues": issues,
    }
    write_json(audit, commands_dir / "visualization_audit.json")
    return audit


def _build_workflow_coverage(
    *,
    fixture_verification: Mapping[str, Any],
    analysis_plan_audit: Mapping[str, Any],
    comparison_workflow_audit: Mapping[str, Any],
    packaged_export_audit: Mapping[str, Any],
    visualization_audit: Mapping[str, Any],
    documentation_audit: Mapping[str, Any],
) -> dict[str, bool]:
    return {
        "fixture_suite_passed": str(fixture_verification.get("status", "")) == "pass",
        "analysis_plan_verified": str(analysis_plan_audit["overall_status"]) == "pass",
        "comparison_workflow_verified": str(comparison_workflow_audit["overall_status"]) == "pass",
        "packaged_exports_verified": str(packaged_export_audit["overall_status"]) == "pass",
        "visualization_verified": str(visualization_audit["overall_status"]) == "pass",
        "documentation_verified": str(documentation_audit["overall_status"]) == "pass",
    }


def _audit_documentation(*, repo_root: Path) -> dict[str, Any]:
    audits: dict[str, Any] = {}
    issues: list[dict[str, str]] = []
    for relative_path, required_snippets in DEFAULT_DOCUMENTATION_SNIPPETS.items():
        doc_path = repo_root / relative_path
        if not doc_path.exists():
            issues.append(
                _issue(
                    "blocking",
                    f"{relative_path} is missing, so the Milestone 12 readiness workflow is not documented there.",
                )
            )
            audits[relative_path] = {
                "status": "fail",
                "path": str(doc_path.resolve()),
                "missing_snippets": list(required_snippets),
            }
            continue
        content = doc_path.read_text(encoding="utf-8")
        missing_snippets = [snippet for snippet in required_snippets if snippet not in content]
        if missing_snippets:
            issues.append(
                _issue(
                    "blocking",
                    f"{relative_path} is missing the Milestone 12 readiness snippets {missing_snippets!r}.",
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


def _parsed_summary_payload(command_summary: Mapping[str, Any]) -> dict[str, Any] | None:
    parsed = command_summary.get("parsed_summary")
    if isinstance(parsed, Mapping):
        return copy.deepcopy(dict(parsed))
    return None


def _load_json_mapping(path: str | Path) -> dict[str, Any]:
    resolved = Path(path).resolve()
    with resolved.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{resolved} must contain a JSON object.")
    return copy.deepcopy(dict(payload))


def _comparison_summary_fingerprint(summary: Mapping[str, Any]) -> dict[str, Any]:
    packaged = _require_mapping(
        summary.get("packaged_analysis_bundle"),
        field_name="summary.packaged_analysis_bundle",
    )
    return {
        "summary_version": str(summary["summary_version"]),
        "bundle_inventory": copy.deepcopy(summary["bundle_set"]["bundle_inventory"]),
        "task_scores": copy.deepcopy(summary["task_scores"]),
        "null_test_results": copy.deepcopy(summary["null_test_results"]),
        "decision_panel": copy.deepcopy(summary["milestone_1_decision_panel"]),
        "output_summaries": copy.deepcopy(summary["output_summaries"]),
        "packaged_bundle_reference": copy.deepcopy(packaged["bundle_reference"]),
        "artifact_inventory": copy.deepcopy(packaged["artifact_inventory"]),
    }


def _capture_analysis_artifact_hashes(summary: Mapping[str, Any]) -> dict[str, str]:
    packaged = _require_mapping(
        summary.get("packaged_analysis_bundle"),
        field_name="summary.packaged_analysis_bundle",
    )
    file_paths = {
        "summary_path": Path(str(summary["summary_path"])).resolve(),
        "metadata_json": Path(str(packaged["metadata_path"])).resolve(),
        "comparison_summary": Path(str(packaged["packaged_summary_path"])).resolve(),
        "task_summary_rows": Path(str(packaged["task_summary_path"])).resolve(),
        "null_test_table": Path(str(packaged["null_test_table_path"])).resolve(),
        "comparison_matrices": Path(str(packaged["comparison_matrices_path"])).resolve(),
        "visualization_catalog": Path(str(packaged["visualization_catalog_path"])).resolve(),
        "analysis_ui_payload": Path(str(packaged["analysis_ui_payload_path"])).resolve(),
        "offline_report_index": Path(str(packaged["report_path"])).resolve(),
        "offline_report_summary": Path(str(packaged["report_summary_path"])).resolve(),
    }
    return {
        name: _hash_file(path)
        for name, path in file_paths.items()
    }


def _capture_visualization_hashes(summary: Mapping[str, Any]) -> dict[str, str]:
    return {
        "report_index": _hash_file(Path(str(summary["report_path"])).resolve()),
        "report_summary": _hash_file(Path(str(summary["summary_path"])).resolve()),
    }


def _overall_status_from_issues(issues: Sequence[Mapping[str, Any]]) -> str:
    severities = {str(item.get("severity", "")) for item in issues}
    if "blocking" in severities:
        return "fail"
    if "review" in severities:
        return "review"
    return "pass"


def _render_milestone12_readiness_markdown(*, summary: Mapping[str, Any]) -> str:
    readiness = dict(summary[FOLLOW_ON_READINESS_KEY])
    analysis_plan_audit = dict(summary["analysis_plan_audit"])
    comparison_workflow_audit = dict(summary["comparison_workflow_audit"])
    packaged_export_audit = dict(summary["packaged_export_audit"])
    visualization_audit = dict(summary["visualization_audit"])
    documentation_audit = dict(summary["documentation_audit"])
    workflow_coverage = dict(summary["workflow_coverage"])
    lines = [
        "# Milestone 12 Readiness Report",
        "",
        f"- Generated at: `{summary['generated_at_utc']}`",
        f"- Readiness verdict: `{readiness['status']}`",
        f"- Ready for Milestones 13 and 14: `{readiness[READY_FOR_FOLLOW_ON_WORK_KEY]}`",
        f"- Representative manifest: `{summary['source_manifest_path']}`",
        f"- Fixture config: `{summary['fixture_config_path']}`",
        f"- Visualization open URL: `{summary['visualization_report_file_url']}`",
        "",
        "## Verified Workflow",
        "",
        f"- Fixture suite passed: `{workflow_coverage['fixture_suite_passed']}`",
        f"- Analysis-plan resolution audit: `{analysis_plan_audit['overall_status']}`",
        f"- Comparison workflow audit: `{comparison_workflow_audit['overall_status']}`",
        f"- Packaged export audit: `{packaged_export_audit['overall_status']}`",
        f"- Visualization regeneration audit: `{visualization_audit['overall_status']}`",
        f"- Documentation audit: `{documentation_audit['overall_status']}`",
        f"- Bundle inventory count: `{comparison_workflow_audit.get('bundle_inventory_count', 0)}`",
        f"- Shared metric rows: `{comparison_workflow_audit.get('shared_metric_row_count', 0)}`",
        f"- Task-decoder metric rows: `{comparison_workflow_audit.get('task_metric_row_count', 0)}`",
        f"- Wave-diagnostic metric rows: `{comparison_workflow_audit.get('wave_metric_row_count', 0)}`",
        f"- Quantitative baseline-versus-wave rollups verified: `{comparison_workflow_audit.get('quantitative_comparison_verified', False)}`",
        f"- Static viewer hint: `{summary['visualization_open_hint']}`",
        "",
        "## Audit Notes",
        "",
        f"- Active output ids: `{analysis_plan_audit.get('active_output_ids', [])}`",
        f"- Comparison group ids: `{analysis_plan_audit.get('comparison_group_ids', [])}`",
        f"- Null test status: `{comparison_workflow_audit.get('null_test_status_by_id', {})}`",
        f"- Comparison card outputs: `{packaged_export_audit.get('comparison_card_output_ids', [])}`",
        f"- Comparison matrix ids: `{packaged_export_audit.get('comparison_matrix_ids', [])}`",
        f"- Phase map reference count: `{packaged_export_audit.get('phase_map_reference_count', 0)}`",
        "",
        "## Remaining Risks",
        "",
    ]
    for risk in summary["remaining_risks"]:
        lines.extend(
            [
                f"- `{risk['risk_id']}` [{risk['category']} / {risk['severity']}] {risk['summary']}",
                f"  Guidance: {risk['guidance']}",
            ]
        )
    lines.extend(["", "## Follow-On Issues", ""])
    for issue in summary["follow_on_issues"]:
        lines.extend(
            [
                f"- `{issue['ticket_id']}` [{issue['severity']}] {issue['title']}",
                f"  Reproduction: {issue['reproduction']}",
            ]
        )
    lines.extend(["", "## Commands", ""])
    for command in summary["verification_command_sequence"]:
        lines.append(f"- `{command}`")
    return "\n".join(lines) + "\n"


def _require_mapping(payload: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    return copy.deepcopy(dict(payload))


def _default_root_specs() -> list[dict[str, object]]:
    return [
        {
            "root_id": 101,
            "cell_type": "fixture_101",
            "project_role": "surface_simulated",
            "asset_profile": "surface",
        },
        {
            "root_id": 202,
            "cell_type": "fixture_202",
            "project_role": "surface_simulated",
            "asset_profile": "surface",
        },
    ]


def _normalize_root_specs(
    root_specs: list[dict[str, object]] | None,
) -> list[dict[str, object]]:
    resolved_specs = root_specs or _default_root_specs()
    normalized: list[dict[str, object]] = []
    seen_root_ids: set[int] = set()
    for item in resolved_specs:
        root_id = int(item["root_id"])
        if root_id in seen_root_ids:
            raise ValueError(f"Duplicate root_id in fixture specs: {root_id}")
        seen_root_ids.add(root_id)
        normalized.append(
            {
                "root_id": root_id,
                "cell_type": str(item.get("cell_type", f"fixture_{root_id}")),
                "project_role": str(item.get("project_role", "surface_simulated")),
                "asset_profile": str(item.get("asset_profile", "surface")),
            }
        )
    normalized.sort(key=lambda item: int(item["root_id"]))
    return normalized


def _write_geometry_manifest_fixture(
    output_dir: Path,
    *,
    root_specs: list[dict[str, object]] | None = None,
) -> None:
    normalized_root_specs = _normalize_root_specs(root_specs)
    root_ids = [int(item["root_id"]) for item in normalized_root_specs]
    coupling_dir = output_dir / "processed_coupling"
    local_synapse_registry_path = coupling_dir / "synapse_registry.csv"
    local_synapse_registry_path.parent.mkdir(parents=True, exist_ok=True)
    local_synapse_registry_path.write_text(
        "\n".join(
            [
                "synapse_row_id,pre_root_id,post_root_id",
                *[
                    f"fixture-{index},{pre_root_id},{post_root_id}"
                    for index, (pre_root_id, post_root_id) in enumerate(
                        [
                            (pre_root_id, post_root_id)
                            for pre_root_id in root_ids
                            for post_root_id in root_ids
                            if pre_root_id != post_root_id
                        ],
                        start=1,
                    )
                ],
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    coupling_paths_by_root = {
        root_id: build_root_coupling_bundle_paths(
            root_id,
            processed_coupling_dir=coupling_dir,
        )
        for root_id in root_ids
    }
    for bundle_paths in coupling_paths_by_root.values():
        _write_placeholder_file(bundle_paths.incoming_anchor_map_path)
        _write_placeholder_file(bundle_paths.outgoing_anchor_map_path)
        _write_placeholder_file(bundle_paths.coupling_index_path)

    edge_paths = [
        coupling_dir / "edges" / f"{pre_root_id}__to__{post_root_id}_coupling.npz"
        for pre_root_id in root_ids
        for post_root_id in root_ids
        if pre_root_id != post_root_id
    ]
    for edge_path in edge_paths:
        _write_placeholder_file(edge_path)

    bundle_records = {}
    for spec in normalized_root_specs:
        root_id = int(spec["root_id"])
        asset_profile = str(spec["asset_profile"])
        asset_statuses = _asset_statuses_for_profile(asset_profile)
        bundle_paths = build_geometry_bundle_paths(
            root_id,
            meshes_raw_dir=output_dir / "meshes_raw",
            skeletons_raw_dir=output_dir / "skeletons_raw",
            processed_mesh_dir=output_dir / "processed_meshes",
            processed_graph_dir=output_dir / "processed_graphs",
        )
        if asset_statuses[SIMPLIFIED_MESH_KEY] == ASSET_STATUS_READY:
            _write_placeholder_file(bundle_paths.simplified_mesh_path)
        if asset_statuses[RAW_SKELETON_KEY] == ASSET_STATUS_READY:
            _write_skeleton_fixture(bundle_paths.raw_skeleton_path)
        operator_bundle_metadata = _write_fixture_operator_bundle(
            bundle_paths=bundle_paths,
            root_id=root_id,
            asset_statuses=asset_statuses,
            asset_profile=asset_profile,
        )
        coupling_metadata = build_coupling_bundle_metadata(
            root_id=root_id,
            processed_coupling_dir=coupling_dir,
            local_synapse_registry_status=ASSET_STATUS_READY,
            incoming_anchor_map_status=ASSET_STATUS_READY,
            outgoing_anchor_map_status=ASSET_STATUS_READY,
            coupling_index_status=ASSET_STATUS_READY,
            edge_bundles=[
                build_edge_coupling_bundle_reference(
                    root_id=root_id,
                    pre_root_id=pre_root_id,
                    post_root_id=post_root_id,
                    processed_coupling_dir=coupling_dir,
                    status=ASSET_STATUS_READY,
                )
                for pre_root_id in root_ids
                for post_root_id in root_ids
                if pre_root_id != post_root_id
                and root_id in (pre_root_id, post_root_id)
            ],
        )
        bundle_records[root_id] = build_geometry_manifest_record(
            bundle_paths=bundle_paths,
            asset_statuses=asset_statuses,
            dataset_name="public",
            materialization_version=783,
            meshing_config_snapshot=_meshing_config_snapshot(),
            registry_metadata={
                "cell_type": str(spec["cell_type"]),
                "project_role": str(spec["project_role"]),
            },
            operator_bundle_metadata=operator_bundle_metadata,
            coupling_bundle_metadata=coupling_metadata,
            processed_coupling_dir=coupling_dir,
        )

    write_geometry_manifest(
        manifest_path=output_dir / "asset_manifest.json",
        bundle_records=bundle_records,
        dataset_name="public",
        materialization_version=783,
        meshing_config_snapshot=_meshing_config_snapshot(),
        processed_coupling_dir=coupling_dir,
    )


def _asset_statuses_for_profile(asset_profile: str) -> dict[str, str]:
    normalized_profile = str(asset_profile)
    if normalized_profile == "surface":
        asset_statuses = default_asset_statuses(fetch_skeletons=False)
        asset_statuses.update(
            {
                SIMPLIFIED_MESH_KEY: ASSET_STATUS_READY,
                FINE_OPERATOR_KEY: ASSET_STATUS_READY,
                COARSE_OPERATOR_KEY: ASSET_STATUS_READY,
                TRANSFER_OPERATORS_KEY: ASSET_STATUS_READY,
                OPERATOR_METADATA_KEY: ASSET_STATUS_READY,
            }
        )
        return asset_statuses
    if normalized_profile == "skeleton":
        asset_statuses = default_asset_statuses(fetch_skeletons=True)
        asset_statuses.update(
            {
                RAW_SKELETON_KEY: ASSET_STATUS_READY,
            }
        )
        return asset_statuses
    if normalized_profile == "point":
        return default_asset_statuses(fetch_skeletons=False)
    raise ValueError(f"Unsupported fixture asset_profile {asset_profile!r}.")


def _meshing_config_snapshot() -> dict[str, object]:
    return {
        "fetch_skeletons": False,
        "operator_assembly": {
            "version": "operator_assembly.v1",
            "boundary_condition": {
                "version": "boundary_condition.v1",
                "mode": "closed_surface_zero_flux",
            },
            "anisotropy": {
                "version": "anisotropy.v1",
                "model": "local_tangent_diagonal",
                "default_tensor": [1.2, 0.8],
            },
        },
    }


def _write_fixture_operator_bundle(
    *,
    bundle_paths: object,
    root_id: int,
    asset_statuses: dict[str, str],
    asset_profile: str,
) -> dict[str, object]:
    if asset_profile != "surface":
        return build_operator_bundle_metadata(
            bundle_paths=bundle_paths,
            asset_statuses=asset_statuses,
            meshing_config_snapshot=_meshing_config_snapshot(),
        )

    fine_operator = sp.csr_matrix(
        [
            [1.0, -1.0, 0.0],
            [-1.0, 2.0, -1.0],
            [0.0, -1.0, 1.0],
        ],
        dtype=np.float64,
    )
    write_deterministic_npz(
        {
            "root_id": np.asarray([root_id], dtype=np.int64),
            **{
                f"operator_{key}": value
                for key, value in serialize_sparse_matrix(fine_operator).items()
            },
        },
        bundle_paths.fine_operator_path,
    )
    coarse_operator = sp.csr_matrix(
        [
            [1.0, -1.0],
            [-1.0, 1.0],
        ],
        dtype=np.float64,
    )
    write_deterministic_npz(
        {
            "root_id": np.asarray([root_id], dtype=np.int64),
            **{
                f"operator_{key}": value
                for key, value in serialize_sparse_matrix(coarse_operator).items()
            },
        },
        bundle_paths.coarse_operator_path,
    )
    restriction = sp.csr_matrix(
        [
            [1.0, 0.0, 0.0],
            [0.0, 0.5, 0.5],
        ],
        dtype=np.float64,
    )
    prolongation = sp.csr_matrix(
        [
            [1.0, 0.0],
            [0.0, 1.0],
            [0.0, 1.0],
        ],
        dtype=np.float64,
    )
    write_deterministic_npz(
        {
            "root_id": np.asarray([root_id], dtype=np.int64),
            **{
                f"restriction_{key}": value
                for key, value in serialize_sparse_matrix(restriction).items()
            },
            **{
                f"prolongation_{key}": value
                for key, value in serialize_sparse_matrix(prolongation).items()
            },
            **{
                f"normalized_restriction_{key}": value
                for key, value in serialize_sparse_matrix(restriction).items()
            },
            **{
                f"normalized_prolongation_{key}": value
                for key, value in serialize_sparse_matrix(prolongation).items()
            },
        },
        bundle_paths.transfer_operator_path,
    )
    write_json({"descriptor_version": 1, "root_id": root_id}, bundle_paths.descriptor_sidecar_path)
    write_json({"qa_version": 1, "root_id": root_id}, bundle_paths.qa_sidecar_path)

    operator_bundle_metadata = build_operator_bundle_metadata(
        bundle_paths=bundle_paths,
        asset_statuses=asset_statuses,
        meshing_config_snapshot=_meshing_config_snapshot(),
        realized_operator_metadata={
            "realization_mode": "fixture_mass_normalized_surface_operator",
            "operator_assembly": _meshing_config_snapshot()["operator_assembly"],
            "preferred_discretization_family": "triangle_mesh_cotangent_fem",
            "discretization_family": "triangle_mesh_cotangent_fem",
            "mass_treatment": "lumped_mass",
            "normalization": "mass_normalized",
            "boundary_condition_mode": "closed_surface_zero_flux",
            "anisotropy_model": "local_tangent_diagonal",
            "fallback_policy": {
                "allowed": False,
                "used": False,
                "reason": "",
                "fallback_discretization_family": "triangle_mesh_cotangent_fem",
            },
            "geodesic_neighborhood": {
                "mode": "fixture_patch_neighbors",
            },
            "transfer_restriction_mode": "mass_weighted_patch_average",
            "transfer_prolongation_mode": "constant_on_patch",
            "transfer_preserves_mass_or_area_totals": True,
            "normalized_state_transfer_available": True,
        },
    )
    write_json(operator_bundle_metadata, bundle_paths.operator_metadata_path)
    return operator_bundle_metadata


def _write_skeleton_fixture(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "1 1 0.0 0.0 0.0 1.0 -1",
                "2 3 1.0 0.0 0.0 0.5 1",
                "3 3 2.0 0.0 0.0 0.5 2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_placeholder_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")
